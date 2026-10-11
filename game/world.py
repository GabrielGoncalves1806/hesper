"""Mapa do jogo: uma grade de 128×128 tiles gerada por noise com seed fixa.

Não usa pygame: é só dados + regras. Por isso dá pra testar sem abrir janela.
"""

import math

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
class World:
    def __init__(self, seed: int, width: int = C.WORLD_W, height: int = C.WORLD_H):
        self.seed = seed
        self.width = width
        self.height = height
        self.tiles = [[C.ROCK] * width for _ in range(height)]   # tiles[y][x]
        self.terminals: list[tuple[int, int]] = []               # posição (tx, ty) de cada terminal, na ordem dos logs
        self.lowness = [[0.0] * width for _ in range(height)]    # "altura" do chão: valores baixos viram poça

    # ---- geração ----------------------------------------------------------
    @classmethod
    def generate(cls, seed: int = C.WORLD_SEED) -> "World":
        world = cls(seed)
        cx, cy = C.CRATER_CENTER
        for y in range(world.height):
            for x in range(world.width):
                dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                world.tiles[y][x] = world._pick_tile(x, y, dist)
                world.lowness[y][x] = value_noise(x * 0.22 + 200, y * 0.22 + 50, seed + 21)
        world._place_terminals()
        return world

    def _pick_tile(self, x: int, y: int, dist: float) -> int:
        seed = self.seed
        # Borda do mapa: rocha indestrutível, pra ninguém cavar pra fora do mundo.
        if x == 0 or y == 0 or x == self.width - 1 or y == self.height - 1:
            return C.BEDROCK
        # Cratera: um círculo com a borda "mordida" pelo noise.
        edge = C.CRATER_RADIUS + (value_noise(x * 0.18, y * 0.18, seed) - 0.5) * 7
        if dist < C.CRATER_SAFE_RADIUS or dist < edge:
            return C.FLOOR
        # Algumas cavernas naturais longe da base, pra exploração não ser só cavar reto.
        if dist > 20 and value_noise(x * 0.13 + 70, y * 0.13 + 30, seed + 3) > 0.74:
            return C.FLOOR
        # Minério: quanto mais longe do centro, mais fácil de aparecer.
        far = min(1.0, max(0.0, (dist - C.CRATER_RADIUS) / 45))
        threshold = 0.66 - 0.11 * far
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
        cx, cy = C.CRATER_CENTER
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
        return self.get(tx, ty) in C.SOLID_TILES

    def visual_tile_at(self, px: float, py: float) -> tuple[int, int]:
        """Tile que a pessoa VÊ no pixel (px, py) do mundo.

        O topo de cada parede é desenhado 24 px acima do tile dela, cobrindo a parte de baixo
        do tile de cima. Então, se o ponto 24 px abaixo cai numa parede, é ela que está à vista.
        """
        tx, ty = int(px // C.TILE), int(py // C.TILE)
        below = int((py + C.WALL_LIFT) // C.TILE)
        if below != ty and self.is_solid(tx, below):
            return tx, below
        return tx, ty

    def is_minable(self, tx: int, ty: int) -> bool:
        return self.get(tx, ty) in C.MINE_TIME

    def dist_from_center(self, tx: int, ty: int) -> float:
        cx, cy = C.CRATER_CENTER
        return math.hypot(tx + 0.5 - cx, ty + 0.5 - cy)

    def is_water(self, tx: int, ty: int, stage: int) -> bool:
        """Poça cosmética (dá pra andar por cima). Só a partir da Névoa, em chão 'baixo', e cresce com o estágio."""
        if stage < 2 or self.get(tx, ty) != C.FLOOR or self.dist_from_center(tx, ty) < 7:
            return False
        return self.lowness[ty][tx] < C.WATER_THRESHOLD[stage]

    def plant_at(self, tx: int, ty: int) -> str | None:
        """Planta decorativa do estágio 3 (sem colisão). Retorna 'bush', 'tree', 'flower' ou None."""
        if self.get(tx, ty) != C.FLOOR or self.dist_from_center(tx, ty) < 7 or self.is_water(tx, ty, 3):
            return None
        if hash01(tx, ty, self.seed + 99) >= C.PLANT_CHANCE:
            return None
        k = hash01(tx, ty, self.seed + 98)
        return "bush" if k < 0.4 else "tree" if k < 0.68 else "flower"
