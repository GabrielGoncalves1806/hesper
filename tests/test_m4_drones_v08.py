"""v0.8 M4 Task 5: os drones atendem o Microscópio e a Centrífuga."""

from game import config as C
from game import drones
from game.drones import Ledger
from game.inventory import Stack
from game.systems import Machine
from tests.test_logistics import add_station, chest, game, run  # noqa: F401  (fixture)

PLANTS = ("plant_1", "plant_2", "plant_3")


def test_microscope_logistics():
    m = Machine(C.MICROSCOPE, 0, 0, 0)
    assert drones.can_receive(m, "ice") and not drones.can_receive(m, "iron")
    assert all(drones.can_send(m, s) for s in C.SAMPLE_ITEMS) and not drones.can_send(m, "ice")
    assert drones.receive_slot(m, "ice") == C.MIC_ICE_SLOT


def test_centrifuge_logistics():
    m = Machine(C.CENTRIFUGE, 0, 0, 0)
    assert drones.can_receive(m, "algae") and all(drones.can_receive(m, s) for s in C.SAMPLE_ITEMS)
    assert not drones.can_receive(m, "plant_1") and not drones.can_receive(m, "iron")
    assert all(drones.can_send(m, p) for p in PLANTS)
    assert not drones.can_send(m, "algae") and not drones.can_send(m, "sample_basic")
    assert drones.receive_slot(m, "algae") == C.CENT_ALGAE_SLOT
    assert drones.receive_slot(m, "sample_mutant") == C.CENT_SAMPLE_SLOT


def test_stock_only_offers_the_output():
    mic = Machine(C.MICROSCOPE, 0, 0, 0)
    mic.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 5)
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", 2)
    assert drones.stock(mic, "ice") == 0 and drones.stock(mic, "sample_rare") == 2
    cen = Machine(C.CENTRIFUGE, 0, 0, 0)
    cen.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 4)
    cen.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_basic", 3)
    cen.storage.slots[C.CENT_OUT_SLOTS["plant_2"]] = Stack("plant_2", 1)
    assert drones.stock(cen, "algae") == 0 and drones.stock(cen, "sample_basic") == 0
    assert drones.stock(cen, "plant_2") == 1


def test_centrifuge_refuses_a_different_sample_type(game):
    st = add_station(game)
    cen = Machine(C.CENTRIFUGE, 70, 70, receives={"sample_basic", "sample_rare"}, chip=True)
    game.machines.append(cen)
    chest(game, 55, 70, sends={"sample_rare"}, sample_rare=4)
    cen.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_basic", 2)
    assert drones.pick_task(st, game.logistics, Ledger()) is None           # outro tipo no slot: não entrega
    cen.storage.slots[C.CENT_SAMPLE_SLOT] = None                            # slot vazio: entrega
    assert drones.pick_task(st, game.logistics, Ledger()).item == "sample_rare"
    cen.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_rare", 1)         # mesmo tipo: entrega
    assert drones.pick_task(st, game.logistics, Ledger()).dest is cen


def test_drones_carry_ice_to_the_microscope_and_samples_back(game):
    add_station(game)
    mic = Machine(C.MICROSCOPE, 70, 70, receives={"ice"}, sends={"sample_basic"}, chip=True)
    game.machines.append(mic)
    src = chest(game, 52, 70, sends={"ice"}, ice=3)
    dst = chest(game, 88, 70, receives={"sample_basic"})
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 2)
    run(game, 40)
    assert src.storage.count("ice") < 3
    assert mic.storage.count("ice") + mic.storage.count("sample_basic") >= 1
    assert dst.storage.count("sample_basic") >= 2        # as 2 de antes (e talvez uma nova, se o gelo virou amostra)
