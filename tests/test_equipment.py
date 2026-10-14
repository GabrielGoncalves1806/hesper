"""Equipamento do traje (v0.3 Marco 3): tanque de O₂ e scanner em slots tipados."""

import pytest

from game import config as C
from game.equipment import Equipment
from game.systems import Controls, GameState
from tests.helpers import give


def test_slots_start_empty_and_roundtrip():
    eq = Equipment()
    assert eq.slots == {"o2_tank": None, "scanner": None, "backpack": None} and eq.o2_max == C.O2_MAX
    assert eq.equip("o2_tank") is None and eq.o2_max == C.O2_TANK_MAX
    assert Equipment.from_data(eq.to_data()).slots == eq.slots
    assert Equipment.from_data({"o2_tank": "scanner", "x": "o2_tank"}).slots == {"o2_tank": None, "scanner": None, "backpack": None}
    with pytest.raises(ValueError):
        eq.equip("iron")


def test_tank_raises_o2_max_and_refill_goes_to_220():
    g = GameState(7)
    g.blueprints.add("o2_tank")
    give(g, iron=10, silicon=6, ice=4)
    assert g.craft("o2_tank")
    i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == "o2_tank")
    assert g.equip_from(i) and g.inventory.count("o2_tank") == 0
    assert g.o2_max == 220 and "o2_tank" in g.equipped_ever
    assert ("equip", "o2_tank") in g.pop_events()
    g.storm = 0.0                                  # céu limpo: a rajada não tira o player da base
    g.o2 = 50
    for _ in range(400):
        g.update(0.05, Controls())                 # parado na base: enche até 220
    assert g.o2 == pytest.approx(220)


def test_unequip_clamps_o2_and_needs_space():
    g = GameState(7)
    g.equipment.equip("o2_tank")
    g.o2 = 180
    for _ in range(C.INVENTORY_SLOTS):
        g.inventory.add("chest", 5)
    assert not g.unequip("o2_tank") and g.o2_max == 220
    g.inventory.clear()
    assert g.unequip("o2_tank") and g.o2 == C.O2_MAX and g.inventory.count("o2_tank") == 1
    assert not g.unequip("o2_tank")


def test_tank_lasts_220_seconds_outside():
    g = GameState(7)
    g.equipment.equip("o2_tank")
    g.storm = 0.0                                 # céu limpo: na tempestade o O₂ gasta ×1,25
    g.o2 = g.o2_max
    g.player.x += 20 * C.TILE                     # fora da zona
    for _ in range(int(219 / 0.05)):
        g.update(0.05, Controls())
    assert not g.fainted and g.o2 > 0
    for _ in range(40):
        g.update(0.05, Controls())
    assert g.fainted


def test_equip_swaps_and_scanner_flag():
    g = GameState(7)
    give(g, scanner=2)
    assert not g.has_scanner
    assert g.equip_from(0) and g.has_scanner and g.inventory.count("scanner") == 1
    assert g.equip_from(0) and g.inventory.count("scanner") == 1     # trocou um pelo outro
    give(g, iron=3)
    i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == "iron")
    assert not g.equip_from(i)
