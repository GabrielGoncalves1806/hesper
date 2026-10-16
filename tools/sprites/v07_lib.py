"""v0.7 Lore · caixa de ferramentas de pixel art (sem anti-aliasing, alpha 0/255 + sombra num nível só).

Usado por v07_destrocos.py, v07_props.py e v07_constructor.py. Só PIL + numpy. Determinístico (hash fixo).
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

OUT = "#1b1630"            # contorno do jogo
SHADOW = (0, 0, 0, 92)     # sombra de chão: preto 36%, um nível só (igual aos sprites aprovados)


def C(h, a=255):
    if isinstance(h, tuple):
        return h
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def hsh(x, y, s=0):
    n = (int(x) * 374761393 + int(y) * 668265263 + s * 2246822519 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 15
    return n / 4294967296.0


def vnoise(x, y, s=0):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hsh(ix, iy, s), hsh(ix + 1, iy, s)
    c, d = hsh(ix, iy + 1, s), hsh(ix + 1, iy + 1, s)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


class Cv:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    # --- primitivas
    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.im.putpixel((int(x), int(y)), C(c))

    def get(self, x, y):
        return self.im.getpixel((int(x), int(y)))

    def rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=C(c))

    def poly(self, pts, c):
        self.d.polygon([(int(a), int(b)) for a, b in pts], fill=C(c))

    def ell(self, cx, cy, rx, ry, c):
        # elipse por teste de centro de pixel (borda estável, sem AA)
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                if ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1:
                    self.px(x, y, c)

    def line(self, pts, c, w=1):
        self.d.line([(int(a), int(b)) for a, b in pts], fill=C(c), width=w)

    def mask(self, fn):
        m = Image.new("L", (self.w, self.h), 0)
        fn(ImageDraw.Draw(m))
        return np.array(m) > 0

    def pmask(self, pts):
        return self.mask(lambda d: d.polygon([(int(a), int(b)) for a, b in pts], fill=255))

    def emask(self, cx, cy, rx, ry):
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        return (((xx + .5 - cx) / rx) ** 2 + ((yy + .5 - cy) / ry) ** 2) <= 1

    def paint(self, m, fn):
        """Pinta cada pixel da máscara com fn(x, y) -> cor (ou None pra deixar)."""
        ys, xs = np.nonzero(m)
        for y, x in zip(ys, xs):
            c = fn(int(x), int(y))
            if c is not None:
                self.im.putpixel((int(x), int(y)), C(c))

    def fill(self, m, c):
        self.paint(m, lambda x, y: c)

    def banded(self, m, cols, y0=None, y1=None, cuts=None):
        """Faixas horizontais (luz de cima): cols de claro pra escuro; cuts = frações onde troca."""
        ys = np.nonzero(m)[0]
        y0 = ys.min() if y0 is None else y0
        y1 = ys.max() + 1 if y1 is None else y1
        cuts = cuts or [(i + 1) / len(cols) for i in range(len(cols) - 1)]

        def f(x, y):
            t = (y - y0) / max(1, (y1 - y0))
            k = sum(1 for c in cuts if t >= c)
            return cols[min(k, len(cols) - 1)]
        self.paint(m, f)

    def speckle(self, m, col, p, seed=1, scale=1.0):
        """Sujeira/ferrugem: pixels de `col` onde um ruído passa de 1-p."""
        self.paint(m, lambda x, y: col if vnoise(x * .45 * scale, y * .55 * scale, seed) > 1 - p and hsh(x, y, seed + 9) > .35 else None)

    def outline(self, col=OUT):
        a = np.array(self.im)
        op = a[:, :, 3] == 255
        ring = np.zeros_like(op)
        ring[1:, :] |= op[:-1, :]
        ring[:-1, :] |= op[1:, :]
        ring[:, 1:] |= op[:, :-1]
        ring[:, :-1] |= op[:, 1:]
        ring &= ~op
        a[ring] = C(col)
        self.im = Image.fromarray(a)
        self.d = ImageDraw.Draw(self.im)

    def shadow_ell(self, cx, cy, rx, ry):
        """Sombra de chão (alpha 92) por baixo de tudo: chamar ANTES de desenhar o resto."""
        self.ell(cx, cy, rx, ry, SHADOW)

    def stamp(self, other, x, y):
        self.im.alpha_composite(other.im if isinstance(other, Cv) else other, (int(x), int(y)))
        self.d = ImageDraw.Draw(self.im)

    def flip(self):
        c = Cv(self.w, self.h)
        c.im = self.im.transpose(Image.FLIP_LEFT_RIGHT)
        c.d = ImageDraw.Draw(c.im)
        return c

    def image(self):
        return self.im

    def check(self):
        a = np.array(self.im)[:, :, 3]
        bad = ((a != 0) & (a != 255) & (a != 92))
        assert not bad.any(), "alpha fora de 0/255/92"


def from_map(rows, pal):
    h = len(rows)
    w = max(len(r) for r in rows)
    cv = Cv(w, h)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch not in ". ":
                cv.px(x, y, pal[ch])
    return cv


def sand_pile(cv, cx, cy, rx, ry, seed=3):
    """Montinho de areia/terra neutro (o mesmo tom dos destroços atuais), com topo claro e pé escuro."""
    m = cv.emask(cx, cy, rx, ry)
    cv.banded(m, ["#a39385", "#8e7f73", "#796b61", "#625650"], cuts=[.28, .6, .85])
    cv.speckle(m, "#b3a393", .22, seed)


def rubble(cv, x, y, s=1, seed=0, light="#6b717a", dark="#3b3f46"):
    """Pedacinho de sucata no chão (placa quebrada): 3×2 a 6×3 px, com contorno."""
    w, h = 4 * s + int(hsh(x, y, seed) * 3), 2 * s + 1
    cv.rect(x, y, w, h, dark)
    cv.rect(x, y, w, 1, light)
    cv.px(x + w - 1, y, dark)
    cv.rect(x - 1, y - 1, w + 2, 1, OUT) if False else None


def scatter(cv, spots, seed=0):
    for i, (x, y) in enumerate(spots):
        k = hsh(x, y, seed + i)
        if k < .35:
            cv.rect(x, y, 3, 2, "#4a4f57"); cv.rect(x, y, 3, 1, "#6b717a")
        elif k < .7:
            cv.rect(x, y, 4, 2, "#3b3f46"); cv.rect(x, y, 2, 1, "#5a6069")
        else:
            cv.rect(x, y, 2, 2, "#796b61"); cv.px(x, y, "#a39385")
