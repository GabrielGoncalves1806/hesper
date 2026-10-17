"""v0.8 M5 Task 5: o Tab A (3 colunas: grades | TRAJE em coluna com 4 slots | detalhe) e os painéis laterais
com a Mochila T2 (32 slots). Medidas do mock aprovado (reports/design/v08_m5_itens/tab_A.png e lado_a_lado_A.png)."""

import os
import random
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from game import art, settings  # noqa: E402
from game import config as C  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from game.ui import BACKPACK_ROW_H, GRID_W, HELP_H, SLOT, TAB_INV_H, TAB_INV_W, UI, backpack_extra  # noqa: E402
from tests.helpers import give  # noqa: E402

SIZES = [(480, 270), (640, 360), (960, 540)]
SUITS = {
    "vazio": (),
    "nv1": ("backpack", "o2_tank"),
    "t2": (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS, "scanner"),
}
SIDE_KINDS = ("chest_small", "chest", "chest_large", "drill", C.SMELTER, C.COLLECTOR, C.CULTIVATOR, C.MICROSCOPE,
              C.CENTRIFUGE, C.DISPENSER, "drone_station", *C.MELTER_KINDS[:1])


def suited(name: str) -> GameState:
    g = GameState(rng=random.Random(5))
    for item in SUITS[name]:
        give(g, **{item: 1})
        i = next(k for k, s in enumerate(g.inventory.slots) if s and s.item == item)
        assert g.equip_from(i), item
    return g


def fill(g: GameState) -> None:
    for i in range(len(g.inventory)):
        g.inventory.slots[i] = Stack("iron", 40)


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def _icon(_item):
    return art.icon("iron")


def draw_tab(ui, size, g, mouse=(0, 0)):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    seen = []
    real = ui.text

    def spy(s, *a, **k):
        seen.append(s)
        return real(s, *a, **k)

    ui.text = spy
    try:
        ui.begin()
        ui.draw_inventory(g.inventory, None, 0, _icon, mouse, equipment=g.equipment, state=g)
    finally:
        del ui.text
    return seen


def row_top(ui, lo):
    return min(r.top for r, _, i in ui.slot_rects if lo <= i < lo + 8)


# ---- a altura que a mochila põe -------------------------------------------------------------------
def test_backpack_extra_is_one_row_h_per_backpack_row():
    assert backpack_extra(16) == 0
    assert backpack_extra(24) == BACKPACK_ROW_H
    assert backpack_extra(32) == 2 * BACKPACK_ROW_H == 64


# ---- Tab A -----------------------------------------------------------------------------------------
def test_window_constants_follow_the_mock():
    assert (TAB_INV_W, TAB_INV_H) == (446, 174)
    assert TAB_INV_W == 10 + GRID_W + 8 + 96 + 8 + 142 + 8


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("suit", list(SUITS))
def test_tab_a_three_columns(ui, size, suit):
    g = suited(suit)
    fill(g)
    draw_tab(ui, size, g)
    win = ui.inv_window
    assert (win.w, win.h) == (TAB_INV_W, TAB_INV_H)          # a janela não muda com a mochila
    assert pygame.Rect(0, 0, *size).contains(win)
    grids = [r for r, _, _ in ui.slot_rects]
    assert sorted(i for _, _, i in ui.slot_rects) == list(range(len(g.inventory)))
    right_of_grids = max(r.right for r in grids)
    suit_r, detail = ui.suit_rect, ui.detail_rect
    assert right_of_grids + 8 == suit_r.left and suit_r.w == 96
    assert suit_r.right + 8 == detail.left and detail.right == win.right - 8 and detail.w == 142
    assert suit_r.top == detail.top == win.top + 40 and suit_r.bottom == detail.bottom == win.bottom - 8
    for r in grids:
        assert win.contains(r) and r.bottom <= win.bottom - 8


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("suit", list(SUITS))
def test_suit_card_is_2x2_with_4_slots(ui, size, suit):
    g = suited(suit)
    draw_tab(ui, size, g)
    kinds = [k for _, k in ui.equip_rects]
    assert kinds == ["o2_tank", "scanner", "backpack", "boots"] == list(C.EQUIP_SLOTS)
    r = dict((k, rect) for rect, k in ui.equip_rects)
    assert r["o2_tank"].top == r["scanner"].top < r["backpack"].top == r["boots"].top
    assert r["o2_tank"].left == r["backpack"].left < r["scanner"].left == r["boots"].left
    for rect in r.values():
        assert ui.suit_rect.contains(rect) and rect.size == (SLOT, SLOT)
    assert r["o2_tank"].top == ui.suit_rect.top + 44


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("suit", list(SUITS))
def test_suit_texts_never_touch(ui, size, suit):
    """Rótulos e estados ("180 s", "400 s", "vazio"): dentro do cartão e com pelo menos 1 px de folga de tudo."""
    g = suited(suit)
    draw_tab(ui, size, g)
    texts = ui.suit_text_rects
    slots = [rect for rect, _ in ui.equip_rects]
    assert len(texts) >= 4
    for n, (s, a) in enumerate(texts):
        assert ui.suit_rect.contains(a), (s, a)
        grown = a.inflate(2, 2)                               # 1 px de folga em volta
        for b in slots:
            assert not grown.colliderect(b), (s, a, b)
        for s2, b in texts[n + 1:]:
            assert not grown.colliderect(b), (s, a, s2, b)


@pytest.mark.parametrize("suit, sub", [("nv1", "220 s"), ("t2", "400 s")])
def test_tank_shows_its_seconds_and_empty_slots_say_vazio(ui, suit, sub):
    g = suited(suit)
    seen = draw_tab(ui, (480, 270), g)
    assert sub in seen
    empty = sum(1 for k in C.EQUIP_SLOTS if not g.equipment.filled(k))
    assert seen.count("vazio") == empty
    assert "equipado" not in seen                              # o estado só aparece no tanque e nos vazios


@pytest.mark.parametrize("suit, label", [("vazio", None), ("nv1", "MOCHILA"), ("t2", "MOCHILA T2")])
def test_backpack_grid_label(ui, suit, label):
    seen = draw_tab(ui, (480, 270), suited(suit))
    grid_labels = [s for s in seen if s in ("MOCHILA", "MOCHILA T2")]
    # o rótulo do slot do traje ("MOCHILA") sempre aparece; o da grade só com a mochila equipada
    assert grid_labels.count("MOCHILA T2") == (label == "MOCHILA T2")
    assert grid_labels.count("MOCHILA") == 1 + (label == "MOCHILA")


@pytest.mark.parametrize("size", SIZES)
def test_t2_rows_go_on_top(ui, size):
    g = suited("t2")
    draw_tab(ui, size, g)
    assert row_top(ui, 16) < row_top(ui, 24) < row_top(ui, 8) < row_top(ui, 0)
    assert row_top(ui, 24) - row_top(ui, 16) == 22
    assert row_top(ui, 8) - row_top(ui, 16) == 2 * BACKPACK_ROW_H


def test_empty_slots_show_the_nv1_ghost(ui):
    g = suited("vazio")
    asked = []

    def icon(item):
        asked.append(item)
        return art.icon("iron")

    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    ui.begin()
    ui.draw_inventory(g.inventory, None, 0, icon, (0, 0), equipment=g.equipment, state=g)
    for rect, kind in ui.equip_rects:
        assert kind in asked
        ghost = next(s for s, pos in ui.native if pos == (rect.x * 2 + 4, rect.y * 2 + 4))
        assert ghost.get_alpha() == 45


@pytest.mark.parametrize("size", SIZES)
def test_inventory_and_logs_tabs_share_the_tab_bar(ui, size):
    """Trocar de aba não pula: a barra das abas fica no mesmo y e no mesmo centro."""
    g = suited("t2")
    draw_tab(ui, size, g)
    inv_bar = [r.copy() for r, _ in ui.inv_tab_rects]
    ui.begin()
    ui.draw_logs(g, 0, 0, (0, 0))
    logs_bar = [r.copy() for r, _ in ui.inv_tab_rects]
    assert [(r.y, r.h) for r in inv_bar] == [(r.y, r.h) for r in logs_bar]
    assert inv_bar[0].left == logs_bar[0].left and inv_bar[-1].right == logs_bar[-1].right


@pytest.mark.parametrize("size", SIZES)
def test_hovering_the_boots_slot_shows_the_boots(ui, size):
    g = suited("t2")
    draw_tab(ui, size, g)
    boots = next(r for r, k in ui.equip_rects if k == "boots")
    draw_tab(ui, size, g, boots.center)
    assert ui.detail_item == C.BOOTS


def side_machine(kind: str) -> Machine:
    from game import drones
    m = Machine(kind, 10, 10, resource="iron") if kind == "drill" else Machine(kind, 10, 10)
    if kind == "drone_station":
        m.station = drones.new_station(m, 0)
    return m


# ---- painéis laterais --------------------------------------------------------------------------------
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("kind", SIDE_KINDS)
def test_side_panels_with_32_slots(ui, size, kind):
    g = suited("t2")
    fill(g)
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    ui.draw_inventory(g.inventory, side_machine(kind), 0, _icon, (0, 0), state=g)
    mine = [r for r, inv, _ in ui.slot_rects if inv is g.inventory]
    assert sorted(i for _, inv, i in ui.slot_rects if inv is g.inventory) == list(range(32))
    assert ui.inv_window.h == 84 + 2 * BACKPACK_ROW_H == 148
    rects = [r for r, _, _ in ui.slot_rects]
    for n, a in enumerate(rects):
        assert pygame.Rect(0, 0, *size).contains(a), a
        for b in rects[n + 1:]:
            assert not a.colliderect(b), (a, b)
    for r in mine:
        assert ui.inv_window.contains(r)
    # a janela "Inventário" (e a linha de ajuda embaixo dela) nunca chega na moldura da hotbar
    frame = ui.hotbar_y - 11 - 1 - HELP_H
    assert max(r.bottom for r in mine) <= frame and ui.inv_window.bottom <= frame
    assert ui.notice_y + ui.NOTICE_H < ui.hotbar_y - 11 or ui.notice_y + ui.NOTICE_H <= ui.inv_window.top


@pytest.mark.parametrize("suit, label", [("nv1", "MOCHILA"), ("t2", "MOCHILA T2")])
def test_side_panel_backpack_label(ui, suit, label):
    g = suited(suit)
    seen = []
    real = ui.text
    ui.text = lambda s, *a, **k: seen.append(s) or real(s, *a, **k)
    try:
        ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
        ui.begin()
        ui.draw_inventory(g.inventory, Machine("chest", 10, 10), 0, _icon, (0, 0), state=g)
    finally:
        del ui.text
    assert label in seen


# ---- clique no 4º slot ------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_m5_tab_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def click(app, rect):
    from game import viewport
    (x, y, _, _), k, _ = viewport.ui_layout(app.window.get_size(), app.settings["ui_size"])
    pos = round(x + rect.centerx * k), round(y + rect.centery * k)
    app.mouse_window = pos
    app.mouse = app.window_to_canvas(pos)
    app.on_click(1)


def test_boots_slot_click_equips_and_unequips(app):
    s = app.state
    app.mode = "play"
    app.on_key(pygame.K_TAB)
    assert app.mode == "inventory"
    app.draw()
    boots = next(r for r, k in app.ui.equip_rects if k == "boots")
    app.held = Stack(C.BOOTS, 1)
    click(app, boots)
    assert s.equipment.slots["boots"] == C.BOOTS and app.held is None
    app.draw()
    click(app, next(r for r, k in app.ui.equip_rects if k == "boots"))   # mão vazia: tira
    assert not s.equipment.filled("boots") and s.inventory.count(C.BOOTS) == 1
    app.on_key(pygame.K_TAB)
