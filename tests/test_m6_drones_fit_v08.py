"""v0.8 M6 Task 2: a seção DRONES do Cultivador, do Microscópio e da Centrífuga usa a fileira compacta do baú (botões
16×16, rótulo no vão) em todos os tamanhos, e o painel cabe na tela: nem os botões, nem a janela do lado (a linha de
ajuda vai embaixo dela) passam da moldura da hotbar. A Fundição continua com a fileira normal (22×22)."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from game import art, drones  # noqa: E402
from game import config as C  # noqa: E402
from game import ui as ui_mod  # noqa: E402
from game.systems import Machine  # noqa: E402
from game.ui import GRID_W, HELP_H, SLOT, UI  # noqa: E402
from tests.test_m5_chest_fit_v08 import SIZES, SUITS, suited  # noqa: E402

LAB = (C.CULTIVATOR, C.MICROSCOPE, C.CENTRIFUGE)
# o que vem logo antes da linha DRONES: no Cultivador os slots (y+114, 20) e o estado ao lado (até 2 linhas: y+107, +12,
# +14 de altura); no Microscópio e na Centrífuga a linha do estado + explicação (y+121, +14)
TEXT_BOTTOM = {C.CULTIVATOR: max(114 + 20, 107 + 12 + 14), C.MICROSCOPE: 121 + 14, C.CENTRIFUGE: 121 + 14}
CULT_STATUS = ("Crescendo", "Sem muda", "Fora da base vedada", "Sem água", "Colheita cheia")   # App.cultivator_label
# (estado, explicação) que o App monta (App.microscope_status/_info, App.centrifuge_status/_info)
LAB_LINES = [(st, "Metade: nada") for st in ("Analisando", "Sem gelo", "Saída cheia")] + \
            [(st, "Ritmo 100%") for st in ("Analisando", "Sem gelo", "Saída cheia")] + \
            [(st, "Alga + amostra") for st in ("Sem alga", "Sem amostra")] + \
            [(st, "Falha: perde as 2") for st in ("Girando", "Sem alga", "Saída cheia")]


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def wired(kind) -> Machine:
    m = Machine(kind, 10, 10)
    m.chip = "chip"
    m.sends = {i for i in C.LOGISTIC_ITEMS if drones.can_send(m, i)}
    m.receives = {i for i in C.LOGISTIC_ITEMS if drones.can_receive(m, i)}
    return m


def draw(ui, kind, size, suit):
    g = suited(suit)
    m = wired(kind)
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    ui.draw_inventory(g.inventory, m, 0, lambda _i: art.icon("iron"), (0, 0), state=g, status="Fora da base vedada",
                      info="Falha: perde as 2")
    return m, ui.hotbar_y - 11 - 1 - HELP_H


def cases():
    for kind in LAB:
        for size in SIZES:
            for suit in SUITS:
                yield pytest.param(kind, size, suit, id=f"{kind}-{size[0]}-{suit}")


@pytest.mark.parametrize("kind,size,suit", list(cases()))
def test_lab_panel_stays_above_the_hotbar_frame(ui, kind, size, suit):
    _m, frame = draw(ui, kind, size, suit)
    btns = [r for r, _ in ui.logistics_buttons]
    assert max(r.bottom for r in btns) <= frame, (max(r.bottom for r in btns), frame)
    assert ui.inv_window.bottom <= frame
    assert ui.side_window.bottom <= frame, (ui.side_window.bottom, frame)
    assert ui.side_window.bottom + HELP_H <= ui.hotbar_y - 11 - 1                 # a linha de ajuda acima da moldura


def test_cultivator_status_fits_beside_the_seed_slot(ui):
    """O estado do Cultivador vai à direita do MUDA, em até 2 linhas, sem cortar palavra nenhuma."""
    assert ui_mod.CULT_STATUS_X >= 2 * ui_mod.CULT_ROW_STEP + ui.font.size("MUDA")[0] + 2     # depois do rótulo MUDA
    assert ui_mod.CULT_ROW_STEP >= max(ui.font.size(t)[0] for t in ("CHEIAS", "VAZIAS")) + 2   # rótulos não encostam
    assert ui_mod.CULT_ROW_STEP >= SLOT + 4
    for status in CULT_STATUS:
        lines = ui_mod.wrap(ui.body, status, ui_mod.CULT_STATUS_W)
        assert len(lines) <= 2 and " ".join(lines) == status, (status, lines)
        assert all(ui.body.size(line)[0] <= ui_mod.CULT_STATUS_W for line in lines), (status, lines)


@pytest.mark.parametrize("status,info", LAB_LINES)
def test_lab_status_and_info_share_one_line_without_cutting(ui, status, info):
    assert ui.body.size(status)[0] + 8 + ui.body.size(info)[0] <= GRID_W, (status, info)


@pytest.mark.parametrize("kind", LAB)
def test_lab_rows_are_compact_and_keep_every_toggle(ui, kind):
    m, _frame = draw(ui, kind, (640, 360), "t2")
    sends = [i for i in C.LOGISTIC_ITEMS if drones.can_send(m, i)]
    recvs = [i for i in C.LOGISTIC_ITEMS if drones.can_receive(m, i)]
    toggles = [(r, v) for r, v in ui.logistics_buttons if v[0] in ("send", "recv")]
    batch = [(r, v) for r, v in ui.logistics_buttons if v[0] == "batch"]
    assert [v for _r, v in toggles] == [("send", i) for i in sends] + [("recv", i) for i in recvs]   # nenhum some
    assert len(batch) == len(C.DRONE_BATCH_OPTIONS)
    assert {(r.w, r.h) for r, _ in toggles} == {(ui_mod.LOGI_WIDE_BTN, ui_mod.LOGI_WIDE_BTN)}
    assert {(r.w, r.h) for r, _ in batch} == {(ui_mod.LOGI_BTN, ui_mod.LOGI_BATCH_H)}            # o Lote fica igual
    for rect, value in ui.logistics_buttons:                                                       # o clique acerta
        assert ui.logistics_at(rect.center) == value


@pytest.mark.parametrize("kind", LAB)
def test_lab_row_and_its_label_stop_before_the_chip(ui, kind):
    m, _frame = draw(ui, kind, (640, 360), "t2")
    chip = next(r for r, mm in ui.chip_rects if mm is m)
    x0 = chip.x + SLOT - GRID_W                                    # x da grade (o chip fica na ponta direita dela)
    room = GRID_W - (SLOT + 4)
    for kind_, label in (("send", "Envia"), ("recv", "Recebe")):
        row = [r for r, v in ui.logistics_buttons if v[0] == kind_]
        assert max(r.right for r in row) - x0 <= room
        n = len(row)
        assert ui_mod.wide_label_inline(n, room)                    # ≤ 5 itens: o vão do rótulo sempre existe
        label_right = n * (ui_mod.LOGI_WIDE_BTN + ui_mod.LOGI_WIDE_GAP) + 6 + ui.body.size(label)[0]
        assert label_right <= room, (kind_, label_right, room)


@pytest.mark.parametrize("kind", LAB)
def test_drones_line_does_not_overlap_the_text_above(kind):
    logi_y = {C.CULTIVATOR: ui_mod.CULT_LOGI_Y, C.MICROSCOPE: ui_mod.MIC_LOGI_Y, C.CENTRIFUGE: ui_mod.CENT_LOGI_Y}[kind]
    assert logi_y >= TEXT_BOTTOM[kind]


@pytest.mark.parametrize("kind", LAB)
def test_logistics_height_matches_what_is_drawn(ui, kind):
    m, _frame = draw(ui, kind, (640, 360), "t2")
    logi_y = {C.CULTIVATOR: ui_mod.CULT_LOGI_Y, C.MICROSCOPE: ui_mod.MIC_LOGI_Y, C.CENTRIFUGE: ui_mod.CENT_LOGI_Y}[kind]
    bottom = max(r.bottom for r, _ in ui.logistics_buttons)
    assert bottom - (ui.side_window.y + logi_y) == ui.logistics_height(m)
