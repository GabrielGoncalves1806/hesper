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

import explorer as ex          # v6.0: personagem novo (Explorador, visor dourado), aprovado pelo dono
import hand_drill as hd        # v6.0: broca de mão, 3 candidatas (A, B, C) em _pending/

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "sprites"
PENDING = OUT / "_pending"  # assets novos aguardando aprovação do dono
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


# ---------------------------------------------------------------- minérios v2.3: estilo "chunky" com contorno

OUTLINE = "#1b1630"  # mesmo contorno do astronauta e da broca
ORE_STYLE = {
    "iron": dict(hi="#fff1dc", light="#f4a868", mid="#d9763a", dark="#9e4c24", deep="#6e3417"),
    "silicon": dict(hi="#ffffff", light="#e3ebf5", mid="#c3d1e2", dark="#7d8ca3", deep="#4f5a70"),
    "ice": dict(hi="#ffffff", light="#cdf6ff", mid="#8fe0f8", dark="#4fb3d6", deep="#2f7fa6"),
}


def shape_block(w, h, r=1):
    m = np.ones((h, w), bool)
    if r:
        for (y, x) in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)):
            m[y, x] = False
    return m


def shape_lump(w, h, seed=0):
    """Pepita gordinha: elipse com um lado achatado e um calombo, contorno irregular mas sem ponta."""
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    m = ((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2 <= 1.15
    m[h - 1, :] &= np.abs(xs[0] - w / 2) < w / 2 - 1
    if seed % 2:
        m[0, : w // 2] = False
    else:
        m[0, w // 2:] = False
    return m


def shape_shard(w, h, lean):
    """Lasca grossa inclinada, de topo rombudo (nada pontudo)."""
    W = w + abs(lean)
    m = np.zeros((h, W), bool)
    for y in range(h):
        off = round(lean * (h - 1 - y) / max(1, h - 1)) if lean > 0 else round(-lean * y / max(1, h - 1))
        x0 = off + (1 if y == 0 else 0)
        x1 = off + w - (1 if y == 0 else 0)
        m[y, x0:x1] = True
    return m


def paint_piece(cv: Canvas, m: np.ndarray, x, y, S, kind, base=2):
    """Pinta uma peça chunky: faixas chapadas (claro em cima/esquerda, escuro embaixo/direita),
    1 brilho, contorno de 1 px e base de 2 px. Cada peça ganha seu próprio contorno (separa as peças)."""
    h, w = m.shape
    layer = Canvas(cv.w, cv.h)
    up = np.zeros_like(m); up[1:] = m[:-1]
    dn = np.zeros_like(m); dn[:-1] = m[1:]
    lf = np.zeros_like(m); lf[:, 1:] = m[:, :-1]
    rt = np.zeros_like(m); rt[:, :-1] = m[:, 1:]
    for j in range(h):
        for i in range(w):
            if not m[j, i]:
                continue
            if not dn[j, i] or not rt[j, i]:
                c = S["dark"]
            elif not up[j, i] or (kind == "cube" and j < 2) or not lf[j, i]:
                c = S["light"]
            else:
                c = S["mid"]
            if kind == "slab" and j % 3 == 1 and 1 < i < w - 2 and (i + j) % 5 != 0 and dn[j, i] and up[j, i]:
                c = S["light"]                               # camadas do ferro
            if kind == "cube" and j == 2 and rt[j, i] and lf[j, i] and dn[j, i]:
                c = S["dark"]                                # aresta entre topo e frente do cubo
            layer.px(x + i, y + j, C(c))
    # brilho: 2 px perto do canto de cima/esquerda
    ys, xs = np.nonzero(m)
    top = ys.min()
    xl = xs[ys == top].min()
    layer.px(x + xl + 1, y + top + 1, C(S["hi"]))
    if kind != "slab":
        layer.px(x + xl + 1, y + top + 2, C(S["hi"]))
    else:
        layer.px(x + xl + 2, y + top + 1, C(S["hi"]))
    layer.outline(C(OUTLINE))
    # base mais grossa: mais 1 px de contorno embaixo
    a = layer.a
    op = a[:, :, 3] == 255
    below = np.zeros_like(op); below[1:] = op[:-1]
    if base >= 2:
        a[below & ~op] = C(OUTLINE)
    cv.paste(layer, 0, 0)


def ore_piece(cv, name, x, y, size, S, seed=0, base=2):
    if name == "iron":
        w, h = size + 2, max(5, size)
        paint_piece(cv, shape_lump(w, h, seed), x, y, S, "slab", base)
    elif name == "silicon":
        w, h = max(3, size - 2), size + 3
        paint_piece(cv, shape_shard(w + 1, h, 2 if seed % 3 != 2 else 1), x, y, S, "shard", base)
    else:
        paint_piece(cv, shape_block(size, size, 0), x, y, S, "cube", base)


ORE_PIECES = {
    # (x, y, tamanho) de trás pra frente; poucas peças, pra rocha continuar aparecendo
    "iron": [(4, 4, 7), (17, 3, 6), (10, 13, 8), (21, 19, 5)],
    "silicon": [(3, 3, 6), (9, 5, 7), (20, 4, 6), (12, 16, 6), (23, 18, 5)],
    "ice": [(4, 4, 7), (19, 3, 7), (10, 15, 7), (22, 18, 5)],
}


def make_ore(name: str) -> Canvas:
    S = ORE_STYLE[name]
    cv = Canvas(T, T)
    for i, (x, y, sz) in enumerate(ORE_PIECES[name]):
        ore_piece(cv, name, x, y, sz, S, i)
    return cv


def make_icon(name: str) -> Canvas:
    S = ORE_STYLE[name]
    cv = Canvas(16, 16)
    if name == "iron":                       # dois lingotes/placas de cobre empilhados
        paint_piece(cv, shape_lump(10, 8, 1), 1, 2, S, "slab")
        paint_piece(cv, shape_lump(8, 7, 0), 7, 7, S, "slab")
    elif name == "silicon":                  # três lascas grossas num toco de rocha escura
        rock = Canvas(16, 16)
        rock.rect(2, 10, 12, 3, C("#4a4458"))
        rock.rect(2, 10, 12, 1, C("#615a72"))
        rock.rect(12, 11, 2, 2, C("#332e40"))
        rock.outline(C(OUTLINE))
        paint_piece(cv, shape_shard(4, 9, 2), 2, 2, S, "shard", 1)
        paint_piece(cv, shape_shard(4, 7, -2), 9, 4, S, "shard", 1)
        cv.paste(rock, 0, 0)
        paint_piece(cv, shape_shard(4, 8, 1), 6, 4, S, "shard", 1)
    else:                                     # três cubos de gelo
        paint_piece(cv, shape_block(6, 6, 0), 1, 8, S, "cube", 1)
        paint_piece(cv, shape_block(6, 6, 0), 9, 8, S, "cube", 1)
        paint_piece(cv, shape_block(7, 7, 0), 4, 1, S, "cube", 1)
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
        cell.alpha_composite(spr[f"player_mine_{view}.png"].crop((0, 0, 32, 32)), (ox, oy))   # v6.0: pose de minerar
        if order == "depois":
            cell.alpha_composite(d, (ox + dx, oy + dy))
        cells.append(cell)
    out = Image.new("RGBA", (64 * 3 + 8, 56), (21, 16, 14, 255))
    for i, c in enumerate(cells):
        out.alpha_composite(c, (i * 68, 0))
    return out.resize((out.width * 6, out.height * 6), Image.NEAREST).convert("RGB")


# ---------------------------------------------------------------- veios e drill automática (v2.2)

def vein_mask(seed, rx, ry, cx=32, cy=36, wob=0.22):
    ys, xs = np.mgrid[0:64, 0:64] + 0.5
    ang = np.arctan2(ys - cy, xs - cx)
    r = np.hypot((xs - cx) / rx, (ys - cy) / ry)
    # borda orgânica: raio varia com o ângulo (soma de senos com fase da seed)
    k = 1 + wob * (0.55 * np.sin(3 * ang + seed) + 0.3 * np.sin(5 * ang + seed * 2.1) + 0.15 * np.sin(9 * ang + seed * 0.7))
    return r <= k


VEIN_SOIL = (0, 0, 0, 48)       # mancha de terra bem sutil (1 nível de alpha)
RUBBLE = ["#4a3f3a", "#6b5d55", "#8a7b70"]  # pedrisco neutro, funciona nos 3 chãos

PLATE = {
    # placas do veio no estilo chunky: tampa chapada, bisel claro, borda escura, fratura clara
    "iron": dict(body="#c9693a", light="#f0a062", edge="#94461f", frac="#ffd0a0", speck="#a8552b"),
    "silicon": dict(body="#a9b8cf", light="#e3ebf5", edge="#6f7f99", frac="#ffffff", speck="#8f9fb8"),
    "ice": dict(body="#8fe0f8", light="#d2f7ff", edge="#3f9fc6", frac="#ffffff", speck="#b3ecfb"),
}


def poly_mask(pts, w=64, h=64):
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    inside = np.zeros((h, w), bool)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        cond = (y1 > ys) != (y2 > ys)
        xint = (x2 - x1) * (ys - y1) / ((y2 - y1) if y2 != y1 else 1e-9) + x1
        inside ^= cond & (xs < xint)
    return inside


def plate_poly(cx, cy, rx, ry, rot, nv, s, jag):
    """Polígono anguloso: nv vértices com ângulo e raio sorteados, girado e achatado (vista de cima/3-4)."""
    pts = []
    for i in range(nv):
        a = (i + (hsh(i, 1, s) - 0.5) * jag) * 2 * math.pi / nv
        r = 1 - jag * 0.35 * hsh(i, 2, s)
        x, y = math.cos(a) * rx * r, math.sin(a) * ry * r
        xr = x * math.cos(rot) - y * math.sin(rot)
        yr = x * math.sin(rot) + y * math.cos(rot)
        pts.append((cx + xr, cy + yr * 0.8))
    return pts


VEIN_PLATES = {
    # (cx, cy, rx, ry, rot, vértices, jag): ferro = lajes rugosas; silício = lascas finas sobrepostas;
    # gelo = placas lisas de arestas retas
    "iron": [(19, 19, 11, 8, 0.3, 5, 0.75), (40, 17, 9, 7, 1.2, 5, 0.75), (52, 31, 7, 8, 0.1, 5, 0.75),
             (13, 37, 8, 9, 2.0, 5, 0.75), (31, 34, 12, 9, 0.7, 5, 0.75), (47, 47, 9, 8, 2.4, 5, 0.75),
             (22, 51, 10, 7, 1.5, 5, 0.75), (37, 55, 6, 5, 0.4, 5, 0.75)],
    "silicon": [(20, 17, 13, 5.2, 0.45, 6, 0.55), (25, 22, 11, 5.2, 0.4, 6, 0.55), (43, 19, 11, 5.2, -0.4, 6, 0.55),
                (13, 34, 10, 5.2, 0.2, 6, 0.55), (31, 32, 14, 5.7, 0.55, 6, 0.55), (36, 37, 11, 5.2, 0.5, 6, 0.55),
                (51, 34, 9, 5.2, -0.6, 6, 0.55), (21, 48, 12, 5.2, -0.3, 6, 0.55), (27, 52, 9, 5.2, -0.25, 6, 0.55),
                (46, 50, 11, 5.2, 0.4, 6, 0.55)],
    "ice": [(19, 20, 11, 9, 0.2, 4, 0.12), (40, 18, 9, 8, 0.9, 5, 0.12), (52, 34, 7, 8, 0.3, 4, 0.12),
            (14, 38, 8, 8, 1.1, 5, 0.12), (32, 35, 12, 10, 0.75, 4, 0.12), (47, 48, 9, 8, 0.1, 5, 0.12),
            (25, 52, 10, 7, 0.5, 4, 0.12)],
}


def make_vein(name: str) -> Canvas:
    O, Pc = ORES[name], PLATE[name]
    sd = {"iron": 1.3, "silicon": 2.9, "ice": 4.4}[name]
    si = int(sd * 10)
    cv = Canvas(64, 64)
    soil = vein_mask(sd, 29, 25)
    cv.a[soil] = VEIN_SOIL
    for k, (cx, cy, rx, ry, rot, nv, jag) in enumerate(VEIN_PLATES[name]):
        top = poly_mask(plate_poly(cx, cy, rx, ry, rot, nv, si + k * 7, jag))
        ring = np.zeros_like(top)                     # contorno escuro de 1 px + 2 px de espessura embaixo
        ring[1:, :] |= top[:-1, :]; ring[2:, :] |= top[:-2, :]
        ring[:-1, :] |= top[1:, :]
        ring[:, 1:] |= top[:, :-1]; ring[:, :-1] |= top[:, 1:]
        cv.a[ring & ~top] = C(OUTLINE)
        up = np.roll(top, 1, 0)
        left = np.roll(top, 1, 1)
        down = np.roll(top, -1, 0)
        right = np.roll(top, -1, 1)
        cv.a[top] = C(Pc["body"])
        cv.a[top & (~down | ~right)] = C(Pc["edge"])
        cv.a[top & (~up | ~left)] = C(Pc["light"])
        ys, xs = np.nonzero(top & up & left & down & right)
        if len(xs) < 4:
            continue
        # textura: ferro rugoso (pontinhos), gelo liso com reflexo diagonal, silício com veio longitudinal
        if name == "iron":
            for i in range(len(xs)):
                if hsh(int(xs[i]), int(ys[i]), si) < 0.12:
                    cv.px(xs[i], ys[i], C(Pc["speck"]))
        elif name == "ice":
            for i in range(len(xs)):
                d = (xs[i] - ys[i] - (cx - cy)) % 9
                if d in (0, 1) and ys[i] < cy:
                    cv.px(xs[i], ys[i], C(Pc["light"]))
            cv.px(int(xs.min()) + 2, int(ys.min()) + 1, C(Pc["frac"]))
        # linhas de fratura finas e claras saindo de um ponto interno
        ox, oy = int(np.median(xs)), int(np.median(ys))
        nfr = 2 if name != "silicon" else 1
        for j in range(nfr):
            a = hsh(k, j, si) * 2 * math.pi if name != "silicon" else rot
            x, y = float(ox), float(oy)
            for _ in range(14):
                xi, yi = int(round(x)), int(round(y))
                if not (0 <= xi < 64 and 0 <= yi < 64) or not (top[yi, xi] and down[yi, xi] and right[yi, xi]):
                    break
                cv.px(xi, yi, C(Pc["frac"]))
                x += math.cos(a)
                y += math.sin(a) * (0.75 if name != "silicon" else 1)
                if name != "ice":
                    a += (hsh(k, int(x * 3), si) - 0.5) * 0.5
    # pepitas do minério (2-4 px), saturadas e contornadas, por cima das placas e em volta
    S = ORE_STYLE[name]
    spots = [(15, 21), (28, 36), (44, 20), (36, 42), (50, 46), (19, 50), (8, 41), (55, 27)]
    for i, (x, y) in enumerate(spots):
        if not soil[y, x]:
            continue
        if name == "iron":
            m = shape_lump(4 if i % 2 else 3, 3, i)
        elif name == "silicon":
            m = shape_shard(2, 4, 1 if i % 2 else -1)
        else:
            m = shape_block(3, 3, 0)
        paint_piece(cv, m, x, y, S, "nug", 1)
    # pedriscos neutros
    for i in range(10):
        x, y = int(hsh(i, 1, si) * 60) + 2, int(hsh(i, 2, si) * 60) + 2
        if not soil[y, x] or cv.a[y, x, 3] == 255:
            continue
        cv.rect(x, y, 2, 1, C(RUBBLE[1]))
        cv.px(x, y, C(RUBBLE[2]))
        cv.rect(x, y + 1, 2, 1, C(RUBBLE[0]))
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


# ---------------------------------------------------------------- v0.2 (pendentes): baú, painel, estação, drone, ícones, slot

MT = dict(w="#f4f6f8", l="#e1e5ea", m="#c8cdd4", s="#abb2bb", d="#8c949e", g="#6b717a", k="#3b3f46", kk="#2a2d33",
          o="#e2733a", oh="#f29a62", od="#a8471f", led="#7fd67a", ledh="#d6ffd0", red="#ff5a4a")


def _m(cv, x, y, w, h, c):
    cv.rect(x, y, w, h, C(MT[c]) if c in MT else C(c))


def make_chest(open_: bool) -> Canvas:
    """Container de carga 32x40 (v3.1): bloco de metal com topo visível, frente corrugada,
    cantoneiras reforçadas, pés de empilhamento, porta com alavanca e LED. Base na última linha útil."""
    cv = Canvas(32, 40)
    cv.ellipse(16, 37.5, 15, 2.5, SHADOW)
    body = Canvas(32, 40)
    # topo (vista de cima, curto) com nervuras transversais e cantos de engate
    body.rect(4, 4, 24, 7, C(MT["l"]))
    for x in range(5, 27, 3):
        body.rect(x, 4, 1, 6, C(MT["m"]))
    body.rect(4, 4, 24, 1, C(MT["w"]))
    body.rect(4, 10, 24, 1, C(MT["s"]))
    # cantoneiras (colunas reforçadas) com rebites
    for cx in (3, 25):
        body.rect(cx, 3, 4, 32, C(MT["k"]))
        body.rect(cx, 3, 1, 32, C(MT["g"]))
        body.rect(cx + 3, 3, 1, 32, C(MT["kk"]))
        for ry in (14, 22, 30):
            body.px(cx + 1, ry, C(MT["d"]))
        body.rect(cx, 3, 4, 2, C(MT["kk"]))              # engate de empilhar (canto de cima)
    body.rect(3, 3, 26, 1, C(MT["g"]))
    # trilho de cima da frente
    body.rect(7, 11, 18, 2, C(MT["g"]))
    body.rect(7, 11, 18, 1, C(MT["d"]))
    # base e pés
    body.rect(3, 33, 26, 2, C(MT["k"]))
    body.rect(3, 33, 26, 1, C(MT["g"]))
    for fx in (3, 25):
        body.rect(fx, 35, 4, 2, C(MT["kk"]))
    if not open_:
        # porta = frente inteira, corrugada (frisos verticais fortes)
        for x in range(7, 25):
            c = MT["w"] if x % 2 == 0 else MT["s"]
            body.rect(x, 13, 1, 20, C(c))
        body.rect(7, 32, 18, 1, C(MT["d"]))
        body.rect(15, 13, 1, 20, C(MT["k"]))             # junta das duas folhas
        # faixa/stencil laranja
        body.rect(7, 15, 18, 3, C(MT["o"]))
        body.rect(7, 15, 18, 1, C(MT["oh"]))
        body.rect(7, 17, 18, 1, C(MT["od"]))
        body.rect(9, 16, 1, 1, C(MT["w"])); body.rect(11, 16, 2, 1, C(MT["w"]))
        # barras de travamento + alavancas
        for rx in (11, 19):
            body.rect(rx, 18, 1, 14, C(MT["k"]))
            body.rect(rx - 1, 25, 3, 2, C(MT["kk"]))
            body.rect(rx + 1, 25, 2, 1, C(MT["o"]))
        # LED de status
        body.rect(22, 20, 2, 2, C(MT["led"]))
        body.px(22, 20, C(MT["ledh"]))
        body.outline(C(OUTLINE))
        cv.paste(body, 0, 0)
        return cv
    # aberto: porta girada pra esquerda (vista de lado, fina) e o interior com prateleiras
    body.rect(7, 13, 18, 20, C("#1a1c22"))
    body.rect(8, 13, 16, 19, C("#262a32"))
    body.rect(8, 13, 16, 2, C("#14161b"))                # sombra do teto
    for sy in (20, 26):                                   # prateleiras
        body.rect(8, sy, 16, 1, C(MT["s"]))
        body.rect(8, sy + 1, 16, 1, C("#14161b"))
    body.rect(8, 31, 16, 1, C(MT["g"]))                  # piso
    body.rect(22, 15, 2, 2, C("#59d0e6"))                # LED ciano
    body.px(22, 15, C("#d8fbff"))
    body.outline(C(OUTLINE))
    cv.paste(body, 0, 0)
    # conteúdo nas prateleiras (estilo v2.3)
    paint_piece(cv, shape_lump(4, 3, 1), 9, 16, ORE_STYLE["iron"], "nug", 1)
    paint_piece(cv, shape_lump(3, 3, 0), 14, 16, ORE_STYLE["iron"], "nug", 1)
    paint_piece(cv, shape_block(3, 3, 0), 19, 16, ORE_STYLE["ice"], "cube", 1)
    paint_piece(cv, shape_shard(2, 3, 1), 10, 21, ORE_STYLE["silicon"], "shard", 1)
    paint_piece(cv, shape_shard(2, 3, 1), 13, 21, ORE_STYLE["silicon"], "shard", 1)
    crate = Canvas(32, 40)                                # caixinha
    crate.rect(17, 22, 5, 3, C(MT["l"]))
    crate.rect(17, 22, 5, 1, C(MT["w"]))
    crate.rect(19, 22, 1, 3, C(MT["o"]))
    crate.outline(C(OUTLINE))
    cv.paste(crate, 0, 0)
    paint_piece(cv, shape_block(3, 3, 0), 10, 27, ORE_STYLE["ice"], "cube", 1)
    paint_piece(cv, shape_lump(3, 2, 1), 16, 28, ORE_STYLE["iron"], "nug", 1)
    # porta aberta: painel fino girado pra fora, à esquerda, sobre a cantoneira
    door = Canvas(32, 40)
    for i, y0 in enumerate(range(15, 33)):
        door.rect(0, y0 - (1 if i < 2 else 0), 4, 1, C(MT["l"] if i % 2 else MT["m"]))
    door.rect(0, 14, 4, 1, C(MT["w"]))
    door.rect(3, 15, 1, 17, C(MT["s"]))
    door.rect(1, 22, 2, 3, C(MT["o"]))
    door.outline(C(OUTLINE))
    cv.paste(door, 0, 0)
    return cv


def make_solar() -> Canvas:
    """Painel solar 32x40: placa inclinada (células azul-escuras, grade e reflexo) num poste."""
    cv = Canvas(32, 40)
    cv.ellipse(16, 37.5, 13, 2.5, SHADOW)
    # base e poste
    _m(cv, 9, 32, 14, 6, INK)
    _m(cv, 10, 33, 12, 4, "s")
    _m(cv, 10, 33, 12, 1, "l")
    _m(cv, 10, 35, 12, 1, "o")
    _m(cv, 13, 22, 6, 11, INK)
    _m(cv, 14, 22, 4, 11, "m")
    _m(cv, 14, 22, 1, 11, "w")
    _m(cv, 17, 22, 1, 11, "d")
    _m(cv, 11, 34, 2, 1, "led")
    # suporte em V
    _m(cv, 10, 21, 12, 3, INK)
    _m(cv, 11, 22, 10, 1, "g")
    # placa: topo mais estreito (vai pra trás) -> trapézio, com espessura embaixo
    top, bot = 3, 20
    for y in range(top, bot + 1):
        t = (y - top) / (bot - top)
        inset = round(3 * (1 - t))
        x0, x1 = 1 + inset, 31 - inset
        cv.rect(x0, y, x1 - x0, 1, C(INK))
        if y in (top, bot):
            continue
        cv.rect(x0 + 1, y, x1 - x0 - 2, 1, C("#1f3a6e"))
        # grade de células (4 colunas x 3 linhas), linhas finas mais claras
        for k in range(1, 4):
            gx = x0 + 1 + round((x1 - x0 - 2) * k / 4)
            cv.px(gx, y, C("#4f74b8"))
        if (y - top) in (6, 12):
            cv.rect(x0 + 1, y, x1 - x0 - 2, 1, C("#4f74b8"))
        cv.px(x0 + 1, y, C("#c8cdd4"))                  # moldura prateada
        cv.px(x1 - 2, y, C("#8c949e"))
        # tom um pouco mais claro na metade de cima de cada célula
        if (y - top) % 6 in (1, 2):
            for x in range(x0 + 2, x1 - 2):
                if cv.get(x, y)[:3] == C("#1f3a6e")[:3]:
                    cv.px(x, y, C("#2a4f8f"))
        # reflexo diagonal
        for x in range(x0 + 1, x1 - 1):
            d = x - (y - top) * 1.1
            if 7 <= d < 10 or 17 <= d < 18:
                cv.px(x, y, C("#9fc4f5" if 7 <= d < 9 or 17 <= d < 18 else "#6e98dc"))
    _m(cv, 2, bot, 28, 1, "#c8cdd4")                    # aresta da frente
    _m(cv, 2, bot + 1, 28, 1, INK)
    cv.rect(4, top + 1, 1, 1, C("#ffffff"))
    return cv


STATION_PADS = [(18, 44), (46, 44)]   # centro do drone pousado, relativo ao PNG da estação


def make_station() -> Canvas:
    """Estação de drones 64x72: plataforma 2x2 com 2 pads marcados e torre de antena. Base em y=71."""
    cv = Canvas(64, 72)
    cv.ellipse(32, 67, 31, 4.5, SHADOW)
    # plataforma: topo (vista de cima) + face frontal
    _m(cv, 1, 26, 62, 42, INK)
    _m(cv, 2, 27, 60, 33, "#4a4f57")
    _m(cv, 2, 27, 60, 1, "g")
    _m(cv, 2, 27, 1, 33, "g")
    _m(cv, 61, 28, 1, 32, "k")
    _m(cv, 2, 60, 60, 7, "s")                           # face da frente
    _m(cv, 2, 60, 60, 1, "l")
    _m(cv, 2, 66, 60, 1, "d")
    hazard(cv, 4, 62, 28)                               # faixa de alerta
    for fx in (2, 58):                                  # pés
        _m(cv, fx, 67, 4, 3, "kk")
    # pads de pouso: anel laranja + "H" claro
    for px_, py_ in STATION_PADS:
        cv.ellipse(px_, py_, 10, 7.5, C("#2f3338"))
        cv.ellipse(px_, py_, 9, 6.5, C(MT["o"]))
        cv.ellipse(px_, py_, 7, 5, C("#2f3338"))
        _m(cv, px_ - 3, py_ - 3, 1, 6, "l")
        _m(cv, px_ + 2, py_ - 3, 1, 6, "l")
        _m(cv, px_ - 2, py_, 4, 1, "l")
        for dx in (-10, 9):
            cv.px(px_ + dx, py_, C(MT["led"]))
    _m(cv, 31, 28, 2, 31, "#3b3f46")                    # divisória
    for yy in (36, 52):                                 # emendas das chapas + rebites
        _m(cv, 3, yy, 27, 1, "#575d66")
        _m(cv, 34, yy, 27, 1, "#575d66")
    for rx_, ry_ in ((4, 29), (28, 29), (35, 29), (59, 29), (4, 57), (28, 57), (35, 57), (59, 57)):
        cv.px(rx_, ry_, C(MT["d"]))
    # torre de antena atrás, à direita
    _m(cv, 50, 4, 6, 24, INK)
    _m(cv, 51, 4, 4, 24, "m")
    _m(cv, 51, 4, 1, 24, "w")
    _m(cv, 54, 4, 1, 24, "d")
    for yy in (9, 15, 21):
        _m(cv, 51, yy, 4, 1, "o")
    _m(cv, 47, 10, 12, 1, INK)
    _m(cv, 52, 0, 2, 4, "g")
    _m(cv, 51, 0, 4, 2, "red")
    cv.px(51, 0, C("#ffb3a8"))
    # módulo de controle atrás, à esquerda
    _m(cv, 6, 14, 18, 13, INK)
    _m(cv, 7, 15, 16, 11, "l")
    _m(cv, 7, 15, 16, 2, "w")
    _m(cv, 21, 15, 2, 11, "s")
    _m(cv, 9, 19, 9, 4, "#14202b")
    _m(cv, 10, 20, 3, 1, "#59d0e6")
    _m(cv, 10, 22, 6, 1, "#59d0e6")
    _m(cv, 19, 19, 2, 2, "led")
    _m(cv, 7, 24, 16, 1, "o")
    return cv


def make_drone_frame(f: int) -> Canvas:
    """Drone 16x16 em 3/4: corpo branco/laranja 8x7, 4 braços, hélices girando (45° por quadro)."""
    cv = Canvas(16, 16)
    rotors = [(2, 3), (13, 3), (2, 12), (13, 12)]
    for rx, ry in rotors:                                # braços
        x, y = 7 + (rx > 7), 7 + (ry > 7)
        while (x, y) != (rx, ry):
            cv.px(x, y, C(MT["k"]))
            x += (rx > x) - (rx < x)
            y += (ry > y) - (ry < y)
    blades = [((-2, 0), (2, 0)), ((-2, -1), (2, 1)), ((0, -2), (0, 2)), ((-2, 1), (2, -1))]
    for i, (rx, ry) in enumerate(rotors):
        (ax, ay), (bx, by) = blades[(f + i) % 4]
        for t in range(5):
            x = round(ax + (bx - ax) * t / 4)
            y = round(ay + (by - ay) * t / 4)
            cv.px(rx + x, ry + y, C("#eef2f8" if t in (0, 4) else "#aab3c2"))
        cv.px(rx, ry, C(MT["kk"]))
    body = Canvas(16, 16)
    body.rect(4, 4, 8, 7, C(MT["w"]))
    body.rect(4, 9, 8, 2, C(MT["m"]))
    body.rect(10, 5, 2, 6, C(MT["s"]))
    body.rect(4, 7, 8, 2, C(MT["o"]))
    body.rect(4, 7, 8, 1, C(MT["oh"]))
    body.rect(6, 4, 3, 2, C("#2b7f99"))
    body.px(6, 4, C("#59d0e6"))
    for x, y in ((4, 4), (11, 4), (4, 10), (11, 10)):
        body.a[y, x] = 0
    body.outline(C(INK))
    cv.paste(body, 0, 0)
    cv.px(10, 9, C(MT["led"] if f % 2 == 0 else "#2f5a2c"))
    return cv


def make_drone_sheet() -> Canvas:
    sheet = Canvas(64, 16)
    for f in range(4):
        sheet.paste(make_drone_frame(f), f * 16, 0)
    return sheet


def make_icon_chest() -> Canvas:
    """Container visto de frente: frente corrugada, faixa laranja, barras de trava, LED, cantoneiras e pés."""
    cv = Canvas(16, 16)
    lay = Canvas(16, 16)
    lay.rect(2, 1, 12, 2, C(MT["l"]))
    lay.rect(2, 1, 12, 1, C(MT["w"]))
    for x in range(4, 12):
        lay.rect(x, 3, 1, 9, C(MT["w"] if x % 2 == 0 else MT["s"]))
    lay.rect(4, 4, 8, 2, C(MT["o"]))
    lay.rect(4, 4, 8, 1, C(MT["oh"]))
    for rx in (6, 9):
        lay.rect(rx, 6, 1, 6, C(MT["k"]))
    lay.px(7, 9, C(MT["o"])); lay.px(10, 9, C(MT["o"]))
    lay.px(11, 7, C(MT["led"]))
    for cx in (2, 12):
        lay.rect(cx, 1, 2, 12, C(MT["k"]))
        lay.rect(cx, 1, 1, 12, C(MT["g"]))
    lay.rect(2, 12, 12, 1, C(MT["k"]))
    lay.rect(2, 13, 2, 1, C(MT["kk"])); lay.rect(12, 13, 2, 1, C(MT["kk"]))
    lay.outline(C(OUTLINE))
    cv.paste(lay, 0, 0)
    return cv


def make_icon_solar() -> Canvas:
    cv = Canvas(16, 16)
    lay = Canvas(16, 16)
    lay.rect(7, 10, 2, 3, C(MT["m"]))
    lay.rect(5, 12, 6, 2, C(MT["s"]))
    lay.rect(5, 12, 6, 1, C(MT["l"]))
    for y in range(2, 10):
        inset = round(2 * (1 - (y - 2) / 7))
        lay.rect(1 + inset, y, 14 - 2 * inset, 1, C("#1f3a6e"))
        lay.px(1 + inset, y, C("#c8cdd4"))
        lay.px(14 - inset, y, C("#8c949e"))
    for y in range(3, 9):
        lay.px(8, y, C("#4f74b8"))
    lay.rect(3, 5, 10, 1, C("#4f74b8"))
    for x, y in ((4, 3), (5, 3), (3, 4), (4, 4), (10, 6), (11, 6)):
        lay.px(x, y, C("#9fc4f5"))
    lay.px(4, 3, C("#ffffff"))
    lay.rect(1, 9, 14, 1, C("#c8cdd4"))
    lay.outline(C(OUTLINE))
    cv.paste(lay, 0, 0)
    return cv


def make_icon_station() -> Canvas:
    cv = Canvas(16, 16)
    lay = Canvas(16, 16)
    lay.rect(1, 8, 14, 5, C("#4a4f57"))
    lay.rect(1, 8, 14, 1, C(MT["g"]))
    lay.rect(1, 12, 14, 2, C(MT["s"]))
    lay.rect(1, 12, 14, 1, C(MT["l"]))
    lay.rect(3, 9, 4, 3, C(MT["o"]))
    lay.rect(4, 10, 2, 1, C("#2f3338"))
    lay.rect(12, 2, 2, 7, C(MT["m"]))
    lay.px(12, 1, C(MT["red"]))
    lay.px(13, 1, C(MT["red"]))
    lay.outline(C(OUTLINE))
    cv.paste(lay, 0, 0)
    # mini drone pousado
    d = Canvas(16, 16)
    d.rect(8, 7, 3, 3, C(MT["w"]))
    d.rect(8, 8, 3, 1, C(MT["o"]))
    d.px(7, 6, C("#aab3c2")); d.px(11, 6, C("#aab3c2"))
    d.outline(C(OUTLINE))
    cv.paste(d, 0, 0)
    return cv


def make_icon_drone() -> Canvas:
    """Ícone de item do drone (parado): corpo branco com faixa laranja e visor ciano,
    4 braços com hélices paradas e pezinhos de pouso. Contorno #1b1630, como os outros ícones."""
    cv = Canvas(16, 16)
    rig = Canvas(16, 16)
    for (rx, ry) in ((2, 3), (13, 3), (2, 10), (13, 10)):
        x, y = 7 + (rx > 7), 6 + (ry > 6)
        while (x, y) != (rx, ry):                       # braço
            rig.px(x, y, C(MT["k"]))
            x += (rx > x) - (rx < x)
            y += (ry > y) - (ry < y)
        rig.rect(rx - 2, ry - 1, 5, 1, C("#dfe5ee"))     # hélice parada (pás na horizontal)
        rig.px(rx - 2, ry - 1, C("#aab3c2"))
        rig.px(rx + 2, ry - 1, C("#aab3c2"))
        rig.px(rx, ry, C(MT["kk"]))                     # cubo do rotor
    rig.rect(5, 12, 1, 2, C(MT["g"]))                   # pezinhos
    rig.rect(10, 12, 1, 2, C(MT["g"]))
    rig.rect(4, 13, 3, 1, C(MT["k"]))
    rig.rect(9, 13, 3, 1, C(MT["k"]))
    rig.outline(C(OUTLINE))
    cv.paste(rig, 0, 0)
    body = Canvas(16, 16)
    body.rect(4, 4, 8, 8, C(MT["w"]))
    body.rect(4, 10, 8, 2, C(MT["m"]))
    body.rect(10, 5, 2, 7, C(MT["s"]))
    body.rect(4, 7, 8, 2, C(MT["o"]))
    body.rect(4, 7, 8, 1, C(MT["oh"]))
    body.rect(6, 4, 4, 2, C("#2b7f99"))
    body.rect(6, 4, 2, 1, C("#59d0e6"))
    body.px(6, 4, C("#d8fbff"))
    body.px(10, 10, C(MT["led"]))
    for x, y in ((4, 4), (11, 4), (4, 11), (11, 11)):
        body.a[y, x] = 0
    body.outline(C(OUTLINE))
    cv.paste(body, 0, 0)
    return cv


def make_slot_preview(spr: dict[str, Image.Image], icon_key: str, ref_key: str) -> Image.Image:
    """ui_slot + ícone em 1x, 2x e 3x (o jogo escala slot e ícone juntos; ícone em (2,2) no slot 1x)."""
    slot = spr["ui_slot.png"]
    out = Image.new("RGBA", (12 + 2 * (20 + 40 + 60 + 3 * 12 + 12), 60 + 24), C("#15100e"))
    x = 12
    for key in (icon_key, ref_key):
        for k in (1, 2, 3):
            sl = slot.resize((20 * k, 20 * k), Image.NEAREST)
            ic = spr[key].resize((16 * k, 16 * k), Image.NEAREST)
            y = 12 + (60 - 20 * k)
            out.alpha_composite(sl, (x, y))
            out.alpha_composite(ic, (x + 2 * k, y + 2 * k))
            x += 20 * k + 12
        x += 12
    return out


def make_ui_slot() -> Canvas:
    cv = Canvas(20, 20)
    cv.rect(0, 0, 20, 20, C("#4a382f"))
    cv.rect(1, 1, 18, 18, C("#1e1714"))
    cv.rect(1, 1, 18, 1, C("#120d0b"))                  # sombra interna em cima/esquerda
    cv.rect(1, 1, 1, 18, C("#120d0b"))
    cv.rect(2, 18, 17, 1, C("#2c211c"))                 # luz interna embaixo/direita
    cv.rect(18, 2, 1, 17, C("#2c211c"))
    for x, y in ((0, 0), (19, 0), (0, 19), (19, 19)):
        cv.a[y, x] = 0
    for x, y in ((1, 1), (18, 1), (1, 18), (18, 18)):
        cv.px(x, y, C("#4a382f"))
    return cv


# ---------------------------------------------------------------- v0.3 · Marco 1 · superfície (aprovados na v4.0)

SAND = {
    # base, faixa escura, faixa clara, grão escuro, grão claro, sombra da ondulação, crista,
    # pedrisco (escuro/claro), laje de rocha no chão (topo/luz/borda)
    "dead": dict(base="#a4583a", d1="#985034", l1="#af6343", gD="#86452c", gL="#bf7350",
                 rip="#874630", crest="#c47b56", peb="#6c3626", pebL="#c98563",
                 slab="#94503a", slabL="#b46b4c", slabD="#7a412e"),
    "mist": dict(base="#787677", d1="#6e6c6e", l1="#838183", gD="#5e5c5f", gL="#959397",
                 rip="#605e61", crest="#9a989b", peb="#4b494d", pebL="#a2a0a3",
                 slab="#6b6869", slabL="#888587", slabD="#575455",
                 wet="#666568", sheen="#a9b6bd"),
    "green": dict(base="#a08e66", d1="#94835d", l1="#ab9a71", gD="#80714e", gL="#bcab82",
                  rip="#85754f", crest="#bfae85", peb="#5f5644", pebL="#c4b48c",
                  slab="#8e8366", slabL="#ada282", slabD="#766c52",
                  grass="#79b04f", grass2="#5e9640", moss="#5c9a43", moss2="#7cba58", mossD="#3f7230"),
}
SAND_KIND = ["areia", "cascalho", "dunas", "rocha"]


def _blob(cv: Canvas, cx, cy, rx, ry, col, s, margin=1):
    """Mancha chapada e achatada (elipse com borda serrilhada), sempre dentro do tile: emenda garantida."""
    for y in range(int(cy - ry - 1), int(cy + ry + 2)):
        for x in range(int(cx - rx - 1), int(cx + rx + 2)):
            if not (margin <= x < T - margin and margin <= y < T - margin):
                continue
            wob = (hsh(x // 2, y, s) - 0.5) * 0.35
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0 + wob:
                cv.px(x, y, C(col))


def make_sand(stage: str, v: int) -> Canvas:
    """Chão do deserto 32x32. Nada encosta na borda (emenda garantida) e a v0, que domina o mapa,
    é quase lisa: só grão de 1 px e risquinhos de vento, sem motivo que vire grade.
    v0 areia · v1 cascalho · v2 ondulação de duna · v3 laje de rocha no chão (as três raras e fora do centro)."""
    P = SAND[stage]
    s = STAGE_SEED[stage] * 1000 + v * 131 + 7
    cv = Canvas(T, T)
    cv.rect(0, 0, T, T, C(P["base"]))

    def free(x, y):
        return 1 <= x < T - 1 and 1 <= y < T - 1 and cv.get(x, y)[:3] == C(P["base"])[:3]

    # risquinhos de vento (faixas chapadas de 2-5 px, tom quase igual ao fundo)
    for i in range(4):
        x, y = 2 + int(hsh(i, 1, s) * 24), 2 + int(hsh(i, 2, s) * 28)
        w = 2 + int(hsh(i, 3, s) * 4)
        cv.rect(x, y, w, 1, C(P["d1"] if i % 2 else P["l1"]))
    if v == 1:                                               # cascalho: um bolo fora do centro
        ox, oy = [(7, 8), (22, 20), (8, 22), (21, 7)][int(hsh(0, 4, s) * 4)]
        for i in range(6):
            x = ox + int((hsh(i, 12, s) - 0.5) * 9)
            y = oy + int((hsh(i, 13, s) - 0.5) * 7)
            if i < 3:
                cv.rect(x, y, 2, 1, C(P["pebL"]))
                cv.rect(x, y + 1, 2, 1, C(P["peb"]))
            else:
                cv.px(x, y, C(P["peb"]))
    if v == 2:                                               # ondulações baixas (faixa clara + sombra)
        x0 = 3 + int(hsh(0, 5, s) * 8)
        y0 = 5 + int(hsh(0, 6, s) * 6)
        ph = hsh(0, 7, s) * 6.28
        for k in range(3):
            ln = 9 + int(hsh(k, 8, s) * 9)
            xs = x0 + int(hsh(k, 9, s) * 6)
            ys = y0 + k * 8
            for j in range(ln):
                x = xs + j
                if x > T - 3 or ys > T - 4:
                    break
                y = ys + int(round(1.2 * math.sin(j * 0.35 + ph + k)))
                cv.px(x, y, C(P["gL"] if 1 < j < ln - 2 else P["l1"]))
                cv.px(x, y + 1, C(P["rip"] if 1 < j < ln - 2 else P["d1"]))
    if v == 3:                                               # laje pequena nivelada com o chão
        lx, ly = 15, 15
        m = poly_mask(plate_poly(lx, ly, 12, 10, 0.3, 7, s, 0.5), T, T)
        m[:3, :] = m[-3:, :] = False
        m[:, :3] = m[:, -3:] = False
        up, dn = np.roll(m, 1, 0), np.roll(m, -1, 0)
        lf, rt = np.roll(m, 1, 1), np.roll(m, -1, 1)
        cv.a[m] = C(P["slab"])
        cv.a[m & (~up | ~lf)] = C(P["slabL"])
        cv.a[m & (~dn | ~rt)] = C(P["slabD"])
        for i in range(3):
            x, y = lx + 6 + i * 2, ly + 4 - i * 3
            if free(x, y):
                cv.px(x, y, C(P["peb"]))
    if stage == "mist" and v in (1, 3):                      # areia úmida: manchinha molhada
        wx, wy = (24, 26) if v == 1 else (6, 6)
        cv.rect(wx - 3, wy, 7, 1, C(P["wet"]))
        cv.rect(wx - 2, wy + 1, 5, 1, C(P["wet"]))
        cv.px(wx - 2, wy, C(P["sheen"]))
    if stage == "green":                                     # verde começando: brotos, musgo e 1 tufo
        for i in range(2):
            x, y = 3 + int(hsh(i, 17, s) * 26), 3 + int(hsh(i, 18, s) * 26)
            if free(x, y) and free(x, y - 1):
                cv.px(x, y, C(P["moss"]))
                cv.px(x, y - 1, C(P["grass"]))
        if v in (1, 3):
            mx, my = (23, 25) if v == 1 else (7, 25)
            cv.rect(mx - 3, my, 7, 1, C(P["moss"]))
            cv.rect(mx - 2, my - 1, 4, 1, C(P["moss2"]))
            cv.px(mx + 2, my + 1, C(P["mossD"]))
        if v == 3:
            gx, gy = 24, 8
            for b, bh in enumerate((2, 4, 3, 2)):
                cv.rect(gx + b, gy - bh, 1, bh, C(P["grass"] if b % 2 else P["grass2"]))
            cv.rect(gx - 1, gy, 6, 1, C(P["mossD"]))
    # grão de 1 px
    for i in range(16):
        x, y = 1 + int(hsh(i, 15, s) * 30), 1 + int(hsh(i, 16, s) * 30)
        if free(x, y):
            cv.px(x, y, C(P["gD"] if i % 3 else P["gL"]))
    return cv


ROCK = dict(hi="#d8d0dc", light="#a69cad", mid="#867c8f", dark="#625a6c", deep="#463f51")


def _chunk_mask(w, h, s, cut=0.18):
    """Pedra gordinha: elipse com uma quina chanfrada (sem ponta), achatada embaixo."""
    ys, xs = np.mgrid[0:h, 0:w] + 0.5
    m = ((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2 <= 1.1
    # chanfro: corta um canto de cima, lado da seed
    if s % 2:
        m &= (xs + ys) > w * cut + 2
    else:
        m &= ((w - xs) + ys) > w * cut + 2
    m[h - 1, :] &= np.abs(xs[0] - w / 2) < w / 2 - 1.5
    return m


def paint_rock(cv: Canvas, m, x, y, top_rows, s, pal=None):
    """Rocha em 3/4: topo claro (top_rows), frente em faixas escurecendo, brilho, contorno #1b1630
    e 2 px de base (pesada no chão). `pal` troca a paleta (padrão: ROCK, roxo-acinzentada)."""
    ROCK = pal or globals()["ROCK"]
    h, w = m.shape
    layer = Canvas(cv.w, cv.h)
    up = np.zeros_like(m); up[1:] = m[:-1]
    dn = np.zeros_like(m); dn[:-1] = m[1:]
    lf = np.zeros_like(m); lf[:, 1:] = m[:, :-1]
    rt = np.zeros_like(m); rt[:, :-1] = m[:, 1:]
    ys, xs = np.nonzero(m)
    top = ys.min()
    for j, i in zip(ys, xs):
        r = j - top
        # aresta do topo pra frente: linha da quina sobe nas laterais (forma de pão)
        edge = top_rows + int(abs(i - w / 2) > w / 2 - 3)
        if r < edge:
            c = ROCK["light"] if (up[j, i] and lf[j, i]) else ROCK["hi"]
            if not rt[j, i]:
                c = ROCK["mid"]
        elif r == edge:
            c = ROCK["mid"]
        else:
            c = ROCK["mid"] if r < edge + 3 else ROCK["dark"]
            if not rt[j, i] or not dn[j, i]:
                c = ROCK["deep"]
            elif not lf[j, i]:
                c = ROCK["mid"] if r < edge + 3 else ROCK["dark"]
        layer.px(x + i, y + j, C(c))
    xl = xs[ys == top].min()
    layer.px(x + xl + 1, y + top + 1, C(ROCK["hi"]))
    layer.px(x + xl + 2, y + top + 1, C("#ffffff"))
    layer.outline(C(OUTLINE))
    a = layer.a
    op = a[:, :, 3] == 255
    below = np.zeros_like(op); below[1:] = op[:-1]
    a[below & ~op] = C(OUTLINE)
    cv.paste(layer, 0, 0)


def make_rock_small() -> Canvas:
    """Rocha pequena de 1 tile: uma pedra gorda e uma pedrinha na frente, roxo-acinzentada
    (neutra: lê bem no vermelho, no cinza e no bege). Sombra num nível só."""
    cv = Canvas(T, T)
    cv.ellipse(16, 27.5, 13, 3.5, SHADOW)
    big = _chunk_mask(22, 17, 1)
    paint_rock(cv, big, 4, 8, 6, 1)
    # rachadura e lascas na frente da pedra grande
    for (x, y) in ((13, 17), (14, 18), (14, 19), (15, 20), (15, 21)):
        cv.px(x, y, C(ROCK["deep"]))
    cv.px(16, 18, C(ROCK["light"]))
    cv.px(9, 11, C(ROCK["light"]))
    cv.rect(18, 10, 3, 1, C(ROCK["light"]))
    small = _chunk_mask(9, 7, 0, 0.1)
    paint_rock(cv, small, 20, 20, 3, 0)
    cv.px(4, 27, C(ROCK["dark"]))
    cv.px(5, 27, C(ROCK["mid"]))
    return cv


def make_pickup(name: str) -> Canvas:
    """Recurso solto 16x16: peças do minério v2.3 (mesmo estilo dos ícones), menores e mais juntas,
    com sombrinha. Ponto de chão = (8, 13)."""
    S = ORE_STYLE[name]
    cv = Canvas(16, 16)
    cv.ellipse(8, 13.5, 7, 2, SHADOW)
    if name == "iron":                       # duas pepitas cor de cobre
        paint_piece(cv, shape_lump(8, 6, 1), 1, 5, S, "slab", 2)
        paint_piece(cv, shape_lump(6, 5, 0), 8, 7, S, "slab", 2)
    elif name == "silicon":                  # duas lascas grossas apoiadas uma na outra
        paint_piece(cv, shape_shard(4, 9, 2), 2, 2, S, "shard", 2)
        paint_piece(cv, shape_shard(4, 7, -2), 8, 4, S, "shard", 2)
    else:                                     # dois cubos de gelo
        paint_piece(cv, shape_block(6, 6, 0), 2, 5, S, "cube", 2)
        paint_piece(cv, shape_block(5, 5, 0), 8, 7, S, "cube", 2)
    return cv


CR = dict(  # cratera: mesma família roxo-acinzentada da rocha pequena (um sprite só pros 3 estágios)
    hi="#d8d0dc", light="#a69cad", mid="#867c8f", dark="#625a6c", deep="#463f51",
    wall1="#5a5264", wall2="#453e50", wall3="#322c3c", wall4="#221d2b", pit="#120e18", pit2="#0b0810",
)


def _crater_masks():
    W = 96
    ys, xs = np.mgrid[0:W, 0:W] + 0.5
    cx, cy, lift = 48, 51, 7                      # lift = altura do morro da borda (3/4)

    def ell(rx, ry, dy, k1, k2):
        ang = np.arctan2(ys - (cy + dy), xs - cx)
        wob = 1 + k1 * np.sin(5 * ang + 1.3) + k2 * np.sin(9 * ang + 0.4)
        return (((xs - cx) / rx) ** 2 + ((ys - cy - dy) / ry) ** 2) <= wob ** 2

    base = ell(46, 40, 0, 0.04, 0.025)            # pé do morro no chão
    top = ell(45, 38, -lift, 0.04, 0.025)         # contorno de cima da borda
    hole = ell(32, 23, -lift - 2, 0.05, 0.03)     # boca do buraco (na altura da borda)
    return xs, ys, cx, cy, lift, base, top, hole


def _crater_base(ramp: bool) -> Canvas:
    """Cratera 96x96 em 3/4: morro de borda contínuo (topo claro com blocos e lascas, face externa
    escurecendo na frente), parede interna do fundo em estratos e breu no centro. Um sprite só, na família
    roxo-acinzentada da rocha pequena, então funciona nos 3 estágios."""
    W = 96
    xs, ys, cx, cy, lift, base, top, hole = _crater_masks()
    cv = Canvas(W, W)
    sh = (((xs - cx) / 47) ** 2 + ((ys - cy - 3) / 41) ** 2) <= 1
    cv.a[sh & ~base & ~top] = SHADOW
    # face externa: o que é pé do morro mas não é topo (aparece só na frente)
    face = base & ~top
    for y in range(W):
        for x in range(W):
            if not face[y, x]:
                continue
            col = np.nonzero(top[:, x])[0]
            d = y - (col.max() if len(col) else y)
            c = CR["mid"] if d <= 2 else CR["dark"] if d <= 5 else CR["deep"]
            if d > 1 and hsh(x // 3, int(d) // 2, 61) < 0.18:
                c = CR["deep"] if c != CR["deep"] else CR["wall2"]      # blocos irregulares
            cv.px(x, y, C(c))
    # topo da borda
    rim = top & ~hole
    upm = np.roll(rim, 1, 0); dnm = np.roll(rim, -1, 0)
    cv.a[rim] = C(CR["light"])
    # placas grandes de rocha no topo (ruído de baixa frequência em 2 faixas chapadas + fendas)
    n = np.array([[vnoise(x * 0.11, y * 0.16, 17) for x in range(W)] for y in range(W)])
    cv.a[rim & (n < 0.38)] = C(CR["mid"])
    edge = (n > 0.38) & (np.roll(n, 1, 0) <= 0.38)
    cv.a[rim & edge] = C(CR["hi"])                                    # quina clara de cada placa
    crack = (np.abs(n - 0.62) < 0.012)
    cv.a[rim & crack] = C(CR["dark"])
    cv.a[rim & ~upm & (ys < cy)] = C(CR["hi"])                        # aresta de fora, atrás: luz
    cv.a[rim & ~dnm & (ys > cy - lift)] = C(CR["mid"])                # quina de cima da face da frente
    # buraco: parede interna do fundo (estratos) e breu
    for y in range(W):
        for x in range(W):
            if not hole[y, x]:
                continue
            col = np.nonzero(hole[:, x])[0]
            d = y - col.min()
            c = (CR["dark"] if d < 2 else CR["wall1"] if d < 5 else CR["wall2"] if d < 9 else
                 CR["wall3"] if d < 13 else CR["wall4"] if d < 17 else CR["pit"])
            if c == CR["pit"] and (x * 3 + y) % 11 == 0:
                c = CR["pit2"]
            cv.px(x, y, C(c))
    hy0 = int(ys[hole].min())
    for k, (dy, x0, x1) in enumerate(((4, 28, 42), (5, 54, 68), (8, 22, 33), (9, 60, 74), (12, 31, 44), (12, 52, 61))):
        yy = hy0 + dy
        for x in range(x0, x1):
            if hole[yy, x] and hole[yy - 1, x] and hsh(x, k, 5) < 0.85:
                cv.px(x, yy, C(CR["wall4"] if k < 4 else CR["pit"]))
                cv.px(x, yy - 1, C(CR["wall1"] if k < 2 else CR["wall2"]))
    for (fx, fy, ln) in ((40, 1, 5), (61, 2, 5), (28, 6, 4)):
        for j in range(ln):
            x, y = fx + j // 2, hy0 + fy + j
            if hole[y, x]:
                cv.px(x, y, C(CR["wall4"]))
    # contorno: em volta de tudo e na boca do buraco
    solid = Canvas(W, W)
    solid.a[(top | base)] = C("#ffffff")
    solid.outline(C(OUTLINE))
    ring = solid.a[:, :, 0] == C(OUTLINE)[0]
    ring &= solid.a[:, :, 3] == 255
    cv.a[ring & (cv.a[:, :, 3] < 255)] = C(OUTLINE)
    lip = hole & ~np.roll(hole, 1, 0)
    cv.a[lip] = C(OUTLINE)
    cv.a[hole & ~np.roll(hole, -1, 0)] = C(CR["pit"])
    cv.a[np.roll(lip, 1, 0) & hole & ~lip] = C(CR["deep"])
    # pedregulhos e lascas na borda (poucos, de trás pra frente)
    boulders = [(26, 15, 17, 11, 1), (36, 12, 8, 6, 0), (80, 36, 12, 10, 0),
                (14, 64, 13, 11, 1), (76, 79, 16, 11, 0), (87, 70, 7, 6, 1)]
    if ramp:
        boulders += [(29, 86, 9, 7, 0)]
    for (bx, by, w, h, sd) in sorted(boulders, key=lambda b: b[1]):
        paint_rock(cv, _chunk_mask(w, h, sd, 0.15), bx - w // 2, by - h // 2, max(3, h // 2), sd)
    for i in range(18):
        a = hsh(i, 6, 41) * 2 * math.pi
        x = int(cx + math.cos(a) * (37 + hsh(i, 7, 41) * 4))
        y = int(cy - lift + math.sin(a) * (30 + hsh(i, 7, 41) * 3))
        if rim[y, x] and rim[y + 1, x] and rim[y, x + 1]:
            cv.px(x, y, C(CR["hi"]))
            cv.px(x + 1, y, C(CR["mid"]))
            cv.px(x, y + 1, C(CR["dark"]))
    return cv


def make_crater() -> Canvas:
    return _crater_base(False)


def make_crater_ramp() -> Canvas:
    """A mesma cratera com um corte na borda da frente e uma rampa de metal descendo pro escuro:
    degraus largos que escurecem com a profundidade, corrimãos laranja, soleira com faixa de alerta
    e 2 balizas com LED verde (lê como "dá pra entrar aqui")."""
    cv = _crater_base(True)
    x0, x1 = 37, 59                       # largura da rampa embaixo (mais perto da câmera)
    yb, yt = 90, 46                       # pé da rampa (no chão) e onde ela some no breu
    steps = ["#c8cdd4", "#abb2bb", "#8c949e", "#6b717a", "#4f545c", "#3b3f46", "#2a2d33", "#1d1f24", "#141519"]
    for y in range(yt, yb):
        f = (yb - y) / (yb - yt)
        inset = int(round(f * 6))
        l, r = x0 + inset, x1 - inset
        k = min(len(steps) - 1, int(f * len(steps)))
        st = (yb - y) % 6                 # degrau de 6 px: pisada clara (2) + espelho escuro (4)
        c = steps[k] if st >= 4 else steps[min(len(steps) - 1, k + 2)]
        cv.rect(l - 6, y, r - l + 12, 1, C(CR["wall3"] if k < 5 else CR["pit"]))   # paredes do corte
        cv.rect(l - 6, y, 3, 1, C(CR["dark"] if k < 3 else CR["wall2"] if k < 6 else CR["wall4"]))
        cv.rect(l, y, r - l, 1, C(c))
        if st == 5 and k < 6:
            cv.px(l + 2, y, C(steps[max(0, k - 1)]))
        cv.px(l - 1, y, C("#e2733a" if k < 5 else "#7a3a1c"))
        cv.px(r, y, C("#a8471f" if k < 5 else "#5a2a14"))
        cv.px(l - 7, y, C(OUTLINE))
        cv.px(r + 6, y, C(OUTLINE))
    # soleira de metal com faixa de alerta, no chão
    cv.rect(x0 - 7, yb, x1 - x0 + 14, 4, C(OUTLINE))
    cv.rect(x0 - 6, yb, x1 - x0 + 12, 2, C("#8c949e"))
    for i in range(x1 - x0 + 12):
        cv.px(x0 - 6 + i, yb, C(GOLD if (i // 3) % 2 == 0 else "#2a2d33"))
    cv.rect(x0 - 6, yb + 1, x1 - x0 + 12, 1, C("#6b717a"))
    # balizas dos dois lados, com LED verde
    for bx in (x0 - 12, x1 + 9):
        cv.rect(bx - 1, yb - 13, 5, 16, C(OUTLINE))
        cv.rect(bx, yb - 12, 3, 14, C("#c8cdd4"))
        cv.rect(bx, yb - 12, 1, 14, C("#f4f6f8"))
        cv.rect(bx + 2, yb - 12, 1, 14, C("#8c949e"))
        cv.rect(bx, yb - 6, 3, 2, C("#e2733a"))
        cv.rect(bx, yb - 12, 3, 2, C("#7fd67a"))
        cv.px(bx, yb - 12, C("#d6ffd0"))
    return cv


POD_GEOM = {
    # m = margem lateral, top = topo do teto, face/skirt = onde começam a frente e a saia, ground = pé da saia
    "pod.png": dict(W=64, H=72, m=3, top=18, face=31, skirt=56, ground=68, ch=5, fw=5, door=13, wing="right"),
    "pod_wide.png": dict(W=96, H=64, m=5, top=14, face=27, skirt=48, ground=60, ch=6, fw=6, door=15, wing="left"),
}
POD_LIGHTS: dict[str, dict] = {}       # preenchido por make_pod_lander: pontos de luz pro Dev


def make_pod_lander(name: str) -> Canvas:
    """Cápsula v4: módulo de fuga pousado. Caixa baixa de cantos chanfrados (perfil quase hexagonal),
    placas creme com junções, saia escura grossa (meio enterrada), janelinhas ciano, escotilha com moldura,
    caixa de equipamento e aleta no teto, toco de asa, faixa laranja, LED e beacon. Visão 3/4."""
    g = POD_GEOM[name]
    W, H, m, top, face, skirt, ground, ch, fw = (g[k] for k in ("W", "H", "m", "top", "face", "skirt", "ground", "ch", "fw"))
    cv = Canvas(W, H)
    cv.ellipse(W / 2, ground + 0.5, W / 2 - 1, 3.5, SHADOW)
    L = Canvas(W, H)
    r = lambda x, y, w, h, c: L.rect(x, y, w, h, C(c))            # noqa: E731
    CREAM = dict(roof="#f7f1e2", roofS="#ddd3bd", hi="#ffffff", face="#ece3cf", seam="#c9bea6",
                 fl="#ddd3bc", fr="#b5aa91", low="#d4c9b1")
    # teto (chanfrado nos cantos de trás = perfil hexagonal visto de cima)
    for y in range(top, face):
        k = max(0, ch - (y - top))
        r(m + k, y, W - 2 * m - 2 * k, 1, CREAM["roof"])
        if k:
            L.px(m + k, y, C(CREAM["hi"]))
            L.px(W - m - k - 1, y, C(CREAM["roofS"]))
    r(m + ch, top, W - 2 * m - 2 * ch, 1, CREAM["hi"])
    for fx in (0.33, 0.66):                                           # junções das placas do teto
        r(int(W * fx), top + 2, 1, face - top - 3, CREAM["roofS"])
    r(m + 2, top + (face - top) // 2 + 1, W - 2 * m - 4, 1, CREAM["roofS"])
    r(m, face - 1, W - 2 * m, 1, CREAM["hi"])                          # quina do teto pra frente
    # frente: painel central creme e duas facetas chanfradas (luz à esquerda, sombra à direita)
    r(m, face, W - 2 * m, skirt - face, CREAM["face"])
    r(m, face, fw, skirt - face, CREAM["fl"])
    r(W - m - fw, face, fw, skirt - face, CREAM["fr"])
    r(m, face, W - 2 * m, 1, CREAM["seam"])
    r(m + fw, skirt - 3, W - 2 * m - 2 * fw, 3, CREAM["low"])           # pé da frente mais escuro
    r(m + fw - 1, face, 1, skirt - face, CREAM["seam"])
    r(W - m - fw, face, 1, skirt - face, "#9c917a")
    # saia escura grossa, abrindo pra baixo (assentada na areia)
    for y in range(skirt, ground):
        k = min(3, (y - skirt) // 3)
        x0, x1 = max(0, m - k), min(W, W - m + k)
        c = "#5a6069" if y == skirt else "#3b3f46" if y < ground - 3 else "#2a2d33"
        r(x0, y, x1 - x0, 1, c)
    pw = 13 if W < 80 else 16                                          # painéis recuados da saia
    for i, px0 in enumerate(range(m + 3, W - m - pw, pw + 3)):
        r(px0, skirt + 3, pw, ground - skirt - 6, "#2a2d33")
        r(px0, skirt + 3, pw, 1, "#22262c")
        r(px0, ground - 4, pw, 1, "#4a4f57")
        L.px(px0 + pw + 1, skirt + 4, C("#8c949e"))
        L.px(px0 + pw + 1, ground - 5, C("#6b717a"))
    for (sx_, sy_) in ((m + fw + 3, skirt - 2), (m + fw + 9, skirt - 1), (W - m - fw - 4, skirt - 2), (W // 2 - 4, skirt - 1)):
        r(sx_, sy_, 2, 1, "#b5aa91")                                      # marcas do pouso perto da saia
    # escotilha (porta) com moldura, um pouco à direita do centro, descendo até a saia
    dw = g["door"]
    dx = int(W * 0.66) - dw // 2
    dy0, dy1 = face + 4, skirt + 3
    r(dx - 1, dy0 - 1, dw + 2, dy1 - dy0 + 1, "#e2733a")               # moldura laranja
    r(dx, dy0, dw, dy1 - dy0, "#8c949e")
    r(dx + 1, dy0 + 1, dw - 2, dy1 - dy0 - 1, "#34444f")
    r(dx + 1, dy0 + 1, dw - 2, 1, "#4a5f6d")
    r(dx + dw // 2, dy0 + 1, 1, dy1 - dy0 - 1, "#22303a")
    r(dx + 2, dy0 + 3, dw // 2 - 3, 2, "#59d0e6")                       # visor da porta
    L.px(dx + 2, dy0 + 3, C("#d8fbff"))
    r(dx + dw // 2 + 2, dy0 + (dy1 - dy0) // 2, 2, 2, "#c8cdd4")         # alavanca
    r(dx - 2, dy1, dw + 4, 2, "#8c949e")                                # degrau
    r(dx - 2, dy1, dw + 4, 1, "#c8cdd4")
    led = (dx - 5, dy0 + 6)
    r(led[0], led[1], 2, 2, "#7fd67a")
    L.px(led[0], led[1], C("#d6ffd0"))
    # faixa laranja na frente (interrompida pela porta)
    fy = face + 10
    for x0, x1 in ((m + fw, dx - 2), (dx + dw + 2, W - m - fw)):
        if x1 > x0:
            r(x0, fy, x1 - x0, 1, "#f29a62")
            r(x0, fy + 1, x1 - x0, 1, "#e2733a")
            r(x0, fy + 2, x1 - x0, 1, "#a8471f")
    # janelinhas ciano em fileira
    wins = []
    x = m + fw + 2
    while x + 4 <= dx - 4:
        r(x - 1, face + 3, 6, 5, "#22303a")
        r(x, face + 4, 4, 3, "#59d0e6")
        r(x, face + 6, 4, 1, "#2b7f99")
        L.px(x, face + 4, C("#d8fbff"))
        wins.append((x + 2, face + 5))
        x += 7
    # junções verticais das placas da frente (abaixo da faixa)
    for jx in range(m + fw + 8, dx - 3, 9):
        r(jx, fy + 3, 1, skirt - fy - 6, CREAM["seam"])
    # caixa de equipamento escura no teto + grade
    bw = int(W * 0.24)
    bx0 = int(W * 0.40)
    r(bx0, top - 5, bw, 3, "#5a6069")
    r(bx0, top - 2, bw, 8, "#2a2d33")
    r(bx0, top - 5, bw, 1, "#6b717a")
    for i in range(3):
        r(bx0 + 2, top + i * 2, bw - 4, 1, "#4a4f57")
    r(bx0 + bw - 4, top - 4, 2, 1, "#e2733a")
    # aleta no teto (lado esquerdo), com ponta laranja
    fx_ = int(W * 0.20)
    r(fx_, top - 8, 3, 12, "#3b3f46")
    r(fx_, top - 8, 1, 12, "#5a6069")
    r(fx_, top - 8, 3, 2, "#e2733a")
    # antena com beacon vermelho
    ax_ = int(W * 0.80)
    r(ax_, top - 12, 1, 14, "#8c949e")
    r(ax_ - 1, top + 1, 3, 2, "#6b717a")
    r(ax_ - 1, top - 15, 3, 3, "#ff5a4a")
    L.px(ax_ - 1, top - 15, C("#ffd0c8"))
    # toco de asa
    if g["wing"] == "right":
        for i in range(5):
            r(W - m, face + 12 + i, 2 + (i < 3), 1, "#3b3f46")
        r(W - m, face + 12, 3, 1, "#e2733a")
    else:
        for i in range(7):
            w = 7 - i
            r(m - w, face + 11 + i, w, 1, "#3b3f46" if i else "#5a6069")
        r(0, face + 11, 2, 2, "#e2733a")
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    POD_LIGHTS[name] = dict(window=wins[len(wins) // 2] if wins else (dx, face + 5), beacon=(ax_, top - 14),
                            led=led, door=(dx + dw // 2, dy1))
    return cv


# ---------------------------------------------------------------- v4.1 (pendente): névoa marrom úmida e verde de verdade

SOIL = {
    # névoa: terra marrom úmida, ponte entre o vermelho do morto e o verde
    "mist": dict(base="#765741", d1="#6c4f3b", l1="#80604a", gD="#5a4232", gL="#927259",
                 damp="#5e4535", damp2="#523c2e", peb="#463830", pebL="#8f7865",
                 mud="#4a382c", water="#4f6f7a", waterD="#3f5a64", sheen="#a3d2e3"),
    # verde: grama cobrindo o chão (mesma família do floor_green aprovado)
    "green": dict(base="#4d7a39", d1="#477235", l1="#548140", gD="#3a5f2c", gL="#79b04f",
                  blade="#79b04f", blade2="#5e9640", bladeD="#3f6a30", moss="#3f7230", moss2="#36632a",
                  mossL="#5c9a43", petal="#f4ecd2", petal2="#f2c46d", core="#e2733a", stem="#3a5f2c"),
}


def _scatter(n, s, k, margin=2):
    """n pontos determinísticos dentro do tile, longe da borda."""
    return [(margin + int(hsh(i, k, s) * (T - 2 * margin)), margin + int(hsh(i, k + 1, s) * (T - 2 * margin)))
            for i in range(n)]


def make_soil_mist(v: int) -> Canvas:
    """Névoa v4.1: terra marrom úmida. v0 terra · v1 cascalho escuro · v2 terra encharcada (textura de
    manchinhas, agrupa em zonas sem virar carimbo) · v3 pocinha de lama (rara). Nada encosta na borda."""
    P = SOIL["mist"]
    s = 7100 + v * 131
    cv = Canvas(T, T)
    cv.rect(0, 0, T, T, C(P["base"]))

    def free(x, y):
        return 1 <= x < T - 1 and 1 <= y < T - 1 and cv.get(x, y)[:3] == C(P["base"])[:3]

    for i, (x, y) in enumerate(_scatter(5, s, 1)):           # torrões: faixas chapadas curtas
        w = 3 + int(hsh(i, 3, s) * 4)
        x = min(x, T - 2 - w)
        cv.rect(x, y, w, 1, C(P["l1"] if i % 2 else P["d1"]))
        if i % 2 == 0:
            cv.rect(x + 1, y + 1, w - 2, 1, C(P["d1"]))
    if v in (0, 2):                                           # 1 mancha de umidade (pequena)
        x, y = _scatter(1, s, 5, 6)[0]
        cv.rect(x - 3, y, 7, 1, C(P["damp"]))
        cv.rect(x - 2, y + 1, 5, 1, C(P["damp"]))
    if v == 2:                                                # encharcada: muitas manchinhas escuras
        for i, (x, y) in enumerate(_scatter(9, s, 7, 3)):
            w = 2 + int(hsh(i, 9, s) * 4)
            x = min(x, T - 2 - w)
            cv.rect(x, y, w, 1, C(P["damp2"] if i % 3 == 0 else P["damp"]))
            if i % 4 == 1:
                cv.px(x, y - 1, C(P["sheen"]))
    if v == 1:                                                # cascalho escuro, num bolo fora do centro
        ox, oy = [(8, 9), (22, 21), (9, 22), (21, 8)][int(hsh(0, 11, s) * 4)]
        for i in range(7):
            x = ox + int((hsh(i, 12, s) - 0.5) * 10)
            y = oy + int((hsh(i, 13, s) - 0.5) * 8)
            if i < 4:
                cv.rect(x, y, 2, 1, C(P["pebL"]))
                cv.rect(x, y + 1, 2, 1, C(P["peb"]))
            else:
                cv.px(x, y, C(P["peb"]))
    if v == 3:                                                # pocinha de lama com reflexo
        cx, cy = 19, 20                                       # lama pequena (as poças de verdade são o autotile)
        for y in range(cy - 3, cy + 3):
            for x in range(cx - 5, cx + 6):
                d = ((x + 0.5 - cx) / 5) ** 2 + ((y + 0.5 - cy) / 2.6) ** 2
                if d <= 1.0:
                    cv.px(x, y, C(P["mud"]))
                if d <= 0.4:
                    cv.px(x, y, C(P["waterD"]))
        cv.rect(cx - 2, cy - 1, 2, 1, C(P["sheen"]))
    for i, (x, y) in enumerate(_scatter(16, s, 15, 1)):      # grão
        if free(x, y):
            cv.px(x, y, C(P["gD"] if i % 3 else P["gL"]))
    return cv


def _blade(cv, x, y, h, c, ctop=None):
    cv.rect(x, y - h + 1, 1, h, C(c))
    if ctop:
        cv.px(x, y - h + 1, C(ctop))


def make_grass_green(v: int) -> Canvas:
    """Verde v4.1: grama cobrindo o chão. Textura densa de folhinhas (densa = repetição some),
    v0 grama · v1 tufos mais altos · v2 musgo escuro (textura de touceirinhas, agrupa em zonas) ·
    v3 florzinha (rara). Nada encosta na borda, 100% opaco."""
    P = SOIL["green"]
    s = 8300 + v * 131
    cv = Canvas(T, T)
    cv.rect(0, 0, T, T, C(P["base"]))
    # manchas de tom (chapadas, achatadas, contidas)
    for i, (x, y) in enumerate(_scatter(4, s, 1, 5)):
        w = 4 + int(hsh(i, 3, s) * 6)
        x = min(x, T - 2 - w)
        cv.rect(x, y, w, 1, C(P["l1"] if i % 2 else P["d1"]))
        cv.rect(x + 1, y + 1, max(1, w - 2), 1, C(P["l1"] if i % 2 else P["d1"]))
    if v == 2:                                                # musgo: touceirinhas escuras espalhadas
        for i, (x, y) in enumerate(_scatter(7, s, 21, 3)):
            w = 3 + int(hsh(i, 23, s) * 3)
            x = min(x, T - 2 - w)
            cv.rect(x, y, w, 1, C(P["moss"]))
            cv.rect(x + 1, y + 1, w - 1, 1, C(P["moss2"]))
            cv.px(x + 1, y - 1, C(P["mossL"]))
    # folhinhas: pares de 1x2 (claro em cima, escuro no pé)
    for i, (x, y) in enumerate(_scatter(22, s, 5, 2)):
        if cv.get(x, y)[:3] not in (C(P["base"])[:3], C(P["l1"])[:3], C(P["d1"])[:3]):
            continue
        c = P["blade"] if i % 3 == 0 else P["blade2"]
        _blade(cv, x, y, 2, c)
        cv.px(x + 1, y, C(P["gD"]))
    if v == 1:                                                # 2 tufos altos
        for (gx, gy) in [((6, 12), (20, 24)), ((19, 10), (8, 25))][int(hsh(0, 31, s) * 2)]:
            for b, bh in enumerate((3, 5, 4, 6, 3)):
                _blade(cv, gx + b, gy, bh, P["blade"] if b % 2 else P["blade2"], P["blade"] if b == 3 else None)
            cv.rect(gx, gy + 1, 5, 1, C(P["bladeD"]))
    if v == 3:                                                # florzinha rara + 1 tufo
        fx, fy = 11, 13
        _blade(cv, fx + 1, fy + 5, 4, P["stem"])
        cv.px(fx + 2, fy + 3, C(P["blade2"]))
        for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
            cv.px(fx + dx, fy + dy, C(P["petal"]))
        cv.px(fx + 1, fy + 1, C(P["petal2"]))
        for b, bh in enumerate((3, 4, 3)):
            _blade(cv, 21 + b, 24, bh, P["blade"] if b % 2 else P["blade2"])
        cv.rect(21, 25, 3, 1, C(P["bladeD"]))
    for i, (x, y) in enumerate(_scatter(10, s, 41, 1)):      # pontinhos escuros (terra entre a grama)
        if cv.get(x, y)[:3] == C(P["base"])[:3]:
            cv.px(x, y, C(P["gD"]))
    return cv


# ---------------------------------------------------------------- v4.1 (pendente): autotile de água (layout A2 do RPG Maker)

WATER_SHORE = {
    # margem por fora da água: anel externo (some no chão) e lama/terra molhada colada na água
    "mist": dict(outer="#5e4535", mud="#4a382c", mud2="#3e2f25", grass=None),
    "green": dict(outer="#3a5f2c", mud="#4a4030", mud2="#3b3326", grass="#5e9640"),
}
AW_E, AW_R = 4, 12          # recuo da água em relação à borda do tile e raio do canto externo (R + E <= 16)


def _wob(t):
    """Ondulação da margem: periódica em 32 px e zero em 0, 8, 16, 24 (fronteiras de minitile casam)."""
    return 1.3 * math.sin(2 * math.pi * t / 32) + 0.6 * math.sin(4 * math.pi * t / 32)


def _sd_island(x, y):
    """Distância com sinal (positivo = água) da ilha 2x2 dos 64x64 de baixo do A2."""
    dx = min(x + 0.5, 64 - x - 0.5) + _wob(y)
    dy = min(y + 0.5, 64 - y - 0.5) + _wob(x)
    ax, ay = max(AW_R + AW_E - dx, 0), max(AW_R + AW_E - dy, 0)
    return AW_R - math.hypot(ax, ay)


def _sd_inner(x, y):
    """Bloco de cima à direita (32x32): 4 cantos internos, a terra é só um cantinho na quina do tile."""
    cx, cy = (0 if x < 16 else 32), (0 if y < 16 else 32)
    u, v = abs(x + 0.5 - cx), abs(y + 0.5 - cy)
    k = 3.0 * math.sin(2 * math.atan2(v, u))     # 0 nos eixos (casa com as bordas retas), +3 na diagonal
    return math.hypot(u, v) - AW_E - k


def _sd_drop(x, y):
    """Bloco de cima à esquerda (32x32): poça isolada, gota redonda."""
    a = math.atan2(y + 0.5 - 16.5, x + 0.5 - 16)
    r = 11.2 + 0.7 * math.sin(3 * a + 0.8)
    return r - math.hypot(x + 0.5 - 16, (y + 0.5 - 16.5) / 0.92)


def make_water_auto(stage: str, water_png: Image.Image) -> Canvas:
    """Autotile A2 64x96: (0,0)-(32,32) poça isolada · (32,0)-(64,32) cantos internos ·
    (0,32)-(64,96) ilha 2x2 = interior + bordas + cantos externos. Fora da margem é transparente
    (o chão aparece por baixo). O interior é o próprio water_{stage}.png, amostrado na mesma posição."""
    P, Wd = STAGES[stage], WATER_SHORE[stage]
    wat = np.array(water_png.convert("RGBA"))
    cv = Canvas(64, 96)
    sd = np.zeros((96, 64))
    for y in range(96):
        for x in range(64):
            if y < 32:
                sd[y, x] = _sd_drop(x, y) if x < 32 else _sd_inner(x - 32, y)
            else:
                sd[y, x] = _sd_island(x, y - 32)
    for y in range(96):
        for x in range(64):
            d = sd[y, x]
            # lado da margem: a água continua pra baixo (margem de cima, faz sombra) ou pra cima (de baixo, brilha)
            below = sd[y + 1, x] if y + 1 < 96 and (y + 1) // 32 == y // 32 else d
            above = sd[y - 1, x] if y > 0 and (y - 1) // 32 == y // 32 else d
            top_bank = below > above
            if d < -3.2:
                continue
            if d < -1.6:
                c = Wd["outer"]
                if Wd["grass"] and hsh(x, y, 5) < 0.35:
                    c = Wd["grass"]
            elif d < 0:
                c = Wd["mud"] if (x + y) % 5 else Wd["mud2"]
            elif d < 1.2:
                c = P["waterD"] if top_bank else P["foam"]
            elif d < 2.2 and top_bank:
                c = P["waterD"]
            else:
                r, g, b, _ = wat[y % 32, x % 32]
                c = "#%02x%02x%02x" % (r, g, b)
                if d < 2.6 and not top_bank:
                    c = P["waterHi"]
            cv.px(x, y, C(c))
    return cv


# fonte (x, y) em px no A2 de cada quadrante, dado o que tem em volta (paridade de quadrante preservada)
def autotile_quads(n: dict) -> list[tuple[int, int, int, int]]:
    """n = vizinhos que são água: chaves 'u','d','l','r','ul','ur','dl','dr'.
    Devolve [(sx, sy, dx, dy)] pros 4 quadrantes 16x16 do tile (dx, dy relativos ao tile)."""
    if not (n["u"] or n["d"] or n["l"] or n["r"]):
        return [(qx * 16, qy * 16, qx * 16, qy * 16) for qy in (0, 1) for qx in (0, 1)]     # poça isolada
    out = []
    for qy in (0, 1):
        for qx in (0, 1):
            h = n["l"] if qx == 0 else n["r"]
            v = n["u"] if qy == 0 else n["d"]
            diag = n[("u" if qy == 0 else "d") + ("l" if qx == 0 else "r")]
            if h and v and not diag:                                            # canto interno
                out.append((32 + qx * 16, qy * 16, qx * 16, qy * 16))
                continue
            col = (2 if h else 0) if qx == 0 else (1 if h else 3)
            row = (2 if v else 0) if qy == 0 else (1 if v else 3)
            out.append((col * 16, 32 + row * 16, qx * 16, qy * 16))
    return out


def draw_water_auto(img: Image.Image, sheet: Image.Image, water: set, x: int, y: int, px: int, py: int):
    w = lambda a, b: (a, b) in water                                            # noqa: E731
    n = dict(u=w(x, y - 1), d=w(x, y + 1), l=w(x - 1, y), r=w(x + 1, y),
             ul=w(x - 1, y - 1), ur=w(x + 1, y - 1), dl=w(x - 1, y + 1), dr=w(x + 1, y + 1))
    for sx, sy, dx, dy in autotile_quads(n):
        img.alpha_composite(sheet.crop((sx, sy, sx + 16, sy + 16)), (px + dx, py + dy))


WATER_DEMO = [  # cena de teste: poça de 1 tile, poça irregular de 3 tiles e lago com reentrâncias (20x9 tiles)
    (2, 2), (5, 2), (6, 2), (6, 3),
    (10, 1), (11, 1), (12, 1), (9, 2), (10, 2), (11, 2), (12, 2), (13, 2), (9, 3), (10, 3), (12, 3), (13, 3),
    (14, 3), (9, 4), (10, 4), (11, 4), (12, 4), (13, 4), (14, 4), (10, 5), (11, 5), (13, 5), (14, 5), (15, 5),
    (11, 6), (12, 6), (13, 6), (14, 6), (12, 7), (2, 6), (3, 6), (3, 7), (4, 7), (17, 2),
]


def make_water_demo(stage: str, spr: dict[str, Image.Image]) -> Image.Image:
    W_, H_ = 20, 9
    img = Image.new("RGBA", (W_ * T, H_ * T))
    water = set(WATER_DEMO)
    for y in range(H_):
        for x in range(W_):
            img.alpha_composite(spr[sand_key(spr, stage, sand_variant(x + 40, y + 20))], (x * T, y * T))
    sheet = spr[f"water_auto_{stage}.png"]
    for (x, y) in water:
        draw_water_auto(img, sheet, water, x, y, x * T, y * T)
    return img.convert("RGB")


# ---------------------------------------------------------------- v5.0 (aprovado): v0.3 · Marco 2 (caverna)

LAMP = dict(hi="#fffbe8", l="#ffe9a8", m="#ffd27a", d="#f2a64a", dd="#c9742f")
LAMP_BULB = (8, 6)          # centro da lâmpada no lamp.png (pro Dev ancorar a luz)


def _lamp_head(L: Canvas, x, y, w, h):
    """Cabeça de gaiola: tampa escura, vidro quente aceso em faixas (claro à esquerda), uma barra de gaiola
    no meio e um aro embaixo. (x, y) = canto sup. esquerdo do vidro."""
    _m(L, x + 1, y - 2, w - 2, 1, "g")                     # tampa
    _m(L, x, y - 1, w, 1, "k")
    for j in range(h):
        for i in range(w):
            c = LAMP["hi"] if i == 0 else LAMP["l"] if i == 1 else LAMP["dd"] if i == w - 1 else \
                LAMP["d"] if i == w - 2 else LAMP["m"]
            if j == h - 1 and 0 < i < w - 1:
                c = LAMP["d"]
            L.px(x + i, y + j, C(c))
    L.px(x + 1, y + 1, C("#ffffff"))
    _m(L, x + w // 2, y, 1, h, "kk")                        # barra vertical da gaiola
    _m(L, x, y + h // 2, w, 1, "k")                         # aro da gaiola
    L.px(x, y + h // 2, C(MT["g"]))
    _m(L, x - 1, y + h, w + 2, 1, "g")                      # aro de baixo
    _m(L, x - 1, y + h + 1, w + 2, 1, "k")


def make_lamp() -> Canvas:
    """Luminária de chão 16x32 (família das máquinas): sapata pesada com faixa laranja, poste cinza em
    faixas, colar escuro e cabeça de gaiola com lâmpada quente acesa. Base na linha 29."""
    cv = Canvas(16, 32)
    cv.ellipse(8, 29.5, 6.5, 2, SHADOW)
    L = Canvas(16, 32)
    _m(L, 3, 24, 10, 2, "l")                                # sapata: topo
    _m(L, 3, 24, 10, 1, "w")
    _m(L, 3, 26, 10, 3, "s")                                # frente
    _m(L, 3, 26, 10, 1, "o")
    _m(L, 3, 27, 10, 1, "od")
    _m(L, 3, 28, 10, 1, "d")
    _m(L, 12, 26, 1, 3, "g")
    L.px(4, 25, C(MT["d"])); L.px(11, 25, C(MT["d"]))       # parafusos
    for y in range(12, 24):                                 # poste
        L.bands(6, y, 1, [(MT["w"], 1), (MT["l"], 1), (MT["m"], 1), (MT["s"], 1)])
    _m(L, 6, 16, 4, 1, "oh")                                # faixa laranja no poste
    _m(L, 6, 17, 4, 1, "o")
    _m(L, 6, 18, 4, 1, "od")
    _m(L, 5, 11, 6, 1, "g")                                 # colar
    _m(L, 5, 12, 6, 1, "k")
    _lamp_head(L, 5, 3, 6, 6)
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


def make_icon_lamp() -> Canvas:
    """Ícone da luminária: a mesma cabeça de gaiola acesa, maior, num poste curto com sapata laranja."""
    cv = Canvas(16, 16)
    L = Canvas(16, 16)
    _lamp_head(L, 4, 2, 8, 6)
    _m(L, 6, 10, 4, 3, "m")
    _m(L, 6, 10, 1, 3, "w")
    _m(L, 9, 10, 1, 3, "s")
    _m(L, 3, 12, 10, 1, "l")
    _m(L, 3, 13, 10, 1, "o")
    _m(L, 3, 14, 10, 1, "od")
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


# ---------------------------------------------------------------- v5.1 (aprovado): luminária forte (lamp_t2)

LAMP2 = dict(hi="#ffffff", l="#fffbe8", m="#fff0bf", d="#ffd27a", dd="#f2a64a")   # vidro mais quente e mais branco
LAMP2_BULB = (8, 7)         # centro do vidro no lamp_t2.png (A)


def _lamp2_glass(L: Canvas, x, y, w, h, bars):
    """Vidro aceso, mais branco que o da comum: núcleo quase branco, laranja só nas bordas da direita/baixo.
    bars = colunas (relativas) das barras verticais da gaiola; aro horizontal no meio."""
    for j in range(h):
        for i in range(w):
            c = LAMP2["hi"] if i == 0 else LAMP2["l"] if i <= 2 else LAMP2["dd"] if i == w - 1 else \
                LAMP2["d"] if i == w - 2 else LAMP2["m"]
            if j == h - 1 and 0 < i < w - 1:
                c = LAMP2["d"]
            if j == 0 and 0 < i < w - 2:
                c = LAMP2["l"]
            L.px(x + i, y + j, C(c))
    L.px(x + 1, y + 1, C("#ffffff")); L.px(x + 2, y + 1, C("#ffffff")); L.px(x + 1, y + 2, C("#ffffff"))
    for b in bars:
        _m(L, x + b, y, 1, h, "kk")
    _m(L, x, y + h // 2, w, 1, "k")
    L.px(x, y + h // 2, C(MT["g"]))


def _lamp2_head(L: Canvas, x, y, w, h, bars):
    """Cabeça reforçada: capuz escuro com aba dourada mais larga que o vidro (refletor), vidro branco-quente
    em 3 painéis, aro dourado + aro escuro embaixo. (x, y) = canto sup. esquerdo do vidro."""
    _m(L, x + 2, y - 3, w - 4, 1, "k")                   # capuz (topo)
    _m(L, x + 1, y - 2, w - 2, 1, "g")
    _m(L, x - 1, y - 1, w + 2, 1, GOLD)                    # aba do refletor, dourada, 1 px pra fora de cada lado
    L.px(x - 1, y - 1, C(GOLD_D)); L.px(x + w, y - 1, C(GOLD_D))
    _lamp2_glass(L, x, y, w, h, bars)
    _m(L, x - 1, y + h, w + 2, 1, GOLD)                    # aro de baixo dourado
    L.px(x + w, y + h, C(GOLD_D))
    _m(L, x - 1, y + h + 1, w + 2, 1, "k")


def _lamp2_base(L: Canvas):
    """Sapata em dois degraus, mais larga que a da comum (12 px), faixa laranja + parafusos dourados."""
    _m(L, 2, 24, 12, 1, "w")                               # degrau de baixo: topo
    _m(L, 2, 25, 12, 1, "l")
    _m(L, 2, 26, 12, 3, "s")                               # frente
    _m(L, 2, 26, 12, 1, "o")
    _m(L, 2, 27, 12, 1, "od")
    _m(L, 2, 28, 12, 1, "d")
    _m(L, 13, 25, 1, 4, "g")
    L.px(3, 25, C(GOLD)); L.px(12, 25, C(GOLD))            # parafusos dourados
    _m(L, 4, 22, 8, 1, "w")                                # degrau de cima (pedestal)
    _m(L, 4, 23, 8, 1, "m")
    _m(L, 11, 22, 1, 2, "s")


def make_lamp_t2(variant: str = "A") -> Canvas:
    """Luminária forte 16x32, irmã nv.2 da lamp.png (mesma âncora: base na linha 29, centro x=8).
    A (recomendada): cabeça de gaiola maior (vidro 10x7, 3 painéis) com aba dourada de refletor, poste mais
    grosso com faixa laranja e anel dourado, sapata larga em 2 degraus.
    B: poste com cruzeta e DUAS cabeças de gaiola menores (silhueta em T)."""
    cv = Canvas(16, 32)
    cv.ellipse(8, 29.5, 7, 2, SHADOW)
    L = Canvas(16, 32)
    _lamp2_base(L)
    if variant == "A":
        for y in range(14, 22):                            # poste 6 px (a comum tem 4)
            L.bands(5, y, 1, [(MT["w"], 1), (MT["l"], 2), (MT["m"], 1), (MT["s"], 1), (MT["d"], 1)])
        _m(L, 5, 16, 6, 1, "oh")                           # faixa laranja
        _m(L, 5, 17, 6, 1, "o")
        _m(L, 5, 18, 6, 1, "od")
        _m(L, 5, 20, 6, 1, GOLD)                           # anel dourado
        L.px(10, 20, C(GOLD_D))
        _m(L, 4, 13, 8, 1, "g")                            # colar
        _m(L, 4, 14, 8, 1, "k")
        _lamp2_head(L, 3, 4, 10, 7, bars=(3, 6))
    else:
        for y in range(10, 22):                            # poste mais alto, 4 px
            L.bands(6, y, 1, [(MT["w"], 1), (MT["l"], 1), (MT["m"], 1), (MT["s"], 1)])
        _m(L, 6, 15, 4, 1, "oh")
        _m(L, 6, 16, 4, 1, "o")
        _m(L, 6, 17, 4, 1, "od")
        _m(L, 6, 19, 4, 1, GOLD)
        _m(L, 1, 9, 14, 1, "g")                            # cruzeta
        _m(L, 1, 10, 14, 1, "k")
        _m(L, 6, 8, 4, 1, GOLD)                            # topo do poste
        for hx in (1, 10):                                 # duas cabeças
            _m(L, hx + 1, 1, 3, 1, "k")
            _m(L, hx, 2, 5, 1, GOLD)
            for j in range(5):
                for i in range(5):
                    c = LAMP2["hi"] if i == 0 else LAMP2["l"] if i == 1 else LAMP2["dd"] if i == 4 else \
                        LAMP2["d"] if i == 3 else LAMP2["m"]
                    L.px(hx + i, 3 + j, C(c))
            L.px(hx + 1, 4, C("#ffffff"))
            _m(L, hx + 2, 3, 1, 5, "kk")
            _m(L, hx, 5, 5, 1, "k")
            _m(L, hx, 8, 5, 1, GOLD)
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


def make_icon_lamp_t2() -> Canvas:
    """Ícone da luminária forte: a cabeça reforçada (aba dourada, vidro branco-quente em 3 painéis) num poste
    curto e grosso, sapata laranja larga. Mesmo enquadramento do icon_lamp, só que mais larga."""
    cv = Canvas(16, 16)
    L = Canvas(16, 16)
    _m(L, 5, 10, 6, 3, "m")
    _m(L, 5, 10, 1, 3, "w")
    _m(L, 6, 10, 1, 3, "l")
    _m(L, 9, 10, 2, 3, "s")
    _m(L, 5, 11, 6, 1, GOLD)
    _m(L, 2, 12, 12, 1, "l")
    _m(L, 2, 13, 12, 1, "o")
    _m(L, 2, 14, 12, 1, "od")
    _lamp2_head(L, 3, 3, 10, 5, bars=(3, 6))
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


CAVE = dict(hi="#958d90", light="#7a7275", mid="#635c5f", dark="#4f484b", deep="#3c3639",
            f1="#5d5659", f2="#484245", f3="#363134", f4="#2b272a", f5="#1f1c1e")
CAVE_ROCK = dict(hi="#aca4a7", light="#857d80", mid="#686164", dark="#504a4d", deep="#3a3538")
SUN = ["#fffaf0", "#fff0c8", "#f8dca0", "#e8c088", "#c9a070"]       # luz do dia descendo pelo poço
STEPS_UP = ["#4a4f57", "#5a6069", "#6b717a", "#7c838c", "#8c949e", "#abb2bb", "#c8cdd4", "#e1e2df", "#f4ecd8", "#fff3dc"]
CAVE_RAMP = dict(sill=(1, 2), arrive=(1, 3), light=(48, 30))      # tiles relativos + centro da luz (px)


def make_cave_ramp_up() -> Canvas:
    """Rampa de subida 96x96 (contraparte da crater_ramp): monte de rocha fria (paleta da caverna) com uma
    escada de metal cortada nele, subindo da soleira (no chão, na frente) até uma boca de luz no fundo.
    Os degraus clareiam conforme sobem (luz do dia vindo de cima), com raios pontilhados e poeira no feixe.
    Mesma linguagem da crater_ramp: corrimão laranja, soleira com faixa de alerta e balizas com LED verde."""
    W = 96
    ys, xs = np.mgrid[0:W, 0:W] + 0.5
    cx, cy, lift = 48, 53, 11

    def ell(rx, ry, ex, ey, k1, k2, ph=1.3):
        ang = np.arctan2(ys - ey, xs - ex)
        wob = 1 + k1 * np.sin(5 * ang + ph) + k2 * np.sin(9 * ang + 0.4)
        return (((xs - ex) / rx) ** 2 + ((ys - ey) / ry) ** 2) <= wob ** 2

    base = ell(46, 40, cx, cy, 0.04, 0.025)
    top = ell(45, 37, cx, cy - lift, 0.04, 0.025)
    hole = ell(18, 11, 48, 24, 0.05, 0.03, 0.2)
    cv = Canvas(W, W)
    sh = (((xs - cx) / 47) ** 2 + ((ys - cy - 3) / 41) ** 2) <= 1
    cv.a[sh & ~base & ~top] = SHADOW
    # face externa (frente do monte), em estratos escurecendo pro pé
    face = base & ~top
    for y in range(W):
        for x in range(W):
            if not face[y, x]:
                continue
            col = np.nonzero(top[:, x])[0]
            d = y - (col.max() if len(col) else y)
            c = CAVE["f1"] if d <= 2 else CAVE["f2"] if d <= 5 else CAVE["f3"] if d <= 9 else CAVE["f4"]
            if d > 1 and hsh(x // 4, int(d) // 3, 63) < 0.2:
                c = CAVE["f3"] if c != CAVE["f3"] else CAVE["f4"]
            cv.px(x, y, C(c))
    # topo do monte: placas em 2 faixas chapadas + quinas claras + fendas
    rim = top & ~hole
    upm = np.roll(rim, 1, 0); dnm = np.roll(rim, -1, 0)
    cv.a[rim] = C(CAVE["light"])
    n = np.array([[vnoise(x * 0.11, y * 0.16, 29) for x in range(W)] for y in range(W)])
    cv.a[rim & (n < 0.4)] = C(CAVE["mid"])
    cv.a[rim & (n > 0.4) & (np.roll(n, 1, 0) <= 0.4)] = C(CAVE["hi"])
    cv.a[rim & (np.abs(n - 0.64) < 0.012)] = C(CAVE["dark"])
    cv.a[rim & ~upm & (ys < cy)] = C(CAVE["hi"])
    cv.a[rim & ~dnm & (ys > cy - lift)] = C(CAVE["mid"])
    # boca de luz no fundo: parede do poço iluminada em cima, depois a luz do dia em anéis
    hy0 = int(ys[hole].min())
    for y in range(W):
        for x in range(W):
            if not hole[y, x]:
                continue
            col = np.nonzero(hole[:, x])[0]
            d = y - col.min()
            r = math.hypot((x + 0.5 - 48) / 18, (y + 0.5 - 26) / 10)
            if d < 2:
                c = CAVE["mid"]
            elif d < 4:
                c = SUN[4]
            elif d < 6:
                c = SUN[3]
            else:
                c = SUN[0] if r < 0.45 else SUN[1] if r < 0.72 else SUN[2]
            cv.px(x, y, C(c))
    # contorno: em volta do monte e no beiço de trás da boca
    solid = Canvas(W, W)
    solid.a[(top | base)] = C("#ffffff")
    solid.outline(C(OUTLINE))
    ring = (solid.a[:, :, 0] == C(OUTLINE)[0]) & (solid.a[:, :, 3] == 255)
    cv.a[ring & (cv.a[:, :, 3] < 255)] = C(OUTLINE)
    lip = hole & ~np.roll(hole, 1, 0)
    cv.a[lip] = C(OUTLINE)
    cv.a[np.roll(hole, -1, 0) & ~hole & rim] = C(CAVE["hi"])          # beiço da frente, pegando luz
    warm = {CAVE["hi"]: "#d2c2ad", CAVE["light"]: "#ac9d8d", CAVE["mid"]: "#8c7f74", CAVE["dark"]: "#6e6359"}
    rr = np.hypot((xs - 48) / 18, (ys - 25) / 11)
    for y, x in zip(*np.nonzero(rim & (rr < 1.45))):                    # rocha em volta da boca, esquentada pela luz
        hexc = "#%02x%02x%02x" % tuple(cv.a[y, x, :3])
        if hexc in warm and (rr[y, x] < 1.25 or (x + y) % 2 == 0):
            cv.px(x, y, C(warm[hexc]))
    # pedregulhos na borda (de trás pra frente), longe da escada
    for (bx, by, w, h, sd) in sorted([(24, 17, 15, 10, 1), (73, 15, 12, 9, 0), (84, 40, 11, 10, 0),
                                       (12, 52, 12, 11, 1), (18, 80, 14, 10, 0), (80, 76, 15, 11, 1),
                                       (88, 64, 7, 6, 1)], key=lambda b: b[1]):
        paint_rock(cv, _chunk_mask(w, h, sd, 0.15), bx - w // 2, by - h // 2, max(3, h // 2), sd, CAVE_ROCK)
    # escada cortada no monte, subindo pro fundo
    yb, yt = 91, 30
    for y in range(yt, yb):
        f = (yb - y) / (yb - yt)
        inset = int(round(f * 5))
        l, r = 37 + inset, 59 - inset
        k = min(len(STEPS_UP) - 1, int(f * len(STEPS_UP)))
        st = (yb - y) % 6                      # 0-2 espelho (frente do degrau), 3 quina, 4-5 pisada
        if st == 3:
            c = STEPS_UP[min(len(STEPS_UP) - 1, k + 1)]
        elif st >= 4:
            c = STEPS_UP[k]
        else:
            c = STEPS_UP[max(0, k - 2)] if st > 0 else STEPS_UP[max(0, k - 3)]
        wl = CAVE["light"] if f > 0.75 else CAVE["mid"] if f > 0.45 else CAVE["dark"]
        cv.rect(l - 5, y, 5, 1, C(wl))                                    # parede do corte, esquerda (luz)
        cv.rect(r, y, 5, 1, C(CAVE["deep"] if f < 0.6 else CAVE["dark"]))  # direita (sombra)
        cv.rect(l, y, r - l, 1, C(c))
        if st >= 4 and k < 7:                                             # ranhuras antiderrapantes
            for gx in range(l + 3, r - 2, 4):
                cv.px(gx, y, C(STEPS_UP[max(0, k - 1)]))
        cv.px(l - 1, y, C("#e2733a"))                                     # corrimão
        cv.px(r, y, C("#a8471f"))
        if (yb - y) % 12 == 4:                                            # pés do corrimão
            cv.px(l - 2, y, C("#a8471f")); cv.px(r + 1, y, C("#6e2f14"))
        cv.px(l - 6, y, C(OUTLINE))
        cv.px(r + 5, y, C(OUTLINE))
    # raios de luz pontilhados descendo pela escada + poeira no feixe
    for (rx0, ln) in ((42, 26), (46, 34), (50, 30), (54, 20)):
        for y in range(yt + 2, yt + 2 + ln):
            fade = (y - yt) / ln
            if (y + rx0) % 2 == 0 and hsh(rx0, y, 83) > fade * 0.9:
                x = rx0 + (y // 9) % 2 - 1
                cv.px(x, y, C(SUN[1] if fade < 0.5 else SUN[2]))
    for (x, y) in ((44, 41), (51, 47), (47, 55), (53, 37), (41, 60), (49, 65)):
        cv.px(x, y, C(SUN[0]))
    # soleira de metal com faixa de alerta, no chão
    x0, x1 = 37, 59
    cv.rect(x0 - 6, yb, x1 - x0 + 12, 4, C(OUTLINE))
    cv.rect(x0 - 5, yb, x1 - x0 + 10, 2, C("#8c949e"))
    for i in range(x1 - x0 + 10):
        cv.px(x0 - 5 + i, yb, C(GOLD if (i // 3) % 2 == 0 else "#2a2d33"))
    cv.rect(x0 - 5, yb + 1, x1 - x0 + 10, 1, C("#6b717a"))
    # balizas com LED verde e seta de "subir"
    for bx in (x0 - 11, x1 + 8):
        cv.rect(bx - 1, yb - 13, 5, 16, C(OUTLINE))
        cv.rect(bx, yb - 12, 3, 14, C("#c8cdd4"))
        cv.rect(bx, yb - 12, 1, 14, C("#f4f6f8"))
        cv.rect(bx + 2, yb - 12, 1, 14, C("#8c949e"))
        cv.rect(bx, yb - 6, 3, 2, C("#e2733a"))
        cv.rect(bx, yb - 12, 3, 2, C("#7fd67a"))
        cv.px(bx, yb - 12, C("#d6ffd0"))
    sx, sy = x1 + 1, yb - 22                    # plaquinha com seta pra cima, presa na parede direita do corte
    cv.rect(sx, sy, 7, 7, C(OUTLINE))
    cv.rect(sx + 1, sy + 1, 5, 5, C("#1d2a22"))
    cv.px(sx + 3, sy + 2, C("#7fd67a"))
    cv.rect(sx + 2, sy + 3, 3, 1, C("#7fd67a"))
    cv.rect(sx + 3, sy + 4, 1, 2, C("#7fd67a"))
    return cv


# ---------------------------------------------------------------- v5.0 (aprovado): v0.3 · Marco 3 (destroços)

WK = dict(roof="#efe7d4", roofS="#d6ccb4", hi="#fbf7ec", face="#e3d9c3", faceS="#cfc4ab", seam="#bdb197",
          low="#b3a78d", dirty="#a39780", fo="#d39065", foh="#e6b08a", fod="#a8663f",
          m1="#6b717a", m2="#5a6069", m3="#4a4f57", m4="#3b3f46", m5="#2a2d33", void="#1a1c21",
          rib="#9c917a", ribL="#c9bea6", glass="#2a3a48", glassL="#5d7a8c", glassH="#a8c8d8")
DRIFT = dict(hi="#a39385", l="#8e7f73", m="#796b61", d="#625650", dd="#4d433e")


def _drift(cv: Canvas, cx, by, rx, ry, s):
    """Monte de areia acumulada (tom neutro, funciona nos 3 chãos): meia-elipse apoiada na linha `by`,
    crista clara, faixas escurecendo pra base e uns grãos. Sem contorno (é areia, não objeto)."""
    for x in range(int(cx - rx - 1), int(cx + rx + 2)):
        t = (x + 0.5 - cx) / rx
        if abs(t) >= 1:
            continue
        hcol = ry * math.sqrt(1 - t * t) * (1 + 0.07 * math.sin(x * 0.35 + s))
        y0 = int(round(by - hcol))
        for y in range(y0, int(by) + 1):
            d = y - y0
            c = DRIFT["hi"] if d == 0 else DRIFT["l"] if d < 3 else DRIFT["m"] if d < 6 else DRIFT["d"]
            if y == int(by):
                c = DRIFT["dd"]
            cv.px(x, y, C(c))
    for i in range(int(rx // 4)):
        x = int(cx - rx * 0.7 + hsh(i, 1, s) * rx * 1.4)
        y = int(by - 1 - hsh(i, 2, s) * ry * 0.5)
        if cv.a[y, x, 3] == 255 and cv.get(x, y)[:3] != C(DRIFT["hi"])[:3]:
            cv.px(x, y, C(DRIFT["dd"] if i % 2 else DRIFT["hi"]))


def _jag(y, x0, amp, s, step=3):
    return x0 + int(hsh(y // step, 0, s) * amp)


def _wear(L: Canvas, y0, y1, seed, near, k_near=0.52, k_far=0.8):
    """Desgaste: manchas de ruído que escurecem o creme um tom (fuligem/poeira grudada). `near(x, y)` diz
    onde a mancha é mais forte."""
    dark1 = {WK[k]: WK[v] for k, v in (("hi", "roof"), ("roof", "roofS"), ("roofS", "seam"), ("face", "faceS"),
                                         ("faceS", "low"), ("low", "dirty"), ("dirty", "rib"))}
    for y in range(y0, y1):
        for x in range(L.w):
            if L.a[y, x, 3] != 255:
                continue
            hexc = "#%02x%02x%02x" % tuple(L.a[y, x, :3])
            if hexc not in dark1:
                continue
            nn = vnoise(x * 0.18, y * 0.22, seed)
            if (near(x, y) and nn > k_near) or nn > k_far:
                L.px(x, y, C(dark1[hexc]))


def make_wreck_cargo() -> Canvas:
    """Nave de carga caída, 128x112 (4x3 tiles + 16 px pra cima). Fuselagem tubular creme em 3/4 (faixas de
    cilindro), nariz pontudo enfiado na areia à esquerda com o vidro da cabine trincado, faixa laranja
    desbotada, placas do teto arrancadas mostrando as costelas, porta de carga caída virando rampa,
    asa do lado de cá apoiada no chão, asa de lá aparecendo atrás, deriva torta, 2 bocais de motor (um partido)
    e areia acumulada no nariz, na barriga e em cima da asa. Sem sangue, sem corpo."""
    W, H = 128, 112
    cv = Canvas(W, H)
    cv.ellipse(66, 94, 60, 11, SHADOW)
    YT, YB, NOSE = 34, 86, 66                   # topo e barriga do tubo, altura da ponta do nariz

    def xl(y):                                  # perfil do nariz (parábola, ponta embaixo: enterrado)
        return 6 + int(round(26 * ((y - NOSE) / 32) ** 2))

    def xr(y):                                  # traseira levemente arredondada
        return 112 - int(round(5 * abs((y - 60) / 26) ** 3))

    def band(y):
        t = (y - YT) / (YB - YT)
        return ("hi" if t < 0.05 else "roof" if t < 0.36 else "roofS" if t < 0.42 else "face" if t < 0.72
                else "faceS" if t < 0.84 else "low" if t < 0.94 else "dirty")

    # asa de lá (atrás do casco), deriva e antena: camada de trás
    back = Canvas(W, H)
    for i in range(9):
        back.rect(66 + i, 26 + i, 30, 1, C(WK["faceS"] if i else WK["roof"]))
    back.rect(92, 26, 5, 3, C(WK["fo"]))
    for i in range(22):                         # deriva: inclinada pra trás, ponta arrancada
        y = 12 + i
        x0 = 98 - i // 2
        w = 9 + i // 3 if i > 3 else 6
        back.rect(x0, y, w, 1, C(WK["face"] if i > 1 else WK["hi"]))
        back.px(x0, y, C(WK["hi"]))
    back.rect(94, 20, 10, 2, C(WK["fo"])); back.rect(94, 20, 10, 1, C(WK["foh"]))
    back.rect(30, 14, 1, 21, C(WK["m2"])); back.rect(31, 12, 1, 3, C(WK["m2"])); back.rect(32, 10, 1, 3, C(WK["m2"]))
    back.rect(31, 8, 4, 2, C(WK["m1"])); back.px(34, 8, C("#ff5a4a"))
    back.outline(C(OUTLINE))
    cv.paste(back, 0, 0)
    L = Canvas(W, H)
    r = lambda x, y, w, h, c: L.rect(x, y, w, h, C(WK[c]) if c in WK else C(c))   # noqa: E731
    # fuselagem
    for y in range(YT, YB):
        a_, b_ = max(0, xl(y)), xr(y)
        if b_ <= a_:
            continue
        r(a_, y, b_ - a_, 1, band(y))
        L.px(a_, y, C(WK["hi"] if y < NOSE else WK["faceS"]))
    for sx in (40, 58, 76, 94):                 # anéis/junções das placas
        for y in range(YT + 2, YB - 2):
            if xl(y) < sx < xr(y) and band(y) not in ("hi",):
                L.px(sx, y, C(WK["seam"] if band(y) in ("roof", "face") else WK["low"]))
    for y in range(YT, YB):                     # faixa laranja desbotada, descascada em pontos
        pass
    fy = YT + 22
    for x in range(xl(fy) + 2, xr(fy)):
        if hsh(x // 3, 0, 75) > 0.12:
            L.px(x, fy, C(WK["foh"])); L.px(x, fy + 1, C(WK["fo"])); L.px(x, fy + 2, C(WK["fod"]))
    # cabine no nariz: vidro inclinado acompanhando a curva, trincado
    for y in range(YT + 7, YT + 15):
        x0 = xl(y) + 3
        for x in range(x0, x0 + 14):
            c = "glass" if (x - x0) % 5 else "m4"
            if y == YT + 7:
                c = "m4"
            L.px(x, y, C(WK[c]))
    for x in range(xl(YT + 8) + 4, xl(YT + 8) + 13):
        if (x - xl(YT + 8) - 3) % 5:
            L.px(x, YT + 8, C(WK["glassL"]))
    L.px(xl(YT + 8) + 4, YT + 8, C(WK["glassH"]))
    for (dx, dy) in ((8, 9), (9, 10), (10, 10), (11, 11), (12, 12), (10, 12)):
        L.px(xl(YT + dy) + dx, YT + dy, C(WK["glassH"]))
    # placas arrancadas no teto: buraco com costelas e uma placa levantada
    r(56, YT + 3, 16, 10, "void"); r(56, YT + 3, 16, 1, "m5")
    for bx in (58, 62, 66, 70):
        r(bx, YT + 4, 1, 9, "rib"); L.px(bx, YT + 4, C(WK["ribL"]))
    r(73, YT + 1, 4, 10, "roofS"); r(73, YT, 5, 1, "hi")
    # porta de carga aberta (porão escuro com costelas)
    dx0, dx1, dy0 = 40, 64, YT + 27
    r(dx0 - 1, dy0 - 1, dx1 - dx0 + 2, YB - dy0 + 1, "fod")
    r(dx0, dy0, dx1 - dx0, YB - dy0, "void")
    r(dx0, dy0, dx1 - dx0, 2, "m5")
    for bx in range(dx0 + 3, dx1 - 1, 6):
        r(bx, dy0 + 2, 1, YB - dy0 - 3, "m4")
    r(dx0, YB - 3, dx1 - dx0, 1, "m3")
    # registro "07" em stencil
    for gx, rows in ((72, ("###", "#.#", "#.#", "#.#", "###")), (76, ("###", "..#", ".#.", ".#.", ".#."))):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch == "#":
                    L.px(gx + i, YT + 31 + j, C(WK["m4"]))
    # painel lateral arrancado (costelas) e trinca diagonal
    r(86, YT + 27, 12, 12, "void"); r(86, YT + 27, 12, 1, "m5")
    for bx in (88, 92, 96):
        r(bx, YT + 28, 1, 11, "rib")
    for (x, y) in ((85, YT + 30), (85, YT + 31), (98, YT + 33), (91, YT + 39)):
        L.px(x, y, C(WK["ribL"]))
    for k in range(13):
        x, y = 20 + k, YT + 29 + k + k // 3
        if xl(y) < x - 1:
            L.px(x, y, C(WK["m3"]))
            L.px(x + 1, y, C(WK["hi"]))
    # fuligem e desgaste: escurece manchas perto do motor, do buraco do teto e na barriga
    _wear(L, YT, YB, 77, lambda x, y: x > 92 or (50 < x < 80 and y < YT + 16) or (x < 30 and y > YB - 12))
    # bocais do motor na traseira (o de baixo partido)
    for (ny, broken) in ((44, False), (60, True)):
        r(xr(ny + 4) - 1, ny, 10, 12, "m4")
        r(xr(ny + 4) + 1, ny + 1, 8, 10, "m3")
        r(xr(ny + 4) + 3, ny + 3, 6, 6, "void")
        r(xr(ny + 4) + 9, ny - 1, 2, 14, "m2")
        if broken:
            for y in range(ny - 1, ny + 13, 2):
                L.a[y, xr(ny + 4) + 10] = 0
            r(xr(ny + 4) + 9, ny + 6, 2, 7, "m4")
    # porta caída virando rampa até o chão (faixa de alerta desbotada na ponta)
    for y in range(YB, YB + 16):
        f = (y - YB) / 16
        inset = int(round((1 - f) * 2))
        r(dx0 - 2 + inset, y, dx1 - dx0 + 4 - 2 * inset, 1, "m1" if (y - YB) % 4 else "m2")
    r(dx0 - 2, YB + 14, dx1 - dx0 + 4, 2, "m3")
    for i in range(dx1 - dx0 + 4):
        L.px(dx0 - 2 + i, YB + 14, C("#c9a050" if (i // 3) % 2 == 0 else WK["m4"]))
    # trem de pouso torto saindo da barriga
    r(26, YB - 1, 3, 6, "m3"); r(23, YB + 4, 8, 2, "m4")
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    # asa do lado de cá, apoiada no chão (pisada creme, ponta laranja desbotada, borda grossa)
    wing = Canvas(W, H)
    for i in range(20):
        y = YB - 8 + i
        x0 = 74 + i * 3 // 4
        w = 32 - i // 3
        wing.rect(x0, y, w, 1, C(WK["roof"] if i < 15 else WK["faceS"]))
        wing.px(x0, y, C(WK["hi"]))
        wing.px(x0 + w - 1, y, C(WK["seam"]))
    wing.rect(74, YB - 8, 32, 1, C(WK["hi"]))
    for i in range(14, 20):
        wing.rect(74 + i * 3 // 4 + 20, YB - 8 + i, 32 - i // 3 - 20, 1, C(WK["fo"] if i < 18 else WK["fod"]))
    wing.rect(78, YB + 2, 18, 1, C(WK["seam"]))
    wing.rect(87, YB + 12, 24, 2, C(WK["low"]))
    wing.outline(C(OUTLINE))
    cv.paste(wing, 0, 0)
    # areia acumulada
    _drift(cv, 16, YB + 4, 19, 17, 1)          # nariz enterrado
    _drift(cv, 32, YB + 3, 10, 6, 2)
    _drift(cv, 70, YB + 2, 8, 3, 3)
    _drift(cv, 96, YB + 10, 9, 3, 4)            # em cima da asa
    _drift(cv, 116, YB + 9, 10, 4, 5)
    _drift(cv, 52, YB + 15, 6, 2, 6)            # na ponta da rampa
    _drift(cv, 44, YT + 3, 7, 2, 7)             # em cima do casco
    return cv


def _terminal_small(cv: Canvas, x, y):
    """Terminal de parede no estilo do terminal.png, menor (18x16): moldura, tela verde com texto e LED."""
    cv.rect(x, y, 18, 16, C(INK))
    cv.rect(x + 1, y + 1, 16, 14, C("#3a3f3c"))
    cv.rect(x + 1, y + 1, 16, 1, C("#4e5551"))
    cv.rect(x + 1, y + 1, 1, 14, C("#4e5551"))
    cv.rect(x + 3, y + 3, 12, 8, C("#0d1a15"))
    for i, w in enumerate((9, 6, 10)):
        cv.rect(x + 4, y + 4 + i * 2, w, 1, C("#6fe3a0"))
    cv.rect(x + 11, y + 8, 2, 1, C("#6fe3a0"))
    cv.rect(x + 3, y + 12, 12, 2, C("#5a605c"))
    cv.rect(x + 13, y + 12, 2, 2, C("#e2733a"))


def _tilt(cv: Canvas, off) -> Canvas:
    """Inclina um layer deslocando cada coluna x pra baixo `off(x)` px (degraus de 1 px: placa torta)."""
    out = Canvas(cv.w, cv.h)
    for x in range(cv.w):
        d = off(x)
        if d >= 0:
            out.a[d:, x] = cv.a[:cv.h - d, x]
        else:
            out.a[:d, x] = cv.a[-d:, x]
    return out


def make_wreck_module() -> Canvas:
    """Módulo da Colônia Hesper, 96x88 (3x2 tiles + 24 px pra cima). Caixa habitável creme, afundada na areia
    do lado esquerdo, teto com placa rasgada, antena parabólica tombada, emblema da colônia desbotado,
    porta emperrada meio aberta, janelas (uma quebrada), asa solar partida caída à direita e um terminal
    ainda ligado na lateral (estilo do terminal.png)."""
    W, H = 96, 88
    cv = Canvas(W, H)
    cv.ellipse(48, 79, 46, 8, SHADOW)
    L = Canvas(W, H)
    r = lambda x, y, w, h, c: L.rect(x, y, w, h, C(WK[c]) if c in WK else C(c))   # noqa: E731
    RT, FT, GB = 18, 44, 78
    x0, x1 = 6, 84
    # teto com cantos de trás chanfrados
    for y in range(RT, FT):
        k = max(0, 4 - (y - RT))
        r(x0 + k, y, x1 - x0 - 2 * k, 1, "roof")
        if k:
            L.px(x0 + k, y, C(WK["hi"])); L.px(x1 - k - 1, y, C(WK["roofS"]))
    r(x0 + 4, RT, x1 - x0 - 8, 1, "hi")
    for sx in (32, 58):
        r(sx, RT + 2, 1, FT - RT - 3, "roofS")
    r(x0 + 2, RT + 13, x1 - x0 - 4, 1, "roofS")
    r(x0, FT - 1, x1 - x0, 1, "hi")
    # placa do teto rasgada (buraco com costelas) e caixa de ventilação
    r(38, 19, 16, 9, "void"); r(38, 19, 16, 1, "m5")
    for bx in (41, 45, 49):
        r(bx, 20, 1, 8, "rib")
    r(37, 28, 18, 1, "seam")
    r(64, 18, 12, 9, "m4"); r(64, 18, 12, 2, "m2")
    for i in range(3):
        r(66, 21 + i * 2, 8, 1, "m5")
    # lateral
    r(x0, FT, x1 - x0, GB - FT, "face")
    r(x0, FT, x1 - x0, 1, "seam")
    r(x0, FT, 4, GB - FT, "faceS")                              # facetas laterais
    r(x1 - 4, FT, 4, GB - FT, "seam")
    r(x0 + 4, GB - 6, x1 - x0 - 8, 6, "low")
    r(x0 + 4, GB - 2, x1 - x0 - 8, 2, "dirty")
    r(x0 + 4, FT + 13, x1 - x0 - 8, 2, "fo")                    # faixa desbotada
    r(x0 + 4, FT + 13, x1 - x0 - 8, 1, "foh")
    for (px_, w_) in ((40, 3), (52, 2)):
        r(px_, FT + 13, w_, 2, "face")
    # porta emperrada meio aberta (esquerda)
    r(12, FT + 4, 14, GB - FT - 4, "fod")
    r(13, FT + 5, 12, GB - FT - 5, WK["m2"])
    r(13, FT + 5, 7, GB - FT - 5, WK["m1"])
    r(20, FT + 5, 4, GB - FT - 5, "void")                       # fresta escura
    r(14, FT + 8, 4, 3, "glass"); L.px(14, FT + 8, C(WK["glassH"]))
    # janelas (uma quebrada)
    for i, wx in enumerate((30, 38, 46)):
        r(wx, FT + 4, 6, 6, "m5")
        r(wx + 1, FT + 5, 4, 4, "glass" if i != 2 else "void")
        if i != 2:
            r(wx + 1, FT + 5, 4, 1, "glassL"); L.px(wx + 1, FT + 5, C(WK["glassH"]))
    L.px(47, FT + 8, C(WK["glassL"])); L.px(49, FT + 6, C(WK["glassL"]))
    # emblema da colônia desbotado: anel laranja com um H
    ex, ey = 34, FT + 19
    for (x, y) in ((ex + 2, ey), (ex + 3, ey), (ex + 4, ey), (ex + 1, ey + 1), (ex + 5, ey + 1), (ex, ey + 2), (ex + 6, ey + 2),
                   (ex, ey + 3), (ex + 6, ey + 3), (ex, ey + 4), (ex + 6, ey + 4), (ex + 1, ey + 5), (ex + 5, ey + 5),
                   (ex + 2, ey + 6), (ex + 3, ey + 6), (ex + 4, ey + 6)):
        L.px(x, y, C(WK["fo"]))
    r(ex + 2, ey + 2, 1, 3, "fod"); r(ex + 4, ey + 2, 1, 3, "fod"); L.px(ex + 3, ey + 3, C(WK["fod"]))
    # placa da lateral solta, pendurada
    r(48, FT + 19, 8, 9, "faceS"); r(48, FT + 19, 8, 1, "hi"); r(55, FT + 20, 1, 8, "seam")
    r(48, FT + 18, 8, 1, "void")
    for k in range(11):                                         # trinca na lateral
        x, y = 70 + k // 2, FT + 2 + k
        L.px(x, y, C(WK["m3"])); L.px(x + 1, y, C(WK["hi"]))
    r(76, FT + 3, 4, 7, "void")                                 # canto da lateral arrancado
    L.px(76, FT + 10, C(WK["ribL"])); L.px(79, FT + 10, C(WK["rib"]))
    _wear(L, RT, GB, 78, lambda x, y: x < 30 or (34 < x < 58 and y < RT + 14) or y > GB - 10)
    L.outline(C(OUTLINE))
    tilt = lambda x: max(0, (60 - x) // 14)       # noqa: E731  lado esquerdo afundado na areia
    cv.paste(_tilt(L, tilt), 0, 0)
    # terminal na lateral, ainda ligado (2a coluna de tiles da direita)
    term = Canvas(W, H)
    _terminal_small(term, 62, FT + 15)
    cv.paste(_tilt(term, tilt), 0, 0)
    # antena parabólica tombada no teto
    dish = Canvas(W, H)
    dish.ellipse(20, 12, 9, 5, C(WK["roof"]))
    dish.ellipse(21, 13, 6, 3, C(WK["faceS"]))
    dish.ellipse(21, 13, 3, 1.6, C(WK["seam"]))
    dish.rect(20, 16, 2, 8, C(WK["m2"]))
    dish.rect(17, 23, 8, 2, C(WK["m3"]))
    dish.rect(25, 7, 1, 4, C(WK["m2"])); dish.px(26, 6, C("#ff5a4a"))
    dish.outline(C(OUTLINE))
    cv.paste(_tilt(dish, tilt), 0, 0)
    # asa solar partida, caída no chão à direita
    wing = Canvas(W, H)
    for i in range(8):
        wing.rect(80 + i // 2, 72 + i, 14 - i // 2, 1, C("#1f3a6e"))
    for (x, y) in ((83, 73), (87, 73), (91, 73), (84, 76), (88, 76), (92, 76)):
        wing.px(x, y, C("#4f74b8"))
    wing.rect(80, 72, 14, 1, C("#c8cdd4"))
    for (x, y) in ((86, 74), (87, 75), (88, 76), (88, 77)):
        wing.px(x, y, C("#9fc4f5"))
    wing.rect(84, 64, 2, 9, C(WK["m2"]))
    wing.outline(C(OUTLINE))
    cv.paste(wing, 0, 0)
    # areia acumulada: lado esquerdo afundado e pé da frente
    _drift(cv, 10, GB + 2, 13, 12, 11)
    _drift(cv, 34, GB + 1, 10, 3, 12)
    _drift(cv, 60, GB + 1, 12, 4, 13)
    _drift(cv, 90, GB + 3, 7, 4, 14)
    _drift(cv, 16, RT + 8, 7, 3, 15)
    return cv


GOLDF = ["#fff3c4", "#f2c46d", "#d9a64e", "#b8893a", "#8a6428"]       # folha dourada (MLI) da sonda


def make_wreck_probe() -> Canvas:
    """Sonda pequena, 64x64 (2x2 tiles): corpo compacto embrulhado em folha dourada amassada, convés de
    instrumentos em cima, parabólica torta, olho-sensor com brilho ciano, LED vermelho ainda aceso,
    uma asa solar aberta e a outra partida no chão, pernas abertas e a marca do impacto (sulco de areia)."""
    W = 64
    cv = Canvas(W, W)
    cv.ellipse(32, 55, 30, 7, SHADOW)
    _drift(cv, 32, 58, 29, 6, 21)                               # sulco/borda do impacto atrás
    L = Canvas(W, W)
    r = lambda x, y, w, h, c: L.rect(x, y, w, h, C(WK[c]) if c in WK else C(c))   # noqa: E731
    # pernas abertas
    r(14, 46, 3, 6, "m3"); r(11, 51, 6, 2, "m4")
    r(46, 46, 3, 6, "m3"); r(46, 51, 6, 2, "m4")
    # corpo: convés em cima + frente dourada
    r(19, 22, 26, 9, "m3")
    r(18, 23, 28, 8, "m3")
    r(19, 22, 26, 1, "m1")
    r(19, 23, 26, 1, "m2")
    r(21, 25, 7, 4, "m5"); r(22, 26, 5, 1, "m2")              # caixa de instrumento
    r(36, 24, 6, 5, "faceS"); r(36, 24, 6, 1, "hi")             # câmera/caixa clara
    for y in range(31, 49):
        for x in range(18, 46):
            if (y > 45 and (x - 18 < y - 45 or 45 - x < y - 45)):
                continue                                        # cantos de baixo chanfrados
            nn = vnoise(x * 0.3 + y * 0.12, y * 0.3, 93)
            k = 1 if nn > 0.62 else 2 if nn > 0.38 else 3
            if x < 20:
                k = max(0, k - 1)
            elif x > 43:
                k = min(4, k + 1)
            if y > 44:
                k = min(4, k + 1)
            L.px(x, y, C(GOLDF[k]))
    for (x, y) in ((22, 41), (23, 42), (24, 42), (25, 43), (38, 44), (39, 44), (40, 45), (29, 33), (30, 34)):
        L.px(x, y, C(GOLDF[0]))                                 # vincos claros da folha
    r(18, 31, 28, 1, "fod")                                     # aro laranja desbotado
    r(18, 32, 28, 1, "fo")
    # olho-sensor
    r(33, 35, 8, 8, "m5")
    r(34, 36, 6, 6, "#14202b")
    r(35, 37, 3, 3, "#2b7f99")
    L.px(35, 37, C("#d8fbff")); L.px(36, 37, C("#59d0e6"))
    # LED vermelho ainda aceso + plaquinha
    r(22, 36, 6, 4, "m4"); L.px(23, 37, C("#ff5a4a")); L.px(24, 37, C("#ffd0c8"))
    # asa solar aberta à esquerda (num braço)
    r(13, 28, 5, 2, "m2")
    for y in range(24, 36):
        r(2, y, 11, 1, "#1f3a6e")
        L.px(2, y, C("#c8cdd4"))
    for y in (27, 31):
        r(3, y, 10, 1, "#4f74b8")
    r(7, 24, 1, 12, "#4f74b8")
    L.px(4, 25, C("#9fc4f5")); L.px(5, 25, C("#9fc4f5")); L.px(4, 26, C("#9fc4f5"))
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    # parabólica torta em cima
    dish = Canvas(W, W)
    dish.ellipse(27, 12, 10, 6, C(WK["roof"]))
    dish.ellipse(28, 13, 7, 4, C(WK["faceS"]))
    dish.ellipse(28, 13, 3, 2, C(WK["seam"]))
    dish.px(24, 9, C(WK["hi"])); dish.px(25, 8, C(WK["hi"]))
    dish.rect(30, 17, 2, 6, C(WK["m2"]))
    dish.rect(33, 6, 1, 6, C(WK["m1"])); dish.rect(32, 5, 3, 1, C(WK["m2"]))
    dish.outline(C(OUTLINE))
    cv.paste(dish, 0, 0)
    # asa partida no chão à direita
    wing = Canvas(W, W)
    for i in range(6):
        wing.rect(48 + i, 47 + i, 13 - i, 1, C("#1f3a6e"))
    wing.rect(48, 47, 13, 1, C("#c8cdd4"))
    wing.px(52, 49, C("#4f74b8")); wing.px(56, 49, C("#4f74b8")); wing.px(55, 51, C("#9fc4f5"))
    wing.outline(C(OUTLINE))
    cv.paste(wing, 0, 0)
    _drift(cv, 26, 50, 12, 4, 22)                               # areia na frente do corpo
    _drift(cv, 8, 52, 7, 3, 23)
    return cv


def make_loot_crate(empty: bool) -> Canvas:
    """Caixa de saque 32x32: case de carga pesado (cinza-chumbo), cantoneiras creme, tampa com faixa laranja
    desbotada, alças laterais, trava com LED âmbar (cheia). Vazia: tampa aberta pra trás, interior escuro,
    LED apagado. Base na linha 28."""
    cv = Canvas(32, 32)
    cv.ellipse(16, 28.5, 14, 2.5, SHADOW)
    B = Canvas(32, 32)
    r = lambda x, y, w, h, c: B.rect(x, y, w, h, C(WK[c]) if c in WK else C(c))   # noqa: E731
    # frente da caixa
    r(5, 16, 22, 11, "m2")
    r(5, 16, 22, 1, "m1")
    for x in range(8, 25, 4):                                   # nervuras
        r(x, 17, 1, 9, "m3")
    r(5, 25, 22, 2, "m4")
    for cx_ in (4, 25):                                         # cantoneiras creme
        r(cx_, 15, 3, 13, "faceS")
        r(cx_, 15, 1, 13, "hi")
        r(cx_ + 2, 15, 1, 13, "seam")
        B.px(cx_ + 1, 18, C(WK["seam"])); B.px(cx_ + 1, 24, C(WK["seam"]))
    r(2, 19, 2, 4, "m4"); r(28, 19, 2, 4, "m4")                 # alças
    r(2, 20, 1, 2, "m2"); r(29, 20, 1, 2, "m2")
    if not empty:
        # tampa fechada: topo visto de cima + aba
        r(4, 8, 24, 6, "m1")
        r(4, 8, 24, 1, "#8c949e")
        r(4, 12, 24, 2, "fo"); r(4, 12, 24, 1, "foh")
        r(4, 14, 24, 1, "m4")
        for cx_ in (4, 25):
            r(cx_, 8, 3, 6, "faceS"); r(cx_, 8, 1, 6, "hi")
        r(9, 9, 14, 2, "m2")                                    # alça da tampa
        r(9, 9, 14, 1, "m3")
        # trava + LED âmbar
        r(13, 15, 6, 6, "m4")
        r(14, 16, 4, 3, "m1")
        B.px(15, 17, C("#ffb84a")); B.px(16, 17, C("#ffe2a0"))
        B.outline(C(OUTLINE))
        cv.paste(B, 0, 0)
        return cv
    # aberta: interior escuro + tampa em pé atrás
    r(4, 10, 24, 6, "m5")
    r(5, 11, 22, 4, "void")
    r(5, 11, 22, 1, "m4")                                       # parede de trás de dentro
    r(4, 15, 24, 1, "m1")                                       # beirada da frente
    for cx_ in (4, 25):
        r(cx_, 10, 3, 6, "faceS"); r(cx_, 10, 1, 6, "hi")
    r(13, 15, 6, 5, "m4"); r(14, 16, 4, 2, "m3")                # trava solta
    B.px(15, 16, C("#5a3a2a")); B.px(16, 16, C("#5a3a2a"))      # LED apagado
    lid = Canvas(32, 32)                                        # tampa: lado de dentro, em pé
    lid.rect(4, 2, 24, 8, C(WK["m3"]))
    lid.rect(5, 3, 22, 6, C(WK["m4"]))
    lid.rect(4, 2, 24, 1, C(WK["m2"]))
    lid.rect(6, 4, 20, 1, C(WK["m3"]))
    lid.rect(6, 7, 20, 1, C(WK["m3"]))
    lid.rect(4, 9, 24, 1, C(WK["fod"]))
    for cx_ in (4, 25):
        lid.rect(cx_, 2, 3, 8, C(WK["seam"]))
    B.paste(lid, 0, 0)
    B.outline(C(OUTLINE))
    cv.paste(B, 0, 0)
    return cv


def make_icon_blueprint() -> Canvas:
    """Projeto: folha de planta azul (canto dobrado, grade e o desenho de uma máquina) com um chip de dados
    laranja de contatos dourados preso embaixo."""
    cv = Canvas(16, 16)
    L = Canvas(16, 16)
    L.rect(2, 1, 12, 12, C("#2f62b3"))
    L.rect(2, 1, 12, 1, C("#4f86d6"))
    L.rect(2, 1, 1, 12, C("#4f86d6"))
    L.rect(13, 2, 1, 11, C("#24508f"))
    for g in (5, 9):                                            # grade
        L.rect(3, g, 10, 1, C("#3f74c4"))
        L.rect(g, 2, 1, 10, C("#3f74c4"))
    L.rect(4, 4, 5, 5, C("#cfe6ff"))                            # desenho: corpo de máquina + roda
    L.rect(5, 5, 3, 3, C("#2f62b3"))
    L.px(10, 6, C("#cfe6ff")); L.px(11, 7, C("#cfe6ff")); L.px(10, 8, C("#cfe6ff")); L.px(9, 7, C("#cfe6ff"))
    L.rect(4, 10, 7, 1, C("#cfe6ff"))
    for (x, y) in ((11, 1), (12, 1), (13, 1), (12, 2), (13, 2), (13, 3)):   # canto dobrado
        L.a[y, x] = 0
    L.px(11, 2, C("#9cc2f0")); L.px(12, 3, C("#9cc2f0")); L.px(11, 3, C("#7fa8e0"))
    L.rect(4, 11, 9, 4, C(MT["o"]))                             # chip
    L.rect(4, 11, 9, 1, C(MT["oh"]))
    L.rect(4, 14, 9, 1, C(MT["od"]))
    for x in (5, 7, 9, 11):
        L.px(x, 13, C(GOLD))
    L.px(5, 12, C("#fff3c4"))
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


def make_icon_o2_tank() -> Canvas:
    """Tanque de O₂ (equipamento): par de cilindros brancos de mochila com faixa ciano, cinta escura,
    válvulas com manopla laranja e um manômetro."""
    cv = Canvas(16, 16)
    L = Canvas(16, 16)
    for tx in (1, 9):
        L.rect(tx, 4, 6, 10, C(MT["w"]))
        L.rect(tx + 1, 3, 4, 1, C(MT["w"]))
        L.rect(tx + 3, 4, 2, 10, C(MT["m"]))
        L.rect(tx + 5, 4, 1, 10, C(MT["s"]))
        L.rect(tx + 1, 3, 1, 1, C("#ffffff"))
        L.rect(tx, 7, 6, 2, C("#59d0e6"))
        L.rect(tx + 4, 7, 2, 2, C("#2b9fb8"))
        L.rect(tx, 13, 6, 1, C(MT["s"]))
        L.rect(tx + 2, 1, 2, 2, C(MT["g"]))                      # válvula
        L.rect(tx + 1, 0, 4, 1, C(MT["o"]))
    L.rect(1, 11, 14, 1, C(MT["k"]))                             # cinta
    L.rect(6, 10, 4, 3, C(MT["kk"]))
    L.px(7, 11, C(MT["d"]))
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


def make_icon_scanner() -> Canvas:
    """Scanner de navegação: aparelho de mão escuro com tela de minimapa (anéis de radar, ponto do player e
    um alvo), antena com ponta vermelha e botões laranja/verde."""
    cv = Canvas(16, 16)
    L = Canvas(16, 16)
    L.rect(2, 3, 11, 12, C(MT["k"]))
    L.rect(2, 3, 11, 1, C(MT["g"]))
    L.rect(2, 3, 1, 12, C(MT["g"]))
    L.rect(3, 13, 9, 2, C(MT["o"]))
    L.rect(3, 13, 9, 1, C(MT["oh"]))
    L.rect(3, 4, 9, 7, C("#0d1a2a"))                             # tela
    for (x, y) in ((5, 5), (6, 5), (7, 5), (8, 5), (9, 5), (4, 6), (10, 6), (4, 7), (10, 7), (4, 8), (10, 8),
                   (5, 9), (6, 9), (7, 9), (8, 9), (9, 9)):
        L.px(x, y, C("#1f5a66"))
    L.px(7, 7, C("#59d0e6")); L.px(6, 7, C("#2b9fb8")); L.px(7, 6, C("#2b9fb8"))
    L.px(9, 6, C("#7fd67a"))
    L.px(5, 8, C(GOLD))
    L.px(4, 11, C(MT["o"])); L.px(6, 11, C(MT["led"]))          # botões
    L.rect(9, 11, 3, 1, C(MT["g"]))
    L.rect(11, 0, 1, 3, C(MT["m"]))                              # antena
    L.px(11, 0, C(MT["red"]))
    L.outline(C(OUTLINE))
    cv.paste(L, 0, 0)
    return cv


WRECK_INFO = {
    # tamanho em tiles, tile da caixa de saque e do terminal (relativos ao tile de cima/esquerda do destroço)
    "wreck_cargo.png": dict(tiles=(4, 3), crate=(1, 3), terminal=None),
    "wreck_module.png": dict(tiles=(3, 2), crate=(0, 2), terminal=(2, 1)),
    "wreck_probe.png": dict(tiles=(2, 2), crate=(2, 1), terminal=None),
}


def from_px(pc) -> Canvas:
    """Converte o canvas do explorer.py/hand_drill.py pro Canvas deste script (mesmos pixels)."""
    cv = Canvas(pc.w, pc.h)
    cv.a = pc.a.copy()
    return cv


def build_explorer() -> dict[str, Canvas]:
    """v6.0 (aprovado): Explorador com visor dourado. Parado, caminhada, idle e mine (tools/sprites/explorer.py)."""
    out: dict[str, Canvas] = {}
    for view in ("down", "up", "side"):
        out[f"player_{view}.png"] = from_px(ex.make_player(view))
        out[f"player_walk_{view}.png"] = from_px(ex.make_walk(view))
        out[f"player_idle_{view}.png"] = from_px(ex.make_idle(view))
        out[f"player_mine_{view}.png"] = from_px(ex.make_mine(view))
    return out


def build_pending() -> dict[str, Canvas]:
    """Assets novos aguardando aprovação do dono: vão pra assets/sprites/_pending/.
    Depois de aprovados, saem daqui e entram em build_v02()/build_v03()/build_v05()/build_sprites() (pasta oficial).
    Vazio agora: na v6.0 o dono escolheu a broca A (virou o drill_* oficial); B e C seguem no hand_drill.py."""
    return {}


def build_candidates() -> dict[str, Canvas]:
    """Variantes pro dono escolher: vão pra assets/sprites/_pending/candidates/. Vazio agora: na v5.1 o dono escolheu
    a A (virou o lamp_t2 oficial); a B segue no make_lamp_t2("B") e, de histórico, em reports/design/before/."""
    return {}


def build_v51() -> dict[str, Canvas]:
    """Luminária forte (variante A), aprovada na v5.1."""
    return {
        "lamp_t2.png": make_lamp_t2("A"),
        "icon_lamp_t2.png": make_icon_lamp_t2(),
    }


def build_v05() -> dict[str, Canvas]:
    """Sprites do v0.3 · Marco 2 (caverna) e Marco 3 (destroços), aprovados na v5.0."""
    return {
        "lamp.png": make_lamp(),
        "icon_lamp.png": make_icon_lamp(),
        "cave_ramp_up.png": make_cave_ramp_up(),
        "wreck_cargo.png": make_wreck_cargo(),
        "wreck_module.png": make_wreck_module(),
        "wreck_probe.png": make_wreck_probe(),
        "loot_crate.png": make_loot_crate(False),
        "loot_crate_empty.png": make_loot_crate(True),
        "icon_blueprint.png": make_icon_blueprint(),
        "icon_o2_tank.png": make_icon_o2_tank(),
        "icon_scanner.png": make_icon_scanner(),
    }


FUTURE = OUT / "_future"  # guardados pelo dono pro futuro: fora do contrato, o jogo não carrega daqui


def build_future() -> dict[str, Canvas]:
    return {"pod_wide.png": make_pod_lander("pod_wide.png")}   # cápsula larga 96x64 (proposta, guardada)


def build_v03() -> dict[str, Canvas]:
    """Sprites do v0.3 · Marco 1 (superfície), aprovados na v4.0; névoa marrom, verde de verdade e autotile
    de água aprovados na v4.1. A cápsula nova entra em build_sprites()."""
    out: dict[str, Canvas] = {}
    for v in range(4):
        out[f"sand_dead_{v}.png"] = make_sand("dead", v)
        out[f"sand_mist_{v}.png"] = make_soil_mist(v)       # v4.1 (o make_sand("mist") da v4.0 fica de histórico)
        out[f"sand_green_{v}.png"] = make_grass_green(v)    # v4.1
    for st in ("mist", "green"):                              # v4.1: autotile A2 de água (no morto não há água)
        out[f"water_auto_{st}.png"] = make_water_auto(st, make_water(st).image())
    out["rock_small.png"] = make_rock_small()
    for o in ("iron", "silicon", "ice"):
        out[f"pickup_{o}.png"] = make_pickup(o)
    out["crater.png"] = make_crater()
    out["crater_ramp.png"] = make_crater_ramp()
    return out


def build_v02() -> dict[str, Canvas]:
    """Sprites do v0.2, aprovados na v3.2."""
    return {
        "chest.png": make_chest(False),
        "chest_open.png": make_chest(True),
        "solar_panel.png": make_solar(),
        "drone_station.png": make_station(),
        "drone.png": make_drone_sheet(),
        "icon_chest.png": make_icon_chest(),
        "icon_solar.png": make_icon_solar(),
        "icon_drone_station.png": make_icon_station(),
        "ui_slot.png": make_ui_slot(),
        "icon_drone.png": make_icon_drone(),          # aprovado na v3.3
    }


# ---------------------------------------------------------------- geração de tudo

def build_sprites() -> dict[str, Canvas]:
    out: dict[str, Canvas] = {}
    for view in ("down", "up", "side"):
        out[f"drill_{view}.png"] = from_px(hd.make_drill("A", view))   # v6.0: A (furadeira de bolso), aprovada; a v2.1 é o make_drill
    out.update(build_explorer())        # v6.0: o astronauta chibi antigo (make_player/make_walk) fica de histórico
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
    out["pod.png"] = make_pod_lander("pod.png")   # v4.0: módulo de fuga pousado (o make_pod antigo fica de histórico)
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
    out.update(build_v02())
    out.update(build_v03())
    out.update(build_v05())
    out.update(build_v51())
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
    base_v02 = {(11, 5), (12, 5), (13, 5), (15, 5), (16, 4), (17, 4), (16, 5), (17, 5)}
    for c in base_v02:                           # baú, painéis e estação (v0.2)
        g[c[1]][c[0]] = FL
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
                    (20, 9), (21, 9), (22, 9), (14, 0), (14, 1)} | vein_cells | base_v02
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
        if name.startswith("landed:"):
            _, lx, ly = name.split(":")
            img.alpha_composite(spr["drone.png"].crop((0, 0, 16, 16)), (int(lx) - 8, int(ly) - 10))
            return
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

    # v0.2 (pendentes): baú, painéis solares e estação de drones na base
    for sx_ in (11, 12, 13):
        obj("solar_panel.png", sx_ * T + 16, 6 * T)
    obj("chest_open.png" if stage == "green" else "chest.png", 15 * T + 16, 6 * T)
    flying = []
    if stage != "dead":                       # a estação só libera na Névoa
        st_ax, st_ay = 17 * T, 6 * T
        obj("drone_station.png", st_ax, st_ay)
        sx0, sy0 = st_ax - 32, st_ay - 72
        # um drone pousado no pad 1; o outro está voando
        objs.append((st_ay + 0.5, f"landed:{sx0 + STATION_PADS[0][0]}:{sy0 + STATION_PADS[0][1]}", 0))
        flying.append((10 * T + 16, 2 * T + 18, 1))     # por cima da parede (face), sombra cai no chão
        flying.append((19 * T + 4, 6 * T + 26, 3))     # sobre o chão, chegando na estação

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
    # drones voando: por cima de tudo; sombra no chão 18 px abaixo (altitude)
    for dx, dy, f in flying:
        sh = Canvas(14, 6)
        sh.ellipse(7, 3, 6, 2.5, SHADOW)
        img.alpha_composite(sh.image(), (dx - 7, dy + 18 - 3))
        img.alpha_composite(spr["drone.png"].crop((f * 16, 0, f * 16 + 16, 16)), (dx - 8, dy - 8))
    return img.crop((0, 0, 960, 540)).convert("RGB")



# ---------------------------------------------------------------- prévia da superfície (v0.3 · Marco 1)

def sand_variant(x: int, y: int, seed: int = 5) -> int:
    """Escolha sugerida da variação da areia (pro Dev copiar): areia lisa domina (~70%), cascalho ~20%,
    ondulações agrupadas em faixas largas (zonas de duna) e lajes raras e espalhadas (agrupadas viram grade)."""
    dune = vnoise(x * 0.11 + 3.1, y * 0.23 + 1.7, seed)        # faixas mais largas que altas = vento
    rock = vnoise(x * 0.17 + 40.3, y * 0.17 + 9.2, seed + 1)
    r = hsh(x, y, seed + 2)
    if dune > 0.6 and r < 0.55:
        return 2
    if rock > 0.66 and r < 0.12:
        return 3
    return 0 if r < 0.72 else 1 if r < 0.92 else 2 if r < 0.965 else 3


def sand_key(spr, stage, v):
    """Areia pendente (se houver) na frente da oficial: prévias e testes mostram a versão nova."""
    k = f"_pending/sand_{stage}_{v}.png"
    return k if k in spr else f"sand_{stage}_{v}.png"


def render_sand_field(stage: str, spr: dict[str, Image.Image], uniform=False) -> Image.Image:
    img = Image.new("RGBA", (GW * T, GH * T))
    for y in range(GH):
        for x in range(GW):
            v = int(hsh(x, y, 3) * 4) if uniform else sand_variant(x, y)
            img.alpha_composite(spr[sand_key(spr, stage, v)], (x * T, y * T))
    return img.crop((0, 0, 960, 540)).convert("RGB")


SURF_HILLS = [  # morros (parede), em tiles
    (2, 2), (3, 2), (4, 2), (2, 3), (3, 3), (4, 3), (5, 3), (3, 4), (4, 4),
    (26, 11), (27, 11), (25, 12), (26, 12), (27, 12), (28, 12), (26, 13), (27, 13),
    (8, 14), (9, 14),
]
SURF_ROCKS = [(7, 3), (11, 2), (20, 13), (23, 9), (4, 9), (13, 14), (28, 6), (1, 12), (18, 2), (24, 14)]
SURF_PICKUPS = [  # (x px, y px do ponto de chão, minério)
    (6 * T + 10, 6 * T + 20, "iron"), (8 * T + 22, 11 * T + 14, "silicon"), (19 * T + 6, 14 * T + 22, "ice"),
    (21 * T + 20, 11 * T + 26, "iron"), (12 * T + 14, 3 * T + 22, "ice"), (27 * T + 8, 8 * T + 18, "silicon"),
    (2 * T + 18, 7 * T + 24, "iron"), (16 * T + 26, 15 * T + 10, "silicon"), (10 * T + 4, 16 * T + 12, "iron"),
    (25 * T + 16, 15 * T + 20, "ice"), (6 * T + 26, 13 * T + 6, "ice"), (22 * T + 8, 1 * T + 24, "silicon"),
]
SURF_CRATER = (22, 2)       # tile de cima/esquerda dos 3x3


def render_surface(stage: str, spr: dict[str, Image.Image]) -> Image.Image:
    """Superfície, com a mesma ordem do jogo: (1) areia, água e veio; (2) linha por linha: topo da parede
    (y−24) + face (y+8) e depois os objetos cuja âncora cai na linha (cratera, rochas, pickups, máquinas)."""
    P = ""
    hills = set(SURF_HILLS)
    water = set()
    auto = f"water_auto_{stage}.png" in spr
    if stage == "mist":
        water = {(18, 13), (19, 13), (19, 14), (11, 14)} if auto else {(18, 12), (19, 12)}
    elif stage == "green":
        water = ({(18, 13), (19, 13), (20, 13), (17, 14), (18, 14), (19, 14), (20, 14), (21, 14), (18, 15), (20, 15),
                  (21, 15), (19, 16), (20, 16), (3, 15), (4, 15), (4, 16), (11, 14)} if auto else
                 {(18, 12), (19, 12), (17, 13), (18, 13), (19, 13), (3, 15), (4, 15), (4, 16)})
    vein = (3, 11)
    img = Image.new("RGBA", (GW * T, GH * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 10), (0, 0, 0, 84))
    shade_b = Image.new("RGBA", (T, 6), (0, 0, 0, 40))
    for y in range(GH):
        for x in range(GW):
            if (x, y) in hills:
                continue
            if (x, y) in water and not auto:
                img.alpha_composite(spr[f"water_{stage}.png"], (x * T, y * T))
            else:
                img.alpha_composite(spr[sand_key(spr, stage, sand_variant(x, y))], (x * T, y * T))
                if (x, y) in water:                          # autotile por cima do chão (fora da margem é transparente)
                    draw_water_auto(img, spr[f"water_auto_{stage}.png"], water, x, y, x * T, y * T)
            if (x, y - 1) in hills:
                img.alpha_composite(shade, (x * T, y * T))
                img.alpha_composite(shade_b, (x * T, y * T + 10))
    img.alpha_composite(spr["vein_iron.png"], (vein[0] * T, vein[1] * T))

    objs = []

    def obj(name, ax, ay):
        objs.append((ay, ax, name))

    cx, cy = SURF_CRATER
    obj(f"{P}crater_ramp.png" if stage == "green" else f"{P}crater.png", (cx + 1.5) * T, (cy + 3) * T)
    for (x, y) in SURF_ROCKS:
        if (x, y) not in water:
            obj(f"{P}rock_small.png", x * T + 16, (y + 1) * T)
    for (px_, py_, o) in SURF_PICKUPS:
        if (px_ // T, py_ // T) not in water:
            obj(f"{P}pickup_{o}.png", px_, py_)
    if stage == "green":                                       # proposta larga: 3x1, centro do tile do meio
        obj("_future/pod_wide.png", 15 * T + 16, 9 * T)
    else:                                                      # redesign no contrato atual (2x1)
        obj(f"{P}pod.png", 15 * T, 9 * T)
    t2 = stage != "dead"
    obj("machine_o2_t2.png" if t2 else "machine_o2.png", 12 * T + 16, 9 * T)
    obj("machine_heater_t2.png" if stage == "green" else "machine_heater.png", 18 * T + 16, 9 * T)
    obj("machine_melter_t2.png" if t2 else "machine_melter.png", 13 * T + 16, 11 * T)
    for sx_ in (12, 13, 14):
        obj("solar_panel.png", sx_ * T + 16, 6 * T)
    obj("chest.png", 17 * T + 16, 6 * T)
    if t2:
        obj("drone_station.png", 18 * T, 12 * T)
        obj("machine_drill.png#1", (vein[0] + 1) * T, (vein[1] + 2) * T)
    if stage == "green":
        for (x, y, k) in ((10, 8, "plant_bush.png"), (11, 12, "plant_flower.png"), (20, 8, "plant_tree.png"),
                          (16, 12, "plant_bush.png"), (9, 10, "plant_flower.png"), (21, 10, "plant_bush.png")):
            obj(k, x * T + 16, y * T + 30)
    obj("player", 16 * T + 20, 10 * T + 20)

    def draw(ay, ax, name):
        if name == "player":
            sh = Canvas(20, 7)
            sh.ellipse(10, 3.5, 8, 2.5, SHADOW)
            img.alpha_composite(sh.image(), (int(ax) - 10, int(ay) - 4))
            img.alpha_composite(spr["player_down.png"], (int(ax) - 16, int(ay) - 32))
            return
        if name.startswith(P + "pickup_"):
            img.alpha_composite(spr[name], (int(ax) - 8, int(ay) - 14))
            return
        if "#" in name:
            n, fr = name.split("#")
            s = spr[n].crop((int(fr) * 64, 0, int(fr) * 64 + 64, 80))
        else:
            s = spr[name]
        img.alpha_composite(s, (int(ax - s.width // 2), int(ay - s.height)))

    for y in range(GH + 1):
        for x in range(GW):
            if (x, y) not in hills:
                continue
            img.alpha_composite(spr[f"wall_{stage}_{int(hsh(x, y, 91) * 3)}.png"], (x * T, y * T - 24))
            if (x, y + 1) not in hills:
                img.alpha_composite(spr[f"wall_face_{stage}.png"], (x * T, y * T + 8))
        for o in sorted(o for o in objs if (o[0] - 1) // T == y):
            draw(*o)
    return img.crop((0, 0, 960, 540)).convert("RGB")


# ---------------------------------------------------------------- v5.0 · prévias: caverna escura e destroços no deserto

BAND_LEVELS = (0.18, 0.40, 0.68, 1.0)          # mesmos degraus do game/lighting.py (banding=True)


def _falloff(d):
    if d >= 1.0:
        return 0.0
    if d <= 0.3:
        return 1.0
    k = (d - 0.3) / 0.7
    return 1.0 - k * k * (3 - 2 * k)


def apply_darkness(img: Image.Image, lights, cell=4) -> tuple[Image.Image, np.ndarray]:
    """Escuridão aproximada como a do jogo: mapa de luz em células de 4 px (anéis em 4 degraus), luzes somadas
    e travadas em 255, multiplicado pelo mundo. lights = [(x, y, raio_px, (r, g, b), intensidade)]."""
    W, H = img.size
    sw, sh = (W + cell - 1) // cell, (H + cell - 1) // cell
    lm = np.zeros((sh, sw, 3), float)
    for (x, y, rad, col, inten) in lights:
        rc = max(1, round(rad / cell))
        gx, gy = int(x // cell), int(y // cell)
        for j in range(2 * rc):
            for i in range(2 * rc):
                cx_, cy_ = gx - rc + i, gy - rc + j
                if not (0 <= cx_ < sw and 0 <= cy_ < sh):
                    continue
                b = _falloff(math.hypot(i + 0.5 - rc, j + 0.5 - rc) / rc)
                if b <= 0:
                    continue
                b = BAND_LEVELS[min(3, int(b * 4))] * inten
                lm[cy_, cx_] += np.array(col, float) * b
    lm = np.clip(lm, 0, 255)
    big = np.repeat(np.repeat(lm, cell, 0), cell, 1)[:H, :W]
    a = np.array(img.convert("RGB")).astype(float)
    out = (a * big / 255.0).astype(np.uint8)
    return Image.fromarray(out), big.max(axis=2) / 255.0


CAVE_ORE = {FE: "iron", SI: "silicon", IC: "ice"}
CAVE_RAMP_AT = (5, 4)                           # tile de cima/esquerda da rampa na prévia
CAVE_LAMPS = [(3, 10), (12, 7), (18, 8), (23, 5), (15, 12), (27, 9)]


def gen_cave(seed=11):
    g = [[RK] * GW for _ in range(GH + 1)]

    def carve_ell(cx, cy, rx, ry, s):
        for y in range(GH + 1):
            for x in range(GW):
                n = vnoise(x * 0.5, y * 0.5, s) - 0.5
                if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1 + n * 0.6:
                    g[y][x] = FL
    carve_ell(6.5, 8.5, 5.6, 4.8, seed)                       # salão da rampa
    carve_ell(24, 7.5, 5, 3.8, seed + 1)                      # câmara da direita
    carve_ell(17, 13.5, 3.6, 2.4, seed + 2)                   # câmara de baixo
    for x in range(10, 21):                                   # corredor
        for y in (7, 8) if x % 5 else (6, 7, 8):
            g[y][x] = FL
    for y in range(9, 13):                                    # ramal descendo
        g[y][15] = FL; g[y][16] = FL
    for y in range(GH + 1):
        for x in range(GW):
            if g[y][x] != RK:
                continue
            near = any(0 <= x + dx < GW and 0 <= y + dy <= GH and g[y + dy][x + dx] == FL
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1)))
            if near and vnoise(x * 0.6 + 7, y * 0.6 + 3, seed + 5) > 0.55:
                k = vnoise(x * 0.3 + 50, y * 0.3, seed + 6)
                g[y][x] = FE if k < 0.45 else SI if k < 0.62 else IC
    rx, ry = CAVE_RAMP_AT
    for y in range(ry - 1, ry + 4):                           # salão limpo em volta da rampa
        for x in range(rx - 1, rx + 4):
            g[y][x] = FL
    for (x, y) in CAVE_LAMPS + [(22, 8), (23, 8), (22, 9), (23, 9), (9, 11)]:
        g[y][x] = FL
    return g


def render_cave(spr: dict[str, Image.Image], dark=True, t2=()) -> Image.Image:
    """Caverna (128x128 no jogo) com a mesma ordem de desenho: chão névoa e veio; linhas de cima pra baixo
    (topo da parede em y−24, minério, face em y+8, terminal) e os objetos da linha (rampa, luminárias, baú,
    drill, player). Depois a escuridão (luzes: rampa, luminárias, capacete, drill) e o brilho dos minérios."""
    P = ""
    g = gen_cave()
    img = Image.new("RGBA", (GW * T, GH * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 10), (0, 0, 0, 84))
    shade_b = Image.new("RGBA", (T, 6), (0, 0, 0, 40))
    for y in range(GH):
        for x in range(GW):
            if is_wall(g[y][x]):
                continue
            img.alpha_composite(spr[f"floor_mist_{int(hsh(x, y, 77) * 4)}.png"], (x * T, y * T))
            if y > 0 and is_wall(g[y - 1][x]):
                img.alpha_composite(shade, (x * T, y * T))
                img.alpha_composite(shade_b, (x * T, y * T + 10))
    vein = (22, 8)
    img.alpha_composite(spr["vein_silicon.png"], (vein[0] * T, vein[1] * T))
    term = None
    for y in range(2, GH - 1):
        for x in range(20, 28):
            if term is None and is_wall(g[y][x]) and g[y + 1][x] == FL and y < 6:
                term = (x, y); g[y][x] = RK
    objs = []
    rx, ry = CAVE_RAMP_AT
    objs.append(((ry + 3) * T, rx * T + 48, P + "cave_ramp_up.png"))
    for (x, y) in CAVE_LAMPS:
        objs.append(((y + 1) * T, x * T + 16, "lamp_t2.png" if (x, y) in t2 else P + "lamp.png"))
    objs.append(((10 + 1) * T, 9 * T + 16, "chest.png"))
    objs.append(((vein[1] + 2) * T, (vein[0] + 1) * T, "machine_drill.png#1"))
    player = (rx * T + 48 + 30, (ry + 4) * T + 10)
    objs.append((player[1], player[0], "player"))

    def draw(ay, ax, name):
        if name == "player":
            sh = Canvas(20, 7)
            sh.ellipse(10, 3.5, 8, 2.5, SHADOW)
            img.alpha_composite(sh.image(), (ax - 10, ay - 4))
            img.alpha_composite(spr["player_side.png"], (ax - 16, ay - 32))
            return
        if "#" in name:
            n, fr = name.split("#")
            s_ = spr[n].crop((int(fr) * 64, 0, int(fr) * 64 + 64, 80))
        else:
            s_ = spr[name]
        img.alpha_composite(s_, (int(ax - s_.width // 2), int(ay - s_.height)))

    for y in range(GH + 1):
        for x in range(GW):
            t = g[y][x]
            if not is_wall(t) or y >= GH + 1:
                continue
            img.alpha_composite(spr[f"wall_mist_{int(hsh(x, y, 91) * 3)}.png"], (x * T, y * T - 24))
            if t in CAVE_ORE:
                img.alpha_composite(spr[f"ore_{CAVE_ORE[t]}.png"], (x * T, y * T - 24))
            if y + 1 <= GH and not is_wall(g[y + 1][x]):
                img.alpha_composite(spr["wall_face_mist.png"], (x * T, y * T + 8))
            if term == (x, y):
                img.alpha_composite(spr["terminal.png"], (x * T, y * T))
        for o in sorted(o for o in objs if (o[0] - 1) // T == y):
            draw(*o)
    img = img.crop((0, 0, 960, 540))
    if not dark:
        return img.convert("RGB")
    lights = [(rx * T + CAVE_RAMP["light"][0], ry * T + CAVE_RAMP["light"][1], 3.5 * T, (255, 240, 214), 1.0)]
    lights += [(x * T + 16, y * T + 8, (7 if (x, y) in t2 else 5) * T, (255, 222, 184), 1.0) for (x, y) in CAVE_LAMPS]
    lights.append((player[0] + 10, player[1] - 18, 4 * T, (255, 236, 206), 1.0))
    lights.append(((vein[0] + 1) * T, (vein[1] + 1) * T, 1.8 * T, (150, 210, 230), 0.55))
    out, bright = apply_darkness(img, lights)
    # brilho dos minérios: pontinho na cor do minério onde está escuro (não ilumina nada)
    ore_col = {"iron": (232, 160, 102), "silicon": (195, 209, 226), "ice": (166, 236, 255)}
    a = np.array(out)
    for y in range(GH):
        for x in range(GW):
            if g[y][x] not in CAVE_ORE:
                continue
            h = (x * 73856093 ^ y * 19349663) & 0xFFFF
            if h % 5 >= 2:
                continue
            px_, py_ = x * T + 7 + h % 18, y * T - 24 + 6 + (h >> 5) % 14 + 24
            if not (1 <= px_ < 959 and 1 <= py_ < 539) or bright[py_, px_] > 0.3:
                continue
            c = np.array(ore_col[CAVE_ORE[g[y][x]]])
            a[py_, px_] = c
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                a[py_ + dy, px_ + dx] = (c * 0.35).astype(np.uint8)
    return Image.fromarray(a)


CAVE_LAMPS_T2 = [(12, 7), (23, 5)]              # na prévia v5.1, essas duas viram luminária forte


def render_lamp_cmp(spr: dict[str, Image.Image], left: str, right: str, dark=True) -> Image.Image:
    """Duas metades de caverna (480x480 cada), uma luminária no meio de cada: comum (raio 5) × forte (raio 7).
    Chão e parede da névoa (a da caverna), mesma ordem de desenho e mesma escuridão da prévia da caverna."""
    W_, H_ = 30, 15
    g = [[FL] * W_ for _ in range(H_ + 1)]
    for y in range(H_ + 1):
        for x in range(W_):
            edge = y <= 2 or x in (0, 14, 15, W_ - 1)
            if y == 3 and hsh(x, y, 5) < 0.3:
                edge = True
            if edge:
                g[y][x] = RK
    for (x, y) in ((3, 2), (10, 2), (19, 3), (25, 2), (6, 2), (21, 2), (12, 2), (27, 2)):
        g[y][x] = FE if x % 3 == 0 else SI if x % 3 == 1 else IC
    lamps = [((7, 9), left), ((22, 9), right)]
    img = Image.new("RGBA", (W_ * T, H_ * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 10), (0, 0, 0, 84))
    shade_b = Image.new("RGBA", (T, 6), (0, 0, 0, 40))
    for y in range(H_):
        for x in range(W_):
            if is_wall(g[y][x]):
                continue
            img.alpha_composite(spr[f"floor_mist_{int(hsh(x, y, 77) * 4)}.png"], (x * T, y * T))
            if y > 0 and is_wall(g[y - 1][x]):
                img.alpha_composite(shade, (x * T, y * T))
                img.alpha_composite(shade_b, (x * T, y * T + 10))
    for y in range(H_ + 1):
        for x in range(W_):
            t = g[y][x]
            if not is_wall(t):
                continue
            img.alpha_composite(spr[f"wall_mist_{int(hsh(x, y, 91) * 3)}.png"], (x * T, y * T - 24))
            if t in CAVE_ORE:
                img.alpha_composite(spr[f"ore_{CAVE_ORE[t]}.png"], (x * T, y * T - 24))
            if y + 1 <= H_ and not is_wall(g[y + 1][x]):
                img.alpha_composite(spr["wall_face_mist.png"], (x * T, y * T + 8))
        for (lx, ly), name in lamps:
            if ly == y:
                s_ = spr[name]
                img.alpha_composite(s_, (lx * T + 16 - s_.width // 2, (ly + 1) * T - s_.height))
    img = img.crop((0, 0, 960, 480))
    if not dark:
        return img.convert("RGB")
    lights = [(lx * T + 16, ly * T + 8, (7 if "t2" in name else 5) * T, (255, 222, 184), 1.0)
              for (lx, ly), name in lamps]
    return apply_darkness(img, lights)[0]


def make_icons_slot_v51(spr: dict[str, Image.Image]) -> Image.Image:
    """icon_lamp × icon_lamp_t2 no ui_slot em 1x, 2x e 3x."""
    keys = ["icon_lamp.png", "icon_lamp_t2.png"]
    slot = spr["ui_slot.png"]
    W = 12 + sum(20 * k + 8 for k in (1, 2, 3)) * len(keys) + 12 * len(keys)
    out = Image.new("RGBA", (W, 60 + 24), C("#15100e"))
    x = 12
    for key in keys:
        for k in (1, 2, 3):
            y = 12 + (60 - 20 * k)
            out.alpha_composite(slot.resize((20 * k, 20 * k), Image.NEAREST), (x, y))
            out.alpha_composite(spr[key].resize((16 * k, 16 * k), Image.NEAREST), (x + 2 * k, y + 2 * k))
            x += 20 * k + 8
        x += 12
    return out


WRECK_SCENE = {   # tile de cima/esquerda de cada destroço na prévia e se a caixa já foi aberta
    "wreck_cargo.png": ((2, 2), True),
    "wreck_module.png": ((17, 3), False),
    "wreck_probe.png": ((22, 10), False),
}


def render_wrecks(stage: str, spr: dict[str, Image.Image]) -> Image.Image:
    """Deserto com os 3 destroços e as caixas, mesma ordem de desenho da superfície."""
    P = ""
    hills = {(9, 11), (10, 11), (11, 11), (12, 11), (8, 12), (9, 12), (10, 12), (11, 12), (12, 12), (10, 13), (11, 13)}
    water = set()
    if stage == "mist":
        water = {(13, 14), (14, 14), (14, 15)}
    elif stage == "green":
        water = {(13, 14), (14, 14), (15, 14), (13, 15), (14, 15), (15, 15), (16, 15), (14, 16), (15, 16)}
    img = Image.new("RGBA", (GW * T, GH * T), (0, 0, 0, 255))
    shade = Image.new("RGBA", (T, 10), (0, 0, 0, 84))
    shade_b = Image.new("RGBA", (T, 6), (0, 0, 0, 40))
    for y in range(GH):
        for x in range(GW):
            if (x, y) in hills:
                continue
            img.alpha_composite(spr[sand_key(spr, stage, sand_variant(x + 11, y + 7))], (x * T, y * T))
            if (x, y) in water:
                draw_water_auto(img, spr[f"water_auto_{stage}.png"], water, x, y, x * T, y * T)
            if (x, y - 1) in hills:
                img.alpha_composite(shade, (x * T, y * T))
                img.alpha_composite(shade_b, (x * T, y * T + 10))
    objs = []
    for name, ((tx, ty), opened) in WRECK_SCENE.items():
        tw, th = WRECK_INFO[name]["tiles"]
        objs.append(((ty + th) * T, (tx + tw / 2) * T, P + name))
        cx_, cy_ = WRECK_INFO[name]["crate"]
        objs.append(((ty + cy_ + 1) * T, (tx + cx_) * T + 16, P + ("loot_crate_empty.png" if opened else "loot_crate.png")))
    for (x, y) in ((8, 3), (13, 2), (26, 3), (6, 14), (20, 15), (27, 14), (1, 9)):
        if (x, y) not in water:
            objs.append(((y + 1) * T, x * T + 16, "rock_small.png"))
    for (px_, py_, o) in ((8 * T + 10, 8 * T + 20, "iron"), (14 * T + 20, 6 * T + 12, "silicon"),
                          (25 * T + 6, 7 * T + 22, "ice"), (5 * T + 22, 11 * T + 16, "iron"),
                          (21 * T + 14, 14 * T + 8, "silicon"), (2 * T + 12, 15 * T + 4, "ice")):
        objs.append((py_, px_, f"pickup_{o}.png"))
    if stage == "green":
        for (x, y, k) in ((7, 7, "plant_bush.png"), (12, 9, "plant_flower.png"), (27, 6, "plant_tree.png"),
                          (19, 12, "plant_bush.png"), (4, 12, "plant_flower.png"), (25, 15, "plant_bush.png"),
                          (15, 4, "plant_tree.png")):
            objs.append((y * T + 30, x * T + 16, k))
    objs.append((5 * T + 22, 19 * T + 16, "player"))         # lendo o terminal do módulo
    objs.append((6 * T + 12, 4 * T + 2, "player2"))          # na frente da caixa da nave (vazia)

    def draw(ay, ax, name):
        if name.startswith("player"):
            sh = Canvas(20, 7)
            sh.ellipse(10, 3.5, 8, 2.5, SHADOW)
            img.alpha_composite(sh.image(), (int(ax) - 10, int(ay) - 4))
            p = spr["player_up.png"] if name == "player" else spr["player_side.png"].transpose(Image.FLIP_LEFT_RIGHT)
            img.alpha_composite(p, (int(ax) - 16, int(ay) - 32))
            return
        if name.startswith("pickup_"):
            img.alpha_composite(spr[name], (int(ax) - 8, int(ay) - 14))
            return
        s_ = spr[name]
        img.alpha_composite(s_, (int(ax - s_.width // 2), int(ay - s_.height)))

    for y in range(GH + 1):
        for x in range(GW):
            if (x, y) not in hills:
                continue
            img.alpha_composite(spr[f"wall_{stage}_{int(hsh(x, y, 91) * 3)}.png"], (x * T, y * T - 24))
            if (x, y + 1) not in hills:
                img.alpha_composite(spr[f"wall_face_{stage}.png"], (x * T, y * T + 8))
        for o in sorted(o for o in objs if (o[0] - 1) // T == y):
            draw(*o)
    return img.crop((0, 0, 960, 540)).convert("RGB")


def make_pickup_check(spr: dict[str, Image.Image]) -> Image.Image:
    """Pickups e rocha pequena em 1x (como no jogo) e 2x, sobre as 3 areias."""
    P = ""
    names = ["pickup_iron.png", "pickup_silicon.png", "pickup_ice.png", "rock_small.png"]
    out = Image.new("RGBA", (6 * T, 3 * 2 * T))
    for j, st in enumerate(STAGES):
        band = Image.new("RGBA", (6 * T, 2 * T))
        for y in range(2):
            for x in range(6):
                band.alpha_composite(spr[sand_key(spr, st, sand_variant(x + 3 * j, y))], (x * T, y * T))
        for i, n in enumerate(names):
            im = spr[P + n]
            if n.startswith("pickup"):
                band.alpha_composite(im, (8 + i * 40, 24))
            else:
                band.alpha_composite(im, (4 * T + 2, 16))
        out.alpha_composite(band, (0, j * 2 * T))
    big = out.resize((12 * T, 12 * T), Image.NEAREST)
    res = Image.new("RGBA", (6 * T + 16 + 12 * T, 12 * T), (21, 16, 14, 255))
    res.alpha_composite(out, (0, 0))
    res.alpha_composite(big, (6 * T + 16, 0))
    return res.convert("RGB")


# ---------------------------------------------------------------- report HTML

GROUPS = [
    ("Explorador · parado (baixo, cima, lado)", "char", ["player_down.png", "player_up.png", "player_side.png"]),
    ("Explorador · caminhada (4 quadros, animada ao lado)", "char", ["player_walk_down.png", "player_walk_up.png", "player_walk_side.png"]),
    ("Explorador · idle (4 quadros, animada a ~4 fps ao lado)", "char", ["player_idle_down.png", "player_idle_up.png", "player_idle_side.png"]),
    ("Explorador · minerando (4 quadros, animada a 14 fps ao lado)", "char", ["player_mine_down.png", "player_mine_up.png", "player_mine_side.png"]),
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
    ("Ícone de item do drone (v3.3, ao lado dos outros ícones de item)", "icon", ["icon_drone.png", "icon_drone_station.png", "icon_chest.png", "icon_solar.png", "icon_drill.png"]),
    ("v0.2 · baú, painel e estação", "obj", ["chest.png", "chest_open.png", "solar_panel.png", "drone_station.png"]),
    ("v0.2 · drone (4 quadros, animado a 15 fps ao lado)", "drone", ["drone.png"]),
    ("v0.2 · ícones e slot", "icon", ["icon_chest.png", "icon_solar.png", "icon_drone_station.png", "ui_slot.png"]),
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


def build_v41_report(spr: dict[str, Image.Image]) -> str:
    """Seção v4.1 (pendente): névoa marrom, verde de verdade e autotile de água."""
    if "water_auto_mist.png" not in spr:
        return ""
    blocks = []
    for st, lab in (("mist", "Névoa · terra marrom úmida"), ("green", "Verde · grama de verdade")):
        bef = "".join(f'<img src="before/sand_{st}_{v}_v40.png" width="128" height="128" alt="antes {v}">' for v in range(4))
        aft = "".join(f'<img src="../../assets/sprites/sand_{st}_{v}.png" width="128" height="128" alt="depois {v}">' for v in range(4))
        blocks.append(f'<figure><div class="pair" style="flex-direction:column;align-items:flex-start">'
                      f'<div>antes (v4.0)<span style="display:flex;gap:8px">{bef}</span></div>'
                      f'<div>depois (v4.1)<span style="display:flex;gap:8px">{aft}</span></div></div>'
                      f'<figcaption>{lab} · sand_{st}_0..3 · 4×</figcaption></figure>')
    pv = "".join(
        f'<figure class="pv"><div class="pair" style="display:flex;flex-direction:column;gap:6px">'
        f'<span class="chip" style="align-self:flex-start">antes (v4.0)</span>'
        f'<img src="before/preview_surface_{st}_v40.png" width="960" height="540" alt="antes">'
        f'<span class="chip ok" style="align-self:flex-start">depois (v4.1)</span>'
        f'<img src="preview_surface_{st}.png" width="960" height="540" alt="depois"></div>'
        f'<figcaption><b>{lab}</b></figcaption></figure>'
        for st, lab in (("mist", "Superfície · Névoa"), ("green", "Superfície · Verde")))
    til = "".join(f'<figure class="pv"><img src="sand_tiling_{st}.png" width="960" height="540" alt="ladrilho {st}">'
                  f'<figcaption><b>Ladrilho 30×17 · {lab}</b><span>mesma distribuição sand_variant</span></figcaption></figure>'
                  for st, lab in (("mist", "Névoa"), ("green", "Verde")))
    sheets = "".join(f'<figure class="spr"><div class="chk"><img src="../../assets/sprites/water_auto_{st}.png" '
                     f'width="256" height="384" alt="water_auto_{st}"></div><figcaption><code>water_auto_{st}.png</code>'
                     f'<span>64×96 · 4×</span></figcaption></figure>' for st in ("mist", "green"))
    demos = "".join(f'<figure class="pv"><img src="water_demo_{st}.png" width="640" height="288" alt="poças {st}" style="width:960px;max-width:100%">'
                    f'<figcaption><b>Autotile · {lab}</b><span>poças de 1 tile, poça irregular de 3 tiles e lago com reentrâncias e ilhas, montados pelo algoritmo de minitiles (1,5×)</span></figcaption></figure>'
                    for st, lab in (("mist", "Névoa"), ("green", "Verde")))
    return f"""<section><h2>v4.1 · Névoa marrom e verde de verdade (aprovado)</h2>
<p class="lede" style="margin-bottom:14px">A terraformação agora transforma o deserto. A <b>Névoa</b> é terra marrom úmida, com torrões, manchas de umidade, cascalho escuro e manchinhas de lama, ainda sem vegetação: fica no meio do caminho entre o vermelho e o verde. O <b>Verde</b> é grama cobrindo o chão, na família do <code>floor_green</code> que tu gostou: textura densa de folhinhas, tufos altos, zonas de musgo mais escuro e uma florzinha rara. O Morto não mudou.</p>
<div class="cmp" style="grid-template-columns:1fr">{"".join(blocks)}</div></section>
<section><h2>v4.1 · Prévias antes × depois</h2><div class="pvs">{pv}</div></section>
<section><h2>v4.1 · Teste de ladrilho</h2><div class="pvs">{til}</div></section>
<section><h2>v4.1 · Poças e lagos (autotile de água)</h2>
<div class="cards">{sheets}</div>
<p class="lede" style="margin:14px 0">A borda é orgânica, com uma margem de 2 a 3 px por fora. Na Névoa ela é de lama marrom; no Verde, de terra molhada com grama em volta. A margem de cima faz uma sombra escura na água, e a de baixo e as laterais têm um brilho claro. O interior é o próprio <code>water_{{stage}}</code> aprovado. Fora da margem o PNG é transparente, então o chão novo aparece por baixo.</p>
<div class="pvs">{demos}</div></section>"""


def build_surface_report(spr: dict[str, Image.Image], scale: dict[str, int]) -> str:
    """Seção v4.0 (superfície, aprovada): prévias, teste de ladrilho, sprites ampliados, cratera e cápsula."""
    P = ""

    def card(n, s, anim=False):
        im = spr[n]
        return (f'<figure class="spr"><div class="chk"><img src="../../assets/sprites/{n}" width="{im.width * s}" '
                f'height="{im.height * s}" alt="{n}"></div><figcaption><code>{n.replace(P, "")}</code>'
                f'<span>{im.width}×{im.height} · {s}×</span></figcaption></figure>')

    pv = "".join(
        f'<figure class="pv"><img src="preview_surface_{st}.png" width="960" height="540" alt="Superfície {lab}">'
        f'<figcaption><b>{lab}</b><span>{sub}</span></figcaption></figure>'
        for st, lab, sub in (
            ("dead", "Superfície · 1 · Morto", "areia avermelhada, cápsula nova 64×72, máquinas nv.1, morros, rochas, pickups, veio de ferro, cratera fechada"),
            ("mist", "Superfície · 2 · Névoa", "areia fria úmida, poça, nv.1 + nv.2, estação de drones, drill no veio, cratera fechada"),
            ("green", "Superfície · 3 · Verde", "areia com brotos e tufos, lagos, plantas, <b>pod_wide 96×64 (guardado pro futuro, fora do jogo)</b> e <b>cratera com rampa</b> (Marco 2)"),
        ))
    tiling = "".join(
        f'<figure class="pv"><img src="sand_tiling_{st}.png" width="960" height="540" alt="Areia {st}">'
        f'<figcaption><b>{lab}</b><span>só areia, 30×17 tiles, escolha sugerida (<code>sand_variant</code>)</span></figcaption></figure>'
        for st, lab in (("dead", "Areia · Morto"), ("mist", "Areia · Névoa"), ("green", "Areia · Verde")))
    tiling += ('<figure class="pv"><img src="sand_tiling_dead_uniform.png" width="960" height="540" alt="Areia uniforme">'
               '<figcaption><b>Comparação · sorteio uniforme (25% cada)</b><span>funciona, mas as lajes e as ondulações '
               'aparecem demais e espalhadas por igual: dá pra ver o carimbo</span></figcaption></figure>')
    sand_cards = "".join(card(f"{P}sand_{st}_{v}.png", 4) for st in STAGES for v in range(4))
    obj_cards = "".join(card(P + n, 8 if n.startswith("pickup") else 4) for n in
                        ("rock_small.png", "pickup_iron.png", "pickup_silicon.png", "pickup_ice.png"))
    cr = spr[P + "crater.png"]
    crater_cmp = (f'<figure><div class="pair"><div>fechada (Marco 1)<img src="../../assets/sprites/{P}crater.png" '
                  f'width="{cr.width * 4}" height="{cr.height * 4}" alt="cratera fechada"></div>'
                  f'<div>com rampa (Marco 2)<img src="../../assets/sprites/{P}crater_ramp.png" width="{cr.width * 4}" '
                  f'height="{cr.height * 4}" alt="cratera com rampa"></div></div><figcaption>crater.png × crater_ramp.png · 96×96 · 4×</figcaption></figure>')
    pod_old = REP / "before" / "pod_v33.png"
    pw = spr["_future/pod_wide.png"]
    pod_cmp = (f'<figure><div class="pair">'
               + (f'<div>antes (v3.3)<img src="before/pod_v33.png" width="{64 * 5}" height="{72 * 5}" alt="pod antes"></div>' if pod_old.exists() else "")
               + f'<div>depois · pod.png 64×72<img src="../../assets/sprites/{P}pod.png" width="{64 * 5}" height="{72 * 5}" alt="pod novo"></div>'
               f'<div>guardado pro futuro · _future/pod_wide.png 96×64<img src="../../assets/sprites/_future/pod_wide.png" width="{pw.width * 5}" height="{pw.height * 5}" alt="pod largo"></div>'
               f'</div><figcaption>cápsula · 5×</figcaption></figure>')
    L1, L2 = POD_LIGHTS["pod.png"], POD_LIGHTS["pod_wide.png"]
    dev_rows = [
        ("<code>sand_{stage}_{v}.png</code>", "32×32",
         "Chão, igual ao <code>floor_*</code>: blit em <code>(tx·32, ty·32)</code>, na passada do chão. Nenhum detalhe encosta na borda, então "
         "qualquer variação emenda com qualquer outra e com outro estágio (a mistura de borda da transição continua valendo). "
         "<b>Escolha da variação:</b> não use sorteio uniforme. Sugestão (é a das prévias, copie a lógica de <code>sand_variant</code> do script): "
         "ruído de baixa frequência pra zonas de duna (v2 em ~55% dos tiles da zona) e de laje (v3 rara), e fora delas v0 ~72%, v1 ~20%, v2 ~5%, v3 ~3%."),
        ("<code>rock_small.png</code>", "32×32",
         "Objeto de 1 tile, na ordenação por <code>ay</code>: <code>ax = tx·32 + 16</code>, <code>ay = (ty+1)·32</code>, blit em <code>(tx·32, ty·32)</code>. "
         "A sombra já vem no PNG. O mesmo sprite serve pros 3 estágios."),
        ("<code>pickup_{iron,silicon,ice}.png</code>", "16×16",
         "Ponto de chão = <code>(8, 14)</code> do PNG (centro da sombrinha). Com o pickup em <code>(x, y)</code> no mundo, blit em <code>(x − 8, y − 14)</code>. "
         "Ordene com os objetos por <code>y</code> (o player passa na frente e atrás). A sombrinha já vem no PNG (preto 36%, um nível só)."),
        ("<code>crater.png</code> / <code>crater_ramp.png</code>", "96×96",
         "Ocupa <b>3×3 tiles</b> sem passar da área: blit em <code>(tx·32, ty·32)</code>, com <code>(tx, ty)</code> = tile de cima/esquerda. "
         "É objeto: entra na ordenação com <code>ay = (ty+3)·32</code> (assim a borda de trás cobre os pés de quem está logo acima). "
         "Colisão sugerida: os 9 tiles sólidos. Na rampa, o alvo do E é o tile de baixo do meio <code>(tx+1, ty+2)</code>, onde fica a soleira com faixa de alerta; "
         "o player chega/sai em <code>(tx+1, ty+3)</code>. A cratera é um sprite só pros 3 estágios (rocha roxo-acinzentada, como a rocha pequena)."),
        ("<code>pod.png</code> (novo, aprovado)", "64×72",
         f"Mesmo contrato e mesma âncora de hoje (<code>POD_ANCHOR</code>, centro da base, 2×1 tiles, blit em <code>(ax − 32, ay − 72)</code>). "
         f"<b>Os pontos de luz mudaram</b> (relativos ao canto sup. esquerdo do PNG): janela ciano <code>{L1['window']}</code>, beacon vermelho <code>{L1['beacon']}</code>, "
         f"LED verde <code>{L1['led']}</code>. No <code>render.py</code> o beacon está fixo em <code>(50, 2)</code> e a janela em <code>(20, 29)</code> relativo a "
         "<code>(ax − 32, ay − 70)</code>; troque pelos valores novos (lembrando do −72 em vez de −70)."),
        ("<code>_future/pod_wide.png</code> (guardado)", "96×64",
         f"<b>Não entra no jogo agora</b> (fora do contrato; o jogo não carrega de <code>_future/</code>). Se um dia entrar: colisão sugerida <b>3×1 tiles</b> (a linha de baixo), o teto e a antena sobem pro tile de cima, como no pod atual. "
         f"Âncora no centro da base do tile do meio: <code>ax = (tx+1)·32 + 16</code>, <code>ay = (ty+1)·32</code>, blit em <code>(ax − 48, ay − 64)</code>. "
         f"Luzes: janela <code>{L2['window']}</code>, beacon <code>{L2['beacon']}</code>, LED <code>{L2['led']}</code>, porta (pé) <code>{L2['door']}</code>."),
    ]
    if "water_auto_mist.png" in spr:
        dev_rows.insert(0, ("<code>water_auto_{mist,green}.png</code> (v4.1)", "64×96",
            "Autotile no layout <b>A2 do RPG Maker</b>, com minitiles de 16×16. Os blocos são de 32×32: "
            "<b>(0,0)</b> = poça isolada (gota de 1 tile); <b>(32,0)</b> = os 4 cantos internos; "
            "<b>(0,32)–(64,96)</b> = ilha 2×2 com interior, bordas e cantos externos (grade 4×4 de minitiles: colunas 0/3 = bordas esquerda/direita, "
            "1–2 = meio; linhas 0/3 = bordas de cima/baixo, 1–2 = meio). "
            "<b>Algoritmo</b>, por tile de água, olhando os 8 vizinhos (água = sim): sem nenhum vizinho ortogonal, copie o bloco (0,0) inteiro. "
            "Senão, pra cada quadrante <code>(qx, qy)</code> ∈ {0,1}², com <code>h</code> = vizinho do lado do quadrante (L se qx=0, R se qx=1), "
            "<code>v</code> = vizinho de cima/baixo (U se qy=0, D se qy=1) e <code>diag</code> = o diagonal daquela quina: "
            "se <code>h and v and not diag</code>, a fonte é <code>(32 + 16·qx, 16·qy)</code> (canto interno); "
            "senão, <code>col = (2 if h else 0)</code> se qx=0 ou <code>(1 if h else 3)</code> se qx=1, "
            "<code>row = (2 if v else 0)</code> se qy=0 ou <code>(1 if v else 3)</code> se qy=1, e a fonte é <code>(16·col, 32 + 16·row)</code>. "
            "Copie 16×16 da fonte pra <code>(16·qx, 16·qy)</code> do tile. A fonte sempre cai no mesmo quadrante do destino (paridade), "
            "então a textura da água e as bordas emendam sem costura. Ordem: o chão do tile primeiro, o autotile por cima (fora da margem é transparente). "
            "Fora do mapa conta como terra. O código de referência está em <code>autotile_quads()</code> no script. No Morto não tem água."))
    dev = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in dev_rows)
    order = ("<ol><li><b>Chão:</b> <code>sand_*</code> (e água/poças), depois os veios.</li>"
             "<li><b>Linhas de cima pra baixo:</b> topo dos morros <code>wall_{stage}_N</code> em <code>(x, y − 24)</code>, face <code>wall_face_{stage}</code> "
             "em <code>(x, y + 8)</code> quando embaixo é chão. Depois os objetos cuja âncora cai na linha, ordenados por <code>ay</code>: cratera, rochas, pickups, cápsula, máquinas e player.</li>"
             "<li>Drones voando, partículas e luz por cima de tudo, como hoje.</li></ol>")
    return f"""<section><h2>v4.0 · Superfície · prévias (960×540, tamanho real)</h2><div class="pvs">{pv}</div></section>

<section><h2>Areia · teste de ladrilho numa área grande</h2>
<p class="lede" style="margin-bottom:14px">30×17 tiles só de areia, pra conferir se vira papel de parede. A <b>v0</b> (areia) é quase lisa, só com grão de 1 px e risquinhos de vento. A <b>v1</b> (cascalho) tem um bolo de pedrisco fora do centro. A <b>v2</b> (duna) tem ondulações baixas, que juntas em zonas viram as faixas de duna. A <b>v3</b> (laje) é uma placa de rocha nivelada com o chão, rara. Nada encosta na borda, então não existe costura.</p>
<div class="pvs">{tiling}</div></section>

<section><h2>v4.0 · Areia (32×32, 4×)</h2><div class="cards">{sand_cards}</div></section>

<section><h2>v4.0 · Rocha pequena e recursos soltos</h2><div class="cards">{obj_cards}</div>
<p class="lede" style="margin:14px 0">Legibilidade: à esquerda em 1× (como no jogo), à direita em 2×, sobre as 3 areias.</p>
<img src="pickup_check.png" width="{(6 * T + 16 + 12 * T)}" height="{12 * T}" alt="Pickups sobre as areias" style="image-rendering:pixelated;display:block;max-width:100%;border:1px solid var(--line)">
</section>

<section><h2>Cratera · fechada × com rampa</h2><div class="cmp" style="grid-template-columns:1fr">{crater_cmp}</div></section>

<section><h2>Cápsula · antes × depois × proposta larga</h2><div class="cmp" style="grid-template-columns:1fr">{pod_cmp}</div>
<div class="box" style="margin-top:14px"><h3>O que aproveitei da referência (só o estilo, desenho original)</h3><ul>
<li>A silhueta de <b>módulo baixo e largo, em caixa de cantos chanfrados</b>: teto com os cantos de trás cortados e frente com duas facetas laterais, que dão o perfil quase hexagonal.</li>
<li><b>Painéis creme em placas com junções visíveis</b>, no teto e na frente, no lugar do casco branco liso de antes.</li>
<li>Uma <b>saia escura grossa</b> que abre pra baixo, com painéis recuados e parafusos, e marquinhas do pouso logo acima. Ela dá a sensação de que o módulo assentou e afundou um pouco na areia.</li>
<li><b>Janelinhas retangulares pequenas com luz ciano</b> em fileira, uma <b>escotilha retangular com moldura</b> (aqui laranja, da nossa família) e degrau, uma <b>caixa de equipamento escura</b> com grade e uma <b>aleta</b> no teto, e um <b>toco de asa</b> na lateral.</li>
<li>Da nossa família, mantive o contorno <code>#1b1630</code>, a faixa laranja <code>#e2733a</code>, o LED verde, o beacon vermelho na antena e a visão 3/4 (teto visível + frente). Nenhuma forma, proporção ou detalhe foi copiado da nave de referência.</li>
</ul></div></section>

<section><h2>v4.0 · Pro Dev integrar (superfície)</h2>
<div class="box dev"><table class="tb"><thead><tr><th>Sprite</th><th>Tamanho</th><th>Âncora / uso</th></tr></thead><tbody>{dev}</tbody></table>
<h3>Ordem de desenho na superfície</h3>{order}
<p class="lede">Os morros e a cordilheira usam a parede já aprovada (<code>wall_*</code>, <code>wall_face_*</code>), sem sprite novo. Faltando qualquer PNG, o fallback do jogo continua valendo.</p></div>
</section>"""


def make_icons_slot_v50(spr: dict[str, Image.Image]) -> Image.Image:
    """Ícones novos no ui_slot em 1x, 2x e 3x (como o jogo escala), com 2 ícones aprovados no fim pra comparar."""
    P = ""
    keys = [P + "icon_lamp.png", P + "icon_blueprint.png", P + "icon_o2_tank.png", P + "icon_scanner.png",
            "icon_chest.png", "icon_iron.png"]
    slot = spr["ui_slot.png"]
    W = 12 + sum(20 * k + 8 for k in (1, 2, 3)) * len(keys) + 12 * len(keys)
    out = Image.new("RGBA", (W, 60 + 24), C("#15100e"))
    x = 12
    for key in keys:
        for k in (1, 2, 3):
            y = 12 + (60 - 20 * k)
            out.alpha_composite(slot.resize((20 * k, 20 * k), Image.NEAREST), (x, y))
            out.alpha_composite(spr[key].resize((16 * k, 16 * k), Image.NEAREST), (x + 2 * k, y + 2 * k))
            x += 20 * k + 8
        x += 12
    return out


def build_v50_report(spr: dict[str, Image.Image]) -> str:
    """Seção v5.0 (aprovada): Marco 2 (caverna) e Marco 3 (destroços) do v0.3."""
    P = ""
    if "lamp.png" not in spr:
        return ""

    def card(n, s, src=None):
        im = spr[n]
        src = src or f"../../assets/sprites/{n}"
        return (f'<figure class="spr"><div class="chk"><img src="{src}" width="{im.width * s}" height="{im.height * s}" '
                f'alt="{n}"></div><figcaption><code>{n.replace(P, "")}</code><span>{im.width}×{im.height} · {s}×</span>'
                f'</figcaption></figure>')

    cave_pv = (
        '<figure class="pv"><img src="preview_cave.png" width="960" height="540" alt="Caverna escura">'
        '<figcaption><b>Caverna · com escuridão</b><span>mesmo algoritmo do <code>game/lighting.py</code> (células de 4 px, anéis 100/68/40/18%, '
        'luzes somadas e multiplicadas): boca de luz da rampa, 6 luminárias, lanterna do capacete, luz fraca da drill e o pontinho dos minérios no escuro</span></figcaption></figure>'
        '<figure class="pv"><img src="preview_cave_lit.png" width="960" height="540" alt="Caverna sem escuridão">'
        '<figcaption><b>A mesma cena sem a escuridão</b><span>pra ver a arte (chão, parede e face da névoa, que a caverna usa sempre)</span></figcaption></figure>')
    wr_pv = "".join(
        f'<figure class="pv"><img src="preview_wrecks_{st}.png" width="960" height="540" alt="Destroços {lab}">'
        f'<figcaption><b>Destroços · {lab}</b><span>nave de carga (caixa já aberta, vazia), módulo da colônia (player lendo o terminal, '
        f'caixa cheia na frente da porta) e sonda (caixa cheia ao lado)</span></figcaption></figure>'
        for st, lab in (("dead", "Morto (areia vermelha)"), ("mist", "Névoa (terra marrom)"), ("green", "Verde (grama)")))
    cr = spr["crater_ramp.png"]
    ramp_cmp = (f'<figure><div class="pair"><div>crater_ramp (aprovada, superfície)<img src="../../assets/sprites/crater_ramp.png" '
                f'width="{cr.width * 4}" height="{cr.height * 4}" alt="crater_ramp"></div>'
                f'<div>cave_ramp_up (nova, caverna)<img src="../../assets/sprites/cave_ramp_up.png" width="{cr.width * 4}" '
                f'height="{cr.height * 4}" alt="cave_ramp_up"></div></div><figcaption>descer × subir · 96×96 · 4×</figcaption></figure>')
    m2 = card(P + "lamp.png", 8) + card(P + "icon_lamp.png", 8)
    m3w = card(P + "wreck_cargo.png", 4) + card(P + "wreck_module.png", 4) + card(P + "wreck_probe.png", 4)
    crate_anim = ('<figure class="spr"><div class="chk"><div class="crate-anim" style="width:192px;height:192px"></div></div>'
                  '<figcaption><code>cheia ↔ vazia</code><span>alternando · 6×</span></figcaption></figure>')
    m3c = card(P + "loot_crate.png", 6) + card(P + "loot_crate_empty.png", 6) + crate_anim
    m3i = "".join(card(P + n, 8) for n in ("icon_blueprint.png", "icon_o2_tank.png", "icon_scanner.png"))
    sw, sh_ = Image.open(REP / "slot_preview_v50.png").size if (REP / "slot_preview_v50.png").exists() else (0, 0)
    lb = LAMP_BULB
    rows = [
        ("<code>lamp.png</code>", "16×32",
         "Objeto de 1 tile, como o baú: <code>ax = tx·32 + 16</code>, <code>ay = (ty+1)·32</code>, blit em <code>(ax − 8, ay − 32)</code>, "
         "ordenado por <code>ay</code>. A sombra já vem no PNG. "
         f"<b>Centro da lâmpada</b> = <code>{lb}</code> do PNG, ou seja <code>(ax, ay − {32 - lb[1]})</code> no mundo. O <code>lighting.lamp()</code> "
         "de hoje põe a luz em <code>ty·32 + 8 = ay − 24</code>: fica 2 px abaixo do vidro, dá pra deixar assim ou trocar pra <code>ay − 26</code>. "
         "O sprite já vem aceso (vidro quente); a luz em volta é do jogo."),
        ("<code>icon_lamp.png</code>", "16×16", "Ícone de item (hotbar, inventário, fabricador)."),
        ("<code>cave_ramp_up.png</code>", "96×96",
         "Igual à <code>crater_ramp</code>: ocupa <b>3×3 tiles</b>, blit em <code>(tx·32, ty·32)</code> com <code>(tx, ty)</code> = tile de cima/esquerda, "
         "e entra na ordenação com <code>ay = (ty+3)·32</code>. Os cantos são transparentes: desenhe o chão da caverna embaixo. "
         "Colisão: os 9 tiles. <b>Alvo do E</b>: tile de baixo do meio <code>(tx+1, ty+2)</code>, onde fica a soleira com a faixa de alerta. "
         "<b>Ponto de chegada</b> (quem desce da superfície): <code>(tx+1, ty+3)</code>, logo na frente da soleira. "
         f"<b>Luz sugerida</b>: uma <code>LightSource</code> fixa na boca de luz, em <code>(tx·32 + {CAVE_RAMP['light'][0]}, ty·32 + {CAVE_RAMP['light'][1]})</code>, "
         "raio ~3,5 tiles, cor <code>(255, 240, 214)</code>, intensidade 1, sem flicker. É ela que faz o feixe iluminar a escada e o salão na prévia; "
         "sem ela, a rampa fica no escuro como o resto."),
        ("<code>wreck_cargo.png</code>", "128×112",
         "<b>4×3 tiles</b> <code>(tx..tx+3, ty..ty+2)</code>, centro da base: <code>ax = (tx+2)·32</code>, <code>ay = (ty+3)·32</code>, "
         "blit em <code>(ax − 64, ay − 112)</code> = <code>(tx·32, ty·32 − 16)</code>. Os 16 px de cima (deriva e antena) sobem pro tile de cima. "
         "Colisão: os 12 tiles. <b>Caixa</b>: <code>(tx+1, ty+3)</code>, logo na ponta da rampa de carga (fora da área do destroço, então o player chega nela). "
         "Sem terminal (se um dia tiver, a porta de carga em <code>(tx+1, ty+2)</code> é o lugar)."),
        ("<code>wreck_module.png</code>", "96×88",
         "<b>3×2 tiles</b>, centro da base: <code>ax = tx·32 + 48</code>, <code>ay = (ty+2)·32</code>, blit em <code>(ax − 48, ay − 88)</code> = "
         "<code>(tx·32, ty·32 − 24)</code>. Teto e antena sobem 24 px. Colisão: os 6 tiles. "
         "<b>Terminal</b>: desenhado no PNG em <code>(62, 59)</code>–<code>(80, 75)</code>, que cai no tile <code>(tx+2, ty+1)</code>: é o alvo do E pro LOG "
         "(o player lê de <code>(tx+2, ty+2)</code>). O contorno claro de alvo pode ir só nesse retângulo. <b>Caixa</b>: <code>(tx, ty+2)</code>, na frente da porta."),
        ("<code>wreck_probe.png</code>", "64×64",
         "<b>2×2 tiles</b>, centro da base: <code>ax = (tx+1)·32</code>, <code>ay = (ty+2)·32</code>, blit em <code>(tx·32, ty·32)</code> (não passa da área). "
         "Colisão: os 4 tiles. <b>Caixa</b>: <code>(tx+2, ty+1)</code>, do lado direito. O LED vermelho da sonda fica em <code>(23, 37)</code> do PNG "
         "(se quiser piscar, desenhe 2×1 px apagado <code>#3b3f46</code> por cima)."),
        ("<code>loot_crate.png</code> / <code>loot_crate_empty.png</code>", "32×32",
         "1 tile, centro da base: blit em <code>(tx·32, ty·32)</code>, ordenado por <code>ay = (ty+1)·32</code>. Obstáculo como o baú. "
         "Cheia = tampa fechada com LED âmbar; quando o conteúdo acabar, troque pela vazia (tampa aberta, LED apagado) e a dica vira \"vazia\"."),
        ("<code>icon_blueprint</code> · <code>icon_o2_tank</code> · <code>icon_scanner</code>", "16×16",
         "Ícones de item. O projeto usa o <code>icon_blueprint</code> no aviso \"PROJETO: …\"; o tanque vai no slot de equipamento."),
    ]
    dev = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)
    order = ("<ol><li><b>Caverna:</b> chão (<code>floor_mist_*</code>) e veios; depois linha por linha: topo da parede em <code>(x, y − 24)</code>, minério, "
             "face em <code>(x, y + 8)</code>, terminal; e os objetos da linha por <code>ay</code> (rampa, luminárias, baú, drill, player). "
             "Por cima: <b>escuridão</b> → brilho dos minérios → indicadores e HUD.</li>"
             "<li><b>Superfície:</b> igual à de hoje; destroços e caixas são objetos e entram na ordenação por <code>ay</code> junto com rochas, pickups e máquinas. "
             "A areia acumulada, a sombra e as peças caídas (asa, aleta) já vêm dentro do PNG do destroço.</li></ol>")
    return f"""<section><h2>v5.0 · Caverna · prévias (960×540, tamanho real)</h2><div class="pvs">{cave_pv}</div></section>

<section><h2>v5.0 · Rampa de subida × rampa de descida</h2><div class="cmp" style="grid-template-columns:1fr">{ramp_cmp}</div>
<p class="lede" style="margin-top:14px">Mesma linguagem da cratera: monte de rocha com uma escada de metal cortada nele, corrimão laranja, soleira com faixa de alerta e duas balizas com LED verde. Só que aqui a escada <b>sobe</b>: os degraus clareiam de baixo pra cima até uma <b>boca de luz</b> no fundo, com a rocha em volta esquentada pela luz do dia, raios pontilhados e poeira no feixe. Uma plaquinha com seta verde pra cima reforça o "sai por aqui". A rocha usa os tons frios da parede da névoa, que é a da caverna.</p></section>

<section><h2>v5.0 · Marco 2 · luminária</h2><div class="cards">{m2}</div>
<p class="lede" style="margin-top:14px">Poste baixo da família das máquinas: sapata pesada com faixa laranja <code>#e2733a</code>, poste cinza em faixas, colar escuro e cabeça de gaiola com a lâmpada quente acesa (amarelo claro → laranja, uma barra e um aro de gaiola). Contorno <code>#1b1630</code>.</p></section>

<section><h2>v5.0 · Destroços · prévias (960×540, tamanho real)</h2><div class="pvs">{wr_pv}</div></section>

<section><h2>v5.0 · Marco 3 · destroços</h2><div class="cards">{m3w}</div>
<div class="notes" style="margin-top:14px"><div class="box"><h3>Escolhas</h3><ul>
<li><b>Mesma família:</b> painéis creme (os da cápsula), laranja desbotado em vez do <code>#e2733a</code> vivo, metal escuro das máquinas e contorno <code>#1b1630</code>.</li>
<li><b>Abandono sem drama:</b> placas arrancadas mostrando as costelas, trincas, manchas de fuligem e poeira, vidro quebrado, peças caídas no chão (asa, aleta, painel solar), antenas tortas. Nada de sangue ou corpo.</li>
<li><b>Nave de carga</b> (o primeiro grande achado): fuselagem tubular comprida em 3/4, nariz enfiado num monte de areia, cabine trincada, porta de carga caída virando rampa, asa apoiada no chão, deriva e bocais de motor (um partido), registro "07".</li>
<li><b>Módulo da colônia:</b> caixa habitável inclinada (o lado esquerdo afundou: as faixas descem em degraus de 1 px), porta emperrada, emblema "H" desbotado da Colônia Hesper e o <b>terminal ainda ligado</b>, no estilo do <code>terminal.png</code>.</li>
<li><b>Sonda:</b> pequena e tecnológica, embrulhada em folha dourada amassada (o isolamento das sondas reais), parabólica torta, olho-sensor ciano, LED vermelho ainda aceso e um sulco de impacto.</li>
<li><b>Areia acumulada num tom neutro</b> (cinza-amarronzado, a mesma ideia do pedrisco dos veios): um sprite só funciona nos 3 chãos. No Morto lê como poeira, na Névoa some na terra e no Verde vira terra exposta.</li>
</ul></div></div></section>

<section><h2>v5.0 · Caixa de saque</h2><div class="cards">{m3c}</div>
<p class="lede" style="margin-top:14px">Case de carga pesado, diferente do baú do jogador: corpo cinza-chumbo nervurado, cantoneiras creme, tampa com faixa laranja desbotada e alça, alças laterais e trava com LED âmbar ("tem coisa aqui"). Vazia: tampa aberta pra trás, interior escuro e LED apagado.</p></section>

<section><h2>v5.0 · Ícones de item</h2><div class="cards">{m3i}</div>
<p class="lede" style="margin:14px 0">Projeto = folha de planta azul com o desenho de uma máquina e um chip laranja de contatos dourados. Tanque de O₂ = par de cilindros de mochila com faixa ciano, válvulas laranja e cinta. Scanner = aparelho de mão com tela de minimapa (anéis de radar, ponto do player, alvo), antena e botões. No slot, em 1×, 2× e 3× (os dois últimos são o baú e o ferro aprovados, pra comparar):</p>
<img src="slot_preview_v50.png" width="{sw}" height="{sh_}" alt="Ícones no slot" style="image-rendering:pixelated;display:block;max-width:100%;border:1px solid var(--line)">
</section>

<section><h2>v5.0 · Pro Dev integrar (caverna e destroços)</h2>
<div class="box dev"><table class="tb"><thead><tr><th>Sprite</th><th>Tamanho</th><th>Âncora · colisão · interação</th></tr></thead><tbody>{dev}</tbody></table>
<h3>Ordem de desenho</h3>{order}
<p class="lede">Aprovado pelo dono e promovido pra <code>assets/sprites/</code>: o jogo carrega esses PNGs no lugar do fallback do <code>art.py</code>. <b>Desvios do contrato:</b> nenhum (nomes e tamanhos exatamente como na bíblia §9).</p></div>
</section>"""


def build_v51_report(spr: dict[str, Image.Image]) -> str:
    """Seção v5.1 (aprovada): luminária forte (lamp_t2) + ícone, com a comum do lado."""
    if "lamp_t2.png" not in spr:
        return ""
    A = "../../assets/sprites/"

    def img(n, s, cls=""):
        im = spr[n]
        return (f'<img class="{cls}" src="{A}{n}" width="{im.width * s}" height="{im.height * s}" alt="{n}" '
                f'style="image-rendering:pixelated">')

    def pair(bg, s):
        return (f'<div class="lp {bg}"><div><span>lamp (comum)</span>{img("lamp.png", s)}</div>'
                f'<div><span>lamp_t2 (forte)</span>{img("lamp_t2.png", s)}</div>'
                f'<div><span>icon_lamp</span>{img("icon_lamp.png", s)}</div>'
                f'<div><span>icon_lamp_t2</span>{img("icon_lamp_t2.png", s)}</div></div>')

    def old(n, s):                                                  # histórico estático em reports/design/before/
        return (f'<img src="before/{n}" width="{16 * s}" height="{32 * s}" alt="{n}" style="image-rendering:pixelated">')

    ab = (f'<div class="lp chkbg"><div><span>A · escolhida</span>{img("lamp_t2.png", 4)}</div>'
          f'<div><span>B · cabeça dupla</span>{old("lamp_t2_B_v51.png", 4)}</div>'
          f'<div><span>A · 1×</span>{img("lamp_t2.png", 1)}</div>'
          f'<div><span>B · 1×</span>{old("lamp_t2_B_v51.png", 1)}</div></div>')
    sw, sh_ = Image.open(REP / "slot_preview_v51.png").size if (REP / "slot_preview_v51.png").exists() else (0, 0)
    zw, zh = Image.open(REP / "lamp_t2_dark_zoom.png").size if (REP / "lamp_t2_dark_zoom.png").exists() else (0, 0)
    lb = LAMP2_BULB
    rows = [
        ("<code>lamp_t2.png</code>", "16×32",
         "<b>Drop-in</b>: mesmo tamanho e âncora da <code>lamp.png</code> (<code>C.LAMP_SPRITE_SIZE</code> não muda). Objeto de 1 tile: "
         "<code>ax = tx·32 + 16</code>, <code>ay = (ty+1)·32</code>, blit em <code>(ax − 8, ay − 32)</code>, ordenado por <code>ay</code>. "
         "Base na linha 29 do PNG, sombra já no PNG (um pouco mais larga, 14 px). Pé que bloqueia: o mesmo 12×12 da comum (a sapata tem 12 px). "
         f"<b>Centro do vidro</b> = <code>{lb}</code> do PNG = <code>(ax, ay − {32 - lb[1]})</code> no mundo; o <code>lighting.lamp()</code> põe a luz em "
         "<code>ay − 24</code>, 1 px abaixo do centro: pode deixar como está. Raio 7 e cor <code>LAMP_COLOR</code> iguais ao que já está no código; "
         "a prévia usa exatamente isso."),
        ("<code>icon_lamp_t2.png</code>", "16×16", "Ícone de item (hotbar, inventário, fabricador, aviso de projeto se quiser). Mesmo enquadramento do <code>icon_lamp</code>."),
    ]
    dev = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows)
    return f"""<section><h2>v5.1 · Luminária forte · comum × forte</h2>
<div class="cmp" style="grid-template-columns:1fr">
<figure><figcaption style="margin:0 0 8px">fundo claro · 4×</figcaption>{pair("lightbg", 4)}</figure>
<figure><figcaption style="margin:0 0 8px">xadrez · 4×</figcaption>{pair("chkbg", 4)}</figure>
<figure><figcaption style="margin:0 0 8px">tamanho real · 1× (como no jogo sem zoom)</figcaption>{pair("lightbg", 1)}{pair("darkbg", 1)}</figure>
</div>
<p class="lede" style="margin-top:14px">Mesma linguagem da comum aprovada (sapata pesada com faixa laranja <code>#e2733a</code>, poste cinza em faixas, colar escuro, cabeça de gaiola acesa, contorno <code>#1b1630</code>), só que na versão nv.2, como as máquinas: <b>dourado <code>#f2c46d</code></b> na aba e no aro da cabeça, nos parafusos e num anel do poste. A cabeça cresce de 6×6 pra <b>10×7 de vidro</b> com 3 painéis e uma aba de refletor mais larga que o vidro; o poste vai de 4 pra 6 px; a sapata ganha um <b>pedestal em 2 degraus</b> e 12 px de largura. O vidro é mais <b>branco-quente</b> (núcleo quase branco, laranja só na borda), pra ler como "luz mais forte" mesmo parado.</p></section>

<section><h2>v5.1 · No escuro da caverna (halo simulado)</h2><div class="pvs">
<figure class="pv"><img src="lamp_t2_dark.png" width="960" height="480" alt="comum x forte no escuro"><figcaption><b>Esquerda: comum (raio 5) · direita: forte (raio 7)</b><span>mesma escuridão da prévia da caverna (células de 4 px, anéis 100/68/40/18%, cor <code>LAMP_COLOR</code>). A forte chega na parede e mostra os minérios; a comum não</span></figcaption></figure>
<figure class="pv"><img class="flick" src="lamp_t2_dark_zoom.png" width="{zw * 4}" height="{zh * 4}" alt="zoom no escuro" style="max-width:none;width:{zw * 4}px"><figcaption><b>Zoom 4× nas duas, no escuro</b><span>de relance: cabeça estreita e amarela × cabeça larga, branca e com aba dourada (a tremidinha é CSS, imitando o flicker 0,06 do jogo)</span></figcaption></figure>
<figure class="pv"><img src="lamp_t2_lit.png" width="960" height="480" alt="mesma cena sem escuridão"><figcaption><b>A mesma cena sem a escuridão</b><span>chão e parede da névoa, que é a arte da caverna</span></figcaption></figure>
<figure class="pv"><img src="preview_cave_t2.png" width="960" height="540" alt="caverna com luminárias fortes"><figcaption><b>Prévia da caverna com 2 fortes</b><span>a mesma da v5.0, só que as luminárias em (12, 7) e (23, 5) viraram <code>lamp_t2</code> com raio 7</span></figcaption></figure>
<figure class="pv"><img src="preview_cave_t2_lit.png" width="960" height="540" alt="caverna com luminárias fortes, sem escuridão"><figcaption><b>A mesma, sem escuridão</b><span>pra ver as duas famílias lado a lado na cena</span></figcaption></figure>
</div></section>

<section><h2>v5.1 · Variantes A × B (o dono escolheu a A)</h2>{ab}
<p class="lede" style="margin:14px 0"><b>A (a recomendada, escolhida pelo dono e promovida como <code>lamp_t2.png</code>)</b>: a mesma silhueta da comum, só que mais parruda; reconhece como irmã na hora. <b>B</b>: poste mais alto com cruzeta e duas cabeças de gaiola menores (silhueta em T), mais diferente de longe, mas perde o "é a mesma luminária, só que melhor" e cada vidro fica pequeno (5×5). A B ficou de histórico em <code>reports/design/before/</code> (e no <code>make_lamp_t2("B")</code> do script). A prévia lado a lado no escuro:</p>
<figure class="pv"><img src="before/lamp_t2_AB_dark_v51.png" width="960" height="480" alt="A x B no escuro"><figcaption><b>A (esquerda) × B (direita), as duas com raio 7</b></figcaption></figure></section>

<section><h2>v5.1 · Ícone no slot</h2>
<p class="lede" style="margin:0 0 14px"><code>icon_lamp</code> (aprovado) e <code>icon_lamp_t2</code> no <code>ui_slot</code> em 1×, 2× e 3×: cabeça mais larga, vidro mais branco, aba e aro dourados, poste grosso com anel dourado e sapata mais larga.</p>
<img src="slot_preview_v51.png" width="{sw}" height="{sh_}" alt="Ícones no slot" style="image-rendering:pixelated;display:block;max-width:100%;border:1px solid var(--line)">
</section>

<section><h2>v5.1 · Pro Dev integrar (luminária forte)</h2>
<div class="box dev"><table class="tb"><thead><tr><th>Sprite</th><th>Tamanho</th><th>Âncora / uso</th></tr></thead><tbody>{dev}</tbody></table>
<p class="lede"><b>Aprovado pelo dono e promovido pra <code>assets/sprites/</code></b>: o <code>render.lamp_surface("lamp_t2")</code> e o ícone já procuram <code>lamp_t2</code> e <code>icon_lamp_t2</code>, então o jogo troca o fallback <code>art.lamp_strong</code> pelos PNGs sem mudar código. Ordem de desenho igual à da comum (objeto da linha, por <code>ay</code>; a escuridão por cima). <b>Desvios do contrato:</b> nenhum.</p></div>
</section>"""


# ---------------------------------------------------------------- v6.0: Explorador (aprovado) + broca de mão (3 candidatas)
DRILL_SRC = {"atual": lambda v: REP / "before" / f"drill_{v}_v21.png",
             "experimento": lambda v: REP / "before" / f"drill_{v}_experimento.png",
             "experimento_t2": lambda v: REP / "before" / f"drill_{v}_experimento_t2.png"}


def drill_sheet(spr: dict[str, Image.Image], key: str, view: str) -> Image.Image:
    """Folha da broca pra comparação: A = a oficial (aprovada), B/C = do hand_drill.py, o resto vem de before/."""
    if key == "A":
        return spr[f"drill_{view}.png"]
    if len(key) == 1:
        return from_px(hd.make_drill(key, view)).image().convert("RGBA")
    return Image.open(DRILL_SRC[key](view)).convert("RGBA")


def make_drill_hand_previews(spr: dict[str, Image.Image]) -> None:
    """Folhas 4×(44×44) da broca NA MÃO (player_mine quadro f + broca quadro f no DRILL_GRIP), uma por candidata e vista."""
    for view in ("side", "down", "up"):
        pm = spr[f"player_mine_{view}.png"]
        for key in ("atual", "experimento", "experimento_t2", "A", "B", "C"):
            sheet = drill_sheet(spr, key, view)
            hd.compose(pm, sheet, view).save(REP / f"drill_hand_{key}_{view}.png")


def drill_tip_world(cand: str, direction: str) -> tuple[int, int]:
    """Ponta da broca (quadro 0) relativa aos pés do player (p.x, p.y), no formato do render.drill_tip()."""
    view = "side" if direction in ("left", "right") else direction
    tx, ty = hd.TIP[f"{cand}_{view}"]
    (gx, gy), _ = hd.GRIP[view]
    if direction == "left":
        return (-16 - 4 + (23 - tx), -32 + gy + ty)
    return (-16 + gx + tx, -32 + gy + ty)


def build_v60_report(spr: dict[str, Image.Image]) -> str:
    A = "../../assets/sprites/"
    Z = 6

    def anim(src, fw, fh, z, fps=14, cls="anim"):
        dur = 4 / fps
        return (f'<div class="{cls}" style="width:{fw * z}px;height:{fh * z}px;--end:-{fw * 4 * z}px;animation-duration:{dur:.3f}s;'
                f'background-image:url({src});background-size:{fw * 4 * z}px {fh * z}px"></div>')

    def still(src, w, h, z):
        return f'<img src="{src}" width="{w * z}" height="{h * z}" alt="" style="image-rendering:pixelated;display:block">'

    labels = {"atual": "Antiga do jogo (v2.1)", "experimento": "Sessão experimental · nv.1 (reprovada)", "experimento_t2": "Sessão experimental · nv.2 perfuratriz térmica",
              "A": "A · furadeira de bolso (APROVADA, oficial)", "B": "B · caneta-broca", "C": "C · broca de punho"}
    blurbs = {
        "atual": "a broca que está no jogo hoje, na mão do explorador novo",
        "experimento": "a que o dono achou feia e grande demais",
        "experimento_t2": "a broca nv.2 que a sessão experimental propôs (perfuratriz térmica, ponta incandescente), na mão do explorador.",
        "A": "pistola em L minúscula: carcaça cinza-metal (a mesma tinta das ombreiras), faixa laranja, LED ciano, pega escura com a luva fechada nela e broca cônica de 6 px. A mais \"furadeira\" das três.",
        "B": "ferramenta reta e fina, segurada por cima como uma lanterna: tampa laranja, cabo de metal com anel, nariz branco com LED e broca fina. A silhueta mais leve.",
        "C": "módulo branco preso na própria luva, com cinta laranja: a broca sai direto da mão. A mais compacta das três.",
    }
    def bbox(key, view):                                        # área desenhada (com contorno) no quadro 0
        sheet = drill_sheet(spr, key, view)
        a = np.array(sheet)[:, : sheet.width // 4, 3]
        ys, xs = np.nonzero(a)
        return f"{xs.max() - xs.min() + 1}×{ys.max() - ys.min() + 1}"

    rows = []
    for key in ("A", "B", "C", "experimento", "experimento_t2", "atual"):
        blurbs[key] += (f" <b style=\"color:var(--fg)\">Área desenhada:</b> lado {bbox(key, 'side')}, baixo {bbox(key, 'down')}, "
                        f"cima {bbox(key, 'up')} px.")
        cells = []
        for view in ("side", "down", "up"):
            cells.append(f'<div class="dh"><span>{view}</span><div class="chkbg" style="padding:6px">'
                         f'{anim(f"drill_hand_{key}_{view}.png", 44, 44, Z)}</div>'
                         f'<div class="real">{still(f"drill_hand_{key}_{view}.png", 176, 44, 1)}</div></div>')
        if key == "A":
            sheets = "".join(
                f'<div class="dh"><span>drill_{v}.png</span><div class="chkbg" style="padding:6px">'
                f'{still(f"{A}drill_{v}.png", *spr[f"drill_{v}.png"].size, 4)}</div></div>'
                for v in ("side", "down", "up"))
        else:
            sheets = ""
        op = "" if len(key) == 1 else ' style="opacity:.8"'
        rows.append(f'<div class="box dhrow"{op}><h3>{labels[key]}</h3><p class="lede" style="margin:0 0 12px">{blurbs[key]}</p>'
                    f'<div class="dhgrid">{"".join(cells)}</div>'
                    f'{f"<div class=dhgrid style=margin-top:14px>{sheets}</div>" if sheets else ""}</div>')

    # antes × depois do personagem
    cmp = []
    for v in ("down", "side", "up"):
        cmp.append(f'<figure><div class="pair"><div>antes (v2)<img src="before/player_{v}_v51.png" width="{32 * Z}" height="{32 * Z}" alt=""></div>'
                   f'<div>depois (v6.0)<img src="{A}player_{v}.png" width="{32 * Z}" height="{32 * Z}" alt=""></div></div>'
                   f'<figcaption>player_{v}.png · {Z}×</figcaption></figure>')
    anims = []
    for kind, fps, title in (("walk", 8, "caminhada · 8 fps"), ("idle", 4, "idle · 4 fps"), ("mine", 14, "minerando · 14 fps")):
        cells = "".join(f'<div class="dh"><span>{v}</span><div class="chkbg" style="padding:6px">'
                        f'{anim(f"{A}player_{kind}_{v}.png", 32, 32, Z, fps)}</div></div>' for v in ("down", "side", "up"))
        anims.append(f'<div class="box dhrow"><h3>{title}</h3><div class="dhgrid">{cells}</div></div>')

    tips = "".join(
        f"<tr><td><b>{c}</b> · {hd.NAMES[c]}</td>"
        + "".join(f"<td><code>(p.x {'+' if t[0] >= 0 else '−'} {abs(t[0])}, p.y − {abs(t[1])})</code></td>"
                  for t in (drill_tip_world(c, d) for d in ("right", "left", "down", "up")))
        + "</tr>" for c in "ABC")
    return f"""<section><h2>v6.0 · Broca de mão · 3 candidatas na mão do explorador</h2>
<p class="lede" style="margin-bottom:16px">Cada uma animada na pose <code>player_mine</code> com o mesmo encaixe do <code>DRILL_GRIP</code> do jogo (lado <code>(12, 13)</code> na frente, baixo <code>(13, 16)</code> na frente, cima <code>(20, 4)</code> atrás do player), a 14 fps, ampliada {Z}×. Embaixo de cada célula, a mesma folha em tamanho real (1×). <b style="color:var(--fg)">Todas mantêm o tamanho do quadro</b> (lado 24×16, baixo/cima 16×24), então escolher qualquer uma é só trocar o PNG, sem mexer no <code>DRILL_GRIP</code>.</p>
{"".join(rows)}
</section>

<section><h2>v6.0 · Explorador · antes × depois</h2><div class="cmp">{"".join(cmp)}</div></section>
<section><h2>v6.0 · Explorador · animações</h2>{"".join(anims)}</section>

<section><h2>v6.0 · Pro Dev integrar</h2>
<div class="box dev"><table class="tb"><thead><tr><th>Sprite</th><th>Tamanho</th><th>Uso</th></tr></thead><tbody>
<tr><td><code>player_{{down,up,side}}.png</code></td><td>32×32</td><td>Mesmo contrato e mesma âncora de antes: pés na linha 30, blit em <code>(x − 16, y − 32)</code>, <code>side</code> olha pra direita e o jogo espelha. Drop-in, sem código.</td></tr>
<tr><td><code>player_walk_{{down,up,side}}.png</code></td><td>128×32</td><td>4 quadros, como antes (8–10 fps). Drop-in.</td></tr>
<tr><td><code>player_idle_{{down,up,side}}.png</code> <b>novo</b></td><td>128×32</td><td>Parado: respiração (o corpo desce 1 px nos quadros 2–3), cachecol mexendo, lanterna do capacete piscando no quadro 2. Tocar em loop a <b>~4 fps</b> quando o player está parado e não minera. Se o Dev não quiser animar, o <code>player_{{view}}</code> continua igual ao quadro 0.</td></tr>
<tr><td><code>player_mine_{{down,up,side}}.png</code> <b>novo</b></td><td>128×32</td><td>Enquanto <code>state.mining</code>: braço na pega da broca, com tranco de recuo (lado: x −1 nos quadros 1 e 3, y +1 no 3; baixo/cima: y +1 nos quadros 1 e 3). Tocar a <b>14 fps com o MESMO índice de quadro da broca</b> (<code>int(t · 14) % 4</code>, igual ao <code>DRILL_FPS</code>): as 3 candidatas têm o mesmo tranco embutido, então ficam coladas na mão.</td></tr>
<tr><td><code>_pending/drill_{{side,down,up}}_{{A,B,C}}.png</code></td><td>96×16 · 64×24</td><td>Candidatas da broca. Mesmo formato da atual (4 quadros de 24×16 / 16×24) e <b>mesmo <code>DRILL_GRIP</code></b>: <code>right (12, 13)</code>, <code>left (−4, 13)</code> espelhada, <code>down (13, 16)</code>, <code>up (20, 4)</code> atrás do player. A escolhida vira <code>drill_{{view}}.png</code> sem sufixo.</td></tr>
</tbody></table>
<p class="lede" style="margin-bottom:10px">Única coisa que muda no código: a ponta da broca ficou mais perto do corpo, então as faíscas do <code>render.drill_tip()</code> precisam vir pra cá (quadro 0, relativo aos pés):</p>
<table class="tb"><thead><tr><th>Candidata</th><th>right</th><th>left</th><th>down</th><th>up</th></tr></thead><tbody>{tips}
<tr><td>atual (hoje no código)</td><td><code>(p.x + 20, p.y − 11)</code></td><td><code>(p.x − 20, p.y − 11)</code></td><td><code>(p.x + 5, p.y + 8)</code></td><td><code>(p.x + 12, p.y − 28)</code></td></tr></tbody></table>
<ul><li>A luva da pose de minerar fica embaixo da broca; por isso cada candidata já traz o <b>punho fechado</b> (tinta da luva <code>#3f3a4c</code> + contorno) desenhado na pega. Se o jogo mostrar a broca com outra pose, o punho continua no lugar certo do braço esticado.</li>
<li>Ordem de desenho igual à de hoje: lado e baixo por cima de tudo (depois das paredes), cima antes do player.</li>
<li><b>Desvios do contrato:</b> nenhum de tamanho. A bíblia §6 ganhou as linhas do <code>player_idle_*</code> e do <code>player_mine_*</code> (pedidas pelo gerente).</li></ul></div>
</section>"""


def build_report(spr: dict[str, Image.Image]):
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
        return 0.299 * r + 0.587 * g + 0.114 * b

    pal_sets = [
        ("Tiles · morto", [k for k in spr if "_dead" in k and not k.startswith("sand_")]),
        ("Tiles · névoa", [k for k in spr if "_mist" in k and not k.startswith("sand_")]),
        ("Tiles · verde", [k for k in spr if "_green" in k and not k.startswith("sand_")]),
        ("Minérios, veios e ícones", [k for k in spr if k.startswith(("ore_", "icon_", "vein_"))]),
        ("Astronauta e broca", [k for k in spr if k.startswith(("player", "drill"))]),
        ("Cápsula, máquinas e terminal", [k for k in spr if k.startswith(("pod", "machine", "terminal"))]),
        ("Plantas", [k for k in spr if k.startswith("plant_")]),
        ("v0.2 · baú, painel, estação, drone, ícones e slot", [k for k in build_v02()]),
        ("v0.3 · areia", [k for k in build_v03() if k.startswith("sand_")]),
        ("v0.3 · rocha, pickups, cratera e cápsula",
         [k for k in build_v03() if not k.startswith("sand_")] + ["pod.png"]),
        ("v0.3 · caverna e destroços (v5.0)", [k for k in build_v05()]),
        ("v0.3 · luminária forte (v5.1)", [k for k in build_v51()]),
        ("Pendentes", [k for k in spr if k.startswith("_pending/")]),
    ]
    total = set()
    pal_html = []
    for title, names in pal_sets:
        if not names:
            continue
        cols = colors_of([spr[n] for n in names])
        total.update(cols)
        sw = "".join(
            f'<li><i style="background:{c}"></i><code>{c}</code></li>' for c in sorted(cols, key=lum)
        )
        pal_html.append(f'<div class="pal"><h3>{title} <span>{len(cols)} cores</span></h3><ul>{sw}</ul></div>')

    scale = {"tile": 4, "obj": 4, "icon": 8, "char": 6, "face": 8, "drill": 8, "drone": 8}
    groups_html = []
    for title, kind, names in GROUPS:
        cards = []
        for n in names:
            im = spr[n]
            s = scale[kind]
            extra = ""
            if n.startswith(("player_walk", "player_idle", "player_mine", "drill_", "machine_drill", "drone.png")):
                fw, fh = im.width // 4, im.height
                cls = ("anim fast" if n.startswith(("drill_", "drone", "player_mine")) else
                       "anim slow" if n.startswith("player_idle") else "anim")
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

    cmp_items = []
    for n in ["ore_iron", "ore_silicon", "ore_ice", "icon_iron", "icon_silicon", "icon_ice", "vein_iron", "vein_silicon", "vein_ice"]:
        im = spr[n + ".png"]
        sc = 8 if n.startswith("icon") else 4 if n.startswith("ore") else 3
        w, h = im.width * sc, im.height * sc
        before = (REP / "before" / (n + ".png")).exists()
        b_html = (f'<div>antes<img src="before/{n}.png" width="{w}" height="{h}" alt="{n} antes"></div>' if before else "")
        cmp_items.append(f'<figure><div class="pair">{b_html}<div>depois<img src="../../assets/sprites/{n}.png" width="{w}" height="{h}" alt="{n} depois"></div></div><figcaption>{n}.png · {sc}×</figcaption></figure>')
    cmp_html = "".join(cmp_items)
    chest_items = []
    for n in ("chest", "chest_open", "icon_chest"):
        im = spr[f"{n}.png"]
        sc = 8 if n.startswith("icon") else 5
        w, h = im.width * sc, im.height * sc
        b_html = (f'<div>antes<img src="before/{n}_v30.png" width="{w}" height="{h}" alt="{n} antes"></div>'
                  if (REP / "before" / f"{n}_v30.png").exists() else "")
        chest_items.append(f'<figure><div class="pair">{b_html}<div>depois<img src="../../assets/sprites/{n}.png" width="{w}" height="{h}" alt="{n} depois"></div></div><figcaption>{n}.png · {sc}×</figcaption></figure>')
    chest_cmp = "".join(chest_items)
    slot_w, slot_h = Image.open(REP / "slot_preview.png").size if (REP / "slot_preview.png").exists() else (0, 0)
    n_pending = sum(1 for k in spr if k.startswith("_pending/") and "/candidates/" not in k)
    n_official = sum(1 for k in spr if "/" not in k)

    notes = [
        ("Tiles sem costura",
         "Chão e água usam ruído periódico de 32 px. Os pontos da borda são iguais em todas as variações do mesmo estágio, então qualquer variação encosta em qualquer outra sem emenda. As pedras da parede ficam dentro do tile (1 px de folga) sobre um fundo granulado que também emenda."),
        ("Paredes altas (v2.1)",
         "A face de 32×24 agora é feita de blocos de rocha irregulares e achatados, em três ou quatro estratos horizontais quebrados, com fissuras diagonais. Cada bloco tem luz no topo e uma junta escura embaixo, e o tom escurece em faixas até o pé, usando as mesmas cores do topo da rocha do estágio. Não existe junta vertical regular, que era o que fazia parecer tábua de cerca. No verde, o musgo na borda e os cipós continuam. Com o topo elevado (y−24), o maciço fica com 56 px de altura visível."),
        ("Minério",
         "Cada minério tem uma silhueta própria, além da cor: ferro em pepitas gordas, silício em lascas grossas, gelo em cubos. Dá pra distinguir até em tela pequena ou pra quem tem daltonismo. O contorno #1b1630 é o mesmo do astronauta, da broca e da drill, então o minério conversa com eles. Numa parede com face, o overlay de 32×32 cai por cima da faixa de topo e da face, então os cristais aparecem brotando do paredão."),
        ("Explorador (v6.0)",
         "Rig de peças desenhadas à mão, cada uma numa camada com contorno #1b1630 próprio (a da frente separa a de trás). Capacete em domo com visor dourado refletivo em faixa (reflexo duro na diagonal, sem 'olhão'), lanterna presa na lateral e antena com ponta vermelha. Traje branco quente em 4 faixas, ombreiras e joelheiras de metal cinza-lilás, cinto com bolsa, painel no peito com LED ciano, botas escuras com poeira vermelha, mochila com 2 tanques e um cachecol cor de ferrugem que balança. Acento laranja #e2733a, o mesmo das máquinas. Caminhada a 8–10 fps, idle a ~4 fps, minerando a 14 fps."),
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

    surf_html = build_v60_report(spr) + build_v51_report(spr) + build_v50_report(spr) + build_v41_report(spr) + build_surface_report(spr, scale)

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
.anim.slow{{animation-duration:1s}}
.dhrow{{margin-top:14px}}
.dhgrid{{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-start}}
.dh{{display:flex;flex-direction:column;gap:6px;font:11px var(--f-label);color:var(--muted)}}
.dh .real{{background:#2a211d;padding:4px;width:max-content}}
.cmp{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}}
.cmp figure{{margin:0;background:var(--panel);border:1px solid var(--line);padding:10px}}
.cmp .pair{{display:flex;gap:12px;align-items:flex-end}}
.cmp .pair div{{display:flex;flex-direction:column;gap:4px;font:11px var(--f-label);color:var(--muted)}}
.cmp img{{image-rendering:pixelated;display:block;background-color:#2a211d;background-image:conic-gradient(#3a2e28 25%,transparent 0 50%,#3a2e28 0 75%,transparent 0);background-size:16px 16px}}
.cmp figcaption{{font:12px var(--f-mono);margin-top:8px}}
.tb{{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:12px}}
.tb th,.tb td{{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line)}}
.tb th{{font:11px var(--f-label);color:var(--muted)}}
.lp{{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end;padding:14px;border:1px solid var(--line)}}
.lp div{{display:flex;flex-direction:column;gap:6px;font:11px var(--f-label);color:var(--muted)}}
.lp img{{image-rendering:pixelated;display:block}}
.lightbg{{background:#d9d3c9}}.lightbg span{{color:#4a3f38}}
.darkbg{{background:#0b0a0c}}
.chkbg{{background-color:#2a211d;background-image:conic-gradient(#3a2e28 25%,transparent 0 50%,#3a2e28 0 75%,transparent 0);background-size:16px 16px}}
.flick{{animation:flick 1.6s steps(1) infinite}}
@keyframes flick{{0%{{filter:brightness(1)}}37%{{filter:brightness(.94)}}41%{{filter:brightness(1)}}78%{{filter:brightness(.97)}}82%{{filter:brightness(1)}}}}
.crate-anim{{image-rendering:pixelated;background:url(../../assets/sprites/loot_crate.png) 0 0/192px 192px;animation:crate 2.4s steps(1) infinite;outline:1px dashed var(--gold);outline-offset:2px}}
@keyframes crate{{0%{{background-image:url(../../assets/sprites/loot_crate.png)}}50%{{background-image:url(../../assets/sprites/loot_crate_empty.png)}}}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="eyebrow">Hesper · Designer · v6.0 (explorador aprovado · broca de mão: 3 candidatas)</div>
  <h1>Sprites do MVP</h1>
  <p class="lede" style="margin-top:12px"><a href="galeria/index.html" style="color:#59d0e6"><b>Galeria completa</b></a> · todos os PNGs num HTML só, com base64, pra mandar de referência de estilo (gerada por <code>tools/sprites/build_gallery.py</code>).</p>
  <p class="lede">Todos os sprites do contrato (bíblia §6) em pixel art 1:1, gerados por <code>tools/sprites/build_sprites.py</code>. Primeiro as três cenas de prévia, montadas só com esses PNGs como o jogo vai montar; embaixo cada sprite ampliado, a paleta e as decisões. Nada disso entra no jogo antes da tua aprovação.</p>
  <div class="status"><span class="chip ok">{n_official} oficiais + {n_pending} pendentes · tamanhos conferidos</span><span class="chip">{len(total)} cores no total</span><span class="chip ok">0 desvios do contrato</span><span class="chip">pod largo guardado em _future/ (fora do contrato)</span><span class="chip">variante B de histórico em before/</span><span class="chip">broca de mão: candidatas A · B · C em _pending/</span></div>
  <div class="v2" style="border-left-color:#59d0e6"><b>Reports à parte (v0.5)</b><ul>
    <li><b><a href="v05_m3_porta/index.html" style="color:#59d0e6">v0.5 M3 · Porta da base redesenhada</a></b> · v2.0 · <b>pra aprovar</b>: a porta de baixo sobe até o topo da parede (fachada alta), batente escuro com rebites, caixa do mecanismo com luz (verde aberta), folha bege com contorno laranja, faixas de alerta, janelinha ciano e soleira com grade. Mesmo tamanho e âncora.</li>
    <li><b><a href="v05_m3_chao_base/index.html" style="color:#59d0e6">v0.5 M3 · Chão da base refeito</a></b> · v1.0 · <b>pra aprovar</b>: um chão só e sutil (as 4 variações viraram a mesma chapa, só muda um desgaste de 1 tom), aço cinza-azulado da referência, junta fina e pino em losango no cruzamento; ícone refeito. Mesmos nomes e tamanhos.</li>
    <li><b><a href="v05_m3_gelo/index.html" style="color:#59d0e6">v0.5 M3 · Faixa gelada</a></b> · v1.0 · <b>pra aprovar</b>: chão azul-neve sem rachadura, decalques de neve, minério de gelo lapidado (mesma silhueta) e rochas com capa de neve.</li>
    <li><b><a href="v05_m2_base/index.html" style="color:#59d0e6">v0.5 M2 · Base respirável</a></b> · v1.2 · chão, parede, Dispersor, vazamento e ícones <b>aprovados</b>; <b>porta refeita: solo e dupla, vão largo (variante B)</b>.</li>
    <li><a href="v05_m1_construtor/index.html" style="color:#59d0e6">v0.5 M1 · Construtor, mochila e luz de scanner</a> · <a href="v05_bancada_itens/index.html" style="color:#59d0e6">v0.5 · Bancada T2 e itens novos</a> · <a href="maquinas_r3d/index.html" style="color:#59d0e6">Máquinas r3d</a> · <a href="bau_r3d/index.html" style="color:#59d0e6">Baú r3d</a></li>
  </ul></div>
  <div class="v2"><b>v6.0 · o que mudou</b><ul>
    <li><b>Personagem novo: o Explorador, com visor dourado</b> (aprovado pelo dono direto com o gerente). Saiu da sessão experimental e agora é gerado aqui, por <code>tools/sprites/explorer.py</code>, chamado pelo <code>build_sprites.py</code>, sem depender de nada fora do repo. Os PNGs saem idênticos aos do experimento (pixel a pixel).</li>
    <li>Trocados no contrato, mesmos tamanhos e âncora: <code>player_{{down,up,side}}</code> (32×32) e <code>player_walk_*</code> (128×32). <b>Novos</b>: <code>player_idle_*</code> e <code>player_mine_*</code> (128×32, 4 quadros cada). O astronauta chibi antigo ficou em <code>reports/design/before/</code>.</li>
    <li><b>Broca de mão: 3 candidatas (A, B, C) em <code>assets/sprites/_pending/</code></b>, bem menores que a do experimento (reprovada: "feia e muito grande") e que a atual. Mesmo tamanho de quadro e mesmo <code>DRILL_GRIP</code>: qualquer uma entra sem mexer no encaixe. Veja cada uma animada na mão do explorador logo abaixo, com a atual e a do experimento do lado.</li>
    <li>O resto do lote experimental (chão, parede, máquinas, cápsula etc.) <b>não</b> entrou. Todos os outros sprites oficiais continuam com os mesmos pixels. As prévias de cena mudaram só porque o player é o novo.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v5.1 · aprovado</b><ul>
    <li><b>O dono aprovou a v5.1 com a variante A</b> (a recomendada), e os 2 sprites foram promovidos de <code>_pending/</code> pra pasta oficial <code>assets/sprites/</code> com os mesmos bytes da entrega pendente (md5 conferido): <code>lamp_t2</code> (16×32) e <code>icon_lamp_t2</code> (16×16). O jogo agora carrega eles no lugar do fallback <code>art.lamp_strong</code>, sem mudar código.</li>
    <li>O contrato oficial passou a ter 101 arquivos (99 + 2). Os outros 99 oficiais e o <code>_future/pod_wide</code> não mudaram (md5 conferido), e a pasta <code>_pending/</code> foi removida, com as candidatas junto.</li>
    <li>A variante B (cabeça dupla em T) não foi pro jogo: ficou de histórico em <code>reports/design/before/lamp_t2_B_v51.png</code>, com a comparação A × B no escuro (<code>before/lamp_t2_AB_dark_v51.png</code>). O desenho dela continua no script (<code>make_lamp_t2("B")</code>).</li>
    <li>Âncora, centro do vidro e raio continuam em "v5.1 · Pro Dev integrar (luminária forte)", logo abaixo.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v5.0 · aprovado</b><ul>
    <li><b>O dono aprovou a v5.0 inteira</b>, e os 11 sprites foram promovidos de <code>_pending/</code> pra pasta oficial <code>assets/sprites/</code> com os mesmos bytes da entrega pendente (md5 conferido). O jogo agora carrega eles no lugar do fallback do <code>art.py</code>:
      <ul>
        <li><b>Marco 2 · caverna:</b> <code>lamp</code> (16×32), <code>icon_lamp</code> (16×16) e <code>cave_ramp_up</code> (96×96);</li>
        <li><b>Marco 3 · destroços:</b> <code>wreck_cargo</code> (128×112), <code>wreck_module</code> (96×88), <code>wreck_probe</code> (64×64), <code>loot_crate</code> e <code>loot_crate_empty</code> (32×32), <code>icon_blueprint</code>, <code>icon_o2_tank</code> e <code>icon_scanner</code> (16×16).</li>
      </ul></li>
    <li>O contrato oficial passou a ter 99 arquivos (88 + 11). Os outros 88 oficiais e o <code>_future/pod_wide</code> não mudaram (md5 conferido), e a pasta <code>_pending/</code> foi removida.</li>
    <li>A luminária forte (<code>lamp_t2</code>, <code>icon_lamp_t2</code>) ficou pra v5.1, aprovada depois.</li>
    <li>Âncoras, colisão, caixa, terminal, chegada da rampa e a luz sugerida da rampa continuam em "v5.0 · Pro Dev integrar".</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v4.1 · aprovado</b><ul>
    <li><b>O dono aprovou</b>, e os sprites foram promovidos pra <code>assets/sprites/</code> com os mesmos bytes da entrega pendente (md5 conferido):
      <ul>
        <li><code>sand_mist_{{0..3}}</code>: terra marrom úmida, substitui a areia cinza;</li>
        <li><code>sand_green_{{0..3}}</code>: grama cobrindo o chão, substitui a areia bege com brotos;</li>
        <li><code>water_auto_mist</code> e <code>water_auto_green</code> (64×96): autotile de água no layout A2, arquivos novos no contrato.</li>
      </ul>
      As versões v4.0 de <code>sand_mist</code> e <code>sand_green</code> estão em <code>reports/design/before/</code>.</li>
    <li>O contrato oficial passou a ter 88 arquivos (86 + 2 autotiles). Os outros 78 oficiais e o <code>_future/pod_wide</code> não mudaram, e a pasta <code>_pending/</code> foi removida.</li>
    <li>O algoritmo do autotile está em "Pro Dev integrar".</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v4.0 · aprovado (pod largo guardado pro futuro)</b><ul>
    <li><b>O dono aprovou a arte do Marco 1 do v0.3</b>, e ela foi promovida pra pasta oficial <code>assets/sprites/</code> com os mesmos bytes da entrega pendente (md5 conferido):
      <ul>
        <li><code>sand_{{dead,mist,green}}_{{0..3}}</code>: chão do deserto (areia, cascalho, ondulação de duna e laje de rocha);</li>
        <li><code>rock_small</code>: rocha quebrável de 1 tile;</li>
        <li><code>pickup_iron</code>, <code>pickup_silicon</code> e <code>pickup_ice</code>: recursos soltos de 16×16;</li>
        <li><code>crater</code> e <code>crater_ramp</code>: cratera 3×3, fechada e com rampa.</li>
      </ul></li>
    <li><b>Cápsula nova aprovada no tamanho atual:</b> o novo <code>pod.png</code> (64×72, módulo de fuga pousado) substitui o antigo, que ficou guardado em <code>reports/design/before/pod_v33.png</code>. Contrato e âncora não mudaram, mas os pontos de luz mudaram (veja "Pro Dev integrar").</li>
    <li><b>Pod largo guardado pro futuro:</b> <code>assets/sprites/_future/pod_wide.png</code> (96×64). Fica fora do contrato, e o jogo não carrega dessa pasta. Ele aparece só na prévia da superfície Verde, como referência.</li>
    <li>O contrato oficial passou a ter 86 arquivos (68 + 18). Os outros 67 oficiais não mudaram (md5 conferido), e a pasta <code>_pending/</code> foi removida. Como o pod mudou, as prévias da caverna também foram regeradas com a cápsula nova.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v3.3 · aprovado: ícone de item do drone</b><ul>
    <li><b>Novo:</b> <code>assets/sprites/icon_drone.png</code> (16×16). Agora o drone é um item que se fabrica e se coloca na estação, então ganhou ícone próprio. O dono aprovou, e ele foi promovido pra pasta oficial com os mesmos bytes (md5 conferido). O contrato oficial passou a ter 68 arquivos.</li>
    <li><b>Visual:</b> é o mesmo drone do <code>drone.png</code>, parado: corpo branco com faixa laranja, visor ciano e LED verde, 4 braços com hélices paradas e pezinhos de pouso. Tem contorno <code>#1b1630</code> e segue a família dos outros ícones de item.</li>
    <li><b>Onde ver:</b> ampliado ao lado dos outros ícones de item, logo abaixo das prévias, e dentro do <code>ui_slot</code> em 1×, 2× e 3× (o tamanho em que o jogo desenha).</li>
    <li>Os outros 67 sprites oficiais não mudaram (md5 conferido). A pasta <code>_pending/</code> foi removida.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v3.2 · sprites do v0.2 aprovados</b><ul>
    <li>O dono aprovou os 9 sprites do v0.2, e eles foram promovidos pra pasta oficial <code>assets/sprites/</code>:
      <ul>
        <li><code>chest</code> e <code>chest_open</code>;</li>
        <li><code>solar_panel</code>;</li>
        <li><code>drone_station</code> e <code>drone</code>;</li>
        <li><code>icon_chest</code>, <code>icon_solar</code> e <code>icon_drone_station</code>;</li>
        <li><code>ui_slot</code>.</li>
      </ul>
      Os bytes são os mesmos da v3.1 (md5 conferido).</li>
    <li>O contrato oficial agora tem 67 arquivos (58 + 9). A pasta <code>_pending/</code> foi removida; o script volta a criá-la só quando houver algo novo pra aprovar.</li>
    <li>As âncoras e os pontos de pouso estão na tabela "v0.2 · pro Dev" e não mudaram.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v3.1 (v0.2) · baú refeito</b><ul>
    <li><b>Novo baú:</b> <code>chest</code>, <code>chest_open</code> e <code>icon_chest</code> agora são um container de carga industrial: bloco de metal robusto, um pouco mais alto que largo.
      <ul>
        <li>Fechado: topo com nervuras e engates de empilhar, cantoneiras reforçadas com rebites e pés. A frente inteira é uma porta corrugada de duas folhas, com faixa laranja tipo stencil, duas barras de trava com alavanca e LED verde.</li>
        <li>Aberto: a folha gira pra esquerda e aparece o interior escuro com 2 prateleiras, pepitas v2.3 e uma caixinha. O LED fica ciano.</li>
      </ul></li>
    <li>Tamanho e âncora não mudaram: 32×40, blit em <code>(tx·32, (ty+1)·32 − 40)</code>. Os outros pendentes e os 58 oficiais também não mudaram.</li>
    <li>O antes × depois do baú está logo abaixo das prévias.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v3.0 (v0.2) · sprites novos, aguardando aprovação</b><ul>
    <li><b>Assets novos</b> em <code>assets/sprites/_pending/</code>, que o jogo ainda não usa:
      <ul>
        <li>baú fechado e aberto (<code>chest</code>, <code>chest_open</code>);</li>
        <li><code>solar_panel</code>;</li>
        <li><code>drone_station</code>, com 2 pads de pouso;</li>
        <li><code>drone</code>, com 4 quadros de hélice girando;</li>
        <li>os ícones <code>icon_chest</code>, <code>icon_solar</code> e <code>icon_drone_station</code>;</li>
        <li>e <code>ui_slot</code>.</li>
      </ul>
      Tudo segue a família das máquinas: branco/cinza em faixas, laranja, LED e contorno escuro. Os ícones seguem o estilo v2.3.</li>
    <li><b>Os 58 sprites oficiais não mudaram</b> (md5 conferido).</li>
    <li><b>Prévias:</b> todas ganharam o baú (aberto no Verde) e 3 painéis solares. Na Névoa e no Verde aparecem também:
      <ul>
        <li>a estação de drones com 1 drone pousado;</li>
        <li>1 drone voando por cima de uma parede, com a sombra caindo no chão;</li>
        <li>1 drone chegando sobre o chão.</li>
      </ul>
      A estação não aparece no Morto porque só libera na Névoa.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v2.3</b><ul>
    <li><b>Minérios num estilo novo, mais amigável:</b> peças chunky e arredondadas, sem cristal fino nem spike. Cores chapadas e saturadas em 2–3 faixas, um brilho claro e contorno <code>#1b1630</code> (o mesmo do astronauta e da broca), com 2 px na base pra parecer encrustado. As formas diferem por minério: ferro em pepitas gordas cor de cobre, silício em lascas grossas de topo rombudo, gelo em cubos.</li>
    <li><b>Arquivos refeitos:</b> <code>ore_*</code> (overlay da parede) e <code>icon_*</code> (agora como item coletado, com o silício num toco de rocha escura).</li>
    <li><b>Veios refeitos</b> como placas achatadas encravadas no chão, quase niveladas com o solo. As placas são angulosas, de tamanhos variados, com contorno escuro, 2 px de espessura embaixo, bisel claro e fraturas finas. Pepitas pequenas contornadas ficam por cima e em volta. Ferro tem placas rugosas, silício tem lascas sobrepostas e gelo tem placas lisas de aresta reta. A mancha de terra ficou mais sutil (preto 19%).</li>
    <li>Tamanhos e nomes não mudaram. O antes × depois está logo abaixo das prévias.</li>
  </ul></div>
  <div class="v2" style="opacity:.75"><b>v2.2</b><ul>
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

{surf_html}

<section><h2>Prévia das cenas da caverna (960×540, tamanho real · aprovadas, sem mudança)</h2><div class="pvs">{previews}</div></section>

<section><h2>Ícone do drone no slot do inventário</h2>
<p class="lede" style="margin-bottom:14px">Imagem em tamanho real (1 pixel da imagem = 1 pixel da tela): <code>ui_slot</code> com o ícone em 1×, 2× e 3×, do jeito que o jogo escala os dois juntos. À direita, o <code>icon_chest</code> aprovado na mesma escala, pra comparar.</p>
<img src="slot_preview.png" width="{slot_w}" height="{slot_h}" alt="Ícone do drone no slot em 1×, 2× e 3×" style="image-rendering:pixelated;display:block;max-width:100%;border:1px solid var(--line)">
<p class="lede" style="margin-top:10px">A mesma imagem ampliada 3×, pra conferir os pixels:</p>
<img src="slot_preview.png" width="{slot_w * 3}" height="{slot_h * 3}" alt="Prévia do slot ampliada 3×" style="image-rendering:pixelated;display:block;max-width:100%;border:1px solid var(--line)">
</section>

<section><h2>Baú · antes (v3.0) × depois (v3.1)</h2><div class="cmp">{chest_cmp}</div></section>

<section><h2>Minérios · antes (v2.2) × depois (v2.3)</h2><div class="cmp">{cmp_html}</div></section>

{"".join(groups_html)}

<section><h2>v0.2 · pro Dev</h2>
<div class="box dev"><table class="tb"><thead><tr><th>Sprite</th><th>Tamanho</th><th>Âncora / uso</th></tr></thead><tbody>
<tr><td><code>chest.png</code> / <code>chest_open.png</code></td><td>32×40</td><td>Centro da base do tile: blit em <code>(tx·32 + 16 − 16, (ty+1)·32 − 40)</code>. Os 8 px de cima sobem pro tile de cima. Sombra no rodapé.</td></tr>
<tr><td><code>solar_panel.png</code></td><td>32×40</td><td>Igual ao baú (1 tile, centro da base). Sombra no rodapé.</td></tr>
<tr><td><code>drone_station.png</code></td><td>64×72</td><td>2×2, centro da base dos 2×2: <code>ax = (tx+1)·32</code>, <code>ay = (ty+2)·32</code>, blit em <code>(ax − 32, ay − 72)</code>. A torre de antena sobe 8 px pro tile de cima.</td></tr>
<tr><td>Pontos de pouso</td><td>2</td><td>Relativos ao canto sup. esquerdo do PNG da estação: <b>pad 1 = {STATION_PADS[0]}</b>, <b>pad 2 = {STATION_PADS[1]}</b>. É o centro do drone pousado: blit do quadro do drone em <code>(sx + px − 8, sy + py − 10)</code> (2 px acima do pad, parece pousado sobre os pés). Desenhar logo depois da estação.</td></tr>
<tr><td><code>drone.png</code></td><td>64×16</td><td>4 quadros de 16×16, recorte <code>(16·f, 0, 16, 16)</code>, ~15 fps sempre (pousado pode ficar no quadro 0). Sem sombra no PNG: o jogo desenha uma elipse ~12×5 (preto 36%) no chão, uns 18 px abaixo do centro do drone (altitude). Voando, o drone vai por cima de tudo (depois de paredes e objetos).</td></tr>
<tr><td><code>ui_slot.png</code></td><td>20×20</td><td>Moldura de slot, opaca, com os cantos vazados. O ícone 16×16 entra em <code>(2, 2)</code>.</td></tr>
</tbody></table></div>
</section>

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
    pend = build_pending()
    if pend:
        PENDING.mkdir(parents=True, exist_ok=True)
    for name, cv in pend.items():
        cv.image().save(PENDING / name)
    spr = {n: Image.open(OUT / n).convert("RGBA") for n in canv}
    spr.update({f"_pending/{n}": Image.open(PENDING / n).convert("RGBA") for n in pend})
    cand = build_candidates()
    if cand:
        (PENDING / "candidates").mkdir(parents=True, exist_ok=True)
    for name, cv in cand.items():
        cv.image().save(PENDING / "candidates" / name)
    spr.update({f"_pending/candidates/{n}": Image.open(PENDING / "candidates" / n).convert("RGBA") for n in cand})
    fut = build_future()
    FUTURE.mkdir(parents=True, exist_ok=True)
    for name, cv in fut.items():
        cv.image().save(FUTURE / name)
    spr.update({f"_future/{n}": Image.open(FUTURE / n).convert("RGBA") for n in fut})
    for st in STAGES:
        render_scene(st, spr).save(REP / f"preview_{st}.png")
    if True:
        for st in STAGES:
            render_surface(st, spr).save(REP / f"preview_surface_{st}.png")
            render_sand_field(st, spr).save(REP / f"sand_tiling_{st}.png")
        render_sand_field("dead", spr, uniform=True).save(REP / "sand_tiling_dead_uniform.png")
        make_pickup_check(spr).save(REP / "pickup_check.png")
        for st in ("mist", "green"):
            if f"water_auto_{st}.png" in spr:
                make_water_demo(st, spr).save(REP / f"water_demo_{st}.png")
    if "lamp.png" in spr:                                          # v5.0: caverna e destroços
        render_cave(spr).save(REP / "preview_cave.png")
        render_cave(spr, dark=False).save(REP / "preview_cave_lit.png")
        for st in STAGES:
            render_wrecks(st, spr).save(REP / f"preview_wrecks_{st}.png")
        make_icons_slot_v50(spr).save(REP / "slot_preview_v50.png")
    if "lamp_t2.png" in spr:                                       # v5.1: luminária forte (aprovada)
        render_cave(spr, t2=CAVE_LAMPS_T2).save(REP / "preview_cave_t2.png")
        render_cave(spr, dark=False, t2=CAVE_LAMPS_T2).save(REP / "preview_cave_t2_lit.png")
        dk = render_lamp_cmp(spr, "lamp.png", "lamp_t2.png")
        dk.save(REP / "lamp_t2_dark.png")
        zoom = Image.new("RGB", (2 * 64 + 8, 72), (21, 16, 14))           # recorte em volta das duas, pro zoom no report
        zoom.paste(dk.crop((7 * T + 16 - 32, 10 * T - 60, 7 * T + 16 + 32, 10 * T + 12)), (0, 0))
        zoom.paste(dk.crop((22 * T + 16 - 32, 10 * T - 60, 22 * T + 16 + 32, 10 * T + 12)), (72, 0))
        zoom.save(REP / "lamp_t2_dark_zoom.png")
        render_lamp_cmp(spr, "lamp.png", "lamp_t2.png", dark=False).save(REP / "lamp_t2_lit.png")
        make_icons_slot_v51(spr).save(REP / "slot_preview_v51.png")
    make_drill_preview(spr).save(REP / "drill_preview.png")
    make_drill_hand_previews(spr)                                  # v6.0: broca na mão (atual, experimento, A, B, C)
    make_slot_preview(spr, "icon_drone.png", "icon_chest.png").save(REP / "slot_preview.png")
    build_report(spr)
    print(f"{len(canv)} sprites oficiais em {OUT.relative_to(ROOT)}, {len(pend)} pendentes + {len(cand)} candidatas, "
          f"3 prévias + index.html em {REP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
