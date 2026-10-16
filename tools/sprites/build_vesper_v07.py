#!/usr/bin/env python3
"""Hesper v0.7 M4 · interior da VÉSPER-7. Gera os sprites pendentes e a montagem do report.

Saída: reports/design/v07_m4/pendentes/*.png  (o dono aprova antes de ir pra assets/sprites/)
       reports/design/v07_m4/*.png            (montagens e ampliações pro report)

    hull_wall_top.png               64×96   atlas A2 (igual ao base_wall_top: minitiles 16×16, game/autotile.py)
    hull_wall_face.png              128×24  4 peças 32×24, índice = W + 2·E (igual ao base_wall_face)
    hull_floor_0..3.png             32×32
    vesper_hatch.png                32×32
    vesper_container_broken.png     40×44   (mesmo pé do container_sealed: centro de baixo do tile)
    vesper_power_panel.png          32×24   face de parede (blit em (x, y+8))
    vesper_jammed_door.png          32×24   face de parede, leitor de crachá em volta de (24, 12)
    vesper_emergency_light.png      32×24   face de parede

Determinístico (sem aleatório; "ruído" vem de hash de posição). Não toca no build_sprites.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from v05_m2_base import _nearest_open, top_tile_mask  # noqa: E402  (máscara + distância até a borda)

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v07_m4"
PEND = REP / "pendentes"
T, FACE_H = 32, 24
OUT = "#1b1630"

# paleta da VÉSPER-7: ardósia azulada (a mesma do destroço), ferrugem e laranja desbotado
S = dict(hl="#c4c8dc", lip="#a8adc6", cap="#7f84a3", cap_d="#5d6280", plate="#474b66", plate_d="#3a3d56",
         seam="#2a2c42", rivet="#9096b4", panel="#6a6f90", panel_l="#8389a9", panel_d="#575c7a",
         low="#4a4e6b", low2="#3d405a", plinth="#32344b", rust="#6b5448", rust_d="#52403a",
         orange="#c8683a", orange_d="#8c4a30", ice="#cfeaf6", ice_d="#8fc3dc", yellow="#ffd23a", yellow_d="#c99a1c",
         red="#e0453a", red_d="#8e2a30", red_l="#ff8a6a", screen="#14111f", screen_l="#242038")


def rgb(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


def hsh(x, y, salt=0):
    """Ruído determinístico 0..1 por posição."""
    n = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


class Img:
    """Imagem RGBA com helpers sem antialias."""

    def __init__(self, w, h):
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.w, self.h = w, h

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.im.putpixel((x, y), rgb(c) if isinstance(c, str) else c)

    def get(self, x, y):
        return self.im.getpixel((x, y))

    def rect(self, x0, y0, x1, y1, c):
        self.d.rectangle([x0, y0, x1, y1], fill=rgb(c))

    def poly(self, pts, c):
        self.d.polygon(pts, fill=rgb(c))

    def line(self, x0, y0, x1, y1, c):
        self.d.line([x0, y0, x1, y1], fill=rgb(c))

    def paste(self, other, x, y):
        self.im.alpha_composite(other.im if isinstance(other, Img) else other, (x, y))

    def save(self, path):
        self.im.save(path)


# ---------------------------------------------------------------------------------------------------------------------
# Topo da parede: chapa ardósia com rebites e uma emenda horizontal (nunca vertical). A aba clara fica no sul.
# ---------------------------------------------------------------------------------------------------------------------
def top_paint(mask):
    H, W = mask.shape
    m, dx, dy = _nearest_open(mask)
    out = np.zeros((H, W, 4), np.uint8)
    for y in range(H):
        for x in range(W):
            if not mask[y, x]:
                continue
            d, ex, ey = m[y, x], dx[y, x], dy[y, x]
            south = ey > 0 and ex == 0
            light = ey < 0 or ex < 0
            ax, ay = x % 16, y % 16
            if d == 0:
                c = S["lip"] if south else OUT
            elif d == 1:
                c = S["hl"] if light else (S["cap_d"] if south else S["plate_d"])
            elif d in (2, 3):
                c = S["cap"] if light else S["cap_d"]
            elif d == 4:
                c = S["seam"]
            else:
                c = S["plate"]
                if ay == 8:
                    c = S["seam"]                                   # emenda horizontal de chapa
                elif ay == 9:
                    c = S["panel_d"] if ax % 2 == 0 else S["cap_d"]
                elif (ax, ay) in ((3, 4), (12, 4), (3, 13), (12, 13)):
                    c = S["rivet"]                                  # rebites
                elif (ax, ay) in ((4, 4), (13, 4), (4, 13), (13, 13)):
                    c = S["seam"]                                   # sombra do rebite
                elif hsh(x, y, 5) > 0.93:
                    c = S["plate_d"]                                # pontinhos de desgaste
            out[y, x] = rgb(c)
    return out


def wall_top_atlas():
    atlas = np.zeros((96, 64, 4), np.uint8)
    iso = top_paint(top_tile_mask([[0, 0, 0], [0, 1, 0], [0, 0, 0]]))
    atlas[0:32, 0:32] = iso[32:64, 32:64]
    plus = top_paint(top_tile_mask([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    atlas[0:32, 32:64] = plus[32:64, 32:64]
    mk = np.zeros((128, 128), bool)
    mk[32:96, 32:96] = True
    blk = top_paint(mk)
    atlas[32:96, 0:64] = blk[32:96, 32:96]
    return Image.fromarray(atlas, "RGBA")


# ---------------------------------------------------------------------------------------------------------------------
# Face da parede (32×24): casco. Faixas horizontais, uma emenda, faixa laranja desbotada, rebites. Sem junta vertical.
# ---------------------------------------------------------------------------------------------------------------------
FACE_ROWS = (["lip", "hl"] + ["panel"] * 7 + ["panel_l", "seam", "rivet_row"] + ["low"] * 4 + ["orange", "orange_d"]
             + ["low2"] * 3 + ["plinth"] * 2 + ["OUT"])
assert len(FACE_ROWS) == FACE_H


def face_base(left_open=True, right_open=True, w=T):
    f = Img(w, FACE_H)
    for y, k in enumerate(FACE_ROWS):
        for x in range(w):
            if k == "OUT":
                c = OUT
            elif k == "rivet_row":
                c = S["rivet"] if x % 8 == 3 else S["panel_d"]
            elif k == "panel_l":
                c = S["panel_l"]
            elif k in ("lip", "hl", "panel", "seam", "orange", "orange_d", "low", "low2", "plinth"):
                c = S[k if k != "lip" else "lip"]
                if k == "panel" and hsh(x, y, 9) > 0.965:
                    c = S["panel_d"]
            else:
                c = S["panel"]
            if k == "orange" and (x // 4) % 5 == 4:
                c = S["low"]                                         # tinta descascada
            if k == "orange_d" and (x // 4) % 5 == 4:
                c = S["low2"]
            f.px(x, y, c)
    if left_open:
        for y in range(FACE_H):
            f.px(0, y, OUT if FACE_ROWS[y] != "OUT" else OUT)
            if FACE_ROWS[y] not in ("OUT",):
                f.px(1, y, S["hl"] if y < 12 else S["panel_l"])
    if right_open:
        for y in range(FACE_H):
            f.px(w - 1, y, OUT)
            if FACE_ROWS[y] != "OUT":
                f.px(w - 2, y, S["low2"])
    return f


def wall_face_strip():
    out = Img(4 * T, FACE_H)
    for idx in range(4):
        out.paste(face_base(not (idx & 1), not (idx >> 1)), idx * T, 0)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Chão de chapa 32×32: grade de 16 px com emenda e rebites nos cantos (casa entre tiles). 4 variações.
# ---------------------------------------------------------------------------------------------------------------------
FL = dict(base="#4d5170", light="#5a5f80", dark="#41445f", seam="#2c2e45", seam_l="#666b8b", rivet="#8a90ae",
          stain="#3a3a4e", rust="#5a4a48", oil="#2f2f42")


def hull_floor(v):
    f = Img(T, T)
    for y in range(T):
        for x in range(T):
            ax, ay = x % 16, y % 16
            c = FL["base"]
            if hsh(x, y, 1 + v) > 0.9:
                c = FL["light"]
            elif hsh(x, y, 11 + v) > 0.88:
                c = FL["dark"]
            if ax == 0 or ay == 0:
                c = FL["seam"]
            elif ax == 1 or ay == 1:
                c = FL["seam_l"] if (ax == 1 and ay > 1) or (ay == 1 and ax > 1) else FL["light"]
            f.px(x, y, c)
    for cx in (0, 16):
        for cy in (0, 16):
            for dx, dy in ((4, 4), (11, 4), (4, 11), (11, 11)):
                if (dx, dy) == (4, 4) or (dx, dy) == (11, 11):
                    f.px(cx + dx, cy + dy, FL["rivet"])
                    f.px(cx + dx + 1, cy + dy + 1, FL["seam"])
    if v == 1:                                                         # manchas de óleo e ferrugem
        for (cx, cy, r, c) in ((9, 20, 5, FL["oil"]), (24, 8, 3, FL["rust"]), (20, 24, 2, FL["rust"])):
            for y in range(T):
                for x in range(T):
                    if (x - cx) ** 2 + ((y - cy) * 1.4) ** 2 <= r * r and hsh(x, y, 4) > 0.04:
                        f.px(x, y, c)
    if v == 2:                                                         # grelha de ventilação
        for y in range(18, 29):
            for x in range(6, 27):
                f.px(x, y, FL["seam"])
        for y in range(19, 28, 2):
            for x in range(7, 26):
                f.px(x, y, "#1a1828")
        for x in range(6, 27):
            f.px(x, 17, FL["seam_l"])
    if v == 3:                                                         # risco de gelo entrando pela fresta
        pts = [(4, 26), (9, 22), (13, 21), (17, 16), (22, 14), (27, 9)]
        for (a, b), (c2, d2) in zip(pts, pts[1:]):
            for i in range(0, 11):
                x = round(a + (c2 - a) * i / 10)
                y = round(b + (d2 - b) * i / 10)
                f.px(x, y, S["ice"])
                f.px(x, y + 1, S["ice_d"])
                if hsh(x, y, 7) > 0.5:
                    f.px(x - 1, y + 2, S["ice_d"])
        for x, y in ((6, 20), (15, 25), (24, 18), (11, 15), (26, 12)):
            f.px(x, y, S["ice"])
    return f


# ---------------------------------------------------------------------------------------------------------------------
# Escotilha do porão (32×32): chapa com moldura, rampa pra cima com degraus e a luz do dia vazando pela fresta.
# ---------------------------------------------------------------------------------------------------------------------
def hatch():
    f = hull_floor(0)
    day, day_l, day_d = "#fff0c0", "#ffffe8", "#e8c878"
    f.rect(3, 3, 28, 28, OUT)
    f.rect(4, 4, 27, 27, S["panel_d"])
    f.rect(4, 4, 27, 5, S["panel"])                              # aro de cima
    # a fresta de luz no alto (porta entreaberta) e o clarão escorrendo pelos degraus
    f.rect(6, 6, 25, 9, OUT)
    f.rect(7, 7, 24, 8, day)
    f.rect(9, 7, 20, 7, day_l)
    for i, y in enumerate((10, 14, 18)):
        f.rect(6, y, 25, y + 1, S["panel"] if i else S["panel_l"])   # degraus (nariz claro)
        f.rect(6, y + 2, 25, y + 3, S["low"])
        f.rect(6, y + 3, 25, y + 3, S["low2"])
    # luz pingando nos 2 primeiros degraus (xadrez fino = degradê sem antialias)
    for x in range(7, 25):
        f.px(x, 10, day_d if x % 2 else day)
        if x % 2 == 0:
            f.px(x, 11, day_d)
    for x in range(10, 22):
        if x % 2 == 0:
            f.px(x, 14, day_d)
    f.rect(6, 22, 25, 26, S["low2"])
    # seta laranja "sobe" no último degrau
    for i in range(4):
        f.px(15 - i, 24 - 0 + 0 + (0), S["orange"]) if False else None
    chev = [(16, 22), (15, 23), (17, 23), (14, 24), (18, 24), (13, 25), (19, 25)]
    for x, y in chev:
        f.px(x, y, S["orange"])
    # cantos aparafusados
    for x, y in ((5, 5), (26, 5), (5, 26), (26, 26)):
        f.px(x, y, S["rivet"])
    # a luz vaza pra fora da moldura (chão iluminado de leve acima da fresta)
    for x in range(8, 24):
        if x % 2 == 0:
            f.px(x, 2, "#9a96a4")
    return f


# ---------------------------------------------------------------------------------------------------------------------
# Contêiner de gelo arrombado por dentro (40×44). Pé: centro de baixo (como o container_sealed, que ocupa y 13..42).
# Corpo azul (a família do lacrado), tampa estourada pra cima/fora, chapas dobradas de dentro pra fora, gelo escorrido.
# ---------------------------------------------------------------------------------------------------------------------
B = dict(b="#0a74de", bl="#2f93f4", bd="#0544a8", bm="#055ec8", hl="#d4ecff", steel="#a9b0be", steel_d="#6e7588",
         inner="#0d0a1a", inner_l="#1b2a44", frost="#bfe4f4")


def container_broken():
    f = Img(40, 44)
    # sombra de chão (nível fixo)
    sh = Image.new("RGBA", (40, 44), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([1, 36, 38, 43], fill=(27, 22, 48, 90))
    f.paste(sh, 0, 0)
    # poça de gelo derretido escorrida pela frente (azul-claro chapado, sem água "líquida" brilhando demais)
    f.poly([(6, 38), (12, 36), (20, 37), (30, 36), (36, 38), (34, 42), (24, 43), (12, 43), (5, 41)], OUT)
    f.poly([(7, 39), (13, 37), (20, 38), (30, 37), (35, 39), (33, 41), (24, 42), (12, 42), (6, 40)], S["ice_d"])
    f.poly([(10, 39), (17, 38), (24, 39), (30, 38), (31, 40), (22, 41), (12, 41)], S["ice"])
    # corpo (parte de baixo) 0..39 x 24..40
    f.rect(1, 24, 38, 39, OUT)
    f.rect(2, 25, 37, 38, B["b"])
    f.rect(2, 25, 37, 27, B["bl"])
    f.rect(2, 36, 37, 38, B["bd"])
    f.rect(2, 33, 37, 35, B["bm"])
    f.rect(3, 26, 36, 26, B["hl"])
    # cinta de aço da frente, torta
    f.rect(2, 30, 37, 31, B["steel"])
    f.rect(2, 31, 37, 31, B["steel_d"])
    # fechadura arrancada: buraco com bordas dobradas pra fora
    f.rect(17, 28, 23, 34, OUT)
    f.rect(18, 29, 22, 33, B["inner"])
    f.px(17, 28, B["steel"]); f.px(23, 28, B["steel"]); f.px(16, 34, B["steel_d"]); f.px(24, 34, B["steel_d"])
    # boca aberta no topo: interior escuro com gelo/geada nas paredes
    f.poly([(3, 24), (36, 24), (37, 18), (33, 14), (6, 14), (2, 18)], OUT)
    f.poly([(4, 23), (35, 23), (36, 19), (32, 15), (7, 15), (3, 19)], B["inner"])
    f.rect(5, 17, 34, 18, B["inner_l"])
    for x in range(6, 34):
        if hsh(x, 3, 2) > 0.45:
            f.px(x, 16, B["frost"])
    for x in (8, 12, 17, 23, 29):
        f.px(x, 20, B["inner_l"]); f.px(x + 1, 21, B["inner_l"])
    # chapas dobradas de dentro pra fora (pétalas) nas bordas da boca, bem gordinhas
    f.poly([(1, 24), (3, 14), (7, 17), (8, 24)], OUT)                  # esquerda
    f.poly([(2, 23), (4, 16), (6, 18), (7, 23)], B["bl"])
    f.poly([(2, 23), (4, 16), (4, 18), (3, 23)], B["b"])
    f.poly([(38, 24), (37, 15), (32, 18), (31, 24)], OUT)              # direita
    f.poly([(37, 23), (36, 17), (33, 19), (32, 23)], B["b"])
    f.poly([(8, 25), (14, 21), (19, 23), (24, 21), (30, 25)], OUT)     # frente da boca: lábio rasgado
    f.poly([(9, 24), (14, 22), (19, 24), (24, 22), (29, 24)], B["bl"])
    f.line(10, 24, 28, 24, B["hl"])
    # tampa: estourada, aberta pra cima e torta pra trás/esquerda (3/4: aparece o lado de baixo, enrugado)
    f.poly([(5, 14), (3, 8), (9, 4), (33, 0), (38, 3), (37, 11), (34, 14)], OUT)
    f.poly([(6, 13), (5, 8), (10, 5), (33, 1), (37, 4), (36, 10), (33, 13)], B["bd"])
    f.poly([(8, 12), (7, 8), (11, 6), (32, 2), (35, 5), (34, 9), (31, 12)], B["bm"])
    f.line(13, 6, 33, 3, B["b"])
    f.line(12, 7, 34, 4, B["b"])
    f.line(8, 10, 33, 7, B["bd"])
    f.line(9, 12, 32, 11, B["bd"])
    # amassado/rasgo da tampa e uma dobradiça solta
    f.poly([(15, 9), (21, 7), (24, 10), (19, 12), (16, 11)], OUT)
    f.poly([(16, 10), (21, 8), (22, 10), (19, 11)], B["inner_l"])
    f.rect(1, 4, 4, 6, OUT); f.rect(2, 5, 3, 5, B["steel"])            # dobradiça quebrada saltando
    f.px(0, 3, OUT); f.px(0, 4, OUT)
    # gelo derretido escorrendo da boca pela frente (3 fios e gotas)
    for x0, ln in ((13, 9), (21, 12), (28, 7)):
        for y in range(24, 24 + ln):
            wob = 1 if (y // 3) % 2 else 0
            f.px(x0 + wob, y, S["ice"])
            f.px(x0 + wob + 1, y, S["ice_d"])
        f.px(x0 + 1, 24 + ln, S["ice"])
    f.px(33, 31, S["ice"]); f.px(6, 33, S["ice"])
    # fragmento de gelo caído
    f.rect(31, 38, 34, 40, OUT)
    f.rect(32, 38, 33, 39, S["ice"])
    f.px(33, 39, S["ice_d"])
    return f


# ---------------------------------------------------------------------------------------------------------------------
# Peças de face (32×24)
# ---------------------------------------------------------------------------------------------------------------------
def power_panel():
    f = face_base(False, False)
    # moldura do painel (placa com cantos aparafusados)
    f.rect(2, 2, 29, 20, OUT)
    f.rect(3, 3, 28, 19, S["panel_d"])
    f.rect(3, 3, 28, 3, S["panel_l"])
    for x, y in ((4, 4), (27, 4), (4, 18), (27, 18)):
        f.px(x, y, S["rivet"])
    # tela apagada (vidro escuro com reflexo na diagonal)
    f.rect(5, 6, 17, 13, OUT)
    f.rect(6, 7, 16, 12, S["screen"])
    for i in range(4):
        f.px(8 + i, 11 - i, S["screen_l"])
        f.px(11 + i, 11 - i, S["screen_l"]) if i < 3 else None
    # botões mortos + LED apagado
    for x in (6, 9, 12):
        f.rect(x, 15, x + 1, 16, S["panel"]); f.px(x, 16, S["seam"])
    f.rect(15, 15, 16, 16, "#5a2630")
    # encaixe VAZIO da bateria: cavidade escura com a silhueta (corpo + polo) marcada em traço claro
    f.rect(19, 4, 27, 18, OUT)
    f.rect(20, 5, 26, 17, S["screen"])
    # silhueta: polo em cima (22..24, 6) e corpo 5×9
    sil = S["cap"]
    for x in range(22, 25):
        f.px(x, 6, sil)
    for x in range(21, 26):
        f.px(x, 8, sil); f.px(x, 16, sil)
    for y in range(8, 17):
        f.px(21, y, sil); f.px(25, y, sil)
    f.px(21, 7, S["screen"]); f.px(25, 7, S["screen"])
    f.px(21, 7, S["screen"])
    for x in (22, 24):                                              # contatos
        f.px(x, 17, S["yellow_d"])
    f.px(23, 12, S["screen_l"]); f.px(23, 11, S["screen_l"]); f.px(23, 13, S["screen_l"])   # símbolo "+" fraco
    f.px(22, 12, S["screen_l"]); f.px(24, 12, S["screen_l"])
    return f


def badge_reader(f, cx=24, cy=12):
    """Leitor de crachá (placa 10×18 em volta de (24, 12)): cordão em laço + crachá com foto, amarelo."""
    x0, y0 = cx - 5, cy - 9
    f.rect(x0, y0, x0 + 9, y0 + 17, OUT)
    f.rect(x0 + 1, y0 + 1, x0 + 8, y0 + 16, S["screen"])
    f.rect(x0 + 1, y0 + 1, x0 + 8, y0 + 1, S["panel_d"])
    y = S["yellow"]; yd = S["yellow_d"]
    # cordão: laço que sai do alto do crachá e faz uma curva pra direita
    for (x, yy) in ((cx - 1, y0 + 7), (cx - 1, y0 + 6), (cx, y0 + 5), (cx + 1, y0 + 4), (cx + 2, y0 + 4), (cx + 3, y0 + 5),
                    (cx + 3, y0 + 6), (cx + 2, y0 + 7)):
        f.px(x, yy, y)
    f.px(cx, y0 + 6, y)
    # crachá 6×8: contorno amarelo, "foto" com cabeça e ombros
    bx, by = cx - 3, y0 + 8
    f.rect(bx, by, bx + 5, by + 8, y)
    f.rect(bx + 1, by + 1, bx + 4, by + 7, S["screen"])
    f.rect(bx + 2, by + 2, bx + 3, by + 3, y)       # cabeça
    f.rect(bx + 1, by + 5, bx + 4, by + 5, y)       # ombros
    f.px(bx + 1, by + 6, y); f.px(bx + 4, by + 6, y)
    f.px(bx, by + 8, yd); f.px(bx + 5, by + 8, yd)
    f.px(cx, by - 1, yd)                            # argola
    # LED vermelho de "sem energia" embaixo do crachá
    f.px(cx, y0 + 16 - 0 + 0, S["red_d"]) if False else None


def jammed_door():
    f = face_base(False, False)
    # batente (vão escuro) e folha torta: o lado da dobradiça (esq.) segura e o resto cai, deixando uma cunha de vão
    f.rect(1, 1, 19, 22, OUT)
    f.rect(2, 2, 18, 21, S["screen"])
    f.poly([(2, 4), (18, 2), (18, 21), (2, 21)], S["screen"])
    for x in range(3, 18):                                   # faixa de perigo no batente de cima
        f.px(x, 2, S["orange"] if (x // 2) % 2 == 0 else S["orange_d"])
    f.poly([(2, 5), (18, 9), (18, 21), (2, 21)], OUT)        # folha: topo desce pra direita
    f.poly([(3, 6), (17, 10), (17, 20), (3, 20)], "#656b8d")
    f.poly([(3, 6), (17, 10), (17, 12), (3, 8)], "#7b82a4")  # quina de cima, clara
    f.poly([(3, 17), (17, 17), (17, 20), (3, 20)], "#4d5272")
    for x in range(4, 17):                                   # tinta de perigo desbotada, acompanha a folha
        if (x // 2) % 2 == 0:
            f.px(x, 14, S["orange"]); f.px(x, 15, S["orange_d"])
    for (x, y) in ((4, 9), (15, 12), (4, 18), (15, 18)):
        f.px(x, y, S["rivet"])
    for (x, y) in ((7, 11), (8, 12), (9, 13), (6, 10), (10, 14), (11, 15)):   # rachadura
        f.px(x, y, S["seam"])
    # faíscas na cunha
    for (x, y, c) in ((14, 5, "yellow"), (16, 7, "orange"), (11, 6, "orange"), (17, 4, "yellow")):
        f.px(x, y, S[c])
    f.px(8, 5, S["seam"])
    # puxador
    f.rect(13, 13, 14, 15, S["rivet"])
    f.px(13, 15, S["seam"])
    # leitor de crachá
    badge_reader(f)
    return f


def emergency_light():
    f = face_base(False, False)
    # brilho vermelho na parede em volta (degradê em 2 níveis com padrão xadrez, sem antialias)
    cx, cy = 15.5, 9
    for y in range(1, FACE_H - 1):
        for x in range(2, T - 2):
            d = ((x - cx) / 1.0) ** 2 + ((y - cy) * 1.5) ** 2
            if d < 150:
                base = f.get(x, y)
                if base[:3] == (27, 22, 48):
                    continue
                if d < 60 or (x + y) % 2 == 0 and d < 110 or d < 150 and (x + y) % 4 == 0 and d < 150:
                    r, g, b, a = base
                    k = 0.55 if d < 60 else 0.3
                    f.px(x, y, (int(r + (224 - r) * k), int(g * (1 - k * 0.5)), int(b * (1 - k * 0.5)), 255))
    # luminária: cúpula com grade
    f.rect(9, 3, 22, 3, OUT)
    f.rect(8, 4, 23, 15, OUT)
    f.rect(9, 4, 22, 14, S["red_d"])
    f.rect(10, 5, 21, 13, S["red"])
    f.rect(11, 6, 20, 8, S["red_l"])
    f.rect(12, 6, 15, 7, "#ffd0b8")
    for x in (13, 16, 19):                                           # grade da cúpula
        f.rect(x, 5, x, 13, S["red_d"])
    f.rect(10, 13, 21, 13, S["red_d"])
    f.rect(8, 16, 23, 17, OUT)
    f.rect(9, 16, 22, 16, S["panel_l"])
    f.rect(12, 18, 19, 18, S["panel_d"])
    return f


# ---------------------------------------------------------------------------------------------------------------------
# Montagem do report: sala 9×6 tiles montada com os sprites, na ordem do jogo (chão, topo/face, props pelo pé)
# ---------------------------------------------------------------------------------------------------------------------
def autotile_compose(atlas: Image.Image, wet, tx, ty):
    """Mesma tabela do game/autotile.py (RPG Maker A2)."""
    M = 16
    SRC = {
        "TL": {"outer": (0, 2), "hedge": (2, 2), "vedge": (0, 4), "full": (2, 4), "inner": (2, 0)},
        "TR": {"outer": (3, 2), "hedge": (1, 2), "vedge": (3, 4), "full": (1, 4), "inner": (3, 0)},
        "BL": {"outer": (0, 5), "hedge": (2, 5), "vedge": (0, 3), "full": (2, 3), "inner": (2, 1)},
        "BR": {"outer": (3, 5), "hedge": (1, 5), "vedge": (3, 3), "full": (1, 3), "inner": (3, 1)},
    }
    ISO = {"TL": (0, 0), "TR": (1, 0), "BL": (0, 1), "BR": (1, 1)}
    OFF = {"TL": (0, 0), "TR": (M, 0), "BL": (0, M), "BR": (M, M)}
    CORNER = {"TL": (-1, -1), "TR": (1, -1), "BL": (-1, 1), "BR": (1, 1)}
    key = []
    for q in ("TL", "TR", "BL", "BR"):
        dx, dy = CORNER[q]
        side, vert, diag = wet(tx + dx, ty), wet(tx, ty + dy), wet(tx + dx, ty + dy)
        key.append(("full" if diag else "inner") if side and vert else "hedge" if side else "vedge" if vert else "outer")
    tile = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    allout = all(k == "outer" for k in key)
    for q, k in zip(("TL", "TR", "BL", "BR"), key):
        c, r = ISO[q] if allout else SRC[q][k]
        tile.alpha_composite(atlas.crop((c * M, r * M, c * M + M, r * M + M)), OFF[q])
    return tile


ROOM = ["#########",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        "#.......#",
        "#########"]


ROOMVAR = [0, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 0]


def build_room(sp, with_props=True):
    """Sala 9×6 (+24 px de topo). sp = dict de imagens. Retorna (imagem, dict de posições)."""
    W, H = 9, 8
    LIFT = 24
    cv = Image.new("RGBA", (W * T, H * T + LIFT), (0, 0, 0, 255))
    wall = lambda x, y: 0 <= x < W and 0 <= y < H and ROOM[y][x] == "#"
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                cv.alpha_composite(sp["floor"][ROOMVAR[(x * 5 + y * 11) % len(ROOMVAR)]], (x * T, y * T + LIFT))
    if with_props:
        cv.alpha_composite(sp["hatch"], (1 * T, 5 * T + LIFT))
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                continue
            cv.alpha_composite(autotile_compose(sp["top"], wall, x, y), (x * T, y * T))   # = (x, y-24) + LIFT
            if not wall(x, y + 1):
                face = None
                if with_props and (x, y) == (6, 0):
                    face = sp["door"]
                elif with_props and (x, y) == (3, 0):
                    face = sp["panel"]
                elif with_props and (x, y) == (1, 0):
                    face = sp["light"]
                elif with_props and (x, y) == (7, 5):
                    face = None
                if face is None:
                    idx = int(wall(x - 1, y)) + 2 * int(wall(x + 1, y))
                    face = sp["face"].crop((idx * T, 0, idx * T + T, FACE_H))
                cv.alpha_composite(face, (x * T, y * T + 8 + LIFT))
    if with_props:
        # contêiner: pé no centro de baixo do tile (6, 3) (blit em (x-4, y-12) como o lacrado)
        cv.alpha_composite(sp["container"], (6 * T - 4 + 0, 4 * T - 12 + LIFT))
    return cv


def lantern(img: Image.Image, cx, cy, radius, emergency=None):
    """Escuro da caverna: círculo de lanterna em degraus (pixel art), 5 níveis. emergency = [(x, y, r)] vermelho."""
    a = np.array(img.convert("RGB")).astype(float)
    H, W, _ = a.shape
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 1.1) ** 2)
    steps = np.array([1.0, 0.72, 0.48, 0.28, 0.14])
    lvl = np.clip((d / radius * 4).astype(int), 0, 4)
    light = steps[lvl]
    tint = np.ones((H, W, 3))
    tint[..., 0] = light * 1.0 + (1 - light) * 0.3
    tint[..., 1] = light * 1.0 + (1 - light) * 0.35
    tint[..., 2] = light * 1.0 + (1 - light) * 0.6
    out = a * (light[..., None] * 0.0 + tint) * np.clip(light[..., None] + 0.05, 0, 1)
    if emergency:
        for (ex, ey, er) in emergency:
            de = np.sqrt((xx - ex) ** 2 + ((yy - ey) * 1.1) ** 2)
            l2 = np.clip((1 - de / er), 0, 1)
            l2 = np.floor(l2 * 3) / 3
            out[..., 0] += a[..., 0] * l2 * 0.7
            out[..., 1] += a[..., 1] * l2 * 0.08
            out[..., 2] += a[..., 2] * l2 * 0.08
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


# ---------------------------------------------------------------------------------------------------------------------
def main():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    out["hull_wall_top"] = wall_top_atlas()
    out["hull_wall_face"] = wall_face_strip().im
    for i in range(4):
        out[f"hull_floor_{i}"] = hull_floor(i).im
    out["vesper_hatch"] = hatch().im
    out["vesper_container_broken"] = container_broken().im
    out["vesper_power_panel"] = power_panel().im
    out["vesper_jammed_door"] = jammed_door().im
    out["vesper_emergency_light"] = emergency_light().im
    for k, im in out.items():
        im.save(PEND / f"{k}.png")
    sp = dict(top=out["hull_wall_top"], face=out["hull_wall_face"], floor=[out[f"hull_floor_{i}"] for i in range(4)],
              hatch=out["vesper_hatch"], door=out["vesper_jammed_door"], panel=out["vesper_power_panel"],
              light=out["vesper_emergency_light"], container=out["vesper_container_broken"])
    room = build_room(sp)
    room.save(REP / "sala_clara.png")
    # luzes: lanterna do player perto da porta; a luz de emergência vermelha na parede
    dark = lantern(room, 6 * T + 16, 1 * T + 44, 84, emergency=[(1 * T + 16, 24 + 22, 52)])
    dark.save(REP / "sala_escura.png")
    dark2 = lantern(room, 2 * T + 8, 5 * T + 40, 78, emergency=[(1 * T + 16, 24 + 22, 52)])
    dark2.save(REP / "sala_escura_porao.png")
    print("ok", len(out), "sprites")


if __name__ == "__main__":
    main()
