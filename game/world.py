"""Mapa de uma camada: uma grade de tiles gerada por noise com seed fixa.

`World` é o mapa em si (consultas e regras de tile). `World.generate(seed)` gera a CAVERNA
(256×256 desde o v0.6 Fundo M1, em game/cave_gen.py: regiões, paredes com minério, terminais, rampa de subida 3×3 embaixo da cratera). A caverna não terraforma (`terraforms = False`: sem água nem plantas). A SUPERFÍCIE (deserto SURFACE_W×SURFACE_H, onde fica a base) é montada pelo game/surface_gen.py
em cima do mesmo `World`.

Paredes altas (rocha, minério, borda, terminal) × sólidos baixos (rocha pequena, cratera, destroço, formação): os dois
bloqueiam o player, mas só a parede alta tem topo elevado e face (ver render.py).

Não usa pygame: é só dados + regras. Por isso dá pra testar sem abrir janela.
"""

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from game import config as C
from game.geo import FROST


# ---------------------------------------------------------------------------
# Noise: um "ruído suave" determinístico (mesma seed = mesmo mapa sempre)
# ---------------------------------------------------------------------------
def hash01(x: int, y: int, seed: int) -> float:
    """Transforma (x, y, seed) num número 'aleatório' entre 0 e 1, sempre o mesmo pra mesma entrada."""
    h = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296


def value_noise(x: float, y: float, seed: int) -> float:
    """Ruído de valor: sorteia um número em cada ponto inteiro da grade e interpola suave entre eles."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)   # curva "smoothstep"
    a = hash01(ix, iy, seed)
    b = hash01(ix + 1, iy, seed)
    c = hash01(ix, iy + 1, seed)
    d = hash01(ix + 1, iy + 1, seed)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


# ---------------------------------------------------------------------------
# Mundo
# ---------------------------------------------------------------------------
# Tiles que o lago das bacias cobre (M3.3): o chão e a rocha pequena (que fica com o pé na água)
LAKE_TILES = frozenset(C.FLOOR_TILES | set(C.SMALL_ROCKS))


@dataclass(frozen=True)
class Vein:
    """Veio de minério 2×2 no chão. (tx, ty) é o tile de cima à esquerda."""
    resource: str
    tx: int
    ty: int

    @property
    def tiles(self) -> list[tuple[int, int]]:
        return [(self.tx + dx, self.ty + dy) for dy in (0, 1) for dx in (0, 1)]

    @property
    def center(self) -> tuple[float, float]:
        """Centro do veio em tiles (é a quina entre os 4 tiles)."""
        return self.tx + 1.0, self.ty + 1.0


class World:
    def __init__(self, seed: int, width: int = C.WORLD_W, height: int = C.WORLD_H):
        self.seed = seed
        self.width = width
        self.height = height
        self.tiles = [[C.ROCK] * width for _ in range(height)]   # tiles[y][x]
        self.terminals: list[tuple[int, int]] = []               # posição (tx, ty) de cada terminal, na ordem dos logs
        self.lowness = [[0.0] * width for _ in range(height)]    # "altura" do chão: valores baixos viram poça
        self.veins: list[Vein] = []                               # veios de minério 2×2 no chão
        self._vein_tiles: dict[tuple[int, int], Vein] = {}        # tile -> veio que ocupa ele
        self.center: tuple[int, int] = (width // 2, height // 2)  # "centro" da camada (base ou chegada da rampa), em tiles
        self.floor_kind = C.FLOOR                                 # o chão que fica quando um sólido quebra
        # Rampa 3×3 da camada (tiles CRATER): a cratera de descida na superfície, a rampa de subida na caverna.
        # Canto de cima à esquerda; as regras de uso ficam em game/layers.py (ramp_target, ramp_arrival).
        self.crater: tuple[int, int] | None = None
        self.terraforms = True                                    # False na caverna: sem água nem plantas, nunca
        # v0.6 Fundo M1 (só na caverna): região de cada tile, (H, W) uint8 com os números do game/geo.py
        # (PLATEAU = centro, SALAR, BASALT, FROST). None na superfície (lá a região é do self.geo).
        self.cave_region: np.ndarray | None = None
        self.sand_variants: list[bytes] | None = None             # variação do sand_{stage}_{v} por tile (superfície)
        self.wrecks: list = []                                    # destroços (game/wrecks.py), só na superfície
        self._wreck_index: dict | None = None                     # tile (área ou caixa) -> destroço (lazy)
        # v0.4 Marco 2 (só na superfície): a geografia da seed (game/geo.py · Geo, só leitura) e os tiles onde nada
        # nasce (halo das formações, bolsões e avental dos gelos-portão): veio, destroço, rocha pequena e a rocha que
        # reaparece respeitam (os afloramentos das formações são os únicos que ficam no halo)
        self.geo = None
        self.keep_clear: frozenset[tuple[int, int]] = frozenset()
        # v0.4 Marco 3 · M3.2: contêineres lacrados (tile C.CONTAINER), um no container_spot de cada bolsão
        self.containers: list[tuple[int, int]] = []
        # v0.4 Marco 3 (M3.3, só com geo): até que altura (escala do geo.height) a água das bacias subiu. Derivado do
        # índice de água (game/thaw.py · lake_level, GameState._apply_thaw), não vai no save. -1 = seco.
        self.water_level = -1.0
        # v0.4 Marco 3 · M3.5: tiles da caixa 4×2 dos gelos-portão ainda fechados (a fresta não abriu). Derivado
        # (nasce com todos na geração; o Layer.refresh_gates refaz). A colisão do gelo é por retângulo, não por tile:
        # isto é a sombra dele em tiles, pro `reachable_from` e pro mapa do scanner (pinta como pegada de formação).
        self.closed_gate_tiles: frozenset[tuple[int, int]] = frozenset()
        # v0.5 M3.6.4: tiles que o mapa do scanner esconde (o interior do bolsão da criatura com o portão grande fechado).
        # Derivado como o closed_gate_tiles (Layer.refresh_gates).
        self.hidden_tiles: frozenset[tuple[int, int]] = frozenset()
        self._geo_rows = None                                     # (altura, bacia, beira) em listas (ver _rows)
        # v0.7 M1 · Estruturas (game/ruins.py): as ruínas da camada, a pegada de todas (trava construção e rocha que
        # reaparece) e os terminais delas (tile da parede -> índice em C.LOGS). Saem da seed, não vão no save.
        self.ruins: list = []
        self.ruin_tiles: frozenset = frozenset()
        self.ruin_terminals: dict = {}

    # ---- geração ----------------------------------------------------------
    @classmethod
    def generate(cls, seed: int = C.WORLD_SEED) -> "World":
        """A CAVERNA da seed (game/cave_gen.py). Fica aqui pelo nome antigo, que os testes e o layers usam."""
        from game.cave_gen import generate_cave          # cave_gen importa World: o import fica aqui dentro
        return generate_cave(seed)

    def _add_vein(self, vein: Vein) -> None:
        self.veins.append(vein)
        for t in vein.tiles:
            self.set(*t, C.FLOOR)
            self._vein_tiles[t] = vein

    def reachable_from(self, start: tuple[int, int]) -> set[tuple[int, int]]:
        """Tiles de chão alcançáveis a pé a partir de `start` (sem cavar; o gelo-portão ainda fechado conta como
        parede, `closed_gate_tiles`). Busca em largura."""
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in seen and self.in_bounds(nx, ny) and not self.is_solid(nx, ny) \
                        and (nx, ny) not in self.closed_gate_tiles:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        return seen

    def vein_at(self, tx: int, ty: int) -> Vein | None:
        return self._vein_tiles.get((tx, ty))

    def wreck_at(self, tx: int, ty: int):
        """Destroço que ocupa esse tile (a área sólida ou a caixa dele), ou None."""
        if self._wreck_index is None:
            self._wreck_index = {t: w for w in self.wrecks for t in [*w.tiles, w.crate]}
        return self._wreck_index.get((tx, ty))

    # ---- consultas --------------------------------------------------------
    def in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.width and 0 <= ty < self.height

    def get(self, tx: int, ty: int) -> int:
        """Tipo do tile. Fora do mapa conta como rocha indestrutível."""
        if not self.in_bounds(tx, ty):
            return C.BEDROCK
        return self.tiles[ty][tx]

    def set(self, tx: int, ty: int, kind: int) -> None:
        if self.in_bounds(tx, ty):
            self.tiles[ty][tx] = kind

    def is_solid(self, tx: int, ty: int) -> bool:
        """Bloqueia o player (parede alta OU sólido baixo, como rocha pequena e cratera)."""
        return self.get(tx, ty) in C.SOLID_TILES

    def is_wall(self, tx: int, ty: int) -> bool:
        """Parede ALTA: tem topo elevado 24 px e face (rocha, minério, borda, terminal)."""
        return self.get(tx, ty) in C.WALL_TILES

    def is_floor(self, tx: int, ty: int) -> bool:
        """Chão livre (o da caverna ou a areia do deserto)."""
        return self.get(tx, ty) in C.FLOOR_TILES

    def visual_tile_at(self, px: float, py: float) -> tuple[int, int]:
        """Tile que a pessoa VÊ no pixel (px, py) do mundo.

        O topo de cada parede é desenhado 24 px acima do tile dela, cobrindo a parte de baixo
        do tile de cima. Então, se o ponto 24 px abaixo cai numa parede, é ela que está à vista.
        """
        tx, ty = int(px // C.TILE), int(py // C.TILE)
        below = int((py + C.WALL_LIFT) // C.TILE)
        if below != ty and self.is_wall(tx, below):
            return tx, below
        return tx, ty

    def is_minable(self, tx: int, ty: int) -> bool:
        return self.get(tx, ty) in C.MINE_TIME

    def region_at_cave(self, tx: int, ty: int) -> int | None:
        """Região da caverna no tile (None fora da caverna ou fora do mapa)."""
        if self.cave_region is None or not self.in_bounds(tx, ty):
            return None
        return int(self.cave_region[ty, tx])

    def is_hard(self, tx: int, ty: int) -> bool:
        """Parede que só a broca nv.2 quebra (v0.6 Fundo): a rocha dura e o minério de parede dentro do gelo e do
        basalto da caverna."""
        kind = self.get(tx, ty)
        if kind == C.HARD_ROCK:
            return True
        return kind in C.ORE_TILES and self.region_at_cave(tx, ty) in C.CAVE_HARD_REGIONS

    def dist_from_center(self, tx: int, ty: int) -> float:
        cx, cy = self.center
        return math.hypot(tx + 0.5 - cx, ty + 0.5 - cy)

    def _rows(self):
        """Altura, bacia e "beira d'água" do geo em listas de listas (consulta por tile bem mais barata que o
        numpy, e o render pergunta centenas de vezes por quadro). Calculado uma vez por geo."""
        if self._geo_rows is None:
            geo = self.geo
            basin = geo.basin >= 0
            r = C.LAKE_SHORE
            pad = np.pad(basin, r)
            h, w = basin.shape
            shore = np.zeros_like(basin)
            for dy in range(2 * r + 1):              # quadrado de lado 2r+1 em volta (dilatação do mapa das bacias)
                for dx in range(2 * r + 1):
                    shore |= pad[dy:dy + h, dx:dx + w]
            self._geo_rows = (geo.height.tolist(), basin.tolist(), shore.tolist())
        return self._geo_rows

    def _low_wet(self, tx: int, ty: int, stage: int) -> bool:
        """Água "crua": chão baixo o bastante pro estágio (antes da suavização do is_water). Só sem geo."""
        if stage < C.MIST_STAGE or not self.terraforms or not (0 <= tx < self.width and 0 <= ty < self.height):
            return False
        if self.lowness[ty][tx] >= C.WATER_THRESHOLD[stage]:   # o teste mais barato primeiro
            return False
        if not self.is_floor(tx, ty) or (tx, ty) in self._vein_tiles:   # água não cobre veio
            return False
        return self.dist_from_center(tx, ty) >= 7

    def is_water(self, tx: int, ty: int, stage: int) -> bool:
        """Água no tile (dá pra andar por cima).

        COM GEO (a superfície do v0.4, Marco 3): lago nas bacias. É água o tile de chão com `geo.height` abaixo do
        `water_level` (que sobe com o índice de água). O `stage` é ignorado e não tem nada aleatório: a água enche
        das partes mais fundas pra fora e nunca sai de uma bacia (o nível para em L3). A rocha pequena que estava
        no leito fica com o pé na água (a água passa por baixo dela). Veio, formação (a crosta de sal vira ilhota) e
        a base (sempre acima de L3) ficam secos.

        SEM GEO (testes antigos; a caverna nunca terraforma): a poça de antes, pelo `lowness`, só a partir da Névoa
        e crescendo com o estágio. Suavização (pra não sair água em xadrez ou ligada só pela quina): um tile de
        água crua só fica se tem um vizinho de lado que também é água, OU se é uma gota sozinha (nenhuma água nem
        nas diagonais). A checagem da gota olha o último estágio (Verde), assim a água de um estágio está sempre
        dentro da do estágio seguinte."""
        if self.geo is not None:
            level = self.water_level
            if level <= 0 or not self.terraforms or not (0 <= tx < self.width and 0 <= ty < self.height):
                return False
            if self._rows()[0][ty][tx] >= level:
                return False
            return self.tiles[ty][tx] in LAKE_TILES and (tx, ty) not in self._vein_tiles
        if not self._low_wet(tx, ty, stage):
            return False
        low = self._low_wet
        if low(tx - 1, ty, stage) or low(tx + 1, ty, stage) or low(tx, ty - 1, stage) or low(tx, ty + 1, stage):
            return True
        top = max(C.WATER_THRESHOLD)
        return not (low(tx - 1, ty - 1, top) or low(tx + 1, ty - 1, top)
                    or low(tx - 1, ty + 1, top) or low(tx + 1, ty + 1, top))

    def future_water(self, tx: int, ty: int) -> bool:
        """"Lago futuro": onde a água pode chegar um dia (rochas que reaparecem e plantas evitam). Com geo, é o chão
        de bacia; sem geo, a água do último estágio (Verde)."""
        if self.geo is None:
            return self.is_water(tx, ty, C.GREEN_STAGE)
        if not self.terraforms or not (0 <= tx < self.width and 0 <= ty < self.height):
            return False
        return self._rows()[1][ty][tx] and self.tiles[ty][tx] in C.FLOOR_TILES

    def near_shore(self, tx: int, ty: int) -> bool:
        """Com geo: o tile está a até C.LAKE_SHORE tiles (num quadrado) de uma bacia. Sem geo: False."""
        if self.geo is None or not (0 <= tx < self.width and 0 <= ty < self.height):
            return False
        return self._rows()[2][ty][tx]

    def plant_at(self, tx: int, ty: int) -> str | None:
        """Planta decorativa do estágio Verde (sem colisão). Retorna 'bush', 'tree', 'flower' ou None.
        Com geo (M3.3), as plantas se juntam na beira d'água: C.PLANT_CHANCE_SHORE até C.LAKE_SHORE tiles da bacia
        e C.PLANT_CHANCE_FAR longe dela. Sem geo, C.PLANT_CHANCE em todo lugar."""
        if not self.terraforms or not self.is_floor(tx, ty):
            return None
        if self.geo is not None:              # com geo, o resto não muda no jogo (bacia, veio, hash): cache por tile
            cache = self.__dict__.setdefault("_plant_cache", {})
            key = (tx, ty)
            if key not in cache:
                cache[key] = self._plant_kind(tx, ty)
            return cache[key]
        return self._plant_kind(tx, ty)

    def _plant_kind(self, tx: int, ty: int) -> str | None:
        """A parte de `plant_at` que não depende do tile ser chão agora (o render pergunta ~600×/quadro no Verde)."""
        if self.dist_from_center(tx, ty) < 7 or self.future_water(tx, ty):
            return None
        if (tx, ty) in self._vein_tiles:      # nem planta em cima de veio
            return None
        if self.geo is not None and self.geo.region_at(tx, ty) == FROST:   # nem na neve (dono, v0.5 M3.3)
            return None
        if self.geo is None:
            chance = C.PLANT_CHANCE
        else:
            chance = C.PLANT_CHANCE_SHORE if self.near_shore(tx, ty) else C.PLANT_CHANCE_FAR
        if hash01(tx, ty, self.seed + 99) >= chance:
            return None
        k = hash01(tx, ty, self.seed + 98)
        return "bush" if k < 0.4 else "tree" if k < 0.68 else "flower"
