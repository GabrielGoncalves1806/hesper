"""Interior da VÉSPER-7 (v0.7 M4): geração da camada pela seed."""

import pytest

from game import config as C
from game import layers, ruins, vesper

SEEDS = range(0, 60, 3)


def test_plans_respect_slots():
    for slot in vesper.SLOTS:
        for key in vesper.VARIANTS[slot.key]:
            plan = vesper.load(key)
            _, _, w, h = slot.box
            assert len(plan.grid) == h and all(len(r) == w for r in plan.grid), key
            for x, y in slot.passages:
                assert plan.grid[y][x] == ".", (key, x, y)


def test_variants_differ():
    for slot in vesper.SLOTS:
        a, b = (vesper.load(k).grid for k in vesper.VARIANTS[slot.key])
        assert a != b, slot.key


def test_plan_requirements():
    def count(key, ch):
        return sum(r.count(ch) for r in vesper.load(key).grid)
    for key in vesper.VARIANTS["bridge"]:
        assert vesper.load(key).grid[0][9] == "J" and count(key, "P") == 1 and count(key, "1") == 1
        assert vesper.load(key).logs["1"] == 21
    for key in vesper.VARIANTS["bunks"]:
        plan = vesper.load(key)
        assert plan.logs["1"] == 22 and count(key, "1") == 1
        bunk = next(k for k, v in plan.props.items() if v == "prop_bunk")
        assert count(key, bunk) >= 2
    for key in vesper.VARIANTS["cold"]:
        assert vesper.load(key).logs["1"] == 23 and count(key, "1") == 1 and count(key, "K") == 1
    for key in vesper.VARIANTS["hold"]:
        assert count(key, "E") == 1 and count(key, "c") == 2


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_same_ship(seed):
    a, b = vesper.compose(seed), vesper.compose(seed)
    assert a.grid == b.grid and a.props == b.props and vesper.fixtures_of(seed) == vesper.fixtures_of(seed)


def test_seeds_vary():
    assert len({tuple(vesper.compose(s).grid) for s in range(40)}) > 1


@pytest.mark.parametrize("seed", SEEDS)
def test_required_pieces(seed):
    fx = vesper.fixtures_of(seed)
    kinds = sorted(fx.values())
    assert kinds.count("hatch") == 1 and kinds.count("container_broken") == 1
    assert kinds.count("power_panel") == 1 and kinds.count("jammed_door") == 1
    ox, oy = vesper.ORIGIN
    assert fx[(ox + 11 + 9, oy + 0)] == "jammed_door"           # porta emperrada no norte, sempre no mesmo lugar
    ship = vesper.compose(seed)
    assert sorted(ship.terminals.values()) == [21, 22, 23]


@pytest.mark.parametrize("seed", SEEDS)
def test_props_are_valid_in_the_composed_grid(seed):
    ship = vesper.compose(seed)
    for (x, y), kind in ship.props.items():
        assert ruins.ok_in_plan(ship.grid, x, y, kind), (seed, x, y, kind)
    for (x, y), kind in vesper.fixtures_of(seed).items():
        if kind in vesper.WALL_FIXTURES:
            assert ship.grid[y][x] == "#" and ship.grid[y + 1][x] == ".", (seed, x, y, kind)


@pytest.mark.parametrize("seed", SEEDS)
def test_everything_reachable_from_hatch(seed):
    layer = layers.make_vesper(seed)
    world = layer.world
    start = vesper.hatch_tile(world)
    seen = vesper.walkable_from(world, layer, start)
    assert (start[0], start[1] - 1) in seen                      # onde o player chega

    def touches(t):
        x, y = t
        return any(n in seen for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for tile in layer.crates:
        assert touches(tile)
    for tile in world.ruin_terminals:                            # o tile de baixo do terminal
        assert (tile[0], tile[1] + 1) in seen
    for tile, kind in world.fixtures.items():
        if kind in ("power_panel", "jammed_door"):
            assert (tile[0], tile[1] + 1) in seen
        elif kind == "container_broken":
            assert touches(tile)
    for m in layer.machines:                                     # as luminárias quebradas também se alcançam
        assert any(n in seen for t in m.tiles for n in ((t[0] + 1, t[1]), (t[0] - 1, t[1]), (t[0], t[1] + 1), (t[0], t[1] - 1)))


@pytest.mark.parametrize("seed", SEEDS)
def test_layer_shape(seed):
    layer = layers.make_vesper(seed)
    world = layer.world
    assert (world.width, world.height) == vesper.SIZE
    assert len(layer.crates) == 2 and not layer.has_base and world.crater is None
    assert world.get(0, 0) == C.BEDROCK
    hx, hy = vesper.hatch_tile(world)
    assert world.is_floor(hx, hy) and world.is_floor(hx, hy - 1)
    kx, ky = next(t for t, k in world.fixtures.items() if k == "container_broken")
    assert world.is_solid(kx, ky)
    assert all(p.ruin for p in layer.props.values())


def test_makers_and_logs():
    assert layers.MAKERS[layers.VESPER] is layers.make_vesper
    assert len(C.LOGS) == len(C.LOG_TITLES) == len(C.LOG_DAYS) == 24
    assert C.LOG_DAYS[21:] == [188, 190, 193]
    assert C.LOG_TITLES[21:] == ["CABINE · VÉSPER-7", "ALOJAMENTO · VÉSPER-7", "CAMARA FRIA · VÉSPER-7"]


def test_pristine_tiles_of_vesper():
    from game import save
    world = layers.make_vesper(5).world
    assert save.pristine_tiles(5, layers.VESPER) == world.tiles
