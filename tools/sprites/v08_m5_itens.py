#!/usr/bin/env python3
"""v0.8 M5 · Materiais e itens · CANDIDATAS (nada daqui vai pro assets/ sem o ok do dono).

    python3 tools/sprites/v08_m5_itens.py          # 1º: sprites (pendentes/ e candidatas/) + folhas de prévia
    python3 tools/sprites/v08_m5_itens_report.py   # 2º: mock do Tab (UIMock) + index.html

Só LÊ assets/sprites/ e escreve em reports/design/v08_m5_itens/. Determinístico (sem aleatório).
Estilo dos icon_* aprovados: chapado em 2–3 faixas, luz de cima-esquerda, um brilho, contorno #1b1630 (4-vizinhos).

Saída (pendentes/ = a recomendada com o nome do contrato; candidatas/ = A e B dos que têm dúvida de leitura):
    icon_fiber, icon_hydrogel, icon_frost_resin, icon_lily_essence          16×16  materiais
    icon_backpack_t2, icon_o2_tank_t2, icon_boots, icon_lamp_bio,
    icon_fertilizer, icon_drone_t2                                          16×16  itens
    lamp_bio.png      16×32  a luminária bio no chão (mesma âncora da lamp.png: base na linha 29, centro x=8)
    drone_t2.png      64×16  drone nv.2 voando (4 quadros de 16×16, como o drone.png)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_sprites as B  # noqa: E402  (só as utilidades: Canvas, C, MT, apply_darkness; o main dele NÃO roda)
import machines_r3d as MR  # noqa: E402  (o drone esférico aprovado: drone_t2 sai da mesma cena)

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v08_m5_itens"
PEND = REP / "pendentes"
CAND = REP / "candidatas"
INK = "#1b1630"
C = B.C
MT = B.MT

# ---- paletas (fundo → brilho), tiradas dos ícones aprovados da v0.8 ------------------------------------------------
ALGA = ("#163a26", "#2f6b3a", "#4f9a3f", "#7fc94f", "#c4ec7a")          # icon_algae (fibra)
ALGA_Y = "#d8c25a"                                                          # bolhinha amarela da alga
GEL = ("#155a5a", "#1f8a86", "#3fc6b4", "#8ff0dc", "#e0fff6")            # gel hídrico: entre a folha e a gota da Folha-gota
LEAF = ("#1f6a52", "#35a06a", "#74d488", "#c8f2a8")                      # folha da Folha-gota
RES = ("#101c40", "#22407a", "#2f68b0", "#58a0e0", "#a6ecff", "#e9fbff")  # Espiral-de-geada (resina)
LILY_I = ("#3d8fb8", "#6cc6e6", "#a6ecff", "#e9fbff")                    # pétala do Lírio-de-Ilves
LILY_V = ("#4a2a8a", "#7a4cc0", "#b48cf0", "#f0e0ff")                    # miolo violeta do Lírio
GOLD, GOLD_D, GOLD_L = "#f2c46d", "#b8893a", "#fff3c4"
BIO = ("#155a5a", "#1f8a86", "#3fc6b4", "#8ff0dc", "#e0fff6", "#ffffff")  # brilho bio (frio, verde-azulado)
BIO_LIGHT = (150, 245, 215)                                                # cor da luz no mapa de luz (prévia)


class Px:
    """Grade 16×16 (ou w×h) de cores hex; contorno #1b1630 no fim, como os outros ícones."""

    def __init__(self, w=16, h=16):
        self.w, self.h = w, h
        self.c = [[None] * w for _ in range(h)]

    def px(self, x, y, col):
        x, y = int(math.floor(x)), int(math.floor(y))
        if 0 <= x < self.w and 0 <= y < self.h and col:
            self.c[y][x] = col

    def get(self, x, y):
        return self.c[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def rect(self, x, y, w, h, col):
        for j in range(h):
            for i in range(w):
                self.px(x + i, y + j, col)

    def rows(self, rows, pal, ox=0, oy=0):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch not in ". ":
                    self.px(ox + i, oy + j, pal[ch])

    def shape(self, inside, shade, ox=0, oy=0):
        """Preenche onde inside(x, y) é verdadeiro; a cor sai de shade(x, y)."""
        for y in range(self.h):
            for x in range(self.w):
                if inside(x + 0.5 - ox, y + 0.5 - oy):
                    self.px(x, y, shade(x, y))

    def blob(self, cx, cy, rx, ry, cols, hl=None):
        """Elipse chapada em 3 faixas (luz de cima-esquerda). cols = (escuro, meio, claro)."""
        def sh(x, y):
            u, v = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            k = u * 0.7 + v * 0.7
            return cols[2] if k < -0.35 else cols[0] if k > 0.45 else cols[1]
        self.shape(lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0, sh)
        if hl:
            self.px(cx - rx * 0.45, cy - ry * 0.45, hl)

    def outline(self, col=INK):
        add = [(x, y) for y in range(self.h) for x in range(self.w) if self.c[y][x] is None and
               any(self.get(x + dx, y + dy) is not None for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        for x, y in add:
            self.c[y][x] = col
        return self

    def under(self, other: "Px"):
        """Cola `other` POR BAIXO (só onde aqui está vazio)."""
        for y in range(self.h):
            for x in range(self.w):
                if self.c[y][x] is None and other.c[y][x] is not None:
                    self.c[y][x] = other.c[y][x]
        return self

    def over(self, other: "Px"):
        for y in range(self.h):
            for x in range(self.w):
                if other.c[y][x] is not None:
                    self.c[y][x] = other.c[y][x]
        return self

    def image(self):
        a = np.zeros((self.h, self.w, 4), np.uint8)
        for y in range(self.h):
            for x in range(self.w):
                if self.c[y][x]:
                    a[y, x] = C(self.c[y][x])
        return Image.fromarray(a)


def band3(cols, cx, cy, rx, ry, lo=-0.35, hi=0.45):
    def sh(x, y):
        u, v = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
        k = u * 0.7 + v * 0.7
        return cols[2] if k < lo else cols[0] if k > hi else cols[1]
    return sh


# =====================================================================================================================
# 1 · materiais
# =====================================================================================================================
def fiber_A():
    """Cone de fio: a fibra enrolada num cone de fiação (o 'rolo de fio' industrial), em voltas verde-alga com
    sombra de cilindro (claro à esquerda, escuro à direita), o tubinho creme aparecendo em cima e embaixo e a ponta
    do fio solta. Não confunde com o fio de cobre (carretel com abas)."""
    g = Px()
    d, m, l, h = ALGA[1], ALGA[2], ALGA[3], ALGA[4]
    top, bot = 3, 13

    def half(y):
        return 3.2 + (y - top) / (bot - top) * 2.9

    def inside(x, y):
        return top <= y <= bot + 1 and abs(x - 8.0) <= half(y)

    def sh(x, y):
        u = (x + 0.5 - 8.0) / half(y + 0.5)
        band = 3 if u < -0.45 else 2 if u < 0.25 else 1 if u < 0.7 else 0
        if y % 2 == 0:                                              # as voltas do fio (risca um tom abaixo)
            band = max(0, band - 1)
        return (d, m, l, h)[band]
    g.shape(inside, sh)
    tube = {"w": "#fdf8ec", "c": "#efe6d4", "s": "#d6c9b4", "S": "#a99a8c"}
    g.rows(["wcs", "wcs"], tube, ox=7, oy=1)                          # tubinho em cima
    g.rows(["wcccccccccsS"], tube, ox=2, oy=14)                      # aba de baixo
    for (x, y) in ((11, 2), (12, 1), (13, 1), (14, 2)):              # ponta solta do fio
        g.px(x, y, m)
    g.px(10, 3, m)
    g.px(5, 11, ALGA_Y)
    return g.outline()


def fiber_C():
    """Meada: a fibra em dois laços amarrados no meio com a fitinha laranja do maço de alga (rodada antiga)."""
    g = Px()
    d, m, l, h = ALGA[1], ALGA[2], ALGA[3], ALGA[4]
    for cx in (4.5, 11.5):
        def inside(x, y, cx=cx):
            r = ((x - cx) / 3.9) ** 2 + ((y - 8.5) / 5.0) ** 2
            hole = ((x - cx) / 1.3) ** 2 + ((y - 8.5) / 2.2) ** 2
            return r <= 1.0 and hole > 1.0

        def sh(x, y, cx=cx):
            u, v = (x + 0.5 - cx) / 3.9, (y + 0.5 - 8.5) / 5.0
            k = u * 0.6 + v * 0.8
            base = 2 if k < -0.3 else 0 if k > 0.45 else 1
            if (x + y) % 3 == 0:
                base = max(0, base - 1)
            return (d, m, l)[base]
        g.shape(inside, sh)
    for x, y in ((3, 4), (10, 4), (2, 6)):
        g.px(x, y, h)
    g.rect(7, 4, 2, 9, "#e2733a")
    g.rect(8, 4, 1, 9, "#a9482a")
    g.px(7, 4, "#f4a06a")
    g.rect(6, 7, 4, 3, "#e2733a")
    g.rect(9, 7, 1, 3, "#a9482a")
    g.px(6, 7, "#f4a06a")
    g.px(13, 11, ALGA_Y); g.px(3, 12, ALGA_Y)
    return g.outline()


def fiber_B():
    """Novelo: bola de fio verde-alga com as voltas em arcos claros (o fio por cima), a ponta solta caindo pela
    direita e uma bolhinha amarela da alga presa no fio."""
    g = Px()
    d, m, l, h = ALGA[1], ALGA[2], ALGA[3], ALGA[4]
    cx, cy, r = 7.0, 7.5, 5.6

    def sh(x, y):
        u, v = (x + 0.5 - cx) / r, (y + 0.5 - cy) / r
        k = u * 0.7 + v * 0.7
        lit = k < 0.3
        X, Y = x + 0.5, y + 0.5
        on = False
        if X + Y < 15.5:                                          # metade de cima-esquerda: arcos de um lado
            on = any(abs(math.hypot(X - 14.0, Y - 0.0) - R) < 0.6 for R in (6.5, 9.5, 12.5))
        else:                                                      # de baixo-direita: do outro (o fio cruza)
            on = any(abs(math.hypot(X - 0.0, Y - 1.0) - R) < 0.6 for R in (11.0, 14.0))
        if on:
            return h if k < -0.2 else l
        return m if k < 0.45 else d
    g.shape(lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r, sh)
    for (x, y) in ((12, 11), (13, 12), (13, 13), (12, 14), (11, 14), (10, 14)):   # a ponta solta
        g.px(x, y, l if y < 13 else m)
    g.px(9, 14, d)
    g.px(5, 10, ALGA_Y)
    return g.outline()


def hydrogel_A():
    """Gota de gel solta: gorda e meio achatada embaixo (gel, não água), faixas verde-azuladas, um miolo mais claro,
    duas bolhinhas presas dentro e a folhinha da Folha-gota grudada na ponta."""
    g = Px()
    def inside(x, y):
        if y >= 8.5:
            return ((x - 7.5) / 5.6) ** 2 + ((y - 9.6) / 4.6) ** 2 <= 1.0
        w = (y - 2.2) / 6.3 * 5.4                                  # ponta da gota
        return y >= 2.2 and abs(x - 7.5) <= w
    sh = band3((GEL[1], GEL[2], GEL[3]), 7.5, 9.0, 5.6, 6.0, -0.25, 0.42)
    g.shape(inside, sh)
    for (x, y) in ((6, 7), (7, 7), (6, 8), (5, 9), (6, 9), (7, 8)):  # miolo claro (gel translúcido)
        g.px(x, y, GEL[3])
    g.px(5, 7, GEL[4]); g.px(4, 9, GEL[4]); g.px(5, 6, GEL[4])
    g.px(10, 11, GEL[4]); g.px(9, 12, GEL[3])                  # bolhinhas presas no gel
    g.px(11, 9, GEL[3])
    g.rect(3, 13, 10, 1, GEL[0])                               # base achatada (escorre)
    g.px(2, 12, GEL[1]); g.px(13, 12, GEL[1])
    # folhinha da Folha-gota na ponta
    g.px(8, 2, LEAF[1]); g.px(9, 1, LEAF[2]); g.px(10, 1, LEAF[2]); g.px(10, 2, LEAF[1]); g.px(11, 1, LEAF[0])
    g.px(9, 2, LEAF[1])
    return g.outline()


def hydrogel_B():
    """Potinho de gel: pote baixo de vidro com tampa creme e faixa laranja (família das máquinas), cheio de gel
    verde-azulado com bolhas; uma folhinha da Folha-gota no rótulo."""
    g = Px()
    pal = {"w": "#fdf8ec", "c": "#efe6d4", "s": "#d6c9b4", "o": "#e2733a", "O": "#a9482a",
           "1": GEL[1], "2": GEL[2], "3": GEL[3], "4": GEL[4], "g": "#d8eef6", "G": "#a9c9d6",
           "f": LEAF[2], "F": LEAF[1]}
    g.rows([
        "................",
        "................",
        "...wwwwwwwwcs...",
        "...ooooooooOO...",
        "..gGGGGGGGGGGG..",
        "..g4433333332G..",
        "..g4333233322G..",
        "..g3332333221G..",
        "..g332fF33221G..",
        "..g33fF332221G..",
        "..g3322222211G..",
        "..g2322221211G..",
        "..g2222211111G..",
        "...G111111111...",
        "................",
        "................",
    ], pal)
    return g.outline()


def frost_resin_A():
    """Pedaço de resina: pepita gorda e redonda (estilo dos minérios "chunky"), azul da Espiral-de-geada em
    faixas, a espiral clara presa dentro, crosta de geada branca em cima e um brilho frio."""
    g = Px()
    def inside(x, y):
        return (((x - 7.0) / 6.0) ** 2 + ((y - 9.0) / 4.8) ** 2 <= 1.0 or
                ((x - 9.5) / 4.0) ** 2 + ((y - 6.5) / 4.0) ** 2 <= 1.0)
    g.shape(inside, band3((RES[1], RES[2], RES[3]), 8.0, 8.5, 6.0, 5.5, -0.3, 0.38))
    # espiral presa dentro (a planta de origem)
    cx, cy = 7.6, 9.0
    for i in range(16):
        a = math.pi * 0.9 + i * 0.52
        rr = 0.6 + i * 0.2
        g.px(cx + rr * math.cos(a), cy + rr * math.sin(a), RES[4])
    g.px(cx, cy, RES[5])
    # geada em cima (crosta branca irregular)
    for (x, y) in ((6, 4), (7, 4), (8, 3), (9, 3), (10, 3), (11, 3), (12, 4), (3, 6), (4, 5), (5, 5), (13, 5)):
        g.px(x, y, RES[5])
    for (x, y) in ((8, 2), (10, 2), (4, 4)):
        g.px(x, y, RES[4])
    g.px(9, 4, "#ffffff"); g.px(10, 4, RES[4])
    g.px(3, 8, RES[4])                                          # brilho
    return g.outline()


def frost_resin_B():
    """Gota de resina: gota grossa escorrendo (âmbar, só que gelada), azul profundo embaixo e claro em cima, com
    um capuz de geada branca em cima e a espiral clara dentro."""
    g = Px()
    def inside(x, y):
        if y >= 7.5:
            return ((x - 7.5) / 5.4) ** 2 + ((y - 9.2) / 5.0) ** 2 <= 1.0
        w = (y - 1.5) / 6.0 * 5.2
        return y >= 1.5 and abs(x - 7.5) <= w
    g.shape(inside, band3((RES[1], RES[2], RES[3]), 7.5, 9.0, 5.4, 6.2, -0.3, 0.38))
    for y in range(1, 8):                                         # capuz de geada: o topo da gota branco
        for x in range(16):
            if g.get(x, y) and y <= 4 + (1 if x in (5, 9) else 0) + (1 if x == 7 else 0):
                g.px(x, y, RES[5] if (x + y) % 3 else RES[4])
    cx, cy = 7.4, 10.0
    for i in range(14):
        a = math.pi * 1.1 + i * 0.55
        rr = 0.5 + i * 0.2
        g.px(cx + rr * math.cos(a), cy + rr * math.sin(a), RES[4])
    g.px(4, 8, RES[4]); g.px(4, 9, RES[5])
    return g.outline()


def lily_essence_A():
    """Frasco-balão: bojo redondo de vidro com a essência violeta acesa (miolo do Lírio) e um núcleo ciano (pétala),
    gargalo com anel dourado, rolha de cristal ciano e brilhinhos fora do frasco. É o único dourado+violeta do jogo."""
    g = Px()
    pal = {"g": "#d8eef6", "G": "#a9c9d6", "y": GOLD, "Y": GOLD_L, "u": GOLD_D,
           "c": LILY_I[2], "C": LILY_I[1], "D": LILY_I[0], "W": "#ffffff"}
    g.rows([
        "................",
        "......cW........",
        ".....DcCc.......",
        "......DC........",
        "......gG........",
        ".....Yyyu.......",
        "......gG........",
    ], pal, ox=1)
    def inside(x, y):
        return (x - 8.0) ** 2 + (y - 10.5) ** 2 <= 4.6 ** 2
    v = LILY_V
    def sh(x, y):
        u, w = (x + 0.5 - 8.0) / 4.6, (y + 0.5 - 10.5) / 4.6
        if w < -0.45:                                             # o ar no alto do bojo (vidro)
            return "#d8eef6" if u < 0.3 else "#a9c9d6"
        k = u * 0.6 + w * 0.8
        return v[3] if k < -0.55 else v[2] if k < -0.05 else v[1] if k < 0.55 else v[0]
    g.shape(inside, sh)
    g.px(8, 10, LILY_I[2]); g.px(7, 10, LILY_I[1]); g.px(8, 11, LILY_I[1]); g.px(9, 10, LILY_I[1])
    g.px(8, 9, LILY_I[3])                                        # núcleo ciano aceso
    g.px(5, 9, "#ffffff")                                         # reflexo do vidro
    for (x, y) in ((13, 4), (12, 3), (14, 3), (13, 2), (2, 6), (3, 13)):
        g.px(x, y, GOLD_L if (x, y) != (13, 3) else "#ffffff")
    g.px(13, 3, "#ffffff")
    return g.outline()


def lily_essence_B():
    """Frasquinho de perfume: vidro facetado em losango com a essência violeta, gargalo dourado e a rolha em forma de
    flor do Lírio (pétalas ciano, miolo violeta). Mais 'joia', menos 'laboratório'."""
    g = Px()
    pal = {"c": LILY_I[2], "C": LILY_I[1], "D": LILY_I[0], "e": LILY_I[3], "v": LILY_V[2], "V": LILY_V[1],
           "y": GOLD, "Y": GOLD_L, "u": GOLD_D}
    g.rows([
        "................",
        "......c.c.......",
        ".....ecvcD......",
        "......CVD.......",
        ".......u........",
        "......Yyu.......",
    ], pal, ox=0)
    v = LILY_V
    def inside(x, y):
        return abs(x - 7.5) / 6.2 + abs(y - 10.5) / 4.6 <= 1.0 and 6 <= y <= 15 and abs(x - 7.5) <= 5.6
    def sh(x, y):
        dx, dy = x + 0.5 - 7.5, y + 0.5 - 10.5
        if dx <= 0 and dy <= 0:
            return v[3] if dx > -2 and dy > -2 else v[2]           # faceta de cima-esquerda (a mais clara)
        if dx > 0 and dy <= 0:
            return v[2]
        if dx <= 0:
            return v[1]
        return v[0]
    g.shape(inside, sh)
    g.px(7, 10, LILY_I[2]); g.px(8, 11, LILY_I[1]); g.px(7, 11, LILY_I[3])
    g.px(5, 9, "#ffffff")
    for (x, y) in ((12, 5), (13, 4), (12, 3), (11, 4), (3, 12), (2, 7)):
        g.px(x, y, GOLD_L)
    g.px(12, 4, "#ffffff")
    return g.outline()


# =====================================================================================================================
# 2 · itens
# =====================================================================================================================
EQ = {"W": "#ffffff", "w": "#f4f6f8", "l": "#e1e5ea", "m": "#c8cdd4", "s": "#abb2bb", "d": "#8c949e", "g": "#6b717a",
      "k": "#3b3f46", "K": "#2a2d33", "o": "#e2733a", "h": "#f29a62", "r": "#a8471f",
      "c": "#59d0e6", "C": "#2b9fb8", "L": "#c8f6ff", "n": "#1f5a66",
      "y": GOLD, "Y": GOLD_L, "u": GOLD_D,
      "1": ALGA[1], "2": ALGA[2], "3": ALGA[3], "4": ALGA[4],
      "5": GEL[1], "6": GEL[2], "7": GEL[3], "8": GEL[4],
      "a": RES[2], "b": RES[3], "e": RES[4], "E": RES[1], "f": RES[5]}


def backpack_t2():
    """Mochila T2: a mesma mochila em domo, mais larga e reforçada. Rolo de fibra verde amarrado em cima (no lugar
    da alça), aba com a faixa de fibra trançada, fivela dourada (nv.2), alças de ombro e bolsos laterais em fibra."""
    g = Px()
    g.rows([
        "................",
        "...y34333334y...",
        "..23y2222222y1..",
        "...1y1111111y...",
        "...wWwwwwwwwlm..",
        "..wwwwwwcCwwwlm.",
        ".1wwwwwwwwwwwwm1",
        ".1323232323232s1",
        ".12323yYu23232s1",
        ".1wwmmmyummmlm1.",
        "21wwdmmmmmmmdm12",
        "21wlohooooooos12",
        "21wlmmmmmmmmss12",
        "21wldssssssdms12",
        ".1.lddddddddm.1.",
        "................",
    ], EQ)
    return g.outline()


def o2_tank_t2():
    """Tanque de O₂ nv.2: o par de cilindros do tanque nv.1, mais gordos, com anéis e válvulas DOURADOS (nv.2), a
    faixa no verde-azulado do gel e a cinta de fibra verde trançada; manômetro no meio."""
    g = Px()
    g.rows([
        "..yyy....yyy....",
        "..uYu....uYu....",
        ".Ywwwwy.Ywwwwy..",
        ".wWwwms.wWwwms..",
        ".wwwwms.wwwwms..",
        ".yyyyyu.yyyyyu..",
        ".778765.778765..",
        ".667655.667655..",
        ".wwwwms.wwwwms..",
        ".2323232323232..",
        ".1212kkkk21212..",
        ".wwwkLckkwwwms..",
        ".wwwkkkkkwwwms..",
        ".yyyyyu.yyyyyu..",
        ".sssssd.sssssd..",
        "................",
    ], EQ)
    return g.outline()


BOOT = [
    "3232......",
    "2121......",
    "wWwm......",
    "wwwm......",
    "ooor......",
    "wwwm......",
    "wwwmm.....",
    "wwwwwmm...",
    "wwwwwwwmm.",
    "wwwwwwwwyu",
    "eeeeeeeeee",
    "aEaEaEaEaE",
]


def boots():
    """Botas de tração: par de botas do traje de perfil (a de trás mais escura e deslocada), cano branco com faixa
    laranja, punho de fibra verde, biqueira dourada e sola grossa de resina azul com cravos (a tração)."""
    back = Px()
    dark = dict(EQ, w="#c8cdd4", W="#e1e5ea", m="#8c949e", o="#a8471f", r="#6e2a1c", **{"3": ALGA[2], "2": ALGA[1],
                "1": ALGA[0]}, y=GOLD_D, u="#6e4a1e", e=RES[2], a=RES[1], E=RES[0])
    back.rows(BOOT, dark, ox=5, oy=1)
    back.outline()
    front = Px()
    front.rows(BOOT, EQ, ox=1, oy=3)
    front.outline()
    return back.over(front)


def lamp_bio_icon():
    """Ícone da Luminária bio: redoma de vidro com um pedaço de resina aceso (frio, verde-azulado) e a espiral dentro,
    tampa escura, poste curto embrulhado em fibra verde e sapata creme. Sem LED, sem fio: ela brilha sozinha."""
    g = Px()
    pal = dict(EQ, A=BIO[0], B=BIO[1], D=BIO[2], F=BIO[3], H=BIO[4], X=BIO[5], q="#d8eef6", Q="#a9c9d6")
    g.rows([
        "................",
        "......kkkk......",
        ".....gkkkkK.....",
        "....qHFFFDDQ....",
        "....HXFFDFDQ....",
        "....FFFDDFDB....",
        "....FDFFFDDB....",
        "....qDDDDBBQ....",
        "....qBBBBBAQ....",
        ".....gkkkkK.....",
        "......3121......",
        "......2131......",
        "......3121......",
        "...wwwwwwwwwl...",
        "...1212121212...",
        "...sssssssssd...",
    ], pal)
    return g.outline()


def fertilizer():
    """Adubo: saquinho creme amarrado com a fitinha laranja, a boca aberta com a alga e bolhas de gel saindo, e no
    rótulo a folha verde com uma gota verde-azulada (alga + gel)."""
    g = Px()
    pal = {"w": "#fdf8ec", "c": "#efe6d4", "s": "#d6c9b4", "S": "#a99a8c", "o": "#e2733a", "O": "#a9482a",
           "L": "#f4a06a", "1": ALGA[1], "2": ALGA[2], "3": ALGA[3], "4": ALGA[4], "6": GEL[2], "7": GEL[3],
           "8": GEL[4], "f": LEAF[2], "F": LEAF[0], "G": LEAF[1]}
    g.rows([
        "................",
        "....3...4.......",
        "...32.7.3.3.....",
        "....2382721.....",
        "....wcccccs.....",
        ".....LooOO......",
        "....wcccccsS....",
        "...wcccccccsS...",
        "..wccffccccssS..",
        "..wcfGfF67cssS..",
        "..wcfGF678cssS..",
        "..wccFF667csSS..",
        "..wcccccccssSS..",
        "..wcccccccsSSS..",
        "...ssssssSSSS...",
        "................",
    ], pal)
    return g.outline()


def drone_t2_icon():
    """Ícone do Drone nv.2: o drone do nv.1 (corpo branco, visor ciano) com faixa DOURADA (nv.2), braços de fibra verde,
    hélices de resina azul (mais leves) e uma garra de carga embaixo com o caixotinho (carrega mais)."""
    rig = Px()
    for (rx, ry) in ((2, 3), (13, 3), (2, 10), (13, 10)):
        x, y = 7 + (rx > 7), 6 + (ry > 6)
        while (x, y) != (rx, ry):                                     # braço de fibra
            rig.px(x, y, ALGA[1])
            x += (rx > x) - (rx < x)
            y += (ry > y) - (ry < y)
        rig.rect(rx - 2, ry - 1, 5, 1, RES[4])                         # hélice de resina
        rig.px(rx - 2, ry - 1, RES[3]); rig.px(rx + 2, ry - 1, RES[3])
        rig.px(rx, ry, MT["kk"])
    rig.rect(6, 12, 4, 3, "#e2733a")                                   # caixote de carga
    rig.rect(6, 12, 4, 1, "#f29a62")
    rig.rect(9, 13, 1, 2, "#a8471f")
    rig.px(7, 13, GOLD)
    rig.outline()
    body = Px()
    body.rect(4, 4, 8, 8, MT["w"])
    body.rect(4, 10, 8, 2, MT["m"])
    body.rect(10, 5, 2, 7, MT["s"])
    body.rect(4, 7, 8, 2, GOLD)
    body.rect(4, 7, 8, 1, GOLD_L)
    body.rect(10, 8, 2, 1, GOLD_D)
    body.rect(6, 4, 4, 2, "#2b7f99")
    body.rect(6, 4, 2, 1, "#59d0e6")
    body.px(6, 4, "#d8fbff")
    body.px(10, 10, MT["led"])
    for x, y in ((4, 4), (11, 4), (4, 11), (11, 11)):
        body.c[y][x] = None
    body.outline()
    return rig.over(body)


# =====================================================================================================================
# 3 · mundo
# =====================================================================================================================
LAMP_BIO_GLOW = (8, 7)       # centro do brilho no lamp_bio.png (a lamp.png tem (8, 6))


def lamp_bio_world():
    """Luminária bio 16×32 (mesma âncora da lamp.png: base na linha 29, centro x=8). Família da luminária: sapata,
    poste e cabeça; mas a cabeça é uma REDOMA de vidro com o pedaço de resina de geada aceso dentro (frio,
    verde-azulado, com a espiral), o poste é embrulhado em fibra verde e não tem LED nem fio: brilha sozinha."""
    cv = B.Canvas(16, 32)
    cv.ellipse(8, 29.5, 6.5, 2, B.SHADOW)
    g = Px(16, 32)
    pal = dict(EQ, A=BIO[0], B=BIO[1], D=BIO[2], F=BIO[3], H=BIO[4], X=BIO[5], q="#d8eef6", Q="#a9c9d6")
    g.rows([
        "................",   # 0
        ".......kk.......",   # 1  argola
        "......k..k......",   # 2
        ".....gkkkkK.....",   # 3  tampa
        "....qqHFFFQQ....",   # 4  redoma
        "....qHXFFDFQ....",   # 5
        "....HXFFDFDB....",   # 6
        "....FFDFFFDB....",   # 7
        "....FDFHDFDB....",   # 8
        "....qFDDFDBQ....",   # 9
        "....qBDDDBAQ....",   # 10
        "....gkkkkkkK....",   # 11 aro de baixo
        ".....kkkkkK.....",   # 12 colar
        "......3121......",   # 13 poste embrulhado em fibra
        "......2131......",   # 14
        "......mmms......",   # 15
        "......3121......",   # 16
        "......2131......",   # 17
        "......mmms......",   # 18
        "......3121......",   # 19
        "......2131......",   # 20
        "......mmms......",   # 21
        "......wmms......",   # 22
        ".....wwmmsd.....",   # 23
        "...wwwwwwwwwl...",   # 24 sapata: topo
        "...lllllllllm...",   # 25
        "...1212121212...",   # 26 faixa de fibra
        "...sssssssssg...",   # 27
        "...dddddddddg...",   # 28
    ], pal)
    g.outline()
    img = cv.image()
    img.alpha_composite(g.image())
    return img


P_RESIN = MR.Pal(["#a6ecff", "#58a0e0", "#2f68b0", "#22407a", "#101c40"])      # resina (Espiral-de-geada), 1 tom abaixo
P_GOLD2 = MR.Pal(["#fff3c4", "#f2c46d", "#d9a64e", "#b8893a", "#6e4a1e"])      # dourado nv.2, 1 tom abaixo (lê no cinto)


def drone_t2_frame(f: int):
    """Drone nv.2 16×16, o MESMO drone esférico do drone.png (r3d, machines_r3d.drone) com: cinto DOURADO no equador
    (nv.2, como a broca nv.2), aletas de resina azul no lugar das de chapa (mais leve) e DOIS propulsores ciano (voa mais rápido). Olho vermelho igual."""
    sc = MR.Scene(16, 16, ground=9.0)

    def shell(N):
        out = np.zeros(len(N), int)
        out[(abs(N[:, 0]) < 0.22) & (N[:, 2] > 0.5)] = 1      # faixa de painel por cima
        out[abs(N[:, 2]) < 0.13] = 2                          # cinto dourado no equador
        out[(N[:, 2] < -0.55)] = 3                            # fundo escuro (onde ficam os propulsores)
        return out
    sc.sphere((0, 0.5, 0.6), 5.0, MR.P_BEIGE, paint=shell, extra=(MR.P_SLATE, P_GOLD2, MR.P_SLATE))
    for sx in (-1, 1):                                        # aletas de resina azul + ponta bege
        sc.obox((sx * 5.6, 0.8, 0.6), (1.0, 2.2, 1.7), P_RESIN)
        sc.obox((sx * 6.5, 0.8, 0.6), (0.4, 2.6, 0.7), MR.P_BEIGE)
    sc.sphere((0, -3.7, 2.2), 2.3, MR.P_SLATE)
    sc.sphere((0, -4.8, 2.2), 1.6, MR.P_EYE[f])
    sc.dot(-0.7, -6.2, 3.1, "#ffffff", always=True)
    for bx in (-1.9, 1.9):                                    # dois bocais
        sc.cyl(bx, 0.5, 1.2, -4.8, -4.0, MR.P_SLATE, cap=False)
    cv = MR.render(sc)
    flames = [[(5, 15), (10, 15)], [(5, 15), (10, 15), (10, 16)], [(5, 15), (10, 15), (5, 16)], [(5, 15), (10, 15)]][f]
    for (x, y) in flames:
        if 0 <= y < 16 and not cv.solid(x, y):
            cv.px(x, y, MR.CYAN_L if y == 15 else MR.CYAN)
    for (x, y, on) in ((3, 2, f % 2 == 0), (12, 2, f % 2 == 1)):
        cv.px(x, y, MR.ALERT if on else "#7a2a24")
    return Image.fromarray(cv.a)


def drone_t2_sheet():
    img = Image.new("RGBA", (64, 16), (0, 0, 0, 0))
    for f in range(4):
        img.alpha_composite(drone_t2_frame(f), (f * 16, 0))
    return img


# =====================================================================================================================
# saída
# =====================================================================================================================
CANDS = {   # nome do contrato: {candidata: função}; a 1ª chave é a recomendada (vai pra pendentes/)
    "icon_fiber": {"A": fiber_A, "B": fiber_B, "C": fiber_C},
    "icon_hydrogel": {"A": hydrogel_A, "B": hydrogel_B},
    "icon_frost_resin": {"A": frost_resin_A, "B": frost_resin_B},
    "icon_lily_essence": {"A": lily_essence_A, "B": lily_essence_B},
    "icon_drone_t2": {"A": drone_t2_icon, "B": lambda: drone_t2_frame(0)},
}
RECOMMEND = {"icon_fiber": "A", "icon_hydrogel": "A", "icon_frost_resin": "A", "icon_lily_essence": "A",
             "icon_drone_t2": "A"}
ITEMS = {"icon_backpack_t2": backpack_t2, "icon_o2_tank_t2": o2_tank_t2, "icon_boots": boots,
         "icon_lamp_bio": lamp_bio_icon, "icon_fertilizer": fertilizer}
CONTRACT = {**{k: (16, 16) for k in CANDS}, **{k: (16, 16) for k in ITEMS}, "lamp_bio": (16, 32), "drone_t2": (64, 16)}


def _img(x):
    return x if isinstance(x, Image.Image) else x.image()


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    CAND.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, cands in CANDS.items():
        for k, fn in cands.items():
            im = _img(fn())
            im.save(CAND / f"{name}_{k}.png")
            if k == RECOMMEND[name]:
                out[name] = im
    for name, fn in ITEMS.items():
        out[name] = fn().image()
    out["lamp_bio"] = lamp_bio_world()
    out["drone_t2"] = drone_t2_sheet()
    for name, im in out.items():
        im.save(PEND / f"{name}.png")
    return out


def check():
    ok = True
    got = sorted(p.stem for p in PEND.glob("*.png"))
    if got != sorted(CONTRACT):
        print("arquivos diferentes do contrato:", set(got) ^ set(CONTRACT))
        ok = False
    for name, size in CONTRACT.items():
        im = Image.open(PEND / f"{name}.png")
        a = np.array(im.convert("RGBA"))[:, :, 3]
        alphas = set(np.unique(a).tolist())
        if im.size != size:
            print("tamanho errado:", name, im.size, size)
            ok = False
        if not alphas <= {0, 255, B.SHADOW[3]}:
            print("alpha fora do padrão:", name, alphas)
            ok = False
    print("contrato ok" if ok else "contrato COM PROBLEMA")
    return ok


# ---- folhas de prévia (pra eu olhar e pro report) ------------------------------------------------------------------
def zoom(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def checker(w, h, s=8):
    a = np.zeros((h, w, 4), np.uint8)
    a[:, :] = C("#2a211d")
    yy, xx = np.mgrid[0:h, 0:w]
    a[((xx // s) + (yy // s)) % 2 == 0] = C("#3a2e28")
    return Image.fromarray(a)


def sheet(names, k=4, pad=8, src=None):
    ims = [Image.open((src or {}).get(n, SPR / f"{n}.png")).convert("RGBA") if not isinstance(n, Image.Image) else n
           for n in names]
    W = sum(im.width * k + pad for im in ims) + pad
    H = max(im.height for im in ims) * k + 2 * pad
    out = checker(W, H)
    x = pad
    for im in ims:
        out.alpha_composite(zoom(im, k), (x, pad))
        x += im.width * k + pad
    return out


if __name__ == "__main__":
    build()
    check()
