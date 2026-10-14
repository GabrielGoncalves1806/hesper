#!/usr/bin/env python3
"""Máquinas do "freela" (sessão experimental) portadas pro repo, AUTOCONTIDAS: só dependem do `r3d.py` daqui.

O dono aprovou as máquinas como estão, então isto NÃO redesenha: é o código do freela
(~/Desktop/hesper_sprites_experimento/gerador/machines3d.py + os pedaços 2D de machines.py/objects.py que a cápsula, o
terminal e o gerador eólico usam), trazido pra cá sem mudar nenhuma linha de desenho. O que mudou é só o plumbing
(imports, o Canvas, onde salva).

    python3 tools/sprites/machines_r3d.py            # gera em reports/design/maquinas_r3d/pendentes/
    python3 tools/sprites/machines_r3d.py --check    # gera e compara pixel a pixel com os PNGs do freela (Desktop)

Saída (reports/design/maquinas_r3d/pendentes/):
    *.png          o contrato: mesmo nome, tamanho e âncora do assets/sprites/ (drop-in)
    anim/          tiras que só o freela anima (o jogo ainda não recorta): anim_machine_*, anim_solar_panel, ...
    eolico/        gerador eólico (wind_turbine, anim_wind_turbine, icon_wind): pronto, FORA do jogo por enquanto
Nada daqui vai pra assets/ sem o ok do dono.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from r3d import SA, Pal, Scene  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "reports" / "design" / "maquinas_r3d" / "pendentes"
FREELA = Path.home() / "Desktop" / "hesper_sprites_experimento"

# ---- paleta (cópia do common.py / machines.py do freela) ---------------------------------------------------------
OUTLINE = "#1b1630"
ORANGE, ORANGE_D, ORANGE_L = "#e2733a", "#a9482a", "#f4a06a"
GOLD, GOLD_D, GOLD_L = "#f2c46d", "#b8823c", "#fff0b8"
CYAN, CYAN_D, CYAN_L = "#59d0e6", "#2b8fb3", "#c8f6ff"
OK, ALERT = "#7fd67a", "#ff6a55"
WHITE = ["#fbf8f1", "#e6e1dc", "#c3bdc6", "#8f88a0", "#5c5570"]
METAL = ["#a7a3b8", "#7d7892", "#58536b", "#3a3549", "#26222f"]
BEIGE = ["#fdf8ec", "#efe6d4", "#d6c9b4", "#a99a8c", "#6f6070"]   # brilho, base, meio, sombra, fundo
GLASS = "#1d2b3a"
ICE = ["#e9fbff", "#a6ecff", "#6cc6e6", "#3d8fb8"]
WATER = ["#9fe0f5", "#4aa8d8", "#2f7fb3", "#1f5a85"]
HEAT = ["#fff4cc", "#ffd27a", "#ff9a3d", "#e0602a", "#8a3420"]
SOLAR = ["#9cc0f0", "#4f78c8", "#2d4f9e", "#1d2f66", "#141f45"]
WIND_TOP, WIND_BOT = 7, 49


def rgb(c):
    if isinstance(c, tuple):
        return c if len(c) == 4 else (*c, 255)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


# ---- Canvas (o do freela, só o que as máquinas usam) -------------------------------------------------------------
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def px(self, x, y, c, wrap=False):
        if wrap:
            x %= self.w
            y %= self.h
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = rgb(c)

    def get(self, x, y, wrap=False):
        if wrap:
            x %= self.w
            y %= self.h
        if 0 <= x < self.w and 0 <= y < self.h:
            return tuple(int(v) for v in self.a[y, x])
        return (0, 0, 0, 0)

    def solid(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h and self.a[y, x, 3] == 255

    def rect(self, x, y, w, h, c, wrap=False):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.px(xx, yy, c, wrap)

    def hline(self, x, y, w, c, wrap=False):
        self.rect(x, y, w, 1, c, wrap)

    def vline(self, x, y, h, c, wrap=False):
        self.rect(x, y, 1, h, c, wrap)

    def draw_map(self, rows, pal, ox=0, oy=0):
        w = len(rows[0])
        for y, row in enumerate(rows):
            assert len(row) == w, f"linha {y} com {len(row)} colunas (esperado {w}): {row!r}"
            for x, ch in enumerate(row):
                if ch in (".", " "):
                    continue
                self.px(x + ox, y + oy, pal[ch])

    def blit(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                if other.a[y, x, 3] == 255:
                    self.px(x + ox, y + oy, tuple(int(v) for v in other.a[y, x]))

    def outline(self, c=OUTLINE):
        sol = self.a[:, :, 3] == 255
        add = np.zeros_like(sol)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sh = np.zeros_like(sol)
            ys = slice(max(dy, 0), self.h + min(dy, 0))
            yd = slice(max(-dy, 0), self.h + min(-dy, 0))
            xs = slice(max(dx, 0), self.w + min(dx, 0))
            xd = slice(max(-dx, 0), self.w + min(-dx, 0))
            sh[yd, xd] = sol[ys, xs]
            add |= sh
        add &= ~sol
        self.a[add] = rgb(c)

    def copy(self):
        c = Canvas(self.w, self.h)
        c.a = self.a.copy()
        return c

    def save(self, path):
        al = np.unique(self.a[:, :, 3])
        assert set(al.tolist()) <= {0, 255}, f"{path}: alpha fora de 0/255: {al}"
        self.a[self.a[:, :, 3] == 0] = 0
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(self.a).save(path)


def strip(frames):
    w, h = frames[0].w, frames[0].h
    s = Canvas(w * len(frames), h)
    for i, f in enumerate(frames):
        s.blit(f, i * w, 0)
    return s


def ellipse_mask(w, h, cx, cy, rx, ry):
    yy, xx = np.mgrid[0:h, 0:w]
    return ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1.0


def render(sc):
    """Renderiza a cena do r3d e devolve no Canvas do freela (com solid/rect/etc. pros retoques de 2D)."""
    cv = sc.render()
    out = Canvas(cv.w, cv.h)
    out.a = cv.a.copy()
    return out


# =====================================================================================================================
# Peças 2D do freela (machines.py / objects.py): usadas pelo terminal, pela cápsula e pelo gerador eólico
# =====================================================================================================================

def hull(cv, x, y, w, h, top, t=BEIGE, cut=2):
    """Casco em 3/4: tampo de `top` px + frente. Cantos do tampo chanfrados em `cut`."""
    for j in range(top):
        c = cut - j if j < cut else 0
        cv.rect(x + c, y + j, w - 2 * c, 1, t[0] if j < top - 1 else t[1])
    fy = y + top
    for xx in range(x, x + w):
        i = xx - x
        col = t[1] if i == 0 else t[3] if i >= w - 2 else t[2] if i >= w - 5 else t[1]
        if i == 1 or i == 2:
            col = t[0]
        cv.rect(xx, fy, 1, h - top, col)
    cv.rect(x, y + h - 1, w, 1, t[3])
    cv.hline(x, fy, w, t[2])                         # quina do tampo com a frente
    return fy


def band(cv, x, y, w, h=2, c=(ORANGE_L, ORANGE, ORANGE_D)):
    """Faixa horizontal na frente do casco (claro à esquerda, escuro nas 2 últimas colunas)."""
    for xx in range(x, x + w):
        i = xx - x
        cv.rect(xx, y, 1, h, c[0] if 1 <= i <= 2 else c[2] if i >= w - 2 else c[1])


def foot(cv, x, y, w, h=6, bolts=ORANGE):
    """Base de metal escuro em 3/4 (tampo 2 px) com parafusos."""
    cv.rect(x + 1, y, w - 2, 2, METAL[1])
    cv.rect(x, y + 2, w, h - 2, METAL[2])
    cv.rect(x + w - 3, y + 2, 3, h - 2, METAL[3])
    cv.rect(x, y + h - 1, w, 1, METAL[3])
    for bx in range(x + 3, x + w - 3, 6):
        cv.px(bx, y + 3, bolts)


def label(cv, x, y):
    """Plaquinha de aviso (triângulo laranja)."""
    cv.rect(x, y, 5, 4, BEIGE[0])
    cv.px(x + 2, y, ORANGE)
    cv.hline(x + 1, y + 1, 3, ORANGE)
    cv.hline(x, y + 2, 5, ORANGE)
    cv.px(x + 2, y + 1, OUTLINE)


def finish(cv):
    cv.outline()
    return cv


def anim(fn, n=4):
    return strip([fn(f) for f in range(n)])


def terminal(f):
    cv = Canvas(32, 32)
    cv.rect(4, 7, 24, 21, BEIGE[1])
    cv.rect(4, 7, 24, 2, BEIGE[0])
    cv.rect(4, 7, 1, 21, BEIGE[0])
    cv.rect(26, 7, 2, 21, BEIGE[3])
    cv.hline(4, 27, 24, BEIGE[3])
    cv.rect(7, 10, 17, 11, METAL[3])
    cv.rect(8, 11, 15, 9, "#102018")
    lines = [(9, 12, 9), (9, 14, 12), (9, 16, 6), (9, 18, 10)]
    for i, (x, y, w) in enumerate(lines):
        if i <= f:                                     # texto "digitando" linha a linha
            ww = w if i < f else max(2, w * 2 // 3)
            cv.hline(x, y, ww, OK if i % 2 == 0 else "#4f9a4c")
    cur = lines[min(f, 3)]
    cv.px(cur[0] + (cur[2] if f < 3 else cur[2]) + 1, cur[1], "#d8ffd0" if f % 2 == 0 else "#102018")
    band(cv, 4, 23, 24)
    cv.px(7, 25, OK if f % 2 == 0 else "#2f5a2c")
    cv.px(9, 25, ORANGE)
    for x in (5, 25):                                  # parafusos na rocha
        cv.px(x, 9, METAL[2])
    return finish(cv)


def pod_anim(base, f):
    cv = base.copy()
    on = f % 2 == 0
    cv.rect(45, 3, 4, 3, ALERT if on else "#7a2a24")
    if on:
        cv.px(45, 3, "#ffb3a8")
    cv.px(43, 48, OK if f < 2 else "#2f5a2c")
    cv.px(45, 48, CYAN if f % 2 else CYAN_D)
    return cv


def to_beige(cv):
    """Troca o branco frio (WHITE) pelo bege da família, tom a tom. Usado na cápsula do objects.py."""
    out = cv.copy()
    for w, b in zip(WHITE, BEIGE):
        src = np.array(rgb(w)[:3], np.uint8)
        hit = (out.a[:, :, :3] == src).all(axis=2) & (out.a[:, :, 3] == 255)
        out.a[hit] = rgb(b)
    return out


def _blade_samples(f, k):
    """Pontos (x, y, profundidade) da pá k no quadro f. Formato de fuso: raio 0 nas pontas, 11 no meio."""
    out = []
    phase = math.radians(f * 15 + k * 120)
    for i in range(400):
        t = i / 399
        r = 1.5 + 10.5 * math.sin(math.pi * t) ** 0.85
        th = phase + math.radians(110) * (t - 0.5)            # torção helicoidal
        out.append((15.5 + r * math.sin(th), WIND_TOP + (WIND_BOT - WIND_TOP) * t, math.cos(th)))
    return out


def _layer(cv, draw):
    tmp = Canvas(cv.w, cv.h)
    draw(tmp)
    tmp.outline()
    cv.blit(tmp, 0, 0)


def wind_turbine(f):
    cv = Canvas(32, 64)
    blades = [_blade_samples(f, k) for k in range(3)]

    def blade_part(c, front):
        for pts in blades:
            for (x, y, d) in pts:
                if (d >= 0) != front:
                    continue
                xi, yi = int(x), int(y)
                if front:
                    c.px(xi, yi, BEIGE[0] if d > 0.6 else BEIGE[1])
                    c.px(xi + 1, yi, BEIGE[2] if d > 0.6 else BEIGE[3])
                else:
                    c.px(xi, yi, BEIGE[3])
                    c.px(xi + 1, yi, BEIGE[4])

    # base: pé de metal + caixa do gerador
    def base(c):
        foot(c, 5, 57, 22, 6)
        hull(c, 9, 46, 14, 12, 4)
        band(c, 9, 51, 14, 2)
        c.rect(11, 54, 5, 2, METAL[3])
        c.px(12, 54, OK if f % 4 < 2 else "#2f5a2c")
        c.px(14, 54, CYAN if f % 2 == 0 else CYAN_D)
        label(c, 17, 54)
    _layer(cv, base)
    _layer(cv, lambda c: blade_part(c, False))              # metade de trás das pás
    # anel de baixo (atrás do mastro)
    m = ellipse_mask(32, 64, 16, WIND_BOT + 1, 6, 1.6)
    mi = ellipse_mask(32, 64, 16, WIND_BOT + 1, 4.6, 0.9)
    _layer(cv, lambda c: [c.px(x, y, METAL[1] if y <= WIND_BOT else METAL[2]) for y, x in zip(*np.nonzero(m & ~mi))])

    def mast(c):
        c.rect(15, WIND_TOP - 1, 2, WIND_BOT - WIND_TOP + 2, "#d7d9e3")   # mastro prateado
        c.vline(16, WIND_TOP - 1, WIND_BOT - WIND_TOP + 2, "#8f92a6")
        c.rect(14, 28, 4, 2, METAL[2])                       # cubo do meio
        c.hline(14, 28, 4, ORANGE)
    _layer(cv, mast)
    _layer(cv, lambda c: blade_part(c, True))               # metade da frente
    # escoras do meio até as pás da frente (1 px, sem contorno)
    for pts in blades:
        x, y, d = pts[200]
        if d > -0.2:
            n = abs(int(x) - 16)
            for i in range(1, n):
                xx = 16 + (i if x > 16 else -i)
                if not cv.solid(xx, 29) or cv.get(xx, 29)[:3] == (0x1b, 0x16, 0x30):
                    cv.px(xx, 29, METAL[2])
    # tampa de cima + antena com farol
    def cap(c):
        mc = ellipse_mask(32, 64, 16, WIND_TOP, 5, 1.5)
        for y, x in zip(*np.nonzero(mc)):
            c.px(x, y, METAL[0] if y < WIND_TOP else METAL[1])
        c.vline(16, 1, WIND_TOP - 1, METAL[1])
    _layer(cv, cap)
    cv.px(16, 0, ALERT if f % 4 < 2 else "#7a2a24")
    # filete de vento passando (sem contorno)
    wx = (f * 5) % 40 - 6
    for i in range(4):
        if 0 <= wx + i < 32 and not cv.solid(wx + i, 18):
            cv.px(wx + i, 18, "#d9d3dc" if i < 2 else "#a79fb2")
    return cv


def icon_wind():
    """Ícone 16×16 desenhado à mão: mastro, 2 pás em fuso (uma clara na frente, uma escura atrás) e a base."""
    rows = [
        ".......R........",
        "......kMk.......",
        ".....b.M.W......",
        "....b..M..W.....",
        "....b..M..W.....",
        "....b..MW.......",
        ".....b.W........",
        "......WM.b......",
        ".....W.M..b.....",
        "....W..M..b.....",
        "....W..M..b.....",
        ".....W.M.b......",
        "......WMb.......",
        ".....BBOBB......",
        "....KKKKKKK.....",
        "................",
    ]
    pal = {"R": ALERT, "k": METAL[1], "M": "#c3c6d4", "W": BEIGE[0], "b": BEIGE[3], "B": BEIGE[1], "O": ORANGE,
           "K": METAL[2]}
    cv = Canvas(16, 16)
    cv.draw_map(rows, pal)
    cv.outline()
    return cv


def cyl_col(u, tones):
    """u 0..1 da esquerda pra direita. tones: [brilho, claro, médio, sombra, fundo]."""
    if u < 0.10:
        return tones[1]
    if u < 0.42:
        return tones[0]
    if u < 0.70:
        return tones[1]
    if u < 0.88:
        return tones[2]
    return tones[3]


def cylinder(cv, x0, w, ytop, ybot, tones, cap=True, ry=None):
    """Cilindro vertical: tampo elíptico + corpo com faixas. Retorna (cx, rx, ry)."""
    rx = w / 2
    cx = x0 + rx
    ry = ry or max(2, round(w * 0.22))
    for x in range(x0, x0 + w):
        u = (x + 0.5 - x0) / w
        arc = math.sqrt(max(0.0, 1 - ((x + 0.5 - cx) / rx) ** 2))
        yb = ybot + round(ry * arc)
        for y in range(ytop, yb):
            cv.px(x, y, cyl_col(u, tones))
    if cap:
        m = ellipse_mask(cv.w, cv.h, cx, ytop, rx, ry)
        for y, x in zip(*np.nonzero(m)):
            dx, dy = (x + 0.5 - cx) / rx, (y + 0.5 - ytop) / ry
            cv.px(x, y, tones[0] if dx + dy < 0.2 else tones[1])
        # aro do tampo
        for y, x in zip(*np.nonzero(m)):
            if not (y + 1 < cv.h and m[y + 1, x]):
                cv.px(x, y, tones[2])
    return cx, rx, ry


def ring(cv, cx, rx, ry, y0, thick, col_l, col, col_d):
    """Faixa horizontal que acompanha a curva do cilindro (arco pra baixo na frente)."""
    for x in range(int(cx - rx), int(cx + rx)):
        u = (x + 0.5 - (cx - rx)) / (2 * rx)
        arc = math.sqrt(max(0.0, 1 - ((x + 0.5 - cx) / rx) ** 2))
        y = y0 + round(ry * arc)
        c = col_l if 0.1 < u < 0.42 else col if u < 0.8 else col_d
        for k in range(thick):
            cv.px(x, y + k, c)


def make_pod():
    W, H = 64, 72
    cv = Canvas(W, H)
    # pernas de pouso (atrás do corpo)
    for (xa, xb, d) in ((15, 4, -1), (48, 59, 1)):
        for i in range(17):
            x = xa + round((xb - xa) * i / 16)
            y = 50 + i
            cv.rect(x - 1, y, 3, 1, METAL[1] if d < 0 else METAL[2])
        cv.rect(xb - 3, 66, 7, 2, METAL[2])
        cv.rect(xb - 3, 68, 7, 1, METAL[3])
    # corpo
    cx, rx, ry = cylinder(cv, 10, 44, 24, 54, WHITE, ry=9)
    # escudo térmico chamuscado embaixo
    for x in range(10, 54):
        arc = math.sqrt(max(0.0, 1 - ((x + 0.5 - cx) / rx) ** 2))
        yb = 54 + round(ry * arc)
        for y in range(yb - 4, yb):
            u = (x - 10) / 44
            cv.px(x, y, METAL[2] if u < 0.75 else METAL[3])
        cv.px(x, yb - 5, METAL[1])
    ring(cv, cx, rx, ry, 30, 2, ORANGE_L, ORANGE, ORANGE_D)
    ring(cv, cx, rx, ry, 45, 1, WHITE[2], WHITE[2], WHITE[3])
    # escotilha no topo
    m = ellipse_mask(W, H, cx - 3, 22, 9, 4)
    for y, x in zip(*np.nonzero(m)):
        cv.px(x, y, METAL[1])
    m2 = ellipse_mask(W, H, cx - 3, 22, 6, 2.5)
    for y, x in zip(*np.nonzero(m2)):
        cv.px(x, y, METAL[2] if y > 21 else METAL[0])
    # porta com moldura laranja + janelinha
    cv.rect(26, 35, 13, 22, ORANGE)
    cv.rect(27, 36, 11, 21, METAL[3])
    cv.rect(28, 37, 9, 20, METAL[2])
    cv.rect(32, 37, 1, 20, METAL[3])
    cv.rect(29, 39, 3, 3, CYAN)
    cv.px(29, 39, CYAN_L)
    cv.px(35, 47, GOLD)
    # degraus
    cv.rect(25, 59, 15, 2, METAL[1])
    cv.rect(25, 61, 15, 1, METAL[3])
    cv.rect(23, 62, 19, 2, METAL[1])
    cv.rect(23, 64, 19, 1, METAL[3])
    # escotilhas redondas (vigias)
    for (wx, wy) in ((17, 38), (45, 38)):
        m = ellipse_mask(W, H, wx, wy, 3.6, 3.6)
        for y, x in zip(*np.nonzero(m)):
            cv.px(x, y, METAL[2])
        m = ellipse_mask(W, H, wx, wy, 2.4, 2.4)
        for y, x in zip(*np.nonzero(m)):
            cv.px(x, y, CYAN if x >= wx - 0.5 else CYAN_L)
        cv.px(int(wx) - 1, int(wy) - 1, "#ffffff")
    # LED de status e placa
    cv.rect(42, 47, 6, 3, METAL[3])
    cv.px(43, 48, OK)
    cv.px(45, 48, CYAN)
    # antena com farol vermelho
    cv.rect(46, 6, 1, 16, METAL[1])
    cv.rect(47, 6, 1, 16, METAL[3])
    cv.rect(45, 3, 4, 3, ALERT)
    cv.px(45, 3, "#ffb3a8")
    cv.rect(44, 20, 6, 3, METAL[2])
    # aleta de painel solar no topo-esquerda
    cv.rect(12, 14, 12, 6, "#2d4f9e")
    for gx in range(12, 24, 3):
        cv.rect(gx, 14, 1, 6, "#1d2f66")
    cv.rect(12, 14, 12, 1, "#6f95dc")
    cv.rect(17, 20, 2, 4, METAL[2])
    cv.outline()
    return cv



# =====================================================================================================================
# Máquinas em r3d (o machines3d.py do freela, sem mudar o desenho)
# =====================================================================================================================
P_BEIGE = Pal(BEIGE)
P_METAL = Pal(METAL)
P_DARK = Pal(["#4a4458", "#3a3549", "#2e2a3a", "#242030", "#1b1726"])
P_ORANGE = Pal(["#ffd0a8", ORANGE_L, ORANGE, ORANGE_D, "#6e2a1c"])
P_GOLD = Pal(["#fff6d6", GOLD_L, GOLD, GOLD_D, "#6e4a1e"])
P_GLASS = Pal(["#ffffff", CYAN_L, CYAN, CYAN_D, "#1d4a66"])
P_STEEL = Pal(["#ffffff", "#e3e5ee", "#b9bccb", "#8f92a6", "#5e6176"])
P_SCREEN = Pal(["#1d2b3a"] * 5, emit=True, emit_tone=0)
P_ICE = Pal([ICE[0], ICE[1], ICE[1], ICE[2], ICE[3]])
P_WATER = Pal(["#d8f6ff", WATER[0], WATER[1], WATER[2], WATER[3]])
P_SOLAR = Pal(SOLAR)
FRONT = 1.5 * math.pi            # ângulo do cilindro que encara a câmera (−Y)


def heat_pal(level):
    """Paleta incandescente que pulsa: level 0..3 desloca os tons (emissiva, não liga pra luz)."""
    seq = [HEAT[0], HEAT[1], HEAT[2], HEAT[3], HEAT[4]]
    return Pal(seq, emit=True, emit_tone=min(4, level))


def ang_dist(a, b):
    d = (a - b) % (2 * math.pi)
    return np.minimum(d, 2 * math.pi - d)


def scene(w, h, front_y):
    """Cena com o chão posicionado pra borda da frente (Y=front_y, Z=0) cair na penúltima linha."""
    return Scene(w, h, ground=h - 2 - (-front_y) * SA)


def fan(sc, cx, cy, z, r, f, n=3, step=30):
    """Ventoinha em 3D: aro escuro + n pás finas girando em volta do eixo Z (step graus por quadro)."""
    sc.disc(cx, cy, z, r, P_DARK)
    for k in range(n):
        a = math.radians(f * step + k * 360 / n)
        sc.obox((cx + math.cos(a) * r * 0.45, cy + math.sin(a) * r * 0.45, z + 0.6), (r * 0.42, 0.9, 0.3), P_STEEL,
                rot_z=a)
    sc.cyl(cx, cy, 1.2, z, z + 1.2, P_ORANGE)


def base_v10(sc, w, d, h=5, pal=P_METAL, bolts=ORANGE):
    """A base do freela (v1.0): plinto reto com a fileira de parafusos. Fica só pra referência do antes."""
    sc.box((-w, w), (-d, d), (0, h), pal)
    for x in range(-w + 3, w - 2, 6):
        sc.dot(x, -d - 0.1, h * 0.5, bolts)


# ---------------------------------------------------------------------------
# v1.1 · SAPATA padrão: UMA peça só, igual em todas as máquinas. Só a meia-largura acompanha a máquina; altura,
# profundidade, cores e detalhes são sempre os mesmos. Os corpos são assentados em cima dela (Scene.dz).
# ---------------------------------------------------------------------------
SAP_H = 5.0                      # altura da sapata (o corpo começa aqui)
SAP_D = 13.0                     # meia-profundidade (1 tile)
SAPATA = "B"                     # estilo escolhido (as opções A/B/C aparecem no report)
P_SILVER = Pal(["#d9dde6", "#a9b0be", "#8c93a3", "#636a7a", "#414553"])     # a prata do baú azul aprovado
P_PLATE = Pal(["#c9c4d6", "#a7a3b8", "#8a85a0", "#5e596f", "#3a3549"])       # chapa do tampo, um tom acima do METAL
P_LED_OK = Pal([OK] * 5, emit=True, emit_tone=0)


def _rim(sc, w, d, z):
    """Friso prata (a prata do baú azul) só na quina da frente do tampo: 1 px claro que desenha a borda."""
    sc.rbox((0, -d + 0.45, z), (w - 0.9, 0.45, 0.45), 0.4, P_SILVER)


def _sap_a(sc, w):
    """A · chanfrada: placa grossa de cantos bem arredondados, friso prata na quina e um painel escuro rebaixado
    no meio da frente (largura fixa) com 2 respiros e o LED. Pezinhos escuros nos 4 cantos."""
    d = SAP_D
    for sx in (-1, 1):
        for sy in (-1, 1):
            sc.rbox((sx * (w - 2.4), sy * (d - 2.4), 0.5), (2.0, 2.0, 0.5), 0.4, P_DARK)
    def paint(L, N):
        out = np.zeros(len(L), int)
        fr = (N[:, 1] < -0.9) & (abs(L[:, 0]) < 6.2) & (abs(L[:, 2]) < 1.3)
        out[fr] = 1
        out[fr & (abs(L[:, 0]) > 1.4) & (abs(L[:, 0]) < 5.0) & (abs(L[:, 2]) < 0.45)] = 2
        return out
    sc.rbox((0, 0, 2.95), (w, d, 2.05), 1.9, P_METAL, paint=paint, extra=(P_DARK, Pal(["#5e596f"] * 5)))
    _rim(sc, w, d, 4.6)
    sc.dot(-0.2, -d - 0.2, 3.0, OK, always=True)


def _sap_b(sc, w):
    """B · sapatas: a placa de cantos arredondados levantada em 4 sapatas laranja com solinha escura, friso prata
    na quina e uma plaqueta prata fixa no meio da frente, com fenda escura e LED verde."""
    d = SAP_D
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (w - 3.2), sy * (d - 2.8)
            sc.rbox((cx, cy, 0.45), (3.4, 2.8, 0.45), 0.35, P_DARK)
            sc.rbox((cx, cy, 1.5), (2.8, 2.3, 0.9), 0.6, P_ORANGE)
    sc.rbox((0, 0, 3.55), (w, d, 1.45), 1.3, P_METAL)
    _rim(sc, w, d, 4.65)
    def plate(L, N):
        return np.where((N[:, 1] < -0.9) & (L[:, 0] > -1.4) & (L[:, 0] < 3.4) & (abs(L[:, 2]) < 0.45), 1, 0)
    sc.rbox((0, -d - 0.3, 3.4), (5.2, 0.5, 1.2), 0.4, P_SILVER, paint=plate, extra=(P_DARK,))
    sc.dot(-3.6, -d - 1.0, 3.5, OK, always=True)


def _sap_c(sc, w):
    """C · degrau: soco escuro largo embaixo com listras de advertência nos cantos da frente e a placa metálica em
    cima, recuada, com friso prata e LED no meio."""
    d = SAP_D
    def hz(L, N):
        fr = N[:, 1] < -0.9
        x = L[:, 0]
        k = (np.floor(x + L[:, 2] + 100) % 3) < 1.5
        return np.where(fr & (abs(x) > w - 6.5) & k, 1, 0)
    sc.rbox((0, 0, 1.2), (w + 0.3, d + 0.3, 1.2), 0.7, P_DARK, paint=hz, extra=(P_ORANGE,))
    sc.rbox((0, 0.6, 3.6), (w - 1.3, d - 1.0, 1.4), 1.4, P_METAL)
    _rim(sc, w - 1.3, d - 0.4, 4.6)
    sc.dot(0, -d - 0.6, 1.3, OK, always=True)


SAPATAS = {"A": _sap_a, "B": _sap_b, "C": _sap_c}


def sapata(sc, w, style=None, at=(0.0, 0.0)):
    """A sapata padrão de TODAS as máquinas. w = meia-largura (16 no nv.1, 19 no nv.2, 12 no painel, 9 na drill).
    at = onde fica o centro dela no chão (a drill põe ao lado do veio); a peça é sempre a mesma."""
    keep = (sc.dx, sc.dy)
    sc.dx, sc.dy = keep[0] + at[0], keep[1] + at[1]
    SAPATAS[style or SAPATA](sc, w)
    sc.dx, sc.dy = keep


def base(sc, w, d, h=5, pal=P_METAL, bolts=ORANGE):
    """Chamada antiga das máquinas: agora põe a sapata padrão e assenta o corpo nela (o corpo foi desenhado pra
    começar em Z = h; o dz faz ele começar em SAP_H, então o nv.2 desce 2 px). d, pal e bolts não importam mais:
    a sapata é sempre a mesma."""
    sapata(sc, w)
    sc.dz = SAP_H - h


def front_panel(sc, x0, x1, y, z0, z1, f, leds=2):
    """Painelzinho escuro saltado da frente (Y = y) com LEDs."""
    sc.box((x0, x1), (y - 1.2, y), (z0, z1), P_DARK)
    sc.dot(x0 + 1, y - 1.3, z1 - 1.5, OK if f < 2 else "#2f5a2c", always=True)
    if leds > 1:
        sc.dot(x0 + 3, y - 1.3, z1 - 1.5, CYAN if f % 2 == 0 else CYAN_D, always=True)
    if leds > 2:
        sc.dot(x0 + 1, y - 1.3, z1 - 3.5, ORANGE, always=True)


def warn(sc, x, y, z):
    """Plaquinha de aviso (triângulo laranja) colada na frente."""
    for (dx, dz) in ((0, 2), (-1, 1), (0, 1), (1, 1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0)):
        sc.dot(x + dx, y - 0.2, z + dz, ORANGE)


# ---------------------------------------------------------------------------
# Gerador de O₂: tanque cilíndrico, visor de bolhas, ventoinha girando no tampo
# ---------------------------------------------------------------------------
def _o2_paint(win_c, win_z, bands, gold_bands=()):
    def paint(th, z, cap):
        if np.all(cap):                                  # tampa (o motor manda um vetor booleano)
            return np.zeros(len(th), int)
        out = np.zeros(len(th), int)
        for (a, b) in bands:
            out[(z > a) & (z < b)] = 1
        for (a, b) in gold_bands:
            out[(z > a) & (z < b)] = 4
        d = ang_dist(th, win_c)
        frame = (d < 0.72) & (z > win_z[0] - 1.5) & (z < win_z[1] + 1.5)
        out[frame] = 2
        out[(d < 0.55) & (z > win_z[0]) & (z < win_z[1])] = 3
        return out
    return paint


def o2(f, tier=1):
    if tier == 1:
        sc = scene(40, 56, -13)
        base(sc, 16, 13)
        sc.cyl(0, 0, 12, 5, 40, P_BEIGE, paint=_o2_paint(FRONT + 0.3, (15, 30), [(10, 12.5), (33, 35.5)]),
               extra=(P_ORANGE, P_METAL, P_GLASS))
        fan(sc, 0, 0, 40.2, 8, f)
        sc.cyl(8, 6, 2, 40, 49, P_BEIGE, paint=lambda t, z, c: np.where((z > 44) & (z < 45.5) & ~c, 1, 0),
               extra=(P_ORANGE,))
        sc.cyl(13.8, -3, 1.6, 5, 30, P_METAL)                       # cano
        sc.box((12.2, 15.6), (-6, -2), (17, 20), P_ORANGE)           # válvula
        sc.box((-11, -6), (-13, -11.5), (18, 24), P_DARK)             # painel à esquerda do visor
        sc.dot(-10, -13.6, 22.5, OK if f < 2 else "#2f5a2c", always=True)
        sc.dot(-8, -13.6, 22.5, CYAN if f % 2 == 0 else CYAN_D, always=True)
        for i in range(4):                                           # bolhas subindo
            z = 16 + (f * 3 + i * 4) % 13
            a = FRONT + 0.3 + (-0.3 + 0.2 * i)
            sc.dot(12.2 * math.cos(a), 12.2 * math.sin(a), z, "#ffffff" if i % 2 else CYAN_L)
        return render(sc)
    sc = scene(40, 64, -13)
    base(sc, 19, 13, 7, bolts=GOLD)
    for x0 in (-14.5, 14.5):                                         # tanques laterais
        sc.cyl(x0, 3, 4, 7, 36, P_GLASS, paint=lambda t, z, c: np.where(((z > 12) & (z < 14)) | ((z > 30) & (z < 32)), 1, 0),
               extra=(P_GOLD,))
    sc.cyl(0, 0, 11, 7, 49, P_BEIGE, paint=_o2_paint(FRONT, (22, 38), [(17, 18.5)], [(11, 13.5), (42, 44.5)]),
           extra=(P_ORANGE, P_GOLD, P_GLASS, P_GOLD))
    fan(sc, 0, 0, 49.2, 8.5, f, n=4, step=22)
    sc.box((-4, 4), (-12.5, -11), (12, 16), P_DARK)
    for k, c in enumerate((OK if f < 2 else "#2f5a2c", CYAN if f % 2 == 0 else CYAN_D, ORANGE)):
        sc.dot(-2 + k * 2, -12.6, 14.5, c, always=True)
    for i in range(5):
        z = 23 + (f * 3 + i * 3) % 14
        a = FRONT + (-0.4 + 0.2 * i)
        sc.dot(11.2 * math.cos(a), 11.2 * math.sin(a), z, "#ffffff" if i % 2 else CYAN_L)
    return render(sc)


# ---------------------------------------------------------------------------
# Aquecedor: caixa com grelha incandescente pulsando, chaminés soltando calor
# ---------------------------------------------------------------------------
HEATS = [heat_pal(i) for i in range(4)]


def _grille_paint(f, x0, x1, z0, rows, band_z, gold=False):
    """Pinta a FRENTE da caixa: faixa, grelha com fendas pulsando (cada fenda num tom), resto bege."""
    def paint(L, face):
        out = np.zeros(len(L), int)
        if face == 2:                                    # frente (−Y)
            x, z = L[:, 0], L[:, 2]
            out[(z > band_z) & (z < band_z + 2.4)] = 2 if gold else 1
            g = (x > x0) & (x < x1) & (z > z0) & (z < z0 + rows * 4)
            out[g] = 3
            for r in range(rows):
                slot = g & (z > z0 + r * 4 + 1) & (z < z0 + r * 4 + 3.2) & (x > x0 + 1) & (x < x1 - 1)
                out[slot] = 4 + (f + r) % 4
        elif face == 5:                                  # tampo: grade de respiro
            x, y = L[:, 0], L[:, 1]
            vent = (abs(x) < 9) & (abs(y) < 3)
            out[vent] = 3
            out[vent & ((np.floor(x) % 2) == 0)] = 8
        return out
    return paint


def _shimmer(sc, x, y, ztop, f):
    for i in range(3):
        z = ztop + 1 + (f * 2 + i * 3) % 8
        sc.dot(x + (1 if (f + i) % 2 else 0), y, z, HEAT[1] if i == 0 else HEAT[2], always=True)


def heater(f, tier=1):
    if tier == 1:
        sc = scene(40, 56, -13)
        base(sc, 16, 13)
        sc.cyl(-6, 4, 2.6, 36, 46, P_BEIGE, paint=lambda t, z, c: np.where((z > 41) & (z < 42.5) & ~c, 1, 0), extra=(P_ORANGE,))
        sc.cyl(7, 5, 2.2, 36, 43, P_BEIGE, paint=lambda t, z, c: np.where((z > 39) & (z < 40.5) & ~c, 1, 0), extra=(P_ORANGE,))
        sc.box((-13, 13), (-10, 10), (5, 36), P_BEIGE,
               paint=_grille_paint(f, -10, 5, -12, 5, 11), extra=(P_ORANGE, P_GOLD, P_DARK, *HEATS, P_METAL))
        front_panel(sc, 7, 11, -10, 14, 20, f, leds=1)
        warn(sc, 9, -10, 7.5)
        _shimmer(sc, -6, 4, 46, f)
        _shimmer(sc, 7, 5, 43, f + 2)
        return render(sc)
    sc = scene(40, 64, -13)
    base(sc, 19, 13, 7, bolts=GOLD)
    for xs in (-17, 13.5):                                           # radiadores laterais
        for z in range(10, 42, 3):
            sc.box((xs, xs + 3.5), (-7, 7), (z, z + 1.5), P_METAL)
    sc.cyl(-6, 4, 2.6, 46, 58, P_BEIGE, paint=lambda t, z, c: np.where((z > 52) & (z < 53.5) & ~c, 1, 0), extra=(P_GOLD,))
    sc.cyl(6, 4, 2.6, 46, 58, P_BEIGE, paint=lambda t, z, c: np.where((z > 52) & (z < 53.5) & ~c, 1, 0), extra=(P_GOLD,))
    sc.box((-13, 13), (-10, 10), (7, 46), P_BEIGE,
           paint=_grille_paint(f, -10, 10, -10, 6, 16, gold=True), extra=(P_ORANGE, P_GOLD, P_DARK, *HEATS, P_METAL))
    front_panel(sc, -10, -3, -10, 9, 13, f, leds=3)
    warn(sc, 7, -10, 9.5)
    _shimmer(sc, -6, 4, 58, f)
    _shimmer(sc, 6, 4, 58, f + 1)
    return render(sc)


# ---------------------------------------------------------------------------
# Derretedor: funil de gelo no tampo, tubo de vidro com água subindo e descendo, bica pingando
# ---------------------------------------------------------------------------
P_TUBE_EMPTY = Pal(["#3a5266", "#2a3e52", GLASS, "#141f2c", "#0e1620"])


def _tube(sc, x, y, z0, z1, r, level):
    sc.cyl(x, y, r, z0, z1, P_WATER, paint=lambda t, z, c: np.where(z > z0 + level, 1, 0), extra=(P_TUBE_EMPTY,))
    sc.cyl(x, y, r + 0.6, z1, z1 + 1.2, P_METAL)
    sc.cyl(x, y, r + 0.6, z0 - 1.2, z0, P_METAL, cap=False)


def _hopper(sc, cx, cy, z0, z1, r0, r1, cubes):
    sc.cyl(cx, cy, r0, z0, z1, P_METAL, r_top=r1, cap=False)
    sc.disc(cx, cy, z1 - 1.5, r1 - 0.8, P_DARK)
    for (x, y, s) in cubes:
        sc.box((x - s, x + s), (y - s, y + s), (z1 - 2, z1 - 2 + 2 * s), P_ICE)


def melter(f, tier=1):
    lv = [0, 1, 2, 1][f]
    if tier == 1:
        sc = scene(40, 56, -13)
        base(sc, 16, 13)
        sc.box((-12, 12), (-9, 9), (5, 28), P_BEIGE,
               paint=lambda L, face: np.where((face == 2) & (L[:, 2] > 6) & (L[:, 2] < 8.4), 1, 0), extra=(P_ORANGE,))
        _hopper(sc, 0, 1, 28, 37, 6, 11, [(-5, 1, 2), (0, 4, 2.2), (4, -1, 2), (-1, -3, 1.8), (6, 4, 1.6)])
        _tube(sc, -5, -10.5, 9, 24, 2.6, 7 + lv * 2)
        front_panel(sc, 3, 8, -9, 16, 21, f)
        warn(sc, 5, -9, 9)
        sc.hcyl(12, 16, -3, 15, 1.3, P_METAL)                         # bica
        sc.box((15, 17), (-4, -2), (11, 16), P_METAL)
        sc.dot(16, -3.2, 10 - f * 2, WATER[0], always=True)
        sc.dot(16, -3.2, 9 - f * 2, WATER[1], always=True)
        return render(sc)
    sc = scene(40, 64, -13)
    base(sc, 19, 13, 7, bolts=GOLD)
    sc.box((-13, 13), (-9, 9), (7, 34), P_BEIGE,
           paint=lambda L, face: np.where((face == 2) & (L[:, 2] > 9) & (L[:, 2] < 11.4), 1, 0), extra=(P_GOLD,))
    _hopper(sc, 0, 1, 34, 44, 7, 15, [(-8, 1, 2.2), (-3, 5, 2.4), (2, 1, 2.4), (7, 4, 2.2), (9, -2, 2), (-6, -4, 2),
                                      (1, -4, 2.2)])
    sc.disc(0, 1, 44.1, 15, P_GOLD, r_in=14)
    _tube(sc, -8, -10.5, 11, 30, 2.4, 9 + lv * 2)
    _tube(sc, -2, -10.5, 11, 30, 2.4, 13 - lv * 2)
    front_panel(sc, 4, 10, -9, 22, 28, f, leds=3)
    warn(sc, 7, -9, 14)
    sc.hcyl(13, 17, -3, 18, 1.4, P_METAL)
    sc.box((16, 18), (-4, -2), (13, 18), P_METAL)
    sc.dot(17, -3.2, 12 - f * 2, WATER[0], always=True)
    sc.dot(17, -3.2, 11 - f * 2, WATER[1], always=True)
    return render(sc)


# ---------------------------------------------------------------------------
# Drill automática 2×2 (64×80 por quadro, contrato). FILL_RECT (48, 47, 7, 12) fica livre e escuro.
# ---------------------------------------------------------------------------
FILL = (48, 47, 7, 12)


# (a drill de broca do freela v1.0 saiu: o PNG dela fica em reports/design/maquinas_r3d/v10/)


# ---------------------------------------------------------------------------
# Painel solar: placa inclinada em 3D, reflexo varrendo
# ---------------------------------------------------------------------------
P_SOLAR_HL = Pal(["#ffffff", "#d8e8ff", SOLAR[0], SOLAR[1], SOLAR[2]], emit=True, emit_tone=2)
P_CELL = Pal([SOLAR[1], SOLAR[2], SOLAR[2], SOLAR[3], SOLAR[4]])


def solar(f):
    """v1.1: o pé de metal virou a sapata padrão (meia-largura 12); o mastro sai dela."""
    sc = scene(32, 40, -SAP_D)
    sapata(sc, 12)
    sc.cyl(0, 0, 1.6, SAP_H, 20, P_BEIGE, paint=lambda t, z, c: np.where((z > 10) & (z < 11.5) & ~c, 1, 0), extra=(P_ORANGE,))
    sc.box((-3, 3), (-1.5, 1.5), (18, 21), P_METAL)
    g = [-26, -10, 6, 22][f]

    def paint(L, face):
        x, y = L[:, 0], L[:, 1]
        out = np.zeros(len(L), int)
        if face == 5:
            cell = (abs(x) < 13) & (abs(y) < 8.8)
            out[cell] = 1
            grid = cell & (((np.floor(x + 13) % 5) < 0.6) | ((np.floor(y + 8.8) % 4.5) < 0.7))
            out[grid] = 2
            glint = cell & ~grid & ((x + y * 0.9 - g) > 0) & ((x + y * 0.9 - g) < 3)
            out[glint] = 3
        return out
    sc.obox((0, -1, 22), (14, 10, 1.0), P_BEIGE, rot_x=0.12, paint=paint, extra=(P_CELL, P_DARK, P_SOLAR_HL))
    sc.dot(1.8, -1.7, 13, OK if f < 2 else "#2f5a2c", always=True)
    return render(sc)


# ---------------------------------------------------------------------------
# Baú (fechado / aberto)
# ---------------------------------------------------------------------------
def chest(opened=False):
    sc = scene(32, 40, -10)
    sc.box((-12, 12), (-10, 9), (0, 3), P_METAL)
    band = lambda L, face: np.where((face == 2) & (L[:, 2] > -1.2) & (L[:, 2] < 1.2), 1, 0)
    if not opened:
        sc.box((-11, 11), (-8, 8), (3, 15), P_BEIGE, paint=band, extra=(P_ORANGE,))
        sc.box((-11.5, 11.5), (-8.5, 8.5), (15, 20), P_BEIGE,
               paint=lambda L, face: np.where(L[:, 2] < -1.6, 1, 0), extra=(P_DARK,))
        sc.box((-2, 2), (-9.6, -8.5), (11, 17), P_METAL)
        sc.dot(0, -9.8, 15, OK, always=True)
        return render(sc)
    for (xr, yr) in (((-11, 11), (-8, -6.5)), ((-11, 11), (6.5, 8)), ((-11, -9.5), (-6.5, 6.5)), ((9.5, 11), (-6.5, 6.5))):
        sc.box(xr, yr, (3, 15), P_BEIGE, paint=band, extra=(P_ORANGE,))
    sc.box((-9.5, 9.5), (-6.5, 6.5), (3, 9), P_DARK)                 # fundo escuro
    for (x, y, c) in ((-6, -2, "#e8a066"), (-1, 2, "#c3d1e2"), (4, -1, "#a6ecff"), (6, 3, "#e8a066"), (-4, 3, "#a6ecff")):
        sc.box((x - 1.8, x + 1.8), (y - 1.8, y + 1.8), (9, 12), Pal(["#ffffff", c, c, "#6e5f52", "#3a3040"]))
    sc.obox((0, 12.5, 21), (11.5, 0.9, 7.5), P_BEIGE,                 # tampa aberta, tombada pra trás
            paint=lambda L, face: np.where(face == 2, 1, np.where(abs(L[:, 2] - 5.5) < 1.1, 2, 0)),
            extra=(Pal(BEIGE[2:] + ["#4a4048", "#3a3040"]), P_ORANGE), rot_x=-0.45)
    sc.box((-2, 2), (-9.2, -8), (10, 14), P_METAL)
    return render(sc)


# ---------------------------------------------------------------------------
# Luminárias
# ---------------------------------------------------------------------------
P_BULB = Pal(["#fffbe8", HEAT[0], HEAT[1], HEAT[1], HEAT[2]], emit=True, emit_tone=1)


P_LAMP_GLASS = Pal(["#fffbe8", "#fff3c4", HEAT[1], HEAT[2], HEAT[3]], emit=True, emit_tone=2)
P_LAMP_GLASS_HI = Pal(["#fffbe8"] * 5, emit=True, emit_tone=0)
P_LAMP_GLASS_LO = Pal([HEAT[2]] * 5, emit=True, emit_tone=0)


def lamp(tier=1):
    """Luminária industrial (forma da v5 aprovada no repo): base larga, coluna bege grossa com faixas laranja,
    colar escuro e lanterna de gaiola com o vidro aceso. nv.2: lanterna mais larga, grade 2×3 e faixa dourada."""
    sc = scene(16, 32, -6.5)
    big = tier == 2
    r_col = 2.1 if big else 1.6
    hw = 4.5 if big else 3.0
    hd = hw * 0.35                                             # cabeça rasa: o tampo não come o vidro
    bands = [(8, 9.6), (11, 12)] if big else [(9.5, 11.5)]

    def col_paint(t, z, c):
        out = np.zeros(len(t), int)
        for i, (a0, a1) in enumerate(bands):
            out[(z > a0) & (z < a1) & ~c] = 2 if (big and i == 2) else 1
        return out
    bw = 6.2 if big else 5.6
    sc.box((-bw, bw), (-3.2, 3.2), (0, 1.2), P_METAL)                                                  # pedestal em degraus
    sc.box((-bw + 0.6, bw - 0.6), (-2.8, 2.8), (1.2, 3.4), P_BEIGE,
           paint=lambda L, face: np.where(abs(L[:, 2]) < 0.5, 1, 0), extra=(P_GOLD if big else P_ORANGE,))
    sc.box((-bw + 2, bw - 2), (-2.2, 2.2), (3.4, 4.8), P_BEIGE)
    sc.cyl(0, 0, r_col, 4.8, 16, P_BEIGE, paint=col_paint, extra=(P_ORANGE, P_GOLD))                   # coluna
    sc.cyl(0, 0, r_col + 1.0, 16, 17.4, P_DARK)                                                        # colar
    rows, cols = (3, 3) if big else (2, 2)

    def cage(L, face):
        x, y, z = L[:, 0], L[:, 1], L[:, 2]
        u = x if face in (2, 3) else y                         # coordenada horizontal da face
        out = np.zeros(len(L), int)
        half_u = hw if face in (2, 3) else hd
        edge = (abs(u) > half_u - 0.9) | (abs(z) > 4.2)
        # molduras alinhadas à grade de pixels (mais fina que 1 px, o vidro ganharia o pixel)
        mull = ((np.floor(u + hw) % round(2 * hw / cols)) == 0) | ((np.floor((z + 5) * 0.82) % round(8.2 / rows)) == 0)
        out[z > 1.5] = 2                                       # vidro: claro em cima, laranja embaixo
        out[z < -2.5] = 3
        out[edge | mull] = 1
        if face == 5:
            out[:] = 1
        return out
    sc.box((-hw, hw), (-hd, hd), (17.4, 27.4), P_LAMP_GLASS, paint=cage, extra=(P_DARK, P_LAMP_GLASS_HI, P_LAMP_GLASS_LO))
    sc.box((-hw - 0.6, hw + 0.6), (-hd - 0.6, hd + 0.6), (27.4, 28.6), P_DARK)                         # tampa
    sc.box((-1.2, 1.2), (-0.8, 0.8), (28.6, 29.6), P_METAL)
    return render(sc)


# ---------------------------------------------------------------------------
# Estação de drones 2×2 (64×72): pads com H em (18,44) e (46,44), radar girando, luzes de pista correndo
# ---------------------------------------------------------------------------
def drone_station(f):
    sc = scene(64, 72, -22)
    pad_y = 6.2

    def deck(L, face):
        out = np.zeros(len(L), int)
        if face == 2:
            z = L[:, 2]
            out[(z > -2) & (z < 0.6)] = 1
        if face == 5:
            x, y = L[:, 0], L[:, 1] + 1        # o centro da caixa está em Y = −1
            for px in (-14, 14):
                dx, dy = x - px, y - pad_y
                r = np.hypot(dx, dy)
                out[(r < 9.2)] = 2
                out[(r > 7.6) & (r < 9.2)] = 1
                hh = ((abs(dx + 3) < 0.9) | (abs(dx - 3) < 0.9)) & (abs(dy) < 3.6) | (abs(dx) < 3.5) & (abs(dy) < 0.8)
                out[(r < 7.6) & hh] = 3
            out[(abs(x) < 0.6) & (out == 0)] = 4
        return out
    sc.box((-31, 31), (-22, 20), (0, 12), P_BEIGE, paint=deck, extra=(P_ORANGE, P_DARK, Pal(["#ffffff"] * 5), Pal(BEIGE[1:] + [BEIGE[4]])))
    sc.box((-30, -18), (11, 20), (12, 28), P_BEIGE,                 # torre
           paint=lambda L, face: np.where((face == 2) & (abs(L[:, 0]) < 4) & (L[:, 2] > 0) & (L[:, 2] < 5), 1,
                                          np.where((face == 2) & (L[:, 2] < -5.5) & (L[:, 2] > -7.5), 2, 0)),
           extra=(P_SCREEN, P_ORANGE))
    sc.cyl(22, 16, 1, 12, 42, P_METAL)                                # antena
    a = math.radians(f * 45)
    sc.obox((22 + math.cos(a) * 2, 16 + math.sin(a) * 2, 39), (3.5, 0.6, 2.2), P_STEEL, rot_z=a + math.pi / 2)
    sc.dot(22, 16, 43.5, ALERT if f % 2 == 0 else "#7a2a24", always=True)
    for k in range(6):                                                # luzes de pista
        sc.dot(-26 + k * 10, -22.3, 6, HEAT[1] if k % 4 == f else METAL[2], always=True)
    for px in (-14, 14):                                              # luzinhas dos pads
        for (dx, dy) in ((-9.6, 0), (9.6, 0), (0, -9.6), (0, 9.6)):
            sc.dot(px + dx, pad_y + dy, 12.2, OK if (f + int(dx)) % 2 == 0 else ORANGE_D, always=True)
    return render(sc)


# ---------------------------------------------------------------------------
# Forno: boca de fogo tremendo, metal escorrendo pro molde, fumaça
# ---------------------------------------------------------------------------
def furnace(f, tier=1):
    tall = tier == 2
    sc = scene(40, 64 if tall else 56, -13)
    base(sc, 19 if tall else 16, 13, 7 if tall else 5, bolts=GOLD if tall else ORANGE)
    z0 = 7 if tall else 5
    ztop = 46 if tall else 36
    flick = [(0, 1, 0, 2), (1, 0, 2, 1), (2, 1, 1, 0), (1, 2, 0, 1)][f]

    def paint(L, face):
        out = np.zeros(len(L), int)
        x, z = L[:, 0], L[:, 2]
        hz = (ztop - z0) / 2
        if face == 2:
            out[(z > hz - 9) & (z < hz - 6.6)] = 1
            mz0, mz1 = -hz + 6, -hz + (21 if tall else 18)
            mouth = (x > -10) & (x < 4) & (z > mz0) & (z < mz1)
            out[mouth] = 2
            col = np.floor(x + 10).astype(int)
            hgt = 3 + np.array([flick[c % 4] + (1 if c % 3 == 0 else 0) for c in range(16)])[np.clip(col, 0, 15)]
            fire = mouth & (z < mz0 + hgt)
            out[fire] = 3
            out[fire & (z < mz0 + 1.2)] = 5
            out[fire & (z > mz0 + hgt - 1.2)] = 6
            out[mouth & ((np.floor(x + 10) % 3) < 0.6)] = 7
        return out
    sc.box((-13, 13), (-10, 10), (z0, ztop), P_BEIGE, paint=paint,
           extra=(P_GOLD if tall else P_ORANGE, Pal(["#2a1418"] * 5), HEATS[1], HEATS[0], HEATS[0], HEATS[2], P_METAL))
    sc.cyl(6, 4, 3, ztop, ztop + (14 if tall else 11), P_BEIGE,
           paint=lambda t, z, c: np.where((z > ztop + 3) & (z < ztop + 4.6) & ~c, 1, 0), extra=(P_GOLD if tall else P_ORANGE,))
    sc.box((-9, 1), (-3, 5), (ztop, ztop + 2), P_METAL)            # tampa do cadinho
    sc.hcyl(13, 17, -3, z0 + 18, 1.3, P_METAL)                      # bica
    fill = [1, 2, 3, 3][f]
    sc.box((13, 19), (-9, -1), (0, 4), P_METAL,                     # molde no chão
           paint=lambda L, face: np.where((face == 5) & (abs(L[:, 0]) < 2) & (abs(L[:, 1]) < 3), 1, 0),
           extra=(HEATS[0] if fill < 3 else Pal([ORANGE] * 5, emit=True, emit_tone=0),))
    if f < 3:
        for z in range(5, z0 + 17):
            sc.dot(16.5, -3, z, HEAT[1] if (z + f) % 2 else HEAT[2], always=True)
    front_panel(sc, 6, 11, -10, z0 + 9, z0 + 14, f, leds=3 if tall else 2)
    warn(sc, 8.5, -10, z0 + 3)
    for i in range(3):
        sc.dot(6 + (i + f) % 2, 4, ztop + (14 if tall else 11) + 1 + (f * 2 + i * 3) % 7, "#9a8f98" if i else "#c9c0c6",
               always=True)
    return render(sc)


# ---------------------------------------------------------------------------
# Drone (16×16, 4 quadros = contrato): corpo em cápsula, 4 braços, hélices girando de verdade
# ---------------------------------------------------------------------------
P_ROTOR = Pal(["#6f6a82", "#5f5a72", "#4f4a62", "#433e55", "#363146"], emit=True, emit_tone=1)


P_SLATE = Pal(["#8b93b8", "#5f6890", "#454d72", "#343a5a", "#262a44"])
P_EYE = [Pal(["#ffffff", "#ff9a8a", ALERT, "#d8323a", "#8a1e2a"], emit=True, emit_tone=t) for t in (3, 2, 1, 2)]
P_THRUST = Pal(["#ffffff", CYAN_L, CYAN, CYAN_D, "#1d4a66"], emit=True, emit_tone=1)


def drone(f):
    """Drone esférico flutuante (sem hélice), 16×16, 4 quadros = contrato.
    Corpo bege com faixa de painel escura passando por cima e cinto no equador, olho vermelho pulsando na
    frente, aletas laterais e um propulsor ciano embaixo tremendo. O balanço de flutuar o jogo já faz."""
    sc = Scene(16, 16, ground=9.0)

    def shell(N):
        out = np.zeros(len(N), int)
        out[(abs(N[:, 0]) < 0.22) & (N[:, 2] > 0.5)] = 1   # faixa de painel por cima
        out[abs(N[:, 2]) < 0.13] = 2                       # cinto laranja no equador
        out[(N[:, 2] < -0.55)] = 1                         # fundo escuro (onde fica o propulsor)
        return out
    sc.sphere((0, 0.5, 0.6), 5.0, P_BEIGE, paint=shell, extra=(P_SLATE, P_ORANGE))
    for sx in (-1, 1):                                       # aletas laterais
        sc.obox((sx * 5.6, 0.8, 0.6), (1.0, 2.2, 1.7), P_SLATE)
        sc.obox((sx * 6.5, 0.8, 0.6), (0.4, 2.6, 0.7), P_BEIGE)
    sc.sphere((0, -3.7, 2.2), 2.3, P_SLATE)                  # moldura do olho, saltada pra frente
    sc.sphere((0, -4.8, 2.2), 1.6, P_EYE[f])                 # olho
    sc.dot(-0.7, -6.2, 3.1, "#ffffff", always=True)          # brilho do olho
    sc.cyl(0, 0.5, 1.6, -4.8, -4.1, P_SLATE, cap=False)      # bocal do propulsor
    cv = render(sc)
    flame = [[(7, 15), (8, 15)], [(7, 15), (8, 15), (8, 16)], [(8, 15)], [(7, 15), (8, 15), (7, 16)]][f]
    for (x, y) in flame:                                      # chama ciano (sem contorno)
        if 0 <= y < 16 and not cv.solid(x, y):
            cv.px(x, y, CYAN_L if y == 15 else CYAN)
    for (x, y, on) in ((3, 2, f % 2 == 0), (12, 2, f % 2 == 1)):   # antenas com ponta piscando
        cv.px(x, y, ALERT if on else "#7a2a24")
    return cv



# =====================================================================================================================
# v1.1 · AQUECEDORES A MAGMATITA (pedido do dono): a máquina queima pedra de Magmatita (basalto com veios de lava).
# Câmara com janela onde dá pra ver as pedras incandescentes, carga por cima e o calor saindo pelas aletas.
# =====================================================================================================================
BASALT = ["#6a5f72", "#4e4558", "#3a3244", "#2a2333", "#1d1726"]
P_BASALT = Pal(BASALT)
LAVA = ["#fff4cc", "#ffd27a", "#ff9a3d", "#e0602a", "#a8402a"]
P_LAVA = [Pal(LAVA, emit=True, emit_tone=t) for t in range(5)]
P_EMBER = [Pal(["#a8402a"] * 5, emit=True, emit_tone=0), Pal(["#c24e2c"] * 5, emit=True, emit_tone=0),
           Pal(["#ff9a3d"] * 5, emit=True, emit_tone=0)]
P_GLASS_HOT = Pal(["#ffe2b8"] * 5, emit=True, emit_tone=0)


def _hash(*v):
    """Pseudo-aleatório determinístico pequeno (sem random)."""
    h = 2166136261
    for x in v:
        h = ((h ^ (int(x * 97) & 0xffffffff)) * 16777619) & 0xffffffff
    return h / 0xffffffff


def magma_rock(sc, c, r, f, k, hot=1):
    """Pedra de Magmatita: bloco gordinho de basalto (caixa arredondada, meio torta) com veios de lava que pulsam.
    k varia a forma e a fase do brilho; hot 0..2 deixa os veios mais claros (nv.2)."""
    hx = r * (0.85 + 0.35 * _hash(k, 1))
    hy = r * (0.8 + 0.3 * _hash(k, 2))
    hz = r * (0.7 + 0.3 * _hash(k, 3))
    a, b = 1.3 + _hash(k, 4) * 1.2, _hash(k, 5) * 6
    tone = [2, 1, 0, 1][(f + k) % 4]
    tone = max(0, tone - hot + 1) if hot > 1 else tone

    def paint(L, N):
        u = L[:, 0] * (a - 0.6) + L[:, 2] * 1.1 + b + 0.8 * np.sin(L[:, 1] * 1.3 + L[:, 0] * 0.9 + k)
        per = 1.7 * r + 1.0
        crack = np.abs(((u + 10) % per) - per / 2) < 0.55
        under = (N[:, 2] < -0.25) | (L[:, 2] < -hz * 0.55)
        return np.where(crack, 1, np.where(under, 2, 0))
    sc.rbox(c, (hx, hy, hz), min(hx, hy, hz) * 0.75, P_BASALT, paint=paint,
            extra=(P_LAVA[min(4, tone + 1)], P_LAVA[min(4, tone + 2)]))


def _rocks_pile(sc, x0, x1, y, z0, z1, f, hot=1, seed=0, r=2.3):
    """Pilha de pedras numa janela: fileiras de baixo pra cima, alternando o passo."""
    k = seed
    z = z0 + r * 0.8
    row = 0
    while z < z1 - r * 0.5:
        x = x0 + r + (r * 0.9 if row % 2 else 0)
        while x < x1 - r * 0.6:
            magma_rock(sc, (x + (_hash(k, 9) - 0.5), y + _hash(k, 8) * 0.8, z), r, f, k, hot)
            x += 2 * r * 0.95
            k += 1
        z += 2 * r * 0.78
        row += 1


def _shimmer2(sc, x, y, ztop, f, n=3, span=9, gold=False):
    """Tremor de calor: fiapos subindo em zigue-zague (sem contorno)."""
    for i in range(n):
        for j in range(2):
            z = ztop + 1 + ((f * 2 + i * 3 + j * 4) % span)
            dx = (1 if ((z // 2) + i) % 2 else 0) + (i - n // 2) * 2.2
            col = HEAT[0] if j == 0 and i % 2 == 0 else (GOLD_L if gold and j else HEAT[1] if j == 0 else HEAT[2])
            sc.dot(x + dx, y, z, col, always=True)


def _fins_side(sc, x0, x1, y0, y1, z0, z1, pitch=2.6, pal=None):
    """Aletas de radiador: lâminas horizontais empilhadas na lateral."""
    z = z0
    while z + 1.2 <= z1:
        sc.box((x0, x1), (y0, y1), (z, z + 1.2), pal or P_METAL)
        z += pitch


def _window(sc, x0, x1, z0, z1, y, f, gold=False, bars=2):
    """Moldura da janela da câmara (metal ou dourado) + o fundo em brasa + grade vertical na frente."""
    sc.box((x0, x1), (y - 0.6, y + 0.4), (z0, z1), P_EMBER[f % 2 + (1 if gold else 0)],
           paint=lambda L, face: np.where(L[:, 2] < -(z1 - z0) / 2 + 2.5, 1, 0), extra=(P_EMBER[2],))
    fr = P_METAL
    t = 1.1
    sc.box((x0 - t, x1 + t), (y - 1.6, y - 0.4), (z0 - t, z0), fr)
    sc.box((x0 - t - 0.3, x1 + t + 0.3), (y - 1.9, y - 0.4), (z1, z1 + t + 0.4), P_GOLD if gold else fr)
    sc.box((x0 - t, x0), (y - 1.6, y - 0.4), (z0, z1), fr)
    sc.box((x1, x1 + t), (y - 1.6, y - 0.4), (z0, z1), fr)
    for i in range(bars):
        bx = x0 + (x1 - x0) * (i + 1) / (bars + 1)
        sc.box((bx - 0.4, bx + 0.4), (y - 4.2, y - 3.4), (z0, z1), P_DARK)


def _feed_hopper(sc, cx, cy, z0, r0, r1, h, f, gold=False, hot=1, n=4):
    """Funil de carga em cima: tronco de cone, aro e as pedras aparecendo na boca."""
    sc.cyl(cx, cy, r0, z0, z0 + h, P_METAL, r_top=r1, cap=False)
    sc.disc(cx, cy, z0 + h - 1.2, r1 - 0.6, P_DARK)
    sc.cyl(cx, cy, r1 + 0.5, z0 + h - 0.2, z0 + h + 0.9, P_GOLD if gold else P_ORANGE, cap=False)
    for i in range(n):
        a = i * 2 * math.pi / n + 0.5
        rr = (r1 - 3.0) * (0.55 + 0.3 * _hash(i, 11)) if i else 0
        magma_rock(sc, (cx + rr * math.cos(a), cy + rr * math.sin(a), z0 + h - 0.8), 2.4 if r1 < 10 else 2.7, f, 20 + i,
                   hot)


def heater_a(f, tier=1):
    """A · fornalha de janela: caixa bege com a câmara de pedras à mostra, funil de carga em cima e aletas nas duas
    laterais. nv.2: câmara DUPLA (duas janelas de moldura dourada), funil maior, aletas mais altas e chaminé."""
    if tier == 1:
        sc = scene(40, 56, -13)
        sapata(sc, 16)
        zb, zt = SAP_H, 31

        def body(L, N):
            fr = N[:, 1] < -0.9
            return np.where(fr & (L[:, 2] > 8.2) & (L[:, 2] < 10.4), 1, 0)
        sc.rbox((0, 0, (zb + zt) / 2), (11.5, 10, (zt - zb) / 2), 1.8, P_BEIGE, paint=body, extra=(P_ORANGE,))
        _window(sc, -9.0, 4.0, 8.5, 23, -10, f, bars=1)
        _rocks_pile(sc, -9.0, 4.0, -10.9, 8.5, 23, f, seed=1, r=3.0)
        for sx in (-1, 1):
            _fins_side(sc, sx * 11.2 - (3.6 if sx > 0 else 0) + (0 if sx > 0 else -0), sx * 11.2 + (3.6 if sx > 0 else 0)
                       if sx > 0 else -11.2, -7, 7, 9, 29) if False else None
        _fins_side(sc, -15, -11.3, -7, 7, 8.5, 29)
        _fins_side(sc, 11.3, 15, -7, 7, 8.5, 29)
        front_panel(sc, 6.5, 10, -10, 17, 22, f, leds=1)
        warn(sc, 8.3, -10, 11.5)
        _feed_hopper(sc, -1, 2, zt, 5.5, 9, 7, f)
        _shimmer2(sc, -1, 2, zt + 8, f)
        _shimmer2(sc, 13.2, 0, 29.5, f + 1, n=2, span=7)
        _shimmer2(sc, -13.2, 0, 29.5, f + 3, n=2, span=7)
        return render(sc)
    sc = scene(40, 64, -13)
    sapata(sc, 19)
    zb, zt = SAP_H, 38

    def body2(L, N):
        fr = N[:, 1] < -0.9
        out = np.zeros(len(L), int)
        out[fr & (L[:, 2] > 12.2) & (L[:, 2] < 14.6)] = 1
        out[fr & (L[:, 2] > -14.6) & (L[:, 2] < -13.2)] = 2
        return out
    sc.rbox((0, 0, (zb + zt) / 2), (13.5, 10, (zt - zb) / 2), 2.0, P_BEIGE, paint=body2, extra=(P_GOLD, P_ORANGE))
    for x0 in (-11.0, 1.5):
        _window(sc, x0, x0 + 9.5, 9.5, 26, -10, f, gold=True, bars=0)
        _rocks_pile(sc, x0, x0 + 9.5, -10.9, 9.5, 26, f, hot=2, seed=int(x0 * 3) + 40, r=2.45)
    _fins_side(sc, -18.5, -13.3, -8, 8, 8, 36, pitch=2.4)
    _fins_side(sc, 13.3, 18.5, -8, 8, 8, 36, pitch=2.4)
    for x in (-18.6, 18.6 - 1.2):                                     # trilho dourado amarrando as aletas
        sc.box((x, x + 1.2), (-8.6, -7.6), (7.5, 37), P_GOLD)
    front_panel(sc, -4, 3, -10, 30, 35, f, leds=3)
    warn(sc, 7, -10, 31)
    _feed_hopper(sc, -3, 2, zt, 6.5, 10.5, 7, f, gold=True, hot=2, n=5)
    sc.cyl(9, 5, 2.4, zt, zt + 10, P_BEIGE, paint=lambda t, z, c: np.where((z > zt + 6) & (z < zt + 7.5) & ~c, 1, 0),
           extra=(P_GOLD,))
    _shimmer2(sc, -3, 2, zt + 8, f, gold=True)
    _shimmer2(sc, 9, 5, zt + 10, f + 2, n=2, gold=True)
    _shimmer2(sc, 16, 0, 36.5, f + 1, n=2, span=6)
    _shimmer2(sc, -16, 0, 36.5, f + 3, n=2, span=6)
    return render(sc)


def _crown_fins(sc, cx, cy, z0, z1, r_in, r_out, n, pal=None):
    """Coroa de aletas radiais (dissipador redondo) em volta de um cilindro."""
    for k in range(n):
        a = k * 2 * math.pi / n + 0.2
        rm = (r_in + r_out) / 2
        sc.obox((cx + rm * math.cos(a), cy + rm * math.sin(a), (z0 + z1) / 2), ((r_out - r_in) / 2, 0.55, (z1 - z0) / 2),
                pal or P_METAL, rot_z=a)


def _slot_paint(z0, z1, ang_half, extra_bands=(), gold_bands=()):
    def paint(t, z, cap):
        out = np.zeros(len(t), int)
        for (a, b) in extra_bands:
            out[(z > a) & (z < b) & ~cap] = 1
        for (a, b) in gold_bands:
            out[(z > a) & (z < b) & ~cap] = 2
        d = ang_dist(t, FRONT)
        out[(d < ang_half + 0.18) & (z > z0 - 1.2) & (z < z1 + 1.2) & ~cap] = 3
        out[(d < ang_half) & (z > z0) & (z < z1) & ~cap] = 4
        return out
    return paint


def heater_b(f, tier=1):
    """B · caldeira de coluna: cilindro bege com uma janela alta na frente cheia de pedras em brasa, coroa de aletas
    radiais em cima (o dissipador) e uma calha de carga de lado. nv.2: coluna mais larga, DUAS janelas, coroa
    dupla com aro dourado e calha maior."""
    big = tier == 2
    sc = scene(40, 64 if big else 56, -13)
    sapata(sc, 19 if big else 16)
    R = 11.5 if big else 10.5
    zb = SAP_H
    zt = 40 if big else 30
    wins = ((-0.5, 0.5),) if not big else ((-0.56, -0.09), (0.09, 0.56))
    wz0, wz1 = (zb + 7, zt - 9) if big else (zb + 5, zt - 6)
    # corpo: a janela é recortada pintando o corpo de brasa e pondo as pedras/barras na frente
    def paint(t, z, cap):
        out = np.zeros(len(t), int)
        out[(z > zb + 1.5) & (z < zb + 3.5) & ~cap] = 2 if big else 1
        out[(z > zt - (5.5 if big else 3.5)) & (z < zt - (3.6 if big else 1.8)) & ~cap] = 1
        for (a0, a1) in wins:
            d = (t - FRONT + math.pi) % (2 * math.pi) - math.pi
            fr = (d > a0 - 0.12) & (d < a1 + 0.12) & (z > wz0 - 1.2) & (z < wz1 + (2.0 if big else 1.2)) & ~cap
            out[fr] = 3
            if big:                                                   # verga dourada em cima da janela (como a A nv.2)
                out[fr & (z > wz1)] = 2
            inn = (d > a0) & (d < a1) & (z > wz0) & (z < wz1) & ~cap
            out[inn] = 4
            out[inn & (z < wz0 + 2.5)] = 5
        return out
    sc.cyl(0, 0, R, zb, zt, P_BEIGE, paint=paint, extra=(P_ORANGE, P_GOLD, P_METAL, P_EMBER[f % 2], P_EMBER[2]))
    k = 60
    for (a0, a1) in wins:
        for j, zz in enumerate(np.arange(wz0 + 2.6, wz1 - 1.5, 4.4)):
            off = 0.13 if j % 2 else 0.0
            for aa in np.arange(a0 + 0.2 + off, a1 - 0.12, 0.27):
                a = FRONT + aa
                rr = R - 2.0
                magma_rock(sc, (rr * math.cos(a), rr * math.sin(a), zz), 2.7, f, k, 2 if big else 1)
                k += 1
        am = FRONT + (a0 + a1) / 2                                    # barra vertical no meio da janela
        sc.box((R * math.cos(am) - 0.4, R * math.cos(am) + 0.4), (R * math.sin(am) - 0.9, R * math.sin(am)),
               (wz0, wz1), P_DARK)
    # tampa + coroa de aletas
    sc.cyl(0, 0, R + 0.4, zt, zt + 1.6, P_GOLD if big else P_METAL)
    _crown_fins(sc, 0, 0, zt + 1.6, zt + (8 if big else 6.5), 5.2, R + (1.6 if big else 1.2), 18 if big else 14, P_STEEL)
    _feed_hopper(sc, 0, 0, zt + 1.6, 4.4, 6.0, (7.2 if big else 5.6), f, gold=big, hot=2 if big else 1, n=3)
    if big:
        sc.cyl(0, 0, R + 2.0, zt + 9, zt + 9.8, P_GOLD, cap=False)
    if big:
        # v1.2: o radiador da A nos dois lados (mesmas aletas), amarrado por trilho dourado, e o painel de 3 LEDs
        for sx in (-1, 1):
            x0, x1 = (R - 1.0, 18.6) if sx > 0 else (-18.6, -R + 1.0)
            _fins_side(sc, x0, x1, -6, 6, zb + 3, zt - 2, pitch=2.4)
            xr = 18.6 - 1.2 if sx > 0 else -18.6
            sc.box((xr, xr + 1.2), (-6.6, -5.6), (zb + 2.5, zt - 1.5), P_GOLD)
            _shimmer2(sc, sx * 16, 0, zt - 1.5, f + 1 + sx, n=2, span=6)
        front_panel(sc, -3, 3, -R - 0.2, zb + 0.6, zb + 4.4, f, leds=3)
    else:
        hx, hz = 12.0, zt - 4
        _fins_side(sc, hx, hx + 4.2, -2.5, 6.5, hz - 22, hz - 7, pitch=2.4, pal=P_METAL)
        front_panel(sc, -R + 0.5, -R + 5, -R * 0.62, zb + 6, zb + 11, f, leds=1)
        _shimmer2(sc, hx + 2, 2, hz - 7, f + 2, n=2, span=6)
    _shimmer2(sc, 0, 0, zt + (9.6 if big else 7.6), f, n=4 if big else 3, gold=big)
    return render(sc)


# =====================================================================================================================
# v1.1 · DRILLS A LASER (pedido do dono). 64×80 por quadro, 4 quadros a 8 fps, mesma âncora (centro da base dos 2×2).
# O feixe é desenhado em 2D por cima do render (luz não tem contorno): núcleo claro, brilho em volta pulsando, ponto
# de impacto incandescente no veio e faíscas voando. A drill T1 usa; a aranha e o tripé (T2/T3) estão em
# machines_r3d_futuro.py.
# =====================================================================================================================
LASER_CYAN = ("#ffffff", CYAN_L, CYAN, CYAN_D)
LASER_HOT = ("#fffbe8", HEAT[0], HEAT[1], HEAT[2])


def _proj(sc, X, Y, Z):
    sx, sy, _ = sc.proj(X, Y, Z)
    return sx, sy


def _line_pts(x0, y0, x1, y1):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    return [(round(x0 + (x1 - x0) * i / max(n - 1, 1) - 0.5), round(y0 + (y1 - y0) * i / max(n - 1, 1) - 0.5))
            for i in range(n)]


def laser(cv, p0, p1, f, pal, under=None):
    """Feixe de p0 (boca) a p1 (impacto), coordenadas de tela. Pulsa: 3 px nos quadros pares, 5 px nos ímpares.
    `under`: máscara (h, w) do que fica na frente do feixe (não pinta por cima)."""
    core, lit, mid, dark = pal
    pts = _line_pts(*p0, *p1)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    steep = abs(dy) >= abs(dx)
    half = 2 if f % 2 else 1
    for i, (x, y) in enumerate(pts):
        for k in range(-half, half + 1):
            xx, yy = (x + k, y) if steep else (x, y + k)
            c = core if k == 0 else lit if abs(k) == 1 else (mid if (i + f) % 3 else dark)
            if 0 <= xx < cv.w and 0 <= yy < cv.h and (under is None or not under[yy, xx]):
                cv.px(xx, yy, c)
    # anéis de energia correndo pelo feixe (1 px mais largo, descendo)
    for i in range((f * 3) % 6, len(pts), 6):
        x, y = pts[i]
        for k in (-half - 1, half + 1):
            xx, yy = (x + k, y) if steep else (x, y + k)
            if 0 <= xx < cv.w and 0 <= yy < cv.h and not cv.solid(xx, yy):
                cv.px(xx, yy, lit)


def impact(cv, x, y, f, pal, rx=6, ry=3):
    """Ponto de impacto: poça elíptica incandescente (só no chão vazio), cruz de brilho e faíscas espirrando."""
    core, lit, mid, dark = pal
    rr = [1.0, 1.25, 1.1, 1.35][f]
    for yy in range(int(y - ry * 1.6), int(y + ry * 1.6) + 1):
        for xx in range(int(x - rx * 1.6), int(x + rx * 1.6) + 1):
            d = ((xx + 0.5 - x) / (rx * rr)) ** 2 + ((yy + 0.5 - y) / (ry * rr)) ** 2
            if d <= 1.0 and not cv.solid(xx, yy):
                cv.px(xx, yy, HEAT[3] if d > 0.6 else (HEAT[1] if d > 0.22 else HEAT[0]))
    xi, yi = int(x), int(y)
    arm = 3 if f % 2 else 2
    for k in range(-arm, arm + 1):
        cv.px(xi + k, yi, core if abs(k) < 2 else lit)
        cv.px(xi, yi + k, core if abs(k) < 2 else lit)
    if f % 2:
        for k in (-1, 1):
            cv.px(xi + k, yi + k, lit)
            cv.px(xi + k, yi - k, lit)
    for i in range(7):                                         # faíscas em arco, trocando a cada quadro
        a = math.radians(200 + i * 22 + f * 9)
        dist = 4 + ((f * 3 + i * 5) % 7)
        sx = int(round(x + math.cos(a) * dist * 1.3))
        sy = int(round(y + math.sin(a) * dist * 0.8 - (dist % 3)))
        if not cv.solid(sx, sy):
            cv.px(sx, sy, HEAT[0] if i % 3 == 0 else (HEAT[1] if i % 3 == 1 else ORANGE))
    for i in range(3):                                         # lascas de pedra saltando
        a = math.radians(160 + i * 110 + f * 31)
        dist = 6 + (f + i * 2) % 5
        sx, sy = int(x + math.cos(a) * dist * 1.2), int(y + math.sin(a) * dist * 0.6 - 2)
        if not cv.solid(sx, sy):
            cv.px(sx, sy, "#8e6b5c" if i % 2 else "#c9a38a")


def _fill_window(cv, rect):
    fx, fy, fw, fh = rect
    cv.rect(fx - 1, fy - 1, fw + 2, fh + 2, METAL[3])
    cv.rect(fx, fy, fw, fh, GLASS)
    cv.px(fx, fy, "#2c4256")


# =====================================================================================================================
# v1.2 · DRILL T1 a laser (o contrato `machine_drill`): poucas peças. Sapata B ao lado do veio, caixa com o indicador,
# mastro, braço e uma cabeça de laser simples apontando pro veio. Mesmo feixe ciano, poça e faíscas da aranha.
# (A aranha e o tripé ficaram guardados pra T2/T3 em machines_r3d_futuro.py.)
# =====================================================================================================================
FILL_T1 = (12, 54, 7, 10)                # indicador na frente da caixa do pé do mastro
P_EMIT_CYAN = [Pal([c] * 5, emit=True, emit_tone=0) for c in (CYAN_L, CYAN, CYAN_L, "#ffffff")]


def drill(f):
    sc = scene(64, 80, -28)
    mx, my = -17.0, -8.0                                            # pé do mastro (em cima da sapata)
    hit = (5.0, 4.0, 0.0)
    sapata(sc, 10, at=(mx, my))
    zb = SAP_H
    # caixa do pé: bege, faixa laranja, LED (o indicador entra em 2D na frente)
    sc.rbox((mx, my - 1.5, zb + 8.5), (6.0, 5.0, 8.5), 1.4, P_BEIGE,
            paint=lambda L, N: np.where((L[:, 2] > 5.2) & (L[:, 2] < 6.8), 1, 0), extra=(P_ORANGE,))
    sc.dot(mx + 4.2, my - 6.8, zb + 12.5, OK if f % 2 == 0 else "#2f5a2c", always=True)
    # mastro + junta + contrapeso laranja
    top = 52.0
    sc.cyl(mx, my + 1, 2.2, zb + 17, top - 1, P_STEEL,
           paint=lambda t, z, c: np.where(((z > 34) & (z < 35.6) | (z > 38) & (z < 39.6)) & ~c, 1, 0), extra=(P_ORANGE,))
    sc.sphere((mx, my + 1, top), 3.2, P_METAL)
    sc.rbox((mx - 5.2, my + 1, top + 0.4), (2.4, 2.2, 2.0), 0.8, P_ORANGE)
    # braço até a cabeça
    head = (hit[0], hit[1], 31.0)
    sc.tube([(mx, my + 1, top), (head[0] - 3.5, head[1], head[2] + 9.5)], 1.7, P_BEIGE,
            paint=lambda sv, th: np.where((sv > 9) & (sv < 11), 1, 0), extra=(P_ORANGE,))
    # cabeça de laser: caixa arredondada com faixa, colar escuro e o anel emissor ciano embaixo
    sc.rbox((head[0], head[1], head[2] + 5), (5.0, 4.2, 5.0), 2.0, P_BEIGE,
            paint=lambda L, N: np.where(np.abs(L[:, 2] + 1.0) < 0.9, 1, 0), extra=(P_ORANGE,))
    sc.cyl(head[0], head[1], 3.4, head[2] - 2.0, head[2], P_DARK)
    sc.cyl(head[0], head[1], 2.2, head[2] - 3.2, head[2] - 2.0, P_EMIT_CYAN[f], cap=False)
    sc.dot(head[0] - 3.4, head[1] - 4.4, head[2] + 7.5, CYAN if f % 2 == 0 else CYAN_D, always=True)
    sc.dot(head[0] - 1.6, head[1] - 4.4, head[2] + 7.5, ALERT if f < 2 else "#7a2a24", always=True)
    cv = render(sc)
    e = _proj(sc, head[0], head[1] - 0.5, head[2] - 3.2)
    h_ = _proj(sc, head[0], head[1] - 0.5, 0.0)
    laser(cv, e, h_, f, LASER_CYAN)
    impact(cv, *h_, f, LASER_CYAN)
    _fill_window(cv, FILL_T1)
    return cv


# =====================================================================================================================
# Geração, contrato e conferência com o freela
# =====================================================================================================================
def _specs():
    """(pasta, nome, canvas, tamanho do contrato do jogo, origem no freela). Pasta '' = contrato (drop-in)."""
    pod = to_beige(make_pod())
    S = []

    def add(folder, name, cv, size, src):
        S.append((folder, name, cv, size, src))

    for k in ("o2", "heater", "melter"):
        fn = V11_FN.get(k, globals()[k])
        add("", f"machine_{k}.png", fn(0), (40, 56), f"machine_{k}.png")
        add("", f"machine_{k}_t2.png", fn(0, 2), (40, 64), f"machine_{k}_t2.png")
    add("", "machine_drill.png", anim(drill), (256, 80), "machine_drill.png")
    add("", "solar_panel.png", solar(0), (32, 40), "solar_panel.png")
    add("", "terminal.png", terminal(0), (32, 32), "terminal.png")
    add("", "lamp.png", lamp(1), (16, 32), "lamp.png")
    add("", "lamp_t2.png", lamp(2), (16, 32), "lamp_t2.png")
    add("", "drone_station.png", drone_station(0), (64, 72), "drone_station.png")
    add("", "drone.png", anim(drone), (64, 16), "drone.png")
    add("", "pod.png", pod, (64, 72), "pod.png")
    # animações que só o freela tem (o jogo ainda não recorta)
    for k in ("o2", "heater", "melter"):
        fn = V11_FN.get(k, globals()[k])
        add("anim", f"anim_machine_{k}.png", anim(fn), (160, 56), f"propostas/anim_machine_{k}.png")
        add("anim", f"anim_machine_{k}_t2.png", anim(lambda f, fn=fn: fn(f, 2)), (160, 64),
            f"propostas/anim_machine_{k}_t2.png")
    add("anim", "anim_solar_panel.png", anim(solar), (128, 40), "propostas/anim_solar_panel.png")
    add("anim", "anim_terminal.png", anim(terminal), (128, 32), "propostas/anim_terminal.png")
    add("anim", "anim_drone_station.png", anim(drone_station), (256, 72), "propostas/anim_drone_station.png")
    add("anim", "anim_pod.png", anim(lambda f: pod_anim(pod, f)), (256, 72), "propostas/anim_pod.png")
    # gerador eólico: pronto, fora do jogo
    add("eolico", "wind_turbine.png", wind_turbine(0), (32, 64), "propostas/wind_turbine.png")
    add("eolico", "anim_wind_turbine.png", anim(wind_turbine, 8), (256, 64), "propostas/anim_wind_turbine.png")
    add("eolico", "icon_wind.png", icon_wind(), (16, 16), "propostas/icon_wind.png")
    return S


# v1.2: o que entra no contrato e o que mudou de propósito em relação ao freela.
# Aquecedor: nv.1 = opção A (fornalha de janela), nv.2 = opção B (caldeira de coluna) ajustada pra família da A.
V11_FN = {"heater": lambda f, tier=1: heater_a(f) if tier == 1 else heater_b(f, 2)}
CHANGED_V11 = {"machine_o2.png", "machine_o2_t2.png", "machine_heater.png", "machine_heater_t2.png", "machine_melter.png",
               "machine_melter_t2.png", "machine_drill.png", "solar_panel.png", "anim/anim_machine_o2.png",
               "anim/anim_machine_o2_t2.png", "anim/anim_machine_heater.png", "anim/anim_machine_heater_t2.png",
               "anim/anim_machine_melter.png", "anim/anim_machine_melter_t2.png", "anim/anim_solar_panel.png"}


def build():
    specs = _specs()
    for folder, name, cv, size, _ in specs:
        assert (cv.w, cv.h) == size, f"{name}: {cv.w}×{cv.h}, esperado {size}"
        cv.save(OUT / folder / name)
    return specs


def check(specs):
    """Compara cada PNG gerado com o do freela (pixel a pixel, RGBA). Devolve (bateu, nao_bateu)."""
    ok, bad = [], []
    for folder, name, cv, size, src in specs:
        if f"{folder + '/' if folder else ''}{name}" in CHANGED_V11:
            continue                                   # mudou de propósito na v1.1 (sapata, aquecedor, drill)
        a = np.array(Image.open(OUT / folder / name).convert("RGBA"))
        b = np.array(Image.open(FREELA / src).convert("RGBA"))
        if a.shape == b.shape and (a == b).all():
            ok.append(f"{folder + '/' if folder else ''}{name}")
        else:
            n = int((a != b).any(axis=2).sum()) if a.shape == b.shape else -1
            bad.append((f"{folder + '/' if folder else ''}{name}", n))
    return ok, bad


def main():
    specs = build()
    print(f"{len(specs)} PNGs em {OUT.relative_to(ROOT)}")
    if "--check" in sys.argv:
        ok, bad = check(specs)
        print(f"bateram pixel a pixel com o freela: {len(ok)}/{len(specs)}")
        for n in ok:
            print("  OK  ", n)
        for n, d in bad:
            print("  DIFF", n, f"({d} px)")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
