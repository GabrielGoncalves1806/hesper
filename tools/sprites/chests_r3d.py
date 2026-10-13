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


# ---- v1.1: o case da referência do dono (reports/design/refs/bau_referencia_dono.png) -------------------------------
# azul royal saturado (cores tiradas da referência: frente #007de0, lados #0046b7, topo #003ba8), puxado pro 3/4 do
# jogo: o tampo leva o tom 0, a frente o 1, a lateral o 3. Brilho especular claro nas arestas de cima.
ROYAL = ["#2f93f4", "#0a74de", "#055ec8", "#0444a8", "#022c78"]
ROYAL_IN = ["#0757c0", "#04479f", "#033a88", "#022f70", "#01214f"]     # fundo dos sulcos da tampa e lado de dentro
SILVER = ["#d9dde6", "#a9b0be", "#8c93a3", "#636a7a", "#414553"]
P_ROYAL = Pal(ROYAL)
P_ROYAL_IN = Pal(ROYAL_IN)
P_SILVER = Pal(SILVER)
P_SPEC = Pal(["#d4ecff"] * 5, emit=True, emit_tone=0)
_HV = np.array([-0.46, -0.31, 0.86]) / np.linalg.norm([-0.46, -0.31, 0.86]) + np.array([0, -math.cos(0.611), math.sin(0.611)])
_HV = _HV / np.linalg.norm(_HV)


def _spec(cut=0.93):
    """Pintura do plástico: brilho especular (índice 1) onde a normal bate no meio-vetor luz/câmera."""
    return lambda L, N: np.where(N @ _HV > cut, 1, 0)


def case(w, h, hw, hd, body, lid, ridges=4, opened=False, contents=(), seal=False, r=2.2):
    """O modelo único (v1.1). hw, hd = meia largura e meia profundidade; body = altura do corpo até a emenda;
    lid = altura da tampa (sem os gomos). opened: tampa em pé, girada pra trás na dobradiça, miolo à mostra."""
    sc = scene(w, h, -hd - 1.5)
    zb = body
    spec = _spec()
    # corpo em duas partes: o recorte vertical fica embaixo do trinco, à direita do meio
    xs = hw * 0.36
    gap = 0.35
    for x0, x1 in ((-hw, xs - gap), (xs + gap, hw)):
        sc.rbox(((x0 + x1) / 2, 0, zb / 2), ((x1 - x0) / 2, hd, zb / 2), r, P_ROYAL, paint=spec, extra=(P_SPEC,))
    # faixa cinza-prata contornando a caixa na emenda
    sc.rbox((0, 0, zb), (hw + 0.45, hd + 0.45, 0.7 if hw >= 9 else 0.6), r + 0.45, P_SILVER)
    # alça de metal na lateral esquerda (sai um tico pra fora da silhueta)
    sc.rbox((-hw - 0.9, -hd * 0.25, zb * 0.55), (0.9, 2.0, 1.1), 0.6, P_SILVER)
    lz0 = zb + 0.85
    lid_parts = []

    def lid_paint(L, N):                         # o tampo da tampa (o fundo dos sulcos) é mais escuro
        return np.where(N[:, 2] > 0.85, 2, np.where(N @ _HV > 0.93, 1, 0))
    lid_parts.append(((0, 0, lz0 + lid / 2), (hw, hd, lid / 2), r, P_ROYAL, lid_paint, (P_SPEC, P_ROYAL_IN)))
    m, g = 1.1, 1.0 if hw < 9 else 1.3
    wr = (2 * (hw - m) - (ridges - 1) * g) / ridges
    hr = 1.6 if hw < 9 else (2.4 if hw < 14 else 2.8)
    for i in range(ridges):
        cx = -hw + m + wr / 2 + i * (wr + g)
        lid_parts.append(((cx, 0, lz0 + lid + hr / 2 - 0.4), (wr / 2, hd - 1.0, hr / 2 + 0.4), min(1.4, wr / 2 - 0.1),
                          P_ROYAL, spec, (P_SPEC,)))
    if not opened:
        for c, half, rr, pal, pnt, ex in lid_parts:
            sc.rbox(c, half, rr, pal, paint=pnt, extra=ex)
        # trinco de metal à direita, em cima da faixa (e em cima do recorte)
        tw = 1.3 if hw < 9 else 1.7
        sc.rbox((xs, -hd - 0.55, zb + 0.6), (tw, 0.55, 1.9 if hw >= 9 else 1.4), 0.5, P_SILVER)
        sc.dot(round(xs), -hd - 1.2, zb + 0.4, "#464a59", always=True)
        if seal:                                       # lacrado: duas cintas de aço por cima da emenda + o selo
            for sx in (-hw * 0.62, hw * 0.78):
                sc.rbox((sx, -hd - 0.5, zb + 0.3), (1.0, 0.5, 3.6), 0.5, P_SILVER)
            sc.rbox((-hw * 0.18, -hd - 0.5, zb - 3.4), (1.9, 0.5, 1.9), 1.5, P_GOLD)
            sc.dot(round(-hw * 0.18), -hd - 1.2, zb - 3.4, GOLD_D, always=True)
        return sc.render()
    # aberta: o miolo escuro com o conteúdo e a tampa em pé, girada na dobradiça de trás
    sc.box((-hw + 1.4, hw - 1.4), (-hd + 1.4, hd - 1.4), (zb, lz0 + 0.1), P_DARK)
    for (x, y, c) in contents:
        sc.box((x - 1.6, x + 1.6), (y - 1.6, y + 1.6), (lz0 - 0.6, lz0 + 1.8), ore_pal(c))
    pivot = (0, hd, lz0)

    def inside(L, N):                                  # o lado de dentro da tampa (fica virado pra câmera)
        return np.where(N[:, 2] < -0.85, 2, np.where(N @ _HV > 0.93, 1, 0))
    for k, (c, half, rr, pal, pnt, ex) in enumerate(lid_parts):
        sc.rbox(c, half, rr, pal, paint=inside if k == 0 else pnt, extra=ex if k else (P_SPEC, P_ROYAL_IN),
                rot_x=-1.68, pivot=pivot)
    return sc.render()


def chest(opened=False):
    cont = ((-6, -1, ORES[0]), (-1, 2, ORES[1]), (4, -1, ORES[2]), (8, 2, ORES[0]), (-8, 2, ORES[2]))
    return case(32, 40, 13, 6.5, 10, 4, ridges=4, opened=opened, contents=cont)


def loot_crate(empty=False):
    """Caixa de saque: o mesmo case menor (cabe no tile 32×32, desenhada no canto do tile). Cheia: fechada;
    vazia: tampa aberta e o miolo vazio."""
    return case(32, 32, 10.5, 5, 7, 3, ridges=3, opened=empty, r=1.8)


def container_sealed():
    """O mesmo case maior, com duas cintas de aço por cima da emenda e o selo dourado da colônia: não abre."""
    return case(40, 44, 17, 8.5, 13, 5, ridges=4, seal=True, r=2.6)


def icon_chest():
    """Ícone 16×16 do item: o case fechado, com 3 gomos."""
    sc = scene(16, 16, -4.5)
    spec = _spec(0.9)
    sc.rbox((0, 0, 2.5), (6.5, 3.2, 2.5), 1.2, P_ROYAL, paint=spec, extra=(P_SPEC,))
    sc.rbox((0, 0, 5.0), (6.8, 3.5, 0.6), 1.2, P_SILVER)
    sc.rbox((0, 0, 6.6), (6.5, 3.2, 1.1), 1.0, P_ROYAL, paint=lambda L, N: np.where(N[:, 2] > 0.85, 1, 0),
            extra=(P_ROYAL_IN,))
    for cx in (-4.2, 0, 4.2):
        sc.rbox((cx, 0, 8.2), (1.6, 2.3, 0.8), 0.7, P_ROYAL, paint=spec, extra=(P_SPEC,))
    sc.rbox((2.4, -3.7, 5.2), (0.8, 0.4, 1.0), 0.3, P_SILVER)
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
