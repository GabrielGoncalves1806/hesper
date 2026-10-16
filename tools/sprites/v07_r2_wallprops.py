#!/usr/bin/env python3
"""v0.7 Lore · rodada 2 · props de PAREDE (32×24, desenhados por cima da face da base_wall, sem colisão) + ícones 16×16.

    python3 tools/sprites/v07_r2_wallprops.py

A face da parede tem 24 px (blit em (tx·32, ty·32+8)): trilho 0–2, painel liso 3–11, faixa laranja 14–17, rodapé 18–22.
Os props moram nas linhas 2–18 e passam por cima da faixa laranja. Saída: pendentes/wall_*.png e icon_wall_*.png.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import Cv, OUT  # noqa: E402
from v07_props import BG, CR, DK, IC, OG, to_icon  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"
BL = ["#cfe6ff", "#4f8fd6", "#2f6fb0", "#1f4f8a", "#17376a"]     # papel azul de projeto


def frame(cv, x, y, w, h):
    cv.rect(x, y, w, h, BG[4]); cv.rect(x + 1, y + 1, w - 2, h - 2, BG[3]); cv.rect(x + 1, y + 1, w - 2, 1, BG[1])


def monitor_on():
    cv = Cv(32, 24)
    frame(cv, 7, 3, 18, 13)
    cv.rect(9, 5, 14, 9, DK[2])
    cv.rect(10, 6, 7, 1, "#7fd67a"); cv.rect(10, 8, 10, 1, "#4aa860"); cv.rect(10, 10, 5, 1, "#7fd67a"); cv.rect(10, 12, 8, 1, "#4aa860")
    for i, h in enumerate((2, 4, 3, 5)):
        cv.rect(18 + i * 1, 12 - h + 1, 1, h, "#59d0e6") if False else None
    cv.rect(19, 10, 3, 3, "#59d0e6"); cv.rect(19, 10, 3, 1, "#c8f6ff")
    cv.px(23, 14, OG[1]); cv.rect(14, 16, 4, 2, BG[3]); cv.rect(11, 18, 10, 1, BG[4])
    cv.outline(); return cv


def monitor_off():
    cv = Cv(32, 24)
    frame(cv, 7, 3, 18, 13)
    cv.rect(9, 5, 14, 9, "#17181c"); cv.line([(10, 12), (15, 6)], "#2a2d33"); cv.line([(13, 13), (19, 6)], "#2a2d33")
    cv.line([(18, 5), (20, 9), (17, 12), (19, 14)], "#58536b")           # rachadura
    cv.px(23, 14, BG[2]); cv.rect(14, 16, 4, 2, BG[3]); cv.rect(11, 18, 10, 1, BG[4])
    cv.outline(); return cv


def sheet(cv, x, y, w, h):
    cv.rect(x, y, w, h, BL[2]); cv.rect(x, y, w, 1, BL[1]); cv.rect(x, y + h - 1, w, 1, BL[3])
    for gx in range(x + 2, x + w - 1, 4):
        cv.rect(gx, y + 1, 1, h - 2, BL[3]) if False else None
    cv.px(x + 1, y + 1, OG[1]); cv.px(x + w - 2, y + 1, OG[1])        # tachinhas


def bp_plan():
    cv = Cv(32, 24); sheet(cv, 5, 3, 22, 14)
    L = BL[0]
    cv.rect(8, 6, 16, 9, L); cv.rect(9, 7, 14, 7, BL[2])
    cv.rect(15, 6, 1, 4, BL[2]); cv.rect(15, 12, 1, 3, BL[2]); cv.rect(9, 10, 5, 1, L); cv.rect(18, 10, 5, 1, L)
    cv.rect(17, 12, 3, 1, BL[0]); cv.px(11, 8, L); cv.px(21, 8, L)
    cv.outline(); return cv


def bp_ship():
    cv = Cv(32, 24); sheet(cv, 5, 3, 22, 14)
    L = BL[0]
    cv.line([(8, 11), (11, 8), (21, 8), (24, 11), (21, 14), (11, 14), (8, 11)], L)
    cv.line([(14, 8), (14, 14)], L); cv.line([(18, 8), (18, 14)], L)
    cv.line([(20, 8), (22, 5)], L); cv.rect(11, 11, 8, 1, BL[1]); cv.px(9, 12, L); cv.px(23, 6, L)
    cv.outline(); return cv


def bp_ice():
    cv = Cv(32, 24); sheet(cv, 5, 3, 22, 14)
    L = BL[0]
    cv.line([(16, 5), (21, 8), (21, 13), (16, 15), (11, 13), (11, 8), (16, 5)], L)
    cv.line([(16, 5), (16, 10), (21, 8)], L); cv.line([(16, 10), (11, 8)], L); cv.line([(16, 10), (16, 15)], L)
    cv.rect(7, 14, 3, 1, L); cv.rect(23, 5, 3, 1, L)
    cv.outline(); return cv


def notice():
    cv = Cv(32, 24)
    frame(cv, 5, 3, 22, 14)
    cv.rect(7, 5, 18, 10, CR[2])
    for (x, y, w, h, c) in ((8, 6, 6, 7, CR[0]), (15, 6, 5, 4, CR[1]), (21, 6, 3, 8, OG[1]), (15, 11, 5, 3, CR[0])):
        cv.rect(x, y, w, h, c)
    for (x, y, w) in ((9, 8, 4), (9, 10, 4), (16, 7, 3), (16, 12, 3)):
        cv.rect(x, y, w, 1, BG[3])
    cv.px(10, 6, "#ff6a55"); cv.px(17, 6, "#ff6a55")
    cv.outline(); return cv


WALL = [("monitor_on", "Monitor ligado", monitor_on), ("monitor_off", "Monitor apagado e rachado", monitor_off),
        ("bp_plan", "Diagrama · planta da base", bp_plan), ("bp_ship", "Diagrama · nave", bp_ship),
        ("bp_ice", "Diagrama · cristal de gelo", bp_ice), ("notice", "Quadro de avisos", notice)]


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for pid, _, fn in WALL:
        cv = fn(); cv.check(); cv.image().save(PEND / f"wall_{pid}.png")
        ic = to_icon(cv); ic.check(); ic.image().save(PEND / f"icon_wall_{pid}.png")


if __name__ == "__main__":
    main()
