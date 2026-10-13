"""v0.3 Marco 2 · caverna: geração, rampa, luminária, luz e áudio."""

import random

from game import config as C
from game import layers
from game.world import World

W = World.generate(C.WORLD_SEED)


# ---------------------------------------------------------------- geração
def test_cave_has_ramp_up_in_the_open_hall():
    tx, ty = W.crater
    assert (tx, ty) == C.CAVE_RAMP
    ramp = layers.ramp_tiles(W)
    assert len(ramp) == 9 and all(W.get(x, y) == C.CRATER for x, y in ramp)
    assert layers.ramp_target(W) == (tx + 1, ty + 2)
    ax, ay = layers.ramp_arrival(W)
    arrival = (int(ax // C.TILE), int((ay - 1) // C.TILE))
    assert arrival == (tx + 1, ty + 3) and W.is_floor(*arrival)
    hall = [(x, y) for y in range(128) for x in range(128) if W.dist_from_center(x, y) < C.CAVE_SAFE_RADIUS]
    assert all(W.is_floor(x, y) for x, y in hall if (x, y) not in ramp)


def test_cave_never_terraforms():
    tiles = [(x, y) for y in range(128) for x in range(128)]
    assert not W.terraforms
    assert not any(W.is_water(x, y, C.GREEN_STAGE) for x, y in tiles)
    assert not any(W.plant_at(x, y) for x, y in tiles)


def ore_ratio(world, lo, hi):
    cells = [world.tiles[y][x] for y in range(128) for x in range(128)
             if lo <= world.dist_from_center(x, y) < hi and not world.is_floor(x, y)]
    return sum(t in C.ORE_TILES for t in cells) / len(cells)


def test_cave_ore_is_more_abundant_and_richer_far():
    assert ore_ratio(W, 40, 60) > ore_ratio(W, 13, 22) > 0.15
    assert 0.34 < ore_ratio(W, 13, 60) < 0.43     # ~39% das paredes (era ~48%, o dono achou demais)
    assert len(W.veins) >= 15                     # veios comuns


def wall_ore_share(world):
    walls = [t for row in world.tiles for t in row if t in (C.ROCK, C.IRON, C.SILICON, C.ICE)]
    return sum(t in C.ORE_TILES for t in walls) / len(walls)


def test_cave_ore_share_is_about_38_to_40_percent_and_the_ramp_has_enough():
    shares = []
    for seed in (7, 1, 42):
        world = W if seed == C.WORLD_SEED else World.generate(seed)
        shares.append(wall_ore_share(world))
        near = [C.ORE_TILES[world.tiles[y][x]] for y in range(128) for x in range(128)
                if world.tiles[y][x] in C.ORE_TILES and world.dist_from_center(x, y) < 20]
        for resource in C.RESOURCES:                 # começo: dezenas de cada minério a até 20 tiles da rampa
            assert near.count(resource) >= 40, (seed, resource, near.count(resource))
    assert all(0.35 < s < 0.43 for s in shares)
    assert 0.37 <= sum(shares) / len(shares) <= 0.41


def test_other_layer():
    assert layers.other_layer(layers.SURFACE) == layers.CAVE
    assert layers.other_layer(layers.CAVE) == layers.SURFACE


def test_surface_crater_uses_the_same_ramp_rules():
    from game.surface_gen import generate_surface
    s = generate_surface(C.WORLD_SEED)
    tx, ty = s.crater
    assert layers.ramp_target(s) == (tx + 1, ty + 2)
    ax, ay = layers.ramp_arrival(s)
    assert s.is_floor(int(ax // C.TILE), int((ay - 1) // C.TILE))


# ---------------------------------------------------------------- rampa no GameState
from game.layers import CAVE, SURFACE  # noqa: E402
from game.systems import Controls, GameState, Machine  # noqa: E402
from tests.helpers import give  # noqa: E402

DT = 1 / 60


def run(g, seconds, controls=None):
    for _ in range(round(seconds / DT)):
        g.update(DT, controls or Controls())


def at_ramp(g, melt=True):
    """Põe o player no ponto de chegada da rampa da camada atual (no alcance do E). Na superfície a cratera
    nasce tampada de gelo (v0.4 M2): `melt` derrete ela antes (o atalho F4 de debug), pra dar pra descer."""
    if melt:
        g.debug_melt_crater()
    g.player.x, g.player.y = layers.ramp_arrival(g.world)
    return g.world.crater


def test_ramp_is_interactable_and_in_reach():
    g = GameState(rng=random.Random(1))
    tx, ty = at_ramp(g)
    hover = g.interactable_at((tx + 1.5) * C.TILE, (ty + 2.5) * C.TILE)
    assert hover == ("ramp", (tx, ty)) and g.in_reach(*hover)
    assert g.interaction() == ("ramp", (tx, ty))
    g.player.x += 6 * C.TILE
    assert not g.in_reach(*hover) and g.interaction() is None


def test_going_down_and_up():
    g = GameState(rng=random.Random(1))
    at_ramp(g)
    assert g.start_ramp() and ("ramp", CAVE) in g.pop_events()
    run(g, C.RAMP_SWITCH_AT / 2, Controls(move_x=1))
    assert g.layer == SURFACE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)   # parado no fade
    run(g, C.RAMP_SWITCH_AT / 2 + 0.05)
    assert g.layer == CAVE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)
    assert ("layer", CAVE) in g.pop_events()
    run(g, C.RAMP_DURATION)
    assert g.ramp is None
    assert g.start_ramp()
    run(g, C.RAMP_DURATION + 0.05)
    assert g.layer == SURFACE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)


def test_cannot_ramp_from_far_or_twice():
    g = GameState(rng=random.Random(1))
    assert not g.start_ramp()
    at_ramp(g)
    assert g.start_ramp() and not g.start_ramp()


def test_fainting_cancels_the_trip():
    g = GameState(rng=random.Random(1))
    at_ramp(g)
    g.start_ramp()
    g._faint()
    run(g, C.RAMP_DURATION)
    assert g.ramp is None and g.layer == SURFACE


def test_safe_point_points_to_the_ramp_in_the_cave():
    g = GameState(rng=random.Random(1))
    assert g.safe_point() == (*C.BASE_CENTER, "BASE")
    g.enter_layer(CAVE)
    tx, ty = g.world.crater
    assert g.safe_point() == ((tx + 1.5) * C.TILE, (ty + 3) * C.TILE, "RAMPA")


def test_player_facing_follows_direction():
    g = GameState(rng=random.Random(1))
    run(g, 0.1, Controls(move_x=-1))
    assert g.player.facing == "left"


# ---------------------------------------------------------------- luminária e drones
def cave_state():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    g.player.x, g.player.y = layers.ramp_arrival(g.world)
    return g


def test_lamp_recipe_is_cheap_unlocked_and_unpowered():
    from game import energy
    lamp = C.MACHINES["lamp"]
    assert lamp.cost == {"iron": 1, "silicon": 1} and lamp.unlock_ti == 0 and lamp.index is None
    assert C.MACHINE_CATEGORY["lamp"] == "light" and ("light", "Luz") in C.FAB_TABS
    assert energy.machine_use("lamp") == 0
    g = GameState(rng=random.Random(1))
    give(g, iron=1, silicon=1)
    assert g.recipe_status("lamp") == "ok" and g.craft("lamp") and g.inventory.count("lamp") == 1


def test_lamp_goes_on_both_layers_and_counts():
    g = GameState(rng=random.Random(1))
    give(g, lamp=2)
    px, py = g.player.tile
    assert g.place("lamp", (px + 2, py)) and g.lamps_placed == 1
    g.enter_layer(CAVE)
    g.player.x, g.player.y = layers.ramp_arrival(g.world)
    px, py = g.player.tile
    assert g.place("lamp", (px + 2, py)) and g.lamps_placed == 2
    assert g.machines[0].is_lamp and g.power.consumption == 0
    assert g.dismantle(g.machines[0]) and g.lamps_placed == 2          # só cresce


def test_no_drone_station_in_the_cave_but_drill_works():
    g = cave_state()
    give(g, drone_station=1)
    px, py = g.player.tile
    assert not g.can_place("drone_station", (px + 2, py + 1))
    g.enter_layer(SURFACE)
    g.player.x, g.player.y = C.SPAWN_POS
    px, py = g.player.tile
    assert g.can_place("drone_station", (px + 2, py))


# ---------------------------------------------------------------- luz e arte
def test_cave_lights_has_helmet_lamps_machines_ramp_and_terminals():
    from game.render import cave_lights
    g = cave_state()
    g.machines += [Machine("lamp", 60, 70), Machine("lamp", 62, 70), Machine("o2", 58, 70),
                   Machine("chest", 57, 70)]
    lights = cave_lights(g)
    head = lights[0]
    assert head.radius == 4 * C.TILE and head.y < g.player.y           # lanterna primeiro, na cabeça
    assert sum(L.radius == 5 * C.TILE for L in lights) == 2           # 2 luminárias
    assert len(lights) == 1 + 1 + 2 + 1 + len(g.world.terminals)      # + rampa + o2 + terminais (baú não)
    g.machines.append(Machine("drill", 50, 50, resource="iron", stored_init=C.DRILL_CAPACITY))
    assert len(cave_lights(g)) == len(lights)                         # drill cheia: parada, sem luz


def test_cave_fallback_sprites_have_contract_sizes():
    import pygame
    pygame.init()
    from game import art
    assert art.lamp().get_size() == C.LAMP_SPRITE_SIZE == (16, 32)
    assert art.lamp_icon().get_size() == (16, 16)
    assert art.cave_ramp_up().get_size() == (96, 96)


def test_save_mid_fade_keeps_the_destination():
    """Marco 4: salvou no meio do fade (antes da troca) -> o save já tem a camada de destino e a chegada."""
    from game import save
    g = GameState(rng=random.Random(1))
    at_ramp(g)
    g.start_ramp()
    run(g, C.RAMP_SWITCH_AT / 2)
    assert g.layer == SURFACE and not g.ramp.switched
    loaded = save.state_from_dict(save.state_to_dict(g))
    assert loaded.layer == CAVE and loaded.ramp is None
    assert (loaded.player.x, loaded.player.y) == layers.ramp_arrival(loaded.world)
    run(g, C.RAMP_DURATION)                                  # o jogo que estava rolando termina a viagem igual
    assert g.layer == CAVE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)
    # e subindo (a caverna já existe), também
    g.start_ramp()
    run(g, C.RAMP_SWITCH_AT / 2)
    loaded = save.state_from_dict(save.state_to_dict(g))
    assert loaded.layer == SURFACE and (loaded.player.x, loaded.player.y) == layers.ramp_arrival(loaded.world)
    # depois da troca (fim do fade) o save é o estado normal
    run(g, C.RAMP_SWITCH_AT / 2 + 0.05)
    loaded = save.state_from_dict(save.state_to_dict(g))
    assert loaded.layer == SURFACE == g.layer and (loaded.player.x, loaded.player.y) == (g.player.x, g.player.y)
