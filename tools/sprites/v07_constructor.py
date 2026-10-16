#!/usr/bin/env python3
"""v0.7 Lore · construtor com módulo de scanner (ícone 16×16). 2 candidatas, lado a lado com o atual.

    python3 tools/sprites/v07_constructor.py

Saída: reports/design/v07_lore/pendentes/icon_constructor_{A,B}.png (CANDIDATAS). O construtor só tem este ícone no
jogo (hotbar, inventário, fabricador; o `render.py` também amplia 3× pro painel). Mesma paleta do icon_constructor atual.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import Cv, OUT, from_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"

EQ = {
    "W": "#ffffff", "w": "#f4f6f8", "l": "#e1e5ea", "m": "#c8cdd4", "s": "#abb2bb", "d": "#8c949e", "g": "#6b717a",
    "k": "#3b3f46", "K": "#2a2d33", "o": "#e2733a", "h": "#f29a62", "r": "#a8471f",
    "c": "#59d0e6", "C": "#2b9fb8", "L": "#c8f6ff", "n": "#1f5a66", "G": "#7fd67a", "y": "#f2c46d",
}

A = [   # módulo de scanner em cima do corpo: carcaça cinza com visor ciano e um ping, LED laranja
    "................",
    "..ggggggg.......",
    ".gnLGGGng..ggg..",
    ".gnGGyGng.gmLWg.",
    ".llwwwwwwkgLccg.",
    ".wWwwwwwwkgcccg.",
    ".hooooooohgccCg.",
    ".wllllllmkgcCCg.",
    ".lmmmmmmmkgmCng.",
    "..ssskssss.ggg..",
    "...ohr.k........",
    "...ohr.k........",
    "..ohr...........",
    "..ohr...........",
    "..rrr...........",
    "................",
]
B = [   # módulo de scanner embaixo do cano: tambor cinza com lente verde, e um ping saindo pra frente
    "................",
    "................",
    "...........ggg..",
    "...kKKk...gmLWg.",
    ".llwwwwwwkgLccg.",
    ".wWwwwwwwkgcccg.",
    ".hooooooohgccCg.",
    ".wllllllmkgcCCg.",
    ".lmmmmmmmkgmCng.",
    "..ssskssssggggg.",
    "...ohr.kggGGgg..",
    "...ohr.kgGLGgg..",
    "..ohr...kgGGgg..",
    "..ohr....ggggG..",
    "..rrr...........",
    "................",
]


def icon(rows):
    cv = from_map([r.ljust(16, ".") for r in rows], EQ)
    cv.outline()
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for tag, rows in (("A", A), ("B", B)):
        cv = icon(rows); cv.check(); cv.image().save(PEND / f"icon_constructor_{tag}.png")


if __name__ == "__main__":
    main()
