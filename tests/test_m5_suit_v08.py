"""v0.8 M5 Task 1: traje com nv.2 (tanque e Mochila T2), botas e save v17."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import equipment, save  # noqa: E402
from game.equipment import Equipment  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState  # noqa: E402
from tests.helpers import give  # noqa: E402

SUIT_ITEMS = ("o2_tank", C.O2_TANK_T2, "scanner", "backpack", C.BACKPACK_T2, C.BOOTS)


def state() -> GameState:
    return GameState(rng=random.Random(5))


def equip_via_inventory(g: GameState, item: str) -> bool:
    give(g, **{item: 1})
    i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == item)
    return g.equip_from(i)


# ---- config e Equipment ---------------------------------------------------------------------------
def test_slots_and_labels():
    assert C.EQUIP_SLOTS == ("o2_tank", "scanner", "backpack", "boots")
    assert C.EQUIP_LABEL["boots"] == "BOTAS"
    assert all(equipment.is_equipment(i) for i in SUIT_ITEMS) and not equipment.is_equipment("iron")
    assert equipment.slot_of(C.O2_TANK_T2) == "o2_tank" and equipment.slot_of(C.BACKPACK_T2) == "backpack"
    assert equipment.slot_of(C.BOOTS) == "boots"


def test_equipment_filled_has_and_swap():
    eq = Equipment()
    assert eq.slots == {k: None for k in C.EQUIP_SLOTS} and eq.backpack_rows == 0
    assert eq.equip("o2_tank") is None and eq.o2_max == C.O2_TANK_MAX
    assert eq.equip(C.O2_TANK_T2) == "o2_tank" and eq.slots["o2_tank"] == C.O2_TANK_T2
    assert eq.filled("o2_tank") and eq.has(C.O2_TANK_T2) and not eq.has("o2_tank")
    assert eq.o2_max == C.O2_TANK_T2_MAX == 400
    eq.equip("backpack")
    assert eq.backpack_rows == 1
    eq.equip(C.BACKPACK_T2)
    assert eq.backpack_rows == 2
    assert eq.unequip("o2_tank") == C.O2_TANK_T2 and eq.o2_max == C.O2_MAX


# ---- tanque nv.2 ------------------------------------------------------------------------------------
def test_tank_t2_swaps_with_t1_and_gives_400():
    g = state()
    assert equip_via_inventory(g, "o2_tank") and g.o2_max == 220
    assert equip_via_inventory(g, C.O2_TANK_T2)
    assert g.o2_max == 400 and g.inventory.count("o2_tank") == 1 and g.inventory.count(C.O2_TANK_T2) == 0
    assert C.O2_TANK_T2 in g.equipped_ever
    assert g.owns(C.O2_TANK_T2) and g.owns("o2_tank")       # um no traje, o outro no inventário


# ---- botas ------------------------------------------------------------------------------------------
def test_boots_speed_and_f3():
    g = state()
    assert g.player_speed == pytest.approx(C.PLAYER_SPEED)
    assert equip_via_inventory(g, C.BOOTS)
    assert g.player_speed == pytest.approx(120 * 1.3)
    g.toggle_fast()
    assert g.player_speed == pytest.approx(120 * 1.3 * C.DEBUG_SPEED)


# ---- Mochila T2 -------------------------------------------------------------------------------------
def test_backpack_t2_gives_32_and_downgrade_needs_empty_rows():
    g = state()
    assert equip_via_inventory(g, "backpack") and len(g.inventory) == 24
    assert equip_via_inventory(g, C.BACKPACK_T2) and len(g.inventory) == 32
    assert g.has_backpack and g.inventory.count("backpack") == 1
    g.inventory.slots[31] = Stack("iron", 3)                 # a última linha cheia: não troca pra nv.1
    i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == "backpack")
    g.pop_events()
    assert not g.equip_from(i)
    assert ("backpack_not_empty",) in g.pop_events()
    assert g.equipment.has(C.BACKPACK_T2) and len(g.inventory) == 32 and g.inventory.count("backpack") == 1
    g.inventory.slots[31] = None                             # esvaziou: troca, e o inventário volta pra 24
    assert g.equip_from(i) and len(g.inventory) == 24
    assert g.equipment.has("backpack") and g.inventory.count(C.BACKPACK_T2) == 1


def test_unequip_t2_needs_both_rows_empty():
    g = state()
    assert equip_via_inventory(g, C.BACKPACK_T2) and len(g.inventory) == 32
    g.inventory.slots[20] = Stack("ice", 1)
    assert not g.unequip("backpack") and ("backpack_not_empty",) in g.pop_events()
    g.inventory.slots[20] = None
    assert g.unequip("backpack") and len(g.inventory) == 16 and g.inventory.count(C.BACKPACK_T2) == 1


def test_equip_item_by_hand_t2_with_full_rows_is_refused():
    g = state()
    g.equipment.equip(C.BACKPACK_T2)
    g.sync_backpack()
    g.inventory.slots[30] = Stack("iron", 1)
    assert g.equip_item("backpack") is None and g.equipment.has(C.BACKPACK_T2)   # recusado: nada sai


# ---- scanner -----------------------------------------------------------------------------------------
def test_scanner_still_gives_minimap():
    g = state()
    assert not g.has_scanner
    assert equip_via_inventory(g, "scanner") and g.has_scanner


# ---- save v17 ---------------------------------------------------------------------------------------
def test_save_roundtrip_t2_items_and_32_slots():
    g = state()
    for item in (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS):
        assert equip_via_inventory(g, item)
    g.inventory.slots[31] = Stack("ice", 7)
    data = save.state_to_dict(g)
    assert data["version"] == save.SAVE_VERSION == 17
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.equipment.slots == {"o2_tank": C.O2_TANK_T2, "scanner": None,
                                      "backpack": C.BACKPACK_T2, "boots": C.BOOTS}
    assert len(loaded.inventory) == 32 and loaded.inventory.slots[31] == Stack("ice", 7)
    assert loaded.o2_max == 400 and loaded.player_speed == pytest.approx(120 * 1.3)
    assert {C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS} <= loaded.equipped_ever


def test_from_data_rejects_wrong_slot():
    eq = Equipment.from_data({"o2_tank": C.BACKPACK_T2, "boots": "scanner", "backpack": C.BACKPACK_T2})
    assert eq.slots == {"o2_tank": None, "scanner": None, "backpack": C.BACKPACK_T2, "boots": None}


def test_v16_save_loads_and_migrates():
    g = state()
    assert equip_via_inventory(g, "backpack") and equip_via_inventory(g, "o2_tank")
    g.inventory.slots[23] = Stack("iron", 2)
    data = save.state_to_dict(g)
    data["version"] = 16
    data["progress"]["equipment"].pop("boots")               # o v16 não tinha o slot das botas
    data["progress"]["equipped_ever"].append("lixo")
    assert save.MIGRATIONS[16]({"version": 16, "x": 1}) == {"version": 16, "x": 1}   # nada a converter
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.equipment.slots == {"o2_tank": "o2_tank", "scanner": None, "backpack": "backpack", "boots": None}
    assert len(loaded.inventory) == 24 and loaded.inventory.slots[23] == Stack("iron", 2)
    assert loaded.equipped_ever == {"backpack", "o2_tank"}


# ---- render e UI -------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def renderer():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    from game.render import Renderer
    from game.assets import Sprites
    return Renderer(Sprites(enabled=False))


@pytest.mark.parametrize("item", SUIT_ITEMS)
def test_machine_preview_and_icon_of_suit_items(renderer, item):
    assert renderer.machine_preview(item).get_size() == (48, 48)
    assert renderer.item_icon(item).get_size() == (32, 32)
    assert renderer.item_icon("boots") is not None          # o fantasma do slot das botas (sem PNG: placeholder)


@pytest.mark.parametrize("size", [(480, 270), (640, 360), (960, 540)])
@pytest.mark.parametrize("t2", [False, True])
def test_tab_does_not_crash_with_4_slots_and_32(t2, size):
    """O layout de verdade é o Tab A (Task 5): aqui só não pode quebrar, nem perder slot."""
    from game.systems import Machine
    from game.ui import UI
    pygame.font.init()
    ui = UI()
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    g = state()
    for item in ((C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS) if t2 else ("backpack", "o2_tank")):
        assert equip_via_inventory(g, item)
    from game import art
    ui.begin()
    ui.draw_inventory(g.inventory, None, 0, lambda _i: art.icon("iron"), (0, 0), equipment=g.equipment, state=g)
    assert sorted(i for _, _, i in ui.slot_rects) == list(range(len(g.inventory)))
    assert {k for _, k in ui.equip_rects} == set(C.EQUIP_SLOTS)
    ui.begin()
    ui.draw_inventory(g.inventory, Machine("chest", 10, 10), 0, lambda _i: art.icon("iron"), (0, 0), state=g)
    assert sorted(i for _, inv, i in ui.slot_rects if inv is g.inventory) == list(range(len(g.inventory)))
    ui.begin()
    ui.draw_hud(g, 0.0, None, {r: art.icon(r) for r in C.RESOURCES}, item_icon=lambda _i: art.icon("iron"))
