#!/usr/bin/env python3
"""v0.5 · PROPOSTA: o GELO GIGANTE da faixa gelada, com uma silhueta escura (o "verme") presa dentro.

    python3 tools/sprites/gelo_gigante.py

Gera tudo em reports/design/gelo_gigante/ (pendentes/ = os PNG indexados propostos + gelo_gigante.json, e as prévias
e o index.html do report). Nada vai pra assets/ sem o ok do dono.

O monólito é um VOLUME 3D (o mesmo motor de regions_volume.py: projeção 3/4, luz em faixas chapadas, sombra própria e
projetada, contorno #1b1630), feito de poliedros convexos como os blocos do portão (regions_ice_blocks.Part).
A criatura é um TUBO segmentado definido no espaço da tela (u = direita, v = pra cima na tela, w = profundidade no
raio de visão). No shade, cada pixel da superfície do gelo marcha pra dentro pelo raio de visão: se bate na criatura
perto da superfície ela aparece escura e nítida; mais fundo, só escurece o gelo um tom (o "difuso").

Índices (PNG modo P, paleta do Árido embutida):
    0..7   rampa ICE (ramps.ICE.frost[estágio]), igual aos blocos do portão
    8      contorno #1b1630
    9      sombra no chão (preto, alfa 80)
    10..12 a silhueta: 10 véu (longe), 11 corpo, 12 miolo/boca. Rampa nova proposta `ramps.ICE_DEEP[estágio]`,
           derivada da ICE do estágio misturada com o contorno (ver deep_ramp)
    255    transparente
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import regions_core as R  # noqa: E402
import regions_ice_blocks as B  # noqa: E402
import regions_volume as V  # noqa: E402
from regions_core import fbm, grid, hash2  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "reports" / "design" / "gelo_gigante"
PEND = OUT / "pendentes"
T = 32

# ---- caixa do sprite e pegada ------------------------------------------------------------------------------------
SW, SH = 256, 220                 # sprite
SHADOW_ZMAX = 84
OX, OY = 120, 216                 # âncora = centro da borda de baixo da pegada 7×4 (o pé), no sprite
FOOT_W, FOOT_H = 7, 4             # pegada em tiles (a âncora cai no meio da borda de baixo do tile (0, 0))
NFRAMES = 8
DEPTH_NEAR, DEPTH_MID, DEPTH_FAR = 12.0, 28.0, 56.0   # profundidade (px no raio) até a criatura

TOWARD = np.array([0.0, 1.0, 1.0]) / math.sqrt(2)      # do gelo pra câmera (o raio de visão ao contrário)
UP = np.array([0.0, 0.0, 1.0])                         # a criatura mora num plano paralelo à face da frente
FRONT = np.array([0.0, 1.0, 0.0])                      # w > 0 = mais perto da face da frente


# =================================================================================================================
# O MONÓLITO
# =================================================================================================================
def _parts():
    P = B.Part
    ring, cap = B._ring, B._cap
    # corpo principal: prisma de 6 faces quase vertical (uma de frente pra câmera), quinas chanfradas finas,
    # tampo em 2 planos (cai pra direita e pra trás): o monólito encalhado, um pouco tombado pra direita
    body = ring(6, 40, tilt=0.06, phase=math.pi / 2, jitter=0.06, seed=501) + \
        ring(6, 44, tilt=0.0, phase=math.pi / 2 + math.pi / 6, jitter=0.08, seed=502) + \
        cap((0.22, -0.10, 1), 60) + cap((-0.45, 0.30, 1), 66) + cap((0.1, 0.9, 0.55), 52) + \
        cap((0.55, 0.55, 0.6), 56) + cap((0.15, -0.6, 1), 58) + cap((0, 0, -1), 54)
    main = P(body, (-8, -50, 54), (2.05, 0.95, 1.0), rot=0.04, lean=(0.10, 0.0))
    # ombro baixo à direita (o iceberg desce em degrau)
    sh = ring(6, 24, tilt=0.10, phase=0.3, jitter=0.12, seed=511) + cap((0.35, 0.15, 1), 16) + \
        cap((0, 0, -1), 24)
    shoulder = P(sh, (86, -44, 22), (1.20, 1.10, 1.0), rot=-0.2)
    # laje encostada na frente-esquerda, inclinada pra fora (caiu do corpo)
    sl = ring(5, 13, phase=0.7, jitter=0.1, seed=521) + cap((-0.2, 0.45, 1), 22) + cap((0, 0, -1), 26)
    slab = P(sl, (-96, -30, 22), (1.2, 0.9, 1.0), lean=(-0.25, 0.10), rot=0.3)
    # ponta de trás mais alta à esquerda (a "torre" do monólito)
    cr = ring(5, 20, tilt=0.05, phase=0.2, jitter=0.12, seed=531) + cap((0.75, 0.1, 1), 50) + \
        cap((-0.6, 0.35, 1), 58) + cap((0, 0, -1), 64)
    crest = P(cr, (-44, -62, 64), (1.5, 0.85, 1.0), lean=(0.04, -0.02))
    return [main, shoulder, slab, crest]


PARTS = _parts()


def ice_dens(X, Y, Z):
    d = np.full(X.shape, -1e9)
    for p in PARTS:
        d = np.maximum(d, p.dens(X, Y, Z, 1.0, 0.0))
    return d + 0.9 * V.fbm3(X, Y, Z, 16, 541, octaves=2) * 2.0


# =================================================================================================================
# A CRIATURA (curvas no espaço da tela)
# =================================================================================================================
def _to_world(u, v, w, c):
    """(u, v, w) da tela -> (X, Y, Z) do mundo; c = centro (X, Y, Z) da criatura dentro do gelo."""
    p = np.array(c, float)[None, :] + u[:, None] * np.array([1.0, 0, 0]) + v[:, None] * UP + w[:, None] * FRONT
    return p


def _resample(p, step=1.5):
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = max(2, int(s[-1] / step))
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, p[:, k]) for k in range(3)], 1), t


def curve_coil():
    """Enrolada: espiral de 1,6 volta (dorme enrolada), cabeça por fora em cima, rabo afinando no miolo."""
    t = np.linspace(0, 1, 400)
    ang = 2.6 + t * 2 * math.pi * 1.25
    rad = 42 - 24 * t
    u = rad * np.cos(ang) * 1.45
    v = rad * np.sin(ang) * 0.95
    w = -4 + 9 * np.sin(t * 6.0 + 0.8) - 14 * t + 16 * np.clip(1 - t / 0.10, 0, 1) ** 2                      # entra e sai do fundo
    p = _to_world(u, v, w, (-8, -30, 56))
    p, s = _resample(p)                                         # s = 0 na cabeça (fora da espiral)
    return p, s


def curve_s():
    """Em S: atravessa o bloco na diagonal, cabeça subindo pra perto da face de cima-esquerda."""
    t = np.linspace(0, 1, 400)
    u = -78 + 150 * t
    v = 30 * np.sin(t * 2 * math.pi * 1.05 + 0.4) + 16 - 30 * t
    w = -6 - 9 * np.sin(t * math.pi * 2.2 + 1.2) + 12 * np.clip(1 - t / 0.16, 0, 1) ** 2   # a cabeça vira pra frente
    p = _to_world(u, v, w, (-2, -32, 42))
    p, s = _resample(p)
    return p, s


def curve_piece():
    """Só um pedaço: um arco grosso saindo do fundo e voltando pro fundo (o resto nunca aparece)."""
    t = np.linspace(0, 1, 300)
    a = math.pi * (0.05 + 0.95 * t)
    u = -20 + 62 * np.cos(a) * 1.05
    v = -14 + 46 * np.sin(a)
    w = -30 + 26 * np.sin(a) ** 1.4                              # as pontas somem no fundo, o meio encosta
    p = _to_world(u, v, w, (-4, -26, 40))
    p, s = _resample(p)
    return p, s


VARIANTS = {
    "coil": dict(name="Enrolada", curve=curve_coil, r0=9.0, seg=13.0, head=True, tail=0.25),
    "s": dict(name="Em S", curve=curve_s, r0=11.5, seg=15.0, head=True, tail=0.35),
    "piece": dict(name="Só um pedaço", curve=curve_piece, r0=15.0, seg=17.0, head=False, tail=0.0),
}


class Creature:
    def __init__(self, key, breath=0.0):
        cfg = VARIANTS[key]
        self.p, self.s = cfg["curve"]()
        L = self.s[-1]
        tt = self.s / L
        seg = cfg["seg"]
        # raio: segmentos (constrição a cada `seg` px), cabeça um pouco mais larga, rabo afinando
        ring = 0.86 + 0.14 * np.abs(np.sin(math.pi * self.s / seg)) ** 0.5
        taper = 1 - cfg["tail"] * np.clip((tt - 0.55) / 0.45, 0, 1) ** 1.3
        headb = 1 + (0.30 * np.exp(-(self.s / 10) ** 2) if cfg["head"] else 0)
        self.r = cfg["r0"] * ring * taper * headb * (1 + breath)
        self.head = cfg["head"]
        self.seg = seg
        self.p0 = self.p[0]
        d = self.p[min(6, len(self.p) - 1)] - self.p[0]
        self.dir0 = d / max(1e-6, np.linalg.norm(d))
        # direção da cabeça na tela (pra fora do corpo) e o centro da boca puxado um pouco pra ponta
        q = self.p[min(10, len(self.p) - 1)]
        e = np.array([self.p0[0] - q[0], (self.p0[1] - self.p0[2]) - (q[1] - q[2])])
        self.mouth_dir = e / max(1e-6, np.linalg.norm(e))

        self.seam = np.abs(((self.s + 0.5 * seg) % seg) - 0.5 * seg) > 0.5 * seg - 1.4
        self.shell = None

    def field(self, P):
        """> 0 dentro da criatura. P (n, 3). Devolve (campo, índice do ponto mais perto)."""
        return _sweep(P, self.p, self.r)


def _sweep(P, pts, rad):
    best = np.full(P.shape[0], -1e9)
    bi = np.zeros(P.shape[0], int)
    for i in range(len(pts)):
        f = rad[i] - np.linalg.norm(P - pts[i], axis=1)
        m = f > best
        best = np.where(m, f, best)
        bi = np.where(m, i, bi)
    return best, bi


# ---- v0.5.1: a criatura encolhida em "C" (pedido do dono: larva, embrião, casulo, fetal) -------------------------
def _catmull(ctrl, n):
    """Curva suave pelos pontos de controle (Catmull-Rom), n amostras."""
    c = np.asarray(ctrl, float)
    c = np.vstack([2 * c[0] - c[1], c, 2 * c[-1] - c[-2]])
    out = []
    segs = len(c) - 3
    for i in range(segs):
        p0, p1, p2, p3 = c[i], c[i + 1], c[i + 2], c[i + 3]
        for t in np.linspace(0, 1, max(2, n // segs), endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(c[-2])
    return np.array(out)


def chain(ctrl, radii, center, seg=None, ring=0.0, step=1.6):
    """Tubo pelos controles (u, v, w) com raio interpolado. Devolve (pontos no mundo, raios, junta?)."""
    ctrl = [(u * CS, v * CS, w) for u, v, w in ctrl]
    radii = [r * CS for r in radii]
    seg = seg * CS if seg else seg
    uvw = _catmull(ctrl, 200)
    p = _to_world(uvw[:, 0], uvw[:, 1], uvw[:, 2], center)
    p, s = _resample(p, step)
    tt = s / max(s[-1], 1e-6)
    r = np.interp(tt, np.linspace(0, 1, len(radii)), radii)
    if seg:
        r = r * ((1 - ring) + ring * np.abs(np.sin(math.pi * s / seg)) ** 0.5)
        sm = np.abs(((s + 0.5 * seg) % seg) - 0.5 * seg) > 0.5 * seg - 1.4
    else:
        sm = np.zeros(len(s), bool)
    return p, r, sm


def ball(u, v, w, rad, center):
    u, v, rad = u * CS, v * CS, rad * CS
    return _to_world(np.array([u], float), np.array([v], float), np.array([w], float), center), np.array([rad], float), \
        np.zeros(1, bool)


class Body:
    """Criatura feita de tubos e bolas (varredura de esferas). Mesma interface da Creature."""

    def __init__(self, pieces, breath=0.0, shell=None):
        self.p = np.concatenate([q[0] for q in pieces])
        self.r = np.concatenate([q[1] for q in pieces]) * (1 + breath)
        self.seam = np.concatenate([q[2] for q in pieces])
        self.head = False
        self.shell = shell

    def field(self, P):
        return _sweep(P, self.p, self.r)


def _ellipsoid_shell(center, ru, rv, rw, thick):
    c = np.array(center, float)

    def f(P):
        q = P - c
        u, w, v = q[:, 0], q[:, 1], q[:, 2]                  # u = X, w = Y (profundidade), v = Z
        e = np.sqrt((u / ru) ** 2 + (v / rv) ** 2 + (w / rw) ** 2)
        inside = e < 1
        shell = inside & (e > 1 - thick / min(ru, rv))
        return shell, inside
    return f


CS = 1.25                   # escala das criaturas novas (ocupam o miolo da face da frente)
CC = (-24, -35, 52)         # centro das criaturas novas (miolo do bloco, ~18 px atrás da face da frente)


def body_larva(br=0.0, scale=1.0, center=CC):
    a = np.radians(np.linspace(38, 318, 9))
    R = np.linspace(31, 22, 9) * scale
    ctrl = [(R[i] * math.cos(a[i]) * 1.12, R[i] * math.sin(a[i]), 4 - 12 * math.sin(math.pi * i / 8)) for i in range(9)]
    rad = np.array([12.5, 15, 16.5, 17, 16.5, 15, 12.5, 9.5, 6.5]) * scale
    pieces = [chain(ctrl, rad, center, seg=9.5 * scale, ring=0.24)]
    hx, hy = 33 * math.cos(math.radians(30)) * 1.12 * scale, 33 * math.sin(math.radians(30)) * scale
    pieces.append(ball(hx, hy, 6, 13.5 * scale, center))                        # a cabeça (sem rosto)
    for k, ang in enumerate((62, 88, 114)):                                     # 3 pares de patinhas dobradas pra dentro
        aa = math.radians(ang)
        r0 = 26 * scale
        x0, y0 = r0 * math.cos(aa) * 1.12, r0 * math.sin(aa)
        x1, y1 = (r0 - 11 * scale) * math.cos(aa + 0.25) * 1.12, (r0 - 11 * scale) * math.sin(aa + 0.25)
        x2, y2 = (r0 - 13 * scale) * math.cos(aa + 0.55) * 1.12, (r0 - 13 * scale) * math.sin(aa + 0.55)
        pieces.append(chain([(x0, y0, 6), (x1, y1, 8), (x2, y2, 8)], [5.2 * scale, 4.4 * scale, 3.4 * scale], center))
    return Body(pieces, br)


def body_embryo(br=0.0):
    c = CC
    pieces = [ball(4, 15, 7, 23, c), ball(-8, 20, 2, 17, c)]                     # cabeça grande (crânio alongado)
    ctrl = [(-12, 0, 2), (-20, -16, 0), (-12, -32, -3), (4, -36, -4), (18, -30, -2), (22, -20, 2), (16, -12, 5)]
    pieces.append(chain(ctrl, [11, 11.5, 11, 10, 8.5, 6.5, 4], c, seg=11, ring=0.10))
    pieces.append(chain([(2, -4, 7), (9, -10, 9), (12, -15, 9)], [5, 4.2, 3.4], c))      # broto de braço
    pieces.append(chain([(2, -26, 4), (11, -22, 6), (14, -17, 6)], [6, 5, 4], c))        # broto de perna
    pieces.append(chain([(12, -16, 0), (34, -30, -10), (56, -24, -20), (70, -8, -28)], [3.4, 3, 2.6, 2.2], c))  # cordão
    return Body(pieces, br)


def body_cocoon(br=0.0):
    b = body_larva(br, scale=0.80, center=(CC[0], CC[1] - 2, CC[2]))
    sh = _ellipsoid_shell((CC[0] + 2, CC[1] - 4, CC[2] + 2), 50, 44, 20, 4.0)
    b.shell = sh
    return b


def body_fetal(br=0.0):
    c = CC
    pieces = [ball(-6, 22, 4, 13, c), ball(-14, 28, 0, 11, c), ball(-20, 32, -3, 8, c)]  # cabeça baixa, crânio pra trás
    pieces.append(chain([(-4, 12, 3), (-11, 0, 1), (-11, -14, 0), (-3, -24, 0)], [10, 13, 13, 12], c))    # costas curvas
    pieces.append(chain([(-3, -22, 3), (9, -15, 6), (18, -8, 7)], [10, 8.5, 7], c))                       # coxa
    pieces.append(chain([(18, -8, 7), (19, -20, 6), (14, -29, 5)], [6.5, 5.5, 5], c))                     # canela
    pieces.append(chain([(-2, 8, 6), (7, -2, 9), (16, -6, 10)], [5.5, 4.6, 4], c))                        # braço abraçando
    pieces.append(chain([(-4, -27, -4), (-22, -37, -8), (-39, -22, -10), (-43, 4, -12), (-34, 26, -12),
                         (-18, 36, -12), (-2, 34, -10)], [9, 8.5, 8, 7, 6, 4.5, 3], c, seg=8, ring=0.14))  # cauda em volta
    return Body(pieces, br)


C_VARIANTS = {
    "larva": dict(name="Larva em C", build=body_larva),
    "embryo": dict(name="Embrião", build=body_embryo),
    "cocoon": dict(name="Casulo", build=body_cocoon),
    "fetal": dict(name="Encolhido com cauda", build=body_fetal),
}


ALL = {**{k: v["name"] for k, v in C_VARIANTS.items()}, **{k: v["name"] for k, v in VARIANTS.items()}}
APPROVED = ("larva", "cocoon")      # o dono aprovou as duas (v0.5.1)
SHOWCASE = "cocoon"                 # a que o report mostra nos 4 estágios


def make_creature(key, br=0.0):
    if key in C_VARIANTS:
        return C_VARIANTS[key]["build"](br)
    return Creature(key, br)


# =================================================================================================================
# SHADE
# =================================================================================================================
HVEC = V.L + np.array([0, 0.7, 0.7])
HVEC = HVEC / np.linalg.norm(HVEC)


def shade_fn(creature: Creature | None, frame: int = 0, glint: bool = True):
    def shade(hx, hy, hz, nrm, lit):
        lam = nrm @ V.L
        b = np.where(lam > 0.80, 5, np.where(lam > 0.52, 4, np.where(lam > 0.22, 3, np.where(lam > -0.1, 2, 1))))
        b = np.where(lit, b, np.maximum(b - 1, 1))
        up = nrm[:, 2] > 0.72
        # espessura: o miolo grosso fica fundo (azul escuro), a borda fina continua clara
        thick = np.zeros(hx.size)
        for t in range(3, 30, 3):
            thick += ice_dens(hx, hy - t * 0.7, hz - t * 0.7) > 0
        b = np.where((thick >= 8) & (b >= 2) & (b <= 3) & ~up, b - 1, b)
        # estratos: camadas antigas levemente inclinadas, linha de 1 px nas faces laterais
        lay = hz + 0.12 * hx + 2.5 * V.fbm3(hx, hy, hz, 26, 551, 2) * 2
        k = np.floor(lay / 10).astype(int)
        line = (np.abs(lay - k * 10) < 0.55) & ~up & (hash2(k, (hx // 24).astype(int), 552) < 0.7)
        b = np.where(line & (b >= 2), b - 1, b)
        b = np.where(np.roll(line, 1) & (b >= 2) & (b <= 4) & (hash2(k, 3, 553) < 0.35), b + 1, b)
        # bolhas presas: pontinhos claros em cachos
        cl = V.fbm3(hx, hy, hz, 14, 561, 2) > 0.18
        bub = cl & (hash2(np.round(hx).astype(int), np.round(hy * 2 + hz * 3).astype(int), 562) < 0.035)
        # fissuras internas (veios de ar), como nos blocos do portão
        g = ((np.round(hx + hy * 2 + hz).astype(int) % 29) < 1) & \
            (hash2((hx // 14).astype(int), (hz // 14).astype(int), 563) < 0.30) & ~up
        b = np.where(g & (b >= 3) & (b < 6), 5, b)

        # brilho frio: especular + bolhas
        spec = nrm @ HVEC > 0.975
        b = np.where(spec, 6, b)
        b = np.where(bub & (b >= 2), 6, b)

        # a criatura vista pelo gelo (por cima do brilho das faces, por baixo das bolhas da frente)
        if creature is not None:
            P0 = np.stack([hx, hy, hz], 1)
            dhit = np.full(hx.size, np.inf)
            cmax = np.full(hx.size, -1e9)
            seamhit = np.zeros(hx.size, bool)
            rhit = np.ones(hx.size)
            shc = np.zeros(hx.size)
            insc = np.zeros(hx.size)
            shd = np.full(hx.size, np.inf)
            mth = np.zeros(hx.size, bool)
            lip = np.zeros(hx.size, bool)
            for t in np.arange(1.0, DEPTH_FAR, 1.5):
                P = P0 - TOWARD[None, :] * t
                f, ii = creature.field(P)
                newhit = (f > 0) & np.isinf(dhit)
                dhit = np.where(newhit, t, dhit)
                seamhit = np.where(newhit, creature.seam[ii], seamhit)
                rhit = np.where(newhit, creature.r[ii], rhit)
                if creature.shell is not None:
                    shl, ins = creature.shell(P)
                    before = np.isinf(dhit) | (t < dhit)
                    shc += shl & before
                    shd = np.where(shl & np.isinf(shd), t, shd)
                    insc += ins & before
                cmax = np.maximum(cmax, np.where(dhit < t + 12, f, -1e9))
            rel = np.clip(cmax / np.maximum(rhit, 1), 0, 1)          # 0 na borda do tubo, ~1 no eixo
            if creature.head:
                # boca: na tela, um disco escuro na ponta da cabeça com um anel um tom mais claro em volta
                hsx, hsy = creature.p0[0], creature.p0[1] - creature.p0[2]
                ex, ey = creature.mouth_dir
                qx, qy = hx - hsx, (hy - hz) - hsy
                a_, c_ = qx * ex + qy * ey, -qx * ey + qy * ex
                rr = np.sqrt((a_ / 0.75) ** 2 + c_ ** 2) / creature.r[0]
                hit = np.isfinite(dhit)
                mth = hit & (rr < 0.52) & (dhit < DEPTH_MID)
                lip = hit & (rr >= 0.52) & (rr < 0.82) & (dhit < DEPTH_MID)
            fall = np.clip(1 - (dhit - DEPTH_NEAR) / (DEPTH_FAR - DEPTH_NEAR), 0, 1)
            vis = rel ** 0.6 * fall
            vis = np.where(np.isfinite(dhit), vis, 0.0)
            vis = np.where(seamhit, vis - 0.13, vis)
            if creature.shell is not None:
                # membrana: a borda (onde o raio corre rente à casca) fica véu; o miolo do casulo, um tom mais escuro
                sfall = np.clip(1 - (shd - DEPTH_NEAR) / (DEPTH_FAR - DEPTH_NEAR), 0, 1)
                vis = np.maximum(vis, np.clip(shc * 0.075, 0, 0.52) * sfall)
                vis = np.maximum(vis, np.where(insc > 3, 0.2, 0) * sfall)
            vis = np.where(up, vis * 0.55, vis)                       # o tampo tem geada: quase não deixa ver
            vis = np.where(lip & np.isfinite(dhit) & ~mth, np.minimum(vis, 0.46), vis)
            vis = np.where(mth & np.isfinite(dhit), np.maximum(vis + 0.45, 0.9), vis)
            # franja difusa: perto de cada limiar o pixel decide pelo xadrez (sobe ou desce meio degrau)
            chk = ((np.round(hx).astype(int) + np.round(hy - hz).astype(int)) % 2) == 0
            vis = vis + np.where(chk, 0.035, -0.035)
            on = (b >= 1) & ~bub
            dim = on & (vis > 0.10) & (vis <= 0.34)
            b = np.where(dim & (b >= 2) & (b <= 6), np.maximum(b - 1, 1), b)
            b = np.where(on & (vis > 0.34) & (vis <= 0.58), 10, b)
            b = np.where(on & (vis > 0.58) & (vis <= 0.93), 11, b)
            b = np.where(on & (vis > 0.93), 12, b)

        # o brilho que percorre o gelo (animação): faixa diagonal varrendo da esquerda pra direita
        if glint and frame is not None:
            pos = GLINT_POS[frame % NFRAMES]
            band = np.abs((hx - (hy - hz) * 0.55) - pos) < 3.5
            b = np.where(band & lit & (b >= 3) & (b <= 5), b + 1, b)
            b = np.where(band & (b == 10), 3, b)
        return b.astype(np.uint8)
    return shade


# =================================================================================================================
# RENDER (geometria uma vez, pinta N vezes)
# =================================================================================================================
class Geo:
    def __init__(self):
        self.v = V.Volume(SW, SH, OX, OY, 0, 132, ice_dens, None)
        v = self.v
        sx, sy = grid(SW, SH)
        X = (sx - OX).astype(float).ravel()
        Y0 = (sy - OY).astype(float).ravel()
        n = X.size
        hitZ = np.full(n, np.nan)
        todo = np.arange(n)
        z = float(v.zmax)
        while z >= v.zmin and todo.size:
            hit = ice_dens(X[todo], Y0[todo] + z, np.full(todo.size, z)) > 0
            hitZ[todo[hit]] = z
            todo = todo[~hit]
            z -= 1.0
        hm = ~np.isnan(hitZ)
        hx, hz = X[hm], hitZ[hm]
        hy = Y0[hm] + hz
        e = 1.0
        gx = ice_dens(hx + e, hy, hz) - ice_dens(hx - e, hy, hz)
        gy = ice_dens(hx, hy + e, hz) - ice_dens(hx, hy - e, hz)
        gz = ice_dens(hx, hy, hz + e) - ice_dens(hx, hy, hz - e)
        nrm = -np.stack([gx, gy, gz], axis=1)
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
        lit = np.ones(hx.size, bool)
        px, py, pz = hx + nrm[:, 0] * 1.5, hy + nrm[:, 1] * 1.5, hz + nrm[:, 2] * 1.5
        for t in range(2, 200, 2):
            m = lit.copy()
            if not m.any() or pz.max() + V.L[2] * t > v.zmax + 2:
                break
            q = ice_dens(px[m] + V.L[0] * t, py[m] + V.L[1] * t, pz[m] + V.L[2] * t) > 0
            lit[np.nonzero(m)[0][q]] = False
        gm = np.nonzero(~hm)[0]
        sh = np.zeros(gm.size, bool)
        for t in range(2, 220, 2):
            if V.L[2] * t > SHADOW_ZMAX:          # a sombra no chão é a da parte de baixo (cabe no sprite)
                break
            sh |= ice_dens(X[gm] + V.L[0] * t, Y0[gm] + V.L[1] * t, np.full(gm.size, V.L[2] * t)) > 0
        self.hm, self.gm_sh = hm, gm[sh]
        self.args = (hx, hy, hz, nrm, lit)
        Zimg = np.full(n, np.nan)
        Zimg[hm] = hitZ[hm]
        Dimg = np.full(n, np.nan)
        Dimg[hm] = (Y0[hm] + hitZ[hm]) + hitZ[hm]
        self.Z, self.D = Zimg.reshape(SH, SW), Dimg.reshape(SH, SW)

    def paint(self, shade):
        idx = np.full(SW * SH, 255, np.uint8)
        idx[self.hm] = shade(*self.args)
        idx[self.gm_sh] = 9
        idx = idx.reshape(SH, SW)
        return finish(idx, self.Z, self.D)


def finish(idx, Z, D):
    """Igual ao Volume.finish, mas a linha de profundidade respeita os índices 10..12 (viram 0 também)."""
    solid = (idx != 255) & (idx != 9)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        Dn = V._sh(D, dy, dx, np.nan)
        sn = V._sh(solid, dy, dx, False)
        back = solid & sn & (np.nan_to_num(Dn, nan=-1e9) - D > 9)
        idx[back & (idx != 8)] = 0
    out = np.zeros_like(solid)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        out |= V._sh(solid, dy, dx, False) & ~solid
    idx[out] = 8
    return idx


_GEO: dict = {}


def geo():
    if "g" not in _GEO:
        _GEO["g"] = Geo()
    return _GEO["g"]


BREATH = (0.0, 0.02, 0.05, 0.07, 0.07, 0.05, 0.02, 0.0)       # a silhueta "respira" (±1 px nas bordas)


def render(key, frame=0, glint=False):
    br = BREATH[frame % NFRAMES] if frame is not None else 0.0
    cr = make_creature(key, br) if key else None
    return geo().paint(shade_fn(cr, frame, glint))


# =================================================================================================================
# PALETA
# =================================================================================================================
def ice_ramp(stage):
    return R.ramp("frost", stage, {"frost": R.ICE})


def deep_ramp(stage):
    """3 cores da silhueta (10 véu, 11 corpo, 12 miolo) a partir da rampa ICE do estágio + o contorno."""
    ice = ice_ramp(stage).astype(float)
    o = np.array(R.OUTLINE, float)
    veil = ice[1] * 0.75 + ice[2] * 0.25
    body = ice[0] * 0.85 + o * 0.15
    core = ice[0] * 0.40 + o * 0.60
    return np.array([veil, body, core]).round().astype(np.uint8)


def full_ramp(stage):
    return np.concatenate([ice_ramp(stage), deep_ramp(stage)], 0)


def colorize(idx, stage):
    return R.colorize(idx, full_ramp(stage))


# =================================================================================================================
# PEGADA, TIRA, GEADA, ESTILHAÇOS
# =================================================================================================================
def footprint_tiles(cover=0.40):
    """Tiles que bloqueiam: o corte da base do volume (Z = 1..3) cobre > `cover` do tile. (dx, dy) relativos ao tile
    da âncora (0, 0), que é o do meio da fileira de baixo; dy negativo = pra trás."""
    xs = np.arange(-160, 160, 1.0) + 0.5
    ys = np.arange(-170, 20, 1.0) + 0.5
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    m = np.zeros(X.shape, bool)
    for z in (1.0, 2.0, 3.0):
        m |= (ice_dens(X.ravel(), Y.ravel(), np.full(X.size, z)) > 0).reshape(X.shape)
    # o pé (âncora) fica 2 px acima da borda de baixo do tile: o tile (0, 0) cobre x em [-16, 16), y em [-30, 2)
    out = []
    for dy in range(-6, 2):
        for dx in range(-5, 6):
            x0, y0 = dx * T - 16, dy * T - 30
            sel = (X >= x0) & (X < x0 + T) & (Y >= y0) & (Y < y0 + T)
            if sel.any() and m[sel].mean() > cover:
                out.append((dx, dy))
    return out, m, (xs, ys)


GLINT_POS = (-260, -260, -130, -60, 10, 80, 150, -260)       # a faixa de brilho passa em 5 dos 8 quadros


def strip(key):
    frames = []
    for f in range(NFRAMES):
        br = BREATH[f]
        cr = make_creature(key, br)
        sh = shade_fn(cr, f, glint=True)
        frames.append(geo().paint(sh))
    return np.concatenate(frames, 1)


def frost_field(w=420, h=200, seed=57):
    """A geada grande em volta do gigante (a frost_ring esticada, com borda mais rasgada e manchas)."""
    xs, ys = grid(w, h)
    e = ((xs - w / 2) / (w / 2)) ** 2 + ((ys - h / 2) / (h / 2)) ** 2
    n = fbm(xs, ys, 18, seed, 3)
    a = np.full((h, w), 255, np.uint8)
    m = ((e + 0.75 * (n - 0.5)) < 1) & (e < 0.97)
    a[m] = 5
    a[m & (hash2(xs, ys, seed + 1) < 0.22 + 0.5 * np.clip(e - 0.6, 0, 1))] = 255
    a[m & (e < 0.55) & (fbm(xs, ys, 9, seed + 2, 2) > 0.56)] = 4
    a[m & (e < 0.35) & (fbm(xs, ys, 7, seed + 3, 2) > 0.62)] = 7
    return a


# estilhaços em volta: blocos do portão (mesmos PNG, quadro = tamanho), (x, y) do pé relativo à âncora do gigante
SHARDS = [
    # o monte que caiu da frente-direita (o lado que "rachou")
    dict(b="boulder_1", k=1, x=128, y=18),
    dict(b="slab_1", k=3, x=78, y=34),
    dict(b="boulder_0", k=5, x=40, y=40),
    dict(b="slab_0", k=6, x=170, y=-8),
    dict(b="boulder_1", k=6, x=112, y=50),
    dict(b="boulder_0", k=7, x=158, y=40),
    # o lado esquerdo: uma lasca grande tombada e caquinhos
    dict(b="shard_1", k=2, x=-142, y=-30),
    dict(b="slab_1", k=4, x=-112, y=26),
    dict(b="boulder_0", k=6, x=-160, y=14),
    dict(b="boulder_1", k=7, x=-64, y=40),
    # atrás (aparecem pouco, só pra o conjunto não ter "frente" de vitrine)
    dict(b="slab_0", k=5, x=-150, y=-96),
    dict(b="boulder_0", k=4, x=140, y=-100),
]
# caquinhos soltos (o decor_ice_chunks de hoje, 1..5): (seed, x, y)
CHIPS = [(1, -96, 52), (2, 12, 58), (3, 196, 22), (4, -190, -40), (5, 60, 66), (2, -30, 64), (4, 186, -70),
         (1, 92, 70), (3, -180, 40)]


def shard_img(item, stage):
    kind, v = item["b"].rsplit("_", 1)
    v = int(v)
    w, h, ox, oy, _ = B.frame_box(kind, v)
    idx = B.render(kind, v, B.SCALES[item["k"]])
    return R.colorize(idx, ice_ramp(stage)), ox, oy


# =================================================================================================================
# CENA (o mundo dos mockups da v9, faixa gelada)
# =================================================================================================================
SITE = (130, 13)            # tile da âncora do gigante no mundo dos mockups
PLAYER_T = (124, 14)


def scene(stage, key, frame=0, with_player=True):
    import regions_mockups as M
    import regions_scene as SC
    import regions_v9 as V9
    world = _world()
    gx, gy = SITE
    x0, y0 = gx * T + 16 - 480, gy * T - 300
    s = SC.Scene(world, x0, y0, stage=stage, water=V9.STAGE_WATER[stage])
    saved = M.GATES
    M.GATES = []
    try:
        M.populate(s, world, stage, player_at=None)
        V9.add_v9(s, world, stage)
    finally:
        M.GATES = saved
    bx, by = gx * T + T // 2, gy * T + T - 2
    # nada solto em cima do conjunto (no jogo: keep_clear em volta da pegada e dos estilhaços)
    s.objects = [o for o in s.objects if not (abs(o[2] + o[1].width / 2 - bx) < 230 and -170 < o[0] - by < 90)]
    s.ground_decals = [d for d in s.ground_decals
                       if not (abs(d[1] + d[0].width / 2 - bx) < 200 and abs(d[2] + d[0].height / 2 - (by - 50)) < 110)]
    ff = R.colorize(frost_field(), R.ramp("frost", stage))
    s.under_decals.append((ff, bx - ff.width // 2, by - 64 - ff.height // 2 + 10))
    for it in SHARDS:
        img, ox, oy = shard_img(it, stage)
        s.objects.append((by + it["y"], img, bx + it["x"] - ox, by + it["y"] - oy))
    from regions_formations import ice_chunks
    for sd, cx, cy in CHIPS:
        img = R.colorize(ice_chunks(sd), ice_ramp(stage))
        s.objects.append((by + cy, img, bx + cx - img.width // 2, by + cy - img.height))
    if frame is None:
        g = render(key, 0)
    else:
        g = strip_cache(key)[:, frame * SW:(frame + 1) * SW]
    s.objects.append((by, colorize(g, stage), bx - OX, by - OY))
    if with_player:
        pl = M.player_img(0, "side")
        px, py = PLAYER_T[0] * T + 16, PLAYER_T[1] * T + 30
        s.objects.append((py, pl, px - 16, py - 32))
    overlay = {"storm": M.storm_overlay, "mist": M.rain_overlay}.get(stage)
    return s.compose(overlay).convert("RGB")


_W: dict = {}
_S: dict = {}


def strip_cache(key):
    if key not in _S:
        _S[key] = strip(key)
    return _S[key]


def _world():
    if "w" not in _W:
        import regions_mockups as M
        w = M.build_world()
        gx, gy = SITE
        w["wall"][gy - 7:gy + 4, gx - 9:gx + 7] = False
        w["rocks"] = [r for r in w["rocks"] if not (abs(r[0] - gx) < 10 and abs(r[1] - gy) < 7)]
        _W["w"] = w
    return _W["w"]


# =================================================================================================================
# EXPORT (pendentes) + PRÉVIAS + REPORT
# =================================================================================================================
TILES_COVER = 0.30


def save_indexed(idx, rgb, path):
    im = Image.frombytes("P", (idx.shape[1], idx.shape[0]), np.ascontiguousarray(idx).tobytes())
    pal = [0] * 768
    for i, c in enumerate(rgb):
        pal[i * 3:i * 3 + 3] = [int(v) for v in c]
    im.putpalette(pal)
    trns = bytes([255] * 9 + [R.SHADOW_A] + [255] * (255 - 10) + [0])
    im.save(path, transparency=trns, optimize=False)


def hexs(arr):
    return [R.hexc(tuple(int(v) for v in c)) for c in arr]


def export():
    PEND.mkdir(parents=True, exist_ok=True)
    for old in PEND.glob("*"):
        old.unlink()
    for k in ALL:
        st = strip_cache(k)
        save_indexed(st[:, :SW], full_ramp("arid"), PEND / f"form_ice_giant_{k}.png")
        save_indexed(st, full_ramp("arid"), PEND / f"form_ice_giant_{k}_anim.png")
    save_indexed(frost_field(), R.ramp("frost", "arid"), PEND / "frost_field.png")
    tiles, _, _ = footprint_tiles(TILES_COVER)
    data = dict(
        note="v0.5 (PROPOSTA): gelo gigante da faixa gelada com a silhueta presa. O dono escolhe UMA variação "
             "(coil, s ou piece); a escolhida vira form_ice_giant.png + form_ice_giant_anim.png. PNG indexado: 0..7 "
             "rampa ICE (ramps.ICE.frost[estágio]), 8 contorno, 9 sombra (alfa 80), 10..12 a silhueta (rampa nova "
             "ICE_DEEP[estágio]), 255 transparente.",
        formation=dict(sprite="form_ice_giant.png", size_px=[SW, SH], foot=[OX, OY], size=[FOOT_W, FOOT_H],
                       tiles=sorted(tiles), region="frost", ramp="ICE", extra_ramp="ICE_DEEP", small=False,
                       count="1 por mundo, num canto da faixa gelada, longe dos gelos-portão",
                       keep_clear="retângulo 11×7 tiles centrado na pegada (os estilhaços e a geada moram aí)"),
        anim=dict(sprite="form_ice_giant_anim.png", frames=NFRAMES, frame=[SW, SH], fps=6,
                  rule="parado no quadro 0; a cada 9–14 s (sorteio) toca a tira 1 vez a 6 fps e volta pro 0",
                  breath=list(BREATH), glint_pos=list(GLINT_POS)),
        ramps=dict(ICE_DEEP={st: hexs(deep_ramp(st)) for st in R.STAGES}),
        shards=[dict(sprite=f"ice_block_{it['b']}.png", frame=it["k"], x=it["x"], y=it["y"]) for it in SHARDS],
        chips=[dict(sprite=f"decor_ice_chunks (seed {sd})", x=x, y=y) for sd, x, y in CHIPS],
        frost_field=dict(sprite="frost_field.png", size=[420, 200], ramp="BASE frost", at=[0, -54],
                         rule="camada de decalques, centro em (âncora.x, âncora.y − 54)"),
        variants=dict(ALL), approved=list(APPROVED),
        history="coil, s e piece são a 1ª rodada (verme comprido); larva, embryo, cocoon e fetal a 2ª (criatura em C)",
    )
    (PEND / "gelo_gigante.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return data


def checker(w, h, a=(42, 47, 56), b=(51, 57, 68), cell=8):
    xs, ys = grid(w, h)
    m = ((xs // cell + ys // cell) % 2) == 0
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.where(m[..., None], a, b)
    out[..., 3] = 255
    return Image.fromarray(out)


def previews():
    import regions_v9 as V9
    for k in ALL:
        st = strip_cache(k)
        colorize(st[:, :SW], "arid").save(OUT / f"giant_{k}.png")
        for stg in R.STAGES:
            colorize(st, stg).save(OUT / f"anim_{k}_{stg}.png")
        # 4 estágios lado a lado, no chão gelado
        row = Image.new("RGBA", (SW * 4 + 18, SH + 20), (21, 16, 14, 255))
        for i, stg in enumerate(R.STAGES):
            patch = V9.ground_patch("frost", stg, SW, SH + 20, 7 + i)
            patch.alpha_composite(colorize(st[:, :SW], stg), (0, 10))
            row.paste(patch, (i * (SW + 6), 0))
        row.save(OUT / f"stages_{k}.png")
        # GIF da animação (Árido), quadro 0 segurado
        fr = [colorize(st[:, f * SW:(f + 1) * SW], "arid") for f in range(NFRAMES)]
        bgp = V9.ground_patch("frost", "arid", SW, SH, 9)
        gif = []
        for f in [0] * 10 + list(range(NFRAMES)):
            im = bgp.copy()
            im.alpha_composite(fr[f])
            gif.append(im.convert("RGB"))
        pal = gif[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
        q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in gif]
        q[0].save(OUT / f"anim_{k}.gif", save_all=True, append_images=q[1:], duration=166, loop=0, disposal=1)
    # pegada: grade de tiles, tiles que bloqueiam, âncora
    tiles, m, (xs, ys) = footprint_tiles(TILES_COVER)
    K = 2
    W, H = 360, 300
    ax, ay = 180, 250
    im = V9.ground_patch("frost", "arid", W, H, 4)
    d = ImageDraw.Draw(im)
    for dx, dy in tiles:
        x0, y0 = ax + dx * T - 16, ay + dy * T - 30
        d.rectangle((x0, y0, x0 + T - 1, y0 + T - 1), fill=(255, 106, 85, 255))
    ii = np.nonzero(m)
    px = (xs[ii[1]] - 0.5 + ax).astype(int)
    py = (ys[ii[0]] - 0.5 + ay).astype(int)
    ok = (px >= 0) & (px < W) & (py >= 0) & (py < H)
    arr = np.array(im)
    arr[py[ok], px[ok], :3] = (arr[py[ok], px[ok], :3] * 0.5 + np.array([89, 208, 230]) * 0.5).astype(np.uint8)
    im = Image.fromarray(arr)
    im.alpha_composite(colorize(render("coil", 0), "arid"), (ax - OX, ay - OY))
    d = ImageDraw.Draw(im)
    for dx in range(-3, 4):
        for dy in range(-3, 1):
            x0, y0 = ax + dx * T - 16, ay + dy * T - 30
            d.rectangle((x0, y0, x0 + T - 1, y0 + T - 1), outline=(242, 196, 109, 255))
    for dx, dy in tiles:
        x0, y0 = ax + dx * T - 16, ay + dy * T - 30
        d.rectangle((x0 + 1, y0 + 1, x0 + T - 2, y0 + T - 2), outline=(255, 106, 85, 255))
    d.rectangle((ax - 2, ay - 2, ax + 2, ay + 2), fill=(89, 208, 230, 255))
    im.resize((W * K, H * K), Image.NEAREST).save(OUT / "footprint.png")
    return tiles


def scenes():
    out = []
    for k in ALL:
        for stg in R.STAGES:
            im = scene(stg, k, 0)
            im.save(OUT / f"scene_{k}_{stg}.png")
            out.append(f"scene_{k}_{stg}.png")
    # recorte ampliado (Árido) pra ver o Explorador do lado
    for k in ALL:
        Image.open(OUT / f"scene_{k}_arid.png").crop((240, 120, 720, 420)).save(OUT / f"crop_{k}_arid.png")
    # as 4 novas lado a lado: o mesmo recorte da mesma cena (Árido), só a criatura muda
    new = list(C_VARIANTS)
    cw, ch = 372, 280
    sheet = Image.new("RGB", (cw * len(new) + 6 * (len(new) - 1), ch), (21, 16, 14))
    for i, k in enumerate(new):
        sheet.paste(Image.open(OUT / f"scene_{k}_arid.png").crop((262, 110, 262 + cw, 110 + ch)), (i * (cw + 6), 0))
    sheet.save(OUT / "c_side_by_side.png")
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("_dbg*"):
        f.unlink()
    data = export()
    tiles = previews()
    scenes()
    import gelo_gigante_report as RR
    page = RR.build(data, tiles)
    print("ok:", page)
    print("tiles que bloqueiam:", sorted(tiles))


if __name__ == "__main__":
    main()
