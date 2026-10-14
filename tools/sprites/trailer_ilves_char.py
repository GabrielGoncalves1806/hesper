"""Dra. Ilves, a cientista da Colônia Hesper (personagem das cutscenes do trailer) · v2 "mais humana".

v2 (feedback do dono): silhueta de curvas (Catmull-Rom) em vez de blocos, proporção humana (cabeça ~1/7 da altura),
sombreamento que segue a forma (form_shade), antialias manual no contorno (aa_outline), e animação com easing e
movimento secundário (coque, mecha solta e barra do jaleco atrasam o corpo), respiração no ombro e piscada natural
(meio-fechado → fechado → meio-fechado).

Mesma família visual do Explorador (contorno #1b1630 por peça, luz em faixas, laranja #e2733a da colônia), mas uma
pessoa diferente: sem capacete, cabelo escuro num coque com prendedor laranja, óculos de aro fino, jaleco branco aberto
por cima do macacão azul-acinzentado da colônia, gola e punhos laranja, crachá com LED ciano, botas escuras.

Todas as poses recebem `light` (direção PRA luz, em passos de pixel) pra sombra já nascer do lado certo da cena.
"""
from __future__ import annotations

import math

import numpy as np

from trailer_lib import (OUTLINE, Cv, aa_outline, blob, breath, cr_closed, ease, form_shade, mix, stroke,
                         tube)

COAT = ["#f4efe6", "#d9d1c8", "#aea4a6", "#7f7482"]
SUIT = ["#8a95b5", "#66708f", "#4b5371", "#353b55"]
ACC = ["#f4a06a", "#e2733a", "#a9482a"]
SKIN = ["#f6cfae", "#e0a885", "#bf8066", "#8d5a4a"]
LIP = "#b86a60"
HAIR = ["#7a5560", "#55383f", "#3b262e", "#2a1a21"]
BOOT = ["#6a6378", "#4a4458", "#353042", "#252030"]
GLASS = ["#eef6ff", "#a6ecff", "#59d0e6"]
CYAN = "#59d0e6"


# ---------------------------------------------------------------------------------------------------------------
# peças
# ---------------------------------------------------------------------------------------------------------------
def piece(cv, shape, ramp, light, hi=1, sh=2, deep=1, details=None, outline=True):
    """Desenha a silhueta (shape), sombreia pela forma, aplica detalhes SÓ dentro dela, contorna e cola."""
    tmp = Cv(cv.w, cv.h)
    shape(tmp)
    m = tmp.arr()[:, :, 3] == 255
    form_shade(tmp, ramp, light, hi, sh, deep)
    if details:
        det = Cv(cv.w, cv.h)
        details(det)
        a, d = tmp.arr(), det.arr()
        sel = m & (d[:, :, 3] == 255)
        a[sel] = d[sel]
        tmp.set_arr(a)
    if outline:
        tmp.outline()
    cv.paste(tmp)
    return m


def rot(pts, ang, cx, cy, s=1.0):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + (x * ca - y * sa) * s, cy + (x * sa + y * ca) * s) for x, y in pts]


# ---------------------------------------------------------------------------------------------------------------
# cabeça pequena de perfil (poses de corpo inteiro). Coordenadas locais: centro do crânio = (0, 0), rosto pra +x.
# tilt > 0 = olhando pra baixo. eye: 1 aberto, 0.5 meio, 0 fechado. lag: atraso do coque/mecha (-1..1).
# ---------------------------------------------------------------------------------------------------------------
SKULL = [(-7, -1), (-5.5, -6), (0, -8.2), (5, -6.6), (7, -3), (7.4, -0.6), (9.4, 2.4), (8.6, 3.4), (7.6, 3.6),
         (8, 4.6), (7.4, 5.4), (7.6, 6.8), (5.5, 8.4), (2, 8.6), (-1, 6.5), (-5, 4.5)]
HAIRS = [(-8, 0), (-7, -6), (-2, -9.4), (4, -8.4), (7.4, -4.6), (5.6, -4.4), (3, -3.8), (0.5, -2.4), (-0.5, 1.6),
         (-1.6, 5.4), (-6, 5)]


def head_small(cv, cx, cy, tilt=0.0, eye=1.0, lag=0.0, light=(-1, -1), glow=None):
    R = lambda pts: rot(pts, tilt, cx, cy)  # noqa: E731

    # coque atrás (atrasa: sobe/desce depois da cabeça)
    def bun(c):
        bx, by = R([(-6.4, -6.2 + lag * 0.7)])[0]
        c.ell(round(bx - 3.6), round(by - 3.4), round(bx + 3.4), round(by + 3.2), "#ffffff")
    piece(cv, bun, HAIR, light, hi=1, sh=1, deep=0,
          details=lambda d: d.line(R([(-8.6, -6.6 + lag * 0.7), (-5, -8.4 + lag * 0.7)]), HAIR[0]))

    def skull(c):
        blob(c, R(SKULL), "#ffffff", 6)
    piece(cv, skull, SKIN, light, hi=1, sh=1, deep=0, details=lambda d: (
        d.px(*map(round, R([(6.4, 6.2)])[0]), SKIN[2]),                       # sombra embaixo do lábio
        d.px(*map(round, R([(7.6, 4.3)])[0]), LIP),                           # boca
        d.px(*map(round, R([(9, 2.2)])[0]), SKIN[0])))                        # luz na ponta do nariz
    # olho (por baixo dos óculos)
    ex, ey = R([(5.4, -0.6)])[0]
    if eye > 0.75:
        cv.px(round(ex), round(ey), OUTLINE)
        cv.px(round(ex) - 1, round(ey) - 1, HAIR[3])                            # cílios / pálpebra
    elif eye > 0.25:
        cv.px(round(ex), round(ey), HAIR[3])
    else:
        cv.px(round(ex), round(ey), SKIN[2])
    # sobrancelha
    stroke(cv, R([(3.6, -3.2), (6.6, -2.6)]), HAIR[2], 4)

    def hair(c):
        blob(c, R(HAIRS), "#ffffff", 6)
    piece(cv, hair, HAIR, light, hi=1, sh=1, deep=0, details=lambda d: (
        stroke(d, R([(-6, -3), (-2, -7.6), (3, -7.8)]), HAIR[0], 4),
        stroke(d, R([(-6.4, 2), (-3, -3), (1, -5.6)]), HAIR[2], 4)))

    def ear(c):
        x, y = R([(-0.4, 1.4)])[0]
        c.ell(round(x - 1.5), round(y - 2), round(x + 1.5), round(y + 2), "#ffffff")
    piece(cv, ear, SKIN, light, hi=0, sh=1, deep=0)
    # óculos: lente fina de perfil + haste até a orelha
    lx, ly = R([(7.6, -0.8)])[0]
    stroke(cv, R([(7.4, -1.2), (0.6, -0.4)]), OUTLINE, 4)
    cv.vline(round(lx), round(ly) - 1, 3, GLASS[2] if glow is None else glow)
    cv.px(round(lx), round(ly) - 1, GLASS[0])
    # mecha solta caindo na frente da orelha (movimento secundário)
    stroke(cv, R([(4.2, -4.6), (4.8 + lag * 0.6, -0.6), (4 + lag * 1.0, 3.4)]), HAIR[1], 4)
    return R([(5.4, -0.6), (7.6, -0.8)])        # olho, lente


# ---------------------------------------------------------------------------------------------------------------
# pose 1 · sentada e curvada no microscópio (perfil pra direita). Caixa 84×96, chão na linha 93.
# phase 0..1 (ciclo de 12 q.), blink: 1/0.5/0. Exporta EYE (onde a ocular tem que estar).
# ---------------------------------------------------------------------------------------------------------------
SIT_W, SIT_H, SIT_FOOT = 84, 96, 93
SIT_BENCH = 47        # tampo da bancada (os antebraços apoiam aqui)


def sit_hunched(phase=0.0, blink=1.0, light=(1, 0), focus=0.0):
    cv = Cv(SIT_W, SIT_H)
    b = breath(phase)                 # respiração: ombro e costas
    bl = breath(phase, 0.12)          # o que atrasa (coque, mecha, barra do jaleco)
    lean = ease(breath(phase, 0.05)) * 0.8
    L = light

    # banco
    def stool(c):
        c.ell(13, 57, 41, 62, "#ffffff")
    piece(cv, stool, BOOT, (-1, -1), hi=1, sh=1, deep=0)
    piece(cv, lambda c: (c.rect(25, 62, 4, 26, "#ffffff")), BOOT, (-1, 0), hi=1, sh=1, deep=0)
    piece(cv, lambda c: c.ell(14, 87, 40, 93, "#ffffff"), BOOT, (-1, -1), hi=1, sh=1, deep=0)

    # perna de trás (mais escura)
    dark = [SUIT[2], SUIT[2], SUIT[3], OUTLINE]
    piece(cv, lambda c: (tube(c, [(27, 57), (35, 56.5), (44, 57.5)], [9, 8, 7], "#ffffff"),
                         tube(c, [(43, 58), (43.5, 72), (43, 85)], [6.5, 5.5, 5], "#ffffff")), dark, L, 1, 1, 0)
    piece(cv, lambda c: blob(c, [(39, 84), (46, 84), (52, 88), (53, 92.6), (39, 92.6)], "#ffffff", 4),
          [BOOT[1], BOOT[2], BOOT[3], BOOT[3]], L, 1, 1, 0)

    # jaleco (tronco curvado: as costas arqueiam, o peito fecha pra baixo; a barra cai atrás do banco)
    coat = [(37, 21.5 - b), (28.5, 26.5 - b), (21.5, 35 - b * 0.7), (18.6, 45 - b * 0.3), (17.4, 53), (14.6, 58),
            (13.4, 62.6), (13.2 + bl * 0.4, 67 + bl * 0.5), (16 + bl * 0.4, 70.4 + bl * 0.5), (23, 69.6 + bl * 0.3),
            (27.4, 63), (29.5, 59), (35, 52), (40.5, 41 - b * 0.4), (43.5, 31 - b * 0.8), (42.5, 24 - b)]

    def coat_det(d):
        stroke(d, [(19, 62), (19.4 + bl * 0.4, 69)], COAT[2], 4)                         # prega da barra
        stroke(d, [(29.5, 26.5 - b), (23.5, 33 - b), (20.4, 42)], COAT[0], 4)            # luz nas costas
        # macacão aparecendo na frente, entre as abas
        blob(d, [(39.4, 27 - b), (43, 29 - b), (40.4, 40), (35.4, 50), (32.6, 50.5), (36, 40)], SUIT[1], 4)
        stroke(d, [(39.4, 27.4 - b), (36, 40), (32.8, 50.4)], COAT[3], 4)                # borda da aba
        d.rect(38, 35 - round(b * 0.5), 2, 3, SUIT[3])                                 # crachá
        d.px(38, 36 - round(b * 0.5), CYAN)
    piece(cv, lambda c: blob(c, coat, "#ffffff", 6), COAT, L, hi=1, sh=2, deep=1, details=coat_det)

    # perna da frente
    piece(cv, lambda c: (tube(c, [(30, 57.4), (38, 56.6), (47, 58)], [9.4, 8.4, 7.4], "#ffffff"),
                         tube(c, [(46.5, 58.5), (47.4, 72), (47, 85.5)], [7, 6, 5.4], "#ffffff")), SUIT, L, 1, 2, 0,
          details=lambda d: stroke(d, [(42, 55), (46.5, 54.6)], SUIT[0], 4))
    piece(cv, lambda c: blob(c, [(43, 84), (50.5, 84), (57, 88), (58, 92.6), (43, 92.6)], "#ffffff", 4), BOOT, L,
          1, 1, 0, details=lambda d: d.hline(44, 86, 6, ACC[2]))
    # pescoço (curva, não caixa)
    hx, hy = 49.6 + lean, 15.6 - b * 0.7 + lean * 0.4
    piece(cv, lambda c: tube(c, [(38.5, 24 - b), (43, 20.5 - b * 0.8), (hx - 3, hy + 4)], [6.4, 5.6, 5], "#ffffff"),
          SKIN, L, 0, 1, 0)
    # gola laranja
    piece(cv, lambda c: blob(c, [(36, 22 - b), (41, 19.5 - b), (44.4, 23 - b), (42.4, 26 - b), (37.4, 25.4 - b)],
                             "#ffffff", 4), ACC, L, 1, 1, 0)

    # braço de trás: só a mão aparece na platina, empurrando a lâmina
    piece(cv, lambda c: blob(c, [(56, 43), (61, 42), (63.4, 44), (60, 46), (56, 45.6)], "#ffffff", 4),
          [SKIN[2], SKIN[2], SKIN[3], SKIN[3]], L, 0, 1, 0)

    head_small(cv, hx, hy, tilt=0.42 + lean * 0.05, eye=blink, lag=bl - b, light=L)

    # braço da frente: ombro caído, cotovelo apoiado na bancada, mão girando o foco
    sx, sy = 36.4, 27.4 - b
    piece(cv, lambda c: tube(c, [(sx, sy), (39.6, 37 - b * 0.4), (42.6, 45)], [7.6, 6.8, 6.4], "#ffffff"), COAT, L,
          1, 2, 1, details=lambda d: stroke(d, [(38, 34 - b * 0.5), (41, 37)], COAT[2], 4))
    piece(cv, lambda c: tube(c, [(42.6, 45), (48, 44.4), (53.6, 42.6)], [6.4, 5.8, 5.4], "#ffffff"), COAT, L, 1, 2,
          1, details=lambda d: stroke(d, [(45, 42.4), (47.4, 46.4)], COAT[2], 4))
    piece(cv, lambda c: tube(c, [(52.6, 42.8), (55, 42)], [5.8, 5.4], "#ffffff"), ACC, L, 1, 1, 0)
    f = focus

    def hand(c):
        blob(c, [(55, 39.6), (58.4, 38.4 + f * 0.6), (61, 39.6 + f * 0.4), (61.4, 42.6), (58.6, 44.6), (55.4, 44.4)],
             "#ffffff", 4)
    piece(cv, hand, SKIN, L, 1, 1, 0, details=lambda d: (
        d.line([(58, 40 + round(f * 0.6)), (60, 41)], SKIN[2]), d.line([(57, 42.6), (59.6, 43)], SKIN[2])))
    aa_outline(cv)
    return cv


def sit_eye(phase=0.0):
    """Posição (x, y) do olho e da lente na pose sentada (pra encostar a ocular)."""
    b = breath(phase)
    lean = ease(breath(phase, 0.05)) * 0.8
    hx, hy = 49.6 + lean, 15.6 - b * 0.7 + lean * 0.4
    return rot([(5.4, -0.6), (7.6, -0.8)], 0.42 + lean * 0.05, hx, hy)


# ---------------------------------------------------------------------------------------------------------------
# pose 2 · em pé de perfil (folha de personagem). Caixa 64×120, pé na linha 117.
# ---------------------------------------------------------------------------------------------------------------
STAND_W, STAND_H, STAND_FOOT = 64, 120, 117


def stand_side(phase=0.0, blink=1.0, light=(-1, -1)):
    cv = Cv(STAND_W, STAND_H)
    b = breath(phase)
    bl = breath(phase, 0.12)
    L = light
    dark = [SUIT[2], SUIT[2], SUIT[3], OUTLINE]
    # perna de trás + bota
    piece(cv, lambda c: tube(c, [(28, 76), (27, 94), (26, 110)], [9, 7.4, 6], "#ffffff"), dark, L, 1, 1, 0)
    piece(cv, lambda c: blob(c, [(22, 108), (29, 108), (35, 113), (35.4, 117.4), (22, 117.4)], "#ffffff", 4),
          [BOOT[1], BOOT[2], BOOT[3], BOOT[3]], L, 1, 1, 0)
    # jaleco: ombro caído, costas levemente curvas, barra abrindo pra trás
    coat = [(28, 24.6 - b), (22, 28 - b), (19.4, 38), (19, 52), (18, 66), (16.6 + bl * 0.5, 80),
            (17 + bl * 0.6, 84.6), (30, 85), (41 + bl * 0.4, 84), (40, 70), (39, 56), (40.4, 44), (39.6, 32 - b),
            (36, 25.4 - b)]

    def coat_det(d):
        blob(d, [(35, 27 - b), (39.4, 30 - b), (40, 44), (39, 56), (38.6, 72), (35, 72), (35.6, 50), (34, 34)],
             SUIT[1], 4)
        stroke(d, [(35, 28 - b), (34.4, 40), (35.4, 60), (35, 72)], COAT[3], 4)
        d.rect(37, 38 - round(b * 0.5), 2, 3, SUIT[3])
        d.px(37, 39 - round(b * 0.5), CYAN)
        stroke(d, [(21, 72), (20 + bl * 0.5, 83)], COAT[2], 4)
        stroke(d, [(26, 74), (26 + bl * 0.3, 84)], COAT[2], 4)
    piece(cv, lambda c: blob(c, coat, "#ffffff", 6), COAT, L, 1, 2, 1, details=coat_det)
    # perna da frente
    piece(cv, lambda c: tube(c, [(33, 86), (33.6, 97), (33, 110)], [8.4, 7.4, 6.2], "#ffffff"), SUIT, L, 1, 2, 0)
    piece(cv, lambda c: blob(c, [(29, 108), (36.4, 108), (43, 113), (43.4, 117.4), (29, 117.4)], "#ffffff", 4), BOOT,
          L, 1, 1, 0, details=lambda d: d.hline(30, 110, 6, ACC[2]))
    # pescoço, gola, cabeça
    piece(cv, lambda c: tube(c, [(30, 26 - b), (32, 19 - b * 0.6)], [6.4, 5.6], "#ffffff"), SKIN, L, 0, 1, 0)
    piece(cv, lambda c: blob(c, [(26, 24 - b), (33, 22.4 - b), (38, 25.6 - b), (35, 28.6 - b), (28, 28 - b)],
                             "#ffffff", 4), ACC, L, 1, 1, 0)
    head_small(cv, 32.6, 12.4 - b * 0.6, tilt=0.0, eye=blink, lag=bl - b, light=L)
    # braço caído, relaxado (curva leve no cotovelo), mão aberta
    piece(cv, lambda c: tube(c, [(28.4, 28 - b), (29.4, 42), (31.4, 55), (33, 62)], [7.6, 6.8, 6, 5.4], "#ffffff"),
          COAT, L, 1, 2, 1, details=lambda d: stroke(d, [(28.4, 43), (31.4, 44)], COAT[2], 4))
    piece(cv, lambda c: tube(c, [(32.4, 61), (33.2, 64)], [5.8, 5.6], "#ffffff"), ACC, L, 1, 1, 0)
    piece(cv, lambda c: blob(c, [(31, 64), (35.4, 64), (36.6, 68.6), (34.6, 71.6), (31.6, 70)], "#ffffff", 4), SKIN, L,
          1, 1, 0, details=lambda d: d.line([(34, 67), (34, 70)], SKIN[2]))
    aa_outline(cv)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# pose 3 · de costas, mão na fechadura (cena 3). Caixa 72×120, pé na linha 117. A mão direita (à direita da tela)
# está levantada no painel. turn 0..1 = o pulso girando a chave. phase = respiração.
# ---------------------------------------------------------------------------------------------------------------
BACK_W, BACK_H, BACK_FOOT = 72, 120, 117
BACK_HAND = (60, 47)      # onde fica a mão (pra alinhar com o painel)


def back_lock(phase=0.0, turn=0.0, droop=0.0, light=(0, -1)):
    cv = Cv(BACK_W, BACK_H)
    b = breath(phase)
    bl = breath(phase, 0.12)
    L = light
    dr = droop                                          # cabeça baixando (peso)
    # pernas
    for x0, ramp in ((26, SUIT), (36, [SUIT[1], SUIT[2], SUIT[3], OUTLINE])):
        piece(cv, lambda c, x0=x0: tube(c, [(x0, 80), (x0 + 0.4, 96), (x0 + 0.6, 110)], [9.4, 7.6, 6.4], "#ffffff"),
              ramp, L, 1, 1, 0)
        piece(cv, lambda c, x0=x0: blob(c, [(x0 - 4.4, 108), (x0 + 4.6, 108), (x0 + 5.4, 117.4), (x0 - 5, 117.4)],
                                        "#ffffff", 4), BOOT, L, 1, 1, 0)
    # braço esquerdo caído (à esquerda da tela)
    piece(cv, lambda c: tube(c, [(20, 30 - b), (17.4, 46), (17.6, 62)], [8, 7, 6], "#ffffff"), COAT, L, 1, 2, 1)
    piece(cv, lambda c: tube(c, [(17.6, 61), (17.6, 64)], [6, 5.6], "#ffffff"), ACC, L, 1, 1, 0)
    piece(cv, lambda c: blob(c, [(15, 64), (20.4, 64), (20.6, 70), (17.4, 72.4), (15, 69.6)], "#ffffff", 4), SKIN, L,
          1, 1, 0)
    # jaleco de costas: ombros caídos e arredondados, cintura marcada pelo martingale, barra abrindo
    coat = [(24, 24 - b), (17.6, 28 - b), (16.6, 36), (19, 50), (18.4, 64), (16.4 + bl * 0.5, 80),
            (16.4 + bl * 0.6, 85), (31, 86 + bl * 0.4), (46 + bl * 0.6, 85), (45.6 + bl * 0.5, 80), (43.4, 64),
            (42.6, 50), (45.4, 36), (44.4, 28 - b), (38, 24 - b)]

    def coat_det(d):
        stroke(d, [(31, 50), (31, 62), (31 + bl * 0.4, 85)], COAT[2], 4)               # costura / fenda
        d.rect(24, 56, 14, 2, COAT[2])                                              # martingale
        d.rect(24, 55, 14, 1, COAT[0])
        d.px(26, 56, COAT[3])
        d.px(35, 56, COAT[3])
        stroke(d, [(21, 34 - b), (25, 44), (24, 54)], COAT[2], 4)                    # prega da omoplata
        stroke(d, [(41, 34 - b), (38, 44), (38.4, 54)], COAT[2], 4)
        stroke(d, [(20, 66), (19 + bl * 0.4, 84)], COAT[2], 4)
        stroke(d, [(42, 66), (43 + bl * 0.5, 84)], COAT[2], 4)
    piece(cv, lambda c: blob(c, coat, "#ffffff", 6), COAT, L, 1, 2, 1, details=coat_det)
    # gola
    piece(cv, lambda c: blob(c, [(23.6, 23 - b), (31, 21 - b), (38.6, 23 - b), (37, 27 - b), (25, 27 - b)], "#ffffff",
                             4), ACC, L, 1, 1, 0)
    # pescoço + cabeça (de costas: nuca, orelhas, coque no alto)
    hy = 12 - b * 0.6 + dr * 1.2
    piece(cv, lambda c: tube(c, [(31, 24 - b), (31, hy + 6)], [7, 6.4], "#ffffff"), SKIN, L, 0, 1, 0)
    for ex, sgn in ((22.6, -1), (39.4, 1)):
        piece(cv, lambda c, ex=ex: c.ell(round(ex - 1.6), round(hy - 1), round(ex + 1.6), round(hy + 3.4), "#ffffff"),
              SKIN, L, 0, 1, 0)
    head = [(31, hy - 9.6), (37, hy - 7.6), (39.6, hy - 2), (38.6, hy + 4), (35, hy + 7.6), (31, hy + 8.4),
            (27, hy + 7.6), (23.4, hy + 4), (22.4, hy - 2), (25, hy - 7.6)]
    piece(cv, lambda c: blob(c, head, "#ffffff", 6), HAIR, L, 1, 1, 0, details=lambda d: (
        stroke(d, [(26, hy - 5), (31, hy - 8), (36, hy - 5)], HAIR[0], 4),
        stroke(d, [(25, hy + 2), (28, hy + 6.6)], HAIR[2], 4),
        stroke(d, [(37, hy + 2), (34, hy + 6.6)], HAIR[2], 4),
        d.hline(28, round(hy + 7), 6, HAIR[3])))
    # hastes dos óculos sumindo atrás da orelha
    cv.px(22, round(hy), OUTLINE)
    cv.px(40, round(hy), OUTLINE)
    lag = (bl - b) * 0.8 + dr * 0.6
    piece(cv, lambda c: c.ell(26, round(hy - 12 + lag), 36, round(hy - 3 + lag), "#ffffff"), HAIR, L, 1, 1, 0,
          details=lambda d: (stroke(d, [(27.6, hy - 9 + lag), (31, hy - 11 + lag), (34.6, hy - 10 + lag)], HAIR[0], 4),
                             d.hline(28, round(hy - 5 + lag), 6, HAIR[2])))
    piece(cv, lambda c: c.rect(29, round(hy - 4 + lag), 4, 2, "#ffffff"), ACC, L, 0, 0, 0)       # prendedor
    # braço direito levantado até o painel: ombro → cotovelo pra fora → mão na chave
    t = turn
    hx, hy2 = BACK_HAND
    piece(cv, lambda c: tube(c, [(42, 29 - b), (49.6, 40), (54, 46.6), (hx - 3.6, hy2 + 0.4)], [8, 7, 6.4, 5.8],
                             "#ffffff"), COAT, L, 1, 2, 1, details=lambda d: stroke(d, [(48, 37), (46, 42)], COAT[2], 4))
    piece(cv, lambda c: tube(c, [(hx - 5, hy2 + 0.6), (hx - 2.6, hy2)], [6, 5.6], "#ffffff"), ACC, L, 1, 1, 0)

    def hand(c):
        blob(c, [(hx - 2.4, hy2 - 3 + t * 0.6), (hx + 1.6, hy2 - 3.6 + t * 1.2), (hx + 4, hy2 - 1 + t),
                 (hx + 3.6, hy2 + 2.6), (hx, hy2 + 3.4 - t * 0.4), (hx - 2.6, hy2 + 2)], "#ffffff", 4)
    piece(cv, hand, [SKIN[1], SKIN[2], SKIN[3], SKIN[3]], L, 1, 1, 0,
          details=lambda d: d.line([(hx, hy2 - 1 + round(t)), (hx + 2, hy2 + round(t))], SKIN[3]))
    aa_outline(cv)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# busto · close (1b). Caixa 200×200, perfil pra direita olhando pra baixo na ocular. Desenhado em resolução nativa
# (1 px = 1 px), com feição: pálpebra, íris, sobrancelha, nariz, lábios, queixo.
#   eye   1 = aberto, 0.5 = meio, 0 = fechado, >1 = arregalado (medo)
#   brow  0 = concentração (franzida), 1 = medo contido (miolo da sobrancelha sobe)
#   mouth 0 = fechada, 1 = entreaberta
#   look  deslocamento da íris (micro-sacada), lean = chega perto/afasta da ocular (px), lag = coque/mecha
# ---------------------------------------------------------------------------------------------------------------
BUST = 200
BH = (96, 82)          # centro da cabeça no busto


def bust(eye=1.0, brow=0.0, mouth=0.0, look=0.0, lean=0.0, lag=0.0, b=0.0, light=(1, 1), tilt=0.2):
    cv = Cv(BUST, BUST)
    hx, hy = BH[0] + lean, BH[1] - b * 1.2 + lean * 0.3
    R = lambda pts: rot(pts, tilt, hx, hy)  # noqa: E731
    L = light

    # pescoço: cilindro inclinado, garganta na frente
    piece(cv, lambda c: tube(c, [(80, 146 - b * 1.6), (86, 126), *R([(4, 50)])], [38, 34, 30], "#ffffff", caps=False), SKIN, L,
          2, 5, 2, details=lambda d: (stroke(d, [*R([(26, 52)]), (100, 132), (104, 142 - b)], SKIN[2], 6),
                                      stroke(d, [(70, 120), (74, 138)], SKIN[2], 6)))
    # ombros / jaleco (respiram: sobem com b)
    def coat(c):
        blob(c, [(-6, 206), (2, 172 - b * 1.4), (24, 150 - b * 1.6), (58, 140 - b * 2), (92, 146 - b * 1.6),
                 (124, 158 - b), (150, 180), (164, 206)], "#ffffff", 8)

    def coat_det(d):
        blob(d, [(104, 150 - b), (124, 158 - b), (140, 206), (114, 206)], SUIT[1], 6)              # macacão
        stroke(d, [(102, 150 - b), (110, 176), (116, 206)], COAT[3], 6)                            # lapela
        stroke(d, [(100, 152 - b), (106, 176), (110, 206)], COAT[0], 6)
        stroke(d, [(126, 160 - b), (138, 182), (146, 206)], COAT[3], 6)
        d.rect(118, 176, 8, 14, SUIT[3])                                                         # crachá
        d.rect(120, 179, 4, 2, CYAN)
        d.hline(120, 184, 4, COAT[2])
        stroke(d, [(30, 158 - b), (44, 150 - b * 1.8), (70, 146 - b * 2)], COAT[0], 6)              # luz no ombro
        stroke(d, [(40, 170), (52, 190), (56, 206)], COAT[2], 6)                                    # dobras
        stroke(d, [(16, 182), (24, 206)], COAT[2], 6)
    piece(cv, coat, COAT, L, hi=2, sh=5, deep=2, details=coat_det)
    # gola laranja
    piece(cv, lambda c: blob(c, [(68, 139 - b * 2), (90, 133 - b * 1.6), (108, 139 - b), (112, 146 - b),
                                 (106, 147 - b), (90, 140 - b * 1.6), (72, 146 - b * 2)], "#ffffff", 6), ACC, L, 1, 2, 0,
          details=lambda d: stroke(d, [(72, 140 - b * 2), (90, 135 - b * 1.6), (106, 140 - b)], ACC[0], 6))
    # coque (atrás, com atraso)
    bx, by = R([(-46, -40)])[0]
    by += lag * 2.0
    piece(cv, lambda c: c.ell(round(bx - 21), round(by - 20), round(bx + 19), round(by + 18), "#ffffff"), HAIR, L,
          hi=2, sh=5, deep=2, details=lambda d: (
              stroke(d, [(bx - 14, by - 10), (bx - 2, by - 17), (bx + 12, by - 12)], HAIR[0], 6),
              stroke(d, [(bx - 17, by + 2), (bx - 6, by - 6), (bx + 8, by - 4)], HAIR[0], 6),
              stroke(d, [(bx - 12, by + 12), (bx + 4, by + 8), (bx + 16, by + 2)], HAIR[2], 6)))

    # rosto/crânio
    face = [(-50, -6), (-46, -36), (-26, -56), (0, -62), (24, -55), (39, -40), (45, -22), (46.6, -12), (44.6, -5),
            (47.4, 3), (53, 12), (59, 21), (57.4, 24.6), (51, 26.4), (49.4, 29), (52.4, 33), (50.2, 35.4), (48.8, 36.4),
            (51.4, 39.6), (48.4, 43.6), (46.4, 45), (48, 50.4), (45.4, 55.6), (38, 58), (22, 55), (6, 44),
            (-6, 28), (-22, 22), (-42, 12)]
    def face_det(d):
        P = lambda p: R([p])[0]  # noqa: E731
        # órbita do olho (sombra), maçã do rosto, sulco nasolabial, sombra do maxilar
        blob(d, R([(26, -18), (36, -20), (42, -14), (40, -4), (32, -2), (26, -8)]), SKIN[2], 6)
        stroke(d, R([(46, 24), (45, 29)]), SKIN[2], 4)
        blob(d, R([(-6, 26), (6, 40), (22, 52), (38, 57), (22, 57), (4, 46), (-8, 32)]), SKIN[2], 6)
        # nariz: luz na cana, narina
        stroke(d, R([(46, -4), (50, 6), (55, 18)]), SKIN[0], 6)
        blob(d, R([(48, 21), (52, 21.4), (53, 23.6), (49, 24)]), SKIN[3], 4)
        # lábios
        blob(d, R([(46.6, 30.6), (51.6, 33), (49.6, 35.4), (45.6, 34.6)]), LIP, 4)            # superior
        blob(d, R([(46.4, 37.6), (50.6, 39.4), (48.4, 43), (45.6, 41.6)]), mix(LIP, SKIN[1], 0.3), 4)  # inferior
        if mouth > 0.3:
            stroke(d, R([(44, 35.6), (48.6, 36.2 + mouth), (50, 36.4 + mouth)]), SKIN[3], 4)
            stroke(d, R([(46, 36.8 + mouth * 0.6), (49.6, 37.2 + mouth)]), "#3a1d22", 4)
        else:
            stroke(d, R([(43.4, 35.4), (49.4, 36.4)]), SKIN[3], 4)
        d.px(*map(round, P((43, 35.2))), SKIN[3])                                             # canto da boca
        stroke(d, R([(42, 46), (45, 47.4)]), SKIN[2], 4)                                      # sob o lábio
        stroke(d, R([(40, 52), (44, 54)]), SKIN[0], 4)                                        # luz no queixo
    piece(cv, lambda c: blob(c, R(face), "#ffffff", 8), SKIN, L, hi=2, sh=5, deep=2, details=face_det)

    # olho (pálpebra de cima pesada, íris, branco pequeno, pálpebra de baixo)
    e = eye
    ex, ey = 33.6, -10.4
    open_h = 4.2 * min(e, 1.4)
    if e <= 0.05:
        stroke(cv, R([(28.6, -10.6), (33, -9.2), (37.6, -10.2)]), HAIR[3], 4)
        stroke(cv, R([(29, -9.4), (33, -8)]), SKIN[2], 4)
    else:
        blob(cv, R([(29, -10), (33, -10 - open_h * 0.6), (37.6, -10.6), (34, -10 + open_h * 0.55)]), "#e9e4ea", 4)
        ir = 2.2 if e <= 1.05 else 1.7                                                      # medo: íris menor
        ix, iy = R([(34.4 + look, -10.2)])[0]
        cv.ell(round(ix - ir), round(iy - ir - 0.4), round(ix + ir - 1), round(iy + ir - 1), "#3b2a2e")
        cv.px(round(ix), round(iy - 1), "#eef6ff")                                            # brilho no olho
        # pálpebra de cima (cílios escuros) e de baixo
        stroke(cv, R([(28, -10.4), (31, -10.4 - open_h * 0.75), (35, -10.6 - open_h * 0.7), (38.4, -10.6)]),
               HAIR[3], 4)
        stroke(cv, R([(29.4, -10.4 - open_h * 0.95), (34.6, -10.6 - open_h * 1.05)]), SKIN[2], 4)   # dobra
        stroke(cv, R([(30, -9.6 + open_h * 0.45), (34, -9.8 + open_h * 0.6), (37, -10)]), SKIN[2], 4)
    # sobrancelha: concentração = miolo baixo; medo = miolo sobe e arqueia
    by0 = -20.0
    inner = by0 + 2.2 - brow * 5.4
    mid = by0 - 1.6 - brow * 1.4
    outer = by0 + 0.6 + brow * 0.6
    stroke(cv, R([(22.6, outer), (32, mid), (41.6, inner)]), HAIR[2], 6, w=2)
    stroke(cv, R([(26, outer - 0.6), (32, mid - 0.6)]), HAIR[1], 6)
    if brow > 0.5:                                                                         # ruguinha de preocupação
        stroke(cv, R([(40, inner - 4), (43, inner - 6)]), SKIN[2], 4)

    # cabelo: massa puxada pra trás, linha da testa, costeleta na frente da orelha
    hair = [(-53, -6), (-50, -36), (-28, -60), (2, -66), (28, -56), (38, -44), (30, -43), (16, -38), (6, -28),
            (1, -16), (-1, -4), (-5, 6), (-16, 18), (-34, 22), (-48, 12)]

    def hair_det(d):
        for k in range(6):
            o = k * 6.4
            stroke(d, R([(-46 + o * 0.3, -18 - o), (-26 + o * 0.6, -44 - o * 0.4), (6 + o * 0.6, -58 + o * 0.3)]),
                   HAIR[0] if k % 2 else HAIR[2], 6)
        stroke(d, R([(-42, 10), (-24, 16), (-10, 12)]), HAIR[3], 6)
        stroke(d, R([(14, -46), (28, -52)]), HAIR[0], 6)
    piece(cv, lambda c: blob(c, R(hair), "#ffffff", 8), HAIR, L, hi=2, sh=4, deep=2, details=hair_det)
    # orelha
    piece(cv, lambda c: blob(c, R([(-15, -8), (-6, -12), (-1, -5), (-2, 7), (-6, 12), (-13, 8), (-16, 0)]), "#ffffff",
                             6), SKIN, L, hi=1, sh=3, deep=1, details=lambda d: (
        stroke(d, R([(-11, -8), (-5, -6), (-5, 6)]), SKIN[3], 6), stroke(d, R([(-10, 2), (-7, 6)]), SKIN[2], 4)))
    # prendedor laranja no coque
    piece(cv, lambda c: blob(c, [(bx + 14, by - 12), (bx + 22, by - 10), (bx + 20, by + 4), (bx + 12, by + 2)],
                             "#ffffff", 4), ACC, L, 1, 2, 0)
    # óculos: lente de perfil (lâmina) na frente do olho, aro fino e haste até a orelha
    stroke(cv, R([(42, -14), (12, -12), (-6, -8)]), OUTLINE, 6)
    lens = R([(40.6, -18), (43.6, -18.4), (44.6, -3), (41.6, -2.6)])
    blob(cv, lens, GLASS[2], 4)
    blob(cv, R([(41.6, -16.4), (43, -16.6), (43.6, -10), (42.2, -10)]), GLASS[1], 4)
    cv.px(*map(round, R([(42.4, -15)])[0]), GLASS[0])
    stroke(cv, R([(40.4, -18.6), (43.8, -19), (45, -2.4), (41.4, -2)]), OUTLINE, 4)
    # mecha solta caindo na frente da orelha (atrasa o movimento da cabeça)
    stroke(cv, R([(28, -46), (34 + lag * 1.0, -40), (37 + lag * 1.8, -32), (37 + lag * 2.4, -26)]), HAIR[1], 8, w=2)
    stroke(cv, R([(28, -46), (34 + lag * 1.0, -40), (36 + lag * 1.8, -33)]), HAIR[0], 8)
    aa_outline(cv)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# ciclos de animação prontos (as cenas e a folha usam estes)
# ---------------------------------------------------------------------------------------------------------------
def blink_curve(i, n, at, dur=3):
    """Piscada natural: meio-fechado → fechado → meio-fechado começando no quadro `at`."""
    k = (i - at) % n
    return {0: 0.5, 1: 0.0, 2: 0.5}.get(k, 1.0) if dur == 3 else 1.0


def sit_cycle(n=12, light=(1, 0)):
    return [sit_hunched(phase=i / n, blink=blink_curve(i, n, 8), light=light,
                        focus=ease(breath(i / n, 0.25))) for i in range(n)]


def stand_cycle(n=12, light=(-1, -1)):
    return [stand_side(phase=i / n, blink=blink_curve(i, n, 7), light=light) for i in range(n)]


def back_cycle(n=12, light=(0, -1)):
    return [back_lock(phase=i / n, turn=ease(breath(i / n, 0.3)) * 0.0, droop=ease(breath(i / n, 0.2)) * 0.6,
                      light=light) for i in range(n)]


def bust_cycle(n=12, light=(1, 1)):
    """Concentração: respira, chega 1 px pra ocular e volta, micro-sacada no olho, pisca nos q. 7-9."""
    out = []
    for i in range(n):
        ph = i / n
        b = breath(ph)
        out.append(bust(eye=blink_curve(i, n, 7), brow=0.0, mouth=0.0, look=[0, 0, 0, 0.6, 0.6, 0.6, 0, 0, 0, -0.4,
                                                                            -0.4, 0][i] if n == 12 else 0,
                        lean=ease(breath(ph, 0.05)) * 1.6, lag=(breath(ph, 0.14) - b) * 2, b=b, light=light))
    return out


def bust_reaction(n=10, light=(1, 1)):
    """Medo contido (sem loop): ela afasta o rosto da ocular devagar, os olhos abrem, a sobrancelha sobe, a boca
    entreabre; o coque e a mecha chegam atrasados."""
    out = []
    for i in range(n):
        u = ease(i / (n - 1))
        ul = ease(max(0, (i - 1.6) / (n - 1)))           # o secundário atrasa ~1.5 quadro
        out.append(bust(eye=1.0 + 0.3 * u, brow=u, mouth=ease(max(0, (i - 3) / (n - 4))) * 1.0, look=-0.4 * u,
                        lean=-7 * u, lag=(u - ul) * 6, b=0.4 * u, light=light, tilt=0.2 - 0.1 * u))
    return out
