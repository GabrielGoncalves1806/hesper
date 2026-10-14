#!/usr/bin/env python3
"""v0.5 · Bancada T2 ("Montadora") e os ícones dos itens novos. PROPOSTA: nada daqui vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_bancada_itens.py

A bancada usa o mesmo motor r3d e as mesmas peças das máquinas aprovadas (tools/sprites/machines_r3d.py): sapata B,
paleta bege/metal/laranja, dourado do nv.2, contorno #1b1630, luz de cima-esquerda em 5 faixas. O laser é o mesmo
feixe 2D da drill. Os ícones são desenhados à mão (mapa de caracteres), 16×16, no padrão dos icon_* do jogo.

Saída: reports/design/v05_bancada_itens/pendentes/
    machine_workbench.png            40×64  repouso (garra recolhida, visor desligado)
    anim/anim_machine_workbench.png  160×64 operando, 4 quadros de 40×64 (quadro 0 = o repouso)
    icon_workbench.png               16×16  ícone do item da bancada (extra: ela vai no inventário pros postos)
    icon_{iron_ingot,water_capsule,silicon_wafer,circuit,chip,wire,diagram}.png  16×16
Depois chama o v05_bancada_itens_report.py (prévias e index.html).
Determinístico: sem aleatório.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import machines_r3d as M  # noqa: E402
from r3d import Pal  # noqa: E402

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v05_bancada_itens"
PEND = REP / "pendentes"

OUTLINE = M.OUTLINE
CYAN, CYAN_D, CYAN_L = M.CYAN, M.CYAN_D, M.CYAN_L
ORANGE, GOLD = M.ORANGE, M.GOLD
OK, ALERT = M.OK, M.ALERT

# cobre do corpo: o "cobre" do conceito do dono puxado pra família (entre o laranja das faixas e o ferro do minério)
P_COPPER = Pal(["#ffd2a8", "#dc8a54", "#bb6a3c", "#8c4a2b", "#5c2c1c"])
P_COPPER_D = Pal(["#bb6a3c", "#a5582f", "#8c4a2b", "#6e3822", "#4a2216"])     # frisos e rebaixos do cobre
P_MOUTH = Pal(["#3a3549", "#2e2a3a", "#242030", "#1b1726", "#141019"])          # boca (escura, sem luz)
P_SCREEN_OFF = Pal(["#1d2b3a"] * 5, emit=True, emit_tone=0)
P_SCREEN_LINE = Pal(["#263a4e"] * 5, emit=True, emit_tone=0)
P_CY = [Pal([c] * 5, emit=True, emit_tone=0) for c in ("#0f3a52", CYAN_D, CYAN, CYAN_L, "#ffffff")]


def _emit(c):
    return Pal([c] * 5, emit=True, emit_tone=0)


# ---------------------------------------------------------------------------------------------------------------------
# Bancada T2 · v2 (feedback do dono): do tamanho do baú (32×40), braço robótico de perfil na quina da frente-esquerda
# do tampo, 8 quadros (a 4 fps = ciclo de 2 s). A v1 (40×64, garra no meio) fica só no report, em v1/.
# ---------------------------------------------------------------------------------------------------------------------
W, H = 32, 40
NF = 8                           # quadros da animação (quadro 0 = repouso = o parado)
FPS = 4                          # sugerido
Z0 = M.SAP_H
ZT = 20.0                        # tampo do corpo de cobre
YF = -7.0                        # frente do corpo
VIS = (-5.0, 5.0, 12.5, 18.5)    # visor (x0, x1, z0, z1)
MOUTH = (-4.0, 4.0, 6.0, 10.6)   # boca
BASE = (-7.5, -4.5)              # pé do braço: quina da frente-esquerda do tampo
YA = -5.5                        # plano do braço (de perfil, paralelo à tela)

# poses: (ombro_z, cotovelo, punho) com cotovelo/punho em (x, z); o braço fica no plano Y = YA, o punho vem pra
# frente até YF - 1.5 quando trabalha (a garra fica na frente do visor)
POSES = [
    ((-10.0, ZT + 13.5), (-1.5, ZT + 17.0), 0.0),    # 0 repouso: antebraço erguido, garra recolhida no alto
    ((-10.0, ZT + 13.5), (-0.5, ZT + 15.5), 0.3),    # 1 começa a baixar
    ((-9.5, ZT + 13.5), (0.5, ZT + 13.0), 0.7),      # 2 punho chega em cima do visor
    ((-9.0, ZT + 13.0), (1.0, ZT + 10.5), 1.0),      # 3 desce, laser acende fino
    ((-9.0, ZT + 13.0), (1.0, ZT + 10.5), 1.0),      # 4 laser cheio
    ((-9.0, ZT + 13.0), (1.0, ZT + 10.5), 1.0),      # 5 laser cheio (pulsa)
    ((-9.5, ZT + 13.5), (0.5, ZT + 13.0), 0.6),      # 6 laser apaga, sobe
    ((-10.0, ZT + 13.5), (-0.5, ZT + 15.5), 0.2),    # 7 voltando pro repouso
]
LASER = [0, 0, 0, 1, 2, 2, 0, 0]                    # 0 apagado, 1 fino, 2 cheio
VISOR = [0, 0, 1, 2, 3, 3, 2, 1]                    # 0 desligado .. 3 todo aceso


def _pillar_paint(t, z, cap):
    out = np.zeros(len(t), int)
    out[(z > 11.0) & (z < 13.0) & ~cap] = 1           # faixa laranja (a do fabricador)
    out[(z > 17.2) & (z < 18.6) & ~cap] = 2           # friso dourado do nv.2
    return out


def _body_paint():
    mx0, mx1, mz0, mz1 = MOUTH
    zc = (Z0 + ZT) / 2

    def paint(L, face):
        out = np.zeros(len(L), int)
        x, z = L[:, 0], L[:, 2] + zc
        if face == 2:
            out[(z > 11.2) & (z < 12.2)] = 1
            frame = (x > mx0 - 1.1) & (x < mx1 + 1.1) & (z > mz0 - 0.2) & (z < mz1 + 1.1)
            out[frame] = 1
            out[(x > mx0) & (x < mx1) & (z > mz0) & (z < mz1)] = 2
        elif face == 5:
            out[(np.abs(x) > 5.6) | (np.abs(L[:, 1]) > 5.6)] = 1
        return out
    return paint


def _visor_paint(level, f):
    vx0, vx1, vz0, vz1 = VIS
    zc = (vz0 + vz1) / 2

    def paint(L, face):
        out = np.zeros(len(L), int)
        if face != 2:
            return out
        x, z = L[:, 0], L[:, 2] + zc
        scr = (x > vx0 + 1.0) & (x < vx1 - 1.0) & (z > vz0 + 1.0) & (z < vz1 - 1.0)
        out[scr] = 1
        if level == 0:
            out[scr & (x < vx0 + 2.0) & (z > vz1 - 2.0)] = 2          # reflexo do vidro apagado
            return out
        gx = (np.floor(x - vx0) % 2) == 0
        out[scr & gx] = 2
        out[scr & (np.abs(x) < 0.6)] = 3
        band = vz1 - 1.6 - (f % 3) * 1.4
        out[scr & (np.abs(z - band) < 0.5)] = 3
        if level == 3:
            out[scr & (np.abs(x) < 1.6) & (np.abs(z - zc) < 1.2)] = 4
        return out
    return paint


def _arm_pts(f):
    (ex, ez), (wx, wz), fwd = POSES[f]
    sh = (BASE[0], YA, ZT + 3.0)
    yw = YA + (YF - 1.6 - YA) * fwd
    return sh, (ex, YA + 0.5, ez), (wx, yw, wz)


def workbench(f):
    """Bancada T2 v2 no quadro f (0 = repouso)."""
    lv = VISOR[f]
    sc = M.scene(W, H, -M.SAP_D)
    M.sapata(sc, 12)
    for sx in (-1, 1):                                              # colunas bege
        sc.cyl(sx * 9.3, -3.0, 3.1, Z0, ZT + 1.0, M.P_BEIGE, paint=_pillar_paint, extra=(M.P_ORANGE, M.P_GOLD))
    sc.box((-7.2, 7.2), (YF, 6.5), (Z0, ZT), P_COPPER, paint=_body_paint(), extra=(P_COPPER_D, P_MOUTH))
    vx0, vx1, vz0, vz1 = VIS
    if lv == 0:
        pals = [M.P_DARK, P_SCREEN_OFF, P_SCREEN_LINE]
    else:
        base = [P_CY[0], P_CY[1], P_CY[1]][lv - 1]
        line = [P_CY[1], P_CY[2], P_CY[3]][lv - 1]
        pals = [M.P_DARK, base, line, P_CY[3] if lv > 1 else P_CY[2], P_CY[4]]
    sc.box((vx0, vx1), (YF - 0.7, YF), (vz0, vz1), pals[0], paint=_visor_paint(lv, f), extra=tuple(pals[1:]))
    mx0, mx1, mz0, mz1 = MOUTH
    sc.box((mx0 - 0.5, mx1 + 0.5), (YF - 2.0, YF), (Z0, mz0 + 0.4), M.P_METAL)          # bandeja
    # braço robótico de perfil: base giratória, ombro, braço, cotovelo, antebraço, punho e garra
    sh, el, wr = _arm_pts(f)
    sc.cyl(BASE[0], BASE[1], 2.6, ZT, ZT + 1.2, M.P_DARK)
    sc.cyl(BASE[0], BASE[1], 1.9, ZT + 1.2, ZT + 2.4, M.P_ORANGE)
    stripe = lambda sv, th: np.where((sv > 4.5) & (sv < 6.0), 1, 0)                   # faixa laranja no meio
    sc.tube([sh, el], 1.2, M.P_BEIGE, paint=stripe, extra=(M.P_ORANGE,))
    sc.tube([el, wr], 1.0, M.P_BEIGE, paint=stripe, extra=(M.P_ORANGE,))
    sc.sphere(sh, 1.6, M.P_DARK)
    sc.sphere(el, 1.5, M.P_DARK)
    hx, hy, hz = wr
    sc.rbox((hx, hy, hz), (1.5, 1.2, 1.1), 0.4, M.P_DARK)                             # punho
    opn = 1.4 if LASER[f] else 0.8
    for sx in (-1, 1):                                                                 # garra: 2 dedos de aço
        sc.tube([(hx + sx * 0.9, hy, hz - 0.9), (hx + sx * opn, hy, hz - 3.2)], 0.55, M.P_STEEL, caps=False)
    # LEDs na coluna da esquerda
    sc.dot(-10.2, -6.3, 8.0, OK if f in (0, 1, 2, 7) else "#2f5a2c", always=True)
    sc.dot(-8.6, -6.3, 8.0, CYAN if lv >= 2 else CYAN_D if lv else "#2b5b73", always=True)
    cv = M.render(sc)
    if LASER[f]:
        tip = M._proj(sc, hx, hy, hz - 3.4)
        hit = M._proj(sc, hx, YF - 0.8, (vz0 + vz1) / 2)
        _beam(cv, tip, hit, LASER[f], f)
    if LASER[f] == 2:
        _sparks(cv, sc, f)
    return cv


def _beam(cv, p0, p1, power, f):
    """Feixe vertical chapado da garra ao visor: 1 px branco com borda ciano (cheio) ou só 1 px ciano (fino)."""
    x0, y0, y1 = int(p0[0]), int(round(p0[1])), int(round(p1[1]))
    for y in range(y0, y1 + 1):
        if power == 1:
            cv.px(x0, y, CYAN_L)
            continue
        cv.px(x0, y, "#ffffff")
        side = CYAN_L if (y + f) % 3 else CYAN
        cv.px(x0 - 1, y, side)
        cv.px(x0 + 1, y, side)


def _sparks(cv, sc, f):
    vx0, vx1, vz0, vz1 = VIS
    mx0, mx1, mz0, mz1 = MOUTH
    pts = {4: [(-2.0, mz0 + 2.0, CYAN), (1.5, mz0 + 3.5, "#ffffff"), (-6.5, vz1 + 1.0, CYAN_L), (6.0, vz1 + 2.0, CYAN)],
           5: [(1.0, mz0 + 1.5, CYAN_L), (-1.5, mz0 + 3.0, CYAN), (6.5, vz0 + 3.0, CYAN_L), (-6.0, vz1 + 2.5, CYAN_D)]}[f]
    for (x, z, c) in pts:
        sx, sy = M._proj(sc, x, YF - 1.0, z)
        if z < mz1 or not cv.solid(int(sx), int(sy)):
            cv.px(int(sx), int(sy), c)


# ---------------------------------------------------------------------------------------------------------------------
# Ícones 16×16 (desenhados à mão)
# ---------------------------------------------------------------------------------------------------------------------
MT = dict(w="#f4f6f8", l="#e1e5ea", m="#c8cdd4", s="#abb2bb", d="#8c949e", g="#6b717a", k="#3b3f46", kk="#2a2d33",
          o="#e2733a", oh="#f29a62", od="#a8471f")                      # o MT do build_sprites (ícones aprovados)
IRON = dict(hi="#ffd8b0", light="#e8a066", mid="#c97a45", dark="#a5582c", line="#4a2214")
SIL = dict(hi="#f4f8fc", light="#c3d1e2", mid="#a2b0c4", dark="#7d8ca3", line="#2c3342")


def icon(rows, pal):
    cv = M.Canvas(16, 16)
    assert len(rows) == 16, len(rows)
    cv.draw_map(rows, pal)
    cv.outline()
    return cv


class Ic:
    """Rascunho 16×16 com pincéis simples; `done()` põe o contorno #1b1630 (como todos os icon_* do jogo)."""

    def __init__(self):
        self.cv = M.Canvas(16, 16)

    def r(self, x, y, w, h, c):
        self.cv.rect(x, y, w, h, c)

    def p(self, x, y, c):
        self.cv.px(x, y, c)

    def ps(self, pts, c):
        for (x, y) in pts:
            self.cv.px(x, y, c)

    def cut(self, pts):
        for (x, y) in pts:
            self.cv.a[y, x] = 0

    def done(self):
        self.cv.outline()
        return self.cv


STEEL = dict(W="#ffffff", b="#eef1f6", T="#d4d9e2", d="#aeb4c2", c="#f2f4f8", l="#c3c8d4", F="#a2a9b8",
             r="#b8becb", D="#6c7383", E="#555b6a", e="#5f6676", s="#7c8394")


def icon_iron_ingot():
    """Lingote de ferro v2 (pedido do dono, ref. `ref_lingote_aco.png`): barra de AÇO cinza claro, bloco retangular
    em 3/4 com o tampo grande e claro, chanfro brilhante nas quinas do tampo, a frente média com um reflexo e o lado
    direito na sombra. Ferro processado tem cor de ferro: nada de cobre."""
    rows = [
        "................",
        "................",
        "................",
        ".....bbbbbbbbb..",
        "....bTWWTTTTTTd.",
        "...bTWWTTTTTTdD.",
        "..bTWWTTTTTTdDD.",
        ".cccccccccccDDD.",
        ".lFFrFFFFFFFDDD.",
        ".lFrFFFFFFFFDDE.",
        ".lrFFFFFrFFFDE..",
        ".ssssssssssse...",
        "................",
        "................",
        "................",
        "................",
    ]
    cv = M.Canvas(16, 16)
    cv.draw_map(rows, STEEL, oy=1)
    cv.px(2, 10, "#ffffff")
    cv.outline()
    return cv


WATER = ["#d8f6ff", "#9fe0f5", "#4aa8d8", "#2f7fb3", "#1f5a85"]


def icon_water_capsule():
    """Cápsula de água: cilindro de vidro gordinho com tampas de metal e a água azul até 2/3, superfície com onda,
    bolhas e o reflexo branco no vidro. Uma só peça (o tanque de O₂ são dois cilindros brancos com faixa ciano)."""
    I = Ic()
    x0, w = 3, 10
    I.r(6, 0, 4, 1, MT["o"]); I.p(6, 0, MT["oh"])                 # manopla
    I.r(7, 1, 2, 1, MT["g"])
    I.r(x0 + 1, 2, w - 2, 1, MT["l"])                             # tampa de cima
    I.r(x0, 3, w, 1, MT["m"])
    I.r(x0 + 1, 2, 2, 1, MT["w"])
    I.r(x0 + w - 2, 3, 2, 1, MT["d"])
    I.r(x0, 4, w, 1, MT["g"])                                     # anel escuro
    I.r(x0, 5, w, 2, "#cfeaf4")                                   # vidro vazio em cima
    I.r(x0 + w - 3, 5, 3, 2, "#9fc9dc")
    I.r(x0, 7, w, 1, WATER[1])                                    # superfície da água (onda)
    I.ps([(x0 + 2, 7), (x0 + 6, 7)], WATER[0])
    I.ps([(x0 + 3, 6), (x0 + 4, 6)], WATER[1])
    I.r(x0, 8, w, 4, WATER[2])
    I.r(x0 + w - 3, 8, 3, 4, WATER[3])
    I.r(x0, 11, w, 1, WATER[3]); I.r(x0 + w - 3, 11, 3, 1, WATER[4])
    I.r(x0 + 1, 5, 1, 6, "#ffffff")                               # reflexo do vidro
    I.ps([(x0 + 4, 9), (x0 + 5, 10), (x0 + 6, 8)], WATER[0])      # bolhas
    I.r(x0, 12, w, 1, MT["g"])                                    # anel de baixo
    I.r(x0, 13, w, 1, MT["m"]); I.r(x0 + w - 2, 13, 2, 1, MT["d"])
    I.r(x0 + 1, 14, w - 2, 1, MT["s"])
    I.p(x0, 13, MT["w"])
    return I.done()


def icon_silicon_wafer():
    """Wafer de silício: disco espelhado em 3/4 (elipse 14×10 com a borda de 1 px de espessura), grade de dies, o
    chanfro reto embaixo e um reflexo iridescente (lilás e ciano) atravessando na diagonal."""
    I = Ic()
    cx, cy, rx, ry = 8.0, 7.0, 7.0, 5.6
    yy, xx = np.mgrid[0:16, 0:16]
    top = ((xx + 0.5 - cx) / rx) ** 2 + ((yy + 0.5 - cy) / ry) ** 2 <= 1.0
    side = ((xx + 0.5 - cx) / rx) ** 2 + ((yy - 0.5 - cy) / ry) ** 2 <= 1.0
    flat = yy >= 12                                                    # chanfro reto (o "flat" do wafer)
    for y, x in zip(*np.nonzero(side & ~top & ~(yy >= 13))):
        I.p(x, y, SIL["dark"] if x < 11 else "#5f6b80")
    for y, x in zip(*np.nonzero(top & ~flat)):
        g = (x % 2 == 0) or (y % 2 == 1)
        c = SIL["light"] if not g else SIL["mid"]
        d = x + y
        if 9 <= d <= 10:
            c = "#d6c2f2" if not g else "#b9a6dc"                      # reflexo lilás
        elif 11 <= d <= 12:
            c = "#bfeaff" if not g else "#97cbe6"                      # e ciano
        elif d <= 7:
            c = SIL["hi"] if not g else SIL["light"]
        I.p(x, y, c)
    for y, x in zip(*np.nonzero(top & flat)):
        I.p(x, y, SIL["mid"])
    I.r(5, 12, 6, 1, SIL["dark"])
    I.ps([(4, 3), (5, 2), (3, 4)], "#ffffff")                        # brilho na borda de cima
    return I.done()


PCB = dict(hi="#9be08a", base="#2f8a3e", trace="#6fc85a", dark="#1f5e2c", side="#246b33")


def icon_circuit():
    """Circuito elétrico: placa verde deitada (retangular, mais larga que alta) com trilhas verde-claras, vias
    douradas, um CI preto pequeno, um resistor laranja e os dentes dourados do conector saindo embaixo."""
    I = Ic()
    I.r(1, 3, 14, 9, PCB["base"])
    I.r(1, 3, 14, 1, PCB["hi"]); I.r(1, 3, 1, 9, PCB["hi"])
    I.r(14, 4, 1, 8, PCB["side"]); I.r(1, 11, 14, 1, PCB["dark"])
    for x in (3, 5, 7, 9, 11):                                         # dentes do conector (borda dourada)
        I.r(x, 12, 1, 2, M.GOLD)
        I.p(x, 13, M.GOLD_D)
    # trilhas
    I.r(3, 5, 4, 1, PCB["trace"]); I.r(3, 5, 1, 5, PCB["trace"]); I.r(3, 9, 5, 1, PCB["trace"])
    I.r(5, 7, 3, 1, PCB["trace"]); I.r(7, 7, 1, 3, PCB["trace"])
    I.r(12, 9, 1, 2, PCB["trace"]); I.r(9, 10, 4, 1, PCB["trace"])
    for (x, y) in ((6, 5), (5, 7), (9, 10), (3, 10)):                  # vias
        I.p(x, y, M.GOLD)
    # CI preto com pernas prateadas
    I.r(9, 5, 4, 3, MT["kk"]); I.r(9, 5, 4, 1, MT["k"])
    for x in (9, 11):
        I.p(x, 4, MT["m"]); I.p(x + 1, 8, MT["m"])
    I.p(9, 5, MT["g"])
    # resistor
    I.r(9, 9, 1, 1, PCB["trace"])
    I.r(4, 7, 1, 1, MT["o"])
    I.p(10, 9, MT["o"]); I.p(11, 9, MT["oh"])
    return I.done()


def icon_chip():
    """Chip de computador (CPU): quadrado escuro de pé no ícone, pernas douradas nos 4 lados, tampa prateada no
    meio com o marcador dourado no canto e a gravação."""
    I = Ic()
    I.r(3, 3, 10, 10, MT["kk"])
    I.r(3, 3, 10, 1, MT["k"]); I.r(3, 3, 1, 10, MT["k"])
    for k in (4, 6, 9, 11):            # pernas: 4 por lado
        I.p(k, 2, M.GOLD); I.p(k, 1, M.GOLD_D)
        I.p(k, 13, M.GOLD); I.p(k, 14, M.GOLD_D)
        I.p(2, k, M.GOLD); I.p(1, k, M.GOLD_D)
        I.p(13, k, M.GOLD); I.p(14, k, M.GOLD_D)
    I.r(5, 5, 6, 6, MT["m"])                                           # tampa prateada
    I.r(5, 5, 6, 1, MT["w"]); I.r(5, 5, 1, 6, MT["l"])
    I.r(10, 6, 1, 5, MT["d"]); I.r(6, 10, 5, 1, MT["d"])
    I.r(7, 7, 3, 1, MT["s"]); I.r(7, 8, 2, 1, MT["s"])                  # gravação
    I.p(4, 11, M.GOLD)                                                 # marcador do pino 1
    return I.done()


COPPER = dict(hi="#ffc49a", light="#f08850", mid="#cc5f30", dark="#8f3a1e")


def icon_wire():
    """Fios: bobina em pé (carretel) com as voltas de fio de cobre avermelhado entre duas abas de metal escuro e a
    ponta do fio solta, enrolando pra fora pela direita."""
    I = Ic()
    I.r(2, 1, 11, 3, MT["g"])                                          # aba de cima (elipse achatada)
    I.r(3, 1, 9, 1, MT["s"]); I.r(2, 2, 11, 1, MT["d"])
    I.cut([(2, 1), (12, 1)])
    I.r(6, 2, 3, 1, MT["kk"])                                          # furo do eixo
    I.r(2, 3, 11, 1, MT["k"])
    for y in range(4, 11):                                             # voltas de fio (cilindro com sombra)
        stripe = y % 2 == 0
        I.r(3, y, 9, 1, COPPER["light"] if stripe else COPPER["mid"])
        I.r(3, y, 2, 1, COPPER["hi"] if stripe else COPPER["light"])
        I.r(10, y, 2, 1, COPPER["mid"] if stripe else COPPER["dark"])
    I.r(2, 11, 11, 1, MT["k"])                                         # aba de baixo
    I.r(2, 12, 11, 2, MT["g"]); I.r(3, 14, 9, 1, MT["k"])
    I.r(2, 12, 2, 1, MT["d"])
    I.ps([(12, 6), (13, 6), (14, 7), (14, 8), (13, 9), (13, 10), (14, 11)], COPPER["light"])   # ponta solta
    I.p(14, 11, COPPER["hi"])
    return I.done()


BP = dict(paper="#2f62b3", hi="#4f86d6", grid="#3f74c4", dark="#24508f", ink="#cfe6ff", back="#9cc2f0",
          back_d="#7fa8e0")


def icon_diagram():
    """Diagrama: evolução do projeto (icon_blueprint). Mesma folha azul de planta com grade, agora DEITADA (cartão),
    sem o chip, com o desenho técnico de uma engrenagem e as cotas, um clipe laranja no topo e o canto de baixo
    enrolando (o verso claro aparece)."""
    I = Ic()
    I.r(1, 3, 14, 10, BP["paper"])
    I.r(1, 3, 14, 1, BP["hi"]); I.r(1, 3, 1, 10, BP["hi"])
    I.r(14, 4, 1, 9, BP["dark"]); I.r(1, 12, 14, 1, BP["dark"])
    for g in (4, 7, 10):                                               # grade (mais apagada que o desenho)
        I.r(2, g, 12, 1, BP["grid"])
    for g in (2, 5, 8, 11):
        I.r(g, 4, 1, 8, BP["grid"])
    # o diagrama: bloco quadrado ligado a um círculo (seta), cota com as pontas embaixo
    I.r(3, 5, 4, 1, BP["ink"]); I.r(3, 8, 4, 1, BP["ink"]); I.r(3, 5, 1, 4, BP["ink"]); I.r(6, 5, 1, 4, BP["ink"])
    I.ps([(10, 5), (11, 5), (9, 6), (12, 6), (9, 7), (12, 7), (10, 8), (11, 8)], BP["ink"])
    I.r(7, 7, 2, 1, BP["ink"]); I.p(8, 6, BP["ink"])
    I.r(3, 10, 9, 1, BP["ink"]); I.p(3, 9, BP["ink"]); I.p(11, 9, BP["ink"])
    # canto enrolando embaixo à direita
    I.cut([(14, 12), (13, 12), (14, 11)])
    I.ps([(12, 12), (13, 11), (14, 10)], BP["back"])
    I.p(12, 11, BP["back_d"]); I.p(13, 10, BP["back_d"])
    # clipe laranja segurando em cima
    I.r(6, 1, 4, 3, MT["o"]); I.r(6, 1, 4, 1, MT["oh"]); I.r(7, 2, 2, 1, MT["od"])
    I.r(6, 4, 4, 1, MT["od"])
    return I.done()


def icon_workbench():
    """Ícone da bancada T2 (v2): a bancada baixa do tamanho do baú, colunas bege com a faixa laranja, corpo de cobre,
    visor escuro com o reflexo ciano, a boca, e o braço robótico de perfil na quina esquerda (base, braço, cotovelo,
    antebraço, punho e os 2 dedos)."""
    rows = [
        "................",
        "...kWWWWkkk.....",
        "...W....s.s.....",
        "...O............",
        "...W............",
        "..kkk...........",
        ".bbPPPPPPPPPbb..",
        ".WbCCCCCCCCCWb..",
        ".WbCDDDDDDDCWb..",
        ".WbCDqDDDDDCWb..",
        ".OOCCCCCCCCCOO..",
        ".WbCCKKKKKCCWb..",
        ".WbCCKKKKKCCWb..",
        ".mmmmmmmmmmmmm..",
        ".MMMMMMMMMMMMM..",
        "................",
    ]
    pal = {"k": "#2e2a3a", "W": "#efe6d4", "b": "#d6c9b4", "s": "#b9bccb", "O": ORANGE, "P": "#ffd2a8",
           "C": "#dc8a54", "D": "#1d2b3a", "q": CYAN, "K": "#242030", "m": "#a7a3b8", "M": "#58536b"}
    cv = M.Canvas(16, 16)
    cv.draw_map([r.ljust(16, ".") for r in rows], pal)
    cv.outline()
    return cv


def build_icons():
    return {
        "icon_iron_ingot.png": icon_iron_ingot(),
        "icon_water_capsule.png": icon_water_capsule(),
        "icon_silicon_wafer.png": icon_silicon_wafer(),
        "icon_circuit.png": icon_circuit(),
        "icon_chip.png": icon_chip(),
        "icon_wire.png": icon_wire(),
        "icon_diagram.png": icon_diagram(),
        "icon_workbench.png": icon_workbench(),
    }


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    still = workbench(0)
    out["machine_workbench.png"] = still
    out["anim/anim_machine_workbench.png"] = M.strip([workbench(f) for f in range(NF)])
    out.update(build_icons())
    for name, cv in out.items():
        cv.save(PEND / name)
    return out


if __name__ == "__main__":
    o = build()
    for k, cv in o.items():
        print(f"{k}: {cv.w}×{cv.h}")
    import v05_bancada_itens_report as REP_
    print(REP_.build())
