"""v0.8 M5 · Task 4 · Drone nv.2: tier no Drone, mais rápido e pega/solta mais depressa, pôr/tirar/desmontar
devolve o item certo, save `[resource, cargo, tier]` (o antigo de 2 elementos carrega tier 1) e o sprite do tier."""

import json
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import drones, save  # noqa: E402
from game.drones import CARRYING, LANDED  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from tests.helpers import build_now, give  # noqa: E402
from tests.test_drones import add_chest, add_drill, free_station_tile  # noqa: E402

ST = (60, 70)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def slot_of(game, item: str) -> int:
    return next(i for i, s in enumerate(game.inventory.slots) if s and s.item == item)


# ---------------------------------------------------------------- tier e números
def test_drone_defaults_to_tier_1_and_tier_2_is_faster():
    m = Machine("drone_station", *ST)
    m.station = drones.new_station(m)
    d1 = drones.dock(m, m.station)
    d2 = drones.dock(m, m.station, tier=2)
    assert d1.tier == 1 and d2.tier == 2
    assert d1.speed == C.DRONE_SPEED and d2.speed == C.DRONE_T2_SPEED
    assert d1.pickup_time == C.DRONE_PICKUP_TIME and d1.drop_time == C.DRONE_DROP_TIME
    assert d2.pickup_time == pytest.approx(C.DRONE_PICKUP_TIME * C.DRONE_T2_HANDLING)
    assert d2.drop_time == pytest.approx(C.DRONE_DROP_TIME * C.DRONE_T2_HANDLING)
    assert drones.item_of(d1) == "drone" and drones.item_of(d2) == C.DRONE_T2
    assert drones.tier_of("drone") == 1 and drones.tier_of(C.DRONE_T2) == 2 and drones.tier_of("iron") is None


def _trip_time(tier: int) -> float:
    """Segundos até o drone (sozinho na estação) entregar o lote num percurso fixo."""
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    st = Machine("drone_station", *ST)
    st.station = drones.new_station(st)
    drones.dock(st, st.station, tier=tier)
    g.machines.append(st)
    add_drill(g, 20, stored=12)
    chest = add_chest(g, (ST[0] - 20, ST[1]), receives={"iron"})
    step, t = 1 / 30, 0.0
    while chest.storage.count("iron") == 0:
        g._update_machines(step)
        t += step
        assert t < 120
    return t


def test_tier_2_arrives_first_on_a_fixed_route():
    t1, t2 = _trip_time(1), _trip_time(2)
    assert t2 < t1 * 0.75


def test_lift_ramp_follows_the_drone_speed():
    m = Machine("drone_station", *ST)
    m.station = drones.new_station(m)
    d = drones.dock(m, m.station, tier=2)
    d.state = CARRYING
    d.x += C.DRONE_T2_SPEED * C.TILE * drones.LIFT_TIME / 2      # metade da rampa do tier 2
    assert drones.lift(m, d) == pytest.approx(0.5)


# ---------------------------------------------------------------- pôr / tirar / desmontar
def test_dock_drone_t2_from_inventory_and_undock_returns_it(game):
    st = Machine("drone_station", *ST)
    st.station = drones.new_station(st)
    game.machines.append(st)
    give(game, drone=1, drone_t2=1)
    assert game.station_dock(st, slot_of(game, C.DRONE_T2)) == 1
    assert game.station_dock(st, slot_of(game, "drone")) == 1
    assert [(d.pad, d.tier) for d in st.station.drones] == [(0, 2), (1, 1)]
    assert game.drones_docked == 2                                  # conta os dois tiers
    assert game.inventory.count(C.DRONE_T2) == 0 and game.inventory.count("drone") == 0
    assert game.station_undock(st, 0)
    assert game.inventory.count(C.DRONE_T2) == 1 and game.inventory.count("drone") == 0
    assert game.station_undock(st, 1)
    assert game.inventory.count("drone") == 1


def test_dock_slot_with_held_drone_t2(game):
    st = Machine("drone_station", *ST)
    st.station = drones.new_station(st)
    game.machines.append(st)
    assert game.station_dock_slot(st, 3, C.DRONE_T2)
    assert st.station.drone_in(3).tier == 2
    assert game.station_dock_slot(st, 1)                            # sem item: o drone nv.1
    assert st.station.drone_in(1).tier == 1
    assert not game.station_dock_slot(st, 0, "iron")                # outro item não entra
    assert game.drones_docked == 2


def test_station_dock_refuses_other_items(game):
    st = Machine("drone_station", *ST)
    st.station = drones.new_station(st)
    game.machines.append(st)
    give(game, iron=5)
    assert game.station_dock(st, slot_of(game, "iron")) == 0


def test_dismantle_returns_each_tier(game):
    tile = free_station_tile(game)
    build_now(game, "drone_station", tile)
    st = game.stations[0]
    game.inventory.clear()
    give(game, drone=2, drone_t2=1)
    game.station_dock(st, slot_of(game, "drone"))
    game.station_dock(st, slot_of(game, C.DRONE_T2))
    out = game.dismantle_returns(st)
    assert out["drone"] == 2 and out[C.DRONE_T2] == 1
    assert game.dismantle(st)
    assert game.inventory.count("drone") == 2 and game.inventory.count(C.DRONE_T2) == 1


def test_dismantle_only_tier_2_has_no_drone_key(game):
    tile = free_station_tile(game)
    build_now(game, "drone_station", tile)
    st = game.stations[0]
    drones.dock(st, st.station, tier=2)
    out = game.dismantle_returns(st)
    assert "drone" not in out and out[C.DRONE_T2] == 1


# ---------------------------------------------------------------- save
def _two_tier_state() -> GameState:
    state = save.new_state()
    state.debug_add_ti()
    tile = free_station_tile(state)
    assert build_now(state, "drone_station", tile)
    st = state.stations[0]
    drones.dock(st, st.station, 0)
    d2 = drones.dock(st, st.station, 2, tier=2)
    d2.resource, d2.cargo = "ice", 5
    return state


def test_save_roundtrip_keeps_the_tier(tmp_path):
    path = tmp_path / "slot1.json"
    assert save.write_save(_two_tier_state(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    saved = next(m for m in data["layers"]["surface"]["machines"] if m["kind"] == "drone_station")
    assert saved["drones"] == [[None, 0, 1], None, ["ice", 5, 2], None]
    st = save.load_game(path).stations[0]
    assert [(d.pad, d.tier) for d in st.station.drones] == [(0, 1), (2, 2)]
    assert st.station.drone_in(2).cargo == 5 and st.station.drone_in(2).state == LANDED


def test_old_two_element_slot_loads_as_tier_1():
    m = save.machine_to_dict(_two_tier_state().stations[0])
    m["drones"] = [["iron", 3], None, [None, 0], None]
    loaded = save.machine_from_dict(m)
    assert [(d.pad, d.tier, d.cargo) for d in loaded.station.drones] == [(0, 1, 3), (2, 1, 0)]


def test_bad_tier_in_save_falls_back_to_1():
    m = save.machine_to_dict(_two_tier_state().stations[0])
    m["drones"] = [[None, 0, 7], None, None, None]
    assert save.machine_from_dict(m).station.drones[0].tier == 1


# ---------------------------------------------------------------- render
@pytest.fixture
def renderer():
    pygame.init()
    pygame.display.set_mode((64, 64))
    from game.assets import Sprites
    from game.render import Renderer
    return Renderer(Sprites())


def test_drone_frame_tier_2_comes_from_drone_t2(renderer):
    sheet = renderer.sprites.get("drone_t2")
    assert sheet is not None and sheet.get_size() == (64, 16)
    f2 = renderer.drone_frame(0, 1, tier=2)
    assert f2.get_size() == (C.DRONE_SPRITE, C.DRONE_SPRITE)
    assert pygame.image.tobytes(f2, "RGBA") == pygame.image.tobytes(sheet.subsurface((16, 0, 16, 16)), "RGBA")
    f1 = renderer.drone_frame(0, 1)
    assert pygame.image.tobytes(f1, "RGBA") != pygame.image.tobytes(f2, "RGBA")


def test_drone_frame_tier_2_falls_back_to_drone(renderer):
    renderer.sprites._cache["drone_t2"] = None
    renderer._surfaces.pop("drone_t2", None)
    f2 = renderer.drone_frame(0, 0, tier=2)
    f1 = renderer.drone_frame(0, 0)
    assert pygame.image.tobytes(f2, "RGBA") == pygame.image.tobytes(f1, "RGBA")


def test_item_icon_drone_t2_uses_its_png(renderer):
    small = renderer.sprites.get("icon_drone_t2")
    assert small is not None
    icon = renderer.item_icon(C.DRONE_T2)
    assert icon.get_size() == (32, 32)
    assert pygame.image.tobytes(icon, "RGBA") == pygame.image.tobytes(pygame.transform.scale_by(small, 2), "RGBA")
