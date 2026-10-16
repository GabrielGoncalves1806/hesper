#!/usr/bin/env python3
"""v0.7 Lore · rodada 5 · VÉSPER-7 em isométrico (2:1), cargueiro hard-surface com porão traseiro aberto.

    python3 tools/sprites/v07_r5_cargo.py    ->  pendentes/r5_wreck_cargo_{A,B}.png   (160×128)
Eixos: u = comprimento (desce pra direita), v = largura (desce pra esquerda), z = altura.  P(u,v,z) = (X0+u−v, Y0+(u+v)/2−z).
Faces visíveis: topo, costado esquerdo (v = W, iluminado) e popa (u = L, mais escura), onde fica o porão aberto.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_destrocos import CAV, METAL, OR, OR_D, OR_L, RUST  # noqa: E402
from v07_lib import Cv, OUT, hsh, sand_pile, scatter  # noqa: E402
from v07_r2_destrocos import FONT  # noqa: E402
from v07_r3_cargo import plate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"

SL = [("#b4bcd6", "#8f98b8", "#6f7898"), ("#8f98b8", "#6f7898", "#575f7d"), ("#6f7898", "#575f7d", "#444b66"), ("#575f7d", "#444b66", "#363c54")]
CR = [("#fbf7ec", "#efe7d4", "#d6ccb4"), ("#efe7d4", "#e3d9c3", "#cfc4ab"), ("#d6ccb4", "#c2b79d", "#a89c84"), ("#b3a78d", "#9a8e76", "#7b6f5a")]
BL = "#59d0e6"; BL2 = "#c8f6ff"; BL3 = "#2b9fb8"


class Iso:
    def __init__(self, cv, x0, y0):
        self.cv, self.x0, self.y0 = cv, x0, y0

    def P(self, u, v, z=0):
        return (self.x0 + u - v, self.y0 + (u + v) / 2 - z)

    def L(self, u, z, v):          # ponto no plano do costado (v fixo)
        return self.P(u, v, z)

    def box(self, u0, u1, v0, v1, z0, z1, tones, border, hi, top_tone=None, seed=0, wear=.08):
        """Caixa com as 3 faces visíveis: topo, costado (v1) e popa (u1)."""
        P, cv = self.P, self.cv
        tl = top_tone or tones[0]
        plate(cv, [P(u1, v0, z0), P(u1, v1, z0), P(u1, v1, z1), P(u1, v0, z1)], tones[2], border, None, wear=wear, seed=seed + 2)      # popa
        plate(cv, [P(u0, v1, z0), P(u1, v1, z0), P(u1, v1, z1), P(u0, v1, z1)], tones[1], border, hi, wear=wear, seed=seed + 1)         # costado
        plate(cv, [P(u0, v0, z1), P(u1, v0, z1), P(u1, v1, z1), P(u0, v1, z1)], tl, border, hi, cuts=(.3, .7), wear=wear, seed=seed)    # topo


def ptext(iso, u, z, v, s, col):
    """Texto 3×5 no plano do costado (v fixo), cisalhado pela inclinação 1:2 da isometria."""
    for i, ch in enumerate(s):
        for j, row in enumerate(FONT[ch]):
            for k, b in enumerate(row):
                if b == "1":
                    uu = u + i * 4 + k
                    x, y = iso.P(uu, v, z - j)
                    iso.cv.px(x, y, col)


def circle_u(iso, u, v, z, r, col):
    """Disco no plano da popa (u fixo): elipse inclinada em iso."""
    for a in range(0, 360, 6):
        pass
    cv = iso.cv
    for dv in range(-r, r + 1):
        for dz in range(-r, r + 1):
            if dv * dv + dz * dz <= r * r:
                x, y = iso.P(u, v + dv, z + dz)
                cv.px(x, y, col); cv.px(x, y + 1, col) if False else None


def cargo5(variant="A"):
    W, H = 160, 128
    cv = Cv(W, H)
    pal = SL if variant == "A" else CR
    BD = "#1d1d32" if variant == "A" else "#3a3550"
    HI = "#c8d0ea" if variant == "A" else "#ffffff"
    ink = "#e8ecfa" if variant == "A" else "#4a4260"
    Lu, Wv, Hh = 80, 42, 28
    iso = Iso(cv, 50, 46)
    P = iso.P
    cv.shadow_ell(84, 98, 66, 15)
    sand_pile(cv, 40, 100, 24, 6, 1); sand_pile(cv, 112, 108, 20, 4, 2)

    # ---- pernas de trás (atrás do casco)
    def leg(u, v, broken=False):
        a = P(u, v, 6)
        b = P(u - 4, v + 8, 0)
        if broken:
            cv.line([a, (a[0] - 1, a[1] + 4)], pal[3][1], 3)
            return
        cv.line([a, b], pal[3][2], 3); cv.line([(a[0] - 1, a[1]), (b[0] - 1, b[1])], pal[2][0])
        cv.rect(b[0] - 5, b[1] - 1, 11, 3, pal[3][2]); cv.rect(b[0] - 5, b[1] - 1, 11, 1, pal[1][0])
    leg(12, 0); leg(66, 0)
    # ---- casco principal
    iso.box(0, Lu, 0, Wv, 4, Hh, pal[:3], BD, HI, seed=1)
    # saias: barriga escura mais larga embaixo
    iso.box(4, Lu - 2, 2, Wv - 1, 0, 6, pal[1:4], BD, HI, seed=9)
    L = lambda u, z: P(u, Wv, z)
    if variant == "A":
        # painéis do costado em camadas (o cara de cargueiro): bloco laranja de trás, placas cinza na frente
        plate(cv, [L(8, 6), L(32, 6), L(32, 24), L(8, 24)], (OR_L, OR, OR_D), BD, "#ffd9b8", cuts=(.2, .6), wear=.08, seed=20)
        for (u0, u1) in ((10, 19), (21, 30)):
            plate(cv, [L(u0, 10), L(u1, 10), L(u1, 20), L(u0, 20)], ("#ffb27a", OR, OR_D), BD, "#ffd9b8", wear=0, seed=21)
            cv.line([L(u0 + 2, 15), L(u0 + 5, 18), L(u0 + 7, 15)], BD)
        plate(cv, [L(34, 6), L(56, 6), L(56, 24), L(34, 24)], pal[0], BD, HI, wear=.1, seed=22)
        plate(cv, [L(58, 6), L(76, 6), L(76, 24), L(58, 24)], pal[2], BD, HI, wear=.1, seed=23)
        for k in range(4):                                                   # ventilação
            cv.line([L(60, 19 - k * 3), L(74, 19 - k * 3)], pal[3][2])
        ptext(iso, 36, 21, Wv, "VESPER-7", ink)
        cv.line([L(34, 12), L(56, 12)], OR); cv.line([L(34, 11), L(56, 11)], OR_D)
        for u in (36, 42, 48, 54):
            x, y = L(u, 8); cv.px(x, y, BL)
        # ---- convés: chapas elevadas em camadas
        iso.box(8, 34, 6, 34, Hh, Hh + 4, pal[:3], BD, HI, seed=30)
        iso.box(40, 68, 10, 32, Hh, Hh + 3, pal[1:4], BD, HI, seed=31)
        iso.box(14, 26, 12, 26, Hh + 4, Hh + 7, pal[:3], BD, HI, seed=32)
        for k in range(4):
            x, y = P(46 + k * 5, 14, Hh + 3); cv.rect(x, y, 3, 1, pal[3][2])
        cv.poly([P(52, 20, Hh + 3), P(62, 20, Hh + 3), P(62, 28, Hh + 3), P(52, 28, Hh + 3)], OR); cv.line([P(52, 20, Hh + 3), P(62, 20, Hh + 3)], OR_L)
        # antena
        ax, ay = P(70, 8, Hh + 3)
        cv.rect(ax, ay - 20, 2, 20, METAL[2]); cv.rect(ax - 2, ay - 22, 6, 1, METAL[2]); cv.rect(ax - 1, ay - 25, 4, 3, "#ff5a4a"); cv.px(ax - 1, ay - 25, "#ffb0a0")
    else:
        # B: nave com cara de nave: cabine elevada com para-brisa de vidro, asas com turbinas e contêineres no convés
        plate(cv, [L(8, 6), L(40, 6), L(40, 22), L(8, 22)], pal[0], BD, HI, wear=.1, seed=70)
        plate(cv, [L(42, 6), L(76, 6), L(76, 24), L(42, 24)], pal[2], BD, HI, wear=.1, seed=71)
        cv.line([L(8, 13), L(76, 13)], OR); cv.line([L(8, 12), L(76, 12)], OR_D)
        ptext(iso, 44, 21, Wv, "VESPER-7", ink)
        for u in (12, 18, 24, 30, 36):
            x, y = L(u, 9); cv.px(x, y, BL)
        # cabine elevada na frente do convés
        iso.box(0, 26, 8, Wv - 8, Hh, Hh + 10, pal[:3], BD, HI, seed=72)
        glass = [L(2, Hh + 8), L(24, Hh + 8), L(24, Hh + 3), L(2, Hh + 3)]
        gp = [P(u, Wv - 8, z) for (u, z) in ((2, Hh + 8), (24, Hh + 8), (24, Hh + 3), (2, Hh + 3))]
        cv.poly(gp, BD)
        gi = cv.pmask([(x, y) for (x, y) in [P(3, Wv - 8, Hh + 7), P(23, Wv - 8, Hh + 7), P(23, Wv - 8, Hh + 4), P(3, Wv - 8, Hh + 4)]])
        cv.banded(gi, [BL2, BL, BL3], cuts=[.3, .65])
        cv.line([P(9, Wv - 8, Hh + 7), P(9, Wv - 8, Hh + 4)], BD); cv.line([P(16, Wv - 8, Hh + 7), P(16, Wv - 8, Hh + 4)], BD)
        # contêineres de carga no convés
        for (u0, c) in ((32, ("#e8a066", "#c97a45", "#a5582c")), (50, ("#9fa8c8", "#6f7898", "#575f7d"))):
            iso.box(u0, u0 + 14, 14, 30, Hh, Hh + 12, (c, c, c), BD, "#ffd8b0", top_tone=(c[0], c[0], c[1]), seed=u0)
        # asa da frente (em cima do costado, saindo pra esquerda) com turbina
        wing = [P(30, Wv, 10), P(62, Wv, 10), P(52, Wv + 26, 8), P(26, Wv + 20, 8)]
        cv.poly(wing, BD); wm = cv.pmask([P(31, Wv + 1, 9), P(61, Wv + 1, 9), P(52, Wv + 24, 7), P(27, Wv + 19, 7)])
        cv.banded(wm, [pal[0][0], pal[1][0], pal[2][1]], cuts=[.3, .7]); cv.line([P(31, Wv + 1, 9), P(61, Wv + 1, 9)], HI)
        cv.line([P(34, Wv + 3, 9), P(30, Wv + 17, 8)], pal[3][1]); cv.rect(*map(int, P(44, Wv + 12, 9)), 6, 2, OR)
        iso.box(34, 56, Wv + 4, Wv + 12, 5, 13, pal[:3], BD, HI, seed=80)
        tx_, ty_ = P(34, Wv + 8, 9)
        cv.fill(cv.emask(tx_, ty_, 4, 5), BD); cv.fill(cv.emask(tx_, ty_, 3, 4), BL3); cv.fill(cv.emask(tx_ - 1, ty_ - 1, 1.5, 2), BL2)
        # deriva de trás
        plate(cv, [P(50, 4, Hh), P(74, 4, Hh), P(74, 4, Hh + 18), P(60, 4, Hh + 18)], pal[2], BD, HI, wear=0, seed=81)
        ax, ay = P(8, 14, Hh + 10)
        cv.rect(ax, ay - 16, 2, 16, METAL[2]); cv.rect(ax - 1, ay - 19, 4, 3, "#ff5a4a"); cv.px(ax - 1, ay - 19, "#ffb0a0")
    # ---- popa: moldura do porão, hazard e luz azul
    S = lambda v, z: P(Lu, v, z)
    plate(cv, [S(6, 3), S(36, 3), S(36, 24), S(6, 24)], (CAV[0], CAV[1], CAV[2]), BD, None, cuts=(.3, .7), wear=0, seed=40)
    inner = cv.pmask([S(7, 4), S(35, 4), S(35, 23), S(7, 23)])
    cv.banded(inner, ["#3a4a66", "#26324a", "#16203a"], cuts=[.3, .7])
    for z in (6, 12, 18):
        cv.line([P(Lu - 8, 8, z + 1), P(Lu - 8, 34, z + 1)], "#3a5a86")                 # costelas do fundo
    cv.line([S(8, 5), S(34, 5)], BL); cv.line([S(8, 22), S(34, 22)], BL3)                # luz azul dentro
    for v in (12, 18, 24, 30):
        x, y = S(v, 7); cv.px(x, y, BL2)
    cx_, cy_ = P(Lu - 3, 22, 9); cv.rect(int(cx_), int(cy_), 8, 9, "#6c4030"); cv.rect(int(cx_), int(cy_), 8, 3, "#9a5a3a"); cx_, cy_ = P(Lu - 3, 12, 8); cv.rect(int(cx_), int(cy_), 7, 8, "#4b5273"); cv.rect(int(cx_), int(cy_), 7, 3, "#7f89ad")
    # moldura
    for (a, b) in ((S(6, 24), S(36, 24)), (S(6, 3), S(6, 24)), (S(36, 3), S(36, 24))):
        cv.line([a, b], OR_D)
    for k in range(5):
        x, y = S(8 + k * 6, 26); cv.rect(x, y, 2, 2, "#f2c46d" if k % 2 == 0 else BD)
    # chapa do topo da porta arrancada
    
    # ---- motores nos cantos da popa (luz azul), um danificado
    for (v0, v1, dmg) in ((0, 5, False), (37, 42, True)):
        iso.box(Lu, Lu + 9, v0, v1, 14, 28, pal[1:4], BD, HI, seed=50 + v0)
        cx, cy = P(Lu + 9, (v0 + v1) / 2, 21)
        cv.fill(cv.emask(cx, cy, 4, 5), BD)
        cv.fill(cv.emask(cx, cy, 3, 4), "#17131e" if dmg else BL3)
        if not dmg:
            cv.fill(cv.emask(cx, cy - 1, 1.5, 2), BL2)
        else:
            cv.line([(cx - 4, cy - 4), (cx + 3, cy + 4)], "#58536b")
    # ---- rampa de tábuas caída até a areia + luzes azuis nas bordas
    ramp = [P(Lu, 6, 3), P(Lu, 36, 3), P(Lu + 26, 36, 0), P(Lu + 26, 6, 0)]
    cv.poly([(x + (1 if i in (1, 2) else 0), y) for i, (x, y) in enumerate(ramp)], OUT)
    r2 = cv.pmask(ramp)
    cv.banded(r2, ["#9aa3bd", "#6f7898", "#575f7d", "#444b66"], cuts=[.2, .5, .8])
    for k in range(1, 5):
        cv.line([P(Lu + k * 5, 6, 2.6 - k * .5), P(Lu + k * 5, 36, 2.6 - k * .5)], "#363c54")
    for k in range(2, 24, 6):
        x, y = P(Lu + k, 6, 1.5); cv.px(x, y, BL); x, y = P(Lu + k, 36, 1.5); cv.px(x, y, BL)
    cv.line([P(Lu, 6, 3), P(Lu + 26, 6, 0)], "#f2c46d"); cv.line([P(Lu, 36, 3), P(Lu + 26, 36, 0)], "#f2c46d")
    # caixas caídas
    for (u, v, c) in ((Lu + 12, 44, "#6c4030"), (Lu + 24, 46, "#4b5273")):
        iso.box(u, u + 9, v, v + 9, 0, 8, ((c, c, c), (c, c, c), (c, c, c)), BD, "#d9a066", top_tone=("#c98a56", "#9a5a3a", "#7a4a34") if c == "#6c4030" else ("#7f89ad", "#4b5273", "#363c54"), seed=60)
    # ---- pernas da frente (uma quebrada) e peças soltas
    leg(10, Wv, broken=False)
    leg(64, Wv, broken=True)
    fx, fy = P(56, Wv + 12, 0)
    cv.rect(fx - 6, fy - 1, 12, 3, pal[3][2]); cv.rect(fx - 6, fy - 1, 12, 1, pal[1][0]); cv.line([(fx + 5, fy - 1), (fx + 12, fy - 9)], pal[3][2], 2)
    for (u, v, z) in ((30, Wv + 14, 0), (40, Wv + 18, 0)):
        x, y = P(u, v, z); cv.rect(x - 5, y - 1, 10, 3, pal[2][1]); cv.rect(x - 5, y - 1, 10, 1, pal[0][0])
    scatter(cv, [(4, 112), (50, 120), (90, 122), (130, 116), (20, 108), (118, 124)], 3)
    cv.outline()
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for v in "AB":
        c = cargo5(v); c.check(); c.image().save(PEND / f"r5_wreck_cargo_{v}.png")


if __name__ == "__main__":
    main()
