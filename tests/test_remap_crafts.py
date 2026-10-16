"""v0.6 Fundo M5: receitas remapeadas pra cadeia nova (bíblia §15 "Marco 5")."""

import random

import pytest

from game import config as C
from game import fabricator, save
from game.systems import GameState
from tests.helpers import give

NEW_COSTS = {
    "silicon_wafer": {"silicon": 10},
    "circuit": {"wire": 3, "silicon": 5},
    "chip": {"silicon_wafer": 5, "wire": 5, "circuit": 1},
    "drone": {"circuit": 2, "wire": 5, "iron_ingot": 2},
    "o2_tank": {"iron_ingot": 5, "circuit": 1},
    "scanner": {"circuit": 4, "iron_ingot": 5, "silicon": 2},
    "backpack": {"iron_ingot": 5},
    "constructor": {"iron": 5, "silicon": 5},
    "o2_dispenser": {"circuit": 3, "chip": 2, "iron_ingot": 15, "wire": 5, "water_capsule": 2},
    "drill": {"iron_ingot": 5, "circuit": 1},
    "drone_station": {"iron_ingot": 10, "circuit": 1, "chip": 1, "wire": 2},
    "o2_t2": {"iron_ingot": 8, "circuit": 2, "ice": 10},
    "melter_t2": {"iron_ingot": 6, "wire": 4, "ice": 20},
    "heater_t2": {"iron_ingot": 8, "copper_ingot": 3, "magmatite": 10},
    "chest": {"iron_ingot": 3},
    "chest_large": {"iron_ingot": 6},
    "diagram_chest_large": {"iron_ingot": 4, "circuit": 1},
}
T2_ONLY = {"silicon_wafer", "circuit", "chip", "drone", "o2_tank", "backpack", "scanner", "hand_drill_t2"}
RAW_AT_TI0 = ("o2", "melter", "heater", "solar", "lamp", "lamp_t2", "chest_small", "smelter", "workbench",
              "diagram_workbench", "base_floor", "base_wall", "base_door", "base_door2")


@pytest.mark.parametrize("kind", sorted(NEW_COSTS))
def test_new_cost(kind):
    assert C.MACHINES[kind].cost == NEW_COSTS[kind]


def test_t2_exclusives():
    assert set(C.T2_RECIPES) == T2_ONLY


@pytest.mark.parametrize("kind", [k for k in RAW_AT_TI0 if k in C.MACHINES])
def test_ti0_stays_raw(kind):
    assert set(C.MACHINES[kind].cost) <= set(C.RESOURCES)


def test_wire_unchanged():
    assert C.MACHINES["wire"].cost == {"copper_ingot": 1} and C.CRAFT_YIELD["wire"] == 3


@pytest.mark.parametrize("diagram", sorted(C.BLUEPRINTS))
def test_bench_t2_reads_every_diagram(diagram):
    assert GameState.bench_reads(diagram, "t2")


def test_tank_and_scanner_diagrams_read_only_on_t2():
    assert not GameState.bench_reads("o2_tank", "t1") and not GameState.bench_reads("scanner", "t1")
    assert GameState.bench_reads("lamp_t2", "t1") and GameState.bench_reads("chest_large", "t1")


def test_t2_tabs_bench_first_then_t1():
    assert C.T2_TABS[0] == ("t2", "Bancada")
    assert C.T2_TABS[1:] == C.CRAFT_TABS
    assert set(fabricator.t2_kinds("t2")) == T2_ONLY
    for tab_id, _ in C.CRAFT_TABS:
        assert fabricator.t2_kinds(tab_id) == fabricator.craft_kinds(tab_id)


def test_t1_hides_t2_recipes():
    t1 = {k for tab_id, _ in C.CRAFT_TABS for k in fabricator.craft_kinds(tab_id)}
    assert not (t1 & T2_ONLY)
    assert "wire" in t1 and "constructor" in t1


def test_bench_crafts_t1_recipe_from_inventory():
    g = GameState(rng=random.Random(1))
    give(g, copper_ingot=1)
    assert g.craft("wire", bench="t2")
    assert g.inventory.count("wire") == 3


def test_t1_still_refuses_t2_recipe():
    g = GameState(rng=random.Random(1))
    give(g, iron_ingot=5)
    assert not g.craft("backpack")                       # T1
    assert g.craft("backpack", bench="t2")


def test_once_item_becomes_made_after_craft():
    g = GameState(rng=random.Random(1))
    give(g, iron_ingot=10)
    assert g.craft("backpack", bench="t2")
    assert g.recipe_status("backpack", inv_only=True) == "made"
    assert not g.craft("backpack", bench="t2")
    assert g.inventory.count("iron_ingot") == 5


def test_once_item_made_when_owned_or_equipped():
    g = GameState(rng=random.Random(1))
    g.inventory.add("constructor", 1)                    # o construtor do começo, sem crafted
    assert g.recipe_status("constructor") == "made"
    g.equipment.equip("o2_tank")
    assert g.recipe_status("o2_tank", inv_only=True) in ("made", "blueprint")


def test_once_items_list():
    assert set(C.ONCE_ITEMS) == {"constructor", "backpack", "o2_tank", "scanner", "hand_drill_t2"}


def test_made_survives_save_roundtrip():
    g = GameState(rng=random.Random(1))
    give(g, iron_ingot=5)
    g.craft("backpack", bench="t2")
    g.inventory.remove("backpack", 1)                    # "esqueceu num baú": só o crafted lembra
    g2 = save.state_from_dict(save.state_to_dict(g))
    assert g2.recipe_status("backpack", inv_only=True) == "made"
