#!/usr/bin/env python3
"""Gera todos os sprites do Hesper (contrato da bíblia, §6), as prévias de cena e o report de design.

Uso:  python3 tools/sprites/build_sprites.py

Tudo é determinístico (seeds fixas): rodar de novo gera exatamente os mesmos PNGs.
Pixel art de verdade: só cores sólidas (a única transparência parcial é a sombra no chão, um nível só).

Saídas:
  assets/sprites/*.png              sprites do contrato (escala 1:1)
  reports/design/preview_{stage}.png cenas 960x540 montadas só com os sprites
  reports/design/index.html          report pra aprovação
"""
from __future__ import annotations

import html
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design"
T = 32  # tamanho do tile


# ---------------------------------------------------------------- utilidades

def C(h: str, a: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


SHADOW = (0, 0, 0, 92)  # sombra no chão: preto 36%, um nível só


def hsh(x: int, y: int, s: int) -> float:
    """Hash inteiro -> [0,1). Determinístico, independente do PYTHONHASHSEED."""
    n = (x * 374761393 + y * 668265263 + s * 2246822519 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 15
    return n / 4294967296.0


def vnoise(x: float, y: float, s: int) -> float:
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hsh(ix, iy, s), hsh(ix + 1, iy, s)
    c, d = hsh(ix, iy + 1, s), hsh(ix + 1, iy + 1, s)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


def tile_noise(seed: int, variant: int, cells: int = 4, size: int = T) -> np.ndarray:
    """Ruído de valor periódico em `size` px. Os pontos de rede da borda (linha 0 e coluna 0)
    dependem só da seed, não da variação: assim variações diferentes emendam sem costura."""
    lat = np.zeros((cells, cells))
    for j in range(cells):
        for i in range(cells):
            v = 0 if (i == 0 or j == 0) else variant + 1
            lat[j, i] = hsh(i, j, seed * 31 + v * 977)
    out = np.zeros((size, size))
    step = size / cells
    for y in range(size):
        for x in range(size):
            gx, gy = x / step, y / step
            i0, j0 = int(gx), int(gy)
            fx, fy = gx - i0, gy - j0
            sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
            i1, j1 = (i0 + 1) % cells, (j0 + 1) % cells
            a, b = lat[j0, i0], lat[j0, i1]
            c, d = lat[j1, i0], lat[j1, i1]
            out[y, x] = a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy
    return out


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def px(self, x, y, c, wrap=False):
        x, y = int(x), int(y)
        if wrap:
            x %= self.w
            y %= self.h
        elif not (0 <= x < self.w and 0 <= y < self.h):
            return
        self.a[y, x] = c

    def get(self, x, y):
        return tuple(int(v) for v in self.a[y % self.h, x % self.w])

    def rect(self, x, y, w, h, c, wrap=False):
        x, y, w, h = int(x), int(y), int(w), int(h)
        if wrap:
            for yy in range(y, y + h):
                for xx in range(x, x + w):
                    self.px(xx, yy, c, True)
            return
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 > x0 and y1 > y0:
            self.a[y0:y1, x0:x1] = c

    def ellipse(self, cx, cy, rx, ry, c):
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                    self.px(x, y, c)

    def disc(self, cx, cy, r, c):
        self.ellipse(cx, cy, r, r, c)

    def bands(self, x, y, h, spec):
        for col, w in spec:
            self.rect(x, y, w, h, C(col))
            x += w

    def draw_map(self, rows, pal, ox=0, oy=0):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != "." and ch != " ":
                    self.px(ox + i, oy + j, C(pal[ch]))

    def outline(self, col, only_alpha_full=True):
        """Contorno de 1 px (4-vizinhos) em volta de tudo que é opaco."""
        op = self.a[:, :, 3] == 255 if only_alpha_full else self.a[:, :, 3] > 0
        ring = np.zeros_like(op)
        ring[1:, :] |= op[:-1, :]
        ring[:-1, :] |= op[1:, :]
        ring[:, 1:] |= op[:, :-1]
        ring[:, :-1] |= op[:, 1:]
        ring &= ~op
        self.a[ring] = col

    def paste(self, other: "Canvas", ox, oy):
        """Cola outro canvas por cima (alpha 'over' com pixels sólidos)."""
        img = Image.fromarray(self.a)
        img.alpha_composite(Image.fromarray(other.a), (int(ox), int(oy)))
        self.a = np.array(img)

    def image(self) -> Image.Image:
        return Image.fromarray(self.a)

    def save(self, name: str):
        self.image().save(OUT / name)


# ---------------------------------------------------------------- paletas (bíblia §3 + mockup)

STAGES = {
    "dead": dict(
        floor=["#7b402c", "#743b29", "#814430"], patch="#6a3424", dot="#5c2d1f",
        peb="#94553b", pebHi="#b0704f", crack="#57291c",
        rock="#4b3332", rock2="#563a38", rockHi="#6e4b47", rockDot="#352323",
        face="#2f1f1f", faceHi="#5f4240", faceMid="#3b2828", faceDark="#221616",
        water="#3d6f86", waterD="#2f5a70", waterHi="#9fcfe0", foam="#b8e2ee",
    ),
    "mist": dict(
        floor=["#6e5a4f", "#685448", "#75604f"], patch="#5e4c42", dot="#54443b",
        peb="#85715f", pebHi="#a08b78", crack=None,
        rock="#4a4447", rock2="#544d50", rockHi="#6c6467", rockDot="#343033",
        face="#2b272a", faceHi="#5d5659", faceMid="#363134", faceDark="#1f1c1e",
        water="#3f7690", waterD="#315f78", waterHi="#a3d2e3", foam="#b8e2ee",
    ),
    "green": dict(
        floor=["#4d7a39", "#477235", "#548140"], patch="#426b31", dot="#3a5f2c",
        peb="#7a8a6a", pebHi="#9aa88a", crack=None,
        rock="#4b4a45", rock2="#55544e", rockHi="#6d6c64", rockDot="#353530",
        face="#2c2c28", faceHi="#5c5b54", faceMid="#373732", faceDark="#1f1f1c",
        water="#2c7ea6", waterD="#22668a", waterHi="#9ed6ee", foam="#c8eef8",
        grass="#79b04f", grass2="#5e9640", moss="#5c9a43", moss2="#7cba58", mossD="#3f7230",
    ),
}
STAGE_SEED = {"dead": 11, "mist": 23, "green": 37}

ORES = {
    "iron": dict(hi="#ffd8b0", light="#e8a066", mid="#c97a45", dark="#a5582c", line="#4a2214"),
    "silicon": dict(hi="#f4f8fc", light="#c3d1e2", mid="#a2b0c4", dark="#7d8ca3", line="#2c3342"),
    "ice": dict(hi="#effdff", light="#a6ecff", mid="#7fd3ef", dark="#4fb3d6", line="#1d4f66"),
}

GOLD, GOLD_D, GOLD_L = "#f2c46d", "#b8893a", "#fff3c4"
INK = "#1a1418"


# ---------------------------------------------------------------- tiles

def make_floor(stage: str, v: int) -> Canvas:
    P, seed = STAGES[stage], STAGE_SEED[stage]
    cv = Canvas(T, T)
    n = tile_noise(seed, v)
    f0, f1, f2 = (C(c) for c in P["floor"])
    for y in range(T):
        for x in range(T):
            cv.a[y, x] = f1 if n[y, x] < 0.36 else f2 if n[y, x] > 0.66 else f0
    s = seed * 100 + v * 7
    # manchas e pontinhos (envolvem a borda: emenda perfeita)
    for i in range(5 + v):
        x, y = int(hsh(i, 1, s) * T), int(hsh(i, 2, s) * T)
        cv.rect(x, y, 2 + int(hsh(i, 3, s) * 3) * 2 // 2 * 1 + 1, 1 + (i % 2), C(P["patch"]), wrap=True)
    for i in range(9):
        cv.px(int(hsh(i, 4, s) * T), int(hsh(i, 5, s) * T), C(P["dot"]), wrap=True)
    # rachadura (só no morto)
    if P["crack"] and v in (1, 3):
        x, y = 4 + int(hsh(0, 6, s) * 10), 8 + int(hsh(0, 7, s) * 14)
        for i in range(11 + v):
            cv.px(x, y, C(P["crack"]), wrap=True)
            if i % 4 == 2:
                cv.px(x, y + 1, C(P["dot"]), wrap=True)
            x += 1
            r = hsh(i, 8, s)
            y += 1 if r < 0.3 else -1 if r < 0.6 else 0
    # pedrinhas
    for i in range(1 + (v % 3)):
        w = 3 + int(hsh(i, 9, s) * 3)
        ax, ay = 3 + int(hsh(i, 10, s) * (T - w - 6)), 3 + int(hsh(i, 11, s) * 24)
        cv.rect(ax, ay + 2, w, 1, C(P["dot"]))
        cv.rect(ax, ay, w, 2, C(P["peb"]))
        cv.rect(ax, ay, 2, 1, C(P["pebHi"]))
    # grama no verde
    if "grass" in P:
        for i in range(2 + v % 2 + (1 if v == 0 else 0)):
            gx, gy = 2 + int(hsh(i, 12, s) * 24), 7 + int(hsh(i, 13, s) * 22)
            for b in range(4):
                bh = 2 + int(hsh(i * 4 + b, 14, s) * 4)
                col = C(P["grass"]) if b % 2 == 0 else C(P["grass2"])
                cv.rect(gx + b * 2 - (b == 3), gy - bh, 1, bh, col)
            cv.rect(gx - 1, gy, 9, 1, C(P["patch"]))
    return cv


def boulder_mask(cx, cy, rx, ry, s) -> np.ndarray:
    """Máscara 32x32 (no toro) de uma pedra irregular: união de 2 elipses."""
    ox, oy = (hsh(s, 1, 3) - 0.5) * rx, (hsh(s, 2, 3) - 0.5) * ry * 0.7
    rx2, ry2 = rx * (0.55 + hsh(s, 3, 3) * 0.3), ry * (0.6 + hsh(s, 4, 3) * 0.35)
    ys, xs = np.mgrid[0:T, 0:T] + 0.5
    m = np.zeros((T, T), bool)
    for dx in (-T, 0, T):
        for dy in (-T, 0, T):
            X, Y = xs + dx, ys + dy
            m |= ((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 <= 1
            m |= ((X - cx - ox) / rx2) ** 2 + ((Y - cy - oy) / ry2) ** 2 <= 1
    return m


def paint_boulder(cv: Canvas, m: np.ndarray, P, alt, moss=False, s=0):
    up = np.roll(m, 1, 0)       # pixel de cima está dentro?
    down = np.roll(m, -1, 0)
    left = np.roll(m, 1, 1)
    right = np.roll(m, -1, 1)
    cast = up & ~m              # sombra projetada 1 px abaixo
    cv.a[cast] = C(P["rockDot"])
    body = C(P["rock2"] if alt else P["rock"])
    cv.a[m] = body
    cv.a[m & ~np.roll(m, 2, 0) & up & left] = C(P["rock2"]) if not alt else C(P["rockHi"])
    cv.a[m & (~up | ~left)] = C(P["rockHi"])
    cv.a[m & (~down | ~right)] = C(P["rockDot"])
    if moss:
        top = m & ~up & down
        ys, xs = np.nonzero(top)
        if len(xs):
            order = np.argsort(xs)
            for j, i in enumerate(order[1:-1]):
                x, y = xs[i], ys[i]
                cv.px(x, y, C(P["moss2"] if j < 2 else P["moss"]), wrap=True)
                cv.px(x, y + 1, C(P["moss"] if j % 3 else P["mossD"]), wrap=True)


def make_wall(stage: str, v: int) -> Canvas:
    P, seed = STAGES[stage], STAGE_SEED[stage]
    cv = Canvas(T, T)
    cv.rect(0, 0, T, T, C(P["rock"]))
    s = seed * 1000 + v * 13 + 5
    # granulado de fundo (periódico: emenda com qualquer vizinho)
    n = tile_noise(seed + 50, v, cells=8)
    cv.a[n > 0.7] = C(P["rock2"])
    cv.a[n < 0.2] = C(P["rockDot"])
    green = "moss" in P
    # pedras que atravessam a borda: dependem só do estágio (iguais em todas as variações),
    # então qualquer variação encosta em qualquer outra sem costura
    shared = [(0, 0, 6.5, 4.6), (0, 17, 5.2, 4.2), (17, 0, 6.0, 4.0)]
    for i, (cx, cy, rx, ry) in enumerate(shared):
        paint_boulder(cv, boulder_mask(cx, cy, rx, ry, seed * 7 + i), P, i % 2, green and i == 1, i)
    # pedras do miolo: mudam por variação e ficam longe da borda
    slots = [(10, 9), (23, 10), (11, 23), (24, 23), (17, 16)]
    for k, (bx, by) in enumerate(slots):
        if k == 4 and hsh(k, 9, s) < 0.5:
            continue
        rx = 3.6 + hsh(k, 8, s) * 2.2
        ry = 2.8 + hsh(k, 10, s) * 1.4
        cx = bx + (hsh(k, 6, s) - 0.5) * 3
        cy = by + (hsh(k, 7, s) - 0.5) * 3
        cx = min(max(cx, 4 + rx), 28 - rx)
        cy = min(max(cy, 4 + ry), 27 - ry)
        m = boulder_mask(cx, cy, rx, ry, s + k * 17)
        m[:3, :] = m[-3:, :] = False
        m[:, :3] = m[:, -3:] = False
        paint_boulder(cv, m, P, (k + v) % 2, green and hsh(k, 11, s) < 0.5)
    for i in range(4):
        cv.px(4 + int(hsh(i, 5, s) * 24), 4 + int(hsh(i, 6, s) * 24), C(P["rockHi"]))
    return cv


def make_face(stage: str) -> Canvas:
    P, seed = STAGES[stage], STAGE_SEED[stage]
    cv = Canvas(T, 12)
    cv.rect(0, 0, T, 12, C(P["face"]))
    cv.rect(0, 0, T, 1, C(P["faceHi"]))
    cv.rect(0, 1, T, 1, C(P["faceMid"]))
    cv.rect(0, 10, T, 2, C(P["faceDark"]))
    # estrato horizontal claro e quebrado
    for x in range(T):
        if hsh(x, 0, seed) < 0.55:
            cv.px(x, 5, C(P["faceMid"]))
    # rachaduras verticais
    for cx, top, ln in ((5, 2, 6), (17, 3, 7), (26, 2, 4)):
        for y in range(top, top + ln):
            cv.px(cx + (1 if y > top + 3 else 0), y, C(P["faceDark"]))
    cv.rect(10, 7, 3, 1, C(P["faceDark"]))
    cv.rect(22, 4, 2, 1, C(P["faceDark"]))
    cv.px(13, 3, C(P["faceHi"]))
    cv.px(29, 7, C(P["faceHi"]))
    if "moss" in P:
        for x, ln in ((3, 4), (4, 6), (12, 3), (20, 5), (21, 2), (28, 4)):
            cv.rect(x, 0, 1, ln, C(P["moss"]))
            cv.px(x, ln - 1, C(P["moss2"]))
        cv.rect(2, 0, 5, 1, C(P["moss2"]))
        cv.rect(19, 0, 4, 1, C(P["moss2"]))
    return cv


def make_water(stage: str) -> Canvas:
    """Água: base lisa, ondinhas escuras curtas e reflexos claros. Tudo com wrap (emenda em si mesma)."""
    P = STAGES[stage]
    cv = Canvas(T, T)
    cv.rect(0, 0, T, T, C(P["water"]))
    # ondas escuras em arco, desencontradas
    for x, y, w in ((2, 3, 5), (18, 1, 4), (10, 9, 6), (26, 12, 5), (4, 17, 4), (16, 20, 6), (27, 25, 4), (8, 28, 5)):
        cv.rect(x + 1, y, w - 2, 1, C(P["waterD"]), wrap=True)
        cv.px(x, y - 1, C(P["waterD"]), wrap=True)
        cv.px(x + w - 1, y - 1, C(P["waterD"]), wrap=True)
    # reflexos
    for x, y, w in ((22, 6, 5), (3, 11, 4), (12, 15, 3), (23, 18, 4), (14, 26, 5), (1, 23, 3)):
        cv.rect(x, y, w, 1, C(P["waterHi"]), wrap=True)
    for x, y in ((29, 9), (8, 6), (20, 29)):
        cv.px(x, y, C(P["foam"]), wrap=True)
    return cv


# ---------------------------------------------------------------- minérios e ícones

def crystal(cv: Canvas, x, yb, w, h, O, kind="point"):
    """Cristal com ponta, base em yb (exclusivo). Luz em cima/esquerda, sombra embaixo/direita."""
    hi, li, mi, dk = C(O["hi"]), C(O["light"]), C(O["mid"]), C(O["dark"])
    if kind == "cube":
        top = yb - h
        cv.rect(x, top, w, h, mi)
        cv.rect(x, top, w, 2, li)
        cv.rect(x, top, w - 1, 1, hi)
        cv.rect(x, top, 1, h - 1, li)
        cv.rect(x + w - 1, top + 1, 1, h - 1, dk)
        cv.rect(x + 1, yb - 1, w - 1, 1, dk)
        cv.px(x + 1, top + 2, hi)
        return
    c = (w - 1) / 2
    slope = (h * 0.45) / max(1, c) if kind == "point" else 0.6
    for i in range(w):
        tip = int(round(abs(i - c) * slope))
        top = yb - h + tip
        for y in range(top, yb):
            if i < c - 0.01:
                col = li
            elif i > c + 0.01:
                col = dk if i >= w - 1 or i > c + 1 else mi
            else:
                col = mi
            if y == top:
                col = hi if i <= c else li
            cv.px(x + i, y, col)
    cv.px(x, yb - h + int(round(c * slope)) + 1, hi)


def gem(cv: Canvas, x, yb, w, h, O, kind="point", line=None):
    """Um cristal com contorno próprio, colado por cima (de trás pra frente = contorno separa os cristais)."""
    tmp = Canvas(cv.w, cv.h)
    crystal(tmp, x, yb, w, h, O, kind)
    tmp.outline(C(line or O["line"]))
    cv.paste(tmp, 0, 0)


ORE_LAYOUT = {
    # (x, base_y, w, h, tipo), de trás pra frente. Cachos no topo visível (y<20) e um embaixo,
    # que fica bonito tanto na rocha quanto por cima da face.
    "iron": [(5, 13, 7, 8, "point"), (11, 15, 6, 6, "point"), (2, 16, 5, 4, "point"),
             (19, 10, 6, 6, "point"), (24, 12, 5, 5, "point"),
             (17, 26, 8, 8, "point"), (23, 28, 5, 5, "point"), (14, 28, 4, 4, "point")],
    "silicon": [(5, 15, 4, 11, "point"), (9, 16, 3, 7, "point"), (2, 17, 3, 5, "point"),
                (21, 13, 4, 10, "point"), (25, 14, 3, 6, "point"),
                (15, 27, 5, 12, "point"), (20, 28, 3, 6, "point"), (12, 28, 3, 5, "point")],
    "ice": [(4, 13, 7, 7, "cube"), (10, 16, 6, 6, "cube"), (2, 17, 4, 4, "cube"),
            (20, 11, 7, 7, "cube"), (25, 13, 4, 4, "cube"),
            (15, 27, 8, 8, "cube"), (22, 28, 5, 5, "cube")],
}


def make_ore(name: str) -> Canvas:
    O = ORES[name]
    cv = Canvas(T, T)
    for x, yb, w, h, k in ORE_LAYOUT[name]:
        gem(cv, x, yb, w, h, O, k)
    for x, y in ((28, 4), (13, 5), (6, 23)):
        cv.px(x, y, C(O["hi"]))
    return cv


def make_icon(name: str) -> Canvas:
    O = ORES[name]
    cv = Canvas(16, 16)
    if name == "iron":
        gem(cv, 4, 12, 8, 10, O, line=INK)
        gem(cv, 1, 15, 6, 6, O, line=INK)
        gem(cv, 9, 15, 6, 7, O, line=INK)
    elif name == "silicon":
        gem(cv, 5, 13, 6, 12, O, line=INK)
        gem(cv, 1, 15, 4, 8, O, line=INK)
        gem(cv, 10, 15, 4, 9, O, line=INK)
    else:
        gem(cv, 4, 8, 8, 7, O, "cube", line=INK)
        gem(cv, 1, 15, 7, 7, O, "cube", line=INK)
        gem(cv, 8, 15, 7, 7, O, "cube", line=INK)
    return cv


# ---------------------------------------------------------------- personagem

PAL_PLAYER = {"k": INK, "w": "#ece8e0", "g": "#b9b2a8", "o": "#e2733a", "O": "#a8471f",
              "c": "#59d0e6", "C": "#2b7f99", "h": "#d8fbff", "d": "#3b3f46", "s": "#6b717a"}
PLAYER = [
    "......kkkkkkk.......",
    "....kkwwwwwwwkk.....",
    "...kwwwwwwwwwwwk....",
    "..kwwwwwwwwwwhwwk...",
    "..kwwwwwwkkkkkkkk...",
    ".kwwwwwwkcccchhhck..",
    ".kgwwwwwkccccchhck..",
    ".kgwwwwwkcccccccck..",
    ".kggwwwwkCcccccccck.",
    ".kggwwwwkCCCcccccck.",
    "..kggwwwwkkkkkkkkk..",
    "...kkgggwwwwwwkk....",
    ".kkkkkgwwwwwwwwk....",
    "kOooOkgwwwwwwwwwk...",
    "kOooOkggwwwwwwwwwk..",
    "kOooOkggwwwwwccwwk..",
    "kOooOkggwwwwwccwdk..",
    "kOooOkgggwwwwwwwddk.",
    "kOOOOkgggooooooodk..",
    ".kkkkkggwwwwwwwwk...",
    ".....kggwwwwwwwwk...",
    ".....kggwwwkgwwwk...",
    ".....kggwwk.kgwwk...",
    ".....kggwwk.kgwwk...",
    ".....kgwwwk.kgwwk...",
    ".....kddddk.kdddk...",
    ".....kddddk.kddddk..",
    "....kdddddk.kddddk..",
    "....ksssssk.kssssk..",
    "....kkkkkkk.kkkkkk..",
]
UPPER = PLAYER[:21]  # cabeça, tronco e quadril (linhas 0..20)

# pernas dos quadros de caminhada: contato = corpo 1 px abaixo, pernas em 8 linhas (22..29)
LEGS_CONTACT_A = [  # perna de trás (longe) atrás, perna da frente adiante
    "....kggwwk.kgwwk....",
    "...kggwwk...kgwwk...",
    "...kggwk....kgwwwk..",
    "..kggwk......kgwwk..",
    "..kdddk......kddddk.",
    ".kdddk.......kddddk.",
    ".ksssk.......kssssk.",
    ".kkkkk.......kkkkkk.",
]
LEGS_PASS_1 = [  # passagem: perna de trás sobe
    ".....kggwwwkgwwwk...",
    ".....kggwwk.kgwwk...",
    "......kggwk.kgwwk...",
    "......kddddkkgwwk...",
    "......kddddkkdddk...",
    "......ksssskkddddk..",
    "......kkkkkkkddddk..",
    "............kssssk..",
    "............kkkkkk..",
]
LEGS_CONTACT_B = [  # trocou: a de trás foi pra frente
    "....kgwwwk.kggwk....",
    "...kgwwwk...kggwk...",
    "...kgwwk....kggwwk..",
    "..kgwwk......kggwk..",
    "..kddddk.....kdddk..",
    ".kddddk......kddddk.",
    ".kssssk......kssssk.",
    ".kkkkkk......kkkkkk.",
]
LEGS_PASS_2 = [  # passagem: perna da frente sobe
    ".....kggwwwkgwwwk...",
    ".....kggwwkkgwwk....",
    ".....kggwwkkgwwk....",
    ".....kgwwwkkddddk...",
    ".....kddddkkddddk...",
    ".....kddddkkssssk...",
    ".....kddddkkkkkkk...",
    "....ksssssk.........",
    "....kkkkkkk.........",
]


def make_player() -> Canvas:
    cv = Canvas(20, 30)
    cv.draw_map(PLAYER, PAL_PLAYER)
    return cv


def make_walk() -> Canvas:
    sheet = Canvas(80, 30)
    frames = [(1, LEGS_CONTACT_A, 22), (0, LEGS_PASS_1, 21), (1, LEGS_CONTACT_B, 22), (0, LEGS_PASS_2, 21)]
    for f, (bob, legs, ly) in enumerate(frames):
        fr = Canvas(20, 30)
        fr.draw_map(legs, PAL_PLAYER, 0, ly)
        fr.draw_map(UPPER, PAL_PLAYER, 0, bob)
        # mochila balança: no contato desce junto com o corpo (já incluso); na passagem o braço fica
        sheet.paste(fr, f * 20, 0)
    return sheet


# ---------------------------------------------------------------- cápsula

def make_pod() -> Canvas:
    W, H = 64, 72
    cv = Canvas(W, H)
    x, y = 0, 69
    cv.ellipse(32, 68.5, 31, 3.5, SHADOW)
    # pés e pernas de pouso
    for lx in (1, 53):
        cv.rect(lx, y - 5, 10, 3, C("#2a2d33"))
        cv.rect(lx, y - 5, 10, 1, C("#4a4f57"))
    for lx in (4, 56):
        cv.rect(lx, y - 16, 4, 11, C("#3b3f46"))
        cv.rect(lx, y - 16, 1, 11, C("#5a6069"))
        cv.rect(lx + 3, y - 16, 1, 11, C("#2a2d33"))
    # casco (cilindro em faixas)
    cv.rect(x + 5, y - 49, 54, 38, C("#22272e"))
    cv.bands(x + 6, y - 48, 36, [("#f4f6f8", 4), ("#e1e5ea", 20), ("#c8cdd4", 16), ("#abb2bb", 8), ("#8c949e", 4)])
    for i, n in enumerate([14, 10, 7, 5, 3, 1]):  # cúpula
        yy = y - 54 + i
        cv.rect(x + 5 + n, yy, 54 - 2 * n, 1, C("#22272e"))
        if i > 0:
            cv.rect(x + 6 + n, yy, 52 - 2 * n, 1, C("#eef1f4" if i < 3 else "#e1e5ea"))
            cv.rect(x + 6 + n + (52 - 2 * n) * 3 // 4, yy, (52 - 2 * n) // 4, 1, C("#c8cdd4"))
    cv.rect(x + 6, y - 38, 52, 1, C("#abb2bb"))
    # faixa laranja
    cv.rect(x + 6, y - 30, 52, 4, C("#e2733a"))
    cv.rect(x + 6, y - 30, 52, 1, C("#f29a62"))
    cv.rect(x + 6, y - 26, 52, 1, C("#a8471f"))
    cv.rect(x + 46, y - 29, 12, 2, C("#c45a28"))
    # rodapé escuro do casco
    cv.rect(x + 6, y - 13, 52, 1, C("#8c949e"))
    cv.rect(x + 6, y - 12, 52, 1, C("#6b717a"))
    # janela
    cv.rect(x + 11, y - 47, 18, 12, C("#22272e"))
    cv.rect(x + 12, y - 46, 16, 10, C("#2b7f99"))
    cv.rect(x + 12, y - 46, 12, 8, C("#59d0e6"))
    cv.rect(x + 14, y - 45, 3, 1, C("#d8fbff"))
    cv.rect(x + 14, y - 44, 1, 2, C("#d8fbff"))
    cv.px(x + 19, y - 45, C("#d8fbff"))
    # porta
    cv.rect(x + 35, y - 25, 16, 14, C("#22272e"))
    cv.rect(x + 36, y - 24, 14, 13, C("#34444f"))
    cv.rect(x + 36, y - 24, 14, 1, C("#4a5f6d"))
    cv.rect(x + 42, y - 24, 1, 13, C("#22303a"))
    cv.rect(x + 39, y - 18, 2, 2, C("#e2733a"))
    cv.rect(x + 44, y - 18, 2, 2, C("#e2733a"))
    # degrau
    cv.rect(x + 34, y - 11, 18, 2, C("#3b3f46"))
    cv.rect(x + 34, y - 11, 18, 1, C("#6b717a"))
    # grade de ventilação
    for i in range(3):
        cv.rect(x + 12, y - 22 + i * 3, 14, 1, C("#8c949e"))
        cv.rect(x + 12, y - 21 + i * 3, 14, 1, C("#e1e5ea"))
    # painel com marcação
    cv.rect(x + 34, y - 46, 18, 4, C("#8c949e"))
    cv.rect(x + 34, y - 46, 4, 4, C("#e2733a"))
    cv.rect(x + 39, y - 45, 11, 1, C("#c8cdd4"))
    # rebites
    for rx in (8, 30, 55):
        cv.px(x + rx, y - 34, C("#8c949e"))
        cv.px(x + rx, y - 17, C("#8c949e"))
    # antena
    cv.rect(x + 50, y - 66, 1, 14, C("#6b717a"))
    cv.rect(x + 47, y - 58, 7, 1, C("#6b717a"))
    cv.rect(x + 49, y - 69, 3, 3, C("#ff5a4a"))
    cv.px(x + 49, y - 69, C("#ffb3a8"))
    return cv


# ---------------------------------------------------------------- máquinas

def gauge(cv, x, y, w=8, h=6, needle_x=3):
    cv.rect(x, y, w, h, C("#e9e5dd"))
    cv.rect(x, y, w, 1, C(INK))
    cv.rect(x, y + h - 1, w, 1, C("#b9b2a8"))
    cv.rect(x + needle_x, y + 2, 1, h - 3, C("#c2281c"))


def hazard(cv, x, y, n, a=GOLD, b=INK):
    for i in range(n):
        cv.rect(x + i * 2, y, 2, 2, C(a if i % 2 == 0 else b))


def m_o2(level: int) -> Canvas:
    if level == 1:
        cv = Canvas(40, 56)
        x, y = 4, 53
        cv.ellipse(20, 53, 17, 3, SHADOW)
        # base
        cv.rect(x, y - 11, 32, 10, C("#151a20"))
        cv.rect(x + 1, y - 10, 30, 8, C("#2b3440"))
        cv.rect(x + 1, y - 10, 30, 2, C("#3d4856"))
        cv.rect(x + 1, y - 3, 30, 1, C("#202730"))
        cv.rect(x + 3, y - 7, 2, 2, C("#8a96a3"))
        cv.rect(x + 27, y - 7, 2, 2, C("#8a96a3"))
        # tanque
        cv.rect(x + 5, y - 45, 22, 35, C("#14202b"))
        cv.rect(x + 7, y - 47, 18, 2, C("#14202b"))
        cv.bands(x + 6, y - 44, 34, [("#9ad9f7", 2), ("#64b7e8", 6), ("#3f91c6", 7), ("#2d70a0", 3), ("#1f5379", 2)])
        cv.rect(x + 8, y - 46, 16, 2, C("#2d70a0"))
        cv.rect(x + 9, y - 46, 8, 1, C("#64b7e8"))
        for ry in (y - 33, y - 20):
            cv.rect(x + 6, ry, 20, 2, C("#1b3448"))
            cv.rect(x + 6, ry, 20, 1, C("#2a4c66"))
        cv.rect(x + 8, y - 42, 1, 7, C("#d4f1ff"))
        gauge(cv, x + 12, y - 29, 8, 6, 3)
        # topo
        cv.rect(x + 13, y - 49, 6, 2, C("#6b717a"))
        cv.rect(x + 12, y - 52, 8, 3, C("#e2733a"))
        cv.rect(x + 12, y - 52, 8, 1, C("#f29a62"))
        cv.rect(x + 12, y - 50, 8, 1, C("#a8471f"))
        # cano lateral
        cv.rect(x + 27, y - 26, 4, 2, C("#6b717a"))
        cv.rect(x + 29, y - 26, 2, 15, C("#6b717a"))
        cv.rect(x + 30, y - 24, 1, 13, C("#4a4f57"))
        cv.rect(x + 4, y - 14, 2, 2, C("#7fd67a"))
        return cv
    # nível 2: tanque mais largo, 2 tanques auxiliares, anéis dourados
    cv = Canvas(40, 64)
    y = 61
    cv.ellipse(20, 61, 19.5, 3, SHADOW)
    cv.rect(0, y - 13, 40, 12, C("#151a20"))
    cv.rect(1, y - 12, 38, 10, C("#2b3440"))
    cv.rect(1, y - 12, 38, 2, C("#3d4856"))
    cv.rect(1, y - 13, 38, 1, C(GOLD))
    cv.rect(1, y - 3, 38, 1, C("#202730"))
    hazard(cv, 3, y - 7, 6)
    hazard(cv, 25, y - 7, 6)
    for bx in (2, 37):
        cv.rect(bx, y - 9, 1, 1, C("#8a96a3"))
    # tanques auxiliares
    for tx in (1, 31):
        cv.rect(tx, y - 33, 8, 21, C("#14202b"))
        cv.bands(tx + 1, y - 32, 20, [("#9ad9f7", 1), ("#64b7e8", 2), ("#3f91c6", 2), ("#1f5379", 1)])
        cv.rect(tx + 1, y - 34, 6, 1, C("#14202b"))
        cv.rect(tx + 2, y - 35, 4, 1, C("#6b717a"))
        cv.rect(tx + 1, y - 24, 6, 1, C(GOLD_D))
    # tanque principal
    cv.rect(8, y - 55, 24, 43, C("#14202b"))
    cv.rect(10, y - 57, 20, 2, C("#14202b"))
    cv.bands(9, y - 54, 42, [("#9ad9f7", 2), ("#64b7e8", 7), ("#3f91c6", 7), ("#2d70a0", 3), ("#1f5379", 3)])
    cv.rect(11, y - 56, 18, 2, C("#2d70a0"))
    cv.rect(12, y - 56, 9, 1, C("#64b7e8"))
    cv.rect(11, y - 52, 1, 9, C("#d4f1ff"))
    for ry in (y - 45, y - 25):
        cv.bands(9, ry, 2, [(GOLD_L, 2), (GOLD, 12), (GOLD_D, 8)])
        cv.rect(9, ry + 2, 22, 1, C("#5e4a26"))
    gauge(cv, 14, y - 38, 12, 8, 5)
    cv.rect(15, y - 33, 10, 1, C("#d9d3c8"))
    # topo com dois bocais
    cv.rect(12, y - 59, 16, 2, C("#6b717a"))
    for nx in (12, 22):
        cv.rect(nx, y - 63, 6, 4, C("#e2733a"))
        cv.rect(nx, y - 63, 6, 1, C("#f29a62"))
        cv.rect(nx, y - 60, 6, 1, C("#a8471f"))
        cv.rect(nx + 1, y - 62, 4, 1, C(GOLD))
    # luzes de status
    cv.rect(10, y - 16, 2, 2, C("#7fd67a"))
    cv.rect(28, y - 16, 2, 2, C("#59d0e6"))
    return cv


def m_heater(level: int) -> Canvas:
    glow = ["#ffd27a", "#ff9a3d", "#ffd27a", "#e0602a", "#ff9a3d"]
    if level == 1:
        cv = Canvas(40, 56)
        x, y = 4, 53
        cv.ellipse(20, 53, 17, 3, SHADOW)
        cv.rect(x + 5, y - 4, 5, 4, C("#2a1712"))
        cv.rect(x + 22, y - 4, 5, 4, C("#2a1712"))
        cv.rect(x + 2, y - 36, 28, 33, C(INK))
        cv.bands(x + 3, y - 35, 31, [("#8a6050", 3), ("#6a4538", 14), ("#5a3a2f", 6), ("#462c24", 3)])
        cv.rect(x + 2, y - 38, 28, 3, C("#9a7060"))
        cv.rect(x + 2, y - 38, 28, 1, C("#b58a78"))
        cv.rect(x + 2, y - 35, 28, 1, C(INK))
        for i in range(4):
            cv.rect(x + 7, y - 30 + i * 5, 18, 4, C("#1d0f0b"))
            cv.rect(x + 8, y - 29 + i * 5, 16, 2, C(glow[i]))
            cv.rect(x + 8, y - 29 + i * 5, 3, 1, C("#fff0c0"))
        hazard(cv, x + 3, y - 8, 13)
        # chaminé
        cv.rect(x + 20, y - 47, 7, 10, C(INK))
        cv.rect(x + 21, y - 46, 5, 9, C("#4a3a34"))
        cv.rect(x + 21, y - 46, 1, 9, C("#6b5a52"))
        cv.rect(x + 19, y - 48, 9, 2, C("#6b5a52"))
        cv.rect(x + 19, y - 48, 9, 1, C("#8a7a72"))
        return cv
    cv = Canvas(40, 64)
    y = 61
    cv.ellipse(20, 61, 19.5, 3, SHADOW)
    for fx in (3, 15, 29):
        cv.rect(fx, y - 4, 8, 4, C("#2a1712"))
        cv.rect(fx, y - 4, 8, 1, C("#4a2d22"))
    cv.rect(1, y - 46, 38, 43, C(INK))
    cv.bands(2, y - 45, 41, [("#8a6050", 4), ("#6a4538", 18), ("#5a3a2f", 9), ("#462c24", 5)])
    cv.rect(1, y - 49, 38, 3, C("#9a7060"))
    cv.rect(1, y - 49, 38, 1, C("#b58a78"))
    cv.rect(1, y - 46, 38, 1, C(GOLD))
    cv.rect(1, y - 45, 38, 1, C(INK))
    for i in range(5):
        cv.rect(6, y - 41 + i * 6, 28, 5, C("#1d0f0b"))
        cv.rect(7, y - 40 + i * 6, 26, 3, C(glow[i]))
        cv.rect(7, y - 40 + i * 6, 4, 1, C("#fff0c0"))
        cv.rect(19, y - 40 + i * 6, 2, 3, C("#1d0f0b"))
    # colunas laterais douradas
    for cx in (2, 35):
        cv.rect(cx, y - 44, 3, 33, C(GOLD_D))
        cv.rect(cx, y - 44, 1, 33, C(GOLD))
    hazard(cv, 2, y - 10, 18)
    # chaminés gêmeas
    for cx in (6, 26):
        cv.rect(cx, y - 60, 8, 11, C(INK))
        cv.rect(cx + 1, y - 59, 6, 10, C("#4a3a34"))
        cv.rect(cx + 1, y - 59, 1, 10, C("#6b5a52"))
        cv.rect(cx - 1, y - 62, 10, 3, C("#6b5a52"))
        cv.rect(cx - 1, y - 62, 10, 1, C("#8a7a72"))
        cv.rect(cx - 1, y - 60, 10, 1, C(GOLD_D))
    return cv


def m_melter(level: int) -> Canvas:
    ice = ORES["ice"]
    if level == 1:
        cv = Canvas(40, 56)
        x, y = 4, 53
        cv.ellipse(18, 53, 16, 3, SHADOW)
        cv.ellipse(36, 53, 4, 2, C("#3d6f86"))
        cv.rect(35, 52, 2, 1, C("#6fb4d0"))
        cv.rect(x + 3, y - 25, 26, 24, C(INK))
        cv.bands(x + 4, y - 24, 22, [("#6f8696", 3), ("#4f6370", 13), ("#3e4f5a", 5), ("#2b3740", 3)])
        cv.rect(x + 4, y - 3, 24, 1, C("#232d34"))
        for i in range(8):
            col = INK if i == 0 else "#8aa2b2" if i < 3 else "#64798a"
            cv.rect(x + i, y - 33 + i, 32 - 2 * i, 1, C(col))
        cv.rect(x, y - 34, 32, 1, C(INK))
        # gelo no funil
        cub = Canvas(40, 56)
        crystal(cub, x + 6, y - 34, 7, 7, ice, "cube")
        crystal(cub, x + 23, y - 33, 6, 6, ice, "cube")
        crystal(cub, x + 14, y - 36, 8, 8, ice, "cube")
        cub.outline(C(ice["line"]))
        cv.paste(cub, 0, 0)
        # visor de nível
        cv.rect(x + 9, y - 21, 7, 15, C("#14202b"))
        cv.rect(x + 10, y - 17, 5, 10, C("#4aa8d8"))
        cv.rect(x + 10, y - 17, 5, 1, C("#9fe0f5"))
        # cano e gota
        cv.rect(x + 28, y - 14, 5, 3, C("#6b717a"))
        cv.rect(x + 31, y - 14, 2, 7, C("#6b717a"))
        cv.rect(x + 32, y - 13, 1, 6, C("#4a4f57"))
        cv.rect(x + 31, y - 5, 2, 2, C("#6fc9ef"))
        cv.rect(x + 20, y - 18, 4, 2, C("#7fd67a"))
        return cv
    cv = Canvas(40, 64)
    y = 61
    cv.ellipse(17, 61, 17, 3, SHADOW)
    cv.ellipse(35, 61, 5, 2, C("#3d6f86"))
    cv.rect(33, 60, 3, 1, C("#6fb4d0"))
    # corpo
    cv.rect(1, y - 33, 32, 32, C(INK))
    cv.bands(2, y - 32, 30, [("#6f8696", 3), ("#4f6370", 17), ("#3e4f5a", 7), ("#2b3740", 3)])
    cv.rect(2, y - 3, 30, 1, C("#232d34"))
    for ry in (y - 30, y - 12):
        cv.bands(2, ry, 2, [(GOLD_L, 2), (GOLD, 18), (GOLD_D, 10)])
    # funil maior com aro dourado
    for i in range(9):
        col = INK if i == 0 else "#8aa2b2" if i < 3 else "#64798a"
        cv.rect(i, y - 43 + i, 34 - 2 * i, 1, C(col))
    cv.rect(0, y - 44, 34, 1, C(GOLD))
    cv.rect(0, y - 45, 34, 1, C(GOLD_D))
    cub = Canvas(40, 64)
    crystal(cub, 3, y - 44, 7, 7, ice, "cube")
    crystal(cub, 25, y - 44, 7, 7, ice, "cube")
    crystal(cub, 9, y - 47, 8, 8, ice, "cube")
    crystal(cub, 18, y - 46, 8, 9, ice, "cube")
    crystal(cub, 13, y - 54, 7, 7, ice, "cube")
    cub.outline(C(ice["line"]))
    cv.paste(cub, 0, 0)
    # dois visores
    for vx, lv in ((6, 12), (15, 8)):
        cv.rect(vx, y - 27, 7, 20, C("#14202b"))
        cv.rect(vx + 1, y - 8 - lv, 5, lv, C("#4aa8d8"))
        cv.rect(vx + 1, y - 8 - lv, 5, 1, C("#9fe0f5"))
    gauge(cv, 24, y - 26, 7, 6, 4)
    cv.rect(25, y - 17, 2, 2, C("#7fd67a"))
    cv.rect(28, y - 17, 2, 2, C("#7fd67a"))
    # cano
    cv.rect(32, y - 16, 6, 3, C("#6b717a"))
    cv.rect(35, y - 16, 3, 9, C("#6b717a"))
    cv.rect(37, y - 15, 1, 8, C("#4a4f57"))
    cv.rect(35, y - 13, 3, 1, C(GOLD))
    cv.rect(36, y - 6, 2, 2, C("#6fc9ef"))
    return cv


# ---------------------------------------------------------------- terminal e plantas

def make_terminal() -> Canvas:
    cv = Canvas(32, 32)
    cv.rect(4, 4, 24, 25, C("#120d0f"))           # recorte na rocha
    cv.rect(5, 5, 22, 22, C(INK))
    cv.rect(6, 6, 20, 20, C("#3a3f3c"))
    cv.rect(6, 6, 20, 1, C("#4e5551"))
    cv.rect(6, 6, 1, 20, C("#4e5551"))
    cv.rect(25, 7, 1, 19, C("#2a2e2c"))
    cv.rect(8, 8, 16, 12, C("#0d1a15"))
    for i, w in enumerate((12, 9, 13, 6)):
        cv.rect(9, 9 + i * 3, w, 1, C("#6fe3a0"))
    cv.rect(17, 17, 3, 2, C("#6fe3a0"))
    cv.rect(8, 8, 16, 1, C("#16291f"))
    cv.rect(8, 22, 16, 2, C("#5a605c"))
    cv.rect(22, 22, 2, 2, C("#e2733a"))
    cv.rect(9, 22, 2, 2, C("#3a3f3c"))
    cv.rect(5, 27, 22, 2, C("#2a2e2c"))          # parafusos/suporte
    cv.px(7, 27, C("#5a605c"))
    cv.px(24, 27, C("#5a605c"))
    return cv


def make_bush() -> Canvas:
    cv = Canvas(24, 18)
    cx, y = 12, 16
    cv.ellipse(cx, y, 11, 2.5, SHADOW)
    cv.disc(cx - 4, y - 6, 6, C("#1d4224"))
    cv.disc(cx + 4, y - 6, 6, C("#1d4224"))
    cv.disc(cx, y - 9, 6, C("#1d4224"))
    cv.disc(cx - 4, y - 7, 5, C("#2f6a33"))
    cv.disc(cx + 3, y - 7, 5, C("#2f6a33"))
    cv.disc(cx, y - 10, 5, C("#2f6a33"))
    cv.disc(cx - 3, y - 11, 3, C("#4a8f45"))
    cv.disc(cx + 4, y - 8, 2, C("#4a8f45"))
    cv.rect(cx - 4, y - 13, 2, 1, C("#7cc45e"))
    cv.px(cx - 5, y - 12, C("#7cc45e"))
    for bx, by in ((cx + 3, y - 10), (cx - 3, y - 6), (cx + 6, y - 5)):
        cv.rect(bx, by, 2, 2, C("#e94f6a"))
        cv.px(bx, by, C("#ff9aa8"))
    return cv


def make_tree() -> Canvas:
    cv = Canvas(32, 40)
    cx, y = 16, 38
    cv.ellipse(cx, y, 12, 2.5, SHADOW)
    cv.rect(cx - 3, y - 17, 6, 17, C("#3d2a1e"))
    cv.rect(cx - 2, y - 17, 3, 17, C("#6b4a33"))
    cv.rect(cx - 2, y - 17, 1, 15, C("#8a6446"))
    cv.rect(cx - 4, y - 1, 2, 1, C("#3d2a1e"))
    cv.rect(cx + 2, y - 1, 3, 1, C("#3d2a1e"))
    for dx, dy, r, c in ((0, -25, 12, "#1a4322"), (-8, -21, 7.5, "#1a4322"), (8, -21, 7, "#1a4322"),
                         (-1, -27, 10, "#2e6a33"), (-6, -23, 6, "#2e6a33"), (6, -23, 6, "#2e6a33"),
                         (-4, -30, 6, "#4a8f45"), (3, -25, 4, "#4a8f45"), (-7, -24, 3, "#4a8f45")):
        cv.disc(cx + dx, y + dy, r, C(c))
    cv.rect(cx - 6, y - 34, 3, 1, C("#7cc45e"))
    cv.rect(cx - 7, y - 33, 1, 2, C("#7cc45e"))
    cv.rect(cx + 2, y - 28, 2, 1, C("#7cc45e"))
    return cv


def make_flower() -> Canvas:
    cv = Canvas(20, 14)
    cv.ellipse(10, 12.5, 8, 1.5, SHADOW)
    for i, (fx, lift, petal) in enumerate(((4, 0, "#f2a3c8"), (10, 3, "#f5d36b"), (16, 1, "#f2a3c8"))):
        fy = 12 - lift
        cv.rect(fx, fy - 5, 1, 5, C("#3f7a34"))
        cv.rect(fx + 1, fy - 3, 2, 1, C("#5c9a43") if i != 1 else C("#3f7a34"))
        cv.rect(fx - 1, fy - 8, 3, 3, C(petal))
        cv.px(fx, fy - 7, C("#fff3c4"))
        cv.px(fx + 1, fy - 6, C("#c97a9a" if petal == "#f2a3c8" else "#c99a3a"))
    cv.rect(1, 12, 3, 1, C("#3f7a34"))
    cv.rect(13, 12, 3, 1, C("#3f7a34"))
    return cv


# ---------------------------------------------------------------- geração de tudo

def build_sprites() -> dict[str, Canvas]:
    out: dict[str, Canvas] = {}
    out["player.png"] = make_player()
    out["player_walk.png"] = make_walk()
    for st in STAGES:
        for v in range(4):
            out[f"floor_{st}_{v}.png"] = make_floor(st, v)
        for v in range(3):
            out[f"wall_{st}_{v}.png"] = make_wall(st, v)
        out[f"wall_face_{st}.png"] = make_face(st)
        out[f"water_{st}.png"] = make_water(st)
    for o in ("iron", "silicon", "ice"):
        out[f"ore_{o}.png"] = make_ore(o)
        out[f"icon_{o}.png"] = make_icon(o)
    out["pod.png"] = make_pod()
    out["machine_o2.png"] = m_o2(1)
    out["machine_heater.png"] = m_heater(1)
    out["machine_melter.png"] = m_melter(1)
    out["machine_o2_t2.png"] = m_o2(2)
    out["machine_heater_t2.png"] = m_heater(2)
    out["machine_melter_t2.png"] = m_melter(2)
    out["terminal.png"] = make_terminal()
    out["plant_bush.png"] = make_bush()
    out["plant_tree.png"] = make_tree()
    out["plant_flower.png"] = make_flower()
    return out


# ---------------------------------------------------------------- cena de prévia (renderer mínimo, como o jogo faria)

GW, GH = 30, 17
FL, RK, FE, SI, IC, WA = 0, 1, 2, 3, 4, 5
BASE_CELLS = [(14, 7), (15, 7), (14, 8), (15, 8), (11, 8), (17, 7), (17, 9), (13, 10), (12, 10), (15, 10),
              (16, 9), (12, 8), (10, 8), (11, 10), (16, 10), (18, 9), (19, 9), (20, 9), (13, 9), (16, 8)]


def gen_world(seed=7):
    g = [[FL] * GW for _ in range(GH)]
    for y in range(GH):
        for x in range(GW):
            n = vnoise(x * 0.35, y * 0.35, seed)
            d = math.hypot((x + 0.5 - 15) / 9.5, (y + 0.5 - 8.5) / 6.0) + (n - 0.5) * 0.55
            t = FL if d < 1 else RK
            if t == RK and vnoise(x * 0.55 + 40, y * 0.55 + 9, seed + 7) > 0.68:
                k = vnoise(x * 0.3 + 90, y * 0.3 + 3, seed + 13)
                t = FE if k < 0.42 else SI if k < 0.62 else IC
            g[y][x] = t
    for x, y in BASE_CELLS:
        g[y][x] = FL
    return g


def add_water(g, seed, thr, keep_r=0.55):
    for y in range(GH):
        for x in range(GW):
            if g[y][x] != FL:
                continue
            if math.hypot((x + 0.5 - 15) / 9, (y + 0.5 - 8.5) / 5.8) < keep_r:
                continue
            if (x, y) in BASE_CELLS:
                continue
            if vnoise(x * 0.32 + 200, y * 0.32 + 50, seed + 21) < thr:
                g[y][x] = WA


def is_wall(t):
    return RK <= t <= IC


def render_scene(stage: str, spr: dict[str, Image.Image]) -> Image.Image:
    seed = 7
    g = gen_world(seed)
    add_water(g, seed, {"dead": 0.16, "mist": 0.3, "green": 0.4}[stage])
    # terminal: uma parede com chão embaixo, na borda esquerda de cima
    term = None
    for y in range(1, GH - 1):
        for x in range(4, 10):
            if is_wall(g[y][x]) and g[y + 1][x] == FL and term is None and y < 7:
                term = (x, y)
                g[y][x] = RK
    img = Image.new("RGBA", (GW * T, GH * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 6), (0, 0, 0, 80))
    shade2 = Image.new("RGBA", (4, T), (0, 0, 0, 40))
    ore_name = {FE: "ore_iron.png", SI: "ore_silicon.png", IC: "ore_ice.png"}
    for y in range(GH):
        for x in range(GW):
            t, px, py = g[y][x], x * T, y * T
            if is_wall(t):
                v = int(hsh(x, y, 91) * 3)
                img.alpha_composite(spr[f"wall_{stage}_{v}.png"], (px, py))
                below = g[y + 1][x] if y + 1 < GH else RK
                if not is_wall(below):
                    img.alpha_composite(spr[f"wall_face_{stage}.png"], (px, py + T - 12))
                if t in ore_name:
                    img.alpha_composite(spr[ore_name[t]], (px, py))
            else:
                if t == WA:
                    img.alpha_composite(spr[f"water_{stage}.png"], (px, py))
                else:
                    v = int(hsh(x, y, 77) * 4)
                    img.alpha_composite(spr[f"floor_{stage}_{v}.png"], (px, py))
                if y > 0 and is_wall(g[y - 1][x]):
                    img.alpha_composite(shade, (px, py))
                if x > 0 and is_wall(g[y][x - 1]):
                    img.alpha_composite(shade2, (px, py))
    if term:
        img.alpha_composite(spr["terminal.png"], (term[0] * T, term[1] * T))

    # objetos ancorados no centro da base, ordenados por y
    objs = []

    def obj(name, ax, ay):
        objs.append((ay, name, ax))

    obj("pod.png", 15 * T, 9 * T)
    if stage == "dead":
        obj("machine_o2.png", 11 * T + 16, 9 * T)
        obj("machine_heater.png", 17 * T + 16, 8 * T)
        obj("machine_melter.png", 17 * T + 16, 10 * T)
        obj("machine_o2.png", 12 * T + 16, 11 * T)
    elif stage == "mist":
        obj("machine_o2_t2.png", 11 * T + 16, 9 * T)
        obj("machine_heater.png", 17 * T + 16, 8 * T)
        obj("machine_melter_t2.png", 17 * T + 16, 10 * T)
        obj("machine_o2.png", 12 * T + 16, 11 * T)
        obj("machine_heater_t2.png", 15 * T + 16, 11 * T)
    else:
        obj("machine_o2_t2.png", 11 * T + 16, 9 * T)
        obj("machine_heater_t2.png", 17 * T + 16, 8 * T)
        obj("machine_melter_t2.png", 17 * T + 16, 10 * T)
        obj("machine_o2_t2.png", 12 * T + 16, 11 * T)
        obj("machine_heater_t2.png", 15 * T + 16, 11 * T)
        occupied = {(11, 8), (17, 7), (17, 9), (12, 10), (15, 10), (14, 7), (15, 7), (14, 8), (15, 8)}
        for y in range(GH):
            for x in range(GW):
                if g[y][x] != FL or (x, y) in occupied:
                    continue
                if math.hypot((x + 0.5 - 15) / 9, (y + 0.5 - 8.5) / 5.8) < 0.55:
                    continue
                if hsh(x, y, 99) < 0.24:
                    k = hsh(x, y, 98)
                    name = "plant_bush.png" if k < 0.4 else "plant_tree.png" if k < 0.68 else "plant_flower.png"
                    obj(name, x * T + 16, y * T + 30)
    # player com sombra (o jogo desenha a sombra)
    pxy = {"dead": (19 * T + 20, 10 * T + 22), "mist": (19 * T + 16, 9 * T + 6), "green": (19 * T + 6, 9 * T + 12)}[stage]
    objs.append((pxy[1], "player", pxy[0]))
    objs.sort(key=lambda o: o[0])
    for ay, name, ax in objs:
        if name == "player":
            sh = Canvas(22, 7)
            sh.ellipse(11, 3.5, 10, 3, SHADOW)
            img.alpha_composite(sh.image(), (ax - 11, ay - 4))
            p = spr["player.png"] if stage != "mist" else spr["player_walk.png"].crop((20, 0, 40, 30))
            if stage == "green":
                p = p.transpose(Image.FLIP_LEFT_RIGHT)
            img.alpha_composite(p, (ax - 10, ay - 30))
            continue
        s = spr[name]
        img.alpha_composite(s, (ax - s.width // 2, ay - s.height))
    return img.crop((0, 0, 960, 540)).convert("RGB")


# ---------------------------------------------------------------- report HTML

GROUPS = [
    ("Personagem", "obj", ["player.png", "player_walk.png"]),
    ("Chão", "tile", [f"floor_{s}_{v}.png" for s in STAGES for v in range(4)]),
    ("Parede (topo) e face", "tile", [f"wall_{s}_{v}.png" for s in STAGES for v in range(3)] + [f"wall_face_{s}.png" for s in STAGES]),
    ("Água", "tile", [f"water_{s}.png" for s in STAGES]),
    ("Minérios (overlay)", "tile", ["ore_iron.png", "ore_silicon.png", "ore_ice.png"]),
    ("Ícones", "icon", ["icon_iron.png", "icon_silicon.png", "icon_ice.png"]),
    ("Cápsula e terminal", "obj", ["pod.png", "terminal.png"]),
    ("Máquinas nv.1", "obj", ["machine_o2.png", "machine_heater.png", "machine_melter.png"]),
    ("Máquinas nv.2", "obj", ["machine_o2_t2.png", "machine_heater_t2.png", "machine_melter_t2.png"]),
    ("Plantas (estágio verde)", "obj", ["plant_bush.png", "plant_tree.png", "plant_flower.png"]),
]

def colors_of(imgs: list[Image.Image]) -> list[str]:
    seen: dict[str, int] = {}
    for im in imgs:
        a = np.array(im)
        m = a[:, :, 3] == 255
        for r, g, b in a[m][:, :3]:
            k = f"#{r:02x}{g:02x}{b:02x}"
            seen[k] = seen.get(k, 0) + 1
    return sorted(seen, key=lambda h: (-seen[h]))


def build_report(spr: dict[str, Image.Image]):
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b

    pal_sets = [
        ("Tiles · morto", [k for k in spr if k.endswith(".png") and "_dead" in k]),
        ("Tiles · névoa", [k for k in spr if "_mist" in k]),
        ("Tiles · verde", [k for k in spr if "_green" in k]),
        ("Minérios e ícones", [k for k in spr if k.startswith(("ore_", "icon_"))]),
        ("Astronauta", ["player.png", "player_walk.png"]),
        ("Cápsula, máquinas e terminal", [k for k in spr if k.startswith(("pod", "machine", "terminal"))]),
        ("Plantas", [k for k in spr if k.startswith("plant_")]),
    ]
    total = set()
    pal_html = []
    for title, names in pal_sets:
        cols = colors_of([spr[n] for n in names])
        total.update(cols)
        sw = "".join(
            f'<li><i style="background:{c}"></i><code>{c}</code></li>' for c in sorted(cols, key=lum)
        )
        pal_html.append(f'<div class="pal"><h3>{title} <span>{len(cols)} cores</span></h3><ul>{sw}</ul></div>')

    scale = {"tile": 4, "obj": 4, "icon": 8}
    groups_html = []
    for title, kind, names in GROUPS:
        cards = []
        for n in names:
            im = spr[n]
            s = scale[kind]
            extra = ""
            if n == "player_walk.png":
                extra = (f'<div class="anim" style="width:{20 * s}px;height:{30 * s}px;'
                         f'background-image:url(../../assets/sprites/{n});background-size:{80 * s}px {30 * s}px"></div>')
            cards.append(
                f'<figure class="spr"><div class="chk">'
                f'<img src="../../assets/sprites/{n}" width="{im.width * s}" height="{im.height * s}" alt="{n}">{extra}</div>'
                f'<figcaption><code>{n}</code><span>{im.width}×{im.height} · {s}×</span></figcaption></figure>'
            )
        groups_html.append(f'<section class="grp"><h2>{title}</h2><div class="cards">{"".join(cards)}</div></section>')

    previews = "".join(
        f'<figure class="pv"><img src="preview_{st}.png" width="960" height="540" alt="Prévia {lab}">'
        f'<figcaption><b>{lab}</b><span>{sub}</span></figcaption></figure>'
        for st, lab, sub in (
            ("dead", "1 · Morto", "máquinas nv.1, poucas poças"),
            ("mist", "2 · Névoa", "nv.1 + nv.2 misturadas, poças maiores, player no quadro 2 da caminhada"),
            ("green", "3 · Primeiro verde", "só nv.2, lagos, arbustos, árvores e flores"),
        )
    )

    notes = [
        ("Tiles sem costura",
         "Chão e água usam ruído periódico de 32 px. Os pontos da borda são iguais em todas as variações do mesmo estágio, então qualquer variação encosta em qualquer outra sem emenda. As pedras da parede ficam dentro do tile (1 px de folga) sobre um fundo granulado que também emenda."),
        ("Paredes",
         "O topo da rocha não tem borda desenhada (borda depende do vizinho, e isso é trabalho do jogo). A face de 32×12 tem lábio claro em cima e pé escuro embaixo, então ela sozinha já separa bem rocha e chão."),
        ("Minério",
         "Cada minério tem uma silhueta própria, além da cor: ferro em cristais baixos e largos, silício em lascas altas, gelo em cubos. Dá pra distinguir até em tela pequena ou pra quem tem daltonismo. Os cristais ficam quase todos nos 20 px de cima; o de baixo também fica bonito por cima da face."),
        ("Astronauta",
         "player.png é o mapa PLAYER do mockup, pixel por pixel. A caminhada usa o mesmo tronco: contato (corpo desce 1 px, pernas abertas), passagem (perna levantada), contato invertido, passagem. Rodar a 8–10 fps."),
        ("Máquinas nv.2",
         "Mesma família das nv.1 (mesmas cores e faixas de cilindro), só que mais largas e altas, com anéis e frisos dourados (#f2c46d) e peças duplicadas: dois bocais no O₂, duas chaminés e cinco fendas no aquecedor, funil maior com dois visores no derretedor."),
        ("Sombras",
         "Pod, máquinas e plantas já trazem a sombra no rodapé do PNG, em preto com 36% de opacidade (um nível só, sem degradê). O player não tem sombra no PNG: o jogo desenha uma elipse 20×6 nos pés, como no mockup."),
        ("Luz e animação",
         "Brilhos, partículas, piscadas e luz ficam por conta do jogo (são cosméticos no MVP). Os sprites vêm no estado 'ligado': luz verde acesa, fendas do aquecedor brilhando."),
    ]
    notes_html = "".join(f"<li><b>{html.escape(a)}.</b> {html.escape(b)}</li>" for a, b in notes)

    integ = [
        "Âncora dos objetos (pod, máquinas, plantas, terminal): centro da base do PNG. Blit em <code>(ax − w/2, ay − h)</code>, com <code>ax</code> = centro do tile e <code>ay</code> = borda de baixo do tile ocupado. O pod tem 64 px e ocupa 2 tiles: <code>ax</code> = linha entre os dois tiles.",
        "Máquinas: nv.1 sempre 40×56, nv.2 sempre 40×64 (canvas fixo, a máquina centralizada). Assim a âncora não muda quando faz upgrade.",
        "Ordem de desenho por tile: chão ou água → parede (topo 32×32) → face (em <code>y + 20</code>, se o tile de baixo não for parede) → overlay de minério → terminal. Depois os objetos e o player ordenados por <code>ay</code>.",
        "Sugestão barata usada nas prévias: no chão logo abaixo de uma parede, um retângulo preto 32×6 com alpha 80; à direita de uma parede, 4×32 com alpha 40. Dá profundidade sem asset novo.",
        "<code>player.png</code> olha pra direita; espelhe pra esquerda. <code>player_walk.png</code>: 4 quadros de 20×30, mesma âncora (pés na última linha).",
        "Carregar com <code>convert_alpha()</code>. Nada de <code>smoothscale</code>: escala inteira só no final, na janela.",
    ]
    integ_html = "".join(f"<li>{s}</li>" for s in integ)

    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Sprites</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Pixelify+Sans:wght@400;600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15100e;--panel:#1e1714;--panel2:#241b17;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;
  --f-label:"Silkscreen",ui-monospace,monospace;--f-display:"Pixelify Sans",ui-monospace,monospace;--f-body:"IBM Plex Sans",system-ui,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,monospace;color-scheme:dark}}
*{{box-sizing:border-box}}html,body{{margin:0}}
body{{background:var(--bg);color:var(--fg);font:15px/1.6 var(--f-body);padding-inline:16px}}
.wrap{{max-width:1320px;margin:0 auto;padding-block:48px 80px}}
.eyebrow{{font:12px var(--f-label);letter-spacing:.08em;color:var(--rust);text-transform:uppercase}}
h1{{font:600 clamp(34px,6vw,58px)/1.05 var(--f-display);margin:10px 0 14px}}
.lede{{color:var(--muted);max-width:68ch;margin:0}}
.status{{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}}
.chip{{font:11px var(--f-label);padding:4px 10px;border:1px solid var(--line);background:var(--panel)}}
.chip.ok{{color:var(--ok);border-color:#2f5a2c}}
h2{{font:600 24px/1.2 var(--f-display);margin:0 0 16px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}}
section{{margin-top:56px}}
.pvs{{display:flex;flex-direction:column;gap:28px}}
.pv{{margin:0}}
.pv img{{display:block;width:100%;max-width:960px;height:auto;image-rendering:pixelated;border:1px solid var(--line)}}
.pv figcaption{{display:flex;gap:12px;align-items:baseline;margin-top:8px;flex-wrap:wrap}}
.pv b{{font:14px var(--f-label);color:var(--gold)}}
.pv span{{color:var(--muted);font-size:14px}}
@media (min-width:1300px){{.pv img{{max-width:none;width:960px}}}}
.cards{{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}}
.spr{{margin:0;background:var(--panel);border:1px solid var(--line);padding:10px;display:flex;flex-direction:column;gap:8px;max-width:100%}}
.chk{{display:flex;gap:10px;align-items:flex-end;padding:8px;overflow:auto;
  background-color:#2a211d;background-image:conic-gradient(#3a2e28 25%,transparent 0 50%,#3a2e28 0 75%,transparent 0);background-size:16px 16px}}
.chk img{{image-rendering:pixelated;display:block;max-width:none}}
.anim{{image-rendering:pixelated;animation:walk .5s steps(4) infinite;flex:none}}
@keyframes walk{{to{{background-position-x:-100%}}}}
.spr figcaption{{display:flex;justify-content:space-between;gap:12px;font:12px var(--f-mono)}}
.spr figcaption span{{color:var(--muted)}}
.pals{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.pal{{background:var(--panel);border:1px solid var(--line);padding:12px}}
.pal h3{{font:12px var(--f-label);margin:0 0 10px;color:var(--fg)}}
.pal h3 span{{color:var(--muted);margin-left:6px}}
.pal ul{{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:4px}}
.pal li{{display:flex;align-items:center;gap:6px;font:11px var(--f-mono);color:var(--muted)}}
.pal i{{width:16px;height:16px;flex:none;border:1px solid rgba(255,255,255,.12)}}
.notes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:28px}}
.notes ul{{margin:0;padding-left:18px;color:var(--muted)}}
.notes li{{margin-bottom:10px}}
.notes b{{color:var(--fg)}}
code{{font-family:var(--f-mono);font-size:.92em;color:var(--gold)}}
.box{{background:var(--panel);border:1px solid var(--line);padding:18px 20px}}
.box h3{{font:600 18px var(--f-display);margin:0 0 10px}}
.dev{{border-left:3px solid var(--cyan)}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Hesper · Designer · v0.1</div>
  <h1>Sprites do MVP</h1>
  <p class="lede">Todos os sprites do contrato (bíblia §6) em pixel art 1:1, gerados por <code>tools/sprites/build_sprites.py</code>. Primeiro as três cenas de prévia, montadas só com esses PNGs como o jogo vai montar; embaixo cada sprite ampliado, a paleta e as decisões. Nada disso entra no jogo antes da tua aprovação.</p>
  <div class="status"><span class="chip ok">{len(spr)} arquivos · tamanhos conferidos</span><span class="chip">{len(total)} cores no total</span><span class="chip ok">0 desvios do contrato</span></div>
</header>

<section><h2>Prévia das cenas (960×540, tamanho real)</h2><div class="pvs">{previews}</div></section>

{"".join(groups_html)}

<section><h2>Paleta usada</h2><p class="lede" style="margin-bottom:16px">Extraída dos PNGs gerados (cores opacas, da mais escura pra mais clara). A base é a paleta da bíblia §3 e os tons auxiliares do mockup; a sombra no chão é preto a 36%.</p><div class="pals">{"".join(pal_html)}</div></section>

<section><h2>Decisões de design</h2><div class="notes">
  <div class="box"><h3>Escolhas</h3><ul>{notes_html}</ul></div>
  <div class="box dev"><h3>Pro Dev integrar</h3><ul>{integ_html}</ul></div>
</div>
<p class="lede" style="margin-top:20px"><b style="color:var(--fg)">Desvios do contrato:</b> nenhum. Nomes e tamanhos exatamente como na bíblia; nos itens "até", usei o máximo (máquinas 40×56 e 40×64) e plantas menores (arbusto 24×18, árvore 32×40, flor 20×14).</p>
</section>
</div>
</body>
</html>
"""
    (REP / "index.html").write_text(page, encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    canv = build_sprites()
    for name, cv in canv.items():
        cv.save(name)
    spr = {n: Image.open(OUT / n).convert("RGBA") for n in canv}
    for st in STAGES:
        render_scene(st, spr).save(REP / f"preview_{st}.png")
    build_report(spr)
    print(f"{len(canv)} sprites em {OUT.relative_to(ROOT)}, 3 prévias + index.html em {REP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
