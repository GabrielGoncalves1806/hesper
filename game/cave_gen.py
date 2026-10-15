"""Gerador da CAVERNA (v0.6 Fundo M1 · bíblia §15). Antes morava no World.generate (128×128).

256×256, igual à superfície. A rampa de subida fica no mesmo canto da cratera da superfície (surface_gen.crater_of).
Regiões pela direção, sem copiar a geometria de cima (decisão do dono): gelo ao norte, basalto a oeste, salar a leste
(maior), centro em volta da chegada. Gelo e basalto têm rocha dura (só a broca nv.2 quebra; ver World.is_hard).

Ordem: regiões → tiles (borda, salão, cavernas naturais, minério solto raro, rocha/rocha dura) → rampa → terminais →
veios de parede (aglomerados de 6–8) → começo garantido perto da rampa → veios 2×2 por região → rochinhas de
magmatita no chão do basalto. Tudo determinístico pela seed.
"""

from __future__ import annotations

import math
import random

import numpy as np

from game import config as C
from game import surface_gen
from game.geo import BASALT, FROST, PLATEAU, SALAR, fbm
from game.world import Vein, World, hash01, value_noise


def region_map(seed: int, center: tuple[int, int], w: int, h: int) -> np.ndarray:
    """Região de cada tile, (h, w) uint8. As fronteiras saem do meio do mapa; `center` (a chegada da rampa) só marca o
    raio livre. O gelo pega a faixa de cima inteira (por cima do basalto e do salar)."""
    mx, my = w // 2, h // 2
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    s = (seed & 0xFFFF) * 16 + 500

    def warp(k: int) -> np.ndarray:
        return C.CAVE_REGION_WARP * 2 * (fbm(xs, ys, 18, s + k, 3) - 0.5)

    region = np.full((h, w), PLATEAU, np.uint8)
    region[xs - mx > C.CAVE_SALAR_EDGE + warp(1)] = SALAR
    region[mx - xs > C.CAVE_BASALT_EDGE + warp(2)] = BASALT
    region[my - ys > C.CAVE_FROST_EDGE + warp(3)] = FROST
    cx, cy = center
    region[np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) < C.CAVE_FREE_RADIUS] = PLATEAU
    return region


def pick_ore(region: int, u: float) -> int:
    """Tile de minério da região pra um sorteio u em [0, 1) (pesos de C.CAVE_WALL_ORE)."""
    table = C.CAVE_WALL_ORE[region]
    total = sum(p for _, p in table)
    acc = 0.0
    for resource, p in table:
        acc += p / total
        if u < acc:
            return _ORE_TILE[resource]
    return _ORE_TILE[table[-1][0]]


_ORE_TILE = {name: kind for kind, name in C.ORE_TILES.items()}


def _rock(region: int) -> int:
    return C.HARD_ROCK if region in C.CAVE_HARD_REGIONS else C.ROCK


def _pick_tile(world: World, x: int, y: int, dist: float, region: int) -> int:
    seed = world.seed
    if x == 0 or y == 0 or x == world.width - 1 or y == world.height - 1:
        return C.BEDROCK                                    # borda: ninguém cava pra fora do mundo
    edge = C.CAVE_HALL_RADIUS + (value_noise(x * 0.18, y * 0.18, seed) - 0.5) * 7
    if dist < C.CAVE_SAFE_RADIUS or dist < edge:
        return C.FLOOR                                      # salão em volta da rampa
    if dist > 20 and value_noise(x * 0.13 + 70, y * 0.13 + 30, seed + 3) > 0.74:
        return C.FLOOR                                      # cavernas naturais (às vezes cruzam a fronteira: tudo bem)
    if value_noise(x * 0.5 + 40, y * 0.5 + 9, seed + 7) > C.CAVE_LOOSE_ORE_THRESHOLD:
        return pick_ore(region, hash01(x, y, seed + 13))    # minério solto, raro
    return _rock(region)


def generate_cave(seed: int) -> World:
    world = World(seed, C.CAVE_W, C.CAVE_H)
    rx, ry = surface_gen.crater_of(seed)
    world.crater = (rx, ry)
    world.center = (rx + 1, ry + 3)
    world.terraforms = False                                # rocha fria: não muda com o Ti (bíblia §9)
    world.cave_region = region_map(seed, world.center, world.width, world.height)
    cx, cy = world.center
    regions = world.cave_region.tolist()
    for y in range(world.height):
        for x in range(world.width):
            dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            world.tiles[y][x] = _pick_tile(world, x, y, dist, regions[y][x])
            world.lowness[y][x] = value_noise(x * 0.22 + 200, y * 0.22 + 50, seed + 21)
    for dy in range(3):
        for dx in range(3):
            world.set(rx + dx, ry + dy, C.CRATER)
    _place_terminals(world)
    rng = random.Random(seed * 7919 + 29)
    _place_wall_veins(world, rng)
    _place_near_wall_veins(world, rng)
    _place_veins(world, rng)
    _place_magmatite_rocks(world)
    return world


def _place_terminals(world: World) -> None:
    """Enterra cada terminal numa parede, com uma salinha de chão embaixo dele (área livre: rocha normal)."""
    cx, cy = world.center
    for dist, angle in C.TERMINAL_SPOTS:
        tx = int(round(cx + dist * math.cos(math.radians(angle))))
        ty = int(round(cy + dist * math.sin(math.radians(angle))))
        for dy in (-1, 0):
            for dx in (-1, 0, 1):
                world.set(tx + dx, ty + dy, C.ROCK)
        world.set(tx, ty, C.TERMINAL)
        for dy in (1, 2):
            for dx in (-1, 0, 1):
                world.set(tx + dx, ty + dy, C.FLOOR)
        world.terminals.append((tx, ty))


def _blocked(world: World) -> set[tuple[int, int]]:
    """Rampa + chegada e terminais + salinha, com folga: nada de veio por cima."""
    rx, ry = world.crater
    out = {(rx + dx, ry + dy) for dx in range(-2, 5) for dy in range(-2, 6)}
    for tx, ty in world.terminals:
        out |= {(tx + dx, ty + dy) for dx in range(-2, 3) for dy in range(-2, 4)}
    return out


def _grow(world: World, rng: random.Random, start: tuple[int, int], size: int, ore: int,
          blocked: set[tuple[int, int]]) -> int:
    """Aglomerado de `size` tiles de `ore` crescendo a partir de `start`, só por rocha (normal ou dura). Devolve
    quantos tiles virou."""
    home = int(world.cave_region[start[1], start[0]])    # o veio não cruza a fronteira (o minério é da região)

    def region_of(t):
        return int(world.cave_region[t[1], t[0]])

    cells, frontier = [start], [start]
    taken = {start}
    while frontier and len(cells) < size:
        x, y = frontier.pop(rng.randrange(len(frontier)))
        for n in rng.sample([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)], 4):
            if len(cells) >= size:
                break
            if n in taken or n in blocked or world.get(*n) not in (C.ROCK, C.HARD_ROCK) or region_of(n) != home:
                continue
            taken.add(n)
            cells.append(n)
            frontier.append(n)
        if len(cells) < size and any(world.get(*m) in (C.ROCK, C.HARD_ROCK) and m not in taken and region_of(m) == home
                                     for m in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
            frontier.append((x, y))                         # ainda tem vizinho de rocha livre: continua na fronteira
    for t in cells:
        world.set(*t, ore)
    return len(cells)


def _place_wall_veins(world: World, rng: random.Random) -> None:
    """Veios de parede pelo mapa todo: 6–8 tiles do mesmo minério (o da região da semente)."""
    blocked = _blocked(world)
    seeds: list[tuple[int, int]] = []
    lo, hi = C.CAVE_WALL_VEIN_SIZE
    for _ in range(C.CAVE_WALL_VEIN_TRIES):
        x, y = rng.randrange(2, world.width - 2), rng.randrange(2, world.height - 2)
        if world.get(x, y) not in (C.ROCK, C.HARD_ROCK) or (x, y) in blocked:
            continue
        if any(abs(x - sx) + abs(y - sy) < C.CAVE_WALL_VEIN_SPACING for sx, sy in seeds):
            continue
        seeds.append((x, y))
        ore = pick_ore(int(world.cave_region[y, x]), rng.random())
        _grow(world, rng, (x, y), rng.randint(lo, hi), ore, blocked)


def _place_near_wall_veins(world: World, rng: random.Random) -> None:
    """Começo garantido: veios de parede de ferro, silício e gelo na borda de um túnel/salão perto da rampa."""
    blocked = _blocked(world)
    lo, hi = C.CAVE_NEAR_RANGE
    lo_s, hi_s = C.CAVE_WALL_VEIN_SIZE
    edge = [(x, y) for y in range(1, world.height - 1) for x in range(1, world.width - 1)
            if world.get(x, y) == C.ROCK and lo <= world.dist_from_center(x, y) <= hi and (x, y) not in blocked
            and any(world.get(*n) == C.FLOOR for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))]
    rng.shuffle(edge)
    for resource, count in C.CAVE_NEAR_WALL_VEINS.items():
        ore = _ORE_TILE[resource]
        for _ in range(count):
            while edge and world.get(*edge[-1]) != C.ROCK:
                edge.pop()
            if not edge:
                return
            _grow(world, rng, edge.pop(), rng.randint(lo_s, hi_s), ore, blocked)


def _place_veins(world: World, rng: random.Random) -> None:
    """Veios 2×2 (drill): 1 de ferro e 1 de silício perto (chão aberto, alcançável a pé) e CAVE_VEINS_PER_REGION por
    região longe, com os recursos da região (C.CAVE_VEINS). Longe e sem chão: cava um bolsão 4×4 em volta."""
    blocked = _blocked(world)

    def block_ok(tx, ty, spacing):
        if not (3 <= tx <= world.width - 5 and 3 <= ty <= world.height - 5):
            return False
        if any((tx + dx, ty + dy) in blocked for dx in range(-1, 3) for dy in range(-1, 3)):
            return False
        return all(math.hypot(tx - v.tx, ty - v.ty) >= spacing for v in world.veins)

    def open_floor(tx, ty):
        return all(world.get(tx + dx, ty + dy) == C.FLOOR for dx in (0, 1) for dy in (0, 1, 2))

    def region_of(tx, ty):
        return int(world.cave_region[ty, tx])

    reach = world.reachable_from(world.center)
    lo, hi = C.CAVE_VEINS_NEAR_RANGE
    for resource in C.CAVE_VEINS_NEAR:
        candidates = [(tx, ty) for ty in range(world.height - 1) for tx in range(world.width - 1)
                      if lo <= world.dist_from_center(tx + 1, ty + 1) <= hi and block_ok(tx, ty, 8)
                      and open_floor(tx, ty) and all(t in reach for t in Vein(resource, tx, ty).tiles)]
        if candidates:
            world._add_vein(Vein(resource, *rng.choice(candidates)))

    for region, resources in C.CAVE_VEINS.items():
        placed = 0
        for _ in range(3000):
            if placed >= C.CAVE_VEINS_PER_REGION:
                break
            tx, ty = rng.randrange(3, world.width - 5), rng.randrange(3, world.height - 5)
            if region_of(tx, ty) != region or region_of(tx + 1, ty + 1) != region:
                continue
            if world.dist_from_center(tx + 1, ty + 1) < C.CAVE_VEINS_MIN_DIST or not block_ok(tx, ty, 10):
                continue
            if any(world.get(tx + dx, ty + dy) == C.TERMINAL for dx in range(-1, 3) for dy in range(-1, 3)):
                continue
            if not open_floor(tx, ty):
                for dy in range(-1, 3):
                    for dx in range(-1, 3):
                        world.set(tx + dx, ty + dy, C.FLOOR)
            world._add_vein(Vein(resources[placed % len(resources)], tx, ty))
            placed += 1


def _place_magmatite_rocks(world: World) -> None:
    """Rochinhas de magmatita no chão do basalto (não reaparecem: o magmatite.py é das fumarolas da superfície)."""
    for y in range(1, world.height - 2):
        for x in range(1, world.width - 1):
            if world.get(x, y) != C.FLOOR or world.get(x, y + 1) != C.FLOOR:
                continue
            if int(world.cave_region[y, x]) != BASALT or world.vein_at(x, y) is not None:
                continue
            if any(world.vein_at(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                continue
            if hash01(x, y, world.seed + 77) < C.CAVE_MAGMATITE_ROCK_CHANCE:
                world.set(x, y, C.SMALL_MAGMATITE)
