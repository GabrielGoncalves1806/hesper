"""v0.4 Marco 3 · M3.3: lagos nas bacias (bíblia §12, "Chuva e lagos").

A altura da água sai do índice de água (`thaw.lake_level`), fica em `layer.water_level` (derivado, não vai no
save) e, com geo, `World.is_water` é só `geo.height < water_level` num tile de chão: enche das partes mais fundas
pra fora e nada aleatório (o `lowness` sai da superfície)."""

import os
import random

import numpy as np
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import save  # noqa: E402
from game.geo import PLATEAU, SALAR  # noqa: E402
from game.rock_respawn import can_spawn  # noqa: E402
from game.surface_gen import generate_surface  # noqa: E402
from game.systems import GameState  # noqa: E402
from game.thaw import lake_level  # noqa: E402

SEEDS = (1, 7, 42)
_WORLDS: dict = {}


def surface(seed: int = C.WORLD_SEED):
    if seed not in _WORLDS:
        _WORLDS[seed] = generate_surface(seed)
    w = _WORLDS[seed]
    w.water_level = -1.0
    return w


def wet_tiles(world) -> set[tuple[int, int]]:
    return {(x, y) for y in range(world.height) for x in range(world.width) if world.is_water(x, y, C.GREEN_STAGE)}


# ---------------------------------------------------------------- lake_level (função pura)
def test_lake_level_is_dry_below_the_first_mark():
    assert lake_level(0) < 0
    assert lake_level(C.LAKE_WATER[0] - 1) < 0


def test_lake_level_hits_each_geo_level_exactly():
    for k in range(3):
        assert lake_level(C.LAKE_WATER[k]) == C.GEO_LEVELS[k]
    assert lake_level(C.LAKE_WATER[2] * 10) == C.GEO_LEVELS[2]     # acima do último: fica em L3


def test_lake_level_is_monotonic():
    values = [lake_level(w) for w in range(0, C.LAKE_WATER[2] + 5000, 250)]
    assert all(b >= a for a, b in zip(values, values[1:]))
    mid = (C.LAKE_WATER[0] + C.LAKE_WATER[1]) / 2
    assert C.GEO_LEVELS[0] < lake_level(mid) < C.GEO_LEVELS[1]


# ---------------------------------------------------------------- is_water pelo geo
@pytest.mark.parametrize("seed", SEEDS)
def test_dry_world_has_no_water_in_any_stage(seed):
    w = surface(seed)
    tiles = [(x, y) for y in range(w.height) for x in range(w.width)]
    for stage in (C.MIST_STAGE, C.GREEN_STAGE):
        assert not any(w.is_water(x, y, stage) for x, y in tiles)


@pytest.mark.parametrize("seed", SEEDS)
def test_at_l1_only_l1_basin_floods(seed):
    w = surface(seed)
    w.water_level = C.GEO_LEVELS[0]
    wet = wet_tiles(w)
    assert wet
    assert all(w.geo.basin[y, x] == 0 for x, y in wet)
    assert any(w.geo.region[y, x] == SALAR for x, y in wet)


@pytest.mark.parametrize("seed", SEEDS)
def test_nothing_outside_a_basin_ever_floods(seed):
    w = surface(seed)
    w.water_level = C.GEO_LEVELS[2]
    wet = wet_tiles(w)
    assert all(w.geo.basin[y, x] >= 0 for x, y in wet)
    # e a água da Névoa (stage) é ignorada com geo: o mesmo nível dá a mesma água em qualquer estágio
    assert all(w.is_water(x, y, C.MIST_STAGE) for x, y in list(wet)[:200])


@pytest.mark.parametrize("seed", SEEDS)
def test_salar_floods_before_the_plateau(seed):
    w = surface(seed)
    g = w.geo
    salar = (g.region == SALAR) & (g.basin >= 0)
    plateau = (g.region == PLATEAU) & (g.basin >= 0)
    assert g.height[salar].min() < g.height[plateau].min()
    w.water_level = float(g.height[plateau].min())          # a água ainda não chegou no fundo das depressões
    wet = wet_tiles(w)
    assert wet and all(g.region[y, x] == SALAR for x, y in wet)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("level", [0.12, C.GEO_LEVELS[0], 0.25, C.GEO_LEVELS[1], C.GEO_LEVELS[2]])
def test_water_starts_from_the_lowest_tiles(seed, level):
    w = surface(seed)
    w.water_level = level
    h = w.geo.height
    wet = wet_tiles(w)
    dry_floor = [(x, y) for y, x in zip(*np.nonzero(w.geo.basin >= 0)) if (x, y) not in wet and w.is_floor(x, y)]
    if wet and dry_floor:
        assert max(h[y, x] for x, y in wet) < min(h[y, x] for x, y in dry_floor)


@pytest.mark.parametrize("seed", SEEDS)
def test_salt_ridge_stays_formation_and_becomes_an_islet(seed):
    w = surface(seed)
    w.water_level = C.GEO_LEVELS[2]
    ridges = [f for f in w.geo.formations if f.kind == "salt_ridge"]
    islets = 0
    for f in ridges:
        assert all(w.get(x, y) == C.FORMATION and not w.is_water(x, y, C.GREEN_STAGE) for x, y in f.tiles)
        ring = {(x + dx, y + dy) for x, y in f.tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - set(f.tiles)
        if any(w.is_water(x, y, C.GREEN_STAGE) for x, y in ring):
            islets += 1
    assert islets >= 1                                        # pelo menos uma vira ilhota no L3


@pytest.mark.parametrize("seed", SEEDS)
def test_base_never_floods(seed):
    w = surface(seed)
    w.water_level = C.GEO_LEVELS[2] + 0.05                    # até acima do L3
    assert not any(w.dist_from_center(x, y) < C.GEO_PLATEAU_CORE for x, y in wet_tiles(w))


def test_veins_wrecks_and_crater_stay_dry_at_l3():
    w = surface()
    w.water_level = C.GEO_LEVELS[2]
    wet = wet_tiles(w)
    assert not any(t in wet for v in w.veins for t in v.tiles)
    assert not any(t in wet for wr in w.wrecks for t in [*wr.tiles, wr.crate])


def test_future_lake_is_the_basin_with_geo():
    w = surface()
    for y in range(0, w.height, 3):
        for x in range(0, w.width, 3):
            assert w.future_water(x, y) == (w.geo.basin[y, x] >= 0 and w.is_floor(x, y))


def test_rocks_never_respawn_in_a_basin():
    w = surface()
    basin = [(x, y) for y, x in zip(*np.nonzero(w.geo.basin >= 0))]
    assert not any(can_spawn(w, x, y) for x, y in basin)


# ---------------------------------------------------------------- GameState: nível derivado e eventos
def mist_state(water: float = 0.0) -> GameState:
    s = GameState(rng=random.Random(1))
    s.stage = C.MIST_STAGE
    s.indices["water"] = water
    return s


def lake_events(s: GameState) -> list[tuple]:
    return [e for e in s.pop_events() if e[0] == "lake_rise"]


def test_water_level_follows_the_index_and_fires_each_level_once():
    s = mist_state()
    s._apply_thaw()
    assert s.surface.water_level < 0 and not lake_events(s)
    s.indices["water"] = C.LAKE_WATER[0]
    s._apply_thaw()
    assert s.surface.water_level == C.GEO_LEVELS[0]
    assert lake_events(s) == [("lake_rise", 0)]
    s._apply_thaw()
    assert not lake_events(s)                                 # uma vez só
    s.indices["water"] = C.LAKE_WATER[2] + 1
    s._apply_thaw()
    assert s.surface.water_level == C.GEO_LEVELS[2]
    assert lake_events(s) == [("lake_rise", 1), ("lake_rise", 2)]


def test_water_level_moves_in_steps_and_never_goes_down():
    s = mist_state(C.LAKE_WATER[0])
    s._apply_thaw()
    level = s.surface.water_level
    s.indices["water"] += 1                                   # mexeu quase nada: o nível não muda (render barato)
    s._apply_thaw()
    assert s.surface.water_level == level
    s.indices["water"] = (C.LAKE_WATER[0] + C.LAKE_WATER[1]) / 2
    s._apply_thaw()
    assert C.GEO_LEVELS[0] < s.surface.water_level < C.GEO_LEVELS[1]
    high = s.surface.water_level
    s.indices["water"] = 0
    s._apply_thaw()
    assert s.surface.water_level == high                      # nunca desce


def test_no_lake_before_the_mist():
    s = mist_state(C.LAKE_WATER[1])
    s.stage = C.ARID_STAGE
    s._apply_thaw()
    assert s.surface.water_level < 0 and not lake_events(s)


def test_machines_update_raises_the_lake():
    s = mist_state(C.LAKE_WATER[0])
    s._update_machines(0.016)
    assert s.surface.water_level == C.GEO_LEVELS[0]


def test_water_level_is_derived_on_load_and_not_saved():
    s = mist_state(C.LAKE_WATER[1])
    s._apply_thaw()
    data = save.state_to_dict(s)
    assert "water_level" not in str(data["layers"])
    loaded = save.state_from_dict(data)
    assert loaded.surface.water_level == C.GEO_LEVELS[1]
    assert loaded.surface.world.water_level == C.GEO_LEVELS[1]


def test_cave_never_has_water():
    s = mist_state(C.LAKE_WATER[2])
    s.enter_layer("cave")
    s._apply_thaw()
    cave = s.layers["cave"].world
    assert not any(cave.is_water(x, y, C.GREEN_STAGE) for y in range(cave.height) for x in range(cave.width))


# ---------------------------------------------------------------- plantas na beira d'água (Verde)
@pytest.mark.parametrize("seed", SEEDS)
def test_plants_crowd_the_shore(seed):
    w = surface(seed)
    shore = far = shore_p = far_p = 0
    for y in range(w.height):
        for x in range(w.width):
            if not w.is_floor(x, y) or w.dist_from_center(x, y) < 7 or w.geo.basin[y, x] >= 0:
                continue
            plant = w.plant_at(x, y) is not None
            if w.near_shore(x, y):
                shore += 1
                shore_p += plant
            else:
                far += 1
                far_p += plant
    assert shore > 100 and far > 1000
    assert abs(shore_p / shore - C.PLANT_CHANCE_SHORE) < 0.06
    assert abs(far_p / far - C.PLANT_CHANCE_FAR) < 0.02


def test_no_plant_inside_a_basin():
    w = surface()
    basin = [(x, y) for y, x in zip(*np.nonzero(w.geo.basin >= 0))]
    assert not any(w.plant_at(x, y) for x, y in basin)


def test_near_shore_is_within_three_tiles_of_a_basin():
    w = surface()
    b = w.geo.basin >= 0
    for y in range(0, w.height, 2):
        for x in range(0, w.width, 2):
            y0, y1 = max(0, y - C.LAKE_SHORE), y + C.LAKE_SHORE + 1
            x0, x1 = max(0, x - C.LAKE_SHORE), x + C.LAKE_SHORE + 1
            assert w.near_shore(x, y) == bool(b[y0:y1, x0:x1].any())


# ---------------------------------------------------------------- render e mapa
def test_render_memo_survives_frames_and_clears_when_the_level_changes():
    import pygame

    from game.assets import Sprites
    from game.render import Renderer
    pygame.init()
    pygame.display.set_mode((64, 64))
    s = mist_state(C.LAKE_WATER[0])
    s._apply_thaw()
    w = s.world
    x, y = next((x, y) for y, x in zip(*np.nonzero(w.geo.basin == 0)) if w.is_floor(x, y))
    r = Renderer(Sprites())
    r.sync_water(w)
    assert r._wet(w, x, y) is True
    r.sync_water(w)
    assert (x, y) in r._wet_memo                              # o nível não mudou: o memo continua
    w.water_level = -1.0
    r.sync_water(w)
    assert not r._wet_memo and r._wet(w, x, y) is False


def test_minimap_paints_the_lake():
    from game import minimap
    w = surface()
    x, y = next((x, y) for y, x in zip(*np.nonzero(w.geo.basin == 0)) if w.is_floor(x, y))
    dry = minimap.tile_color(w, x, y)
    w.water_level = C.GEO_LEVELS[0]
    assert minimap.tile_color(w, x, y) == minimap.WATER_COLOR != dry


@pytest.mark.parametrize("seed", (1, 7, 42))
def test_no_ore_spawns_in_a_basin(seed):
    """Nem rocha pequena nem afloramento no chão de bacia: quando o lago enche, não sobra minério boiando."""
    w = generate_surface(seed)
    rocks = [(x, y) for y, x in zip(*np.nonzero(w.geo.basin >= 0)) if w.get(x, y) in C.SMALL_ROCKS]
    assert rocks == []
