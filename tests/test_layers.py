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
from game.pickups import Pickup, Pickups  # noqa: E402
from tests.helpers import give  # noqa: E402

DT = 1 / 60


def run(game, seconds, controls=None):
    for _ in range(round(seconds / DT)):
        game.update(DT, controls or Controls())


def test_game_starts_on_the_surface_with_layers():
    g = GameState(rng=random.Random(1))
    assert g.layer == SURFACE and set(g.layers) == {SURFACE}
    assert g.world is g.layers[SURFACE].world and g.world.width == C.SURFACE_W
    assert g.in_base_zone() and g.pickups is g.layers[SURFACE].pickups
    assert len(g.pickups.items) == C.PICKUP_START


def test_cave_layer_has_its_own_world_and_machines_but_global_energy_and_ti():
    g = GameState(rng=random.Random(1))
    g.machines.append(Machine("solar", 90, 90))
    g.enter_layer(CAVE)
    assert g.layer == CAVE and g.world.width == C.CAVE_W and g.machines == []
    assert not g.in_base_zone() and g.pickups is None
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


def test_drones_only_serve_the_surface():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    cave_chest = Machine("chest", 60, 60)
    g.machines.append(cave_chest)
    g.enter_layer(SURFACE)
    assert cave_chest not in g.drone_logistics() and g.base_chests() == []


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


# ---------------------------------------------------------------- pegar soltos
def with_pickup(resource="iron", amount=2, dx=3):
    g = GameState(rng=random.Random(1))
    g.pickups.items = []
    p = Pickup(resource, amount, g.player.x + dx * C.TILE, g.player.y - 4)
    g.pickups.items.append(p)
    return g, p


def test_walk_over_pickup_collects_it():
    g, p = with_pickup(dx=2)
    run(g, 1.0, Controls(move_x=1))
    assert g.pickups.items == []
    assert g.inventory.count("iron") == 2 and g.mined_total["iron"] == 2
    assert any(e[0] == "pickup" and e[2] == "iron" and e[3] == 2 for e in g.pop_events())


def test_full_inventory_keeps_pickup_and_warns_once():
    g, p = with_pickup(dx=0)
    for i in range(C.INVENTORY_SLOTS):
        g.inventory.add("o2", C.STACK_MACHINE)
    run(g, 0.5)
    events = g.pop_events()
    assert p in g.pickups.items and sum(e[0] == "inv_full" for e in events) == 1
    g.inventory.remove("o2", C.STACK_MACHINE)            # abriu um slot: pega sozinho, ainda em cima
    run(g, 0.1)
    assert g.pickups.items == [] and g.inventory.count("iron") == 2


def test_partial_pickup_leaves_the_rest():
    g, p = with_pickup(amount=3, dx=0)
    for i in range(C.INVENTORY_SLOTS - 1):
        g.inventory.add("o2", C.STACK_MACHINE)
    g.inventory.add("iron", C.STACK_RESOURCE - 1)
    run(g, 0.1)
    assert g.inventory.count("iron") == C.STACK_RESOURCE and p.amount == 2 and p in g.pickups.items


def test_e_and_mouse_take_pickup_in_reach():
    g, p = with_pickup(dx=1.5)
    assert g.interactable_at(p.x, p.y - 3) == ("pickup", p)
    assert g.interaction() == ("pickup", p)
    assert g.take_pickup(p) == 2 and g.pickups.items == []
    g2, far = with_pickup(dx=6)
    assert g2.interactable_at(far.x, far.y) == ("pickup", far)
    assert not g2.in_reach("pickup", far) and g2.interaction() is None


def test_pickups_respawn_with_the_real_update():
    g = GameState(rng=random.Random(1))
    g.pickups.items = []
    g.toggle_time_scale()                                  # F1 acelera
    run(g, C.PICKUP_RESPAWN / C.DEBUG_TIME_SCALE * 3 + 0.05)
    assert len(g.pickups.items) == 3


def test_cave_layer_is_made_by_the_old_generator():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    assert len(g.world.terminals) == 3 and g.world.center == C.CAVE_CENTER
    give(g, iron=1)
