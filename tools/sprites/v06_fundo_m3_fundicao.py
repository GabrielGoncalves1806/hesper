#!/usr/bin/env python3
"""v0.6 Fundo M3 (v2 = r3d; a v1 chapada ficou aqui como smelter_flat só pra comparação) · Fundição (key `smelter`): máquina nv.1 apagada + tira acesa, e icon_copper_ingot.
PROPOSTA: nada vai pra assets/sprites sem o ok do dono.

    python3 tools/sprites/v06_fundo_m3_fundicao.py

Saída: reports/design/v06_fundo_m3_fundicao/ (pendentes/ + prévias + index.html). Só LÊ assets/sprites/.
Determinístico (sem aleatório), alpha só 0/255 (exceto a sombra de chão, 36%), contorno #1b1630.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_sprites as M  # noqa: E402
import machines_r3d as MR  # noqa: E402
import v05_bancada_itens as BI  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v06_fundo_m3_fundicao"
PEND = REP / "pendentes"
C, SHADOW = M.C, M.SHADOW
INK = "#1b1630"
W, H = 40, 56
H0 = 58   # desenho em 58 e corta 2 px de cima (o pé fica no mesmo lugar)
FRAMES, FPS = 4, 5

# paleta da família nv.1 (tirada do aquecedor/derretedor)
CREAM = ["#fdf8ec", "#efe6d4", "#d6c9b4"]
GR = ["#d9dde6", "#a7a3b8", "#7d7892", "#58536b"]
DK = ["#4a4458", "#6a5f72", "#3a3549"]
OR, OR_L, OR_D = "#e2733a", "#f4a06a", "#a9482a"
GLOW = ["#fff4cc", "#ffd27a", "#ff9a3d", "#e0602a", "#a8402a"]
IRON_O = ["#dcc0a3", "#b99b82", "#7a6552"]
CU_O = ["#f7966a", "#e0703f", "#aa4a2a"]


def chunk(cv, x, y, pal):
    """pepita de minério 4x3 com contorno, pra boca do funil"""
    cv.rect(x - 1, y - 1, 6, 5, C(INK))
    cv.rect(x, y, 4, 3, C(pal[1]))
    cv.rect(x, y, 3, 1, C(pal[0]))
    cv.rect(x + 3, y + 1, 1, 2, C(pal[2]))
    cv.rect(x, y + 2, 4, 1, C(pal[2]))


def smelter_flat(lit: bool, f: int = 0) -> M.Canvas:
    cv = M.Canvas(W, H0)
    cv.ellipse(20, 55, 18, 3, SHADOW)
    # base
    cv.rect(3, 50, 34, 8, C(INK))
    cv.rect(4, 51, 32, 1, C(GR[0]))
    cv.rect(4, 52, 32, 2, C(GR[1]))
    cv.rect(4, 54, 32, 2, C(GR[2]))
    cv.rect(4, 55, 32, 1, C(GR[3]))
    for fx in (6, 27):
        cv.rect(fx, 55, 8, 2, C(OR))
        cv.rect(fx, 55, 8, 1, C(OR_L))
    cv.rect(19, 53, 2, 1, C("#7fd67a" if lit else "#4e4558"))
    # pilares de aço
    for px_ in (4, 32):
        cv.rect(px_, 19, 4, 32, C(INK))
        cv.rect(px_ + 1, 20, 2, 30, C(DK[0]))
        cv.rect(px_ + 1, 20, 1, 30, C(DK[1]))
        for k in range(6):
            cv.rect(px_ + 1, 24 + k * 4, 2, 1, C(DK[2]))
    # corpo
    cv.rect(7, 18, 26, 33, C(INK))
    cv.bands(8, 21, 29, [(CREAM[0], 3), (CREAM[1], 15), (CREAM[2], 6)])
    cv.rect(8, 19, 24, 2, C(GR[1]))
    cv.rect(8, 19, 24, 1, C(GR[0]))
    cv.rect(8, 24, 24, 1, C(OR_L))
    cv.rect(8, 25, 24, 1, C(OR))
    # boca da fundição (moldura de aço, aba de proteção)
    cv.rect(9, 28, 18, 19, C(INK))
    cv.rect(10, 29, 16, 17, C(GR[2]))
    cv.rect(10, 29, 16, 1, C(GR[1]))
    cv.rect(10, 29, 1, 17, C(GR[1]))
    cv.rect(10, 44, 16, 2, C(DK[0]))
    cv.rect(10, 44, 16, 1, C(DK[1]))
    # interior
    ix, iy, iw, ih = 12, 31, 12, 12
    cv.rect(ix - 1, iy - 1, iw + 2, ih + 2, C(INK))
    cv.rect(ix, iy, iw, ih, C("#241d2c"))
    if lit:
        phase = f % FRAMES
        rows = [GLOW[4], GLOW[4], GLOW[3], GLOW[3], GLOW[2], GLOW[2], GLOW[2], GLOW[1]]
        for r, col in enumerate(rows):           # brasa sobe do fundo
            yy = iy + ih - 1 - r
            cv.rect(ix, yy, iw, 1, C(GLOW[min(4, max(0, [4, 3, 3, 2, 2, 1, 1, 0][r] if r < 8 else 0))]))
        # o brilho do fundo anda: topo da massa incandescente oscila e pontos claros saltam
        top = iy + 4 + (1 if phase in (1, 3) else 0)
        for yy in range(iy, top):
            cv.rect(ix, yy, iw, 1, C("#241d2c"))
        cv.rect(ix, top, iw, 1, C(GLOW[4]))
        for k, (dx, dy) in enumerate([(1, 8), (4, 9), (7, 8), (10, 9), (2, 6), (8, 6), (5, 7), (10, 5)]):
            on = ((k + phase) % 4) < 2
            cv.rect(ix + dx, iy + dy, 2, 1, C(GLOW[0] if on else GLOW[1]))
        for k, dx in enumerate((1, 5, 9)):       # grelha escura na frente
            cv.rect(ix + dx + 1, iy + ih - 3, 1, 3, C("#3a1d1a"))
        # luz que vaza pela borda da moldura
        cv.rect(10, 45, 16, 1, C(GLOW[2]))
    else:
        for dx, dy in ((2, 10), (6, 11), (9, 10), (4, 11)):
            cv.rect(ix + dx, iy + dy, 2, 1, C("#5a2a24"))
        for d in range(4):                       # reflexo no vidro escuro
            cv.px(ix + 2 + d * 2, iy + 1 + d, C("#3a3549"))
            cv.px(ix + 3 + d * 2, iy + 1 + d, C("#3a3549"))
    # painel lateral: janela de magmatita + LED
    cv.rect(28, 28, 4, 1, C(INK))
    cv.rect(28, 29, 4, 7, C(INK))
    cv.rect(29, 30, 2, 5, C("#4a1f18"))
    if lit:
        cv.rect(29, 31, 2, 3, C(GLOW[2]))
        cv.px(29, 31, C(GLOW[0]))
    else:
        cv.rect(29, 32, 2, 2, C("#7a3a2a"))
        cv.px(29, 32, C("#a8402a"))
    cv.rect(28, 38, 3, 2, C(INK))
    cv.rect(29, 38, 1, 1, C("#7fd67a" if lit else "#3a3549"))
    cv.rect(29, 41, 2, 2, C(OR if lit else OR_D))
    # bandeja de saída (lado direito) + lingote
    cv.rect(33, 43, 7, 7, C(INK))
    cv.rect(34, 44, 5, 5, C(GR[2]))
    cv.rect(34, 44, 5, 1, C(GR[0]))
    cv.rect(34, 48, 5, 1, C(OR))
    cv.rect(35, 45, 3, 2, C("#241d2c"))
    if lit:
        cv.rect(35, 46, 3, 1, C(GLOW[1] if f % 2 == 0 else GLOW[2]))
        cv.rect(35, 45, 3, 1, C(GLOW[2]))
    # funil de entrada (esquerda) com minério
    for i in range(7):
        cv.rect(6 + i, 11 + i, 17 - 2 * i, 1, C(INK))
    cv.rect(6, 10, 17, 1, C(INK))
    for i in range(6):
        cv.rect(8 + i, 11 + i, 13 - 2 * i, 1, C(GR[1] if i < 3 else GR[2]))
    cv.rect(8, 11, 13, 1, C(GR[0]))
    chunk(cv, 8, 7, IRON_O)
    chunk(cv, 16, 7, CU_O)
    chunk(cv, 12, 5, CU_O)
    cv.rect(11, 17, 7, 2, C(INK))
    cv.rect(12, 17, 5, 2, C(GR[2]))
    cv.rect(9, 18, 3, 1, C(OR))
    cv.rect(17, 18, 3, 1, C(OR))
    # chaminé
    cv.rect(24, 8, 8, 11, C(INK))
    cv.rect(25, 9, 6, 10, C(DK[0]))
    cv.rect(25, 9, 1, 10, C(DK[1]))
    cv.rect(23, 6, 10, 3, C(INK))
    cv.rect(24, 7, 8, 1, C(OR_L))
    cv.rect(24, 8, 8, 1, C(OR))
    if lit:
        sp = [[(26, 3), (29, 2)], [(28, 2), (25, 3)], [(27, 2), (30, 3)], [(25, 2), (29, 3)]][f % 4]
        for sx, sy in sp:
            cv.px(sx, sy, C(GLOW[1]))
            cv.px(sx + 1, sy + 1, C(GLOW[2]))
        cv.rect(26, 4, 4, 1, C(GR[1] if f % 2 else GR[2]))
        cv.rect(25 + f % 2, 5, 5, 1, C(GR[2]))
    out = M.Canvas(W, H)
    out.a[:] = cv.a[H0 - H:]
    return out


def strip(frames):
    s = M.Canvas(W * len(frames), H)
    for i, c in enumerate(frames):
        s.paste(c, i * W, 0)
    return s


def copper_ingot():
    """Par do icon_iron_ingot: mesma barra (tronco retangular em 3/4, tampo claro, frente média, lado na sombra),
    na paleta do cobre (laranja-salmão) com uma mancha de verdete no tampo."""
    pal = dict(W="#ffd2ae", b="#f7966a", T="#f7966a", d="#c8583a", c="#f9a77c", l="#e0703f", F="#e0703f",
               r="#f2864f", D="#aa4a2a", E="#7a3319", e="#8a3a20", s="#aa4a2a")
    rows = [
        "................", "................", "................",
        ".....bbbbbbbbb..", "....bTWWTTTTTTd.", "...bTWWTTTTTTdD.", "..bTWWTTTTTTdDD.",
        ".cccccccccccDDD.", ".lFFrFFFFFFFDDD.", ".lFrFFFFFFFFDDE.", ".lrFFFFFrFFFDE..",
        ".ssssssssssse...", "................", "................", "................", "................",
    ]
    cv = M.Canvas(16, 16)
    cv.draw_map(rows, pal, oy=1)
    cv.px(2, 10, C("#ffe6cf"))
    for x, y, c in ((8, 5, "#74dcbd"), (9, 5, "#74dcbd"), (8, 6, "#3fb094"), (9, 6, "#c9fbe9"), (10, 6, "#3fb094"),
                    (10, 5, "#3fb094"), (7, 6, "#74dcbd")):    # verdete no tampo
        if cv.a[y, x, 3]:
            cv.px(x, y, C(c))
    cv.outline(C(INK))
    return cv


def save(cv, path):
    Image.fromarray(cv.a).save(path)


# ---------------------------------------------------------------------------
# v2 · r3d (mesmo pipeline do aquecedor/derretedor: scene + sapata B + render)
# ---------------------------------------------------------------------------
P_DARK, P_METAL, P_BEIGE, P_ORANGE = MR.P_DARK, MR.P_METAL, MR.P_BEIGE, MR.P_ORANGE
P_STEEL, P_SILVER, P_LAVA, P_EMBER = MR.P_STEEL, MR.P_SILVER, MR.P_LAVA, MR.P_EMBER
P_IRON = MR.Pal(["#f3e2cf", "#dcc0a3", "#b99b82", "#7a6552", "#3b3027"])
P_COPPER = MR.Pal(["#ffd2ae", "#f7966a", "#e0703f", "#aa4a2a", "#52210f"])
P_INGOT = [MR.Pal(["#ffe9b0", "#ffd27a", "#ff9a3d", "#e0602a", "#a8402a"], emit=True, emit_tone=t) for t in range(3)]
BX0, BX1, BY, BZ0, BZ1 = -13, 13, 10, 5, 34          # corpo: x ±13, y ±10, z 5..34 (assentado na sapata)
CZ = (BZ0 + BZ1) / 2
MX0, MX1, MZ0, MZ1 = -11.0, 3.0, 8.0, 25.0           # boca (mundo): x, z
ENTRIES = ("A", "B")


def _front_paint(lit, f):
    """Pinta a FRENTE do corpo: faixa laranja, janela da magmatita e o interior da boca (apagado/brasa/acesa)."""
    def paint(L, face):
        out = np.zeros(len(L), int)
        if face == 2:
            x, z = L[:, 0], L[:, 2] + CZ
            out[(z > 27.5) & (z < 29.8)] = 1                                   # faixa laranja
            inb = (x > MX0 + 1) & (x < MX1 - 1) & (z > MZ0 + 1) & (z < MZ1 - 1)
            if lit:
                r = np.floor((z - (MZ0 + 1)) / 2.1).astype(int)                # 0 = fundo (mais quente)
                base = np.array([1, 1, 2, 2, 3, 3, 4])[np.clip(r, 0, 6)]
                tone = np.clip(base + np.where((np.floor(x) + r * 2 + f) % 4 == 0, -1, 0)
                               + np.where((np.floor(x) + r + 2 * f) % 5 == 0, 1, 0), 0, 4)
                out[inb] = (4 + tone)[inb]
                out[inb & (np.floor(x - MX0) % 4 == 3)] = 2                    # grelha escura na frente
            else:
                out[inb] = 2
                out[inb & (z < MZ0 + 3.4) & (np.floor(x) % 5 == 0)] = 9        # brasa morta
            win = (x > 6) & (x < 11) & (z > 21) & (z < 26)                     # janela da magmatita
            out[win] = 2
            out[win & (x > 7) & (x < 10) & (z > 22) & (z < 25)] = 10 if lit else 11
        elif face == 5:                                                        # tampo: respiros à direita
            x, y = L[:, 0], L[:, 1]
            out[(x > 5.5) & (x < 11) & (abs(y) < 2.5) & (np.floor(x) % 2 == 0)] = 2
        return out
    return paint


def smelter_r3d(lit: bool, f: int = 0, entry: str = "A"):
    sc = MR.scene(40, 56, -13)
    MR.base(sc, 16, 13)
    extra = (P_ORANGE, P_DARK, P_METAL, *P_LAVA, P_EMBER[0], P_LAVA[2], P_EMBER[0])
    # índices: 1 laranja, 2 escuro, 3 metal, 4..8 lava (tons 0..4), 9 brasa morta, 10 janela acesa, 11 janela apagada
    extra = (P_ORANGE, P_DARK, P_METAL, *P_LAVA, P_EMBER[1], P_LAVA[2], P_EMBER[0])
    sc.box((BX0, BX1), (-BY, BY), (BZ0, BZ1), P_BEIGE, paint=_front_paint(lit, f), extra=extra)
    # moldura de aço saltada em volta da boca (dá o volume) + aba de proteção embaixo
    fy = -BY - 1.3
    for (x0, x1, z0, z1) in ((MX0 - 1.4, MX1 + 1.4, MZ1, MZ1 + 1.6), (MX0 - 1.4, MX0, MZ0, MZ1),
                             (MX1, MX1 + 1.4, MZ0, MZ1)):
        sc.box((x0, x1), (fy, -BY), (z0, z1), P_METAL)
    sc.box((MX0 - 1.8, MX1 + 1.8), (fy - 0.6, -BY), (MZ0 - 1.8, MZ0), P_STEEL)
    sc.box((MX0 - 1.8, MX1 + 1.8), (fy - 0.6, fy), (MZ0 - 1.8, MZ0 - 1.4), P_ORANGE)
    # painel/LEDs
    MR.front_panel(sc, 6, 11, -BY, 11, 17, 0 if lit else 3, leds=1)
    if lit:
        sc.dot(7, -BY - 1.4, 13, MR.OK, always=True)
    # bandeja de saída à direita com o lingote
    sc.box((13, 18), (-9, -1), (8, 10.2), P_DARK)
    sc.box((13, 18), (-9.4, -9), (10.2, 11.2), P_METAL)
    sc.box((17.6, 18), (-9, -1), (10.2, 11.2), P_METAL)
    sc.box((13, 18), (-9.6, -9.2), (8, 8.8), P_ORANGE)
    if lit:
        sc.box((14.2, 17.2), (-7, -3), (10.2, 11.8), P_INGOT[f % 2])
    # entrada de minério
    if entry == "A":
        # tremonha integrada: boca de carga rente ao tampo, aro saltado baixo, tampa articulada aberta atrás
        ztop = BZ1
        sc.box((-11.5, 0.5), (-6.5, 4.5), (ztop, ztop + 0.8), P_DARK)                  # fundo escuro da boca
        for (xr, yr) in (((-12, 1), (-7.5, -6.5)), ((-12, 1), (4.5, 5.5)), ((-12, -11), (-6.5, 4.5)), ((0.5, 1.5), (-6.5, 4.5))):
            sc.box(xr, yr, (ztop, ztop + 1.8), P_METAL)
        sc.box((-12, 1), (-7.9, -7.5), (ztop, ztop + 0.9), P_ORANGE)                   # lábio laranja na frente
        for (x, y, z, r, pal) in ((-8, -1, 1.0, 2.2, P_IRON), (-2.5, 0.5, 1.4, 2.4, P_COPPER), (-5.5, 2.8, 2.0, 1.8, P_COPPER)):
            sc.rbox((x, y, ztop + z), (r, r * 0.9, r * 0.6), 0.5, pal)                 # minério a ras da boca
        sc.box((-12, 1), (4.5, 6), (ztop, ztop + 3.4), P_METAL)                          # parede de trás (anteparo)
        sc.box((-11, 0), (5.9, 6.1), (ztop + 2.4, ztop + 3.0), P_ORANGE)
    else:
        # B · calha de carga: aba inclinada na frente do tampo (rampa) que leva o minério pra uma fenda
        ztop = BZ1
        sc.box((-12, 1.5), (-8, 5), (ztop, ztop + 1.4), P_METAL)
        sc.obox((-5.2, -3.2, ztop + 2.6), (6.8, 4.2, 0.7), P_METAL, rot_x=0.42)          # rampa
        sc.box((-12.4, -11.4), (-8, 5), (ztop, ztop + 3.6), P_METAL)
        sc.box((1.4, 2.4), (-8, 5), (ztop, ztop + 3.6), P_METAL)
        sc.box((-11, 0.6), (1.5, 5), (ztop + 1.4, ztop + 2.6), P_DARK)                  # fenda
        for (x, y, z, r, pal) in ((-8, -4, 7.2, 1.8, P_IRON), (-3, -2, 6.4, 2.0, P_COPPER)):
            sc.rbox((x, y, ztop + z - 3.0), (r, r * 0.9, r * 0.6), 0.5, pal)
    # chaminé de aço com anel laranja
    sc.cyl(8.5, 3.5, 2.6, 30, 47, P_DARK, paint=lambda t, z, c: np.where((z > 42) & (z < 44) & ~c, 1, 0),
           extra=(P_ORANGE,))
    sc.cyl(8.5, 3.5, 3.3, 45.2, 47, P_METAL)
    if lit:
        for i in range(3):
            z = 48 + (f * 2 + i * 3) % 6
            sc.dot(8.5 + (1 if (f + i) % 2 else -1) * (i % 2), 3.5, z, MR.HEAT[1] if i == 0 else MR.HEAT[2], always=True)
    return MR.render(sc)


def render_all(entry="A"):
    return smelter_r3d(False, 0, entry), [smelter_r3d(True, i, entry) for i in range(FRAMES)]


def save(cv, path):
    Image.fromarray(cv.a).save(path)


def save_cv(cv, path):
    cv.save(path)


def main():
    (PEND / "anim").mkdir(parents=True, exist_ok=True)
    for e in ENTRIES:
        off, lit = render_all(e)
        suf = "" if e == "A" else "_B"
        off.save(PEND / f"machine_smelter{suf}.png")
        MR.strip(lit).save(PEND / "anim" / f"anim_machine_smelter{suf}.png")
        for i in range(FRAMES):
            lit[i].save(PEND / f"_f{i}{suf}.png")
    save(copper_ingot(), PEND / "icon_copper_ingot.png")
    save(smelter_flat(False), PEND / "v1_flat_machine_smelter.png")
    save(smelter_flat(True, 0), PEND / "v1_flat_acesa.png")
    write_html()


def load(path):
    return Image.open(path).convert("RGBA")


def floors():
    cave = load(SPR / "cave_ground" / "ground_cave_plateau.png")
    return {"dead": [load(SPR / f"floor_dead_{i}.png") for i in range(4)],
            "mist": [load(SPR / f"floor_mist_{i}.png") for i in range(4)],
            "green": [load(SPR / f"floor_green_{i}.png") for i in range(4)],
            "cave": [cave.crop((32 * i, 64, 32 * i + 32, 96)) for i in range(4)]}


def scene(name, tiles, pieces, cols=9, rows=3):
    im = Image.new("RGBA", (cols * 32, rows * 32))
    for r in range(rows):
        for c in range(cols):
            im.alpha_composite(tiles[(c * 3 + r * 5) % 4], (c * 32, r * 32))
    for spr, tx, ty in pieces:
        im.alpha_composite(spr, (tx * 32 + 16 - spr.width // 2, ty * 32 + 32 - spr.height))
    im.save(REP / f"cena_{name}.png")


def write_html():
    heater, melter = load(SPR / "machine_heater.png"), load(SPR / "machine_melter.png")
    A_off, B_off = load(PEND / "machine_smelter.png"), load(PEND / "machine_smelter_B.png")
    A_lit, B_lit = load(PEND / "_f0.png"), load(PEND / "_f0_B.png")
    fl = floors()
    for k in ("dead", "mist", "green", "cave"):
        scene(f"{k}_apagada", fl[k], [(heater, 2, 2), (melter, 4, 2), (A_off, 6, 2)])
        scene(f"{k}_acesa", fl[k], [(heater, 2, 2), (melter, 4, 2), (A_lit, 6, 2)])
    for k in ("mist", "cave"):
        scene(f"{k}_entradaB", fl[k], [(heater, 2, 2), (melter, 4, 2), (B_lit, 6, 2)])
    cmp_ = Image.new("RGBA", (46 * 7, 56))
    for i, im in enumerate([melter, heater, A_off, A_lit, B_off, B_lit]):
        cmp_.alpha_composite(im, (i * 46, 0))
    cmp_.save(REP / "comparativo.png")
    ing = Image.new("RGBA", (56, 16))
    for i, n in enumerate(("icon_copper", "icon_iron_ingot")):
        ing.alpha_composite(load(SPR / f"{n}.png"), (i * 20, 0))
    ing.alpha_composite(load(PEND / "icon_copper_ingot.png"), (40, 0))
    ing.save(REP / "cadeia_icones.png")

    def box(src, w, h, z, cap=""):
        return (f'<figure><div class="chk"><img src="{src}" width="{w * z}" height="{h * z}" alt=""></div>'
                f'<figcaption>{cap}</figcaption></figure>')

    def animdiv(src, z, cls):
        return (f'<div class="chk"><div class="{cls}" style="width:{W * z}px;height:{H * z}px;background-image:url({src});'
                f'background-size:{W * FRAMES * z}px {H * z}px"></div></div>')

    sc = ""
    for k, t in (("dead", "superfície · morto"), ("mist", "superfície · névoa"), ("green", "superfície · verde"),
                 ("cave", "chão da caverna (plateau)")):
        sc += (f'<h3>{t}</h3><div class="row">'
               f'<figure><img src="cena_{k}_apagada.png" width="{288 * 3}" height="{96 * 3}" alt=""><figcaption>apagada · aquecedor, derretedor, fundição (entrada A) · 3×</figcaption></figure>'
               f'<figure><img src="cena_{k}_acesa.png" width="{288 * 3}" height="{96 * 3}" alt=""><figcaption>acesa (quadro 0)</figcaption></figure></div>')
    css_anim = "".join(
        f"@keyframes a{z}{{to{{background-position:-{W * FRAMES * z}px 0}}}}.an{z}{{image-rendering:pixelated;animation:a{z} {FRAMES / FPS}s steps({FRAMES}) infinite}}"
        for z in (1, 3, 6, 8))
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Hesper · v0.6 Fundo M3: Fundição</title>
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:16px}}
.wrap{{max-width:1320px;margin:0 auto;padding-block:32px 80px}}h1{{font-size:38px;margin:8px 0}}
h2{{margin:44px 0 8px;border-top:1px solid var(--line);padding-top:24px}}h3{{margin:20px 0 6px;color:var(--gold)}}
.eyebrow{{font:12px monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}}
.note{{border-left:3px solid var(--cyan);background:var(--panel);padding:10px 16px;margin:16px 0}}
.muted{{color:var(--muted)}}code{{background:#2a201b;padding:1px 5px}}
img{{image-rendering:pixelated;display:block}}
.chk{{background-color:#342c28;background-image:linear-gradient(45deg,#423835 25%,transparent 25%,transparent 75%,#423835 75%),linear-gradient(45deg,#423835 25%,transparent 25%,transparent 75%,#423835 75%);background-size:16px 16px;background-position:0 0,8px 8px;padding:8px;display:inline-block}}
.row{{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end}}figure{{margin:0}}figcaption{{font:12px monospace;color:var(--muted);margin-top:4px;max-width:44ch}}
table{{border-collapse:collapse}}td,th{{border:1px solid var(--line);padding:6px 10px;text-align:left}}th{{font:12px monospace;color:var(--muted)}}
{css_anim}
</style></head><body><div class="wrap">
<div class="eyebrow">v0.6 · Fundo M3 · PRA APROVAR</div>
<h1>Fundição (<code>smelter</code>) · v2 em 3D (r3d)</h1>
<div class="note"><b>v2.0 · o que mudou.</b> A v1 saiu chapada, de frente. Refeita pelo pipeline r3d (<code>tools/sprites/r3d.py</code>, o mesmo do
aquecedor, do derretedor e do O₂): volume em 3/4, tampo visível, luz em faixas, <b>sapata B</b> padrão (4 sapatas laranja, friso prata, plaqueta com LED), 40×56 com o mesmo
pé. Mesmas ideias: boca de aço, chaminé, janela da magmatita, LED, bandeja de saída. <b>O funil espetado com pepitas saiu</b>: a entrada de minério agora é
integrada ao corpo, e deixei <b>duas opções (A e B) pro dono escolher</b>. O ícone do lingote de cobre continua o mesmo (aprovado).</div>

<h2>1 · A máquina (entrada A, a minha preferida)</h2>
<div class="row">
<figure>{box("pendentes/machine_smelter.png", W, H, 8, "apagada · machine_smelter.png · 40×56 · 8×")}</figure>
<figure>{animdiv("pendentes/anim/anim_machine_smelter.png", 8, "an8")}<figcaption>acesa animada · anim_machine_smelter.png · 8× · {FPS} fps</figcaption></figure></div>
<p><b>Entrada A · tremonha integrada.</b> Boca de carga rente ao tampo (aro de aço baixo com lábio laranja e fundo escuro), com minério de ferro e de cobre
a ras da boca e a tampa articulada levantada atrás. Lê "entra minério aqui" sem nenhum acessório colado por cima.<br>
Apagada: boca escura com brasa morta, janela de magmatita apagada, LED apagado. Acesa: massa incandescente pulsando atrás de uma grelha, magmatita acesa na janela,
lingote quente na bandeja, LED verde, calor saindo da chaminé.</p>

<h2>2 · Duas opções de entrada pro dono escolher</h2>
<div class="row">
{box("pendentes/machine_smelter.png", W, H, 6, "A · tremonha integrada (boca de carga com anteparo)")}
{box("pendentes/machine_smelter_B.png", W, H, 6, "B · calha de carga (rampa inclinada que leva o minério pra fenda)")}
{box("pendentes/_f0.png", W, H, 6, "A acesa")}
{box("pendentes/_f0_B.png", W, H, 6, "B acesa")}
</div>
<p class="muted">A tira acesa da B é <code>pendentes/anim/anim_machine_smelter_B.png</code>. Só a entrada muda; o resto é igual. Escolhida a opção, descarto a outra.</p>

<h3>Ao lado do derretedor e do aquecedor (1×, escala real)</h3>
<div class="row"><figure><div class="chk"><img src="comparativo.png" width="322" height="56" alt=""></div><figcaption>derretedor, aquecedor, fundição A apagada, A acesa, B apagada, B acesa · 1×</figcaption></figure>
<figure><div class="chk"><img src="comparativo.png" width="{322 * 3}" height="168" alt=""></div><figcaption>o mesmo a 3×</figcaption></figure></div>

<h2>3 · Em cena (superfície e caverna)</h2>
<p>Da esquerda pra direita: aquecedor, derretedor, fundição (entrada A). Chão primeiro, máquina ancorada no centro-baixo do tile.</p>
{sc}
<h3>Entrada B em cena</h3><div class="row">
<figure><img src="cena_mist_entradaB.png" width="{288 * 3}" height="{96 * 3}" alt=""><figcaption>névoa</figcaption></figure>
<figure><img src="cena_cave_entradaB.png" width="{288 * 3}" height="{96 * 3}" alt=""><figcaption>caverna</figcaption></figure></div>

<h2>4 · Ícone do lingote de cobre (inalterado)</h2>
<div class="row">
{box("pendentes/icon_copper_ingot.png", 16, 16, 12, "icon_copper_ingot · 16×16")}
{box("../../../assets/sprites/icon_iron_ingot.png", 16, 16, 12, "icon_iron_ingot (já no jogo)")}
{box("../../../assets/sprites/icon_copper.png", 16, 16, 12, "icon_copper (minério)")}
{box("cadeia_icones.png", 56, 16, 8, "minério · lingote de ferro · lingote de cobre · 8×")}</div>

<h2>Pro Dev integrar</h2>
<table><tr><th>arquivo (em <code>assets/sprites/</code> depois do ok)</th><th>tamanho</th><th>uso</th></tr>
<tr><td><code>machine_smelter.png</code></td><td>40×56</td><td>fundição <b>parada</b> (sem energia, sem insumo, submersa), fantasma de colocar, ícone</td></tr>
<tr><td><code>anim/anim_machine_smelter.png</code></td><td>160×56 ({FRAMES} quadros de 40 px, horizontal)</td><td>fundição <b>acesa</b> (fundindo), {FPS} fps como as outras máquinas (fase por tile, mais devagar no déficit). Quadro 0 = acesa estática</td></tr>
<tr><td><code>icon_copper_ingot.png</code></td><td>16×16</td><td>item <code>copper_ingot</code></td></tr></table>
<ul>
<li><b>Âncora:</b> igual ao aquecedor e ao derretedor nv.1: centrada em x no tile, base da imagem no pé do tile, 40×56. Mesma sapata B; sombra de chão não vai desenhada (como nas outras r3d).</li>
<li><b>Convenção:</b> <code>machine_{{key}}.png</code> parada + <code>anim/anim_machine_{{key}}.png</code> acesa (sem a tira, usa o parado). Key <code>smelter</code>.</li>
<li>Os nomes acima são da <b>opção A</b>. Se o dono escolher a B, renomeio <code>machine_smelter_B.png</code> e <code>anim_machine_smelter_B.png</code> pros nomes finais. Arquivos <code>_f*</code>, <code>_B</code> e <code>v1_flat_*</code> são prévia/descartados e não entram.</li>
<li>Alpha só 0/255. Gerador: <code>python3 tools/sprites/v06_fundo_m3_fundicao.py</code> (determinístico).</li>
</ul>

<h2>v1 (descartada) · só pra comparar</h2>
<div class="row">
{box("pendentes/v1_flat_machine_smelter.png", 40, 56, 3, "v1 chapada, apagada")}
{box("pendentes/v1_flat_acesa.png", 40, 56, 3, "v1 chapada, acesa")}
{box("pendentes/machine_smelter.png", 40, 56, 3, "v2 r3d, apagada")}
{box("pendentes/_f0.png", 40, 56, 3, "v2 r3d, acesa")}</div>
</div></body></html>"""
    html = html.replace('class="an8"', 'class="an8"')
    (REP / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
