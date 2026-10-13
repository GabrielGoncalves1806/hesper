"""Formações fixas (não mineráveis, marcos no mapa) e decoração solta com altura. Desde a v8.1 as formações, o
gelo-portão e a cratera são volumes 3D em regions_volume.py; este módulo reexporta e guarda os soltos. Tudo em ÍNDICE (ver
regions_core: 0..7 rampa, 8 contorno, 9 sombra), recolorido pela rampa da região e do estágio.

Cada formação devolve (índice, info):
    info["foot"]  = (x, y) do ponto de ancoragem no sprite = centro da base (igual aos outros objetos)
    info["tiles"] = lista de (dx, dy) dos tiles que BLOQUEIAM, relativos ao tile do pé (0, 0) = tile da âncora
    info["size"]  = (w, h) em tiles do retângulo ocupado (pro mapa e pro gerador reservar espaço)
"""

from __future__ import annotations

import numpy as np

import regions_volume as V
from regions_core import fbm, grid, hash2

T = 32


def outline(idx):
    """Contorno de 1 px por fora (índice 8) + nada mais."""
    m = (idx != 255) & (idx != 9)
    d = np.zeros_like(m)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d |= np.roll(np.roll(m, dy, 0), dx, 1)
    idx[d & ~m] = 8
    return idx


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


# v8.1: as formações viraram VOLUMES 3D (tools/sprites/regions_volume.py). Aqui ficam a geada e os soltos.
FORMATIONS = {"monolith": V.monolith, "arch": V.arch, "basalt_spires": V.basalt_spires, "salt_ridge": V.salt_ridge,
              "cone": V.cone}
ice_block = V.ice_block
crater = V.crater
ejecta = V.ejecta
