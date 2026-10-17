"""v0.8 · ícones 16×16 (estilo dos icon_* aprovados: chapado, 2–3 faixas, contorno #1b1630, um brilho).

Orgânicos (alga e plantas) saem da mesma grade G das plantas do cultivador; os mecânicos e os frascos são desenhados
à mão em grade de caracteres. Sem aleatório.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image

import v08_plants_art as PA

INK = "#1b1630"


def rgb(c):
    return PA.rgb(c)


def from_rows(rows, pal):
    assert len(rows) == 16, len(rows)
    a = np.zeros((16, 16, 4), np.uint8)
    for y, row in enumerate(rows):
        assert len(row) == 16, (y, row, len(row))
        for x, ch in enumerate(row):
            if ch != ".":
                a[y, x] = rgb(pal[ch])
    return a


BASE = {"a": INK, "w": "#fdf8ec", "c": "#efe6d4", "s": "#d6c9b4", "S": "#a99a8c",
        "o": "#e2733a", "O": "#a9482a", "L": "#f4a06a",
        "m": "#c9c4d6", "M": "#a7a3b8", "n": "#7d7892", "N": "#58536b", "k": "#2e2a3a",
        "g": "#7fd67a", "y": "#59d0e6", "Y": "#c8f6ff", "z": "#2b8fb3"}


# ---- máquinas (menu do construtor) -----------------------------------------------------------------------------------
def icon_cultivator():
    pal = dict(BASE, r="#d2f7e6", q="#a8e6cf", Q="#66b0a6", l="#7fc94f", d="#2f6b3a", b="#6e523f", B="#4a3427",
               G="#e8ffd8")
    rows = [
        ".....aaaaaa.....",
        "...aawwwwwcaa...",
        "...awwgggwcca...",
        "...asccccccSa...",
        "...aooooooOOa...",
        "...arqqqlqqQa...",
        "...arqqldlqQa...",
        "...aGgglllggg...",
        "...arqldldlQa...",
        "...arlldlllQa...",
        "...abbbdbbbBa...",
        "..aaBBBBBBBBaa..",
        "..awwwwwwwwwca..",
        "..aoooookgooOa..",
        ".anMMMMMMMMMMNa.",
        ".aaaaaaaaaaaaaa.",
    ]
    rows[7] = "...aGgglllggga.."[:16]
    rows[7] = "...aGggglgggga.."
    return from_rows(rows, pal)


def icon_microscope():
    pal = dict(BASE, G="#b6f0b0")
    rows = [
        "................",
        ".....aaaa.......",
        ".....akka.......",
        "....awwwca......",
        "....awwcsaaaaaa.",
        "....aoooOakGGka.",
        ".....aMnwakggka.",
        ".....aMnwakkkka.",
        ".....aYyca.aaa..",
        "......aaca..aMa.",
        ".aaaaaaaaaaaaaa.",
        ".awwwwwwwwwwwca.",
        ".aooooooooooOOa.",
        ".acckgcccccssSa.",
        ".anMMMMMMMMMMNa.",
        ".aaaaaaaaaaaaaa.",
    ]
    return from_rows(rows, pal)


def icon_centrifuge():
    pal = dict(BASE, l="#7fc94f", d="#2f6b3a", v="#b48cf0", V="#7a4cc0", R="#a9b0be")
    rows = [
        "................",
        "....aaaaaaaa....",
        "..aammmmmmmmaa..",
        ".amkklkkkkvkkma.",
        ".amkldkkkkVvkma.",
        ".amkkkkRRkkkkma.",
        ".amkkkkRRkkkkma.",
        ".amkvVkkkkldkma.",
        ".amkkvkkkkklkma.",
        "..aammmmmmmmaa..",
        ".awwwwwwwwwwwca.",
        ".aooooooooooOOa.",
        ".acckgkcccLcssa.",
        ".acccccccLLLssa.",
        ".anMMMMMMMMMMNa.",
        ".aaaaaaaaaaaaaa.",
    ]
    return from_rows(rows, pal)


def icon_water_collector():
    pal = dict(BASE, f="#e3e5ee", F="#5e6176", q="#9fe0f5", Q="#4aa8d8")
    rows = [
        "....aaaaaaaa....",
        "...aNmMmmMmNa...",
        "...aaooooOOaa...",
        "...affffffffa...",
        "...aFFFFFFFFa...",
        "...affffYfffa...",
        "...aFFFFFFFFa...",
        "...affffffffa...",
        "..aaaaaaaaaaaa..",
        ".awwwwwwwwwwwca.",
        ".akYkkcccccsssa.",
        ".akqqkcckyykssa.",
        ".akQQkccaaaassa.",
        ".aooooooooooOOa.",
        ".anMMMMMMMMMMNa.",
        ".aaaaaaaaaaaaaa.",
    ]
    rows[12] = ".akQQkcccccsssa."
    rows[11] = ".akqqkcckyyksSa."
    return from_rows(rows, pal)


# ---- frascos de amostra --------------------------------------------------------------------------------------------
VIAL = [
    "................",
    "....aaaaaaaa....",
    "....aCCCCCCa....",
    "....aDDDDDDa....",
    ".....aWGGGa.....",
    ".....aWGGGa.....",
    ".....aW112a.....",
    ".....aW122a.....",
    ".....a1223a.....",
    ".....a1223a.....",
    ".....a1223a.....",
    ".....a2233a.....",
    ".....a2333a.....",
    "......a33a......",
    ".......aa.......",
    "................",
]


def _vial(liq, cap, extra=None, marks=()):
    pal = {"a": INK, "W": "#ffffff", "G": "#d8eef6", "1": liq[0], "2": liq[1], "3": liq[2],
           "C": cap[0], "D": cap[1]}
    rows = [list(r) for r in VIAL]
    for (x, y, ch) in marks:
        rows[y][x] = ch
    if extra:
        pal.update(extra)
    return from_rows(["".join(r) for r in rows], pal)


def icon_sample_basic():
    # amostra simples: líquido verde-água claro, tampa ciano
    return _vial(("#c8f6e0", "#7fd6b0", "#3f9690"), ("#59d0e6", "#2b8fb3"))


def icon_sample_mutant():
    # amostra com mutação: azul-violeta com um redemoinho claro dentro, tampa violeta
    return _vial(("#a6c8ff", "#5f7ee0", "#3a3a9a"), ("#b48cf0", "#7a4cc0"), extra={"x": "#e9fbff", "v": "#b48cf0"},
                 marks=[(7, 8, "x"), (8, 9, "v"), (7, 10, "x"), (8, 11, "v")])


def icon_sample_rare():
    # amostra rara: dourado aceso com brilhinhos fora do frasco, tampa dourada
    return _vial(("#fff0b8", "#f2c46d", "#b8823c"), ("#fff0b8", "#b8823c"), extra={"x": "#ffffff", "y": "#fff0b8"},
                 marks=[(12, 4, "y"), (13, 5, "x"), (12, 6, "y"), (11, 5, "y"), (3, 9, "y"), (2, 10, "x"),
                        (3, 11, "y"), (7, 9, "x")])


# ---- cápsula vazia (par do icon_water_capsule aprovado: mesmo desenho, sem a água) ---------------------------------
def icon_water_capsule_empty(src_path):
    im = np.array(Image.open(src_path).convert("RGBA"))
    swap = {"#9fe0f5": "#cfeaf4", "#d8f6ff": "#cfeaf4", "#4aa8d8": "#cfeaf4", "#2f7fb3": "#9fc9dc",
            "#1f5a85": "#9fc9dc"}
    out = im.copy()
    for y in range(16):
        for x in range(16):
            h = "#%02x%02x%02x" % tuple(im[y, x, :3])
            if im[y, x, 3] and h in swap:
                out[y, x, :3] = rgb(swap[h])[:3]
    # uma gotinha esquecida no fundo, pra ler "vazia" e não "vidro"
    out[10, 9, :3] = rgb("#4aa8d8")[:3]
    out[10, 8, :3] = rgb("#9fe0f5")[:3]
    return out


# ---- culturas (itens) ----------------------------------------------------------------------------------------------
def icon_algae():
    p = PA.PAL["algae"]
    g = PA.G(16, 16)
    cols = (p["d"], p["m"], p["l"])
    for (dx, h, amp, ph, lean) in ((-4, 10, 0.8, 0.3, -0.25), (-1, 12, 0.9, 1.9, 0.0), (2, 11, 0.9, 3.3, 0.2),
                                   (4, 8, 0.7, 4.6, 0.4)):
        pts = [(7 + dx * 0.5 + lean * k + amp * math.sin(k / 2.0 + ph) * min(1, k / 3), 14 - k) for k in range(h + 1)]
        g.line(pts, cols, width=2)
        g.px(pts[-1][0], pts[-1][1], p["h"])
    for (x, y) in ((5, 7), (9, 5), (10, 9), (6, 10)):
        g.px(x, y, p["y"])
        g.px(x, y - 1, p["Y"])
    for x in range(5, 11):                    # amarrinho laranja do maço
        g.px(x, 12, "#e2733a" if x < 10 else "#a9482a")
    g.px(5, 12, "#f4a06a")
    g.outline(INK)
    return g.array()


def icon_plant_1():
    p = PA.PAL["plant_1"]
    g = PA.G(16, 16)
    cols = (p["d"], p["m"], p["l"])
    g.line([(7.5, 15), (7.6, 11), (7.2, 7), (7.8, 4)], cols, width=2)
    g.blob(4.2, 9.5, 3.6, 2.3, cols, hl=p["h"])
    g.blob(11.6, 6.5, 3.4, 2.2, cols, hl=p["h"])
    g.blob(6.5, 3.5, 2.2, 1.8, cols, hl=p["h"])
    g.blob(11.0, 11.8, 2.0, 2.3, (p["wd"], p["wm"], p["wl"]), hl=p["ww"])
    g.px(10, 9, p["d"])
    g.outline(INK)
    return g.array()


def icon_plant_2():
    p = PA.PAL["plant_2"]
    g = PA.G(16, 16)
    cols = (p["d"], p["m"], p["l"])
    stem = [(6.5 + 0.5 * math.sin(k / 2.5), 15 - k) for k in range(8)]
    cx, cy, r = 9.0, 6.0, 4.6
    spiral = [(cx + r * (1 - i / 24) * math.cos(math.pi - i * 0.40), cy - r * (1 - i / 24) * math.sin(math.pi - i * 0.40))
              for i in range(22)]
    spiral = [(stem[-1][0], stem[-1][1])] + spiral
    g.line(stem, cols, width=2)
    g.line(spiral, cols, width=2)
    ex, ey = spiral[-1]
    g.px(ex, ey, p["f"])
    g.px(ex + 1, ey, p["g"])
    for (x, y) in ((5, 12), (8, 10), (12, 3)):
        g.px(x, y, p["g"])
    g.line([(4, 15), (3, 13), (2.5, 11)], cols, width=1)
    g.px(2, 10, p["f"])
    g.outline(INK)
    return g.array()


def icon_plant_3():
    p = PA.PAL["plant_3"]
    g = PA.G(16, 16)
    g.blob(4.5, 13.5, 3.2, 1.3, (p["ld"], p["lm"], p["lm"]))
    g.blob(11.5, 13.5, 3.2, 1.3, (p["ld"], p["lm"], p["lm"]))
    g.line([(7.5, 15), (7.5, 9)], (p["d"], p["m"], p["l"]), width=2)
    for (dx, dy, rx, ry) in ((-4.5, 7.5, 2.6, 2.0), (4.5, 7.5, 2.6, 2.0), (-2.5, 4.0, 2.2, 2.8), (2.5, 4.0, 2.2, 2.8),
                             (0, 2.6, 2.2, 2.5)):
        g.blob(8 + dx, dy + 0.5, rx, ry, (p["i0"], p["i1"], p["i2"]), hl=p["i3"])
    g.blob(8, 7, 2.2, 1.8, (p["v0"], p["v1"], p["v2"]))
    g.px(7, 6, "#ffffff")
    g.px(8, 6, "#ffffff")
    g.outline(INK)
    return g.array()


ICONS = {
    "icon_algae": icon_algae, "icon_plant_1": icon_plant_1, "icon_plant_2": icon_plant_2,
    "icon_plant_3": icon_plant_3, "icon_sample_basic": icon_sample_basic, "icon_sample_mutant": icon_sample_mutant,
    "icon_sample_rare": icon_sample_rare, "icon_cultivator": icon_cultivator, "icon_microscope": icon_microscope,
    "icon_centrifuge": icon_centrifuge, "icon_water_collector": icon_water_collector,
}
