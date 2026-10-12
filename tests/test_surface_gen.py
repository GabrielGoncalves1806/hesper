"""Gerador do deserto (superfície, v0.3 Marco 1)."""

from game import config as C
from game.surface_gen import generate_surface

W = generate_surface(C.WORLD_SEED)
ALL = [(x, y) for y in range(C.SURFACE_H) for x in range(C.SURFACE_W)]


def test_size_seed_and_copy():
    assert (W.width, W.height) == (192, 192) and W.floor_kind == C.SAND
    assert W.center == C.BASE_TILE
    assert generate_surface(C.WORLD_SEED).tiles == W.tiles
    assert generate_surface(C.WORLD_SEED + 1).tiles != W.tiles
    other = generate_surface(C.WORLD_SEED)
    before = W.get(50, 50)
    other.set(50, 50, C.ROCK if before != C.ROCK else C.SAND)
    assert generate_surface(C.WORLD_SEED).get(50, 50) == before      # cada chamada é uma cópia


def test_border_is_bedrock_2_to_3_thick():
    for i in range(192):
        for x, y in ((i, 0), (i, 1), (0, i), (1, i), (i, 191), (i, 190), (191, i), (190, i)):
            assert W.get(x, y) == C.BEDROCK
    assert not W.is_minable(0, 50)
    assert all(W.get(x, y) != C.BEDROCK for y in range(3, 189) for x in range(3, 189))
    thick3 = sum(W.get(2, y) == C.BEDROCK for y in range(3, 189))
    assert 0 < thick3 < 186                                     # a espessura varia (2 ou 3)


def test_base_area_is_clear_sand():
    for x, y in ALL:
        if W.dist_from_center(x, y) < C.SURFACE_CLEAR_RADIUS:
            assert W.get(x, y) == C.SAND, (x, y)


def test_crater_3x3_between_15_and_20_tiles():
    tx, ty = W.crater
    assert all(W.get(tx + dx, ty + dy) == C.CRATER for dx in range(3) for dy in range(3))
    assert sum(W.get(x, y) == C.CRATER for x, y in ALL) == 9
    assert 15 <= W.dist_from_center(tx + 1, ty + 1) <= 20
    assert not W.is_minable(tx, ty) and W.is_solid(tx, ty) and not W.is_wall(tx, ty)


def test_three_to_five_veins_far_and_apart():
    lo, hi = C.SURFACE_VEINS
    for seed in (1, 2, 3, C.WORLD_SEED):
        w = generate_surface(seed)
        assert lo <= len(w.veins) <= hi
        assert {v.resource for v in w.veins} == set(C.RESOURCES)
        seen = set()
        for v in w.veins:
            assert all(w.dist_from_center(*t) >= C.SURFACE_VEIN_MIN_DIST for t in v.tiles)
            assert not set(v.tiles) & seen
            assert all(w.get(x, y) == C.SAND for x, y in v.tiles)
            assert all(w.get(x, v.ty + 2) == C.SAND for x in (v.tx, v.tx + 1))   # sem topo de parede cobrindo
            seen |= set(v.tiles)


def test_hills_small_rocks_and_reachability():
    rocks = [t for t in ALL if W.get(*t) in C.SMALL_ROCKS]
    walls = [(x, y) for x, y in ALL if 3 <= x < 189 and 3 <= y < 189 and W.is_wall(x, y)]
    assert len(rocks) > 150 and len(walls) > 60
    assert {W.get(*t) for t in rocks} == set(C.SMALL_ROCKS)
    assert all(W.dist_from_center(*t) >= C.SMALL_ROCK_MIN_DIST for t in rocks)
    reach = W.reachable_from(C.BASE_TILE)          # sem quebrar nada
    for v in W.veins:
        assert all(t in reach for t in v.tiles)
    tx, ty = W.crater
    assert any((tx + dx, ty + 3) in reach for dx in range(3))
    assert len(reach) > 0.8 * 186 * 186


def test_hills_are_small_blobs():
    """Cada morro (parede ligada, fora da borda) tem de 3 a 8 tiles de largura e de altura."""
    seen = set()
    walls = {(x, y) for x, y in ALL if 3 <= x < 189 and 3 <= y < 189 and W.is_wall(x, y)}
    for start in walls:
        if start in seen:
            continue
        blob, stack = set(), [start]
        while stack:
            x, y = stack.pop()
            if (x, y) in blob or (x, y) not in walls:
                continue
            blob.add((x, y))
            stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        seen |= blob
        xs, ys = [x for x, _ in blob], [y for _, y in blob]
        assert max(xs) - min(xs) + 1 <= 8 and max(ys) - min(ys) + 1 <= 8, start


def test_water_and_plants_still_appear():
    assert not any(W.is_water(x, y, 1) for x, y in ALL)
    assert any(W.is_water(x, y, 2) for x, y in ALL)
    assert any(W.plant_at(x, y) for x, y in ALL)
    for v in W.veins:
        assert not any(W.is_water(x, y, 3) for x, y in v.tiles)


def test_sand_variants_follow_the_designer_distribution():
    from game.surface_gen import sand_variant
    counts = [0, 0, 0, 0]
    for x, y in ALL:
        v = W.sand_variants[y][x]
        assert v == sand_variant(x, y)
        counts[v] += 1
    total = len(ALL)
    assert counts[0] / total > 0.45 and counts[1] / total > 0.12           # lisa domina, cascalho comum
    assert 0.03 < counts[2] / total < 0.3 and counts[3] / total < 0.08     # dunas em zonas, laje rara


def _hill_walls(w):
    return {(x, y) for y in range(3, 189) for x in range(3, 189) if w.is_wall(x, y)}


def test_hills_have_no_loose_diagonals_or_spurs():
    """Marco 4: morro orgânico, sem tile encostando só pela quina, sem ponta de 1 tile e sem dente de 1 tile."""
    for seed in (1, 2, 3, C.WORLD_SEED):
        w = generate_surface(seed)
        walls = _hill_walls(w)
        for x, y in walls:
            sides = sum(n in walls for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
            assert sides >= 2, (seed, x, y)                                  # nem ilhado nem ponta solta
        for y in range(3, 188):
            for x in range(3, 188):
                a, b, c, d = (x, y) in walls, (x + 1, y) in walls, (x, y + 1) in walls, (x + 1, y + 1) in walls
                assert not (a and d and not b and not c) and not (b and c and not a and not d), (seed, x, y)


def test_hill_count_and_mass_stay_close():
    """A forma nova não muda o tamanho do deserto: 24–32 morros e ~500–850 tiles de rocha."""
    lo, hi = C.HILLS
    for seed in (1, 2, 3, C.WORLD_SEED):
        walls = _hill_walls(generate_surface(seed))
        seen, hills = set(), 0
        for start in walls:
            if start in seen:
                continue
            hills += 1
            stack = [start]
            while stack:
                t = stack.pop()
                if t in seen or t not in walls:
                    continue
                seen.add(t)
                stack += [(t[0] + 1, t[1]), (t[0] - 1, t[1]), (t[0], t[1] + 1), (t[0], t[1] - 1)]
        assert lo - 2 <= hills <= hi, (seed, hills)
        assert 500 <= len(walls) <= 850, (seed, len(walls))
