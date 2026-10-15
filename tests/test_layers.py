"""Camadas (superfície e caverna) e os tipos de tile novos do v0.3."""

import random

import pytest

from game import config as C
from game.systems import Controls, GameState, Machine
from game.world import World


# ---------------------------------------------------------------- tiles: parede alta × sólido baixo
def test_flat_solids_are_solid_but_not_walls():
    w = World(seed=1, width=8, height=8)
    w.set(2, 2, C.SMALL_IRON)
    w.set(3, 3, C.CRATER)
    w.set(4, 4, C.ROCK)
    w.set(5, 5, C.SAND)
    assert w.is_solid(2, 2) and not w.is_wall(2, 2) and w.is_minable(2, 2)
    assert w.is_solid(3, 3) and not w.is_wall(3, 3) and not w.is_minable(3, 3)
    assert w.is_wall(4, 4) and w.is_floor(5, 5) and not w.is_solid(5, 5)
    w.set(1, 1, C.FLOOR)
    assert w.is_floor(1, 1)                      # FLOOR também é chão


def test_visual_tile_ignores_flat_solids():
    w = World(seed=1, width=8, height=8)
    w.set(2, 3, C.SMALL_IRON)
    assert w.visual_tile_at(2 * C.TILE + 5, 2 * C.TILE + 20) == (2, 2)   # rocha pequena não tem topo elevado
    w.set(2, 3, C.ROCK)
    assert w.visual_tile_at(2 * C.TILE + 5, 2 * C.TILE + 20) == (2, 3)   # parede alta tem


# ---------------------------------------------------------------- camadas no GameState
from game.layers import CAVE, SURFACE  # noqa: E402
from tests.helpers import give  # noqa: E402

DT = 1 / 60


def run(game, seconds, controls=None):
    for _ in range(round(seconds / DT)):
        game.update(DT, controls or Controls())


def test_game_starts_on_the_surface_with_layers():
    g = GameState(rng=random.Random(1))
    assert g.layer == SURFACE and set(g.layers) == {SURFACE}
    assert g.world is g.layers[SURFACE].world and g.world.width == C.SURFACE_W
    assert g.in_base_zone() and g.layers[SURFACE].rocks is not None


def test_cave_layer_has_its_own_world_and_machines_but_global_energy_and_ti():
    g = GameState(rng=random.Random(1))
    g.machines.append(Machine("solar", 90, 90))
    g.enter_layer(CAVE)
    assert g.layer == CAVE and g.world.width == C.CAVE_W and g.machines == []
    assert not g.in_base_zone() and g.active.rocks is None
    g.machines.append(Machine("o2", 60, 60))
    assert g.power.production == C.POD_POWER + 4 and g.power.consumption == 1
    assert g.ti_rate == 3
    g._update_machines(1.0)
    assert g.indices["o2"] == pytest.approx(3)
    g.enter_layer(SURFACE)
    assert [m.kind for m in g.machines] == ["solar"] and len(g.all_machines) == 2


def test_machines_setter_and_world_setter_hit_the_active_layer():
    g = GameState(rng=random.Random(1))
    g.machines = [Machine("o2", 90, 90)]
    assert g.layers[SURFACE].machines[0].kind == "o2"


def test_faint_in_cave_wakes_up_on_the_surface():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    g._faint()
    run(g, C.FAINT_RESPAWN_AT + 0.1)
    assert g.layer == SURFACE and (g.player.x, g.player.y) == C.SPAWN_POS


def test_each_layer_has_its_own_drone_network():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    cave_chest = Machine("chest", 60, 60)
    g.machines.append(cave_chest)
    g.enter_layer(SURFACE)
    assert cave_chest not in g.drone_logistics() and cave_chest in g.drone_logistics(CAVE)
    assert g.base_chests() == []


def test_small_rock_drops_2_to_4_and_becomes_sand():
    amounts = set()
    for seed in range(20):
        g = GameState(rng=random.Random(seed))
        px, py = g.player.tile
        g.world.set(px + 1, py, C.SMALL_SILICON)
        run(g, 0.8, Controls(mine_tile=(px + 1, py)))
        assert g.world.get(px + 1, py) == C.SAND
        amounts.add(g.inventory.count("silicon"))
        assert g.mined_total["silicon"] == g.inventory.count("silicon")
    assert amounts <= {2, 3, 4} and len(amounts) > 1


def test_mined_hill_becomes_sand():
    g = GameState(rng=random.Random(1))
    px, py = g.player.tile
    g.world.set(px + 1, py, C.ROCK)
    run(g, 0.7, Controls(mine_tile=(px + 1, py)))
    assert g.world.get(px + 1, py) == C.SAND


# ---------------------------------------------------------------- rochas reaparecendo (jogo de verdade)
def test_rocks_respawn_with_the_real_update():
    from game.rock_respawn import count
    g = GameState(rng=random.Random(1))
    before = count(g.world)
    g.toggle_time_scale()                                  # F1 acelera
    run(g, C.ROCK_RESPAWN / C.DEBUG_TIME_SCALE * 3 + 0.05)
    events = [e for e in g.pop_events() if e[0] == "rock_spawn"]
    assert count(g.world) == before + 3 and len(events) == 3
    assert all(g.world.get(*e[1]) in C.SMALL_ROCKS for e in events)


def test_cave_layer_is_made_by_the_old_generator():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    assert len(g.world.terminals) == 3 and g.world.center == (g.world.crater[0] + 1, g.world.crater[1] + 3)
    give(g, iron=1)
