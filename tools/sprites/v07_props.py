#!/usr/bin/env python3
"""v0.7 Lore · kit médio de props (16), 1 tile cada: sprite 32×40 (pé na linha 37, como o baú) + ícone 16×16.

    python3 tools/sprites/v07_props.py

Saída: reports/design/v07_lore/pendentes/prop_<id>.png e icon_prop_<id>.png (CANDIDATOS: nada vai pra assets/sprites).
`ice_stain` é decal de chão (32×32, sem colisão). Os ícones saem do próprio sprite (sem contorno, reduzido 2:1 por
maioria de cor, contorno refeito), então sempre batem com ele.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import Cv, OUT, SHADOW, hsh, scatter  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"

CR = ["#fdf8ec", "#efe6d4", "#d6c9b4", "#a99a8c", "#7b6f69"]          # creme das máquinas
BG = ["#d9dde6", "#a9b0be", "#8c93a3", "#58536b", "#3a3549"]          # cinza-lavanda
OG = ["#f4a06a", "#e2733a", "#a9482a"]                                # laranja
CT = ["#f0b27a", "#dc8a54", "#bb6a3c", "#8a4a2a"]                     # caixote (cor de ferro)
IC = ["#f2fdff", "#c8f6ff", "#a6ecff", "#7fd3ef", "#4fb3d6"]          # gelo
DK = ["#2a2d33", "#17131e", "#102018"]
SCR = ["#3b3f46", "#2a2d33", "#17181c"]


def new(h=40):
    cv = Cv(32, h)
    return cv


def shade(cv, rx=12, ry=3, cy=36):
    cv.shadow_ell(16, cy, rx, ry)


def slab(cv, x, y, w, h, cols, hl=True):
    """Retângulo com topo claro e pé escuro (cols de claro a escuro, 3 ou 4 tons)."""
    n = len(cols)
    for i, c in enumerate(cols):
        y0 = y + h * i // n
        y1 = y + h * (i + 1) // n
        cv.rect(x, y0, w, y1 - y0, c)
    if hl:
        cv.rect(x, y, w, 1, cols[0])


def table():
    cv = new(); shade(cv, 13)
    cv.rect(5, 29, 3, 7, BG[3]); cv.rect(24, 29, 3, 7, BG[3]); cv.rect(5, 29, 1, 7, BG[1]); cv.rect(24, 29, 1, 7, BG[1])
    cv.rect(4, 17, 24, 9, CR[0]); cv.rect(4, 17, 24, 1, "#ffffff"); cv.rect(4, 24, 24, 2, CR[2])
    cv.rect(4, 26, 24, 4, BG[1]); cv.rect(4, 26, 24, 1, BG[0]); cv.rect(4, 29, 24, 1, BG[2])
    cv.rect(6, 19, 7, 1, CR[2]); cv.rect(18, 21, 6, 1, CR[2])
    # coisas em cima: prancheta e caneca
    cv.rect(7, 19, 8, 5, BG[3]); cv.rect(8, 20, 6, 3, CR[0]); cv.rect(9, 21, 4, 1, BG[2])
    cv.rect(20, 17, 4, 5, OG[1]); cv.rect(20, 17, 4, 1, OG[0]); cv.px(24, 19, OG[1])
    cv.outline(); return cv


def chair():
    cv = new(); shade(cv, 9)
    cv.rect(10, 11, 12, 11, BG[3]); cv.rect(11, 12, 10, 8, BG[2]); cv.rect(11, 12, 10, 2, BG[0]); cv.rect(12, 18, 8, 1, BG[3])
    cv.rect(8, 22, 16, 7, BG[1]); cv.rect(8, 22, 16, 2, BG[0]); cv.rect(8, 27, 16, 2, BG[2])
    cv.rect(9, 24, 14, 2, OG[1]); cv.rect(9, 24, 14, 1, OG[0])
    cv.rect(9, 29, 2, 7, BG[3]); cv.rect(21, 29, 2, 7, BG[3]); cv.rect(15, 29, 2, 6, BG[4])
    cv.outline(); return cv


def chair_fallen():
    cv = new(); shade(cv, 13, 3, 35)
    # caída de lado: encosto deitado no chão (esquerda), assento em pé no meio, pernas apontando pra direita
    cv.rect(3, 29, 10, 7, BG[3]); cv.rect(3, 29, 10, 3, BG[1]); cv.rect(3, 29, 10, 1, BG[0]); cv.rect(5, 33, 6, 1, BG[2])
    cv.rect(12, 21, 6, 15, BG[1]); cv.rect(12, 21, 6, 2, BG[0]); cv.rect(15, 23, 3, 13, BG[2]); cv.rect(12, 23, 3, 5, OG[1]); cv.rect(12, 23, 3, 1, OG[0])
    cv.rect(18, 24, 11, 3, BG[3]); cv.rect(18, 24, 11, 1, BG[1])
    cv.rect(18, 32, 11, 3, BG[3]); cv.rect(18, 32, 11, 1, BG[1]); cv.rect(28, 31, 2, 5, BG[4])
    cv.outline(); return cv


def crate():
    cv = new(); shade(cv, 13)
    cv.rect(4, 14, 24, 8, CT[0]); cv.rect(4, 14, 24, 1, "#ffd8b0")
    cv.rect(4, 22, 24, 13, CT[1]); cv.rect(4, 22, 24, 1, CT[0]); cv.rect(4, 31, 24, 4, CT[2]); cv.rect(4, 34, 24, 1, CT[3])
    for x in (4, 25):
        cv.rect(x, 22, 3, 13, CT[2]); cv.rect(x, 22, 3, 1, CT[1])
    cv.line([(7, 24), (24, 32)], CT[3]); cv.line([(7, 32), (24, 24)], CT[3])
    cv.rect(11, 15, 10, 2, CT[2]); cv.rect(13, 28, 6, 3, CR[1]); cv.rect(14, 29, 4, 1, BG[3])
    for (x, y) in ((5, 24), (5, 32), (26, 24), (26, 32)):
        cv.px(x, y, CR[0])
    cv.outline(); return cv


def lab_bench():
    cv = new(); shade(cv, 14)
    cv.rect(2, 19, 28, 7, CR[0]); cv.rect(2, 19, 28, 1, "#ffffff"); cv.rect(2, 24, 28, 2, CR[2])
    cv.rect(3, 26, 26, 10, CR[1]); cv.rect(3, 26, 26, 1, CR[0]); cv.rect(3, 33, 26, 3, CR[3])
    cv.rect(15, 27, 1, 8, CR[3]); cv.rect(5, 28, 8, 4, CR[2]); cv.rect(18, 28, 8, 4, CR[2]); cv.rect(5, 28, 8, 1, CR[0]); cv.rect(18, 28, 8, 1, CR[0])
    cv.rect(8, 30, 3, 1, BG[3]); cv.rect(21, 30, 3, 1, BG[3]); cv.rect(3, 31, 26, 1, OG[1]) if False else None
    cv.rect(3, 33, 26, 1, OG[1])
    # vidraria: balão com líquido ciano, béquer, estante de tubos, aparelhinho
    cv.rect(5, 11, 6, 8, "#d9f3fa"); cv.rect(6, 12, 4, 6, "#59d0e6"); cv.rect(6, 12, 4, 1, IC[0]); cv.rect(7, 9, 2, 3, "#d9f3fa")
    cv.rect(13, 14, 5, 5, "#d9f3fa"); cv.rect(14, 16, 3, 2, "#7fd67a"); cv.rect(14, 14, 3, 1, IC[0])
    cv.rect(20, 15, 9, 4, BG[3]); cv.rect(20, 15, 9, 1, BG[1])
    for x, c in ((21, "#59d0e6"), (23, "#ff6a55"), (25, "#f2c46d"), (27, "#7fd67a")):
        cv.rect(x, 11, 1, 5, c)
    cv.outline(); return cv


def microscope():
    cv = new(); shade(cv, 11)
    cv.rect(4, 22, 24, 8, CR[0]); cv.rect(4, 22, 24, 1, "#ffffff"); cv.rect(4, 28, 24, 2, CR[2])
    cv.rect(4, 30, 24, 6, CR[1]); cv.rect(4, 30, 24, 1, CR[0]); cv.rect(4, 34, 24, 2, CR[3]); cv.rect(10, 31, 12, 3, CR[2]); cv.rect(10, 31, 12, 1, CR[0])
    # microscópio: base, braço curvo, tubo inclinado, platina
    cv.rect(9, 20, 14, 3, BG[3]); cv.rect(9, 20, 14, 1, BG[1])
    cv.rect(11, 8, 4, 13, BG[1]); cv.rect(11, 8, 1, 13, BG[0]); cv.rect(14, 8, 1, 13, BG[2])
    cv.poly([(13, 6), (22, 6), (24, 10), (15, 10)], BG[1]); cv.rect(14, 6, 9, 1, BG[0])
    cv.poly([(17, 9), (22, 9), (24, 18), (19, 18)], BG[2]); cv.rect(18, 18, 6, 3, BG[3])
    cv.rect(17, 3, 5, 4, BG[4]); cv.rect(17, 3, 5, 1, BG[1])
    cv.rect(15, 15, 8, 2, CR[3]); cv.rect(19, 16, 3, 1, "#59d0e6")
    cv.rect(24, 20, 3, 2, OG[1])
    cv.outline(); return cv


def sample_shelf():
    cv = new(); shade(cv, 12)
    cv.rect(4, 3, 24, 33, BG[3]); cv.rect(5, 4, 22, 31, BG[4])
    cv.rect(4, 3, 24, 2, BG[1]); cv.rect(4, 3, 24, 1, BG[0])
    cv.rect(4, 3, 2, 33, BG[2]); cv.rect(26, 3, 2, 33, BG[3])
    for i, y in enumerate((14, 25, 34)):
        cv.rect(5, y, 22, 2, CR[1]); cv.rect(5, y, 22, 1, CR[0]); cv.rect(5, y + 1, 22, 1, CR[3]) if False else None
        for j in range(5):
            x = 7 + j * 4
            hgt = 6 if (i + j) % 3 else 4
            cv.rect(x, y - hgt, 3, hgt, IC[3]); cv.rect(x, y - hgt, 3, 2, IC[1]); cv.px(x, y - hgt, IC[0])
            cv.rect(x, y - hgt - 1, 3, 1, CR[3])
            if (i + j) % 2 == 0:
                cv.rect(x, y - 2, 3, 1, CR[0])
    cv.rect(8, 8, 5, 2, OG[1]) if False else None
    cv.rect(21, 27, 4, 3, OG[1]); cv.rect(22, 28, 2, 1, CR[0])
    cv.outline(); return cv


def bunk():
    cv = new(); shade(cv, 14)
    cv.rect(3, 6, 3, 30, BG[3]); cv.rect(26, 6, 3, 30, BG[3]); cv.rect(3, 6, 1, 30, BG[1]); cv.rect(26, 6, 1, 30, BG[1])
    # colchão de cima e de baixo, vistos de frente (borda grossa) com cobertor laranja e travesseiro
    for y0 in (11, 25):
        cv.rect(4, y0, 24, 3, BG[2]); cv.rect(4, y0, 24, 1, BG[0])
        cv.rect(6, y0 - 5, 20, 6, BG[1]); cv.rect(6, y0 - 5, 20, 1, BG[0])
        cv.rect(14, y0 - 4, 11, 5, OG[1]); cv.rect(14, y0 - 4, 11, 1, OG[0]); cv.rect(14, y0, 11, 1, OG[2])
        cv.rect(7, y0 - 4, 6, 3, CR[0]); cv.rect(7, y0 - 4, 6, 1, "#ffffff"); cv.rect(7, y0 - 2, 6, 1, CR[2])
        cv.rect(4, y0 + 3, 24, 2, BG[3])
    cv.rect(26, 14, 2, 12, BG[2]); cv.rect(26, 17, 3, 1, BG[0]); cv.rect(26, 21, 3, 1, BG[0])      # escadinha
    cv.outline(); return cv


def locker():
    cv = new(); shade(cv, 11)
    cv.rect(7, 4, 18, 32, BG[1]); cv.rect(7, 4, 18, 4, BG[0]); cv.rect(7, 4, 18, 1, "#ffffff")
    cv.rect(7, 8, 18, 28, BG[1]); cv.rect(7, 31, 18, 5, BG[2]); cv.rect(7, 35, 18, 1, BG[3])
    cv.rect(15, 8, 2, 28, BG[3]); cv.rect(7, 8, 1, 28, BG[0]); cv.rect(24, 8, 1, 28, BG[2])
    for y in (11, 13, 15, 17):
        cv.rect(9, y, 5, 1, BG[3]); cv.rect(19, y, 5, 1, BG[3])
    cv.rect(13, 22, 1, 4, CR[0]); cv.rect(18, 22, 1, 4, CR[0])
    cv.rect(7, 27, 18, 2, OG[1]); cv.rect(7, 27, 18, 1, OG[0])
    cv.rect(20, 18, 3, 3, OG[2]); cv.px(21, 19, "#ffd8b0")        # amassado
    cv.outline(); return cv


def console():
    cv = new(); shade(cv, 12)
    cv.rect(4, 24, 24, 12, CR[1]); cv.rect(4, 24, 24, 3, CR[0]); cv.rect(4, 33, 24, 3, CR[3]); cv.rect(4, 24, 24, 1, "#ffffff")
    for x in range(6, 26, 3):
        cv.rect(x, 28, 2, 1, BG[3]); cv.rect(x, 30, 2, 1, BG[3])
    cv.rect(21, 31, 3, 1, BG[1]); cv.px(25, 29, BG[2])
    cv.rect(5, 6, 22, 18, CR[2]); cv.rect(5, 6, 22, 1, CR[0])
    cv.rect(7, 8, 18, 13, SCR[2]); cv.rect(7, 8, 18, 1, SCR[1])
    cv.rect(7, 8, 18, 13, SCR[1]); cv.line([(9, 19), (14, 10)], SCR[0]); cv.line([(12, 20), (19, 10)], SCR[0])
    cv.line([(18, 12), (21, 17), (19, 21)], "#58536b")            # rachadura da tela
    cv.rect(6, 22, 20, 2, CR[3]); cv.rect(8, 22, 2, 1, BG[2]); cv.rect(23, 22, 2, 1, OG[2])
    cv.outline(); return cv


def sample_tank():
    cv = new(); shade(cv, 10)
    cv.rect(7, 31, 18, 5, BG[2]); cv.rect(7, 31, 18, 1, BG[0]); cv.rect(7, 34, 18, 2, BG[3]); cv.rect(7, 33, 18, 1, OG[1])
    cv.rect(8, 5, 16, 3, BG[1]); cv.rect(8, 5, 16, 1, BG[0]); cv.rect(8, 7, 16, 1, BG[3])
    gl = cv.mask(lambda d: d.rectangle([8, 8, 23, 30], fill=255))
    cv.banded(gl, ["#d9f6fb", "#a9e0ee", "#7fc3d6", "#5aa3ba"], cuts=[.15, .5, .85])
    cv.rect(8, 8, 2, 23, "#effcff"); cv.rect(22, 8, 2, 23, "#4a8aa0")
    # gelo lá dentro e um vulto fino (a "coisa" no gelo, sem dizer o quê)
    cv.rect(11, 18, 10, 12, IC[2]); cv.rect(11, 18, 10, 3, IC[1]); cv.rect(11, 18, 3, 1, IC[0])
    cv.rect(12, 14, 6, 5, IC[3]); cv.rect(12, 14, 6, 2, IC[1])
    cv.line([(15, 22), (17, 25), (14, 28)], "#2f6f86"); cv.px(14, 28, "#17131e")
    for (x, y) in ((11, 11), (20, 12), (19, 16)):
        cv.px(x, y, "#ffffff")
    cv.rect(21, 28, 3, 1, OG[1])
    cv.outline(); return cv


def sign():
    cv = new(); shade(cv, 8)
    cv.rect(15, 20, 3, 16, BG[3]); cv.rect(15, 20, 1, 16, BG[1])
    cv.rect(13, 34, 7, 2, BG[4])
    cv.rect(5, 6, 22, 15, BG[3]); cv.rect(6, 7, 20, 13, CR[1]); cv.rect(6, 7, 20, 2, CR[0]); cv.rect(6, 18, 20, 2, CR[3])
    cv.rect(6, 7, 20, 3, OG[1]); cv.rect(6, 7, 20, 1, OG[0])
    for x in range(6, 26, 4):                                  # listras de advertência
        cv.poly([(x, 9), (x + 2, 9), (x + 4, 12), (x + 2, 12)], DK[0])
    cv.rect(8, 13, 14, 1, BG[3]); cv.rect(8, 15, 9, 1, BG[3]); cv.rect(8, 17, 11, 1, BG[2])
    cv.rect(23, 14, 2, 3, OG[2]); cv.px(24, 18, OG[2])
    cv.px(6, 7, BG[3]); cv.px(25, 19, BG[3])
    cv.outline(); return cv


def rubble():
    cv = new(); shade(cv, 13, 3, 35)
    def chunk(x, y, w, h, c0, c1, c2):
        cv.rect(x, y, w, h, c1); cv.rect(x, y, w, 2, c0); cv.rect(x, y + h - 2, w, 2, c2); cv.px(x, y, c0)
    chunk(4, 28, 12, 8, CR[2], CR[3], CR[4]); chunk(14, 25, 10, 10, BG[1], BG[2], BG[3]); chunk(22, 29, 8, 7, CR[1], CR[2], CR[3])
    chunk(9, 24, 7, 6, BG[2], BG[3], BG[4]); chunk(17, 31, 9, 5, CR[2], CR[3], CR[4])
    cv.rect(11, 29, 4, 1, OG[1]); cv.rect(20, 27, 3, 1, OG[1]); cv.px(6, 30, OG[2])
    cv.line([(24, 24), (27, 18), (28, 14)], BG[3]); cv.line([(26, 25), (30, 21)], BG[3])      # vergalhão torto
    cv.outline(); return cv


def ice_stain():
    cv = Cv(32, 32)
    m = cv.emask(16, 17, 14, 8) | cv.emask(11, 15, 8, 6) | cv.emask(22, 19, 8, 5)
    def f(x, y):
        n = (hsh(x, y, 3) * .3 + (1 - ((x - 16) / 15) ** 2 - ((y - 17) / 9) ** 2) * .9)
        return IC[3] if n < .4 else IC[2] if n < .6 else IC[1] if n < .85 else IC[0]
    cv.paint(m, f)
    cv.fill(m & ~cv.emask(16, 17, 12, 7) & np.fromfunction(lambda y, x: (x + y) % 2 == 0, (32, 32)), IC[4])
    cv.line([(8, 14), (12, 17), (11, 21)], "#ffffff"); cv.line([(19, 12), (23, 15)], "#ffffff")
    for (x, y) in ((7, 22), (26, 15), (14, 26), (27, 22)):
        cv.px(x, y, IC[3]); cv.px(x + 1, y, IC[4])
    cv.outline("#2f6f86")
    return cv


def dead_plant():
    cv = new(); shade(cv, 9)
    cv.rect(10, 26, 13, 10, CR[2]); cv.rect(10, 26, 13, 2, CR[0]); cv.rect(10, 34, 13, 2, CR[4]); cv.rect(22, 27, 1, 8, CR[3]) if False else None
    cv.rect(9, 24, 15, 3, CR[1]); cv.rect(9, 24, 15, 1, CR[0]); cv.rect(11, 31, 11, 2, OG[1]); cv.rect(11, 31, 11, 1, OG[0])
    cv.rect(11, 23, 11, 2, "#6a4a30")                     # terra seca
    st = "#8a6a4a"; stl = "#b08a5a"; sd = "#5e4630"
    cv.line([(15, 23), (13, 15), (9, 10)], st); cv.line([(17, 23), (18, 13), (22, 8)], st); cv.line([(16, 23), (16, 14)], sd)
    cv.line([(9, 10), (6, 12)], stl); cv.line([(22, 8), (26, 11)], stl); cv.line([(13, 15), (10, 17)], stl); cv.line([(18, 13), (21, 15)], stl)
    for (x, y) in ((6, 12), (26, 11), (10, 17), (21, 15), (16, 13)):
        cv.rect(x - 1, y, 3, 2, "#b08a5a"); cv.px(x, y + 2, sd)
    cv.outline(); return cv


def barrel():
    cv = new(); shade(cv, 10)
    body = cv.mask(lambda d: d.rectangle([7, 12, 24, 34], fill=255)) | cv.emask(16, 34, 9, 3)
    cv.banded(body, [BG[0], BG[1], BG[2], BG[3]], cuts=[0, 0, 0])
    def f(x, y):
        t = (x - 7) / 18
        return BG[0] if t < .22 else BG[1] if t < .5 else BG[2] if t < .78 else BG[3]
    cv.paint(body, f)
    cv.fill(cv.emask(16, 12, 9, 3), BG[1]); cv.fill(cv.emask(16, 12, 6.5, 2), BG[3]); cv.rect(14, 11, 4, 2, BG[4])
    cv.rect(7, 18, 18, 3, OG[1]); cv.rect(7, 18, 18, 1, OG[0]); cv.rect(7, 28, 18, 2, OG[1]); cv.rect(7, 28, 18, 1, OG[0])
    cv.paint(cv.mask(lambda d: d.rectangle([7, 18, 24, 20], fill=255)), lambda x, y: OG[2] if x > 19 else None)
    cv.poly([(13, 22), (19, 22), (16, 27)], DK[0]); cv.px(16, 24, OG[0])
    cv.outline(); return cv


PROPS = [
    # id, nome, função, colide, liberado de cara, onde aparece
    ("table", "Mesa", table, True, True, "acampamento, interior, base"),
    ("chair", "Cadeira", chair, False, True, "acampamento, interior, base"),
    ("crate", "Caixote", crate, True, True, "acampamento, interior da nave, base"),
    ("sign", "Placa de aviso", sign, False, True, "todas as ruínas, base"),
    ("chair_fallen", "Cadeira caída", chair_fallen, False, False, "ruínas destruídas, nave"),
    ("lab_bench", "Bancada de laboratório", lab_bench, True, False, "laboratório, estação de derretedores"),
    ("microscope", "Microscópio", microscope, True, False, "laboratório"),
    ("sample_shelf", "Estante de amostras", sample_shelf, True, False, "laboratório"),
    ("bunk", "Beliche", bunk, True, False, "acampamento, alojamento da nave"),
    ("locker", "Armário", locker, True, False, "acampamento, posto, nave"),
    ("console", "Console apagado", console, True, False, "laboratório, posto, cabine"),
    ("sample_tank", "Tanque de amostra", sample_tank, True, False, "laboratório, câmara fria"),
    ("rubble", "Entulho", rubble, True, False, "todas as ruínas"),
    ("ice_stain", "Mancha de gelo (decal)", ice_stain, False, False, "laboratório, estação, câmara fria"),
    ("dead_plant", "Vaso com planta seca", dead_plant, False, False, "acampamento, laboratório, base"),
    ("barrel", "Barril", barrel, True, False, "acampamento, posto de perfuração"),
]


def to_icon(cv: Cv) -> Cv:
    """Sprite → ícone 16×16: tira o contorno, recorta a caixa útil, reduz 2:1 por maioria de cor e refaz o contorno."""
    a = np.array(cv.im)
    ys, xs = np.nonzero((a[:, :, 3] == 255) & ~np.all(a[:, :, :3] == np.array([0x1b, 0x16, 0x30]), axis=2))
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop = a[y0:y1, x0:x1].copy()
    # tira o contorno (vira transparente) e a sombra de chão
    dark = np.all(crop[:, :, :3] == np.array([0x1b, 0x16, 0x30]), axis=2) | (crop[:, :, 3] != 255)
    crop[dark] = 0
    h, w = crop.shape[:2]
    f = max(h, w) / 14.0
    tw, th = max(1, round(w / f)), max(1, round(h / f))
    out = np.zeros((16, 16, 4), np.uint8)
    ox, oy = (16 - tw) // 2, 15 - th
    for j in range(th):
        for i in range(tw):
            ya, yb = int(j * h / th), max(int(j * h / th) + 1, int((j + 1) * h / th))
            xa, xb = int(i * w / tw), max(int(i * w / tw) + 1, int((i + 1) * w / tw))
            blk = crop[ya:yb, xa:xb].reshape(-1, 4)
            op = [tuple(int(v) for v in p) for p in blk if p[3] == 255]
            if len(op) * 2 >= len(blk):
                cnt = Counter(op)
                out[oy + j, ox + i] = max(cnt.items(), key=lambda kv: (kv[1], sum(kv[0][:3])))[0]
    ic = Cv(16, 16)
    ic.im = Image.fromarray(out)
    ic.outline()
    return ic


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    for pid, name, fn, _, _, _ in PROPS:
        cv = fn(); cv.check()
        cv.image().save(PEND / f"prop_{pid}.png")
        if pid == "ice_stain":
            # ícone do decal: o próprio decal reduzido
            ic = to_icon(cv)
        else:
            ic = to_icon(cv)
        ic.check(); ic.image().save(PEND / f"icon_prop_{pid}.png")


if __name__ == "__main__":
    main()
