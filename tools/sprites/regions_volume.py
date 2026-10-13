"""Formações NATURAIS (v8.1): cada uma é um VOLUME 3D (densidade > 0 = rocha) renderizado em pixel art na projeção
do jogo (3/4: o pixel (sx, sy) vê os pontos (X, Y, Z) com sx = X, sy = Y − Z; o mais alto na linha é o visível).

    luz em faixas chapadas (5 tons da rampa), sombra própria e projetada no chão (índice 9, alfa fixo),
    linha escura onde uma parte passa na frente da outra, contorno #1b1630 na silhueta.

Nada de polígono 2D: o arco é um tubo torto com erosão, o hoodoo um fuste que afina e engorda com pedra de topo,
o basalto são prismas hexagonais em degraus, a crosta de sal são placas inclinadas, o cone e a cratera são
relevo (campo de altura), o gelo é um bloco poliédrico translúcido.

Índices: 0..7 rampa da região, 8 contorno, 9 sombra, 255 transparente. Na cratera: 10..17 gelo (rampa ICE),
18..20 metal da rampa (claro, escuro, laranja).
"""

from __future__ import annotations

import math

import numpy as np

from regions_core import fbm, grid, hash2, vnoise

L = np.array([-0.50, 0.28, 0.82])
L = L / np.linalg.norm(L)


# ---- ruído 3D ---------------------------------------------------------------------------------------------------
def vnoise3(x, y, z, cell, seed):
    fx, fy, fz = x / cell, y / cell, z / cell
    ix, iy, iz = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64), np.floor(fz).astype(np.int64)
    tx, ty, tz = fx - ix, fy - iy, fz - iz
    tx, ty, tz = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty), tz * tz * (3 - 2 * tz)

    def h(a, b, c):
        return hash2(a, b * 131 + c * 977, seed)

    c00 = h(ix, iy, iz) * (1 - tx) + h(ix + 1, iy, iz) * tx
    c10 = h(ix, iy + 1, iz) * (1 - tx) + h(ix + 1, iy + 1, iz) * tx
    c01 = h(ix, iy, iz + 1) * (1 - tx) + h(ix + 1, iy, iz + 1) * tx
    c11 = h(ix, iy + 1, iz + 1) * (1 - tx) + h(ix + 1, iy + 1, iz + 1) * tx
    return (c00 * (1 - ty) + c10 * ty) * (1 - tz) + (c01 * (1 - ty) + c11 * ty) * tz


def fbm3(x, y, z, cell, seed, octaves=3):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * vnoise3(x, y, z, cell / 2 ** o, seed + 17 * o)
        norm += amp
        amp *= 0.5
    return tot / norm - 0.5          # centrado em 0, ~[-0.5, 0.5]


# ---- o renderizador ---------------------------------------------------------------------------------------------
class Volume:
    """dens(X, Y, Z) -> densidade (> 0 dentro). mat(X, Y, Z, n) -> índice final (opcional)."""

    def __init__(self, w, h, ox, oy, zmin, zmax, dens, shade, soft_edge=False, ground_shadow=True, stop=None):
        self.stop = stop                    # stop(X, Y, Z) -> o raio bateu num chão que oculta (fica transparente)
        self.w, self.h, self.ox, self.oy = w, h, ox, oy
        self.zmin, self.zmax = zmin, zmax
        self.dens, self.shade = dens, shade
        self.soft_edge = soft_edge
        self.ground_shadow = ground_shadow

    def render(self):
        sx, sy = grid(self.w, self.h)
        X = (sx - self.ox).astype(float).ravel()
        Y0 = (sy - self.oy).astype(float).ravel()
        n = X.size
        hitZ = np.full(n, np.nan)
        todo = np.arange(n)
        z = float(self.zmax)
        while z >= self.zmin and todo.size:
            d = self.dens(X[todo], Y0[todo] + z, np.full(todo.size, z))
            hit = d > 0
            if self.stop is not None:
                dead = ~hit & self.stop(X[todo], Y0[todo] + z, np.full(todo.size, z))
                todo = todo[~dead]
                hit = hit[~dead]
            if hit.any():
                # refina: meio passo pra cima ainda dentro?
                hitZ[todo[hit]] = z
                todo = todo[~hit]
            z -= 1.0
        idx = np.full(n, 255, np.uint8)
        hm = ~np.isnan(hitZ)
        hx, hz = X[hm], hitZ[hm]
        hy = Y0[hm] + hz
        e = 1.0
        gx = self.dens(hx + e, hy, hz) - self.dens(hx - e, hy, hz)
        gy = self.dens(hx, hy + e, hz) - self.dens(hx, hy - e, hz)
        gz = self.dens(hx, hy, hz + e) - self.dens(hx, hy, hz - e)
        nrm = -np.stack([gx, gy, gz], axis=1)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
        # sombra própria: marcha na direção da luz
        lit = np.ones(hx.size, bool)
        px, py, pz = hx + nrm[:, 0] * 1.5, hy + nrm[:, 1] * 1.5, hz + nrm[:, 2] * 1.5
        for t in range(2, 120, 2):
            m = lit.copy()
            if not m.any():
                break
            q = self.dens(px[m] + L[0] * t, py[m] + L[1] * t, pz[m] + L[2] * t) > 0
            lit[np.nonzero(m)[0][q]] = False
            if pz.max() + L[2] * t > self.zmax + 2:
                break
        idx[hm] = self.shade(hx, hy, hz, nrm, lit)
        # sombra projetada no chão (Z = 0)
        if self.ground_shadow:
            gm = np.nonzero(~hm)[0]
            sh = np.zeros(gm.size, bool)
            gxx, gyy = X[gm], Y0[gm]
            for t in range(2, 160, 2):
                if pz.size == 0 or L[2] * t > self.zmax + 2:
                    break
                q = self.dens(gxx + L[0] * t, gyy + L[1] * t, np.full(gm.size, L[2] * t)) > 0
                sh |= q
            idx[gm[sh]] = 9
        idx = idx.reshape(self.h, self.w)
        Zimg = np.full(n, np.nan)
        Zimg[hm] = hitZ[hm]
        Zimg = Zimg.reshape(self.h, self.w)
        Dimg = np.full(n, np.nan)
        Dimg[hm] = (Y0[hm] + hitZ[hm]) + hitZ[hm]                           # "perto da câmera"
        Dimg = Dimg.reshape(self.h, self.w)
        self.Z, self.D = Zimg, Dimg
        return self.finish(idx, Zimg, Dimg)

    def finish(self, idx, Z, D):
        solid = (idx != 255) & (idx != 9)
        # linha escura onde uma parte passa na frente de outra (salto de profundidade)
        for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            Dn = _sh(D, dy, dx, np.nan)
            sn = _sh(solid, dy, dx, False)
            back = solid & sn & (np.nan_to_num(Dn, nan=-1e9) - D > 9)                   # este pixel está atrás do vizinho
            idx[back & (idx < 10)] = 0
            idx[back & (idx >= 10) & (idx < 18)] = 10
        # contorno na silhueta (por fora); borda baixa (campo de altura) fica sem contorno
        out = np.zeros_like(solid)
        for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nb = _sh(solid, dy, dx, False)
            nz = _sh(np.nan_to_num(Z, nan=0), dy, dx, 0.0)
            ok = nb & ((nz > 3) if self.soft_edge else True)
            out |= ok & ~solid
        idx[out] = 8
        return idx


def _sh(a, dy, dx, fill):
    out = np.full_like(a, fill)
    h, w = a.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = a[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


def bands(lam, lit):
    b = np.where(lam > 0.80, 5, np.where(lam > 0.55, 4, np.where(lam > 0.30, 3, np.where(lam > 0.05, 2, 1))))
    b = np.where(lit, b, np.minimum(b, 2) - (lam < 0.3))
    return np.clip(b, 0, 5).astype(np.int16)


def sandstone(hx, hy, hz, nrm, lit, seed, period=7.0):
    """Arenito: luz em faixas + camadas horizontais que acompanham a curva da rocha (a camada é a altura Z)."""
    lam = nrm @ L
    b = bands(lam, lit)
    layer = np.floor((hz + 3.5 * fbm3(hx, hy, hz, 18, seed, 2) * 2) / period).astype(int)
    k = layer % 5
    b = np.where((k == 1) & (b < 5) & (b > 0) & (nrm[:, 2] < 0.7), b + 1, b)
    b = np.where((k == 3) & (b > 1) & (nrm[:, 2] < 0.7), b - 1, b)
    sp = hash2(np.round(hx).astype(int), np.round(hy * 3 + hz).astype(int), seed + 1)
    b = np.where((sp < 0.05) & (b > 1), b - 1, b)
    return b.astype(np.uint8)


# =================================================================================================================
# ARCO NATURAL (Delicate Arch): tubo torto, perna esquerda grossa, direita fina, vão torto, buracos de erosão
# =================================================================================================================
def _curve(n=56):
    t = np.linspace(0, 1, n)
    x = -70 + 130 * t + 12 * np.sin(np.pi * t) ** 2 - 8 * t ** 3
    z = 100 * np.sin(np.pi * np.clip(t * 0.97 + 0.015, 0, 1)) ** 0.55 * (1.0 - 0.12 * t)
    y = 3 * np.sin(2 * np.pi * t)
    # perna esquerda maciça, vão afinando à direita, perna direita fina com "cintura"
    r = 25 * (1 - t) ** 1.3 + 10 * t + 9 * np.exp(-((t - 0.33) / 0.14) ** 2) - 3 * np.exp(-((t - 0.82) / 0.06) ** 2)
    return np.stack([x, y, z], 1), r


CURVE, CRAD = _curve()
HOLES = [(-52, 16, 60, 5), (-64, 18, 30, 4.5), (-28, 14, 88, 4), (44, 10, 64, 3), (-76, 14, 12, 5), (-38, 15, 44, 3.5)]


def arch_dens(X, Y, Z):
    best = np.full(X.shape, 1e9)
    rb = np.zeros(X.shape)
    for (cx, cy, cz), r in zip(CURVE, CRAD):
        d = np.sqrt((X - cx) ** 2 + ((Y - cy) * 1.25) ** 2 + ((Z - cz) * 0.9) ** 2)
        m = d < best
        best = np.where(m, d, best)
        rb = np.where(m, r, rb)
    flare = np.clip(16 - Z, 0, None) * 0.7                          # o pé abre no chão
    # erosão anisotrópica: sulcos horizontais (ruído esticado em X e Y, fino em Z) + ressaltos de estrato
    groove = fbm3(X / 2.6, Y / 2.6, Z, 7, 37, 2)
    ledge = np.clip(((Z + 4 * fbm3(X, Y, Z, 26, 38, 2)) % 9) - 6.5, 0, None)   # recuo no fim de cada camada
    d = rb + flare - best + 9 * fbm3(X, Y, Z, 30, 31, 2) + 5.5 * groove + 1.5 * fbm3(X, Y, Z, 5, 33) - 1.1 * ledge
    for hx, hy, hz, hr in HOLES:                                       # buracos de erosão
        d = np.minimum(d, np.sqrt((X - hx) ** 2 + (Y - hy) ** 2 + (Z - hz) ** 2) - hr)
    base = 11 - np.sqrt(((X + 70) / 1.8) ** 2 + (Y / 1.3) ** 2 + (Z * 2.0) ** 2) + 7 * fbm3(X, Y, Z, 9, 35)
    base2 = 7 - np.sqrt(((X - 62) / 1.5) ** 2 + (Y / 1.2) ** 2 + (Z * 2.4) ** 2) + 5 * fbm3(X, Y, Z, 8, 36)
    return np.maximum(np.maximum(d, base), base2)


def arch():
    v = Volume(208, 150, 112, 128, 0, 124, arch_dens, lambda *a: sandstone(*a, seed=41, period=9.0))
    idx = v.render()
    return idx, dict(foot=(112, 128), tiles=[(-2, 0), (2, 0)], size=(5, 1), name="Arco de pedra")


# =================================================================================================================
# HOODOO: fuste que afina e engorda + pedra de topo mais escura e larga
# =================================================================================================================
HOODOO_R = [(0, 22), (8, 18), (22, 12.5), (36, 15.5), (48, 13), (60, 14), (72, 9.5), (82, 7.5), (88, 8.5)]


def _rz(Z):
    zs, rs = zip(*HOODOO_R)
    return np.interp(Z, zs, rs)


def hoodoo_dens(X, Y, Z, part=False):
    ax = 3 * np.sin(Z / 34) + 0.04 * Z
    ledge = np.clip(((Z + 3 * fbm3(X, Y, Z, 20, 56, 2)) % 10) - 7.5, 0, None)
    shaft = _rz(Z) - np.sqrt(((X - ax) * 0.9) ** 2 + (Y * 1.1) ** 2) + 4.5 * fbm3(X, Y, Z, 16, 51) \
        + 3.5 * fbm3(X / 2.5, Y / 2.5, Z, 6, 57, 2) + 1.2 * fbm3(X, Y, Z, 5, 52) - 1.0 * ledge
    shaft = np.where(Z > 92, -9, shaft)
    cx, cz = ax + 5, 94
    tiltz = (Z - cz) + 0.12 * (X - cx)                                   # laje de topo inclinada
    tiltz = (Z - cz) + 0.18 * (X - cx) - 0.08 * Y
    cap = np.minimum(19 - np.sqrt(((X - cx) * 0.95) ** 2 + (Y * 1.2) ** 2) + 9 * fbm3(X, Y, Z, 12, 53, 2),
                     5.0 - np.abs(tiltz) + 2.5 * fbm3(X, Y, Z, 6, 58, 2))
    base = 9 - np.sqrt((X / 2.0) ** 2 + (Y / 1.6) ** 2 + (Z * 1.8) ** 2) + 5 * fbm3(X, Y, Z, 8, 54)
    if part:
        return cap > np.maximum(shaft, base)
    return np.maximum(np.maximum(shaft, cap), base)


def hoodoo_shade(hx, hy, hz, nrm, lit):
    b = sandstone(hx, hy, hz, nrm, lit, 55, 8.0)
    cap = hoodoo_dens(hx, hy, hz, part=True)
    capb = bands(nrm @ L, lit)                                         # pedra de topo: mais dura, cinza e escura
    capb = np.where(capb >= 3, 6, np.maximum(capb - 1, 0))
    spk = hash2(np.round(hx).astype(int), np.round(hy * 2 + hz).astype(int), 59)
    capb = np.where((capb == 6) & (spk < 0.18), 2, capb)
    capb = np.where((capb == 6) & (spk > 0.9) & lit, 4, capb)
    return np.where(cap, capb, b).astype(np.uint8)


def monolith():
    v = Volume(80, 140, 38, 124, 0, 110, hoodoo_dens, hoodoo_shade)
    idx = v.render()
    return idx, dict(foot=(38, 124), tiles=[(0, 0)], size=(1, 1), name="Hoodoo (monolito)")


# =================================================================================================================
# BASALTO COLUNAR: prismas hexagonais em degraus, topos quebrados, colunas caídas, juntas transversais
# =================================================================================================================
APO = 8.4                     # apótema do hexágono (px no chão)


def _columns():
    cols = []
    rng = np.random.default_rng(71)
    s = 2 * APO + 1.4                                    # distância entre centros (1,4 px de junta)
    for q in range(-5, 6):
        for r in range(-3, 4):
            x = s * (q + r * 0.5)
            y = s * 0.866 * r
            d = math.hypot(x / 1.25, y)
            if d > 42 + 10 * hash2(q, r, 72):
                continue
            pl = fbm(np.array(x + 40.0), np.array(y + 40.0), 26, 76, 2)
            hgt = 44 - 1.0 * d - 0.7 * y + 40 * pl + rng.uniform(-6, 6)   # patamares em degrau, mais alto atrás
            if hash2(q, r, 77) < 0.12:
                hgt += 22                                                 # uma ou outra coluna "órgão"
            hgt = max(5, round(hgt / 8) * 8)
            tilt = (rng.uniform(-0.45, 0.45), rng.uniform(-0.3, 0.15)) if rng.uniform() < 0.4 else (0, 0)
            cols.append((x, y, hgt, tilt, rng.uniform(9, 15)))
    return cols


COLS = _columns()
FALLEN = [((30, 26), 0.35, 44, 6.5), ((-34, 30), -0.25, 30, 6.0), ((48, 6), 1.2, 22, 5.5)]


def _hexd(qx, qy, a):
    qx, qy = np.abs(qx), np.abs(qy)
    return a - np.maximum(qy, qx * 0.866 + qy * 0.5)


def basalt_dens(X, Y, Z, which=False):
    best = np.full(X.shape, -1e9)
    bid = np.full(X.shape, -1)
    for i, (cx, cy, hgt, (tx, ty), _) in enumerate(COLS):
        top = hgt + tx * (X - cx) + ty * (Y - cy)
        d = np.minimum(_hexd(X - cx, Y - cy, APO), top - Z)
        m = d > best
        best = np.where(m, d, best)
        bid = np.where(m, i, bid)
    for k, ((fx, fy), ang, ln, a) in enumerate(FALLEN):                 # colunas caídas, em gomos com junta
        ux, uy = math.cos(ang), math.sin(ang)
        along = (X - fx) * ux + (Y - fy) * uy
        across = -(X - fx) * uy + (Y - fy) * ux
        seg = np.abs(((along + 300) % 15) - 7.5) < 0.7
        d = np.minimum(_hexd(across, Z - a * 0.9, a), ln / 2 - np.abs(along))
        d = np.where(seg, np.minimum(d, -0.1), d)
        m = d > best
        best = np.where(m, d, best)
        bid = np.where(m, 100 + k, bid)
    best = best + 0.5 * fbm3(X, Y, Z, 4, 73)
    return bid if which else best


def basalt_shade(hx, hy, hz, nrm, lit):
    lam = nrm @ L
    b = bands(lam, lit)
    up = nrm[:, 2] > 0.8
    b = np.where(up, np.where(lit, 5, 3), np.minimum(b, 3))             # topo claro (o hexágono lê), faces escuras
    bid = basalt_dens(hx, hy, hz, which=True)
    for i, (cx, cy, hgt, tilt, js) in enumerate(COLS):                   # juntas transversais (fraturas)
        m = (bid == i) & ~up
        ph = hash2(i, 0, 74) * js
        joint = (np.abs(((hgt - hz + ph) % js)) < 0.9) & (hz < hgt - 4)
        b = np.where(m & joint, 0, b)
    sp = hash2(np.round(hx).astype(int), np.round(hy * 2 + hz).astype(int), 75)
    b = np.where((sp < 0.06) & (b > 1), b - 1, b)
    b = np.where((sp > 0.985) & ~up & (b >= 2), 6, b)                    # óxido
    return b.astype(np.uint8)


def basalt_spires():
    v = Volume(156, 136, 78, 116, 0, 104, basalt_dens, basalt_shade)
    idx = v.render()
    return idx, dict(foot=(78, 116), tiles=[(-1, 0), (0, 0), (1, 0), (-1, -1), (0, -1), (1, -1)], size=(3, 2),
                     name="Basalto colunar")


# =================================================================================================================
# CROSTA DE SAL: placas de sal inclinadas que se encontram na crista ("tenda"), quebradas em pedaços
# =================================================================================================================
_rng = np.random.default_rng(81)
SALT_PLATES = []
_x = -84.0
while _x < 84:
    for row in (0, 1) if _rng.uniform() < 0.45 else (0,):
        SALT_PLATES.append(dict(c=(_x + _rng.uniform(-3, 3), _rng.uniform(-6, 6) + row * _rng.choice([-9, 9])),
                                a=_rng.uniform(-0.7, 0.7), l=_rng.uniform(9, 17), A=_rng.uniform(7, 22) * (1 - row * 0.4),
                                sn=_rng.uniform(0.45, 0.8), ss=_rng.uniform(1.5, 2.4), flip=_rng.uniform() < 0.3))
    _x += _rng.uniform(13, 21)


def salt_h(X, Y):
    """Placas de sal empurradas e quebradas: cada placa tem o próprio eixo (girada), crista, um lado suave e outro
    íngreme (a borda que levantou), pontas quebradas irregulares. Encavalam umas nas outras."""
    h = np.full(X.shape, -1.0)
    env = np.clip(1 - (np.abs(X) / 96) ** 2, 0, 1) ** 0.5
    for k, p in enumerate(SALT_PLATES):
        ca, sa = math.cos(p["a"]), math.sin(p["a"])
        u = (X - p["c"][0]) * ca + (Y - p["c"][1]) * sa
        v = -(X - p["c"][0]) * sa + (Y - p["c"][1]) * ca
        if p["flip"]:
            v = -v
        slope = np.where(v < 0, p["sn"], p["ss"])
        end = np.clip(1 - (np.abs(u) / (p["l"] * (1 + 0.3 * fbm(X, Y, 5, 90 + k, 1)))) ** 3, 0, 1)
        plane = p["A"] * env * end - slope * np.abs(v) + 2.0 * fbm(X, Y, 4, 120 + k, 1) * (end > 0.05)
        plate = np.where((plane > 0) & (end > 0.05), plane + 2.5, -1)
        h = np.maximum(h, plate)
    return h + 0.8 * fbm(X, Y, 3, 86, 1) * (h > 0)


def salt_shade(hx, hy, hz, nrm, lit):
    lam = nrm @ L
    b = bands(lam, lit)
    b = np.where(nrm[:, 2] > 0.9, np.maximum(b, 4), b)                    # chão de sal e topo
    b = np.where(nrm[:, 2] > 0.45, np.maximum(b, 4), b)                   # face suave (vira pra luz): clara
    b = np.where(nrm[:, 2] < 0.45, np.minimum(b, 3), b)                    # borda levantada: meio-tom
    sp = hash2(np.round(hx).astype(int), np.round(hy).astype(int), 87)
    b = np.where((sp < 0.05) & (b >= 4), 7, b)
    b = np.where((sp > 0.96) & (b >= 3), b - 1, b)
    from regions_core import voronoi
    _, edge, _ = voronoi(hx + 500, hy + 500, 11, 88)                       # rachaduras na placa
    b = np.where((edge < 0.8) & (nrm[:, 1] < 0) & (b >= 3), 2, b)
    return b.astype(np.uint8)


def salt_ridge():
    v = Volume(204, 96, 102, 70, -1, 34, lambda X, Y, Z: salt_h(X, Y) - Z, salt_shade)
    idx = v.render()
    return idx, dict(foot=(102, 70), tiles=[(-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0)], size=(5, 1),
                     name="Crosta de sal elevada")


# =================================================================================================================
# CONE DE ESCÓRIA (extinto): relevo radial com cratera no topo, sulcos de erosão, borda que some no chão
# =================================================================================================================
def cone_h(X, Y):
    ang = np.arctan2(Y, X)
    r = np.sqrt(X ** 2 + (Y * 1.25) ** 2) * (1 + 0.07 * np.sin(3 * ang + 1) + 0.05 * np.sin(7 * ang))
    R, H, rc = 66, 44, 20
    h = H * np.clip(1 - (r - rc) / (R - rc), 0, 1) ** 1.25
    h = np.where(r < rc, H - 13 * np.clip(1 - (r / rc) ** 2, 0, 1) ** 0.8, h)
    gully = np.abs(np.sin(ang * 8 + 2.0 * fbm(X, Y, 18, 91, 2))) ** 6
    h = h - 4.5 * gully * np.clip((r - rc) / 20, 0, 1) * (h > 1)
    h = h + 2.5 * fbm(X, Y, 7, 92, 2) * (h > 1)
    return np.where(h > 1.2 + 1.5 * fbm(X, Y, 6, 93, 1), h, -50)


def cone_shade(hx, hy, hz, nrm, lit):
    b = bands(nrm @ L, lit)
    ang = np.arctan2(hy, hx)
    streak = (np.abs(np.sin(ang * 8 + 0.6)) ** 8 > 0.7) & (hz > 6) & (hash2((ang * 30).astype(int), 0, 94) < 0.5)
    b = np.where(streak & (b >= 2), 6, b)
    r = np.sqrt(hx ** 2 + (hy * 1.25) ** 2)
    b = np.where((r < 20) & (hz < 38), np.minimum(b, 1), b)
    sp = hash2(np.round(hx).astype(int), np.round(hy).astype(int), 95)
    b = np.where((sp < 0.07) & (b > 1), b - 1, b)
    return b.astype(np.uint8)


def cone():
    v = Volume(152, 112, 76, 74, 0, 50, lambda X, Y, Z: cone_h(X, Y) - Z, cone_shade, soft_edge=True)
    idx = v.render()
    return idx, dict(foot=(76, 74), tiles=[(-1, 0), (0, 0), (1, 0), (-1, -1), (0, -1), (1, -1)], size=(3, 2),
                     name="Cone de escória")


# =================================================================================================================
# GELO-PORTÃO: bloco poliédrico translúcido (rocha presa dentro), encolhe em etapas
# =================================================================================================================
def _poly(seed, n, r, center, squash):
    rng = np.random.default_rng(seed)
    planes = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):                                   # direções bem espalhadas (esfera de Fibonacci) + tremida
        zc = 1 - 2 * (i + 0.5) / n
        rr = math.sqrt(1 - zc * zc)
        u = np.array([math.cos(ga * i) * rr, math.sin(ga * i) * rr, zc]) + rng.normal(scale=0.18, size=3)
        u /= np.linalg.norm(u)
        planes.append((u, r * rng.uniform(0.80, 1.0)))
    return planes, np.array(center, float), np.array(squash, float)


ICE_PARTS = [_poly(101, 18, 32, (0, -2, 30), (1.25, 0.85, 1.2)), _poly(102, 14, 20, (-34, 8, 14), (1.1, 1.0, 1.0)),
             _poly(103, 14, 18, (34, 10, 12), (1.0, 1.0, 1.1))]


def ice_dens(X, Y, Z, scale=1.0, rock=False):
    if rock:
        return 13 * scale - np.sqrt(((X + 6) / 1.4) ** 2 + (Y - 2) ** 2 + ((Z - 24 * scale) / 0.9) ** 2)
    best = np.full(X.shape, -1e9)
    for planes, c, sq in ICE_PARTS:
        p = np.stack([(X - c[0] * scale) / sq[0], (Y - c[1] * scale) / sq[1], (Z - c[2] * scale) / sq[2]], 1)
        d = np.full(X.shape, 1e9)
        for u, r in planes:
            d = np.minimum(d, r * scale - p @ u)
        best = np.maximum(best, d)
    soft = 1.0 + 2.5 * (1 - scale)                                     # derretendo: quinas mais moles
    return best + soft * fbm3(X, Y, Z, 10, 104) * 2 - 0.0 * (Z < 0)


def ice_shade_fn(scale):
    def shade(hx, hy, hz, nrm, lit):
        lam = nrm @ L
        b = np.where(lam > 0.75, 5, np.where(lam > 0.45, 4, np.where(lam > 0.15, 3, 2)))
        b = np.where(lit, b, np.maximum(b - 1, 1))
        hvec = L + np.array([0, 0.7, 0.7])
        hvec = hvec / np.linalg.norm(hvec)
        spec = nrm @ hvec > 0.96
        b = np.where(spec, 6, b)
        # translucidez: a rocha presa aparece por dentro, até 16 px de profundidade
        seen = np.zeros(hx.size, bool)
        for t in range(2, 18, 2):
            seen |= ice_dens(hx, hy - t * 0.7, hz - t * 0.7, scale, rock=True) > 0
        b = np.where(seen & (b >= 3), 7, b)
        b = np.where(seen & (b < 3), 1, b)
        g = ((np.round(hx + hy * 2 + hz).astype(int) % 23) < 2) & (hash2((hx // 10).astype(int), (hz // 10).astype(int), 105) < 0.5)
        b = np.where(g & (b >= 3) & ~seen, 6, b)
        return b.astype(np.uint8)
    return shade


def ice_block(scale=1.0):
    v = Volume(144, 132, 70, 112, 0, 100, lambda X, Y, Z: ice_dens(X, Y, Z, scale), ice_shade_fn(scale))
    idx = v.render()
    feet = {1.0: [(dx, dy) for dx in (-2, -1, 0, 1) for dy in (0, -1)], 0.72: [(dx, dy) for dx in (-1, 0, 1)
                                                                            for dy in (0, -1)],
            0.45: [(-1, 0), (0, 0)]}
    return idx, dict(foot=(70, 112), tiles=feet.get(scale, []), size=(4, 2), name="Gelo-portão")


# =================================================================================================================
# CRATERA DE IMPACTO: borda elevada irregular, ejeção em volta, bacia rebaixada, rampa até o buraco no fundo
# =================================================================================================================
CR = 44            # raio da crista (px): a bacia ocupa os 3×3 tiles
RIM = 9
DEPTH = 19
ICE_LEVELS = [3, -6, -14, -21, None]          # superfície do gelo em cada etapa (None = sem gelo)


RAMP_Y0, RAMP_Y1 = 62, -2


def _ramp_path(X, Y):
    """Distância horizontal até o eixo da rampa e a altura dela ali. Ela corta a borda sul (um entalhe) e desce
    em ~0,6 de inclinação até entrar no buraco do fundo: de frente pra câmera, então aparece."""
    t = np.clip((RAMP_Y0 - Y) / (RAMP_Y0 - RAMP_Y1), 0, 1)
    cx = 5 * np.sin(t * 2.4)
    zr = 1.0 - (DEPTH + 13) * t ** 1.1
    return np.abs(X - cx), zr, t


def crater_h(X, Y, mask=False):
    ang = np.arctan2(Y, X)
    warp = 1 + 0.07 * np.sin(3 * ang + 0.7) + 0.05 * np.sin(5 * ang + 2) + 0.06 * fbm(X, Y, 12, 111, 2)
    r = np.sqrt(X ** 2 + (Y * 1.12) ** 2) / warp
    inner = RIM - (RIM + DEPTH) * np.clip(1 - (r / CR) ** 2.4, 0, 1)
    outer = RIM * np.exp(-np.clip(r - CR, 0, None) / 11)
    h = np.where(r < CR, inner, outer)
    h = h + (2.2 * fbm(X, Y, 6, 112, 2) + 1.5 * np.clip(1 - np.abs(r - CR) / 10, 0, 1) * fbm(X, Y, 3, 113, 1)) \
        * (r < CR + 8)
    # blocos ejetados na borda e fora dela
    rng = np.random.default_rng(114)
    for _ in range(26):
        a = rng.uniform(0, 2 * math.pi)
        rr = CR + rng.uniform(-2, 30)
        bx, by = math.cos(a) * rr, math.sin(a) * rr / 1.12
        s = rng.uniform(2.5, 5.5)
        bump = s * 1.2 * np.clip(1 - ((X - bx) ** 2 + (Y - by) ** 2) / s ** 2, 0, None) ** 0.5
        h = np.maximum(h, np.where(bump > 0, outer_at(X, Y, r) + bump, -99))
    # buraco no fundo (a boca da caverna)
    pit = np.sqrt((X / 13) ** 2 + ((Y + 4) / 9) ** 2) + 0.12 * fbm(X, Y, 4, 115, 1)
    h = np.where(pit < 1, -DEPTH - 60, h)
    # rampa: um corte liso descendo da borda sul até dentro do buraco
    ax, zr, t = _ramp_path(X, Y)
    on = (ax < 6.5) & (Y > RAMP_Y1 - 6) & (Y < RAMP_Y0)
    h = np.where(on, np.where(t < 1, np.minimum(zr, h), h), h)
    wall = (ax >= 6.5) & (ax < 9) & (Y > 20) & (Y < RAMP_Y0) & (h > zr)    # beirada do entalhe
    h = np.where(wall, np.maximum(zr + 0.5, np.minimum(h, zr + (ax - 6.5) * 4)), h)
    # fora da borda o terreno some no chão (o sprite fica transparente; a ejeção é decalque à parte)
    cut = (r > CR + 6) & (h < 1.8 + 1.2 * fbm(X, Y, 5, 119, 1)) & ~on
    if mask:                                    # onde existe rocha abaixo do chão: só na bacia e no entalhe
        return (r < CR + 1) | on
    return np.where(cut, -1000, h)


def outer_at(X, Y, r):
    return RIM * np.exp(-np.clip(r - CR, 0, None) / 11)


def crater_dens_fn(level):
    def dens(X, Y, Z):
        h = crater_h(X, Y)
        below = crater_h(X, Y, mask=True)
        d = np.where((Z > -1.5) | below, h - Z, -1)
        if level is not None:
            ang = np.arctan2(Y, X)
            r = np.sqrt(X ** 2 + (Y * 1.12) ** 2)
            ice = (Z < level) & (r < CR + 2) & (Z > h - 0.5)
            d = np.where(ice, np.maximum(d, level - Z), d)
        return np.where(h < -999, -1, d)
    return dens


def crater_shade_fn(level, marks):
    def shade(hx, hy, hz, nrm, lit):
        h = crater_h(hx, hy)
        is_ice = (level is not None) & (hz > h + 0.6)
        b = bands(nrm @ L, lit)
        r = np.sqrt(hx ** 2 + (hy * 1.12) ** 2)
        # rocha: parede de dentro mais escura, borda e ejeção claras
        b = np.where((r < CR - 4) & (hz < -4), np.minimum(b, 3), b)
        deep = hz < -DEPTH - 3                                         # dentro do buraco: escurece com a profundidade
        b = np.where(deep, np.where(hz < -DEPTH - 14, 8, 0), b)
        sp = hash2(np.round(hx).astype(int), np.round(hy).astype(int), 116)
        b = np.where((sp < 0.06) & (b > 1) & ~deep, b - 1, b)
        b = np.where((sp > 0.97) & (b >= 3) & ~deep, 5, b)
        # rampa: degraus de metal (a mesma família da crater_ramp de hoje)
        ax, zr, t = _ramp_path(hx, hy)
        ramp = (ax < 5.5) & (np.abs(hz - zr) < 1.5) & (t > 0.02)
        step = (np.round(hy).astype(int) % 3) == 0
        b = np.where(ramp, np.where(step, 19, 18), b)
        b = np.where(ramp & (ax > 4.2), 19, b)
        post = (np.abs(ax - 7.5) < 1.3) & (hy > 52) & (hy < 60) & (hz > zr - 0.5)
        b = np.where(post, 20, b)
        b = np.where(ramp & deep, 8, b)
        # marcas do gelo nas paredes (os níveis por onde ele já passou)
        for lv in marks:
            mk = (np.abs(hz - lv) < 0.8) & (r < CR) & ~ramp & ~deep
            b = np.where(mk & ~is_ice, 16, b)
            b = np.where((np.abs(hz - (lv - 1.2)) < 0.5) & (r < CR) & ~ramp & ~deep & ~is_ice, 1, b)
        # gelo: superfície lisa (rampa ICE em 10..17), rachaduras, brilho
        if level is not None:
            ib = np.where(lit, 14, 12)
            gl = ((np.round(hx + hy * 2).astype(int) % 19) < 2) & (hash2((hx // 9).astype(int), (hy // 9).astype(int), 117) < 0.55)
            ib = np.where(gl, 16, ib)
            from regions_core import voronoi
            _, edge, _ = voronoi(hx + 300, hy + 300, 16, 118)
            ib = np.where((edge < 0.9) & (level < 0), 11, ib)
            rim_ice = r > CR - 8 - 2.5 * (level + 22) / 25
            ib = np.where(rim_ice & (ib >= 14), 15, ib)
            b = np.where(is_ice, ib, b)
        return b.astype(np.uint8)
    return shade


def crater(stage):
    """stage 0..4: 0 = tampa cheia, 1..3 = o gelo baixando (marcas nas paredes), 4 = vazia, rampa exposta."""
    level = ICE_LEVELS[stage]
    marks = [lv for lv in ICE_LEVELS[:stage] if lv is not None]
    v = Volume(168, 150, 84, 70, -DEPTH - 62, RIM + 8, crater_dens_fn(level), crater_shade_fn(level, marks),
               soft_edge=True, stop=lambda X, Y, Z: (Z < -1) & ~crater_h(X, Y, mask=True))
    idx = v.render()
    return idx, dict(anchor=(84, 70), tiles=[(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)], size=(3, 3),
                     name="Cratera de impacto")


def ejecta(seed=121):
    """Decalque de chão em volta da cratera (não colide): um manto de material ejetado, irregular e quebrado,
    mais denso perto da borda, e pedrisco/blocos espalhados que rareiam pra fora. Nada de raio desenhado."""
    w, h = 256, 216
    xs, ys = grid(w, h)
    X, Y = xs - w / 2, ys - h / 2
    r = np.sqrt(X ** 2 + (Y * 1.12) ** 2)
    a = np.full((h, w), 255, np.uint8)
    n = fbm(X, Y, 16, seed, 3)
    blanket = (r > 42) & (r < 64 + 36 * n) & (fbm(X, Y, 7, seed + 1, 2) > -0.05)
    a[blanket] = 4
    a[blanket & (fbm(X, Y, 5, seed + 2, 1) > 0.22)] = 5
    sp = hash2(xs, ys, seed + 3)
    dens = 0.05 * np.clip(1 - (r - 44) / 70, 0, 1) ** 2
    peb = (r > 44) & (sp < dens)
    a[peb] = 2
    a[np.roll(peb, 1, 0) & (a == 255)] = 1
    big = (r > 50) & (sp > 1 - dens * 0.15)
    for dy in (0, 1):
        for dx in (0, 1):
            a[np.roll(np.roll(big, dy, 0), dx, 1)] = 3 if dy == 0 else 1
    return a
