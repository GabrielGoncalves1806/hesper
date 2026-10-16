#!/usr/bin/env python3
"""v0.7 Lore · rodada 3 · transportador VESPER-7 angular/facetado (hard-surface), 2 formas. 160×112 · 5×3 tiles.

    python3 tools/sprites/v07_r3_cargo.py        ->  pendentes/r3_wreck_cargo_{A,B}.png
Chapas sobrepostas em camadas com bordas escuras, frisos, recortes; 3/4 (topo + costado). Boca do porão no tile (4,2).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_destrocos import CAV, GLASS, METAL, OR, OR_D, OR_L, RUST  # noqa: E402
from v07_lib import Cv, OUT, hsh, sand_pile, scatter  # noqa: E402
from v07_r2_destrocos import text  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"


def plate(cv, pts, tones, border, hi=None, cuts=(.18, .6), light="tl", seed=0, wear=.1):
    """Chapa facetada: preenchimento em faixas (claro em cima), borda escura grossa de 1 px por dentro e realce nas
    arestas de cima/esquerda. tones = (claro, médio, escuro)."""
    m = cv.pmask(pts)
    cv.banded(m, list(tones), cuts=list(cuts))
    if wear:
        cv.speckle(m, tones[2], wear, seed + 1)
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        cv.line([a, b], border)
        if hi:
            dx, dy = b[0] - a[0], b[1] - a[1]
            if dy < 0 or (dy == 0 and dx > 0):          # aresta virada pra cima: realce 1 px abaixo
                cv.line([(a[0], a[1] + 1), (b[0], b[1] + 1)], hi)
    return m


def vent(cv, x, y, w, h, dark, light):
    cv.rect(x, y, w, h, dark)
    for k in range(1, h - 1, 2):
        cv.rect(x + 1, y + k, w - 2, 1, light)


def cargo3(variant="A"):
    W, H = 160, 112
    cv = Cv(W, H)
    if variant == "A":     # creme com bordas azul-marinho (ref. creme)
        T = [("#fbf7ec", "#efe7d4", "#d6ccb4"), ("#efe7d4", "#e3d9c3", "#cfc4ab"), ("#e3d9c3", "#cfc4ab", "#b3a78d"), ("#cfc4ab", "#b3a78d", "#8e7f73")]
        BD, HI, DK2, ACC, ink = "#2a2d44", "#f4efe0", "#3a3f5c", OR, "#2a2d44"
        GL = ["#d6ecff", "#7fb4e0", "#3a5a8a", "#1d2b4a"]
    else:                  # vermelho facetado escuro (ref. Planet Crafter)
        T = [("#e0675a", "#c14a3c", "#9a3530"), ("#c14a3c", "#9a3530", "#7a2a2c"), ("#9a3530", "#7a2a2c", "#5a1f24"), ("#7a2a2c", "#5a1f24", "#3e151a")]
        BD, HI, DK2, ACC, ink = "#1d1626", "#f08a7a", "#2a2236", "#f2c46d", "#f4e7d8"
        GL = ["#bff4ff", "#59d0e6", "#2b7a99", "#143a52"]
    cv.shadow_ell(78, 101, 74, 9)
    sand_pile(cv, 14, 98, 14, 5, 1)

    if variant == "A":
        # asa traseira (atrás), aletas curtas
        plate(cv, [(54, 42), (70, 26), (110, 22), (104, 38), (84, 42)], T[3], BD, HI, seed=2)
        plate(cv, [(112, 40), (126, 24), (138, 26), (130, 42)], T[3], BD, HI, seed=3)
        # costado (face da frente): faceta larga e baixa, nariz chanfrado
        side = [(6, 68), (34, 62), (120, 62), (134, 68), (136, 96), (118, 100), (36, 100), (10, 92)]
        plate(cv, side, T[1] + ("#8e7f73",), BD, HI, cuts=(.12, .45, .8), seed=4)
        # chapas sobrepostas no costado (camadas)
        plate(cv, [(14, 74), (60, 70), (62, 90), (18, 92)], T[0], BD, HI, seed=5)
        plate(cv, [(58, 70), (108, 68), (110, 88), (60, 90)], T[2], BD, HI, seed=6)
        plate(cv, [(20, 92), (62, 91), (64, 98), (24, 98)], T[3], BD, HI, wear=.05, seed=7)
        cv.rect(14, 80, 46, 2, ACC); cv.rect(14, 80, 46, 1, OR_L)                      # friso laranja
        vent(cv, 98, 74, 9, 8, DK2, T[3][1])
        # convés (topo): 3 chapas facetadas em camadas
        plate(cv, [(6, 68), (24, 48), (56, 44), (52, 62), (34, 62)], T[0], BD, HI, seed=8)                    # nariz
        plate(cv, [(52, 62), (56, 44), (112, 40), (122, 58), (120, 62)], T[1], BD, HI, seed=9)                 # meio
        plate(cv, [(112, 40), (130, 46), (134, 68), (120, 62), (122, 58)], T[2], BD, HI, seed=10)              # popa
        plate(cv, [(62, 56), (66, 48), (100, 46), (104, 54)], T[3], BD, HI, cuts=(.3, .7), seed=11)            # camada elevada
        vent(cv, 72, 49, 20, 4, DK2, T[3][0])
        # cockpit: faceta de vidro no nariz
        cv.poly([(14, 62), (22, 52), (40, 49), (42, 60), (26, 63)], BD)
        cv.poly([(16, 61), (23, 54), (38, 51), (40, 59), (27, 62)], GL[2])
        cv.poly([(16, 61), (23, 54), (30, 53), (24, 61)], GL[1]); cv.line([(32, 52), (34, 61)], GL[0]); cv.line([(18, 60), (24, 55)], GL[0])
        cv.line([(30, 52), (28, 62)], BD)
        # nome
        text(cv, 62, 76, "VESPER-7", ink, accent_at=1)
        # motores traseiros e antena
        for (x, y) in ((118, 36), (126, 52)):
            cv.rect(x, y, 14, 10, BD); cv.rect(x + 1, y + 1, 12, 8, "#4a4f57"); cv.rect(x + 1, y + 1, 12, 2, "#9aa2ab"); cv.rect(x + 9, y + 2, 4, 6, "#17131e")
        cv.rect(80, 26, 2, 18, METAL[2]); cv.rect(78, 24, 6, 1, METAL[2]); cv.rect(79, 21, 4, 3, "#ff5a4a"); cv.px(79, 21, "#ffb0a0")
        cx_b = 134
    else:
        # B: comprido, cabine elevada, motores laterais
        plate(cv, [(100, 44), (112, 20), (128, 18), (122, 42)], T[3], BD, HI, seed=2)                 # deriva
        side = [(4, 72), (20, 66), (118, 64), (130, 70), (132, 96), (112, 100), (24, 100), (8, 92)]
        plate(cv, side, T[1] + ("#5a1f24",), BD, HI, cuts=(.12, .45, .8), seed=4)
        plate(cv, [(10, 78), (44, 74), (46, 92), (14, 94)], T[0], BD, HI, seed=5)
        plate(cv, [(44, 74), (92, 72), (94, 90), (46, 92)], T[2], BD, HI, seed=6)
        cv.rect(12, 84, 36, 2, ACC); cv.rect(48, 80, 44, 2, OR)
        for x0 in (100, 112):
            vent(cv, x0, 76, 8, 8, DK2, T[3][1])
        # convés longo e achatado
        plate(cv, [(4, 72), (20, 56), (60, 52), (56, 66), (20, 66)], T[0], BD, HI, seed=8)
        plate(cv, [(56, 66), (60, 52), (118, 48), (126, 60), (118, 64)], T[1], BD, HI, seed=9)
        plate(cv, [(118, 48), (132, 54), (130, 70), (118, 64), (126, 60)], T[2], BD, HI, seed=10)
        # cabine elevada (bloco com vidros inclinados)
        plate(cv, [(22, 58), (30, 42), (58, 40), (62, 52), (54, 60)], T[1], BD, HI, seed=12)
        cv.poly([(28, 56), (34, 45), (56, 43), (58, 52), (52, 57)], BD)
        cv.poly([(30, 55), (35, 47), (54, 45), (55, 51), (51, 55)], GL[2])
        cv.poly([(30, 55), (35, 47), (42, 46), (38, 54)], GL[1]); cv.line([(44, 46), (42, 55)], GL[0]); cv.line([(32, 54), (36, 49)], GL[0])
        cv.line([(48, 45), (47, 55)], BD)
        plate(cv, [(30, 42), (36, 36), (56, 34), (58, 40)], T[3], BD, HI, seed=13)
        text(cv, 52, 86 + 0, "VESPER-7", ink, accent_at=1) if False else text(cv, 28, 66, "VESPER-7", ink, accent_at=1) if False else None
        text(cv, 52, 83, "VESPER-7", ink, accent_at=1)
        # motores laterais (nacelas facetadas, uma quebrada)
        plate(cv, [(78, 86), (122, 84), (132, 90), (128, 100), (80, 102), (72, 94)], T[3], BD, HI, seed=14)
        cv.rect(80, 88, 40, 3, "#9aa2ab"); cv.rect(122, 88, 8, 8, "#17131e"); cv.rect(123, 90, 5, 4, "#59d0e6")
        plate(cv, [(80, 40), (92, 34), (106, 36), (104, 46), (86, 48)], T[3], BD, HI, seed=15)
        cv.rect(104, 38, 8, 8, BD); cv.rect(105, 39, 6, 6, "#17131e")
        cv.rect(70, 26, 2, 20, METAL[2]); cv.rect(68, 24, 6, 1, METAL[2]); cv.rect(69, 21, 4, 3, "#ff5a4a"); cv.px(69, 21, "#ffb0a0")
        cx_b = 132
    # --- boca do porão: popa aberta (corte irregular) + rampa caída
    mouth = [(cx_b - 10, 66), (cx_b - 2, 58), (cx_b + 10, 62), (cx_b + 12, 88), (cx_b + 2, 98), (cx_b - 12, 94)]
    cv.fill(cv.pmask(mouth), (0, 0, 0, 0))
    mm = cv.pmask(mouth)
    cv.banded(mm, ["#6a5560", "#4a3a44", "#362a38", CAV[1]], cuts=[.25, .5, .8])
    for k in (-6, 0, 6):
        cv.line([(cx_b + k, 62 + abs(k) // 3), (cx_b + k + 1, 80), (cx_b + k, 95)], RUST[1])
    cv.rect(cx_b - 8, 76, 9, 10, "#4b5273"); cv.rect(cx_b - 8, 76, 9, 3, "#7f89ad")
    cv.rect(cx_b - 1, 70, 8, 9, "#6c4030"); cv.rect(cx_b - 1, 70, 8, 3, "#9a5a3a")
    cv.line(mouth + [mouth[0]], OR_D)
    for (x, y) in mouth:
        cv.rect(x - 2, y - 1, 4, 3, T[2][1]); cv.px(x - 2, y - 1, T[0][0]); cv.px(x + 1, y + 1, OR_D)
    ramp = [(cx_b - 12, 94), (cx_b + 4, 96), (156, 104), (150, 111), (cx_b - 8, 111), (cx_b - 16, 104)]
    cv.poly(ramp, OUT)
    r2 = cv.pmask([(cx_b - 11, 95), (cx_b + 4, 97), (154, 104), (149, 109), (cx_b - 7, 109), (cx_b - 15, 104)])
    cv.banded(r2, ["#d29a62", "#a76a44", "#7a4a34", "#5e3526"], cuts=[.2, .55, .85])
    for k in range(5):
        cv.line([(cx_b - 9 + k * 6, 96 + k // 2), (cx_b - 7 + k * 6, 109)], "#5e3526")
    for k in range(5):
        cv.rect(cx_b - 12 + k * 4, 106, 2, 2, "#f2c46d" if k % 2 == 0 else "#3b3f46")
    cv.rect(146, 96, 12, 10, OUT); cv.rect(147, 97, 10, 8, "#6c4030"); cv.rect(147, 97, 10, 3, "#9a5a3a"); cv.rect(147, 100, 10, 1, OUT)
    # asa/flap da frente caído no chão, entulho
    if variant == "A":
        plate(cv, [(30, 100), (14, 106), (60, 110), (72, 102)], T[3], BD, HI, wear=.05, seed=20)
    sand_pile(cv, 40, 102, 26, 4, 2)
    scatter(cv, [(2, 106), (50, 108), (90, 108), (4, 98), (76, 109), (120, 110)], 3)
    cv.outline()
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for v in "AB":
        c = cargo3(v); c.check(); c.image().save(PEND / f"r3_wreck_cargo_{v}.png")


if __name__ == "__main__":
    main()
