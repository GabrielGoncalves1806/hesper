#!/usr/bin/env python3
"""v0.8 M5 · Materiais e itens · prévias, mock do Tab (traje com BOTAS, Mochila T2 A × B) e o index.html.

    python3 tools/sprites/v08_m5_itens.py          # 1º: sprites (pendentes/ e candidatas/)
    python3 tools/sprites/v08_m5_itens_report.py   # 2º: este (roda o 1º de novo, então basta este)

Mock com as medidas REAIS de game/ui.py (TAB_INV_W 346, TAB_INV_H 178, BACKPACK_ROW_H 32, GRID_W 174, SLOT 20,
passo 22, detalhe = do fim da grade até a borda, cartão do TRAJE em top+68...) e o UIMock do mock aprovado do
Cultivador (v08_plantas_report). Escala Grande = tela lógica 480×270 ampliada ×2.
Só LÊ assets/sprites/ e escreve em reports/design/v08_m5_itens/. Determinístico.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_sprites as B  # noqa: E402
import v08_m5_itens as I  # noqa: E402
import v08_plantas_report as R  # noqa: E402
import v08_m4_paineis as P4  # noqa: E402
from v08_plantas_report import (ACCENT, B_CARD, B_CARD2, B_DIM, B_LINE, B_LINE2, B_MUTED, B_TEXT, B_WELL,  # noqa: E402
                                CYAN_UI, GOLD_UI, OK_UI, SLOT, STEP, UIMock)

REP = I.REP
SPR = I.SPR
GRID_W = 8 * STEP - 2                       # 174
TAB_INV_W, TAB_INV_H, BACKPACK_ROW_H = 346, 178, 32
INV_CONTENT_Y = 40
HELP_H = 18
UW, UH = 480, 270
HOTBAR_Y = UH - 6 - SLOT                    # 244
B_DEEP, B_HOVER = "#0b0d13", "#232838"
ALERT = "#ff6a55"


def icon(name):
    for d in (I.PEND, I.CAND, SPR, R.PEND):
        p = d / f"{name}.png"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(name)


NAMES = {"fiber": "Fibra sintética", "hydrogel": "Gel hídrico", "frost_resin": "Resina de geada",
         "lily_essence": "Essência de Lírio", "backpack_t2": "Mochila T2", "o2_tank_t2": "Tanque de O₂ nv.2",
         "boots": "Botas de tração", "lamp_bio": "Luminária bio", "fertilizer": "Adubo", "drone_t2": "Drone nv.2"}


def window_top(h):
    return max(4, min((UH - h) // 2 - 8, HOTBAR_Y - 11 - 1 - HELP_H - h))


# ---- peças do Tab ---------------------------------------------------------------------------------------------------
def win(m, x, y, w, h, title, right):
    m.window(x, y, w, h)
    m.text(x + 8, y + 2 + 1, title, B_TEXT, "body")
    m.text(x + w - 8, y + 4 + 1, right, B_MUTED, "label", "right")


def tabs(m, x, y, w):
    labels = (("Inventário", 66), ("LOGs 3/7", 64))
    total = sum(lw for _, lw in labels) + 2
    sx = x + (w - total) // 2
    m.rr(sx, y + 20, total, 15, B_WELL, B_LINE)
    cx = sx + 1
    for k, (lb, lw) in enumerate(labels):
        if k == 0:
            m.rr(cx, y + 21, lw, 13, B_HOVER)
            m.d.line((cx + 4, y + 32, cx + lw - 5, y + 32), fill=ACCENT)
        m.text(cx + lw // 2, y + 21, lb, B_TEXT if k == 0 else B_MUTED, "body", "center")
        cx += lw
    m.d.point((cx - 6, y + 24), fill=ACCENT)


def grid(m, x, y, items, sel=None, n=8):
    for i in range(n):
        it = items[i] if i < len(items) else None
        name, cnt = it if it else (None, 0)
        m.slot(x + i * STEP, y, icon(f"icon_{name}") if name else None, cnt, hl=ACCENT if i == sel else None)


def label(m, x, y, txt, col=B_MUTED):
    m.text(x, y + 1, txt, col)


def chip(m, x, y, txt, col=GOLD_UI):
    """Selinho (pílula) com texto escuro: o '2X' da Mochila T2 (opção B)."""
    w = len(txt) * 5 + 5
    m.rr(x, y, w, 9, col)
    m.text(x + w // 2 + 1, y + 1, txt, "#1b1411", "label", "center")
    return w


def help_line(m, y, pairs, x0=None):
    widths = [len(k) * 5 + 6 + 4 + round(len(t) * 6.6) + 10 for k, t in pairs]
    x = x0 if x0 is not None else (UW - sum(widths)) // 2
    for (key, txt), w in zip(pairs, widths):
        kw = len(key) * 5 + 6
        m.rr(x, y, kw, 11, B_CARD2, B_LINE2)
        m.text(x + 3, y + 1, key, B_TEXT)
        m.text(x + kw + 4, y - 1, txt, B_MUTED, "body")
        x += w


def hotbar(m, items, sel=0, stack100=False):
    hx = (UW - GRID_W) // 2
    m.rr(hx - 4, HOTBAR_Y - 11, GRID_W + 8, SLOT + 15, (15, 17, 25, 236), B_LINE)
    for i in range(8):
        m.text(hx + i * STEP + SLOT // 2, HOTBAR_Y - 11, str(i + 1), ACCENT if i == sel else B_DIM, "label", "center")
    grid(m, hx, HOTBAR_Y, items, sel)


def explorer():
    sh = Image.open(SPR / "player_idle_down.png").convert("RGBA").crop((0, 0, 32, 32))
    return sh.resize((64, 64), Image.NEAREST)


def ghost(name):
    im = icon(f"icon_{name}").resize((32, 32), Image.NEAREST)
    a = np.array(im)
    a[:, :, 3] = (a[:, :, 3].astype(int) * 45 // 255).astype(np.uint8)
    return Image.fromarray(a)


def equip_slot(m, x, y, kind, item):
    m.slot(x, y, icon(f"icon_{item}") if item else None)
    if item:
        m.rr(x - 1, y - 1, SLOT + 2, SLOT + 2, None, CYAN_UI)
    else:
        m.icons.append((ghost(kind), x * 2 + 4, y * 2 + 4))


def status(m, x, y, sub, ok, right=False, col=None):
    col = col or (OK_UI if ok else B_DIM)
    if right:
        w = round(len(sub) * 6.4)
        m.d.rectangle((x - w - 5, y + 5, x - w - 3, y + 7), fill=col)
        m.text(x, y, sub, col, "body", "right")
    else:
        m.d.rectangle((x, y + 5, x + 2, y + 7), fill=col)
        m.text(x + 5, y, sub, col, "body")


def suit_card_wide(m, x, y, w, h, eq, badge=False):
    """TRAJE no cartão de hoje (174×62 embaixo das grades) com 4 slots: um em cada canto, rótulo e estado virados pra
    dentro (o Explorador no meio). Hoje são tanque/scanner dos lados e a mochila embaixo do corpo; com as BOTAS os
    rótulos de baixo batiam nos de cima, então cada slot ganha o seu canto."""
    m.rr(x, y, w, h, B_CARD)
    label(m, x + 6, y - 2, "TRAJE", CYAN_UI)
    ex, ey = x + w // 2 - 16, y + 6
    m.rr(ex - 2, ey + 30, 36, 3, B_DEEP)
    m.icons.append((explorer(), ex * 2, ey * 2))
    cells = (("o2_tank", "TANQUE", "180 s", 0, 0), ("scanner", "SCANNER", "equipado", 1, 0),
             ("backpack", "MOCHILA", "pilha ×2" if badge else "equipada", 0, 1), ("boots", "BOTAS", "equipadas", 1, 1))
    for kind, lab, sub, col, row in cells:
        item = eq.get(kind)
        sx = x + 8 if col == 0 else x + w - 28
        sy = y + 9 + row * 27
        equip_slot(m, sx, sy, kind, item)
        txt = sub if item else "vazio"
        c = (GOLD_UI if (badge and kind == "backpack") else OK_UI) if item else B_DIM
        if col == 0:
            m.text(sx + 24, sy + 2, lab, B_TEXT if item else B_MUTED)
            status(m, sx + 24, sy + 9, txt, bool(item), col=c)
        else:
            m.text(sx - 4, sy + 2, lab, B_TEXT if item else B_MUTED, "label", "right")
            status(m, sx - 4, sy + 9, txt, bool(item), right=True)


def suit_card_col(m, x, y, w, h, eq):
    """TRAJE em coluna (opção A): o Explorador em cima e os 4 slots em 2×2 embaixo, rótulo e estado em cada um."""
    m.rr(x, y, w, h, B_CARD)
    label(m, x + 6, y - 2, "TRAJE", CYAN_UI)
    ex, ey = x + w // 2 - 16, y + 6
    m.rr(ex - 2, ey + 30, 36, 3, B_DEEP)
    m.icons.append((explorer(), ex * 2, ey * 2))
    cells = (("o2_tank", "TANQUE", "180 s"), ("scanner", "SCANNER", ""),
             ("backpack", "MOCHILA", ""), ("boots", "BOTAS", ""))
    cw = (w - 4) // 2
    for k, (kind, lab, sub) in enumerate(cells):
        cx = x + 2 + (k % 2) * cw + cw // 2
        sy = y + 44 + (k // 2) * 40
        item = eq.get(kind)
        equip_slot(m, cx - SLOT // 2, sy, kind, item)
        m.text(cx, sy + 21, lab, B_TEXT if item else B_MUTED, "label", "center")
        sub = sub if item else "vazio"
        if sub:                                   # só o que diz alguma coisa (segundos do tanque, vazio)
            sw = len(sub) * 5
            col = OK_UI if item else B_DIM
            m.d.rectangle((cx - sw // 2 - 4, sy + 33, cx - sw // 2 - 2, sy + 35), fill=col)
            m.text(cx + 2, sy + 28, sub, col, "body", "center")
    # linhas do tanque e do scanner até o corpo (o mesmo desenho do cartão de hoje, curtinho)
    for k, (bxx, byy) in enumerate(((ex + 6, ey + 18), (ex + 26, ey + 22))):
        cx = x + 2 + k * cw + cw // 2
        sy = y + 44
        side = -1 if k == 0 else 1
        m.d.line((cx, sy - 2, cx, byy), fill=B_LINE2)
        m.d.line((cx, byy, bxx + (2 * side) * -1, byy), fill=B_LINE2)
        m.d.rectangle((bxx - 1 - side * 1, byy - 1, bxx + 1 - side * 1, byy + 1), fill=CYAN_UI)


def detail(m, x, y, w, h, item, count, maxs, uses, badge=False):
    m.rr(x, y, w, h, B_CARD)
    m.rr(x + 6, y + 6, 36, 36, B_WELL)
    big = icon(f"icon_{item}").resize((64, 64), Image.NEAREST)
    m.icons.append((big, (x + 8) * 2, (y + 8) * 2))
    m.text(x + 48, y + 5, NAMES.get(item, item), B_TEXT, "body")
    m.text(x + 48, y + 17, "RECURSO", CYAN_UI)
    m.text(x + 48, y + 26, f"{count} / {maxs}", B_MUTED, "body")
    if badge:
        chip(m, x + 48 + len(f"{count} / {maxs}") * 6 + 4, y + 28, "2X")
    m.d.line((x + 6, y + 48, x + w - 7, y + 48), fill=B_LINE)
    m.text(x + 6, y + 47, "USADO EM", B_MUTED)
    room = max(1, (h - 60) // 20)
    for i, it in enumerate(uses[:room]):
        yy = y + 58 + i * 20
        m.icons.append((icon(f"icon_{it}"), (x + 6) * 2, yy * 2))
        m.text(x + 26, yy + 1, NAMES[it], B_TEXT, "body")


EQ_T2 = {"o2_tank": "o2_tank_t2", "scanner": "scanner", "backpack": "backpack_t2", "boots": "boots"}
FIBER_USES = ["backpack_t2", "o2_tank_t2", "boots", "drone_t2"]
HOT = [("hand_drill_t2", 1), ("fiber", 12), ("hydrogel", 4), ("frost_resin", 3), ("water_capsule", 6),
       ("fertilizer", 2), ("lamp_bio", 3), ("ice", 40)]
INV = [("algae", 9), ("plant_1", 4), ("plant_2", 2), ("plant_3", 1), ("lily_essence", 1), ("iron", 22),
       ("silicon", 18), None]
BAG1 = [("copper", 31), ("iron_ingot", 12), ("drone_t2", 2), None, None, None, None, None]
BAG2 = [("ice", 50), ("silicon_wafer", 6), None, None, None, None, None, None]


def tab_current(bg, path):
    """O Tab como é hoje (Grande): referência pra comparar (só o slot de BOTAS a mais, vazio)."""
    m = UIMock(bg)
    w, h = TAB_INV_W, TAB_INV_H + BACKPACK_ROW_H
    x, y = (UW - w) // 2, window_top(h)
    win(m, x, y, w, h, "Inventário", "27/32")
    tabs(m, x, y, w)
    gx, top = x + 10, y + INV_CONTENT_Y
    label(m, gx, top, "MOCHILA", ACCENT)
    grid(m, gx, top + 10, BAG1)
    top += BACKPACK_ROW_H
    label(m, gx, top, "INVENTÁRIO")
    grid(m, gx, top + 10, INV)
    label(m, gx, top + 32, "HOTBAR")
    grid(m, gx, top + 42, HOT, sel=1)
    eq = {"o2_tank": "o2_tank", "scanner": "scanner", "backpack": "backpack", "boots": None}
    suit_card_wide(m, gx, top + 68, GRID_W, y + h - 8 - (top + 68), eq)
    dx = gx + GRID_W + 12
    detail(m, dx, y + INV_CONTENT_Y, x + w - 8 - dx, y + h - 8 - (y + INV_CONTENT_Y), "fiber", 12, 50, FIBER_USES)
    help_line(m, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")])
    hotbar(m, HOT, 1)
    m.finish(path)


def tab_B(bg, path):
    """Opção B: a mesma janela de hoje (346×210), Mochila T2 no slot da mochila, as pilhas de recurso no player vão a
    100. Onde o jogador vê: selo 2X no rótulo MOCHILA, no slot do traje e no detalhe (12 / 100)."""
    m = UIMock(bg)
    w, h = TAB_INV_W, TAB_INV_H + BACKPACK_ROW_H
    x, y = (UW - w) // 2, window_top(h)
    win(m, x, y, w, h, "Inventário", "27/32")
    tabs(m, x, y, w)
    gx, top = x + 10, y + INV_CONTENT_Y
    label(m, gx, top, "MOCHILA T2", ACCENT)
    chip(m, gx + 62, top, "PILHA 2X")
    big1 = [("copper", 100), ("iron_ingot", 12), ("drone_t2", 2), ("ice", 100), ("silicon", 64), None, None, None]
    grid(m, gx, top + 10, big1)
    top += BACKPACK_ROW_H
    label(m, gx, top, "INVENTÁRIO")
    grid(m, gx, top + 10, [("algae", 9), ("plant_1", 4), ("plant_2", 2), ("plant_3", 1), ("lily_essence", 1),
                           ("iron", 87), ("silicon", 100), None])
    label(m, gx, top + 32, "HOTBAR")
    hot = [("hand_drill_t2", 1), ("fiber", 12), ("hydrogel", 4), ("frost_resin", 3), ("water_capsule", 6),
           ("fertilizer", 2), ("lamp_bio", 3), ("ice", 100)]
    grid(m, gx, top + 42, hot, sel=1)
    suit_card_wide(m, gx, top + 68, GRID_W, y + h - 8 - (top + 68), EQ_T2, badge=True)
    dx = gx + GRID_W + 12
    detail(m, dx, y + INV_CONTENT_Y, x + w - 8 - dx, y + h - 8 - (y + INV_CONTENT_Y), "fiber", 12, 100, FIBER_USES,
           badge=True)
    help_line(m, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")])
    hotbar(m, hot, 1)
    m.finish(path)


def tab_A_naive(bg, path):
    """Opção A sem mexer no layout: +1 linha (2 da mochila) = 242 de altura. Passa da moldura da hotbar."""
    m = UIMock(bg)
    w, h = TAB_INV_W, TAB_INV_H + 2 * BACKPACK_ROW_H
    x, y = (UW - w) // 2, window_top(h)
    win(m, x, y, w, h, "Inventário", "28/40")
    tabs(m, x, y, w)
    gx, top = x + 10, y + INV_CONTENT_Y
    label(m, gx, top, "MOCHILA T2", ACCENT)
    grid(m, gx, top + 10, BAG1)
    grid(m, gx, top + 32, BAG2)
    top += 2 * BACKPACK_ROW_H
    label(m, gx, top, "INVENTÁRIO")
    grid(m, gx, top + 10, INV)
    label(m, gx, top + 32, "HOTBAR")
    grid(m, gx, top + 42, HOT, sel=1)
    suit_card_wide(m, gx, top + 68, GRID_W, y + h - 8 - (top + 68), EQ_T2)
    dx = gx + GRID_W + 12
    detail(m, dx, y + INV_CONTENT_Y, x + w - 8 - dx, y + h - 8 - (y + INV_CONTENT_Y), "fiber", 12, 50, FIBER_USES)
    hotbar(m, HOT, 1)
    help_line(m, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")])
    m.d.rectangle((x - 2, HOTBAR_Y - 12, x + w + 1, y + h + 1), outline=ALERT)
    m.text(x + w + 4, HOTBAR_Y - 30, "+32 PX:", ALERT, "label")
    m.text(x + w + 4, HOTBAR_Y - 21, "COBRE A", ALERT, "label")
    m.text(x + w + 4, HOTBAR_Y - 12, "HOTBAR", ALERT, "label")
    m.finish(path)


A_W = 10 + GRID_W + 8 + 96 + 8 + 142 + 8         # 446
A_H = INV_CONTENT_Y + 4 * BACKPACK_ROW_H - 2 + 8  # 174


def tab_A(bg, path):
    """Opção A reorganizada: 3 colunas. Grades (2 linhas da mochila + inventário + hotbar) | TRAJE em coluna
    (Explorador + 2×2) | detalhe. 446×174: mais larga, mas MAIS BAIXA que hoje (210)."""
    m = UIMock(bg)
    w, h = A_W, A_H
    x, y = (UW - w) // 2, window_top(h)
    win(m, x, y, w, h, "Inventário", "28/40")
    tabs(m, x, y, w)
    gx, top = x + 10, y + INV_CONTENT_Y
    label(m, gx, top, "MOCHILA T2", ACCENT)
    grid(m, gx, top + 10, BAG1)
    grid(m, gx, top + 32, BAG2)
    t2 = top + 2 * BACKPACK_ROW_H
    label(m, gx, t2, "INVENTÁRIO")
    grid(m, gx, t2 + 10, INV)
    label(m, gx, t2 + 32, "HOTBAR")
    grid(m, gx, t2 + 42, HOT, sel=1)
    cx = gx + GRID_W + 8
    ch = y + h - 8 - top
    suit_card_col(m, cx, top, 96, ch, EQ_T2)
    dx = cx + 96 + 8
    detail(m, dx, top, x + w - 8 - dx, ch, "fiber", 12, 50, FIBER_USES)
    help_line(m, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")])
    hotbar(m, HOT, 1)
    m.finish(path)


def side_A(bg, path):
    """Opção A nos painéis lado a lado (baú grande): a janela do inventário fica com 84 + 2×32 = 148 de altura; o baú
    já é mais alto (BAÚ 3 linhas + DRONES), então nada muda de lugar."""
    m = UIMock(bg)
    inv_h = 84 + 2 * BACKPACK_ROW_H
    chest_h = 26 + 3 * STEP + 8 + P4.LOGI_H + 12
    h = max(inv_h, chest_h)
    lx = (UW - (2 * P4.SIDE_W + P4.SIDE_MID)) // 2
    rx = lx + P4.SIDE_W + P4.SIDE_MID
    y = window_top(h)
    win(m, lx, y, P4.SIDE_W, inv_h, "Inventário", "28/40")
    gx, gy = lx + 8, y
    label(m, gx, gy + 16, "MOCHILA T2", ACCENT)
    grid(m, gx, gy + 26, BAG1)
    grid(m, gx, gy + 48, BAG2)
    gy += 2 * BACKPACK_ROW_H
    label(m, gx, gy + 16, "INVENTÁRIO")
    grid(m, gx, gy + 26, INV)
    label(m, gx, gy + 48, "HOTBAR")
    grid(m, gx, gy + 58, HOT, sel=1)
    mx, my = lx + P4.SIDE_W + 4, y + 22
    m.rr(mx, my, P4.SIDE_MID - 8, 40, (15, 17, 25, 246), B_LINE)
    for k, t in enumerate(("<<", "PEGAR", "TUDO")):
        m.text(mx + (P4.SIDE_MID - 8) // 2, my + 7 + k * 9, t, B_TEXT, "label", "center")
    win(m, rx, y, P4.SIDE_W, h, "Baú grande", "11/24")
    bx = rx + 8
    label(m, bx, y + 16, "BAÚ")
    chest = [("fiber", 40), ("hydrogel", 12), ("frost_resin", 9), ("lily_essence", 2), ("algae", 30), ("plant_1", 8),
             ("plant_2", 5), ("plant_3", 3), ("iron", 50), ("copper", 50), ("silicon", 44), None, None, None, None,
             None, None, None, None, None, None, None, None, None]
    for r in range(3):
        grid(m, bx, y + 26 + r * STEP, chest[r * 8:(r + 1) * 8])
    P4.drones(m, bx, y + 26 + 3 * STEP + 8, [("icon_algae", True), ("icon_plant_1", False)],
              [("icon_ice", True)], 10, "envia 1 · recebe 1")
    help_line(m, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade/1"), ("SHIFT+CLIQUE", "manda direto"),
                             ("ESC", "fecha")])
    hotbar(m, HOT, 1)
    m.finish(path)


# ---- prévias de sprite ----------------------------------------------------------------------------------------------
def cave_lamps(dark=True):
    """Caverna (chão/parede da névoa, como a prévia da lamp_t2) com as 3 luminárias: comum (raio 5), forte (7) e bio.
    Bio na prévia: raio 5, luz fria (150, 245, 215). Mesma ordem de desenho e escuridão do build_sprites."""
    spr = {p.name: Image.open(p).convert("RGBA") for p in SPR.glob("*.png")}
    spr["lamp_bio.png"] = Image.open(I.PEND / "lamp_bio.png").convert("RGBA")
    FL, RK = B.FL, B.RK
    W_, H_ = 30, 12
    g = [[FL] * W_ for _ in range(H_ + 1)]
    for yy in range(H_ + 1):
        for xx in range(W_):
            edge = yy <= 2 or xx in (0, 9, 10, 19, 20, W_ - 1) or yy == H_
            if yy == 3 and B.hsh(xx, yy, 5) < 0.3:
                edge = True
            if edge:
                g[yy][xx] = RK
    for (xx, yy) in ((3, 2), (6, 2), (13, 2), (16, 2), (23, 2), (26, 2)):
        g[yy][xx] = B.FE if xx % 3 == 0 else B.SI if xx % 3 == 1 else B.IC
    lamps = [((4, 7), "lamp.png"), ((14, 7), "lamp_t2.png"), ((24, 7), "lamp_bio.png")]
    T = 32
    img = Image.new("RGBA", (W_ * T, H_ * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 10), (0, 0, 0, 84))
    shade_b = Image.new("RGBA", (T, 6), (0, 0, 0, 40))
    for yy in range(H_):
        for xx in range(W_):
            if B.is_wall(g[yy][xx]):
                continue
            img.alpha_composite(spr[f"floor_mist_{int(B.hsh(xx, yy, 77) * 4)}.png"], (xx * T, yy * T))
            if yy > 0 and B.is_wall(g[yy - 1][xx]):
                img.alpha_composite(shade, (xx * T, yy * T))
                img.alpha_composite(shade_b, (xx * T, yy * T + 10))
    for yy in range(H_ + 1):
        for xx in range(W_):
            t = g[yy][xx]
            if B.is_wall(t):
                img.alpha_composite(spr[f"wall_mist_{int(B.hsh(xx, yy, 91) * 3)}.png"], (xx * T, yy * T - 24))
                if t in B.CAVE_ORE:
                    img.alpha_composite(spr[f"ore_{B.CAVE_ORE[t]}.png"], (xx * T, yy * T - 24))
                if yy + 1 <= H_ and yy + 1 < len(g) and not B.is_wall(g[yy + 1][xx]):
                    img.alpha_composite(spr["wall_face_mist.png"], (xx * T, yy * T + 8))
        for (lx, ly), name in lamps:
            if ly == yy:
                s_ = spr[name]
                img.alpha_composite(s_, (lx * T + 16 - s_.width // 2, (ly + 1) * T - s_.height))
    img = img.crop((0, 0, 960, 384))
    if not dark:
        return img.convert("RGB")
    lights = []
    for (lx, ly), name in lamps:
        if name == "lamp_bio.png":
            lights.append((lx * T + 16, ly * T + 8, 5 * T, I.BIO_LIGHT, 1.0))
        else:
            lights.append((lx * T + 16, ly * T + 8, (7 if "t2" in name else 5) * T, (255, 222, 184), 1.0))
    return B.apply_darkness(img, lights)[0]


def scene_items():
    """Cena 960×540 (base da névoa, a mesma das rodadas da v0.8) com as coisas novas no chão: 3 luminárias bio, os
    dois drones (nv.1 e nv.2) voando e o player. Mesma ordem de desenho do jogo (por y do pé)."""
    bg = R.scene_base("mist").convert("RGBA")
    lb = Image.open(I.PEND / "lamp_bio.png").convert("RGBA")
    d1 = Image.open(SPR / "drone.png").convert("RGBA").crop((0, 0, 16, 16))
    d2 = Image.open(I.PEND / "drone_t2.png").convert("RGBA").crop((16, 0, 32, 16))
    T = 32
    for (tx, ty) in ((5, 10), (13, 10), (21, 8)):
        bg.alpha_composite(lb, (tx * T + 16 - 8, (ty + 1) * T - 32))
    bg.alpha_composite(d1, (11 * T + 8, 10 * T - 2))
    bg.alpha_composite(d2, (12 * T + 20, 10 * T - 6))
    bg.alpha_composite(d2, (24 * T + 4, 8 * T + 2))
    return bg.convert("RGB")


def slot_sheet(names, k=2):
    """Os ícones como aparecem no jogo: dentro do slot (20 px lógicos) na escala ×2 (Grande)."""
    S = SLOT * k
    pad = 6 * k
    W = len(names) * (S + pad) + pad
    out = Image.new("RGBA", (W, S + 2 * pad), B.C("#0f1119"))
    from PIL import ImageDraw
    d = ImageDraw.Draw(out)
    for i, n in enumerate(names):
        x = pad + i * (S + pad)
        d.rectangle((x, pad, x + S - 1, pad + S - 1), fill="#0c0e15")
        d.rectangle((x + k, pad + k, x + S - 1 - k, pad + S - 1 - k), fill="#181c28")
        d.rectangle((x + 2 * k, pad + k, x + S - 1 - 2 * k, pad + 2 * k - 1), fill="#22273a")
        im = icon(n).resize((16 * k, 16 * k), Image.NEAREST)
        out.alpha_composite(im, (x + 2 * k, pad + 2 * k))
    return out


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def save_all():
    REP.mkdir(parents=True, exist_ok=True)
    bg = R.scene_base("mist")
    tab_current(bg, REP / "tab_hoje_botas.png")
    tab_B(bg, REP / "tab_B.png")
    tab_A_naive(bg, REP / "tab_A_sem_reorganizar.png")
    tab_A(bg, REP / "tab_A.png")
    side_A(bg, REP / "lado_a_lado_A.png")
    dk = cave_lamps()
    dk.save(REP / "caverna_luminarias_escuro.png")
    cx, cy = 24 * 32 + 16, 7 * 32 + 8
    dk.crop((cx - 80, cy - 56, cx + 80, cy + 56)).resize((480, 336), Image.NEAREST).save(REP / "caverna_bio_zoom.png")
    cave_lamps(False).save(REP / "caverna_luminarias_claro.png")
    scene_items().save(REP / "preview_base_mist.png")
    mats = ["icon_fiber", "icon_hydrogel", "icon_frost_resin", "icon_lily_essence"]
    items = ["icon_backpack_t2", "icon_o2_tank_t2", "icon_boots", "icon_lamp_bio", "icon_fertilizer", "icon_drone_t2"]
    slot_sheet(["icon_algae", "icon_plant_1", "icon_plant_2", "icon_plant_3", "icon_sample_basic", "icon_sample_rare"]
               + mats).save(REP / "slots_materiais.png")
    slot_sheet(["icon_backpack", "icon_o2_tank", "icon_scanner", "icon_lamp", "icon_drone"] + items).save(
        REP / "slots_itens.png")


# ---- report ---------------------------------------------------------------------------------------------------------
CSS = """
:root{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:0 16px}
.wrap{max-width:1020px;margin:0 auto;padding:40px 0 80px}
.eyebrow{font:12px ui-monospace,monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
h1{font:600 38px/1.1 ui-monospace,monospace;margin:10px 0 14px}h2{margin:44px 0 6px;color:var(--gold)}h3{margin:22px 0 6px}
p,li{color:var(--muted)}p b,li b{color:var(--fg)}
.note{background:var(--panel);border-left:4px solid var(--cyan);padding:12px 16px;margin:16px 0;border-radius:4px}
.rec{border-left-color:var(--ok)}
img.full{display:block;width:960px;max-width:100%;height:auto;image-rendering:pixelated;border:1px solid var(--line);border-radius:4px;margin:6px 0}
img.px{image-rendering:pixelated}
.chk{display:inline-flex;gap:14px;align-items:flex-end;padding:10px;background:repeating-conic-gradient(#2a211c 0 25%,#221a16 0 50%) 0 0/16px 16px;border-radius:4px}
.row{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;margin:8px 0}
figure{margin:0;background:var(--panel);border:1px solid var(--line);padding:8px;border-radius:4px}
figcaption{font:12px ui-monospace,monospace;color:var(--muted);margin-top:6px;max-width:360px}
.arrow{font:22px ui-monospace,monospace;color:var(--muted);align-self:center}
.pick{outline:2px solid var(--ok);outline-offset:2px}
.anim{image-rendering:pixelated;animation:a .27s steps(4) infinite}
@keyframes a{to{background-position:var(--end) 0}}
table{border-collapse:collapse;width:100%}td,th{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{background:var(--panel)}
code{background:var(--panel);padding:1px 5px;border-radius:3px;color:var(--gold)}
"""


def ic(name, cap, k=4, pick=False):
    p = next(d / f"{name}.png" for d in (I.CAND, I.PEND, SPR) if (d / f"{name}.png").exists())
    w, h = Image.open(p).size
    url = p.relative_to(REP).as_posix() if str(p).startswith(str(REP)) else f"../../../assets/sprites/{name}.png"
    return (f'<figure{" class=pick" if pick else ""}><div class="chk"><img class="px" src="{url}" width="{w}" height="{h}">'
            f'<img class="px" src="{url}" width="{w * k}" height="{h * k}"></div><figcaption>{cap}</figcaption></figure>')


def anim(url, k, cap, fps=15):
    w = 64
    return (f'<figure><div class="chk"><div class="anim" style="width:{16 * k}px;height:{16 * k}px;background:url({url}) 0 0/'
            f'{w * k}px {16 * k}px;--end:-{w * k}px;animation-duration:{4 / fps:.3f}s"></div></div><figcaption>{cap}</figcaption></figure>')


ARROW = '<span class="arrow">→</span>'


def write_html(ok):
    o = []
    a = o.append
    a(f'<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>v0.8 M5 · Materiais e itens</title><style>{CSS}</style></head><body><div class="wrap">')
    a('<div class="eyebrow">Hesper · Designer · v0.8 M5 · candidatas</div>')
    a('<h1>Materiais e itens</h1>')
    a('<div class="note rec"><b>Rodada 2 (2026-10-17):</b> o dono aprovou a <b>opção A reorganizada</b> do Tab. A rodada 2 traz o gel hídrico como bola de slime '
      'e os equipáveis do traje com volume (r3d): <a href="../v08_m5_itens_r2/index.html" style="color:#59d0e6">v08_m5_itens_r2</a>.</div>')
    a('<div class="note"><b>v1.0 · o que é isto:</b> a rodada de arte do marco "Materiais e itens" (bíblia §17, "Plantas viram material"). '
      '<b>Candidatas</b>, nada foi pro jogo: 4 materiais (fibra, gel, resina, essência; 2 ou 3 versões dos que têm dúvida de leitura), '
      '6 itens (Mochila T2, Tanque nv.2, Botas, Luminária bio, Adubo, Drone nv.2), a Luminária bio e o Drone nv.2 no mundo, e o mock do '
      'painel de equipamento com o slot novo de <b>BOTAS</b> e as duas opções da Mochila T2. A versão recomendada de cada ícone está em '
      '<code>pendentes/</code> com o nome do contrato; as outras em <code>candidatas/</code>. '
      f'Tamanhos: <b>{"todos no contrato (16×16, lamp_bio 16×32, drone_t2 64×16), alpha só 0/255 e a sombra" if ok else "COM PROBLEMA"}</b>. '
      'Referência de estilo: só os ícones aprovados do próprio jogo (v0.8 e os equipamentos); nada de fora.</div>')

    a('<h2>1 · Materiais (a planta aparece no material)</h2>')
    a('<p>Ampliados ×4 com o 1× do lado. Cada linha: a planta de origem (aprovada) → as candidatas → o ícone do jogo que pode confundir. '
      'Contorno <code>#1b1630</code>, faixas chapadas, um brilho, como os ícones da v0.8. Borda verde = recomendada.</p>')
    rows = [
        ("Fibra sintética", "icon_algae", "Alga",
         [("icon_fiber_A", "A · cone de fio: a fibra enrolada num cone de fiação, voltas verde-alga, tubinho creme e a ponta solta", True),
          ("icon_fiber_B", "B · novelo: bola de fio com a ponta solta", False),
          ("icon_fiber_C", "C · meada amarrada com a fitinha laranja do maço de alga", False)],
         ("icon_wire", "fio de cobre (carretel com abas): o cone não tem aba, não confunde")),
        ("Gel hídrico", "icon_plant_1", "Folha-gota",
         [("icon_hydrogel_A", "A · gota de gel gorda, achatada embaixo, bolhinhas presas e a folhinha da Folha-gota na ponta", True),
          ("icon_hydrogel_B", "B · potinho de vidro com tampa creme e faixa laranja", False)],
         ("icon_water_capsule", "cápsula de água: o pote B fica parecido demais com ela")),
        ("Resina de geada", "icon_plant_2", "Espiral-de-geada",
         [("icon_frost_resin_A", "A · pepita gorda (estilo minério chunky) azul da Espiral, a espiral presa dentro, crosta de geada em cima", True),
          ("icon_frost_resin_B", "B · gota de resina com capuz de geada", False)],
         ("icon_ice", "gelo: a resina é mais funda (azul da planta), lisa, com a espiral")),
        ("Essência de Lírio", "icon_plant_3", "Lírio-de-Ilves",
         [("icon_lily_essence_A", "A · frasco-balão: essência violeta (miolo do Lírio) com núcleo ciano aceso, anel dourado, rolha de cristal e brilhinhos", True),
          ("icon_lily_essence_B", "B · frasquinho facetado (joia) com a rolha em flor", False)],
         ("icon_sample_rare", "amostra rara: tubo de ensaio dourado; a essência é bojo redondo e violeta")),
    ]
    for title, plant, pname, cands, (nb, ncap) in rows:
        a(f'<h3>{title} · da {pname}</h3><div class="row">')
        a(ic(plant, f"{pname} (aprovada)"))
        a(ARROW)
        for n, cap, pick in cands:
            a(ic(n, cap, pick=pick))
        a(ic(nb, "vizinho: " + ncap))
        a('</div>')
    a('<div class="note rec"><b>Recomendação:</b> <b>fibra A</b> (o cone lê "fio industrial" e foge do maço de alga e do carretel de cobre; '
      'o novelo B em 16 px lê "repolho" e a meada C lê "laço de presente"); <b>gel A</b> (gota de gel; o pote B briga com a cápsula de água); '
      '<b>resina A</b> (a gota B fica com a mesma silhueta da gota de gel no mesmo inventário); <b>essência A</b> (lê "poção preciosa" na hora; '
      'o B é bonito mas pode ler "gema"). A essência é o único ícone violeta + dourado do jogo, pra parecer a coisa mais rara.</div>')
    a('<h3>Na escala do jogo (slot 20 px, escala Grande ×2)</h3>')
    a('<p>Alga, as 3 plantas e 2 amostras (aprovados) e, depois, os 4 materiais recomendados.</p>')
    a('<img class="px" src="slots_materiais.png" style="display:block;margin:6px 0">')

    a('<h2>2 · Itens</h2>')
    a('<p>Os nv.2 saem do nv.1 aprovado (mesma silhueta), com o <b>dourado <code>#f2c46d</code></b> das máquinas nv.2 e o material de que são feitos aparecendo: fibra verde, gel verde-azulado, resina azul.</p>')
    a('<div class="row">')
    a(ic("icon_backpack", "Mochila (hoje)"))
    a(ARROW)
    a(ic("icon_backpack_t2", "Mochila T2: rolo de fibra amarrado em cima com tiras douradas, aba de fibra trançada, fivela dourada, alças e bolsos de fibra; mais larga", True))
    a('</div><div class="row">')
    a(ic("icon_o2_tank", "Tanque de O₂ (hoje)"))
    a(ARROW)
    a(ic("icon_o2_tank_t2", "Tanque nv.2: cilindros com tampas, válvulas e anéis dourados, faixa no verde-azulado do gel, cinta de fibra", True))
    a('</div><div class="row">')
    a(ic("icon_boots", "Botas de tração: par de botas do traje (cano branco, faixa laranja, punho de fibra), biqueira dourada e sola grossa de resina azul com cravos", True))
    a(ic("icon_fertilizer", "Adubo: saquinho creme com a fitinha laranja, alga e bolhas de gel saindo da boca, rótulo com folha + gota", True))
    a('</div><div class="row">')
    a(ic("icon_lamp", "Luminária (hoje)"))
    a(ic("icon_lamp_t2", "Luminária forte (hoje)"))
    a(ARROW)
    a(ic("icon_lamp_bio", "Luminária bio: redoma de vidro com a resina acesa (fria) e a espiral, poste de fibra, sem LED nem fio", True))
    a('</div><div class="row">')
    a(ic("icon_drone", "Drone (ícone de hoje: quadricóptero)"))
    a(ARROW)
    a(ic("icon_drone_t2_A", "A · o ícone de hoje com faixa dourada, braços de fibra, hélices de resina e caixotinho de carga embaixo (carrega mais)", True))
    a(ic("icon_drone_t2_B", "B · o quadro 0 do drone_t2 de mundo (esférico), como ícone"))
    a('</div>')
    a('<div class="note"><b>Achado:</b> o <code>icon_drone.png</code> de hoje ainda é o quadricóptero antigo, mas o <code>drone.png</code> do mundo é o drone esférico do r3d. '
      'Por isso o ícone nv.2 tem duas candidatas: <b>A</b> segue o ícone de hoje (recomendo, pra hotbar ficar coerente com o nv.1), <b>B</b> segue o drone do mundo. '
      'Se o dono quiser alinhar ícone e mundo, o certo é refazer o <code>icon_drone</code> também (fica pra outra rodada).</div>')
    a('<h3>Na escala do jogo</h3><p>Os equipamentos de hoje (mochila, tanque, scanner, luminária, drone) e, depois, os 6 itens novos.</p>')
    a('<img class="px" src="slots_itens.png" style="display:block;margin:6px 0">')

    a('<h2>3 · No mundo</h2>')
    a('<h3>Luminária bio · <code>lamp_bio.png</code> 16×32</h3>')
    a('<div class="row">')
    a(ic("lamp", "lamp (hoje)", k=5))
    a(ic("lamp_t2", "lamp_t2 (hoje)", k=5))
    a(ic("lamp_bio", "lamp_bio: mesma sapata/poste/cabeça da família, mas a cabeça é uma redoma com a resina acesa dentro (espiral), poste embrulhado em fibra, faixa de fibra na sapata. Sem fio, sem LED.", k=5, pick=True))
    a('</div>')
    a('<p>Na caverna escura (mesma escuridão e ordem de desenho da prévia da luminária forte): comum (raio 5, quente), forte (raio 7, quente) e <b>bio (raio 5 na prévia, luz fria verde-azulada <code>(150, 245, 215)</code>)</b>.</p>')
    a('<img class="full" src="caverna_luminarias_escuro.png" width="960" height="384">')
    a('<img class="px" src="caverna_bio_zoom.png" width="480" height="336" style="display:block;border:1px solid #3a2c25;margin:6px 0">')
    a('<p style="font-size:13px">Zoom ×3 da bio acesa. Mesma cena com luz cheia, pra ver o sprite: <a href="caverna_luminarias_claro.png" style="color:#59d0e6">caverna_luminarias_claro.png</a>.</p>')
    a('<h3>Drone nv.2 · <code>drone_t2.png</code> 64×16 (4 quadros de 16×16, igual ao <code>drone.png</code>)</h3>')
    a('<div class="row">')
    a(anim("../../../assets/sprites/drone.png", 6, "drone (hoje) · 15 fps"))
    a(anim("pendentes/drone_t2.png", 6, "drone_t2 · 15 fps: o mesmo drone esférico (mesma cena r3d) com cinto DOURADO, aletas de resina azul e DOIS propulsores (voa mais rápido); olho e antenas iguais"))
    a(ic("drone_t2", "a tira (4 quadros)", k=4))
    a('</div>')
    a('<h3>Na base (névoa)</h3><p>Três luminárias bio no chão e os dois drones voando (o nv.1 perto do player, dois nv.2), em escala 1:1, mesma ordem de desenho.</p>')
    a('<img class="full" src="preview_base_mist.png" width="960" height="540">')

    a('<h2>4 · Painel de equipamento (aba Tab · Inventário)</h2>')
    a('<p>Escala Grande (tela lógica 480×270, ×2), medidas reais de <code>game/ui.py</code>: <code>TAB_INV_W</code> 346, <code>TAB_INV_H</code> 178, '
      '<code>BACKPACK_ROW_H</code> 32, grade 174, slot 20 e passo 22, detalhe do fim da grade até a borda, TRAJE em <code>top+68</code>. '
      'O detalhe mostra a Fibra com o "USADO EM" das receitas novas.</p>')
    a('<h3>O TRAJE com 4 slots (vale pras duas opções)</h3>')
    a('<p>Hoje: tanque e scanner dos lados do Explorador e a mochila embaixo do corpo. Com <b>BOTAS</b> os rótulos de baixo batiam nos estados de cima, '
      'então cada slot ganha um canto do cartão (rótulo e estado virados pra dentro): TANQUE e SCANNER em cima, MOCHILA e BOTAS embaixo. '
      'Mesmo cartão de 174×62, nada muda de altura. Abaixo, o Tab de hoje só com esse cartão novo (botas vazias, fantasma a 45 como os outros).</p>')
    a('<img class="full" src="tab_hoje_botas.png" width="960" height="540">')
    a('<h3>Opção B · mesma janela, as pilhas dobram</h3>')
    a('<p>Mesma janela de hoje (346×210), Mochila T2 no slot da mochila: <b>recurso empilha até 100 no player</b> (hotbar, inventário e mochila; baú continua 50). '
      'Como o jogador percebe: (1) o rótulo vira <b>MOCHILA T2</b> com o selo dourado <b>PILHA 2X</b>; (2) o estado da mochila no TRAJE diz <b>pilha ×2</b> em dourado; '
      '(3) o detalhe mostra <b>12 / 100</b> com o selo <b>2X</b>; (4) os números passam de 50 nos slots (o "100" ocupa o slot quase inteiro, ainda lê). '
      'Ao pegar a Mochila T2, um aviso "Pilhas dobradas: recursos até 100" fecha a conta.</p>')
    a('<img class="full" src="tab_B.png" width="960" height="540">')
    a('<h3>Opção A · +1 linha (2 linhas da mochila)</h3>')
    a('<p><b>Sem reorganizar não cabe:</b> 178 + 2×32 = 242 de altura; na Grande a janela já encosta no topo (y 4) e passa 32 px por cima da moldura da hotbar (vermelho).</p>')
    a('<img class="full" src="tab_A_sem_reorganizar.png" width="960" height="540">')
    a('<p><b>Reorganizada:</b> 3 colunas, com o TRAJE numa coluna própria (Explorador em cima, os 4 slots em 2×2). Fica <b>446×174</b>: mais larga, '
      'mas <b>mais baixa que a de hoje</b> (210), então sobra folga na Grande e nas outras escalas. O detalhe perde altura (3 linhas de "USADO EM" em vez de 5, o resto vira "+ N receitas" como hoje).</p>')
    a('<img class="full" src="tab_A.png" width="960" height="540">')
    a('<p>Nos painéis lado a lado (baú, máquinas) a janela do inventário vai de 116 pra <b>148</b> de altura. O painel do outro lado já é mais alto (baú grande ~194, cultivador 244), então nada muda de lugar:</p>')
    a('<img class="full" src="lado_a_lado_A.png" width="960" height="540">')
    a('<div class="note rec"><b>Recomendação: A reorganizada.</b> Na v0.8 o inventário ganha muita <b>variedade</b> (alga, 3 plantas, 3 amostras, 4 materiais, cápsulas cheias e vazias, adubo), '
      'e é variedade que lota slot; dobrar pilha (B) ajuda gelo e ferro, não isso. O layout de 3 colunas cabe com folga, fica até mais baixo, e o TRAJE em coluna '
      'deixa espaço pra mais equipamento no futuro (o filtro do traje da atualização do basalto). <b>B</b> é o caminho barato (zero layout, só a regra de pilha + o selo); '
      'se o dono escolher B, o selo PILHA 2X no rótulo + "12 / 100" no detalhe resolvem a leitura.</div>')

    a('<h2>Pro Dev integrar (depois do ok do dono)</h2><ul>')
    a('<li><b>Arquivos</b> (de <code>reports/design/v08_m5_itens/pendentes/</code> pra <code>assets/sprites/</code>, só os escolhidos): '
      '<code>icon_fiber</code>, <code>icon_hydrogel</code>, <code>icon_frost_resin</code>, <code>icon_lily_essence</code>, <code>icon_backpack_t2</code>, '
      '<code>icon_o2_tank_t2</code>, <code>icon_boots</code>, <code>icon_lamp_bio</code>, <code>icon_fertilizer</code>, <code>icon_drone_t2</code> (16×16, ícone de item, desenhados ×2 no slot como os outros); '
      '<code>lamp_bio.png</code> 16×32; <code>drone_t2.png</code> 64×16. Se o dono escolher B/C de algum, o PNG está em <code>candidatas/&lt;nome&gt;_&lt;letra&gt;.png</code> (renomear pro nome do contrato).</li>')
    a('<li><b>lamp_bio.png</b>: drop-in da <code>lamp.png</code> (<code>C.LAMP_SPRITE_SIZE</code> (16, 32) não muda): objeto de 1 tile, base na linha 29, centro x = 8, desenhada em '
      '<code>(tx*32 + 16 - 8, (ty+1)*32 - 32)</code>, ordem de desenho pelo pé como as outras. <b>Centro do brilho</b> = <code>(8, 7)</code> do PNG; o '
      '<code>lighting.lamp()</code> de hoje (<code>tx*T + 16, ty*T + 8</code>) já cai certo. Luz: <code>LAMP_RADIUS["lamp_bio"]</code> (sugiro 5, número decide o marco) e uma cor própria '
      'fria, <code>(150, 245, 215)</code>, em vez do <code>LAMP_COLOR</code> quente; sem flicker (sugestão: um "respirar" lento de intensidade 0,9–1,0 em ~3 s, se for barato). '
      'Sem energia: não entra na rede.</li>')
    a('<li><b>drone_t2.png</b>: mesmo contrato do <code>drone.png</code> (<code>C.DRONE_SPRITE</code> 16, 4 quadros lado a lado, 15 fps, mesmo balanço de flutuar e mesmo offset de desenho). '
      'Gerado pela mesma cena r3d do drone aprovado (<code>machines_r3d.drone</code>), só trocando cinto, aletas e propulsores.</li>')
    a('<li><b>Slot BOTAS</b>: <code>EQUIP_SLOTS</code> = ("o2_tank", "scanner", "backpack", "boots"), <code>EQUIP_LABEL["boots"] = "BOTAS"</code>. '
      'Mochila T2 e Tanque nv.2 ocupam o mesmo slot da nv.1 (o fantasma do slot vazio continua sendo o ícone nv.1). '
      'Cartão do TRAJE (opção B / layout de hoje): 4 slots nos cantos de <code>(gx, top+68, 174, 62)</code>: esquerda <code>x+8</code>, direita <code>x+w-28</code>, '
      'linhas <code>y+9</code> e <code>y+36</code>; rótulo em <code>sy+2</code> e estado (ponto 3×3 + texto) em <code>sy+9</code>, alinhados pra dentro (<code>sx+24</code> à esquerda, '
      'alinhado à direita em <code>sx-4</code> do lado direito). As linhas até o corpo saem.</li>')
    a('<li><b>Opção A (layout)</b>: janela <code>446×174</code> (= 10 + 174 + 8 + 96 + 8 + 142 + 8; altura 40 + 4×32 − 2 + 8). Coluna 1: MOCHILA T2 (2 linhas, '
      '<code>top+10</code> e <code>top+32</code>), INVENTÁRIO em <code>top+64</code>, HOTBAR em <code>top+96</code>. Coluna 2 (TRAJE, 96 de largura, de <code>top</code> até '
      '<code>y+h-8</code>): Explorador em <code>(x+32, y+6)</code>, slots 2×2 centrados em células de 46, linhas <code>y+44</code> e <code>y+84</code>, rótulo centrado em '
      '<code>sy+21</code>; estado só no tanque ("180 s") e nos vazios ("vazio"). Coluna 3: o detalhe de hoje com 142 de largura. Painéis lado a lado: '
      '<code>inv_h = SIDE_INV_H + 2×BACKPACK_ROW_H</code> (148), o resto igual.</li>')
    a('<li><b>Opção B (pilha)</b>: <code>max_stack</code> de recurso ×2 no inventário do player com a Mochila T2 equipada (baú não muda). Rótulo "MOCHILA T2" + selo dourado '
      '"PILHA 2X" (pílula <code>#f2c46d</code>, texto <code>#1b1411</code>) logo depois do rótulo; no TRAJE o estado da mochila "pilha ×2" em dourado; no detalhe o selo '
      '"2X" depois de "12 / 100". Tirar a mochila com pilha &gt; 50: o que sobra cai no chão/não deixa tirar (regra do Dev).</li>')
    a('<li><b>Cores novas</b> (só nos ícones): gel <code>#1f8a86/#3fc6b4/#8ff0dc</code>, brilho bio <code>#3fc6b4/#8ff0dc/#e0fff6</code>; o resto vem das paletas aprovadas '
      '(alga, Folha-gota, Espiral-de-geada, Lírio, equipamentos, dourado nv.2).</li>')
    a('<li><b>Gerar de novo</b>: <code>python3 tools/sprites/v08_m5_itens_report.py</code> (roda o <code>v08_m5_itens.py</code> antes). Determinístico. Não mexe em <code>assets/</code>.</li>')
    a('</ul></div></body></html>')
    (REP / "index.html").write_text("\n".join(o), encoding="utf-8")


if __name__ == "__main__":
    I.build()
    ok = I.check()
    save_all()
    write_html(ok)
    print("ok")
