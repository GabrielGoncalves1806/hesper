#!/usr/bin/env python3
"""v0.7 Lore · rodada 3 · mesas de parede (1 tile, colada na parede norte, tampo alto).

    python3 tools/sprites/v07_r3_desks.py    ->  pendentes/prop_wall_desk_{a,b}.png + icon_prop_wall_desk_{a,b}.png

Sprite 32×40 (blit (tx·32, ty·32−8), igual aos props). O tampo começa na linha 1 do PNG = linha 17 da face de 24 px da
parede de cima (a face ocupa y+8..y+32 do tile da parede; o PNG cobre os 8 px de baixo dela): o pé do monitor
(linhas 16–18 da face) fica atrás da borda do tampo, então o monitor "senta" na mesa.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import Cv  # noqa: E402
from v07_props import BG, CR, OG, shade, to_icon  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"


def top(cv, x0=3, x1=29):
    w = x1 - x0
    cv.rect(x0, 1, w, 10, CR[0]); cv.rect(x0, 1, w, 1, "#ffffff")
    cv.rect(x0, 9, w, 2, CR[2]); cv.rect(x0, 11, w, 5, BG[1]); cv.rect(x0, 11, w, 1, BG[0]); cv.rect(x0, 15, w, 1, BG[2])
    cv.rect(x0, 11, 1, 5, BG[0]); cv.rect(x1 - 1, 11, 1, 5, BG[2])


def desk_a():
    cv = Cv(32, 40); shade(cv, 13)
    top(cv)
    # pernas e prateleira de baixo com caixa
    cv.rect(4, 16, 3, 20, BG[3]); cv.rect(4, 16, 1, 20, BG[1]); cv.rect(25, 16, 3, 20, BG[3]); cv.rect(25, 16, 1, 20, BG[1])
    cv.rect(7, 28, 18, 2, BG[2]); cv.rect(7, 28, 18, 1, BG[0]); cv.rect(7, 30, 18, 1, BG[3])
    cv.rect(10, 22, 8, 6, "#bb6a3c"); cv.rect(10, 22, 8, 2, "#dc8a54"); cv.rect(10, 24, 8, 1, "#1b1630")
    cv.rect(19, 24, 5, 4, CR[1]); cv.rect(19, 24, 5, 1, CR[0])
    # em cima: teclado e caneca
    cv.rect(9, 7, 11, 3, BG[3]); cv.rect(9, 7, 11, 1, BG[1])
    for x in range(10, 19, 2):
        cv.px(x, 8, BG[0])
    cv.rect(23, 4, 4, 5, OG[1]); cv.rect(23, 4, 4, 1, OG[0]); cv.px(27, 6, OG[1])
    cv.outline(); return cv


def desk_b():
    cv = Cv(32, 40); shade(cv, 13)
    top(cv)
    # pedestal de gavetas à direita, vão com pernas à esquerda
    cv.rect(15, 16, 14, 20, BG[2]); cv.rect(15, 16, 14, 1, BG[0]); cv.rect(28, 16, 1, 20, BG[3]); cv.rect(15, 34, 14, 2, BG[3])
    for i, y in enumerate((18, 25)):
        cv.rect(17, y, 10, 5, BG[1]); cv.rect(17, y, 10, 1, BG[0]); cv.rect(17, y + 4, 10, 1, BG[3])
        cv.rect(20, y + 2, 4, 1, OG[1]); cv.px(20, y + 2, OG[0])
    cv.rect(17, 31, 10, 3, BG[1]); cv.rect(17, 31, 10, 1, BG[0]); cv.rect(20, 32, 4, 1, BG[4])
    cv.rect(4, 16, 3, 20, BG[3]); cv.rect(4, 16, 1, 20, BG[1])
    cv.rect(8, 33, 6, 2, BG[3]); cv.rect(9, 32, 4, 1, BG[2])        # banquinho embaixo
    # em cima: pilha de papéis e luminária de mesa
    cv.rect(6, 5, 8, 5, CR[1]); cv.rect(6, 5, 8, 1, CR[0]); cv.rect(6, 7, 8, 1, CR[3]); cv.rect(7, 4, 7, 1, CR[0])
    cv.rect(21, 8, 6, 2, BG[3]); cv.line([(23, 8), (24, 4), (27, 3)], BG[2]); cv.rect(26, 3, 4, 2, OG[1]); cv.px(26, 3, OG[0])
    cv.outline(); return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for k, fn in (("a", desk_a), ("b", desk_b)):
        c = fn(); c.check(); c.image().save(PEND / f"prop_wall_desk_{k}.png")
        i = to_icon(c); i.check(); i.image().save(PEND / f"icon_prop_wall_desk_{k}.png")


if __name__ == "__main__":
    main()
