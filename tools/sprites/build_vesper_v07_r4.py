#!/usr/bin/env python3
"""Hesper v0.7 M4 · rodada 4: pilha de contêineres 2×1 e kit de props da nave (r3d + à mão). Rode depois dos outros.

Saída: reports/design/v07_m4/pendentes/<id>.png e icon_<id>.png ; reports/design/v07_m4/sala_r4_{cabine,alojamento}_{clara,escura}.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chests_r3d as CH  # noqa: E402
import build_vesper_v07 as V  # noqa: E402
import build_vesper_v07_r2 as R2  # noqa: E402
import build_vesper_v07_r3 as R3  # noqa: E402
from r3d import Pal, Scene, SA  # noqa: E402

PEND, REP, T, S, OUT = V.PEND, V.REP, V.T, V.S, V.OUT
SL = Pal(["#b4b9d2", "#8f94b4", "#6a6f90", "#4a4e6b", "#2e3048"])
SLD = Pal(["#6a6f90", "#4a4e6b", "#3a3d56", "#2e3048", "#1f2036"])
CR = Pal(["#ffffff", "#eceaf2", "#cfcbdb", "#a29db6", "#6f6a88"])
OR = Pal(["#f4a06a", "#e2733a", "#c8683a", "#a9482a", "#6e2a1c"])
TANK = Pal(["#e4e2ec", "#cfcbdb", "#b4afc6", "#8f8aa6", "#6a6580"])
GO = CH.P_GOLD
SCR = Pal(["#2c3a52", "#1e2840", "#161d33", "#10152a", "#0a0e1e"])
DIM = Pal(["#3c6a80"] * 5, emit=True, emit_tone=0)
LEDR = Pal(["#7a2a36"] * 5, emit=True, emit_tone=0)
LEDO = Pal(["#ffb04a"] * 5, emit=True, emit_tone=0)
LEDG = Pal(["#7fe08a"] * 5, emit=True, emit_tone=0)
CAB_R = Pal(["#ff8a6a", "#e0453a", "#b3333a", "#8e2a30", "#5a1c28"])
CAB_B = Pal(["#9ad8f0", "#59b0d0", "#3a86a8", "#2a6482", "#1c4258"])
SHADOW = (27, 22, 48, 90)


class K:
    """Escala os números de uma cena (pra gerar o ícone 16×16 do mesmo modelo). Os painters usam coordenadas normalizadas."""

    def __init__(self, sc, k=1.0):
        self.sc, self.k = sc, k

    def _t(self, t):
        return tuple(v * self.k for v in t)

    def box(self, xr, yr, zr, pal, **kw):
        self.sc.box(self._t(xr), self._t(yr), self._t(zr), pal, **kw)

    def obox(self, c, h, pal, **kw):
        self.sc.obox(self._t(c), self._t(h), pal, **kw)

    def cyl(self, cx, cy, r, z0, z1, pal, **kw):
        if "r_top" in kw and kw["r_top"] is not None:
            kw["r_top"] *= self.k
        self.sc.cyl(cx * self.k, cy * self.k, r * self.k, z0 * self.k, z1 * self.k, pal, **kw)

    def hcyl(self, x0, x1, cy, cz, r, pal):
        self.sc.hcyl(x0 * self.k, x1 * self.k, cy * self.k, cz * self.k, max(r * self.k, 0.8), pal)

    def sphere(self, c, r, pal, **kw):
        self.sc.sphere(self._t(c), max(r * self.k, 0.8), pal, **kw)

    def tube(self, pts, r, pal, **kw):
        self.sc.tube([self._t(p) for p in pts], max(r * self.k, 0.5), pal, **kw)

    def dot(self, x, y, z, c, always=True):
        self.sc.dot(x * self.k, y * self.k, z * self.k, c, always=always)


def front(fn):
    """Painter de face frontal (face 2 do obox): fn(u, v, idx) com u, v em [-1, 1]; recebe `half` no uso."""
    def make(hx, hz):
        def paint(L, face):
            idx = np.zeros(len(L), int)
            if face == 2:
                fn(L[:, 0] / hx, L[:, 2] / hz, idx)
            return idx
        return paint
    return make


def top(fn):
    def make(hx, hy):
        def paint(L, face):
            idx = np.zeros(len(L), int)
            if face == 5:
                fn(L[:, 0] / hx, L[:, 1] / hy, idx)
            return idx
        return paint
    return make


def finish(cv, size, shadow=True, shw=None):
    im = cv.image().convert("RGBA")
    if shadow:
        sh = Image.new("RGBA", size, (0, 0, 0, 0))
        from PIL import ImageDraw
        w = shw or size[0] - 6
        ImageDraw.Draw(sh).ellipse([(size[0] - w) // 2, size[1] - 7, (size[0] + w) // 2, size[1] - 1], fill=SHADOW)
        sh.alpha_composite(im)
        im = sh
    return im


def render(model, size, k, detail, front_y):
    sc = CH.scene(size[0], size[1], front_y * k)
    model(K(sc, k), detail)
    cv = sc.render()
    CH.check(cv, "x", size)
    return cv


# ---------------------------------------------------------------------------------------------------------------------
# Modelos 3D (unidades em px do sprite 32×40; k escala pro ícone)
# ---------------------------------------------------------------------------------------------------------------------
def m_command_table(s, d):
    s.box((-20, 20), (-5, 5), (0, 9), SL, paint=front(lambda u, v, i: i.__setitem__((v > -0.1) & (v < 0.35), 1))(20, 4.5) if d else None, extra=(OR,))
    s.box((-9, 9), (-6, -4.5), (0.5, 8.5), SLD)
    s.box((-26, 26), (-8, 8), (9, 12), SL,
          paint=top(lambda u, v, i: i.__setitem__((abs(u) < 0.86) & (abs(v) < 0.62), 1))(26, 8) if d else None, extra=(SCR,))
    s.cyl(0, 0, 4.2, 12, 13.6, SLD)
    s.cyl(0, 0, 2.6, 13.6, 14.4, SCR)
    s.box((-15, 15), (-9.5, -6.5), (11.5, 13.2), SLD)
    for i, x in enumerate((-11, -7, -3, 1, 5)):
        s.dot(x, -9.8, 12.3, "#ffb04a" if i == 3 else "#7a2a36")
    for (x, y, z) in ((-3, 0, 19), (1, 1, 22), (3, -1, 17), (-1, 2, 25), (5, 0, 21)):
        s.dot(x, y, z, "#4f86a8")


def m_locker(s, d):
    s.box((-8, 8), (-5, 5), (0, 28), SL)
    s.box((-6.2, 6.2), (-5.2, -4.8), (1.8, 26.2), SCR)                 # vão aberto
    s.box((-4.6, 4.6), (-5.9, -4.4), (4, 17), CR)                      # o traje pendurado: tronco
    s.sphere((0, -5.2, 21), 3.6, CR)                                   # capacete
    s.box((-2.6, 2.6), (-7.2, -6.6), (19.6, 22.2), SCR) if False else None
    s.box((-2.4, 2.4), (-7.6, -7.0), (20, 22.4), SCR) if False else None
    s.box((-4.8, 4.8), (-6.0, -4.3), (9.5, 10.8), OR)                  # faixa laranja
    s.box((-3.8, -0.6), (-5.8, -4.4), (1.8, 4.5), CR)
    s.box((0.6, 3.8), (-5.8, -4.4), (1.8, 4.5), CR)
    s.box((-1.2, 1.2), (-5.3, -4.3), (18.5, 20.5), SCR)
    s.obox((-6.9, -8.8, 14), (4, 0.6, 13.2), SL, rot_z=-1.3)           # a porta aberta pra fora


def m_cyl(s, d):
    for (x0, x1, y, z) in ((-11, 9, -4.4, 3.4), (-8, 12, 4.6, 3.4), (-10, 10, 0, 10.2)):
        s.hcyl(x0, x1, y, z, 3.4, TANK)
        s.sphere((x0, y, z), 3.4, TANK)
        s.sphere((x1, y, z), 3.4, TANK)
        s.hcyl(x0 + 7, x0 + 9, y, z, 3.6, OR)
        s.box((x1 - 1, x1 + 2), (y - 1, y + 1), (z - 1, z + 1.4), SLD)


def m_rack(s, d):
    def fn(u, v, i):
        rec = (abs(u) < 0.82) & (v > -0.9) & (v < 0.86)
        i[rec] = 1
        r = ((v + 0.9) / 1.76 * 6)
        fr = r - np.floor(r)
        i[rec & (fr < 0.1)] = 2
        led = rec & (abs(u + 0.58) < 0.09) & (np.abs(fr - 0.5) < 0.14)
        i[led] = 3
        i[led & (np.floor(r) == 2)] = 4
        vents = rec & (u > 0.0) & (fr > 0.3) & (fr < 0.7) & (np.floor(u * 7) % 2 == 0)
        i[vents] = 2
    s.box((-9, 9), (-6, 6), (0, 30), SL, paint=front(fn)(9, 15) if d else None, extra=(SLD, SCR, LEDR, LEDO))
    s.box((-10, 10), (-6.6, 6.6), (29, 31), SLD)
    s.box((-10, 10), (-6.6, 6.6), (0, 1.6), SLD)


def m_rack_open(s, d):
    s.box((-9, -7.4), (-6, 6), (0, 30), SL)
    s.box((7.4, 9), (-6, 6), (0, 30), SL)
    s.box((-9, 9), (-6, 6), (28.4, 30), SL)
    s.box((-9, 9), (-6, 6), (0, 1.6), SLD)
    s.box((-7.4, 7.4), (3, 6), (1.6, 28.4), SCR)
    for i, (z, y) in enumerate(((3, -1.2), (8, -5.4), (13, -0.8), (18, -4.2), (23, -1.2))):   # servidores meio puxados
        s.box((-6.8, 6.8), (-5.8 + y * 0.0, 1 + y), (z, z + 4), SLD if i % 2 else SL)
        s.dot(-5, y - 3.5 if False else -5.3 + y * 0, z + 2, "#ffb04a" if i == 1 else "#7a2a36")
    s.obox((-6.5, -9.2, 15), (4.6, 0.6, 14.5), SL, rot_z=-1.25)
    s.tube([(-3, -6, 19), (-4, -9.5, 13), (-2, -11, 6), (3, -12, 1)], 0.9, CAB_R)
    s.tube([(2, -3, 10), (4, -8, 6), (7, -11, 1.5)], 0.9, CAB_B)
    s.tube([(5, -2, 23), (8, -6, 19), (9.5, -7, 14)], 0.8, GO)


def m_workstation(s, d):
    s.box((-12, 12), (-6, 6), (0, 10), SL, paint=front(lambda u, v, i: i.__setitem__((v > 0.1) & (v < 0.35), 1))(12, 5) if d else None, extra=(OR,))
    s.box((-13, 13), (-7, 7), (10, 11), SLD)
    s.cyl(0, 2, 2, 11, 13, SLD)
    s.box((-8, 8), (0.5, 2.5), (13, 23),
          SL, paint=front(lambda u, v, i: (i.__setitem__((abs(u) < 0.86) & (abs(v) < 0.88), 1), i.__setitem__((abs(u) < 0.86) & (abs(v) < 0.88) & ((np.floor(v * 6) % 3) == 0) & (u < 0.2), 2)))(8, 5) if d else None,
          extra=(SCR, DIM))
    s.box((-6, 6), (-5.5, -2.5), (11, 11.9), SLD)
    for x in (-4, -1, 2, 5):
        s.dot(x, -3.6, 12.2, "#8f94b4")
    s.cyl(9.5, -2.5, 1.5, 11, 14, OR)


def m_chair(s, d):
    s.cyl(0, 0, 5.5, 0, 1.2, SLD)
    s.cyl(0, 0, 1.4, 1.2, 6, SLD)
    s.box((-6.5, 6.5), (-5.5, 5.5), (6, 9), SL, paint=top(lambda u, v, i: i.__setitem__(np.abs(u) < 0.8, 1))(6.5, 5.5) if d else None, extra=(OR,))
    s.box((-5.8, 5.8), (4, 6.2), (9, 21), SL)
    s.box((-4.5, 4.5), (3.4, 6.8), (17.5, 23), OR)
    s.box((-8, -6.5), (-4, 3), (9, 11.5), SLD)
    s.box((6.5, 8), (-4, 3), (9, 11.5), SLD)


# ---- à mão ----------------------------------------------------------------------------------------------------------
def outline_img(im):
    a = im.im
    px = a.load()
    w, h = a.size
    add = []
    for y in range(h):
        for x in range(w):
            if px[x, y][3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 255:
                        add.append((x, y))
                        break
    for x, y in add:
        px[x, y] = V.rgb(OUT)


def uniforms():
    f = V.Img(32, 32)
    cr, crd, orn, ornd = "#eceaf2", "#b9b4c9", "#e2733a", "#a9482a"
    f.poly([(18, 15), (28, 14), (30, 20), (21, 22)], orn)                       # macacão laranja amassado
    f.poly([(21, 19), (30, 19), (30, 20), (21, 22)], ornd)
    f.poly([(7, 8), (16, 7), (17, 16), (8, 17)], cr)                          # macacão branco: tronco
    f.poly([(8, 14), (17, 13), (17, 16), (8, 17)], crd)
    f.poly([(7, 8), (2, 11), (3, 16), (8, 14)], cr)                           # manga
    f.poly([(16, 7), (22, 5), (24, 8), (17, 11)], cr)                         # outra manga, esticada
    f.poly([(8, 17), (17, 16), (21, 22), (17, 24), (13, 20), (10, 25), (5, 24)], crd)   # pernas
    f.poly([(8, 17), (17, 16), (18, 18), (9, 19)], cr)
    f.rect(8, 11, 16, 12, orn)                                                 # faixa no peito
    f.px(14, 9, "#ffd23a"); f.px(15, 9, "#ffd23a")                             # remendo de nome
    f.rect(22, 24, 27, 27, "#4a4e6b")                                          # bota
    f.rect(22, 24, 24, 25, "#6a6f90")
    f.rect(26, 27, 28, 27, "#2e3048")
    outline_img(f)
    return f


def wall_bunk():
    f = V.Img(32, 24)
    for x in (2, 3, 28, 29):
        f.rect(x, 1, x, 22, "#4a4e6b")
    for y0, c1 in ((3, "#e2733a"), (13, "#cfcbdb")):
        f.rect(3, y0, 28, y0 + 6, "#6a6f90")
        f.rect(3, y0, 28, y0, "#8f94b4")
        f.rect(4, y0 + 1, 27, y0 + 5, "#eceaf2")                              # colchão
        f.rect(11, y0 + 1, 27, y0 + 5, c1)                                      # cobertor
        f.rect(11, y0 + 1, 11, y0 + 5, "#a9482a" if c1 == "#e2733a" else "#a29db6")
        f.rect(5, y0 + 1, 9, y0 + 3, "#ffffff")                                 # travesseiro
        f.rect(4, y0 + 5, 27, y0 + 5, "#a29db6")
    f.rect(2, 11, 3, 12, "#8f94b4"); f.rect(28, 11, 29, 12, "#8f94b4")       # presilhas
    f.rect(27, 8, 27, 11, "#ffd23a")                                         # tira de segurança solta
    outline_img(f)
    return f


def cable_panel():
    f = V.Img(32, 24)
    f.rect(3, 2, 28, 17, "#6a6f90")
    f.rect(3, 2, 28, 2, "#b4b9d2")
    f.rect(5, 4, 26, 15, "#161d33")
    for x, y in ((4, 3), (27, 3), (4, 16), (27, 16)):
        f.px(x, y, "#9096b4")
    f.rect(8, 6, 14, 9, "#2e3048"); f.px(9, 7, "#7a2a36"); f.px(12, 7, "#ffb04a")     # placa de circuito
    f.rect(17, 6, 24, 8, "#2e3048")
    f.rect(5, 15, 26, 16, "#3a3d56")                                                  # tampa pendurada
    cols = (("#e0453a", [(10, 14), (10, 17), (11, 20), (13, 22)]), ("#ffd23a", [(15, 14), (16, 17), (14, 20), (15, 23)]),
            ("#59b0d0", [(20, 14), (21, 17), (23, 19), (23, 22)]))
    for c, pts in cols:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for t in range(6):
                f.px(round(x0 + (x1 - x0) * t / 5), round(y0 + (y1 - y0) * t / 5), c)
    for (x, y) in ((13, 22), (15, 23), (23, 22)):
        f.px(x, y, "#ffffff")
    outline_img(f)
    return f


# ---- ícones à mão ---------------------------------------------------------------------------------------------------
def icon_uniforms():
    f = V.Img(16, 16)
    f.poly([(3, 4), (8, 3), (9, 9), (4, 10)], "#eceaf2")
    f.poly([(3, 4), (1, 6), (2, 9), (4, 8)], "#eceaf2")
    f.poly([(4, 10), (9, 9), (11, 13), (8, 14), (6, 12), (4, 14)], "#b9b4c9")
    f.poly([(9, 7), (14, 7), (15, 11), (10, 12)], "#e2733a")
    f.rect(4, 6, 8, 6, "#e2733a")
    outline_img(f)
    return f


def icon_wall_bunk():
    f = V.Img(16, 16)
    f.rect(1, 1, 14, 6, "#6a6f90"); f.rect(2, 2, 13, 5, "#eceaf2"); f.rect(6, 2, 13, 5, "#e2733a")
    f.rect(1, 9, 14, 14, "#6a6f90"); f.rect(2, 10, 13, 13, "#eceaf2"); f.rect(6, 10, 13, 13, "#cfcbdb")
    f.rect(1, 7, 1, 8, "#4a4e6b"); f.rect(14, 7, 14, 8, "#4a4e6b")
    outline_img(f)
    return f


def icon_cable_panel():
    f = V.Img(16, 16)
    f.rect(1, 1, 14, 9, "#6a6f90"); f.rect(2, 2, 13, 8, "#161d33")
    f.rect(3, 3, 6, 5, "#2e3048"); f.px(4, 4, "#ffb04a")
    for x, c in ((4, "#e0453a"), (8, "#ffd23a"), (11, "#59b0d0")):
        f.rect(x, 8, x, 12, c)
    f.px(4, 13, "#ffffff"); f.px(11, 13, "#ffffff")
    outline_img(f)
    return f


# ---------------------------------------------------------------------------------------------------------------------
KIT = [
    # id, nome, lugar, tiles, colide, builder(sprite, icon)
    ("prop_command_table", "Mesa de comando", "floor", "2×1", True),
    ("wall_bunk", "Beliche de parede", "face", "1×1", False),
    ("prop_uniforms", "Uniformes largados", "decal", "1×1", False),
    ("prop_suit_locker", "Armário de traje", "floor", "1×1", True),
    ("prop_o2_cylinders", "Cilindros de O₂ tombados", "floor", "1×1", True),
    ("wall_cable_panel", "Painel de cabos soltos", "face", "1×1", False),
    ("prop_server_rack", "Rack de servidor", "floor", "1×1", True),
    ("prop_server_rack_open", "Rack de servidor aberto", "floor", "1×1", True),
    ("prop_workstation", "Estação de computador", "floor", "1×1", True),
    ("prop_pilot_chair", "Cadeira de piloto", "floor", "1×1", False),
    ("prop_container_stack", "Pilha de contêineres", "floor", "2×1", True),
]
MODELS = {"prop_command_table": (m_command_table, (64, 40), 0.5, -8.5, 0.27, (16, 16)),
          "prop_suit_locker": (m_locker, (32, 40), 1, -8, 0.42, (16, 16)),
          "prop_o2_cylinders": (m_cyl, (32, 40), 1, -7, 0.5, (16, 16)),
          "prop_server_rack": (m_rack, (32, 40), 1, -6.5, 0.4, (16, 16)),
          "prop_server_rack_open": (m_rack_open, (32, 40), 1, -12, 0.36, (16, 16)),
          "prop_workstation": (m_workstation, (32, 40), 1, -7, 0.5, (16, 16)),
          "prop_pilot_chair": (m_chair, (32, 40), 1, -6.5, 0.5, (16, 16))}


def stack_big():
    sc = CH.scene(64, 40, -7.0)
    R3.mini(sc, -14.0, -2.4, 0, 12.5, 5.6, 8.0, 2.8, 2.0, ridges=4)
    R3.mini(sc, 14.2, 2.0, 0, 11.5, 5.2, 6.0, 2.6, 1.9, ridges=4, seal=False)
    R3.mini(sc, -15.0, -2.8, 11.5, 10.5, 5.0, 6.5, 2.4, 1.9, ridges=3)
    cv = sc.render()
    CH.check(cv, "stack", (64, 40))
    return cv


def scene_room(sp, rows, faces, floor_props, decals, lantern, glows, name):
    W, H, LIFT = 9, 8, 24
    ROOM = ["#########"] + ["#.......#"] * 6 + ["#########"]
    cv = Image.new("RGBA", (W * T, H * T + LIFT), (0, 0, 0, 255))
    wall = lambda x, y: 0 <= x < W and 0 <= y < H and ROOM[y][x] == "#"
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                cv.alpha_composite(sp["floor"][R3_VAR[(x * 5 + y * 11) % len(R3_VAR)]], (x * T, y * T + LIFT))
    for (img, tx, ty) in decals:
        cv.alpha_composite(img, (tx * T, ty * T + LIFT))
    items = sorted(floor_props, key=lambda p: p[2])
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                continue
            cv.alpha_composite(V.autotile_compose(sp["top"], wall, x, y), (x * T, y * T))
            if not wall(x, y + 1):
                idx = int(wall(x - 1, y)) + 2 * int(wall(x + 1, y))
                cv.alpha_composite(sp["face"].crop((idx * T, 0, idx * T + T, 24)), (x * T, y * T + 8 + LIFT))
                if (x, y) in faces:
                    cv.alpha_composite(faces[(x, y)], (x * T, y * T + 8 + LIFT))
    for (img, tx, ty) in items:
        cv.alpha_composite(img, (tx * T, ty * T - 8 + LIFT))
    cv.save(REP / f"sala_r4_{name}_clara.png")
    R2.dark_scene(cv, lantern, glows).save(REP / f"sala_r4_{name}_escura.png")


R3_VAR = [0, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 0]


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    img = {}
    for pid, (model, size, kk, fy, ik, isz) in MODELS.items():
        cv = render(model, size, 1.0, True, fy)
        im = finish(cv, size)
        im.save(PEND / f"{pid}.png")
        ic = render(model, isz, ik, False, fy)
        ic.image().save(PEND / f"icon_{pid}.png")
        img[pid] = im
    cv = stack_big()
    im = finish(cv, (64, 40), shw=58)
    im.save(PEND / "prop_container_stack.png")
    img["prop_container_stack"] = im
    Image.open(PEND / "icon_prop_container_stack_A.png").save(PEND / "icon_prop_container_stack.png")
    for pid, fn, ic in (("prop_uniforms", uniforms, icon_uniforms), ("wall_bunk", wall_bunk, icon_wall_bunk),
                        ("wall_cable_panel", cable_panel, icon_cable_panel)):
        im = fn().im
        im.save(PEND / f"{pid}.png")
        ic().im.save(PEND / f"icon_{pid}.png")
        img[pid] = im
    sizes = {"prop_command_table": (64, 40), "prop_container_stack": (64, 40), "wall_bunk": (32, 24), "wall_cable_panel": (32, 24),
             "prop_uniforms": (32, 32)}
    for pid, *_ in KIT:
        assert Image.open(PEND / f"{pid}.png").size == sizes.get(pid, (32, 40)), pid
        assert Image.open(PEND / f"icon_{pid}.png").size == (16, 16), pid
    sp = dict(top=Image.open(PEND / "hull_wall_top.png").convert("RGBA"), face=Image.open(PEND / "hull_wall_face.png").convert("RGBA"),
              floor=[Image.open(PEND / f"hull_floor_{i}.png").convert("RGBA") for i in range(4)])
    light = Image.open(PEND / "vesper_emergency_light_A.png").convert("RGBA")
    # cabine: mesa central, racks, estação, cadeira, painel de cabos, luz
    scene_room(sp, 8, {(3, 0): img["wall_cable_panel"], (7, 0): light},
               [(img["prop_command_table"], 3, 3), (img["prop_server_rack"], 1, 1), (img["prop_server_rack"], 2, 1),
                (img["prop_server_rack_open"], 3, 1), (img["prop_workstation"], 6, 1), (img["prop_pilot_chair"], 6, 2),
                (img["prop_pilot_chair"], 4, 4)], [], (4 * T + 16, 3 * T + 40),
               [(1 * T + 16, 2 * T + 30, 14, (.6, .35, .05)), (2 * T + 16, 2 * T + 30, 14, (.6, .35, .05))], "cabine")
    scene_room(sp, 8, {(2, 0): img["wall_bunk"], (3, 0): img["wall_bunk"], (6, 0): img["wall_bunk"], (5, 0): light},
               [(img["prop_suit_locker"], 7, 1), (img["prop_o2_cylinders"], 7, 5), (img["prop_container_stack"], 1, 5)],
               [(img["prop_uniforms"], 3, 2), (img["prop_uniforms"], 5, 3)], (4 * T + 16, 2 * T + 40), [(5 * T + 16, 24 + 22, 30, (.7, .08, .08))],
               "alojamento")
    print("ok")




# ---------------------------------------------------------------------------------------------------------------------
# Saída (vesper_hatch) refeita pelo rascunho do dono: buraco escuro no chão + grade arrancada deitada por cima + parafusos
# ---------------------------------------------------------------------------------------------------------------------
def hatch_exit(variant):
    from PIL import ImageDraw
    f = V.hull_floor(0)
    hx0, hy0, hx1, hy1 = (9, 14, 27, 29) if variant == "A" else (7, 12, 25, 28)
    f.rect(hx0 - 1, hy0 - 1, hx1 + 1, hy1 + 1, OUT)
    f.rect(hx0, hy0, hx1, hy1, "#0c0916")
    f.rect(hx0, hy0, hx1, hy0 + 1, "#2e3048")                               # parede de dentro (lado de longe)
    f.rect(hx0, hy0, hx0, hy1, "#1f2036")
    f.rect(hx0 - 2, hy1 + 1, hx1 + 2, hy1 + 1, S["panel_l"])                  # lábio de chapa na frente
    f.rect(hx0 - 1, hy0 - 2, hx1 + 1, hy0 - 2, S["panel_l"])
    if variant == "A":                                                       # escada sutil: dois montantes e degraus
        for x in (hx0 + 4, hx1 - 4):
            f.rect(x, hy0 + 2, x, hy1, "#2e3048")
        for y in (hy0 + 5, hy0 + 9, hy0 + 13):
            f.rect(hx0 + 4, y, hx1 - 4, y, "#3a3d56")
    else:                                                                    # um degrau largo no fundo
        f.rect(hx0 + 1, hy1 - 4, hx1 - 1, hy1, "#1f2036")
        f.rect(hx0 + 1, hy1 - 4, hx1 - 1, hy1 - 4, "#3a3d56")
    # a grade redonda, arrancada, deitada por cima do canto de cima/esquerda (com sombra no chão)
    cx, cy, rx, ry = (11, 9, 7, 6) if variant == "A" else (11, 8, 8, 6)
    sh = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - rx + 2, cy - ry + 3, cx + rx + 2, cy + ry + 3], fill=(27, 22, 48, 110))
    f.im.alpha_composite(sh)
    f.d = ImageDraw.Draw(f.im)
    f.d.ellipse([cx - rx - 1, cy - ry - 1, cx + rx + 1, cy + ry + 1], fill=V.rgb(OUT))
    f.d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=V.rgb(S["panel"]))
    f.d.ellipse([cx - rx + 2, cy - ry + 2, cx + rx - 2, cy + ry - 2], fill=V.rgb(S["low2"]))   # vão entre as barras
    for i, dy in enumerate((-2, 1, 4) if variant == "A" else (-2, 1, 4)):
        half = int(rx * (1 - (dy / ry) ** 2) ** .5) - 1
        f.rect(cx - half, cy + dy - (1 if variant == "A" else 0), cx + half, cy + dy, S["panel_l"] if i == 0 else S["panel"])
        f.rect(cx - half, cy + dy + 1, cx + half, cy + dy + 1, S["panel_d"]) if variant == "A" else None
    f.line(cx - rx + 1, cy - 2, cx - rx + 2, cy + 2, S["hl"])                   # brilho no aro
    # parafusos soltos no chão
    for (x, y) in (((29, 14), (30, 25), (5, 27), (22, 6)) if variant == "A" else ((28, 10), (29, 22), (3, 22), (18, 3))):
        f.rect(x, y, x + 1, y, S["rivet"])
        f.px(x, y + 1, S["seam"]); f.px(x + 1, y + 1, S["seam"])
    return f


def hatch_main():
    for v in "AB":
        hatch_exit(v).im.save(PEND / f"vesper_hatch_exit_{v}.png")


if __name__ == "__main__":
    main()
    hatch_main()
