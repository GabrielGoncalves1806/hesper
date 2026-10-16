#!/usr/bin/env python3
"""v0.7 Lore · os 5 destroços (a partir da referência do dono, recriados no estilo do jogo).

    python3 tools/sprites/v07_destrocos.py

Saída: reports/design/v07_lore/pendentes/wreck_*.png (CANDIDATAS, nada vai pra assets/sprites sem o ok do dono).
Só PIL + numpy, determinístico. O report e as prévias saem do v07_lore_report.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import *  # noqa: E402,F401,F403
from v07_lib import C, Cv, OUT, hsh, sand_pile, scatter, vnoise  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"

# ---- paletas (as do jogo: creme das máquinas, laranja #e2733a, contorno #1b1630) + ardósia pro transportador
CREAM = ["#fbf7ec", "#efe7d4", "#e3d9c3", "#cfc4ab", "#b3a78d", "#8e7f73"]
SLATE = ["#aab2d0", "#7f89ad", "#626b8e", "#4b5273", "#363b58"]
OR_L, OR, OR_D = "#f29a62", "#e2733a", "#a8471f"
RUST = ["#b0663f", "#8a4e34", "#5e3526", "#3a2219"]
CAV = ["#2c2634", "#221d2a", "#17131e"]
GLASS = ["#8fc4f0", "#3a5068", "#1d2b3a"]
METAL = ["#c8cdd4", "#9aa2ab", "#6b717a", "#4a4f57", "#3b3f46"]


def seam(cv, m, pts, col):
    """Linha de emenda só dentro da máscara."""
    t = Cv(cv.w, cv.h)
    t.line(pts, "#ffffff")
    a = np.array(t.im)[:, :, 3] > 0
    cv.fill(a & m, col)


import math  # noqa: E402
import numpy as np  # noqa: E402


# =====================================================================================================================
# 3 · Transportador de carga (VÉSPER-7) · 128×112 · 4×3 tiles · porão traseiro aberto = boca
# =====================================================================================================================
def slab(cv, m, top_fn, hgt, cols, cuts):
    """Pinta `m` em faixas relativas a uma borda de cima inclinada: top_fn(x) -> y da borda."""
    def f(x, y):
        t = (y - top_fn(x)) / hgt
        k = sum(1 for c in cuts if t >= c)
        return cols[min(k, len(cols) - 1)]
    cv.paint(m, f)


def quad(p0, e1, e2):
    """Mapeia (u, v) em [0,1]² num paralelogramo p0 + u·e1 + v·e2 (o plano de cada face da caixa 3/4)."""
    return lambda u, v: (p0[0] + u * e1[0] + v * e2[0], p0[1] + u * e1[1] + v * e2[1])


def cargo(variant="A"):
    W, H = 128, 112
    cv = Cv(W, H)
    P = SLATE if variant == "A" else CREAM[1:]           # A ardósia (referência), B creme (família dos de hoje)
    hi = "#d4daee" if variant == "A" else CREAM[0]
    dk = "#262a42" if variant == "A" else "#6e6256"
    crA = ("#7f89ad", "#4b5273") if variant == "A" else ("#b38a5e", "#8a6a4a")
    cv.shadow_ell(64, 101, 62, 9)
    sand_pile(cv, 12, 98, 14, 5, 1)

    TL, TR, BL, BR = (6, 60), (80, 70), (6, 92), (80, 102)
    DX, DY = 22, -16
    sl = (TR[1] - TL[1]) / (TR[0] - TL[0])
    top = lambda x: TL[1] + (x - TL[0]) * sl
    S = quad(TL, (TR[0] - TL[0], TR[1] - TL[1]), (0, 32))            # costado
    R = quad(TL, (TR[0] - TL[0], TR[1] - TL[1]), (DX, DY))           # telhado (v=1 é o fundo)
    K = quad(TR, (DX, DY), (0, 32))                                  # tampa traseira (u profundidade, v altura)

    # braço da cauda (atrás), sobe e dobra
    arm = [(78, 58), (84, 36), (94, 24), (106, 20), (112, 24), (110, 32), (103, 33), (100, 46), (98, 60)]
    cv.poly(arm, P[3]); cv.poly([(81, 56), (87, 37), (96, 27), (106, 22), (108, 25), (99, 33), (94, 48), (92, 58)], P[2])
    cv.poly([(94, 24), (106, 20), (109, 23), (97, 27)], hi); cv.rect(86, 38, 7, 2, OR); cv.px(111, 26, "#ff5a4a"); cv.px(112, 25, "#ff5a4a")
    cv.line([(100, 44), (106, 38)], P[4]); cv.px(103, 34, P[4])

    roof = [R(0, 0), R(1, 0), R(1, 1), R(0, 1)]
    side = [S(0, 0), S(1, 0), S(1, 1), S(0, 1)]
    cap = [K(0, 0), K(1, 0), K(1, 1), K(0, 1)]
    mr, ms, mc = cv.pmask(roof), cv.pmask(side), cv.pmask(cap)
    slab(cv, ms, top, 34, [hi, P[0], P[1], P[2], P[3]], [.04, .3, .62, .9])
    # telhado: claro no fundo (luz), escurece pra frente
    def rf(x, y):
        # v do pixel dentro do telhado (0 = borda da frente, 1 = fundo)
        t = (top(x) - y) / (-DY)
        return P[0] if t > .75 else P[1] if t > .35 else P[2]
    cv.paint(mr, rf)
    cv.paint(mr, lambda x, y: hi if abs((top(x) - y) / (-DY) - 1) < .07 else None)
    for (u0, v0, u1, v1) in ((.38, 0, .34, 1), (.7, 0, .74, 1), (0, .45, 1, .5)):
        cv.line([R(u0, v0), R(u1, v1)], P[3])
    cv.speckle(mr, P[1], .22, 4)
    # placas do costado (emendas irregulares) e rebites
    for (u0, v0, u1, v1) in ((.3, 0, .28, 1), (.62, 0, .65, 1), (.0, .6, .45, .66), (.5, .7, 1, .74)):
        cv.line([S(u0, v0), S(u1, v1)], P[4])
    for k in range(7):
        cv.px(*map(int, S(.05 + k * .15, .08)), P[0])
    # faixa laranja do costado
    for x in range(TL[0] + 2, TR[0] - 1):
        y0 = int(top(x)) + 12
        cv.rect(x, y0, 1, 4, OR); cv.px(x, y0, OR_L); cv.px(x, y0 + 4, OR_D)
    # faixa laranja no telhado + placa chamuscada
    cv.poly([R(.12, .25), R(.34, .25), R(.34, .5), R(.12, .5)], OR); cv.line([R(.12, .5), R(.34, .5)], OR_D)
    cv.poly([R(.55, .3), R(.72, .3), R(.72, .45), R(.55, .45)], OR_D)
    # cockpit elevado
    q = quad(R(.05, .5), (16, 1), (10, -8))
    cv.poly([q(0, 0), q(1, 0), q(1, 1), q(0, 1)], P[2]); cv.poly([q(.1, .15), q(.9, .15), q(.9, .6), q(.1, .6)], "#17131e")
    cv.px(*map(int, q(.2, .3)), GLASS[0]); cv.px(*map(int, q(.3, .3)), GLASS[0])
    # "03"
    d0 = ["111", "101", "101", "101", "101", "101", "111"]
    d3 = ["111", "001", "001", "111", "001", "001", "111"]
    col03 = "#dde3f4" if variant == "A" else "#7a6e62"
    for k, dg in enumerate((d0, d3)):
        for j, row in enumerate(dg):
            for i, ch in enumerate(row):
                if ch == "1":
                    x = 30 + k * 5 + i
                    cv.px(x, int(top(x)) + 12 + 7 + j - 2, col03)
    for (u, v, rx, ry) in ((.52, .72, 6, 3), (.2, .8, 4, 3), (.85, .45, 3, 4)):
        x, y = S(u, v)
        m = cv.emask(x, y, rx, ry) & ms
        cv.fill(m, P[4]); cv.speckle(m, dk, .4, 7)
    cv.banded(mc, [P[2], P[3], P[4]], cuts=[.5, .85])
    cv.line([K(.5, 0), K(.5, 1)], P[4])

    # --- BOCA: buraco na tampa traseira + telhado rasgado em cima
    mouth_uv = [(.04, .22), (.3, .04), (.96, .05), (.98, .93), (.12, .95), (.0, .62)]
    mouth = [K(u, v) for u, v in mouth_uv]
    tear = [R(.6, .15), R(.7, .0), R(.86, .12), R(1.0, 0), R(1.0, .8), R(.9, 1.0), R(.78, .78), R(.68, .6)]
    mt = cv.pmask(tear) & mr
    mm = cv.pmask(mouth)
    cv.fill(mt | mm, (0, 0, 0, 0))
    inner = mm | mt
    cv.banded(inner, ["#6a5560", "#4a3a44", "#362a38", CAV[1]], cuts=[.25, .5, .78])
    # parede do fundo + costelas (arcos) em ferrugem
    for u in (.3, .52, .74, .94):
        pts = [K(u, .08 + abs(u - .6) * .1), K(u + .03, .5), K(u, .96)]
        cv.line(pts, RUST[1]); cv.line([(x + 1, y) for x, y in pts], RUST[3])
    cv.line([K(.1, .5), K(1, .46)], RUST[2])
    cv.speckle(inner, RUST[0], .1, 11)
    # carga dentro
    for (u, v, w, h, c) in ((.55, .38, 7, 8, crA), (.72, .55, 8, 9, ("#9a5a3a", "#6c4030"))):
        x, y = map(int, K(u, v))
        cv.rect(x, y, w, h, c[1]); cv.rect(x, y, w, 3, c[0]); cv.rect(x, y + 3, w, 1, OUT)
    # lábio torto da abertura
    for (x, y) in [K(u, v) for u, v in mouth_uv] + [R(.6, .15), R(.7, 0), R(.86, .12), R(.9, 1)]:
        cv.rect(int(x) - 2, int(y) - 1, 4, 3, P[2]); cv.px(int(x) - 2, int(y) - 1, P[0]); cv.px(int(x) + 1, int(y) + 1, OR_D)
    cv.line(mouth + [mouth[0]], OR_D)
    cv.line([R(.6, .15), R(.7, 0), R(.86, .12), R(1.0, 0)], OR_D)
    # chão do porão → RAMPA caída (a BOCA do porão)
    e = quad(BR, (DX, DY), (24, 4))           # sai da borda de baixo da tampa pra frente/direita
    ramp = [BR, (BR[0] + DX, BR[1] + DY), (BR[0] + DX + 24, BR[1] + DY + 4), (BR[0] + 24, BR[1] + 4)]
    cv.poly(ramp, OUT)
    inner_r = [(BR[0] + 1, BR[1]), (BR[0] + DX - 1, BR[1] + DY + 1), (BR[0] + DX + 23, BR[1] + DY + 4), (BR[0] + 23, BR[1] + 3)]
    r2 = cv.pmask(inner_r)
    cv.banded(r2, ["#d29a62", "#a76a44", "#7a4a34", "#5e3526"], cuts=[.2, .55, .85])
    for k in range(5):
        a_, b_ = e(.1 + k * .2, 0.05), e(.1 + k * .2, 1)
        cv.line([a_, b_], "#5e3526")
    # rampa da frente: faixa de perigo na ponta (soleira)
    for k in range(6):
        x = BR[0] + 24 + k * 0 - 1
    for k in range(5):
        cv.rect(BR[0] + 2 + k * 4, BR[1] + 3 + (k * 1) // 3, 2, 2, "#f2c46d" if k % 2 == 0 else "#3b3f46")
    # caixas caídas
    cv.rect(108, 95, 12, 10, OUT); cv.rect(109, 96, 10, 8, "#6c4030"); cv.rect(109, 96, 10, 3, "#9a5a3a"); cv.rect(109, 99, 10, 1, OUT)
    cv.rect(118, 86, 9, 10, OUT); cv.rect(119, 87, 7, 8, crA[1]); cv.rect(119, 87, 7, 3, crA[0])
    cv.rect(4, 94, 9, 8, OUT); cv.rect(5, 95, 7, 6, "#6c4030"); cv.rect(5, 95, 7, 2, "#9a5a3a")
    # antena torta com luz vermelha
    cv.rect(10, 32, 2, 24, METAL[2]); cv.px(10, 32, METAL[0]); cv.rect(9, 29, 4, 3, "#ff5a4a"); cv.px(9, 29, "#ffb0a0")
    cv.rect(18, 95, 14, 3, METAL[3]); cv.rect(56, 102, 16, 3, METAL[3])
    sand_pile(cv, 40, 100, 24, 4, 2)
    scatter(cv, [(2, 106), (46, 106), (66, 108), (30, 108), (84, 109), (124, 109), (1, 98), (20, 104)], 3)
    cv.outline()
    return cv


# =====================================================================================================================
# 2 · Base espacial (vira o módulo da colônia) · domo partido sobre um anel + torre + terminal
# =====================================================================================================================
LAV = ["#d9dbe8", "#b9bccf", "#8f93ad", "#6b6f8c"]      # painéis frios (as paredes da base do player usam esse tom)


def arc(cv, cx, cy, rx, ry, a0, a1, col, n=60, w=1):
    pts = [(cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        cv.line([(x0, y0), (x1, y1)], col, w)
    return pts


def module(tw, th, tower=True):
    """tw×th tiles de pegada; o sprite tem 24 px de lift em cima (domo, torre e antenas)."""
    LIFT = 24
    W, H = tw * 32, th * 32 + LIFT
    cv = Cv(W, H)
    k = tw / 5.0                                          # escala relativa à versão 5×4
    cx = int(W * (0.42 if tower else 0.5))
    ground = H - 10                                       # linha do pé do anel (frente)
    ry = int(26 * k * (th / 4.0) ** .5 * 1.05)
    rx = int(66 * k)
    wall = 11
    cy = ground - wall - ry                               # centro da elipse do topo do anel
    cv.shadow_ell(cx + 4, ground - 4, rx + 10, ry * .75 + 5)
    # --- torre (atrás do anel, à direita)
    if tower:
        tx = int(W - 15 * k - 11); tw_ = int(24 * k) // 2
        tb = cy + 4                                       # chão da torre
        ttop = LIFT + 6
        bodym = cv.mask(lambda d: d.rectangle([tx - tw_, ttop, tx + tw_, tb], fill=255)) | cv.emask(tx, tb, tw_ + .5, 5) | cv.emask(tx, ttop, tw_ + .5, 5)
        cv.paint(bodym, lambda x, y: [CREAM[0], CREAM[1], CREAM[2], CREAM[3], CREAM[4], CREAM[5]][min(5, int((x - (tx - tw_)) / (2 * tw_ + 1) * 6))] if y > ttop + 3 else None)
        cv.fill(cv.emask(tx, ttop, tw_ + .5, 5), CREAM[1])
        cv.fill(cv.emask(tx - 1, ttop - 1, tw_ - 3, 2.5), CREAM[0])
        for (y0, h_) in ((ttop + 14, 4), (ttop + 34, 5)):
            for x in range(tx - tw_, tx + tw_ + 1):
                t = (x - (tx - tw_)) / (2 * tw_ + 1)
                yy = y0 + int(2.2 * math.sqrt(max(0, 1 - ((x - tx) / (tw_ + .5)) ** 2)))
                cv.rect(x, yy, 1, h_, OR if t < .6 else OR_D); cv.px(x, yy, OR_L if t < .4 else OR)
        cv.line([(tx - tw_ + 1, ttop + 24), (tx + tw_ - 1, ttop + 27)], CREAM[5])
        for y in range(ttop + 8, tb - 4, 11):
            cv.px(tx - 3, y, CREAM[5]); cv.px(tx + 4, y + 3, CREAM[5])
        cv.rect(tx - 1, ttop - 18, 2, 14, METAL[2]); cv.rect(tx - 3, ttop - 8, 6, 1, METAL[2]); cv.rect(tx - 2, ttop - 21, 4, 3, "#ff5a4a")
        cv.rect(tx - tw_ - 2, tb - 12, 2, 12, METAL[3])          # perna quebrada
        cv.line([(tx - tw_ + 2, ttop + 12), (tx - tw_ + 8, ttop + 20), (tx - tw_ + 3, ttop + 30)], CREAM[5])   # rachadura
    # --- anel: parede (cilindro) + topo
    wall_m = cv.emask(cx, cy + wall, rx, ry) | cv.mask(lambda d: d.rectangle([cx - rx, cy, cx + rx - 1, cy + wall], fill=255))
    wall_m &= ~(cv.emask(cx, cy, rx, ry) & (np.arange(H)[:, None] < cy))
    def wallc(x, y):
        t = (x - cx) / rx
        c = CREAM[1] if t < -.55 else CREAM[2] if t < -.1 else CREAM[3] if t < .45 else CREAM[4] if t < .8 else CREAM[5]
        ey = cy + ry * math.sqrt(max(0, 1 - t * t))
        d = y - ey
        if 3 <= d <= 5.2:
            return OR if t < .5 else OR_D
        if d < 1:
            return CREAM[0] if t < 0 else CREAM[2]
        return c
    cv.paint(wall_m, wallc)
    for ang in (.25, .62, .9, 1.35, 1.75, 2.25, 2.8):               # emendas verticais da parede, ângulos irregulares
        x = cx + rx * math.cos(ang); y = cy + ry * math.sin(ang)
        cv.line([(x, y + 1), (x + (1 if ang > 1.6 else 0), y + wall)], CREAM[5])
    top_m = cv.emask(cx, cy, rx, ry)
    inner_rx, inner_ry = int(rx * .72), int(ry * .72)
    hole = cv.emask(cx, cy, inner_rx, inner_ry)
    ring_m = top_m & ~hole
    def ringc(x, y):
        t = (x - cx) / rx
        u = (y - cy) / ry
        return CREAM[0] if (t + u) < -.9 else CREAM[1] if t < .2 else CREAM[2] if t < .6 else CREAM[3]
    cv.paint(ring_m, ringc)
    # emendas radiais do topo do anel, laranja em alguns blocos, painéis frios
    for i, ang in enumerate((0.15, 0.55, 0.95, 1.3, 1.7, 2.1, 2.55, 2.95, 3.5, 4.0, 4.5, 5.0, 5.55, 6.0)):
        x0, y0 = cx + inner_rx * math.cos(ang), cy + inner_ry * math.sin(ang)
        x1, y1 = cx + rx * math.cos(ang), cy + ry * math.sin(ang)
        cv.line([(x0, y0), (x1, y1)], CREAM[4])
        if i % 4 == 1:
            a2 = ang + .2
            for rr in (.88, .94):
                pass
    for (a0, a1) in ((.6, 1.3), (2.1, 2.9), (3.6, 4.2), (5.0, 5.8)):               # faixa laranja em arco no topo do anel
        arc(cv, cx, cy, (rx + inner_rx) / 2, (ry + inner_ry) / 2, a0, a1, OR, 12, 3)
        arc(cv, cx, cy, (rx + inner_rx) / 2, (ry + inner_ry) / 2 + 1.5, a0, a1, OR_D, 12, 1)
    for (a0, a1) in ((1.0, 1.6), (3.0, 3.3)):
        arc(cv, cx, cy, (rx + inner_rx) / 2 + 3, (ry + inner_ry) / 2 + 2, a0, a1, LAV[1], 10, 2)
    # miolo do anel: o chão da base lá dentro (escuro) com o domo em cima
    cv.fill(hole, CAV[0])
    cv.paint(hole, lambda x, y: CAV[1] if y > cy + inner_ry * .3 else None)
    # --- domo
    dr = int(inner_rx * .84)
    dh = int(52 * k * (th / 4.0) ** .5 * 1.1) if th >= 4 else int(40 * k * 1.2)
    dby = cy + 2                                              # centro da base do domo
    dry = int(inner_ry * .88)
    dome_m = cv.emask(cx, dby, dr, dry) | (cv.emask(cx, dby, dr, dh) & (np.arange(H)[:, None] <= dby))
    def domec(x, y):
        tx_ = (x - cx) / dr
        f = (dby - y) / dh
        lit = -.55 * tx_ + .55 * f
        c = CREAM[0] if lit > .72 else CREAM[1] if lit > .45 else CREAM[2] if lit > .2 else CREAM[3] if lit > -.1 else CREAM[4] if lit > -.35 else CREAM[5]
        return c
    cv.paint(dome_m, domec)
    # meridianos (painéis) e paralelos; alguns painéis frios
    import math as m_
    def meridian(psi, col, w=1):
        pts = []
        for i in range(25):
            f = i / 24 * 0.985
            r_ = m_.sqrt(1 - f * f)
            pts.append((cx + dr * r_ * m_.cos(psi), dby - f * dh + dry * r_ * m_.sin(psi)))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            cv.line([(x0, y0), (x1, y1)], col, w)
    for psi in (0.15, 0.6, 1.05, 1.5, 1.95, 2.4, 2.95):
        meridian(psi, CREAM[4])
    for f_, col, wd in ((.18, OR_D, 1), (.55, CREAM[4], 1)):
        r_ = m_.sqrt(1 - f_ * f_)
        arc(cv, cx, dby - f_ * dh, dr * r_, dry * r_, .02, m_.pi - .02, col, 40, wd)
    r_ = m_.sqrt(1 - .3 * .3)
    arc(cv, cx, dby - .3 * dh, dr * r_, dry * r_, .05, m_.pi - .05, OR, 40, 2)
    # painéis frios (lavanda) em 2 gomos
    pan = cv.emask(cx, dby, dr - 1, dh) & (np.arange(H)[:, None] <= dby)
    cv.paint(pan, lambda x, y: LAV[1] if (cx + 6 < x < cx + 15 and dby - dh * .75 < y < dby - dh * .32) else LAV[2] if (cx - 22 < x < cx - 14 and dby - dh * .6 < y < dby - dh * .36) else None)
    # BURACO: o domo está partido (parte de cima e da direita)
    hx, hy = cx + int(dr * .12), dby - int(dh * .62)
    brk = []
    nb = 18
    for i in range(nb):
        an = 2 * math.pi * i / nb
        rr = (1.0 + (0.24 if i % 2 else -0.1) * (1 if hsh(i, tw, 4) > .35 else .3) + .15 * hsh(i, th, 8)) * 15 * min(1.0, dh / 52)
        brk.append((hx + rr * math.cos(an) * 1.05, hy + rr * math.sin(an) * .95 + (-3 if math.sin(an) < 0 else 2)))
    mb = cv.pmask(brk) & dome_m
    cv.fill(mb, CAV[1])
    cv.paint(mb, lambda x, y: CAV[0] if y < hy - 4 else CAV[2] if y > hy + 6 else None)
    # costelas internas (vigas ferrugem) atravessando o buraco
    cv.line([(hx - 12, hy - 8), (hx + 2, hy + 1), (hx + 14, hy - 6)], RUST[1], 2)
    cv.line([(hx - 4, hy - 15), (hx - 2, hy + 12)], RUST[2]); cv.line([(hx + 8, hy - 18), (hx + 10, hy + 9)], RUST[2])
    for (x, y) in brk:                                      # lábio rasgado
        cv.rect(x - 1, y - 1, 3, 3, CREAM[3] if x < hx else CREAM[4]); cv.px(x, y + 1, OR_D)
    cv.line(brk + [brk[0]], OR_D)
    for (x, y) in ((hx - 6, hy - 14), (hx + 12, hy - 12)):
        cv.px(x, y - 2, CREAM[0])
    # antenas no topo do domo
    ax = cx - int(dr * .78)
    cv.rect(ax, 2, 2, int(dby - dh * .55) - 2, METAL[2]); cv.rect(ax - 3, 10, 8, 1, METAL[2]); cv.rect(ax - 1, 0, 4, 3, "#ff5a4a"); cv.px(ax - 1, 0, "#ffb0a0")
    cv.rect(ax + 9, 14, 2, int(dby - dh * .4) - 14, METAL[3]); cv.rect(ax + 8, 12, 4, 3, METAL[0])
    # --- vão no anel (parte da parede e do topo caída) na frente-direita + entulho
    ga = (0.85, 1.35)
    gap = [(cx + rx * math.cos(a_), cy + ry * math.sin(a_) + 1) for a_ in (ga[0], .95, 1.1, 1.25, ga[1])]
    gp = gap + [(gap[-1][0] - 4, gap[-1][1] + wall + 3), (gap[0][0] + 4, gap[0][1] + wall + 3)]
    gm = cv.pmask(gp) & (wall_m | top_m)
    cv.fill(gm, (0, 0, 0, 0))
    gm2 = gm & ~hole
    cv.fill(gm2 & (np.arange(H)[:, None] > cy + inner_ry - 2), CAV[1])
    # terminal na parede da frente-esquerda (tela verde apagada pela metade)
    tzx, tzy = (38, LIFT + (th - 1) * 32 + 4)          # dentro do tile (1, th-1), de ponta a ponta
    cv.rect(tzx, tzy, 20, 17, OUT)
    cv.rect(tzx + 1, tzy + 1, 18, 15, CREAM[1]); cv.rect(tzx + 1, tzy + 13, 18, 3, CREAM[4])
    cv.rect(tzx + 3, tzy + 3, 14, 9, "#102018"); cv.rect(tzx + 4, tzy + 4, 8, 1, "#7fd67a"); cv.rect(tzx + 4, tzy + 6, 11, 1, "#4aa860"); cv.rect(tzx + 4, tzy + 8, 6, 1, "#7fd67a")
    cv.rect(tzx + 14, tzy + 14, 3, 1, OR)
    cv.rect(tzx + 2, tzy + 17, 16, 3, OUT) if False else None
    cv.terminal_rect = (tzx, tzy, 20, 17)
    # entulho, placas caídas, sucata
    sand_pile(cv, cx - rx + 8, ground - 4, 12, 5, 5)
    sand_pile(cv, cx + int(rx * .6), ground - 1, 16, 5, 6)
    def slabbit(x, y, w, h, c0=CREAM[2], c1=CREAM[4]):
        cv.rect(x, y, w, h, c1); cv.rect(x, y, w, max(1, h // 3), c0); cv.rect(x, y, w, 1, CREAM[0])
        cv.px(x + w - 2, y + h - 1, OR_D)
    slabbit(cx + int(rx * .22), ground - 3, 14, 5); slabbit(cx + int(rx * .5), ground - 7, 12, 5); slabbit(cx - int(rx * .95), ground - 11, 10, 4)
    cv.rect(cx + int(rx * .3), ground - 11, 9, 4, METAL[3]); cv.rect(cx + int(rx * .3), ground - 11, 9, 1, METAL[1])
    scatter(cv, [(4, H - 6), (cx - int(rx * .7), H - 4), (cx + int(rx * .1), H - 3), (W - 20, H - 5), (W - 40, H - 8), (cx + int(rx * .85), H - 12), (6, H - 18)], 5)
    cv.outline()
    return cv


# =====================================================================================================================
# 4 · Sonda (troca a wreck_probe) · 64×64 · 2×2 tiles
# =====================================================================================================================
SOLAR = ["#9cc0ff", "#3d63a8", "#27468a", "#1f3a6e", "#142a52"]


def panel(cv, p0, ex, ey, nx, ny, tear=None):
    """Painel solar: paralelogramo p0 + u·ex + v·ey com grade nx×ny. tear = (u,v) cantos arrancados."""
    q = quad(p0, ex, ey)
    pts = [q(0, 0), q(1, 0), q(1, 1), q(0, 1)]
    cv.poly([(x + (1 if i in (1, 2) else -1) * 0, y) for i, (x, y) in enumerate(pts)], METAL[3])
    m = cv.pmask(pts)
    cv.fill(m, SOLAR[1])
    cv.paint(m, lambda x, y: SOLAR[0] if (x + y) % 11 == 0 else None)
    for i in range(1, nx):
        cv.line([q(i / nx, 0), q(i / nx, 1)], SOLAR[3])
    for j in range(1, ny):
        cv.line([q(0, j / ny), q(1, j / ny)], SOLAR[3])
    cv.line([q(0, 0), q(1, 0)], SOLAR[0]); cv.line([q(0, 1), q(1, 1)], SOLAR[4])
    if tear:
        u, v = tear
        cv.fill(cv.pmask([q(u, 0), q(1, 0), q(1, v), q(u + .1, v * .6)]) & m, (0, 0, 0, 0))
        cv.line([q(u, 0), q(u + .1, v * .6), q(1, v)], METAL[2])


def probe():
    cv = Cv(64, 64)
    cv.shadow_ell(32, 54, 28, 6)
    sand_pile(cv, 30, 54, 25, 5, 4)
    # painel esquerdo (baixo, apoiado no chão) e direito (levantado, rasgado)
    panel(cv, (3, 44), (18, -8), (-3, 10), 4, 3)
    panel(cv, (44, 36), (16, -12), (4, 10), 3, 3)
    cv.line([(18, 42), (24, 44)], METAL[2], 2); cv.line([(44, 40), (40, 42)], METAL[2], 2)
    # parabólica (torta) em cima à esquerda
    cv.line([(25, 24), (23, 15)], METAL[2], 2)
    dish = cv.emask(23, 12, 11, 7)
    cv.banded(dish, [CREAM[0], CREAM[2], CREAM[3], CREAM[4]], cuts=[.2, .5, .8])
    cv.fill(cv.emask(22, 11, 6, 3.5), CREAM[4]); cv.fill(cv.emask(22, 10, 3.5, 2), CREAM[5])
    cv.line([(22, 11), (30, 4)], METAL[2]); cv.rect(30, 3, 2, 2, "#ff5a4a"); cv.line([(24, 17), (28, 26)], METAL[2], 2)
    # corpo esférico
    body = cv.emask(32, 38, 14, 13)
    def bc(x, y):
        lit = -.6 * (x - 32) / 14 - .8 * (y - 38) / 13
        return CREAM[0] if lit > .62 else CREAM[1] if lit > .3 else CREAM[2] if lit > -.05 else CREAM[3] if lit > -.4 else CREAM[4]
    cv.paint(body, bc)
    arc(cv, 32, 38, 14, 5, .05, math.pi - .05, OR, 30, 3)       # cinta laranja
    arc(cv, 32, 39.5, 14, 5, .05, math.pi - .05, OR_D, 30, 1)
    arc(cv, 32, 30, 12, 3, .2, math.pi - .2, CREAM[4], 20, 1)
    cv.fill(cv.emask(32, 31, 4.5, 2.5) | cv.emask(32, 33, 5, 2), OUT)   # lente
    cv.fill(cv.emask(32, 32, 3.5, 2), "#3a5068"); cv.px(31, 31, GLASS[0]); cv.px(32, 31, GLASS[0])
    cv.line([(22, 40), (25, 48)], CREAM[5]); cv.line([(25, 48), (23, 51)], CREAM[5])        # rachadura
    cv.fill(cv.emask(40, 46, 3, 2), CAV[1])                                             # furo
    # bocal/canhão virado pra frente-direita
    nz = [(36, 46), (50, 51), (52, 55), (38, 52)]
    cv.poly(nz, METAL[3]); cv.poly([(36, 46), (50, 51), (50, 52), (36, 48)], METAL[0])
    cv.fill(cv.emask(51, 54, 2.5, 2), CAV[2]); cv.px(50, 52, OR)
    # LED piscante (x=23,y=37 fica reservado: a prévia pisca 2×1 px nele)
    cv.rect(23, 37, 2, 1, "#ff5a4a")
    # patas e sucata
    cv.rect(18, 50, 3, 5, METAL[3]); cv.rect(44, 52, 3, 4, METAL[3])
    cv.rect(52, 36, 8, 7, OUT) if False else None
    scatter(cv, [(4, 56), (10, 58), (54, 58), (30, 59), (58, 52), (2, 52), (46, 58)], 9)
    cv.rect(46, 44, 9, 7, METAL[4]); cv.rect(46, 44, 9, 2, METAL[1])        # caixinha de instrumentos
    cv.outline()
    return cv


# =====================================================================================================================
# 5 · Robô de reconhecimento (esteiras) · 64×64 · 2×2 tiles
# =====================================================================================================================
def track(cv, x0, y0, w, h, dark=False, tilt=0):
    """Esteira: barra arredondada com sapatas (costelas) e rodas aparecendo."""
    m = cv.mask(lambda d: d.rounded_rectangle([x0, y0, x0 + w - 1, y0 + h - 1], radius=h // 2, fill=255))
    cols = ["#4a4f57", "#3b3f46", "#2a2d33", "#1f2126"] if not dark else ["#3b3f46", "#2a2d33", "#1f2126", "#17181c"]
    cv.banded(m, cols, cuts=[.3, .65, .9])
    for x in range(x0 + 3, x0 + w - 2, 4):
        cv.line([(x, y0 + 1), (x, y0 + h - 2)], cols[3])
        cv.px(x + 1, y0 + 1, METAL[1] if not dark else METAL[3])
    cv.fill(cv.emask(x0 + w * .22, y0 + h / 2, 2.5, 2.5), METAL[2]); cv.fill(cv.emask(x0 + w * .78, y0 + h / 2, 2.5, 2.5), METAL[2])
    cv.px(x0 + w * .22 - 1, y0 + h / 2 - 1, METAL[0])


def robot():
    cv = Cv(64, 64)
    cv.shadow_ell(32, 55, 29, 6)
    sand_pile(cv, 28, 55, 25, 5, 6)
    # esteira de trás (escura) e corpo
    track(cv, 14, 33, 40, 11, dark=True)
    body = [(14, 24), (22, 17), (50, 19), (54, 26), (52, 40), (16, 42)]
    cv.poly(body, CREAM[3])
    mb = cv.pmask(body)
    cv.banded(mb, [CREAM[0], CREAM[1], CREAM[2], CREAM[3], CREAM[4]], cuts=[.12, .4, .65, .88])
    cv.poly([(14, 28), (52, 28), (52, 33), (14, 33)] , OR); cv.rect(14, 33, 38, 1, OR_D); cv.rect(14, 28, 38, 1, OR_L)
    cv.line([(30, 20), (28, 40)], CREAM[4]); cv.line([(42, 21), (44, 40)], CREAM[4])
    cv.fill(cv.emask(46, 36, 3, 2), CREAM[5]); cv.speckle(mb, CREAM[4], .2, 5)
    cv.rect(18, 36, 6, 3, "#17131e"); cv.rect(19, 37, 4, 1, "#7fd67a")      # painelzinho
    # mastro com cabeça de câmera
    cv.rect(31, 11, 4, 8, METAL[2])
    head = cv.mask(lambda d: d.rectangle([24, 3, 41, 12], fill=255))
    cv.banded(head, [CREAM[0], CREAM[1], CREAM[3], CREAM[4]], cuts=[.2, .6, .85])
    cv.rect(25, 7, 16, 2, OR); cv.fill(cv.emask(30, 8, 3.5, 3), OUT); cv.fill(cv.emask(30, 8, 2.5, 2), "#ff8a4a"); cv.px(29, 7, "#ffe0b0")
    cv.rect(37, 4, 3, 3, METAL[3])
    cv.line([(47, 22), (50, 6)], METAL[2]); cv.rect(49, 3, 3, 3, "#ff5a4a")        # antena
    # braço dobrado na frente
    cv.line([(20, 40), (14, 46), (18, 50)], METAL[2], 2); cv.rect(15, 49, 5, 3, METAL[3])
    # esteira da frente (grande) e a solta
    track(cv, 6, 40, 42, 14)
    cv.speckle(cv.mask(lambda d: d.rounded_rectangle([6, 40, 47, 53], radius=7, fill=255)), "#5a6069", .15, 4)
    sl = quad((42, 52), (18, -5), (-3, 8))
    pts = [sl(0, 0), sl(1, 0), sl(1, 1), sl(0, 1)]
    cv.poly(pts, "#2a2d33"); cv.line([sl(0, 0), sl(1, 0)], METAL[3])
    for i in range(1, 7):
        cv.line([sl(i / 7, 0), sl(i / 7, 1)], "#1f2126")
    # caixa de componentes caída
    cv.rect(50, 34, 12, 10, OUT); cv.rect(51, 35, 10, 8, CREAM[2]); cv.rect(51, 35, 10, 3, CREAM[0]); cv.rect(51, 38, 10, 1, CREAM[4]); cv.rect(53, 40, 4, 1, OR)
    scatter(cv, [(2, 56), (4, 60), (30, 60), (58, 60), (2, 46), (40, 61)], 12)
    cv.outline()
    return cv


# =====================================================================================================================
# 1 · Nave de passageiros (NOVA: a que trouxe a colônia) · 160×120 · 5×3 tiles (24 px de lift)
# =====================================================================================================================
def liner():
    W, H = 160, 120
    cv = Cv(W, H)
    cv.shadow_ell(80, 104, 74, 11)
    sand_pile(cv, 14, 98, 14, 7, 1)
    # cauda (deriva vertical) atrás do casco
    fin = [(116, 66), (126, 22), (144, 10), (150, 14), (144, 58), (140, 70)]
    cv.poly(fin, LAV[2]); cv.poly([(119, 64), (128, 26), (144, 13), (146, 16), (138, 56), (134, 68)], LAV[1])
    cv.poly([(128, 26), (144, 13), (146, 16), (130, 30)], LAV[0]); cv.rect(130, 36, 14, 4, OR); cv.rect(138, 20, 3, 8, OR_D)
    cv.line([(134, 44), (140, 56), (138, 64)], LAV[3]); cv.fill(cv.pmask([(142, 44), (150, 46), (146, 56)]), (0, 0, 0, 0))
    # asa de trás (do outro lado, aparece acima do casco)
    cv.poly([(90, 54), (112, 36), (126, 38), (110, 58)], LAV[3])
    # fuselagem: capsula horizontal, nariz à esquerda (cabine) enterrado na areia
    def hh(x):                                           # meia altura do casco por x (nariz elíptico, cauda afinando)
        if x < 40:
            return 6 + 18 * math.sqrt(max(0, 1 - ((40 - x) / 37) ** 2))
        if x > 130:
            return 24 - (x - 130) * .62
        return 24
    x0, x1 = 4, 148
    cy = lambda x: 74 + (8 if x < 40 else 0) * (40 - x) / 36 * 0.0 - (x - 4) * 0.02
    fus = []
    for x in range(x0, x1 + 1):
        fus.append((x, cy(x) - hh(x)))
    for x in range(x1, x0 - 1, -1):
        fus.append((x, cy(x) + hh(x) * .95))
    mf = cv.pmask(fus)
    def fc(x, y):
        t = (y - (cy(x) - hh(x))) / (2 * hh(x))
        return CREAM[0] if t < .06 else CREAM[1] if t < .3 else CREAM[2] if t < .55 else CREAM[3] if t < .78 else CREAM[4] if t < .93 else CREAM[5]
    cv.paint(mf, fc)
    # painéis lavanda (as chapas azuladas da referência), irregulares
    for (xa, xb, ta, tb) in ((44, 70, .12, .5), (96, 112, .55, .9), (20, 36, .55, .85), (118, 132, .1, .4)):
        pm = cv.mask(lambda d: d.rectangle([xa, 0, xb, H], fill=255)) & mf
        cv.paint(pm, lambda x, y: (LAV[0] if (y - (cy(x) - hh(x))) / (2 * hh(x)) < (ta + tb) / 2 - .1 else LAV[1]) if ta < (y - (cy(x) - hh(x))) / (2 * hh(x)) < tb else None)
    # emendas de painel (irregulares) e rebites
    for (xx, ya, yb) in ((22, 0, 1), (43, 0, 1), (71, 0, 1), (96, 0, 1), (118, 0, 1), (132, 0, 1)):
        cv.line([(xx, cy(xx) - hh(xx) + 1), (xx + 2, cy(xx) + hh(xx) - 2)], CREAM[4])
    cv.speckle(mf, CREAM[4], .18, 21)
    # faixa laranja ao longo da fuselagem (segmentada)
    for (xa, xb) in ((28, 66), (76, 104), (120, 140)):
        for x in range(xa, xb):
            y = int(cy(x) + 3)
            cv.rect(x, y, 1, 4, OR); cv.px(x, y, OR_L); cv.px(x, y + 4, OR_D)
    # janelas de passageiros (fileira)
    for x in range(40, 124, 9):
        if 78 < x < 100:
            continue
        y = int(cy(x) - 9)
        cv.rect(x, y, 5, 4, "#17131e"); cv.rect(x + 1, y + 1, 3, 2, GLASS[1]); cv.px(x + 1, y + 1, GLASS[0])
    # cabine: vidro azul grande no nariz com reflexos
    cab = [(8, 70), (16, 60), (30, 56), (34, 66), (22, 76)]
    cv.poly(cab, "#17131e")
    cab2 = cv.pmask([(10, 70), (17, 62), (28, 59), (31, 66), (22, 74)])
    cv.banded(cab2, [GLASS[0], "#4d78a8", GLASS[1], GLASS[2]], cuts=[.2, .5, .8])
    cv.line([(12, 69), (20, 62)], "#d6ecff"); cv.line([(23, 60), (25, 72)], "#17131e"); cv.rect(14, 74, 6, 2, "#17131e")
    cv.px(27, 62, "#17131e"); cv.line([(9, 71), (21, 77)], "#17131e")
    # ROMBO na meia-nau: casco aberto, estrutura à mostra
    gap = [(74, 56), (82, 52), (90, 56), (98, 54), (104, 62), (100, 74), (104, 84), (92, 92), (84, 88), (78, 94), (72, 84), (76, 72), (70, 64)]
    mg = cv.pmask(gap) & mf
    cv.fill(mg, CAV[1])
    cv.paint(mg, lambda x, y: "#4a3a44" if y < 66 else CAV[0] if y < 80 else CAV[2])
    for xx in (78, 86, 94):
        cv.line([(xx, 56), (xx + 2, 74), (xx + 1, 90)], RUST[1]); cv.line([(xx + 1, 56), (xx + 3, 74), (xx + 2, 90)], RUST[3])
    cv.line([(74, 66), (102, 68)], RUST[2]); cv.line([(74, 80), (102, 82)], RUST[2])
    # poltronas aparecendo (2 cabecinhas azuladas)
    for xx in (80, 92):
        cv.rect(xx, 68, 6, 6, LAV[3]); cv.rect(xx, 68, 6, 2, LAV[2]); cv.rect(xx + 1, 74, 4, 3, "#4b5273")
    for (x, y) in gap:
        cv.rect(x - 2, y - 1, 4, 3, CREAM[3]); cv.px(x - 2, y - 1, CREAM[1]); cv.px(x + 1, y + 1, OR_D)
    cv.line(gap + [gap[0]], OR_D)
    # buraco menor no nariz (rombo) e amassados
    for (x, y, rx, ry) in ((44, 88, 6, 3), (60, 64, 4, 3), (118, 82, 5, 3)):
        m = cv.emask(x, y, rx, ry) & mf
        cv.fill(m, CREAM[5]); cv.speckle(m, "#4d433e", .4, 7)
    # asa da frente (apoiada na areia) e carenagem
    wing = [(58, 84), (96, 88), (104, 100), (74, 106), (48, 98)]
    cv.poly(wing, LAV[3])
    cv.poly([(60, 85), (95, 89), (101, 98), (74, 103), (52, 97)], LAV[2])
    cv.poly([(60, 85), (95, 89), (97, 91), (62, 88)], LAV[0]); cv.rect(70, 92, 20, 3, OR)
    cv.line([(64, 98), (88, 99)], LAV[3])
    # motor traseiro: nacela (cilindro com anel escuro) e 2º bocal partido
    nac = cv.mask(lambda d: d.rounded_rectangle([132, 62, 156, 86], radius=6, fill=255))
    cv.banded(nac, [METAL[0], METAL[1], METAL[2], METAL[3], METAL[4]], cuts=[.12, .35, .6, .85])
    cv.fill(cv.emask(152, 74, 4, 10), METAL[4]); cv.fill(cv.emask(153, 74, 2.5, 7), CAV[2])
    cv.rect(138, 66, 10, 2, OR); cv.line([(136, 72), (136, 84)], METAL[4])
    # antena + LED
    cv.rect(46, 30, 2, 26, METAL[2]); cv.rect(44, 40, 6, 1, METAL[2]); cv.rect(45, 27, 4, 3, "#ff5a4a"); cv.px(45, 27, "#ffb0a0")
    sand_pile(cv, 24, 90, 20, 6, 3)
    sand_pile(cv, 126, 96, 18, 5, 4)
    # sucata + poltronas soltas
    cv.rect(100, 100, 12, 6, METAL[4]); cv.rect(100, 100, 12, 2, METAL[1]); cv.rect(124, 104, 10, 5, LAV[3]); cv.rect(124, 104, 10, 2, LAV[1])
    scatter(cv, [(4, 108), (36, 108), (54, 110), (84, 112), (112, 110), (146, 108), (152, 100), (6, 92), (70, 110)], 11)
    cv.outline()
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    cv = cargo("A"); cv.check(); cv.image().save(PEND / "wreck_cargo_A.png")
    cv = cargo("B"); cv.check(); cv.image().save(PEND / "wreck_cargo_B.png")
    for nm, fn in (("probe", probe), ("robot", robot), ("liner", liner)):
        cv = fn(); cv.check(); cv.image().save(PEND / f"wreck_{nm}.png")
    for tag, (tw, th, tower) in {"A": (5, 4, True), "B": (4, 3, True)}.items():
        cv = module(tw, th, tower); cv.check(); cv.image().save(PEND / f"wreck_module_{tag}.png")
        print("module", tag, cv.w, cv.h, cv.terminal_rect)


if __name__ == "__main__":
    main()
