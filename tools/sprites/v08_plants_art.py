"""v0.8 · as 4 culturas do cultivador (alga + plantas 1–3) em 4 etapas, desenhadas em 2D numa grade pequena.

Cada planta sai numa grade W×H (padrão 20×19) com o PÉ no centro da última linha. Pixel art chapada: cada peça
(fita, folha, pétala) pinta 2–3 faixas de cor com luz de cima-esquerda, e no fim entra um contorno escuro na cor de
"sombra dentro d'água" (mais macio que o #1b1630, porque a planta está atrás do vidro). Sem aleatório.

    grid = plant("plant_2", 3)        # np.array (H, W, 4) RGBA
"""
from __future__ import annotations

import math

import numpy as np

W, H = 20, 19


def rgb(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


# ---- paletas (fundo → brilho) ----------------------------------------------------------------------------------------
PAL = {
    "algae": dict(line="#163a26", d="#2f6b3a", m="#4f9a3f", l="#7fc94f", h="#c4ec7a", y="#d8c25a", Y="#fff2a0"),
    "plant_1": dict(line="#123a34", d="#1f6a52", m="#35a06a", l="#74d488", h="#c8f2a8",
                    wd="#2b7fb3", wm="#59c8e6", wl="#bff2ff", ww="#ffffff"),
    "plant_2": dict(line="#101c40", d="#22407a", m="#2f68b0", l="#58a0e0", h="#a6ecff", f="#e9fbff", g="#ffffff"),
    "plant_3": dict(line="#1c1840", d="#3a3f7a", m="#5a5fae", l="#8a8fe0", ld="#2f6f78", lm="#4fa0a0",
                    i0="#3d8fb8", i1="#6cc6e6", i2="#a6ecff", i3="#e9fbff", v0="#7a4cc0", v1="#b48cf0", v2="#f0e0ff"),
}


class G:
    """Grade de cores (None = vazio), com peças simples e o contorno no fim."""

    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.c = [[None] * w for _ in range(h)]

    def px(self, x, y, col):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h:
            self.c[y][x] = col

    def get(self, x, y):
        return self.c[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def blob(self, cx, cy, rx, ry, cols, hl=None):
        """Elipse chapada em 3 faixas (luz de cima-esquerda). cols = (escuro, meio, claro)."""
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                u, v = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
                if u * u + v * v <= 1.0:
                    k = u * 0.7 + v * 0.7
                    self.px(x, y, cols[2] if k < -0.35 else cols[0] if k > 0.45 else cols[1])
        if hl:
            self.px(cx - rx * 0.45, cy - ry * 0.45, hl)

    def line(self, pts, cols, width=1):
        """Polilinha. width 2: o pixel da esquerda claro, o da direita escuro."""
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * 2))
            for i in range(n + 1):
                t = i / n
                x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                if width == 1:
                    self.px(x, y, cols[1])
                else:
                    self.px(math.floor(x), y, cols[2])
                    self.px(math.floor(x) + 1, y, cols[0])

    def outline(self, col):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.c[y][x] is not None:
                    continue
                if any(self.get(x + dx, y + dy) not in (None, "OUT") for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    add.append((x, y))
        for x, y in add:
            if y < self.h - 1 or True:
                self.c[y][x] = col

    def array(self):
        a = np.zeros((self.h, self.w, 4), np.uint8)
        for y in range(self.h):
            for x in range(self.w):
                if self.c[y][x]:
                    a[y, x] = rgb(self.c[y][x])
        return a


FOOT_X = W // 2          # 10
BASE_Y = H - 1           # 18 (a linha do pé)


def _wave(x0, h, amp, lam, ph, y_base=BASE_Y):
    pts = []
    for k in range(int(h) + 1):
        y = y_base - k
        x = x0 + amp * math.sin(k / lam + ph) * min(1.0, k / 3.0)
        pts.append((x, y))
    return pts


# ---- Alga (a cultura-controle, alga da Terra): fitas de alga onduladas com bolhinhas amarelas -----------------------
def algae(stage):
    p = PAL["algae"]
    g = G()
    cols = (p["d"], p["m"], p["l"])
    fronds = {
        0: [(-1, 3, 0.4, 1.6, 0.0), (1, 2, 0.4, 1.6, 2.0)],
        1: [(-3, 6, 0.8, 2.0, 0.3), (0, 8, 0.9, 2.2, 1.9), (3, 5, 0.8, 1.8, 3.4)],
        2: [(-5, 8, 0.9, 2.2, 0.2), (-2, 12, 1.1, 2.4, 1.7), (1, 13, 1.1, 2.4, 3.1), (4, 10, 1.0, 2.2, 4.4),
            (6, 6, 0.6, 1.8, 0.9)],
        3: [(-7, 11, 1.0, 2.3, 0.1), (-4, 16, 1.3, 2.6, 1.5), (-1, 17, 1.2, 2.5, 3.0), (2, 17, 1.3, 2.6, 4.2),
            (5, 14, 1.2, 2.4, 5.6), (7, 9, 0.9, 2.0, 0.6)],
    }[stage]
    for (dx, h, amp, lam, ph) in fronds:
        pts = _wave(FOOT_X + dx, h, amp, lam, ph)
        g.line(pts, cols, width=2)
        tx, ty = pts[-1]
        g.px(tx, ty, p["h"])
        g.px(tx + 1, ty, p["l"])
    if stage >= 2:
        bl = [(-2, 7), (1, 9), (4, 6)] if stage == 2 else [(-4, 9), (-1, 12), (2, 7), (2, 13), (5, 9), (-6, 6)]
        for i, (dx, k) in enumerate(bl):
            fx = [f for f in fronds if abs(f[0] - dx) < 1.5]
            f = fx[0] if fx else fronds[0]
            x = FOOT_X + f[0] + f[2] * math.sin(k / f[3] + f[4]) * min(1.0, k / 3.0)
            g.px(x + 2, BASE_Y - k, p["y"])
            g.px(x + 2, BASE_Y - k - 1, p["Y"])
    g.outline(p["line"])
    return g


# ---- Planta 1 (amostra simples): folhas redondas e gordas num talo, com frutinhas-gota de água -----------------------
def plant_1(stage):
    p = PAL["plant_1"]
    g = G()
    cols = (p["d"], p["m"], p["l"])
    hs = [3, 7, 12, 16][stage]
    stem = [(FOOT_X - 0.5 + 0.6 * math.sin(k / 3.0), BASE_Y - k) for k in range(hs + 1)]
    g.line(stem, cols, width=2)
    leaves = {
        0: [(-2, 2, 1.8, 1.2), (2, 2, 1.8, 1.2)],
        1: [(-3, 3, 2.6, 1.6), (3, 5, 2.6, 1.6), (-1, 7, 1.6, 1.2)],
        2: [(-4, 3, 3.2, 1.9), (4, 6, 3.2, 1.9), (-4, 9, 2.8, 1.7), (3, 11, 2.2, 1.5), (0, 12, 1.6, 1.4)],
        3: [(-5, 3, 3.6, 2.1), (5, 5, 3.6, 2.1), (-5, 9, 3.2, 1.9), (5, 11, 3.0, 1.8), (-3, 14, 2.4, 1.6),
            (3, 15, 2.2, 1.5), (0, 16, 1.8, 1.5)],
    }[stage]
    for (dx, k, rx, ry) in leaves:
        cx, cy = FOOT_X + dx, BASE_Y - k
        g.blob(cx, cy, rx, ry, cols, hl=p["h"])
        # nervura: 1 px escuro do talo até o meio da folha
        g.px(cx - (1 if dx > 0 else -1) * 0, cy, p["d"])
    if stage == 3:
        for (dx, k) in ((-2, 6), (3, 9)):
            cx, cy = FOOT_X + dx, BASE_Y - k
            g.blob(cx + 0.5, cy + 0.5, 1.6, 1.8, (p["wd"], p["wm"], p["wl"]), hl=p["ww"])
            g.px(cx, cy - 2, p["d"])
    g.outline(p["line"])
    return g


# ---- Planta 2 (amostra com mutação): báculos de samambaia enrolados, azul-petróleo com geada e pontos que brilham ---
def _curl(g, x0, h, side, r, cols, frost, glow):
    """Talo que sobe e enrola num báculo (espiral) no topo. side = +1 enrola pra direita, -1 pra esquerda."""
    pts = [(x0 + 0.4 * math.sin(k / 2.5), BASE_Y - k) for k in range(int(h) + 1)]
    tx, ty = pts[-1]
    cx = tx + side * r
    cy = ty
    spiral = []
    for i in range(0, 22):
        a = math.pi - i * 0.42 if side > 0 else i * 0.42
        rr = r * (1 - i / 26)
        spiral.append((cx + rr * math.cos(a), cy - rr * math.sin(a) * 1.0))
    g.line(pts, cols, width=2)
    g.line(spiral, cols, width=2)
    ex, ey = spiral[-1]
    g.px(ex, ey, frost)
    g.px(ex + side, ey, glow)
    return pts, spiral


def plant_2(stage):
    p = PAL["plant_2"]
    g = G()
    cols = (p["d"], p["m"], p["l"])
    spec = {
        0: [(0, 3, 1, 1.6)],
        1: [(-2, 5, -1, 2.0), (2, 7, 1, 2.2)],
        2: [(-3, 8, -1, 2.6), (2, 11, 1, 2.8)],
        3: [(-5, 10, -1, 3.0), (-1, 15, -1, 3.2), (3, 13, 1, 3.2), (6, 7, 1, 2.2)],
    }[stage]
    for (dx, h, side, r) in spec:
        pts, sp = _curl(g, FOOT_X + dx, h, side, r, cols, p["f"], p["h"])
        if stage >= 2:                                  # folíolos: tracinhos claros nos dois lados do talo
            for k in range(4, int(h) - 2, 4):
                x, y = pts[k]
                g.px(x - 1, y, p["l"])
                g.px(x + 2, y - 1, p["l"])
    if stage == 3:                                      # nós que brilham (geada viva)
        for (dx, k) in ((-5, 5), (3, 7), (-1, 10)):
            g.px(FOOT_X + dx - 1, BASE_Y - k, p["g"])
            g.px(FOOT_X + dx - 1, BASE_Y - k + 1, p["h"])
    g.outline(p["line"])
    return g


# ---- Planta 3 (amostra rara): lírio de gelo, talo violeta e uma flor de pétalas de cristal gordinhas com miolo aceso
def _petal(g, cx, cy, rx, ry, p):
    g.blob(cx, cy, rx, ry, (p["i0"], p["i1"], p["i2"]), hl=p["i3"])


def plant_3(stage):
    p = PAL["plant_3"]
    g = G()
    stalk = (p["d"], p["m"], p["l"])
    leaf = (p["ld"], p["lm"], p["lm"])
    hs = [2, 5, 8, 8][stage]
    pts = [(FOOT_X - 0.5 + 0.5 * math.sin(k / 4.0), BASE_Y - k) for k in range(hs + 1)]
    if stage >= 1:                                      # folhas largas da base
        g.blob(FOOT_X - 3, BASE_Y - 1, 3.2, 1.4, leaf)
        g.blob(FOOT_X + 3, BASE_Y - 1, 3.2, 1.4, leaf)
    if stage >= 2:
        g.blob(FOOT_X - 5, BASE_Y - 4, 2.6, 1.2, leaf)
        g.blob(FOOT_X + 5, BASE_Y - 5, 2.6, 1.2, leaf)
    g.line(pts, stalk, width=2)
    tx, ty = pts[-1]
    tx += 0.5
    if stage == 0:                                      # bulbo violeta brotando com ponta de gelo
        g.blob(FOOT_X, BASE_Y - 1.5, 2.4, 2.0, (p["v0"], p["v0"], p["v1"]), hl=p["v2"])
        g.px(FOOT_X, BASE_Y - 4, p["i2"])
        g.px(FOOT_X - 1, BASE_Y - 4, p["i1"])
    elif stage == 1:                                    # botão fechado: gota violeta com capa de gelo
        g.blob(tx, ty - 2, 2.4, 3.0, (p["v0"], p["v0"], p["v1"]), hl=p["v2"])
        g.blob(tx, ty - 4.5, 1.6, 1.4, (p["i0"], p["i1"], p["i2"]), hl=p["i3"])
    elif stage == 2:                                    # botão abrindo: 3 pétalas de cristal fechadas no miolo
        _petal(g, tx - 2.5, ty - 3, 2.4, 3.2, p)
        _petal(g, tx + 2.5, ty - 3, 2.4, 3.2, p)
        _petal(g, tx, ty - 5, 2.2, 3.0, p)
        g.blob(tx, ty - 1.5, 1.8, 1.4, (p["v0"], p["v1"], p["v1"]), hl=p["v2"])
    else:                                               # aberta: 5 pétalas gordinhas em leque + miolo aceso
        for (dx, dy, rx, ry) in ((-6, -2, 3.0, 2.2), (6, -2, 3.0, 2.2), (-3.5, -6, 2.6, 3.2), (3.5, -6, 2.6, 3.2),
                                 (0, -8, 2.6, 3.0)):
            _petal(g, tx + dx, ty + dy, rx, ry, p)
        g.blob(tx, ty - 3, 2.6, 2.2, (p["v0"], p["v1"], p["v2"]))
        g.px(tx - 1, ty - 4, "#ffffff")
        g.px(tx, ty - 4, "#ffffff")
        g.px(tx - 1, ty - 3, p["v2"])
    g.outline(p["line"])
    return g


CROPS = {"algae": algae, "plant_1": plant_1, "plant_2": plant_2, "plant_3": plant_3}


def plant(name, stage):
    return CROPS[name](stage).array()
