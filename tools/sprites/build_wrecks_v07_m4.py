#!/usr/bin/env python3
"""v0.7 M4 · os 5 destroços MAIORES (pedido do dono: "eu sou quase do tamanho da nave").

    python3 tools/sprites/build_wrecks_v07_m4.py
    ->  reports/design/v07_m4_destrocos/pendentes/wreck_{cargo,module,probe,robot,liner}.png   (CANDIDATAS)

Mesmo design aprovado de cada um (v0.7 M3: VÉSPER-7 r5 A ardósia em iso, base de vidro r5 em iso, sonda r1, robô r2,
ARCA-2 r1), redesenhado numa escala maior e enriquecido. Como: cada desenho aprovado roda de novo por cima de um
"canvas com escala" (SCv), que multiplica as coordenadas por k e desenha NA RESOLUÇÃO NOVA (polígono, elipse, linha de
1 px e contorno ficam finos e nítidos; não é ampliação de bitmap). Por cima disso entram os detalhes nativos novos
(rebites, emendas, luzes, porão mais fundo, sucata, bagagem...).

Não mexe no build_sprites.py nem em assets/. Só PIL + numpy, determinístico (hash fixo, sem random).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_destrocos import CAV, CREAM, GLASS, LAV, METAL, OR, OR_D, OR_L, RUST, SOLAR, arc, quad  # noqa: E402
from v07_lib import Cv, OUT, SHADOW, hsh, sand_pile, scatter  # noqa: E402
from v07_r2_destrocos import BGR, FONT, GL, INT, pane, track2  # noqa: E402
from v07_r3_base import shade_region  # noqa: E402
from v07_r3_cargo import plate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REP = ROOT / "reports" / "design" / "v07_m4_destrocos"
PEND = REP / "pendentes"
T = 32


# =====================================================================================================================
# Canvas com escala: as coordenadas do desenho aprovado (unidades "velhas") viram pixels novos = ox + u·k
# =====================================================================================================================
class _SDraw:
    def __init__(self, s, d):
        self.s, self.d = s, d

    def _box(self, b):
        x0, y0, x1, y1 = b
        return [round(self.s.X(x0)), round(self.s.Y(y0)), round(self.s.X(x1 + 1)) - 1, round(self.s.Y(y1 + 1)) - 1]

    def rectangle(self, b, fill=None):
        self.d.rectangle(self._box(b), fill=fill)

    def rounded_rectangle(self, b, radius=0, fill=None):
        self.d.rounded_rectangle(self._box(b), radius=round(radius * self.s.k), fill=fill)

    def polygon(self, pts, fill=None):
        self.d.polygon([self.s.pt(p) for p in pts], fill=fill)


class SCv:
    """Mesma interface do Cv (v07_lib), em unidades velhas. `n` é o Cv nativo (pra detalhe novo, em px novos)."""

    def __init__(self, w, h, k, ox=0.0, oy=0.0):
        self.n = Cv(w, h)
        self.k, self.ox, self.oy = k, ox, oy
        self.w, self.h = w, h

    # conversões
    def X(self, x):
        return self.ox + x * self.k

    def Y(self, y):
        return self.oy + y * self.k

    def pt(self, p):
        return (int(round(self.X(p[0]))), int(round(self.Y(p[1]))))

    def N(self, x, y):
        """Ponto velho -> px novo (int)."""
        return self.pt((x, y))

    @property
    def im(self):
        return self.n.im

    @property
    def d(self):
        return self.n.d

    # primitivas
    def px(self, x, y, c):
        s = max(1, round(self.k))
        self.n.rect(round(self.X(x)), round(self.Y(y)), s, s, c)

    def rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            x0, y0 = round(self.X(x)), round(self.Y(y))
            x1, y1 = round(self.X(x + w)), round(self.Y(y + h))
            self.n.rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0), c)

    def poly(self, pts, c):
        self.n.poly([self.pt(p) for p in pts], c)

    def ell(self, cx, cy, rx, ry, c):
        self.n.ell(self.X(cx), self.Y(cy), rx * self.k, ry * self.k, c)

    def line(self, pts, c, w=1):
        self.n.line([self.pt(p) for p in pts], c, 1 if w == 1 else max(1, round(w * self.k)))

    def mask(self, fn):
        m = Image.new("L", (self.w, self.h), 0)
        fn(_SDraw(self, ImageDraw.Draw(m)))
        return np.array(m) > 0

    def pmask(self, pts):
        return self.n.pmask([self.pt(p) for p in pts])

    def emask(self, cx, cy, rx, ry):
        return self.n.emask(self.X(cx), self.Y(cy), rx * self.k, ry * self.k)

    def paint(self, m, fn):
        k, ox, oy = self.k, self.ox, self.oy
        self.n.paint(m, lambda x, y: fn((x + .5 - ox) / k - .5, (y + .5 - oy) / k - .5))

    def fill(self, m, c):
        self.n.fill(m, c)

    def banded(self, m, cols, y0=None, y1=None, cuts=None):
        self.n.banded(m, cols, None if y0 is None else self.Y(y0), None if y1 is None else self.Y(y1), cuts)

    def speckle(self, m, col, p, seed=1, scale=1.0):
        self.n.speckle(m, col, p, seed, scale / self.k)

    def shadow_ell(self, cx, cy, rx, ry):
        self.ell(cx, cy, rx, ry, SHADOW)

    def outline(self, col=OUT):
        self.n.outline(col)

    def check(self):
        self.n.check()

    def image(self):
        return self.n.im


# ---- detalhes nativos (px novos) ------------------------------------------------------------------------------------
def rivets(n, pts, col, step=6, seed=0):
    """Fileira de rebites ao longo do segmento (px novos)."""
    (x0, y0), (x1, y1) = pts
    L = max(1, int(math.hypot(x1 - x0, y1 - y0) // step))
    for i in range(L + 1):
        t = i / L
        n.px(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), col)


def stripes(n, mask, a, b, w=3):
    """Faixa de perigo (diagonais alternadas a/b) dentro da máscara."""
    n.paint(mask, lambda x, y: a if ((x + y) // w) % 2 == 0 else b)


def scrap(n, x, y, w, h, light, dark, seed=0):
    """Chapa solta no chão (px novos): retângulo torto com face clara e borda escura."""
    sk = int(hsh(x, y, seed) * 3) - 1
    pts = [(x, y + max(0, sk)), (x + w, y + max(0, -sk)), (x + w, y + h), (x, y + h)]
    n.poly(pts, dark)
    n.poly([(x, y + max(0, sk)), (x + w, y + max(0, -sk)), (x + w, y + max(0, -sk) + 1), (x, y + max(0, sk) + 1)], light)


def flat_plate(cv, P, u, v, du, dv, tones, border, h=1.0, seed=0, tilt=0.0):
    """Chapa caída deitada no chão do iso (com espessura nas bordas da frente). tilt levanta o canto do fundo."""
    top = [P(u, v, h + tilt), P(u + du, v, h), P(u + du, v + dv, h), P(u, v + dv, h + tilt * .5)]
    cv.poly([P(u + du, v, 0), P(u + du, v + dv, 0), P(u, v + dv, 0), top[3], top[2], top[1]], tones[2])
    m = cv.pmask(top)
    cv.banded(m, list(tones), cuts=[.35, .7])
    cv.speckle(m, tones[2], .1, seed)
    cv.line([top[0], top[1]], tones[0] if len(tones) < 4 else tones[3])
    return m


def scatter_n(n, spots, seed=0):
    for i, (x, y) in enumerate(spots):
        kk = hsh(x, y, seed + i)
        if kk < .3:
            n.rect(x, y, 5, 3, "#4a4f57"); n.rect(x, y, 5, 1, "#6b717a")
        elif kk < .6:
            n.rect(x, y, 6, 3, "#3b3f46"); n.rect(x, y, 3, 1, "#5a6069")
        elif kk < .8:
            n.rect(x, y, 3, 2, "#796b61"); n.px(x, y, "#a39385")
        else:
            n.rect(x, y, 4, 2, "#625650"); n.rect(x + 1, y, 2, 1, "#8e7f73")


# =====================================================================================================================
# 1 · VÉSPER-7 (cargo) · r5 A ardósia em iso · k = 2 · 320×224 · pegada 10×5 · lift 64
# =====================================================================================================================
SL = [("#b4bcd6", "#8f98b8", "#6f7898"), ("#8f98b8", "#6f7898", "#575f7d"), ("#6f7898", "#575f7d", "#444b66"), ("#575f7d", "#444b66", "#363c54")]
BL, BL2, BL3 = "#59d0e6", "#c8f6ff", "#2b9fb8"
GOLD = "#f2c46d"


class Iso:
    def __init__(self, cv, x0, y0):
        self.cv, self.x0, self.y0 = cv, x0, y0

    def P(self, u, v, z=0):
        return (self.x0 + u - v, self.y0 + (u + v) / 2 - z)

    def box(self, u0, u1, v0, v1, z0, z1, tones, border, hi, top_tone=None, seed=0, wear=.08):
        P, cv = self.P, self.cv
        tl = top_tone or tones[0]
        plate(cv, [P(u1, v0, z0), P(u1, v1, z0), P(u1, v1, z1), P(u1, v0, z1)], tones[2], border, None, wear=wear, seed=seed + 2)
        plate(cv, [P(u0, v1, z0), P(u1, v1, z0), P(u1, v1, z1), P(u0, v1, z1)], tones[1], border, hi, wear=wear, seed=seed + 1)
        plate(cv, [P(u0, v0, z1), P(u1, v0, z1), P(u1, v1, z1), P(u0, v1, z1)], tl, border, hi, cuts=(.3, .7), wear=wear, seed=seed)


def ptext(iso, u, z, v, s, col, sz=1.0):
    """Texto 3×5 no costado (v fixo), cisalhado pelo iso; sz = tamanho do "pixel" da fonte em unidades velhas."""
    for i, ch in enumerate(s):
        for j, row in enumerate(FONT[ch]):
            for kk, b in enumerate(row):
                if b == "1":
                    x, y = iso.P(u + (i * 4 + kk) * sz, v, z - j * sz)
                    iso.cv.rect(x, y, sz, sz, col)


CARGO = dict(size=(10, 5), sprite=(320, 224), lift=64, crate=(2, 5), mouth=(8, 4), approach=(8, 5))


def cargo(r2=False):
    """r2 (rodada 2): os caixotes caídos que encostavam na borda do canvas (o azul embaixo da rampa e o da esquerda) vêm pra dentro."""
    W, H = CARGO["sprite"]
    k = 2.0
    cv = SCv(W, H, k, ox=0, oy=-31)
    n = cv.n
    pal = SL
    BD, HI, ink = "#1d1d32", "#c8d0ea", "#e8ecfa"
    Lu, Wv, Hh = 80, 42, 28
    RL = 34                                                   # rampa mais comprida (o pé chega na borda de baixo)
    iso = Iso(cv, 50, 46)
    P = iso.P
    cv.shadow_ell(86, 104, 70, 17)
    sand_pile(cv, 40, 100, 24, 6, 1); sand_pile(cv, 112, 110, 22, 4, 2); sand_pile(cv, 22, 96, 12, 4, 5)

    def leg(u, v, broken=False):
        a = P(u, v, 6)
        b = P(u - 4, v + 8, 0)
        if broken:
            cv.line([a, (a[0] - 1, a[1] + 4)], pal[3][1], 3)
            return
        cv.line([a, b], pal[3][2], 3); cv.line([(a[0] - 1, a[1]), (b[0] - 1, b[1])], pal[2][0])
        cv.rect(b[0] - 5, b[1] - 1, 11, 3, pal[3][2]); cv.rect(b[0] - 5, b[1] - 1, 11, 1, pal[1][0])
        # pistão do trem (detalhe novo)
        pa, pb = cv.pt(a), cv.pt(b)
        n.line([(pa[0] + 2, pa[1] + 2), ((pa[0] + pb[0]) // 2 + 2, (pa[1] + pb[1]) // 2)], pal[0][0])
    leg(12, 0); leg(66, 0)

    # ---- casco
    iso.box(0, Lu, 0, Wv, 4, Hh, pal[:3], BD, HI, seed=1)
    iso.box(4, Lu - 2, 2, Wv - 1, 0, 6, pal[1:4], BD, HI, seed=9)
    L = lambda u, z: P(u, Wv, z)
    # costado: painéis em camadas
    plate(cv, [L(8, 6), L(32, 6), L(32, 24), L(8, 24)], (OR_L, OR, OR_D), BD, "#ffd9b8", cuts=(.2, .6), wear=.08, seed=20)
    for (u0, u1) in ((10, 19), (21, 30)):
        plate(cv, [L(u0, 10), L(u1, 10), L(u1, 20), L(u0, 20)], ("#ffb27a", OR, OR_D), BD, "#ffd9b8", wear=0, seed=21)
        cv.line([L(u0 + 2, 15), L(u0 + 5, 18), L(u0 + 7, 15)], BD)
    plate(cv, [L(34, 6), L(56, 6), L(56, 24), L(34, 24)], pal[0], BD, HI, wear=.1, seed=22)
    plate(cv, [L(58, 6), L(76, 6), L(76, 24), L(58, 24)], pal[2], BD, HI, wear=.1, seed=23)
    for kk in range(4):
        cv.line([L(60, 19 - kk * 3), L(74, 19 - kk * 3)], pal[3][2])
    cv.line([L(34, 12), L(56, 12)], OR); cv.line([L(34, 11), L(56, 11)], OR_D)
    ptext(iso, 36, 21, Wv, "VESPER-7", ink, sz=1)
    # NOVO: vigias acesas ao longo do costado (fileira de janelinhas ciano com moldura)
    for u in (37, 41.5, 46, 50.5):
        a = cv.pt(L(u, 8))
        n.rect(a[0] - 1, a[1] - 2, 5, 4, BD); n.rect(a[0], a[1] - 1, 3, 2, BL); n.px(a[0], a[1] - 1, BL2)
    # NOVO: rebites nas emendas das placas e na saia
    for (u0, u1, z) in ((34, 56, 23), (58, 76, 23), (8, 32, 7), (34, 56, 7), (58, 76, 7)):
        rivets(n, [cv.pt(L(u0 + 1, z)), cv.pt(L(u1 - 1, z))], pal[3][2], 7)
    for (u0, u1) in ((6, 30), (32, 54), (56, 76)):
        rivets(n, [cv.pt(P(u0, Wv - 1, 3)), cv.pt(P(u1, Wv - 1, 3))], pal[0][0], 8)
    # NOVO: amassado com chapa rasgada e costelas no costado (perto da proa)
    dent = [L(60, 6), L(66, 5), L(70, 9), L(66, 13), L(61, 12)]
    md = cv.pmask(dent)
    cv.fill(md, CAV[1]); n.paint(md, lambda x, y: RUST[2] if (x // 3) % 2 == 0 else None)
    for (a, b) in ((dent[0], dent[1]), (dent[1], dent[2])):
        cv.line([a, b], pal[0][0])
    # NOVO: escorrido de ferrugem saindo da ventilação
    for (u, ln) in ((62, 5), (67, 7), (71, 4)):
        a = cv.pt(L(u, 8))
        n.line([(a[0], a[1]), (a[0], a[1] + ln)], RUST[1]); n.px(a[0], a[1] + ln, RUST[2])

    # ---- convés
    iso.box(8, 34, 6, 34, Hh, Hh + 4, pal[:3], BD, HI, seed=30)
    iso.box(40, 68, 10, 32, Hh, Hh + 3, pal[1:4], BD, HI, seed=31)
    iso.box(14, 26, 12, 26, Hh + 4, Hh + 7, pal[:3], BD, HI, seed=32)
    for kk in range(4):
        x, y = P(46 + kk * 5, 14, Hh + 3); cv.rect(x, y, 3, 1, pal[3][2])
    cv.poly([P(52, 20, Hh + 3), P(62, 20, Hh + 3), P(62, 28, Hh + 3), P(52, 28, Hh + 3)], OR); cv.line([P(52, 20, Hh + 3), P(62, 20, Hh + 3)], OR_L)
    # NOVO: escotilha redonda no convés da frente, com volante
    hx, hy = cv.pt(P(20, 19, Hh + 7))
    n.fill(n.emask(hx, hy, 7, 3.6), BD); n.fill(n.emask(hx, hy, 6, 2.8), pal[2][1]); n.fill(n.emask(hx, hy - .5, 4, 1.8), pal[1][0])
    n.line([(hx - 3, hy), (hx + 3, hy)], BD); n.line([(hx, hy - 2), (hx, hy + 1)], BD)
    # NOVO: módulo de sensores (cúpula) e caixa de rádio no convés de trás
    sx, sy = cv.pt(P(30, 22, Hh + 4))
    n.fill(n.emask(sx, sy - 2, 5, 4), BD); n.fill(n.emask(sx, sy - 2, 4, 3), pal[0][0]); n.rect(sx - 2, sy - 4, 2, 1, "#ffffff")
    iso.box(42, 48, 26, 31, Hh + 3, Hh + 6, pal[1:4], BD, HI, seed=33)
    # NOVO: listras de perigo na borda do convés elevado
    for u in range(41, 67, 4):
        a = cv.pt(P(u, 32, Hh + 1.5)); n.rect(a[0], a[1], 3, 2, GOLD if (u // 4) % 2 else BD)
    # antena (+ antena curta nova)
    ax, ay = P(70, 8, Hh + 3)
    cv.rect(ax, ay - 20, 1, 20, METAL[2]); cv.rect(ax - 2, ay - 22, 5, .5, METAL[2]); cv.rect(ax - 1, ay - 25, 3, 3, "#ff5a4a"); cv.px(ax - 1, ay - 25, "#ffb0a0")
    bx, by = cv.pt(P(60, 10, Hh + 3))
    n.rect(bx, by - 14, 2, 14, METAL[3]); n.rect(bx - 3, by - 10, 8, 1, METAL[2]); n.rect(bx - 2, by - 6, 6, 1, METAL[2])

    # ---- popa: porão aberto (maior e iluminado: tem que chamar o player)
    S = lambda v, z: P(Lu, v, z)
    plate(cv, [S(6, 3), S(36, 3), S(36, 25), S(6, 25)], (CAV[0], CAV[1], CAV[2]), BD, None, cuts=(.3, .7), wear=0, seed=40)
    inner = cv.pmask([S(7, 4), S(35, 4), S(35, 24), S(7, 24)])
    # o interior é desenhado numa camada à parte e recortado pela boca (nada vaza pro casco)
    lay = SCv(W, H, k, cv.ox, cv.oy)
    ln = lay.n
    li = Iso(lay, 50, 46)
    Q = li.P
    DP = 16                                                                   # profundidade do porão
    lay.fill(inner, "#121a30")
    # parede de dentro (lado direito, plano v = 7): chapas com costelas e fita de LED
    rw = lay.pmask([Q(Lu - DP, 7, 4), Q(Lu, 7, 4), Q(Lu, 7, 24), Q(Lu - DP, 7, 24)])
    lay.banded(rw, ["#1e2a48", "#2a3a5e", "#34507a"], cuts=[.3, .65])
    for u in range(Lu - DP + 3, Lu, 4):
        lay.line([Q(u, 7, 4), Q(u, 7, 24)], "#16203a")
    lay.line([Q(Lu - DP, 7, 19), Q(Lu, 7, 19)], BL3); lay.line([Q(Lu - DP, 7, 18.5), Q(Lu, 7, 18.5)], BL)
    for u in range(Lu - DP + 1, Lu, 3):
        x, y = lay.pt(Q(u, 7, 10)); ln.rect(x, y, 2, 3, "#3f5f8c")
    # fundo (plano u = Lu − DP) com a porta acesa (o corredor que leva pro interior: o "entra aqui")
    bw = lay.pmask([Q(Lu - DP, 7, 4), Q(Lu - DP, 35, 4), Q(Lu - DP, 35, 24), Q(Lu - DP, 7, 24)])
    lay.banded(bw, ["#18223c", "#22304e", "#2c3e62"], cuts=[.35, .7])
    for z in (9, 14, 19):
        lay.line([Q(Lu - DP, 7, z), Q(Lu - DP, 35, z)], "#30466c")
    # a porta acesa fica na parede de dentro que aparece (v = 7): é o corredor que leva pro interior
    D0, D1 = Lu - 13, Lu - 6
    dw = lay.pmask([Q(D0, 7, 4.5), Q(D1, 7, 4.5), Q(D1, 7, 18), Q(D0, 7, 18)])
    lay.fill(dw, "#8fb4dc"); ln.paint(dw, lambda x, y: "#c8f6ff" if (x + 2 * y) % 9 == 0 else None)
    sil = lay.pmask([Q(D0 + 2, 7, 4.5), Q(D1 - 1, 7, 4.5), Q(D1 - 1, 7, 9), Q(D0 + 2, 7, 9)])
    lay.fill(sil, "#b9d4ee")                                                  # luz no chão do corredor
    lay.line([Q(D0 - .5, 7, 4.5), Q(D0 - .5, 7, 18.5), Q(D1 + .5, 7, 18.5), Q(D1 + .5, 7, 4.5)], BD)
    lay.line([Q(D0 - 1.5, 7, 4.5), Q(D0 - 1.5, 7, 19.5), Q(D1 + 1.5, 7, 19.5), Q(D1 + 1.5, 7, 4.5)], GOLD)
    x, y = lay.pt(Q(D1 + 3, 7, 12)); ln.rect(x, y, 2, 2, "#7fd67a")                         # botão da porta
    # piso: chapas claras, a luz da porta escorrendo até a boca
    flo = lay.pmask([Q(Lu, 7, 4), Q(Lu, 35, 4), Q(Lu - DP, 35, 4), Q(Lu - DP, 7, 4)])
    lay.banded(flo, ["#3a5a86", "#4a6e9a", "#5b82ae"], cuts=[.4, .75])
    for kk in range(1, DP // 3 + 1):
        lay.line([Q(Lu - kk * 3, 7, 4), Q(Lu - kk * 3, 35, 4)], "#2a4066")
    glow = lay.pmask([Q(D0, 7, 4), Q(D1, 7, 4), Q(Lu, 16, 4), Q(Lu - 4, 18, 4)]) & flo
    ln.paint(glow, lambda x, y: "#9fc0e6" if (x + y) % 2 else "#7fa6d2")
    # teto: fileira de luzes
    for u in range(Lu - DP + 2, Lu, 4):
        x, y = lay.pt(Q(u, 12, 24)); ln.rect(x, y, 3, 1, BL2)
    # carga (à esquerda; o caminho até a porta fica livre)
    li.box(Lu - 13, Lu - 4, 26, 35, 4, 17, (("#4b5273",) * 3, ("#4b5273",) * 3, ("#363c54",) * 3), BD, "#9fa8c8",
           top_tone=("#7f89ad", "#7f89ad", "#4b5273"), seed=92, wear=0)
    for z in (8, 12):
        lay.line([Q(Lu - 4, 26, z), Q(Lu - 4, 35, z)], "#262a42")
    li.box(Lu - 12, Lu - 5, 19, 25, 4, 12, (("#9a5a3a",) * 3, ("#9a5a3a",) * 3, ("#6c4030",) * 3), BD, "#d9a066",
           top_tone=("#c98a56", "#c98a56", "#9a5a3a"), seed=90, wear=0)
    li.box(Lu - 11, Lu - 7, 20, 24, 12, 16, (("#9a5a3a",) * 3, ("#9a5a3a",) * 3, ("#6c4030",) * 3), BD, "#d9a066",
           top_tone=("#c98a56", "#c98a56", "#9a5a3a"), seed=91, wear=0)
    a_, b_ = lay.pt(Q(Lu - 5, 19, 9)), lay.pt(Q(Lu - 5, 25, 9)); ln.line([a_, b_], GOLD)
    li.box(Lu - 4, Lu - 1, 18, 22, 4, 7, (("#9a5a3a",) * 3, ("#9a5a3a",) * 3, ("#6c4030",) * 3), BD, "#d9a066",
           top_tone=("#c98a56", "#c98a56", "#9a5a3a"), seed=93, wear=0)        # caixote tombado na boca
    c0 = lay.pt(Q(Lu - 4, 14, 24)); ln.line([c0, (c0[0] + 1, c0[1] + 9), (c0[0] - 1, c0[1] + 14)], "#17131e"); ln.px(c0[0] - 1, c0[1] + 15, GOLD)
    la = np.array(ln.im); keep = inner & (la[:, :, 3] > 0)
    base = np.array(n.im); base[keep] = la[keep]
    n.im = Image.fromarray(base); n.d = ImageDraw.Draw(n.im)
    cv.line([S(8, 23.5), S(34, 23.5)], BL3)                                       # luz azul na verga
    # moldura com hazard + lâmpada de aviso
    for (a, b) in ((S(6, 25), S(36, 25)), (S(6, 3), S(6, 25)), (S(36, 3), S(36, 25))):
        cv.line([a, b], OR_D)
    hz = cv.pmask([S(5, 25), S(37, 25), S(37, 28), S(5, 28)])
    stripes(n, hz, GOLD, BD, 3)
    for v in (5, 37):
        q = cv.pmask([S(v - 1, 3), S(v + 1, 3), S(v + 1, 25), S(v - 1, 25)]); stripes(n, q, GOLD, BD, 3)
    lx, ly = cv.pt(S(21, 30)); n.rect(lx - 2, ly - 2, 5, 4, BD); n.rect(lx - 1, ly - 1, 3, 2, "#ffcf5a"); n.px(lx - 1, ly - 1, "#fff2c0")
    # porta do porão arrancada: aba de chapa torta pendurada no canto de cima
    flap = [S(28, 25), S(36, 25), S(38, 21), S(31, 19)]
    cv.poly(flap, pal[2][1]); cv.line([flap[0], flap[1]], pal[0][0]); cv.line([flap[2], flap[3]], BD)

    # ---- motores (um apagado)
    for (v0, v1, dmg) in ((0, 5, False), (37, 42, True)):
        iso.box(Lu, Lu + 9, v0, v1, 14, 28, pal[1:4], BD, HI, seed=50 + v0)
        cx, cy = P(Lu + 9, (v0 + v1) / 2, 21)
        cv.fill(cv.emask(cx, cy, 4, 5), BD)
        cv.fill(cv.emask(cx, cy, 3, 4), "#17131e" if dmg else BL3)
        if not dmg:
            cv.fill(cv.emask(cx, cy - 1, 1.5, 2), BL2)
            p = cv.pt((cx, cy)); n.fill(n.emask(p[0], p[1], 2, 3), BL)
        else:
            cv.line([(cx - 4, cy - 4), (cx + 3, cy + 4)], "#58536b")
            p = cv.pt((cx, cy + 4)); n.line([(p[0], p[1]), (p[0] + 1, p[1] + 8)], "#17131e")   # fio solto
        for z in (17, 25):
            rivets(n, [cv.pt(P(Lu + 1, v1, z)), cv.pt(P(Lu + 8, v1, z))], pal[3][2], 4)

    # ---- rampa (mais comprida) até a areia, com luz do porão caindo nela
    ramp = [P(Lu, 6, 3), P(Lu, 36, 3), P(Lu + RL, 36, 0), P(Lu + RL, 6, 0)]
    cv.poly([(x + (1 if i in (1, 2) else 0), y) for i, (x, y) in enumerate(ramp)], OUT)
    rmask = cv.pmask(ramp)
    cv.banded(rmask, ["#9aa3bd", "#7f89ad", "#6f7898", "#575f7d"], cuts=[.25, .55, .8])
    pool = cv.pmask([P(Lu, 10, 3), P(Lu, 32, 3), P(Lu + 14, 30, 1.8), P(Lu + 14, 12, 1.8)]) & rmask   # poça de luz
    n.paint(pool, lambda x, y: "#b9c6e6" if (x + 2 * y) % 5 else "#cfe0ff")
    for kk in range(1, 9):
        z = 3 - 3 * kk * 4 / RL
        cv.line([P(Lu + kk * 4, 6, z), P(Lu + kk * 4, 36, z)], "#363c54")
    for kk in range(2, RL, 5):
        x, y = P(Lu + kk, 6, 1.5); cv.px(x, y, BL); x, y = P(Lu + kk, 36, 1.5); cv.px(x, y, BL)
    cv.line([P(Lu, 6, 3), P(Lu + RL, 6, 0)], GOLD); cv.line([P(Lu, 36, 3), P(Lu + RL, 36, 0)], GOLD)
    # pegadas de bota na rampa? não: ninguém voltou. Rastro de areia escorrida no pé da rampa
    sand_pile(cv, *P(Lu + RL + 2, 22, 0), 9, 2.4, 7)

    # ---- caixas caídas do porão (fora, perto da rampa) + carga espalhada
    for (u, v, c) in ((Lu + 14, 44, "#6c4030"), (Lu + 22, 37, "#4b5273") if r2 else (Lu + 28, 46, "#4b5273")):
        iso.box(u, u + 9, v, v + 9, 0, 8, ((c, c, c), (c, c, c), (c, c, c)), BD, "#d9a066",
                top_tone=("#c98a56", "#9a5a3a", "#7a4a34") if c == "#6c4030" else ("#7f89ad", "#4b5273", "#363c54"), seed=60)
    su, sv = (Lu + 4, 47) if r2 else (Lu + 20, 38)
    iso.box(su, su + 5, sv, sv + 5, 0, 4, (("#c98a56",) * 3, ("#9a5a3a",) * 3, ("#6c4030",) * 3), BD, "#d9a066", seed=61, wear=0)
    a = cv.pt(P(Lu + 18, 46, 8)); n.rect(a[0], a[1] + 2, 6, 1, GOLD)

    # ---- pernas da frente (uma quebrada), peças soltas
    leg(10, Wv, broken=False)
    leg(64, Wv, broken=True)
    fx, fy = P(56, Wv + 12, 0)
    cv.rect(fx - 6, fy - 1, 12, 3, pal[3][2]); cv.rect(fx - 6, fy - 1, 12, 1, pal[1][0]); cv.line([(fx + 5, fy - 1), (fx + 12, fy - 9)], pal[3][2], 2)
    for (u, v, z) in ((30, Wv + 14, 0), (40, Wv + 18, 0)):
        x, y = P(u, v, z); cv.rect(x - 5, y - 1, 10, 3, pal[2][1]); cv.rect(x - 5, y - 1, 10, 1, pal[0][0])
    # NOVO: chapa grande do casco arrancada no pouso, caída na areia (preenche a frente da pegada com coisa de verdade)
    hp = [P(30, 58, 1), P(52, 54, 1), P(58, 66, 1), P(36, 72, 1)]
    cv.poly([(x, y + 1) for x, y in hp], BD)
    hm = cv.pmask(hp)
    cv.banded(hm, [pal[0][1], pal[1][1], pal[2][1]], cuts=[.35, .7])
    cv.speckle(hm, pal[2][2], .12, 31)
    for t in (.33, .66):
        a_ = (hp[0][0] + (hp[1][0] - hp[0][0]) * t, hp[0][1] + (hp[1][1] - hp[0][1]) * t)
        b_ = (hp[3][0] + (hp[2][0] - hp[3][0]) * t, hp[3][1] + (hp[2][1] - hp[3][1]) * t)
        cv.line([a_, b_], pal[3][2])
    cv.line([hp[0], hp[1]], pal[0][0])
    rivets(n, [cv.pt(P(32, 60, 1)), cv.pt(P(51, 56, 1))], pal[3][2], 5)
    ob = cv.pmask([P(40, 60, 1.2), P(48, 58, 1.2), P(50, 62, 1.2), P(42, 64, 1.2)])
    cv.fill(ob, OR); cv.line([P(40, 60, 1.2), P(48, 58, 1.2)], OR_L)
    cv.poly([hp[1], P(52, 54, 6), P(58, 66, 6), hp[2]], pal[3][1])            # borda dobrada pra cima
    cv.line([P(52, 54, 6), P(58, 66, 6)], pal[1][0])
    # NOVO: caixotes que caíram pelo rasgo e cabos soltos
    for (u, v, s_, c) in ((64, 58, 7, "#6c4030"), (26, 62, 6, "#4b5273") if r2 else (20, 64, 6, "#4b5273"), (70, 66, 5, "#6c4030")):
        top = ("#c98a56", "#9a5a3a", "#7a4a34") if c == "#6c4030" else ("#7f89ad", "#4b5273", "#363c54")
        iso.box(u, u + s_, v, v + s_, 0, s_ - 1, ((c, c, c),) * 3, BD, "#d9a066", top_tone=top, seed=u + v, wear=0)
    for (p0, p1, p2) in (((60, 50, 0), (66, 54, 0), (64, 60, 0)), ((14, 50, 0), (12, 56, 0), (18, 62, 0))):
        cv.line([P(*p0), P(*p1), P(*p2)], "#17131e")
    scatter(cv, [(4, 112), (50, 120), (90, 122), (20, 108), (60, 116), (8, 100)], 3)
    scatter_n(n, [(40, 196), (70, 206), (150, 212), (118, 200), (186, 214), (20, 186), (300, 200), (306, 186)], 4)
    for (x, y, w_, h_) in ((96, 196, 14, 4), (54, 186, 10, 3), (172, 206, 12, 4)):
        scrap(n, x, y, w_, h_, pal[0][0], pal[3][2], 2)
    cv.outline()
    cv.meta = dict(CARGO)
    return cv


# =====================================================================================================================
# 2 · Base espacial de vidro (module) · r5 em iso · k = 1.75 · 448×294 · pegada 14×5 · lift 134
# =====================================================================================================================
BBD = "#4a4256"
TONES = [(CREAM[0], CREAM[1], CREAM[2]), (CREAM[2], CREAM[3], CREAM[4]), (CREAM[3], CREAM[4], CREAM[5])]
MODULE = dict(size=(14, 5), sprite=(448, 294), lift=134, crate=(10, 5), terminal=(8, 4), reads_from=(8, 5),
              door=(2, 4), door_approach=(2, 5))


def solar_s(cv, P, u, v0, v1, z0, z1, hole=False):
    """Painel solar no plano u = const (igual ao r5), células com brilho em px nativos."""
    n = cv.n
    a, b = P(u, (v0 + v1) / 2, 0), P(u, (v0 + v1) / 2, z0 + 2)
    cv.line([a, b], METAL[3], 3)
    cv.poly([P(u + 3, v0, z0), P(u + 3, v1, z0), P(u + 3, v1, z1), P(u + 3, v0, z1)], METAL[4])
    q = [P(u, v0, z0), P(u, v1, z0), P(u, v1, z1), P(u, v0, z1)]
    cv.poly(q, METAL[3])
    m = cv.pmask([P(u, v0 + 1, z0 + 1), P(u, v1 - 1, z0 + 1), P(u, v1 - 1, z1 - 1), P(u, v0 + 1, z1 - 1)])
    cv.banded(m, ["#5b86d0", "#3d63a8", "#2f5090"], cuts=[.3, .7])
    n.paint(m, lambda x, y: "#bcd6ff" if (x + y * 2) % 17 == 0 else None)
    for kk in range(1, 6):
        cv.line([P(u, v0 + (v1 - v0) * kk / 6, z0), P(u, v0 + (v1 - v0) * kk / 6, z1)], "#1f3a6e")
    for zz in (1 / 3, 2 / 3):
        cv.line([P(u, v0, z0 + (z1 - z0) * zz), P(u, v1, z0 + (z1 - z0) * zz)], "#1f3a6e")
    if hole:
        cv.fill(cv.pmask([P(u, v0, z1), P(u, v0 + 10, z1), P(u, v0 + 4, z1 - 8), P(u, v0, z1 - 12)]) & m, (0, 0, 0, 0))
        cv.line([P(u, v0 + 10, z1), P(u, v0 + 4, z1 - 8), P(u, v0, z1 - 12)], METAL[2])


def _tank(cv, n, P, iso, TU):
    """Anexo-tanque da base (caixa creme com escada), com o canto de trás em u = TU."""
    iso.box(TU, TU + 26, 30, 56, 0, 24, TONES, BBD, CREAM[0], seed=3)
    L1 = lambda u, z: P(u, 56, z)
    cv.line([L1(TU, 12), L1(TU + 26, 12)], OR); cv.line([L1(TU, 11), L1(TU + 26, 11)], OR_D)
    cv.poly([L1(TU + 6, 20), L1(TU + 14, 20), L1(TU + 14, 14), L1(TU + 6, 14)], "#17131e"); cv.line([L1(TU + 7, 19), L1(TU + 13, 19)], GL[1])
    for kk in range(3):
        x, y = P(TU + 8 + kk * 5, 38, 28); cv.rect(x, y - 3, 3, 4, CREAM[3])
    # NOVO: medidor e válvula no tanque, rebites, escada de manutenção
    gx, gy = cv.pt(L1(TU + 19, 18)); n.fill(n.emask(gx, gy, 3.5, 3.5), BBD); n.fill(n.emask(gx, gy, 2.5, 2.5), "#f4efe0"); n.line([(gx, gy), (gx + 2, gy - 1)], OR_D)
    for z in (3, 22):
        rivets(n, [cv.pt(L1(TU + 1, z)), cv.pt(L1(TU + 25, z))], CREAM[4], 6)
    for kk in range(5):
        a_ = cv.pt(P(TU + 26, 44, 3 + kk * 4)); n.rect(a_[0] - 3, a_[1], 6, 1, METAL[3])
    a_, b_ = cv.pt(P(TU + 26, 41, 1)), cv.pt(P(TU + 26, 41, 21)); n.line([a_, b_], METAL[3]); a_, b_ = cv.pt(P(TU + 26, 47, 1)), cv.pt(P(TU + 26, 47, 21)); n.line([a_, b_], METAL[3])


def module(r2=False):
    """r2 (rodada 2): painéis solares atrás e à direita do tambor, sem cortar o domo; o anexo-tanque afastado e desenhado DEPOIS do
    tambor (ele está na frente); antena sem encostar na borda de cima."""
    W, H = MODULE["sprite"]
    k = 1.75
    cv = SCv(W, H, k, ox=0, oy=-6)
    n = cv.n
    iso = Iso(cv, 128, 62)
    P = iso.P
    rows = np.arange(H)[:, None]
    cols = np.arange(W)[None, :]
    cv.shadow_ell(132, 122, 118, 26)
    sand_pile(cv, 14, 124, 12, 4, 1); sand_pile(cv, 242, 126, 12, 4, 2); sand_pile(cv, 196, 150, 18, 4, 6)

    if r2:
        solar_s(cv, P, 92, -24, -3, 22, 46, True); solar_s(cv, P, 92, -1, 18, 22, 46)
    else:
        solar_s(cv, P, 108, -8, 14, 22, 46, True); solar_s(cv, P, 108, 18, 40, 22, 46)
    TU = 108 if r2 else 100                                                   # u do anexo-tanque (r2: 8 mais pra frente)

    def tank():
        _tank(cv, n, P, iso, TU)
    if not r2:
        tank()
    # ---- tambor central (nativo: a elipse e o vidro saem na resolução nova)
    cxo, cyo = P(60, 40, 30)
    cx, cy0 = cv.pt((cxo, cyo))
    rx, ry, wall = 48 * k, 24 * k, round(30 * k)
    body = n.emask(cx, cy0 + wall, rx, ry) | n.mask(lambda d: d.rectangle([int(cx - rx), int(cy0), int(cx + rx - 1), int(cy0 + wall)], fill=255))
    body &= ~(n.emask(cx, cy0, rx, ry) & (rows < cy0))
    n.paint(body, lambda x, y: CREAM[1] if (x - cx) / rx < -.55 else CREAM[2] if (x - cx) / rx < -.05 else CREAM[3] if (x - cx) / rx < .4 else CREAM[4] if (x - cx) / rx < .75 else CREAM[5])
    b0, b1 = round(5 * k), round(22 * k)
    band = np.zeros_like(body)
    for x in range(int(cx - rx + 4), int(cx + rx - 3)):
        t = (x - cx) / rx
        e = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        band[int(e) + b0:int(e) + b1, x] = True
    band &= body
    pane(n, band, 11)
    shade_region(n, band & (cols > cx + rx * .35), .72)
    for ang in np.linspace(0.08, math.pi - 0.08, 15):
        x = cx + rx * math.cos(ang); e = cy0 + ry * math.sin(ang)
        for yy in range(int(e) + b0, int(e) + b1 + 1):
            n.px(x, yy, CREAM[2] if math.cos(ang) < 0 else CREAM[5])
    for x in range(int(cx - rx + 1), int(cx + rx)):
        t = (x - cx) / rx
        e = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        n.rect(x, int(e) + 1, 1, 5, OR if t < .4 else OR_D); n.px(x, int(e) + 1, OR_L if t < -.2 else OR)
        n.rect(x, int(e) + b1 + 2, 1, wall - b1 - 2, CREAM[3] if t < 0 else CREAM[4] if t < .5 else CREAM[5])
        if x % 9 == 0:
            n.px(x, int(e) + b1 + 5, CREAM[5] if t < .5 else BBD)                      # NOVO: rebites da saia
    topm = n.emask(cx, cy0, rx, ry)
    n.paint(topm, lambda x, y: CREAM[0] if (x - cx) / rx + (y - cy0) / ry < -.55 else CREAM[1] if (x - cx) / rx < .25 else CREAM[2] if (x - cx) / rx < .65 else CREAM[3])
    # domo
    dr, dry, dh = 40 * k, 20 * k, 44 * k
    dome = n.emask(cx, cy0, dr, dry) | (n.emask(cx, cy0, dr, dh) & (rows <= cy0))
    pane(n, dome, 29)
    floor = n.emask(cx, cy0 - 1, dr - 8, dry - 6)
    n.paint(floor, lambda x, y: "#2c5060" if ((x // 4) + (y // 3)) % 2 == 0 else "#244456")
    for (x, y) in ((cx - 20, cy0 - 5), (cx + 10, cy0 + 3), (cx + 30, cy0 - 3), (cx - 5, cy0 - 13), (cx - 34, cy0 + 2)):
        n.rect(x, y, 6, 4, "#3f7a8c"); n.px(x + 1, y, "#7fd67a"); n.px(x + 3, y - 1, "#7fd67a")       # canteiros secos
    def meridian(psi, col):
        pts = []
        for i in range(40):
            f = i / 39 * .985; r_ = math.sqrt(1 - f * f)
            pts.append((cx + dr * r_ * math.cos(psi), cy0 - f * dh + dry * r_ * math.sin(psi)))
        for a_, b_ in zip(pts, pts[1:]):
            n.line([a_, b_], col, 1)
    for psi in (math.pi + .4, math.pi + 1.0, math.pi + 1.6, math.pi + 2.2, math.pi + 2.8):
        meridian(psi, GL[4])
    for psi in (0.1, 0.5, 0.95, 1.35, 1.75, 2.15, 2.6, 3.05):
        meridian(psi, CREAM[1] if math.cos(psi) < 0 else CREAM[4])
    for f_ in (.3, .62):
        r_ = math.sqrt(1 - f_ * f_)
        arc(n, cx, cy0 - f_ * dh, dr * r_, dry * r_, .02, math.pi - .02, CREAM[2], 60, 1)
    arc(n, cx, cy0, dr, dry, .0, math.pi, CREAM[1], 70, 3)
    shade_region(n, dome & (cols > cx + dr * .4), .78)
    hx, hy = cx + 8 * k, cy0 - 28 * k
    brk = []
    for i in range(16):
        an = 2 * math.pi * i / 16
        rr = (11 + 5 * hsh(i, 3, 4) + (5 if i % 2 else 0)) * k
        brk.append((hx + rr * 1.25 * math.cos(an), hy + rr * .9 * math.sin(an)))
    mb = n.pmask(brk) & dome
    n.fill(mb, INT[1]); n.paint(mb, lambda x, y: INT[2] if y > hy + 3 else INT[0] if y < hy - 14 else None)
    n.line([(hx - 17, hy - 14), (hx, hy + 3), (hx + 21, hy - 10)], RUST[1], 3); n.line([(hx - 3, hy - 22), (hx, hy + 17)], RUST[2], 2)
    for (x, y) in brk:
        n.px(x, y, GL[0]); n.px(x + 1, y + 1, GL[4])
    for (a_, b_) in (((hx - 42, hy + 14), (hx - 23, hy + 3)), ((hx + 24, hy + 5), (hx + 45, hy + 24)), ((hx - 14, hy + 28), (hx - 21, hy + 45)), ((hx + 6, hy - 30), (hx + 16, hy - 44))):
        n.line([a_, b_], "#ffffff"); n.line([(a_[0] + 1, a_[1] + 1), (b_[0] + 1, b_[1] + 1)], GL[4])
    n.fill(n.pmask([(cx + 24, cy0 + 14), (cx + 45, cy0 + 7), (cx + 52, cy0 + 31), (cx + 31, cy0 + 38)]) & band, INT[2])
    # antena (mais alta) + prato novo
    at = 4 if r2 else 0                                                      # r2: a ponta não encosta na borda
    n.rect(cx - 49, 4 + at, 3, int(cy0 - 4 - 38 * k) + 6 - at, METAL[2]); n.rect(cx - 56, 26, 17, 2, METAL[2]); n.rect(cx - 51, at, 7, 5, "#ff5a4a"); n.rect(cx - 51, at, 2, 2, "#ffb0a0")
    if r2:
        tank()


    # NOVO: tubo de ligação eclusa → tambor (sanfona)
    for kk in range(6):
        a_ = cv.pt(P(40 + kk * 3, 80, 18)); n.rect(a_[0] - 3, a_[1] - 9, 7, 13, CREAM[2] if kk % 2 else CREAM[3]); n.rect(a_[0] - 3, a_[1] - 9, 7, 1, CREAM[0])

    # ---- eclusa (frente-esquerda)
    iso.box(30, 66, 84, 112, 0, 28, TONES, BBD, CREAM[0], seed=5)
    LL = lambda u, z: P(u, 112, z)
    cv.line([LL(30, 14), LL(66, 14)], OR); cv.line([LL(30, 13), LL(66, 13)], OR_D); cv.line([LL(30, 18), LL(66, 18)], OR_L)
    cv.poly([LL(34, 24), LL(42, 24), LL(42, 18), LL(34, 18)], "#17131e"); cv.poly([LL(35, 23), LL(41, 23), LL(41, 19), LL(35, 19)], GL[2]); cv.line([LL(35, 22), LL(40, 20)], GL[0])
    door = [LL(46, 3), LL(60, 3), LL(60, 25), LL(46, 25)]
    cv.poly(door, OUT)
    dm = cv.pmask([LL(47, 4), LL(59, 4), LL(59, 24), LL(47, 24)])
    cv.banded(dm, [CAV[0], CAV[1], CAV[2]], cuts=[.3, .7])
    cv.line([LL(46, 25), LL(60, 25)], GOLD); cv.line([LL(47, 5), LL(59, 5)], "#59d0e6")
    x, y = LL(52, 14); cv.rect(x, y, 2, 2, "#ff6a55")
    # NOVO: porta entreaberta (folha de correr presa na metade, fresta escura) e luz de emergência em cima
    leaf = cv.pmask([LL(47, 4), LL(53, 4), LL(53, 24), LL(47, 24)])
    cv.banded(leaf, [CREAM[2], CREAM[3], CREAM[4]], cuts=[.3, .7])
    cv.line([LL(53, 4), LL(53, 24)], BBD); cv.line([LL(50, 6), LL(50, 22)], CREAM[5])
    a_ = cv.pt(LL(53, 28)); n.rect(a_[0] - 2, a_[1] - 3, 6, 4, BBD); n.rect(a_[0] - 1, a_[1] - 2, 4, 2, "#ff8a3a")
    for z in (4, 27):
        rivets(n, [cv.pt(LL(31, z)), cv.pt(LL(65, z))], CREAM[4], 6)
    ramp = [P(46, 112, 3), P(60, 112, 3), P(60, 134, 0), P(46, 134, 0)]
    cv.poly([(x - (1 if i in (0, 3) else 0), y) for i, (x, y) in enumerate(ramp)], OUT)
    rm = cv.pmask(ramp)
    cv.paint(rm, lambda x, y: BGR[0] if y < P(46, 118, 0)[1] - 2 else BGR[1] if y < P(46, 126, 0)[1] - 1 else BGR[2])
    for kk in range(1, 5):
        cv.line([P(46, 112 + kk * 5, 3 - kk * .6), P(60, 112 + kk * 5, 3 - kk * .6)], BGR[3])
    cv.line([P(46, 112, 3), P(46, 134, 0)], GOLD); cv.line([P(60, 112, 3), P(60, 134, 0)], GOLD)
    # ---- terminal na FRENTE (borda de baixo da pegada: se lê do tile logo abaixo, de fora)
    tpos = P(104, 80, 0)
    tx, ty = cv.pt(tpos)
    n.rect(tx - 10, ty - 6, 22, 8, CREAM[4]); n.rect(tx - 10, ty - 6, 22, 2, CREAM[2]); n.rect(tx - 10, ty + 1, 22, 1, CREAM[5])   # sapata
    n.rect(tx - 3, ty - 14, 8, 9, CREAM[3]); n.rect(tx - 3, ty - 14, 2, 9, CREAM[2])                                           # coluna
    TW, TH = 32, 26
    rx0, ry0 = tx - TW // 2 + 1, ty - 14 - TH
    n.rect(rx0, ry0, TW, TH, OUT); n.rect(rx0 + 1, ry0 + 1, TW - 2, TH - 2, CREAM[1]); n.rect(rx0 + 1, ry0 + TH - 7, TW - 2, 6, CREAM[4])
    n.rect(rx0 + 1, ry0 + 1, TW - 2, 1, CREAM[0])
    n.rect(rx0 + 4, ry0 + 4, TW - 8, TH - 13, "#102018")
    for (yy, w_, c) in ((6, 14, "#7fd67a"), (9, 20, "#4aa860"), (12, 10, "#7fd67a"), (15, 16, "#4aa860")):
        n.rect(rx0 + 6, ry0 + yy, w_, 1, c)
    n.rect(rx0 + TW - 9, ry0 + 15, 2, 1, "#7fd67a")
    for kk in range(4):
        n.rect(rx0 + 5 + kk * 6, ry0 + TH - 5, 4, 2, CREAM[2] if kk != 2 else OR)                                                   # teclas
    n.rect(rx0 + TW - 4, ry0 + 2, 2, 2, "#ff5a4a")
    # cabo do terminal até o tambor
    n.line([(tx + 10, ty - 1), (tx + 26, ty - 6), (tx + 40, ty - 20)], "#17131e")
    term_rect = (rx0, ry0, TW, TH)

    # ---- entulho e sucata (novo, mais e maior)
    for (u, v, du, dv, tn, sd, tl) in ((92, 98, 10, 6, TONES[0], 1, 0), (70, 128, 7, 5, TONES[0], 3, 0),
                                        (150, 40, 10, 7, TONES[1], 4, 3), (36, 122, 6, 6, TONES[2], 5, 0)):
        m = flat_plate(cv, P, u, v, du, dv, tn, BBD, seed=sd, tilt=tl)
        if sd in (1, 4):
            a_, b_ = cv.pt(P(u + 2, v + 1, 1.2)), cv.pt(P(u + du - 2, v + 1, 1.2)); n.line([a_, b_], OR)
    # painel solar arrancado, deitado na areia na frente do tanque (vidro azul com a grade) (r2: tirado, encostava no pé do anexo)
    if not r2:
        FV = 60 if r2 else 52                                                    # r2: longe do pé do anexo
        sp = [P(118, 0 + FV, 2), P(134, FV, 1), P(134, FV + 12, 1), P(118, FV + 12, 3)]
        cv.poly([(x, y + 2) for x, y in sp], METAL[4]); cv.poly(sp, METAL[3])
        m = cv.pmask([P(119, FV + 1, 2), P(133, FV + 1, 1), P(133, FV + 11, 1), P(119, FV + 11, 3)])
        cv.banded(m, ["#5b86d0", "#3d63a8", "#2f5090"], cuts=[.3, .7]); n.paint(m, lambda x, y: "#bcd6ff" if (x + 2 * y) % 17 == 0 else None)
        for kk in range(1, 4):
            cv.line([P(118 + kk * 4, FV, 1.5), P(118 + kk * 4, FV + 12, 1.5)], "#1f3a6e")
        cv.line([P(118, FV + 6, 2), P(134, FV + 6, 1)], "#1f3a6e")
    # vidro estilhaçado do domo no chão (cacos ciano)
    for (u, v) in ((88, 70), (96, 84), (80, 90), (110, 86), (74, 78)):
        x, y = cv.pt(P(u, v, 0)); n.poly([(x, y), (x + 4, y - 2), (x + 6, y + 1), (x + 2, y + 2)], GL[2]); n.px(x + 3, y - 1, GL[0])
    scatter(cv, [(4, 154), (106, 160), (166, 152), (216, 144), (244, 126), (60, 158)], 5)
    scatter_n(n, [(30, 250), (300, 270), (380, 250), (420, 236), (150, 284), (250, 286), (340, 288), (12, 230)], 7)
    cv.outline()
    cv.meta = dict(MODULE, terminal_rect=term_rect, terminal_foot=(tx, ty))
    return cv


# =====================================================================================================================
# 3 · Sonda (probe) · r1 · k = 1.5 · 96×96 · pegada 3×2 · lift 32
# =====================================================================================================================
PROBE = dict(size=(3, 2), sprite=(96, 96), lift=32, crate=(3, 1), led=(34, 55, 3, 2))


def panel_s(cv, p0, ex, ey, nx, ny, tear=None):
    """Painel solar (como o panel do r1), com o brilho das células em px nativos."""
    n = cv.n
    q = quad(p0, ex, ey)
    pts = [q(0, 0), q(1, 0), q(1, 1), q(0, 1)]
    cv.poly(pts, METAL[3])
    m = cv.pmask(pts)
    cv.fill(m, SOLAR[1])
    n.paint(m, lambda x, y: SOLAR[0] if hsh(x, y, 77) > .95 else None)
    for i in range(1, nx):
        cv.line([q(i / nx, 0), q(i / nx, 1)], SOLAR[3])
    for j in range(1, ny):
        cv.line([q(0, j / ny), q(1, j / ny)], SOLAR[3])
    cv.line([q(0, 0), q(1, 0)], SOLAR[0]); cv.line([q(0, 1), q(1, 1)], SOLAR[4])
    if tear:
        u, v = tear
        cv.fill(cv.pmask([q(u, 0), q(1, 0), q(1, v), q(u + .1, v * .6)]) & m, (0, 0, 0, 0))
        cv.line([q(u, 0), q(u + .1, v * .6), q(1, v)], METAL[2])
    return m


def probe(r2=False):
    """r2 (rodada 2): os dois painéis solares encostavam nas bordas esquerda e direita: um tiquinho pra dentro."""
    W, H = PROBE["sprite"]
    cv = SCv(W, H, 1.5, 0, 0)
    n = cv.n
    cv.shadow_ell(32, 54, 28, 6)
    sand_pile(cv, 30, 54, 25, 5, 4)
    if r2:
        panel_s(cv, (5, 44), (17, -8), (-3, 10), 6, 4)
        panel_s(cv, (44, 36), (14.5, -11), (3.5, 10), 4, 4, tear=(.7, .5))
    else:
        panel_s(cv, (3, 44), (18, -8), (-3, 10), 6, 4)
        panel_s(cv, (44, 36), (16, -12), (4, 10), 4, 4, tear=(.7, .5))
    cv.line([(18, 42), (24, 44)], METAL[2], 2); cv.line([(44, 40), (40, 42)], METAL[2], 2)
    # NOVO: dobradiça do painel (cubo com parafuso)
    for (x, y) in ((22, 43), (42, 41)):
        a_ = cv.pt((x, y)); n.rect(a_[0] - 2, a_[1] - 2, 5, 4, METAL[3]); n.px(a_[0], a_[1] - 1, METAL[0])
    # parabólica
    cv.line([(25, 24), (23, 15)], METAL[2], 2)
    dish = cv.emask(23, 12, 11, 7)
    cv.banded(dish, [CREAM[0], CREAM[2], CREAM[3], CREAM[4]], cuts=[.2, .5, .8])
    cv.fill(cv.emask(22, 11, 6, 3.5), CREAM[4]); cv.fill(cv.emask(22, 10, 3.5, 2), CREAM[5])
    # NOVO: aros concêntricos e amassado na parabólica
    a_ = cv.pt((23, 12)); arc(n, a_[0], a_[1], 13, 8, math.pi * .1, math.pi * .9, CREAM[3], 30, 1)
    n.line([(a_[0] + 6, a_[1] - 9), (a_[0] + 10, a_[1] - 5)], CREAM[4])
    cv.line([(22, 11), (30, 4)], METAL[2]); cv.rect(30, 3, 2, 2, "#ff5a4a"); cv.line([(24, 17), (28, 26)], METAL[2], 2)
    # corpo
    body = cv.emask(32, 38, 14, 13)
    def bc(x, y):
        lit = -.6 * (x - 32) / 14 - .8 * (y - 38) / 13
        return CREAM[0] if lit > .62 else CREAM[1] if lit > .3 else CREAM[2] if lit > -.05 else CREAM[3] if lit > -.4 else CREAM[4]
    cv.paint(body, bc)
    arc(cv, 32, 38, 14, 5, .05, math.pi - .05, OR, 30, 3)
    arc(cv, 32, 39.5, 14, 5, .05, math.pi - .05, OR_D, 30, 1)
    arc(cv, 32, 30, 12, 3, .2, math.pi - .2, CREAM[4], 20, 1)
    # NOVO: emendas e rebites do casco esférico, escotilha de serviço
    c_ = cv.pt((32, 38))
    for ang in (math.pi * .62, math.pi * .38):
        n.line([(c_[0] + 20 * math.cos(ang + math.pi), c_[1] - 19), (c_[0] + 21 * math.cos(ang), c_[1] + 18)], CREAM[3]) if False else None
    for i in range(9):
        ang = math.pi * (.08 + .84 * i / 8)
        n.px(c_[0] + 19 * math.cos(ang), c_[1] + 11 + 4 * math.sin(ang), CREAM[5])
    n.rect(c_[0] - 14, c_[1] - 6, 6, 5, CREAM[4]); n.rect(c_[0] - 14, c_[1] - 6, 6, 1, CREAM[1]); n.px(c_[0] - 9, c_[1] - 4, BBD)
    cv.fill(cv.emask(32, 31, 4.5, 2.5) | cv.emask(32, 33, 5, 2), OUT)
    cv.fill(cv.emask(32, 32, 3.5, 2), "#3a5068"); cv.px(31, 31, GLASS[0])
    cv.line([(22, 40), (25, 48)], CREAM[5]); cv.line([(25, 48), (23, 51)], CREAM[5])
    cv.fill(cv.emask(40, 46, 3, 2), CAV[1])
    # bocal
    nz = [(36, 46), (50, 51), (52, 55), (38, 52)]
    cv.poly(nz, METAL[3]); cv.poly([(36, 46), (50, 51), (50, 52), (36, 48)], METAL[0])
    cv.fill(cv.emask(51, 54, 2.5, 2), CAV[2]); cv.px(50, 52, OR)
    for t in (.3, .55):                                                        # NOVO: anéis do bocal
        a_ = cv.pt((36 + 14 * t, 46 + 5 * t)); n.line([(a_[0], a_[1]), (a_[0] + 2, a_[1] + 7)], METAL[4])
    # LED piscante (o render apaga esse retângulo)
    lx, ly, lw, lh = PROBE["led"]
    n.rect(lx - 1, ly - 1, lw + 2, lh + 2, BBD); n.rect(lx, ly, lw, lh, "#ff5a4a")
    # patas, sucata, caixa de instrumentos
    cv.rect(18, 50, 3, 5, METAL[3]); cv.rect(44, 52, 3, 4, METAL[3])
    a_ = cv.pt((19, 55)); n.rect(a_[0] - 3, a_[1] - 1, 8, 2, METAL[2])
    a_ = cv.pt((45, 56)); n.rect(a_[0] - 3, a_[1] - 1, 8, 2, METAL[2])
    scatter(cv, [(4, 56), (10, 58), (54, 58), (30, 59), (58, 52), (2, 52), (46, 58)], 9)
    cv.rect(46, 44, 9, 7, METAL[4]); cv.rect(46, 44, 9, 2, METAL[1])
    a_ = cv.pt((47, 47)); n.rect(a_[0] + 1, a_[1] + 1, 4, 1, "#7fd67a"); n.rect(a_[0] + 7, a_[1] + 1, 2, 2, OR)
    # NOVO: cabo saindo do casco até a caixinha, e antena-chicote quebrada
    n.line([cv.pt((44, 42)), cv.pt((47, 41)), cv.pt((49, 44))], "#17131e")
    n.line([cv.pt((38, 26)), cv.pt((44, 14)), cv.pt((49, 12))], METAL[2])
    cv.outline()
    cv.meta = dict(PROBE)
    return cv


# =====================================================================================================================
# 4 · Robô de reconhecimento R-2 (robot) · r2 · k = 5/3 · 160×104 · pegada 5×2 · lift 40
# =====================================================================================================================
ROBOT = dict(size=(5, 2), sprite=(160, 104), lift=40, crate=(2, 2))


def robot():
    W, H = ROBOT["sprite"]
    cv = SCv(W, H, 5 / 3, 0, 0)
    n = cv.n
    cv.shadow_ell(48, 56, 45, 6.5)
    sand_pile(cv, 40, 56, 38, 5, 6)
    track2(cv, (50, 34), (76, 31), 6, dark=True)
    track2(cv, (62, 58), (92, 57), 4)
    body = [(20, 28), (26, 18), (62, 16), (70, 24), (68, 42), (24, 44)]
    cv.poly(body, CREAM[3]); mb = cv.pmask(body)
    cv.banded(mb, [CREAM[0], CREAM[1], CREAM[2], CREAM[3], CREAM[4]], cuts=[.12, .4, .65, .88])
    cv.rect(22, 27, 46, 4, OR); cv.rect(22, 27, 46, 1, OR_L); cv.rect(22, 30, 46, 1, OR_D)
    cv.line([(40, 19), (38, 41)], CREAM[4]); cv.line([(56, 18), (58, 41)], CREAM[4])
    cv.speckle(mb, CREAM[4], .2, 5)
    # NOVO: rebites nas emendas, grade de ventilação, número "R-2" no capô e painel solar no lombo
    for (a_, b_) in (((40, 20), (38, 40)), ((56, 19), (58, 40))):
        rivets(n, [cv.pt((a_[0] + 1.2, a_[1])), cv.pt((b_[0] + 1.2, b_[1]))], CREAM[5], 5)
    for kk in range(4):
        a_ = cv.pt((26 + kk * 3, 35)); n.rect(a_[0], a_[1], 3, 6, CREAM[5]); n.rect(a_[0], a_[1], 1, 6, CREAM[4])
    sp = [(28, 17), (52, 15.5), (54, 19), (30, 21)]
    cv.poly(sp, METAL[3]); m = cv.pmask([(29, 17.5), (51, 16), (53, 18.6), (31, 20.4)]); cv.fill(m, SOLAR[1])
    for kk in range(1, 4):
        cv.line([(29 + kk * 6, 17.2), (30.5 + kk * 6, 20.5)], SOLAR[3])
    n.paint(m, lambda x, y: SOLAR[0] if hsh(x, y, 5) > .9 else None)
    for i, ch in enumerate(("R", "-")):
        for j, row in enumerate(FONT[ch]):
            for kk, b in enumerate(row):
                if b == "1":
                    a_ = cv.pt((30, 22)); n.rect(a_[0] + (i * 4 + kk) * 2, a_[1] + j * 2, 2, 2, BBD)
    a_ = cv.pt((30, 22)); x0 = a_[0] + 16
    for (dx, dy, w_, h_) in ((0, 0, 6, 2), (4, 2, 2, 2), (0, 4, 6, 2), (0, 6, 2, 2), (0, 8, 6, 2)):
        n.rect(x0 + dx, a_[1] + dy, w_, h_, BBD)
    # painel arrancado com a placa verde
    cv.rect(42, 33, 12, 7, OUT); cv.rect(43, 34, 10, 5, "#2a6a3a")
    a_ = cv.pt((43, 34))
    for (dx, dy, c) in ((2, 2, "#7fd67a"), (8, 3, GOLD), (12, 2, "#7fd67a"), (5, 5, "#9fe8a0")):
        n.rect(a_[0] + dx, a_[1] + dy, 2, 2, c)
    n.line([(a_[0] + 1, a_[1] + 7), (a_[0] + 15, a_[1] + 7)], "#7fd67a"); n.line([(a_[0] + 6, a_[1] + 1), (a_[0] + 6, a_[1] + 6)], "#4aa860")
    cv.poly([(54, 32), (60, 33), (58, 39), (54, 37)], CREAM[3]); cv.line([(54, 32), (60, 33)], CREAM[0])
    # fios pra fora do painel
    n.line([cv.pt((50, 39)), cv.pt((53, 43)), cv.pt((51, 46))], "#ff5a4a"); n.line([cv.pt((47, 39)), cv.pt((48, 44))], "#59d0e6")
    # braço dobrado com garra caída
    cv.line([(24, 32), (13, 36), (9, 48)], METAL[2], 3)
    for pnt in ((24, 32), (13, 36)):
        a_ = cv.pt(pnt); n.fill(n.emask(a_[0], a_[1], 3, 3), METAL[3]); n.px(a_[0] - 1, a_[1] - 1, METAL[0])
    cv.rect(8, 50, 8, 3, METAL[3]); cv.rect(8, 53, 3, 2, METAL[4]); cv.rect(13, 53, 3, 2, METAL[4])
    # pescoço + cabeça/câmera
    cv.line([(46, 18), (46, 14)], METAL[2], 3); cv.fill(cv.emask(46, 18, 4, 2.5), METAL[3])
    head = cv.pmask([(34, 3), (56, 1), (58, 14), (36, 16)])
    cv.banded(head, [CREAM[0], CREAM[1], CREAM[3], CREAM[4]], cuts=[.2, .55, .85])
    cv.rect(35, 9, 22, 2, OR)
    cv.fill(cv.emask(46, 8, 5, 5), OUT); cv.fill(cv.emask(46, 8, 3.8, 3.8), "#e2733a"); cv.fill(cv.emask(46, 8, 2, 2), "#17131e"); cv.px(44, 6, "#ffe0b0")
    # NOVO: lente rachada e segunda lente apagada
    a_ = cv.pt((46, 8)); n.line([(a_[0] + 1, a_[1] - 3), (a_[0] + 3, a_[1] + 1)], "#ffe0b0")
    b_ = cv.pt((53, 6)); n.fill(n.emask(b_[0], b_[1], 3, 3), OUT); n.fill(n.emask(b_[0], b_[1], 2, 2), "#3a5068")
    cv.rect(35, 5, 3, 4, METAL[3]); cv.rect(54, 4, 3, 5, METAL[3])
    cv.line([(64, 18), (68, 8)], METAL[2]); cv.rect(67, 4, 4, 3, "#ff5a4a"); cv.px(67, 4, "#ffb0a0")
    # esteira da frente
    track2(cv, (18, 51), (52, 47), 7)
    # caixote caído (amostras) com tampa solta e tubos de amostra espalhados
    cv.poly([(74, 42), (88, 40), (90, 50), (76, 52)], OUT); cv.poly([(75, 43), (87, 41), (88, 49), (76, 51)], "#4b5273")
    cv.poly([(75, 43), (87, 41), (88, 44), (75, 46)], "#7f89ad"); cv.line([(76, 48), (88, 46)], "#262a42")
    cv.rect(80, 45, 3, 2, OR)
    for (x, y, c) in ((90, 54, "#7fd67a"), (95, 51, "#59d0e6"), (86, 56, GOLD)):
        a_ = cv.pt((x, y)); n.rect(a_[0], a_[1], 6, 3, "#d9dde6"); n.rect(a_[0] + 1, a_[1] + 1, 3, 1, c); n.px(a_[0] + 5, a_[1] + 1, METAL[3])
    # NOVO: roda solta e sapatas de esteira no chão
    w_ = cv.pt((6, 58)); n.fill(n.emask(w_[0], w_[1], 6, 4), "#2a2d33"); n.fill(n.emask(w_[0], w_[1], 3, 2), "#9aa2ab"); n.px(w_[0], w_[1], "#3b3f46")
    for (x, y) in ((58, 60), (70, 61)):
        a_ = cv.pt((x, y)); n.rect(a_[0], a_[1], 6, 2, "#3b3f46"); n.rect(a_[0], a_[1], 6, 1, "#5a6069")
    scatter(cv, [(2, 58), (20, 60), (50, 60), (78, 60), (4, 46), (70, 58)], 12)
    cv.outline()
    cv.meta = dict(ROBOT)
    return cv


# =====================================================================================================================
# 5 · Nave de passageiros ARCA-2 (liner) · r1 · k = 1.8 · 288×208 · pegada 9×4 · lift 80
# =====================================================================================================================
LINER = dict(size=(9, 4), sprite=(288, 208), lift=80, crate=(3, 4))
FONT2 = dict(FONT, A=["010", "101", "111", "101", "101"], C=["111", "100", "100", "100", "111"], **{"2": ["111", "001", "111", "100", "111"]})


def ntext(n, x, y, s, col, sz=2):
    for i, ch in enumerate(s):
        for j, row in enumerate(FONT2[ch]):
            for kk, b in enumerate(row):
                if b == "1":
                    n.rect(x + (i * 4 + kk) * sz, y + j * sz, sz, sz, col)


def liner():
    W, H = LINER["sprite"]
    k = 1.8
    cv = SCv(W, H, k, 0, -2)
    n = cv.n
    cv.shadow_ell(80, 104, 76, 12)
    sand_pile(cv, 14, 98, 14, 7, 1)
    # cauda
    fin = [(116, 66), (126, 22), (144, 10), (150, 14), (144, 58), (140, 70)]
    cv.poly(fin, LAV[2]); cv.poly([(119, 64), (128, 26), (144, 13), (146, 16), (138, 56), (134, 68)], LAV[1])
    cv.poly([(128, 26), (144, 13), (146, 16), (130, 30)], LAV[0]); cv.rect(130, 36, 14, 4, OR); cv.rect(138, 20, 3, 8, OR_D)
    cv.line([(134, 44), (140, 56), (138, 64)], LAV[3]); cv.fill(cv.pmask([(142, 44), (150, 46), (146, 56)]), (0, 0, 0, 0))
    # NOVO: luz de navegação na ponta da deriva e emendas
    a_ = cv.pt((146, 13)); n.rect(a_[0] - 1, a_[1] - 1, 3, 3, "#ff5a4a")
    for (p0, p1) in (((126, 40), (142, 34)), ((122, 54), (140, 48))):
        n.line([cv.pt(p0), cv.pt(p1)], LAV[2])
    cv.poly([(90, 54), (112, 36), (126, 38), (110, 58)], LAV[3])
    def hh(x):
        if x < 40:
            return 6 + 18 * math.sqrt(max(0, 1 - ((40 - x) / 37) ** 2))
        if x > 130:
            return 24 - (x - 130) * .62
        return 24
    x0, x1 = 4, 148
    cy = lambda x: 74 - (x - 4) * 0.02
    fus = [(x, cy(x) - hh(x)) for x in range(x0, x1 + 1)] + [(x, cy(x) + hh(x) * .95) for x in range(x1, x0 - 1, -1)]
    mf = cv.pmask(fus)
    def fc(x, y):
        t = (y - (cy(x) - hh(x))) / (2 * hh(x))
        return CREAM[0] if t < .06 else CREAM[1] if t < .3 else CREAM[2] if t < .55 else CREAM[3] if t < .78 else CREAM[4] if t < .93 else CREAM[5]
    cv.paint(mf, fc)
    for (xa, xb, ta, tb) in ((44, 70, .12, .5), (96, 112, .55, .9), (20, 36, .55, .85), (118, 132, .1, .4)):
        pm = cv.mask(lambda d: d.rectangle([xa, 0, xb, 120], fill=255)) & mf
        cv.paint(pm, lambda x, y: (LAV[0] if (y - (cy(x) - hh(x))) / (2 * hh(x)) < (ta + tb) / 2 - .1 else LAV[1]) if ta < (y - (cy(x) - hh(x))) / (2 * hh(x)) < tb else None)
    for xx in (22, 43, 71, 96, 118, 132):
        cv.line([(xx, cy(xx) - hh(xx) + 1), (xx + 2, cy(xx) + hh(xx) - 2)], CREAM[4])
        for t in np.linspace(.12, .88, 7):                                      # NOVO: rebites na emenda
            yy = cy(xx) - hh(xx) + 2 * hh(xx) * t
            a_ = cv.pt((xx + 2 * t + .8, yy)); n.px(*a_, CREAM[5])
    # NOVO: emenda longitudinal (as chapas em fileira) e escotilha de carga
    for t in (.22, .7):
        pts = [cv.pt((x, cy(x) - hh(x) + 2 * hh(x) * t)) for x in range(44, 130, 2)]
        for a_, b_ in zip(pts, pts[1:]):
            n.line([a_, b_], CREAM[3])
    cv.speckle(mf, CREAM[4], .18, 21)
    for (xa, xb) in ((28, 66), (76, 104), (120, 140)):
        for x in range(xa, xb):
            y = cy(x) + 3
            cv.rect(x, y, 1, 4, OR); cv.rect(x, y, 1, .6, OR_L); cv.rect(x, y + 4, 1, .6, OR_D)
    # janelas de passageiros (nativas: mais e menores, com moldura e reflexo) e nome ARCA-2
    for x in range(40, 125, 6):
        if 72 < x < 104:
            continue
        a_ = cv.pt((x, cy(x) - 9.5))
        n.rect(a_[0], a_[1], 7, 6, "#17131e"); n.rect(a_[0] + 1, a_[1] + 1, 5, 4, GLASS[1]); n.rect(a_[0] + 1, a_[1] + 1, 2, 1, GLASS[0])
        if hsh(x, 3, 9) > .7:
            n.rect(a_[0] + 1, a_[1] + 1, 5, 4, "#1d2b3a")                       # janela apagada/quebrada
            n.px(a_[0] + 2, a_[1] + 2, GLASS[0])
    a_ = cv.pt((106, 67.5)); ntext(n, a_[0], a_[1], "ARCA-2", "#4a4260")
    # cabine
    cab = [(8, 70), (16, 60), (30, 56), (34, 66), (22, 76)]
    cv.poly(cab, "#17131e")
    cab2 = cv.pmask([(10, 70), (17, 62), (28, 59), (31, 66), (22, 74)])
    cv.banded(cab2, [GLASS[0], "#4d78a8", GLASS[1], GLASS[2]], cuts=[.2, .5, .8])
    cv.line([(12, 69), (20, 62)], "#d6ecff"); cv.line([(23, 60), (25, 72)], "#17131e"); cv.rect(14, 74, 6, 2, "#17131e")
    cv.px(27, 62, "#17131e"); cv.line([(9, 71), (21, 77)], "#17131e")
    # NOVO: rachadura em teia no para-brisa
    c_ = cv.pt((19, 66))
    for ang in (0.3, 1.4, 2.6, 3.9, 5.1):
        n.line([c_, (c_[0] + 8 * math.cos(ang), c_[1] + 6 * math.sin(ang))], "#d6ecff")
    # ROMBO na meia-nau
    gap = [(74, 56), (82, 52), (90, 56), (98, 54), (104, 62), (100, 74), (104, 84), (92, 92), (84, 88), (78, 94), (72, 84), (76, 72), (70, 64)]
    mg = cv.pmask(gap) & mf
    cv.fill(mg, CAV[1])
    cv.paint(mg, lambda x, y: "#4a3a44" if y < 66 else CAV[0] if y < 80 else CAV[2])
    for xx in (78, 86, 94):
        cv.line([(xx, 56), (xx + 2, 74), (xx + 1, 90)], RUST[1]); cv.line([(xx + 1, 56), (xx + 3, 74), (xx + 2, 90)], RUST[3])
    cv.line([(74, 66), (102, 68)], RUST[2]); cv.line([(74, 80), (102, 82)], RUST[2])
    for xx in (80, 92):
        cv.rect(xx, 68, 6, 6, LAV[3]); cv.rect(xx, 68, 6, 2, LAV[2]); cv.rect(xx + 1, 74, 4, 3, "#4b5273")
    # NOVO: mais uma fileira de poltronas lá no fundo, cabo pendurado e luz de emergência âmbar
    for xx in (77, 86, 95):
        a_ = cv.pt((xx, 60)); n.rect(a_[0], a_[1], 7, 6, "#3a3448"); n.rect(a_[0], a_[1], 7, 2, "#4b4560")
    a_ = cv.pt((88, 57)); n.line([a_, (a_[0] + 2, a_[1] + 10), (a_[0], a_[1] + 16)], "#17131e"); n.rect(a_[0] - 1, a_[1] + 16, 3, 2, "#ffcf5a")
    for (x, y) in gap:
        cv.rect(x - 2, y - 1, 4, 3, CREAM[3]); cv.px(x - 2, y - 1, CREAM[1]); cv.px(x + 1, y + 1, OR_D)
    cv.line(gap + [gap[0]], OR_D)
    for (x, y, rx, ry) in ((44, 88, 6, 3), (60, 64, 4, 3), (118, 82, 5, 3)):
        m = cv.emask(x, y, rx, ry) & mf
        cv.fill(m, CREAM[5]); cv.speckle(m, "#4d433e", .4, 7)
    # asa da frente
    wing = [(58, 84), (96, 88), (104, 100), (74, 106), (48, 98)]
    cv.poly(wing, LAV[3])
    cv.poly([(60, 85), (95, 89), (101, 98), (74, 103), (52, 97)], LAV[2])
    cv.poly([(60, 85), (95, 89), (97, 91), (62, 88)], LAV[0]); cv.rect(70, 92, 20, 3, OR)
    cv.line([(64, 98), (88, 99)], LAV[3])
    for t in np.linspace(.1, .9, 6):                                          # NOVO: flaps
        a_ = cv.pt((52 + 50 * t, 97 + 6 * t)); n.line([a_, (a_[0] + 3, a_[1] - 9)], LAV[3])
    # motor traseiro
    nac = cv.mask(lambda d: d.rounded_rectangle([132, 62, 156, 86], radius=6, fill=255))
    cv.banded(nac, [METAL[0], METAL[1], METAL[2], METAL[3], METAL[4]], cuts=[.12, .35, .6, .85])
    cv.fill(cv.emask(152, 74, 4, 10), METAL[4]); cv.fill(cv.emask(153, 74, 2.5, 7), CAV[2])
    cv.rect(138, 66, 10, 2, OR); cv.line([(136, 72), (136, 84)], METAL[4])
    for yy in range(66, 86, 3):                                               # NOVO: aletas do bocal
        a_ = cv.pt((150, yy)); n.rect(a_[0], a_[1], 3, 1, METAL[4])
    cv.rect(46, 30, 1.2, 26, METAL[2]); cv.rect(44, 40, 6, 1, METAL[2]); cv.rect(45, 27, 3, 3, "#ff5a4a"); cv.px(45, 27, "#ffb0a0")
    sand_pile(cv, 24, 90, 20, 6, 3)
    sand_pile(cv, 126, 96, 18, 5, 4)
    # sucata + poltronas soltas + BAGAGEM dos colonos espalhada (NOVO)
    cv.rect(100, 100, 12, 6, METAL[4]); cv.rect(100, 100, 12, 2, METAL[1]); cv.rect(124, 104, 10, 5, LAV[3]); cv.rect(124, 104, 10, 2, LAV[1])
    for (x, y, w_, h_, c0, c1) in ((84, 96, 7, 5, "#c98a56", "#8a4e34"), (112, 108, 6, 4, "#7f89ad", "#4b5273"), (66, 110, 6, 4, "#b0663f", "#5e3526"),
                                   (140, 98, 7, 5, "#e3d9c3", "#8e7f73")):
        a_ = cv.pt((x, y)); ww, hh_ = round(w_ * k), round(h_ * k)
        n.rect(a_[0], a_[1], ww, hh_, c1); n.rect(a_[0], a_[1], ww, 3, c0); n.rect(a_[0] + ww // 2 - 2, a_[1] - 2, 5, 2, "#3b3f46")   # alça
        n.rect(a_[0] + 2, a_[1] + hh_ // 2, ww - 4, 1, c0)
    for (x, y) in ((56, 104), (106, 96)):                                     # poltrona tombada
        a_ = cv.pt((x, y)); n.rect(a_[0], a_[1], 10, 6, LAV[3]); n.rect(a_[0], a_[1] - 6, 4, 7, LAV[2]); n.rect(a_[0], a_[1], 10, 2, LAV[1])
    scatter(cv, [(4, 108), (36, 108), (54, 110), (84, 112), (146, 108), (152, 100), (6, 92), (70, 112)], 11)
    cv.outline()
    cv.meta = dict(LINER)
    return cv


# =====================================================================================================================
def main():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in (("cargo", cargo), ("module", module), ("probe", probe), ("robot", robot), ("liner", liner)):
        c = fn()
        c.check()
        assert c.image().size == tuple(c.meta["sprite"]), (name, c.image().size)
        c.image().save(PEND / f"wreck_{name}.png")
        out[name] = c.meta
        print(name, c.meta)
    for name, fn in (("cargo", cargo), ("module", module), ("probe", probe)):   # rodada 2: correções (arquivo à parte)
        c = fn(r2=True)
        c.check()
        c.image().save(PEND / f"wreck_{name}_r2.png")
    return out


if __name__ == "__main__":
    main()
