"""Veios 2×2 e drill automática: geração, colocar, extrair, coletar, desmontar."""

import random

import pytest

from game import config as C
from game.systems import Controls, GameState
from game.world import World
from tests.helpers import give

DT = 1 / 60


@pytest.fixture(scope="module")
def world() -> World:
    return World.generate()


def near_veins(world):
    cx, cy = C.CAVE_CENTER
    return [v for v in world.veins if ((v.tx + 1 - cx) ** 2 + (v.ty + 1 - cy) ** 2) ** 0.5 <= 20]


# ---------------------------------------------------------------- geração
def test_veins_are_deterministic(world):
    assert World.generate().veins == world.veins
    assert World.generate(C.WORLD_SEED + 1).veins != world.veins


def test_one_of_each_type_near_base_and_reachable(world):
    near = near_veins(world)
    assert sorted(v.resource for v in near) == sorted(C.RESOURCES)
    reach = world.reachable_from(C.CAVE_CENTER)
    for v in near:
        assert all(t in reach for t in v.tiles)          # dá pra chegar andando, sem cavar


def test_more_veins_far_away(world):
    far = [v for v in world.veins if v not in near_veins(world)]
    for r in C.RESOURCES:
        assert sum(v.resource == r for v in far) == C.VEINS_FAR_PER_TYPE


def test_veins_do_not_overlap_anything(world):
    seen = set()
    terminal_tiles = {(tx + dx, ty + dy) for tx, ty in world.terminals for dx in (-1, 0, 1) for dy in (-1, 0, 1, 2)}
    for v in world.veins:
        tiles = set(v.tiles)
        assert not tiles & seen                           # veio não encosta em outro
        assert not tiles & {(63, 63), (64, 63)}          # meio do salão (a rampa do Marco 2)
        assert not tiles & terminal_tiles
        assert all(2 < x < world.width - 3 and 2 < y < world.height - 3 for x, y in tiles)   # longe da borda
        assert all(world.get(x, y) == C.FLOOR for x, y in tiles)
        assert all(world.get(x, v.ty + 2) == C.FLOOR for x in (v.tx, v.tx + 1))   # chão embaixo (sem topo de parede)
        seen |= tiles


def test_vein_is_floor_not_minable_no_water_no_plants(world):
    for v in world.veins:
        for x, y in v.tiles:
            assert world.vein_at(x, y) is v
            assert not world.is_solid(x, y) and not world.is_minable(x, y)
            assert not world.is_water(x, y, 3)
            assert world.plant_at(x, y) is None


# ---------------------------------------------------------------- drill
def mist_game() -> GameState:
    game = GameState(rng=random.Random(5))
    game.debug_add_ti()                                   # Ti 10.000: drill liberada
    give(game, iron=200, silicon=200, ice=200)
    return game


def stand_below(game, vein):
    game.player.x, game.player.y = (vein.tx + 0.5) * C.TILE, (vein.ty + 3) * C.TILE - 4


def test_drill_unlocks_in_mist():
    game = GameState(rng=random.Random(5))
    give(game, iron=200, silicon=200)
    assert game.recipe_status("drill") == "locked"
    game.debug_add_ti()
    assert game.recipe_status("drill") == "ok"


def test_drill_only_on_free_vein_origin():
    game = mist_game()
    assert game.craft("drill")
    vein = game.world.veins[0]
    stand_below(game, vein)
    assert not game.can_place("drill", (vein.tx + 1, vein.ty))     # tile do veio, mas não o canto
    assert not game.can_place("drill", (vein.tx, vein.ty + 2))     # chão comum
    assert game.can_place("drill", (vein.tx, vein.ty))
    assert game.place("drill", (vein.tx, vein.ty))
    drill = game.drills[0]
    assert drill.resource == vein.resource and set(drill.tiles) == set(vein.tiles)
    assert all(game.machine_at(t) is drill for t in vein.tiles)    # ocupa os 2×2
    give(game, drill=1)                                            # mais uma no inventário
    assert not game.can_place("drill", (vein.tx, vein.ty))         # veio ocupado


def test_regular_machines_cannot_sit_on_veins():
    game = mist_game()
    game.craft("o2")
    vein = game.world.veins[0]
    stand_below(game, vein)
    assert not any(game.can_place("o2", t) for t in vein.tiles)


def place_drill(game):
    vein = game.world.veins[0]
    game.craft("drill")
    stand_below(game, vein)
    assert game.place("drill", (vein.tx, vein.ty))
    return game.drills[0]


def test_extraction_rate_capacity_and_full_event():
    game = mist_game()
    drill = place_drill(game)
    ti = game.ti
    game._update_machines(C.DRILL_INTERVAL * 3 + 1)
    assert drill.stored == 3
    assert game.ti == ti                                           # drill não soma Ti
    game.pop_events()
    game._update_machines(C.DRILL_INTERVAL * 100)
    assert drill.stored == C.DRILL_CAPACITY and drill.full
    assert [e for e in game.pop_events() if e[0] == "drill_full"]
    game._update_machines(C.DRILL_INTERVAL * 5)
    assert drill.stored == C.DRILL_CAPACITY                        # cheia, para
    assert not [e for e in game.pop_events() if e[0] == "drill_full"]


def test_drill_runs_with_the_real_update_and_f1():
    game = mist_game()
    drill = place_drill(game)
    game.toggle_time_scale()                                       # F1 ×10
    for _ in range(round(2.1 / DT)):
        game.update(DT, Controls())
    assert drill.stored == 1                                       # 2,1 s × 10 = 21 s


def test_collect_with_e_goes_to_inventory():
    game = mist_game()
    drill = place_drill(game)
    drill.stored = 12
    iron_before = game.inventory.counts()
    assert game.interaction() == ("drill", drill)
    assert game.collect(drill) == 12
    assert drill.stored == 0
    assert game.inventory.count(drill.resource) == iron_before[drill.resource] + 12
    assert game.drill_collected[drill.resource] == 12
    assert ("drill_collect", drill.resource, 12, drill.anchor) in game.pop_events()
    assert game.collect(drill) == 0                                # vazia: nada


def test_collect_needs_to_be_close():
    game = mist_game()
    drill = place_drill(game)
    game.player.x += 6 * C.TILE
    assert game.nearby_drill() is None
    assert game.interaction() is None or game.interaction()[0] != "drill"


def test_interaction_prefers_the_closest_between_terminal_and_drill():
    game = mist_game()
    drill = place_drill(game)
    game.layers["surface"].world.terminals.append(cave_terminal := (90, 60))   # terminal "de mentira" na superfície
    game.world.set(*cave_terminal, C.TERMINAL)
    tx, ty = game.world.terminals[0]
    game.player.x, game.player.y = (tx + 0.5) * C.TILE, (ty + 2) * C.TILE - 4
    assert game.interaction() == ("terminal", 0)                   # longe da drill, perto do terminal
    stand_below(game, game.world.veins[0])
    assert game.interaction() == ("drill", drill)


def test_dismantle_returns_drill_and_content():
    game = mist_game()
    drill = place_drill(game)
    drill.stored = 7
    before = game.inventory.count(drill.resource)
    assert game.dismantle(drill)
    assert game.inventory.count("drill") == 1 and not game.drills
    assert game.inventory.count(drill.resource) == before + 7
    vein = game.world.veins[0]
    assert game.place("drill", (vein.tx, vein.ty))                 # recoloca no mesmo veio
    assert game.drills[0].stored == 0


def test_drill_hit_area_is_the_tall_sprite():
    game = mist_game()
    drill = place_drill(game)
    ax, ay = drill.anchor
    assert game.machine_at_point(ax, ay - 2) is drill
    assert game.machine_at_point(ax, ay - 76) is drill             # cabeça (sobe 16 px pro tile de cima)
    assert game.machine_at_point(ax, ay - 84) is None
