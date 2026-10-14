#!/usr/bin/env python3
"""Drills a laser GUARDADAS pra T2/T3 (fora do contrato). Decisão do dono na v1.2 das máquinas: ele adorou as duas, mas
elas têm cara de nível alto; a T1 do jogo é a `drill()` simples do machines_r3d.py. Mesmo quadro (64×80, 4 quadros a
8 fps, âncora no centro da base dos 2×2) e o mesmo feixe/poça/faíscas da T1.

    python3 tools/sprites/machines_r3d_futuro.py      # gera em reports/design/maquinas_r3d/futuro/

    drill_tripod.png   256×80  A · tripé articulado, cabeça-canhão e cano longo, feixe LARANJA. Indicador FILL_TRIPOD.
    drill_spider.png   256×80  B · cápsula com tanque de energia e 4 pernas de aranha, feixe CIANO. Indicador FILL_SPIDER.
Quando virarem máquina de verdade (machine_drill_t2/_t3), o nome e o retângulo entram na bíblia §6 antes.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from machines_r3d import (ALERT, CYAN, CYAN_D, CYAN_L, LASER_CYAN, LASER_HOT, OK, FRONT, P_BEIGE, P_DARK, P_GLASS,  # noqa: E402
                          P_METAL, P_ORANGE, P_STEEL, Pal, _fill_window, _proj, anim, impact, laser, render, scene)

OUT = HERE.parents[1] / "reports" / "design" / "maquinas_r3d" / "futuro"
FILL_TRIPOD = (48, 47, 7, 12)            # na caçamba ao lado (o mesmo lugar da drill de broca do freela)
FILL_SPIDER = (29, 34, 7, 10)            # na "barriga" da cápsula


def _foot(sc, x, y, pal=P_ORANGE):
    sc.rbox((x, y, 0.8), (3.0, 2.4, 0.8), 0.5, P_DARK)
    sc.rbox((x, y, 2.2), (2.2, 1.8, 0.9), 0.6, pal)


def drill_tripod(f, beam=True):
    """A · tripé: três pernas articuladas, cabeça-canhão redonda e o cano longo apontado pro veio. Feixe LARANJA.
    Ao lado, a caçamba que recebe o minério (indicador no lugar de hoje) com a mangueira de sucção."""
    sc = scene(64, 80, -28)
    hit = (9.0, -5.0, 0.0)
    hip = (-14.0, 10.0, 28.0)
    head = (-14.0, 11.0, 44.0)
    rec = 0.8 if f % 2 else 0.0                                         # recuo do cano no pulso
    # pernas: quadril -> joelho (alto, pra fora) -> pé
    legs = [((-27.0, -20.0), (-25.0, -6.0, 33.0)), ((-29.0, 24.0), (-27.0, 18.0, 35.0)), ((6.0, 26.0), (0.0, 21.0, 36.0))]
    for (fx_, fy_), knee in legs:
        sc.tube([hip, knee], 1.3, P_METAL)
        def lp(sv, th):
            return np.where((sv > 4) & (sv < 6.5), 1, 0)
        sc.tube([knee, (fx_, fy_, 3.0)], 1.6, P_BEIGE, paint=lp, extra=(P_ORANGE,))
        sc.sphere(knee, 2.0, P_METAL)
        _foot(sc, fx_, fy_)
    sc.sphere(hip, 3.6, P_METAL)                                        # quadril
    sc.cyl(hip[0], hip[1], 2.6, hip[2], head[2] - 6, P_STEEL)           # pescoço
    # cabeça-canhão: esfera branca com faixa laranja e o "olho" escuro de lado
    def hp(N):
        out = np.zeros(len(N), int)
        out[np.abs(N[:, 2] + 0.05) < 0.12] = 1
        port = (N[:, 0] < -0.55) & (N[:, 1] < 0.2) & (np.abs(N[:, 2]) < 0.6)
        out[port] = 2
        out[port & (N[:, 0] < -0.78)] = 3
        return out
    sc.sphere(head, 7.5, P_BEIGE, paint=hp, extra=(P_ORANGE, P_METAL, Pal(["#1d2b3a"] * 5)))
    sc.dot(head[0] - 7.8, head[1] - 1.5, head[2] + 1.5, CYAN_L if f % 2 == 0 else CYAN, always=True)
    sc.cyl(head[0] + 1, head[1] + 1, 0.6, head[2] + 6, head[2] + 12, P_METAL)       # antena
    sc.dot(head[0] + 1, head[1] + 1, head[2] + 12.8, ALERT if f < 2 else "#7a2a24", always=True)
    # cano: da cabeça até perto do veio, com luvas e a boca
    H = np.array(head)
    D = np.array(hit) - H
    D /= np.linalg.norm(D)
    p_a = H + D * 5.0
    p_b = H + D * (27.0 - rec)
    p_m = H + D * (31.0 - rec)
    def barrel(sv, th):
        out = np.zeros(len(sv), int)
        out[(sv > 5) & (sv < 7.5)] = 1
        out[(sv > 15) & (sv < 16.5)] = 1
        return out
    sc.tube([tuple(p_a), tuple(p_b)], 2.5, P_STEEL, paint=barrel, extra=(P_ORANGE,), caps=False)
    sc.tube([tuple(H + D * 8), tuple(H + D * 11.5)], 3.0, P_METAL, caps=False)
    sc.tube([tuple(H + D * 19), tuple(H + D * 21.5)], 2.8, P_METAL, caps=False)
    sc.tube([tuple(p_b), tuple(p_m)], 3.1, P_DARK, caps=False)
    sc.tube([tuple(p_b - D * 1.2), tuple(p_b)], 3.3, P_ORANGE, caps=False)
    rail = np.array([0.0, -2.6, 0.6])                                   # trilho fininho paralelo (como na ref)
    sc.tube([tuple(H + D * 8 + rail), tuple(H + D * 25 + rail)], 0.7, P_STEEL)
    # caçamba de coleta à direita + mangueira de sucção até o veio
    sc.cyl(19.5, -9, 5.2, 2.5, 31, P_BEIGE,
           paint=lambda t, z, c: np.where(((z > 5) & (z < 6.6) | (z > 28) & (z < 29.4)) & ~c, 1, np.where(c, 2, 0)),
           extra=(P_ORANGE, P_DARK))
    sc.cyl(19.5, -9, 5.8, 0, 2.5, P_METAL)
    sc.cyl(19.5, -9, 5.8, 31, 32.5, P_METAL)
    sc.dot(22.6, -14.4, 26.5, OK if f % 2 == 0 else "#2f5a2c", always=True)
    sc.tube([(17.0, -5, 30.5), (14, -2, 33), (13, 0, 16), (13.5, 1, 4), (12, 1, 1.6)], 0.9, P_METAL)
    sc.box((10, 13), (-0.4, 2.4), (0.6, 2.2), P_DARK)                     # bocal da sucção
    cv = render(sc)
    if beam:
        m = _proj(sc, *tuple(p_m))
        h_ = _proj(sc, *hit)
        laser(cv, m, h_, f, LASER_HOT)
        impact(cv, *h_, f, LASER_HOT)
        cv.px(round(m[0] - 0.5), round(m[1] - 0.5), "#ffffff")
    _fill_window(cv, FILL_TRIPOD)
    return cv


def drill_spider(f, beam=True):
    """B · aranha: cápsula de pé com o tanque de vidro de energia ciano no meio, 4 pernas de aranha cravadas no
    chão e o emissor por baixo, disparando o feixe CIANO direto no veio. O indicador vai no 'estômago' da cápsula
    (retângulo próprio, FILL_SPIDER)."""
    sc = scene(64, 80, -28)
    cx, cy = 0.0, 6.0
    z_emit, z_low, z_tank, z_up, z_top = 21.0, 24.0, 37.0, 50.0, 53.0
    # pernas (atrás e na frente do corpo): quadril no corpo -> joelho alto -> ponta cravada
    for ang in (25, 155, -25, -155):
        a = math.radians(ang)
        hipp = (cx + 6.5 * math.cos(a), cy + 6.5 * math.sin(a), 31.0)
        knee = (cx + 21 * math.cos(a), cy + 16 * math.sin(a), 44.0)
        tip = (cx + 28.5 * math.cos(a), cy + 22 * math.sin(a), 0.0)
        def lp(sv, th):
            return np.where((sv > 4) & (sv < 6), 1, np.where(sv > 41, 2, 0))
        sc.tube([hipp, knee], 1.4, P_METAL)
        sc.tube([knee, ((knee[0] + tip[0]) / 2, (knee[1] + tip[1]) / 2, 22.0), tip], 1.7, P_BEIGE, paint=lp,
                extra=(P_ORANGE, P_DARK), caps=False)
        sc.sphere(knee, 2.3, P_STEEL)
        sc.sphere(hipp, 2.1, P_METAL)
    # emissor (cone virado pra baixo) + barriga com o indicador
    sc.cyl(cx, cy, 2.6, z_emit, z_low, P_DARK, r_top=6.0)
    sc.cyl(cx, cy, 1.6, z_emit - 1.8, z_emit, P_GLASS, cap=False)
    sc.cyl(cx, cy, 8.0, z_low, z_tank, P_BEIGE, paint=lambda t, z, c: np.where((z > z_low + 1) & (z < z_low + 2.6) & ~c, 1, 0),
           extra=(P_ORANGE,))
    # tanque de energia: vidro ciano com anéis de luz subindo e 4 colunas
    lvl = [0, 2, 4, 6][f]
    P_EN = Pal(["#ffffff", CYAN_L, CYAN, CYAN_D, "#1d4a66"])
    P_EN_HI = Pal([CYAN_L] * 5, emit=True, emit_tone=0)
    sc.cyl(cx, cy, 7.4, z_tank, z_up, P_EN,
           paint=lambda t, z, c: np.where((((z - z_tank - lvl) % 6) < 1.2) & ~c, 1, 0), extra=(P_EN_HI,))
    for k in range(4):
        a = FRONT + math.radians(45 + 90 * k)
        sc.cyl(cx + 8.0 * math.cos(a), cy + 8.0 * math.sin(a), 0.9, z_tank, z_up, P_STEEL)
    sc.cyl(cx, cy, 8.8, z_tank - 0.6, z_tank + 1.0, P_METAL)
    sc.cyl(cx, cy, 8.8, z_up - 1.0, z_up + 0.6, P_METAL)
    # tampa: anel bege, faixa laranja, domo de metal e antena
    sc.cyl(cx, cy, 8.0, z_up + 0.6, z_top, P_BEIGE, paint=lambda t, z, c: np.where((z > z_up + 1.6) & (z < z_up + 3) & ~c, 1, 0),
           extra=(P_ORANGE,))
    sc.cyl(cx, cy, 6.0, z_top, z_top + 2.2, P_METAL, r_top=3.8)
    sc.cyl(cx, cy, 0.6, z_top + 2.2, z_top + 7, P_METAL)
    sc.dot(cx, cy, z_top + 7.8, ALERT if f < 2 else "#7a2a24", always=True)
    sc.dot(cx - 5.5, cy - 5.6, z_low + 4.5, OK if f % 2 == 0 else "#2f5a2c", always=True)
    cv = render(sc)
    if beam:
        e = _proj(sc, cx, cy - 1, z_emit - 2.0)
        h_ = _proj(sc, cx, cy - 1, 0.0)
        laser(cv, e, h_, f, LASER_CYAN)
        impact(cv, *h_, f, LASER_CYAN)
    _fill_window(cv, FILL_SPIDER)
    return cv



def main():
    for name, fn in (("drill_tripod", drill_tripod), ("drill_spider", drill_spider)):
        cv = anim(fn)
        assert (cv.w, cv.h) == (256, 80)
        cv.save(OUT / f"{name}.png")
    print("ok ->", OUT)


if __name__ == "__main__":
    main()
