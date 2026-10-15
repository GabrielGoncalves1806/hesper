"""v0.6 Fundo M1: a caverna nova (game/cave_gen.py · bíblia §15)."""

import math
from collections import Counter

import numpy as np
import pytest

from game import cave_gen, surface_gen
from game import config as C
from game.geo import BASALT, FROST, PLATEAU, SALAR
from game.world import World

SEEDS = (7, 1, 42)


@pytest.fixture(scope="module")
def caves():
    return {s: cave_gen.generate_cave(s) for s in SEEDS}


def walls(w):
    return [(x, y) for y in range(w.height) for x in range(w.width) if w.get(x, y) in C.WALL_TILES
            and w.get(x, y) not in (C.BEDROCK, C.TERMINAL)]


def test_cave_is_256_and_the_ramp_is_under_the_crater(caves):
    for s, w in caves.items():
        assert (w.width, w.height) == (256, 256)
        assert w.crater == surface_gen.crater_of(s)
        assert w.center == (w.crater[0] + 1, w.crater[1] + 3)
        assert all(w.get(w.crater[0] + dx, w.crater[1] + dy) == C.CRATER for dx in range(3) for dy in range(3))


def test_world_generate_delegates_to_cave_gen():
    assert World.generate(7).tiles == cave_gen.generate_cave(7).tiles


def test_regions_follow_the_directions(caves):
    for w in caves.values():
        r, (cx, cy) = w.cave_region, w.center
        assert r[cy, cx] == PLATEAU
        assert r[5, 128] == FROST                  # norte
        assert r[200, 5] == BASALT                 # oeste (abaixo do gelo)
        assert r[200, 250] == SALAR                # leste
        free = [(x, y) for y in range(256) for x in range(256) if math.hypot(x + .5 - cx, y + .5 - cy) < C.CAVE_FREE_RADIUS]
        assert all(r[y, x] == PLATEAU for x, y in free)


def test_region_shares_are_about_the_plan(caves):
    for w in caves.values():
        share = Counter(w.cave_region.ravel().tolist())
        n = 256 * 256
        assert 0.24 <= share[FROST] / n <= 0.38
        assert 0.18 <= share[BASALT] / n <= 0.30
        assert 0.22 <= share[SALAR] / n <= 0.34   # o salar é o maior depois do gelo
        assert share[SALAR] > share[BASALT]


def test_region_map_is_deterministic():
    a = cave_gen.region_map(7, (112, 132), 256, 256)
    assert np.array_equal(a, cave_gen.region_map(7, (112, 132), 256, 256))
    assert not np.array_equal(a, cave_gen.region_map(8, (112, 132), 256, 256))


def test_hard_regions_have_only_hard_rock(caves):
    for w in caves.values():
        for x, y in walls(w):
            reg = int(w.cave_region[y, x])
            kind = w.get(x, y)
            if kind == C.ROCK:
                assert reg not in C.CAVE_HARD_REGIONS
            if kind == C.HARD_ROCK:
                assert reg in C.CAVE_HARD_REGIONS
            if reg in C.CAVE_HARD_REGIONS:
                assert w.is_hard(x, y)


def test_free_regions_are_not_hard(caves):
    for w in caves.values():
        for x, y in walls(w):
            if int(w.cave_region[y, x]) not in C.CAVE_HARD_REGIONS:
                assert not w.is_hard(x, y)


def test_is_hard_is_false_on_the_surface_and_on_floor():
    surf = surface_gen.generate_surface(7)
    assert surf.cave_region is None
    assert not any(surf.is_hard(x, 50) for x in range(256))


def test_magmatite_never_in_the_wall_and_copper_only_in_the_salar(caves):
    for w in caves.values():
        for x, y in walls(w):
            kind = w.get(x, y)
            assert C.ORE_TILES.get(kind) != "magmatite"
            if kind == C.COPPER:
                assert int(w.cave_region[y, x]) == SALAR
            if kind in C.ORE_TILES:
                allowed = {r for r, _ in C.CAVE_WALL_ORE[int(w.cave_region[y, x])]}
                assert C.ORE_TILES[kind] in allowed


def test_ore_share_is_low_and_mostly_wall_veins(caves):
    for w in caves.values():
        ws = walls(w)
        ore = {t for t in ws if w.get(*t) in C.ORE_TILES}
        assert 0.06 <= len(ore) / len(ws) <= 0.20        # antes ~39%
        # aglomerados de 6+ tiles do mesmo minério (4-vizinhos)
        seen, big = set(), 0
        for t in ore:
            if t in seen:
                continue
            kind, stack, comp = w.get(*t), [t], 0
            seen.add(t)
            while stack:
                x, y = stack.pop()
                comp += 1
                for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if n in ore and n not in seen and w.get(*n) == kind:
                        seen.add(n)
                        stack.append(n)
            big += comp >= C.CAVE_WALL_VEIN_SIZE[0]
        assert big >= 120


def test_every_region_has_wall_veins(caves):
    for w in caves.values():
        per_region = Counter(int(w.cave_region[y, x]) for x, y in walls(w) if w.get(x, y) in C.ORE_TILES)
        for reg in (PLATEAU, SALAR, BASALT, FROST):
            assert per_region[reg] >= 30


def test_start_has_enough_ore_near_the_ramp(caves):
    for w in caves.values():
        near = Counter(C.ORE_TILES[w.get(x, y)] for x, y in walls(w)
                       if w.get(x, y) in C.ORE_TILES and w.dist_from_center(x, y) <= 30)
        assert near["iron"] >= 18 and near["silicon"] >= 18 and near["ice"] >= 12


def test_floor_veins_per_region(caves):
    for w in caves.values():
        reach = w.reachable_from(w.center)
        near = [v for v in w.veins if w.dist_from_center(*v.center) <= C.CAVE_VEINS_NEAR_RANGE[1] + 1]
        for res in C.CAVE_VEINS_NEAR:
            assert any(v.resource == res and all(t in reach for t in v.tiles) for v in near)
        for v in w.veins:
            reg = int(w.cave_region[v.ty, v.tx])
            assert v.resource in C.CAVE_VEINS[reg]
        got = Counter(v.resource for v in w.veins)
        assert got["copper"] >= 3 and got["magmatite"] >= 4 and got["ice"] >= 4


def test_magmatite_rocks_only_on_basalt_floor(caves):
    for w in caves.values():
        rocks = [(x, y) for y in range(256) for x in range(256) if w.get(x, y) == C.SMALL_MAGMATITE]
        assert len(rocks) >= 20
        assert all(int(w.cave_region[y, x]) == BASALT for x, y in rocks)
        assert not any(w.get(x, y) in (C.SMALL_IRON, C.SMALL_SILICON, C.SMALL_ICE)
                       for y in range(256) for x in range(256))


def test_terminals_are_in_the_free_area(caves):
    for w in caves.values():
        assert len(w.terminals) == 3
        for tx, ty in w.terminals:
            assert int(w.cave_region[ty, tx]) not in C.CAVE_HARD_REGIONS
            assert all(w.get(tx + dx, ty + dy) == C.FLOOR for dx in (-1, 0, 1) for dy in (1, 2))


def test_cave_never_terraforms_and_has_no_geo(caves):
    for w in caves.values():
        assert w.terraforms is False and w.geo is None
