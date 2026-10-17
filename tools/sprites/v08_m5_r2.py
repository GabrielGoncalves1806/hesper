#!/usr/bin/env python3
"""v0.8 M5 · rodada 2 · CANDIDATAS (nada daqui vai pro assets/ sem o ok do dono).

    python3 tools/sprites/v08_m5_r2.py          # sprites (pendentes/ e candidatas/) + mock do Tab A + index.html

Pedidos do dono (2026-10-17):
  1. Tab: opção A reorganizada aprovada (o mock daqui usa o mesmo layout).
  2. icon_hydrogel vira "bola de slime" (2 candidatas), no verde-azulado da Folha-gota.
  3. Equipáveis do traje com volume, no espírito das máquinas r3d (mesma cena/luz do r3d.py, contorno #1b1630):
     icon_o2_tank, icon_o2_tank_t2, icon_backpack, icon_backpack_t2, icon_scanner, icon_boots.
Só LÊ assets/sprites/ e escreve em reports/design/v08_m5_itens_r2/. Determinístico.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v08_m5_itens as I  # noqa: E402
from r3d import SA, Pal, Scene  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v08_m5_itens_r2"
PEND = REP / "pendentes"
CAND = REP / "candidatas"
Px = I.Px

# ---- paletas r3d (5 tons: brilho, claro, base, sombra, fundo) --------------------------------------------------------
P_WHITE = Pal(["#f4f6f8", "#e8ebef", "#cfd4db", "#a3aab6", "#767d8b"])
P_GREYP = Pal(["#c8cdd4", "#b9bfc8", "#abb2bb", "#8c949e", "#6b717a"])
P_DARK = Pal(["#5a5f6b", "#4a4f5a", "#3b3f46", "#2a2d33", "#1f2126"])
P_ORANGE = Pal(["#f4a06a", "#e88550", "#e2733a", "#a9482a", "#6e2a1c"])
P_CYAN = Pal(["#8fe8f6", "#6cdcee", "#59d0e6", "#2b9fb8", "#1f5a66"])
P_GOLD = Pal(["#ffe08f", "#f2c46d", "#d9a64e", "#b8893a", "#6e4a1e"])
P_FIBER = Pal(["#8fd65a", "#7fc94f", "#4f9a3f", "#2f6b3a", "#163a26"])
P_FIBER_D = Pal(["#5fae45", "#4f9a3f", "#3f8236", "#2f6b3a", "#163a26"])   # o rolo, 1 tom abaixo (separa da aba)
P_GEL = Pal(["#8ff0dc", "#5fdcc4", "#3fc6b4", "#1f8a86", "#155a5a"])
P_RESIN = Pal(["#a6ecff", "#58a0e0", "#2f68b0", "#22407a", "#101c40"])
P_SCREEN = Pal(["#0d1a2a"] * 5, emit=True, emit_tone=0)
P_RED = Pal(["#ff5a4a"] * 5, emit=True, emit_tone=0)


def scene(front_y, w=16, h=16):
    """Cena 16×16 com a borda da frente (Y=front_y, Z=0) na penúltima linha (igual ao icon_chest r3d)."""
    return Scene(w, h, ground=h - 2 - (-front_y) * SA)


def zband(bands, default=0):
    """paint de cyl: índice pela altura z. bands = [(z0, z1, idx)]."""
    def f(theta, z, is_cap):
        out = np.full(len(np.atleast_1d(z)), default)
        z = np.atleast_1d(z)
        for z0, z1, k in bands:
            out[(z >= z0) & (z < z1) & ~np.atleast_1d(is_cap)] = k
        return out
    return f


def img(cv):
    return Image.fromarray(cv.a)


# =====================================================================================================================
# 2 · gel hídrico = bola de slime
# =====================================================================================================================
SL = dict(hi="#f2fffb", l2="#b6f5d2", l="#86e8bc", m="#52cfa2", spot="#2f9e86", d="#1f7f86", dd="#175f6a",
          deep="#0f3f4a", leaf_l="#74d488", leaf_d="#1f6a52")


def _slime(cx, cy, rx, ry, drip_y, drips, spots, hl, leaf=False, flat=False):
    g = Px()

    def inside(x, y):
        if flat and y > cy + ry * 0.62:
            return False
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0

    def sh(x, y):
        X, Y = x + 0.5, y + 0.5
        u, v = (X - cx) / rx, (Y - cy) / ry
        edge = drips.get(x, drip_y)
        if Y > edge:                                         # base mais escura (o "fundo" da bola, por baixo da gosma)
            return SL["deep"] if (u > 0.45 or v > 0.75) else SL["dd"] if u > -0.1 else SL["d"]
        k = u * 0.65 + v * 0.75                               # gosma de cima: luz de cima-esquerda
        return SL["l2"] if k < -0.62 else SL["l"] if k < -0.05 else SL["m"] if k < 0.5 else SL["spot"]
    g.shape(inside, sh)
    for x, ys in drips.items():                               # a borda da gosma: 1 px mais escuro na ponta do pingo
        for y in range(16):
            if g.get(x, y) and y + 0.5 <= ys < y + 1.5 and y > 0:
                g.px(x, y, SL["spot"] if x > cx + 1 else SL["m"])
    for (x, y) in spots:                                      # manchas / bolhas mais escuras
        g.px(x, y, SL["spot"])
    for (x, y, c) in hl:
        g.px(x, y, SL[c])
    if leaf:
        g.px(9, 1, SL["leaf_l"]); g.px(10, 1, SL["leaf_l"]); g.px(10, 0, SL["leaf_l"]); g.px(11, 0, SL["leaf_d"])
        g.px(9, 2, SL["leaf_d"])
    return g.outline()


def hydrogel_slime_A():
    """Bola de slime: esfera verde-azulada, a gosma clara por cima escorrendo em pingos sobre a base escura, manchas
    mais escuras e o brilho em cima-esquerda. Redonda (não é cápsula nem gota de resina)."""
    drips = {1: 7.5, 2: 8.0, 3: 10.5, 4: 11.5, 5: 9.0, 6: 8.0, 7: 9.0, 8: 12.0, 9: 11.0, 10: 8.5, 11: 8.0, 12: 10.5,
             13: 9.0, 14: 7.5}
    spots = [(10, 3), (11, 3), (10, 4), (5, 7), (6, 7), (11, 6)]
    hl = [(4, 3, "hi"), (5, 3, "hi"), (4, 4, "hi"), (3, 5, "l2"), (7, 5, "hi")]
    return _slime(7.5, 7.8, 6.6, 6.6, 9.5, drips, spots, hl)


def hydrogel_slime_B():
    """Slime 'mole': a mesma bola meio assentada (base achatada, mais larga que alta), pingos mais compridos e a
    folhinha da Folha-gota grudada no alto."""
    drips = {1: 9.0, 2: 10.0, 3: 12.0, 4: 10.5, 5: 9.0, 6: 11.5, 7: 13.0, 8: 10.0, 9: 9.0, 10: 10.5, 11: 12.5,
             12: 10.0, 13: 9.0, 14: 9.5}
    spots = [(10, 4), (11, 4), (10, 5), (5, 8), (6, 8), (12, 7)]
    hl = [(4, 4, "hi"), (5, 4, "hi"), (4, 5, "hi"), (3, 6, "l2"), (7, 6, "hi")]
    return _slime(7.5, 8.6, 7.0, 6.2, 10.5, drips, spots, hl, leaf=True, flat=True)


# =====================================================================================================================
# 3 · equipáveis com volume (r3d)
# =====================================================================================================================
def o2_tank(t2=False):
    """Dois cilindros em pé (o da direita um passo à frente, pra o contorno separar os dois). nv.1: brancos, faixa
    ciano, válvula escura e manopla laranja; nv.2: tampa, anéis e válvula dourados, faixa no verde-azulado do gel,
    cinta de fibra. Cinta na frente com o manômetro."""
    sc = scene(-3.4)
    band = P_GEL if t2 else P_CYAN
    ring = P_GOLD if t2 else P_WHITE
    for X, Y in ((-3.3, 1.6), (3.3, -0.6)):
        sc.cyl(X, Y, 2.8, 0.0, 9.6, P_WHITE, paint=zband([(5.0, 7.2, 1), (0.0, 0.9, 2), (8.6, 9.7, 2)]),
               extra=(band, ring))
        sc.cyl(X, Y, 2.0, 9.6, 10.8, ring)                                               # ombro
        sc.cyl(X, Y, 0.9, 10.8, 12.0, P_GOLD if t2 else P_DARK)                          # válvula
        sc.box((X - 1.7, X + 1.7), (Y - 0.6, Y + 0.6), (12.0, 12.9), P_GOLD if t2 else P_ORANGE)   # manopla
    sc.box((-6.4, 6.4), (-3.6, -2.8), (2.2, 3.8), P_FIBER if t2 else P_DARK)             # cinta
    sc.rbox((0, -3.6, 3.0), (1.5, 0.6, 1.5), 0.5, P_DARK)                                # manômetro
    sc.dot(0.0, -4.3, 3.3, "#fff3c4" if t2 else "#c8f6ff")
    return img(sc.render())


def backpack(t2=False):
    """Mochila em domo de 3/4, alta e pouco funda (a frente é o que lê): corpo branco arredondado, aba na frente de
    cima com a faixa (nv.1 laranja, nv.2 fibra), fivela, bolso da frente cinza com o zíper, alça de mão em cima.
    nv.2: mais larga, rolo de fibra amarrado em cima com tiras douradas, fivela e zíper dourados, bolsos de fibra."""
    sc = scene(-2.6)
    w = 5.9 if t2 else 5.2
    sc.rbox((0, 0, 5.0), (w, 2.2, 5.0), 2.0, P_WHITE)                                    # corpo
    sc.rbox((0, -1.2, 7.9), (w - 0.3, 1.3, 1.5 if not t2 else 1.1), 1.0, P_FIBER if t2 else P_ORANGE)   # aba
    sc.rbox((0, -2.1, 3.0), (w - 1.5, 0.7, 2.2), 0.7, P_GREYP)                           # bolso da frente
    sc.box((-(w - 2.2), w - 2.2), (-2.95, -2.75), (4.3, 4.9), P_GOLD if t2 else P_ORANGE)  # zíper
    sc.rbox((0, -2.6, 7.0), (1.0, 0.4, 0.8), 0.3, P_GOLD if t2 else P_DARK)              # fivela
    if t2:
        for sx in (-1, 1):
            sc.rbox((sx * (w + 0.3), -0.2, 3.8), (0.9, 1.6, 2.4), 0.7, P_FIBER)          # bolsos laterais
        sc.hcyl(-w + 1.2, w - 1.2, 1.2, 10.6, 1.2, P_FIBER_D)                            # rolo de fibra
        for X in (-3.0, 3.0):
            sc.box((X - 0.5, X + 0.5), (-1.2, 2.2), (9.4, 12.6), P_GOLD)                  # tiras douradas
    else:
        sc.box((-1.8, 1.8), (-0.4, 0.4), (10.0, 11.4), P_DARK)                            # alça de mão
    cv = sc.render()
    return img(cv)


def scanner():
    """Scanner de navegação: aparelho de mão escuro, inclinado pra mostrar a tela de radar (anéis, ponto do player e
    um alvo), faixa laranja embaixo e a antena com a ponta vermelha."""
    sc = scene(-2.8)
    sc.rbox((0, 0, 1.4), (5.6, 2.6, 1.4), 0.8, P_ORANGE)                               # base laranja
    sc.rbox((0, 0.6, 6.2), (5.6, 1.8, 4.6), 0.9, P_DARK)                               # corpo em pé
    sc.box((-4.2, 4.2), (-1.35, -1.2), (3.6, 9.8), P_SCREEN)                           # tela
    sc.cyl(4.0, 1.4, 0.45, 10.6, 13.4, P_GREYP)                                        # antena
    sc.sphere((4.0, 1.4, 13.9), 0.7, P_RED)                                             # ponta vermelha
    cv = sc.render()
    for (x, y) in ((6, 5), (7, 5), (8, 5), (9, 5), (5, 6), (10, 6), (5, 7), (10, 7), (5, 8), (10, 8),
                   (6, 9), (7, 9), (8, 9), (9, 9)):
        if cv.a[y, x, 3] and tuple(cv.a[y, x, :3]) == (13, 26, 42):
            cv.px(x, y, "#1f5a66")
    cv.px(7, 7, "#59d0e6"); cv.px(8, 6, "#7fd67a"); cv.px(6, 8, "#f2c46d")
    return img(cv)


def boots():
    """Par de botas de tração de perfil em 3/4, uma ao lado da outra (a de trás meio passo à direita e mais cinza, pra
    as duas silhuetas lerem): cano branco com punho de fibra verde e faixa laranja, pé arredondado, biqueira dourada e
    sola grossa de resina azul."""
    sc = scene(-2.4)
    for (Y, X0, body) in ((2.0, 0.2, P_GREYP), (-1.0, -5.0, P_WHITE)):                   # de trás pra frente
        sc.rbox((X0, Y, 5.6), (1.6, 1.3, 4.2), 0.8, body,
                paint=lambda L, N: np.where((L[:, 2] > -0.8) & (L[:, 2] < 0.4), 1, np.where(L[:, 2] > 2.8, 2, 0)),
                extra=(P_ORANGE, P_FIBER))                                                # cano: faixa + punho
        sc.rbox((X0 + 2.0, Y, 1.7), (3.0, 1.3, 1.1), 0.8, body)                          # pé
        sc.rbox((X0 + 4.6, Y, 1.6), (0.8, 1.25, 1.0), 0.5, P_GOLD)                        # biqueira
        sc.box((X0 - 1.6, X0 + 5.4), (Y - 1.4, Y + 1.4), (0.0, 0.7), P_RESIN)             # sola
    return img(sc.render())


EQUIP = {
    "icon_o2_tank": (lambda: o2_tank(False), "icon_o2_tank"),
    "icon_o2_tank_t2": (lambda: o2_tank(True), "icon_o2_tank_t2"),
    "icon_backpack": (lambda: backpack(False), "icon_backpack"),
    "icon_backpack_t2": (lambda: backpack(True), "icon_backpack_t2"),
    "icon_scanner": (scanner, "icon_scanner"),
    "icon_boots": (boots, "icon_boots"),
}
SLIME = {"A": hydrogel_slime_A, "B": hydrogel_slime_B}


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    CAND.mkdir(parents=True, exist_ok=True)
    out = {}
    for k, fn in SLIME.items():
        im = fn().image()
        im.save(CAND / f"icon_hydrogel_{k}.png")
        if k == "A":
            out["icon_hydrogel"] = im
    for name, (fn, _) in EQUIP.items():
        out[name] = fn()
    for name, im in out.items():
        im.save(PEND / f"{name}.png")
    return out


def check():
    ok = True
    want = {"icon_hydrogel", *EQUIP}
    got = {p.stem for p in PEND.glob("*.png")}
    if got != want:
        print("arquivos fora do contrato:", got ^ want)
        ok = False
    for n in want:
        im = Image.open(PEND / f"{n}.png")
        al = set(np.unique(np.array(im.convert("RGBA"))[:, :, 3]).tolist())
        if im.size != (16, 16) or not al <= {0, 255}:
            print("problema:", n, im.size, al)
            ok = False
    print("contrato ok" if ok else "contrato COM PROBLEMA")
    return ok


# =====================================================================================================================
# report
# =====================================================================================================================
def _icon_r2(name):
    for d in (PEND, I.PEND, I.CAND, SPR):
        p = d / f"{name}.png"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(name)


def _icon_r1(name):
    for d in (I.PEND, I.CAND, SPR):
        p = d / f"{name}.png"
        if p.exists():
            return Image.open(p).convert("RGBA")
    raise FileNotFoundError(name)


EQ_NAMES = ["icon_o2_tank", "icon_o2_tank_t2", "icon_backpack", "icon_backpack_t2", "icon_scanner", "icon_boots"]


def previews():
    import v08_m5_itens_report as RP
    import v08_plantas_report as PR
    bg = PR.scene_base("mist")
    RP.icon = _icon_r1
    RP.tab_A(bg, REP / "tab_A_2d.png")
    RP.slot_sheet(EQ_NAMES + ["icon_hydrogel"]).save(REP / "slots_2d.png")
    RP.icon = _icon_r2
    RP.tab_A(bg, REP / "tab_A_3d.png")
    RP.slot_sheet(EQ_NAMES + ["icon_hydrogel"]).save(REP / "slots_3d.png")
    eq_nv1 = {"o2_tank": "o2_tank", "scanner": "scanner", "backpack": "backpack", "boots": "boots"}
    # o traje só com os nv.1 (pra ver a família): cartão em coluna recortado das duas versões
    for tag, fn in (("2d", _icon_r1), ("3d", _icon_r2)):
        RP.icon = fn
        m = PR.UIMock(bg)
        m.window(150, 40, 220, 150)
        RP.suit_card_col(m, 158, 56, 96, 126, eq_nv1)
        RP.suit_card_col(m, 266, 56, 96, 126, RP.EQ_T2)
        m.text(206, 44, "nv.1", PR.B_MUTED, "label", "center")
        m.text(314, 44, "nv.2", PR.GOLD_UI, "label", "center")
        m.finish(REP / f"traje_{tag}.png")
    RP.icon = _icon_r1


CSS = """
:root{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:0 16px}
.wrap{max-width:1020px;margin:0 auto;padding:40px 0 80px}
.eyebrow{font:12px ui-monospace,monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
h1{font:600 38px/1.1 ui-monospace,monospace;margin:10px 0 14px}h2{margin:44px 0 6px;color:var(--gold)}h3{margin:22px 0 6px}
p,li{color:var(--muted)}p b,li b{color:var(--fg)}
.note{background:var(--panel);border-left:4px solid var(--cyan);padding:12px 16px;margin:16px 0;border-radius:4px}
.rec{border-left-color:var(--ok)}
img.full{display:block;width:960px;max-width:100%;height:auto;image-rendering:pixelated;border:1px solid var(--line);border-radius:4px;margin:6px 0}
img.px{image-rendering:pixelated}
.chk{display:inline-flex;gap:14px;align-items:flex-end;padding:10px;background:repeating-conic-gradient(#2a211c 0 25%,#221a16 0 50%) 0 0/16px 16px;border-radius:4px}
.row{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;margin:8px 0}
figure{margin:0;background:var(--panel);border:1px solid var(--line);padding:8px;border-radius:4px}
figcaption{font:12px ui-monospace,monospace;color:var(--muted);margin-top:6px;max-width:330px}
.arrow{font:22px ui-monospace,monospace;color:var(--muted);align-self:center}
.pick{outline:2px solid var(--ok);outline-offset:2px}
code{background:var(--panel);padding:1px 5px;border-radius:3px;color:var(--gold)}
"""


def _url(p):
    p = Path(p)
    if str(p).startswith(str(REP)):
        return p.relative_to(REP).as_posix()
    if str(p).startswith(str(I.REP)):
        return "../v08_m5_itens/" + p.relative_to(I.REP).as_posix()
    return "../../../assets/sprites/" + p.name


def fig(path, cap, k=4, pick=False):
    w, h = Image.open(path).size
    u = _url(path)
    return (f'<figure{" class=pick" if pick else ""}><div class="chk"><img class="px" src="{u}" width="{w}" height="{h}">'
            f'<img class="px" src="{u}" width="{w * k}" height="{h * k}"></div><figcaption>{cap}</figcaption></figure>')


EQ_INFO = {
    "icon_o2_tank": ("Tanque de O₂ (nv.1)", SPR / "icon_o2_tank.png", "melhora: os dois cilindros ganham corpo e o da direita vem um passo à frente; a manopla laranja e a faixa ciano continuam."),
    "icon_o2_tank_t2": ("Tanque de O₂ nv.2", I.PEND / "icon_o2_tank_t2.png", "melhora: tampas e válvulas douradas ficam no topo iluminado, a faixa de gel e a cinta de fibra na frente."),
    "icon_backpack": ("Mochila (nv.1)", SPR / "icon_backpack.png", "fica parecida: lê como bolsa em domo com a aba laranja; perde o LED ciano e as alças de ombro do 2D."),
    "icon_backpack_t2": ("Mochila T2", I.PEND / "icon_backpack_t2.png", "melhora: o rolo de fibra deitado em cima e as tiras douradas ficam com cara de objeto."),
    "icon_scanner": ("Scanner", SPR / "icon_scanner.png", "melhora: aparelho em pé com a tela maior, base laranja e a antena com a ponta vermelha."),
    "icon_boots": ("Botas de tração", I.PEND / "icon_boots.png", "fica PIOR: em 16 px, as duas botas em 3/4 viram um bloco baixo; o 2D de perfil lê 'bota' mais rápido."),
}


def write_html(ok):
    o = []
    a = o.append
    a(f'<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>v0.8 M5 · Materiais e itens · rodada 2</title><style>{CSS}</style></head><body><div class="wrap">')
    a('<div class="eyebrow">Hesper · Designer · v0.8 M5 · rodada 2 · candidatas</div>')
    a('<h1>Materiais e itens · rodada 2</h1>')
    a('<div class="note"><b>v1.1 · o que mudou:</b> (1) o Tab segue a <b>opção A reorganizada</b>, aprovada pelo dono; os mocks daqui usam o mesmo layout. '
      '(2) <b>Gel hídrico virou bola de slime</b> (2 candidatas). (3) Os <b>equipáveis do traje com volume</b>, feitos na mesma cena e com a mesma luz das máquinas r3d '
      '(<code>r3d.py</code>: luz de cima e da esquerda, faces em tons diferentes, contorno <code>#1b1630</code>, linha escura entre peças). Entram aqui o tanque, a mochila e o scanner '
      'de hoje, mais os novos tanque nv.2, Mochila T2 e botas. Nada foi pro jogo. Rodada 1: <a href="../v08_m5_itens/index.html" style="color:#59d0e6">v08_m5_itens</a>. '
      f'Tamanhos: <b>{"todos 16×16, alpha 0/255, sem extras" if ok else "COM PROBLEMA"}</b>.</div>')

    a('<h2>1 · Gel hídrico: bola de slime</h2>')
    a('<p><b>Do estilo da referência do dono eu aproveitei</b> a esfera translúcida, o brilho em cima e à esquerda, as manchas mais escuras e a gosma clara escorrendo em pingos '
      'por cima de uma base escura. O desenho é próprio, em 16×16 e no verde-azulado da Folha-gota: gosma <code>#86e8bc</code>/<code>#52cfa2</code> e base <code>#1f7f86</code>/<code>#0f3f4a</code>. '
      'Do lado ficam a planta de origem e os dois ícones com que o gel não pode confundir.</p><div class="row">')
    a(fig(SPR / "icon_plant_1.png", "Folha-gota (aprovada)"))
    a('<span class="arrow">→</span>')
    a(fig(CAND / "icon_hydrogel_A.png", "A · bola redonda, pingos de vários tamanhos, base escura aparecendo embaixo", pick=True))
    a(fig(CAND / "icon_hydrogel_B.png", "B · slime meio assentado (base achatada, mais largo) com a folhinha da Folha-gota no alto"))
    a(fig(I.CAND / "icon_hydrogel_A.png", "rodada 1 (gota), pra comparar"))
    a(fig(SPR / "icon_water_capsule.png", "vizinho: cápsula de água (cilindro com tampa)"))
    a(fig(I.PEND / "icon_frost_resin.png", "vizinho: resina (azul, pedra com espiral)"))
    a('</div><div class="note rec"><b>Recomendo A.</b> A bola redonda é a leitura mais direta de "slime" e não se parece com nada do inventário. '
      'O B tem a folhinha (amarra melhor com a planta), mas achatado vira "gosma no chão". A cor é o verde-azulado do gel, longe do azul da resina e do branco com azul da cápsula.</div>')

    a('<h2>2 · Equipáveis com volume (r3d)</h2>')
    a('<p>Cada um lado a lado: o atual ou o da rodada 1 (2D) → o 3D. Ampliado ×4, com o 1× do lado. Embaixo de cada um, o que ganhou ou perdeu.</p>')
    for n in EQ_NAMES:
        title, old, note = EQ_INFO[n]
        a(f'<h3>{title}</h3><div class="row">')
        a(fig(old, "2D (" + ("hoje" if str(old).startswith(str(SPR)) else "rodada 1") + ")"))
        a('<span class="arrow">→</span>')
        a(fig(PEND / f"{n}.png", "3D · " + note, pick=not n.endswith("boots")))
        a('</div>')
    a('<h3>Na escala do jogo (slot 20 px, Grande ×2): primeiro em 2D, depois em 3D</h3>')
    a('<p>Ordem: tanque, tanque nv.2, mochila, Mochila T2, scanner, botas e gel.</p>')
    a('<img class="px" src="slots_2d.png" style="display:block;margin:6px 0"><img class="px" src="slots_3d.png" style="display:block;margin:6px 0">')
    a('<h3>A família nv.1 / nv.2 no cartão TRAJE (layout A)</h3>')
    a('<p>À esquerda o traje só com nv.1 e as botas; à direita com os nv.2. Em cima a versão 2D, embaixo a 3D.</p>')
    a('<img class="full" src="traje_2d.png" width="960" height="540"><img class="full" src="traje_3d.png" width="960" height="540">')
    a('<h3>No Tab A aprovado</h3>')
    a('<img class="full" src="tab_A_2d.png" width="960" height="540"><img class="full" src="tab_A_3d.png" width="960" height="540">')
    a('<p style="font-size:13px">Em cima, os ícones 2D (de hoje e da rodada 1). Embaixo, os 3D desta rodada, com o gel de slime na hotbar.</p>')
    a('<div class="note rec"><b>Recomendação:</b> passar pra 3D o <b>tanque nv.1 e o nv.2, a Mochila T2 e o scanner</b>, que ganham volume e continuam lendo. '
      'A <b>mochila nv.1</b> fica equivalente: vale ir pro 3D só pra família com a T2 ficar igual. As <b>botas ficam piores em 3D</b>, porque em 16 px o par em 3/4 vira um bloco baixo. '
      'Pra elas eu manteria o 2D de perfil da rodada 1, que já tem sombra própria e o contorno, então não destoa dos vizinhos 3D no slot. '
      'A família continua óbvia: o nv.2 é a mesma peça com dourado <code>#f2c46d</code> no topo (tampas, válvulas, tiras e fivela) e o material novo (fibra verde, gel).</div>')

    a('<h2>Pro Dev integrar (depois do ok do dono)</h2><ul>')
    a('<li>Só troca PNG, nenhum código muda. <code>icon_o2_tank.png</code>, <code>icon_backpack.png</code> e <code>icon_scanner.png</code> já existem no jogo: o 3D de '
      '<code>v08_m5_itens_r2/pendentes/</code> entra por cima, com o mesmo nome e o mesmo tamanho (16×16). <code>icon_o2_tank_t2</code>, <code>icon_backpack_t2</code> e <code>icon_boots</code> '
      'são novos (rodada 1). Botas: se o dono seguir a recomendação, use o de <code>v08_m5_itens/pendentes/icon_boots.png</code>.</li>')
    a('<li><code>icon_hydrogel.png</code>: use o de <code>v08_m5_itens_r2/pendentes/</code> (slime A). O B está em <code>candidatas/icon_hydrogel_B.png</code>.</li>')
    a('<li>O fantasma do slot vazio no TRAJE continua sendo o ícone nv.1 a alpha 45. Com o 3D, o fantasma ganha volume junto.</li>')
    a('<li>Gerar de novo: <code>python3 tools/sprites/v08_m5_r2.py</code>. É determinístico e só lê <code>assets/</code>.</li>')
    a('</ul></div></body></html>')
    (REP / "index.html").write_text("\n".join(o), encoding="utf-8")


def main():
    build()
    ok = check()
    previews()
    write_html(ok)
    print("ok")


if __name__ == "__main__":
    main()
