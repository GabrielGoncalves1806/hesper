"""Gerador do deserto (superfície, v0.3 Marco 1)."""

import math

import pytest

from game import config as C
from game.geo import BASALT, FROST, PLATEAU, REGION_NAMES, SALAR
from game.rock_respawn import blocked_tiles, can_spawn
from game.surface_gen import generate_surface

W = generate_surface(C.WORLD_SEED)
ALL = [(x, y) for y in range(C.SURFACE_H) for x in range(C.SURFACE_W)]
HILL_TILES = (C.ROCK, C.IRON, C.SILICON, C.ICE)     # morro minerável (a BEDROCK é a cordilheira e os bolsões)


def pocket_rock(w) -> set:
    """Os anéis de rocha dos bolsões dos gelos-portão (BEDROCK ligada à cordilheira do norte)."""
    return {t for p in w.geo.pockets for t in p.ring}


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
    rings = pocket_rock(W)                                      # Marco 2: a cordilheira desce nos bolsões
    assert all(W.get(x, y) != C.BEDROCK for y in range(3, 189) for x in range(3, 189) if (x, y) not in rings)
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
    walls = [(x, y) for x, y in ALL if 3 <= x < 189 and 3 <= y < 189 and W.get(x, y) in HILL_TILES]
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
    walls = {(x, y) for x, y in ALL if 3 <= x < 189 and 3 <= y < 189 and W.get(x, y) in HILL_TILES}
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
    """M3.3: com geo a água é o lago nas bacias, que sobe com o índice (`water_level`), e não mais a poça por
    estágio. Seca no começo (em qualquer estágio); no L1 aparece; veio nunca alaga."""
    assert W.water_level < 0
    assert not any(W.is_water(x, y, s) for x, y in ALL for s in (1, 2, 3, 4))
    try:
        W.water_level = C.GEO_LEVELS[0]
        assert any(W.is_water(x, y, 3) for x, y in ALL)
        W.water_level = C.GEO_LEVELS[2]
        for v in W.veins:
            assert not any(W.is_water(x, y, 4) for x, y in v.tiles)
    finally:
        W.water_level = -1.0
    assert any(W.plant_at(x, y) for x, y in ALL)


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
    return {(x, y) for y in range(3, 189) for x in range(3, 189) if w.get(x, y) in HILL_TILES}


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
    """A forma nova não muda o tamanho do deserto: 26–34 morros (v0.4 Marco 2: bacia e salar sem morro, então
    o alvo subiu de 24–32 pra manter a massa) e ~500–850 tiles de rocha."""
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


# ---------------------------------------------------------------------------------------------------------------
# v0.4 Marco 2 · geografia nova: formações, afloramentos, gelos-portão, regiões e alcance
# ---------------------------------------------------------------------------------------------------------------
SEEDS = (1, 7, 42)


def _near(tiles, r):
    return {(x + dx, y + dy) for x, y in tiles for dx in range(-r, r + 1) for dy in range(-r, r + 1)}


@pytest.mark.parametrize("seed", SEEDS)
def test_formation_tiles_are_exactly_the_footprints(seed):
    w = generate_surface(seed)
    feet = {t for f in w.geo.formations for t in f.tiles}
    assert feet and {t for t in ALL if w.get(*t) == C.FORMATION} == feet
    for t in feet:
        assert w.is_solid(*t) and not w.is_wall(*t) and not w.is_minable(*t)


@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_spawns_on_or_next_to_a_formation(seed):
    """Veio, destroço, cratera e rocha pequena ficam fora da caixa + halo das formações (só os afloramentos)."""
    w = generate_surface(seed)
    for f in w.geo.formations:
        halo = _near(f.box, C.FORMATION_HALO)
        for v in w.veins:
            assert not halo & set(v.tiles), (f.kind, v)
        for wreck in w.wrecks:
            assert not halo & set(wreck.tiles + [wreck.crate]), (f.kind, wreck.kind)
        cx, cy = w.crater
        assert not halo & {(cx + dx, cy + dy) for dx in range(3) for dy in range(3)}
        assert all(w.get(*t) != C.FORMATION for t in set(f.box) - set(f.tiles))   # o vão do arco é chão
    for t in w.keep_clear:
        assert not can_spawn(w, *t, blocked_tiles(w)), t                          # nem a rocha que reaparece


@pytest.mark.parametrize("seed", SEEDS)
def test_every_formation_has_outcrops(seed):
    """3 ou 4 afloramentos (rochas pequenas com o minério da região) a 1–2 tiles da pegada; o gelo-portão não."""
    w = generate_surface(seed)
    kinds = [f.kind for f in w.geo.formations]
    assert {"monolith", "arch", "salt_ridge", "basalt_spires", "cone"} <= set(kinds)
    for f in w.geo.formations:
        if f.kind == "ice_gate" or f.small or f.kind.startswith("vent_"):   # portão, pequenas da v9 e fumarolas: sem afloramento
            continue
        ring = _near(f.tiles, 2) - set(f.box)
        rocks = [t for t in ring if w.get(*t) in C.SMALL_ROCKS]
        assert not any(w.geo.basin_at(*t) >= 0 for t in rocks)        # nunca na bacia (vira lago no M3)
        dry = [t for t in ring if w.geo.basin_at(*t) < 0]
        # a crosta de sal fica no salar (quase todo bacia): com pouco chão seco em volta, sai com menos
        low = C.OUTCROPS[0] if len(dry) >= 3 * C.OUTCROPS[1] else 0
        assert low <= len(rocks) <= C.OUTCROPS[1], (f.kind, rocks)
        ores = set(C.OUTCROP_ORE[REGION_NAMES[f.region]])
        assert {C.SMALL_ROCKS[w.get(*t)] for t in rocks} <= ores
        if f.kind == "arch":                                   # o vão do arco e o que fica na frente/atrás
            gap = {(f.tx + dx, f.ty + dy) for dx in range(1, f.size[0] - 1) for dy in range(-2, 3)}
            assert not any(w.get(*t) in C.SMALL_ROCKS for t in gap)


@pytest.mark.parametrize("seed", SEEDS)
def test_formations_sit_in_their_region_away_from_base(seed):
    w = generate_surface(seed)
    for f in w.geo.formations:
        assert all(w.geo.region_at(*t) == f.region for t in f.box), f.kind
        assert math.hypot(f.center[0] - C.BASE_TILE[0], f.center[1] - C.BASE_TILE[1]) >= C.FORMATION_MIN_BASE_DIST


@pytest.mark.parametrize("seed", SEEDS)
def test_wrecks_and_veins_reachable_on_foot_and_gates_block_only_their_pocket(seed):
    """BFS no grid a partir da base, sem cavar: todo destroço (a caixa) e todo veio. O interior de cada bolsão só
    fica alcançável quando o gelo-portão some (Marco 3), e o anel de rocha não minera (não dá pra contornar)."""
    w = generate_surface(seed)
    reach = w.reachable_from(C.BASE_TILE)
    for wreck in (x for x in w.wrecks if not x.rich):      # o destroço rico (M3.2) fica atrás do portão
        x, y = wreck.crate
        assert any(n in reach for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))), wreck.kind
    for v in w.veins:
        assert all(t in reach for t in v.tiles), v
    pockets = w.geo.pockets
    assert C.ICE_GATES[0] <= len(pockets) <= C.ICE_GATES[1]
    for p in pockets:
        assert not reach & set(p.interior)
        assert reach & set(p.apron)
        assert all(w.get(*t) == C.BEDROCK and not w.is_minable(*t) for t in p.ring)
        assert all(w.geo.region_at(*t) == FROST for t in p.interior + p.gate.tiles)
        assert p.wreck_spot in p.interior and p.container_spot in p.interior
    opened = generate_surface(seed)
    for p in pockets:
        for t in p.gate.tiles:
            opened.set(*t, C.SAND)
    reach2 = opened.reachable_from(C.BASE_TILE)
    for p in pockets:
        assert {t for t in p.interior if not opened.is_solid(*t)} <= reach2   # menos o destroço rico e o contêiner


@pytest.mark.parametrize("seed", SEEDS)
def test_crater_in_the_plateau_and_dry(seed):
    w = generate_surface(seed)
    tx, ty = w.crater
    for dx in range(-2, 5):
        for dy in range(-2, 5):
            assert w.geo.region_at(tx + dx, ty + dy) == PLATEAU and w.geo.basin_at(tx + dx, ty + dy) < 0


@pytest.mark.parametrize("seed", SEEDS)
def test_hills_follow_the_regions(seed):
    """O salar quase sem morro, o basalto com mais morro por tile que o planalto, e morro nenhum em bacia."""
    w = generate_surface(seed)
    walls = _hill_walls(w)
    assert not any(w.geo.basin_at(*t) >= 0 for t in walls)
    area = {r: (w.geo.region == r).sum() for r in (PLATEAU, SALAR, BASALT)}
    per = {r: sum(w.geo.region_at(*t) == r for t in walls) / area[r] for r in area}
    assert per[SALAR] < 0.25 * per[PLATEAU]
    assert per[BASALT] > per[PLATEAU]


@pytest.mark.parametrize("seed", SEEDS)
def test_veins_and_wrecks_stay_out_of_basins(seed):
    w = generate_surface(seed)
    for v in w.veins:
        assert all(w.geo.basin_at(*t) < 0 for t in v.tiles)
    for wreck in w.wrecks:
        assert all(w.geo.basin_at(*t) < 0 for t in wreck.tiles + [wreck.crate])
