"""Kit de desenho das cutscenes do trailer (Dra. Ilves).

Pixel art de verdade: tudo é desenhado com PIL sem anti-aliasing (polygon/ellipse/line do ImageDraw são serrilhados),
alpha só 0 ou 255, contorno #1b1630 feito por vizinhança, luz em faixas com dither ordenado (Bayer 4×4) só na borda
das faixas. Determinístico: nada de random sem seed.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

OUTLINE = "#1b1630"

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], float) / 16.0 + 1 / 32


def rgb(c):
    if isinstance(c, (tuple, list)):
        return tuple(c) if len(c) == 4 else (*c, 255)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


def hexc(t):
    return "#%02x%02x%02x" % tuple(int(v) for v in t[:3])


def mix(a, b, t):
    a, b = rgb(a), rgb(b)
    return hexc([round(a[i] + (b[i] - a[i]) * t) for i in range(3)])


class Cv:
    """Canvas RGBA com primitivas serrilhadas."""

    def __init__(self, w, h, fill=None):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w, h), rgb(fill) if fill else (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    # ---- primitivas
    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.im.putpixel((int(x), int(y)), rgb(c))

    def rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=rgb(c))

    def poly(self, pts, c):
        self.d.polygon([(round(x), round(y)) for x, y in pts], fill=rgb(c))

    def ell(self, x0, y0, x1, y1, c):
        self.d.ellipse([x0, y0, x1, y1], fill=rgb(c))

    def line(self, pts, c, w=1):
        self.d.line([(round(x), round(y)) for x, y in pts], fill=rgb(c), width=w)

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def paste(self, other, x=0, y=0):
        src = other.im if isinstance(other, Cv) else other
        self.im.alpha_composite(src, (int(x), int(y)))

    # ---- numpy
    def arr(self):
        return np.array(self.im)

    def set_arr(self, a):
        self.im = Image.fromarray(a.astype(np.uint8), "RGBA")
        self.d = ImageDraw.Draw(self.im)

    def outline(self, c=OUTLINE, diag=False):
        a = self.arr()
        sol = a[:, :, 3] == 255
        add = np.zeros_like(sol)
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if diag:
            dirs += [(-1, -1), (1, -1), (-1, 1), (1, 1)]
        for dx, dy in dirs:
            add |= shift(sol, dx, dy)
        add &= ~sol
        a[add] = rgb(c)
        self.set_arr(a)
        return self

    def copy(self):
        c = Cv(self.w, self.h)
        c.im = self.im.copy()
        c.d = ImageDraw.Draw(c.im)
        return c

    def flip(self):
        c = Cv(self.w, self.h)
        c.im = self.im.transpose(Image.FLIP_LEFT_RIGHT)
        c.d = ImageDraw.Draw(c.im)
        return c

    def crop(self, x, y, w, h):
        c = Cv(w, h)
        c.im = self.im.crop((x, y, x + w, y + h))
        c.d = ImageDraw.Draw(c.im)
        return c


def shift(m, dx, dy):
    """Desloca a máscara m por (dx, dy) (o vizinho em (x-dx, y-dy) vem pra (x, y))."""
    h, w = m.shape
    out = np.zeros_like(m)
    ys = slice(max(-dy, 0), h + min(-dy, 0))
    yd = slice(max(dy, 0), h + min(dy, 0))
    xs = slice(max(-dx, 0), w + min(-dx, 0))
    xd = slice(max(dx, 0), w + min(dx, 0))
    out[yd, xd] = m[ys, xs]
    return out


def part(cv, draw, outline=True, diag=False):
    """Desenha uma peça numa camada própria, contorna e cola (a peça da frente separa a de trás)."""
    tmp = Cv(cv.w, cv.h)
    draw(tmp)
    if outline:
        tmp.outline(diag=diag)
    cv.paste(tmp)


def bands(field, ramp, x0=0, y0=0, dither=0.5):
    """Quantiza um campo [0..1] (0 = escuro) na rampa (escuro→claro). dither = largura da transição em faixas.
    Devolve um array HxWx4."""
    n = len(ramp)
    h, w = field.shape
    yy, xx = np.mgrid[0:h, 0:w]
    b = BAYER4[(yy + y0) % 4, (xx + x0) % 4]
    v = np.clip(field, 0, 1) * (n - 1)
    lo = np.floor(v)
    frac = v - lo
    # só dithera perto da fronteira: frac em [0.5 - d/2, 0.5 + d/2] vira mistura ordenada
    if dither > 0:
        t = np.clip((frac - (0.5 - dither / 2)) / dither, 0, 1)
        idx = lo + (t > b)
    else:
        idx = np.round(v)
    idx = np.clip(idx, 0, n - 1).astype(int)
    cols = np.array([rgb(c) for c in ramp], np.uint8)
    return cols[idx]


def fill_mask(cv, mask, arr):
    a = cv.arr()
    a[mask] = arr[mask]
    cv.set_arr(a)


def relight(cv, tint=(1, 1, 1), add=(0, 0, 0)):
    """Troca de iluminação por cena: multiplica as cores (mapa discreto de cor → cor; não cria AA)."""
    a = cv.arr().astype(float)
    o = rgb(OUTLINE)
    m = (a[:, :, 3] > 0) & ~((a[:, :, 0] == o[0]) & (a[:, :, 1] == o[1]) & (a[:, :, 2] == o[2]))
    for i in range(3):
        a[:, :, i][m] = np.clip(a[:, :, i][m] * tint[i] + add[i], 0, 255)
    out = cv.copy()
    out.set_arr(np.round(a))
    return out


def rim(cv, d, col, depth=1, skip=(OUTLINE,), only=None):
    """Luz de recorte: pinta com `col` os pixels do corpo que têm o contorno/vazio na direção d=(dx,dy) da luz.
    `only`: máscara opcional limitando onde a luz bate."""
    a = cv.arr()
    sol = a[:, :, 3] == 255
    skipm = np.zeros_like(sol)
    for s in skip:
        r = rgb(s)
        skipm |= (a[:, :, 0] == r[0]) & (a[:, :, 1] == r[1]) & (a[:, :, 2] == r[2])
    body = sol & ~skipm
    hit = np.zeros_like(sol)
    edge = body.copy()
    for k in range(1, depth + 1):
        nb = shift(body, -d[0] * k, -d[1] * k)  # vizinho na direção da luz é corpo?
        hit |= body & ~nb
    if only is not None:
        hit &= only
    a[hit] = rgb(col)
    out = cv.copy()
    out.set_arr(a)
    return out


def ring_mask(w, h, cx, cy, r):
    yy, xx = np.mgrid[0:h, 0:w]
    return (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 <= r * r


def hash2(x, y, s=0):
    """Hash inteiro determinístico em [0,1)."""
    n = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65536.0


def vnoise(w, h, scale, seed=0, x0=0, y0=0):
    """Value noise suave (bilinear) determinístico."""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    fx, fy = (xx + x0) / scale, (yy + y0) / scale
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    hv = np.vectorize(lambda a, b: hash2(int(a), int(b), seed))
    g00, g10 = hv(ix, iy), hv(ix + 1, iy)
    g01, g11 = hv(ix, iy + 1), hv(ix + 1, iy + 1)
    return (g00 * (1 - tx) + g10 * tx) * (1 - ty) + (g01 * (1 - tx) + g11 * tx) * ty


def fbm(w, h, scale, seed=0, oct=3, x0=0, y0=0):
    out = np.zeros((h, w))
    amp, tot = 1.0, 0.0
    for o in range(oct):
        out += amp * vnoise(w, h, scale / (2 ** o), seed + o * 17, x0, y0)
        tot += amp
        amp *= 0.5
    return out / tot


def strip(frames):
    w, h = frames[0].w, frames[0].h
    s = Cv(w * len(frames), h)
    for i, f in enumerate(frames):
        s.paste(f, i * w, 0)
    return s


def check_pixel_art(img: Image.Image):
    a = np.array(img.convert("RGBA"))
    al = np.unique(a[:, :, 3])
    return set(al.tolist()) <= {0, 255}


def rim_mix(cv, d, light, t=0.5, depth=1, only=None, skip=(OUTLINE,)):
    """Luz de recorte que mistura a cor original com a da luz (mantém o volume das faixas)."""
    a = cv.arr()
    sol = a[:, :, 3] == 255
    skipm = np.zeros_like(sol)
    for s in skip:
        r = rgb(s)
        skipm |= (a[:, :, 0] == r[0]) & (a[:, :, 1] == r[1]) & (a[:, :, 2] == r[2])
    body = sol & ~skipm
    hit = np.zeros_like(sol)
    for k in range(1, depth + 1):
        hit |= body & ~shift(body, -d[0] * k, -d[1] * k)
    if only is not None:
        hit &= only
    L = np.array(rgb(light)[:3], float)
    a = a.astype(float)
    a[hit, :3] = np.round(a[hit, :3] + (L - a[hit, :3]) * t)
    out = cv.copy()
    out.set_arr(a)
    return out


def light_bands(cv, lights, x0=0, y0=0, levels=(0.16, 0.32, 0.5), dither=True, mask=None, dw=0.3):
    """Luz em faixas: cada luz = (cx, cy, rx, ry, cor, força). Soma as luzes, quantiza em len(levels) faixas
    (com dither Bayer só na borda da faixa) e mistura a cor do pixel com a cor da luz mais forte naquele ponto."""
    a = cv.arr().astype(float)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    tot = np.zeros((h, w))
    best = np.zeros((h, w))
    bestc = np.zeros((h, w, 3))
    for (cx, cy, rx, ry, col, k) in lights:
        dd = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
        v = np.clip(1 - dd, 0, 1) * k
        tot += v
        sel = v > best
        best[sel] = v[sel]
        bestc[sel] = np.array(rgb(col)[:3], float)
    n = len(levels)
    bb = BAYER4[(yy.astype(int) + y0) % 4, (xx.astype(int) + x0) % 4] if dither else 0.5
    # nível contínuo 0..n; dither só nos 30% de perto da troca de faixa
    v = np.clip(tot, 0, 1) * n
    lo = np.floor(v)
    fr = v - lo
    t = np.clip((fr - (1 - dw)) / dw, 0, 1)
    lvl = np.clip(lo + (t > bb), 0, n).astype(int)
    f = np.array((0.0,) + tuple(levels))[lvl]
    m = (a[:, :, 3] > 0) & (lvl > 0)
    if mask is not None:
        m &= mask
    a[m, :3] = np.round(a[m, :3] + (bestc[m] - a[m, :3]) * f[m, None])
    out = cv.copy()
    out.set_arr(a)
    return out
