#!/usr/bin/env python3
"""v0.7 M4 · destroços maiores · RODADA 3: VÉSPER-7 v2 (maior, menos "caixa"), 2 candidatas.

    python3 tools/sprites/build_wrecks_v07_m4_r3.py
    ->  reports/design/v07_m4_destrocos/pendentes/wreck_cargo_r3_{A,B}.png      (384×240 · pegada 12×6 · lift 48)

A mesma cargueira de ardósia em iso (o nome pintado, a faixa laranja desbotada, o porão aberto com a porta acesa),
agora feita no renderizador com z-buffer da rodada 2 (build_wrecks_v07_m4_r2.py):
  - casco em seção chanfrada (octógono) e NARIZ com volume: A chanfrado em cunha com para-brisa facetado,
    B arredondado com cabine-bolha;
  - porão na TRASEIRA (a popa, u = L, virada pra baixo-direita): boca grande, rampa de carga comprida até a areia,
    porta acesa no fundo do porão e luz no piso; motores em pilones dos dois lados da popa, por fora da boca;
  - trem de pouso articulado (braço, joelho, amortecedor com haste, sapata); a perna da frente de perto QUEBRADA,
    a de trás de longe afundada na areia; o nariz embicado no chão (casco inclinado 3°) com o casco amassado;
  - módulos no convés (espinha, radiadores, rádio, prato, antenas), costado com painel laranja desbotado, vigias,
    "VESPER-7", rebites e amassados.
Eixos como sempre: u = comprimento (proa em u = 0, lá em cima à esquerda; popa em u = L, embaixo à direita), v = largura
(+v = costado claro, de frente pra quem olha), z = altura.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_wrecks_v07_m4_r2 as R2  # noqa: E402
from build_wrecks_v07_m4_r2 import (GLR, METR, ORR, RUBR, RUSTR, SANDR, WOODR, ZR, box, cyl, disc, finish, mound,  # noqa: E402
                                    plate_poly, quad, ramp, rgb, rot, toneidx, tube)
from v07_lib import SHADOW, hsh, sand_pile, scatter  # noqa: E402
from v07_r2_destrocos import FONT  # noqa: E402

PEND = R2.PEND
SLR = ramp("#b4bcd6", "#9aa3c2", "#838cad", "#6f7898", "#5d6585", "#4b5273", "#363c54")
DECK = ramp("#a0a8c4", "#8f98b8", "#79829f", "#6f7898", "#575f7d", "#444b66")
ORF = ramp("#e9a37a", "#d9895c", "#c06f45", "#9a5636", "#7a4a3a")         # laranja desbotado
BD = "#1d1d32"
CYAN = ramp("#c8f6ff", "#8fe0ee", "#59d0e6", "#2b9fb8")
GOLDR = ramp("#ffe39a", "#f2c46d", "#c8963a", "#8a6420")
LEDR = ramp("#ff8a7a", "#ff5a4a", "#c83a2a", "#8a2a20")
HOLDR = ramp("#3a5a86", "#2c4268", "#22324e", "#18223c", "#121a30")
LIGHT = ramp("#e6f4ff", "#c8e2f6", "#a8c8e8", "#8fb4dc")

CARGO_R3 = dict(size=(12, 6), sprite=(384, 240), lift=48, crate=(6, 6), mouth=(10, 5), approach=(10, 6))
L = 200                      # comprimento do casco
HW, HZ0, HZ1, HD = 22, 6, 50, 26     # porão: meia largura, piso, teto, profundidade


def octo(w, zb, zt, cb=6, ct=12, dz=0.0):
    """Seção chanfrada (v,z) com meia largura w, base zb, topo zt; cb/ct = tamanho dos chanfros de baixo/de cima."""
    return [(-w + cb, zb + dz), (w - cb, zb + dz), (w, zb + cb + dz), (w, zt - ct + dz), (w - ct, zt + dz),
            (-w + ct, zt + dz), (-w, zt - ct + dz), (-w, zb + cb + dz)]


def roundsec(w, zb, zt, n=12, dz=0.0):
    """Seção quase redonda (superelipse) com o mesmo número de vértices em cada fatia."""
    zc, hz = (zb + zt) / 2 + dz, (zt - zb) / 2
    pts = []
    for i in range(n):
        a = -math.pi / 2 + 2 * math.pi * (i + .5) / n
        c, s = math.cos(a), math.sin(a)
        pts.append((w * np.sign(c) * abs(c) ** .7, zc + hz * np.sign(s) * abs(s) ** .7))
    return pts


def loft(zr, sections, fn, step=.45):
    """Casco entre fatias (u, [(v,z)...]) com o mesmo número de vértices. fn(face, s, P, l, N) -> (cores, keep);
    s = posição ao longo da aresta (unidades), P = pontos no mundo."""
    for (ua, A), (ub, Bs) in zip(sections, sections[1:]):
        A, Bs = np.array(A, float), np.array(Bs, float)
        ca, cb = A.mean(0), Bs.mean(0)
        n = len(A)
        for i in range(n):
            a0, a1, b0, b1 = A[i], A[(i + 1) % n], Bs[i], Bs[(i + 1) % n]
            le = max(np.linalg.norm(a1 - a0), np.linalg.norm(b1 - b0), .5)
            lu = math.hypot(ub - ua, *(b0 - a0)) + .5
            s, t = np.meshgrid(np.arange(0, 1 + 1e-6, step / le), np.arange(0, 1 + 1e-6, step / lu))
            s, t = s.ravel(), t.ravel()
            pa = a0 + np.outer(s, a1 - a0); pb = b0 + np.outer(s, b1 - b0)
            vz = pa + (pb - pa) * t[:, None]
            u = ua + (ub - ua) * t
            P = np.column_stack([u, vz[:, 0], vz[:, 1]])
            dS = np.column_stack([np.zeros(len(s)), *(((a1 - a0) + ((b1 - b0) - (a1 - a0)) * t[:, None]).T)])
            dT = np.column_stack([np.full(len(s), ub - ua), *((pb - pa).T)])
            N = np.cross(dS, dT)
            N /= np.linalg.norm(N, axis=1)[:, None] + 1e-9
            cen = ca + (cb - ca) * t[:, None]
            out = np.column_stack([np.zeros(len(s)), vz - cen])
            N = np.where(((N * out).sum(1) < 0)[:, None], -N, N)
            C, keep = fn(i, s * le, P, zr.light(N), N)
            zr.emit(P[keep], C[keep])


def font_mask(text, u0, z0, sz, U, Z):
    """Máscara da fonte 3×5 no plano (u,z): 1 px de fonte = sz unidades, linha de cima em z0."""
    m = np.zeros(len(U), bool)
    for i, ch in enumerate(text):
        for j, row in enumerate(R2.FONT2[ch]):
            for k, b in enumerate(row):
                if b == "1":
                    uu = u0 + (i * 4 + k) * sz
                    zz = z0 - j * sz
                    m |= (U >= uu) & (U < uu + sz) & (Z <= zz) & (Z > zz - sz)
    return m


CARGO_R4 = dict(size=(14, 7), sprite=(448, 272), lift=48, crate=(7, 7), mouth=(12, 6), approach=(12, 7))
VIEW = {"r3": (CARGO_R3, 74, 96, 1.0), "r4": (CARGO_R4, 91, 104, 1.17)}     # (contrato, x0, y0, escala g)


def vesper_r3(variant="A", view="r3"):
    """view "r4" (rodada 4): o MESMO desenho, renderizado 17% maior (g = 1,17) num canvas 448×272 · pegada 14×7."""
    meta, X0, Y0, G = VIEW[view]
    W, H = meta["sprite"]
    Bv = variant == "B"
    zr = ZR(W, H, X0, Y0, g=G, clip=True)
    sec_full = (lambda dz=0: roundsec(34, 4, 56, dz=dz)) if Bv else (lambda dz=0: octo(34, 4, 56, dz=dz))
    nsec = len(sec_full())

    # ---------- casco: proa (nariz) → corpo → popa
    if Bv:   # nariz redondo, mais baixo na ponta (bico de cargueiro)
        nose = [(0, roundsec(9, 18, 36, dz=0)), (8, roundsec(19, 11, 45)), (20, roundsec(27, 7, 51)), (36, roundsec(32, 5, 55)), (52, sec_full())]
    else:    # nariz em cunha chanfrada
        nose = [(0, octo(12, 14, 30, 3, 4)), (12, octo(22, 8, 42, 4, 8)), (28, octo(30, 5, 52, 5, 11)), (46, sec_full())]
    sections = nose + [(L - 6, sec_full()), (L, sec_full())]

    def hull(face, s, P, l, N):
        u, v, z = P[:, 0], P[:, 1], P[:, 2]
        idx = toneidx(l, len(SLR))
        out = SLR[idx].copy()
        side = (N[:, 1] > .8) & (np.abs(N[:, 2]) < .5)                       # costado claro (+v)
        top = N[:, 2] > .8
        # emendas de chapa (u a cada 16) e a borda das faces (a quina vira linha)
        seam = ((u % 16) < .5) & (u > 50)
        out[seam] = SLR[np.clip(idx[seam] + 1, 0, 6)]
        edge = s < .55
        out[edge] = SLR[np.clip(idx[edge] - 1, 0, 6)] if False else SLR[np.clip(idx[edge] + 1, 0, 6)]
        # costado: painel laranja desbotado com chevrons, vigias, nome, ventilação, rebites, faixa
        orp = side & (u > 24) & (u < 62) & (z > 18) & (z < 40)
        oi = np.clip(toneidx(l, 5), 0, 4)
        out[orp] = ORF[oi[orp]]
        fade = orp & (np.array([hsh(int(a), int(b), 3) for a, b in zip(u, z)]) > .72)
        out[fade] = SLR[3]
        chev = orp & (np.abs(((u - z * .8) % 12) - 6) < 1.1) & (z > 22) & (z < 34)
        out[chev] = ORF[3]
        band = side & (z > 15) & (z < 17.5) & (u > 50) & (u < L - 8)
        out[band] = ORF[2]
        win = side & (z > 33) & (z < 37) & (u > 68) & (u < 160) & (((u - 68) % 9) < 4)
        out[win] = CYAN[2]; out[win & (((u - 68) % 9) < 1.5)] = CYAN[0]
        vent = side & (u > 182) & (u < 196) & (z > 20) & (z < 38)
        out[vent] = np.where(((z[vent] % 3) < 1.4)[:, None], SLR[6], SLR[4])
        riv = side & ((np.abs(z - 41) < .5) | (np.abs(z - 13) < .5)) & ((u % 6) < .6)
        out[riv] = SLR[5]
        # para-brisa (na proa, chanfro de cima e topo)
        if Bv:
            gl = (u < 30) & (u > 6) & (N[:, 2] > .25) & (N[:, 1] > -.3) & (z > 30)
        else:
            gl = (u > 4) & (u < 30) & (face in (2, 3, 4)) & (z > 30) & (np.abs(v) < 30)
        if gl.any():
            gi = np.clip(toneidx(l, 4), 0, 3)
            out[gl] = GLR[np.clip(gi[gl] + 1, 1, 4)]
            mull = gl & ((np.abs(u - 13) < .6) | (np.abs(u - 20) < .6) | (np.abs(v) < .7))
            out[mull] = SLR[5]
            streak = gl & (np.abs((u - 8) - (z - 30) * 1.4) < .8)
            out[streak] = GLR[0]
        # amassado do impacto (nariz e costado baixo da frente) + riscos
        dent = (u < 60) & (z < 22) & (N[:, 1] > .3) & (np.array([R2_dent(a, b) for a, b in zip(u, z)]))
        out[dent] = SLR[np.clip(idx[dent] + 2, 0, 6)]
        scr = side & (u > 30) & (u < 70) & (np.abs((z - 8) - (u - 30) * .3) < .5)
        out[scr] = SLR[1]
        dirt = np.array([hsh(int(a), int(b), 5) for a, b in zip(u, z + v)]) > .95
        out[dirt] = SLR[np.clip(idx[dirt] + 2, 0, 6)]
        if top.any():
            dk = top & (np.array([hsh(int(a // 3), int(b // 3), 9) for a, b in zip(u, v)]) > .86)
            out[dk] = SLR[np.clip(idx[dk] + 1, 0, 6)]
        return out, np.ones(len(u), bool)

    global R2_dent
    R2_dent = lambda a, b: hsh(int(a // 5), int(b // 4), 17) > .55 and (a - 25) ** 2 / 900 + (b - 12) ** 2 / 100 < 1

    RAISE = 9                                                                # o casco fica em cima das pernas
    zr.push(rot("v", math.radians(-5)), pivot=(L, 0, 0), move=(0, 0, RAISE))  # embicada: o nariz desce e enterra

    def gz(u, v=0.0):
        """z local que cai no chão do mundo (z = 0) naquele (u, v), com a inclinação e a subida do casco."""
        M, t = zr.M, zr.t
        return -(M[2, 0] * u + M[2, 1] * v + t[2]) / M[2, 2]
    loft(zr, sections, hull)
    # nome: pixels da fonte 3×5 (2×2 px) projetados no costado com a mesma transformação; pintados no fim
    name_px = []
    for i, ch in enumerate("VESPER-7"):
        for j, row in enumerate(R2.FONT2[ch]):
            for k, b in enumerate(row):
                if b == "1":
                    for du in ((0, 1) if G == 1 else (0, .8, 1.6)):
                        for dz in ((0, 1) if G == 1 else (0, .8, 1.6)):
                            p3 = (zr.M @ np.array([72 + (i * 4 + k) * 2 + du, 34.6, 30 - j * 2 - dz]) + zr.t) * G
                            x = int(math.floor(zr.x0 + p3[0] - p3[1] + .5)); y = int(math.floor(zr.y0 + (p3[0] + p3[1]) / 2 - p3[2] + .5))
                            name_px.append((x, y, hsh(i * 9 + k, j * 3 + dz, 8) > .82))

    # ---------- popa: tampa com a BOCA do porão
    sec = np.array(sec_full())
    def popa(s, t, l):
        idx = np.clip(toneidx(l, len(SLR)), 0, 6)
        out = SLR[idx].copy()
        hole = (np.abs(s) < HW) & (t > HZ0) & (t < HZ1)
        frame = (np.abs(s) < HW + 3) & (t > HZ0 - 1) & (t < HZ1 + 3) & ~hole
        hz = frame & (((s + t) // 2.5) % 2 == 0)
        out[frame] = GOLDR[1]; out[hz] = rgb(BD)
        return out, ~hole
    plate_poly(zr, (L, 0, 0), (0, 1, 0), (0, 0, 1), [tuple(p) for p in sec], popa)
    # interior do porão
    def hfloor(s, t, l):
        out = np.tile(HOLDR[0], (len(s), 1))
        out[(s % 4) < .5] = HOLDR[1]
        glow = (np.abs(t - (HW - 12 - .0)) < 7) & (s > HD * .3)
        out[glow] = LIGHT[3]
        out[glow & ((s.astype(int) + t.astype(int)) % 2 == 0)] = LIGHT[2]
        return out, np.ones(len(s), bool)
    quad(zr, (L - HD, -HW, HZ0), (HD, 0, 0), (0, 2 * HW, 0), hfloor)
    def hwall(s, t, l):
        out = np.tile(HOLDR[2], (len(s), 1))
        out[(s % 5) < .6] = HOLDR[3]
        out[np.abs(t - (HZ1 - HZ0 - 8)) < .6] = CYAN[2]
        out[np.abs(t - (HZ1 - HZ0 - 8.8)) < .4] = CYAN[0]
        return out, np.ones(len(s), bool)
    quad(zr, (L - HD, -HW, HZ0), (HD, 0, 0), (0, 0, HZ1 - HZ0), hwall)         # parede de dentro (lado de lá)
    def hback(s, t, l):                                                      # fundo, com a porta acesa
        out = np.tile(HOLDR[3], (len(s), 1))
        out[(t % 7) < .6] = HOLDR[2]
        door = (s > 4) & (s < 17) & (t < 19)
        out[door] = LIGHT[1]
        out[door & (((s * 2 + t) % 7) < 1)] = LIGHT[0]
        fr = ((s > 3) & (s < 18) & (t < 20.5)) & ~door
        out[fr] = GOLDR[1]
        out[(np.abs(s - 20) < 1) & (np.abs(t - 10) < 1)] = rgb("#7fd67a")
        return out, np.ones(len(s), bool)
    quad(zr, (L - HD, -HW, HZ0), (0, 2 * HW, 0), (0, 0, HZ1 - HZ0), hback)
    for us in range(int(L - HD + 3), L, 6):                                  # costelas do teto
        box(zr, us, us + 1.2, -HW, HW, HZ1 - 2, HZ1, HOLDR)
    # carga presa no porão (lado de cá, o caminho até a porta fica livre)
    crate_r = ramp("#c98a56", "#9a5a3a", "#7a4a34", "#6c4030")
    box(zr, L - 20, L - 9, 8, 20, HZ0, HZ0 + 11, crate_r)
    box(zr, L - 18, L - 11, 10, 18, HZ0 + 11, HZ0 + 18, crate_r)
    box(zr, L - 20, L - 9, 13.5, 14.5, HZ0, HZ0 + 18.3, GOLDR, sides=("top", "v", "u"))      # cinta
    box(zr, L - 7, L - 2, -2, 4, HZ0, HZ0 + 5, crate_r)                     # caixote tombado na boca
    tube(zr, [(L - 4, -6, HZ1 - 1), (L - 4, -6, HZ1 - 10), (L - 3, -7, HZ1 - 16)], .5, RUBR)       # cabo pendurado
    box(zr, L - 3.6, L - 2.4, -7.6, -6.4, HZ1 - 18, HZ1 - 16, GOLDR)
    # lâmpada âmbar em cima da boca
    box(zr, L, L + 2, -3, 3, HZ1 + 4, HZ1 + 7, GOLDR)
    # ---------- motores em pilones dos dois lados da popa (por fora da boca), um apagado
    for (vm, lit) in ((-40, True), (40, False)):
        box(zr, L - 24, L - 6, vm * .8 - 3, vm * .8 + 3, 36, 44, SLR)       # pilone
        def nac(s, th, l, N):
            idx = toneidx(l, len(SLR))
            out = SLR[np.clip(idx, 0, 6)].copy()
            out[(s > 8) & (s < 10)] = ORF[2]
            out[(s % 7) < .5] = SLR[np.clip(idx[(s % 7) < .5] + 1, 0, 6)]
            return out, np.ones(len(s), bool)
        cyl(zr, (L - 30, vm, 44), "u", 38, lambda s: 10 if s > 6 else 6 + s * .67, nac)
        def noz(rho, th, l, lit=lit):
            out = np.tile(rgb("#17131e"), (len(rho), 1))
            out[rho > 8] = SLR[5]
            if lit:
                out[rho < 6] = CYAN[3]; out[rho < 3.5] = CYAN[2]; out[(rho < 2) & (th > .5)] = CYAN[0]
            else:
                out[(np.abs(np.sin(th - .7)) < .2) & (rho < 8)] = rgb("#58536b")
            return out, np.ones(len(rho), bool)
        disc(zr, (L + 8, vm, 44), "u", 10, noz)
    # ---------- ponte de comando atrás do nariz (volume em cima da cabine), janelas no lado claro
    def bridge_side(s_, t_, l):
        out = SLR[np.clip(toneidx(l, 7), 0, 6)].copy()
        wb = (t_ > 3) & (t_ < 8) & (s_ > 2) & (s_ < s_.max() - 2)
        out[wb] = GLR[3]; out[wb & (t_ > 6.5)] = GLR[1]
        out[wb & ((s_ % 6) < .7)] = SLR[5]
        out[t_ > t_.max() - .8] = SLR[0]
        return out, np.ones(len(s_), bool)
    if not Bv:
        box(zr, 30, 64, -20, 20, 54, 66, SLR, fns={"v": bridge_side})
        box(zr, 34, 60, -16, 16, 66, 69, DECK)
    else:   # B: cabine-bolha de vidro em cima do nariz arredondado
        def bub(s_, th, l, N):
            gi = np.clip(toneidx(l, 4), 0, 3)
            out = GLR[np.clip(gi + 1, 1, 4)].copy()
            out[(np.abs(np.cos(th)) < .08)] = SLR[4]
            out[(N[:, 2] > .6) & (N[:, 1] > .2)] = GLR[0]
            return out, np.ones(len(s_), bool)
        cyl(zr, (16, 0, 46), "u", 30, lambda s_: 13 * math.sqrt(max(0, 1 - ((s_ - 15) / 15.5) ** 2)), bub, th=(-.2, math.pi + .2))
        box(zr, 44, 70, -18, 18, 54, 64, SLR, fns={"v": bridge_side})
    # módulo lateral (caixa de equipamento presa no costado claro) e escada de acesso
    box(zr, 152, 168, 34, 40, 10, 28, SLR)
    for k in range(5):
        box(zr, 147, 150, 34, 35.2, 10 + k * 4, 11 + k * 4, METR, sides=("v", "top"))
    # radiadores abertos do lado de lá (quebram a silhueta por cima)
    def radw(s_, t_, l):
        out = np.tile(SLR[2], (len(s_), 1))
        out[(s_ % 3) < 1.2] = SLR[4]
        out[t_ > t_.max() - 1] = ORF[2]
        return out, np.ones(len(s_), bool)
    for (u0, u1) in ((96, 120), (124, 148)) if not Bv else ((96, 126),):
        plate_poly(zr, (0, -34, 50), (1, 0, 0), (0, -1, .35), [(u0, 0), (u1, 0), (u1 - 2, 24), (u0 + 2, 24)], radw, thick=1.2, dark="#363c54")
    # ---------- convés: espinha, radiadores, rádio, prato, antenas
    box(zr, 60, 170, -16, 16, 56, 63, DECK)
    box(zr, 70, 96, -10, 10, 63, 67, DECK)
    def rad(s, t, l):
        out = np.tile(SLR[3], (len(s), 1))
        out[(s % 2.4) < 1.2] = SLR[1]
        out[t > t.max() - .8] = SLR[0]
        return out, np.ones(len(s), bool)
    for vr in ((-26, -18), (18, 26)) if not Bv else ((18, 26),):
        box(zr, 108, 150, vr[0], vr[1], 54, 58, SLR, fns={"top": rad})
    if Bv:   # B: dois contêineres de carga presos no convés de trás
        for (u0, c) in ((150, ramp("#e8a066", "#c97a45", "#a5582c", "#7a4020")), (172, ramp("#9fa8c8", "#7f89ad", "#626b8e", "#4b5273"))):
            box(zr, u0, u0 + 18, -14, 14, 56, 70, c)
            box(zr, u0, u0 + 18, -1, 1, 70, 70.6, GOLDR, sides=("top",))
    else:
        box(zr, 176, 190, -12, 12, 56, 62, DECK)                              # caixa de rádio
        for k in range(4):
            box(zr, 178 + k * 3, 179 + k * 3, -10, 10, 62, 62.6, SLR, sides=("top",))
    # escotilha redonda e cúpula de sensores
    def hatch(rho, th, l):
        out = np.tile(SLR[3], (len(rho), 1)); out[rho > 5] = rgb(BD); out[rho < 3.5] = SLR[1]
        out[(np.abs(np.sin(th)) < .15) & (rho < 5)] = rgb(BD)
        return out, np.ones(len(rho), bool)
    disc(zr, (120, 0, 63.2), "z", 6, hatch)
    def dome(s, th, l, N):
        return CYAN[np.clip(toneidx(l, 4), 0, 3)], np.ones(len(s), bool)
    cyl(zr, (40 if not Bv else 58, -6, 54), "z", 6, lambda s: math.sqrt(max(0, 36 - s * s)), dome, th=(0, 2 * math.pi))
    # prato de comunicação inclinado
    zr.push(rot("u", math.radians(28)), pivot=(160 if not Bv else 140, -20, 66))
    def dish(rho, th, l):
        out = np.tile(SLR[1], (len(rho), 1)); out[rho > 7] = SLR[3]; out[rho < 2] = SLR[4]
        return out, np.ones(len(rho), bool)
    disc(zr, (160 if not Bv else 140, -20, 70), "z", 8, dish)
    zr.pop()
    tube(zr, [(160 if not Bv else 140, -20, 60), (160 if not Bv else 140, -20, 68)], .9, METR)
    for (ua, va, h_) in ((186, -18, 26), (64, 12, 16)):
        tube(zr, [(ua, va, 62), (ua, va, 62 + h_)], .5, METR)
        box(zr, ua - 1.2, ua + 1.2, va - 1.2, va + 1.2, 62 + h_, 64.5 + h_, LEDR)
    # ---------- trem de pouso: braço, joelho, amortecedor, sapata (A e B iguais; o da frente de perto quebrou)
    ground_bits = []

    def leg(u, side, state):
        vs = 34 * side
        hip = (u, vs - 2 * side, 12)
        knee = (u - 5, vs + 15 * side, 16)
        fz = gz(u - 9, vs + 20 * side)
        foot = (u - 9, vs + 20 * side, fz + 2.6)
        box(zr, hip[0] - 4, hip[0] + 4, hip[1] - 3, hip[1] + 3, 8, 16, SLR)            # caixa da dobradiça no casco
        tube(zr, [hip, knee], 2.3, SLR[2:])                                              # braço
        tube(zr, [(hip[0], hip[1], hip[2] - 3), (knee[0], knee[1], knee[2] - 4)], 1.0, METR)   # tirante
        box(zr, knee[0] - 2.5, knee[0] + 2.5, knee[1] - 2.5, knee[1] + 2.5, knee[2] - 2.5, knee[2] + 2.5, SLR)   # joelho
        if state == "broken":
            tube(zr, [knee, (knee[0] - 1, knee[1] + 2 * side, knee[2] - 6)], 2.6, SLR[3:])   # toco do amortecedor
            ground_bits.append((u, vs, side))
            return
        mid = tuple(knee[i] + (foot[i] - knee[i]) * .5 for i in range(3))
        tube(zr, [knee, mid], 3.0, SLR[3:])                                  # cilindro do amortecedor
        tube(zr, [mid, foot], 1.5, METR)                                     # haste cromada
        box(zr, mid[0] - 3.4, mid[0] + 3.4, mid[1] - 3.4, mid[1] + 3.4, mid[2] - 1, mid[2] + 1, ORF)   # anel de aviso
        def pad(rho, th, l):
            out = np.tile(SLR[2], (len(rho), 1)); out[rho > 6.5] = SLR[4]; out[rho < 2] = SLR[5]
            return out, np.ones(len(rho), bool)
        zz = fz if state == "ok" else fz - 3.5
        disc(zr, (foot[0], foot[1], zz + 2.4), "z", 8, pad)
        cyl(zr, (foot[0], foot[1], zz), "z", 2.4, lambda s: 8, lambda s, th, l, N: (SLR[np.clip(toneidx(l, 7), 0, 6)], np.ones(len(s), bool)))
    leg(52, 1, "broken"); leg(166, 1, "ok"); leg(52, -1, "ok"); leg(166, -1, "sunk")
    # ---------- rampa de carga até a areia (porão na traseira)
    RL = 58
    def rampf(s, t, l):
        out = np.tile(DECK[2], (len(s), 1))
        out[(s % 5) < .8] = DECK[4]
        pool = (s < 26) & (np.abs(t - HW) < 14)
        out[pool & ((s % 5) >= .8)] = LIGHT[2]
        out[pool & ((s % 5) >= .8) & (s < 12) & (np.abs(t - HW) < 8)] = LIGHT[1]
        edge = (t < 1.6) | (t > 2 * HW - 1.6)
        out[edge] = GOLDR[1]
        led = edge & ((s % 8) < 1.5)
        out[led] = CYAN[1]
        return out, np.ones(len(s), bool)
    quad(zr, (L, -HW, HZ0), (RL, 0, gz(L + RL) - HZ0), (0, 2 * HW, 0), rampf)
    for vv in (-HW - .5, HW + .5):                                           # trilhos laterais
        tube(zr, [(L, vv, HZ0 + 3), (L + RL, vv, gz(L + RL) + 2.5)], .6, GOLDR)
    zr.pop()
    # perna quebrada: o pedaço de baixo do amortecedor caído na areia, a sapata virada, chapa amassada
    for (u, vs, side) in ground_bits:
        tube(zr, [(u - 20, vs + 28 * side, 2.2), (u - 6, vs + 36 * side, 2.2)], 2.6, SLR[3:])
        tube(zr, [(u - 6, vs + 36 * side, 2.0), (u + 3, vs + 38 * side, 1.6)], 1.4, METR)
        zr.push(rot("u", math.radians(70 * side)), pivot=(u - 26, vs + 24 * side, 2))
        box(zr, u - 34, u - 20, vs + 20 * side - 7, vs + 20 * side + 7, 0, 2.6, SLR)
        zr.pop()
        zr.push(rot("z", math.radians(-20)), pivot=(36, 44, 0))
        box(zr, 26, 44, 40, 50, 0, 2, SLR)
        zr.pop()
    # ---------- areia e coisas no chão (fora da inclinação)
    mound(zr, 6, 14, 18, 26, 9, 1)                                           # o nariz enterrado
    mound(zr, 30, 52, 14, 9, 3, 2)
    mound(zr, L + 52, 0, 7, 14, 1.8, 7)                                  # areia escorrida no pé da rampa
    crate_r2 = ramp("#7f89ad", "#626b8e", "#4b5273", "#363b58")
    zr.push(rot("z", math.radians(14)), pivot=(L + 19, 33, 0))
    box(zr, L + 14, L + 24, 28, 38, 0, 10, crate_r)
    zr.pop()
    box(zr, L + 30, L + 36, 24, 30, 0, 6, crate_r2)
    box(zr, L + 6, L + 14, 36, 44, 0, 8, crate_r)
    box(zr, 110, 118, 56, 64, 0, 7, crate_r2)
    box(zr, 128, 134, 52, 58, 0, 5, crate_r)
    for (u, v) in ((96, 58), (140, 60), (78, 62)):
        zr.push(rot("z", math.radians(-25 + 50 * hsh(u, v, 3))), pivot=(u, v, 0))
        box(zr, u, u + 14, v, v + 5, 0, 1.4, SLR)
        zr.pop()
    tube(zr, [(150, 36, 12), (152, 48, 2), (160, 58, .8), (176, 62, .8)], .6, RUBR)          # cabo solto

    def ground(cv):
        P = lambda u, v: (zr.x0 + G * (u - v), zr.y0 + G * (u + v) / 2)
        cv.poly([P(4, -30), P(L + 14, -30), P(L + 14, 44), P(4, 44)], SHADOW)
        sand_pile(cv, *P(60, 50), 30 * G, 6 * G, 3); sand_pile(cv, *P(170, 50), 26 * G, 5 * G, 4)
        scatter(cv, [(round(X0 + (x - 74) * G), round(Y0 + (y - 96) * G)) for (x, y) in
                     [(20, 222), (60, 230), (130, 232), (190, 228), (250, 233), (300, 226), (360, 200), (12, 200)]], 11)
    cv = finish(W, H, zr, BD, ground)
    img = np.array(cv.im)
    for (x, y, worn) in name_px:
        if img[y, x, 3] == 255:
            img[y, x, :3] = SLR[2] if worn else rgb("#e8ecfa")
    cv.im = Image.fromarray(img)
    cv.meta = dict(meta)
    return cv


R2_dent = None


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for v in "AB":
        c = vesper_r3(v)
        assert c.im.size == tuple(c.meta["sprite"])
        c.im.save(PEND / f"wreck_cargo_r3_{v}.png")
        out[v] = c.meta
        print(v, c.meta)
        c = vesper_r3(v, "r4")                                               # rodada 4: o mesmo, 17% maior
        assert c.im.size == tuple(c.meta["sprite"])
        c.im.save(PEND / f"wreck_cargo_r4_{v}.png")
        print(v, "r4", c.meta)
    return out


if __name__ == "__main__":
    main()
