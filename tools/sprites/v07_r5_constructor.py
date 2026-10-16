#!/usr/bin/env python3
"""v0.7 Lore · rodada 5 · ícone do construtor: forma da B (tablet em 3/4), casca creme + laranja (paleta das máquinas).

    python3 tools/sprites/v07_r5_constructor.py   ->  pendentes/r5_icon_constructor_{A,B}.png   (A = laranja na lateral, B = moldura laranja)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import from_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"
PAL = {"w": "#fbf7ec", "a": "#f4f6f8", "b": "#e1e5ea", "c": "#c8cdd4", "d": "#cfc4ab", "e": "#8c93a3",
       "o": "#e2733a", "h": "#f29a62", "r": "#a8471f", "K": "#17181c", "n": "#1f5a66", "L": "#c8f6ff", "G": "#7fd67a"}
A = [  # laranja = painel da lateral e empunhadura (como a B verde, na paleta das máquinas)
    "................",
    "..aaaaaaaaaaaa..",
    ".abbdbbbbbbbbbc.",
    ".bohdKnKnKnKnbc.",
    ".bohdKKKKKLLKbc.",
    ".brhdKKKKLLKKbc.",
    ".bohdKKLLKKKKbc.",
    ".brodKnKnKnKnbc.",
    ".bohdLLnKnKnKbc.",
    ".bcddddddddddd..",
    "..cdddddddddd...",
    "...ddoodd.......",
    "...ddrrdd.......",
    "...cddddc.......",
    "....cddc........",
    "................",
]
B = [  # laranja = moldura/faixa em volta da tela e empunhadura; lateral creme lisa com ranhuras
    "................",
    "..aaaaaaaaaaaa..",
    ".abbdooooooooac.",
    ".bbbdoKnKnKnoac.",
    ".bcbdoKKKKKLLoc.",
    ".bbbdoKKKKLLKoc.",
    ".bcbdoKKLLKKKoc.",
    ".bbbdoKnKnKnKoc.",
    ".bcbdoLLnKnKnoc.",
    ".bbddoooooooooc.",
    "..cdddddddddddd.",
    "...ddoodd.......",
    "...ddrrdd.......",
    "...cddddc.......",
    "....cddc........",
    "................",
]


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for t, rows in (("A", A), ("B", B)):
        cv = from_map(rows, PAL); cv.outline(); cv.check()
        cv.image().save(PEND / f"r5_icon_constructor_{t}.png")


if __name__ == "__main__":
    main()
