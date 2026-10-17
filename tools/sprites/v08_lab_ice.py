"""v0.8 · gelo na porta do laboratório da Ilves (proposta B: gelo colado na porta dupla).

Overlay 64×72 desenhado em (x, y − 24) do 1º tile da porta dupla horizontal (o mesmo (x, y − 24) do
base_door2_h_s), por cima dos quadros fechados da porta. Os 16 px de baixo passam pro tile de chão de fora (o gelo
transborda no chão). 3 etapas + aberto (sem overlay, só a poça):
    lab_ice_door2_h_0   inteiro: placa de gelo grossa tampando o vão + blocos no pé
    lab_ice_door2_h_1   derretendo: placa baixou pra ~metade, rachada, pingando; a porta aparece em cima
    lab_ice_door2_h_2   quase: só os cacos no pé e a poça
    lab_ice_puddle_h    aberto: poça/geada no chão de fora (opcional, some com o tempo ou fica)
Paleta: a rampa ICE da faixa gelada no estágio Úmido (regions_palettes.json → ramps.ICE.frost.mist), a mesma dos
gelos-portão nesse estágio. Em r3d (volume de verdade, luz em faixas) com contorno #1b1630.
"""
from __future__ import annotations

import math

import numpy as np

import machines_r3d as MR
from r3d import Pal, Scene

ICE_MIST = ['#374451', '#425363', '#4d6676', '#587e92', '#6b93a3', '#80a4b1', '#90aeb9', '#4f575f']
P_ICEB = Pal(["#dceaf0", ICE_MIST[6], ICE_MIST[4], ICE_MIST[3], ICE_MIST[2]])     # bloco (brilho → fundo)
P_ICED = Pal([ICE_MIST[5], ICE_MIST[4], ICE_MIST[3], ICE_MIST[2], ICE_MIST[1]])  # gelo de dentro (mais fundo)
P_PUDDLE = Pal(["#6b93a3"] * 5, emit=True, emit_tone=0)
P_PUDDLE_D = Pal(["#374451"] * 5, emit=True, emit_tone=0)
P_HI = Pal(["#eef6fa"] * 5, emit=True, emit_tone=0)
W, H, GY = 64, 72, 57.0


def _scene():
    return Scene(W, H, ground=GY)


def _slab(sc, x0, x1, ztop, y0=-3.0, y1=2.0, seed=0, cracks=False):
    """Placa de gelo tampando o vão: blocos verticais irregulares lado a lado (topo em degraus, nada de agulha)."""
    xs = np.linspace(x0, x1, 6)
    tops = [ztop * k for k in (0.86, 1.0, 0.93, 0.97, 0.82)]
    for i in range(5):
        a, b = xs[i], xs[i + 1]
        t = tops[(i + seed) % 5]
        rz = (-0.05, 0.04, -0.02, 0.05, -0.04)[i]
        def paint(L, face, i=i, t=t):
            out = np.zeros(len(L), int)
            if face == 2:                                   # frente: núcleo mais fundo + 1 veio claro na diagonal
                x, z = L[:, 0], L[:, 2]
                out[(np.abs(x) < 2.2) & (z < t * 0.1) & (z > -t * 0.42)] = 1
                if i % 2 == 0:
                    out[(np.abs(x + z * 0.35 - (i % 3 - 1) * 1.5) < 0.35) & (z > -t * 0.1) & (z < t * 0.35)] = 2
            return out
        sc.obox(((a + b) / 2, (y0 + y1) / 2 - (i % 2) * 0.6, t / 2), ((b - a) / 2 + 0.3, (y1 - y0) / 2, t / 2),
                P_ICEB, rot_z=rz, paint=paint, extra=(P_ICED, P_HI))
        sc.obox(((a + b) / 2 - 0.5, (y0 + y1) / 2 - (i % 2) * 0.6 + 0.5, t + 0.6), ((b - a) / 2 - 0.6, 1.2, 0.8),
                P_ICEB, rot_z=rz, rot_x=0.4)                                            # chanfro em cima
    if cracks:
        for (x, z) in ((-12, 14), (-11, 13), (-10, 13), (-9, 12), (-9, 11), (6, 18), (7, 17), (7, 16), (8, 15),
                       (14, 10), (15, 9)):
            sc.dot(x, y0 - 0.2, z, ICE_MIST[1])


def _chunk(sc, x, y, r, h, rz=0.0):
    sc.rbox((x, y, h / 2), (r, r * 0.8, h / 2), min(1.2, r * 0.4), P_ICEB)
    sc.obox((x - 0.2, y - 0.2, h + 0.2), (r * 0.7, r * 0.55, 0.5), P_ICEB, rot_z=rz)


def _puddle(r):
    """Poça d'água derretida: chapada, sem contorno (decalque de chão)."""
    sc = _scene()
    sc.disc(0, -7, 0.15, r, P_PUDDLE_D)
    sc.disc(-1, -7.4, 0.2, r * 0.7, P_PUDDLE)
    sc.disc(-3.5, -8.5, 0.25, 1.4, P_HI)
    return sc.render(outline=False, inner=False)


def ice_door(stage):
    sc = _scene()
    puddle = {0: 0, 1: 9.0, 2: 12.0, 3: 10.0}[stage]
    if stage == 0:
        _slab(sc, -28, 28, 57.0)
        for (x, y, r, h, rz) in ((-22, -6, 4.2, 9, 0.2), (-12, -7.5, 3.4, 6, -0.3), (2, -6.5, 4.6, 11, 0.1),
                                 (15, -7, 3.6, 7, 0.4), (25, -5.5, 3.0, 8, -0.2), (-29, -3.5, 2.6, 13, 0)):
            _chunk(sc, x, y, r, h, rz)
        for (x, z) in ((-20, 40), (-6, 48), (10, 44), (21, 34)):                       # veios brancos de geada
            sc.dot(x, -3.4, z, "#ffffff")
            sc.dot(x + 1, -3.4, z - 1, "#dceaf0")
    elif stage == 1:
        _slab(sc, -24, 24, 28.0, y0=-2.5, y1=1.5, seed=2, cracks=True)
        for (x, y, r, h, rz) in ((-18, -6, 3.0, 6, 0.2), (4, -6.5, 3.4, 7, 0.1), (19, -6, 2.6, 5, -0.2)):
            _chunk(sc, x, y, r, h, rz)
        for (x, z) in ((-14, 29.0), (-14, 26.5), (9, 30.0), (9, 27.0), (0, 29.5), (-14, 22.0), (9, 23.0)):      # gotas escorrendo
            sc.dot(x, -3.0, z, "#dceaf0", always=True)
    elif stage == 2:
        for (x, y, r, h, rz) in ((-17, -4, 2.6, 4, 0.2), (-9, -6, 1.8, 3, -0.1), (8, -5, 2.4, 4, 0.3),
                                 (18, -4.5, 1.6, 2.5, 0)):
            _chunk(sc, x, y, r, h, rz)
    out = MR.Canvas(W, H)
    if puddle:
        out.a = _puddle(puddle).a.copy()
    if stage < 3:
        ice = MR.render(sc)
        m = ice.a[:, :, 3] == 255
        out.a[m] = ice.a[m]
    return out


NAMES = ["lab_ice_door2_h_0", "lab_ice_door2_h_1", "lab_ice_door2_h_2", "lab_ice_puddle_h"]


def all_stages():
    return {n: ice_door(i) for i, n in enumerate(NAMES)}
