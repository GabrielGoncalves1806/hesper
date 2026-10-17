"""Mochila (v0.5 M1 B3): equipamento do traje que dá +1 linha de 8 slots (16 -> 24)."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C  # noqa: E402
from game import drones, save  # noqa: E402
from game.inventory import Inventory, Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from game.ui import BACKPACK_ROW_H, HELP_H, UI  # noqa: E402
from tests.helpers import give  # noqa: E402

BASE, FULL = C.INVENTORY_SLOTS, C.INVENTORY_SLOTS + C.BACKPACK_SLOTS


def with_backpack() -> GameState:
    g = GameState(rng=random.Random(3))
    give(g, backpack=1)
    assert g.equip_from(next(i for i, s in enumerate(g.inventory.slots) if s and s.item == "backpack"))
    return g


def fill_base(g: GameState, item: str = "silicon") -> None:
    for i in range(BASE):
        g.inventory.slots[i] = Stack(item, 50)


# ---- equipar ----------------------------------------------------------------------------------
def test_recipe_is_a_suit_item_and_slots_start_at_16():
    m = C.MACHINES["backpack"]
    assert m.cost == {"iron_ingot": 5} and not m.placeable and C.MACHINE_CATEGORY["backpack"] == "suit"
    assert "backpack" in C.EQUIP_SLOTS and C.EQUIP_LABEL["backpack"] == "MOCHILA" and C.BACKPACK_SLOTS == 8
    g = GameState(rng=random.Random(3))
    assert len(g.inventory) == BASE and not g.has_backpack


def test_craft_and_equip_gives_eight_slots():
    g = GameState(rng=random.Random(3))
    give(g, iron_ingot=5)
    assert not g.craft("backpack")                       # a receita é da Bancada T2, não do fabricador T1
    assert g.craft("backpack", "t2")
    i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == "backpack")
    assert g.equip_from(i)
    assert g.has_backpack and len(g.inventory) == FULL == 24
    assert g.inventory.count("backpack") == 0 and ("equip", "backpack") in g.pop_events()
    assert all(s is None for s in g.inventory.slots[BASE:])


def test_equip_by_hand_also_grows_the_inventory():
    g = GameState(rng=random.Random(3))
    assert g.equip_item("backpack") is None and len(g.inventory) == FULL


# ---- itens indo pra linha extra ----------------------------------------------------------------
def test_without_backpack_nothing_goes_past_16():
    g = GameState(rng=random.Random(3))
    fill_base(g)
    assert not g.inventory.has_space("iron") and g.inventory.add("iron", 5) == 5
    assert len(g.inventory) == BASE


def test_add_and_has_space_use_the_extra_row_only_with_backpack():
    g = with_backpack()
    fill_base(g)
    assert g.inventory.has_space("iron", C.BACKPACK_SLOTS * C.STACK_RESOURCE)
    assert not g.inventory.has_space("iron", C.BACKPACK_SLOTS * C.STACK_RESOURCE + 1)
    assert g.inventory.add("iron", 60) == 0
    assert g.inventory.slots[BASE] == Stack("iron", 50) and g.inventory.slots[BASE + 1] == Stack("iron", 10)
    assert g.inventory.count("iron") == 60


def test_drone_station_collect_uses_the_extra_row():
    g = with_backpack()
    g.debug_add_ti()
    st = Machine("drone_station", 60, 70)
    st.station = drones.new_station(st, 0)
    g.machines.append(st)
    fill_base(g)
    st.station.buffer = {"iron": 70}
    assert g.collect_station(st) == 70                       # com 16 slots lotados não entraria nada
    assert g.inventory.count("iron") == 70 and st.station.buffer == {}


def test_take_all_from_chest_uses_the_extra_row():
    g = with_backpack()
    fill_base(g)
    chest = Inventory(C.CHEST_SLOTS)
    chest.add("ice", 120)
    assert chest.transfer_all(g.inventory) == 120
    assert g.inventory.count("ice") == 120 and chest.is_empty()
    plain = GameState(rng=random.Random(3))
    fill_base(plain)
    chest.add("ice", 120)
    assert chest.transfer_all(plain.inventory) == 0          # sem mochila não cabe nada


def test_guardar_tudo_takes_from_the_extra_row():
    g = with_backpack()
    g.inventory.slots[BASE + 2] = Stack("iron", 40)
    chest_inv = Inventory(C.CHEST_SLOTS)
    assert g.inventory.transfer_all(chest_inv, items={"iron"}) == 40
    assert chest_inv.count("iron") == 40 and g.inventory.count("iron") == 0


def test_crafting_spends_the_extra_row_first():
    g = with_backpack()
    g.inventory.slots[0] = Stack("iron", 5)
    g.inventory.slots[BASE] = Stack("iron", 5)
    assert g.inventory.remove("iron", 5) == 5
    assert g.inventory.slots[0] == Stack("iron", 5) and g.inventory.slots[BASE] is None


# ---- tirar a mochila ---------------------------------------------------------------------------
def test_unequip_with_empty_extra_row_shrinks_back():
    g = with_backpack()
    assert g.unequip("backpack")
    assert len(g.inventory) == BASE and not g.has_backpack and g.inventory.count("backpack") == 1


def test_unequip_blocked_when_extra_row_has_items():
    g = with_backpack()
    g.inventory.slots[BASE + 3] = Stack("ice", 7)
    g.pop_events()
    assert not g.unequip("backpack")
    assert g.has_backpack and len(g.inventory) == FULL and g.inventory.slots[BASE + 3] == Stack("ice", 7)
    assert ("backpack_not_empty",) in g.pop_events()


def test_unequip_needs_room_in_the_base_slots():
    g = with_backpack()
    fill_base(g)
    g.pop_events()
    assert not g.unequip("backpack") and len(g.inventory) == FULL
    assert ("inv_full",) in g.pop_events()
    g.inventory.slots[0] = None
    assert g.unequip("backpack") and g.inventory.slots[0] == Stack("backpack", 1)


def test_app_turns_the_event_into_the_notice():
    from game import app
    src = open(app.__file__, encoding="utf-8").read()
    assert '"backpack_not_empty"' in src and 'show_notice("Esvazie a mochila primeiro")' in src


# ---- save ----------------------------------------------------------------------------------------
def test_save_roundtrip_keeps_backpack_and_extra_row():
    g = with_backpack()
    g.inventory.slots[BASE] = Stack("iron", 33)
    g.inventory.slots[FULL - 1] = Stack("ice", 4)
    loaded = save.state_from_dict(save.migrate(save.state_to_dict(g)))
    assert loaded.has_backpack and len(loaded.inventory) == FULL
    assert loaded.inventory.slots[BASE] == Stack("iron", 33) and loaded.inventory.slots[FULL - 1] == Stack("ice", 4)
    assert "backpack" in loaded.equipped_ever
    assert loaded.unequip("backpack") is False                # a linha ainda tem item


def test_save_without_backpack_has_16_slots_and_v8_loads():
    g = GameState(rng=random.Random(3))
    give(g, iron=5)
    data = save.state_to_dict(g)
    assert data["version"] == save.SAVE_VERSION and len(data["inventory"]["slots"]) == BASE
    data["progress"]["equipment"].pop("backpack", None)       # v8 de antes da mochila não tinha a chave
    loaded = save.state_from_dict(save.migrate(data))
    assert not loaded.has_backpack and len(loaded.inventory) == BASE and loaded.inventory.count("iron") == 5


def test_save_with_extra_row_but_no_backpack_does_not_lose_items():
    g = with_backpack()
    g.inventory.slots[BASE] = Stack("iron", 9)
    data = save.state_to_dict(g)
    data["progress"]["equipment"]["backpack"] = None          # save estragado à mão
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.inventory.count("iron") == 9                # não encolhe com item lá dentro


# ---- layout ----------------------------------------------------------------------------------------
SIZES = [(480, 270), (640, 360), (960, 540)]


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def _icon(_item):
    return art.icon("iron")


def _assert_clear(ui, size, bottom):
    rects = [r for r, _, _ in ui.slot_rects] + [r for r, _ in ui.equip_rects]
    for n, a in enumerate(rects):
        assert a.left >= 0 and a.top >= 0 and a.right <= size[0] and a.bottom <= size[1], a
        for b in rects[n + 1:]:
            assert not a.colliderect(b), (a, b)
    assert max(r.bottom for r in rects) <= bottom
    assert ui.notice_y + ui.NOTICE_H < ui.hotbar_y - 11


def with_t2() -> GameState:
    """Mochila T2 (32 slots), tanque nv.2 e botas (v0.8 M5)."""
    g = GameState(rng=random.Random(3))
    for item in (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS):
        give(g, **{item: 1})
        assert g.equip_from(next(i for i, s in enumerate(g.inventory.slots) if s and s.item == item))
    return g


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("suit", ["none", "nv1", "t2"])
def test_tab_inventory_layout(ui, size, suit):
    """Tab A (v0.8 M5): grades | TRAJE (4 slots em 2×2) | detalhe, com 16, 24 e 32 slots."""
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = {"none": lambda: GameState(rng=random.Random(1)), "nv1": with_backpack, "t2": with_t2}[suit]()
    ui.begin()
    ui.draw_inventory(s.inventory, None, 0, _icon, (0, 0), equipment=s.equipment, state=s)
    assert sorted(i for _, _, i in ui.slot_rects) == list(range(len(s.inventory)))
    assert [k for _, k in ui.equip_rects] == ["o2_tank", "scanner", "backpack", "boots"]
    assert len(s.inventory) == {"none": BASE, "nv1": FULL, "t2": FULL + 8}[suit]

    def row_top(lo):
        return min(r.top for r, _, i in ui.slot_rects if lo <= i < lo + 8)

    if suit != "none":                                        # a(s) linha(s) da mochila (16–31) ficam em cima da 8–15
        assert row_top(16) < row_top(8) < row_top(0)
        assert row_top(8) - row_top(16) == BACKPACK_ROW_H * (len(s.inventory) - BASE) // 8
    # 3 colunas: as grades, o TRAJE e o detalhe, nessa ordem e sem encostar
    grids_right = max(r.right for r, _, _ in ui.slot_rects)
    assert grids_right < ui.suit_rect.left < ui.suit_rect.right < ui.detail_rect.left
    for r, _ in ui.equip_rects:
        assert ui.suit_rect.contains(r)
    # janela + linha de ajuda nunca passam da moldura da hotbar
    _assert_clear(ui, size, ui.hotbar_y - 11 - 1 - HELP_H - 8)
    assert ui.inv_window.bottom + HELP_H <= ui.hotbar_y - 11 - 1


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("backpack", [False, True])
def test_chest_panel_layout_shows_extra_row(ui, size, backpack):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = with_backpack() if backpack else GameState(rng=random.Random(1))
    chest = Machine("chest", 10, 10)
    ui.begin()
    ui.draw_inventory(s.inventory, chest, 0, _icon, (0, 0), state=s)
    mine = sorted(i for _, inv, i in ui.slot_rects if inv is s.inventory)
    assert mine == list(range(len(s.inventory)))
    _assert_clear(ui, size, ui.hotbar_y - 11 - 1 - HELP_H)
