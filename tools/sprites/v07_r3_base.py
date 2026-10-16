#!/usr/bin/env python3
"""v0.7 Lore · rodada 3 · base espacial de vidro em 3/4 de verdade (topo + frente + lateral com volume). 224×192 · 7×5.

    python3 tools/sprites/v07_r3_base.py     ->  pendentes/r3_wreck_module_glass.png
Luz de cima-esquerda; frente = tom médio, topo = claro, lateral direita = escura; sombra projetada pra direita/baixo.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_destrocos import CAV, CREAM, METAL, OR, OR_D, OR_L, RUST, arc  # noqa: E402
from v07_lib import Cv, OUT, hsh, sand_pile, scatter, C  # noqa: E402
from v07_r2_destrocos import GL, INT, pane, BGR  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_lore" / "pendentes"


def darken(c, f):
    r, g, b, a = c
    return (int(r * f), int(g * f), int(b * f), a)


def shade_region(cv, mask, f):
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        p = cv.im.getpixel((int(x), int(y)))
        if p[3] == 255:
            cv.im.putpixel((int(x), int(y)), darken(p, f))


def box3(cv, x, y, w, h, dx, dy, front, top, side):
    """Caixa 3/4: frente (x,y,w,h), topo em paralelogramo (profundidade dx,dy<0) e lateral direita."""
    cv.poly([(x + w, y), (x + w + dx, y + dy), (x + w + dx, y + dy + h), (x + w, y + h)], side[0])
    ms = cv.pmask([(x + w, y), (x + w + dx, y + dy), (x + w + dx, y + dy + h), (x + w, y + h)])
    cv.banded(ms, list(side), cuts=[.3, .7][:len(side) - 1])
    mf = cv.pmask([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    cv.banded(mf, list(front), cuts=[.15, .5, .85][:len(front) - 1])
    mt = cv.pmask([(x, y), (x + w, y), (x + w + dx, y + dy), (x + dx, y + dy)])
    cv.fill(mt, top[1]); cv.paint(mt, lambda xx, yy: top[0] if yy < y + dy * .55 else None)
    cv.line([(x, y), (x + dx, y + dy), (x + w + dx, y + dy)], top[0])
    cv.line([(x, y), (x + w, y)], CREAM[0])
    return mf, mt, ms


def base3():
    W, H = 224, 192
    cv = Cv(W, H)
    cv.shadow_ell(124, 178, 108, 12)
    sand_pile(cv, 12, 182, 12, 4, 1); sand_pile(cv, 214, 182, 12, 4, 2)

    def solar(x, y, w, h, hole=False):
        cv.rect(x + w // 2 - 1, y + h, 3, 20, METAL[3]); cv.rect(x + w // 2 - 5, y + h + 18, 11, 3, METAL[4])
        top = [(x, y + 8), (x + w, y), (x + w, y + h - 8), (x, y + h)]
        cv.poly([(px, py + 3) for px, py in top], METAL[4])                              # espessura (borda de baixo)
        cv.poly(top, METAL[3]); m = cv.pmask([(x + 1, y + 9), (x + w - 1, y + 1), (x + w - 1, y + h - 9), (x + 1, y + h - 1)])
        cv.banded(m, ["#5b86d0", "#3d63a8", "#2f5090"], cuts=[.3, .7])
        cv.paint(m, lambda xx, yy: "#bcd6ff" if (xx + yy * 2) % 13 == 0 else None)
        for i in range(1, 4):
            cv.line([(x + i * w // 4, y + 8 - i * 2), (x + i * w // 4, y + h - i * 2)], "#1f3a6e")
        cv.line([(x + 1, y + h // 2 + 4), (x + w - 1, y + h // 2 - 4)], "#1f3a6e")
        if hole:
            cv.fill(cv.pmask([(x + w - 14, y + 3), (x + w, y), (x + w, y + 14), (x + w - 8, y + 10)]) & m, (0, 0, 0, 0))
            cv.line([(x + w - 14, y + 3), (x + w - 8, y + 10), (x + w, y + 14)], METAL[2])
    solar(172, 56, 36, 38, True); solar(180, 104, 34, 32)

    # ---- módulo-tanque (direita), caixa 3/4
    mf, mt, ms = box3(cv, 168, 152, 36, 26, 14, -12,
                      (CREAM[1], CREAM[2], CREAM[3], CREAM[4]), (CREAM[0], CREAM[1]), (CREAM[4], CREAM[5]))
    cv.rect(168, 162, 36, 3, OR); cv.rect(168, 162, 36, 1, OR_L)
    cv.rect(173, 168, 10, 6, "#17131e"); cv.rect(174, 169, 8, 4, GL[3]); cv.px(174, 169, GL[0])
    for k in range(3):
        cv.rect(184 + k * 5, 141 - k, 3, 6, CREAM[3])       # saídas de ventilação no teto
    # ---- tubo de ligação e eclusa
    cv.rect(66, 156, 28, 16, OUT); cv.rect(66, 157, 28, 14, CREAM[2]); cv.rect(66, 157, 28, 4, CREAM[0]); cv.rect(66, 164, 28, 3, CREAM[3]); cv.rect(66, 168, 28, 3, CREAM[4])
    cv.rect(76, 156, 3, 16, CREAM[4]); cv.rect(84, 156, 3, 16, CREAM[4])
    ex, ey, ew, eh = 8, 148, 56, 32
    mf, mt, ms = box3(cv, ex, ey, ew, eh, 18, -16,
                      (CREAM[1], CREAM[2], CREAM[2], CREAM[3], CREAM[4]), (CREAM[0], CREAM[1]), (CREAM[4], CREAM[5]))
    # teto da eclusa: escotilha, painéis e luz
    q = lambda u, v: (ex + u * ew + v * 18, ey - v * 16)
    cv.poly([q(.12, .25), q(.5, .25), q(.5, .75), q(.12, .75)], CREAM[3]); cv.poly([q(.16, .32), q(.46, .32), q(.46, .7), q(.16, .7)], CREAM[2])
    cv.line([q(.31, .32), q(.31, .7)], CREAM[4]); cv.line([q(.16, .5), q(.46, .5)], CREAM[4])
    cv.poly([q(.62, .3), q(.9, .3), q(.9, .6), q(.62, .6)], "#3d63a8"); cv.line([q(.76, .3), q(.76, .6)], "#1f3a6e")
    cv.rect(ex, ey + 14, ew, 4, OR); cv.rect(ex, ey + 14, ew, 1, OR_L); cv.rect(ex, ey + 17, ew, 1, OR_D)
    cv.rect(ex + 5, ey + 4, 12, 8, "#17131e"); cv.rect(ex + 6, ey + 5, 10, 6, GL[3]); cv.rect(ex + 6, ey + 5, 10, 2, GL[1]); cv.line([(ex + 8, ey + 10), (ex + 13, ey + 6)], GL[0])
    dx0 = ex + 26
    cv.rect(dx0 - 1, ey + 6, 22, eh - 6, OUT)
    cv.rect(dx0, ey + 7, 20, eh - 7, CAV[1]); cv.rect(dx0, ey + 7, 20, 3, CAV[0])
    cv.rect(dx0, ey + 7, 3, eh - 7, CREAM[3]); cv.rect(dx0 + 17, ey + 7, 3, eh - 7, CREAM[4])
    cv.rect(dx0 + 7, ey + 12, 3, 3, "#ff6a55"); cv.line([(dx0 - 1, ey + 6), (dx0 + 20, ey + 6)], "#f2c46d")
    ramp = cv.pmask([(dx0 - 2, ey + eh), (dx0 + 22, ey + eh), (dx0 + 28, ey + eh + 11), (dx0 - 8, ey + eh + 11)])
    cv.paint(ramp, lambda x, y: BGR[0] if (y - ey - eh) < 3 else BGR[1] if (y - ey - eh) < 7 else BGR[2])
    for k in range(5):
        cv.line([(dx0 + k * 5, ey + eh + 1), (dx0 - 5 + k * 8, ey + eh + 10)], BGR[3])
    cv.line([(dx0 - 2, ey + eh), (dx0 - 8, ey + eh + 11)], CREAM[5]); cv.line([(dx0 + 22, ey + eh), (dx0 + 28, ey + eh + 11)], CREAM[5])

    # ---- tambor central em 3/4 (topo elíptico alto), parede de janelões, domo de vidro
    cx, cy0, rx, ry, wall = 122, 116, 50, 25, 34
    body = cv.emask(cx, cy0 + wall, rx, ry) | cv.mask(lambda d: d.rectangle([cx - rx, cy0, cx + rx - 1, cy0 + wall], fill=255))
    body &= ~(cv.emask(cx, cy0, rx, ry) & (np.arange(H)[:, None] < cy0))
    def drum(x, y):
        t = (x - cx) / rx
        return CREAM[1] if t < -.55 else CREAM[2] if t < -.05 else CREAM[3] if t < .4 else CREAM[4] if t < .75 else CREAM[5]
    cv.paint(body, drum)
    band = np.zeros_like(body)
    for x in range(cx - rx + 3, cx + rx - 2):
        t = (x - cx) / rx
        ey_ = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        band[int(ey_) + 5:int(ey_) + 24, x] = True
    band &= body
    pane(cv, band, 11)
    shade_region(cv, band & (np.arange(W)[None, :] > cx + rx * .35), .72)
    shade_region(cv, band & (np.arange(W)[None, :] > cx + rx * .7), .85)
    for ang in np.linspace(0.08, math.pi - 0.08, 11):
        x = cx + rx * math.cos(ang); ey_ = cy0 + ry * math.sin(ang)
        for yy in range(int(ey_) + 5, int(ey_) + 25):
            cv.px(x, yy, CREAM[2] if math.cos(ang) < 0 else CREAM[5])
    for x in range(cx - rx + 1, cx + rx):
        t = (x - cx) / rx
        ey_ = cy0 + ry * math.sqrt(max(0, 1 - t * t))
        cv.rect(x, int(ey_) + 1, 1, 3, OR if t < .4 else OR_D); cv.px(x, int(ey_) + 1, OR_L if t < -.2 else OR)
        cv.rect(x, int(ey_) + 25, 1, 9, CREAM[3] if t < 0 else CREAM[4] if t < .5 else CREAM[5])
    # topo (anel) com realce e sombra à direita
    topm = cv.emask(cx, cy0, rx, ry)
    cv.paint(topm, lambda x, y: CREAM[0] if (x - cx) / rx + (y - cy0) / ry < -.55 else CREAM[1] if (x - cx) / rx < .25 else CREAM[2] if (x - cx) / rx < .65 else CREAM[3])
    arc(cv, cx, cy0, rx - 3, ry - 2, math.pi, 2 * math.pi, CREAM[0], 40, 1)
    # domo: hemisfério de vidro com piso interior visível (olhando de cima), costelas de trás e da frente
    dr, dry, dh = 43, 20, 48
    dome = cv.emask(cx, cy0, dr, dry) | (cv.emask(cx, cy0, dr, dh) & (np.arange(H)[:, None] <= cy0))
    pane(cv, dome, 29)
    floor = cv.emask(cx, cy0 - 1, dr - 5, dry - 4)
    cv.paint(floor, lambda x, y: "#2c5060" if ((x // 4) + (y // 3)) % 2 == 0 else "#244456")
    for (x, y) in ((cx - 14, cy0 - 3), (cx + 6, cy0 + 2), (cx + 20, cy0 - 2), (cx - 4, cy0 - 8)):
        cv.rect(x, y, 4, 3, "#3f7a8c"); cv.px(x + 1, y, "#7fd67a")
    cv.rect(cx - 2, cy0 - 3, 2, 2, "#f2c46d")
    def meridian(psi, col, back=False):
        pts = []
        for i in range(26):
            f = i / 25 * .985; r_ = math.sqrt(1 - f * f)
            pts.append((cx + dr * r_ * math.cos(psi), cy0 - f * dh + dry * r_ * math.sin(psi)))
        for a, b in zip(pts, pts[1:]):
            cv.line([a, b], col, 1)
    for psi in (math.pi + .4, math.pi + 1.0, math.pi + 1.6, math.pi + 2.2, math.pi + 2.8):       # costelas de trás (vistas pelo vidro)
        meridian(psi, GL[4])
    for psi in (0.1, 0.5, 0.95, 1.35, 1.75, 2.15, 2.6, 3.05):
        meridian(psi, CREAM[1] if math.cos(psi) < 0 else CREAM[4])
    for f_ in (.3, .62):
        r_ = math.sqrt(1 - f_ * f_)
        arc(cv, cx, cy0 - f_ * dh, dr * r_, dry * r_, .02, math.pi - .02, CREAM[2], 40, 1)
    arc(cv, cx, cy0, dr, dry, .0, math.pi, CREAM[1], 40, 2)
    shade_region(cv, dome & (np.arange(W)[None, :] > cx + dr * .4), .78)
    # ruína: buraco irregular no domo (alto, à direita) com vigas e estilhaços
    hx, hy = cx + 9, cy0 - 30
    brk = []
    for i in range(16):
        an = 2 * math.pi * i / 16
        rr = 12 + 5 * hsh(i, 3, 4) + (5 if i % 2 else 0)
        brk.append((hx + rr * 1.25 * math.cos(an), hy + rr * .9 * math.sin(an)))
    mb = cv.pmask(brk) & dome
    cv.fill(mb, INT[1]); cv.paint(mb, lambda x, y: INT[2] if y > hy + 2 else INT[0] if y < hy - 8 else None)
    cv.line([(hx - 11, hy - 8), (hx, hy + 2), (hx + 13, hy - 6)], RUST[1], 2)
    cv.line([(hx - 2, hy - 14), (hx, hy + 11)], RUST[2])
    for (x, y) in brk:
        cv.px(x, y, GL[0]); cv.px(x + 1, y + 1, GL[4])
    for (a, b) in (((hx - 26, hy + 8), (hx - 14, hy + 2)), ((hx + 15, hy + 3), (hx + 28, hy + 15)), ((hx - 8, hy + 17), (hx - 13, hy + 28)), ((hx + 18, hy - 10), (hx + 28, hy - 6))):
        cv.line([a, b], "#ffffff"); cv.line([(a[0] + 1, a[1] + 1), (b[0] + 1, b[1] + 1)], GL[4])
    cv.fill(cv.pmask([(cx + 16, 150), (cx + 28, 146), (cx + 32, 160), (cx + 20, 164)]) & band, INT[2])
    for (a, b) in (((cx - 30, 150), (cx - 20, 160)), ((cx - 8, 150), (cx - 2, 163)), ((cx + 32, 150), (cx + 38, 158))):
        cv.line([a, b], "#ffffff")
    cv.rect(cx - 30, 14, 2, 70, METAL[2]); cv.rect(cx - 34, 28, 10, 1, METAL[2]); cv.rect(cx - 31, 11, 4, 3, "#ff5a4a"); cv.px(cx - 31, 11, "#ffb0a0")
    cv.rect(cx - 21, 26, 2, 54, METAL[3]); cv.rect(cx - 23, 22, 6, 4, METAL[0])
    # terminal em pedestal na frente do tambor: tile (3,4)
    tx_, ty_ = 104, 166
    cv.rect(tx_ + 4, ty_ + 16, 12, 5, CREAM[4]); cv.rect(tx_ + 4, ty_ + 16, 12, 1, CREAM[2])
    cv.rect(tx_, ty_, 20, 17, OUT); cv.rect(tx_ + 1, ty_ + 1, 18, 15, CREAM[1]); cv.rect(tx_ + 1, ty_ + 13, 18, 3, CREAM[4])
    cv.rect(tx_ + 3, ty_ + 3, 14, 9, "#102018"); cv.rect(tx_ + 4, ty_ + 4, 8, 1, "#7fd67a"); cv.rect(tx_ + 4, ty_ + 6, 11, 1, "#4aa860"); cv.rect(tx_ + 4, ty_ + 8, 6, 1, "#7fd67a"); cv.rect(tx_ + 14, ty_ + 14, 3, 1, OR)
    for (x, y, w_, c0, c1) in ((84, 180, 14, CREAM[2], CREAM[4]), (134, 182, 16, CREAM[1], CREAM[3]), (152, 176, 10, GL[1], GL[3]), (72, 184, 8, GL[2], GL[4]), (166, 184, 12, CREAM[2], CREAM[4])):
        cv.rect(x, y, w_, 5, c1); cv.rect(x, y, w_, 2, c0); cv.rect(x, y, w_, 1, CREAM[0] if c0 != GL[1] else GL[0])
    sand_pile(cv, 104, 187, 20, 4, 6)
    scatter(cv, [(4, 188), (76, 189), (140, 189), (190, 188), (214, 180), (40, 190), (160, 190)], 5)
    cv.outline()
    cv.terminal_rect = (tx_, ty_, 20, 17)
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    c = base3(); c.check(); c.image().save(PEND / "r3_wreck_module_glass.png")


if __name__ == "__main__":
    main()
