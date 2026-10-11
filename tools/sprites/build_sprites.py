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


FACE_EXTRA = {  # tons extras da face alta (derivados da cor de face da bíblia)
    "dead": dict(faceL="#3e2928", faceD="#241717", faceDD="#180f10"),
    "mist": dict(faceL="#3a3438", faceD="#211e20", faceDD="#151314"),
    "green": dict(faceL="#3b3b36", faceD="#22221f", faceDD="#151513"),
}
FH = 24  # altura da face


def make_face(stage: str) -> Canvas:
    """Paredão de rocha 32x24: blocos irregulares (Voronoi achatado, periódico na horizontal),
    estratos horizontais quebrados, fissuras diagonais, luz em cima e sombra embaixo de cada bloco,
    escurecendo pro pé. Usa a mesma família de cores do topo do estágio."""
    P, seed = STAGES[stage], STAGE_SEED[stage]
    X = FACE_EXTRA[stage]
    ramp = [P["rockHi"], P["rock2"], P["rock"], P["rockDot"], P["face"], X["faceD"], X["faceDD"]]
    # pontos dos blocos: 3 "camadas" horizontais com tamanhos variados (estratos)
    pts = []
    rng_i = 0
    for layer, (yc, n) in enumerate(((3.5, 3), (10.5, 4), (17.5, 3), (24.0, 4))):
        for i in range(n):
            rng_i += 1
            x = (i + 0.2 + hsh(rng_i, 1, seed) * 0.6) * T / n
            y = yc + (hsh(rng_i, 2, seed) - 0.5) * 3.0
            pts.append((x, y, layer))
    ys, xs = np.mgrid[0:FH, 0:T] + 0.5
    best = np.full((FH, T), 1e9)
    cell = np.zeros((FH, T), int)
    jit = np.array([[vnoise(x * 0.45, y * 0.45, seed + 5) for x in range(T)] for y in range(FH)])
    for k, (px_, py_, _) in enumerate(pts):
        dx = np.abs(xs - px_)
        dx = np.minimum(dx, T - dx)               # distância periódica na horizontal
        d = np.sqrt((dx * 0.6) ** 2 + ((ys - py_) * 1.5) ** 2) + jit * 1.2
        m = d < best
        best[m] = d[m]
        cell[m] = k
    cv = Canvas(T, FH)
    # tom base: escurece com a profundidade; cada bloco varia ±1
    for y in range(FH):
        base = 1 if y < 4 else 2 if y < 9 else 3 if y < 14 else 4 if y < 19 else 5
        for x in range(T):
            k = cell[y, x]
            lvl = base + (1 if hsh(k, 7, seed) < 0.35 else 0)
            cv.px(x, y, C(ramp[min(6, lvl)]))
    lvl_at = lambda y: 1 if y < 4 else 2 if y < 9 else 3 if y < 14 else 4 if y < 19 else 5
    up = np.roll(cell, 1, 0); up[0] = cell[0]
    down = np.roll(cell, -1, 0); down[-1] = cell[-1]
    left = np.roll(cell, 1, 1)
    for y in range(FH):
        for x in range(T):
            if down[y, x] != cell[y, x]:
                cv.px(x, y, C(X["faceDD"]))                       # junta/sombra embaixo do bloco
            elif up[y, x] != cell[y, x] or y == 0:
                cv.px(x, y, C(ramp[max(0, lvl_at(y) - 2)]))      # luz no topo do bloco
            elif left[y, x] != cell[y, x]:
                cv.px(x, y, C(ramp[min(6, lvl_at(y) + 1)]))      # junta lateral, curta e irregular
    # fissuras diagonais dentro dos blocos
    for i, (fx, fy, ln, dirx) in enumerate(((6, 4, 4, 1), (24, 12, 4, -1))):
        x, y = fx, fy
        for j in range(ln):
            cv.px(x, y, C(X["faceDD"]), wrap=True)
            cv.px(x + (1 if dirx < 0 else -1), y, C(ramp[max(0, lvl_at(y) - 1)]), wrap=True)
            y += 1
            if j % 2 == 0 or hsh(i, j, seed) < 0.4:
                x += dirx
    # lábio do topo, casando com o topo da rocha
    cv.rect(0, 0, T, 1, C(P["rockHi"]))
    for x in range(T):
        if hsh(x, 9, seed) < 0.5:
            cv.px(x, 1, C(P["rock2"]))
    cv.rect(0, FH - 1, T, 1, C(X["faceDD"]))
    for x, y in ((3, 3), (17, 2), (25, 9), (10, 8)):
        cv.px(x, y, C(P["rockHi"]))
    if "moss" in P:
        for x in range(T):
            cv.px(x, 0, C(P["moss2"] if hsh(x, 3, seed) < 0.5 else P["moss"]))
            if hsh(x, 4, seed) < 0.6:
                cv.px(x, 1, C(P["moss"]))
            if hsh(x, 5, seed) < 0.2:
                cv.px(x, 2, C(P["mossD"]))
        for vx, ln in ((4, 14), (13, 7), (22, 18), (29, 10)):
            x = vx
            for y in range(1, 1 + ln):
                cv.px(x, y, C(P["moss"] if y % 4 else P["mossD"]), wrap=True)
                if y % 3 == 2:
                    cv.px(x + (1 if (y // 3) % 2 else -1), y, C(P["moss2"]), wrap=True)
                if y in (5, 11):
                    x += 1 if vx % 2 else -1
            cv.px(x, 1 + ln, C(P["moss2"]), wrap=True)
        for mx, my, w in ((7, 12, 3), (18, 8, 3)):
            cv.rect(mx, my, w, 1, C(P["moss"]))
            cv.px(mx + 1, my - 1, C(P["moss2"]))
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


# ---------------------------------------------------------------- personagem (v2: astronauta chibi 32x32)

AST = dict(
    line="#1b1630", w="#f4f4f8", l="#d3d8e6", s="#9aa2bf", d="#6a7194",
    v0="#151638", v1="#232457", v2="#3b2f78", vr="#9fb2ff", vh="#ffffff",
    r="#d9384a", rd="#97213a", p="#353a5a", cy="#59d0e6", y="#f2c46d",
    bp="#b9bfd1", bps="#878fac",
)


def shade_ellipse(cx, cy, rx, ry):
    """Máscara + nível de luz (0 claro .. 3 escuro) de uma elipse, luz vindo de cima/esquerda."""
    ys, xs = np.mgrid[0:32, 0:32] + 0.5
    dx, dy = (xs - cx) / rx, (ys - cy) / ry
    m = dx * dx + dy * dy <= 1.0
    k = dx * 0.75 + dy * 0.65
    lvl = np.where(k > 0.62, 3, np.where(k > 0.3, 2, np.where(k > -0.25, 1, 0)))
    lvl[(k < -0.62)] = 0
    return m, lvl


class Part:
    """Uma camada do boneco: pinta numa tela própria, ganha contorno e é colada de trás pra frente."""
    def __init__(self):
        self.cv = Canvas(32, 32)

    def r(self, x, y, w, h, c):
        self.cv.rect(x, y, w, h, C(AST[c]))
        return self

    def p(self, x, y, c):
        self.cv.px(x, y, C(AST[c]))
        return self

    def body_rect(self, x, y, w, h, round_=True):
        """Bloco do traje: branco, coluna da esquerda clara, direita e base em cinza-azulado."""
        self.r(x, y, w, h, "w")
        self.r(x + w - 2, y, 2, h, "l")
        self.r(x + w - 1, y + 1, 1, h - 1, "s")
        self.r(x, y + h - 1, w, 1, "s")
        if round_:
            for cx, cy in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
                self.cv.a[cy, cx] = 0
        return self


def put(dst: Canvas, part: Part):
    part.cv.outline(C(AST["line"]))
    dst.paste(part.cv, 0, 0)


def helmet(dst: Canvas, view: str, bob: int):
    cx, cy = (16.0 if view != "side" else 15.5), 8.5 + bob
    m, lvl = shade_ellipse(cx, cy, 8.6, 7.7)
    pt = Part()
    cols = [C(AST["w"]), C(AST["w"]), C(AST["l"]), C(AST["s"])]
    for k in range(4):
        pt.cv.a[m & (lvl == k)] = cols[k]
    if view == "up":
        # nuca: faixa vermelha e respiro
        yb = int(cy + 3)
        for x in range(32):
            if m[yb, x] and m[yb + 1, x]:
                pt.cv.px(x, yb, C(AST["r"]))
        pt.r(14, int(cy) - 3, 4, 2, "l").r(14, int(cy) - 3, 4, 1, "s")
    else:
        vcx = cx if view == "down" else cx + 3.2
        vrx = 6.2 if view == "down" else 4.6
        vm, vl = shade_ellipse(vcx, cy + 0.6, vrx, 5.0)
        vm &= m
        if view == "side":
            inner, _ = shade_ellipse(cx, cy, 7.6, 6.7)
            vm &= inner
        vc = [C(AST["v1"]), C(AST["v1"]), C(AST["v1"]), C(AST["v0"])]
        for k in range(4):
            pt.cv.a[vm & (vl == k)] = vc[k]
        # meia-lua roxa na base do visor (luz rebatida)
        below2 = np.roll(vm, -2, 0)
        pt.cv.a[vm & ~below2 & np.roll(vm, -1, 0)] = C(AST["v2"])
        # aro cinza em volta do visor (só do lado de dentro do capacete)
        ring = np.zeros_like(vm)
        ring[1:, :] |= vm[:-1, :]; ring[:-1, :] |= vm[1:, :]
        ring[:, 1:] |= vm[:, :-1]; ring[:, :-1] |= vm[:, 1:]
        ring &= ~vm & m
        if view == "side":
            ring &= np.arange(32)[None, :] < 26
        pt.cv.a[ring] = C(AST["s"])
        # reflexo em curva: faixa fina perto da borda de cima/esquerda do visor
        ys_, xs_ = np.mgrid[0:32, 0:32] + 0.5
        ddx, ddy = (xs_ - vcx) / vrx, (ys_ - cy - 0.6) / 5.0
        rr = ddx * ddx + ddy * ddy
        arc = vm & (rr > 0.42) & (rr < 0.78) & (ddx < -0.05) & (ddy < -0.15) & (ddx + ddy < -0.55)
        pt.cv.a[arc] = C(AST["vr"])
        ay, ax = np.nonzero(arc)
        if len(ax):
            i = np.argsort(ax + ay)[len(ax) // 2]
            pt.cv.px(ax[i], ay[i], C(AST["vh"]))
        gx = int(vcx + vrx * 0.35)
        pt.cv.px(gx, int(cy + 0.6 + 2.6), C(AST["vr"]))
        if view == "side":  # antena/luz da lateral do capacete
            pt.r(int(cx) - 6, int(cy) - 1, 2, 3, "l").p(int(cx) - 6, int(cy), "r")
    put(dst, pt)


def leg(dst: Canvas, x, top, bottom, view, stride=0, toe=1):
    """Perna com bota; `stride` inclina (desloca o pé) no lado."""
    pt = Part()
    n = bottom - top + 1
    for i, y in enumerate(range(top, bottom + 1)):
        t = i / max(1, n - 1)
        xo = x + int(round(stride * t))
        boot = y >= bottom - 2
        if boot:
            pt.r(xo, y, 4, 1, "d").p(xo, y, "s")
            if view == "side" and y == bottom:
                pt.p(xo + 4 * (1 if toe > 0 else 0) - (1 if toe < 0 else 0), y, "d")
        else:
            pt.r(xo, y, 4, 1, "w").r(xo + 3, y, 1, 1, "s").r(xo + 2, y, 1, 1, "l")
        if y == bottom - 3:
            pt.r(xo, y, 4, 1, "r").p(xo + 3, y, "rd")
    put(dst, pt)


def arm(dst: Canvas, x, y, w=3, h=7, glove_rows=2, side=False):
    pt = Part()
    pt.r(x, y, w, h, "w").r(x + w - 1, y, 1, h, "s").r(x, y, 1, h - glove_rows, "w")
    if w >= 3:
        pt.r(x + 1, y, 1, h, "l") if side else None
    pt.r(x, y + h - glove_rows, w, glove_rows, "r").r(x + w - 1, y + h - glove_rows, 1, glove_rows, "rd")
    pt.r(x, y + 1, w, 1, "l")
    put(dst, pt)


def astronaut(view: str, bob=0, lift_l=0, lift_r=0, arm_l=0, arm_r=0, stride=0, swap=False) -> Canvas:
    """Desenha um quadro. bob<0 sobe o corpo; lift_* levanta o pé; arm_* move o braço; stride = passada (lado)."""
    cv = Canvas(32, 32)
    B = bob
    if view in ("down", "up"):
        # mochila aparecendo atrás (frente) — na vista de costas ela vem por cima, mais abaixo
        if view == "down":
            bp = Part().r(9, 14 + B, 14, 8, "bp").r(20, 14 + B, 3, 8, "bps")
            put(cv, bp)
        leg(cv, 11, 23 + B, 30 - lift_l, view)
        leg(cv, 17, 23 + B, 30 - lift_r, view)
        torso = Part().body_rect(10, 15 + B, 12, 10)
        torso.r(10, 22 + B, 12, 1, "r").r(20, 22 + B, 2, 1, "rd")      # cinto vermelho
        if view == "down":
            torso.r(13, 17 + B, 6, 4, "p")                           # painel do peito
            torso.p(14, 18 + B, "r").p(15, 18 + B, "cy").p(16, 18 + B, "y").r(14, 19 + B, 4, 1, "d")
            torso.p(17, 18 + B, "cy")
        put(cv, torso)
        arm(cv, 7, 16 + B + arm_l, 3, 7)
        arm(cv, 22, 16 + B + arm_r, 3, 7)
        if view == "up":
            bp = Part().r(10, 14 + B, 12, 10, "bp").r(19, 14 + B, 3, 10, "bps").r(10, 23 + B, 12, 1, "bps")
            bp.r(12, 16 + B, 8, 1, "r").r(12, 19 + B, 3, 2, "d").r(17, 19 + B, 3, 2, "d")
            bp.p(12, 19 + B, "s").p(17, 19 + B, "s")
            for cx, cy_ in ((10, 14), (21, 14), (10, 23), (21, 23)):
                bp.cv.a[cy_ + B, cx] = 0
            put(cv, bp)
        helmet(cv, view, B)
        return cv
    # lado (olhando pra direita)
    bp = Part().r(6, 14 + B, 6, 10, "bp").r(6, 14 + B, 6, 1, "w").r(6, 23 + B, 6, 1, "bps")
    bp.r(7, 16 + B, 1, 6, "r")
    for cx, cy_ in ((6, 14), (6, 23)):
        bp.cv.a[cy_ + B, cx] = 0
    back, front = (13, 15) if not swap else (15, 13)
    leg(cv, back if not swap else front, 23 + B, 30 - (lift_l if not swap else lift_r), "side", -stride)
    torso = Part().body_rect(11, 15 + B, 10, 10)
    torso.r(11, 22 + B, 10, 1, "r").r(19, 22 + B, 2, 1, "rd")
    torso.r(17, 17 + B, 3, 3, "p").p(18, 18 + B, "cy")
    leg_front_x = front if not swap else back
    leg(cv, leg_front_x, 23 + B, 30 - (lift_r if not swap else lift_l), "side", stride)
    put(cv, torso)
    put(cv, bp)
    helmet(cv, "side", B)
    arm(cv, 14 + arm_r, 16 + B, 3, 7, side=True)
    return cv


WALK = {
    # (bob, lift_l, lift_r, arm_l, arm_r, stride, swap): contato, passagem, contato invertido, passagem
    "down": [(0, 0, 2, 1, -1, 0, False), (-1, 0, 0, 0, 0, 0, False), (0, 2, 0, -1, 1, 0, False), (-1, 0, 0, 0, 0, 0, False)],
    "side": [(0, 0, 0, 0, 1, 3, False), (-1, 2, 0, 0, 0, 0, False), (0, 0, 0, 0, -1, 3, True), (-1, 0, 2, 0, 0, 0, False)],
}
WALK["up"] = WALK["down"]


def make_player(view: str) -> Canvas:
    return astronaut(view)


def make_walk(view: str) -> Canvas:
    sheet = Canvas(128, 32)
    for f, (bob, ll, lr, al, ar, st, sw) in enumerate(WALK[view]):
        sheet.paste(astronaut(view, bob, ll, lr, al, ar, st, sw), f * 32, 0)
    return sheet


# ---------------------------------------------------------------- broca (v2.1)

DR = dict(w="#f4f4f8", l="#d3d8e6", s="#9aa2bf", d="#6a7194", g="#3b3f46", gl="#5a6069",
          o="#e2733a", oh="#f29a62", od="#a8471f", led="#7fd67a", ledh="#d6ffd0",
          m0="#f2f5fa", m1="#bcc4d2", m2="#8b94a8", m3="#555d72")
DRILL_LINE = "#1b1630"
SHAKE = [(0, 0), (0, 1), (1, 0), (0, -1)]  # tremor de 1 px por quadro


def _dp(cv, x, y, c):
    cv.px(x, y, C(DR[c]))


def _dr(cv, x, y, w, h, c):
    cv.rect(x, y, w, h, C(DR[c]))


def spiral_bit(cv: Canvas, axis: str, base, center, length, half0, f):
    """Ponta cônica com rosca. axis 'x': base em x=base indo pra +x; 'y+': pra baixo; 'y-': pra cima.
    A rosca são listras diagonais que andam 1 px por quadro (gira); o reflexo corre pela ponta."""
    for i in range(length):
        half = max(0, round(half0 * (1 - i / length)))
        for j in range(-half, half + 1):
            # posição ao longo do eixo (i) e através (j)
            band = (i + (j if axis != "y-" else -j) - f) % 4
            edge_light = j == -half
            edge_dark = j == half
            if band == 0:
                c = "m3"
            elif band == 1:
                c = "m0" if j < 0 else "m1"
            elif edge_dark:
                c = "m2"
            else:
                c = "m1" if j <= 0 else "m2"
            if edge_light and band != 0:
                c = "m0" if band == 1 else "m1"
            if axis == "x":
                _dp(cv, base + i, center + j, c)
            elif axis == "y+":
                _dp(cv, center + j, base + i, c)
            else:
                _dp(cv, center + j, base - i, c)
    # reflexo correndo pela ponta
    k = (f * 2) % max(2, length - 2)
    hj = -max(0, round(half0 * (1 - k / length))) + 1
    if axis == "x":
        _dp(cv, base + k, center + hj, "m0")
        _dp(cv, base + k + 1, center + hj, "m0")
    elif axis == "y+":
        _dp(cv, center + hj, base + k, "m0")
        _dp(cv, center + hj, base + k + 1, "m0")
    else:
        _dp(cv, center + hj, base - k, "m0")
        _dp(cv, center + hj, base - k - 1, "m0")


def drill_layer(w, h, draw) -> Canvas:
    p = Canvas(w, h)
    draw(p)
    p.outline(C(DRILL_LINE))
    return p


def drill_frame(view: str, f: int) -> Canvas:
    sx, sy = SHAKE[f]
    if view == "side":
        cv = Canvas(24, 16)

        def grip(p):
            _dr(p, 5 + sx, 9 + sy, 3, 5, "g")
            _dr(p, 5 + sx, 9 + sy, 1, 5, "gl")

        def body(p):
            x, y = 1 + sx, 3 + sy
            _dr(p, x, y, 10, 7, "w")
            _dr(p, x, y + 5, 10, 2, "s")
            _dr(p, x, y + 4, 10, 1, "l")
            _dr(p, x + 3, y + 2, 5, 2, "o")
            _dr(p, x + 3, y + 2, 5, 1, "oh")
            _dp(p, x + 1, y + 1, "led")
            _dp(p, x + 1, y + 2, "ledh" if f % 2 == 0 else "led")
            _dr(p, x + 9, y, 1, 7, "d")
            p.a[y, x] = 0
            p.a[y + 6, x] = 0

        def collar(p):
            _dr(p, 11 + sx, 3 + sy, 2, 7, "g")
            _dr(p, 11 + sx, 3 + sy, 2, 1, "gl")

        def bit(p):
            spiral_bit(p, "x", 13 + sx, 6 + sy, 9, 3, f)

        for d in (grip, body, collar, bit):
            cv.paste(drill_layer(24, 16, d), 0, 0)
        return cv
    cv = Canvas(16, 24)
    if view == "down":
        def body(p):
            x, y = 4 + sx, 1 + sy
            _dr(p, x, y, 7, 10, "w")
            _dr(p, x + 5, y, 2, 10, "s")
            _dr(p, x + 4, y, 1, 10, "l")
            _dr(p, x + 1, y + 3, 4, 4, "o")
            _dr(p, x + 1, y + 3, 1, 4, "oh")
            _dp(p, x + 1, y + 1, "ledh" if f % 2 == 0 else "led")
            _dr(p, x, y + 9, 7, 1, "d")
            p.a[y, x] = 0
            p.a[y, x + 6] = 0

        def grip(p):
            _dr(p, 11 + sx, 3 + sy, 3, 5, "g")
            _dr(p, 11 + sx, 3 + sy, 3, 1, "gl")

        def collar(p):
            _dr(p, 4 + sx, 11 + sy, 7, 2, "g")
            _dr(p, 4 + sx, 11 + sy, 1, 2, "gl")

        def bit(p):
            spiral_bit(p, "y+", 13 + sy, 7 + sx, 9, 3, f)

        for d in (grip, body, collar, bit):
            cv.paste(drill_layer(16, 24, d), 0, 0)
        return cv
    # up: a broca aponta pra cima; o corpo fica quase todo atrás do astronauta
    def body(p):
        x, y = 5 + sx, 13 + sy
        _dr(p, x, y, 7, 9, "w")
        _dr(p, x + 5, y, 2, 9, "s")
        _dr(p, x + 1, y + 3, 4, 3, "o")
        _dp(p, x + 1, y + 1, "ledh" if f % 2 == 0 else "led")

    def grip(p):
        _dr(p, 2 + sx, 15 + sy, 3, 5, "g")

    def collar(p):
        _dr(p, 5 + sx, 11 + sy, 7, 2, "g")
        _dr(p, 5 + sx, 11 + sy, 1, 2, "gl")

    def bit(p):
        spiral_bit(p, "y-", 10 + sy, 8 + sx, 9, 3, f)

    for d in (grip, body, collar, bit):
        cv.paste(drill_layer(16, 24, d), 0, 0)
    return cv


def make_drill(view: str) -> Canvas:
    w, h = (24, 16) if view == "side" else (16, 24)
    sheet = Canvas(w * 4, h)
    for f in range(4):
        sheet.paste(drill_frame(view, f), f * w, 0)
    return sheet


# offset do quadro da broca relativo ao canto sup. esquerdo do quadro do player (32x32) + ordem
DRILL_OFFSET = {"side": ((12, 13), "depois"), "down": ((13, 16), "depois"), "up": ((20, 4), "antes")}


def make_drill_preview(spr: dict[str, Image.Image]) -> Image.Image:
    """Player parado + broca (quadro 0) nas 3 direções, ampliado 6x, sobre o chão do estágio morto."""
    cells = []
    for view in ("side", "down", "up"):
        cell = Image.new("RGBA", (64, 56), (0, 0, 0, 0))
        for yy in range(0, 56, 32):
            for xx in range(0, 64, 32):
                cell.alpha_composite(spr["floor_dead_0.png"], (xx, yy))
        ox, oy = 16, 14
        sh = Canvas(20, 7)
        sh.ellipse(10, 3.5, 8, 2.5, SHADOW)
        cell.alpha_composite(sh.image(), (ox + 6, oy + 28))
        (dx, dy), order = DRILL_OFFSET[view]
        w = 24 if view == "side" else 16
        d = spr[f"drill_{view}.png"].crop((0, 0, w, spr[f"drill_{view}.png"].height))
        if order == "antes":
            cell.alpha_composite(d, (ox + dx, oy + dy))
        cell.alpha_composite(spr[f"player_{view}.png"], (ox, oy))
        if order == "depois":
            cell.alpha_composite(d, (ox + dx, oy + dy))
        cells.append(cell)
    out = Image.new("RGBA", (64 * 3 + 8, 56), (21, 16, 14, 255))
    for i, c in enumerate(cells):
        out.alpha_composite(c, (i * 68, 0))
    return out.resize((out.width * 6, out.height * 6), Image.NEAREST).convert("RGB")


# ---------------------------------------------------------------- veios e drill automática (v2.2)

VEIN_SOIL = (0, 0, 0, 72)       # terra remexida: escurece qualquer chão (1 nível de alpha)
VEIN_PIT = (0, 0, 0, 128)       # miolo mais fundo, em volta dos cristais
RUBBLE = ["#4a3f3a", "#6b5d55", "#8a7b70"]  # cascalho neutro, funciona nos 3 chãos

VEIN_LAYOUT = {
    # (x, base_y, w, h, tipo), de trás pra frente
    "iron": [(17, 27, 9, 10, "point"), (27, 24, 11, 13, "point"), (38, 28, 8, 8, "point"),
             (12, 36, 7, 7, "point"), (21, 40, 10, 11, "point"), (33, 42, 12, 12, "point"),
             (44, 39, 7, 7, "point"), (27, 49, 8, 7, "point"), (17, 48, 6, 5, "point"), (40, 50, 6, 5, "point")],
    "silicon": [(19, 28, 5, 13, "point"), (26, 26, 6, 18, "point"), (34, 27, 5, 12, "point"),
                (40, 33, 4, 9, "point"), (13, 37, 4, 9, "point"), (22, 43, 6, 16, "point"),
                (31, 45, 7, 20, "point"), (40, 47, 5, 12, "point"), (16, 49, 4, 7, "point"), (47, 45, 3, 6, "point")],
    "ice": [(18, 28, 9, 9, "cube"), (29, 25, 10, 10, "cube"), (40, 31, 7, 7, "cube"),
            (12, 38, 7, 7, "cube"), (21, 43, 11, 11, "cube"), (34, 44, 10, 10, "cube"),
            (44, 46, 7, 7, "cube"), (28, 51, 7, 6, "cube"), (16, 51, 5, 5, "cube")],
}


def vein_mask(seed, rx, ry, cx=32, cy=36, wob=0.22):
    ys, xs = np.mgrid[0:64, 0:64] + 0.5
    ang = np.arctan2(ys - cy, xs - cx)
    r = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    # borda orgânica: raio varia com o ângulo (soma de senos com fase da seed)
    k = 1 + wob * (0.55 * np.sin(3 * ang + seed) + 0.3 * np.sin(5 * ang + seed * 2.1) + 0.15 * np.sin(9 * ang + seed * 0.7))
    return r <= k


def make_vein(name: str) -> Canvas:
    O = ORES[name]
    sd = {"iron": 1.3, "silicon": 2.9, "ice": 4.4}[name]
    cv = Canvas(64, 64)
    soil = vein_mask(sd, 29, 25)
    pit = vein_mask(sd + 1, 19, 15, wob=0.18)
    cv.a[soil] = VEIN_SOIL
    cv.a[pit] = VEIN_PIT
    # rachaduras saindo do miolo
    for i in range(7):
        a = sd + i * 0.9
        x, y = 32 + math.cos(a) * 15, 36 + math.sin(a) * 12
        for j in range(5 + i % 3):
            xi, yi = int(x), int(y)
            if 0 <= xi < 64 and 0 <= yi < 64 and soil[yi, xi]:
                cv.px(xi, yi, C("#241c18"))
            x += math.cos(a) * 1.4 + (hsh(i, j, 5) - 0.5)
            y += math.sin(a) * 1.0
    # cascalho na terra remexida
    for i in range(26):
        x, y = int(hsh(i, 1, int(sd * 10)) * 64), int(hsh(i, 2, int(sd * 10)) * 64)
        if not soil[y, x] or pit[y, x]:
            continue
        w = 1 + (i % 3 == 0)
        cv.rect(x, y, w + 1, 1, C(RUBBLE[1]))
        cv.px(x, y, C(RUBBLE[2]))
        cv.rect(x, y + 1, w + 1, 1, C(RUBBLE[0]))
    # lascas do minério espalhadas (dão a cor do veio de longe)
    for i in range(14):
        x, y = int(hsh(i, 3, int(sd * 10)) * 64), int(hsh(i, 4, int(sd * 10)) * 64)
        if not soil[y, x]:
            continue
        cv.rect(x, y, 2, 1, C(O["light"]))
        cv.px(x + 1, y, C(O["dark"]))
        cv.px(x, y + 1, C(O["line"]))
        cv.px(x + 1, y + 1, C(O["line"]))
    # afloramento: cristais grandes com contorno próprio
    for x, yb, w, h, k in VEIN_LAYOUT[name]:
        gem(cv, x, yb, w, h, O, k)
    for x, y in ((24, 20), (41, 24), (11, 31), (50, 41), (30, 56)):
        if soil[y, x]:
            cv.px(x, y, C(O["hi"]))
    return cv


def make_machine_drill(f: int) -> Canvas:
    """Drill automática 64x80, um quadro. Chão (centro dos 2x2) em y=48; base na última linha."""
    cv = Canvas(64, 80)
    sx, sy = SHAKE[f]
    cv.ellipse(32, 73, 31, 6, SHADOW)
    # buraco onde a broca entra
    cv.ellipse(32, 60, 9, 3.5, C("#140f0d"))
    cv.rect(26, 58, 12, 1, C("#2a201c"))

    def L(draw):
        cv.paste(drill_layer(64, 80, draw), 0, 0)

    # moldura no chão (vazada: o veio aparece no meio)
    def frame_back(p):
        _dr(p, 6, 30, 52, 3, "s")
        _dr(p, 6, 30, 52, 1, "l")
        _dr(p, 4, 30, 3, 40, "s")
        _dr(p, 4, 30, 1, 40, "l")
        _dr(p, 57, 30, 3, 40, "d")
        _dr(p, 59, 30, 1, 40, "g")
    L(frame_back)

    # pernas da torre (A), da carcaça até os cantos de trás
    def struts(p):
        for (x0, y0, x1, y1) in ((20, 22, 7, 31), (43, 22, 56, 31)):
            n = max(abs(x1 - x0), abs(y1 - y0))
            for i in range(n + 1):
                x = round(x0 + (x1 - x0) * i / n)
                y = round(y0 + (y1 - y0) * i / n)
                _dr(p, x, y, 2, 2, "d")
                _dp(p, x, y, "s")
    L(struts)

    # eixo e broca girando pra baixo
    def shaft(p):
        _dr(p, 29, 26 + sy, 6, 22, "s")
        _dr(p, 29, 26 + sy, 1, 22, "l")
        _dr(p, 34, 26 + sy, 1, 22, "d")
        for yy in range(26, 48):
            if (yy + f * 2) % 6 == 0:          # marcas do eixo correndo = giro
                _dr(p, 30, yy + sy, 4, 1, "g")
        _dr(p, 25, 45 + sy, 14, 3, "g")
        _dr(p, 25, 45 + sy, 14, 1, "gl")
    L(shaft)

    def bit(p):
        spiral_bit(p, "y+", 48 + sy, 32, 13, 5, f)
    L(bit)
    # lábio da frente do buraco (a ponta "entra" no chão)
    cv.rect(25, 61, 14, 1, C("#2a201c"))
    cv.rect(27, 62, 10, 1, C("#4a3f3a"))

    # carcaça (cabeça da drill), estilo das máquinas: cilindro em faixas + faixa laranja + LED
    def head(p):
        x, y = 17 + sx, 3 + sy
        p.rect(x, y + 3, 30, 22, C(INK))
        p.bands(x + 1, y + 4, 20, [("#f4f6f8", 3), ("#e1e5ea", 12), ("#c8cdd4", 8), ("#abb2bb", 4), ("#8c949e", 2)])
        for i, n in enumerate((6, 3, 1)):                    # tampa arredondada
            p.rect(x + n, y + i, 30 - 2 * n, 1, C(INK))
            if i:
                p.rect(x + n + 1, y + i, 28 - 2 * n, 1, C("#eef1f4"))
        p.rect(x + 1, y + 3, 28, 1, C("#e1e5ea"))
        p.rect(x + 1, y + 13, 28, 4, C("#e2733a"))
        p.rect(x + 1, y + 13, 28, 1, C("#f29a62"))
        p.rect(x + 1, y + 16, 28, 1, C("#a8471f"))
        p.rect(x + 1, y + 22, 28, 2, C("#6b717a"))
        p.rect(x + 1, y + 22, 28, 1, C("#8c949e"))
        p.rect(x + 4, y + 7, 2, 2, C("#7fd67a" if f % 2 == 0 else "#2f5a2c"))   # LED
        p.px(x + 4, y + 7, C("#d6ffd0") if f % 2 == 0 else C("#2f5a2c"))
        for i in range(3):                                   # grade
            p.rect(x + 9, y + 6 + i * 2, 12, 1, C("#8c949e"))
        p.rect(x + 23, y + 6, 4, 4, C("#34444f"))
        p.rect(x + 24, y + 7, 2, 1, C("#59d0e6"))
    L(head)

    # caçamba com visor de nível (o jogo pinta o enchimento dentro do visor)
    def hopper(p):
        x, y = 44, 38
        _dr(p, x, y, 15, 24, "s")
        _dr(p, x, y, 15, 2, "w")
        _dr(p, x, y, 1, 24, "l")
        _dr(p, x + 14, y + 2, 1, 22, "d")
        _dr(p, x, y + 4, 15, 2, "o")
        _dr(p, x, y + 4, 15, 1, "oh")
        p.rect(x + 3, y + 8, 9, 14, C(INK))                  # moldura do visor
        p.rect(x + 4, y + 9, 7, 12, C("#14202b"))            # interior vazio (área do indicador)
        p.rect(x + 4, y + 9, 1, 12, C("#1f3140"))
        p.rect(x + 2, y + 23, 11, 1, C("#6b717a"))
    L(hopper)

    # trilho da frente e pés (por cima de tudo, mais perto da câmera)
    def frame_front(p):
        _dr(p, 4, 66, 56, 2, "l")
        _dr(p, 4, 68, 56, 3, "d")
        _dr(p, 4, 66, 56, 1, "w")
        for fx in (2, 54):
            _dr(p, fx, 64, 8, 9, "g")
            _dr(p, fx, 64, 8, 2, "o")
            _dr(p, fx, 64, 8, 1, "oh")
            _dr(p, fx, 70, 8, 3, "gl")
        for fx in (2, 54):
            _dr(p, fx + 1, 27, 6, 6, "g")
            _dr(p, fx + 1, 27, 6, 2, "o")
    L(frame_front)
    return cv


# retângulo do indicador de nível dentro de cada quadro de 64x80 (x, y, w, h); enche de baixo pra cima
DRILL_GAUGE = (48, 47, 7, 12)


def make_machine_drill_sheet() -> Canvas:
    sheet = Canvas(256, 80)
    for f in range(4):
        sheet.paste(make_machine_drill(f), f * 64, 0)
    return sheet


def make_icon_drill() -> Canvas:
    cv = Canvas(16, 16)

    def L(draw):
        cv.paste(drill_layer(16, 16, draw), 0, 0)

    def base(p):
        _dr(p, 1, 12, 14, 2, "d")
        _dr(p, 1, 12, 14, 1, "l")

    def bit(p):
        _dr(p, 7, 7, 2, 2, "g")
        spiral_bit(p, "y+", 9, 8, 6, 2, 0)

    def head(p):
        _dr(p, 3, 1, 10, 6, "w")
        _dr(p, 11, 1, 2, 6, "s")
        _dr(p, 3, 4, 10, 2, "o")
        _dr(p, 3, 4, 10, 1, "oh")
        _dp(p, 4, 2, "led")
        p.a[1, 3] = 0
        p.a[1, 12] = 0
    L(base)
    L(bit)
    L(head)
    return cv


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
    for view in ("down", "up", "side"):
        out[f"player_{view}.png"] = make_player(view)
        out[f"player_walk_{view}.png"] = make_walk(view)
        out[f"drill_{view}.png"] = make_drill(view)
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
    for o in ("iron", "silicon", "ice"):
        out[f"vein_{o}.png"] = make_vein(o)
    out["machine_drill.png"] = make_machine_drill_sheet()
    out["icon_drill.png"] = make_icon_drill()
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
    """Renderer mínimo com a regra v2.1 (estilo Core Keeper):
    1) chão e água; 2) linha por linha, de cima pra baixo: paredes da linha (topo elevado em y-24,
    minério junto do topo, face em y+8 se embaixo é chão, terminal) e depois os objetos ancorados nessa linha."""
    seed = 7
    g = gen_world(seed)
    add_water(g, seed, {"dead": 0.16, "mist": 0.3, "green": 0.4}[stage])
    # túnel vertical de 1 tile saindo da cratera pra cima, e um pilar isolado com o player logo acima
    for y in (0, 1):
        g[y][14] = FL
    PILLAR = (21, 10)
    for c in ((20, 9), (21, 9), (22, 9), (20, 10), (22, 10), (20, 11), (21, 11), (22, 11)):
        g[c[1]][c[0]] = FL
    g[PILLAR[1]][PILLAR[0]] = RK
    # veios 2x2 no chão (a água não cobre veio)
    VEINS = {(9, 4): "iron", (20, 7): "silicon", (7, 8): "ice"}
    vein_cells = set()
    for (vx, vy) in VEINS:
        for c in ((vx, vy), (vx + 1, vy), (vx, vy + 1), (vx + 1, vy + 1)):
            g[c[1]][c[0]] = FL
            vein_cells.add(c)
    # terminal: parede com chão embaixo, na borda esquerda de cima
    term = None
    for y in range(1, GH - 1):
        for x in range(4, 10):
            if is_wall(g[y][x]) and g[y + 1][x] == FL and term is None and y < 7:
                term = (x, y)
                g[y][x] = RK
    img = Image.new("RGBA", (GW * T, GH * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 10), (0, 0, 0, 84))
    shade_b = Image.new("RGBA", (T, 6), (0, 0, 0, 40))
    ore_name = {FE: "ore_iron.png", SI: "ore_silicon.png", IC: "ore_ice.png"}
    # 1) chão e água
    for y in range(GH):
        for x in range(GW):
            t, px, py = g[y][x], x * T, y * T
            if is_wall(t):
                continue
            if t == WA:
                img.alpha_composite(spr[f"water_{stage}.png"], (px, py))
            else:
                img.alpha_composite(spr[f"floor_{stage}_{int(hsh(x, y, 77) * 4)}.png"], (px, py))
            if y > 0 and is_wall(g[y - 1][x]):
                img.alpha_composite(shade, (px, py))
                img.alpha_composite(shade_b, (px, py + 10))
    for (vx, vy), ore in VEINS.items():          # veio = camada de chão, antes de tudo
        img.alpha_composite(spr[f"vein_{ore}.png"], (vx * T, vy * T))

    # objetos ancorados no centro da base
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
        obj("machine_drill.png#0", 21 * T, 9 * T)        # drill em cima do veio de silício
    else:
        obj("machine_o2_t2.png", 11 * T + 16, 9 * T)
        obj("machine_heater_t2.png", 17 * T + 16, 8 * T)
        obj("machine_melter_t2.png", 17 * T + 16, 10 * T)
        obj("machine_o2_t2.png", 12 * T + 16, 11 * T)
        obj("machine_heater_t2.png", 15 * T + 16, 11 * T)
        occupied = {(11, 8), (17, 7), (17, 9), (12, 10), (15, 10), (14, 7), (15, 7), (14, 8), (15, 8),
                    (20, 9), (21, 9), (22, 9), (14, 0), (14, 1)} | vein_cells
        obj("machine_drill.png#2", 21 * T, 9 * T)
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
    # player logo acima do pilar: o topo elevado do pilar esconde metade dele
    objs.append((PILLAR[1] * T - 8, "player", PILLAR[0] * T + 16))
    if stage != "dead":  # um segundo astronauta dentro do túnel
        objs.append((2 * T - 4, "player2", 14 * T + 16))

    def draw_obj(ay, name, ax):
        if name.startswith("player"):
            sh = Canvas(20, 7)
            sh.ellipse(10, 3.5, 8, 2.5, SHADOW)
            img.alpha_composite(sh.image(), (ax - 10, ay - 4))
            if name == "player2":
                p = spr["player_walk_up.png"].crop((32, 0, 64, 32))
            else:
                p = {"dead": spr["player_down.png"],
                     "mist": spr["player_walk_side.png"].crop((0, 0, 32, 32)),
                     "green": spr["player_side.png"].transpose(Image.FLIP_LEFT_RIGHT)}[stage]
            img.alpha_composite(p, (ax - 16, ay - 32))
            return
        if "#" in name:  # sheet de animação: recorta o quadro
            n, fr = name.split("#")
            s = spr[n].crop((int(fr) * 64, 0, int(fr) * 64 + 64, 80))
        else:
            s = spr[name]
        img.alpha_composite(s, (ax - s.width // 2, ay - s.height))

    # 2) linhas de cima pra baixo
    for y in range(GH):
        for x in range(GW):
            t, px, py = g[y][x], x * T, y * T
            if not is_wall(t):
                continue
            top = spr[f"wall_{stage}_{int(hsh(x, y, 91) * 3)}.png"]
            img.alpha_composite(top, (px, py - 24))
            if t in ore_name:
                img.alpha_composite(spr[ore_name[t]], (px, py - 24))
            if y + 1 >= GH:  # fora do mapa da prévia: continua rocha
                img.alpha_composite(spr[f"wall_{stage}_{int(hsh(x, y + 1, 91) * 3)}.png"], (px, py + 8))
            elif not is_wall(g[y + 1][x]):
                img.alpha_composite(spr[f"wall_face_{stage}.png"], (px, py + 8))
            if term == (x, y):
                img.alpha_composite(spr["terminal.png"], (px, py))
        for o in sorted(o for o in objs if (o[0] - 1) // T == y):
            draw_obj(*o)
    return img.crop((0, 0, 960, 540)).convert("RGB")



# ---------------------------------------------------------------- report HTML

GROUPS = [
    ("Astronauta · parado (baixo, cima, lado)", "char", ["player_down.png", "player_up.png", "player_side.png"]),
    ("Astronauta · caminhada (4 quadros, animada ao lado)", "char", ["player_walk_down.png", "player_walk_up.png", "player_walk_side.png"]),
    ("Chão", "tile", [f"floor_{s}_{v}.png" for s in STAGES for v in range(4)]),
    ("Face alta da parede (nova, 32×24)", "face", [f"wall_face_{s}.png" for s in STAGES]),
    ("Parede (topo)", "tile", [f"wall_{s}_{v}.png" for s in STAGES for v in range(3)]),
    ("Água", "tile", [f"water_{s}.png" for s in STAGES]),
    ("Minérios (overlay)", "tile", ["ore_iron.png", "ore_silicon.png", "ore_ice.png"]),
    ("Veios no chão (2×2, overlay)", "tile", ["vein_iron.png", "vein_silicon.png", "vein_ice.png"]),
    ("Ícones", "icon", ["icon_iron.png", "icon_silicon.png", "icon_ice.png", "icon_drill.png"]),
    ("Cápsula e terminal", "obj", ["pod.png", "terminal.png"]),
    ("Máquinas nv.1", "obj", ["machine_o2.png", "machine_heater.png", "machine_melter.png"]),
    ("Máquinas nv.2", "obj", ["machine_o2_t2.png", "machine_heater_t2.png", "machine_melter_t2.png"]),
    ("Plantas (estágio verde)", "obj", ["plant_bush.png", "plant_tree.png", "plant_flower.png"]),
    ("Drill automática (4 quadros, animada a 8 fps ao lado)", "obj", ["machine_drill.png"]),
    ("Broca (4 quadros, animada a 12 fps ao lado)", "drill", ["drill_side.png", "drill_down.png", "drill_up.png"]),
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
        ("Minérios, veios e ícones", [k for k in spr if k.startswith(("ore_", "icon_", "vein_"))]),
        ("Astronauta e broca", [k for k in spr if k.startswith(("player", "drill"))]),
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

    scale = {"tile": 4, "obj": 4, "icon": 8, "char": 6, "face": 8, "drill": 8}
    groups_html = []
    for title, kind, names in GROUPS:
        cards = []
        for n in names:
            im = spr[n]
            s = scale[kind]
            extra = ""
            if n.startswith(("player_walk", "drill_", "machine_drill")):
                fw, fh = im.width // 4, im.height
                cls = "anim fast" if n.startswith("drill_") else "anim"
                extra = (f'<div class="{cls}" style="width:{fw * s}px;height:{fh * s}px;--end:-{im.width * s}px;'
                         f'background-image:url(../../assets/sprites/{n});background-size:{im.width * s}px {fh * s}px"></div>')
            cards.append(
                f'<figure class="spr"><div class="chk">'
                f'{extra}<img src="../../assets/sprites/{n}" width="{im.width * s}" height="{im.height * s}" alt="{n}"></div>'
                f'<figcaption><code>{n}</code><span>{im.width}×{im.height} · {s}×</span></figcaption></figure>'
            )
        groups_html.append(f'<section class="grp"><h2>{title}</h2><div class="cards">{"".join(cards)}</div></section>')

    previews = "".join(
        f'<figure class="pv"><img src="preview_{st}.png" width="960" height="540" alt="Prévia {lab}">'
        f'<figcaption><b>{lab}</b><span>{sub}</span></figcaption></figure>'
        for st, lab, sub in (
            ("dead", "1 · Morto", "máquinas nv.1, poucas poças, player logo acima do pilar isolado"),
            ("mist", "2 · Névoa", "nv.1 + nv.2 misturadas, poças maiores, um astronauta subindo pelo túnel de 1 tile e outro meio escondido atrás do pilar"),
            ("green", "3 · Primeiro verde", "só nv.2, lagos, arbustos, árvores e flores"),
        )
    )

    notes = [
        ("Tiles sem costura",
         "Chão e água usam ruído periódico de 32 px. Os pontos da borda são iguais em todas as variações do mesmo estágio, então qualquer variação encosta em qualquer outra sem emenda. As pedras da parede ficam dentro do tile (1 px de folga) sobre um fundo granulado que também emenda."),
        ("Paredes altas (v2.1)",
         "A face de 32×24 agora é feita de blocos de rocha irregulares e achatados, em três ou quatro estratos horizontais quebrados, com fissuras diagonais. Cada bloco tem luz no topo e uma junta escura embaixo, e o tom escurece em faixas até o pé, usando as mesmas cores do topo da rocha do estágio. Não existe junta vertical regular, que era o que fazia parecer tábua de cerca. No verde, o musgo na borda e os cipós continuam. Com o topo elevado (y−24), o maciço fica com 56 px de altura visível."),
        ("Minério",
         "Cada minério tem uma silhueta própria, além da cor: ferro em cristais baixos e largos, silício em lascas altas, gelo em cubos. Dá pra distinguir até em tela pequena ou pra quem tem daltonismo. Numa parede com face, o overlay de 32×32 cai por cima da faixa de topo e da face, então os cristais aparecem brotando do paredão."),
        ("Astronauta chibi (v2)",
         "Personagem original no estilo das referências, sem copiar nenhuma. O capacete ocupa metade da altura, com visor azul-marinho, meia-lua roxa na base e reflexo claro em curva. Traje branco sombreado em cinza-azulado, luvas, cinto e faixa no joelho vermelhos, painel no peito e mochila (atrás dos ombros de frente, grande de costas e de lado). Contorno #1b1630 em todas as peças, então ele lê bem a 1×. A caminhada segue contato, passagem (corpo sobe 1 px), contato invertido e passagem, com braço balançando. Rodar a 8–10 fps."),
        ("Máquinas nv.2",
         "Mesma família das nv.1 (mesmas cores e faixas de cilindro), só que mais largas e altas, com anéis e frisos dourados (#f2c46d) e peças duplicadas: dois bocais no O₂, duas chaminés e cinco fendas no aquecedor, funil maior com dois visores no derretedor."),
        ("Sombras",
         "Pod, máquinas e plantas já trazem a sombra no rodapé do PNG, em preto com 36% de opacidade (um nível só, sem degradê). O player não tem sombra no PNG: o jogo desenha uma elipse de ~16×5 nos pés."),
        ("Luz e animação",
         "Brilhos, partículas, piscadas e luz ficam por conta do jogo (são cosméticos no MVP). Os sprites vêm no estado 'ligado': luz verde acesa, fendas do aquecedor brilhando."),
    ]
    notes_html = "".join(f"<li><b>{html.escape(a)}.</b> {html.escape(b)}</li>" for a, b in notes)

    integ = [
        "Âncora dos objetos (pod, máquinas, plantas, terminal): centro da base do PNG. Blit em <code>(ax − w/2, ay − h)</code>, com <code>ax</code> = centro do tile e <code>ay</code> = borda de baixo do tile ocupado. O pod tem 64 px e ocupa 2 tiles: <code>ax</code> = linha entre os dois tiles.",
        "Máquinas: nv.1 sempre 40×56, nv.2 sempre 40×64 (canvas fixo, a máquina centralizada). Assim a âncora não muda quando faz upgrade.",
        "Regra de desenho v2.1, no estilo Core Keeper: (1) todo o chão e a água primeiro. (2) Depois, linha por linha de cima pra baixo: pra cada parede da linha, o topo <code>wall_{stage}_N</code> em <code>(x, y − 24)</code> e o overlay de minério no mesmo lugar; se o tile de baixo não for parede, <code>wall_face_{stage}</code> em <code>(x, y + 8)</code>; e o terminal em <code>(x, y)</code>. Em seguida, os objetos e o player cuja âncora cai nessa linha. Assim o topo da parede da linha de baixo cobre os pés de quem está logo acima, como na prévia com o pilar.",
        "Túnel de 1 tile: na vertical fica bonito (prévias). Na horizontal, o topo elevado da parede de baixo cobre 24 dos 32 px do corredor; é o comportamento normal do Core Keeper, mas fica avisado.",
        "Sombra no chão logo abaixo de uma face (usada nas prévias): retângulo preto 32×10 com alpha 84 e mais 32×6 com alpha 40 logo abaixo.",
        "Player: quadros de 32×32 com os pés na linha 30 (a 31 é o contorno da bota). Blit em <code>(ax − 16, ay − 32)</code>. <code>side</code> olha pra direita; espelhe pra esquerda. Caminhadas: 4 quadros de 32×32 na horizontal.",
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
.anim{{image-rendering:pixelated;animation:walk .5s steps(4) infinite;flex:none;outline:1px dashed var(--gold);outline-offset:2px}}
@keyframes walk{{from{{background-position:0 0}}to{{background-position:var(--end) 0}}}}
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
.v2{{margin-top:22px;max-width:860px;background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--gold);padding:14px 18px}}
.v2 > b{{font:13px var(--f-label);color:var(--gold)}}
.v2 ul{{margin:8px 0 0;padding-left:18px;color:var(--muted)}}
.v2 li{{margin-bottom:6px}}
.v2 li b{{color:var(--fg)}}
.anim.fast{{animation-duration:.3s}}
.tb{{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:12px}}
.tb th,.tb td{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line)}}
.tb th{{font:11px var(--f-label);color:var(--muted)}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Hesper · Designer · v2.2</div>
  <h1>Sprites do MVP</h1>
  <p class="lede">Todos os sprites do contrato (bíblia §6) em pixel art 1:1, gerados por <code>tools/sprites/build_sprites.py</code>. Primeiro as três cenas de prévia, montadas só com esses PNGs como o jogo vai montar; embaixo cada sprite ampliado, a paleta e as decisões. Nada disso entra no jogo antes da tua aprovação.</p>
  <div class="status"><span class="chip ok">{len(spr)} arquivos · tamanhos conferidos</span><span class="chip">{len(total)} cores no total</span><span class="chip ok">0 desvios do contrato</span></div>
  <div class="v2"><b>v2.2 · o que mudou</b><ul>
    <li><b>Veios no chão:</b> <code>vein_iron</code>, <code>vein_silicon</code> e <code>vein_ice</code> (64×64, 2×2 tiles). São overlays transparentes: um afloramento de cristais no mesmo idioma dos minérios da parede, em cima de uma mancha de terra remexida com borda orgânica, rachaduras, cascalho e lascas. A mancha é preto translúcido, então funciona sobre o chão dos 3 estágios.</li>
    <li><b>Drill automática:</b> <code>machine_drill</code> (256×80, 4 quadros de 64×80). Tem uma moldura vazada sobre o veio, a cabeça no estilo das máquinas e um eixo com broca girando enterrada no chão. A caçamba tem um visor onde o jogo pinta o nível. Âncora e retângulo do indicador estão na tabela da seção da drill.</li>
    <li><b>Ícone:</b> <code>icon_drill</code> (16×16). As prévias ganharam um veio de cada tipo; a drill aparece em cima do veio de silício na Névoa e no Verde (no Morto ela ainda não foi liberada).</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v2.1</b><ul>
    <li><b>Face da parede refeita</b> (mesmos 32×24): agora são blocos de rocha irregulares com estratos horizontais e fissuras diagonais, sem as juntas verticais que pareciam tábua.</li>
    <li><b>Regra de desenho nova:</b> o topo da parede sobe pra <code>y − 24</code>, a face fica em <code>y + 8</code>, e as linhas são desenhadas de cima pra baixo. As prévias mostram um túnel de 1 tile, um pilar isolado e o player meio escondido atrás dele.</li>
    <li><b>Broca nova:</b> <code>drill_side</code> (96×16), <code>drill_down</code> e <code>drill_up</code> (64×24), com 4 quadros de espiral girando e tremor de 1 px. Offsets e ordem de desenho estão na seção Broca.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v2 · antes disso</b><ul>
    <li><b>Paredes mais altas:</b> a face foi de 32×12 pra <b>32×24</b>. Quando o tile de baixo é chão, a parede mostra 8 px do topo da rocha e um paredão de 24 px, com borda clara, estratos, rachas verticais e saliências, escurecendo pra baixo. No verde tem musgo e cipós. A sombra no chão ficou mais longa.</li>
    <li><b>Astronauta novo, chibi:</b> 32×32, capacete grande com visor escuro e reflexo, traje branco com vermelho e mochila. Tem 3 direções paradas (<code>player_down/up/side</code>) e 3 caminhadas de 4 quadros (<code>player_walk_*</code>). <code>player.png</code> e <code>player_walk.png</code> saíram do contrato.</li>
    <li>As prévias foram refeitas com a regra nova. Chão, água, minério, máquinas, pod e plantas não mudaram.</li>
  </ul></div>
</header>

<section><h2>Prévia das cenas (960×540, tamanho real)</h2><div class="pvs">{previews}</div></section>

{"".join(groups_html)}

<section><h2>Drill automática · pro Dev</h2>
<div class="box dev"><table class="tb"><thead><tr><th>Item</th><th>Valor</th></tr></thead><tbody>
<tr><td>Quadro</td><td><code>machine_drill.png</code>: 4 quadros de 64×80 na horizontal; quadro <code>f</code> = recorte <code>(64·f, 0, 64, 80)</code>. Tocar a ~8 fps enquanto trabalha; parada (cheia) = quadro 0 fixo.</td></tr>
<tr><td>Âncora</td><td>Centro da base dos 2×2: <code>ax = (vx + 1)·32</code>, <code>ay = (vy + 2)·32</code>, com <code>(vx, vy)</code> = tile de cima/esquerda do veio. Blit em <code>(ax − 32, ay − 80)</code>. Os 64×64 de baixo do quadro casam com os 2×2; os 16 px de cima são a cabeça, que sobe pro tile de cima.</td></tr>
<tr><td>Indicador de nível</td><td>Retângulo <code>(x, y, w, h) = {DRILL_GAUGE}</code> dentro do quadro. Encher de baixo pra cima: <code>altura = round(h · conteúdo/20)</code>, desenhar em <code>(x, y + h − altura, w, altura)</code> com a cor do minério (ferro <code>#e8a066</code>, silício <code>#c3d1e2</code>, gelo <code>#a6ecff</code>). Vazio já vem pintado de azul-escuro no PNG.</td></tr>
<tr><td>Ordem de desenho</td><td>O veio é chão: desenha junto com o chão, antes de paredes e objetos, em <code>(vx·32, vy·32)</code>. A drill é objeto: entra na ordenação por <code>ay</code> com o resto. O veio continua visível pela moldura vazada.</td></tr>
</tbody></table></div>
</section>

<section><h2>Broca · encaixe na mão</h2>
<figure class="pv"><img src="drill_preview.png" width="1200" height="336" alt="Player com a broca nas 3 direções, 6×"><figcaption><b>Lado · baixo · cima</b><span>player parado + quadro 0 da broca, ampliado 6×</span></figcaption></figure>
<div class="box dev" style="margin-top:18px"><h3>Offsets pro Dev</h3>
<table class="tb"><thead><tr><th>Direção</th><th>Sprite (quadro)</th><th>Offset do blit (x, y)</th><th>Ordem</th></tr></thead><tbody>
{"".join(f"<tr><td>{v}</td><td><code>drill_{v}.png</code> ({'24×16' if v == 'side' else '16×24'})</td><td><code>({o[0][0]}, {o[0][1]})</code></td><td>{'<b>antes</b> do player (fica atrás)' if o[1] == 'antes' else '<b>depois</b> do player (fica na frente)'}</td></tr>" for v, o in DRILL_OFFSET.items())}
</tbody></table>
<ul><li>O offset é medido a partir do canto superior esquerdo do quadro do player (32×32): <code>broca = (px + dx, py + dy)</code>.</li>
<li>Lado espelhado (pra esquerda): espelhe a broca também e use <code>dx' = 32 − dx − 24</code>, que dá <code>{32 - DRILL_OFFSET["side"][0][0] - 24}</code>; o <code>dy</code> não muda.</li>
<li>O quadro da broca é independente do quadro do player. Toque os 4 quadros em loop a ~12–15 fps enquanto o botão estiver pressionado. O tremor de 1 px já está nos quadros.</li>
<li>A ponta de <code>drill_down</code> passa 16 px pra baixo do quadro do player e a de <code>drill_side</code> passa 4 px pra direita: é de propósito, ela entra no tile que está sendo minerado. Faíscas e lascas são do jogo.</li></ul></div>
</section>

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
    make_drill_preview(spr).save(REP / "drill_preview.png")
    build_report(spr)
    print(f"{len(canv)} sprites em {OUT.relative_to(ROOT)}, 3 prévias + index.html em {REP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
