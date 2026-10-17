"""v0.8 M4 · mock dos painéis do Microscópio e da Centrífuga (2 candidatas por máquina).

So mock pro dono aprovar: nao escreve em assets/sprites nem em game/. Reaproveita o UIMock do mock aprovado do Cultivador
(`v08_plantas_report.py`), com as medidas REAIS de game/ui.py (SIDE_W 190, slot 20, botao de drone 22, LOGI_ROW 25...).
Saida: reports/design/v08_m4_paineis/*.png + index.html.   Rodar: python3 tools/sprites/v08_m4_paineis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v08_plantas_report as R  # noqa: E402
from v08_plantas_report import (ACCENT, B_CARD, B_CARD2, B_DIM, B_LINE, B_LINE2, B_MUTED, B_TEXT, B_TRACK, B_WELL,  # noqa: E402
                                B_WINDOW, CYAN_UI, GOLD_UI, OK_UI, SLOT, STEP, UIMock, icon)

OUT = R.ROOT / "reports" / "design" / "v08_m4_paineis"
PEND = R.PEND
SIDE_W, SIDE_MID = 190, 58
LOGI_BTN, LOGI_ROW, LOGI_COL, LOGI_BATCH_H = 22, 25, 52, 16
GW = 174                                                   # largura da grade (8 slots)

COL_BASIC, COL_MUT, COL_RARE = "#7fd6b0", "#5f7ee0", "#f2c46d"      # cor de cada amostra (do ícone)
COL_NADA = "#4f566b"
SAMPLES = (("SIMPLES", "30%", COL_BASIC, "icon_sample_basic"),
           ("MUTAÇÃO", "15%", COL_MUT, "icon_sample_mutant"),
           ("RARA", "5%", COL_RARE, "icon_sample_rare"))


def mix(c1, c2, t):
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def dark(img, k=90):
    a = img.copy()
    px = a.load()
    for y in range(a.height):
        for x in range(a.width):
            r, g, b, al = px[x, y]
            px[x, y] = (r * k // 255, g * k // 255, b * k // 255, al)
    return a


# ---- peças ----------------------------------------------------------------------------------------------------------
def hbar(m, x, y, w, frac, color, h=4):
    m.d.rectangle((x, y, x + w - 1, y + h - 1), fill=B_TRACK)
    fw = round(w * frac)
    if fw:
        m.d.rectangle((x, y, x + fw - 1, y + h - 1), fill=color)
        m.d.line((x, y, x + fw - 1, y), fill=mix(color, "#ffffff", 0.35))


def vbar(m, x, y, w, h, frac, color):
    m.d.rectangle((x, y, x + w - 1, y + h - 1), fill=B_TRACK)
    fh = round(h * frac)
    if fh:
        m.d.rectangle((x, y + h - fh, x + w - 1, y + h - 1), fill=color)
        m.d.line((x, y + h - fh, x + w - 1, y + h - fh), fill=mix(color, "#ffffff", 0.35))


def toggle(m, x, y, img, active, color):
    if active:
        m.rr(x, y, LOGI_BTN, LOGI_BTN, mix(B_WINDOW[:3] and "#0f1119", color, 0.20), color)
        m.d.line((x + 2, y + LOGI_BTN - 2, x + LOGI_BTN - 3, y + LOGI_BTN - 2), fill=color)
        m.icons.append((img, x * 2 + 6, y * 2 + 4))
    else:
        m.rr(x, y, LOGI_BTN, LOGI_BTN, B_WELL, B_LINE)
        m.icons.append((dark(img.resize((32, 32), Image.NEAREST)), x * 2 + 6, y * 2 + 6))


def drones(m, x, y, sends, recvs, batch=10, summary=""):
    """Seção DRONES como o jogo desenha (draw_logistics): linha, título, Envia, Recebe, Lote e o slot do CHIP."""
    m.d.line((x, y, x + GW - 1, y), fill=B_LINE)
    m.text(x, y + 3, "DRONES", CYAN_UI)
    m.text(x + 34, y + 1, "· " + summary, GOLD_UI, "body")
    ry = y + 14
    for label, rows, color in (("Envia", sends, ACCENT), ("Recebe", recvs, CYAN_UI)):
        m.text(x, ry + 2, label, B_MUTED, "body")
        for k, (name, on) in enumerate(rows):
            toggle(m, x + LOGI_COL + k * (LOGI_BTN + 3), ry, icon(name), on, color)
        ry += LOGI_ROW
    ry += 2
    m.text(x, ry + 1, "Lote", B_MUTED, "body")
    for k, n in enumerate((1, 5, 10, 20)):
        bx = x + LOGI_COL + k * (LOGI_BTN + 3)
        m.rr(bx, ry, LOGI_BTN, LOGI_BATCH_H, "#262b3b" if n == batch else B_WELL, ACCENT if n == batch else B_LINE)
        m.text(bx + LOGI_BTN // 2, ry + 1, str(n), B_TEXT if n == batch else B_MUTED, "body", "center")
    cx = x + GW - SLOT
    m.slot(cx, y + 14, icon("icon_chip"))
    m.text(cx + SLOT // 2, y + 14 + SLOT + 1, "CHIP", B_TEXT, "label", "center")


LOGI_H = 14 + 2 * LOGI_ROW + 2 + LOGI_BATCH_H                # 82, como no jogo


def card(m, x, y, w, h):
    m.rr(x, y, w, h, "#0d0f16", B_LINE2)


def machine_art(name, f=0, k=2):
    """O sprite da máquina (40×56 nativo) ×k, igual ao cilindro do Cultivador (×2 nativo = 40×56 na UI)."""
    if name == "machine_centrifuge":
        strip = Image.open(PEND / "anim" / "anim_machine_centrifuge.png").convert("RGBA")
        img = R.frame(strip, f)
    elif name == "machine_microscope":
        strip = Image.open(PEND / "anim" / "anim_machine_microscope.png").convert("RGBA")
        img = R.frame(strip, f)
    else:
        img = Image.open(PEND / f"{name}.png").convert("RGBA")
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def place_machine(m, name, x, y, f, k=2):
    art = machine_art(name, f, k)
    m.icons.append((art, x * 2, y * 2))                      # `icons` já está em px nativos; art é grande (não duplica)


def chance_strip(m, x, y, w=GW):
    """Faixa 'o que sai de cada gelo': NADA 50% | SIMPLES 30% | MUTAÇÃO 15% | RARA 5%."""
    segs = [("NADA", 50, COL_NADA), ("", 30, COL_BASIC), ("", 15, COL_MUT), ("", 5, COL_RARE)]
    cx = x
    for i, (name, pct, col) in enumerate(segs):
        sw = round(w * pct / 100) if i < len(segs) - 1 else x + w - cx
        m.d.rectangle((cx, y, cx + sw - 1, y + 9), fill=col)
        m.d.line((cx, y, cx + sw - 1, y), fill=mix(col, "#ffffff", 0.3))
        if i:
            m.d.line((cx, y, cx, y + 9), fill="#0f1119")
        cx += sw
    m.text(x + 4, y + 1, "NADA 50%", B_TEXT)


# ---- janelas -------------------------------------------------------------------------------------------------------
LX, RX = 21, 21 + SIDE_W + SIDE_MID


def frame_ui(m, y, side_h, mid_label_enabled=True):
    R.inv_panel(m, LX, y)
    mx, my = LX + SIDE_W + 4, y + 22
    m.rr(mx, my, SIDE_MID - 8, 40, B_WINDOW, B_LINE)
    for k, t in enumerate(("<<", "PEGAR", "TUDO")):
        m.text(mx + (SIDE_MID - 8) // 2, my + 7 + k * 9, t, B_TEXT, "label", "center")
    m.window(RX, y, SIDE_W, side_h)
    R.help_line(m, y + side_h + 7)


def title(m, y, name, right, color):
    m.text(RX + 8, y + 6, name, color, "body")
    m.text(RX + SIDE_W - 8, y + 8, right, B_MUTED, "label", "right")


def out_row(m, x, y, label, pct, col, img, count, active=True, dim_pct=False):
    """Slot de saída + legenda de duas linhas: nome (cor) e chance."""
    m.slot(x, y, img, count, hl=ACCENT if (active and count and False) else None)
    m.text(x + 24, y + 2, label, col if not dim_pct else B_MUTED)
    m.text(x + 24, y + 11, pct, col if not dim_pct else B_DIM)


# ---- microscópio -----------------------------------------------------------------------------------------------------
def micro_A(bg, path):
    m = UIMock(bg)
    y = 10
    gx = RX + 8
    H = 150 + LOGI_H + 10
    frame_ui(m, y, H)
    title(m, y, "Microscópio", "4 AMOSTRAS", CYAN_UI)
    top = y + 28
    m.text(gx, y + 17, "GELO", CYAN_UI)
    m.slot(gx, top, icon("icon_ice"), 14)
    m.text(gx, top + 24, "20 S", B_TEXT)
    m.text(gx + 29, y + 17, "ANÁLISE", OK_UI)
    vbar(m, gx + 40, top, 9, 56, 0.63, OK_UI)
    m.text(gx + 44, top + 59, "63%", B_TEXT, "label", "center")
    cx = gx + 68
    card(m, cx, y + 22, 44, 66)
    place_machine(m, "machine_microscope", cx + 2, y + 26, 1)
    hx = gx + 114
    m.text(hx, y + 17, "SAÍDA", GOLD_UI)
    for k, (label, pct, col, ic) in enumerate(SAMPLES):
        out_row(m, hx, top + k * 23, label, pct, col, icon(ic), (3, 1, None)[k])
    m.text(gx, y + 98, "CHANCE POR GELO", B_MUTED)
    chance_strip(m, gx, y + 108)
    m.text(gx, y + 123, "Analisando", OK_UI, "body")
    m.text(gx, y + 136, "Metade das análises não dá nada.", B_MUTED, "body")
    drones(m, gx, y + 156, [("icon_sample_basic", True), ("icon_sample_mutant", True), ("icon_sample_rare", True)],
           [("icon_ice", True)], 10, "envia 3 · recebe 1")
    m.finish(path)


def micro_B(bg, path):
    m = UIMock(bg)
    y = 8
    gx = RX + 8
    H = 138 + LOGI_H + 10
    frame_ui(m, y, H)
    title(m, y, "Microscópio", "4 AMOSTRAS", CYAN_UI)
    top = y + 28
    m.text(gx, y + 17, "ENTRA", CYAN_UI)
    m.slot(gx, top, icon("icon_ice"), 14)
    m.text(gx + 25, top + 3, ">", B_MUTED)
    bx = gx + 36
    bw = GW - 36 - 38
    m.text(bx, y + 17, "ANÁLISE 20 S", OK_UI)
    hbar(m, bx, top + 3, bw, 0.63, OK_UI, 5)
    m.text(bx, top + 10, "Analisando", OK_UI, "body")
    m.text(bx + bw, top + 18, "63%", B_TEXT, "label", "right")
    card(m, gx + GW - 32, y + 20, 32, 38)
    place_machine(m, "machine_microscope", gx + GW - 30, y + 23, 1, k=1)
    m.d.line((gx, y + 58, gx + GW - 1, y + 58), fill=B_LINE)
    m.text(gx, y + 63, "SAI DE CADA GELO", GOLD_UI)
    for k, (label, pct, col, ic) in enumerate(SAMPLES):
        m.text(gx + k * 60, y + 74, label, col)
        m.slot(gx + k * 60, y + 84, icon(ic), (3, 1, None)[k])
        m.text(gx + k * 60 + 24, y + 91, pct, col, "label")
    chance_strip(m, gx, y + 110)
    m.text(gx, y + 124, "Metade das análises não dá nada.", B_MUTED, "body")
    drones(m, gx, y + 138, [("icon_sample_basic", True), ("icon_sample_mutant", True), ("icon_sample_rare", True)],
           [("icon_ice", True)], 10, "envia 3 · recebe 1")
    m.finish(path)


# ---- centrífuga ------------------------------------------------------------------------------------------------------
PLANTS = (("FOLHA", "icon_plant_1", "Folha-gota"), ("ESPIRAL", "icon_plant_2", "Espiral-de-geada"),
          ("LÍRIO", "icon_plant_3", "Lírio-de-Ilves"))
CHANCE = {"basic": (60, 0, COL_BASIC, "icon_sample_basic", "simples"),
          "mutant": (45, 1, COL_MUT, "icon_sample_mutant", "mutação"),
          "rare": (30, 2, COL_RARE, "icon_sample_rare", "rara")}
PCT_BY_PLANT = ("60%", "45%", "30%")                      # chance de cada planta quando a amostra dela está no slot


def plant_row(m, x, y, k, sample, count):
    """Saída da centrífuga: o slot, o nome e a chance; acesa (cor da amostra) só a planta que a amostra atual dá."""
    name, ic, _ = PLANTS[k]
    active = CHANCE[sample][1] == k
    col = CHANCE[sample][2] if active else B_MUTED
    m.slot(x, y, icon(ic), count, hl=col if active else None)
    m.text(x + 24, y + 2, name, col if active else B_MUTED)
    m.text(x + 24, y + 11, PCT_BY_PLANT[k], col if active else B_DIM)


def plant_col(m, x, y, k, sample, count):
    """Versão em coluna (B): nome em cima, slot e a chance ao lado; acesa só a planta que a amostra atual dá."""
    name, ic, _ = PLANTS[k]
    active = CHANCE[sample][1] == k
    col = CHANCE[sample][2] if active else B_MUTED
    m.text(x, y, name, col)
    m.slot(x, y + 10, icon(ic), count, hl=col if active else None)
    m.text(x + 24, y + 17, PCT_BY_PLANT[k], col if active else B_DIM, "label")


def result_card(m, x, y, w, sample):
    pct, k, col, ic, sname = CHANCE[sample]
    m.rr(x, y, w, 26, B_CARD, mix("#141722", col, 0.6))
    m.icons.append((icon(ic), (x + 5) * 2, (y + 5) * 2))
    m.text(x + 26, y + 2, f"Amostra {sname}", col, "body")
    m.text(x + 26, y + 13, f"dá {PLANTS[k][2]}", B_TEXT, "body")
    m.text(x + w - 6, y + 9, f"{pct}%", col, "label", "right")


def centri_A(bg, path):
    m = UIMock(bg)
    y = 10
    gx = RX + 8
    H = 146 + LOGI_H + 10
    frame_ui(m, y, H)
    title(m, y, "Centrífuga", "5 PLANTAS", GOLD_UI)
    top = y + 28
    m.text(gx, y + 17, "ALGA", OK_UI)
    m.slot(gx, top, icon("icon_algae"), 5)
    m.text(gx, y + 52, "AMOSTRA", CYAN_UI)
    m.slot(gx, y + 62, icon("icon_sample_basic"), 2, hl=ACCENT)
    m.text(gx + 32, y + 17, "CICLO", OK_UI)
    vbar(m, gx + 40, top, 9, 56, 0.40, OK_UI)
    m.text(gx + 44, top + 59, "40%", B_TEXT, "label", "center")
    cx = gx + 68
    card(m, cx, y + 22, 44, 66)
    place_machine(m, "machine_centrifuge", cx + 2, y + 26, 2)
    hx = gx + 114
    m.text(hx, y + 17, "SAÍDA", GOLD_UI)
    for k, cnt in enumerate((4, 1, None)):
        plant_row(m, hx, top + k * 23, k, "basic", cnt)
    result_card(m, gx, y + 96, GW, "basic")
    m.text(gx, y + 123, "Girando", OK_UI, "body")
    m.text(gx + 56, y + 123, "30 s por ciclo", B_MUTED, "body")
    m.text(gx, y + 137, "Falhou: gasta alga e amostra.", B_MUTED, "body")
    drones(m, gx, y + 152, [("icon_plant_1", True), ("icon_plant_2", True), ("icon_plant_3", True)],
           [("icon_algae", True), ("icon_sample_basic", True), ("icon_sample_mutant", True), ("icon_sample_rare", False)],
           10, "envia 3 · recebe 3")
    m.finish(path)


def centri_B(bg, path):
    m = UIMock(bg)
    y = 6
    gx = RX + 8
    H = 148 + LOGI_H + 10
    frame_ui(m, y, H)
    title(m, y, "Centrífuga", "5 PLANTAS", GOLD_UI)
    top = y + 28
    m.text(gx, y + 17, "ALGA", OK_UI)
    m.slot(gx, top, icon("icon_algae"), 5)
    m.text(gx + 24, top + 3, "+", B_MUTED)
    m.text(gx + 34, y + 17, "AMOSTRA", CYAN_UI)
    m.slot(gx + 34, top, icon("icon_sample_mutant"), 1, hl=ACCENT)
    m.text(gx + 59, top + 3, ">", B_MUTED)
    bx = gx + 80
    bw = GW - 80 - 38
    m.text(bx, y + 17, "CICLO", OK_UI)
    hbar(m, bx, top + 3, bw, 0.40, OK_UI, 5)
    m.text(bx, top + 10, "Girando", OK_UI, "body")
    m.text(bx + bw, top + 18, "40% · 30 S", B_TEXT, "label", "right")
    card(m, gx + GW - 32, y + 20, 32, 38)
    place_machine(m, "machine_centrifuge", gx + GW - 30, y + 23, 2, k=1)
    m.d.line((gx, y + 58, gx + GW - 1, y + 58), fill=B_LINE)
    m.text(gx, y + 63, "SAÍDA", GOLD_UI)
    for k, cnt in enumerate((2, None, 1)):
        plant_col(m, gx + k * 60, y + 74, k, "mutant", cnt)
    result_card(m, gx, y + 110, GW, "mutant")
    m.text(gx, y + 140, "Falhou: gasta alga e amostra.", B_MUTED, "body")
    drones(m, gx, y + 154, [("icon_plant_1", True), ("icon_plant_2", True), ("icon_plant_3", True)],
           [("icon_algae", True), ("icon_sample_basic", True), ("icon_sample_mutant", True), ("icon_sample_rare", False)],
           10, "envia 3 · recebe 3")
    m.finish(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bg = R.scene_base("mist")
    micro_A(bg, OUT / "ui_microscopio_A.png")
    micro_B(bg, OUT / "ui_microscopio_B.png")
    centri_A(bg, OUT / "ui_centrifuga_A.png")
    centri_B(bg, OUT / "ui_centrifuga_B.png")
    print("ok")


if __name__ == "__main__":
    main()
