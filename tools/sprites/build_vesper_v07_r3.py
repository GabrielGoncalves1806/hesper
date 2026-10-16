#!/usr/bin/env python3
"""Hesper v0.7 M4 · rodada 3: prop_container_stack (3 contêineres azuis empilhados) A/B no motor r3d + ícone 16×16
+ sala escura com o container_open aprovado e a pilha num canto. Rode depois do build_vesper_v07.py e do _r2.

Saída: reports/design/v07_m4/pendentes/{prop_container_stack,icon_prop_container_stack}_{A,B}.png
       reports/design/v07_m4/sala_r3_{clara,escura}_{A,B}.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chests_r3d as CH  # noqa: E402
import build_vesper_v07 as V  # noqa: E402
import build_vesper_v07_r2 as R2  # noqa: E402
from r3d import Pal  # noqa: E402

PEND, REP, T = V.PEND, V.REP, V.T
P_OR = CH.P_ORANGE


def mini(sc, cx, cy, z0, hw, hd, body, lid, r, ridges=3, strap=None, seal=True, band=0.4, straps=True):
    """Um contêiner menor (o mesmo case: corpo, faixa de prata, tampa com gomos, cintas e selo), pé em z0."""
    spec = CH._spec(0.9)
    sc.rbox((cx, cy, z0 + body / 2), (hw, hd, body / 2), r, CH.P_ROYAL, paint=spec, extra=(CH.P_SPEC,))
    zb = z0 + body
    sc.rbox((cx, cy, zb), (hw + 0.3, hd + 0.3, band), r + 0.3, CH.P_SILVER)
    lz = zb + 0.7
    sc.rbox((cx, cy, lz + lid / 2), (hw, hd, lid / 2), r, CH.P_ROYAL,
            paint=lambda L, N: np.where(N[:, 2] > 0.85, 2, np.where(N @ CH._HV > 0.9, 1, 0)), extra=(CH.P_SPEC, CH.P_ROYAL_IN))
    m, g = 0.9, 0.8
    wr = (2 * (hw - m) - (ridges - 1) * g) / ridges
    for i in range(ridges):
        x = cx - hw + m + wr / 2 + i * (wr + g)
        sc.rbox((x, cy, lz + lid + 0.5), (wr / 2, hd - 0.8, 0.9), min(1.0, wr / 2 - 0.1), CH.P_ROYAL, paint=spec,
                extra=(CH.P_SPEC,))
    pal = strap or CH.P_SILVER
    for sx in ((-hw * 0.6, hw * 0.7) if straps else ()):
        sc.rbox((cx + sx, cy - hd - 0.4, zb + 0.2), (0.9, 0.45, 2.6), 0.4, pal)
    if seal:
        sc.rbox((cx - hw * 0.1, cy - hd - 0.4, zb - 2.4), (1.4, 0.45, 1.4), 1.0, CH.P_GOLD)


def stack(variant):
    sc = CH.scene(32, 40, -8.0)
    if variant == "A":                       # como o rascunho: 2 embaixo lado a lado (a da direita recuada e mais baixa), 1 em cima à esquerda
        mini(sc, -7.2, -3.0, 0, 7.0, 4.6, 7.5, 2.4, 1.8)
        mini(sc, 7.6, 1.8, 0, 6.6, 4.4, 5.5, 2.2, 1.7, seal=False)
        mini(sc, -7.0, -3.2, 10.7, 6.4, 4.2, 6.0, 2.2, 1.7)
    else:                                    # B: caixa grande em baixo à esquerda, pequena de cintas laranja à direita, e a de cima atravessada no meio
        mini(sc, -7.5, -3.0, 0, 7.5, 4.8, 7.5, 2.4, 1.8, seal=False)
        mini(sc, 8.2, 1.2, 0, 6.2, 4.2, 5.2, 2.0, 1.6, strap=P_OR, seal=False)
        mini(sc, -1.0, -0.8, 10.7, 7.0, 4.4, 6.0, 2.0, 1.6, strap=P_OR)
    return sc.render()


def icon(variant):
    sc = CH.scene(16, 16, -3.4)
    kw = dict(ridges=2, seal=False, band=0.3, straps=False)
    if variant == "A":
        mini(sc, -3.5, -1.2, 0, 3.6, 2.8, 3.4, 0.9, 1.1, **kw)
        mini(sc, 3.8, 1.0, 0, 3.2, 2.6, 2.6, 0.9, 1.0, **kw)
        mini(sc, -3.4, -1.3, 4.7, 3.2, 2.6, 2.6, 0.9, 1.0, **kw)
    else:
        mini(sc, -3.8, -1.2, 0, 3.8, 2.8, 3.4, 0.9, 1.1, **kw)
        mini(sc, 4.0, 0.8, 0, 3.0, 2.6, 2.4, 0.8, 1.0, strap=P_OR, **kw)
        mini(sc, -0.6, -0.4, 4.7, 3.6, 2.6, 2.6, 0.8, 1.0, strap=P_OR, **kw)
    return sc.render()


def build_room_r3(sp):
    """Sala 9×8 da rodada 1 com: container_open (aprovado) no lugar do quebrado e a pilha no canto de cima à direita."""
    room = V.build_room(dict(sp, container=Image.new("RGBA", (1, 1))))
    # a pilha (32×40, pé no tile): blit em (x, y−8) do tile, ordenado pelo pé; o aberto fica na parede oposta
    room.alpha_composite(sp["stack"], (7 * T, 1 * T + 24 - 8 + 0))
    room.alpha_composite(sp["open"], (5 * T - 4, 4 * T - 12 + 24))
    return room


def main():
    out = {}
    for v in "AB":
        cv = stack(v); CH.check(cv, "stack", (32, 40)); cv.image().save(PEND / f"prop_container_stack_{v}.png")
        ic = icon(v); CH.check(ic, "icon", (16, 16)); ic.image().save(PEND / f"icon_prop_container_stack_{v}.png")
        out[v] = Image.open(PEND / f"prop_container_stack_{v}.png").convert("RGBA")
    base = dict(top=Image.open(PEND / "hull_wall_top.png").convert("RGBA"), face=Image.open(PEND / "hull_wall_face.png").convert("RGBA"),
                floor=[Image.open(PEND / f"hull_floor_{i}.png").convert("RGBA") for i in range(4)],
                door=Image.open(PEND / "vesper_jammed_door.png").convert("RGBA"),
                panel=Image.open(PEND / "vesper_power_panel.png").convert("RGBA"),
                hatch=Image.open(PEND / "vesper_hatch_B.png").convert("RGBA"),
                light=Image.open(PEND / "vesper_emergency_light_A.png").convert("RGBA"),
                open=Image.open(V.ROOT / "assets" / "sprites" / "container_open.png").convert("RGBA"))
    for v in "AB":
        room = build_room_r3(dict(base, stack=out[v]))
        room.save(REP / f"sala_r3_clara_{v}.png")
        R2.dark_scene(room, (6 * T + 16, 2 * T + 44), [(T + 16, 24 + 22, 30, (.7, .08, .08))]).save(REP / f"sala_r3_escura_{v}.png")
    print("ok")


if __name__ == "__main__":
    main()
