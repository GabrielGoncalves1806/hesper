#!/usr/bin/env python3
"""Família de caixas no motor r3d (proposta, pedido do dono): UM modelo só, o contêiner padrão azul, na pegada do
contêiner de armazenamento básico do The Planet Crafter, com a forma do chest() experimental (base de metal, corpo,
tampa com friso, trinco na frente) e o contorno #1b1630 e o laranja #e2733a do jogo.

    python3 tools/sprites/chests_r3d.py

Gera em reports/design/bau_r3d/: pendentes/ (os PNGs no tamanho do contrato), before/ (os de hoje), as prévias, a
cena da base e o index.html. Nada vai pra assets/ sem o ok do dono.

    chest.png / chest_open.png               32×40  baú fabricado (fechado / aberto com o conteúdo à mostra)
    icon_chest.png                           16×16  ícone do item
    loot_crate.png / loot_crate_empty.png    32×32  caixa de saque dos destroços (cheia: fechada / vazia: aberta, sem nada)
    container_sealed.png                     40×44  contêiner lacrado do bolsão (o mesmo modelo, maior, com trava e selo)

Cheia × vazia/aberta muda só a tampa e o conteúdo, nunca a cor.
"""

from __future__ import annotations

import hashlib
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from r3d import SA, Pal, Scene  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
OUT = ROOT / "reports" / "design" / "bau_r3d"
PEND = OUT / "pendentes"
BEFORE = OUT / "before"

OUTLINE = "#1b1630"
ORANGE, ORANGE_D, ORANGE_L = "#e2733a", "#a9482a", "#f4a06a"
GOLD, GOLD_D, GOLD_L = "#f2c46d", "#b8823c", "#fff0b8"
OK, ALERT, AMBER = "#7fd67a", "#ff6a55", "#f2a33a"

# a cor principal: azul de contêiner (brilho, claro, base, sombra, fundo), frio e saturado, sem virar ciano do O₂
# (a luz de cima cai no tom 0 no tampo, 1 na frente e 3 na lateral: a frente é o azul "de verdade")
BLUE = ["#8ec4f4", "#4a86d0", "#3a6cb4", "#2b5190", "#1c3263"]
BLUE_D = ["#5f98da", "#346aae", "#2b5899", "#21427a", "#152a52"]     # o painel rebaixado da frente
P_BLUE = Pal(BLUE)
P_BLUE_D = Pal(BLUE_D)
P_METAL = Pal(["#a7a3b8", "#7d7892", "#58536b", "#3a3549", "#26222f"])
P_STEEL = Pal(["#e3e5ee", "#b9bccb", "#8f92a6", "#5e6176", "#3a3549"])
P_DARK = Pal(["#4a4458", "#3a3549", "#2e2a3a", "#242030", "#1b1726"])
P_ORANGE = Pal(["#ffd0a8", ORANGE_L, ORANGE, ORANGE_D, "#6e2a1c"])
P_GOLD = Pal([GOLD_L, GOLD, GOLD_D, "#8a5a28", "#6e4a1e"])
ORES = ("#e8a066", "#c3d1e2", "#a6ecff")


def scene(w, h, front_y):
    """Cena com o chão posicionado pra borda da frente (Y=front_y, Z=0) cair na penúltima linha."""
    return Scene(w, h, ground=h - 2 - (-front_y) * SA)


def ore_pal(c):
    r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
    d = "#%02x%02x%02x" % (int(r * .62), int(g * .62), int(b * .66))
    return Pal([c, c, d, d, "#3a3040"])


def container(w, h, hw, hd, body, lid, opened=False, contents=(), led=OK, seal=False, skid=3, band=True):
    """O modelo único. hw, hd = meia largura e meia profundidade do corpo; body = altura do corpo (acima da base);
    lid = altura da tampa. opened: tampa tombada pra trás e o miolo à mostra (contents = [(x, y, cor)])."""
    sc = scene(w, h, -hd - 2)
    z0 = skid
    z1 = z0 + body
    sc.box((-hw - 1, hw + 1), (-hd - 2, hd + 1), (0, skid), P_METAL)            # base (skid) de metal
    bz = (z0 + z1) / 2 - (body * 0.05)

    def front(L, face):
        """Frente (face 2 = −Y): painel rebaixado mais escuro e a faixa laranja de acento."""
        x, z = L[:, 0], L[:, 2]
        f = face == 2
        panel = f & (np.abs(x) < hw - 2.6) & (z > -body / 2 + 1.6) & (z < body / 2 - 1.8)
        strip = f & (np.abs(z - (bz - (z0 + z1) / 2)) < 0.9) & band
        return np.where(strip, 2, np.where(panel, 1, 0))
    if not opened:
        sc.box((-hw, hw), (-hd, hd), (z0, z1), P_BLUE, paint=front, extra=(P_BLUE_D, P_ORANGE))
        # tampa: um tico maior que o corpo, com o friso escuro embaixo (a emenda)
        sc.box((-hw - 0.5, hw + 0.5), (-hd - 0.5, hd + 0.5), (z1, z1 + lid), P_BLUE,
               paint=lambda L, face: np.where(L[:, 2] < -lid / 2 + 1.0, 1, 0), extra=(P_DARK,))
        # trinco: chapinha de aço atravessando a emenda + LED
        tw = 2.0 if hw < 14 else 2.5
        sc.box((-tw, tw), (-hd - 1.4, -hd - 0.4), (z1 - 4, z1 + 2), P_STEEL if not seal else P_METAL)
        sc.dot(0, -hd - 1.6, z1 + 0.5, led, always=True)
        if seal:                                                                 # lacrado: trava e selo
            for sx in (-hw + 3.5, hw - 3.5):                                     # duas travas laterais
                sc.box((sx - 1.2, sx + 1.2), (-hd - 1.2, -hd - 0.3), (z1 - 3, z1 + lid - 1), P_STEEL)
            sc.box((-3, 3), (-hd - 1.0, -hd - 0.2), (z1 - 9, z1 - 4.5), P_GOLD)  # placa do selo da colônia
            for dx, dz in ((-1, -6.2), (0, -7.2), (1, -6.2), (0, -5.6)):
                sc.dot(dx, -hd - 1.3, z1 + dz, GOLD_D, always=True)
        return sc.render()
    # aberto: 4 paredes do corpo, o fundo escuro e a tampa tombada pra trás
    t = 1.5
    for (xr, yr) in (((-hw, hw), (-hd, -hd + t)), ((-hw, hw), (hd - t, hd)), ((-hw, -hw + t), (-hd + t, hd - t)),
                     ((hw - t, hw), (-hd + t, hd - t))):
        sc.box(xr, yr, (z0, z1), P_BLUE, paint=front, extra=(P_BLUE_D, P_ORANGE))
    floor = z0 + body * 0.45
    sc.box((-hw + t, hw - t), (-hd + t, hd - t), (z0, floor), P_DARK)
    for (x, y, c) in contents:
        sc.box((x - 1.8, x + 1.8), (y - 1.8, y + 1.8), (floor, floor + 3), ore_pal(c))
    sc.obox((0, hd + 2.5, z1 + lid / 2 + 5.5), (hw + 0.5, lid / 2, 6.0 if hw < 14 else 7.0), P_BLUE,
            paint=lambda L, face: np.where(face == 2, 1, 0), extra=(P_BLUE_D,), rot_x=-0.45)
    sc.box((-2, 2), (-hd - 1.2, -hd), (z1 - 4, z1), P_STEEL)
    return sc.render()


def chest(opened=False):
    cont = ((-6, -2, ORES[0]), (-1, 2, ORES[1]), (4, -1, ORES[2]), (6, 3, ORES[0]), (-4, 3, ORES[2]))
    return container(32, 40, 11, 8, 12, 5, opened=opened, contents=cont, led=OK)


def loot_crate(empty=False):
    """Caixa de saque: o mesmo modelo menor (cabe no tile 32×32, desenhada no canto do tile). Cheia: fechada com o
    LED âmbar; vazia: tampa aberta e o miolo vazio."""
    return container(32, 32, 9, 6, 9, 4, opened=empty, contents=(), led=AMBER)


def container_sealed():
    """O mesmo modelo maior e mais pesado, com duas travas, selo dourado e LED vermelho: não abre."""
    return container(40, 44, 15, 9, 15, 6, led=ALERT, seal=True, skid=4)


def icon_chest():
    """Ícone 16×16 do item: o baú fechado, enxuto (sem a base, pra caber)."""
    sc = scene(16, 16, -5)
    sc.box((-6, 6), (-4, 4), (0, 6), P_BLUE,
           paint=lambda L, face: np.where((face == 2) & (np.abs(L[:, 2]) < 0.8), 1, 0), extra=(P_ORANGE,))
    sc.box((-6.4, 6.4), (-4.4, 4.4), (6, 9), P_BLUE,
           paint=lambda L, face: np.where(L[:, 2] < -0.7, 1, 0), extra=(P_DARK,))
    sc.box((-1, 1), (-5.2, -4.4), (4, 7), P_STEEL)
    return sc.render()


ITEMS = {
    "chest": (lambda: chest(False), (32, 40)),
    "chest_open": (lambda: chest(True), (32, 40)),
    "icon_chest": (icon_chest, (16, 16)),
    "loot_crate": (lambda: loot_crate(False), (32, 32)),
    "loot_crate_empty": (lambda: loot_crate(True), (32, 32)),
    "container_sealed": (container_sealed, (40, 44)),
}


def check(cv, name, size):
    a = cv.a
    assert (a.shape[1], a.shape[0]) == size, f"{name}: {a.shape[1]}×{a.shape[0]} (esperado {size})"
    al = set(np.unique(a[:, :, 3]).tolist())
    assert al <= {0, 255}, f"{name}: alpha fora de 0/255: {al}"


def export():
    PEND.mkdir(parents=True, exist_ok=True)
    for old in PEND.glob("*.png"):
        old.unlink()
    out = {}
    for name, (fn, size) in ITEMS.items():
        cv = fn()
        check(cv, name, size)
        cv.image().save(PEND / f"{name}.png")
        out[name] = hashlib.md5((PEND / f"{name}.png").read_bytes()).hexdigest()
    # os de hoje (antes), copiados uma vez pra o report não mudar quando o assets/ for promovido
    BEFORE.mkdir(parents=True, exist_ok=True)
    for name in ("chest", "chest_open", "icon_chest", "loot_crate", "loot_crate_empty"):
        dst = BEFORE / f"{name}.png"
        if not dst.exists():
            shutil.copy(SPR / f"{name}.png", dst)
    return out


if __name__ == "__main__":
    md5 = export()
    import chests_r3d_report as RR
    page = RR.build()
    for k, v in md5.items():
        print(f"{k:20s} {v}")
    print("ok ->", page)
