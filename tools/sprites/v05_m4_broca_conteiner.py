#!/usr/bin/env python3
"""v0.5 M4 · Ícone da broca de mão (nv.1) e contêiner lacrado ABERTO. PROPOSTA: nada vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_m4_broca_conteiner.py

Gera em reports/design/v05_m4_broca_conteiner/: pendentes/ (candidatos), cenas e o index.html.
    icon_hand_drill_{A,B,C}.png      16×16  ícone de hotbar da broca de mão (a mesma pistola do drill_side.png)
    container_open_{A,B}.png       40×44  contêiner lacrado aberto (mesmo modelo/pivô do container_sealed.png)
Determinístico: sem aleatório.
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chests_r3d as C  # noqa: E402
from r3d import Canvas, Pal, SA  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v05_m4_broca_conteiner"
PEND = REP / "pendentes"

# ------------------------------------------------------------------ ícone da broca (paleta do hand_drill.py)
GREY = ["#d6d3e0", "#a6a1b8", "#77728a", "#565168"]
DARK = ["#5f586e", "#3f3a4c", "#2f2a3a", "#221e2b"]
STEEL = ["#eef0f6", "#c3c6d4", "#8f92a6", "#5e6176"]
OR, OR_D, OR_L = "#e2733a", "#a9482a", "#f4a06a"
CY, CY_L = "#59d0e6", "#c8f6ff"
SPARK = "#f2c46d"
KEY = {"a": GREY[0], "b": GREY[1], "c": GREY[2], "d": GREY[3], "k": DARK[1], "K": DARK[2],
       "o": OR, "p": OR_L, "q": OR_D, "l": CY_L, "y": CY, "w": STEEL[0], "x": STEEL[1], "z": STEEL[2], "v": STEEL[3],
       "s": SPARK}

# o contorno #1b1630 é desenhado por cima (Canvas.outline); aqui só o miolo, 14×14 dentro do 16×16
ICON_A = """
..............
..............
.aaaaaaaa.....
.ablbbbbbc....
.apooooooc....
.abbbbbbcKkwx.
.abbbbbbcKkxzv
.dccckkbcKkwx.
...ccKkc......
...ccKk.......
...ccKk.......
...qqqq.......
..............
..............
"""
# B · "robusta": carcaça mais alta, bateria laranja grande no cabo, bit mais curto e gordo
ICON_B = """
..............
.aaaaaaa......
.abbbbbbc.....
.ablbbbbc.....
.apooooocKkwx.
.abbbbbbcKkxzv
.abbbbbbcKkwx.
.dccccccc.....
..cckKb.......
..cckKb.......
..qooooq......
..qooooq......
..qqqqqq......
..............
"""
# C · "compacta": carcaça curta e o bit comprido, com espiral bem marcada (lê "broca" mesmo em 16 px)
ICON_C = """
..............
..............
..............
.aaaaaa.......
.ablbbbc......
.apoooocKkwx..
.abbbbbcKkxzvv
.abbbbbcKkwxz.
.dcckbccKkxz..
..ccKkc.......
..ccKkc.......
..ccKkc.......
..qqqqq.......
..............
"""


def grid_icon(txt, sparks=()):
    rows = [r for r in txt.strip("\n").split("\n")]
    cv = Canvas(16, 16)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                cv.px(x + 1, y + 1, KEY[ch])
    cv.outline()
    for x, y in sparks:
        cv.px(x, y, SPARK)
    return cv


def icon_a():
    return grid_icon(ICON_A)


def icon_b():
    return grid_icon(ICON_B)


def icon_c():
    return grid_icon(ICON_C)


# ------------------------------------------------------------------ contêiner aberto
VOID = Pal(["#2c2640", "#221d34", "#19152a", "#110e1e", "#0a0814"])
SCORCH = Pal(["#6e4a1e", "#5a3c18", "#3f2a12", "#2c1d0c", "#1c1208"])


def open_case(angle=-1.68, broken="stubs", lid_show=True):
    """O mesmo `case` aberto do chests_r3d (tampa girada na dobradiça de trás), mas com o miolo bem escuro e vazio,
    e o lacre rompido: cintas de aço cortadas (cotos) e o selo dourado partido em dois, escurecido."""
    w, h, hw, hd, body, lid, ridges, r = 40, 44, 17, 8.5, 13, 5, 4, 2.6
    sc = C.scene(w, h, -hd - 1.5)
    zb = body
    spec = C._spec()
    xs = hw * 0.36
    gap = 0.35
    for x0, x1 in ((-hw, xs - gap), (xs + gap, hw)):
        sc.rbox(((x0 + x1) / 2, 0, zb / 2), ((x1 - x0) / 2, hd, zb / 2), r, C.P_ROYAL, paint=spec, extra=(C.P_SPEC,))
    sc.rbox((0, 0, zb), (hw + 0.45, hd + 0.45, 0.7), r + 0.45, C.P_SILVER)
    sc.rbox((-hw - 0.9, -hd * 0.25, zb * 0.55), (0.9, 2.0, 1.1), 0.6, C.P_SILVER)
    lz0 = zb + 0.85
    lid_parts = []

    def lid_paint(L, N):
        return np.where(N[:, 2] > 0.85, 2, np.where(N @ C._HV > 0.93, 1, 0))
    lid_parts.append(((0, 0, lz0 + lid / 2), (hw, hd, lid / 2), r, C.P_ROYAL, lid_paint, (C.P_SPEC, C.P_ROYAL_IN)))
    m, g = 1.1, 1.3
    wr = (2 * (hw - m) - (ridges - 1) * g) / ridges
    hr = 2.4
    for i in range(ridges):
        cx = -hw + m + wr / 2 + i * (wr + g)
        lid_parts.append(((cx, 0, lz0 + lid + hr / 2 - 0.4), (wr / 2, hd - 1.0, hr / 2 + 0.4), min(1.4, wr / 2 - 0.1),
                          C.P_ROYAL, spec, (C.P_SPEC,)))
    # miolo escuro e vazio (fundo rebaixado um pouco, pra ler como buraco)
    sc.box((-hw + 1.4, hw - 1.4), (-hd + 1.4, hd - 1.4), (zb - 0.4, lz0 + 0.1), VOID)
    # trinco aberto (levantado) à direita e a dobradiça
    sc.rbox((xs, -hd - 0.55, zb + 0.6), (1.7, 0.55, 1.9), 0.5, C.P_SILVER)
    if broken in ("stubs", "fallen"):
        # cintas rompidas: só o coto de baixo, na frente do corpo, com a ponta cortada escura
        for sx in (-hw * 0.62, hw * 0.78):
            sc.rbox((sx, -hd - 0.5, zb - 2.0), (1.0, 0.5, 1.9), 0.5, C.P_SILVER)
            sc.rbox((sx, -hd - 0.6, zb - 0.1), (1.0, 0.5, 0.35), 0.2, C.P_DARK)
        # selo partido: só a metade de baixo sobra (dourado fosco), com a rachadura escura em cima
        sc.rbox((-hw * 0.18, -hd - 0.5, zb - 4.4), (1.9, 0.5, 0.9), 0.4, C.P_GOLD)
        sc.rbox((-hw * 0.18 - 0.6, -hd - 0.6, zb - 2.6), (0.7, 0.5, 0.8), 0.3, C.P_GOLD)
        sc.dot(round(-hw * 0.18) + 1, -hd - 1.2, zb - 2.6, "#1b1630", always=True)
        sc.dot(round(-hw * 0.18), -hd - 1.2, zb - 3.4, "#1b1630", always=True)
    pivot = (0, hd, lz0)

    def inside(L, N):
        return np.where(N[:, 2] < -0.85, 2, np.where(N @ C._HV > 0.93, 1, 0))
    for k, (c, half, rr, pal, pnt, ex) in enumerate(lid_parts):
        sc.rbox(c, half, rr, pal, paint=inside if k == 0 else pnt, extra=ex if k else (C.P_SPEC, C.P_ROYAL_IN),
                rot_x=angle, pivot=pivot)
    cv = sc.render()
    return cv


def cont_a():      # tampa totalmente em pé, cotos de cinta e selo partido
    return open_case(-1.68, "stubs")


def cont_b():      # tampa meio aberta (≈ 70°): lê "foi forçada", cobre menos o fundo da cena
    return open_case(-1.2, "stubs")


# ------------------------------------------------------------------ rodada 2
KEY2 = dict(KEY)
KEY2.update({"A": "#fdf8ec", "B": "#efe6d4", "D": "#d6c9b4", "E": "#a99a8c",              # bege da máquina
             "m": "#a7a3b8", "M": "#7d7892", "n": "#58536b", "N": "#3a3549",             # metal
             "S": "#1d2b3a", "T": "#2c4256", "Y": "#59d0e6", "L": "#c8f6ff", "G": "#7fd67a",
             "e": "#e0602a", "r": "#ff6a55", "f": "#5a6770", "F": "#4c5861", "g": "#72808a", "h": "#3a474e",
             "W": "#f1f3f8", "u": "#d9dde6", "t": "#8a8ea0", "j": "#4f5262", "J": "#3d3f4d",
             "R": "#625d78", "Q": "#8f8aa6", "C": "#c9c4d6"})


def grid2(txt, sparks=(), ox=1, oy=1):
    cv = Canvas(16, 16)
    for y, row in enumerate(txt.strip("\n").split("\n")):
        for x, ch in enumerate(row):
            if ch != ".":
                cv.px(x + ox, y + oy, KEY2[ch])
    cv.outline()
    for x, y, c in sparks:
        cv.px(x, y, c)
    return cv


# 2 · broca de mão: a MESMA pistola do drill_side.png (quadro 0), de perfil
HAND_1 = """
..............
..............
.aaaaaaa......
.ablbbbbc.....
.apoooooc.....
.abbbbbbcKkwx.
.abbbbbbcKkxzv
.dccckkbcKkwx.
...ccKkc......
...ccKk.......
...ccKk.......
...qqqq.......
..............
..............
"""


def shear(cv, k):
    """Inclina o desenho: cada coluna sobe floor((x-1)*k) px (bocal pra cima-direita), contorno refeito."""
    inner = Canvas(16, 16)
    src = cv.a
    sol = src[:, :, 3] == 255
    # tira o contorno (cor exata) pra refazer depois
    for y in range(16):
        for x in range(16):
            if sol[y, x] and tuple(src[y, x, :3]) != (0x1b, 0x16, 0x30):
                dy = int(x * k)
                inner.px(x, y + 2 - dy, tuple(int(v) for v in src[y, x]))
    inner.outline()
    return inner


def hand_1():
    return grid2(HAND_1)


def rot(cv, deg):
    """Gira o desenho (sem contorno) por votação de cor num bloco 6×6 e refaz o contorno."""
    src = cv.a
    base = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            if src[y, x, 3] == 255 and tuple(src[y, x, :3]) != (0x1b, 0x16, 0x30):
                base.putpixel((x, y), tuple(int(v) for v in src[y, x]))
    big = base.resize((96, 96), Image.NEAREST).rotate(deg, resample=Image.NEAREST, center=(48, 52))
    out = Canvas(16, 16)
    for y in range(16):
        for x in range(16):
            blk = [big.getpixel((x * 6 + i, y * 6 + j)) for i in range(6) for j in range(6)]
            op = [c for c in blk if c[3] == 255]
            if len(op) >= 18:
                out.px(x, y, max(set(op), key=op.count))
    out.outline()
    return out


def hand_2():
    return rot(grid2(HAND_1), 28)


# 3 · drill automática (a máquina do machine_drill.png: base com tela, mastro, braço, cabeça e feixe ciano no chão)
DR_A = """
..............
.ooAAAAAAA....
.BDBBBBBBBBc..
.BD....BLBBc..
.oe....DDDDc..
.BD.....DD....
.BD.....YL....
.BD.....YL....
.BD.....YL....
BBBBBBB.YL....
BSSSSSB.YL....
BSSSSSBeYLe.s.
EEEEEEEeeLeen.
..............
"""


DR_C = """
..............
..............
...mmmmmmmm...
..mAAAAAAAAm..
..mBLBBBBBBm..
..mDDBBBBDDm..
...nnDYLDnn...
.....DYLD.....
......YL......
......YL......
.NNNNNYLNNNNN.
.nnnnnLYnnnnn.
.NnsNeeeeNnsN.
..............
"""


def drill_a():
    return grid2(DR_A, sparks=())


def drill_b():
    # variante: a mesma máquina com o LED verde ligado na base e o mastro com mais uma faixa laranja
    return grid2(DR_A.replace("BSSSSSB", "BSSSSGB").replace(".BD.....YL....\n.BD.....YL....\n.BD.....YL", ".BD.....YL....\n.oe.....YL....\n.BD.....YL", 1))


def drill_c():
    return grid2(DR_C)


# 4 · aba "Base" do construtor
BASE_A = """
NNNNNNNNNNNNNN
nnnnnnnnnnnnnn
BBBBBBMMMMBBBB
BBBBBBMrrMBBBB
BDDDDBjJJjBDDD
BBBBBBJWWJBBBB
BBBBBWJJJJWBBB
BBBBBWJttJWBBB
BBBBBWJjjJWBBB
oooooWJjjJWooo
eeeeeWJjjJWeee
fgfgfgfgfgfgfg
FfFfFfFfFfFfFf
..............
"""
BASE_B = """
..............
....MMMMMM....
...MmmmmmmM...
..MBBBBBBBBM..
..BAAAAAAAAB..
..BBBBBBBBBB..
..BDDBjJJjBB..
..BBBBJrrJBB..
..oooooJWJoo..
..eeeeeJJJee..
.fgfgfgfgfgfg.
.FfFfFfFfFfFf.
..............
..............
"""
BASE_C = """
..............
.....MMMMMMM..
...MmBBBBBBBM.
..MmBAAAAAABBM
..MBBDDDDDDDBM
..MBBBBBBBBBBM
..MoooooooooBM
..MeeeeeeeeeBM
..nNnfgfgfgfgf
....fgfgfgfgfg
.....fFfFfFfF.
......FhFhFh..
..............
..............
"""


def base_a():
    return grid2(BASE_A, ox=1, oy=1)


def base_b():
    return grid2(BASE_B)


def base_c():
    return grid2(BASE_C)


# ------------------------------------------------------------------ rodada 3
KEY2.update({"X": "#ffd27a", "Z": "#fff4cc"})


def frame0():
    return Image.open(SPR / "drill_side.png").convert("RGBA").crop((0, 0, 24, 16))


def to_canvas(im):
    cv = Canvas(16, 16)
    for y in range(16):
        for x in range(16):
            p = im.getpixel((x, y))
            if p[3] == 255:
                cv.px(x, y, tuple(p))
    return cv


def hand_x():
    """Opção X: o corpo pixel-idêntico ao quadro 0 (colunas 2..13 do quadro) e a broca encurtada em 3 colunas."""
    src = frame0().crop((2, 2, 21, 12))                  # 19×10, o desenho todo
    keep = [i for i in range(19) if i not in (13, 14, 15)]
    out = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for j, i in enumerate(keep):
        for y in range(10):
            out.putpixel((j, y + 3), src.getpixel((i, y)))
    return to_canvas(out)


def hand_y():
    """Opção Y: o quadro 0 inteiro (19×10) reduzido por nearest pra 16×8, centralizado, e só os buracos do contorno
    tapados (pixel que ficou colado num pixel de cor sem contorno em volta)."""
    src = frame0().crop((2, 2, 21, 12))
    small = src.resize((16, 8), Image.NEAREST)
    out = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    out.paste(small, (0, 4))
    cv = to_canvas(out)
    cv.outline()
    return cv


# 4b · aba Base com a porta entreaberta (parte da fachada A)
BASE_1 = """
NNNNNNNNNNNNNN
nnnnnnnnnnnnnn
BBBBBBMMMMBBBB
BBBBBBMXXMBBBB
BDDDDBjJJjBDDD
BBBBBBJJJJBBBB
BBBBBWJJZXWBBB
BBBBBWJJZXWBBB
BBBBBWJjZXWBBB
oooooWJjZXWooo
eeeeeWJjZXWeee
fgfgfgfgXXgfgf
FfFfFfFfFZFfFf
..............
"""
BASE_2 = """
NNNNNNNNNNNNNN
nnnnnnnnnnnnnn
BBBBBBMMMMBBBB
BBBBBBMGGMBBBB
BDDDDBjJJjBDDD
BBBBBBJJJJBBBB
BBBBBWJJJZWBBB
BBBBBWJttZWBBB
BBBBBWJjjZWBBB
oooooWJjjZWooo
eeeeeWJjjZWeee
fgfgfgXXXXgfgf
FfFfFfFXXXFfFf
..............
"""


def base_1():
    return grid2(BASE_1)


def base_2():
    return grid2(BASE_2)


# ------------------------------------------------------------------ rodada 4 · broca da referência do dono
def hand_ref(bw, prof):
    """Broca de perfil (referência do dono): corpo creme com topo claro, visor escuro com LED verde, faixa laranja,
    barriga cinza com detalhe amarelo, base escura com friso laranja, mandril escuro e broca cônica com anéis.
    bw = largura do corpo; prof = meia-altura da broca em cada coluna (da raiz pra ponta)."""
    g = [["."] * 14 for _ in range(9)]
    for y in range(9):
        for x in range(bw):
            ch = "."
            if y == 0:
                ch = "B" if x == 1 else "A" if 1 < x < bw - 1 else "."
            elif y == 1:
                ch = "B" if x == 0 else "D" if x == bw - 1 else "A"
            elif y in (2, 3):
                ch = "B" if x == 0 else "D" if x == bw - 1 else ("S" if x in (1, 2) else "A")
                if y == 3 and x == 1:
                    ch = "G"
                if y == 3 and 2 < x < bw - 1:
                    ch = "B"
            elif y in (4, 5):
                ch = "p" if (y == 4 and x == 0) else "o"
            elif y == 6:
                ch = "X" if x == 3 else ("M" if x == bw - 1 else "m")
            elif y == 7:
                ch = "N" if 0 < x < bw else "."
            elif y == 8:
                ch = "o" if 0 < x < bw - 1 else "."
            g[y][x] = ch
    for y in range(2, 7):                                  # mandril: 2 colunas escuras
        g[y][bw], g[y][bw + 1] = "K", "k"
    stripes = "wzxvxz"
    for j, hh in enumerate(prof):
        x = bw + 2 + j
        for y in range(4 - hh, 4 + hh + 1):
            g[y][x] = stripes[j % len(stripes)]
    return "\n".join("".join(r) for r in g)


def hand_r1():
    return grid2(hand_ref(7, [2, 2, 1, 1, 0]), ox=1, oy=3)


def hand_r2():
    return grid2(hand_ref(6, [2, 2, 1, 1, 1, 0]), ox=1, oy=3)


# ------------------------------------------------------------------ rodada 4 · aba Base = cápsula de pouso (pod.png, de frente)
CAP_A = """
......pp......
......nn......
....BAAAAD....
..BAAAAAAAAD..
.BAAAAAAAAAAD.
.BAAonYnnoAAD.
.BAAonnnnoAAD.
.ooAonnnnoAoo.
.BDDonnnnoDDD.
..DDDmmmmDDD..
..nn..mm..nn..
.nn...mm...nn.
nn....oo....nn
oo..........oo
"""
CAP_B = """
......pp......
......nn......
....BAAAAD....
..BAAAAAAAAD..
.BAAAAAAAAAAD.
.BAAoSSSSoAAD.
.BAAoSYLSoAAD.
.ooAoSSSSoAoo.
.BDDoSSSSoDDD.
..DDDmmmmDDD..
.nnn..mm..nnn.
nn.oo.oo.oo.nn
..............
..............
"""


def cap_a():
    return grid2(CAP_A)


def cap_b():
    return grid2(CAP_B)


ITEMS = {
    "icon_hand_drill_A": (icon_a, (16, 16)),
    "icon_hand_drill_B": (icon_b, (16, 16)),
    "icon_hand_drill_C": (icon_c, (16, 16)),
    "container_open_A": (cont_a, (40, 44)),
    "container_open_B": (cont_b, (40, 44)),
    "icon_hand_drill_1": (hand_1, (16, 16)),
    "icon_hand_drill_2": (hand_2, (16, 16)),
    "icon_drill_A": (drill_a, (16, 16)),
    "icon_drill_B": (drill_b, (16, 16)),
    "icon_drill_C": (drill_c, (16, 16)),
    "icon_tab_base_A": (base_a, (16, 16)),
    "icon_tab_base_B": (base_b, (16, 16)),
    "icon_hand_drill_X": (hand_x, (16, 16)),
    "icon_tab_base_cap_A": (cap_a, (16, 16)),
    "icon_tab_base_cap_B": (cap_b, (16, 16)),
    "icon_hand_drill_R1": (hand_r1, (16, 16)),
    "icon_hand_drill_R2": (hand_r2, (16, 16)),
    "icon_hand_drill_Y": (hand_y, (16, 16)),
    "icon_tab_base_1": (base_1, (16, 16)),
    "icon_tab_base_2": (base_2, (16, 16)),
}


def export():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, (fn, size) in ITEMS.items():
        cv = fn()
        C.check(cv, name, size)
        cv.image().save(PEND / f"{name}.png")
        out[name] = hashlib.md5((PEND / f"{name}.png").read_bytes()).hexdigest()
    return out


if __name__ == "__main__":
    md5 = export()
    import v05_m4_broca_conteiner_report as RR
    page = RR.build()
    for k, v in md5.items():
        print(f"{k:22s} {v}")
    print("ok ->", page)
