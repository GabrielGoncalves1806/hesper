"""v0.4 Marco 3 · M3.4: máquina submersa e água como obstáculo de construção (bíblia §12, "Máquina submersa").

Não dá pra construir na água (`can_place` olha o `world.is_water`). Uma máquina que estava num tile seco de bacia e
alagou quando o lago subiu fica com `m.submerged = True` (derivado, não vai no save): para tudo (índice, energia,
drill, drones) e solta um ("submerged", kind, tile) uma vez só. Desmontar continua normal."""

import math
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import drones, save  # noqa: E402
from game.drones import LANDED  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from tests.helpers import build_now, give  # noqa: E402


def mist_state() -> GameState:
    s = GameState(rng=random.Random(1))
    s.stage = C.MIST_STAGE
    return s


def flood(s: GameState, k: int = 0) -> None:
    """Sobe o lago até a marca L(k+1) (índice de água) e reaplica o derretimento."""
    s.indices["water"] = max(s.indices["water"], C.LAKE_WATER[k])
    s._apply_thaw()


def wet_at(world, level: float) -> list[tuple[int, int]]:
    """Tiles que viram água no nível `level`, do mais perto da base pro mais longe."""
    old = world.water_level
    world.water_level = level
    wet = [(x, y) for y in range(world.height) for x in range(world.width) if world.is_water(x, y, C.GREEN_STAGE)]
    world.water_level = old
    bx, by = C.BASE_TILE
    return sorted(wet, key=lambda t: math.hypot(t[0] - bx, t[1] - by))


def stand_near(s: GameState, tile: tuple[int, int], dy: int = -3) -> None:
    """Põe o player a 3 tiles do `tile` (no alcance de colocar/desmontar, sem encostar na máquina)."""
    s.player.x, s.player.y = (tile[0] + 0.5) * C.TILE, (tile[1] + dy + 0.5) * C.TILE


def submerged_events(s: GameState) -> list[tuple]:
    return [e for e in s.pop_events() if e[0] == "submerged"]


def basin_tile(s: GameState) -> tuple[int, int]:
    """Um tile de chão de bacia que alaga em L1 (seco antes disso), longe da base."""
    return wet_at(s.surface.world, C.GEO_LEVELS[0])[0]


# ---------------------------------------------------------------- não constrói na água
def test_can_place_refuses_a_water_tile():
    s = mist_state()
    flood(s)
    tile = basin_tile(s)
    give(s, constructor=1, iron=10, silicon=4)
    stand_near(s, tile)
    assert s.surface.world.is_water(*tile, s.stage)
    assert not s.can_place("o2", tile)
    assert not s.build("o2", tile)
    assert s.inventory.count("iron") == 10


def test_can_place_on_the_same_tile_while_it_is_dry():
    s = mist_state()
    tile = basin_tile(s)
    stand_near(s, tile)
    assert s.can_place("o2", tile)                     # bacia seca: dá pra construir (e alagar depois)


def test_can_place_refuses_when_any_tile_of_a_big_machine_is_water():
    s = mist_state()
    flood(s)
    world = s.surface.world
    for tx, ty in wet_at(world, C.GEO_LEVELS[0]):      # estação 2×2 com só um canto na água (margem)
        corner = (tx - 1, ty - 1)
        tiles = [(corner[0] + dx, corner[1] + dy) for dy in (0, 1) for dx in (0, 1)]
        dry = [t for t in tiles if world.is_floor(*t) and not world.is_water(*t, s.stage) and not world.vein_at(*t)]
        if len(dry) == 3:
            break
    else:
        pytest.skip("sem margem com 3 tiles secos")
    stand_near(s, corner, dy=-4)
    assert not s.can_place("drone_station", corner)


# ---------------------------------------------------------------- alaga depois
def test_machine_in_a_dry_basin_floods_later_and_fires_once():
    s = mist_state()
    tile = basin_tile(s)
    stand_near(s, tile)
    assert build_now(s, "o2", tile)
    m = s.machine_at(tile)
    s._apply_thaw()
    assert not m.submerged and not submerged_events(s)
    flood(s)
    assert m.submerged
    assert submerged_events(s) == [("submerged", "o2", tile)]
    flood(s, 2)                                         # o lago sobe mais: o evento não repete
    s._update_machines(0.1)
    assert m.submerged and not submerged_events(s)


def test_base_never_floods():
    s = mist_state()
    bx, by = C.BASE_TILE
    near = [(x, y) for y in range(by - 16, by + 17) for x in range(bx - 16, bx + 17)
            if math.hypot(x - bx, y - by) <= 16]
    flood(s, 2)
    world = s.surface.world
    assert not any(world.is_water(x, y, C.GREEN_STAGE) for x, y in near)
    m = Machine("o2", bx + 3, by + 2)
    s.machines.append(m)
    s._apply_thaw()
    assert not m.submerged


def test_cave_machines_never_flood():
    s = mist_state()
    s.enter_layer("cave")
    m = Machine("o2", 10, 10)
    s.machines.append(m)
    flood(s, 2)
    assert not m.submerged


# ---------------------------------------------------------------- submersa para tudo
def flooded_machine(kind: str) -> tuple[GameState, Machine]:
    s = mist_state()
    tile = basin_tile(s)
    m = Machine(kind, *tile)
    s.machines.append(m)
    flood(s)
    assert m.submerged
    s.pop_events()
    return s, m


def test_submerged_machine_adds_no_index():
    s, m = flooded_machine("o2")
    before = s.indices["o2"]
    s._update_machines(10.0)
    assert s.indices["o2"] == before
    assert s.ti_rate == 0


def test_submerged_machine_uses_no_power():
    s, m = flooded_machine("heater")
    assert s.power.consumption == 0


def test_submerged_solar_panel_makes_no_power():
    s, m = flooded_machine("solar")
    assert s.power.production == C.POD_POWER


def test_submerged_drill_does_not_dig():
    s = mist_state()
    vein = s.surface.world.veins[0]
    d = Machine("drill", vein.tx, vein.ty, resource=vein.resource)
    s.machines.append(d)
    d.submerged = True                                  # veio fica seco no lago de verdade: aqui é forçado
    s._update_machines(C.DRILL_INTERVAL * 5)
    assert d.stored == 0
    assert s.power.consumption == 0


def test_submerged_station_does_not_send_drones():
    s = mist_state()
    tile = basin_tile(s)
    st = Machine("drone_station", *tile)
    st.station = drones.new_station(st, 1)
    s.machines.append(st)
    bx, by = C.BASE_TILE                                # baús perto da base: nunca alagam
    src = Machine("chest", bx + 4, by + 3, sends={"iron"})
    dst = Machine("chest", bx + 6, by + 3, receives={"iron"})
    src.storage.add("iron", 10)
    s.machines += [src, dst]
    flood(s)
    assert st.submerged
    for _ in range(300):
        s._update_machines(1 / 30)
    assert all(d.state == LANDED for d in st.station.drones)
    assert src.storage.count("iron") == 10 and dst.storage.count("iron") == 0


def test_dry_station_still_works_next_to_a_flooded_one():
    s = mist_state()
    bx, by = C.BASE_TILE
    st = Machine("drone_station", bx - 5, by + 3)
    st.station = drones.new_station(st, 1)
    s.machines.append(st)
    wet = Machine("drone_station", *basin_tile(s))
    wet.station = drones.new_station(wet, 1)
    s.machines.append(wet)
    src = Machine("chest", bx + 4, by + 3, sends={"iron"})
    dst = Machine("chest", bx + 6, by + 3, receives={"iron"})
    src.storage.add("iron", 10)
    s.machines += [src, dst]
    flood(s)
    assert not st.submerged and wet.submerged
    for _ in range(600):
        s._update_machines(1 / 30)
    assert dst.storage.count("iron") > 0


# ---------------------------------------------------------------- desmontar
def test_dismantle_a_submerged_machine_returns_it():
    s, m = flooded_machine("o2")
    stand_near(s, (m.tx, m.ty))
    assert s.dismantle(m)
    assert m not in s.machines and s.inventory.count("iron") == C.MACHINES["o2"].cost["iron"]   # a receita


# ---------------------------------------------------------------- derivado: fora do save
def test_submerged_is_derived_on_load_without_events():
    s, m = flooded_machine("o2")
    data = save.state_to_dict(s)
    assert "submerged" not in str(data)
    loaded = save.state_from_dict(data)
    lm = next(x for x in loaded.surface.machines if (x.tx, x.ty) == (m.tx, m.ty))
    assert lm.submerged
    assert not [e for e in loaded.events if e[0] == "submerged"]


# ---------------------------------------------------------------- aviso e dica (App)
def test_submerged_notice_text_agrees_with_the_machine():
    from game.ui import submerged_notice
    assert submerged_notice(["o2"]) == f"Gerador de O₂ submerso · segure [{C.DISMANTLE_KEY}]"
    assert submerged_notice(["lamp"]) == f"Luminária submersa · segure [{C.DISMANTLE_KEY}]"
    assert submerged_notice(["o2", "heater", "lamp"]) == f"3 máquinas submersas · segure [{C.DISMANTLE_KEY}]"
    assert C.DISMANTLE_KEY == "Clique direito"          # o verbo que a dica de desmontar já usa


@pytest.fixture(scope="module")
def app():
    import tempfile
    from pathlib import Path

    import pygame

    from game import settings
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_submerged_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def test_floods_together_make_one_grouped_notice(app):
    from game.ui import submerged_notice
    app.thaw_notice, app.thaw_notice_time = None, 0.0
    app.on_game_event(("submerged", "o2", (1, 1)))
    assert app.thaw_notice == submerged_notice(["o2"])
    app.on_game_event(("submerged", "heater", (2, 1)))
    app.on_game_event(("submerged", "lamp", (3, 1)))
    assert app.thaw_notice == submerged_notice(["o2", "heater", "lamp"])
    app.thaw_notice_time = 0.0                          # o aviso saiu: o próximo conta do zero
    app.on_game_event(("submerged", "solar", (4, 1)))
    assert app.thaw_notice == submerged_notice(["solar"])


def test_submerged_machine_hint_says_submersa(app):
    s = app.state
    m = Machine("o2", 40, 40)
    m.submerged = True
    s.machines.append(m)
    try:
        app.placing = None
        app.hovered_machine = lambda: m
        app.e_target = lambda: None
        assert app.hint().startswith("Submersa")
    finally:
        s.machines.remove(m)
        del app.hovered_machine, app.e_target


def test_render_draws_only_the_top_half_with_a_waterline(app):
    r = app.renderer
    for kind in ("o2", "heater", "chest", "drone_station", "lamp", "drill"):
        m = Machine(kind, 40, 40)
        sprite, _ = r.machine_still(m)
        sub = r.submerged_surface(m)
        assert sub.get_size() == sprite.get_size() and sub.get_flags() & pygame.SRCALPHA
        box = sprite.get_bounding_rect(40)
        cut = box.top + box.height // 2
        w, h = sub.get_size()
        assert all(sub.get_at((x, y)).a == 0 for y in range(cut + 1, h) for x in range(w))   # embaixo: nada
        foam = pygame.Color(C.PALETTES["dead"]["foam"])
        assert any(sub.get_at((x, cut - 1))[:3] == foam[:3] for x in range(w))              # a linha d'água


def test_placing_over_water_hint(app):
    s = app.state
    tile = (50, 50)
    old = s.world.is_water
    s.world.is_water = lambda x, y, stage: (x, y) == tile
    try:
        app.placing = "o2"
        app.place_target = lambda: tile
        assert app.hint().startswith("Não dá pra construir na água")
    finally:
        app.placing = None
        del s.world.is_water, app.place_target
        assert s.world.is_water == old
