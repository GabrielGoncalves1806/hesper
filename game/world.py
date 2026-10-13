"""Mapa de uma camada: uma grade de tiles gerada por noise com seed fixa.

`World` é o mapa em si (consultas e regras de tile). `World.generate(seed)` gera a CAVERNA
(128×128, paredes com minério, terminais, rampa de subida 3×3 no meio do salão), que era o mapa inteiro
até o v0.2. A caverna não terraforma (`terraforms = False`: sem água nem plantas). A SUPERFÍCIE (deserto 192×192, onde fica a base) é montada pelo game/surface_gen.py
em cima do mesmo `World`.

Paredes altas (rocha, minério, borda, terminal) × sólidos baixos (rocha pequena, cratera, destroço, formação): os dois
bloqueiam o player, mas só a parede alta tem topo elevado e face (ver render.py).

Não usa pygame: é só dados + regras. Por isso dá pra testar sem abrir janela.
"""

import math
import random
from collections import deque
from dataclasses import dataclass

import numpy as np

from game import config as C


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
        self.center: tuple[int, int] = C.CAVE_CENTER              # "centro" da camada (base ou rampa), em tiles
        self.floor_kind = C.FLOOR                                 # o chão que fica quando um sólido quebra
        # Rampa 3×3 da camada (tiles CRATER): a cratera de descida na superfície, a rampa de subida na caverna.
        # Canto de cima à esquerda; as regras de uso ficam em game/layers.py (ramp_target, ramp_arrival).
        self.crater: tuple[int, int] | None = None
        self.terraforms = True                                    # False na caverna: sem água nem plantas, nunca
        self.sand_variants: list[bytes] | None = None             # variação do sand_{stage}_{v} por tile (superfície)
        self.wrecks: list = []                                    # destroços (game/wrecks.py), só na superfície
        self._wreck_index: dict | None = None                     # tile (área ou caixa) -> destroço (lazy)
        # v0.4 Marco 2 (só na superfície): a geografia da seed (game/geo.py · Geo, só leitura) e os tiles onde nada
        # nasce (halo das formações, bolsões e avental dos gelos-portão): veio, destroço, rocha pequena e a rocha que
        # reaparece respeitam (os afloramentos das formações são os únicos que ficam no halo)
        self.geo = None
        self.keep_clear: frozenset[tuple[int, int]] = frozenset()
        # v0.4 Marco 3 (M3.3, só com geo): até que altura (escala do geo.height) a água das bacias subiu. Derivado do
        # índice de água (game/thaw.py · lake_level, GameState._apply_thaw), não vai no save. -1 = seco.
        self.water_level = -1.0
        self._geo_rows = None                                     # (altura, bacia, beira) em listas (ver _rows)

    # ---- geração ----------------------------------------------------------
    @classmethod
    def generate(cls, seed: int = C.WORLD_SEED) -> "World":
        world = cls(seed)
        cx, cy = C.CAVE_CENTER
        for y in range(world.height):
            for x in range(world.width):
                dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                world.tiles[y][x] = world._pick_tile(x, y, dist)
                world.lowness[y][x] = value_noise(x * 0.22 + 200, y * 0.22 + 50, seed + 21)
        world.terraforms = False                              # rocha fria: não muda com o Ti (bíblia §9)
        world.crater = C.CAVE_RAMP                           # rampa de subida no meio do salão
        rx, ry = C.CAVE_RAMP
        for dy in range(3):
            for dx in range(3):
                world.set(rx + dx, ry + dy, C.CRATER)
        world._place_terminals()
        world._place_veins()
        return world

    def _pick_tile(self, x: int, y: int, dist: float) -> int:
        seed = self.seed
        # Borda do mapa: rocha indestrutível, pra ninguém cavar pra fora do mundo.
        if x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1:
            return C.BEDROCK
        # Cratera: um círculo com a borda "mordida" pelo noise.
        edge = C.CAVE_HALL_RADIUS + (value_noise(x * 0.18, y * 0.18, seed) - 0.5) * 7
        if dist < C.CAVE_SAFE_RADIUS or dist < edge:
            return C.FLOOR
        # Algumas cavernas naturais longe da base, pra exploração não ser só cavar reto.
        if dist > 20 and value_noise(x * 0.13 + 70, y * 0.13 + 30, seed + 3) > 0.74:
            return C.FLOOR
        # Minério: quanto mais longe do centro, mais fácil de aparecer.
        far = min(1.0, max(0.0, (dist - C.CAVE_HALL_RADIUS) / 45))
        base, extra = C.CAVE_ORE_THRESHOLD
        threshold = base - extra * far
        if value_noise(x * 0.5 + 40, y * 0.5 + 9, seed + 7) > threshold:
            kind = value_noise(x * 0.15 + 90, y * 0.15 + 3, seed + 13)
            if kind < 0.47:
                return C.IRON
            if kind < 0.62:
                return C.SILICON
            return C.ICE
        return C.ROCK

    def _place_terminals(self) -> None:
        """Enterra cada terminal numa parede, com uma salinha de chão embaixo dele."""
        cx, cy = C.CAVE_CENTER
        for dist, angle in C.TERMINAL_SPOTS:
            tx = int(round(cx + dist * math.cos(math.radians(angle))))
            ty = int(round(cy + dist * math.sin(math.radians(angle))))
            # moldura de rocha em volta do terminal (fica "dentro" da parede)
            for dy in (-1, 0):
                for dx in (-1, 0, 1):
                    self.set(tx + dx, ty + dy, C.ROCK)
            self.set(tx, ty, C.TERMINAL)
            # salinha 3×2 na frente (embaixo) do terminal
            for dy in (1, 2):
                for dx in (-1, 0, 1):
                    self.set(tx + dx, ty + dy, C.FLOOR)
            self.terminals.append((tx, ty))

    def _place_veins(self) -> None:
        """Veios 2×2: 1 de cada tipo perto da base (chão aberto e alcançável) e mais alguns longe,
        uns em caverna aberta e outros enterrados num bolsão escavado na rocha (achados cavando)."""
        rng = random.Random(self.seed * 7919 + 13)
        cx, cy = C.CAVE_CENTER
        rx, ry = C.CAVE_RAMP                                # a rampa de subida + 2 tiles de folga (e a chegada)
        blocked = {(rx + dx, ry + dy) for dx in range(-2, 5) for dy in range(-2, 6)}
        for tx, ty in self.terminals:                       # terminal + salinha + folga
            blocked |= {(tx + dx, ty + dy) for dx in range(-2, 3) for dy in range(-2, 4)}

        def block_ok(tx, ty, spacing):
            if not (3 <= tx <= self.width - 5 and 3 <= ty <= self.height - 5):     # longe da borda
                return False
            area = [(tx + dx, ty + dy) for dx in range(-1, 3) for dy in range(-1, 3)]   # 2×2 + 1 de folga
            if any(t in blocked for t in area):
                return False
            return all(math.hypot(tx - v.tx, ty - v.ty) >= spacing for v in self.veins)

        def center_dist(tx, ty):
            return math.hypot(tx + 1 - cx, ty + 1 - cy)

        def open_floor(tx, ty):
            """Os 2×2 são chão E a linha logo abaixo também (senão o topo elevado da parede
            de baixo cobriria o veio)."""
            return all(self.get(tx + dx, ty + dy) == C.FLOOR for dx in (0, 1) for dy in (0, 1, 2))

        # perto da base: chão aberto, alcançável a pé a partir da cratera
        reach = self.reachable_from(C.CAVE_CENTER)
        lo, hi = C.VEINS_NEAR_BASE
        for resource in C.RESOURCES:
            candidates = [(tx, ty) for ty in range(self.height - 1) for tx in range(self.width - 1)
                          if lo <= center_dist(tx, ty) <= hi and block_ok(tx, ty, spacing=8)
                          and open_floor(tx, ty)
                          and all((x, y) in reach for x, y in Vein(resource, tx, ty).tiles)]
            if candidates:
                self._add_vein(Vein(resource, *rng.choice(candidates)))

        # longe: mais veios, alternando caverna aberta e bolsão escavado na rocha
        lo, hi = C.VEINS_FAR_RANGE
        for resource in C.RESOURCES:
            placed = 0
            for _ in range(400):
                if placed >= C.VEINS_FAR_PER_TYPE:
                    break
                angle, dist = rng.uniform(0, math.tau), rng.uniform(lo, hi)
                tx, ty = int(cx + dist * math.cos(angle)) - 1, int(cy + dist * math.sin(angle)) - 1
                if not block_ok(tx, ty, spacing=6):
                    continue
                vein = Vein(resource, tx, ty)
                if not open_floor(tx, ty):
                    for dy in range(-1, 3):                  # bolsão de chão 4×4 em volta do veio (inclui a linha de baixo)
                        for dx in range(-1, 3):
                            self.set(tx + dx, ty + dy, C.FLOOR)
                self._add_vein(vein)
                placed += 1

    def _add_vein(self, vein: Vein) -> None:
        self.veins.append(vein)
        for t in vein.tiles:
            self.set(*t, C.FLOOR)
            self._vein_tiles[t] = vein

    def reachable_from(self, start: tuple[int, int]) -> set[tuple[int, int]]:
        """Tiles de chão alcançáveis a pé a partir de `start` (sem cavar). Busca em largura."""
        seen = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in seen and self.in_bounds(nx, ny) and not self.is_solid(nx, ny):
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
        if not self.terraforms or not self.is_floor(tx, ty) or self.dist_from_center(tx, ty) < 7 \
                or self.future_water(tx, ty):
            return None
        if (tx, ty) in self._vein_tiles:      # nem planta em cima de veio
            return None
        if self.geo is None:
            chance = C.PLANT_CHANCE
        else:
            chance = C.PLANT_CHANCE_SHORE if self.near_shore(tx, ty) else C.PLANT_CHANCE_FAR
        if hash01(tx, ty, self.seed + 99) >= chance:
            return None
        k = hash01(tx, ty, self.seed + 98)
        return "bush" if k < 0.4 else "tree" if k < 0.68 else "flower"
