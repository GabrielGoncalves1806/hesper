#!/usr/bin/env python3
"""v0.8 · Plantas (rodada 1) · cultivador, microscópio, centrífuga, coletor de água, ícones, gelo da porta do lab.
PROPOSTA: nada vai pra assets/sprites sem o ok do dono (quem copia é o gerente).

    python3 tools/sprites/v08_plantas.py          # sprites em reports/design/v08_plantas/pendentes/
    python3 tools/sprites/v08_plantas_report.py   # prévias + index.html

Família das máquinas: r3d (tools/sprites/r3d.py + machines_r3d.py), sapata B, corpo creme, faixa laranja #e2733a,
contorno #1b1630. Determinístico (sem aleatório), alpha só 0/255.

Cultivador = CORPO + MIOLO. O corpo (machine_cultivator*.png) já traz o tanque de vidro com o líquido, o substrato e
os anéis; o miolo (cultivator_crop_<cultura>_<etapa>.png, 40×56, mesmo (x, y) do corpo) só tem os pixels da planta, já
recortados pelo vidro (anel e tampa passam na frente). O jogo desenha corpo e depois miolo, no mesmo lugar.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import machines_r3d as MR  # noqa: E402
from r3d import CA, SA, Pal  # noqa: E402

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v08_plantas"
PEND = REP / "pendentes"
INK = "#1b1630"
OK, ALERT, CYAN, CYAN_L, CYAN_D = MR.OK, MR.ALERT, MR.CYAN, MR.CYAN_L, MR.CYAN_D
ORANGE, GOLD = MR.ORANGE, MR.GOLD
AMBER = "#f2c46d"

P_BEIGE, P_METAL, P_DARK, P_ORANGE, P_STEEL = MR.P_BEIGE, MR.P_METAL, MR.P_DARK, MR.P_ORANGE, MR.P_STEEL
P_SILVER, P_GLASS = MR.P_SILVER, MR.P_GLASS

# ---- vidro e líquido -----------------------------------------------------------------------------------------------
LIQ = ["#d2f7e6", "#a8e6cf", "#86ceba", "#66b0a6", "#4a8c8c"]          # nutriente verde-água (brilho → fundo)
P_LIQ = Pal(LIQ)
HI_WET, HI_DRY = "#f4fffa", "#8fb4c8"
P_LIQ_HI = Pal([HI_WET] * 5, emit=True, emit_tone=0)                 # risco de brilho do vidro (sobre o líquido)
P_EMPTY = Pal(["#4b6478", "#3a5266", "#2a3e52", "#1d2b3a", "#141f2c"])  # vidro sem líquido (escuro)
P_EMPTY_HI = Pal([HI_DRY] * 5, emit=True, emit_tone=0)
P_SOIL = Pal(["#8a6a52", "#6e523f", "#58402f", "#432f22", "#2e1f16"])
RING_ON = [Pal(["#e8ffd8"] * 5, emit=True, emit_tone=0), Pal([OK] * 5, emit=True, emit_tone=0),
           Pal(["#4fae5a"] * 5, emit=True, emit_tone=0)]
RING_OFF = Pal(["#6f8a7a", "#55705f", "#45604f", "#36493d", "#26332b"])
P_MAGIC = Pal(["#ff00ff"] * 5, emit=True, emit_tone=0)                  # marca a área do vidro (2ª passada)
MAGIC = (255, 0, 255)

FRONT = MR.FRONT
GZ0, GZ1, GR = 15.0, 44.0, 10.5           # vidro do cultivador: z de baixo, z de cima, raio
SUB_Z = GZ0 + 2.0                         # tampo do substrato (onde a planta pisa)
SUB_R = 6.0                               # raio do cesto de substrato no fundo do tanque


def ang_dist(a, b):
    d = (a - b) % (2 * math.pi)
    return np.minimum(d, 2 * math.pi - d)


def glass_paint(level_z, wet=True):
    """0 líquido/vidro, 1 risco de brilho. Acima do nível: 2 vidro vazio, 3 brilho do vazio."""
    def paint(th, z, cap):
        out = np.zeros(len(th), int)
        hi = (ang_dist(th, FRONT - 0.55) < 0.10) | (ang_dist(th, FRONT - 0.95) < 0.05)
        out[hi] = 1
        dry = z > level_z
        out[dry] = 2
        out[dry & hi] = 3
        if np.all(cap):
            out[:] = 2 if level_z < GZ1 else 0
        return out
    return paint


# =====================================================================================================================
# Cultivador
# =====================================================================================================================
def _cult_body(sc, style, lit, f, wet, glass_pal_override=None, broken=False):
    """Monta o cultivador na cena. style 'B' = base cheia (pedestal), 'A' = cilindro em pernas."""
    MR.base(sc, 16, 13)                                     # sapata B padrão (nv.1), corpo começa em z=5
    sc.dz = 0.0
    ring = RING_ON[[1, 0, 1, 2][f % 4]] if lit else RING_OFF
    if style == "B":
        z0 = 5.0
        # pedestal: tambor creme largo com faixa laranja, painel e o anel de luz em cima
        def ped(th, z, cap):
            out = np.zeros(len(th), int)
            out[(z > 9.0) & (z < 10.8) & ~cap] = 1
            fr = (ang_dist(th, FRONT + 0.05) < 0.42) & (z > 5.6) & (z < 8.6) & ~cap
            out[fr] = 2
            return out
        sc.cyl(0, 0, 13.0, z0, 13.2, P_BEIGE, paint=ped, extra=(P_ORANGE, P_DARK))
        sc.cyl(0, 0, 12.0, 13.2, 14.0, ring)                                     # anel de luz do pedestal
        sc.cyl(0, 0, 11.4, 14.0, GZ0, P_METAL)                                   # aro do pé do vidro
        # LEDs no painel do pedestal
        for k, c in enumerate(("#3a3549" if broken else (OK if (lit and f < 2) else "#2f5a2c") if wet else ALERT,
                               (CYAN if f % 2 == 0 else CYAN_D) if lit else "#2b4a5a")):
            sc.dot(-2 + k * 3, -13.3, 7.3, c, always=True)
    else:
        # A · pernas: cubo central baixo e 4 pernas dobradas até a sapata (a ref A)
        hub0 = 11.0
        sc.cyl(0, 0, 9.5, hub0, 14.4, P_BEIGE, paint=lambda t, z, c: np.where((z > 11.2) & (z < 12.6) & ~c, 1, 0),
               extra=(P_ORANGE,))
        sc.cyl(0, 0, 8.0, hub0 - 3.0, hub0, P_METAL, cap=False)
        sc.cyl(0, 0, 10.6, 14.4, 15.3, ring)
        sc.cyl(0, 0, 11.0, 15.3, GZ0, P_METAL)
        for a in (0.25, 0.75, 1.25, 1.75):
            ang = a * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            pts = [(ca * 8.5, sa * 8.5, 12.0), (ca * 13.0, sa * 10.5, 10.5), (ca * 13.2, sa * 10.0, 5.6)]
            sc.tube(pts, 1.5, P_STEEL)
        sc.dot(-1, -9.8, 11.9, (OK if (lit and f < 2) else "#2f5a2c") if wet else ALERT, always=True)
    # vidro (líquido + vazio) e substrato
    level = GZ1 - 2.5 if wet else GZ0 - 1
    gp = glass_pal_override
    if broken:
        return ring
    if gp is None:
        sc.cyl(0, 0, GR, GZ0, GZ1, P_LIQ, paint=glass_paint(level, wet), extra=(P_LIQ_HI, P_EMPTY, P_EMPTY_HI),
               cap=False)
    else:
        sc.cyl(0, 0, GR, GZ0, GZ1, gp, cap=False)
    # os 2 anéis do vidro são 2D (draw_rings): linha fina sem contorno, por cima da planta
    # tampa: tambor creme + faixa laranja + domo e válvula
    def capp(th, z, cap):
        out = np.zeros(len(th), int)
        out[(z > GZ1 + 1.4) & (z < GZ1 + 2.6) & ~cap] = 1
        return out
    sc.cyl(0, 0, GR + 1.2, GZ1, GZ1 + 3.6, P_BEIGE, paint=capp, extra=(P_ORANGE,))
    sc.cyl(0, 0, 7.5, GZ1 + 3.6, GZ1 + 5.0, P_BEIGE, r_top=5.0)
    sc.disc(0, 0, GZ1 + 5.05, 4.2, ring if lit else P_METAL, r_in=0.0)          # luz de cultivo no tampo
    sc.disc(0, 0, GZ1 + 5.1, 2.0, P_DARK)
    sc.dot(-5, -GR - 1.4, GZ1 + 1.2, (OK if f % 2 == 0 else "#2f5a2c") if lit else "#4a4458", always=True)
    return ring


def _cult_scene():
    return MR.scene(40, 56, -13)


SOIL_TOP = ["#8f6c50", "#7a5a42", "#a07a58"]
SOIL_SIDE = ["#4a3427", "#3a281d", "#5a4030"]
SOIL_SIDE_H = 4                           # altura da terra vista pelo vidro (px)


def paint_substrate(cv, mask):
    """Canteiro de terra no fundo do tanque, visto pelo vidro: faixa de terra (lado) que acompanha a curva do pé do
    vidro e o tampo da terra por cima (mais alto no meio, como uma elipse achatada). Só onde é vidro."""
    cols = [x for x in range(cv.w) if mask[:, x].any()]
    x0, x1 = cols[0], cols[-1]
    cx = (x0 + x1) / 2
    half = (x1 - x0) / 2 + 0.5
    foot = None
    for x in cols:
        ys = np.nonzero(mask[:, x])[0]
        bot = ys[-1]
        dx = (x - cx) / half
        top_h = 1 + int(round(2.2 * math.sqrt(max(0.0, 1 - dx * dx))))
        for k in range(SOIL_SIDE_H):
            y = bot - k
            if mask[y, x]:
                h = (x * 5 + y * 3) % 7
                cv.px(x, y, SOIL_SIDE[1] if k == 0 else SOIL_SIDE[2] if h == 0 else SOIL_SIDE[0])
        for k in range(top_h):
            y = bot - SOIL_SIDE_H - k
            if mask[y, x]:
                h = (x * 7 + y * 13) % 11
                c = SOIL_TOP[2] if (k == top_h - 1 and h < 3) else SOIL_TOP[1] if k == 0 else SOIL_TOP[0]
                cv.px(x, y, c)
        if abs(x - cx) < 0.6 or (foot is None and x >= cx):
            foot = (x, bot - SOIL_SIDE_H - 1)
    return foot                              # pé da planta: coluna do meio, linha do meio do tampo da terra


def glass_mask(style, lit, f, wet):
    sc = _cult_scene()
    _cult_body(sc, style, lit, f, wet, glass_pal_override=P_MAGIC)
    cv = sc.render()
    return np.all(cv.a[:, :, :3] == MAGIC, axis=2) & (cv.a[:, :, 3] == 255)


def bubbles(cv, mask, f, n=5):
    sc = _cult_scene()
    for i in range(n):
        x = int(sc.cx) - 7 + (i * 5) % 14
        y0 = int(sc.gy - (SUB_Z + 2) * CA)
        span = int((GZ1 - SUB_Z - 6) * CA)
        y = y0 - ((f * 4 + i * 7) % span)
        if 0 <= y < cv.h and mask[y, x]:
            cv.px(x, y, "#ffffff" if i % 2 else "#e8fff6")


def cultivator(style="B", lit=False, f=0, wet=True):
    """Corpo do cultivador (sem planta). Devolve (canvas, máscara do vidro, pé da planta)."""
    sc = _cult_scene()
    _cult_body(sc, style, lit, f, wet)
    cv = MR.render(sc)
    mask = glass_mask(style, lit, f, wet)
    foot = paint_substrate(cv, mask)
    if lit and wet:
        bubbles(cv, mask, f)
    draw_rings(cv, mask, lit)
    return cv, mask, foot


def draw_rings(cv, mask, lit, zs=(25.0, 35.0)):
    """Os 2 anéis de luz do vidro: arco da frente, 1 px, sem contorno (claro no meio, mais escuro nas pontas)."""
    sc = _cult_scene()
    cols = [x for x in range(cv.w) if mask[:, x].any()]
    cx = (cols[0] + cols[-1]) / 2
    half = (cols[-1] - cols[0]) / 2 + 0.5
    for z in zs:
        yc = sc.gy - z * CA
        for x in cols:
            dx = (x - cx) / half
            y = int(round(yc + GR * SA * math.sqrt(max(0.0, 1 - dx * dx)) - 0.5))
            if 0 <= y < cv.h and mask[y, x]:
                if lit:
                    c = "#e8ffd8" if abs(dx) < 0.35 else OK if abs(dx) < 0.8 else "#4fae5a"
                else:
                    c = "#8aa898" if abs(dx) < 0.35 else "#6f8a7a" if abs(dx) < 0.8 else "#55705f"
                cv.px(x, y, c)


def glass_highlight(body):
    """Pixels do risco de brilho do vidro (os da paleta de brilho): voltam por cima da planta."""
    keys = {MR.rgb(HI_WET)[:3], MR.rgb(HI_DRY)[:3]}
    return np.array([[tuple(int(v) for v in body.a[y, x, :3]) in keys for x in range(body.w)] for y in range(body.h)])


def compose_crop(body, mask, foot, plant_rgba):
    """Põe a planta (grade RGBA com o pé no meio da última linha) no tanque, recortada pela máscara do vidro; o
    risco de brilho e os anéis continuam na frente."""
    out = body.copy()
    h, w = plant_rgba.shape[:2]
    ox, oy = foot[0] - w // 2, foot[1] - h + 1
    keep = glass_highlight(body)                     # o risco do vidro fica na frente; os anéis, atrás da planta
    for y in range(h):
        for x in range(w):
            if plant_rgba[y, x, 3] == 0:
                continue
            X, Y = ox + x, oy + y
            if 0 <= X < out.w and 0 <= Y < out.h and mask[Y, X] and not keep[Y, X]:
                out.a[Y, X] = plant_rgba[y, x]
    return out


def crop_overlay(body, comp):
    """Miolo = só os pixels que a planta mudou (overlay transparente no resto)."""
    ov = MR.Canvas(body.w, body.h)
    diff = np.any(body.a != comp.a, axis=2)
    ov.a[diff] = comp.a[diff]
    return ov



P_FROSTP = Pal(["#ffffff", "#e9fbff", "#c8e8f4", "#a6ccdf", "#7fa6c2"])


# ---- cultivador quebrado (ruína do lab) ----------------------------------------------------------------------------
GLASS_BROKEN = ["#a9c4d2", "#7f9cb0", "#5a7488"]           # vidro sem líquido, sujo de geada (claro, meio, fundo)
DEAD = ["#8a6a4a", "#6a5038", "#4a3626"]                   # planta seca
FROST = ["#ffffff", "#d8f2ff", "#a6ccdf"]


def cultivator_broken():
    """Ruína do lab: o vidro quebrou na altura do 1º anel (lascas em pé na borda), a tampa sumiu, o tanque secou com a
    terra rachada e uma muda morta saindo pela boca; crosta de geada na borda e cacos na sapata. Sem luz nenhuma."""
    sc = _cult_scene()
    _cult_body(sc, "B", False, 0, False, broken=True)
    P_GB = Pal(["#e2eef4", "#b8ccd8", "#90a8b8", "#6a8294", "#4a5e70"])
    rim = 25.0
    sc.cyl(0, 0, GR, GZ0, rim, P_GB, paint=lambda t, z, c: np.where(ang_dist(t, FRONT - 0.55) < 0.10, 1, 0),
           extra=(Pal([HI_DRY] * 5, emit=True, emit_tone=0),), cap=False)
    sc.disc(0, 0, rim - 2.5, GR - 0.3, P_SOIL)                               # terra seca lá dentro
    # lascas de vidro em pé na borda (a de trás mais alta), cada uma uma placa fina inclinada
    for (a, h, w, tilt) in ((0.35, 7.0, 1.6, 0.10), (0.9, 4.0, 1.4, -0.12), (1.55, 9.0, 2.0, 0.05),
                            (2.2, 5.0, 1.5, 0.15), (2.75, 3.0, 1.2, 0.0), (4.1, 2.5, 1.4, 0.0), (5.6, 3.5, 1.3, -0.1)):
        x, y = math.cos(a) * GR, math.sin(a) * GR
        sc.obox((x, y, rim + h / 2), (w, 0.35, h / 2), P_GB, rot_z=a + math.pi / 2, rot_x=tilt)
    # crosta de geada em cima da borda
    for (a, r) in ((1.2, 1.5), (3.6, 1.7), (4.9, 1.3), (0.2, 1.2)):
        sc.rbox((math.cos(a) * GR, math.sin(a) * GR, rim + 0.4), (r, r * 0.8, 0.7), 0.4, P_FROSTP)
    # muda morta saindo pela boca
    for (pts, r) in (([(0.5, 1.0, rim - 2.5), (0.0, 0.5, rim + 4.0), (1.5, 0.0, rim + 8.0), (4.0, -0.5, rim + 9.0)], 0.55),
                     ([(0.0, 0.5, rim + 2.5), (-3.0, -0.5, rim + 5.0)], 0.45)):
        sc.tube(pts, r, Pal(["#a08060", "#8a6a4a", "#6a5038", "#4a3626", "#33241a"]))
    # cacos na sapata
    for (x, y) in ((-13.5, -10), (12.5, -9.5), (-10, -12)):
        sc.rbox((x, y, 5.3), (1.0, 0.7, 0.3), 0.2, P_GB)
    sc.dot(-3.6, -14.0, 3.5, "#3a3549", always=True)                          # LED da sapata apagado
    return MR.render(sc)


def _reoutline(cv):
    """Contorno #1b1630 em volta do que ficou sólido (o 2D novo encosta no contorno do r3d)."""
    cv.outline(INK)


# =====================================================================================================================
# Microscópio · entra gelo (funil à esquerda), sai amostra (frascos à direita). Braço em C, cabeça e lente ciano.
# =====================================================================================================================
P_ICE = MR.P_ICE
P_LENS = [Pal(["#ffffff", CYAN_L, CYAN, CYAN_D, "#1d4a66"], emit=True, emit_tone=t) for t in (1, 2)]
P_SCREEN_ON = Pal(["#1d3a3a"] * 5, emit=True, emit_tone=0)
P_VIAL = {"basic": Pal(["#e8ffd8", "#b6f0b0", OK, "#4fae5a", "#2f6a3a"]),
          "mutant": Pal(["#e8f4ff", "#a6c8ff", "#5f8ae0", "#3a5aa8", "#22306a"]),
          "rare": Pal(["#fff6d6", "#fff0b8", GOLD, "#b8823c", "#6e4a1e"])}


def microscope(f=0, lit=True, broken=False):
    sc = MR.scene(40, 56, -13)
    MR.base(sc, 16, 13)
    # bancada: caixa creme com faixa laranja e painel
    def bench(L, face):
        out = np.zeros(len(L), int)
        if face == 2:
            z = L[:, 2]
            out[(z > 1.0) & (z < 2.6)] = 1
        return out
    sc.box((-13, 13), (-9, 9), (5, 17), P_BEIGE, paint=bench, extra=(P_ORANGE,))
    MR.front_panel(sc, -11, -6, -9, 7, 12, f if lit else 3, leds=2 if (lit and not broken) else 1)
    # funil de gelo (entrada) atrás à esquerda
    sc.cyl(-8.5, 4, 3.0, 17, 22, P_METAL, r_top=4.6, cap=False)
    sc.disc(-8.5, 4, 21.0, 3.8, P_DARK)
    if not broken:
        sc.box((-10.2, -7.2), (2.6, 5.6), (20.0, 23.0), P_ICE)
        sc.box((-8.6, -6.4), (4.5, 6.6), (19.6, 21.8), P_ICE)
    # rack de amostras (saída) na frente à direita: 3 frasquinhos
    sc.box((4, 12), (-8, -3), (17, 18.6), P_METAL)
    for k, key in enumerate(("basic", "mutant", "rare")):
        if broken and k > 0:
            continue
        sc.cyl(5.8 + k * 2.8, -5.5, 1.0, 18.6, 23.0 - (k == 1) * 0.6, P_VIAL[key])
        sc.cyl(5.8 + k * 2.8, -5.5, 1.1, 23.0 - (k == 1) * 0.6, 24.0 - (k == 1) * 0.6, P_DARK)
    # platina (mesa da lâmina) e coluna em C
    sc.box((-6, 3), (-5, 2), (17, 18.6), P_METAL)
    sc.box((-4, 1), (-3.5, -0.5), (18.6, 19.2), P_LENS[0] if (lit and not broken) else P_STEEL)
    sc.box((-3, 2), (3, 8), (17, 41), P_BEIGE,
           paint=lambda L, face: np.where((face == 2) & (L[:, 2] > 5) & (L[:, 2] < 6.6), 1, 0), extra=(P_ORANGE,))
    tilt = 0.55 if broken else 0.0
    piv = (0.0, 5.0, 38.0)
    # cabeça + tubo da objetiva (no quebrado, tombados pra frente)
    def rot(p):
        if not tilt:
            return p
        y, z = p[1] - piv[1], p[2] - piv[2]
        c, s_ = math.cos(-tilt), math.sin(-tilt)
        return (p[0], piv[1] + y * c - z * s_, piv[2] + y * s_ + z * c)
    hc = rot((-0.5, 0.5, 40.0))
    sc.obox(hc, (4.2, 5.0, 3.6), P_BEIGE, rot_x=-tilt,
            paint=lambda L, face: np.where((face == 5) & (abs(L[:, 0]) < 1.6), 1, 0), extra=(P_ORANGE,))
    tb = rot((-0.5, -1.5, 31.5))
    sc.obox(tb, (1.8, 1.8, 5.0), P_STEEL, rot_x=-tilt)
    lens = rot((-0.5, -1.5, 26.2))
    sc.obox(lens, (2.0, 2.0, 0.6), (P_LENS[f % 2] if lit else MR.P_DARK) if not broken else P_DARK, rot_x=-tilt)
    # ocular em cima
    eye = rot((-0.5, 3.0, 45.0))
    sc.obox(eye, (1.4, 1.4, 2.2), P_DARK, rot_x=-0.5 - tilt)
    # monitor ao lado (direita), mostrando a célula
    sc.box((5, 13), (2, 5), (24, 34), P_DARK)
    sc.box((8, 10), (5, 7), (17, 24), P_METAL)
    if broken:
        for (x, z) in ((6.5, 32), (7.5, 31), (8.5, 30), (9.5, 30), (10.5, 29), (11.5, 28), (8.5, 28), (8.5, 27)):
            sc.dot(x, 1.8, z, "#7f8aa0", always=True)
        # geada na bancada e na platina
        for (x, y, z, r) in ((-4, -6, 18.5, 1.6), (1, -7, 17.6, 1.3), (-11, -7, 17.6, 1.4), (10, -7, 18.6, 1.1)):
            sc.rbox((x, y, z), (r, r * 0.8, r * 0.5), 0.4, P_FROSTP)
    else:
        scr = [(7, 32, CYAN), (8, 32, CYAN), (9, 32, CYAN), (10, 32, CYAN), (11, 32, CYAN)] if False else []
        cell = [(8.5, 30), (9.5, 30), (10.5, 30), (8.5, 29), (9.5, 29), (10.5, 29), (7.5, 29), (11.5, 29),
                (8.5, 28), (9.5, 28), (10.5, 28), (7.5, 28), (11.5, 28), (8.5, 27), (9.5, 27), (10.5, 27)]
        on = lit
        for (x, z) in cell:
            sc.dot(x, 1.8, z, (OK if (x + z + f) % 3 else "#b6f0b0") if on else "#2a4040", always=True)
        sc.dot(9.5, 1.8, 28.5, "#1d3a3a" if on else "#2a4040", always=True)
        if on:
            for k in range(4):
                sc.dot(6.5 + k * 2, 1.8, 25.5, CYAN if (k + f) % 4 < 2 else CYAN_D, always=True)
    return MR.render(sc)


# =====================================================================================================================
# Centrífuga · tambor com rotor de 4 braços (2 frascos verdes de alga, 2 de amostra) girando; torre de controle atrás
# =====================================================================================================================
P_ROTOR = Pal(["#d9dde6", "#a9b0be", "#8c93a3", "#636a7a", "#414553"])
P_ALGAE_V = Pal(["#e8ffd8", "#b6f0b0", "#7fc94f", "#4f9a3f", "#2f6b3a"])
P_SAMPLE_V = Pal(["#f0e0ff", "#b48cf0", "#7a4cc0", "#553490", "#36205e"])


def centrifuge(f=0, lit=True):
    sc = MR.scene(40, 56, -13)
    MR.base(sc, 16, 13)
    # corpo: caixa de cantos redondos com faixa laranja
    def body(L, N):
        out = np.zeros(len(L), int)
        fr = N[:, 1] < -0.9
        z = L[:, 2]
        out[fr & (z > -1.5) & (z < 0.2)] = 1
        return out
    sc.rbox((0, 0, 13.5), (13.5, 10.5, 8.5), 3.0, P_BEIGE, paint=body, extra=(P_ORANGE,))
    # torre de controle atrás à esquerda com tela
    sc.rbox((-8, 6.5, 28.0), (5.0, 3.5, 6.5), 1.2, P_BEIGE)
    sc.box((-11.5, -4.5), (2.6, 3.0), (25.5, 32.5), P_DARK)
    for k in range(3):
        sc.dot(-10 + k * 2, 2.4, 31, (ORANGE if k <= f % 3 else "#5a3a2a") if lit else "#3a3549", always=True)
    for k in range(5):
        sc.dot(-10.5 + k * 1.5, 2.4, 28 - (k % 2), OK if lit else "#2f5a2c", always=True)
    sc.dot(-9, 2.4, 26.5, CYAN if lit else "#2b4a5a", always=True)
    # boca do tambor: aro de aço, fundo escuro e o rotor
    sc.cyl(2.5, -1.0, 9.0, 21.5, 23.0, P_STEEL, cap=False)
    sc.disc(2.5, -1.0, 22.6, 8.4, P_DARK)
    ang0 = math.radians(f * 45.0)
    sc.cyl(2.5, -1.0, 2.2, 22.6, 25.2, P_ROTOR)
    for k in range(4):
        a = ang0 + k * math.pi / 2
        ex, ey = 2.5 + math.cos(a) * 5.2, -1.0 + math.sin(a) * 5.2
        sc.obox((2.5 + math.cos(a) * 2.8, -1.0 + math.sin(a) * 2.8, 24.0), (2.8, 0.9, 0.6), P_ROTOR, rot_z=a)
        sc.cyl(ex, ey, 1.6, 22.8, 26.0, P_ALGAE_V if k % 2 == 0 else P_SAMPLE_V)
        sc.cyl(ex, ey, 1.7, 26.0, 26.8, P_ROTOR)
    # tampa articulada aberta atrás do tambor (vidro fumê com aro)
    sc.obox((2.5, 9.6, 30.0), (8.6, 0.6, 7.0), MR.P_TUBE_EMPTY, rot_x=-0.15)
    sc.dot(-3.0, 9.0, 34.0, "#8fb4c8", always=True)
    sc.dot(-2.0, 9.0, 33.0, "#8fb4c8", always=True)
    sc.obox((2.5, 9.0, 23.4), (8.8, 1.0, 0.8), P_METAL)
    # painel da frente: visor de rotação e LEDs; aviso
    MR.front_panel(sc, 5, 11, -10.5, 9, 14, f if lit else 3, leds=2 if lit else 1)
    MR.warn(sc, -8, -10.5, 9)
    if lit:                                                    # traço de giro: risquinhos brancos na boca
        for k in range(3):
            a = ang0 + math.radians(20) + k * 2.1
            sc.dot(2.5 + math.cos(a) * 8.0, -1.0 + math.sin(a) * 8.0, 23.4, "#ffffff", always=True)
    return MR.render(sc)


# =====================================================================================================================
# Coletor de água · condensador de aletas no alto (orvalho), ventoinha no tampo, cápsula enchendo na doca da frente
# =====================================================================================================================
P_FIN = Pal(["#ffffff", "#e3e5ee", "#b9bccb", "#8f92a6", "#5e6176"])
P_WATER = MR.P_WATER
P_CAP_EMPTY = Pal(["#c8dce8", "#9fb8c8", "#7f98aa", "#5f788a", "#3f5466"])


def collector(f=0, lit=True, level=None):
    sc = MR.scene(40, 56, -13)
    MR.base(sc, 16, 13)
    def body(L, face):
        out = np.zeros(len(L), int)
        if face == 2:
            z = L[:, 2]
            out[(z > 5.0) & (z < 6.6)] = 1
        return out
    sc.box((-12.5, 12.5), (-9, 9), (5, 24), P_BEIGE, paint=body, extra=(P_ORANGE,))
    # condensador: pilha de aletas (disco de aço / fenda escura), com orvalho
    def fins(th, z, cap):
        out = np.zeros(len(th), int)
        out[(np.floor(z * 1.0) % 2 == 0) & ~cap] = 1
        return out
    sc.cyl(0, 2, 6.0, 24, 26, P_METAL)
    sc.cyl(0, 2, 9.0, 26, 41, P_FIN, paint=fins, extra=(P_DARK,), cap=False)
    sc.cyl(0, 2, 3.0, 26, 41, P_DARK)
    sc.cyl(0, 2, 9.6, 41, 43, P_BEIGE, paint=lambda t, z, c: np.where((z > 41.6) & (z < 42.6) & ~c, 1, 0),
           extra=(P_ORANGE,), cap=False)
    MR.fan(sc, 0, 2, 43.0, 7.2, f if lit else 0)
    if lit:                                                     # gotas de orvalho nas aletas
        for k in range(5):
            a = MR.FRONT - 0.9 + k * 0.45
            z = 28 + ((k * 5 + f * 3) % 12)
            sc.dot(9.3 * math.cos(a), 2 + 9.3 * math.sin(a), z, CYAN_L if (k + f) % 2 else "#ffffff")
    # doca da cápsula: nicho escuro na frente à esquerda, bico pingando, cápsula com água
    sc.box((-10.5, -1.5), (-9.6, -9.0), (7.5, 21), P_DARK)
    lv = (level if level is not None else [1, 2, 3, 4][f]) if lit else 0
    sc.cyl(-6, -10.6, 2.4, 9.5, 18.5, P_WATER, paint=lambda t, z, c: np.where(z > 9.5 + lv * 2.0, 1, 0),
           extra=(P_CAP_EMPTY,))
    sc.cyl(-6, -10.6, 2.5, 18.5, 19.5, P_METAL)
    sc.cyl(-6, -10.6, 2.5, 8.5, 9.5, P_METAL, cap=False)
    sc.box((-7.2, -4.8), (-11.6, -9.6), (20.3, 21.2), P_METAL)
    if lit:
        sc.dot(-6, -11.2, 20.0 - (f % 2), CYAN_L, always=True)
    # medidor de umidade (barras ciano) e LED à direita
    sc.box((2.5, 10.5), (-9.8, -9.0), (12, 19), P_DARK)
    for k in range(4):
        on = lit and k <= (f % 4)
        for j in range(2):
            sc.dot(4.0 + k * 2, -10.0, 13.5 + j, CYAN if on else "#2b4a5a", always=True)
    sc.dot(4.0, -10.0, 17.5, OK if lit else "#2f5a2c", always=True)
    sc.dot(6.0, -10.0, 17.5, CYAN if (lit and f % 2 == 0) else "#2b4a5a", always=True)
    return MR.render(sc)


CULTURES = ("algae", "plant_1", "plant_2", "plant_3")
FRAMES = 4


def save(cv, path):
    cv.save(path)


def build():
    import v08_icons as IC
    import v08_lab_ice as LI
    import v08_plants_art as PA
    PEND.mkdir(parents=True, exist_ok=True)
    (PEND / "anim").mkdir(exist_ok=True)
    (PEND / "_compare").mkdir(exist_ok=True)
    for old in PEND.glob("_test_*.png"):
        old.unlink()
    # cultivador: corpo parado, tira acesa, seco, quebrado e os 16 miolos
    body, mask, foot = cultivator("B", lit=False, f=0, wet=True)
    save(body, PEND / "machine_cultivator.png")
    MR.strip([cultivator("B", lit=True, f=i, wet=True)[0] for i in range(FRAMES)]).save(
        PEND / "anim" / "anim_machine_cultivator.png")
    save(cultivator("B", lit=False, f=0, wet=False)[0], PEND / "machine_cultivator_dry.png")
    save(cultivator_broken(), PEND / "machine_cultivator_broken.png")
    for name in CULTURES:
        for st in range(4):
            comp = compose_crop(body, mask, foot, PA.plant(name, st))
            save(crop_overlay(body, comp), PEND / f"cultivator_crop_{name}_{st}.png")
    # variante A (pernas), só pra comparar no report
    bA, mA, fA = cultivator("A", lit=False, f=0, wet=True)
    save(bA, PEND / "_compare" / "machine_cultivator_A.png")
    save(compose_crop(bA, mA, fA, PA.plant("plant_1", 3)), PEND / "_compare" / "cultivator_A_plant_1_3.png")
    MR.strip([cultivator("A", lit=True, f=i, wet=True)[0] for i in range(FRAMES)]).save(
        PEND / "_compare" / "anim_machine_cultivator_A.png")
    # microscópio
    save(microscope(0, lit=False), PEND / "machine_microscope.png")
    MR.strip([microscope(i, lit=True) for i in range(FRAMES)]).save(PEND / "anim" / "anim_machine_microscope.png")
    save(microscope(0, lit=False, broken=True), PEND / "machine_microscope_broken.png")
    # centrífuga
    save(centrifuge(0, lit=False), PEND / "machine_centrifuge.png")
    MR.strip([centrifuge(i, lit=True) for i in range(FRAMES)]).save(PEND / "anim" / "anim_machine_centrifuge.png")
    # coletor de água
    save(collector(0, lit=False), PEND / "machine_water_collector.png")
    MR.strip([collector(i, lit=True) for i in range(FRAMES)]).save(PEND / "anim" / "anim_machine_water_collector.png")
    # ícones
    for name, fn in IC.ICONS.items():
        Image.fromarray(fn()).save(PEND / f"{name}.png")
    Image.fromarray(IC.icon_water_capsule_empty(ROOT / "assets" / "sprites" / "icon_water_capsule.png")).save(
        PEND / "icon_water_capsule_empty.png")
    # gelo da porta do lab
    for name, cv in LI.all_stages().items():
        save(cv, PEND / f"{name}.png")


if __name__ == "__main__":
    build()
