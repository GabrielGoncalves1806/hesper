#!/usr/bin/env python3
"""Hesper v0.7 M4 · rodada 7: roupa de cama do beliche caprichada, 5 mesas novas (r3d) e o microscópio refeito (A/B).

- prop_wall_bunk: a plataforma, os cabos com esticador e a sombra são os da r6 (aprovados); muda só a cama: travesseiro
  com volume e afundado, fronha com a aba dobrada, lençol com a dobra virada na cabeceira, rugas e caimento pela borda,
  cobertor laranja desbotado por cima com textura de tecido (pesponto em losango) e barra.
- mesas: prop_briefing_table (redonda 2×2 com telas no tampo, consoles na borda e o holo apagado no centro),
  prop_mess_table (refeitório 2×1 com bancos), prop_repair_bench (bancada de manutenção 2×1 com ferramentas),
  prop_nav_table (mesa de navegação 1×1 com tela inclinada e carta), prop_side_table (mesinha de canto 1×1 com caneca).
- prop_microscope A/B (floor 1×1, 32×40, mesmo contrato da v0.7 M2).

Sufixo _r7 (candidatas _r7_A/_r7_B). Rode depois do r4, r5 e r6 (usa a casca e os props aprovados deles).
Determinístico, alpha só 0/255 (a sombra de chão no nível fixo do kit).

Saída: reports/design/v07_m4/pendentes/<id>_r7*.png + icon_<id>_r7*.png ;
       reports/design/v07_m4/sala_r7_{cabine,alojamento,apoio}_{clara,escura}.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chests_r3d as CH  # noqa: E402
import build_vesper_v07 as V  # noqa: E402
import build_vesper_v07_r2 as R2  # noqa: E402
import build_vesper_v07_r4 as R4  # noqa: E402
import build_vesper_v07_r6 as R6  # noqa: E402
from r3d import SA, Pal, Scene  # noqa: E402

PEND, REP, T, OUT = V.PEND, V.REP, V.T, V.OUT
SL, SLD, CR, OR, SCR, GO = R4.SL, R4.SLD, R4.CR, R4.OR, R4.SCR, R4.GO
DIM, LEDR, LEDO, LEDG = R4.DIM, R4.LEDR, R4.LEDO, R4.LEDG
S6, grid, cut, alpha_ok, SHADOW = R6.S6, R6.grid, R6.cut, R6.alpha_ok, R6.SHADOW
MATT, BLANK, BLANK_D, STEEL, DIMC = R6.MATT, R6.BLANK, R6.BLANK_D, R6.STEEL, R6.DIMC
SHEET = Pal(["#ffffff", "#eae8f2", "#d2cee0", "#aca7c2", "#827d9c"])            # lençol (branco frio)
CASE = Pal(["#f6ecda", "#e4d6bc", "#cbbb9e", "#a69478", "#7a6a56"])             # fronha (creme quente: separa do lençol)
CASE_D = Pal(["#d8c8aa", "#c4b294", "#a9967a", "#857460", "#5e5244"])
WOOD = Pal(["#d9a77a", "#b98456", "#966540", "#6e4a30", "#4a3222"])            # cabo de ferramenta / prancheta
GLASS = Pal(["#e8f8ff", "#bfe4f4", "#8fc3dc", "#5f93b0", "#3c6a80"])
HOLO = Pal(["#3a5a78", "#2c4660", "#22384e", "#1a2a3c", "#121e2c"])              # vidro do holo apagado
SCR_L = Pal(["#3c6a80"] * 5, emit=True, emit_tone=0)                           # linha acesa (fraca) nas telas
SCR_O = Pal(["#c8683a"] * 5, emit=True, emit_tone=0)
LAMP = Pal(["#fff0b8"] * 5, emit=True, emit_tone=0)
MUG = Pal(["#f4a06a", "#e2733a", "#c8683a", "#a9482a", "#6e2a1c"])
FOODG = Pal(["#a6e08a"] * 5, emit=False)
SCRATCH = "/private/tmp/claude-501/-Users-gabrieloliveira-personal-projects-hesper/069fd66e-94db-441d-a898-b23f7dde8863/scratchpad"


# ---------------------------------------------------------------------------------------------------------------------
# 1 · Beliche: a plataforma e os cabos da r6, cama nova
# ---------------------------------------------------------------------------------------------------------------------
def bunk_model7(s, d=True):
    B = R6.BUNK
    x, yb, yf, z0, z1, zm = (B[k] for k in ("x", "yb", "yf", "z0", "z1", "zm"))
    ym, hy = (yb + yf) / 2, (yb - yf) / 2

    def plat_paint(L, N):
        idx = np.zeros(len(L), int)
        front = N[:, 1] < -0.8
        band = front & (np.abs(L[:, 2] + 0.1) < 0.8)
        idx[band] = 1
        idx[band & (np.abs((L[:, 0] + x) % 13.5 - 6.75) < 0.4)] = 2
        return idx
    s.rbox((0, ym, (z0 + z1) / 2), (x, hy, (z1 - z0) / 2), 0.8, R6.SL, paint=plat_paint if d else None, extra=(OR, SLD))
    s.box((-x + 1.5, x - 1.5), (yf + 0.8, yb - 0.5), (z0 - 1.0, z0), SLD)
    for sx in (-1, 1):
        s.box((sx * x - 0.2 * sx, sx * (x + 2.0)) if sx > 0 else (-(x + 2.0), -x + 0.2), (yf + 0.4, yf + 3.0), (z1 - 2.6, z1 - 0.4), SLD)
    # colchão (quase todo coberto: aparece no fundo e no pé)
    s.rbox((0, ym + 0.2, (z1 + zm) / 2), (x - 0.9, hy - 0.7, (zm - z1) / 2 - 0.2), 1.6, MATT)

    # lençol: cobre o tampo do colchão com rugas e cai pela frente até passar da borda da plataforma
    def sheet_top(U, Vv):
        w = 0.35 * np.sin(U * 0.55 + Vv * 0.9) * np.clip((U + x - 10) / 6, 0, 1)
        return U, Vv, zm + 0.15 + w

    s.psurf(grid(-x + 0.4, x - 0.5), grid(yf + 0.3, yb - 0.7), sheet_top, SHEET)

    def sheet_drape(U, Vv):     # V 0..1 descendo; a barra é ondulada e passa um pouco do topo da plataforma
        zbot = z1 + 0.5 - 0.9 * (0.5 + 0.5 * np.sin(U * 0.42 + 0.3)) - 0.4 * (0.5 + 0.5 * np.sin(U * 1.3))
        z = zm + 0.15 - Vv * (zm + 0.15 - zbot)
        y = yf + 0.3 - 0.7 * np.sin(Vv * math.pi * 0.6) - 0.25 * np.sin(U * 0.9) * Vv - 0.3
        return U, y, z

    s.psurf(grid(-x + 1.0, x - 1.0), grid(0, 1, 16), sheet_drape, SHEET,
            paint=(lambda U, Vv: np.where((np.sin(U * 0.9 + 0.4) > 0.55) & (Vv > 0.25), 1, 0)) if d else None, extra=(R6.MATT,))
    # travesseiro: altura de "almofada" (superelipse), afundado no meio onde a cabeça ficou, costura em volta
    px0, px1 = -x + 1.4, -x + 11.6
    py0, py1 = yf + 1.6, yb - 1.4
    pcx, pcy, phx, phy = (px0 + px1) / 2, (py0 + py1) / 2, (px1 - px0) / 2, (py1 - py0) / 2

    def pillow(U, Vv):
        u, v = (U - pcx) / phx, (Vv - pcy) / phy
        e = np.clip(1 - np.abs(u) ** 3, 0, 1) * np.clip(1 - np.abs(v) ** 3, 0, 1)
        dent = 1.8 * np.exp(-(((U - pcx - 0.6) / 2.6) ** 2 + ((Vv - pcy + 0.4) / 3.2) ** 2))
        return U, Vv, zm + 0.4 + 3.6 * np.sqrt(e) - dent * e

    def pillow_paint(U, Vv):
        u, v = (U - pcx) / phx, (Vv - pcy) / phy
        idx = np.zeros(len(U), int)
        idx[(np.abs(u) > 0.80) & (u > 0)] = 1                     # a ponta aberta da fronha (lado do cobertor)
        return idx

    s.psurf(grid(px0, px1), grid(py0, py1), pillow, CASE, paint=pillow_paint if d else None, extra=(CASE_D,))
    # a aba da fronha dobrada pra fora, caída sobre o lençol
    if d:
        s.psurf(grid(px1 - 0.2, px1 + 2.2), grid(py0 + 1.4, py1 - 2.6),
                lambda U, Vv: (U, Vv, zm + 0.5 + 1.6 * np.clip((px1 + 2.2 - U) / 2.4, 0, 1) ** 1.5), CASE)
    # cobertor por cima: borda torta, pesponto em losango (textura de tecido), barra mais escura
    bx0, bx1 = -x + 15.0, x - 0.3

    def edge_x(Vv):
        return bx0 + 1.3 * np.sin((Vv - yf) * 0.42) + (Vv - yf) * 0.12

    def fold(U, Vv):
        return 0.8 * np.sin(U * 0.26 + Vv * 0.30 + 0.6) + 0.3 * np.sin(U * 0.55 - Vv * 0.25 + 2.0)

    def btop(U, Vv):
        e = np.clip((U - edge_x(Vv)) / 1.6, 0, 1)
        ch = 0.6 * np.abs(np.sin((Vv - yf) * math.pi / 5.0))            # gomos do acolchoado (ao longo do X)
        return U, Vv, zm + 0.8 + e * (1.5 + 0.7 * fold(U, Vv) + ch)

    def quilt(U, Vv):
        """A barra mais escura perto da borda (a textura vem dos gomos do acolchoado, na geometria)."""
        return np.where(np.abs(U - edge_x(Vv) - 3.0) < 0.8, 1, 0)

    s.psurf(grid(bx0 - 2, bx1), grid(yf + 0.1, yb - 0.6), btop, BLANK, keep=lambda U, Vv: U >= edge_x(Vv),
            paint=quilt if d else None, extra=(BLANK_D,))

    def bdrape(U, Vv):          # aba do cobertor na frente, mais curta que o lençol (a barra branca aparece embaixo)
        z_top = btop(U, np.full_like(U, yf + 0.1))[2]
        zbot = zm - 1.0 - 1.4 * (0.5 + 0.5 * np.sin(U * 0.33 + 1.2))
        z = z_top - Vv * (z_top - zbot)
        y = yf + 0.1 - 1.2 * np.sin(Vv * math.pi * 0.55) - 0.6 * (0.5 + 0.5 * np.sin(U * 0.8)) * Vv - 0.4
        return U, y, z

    if d:
        s.psurf(grid(bx0 - 2, bx1 - 0.3), grid(0, 1, 16), bdrape, BLANK,
                keep=lambda U, Vv: U >= edge_x(np.full_like(U, yf + 0.1)),
                paint=lambda U, Vv: quilt(U, np.full_like(U, yf + 0.1)), extra=(BLANK_D,))
    # a dobra virada do lençol por cima da cabeceira do cobertor (faixa branca, um pouco acima)
    s.psurf(grid(bx0 - 3, bx0 + 5), grid(yf + 0.2, yb - 0.8),
            lambda U, Vv: (U, Vv, zm + 1.2 + 1.2 * np.clip((U - edge_x(Vv) + 0.6) / 1.4, 0, 1) - 0.25 * np.clip((U - edge_x(Vv) - 1.6), 0, 2)),
            SHEET, keep=lambda U, Vv: (U >= edge_x(Vv) - 0.6) & (U <= edge_x(Vv) + 2.6))


def bunk_sprite7():
    sc = Scene(64, 40, ground=8.0)
    bunk_model7(S6(sc), True)
    cv = sc.render()
    CH.check(cv, "bunk7", (64, 40))
    im = cv.image().convert("RGBA")
    sc2 = Scene(64, 40, ground=8.0)
    R6.bunk_cables(S6(sc2), True)
    im.alpha_composite(sc2.render().image().convert("RGBA"))
    sh = Image.new("RGBA", (64, 40), (0, 0, 0, 0))
    y_floor = 8.0 - R6.BUNK["yf"] * SA
    ImageDraw.Draw(sh).rectangle([3, int(y_floor) - 5, 60, int(y_floor) + 1], fill=SHADOW)
    sh.alpha_composite(im)
    return sh


# ---------------------------------------------------------------------------------------------------------------------
# 2 · Mesas
# ---------------------------------------------------------------------------------------------------------------------
def m_briefing(s, d=True):
    """Mesa redonda de briefing, 2×2: pé central com faixa laranja, tampo grosso com friso, 6 telas embutidas em
    anel, 4 consoles inclinados na borda e o emissor do holo (apagado) no centro."""
    R, zt = 29.6, 15.0
    s.cyl(0, 0, 14, 0, 1.4, SLD)
    s.cyl(0, 0, 9, 1.4, zt - 2.2, SL, paint=(lambda th, z, c: np.where((z > 4.2) & (z < 6.0) & ~c, 1, 0)) if d else None, extra=(OR,))
    s.cyl(0, 0, R - 1.5, zt - 4.0, zt - 3.2, SLD)                                               # aba de baixo

    def top(th, z, cap):
        idx = np.zeros(len(th), int)
        side = ~cap
        idx[side & (np.abs(z - (zt - 1.6)) < 0.75)] = 1                                       # friso laranja da borda
        if d:
            rr = z                                                                         # no tampo, z = raio
            sec = (th * 6 / (2 * math.pi)) % 1.0
            scr = cap & (rr > 11.5) & (rr < 22.5) & (sec > 0.12) & (sec < 0.88)
            idx[scr] = 2
            idx[scr & (np.abs(rr - 17.0) < 1.0) & (sec > 0.3) & (sec < 0.7)] = 3          # a linha fraca acesa
            idx[cap & (np.abs(rr - 24.6) < 0.8)] = 4                                         # sulco do anel
        return idx
    s.cyl(0, 0, R, zt - 3.2, zt, SL, paint=top, extra=(OR, SCR, SCR_L, SLD))
    # consoles na borda: chapa inclinada com teclado e LED (atrás, dos lados e na frente)
    for i, ang in enumerate((math.radians(a) for a in (30, 150, 210, 330))):
        cx, cy = (R - 4.2) * math.cos(ang), (R - 4.2) * math.sin(ang) * 0.98
        s.obox((cx, cy, zt + 1.2), (4.6, 2.2, 1.0), SLD, rot_z=ang + math.pi / 2, rot_x=0.0)
        if d:
            s.dot(cx, cy - 1.0, zt + 2.4, "#ffb04a" if i == 1 else "#7fe08a", always=True)
            s.dot(cx + 1.6, cy - 1.0, zt + 2.4, "#7a2a36", always=True)
    # emissor do holo no centro, apagado (vidro escuro com um brilhinho)
    s.cyl(0, 0, 6.0, zt, zt + 1.4, SLD)
    s.cyl(0, 0, 4.0, zt + 1.4, zt + 2.0, SL)
    s.sphere((0, 0, zt + 2.4), 3.0, HOLO)
    if d:
        s.dot(-1.2, -2.2, zt + 4.0, "#7fa8e0", always=True)
        for k in range(6):                                                                 # lentes em volta
            a_ = k * math.pi / 3 + 0.5
            s.dot(5.0 * math.cos(a_), 5.0 * math.sin(a_), zt + 1.5, "#59d0e6", always=False)


def m_mess(s, d=True):
    """Mesa de refeitório 2×1: tampo claro com bandejas, caneca e talher; cavaletes; banco na frente e atrás."""
    s.rbox((0, 0, 11.2), (24, 7.0, 1.1), 0.9, CR,
           paint=(lambda L, N: np.where((N[:, 1] < -0.7), 1, 0)) if d else None, extra=(SL,))
    for sx in (-1, 1):                                                                    # cavaletes
        s.box((sx * 17 - 1.2, sx * 17 + 1.2), (-5, 5), (1.0, 10.1), SLD)
        s.box((sx * 17 - 1.8, sx * 17 + 1.8), (-6, 6), (0, 1.2), SLD)
    s.box((-16, 16), (-0.8, 0.8), (3.4, 4.6), SLD)                                           # travessa
    for y, h in ((-12.0, 6.6), (12.0, 6.6)):                                               # bancos
        s.rbox((0, y, h), (22, 2.4, 0.9), 0.7, SL,
               paint=(lambda L, N: np.where((N[:, 1] < -0.7) & (np.abs(L[:, 2]) < 0.5), 1, 0)) if d else None, extra=(OR,))
        for sx in (-1, 1):
            s.box((sx * 16 - 0.9, sx * 16 + 0.9), (y - 1.6, y + 1.6), (0, h - 0.9), SLD)
    if d:
        for (x, y) in ((-13, -2.4), (6, 2.4)):                                             # bandejas com comida
            s.rbox((x, y, 12.6), (4.4, 2.8, 0.35), 0.3, SL)
            s.sphere((x - 1.6, y - 0.6, 12.9), 1.2, MUG)
            s.sphere((x + 1.4, y - 0.4, 12.9), 1.1, FOODG)
            s.box((x + 2.6, x + 3.6), (y - 2.2, y + 1.6), (12.9, 13.2), STEEL)
        s.cyl(17.5, -2.0, 1.5, 12.3, 15.2, MUG)                                           # caneca
        s.tube([(19.0, -2.0, 14.6), (19.9, -2.0, 13.8), (19.0, -2.0, 12.9)], 0.45, MUG)
        s.cyl(-4.0, 3.6, 1.1, 12.3, 14.4, GLASS)                                          # copo


def m_repair(s, d=True):
    """Bancada de manutenção 2×1: tampo de aço grosso com borda laranja, prateleira com caixa de ferramentas,
    morsa, luminária articulada, chave, chave de fenda e uma peça desmontada."""
    s.rbox((0, 0, 12.0), (24, 7.2, 1.4), 0.6, SLD,
           paint=(lambda L, N: np.where((N[:, 1] < -0.7) & (np.abs(L[:, 2]) < 0.6), 1, 0)) if d else None, extra=(OR,))
    for sx in (-1, 1):
        for sy in (-1, 1):
            s.box((sx * 22 - 1.0, sx * 22 + 1.0), (sy * 5.6 - 1.0, sy * 5.6 + 1.0), (0, 10.6), SL)
    s.box((-21, 21), (-5.6, 5.6), (2.6, 3.6), SL)                                            # prateleira
    s.rbox((-11, -0.5, 6.0), (6.0, 3.6, 2.4), 0.6, MUG,
           paint=(lambda L, N: np.where(np.abs(L[:, 2] - 0.6) < 0.5, 1, 0)) if d else None, extra=(SLD,))   # caixa
    s.box((-12.5, -9.5), (-1.0, 0.0), (8.4, 9.4), SLD)                                        # alça
    s.rbox((10, 0.5, 5.2), (5.0, 3.2, 1.6), 0.6, SL)                                        # gaveteiro/peças
    # morsa na ponta esquerda
    s.box((-21.5, -16.5), (-4.5, -1.5), (13.4, 15.4), SL)
    s.box((-21.0, -17.0), (-6.0, -4.5), (13.4, 17.0), SL)
    s.box((-21.0, -17.0), (-1.5, 0.0), (13.4, 17.0), SL)
    s.tube([(-19, -7.6, 15.6), (-19, -10.2, 15.6)], 0.5, STEEL)
    if d:
        s.tube([(-6, -3.2, 13.8), (2.0, -4.8, 13.8)], 0.55, STEEL)                          # chave
        s.cyl(2.6, -4.9, 1.2, 13.4, 14.2, STEEL)
        s.tube([(4, -1.0, 13.8), (8, 0.4, 13.8)], 0.45, STEEL, caps=False)                  # chave de fenda
        s.tube([(8, 0.4, 13.9), (11.4, 1.6, 13.9)], 0.9, OR)
        s.rbox((-7, 2.6, 14.4), (3.0, 2.2, 1.0), 0.6, SL)                                   # peça desmontada (tampa)
        s.cyl(-7, 2.6, 1.3, 15.2, 16.0, GO)
        for (x, y) in ((-2.0, 3.0), (-0.6, 4.0), (0.4, 2.6)):                               # parafusos
            s.dot(x, y, 13.5, "#c4c8dc", always=True)
    # luminária articulada na ponta direita
    s.cyl(19.5, 4.0, 2.2, 13.4, 14.4, SLD)
    s.tube([(19.5, 4.0, 14.4), (18.5, 4.6, 22.0), (14.5, 1.0, 24.0)], 0.6, SL)
    s.cyl(14.0, 0.6, 2.4, 21.2, 23.6, OR, r_top=1.0)
    if d:
        s.dot(14.0, 0.0, 21.0, "#fff0b8", always=True)
        s.dot(13.0, 0.2, 21.0, "#fff0b8", always=True)


def m_nav(s, d=True):
    """Mesa de navegação 1×1: gabinete com tampo inclinado; tela com a rota acesa e uma carta de papel por cima,
    compasso dourado; gavetas embaixo."""
    s.rbox((0, 0, 6.0), (12, 7.5, 6.0), 1.0, SL,
           paint=(lambda L, N: np.where((N[:, 1] < -0.7) & (np.abs(L[:, 2] - 1.5) < 0.6), 1,
                                        np.where((N[:, 1] < -0.7) & (np.abs(L[:, 2] + 2.5) < 0.5), 2, 0))) if d else None,
           extra=(OR, SLD))
    piv = (0, 0, 12.0)
    tilt = 0.30

    def screen(L, N):
        idx = np.zeros(len(L), int)
        top_ = N[:, 2] > 0.5
        sc_ = top_ & (np.abs(L[:, 0]) < 10.0) & (np.abs(L[:, 1]) < 6.0)
        idx[sc_] = 1
        if d:
            route = sc_ & (np.abs(L[:, 1] - (np.sin(L[:, 0] * 0.35) * 3.0)) < 0.9) & (L[:, 0] > -7)
            idx[route] = 2
        return idx
    s.rbox((0, 0, 13.0), (12.4, 7.8, 1.0), 0.6, SLD, rot_x=tilt, pivot=piv, paint=screen, extra=(SCR, DIMC))
    if d:
        # carta de papel (meio dobrada) e compasso
        s.obox((-6.0, -2.0, 14.6), (4.6, 3.4, 0.25), CR, rot_z=0.25, rot_x=tilt)
        s.obox((-6.4, -2.4, 14.9), (1.2, 3.0, 0.15), CASE, rot_z=0.25, rot_x=tilt)
        s.tube([(5.0, -3.2, 15.4), (7.4, 1.8, 14.0)], 0.4, GO)
        s.tube([(5.0, -3.2, 15.4), (2.6, 1.4, 14.0)], 0.4, GO)
        s.dot(9.0, -2.0, 15.4, "#ffb04a", always=True)                                   # destino piscando


def m_side(s, d=True):
    """Mesinha de canto 1×1: tampo redondo com borda laranja, pé central, caneca fumegando (fria) e um tablet."""
    s.cyl(0, 0, 6.0, 0, 1.0, SLD)
    s.cyl(0, 0, 1.6, 1.0, 10.0, SL)
    s.cyl(0, 0, 9.5, 10.0, 11.6, SL, paint=(lambda th, z, c: np.where(~c & (z < 10.9), 1, 0)) if d else None, extra=(OR,))
    s.cyl(2.8, 0.8, 1.6, 11.6, 14.8, CR, paint=(lambda th, z, c: np.where(~c & (np.abs(z - 13.0) < 0.6), 1, 0)) if d else None,
          extra=(OR,))
    s.cyl(2.8, 0.8, 1.1, 14.3, 14.9, Pal(["#5a3a2a"] * 5))                                 # café
    s.tube([(4.4, 0.8, 14.2), (5.5, 0.8, 13.4), (4.4, 0.8, 12.4)], 0.5, CR)
    if d:
        s.obox((-3.6, -1.2, 11.9), (3.4, 2.4, 0.35), SLD, rot_z=0.35)                   # tablet
        s.obox((-3.6, -1.2, 12.3), (2.8, 1.9, 0.1), SCR, rot_z=0.35)
        s.dot(-4.4, -1.6, 12.6, "#3c6a80", always=True)


# ---------------------------------------------------------------------------------------------------------------------
# 3 · Microscópio (A: branco, na bancada creme do laboratório · B: ardósia/laranja, digital, no pedestal)
# ---------------------------------------------------------------------------------------------------------------------
class Rot:
    """Grupo girado em z em volta de (ox, oy): coordenadas locais (u, v, z); u+ = pro lado do braço (atrás),
    u- = pro lado de quem usa (a ocular aponta pra lá)."""

    def __init__(self, s, ang, ox=0.0, oy=0.0):
        self.s, self.a, self.ox, self.oy = s, ang, ox, oy
        self.c, self.sn = math.cos(ang), math.sin(ang)

    def w(self, p):
        return (self.ox + p[0] * self.c - p[1] * self.sn, self.oy + p[0] * self.sn + p[1] * self.c, p[2])

    def box(self, c, h, pal, **kw):
        self.s.obox(self.w(c), h, pal, rot_z=self.a, **kw)

    def tube(self, pts, r, pal, **kw):
        self.s.tube([self.w(p) for p in pts], r, pal, **kw)

    def cyl(self, u, v, r, z0, z1, pal, **kw):
        x, y, _ = self.w((u, v, 0))
        self.s.cyl(x, y, r, z0, z1, pal, **kw)

    def sphere(self, c, r, pal, **kw):
        self.s.sphere(self.w(c), r, pal, **kw)

    def dot(self, u, v, z, c, always=True):
        x, y, _ = self.w((u, v, 0))
        self.s.dot(x, y, z, c, always=always)


def micro_layers(z0, body, trim, arm, d=True, digital=False, ang=0.28, ox=0.0, oy=0.0, m=1.45):
    """O microscópio em camadas, de trás pra frente; cada camada sai numa cena própria com contorno e é colada por
    cima da anterior (em 32 px o contorno interno do r3d some entre peças tão juntas; assim cada peça fica legível).
    De perfil, girado ~16°: base pesada e braço em C atrás; platina com lâmina e luz; revólver com 3 objetivas e a
    cabeça; o tubo com a ocular inclinada pra frente."""
    def prep(s):
        s = S6(s, m)
        return s, Rot(s, ang, ox / m, oy / m), z0 / m

    def base(s):
        s, g, z = prep(s)
        g.box((0.6, 0, z + 1.3), (5.8, 3.8, 1.3), body)
        g.box((0.6, 0, z + 2.8), (5.0, 3.2, 0.25), trim)
        g.cyl(-1.0, 0, 1.5, z + 2.8, z + 4.0, trim)
        g.cyl(-1.0, 0, 1.0, z + 4.0, z + 4.6, LAMP)
        g.tube([(3.6, 0, z + 2.6), (4.4, 0, z + 8.6), (3.6, 0, z + 14.0), (1.6, 0, z + 16.0)], 1.75, arm)
        for sv in (-1, 1):
            g.tube([(4.2, sv * 1.6, z + 8.6), (4.2, sv * 3.0, z + 8.6)], 1.3, trim)

    def stage(s):
        s, g, z = prep(s)
        g.box((2.2, 0, z + 8.2), (1.4, 1.4, 1.0), SLD)
        g.box((-0.8, 0, z + 8.3), (3.0, 2.6, 0.45), SLD)
        if d:
            g.box((-0.8, 0, z + 8.9), (2.4, 1.1, 0.12), GLASS)
            g.dot(-1.2, 0, z + 9.2, "#a6e08a")
            g.box((-0.6, 1.7, z + 9.0), (1.6, 0.3, 0.2), STEEL)

    def head(s):
        s, g, z = prep(s)
        g.cyl(-0.8, 0, 2.0, z + 12.4, z + 13.8, SLD)
        for du, pal in ((-1.4, STEEL), (0.0, GO), (1.3, STEEL)):
            g.tube([(-0.8 + du * 0.5, 0, z + 12.6), (-0.8 + du, 0, z + 10.6)], 0.7, pal)
        g.box((0.4, 0, z + 15.4), (2.8, 2.0, 1.6), body)
        if digital:
            g.cyl(1.4, 0, 1.0, z + 17.0, z + 18.6, SLD)

    def tube(s):
        s, g, z = prep(s)
        g.tube([(-0.6, 0, z + 16.4), (-3.4, 0, z + 19.4)], 1.3, body)
        g.tube([(-3.4, 0, z + 19.4), (-4.3, 0, z + 20.4)], 1.1, SLD)
        if digital:                                                                       # telinha presa na câmera
            g.tube([(1.4, 0, z + 18.6), (3.4, -2.0, z + 19.6)], 0.45, SLD)
            s.obox(g.w((4.2, -3.4, z + 19.8)), (2.6, 0.4, 1.9), SLD, rot_z=-0.15)
            s.obox(g.w((4.2, -3.85, z + 19.8)), (2.1, 0.12, 1.45), SCR, rot_z=-0.15)
            if d:
                x, y, _ = g.w((4.2, -4.2, 0))
                s.dot(x - 0.6, y - 0.2, z + 20.2, "#a6e08a", always=True)
                s.dot(x + 0.5, y - 0.2, z + 19.4, "#59d0e6", always=True)
    return [base, stage, head, tube]


def m_micro_A(s, d=True):
    """A: microscópio branco num balcão baixo de laboratório (creme, família da prop_lab_bench), com o tapete de
    trabalho escuro no tampo (o branco do microscópio destaca), gaveta, LED e a caixinha de lâminas."""
    s.rbox((0, 0, 3.0), (12.0, 7.0, 3.0), 1.0, CR,
           paint=(lambda L, N: np.where((N[:, 2] > 0.8) & (np.abs(L[:, 0]) < 10.6) & (np.abs(L[:, 1]) < 5.6), 1,
                                        np.where((N[:, 1] < -0.7) & (L[:, 2] < -1.6), 2, 0))) if d else None,
           extra=(SLD, SL))
    if d:
        s.box((-3.0, 3.0), (-7.4, -6.9), (2.4, 3.2), SLD)                                 # puxador
        s.dot(9.4, -7.4, 4.4, "#ffb04a", always=True)
        s.rbox((8.4, -4.0, 6.4), (2.0, 1.3, 0.4), 0.3, GLASS)                             # caixinha de lâminas


def m_micro_B(s, d=True):
    """B: microscópio digital ardósia com detalhes laranja num pedestal redondo baixo; telinha na câmera."""
    s.cyl(0, 0, 7.0, 0, 1.2, SLD)
    s.cyl(0, 0, 2.4, 1.2, 3.6, SL)
    s.cyl(0, 0, 9.4, 3.6, 5.4, SLD, paint=(lambda th, z, c: np.where(~c & (z < 4.5), 1, 0)) if d else None, extra=(OR,))


TABLES = {  # id: (modelo, tamanho, front_y, k do ícone, sombra)
    "prop_briefing_table": (m_briefing, (64, 72), -30.0, 0.24, 60),
    "prop_mess_table": (m_mess, (64, 40), -15.0, 0.27, 58),
    "prop_repair_bench": (m_repair, (64, 40), -10.0, 0.27, 56),
    "prop_nav_table": (m_nav, (32, 40), -9.0, 0.5, 28),
    "prop_side_table": (m_side, (32, 40), -10.0, 0.55, 22),
    "prop_microscope_A": (m_micro_A, (32, 40), -8.0, 0.48, 28),
    "prop_microscope_B": (m_micro_B, (32, 40), -9.6, 0.5, 24),
}


MICRO = {"prop_microscope_A": dict(z0=6.0, body=CR, trim=SL, arm=SL, ox=-1.0, oy=1.0),
         "prop_microscope_B": dict(z0=5.4, body=SL, trim=SLD, arm=OR, digital=True, ox=-2.0, oy=1.0)}


def layered(pid, size, fy, k, d, scene_fn):
    """Renderiza o modelo (e, no microscópio, cada camada por cima) e devolve a PIL.Image."""
    model = TABLES[pid][0]
    sc = scene_fn()
    model(S6(sc, k), d)
    cv = sc.render()
    CH.check(cv, pid, cv.a.shape[1::-1])
    im = cv.image().convert("RGBA")
    if pid in MICRO:
        for lay in micro_layers(d=d, **MICRO[pid]):
            sc = scene_fn()
            lay(S6(sc, k))
            im.alpha_composite(sc.render().image().convert("RGBA"))
    return im


def table_sprite(pid):
    model, size, fy, _, shw = TABLES[pid]
    im = layered(pid, size, fy, 1.0, True, lambda: CH.scene(size[0], size[1], fy))
    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([(size[0] - shw) // 2, size[1] - 7, (size[0] + shw) // 2, size[1] - 1], fill=SHADOW)
    sh.alpha_composite(im)
    return sh


def table_icon(pid):
    """Ícone do mesmo modelo (com as telas e os LEDs, que dão a leitura); a escala desce de 0,01 em 0,01 até caber em 16×16."""
    model, size, fy, k, _ = TABLES[pid]
    while True:
        im = layered(pid, size, fy, k, True, lambda: Scene(48, 48, ground=34))
        bb = im.getbbox()
        if bb[2] - bb[0] <= 16 and bb[3] - bb[1] <= 16:
            return cut(im, (16, 16))
        k = round(k - 0.01, 2)


# ---------------------------------------------------------------------------------------------------------------------
# Montagens (casca aprovada, ordem do jogo: chão → decal → topo/face da parede → props de chão/mesa pelo pé)
# ---------------------------------------------------------------------------------------------------------------------
def room(sp, faces, props, decals, lantern, glows, name):
    """props: (img, tx, ty, altura em tiles); blit em (tx·32, ty·32 − 8), ordenados pelo pé (ty + altura)."""
    W, H, LIFT = 9, 8, 24
    ROOM = ["#########"] + ["#.......#"] * 6 + ["#########"]
    cv = Image.new("RGBA", (W * T, H * T + LIFT), (0, 0, 0, 255))
    wall = lambda x, y: 0 <= x < W and 0 <= y < H and ROOM[y][x] == "#"
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                cv.alpha_composite(sp["floor"][R4.R3_VAR[(x * 5 + y * 11) % len(R4.R3_VAR)]], (x * T, y * T + LIFT))
    for (img, tx, ty) in decals:
        cv.alpha_composite(img, (tx * T, ty * T + LIFT))
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                continue
            cv.alpha_composite(V.autotile_compose(sp["top"], wall, x, y), (x * T, y * T))
            if not wall(x, y + 1):
                idx = int(wall(x - 1, y)) + 2 * int(wall(x + 1, y))
                cv.alpha_composite(sp["face"].crop((idx * T, 0, idx * T + T, 24)), (x * T, y * T + 8 + LIFT))
                if (x, y) in faces:
                    cv.alpha_composite(faces[(x, y)], (x * T, y * T + 8 + LIFT))
    for (img, tx, ty, th) in sorted(props, key=lambda p: (p[2] + p[3], p[1])):
        cv.alpha_composite(img, (tx * T, ty * T - 8 + LIFT))
    cv.save(REP / f"sala_r7_{name}_clara.png")
    R2.dark_scene(cv, lantern, glows).save(REP / f"sala_r7_{name}_escura.png")


NAMES = {"prop_wall_bunk_r7": (64, 40), "prop_briefing_table_r7": (64, 72), "prop_mess_table_r7": (64, 40),
         "prop_repair_bench_r7": (64, 40), "prop_nav_table_r7": (32, 40), "prop_side_table_r7": (32, 40),
         "prop_microscope_r7_A": (32, 40), "prop_microscope_r7_B": (32, 40)}


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}

    def save(im, name, size):
        assert im.size == size, (name, im.size)
        alpha_ok(im, name)
        im.save(PEND / f"{name}.png")
        out[name] = im

    save(bunk_sprite7(), "prop_wall_bunk_r7", (64, 40))
    Image.open(PEND / "icon_prop_wall_bunk_r6.png").save(PEND / "icon_prop_wall_bunk_r7.png")    # o ícone não muda
    for pid, (model, size, fy, k, shw) in TABLES.items():
        v = pid[-2:] if pid[-2:] in ("_A", "_B") else ""
        name = pid[:len(pid) - len(v)] + "_r7" + v
        save(table_sprite(pid), name, size)
        save(table_icon(pid), "icon_" + name, (16, 16))
    assert set(NAMES) <= set(out), set(NAMES) - set(out)
    before = REP.parent / "before"                                   # o microscópio da v0.7 M2, pro antes × depois
    before.mkdir(exist_ok=True)
    for n in ("prop_microscope", "icon_prop_microscope"):
        if not (before / f"{n}_v07m2.png").exists():
            Image.open(V.ROOT / "assets" / "sprites" / f"{n}.png").save(before / f"{n}_v07m2.png")
    ld = lambda n: Image.open(PEND / f"{n}.png").convert("RGBA")
    sp = dict(top=ld("hull_wall_top"), face=ld("hull_wall_face"), floor=[ld(f"hull_floor_{i}") for i in range(4)])
    light, cable = ld("vesper_emergency_light_A"), ld("wall_cable_panel")
    rack, rack_o, ws, chair = ld("prop_server_rack_r5"), ld("prop_server_rack_open_r5"), ld("prop_workstation_r5"), ld("prop_pilot_chair_r5")
    o2, stack, locker, unif = ld("prop_o2_cylinders_r5"), ld("prop_container_stack"), ld("prop_suit_locker_r6_A"), ld("prop_uniforms_r6_A")
    room(sp, {(4, 0): cable, (7, 0): light},
         [(out["prop_briefing_table_r7"], 3, 3, 2), (rack, 1, 1, 1), (rack, 2, 1, 1), (rack_o, 3, 1, 1),
          (out["prop_nav_table_r7"], 5, 1, 1), (ws, 6, 1, 1), (chair, 6, 2, 1), (chair, 2, 4, 1), (chair, 5, 4, 1),
          (out["prop_side_table_r7"], 7, 5, 1)], [],
         (4 * T + 16, 4 * T + 30), [(1 * T + 16, 2 * T + 30, 14, (.6, .35, .05)), (2 * T + 16, 2 * T + 30, 14, (.6, .35, .05))],
         "cabine")
    room(sp, {(3, 0): light},
         [(out["prop_wall_bunk_r7"], 1, 1, 1), (out["prop_wall_bunk_r7"], 4, 1, 1), (out["prop_side_table_r7"], 3, 1, 1),
          (locker, 7, 1, 1), (o2, 7, 3, 1), (stack, 1, 5, 1)],
         [(unif, 3, 3), (ld("prop_uniforms_r6_B"), 5, 4)],
         (4 * T + 16, 3 * T + 40), [(3 * T + 16, 24 + 22, 30, (.7, .08, .08))], "alojamento")
    room(sp, {(6, 0): light},
         [(out["prop_microscope_r7_A"], 1, 1, 1), (out["prop_repair_bench_r7"], 3, 1, 1), (out["prop_microscope_r7_B"], 7, 1, 1),
          (out["prop_mess_table_r7"], 2, 4, 1), (out["prop_side_table_r7"], 6, 4, 1), (chair, 6, 5, 1)], [],
         (4 * T + 16, 3 * T + 40), [(6 * T + 16, 24 + 22, 30, (.7, .08, .08))], "apoio")
    return out


if __name__ == "__main__":
    build()
    print("ok")
