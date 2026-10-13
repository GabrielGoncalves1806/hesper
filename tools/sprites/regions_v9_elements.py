"""v9 · elementos novos das regiões (PROPOSTA, pendente do dono): decalques de chão, decoração solta com altura,
formações pequenas e o musgo do Verde+. Tudo em ÍNDICE, igual ao resto das regiões (ver regions_core):

    0..7 rampa da região · 8 contorno #1b1630 · 9 sombra (preto, alfa fixo) · 255 transparente
    musgo (Verde+): overlay à parte, 0..3 = rampa fixa MOSS (não muda com estágio: só aparece no Verde)

Regras do dono: natural (nada de cara de construção), sem ossada nem nada biológico, e funciona nos 4 estágios só
trocando a paleta. Os volumes saem do mesmo renderizador das formações (regions_volume.Volume).
Determinístico: só hash fixo e np.random.default_rng(seed).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

import regions_core as R
from regions_core import fbm, grid, hash2, vnoise
from regions_volume import L, Volume, bands, fbm3, _hexd, sandstone

MOSS = ["#22331f", "#38502e", "#5c7d45", "#75985a"]          # a mesma família do musgo da cobertura do Verde


def _crop(a, pad=0):
    ys, xs = np.nonzero(a != 255)
    if len(xs) == 0:
        return a
    return a[max(0, ys.min() - pad):ys.max() + 1 + pad, max(0, xs.min() - pad):xs.max() + 1 + pad]


def _blob(w, h, seed, k=0.9, cell=None):
    """Envelope orgânico (máscara) de w×h: elipse torcida por ruído."""
    xs, ys = grid(w, h)
    ex = (xs - w / 2) / (w / 2)
    ey = (ys - h / 2) / (h / 2)
    n = fbm(xs + seed * 37, ys + seed * 11, cell or min(w, h) / 2.5, seed, 3)
    return (1 - (ex * ex + ey * ey)) + k * (n - 0.5) > 0.18


def _shift(a, dy, dx, fill=False):
    out = np.full_like(a, fill)
    h, w = a.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = a[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)]
    return out


# =================================================================================================================
# DECALQUES (chão, não colidem) · rampa BASE da região onde caem
# =================================================================================================================
def d_vein(seed, length=110):
    """Planalto · veio mineral exposto: faixa clara (mineral mais duro, fica em relevo) que serpenteia, com borda
    escura embaixo, trechos que somem na terra e galhos finos. Não é rachadura: é uma linha CLARA."""
    rng = np.random.default_rng(seed)
    w, h = length + 24, 90
    a = np.full((h, w), 255, np.uint8)
    x, y = 12.0, h / 2 + rng.uniform(-8, 8)
    ang = rng.uniform(-0.35, 0.35)
    path = []
    for i in range(length):
        ang = max(-0.6, min(0.6, ang + rng.normal(0, 0.06)))
        x += math.cos(ang)
        y += math.sin(ang)
        f = i / length
        wid = 1 + (1 if 0.12 < f < 0.88 else 0) + (1 if 0.3 < f < 0.7 else 0) \
            + (1 if 0.4 < f < 0.6 and hash2(i // 9, 0, seed) < .6 else 0)
        path.append((x, y, wid, i))
    for k in range(int(rng.integers(2, 4))):                       # galhos finos
        j = int(rng.uniform(0.2, 0.8) * length)
        bx, by, _, _ = path[j]
        ba = ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1)
        for i in range(int(rng.uniform(10, 26))):
            ba += rng.normal(0, 0.1)
            bx += math.cos(ba)
            by += math.sin(ba)
            path.append((bx, by, 1, -1))
    for (px, py, wid, i) in path:
        if i >= 0 and hash2(i // 7, 1, seed) < 0.10:                # trecho enterrado
            continue
        ix, iy = int(px), int(py)
        for d in range(wid):
            if 0 <= ix < w and 0 <= iy + d < h - 2 and a[iy + d, ix] != 5:
                a[iy + d, ix] = 5 if d == 0 else 4
    m = a != 255
    a[_shift(m, 1, 0) & ~m] = 2                                     # degrau escuro embaixo (o veio fica em relevo)
    sp = hash2(*grid(w, h), seed + 3)
    a[m & (sp < 0.10)] = 6                                          # grão do mineral
    return _crop(a)


def d_oxide(seed, w=72, h=46):
    """Planalto · manchas de oxidação: halo de ferrugem com 2 ou 3 anéis finos e tortos (Liesegang), quebrados,
    abertos de um lado. Baixo contraste: é mancha no chão, não desenho."""
    xs, ys = grid(w, h)
    ex = (xs - w / 2) / (w / 2)
    ey = (ys - h / 2) / (h / 2)
    r = np.sqrt(ex * ex + ey * ey) + 0.34 * (fbm(xs + seed, ys, 12, seed, 2) - 0.5)
    a = np.full((h, w), 255, np.uint8)
    open_side = fbm(xs, ys + seed, 16, seed + 1, 2) < 0.40
    body = (r < 0.95) & ~open_side
    stain = body & (fbm(xs, ys, 6, seed + 3, 2) > 0.45) & (r < 0.8)
    a[stain] = 2
    ring = (r * 5) % 2.0
    rings = body & (ring < 0.32) & (r > 0.25) & (hash2(xs // 3, ys // 3, seed + 4) < 0.8)
    a[rings] = 7
    a[_shift(rings, 1, 0) & body & ~rings] = 4
    a[body & (hash2(xs, ys, seed + 2) < 0.05) & (a == 255)] = 7
    return _crop(a)


def d_saltpoly(seed, w=120, h=72):
    """Salar · polígonos de sal miúdos (~14 px) com a borda empurrada pra cima: crista clara, sombra embaixo e fenda
    no meio de algumas. Vira um remendo de 'favo torto' por cima dos polígonos grandes da textura."""
    xs, ys = grid(w, h)
    env = _blob(w, h, seed, 1.1)
    wx = xs + 3 * (vnoise(xs, ys, 9, seed + 1) - 0.5)
    wy = ys + 3 * (vnoise(xs, ys, 9, seed + 2) - 0.5)
    _, edge, _ = R.voronoi(wx + seed * 300, wy, 14, seed + 3, None, jitter=0.9)
    a = np.full((h, w), 255, np.uint8)
    ridge = env & (edge < 1.6)
    a[ridge] = 5
    a[ridge & (edge < 0.5) & (hash2(xs // 4, ys // 4, seed + 4) < 0.5)] = 7
    a[_shift(ridge, 1, 0) & ~ridge & env] = 2
    a[_shift(ridge, -1, 0) & ~ridge & env & (hash2(xs, ys, seed + 5) < 0.5)] = 4
    return _crop(a)


def d_efflor(seed, w=64, h=40):
    """Salar · eflorescência: rosetas de sal (raios curtos saindo de um miolo), em grupinho."""
    rng = np.random.default_rng(seed)
    a = np.full((h, w), 255, np.uint8)
    for _ in range(int(rng.integers(4, 8))):
        cx, cy = rng.uniform(9, w - 9), rng.uniform(7, h - 7)
        rr = rng.uniform(4, 9)
        for k in range(int(rng.integers(7, 12))):
            ang = k / 9 * 2 * math.pi + rng.uniform(-0.3, 0.3)
            ln = rr * rng.uniform(0.5, 1.0)
            for t in np.arange(0, ln, 0.7):
                x, y = int(cx + math.cos(ang) * t), int(cy + math.sin(ang) * t * 0.62)
                if 0 <= x < w and 0 <= y < h - 1:
                    a[y, x] = 7 if t < ln * 0.5 else 5
        a[int(cy), int(cx)] = 7
        a[int(cy), int(cx) + 1] = 7
    m = a != 255
    a[_shift(m, 1, 0) & ~m] = 2
    return _crop(a)


def d_fumarole(seed, w=60, h=38):
    """Basalto · respiro de fumarola apagada: boca escura, anel de crosta clara (mineral depositado) manchada de
    ferrugem e um halo de pintas de óxido que rareia pra fora. Sem amarelo: fica na rampa do basalto."""
    xs, ys = grid(w, h)
    ex = (xs - w / 2) / (w / 2)
    ey = (ys - h / 2) / (h / 2)
    r = np.sqrt(ex * ex + ey * ey) + 0.30 * (fbm(xs + seed * 7, ys, 8, seed, 2) - 0.5)
    sp = hash2(xs, ys, seed + 1)
    a = np.full((h, w), 255, np.uint8)
    halo = (r < 1.0) & (sp < 0.45 * np.clip(1 - r, 0, 1) ** 1.2)
    a[halo] = 7
    a[halo & (sp < 0.06)] = 6
    crust = r < 0.52
    a[crust] = 5
    a[crust & (fbm(xs, ys, 4, seed + 2, 1) > 0.55)] = 4
    a[crust & (r > 0.40) & (sp < 0.3)] = 7
    mouth = r < 0.20
    a[mouth] = 0
    a[_shift(mouth, -1, 0) & ~mouth & crust] = 1                    # parede de dentro da boca
    a[_shift(mouth, 1, 0) & ~mouth] = 4                             # lábio de baixo, iluminado
    return _crop(a)


def d_ropy(seed, w=104, h=58):
    """Basalto · lava em corda (pahoehoe): a frente de um lóbulo de lava lisa, com dobras em arco (a convexidade
    pro lado em que ela escorreu). Só a frente aparece: crista clara, sulco escuro, borda baixa no fim."""
    xs, ys = grid(w, h)
    env = _blob(w, h, seed, 0.7)
    cx = -w * (0.35 + 0.25 * hash2(seed, 0, 1))
    cy = h / 2 + h * (hash2(seed, 0, 2) - 0.5)
    d = np.sqrt((xs - cx) ** 2 + ((ys - cy) / 0.8) ** 2) + 6 * (fbm(xs, ys, 12, seed + 1, 2) - 0.5)
    ph = d % 6.0
    a = np.full((h, w), 255, np.uint8)
    keep = env & (fbm(xs, ys, 9, seed + 3, 2) > 0.36)                 # dobras somem por baixo da poeira
    a[keep & (ph < 1.0)] = 5
    a[keep & (ph > 1.0) & (ph < 1.9)] = 4
    a[keep & (ph > 5.2)] = 1
    return _crop(a)


def d_icepoly(seed, w=132, h=82):
    """Faixa gelada · solo poligonal (permafrost): polígonos de ~22 px separados por cunha de gelo (sulco escuro com
    gelo claro dentro), borda levantada iluminada."""
    xs, ys = grid(w, h)
    env = _blob(w, h, seed, 1.0)
    wx = xs + 4 * (vnoise(xs, ys, 14, seed + 1) - 0.5)
    wy = ys + 4 * (vnoise(xs, ys, 14, seed + 2) - 0.5)
    _, edge, _ = R.voronoi(wx + seed * 300, wy * 1.3, 22, seed + 3, None, jitter=0.85)
    a = np.full((h, w), 255, np.uint8)
    trough = env & (edge < 2.0)
    a[trough] = 1
    a[trough & (edge < 0.7) & (hash2(xs // 3, ys // 3, seed + 4) < 0.65)] = 7
    a[_shift(trough, 1, 0) & ~trough & env] = 5
    a[_shift(trough, -1, 0) & ~trough & env & (hash2(xs, ys, seed + 5) < 0.6)] = 2
    return _crop(a)


def d_rime(seed, w=80, h=50):
    """Faixa gelada · geada em pena: galhos de cristal de gelo que se ramificam a partir de 2 a 4 pontos."""
    rng = np.random.default_rng(seed)
    a = np.full((h, w), 255, np.uint8)

    def branch(x, y, ang, ln, depth):
        for t in range(int(ln)):
            x += math.cos(ang)
            y += math.sin(ang) * 0.62
            ix, iy = int(x), int(y)
            if not (0 <= ix < w and 0 <= iy < h - 1):
                return
            a[iy, ix] = 7 if depth == 0 else 5
            if depth < 2 and t > 2 and t % 3 == 0:
                for s in (-1, 1):
                    if hash2(ix, iy * 3 + s, seed) < 0.75:
                        branch(x, y, ang + s * 0.9, ln * 0.35, depth + 1)

    for _ in range(int(rng.integers(2, 5))):
        x, y = rng.uniform(14, w - 14), rng.uniform(12, h - 12)
        for k in range(int(rng.integers(3, 6))):
            branch(x, y, rng.uniform(0, 2 * math.pi), rng.uniform(14, 28), 0)
    m = a != 255
    a[_shift(m, 1, 0) & ~m & (hash2(*grid(w, h), seed + 1) < 0.5)] = 2
    return _crop(a)


def d_trail(seed, length=150):
    """Leito seco · rastro de seixo (pedra que o vento empurrou no lodo do lago raso, antes de secar): sulco raso
    e comprido da largura da pedra, com curva suave, e o seixo achatado parado no fim. Nada vivo."""
    rng = np.random.default_rng(seed)
    w, h = length + 24, 160
    a = np.full((h, w), 255, np.uint8)
    x, y = 6.0, h / 2
    ang = rng.uniform(-0.2, 0.2)
    turn = rng.choice([-1, 1]) * rng.uniform(0.004, 0.009)
    for i in range(length):
        ang = max(-0.45, min(0.45, ang + turn + rng.normal(0, 0.006)))
        x += math.cos(ang)
        y += math.sin(ang)
        ix, iy = int(x), int(y)
        if i < 14 and i % 3:                                        # começo some
            continue
        if a[iy - 1, ix] == 255:
            a[iy - 1, ix] = 1                                       # parede de cima do sulco (sombra)
        a[iy, ix] = 2
        a[iy + 1, ix] = 2
        if i > length * 0.25:
            a[iy + 2, ix] = 2
        if a[iy + 3, ix] == 255:
            a[iy + 3, ix] = 4                                       # beirada de baixo, iluminada
    sx, sy = int(x) + 4, int(y) + 1                                 # o seixo no fim
    pw, ph = int(rng.integers(8, 11)), int(rng.integers(5, 7))
    for yy in range(ph):
        for xx in range(pw):
            corner = (xx in (0, pw - 1)) and (yy in (0, ph - 1))
            if corner:
                continue
            a[sy - ph // 2 + yy, sx - pw // 2 + xx] = 5 if yy == 0 else (4 if yy < ph - 2 else 1)
    for xx in range(1, pw):
        a[sy - ph // 2 + ph, sx - pw // 2 + xx] = 0                 # sombrinha
    return _crop(a)


def d_ripples(seed, w=100, h=60):
    """Leito seco · marcas de onda fossilizadas no silte: cristas paralelas onduladas que se bifurcam."""
    xs, ys = grid(w, h)
    env = _blob(w, h, seed, 1.0)
    ang = 0.5 + 0.6 * hash2(seed, 0, 3)
    u = xs * math.cos(ang) + ys * math.sin(ang)
    v = -xs * math.sin(ang) + ys * math.cos(ang)
    ph = (u + 2.2 * np.sin(v / 9 + seed) + 3 * (fbm(xs, ys, 16, seed + 1, 2) - 0.5)) % 6.0
    a = np.full((h, w), 255, np.uint8)
    crest = env & (ph < 1.0)
    a[crest] = 4
    a[env & (ph > 1.0) & (ph < 2.0)] = 2
    a[crest & (hash2(xs, ys // 2, seed + 2) < 0.12)] = 255           # quebras
    fade = env & (fbm(xs, ys, 10, seed + 5, 2) < 0.36)
    a[fade] = 255
    return _crop(a)


def decal_set_v9():
    out = {}
    for v in range(3):
        out[f"vein_{v}"] = d_vein(900 + v, (110, 86, 130)[v])
        out[f"oxide_{v}"] = d_oxide(910 + v, (72, 56, 88)[v], (46, 38, 54)[v])
        out[f"saltpoly_{v}"] = d_saltpoly(920 + v, (120, 96, 140)[v], (72, 60, 84)[v])
        out[f"efflor_{v}"] = d_efflor(930 + v)
        out[f"fumarole_{v}"] = d_fumarole(940 + v, (60, 48, 70)[v], (38, 32, 44)[v])
        out[f"ropy_{v}"] = d_ropy(950 + v, (104, 84, 124)[v], (58, 50, 66)[v])
        out[f"icepoly_{v}"] = d_icepoly(960 + v, (132, 108, 152)[v], (82, 68, 92)[v])
        out[f"rime_{v}"] = d_rime(970 + v)
        out[f"trail_{v}"] = d_trail(980 + v, (150, 110, 180)[v])
        out[f"ripples_{v}"] = d_ripples(990 + v, (100, 84, 120)[v], (60, 50, 70)[v])
    return out


# =================================================================================================================
# DECORAÇÃO SOLTA COM ALTURA (não colide, ordenada pelo pé) · volumes pequenos
# =================================================================================================================
def _vol(w, h, ox, oy, zmax, dens, shade, shadow=True):
    v = Volume(w, h, ox, oy, 0, zmax, dens, shade, ground_shadow=shadow)
    return v.render()


def _rock_shade(seed, oxide=False):
    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        sp = hash2(np.round(hx).astype(int), np.round(hy * 2 + hz).astype(int), seed)
        b = np.where((sp < 0.05) & (b > 1), b - 1, b)
        if oxide:
            b = np.where((sp > 0.97) & (b >= 2), 7, b)
        return b.astype(np.uint8)
    return shade


def _ell(X, Y, Z, c, r, noise=0.0, seed=0, cell=6):
    cx, cy, cz = c
    rx, ry, rz = r
    d = 1 - np.sqrt(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2 + ((Z - cz) / rz) ** 2)
    if noise:
        d = d + noise * fbm3(X, Y, Z, cell, seed, 2)
    return d * min(rx, ry, rz)


def pebbles(seed):
    """Planalto/leito · seixos: 2 a 4 pedrinhas roladas e achatadas, de tamanhos diferentes."""
    rng = np.random.default_rng(seed)
    ps = []
    for k in range(int(rng.integers(2, 5))):
        r = rng.uniform(2.6, 5.0) if k else rng.uniform(4.5, 6.0)
        ps.append(((rng.uniform(-8, 8), rng.uniform(-3, 3), r * 0.55), (r * rng.uniform(1.0, 1.4), r, r * 0.6)))

    def dens(X, Y, Z):
        d = np.full(X.shape, -9.0)
        for k, (c, r) in enumerate(ps):
            d = np.maximum(d, _ell(X, Y, Z, c, r, 0.25, seed + k, 4))
        return d
    return _crop(_vol(30, 20, 15, 13, 10, dens, _rock_shade(seed)))


def boulder(seed):
    """Planalto · pedra média, roída pelo vento: corpo achatado e encaroçado, uma face reta de lasca que saiu."""
    rng = np.random.default_rng(seed)
    rx, ry, rz = rng.uniform(10.5, 12.5), rng.uniform(7.5, 9), rng.uniform(6.5, 8.5)
    cut_a = rng.uniform(0, 2 * math.pi)
    nx, ny = math.cos(cut_a), math.sin(cut_a) * 0.6

    def dens(X, Y, Z):
        d = _ell(X, Y, Z, (0, 0, rz * 0.6), (rx, ry, rz), 0.55, seed, 6)
        cut = (rx * 0.66) - (X * nx + Y * ny + (Z - rz * 0.6) * 0.3)
        return np.minimum(d, cut)
    return _crop(_vol(32, 28, 16, 20, 20, dens, _rock_shade(seed + 1)))


def slabs(seed, thick=(2, 3), n=(2, 4), r=(5.5, 9.0)):
    """Lajes lascadas: 2 a 4 placas chatas e angulosas deitadas, uma meio por cima da outra (rocha que esfoliou /
    crosta que soltou). Desenho 2D: face de cima chapada com a quina de trás clara, espessura escura na frente,
    sombra no chão e contorno."""
    rng = np.random.default_rng(seed)
    w, h = 34, 24
    a = np.full((h, w), 255, np.uint8)
    k_n = int(rng.integers(n[0], n[1] + 1))
    plates = []
    for k in range(k_n):
        cx, cy = 17 + rng.uniform(-8, 8), 12 + rng.uniform(-3, 3)
        rr = rng.uniform(*r) * (1.0 if k == 0 else 0.8)
        nv = int(rng.integers(5, 7))
        angs = np.sort(rng.uniform(0, 2 * math.pi, nv))
        poly = [(cx + math.cos(t) * rr * rng.uniform(0.75, 1.0), cy + math.sin(t) * rr * 0.55 * rng.uniform(0.75, 1.0))
                for t in angs]
        plates.append((cy - k * 0.5, poly, int(rng.integers(thick[0], thick[1] + 1))))
    plates.sort(key=lambda p: p[0])
    for _, poly, th in plates:
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).polygon(poly, fill=1)
        m = np.array(im) > 0
        side = np.zeros_like(m)
        for t in range(1, th + 1):
            side |= _shift(m, t, 0)
        side &= ~m
        sh = _shift(m | side, 1, 1) & ~(m | side)
        a[sh & (a == 255)] = 9
        a[side] = 2
        a[side & ~_shift(side, -1, 0)] = 1
        a[m] = 4
        a[m & ~_shift(m, 1, 0)] = 5                                    # quina de trás, iluminada
        a[m & (hash2(*grid(w, h), seed + len(poly)) < 0.05)] = 3
        body = m | side
        ring = np.zeros_like(body)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ring |= _shift(body, dy, dx)
        a[ring & ~body] = 8
    return _crop(a)


def salt_mound(seed):
    """Salar · montinho de sal em couve-flor (eflorescência que cresceu): bolotas encostadas, topo branco."""
    rng = np.random.default_rng(seed)
    bs = [((rng.uniform(-6, 6), rng.uniform(-2.5, 2.5)), rng.uniform(2.5, 4.5)) for _ in range(int(rng.integers(5, 9)))]
    bs.append(((0, 0), rng.uniform(4.5, 5.5)))

    def hgt(X, Y):
        h = np.full(X.shape, -1.0)
        for (cx, cy), r in bs:
            d2 = r * r - (X - cx) ** 2 - ((Y - cy) * 1.3) ** 2
            h = np.maximum(h, np.where(d2 > 0, np.sqrt(np.maximum(d2, 0)) * 1.1 + (r - 2.5) * 0.8, -1))
        return h

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        b = np.where(nrm[:, 2] > 0.7, np.maximum(b, 4), b)
        b = np.where((nrm[:, 2] > 0.85) & lit, 7, b)
        return np.clip(b, 1, 7).astype(np.uint8)
    return _crop(_vol(26, 20, 13, 14, 12, lambda X, Y, Z: hgt(X, Y) - Z, shade))


def bombs(seed):
    """Basalto · bombas vulcânicas / escória: pedras porosas, uma em fuso (esfriou girando no ar), com buraquinhos
    (vesículas) espalhados sem padrão e uma pinta de óxido."""
    rng = np.random.default_rng(seed)
    rs = [((0.0, 0.0), (rng.uniform(8, 10), rng.uniform(5.5, 6.5), rng.uniform(5, 6.5)), rng.uniform(-0.4, 0.4))]
    for k in range(int(rng.integers(1, 3))):
        r = rng.uniform(3, 4.5)
        rs.append(((rng.choice([-1, 1]) * rng.uniform(9, 11), rng.uniform(-2, 3)), (r, r * 0.9, r * 0.8), 0.0))

    def dens(X, Y, Z):
        d = np.full(X.shape, -9.0)
        for k, ((cx, cy), (rx, ry, rz), a) in enumerate(rs):
            ca, sa = math.cos(a), math.sin(a)
            u, v = (X - cx) * ca + (Y - cy) * sa, -(X - cx) * sa + (Y - cy) * ca
            d = np.maximum(d, _ell(u, v, Z, (0, 0, rz * 0.8), (rx, ry, rz), 0.45, seed + k, 3))
        return d

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        b = np.minimum(b, 4)
        ves = fbm3(hx, hy, hz, 1.6, seed + 9, 1) > 0.32
        b = np.where(ves, np.maximum(b - 2, 0), b)
        rust = fbm3(hx, hy, hz, 4, seed + 4, 1) > 0.36
        b = np.where(rust & (b >= 2) & ~ves, 7, b)
        return b.astype(np.uint8)
    return _crop(_vol(32, 22, 16, 15, 14, dens, shade))


def column_stub(seed):
    """Basalto · toco de coluna hexagonal: 1 a 3 prismas curtos, topo reto (o hexágono claro tem que ler) com uma
    quina quebrada, junta transversal na lateral."""
    rng = np.random.default_rng(seed)
    cols = []
    n = int(rng.integers(1, 4))
    for k in range(n):
        ap = rng.uniform(4.6, 5.4) if k else rng.uniform(6.0, 7.0)
        ang = k * 2.4 + rng.uniform(-0.3, 0.3)
        dist = 0 if k == 0 else 2 * ap + 1.6
        cols.append(((math.cos(ang) * dist, math.sin(ang) * dist * 0.45), ap,
                     rng.uniform(8, 12) if k == 0 else rng.uniform(4, 8),
                     (rng.uniform(-0.12, 0.12), rng.uniform(-0.1, 0.05)), rng.uniform(0, 6.28)))

    def dens(X, Y, Z, which=False):
        best = np.full(X.shape, -1e9)
        bid = np.full(X.shape, -1)
        for i, ((cx, cy), ap, hgt, (tx, ty), ca) in enumerate(cols):
            top = hgt + tx * (X - cx) + ty * (Y - cy)
            chip = (hgt + ap * 0.9) - ((X - cx) * math.cos(ca) + (Y - cy) * math.sin(ca)) * 0.9 - Z   # quina quebrada
            d = np.minimum(np.minimum(_hexd(X - cx, Y - cy, ap), top - Z), chip)
            m = d > best
            best, bid = np.where(m, d, best), np.where(m, i, bid)
        return bid if which else best + 0.25 * fbm3(X, Y, Z, 3, seed)

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        up = nrm[:, 2] > 0.85
        b = np.where(up, np.where(lit, 5, 4), np.where(nrm[:, 0] < -0.3, 3, np.where(nrm[:, 1] > 0.5, 2, 1)))
        bid = dens(hx, hy, hz, which=True)
        for i, (_, _, hgt, _, _) in enumerate(cols):
            joint = (bid == i) & ~up & (np.abs(hz - hgt * 0.5) < 0.6)
            b = np.where(joint, 0, b)
        sp = hash2(np.round(hx).astype(int), np.round(hy * 2 + hz).astype(int), seed + 2)
        b = np.where((sp > 0.98) & ~up & (b >= 2), 6, b)
        return b.astype(np.uint8)
    return _crop(_vol(32, 32, 16, 23, 20, dens, shade))


def _ice_shade(seed):
    def shade(hx, hy, hz, nrm, lit):
        lam = nrm @ L
        b = np.where(lam > 0.72, 5, np.where(lam > 0.42, 4, np.where(lam > 0.12, 3, 2)))
        b = np.where(lit, b, np.maximum(b - 1, 1))
        hv = L + np.array([0, 0.7, 0.7])
        b = np.where(nrm @ (hv / np.linalg.norm(hv)) > 0.95, 6, b)
        g = ((np.round(hx + hz * 1.5).astype(int) % 9) == 0) & (b >= 3) & (hash2(np.round(hz).astype(int), 0, seed) < .4)
        b = np.where(g, 2, b)                                                  # estrias de sublimação
        return b.astype(np.uint8)
    return shade


def _blades(seed, n, hmin, hmax, spread, base_w):
    rng = np.random.default_rng(seed)
    bl = []
    for k in range(n):
        x = rng.uniform(-spread, spread)
        y = rng.uniform(-spread * 0.3, spread * 0.3)
        bl.append(((x, y), rng.uniform(hmin, hmax) * (1 - 0.35 * abs(x) / max(spread, 1)), base_w * rng.uniform(0.8, 1.2),
                   rng.uniform(-0.45, -0.2), rng.uniform(-0.15, 0.15)))         # inclinam pro norte (pro sol)
    return bl


def _blades_dens(bl, seed):
    def dens(X, Y, Z):
        d = np.full(X.shape, -9.0)
        for k, ((cx, cy), hgt, bw, lean_y, lean_x) in enumerate(bl):
            t = np.clip(Z / hgt, 0, 1.0)
            ax, ay = cx + lean_x * Z, cy + lean_y * Z
            half = bw * (1 - t) ** 0.6
            dd = np.minimum(half - np.sqrt(((X - ax) * 1.0) ** 2 + ((Y - ay) * 1.7) ** 2), hgt - Z)
            d = np.maximum(d, dd)
        return d + 0.4 * fbm3(X, Y, Z, 3, seed)
    return dens


def sharpen(idx):
    """Ponta de 1 px com contorno vira 'alfinete'. Aqui a ponta solta vira contorno e o contorno órfão some."""
    solid = (idx != 255) & (idx != 9) & (idx != 8)
    for _ in range(2):
        nb_l, nb_r, nb_u = _shift(solid, 0, 1), _shift(solid, 0, -1), _shift(solid, 1, 0)
        tip = solid & ~nb_l & ~nb_r & ~nb_u
        idx[tip] = 8
        solid &= ~tip
    near = np.zeros_like(solid)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        near |= _shift(solid, dy, dx)
    idx[(idx == 8) & ~near] = 255
    return idx


def penitentes(seed):
    """Faixa gelada · penitentes: lâminas de gelo afiadas pela sublimação, em grupinho, inclinadas pro sol."""
    bl = _blades(seed, int(np.random.default_rng(seed).integers(4, 7)), 9, 17, 9, 3.4)
    return _crop(sharpen(_vol(32, 32, 16, 27, 24, _blades_dens(bl, seed), _ice_shade(seed))))


def rimed_rock(seed):
    """Faixa gelada · pedra com crosta de geada: rocha escura embaixo, a geada (índice claro da rampa HILL da gelada)
    em cima e escorrendo de um lado."""
    rng = np.random.default_rng(seed)
    rx, ry, rz = rng.uniform(8.5, 11), rng.uniform(6.5, 8), rng.uniform(6.5, 9)
    second = rng.uniform() < 0.6

    def dens(X, Y, Z):
        d = _ell(X, Y, Z, (0, 0, rz * 0.55), (rx, ry, rz), 0.35, seed, 6)
        if second:
            d = np.maximum(d, _ell(X, Y, Z, (rx * 0.95, 2.5, 2.5), (4.2, 3.6, 3.4), 0.3, seed + 1, 4))
        return d

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        b = np.minimum(b, 3)
        frost = (nrm[:, 2] > 0.55 - 0.25 * (fbm(hx, hy, 4, seed + 2, 1) - 0.5) * 2) & (hz > 2)
        b = np.where(frost, np.where(lit, 5, 4), b)
        sp = hash2(np.round(hx).astype(int), np.round(hy + hz).astype(int), seed + 3)
        b = np.where(frost & (sp < 0.08), 7, b)
        return b.astype(np.uint8)
    return _crop(_vol(32, 26, 16, 18, 18, dens, shade))


def mud_curls(seed):
    """Leito seco · lascas de lama enroladas: plaquinhas finas de lodo seco com a borda de trás curvando pra cima.
    Desenho 2D: placa chapada, a beirada de trás levantada e iluminada (vê-se a parte de dentro), sombra na frente."""
    rng = np.random.default_rng(seed)
    w, h = 32, 16
    a = np.full((h, w), 255, np.uint8)
    xs, ys = grid(w, h)
    chips = []
    for k in range(int(rng.integers(3, 6))):
        chips.append((rng.uniform(5, w - 5), rng.uniform(5, h - 4), rng.uniform(3.2, 5.2), rng.uniform(2.0, 3.0)))
    chips.sort(key=lambda c: c[1])                                    # de trás pra frente
    for k, (cx, cy, rx, ry) in enumerate(chips):
        e = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 + 0.5 * (hash2(xs, ys, seed + k) - 0.5) * 0.3
        m = e < 1
        if not m.any():
            continue
        a[_shift(m, 1, 0) & ~m & (a == 255)] = 9                       # sombra no chão
        a[m] = 3
        top = m & ~_shift(m, 1, 0)
        a[top] = 8                                                    # a beirada de cima
        a[_shift(top, 1, 0) & m] = 5                                  # dentro da borda que enrola: claro
        a[_shift(top, 2, 0) & m & (ys > cy - ry * 0.3)] = 4
        bot = m & ~_shift(m, -1, 0)
        a[bot] = 1                                                    # frente (a espessura da lasca)
        side = m & (~_shift(m, 0, 1) | ~_shift(m, 0, -1)) & ~top
        a[side] = 8
    return _crop(a)


def moss_overlay(idx, seed):
    """Verde+ · musgo por cima de uma pedra: só nas faces viradas pra cima (índices claros do topo) e escorrendo
    um pouco. Mesmo tamanho do sprite; 0..3 = rampa fixa MOSS, 8 = contorno, 255 = nada."""
    h, w = idx.shape
    xs, ys = grid(w, h)
    solid = (idx != 255) & (idx != 9) & (idx != 8)
    top = np.zeros_like(solid)
    for x in range(w):
        col = np.nonzero(solid[:, x])[0]
        if len(col):
            top[col[0]:col[0] + 2 + int(hash2(x, 0, seed) * 3), x] = True
    n = fbm(xs, ys, 4, seed, 2)
    m = solid & (top | ((idx >= 4) & (idx <= 5) & (n > 0.5))) & (n > 0.34)
    out = np.full((h, w), 255, np.uint8)
    out[m] = 2
    out[m & (hash2(xs, ys, seed + 1) < 0.3)] = 3
    out[m & ~_shift(m, -1, 0)] = 1                                   # pé do tufo (escorre)
    out[m & ~_shift(m, 1, 0)] = 3                                    # topo do tufo
    return out


def decor_set_v9():
    """{nome: (índice, região, tabela)}"""
    out = {}
    for v in range(3):
        out[f"pebbles_{v}"] = (pebbles(1000 + v), "plateau", "HILL")
        out[f"boulder_{v}"] = (boulder(1010 + v), "plateau", "HILL")
        out[f"slabs_{v}"] = (slabs(1020 + v), "plateau", "HILL")
        out[f"salt_slabs_{v}"] = (slabs(1030 + v, (1, 2), (2, 4), (5.0, 8.0)), "salar", "BASE")
        out[f"salt_mound_{v}"] = (salt_mound(1040 + v), "salar", "BASE")
        out[f"bombs_{v}"] = (bombs(1050 + v), "basalt", "HILL")
        out[f"column_stub_{v}"] = (column_stub(1060 + v), "basalt", "HILL")
        out[f"penitentes_{v}"] = (penitentes(1070 + v), "frost", "ICE")
        out[f"rimed_rock_{v}"] = (rimed_rock(1080 + v), "frost", "HILL")
        out[f"mud_curls_{v}"] = (mud_curls(1090 + v), "bed", "BASE")
    return out


# =================================================================================================================
# FORMAÇÕES PEQUENAS (opcionais) · bloqueiam 1 a 3 tiles
# =================================================================================================================
def split_rock():
    """Planalto · pedra rachada: um matacão grande, facetado e gasto, partido ao meio por uma fenda funda (o gelo
    e o calor abriram), as duas metades um tico afastadas. Bloqueia 1 tile, como o hoodoo."""
    from regions_volume import _poly
    planes, c, sq = _poly(241, 24, 19, (0, 0, 15), (1.25, 0.95, 0.85))
    gap_a = 0.35

    def body(X, Y, Z):
        p = np.stack([(X - c[0]) / sq[0], (Y - c[1]) / sq[1], (Z - c[2]) / sq[2]], 1)
        d = np.full(X.shape, 1e9)
        for u, r in planes:
            d = np.minimum(d, r - p @ u)
        return d + 3.2 * fbm3(X, Y, Z, 9, 242) + 0.8 * fbm3(X, Y, Z, 3, 243)

    def dens(X, Y, Z):
        s = X * math.cos(gap_a) - Y * math.sin(gap_a) + 0.08 * Z + 0.8 * fbm3(X, Y, Z, 5, 244)
        side = np.sign(s)
        Xs = X - side * 1.8                                             # as metades se afastam
        d = body(Xs, Y, Z)
        d = np.minimum(d, np.abs(s) - 1.6)                              # a fenda
        base = 7 - np.sqrt((X / 3.0) ** 2 + (Y / 2.0) ** 2 + (Z * 1.6) ** 2) + 3 * fbm3(X, Y, Z, 6, 245)
        return np.maximum(d, base)

    def shade(hx, hy, hz, nrm, lit):
        lam = nrm @ L
        b = np.where(lam > 0.72, 5, np.where(lam > 0.45, 4, np.where(lam > 0.2, 3, np.where(lam > 0.0, 2, 1))))
        b = np.where(lit, b, np.minimum(b, 2))
        s = hx * math.cos(gap_a) - hy * math.sin(gap_a) + 0.08 * hz + 0.8 * fbm3(hx, hy, hz, 5, 244)
        b = np.where(np.abs(s) < 2.6, np.minimum(b, 1), b)               # dentro da fenda
        layer = ((hz + 2 * fbm(hx, hy, 8, 246, 1)) % 7) < 1.0
        b = np.where(layer & (b >= 3) & (nrm[:, 2] < 0.6), b - 1, b)
        sp = hash2(np.round(hx).astype(int), np.round(hy + hz).astype(int), 247)
        b = np.where((sp < 0.05) & (b > 1), b - 1, b)
        return b.astype(np.uint8)
    idx = Volume(72, 64, 36, 52, 0, 36, dens, shade).render()
    return idx, dict(foot=(36, 52), tiles=[(0, 0)], size=(1, 1), name="Pedra rachada")


def salt_pillar():
    """Salar · pilares de sal pequenos: 3 torrões de sal gordos e encaroçados, de alturas bem diferentes, colados num
    pé largo de crosta, com os topos quebrados em bisel. Lê como sal que cresceu e o vento roeu."""
    tw = [((-5, 1), 11.0, 29, 0.55), ((8, -2), 9.5, 18, -0.6), ((1, 7), 8.0, 10, 0.4)]

    def dens(X, Y, Z):
        best = np.full(X.shape, -9.0)
        for k, ((cx, cy), r0, hh, tl) in enumerate(tw):
            rz = r0 * (1 - 0.25 * np.clip(Z / hh, 0, 1)) + 2.5 * np.clip(1 - Z / 6, 0, 1)
            d = rz - np.sqrt((X - cx - 0.1 * Z) ** 2 + ((Y - cy) * 1.2) ** 2) + 3.2 * fbm3(X, Y, Z, 6, 211 + k) \
                + 1.6 * fbm3(X, Y, Z, 3, 217)
            d = np.minimum(d, hh + tl * (X - cx) + 1.5 * fbm3(X, Y, Z, 5, 213) - Z)
            best = np.maximum(best, d)
        skirt = 7 - np.sqrt((X / 2.8) ** 2 + (Y / 2.0) ** 2 + (Z * 1.5) ** 2) + 3 * fbm3(X, Y, Z, 5, 214)
        return np.maximum(best, skirt)

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        b = np.where(nrm[:, 2] > 0.6, np.maximum(b, 4), b)
        sp = hash2(np.round(hx).astype(int), np.round(hy + hz).astype(int), 216)
        b = np.where((sp < 0.06) & (b >= 4), 7, b)
        b = np.where((sp > 0.97) & (b >= 3), 6, b)
        return b.astype(np.uint8)
    idx = Volume(68, 60, 34, 52, 0, 38, dens, shade).render()
    return idx, dict(foot=(34, 52), tiles=[(0, 0)], size=(1, 1), name="Pilares de sal")


def lava_tube():
    """Basalto · tubo de lava colapsado: lombada baixa e comprida (o teto do tubo), levemente curva, com um trecho do
    teto caído (claraboia): um buraco escuro com entulho no fundo. Bloqueia os 3 tiles do comprimento."""
    def axis_y(X):
        return 4 * np.sin(X / 30 + 0.6)

    def hgt(X, Y):
        r = 13 + 1.5 * np.sin(X / 11 + 1) + 1.5 * fbm(X, Y, 9, 227, 1)
        ln = 50 + 6 * fbm(X, Y, 10, 223, 1)
        taper = np.clip((ln - np.abs(X)) / 18, 0, 1) ** 0.6
        y = Y - axis_y(X)
        roof = 11 * taper * np.sqrt(np.clip(1 - (y / np.maximum(r * taper ** 0.5, 1)) ** 2, 0, 1))
        roof = roof + 1.5 * fbm(X, Y, 4, 221, 2) * (roof > 0)
        hole = ((X - 8) / 13) ** 2 + (y / 8.5) ** 2 + 0.5 * (fbm(X, Y, 5, 224, 1) - 0.5) < 1
        pit = -5 + 3 * fbm(X, Y, 3, 225, 2)
        h = np.where(hole, pit, roof)
        return np.where((roof > 0.4) | hole, h, -20)

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        b = np.where(nrm[:, 2] > 0.85, np.where(lit, 4, 3), np.minimum(b, 4))
        b = np.where(hz < 0.5, np.where(lit & (nrm[:, 2] > 0.7), 1, 0), b)      # dentro da claraboia: escuro
        sp = hash2(np.round(hx).astype(int), np.round(hy * 2 + hz).astype(int), 226)
        rust = fbm3(hx, hy, hz, 4, 228, 2) > 0.30
        b = np.where(rust & (hz > 1) & (b >= 2), 7, b)
        b = np.where((sp < 0.05) & (b > 1), b - 1, b)
        return b.astype(np.uint8)
    idx = Volume(124, 56, 62, 40, -8, 16, lambda X, Y, Z: hgt(X, Y) - Z, shade, soft_edge=True).render()
    return idx, dict(foot=(62, 40), tiles=[(-1, 0), (0, 0), (1, 0)], size=(3, 1), name="Tubo de lava colapsado")


def ice_needles():
    """Faixa gelada · agulhas de gelo (campo de penitentes grande): lâminas altas inclinadas pro sol, as do meio
    maiores, com uma base de neve dura."""
    bl = _blades(231, 11, 20, 46, 26, 5.0)
    bd = _blades_dens(bl, 231)

    def dens(X, Y, Z):
        base = 6 - np.sqrt((X / 4.6) ** 2 + (Y / 2.0) ** 2 + (Z * 1.4) ** 2) + 2 * fbm3(X, Y, Z, 6, 232)
        return np.maximum(bd(X, Y, Z), base)
    idx = sharpen(Volume(84, 72, 42, 62, 0, 50, dens, _ice_shade(233)).render())
    return idx, dict(foot=(42, 62), tiles=[(-1, 0), (0, 0), (1, 0)], size=(3, 1), name="Agulhas de gelo")


SMALL_FORMS = {
    "split_rock": (split_rock, "plateau", "HILL"),
    "salt_pillar": (salt_pillar, "salar", "BASE"),
    "lava_tube": (lava_tube, "basalt", "HILL"),
    "ice_needles": (ice_needles, "frost", "ICE"),
}


# ---- rampas ------------------------------------------------------------------------------------------------------
TABLES = {"BASE": R.BASE, "HILL": R.HILL, "SAND": {"plateau": R.SAND}, "ICE": {"frost": R.ICE}}


def ramp_for(region, table, stage):
    """Rampa (10×3) pro colorize, pela tabela do elemento."""
    if table == "ICE":
        return R.ramp("frost", stage, TABLES["ICE"])
    if table == "SAND":
        return R.ramp("plateau", stage, TABLES["SAND"])
    return R.ramp(region, stage, TABLES[table])


def moss_ramp():
    return np.array([R.rgb(c) for c in MOSS] + [R.OUTLINE] * 5 + [(0, 0, 0)], np.uint8)
