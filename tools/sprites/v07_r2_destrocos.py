#!/usr/bin/env python3
"""v0.7 Lore · rodada 2 dos destroços: transportador curvo com nome, sonda de satélite caído, base de vidro 7×5.

    python3 tools/sprites/v07_r2_destrocos.py

Saída: reports/design/v07_lore/pendentes/r2_*.png (CANDIDATAS). Reaproveita as paletas/ferramentas da rodada 1.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_destrocos import (CAV, CREAM, GLASS, LAV, METAL, OR, OR_D, OR_L, RUST, SLATE, arc)  # noqa: E402
from v07_lib import Cv, OUT, hsh, sand_pile, scatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"

FONT = {
    "V": ["101", "101", "101", "101", "010"], "S": ["111", "100", "111", "001", "111"],
    "P": ["111", "101", "111", "100", "100"], "E": ["111", "100", "110", "100", "111"],
    "R": ["110", "101", "110", "101", "101"], "-": ["000", "000", "111", "000", "000"],
    "7": ["111", "001", "010", "010", "010"],
}


def text(cv, x, y, s, col, accent_at=None):
    for i, ch in enumerate(s):
        for j, row in enumerate(FONT[ch]):
            for k, b in enumerate(row):
                if b == "1":
                    cv.px(x + i * 4 + k, y + j, col)
    if accent_at is not None:
        cv.px(x + accent_at * 4 + 2, y - 2, col)


# =====================================================================================================================
def cargo2(variant="A"):
    W, H = 128, 112
    cv = Cv(W, H)
    P = SLATE if variant == "A" else CREAM[1:]
    hi = "#d4daee" if variant == "A" else CREAM[0]
    ink = "#e8ecfa" if variant == "A" else "#5a4f48"
    cv.shadow_ell(62, 101, 60, 9)
    sand_pile(cv, 14, 97, 14, 5, 1)
    cy = lambda x: 66 + (x - 6) * 0.06
    def hh(x):
        if x < 38:
            return 8 + 20 * math.sqrt(max(0, 1 - ((38 - x) / 32) ** 2))
        return 28 - max(0, x - 84) * .12
    # barbatana dorsal (atrás do casco), curva, ponta laranja
    cv.poly([(60, 44), (74, 30), (92, 20), (104, 20), (98, 28), (90, 38), (86, 50)], P[3])
    cv.poly([(63, 44), (75, 33), (92, 23), (101, 22), (92, 31), (82, 44)], P[2])
    cv.poly([(92, 20), (104, 20), (100, 25), (93, 26)], OR); cv.px(104, 21, "#ff5a4a")
    # pernas de pouso quebradas
    cv.rect(26, 92, 3, 8, METAL[3]); cv.rect(24, 99, 8, 2, METAL[4]); cv.rect(70, 94, 3, 7, METAL[3]); cv.rect(67, 100, 8, 2, METAL[4])
    # casco (cápsula com volume)
    top = [(x, cy(x) - hh(x)) for x in range(6, 100)]
    bot = [(x, cy(x) + hh(x) * .96) for x in range(99, 5, -1)]
    mf = cv.pmask(top + bot)
    def tt(x, y):
        return (y - (cy(x) - hh(x))) / (2 * hh(x))
    cv.paint(mf, lambda x, y: hi if tt(x, y) < .05 else P[0] if tt(x, y) < .22 else P[1] if tt(x, y) < .5 else P[2] if tt(x, y) < .76 else P[3] if tt(x, y) < .92 else P[4])
    # costuras de placas (curvas suaves, espaçamento irregular)
    for xx in (24, 47, 61, 79):
        pts = [(xx + int(2 * math.sin(k / 6.0)), int(cy(xx) - hh(xx)) + 1 + k) for k in range(0, int(2 * hh(xx)) - 1, 2)]
        for (a, b) in pts:
            if mf[b, a] if 0 <= b < H and 0 <= a < W else False:
                cv.px(a, b, P[4])
    cv.speckle(mf, P[1], .18, 4)
    # faixa laranja (segue a curva)
    for x in range(10, 88):
        y = int(cy(x) + hh(x) * .18)
        if mf[y, x]:
            cv.rect(x, y, 1, 4, OR); cv.px(x, y, OR_L); cv.px(x, y + 3, OR_D)
    # nome no casco: VÉSPER-7
    text(cv, 41, int(cy(41) - hh(41) * .40), "VESPER-7", ink, accent_at=1)
    # cockpit (vidro)
    gl = cv.pmask([(8, 62), (13, 50), (22, 43), (34, 41), (38, 47), (36, 58), (22, 62)])
    cv.fill(gl, "#17131e")
    inner = cv.pmask([(10, 61), (14, 51), (22, 45), (33, 43), (36, 48), (34, 57), (22, 60)])
    cv.paint(inner, lambda x, y: GLASS[0] if (x - y) % 9 == 0 or y < 46 else GLASS[1] if y < 53 else GLASS[2])
    cv.line([(14, 56), (24, 46)], "#d6ecff"); cv.line([(28, 43), (28, 59)], P[4])
    # amassados / queimadura
    for (x, y, rx, ry) in ((58, 82, 6, 3), (46, 54, 4, 2), (84, 62, 3, 4)):
        m = cv.emask(x, y, rx, ry) & mf
        cv.fill(m, P[4]); cv.speckle(m, "#17131e", .4, 7)
    # --- boca do porão: a popa terminada em arco, aberta
    bx, by = 99, int(cy(99))
    rx_, ry_ = 11, int(hh(99))
    rim = cv.emask(bx, by, rx_ + 3, ry_ + 2)
    cv.paint(rim, lambda x, y: P[1] if y < by - ry_ * .3 else P[3])
    cav = cv.emask(bx + 1, by, rx_, ry_)
    cv.banded(cav, ["#6a5560", "#4a3a44", "#362a38", CAV[1]], cuts=[.25, .5, .8])
    for k in range(4):                                                     # costelas em arco
        arc(cv, bx - 1 + k * 3, by, 3 + k * 2.5, ry_ - 1, -math.pi / 2, math.pi / 2, RUST[1] if k % 2 == 0 else RUST[3], 16, 1)
    cv.rect(bx - 2, by + 4, 9, 9, "#4b5273" if variant == "A" else "#8a6a4a"); cv.rect(bx - 2, by + 4, 9, 3, "#7f89ad" if variant == "A" else "#b38a5e")
    cv.rect(bx + 2, by - 6, 7, 8, "#6c4030"); cv.rect(bx + 2, by - 6, 7, 2, "#9a5a3a")
    # lábio rasgado: chapas tortas em volta, uma mordida no topo
    for (dx, dy) in ((-6, -ry_ - 1), (3, -ry_ - 3), (10, -ry_ + 4), (13, 0), (11, ry_ - 6), (-4, ry_ + 1)):
        cv.rect(bx + dx - 2, by + dy - 1, 5, 3, P[2]); cv.px(bx + dx - 2, by + dy - 1, P[0]); cv.px(bx + dx + 1, by + dy + 1, OR_D)
    arc(cv, bx + 1, by, rx_ + 1, ry_ + 1, -math.pi / 2, math.pi / 2, OR_D, 30, 1)
    cv.fill(cv.pmask([(bx - 8, by - ry_ - 4), (bx + 4, by - ry_ - 4), (bx + 1, by - ry_ + 3), (bx - 4, by - ry_ + 1)]), (0, 0, 0, 0))
    # rampa de tábuas caída até a areia
    ramp = [(91, by + ry_ - 4), (108, by + ry_ - 8), (127, 101), (122, 111), (98, 111), (90, 104)]
    cv.poly(ramp, OUT)
    r2 = cv.pmask([(93, by + ry_ - 3), (107, by + ry_ - 7), (125, 101), (121, 109), (99, 109), (92, 103)])
    cv.banded(r2, ["#d29a62", "#a76a44", "#7a4a34", "#5e3526"], cuts=[.2, .55, .85])
    for k in range(5):
        cv.line([(96 + k * 6, by + ry_ - 3 + k), (98 + k * 6, 109)], "#5e3526")
    for k in range(5):
        cv.rect(95 + k * 4, 106 - k // 3, 2, 2, "#f2c46d" if k % 2 == 0 else "#3b3f46")
    # caixas caídas pra fora
    cv.rect(110, 95, 12, 10, OUT); cv.rect(111, 96, 10, 8, "#6c4030"); cv.rect(111, 96, 10, 3, "#9a5a3a"); cv.rect(111, 99, 10, 1, OUT)
    cv.rect(119, 87, 8, 9, OUT); cv.rect(120, 88, 6, 7, "#4b5273" if variant == "A" else "#8a6a4a"); cv.rect(120, 88, 6, 3, "#7f89ad" if variant == "A" else "#b38a5e")
    cv.rect(10, 92, 3, 8, METAL[3]) if False else None
    # antena com luz
    cv.rect(46, 24, 2, 18, METAL[2]); cv.rect(44, 22, 6, 1, METAL[2]); cv.rect(45, 20, 4, 3, "#ff5a4a"); cv.px(45, 20, "#ffb0a0")
    sand_pile(cv, 38, 100, 26, 4, 2)
    scatter(cv, [(2, 106), (50, 106), (64, 108), (30, 109), (84, 109), (124, 109), (1, 99), (80, 104)], 3)
    cv.outline()
    return cv


# =====================================================================================================================
def probe2():
    """Satélite caído: barramento de instrumentos em caixa, prato torto no braço, 2 asas solares, pernas e sulco."""
    cv = Cv(64, 64)
    # cratera/sulco de impacto
    crater = cv.emask(30, 52, 29, 7)
    cv.banded(crater, ["#625650", "#796b61", "#8e7f73"], cuts=[.4, .75])
    cv.line([(2, 58), (14, 56)], "#625650", 2)
    cv.shadow_ell(32, 54, 26, 5)
    sand_pile(cv, 12, 56, 12, 4, 3); sand_pile(cv, 52, 57, 10, 3, 4)
    # asa solar esquerda: caída no chão, quebrada ao meio
    def wing(p0, ex, ey, nx, ny, broken=False):
        from v07_destrocos import quad
        q = quad(p0, ex, ey)
        pts = [q(0, 0), q(1, 0), q(1, 1), q(0, 1)]
        cv.poly(pts, METAL[3]); m = cv.pmask(pts)
        cv.fill(m, "#3d63a8")
        cv.paint(m, lambda x, y: "#9cc0ff" if (x + 2 * y) % 13 == 0 else None)
        for i in range(1, nx):
            cv.line([q(i / nx, 0), q(i / nx, 1)], "#1f3a6e")
        for j in range(1, ny):
            cv.line([q(0, j / ny), q(1, j / ny)], "#1f3a6e")
        cv.line([q(0, 0), q(1, 0)], "#9cc0ff")
        if broken:
            cv.fill(cv.pmask([q(.55, 0), q(.75, .3), q(.6, .6), q(.85, 1), q(1, 1), q(1, 0)]) & m, (0, 0, 0, 0))
            cv.line([q(.55, 0), q(.75, .3), q(.6, .6), q(.85, 1)], METAL[2])
    wing((38, 50), (22, -3), (-1, 7), 3, 2, broken=True)
    # perna de pouso entortada à esquerda e à direita
    cv.line([(24, 46), (18, 52), (14, 54)], METAL[3], 2); cv.rect(11, 54, 6, 2, METAL[4])
    cv.line([(42, 46), (48, 51), (53, 50)], METAL[3], 2); cv.rect(50, 49, 6, 2, METAL[4])
    # asa direita: levantada, apoiada, quebrada
    wing((44, 22), (14, -9), (6, 12), 3, 3, broken=True)
    cv.line([(40, 36), (46, 32)], METAL[2], 2)
    # corpo: caixa de instrumentos (topo + frente), manta dourada, luneta no topo
    top = cv.pmask([(18, 28), (30, 22), (46, 24), (44, 31), (22, 36)])
    cv.banded(top, [CREAM[0], CREAM[1], CREAM[2]], cuts=[.3, .7])
    front = cv.pmask([(18, 33), (44, 31), (46, 47), (20, 50)])
    cv.banded(front, ["#f2c46d", "#d9a64e", "#b8893a", "#8a6a28"], cuts=[.25, .6, .85])
    cv.speckle(front, "#fff3c4", .22, 5); cv.speckle(front, "#6a4a1a", .2, 8)
    cv.line([(19, 40), (27, 37), (33, 41), (45, 38)], "#8a6a28")
    cv.rect(18, 33, 27, 2, CREAM[2]); cv.rect(18, 33, 27, 1, CREAM[0])
    cv.poly([(24, 24), (36, 22), (38, 26), (26, 28)], METAL[2]); cv.rect(23, 24, 3, 4, METAL[4]); cv.line([(25, 24), (36, 22)], METAL[0])
    cv.rect(40, 26, 2, 1, "#ff5a4a")                       # LED que pisca (NOVA posição: 2×1 em (40,26))
    cv.rect(21, 44, 4, 3, METAL[4])
    # bocal de empuxo apontando pro chão
    cv.poly([(28, 48), (36, 47), (38, 53), (27, 54)], METAL[3]); cv.rect(28, 52, 10, 2, METAL[4])
    # prato (parabólica) arrancado: caído no chão à esquerda, boca virada pra cima, borda torta e mordida
    cv.rect(17, 36, 3, 6, METAL[3])                                  # toco do braço que sobrou no corpo
    dish = cv.emask(12, 47, 12, 7)
    cv.banded(dish, [CREAM[0], CREAM[2], CREAM[3], CREAM[4]], cuts=[.2, .5, .8])
    inner = cv.emask(12, 46, 9, 4.5)
    cv.banded(inner, [CREAM[4], CREAM[3], CREAM[5]], cuts=[.4, .8])
    cv.fill(cv.emask(12, 46, 2.5, 1.5), METAL[3])
    cv.fill(cv.pmask([(18, 40), (26, 44), (22, 49), (17, 47)]) & dish, (0, 0, 0, 0))
    cv.line([(17, 41), (21, 47), (25, 44)], METAL[2])
    cv.line([(12, 46), (8, 40), (4, 34)], METAL[2]); cv.rect(2, 32, 3, 3, "#ff5a4a")      # alimentador torto
    scatter(cv, [(3, 60), (22, 60), (40, 60), (56, 56), (58, 48), (30, 58)], 9)
    cv.rect(52, 40, 8, 6, METAL[4]); cv.rect(52, 40, 8, 2, METAL[1])
    cv.outline()
    return cv


# =====================================================================================================================
# Base espacial de vidro · 224×192 · 7×5 tiles · lift 32
# =====================================================================================================================
GL = ["#e6fbff", "#a8e4f2", "#6cbcd4", "#3f8fae", "#26627c"]     # vidro: degraus cian (sem alpha), reflexo duro branco
INT = ["#1f3a46", "#16293a", "#0e1a28"]                           # interior visto pelo vidro


def pane(cv, mask, seed, broken=0.0, lit=True):
    """Vidro em degraus: faixa clara em cima, miolo, base escura; interior escuro aparece em parte; reflexos duros."""
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    def f(x, y):
        t = (y - y0) / max(1, y1 - y0)
        refl = ((x - x0) * 2 + (y - y0) + seed * 7) % 23
        base = GL[1] if t < .3 else GL[2] if t < .62 else GL[3] if t < .88 else GL[4]
        if refl < 2 and t < .85:
            return GL[0]
        # interior visível: faixa mais escura, com luzes e plantinhas
        h = hsh(x // 3, y // 3, seed)
        if t > .45 and h > .72:
            return INT[0] if t < .62 else INT[1]
        return base
    cv.paint(mask, f)
    # detalhes interiores: luz quente e planta
    for (x, y) in zip(xs, ys):
        h = hsh(x, y, seed + 3)
        if h > .985:
            cv.px(x, y, "#f2c46d")
        elif h < .01:
            cv.px(x, y, "#7fd67a")


def glass_base():
    W, H = 224, 192
    cv = Cv(W, H)
    LIFT = 32
    cv.shadow_ell(112, 178, 104, 11)
    sand_pile(cv, 14, 180, 14, 5, 1); sand_pile(cv, 205, 180, 16, 5, 2)
    # ---- painéis solares (direita, atrás), um rachado
    def solar(x, y, w, h, hole=False):
        cv.rect(x + w // 2 - 1, y + h - 2, 3, 22, METAL[3]); cv.rect(x + w // 2 - 4, y + h + 18, 9, 2, METAL[4])
        pts = [(x, y + 6), (x + w, y), (x + w, y + h - 6), (x, y + h)]
        cv.poly(pts, METAL[3]); m = cv.pmask([(x + 1, y + 7), (x + w - 1, y + 1), (x + w - 1, y + h - 7), (x + 1, y + h - 1)])
        cv.fill(m, "#3d63a8"); cv.paint(m, lambda xx, yy: "#9cc0ff" if (xx + yy * 2) % 15 == 0 else None)
        for i in range(1, 4):
            cv.line([(x + i * w // 4, y + 6 - i * 1), (x + i * w // 4, y + h - i * 1)], "#1f3a6e")
        cv.line([(x, y + h // 2 + 3), (x + w, y + h // 2 - 3)], "#1f3a6e")
        if hole:
            cv.fill(cv.pmask([(x + w - 14, y + 3), (x + w, y), (x + w, y + 14), (x + w - 8, y + 10)]) & m, (0, 0, 0, 0))
            cv.line([(x + w - 14, y + 3), (x + w - 8, y + 10), (x + w, y + 14)], METAL[2])
    solar(176, 66, 34, 34, True); solar(184, 112, 32, 30)
    # ---- módulo da direita (baixo, tanque) e tubo de ligação
    cv.rect(166, 150, 46, 26, OUT)
    bx = cv.pmask([(168, 152), (212, 152), (212, 174), (168, 174)])
    cv.banded(bx, [CREAM[0], CREAM[1], CREAM[2], CREAM[3]], cuts=[.2, .55, .85])
    cv.rect(168, 160, 44, 3, OR); cv.rect(168, 163, 44, 1, OR_D)
    cv.rect(174, 166, 10, 6, "#17131e"); cv.rect(175, 167, 8, 4, GL[3]); cv.px(175, 167, GL[0])
    cv.poly([(168, 152), (212, 152), (206, 144), (174, 144)], CREAM[1])
    # ---- módulo da esquerda: eclusa com porta e rampa
    ex0, ex1, ey0, ey1 = 10, 70, 138, 174
    cv.poly([(ex0, ey0), (ex1, ey0), (ex1 - 8, ey0 - 14), (ex0 + 8, ey0 - 14)], CREAM[0])
    cv.poly([(ex0, ey0), (ex1, ey0), (ex1 - 8, ey0 - 14), (ex0 + 8, ey0 - 14)], CREAM[0])
    cv.line([(ex0 + 14, ey0 - 7), (ex1 - 14, ey0 - 7)], CREAM[3])
    fr = cv.pmask([(ex0, ey0), (ex1, ey0), (ex1, ey1), (ex0, ey1)])
    cv.banded(fr, [CREAM[1], CREAM[2], CREAM[2], CREAM[3], CREAM[4]], cuts=[.12, .4, .7, .92])
    cv.rect(ex0, ey0 + 2, 6, ey1 - ey0, CREAM[0]) if False else None
    cv.rect(ex0, ey0 + 15, ex1 - ex0, 4, OR); cv.rect(ex0, ey0 + 15, ex1 - ex0, 1, OR_L); cv.rect(ex0, ey0 + 18, ex1 - ex0, 1, OR_D)
    # janela e porta (dupla de aço, entreaberta no escuro) — a futura entrada do interior
    cv.rect(14, ey0 + 5, 12, 8, "#17131e"); cv.rect(15, ey0 + 6, 10, 6, GL[3]); cv.rect(15, ey0 + 6, 10, 2, GL[1]); cv.line([(17, ey0 + 11), (22, ey0 + 7)], GL[0])
    cv.rect(36, ey0 + 4, 20, ey1 - ey0 - 3, OUT)
    cv.rect(37, ey0 + 5, 18, ey1 - ey0 - 5, CAV[1]); cv.rect(37, ey0 + 5, 18, 3, CAV[0])
    cv.rect(37, ey0 + 5, 3, ey1 - ey0 - 5, CREAM[3]); cv.rect(52, ey0 + 5, 3, ey1 - ey0 - 5, CREAM[3])   # batentes
    cv.rect(44, ey0 + 8, 4, 12, "#7fd67a") if False else None
    cv.rect(42, ey0 + 10, 3, 3, "#ff6a55")                       # luz de falha
    cv.line([(36, ey0 + 4), (56, ey0 + 4)], "#f2c46d")
    ramp = cv.pmask([(34, ey1), (58, ey1), (64, ey1 + 14), (28, ey1 + 14)])
    cv.paint(ramp, lambda x, y: BGR[0] if (y - ey1) < 4 else BGR[1] if (y - ey1) < 9 else BGR[2])
    for k in range(5):
        cv.line([(36 + k * 5, ey1 + 1), (33 + k * 7, ey1 + 13)], BGR[3])
    cv.line([(34, ey1), (28, ey1 + 14)], CREAM[5]); cv.line([(58, ey1), (64, ey1 + 14)], CREAM[5])
    # tubo de ligação eclusa → tambor
    cv.rect(68, 152, 22, 14, OUT); cv.rect(68, 153, 22, 12, CREAM[2]); cv.rect(68, 153, 22, 3, CREAM[0]); cv.rect(68, 162, 22, 3, CREAM[4])
    # ---- tambor central: parede de vidro (janelões) + topo + domo de vidro
    cx, cy0, rx, ry, wall = 120, 118, 54, 20, 36
    ytop = cy0
    body = cv.emask(cx, cy0 + wall, rx, ry) | cv.mask(lambda d: d.rectangle([cx - rx, cy0, cx + rx - 1, cy0 + wall], fill=255))
    body &= ~(cv.emask(cx, cy0, rx, ry) & (np.arange(H)[:, None] < cy0))
    def drum(x, y):
        t = (x - cx) / rx
        c = CREAM[1] if t < -.5 else CREAM[2] if t < 0 else CREAM[3] if t < .5 else CREAM[4]
        return c
    cv.paint(body, drum)
    # faixa de janelões (vidro) com montantes, curvando com o tambor
    band = body.copy()
    bb = np.zeros_like(band)
    for x in range(cx - rx + 4, cx + rx - 3):
        t = (x - cx) / rx
        ey = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        bb[int(ey) + 5:int(ey) + 24, x] = True
    band &= bb
    pane(cv, band, 11)
    for ang in np.linspace(0.1, math.pi - 0.1, 10):                  # montantes (acompanham a curva)
        x = cx + rx * math.cos(ang); ey = cy0 + ry * math.sin(ang)
        for yy in range(int(ey) + 5, int(ey) + 25):
            cv.px(x, yy, CREAM[2] if math.cos(ang) < 0 else CREAM[4])
    # faixa laranja e rodapé do tambor
    for x in range(cx - rx + 1, cx + rx):
        t = (x - cx) / rx
        ey = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        cv.rect(x, int(ey) + 1, 1, 3, OR if t < .5 else OR_D); cv.px(x, int(ey) + 1, OR_L if t < 0 else OR)
        cv.rect(x, int(ey) + 25, 1, 7, CREAM[3] if t < .3 else CREAM[4])
    # topo do tambor (anel) e miolo onde assenta o domo
    topm = cv.emask(cx, cy0, rx, ry)
    cv.paint(topm, lambda x, y: CREAM[0] if (x - cx) / rx + (y - cy0) / ry < -.6 else CREAM[1] if (x - cx) / rx < .3 else CREAM[2])
    # domo de vidro com estrutura
    dr, dry, dh = 46, 17, 46
    dome = cv.emask(cx, cy0, dr, dry) | (cv.emask(cx, cy0, dr, dh) & (np.arange(H)[:, None] <= cy0))
    pane(cv, dome, 29)
    def meridian(psi, col):
        pts = []
        for i in range(26):
            f = i / 25 * .985; r_ = math.sqrt(1 - f * f)
            pts.append((cx + dr * r_ * math.cos(psi), cy0 - f * dh + dry * r_ * math.sin(psi)))
        for a, b in zip(pts, pts[1:]):
            cv.line([a, b], col, 1)
    for psi in (0.1, 0.55, 1.0, 1.4, 1.75, 2.15, 2.6, 3.05):
        meridian(psi, CREAM[1] if math.cos(psi) < 0 else CREAM[3])
    for f_ in (.28, .6):
        r_ = math.sqrt(1 - f_ * f_)
        arc(cv, cx, cy0 - f_ * dh, dr * r_, dry * r_, .02, math.pi - .02, CREAM[2], 40, 1)
    arc(cv, cx, cy0, dr, dry, .0, math.pi, CREAM[1], 40, 2)
    # RUÍNA: vidro partido (buraco irregular no domo, interior escuro, estilhaços) + rachaduras
    hx, hy = cx + 8, cy0 - 26
    brk = []
    for i in range(16):
        an = 2 * math.pi * i / 16
        rr = (13 + 6 * hsh(i, 3, 4) + (6 if i % 2 else 0))
        brk.append((hx + rr * 1.25 * math.cos(an), hy + rr * .9 * math.sin(an)))
    mb = cv.pmask(brk) & dome
    cv.fill(mb, INT[1]); cv.paint(mb, lambda x, y: INT[2] if y > hy + 2 else INT[0] if y < hy - 8 else None)
    cv.line([(hx - 12, hy - 8), (hx, hy + 2), (hx + 14, hy - 6)], RUST[1], 2)
    cv.line([(hx - 2, hy - 15), (hx, hy + 12)], RUST[2])
    for (x, y) in brk:
        cv.px(x, y, GL[0]); cv.px(x + 1, y + 1, GL[4])
    for (a, b) in (((hx - 28, hy + 8), (hx - 15, hy + 2)), ((hx + 16, hy + 2), (hx + 30, hy + 16)), ((hx - 8, hy + 18), (hx - 14, hy + 30)), ((hx + 20, hy - 10), (hx + 30, hy - 6))):
        cv.line([a, b], "#ffffff"); cv.line([(a[0] + 1, a[1] + 1), (b[0] + 1, b[1] + 1)], GL[4])
    # janelão rachado e um painel arrancado na faixa de vidro
    cv.fill(cv.pmask([(cx + 18, 150), (cx + 30, 146), (cx + 34, 160), (cx + 22, 164)]) & band, INT[2])
    for (a, b) in (((cx - 30, 150), (cx - 20, 160)), ((cx - 8, 150), (cx - 2, 163)), ((cx + 34, 150), (cx + 42, 158))):
        cv.line([a, b], "#ffffff")
    # antenas no topo
    cv.rect(cx - 30, 10, 2, 74, METAL[2]); cv.rect(cx - 34, 24, 10, 1, METAL[2]); cv.rect(cx - 31, 7, 4, 3, "#ff5a4a"); cv.px(cx - 31, 7, "#ffb0a0")
    cv.rect(cx - 22, 22, 2, 58, METAL[3]); cv.rect(cx - 24, 18, 6, 4, METAL[0])
    # terminal embutido na base do tambor: tile (3,4)
    tx_, ty_ = 104, 166
    cv.rect(tx_, ty_, 20, 17, OUT); cv.rect(tx_ + 1, ty_ + 1, 18, 15, CREAM[1]); cv.rect(tx_ + 1, ty_ + 13, 18, 3, CREAM[4])
    cv.rect(tx_ + 3, ty_ + 3, 14, 9, "#102018"); cv.rect(tx_ + 4, ty_ + 4, 8, 1, "#7fd67a"); cv.rect(tx_ + 4, ty_ + 6, 11, 1, "#4aa860"); cv.rect(tx_ + 4, ty_ + 8, 6, 1, "#7fd67a"); cv.rect(tx_ + 14, ty_ + 14, 3, 1, OR)
    # entulho, placas e estilhaços de vidro no chão
    for (x, y, w_, c0, c1) in ((84, 176, 14, CREAM[2], CREAM[4]), (130, 178, 16, CREAM[1], CREAM[3]), (150, 172, 10, GL[1], GL[3]), (72, 180, 8, GL[2], GL[4]), (160, 180, 12, CREAM[2], CREAM[4])):
        cv.rect(x, y, w_, 5, c1); cv.rect(x, y, w_, 2, c0); cv.rect(x, y, w_, 1, CREAM[0] if c0 != GL[1] else GL[0])
    sand_pile(cv, 100, 184, 20, 4, 6)
    scatter(cv, [(4, 186), (76, 188), (140, 188), (190, 186), (214, 180), (40, 190), (160, 190), (205, 150)], 5)
    cv.outline()
    cv.terminal_rect = (tx_, ty_, 20, 17)
    return cv


# =====================================================================================================================
# Robô de reconhecimento v2 · 96×64 · 3×2 tiles (rover de esteiras com cabeça em pescoço)
# =====================================================================================================================
def track2(cv, p0, p1, r, dark=False):
    """Esteira inclinada: cápsula entre duas rodas, com sapatas, rodas e cubos."""
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    poly = [(x0 + nx * r, y0 + ny * r), (x1 + nx * r, y1 + ny * r), (x1 - nx * r, y1 - ny * r), (x0 - nx * r, y0 - ny * r)]
    m = cv.pmask(poly) | cv.emask(x0, y0, r, r) | cv.emask(x1, y1, r, r)
    cols = ["#5a6069", "#4a4f57", "#3b3f46", "#2a2d33"] if not dark else ["#3b3f46", "#2a2d33", "#1f2126", "#17181c"]
    cv.banded(m, cols, cuts=[.22, .55, .85])
    n = int(L // 4.5)
    for i in range(-2, n + 3):
        t = i * 4.5
        cx_, cy_ = x0 + ux * t, y0 + uy * t
        cv.line([(cx_ + nx * (r - 1), cy_ + ny * (r - 1)), (cx_ - nx * (r - 1), cy_ - ny * (r - 1))], cols[2] if not dark else "#17181c")
    for (px_, py_) in (p0, p1, ((x0 + x1) / 2, (y0 + y1) / 2 + 1)):
        cv.fill(cv.emask(px_, py_, r * .55, r * .55), "#9aa2ab" if not dark else "#6b717a")
        cv.fill(cv.emask(px_, py_, r * .25, r * .25), "#3b3f46")
        cv.px(px_ - 1, py_ - 2, "#d9dde6" if not dark else "#9aa2ab")
    return m


def robot2():
    cv = Cv(96, 64)
    cv.shadow_ell(48, 56, 44, 6)
    sand_pile(cv, 40, 56, 38, 5, 6)
    # esteira de trás (escura) e esteira solta caída à direita
    track2(cv, (50, 34), (76, 31), 6, dark=True)
    loose = track2(cv, (62, 58), (92, 57), 4)
    cv.line([(63, 50), (92, 45)], "#17181c") if False else None
    # corpo: chassi robusto com capô inclinado
    body = [(20, 28), (26, 18), (62, 16), (70, 24), (68, 42), (24, 44)]
    cv.poly(body, CREAM[3]); mb = cv.pmask(body)
    cv.banded(mb, [CREAM[0], CREAM[1], CREAM[2], CREAM[3], CREAM[4]], cuts=[.12, .4, .65, .88])
    cv.rect(22, 27, 46, 4, OR); cv.rect(22, 27, 46, 1, OR_L); cv.rect(22, 30, 46, 1, OR_D)
    cv.line([(40, 19), (38, 41)], CREAM[4]); cv.line([(56, 18), (58, 41)], CREAM[4])
    cv.speckle(mb, CREAM[4], .2, 5)
    # painel arrancado mostrando a placa verde
    cv.rect(42, 33, 12, 7, OUT); cv.rect(43, 34, 10, 5, "#2a6a3a"); cv.px(44, 35, "#7fd67a"); cv.px(49, 36, "#f2c46d"); cv.line([(44, 38), (52, 38)], "#7fd67a")
    cv.poly([(54, 32), (60, 33), (58, 39), (54, 37)], CREAM[3]); cv.line([(54, 32), (60, 33)], CREAM[0])
    # braço dobrado com garra caída (frente-esquerda)
    cv.line([(24, 32), (13, 36), (9, 48)], METAL[2], 3)
    cv.rect(8, 50, 8, 3, METAL[3]); cv.rect(8, 53, 3, 2, METAL[4]); cv.rect(13, 53, 3, 2, METAL[4])
    # pescoço articulado + cabeça/câmera (levemente tombada)
    cv.line([(46, 18), (46, 14)], METAL[2], 3); cv.fill(cv.emask(46, 18, 4, 2.5), METAL[3])
    head = cv.pmask([(34, 3), (56, 1), (58, 14), (36, 16)])
    cv.banded(head, [CREAM[0], CREAM[1], CREAM[3], CREAM[4]], cuts=[.2, .55, .85])
    cv.rect(35, 9, 22, 2, OR)
    cv.fill(cv.emask(46, 8, 5, 5), OUT); cv.fill(cv.emask(46, 8, 3.8, 3.8), "#e2733a"); cv.fill(cv.emask(46, 8, 2, 2), "#17131e"); cv.px(44, 6, "#ffe0b0")
    cv.rect(35, 5, 3, 4, METAL[3]); cv.rect(54, 4, 3, 5, METAL[3])
    # antena com LED
    cv.line([(64, 18), (68, 8)], METAL[2]); cv.rect(67, 4, 4, 3, "#ff5a4a"); cv.px(67, 4, "#ffb0a0")
    # esteira da frente (grande, na frente do corpo)
    track2(cv, (18, 51), (52, 47), 7)
    # caixote caído (cinza-azulado) com tampa solta
    cv.poly([(74, 42), (88, 40), (90, 50), (76, 52)], OUT); cv.poly([(75, 43), (87, 41), (88, 49), (76, 51)], "#4b5273")
    cv.poly([(75, 43), (87, 41), (88, 44), (75, 46)], "#7f89ad"); cv.line([(76, 48), (88, 46)], "#262a42")
    cv.rect(80, 45, 3, 2, OR)
    scatter(cv, [(2, 58), (20, 60), (50, 60), (78, 60), (90, 58), (4, 46), (70, 58)], 12)
    cv.outline()
    return cv


BGR = ["#d9dde6", "#a9b0be", "#8c93a3", "#58536b"]


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for v in ("A", "B"):
        c = cargo2(v); c.check(); c.image().save(PEND / f"r2_wreck_cargo_{v}.png")
    c = robot2(); c.check(); c.image().save(PEND / "r2_wreck_robot.png")
    c = probe2(); c.check(); c.image().save(PEND / "r2_wreck_probe.png")
    c = glass_base(); c.check(); c.image().save(PEND / "r2_wreck_module_glass.png")
    print(c.terminal_rect)


if __name__ == "__main__":
    main()
