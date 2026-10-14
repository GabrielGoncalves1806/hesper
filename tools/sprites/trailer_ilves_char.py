"""Dra. Ilves · v1.2 · desenhada À MÃO em grade de pixels (mapas de caracteres), montada como rig (igual ao Explorador).

Cada peça é uma lista de strings; cada caractere é uma cor da paleta curta abaixo ('.' = vazio). O contorno 'o' já
vem desenhado no mapa (controle total do pixel, sem contorno automático). As poses montam as peças com offsets.

Direção (inspiração, sem copiar): cientista intensa e meio desleixada, alta e esguia, postura curvada e curiosa,
cabelo castanho num rabo de cavalo alto e bagunçado com mechas soltas caindo no rosto, goggles de laboratório
empurrados na testa, jaleco aberto por cima do uniforme azul-acinzentado da Colônia Hesper com a gola laranja.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

PAL = {
    "o": "#1b1630",                                   # contorno
    "S": "#f6cfae", "s": "#dfa27f", "d": "#b06f58",   # pele (3)
    "H": "#a0694a", "h": "#6e4330", "k": "#43271d",   # cabelo castanho (3)
    "W": "#f4efe6", "w": "#cfc6c4", "c": "#958a98",   # jaleco (3)
    "U": "#6a7494", "u": "#464e6c",                   # uniforme (2)
    "A": "#e2733a",                                   # laranja da colônia
    "m": "#8a8aa0", "G": "#a6ecff", "g": "#4fb3d6",   # goggles: aro, lente, lente funda
    "B": "#4a4458", "b": "#2e2a3a",                   # botas / banco
    "e": "#ffffff",                                   # brilho do olho
    "r": "#b05a52",                                   # boca
    "i": "#3a2a24",                                   # íris
    "C": "#59d0e6",                                   # LED ciano do crachá
    "Y": "#f2c46d", "y": "#a5582c",                   # a chave (latão)
}


def rgba(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


class Sprite:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def put(self, rows, ox=0, oy=0, flip=False):
        for y, row in enumerate(rows):
            if flip:
                row = row[::-1]
            for x, ch in enumerate(row):
                if ch == "." or ch == " ":
                    continue
                X, Y = ox + x, oy + y
                if 0 <= X < self.w and 0 <= Y < self.h:
                    self.a[Y, X] = rgba(PAL[ch])
        return self

    def image(self):
        return Image.fromarray(self.a.copy())


def check(rows, name):
    w = max(len(r) for r in rows)
    return [r.ljust(w, ".") for r in rows]


# =================================================================================================================
# POSE 1 · sentada e curvada no microscópio (perfil pra direita). Caixa 44×48, chão na linha 47.
# =================================================================================================================
SIT_W, SIT_H, SIT_FOOT = 44, 48, 47
SIT_BENCH = 26          # tampo da bancada (o antebraço apoia aqui)
SIT_EYE = (32, 11)      # logo na frente do olho (onde a ocular encosta), com a cabeça baixa

STOOL = check([
    ".oooooooooooo.",
    "oBBBBBBBBBBBBo",
    "obbbbbbbbbbbbo",
    ".oooooooooooo.",
    ".....obbo.....",
    ".....obbo.....",
    ".....obbo.....",
    ".....obbo.....",
    ".....obbo.....",
    ".....obbo.....",
    ".....obbo.....",
    "...oobbbboo...",
    "..obbbbbbbbo..",
    ".oooooooooooo.",
], "STOOL")

LEGS = check([
    "..ooooooooooooo....",
    ".oUUUUUUUUUUUUUo...",
    "oUUUUUUUUUUUUUUUo..",
    "oUUUUUUUUUUUUUUUo..",
    "ouuuuuuuuuuuuUUUo..",
    ".ooooooooooooUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oUUuo..",
    "............oAAAo..",
    "...........oBBBBoo.",
    "...........oBBBBBBo",
    "...........obbbbbbo",
    "...........oooooooo",
], "LEGS")

# tronco curvado (jaleco), 2 respirações: 0 = solta o ar, 1 = enche (ombro/costas sobem 1 px)
TORSO = [check([
    "...........oooooo.....",
    ".........ooWWWWWWoAo..",
    "........oWWWWWWWWoAAo.",
    ".......oWWWWWWWWwoUUo.",
    "......owWWWWWWWwwoUUo.",
    "......owWWWWWWwwwoUUo.",
    ".....owwWWWWWwwwwoUUo.",
    ".....owwWWWWwwwwwoUCo.",
    "....ocwwWWWwwwwwoUUo..",
    "....ocwwWWwwwwwwoUUo..",
    "...ocwwWWwwwwwwwoUo...",
    "...ocwwWwwwwwwwoUUo...",
    "..occwwwwwwwwwwoUo....",
    "..occwwwwwwwwwwwoo....",
    "..occwwwwwwwwwwwo.....",
    ".occwwwwwwwwwwwo......",
    ".occwwwwwwwwwwo.......",
    ".occwwwwwwwwwo........",
    ".occwwwwwwwwo.........",
    ".occwwwwwwwo..........",
    ".occwwwwwwo...........",
    ".occwwwwwo............",
    ".occwcwwwo............",
    ".occwcwwwo............",
    ".occwcwwo.............",
    "..occcwwo.............",
    "...ooooo..............",
], "TORSO0")]
TORSO.append(check([
    "............ooooo.....",
    "..........ooWWWWWoAo..",
    "........ooWWWWWWWoAAo.",
    ".......oWWWWWWWWwoUUo.",
    "......owWWWWWWWwwoUUo.",
    "......owWWWWWWwwwoUUo.",
    ".....owwWWWWWwwwwoUUo.",
    ".....owwWWWWwwwwwoUCo.",
    "....ocwwWWWwwwwwoUUo..",
    "....ocwwWWwwwwwwoUUo..",
    "...ocwwWWwwwwwwwoUo...",
    "...ocwwWwwwwwwwoUUo...",
    "..occwwwwwwwwwwoUo....",
    "..occwwwwwwwwwwwoo....",
    "..occwwwwwwwwwwwo.....",
    ".occwwwwwwwwwwwo......",
    ".occwwwwwwwwwwo.......",
    ".occwwwwwwwwwo........",
    ".occwwwwwwwwo.........",
    ".occwwwwwwwo..........",
    ".occwwwwwwo...........",
    ".occwwwwwo............",
    ".occwcwwwo............",
    ".occwcwwwo............",
    ".occwcwwo.............",
    "..occcwwo.............",
    "...ooooo..............",
], "TORSO1"))

# braço da frente: ombro → cotovelo apoiado → mão no foco. 2 quadros de mão (gira o botão)
ARM = [check([
    ".oo................",
    "oWWo...............",
    "oWWwo..............",
    ".oWWwo.............",
    ".oWWwo.............",
    "..oWwwo............",
    "..oWwwo.......oo...",
    "..oWwwoooooooAoSSo.",
    "...oWwwWWWWwwAoSSSo",
    "...owwwwwwwwwAosSdo",
    "....ooooooooooo.oo.",
], "ARM0"), check([
    ".oo................",
    "oWWo...............",
    "oWWwo..............",
    ".oWWwo.............",
    ".oWWwo.............",
    "..oWwwo............",
    "..oWwwo............",
    "..oWwwoooooooAooSo.",
    "...oWwwWWWWwwAoSSSo",
    "...owwwwwwwwwAosSdo",
    "....ooooooooooo.oo.",
], "ARM1")]

# cabeça de perfil olhando pra baixo, na ocular (goggles empurrados na testa, franja caindo no rosto)
HEAD_DOWN = check([
    "....oooooo....",
    "..ookhhhHHoo..",
    ".okhhhhhhHHHo.",
    ".ohhkhmmmmmGGo",
    "okhhkmmmmmmggo",
    "okhhhhhhhkhSSo",
    "okhhhhhhkSkSSo",
    "okhhhhhsskiSSo",
    ".okhhhdsSSSSSSo",
    ".okkhddsSSSSso",
    "..okkdsssSrso.",
    "...oodsssso...",
    ".....oooo.....",
], "HEAD_DOWN")


HEAD_DOWN_BLINK = [r.replace("i", "d") if i == 7 else r for i, r in enumerate(HEAD_DOWN)]

# cabeça levantada, assustada: olho arregalado (branco + íris), boca entreaberta
HEAD_UP = check([
    "....oooooo....",
    "..ookhhhHHoo..",
    ".okhhhhhhHHHo.",
    ".ohhkhmmmmmGGo",
    "okhhkmmmmmmggo",
    "okhhhhhhkhSSSo",
    "okhhhhhkSeiSSo",
    "okhhhhhsSSdSSSo",
    ".okhhhdsSSSSSo.",
    ".okkhddsSSSSro.",
    "..okkdsssSSso..",
    "...oodssssso...",
    ".....ooooo.....",
], "HEAD_UP")

# rabo de cavalo alto e bagunçado, preso no alto da cabeça (elástico laranja); 3 posições pro atraso
PONY = [check([
    "......ooo..",
    "....oohHHo.",
    "...okhhHHAo",
    "..okhhkhhAo",
    ".okhhko.oo.",
    ".okhko.....",
    "okhhko.....",
    "okhko......",
    "okhko......",
    ".okhko.....",
    ".okko......",
    "..oko......",
    "..o.ko.....",
    "....o......",
], "PONY0"), check([
    ".....ooo...",
    "...oohHHoo.",
    "..okhhHHHAo",
    ".okhhkkhhAo",
    "okhhko.ooo.",
    "okhko......",
    "okhko......",
    "okhko......",
    ".okhko.....",
    ".okhko.....",
    "..okko.....",
    "..oko......",
    "...o.ko....",
    ".....o.....",
], "PONY1"), check([
    ".......ooo.",
    ".....oohHHo",
    "....okhhHAo",
    "...okhhkhAo",
    "..okhhko.o.",
    "..okhko....",
    ".okhhko....",
    ".okhko.....",
    ".okhko.....",
    "..okhko....",
    "..okko.....",
    "...oko.....",
    "...o.ko....",
    ".....o.....",
], "PONY2")]


def sit(breath=0, hand=0, head=None, pony=0, hx=0, hy=0, arm_dy=None):
    s = Sprite(SIT_W, SIT_H)
    s.put(PONY[pony], 12 + hx, 1 + hy)
    s.put(TORSO[breath], 3, 12)
    s.put(STOOL, 3, 34)
    s.put(LEGS, 8, 26)
    s.put(head or HEAD_DOWN, 21 + hx, 4 + hy)
    s.put(ARM[hand], 13, 14 + (1 - breath) if arm_dy is None else 14 + arm_dy)
    return s


# loop de 8 q.: respira (ombro sobe), a mão gira o foco, o rabo de cavalo atrasa a respiração, pisca no q. 6
SIT_LOOP = [dict(breath=b, hand=h, pony=p, head=(HEAD_DOWN_BLINK if i == 6 else HEAD_DOWN))
            for i, (b, h, p) in enumerate([(0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 1, 2), (1, 1, 2), (1, 0, 2),
                                           (0, 0, 0), (0, 0, 1)])]
# susto (6 q., sem loop): ela tira o olho da ocular e levanta a cabeça; o rabo de cavalo chega depois
SIT_STARTLE = [dict(breath=0, hand=0, pony=0, head=HEAD_DOWN),
               dict(breath=1, hand=1, pony=0, head=HEAD_DOWN, hx=-1, hy=-1),
               dict(breath=1, hand=1, pony=2, head=HEAD_UP, hx=-2, hy=-3),
               dict(breath=1, hand=1, pony=1, head=HEAD_UP, hx=-2, hy=-3),
               dict(breath=1, hand=1, pony=0, head=HEAD_UP, hx=-2, hy=-3),
               dict(breath=1, hand=1, pony=0, head=HEAD_UP, hx=-2, hy=-3)]


def sit_frames(seq):
    return [sit(**f) for f in seq]


# =================================================================================================================
# RETRATO 64×64 · estilo retrato de diálogo de RPG, rosto 3/4 pra direita. Base = expressão neutra; as expressões
# são sobreposições pequenas (olhos, sobrancelhas, boca) desenhadas pixel a pixel.
# =================================================================================================================
PORTRAIT = check([
    ".............ookhhHHho..........................................",
    "...........ookhhHhhHHo..........................................",
    "..........okhhHHhhkkHHo.........................................",
    ".........okhhHhhkkhHHHHoo.......................................",
    "........okhhHhkkhHHhhHHoho......................................",
    ".......okhhHhkhhHhhhkkoho.......................................",
    "......okhhHhkhhHhhkkoooo........................................",
    ".....okhhhhkhhHhkkooAAAooooooooooooo............................",
    ".....okhhhkhhHhkHo..oAAohhhkhhhhHHhhooo.........................",
    "....okhhhkhhhhkHo..oohkhhhhkhHHHHkHHHhhoo.......................",
    "....okhhhkhhhkHo..ohkhkhhhhkhhhHHkHHHHHhho......................",
    "...okhhhkhhhhkHo.ohkhhkhhmmmmmhhHkHHHmmmhho.....................",
    "..ookhhhkhhhkHo.ohkhhhkhmGGGGGmhhHHmmGGGmmho....................",
    ".ohokhhhkhhhkHoohkhhhhkmGGeGGGGmhhhmGeGGGmhho...................",
    "ohokhhhkhhhhkHohkhhhhhmGGGGGGGGGmhmGGGGGGGmho...................",
    ".ookhhhkhhhkhHHhkhhhhhmGGGGGGGGGmhmGGGGGGGmhho..................",
    "..ookhhkhhhkHHommmmmmmmGGGGGGGGGmmmGGGGGGGmmmo..................",
    ".ohokhhkhhhkHoouuuuuuuumgggggggmuuumgggggmuuuo..................",
    "..ookhhkhhkHHoohkhhhhhhhmhggggmhhhhmhgggmhhhho..................",
    "...ookhkhhkHHoohkhhhhhhhhhmmmmhhhhhhhmmmhhhhho..................",
    "..ohokhhkhHHo.ohhhhSSkkSSkSSSSSkkSSSkSSSSkkSSo..................",
    "...oookhkhHHo.ohhhhSSkkSSkSSSSSkkSSSSSSSSkkSSo..................",
    "...ohokhhHHo..ohhhhSSkkSSkSSSSSkSSSSSSSSSkkSSo..................",
    "....o.okhHHo..ohhhhSSkkSkkkkkkkkSSSSSkkkkkkSSo..................",
    ".......okHoo..ohhhhSSkSSSSSSSSSkSSSSSSSSSkkSSo..................",
    "........oooho.ohhhhSSkSSSooooookSSSSSooookSSSo..................",
    ".........oho..ohsssSSkSSSoeiiioSSSSSSeiiokSSo...................",
    "..........o...ohsdsSSSSSSoeieioSSSSSSieiokSSo...................",
    "..............ohsdssSSSSSSssssSSSSSSSSssSSSSo...................",
    "..............ohsdssSSSSSSSSSSSSSSSSSSSSSSsSSo..................",
    "..............ohsdssSSSSSSSSSSSSSSSSSSSSSSsSSSo.................",
    "..............ohssssSSSSSSSSSSSSSSSSSSSSSSSsSSSo................",
    "..............ohssssSSSSSSSSSSSSSSSSSSSSSSSdSSSo................",
    "..............ohhhhSSSSSSSSSSSSSSSSSSSSSSSSSdoo.................",
    "..............ossssSSSSSSSSSSSSSSSSSSSSSSSSSo...................",
    "...............oddssSSSSSSSSSSSSSSSSSSSSSSSSo...................",
    "................oddssSSSSSSSSSSSSSSSSSSSdSSSo...................",
    ".................oddssSSSSSSSSSSSSSSdrrdSSSSo...................",
    "..................oddssSSSSSSSSSSSSSSSSSSSSo....................",
    "...................oddssSSSSSSSSSSSSSSsSSSSo....................",
    "....................oddssSSSSSSSSSSSSSSSSSSo....................",
    ".....................ooddssSSSSSSSSSSSSSSSo.....................",
    ".......................oooossSSSSSSSSSSSSo......................",
    "........................oddoossSSSSSSSSSo.......................",
    "........................oddddoooooooddoo........................",
    "......................ooAAAAAAAAAAAAAAAoo.......................",
    "...................ooowwAAAAAAAAAAAAAAAWWoooo...................",
    "...............oooowwwwWAAAAAAAAAAAAAAAWWWWWWoooo...............",
    "............ooowwwwWWWWWAAAAAAAAAAAAAAAWWWWWWWWWWooo............",
    "..........oowwwwWWWWWWWWWwUUUUUUUUUUUcWWWWWWWWWWWWWWoo..........",
    "........oowwwwWWWWWWWWWWWwUUUUUUUUUUUcWWWWWWWWWWWWWWWWoo........",
    ".......ocwwwWWWWWWWWWWWWWwUUUUUUUUUUUcWWWWWWWWWWWWWWWWWWo.......",
    "......ocwwwWWWWWWWWWWWWWWWwUUUUUUUUUcWWWWWWWWWWWWWWWWWWWWoo.....",
    ".....ocwwwWWWWWWWWWWWWWWWWwUUUUUUUUUcWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWwUUUUUUUUUcWWWuuWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWwUUUUUUUcWWWWCuWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWwUUUUUUUcWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWwUUUUUUUcWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWWwUUUUUcWWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWWwUUUUUcWWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWWwUUUUUcWWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWWWwUUUcWWWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWWWwUUUcWWWWWWWWWWWWWWWWWWWWWWWWWo....",
    ".....ocwwwWWWWWWWWWWWWWWWWWWWwUUUcWWWWWWWWWWWWWWWWWWWWWWWWWo....",
], "PORTRAIT")

PORTRAIT_SPLIT = 42      # linhas >= 42 = corpo (pescoço, gola, jaleco); < 45 = cabeça (desenhada por cima)

# sobreposições: (x, y, linhas). '.' = mantém o que estava embaixo
EYES = {
    "aberto": [],
    "meio": [(25, 25, ["SSSSSS"]), (25, 26, ["oooooo"]), (37, 25, ["SSSS"]), (37, 26, ["oooo"])],
    "fechado": [(25, 25, ["SSSSSS", "ssssss", "oooooo", "ssss.."]), (37, 25, ["SSSS", "ssss", "oooo", ".ss."])],
    "arregalado": [(25, 24, ["oooooo", "oeiieo", "oeiieo", "oeeeeo", ".oooo."]),
                   (37, 24, ["oooo", "eiio", "eiio", "eeeo", "ooo."])],
}
BROWS = {
    "neutra": [],
    "foco": [(24, 23, ["kkkkSSS", "SSSSkkk"]), (37, 23, ["SSkk", "kk.."])],          # miolo baixo: concentração
    "medo": [(24, 21, ["....kkk", "kkkk...", "SSSSSSS"]), (37, 21, ["kk..", "..kk", "SSSS"])],      # miolo sobe
}
MOUTHS = {
    "neutra": [],
    "apertada": [(36, 37, ["dddd"])],
    "aberta": [(36, 36, ["dddd", "orro", ".oo."])],
}


def portrait(eyes="aberto", brows="foco", mouth="apertada", body_dy=0, head_dx=0, head_dy=0):
    s = Sprite(64, 64)
    body = ["." * 64] * PORTRAIT_SPLIT + PORTRAIT[PORTRAIT_SPLIT:]
    head = PORTRAIT[:45]
    s.put(body, 0, body_dy)
    h = Sprite(64, 64).put(head)
    for (x, y, rows) in BROWS[brows] + EYES[eyes] + MOUTHS[mouth]:
        h.put(rows, x, y)
    moved = Sprite(64, 64)
    moved.a[max(0, head_dy):64 + min(0, head_dy), max(0, head_dx):64 + min(0, head_dx)] = \
        h.a[max(0, -head_dy):64 + min(0, -head_dy), max(0, -head_dx):64 + min(0, -head_dx)]
    s.a = _over(s.a, moved.a)
    return s


def _over(base, top):
    out = base.copy()
    m = top[:, :, 3] == 255
    out[m] = top[m]
    return out


# concentração (8 q., loop): o ombro respira e a cabeça acompanha 1 q. depois; piscada nos q. 5-7
PORTRAIT_LOOP = [dict(body_dy=b, head_dy=hd, eyes=e) for b, hd, e in
                 [(0, 0, "aberto"), (0, 0, "aberto"), (-1, 0, "aberto"), (-1, -1, "aberto"), (-1, -1, "aberto"),
                  (0, -1, "meio"), (0, 0, "fechado"), (0, 0, "meio")]]
# medo contido (6 q., sem loop): pisca de susto, arregala, a cabeça recua, a boca entreabre, segura respirando
PORTRAIT_FEAR = [dict(eyes="aberto", brows="foco", mouth="apertada"),
                 dict(eyes="meio", brows="neutra", mouth="apertada", head_dx=-1),
                 dict(eyes="arregalado", brows="medo", mouth="apertada", head_dx=-2, head_dy=-1, body_dy=-1),
                 dict(eyes="arregalado", brows="medo", mouth="aberta", head_dx=-2, head_dy=-1, body_dy=-1),
                 dict(eyes="arregalado", brows="medo", mouth="aberta", head_dx=-2, head_dy=0, body_dy=0),
                 dict(eyes="arregalado", brows="medo", mouth="aberta", head_dx=-2, head_dy=-1, body_dy=-1)]


def portrait_frames(seq):
    return [portrait(**f) for f in seq]


# =================================================================================================================
# POSE 3 · de costas, em pé, girando a chave na fechadura (à direita). Caixa 30×60, pé na linha 59.
# =================================================================================================================
BACK_W, BACK_H, BACK_FOOT = 30, 60, 59
BACK_HAND = (27, 29)        # onde fica a chave (pra alinhar a fechadura do painel)
BACK = check([
    "............ohhhho............",
    "...........ohhhhhho...........",
    "............ohAAhho...........",
    "...........okkhhHko...........",
    "..........okhkhhHhko..........",
    ".........okhHkhhHhhko.........",
    ".........okhhkhhHhhko.........",
    ".........ommmkhhHmmmo.........",
    "........oskhhkhhHhhkso........",
    "........oskhhkhhHhhkso........",
    ".........okhhkhhHhhko.........",
    "..........okhkhhHhko..........",
    "...........okkhhhHo...........",
    "............okhhhHo...........",
    "...........oAkhhhHo...........",
    ".........ooAAAkhhHAoo.........",
    "....ooo.owwWWWkhhHwwco........",
    "...ocwWowwWWWWkhHWWwwco.......",
    "...ocwWowwWwWWkhHWwWwwco......",
    "...ocwWowwWwWWWkHWwWwwco......",
    "...ocwWowwWwWWhWkWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWwWWWWWWwwwco.......",
    "...ocwWowwWWWWWWWWWwwco.......",
    "...ocwWoowwWWWWWWWWwwco.......",
    "...ocwWoowwwWwwwwWwwwco.......",
    "...ocwWoowwccccccccwwco.......",
    "...ocwWoowwWWWWWWWWwwco.......",
    "...ocwWowwWWWWWWWWWWwwco......",
    "...ocwWowwWWWWWWWWWWwwco......",
    "...ocwWowwWWWWWWWWWWwwco......",
    "...ocwWowwWWWWWcWWWWwwco......",
    "...oAAAowwWWWWWcWWWWwwco......",
    "...osssowwWWWWWcWWWWwwco......",
    "...osssowwWWWWWcWWWWwwco......",
    "...odddwwWWWWWWcWWWWwwco......",
    "....ooowwWWWWWWcWWWWwwco......",
    "......owwWWWWWWcWWWWwwco......",
    "......owwWWWWWWcWWWWwwco......",
    "......owwWWWWWWcWWWWwwco......",
    ".......oooUUUuoouuuuooo.......",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    ".........oUUUuoouuuuo.........",
    "........oBAAAAooAAAABo........",
    "........oBBBBBooBBBBBo........",
    "........oBBBBBooBBBBBo........",
    "........oBBBBBooBBBBBo........",
    ".........ooooo..ooooo.........",
], "BACK")

# braço direito levantado até a fechadura; 4 quadros = o pulso girando a chave 90°
_ARM_TOP = [
    "oo......",
    "wwo.....",
    "wwwo....",
    "cwwo....",
    ".cwwo...",
    ".cwwo...",
    "..cwwo..",
    "..cwwo..",
    "..cwwo..",
    "...cwo..",
    "...AAo..",
]
ARM_KEY = [check(_ARM_TOP + h, f"ARM_KEY{i}") for i, h in enumerate([
    ["..osSso.", "..osSYYo", "..odsyo.", "...ooo.."],     # chave em pé
    ["..osSso.", "..osSSYo", "..odsYyo", "...oooo."],     # 30°
    ["..oSsso.", "..odSsYo", "..oddYYo", "...oooo."],     # 60°
    ["..oSsso.", "..odSso.", "..oddYYY", "...ooooo"],     # deitada: travou
])]


def back(turn=0, breath=0, pony_dx=0):
    s = Sprite(BACK_W, BACK_H)
    body = Sprite(BACK_W, BACK_H).put(BACK)
    if breath:                                         # o ombro/cabeça sobem 1 px (linhas de cima do quadril)
        a = body.a.copy()
        a[0:29] = body.a[1:30]
        body.a = a
    s.a = body.a
    s.put(ARM_KEY[turn], 20, 16 - breath)
    return s


# loop parado (6 q.): respira; e o giro (4 q., sem loop)
BACK_IDLE = [dict(breath=b) for b in (0, 0, 1, 1, 1, 0)]
BACK_TURN = [dict(turn=t, breath=1 if t == 3 else 0) for t in range(4)]


def back_frames(seq):
    return [back(**f) for f in seq]


# =================================================================================================================
# objetos pequenos da cena 1 (mesma linguagem: mapa de pixels)
# =================================================================================================================
SCOPE = check([
    "oo...........",
    "obo..........",
    "obWo.........",
    ".oWWo..ooo...",
    "..oWWoowWWo..",
    "...oWWowwWo..",
    "...oWWo.owWo.",
    "...oWAo.owWo.",
    "...oWWo.oAWo.",
    "...ommo.owWo.",
    "..oommoooWwo.",
    ".ommmmmmmmmmo",
    ".ooooGGoooWwo",
    "........owWo.",
    "...oooooowWoo",
    "..oBBBBBBBBBBo",
    "..oooooooooooo",
], "SCOPE")
SCOPE_STAGE = (5, 12)     # onde a luz da lâmina fica (pro brilho)

JAR = [check(r, f"JAR{i}") for i, r in enumerate([
    [".oooooooo.", "ommmmmmmmo", "oooooooooo", "oGeGGGGGgo", "oGeGGGGGgo", "oGeGuuGGgo", "oGeGuuuGgo",
     "oGeGGuGGgo", "oGeGGGGGgo", "ogggggggg o".replace(" ", ""), ".oooooooo."],
    [".oooooooo.", "ommmmmmmmo", "oooooooooo", "oGeGGGGGgo", "oGeGGGGGgo", "oGeGGuuGgo", "oGeGuuuGgo",
     "oGeGGGuGgo", "oGeGGGGGgo", "oggggggggo", ".oooooooo."],
    [".oooooooo.", "ommmmmmmmo", "oooooooooo", "oGeGGGGGgo", "oGeGGuGGgo", "oGeGuuuGgo", "oGeGGuuGgo",
     "oGeGGGGGgo", "oGeGGGGGgo", "oggggggggo", ".oooooooo."],
])]


def to_img(sprite):
    return sprite.image()
