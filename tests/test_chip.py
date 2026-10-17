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


def test_install_marks_nothing_and_take_keeps_config(game):
    """Dono (2026-10-16): o chip não liga Envia nem Recebe; o que o player marcou fica como estava."""
    melter = Machine("melter", 1, 1, sends={"water_capsule"})
    game.surface.machines.append(melter)
    assert game.chip_install(melter)
    assert melter.chip and melter.receives == set() and melter.sends == {"water_capsule"}
    melter.receives.add("ice")
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
    assert disp.chip and disp.receives == set() and game.inventory.count("chip") == 2


def test_chest_never_takes_a_chip(game):
    chest = Machine("chest", 1, 1)
    assert not game.chip_install(chest)


def test_what_each_machine_accepts():
    drill = Machine("drill", 0, 0, resource="iron")
    melter, disp = Machine("melter", 0, 0), Machine(C.DISPENSER, 0, 0)
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_send(drill, i)] == ["iron"]
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_receive(drill, i)] == []
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_send(melter, i)] == ["water_capsule"]
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_receive(melter, i)] == ["ice", C.EMPTY_CAPSULE]   # v0.8 M6: + as vazias
    assert [i for i in C.LOGISTIC_ITEMS if drones.can_send(disp, i)] == [C.EMPTY_CAPSULE]   # v0.8 M2: as vazias
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
    melter = Machine("melter", 66, 72, receives={"ice"})                # o player marcou o Recebe
    disp = Machine(C.DISPENSER, 66, 66, receives={"water_capsule"})
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
    gone = Machine("melter", 40, 70, receives={"ice"})
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
    assert [v for _, v in ui.logistics_buttons if v[0] != "batch"] == [("send", "water_capsule"), ("recv", "ice"),
                                                                          ("recv", C.EMPTY_CAPSULE)]   # v0.8 M6
    disp = Machine(C.DISPENSER, 0, 0, chip=True)
    ui.begin()
    ui.draw_inventory(s.inventory, disp, 0, icon, (0, 0))
    assert {v[0] for _, v in ui.logistics_buttons} == {"recv", "send", "batch"}   # dispersor: recebe cápsula, envia as vazias (v0.8 M2)
    drill = Machine("drill", 0, 0, resource="iron")
    assert ui.logistics_height(drill) == ui.logistics_height(Machine("drill", 0, 0, resource="iron", chip=True))


# ---- v0.6 M2 Task 2: receita do chip e save v11 ----------------------------------------------------
def test_chip_is_a_t2_recipe(game):
    from game import fabricator
    assert C.MACHINES["chip"].cost == {"silicon_wafer": 5, "wire": 5, "circuit": 1}      # v0.6 Fundo M5
    assert "chip" in fabricator.t2_kinds("t2") and "chip" not in fabricator.craft_kinds("t2")
    give(game, silicon_wafer=5, wire=5, circuit=1)
    assert game.craft("chip", bench="t2") and game.inventory.count("chip") == 1
    assert game.inventory.count("silicon_wafer") == 0


def test_v10_to_v11_gives_chip_to_working_drills_and_melters():
    data = {"version": 10, "layers": {"surface": {"machines": [
        {"kind": "drill", "tx": 0, "ty": 0, "rotation": 0, "resource": "iron", "sends": ["iron"]},
        {"kind": "drill", "tx": 4, "ty": 0, "rotation": 0, "resource": "iron", "sends": []},
        {"kind": "melter", "tx": 8, "ty": 0, "rotation": 0, "sends": ["water_capsule"]},
        {"kind": "o2_dispenser", "tx": 9, "ty": 0, "rotation": 0},
        {"kind": "chest", "tx": 10, "ty": 0, "rotation": 0, "sends": ["iron"]},
    ]}}}
    out = save.MIGRATIONS[10](data)["layers"]["surface"]["machines"]
    assert [m.get("chip") for m in out] == [True, None, True, None, None]


def test_v10_save_loads_with_chip_on_working_drill(game):
    drill = Machine("drill", 70, 70, resource="iron")
    drill.sends.add("iron")
    disp = Machine(C.DISPENSER, 74, 70)
    game.machines += [drill, disp]
    data = save.state_to_dict(game)
    data["version"] = 10
    for layer in data["layers"].values():
        for m in layer["machines"]:
            m.pop("chip", None)
    loaded = save.state_from_dict(save.migrate(data))
    by_kind = {m.kind: m for m in loaded.machines}
    assert by_kind["drill"].chip is True and by_kind[C.DISPENSER].chip is False


# ---- v0.6 M2 Task 3: estado do dispersor só no hover -----------------------------------------------
def test_dispenser_label_only_on_hover_and_bang_when_stopped(monkeypatch):
    from game.app import App
    app = App.__new__(App)
    state = GameState(rng=random.Random(3))
    app.state = state
    dry, ok = Machine(C.DISPENSER, 3, 3), Machine(C.DISPENSER, 9, 9)
    state.machines += [dry, ok]
    monkeypatch.setattr(state, "dispenser_state", lambda m, factor=None: "dry" if m is dry else "sealed")
    monkeypatch.setattr(app, "hovered_machine", lambda: None)
    assert app.dispenser_labels() == [(dry, "dry", False)]          # vedado sem hover: nada
    monkeypatch.setattr(app, "hovered_machine", lambda: ok)
    got = sorted(app.dispenser_labels(), key=lambda t: t[0].tx)
    assert got == [(dry, "dry", False), (ok, "sealed", True)]


def test_draw_dispenser_labels_bang_and_hover(ui):
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    m = Machine(C.DISPENSER, 20, 20)
    ui.begin()
    ui.draw_dispenser_labels([(m, "dry", False)], (0, 0), 1.0)
    ui.draw_dispenser_labels([(m, "sealed", True)], (0, 0), 1.0)


# ---- resumo do título da seção DRONES usa nome curto antes de cair na contagem -----------------------
def test_logistics_summary_short_names(ui):
    assert ui.logistics_summary(Machine("chest", 0, 0), short=True) == "nada configurado"
    disp = Machine(C.DISPENSER, 0, 0, chip=True)
    disp.receives.add("water_capsule")
    assert ui.logistics_summary(disp) == "recebe cápsula de água"
    assert ui.logistics_summary(disp, short=True) == "recebe cápsula"
    melter = Machine("melter", 0, 0, chip=True)
    melter.sends.add("water_capsule")
    melter.receives.add("ice")
    assert ui.logistics_summary(melter, short=True) == "envia cápsula · recebe gelo"
