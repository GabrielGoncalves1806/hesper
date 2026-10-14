"""Dra. Ilves, a cientista da Colônia Hesper (personagem das cutscenes do trailer).

Uma pessoa diferente do Explorador, mas da mesma família visual: contorno #1b1630 por peça, luz em faixas chapadas,
o laranja #e2733a da colônia nos detalhes. Sem capacete: cabelo escuro preso num coque, óculos de aro fino (o reflexo
das lentes é o "olho" dela nas cenas escuras), jaleco branco aberto por cima do macacão azul-acinzentado da colônia,
gola e punhos laranja, crachá com LED ciano, botas escuras.

Todas as poses são desenhadas na luz "neutra"; cada cena aplica relight() (tinta da noite) e rim() (luz de recorte
vinda da fonte da cena: microscópio, porta, monitor).
"""
from __future__ import annotations

from trailer_lib import OUTLINE, Cv, part

COAT = ["#f1ece2", "#d6cec4", "#aaa0a0", "#7b707c"]
SUIT = ["#7f8aab", "#5d6789", "#454d6c", "#323850"]
ACC = ["#f4a06a", "#e2733a", "#a9482a"]
SKIN = ["#f0c3a0", "#d99c7a", "#b2725a", "#80503f"]
HAIR = ["#6e4a52", "#4b3038", "#35212a", "#26171e"]
BOOT = ["#5f586e", "#3f3a4c", "#2f2a3a"]
GLASS = ["#eef6ff", "#a6ecff", "#59d0e6"]
CYAN = "#59d0e6"

W, H = 48, 84      # caixa das poses de corpo inteiro; pé na linha 81


# ---------------------------------------------------------------------------------------------------------------
# cabeça de perfil (olhando pra direita). (x, y) = canto de cima-esquerda da caixa 22×22 da cabeça.
# look: "fwd" ou "down" (olhando pra baixo, no microscópio). blink: olho fechado.
# ---------------------------------------------------------------------------------------------------------------
def head_side(cv, x, y, look="fwd", blink=False, glasses=True):
    def skull(c):
        c.ell(x + 2, y + 1, x + 19, y + 19, SKIN[1])                      # crânio
        c.poly([(x + 12, y + 8), (x + 20, y + 8), (x + 21, y + 13), (x + 22, y + 15),     # rosto: testa, nariz
                (x + 20, y + 16), (x + 20, y + 19), (x + 18, y + 21), (x + 12, y + 21)], SKIN[1])
        c.rect(x + 12, y + 18, 3, 4, SKIN[2])                              # sombra do queixo/maxilar
        c.poly([(x + 9, y + 17), (x + 15, y + 21), (x + 9, y + 21)], SKIN[2])
        c.px(x + 21, y + 14, SKIN[0])                                      # luz na ponta do nariz
        c.hline(x + 16, y + 9, 4, SKIN[0])                                 # testa
        c.px(x + 19, y + 18, SKIN[3])                                      # boca
        c.px(x + 18, y + 18, SKIN[2])
    part(cv, skull)

    def hair(c):
        # massa do cabelo puxado pra trás, linha da testa em x+15
        c.ell(x + 1, y, x + 18, y + 14, HAIR[1])
        c.poly([(x + 2, y + 6), (x + 8, y + 4), (x + 9, y + 17), (x + 3, y + 15)], HAIR[1])
        c.poly([(x + 9, y + 1), (x + 17, y + 3), (x + 19, y + 7), (x + 14, y + 7)], HAIR[1])
        # mechas em faixas
        c.line([(x + 6, y + 3), (x + 14, y + 2)], HAIR[0])
        c.line([(x + 4, y + 6), (x + 11, y + 4)], HAIR[0])
        c.line([(x + 3, y + 10), (x + 8, y + 7)], HAIR[2])
        c.line([(x + 3, y + 13), (x + 7, y + 11)], HAIR[2])
        c.hline(x + 4, y + 14, 4, HAIR[3])
        c.px(x + 16, y + 4, HAIR[0])
        # coque atrás
        c.ell(x - 4, y + 2, x + 4, y + 10, HAIR[1])
        c.line([(x - 3, y + 4), (x + 1, y + 3)], HAIR[0])
        c.hline(x - 2, y + 8, 4, HAIR[2])
        c.rect(x + 2, y + 5, 2, 3, ACC[1])                                 # prendedor laranja
    part(cv, hair)

    def ear(c):
        c.ell(x + 8, y + 9, x + 11, y + 14, SKIN[1])
        c.px(x + 9, y + 11, SKIN[2])
        c.px(x + 9, y + 12, SKIN[2])
    part(cv, ear)

    def face(c):
        ey = y + 12 if look == "fwd" else y + 13
        if blink:
            c.hline(x + 16, ey + 1, 2, SKIN[3])
        else:
            c.px(x + 17, ey, OUTLINE)
            c.px(x + 17, ey + 1, OUTLINE)
            c.px(x + 16, ey, "#ffffff")
        c.hline(x + 16, y + 10, 3, HAIR[2])                                # sobrancelha
        if glasses:
            c.rect(x + 15, y + 11, 5, 4, None or GLASS[2])
            c.rect(x + 16, y + 12, 3, 2, GLASS[1])
            c.px(x + 16, y + 12, GLASS[0])
            c.line([(x + 10, y + 11), (x + 15, y + 12)], OUTLINE)          # haste
            c.px(x + 15, y + 11, OUTLINE)
            c.hline(x + 15, y + 15, 5, OUTLINE)
    face(cv)


# ---------------------------------------------------------------------------------------------------------------
# pose 1: em pé de perfil, olhando pra direita
# ---------------------------------------------------------------------------------------------------------------
def stand_side(blink=False, breath=0):
    cv = Cv(W, H)
    b = breath
    ox = 10

    def leg_back(c):
        c.poly([(ox + 9, 60), (ox + 16, 60), (ox + 15, 76), (ox + 9, 76)], SUIT[2])
        c.rect(ox + 8, 75, 9, 6, BOOT[1])
        c.hline(ox + 8, 80, 10, BOOT[2])
    part(cv, leg_back)

    def leg_front(c):
        c.poly([(ox + 14, 60), (ox + 21, 60), (ox + 21, 76), (ox + 15, 76)], SUIT[1])
        c.vline(ox + 20, 61, 15, SUIT[2])
        c.hline(ox + 15, 68, 6, SUIT[2])                                   # joelho
        c.rect(ox + 14, 75, 11, 6, BOOT[0])
        c.hline(ox + 14, 80, 11, BOOT[2])
        c.rect(ox + 22, 77, 3, 3, BOOT[1])
        c.hline(ox + 15, 76, 4, ACC[2])                                    # faixa laranja da bota
    part(cv, leg_front)

    def body(c):
        # macacão por baixo (aparece na frente, entre as abas do jaleco)
        c.poly([(ox + 9, 27 + b), (ox + 23, 27 + b), (ox + 24, 60), (ox + 9, 60)], SUIT[1])
        # jaleco: costas retas, aba da frente aberta
        c.poly([(ox + 5, 28 + b), (ox + 19, 26 + b), (ox + 21, 40), (ox + 22, 64), (ox + 3, 65), (ox + 4, 44)], COAT[1])
        c.poly([(ox + 3, 52), (ox + 6, 30 + b), (ox + 8, 30 + b), (ox + 7, 64), (ox + 3, 65)], COAT[2])   # costas na sombra
        c.poly([(ox + 21, 30 + b), (ox + 25, 33 + b), (ox + 26, 64), (ox + 21, 64)], COAT[1])          # aba da frente
        c.vline(ox + 21, 32 + b, 32, COAT[2])                                # dobra da aba
        c.vline(ox + 25, 36, 28, COAT[2])
        c.hline(ox + 4, 64, 22, COAT[3])                                     # barra
        c.line([(ox + 10, 30 + b), (ox + 16, 28 + b)], COAT[0])              # ombro com luz
        c.hline(ox + 22, 46, 3, COAT[3])                                     # bolso
        c.rect(ox + 22, 34 + b, 2, 4, SUIT[3])                               # crachá
        c.px(ox + 22, 35 + b, CYAN)
        # gola laranja do macacão
        c.poly([(ox + 14, 25 + b), (ox + 22, 25 + b), (ox + 23, 29 + b), (ox + 15, 29 + b)], ACC[1])
        c.hline(ox + 15, 25 + b, 6, ACC[0])
    part(cv, body)

    def arm(c):
        # braço caído na frente do corpo, manga do jaleco
        c.poly([(ox + 11, 29 + b), (ox + 18, 29 + b), (ox + 19, 44), (ox + 18, 53), (ox + 12, 53), (ox + 11, 44)], COAT[1])
        c.poly([(ox + 11, 31 + b), (ox + 13, 31 + b), (ox + 13, 53), (ox + 12, 53), (ox + 11, 44)], COAT[2])
        c.vline(ox + 18, 34 + b, 18, COAT[2])
        c.hline(ox + 12, 41, 5, COAT[2])                                     # dobra do cotovelo
        c.rect(ox + 12, 53, 7, 2, ACC[1])                                    # punho laranja do macacão
        c.ell(ox + 12, 54, ox + 18, 60, SKIN[1])                             # mão
        c.hline(ox + 13, 59, 4, SKIN[2])
        c.px(ox + 17, 56, SKIN[0])
    part(cv, arm)

    def neck(c):
        c.rect(ox + 13, 21 + b, 6, 6, SKIN[2])
    part(cv, neck)
    head_side(cv, ox + 2, 3 + b, blink=blink)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# pose 2: sentada no banco, curvada no microscópio (perfil pra direita). Caixa 64×76, pé na linha 74.
# As mãos ficam nos botões de foco (x≈50..56, y≈40). lean: 0/1 (respira chegando o rosto 1 px pra lente).
# ---------------------------------------------------------------------------------------------------------------
SIT_W, SIT_H = 64, 76


def sit_hunched(lean=0, blink=False, hand=0):
    cv = Cv(SIT_W, SIT_H)
    L = lean

    def stool(c):
        c.rect(10, 50, 20, 4, BOOT[1])
        c.hline(10, 50, 20, BOOT[0])
        c.rect(18, 54, 4, 16, "#4a4458")
        c.poly([(12, 72), (28, 72), (26, 70), (14, 70)], "#4a4458")
        c.hline(11, 73, 18, "#3a3546")
    part(cv, stool)

    def legs(c):
        # coxa horizontal pro banco da frente, canela pra baixo
        c.poly([(14, 42), (36, 43), (37, 50), (14, 50)], SUIT[1])
        c.hline(16, 49, 20, SUIT[2])
        c.poly([(31, 45), (38, 44), (39, 69), (33, 69)], SUIT[1])
        c.vline(38, 48, 21, SUIT[2])
        c.rect(31, 68, 11, 6, BOOT[0])
        c.hline(31, 73, 11, BOOT[2])
        c.hline(32, 69, 4, ACC[2])
    part(cv, legs)

    def body(c):
        # tronco inclinado ~35°: quadril em (16..30, 48), ombro em (26..42, 22)
        c.poly([(14, 49), (30, 49), (44, 26 + L), (40, 20 + L), (28, 18 + L), (14, 36)], COAT[1])
        c.poly([(14, 49), (20, 49), (30, 20 + L), (28, 18 + L), (14, 36)], COAT[2])        # costas na sombra
        c.line([(29, 19 + L), (40, 21 + L)], COAT[0])
        # barra do jaleco caindo atrás do banco
        c.poly([(12, 42), (19, 46), (18, 59), (8, 59)], COAT[2])
        c.hline(8, 59, 11, COAT[3])
        c.vline(13, 47, 11, COAT[3])
        # macacão na frente (peito)
        c.poly([(38, 25 + L), (44, 27 + L), (34, 45), (30, 45)], SUIT[1])
        c.poly([(40, 21 + L), (46, 23 + L), (45, 27 + L), (40, 26 + L)], ACC[1])          # gola
    part(cv, body)

    def arm(c):
        # braço da frente: ombro (34,26) → cotovelo (40,38) → mão no botão de foco (52,38+hand)
        c.poly([(31, 24 + L), (38, 23 + L), (43, 36), (40, 40), (35, 38)], COAT[1])
        c.poly([(31, 24 + L), (33, 24 + L), (37, 39), (35, 38)], COAT[2])
        c.poly([(39, 34), (50, 34 + hand), (50, 39 + hand), (40, 40)], COAT[1])
        c.hline(41, 39, 9, COAT[2])
        c.rect(48, 34 + hand, 2, 5, ACC[1])
        c.ell(50, 33 + hand, 55, 39 + hand, SKIN[1])
        c.px(54, 35 + hand, SKIN[0])
        c.hline(51, 38 + hand, 3, SKIN[2])
    part(cv, arm)

    def neck(c):
        c.poly([(38, 20 + L), (44, 18 + L), (46, 23 + L), (41, 24 + L)], SKIN[2])
    part(cv, neck)
    head_side(cv, 34 + L, 1 + L, look="down", blink=blink)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# pose 3: de costas, braço direito levantado na fechadura (cena 3). Caixa 48×84, pé na linha 81.
# turn: 0..3 = a mão girando a chave (o pulso gira; a chave muda de ângulo).
# ---------------------------------------------------------------------------------------------------------------
def back_lock(turn=0, breath=0):
    cv = Cv(W, H)
    b = breath

    def legs(c):
        for x0 in (15, 24):
            c.poly([(x0, 60), (x0 + 8, 60), (x0 + 7, 76), (x0 + 1, 76)], SUIT[1] if x0 == 15 else SUIT[2])
            c.rect(x0, 75, 8, 6, BOOT[1])
            c.hline(x0, 80, 8, BOOT[2])
    part(cv, legs)

    def arm_l(c):
        c.poly([(11, 30 + b), (16, 29 + b), (17, 52), (12, 53)], COAT[2])
        c.rect(11, 52, 6, 2, ACC[2])
        c.ell(11, 53, 16, 59, SKIN[2])
    part(cv, arm_l)

    def body(c):
        c.poly([(14, 26 + b), (34, 26 + b), (37, 33 + b), (37, 64), (11, 64), (11, 33 + b)], COAT[1])
        c.poly([(27, 30 + b), (37, 33 + b), (37, 64), (29, 64)], COAT[2])                    # lado na sombra
        c.vline(24, 40, 24, COAT[2])                                                          # costura das costas
        c.hline(16, 46, 18, COAT[2])                                                          # martingale
        c.rect(22, 45, 5, 3, COAT[0])
        c.px(24, 46, COAT[3])
        c.hline(11, 64, 27, COAT[3])
        c.line([(15, 27 + b), (25, 26 + b)], COAT[0])
        c.poly([(18, 23 + b), (30, 23 + b), (31, 27 + b), (17, 27 + b)], ACC[1])            # gola
    part(cv, body)

    def neck(c):
        c.rect(20, 18 + b, 8, 6, SKIN[2])
    part(cv, neck)

    def head(c):
        c.ell(13, 1 + b, 34, 22 + b, HAIR[1])
        c.line([(16, 6 + b), (22, 2 + b)], HAIR[0])
        c.line([(18, 9 + b), (25, 4 + b)], HAIR[0])
        c.line([(27, 4 + b), (32, 10 + b)], HAIR[2])
        c.line([(29, 12 + b), (33, 16 + b)], HAIR[2])
        c.hline(18, 21 + b, 12, HAIR[3])
        c.ell(11, 10 + b, 14, 15 + b, SKIN[2])                                               # orelhas
        c.ell(33, 10 + b, 36, 15 + b, SKIN[3])
    part(cv, head)

    def bun(c):
        c.ell(19, 5 + b, 29, 14 + b, HAIR[1])
        c.line([(21, 7 + b), (25, 6 + b)], HAIR[0])
        c.hline(21, 12 + b, 6, HAIR[2])
        c.rect(22, 14 + b, 4, 2, ACC[1])
    part(cv, bun)
    # hastes dos óculos atrás da orelha
    cv.px(13, 10 + b, OUTLINE)
    cv.px(34, 10 + b, OUTLINE)

    def arm_r(c):
        # braço direito levantado pra frente/direita (pra fechadura): ombro (33,29) → mão (42,34)
        c.poly([(31, 28 + b), (37, 28 + b), (43, 33), (41, 38), (34, 35)], COAT[2])
        c.hline(36, 35, 5, COAT[3])
        c.rect(40, 31, 2, 6, ACC[2])
        c.ell(41, 30, 46, 37, SKIN[2])
        c.px(44, 31, SKIN[1])
    part(cv, arm_r)
    return cv


# ---------------------------------------------------------------------------------------------------------------
# busto (close): perfil pra direita, olhando pra baixo na ocular. Caixa 96×96. Mais detalhe: o dobro da escala.
# ---------------------------------------------------------------------------------------------------------------
BUST = 96


class Scaled:
    """Proxy que desenha as mesmas primitivas numa escala maior, mas rasterizando em 1:1 (bordas em pixel real)."""

    def __init__(self, c, s):
        self.c, self.s = c, s

    def _p(self, pts):
        return [(x * self.s, y * self.s) for x, y in pts]

    def poly(self, pts, col):
        self.c.poly(self._p(pts), col)

    def ell(self, x0, y0, x1, y1, col):
        s = self.s
        self.c.ell(round(x0 * s), round(y0 * s), round(x1 * s + s - 1), round(y1 * s + s - 1), col)

    def line(self, pts, col, w=1):
        self.c.line(self._p(pts), col, max(1, round(w * self.s * 0.75)))

    def rect(self, x, y, w, h, col):
        s = self.s
        self.c.rect(round(x * s), round(y * s), round(w * s), round(h * s), col)

    def px(self, x, y, col):
        self.rect(x, y, 1, 1, col)

    def hline(self, x, y, w, col):
        self.rect(x, y, w, 1, col)

    def vline(self, x, y, h, col):
        self.rect(x, y, 1, h, col)


def bust(blink=False, look="down", lean=0, scale=2):
    cv = Cv(BUST * scale, BUST * scale)
    raw = cv

    def spart(c0, draw):
        part(c0, lambda c: draw(Scaled(c, scale)))
    L = lean

    def shoulders(c):
        c.poly([(4, 96), (6, 70), (16, 60), (40, 56 + L), (62, 60 + L), (78, 72), (84, 96)], COAT[1])
        c.poly([(4, 96), (6, 70), (16, 60), (26, 58), (22, 96)], COAT[2])
        c.line([(18, 60), (40, 56 + L)], COAT[0])
        c.line([(42, 57 + L), (60, 60 + L)], COAT[0])
        # lapela do jaleco + macacão
        c.poly([(58, 62 + L), (70, 66), (78, 96), (62, 96)], SUIT[1])
        c.poly([(56, 60 + L), (63, 62 + L), (66, 96), (60, 96), (57, 72)], COAT[1])
        c.line([(57, 63 + L), (61, 96)], COAT[2])
        c.poly([(70, 66), (75, 68), (82, 96), (78, 96)], COAT[1])
        c.rect(66, 76, 4, 8, SUIT[3])                                    # crachá
        c.px(67, 78, CYAN)
        c.px(68, 78, CYAN)
        c.hline(67, 81, 2, COAT[2])
    spart(cv, shoulders)

    def collar(c):
        c.poly([(50, 54 + L), (64, 56 + L), (70, 64), (56, 64)], ACC[1])
        c.line([(52, 55 + L), (64, 57 + L)], ACC[0])
        c.hline(57, 63, 12, ACC[2])
    spart(cv, collar)

    def neck(c):
        c.poly([(44, 44 + L), (60, 44 + L), (62, 58 + L), (48, 58 + L)], SKIN[2])
        c.line([(52, 48 + L), (60, 56 + L)], SKIN[3])
    spart(cv, neck)

    # cabeça 2× (x 20..84, y 2..58)
    def skull(c):
        c.ell(22, 4 + L, 66, 50 + L, SKIN[1])
        f = [(50, 20), (72, 22), (74, 30), (76, 33), (81, 39), (80, 41), (76, 42), (76, 44), (75, 46), (76, 47),
             (73, 50), (74, 53), (71, 56), (62, 58), (50, 56)]
        c.poly([(x, y + L) for x, y in f], SKIN[1])
        # sombra embaixo do maxilar (a luz vem da ocular, de baixo-direita: o rim faz o resto)
        c.poly([(x, y + L) for x, y in [(30, 40), (44, 46), (56, 56), (62, 58), (50, 58), (34, 48)]], SKIN[2])
        c.line([(70, 24 + L), (74, 30 + L)], SKIN[0])                  # testa e nariz com luz
        c.line([(76, 34 + L), (80, 39 + L)], SKIN[0])
        c.px(77, 41 + L, SKIN[3])                                        # narina
        c.line([(72, 45 + L), (75, 45 + L)], SKIN[3])                  # boca
        c.line([(66, 40 + L), (69, 37 + L)], SKIN[2])                  # bochecha
        c.line([(70, 52 + L), (72, 51 + L)], SKIN[2])                  # queixo
    spart(cv, skull)

    def hair(c):
        c.ell(20, 0 + L, 66, 32 + L, HAIR[1])
        c.poly([(22, 12 + L), (36, 8 + L), (38, 40 + L), (26, 36 + L)], HAIR[1])
        c.poly([(40, 2 + L), (62, 6 + L), (70, 18 + L), (58, 18 + L)], HAIR[1])
        for i, (a, bb, col) in enumerate([((28, 6), (52, 2), HAIR[0]), ((24, 12), (44, 6), HAIR[0]),
                                          ((22, 20), (36, 12), HAIR[2]), ((24, 28), (34, 20), HAIR[2]),
                                          ((46, 4), (64, 10), HAIR[0]), ((50, 9), (66, 15), HAIR[2])]):
            c.line([(a[0], a[1] + L), (bb[0], bb[1] + L)], col)
        c.line([(26, 34 + L), (36, 38 + L)], HAIR[3])
        c.px(60, 8 + L, "#8a6670")
        # coque
        c.ell(8, 4 + L, 28, 24 + L, HAIR[1])
        c.line([(11, 9 + L), (20, 6 + L)], HAIR[0])
        c.line([(10, 15 + L), (17, 11 + L)], HAIR[0])
        c.line([(12, 21 + L), (24, 20 + L)], HAIR[2])
        c.rect(24, 10 + L, 4, 8, ACC[1])
        c.vline(24, 10 + L, 8, ACC[0])
    spart(cv, hair)

    def ear(c):
        c.ell(36, 24 + L, 44, 36 + L, SKIN[1])
        c.line([(39, 28 + L), (40, 33 + L)], SKIN[3])
    spart(cv, ear)

    # olho + óculos
    cv = Scaled(raw, scale)
    ey = 30 + L if look == "down" else 28 + L
    if blink:
        cv.line([(64, ey + 1), (68, ey + 2)], SKIN[3])
    else:
        cv.rect(65, ey, 3, 3, OUTLINE)
        cv.px(65, ey, "#ffffff")
        cv.line([(64, ey + 3), (67, ey + 3)], SKIN[2])
    cv.line([(62, 24 + L), (69, 25 + L)], HAIR[2])                     # sobrancelha
    cv.line([(62, 25 + L), (69, 26 + L)], HAIR[3])
    # lente (de perfil vira uma lâmina inclinada) + haste
    cv.poly([(69, 24 + L), (72, 24 + L), (73, 35 + L), (70, 35 + L)], GLASS[2])
    cv.poly([(70, 26 + L), (71, 26 + L), (72, 33 + L), (71, 33 + L)], GLASS[1])
    cv.vline(71, 27 + L, 2, GLASS[0])
    cv.line([(42, 26 + L), (69, 25 + L)], OUTLINE)
    cv.line([(69, 23 + L), (72, 23 + L)], OUTLINE)
    cv.line([(70, 36 + L), (73, 36 + L)], OUTLINE)
    return raw
