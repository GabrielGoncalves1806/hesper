"""Estação de drones como inventário: 4 slots só de drone, trava em voo, tirar/colocar, desmontar e save v4."""

import json
import random

import pytest

from game import config as C
from game import drones, save
from game.drones import LANDED, OUTBOUND, RETURNING
from game.inventory import Stack
from game.systems import GameState, Machine
from tests.helpers import give

ST = (60, 70)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def station(game) -> Machine:
    m = Machine("drone_station", *ST)
    m.station = drones.new_station(m)
    game.machines.append(m)
    return m


def slot_of(game, item) -> int:
    return next(i for i, s in enumerate(game.inventory.slots) if s and s.item == item)


def test_dock_whole_stack_fills_free_slots_up_to_4(game):
    st = station(game)
    give(game, drone=5)
    assert game.station_dock(st, slot_of(game, "drone")) == 4
    assert [d.pad for d in st.station.drones] == [0, 1, 2, 3] and st.station.free_slots() == []
    assert game.inventory.count("drone") == 1
    assert game.station_dock(st, slot_of(game, "drone")) == 0           # cheia
    assert game.drones_docked == 4
    assert ("drone_dock", 4) in game.pop_events()


def test_dock_one_with_right_click(game):
    st = station(game)
    give(game, drone=3)
    assert game.station_dock(st, slot_of(game, "drone"), 1) == 1
    assert len(st.station.drones) == 1 and game.inventory.count("drone") == 2


def test_only_drones_go_in(game):
    st = station(game)
    give(game, iron=10, chest=1)
    assert game.station_dock(st, slot_of(game, "iron")) == 0
    assert game.station_dock(st, slot_of(game, "chest")) == 0
    assert game.station_dock(st, 15) == 0                               # slot vazio
    assert st.station.drones == []


def test_docked_drone_starts_working(game):
    st = station(game)
    drill = Machine("drill", ST[0] + 8, ST[1], resource="iron", stored=10)
    game.machines.append(drill)
    game._update_machines(0.1)
    assert drill.stored == 10                                           # sem drone, nada acontece
    give(game, drone=1)
    game.station_dock(st, slot_of(game, "drone"))
    game._update_machines(0.1)
    assert st.station.drones[0].state == OUTBOUND


def test_slot_locked_while_flying_and_free_after_landing(game):
    st = station(game)
    give(game, drone=1)
    game.station_dock(st, slot_of(game, "drone"))
    drill = Machine("drill", ST[0] + 6, ST[1], resource="ice", stored=8)
    game.machines.append(drill)
    game._update_machines(0.1)
    d = st.station.drones[0]
    assert d.busy and not game.station_undock(st, 0)                    # em voo: travado
    assert st.station.drones == [d]
    for _ in range(600):
        game._update_machines(1 / 30)
        if not d.busy:
            break
    assert d.state == LANDED and st.station.buffer == {"ice": 8}
    assert game.station_undock(st, 0)
    assert st.station.drones == [] and game.inventory.count("drone") == 1
    assert not game.station_undock(st, 0)                               # slot vazio


def test_undock_brings_held_cargo_or_refuses_when_full(game):
    st = station(game)
    d = drones.dock(st, st.station, 1)
    d.resource, d.cargo = "iron", 7                                     # pousado segurando (buffer estava cheio)
    for i in range(C.INVENTORY_SLOTS):
        game.inventory.slots[i] = Stack("silicon", 50)
    assert not game.station_undock(st, 1)
    assert st.station.drone_in(1) is d and ("inv_full",) in game.pop_events()
    game.inventory.slots[0] = None
    game.inventory.slots[1] = None
    assert game.station_undock(st, 1)
    assert game.inventory.count("drone") == 1 and game.inventory.count("iron") == 7


def test_take_from_buffer_stack_or_one(game):
    st = station(game)
    st.station.buffer = {"iron": 20, "ice": 3}
    assert st.station.buffer_stacks() == [("iron", 20), ("ice", 3)]
    assert game.station_take(st, "iron", 1) == 1
    assert game.station_take(st, "iron") == 19
    assert st.station.buffer == {"ice": 3} and game.inventory.count("iron") == 20


def test_dismantle_returns_station_flying_drones_and_all_ore(game):
    st = station(game)
    give(game, drone=3)
    game.station_dock(st, slot_of(game, "drone"))
    a, b, c = st.station.drones
    a.state, a.target = OUTBOUND, None                                  # indo vazio
    b.state, b.resource, b.cargo = RETURNING, "silicon", 11             # voltando carregado
    st.station.buffer = {"iron": 9}
    game.player.x, game.player.y = (ST[0] + 1) * C.TILE, (ST[1] + 3) * C.TILE
    assert game.dismantle(st)
    assert st not in game.machines
    assert game.inventory.counts() == {"drone": 3, "silicon": 11, "iron": 9, "drone_station": 1}


def test_dismantle_refuses_if_drones_do_not_fit(game):
    st = station(game)
    give(game, drone=2)
    game.station_dock(st, slot_of(game, "drone"))
    for i in range(C.INVENTORY_SLOTS - 1):
        game.inventory.slots[i] = Stack("silicon", 50)
    game.inventory.slots[-1] = None                                     # cabe a estação, mas não os drones
    game.player.x, game.player.y = (ST[0] + 1) * C.TILE, (ST[1] + 3) * C.TILE
    assert not game.dismantle(st)
    assert st in game.machines and len(st.station.drones) == 2


# ---------------------------------------------------------------- save v3 -> v4
def v3_save() -> dict:
    state = save.new_state()
    state.debug_add_ti()
    give(state, chest=1)
    state.player.x, state.player.y = 62.5 * C.TILE, 70 * C.TILE
    assert state.place("chest", (62, 68))
    m = Machine("drone_station", 66, 68)
    m.station = drones.new_station(m)
    m.station.buffer = {"iron": 5}
    state.machines.append(m)
    data = save.state_to_dict(state)
    data["version"] = 3
    for md in data["machines"]:
        md.pop("name", None)
        if md["kind"] == "drone_station":
            md.pop("drones")
            md["drone_cargo"] = [["ice", 4], None]                     # o formato do v3
    del data["progress"]["drones_docked"]
    return data


def test_migration_v3_to_v4_names_chests_and_gives_two_drones(tmp_path):
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(v3_save()), encoding="utf-8")
    loaded = save.load_game(path)
    assert loaded is not None
    assert loaded.chests[0].name == "Baú"
    st = loaded.stations[0]
    assert [d.pad for d in st.station.drones] == [0, 1]
    assert st.station.drones[0].cargo == 4 and st.station.drones[0].resource == "ice"
    assert st.station.drones[1].cargo == 0 and st.station.buffer == {"iron": 5}
    assert loaded.drones_docked == 2
    save.write_save(loaded, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 4
    assert next(m for m in data["machines"] if m["kind"] == "drone_station")["drones"] == \
        [["ice", 4], [None, 0], None, None]


def test_migration_v3_without_station_docks_nothing():
    data = save.state_to_dict(save.new_state())
    data["version"] = 3
    del data["progress"]["drones_docked"]
    state = save.state_from_dict(save.migrate(data))
    assert state.drones_docked == 0 and state.stations == []


def test_drone_as_placed_machine_in_save_is_rejected():
    data = save.state_to_dict(save.new_state())
    data["machines"] = [{"kind": "drone", "tx": 60, "ty": 66, "rotation": 0}]
    with pytest.raises(ValueError):
        save.state_from_dict(data)
