"""Magmatita (v0.4 · bíblia §12): recurso novo, rochas só em volta das fumarolas, receita do Aquecedor, objetivo."""

import json

import pytest

from game import config as C
from game import magmatite
from game import save
from game import surface_gen
from game.objectives import OBJECTIVES, MAGMATITE_HINT, ObjectiveTracker, current_index
from game.systems import GameState, Machine
from tests.helpers import from_192, give

SEEDS = (1, 7, 42)


@pytest.fixture(scope="module")
def worlds():
    return {seed: surface_gen.generate_surface(seed) for seed in SEEDS}


def magma_tiles(world) -> list[tuple[int, int]]:
    return [(x, y) for y in range(world.height) for x in range(world.width) if world.tiles[y][x] == C.SMALL_MAGMATITE]


# ---------------------------------------------------------------- o recurso em todas as listas
def test_resource_is_in_every_list():
    r = "magmatite"
    assert r in C.RESOURCES and r in C.LOGISTIC_ITEMS
    assert C.RESOURCE_NAME[r] == "magmatita" and C.RESOURCE_LABEL[r] == "MAGMATITA"
    assert C.ORE_COLORS[r][0] == "#ff7a2e"
    assert C.SMALL_ROCKS[C.SMALL_MAGMATITE] == r and C.TILE_RESOURCE[C.SMALL_MAGMATITE] == r
    assert C.SMALL_MAGMATITE in C.FLAT_SOLIDS and C.SMALL_MAGMATITE in C.MINE_TIME
    assert C.DROP_RANGE[C.SMALL_MAGMATITE] == (2, 4)
    assert r not in C.VEIN_RESOURCES                     # sem veio: o sorteio dos veios não muda
    from game import minimap
    assert minimap.TILE_COLORS[C.SMALL_MAGMATITE] == minimap.TILE_COLORS[C.SMALL_IRON]   # como as outras rochas
    from game.ui import item_category, item_name
    assert item_name(r) == "Magmatita" and item_category(r)[0] == "RECURSO"


def test_sprites_exist():
    for name in ("icon_magmatite", "ore_magmatite", "pickup_magmatite", "rock_small_magmatite_0",
                 "rock_small_magmatite_1"):
        assert (C.SPRITES_DIR / f"{name}.png").exists(), name


def test_stacks_like_a_resource():
    g = GameState(1)
    give(g, magmatite=60)
    assert g.inventory.count("magmatite") == 60
    assert sorted(s.count for s in g.inventory.slots if s) == [10, 50]


# ---------------------------------------------------------------- onde nasce
def test_rocks_only_around_vents_never_on_footprint_basin_or_blocking(worlds):
    for seed, w in worlds.items():
        rings = set()
        for v in w.geo.vents:
            rings |= set(magmatite.ring_tiles(v))
        rocks = magma_tiles(w)
        assert rocks, seed
        for x, y in rocks:
            assert (x, y) in rings, (seed, x, y)
            assert (x, y) not in w.keep_clear                  # nem pegada nem halo das formações
            assert w.geo.basin_at(x, y) < 0                    # nunca na bacia
            assert w.vein_at(x, y) is None
            neighbors = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
            assert not any(w.is_solid(*t) for t in neighbors), (seed, x, y)   # não fecha passagem


def test_ring_is_outside_the_footprint_and_halo(worlds):
    for v in worlds[7].geo.vents:
        ring = set(magmatite.ring_tiles(v))
        assert not ring & set(v.box)
        lo, hi = C.MAGMATITE_RING
        assert lo > C.FORMATION_HALO and lo <= hi


def test_dormant_vent_has_enough_for_the_first_heater(worlds):
    cost = C.MACHINES["heater"].cost["magmatite"]
    low = C.DROP_RANGE[C.SMALL_MAGMATITE][0]
    for seed, w in worlds.items():
        assert w.geo.vents, seed
        for v in w.geo.vents:
            n = len(magmatite.rocks_around(w, v))
            assert n >= C.MAGMATITE_DORMANT[0], (seed, v.kind, n)
            assert n * low >= cost                              # mesmo no pior sorteio do drop
        assert len(magma_tiles(w)) * low >= cost


def test_world_still_walkable_to_every_rock(worlds):
    w = worlds[1]
    reach = w.reachable_from(C.BASE_TILE)
    for x, y in magma_tiles(w):
        assert any((x + dx, y + dy) in reach for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)))


def test_deterministic_and_does_not_touch_the_other_rocks(monkeypatch):
    a = surface_gen._build(42)
    b = surface_gen._build(42)
    assert a.tiles == b.tiles
    monkeypatch.setattr(magmatite, "place_initial", lambda world: [])
    plain = surface_gen._build(42)
    diff = [(x, y) for y in range(a.height) for x in range(a.width) if a.tiles[y][x] != plain.tiles[y][x]]
    assert diff and all(a.tiles[y][x] == C.SMALL_MAGMATITE and plain.tiles[y][x] == C.SAND for x, y in diff)
    assert [(v.resource, v.tx, v.ty) for v in a.veins] == [(v.resource, v.tx, v.ty) for v in plain.veins]


# ---------------------------------------------------------------- reaparecimento
def _respawn_until(g, awake: bool, seconds: float, step: float = 5.0) -> None:
    surface = g.surface
    surface.vents_awake = [awake] * len(surface.geo.vents)
    far = (C.BASE_TILE[0] * C.TILE, C.BASE_TILE[1] * C.TILE)      # o player na base, longe das fumarolas
    t = 0.0
    while t < seconds:
        magmatite.respawn(surface.world, surface.vents_awake, surface.rocks.vent_timers, g.magma_rng, step, far)
        t += step


def test_awake_vent_expels_more_and_faster():
    g = GameState(7)
    w = g.surface.world
    vents = g.surface.geo.vents
    rings = [set(magmatite.ring_tiles(v)) for v in vents]
    k = next(i for i, r in enumerate(rings) if not any(r & o for j, o in enumerate(rings) if j != i))
    vent = vents[k]                                                  # uma fumarola sem anel dividido com outra
    for t in magmatite.rocks_around(w, vent):                       # quebrou todas as dela
        w.set(*t, C.SAND)
    _respawn_until(g, awake=False, seconds=C.MAGMATITE_DORMANT_RESPAWN - 10)
    assert len(magmatite.rocks_around(w, vent)) == 0                 # dormente: devagar
    _respawn_until(g, awake=False, seconds=C.MAGMATITE_DORMANT_RESPAWN * 6)
    dormant = len(magmatite.rocks_around(w, vent))
    assert dormant == C.MAGMATITE_DORMANT_MAX                        # volta até o teto da dormente e para
    _respawn_until(g, awake=True, seconds=C.MAGMATITE_AWAKE_RESPAWN * 20)
    awake = len(magmatite.rocks_around(w, vent))
    assert awake == C.MAGMATITE_AWAKE_MAX and awake > dormant
    assert C.MAGMATITE_AWAKE_RESPAWN < C.MAGMATITE_DORMANT_RESPAWN
    assert C.MAGMATITE_AWAKE_MAX > C.MAGMATITE_DORMANT_MAX >= C.MAGMATITE_DORMANT[1]


def test_respawn_never_under_the_player_and_respects_the_rules():
    g = GameState(1)
    w = g.surface.world
    vent = g.surface.geo.vents[0]
    for t in magmatite.rocks_around(w, vent):
        w.set(*t, C.SAND)
    ring = magmatite.ring_tiles(vent)
    px, py = ring[len(ring) // 2]
    player = ((px + 0.5) * C.TILE, (py + 0.5) * C.TILE)
    g.surface.vents_awake = [True] * len(g.surface.geo.vents)
    born = []
    for _ in range(100):
        born += magmatite.respawn(w, g.surface.vents_awake, g.surface.rocks.vent_timers, g.magma_rng, 5.0, player)
    assert born
    for x, y in born:
        assert max(abs(x - px), abs(y - py)) > 1
        assert w.geo.basin_at(x, y) < 0 and (x, y) not in w.keep_clear


def test_game_loop_spawns_magmatite_and_general_cap_ignores_it():
    from game import rock_respawn
    g = GameState(7)
    before = rock_respawn.count(g.surface.world)
    g.surface.vents_awake = [True] * len(g.surface.geo.vents)
    for _ in range(40):
        g._update_rocks(C.MAGMATITE_AWAKE_RESPAWN)
    spawned = [e for e in g.events if e[0] == "rock_spawn"
               and g.surface.world.get(*e[1]) == C.SMALL_MAGMATITE]
    assert spawned
    # a magmatita não entra no teto das outras rochas
    assert rock_respawn.count(g.surface.world) - before == len([e for e in g.events if e[0] == "rock_spawn"]) - len(spawned)


def test_mining_a_magmatite_rock_gives_magmatite():
    g = GameState(1)
    w = g.surface.world
    x, y = magma_tiles(w)[0]
    g._break_tile((x, y), C.SMALL_MAGMATITE)
    assert 2 <= g.inventory.count("magmatite") <= 4 and g.mined_total["magmatite"] == g.inventory.count("magmatite")
    assert w.get(x, y) == C.SAND


# ---------------------------------------------------------------- receita
def test_heater_recipes_charge_magmatite():
    assert C.MACHINES["heater"].cost["magmatite"] == 3
    assert C.MACHINES["heater_t2"].cost["magmatite"] == 10
    g = GameState(1)
    g.indices["o2"] = 500
    give(g, constructor=1, iron=50, silicon=50)
    px, py = g.player.tile
    assert g.build_status("heater") == "missing"
    assert not g.build("heater", (px + 2, py))
    give(g, magmatite=5)
    assert g.build_status("heater") == "ok" and g.build("heater", (px + 2, py))
    assert g.inventory.count("magmatite") == 2


# ---------------------------------------------------------------- objetivo
def test_objective_right_before_the_heater_with_the_hint():
    texts = [o.text for o in OBJECTIVES]
    i = texts.index("Encontre magmatita no basalto (oeste)")
    assert texts[i - 1] == "Chegue a Ti 500" and texts[i + 1] == "Construa um Aquecedor"
    assert OBJECTIVES[i].hint == MAGMATITE_HINT
    assert MAGMATITE_HINT == "Os sensores detectaram calor a oeste. Talvez exista algo por lá pra gerar calor."


def _state_at_magmatite_objective() -> GameState:
    g = GameState(1)
    g.mined_total.update(iron=10, silicon=4)
    g.fabricator_opened = True
    g.crafted.update(constructor=1, o2=1, chest=1, melter=1)
    g.surface.machines.append(Machine("o2", *from_192(93, 98)))
    g.indices["o2"] = 500
    return g


def test_objective_completes_on_first_magmatite_and_shows_hint_once():
    g = _state_at_magmatite_objective()
    i = current_index(g)
    assert OBJECTIVES[i].text == "Encontre magmatita no basalto (oeste)"
    tracker = ObjectiveTracker(g)
    tracker.update(g, 0.1)
    assert tracker.take_hint() == MAGMATITE_HINT
    assert tracker.take_hint() is None                                   # uma vez só
    g.mined_total["magmatite"] = 2
    tracker.update(g, 0.1)
    assert OBJECTIVES[current_index(g)].text == "Construa um Aquecedor"


def test_old_progress_with_heater_does_not_go_back():
    g = _state_at_magmatite_objective()
    g.crafted["heater"] = 1                                               # save de antes da magmatita
    assert OBJECTIVES[current_index(g)].text != "Encontre magmatita no basalto (oeste)"
    assert current_index(g) > [o.text for o in OBJECTIVES].index("Construa um Aquecedor")


# ---------------------------------------------------------------- save
def test_save_round_trip_keeps_magmatite():
    g = GameState(7)
    give(g, magmatite=7)
    g.mined_total["magmatite"] = 9
    g.surface.rocks.vent_timers = [3.0, 50.0]
    back = save.state_from_dict(json.loads(json.dumps(save.state_to_dict(g))))
    assert back.inventory.count("magmatite") == 7 and back.mined_total["magmatite"] == 9
    assert back.surface.rocks.vent_timers == [3.0, 50.0]


def test_old_save_without_magmatite_fields_loads():
    g = GameState(7)
    give(g, iron=5)
    data = json.loads(json.dumps(save.state_to_dict(g)))
    del data["progress"]["mined_total"]["magmatite"]
    del data["progress"]["drill_collected"]["magmatite"]
    del data["layers"]["surface"]["rocks"]["vents"]
    # uma máquina que estava em cima de onde agora nasce uma rocha de magmatita
    x, y = magma_tiles(g.surface.world)[0]
    data["layers"]["surface"]["machines"].append({"kind": "o2", "tx": x, "ty": y, "rotation": 0})
    back = save.state_from_dict(save.migrate(data))
    assert back.mined_total["magmatite"] == 0 and back.inventory.count("iron") == 5
    assert back.surface.rocks.vent_timers == []
    assert back.surface.world.get(x, y) == C.SAND                        # a rocha nova não fica embaixo da máquina


def test_logistics_accept_magmatite():
    from game import drones
    chest = Machine("chest", 90, 90)
    assert drones.can_receive(chest, "magmatite") and drones.can_send(chest, "magmatite")


def test_hint_card_goes_below_the_left_column_and_wraps():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.font.init()
    from game.ui import UI
    ui = UI()
    ui.hud_rects = []
    ui.left_bottom, ui.gust_rect, ui.thaw_rect = 80, None, pygame.Rect(6, 84, 100, 15)
    ui.draw_objective_hint(MAGMATITE_HINT, 1.0)
    rect = ui.hud_rects[-1]
    assert rect.top == 84 + 15 + 4 and rect.width == ui.objective_w and rect.height > 20   # várias linhas
