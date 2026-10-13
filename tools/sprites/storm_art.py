#!/usr/bin/env python3
"""Arte da TEMPESTADE de poeira (v0.4 Marco 1 · estágio 1 `storm`): propostas de cor, textura de nuvem,
faixas de vento e o ícone de vento do aviso RAJADA no HUD.

    python3 tools/sprites/storm_art.py          (PIL + numpy do sistema; determinístico, sem aleatório)

Saídas (tudo PENDENTE, aguardando o dono):
  assets/sprites/_pending/storm/storm_palettes.json      as 3 propostas (fundo, nuvem, grãos, faixa)
  assets/sprites/_pending/storm/dust_cloud_{a,b,c}.png   256×256, emenda nos 4 lados, blocos de 4 px (a célula
                                                          do Lighting), 3 tons chapados, opaca
  assets/sprites/_pending/storm/dust_streaks_{a,b,c}.png 128×8: 4 faixas de vento de 1 px de altura (opacas;
                                                          o jogo aplica o alfa fixo na camada inteira)
  assets/sprites/_pending/storm/hud_wind.png             8×8 px da UI, glifo de 1 cor (#e2733a), alfa 0/255

Os mockups 960×540 saem do tools/sprites/storm_capture.py (roda com uv: usa o jogo de verdade).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "sprites" / "_pending" / "storm"

# ---- as 3 propostas ----------------------------------------------------------------------------------
# bg      = cor de fundo da camada de poeira (o "tom médio" da nuvem)
# cloud   = (escuro, médio = bg, claro): os 3 tons da textura de nuvem
# grains  = (claro, brilho, escuro): os grãos
# streak  = a faixa de vento
PALETTES = {
    "a": {"name": "Ferrugem", "bg": "#a8694a",
          "cloud": ["#9c6045", "#a8694a", "#b47553"],
          "grains": ["#cf9a70", "#efcba0", "#6e3f2b"],
          "streak": "#dcab80"},
    "b": {"name": "Ocre", "bg": "#ad875f",
          "cloud": ["#a17d57", "#ad875f", "#b9936a"],
          "grains": ["#d8b585", "#f3e0b6", "#74553a"],
          "streak": "#e4c797"},
    "c": {"name": "Crepúsculo", "bg": "#6e443c",
          "cloud": ["#643d37", "#6e443c", "#7a4d44"],
          "grains": ["#a87260", "#d8a585", "#43262a"],
          "streak": "#bc8670"},
}

WIND_GLYPH = [            # 8×8 px da UI (o raio da energia é 5×8): 2 linhas de vento com a ponta enrolada
    "....##..",
    "...#..#.",
    "......#.",
    "######..",
    "........",
    "#######.",
    ".......#",
    ".....##.",
]
# de cima: a linha curta enrola pra cima, a comprida enrola pra baixo (o "redemoinho" do ícone de vento)


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hsh(x: int, y: int, s: int) -> float:
    n = (x * 374761393 + y * 668265263 + s * 2246822519 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 15
    return n / 4294967296.0


def periodic_noise(w: int, h: int, gx: int, gy: int, seed: int) -> np.ndarray:
    """Value noise que emenda: grade gx×gy com as bordas repetindo (o lattice dá a volta)."""
    out = np.zeros((h, w))
    for y in range(h):
        fy = y / h * gy
        iy = int(fy)
        ty = fy - iy
        ty = ty * ty * (3 - 2 * ty)
        for x in range(w):
            fx = x / w * gx
            ix = int(fx)
            tx = fx - ix
            tx = tx * tx * (3 - 2 * tx)
            a = hsh(ix % gx, iy % gy, seed)
            b = hsh((ix + 1) % gx, iy % gy, seed)
            c = hsh(ix % gx, (iy + 1) % gy, seed)
            d = hsh((ix + 1) % gx, (iy + 1) % gy, seed)
            out[y, x] = a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty
    return out


def cloud_levels() -> np.ndarray:
    """64×64 células (cada uma vira 4×4 px): 0 = escuro, 1 = médio, 2 = claro. Nuvens esticadas na horizontal
    (o vento dominante sopra pra leste), com 2 oitavas pra borda não ficar redonda demais."""
    n = 0.8 * periodic_noise(64, 64, 3, 9, 11) + 0.2 * periodic_noise(64, 64, 6, 18, 12)
    lo, hi = np.quantile(n, 0.28), np.quantile(n, 0.74)
    lv = np.ones((64, 64), dtype=np.uint8)
    lv[n < lo] = 0
    lv[n > hi] = 2
    return lv


def make_cloud(pal: dict, lv: np.ndarray) -> Image.Image:
    cols = np.array([rgb(c) for c in pal["cloud"]], dtype=np.uint8)
    small = cols[lv]                                       # 64×64×3
    big = small.repeat(4, axis=0).repeat(4, axis=1)        # blocos de 4 px (célula do Lighting)
    return Image.fromarray(big)


STREAKS = [   # (y, padrão): "#" = tom da faixa, "+" = grão claro na cabeça, "." = vazio. Cabeça à DIREITA (vento pra leste)
    (1, "....######.###########.##################+"),
    (3, ".........####.....##############+"),
    (5, "..######.##.#####################.############################+"),
    (7, "...###.####################+"),
]


def make_streaks(pal: dict) -> Image.Image:
    im = Image.new("RGBA", (128, 8), (0, 0, 0, 0))
    px = im.load()
    s = (*rgb(pal["streak"]), 255)
    g = (*rgb(pal["grains"][1]), 255)
    for y, pat in STREAKS:
        for x, ch in enumerate(pat):
            if ch == "#":
                px[x, y] = s
            elif ch == "+":
                px[x, y] = g
    return im


def make_wind_icon() -> Image.Image:
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    px = im.load()
    c = (*rgb("#e2733a"), 255)
    for y, row in enumerate(WIND_GLYPH):
        for x, ch in enumerate(row):
            if ch == "#":
                px[x, y] = c
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lv = cloud_levels()
    for key, pal in PALETTES.items():
        make_cloud(pal, lv).save(OUT / f"dust_cloud_{key}.png")
        make_streaks(pal).save(OUT / f"dust_streaks_{key}.png")
    make_wind_icon().save(OUT / "hud_wind.png")
    data = {"palettes": PALETTES, "wind_glyph": WIND_GLYPH,
            "streaks": [{"y": y, "len": len(p)} for y, p in STREAKS]}
    (OUT / "storm_palettes.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print("ok:", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
