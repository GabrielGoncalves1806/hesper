#!/usr/bin/env python3
"""v0.5 Marco 3 · item 2 · Arte da faixa gelada (neve azul + minério de gelo cristalino).
PROPOSTA: nada daqui vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_m3_gelo.py          gera os pendentes e chama o v05_m3_gelo_report.py

O que sai em reports/design/v05_m3_gelo/pendentes/ (mesmos nomes, tamanhos e âncoras do contrato):
    regions/ground_frost.png             512×512  PNG indexado (paleta do Árido embutida): neve com montes de vento,
                                                  sastrugi, gelo azul polido e cintilado. SEM rachadura nenhuma
    regions/decal_snowbank_{0..2}.png    grande   NOVO · camada de neve fofa (degrau de neve com borda iluminada)
    regions/decal_sastrugi_{0..2}.png    médio    NOVO · ondinhas do vento na neve
    regions/decal_glaze_{0..2}.png       médio    NOVO · gelo azul polido pelo vento (no Verde vira poça de degelo)
    regions/decal_snowdrift_{0..2}.png   pequeno  NOVO · montinho de neve com sombra azul
    regions/decal_sparkle_{0..3}.png     miúdo    NOVO · cintilado (estrelinhas de luz na neve)
    regions/regions_palettes.json        o JSON inteiro do jogo com: rampas BASE.frost novas (4 estágios), mistura de
                                         decalques da faixa gelada trocada e as entradas dos arquivos novos
    ore_ice.png 32×32 · vein_ice.png 64×64 · icon_ice.png 16×16 · pickup_ice.png 16×16 · rock_small_ice_{0,1}.png 32×32
                                         MESMA silhueta (alpha idêntico ao de hoje), pintados como cristal facetado

Índices da rampa BASE (iguais aos das outras regiões): 0 fenda · 1 sombra · 2 escuro · 3 base · 4 claro · 5 brilho ·
6 acento (aqui: gelo azul / água de degelo) · 7 acento 2 (aqui: cintilado). 8 contorno, 9 sombra (não usados no chão).
Determinístico: só hash e Random/rng com seed fixa.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import ores_raw as O  # noqa: E402
import regions_core as R  # noqa: E402
from regions_core import grid, hash2  # noqa: E402

OUT = ROOT / "reports" / "design" / "v05_m3_gelo"
PEND = OUT / "pendentes"
PREG = PEND / "regions"
ASSETS = ROOT / "assets" / "sprites"
REGIONS = ASSETS / "regions"
TEX = 512
STAGES = ("storm", "arid", "mist", "green")

# ---------------------------------------------------------------------------------------------------------------
# RAMPAS · BASE.frost por estágio (0 fenda, 1 sombra, 2 escuro, 3 base, 4 claro, 5 brilho, 6 gelo azul, 7 cintilado)
# ---------------------------------------------------------------------------------------------------------------
FROST_BASE = {
    # Árido: neve seca e fria, azul-neve de verdade; sombra azul saturada, cintilado branco puro
    "arid":  ["#3d4f8a", "#5f7ec0", "#8eaee0", "#b0cbef", "#c8dcf6", "#e4f0ff", "#6fc4ec", "#ffffff"],
    # Tempestade: a mesma neve com poeira ocre assentada (claro amornado), mas a sombra continua azul
    "storm": ["#4a5270", "#6c7896", "#96a2bc", "#b2bccc", "#c8ccd2", "#e0ddd6", "#7fa6c2", "#f6f1e8"],
    # Névoa: neve molhada e encharcada, mais escura e fria; o gelo azul vira neve-papa (slush)
    "mist":  ["#2f3d5a", "#47597e", "#6880a6", "#86a0c4", "#9eb4d2", "#bccde2", "#4a7fae", "#dbe7f4"],
    # Verde: neve velha derretendo (verde-água pálido); o gelo azul vira poça de degelo; a grama do jogo brota por cima
    "green": ["#2f4c58", "#4a6f7c", "#76a0aa", "#a0c2c8", "#bad6d8", "#d6eae8", "#3f8494", "#eef8f4"],
}


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ramp_rgb(stage):
    """10×3: rampa + contorno + sombra (mesma convenção do regions_core.ramp)."""
    return np.array([rgb(c) for c in FROST_BASE[stage]] + [R.OUTLINE, (0, 0, 0)], np.uint8)


# ---------------------------------------------------------------------------------------------------------------
# Ruído que emenda (anisotrópico: célula diferente em x e em y, período inteiro nos dois)
# ---------------------------------------------------------------------------------------------------------------
def pvn(xs, ys, cx, cy, seed):
    px, py = TEX // cx, TEX // cy
    fx, fy = xs / cx, ys / cy
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = R._smooth(fx - ix), R._smooth(fy - iy)

    def L(a, b):
        return hash2(a % px, b % py, seed)

    a, b, c, d = L(ix, iy), L(ix + 1, iy), L(ix, iy + 1), L(ix + 1, iy + 1)
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty


def pfbm(xs, ys, cx, cy, seed, octaves=3):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * pvn(xs, ys, cx >> o, cy >> o, seed + 101 * o)
        norm += amp
        amp *= 0.5
    return tot / norm


def majority(idx, keep=(7,), it=1):
    """Limpa pixel solto na borda das faixas (cada px vira o valor que aparece 5+ vezes na vizinhança 3×3, com
    emenda). Os índices de `keep` (cintilado) não são tocados."""
    for _ in range(it):
        out = idx.copy()
        stack = np.stack([np.roll(np.roll(idx, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        for v in np.unique(idx):
            cnt = (stack == v).sum(0)
            out[(cnt >= 5) & ~np.isin(idx, keep)] = v
        idx = out
    return idx


# ---------------------------------------------------------------------------------------------------------------
# CHÃO · ground_frost 512×512 (emenda nos 4 lados)
# ---------------------------------------------------------------------------------------------------------------
def tex_snow(seed=4101):
    xs, ys = grid(TEX, TEX)
    xs = xs.astype(float)
    ys = ys.astype(float)
    # domínio torcido: o vento não sopra reto
    wx = xs + 26 * (pfbm(xs, ys, 128, 128, seed + 1, 2) - 0.5)
    wy = ys + 34 * (pfbm(xs, ys, 128, 128, seed + 2, 2) - 0.5)
    # altura: dunas de neve compridas no sentido do vento + calombos
    h = 0.72 * pfbm(wx % TEX, wy % TEX, 128, 32, seed + 3, 3) + 0.28 * pfbm(xs, ys, 64, 64, seed + 4, 2)
    gx = (np.roll(h, -2, 1) - np.roll(h, 2, 1))
    gy = (np.roll(h, -2, 0) - np.roll(h, 2, 0))
    lit = -(gx * 0.8 + gy * 1.2)                     # luz de cima-esquerda
    s = lit / lit.std()
    idx = np.full((TEX, TEX), 3, np.uint8)
    idx[s > 0.55] = 4
    idx[s > 1.85] = 5
    idx[s < -1.05] = 2
    idx[s < -2.7] = 1
    idx = majority(idx, it=2)

    # sastrugi: campos de ondinhas de vento (crista clara de 1 px com o pé escuro logo abaixo)
    zone = pfbm(xs, ys, 128, 128, seed + 7, 2)
    zq = np.quantile(zone, 0.68)
    ph = (wy + 5 * (pfbm(xs, ys, 32, 32, seed + 8, 1) - 0.5) + 0.18 * wx) % 8
    seg = pfbm(xs, ys, 16, 8, seed + 9, 1) > 0.42
    crest = (zone > zq) & (ph < 1) & seg
    under = np.roll(crest, 1, 0) & ~crest
    idx[crest & (idx >= 3)] = 5
    idx[crest & (idx < 3)] = 4
    idx[under] = np.where(idx[under] >= 4, 3, 2)

    # gelo azul polido (no Verde vira poça de degelo): manchas pequenas, borda de neve clara em cima e escura embaixo
    g = pfbm(xs, ys, 64, 32, seed + 11, 3)
    glaze = g > np.quantile(g, 0.965)
    glaze = majority(glaze.astype(np.uint8), keep=(), it=2).astype(bool)
    top = glaze & ~np.roll(glaze, 1, 0)
    bot = glaze & ~np.roll(glaze, -1, 0)
    idx[glaze] = 6
    sheen = glaze & (((xs + 2 * ys) % 29) < 1) & ~top & ~bot & (pfbm(xs, ys, 8, 8, seed + 12, 1) > 0.6)
    idx[sheen] = 7
    idx[np.roll(glaze, -1, 0) & ~glaze] = 5            # lábio de neve em cima
    idx[bot] = 2
    idx[np.roll(glaze, 1, 0) & ~glaze] = 4             # neve clara logo abaixo

    # textura miúda da neve (grão e covinha) e cintilado
    sp = hash2(xs.astype(np.int64), ys.astype(np.int64), seed + 20)
    flat = idx == 3
    idx[flat & (sp < 0.010)] = 4
    pit = flat & (sp > 0.9965)
    idx[pit] = 2
    below = np.roll(pit, 1, 0)
    idx[below & (idx == 3)] = 4
    bright = (idx == 4) | (idx == 5)
    idx[bright & (hash2(xs.astype(np.int64), ys.astype(np.int64), seed + 21) < 0.0045)] = 7
    # estrelinha de 5 px (rara)
    st = (hash2(xs.astype(np.int64) // 1, ys.astype(np.int64), seed + 22) < 0.00045) & (idx >= 4) & (idx != 6)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        arm = np.roll(np.roll(st, dy, 0), dx, 1)
        idx[arm & (idx != 6)] = 5
    idx[st] = 7
    return idx


# ---------------------------------------------------------------------------------------------------------------
# DECALQUES (rampa BASE.frost; 255 = transparente; nunca 8/9)
# ---------------------------------------------------------------------------------------------------------------
def _sh(a, dy, dx, fill=False):
    out = np.full_like(a, fill)
    h, w = a.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = a[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def _blob(w, h, seed, k=0.9, cell=None):
    xs, ys = grid(w, h)
    ex = (xs - w / 2) / (w / 2)
    ey = (ys - h / 2) / (h / 2)
    n = R.fbm(xs + seed * 37, ys + seed * 11, cell or min(w, h) / 2.5, seed, 3)
    return (1 - (ex * ex + ey * ey)) + k * (n - 0.5) > 0.18


def _clean(m, it=2):
    m = m.astype(np.uint8)
    for _ in range(it):
        cnt = sum(_sh(m, dy, dx, 0) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        m = (cnt >= 5).astype(np.uint8)
    return m.astype(bool)


def _crop(a, pad=1):
    ys, xs = np.nonzero(a != 255)
    out = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return np.pad(out, pad, constant_values=255)


def d_snowbank(seed, w, h):
    """Camada de neve fofa por cima do chão: um degrau baixo, borda de cima iluminada, pé com 1 px de sombra azul."""
    m = _clean(_blob(w, h, seed, 1.1))
    xs, ys = grid(w, h)
    a = np.full((h, w), 255, np.uint8)
    a[m] = 4
    a[m & ~_sh(m, 1, 0)] = 5                                # borda de cima
    a[m & ~_sh(m, 0, 1) & ~_sh(m, -1, 0)] = 5
    a[m & ~_sh(m, -1, 0)] = 3                               # face de baixo do degrau
    shadow = _sh(m, 1, 0) & ~m
    a[m & ~_sh(m, -2, 0) & ~_sh(m, -1, 0)] = 3
    a[shadow] = 2
    a[_sh(m, 2, 1) & ~m & ~shadow] = 2
    sp = hash2(xs, ys, seed + 9)
    a[m & (a == 4) & (sp < 0.006)] = 7
    return _crop(a)


def d_sastrugi(seed, w, h):
    """Ondinhas do vento: cristas curvas e paralelas (1 px claro, pé escuro logo abaixo), quebradas e se perdendo
    nas pontas. Fundo transparente: o chão aparece entre elas."""
    env = _blob(w, h, seed, 1.0)
    xs, ys = grid(w, h)
    a = np.full((h, w), 255, np.uint8)
    lam = 6 + (seed % 3)
    ph = (ys + 3.2 * np.sin(xs / (11 + seed % 5) + seed) + 0.22 * xs + 2.5 * (R.fbm(xs, ys, 18, seed, 2) - 0.5)) % lam
    seg = R.fbm(xs + seed * 5, ys * 3, 9, seed + 1, 2) > 0.40
    crest = env & (ph < 1) & seg
    crest &= _sh(crest, 0, 1) | _sh(crest, 0, -1)          # sem pixel solto
    a[crest] = 5
    lee = _sh(crest, 1, 0) & ~crest & env
    a[lee] = 2
    glow = _sh(crest, -1, 0) & ~crest & ~lee & env & (hash2(xs, ys, seed + 2) < 0.5)
    a[glow] = 4
    a[crest & (hash2(xs, ys, seed + 4) < 0.03)] = 7
    return _crop(a)


def d_glaze(seed, w, h):
    """Gelo azul polido pelo vento (Árido/Tempestade) que vira papa de neve na Névoa e poça de degelo no Verde.
    Liso: sem rachadura. Reflexo em riscos diagonais, lábio de neve em volta."""
    m = _clean(_blob(w, h, seed, 1.25), 3)
    xs, ys = grid(w, h)
    a = np.full((h, w), 255, np.uint8)
    a[m] = 6
    inner = m & _sh(m, 2, 0) & _sh(m, -2, 0) & _sh(m, 0, 2) & _sh(m, 0, -2)
    streak = inner & (((xs + 2 * ys) % 23) < 1) & (R.fbm(xs, ys, 6, seed + 3, 1) > 0.62)
    a[streak] = 7
    a[_sh(m, -1, 0) & ~m] = 5                              # lábio de neve em cima
    a[_sh(m, 0, -1) & ~m & ~_sh(m, -1, 0)] = 5
    a[m & ~_sh(m, -1, 0)] = 2                              # borda de baixo do gelo
    a[_sh(m, 1, 0) & ~m] = 4                               # neve clara logo abaixo
    return _crop(a)


def d_snowdrift(seed, w, h):
    """Montinho de neve (amontoado pelo vento): cúpula com topo claro, lado de baixo-direita azul e uma meia-lua de
    sombra no chão. Volume desenhado no próprio decalque (é chão: não colide)."""
    xs, ys = grid(w, h)
    cx, cy = w * 0.44, h * 0.46
    rx, ry = w * 0.40, h * 0.36
    n = R.fbm(xs + seed * 23, ys + seed * 19, 6, seed, 2) - 0.5
    ex, ey = (xs - cx) / rx, (ys - cy) / ry
    d = ex * ex + ey * ey + 0.45 * n
    m = _clean(d < 1.0, 1)
    t = 0.55 * ex + ey                                   # lado que pega luz (cima-esquerda) × lado da sombra
    a = np.full((h, w), 255, np.uint8)
    a[m] = 4
    a[m & (t < -0.35) & (d < 0.75)] = 5
    a[m & (t > 0.45)] = 3
    a[m & (t > 0.95)] = 2
    a[m & ~_sh(m, 1, 0)] = 5                             # crista de cima
    a[m & ~_sh(m, -1, 0)] = 2                            # pé
    sh = (_sh(m, 1, 2) | _sh(m, 2, 3) | _sh(m, 1, 3)) & ~m
    a[sh] = 2
    pk = [(x, y) for y, x in zip(*np.nonzero(m & (a == 5)))]
    if pk:
        x, y = sorted(pk, key=lambda p: (p[0] + p[1], p[1]))[len(pk) // 2]
        a[y, x] = 7
    return _crop(a)


def d_sparkle(seed, w=30, h=20):
    """Cintilado: 2–3 estrelinhas de 5 px e uns pontos soltos de luz."""
    rng = np.random.default_rng(seed)
    a = np.full((h, w), 255, np.uint8)
    for _ in range(int(rng.integers(2, 4))):
        x, y = int(rng.integers(2, w - 2)), int(rng.integers(2, h - 2))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a[y + dy, x + dx] = 5
        a[y, x] = 7
    for _ in range(int(rng.integers(3, 6))):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        if a[y, x] == 255:
            a[y, x] = 7
    return _crop(a, 0)


def decal_set():
    out = {}
    for v in range(3):
        out[f"snowbank_{v}"] = d_snowbank(4200 + v, (168, 132, 196)[v], (78, 64, 92)[v])
        out[f"sastrugi_{v}"] = d_sastrugi(4210 + v, (124, 100, 148)[v], (60, 50, 70)[v])
        out[f"glaze_{v}"] = d_glaze(4220 + v, (84, 64, 104)[v], (40, 32, 48)[v])
        out[f"snowdrift_{v}"] = d_snowdrift(4230 + v, (40, 30, 52)[v], (24, 18, 30)[v])
    for v in range(4):
        out[f"sparkle_{v}"] = d_sparkle(4240 + v)
    return out


# ---------------------------------------------------------------------------------------------------------------
# MINÉRIO DE GELO · mesma silhueta, pintado como cristal facetado (luz de cima-esquerda)
# ---------------------------------------------------------------------------------------------------------------
GEM = {                   # v1.1: um tom mais claro e translúcido (a v1.0 puxava pra safira)
    "white": "#f2fcff",   # brilho / aresta
    "hi":    "#c4ecfd",   # faceta de cima (a que pega luz)
    "lt":    "#a0dcf8",   # faceta da esquerda
    "md":    "#6cbcee",   # faceta da direita
    "dk":    "#3a82d0",   # faceta de baixo
    "deep":  "#1e4593",   # fundo / encaixe na rocha / pé da face
}
# placas do veio: gelo mais calmo que a pepita (a pepita tem que saltar)
PLATE = {"hi": "#e6f6ff", "lt": "#c2e5fa", "md": "#9fcff2", "dk": "#78ade4", "deep": "#4f80c6"}


def facet_of(nx, ny, table=None):
    """Faceta de um px pelo vetor normalizado a partir do centro da peça (pirâmide de 4 faces + mesa)."""
    if table is not None and abs(nx) < table and abs(ny) < table:
        return "hi"
    cand = [(-ny, "hi"), (-nx, "lt"), (nx, "md"), (ny, "dk")]
    best = max(c[0] for c in cand)
    for val, name in cand:                  # desempate na ordem: cima, esquerda, direita, baixo
        if val >= best - 1e-9:
            return name


def gem_paint(cv, pts, pal=GEM, socket=True, glint=True, table=None, light=False):
    """light (v1.1): pepita de gelo clara, a faceta de baixo fica no azul médio e o fundo escuro só no encaixe."""
    pts = set(pts)
    if not pts:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ex, ey = max(0.5, (max(xs) - min(xs)) / 2), max(0.5, (max(ys) - min(ys)) / 2)
    if socket:
        for (px, py) in pts:
            for (dx, dy) in ((1, 0), (0, 1), (1, 1)):
                q = (px + dx, py + dy)
                if q not in pts and cv.solid(*q) is not None:
                    cv.px(q[0], q[1], pal["deep"])
    for (px, py) in pts:
        f = facet_of((px - cx) / ex, (py - cy) / ey, table)
        if light:
            f = {"dk": "md", "md": "lt", "lt": "hi", "hi": "hi"}[f]
        cv.px(px, py, pal[f])
    if glint:
        gx, gy = min(pts, key=lambda p: (p[0] + p[1], p[1]))
        cv.px(gx, gy, GEM["white"])


def shape_pts(x, y, shape):
    return [(x + i, y + j) for j, row in enumerate(shape) for i, ch in enumerate(row) if ch == "#"]


def ore_ice():
    """Overlay da parede: as MESMAS pintas do ore_ice de hoje (posição e forma), cada uma lapidada."""
    cv = O.Canvas(32, 32)
    for (x, y, s, big) in O.ORE_SPOTS["ice"]:
        shp = O.BIG[s] if big else O.SPECKS[s]
        gem_paint(cv, shape_pts(x, y, shp), table=0.3 if big else None, light=True)
    return cv


def raw_ice(size=16, scale=1.0):
    """icon/pickup: a mesma pilha de calombos do raw('ice') de hoje (mesma máscara), cada calombo uma pirâmide
    facetada (4 faces + mesa), arestas de baixo-direita no azul fundo, contorno."""
    cv = O.Canvas(size, size)
    off = (size - 16 * scale) / 2
    yy, xx = np.mgrid[0:size, 0:size]
    for k, (cx, cy, r) in enumerate(O.RAW_BUMPS["ice"]):
        cx, cy, r = cx * scale + off, cy * scale + off, r * scale
        dx, dy = xx + 0.5 - cx, yy + 0.5 - cy
        d = (np.maximum(abs(dx), abs(dy)) * 0.75 + (abs(dx) + abs(dy)) * 0.3) / r
        inside = d <= 1
        for y, x in zip(*np.nonzero(inside)):
            nx, ny = dx[y, x] / r, dy[y, x] / r
            f = facet_of(nx, ny)
            if d[y, x] > 0.85 and (nx + ny) > 0.35:
                f = "deep"
            cv.px(x, y, GEM[f])
        # brilho na ponta de cima-esquerda da mesa de cada calombo
        gx, gy = int(cx - r * 0.35), int(cy - r * 0.45)
        if 0 <= gx < size and 0 <= gy < size and inside[gy, gx]:
            cv.px(gx, gy, GEM["white"])
    cv.outline()
    return cv


def _rock_base(v):
    """A rocha da rock_small_ice_v de hoje sem as linhas do veio (o mesmo código do ores_raw.rock_vein) e as
    máscaras da pedrinha (tampo e face)."""
    d = O.ROCK_VARS[v]
    w = h = 32
    cx, cy, rx, ry, seed, wob = d["top"]
    top = O.lump_mask(w, h, cx, cy, rx, ry, seed, wob=wob)
    yy, xx = np.mgrid[0:h, 0:w]
    fac = top & ((xx - cx) * 0.8 + (yy - cy) * 1.4 > 2)
    cv = O.Canvas(w, h)
    cv.blit(O.extrude(top, 6, O.ROCK[0], O.ROCK[1], O.ROCK[2], O.ROCK[3], glint=False, facets=fac), 0, 0)
    px_, py_, prx, pry, ps = d["peb"]
    ptop = O.lump_mask(w, h, px_, py_, prx, pry, ps)
    peb = O.extrude(ptop, 2, O.ROCK[0], O.ROCK[1], O.ROCK[2], O.ROCK[3], glint=False)
    cv.blit(peb, 0, 0)
    pebpx = (peb.a[:, :, 3] == 255) & ~(peb.a[:, :, :3] == np.array(rgb(O.OUTLINE), np.uint8)).all(2)
    return cv, top, ptop, pebpx


# pepitas de cristal cravadas na rocha (x, y, forma do ores_raw.BIG/SPECKS, grande?) por variação
ROCK_GEMS = {
    0: [(8, 13, 0, 1), (14, 18, 3, 1), (18, 12, 2, 1), (23, 16, 4, 0)],
    1: [(8, 15, 2, 1), (13, 12, 0, 1), (19, 13, 3, 1), (21, 19, 1, 0)],
}


def rock_small_ice(v):
    cv, top, ptop, pebpx = _rock_base(v)
    inner = O._solid_noline(cv)
    for (x, y, s, big) in ROCK_GEMS[v]:
        pts = [p for p in shape_pts(x, y, O.BIG[s] if big else O.SPECKS[s]) if inner[p[1], p[0]] and not pebpx[p[1], p[0]]]
        gem_paint(cv, pts, table=0.3 if big else None)
    # a pedrinha do lado vira um cubo de gelo (tampo facetado + face azul)
    ys, xs = np.nonzero(pebpx)
    tops = [(x, y) for y, x in zip(ys, xs) if ptop[y, x]]
    fronts = [(x, y) for y, x in zip(ys, xs) if not ptop[y, x]]
    gem_paint(cv, tops, socket=False, glint=True)
    if fronts:
        fx0, fx1 = min(p[0] for p in fronts), max(p[0] for p in fronts)
        for (x, y) in fronts:
            cv.px(x, y, GEM["dk"] if (x - fx0) / max(1, fx1 - fx0) < 0.6 else GEM["deep"])
    # o contorno escuro em volta do pé continua o da rocha (não mexe na silhueta)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# v1.1 · rocha pequena de gelo = BLOCO DE GELO (feedback do dono: a v1.0 lia "pedra marrom com safira")
# Mesma silhueta (tampo + face de 6 px + pedrinha). Tampo claro e translúcido, lapidado em facetas com aresta
# branca; face funda em faixas de azul; miolo azul profundo aparecendo por baixo da superfície; bolhas presas.
# Estilos pro dono escolher: "A" lapidado · "B" translúcido com bolhas · "C" com um caco de pedra preso dentro.
# ---------------------------------------------------------------------------------------------------------------
ICEB = {
    "rim":   "#f2fcff",   # aresta / brilho
    "t1":    "#c4ecfd",   # faceta clara do tampo
    "t2":    "#97d6f7",   # faceta média do tampo
    "t3":    "#6cbcee",   # chanfro / faceta em sombra
    "core":  "#4a98de",   # miolo fundo visto através do gelo
    "f1":    "#5aa8e6",   # face: logo abaixo da aresta
    "f2":    "#3a82d0",
    "f3":    "#2a63b8",
    "f4":    "#1e4593",   # pé da face
    "glow":  "#86cdf4",   # luz refratada na face
}
ROCK_STYLE = "A"          # o escolhido vai pro pendente; os 3 vão pro report


def rock_ice_block(v, style="A"):
    cv, top, ptop, pebpx = _rock_base(v)
    inner = O._solid_noline(cv)
    body_top = top & inner & ~pebpx
    body = inner & ~pebpx
    front = body & ~body_top
    d = O.ROCK_VARS[v]
    cx, cy, rx, ry = d["top"][:4]
    ys, xs = np.nonzero(body_top)
    # --- tampo
    ox, oy = cx - rx * 0.12, cy - ry * 0.25            # vértice das facetas (A): um tico pra cima-esquerda
    bounds = (-2.55, -1.05, 0.35, 1.75)                # arestas (rad): 4 facetas em volta do vértice
    tone = ("t1", "t2", "t3", "t3", "t1")              # esquerda, cima, direita, baixo-dir, baixo-esq
    for y, x in zip(ys, xs):
        u, w = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
        if style == "A":
            a = math.atan2((y + 0.5 - oy) / ry, (x + 0.5 - ox) / rx)
            k = sum(a > b for b in bounds)
            c = ICEB[tone[k]]
            if k == 1 and w < -0.35:
                c = ICEB["t1"]                         # faceta de cima pega luz
        else:
            c = ICEB["t1"] if (u + w) < -0.2 else ICEB["t2"]
            if w > 0.55:
                c = ICEB["t3"]
        cv.px(x, y, c)
    if style == "A":                                   # arestas brancas de 1 px (só as que pegam luz)
        for b in bounds[:3]:
            for t in np.linspace(0.15, 1.6, 40):
                x = int(ox + math.cos(b) * rx * t)
                y = int(oy + math.sin(b) * ry * t)
                if 0 <= x < 32 and 0 <= y < 32 and body_top[y, x] and (b < 0 or t < 0.9):
                    cv.px(x, y, ICEB["rim"] if b < 0 else ICEB["t1"])
    else:                                              # B e C: miolo fundo visto através do gelo, irregular
        for y, x in zip(ys, xs):
            u, w = (x + 0.5 - cx - rx * 0.15) / rx, (y + 0.5 - cy - ry * 0.25) / ry
            wob = 0.18 * math.sin(x * 1.3 + y * 0.7)
            if u * u / 0.28 + w * w / 0.16 < 1 + wob:
                cv.px(x, y, ICEB["t3"])
                if u * u / 0.10 + w * w / 0.06 < 1:
                    cv.px(x, y, ICEB["core"])
    for y, x in zip(ys, xs):                     # borda de cima e da esquerda = brilho
        up = not body_top[y - 1, x]
        lf = not body_top[y, x - 1]
        if up or (lf and y < cy):
            cv.px(x, y, ICEB["rim"] if up else ICEB["t1"])
    # --- face: faixas por profundidade + aresta clara + luz refratada
    for x in range(32):
        col = np.nonzero(front[:, x])[0]
        if len(col) == 0:
            continue
        y0c, y1c = col.min(), col.max()
        u = (x + 0.5 - cx) / rx
        for y in col:
            k = y - y0c
            c = ICEB["f1"] if k == 0 else ICEB["f2"] if k <= 2 else ICEB["f3"]
            if y == y1c:
                c = ICEB["f4"]
            if u > 0.45 and k > 0:               # lado direito da face, mais fundo
                c = ICEB["f3"] if c == ICEB["f2"] else ICEB["f4"]
            cv.px(x, y, c)
        if int(x) % 7 == 3 and u < 0.4:          # luz refratada: risquinho vertical claro
            for y in col[1:3]:
                cv.px(x, y, ICEB["glow"])
    # --- bolhas presas
    bub = {0: [(12, 15), (18, 18), (9, 21), (21, 23)], 1: [(13, 14), (20, 17), (11, 23), (18, 24)]}[v]
    nb = 2 if style == "A" else 4
    for (x, y) in bub[:nb]:
        if body[y, x] and body[y + 1, x + 1]:
            cv.px(x, y, ICEB["rim"])
            if style != "A":
                cv.px(x + 1, y + 1, ICEB["t1"] if body_top[y + 1, x + 1] else ICEB["glow"])
    # --- C: caco de pedra escura preso no miolo (visto através do gelo: aro azul fundo)
    if style == "C":
        px0, py0 = int(cx + rx * 0.08), int(cy + ry * 0.12)
        shard = [(0, 0), (1, 0), (0, 1), (1, 1), (2, 1)]
        for (dx, dy) in shard:
            x, y = px0 + dx, py0 + dy
            if body[y, x]:
                cv.px(x, y, O.ROCK[2] if dy == 0 else O.ROCK[3])
        cv.px(px0, py0, O.ROCK[1])
    # --- pedrinha: cubo de gelo (como na v1.0, nas cores do bloco)
    pys, pxs = np.nonzero(pebpx)
    tops = [(x, y) for y, x in zip(pys, pxs) if ptop[y, x]]
    fronts = [(x, y) for y, x in zip(pys, pxs) if not ptop[y, x]]
    for (x, y) in tops:
        cv.px(x, y, ICEB["t2"])
    if tops:
        ty0 = min(p[1] for p in tops)
        for (x, y) in tops:
            if y == ty0:
                cv.px(x, y, ICEB["rim"])
        tx1 = max(p[0] for p in tops)
        for (x, y) in tops:
            if x == tx1 and y > ty0:
                cv.px(x, y, ICEB["t3"])
    if fronts:
        fx0, fx1 = min(p[0] for p in fronts), max(p[0] for p in fronts)
        for (x, y) in fronts:
            cv.px(x, y, ICEB["f2"] if (x - fx0) / max(1, fx1 - fx0) < 0.6 else ICEB["f4"])
    return cv


# pepitas do veio: um tico maiores que as da parede (o veio tem que ler de longe sobre a placa clara)
VEIN_GEMS = [
    [".####.", "######", "######", ".####."],
    ["..##..", ".####.", "######", ".####.", "..##.."],
    [".###.", "#####", "#####", ".###."],
    [".##..", "####.", "#####", ".####", "..##."],
]


def vein_ice():
    """Veio 2×2: as MESMAS lajes do vein_ice de hoje (mesmos polígonos, mesma extrusão de 3 px), agora placas de
    gelo com uma aresta de cristal cruzando cada uma (2 facetas), e pepitas lapidadas por cima. Sem rachadura."""
    rnd = random.Random(7 * 131)
    slabs = [(17, 20, 17, 7), (43, 18, 15, 6), (14, 42, 14, 7), (35, 38, 19, 8), (54, 45, 10, 6), (26, 55, 13, 6),
             (52, 28, 9, 6)]
    items = [(cy, O.poly_slab(rnd, cx, cy, r, n), (cx, cy, r)) for (cx, cy, r, n) in slabs]
    cv = O.Canvas(64, 64)
    for k, (_cy, top, (cx, cy, r)) in enumerate(sorted(items, key=lambda i: i[0])):
        part = O.Canvas(64, 64)
        front = np.zeros_like(top)
        for s in range(1, 4):
            front |= O._shift(top, 0, s)
        front &= ~top
        ys, xs = np.nonzero(top | front)
        x0, x1 = xs.min(), xs.max()
        for y, x in zip(*np.nonzero(front)):
            u = (x - x0) / max(1, x1 - x0)
            below = y + 1 >= 64 or not front[y + 1, x]
            part.px(x, y, PLATE["deep"] if (u > 0.62 or below) else PLATE["dk"])
        # aresta do cristal: uma linha inclinada que divide o tampo em faceta clara (cima-esq) e média (baixo-dir)
        ang = (-0.55, 0.35, -0.25, 0.5, -0.4, 0.2, -0.6)[k % 7]
        for y, x in zip(*np.nonzero(top)):
            up = y == 0 or not top[y - 1, x]
            lf = x == 0 or not top[y, x - 1]
            rt = x == 63 or not top[y, x + 1]
            dn = y == 63 or not top[y + 1, x]
            side = (x - cx) * math.sin(ang) + (y - cy) * 1.6 * math.cos(ang)
            if up or (lf and not rt):
                c = PLATE["hi"]
            elif side < -0.6:
                c = PLATE["lt"]
            elif side < 0.6:
                c = GEM["white"]                  # a aresta pega luz
            elif rt or dn:
                c = PLATE["dk"]
            else:
                c = PLATE["md"]
            part.px(x, y, c)
        # reflexo de vidro: 2 riscos curtos paralelos no lado claro
        for y, x in zip(*np.nonzero(top)):
            side = (x - cx) * math.sin(ang) + (y - cy) * 1.6 * math.cos(ang)
            if -4.5 < side < -3.2 and (x + y) % 5 < 2 and abs(x - cx) < r * 0.5:
                part.px(x, y, GEM["white"])
        part.outline()
        cv.blit(part, 0, 0)
    allowed = O._solid_noline(cv)
    spots = [(9, 15, 0), (21, 12, 1), (35, 12, 0), (46, 15, 2), (15, 22, 3), (27, 19, 2),
             (8, 37, 1), (18, 41, 0), (30, 33, 2), (39, 38, 0), (46, 33, 3), (51, 42, 1), (22, 50, 2), (31, 50, 3),
             (53, 25, 3)]
    for (x, y, s) in spots:
        pts = [p for p in shape_pts(x, y, VEIN_GEMS[s]) if 0 <= p[0] < 64 and 0 <= p[1] < 64 and allowed[p[1], p[0]]]
        if len(pts) >= 8:
            gem_paint(cv, pts, table=0.3, light=True)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# ROCHAS COM NEVE (referência do dono: pedra cinza-azulada com capa de neve em cima e nas bordas de cima; sem verde)
# ---------------------------------------------------------------------------------------------------------------
# HILL.frost novo. Os índices continuam os do hill_top/hill_face: 0..2 pedra, 3..5 neve (3 sombra azul, 4 neve,
# 5 brilho), 6 e 7 acentos (iguais aos de hoje). No hill_top o 3/4/5 cobrem ~90% (vira campo de neve com a pedra
# aparecendo nas fendas e nos afloramentos) e na hill_face as linhas 0..1 (4) e 2..7 (3) viram a capa de neve que
# escorre da borda de cima. Nenhum estágio puxa pro verde: a pedra é cinza-azulada nos 4.
FROST_HILL = {
    "arid":  ["#2c3548", "#46536c", "#7d8ea8", "#9fb8de", "#d0e1f6", "#f2f8ff", "#62bede", "#c6f3ff"],
    "storm": ["#32333f", "#4b4d5e", "#7a7d8c", "#a8b0c0", "#d2d2d4", "#ece8e0", "#7ca7ad", "#bac9c2"],
    "mist":  ["#232b3b", "#384459", "#5f6e86", "#7e96b8", "#a8bcd6", "#cbd9ea", "#588396", "#80a7b4"],
    "green": ["#27313e", "#3c4a5a", "#667888", "#90acbe", "#bcd2dc", "#e0eef0", "#518b95", "#7eacae"],
}


def hill_rgb(stage):
    return np.array([rgb(c) for c in FROST_HILL[stage]] + [R.OUTLINE, (0, 0, 0)], np.uint8)


def _poly(w, h, cx, cy, r, n, rnd, squash=0.62):
    a0 = rnd.uniform(0, 6.3)
    pts = []
    for i in range(n):
        a = a0 + (i + rnd.uniform(-0.25, 0.25)) * 2 * math.pi / n
        rr = r * rnd.uniform(0.75, 1.1)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * squash))
    return O.poly_mask(w, h, pts)


def _outline_idx(a):
    sol = a != 255
    ring = np.zeros_like(sol)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= _sh(sol, dy, dx)
    a[ring & ~sol] = 8


def snow_slab(a, top, thick, seed, cover=0.75):
    """Pinta 1 laje (tampo `top` + face de `thick` px) em `a` (índices HILL.frost), com capa de neve no tampo e
    escorrendo um tico na face. Contorno 8 em volta da laje (separa das de trás)."""
    h, w = a.shape
    front = np.zeros_like(top)
    for k in range(1, thick + 1):
        front |= _sh(top, k, 0)
    front &= ~top
    part = np.full((h, w), 255, np.uint8)
    ys, xs = np.nonzero(top | front)
    x0, x1 = xs.min(), xs.max()
    for y, x in zip(*np.nonzero(front)):
        u = (x - x0) / max(1, x1 - x0)
        below = y + 1 >= h or not front[y + 1, x]
        part[y, x] = 0 if below else (1 if u > 0.58 else 2)
    # neve: a parte de cima do tampo (cada coluna cobre `cover` da altura dela, com ruído de 1 px)
    for x in range(w):
        col = np.nonzero(top[:, x])[0]
        if len(col) == 0:
            continue
        y0c, y1c = col.min(), col.max()
        dep = max(1, int(round((y1c - y0c + 1) * cover + (hash2(x // 2, 0, seed) - 0.5) * 2.2)))
        for y in col:
            if y - y0c < dep:
                part[y, x] = 4
            else:
                part[y, x] = 2 if (x - x0) / max(1, x1 - x0) < 0.6 else 1
        # escorrido de neve na face (1–2 px) em algumas colunas
        if hash2(x, 1, seed) < 0.33 and dep >= y1c - y0c + 1:
            for k in range(1, 1 + int(1 + hash2(x, 2, seed) * 2)):
                if y1c + k < h and front[y1c + k, x]:
                    part[y1c + k, x] = 3
    snow = part == 4
    up = snow & ~_sh(snow, 1, 0)
    lf = snow & ~_sh(snow, 0, 1)
    rt = snow & ~_sh(snow, 0, -1)
    dn = snow & ~_sh(snow, -1, 0)
    part[snow & (up | lf)] = 5
    part[snow & (dn | rt) & ~up] = 3
    _outline_idx(part)
    a[part != 255] = part[part != 255]


def snow_rocks(w, h, slabs, seed, shadow=True):
    """Grupo de pedras com neve, desenhado de trás pra frente. slabs = [(cx, cy, r, n, thick, cover)]."""
    rnd = random.Random(seed)
    a = np.full((h, w), 255, np.uint8)
    tops = [(cy, _poly(w, h, cx, cy, r, n, rnd), th, cov) for (cx, cy, r, n, th, cov) in slabs]
    for k, (_cy, top, th, cov) in enumerate(sorted(tops, key=lambda t: t[0])):
        snow_slab(a, top, th, seed + k * 17, cov)
    if shadow:                                   # sombra no chão (9, alfa fixo): faixa embaixo-direita do pé
        sol = a != 255
        foot = sol & ~_sh(sol, -1, 0)
        sh = np.zeros_like(sol)
        for dy, dx in ((1, 1), (1, 2), (2, 2), (1, 0)):
            sh |= _sh(foot, dy, dx)
        a[sh & ~sol] = 9
    return a


def fit(a, w, h):
    """Recorta/centraliza o desenho no tamanho exato w×h (âncora = centro da base, como os decor de hoje)."""
    ys, xs = np.nonzero(a != 255)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    out = np.full((h, w), 255, np.uint8)
    hh, ww = min(h, a.shape[0]), min(w, a.shape[1])
    ox = (w - ww) // 2
    out[h - hh:, ox:ox + ww] = a[a.shape[0] - hh:, :ww]
    return out


# decor_rimed_rock_{0..2}: mesmos tamanhos de hoje (27×25, 26×24, 24×23), agora pedra com capa de neve
RIMED = [
    ((27, 25), [(13, 12, 10, 6, 6, 0.8), (21, 18, 5, 5, 3, 0.85)]),
    ((26, 24), [(12, 11, 9, 5, 7, 0.75), (5, 18, 4, 5, 3, 0.9), (19, 17, 5, 6, 3, 0.8)]),
    ((24, 23), [(12, 13, 10, 7, 5, 0.85)]),
]
# decor_snow_slabs_{0..2} (NOVO): a pedra grande de várias lajes da referência, até 32×28 (limite dos soltos)
SLABS = [
    ((32, 28), [(14, 9, 11, 6, 6, 0.8), (22, 15, 8, 5, 5, 0.8), (9, 18, 7, 5, 4, 0.85), (26, 21, 4, 5, 2, 0.9)]),
    ((32, 26), [(12, 10, 10, 5, 6, 0.75), (23, 11, 7, 6, 5, 0.8), (17, 18, 8, 5, 4, 0.85)]),
    ((30, 24), [(15, 10, 11, 6, 5, 0.8), (6, 17, 4, 5, 2, 0.9), (21, 17, 6, 5, 3, 0.85)]),
]


def decor_set():
    out = {}
    for v, ((w, h), sl) in enumerate(RIMED):
        out[f"rimed_rock_{v}"] = fit(snow_rocks(w + 8, h + 8, [(x + 4, y + 3, r, n, t, c) for (x, y, r, n, t, c) in sl],
                                                4300 + v), w, h)
    for v, ((w, h), sl) in enumerate(SLABS):
        out[f"snow_slabs_{v}"] = fit(snow_rocks(w + 8, h + 8, [(x + 4, y + 3, r, n, t, c) for (x, y, r, n, t, c) in sl],
                                                4310 + v), w, h)
    return out


def snowcap(v):
    """Overlay 32×32 (RGBA) da capa de neve por cima de QUALQUER rock_small* da variação v (mesma silhueta das
    rock_small_{minério}_v; o rock_small.png comum é a variação 0). Fica dentro da silhueta (não muda o contorno)."""
    cv, top, ptop, pebpx = _rock_base(v)
    inner = O._solid_noline(cv)
    idx = np.full((32, 32), 255, np.uint8)
    m = top & inner & ~pebpx
    for x in range(32):
        col = np.nonzero(m[:, x])[0]
        if len(col) == 0:
            continue
        y0c, y1c = col.min(), col.max()
        dep = int(round((y1c - y0c + 1) * 0.48 + (hash2(x // 2, v, 4400) - 0.5) * 2.6))
        for y in col:
            if y - y0c < max(1, dep):
                idx[y, x] = 4
    pm = ptop & pebpx                              # a pedrinha ganha um chapeuzinho
    for x in range(32):
        col = np.nonzero(pm[:, x])[0]
        if len(col):
            idx[col.min(), x] = 4
            if len(col) > 2:
                idx[col.min() + 1, x] = 4
    snow = idx == 4
    up = snow & ~_sh(snow, 1, 0)
    lf = snow & ~_sh(snow, 0, 1)
    dn = snow & ~_sh(snow, -1, 0)
    rt = snow & ~_sh(snow, 0, -1)
    idx[snow & (up | lf)] = 5
    idx[snow & (dn | rt) & ~up] = 3
    rgba = np.zeros((32, 32, 4), np.uint8)
    pal = hill_rgb("arid")
    s = idx != 255
    rgba[s, :3] = pal[idx[s]]
    rgba[s, 3] = 255
    cap = O.Canvas(32, 32)
    cap.a = rgba
    return cap


# ---------------------------------------------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------------------------------------------
def save_indexed(idx, path, pal_rgb=None):
    """PNG modo P com a rampa do Árido (o mesmo formato dos outros sprites de região)."""
    im = Image.frombytes("P", (idx.shape[1], idx.shape[0]), np.ascontiguousarray(idx).tobytes())
    pal = [0] * 768
    for i, c in enumerate(ramp_rgb("arid") if pal_rgb is None else pal_rgb):
        pal[i * 3:i * 3 + 3] = [int(v) for v in c]
    im.putpalette(pal)
    trns = bytes([255] * 9 + [R.SHADOW_A] + [255] * (255 - 10) + [0])
    im.save(path, transparency=trns)


def save_rgba(cv, path):
    assert set(np.unique(cv.a[:, :, 3]).tolist()) <= {0, 255}, path
    cv.a[cv.a[:, :, 3] == 0] = 0
    cv.image().save(path)


V8_MIX = [["snowbank", 4], ["sastrugi", 4], ["glaze", 2], ["patch_light", 2]]
V9_MIX = [["snowdrift", 4], ["sparkle", 3]]
V8_P, V9_P = 0.5, 0.45


def patched_json():
    meta = json.loads((REGIONS / "regions_palettes.json").read_text())
    new = copy.deepcopy(meta)
    new["ramps"]["BASE"]["frost"] = {st: list(FROST_BASE[st]) for st in STAGES}
    new["decal_mix"]["frost"] = V8_MIX
    new["decal_p"]["frost"] = V8_P
    new["v9_density"]["decal_mix"]["frost"] = V9_MIX
    new["v9_density"]["decal_p"]["frost"] = V9_P
    new["ramps"]["HILL"]["frost"] = {st: list(FROST_HILL[st]) for st in STAGES}
    new["v9_density"]["decor_p"]["frost"] = V9_DECOR
    return meta, new


V9_DECOR = [["penitentes", 0.010], ["rimed_rock", 0.010], ["snow_slabs", 0.006]]


def ore_contract():
    return {
        "ore_ice.png": (ore_ice(), (32, 32)),
        "vein_ice.png": (vein_ice(), (64, 64)),
        "icon_ice.png": (raw_ice(), (16, 16)),
        "pickup_ice.png": (raw_ice(16, 0.75), (16, 16)),
        "rock_small_ice_0.png": (rock_ice_block(0, ROCK_STYLE), (32, 32)),
        "rock_small_ice_1.png": (rock_ice_block(1, ROCK_STYLE), (32, 32)),
        "rock_small_snowcap_0.png": (snowcap(0), (32, 32)),
        "rock_small_snowcap_1.png": (snowcap(1), (32, 32)),
    }


def build():
    PREG.mkdir(parents=True, exist_ok=True)
    for p in list(PREG.glob("*.png")) + list(PEND.glob("*.png")):
        p.unlink()
    ground = tex_snow()
    assert ground.shape == (TEX, TEX)
    save_indexed(ground, PREG / "ground_frost.png")
    decals = decal_set()
    for name, idx in decals.items():
        assert not np.isin(idx, (8, 9)).any(), name
        save_indexed(idx, PREG / f"decal_{name}.png")
    decors = decor_set()
    for name, idx in decors.items():
        save_indexed(idx, PREG / f"decor_{name}.png", hill_rgb("arid"))
    meta, new = patched_json()
    for name, idx in decals.items():
        new["files"][f"decal_{name}.png"] = {"size": f"{idx.shape[1]}×{idx.shape[0]}", "region": "frost", "ramp": "BASE"}
    for name, idx in decors.items():
        new["files"][f"decor_{name}.png"] = {"size": f"{idx.shape[1]}×{idx.shape[0]}", "region": "frost", "ramp": "HILL"}
    new["files"] = dict(sorted(new["files"].items()))
    (PREG / "regions_palettes.json").write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n")

    report = {}
    for name, (cv, size) in ore_contract().items():
        assert (cv.w, cv.h) == size, name
        if (ASSETS / name).exists():
            old = np.array(Image.open(ASSETS / name).convert("RGBA"))
            report[name] = bool(((old[:, :, 3] > 0) == (cv.a[:, :, 3] > 0)).all())
        save_rgba(cv, PEND / name)
    return ground, decals, report


def digest():
    h = hashlib.md5()
    for p in sorted(PEND.rglob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


if __name__ == "__main__":
    _g, _d, sil = build()
    d1 = digest()
    build()
    d2 = digest()
    print("silhueta igual à de hoje:", sil)
    print("determinismo:", "OK" if d1 == d2 else "FALHOU", d1)
    if "--no-report" not in sys.argv:
        subprocess.run([sys.executable, str(HERE / "v05_m3_gelo_report.py")], check=True)
