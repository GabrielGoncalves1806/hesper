#!/usr/bin/env python3
"""v0.7 Lore · rodada 4 · ícone do construtor como scanner de mão (tela grande com grade e HUD). 2 candidatas 16×16.

    python3 tools/sprites/v07_r4_constructor.py   ->  pendentes/r4_icon_constructor_{A,B}.png
O jogo amplia o MESMO 16×16 em 3× pro painel (render.py: scale_by(icon_constructor, 3)); não há outro sprite.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import from_map  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"

PAL = {
    "w": "#f4f6f8", "l": "#e1e5ea", "m": "#c8cdd4", "s": "#abb2bb", "g": "#6b717a",
    "o": "#e2733a", "h": "#f29a62", "r": "#a8471f",
    "K": "#17181c", "n": "#1f5a66", "G": "#7fd67a", "L": "#c8f6ff",
    "a": "#8fc9a0", "b": "#5a9a74", "c": "#3f7a5a", "d": "#2f5a44",
}
A = [  # frente: tela dominando, casca creme com faixa laranja (família das máquinas)
    "................",
    "..wwwwwwwwwwww..",
    ".wllllllllllllm.",
    ".wlKnKnKnKnKnlm.",
    ".wlKKKKKKKLLKlm.",
    ".wlKKKKKLLKKKlm.",
    ".wlKKKLLKKKKKlm.",
    ".wlKnKnKnKnKnlm.",
    ".wlKLLnKnKnKnlm.",
    ".wllllllllllllm.",
    ".hooooooooooorm.",
    "..msssssssssmm..",
    "....mooooom.....",
    "....mooooom.....",
    "....mrrrrrm.....",
    "................",
]
B = [  # 3/4: lateral esquerda com painel laranja, tela à direita, casca verde-escura (como a referência)
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


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for tag, rows in (("A", A), ("B", B)):
        cv = from_map(rows, PAL); cv.outline(); cv.check()
        cv.image().save(PEND / f"r4_icon_constructor_{tag}.png")


if __name__ == "__main__":
    main()
