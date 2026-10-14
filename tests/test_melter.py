"""v0.5 Marco 2: cápsula de água, derretedor com inventário e drones tirando as cápsulas."""

import random

import pytest

from game import config as C
from game import drones, save
from game.inventory import Stack, max_stack
from game.systems import GameState, Machine
from tests.helpers import give

ST = (60, 70)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add_melter(game, kind="melter", tile=(64, 70), ice=0, capsules=0, sends=("water_capsule",)) -> Machine:
    m = Machine(kind, *tile, sends=set(sends))
    if ice:
        m.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", ice)
    if capsules:
        m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", capsules)
    game.machines.append(m)
    return m


def run(game, seconds, step=1 / 30):
    for _ in range(round(seconds / step)):
        game._update_machines(step)


# ---------------------------------------------------------------- item
def test_item_is_registered_not_craftable_and_stacks():
    item = C.MACHINES["water_capsule"]
    assert item.name == "Cápsula de água" and not item.placeable
    assert "water_capsule" not in C.MACHINE_ORDER and "water_capsule" not in C.MACHINE_CATEGORY
    assert max_stack("water_capsule") == C.STACK_MACHINE
    assert (C.SPRITES_DIR / f"{item.sprite}.png").exists()


# ---------------------------------------------------------------- produção
def test_melter_has_two_slots(game):
    m = Machine("melter", 5, 5)
    assert len(m.storage) == C.MELTER_SLOTS and m.is_logistic and m.is_producer
    assert Machine("melter_t2", 5, 5).is_melter


def test_makes_capsule_from_ice(game):
    m = add_melter(game, ice=10)
    run(game, C.MELTER_CAPSULE_TIME["melter"] + 0.5)
    assert m.capsules == 1 and m.ice == 10 - C.MELTER_ICE_PER_CAPSULE


def test_no_ice_no_capsule(game):
    m = add_melter(game)
    run(game, C.MELTER_CAPSULE_TIME["melter"] * 2)
    assert m.capsules == 0 and m.timer == 0


def test_full_output_stops_capsules_and_keeps_ice_but_terraforms(game):
    full = max_stack("water_capsule")
    m = add_melter(game, ice=20, capsules=full)
    assert m.capsules_full
    water = game.indices["water"]
    run(game, C.MELTER_CAPSULE_TIME["melter"] * 2)
    assert m.capsules == full and m.ice == 20                      # nada gasto
    assert game.indices["water"] > water                           # terraformação segue
    m.storage.remove("water_capsule", 1)
    run(game, C.MELTER_CAPSULE_TIME["melter"] + 0.5)
    assert m.capsules == full and m.ice == 20 - C.MELTER_ICE_PER_CAPSULE


def test_terraforming_unchanged_with_empty_melter(game):
    before = game.indices["water"]
    add_melter(game, sends=())
    run(game, 10)
    assert game.indices["water"] - before == pytest.approx(C.MACHINES["melter"].rate * 10, rel=1e-3)


# ---------------------------------------------------------------- painel (player)
def test_put_only_ice_and_take_back(game):
    m = add_melter(game)
    give(game, ice=60, iron=5)
    i_ice = next(i for i, s in enumerate(game.inventory.slots) if s and s.item == "ice")
    i_iron = next(i for i, s in enumerate(game.inventory.slots) if s and s.item == "iron")
    assert game.melter_put(m, i_iron) == 0
    assert game.melter_put(m, i_ice, 1) == 1 and m.ice == 1
    assert game.melter_put(m, i_ice) >= 1 and m.ice <= max_stack("ice")
    m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", 3)
    assert game.melter_take(m) > 0
    assert m.storage.is_empty() and game.inventory.count("water_capsule") == 3


def test_dismantle_returns_what_is_inside(game):
    m = add_melter(game, ice=7, capsules=2)
    ret = game.dismantle_returns(m)
    assert ret["ice"] == C.MACHINES["melter"].cost["ice"] + 7 and ret["water_capsule"] == 2


def test_interaction_opens_melter(game):
    m = add_melter(game)
    game.player.x, game.player.y = m.anchor[0], m.anchor[1] + 4
    assert game.interaction() == ("melter", m)


# ---------------------------------------------------------------- drones
def add_station(game):
    st = Machine("drone_station", *ST)
    st.station = drones.new_station(st, 1)
    game.machines.append(st)
    return st


def test_drone_takes_capsules_to_chest(game):
    add_station(game)
    m = add_melter(game, capsules=3)
    chest = Machine("chest", 66, 72, receives={"water_capsule"})
    game.machines.append(chest)
    run(game, 20)
    assert chest.storage.count("water_capsule") == 3 and m.capsules == 0


def test_drone_never_feeds_melter_and_ignores_unmarked(game):
    add_station(game)
    m = add_melter(game, capsules=2, sends=())            # Envia desligado: ninguém tira
    chest = Machine("chest", 66, 72, receives={"water_capsule"})
    game.machines.append(chest)
    run(game, 20)
    assert m.capsules == 2 and chest.storage.is_empty()
    assert not drones.can_receive(m, "ice") and not drones.can_receive(m, "water_capsule")
    assert drones.can_send(m, "water_capsule") and not drones.can_send(m, "ice")
    assert not drones.toggle_receive(m, "ice")


# ---------------------------------------------------------------- save
def test_save_roundtrip_keeps_melter_inventory():
    state = save.new_state()
    m = Machine("melter_t2", 40, 40, sends={"water_capsule"})
    m.storage.slots[0], m.storage.slots[1], m.timer = Stack("ice", 9), Stack("water_capsule", 4), 3.5
    state.machines.append(m)
    loaded = save.state_from_dict(save.migrate(save.state_to_dict(state)))
    got = next(x for x in loaded.machines if x.is_melter)
    assert got.kind == "melter_t2" and got.ice == 9 and got.capsules == 4
    assert got.timer == pytest.approx(3.5) and got.sends == {"water_capsule"}


def test_v8_save_without_melter_storage_loads_empty():
    """Derretedor de antes do Marco 2 (sem "storage" no JSON, mesma v8): carrega com o inventário vazio."""
    state = save.new_state()
    state.machines.append(Machine("melter", 40, 40))
    data = save.state_to_dict(state)
    entry = next(m for m in data["layers"]["surface"]["machines"] if m["kind"] == "melter")
    for key in ("storage", "sends", "receives", "batch", "timer"):
        entry.pop(key, None)
    assert data["version"] == save.SAVE_VERSION
    loaded = save.state_from_dict(save.migrate(data))
    got = next(x for x in loaded.machines if x.is_melter)
    assert got.storage.is_empty() and got.timer == 0 and not got.sends


def test_corrupt_melter_storage_is_cleaned():
    assert save.melter_storage([["iron", 5], ["ice", 3]]).is_empty()      # item no slot errado: some
    assert save.melter_storage([["ice", 999], None]).count("ice") == max_stack("ice")
