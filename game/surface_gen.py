"""Gerador do deserto: a SUPERFÍCIE do v0.3 (bíblia §9, Marco 1).

Monta um `World` de 192×192 com a mesma interface do mapa antigo, então todo o resto do jogo
(colisão, mineração, render, transição de estágio, água e plantas) funciona igual. Ordem:

    areia + "altura" (lowness, pras poças)  →  borda (cordilheira, 2–3 tiles)  →  morros
    →  limpa a área da cápsula  →  cratera 3×3  →  veios (3 a 5, longe)  →  destroços (6 a 8, game/wrecks.py)
    →  rochas pequenas

Tudo sai da seed: mesma seed, mesmo deserto. A geração custa ~0,3 s, então o mapa virgem de cada
seed fica num cache e `generate_surface` devolve uma CÓPIA (o jogador mexe na cópia).

Python puro (sem pygame), testado em tests/test_surface_gen.py.
"""

import math
import random

from game import config as C
from game import wrecks as wreck_gen
from game.world import Vein, World, hash01, value_noise

_cache: dict[int, World] = {}


def generate_surface(seed: int = C.WORLD_SEED) -> World:
    """Deserto da seed `seed`: uma cópia nova (pode mexer à vontade)."""
    if seed not in _cache:
        _cache[seed] = _build(seed)
    return _copy(_cache[seed])


def pristine_tiles(seed: int) -> list[list[int]]:
    """Os tiles do deserto recém-gerado (só leitura: é o que o save usa pra saber o que mudou)."""
    if seed not in _cache:
        _cache[seed] = _build(seed)
    return _cache[seed].tiles


# ---------------------------------------------------------------------------
# Variação da areia (sand_{stage}_{v}): lógica da Designer (tools/sprites/build_sprites.py · sand_variant),
# copiada aqui igual, com o mesmo hash e ruído, pra o jogo bater com as prévias aprovadas.
# 0 areia lisa (~72% fora das zonas) · 1 cascalho (~20%) · 2 dunas (faixas largas) · 3 laje (rara)
# ---------------------------------------------------------------------------
SAND_SEED = 5


def _hsh(x: int, y: int, s: int) -> float:
    n = (x * 374761393 + y * 668265263 + s * 2246822519 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 15
    return n / 4294967296.0


def _vnoise(x: float, y: float, s: int) -> float:
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hsh(ix, iy, s), _hsh(ix + 1, iy, s)
    c, d = _hsh(ix, iy + 1, s), _hsh(ix + 1, iy + 1, s)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


def sand_variant(x: int, y: int, seed: int = SAND_SEED) -> int:
    dune = _vnoise(x * 0.11 + 3.1, y * 0.23 + 1.7, seed)        # faixas mais largas que altas = vento
    rock = _vnoise(x * 0.17 + 40.3, y * 0.17 + 9.2, seed + 1)
    r = _hsh(x, y, seed + 2)
    if dune > 0.6 and r < 0.55:
        return 2
    if rock > 0.66 and r < 0.12:
        return 3
    return 0 if r < 0.72 else 1 if r < 0.92 else 2 if r < 0.965 else 3


def _copy(src: World) -> World:
    world = World(src.seed, src.width, src.height)
    world.tiles = [row[:] for row in src.tiles]
    world.lowness = src.lowness                 # só leitura: dá pra dividir
    world.veins = list(src.veins)
    world._vein_tiles = dict(src._vein_tiles)
    world.center, world.floor_kind, world.crater = src.center, src.floor_kind, src.crater
    world.terminals = list(src.terminals)
    world.sand_variants = src.sand_variants     # só leitura
    world.wrecks = list(src.wrecks)             # destroços: geometria fixa (o conteúdo das caixas fica na camada)
    return world


# ---------------------------------------------------------------------------
def _build(seed: int) -> World:
    world = World(seed, C.SURFACE_W, C.SURFACE_H)
    world.center = C.BASE_TILE
    world.floor_kind = C.SAND
    rng = random.Random(seed * 7919 + 101)
    W, H = world.width, world.height
    for y in range(H):
        for x in range(W):
            world.tiles[y][x] = C.SAND
            world.lowness[y][x] = value_noise(x * 0.22 + 200, y * 0.22 + 50, seed + 21)
    _border(world)
    _hills(world, rng)
    for y in range(H):                           # a área da cápsula fica sempre limpa
        for x in range(W):
            if world.dist_from_center(x, y) < C.SURFACE_CLEAR_RADIUS:
                world.tiles[y][x] = C.SAND
    _crater(world, rng)
    _veins(world, rng)
    wreck_gen.place_wrecks(world, rng)           # Marco 3: destroços (antes das rochas pequenas, com folga livre)
    _small_rocks(world)
    world.sand_variants = [bytes(sand_variant(x, y) for x in range(W)) for y in range(H)]
    return world


def _border(world: World) -> None:
    """Cordilheira intransponível: 2 tiles sempre, 3 onde o noise mandar (borda irregular)."""
    lo, hi = C.SURFACE_BORDER
    W, H = world.width, world.height
    for y in range(H):
        for x in range(W):
            edge = min(x, y, W - 1 - x, H - 1 - y)
            thick = hi if value_noise(x * 0.17, y * 0.17, world.seed + 31) > 0.5 else lo
            if edge < thick:
                world.tiles[y][x] = C.BEDROCK


def _hills(world: World, rng: random.Random) -> None:
    """Morros: blobs de rocha de 3 a 8 tiles, com um pouco de minério. Não encostam um no outro."""
    lo, hi = C.HILLS
    target = rng.randint(lo, hi)
    placed, tries = 0, 0
    cx0, cy0 = world.center
    taken: set[tuple[int, int]] = set()
    while placed < target and tries < 2000:
        tries += 1
        size = rng.randint(*C.HILL_SIZE)
        x0 = rng.randint(5, world.width - 6 - size)
        y0 = rng.randint(5, world.height - 6 - size)
        mid = (x0 + size / 2, y0 + size / 2)
        if math.hypot(mid[0] - cx0, mid[1] - cy0) < C.SURFACE_CLEAR_RADIUS + size:
            continue
        r = size / 2
        blob = []
        for y in range(y0, y0 + size):
            for x in range(x0, x0 + size):
                wob = (value_noise(x * 0.6, y * 0.6, world.seed + 41) - 0.5) * 1.2
                if math.hypot(x + 0.5 - mid[0], y + 0.5 - mid[1]) < r + wob:
                    blob.append((x, y))
        if len(blob) < 3:
            continue
        # folga de 2 tiles entre morros (senão viram um paredão maior que 8)
        halo = {(x + dx, y + dy) for x, y in blob for dx in range(-2, 3) for dy in range(-2, 3)}
        if halo & taken:
            continue
        for x, y in blob:
            kind = C.ROCK
            if rng.random() < C.HILL_ORE_CHANCE:
                kind = _weighted(rng.random(), {C.IRON: 0.45, C.SILICON: 0.3, C.ICE: 0.25})
            world.tiles[y][x] = kind
        taken |= set(blob)
        placed += 1


def _crater(world: World, rng: random.Random) -> None:
    """Cratera 3×3 a 15–20 tiles da base, com uma folga de areia em volta.

    Ponto de extensão (Marco 2): `world.crater` guarda o canto de cima à esquerda; a rampa de descida
    vai ser desenhada aqui (crater_ramp.png) e o E nesse ponto troca de camada."""
    cx, cy = world.center
    lo, hi = C.SURFACE_CRATER_DIST
    for _ in range(500):
        angle, dist = rng.uniform(0, math.tau), rng.uniform(lo + 0.5, hi - 0.5)
        mx, my = int(cx + dist * math.cos(angle)), int(cy + dist * math.sin(angle))
        if lo <= world.dist_from_center(mx, my) <= hi:
            break
    tx, ty = mx - 1, my - 1
    for y in range(ty - 2, ty + 5):              # areia limpa em volta (dá pra chegar de todo lado)
        for x in range(tx - 2, tx + 5):
            world.set(x, y, C.SAND)
    for dy in range(3):
        for dx in range(3):
            world.set(tx + dx, ty + dy, C.CRATER)
    world.crater = (tx, ty)


def _veins(world: World, rng: random.Random) -> None:
    """3 a 5 veios 2×2, longe da base, em areia aberta, um de cada recurso primeiro."""
    lo, hi = C.SURFACE_VEINS
    count = rng.randint(lo, hi)
    resources = list(C.RESOURCES)
    rng.shuffle(resources)
    resources += [rng.choice(C.RESOURCES) for _ in range(count - len(resources))]
    cx, cy = world.center
    max_dist = min(world.width, world.height) / 2 - 8
    crater = world.crater

    def ok(tx, ty):
        area = [(tx + dx, ty + dy) for dx in range(-1, 3) for dy in range(-1, 4)]   # 2×2 + linha de baixo + folga
        if not all(world.get(*t) == C.SAND for t in area):
            return False
        if any(world.dist_from_center(tx + dx, ty + dy) < C.SURFACE_VEIN_MIN_DIST for dx in (0, 1) for dy in (0, 1)):
            return False
        if crater and math.hypot(tx - crater[0], ty - crater[1]) < 8:
            return False
        return all(math.hypot(tx - v.tx, ty - v.ty) >= C.SURFACE_VEIN_SPACING for v in world.veins)

    for resource in resources:
        for _ in range(3000):
            angle = rng.uniform(0, math.tau)
            dist = rng.uniform(C.SURFACE_VEIN_MIN_DIST + 2, max_dist)
            tx, ty = int(cx + dist * math.cos(angle)) - 1, int(cy + dist * math.sin(angle)) - 1
            if ok(tx, ty):
                world.veins.append(Vein(resource, tx, ty))
                for t in world.veins[-1].tiles:
                    world._vein_tiles[t] = world.veins[-1]
                break


def _small_rocks(world: World) -> None:
    """Rochas pequenas espalhadas pela areia (por hash, sem formar padrão)."""
    keep_free = set(world._vein_tiles) | wreck_gen.keep_free(world.wrecks)
    for v in world.veins:                         # a linha de baixo do veio fica livre (o player para ali)
        keep_free |= {(v.tx + dx, v.ty + 2) for dx in (0, 1)}
    kinds = {C.SMALL_IRON: C.SMALL_ROCK_WEIGHTS["iron"], C.SMALL_SILICON: C.SMALL_ROCK_WEIGHTS["silicon"],
             C.SMALL_ICE: C.SMALL_ROCK_WEIGHTS["ice"]}
    for y in range(world.height):
        for x in range(world.width):
            if world.tiles[y][x] != C.SAND or (x, y) in keep_free:
                continue
            if world.dist_from_center(x, y) < C.SMALL_ROCK_MIN_DIST:
                continue
            if hash01(x, y, world.seed + 61) < C.SMALL_ROCK_CHANCE:
                world.tiles[y][x] = _weighted(hash01(x, y, world.seed + 62), kinds)


def _weighted(r: float, weights: dict):
    acc = 0.0
    total = sum(weights.values())
    for key, w in weights.items():
        acc += w / total
        if r < acc:
            return key
    return key
