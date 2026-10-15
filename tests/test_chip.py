"""v0.6 M2: chip nas máquinas, entrar/sair da rede, derretedor recebe gelo, dispersor recebe cápsula."""
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C, drones, save  # noqa: E402
from game.drones import CARRYING  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from game.ui import UI  # noqa: E402
from tests.helpers import give  # noqa: E402

ST = (60, 70)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def icon(_item):
    return art.icon("iron")


def add_station(game) -> Machine:
    m = Machine("drone_station", *ST)
    m.station = drones.new_station(m, 1)
    game.machines.append(m)
    return m


def run(game, seconds: float, step: float = 1 / 30) -> None:
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def test_machines_that_need_a_chip():
    assert Machine("drill", 0, 0, resource="iron").needs_chip
    assert Machine("melter", 0, 0).needs_chip and Machine("melter_t2", 0, 0).needs_chip
    assert Machine(C.DISPENSER, 0, 0).needs_chip
    assert not Machine("chest", 0, 0).needs_chip


def test_network_needs_chip_but_chest_does_not(game):
    drill = Machine("drill", 1, 1, resource="iron", sends={"iron"})
    chest = Machine("chest", 5, 5, receives={"iron"})
    game.surface.machines += [drill, chest]
    assert chest in game.drone_logistics() and drill not in game.drone_logistics()
    drill.chip = True
    assert drill in game.drone_logistics()


def test_install_turns_receive_on_and_take_keeps_config(game):
    melter = Machine("melter", 1, 1, sends={"water_capsule"})
    game.surface.machines.append(melter)
    assert game.chip_install(melter)
    assert melter.chip and melter.receives == {"ice"} and melter.sends == {"water_capsule"}
    assert ("chip_on", melter.anchor) in game.pop_events()
    assert not game.chip_install(melter)                         # 1 por máquina
    assert game.chip_take(melter)
    assert not melter.chip and game.inventory.count("chip") == 1
    assert ("chip_off", melter.anchor) in game.pop_events()
    assert melter.receives == {"ice"}                            # a config fica guardada


def test_install_from_inventory_spends_one_chip(game):
    give(game, chip=3)
    i = next(k for k, s in enumerate(game.inventory.slots) if s and s.item == "chip")
    disp = Machine(C.DISPENSER, 1, 1)
    game.surface.machines.append(disp)
    assert game.chip_install_from(disp, i)
    assert disp.chip and disp.receives == {"water_capsule"} and game.inventory.count("chip") == 2


def test_chest_never_takes_a_chip(game):
    chest = Machine("chest", 1, 1)
    assert not game.chip_install(chest)


def test_what_each_machine_accepts():
    drill = Machine("drill", 0, 0, resource="iron")
    melter, disp = Machine("melter", 0, 0), Machine(C.DISPENSER, 0, 0)
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_send(drill, i)] == ["iron"]
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_receive(drill, i)] == []
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_send(melter, i)] == ["water_capsule"]
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_receive(melter, i)] == ["ice"]
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_send(disp, i)] == []
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_receive(disp, i)] == ["water_capsule"]


def test_melter_room_is_the_ice_slot_only():
    melter = Machine("melter", 0, 0)
    melter.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", 3)
    melter.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", 30)
    ledger = drones.Ledger()
    assert ledger.room(melter, "ice") == Stack("ice", 30).room
    ledger.bring(melter, "ice", 5)
    assert ledger.room(melter, "ice") == Stack("ice", 30).room - 5


def test_deliver_goes_to_the_right_slot():
    melter = Machine("melter", 0, 0)
    assert drones.deliver(melter, "ice", 4) == 0
    assert melter.storage.slots[C.MELTER_ICE_SLOT] == Stack("ice", 4)
    assert melter.storage.slots[C.MELTER_CAPSULE_SLOT] is None
    disp = Machine(C.DISPENSER, 0, 0)
    full = Stack("water_capsule", 1).max
    assert drones.deliver(disp, "water_capsule", full + 3) == 3


def test_drones_feed_melter_with_ice_and_dispenser_with_capsules(game):
    """Com o update de verdade: baú envia gelo e cápsula, derretedor e dispersor com chip recebem."""
    add_station(game)
    chest = Machine("chest_large", 80, 70, sends={"ice", "water_capsule"})
    chest.storage.add("ice", 20)
    chest.storage.add("water_capsule", 5)
    melter = Machine("melter", 66, 72)
    disp = Machine(C.DISPENSER, 66, 66)
    game.machines += [chest, melter, disp]
    assert game.chip_install(melter) and game.chip_install(disp)
    run(game, 60)
    assert melter.ice > 0 and disp.capsules > 0


def test_machine_without_chip_gets_nothing(game):
    add_station(game)
    chest = Machine("chest_large", 80, 70, sends={"ice"})
    chest.storage.add("ice", 20)
    melter = Machine("melter", 66, 72, receives={"ice"})            # configurado, mas sem chip
    game.machines += [chest, melter]
    run(game, 30)
    assert melter.ice == 0 and chest.storage.count("ice") == 20


def test_chip_removed_mid_flight_drone_goes_elsewhere(game):
    st = add_station(game)
    chest = Machine("chest_large", 80, 70, sends={"ice"})
    chest.storage.add("ice", 10)
    gone = Machine("melter", 40, 70)
    other = Machine("chest_large", 30, 76, receives={"ice"})
    game.machines += [chest, gone, other]
    assert game.chip_install(gone)
    run(game, 0.1)
    d = st.station.drones[0]
    assert d.dest is gone
    run(game, 5)                                                          # já pegou e está levando
    assert d.state == CARRYING
    assert game.chip_take(gone)
    run(game, 20)
    assert other.storage.count("ice") == 10 and d.cargo == 0 and gone.ice == 0


def test_dismantle_returns_the_chip(game):
    drill = Machine("drill", 70, 70, resource="iron")
    assert "chip" not in game.dismantle_returns(drill)
    drill.chip = True
    assert game.dismantle_returns(drill).get("chip") == 1


def test_save_roundtrip_keeps_chip():
    melter = Machine("melter", 1, 1, chip=True, receives={"ice"})
    assert save.machine_from_dict(save.machine_to_dict(melter)).chip
    assert not save.machine_from_dict(save.machine_to_dict(Machine("melter", 1, 1))).chip
    disp = Machine(C.DISPENSER, 1, 1, chip=True, receives={"water_capsule"})
    back = save.machine_from_dict(save.machine_to_dict(disp))
    assert back.chip and back.receives == {"water_capsule"}
    assert "chip" not in save.machine_to_dict(Machine("chest", 1, 1))


def test_ui_chip_slot_and_hint(ui):
    size = (960, 540)
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = GameState(rng=random.Random(1))
    melter = Machine("melter", 0, 0, sends={"water_capsule"})
    ui.begin()
    ui.draw_inventory(s.inventory, melter, 0, icon, (0, 0))
    assert ui.chip_at(ui.chip_rects[0][0].center) is melter
    assert ui.logistics_buttons == []                                    # sem chip: nada de Envia/Recebe/Lote
    s.chip_install(melter)
    ui.begin()
    ui.draw_inventory(s.inventory, melter, 0, icon, (0, 0))
    assert [v for _, v in ui.logistics_buttons if v[0] != "batch"] == [("send", "water_capsule"), ("recv", "ice")]
    disp = Machine(C.DISPENSER, 0, 0, chip=True)
    ui.begin()
    ui.draw_inventory(s.inventory, disp, 0, icon, (0, 0))
    assert {v[0] for _, v in ui.logistics_buttons} == {"recv"}           # dispersor: sem Envia e sem Lote
    drill = Machine("drill", 0, 0, resource="iron")
    assert ui.logistics_height(drill) == ui.logistics_height(Machine("drill", 0, 0, resource="iron", chip=True))
