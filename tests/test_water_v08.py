"""v0.8 M2: Dispersor proporcional à base, cápsula vazia e coletor de água."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game.systems import dispenser_capsule_time  # noqa: E402
from tests.test_base import demo_base, run  # noqa: E402,F401
from tests.test_base import game  # noqa: E402,F401  (fixture)


@pytest.mark.parametrize("floor, want", [(25, 180.0), (9, 360.0), (100, 45.0), (200, 30.0), (50, 90.0)])
def test_capsule_time_scales_with_the_base(floor, want):
    assert dispenser_capsule_time(floor) == pytest.approx(want)


def test_capsule_time_limits():
    assert dispenser_capsule_time(1) == C.DISPENSER_TIME_MAX
    assert dispenser_capsule_time(10_000) == C.DISPENSER_TIME_MIN


def test_dispenser_dries_after_the_time_of_a_10x10_base(game):
    d, x0, y0 = demo_base(game, w=10, h=10, water=1)
    assert len(game.seal_of(d).floor) == 100
    run(game, 44)
    assert game.dispenser_state(d) == "sealed"
    run(game, 2)                                                  # 45 s na 10×10
    assert game.dispenser_state(d) == "dry"


# ---------------------------------------------------------------- Task 2: cápsula vazia e o 2º slot do Dispersor
from game import drones, save  # noqa: E402
from game.inventory import Stack, max_stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from tests.helpers import give  # noqa: E402


@pytest.fixture
def sealed_base(game):
    """Base vedada 5×5 (25 tiles de chão) com 1 Dispersor ligado. Devolve (state, dispersor)."""
    d, x0, y0 = demo_base(game, w=5, h=5)
    assert len(game.seal_of(d).floor) == 25
    return game, d


def test_empty_capsule_is_an_item():
    item = C.MACHINES[C.EMPTY_CAPSULE]
    assert item.name == "Cápsula vazia" and not item.placeable and item.sprite == "icon_water_capsule_empty"
    assert max_stack(C.EMPTY_CAPSULE) == max_stack("water_capsule") == C.STACK_MACHINE
    assert C.EMPTY_CAPSULE in C.LOGISTIC_ITEMS and C.DISPENSER_SLOTS == 2 and C.DISPENSER_EMPTY_SLOT == 1


def test_burned_capsule_becomes_an_empty_one(sealed_base):
    state, disp = sealed_base
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 2)
    run(state, 181)                                             # a 1ª queimou inteira (180 s na 5×5)
    assert disp.storage.count(C.EMPTY_CAPSULE) == 1


def test_full_empty_slot_never_stops_the_air(sealed_base):
    state, disp = sealed_base
    disp.storage.slots[C.DISPENSER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, C.STACK_MACHINE)
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 2)
    run(state, 181)
    assert state.dispenser_state(disp) == "sealed"                # ainda sopra (a 2ª tá queimando)
    assert disp.storage.count(C.EMPTY_CAPSULE) == C.STACK_MACHINE  # a vazia que não coube sumiu


def test_last_capsule_also_leaves_an_empty_one_and_goes_dry(sealed_base):
    state, disp = sealed_base
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 1)
    run(state, 181)
    assert state.dispenser_state(disp) == "dry" and disp.storage.count(C.EMPTY_CAPSULE) == 1


def test_player_cannot_put_an_empty_capsule_in_the_dispenser(sealed_base):
    state, disp = sealed_base
    give(state, **{C.EMPTY_CAPSULE: 1})
    index = next(i for i, s in enumerate(state.inventory.slots) if s and s.item == C.EMPTY_CAPSULE)
    assert state.dispenser_put(disp, index) == 0


def test_drones_take_empties_from_the_dispenser():
    disp = Machine(C.DISPENSER, 0, 0)
    assert drones.can_send(disp, C.EMPTY_CAPSULE) and not drones.can_send(disp, "water_capsule")
    assert drones.can_receive(disp, "water_capsule") and not drones.can_receive(disp, C.EMPTY_CAPSULE)


def test_dispenser_save_roundtrip_with_empties():
    m = Machine(C.DISPENSER, 3, 3)
    m.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 1)
    m.storage.slots[C.DISPENSER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    back = save.machine_from_dict(save.machine_to_dict(m))
    assert back.storage.count(C.EMPTY_CAPSULE) == 2 and back.capsules == 1


def test_v14_dispenser_with_one_slot_loads_with_the_empty_slot_free():
    data = save.machine_to_dict(Machine(C.DISPENSER, 3, 3))
    data["storage"] = [["water_capsule", 2]]
    back = save.machine_from_dict(data)
    assert back.capsules == 2 and back.storage.slots[C.DISPENSER_EMPTY_SLOT] is None


def test_dispenser_save_does_not_accept_a_full_capsule_in_the_empty_slot():
    data = save.machine_to_dict(Machine(C.DISPENSER, 3, 3))
    data["storage"] = [None, ["water_capsule", 2]]
    assert save.machine_from_dict(data).storage.slots[C.DISPENSER_EMPTY_SLOT] is None


def test_v14_to_v15_migration_registered():
    assert save.SAVE_VERSION >= 15 and 14 in save.MIGRATIONS     # (o v16 é do M3, ver test_cultivator_v08)
    data = {"version": 14, "x": 1}
    assert save.MIGRATIONS[14](dict(data)) == data


# ---------------------------------------------------------------- Task 3: Coletor de água
from game.layers import CAVE  # noqa: E402
from game.systems import collector_time  # noqa: E402
from tests.helpers import build_now  # noqa: E402
from tests.test_base import free_spot, stand_at  # noqa: E402


def make_collector(state, tile=(70, 70), empties=3, **kw):
    """Coletor na camada ativa (a máquina nasce pronta), com `empties` vazias na entrada."""
    m = Machine(C.COLLECTOR, *tile, **kw)
    if empties:
        m.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, empties)
    state.machines.append(m)
    return m


def tick(state, seconds, step=1 / 30):
    """Só as máquinas (sem a chuva sorteada do update inteiro, que acelera o coletor)."""
    for _ in range(round(seconds / step)):
        state._update_machines(step)


def at_stage(state, stage):
    state.stage = stage


def test_collector_is_registered():
    t = C.MACHINES[C.COLLECTOR]
    assert t.name == "Coletor de água" and t.desc == "umidade → cápsula" and t.placeable and t.index is None
    assert t.cost == {"iron_ingot": 3, "silicon": 6} and t.unlock_ti == 10_000 and t.sprite == "machine_water_collector"
    assert C.POWER_USE[C.COLLECTOR] == 1 and C.MACHINE_CATEGORY[C.COLLECTOR] == "automation"
    assert C.MACHINE_ORDER.index(C.COLLECTOR) == C.MACHINE_ORDER.index(C.SMELTER) + 1
    assert C.COLLECTOR not in C.MACHINE_FEMININE
    assert (C.COLLECTOR_IN_SLOT, C.COLLECTOR_OUT_SLOT, C.COLLECTOR_SLOTS) == (0, 1, 2)


def test_collector_can_be_built(game):
    x0, y0 = free_spot(game, 4, 4)
    stand_at(game, x0 + 1, y0 + 1)
    m = build_now(game, C.COLLECTOR, (x0, y0))
    assert m is not None and m.is_collector and len(m.storage) == 2 and m.is_logistic and m.needs_chip
    assert game.power.consumption >= 1


def test_collector_fills_an_empty_in_40s(game):
    at_stage(game, C.MIST_STAGE)
    m = make_collector(game)
    tick(game, C.COLLECTOR_TIME - 1)
    assert m.storage.count("water_capsule") == 0 and m.timer > 0
    tick(game, 2)
    assert m.storage.count("water_capsule") == 1 and m.storage.count(C.EMPTY_CAPSULE) == 2
    assert any(e[0] == "collector_done" for e in game.events)


def test_collector_waits_for_the_humid_stage():
    game = GameState(rng=random.Random(5))                        # sem o Ti do debug: o estágio não sobe sozinho
    at_stage(game, C.ARID_STAGE)
    m = make_collector(game)
    assert game.collector_blocker(m, game.active) == "stage"
    tick(game, C.COLLECTOR_TIME + 0.5)
    assert m.storage.count("water_capsule") == 0 and m.timer == 0
    at_stage(game, C.MIST_STAGE)
    assert game.collector_blocker(m, game.active) is None


def test_rain_makes_it_faster():
    assert collector_time(0.0) == pytest.approx(C.COLLECTOR_TIME)
    assert collector_time(1.0) == pytest.approx(C.COLLECTOR_TIME / 3)
    assert collector_time(5.0) == pytest.approx(C.COLLECTOR_TIME / 3)        # limitada a 1


def test_collector_uses_the_rain_of_the_surface(game):
    at_stage(game, C.MIST_STAGE)
    m = make_collector(game)
    game.rain.intensity = 1.0
    tick(game, C.COLLECTOR_TIME / 3 + 0.5)
    assert m.storage.count("water_capsule") == 1


def test_collector_stops_without_empties_or_with_full_out(game):
    at_stage(game, C.MIST_STAGE)
    m = make_collector(game, empties=0)
    assert game.collector_blocker(m, game.active) == "no_empty"
    m.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    m.storage.slots[C.COLLECTOR_OUT_SLOT] = Stack("water_capsule", C.STACK_MACHINE)
    assert game.collector_blocker(m, game.active) == "out_full"
    tick(game, C.COLLECTOR_TIME + 1)
    assert m.storage.count(C.EMPTY_CAPSULE) == 2 and m.timer == 0


def test_collector_is_idle_in_the_cave(game):
    at_stage(game, C.MIST_STAGE)
    game.enter_layer(CAVE)
    m = make_collector(game, tile=(60, 60))
    assert game.collector_blocker(m, game.active) == "cave"
    tick(game, C.COLLECTOR_TIME + 1)
    assert m.storage.count("water_capsule") == 0


def test_surface_collector_keeps_working_while_the_player_is_in_the_cave(game):
    at_stage(game, C.MIST_STAGE)
    m = make_collector(game)
    game.enter_layer(CAVE)
    tick(game, C.COLLECTOR_TIME + 1)
    assert m.storage.count("water_capsule") == 1


def test_power_deficit_slows_the_collector(game):
    at_stage(game, C.MIST_STAGE)
    m = make_collector(game)
    game._update_machines(1.0)
    assert m.timer == pytest.approx(1.0 * game.power.factor)


def test_collector_logistics():
    m = Machine(C.COLLECTOR, 0, 0)
    assert drones.can_receive(m, C.EMPTY_CAPSULE) and drones.receive_slot(m, C.EMPTY_CAPSULE) == C.COLLECTOR_IN_SLOT
    assert not drones.can_receive(m, "water_capsule") and not drones.can_receive(m, "iron")
    assert drones.can_send(m, "water_capsule") and not drones.can_send(m, C.EMPTY_CAPSULE)
    assert m.is_logistic and m.needs_chip and not m.in_network


def test_collector_put_only_takes_empties(game):
    m = make_collector(game, empties=0)
    game.inventory.slots[0] = Stack(C.EMPTY_CAPSULE, 4)
    game.inventory.slots[1] = Stack("water_capsule", 2)
    assert game.collector_put(m, 1) == 0
    assert game.collector_put(m, 0, 1) == 1 and game.collector_put(m, 0) == 3
    assert m.storage.slots[C.COLLECTOR_IN_SLOT] == Stack(C.EMPTY_CAPSULE, 4)


def test_interaction_opens_collector(game):
    m = make_collector(game, tile=(64, 70))
    game.player.x, game.player.y = (64 + 0.5) * C.TILE, (70 + 1) * C.TILE + 20
    x, y, w, h = m.sprite_rect
    assert game.nearby_collector() is m
    assert game.interactable_at(x + w / 2, y + h / 2) == ("collector", m)
    assert game.interaction() == ("collector", m) and game.in_reach("collector", m)
    m.build = 1.0
    assert game.nearby_collector() is None
    m.build = 0.0
    game.player.x += 5 * C.TILE
    assert game.nearby_collector() is None and not game.in_reach("collector", m)


def test_collector_save_roundtrip():
    m = Machine(C.COLLECTOR, 7, 8, sends={"water_capsule"}, receives={C.EMPTY_CAPSULE}, chip=True)
    m.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, 3)
    m.storage.slots[C.COLLECTOR_OUT_SLOT] = Stack("water_capsule", 2)
    m.timer = 12.5
    back = save.machine_from_dict(save.machine_to_dict(m))
    assert back.storage.slots == m.storage.slots and back.timer == 12.5 and back.chip
    assert back.sends == {"water_capsule"} and back.receives == {C.EMPTY_CAPSULE}


def test_collector_save_cleans_bad_slots():
    data = {"kind": C.COLLECTOR, "tx": 1, "ty": 1, "rotation": 0, "timer": 999,
            "storage": [["water_capsule", 3], ["water_capsule_empty", 2]]}
    m = save.machine_from_dict(data)
    assert m.storage.slots == [None, None] and m.timer == C.COLLECTOR_TIME


def test_collector_dismantle_returns_contents(game):
    m = make_collector(game, empties=2, chip=True)
    m.storage.slots[C.COLLECTOR_OUT_SLOT] = Stack("water_capsule", 1)
    out = game.dismantle_returns(m)
    assert out["iron_ingot"] == 3 and out["silicon"] == 6 and out[C.EMPTY_CAPSULE] == 2
    assert out["water_capsule"] == 1 and out["chip"] == 1


def test_collector_light_only_while_collecting(game):
    from game.render import cave_lights
    at_stage(game, C.MIST_STAGE)
    base = len(cave_lights(game))
    m = make_collector(game, empties=0)
    assert len(cave_lights(game)) == base
    m.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    assert len(cave_lights(game)) == base + 1


# ---------------------------------------------------------------- Task 3: App e render
from game.app import PANEL_MODES, capsule_time_text  # noqa: E402
from tests.test_base_app import app, base_with_dispenser, fresh  # noqa: E402,F401  (fixtures)


def test_capsule_time_text():
    assert capsule_time_text(45) == "45 s" and capsule_time_text(90) == "90 s"
    assert capsule_time_text(180) == "3 min" and capsule_time_text(150) == "2.5 min"


def test_dispenser_panel_shows_the_time_for_this_base(fresh):
    m, x0, y0 = base_with_dispenser(fresh, water=1)
    fresh.open_dispenser = m
    n = len(fresh.state.seal_of(m).floor)
    assert f"{capsule_time_text(dispenser_capsule_time(n))} nesta base" in fresh.dispenser_info()
    fresh.state.base.remove(fresh.state.base.get((x0 + 4, y0)))      # abre um furo
    assert "vede a base" in fresh.dispenser_info()


def test_dispenser_panel_does_not_take_anything_in_the_empty_slot(fresh):
    m, x0, y0 = base_with_dispenser(fresh, water=0)
    fresh.open_dispenser = m
    fresh.set_mode("dispenser")
    assert fresh.panel_refusal(m.storage, C.DISPENSER_EMPTY_SLOT, "water_capsule") is not None
    assert fresh.panel_refusal(m.storage, C.DISPENSER_CAPSULE_SLOT, "water_capsule") is None
    fresh.set_mode("play")


def test_collector_panel_in_the_app(fresh):
    s = fresh.state
    at_stage(s, C.MIST_STAGE)
    m = make_collector(s, empties=0)
    fresh.open_collector = m
    fresh.set_mode("collector")
    assert fresh.mode == "collector" and fresh.mode in PANEL_MODES
    assert fresh.collector_status() == "SEM VAZIA"
    s.inventory.add(C.EMPTY_CAPSULE, 2)
    s.inventory.add("iron", 2)
    assert fresh.panel_refusal(m.storage, C.COLLECTOR_IN_SLOT, "iron") is not None
    assert fresh.panel_refusal(m.storage, C.COLLECTOR_IN_SLOT, C.EMPTY_CAPSULE) is None
    assert fresh.panel_refusal(m.storage, C.COLLECTOR_OUT_SLOT, C.EMPTY_CAPSULE) is not None
    m.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    assert fresh.collector_status() == "COLETANDO" and "40 s" in fresh.collector_info()
    s.rain.intensity = 1.0
    assert "20 s" not in fresh.collector_info() and "13 s" in fresh.collector_info() and "chuva x3.0" in fresh.collector_info()
    at_stage(s, C.ARID_STAGE)
    assert fresh.collector_status() == "PARADO" and "estágio Úmido" in fresh.collector_info()
    fresh.set_mode("play")
    assert fresh.open_collector is None


def test_collector_item_icons_and_previews(fresh):
    for kind in (C.COLLECTOR, C.EMPTY_CAPSULE):
        assert fresh.renderer.item_icon(kind).get_size() == (32, 32)
        assert fresh.renderer.machine_preview(kind).get_width() > 0


def test_collector_animates_only_while_collecting(game):
    from game.render import Renderer
    at_stage(game, C.MIST_STAGE)
    m = make_collector(game, empties=0)
    r = Renderer.__new__(Renderer)
    r.machine_t = 3.1
    tick(game, 0.1)
    assert r.machine_anim_index(m, True, 0.0) is None                 # sem vazia: apagado
    m.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    tick(game, 0.1)
    assert r.machine_anim_index(m, True, 0.0) is not None and r.machine_anim_index(m, False, 0.0) is None


# ---------------------------------------------------------------- Task 4: a volta da água pelos drones
def test_drones_carry_empties_to_the_collector_and_full_ones_back(game):
    from tests.test_base import room
    at_stage(game, C.MIST_STAGE)
    x0, y0 = free_spot(game, 16, 8)
    x0, y0 = x0 + 1, y0 + 1
    room(game.base, x0, y0, 4, 3, door=(x0 + 1, y0 + 3))               # base vedada de 12 tiles
    disp = Machine(C.DISPENSER, x0, y0, sends={C.EMPTY_CAPSULE}, receives={"water_capsule"}, chip=True)
    disp.storage.slots[C.DISPENSER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    collector = Machine(C.COLLECTOR, x0 + 9, y0, sends={"water_capsule"}, receives={C.EMPTY_CAPSULE}, chip=True)
    station = Machine("drone_station", x0 + 6, y0 + 4)
    station.station = drones.new_station(station, 1)
    game.machines += [disp, collector, station]

    tick(game, 25)                                                    # 1ª viagem: as vazias saem do Dispersor...
    assert disp.storage.count(C.EMPTY_CAPSULE) < 2
    assert collector.storage.count(C.EMPTY_CAPSULE) + collector.storage.count("water_capsule") >= 1
    tick(game, 3 * C.COLLECTOR_TIME)                                  # ...o Coletor enche...
    assert disp.storage.count("water_capsule") >= 1                   # ...e a cheia volta pro Dispersor
    total = sum(m.storage.count(i) for m in (disp, collector) for i in ("water_capsule", C.EMPTY_CAPSULE))
    assert total <= 2                                                 # nenhuma cápsula nasceu do nada (uma pode estar no ar)
