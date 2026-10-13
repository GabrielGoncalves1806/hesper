"""Formações fixas (não mineráveis, marcos no mapa) e decoração solta com altura. Tudo em ÍNDICE (ver
regions_core: 0..7 rampa, 8 contorno, 9 sombra), recolorido pela rampa da região e do estágio.

Cada formação devolve (índice, info):
    info["foot"]  = (x, y) do ponto de ancoragem no sprite = centro da base (igual aos outros objetos)
    info["tiles"] = lista de (dx, dy) dos tiles que BLOQUEIAM, relativos ao tile do pé (0, 0) = tile da âncora
    info["size"]  = (w, h) em tiles do retângulo ocupado (pro mapa e pro gerador reservar espaço)
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from regions_core import fbm, grid, hash2, vnoise

T = 32


def outline(idx):
    """Contorno de 1 px por fora (índice 8) + nada mais."""
    m = (idx != 255) & (idx != 9)
    d = np.zeros_like(m)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d |= np.roll(np.roll(m, dy, 0), dx, 1)
    idx[d & ~m] = 8
    return idx


def ground_shadow(idx, cx, cy, rx, ry):
    """Sombra no chão (índice 9, alfa fixo), elipse deslocada pra direita-baixo, por baixo do resto."""
    h, w = idx.shape
    xs, ys = grid(w, h)
    e = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 < 1
    idx[e & (idx == 255)] = 9
    return idx


def side_band(t):
    """Sombreamento em faixas pela posição horizontal normalizada (-1 esquerda iluminada .. 1 direita)."""
    return np.where(t < -0.55, 4, np.where(t < 0.12, 3, np.where(t < 0.62, 2, 1))).astype(np.int16)


def pillar(idx, cx, base_y, top_y, hw_base, hw_top, seed, lean=0.0, strata=12, cap=True):
    """Coluna de rocha com estratos: frente sombreada em faixas, tampa clara em cima, sulcos horizontais."""
    h, w = idx.shape
    xs, ys = grid(w, h)
    k = np.clip((base_y - ys) / max(1, base_y - top_y), 0, 1)           # 0 na base, 1 no topo
    c = cx + lean * k * (base_y - top_y)
    hw = hw_base + (hw_top - hw_base) * k
    hw = hw + 2.2 * (fbm(ys * 1.0, 0 * ys + seed, 9, seed, 2) - 0.5) * 2
    notch = (np.sin(ys / strata * 2 * math.pi + seed) > 0.82) * 1.5       # cintura nos estratos
    hw = hw - notch
    topwob = top_y + 3 * (vnoise(xs, 0 * xs, 7, seed + 1) - 0.5) * 2
    body = (np.abs(xs - c) <= hw) & (ys >= topwob) & (ys <= base_y)
    t = (xs - c) / np.maximum(hw, 1)
    band = side_band(t)
    # estratos: linha escura tremida com brilho em cima (só na parte iluminada)
    sy = (ys + 2.5 * (vnoise(xs, 0 * xs, 11, seed + 2) - 0.5) * 2) % strata
    groove = sy < 1.0
    band = np.where(groove, np.maximum(band - 2, 0), band)
    lit = (sy >= strata - 1) & (t < 0.1)
    band = np.where(lit, np.minimum(band + 1, 5), band)
    # fissuras curtas e tortas
    fiss = (np.abs(xs - (c + (hash2(ys // 14, 0, seed + 3) - 0.5) * hw * 1.4)) < 0.6) & \
           (hash2(ys // 14, 1, seed + 4) < 0.45) & (((ys % 14) > 2) & ((ys % 14) < 11))
    band = np.where(fiss, 0, band)
    sp = hash2(xs, ys, seed + 5)
    band = np.where((sp < 0.05) & (band > 1), band - 1, band)
    idx[body] = band[body]
    if cap:                                                             # tampa (o topo visto em 3/4)
        capm = body & (ys < topwob + 6)
        idx[capm] = np.where(t[capm] < 0.3, 5, 4)
        edge = body & (ys >= topwob + 5) & (ys < topwob + 7)
        idx[edge] = 2
    # pé escuro (contato com o chão)
    idx[body & (ys > base_y - 3)] = np.minimum(idx[body & (ys > base_y - 3)], 1)
    return idx


def rubble(idx, x0, x1, y, seed, n=10, pal=(5, 4, 2, 1)):
    rng = np.random.default_rng(seed)
    h, w = idx.shape
    for _ in range(n):
        pw = int(rng.integers(2, 6))
        x = int(rng.uniform(x0, x1 - pw))
        yy = int(y + rng.uniform(-4, 4))
        for i in range(pw):
            for j in range(max(2, pw - 1)):
                if 0 <= x + i < w and 0 <= yy + j < h and idx[yy + j, x + i] in (255, 9):
                    idx[yy + j, x + i] = pal[0] if j == 0 else (pal[2] if j == max(2, pw - 1) - 1 else pal[1])
    return idx


# ---------------------------------------------------------------------------------------------------------------
def monolith():
    """Monolito do planalto: pilar de arenito em camadas, levemente inclinado. 1 tile bloqueando (é fino e alto)."""
    w, h = 72, 136
    idx = np.full((h, w), 255, np.uint8)
    ground_shadow(idx, 46, 126, 30, 7)
    pillar(idx, 34, 126, 8, 21, 15, 3, lean=0.05, strata=13)
    rubble(idx, 8, 64, 124, 4, 12)
    outline(idx)
    return idx, dict(foot=(36, 128), tiles=[(0, 0)], size=(1, 1), name="Monolito")


def arch():
    """Arco de pedra: 2 pernas (1 tile cada) e um vão de 3 tiles por onde o player passa."""
    w, h = 176, 128
    idx = np.full((h, w), 255, np.uint8)
    ground_shadow(idx, 100, 118, 78, 7)
    xs, ys = grid(w, h)
    pillar(idx, 26, 118, 18, 19, 17, 11, lean=0.0, strata=12, cap=False)
    pillar(idx, 150, 118, 18, 19, 16, 12, lean=0.0, strata=12, cap=False)
    # vão: banda entre o topo e a parte de baixo curva
    top = 10 + 5 * ((xs - 88) / 88) ** 2 + 2.5 * (vnoise(xs, 0 * xs, 9, 13) - 0.5) * 2
    under = 44 + 40 * np.clip(np.abs(xs - 88) / 62, 0, 1) ** 2.2
    span = (ys >= top) & (ys <= under) & (xs > 8) & (xs < 168)
    v = (ys - top) / np.maximum(under - top, 1)
    band = np.where(v < 0.35, 3, np.where(v < 0.8, 2, 1)).astype(np.int16)
    sy = (ys + 2 * (vnoise(xs, 0 * xs, 13, 14) - 0.5) * 2) % 12
    band = np.where(sy < 1, np.maximum(band - 1, 0), band)
    band = np.where(xs < 30, np.minimum(band + 1, 4), band)
    band = np.where(ys > under - 2, 0, band)                        # barriga do arco na sombra
    idx[span] = band[span]
    capm = span & (ys < top + 6)
    idx[capm] = np.where(xs[capm] < 120, 5, 4)
    idx[span & (ys >= top + 5) & (ys < top + 7)] = 2
    rubble(idx, 6, 50, 116, 15, 7)
    rubble(idx, 128, 172, 116, 16, 7)
    outline(idx)
    return idx, dict(foot=(88, 120), tiles=[(-2, 0), (2, 0)], size=(5, 1), name="Arco de pedra")


def spire(idx, cx, base_y, height, hw, seed, flat=False, taper=0.35):
    """Coluna de basalto: lados quase retos (afinam `taper`), topo QUEBRADO em diagonal (a ponta sai do corte, não
    de um cone), 3 facetas chapadas (esquerda clara, meio, direita escura) e fraturas horizontais."""
    h, w = idx.shape
    xs, ys = grid(w, h)
    top = base_y - height
    k = np.clip((base_y - ys) / height, 0, 1)
    half = hw * (1 - k * taper)
    slope = (0.9 + 0.8 * hash2(seed, 0, 2)) * (1 if hash2(seed, 0, 1) < 0.5 else -1)
    cut = top + (xs - cx) * slope + (0 if not flat else 0)
    if flat:
        cut = top + (xs - cx) * slope * 0.25
    body = (np.abs(xs - cx) <= half) & (ys <= base_y) & (ys >= cut)
    t = (xs - cx) / np.maximum(half, 1)
    band = np.where(t < -0.35, 4, np.where(t < 0.3, 3, 1)).astype(np.int16)
    band = np.where((np.abs(t + 0.35) < 0.12) & (t < 0), 5, band)                 # aresta iluminada
    band = np.where((np.abs(t - 0.3) < 0.1), 2, band)
    cr = (hash2(ys // 7, seed, 3) < 0.30) & ((ys % 7) == 0) & (ys > cut + 4)       # fratura horizontal
    band = np.where(cr, np.where(t < 0.3, 1, 0), band)
    band = np.where(np.roll(cr, 1, 0) & (t < 0.3), 5, band)
    sp = hash2(xs, ys, seed + 7)
    band = np.where((sp < 0.04) & (band > 1), band - 1, band)
    band = np.where((sp > 0.988) & (band >= 3), 6, band)                         # óxido
    idx[body] = band[body]
    capm = body & (ys < cut + 3)                                                # a face do corte (clara)
    idx[capm] = np.where(t[capm] < 0.3, 5, 4)
    idx[body & (ys > base_y - 2)] = 0
    return idx


def basalt_spires():
    """Pináculos de basalto: aglomerado de colunas pontudas. 3×2 tiles bloqueando."""
    w, h = 120, 136
    idx = np.full((h, w), 255, np.uint8)
    ground_shadow(idx, 70, 124, 52, 9)
    spire(idx, 70, 112, 74, 12, 21, flat=True, taper=0.1)
    spire(idx, 46, 116, 106, 14, 22, taper=0.3)
    spire(idx, 88, 120, 86, 12, 23, taper=0.25)
    spire(idx, 26, 124, 58, 11, 24, flat=True, taper=0.1)
    spire(idx, 104, 126, 44, 9, 25, taper=0.2)
    spire(idx, 62, 128, 30, 9, 26, flat=True, taper=0.05)
    rubble(idx, 8, 116, 126, 27, 16, pal=(4, 3, 1, 0))
    outline(idx)
    return idx, dict(foot=(62, 130), tiles=[(-1, 0), (0, 0), (1, 0), (-1, -1), (0, -1), (1, -1)], size=(3, 2),
                     name="Pináculos de basalto")


def slab(dr, pts, top, side, edge):
    dr.polygon(pts, fill=side)
    dr.polygon(pts[:3], fill=top)
    dr.line(pts + [pts[0]], fill=edge)


def salt_ridge():
    """Crosta de sal elevada: placas grossas de sal empurradas e inclinadas, encavaladas numa crista baixa.
    Lajes largas e de topo chato (nada de dente). 5×1 tiles bloqueando; baixa, não esconde quem está atrás."""
    w, h = 176, 72
    rng = np.random.default_rng(37)
    im = Image.new("L", (w, h), 255)
    dr = ImageDraw.Draw(im)
    xs_, ys_ = np.meshgrid(np.arange(w), np.arange(h))
    base = lambda x: 58 + 4 * math.sin(x / 36)  # noqa: E731
    x = 4
    slabs = []
    while x < w - 30:
        sw = rng.uniform(24, 36)
        mid = 1 - abs(x + sw / 2 - w / 2) / (w * 0.62)
        lift = rng.uniform(18, 32) * mid + 6                      # quanto a borda de trás subiu
        tilt = rng.uniform(-0.9, 0.9)
        b0, b1 = base(x), base(x + sw)
        # topo da laje (inclinado pra frente, visto de cima): quadrilátero; frente: a espessura (6-9 px)
        th = rng.uniform(7, 11)
        tl = (x + 3, b0 - lift - th + tilt * 10)
        tr = (x + sw - 2, b1 - lift - th - tilt * 10)
        fr = (x + sw, b1 - th)
        fl = (x, b0 - th)
        slabs.append((tl, tr, fr, fl, th))
        x += sw * rng.uniform(0.8, 1.05)
    for tl, tr, fr, fl, th in sorted(slabs, key=lambda q: -(q[2][1] - q[0][1])):
        dr.polygon([fl, fr, (fr[0], fr[1] + th), (fl[0], fl[1] + th)], fill=2)         # espessura (frente)
        dr.polygon([tl, tr, fr, fl], fill=4)                                            # topo
        dr.line([tl, tr], fill=5)
        dr.line([fl, fr], fill=3)
        dr.line([(fl[0], fl[1] + th), (fr[0], fr[1] + th)], fill=1)
        dr.line([tr, fr, (fr[0], fr[1] + th)], fill=1)
        mx = (tl[0] + tr[0]) / 2 + rng.uniform(-6, 6)                                    # rachadura no topo
        dr.line([(mx, (tl[1] + tr[1]) / 2 + 2), (mx + rng.uniform(-4, 4), (fl[1] + fr[1]) / 2 - 1)], fill=2)
    a = np.array(im)
    sp = hash2(xs_, ys_, 33)
    a[(a == 4) & (sp < 0.05)] = 7
    a[(a == 4) & (sp > 0.95)] = 3
    a[(a == 2) & (sp < 0.05)] = 1
    ground_shadow(a, 94, 66, 84, 6)
    outline(a)
    return a, dict(foot=(88, 68), tiles=[(-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0)], size=(5, 1),
                   name="Crosta de sal elevada")


def cone():
    """Cone de basalto (gancho do vulcão do futuro): morro baixo com cratera escura no topo. 5 + 3 tiles."""
    w, h = 144, 100
    idx = np.full((h, w), 255, np.uint8)
    ground_shadow(idx, 80, 90, 66, 9)
    xs, ys = grid(w, h)
    cx, top, base = 72, 22, 88
    k = np.clip((ys - top) / (base - top), 0, 1)
    half = 26 + 42 * k ** 0.8 + 3 * (fbm(ys * 1.0, 0 * ys, 8, 41, 2) - 0.5) * 2
    body = (np.abs(xs - cx) <= half) & (ys >= top) & (ys <= base)
    t = (xs - cx) / np.maximum(half, 1)
    band = side_band(t)
    # sulcos radiais (do topo pro pé)
    ang = np.arctan2(xs - cx, (ys - top + 6))
    gully = (np.abs(((ang * 9) % 1.0) - 0.5) < 0.06) & (hash2((ang * 9).astype(int), 0, 42) < 0.7) & (k > 0.15)
    band = np.where(gully, np.maximum(band - 1, 0), band)
    rust = (hash2((ang * 9).astype(int), 1, 43) < 0.25) & (np.abs(((ang * 9) % 1.0) - 0.62) < 0.05) & (k > 0.1)
    rust &= hash2(xs // 2, ys // 3, 45) < 0.55                                   # óxido apagado, tracejado
    band = np.where(rust & (band >= 2), 6, band)
    idx[body] = band[body]
    # borda da cratera (elipse) e o buraco escuro
    rim = ((xs - cx) / 30) ** 2 + ((ys - top - 4) / 9) ** 2
    idx[(rim < 1.0) & (ys >= top - 6)] = 4
    idx[(rim < 1.0) & (ys < top + 1) & (ys >= top - 6)] = 5
    idx[(rim < 0.62)] = 1
    idx[(rim < 0.42)] = 0
    idx[(rim < 0.30)] = 0
    idx[body & (ys > base - 2)] = 1
    rubble(idx, 8, w - 8, 90, 44, 18, pal=(4, 3, 1, 0))
    outline(idx)
    return idx, dict(foot=(72, 92), tiles=[(-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (-1, -1), (0, -1), (1, -1)],
                     size=(5, 2),
                     name="Cone de basalto")


# ---- gelo -----------------------------------------------------------------------------------------------------
ICE_POLY = [(10, 96), (4, 62), (16, 30), (42, 12), (78, 8), (106, 22), (122, 52), (120, 88), (98, 108), (34, 110)]


def ice_block(scale=1.0, seed=51):
    """Gelo-portão: bloco de gelo gigante facetado com rocha presa dentro. `scale` = etapa do derretimento."""
    w, h = 136, 132
    idx = np.full((h, w), 255, np.uint8)
    cx, base = 66, 116
    pts = [(cx + (x - 64) * scale, base - (112 - y) * scale) for x, y in ICE_POLY]
    if scale < 1:                                           # derretendo: cantos mais redondos (menos vértices)
        pts = pts[::1] if scale > 0.7 else pts[::2]
    im = Image.new("L", (w, h), 255)
    dr = ImageDraw.Draw(im)
    dr.polygon(pts, fill=3)
    a = np.array(im)
    body = a != 255
    xs, ys = grid(w, h)
    # facetas: topo claro, frente, lado direito escuro (cortes retos a partir de pontos internos)
    top_y = base - 70 * scale
    a[body & (ys < top_y + (xs - cx) * 0.25)] = 5
    a[body & (ys < top_y - 18 * scale + (xs - cx) * 0.35)] = 6
    a[body & (xs > cx + 30 * scale - (ys - top_y) * 0.2) & (ys > top_y)] = 2
    a[body & (ys > base - 14 * scale)] = np.minimum(a[body & (ys > base - 14 * scale)], 2)
    # rocha presa dentro (silhueta escura vista através do gelo)
    rock = ((xs - cx + 8 * scale) / (22 * scale)) ** 2 + ((ys - base + 38 * scale) / (14 * scale)) ** 2 < 1
    a[body & rock & (a >= 3)] = 7
    a[body & rock & (a < 3)] = 1
    # rachaduras internas e reflexos diagonais
    crack = (np.abs((xs - cx) * 0.8 - (ys - base + 60 * scale) * 0.5) < 0.6) & (ys > top_y)
    a[body & crack] = 1
    glint = (((xs + ys * 2) % 29) < 2) & (hash2(xs // 12, ys // 12, seed) < 0.5)
    a[body & glint & (a >= 3)] = 6
    sp = hash2(xs, ys, seed + 1)
    a[body & (sp < 0.03) & (a >= 3)] = 4
    a[body & (sp > 0.985)] = 6
    ground_shadow(a, cx + 14, base - 2, 60 * scale + 4, 9 * scale + 3)
    outline(a)
    foot_tiles = {1.0: [(dx, dy) for dx in (-2, -1, 0, 1) for dy in (0, -1)],
                  0.72: [(dx, dy) for dx in (-1, 0, 1) for dy in (0, -1)],
                  0.45: [(-1, 0), (0, 0)]}
    return a, dict(foot=(cx, base + 2), tiles=foot_tiles.get(scale, []), size=(4, 2), name="Gelo-portão")


def frost_ring(w=176, h=72, seed=55):
    """Geada em volta do gelo que sublima (no Árido não tem água líquida: o gelo vira vapor e deixa geada)."""
    xs, ys = grid(w, h)
    e = ((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2
    n = fbm(xs, ys, 12, seed, 2)
    a = np.full((h, w), 255, np.uint8)
    m = (e + 0.6 * (n - 0.5)) < 1
    a[m] = 5
    a[m & (hash2(xs, ys, seed + 1) < 0.25)] = 255
    a[m & (e < 0.55) & (n > 0.55)] = 4
    return a


def crater_ice(stage):
    """Tampa de gelo da cratera (overlay 96×96 por cima do crater.png). 0 = inteira, 1 = rachada, 2 = restos."""
    w = h = 96
    xs, ys = grid(w, h)
    cx, cy, rx, ry = 48, 44, 33, 25
    e = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2
    a = np.full((h, w), 255, np.uint8)
    lid = e < 1
    a[lid] = 4
    a[lid & (ys < cy - 4 + (xs - cx) * 0.1)] = 5
    a[lid & (e < 0.35) & (ys < cy - 2)] = 6
    a[lid & (e > 0.82)] = 3
    a[lid & (e > 0.82) & (ys > cy)] = 2
    glint = (((xs + ys * 2) % 21) < 2) & (hash2(xs // 10, ys // 10, 61) < 0.5) & (e < 0.8)
    a[glint & lid] = 6
    if stage >= 1:                                         # rachaduras que viram buracos escuros
        _, edge, cid = __import__("regions_core").voronoi(xs, ys, 20, 63)
        crack = lid & (edge < 1.2 + 1.8 * stage) & (e < 0.95)
        a[crack] = 0
        a[np.roll(crack, 1, 0) & ~crack & lid] = 6
    if stage >= 2:                                         # sobram blocos na beira
        keep = lid & ((e > 0.55) | (hash2(cid, 0, 65) < 0.25))
        a[lid & ~keep] = 255
        a[lid & ~keep & (e > 0.45)] = 255
    outline(a)
    return a


# ---- decoração solta com altura (não colide) ---------------------------------------------------------------------
def shards(seed=71):
    """Lascas pontudas de basalto, 12-20 px."""
    w, h = 28, 24
    idx = np.full((h, w), 255, np.uint8)
    rng = np.random.default_rng(seed)
    for k in range(int(rng.integers(2, 4))):
        cx = int(rng.uniform(6, w - 6))
        ht = int(rng.uniform(9, 19))
        spire(idx, cx, h - 3, ht, int(rng.uniform(3, 5)), seed + k)
    outline(idx)
    return idx


def salt_crystals(seed=81):
    w, h = 22, 16
    idx = np.full((h, w), 255, np.uint8)
    rng = np.random.default_rng(seed)
    for _ in range(int(rng.integers(3, 6))):
        x, s = int(rng.uniform(2, w - 7)), int(rng.integers(3, 6))
        y = h - 2 - s - int(rng.uniform(0, 3))
        idx[y:y + s, x:x + s] = 4
        idx[y, x:x + s] = 5
        idx[y:y + s, x + s - 1] = 2
        idx[y + s - 1, x:x + s] = 2
        idx[y, x] = 7
    outline(idx)
    return idx


def ice_chunks(seed=91):
    w, h = 26, 18
    idx = np.full((h, w), 255, np.uint8)
    rng = np.random.default_rng(seed)
    for _ in range(int(rng.integers(2, 4))):
        x, s = int(rng.uniform(2, w - 9)), int(rng.integers(5, 9))
        y = h - 2 - s - int(rng.uniform(0, 2))
        idx[y:y + s, x:x + s] = 4
        idx[y:y + 2, x:x + s] = 6
        idx[y + 2:y + s, x + s - 2:x + s] = 2
        idx[y + 2, x + 1] = 7
    outline(idx)
    return idx


FORMATIONS = {"monolith": monolith, "arch": arch, "basalt_spires": basalt_spires, "salt_ridge": salt_ridge,
              "cone": cone}
