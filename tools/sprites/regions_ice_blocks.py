"""v9.2 · BLOCOS DE GELO do gelo-portão (proposta, M3.5): cada portão vira um amontoado de blocos que derretem
cada um no seu ritmo, encolhendo de verdade (o volume é refeito em cada escala, nada de redimensionar pixel).

Três tipos, duas variações cada (todos rampa ICE, recolorível nos 4 estágios, índices iguais aos da v8):
    shard    lasca: coluna alta e grossa com o topo cortado em bisel (nada de agulha: é gordinha)
    slab     laje: bloco largo e baixo, com as quinas chanfradas
    boulder  pedra: pedaço poliédrico arredondado (v0) e cubo tombado de quinas gastas (v1)

Escala s (1.0 → 0.2): o volume inteiro encolhe em volta do centro da base (a âncora não anda), e quanto menor,
mais o poliedro puxa pro elipsoide de dentro (quinas derretidas) e mais brilho molhado ele ganha.

Índices: 1..6 rampa ICE (escuro → branco), 7 a pedra presa, 8 contorno, 9 sombra no chão, 255 transparente.
"""

from __future__ import annotations

import math

import numpy as np

import regions_volume as V
from regions_core import hash2

SCALES = (1.0, 0.89, 0.78, 0.67, 0.56, 0.45, 0.34, 0.23)      # 8 passos, do inteiro ao último caquinho
MARGIN = 3
SIZE = 1.25                     # tamanho do bloco inteiro (o desenho é em px "1.0"; a v9.2 sai 25% maior)


# ---- poliedros convexos -----------------------------------------------------------------------------------------
def _ring(n, r, tilt=0.0, phase=0.0, jitter=0.0, seed=0):
    """n planos verticais (ou inclinados `tilt`) em volta do eixo Z: as faces laterais do prisma."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        a = phase + 2 * math.pi * i / n + rng.uniform(-jitter, jitter)
        u = np.array([math.cos(a), math.sin(a), tilt])
        out.append((u / np.linalg.norm(u), r * rng.uniform(0.92, 1.0) if jitter else r))
    return out


def _cap(normal, r):
    u = np.array(normal, float)
    return [(u / np.linalg.norm(u), r)]


def _fib(n, r, seed):
    rng = np.random.default_rng(seed)
    ga = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        zc = 1 - 2 * (i + 0.5) / n
        rr = math.sqrt(1 - zc * zc)
        u = np.array([math.cos(ga * i) * rr, math.sin(ga * i) * rr, zc]) + rng.normal(scale=0.16, size=3)
        out.append((u / np.linalg.norm(u), r * rng.uniform(0.86, 1.0)))
    return out


class Part:
    """Poliedro convexo: planos (u, r) em coordenadas locais, centro, esticão por eixo e giro em Z."""

    def __init__(self, planes, center, squash=(1, 1, 1), rot=0.0, lean=(0.0, 0.0)):
        self.planes = planes
        self.c = np.array(center, float)
        self.sq = np.array(squash, float)
        self.rot = rot
        self.lean = lean                       # inclinação (px de X e Y por px de Z)
        self.ell = min(r for _, r in planes) * 1.02     # raio do "miolo" (pra onde ele derrete)

    def local(self, X, Y, Z, s):
        x = (X - self.c[0] * s) - self.lean[0] * (Z - self.c[2] * s)
        y = (Y - self.c[1] * s) - self.lean[1] * (Z - self.c[2] * s)
        z = Z - self.c[2] * s
        cr, sr = math.cos(self.rot), math.sin(self.rot)
        x, y = x * cr + y * sr, -x * sr + y * cr
        return np.stack([x / (self.sq[0] * s), y / (self.sq[1] * s), z / (self.sq[2] * s)], 1)

    def dens(self, X, Y, Z, s, melt):
        p = self.local(X, Y, Z, s)
        d = np.full(X.shape, 1e9)
        for u, r in self.planes:
            d = np.minimum(d, r - p @ u)
        if melt > 0:                                       # quinas moles: puxa pro elipsoide de dentro
            e = self.ell * 1.08 - np.linalg.norm(p, axis=1)
            d = (1 - melt) * d + melt * e
        return d * s * float(self.sq.min())


# ---- os 6 blocos ------------------------------------------------------------------------------------------------
def _shard(v):
    if v == 0:      # coluna de 6 faces, topo em bisel caindo pra direita-frente
        body = _ring(6, 12, phase=0.3) + _cap((0.42, 0.22, 1), 30) + _cap((0, 0, -1), 33)
        return [Part(body, (0, -10, 29), (1.0, 0.85, 1.0), lean=(0.06, 0.0))]
    # par: coluna alta + toco mais baixo encostado na frente-esquerda
    tall = _ring(5, 11, phase=0.9) + _cap((-0.35, 0.25, 1), 33) + _cap((0, 0, -1), 35)
    stub = _ring(6, 9, phase=0.1) + _cap((0.3, 0.5, 1), 12) + _cap((0, 0, -1), 14)
    return [Part(tall, (3, -12, 32), (1.0, 0.9, 1.0), lean=(-0.05, 0.0)),
            Part(stub, (-10, -5, 12), (1.0, 0.9, 1.0))]


def _slab(v):
    if v == 0:      # laje larga: prisma de 8 faces achatado, tampo levemente inclinado, quinas chanfradas
        body = _ring(8, 26, phase=0.39) + _ring(8, 25, tilt=1.1, phase=0.0) + _cap((0.05, 0.12, 1), 10) + \
            _cap((0, 0, -1), 12)
        return [Part(body, (0, -13, 10), (1.0, 0.55, 1.0))]
    # laje tombada: um lado mais alto, rachada em dois blocos encostados
    a = _ring(7, 18, phase=0.2, jitter=0.12, seed=7) + _cap((-0.3, 0.1, 1), 11) + _cap((0, 0, -1), 12)
    b = _ring(6, 15, phase=0.5, jitter=0.12, seed=8) + _cap((0.28, 0.15, 1), 9) + _cap((0, 0, -1), 10)
    return [Part(a, (-10, -14, 11), (1.0, 0.62, 1.0)), Part(b, (16, -11, 8), (1.0, 0.65, 1.0))]


def _boulder(v):
    if v == 0:
        return [Part(_fib(16, 19, 211) + _cap((0, 0, -1), 14), (0, -14, 16), (1.15, 0.9, 1.0))]
    # cubo tombado: 6 faces de um cubo girado (lembra o gelo em cubos dos minérios), quinas já gastas
    rx, rz = 0.42, 0.55
    planes = []
    for n in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        u = np.array(n, float)
        c, s_ = math.cos(rx), math.sin(rx)
        u = np.array([u[0], c * u[1] - s_ * u[2], s_ * u[1] + c * u[2]])
        c, s_ = math.cos(rz), math.sin(rz)
        u = np.array([c * u[0] - s_ * u[1], s_ * u[0] + c * u[1], u[2]])
        planes.append((u, 15.5))
    planes += _fib(14, 19.5, 223)                                  # chanfro nas quinas
    return [Part(planes + _cap((0, 0, -1), 13), (0, -15, 15), (1.05, 1.0, 1.0))]


BLOCKS = {
    "shard": dict(name="Lasca", build=_shard),
    "slab": dict(name="Laje", build=_slab),
    "boulder": dict(name="Pedra", build=_boulder),
}
KINDS = tuple(BLOCKS)


def parts(kind, v):
    return BLOCKS[kind]["build"](v)


def melt_of(s):
    return float(np.clip((1.0 - s) / 0.77, 0, 1)) ** 1.7 * 0.7


def dens_fn(kind, v, s):
    ps = parts(kind, v)
    melt = melt_of(s)
    amp = 0.45 + 1.1 * (1 - s)
    g = s * SIZE                                    # escala geométrica

    def dens(X, Y, Z):
        d = np.full(X.shape, -1e9)
        for p in ps:
            d = np.maximum(d, p.dens(X, Y, Z, g, melt))
        # textura da superfície em coordenadas locais (encolhe junto: é "o mesmo bloco")
        return d + amp * g * V.fbm3(X / g, Y / g, Z / g, 16, 300 + 7 * v + len(kind), octaves=2) * 2.0
    return dens


def rock_fn(kind, v, s):
    """A pedra presa dentro (só a pedra v1)."""
    return None                                   # (a pedra presa lia como buraco: saiu na v9.2)
    if not (kind == "boulder" and v == 1):
        return None
    return lambda X, Y, Z: 7.5 * s - np.sqrt(((X + 3 * s) / 1.3) ** 2 + (Y + 13 * s) ** 2 + ((Z - 15 * s) / 0.9) ** 2)


def shade_fn(kind, v, s):
    dens = dens_fn(kind, v, s)
    rock = rock_fn(kind, v, s)
    spec_cut = 0.965 - 0.07 * (1 - s)                     # derretendo: mais brilho molhado
    hvec = V.L + np.array([0, 0.7, 0.7])
    hvec = hvec / np.linalg.norm(hvec)

    def shade(hx, hy, hz, nrm, lit):
        lam = nrm @ V.L
        b = np.where(lam > 0.80, 5, np.where(lam > 0.52, 4, np.where(lam > 0.22, 3, np.where(lam > -0.1, 2, 1))))
        b = np.where(lit, b, np.maximum(b - 1, 1))
        # translucidez pela espessura: o miolo grosso fica fundo (azul escuro), a borda fina continua clara
        thick = np.zeros(hx.size)
        for t in range(2, 16, 2):
            thick += dens(hx, hy - t * 0.7, hz - t * 0.7) > 0
        b = np.where((thick >= 6) & (b >= 2) & (b <= 3), b - 1, b)
        b = np.where((thick <= 1) & (b == 1), 2, b)
        spec = nrm @ hvec > spec_cut
        b = np.where(spec, 6, b)
        # veios de ar presos (fissuras internas), em coordenadas locais pra encolher junto
        lx, ly, lz = hx / (s * SIZE), hy / (s * SIZE), hz / (s * SIZE)
        g = ((np.round(lx + ly * 2 + lz).astype(int) % 23) < 1) & \
            (hash2((lx // 12).astype(int), (lz // 12).astype(int), 405 + v) < 0.35)
        b = np.where(g & (b >= 3) & (b < 6), 5, b)
        if rock is not None:
            seen = np.zeros(hx.size, bool)
            for t in range(2, 16, 2):
                seen |= rock(hx, hy - t * 0.7, hz - t * 0.7) > 0
            b = np.where(seen & (b >= 3) & (b < 6), 7, b)
            b = np.where(seen & (b < 3), 1, b)
        return b.astype(np.uint8)
    return shade


# ---- caixa do quadro (igual pra todas as escalas: a âncora não anda) --------------------------------------------
_FRAME: dict = {}


def frame_box(kind, v):
    """(w, h, ox, oy, zmax): quadro que cabe o bloco inteiro + a sombra, com a âncora (centro da base) em (ox, oy)."""
    key = (kind, v)
    if key in _FRAME:
        return _FRAME[key]
    dens = dens_fn(kind, v, 1.0)
    # varre o volume num cubo largo pra achar a caixa
    xs = np.arange(-90, 91, 1.0)
    ys = np.arange(-90, 31, 1.0)
    zs = np.arange(0, 120, 1.0)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    m = dens(X.ravel(), Y.ravel(), Z.ravel()) > 0
    X, Y, Z = X.ravel()[m], Y.ravel()[m], Z.ravel()[m]
    zmax = int(Z.max()) + 3
    sx0, sx1 = X.min(), X.max()
    sy0, sy1 = (Y - Z).min(), Y.max()
    # sombra: cai pra +X e pra trás (−Y) a partir do topo; folga generosa medida pela altura
    sh = zmax * 0.62
    w = int(sx1 - sx0 + sh + 2 * MARGIN + 2)
    h = int(sy1 - sy0 + 2 * MARGIN + 2)
    ox = int(-sx0 + MARGIN + 1)
    oy = int(-sy0 + MARGIN + 1)
    _FRAME[key] = (w, h, ox, oy, zmax)
    return _FRAME[key]


_IDX: dict = {}


def render(kind, v, s):
    key = (kind, v, s)
    if key in _IDX:
        return _IDX[key]
    w, h, ox, oy, zmax = frame_box(kind, v)
    vol = V.Volume(w, h, ox, oy, 0, zmax, dens_fn(kind, v, s), shade_fn(kind, v, s))
    idx = vol.render()
    _IDX[key] = idx
    return idx


def collision(kind, v, s, inset=1):
    """Retângulo de colisão sugerido: a base do bloco (corte do volume em Z = 1..3), relativo à âncora no pé,
    em px do mundo (x, y, w, h). y negativo = pra trás (pra cima na tela)."""
    dens = dens_fn(kind, v, s)
    xs = np.arange(-90, 91, 1.0)
    ys = np.arange(-90, 31, 1.0)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    X, Y = X.ravel(), Y.ravel()
    m = np.zeros(X.size, bool)
    for z in (1.0, 2.0, 3.0):
        m |= dens(X, Y, np.full(X.size, z)) > 0
    if not m.any():
        return None
    x0, x1 = X[m].min(), X[m].max() + 1
    y0, y1 = Y[m].min(), Y[m].max() + 1
    x0, x1, y0, y1 = x0 + inset, x1 - inset, y0 + inset, y1 - inset
    return [int(x0), int(y0), int(max(2, x1 - x0)), int(max(2, y1 - y0))]


def strip(kind, v):
    """As 8 escalas lado a lado (o PNG que vai pro jogo)."""
    frames = [render(kind, v, s) for s in SCALES]
    h, w = frames[0].shape
    out = np.full((h, w * len(frames)), 255, np.uint8)
    for i, f in enumerate(frames):
        out[:, i * w:(i + 1) * w] = f
    return out
