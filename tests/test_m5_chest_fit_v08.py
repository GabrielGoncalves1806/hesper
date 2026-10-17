"""v0.8 M5: o painel do baú (com a seção DRONES de 16 materiais) cabe na tela nos 3 tamanhos, com a mochila nv.1
e com a T2: nem os botões nem a linha de ajuda passam da moldura da hotbar. As máquinas não mudam (fileira normal)."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C  # noqa: E402
from game import ui as ui_mod  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from game.ui import GRID_W, HELP_H, UI  # noqa: E402
from tests.helpers import give  # noqa: E402

SIZES = [(480, 270), (640, 360), (960, 540)]
CHESTS = ("chest_small", "chest", "chest_large")
SUITS = {"nv1": ("backpack", "o2_tank"), "t2": (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS, "scanner")}


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def suited(name):
    g = GameState(rng=random.Random(5))
    for item in SUITS[name]:
        give(g, **{item: 1})
        i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == item)
        assert g.equip_from(i), item
    return g


@pytest.mark.parametrize("suit", SUITS)
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("kind", CHESTS)
def test_chest_panel_stays_above_the_hotbar_frame(ui, kind, size, suit):
    g = suited(suit)
    chest = Machine(kind, 10, 10)
    chest.sends = set(C.LOGISTIC_ITEMS)
    chest.receives = set(C.LOGISTIC_ITEMS)
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    ui.draw_inventory(g.inventory, chest, 0, lambda _i: art.icon("iron"), (0, 0), state=g)
    frame = ui.hotbar_y - 11 - 1 - HELP_H
    btns = [r for r, _ in ui.logistics_buttons]
    assert len(btns) == 2 * len(C.LOGISTIC_ITEMS) + len(C.DRONE_BATCH_OPTIONS)
    assert max(r.bottom for r in btns) <= frame, (max(r.bottom for r in btns), frame)
    assert ui.inv_window.bottom <= frame


def test_wide_row_is_16px_buttons_ten_per_line():
    assert ui_mod.LOGI_WIDE_BTN == 16 and ui_mod.LOGI_WIDE_COLS == 10
    assert 10 * ui_mod.LOGI_WIDE_BTN + 9 * ui_mod.LOGI_WIDE_GAP <= GRID_W
    assert ui_mod.wide_row_height(16) == 2 * (ui_mod.LOGI_WIDE_BTN + 2)   # o rótulo vai no vão da 2ª linha
    assert ui_mod.wide_row_height(8) == ui_mod.LOGI_WIDE_ROW             # 8 materiais: sem vão, rótulo em cima


def test_machine_rows_stay_normal(ui):
    ui.begin()
    ui.logistics_buttons.clear()
    m = Machine(C.SMELTER, 10, 10)
    m.chip = "chip"
    ui.draw_logistics(0, 0, GRID_W, m, lambda _i: art.icon("iron"), (0, 0))
    widths = {r.w for r, (k, *_x) in ui.logistics_buttons if k in ("send", "recv")}
    assert widths == {ui_mod.LOGI_BTN}
