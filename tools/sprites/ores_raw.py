"""Minério bruto do "freela" (sessão experimental), portado pro Hesper e autocontido.

Gera ore_*, vein_*, pickup_*, icon_* (ferro, silício, gelo) e rock_small.png, pixel a pixel iguais aos PNGs
do freela (~/Desktop/hesper_sprites_experimento). Os lingotes e wafers NÃO entram.

  python3 tools/sprites/ores_raw.py            gera em reports/design/minerio_raw/pendentes/
  python3 tools/sprites/ores_raw.py --check    compara com os PNGs do freela (se a pasta existir) e com o
                                               hash congelado; sai com código 1 se algo divergir

Não escreve em assets/sprites/. Determinístico (seeds fixas). Luz de cima-esquerda, alpha só 0/255.
"""
import hashlib
import math
import os
import random
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "reports", "design", "minerio_raw", "pendentes")
FREELA = os.path.expanduser("~/Desktop/hesper_sprites_experimento")

# ---------------------------------------------------------------------------
# Base (do common.py do freela): paleta, Canvas, máscaras
# ---------------------------------------------------------------------------
OUTLINE = "#1b1630"
# rocha neutra (pedras soltas): mauve que conversa com os 3 chãos
ROCK = ["#b4a0a0", "#8e7b7f", "#6b5a62", "#4a3e49", "#2e2633"]



def rgb(c):
    if isinstance(c, tuple):
        return c if len(c) == 4 else (*c, 255)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


def mix(a, b, t):
    a, b = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------------------

class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    # -- básico
    def px(self, x, y, c, wrap=False):
        if wrap:
            x %= self.w
            y %= self.h
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = rgb(c)

    def get(self, x, y, wrap=False):
        if wrap:
            x %= self.w
            y %= self.h
        if 0 <= x < self.w and 0 <= y < self.h:
            return tuple(int(v) for v in self.a[y, x])
        return (0, 0, 0, 0)

    def solid(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h and self.a[y, x, 3] == 255


    def blit(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                if other.a[y, x, 3] == 255:
                    self.px(x + ox, y + oy, tuple(int(v) for v in other.a[y, x]))

    def outline(self, c=OUTLINE, diag=False):
        """Contorno externo de 1 px em volta de tudo que é opaco."""
        sol = self.a[:, :, 3] == 255
        add = np.zeros_like(sol)
        nb = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if diag:
            nb += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        for dx, dy in nb:
            sh = np.zeros_like(sol)
            ys = slice(max(dy, 0), self.h + min(dy, 0))
            yd = slice(max(-dy, 0), self.h + min(-dy, 0))
            xs = slice(max(dx, 0), self.w + min(dx, 0))
            xd = slice(max(-dx, 0), self.w + min(-dx, 0))
            sh[yd, xd] = sol[ys, xs]
            add |= sh
        add &= ~sol
        self.a[add] = rgb(c)


    def image(self):
        return Image.fromarray(self.a)


def ellipse_mask(w, h, cx, cy, rx, ry):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1.0


def poly_mask(w, h, pts):
    """Polígono cheio (regra par-ímpar, amostrando o centro do pixel)."""
    m = np.zeros((h, w), bool)
    n = len(pts)
    for y in range(h):
        yc = y + 0.5
        xs = []
        for i in range(n):
            (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(w):
                if xs[i] <= x + 0.5 < xs[i + 1]:
                    m[y, x] = True
    return m




# ---------------------------------------------------------------------------
# Extrusão 3/4 e peças (do objects.py do freela)
# ---------------------------------------------------------------------------
ORE = {
    "iron": dict(hl="#ffd6a6", base="#e8a066", mid="#c97a45", sh="#a5582c",
                 plate=("#9a6450", "#7a4a3a", "#5a3328", "#40241e")),
    "silicon": dict(hl="#f5f9ff", base="#c3d1e2", mid="#9eaec4", sh="#7d8ca3",
                    plate=("#7b8296", "#5d6478", "#454b5c", "#323644")),
    "ice": dict(hl="#f0fdff", base="#a6ecff", mid="#78cfee", sh="#4fb3d6",
                plate=("#6d93a8", "#4f7388", "#3a586b", "#2a4150")),
}



def _shift(m, dx, dy):
    h, w = m.shape
    out = np.zeros_like(m)
    ys, yd = slice(max(-dy, 0), h - max(dy, 0)), slice(max(dy, 0), h - max(-dy, 0))
    xs, xd = slice(max(-dx, 0), w - max(dx, 0)), slice(max(dx, 0), w - max(-dx, 0))
    out[yd, xd] = m[ys, xs]
    return out


def extrude(top, t, hl, base, mid, sh, glint=True, outline=True, facets=None):
    """Tampo `top` (bool) + face frontal de `t` px. facets: máscara opcional do tampo que fica em sombra."""
    h, w = top.shape
    cv = Canvas(w, h)
    front = np.zeros_like(top)
    for k in range(1, t + 1):
        front |= _shift(top, 0, k)
    front &= ~top
    ys, xs = np.nonzero(top | front)
    if len(xs) == 0:
        return cv
    x0, x1 = xs.min(), xs.max()
    for y, x in zip(*np.nonzero(front)):
        u = (x - x0) / max(1, x1 - x0)
        below = y + 1 >= h or not front[y + 1, x]
        cv.px(x, y, sh if (u > 0.68 or below) else mid)
    for y, x in zip(*np.nonzero(top)):
        up = y == 0 or not top[y - 1, x]
        lf = x == 0 or not top[y, x - 1]
        rt = x == w - 1 or not top[y, x + 1]
        if facets is not None and facets[y, x]:
            c = mid
        elif up or (lf and not rt):
            c = hl
        elif rt:
            c = mid
        else:
            c = base
        cv.px(x, y, c)
    if glint:
        # brilho: primeiro pixel do tampo a partir do canto de cima-esquerda, um pra dentro
        for s in range(2, w + h):
            hit = [(x, s - x) for x in range(max(0, s - h + 1), min(w, s + 1)) if top[s - x, x]]
            if hit:
                gx, gy = hit[len(hit) // 2]
                if gy + 1 < h and gx + 1 < w and top[gy + 1, gx + 1]:
                    cv.px(gx + 1, gy + 1, "#ffffff")
                break
    if outline:
        cv.outline()
    return cv


def lump_mask(w, h, cx, cy, rx, ry, seed, wob=0.12):
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.3) for _ in range(3)]
    yy, xx = np.mgrid[0:h, 0:w]
    ang = np.arctan2(yy + 0.5 - cy, xx + 0.5 - cx)
    r = 1 + wob * (np.sin(ang * 2 + ph[0]) + 0.6 * np.sin(ang * 3 + ph[1]))
    return ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= r * r


def piece(kind, P, w, h, cx, cy, size, seed=0):
    """Uma peça de minério isolada (canvas do tamanho w×h)."""
    if kind == "iron":            # pepita: caroço arredondado
        top = lump_mask(w, h, cx, cy, size, size * 0.72, seed)
        return extrude(top, max(2, size // 2), P["hl"], P["base"], P["mid"], P["sh"])
    if kind == "silicon":         # lasca grossa: placa angulosa inclinada, cantos aparados
        rnd = random.Random(seed)
        s = size
        lean = rnd.choice([-1, 1]) * s * 0.35
        pts = [(cx - s + lean, cy - s * 0.55), (cx + s * 0.4 + lean, cy - s * 0.75), (cx + s, cy + s * 0.1),
               (cx - s * 0.1, cy + s * 0.5), (cx - s * 1.05, cy + s * 0.15)]
        top = poly_mask(w, h, pts)
        # facetinha sombreada na metade de baixo-direita: lasca tem aresta
        yy, xx = np.mgrid[0:h, 0:w]
        fac = top & ((xx - cx) * 0.5 + (yy - cy) > s * 0.18)
        return extrude(top, max(2, int(s * 0.6)), P["hl"], P["base"], P["mid"], P["sh"], facets=fac)
    if kind == "ice":             # cubo: tampo quadrado achatado + face alta
        s = size
        top = np.zeros((h, w), bool)
        x0, y0 = int(cx - s), int(cy - s * 0.6)
        top[y0:y0 + int(s * 1.2), x0:x0 + 2 * s] = True
        top[y0, x0] = top[y0, x0 + 2 * s - 1] = False
        return extrude(top, int(s * 1.1), P["hl"], P["base"], P["mid"], P["sh"])
    raise ValueError(kind)


def cluster(kind, w, h, items):
    """Compõe peças de trás pra frente (o contorno da da frente separa as de trás)."""
    P = ORE[kind]
    cv = Canvas(w, h)
    for (cx, cy, s, seed) in sorted(items, key=lambda it: it[1]):
        cv.blit(piece(kind, P, w, h, cx, cy, s, seed), 0, 0)
    return cv




# ---------------------------------------------------------------------------
# Minério na parede (ore_*), veio 2x2 (vein_*) e pedaço bruto (icon_*/pickup_*): do items.py do freela
# ---------------------------------------------------------------------------
# brilho, claro, base, sombra, fundo (o "buraco" em volta da pinta)
MIN = {
    "iron": ["#ffe0bd", "#f4b27a", "#e8a066", "#b86a38", "#6e3a22"],
    "silicon": ["#ffffff", "#dde6f2", "#c3d1e2", "#8796b0", "#4a5168"],
    "ice": ["#f4feff", "#c8f6ff", "#a6ecff", "#5fb8de", "#2c6a8c"],
}
# rocha do pedaço bruto (o minério vem com um pouco de pedra grudada, como o raw do Minecraft)
GANGUE = ["#c9b8b4", "#9d8a8c", "#76646b", "#4e414b"]

# pintas em pixel: '#' = mineral. Formas pequenas e duras, sem círculo.
SPECKS = [
    [".##.", "####", ".##."],
    ["##.", "###", ".##"],
    [".#", "##"],
    ["###", "##.", "#.."],
    [".##", "###", "##."],
    ["##", "##"],
]


def vein_line(cv, kind, x0, y0, x1, y1, rnd, protect=None):
    """Veio em linha: rachadura preenchida que atravessa a pedra de ponta a ponta (só dentro da rocha, nunca no
    contorno). Fundo escuro de 1 px (a "fenda"), miolo na cor do minério, brilho a cada poucos px (luz de cima-esquerda)."""
    pal = MIN[kind]
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    pts, y = [], y0
    for i in range(n + 1):
        t = i / n
        y = y0 + (y1 - y0) * t + rnd.choice([-1, 0, 0, 1]) * (1 if 0.1 < t < 0.9 else 0)
        pts.append((round(x0 + (x1 - x0) * t), round(y)))
    ok = lambda x, yy: cv.solid(x, yy) and cv.get(x, yy)[:3] != rgb(OUTLINE)[:3]
    for (x, yy) in pts:                                       # fenda
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)):
            if ok(x + dx, yy + dy):
                cv.px(x + dx, yy + dy, pal[4])
    for i, (x, yy) in enumerate(pts):                         # miolo
        for dx, dy in ((0, 0), (1, 0)):
            if ok(x + dx, yy + dy):
                cv.px(x + dx, yy + dy, pal[2])
        if ok(x, yy + 1) and i % 2 == 0:
            cv.px(x, yy + 1, pal[3])
        if ok(x, yy) and i % 3 == 1:
            cv.px(x, yy, pal[0])
    return pts



def speck(cv, x, y, shape, pal, socket=True):
    """Pinta cravada: brilho na borda de cima/esquerda, sombra na de baixo/direita, buraco escuro fora."""
    pts = {(x + i, y + j) for j, row in enumerate(shape) for i, ch in enumerate(row) if ch == "#"}
    if socket:
        for (px, py) in pts:
            for (dx, dy) in ((1, 0), (0, 1), (1, 1)):
                if (px + dx, py + dy) not in pts:
                    cv.px(px + dx, py + dy, pal[4])
    for (px, py) in pts:
        up, left = (px, py - 1) in pts, (px - 1, py) in pts
        down, right = (px, py + 1) in pts, (px + 1, py) in pts
        if not up and not left:
            c = pal[0]
        elif not up or not left:
            c = pal[1]
        elif not down or not right:
            c = pal[3]
        else:
            c = pal[2]
        cv.px(px, py, c)


BIG = [
    [".###.", "#####", "####.", ".##.."],
    ["##...", "####.", ".####", "..##."],
    [".##..", "####.", "#####", ".###."],
    ["###", "###", ".##"],
]
# (x, y, forma, grande?) — 4 a 5 grupos gordos + pintinhas soltas, como o bloco de minério do Minecraft
ORE_SPOTS = {
    "iron": [(3, 3, 0, 1), (8, 6, 2, 0), (18, 2, 1, 1), (23, 6, 3, 0), (10, 12, 2, 1), (15, 15, 4, 0), (22, 17, 3, 1),
             (26, 21, 2, 0), (3, 21, 1, 1), (7, 25, 0, 0), (15, 24, 2, 1), (27, 11, 2, 0)],
    "silicon": [(4, 2, 1, 1), (9, 6, 2, 0), (19, 4, 0, 1), (25, 8, 3, 0), (8, 14, 3, 1), (14, 18, 1, 0),
                (21, 18, 2, 1), (27, 23, 2, 0), (2, 23, 2, 1), (14, 25, 0, 1)],
    "ice": [(3, 4, 3, 1), (7, 8, 5, 0), (16, 2, 0, 1), (22, 6, 2, 0), (9, 13, 1, 1), (15, 17, 2, 0), (22, 16, 3, 1),
            (27, 20, 5, 0), (3, 23, 2, 1), (14, 24, 0, 1), (27, 11, 4, 0)],
}


def ore(kind):
    """Overlay 32×32 na parede: pintas cravadas espalhadas pelo tampo (sem contorno: é rocha com veio)."""
    if kind == "magmatite":
        return ore_magma()
    cv = Canvas(32, 32)
    for (x, y, s, big) in ORE_SPOTS[kind]:
        speck(cv, x, y, BIG[s] if big else SPECKS[s], MIN[kind])
    return cv


def vein(kind, lines=False):
    """Veio 64×64 no chão: laje de rocha neutra rachada, com pintas do mineral cravadas (2 tamanhos)."""
    rnd = random.Random({"iron": 11, "silicon": 22, "ice": 33}[kind])
    cv = Canvas(64, 64)
    rk = [mix(c, MIN[kind][3], 0.28) for c in ROCK]                                # rocha puxando pra cor do mineral
    lumps = [(20, 22, 13, 9), (42, 20, 12, 8), (16, 42, 11, 8), (36, 40, 14, 10), (52, 42, 8, 7), (28, 52, 10, 6)]
    yy, xx = np.mgrid[0:64, 0:64]
    for (cx, cy, rx, ry) in sorted(lumps, key=lambda l: l[1]):
        m = ellipse_mask(64, 64, cx, cy, rx, ry)
        m &= ((xx - cx) * 0.7 + (yy - cy) * 0.9) < rx * 0.95 - rnd.uniform(0, 2)    # corta uma aresta
        face = np.zeros_like(m)
        face[2:] = m[:-2] & ~m[2:]                                                  # 2 px de face frontal
        face |= np.vstack([np.zeros((1, 64), bool), m[:-1]]) & ~m
        for y, x in zip(*np.nonzero(face)):
            cv.px(x, y, rk[3])
        for y, x in zip(*np.nonzero(m)):
            d = (x - cx) / rx + (y - cy) / ry
            cv.px(x, y, rk[0] if d < -0.9 else rk[1] if d < 0.3 else rk[2])
    cv.outline()
    for (cx, cy, rx, ry) in lumps:                                                   # rachaduras
        x, y = cx - rx // 2, cy + 1
        for _ in range(rx // 2):
            if cv.get(x, y)[:3] != (0, 0, 0) and cv.solid(x, y):
                cv.px(x, y, rk[3])
            x += 1
            y += rnd.choice([-1, 0, 0, 1])
    if lines:                                                   # proposta B: veio em linha, não pinta
        for (cx, cy, rx, ry) in lumps:
            vein_line(cv, kind, cx - rx + 1, cy + ry * 0.6, cx + rx - 1, cy - ry * 0.6, rnd)
            if rx >= 12:
                vein_line(cv, kind, cx - rx * 0.2, cy - ry * 0.9, cx + rx * 0.4, cy + ry * 0.9, rnd)
        return cv
    spots = [(10, 15, 0), (19, 13, 3), (26, 19, 1), (34, 12, 0), (44, 14, 3), (49, 21, 1), (14, 22, 2),
             (8, 37, 1), (17, 41, 0), (24, 36, 2), (30, 33, 3), (38, 38, 0), (44, 34, 2), (49, 39, 1), (55, 43, 2),
             (22, 50, 0), (30, 48, 1), (36, 45, 2), (12, 45, 2), (40, 20, 2)]
    for (x, y, s) in spots:                                     # muitas pintas gordas: o veio tem que ler de longe
        if cv.solid(x + 2, y + 2):
            speck(cv, x, y, BIG[s], MIN[kind])
    return cv




RAW_BUMPS = {
    # calombos (cx, cy, r) desenhados de trás pra frente; cada um tem brilho e sombra próprios
    "iron": [(5, 5, 3.0), (10, 4.5, 3.0), (13, 8, 2.4), (4, 9.5, 3.2), (9, 8.5, 3.6), (7, 12.5, 2.8), (12, 12, 2.6)],
    "silicon": [(5, 5, 3.0), (10.5, 5, 3.0), (4.5, 10, 3.0), (9, 9, 3.4), (12.5, 10.5, 2.4), (8, 12.5, 2.4)],
    "ice": [(5, 6, 3.0), (10, 4.5, 2.8), (12.5, 9, 2.6), (4, 11, 2.6), (8.5, 9.5, 3.4), (9, 13, 2.2)],
}


def raw(kind, size=16, scale=1.0, seed=0):
    """Pedaço bruto à la Minecraft: pilha de calombos, cada um com brilho em cima/esquerda e sombra
    embaixo/direita, cavidades escuras, pedra grudada (ferro/silício) ou bolha de ar (gelo)."""
    pal = BASALT_RAW if kind == "magmatite" else MIN[kind]
    cv = Canvas(size, size)
    off = (size - 16 * scale) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    m = np.zeros((size, size), bool)
    kind_b = "iron" if kind == "magmatite" else kind
    square = kind in ("silicon", "ice")                          # silício e gelo: calombo facetado
    for (cx, cy, r) in RAW_BUMPS[kind_b]:
        cx, cy, r = cx * scale + off, cy * scale + off, r * scale
        dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
        d = (np.maximum(abs(dx), abs(dy)) * 0.75 + (abs(dx) + abs(dy)) * 0.3) / r if square else np.hypot(dx, dy) / r
        inside = d <= 1
        m |= inside
        for y, x in zip(*np.nonzero(inside)):
            v = (-dx[y, x] - dy[y, x]) / r
            if d[y, x] > 0.8 and v < 0:
                c = pal[3]
            elif v > 0.75:
                c = pal[0]
            elif v > 0.15:
                c = pal[1]
            elif v > -0.55:
                c = pal[2]
            else:
                c = pal[3]
            cv.px(x, y, c)
    rnd = random.Random(seed * 7 + len(kind))
    interior = [(y, x) for (y, x) in zip(*np.nonzero(m))
                if all(0 <= y + dy < size and 0 <= x + dx < size and m[y + dy, x + dx]
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    rnd.shuffle(interior)
    n = max(2, round(len(interior) / 30))
    for (y, x) in interior[:n]:                                  # cavidade: pixel fundo + borda clara embaixo
        cv.px(x, y, pal[4])
        cv.px(x, y + 1, pal[1])
    if kind == "magmatite":
        lava_raw(cv, m, size, scale, seed)
    elif kind != "ice":
        for (y, x) in interior[n:n + 2]:                         # pedrinha grudada (gangue)
            cv.px(x, y, GANGUE[1])
            cv.px(x + 1, y, GANGUE[2])
    else:
        for (y, x) in interior[n:n + 2]:                         # bolha de ar presa no gelo
            cv.px(x, y, "#ffffff")
    cv.outline()
    return cv



# ---------------------------------------------------------------------------
# Rocha pequena (objects.py do freela)
# ---------------------------------------------------------------------------
def make_rock_small():
    w = h = 32
    top = lump_mask(w, h, 15, 17, 10, 6.5, 9, wob=0.08)
    yy, xx = np.mgrid[0:h, 0:w]
    fac = top & ((xx - 15) * 0.8 + (yy - 17) * 1.4 > 2)          # aresta: metade de baixo-direita sombreada
    cv = Canvas(w, h)
    big = extrude(top, 6, ROCK[0], ROCK[1], ROCK[2], ROCK[3], glint=False, facets=fac)
    peb = extrude(lump_mask(w, h, 25, 25, 3.5, 2.3, 4), 2, ROCK[0], ROCK[1], ROCK[2], ROCK[3], glint=False)
    cv.blit(big, 0, 0)
    cv.blit(peb, 0, 0)
    # rachadura e pontinhos
    for (x, y) in ((11, 15), (12, 16), (13, 16), (14, 17)):
        cv.px(x, y, ROCK[3])
        cv.px(x, y + 1, ROCK[0])
    cv.px(9, 14, ROCK[0])
    cv.px(19, 13, ROCK[0])
    return cv



# ---------------------------------------------------------------------------
# EXTRA (proposta nossa, não vem do freela): cristalzinho do minério por cima do rock_small
# Hoje o jogo desenha isso por código (game/art.py ore_fleck). Overlay 32x32 no mesmo tile da rocha.
# ---------------------------------------------------------------------------
FLECK_LAYOUT = {
    "iron": [(12, 15, 3, 1), (19, 16, 3, 2)],
    "silicon": [(12, 14, 3, 1), (19, 16, 3, 2)],
    "ice": [(12, 14, 3, 1), (19, 16, 2, 2)],
}


def fleck(kind):
    return cluster(kind, 32, 32, FLECK_LAYOUT[kind])


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------
KINDS = ("iron", "silicon", "ice")


def contract():
    """nome do arquivo -> (Canvas, (w, h)). Mesmos nomes e tamanhos de assets/sprites/."""
    d = {}
    for k in KINDS:
        d[f"ore_{k}.png"] = (ore(k), (32, 32))
        d[f"vein_{k}.png"] = (vein(k), (64, 64))
        d[f"icon_{k}.png"] = (raw(k), (16, 16))
        d[f"pickup_{k}.png"] = (raw(k, 16, 0.75, 2), (16, 16))
    d["rock_small.png"] = (make_rock_small(), (32, 32))
    return d


def extras():
    return {**{f"fleck_{k}.png": (fleck(k), (32, 32)) for k in KINDS}, **rocks_vein(),
            **{f"vein_linha_{k}.png": (vein_organic(k), (64, 64)) for k in KINDS}, **magma_family()}


def save(cv, path):
    assert set(np.unique(cv.a[:, :, 3]).tolist()) <= {0, 255}, f"{path}: alpha fora de 0/255"
    cv.a[cv.a[:, :, 3] == 0] = 0
    cv.image().save(path)


def build():
    os.makedirs(OUT, exist_ok=True)
    for name, (cv, size) in {**contract(), **extras()}.items():
        assert (cv.w, cv.h) == size, name
        save(cv, os.path.join(OUT, name))
    return sorted(os.listdir(OUT))


def check():
    bad = 0
    for name, (cv, _s) in contract().items():
        ref = os.path.join(FREELA, name)
        if not os.path.exists(ref):
            print(f"?? {name}: sem referência em {FREELA}")
            bad += 1
            continue
        a = np.array(Image.open(ref).convert("RGBA"))
        ok = a.shape == cv.a.shape and bool((a == cv.a).all())
        print(f"{'OK ' if ok else 'DIF'} {name}")
        bad += not ok
    h1 = hashlib.md5(b"".join(cv.a.tobytes() for cv, _ in contract().values())).hexdigest()
    h2 = hashlib.md5(b"".join(cv.a.tobytes() for cv, _ in contract().values())).hexdigest()
    print(f"determinismo: {'OK' if h1 == h2 else 'FALHOU'} ({h1})")
    bad += h1 != h2
    print("tudo bate pixel a pixel" if not bad else f"{bad} divergência(s)")
    return bad




# ---------------------------------------------------------------------------
# EXTRA (pedido do dono): rocha pequena COM VEIO DENTRO (2 variações por minério)
# Linhas da cor do minério cruzando a pedra de uma ponta à outra, rachaduras preenchidas, brilho na linha.
# ---------------------------------------------------------------------------
ROCK_VARS = [
    dict(top=(15, 17, 10, 6.5, 9, 0.08), peb=(25, 25, 3.5, 2.3, 4), lines=[(8, 10, 15, 25), (14, 11, 27, 21)]),
    dict(top=(16, 17, 9.5, 7.2, 21, 0.1), peb=(6, 25, 3.2, 2.2, 8), lines=[(5, 21, 17, 10), (16, 10, 26, 24)]),
]


def rock_vein(kind, v):
    d = ROCK_VARS[v]
    w = h = 32
    cx, cy, rx, ry, seed, wob = d["top"]
    top = lump_mask(w, h, cx, cy, rx, ry, seed, wob=wob)
    yy, xx = np.mgrid[0:h, 0:w]
    fac = top & ((xx - cx) * 0.8 + (yy - cy) * 1.4 > 2)
    cv = Canvas(w, h)
    cv.blit(extrude(top, 6, ROCK[0], ROCK[1], ROCK[2], ROCK[3], glint=False, facets=fac), 0, 0)
    px_, py_, prx, pry, ps = d["peb"]
    cv.blit(extrude(lump_mask(w, h, px_, py_, prx, pry, ps), 2, ROCK[0], ROCK[1], ROCK[2], ROCK[3], glint=False), 0, 0)
    rnd = random.Random(100 + v * 7 + len(kind))
    for (x0, y0, x1, y1) in d["lines"]:
        vein_line(cv, kind, x0, y0, x1, y1, rnd)
    return cv


def rocks_vein():
    return {f"rock_small_{k}_{v}.png": (rock_vein(k, v), (32, 32)) for k in KINDS for v in (0, 1)}




# ---------------------------------------------------------------------------
# VEIO ORGÂNICO (v2 do veio 2x2) e MAGMATITA
# Rachaduras irregulares que seguem a rocha: espessura varia (1 a 3 px), ramificam e se perdem em pontilhado.
# ---------------------------------------------------------------------------
# lava: núcleo amarelo, laranja, vermelho, fenda escura. (mesma ordem do MIN: brilho, claro, base, sombra, fundo)
MIN["magmatite"] = ["#fff4cc", "#ffd27a", "#ff9a3d", "#e0602a", "#2a2333"]   # lava do aquecedor; [4] = rocha em volta da fissura
# basalto: rocha escura e fria, quase preta (pedra quente de fumarola)
BASALT = ["#6a5f72", "#4e4558", "#3a3244", "#2a2333", "#1d1726"]      # o basalto do aquecedor (machines_r3d.py)
BASALT_RAW = ["#6a5f72", "#4e4558", "#3a3244", "#2a2333", "#1b1630"]


def _stamp(m, x, y, wd, horiz):
    h, w = m.shape
    pts = [(x, y)]
    if wd >= 2:
        pts.append((x, y + 1) if horiz else (x + 1, y))
    if wd >= 3:
        pts += [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
    for (a, b) in pts:
        if 0 <= a < w and 0 <= b < h:
            m[b, a] = True


def crack(m, rnd, x, y, ang, length, wd, depth=0, wob=0.18):
    """Passeio aleatório com direção persistente: espessura oscila, ramifica e a ponta vira pontilhado."""
    ph = rnd.uniform(0, 6.3)
    for i in range(int(length)):
        ang += rnd.gauss(0, wob)
        x += math.cos(ang)
        y += math.sin(ang) * 0.8
        t = i / max(1, length - 1)
        wi = wd * (0.55 + 0.6 * (0.5 + 0.5 * math.sin(i * 0.35 + ph))) * (1.0 if t < 0.6 else 1.6 - t)
        wi = max(1, min(3, round(wi)))
        if t > 0.8 and i % 2:                                     # se perde: pontilhado
            continue
        _stamp(m, round(x), round(y), wi, abs(math.cos(ang)) > abs(math.sin(ang)))
        if depth < 2 and wd >= 1.5 and 0.15 < t < 0.8 and rnd.random() < 0.035:
            crack(m, rnd, x, y, ang + rnd.choice([-1, 1]) * rnd.uniform(0.6, 1.2), length * rnd.uniform(0.3, 0.5),
                  max(1, wd - 1), depth + 1, wob + 0.08)


MAGMA_STATIC = ["#ffd27a", "#ffae55", "#ff9a3d", "#e0602a", "#2a2333"]   # estático: laranja do aquecedor, só um toque de amarelo


def paint_crack(cv, m, pal, socket=True):
    """Pinta a máscara `m` (já recortada na rocha): fenda escura em volta, miolo, brilho em cima/esquerda, sombra embaixo."""
    h, w = m.shape
    if pal is MIN["magmatite"]:
        pal = MAGMA_STATIC
    if socket:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1)):
            sh = np.zeros_like(m)
            sh[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = m[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
            for y, x in zip(*np.nonzero(sh & ~m & (cv.a[:, :, 3] == 255))):
                if tuple(cv.a[y, x, :3]) != rgb(OUTLINE)[:3]:
                    cv.px(x, y, pal[4])
    for y, x in zip(*np.nonzero(m)):
        up = y > 0 and m[y - 1, x]
        lf = x > 0 and m[y, x - 1]
        dn = y + 1 < h and m[y + 1, x]
        rt = x + 1 < w and m[y, x + 1]
        if not up and not lf:
            c = pal[0]
        elif not up or not lf:
            c = pal[1] if (x + y) % 3 else pal[0]
        elif not dn or not rt:
            c = pal[3]
        else:
            c = pal[2]
        cv.px(x, y, c)


def _solid_noline(cv):
    sol = cv.a[:, :, 3] == 255
    return sol & ~(cv.a[:, :, :3] == np.array(rgb(OUTLINE)[:3], np.uint8)).all(axis=2)


def poly_slab(rnd, cx, cy, r, n):
    a0 = rnd.uniform(0, 6.3)
    pts = []
    for i in range(n):
        a = a0 + (i + rnd.uniform(-0.3, 0.3)) * 2 * math.pi / n
        rr = r * rnd.uniform(0.62, 1.15)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * rnd.uniform(0.62, 0.8)))
    return poly_mask(64, 64, pts)


def vein_organic_parts(kind):
    """Veio 2x2 64x64: lajes angulosas (polígonos irregulares, sem elipses repetidas) cruzadas por rachaduras
    preenchidas do minério. Devolve (canvas só com as lajes, máscara das rachaduras)."""
    rnd = random.Random({"iron": 5, "silicon": 6, "ice": 7, "magmatite": 8}[kind] * 131)
    rock = BASALT if kind == "magmatite" else [mix(c, MIN[kind][3], 0.28) for c in ROCK]
    cv = Canvas(64, 64)
    slabs = [(17, 20, 17, 7), (43, 18, 15, 6), (14, 42, 14, 7), (35, 38, 19, 8), (54, 45, 10, 6), (26, 55, 13, 6),
             (52, 28, 9, 6)]
    items = [(cy, poly_slab(rnd, cx, cy, r, n)) for (cx, cy, r, n) in slabs]
    for _cy, top in sorted(items, key=lambda i: i[0]):
        cv.blit(extrude(top, 3, rock[0], rock[1], rock[2], rock[3], glint=False, outline=True), 0, 0)
    allowed = _solid_noline(cv)
    m = np.zeros((64, 64), bool)
    for (cx, cy, r, n) in slabs:                                  # uma rachadura por laje, de borda a borda
        a = rnd.choice([-1, 1]) * rnd.uniform(0.15, 0.6) + (0 if rnd.random() < 0.5 else math.pi)
        sx, sy = cx - math.cos(a) * r * 0.9, cy - math.sin(a) * r * 0.5
        crack(m, rnd, sx, sy, a, r * 1.9, rnd.choice([2, 3]))
    for (x, y, ang, ln, wd) in [(3, 24, 0.2, 58, 2), (8, 50, -0.3, 52, 2), (30, 6, 1.3, 36, 2)]:
        crack(m, rnd, x, y, ang, ln, wd)
    if kind == "magmatite":                                       # rede de rachaduras finas por TODA a pedra
        for (cx, cy, r, n) in slabs:
            for _ in range(3):
                x, y = cx + rnd.uniform(-r, r) * 0.8, cy + rnd.uniform(-r, r) * 0.4
                crack(m, rnd, x, y, rnd.uniform(0, 6.3), r * rnd.uniform(1.0, 1.7), 1.0, wob=0.28)
    return cv, m & allowed


def vein_organic(kind):
    cv, m = vein_organic_parts(kind)
    paint_crack(cv, m, MIN[kind])
    return cv


def ore_magma_parts():
    """ore_magmatite 32x32: rede de fissuras de lava espalhada pela parede inteira."""
    rnd = random.Random(808)
    cv = Canvas(32, 32)
    m = np.zeros((32, 32), bool)
    for (x, y, ang, ln, wd) in [(1, 8, 0.45, 30, 3), (3, 26, -0.5, 28, 3), (16, 1, 1.3, 22, 2)]:
        crack(m, rnd, x, y, ang, ln, wd)
    for _ in range(9):
        crack(m, rnd, rnd.uniform(1, 30), rnd.uniform(1, 30), rnd.uniform(0, 6.3), rnd.uniform(9, 16), 1.0, wob=0.28)
    return cv, m


def ore_magma():
    cv, m = ore_magma_parts()
    paint_crack(cv, m, MIN["magmatite"])
    return cv


def lava_raw(cv, m, size, scale, seed):
    """Fissuras de lava no pedaço bruto (icon/pickup): 1 a 2 px, sem fenda escura."""
    rnd = random.Random(900 + seed)
    k = np.zeros((size, size), bool)
    c = size / 2
    crack(k, rnd, c - 5 * scale, c - 3 * scale, 0.7, 11 * scale, 1.2, wob=0.35)
    crack(k, rnd, c + 5 * scale, c - 4 * scale, 2.1, 9 * scale, 1.0, wob=0.35)
    k &= m
    paint_crack(cv, k, MIN["magmatite"], socket=False)


def rock_vein_magma_parts(v):
    """Rocha de basalto (mesmas 2 formas das outras) com fissuras de lava por toda a pedra."""
    d = ROCK_VARS[v]
    w = h = 32
    cx, cy, rx, ry, seed, wob = d["top"]
    top = lump_mask(w, h, cx, cy, rx, ry, seed, wob=wob)
    yy, xx = np.mgrid[0:h, 0:w]
    fac = top & ((xx - cx) * 0.8 + (yy - cy) * 1.4 > 2)
    cv = Canvas(w, h)
    B = BASALT
    cv.blit(extrude(top, 6, B[0], B[1], B[2], B[3], glint=False, facets=fac), 0, 0)
    px_, py_, prx, pry, ps = d["peb"]
    cv.blit(extrude(lump_mask(w, h, px_, py_, prx, pry, ps), 2, B[0], B[1], B[2], B[3], glint=False), 0, 0)
    allowed = _solid_noline(cv)
    rnd = random.Random(300 + v)
    m = np.zeros((h, w), bool)
    for (x0, y0, x1, y1) in d["lines"]:
        crack(m, rnd, x0, y0, math.atan2(y1 - y0, x1 - x0), math.hypot(x1 - x0, y1 - y0), 1.6, wob=0.12)
    for _ in range(7):                                            # rede fina por toda a pedra
        crack(m, rnd, rnd.uniform(5, 27), rnd.uniform(11, 25), rnd.uniform(0, 6.3), rnd.uniform(7, 13), 1.0, wob=0.3)
    return cv, m & allowed


def rock_vein_magma(v):
    cv, m = rock_vein_magma_parts(v)
    paint_crack(cv, m, MIN["magmatite"])
    return cv


# --- animação: 4 quadros (a lava pulsa e o calor escorre pelas fissuras; sem halo fora da pedra) -------------
def paint_lava_frame(cv, m, f, socket=True):
    pal = MIN["magmatite"]
    h, w = m.shape
    if socket:
        paint_socket(cv, m, pal)
    ramp_ = [pal[3], pal[2], pal[1], pal[0]]
    for y, x in zip(*np.nonzero(m)):
        edge = not (0 < x < w - 1 and 0 < y < h - 1 and m[y - 1, x] and m[y + 1, x] and m[y, x - 1] and m[y, x + 1])
        ph = f / 4 - (x * 0.6 + y * 0.4) / 9.0                    # onda que desce pelas fissuras
        lvl = round(1.5 + 1.5 * math.sin(2 * math.pi * ph))
        cv.px(x, y, ramp_[max(0, lvl - (1 if edge else 0))])


def paint_socket(cv, m, pal):
    h, w = m.shape
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1)):
        sh = np.zeros_like(m)
        sh[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = m[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
        for y, x in zip(*np.nonzero(sh & ~m & (cv.a[:, :, 3] == 255))):
            if tuple(cv.a[y, x, :3]) != rgb(OUTLINE)[:3]:
                cv.px(x, y, pal[4])


def anim_strip(parts, glow_on):
    """parts() -> (canvas base, máscara). Tira horizontal de 4 quadros do mesmo tamanho do estático."""
    base, m = parts()
    out = Canvas(base.w * 4, base.h)
    for f in range(4):
        fr = Canvas(base.w, base.h)
        fr.a = base.a.copy()
        paint_lava_frame(fr, m, f)
        out.blit(fr, f * base.w, 0)
    return out



# ---------------------------------------------------------------------------
# vein_magmatite v3 ("mais lava"): placas de basalto quase pretas com desnível, uma fenda principal larga de lava
# (núcleo amarelo-branco, laranja, borda vermelha), rachaduras finas ramificadas, brilho que vaza pras quinas das
# placas vizinhas (dentro da silhueta) e brasas. Referência de estilo: a imagem do dono (só estilo, desenho original).
# ---------------------------------------------------------------------------
B_DARK = ["#3c3446", "#2c2536", "#211b29", "#181320", "#120e18"]


def _lift(mask, k):
    out = np.zeros_like(mask)
    if k:
        out[:-k] = mask[k:]
        return out
    return mask


def vein_lava_parts():
    rnd = random.Random(8 * 977)
    cv = Canvas(64, 64)
    # placas: (cx, cy, r, vértices, altura do degrau); as que encostam na fenda são mais altas
    slabs = [(15, 17, 17, 7, 0), (44, 14, 14, 6, 3), (12, 41, 14, 7, 0), (36, 41, 18, 8, 2), (55, 46, 10, 6, 0),
             (26, 57, 13, 6, 0), (53, 27, 11, 6, 2), (30, 24, 11, 6, 3)]
    items = []
    for (cx, cy, r, n, lift) in slabs:
        items.append((cy - lift, poly_slab(rnd, cx, cy, r, n), lift))
    for _cy, top, lift in sorted(items, key=lambda i: i[0]):
        top = _lift(top, lift)
        cv.blit(extrude(top, 3 + lift, B_DARK[0], B_DARK[1], B_DARK[2], B_DARK[3], glint=False), 0, 0)
    # lava RADIAL: uma poça incandescente no meio e 8 rachaduras tortas irradiando pelas juntas das placas,
    # ramificando e afinando até 1 px perto das bordas.
    allowed = _solid_noline(cv)
    C0 = (31.5, 31.0)
    joint = ~allowed                                               # contorno ou vazio: onde estão as juntas

    def jscore(x, y):
        ix, iy = int(round(x)), int(round(y))
        if not (0 <= ix < 64 and 0 <= iy < 64):
            return 1.0
        return float(joint[max(0, iy - 1):iy + 2, max(0, ix - 1):ix + 2].mean())

    samples = []                                                   # (x, y, raio, percurso desde o centro)
    for k in range(8):                                             # poça: miolo grande + lóbulos tortos
        a_ = k * math.pi / 4 + rnd.uniform(-0.3, 0.3)
        samples.append((C0[0] + math.cos(a_) * 2.2, C0[1] + math.sin(a_) * 1.8, rnd.uniform(1.8, 2.5), 0.0))
    samples.append((C0[0], C0[1], 3.6, 0.0))

    def arm(x, y, ang, length, r0, travel, depth):
        base, step, nb = ang, 0.5, 0
        n_ = int(length / step)
        for i in range(n_):
            t = i / n_
            best, bs = ang, -9
            for da in (-0.55, -0.3, -0.1, 0.1, 0.3, 0.55):
                cand = ang + da
                sc = jscore(x + math.cos(cand) * 2.2, y + math.sin(cand) * 2.2) + rnd.uniform(0, 0.45) - abs(cand - base) * 0.35
                if sc > bs:
                    best, bs = cand, sc
            ang = best + rnd.gauss(0, 0.16)
            x += math.cos(ang) * step
            y += math.sin(ang) * step
            travel += step
            r = max(0.7, r0 * (1.0 - t) ** 1.3 + 0.2)
            samples.append((x, y, r, travel))
            if depth < 2 and nb < (3 if depth == 0 else 1) and 0.2 < t < 0.7 and rnd.random() < 0.09:
                nb += 1
                arm(x, y, ang + rnd.choice([-1, 1]) * rnd.uniform(0.7, 1.2), length * rnd.uniform(0.3, 0.45), max(0.8, r * 0.6),
                    travel, depth + 1)
            if x < -2 or x > 66 or y < -2 or y > 66:
                break
    for k in range(8):
        arm(C0[0], C0[1], k * math.pi / 4 + rnd.uniform(-0.35, 0.35), rnd.uniform(26, 34), rnd.uniform(1.8, 2.2), 0.0, 0)
    rho = np.full((64, 64), 9.0)
    trav = np.zeros((64, 64))
    rr = np.zeros((64, 64))
    yy, xx = np.mgrid[0:64, 0:64]
    for (px, py, r, tr) in samples:
        d = np.hypot(xx + 0.5 - px, (yy + 0.5 - py) * 1.1) / r
        better = d < rho
        rho[better] = d[better]
        trav[better] = tr
        rr[better] = r
    lava = rho <= 1.0
    embers = []
    for _ in range(26):
        ex, ey = rnd.randrange(2, 62), rnd.randrange(2, 62)
        if allowed[ey, ex] and not lava[ey, ex]:
            embers.append((ex, ey, rnd.randrange(4)))
    return dict(cv=cv, rho=rho, trav=trav, rr=rr, lava=lava, embers=embers, allowed=allowed, c=C0)


def vein_lava_frame(P, f):
    cv = Canvas(64, 64)
    cv.a = P["cv"].a.copy()
    rho, trav, rr, lava = P["rho"], P["trav"], P["rr"], P["lava"]
    cx, cy = P["c"]
    # 1) brilho que vaza: dilatação da lava tinge as placas vizinhas (só dentro da silhueta), mais forte no centro
    dist = np.full((64, 64), 9)
    dist[lava] = 0
    cur = lava.copy()
    for d in (1, 2, 3):
        grow = cur.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            sh = np.zeros_like(cur)
            sh[max(dy, 0):64 + min(dy, 0), max(dx, 0):64 + min(dx, 0)] = cur[max(-dy, 0):64 + min(-dy, 0), max(-dx, 0):64 + min(-dx, 0)]
            grow |= sh
        dist[grow & (dist == 9)] = d
        cur = grow
    breath = 0.5 + 0.5 * math.sin(2 * math.pi * f / 4)
    for y, x in zip(*np.nonzero(P["allowed"] & ~lava & (dist <= 3))):
        base = tuple(int(v) for v in cv.a[y, x, :3])
        near = math.exp(-math.hypot(x - cx, y - cy) / 13.0)
        t = {1: 0.34, 2: 0.16, 3: 0.06}[int(dist[y, x])] * (0.55 + 0.9 * near) * (0.85 + 0.3 * breath)
        cv.px(x, y, mix((*base, 255), "#ff8a3a", t))
    # 2) brasas piscando
    for (ex, ey, ph) in P["embers"]:
        k = (f + ph) % 4
        if k == 0:
            cv.px(ex, ey, "#ffb25a")
        elif k == 1:
            cv.px(ex, ey, "#ff9a3d")
        elif k == 2:
            cv.px(ex, ey, "#a8402a")
    # 3) lava: o calor corre do centro pras pontas (onda em função do percurso); o núcleo da poça pulsa
    for y, x in zip(*np.nonzero(lava)):
        r, w_ = rho[y, x], rr[y, x]
        wave = math.sin(2 * math.pi * (f / 4 - trav[y, x] / 22))
        if w_ < 1.25:                                              # rachadura fina: laranja com calor correndo
            c = "#ffd27a" if wave > 0.55 else "#ff9a3d" if wave > -0.45 else "#e0602a"
        else:
            core = 0.30 + 0.15 * wave if trav[y, x] > 0 else 0.45 + 0.12 * math.sin(2 * math.pi * f / 4)
            if r < core:
                c = "#fff4cc"
            elif r < core + 0.18:
                c = "#ffd27a"
            elif r < 0.62 + 0.08 * wave:
                c = "#ff9a3d"
            elif r < 0.88:
                c = "#e0602a"
            else:
                c = "#a8402a"
        cv.px(x, y, c)
    cv.outline()                                                   # contorno #1b1630 também ao redor da lava
    return cv


def vein_lava():
    return vein_lava_frame(vein_lava_parts(), 0)


def vein_lava_anim():
    P = vein_lava_parts()
    out = Canvas(256, 64)
    for f in range(4):
        out.blit(vein_lava_frame(P, f), f * 64, 0)
    return out


def magma_family():
    d = {"ore_magmatite.png": (ore_magma(), (32, 32)),
         "vein_magmatite.png": (vein_lava(), (64, 64)),
         "vein_magmatite_anim.png": (vein_lava_anim(), (256, 64)),
         "ore_magmatite_anim.png": (anim_strip(ore_magma_parts, False), (128, 32)),
         "icon_magmatite.png": (raw("magmatite"), (16, 16)),
         "pickup_magmatite.png": (raw("magmatite", 16, 0.75, 2), (16, 16))}
    for v in (0, 1):
        d[f"rock_small_magmatite_{v}.png"] = (rock_vein_magma(v), (32, 32))
        d[f"rock_small_magmatite_{v}_anim.png"] = (anim_strip(lambda v=v: rock_vein_magma_parts(v), True), (128, 32))
    return d






if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(1 if check() else 0)
    for f in build():
        print(f)
