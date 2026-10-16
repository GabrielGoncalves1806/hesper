"""v0.5 Marco 2 · base respirável: os blocos (chão, parede, porta solo e dupla) e a vedação.

Python puro (nada de pygame), testado em tests/test_base.py.

Os blocos moram no `Layer.base` (`BaseGrid`), não na lista de máquinas: uma base tem centenas de tiles e as
máquinas são varridas toda hora (colisão, energia). Cada tile guarda no máximo 1 bloco. A porta dupla é UM bloco que
ocupa 2 tiles (âncora = a metade de oeste/norte).

Vedação (flood fill): a partir do tile do Dispersor, andando só por chão da base, vizinhança de 4. Cada vizinho:
chão = entra na fila; parede ou porta = muro (ok); qualquer outra coisa = vazamento (guarda o PRIMEIRO achado e para).
A base vale com ≥ BASE_MIN_FLOOR de chão, ≥ BASE_MIN_DOORS portas e ≤ BASE_MAX_FLOOR de chão. A porta conta como muro
aberta ou fechada: ela não quebra a vedação. O resultado (`Seal`) guarda os tiles examinados (`watch`): a grade lembra
as últimas mudanças de bloco e o recálculo só roda quando uma delas cai dentro do `watch`, nunca por frame.
"""

from collections import deque
from dataclasses import dataclass, field

from game import config as C

T = C.TILE
H, V = "h", "v"


@dataclass(eq=False)
class BaseBlock:
    kind: str                  # C.BASE_FLOOR / BASE_WALL / BASE_DOOR / BASE_DOOR2
    tx: int                    # tile (a porta dupla: a metade de oeste/norte)
    ty: int
    orient: str = H            # só a dupla: H = 2 tiles lado a lado, V = um em cima do outro. A solo se deduz dos vizinhos
    frame: float = 0.0         # portas: 0 (fechada) .. 3 (aberta). Não vai no save
    opening: bool = False      # portas: indo pro aberto?
    ruin: bool = field(default=False, compare=False)   # v0.7 M1: casca de ruína (game/ruins.py): intocável, não veda, não vai no save
    # derivado da vizinhança (BaseGrid.layout), no cache por versão da grade:
    _layout: tuple = field(default=("", "", -1), repr=False, compare=False)

    @property
    def is_floor(self) -> bool:
        return self.kind == C.BASE_FLOOR

    @property
    def is_wall(self) -> bool:
        return self.kind == C.BASE_WALL

    @property
    def is_door(self) -> bool:
        return self.kind in C.BASE_DOOR_KINDS

    @property
    def is_double(self) -> bool:
        return self.kind == C.BASE_DOOR2

    # contrato de "coisa desmontável" (GameState._update_dismantle trata máquina e bloco igual)
    is_chest = False
    submerged = False
    build = 0.0

    @property
    def tiles(self) -> list[tuple[int, int]]:
        if self.is_double:
            return [(self.tx, self.ty), (self.tx + 1, self.ty)] if self.orient == H else \
                [(self.tx, self.ty), (self.tx, self.ty + 1)]
        return [(self.tx, self.ty)]

    @property
    def type(self) -> C.MachineType:
        return C.MACHINES[self.kind]

    @property
    def closed(self) -> bool:
        """Porta que ainda bloqueia o player (quadros 0–2); a aberta (quadro 3) deixa passar."""
        return self.frame < C.DOOR_FRAMES - 1

    @property
    def frame_index(self) -> int:
        return max(0, min(C.DOOR_FRAMES - 1, int(self.frame)))

    @property
    def xray(self) -> bool:
        """Entra no raio-x (cobre o player como parede): parede, ou porta nos quadros 0–1."""
        return self.is_wall or (self.is_door and self.frame < C.DOOR_XRAY_FRAMES)


def floor_variant(tx: int, ty: int) -> int:
    """Qual dos 4 desenhos do chão (base_floor_N) o tile usa: sorteio por hash do tile."""
    return C.FLOOR_PICK[((tx * 73856093) ^ (ty * 19349663)) & 7]


@dataclass(frozen=True)
class Seal:
    """Resultado da vedação a partir de um Dispersor."""
    reason: str                              # "sealed", "leak", "small", "nodoor", "big", "nofloor"
    floor: frozenset = frozenset()           # chão alcançado
    doors: int = 0                           # portas distintas na borda
    leak: tuple[int, int] | None = None      # o tile furado (o primeiro vazamento achado)
    watch: frozenset = frozenset()           # tiles examinados: mudança de bloco aqui exige recalcular
    inside: frozenset = frozenset()          # onde o ar vale: o chão e as portas da borda

    @property
    def ok(self) -> bool:
        return self.reason == "sealed"


class BaseGrid:
    """Os blocos da base de uma camada."""

    def __init__(self):
        self.cells: dict[tuple[int, int], BaseBlock] = {}
        self.blocks: list[BaseBlock] = []        # um por objeto (a dupla conta 1), na ordem em que foram postos
        self.door_list: list[BaseBlock] = []     # as portas (a animação varre só elas)
        self.version = 0
        self.log: deque = deque(maxlen=C.BASE_LOG_KEEP)   # (versão, tiles mudados)

    def __len__(self) -> int:
        return len(self.blocks)

    def get(self, tile) -> BaseBlock | None:
        return self.cells.get(tile)

    def has_floor(self, tile) -> bool:
        b = self.cells.get(tile)
        return b is not None and b.is_floor

    def is_wall(self, tile) -> bool:
        """Parede da base (a porta NÃO conta: é o que o desenho do autotile e da face usa)."""
        b = self.cells.get(tile)
        return b is not None and b.is_wall

    def is_barrier(self, tile) -> bool:
        """Parede ou porta (de qualquer tile da dupla): o que fecha a vedação e o raio-x lê."""
        b = self.cells.get(tile)
        return b is not None and (b.is_wall or b.is_door)

    def doors(self) -> list[BaseBlock]:
        return self.door_list

    # ---- mexer ---------------------------------------------------------------------------------
    def add(self, block: BaseBlock) -> None:
        for t in block.tiles:
            self.cells[t] = block
        self.blocks.append(block)
        if block.is_door:
            self.door_list.append(block)
        self._changed(block.tiles)

    def remove(self, block: BaseBlock) -> None:
        for t in block.tiles:
            if self.cells.get(t) is block:
                del self.cells[t]
        self.blocks.remove(block)
        if block.is_door:
            self.door_list.remove(block)
        self._changed(block.tiles)

    def _changed(self, tiles) -> None:
        self.version += 1
        self.log.append((self.version, frozenset(tiles)))

    def changed_near(self, since: int, watch) -> bool:
        """Alguma mudança de bloco depois da versão `since` caiu em `watch`? (log curto demais = sim, por garantia)"""
        if self.version == since:
            return False
        if not self.log or self.log[0][0] > since + 1:
            return True
        return any(v > since and not tiles.isdisjoint(watch) for v, tiles in self.log)

    # ---- porta: orientação e borda de fora -------------------------------------------------------
    def layout(self, door: BaseBlock) -> tuple[str, str]:
        """(orientação, borda) da porta, deduzidas dos vizinhos (no cache por versão da grade).

        Orientação: a dupla é a dela (lado a lado = h). A solo é "h" se oeste/leste são parede ou porta, "v" se norte/sul
        são e os lados não; no empate, h. Borda (variante B, a folha vai na face de FORA da parede, oposta ao chão
        da base): h com chão ao norte = "s", chão ao sul = "n"; v com chão a oeste = "e", a leste = "w".
        Porta solta (sem chão em volta): h_s / v_e."""
        if door._layout[2] == self.version:
            return door._layout[0], door._layout[1]
        tiles = door.tiles
        if door.is_double:
            orient = door.orient
        else:
            tx, ty = door.tx, door.ty
            lr = self.is_barrier((tx - 1, ty)) or self.is_barrier((tx + 1, ty))
            ud = self.is_barrier((tx, ty - 1)) or self.is_barrier((tx, ty + 1))
            orient = V if ud and not lr else H
        if orient == H:
            north = any(self.has_floor((x, y - 1)) for x, y in tiles)
            south = any(self.has_floor((x, y + 1)) for x, y in tiles)
            edge = "n" if south and not north else "s"
        else:
            west = any(self.has_floor((x - 1, y)) for x, y in tiles)
            east = any(self.has_floor((x + 1, y)) for x, y in tiles)
            edge = "w" if east and not west else "e"
        door._layout = (orient, edge, self.version)
        return orient, edge

    def door_rects(self, door: BaseBlock) -> list[tuple[int, int, int, int]]:
        """Retângulos de colisão (px do mundo) da porta no estado atual: tabela da v1.2 do report da Designer.
        Fechada (quadros 0–2): a faixa da moldura inteira. Aberta (quadro 3): só as jambas de 2 px."""
        orient, edge = self.layout(door)
        x, y = door.tx * T, door.ty * T
        n = 2 if door.is_double else 1
        long_ = n * T
        closed = door.closed
        if orient == H:
            ry = y + 27 if edge == "s" else y
            if closed:
                return [(x, ry, long_, 5)]
            return [(x, ry, 2, 5), (x + long_ - 2, ry, 2, 5)]
        rx = x + 26 if edge == "e" else x
        if closed:
            return [(rx, y, 6, long_)]
        return [(rx, y, 6, 2), (rx, y + long_ - 2, 6, 2)]

    def solids_in(self, x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int, int, int]]:
        """Retângulos sólidos dos blocos nos tiles x0..x1 × y0..y1: parede = o tile inteiro; porta = a tabela."""
        out = []
        seen = set()
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                b = self.cells.get((tx, ty))
                if b is None or b.is_floor or id(b) in seen:
                    continue
                if b.is_wall:
                    out.append((tx * T, ty * T, T, T))
                else:                                   # a dupla sai uma vez só, mesmo com os 2 tiles na caixa
                    seen.add(id(b))
                    out += self.door_rects(b)
        return out

    # ---- vedação -------------------------------------------------------------------------------------
    def seal_from(self, start: tuple[int, int]) -> Seal:
        """Flood fill a partir de `start` (o tile do Dispersor). Ver o topo do arquivo."""
        if not self.has_floor(start):
            return Seal("nofloor", leak=start, watch=frozenset([start]))
        floor = {start}
        watch = {start}
        queue = deque([start])
        doors: set[int] = set()
        door_tiles: set[tuple[int, int]] = set()
        while queue:
            x, y = queue.popleft()
            for n in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                watch.add(n)
                b = self.cells.get(n)
                if b is None or b.ruin or (not b.is_floor and not b.is_wall and not b.is_door):   # casca de ruína = vazamento
                    return Seal("leak", frozenset(floor), len(doors), n, frozenset(watch))
                if b.is_floor:
                    if n not in floor:
                        floor.add(n)
                        queue.append(n)
                        if len(floor) > C.BASE_MAX_FLOOR:
                            return Seal("big", frozenset(floor), len(doors), None, frozenset(watch))
                elif b.is_door:
                    doors.add(id(b))
                    door_tiles.update(b.tiles)
        if len(floor) < C.BASE_MIN_FLOOR:
            reason = "small"
        elif len(doors) < C.BASE_MIN_DOORS:
            reason = "nodoor"
        else:
            reason = "sealed"
        return Seal(reason, frozenset(floor), len(doors), None, frozenset(watch), frozenset(floor | door_tiles))
