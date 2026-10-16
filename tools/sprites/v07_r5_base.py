#!/usr/bin/env python3
"""v0.7 Lore · rodada 5 · base espacial de vidro em ISOMÉTRICO (diagonal, 2:1). 224×160.

    python3 tools/sprites/v07_r5_base.py   ->  pendentes/r5_wreck_module_glass.png
Mesmo design aprovado (domo de vidro estilhaçado, janelões, eclusa com porta e rampa, módulo-tanque, painéis solares),
com caixas isométricas (topo + 2 faces) e o tambor circular. Eixos como no r5_cargo: P(u,v,z) = (X0+u−v, Y0+(u+v)/2−z).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_destrocos import CAV, CREAM, METAL, OR, OR_D, OR_L, RUST, arc  # noqa: E402
from v07_lib import Cv, OUT, hsh, sand_pile, scatter  # noqa: E402
from v07_r2_destrocos import BGR, GL, INT, pane  # noqa: E402
from v07_r3_base import shade_region  # noqa: E402
from v07_r3_cargo import plate  # noqa: E402
from v07_r5_cargo import Iso  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"
BD = "#4a4256"
TONES = [(CREAM[0], CREAM[1], CREAM[2]), (CREAM[2], CREAM[3], CREAM[4]), (CREAM[3], CREAM[4], CREAM[5])]


def base5():
    W, H = 256, 168
    cv = Cv(W, H)
    iso = Iso(cv, 128, 62)
    P = iso.P
    cv.shadow_ell(132, 120, 116, 24)
    sand_pile(cv, 14, 122, 12, 4, 1); sand_pile(cv, 242, 124, 12, 4, 2)

    # ---- painéis solares (atrás, à direita), no plano u=const, com espessura e poste; o da direita com canto arrancado
    def solar(u, v0, v1, z0, z1, hole=False):
        for vp in ((v0 + v1) / 2,):
            a, b = P(u, vp, 0), P(u, vp, z0 + 2)
            cv.line([a, b], METAL[3], 3)
        cv.poly([P(u + 3, v0, z0), P(u + 3, v1, z0), P(u + 3, v1, z1), P(u + 3, v0, z1)], METAL[4])
        q = [P(u, v0, z0), P(u, v1, z0), P(u, v1, z1), P(u, v0, z1)]
        cv.poly(q, METAL[3]); m = cv.pmask([P(u, v0 + 1, z0 + 1), P(u, v1 - 1, z0 + 1), P(u, v1 - 1, z1 - 1), P(u, v0 + 1, z1 - 1)])
        cv.banded(m, ["#5b86d0", "#3d63a8", "#2f5090"], cuts=[.3, .7])
        cv.paint(m, lambda x, y: "#bcd6ff" if (x + y * 2) % 13 == 0 else None)
        for k in range(1, 4):
            cv.line([P(u, v0 + (v1 - v0) * k / 4, z0), P(u, v0 + (v1 - v0) * k / 4, z1)], "#1f3a6e")
        cv.line([P(u, v0, (z0 + z1) / 2), P(u, v1, (z0 + z1) / 2)], "#1f3a6e")
        if hole:
            cv.fill(cv.pmask([P(u, v0, z1), P(u, v0 + 10, z1), P(u, v0 + 4, z1 - 8), P(u, v0, z1 - 12)]) & m, (0, 0, 0, 0))
            cv.line([P(u, v0 + 10, z1), P(u, v0 + 4, z1 - 8), P(u, v0, z1 - 12)], METAL[2])
    solar(108, -8, 14, 22, 46, True); solar(108, 18, 40, 22, 46)

    # ---- tanque (direita) e tubo
    iso.box(100, 126, 30, 56, 0, 24, TONES, BD, CREAM[0], seed=3)
    L1 = lambda u, z: P(u, 56, z)
    cv.rect(*map(int, L1(104, 17)), 1, 1, OR)
    for k in range(10):
        x, y = L1(102 + k * 2.3, 11); cv.rect(x, y, 2, 3, OR if k % 2 == 0 else OR_D) if False else None
    cv.line([L1(100, 12), L1(126, 12)], OR); cv.line([L1(100, 11), L1(126, 11)], OR_D)
    cv.poly([L1(106, 20), L1(114, 20), L1(114, 14), L1(106, 14)], "#17131e"); cv.line([L1(107, 19), L1(113, 19)], GL[1])
    for k in range(3):
        x, y = P(108 + k * 5, 38, 28); cv.rect(x, y - 3, 3, 4, CREAM[3])

    # ---- tambor central (base redonda em iso: elipse rx = 1.41 r, ry = rx/2)
    cx, cy0 = P(60, 40, 30)
    rx, ry, wall = 48, 24, 30
    body = cv.emask(cx, cy0 + wall, rx, ry) | cv.mask(lambda d: d.rectangle([int(cx - rx), int(cy0), int(cx + rx - 1), int(cy0 + wall)], fill=255))
    body &= ~(cv.emask(cx, cy0, rx, ry) & (np.arange(H)[:, None] < cy0))
    cv.paint(body, lambda x, y: CREAM[1] if (x - cx) / rx < -.55 else CREAM[2] if (x - cx) / rx < -.05 else CREAM[3] if (x - cx) / rx < .4 else CREAM[4] if (x - cx) / rx < .75 else CREAM[5])
    band = np.zeros_like(body)
    for x in range(int(cx - rx + 3), int(cx + rx - 2)):
        t = (x - cx) / rx
        e = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        band[int(e) + 5:int(e) + 22, x] = True
    band &= body
    pane(cv, band, 11)
    shade_region(cv, band & (np.arange(W)[None, :] > cx + rx * .35), .72)
    for ang in np.linspace(0.08, math.pi - 0.08, 11):
        x = cx + rx * math.cos(ang); e = cy0 + ry * math.sin(ang)
        for yy in range(int(e) + 5, int(e) + 23):
            cv.px(x, yy, CREAM[2] if math.cos(ang) < 0 else CREAM[5])
    for x in range(int(cx - rx + 1), int(cx + rx)):
        t = (x - cx) / rx
        e = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        cv.rect(x, int(e) + 1, 1, 3, OR if t < .4 else OR_D); cv.px(x, int(e) + 1, OR_L if t < -.2 else OR)
        cv.rect(x, int(e) + 23, 1, 8, CREAM[3] if t < 0 else CREAM[4] if t < .5 else CREAM[5])
    topm = cv.emask(cx, cy0, rx, ry)
    cv.paint(topm, lambda x, y: CREAM[0] if (x - cx) / rx + (y - cy0) / ry < -.55 else CREAM[1] if (x - cx) / rx < .25 else CREAM[2] if (x - cx) / rx < .65 else CREAM[3])
    # domo
    dr, dry, dh = 40, 20, 44
    dome = cv.emask(cx, cy0, dr, dry) | (cv.emask(cx, cy0, dr, dh) & (np.arange(H)[:, None] <= cy0))
    pane(cv, dome, 29)
    floor = cv.emask(cx, cy0 - 1, dr - 5, dry - 4)
    cv.paint(floor, lambda x, y: "#2c5060" if ((x // 4) + (y // 3)) % 2 == 0 else "#244456")
    for (x, y) in ((cx - 12, cy0 - 3), (cx + 6, cy0 + 2), (cx + 18, cy0 - 2), (cx - 3, cy0 - 8)):
        cv.rect(x, y, 4, 3, "#3f7a8c"); cv.px(x + 1, y, "#7fd67a")
    def meridian(psi, col):
        pts = []
        for i in range(26):
            f = i / 25 * .985; r_ = math.sqrt(1 - f * f)
            pts.append((cx + dr * r_ * math.cos(psi), cy0 - f * dh + dry * r_ * math.sin(psi)))
        for a, b in zip(pts, pts[1:]):
            cv.line([a, b], col, 1)
    for psi in (math.pi + .4, math.pi + 1.0, math.pi + 1.6, math.pi + 2.2, math.pi + 2.8):
        meridian(psi, GL[4])
    for psi in (0.1, 0.5, 0.95, 1.35, 1.75, 2.15, 2.6, 3.05):
        meridian(psi, CREAM[1] if math.cos(psi) < 0 else CREAM[4])
    for f_ in (.3, .62):
        r_ = math.sqrt(1 - f_ * f_)
        arc(cv, cx, cy0 - f_ * dh, dr * r_, dry * r_, .02, math.pi - .02, CREAM[2], 40, 1)
    arc(cv, cx, cy0, dr, dry, .0, math.pi, CREAM[1], 40, 2)
    shade_region(cv, dome & (np.arange(W)[None, :] > cx + dr * .4), .78)
    hx, hy = cx + 8, cy0 - 28
    brk = []
    for i in range(16):
        an = 2 * math.pi * i / 16
        rr = 11 + 5 * hsh(i, 3, 4) + (5 if i % 2 else 0)
        brk.append((hx + rr * 1.25 * math.cos(an), hy + rr * .9 * math.sin(an)))
    mb = cv.pmask(brk) & dome
    cv.fill(mb, INT[1]); cv.paint(mb, lambda x, y: INT[2] if y > hy + 2 else INT[0] if y < hy - 8 else None)
    cv.line([(hx - 10, hy - 8), (hx, hy + 2), (hx + 12, hy - 6)], RUST[1], 2); cv.line([(hx - 2, hy - 13), (hx, hy + 10)], RUST[2])
    for (x, y) in brk:
        cv.px(x, y, GL[0]); cv.px(x + 1, y + 1, GL[4])
    for (a, b) in (((hx - 24, hy + 8), (hx - 13, hy + 2)), ((hx + 14, hy + 3), (hx + 26, hy + 14)), ((hx - 8, hy + 16), (hx - 12, hy + 26))):
        cv.line([a, b], "#ffffff"); cv.line([(a[0] + 1, a[1] + 1), (b[0] + 1, b[1] + 1)], GL[4])
    cv.fill(cv.pmask([(cx + 14, cy0 + 8), (cx + 26, cy0 + 4), (cx + 30, cy0 + 18), (cx + 18, cy0 + 22)]) & band, INT[2])
    cv.rect(cx - 28, 4, 2, int(cy0 - 4 - 38), METAL[2]); cv.rect(cx - 32, 18, 10, 1, METAL[2]); cv.rect(cx - 29, 1, 4, 3, "#ff5a4a"); cv.px(cx - 29, 1, "#ffb0a0")

    # ---- eclusa (frente-esquerda): caixa iso, porta e rampa na face da esquerda (v), tubo até o tambor
    iso.box(30, 66, 84, 112, 0, 28, TONES, BD, CREAM[0], seed=5)
    LL = lambda u, z: P(u, 112, z)
    cv.line([LL(30, 14), LL(66, 14)], OR); cv.line([LL(30, 13), LL(66, 13)], OR_D); cv.line([LL(30, 18), LL(66, 18)], OR_L)
    cv.poly([LL(34, 24), LL(42, 24), LL(42, 18), LL(34, 18)], "#17131e"); cv.poly([LL(35, 23), LL(41, 23), LL(41, 19), LL(35, 19)], GL[2]); cv.line([LL(35, 22), LL(40, 20)], GL[0])
    door = [LL(46, 3), LL(60, 3), LL(60, 24), LL(46, 24)]
    cv.poly(door, OUT)
    dm = cv.pmask([LL(47, 4), LL(59, 4), LL(59, 23), LL(47, 23)])
    cv.banded(dm, [CAV[0], CAV[1], CAV[2]], cuts=[.3, .7])
    cv.line([LL(46, 24), LL(60, 24)], "#f2c46d"); cv.line([LL(47, 5), LL(59, 5)], "#59d0e6")
    x, y = LL(52, 14); cv.rect(x, y, 2, 2, "#ff6a55")
    ramp = [P(46, 112, 3), P(60, 112, 3), P(60, 134, 0), P(46, 134, 0)]
    cv.poly([(x - (1 if i in (0, 3) else 0), y) for i, (x, y) in enumerate(ramp)], OUT)
    rm = cv.pmask(ramp)
    cv.paint(rm, lambda x, y: BGR[0] if y < P(46, 118, 0)[1] - 2 else BGR[1] if y < P(46, 126, 0)[1] - 1 else BGR[2])
    for k in range(1, 5):
        cv.line([P(46, 112 + k * 5, 3 - k * .6), P(60, 112 + k * 5, 3 - k * .6)], BGR[3])
    cv.line([P(46, 112, 3), P(46, 134, 0)], CREAM[5]); cv.line([P(60, 112, 3), P(60, 134, 0)], CREAM[5])
    # terminal em pedestal na frente do tambor
    tx, ty = P(86, 66, 0)
    cv.rect(tx - 4, ty - 4, 12, 5, CREAM[4]); cv.rect(tx - 4, ty - 4, 12, 1, CREAM[2])
    cv.rect(tx - 10, ty - 21, 20, 17, OUT); cv.rect(tx - 9, ty - 20, 18, 15, CREAM[1]); cv.rect(tx - 9, ty - 8, 18, 3, CREAM[4])
    cv.rect(tx - 7, ty - 18, 14, 9, "#102018"); cv.rect(tx - 6, ty - 17, 8, 1, "#7fd67a"); cv.rect(tx - 6, ty - 15, 11, 1, "#4aa860"); cv.rect(tx - 6, ty - 13, 6, 1, "#7fd67a")
    cv.terminal_rect = (tx - 10, ty - 21, 20, 17)
    for (x, y, w_, c0, c1) in ((100, 126, 14, CREAM[2], CREAM[4]), (156, 124, 16, CREAM[1], CREAM[3]), (134, 138, 10, GL[1], GL[3]), (186, 118, 12, CREAM[2], CREAM[4]), (88, 144, 8, GL[2], GL[4])):
        cv.rect(x, y, w_, 5, c1); cv.rect(x, y, w_, 2, c0); cv.rect(x, y, w_, 1, CREAM[0] if c0 != GL[1] else GL[0])
    scatter(cv, [(4, 154), (106, 160), (166, 150), (216, 142), (244, 124), (60, 158)], 5)
    cv.outline()
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    c = base5(); c.check(); c.image().save(PEND / "r5_wreck_module_glass.png")
    print(c.terminal_rect)


if __name__ == "__main__":
    main()
