#!/usr/bin/env python3
"""Hesper v0.7 M4 · rodada 6: beliche de parede na HORIZONTAL (2×1, 64×40, lugar desk) e o traje caprichado
(macacão largado no chão, decal 32×32, e o traje EVA no armário, 32×40), com candidatas A/B nos dois do traje.

Rascunho do dono: a cama deitada ao longo da parede norte, no comprido, com dois cabos saindo dos cantos da frente e
subindo até a parede (referência: cama suspensa por cabo de aço com esticador). Só a ideia/estilo; o desenho é nosso.

Sufixo _r6 (candidatas _r6_A / _r6_B); as rodadas anteriores não são sobrescritas. Rode depois do r4 (usa a casca e a
montagem dele) e do r5 (os cilindros de O₂ da montagem). Determinístico, alpha só 0/255 (a sombra de chão no nível fixo do kit).

Saída: reports/design/v07_m4/pendentes/{prop_wall_bunk_r6, prop_uniforms_r6_{A,B}, prop_suit_locker_r6_{A,B}}.png
       + icon_*.png de cada ; reports/design/v07_m4/sala_r6_alojamento_{A,B}_{clara,escura}.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chests_r3d as CH  # noqa: E402
import build_vesper_v07 as V  # noqa: E402
import build_vesper_v07_r2 as R2  # noqa: E402
import build_vesper_v07_r4 as R4  # noqa: E402
import r3d  # noqa: E402
from r3d import CA, SA, Pal, Scene, rgb  # noqa: E402

PEND, REP, T, OUT = V.PEND, V.REP, V.T, V.OUT
SL, SLD, CR, OR, SCR, GO = R4.SL, R4.SLD, R4.CR, R4.OR, R4.SCR, R4.GO
SHADOW = R4.SHADOW
STEEL = Pal(["#d4d8e8", "#a8adc6", "#7f84a3", "#5d6280", "#3d405a"])           # cabo de aço / argola
CABLE = Pal(["#a8adc6", "#8f94b4", "#6a6f90", "#4a4e6b", "#2e3048"])           # cabo de aço (mais escuro)
MATT = Pal(["#d8dcea", "#bfc3d8", "#a3a8c2", "#7f84a3", "#5d6280"])            # colchão (lona clara, fria)
BLANK = Pal(["#e99a66", "#d27e50", "#b8643e", "#94503a", "#6a3830"])           # cobertor laranja desbotado
BLANK_D = Pal(["#c87a50", "#b0623e", "#985034", "#7a3e2e", "#5a2e28"])
PILLOW = Pal(["#ffffff", "#eceaf2", "#d6d2e2", "#b0abc4", "#8a85a2"])
SPEC = Pal(["#ffffff"] * 5, emit=True, emit_tone=0)


# ---------------------------------------------------------------------------------------------------------------------
# Cena com escala (o mesmo modelo serve pro sprite e pro ícone) + superfície paramétrica (pano amarrotado)
# ---------------------------------------------------------------------------------------------------------------------
class S6:
    def __init__(self, sc, k=1.0):
        self.sc, self.k = sc, k

    def t(self, v):
        return tuple(a * self.k for a in v)

    def box(self, xr, yr, zr, pal, **kw):
        self.sc.box(self.t(xr), self.t(yr), self.t(zr), pal, **kw)

    def obox(self, c, h, pal, **kw):
        self.sc.obox(self.t(c), self.t(h), pal, **kw)

    def rbox(self, c, h, r, pal, **kw):
        if kw.get("pivot") is not None:
            kw["pivot"] = self.t(kw["pivot"])
        self.sc.rbox(self.t(c), self.t(h), max(r * self.k, 0.3), pal, **kw)

    def cyl(self, cx, cy, r, z0, z1, pal, **kw):
        k = self.k
        if kw.get("r_top") is not None:
            kw["r_top"] *= k
        self.sc.cyl(cx * k, cy * k, max(r * k, 0.6), z0 * k, z1 * k, pal, **kw)

    def sphere(self, c, r, pal, **kw):
        self.sc.sphere(self.t(c), max(r * self.k, 0.6), pal, **kw)

    def tube(self, pts, r, pal, **kw):
        self.sc.tube([self.t(p) for p in pts], max(r * self.k, 0.45), pal, **kw)

    def dot(self, x, y, z, c, always=False):
        self.sc.dot(x * self.k, y * self.k, z * self.k, c, always=always)

    def psurf(self, u, v, fn, pal, paint=None, extra=(), keep=None):
        """Superfície paramétrica: fn(U, V) -> (X, Y, Z) (arrays). Normal = derivada numérica, virada pra câmera.
        paint(U, V) -> índice em [pal, *extra]."""
        k = self.k
        U, Vv = np.meshgrid(u, v)
        U, Vv = U.ravel(), Vv.ravel()
        if keep is not None:
            m = keep(U, Vv)
            U, Vv = U[m], Vv[m]
        e = 1e-3
        P = np.stack(fn(U, Vv), 1)
        du = (np.stack(fn(U + e, Vv), 1) - np.stack(fn(U - e, Vv), 1))
        dv = (np.stack(fn(U, Vv + e), 1) - np.stack(fn(U, Vv - e), 1))
        N = np.cross(du, dv)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        view = np.array([0, -CA, SA])
        N[(N @ view) < 0] *= -1
        idx = np.broadcast_to(np.asarray(paint(U, Vv), int), (len(P),)) if paint else np.zeros(len(P), int)
        self.sc._emit(P * k, N, idx, [pal, *extra], cull=False)


def grid(a, b, n_per_unit=1 / r3d.STEP):
    return np.linspace(a, b, max(int(abs(b - a) * n_per_unit) + 2, 3))


def cut(img_scene, size):
    """Recorta a cena renderizada no bbox e centraliza num quadro `size` (sem reamostrar)."""
    im = img_scene
    bb = im.getbbox()
    c = im.crop(bb)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    assert c.width <= size[0] and c.height <= size[1], (c.size, size)
    out.alpha_composite(c, ((size[0] - c.width) // 2, (size[1] - c.height) // 2))
    return out


def alpha_ok(im, name):
    al = set(np.unique(np.array(im)[:, :, 3]).tolist())
    assert al <= {0, 255, SHADOW[3]}, f"{name}: alpha {al}"


# ---------------------------------------------------------------------------------------------------------------------
# 1 · Beliche de parede horizontal (prop_wall_bunk), 2×1, 64×40, lugar desk
# ---------------------------------------------------------------------------------------------------------------------
# Coordenadas: Y=0 é o pé da parede norte (cai na linha 8 do sprite, onde a face da parede termina no jogo), Y<0 vem
# pra frente. A cama fica a ~10 de distância no modelo, mas o tampo dela tapa o pé da parede: na tela ela encosta.
BUNK = dict(x=27.2, yb=-15.1, yf=-30.8, z0=4.0, z1=9.4, zm=13.2, ax=18.5, az=7.6)


def bunk_model(s, d=True):
    x, yb, yf, z0, z1, zm = (BUNK[k] for k in ("x", "yb", "yf", "z0", "z1", "zm"))
    ym, hy = (yb + yf) / 2, (yb - yf) / 2

    def plat_paint(L, N):      # friso laranja na borda da frente, com as juntas da chapa
        idx = np.zeros(len(L), int)
        front = N[:, 1] < -0.8
        band = front & (np.abs(L[:, 2] + 0.1) < 0.8)
        idx[band] = 1
        idx[band & (np.abs((L[:, 0] + x) % 13.5 - 6.75) < 0.4)] = 2
        return idx
    s.rbox((0, ym, (z0 + z1) / 2), (x, hy, (z1 - z0) / 2), 0.8, SL, paint=plat_paint if d else None, extra=(OR, SLD))
    s.box((-x + 1.5, x - 1.5), (yf + 0.8, yb - 0.5), (z0 - 1.0, z0), SLD)                        # nervura de baixo
    # orelhas de chapa nas quinas da frente, pra fora da cama: é nelas que o cabo prende
    for sx in (-1, 1):
        s.box((sx * x - 0.2 * sx, sx * (x + 2.0)) if sx > 0 else (-(x + 2.0), -x + 0.2), (yf + 0.4, yf + 3.0), (z1 - 2.6, z1 - 0.4), SLD)
    # colchão grosso
    s.rbox((0, ym + 0.2, (z1 + zm) / 2), (x - 0.9, hy - 0.7, (zm - z1) / 2), 1.6, MATT,
           paint=(lambda L, N: np.where((N[:, 1] < -0.7) & (np.abs(L[:, 2]) < 0.3), 1, 0)) if d else None, extra=(PILLOW,))
    # travesseiro do lado esquerdo
    s.rbox((-x + 6.0, ym + 1.2, zm + 1.1), (4.2, hy - 2.4, 1.5), 1.4, PILLOW)
    # cobertor laranja desbotado, amarrotado: tampo + aba que cai pela frente do colchão
    bx0, bx1 = -x + 13.0, x - 0.3

    def edge_x(Vv):            # borda da cabeceira do cobertor: torta, puxada pra trás no canto do fundo
        return bx0 + 1.4 * np.sin((Vv - yf) * 0.42) + (Vv - yf) * 0.12

    def fold(U, Vv):
        return 1.25 * np.sin(U * 0.30 + Vv * 0.45 + 0.6) + 0.55 * np.sin(U * 0.66 - Vv * 0.32 + 2.0)

    def top(U, Vv):
        e = np.clip((U - edge_x(Vv)) / 1.6, 0, 1)
        return U, Vv, zm + 0.5 + e * (1.6 + 0.75 * fold(U, Vv))

    s.psurf(grid(bx0 - 2, bx1), grid(yf + 0.1, yb - 0.6), top, BLANK, keep=lambda U, Vv: U >= edge_x(Vv),
            paint=(lambda U, Vv: np.where(np.abs(U - edge_x(Vv) - 2.6) < 0.55, 1, 0)) if d else None, extra=(BLANK_D,))

    def drape(U, Vv):          # V: 0 em cima (emenda com o tampo) .. 1 embaixo
        z_top = top(U, np.full_like(U, yf + 0.1))[2]
        zbot = z1 + 0.9 + 1.3 * (0.5 + 0.5 * np.sin(U * 0.33 + 1.2))
        z = z_top - Vv * (z_top - zbot)
        y = yf + 0.1 - 1.0 * np.sin(Vv * math.pi * 0.55) - 0.5 * (0.5 + 0.5 * np.sin(U * 0.8)) * Vv
        return U, y, z

    if d:
        s.psurf(grid(bx0 - 2, bx1 - 0.3), grid(0, 1, 16), drape, BLANK, keep=lambda U, Vv: U >= edge_x(np.full_like(U, yf + 0.1)),
                paint=lambda U, Vv: np.where(np.abs(U - edge_x(np.full_like(U, yf + 0.1)) - 2.6) < 0.55, 1, 0), extra=(BLANK_D,))


def bunk_cables(s, d=True):
    """Os 2 cabos numa cena à parte, desenhada POR CIMA da cama: a ancoragem fica no alto da parede, então o cabo
    passa na frente do tampo (como na foto de referência). Olhal na orelha da quina -> cabo -> esticador -> cabo ->
    argola na chapa da parede."""
    x, yf, z1, ax, az = (BUNK[k] for k in ("x", "yf", "z1", "ax", "az"))
    for sx in (-1, 1):
        a = np.array((sx * (x + 0.9), yf + 1.6, z1 - 0.6))
        b = np.array((sx * ax, -0.9, az))
        s.box((sx * ax - 1.8, sx * ax + 1.8), (-0.8, 0.0), (az - 1.6, az + 1.0), SLD)        # chapa de ancoragem
        if d:
            s.dot(sx * ax - 1.2, -1.0, az - 0.4, "#9096b4", always=True)
            s.dot(sx * ax + 1.2, -1.0, az - 0.4, "#9096b4", always=True)
        s.sphere(tuple(a), 0.9, STEEL)
        t0, t1 = 0.36, 0.56
        # (o cabo usa o aço mais escuro pra não sumir em cima do travesseiro branco)
        p0, p1 = a + (b - a) * t0, a + (b - a) * t1
        s.tube([tuple(a), tuple(p0)], 0.42, CABLE, caps=False)
        s.tube([tuple(p1), tuple(b)], 0.42, CABLE, caps=False)
        s.tube([tuple(p0), tuple(p1)], 0.9, GO)


def bunk_sprite():
    sc = Scene(64, 40, ground=8.0)
    bunk_model(S6(sc), True)
    cv = sc.render()
    CH.check(cv, "bunk", (64, 40))
    im = cv.image().convert("RGBA")
    sc2 = Scene(64, 40, ground=8.0)
    bunk_cables(S6(sc2), True)
    cab = sc2.render()
    CH.check(cab, "bunk_cab", (64, 40))
    im.alpha_composite(cab.image().convert("RGBA"))
    # sombra no chão, embaixo e na frente da cama suspensa (nível fixo)
    sh = Image.new("RGBA", (64, 40), (0, 0, 0, 0))
    yf = BUNK["yf"]
    y_floor = 8.0 - yf * SA
    ImageDraw.Draw(sh).rectangle([3, int(y_floor) - 5, 60, int(y_floor) + 1], fill=SHADOW)
    sh.alpha_composite(im)
    return sh


def bunk_icon():
    """Ícone à mão (a cama é larga demais pra sair legível do modelo em 16 px): cama deitada + os 2 cabos subindo."""
    f = V.Img(16, 16)
    f.rect(1, 7, 14, 9, "#e2733a")                                   # cobertor (tampo)
    f.rect(1, 7, 4, 9, "#ffffff")                                    # travesseiro
    f.rect(1, 9, 4, 9, "#d6d2e2")
    f.px(7, 8, "#c25e32"); f.px(8, 8, "#c25e32"); f.px(11, 7, "#c25e32"); f.px(12, 8, "#c25e32")   # dobras
    f.rect(5, 10, 14, 10, "#c25e32")                                 # a aba que cai na frente
    f.rect(1, 10, 4, 10, "#bfc3d8")                                  # colchão
    f.rect(1, 11, 14, 11, "#b4b9d2")                                 # plataforma: luz em cima
    f.rect(1, 12, 14, 12, "#e2733a")                                 # friso laranja
    f.rect(1, 13, 14, 13, "#4a4e6b")
    for (x0, y0, x1, y1) in ((1, 11, 5, 3), (14, 11, 10, 3)):        # cabos, com o esticador dourado no meio
        n = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(n + 1):
            x, y = round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)
            f.px(x, y, "#f2c46d" if i in (3, 4) else "#c4c8dc")
    for x in (4, 10):                                                # chapas na parede
        f.rect(x, 1, x + 1, 2, "#6a6f90")
    R4.outline_img(f)
    return f.im


# ---------------------------------------------------------------------------------------------------------------------
# 2 · Armário de traje (prop_suit_locker), 32×40, floor, colide · candidatas A e B
# ---------------------------------------------------------------------------------------------------------------------
SUIT = Pal(["#ffffff", "#eceaf2", "#d4d0e0", "#a9a4bd", "#77728f"])               # tecido do traje EVA
VISOR = Pal(["#4a6aa8", "#2c3a6e", "#1f2a52", "#161d3a", "#0e1228"])              # visor azul-marinho (o do astronauta)
VISOR_G = Pal(["#fff0b8", "#f2c46d", "#c8923c", "#8a5a28", "#5a3a1e"])            # viseira solar dourada (B)
HOSE = Pal(["#bfeaf6", "#7fd0e6", "#4fa8c8", "#357f9e", "#22566e"])               # mangueira de ar (ciano do O₂)
HOSE_D = Pal(["#7fd0e6", "#4fa8c8", "#357f9e", "#22566e", "#163a4a"])
GLOVE = Pal(["#8f94b4", "#6a6f90", "#4a4e6b", "#3a3d56", "#2e3048"])
REFL = Pal(["#d4ecff"] * 5, emit=True, emit_tone=0)
REFL2 = Pal(["#7fa8e0"] * 5, emit=True, emit_tone=0)
LEDG = R4.LEDG
LEDO = R4.LEDO
DIMC = Pal(["#59d0e6"] * 5, emit=True, emit_tone=0)


def helmet(s, c, r, gold=False, d=True):
    """Capacete: casco branco, visor com reflexo (mancha clara + arco), anel do pescoço."""
    vp = VISOR_G if gold else VISOR
    L1 = np.array([-0.55, -0.62, 0.56]); L1 /= np.linalg.norm(L1)
    L2 = np.array([0.42, -0.80, -0.20]); L2 /= np.linalg.norm(L2)

    def paint(N):
        idx = np.zeros(len(N), int)
        rim = (N[:, 1] < -0.12) & (N[:, 2] < 0.66) & (N[:, 2] > -0.62) & (np.abs(N[:, 0]) < 0.9)
        vis = (N[:, 1] < -0.26) & (N[:, 2] < 0.56) & (N[:, 2] > -0.52) & (np.abs(N[:, 0]) < 0.82)
        idx[rim] = 4
        idx[vis] = 1
        if d:
            idx[vis & ((N @ L1) > 0.975)] = 2
            idx[vis & ((N @ L2) > 0.985)] = 3
        return idx
    s.sphere(c, r, SUIT, paint=paint, extra=(vp, REFL, REFL2 if not gold else REFL, GLOVE))


def eva_suit(s, cx, cy, z_boot, gold=False, d=True, wide=1.0):
    """Traje EVA pendurado de frente. cy = plano da frente do tronco. Medidas em px do sprite."""
    w = wide
    zb, zh, zt, zs = z_boot, z_boot + 7.0, z_boot + 14.6, z_boot + 17.2   # bota, quadril, peito, ombro
    # mochila de suporte de vida, atrás (aparece nos lados e por cima dos ombros)
    s.rbox((cx, cy + 5.6, zt - 1.2), (6.4 * w, 2.4, 7.6), 1.4, SUIT,
           paint=(lambda L, N: np.where(np.abs(L[:, 2] - 3.6) < 0.7, 1, 0)) if d else None, extra=(OR,))
    s.cyl(cx - 4.4 * w, cy + 5.0, 1.1, zt + 6.0, zt + 7.8, GLOVE)                     # válvulas em cima da mochila
    s.cyl(cx + 4.4 * w, cy + 5.0, 1.1, zt + 6.0, zt + 7.8, GLOVE)
    # pernas e botas
    for sx in (-1, 1):
        s.tube([(cx + sx * 2.3 * w, cy + 2.0, zh), (cx + sx * 2.5 * w, cy + 1.7, zb + 4.6), (cx + sx * 2.5 * w, cy + 1.9, zb + 2.6)],
               2.0, SUIT)
        s.rbox((cx + sx * 2.6 * w, cy + 1.0, zb + 1.4), (1.9, 2.9, 1.5), 0.8, GLOVE)
        s.box((cx + sx * 2.6 * w - 1.9, cx + sx * 2.6 * w + 1.9), (cy - 1.9, cy + 3.9), (zb - 0.6, zb), OR)              # sola
        s.box((cx + sx * 2.6 * w - 1.9, cx + sx * 2.6 * w + 1.9), (cy - 0.2, cy + 1.6), (zb + 3.0, zb + 3.8), OR)   # faixa na canela
    # tronco
    s.rbox((cx, cy + 2.4, (zh + zs) / 2 - 0.4), (4.9 * w, 2.6, (zs - zh) / 2 + 0.6), 2.0, SUIT,
           paint=(lambda L, N: np.where((N[:, 1] < -0.6) & (np.abs(L[:, 2] + 3.4) < 0.6), 1, 0)) if d else None, extra=(GLOVE,))
    # ombreiras laranja + braços + luvas
    for sx in (-1, 1):
        s.sphere((cx + sx * 5.2 * w, cy + 2.3, zs - 0.6), 2.5, OR)
        s.tube([(cx + sx * 5.6 * w, cy + 2.0, zs - 2.2), (cx + sx * 6.5 * w, cy + 1.2, zh + 3.8), (cx + sx * 6.3 * w, cy + 0.2, zh + 1.8)],
               1.65, SUIT)
        s.box((cx + sx * 6.3 * w - 1.7, cx + sx * 6.3 * w + 1.7), (cy - 1.4, cy + 1.8), (zh + 1.6, zh + 2.5), OR)  # punho
        s.rbox((cx + sx * 6.4 * w, cy - 0.2, zh + 0.3), (1.6, 1.5, 1.6), 1.0, GLOVE)                                # luva
    # caixa de controle no peito, com LEDs, e o emblema laranja da VÉSPER
    s.rbox((cx, cy - 0.4, zt - 1.6), (2.4, 0.9, 1.6), 0.5, GLOVE)
    if d:
        s.dot(cx - 1.2, cy - 1.4, zt - 1.0, "#7fe08a", always=True)
        s.dot(cx + 0.6, cy - 1.4, zt - 1.0, "#ffb04a", always=True)
        s.dot(cx - 3.0 * w, cy - 0.3, zt + 0.8, "#e2733a", always=True)
        s.dot(cx - 2.2 * w, cy - 0.3, zt + 0.8, "#e2733a", always=True)
    # mangueiras de ar (sanfonadas): da caixa do peito descem pra fora e entram na mochila na altura da cintura
    for sx in (-1, 1):
        s.tube([(cx + sx * 2.0, cy - 0.9, zt - 2.2), (cx + sx * 3.4 * w, cy - 1.2, zt - 4.6), (cx + sx * 4.9 * w, cy - 0.6, zt - 6.2),
                (cx + sx * 6.4 * w, cy + 2.2, zt - 5.2), (cx + sx * 6.6 * w, cy + 4.6, zt - 3.4)], 0.7, HOSE,
               paint=(lambda S_, TH: np.where((S_ % 1.3) < 0.5, 1, 0)) if d else None, extra=(HOSE_D,))
    # anel do pescoço e capacete
    s.cyl(cx, cy + 2.4, 3.3, zs - 0.2, zs + 1.0, GLOVE)
    helmet(s, (cx, cy + 2.0, zs + 4.4), 4.4, gold, d)


def roof_paint(L, N):
    """Teto do armário: friso laranja na borda da frente e duas fendas de ventilação no tampo."""
    idx = np.zeros(len(L), int)
    idx[(N[:, 1] < -0.7) & (np.abs(L[:, 2]) < 0.45)] = 1
    topf = N[:, 2] > 0.85
    idx[topf & (np.abs(np.abs(L[:, 1]) - 2.4) < 0.85) & (np.abs(L[:, 0]) < 5.5)] = 2
    return idx


def locker_A(s, d=True):
    """A: armário de chapa com as duas portas abertas em ângulo (como asas), o traje pendurado no cabide."""
    hx, hy, hz = 8.8, 5.6, 32.6
    s.box((-hx, hx), (hy - 1.2, hy), (0, hz), SCR)                                          # fundo (escuro)
    s.box((-hx, -hx + 1.3), (-hy, hy), (0, hz), SL)
    s.box((hx - 1.3, hx), (-hy, hy), (0, hz), SL)
    s.rbox((0, 0, hz - 1.0), (hx + 0.4, hy + 0.4, 1.2), 0.7, SL, paint=roof_paint if d else None, extra=(OR, SLD))
    s.rbox((0, 0, 0.9), (hx + 0.4, hy + 0.4, 0.9), 0.5, SLD)
    s.box((-hx + 1.6, hx - 1.6), (hy - 2.0, hy - 1.2), (hz - 3.4, hz - 2.6), DIMC)              # fita de luz lá dentro
    s.tube([(-hx + 1.3, 0.6, hz - 4.2), (hx - 1.3, 0.6, hz - 4.2)], 0.45, STEEL, caps=False)   # barra do cabide
    # portas: dobradiças nas quinas da frente; a face de dentro tem uma plaqueta laranja
    half = hx / 2
    for sx, beta in ((-1, math.radians(-128)), (1, math.radians(-48))):
        hinge = (sx * hx, -hy)
        cen = (hinge[0] + half * math.cos(beta), hinge[1] + half * math.sin(beta))
        s.obox((cen[0], cen[1], hz / 2), (half, 0.6, hz / 2 - 0.4), SL, rot_z=beta,
               paint=(lambda L, f: np.where((np.abs(L[:, 2] - 1.0) < 9.0) & (np.abs(L[:, 0]) < 2.4), 1, 0)) if d else None, extra=(SLD,))
    eva_suit(s, 0.0, -5.6, 2.4, gold=False, d=d)


def locker_B(s, d=True):
    """B: estação de traje (nicho sem porta, moldura grossa com faixa laranja/escura, painel de status ao lado)."""
    hx, hy, hz = 11.4, 5.8, 33.5
    ox = 0.0
    s.box((ox - hx, ox + hx), (hy - 1.2, hy), (0, hz), SCR)
    for x0, x1 in ((ox - hx, ox - hx + 2.0), (ox + hx - 2.0, ox + hx)):
        s.box((x0, x1), (-hy, hy), (0, hz), SL,
              paint=(lambda L, f: np.where((f == 2) & (((L[:, 2] + 40) % 4.0) < 2.0) & (L[:, 2] < -11), 1, 0)) if d else None,
              extra=(OR,))
    s.rbox((ox, 0, hz - 1.2), (hx + 0.6, hy + 0.6, 1.4), 0.8, SL, paint=roof_paint if d else None, extra=(OR, SLD))
    s.rbox((ox, 0, 1.0), (hx + 0.6, hy + 0.6, 1.0), 0.6, SLD)
    s.box((ox - hx + 2.4, ox + hx - 2.4), (hy - 2.2, hy - 1.4), (hz - 3.4, hz - 2.8), DIMC)
    # painel de status na lateral direita (frente)
    s.box((ox + hx - 1.8, ox + hx - 0.3), (-hy - 0.6, -hy), (12, 19), SCR)
    if d:
        s.dot(ox + hx - 1.0, -hy - 0.8, 17.6, "#7fe08a", always=True)
        s.dot(ox + hx - 1.0, -hy - 0.8, 15.6, "#ffb04a", always=True)
        s.dot(ox + hx - 1.0, -hy - 0.8, 13.6, "#7a2a36", always=True)
    # braço de fixação que segura a mochila
    s.box((ox - 1.2, ox + 1.2), (2.4, hy - 1.2), (19, 21), SLD)
    eva_suit(s, ox, -5.4, 2.6, gold=True, d=d, wide=1.08)


def locker_sprite(model, front_y):
    sc = CH.scene(32, 40, front_y)
    model(S6(sc), True)
    cv = sc.render()
    CH.check(cv, "locker", (32, 40))
    return R4.finish(cv, (32, 40), shw=26)


def model_icon(model, k, size=(40, 40), ground=30):
    sc = Scene(*size, ground=ground)
    model(S6(sc, k), False)
    return cut(sc.render().image().convert("RGBA"), (16, 16))


# ---------------------------------------------------------------------------------------------------------------------
# 3 · Macacão largado no chão (prop_uniforms), decal 32×32 · candidatas A e B
# ---------------------------------------------------------------------------------------------------------------------
# Pano visto de cima: cada peça (tronco, manga, perna, gola, bota...) é uma máscara com relevo (o tecido "estufa" no
# meio e cai nas bordas, mais as dobras), a luz vem de cima-esquerda e o tom sai em 4 faixas da paleta. Peça de cima
# ganha contorno por cima da de baixo; peça emendada (manga no tronco) ganha só a costura escura. Detalhe à mão no fim.
CLOTH_L = np.array([-0.55, -0.65, 0.55]) / np.linalg.norm([-0.55, -0.65, 0.55])
CW = ["#ffffff", "#e6e3ee", "#bfbace", "#8f8aa6"]            # macacão claro (A)
CO = ["#eea27a", "#d6845a", "#b8673f", "#8e4a30"]            # macacão laranja desbotado (B)
CS = ["#7a7fa0", "#555a7a", "#3f4260", "#2c2e46"]            # ardósia escura: bota, cinto, arnês
CA_ = ["#f4a06a", "#e2733a", "#c25e32", "#94401f"]            # laranja vivo: punhos, emblema, faixas
CG = ["#a8adc6", "#848aa8", "#646a8a", "#484c68"]            # luva cinza
CIN = "#2a2c42"                                              # o forro escuro (gola aberta, boca da manga)
SSUP = 4


def seg_dist(X, Y, pts):
    """Distância de cada ponto à polilinha e o parâmetro t (0..1 ao longo do comprimento total)."""
    best = np.full(X.shape, np.inf)
    tpar = np.zeros(X.shape)
    lens = [math.dist(a, b) for a, b in zip(pts[:-1], pts[1:])]
    tot, acc = max(sum(lens), 1e-9), 0.0
    for (a, b), L in zip(zip(pts[:-1], pts[1:]), lens):
        ax, ay = a
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = max(L, 1e-9)
        u = np.clip(((X - ax) * dx + (Y - ay) * dy) / max(L * L, 1e-9), 0, 1)
        d = np.hypot(X - (ax + u * dx), Y - (ay + u * dy))
        m = d < best
        best[m] = d[m]
        tpar[m] = (acc + u[m] * L) / tot
        acc += L
    return best, tpar


def poly_dist(X, Y, pts):
    """Máscara (dentro do polígono) e distância até a borda."""
    inside = np.zeros(X.shape, bool)
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        c = ((y0 > Y) != (y1 > Y)) & (X < (x1 - x0) * (Y - y0) / ((y1 - y0) + 1e-12) + x0)
        inside ^= c
    d, _ = seg_dist(X, Y, list(pts) + [pts[0]])
    return inside, d


class Cloth:
    def __init__(self, w=32, h=32, k=1.0):
        self.w, self.h, self.k = w, h, k
        self.icon = k < 1.0                                         # no ícone: só costura (sem contorno interno)
        ys, xs = np.mgrid[0:h * SSUP, 0:w * SSUP]
        self.X = (xs + 0.5) / SSUP
        self.Y = (ys + 0.5) / SSUP
        self.rgb = np.zeros((h, w, 3), np.uint8)
        self.id = np.full((h, w), -1)
        self.sep = []
        self.pals = []

    def _commit(self, mask, hgt, pal, sep):
        k = 1.0 / SSUP
        gy, gx = np.gradient(hgt, k)
        N = np.stack([-gx, -gy, np.ones_like(hgt)], -1)
        N /= np.linalg.norm(N, axis=-1, keepdims=True)
        sh = N @ CLOTH_L
        tone = np.select([sh > 0.80, sh > 0.48, sh > 0.18], [0, 1, 2], 3)
        c = SSUP // 2
        m = mask[c::SSUP, c::SSUP]
        t = tone[c::SSUP, c::SSUP]
        cols = np.array([rgb(x)[:3] for x in pal], np.uint8)
        pid = len(self.sep)
        self.rgb[m] = cols[t[m]]
        self.id[m] = pid
        self.sep.append(sep and not self.icon)
        self.pals.append(cols)
        return pid

    def limb(self, pts, r, pal, flat=0.55, wr=(0.0, 1.0, 0.0), sep=True, t_range=(0, 1)):
        """Tubo de pano (manga, perna) pela polilinha; r = raio (ou (r0, r1) afinando). wr = (amp, freq, fase) das
        dobras atravessadas (franzido)."""
        k = self.k
        pts = [(x * k, y * k) for x, y in pts]
        r0, r1 = (r, r) if not isinstance(r, tuple) else r
        d, t = seg_dist(self.X, self.Y, pts)
        rr = (r0 + (r1 - r0) * t) * k
        mask = (d <= rr) & (t >= t_range[0]) & (t <= t_range[1])
        h = flat * np.sqrt(np.clip(rr * rr - d * d, 0, None))
        amp, fr, ph = wr
        L = sum(math.dist(a, b) for a, b in zip(pts[:-1], pts[1:]))
        h = h + amp * k * np.sin(t * L * fr / k + ph) * (d < rr * 0.85)
        return self._commit(mask, np.where(mask, h, 0), pal, sep)

    def blob(self, pts, pal, puff=2.2, wr=(0.0, 0.6, 0.0, 0.0), sep=True):
        """Pano chapado (tronco, gola): polígono que estufa a partir da borda, com dobras retas (amp, freq, ângulo, fase)."""
        k = self.k
        pts = [(x * k, y * k) for x, y in pts]
        inside, d = poly_dist(self.X, self.Y, pts)
        h = puff * k * (1 - np.exp(-d / (1.6 * k)))
        amp, fr, ang, ph = wr
        u = self.X * math.cos(ang) + self.Y * math.sin(ang)
        h = h + amp * k * np.sin(u * fr / k + ph) * (d > 0.8 * k)
        return self._commit(inside, np.where(inside, h, 0), pal, sep)

    def px(self, x, y, c):
        x, y = int(round(x * self.k)), int(round(y * self.k))
        if 0 <= x < self.w and 0 <= y < self.h and self.id[y, x] >= 0:
            self.rgb[y, x] = rgb(c)[:3]

    def line(self, pts, c, only=None):
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            n = int(max(abs(x1 - x0), abs(y1 - y0)) * self.k) + 1
            for i in range(n + 1):
                x = x0 + (x1 - x0) * i / n
                y = y0 + (y1 - y0) * i / n
                xi, yi = int(round(x * self.k)), int(round(y * self.k))
                if 0 <= xi < self.w and 0 <= yi < self.h and self.id[yi, xi] >= 0 and (only is None or self.id[yi, xi] in only):
                    self.rgb[yi, xi] = rgb(c)[:3]

    def image(self):
        """Contornos internos (peça de cima sobre a de baixo) + contorno externo."""
        H, W = self.h, self.w
        out = self.rgb.copy()
        idm = self.id
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = np.full_like(idm, -1)
            ys = slice(max(dy, 0), H + min(dy, 0)); yd = slice(max(-dy, 0), H + min(-dy, 0))
            xs = slice(max(dx, 0), W + min(dx, 0)); xd = slice(max(-dx, 0), W + min(-dx, 0))
            nb[yd, xd] = idm[ys, xs]
            over = (idm >= 0) & (nb > idm)                      # o vizinho é de uma peça desenhada depois (por cima)
            for pid, sep in enumerate(self.sep):
                m = over & (nb == pid)
                if sep:
                    out[m] = rgb(OUT)[:3]
                else:                                           # costura: o tom mais escuro da peça de baixo
                    for q in np.unique(idm[m]):
                        mm = m & (idm == q)
                        out[mm] = self.pals[q][3]
        im = np.zeros((H, W, 4), np.uint8)
        im[..., :3] = out
        im[..., 3] = np.where(idm >= 0, 255, 0)
        f = V.Img(W, H)
        f.im = Image.fromarray(im).copy()
        R4.outline_img(f)
        return f.im


def boot(c, shaft, foot, sole_side=1, r=(1.9, 1.6)):
    """Bota deitada de lado (perfil em L): cano + pé, sola laranja na borda de baixo do pé."""
    c.limb(shaft, r[0], CS, flat=0.8, sep=True)
    c.limb(foot, r[1], CS, flat=0.8, sep=False)
    (x0, y0), (x1, y1) = foot
    c.line([(x0, y0 + sole_side * r[1]), (x1 + 0.4, y1 + sole_side * r[1])], "#c25e32")


def limb_cuff(c, pts, r, pal, cuff, t0=0.82, **kw):
    """Manga/perna com a barra (punho) na ponta: a mesma polilinha, a barra é o trecho final."""
    c.limb(pts, r, pal, **kw)
    rr = r if not isinstance(r, tuple) else r[1]
    return c.limb(pts, rr + 0.15, cuff, flat=0.45, sep=False, t_range=(t0, 1.0))


def emblem(c, x, y, ring, core, hi):
    for dx in range(3):
        for dy in range(3):
            c.px(x + dx, y + dy, ring)
    c.px(x + 1, y + 1, core)
    c.px(x + 1, y, core)
    c.px(x, y + 1, hi)


def uniforms_A(k=1.0, d=True):
    """A: macacão claro de tripulante, aberto e largado: uma manga esticada, a outra caída do lado, uma perna dobrada
    no joelho; o par de botas tirado do lado."""
    c = Cloth(int(32 * k), int(32 * k), k)
    if d:
        boot(c, [(24.0, 21.4), (24.4, 26.8)], [(24.4, 27.6), (28.6, 27.8)])
        boot(c, [(28.6, 18.8), (28.9, 23.8)], [(28.9, 24.2), (28.0, 24.4)], r=(1.7, 1.4))
    # pernas (a direita dobrada no joelho)
    limb_cuff(c, [(12.0, 17.5), (11.0, 23.5), (10.2, 28.8)], (3.0, 2.6), CW, CA_, t0=0.86, wr=(0.45, 1.3, 0.5), sep=True)
    limb_cuff(c, [(16.6, 17.0), (20.4, 20.6), (19.4, 25.8)], (3.0, 2.5), CW, CA_, t0=0.86, wr=(0.45, 1.3, 1.6), sep=True)
    # manga esticada (atrás do tronco), tronco, manga caída (por cima)
    limb_cuff(c, [(18.4, 7.4), (24.2, 6.0), (28.8, 7.8)], (2.6, 2.2), CW, CA_, t0=0.88, wr=(0.5, 1.4, 0.0), sep=False)
    torso = c.blob([(8.2, 6.0), (18.8, 5.6), (19.4, 17.8), (9.0, 18.4)], CW, puff=1.8, wr=(0.4, 1.2, 0.5, 0.3), sep=True)
    limb_cuff(c, [(8.4, 7.2), (4.6, 10.6), (3.6, 16.6)], (2.6, 2.3), CW, CA_, t0=0.84, wr=(0.5, 1.4, 1.0), sep=True)
    # gola aberta: o forro escuro no decote e as duas abas
    c.blob([(11.8, 4.6), (15.6, 4.4), (14.6, 9.6), (13.0, 9.8)], [CIN] * 4, puff=0.3, sep=False)
    c.blob([(9.0, 4.4), (12.4, 3.6), (13.6, 8.8), (11.8, 8.6)], CW, puff=1.0, sep=True)
    c.blob([(15.2, 3.4), (18.6, 4.6), (16.0, 8.6), (14.2, 8.8)], CW, puff=1.0, sep=True)
    # cinto + fivela
    c.blob([(8.8, 15.8), (19.3, 15.4), (19.4, 17.6), (9.0, 18.0)], CS, puff=0.6, sep=False)
    if d:
        c.line([(14.0, 9.8), (14.2, 15.2)], "#8f8aa6", only={torso})                          # zíper
        c.px(14.2, 12.6, "#7a7fa0")                                                          # puxador
        c.px(13.6, 16.5, "#f2c46d"); c.px(14.6, 16.5, "#f2c46d")                            # fivela
        emblem(c, 9.8, 9.0, "#e2733a", "#f4a06a", "#ffffff")                                  # emblema da VÉSPER
        c.px(16.4, 10.0, "#8f8aa6"); c.px(17.4, 10.0, "#8f8aa6")                            # plaqueta de nome
    return c.image()


def glove(c, a, b, thumb):
    """Luva: o punho laranja, a mão gorda (luva de traje) e o polegar curto de lado."""
    c.limb([a, b], (1.7, 2.1), CG, flat=0.8, sep=True)
    c.limb([a, a], 1.6, CA_, flat=0.5, sep=False)
    c.limb([thumb, thumb], 1.0, CG, flat=0.8, sep=True)


def uniforms_B(k=1.0, d=True):
    """B: macacão laranja desbotado com arnês ardósia, esparramado: uma manga dobrada pra cima, a outra caída pro lado,
    pernas abertas com as botas ainda calçadas; o par de luvas largado do lado."""
    c = Cloth(int(32 * k), int(32 * k), k)
    if d:
        glove(c, (25.2, 22.6), (28.4, 24.6), (26.6, 26.6))
    # pernas com bota calçada na ponta
    for pts in ([(12.4, 17.6), (10.0, 23.4), (7.4, 27.4)], [(17.2, 17.4), (19.0, 22.6), (21.0, 27.0)]):
        c.limb(pts, (3.0, 2.6), CO, wr=(0.35, 1.2, 0.4), sep=True)
        c.limb(pts, 2.85, CS, flat=0.8, sep=False, t_range=(0.84, 1.0))
    c.line([(5.2, 29.4), (7.6, 30.2)], "#c25e32"); c.line([(20.0, 29.8), (22.4, 29.2)], "#c25e32")   # sola
    # mangas atrás do tronco: uma dobrada pra cima no cotovelo, a outra caída pro lado
    limb_cuff(c, [(10.2, 7.8), (5.0, 10.2), (3.0, 5.0)], (2.6, 2.2), CO, CS, t0=0.86, wr=(0.35, 1.3, 0.4), sep=False)
    limb_cuff(c, [(19.2, 7.6), (23.2, 11.4), (24.6, 16.6)], (2.6, 2.2), CO, CS, t0=0.86, wr=(0.35, 1.3, 1.0), sep=False)
    torso = c.blob([(9.4, 6.4), (19.8, 6.0), (20.2, 17.8), (10.0, 18.2)], CO, puff=1.8, wr=(0.3, 1.1, 0.9, 0.0), sep=True)
    c.blob([(9.8, 15.6), (20.1, 15.2), (20.2, 17.6), (10.0, 18.0)], CS, puff=0.6, sep=False)            # cinto
    # gola clara
    c.blob([(12.8, 5.0), (16.6, 4.8), (15.6, 10.0), (14.0, 10.2)], [CIN] * 4, puff=0.3, sep=False)
    c.blob([(10.2, 4.8), (13.6, 4.0), (14.6, 9.4), (12.8, 9.2)], CW, puff=1.0, sep=True)
    c.blob([(16.2, 3.8), (19.6, 5.0), (17.0, 9.2), (15.2, 9.4)], CW, puff=1.0, sep=True)
    if d:
        c.line([(11.6, 9.2), (12.2, 15.4)], "#3f4260", only={torso})                         # alças do arnês
        c.line([(18.4, 8.8), (18.6, 15.2)], "#3f4260", only={torso})
        c.line([(15.0, 10.4), (15.2, 15.2)], "#86452e", only={torso})                        # zíper
        c.px(15.1, 12.8, "#d4d8e8")
        c.px(14.6, 16.4, "#d4d8e8"); c.px(15.6, 16.4, "#d4d8e8")                            # fivela
        emblem(c, 12.8, 10.6, "#e6e3ee", "#e2733a", "#ffffff")                                # emblema: aro claro
    return c.image()


# ---------------------------------------------------------------------------------------------------------------------
# Montagem do alojamento (clara e escura), com a casca aprovada; mesma ordem de desenho do jogo
# ---------------------------------------------------------------------------------------------------------------------
def room(sp, faces, floor_props, decals, lantern, glows, name):
    W, H, LIFT = 9, 8, 24
    ROOM = ["#########"] + ["#.......#"] * 6 + ["#########"]
    cv = Image.new("RGBA", (W * T, H * T + LIFT), (0, 0, 0, 255))
    wall = lambda x, y: 0 <= x < W and 0 <= y < H and ROOM[y][x] == "#"
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                cv.alpha_composite(sp["floor"][R4.R3_VAR[(x * 5 + y * 11) % len(R4.R3_VAR)]], (x * T, y * T + LIFT))
    for (img, tx, ty) in decals:                                    # decal: junto com o chão
        cv.alpha_composite(img, (tx * T, ty * T + LIFT))
    for y in range(H):
        for x in range(W):
            if not wall(x, y):
                continue
            cv.alpha_composite(V.autotile_compose(sp["top"], wall, x, y), (x * T, y * T))
            if not wall(x, y + 1):
                idx = int(wall(x - 1, y)) + 2 * int(wall(x + 1, y))
                cv.alpha_composite(sp["face"].crop((idx * T, 0, idx * T + T, 24)), (x * T, y * T + 8 + LIFT))
                if (x, y) in faces:
                    cv.alpha_composite(faces[(x, y)], (x * T, y * T + 8 + LIFT))
    for (img, tx, ty) in sorted(floor_props, key=lambda p: p[2]):   # chão e mesa: (tx·32, ty·32 − 8), pelo pé
        cv.alpha_composite(img, (tx * T, ty * T - 8 + LIFT))
    cv.save(REP / f"sala_r6_{name}_clara.png")
    R2.dark_scene(cv, lantern, glows).save(REP / f"sala_r6_{name}_escura.png")


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}

    def save(im, name, size):
        assert im.size == size, (name, im.size)
        alpha_ok(im, name)
        im.save(PEND / f"{name}.png")
        out[name] = im

    save(bunk_sprite(), "prop_wall_bunk_r6", (64, 40))
    save(bunk_icon(), "icon_prop_wall_bunk_r6", (16, 16))
    for v, fn in (("A", uniforms_A), ("B", uniforms_B)):
        save(fn(), f"prop_uniforms_r6_{v}", (32, 32))
        save(fn(0.5, False), f"icon_prop_uniforms_r6_{v}", (16, 16))
    for v, fn, fy in (("A", locker_A, -11.5), ("B", locker_B, -9)):
        save(locker_sprite(fn, fy), f"prop_suit_locker_r6_{v}", (32, 40))
        save(model_icon(fn, 0.36), f"icon_prop_suit_locker_r6_{v}", (16, 16))
    sp = dict(top=Image.open(PEND / "hull_wall_top.png").convert("RGBA"), face=Image.open(PEND / "hull_wall_face.png").convert("RGBA"),
              floor=[Image.open(PEND / f"hull_floor_{i}.png").convert("RGBA") for i in range(4)])
    light = Image.open(PEND / "vesper_emergency_light_A.png").convert("RGBA")
    o2 = Image.open(PEND / "prop_o2_cylinders_r5.png").convert("RGBA")
    stack = Image.open(PEND / "prop_container_stack.png").convert("RGBA")
    for v in "AB":
        room(sp, {(3, 0): light},
             [(out["prop_wall_bunk_r6"], 1, 1), (out["prop_wall_bunk_r6"], 4, 1), (out[f"prop_suit_locker_r6_{v}"], 7, 1),
              (o2, 7, 3), (stack, 1, 5)],
             [(out[f"prop_uniforms_r6_{v}"], 3, 3), (out[f"prop_uniforms_r6_{v}"], 5, 4)],
             (4 * T + 16, 3 * T + 40), [(3 * T + 16, 24 + 22, 30, (.7, .08, .08))], f"alojamento_{v}")
    return out


if __name__ == "__main__":
    build()
    print("ok")
