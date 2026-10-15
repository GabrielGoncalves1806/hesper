"""Desenhos "de retângulos" usados quando não existe sprite (ou ENABLE_SPRITES = False).

Cada função devolve uma pygame.Surface do mesmo tamanho que o sprite do contrato (§6),
então trocar pelo PNG da Designer depois é só ligar a flag. Os desenhos foram portados
do mockup aprovado (reports/mockups/mockups.html).

Convenção dos objetos (cápsula, máquinas, plantas, player): a âncora é o centro da BASE,
ou seja, o ponto (largura/2, altura) da imagem fica em cima do ponto do mundo.
"""

import math
import random

import pygame

from game import config as C
from game.surfaces import opaque   # tiles opacos: formato fixo, não o da janela (ver game/surfaces.py)

Color = pygame.Color


def _r(surf, color, x, y, w, h):
    """Retângulo cheio (atalho pra deixar os desenhos legíveis)."""
    surf.fill(Color(color) if isinstance(color, str) else color, (x, y, w, h))


def _ellipse(surf, color, cx, cy, rx, ry):
    pygame.draw.ellipse(surf, color, (cx - rx, cy - ry, rx * 2, ry * 2))


def _bands(surf, x, y, h, bands):
    """Faixas verticais lado a lado: [(cor, largura), ...]. Dá o volume 'cilíndrico' das máquinas."""
    for color, w in bands:
        _r(surf, color, x, y, w, h)
        x += w


def _crystal(surf, x, y, color, shadow, size):
    _r(surf, shadow, x + 1, y + 1, size, size + 2)
    _r(surf, color, x, y, size, size + 1)
    _r(surf, color, x + 1, y - 1, max(1, size - 2), 1)
    _r(surf, (255, 255, 255, 220), x, y, 1, 2)


# ---------------------------------------------------------------- tiles
def floor(stage: str, variant: int) -> pygame.Surface:
    P = C.PALETTES[stage]
    rng = random.Random(f"floor-{stage}-{variant}")
    s = opaque((C.TILE, C.TILE))
    s.fill(P["floor"][variant % 3])
    for _ in range(5):   # manchas
        _r(s, P["patch"], rng.randrange(27), rng.randrange(29), rng.choice((2, 4, 6)), 2)
    for _ in range(6):   # pontinhos
        _r(s, P["dot"], rng.randrange(31), rng.randrange(31), 1, 1)
    if P["crack"] and variant in (1, 3):   # rachaduras só no planeta morto
        x, y = 4 + rng.randrange(12), 8 + rng.randrange(14)
        for _ in range(12):
            _r(s, P["crack"], x, y, 1, 1)
            x += 1
            y += rng.choice((-1, 0, 1))
    for _ in range(2):   # pedrinhas
        if rng.random() < 0.5:
            x, y = 3 + rng.randrange(24), 4 + rng.randrange(22)
            _r(s, P["dot"], x, y + 2, 4, 1)
            _r(s, P["peb"], x, y, 4, 2)
            _r(s, P["peb_hi"], x, y, 2, 1)
    if "grass" in P:      # tufos de grama no estágio verde
        for _ in range(3):
            if rng.random() < 0.65:
                gx, gy = 2 + rng.randrange(22), 9 + rng.randrange(20)
                for b in range(4):
                    bh = 3 + rng.randrange(4)
                    _r(s, P["grass2"] if b % 2 else P["grass"], gx + b * 2, gy - bh, 1, bh)
    return s


def sand(stage: str, variant: int) -> pygame.Surface:
    """Chão do deserto (32×32): 0 areia lisa, 1 cascalho, 2 dunas (ondulação), 3 laje de rocha.
    Fallback do sand_{stage}_{v}.png (Designer, pendente); a escolha da variação é do surface_gen."""
    P = C.PALETTES[stage]
    rng = random.Random(f"sand-{stage}-{variant}")
    s = opaque((C.TILE, C.TILE))
    s.fill(P["sand"][0])
    for _ in range(4):   # manchinhas suaves
        _r(s, P["sand"][1 + rng.randrange(2)], rng.randrange(26), rng.randrange(29), rng.choice((3, 5, 7)), 2)
    for _ in range(7):   # grãos
        _r(s, P["sand_dark"] if rng.random() < 0.6 else P["sand_hi"], rng.randrange(31), rng.randrange(31), 1, 1)
    if variant == 1:     # cascalho
        for _ in range(6):
            x, y = 2 + rng.randrange(27), 2 + rng.randrange(26)
            _r(s, P["sand_dark"], x, y + 1, 2, 1)
            _r(s, P["sand_hi"], x, y, 2, 1)
    elif variant == 2:   # ondulações de duna (o vento risca na horizontal)
        for row in (7, 16, 25):
            x = 2 + rng.randrange(6)
            w = 14 + rng.randrange(10)
            _r(s, P["sand"][1], x, row + 1, w, 1)
            _r(s, P["sand"][2], x + 1, row, w - 2, 1)
    elif variant == 3:   # laje de rocha aflorando
        x, y = 6 + rng.randrange(8), 8 + rng.randrange(8)
        _r(s, P["sand_dark"], x, y + 6, 14, 2)
        _r(s, P["sand"][1], x, y, 14, 6)
        _r(s, P["sand_hi"], x, y, 13, 1)
    if "grass" in P:      # algum tufo de grama no verde
        if rng.random() < 0.6:
            gx, gy = 3 + rng.randrange(22), 10 + rng.randrange(18)
            for b in range(3):
                bh = 2 + rng.randrange(3)
                _r(s, P["grass2"] if b % 2 else P["grass"], gx + b * 2, gy - bh, 1, bh)
    return s


def rock_small() -> pygame.Surface:
    """Rocha pequena (32×32), fallback do rock_small.png: pedra cinza-arroxeada com sombra no chão.
    Serve nos 3 estágios. O pontinho do minério que ela dá é desenhado à parte (ore_fleck)."""
    s = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 92), (3, 21, 27, 8))                  # sombra
    pygame.draw.ellipse(s, Color("#1b1630"), (3, 8, 24, 19))               # contorno
    pygame.draw.ellipse(s, Color("#625a6c"), (4, 9, 22, 17))
    pygame.draw.ellipse(s, Color("#867c8f"), (6, 10, 16, 9))
    _r(s, Color("#a69cad"), 9, 11, 7, 2)
    pygame.draw.ellipse(s, Color("#1b1630"), (20, 18, 10, 9))              # pedrinha do lado
    pygame.draw.ellipse(s, Color("#5a5264"), (21, 19, 8, 7))
    _r(s, Color("#867c8f"), 23, 20, 3, 1)
    return s


def ore_fleck(resource: str) -> pygame.Surface:
    """Cristalzinho do minério que a rocha pequena dá (por cima do rock_small, pra ler de longe)."""
    color, shadow = (Color(c) for c in C.ORE_COLORS[resource])
    s = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
    for x, y, size in ((11, 12, 4), (16, 14, 3)):
        _r(s, Color("#1b1630"), x - 1, y - 2, size + 2, size + 4)          # contorno: lê em cima da pedra
    _crystal(s, 11, 12, color, shadow, 4)
    _crystal(s, 16, 14, color, shadow, 3)
    return s


def crater(open_ramp: bool = False) -> pygame.Surface:
    """Cratera 3×3 (96×96), fallback do crater.png / crater_ramp.png: borda de rocha, fundo escuro.
    `open_ramp` (Marco 2): a rampa de descida aberta embaixo, no meio."""
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 80), (6, 14, 88, 80))                  # sombra no chão
    pygame.draw.ellipse(s, Color("#1b1630"), (3, 5, 90, 84))
    pygame.draw.ellipse(s, Color("#625a6c"), (5, 7, 86, 80))
    pygame.draw.ellipse(s, Color("#867c8f"), (9, 9, 78, 66))
    pygame.draw.ellipse(s, Color("#322c3c"), (18, 18, 60, 50))              # boca
    pygame.draw.ellipse(s, Color("#120e18"), (22, 24, 52, 40))
    pygame.draw.ellipse(s, Color("#0b0810"), (28, 32, 40, 28))
    for x, y in ((14, 14), (70, 22), (12, 56), (66, 66), (40, 8)):      # pedras na borda
        pygame.draw.ellipse(s, Color("#1b1630"), (x, y, 14, 10))
        pygame.draw.ellipse(s, Color("#867c8f"), (x + 1, y + 1, 12, 8))
        _r(s, Color("#a69cad"), x + 4, y + 2, 4, 1)
    if open_ramp:
        _r(s, Color("#453e50"), 38, 48, 20, 36)
        for i in range(0, 34, 6):
            _r(s, Color("#5a5264"), 38, 50 + i, 20, 2)
        _r(s, Color("#f2c46d"), 38, 82, 20, 2)
    return s


def cave_ramp_up() -> pygame.Surface:
    """Rampa de subida da caverna (96×96, fallback do cave_ramp_up.png): poço na rocha com luz fria vindo de
    cima e degraus de metal subindo (de baixo pra cima). Mesma linguagem da crater_ramp."""
    s = pygame.Surface((96, 96), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 90), (6, 14, 88, 80))                  # sombra no chão
    pygame.draw.ellipse(s, Color("#1b1630"), (3, 4, 90, 86))
    pygame.draw.ellipse(s, Color("#4a4447"), (5, 6, 86, 82))                # borda de rocha (névoa)
    pygame.draw.ellipse(s, Color("#6c6467"), (9, 8, 78, 66))
    pygame.draw.ellipse(s, Color("#2b272a"), (17, 14, 62, 58))              # parede do poço
    pygame.draw.ellipse(s, Color("#9fc4d6"), (24, 16, 48, 30))              # céu lá em cima (luz fria)
    pygame.draw.ellipse(s, Color("#d9eef6"), (32, 19, 32, 18))
    for i in range(6):                                                      # feixe de luz descendo
        a = 70 - i * 10
        pygame.draw.polygon(s, (200, 228, 240, a), [(30 + i, 32), (66 - i, 32), (60 - i, 70), (36 + i, 70)])
    _r(s, Color("#3b3f4a"), 36, 34, 24, 52)                                 # trilho dos degraus
    for i, y in enumerate(range(82, 36, -7)):                               # degraus de metal (sobem)
        w = 24 - i
        _r(s, Color("#1b1630"), 48 - w // 2, y + 2, w, 2)
        _r(s, Color("#8f98a8"), 48 - w // 2, y, w, 2)
        _r(s, Color("#c5ccd8"), 48 - w // 2, y, w, 1)
    _r(s, Color("#f2c46d"), 36, 84, 24, 2)                                  # faixa de aviso no pé
    for x, y in ((12, 16), (70, 20), (10, 58), (68, 66), (42, 6)):          # pedras na borda
        pygame.draw.ellipse(s, Color("#1b1630"), (x, y, 14, 10))
        pygame.draw.ellipse(s, Color("#6c6467"), (x + 1, y + 1, 12, 8))
        _r(s, Color("#8c8487"), x + 4, y + 2, 4, 1)
    return s


def lamp() -> pygame.Surface:
    """Luminária de chão (16×32, fallback do lamp.png): poste baixo com luz quente no topo. Âncora: centro
    da base. A luz do mundo vem do game/lighting.py; aqui só o objeto."""
    s = pygame.Surface(C.LAMP_SPRITE_SIZE, pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 90), 8, 30, 6, 2)                                 # sombra
    _r(s, Color("#1b1630"), 3, 26, 10, 5)                                   # pé
    _r(s, Color("#5d5659"), 4, 27, 8, 3)
    _r(s, Color("#1b1630"), 6, 10, 4, 17)                                   # poste
    _r(s, Color("#7c757d"), 7, 10, 2, 17)
    _r(s, Color("#1b1630"), 2, 2, 12, 10)                                   # cúpula
    _r(s, Color("#c98a3c"), 3, 3, 10, 8)
    _r(s, Color("#ffd27a"), 4, 4, 8, 6)
    _r(s, Color("#fff3c4"), 5, 5, 4, 3)
    _r(s, Color("#5d5659"), 3, 1, 10, 2)                                    # tampa
    return s


def lamp_icon() -> pygame.Surface:
    """Ícone 16×16 da luminária (fallback do icon_lamp.png)."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, Color("#1b1630"), 4, 1, 8, 7)
    _r(s, Color("#ffd27a"), 5, 2, 6, 5)
    _r(s, Color("#fff3c4"), 6, 3, 3, 2)
    _r(s, Color("#1b1630"), 7, 8, 2, 5)
    _r(s, Color("#9a9086"), 7, 8, 1, 5)
    _r(s, Color("#1b1630"), 4, 13, 8, 3)
    _r(s, Color("#5d5659"), 5, 13, 6, 2)
    return s


def wall(stage: str, variant: int) -> pygame.Surface:
    """Topo da rocha (32×32). Com chão embaixo, só os 8 px de cima aparecem e a face (24 px) cobre o resto."""
    P = C.PALETTES[stage]
    rng = random.Random(f"wall-{stage}-{variant}")
    s = opaque((C.TILE, C.TILE))
    s.fill(P["rock"] if variant % 2 == 0 else P["rock2"])
    for i in range(5):   # blocos de pedra com luz em cima/esquerda e sombra embaixo/direita
        sx, sy = 1 + rng.randrange(20), 1 + rng.randrange(22)
        sw, sh = min(6 + rng.randrange(8), 31 - sx), min(4 + rng.randrange(4), 31 - sy)
        _r(s, P["rock2"] if i % 2 else P["rock"], sx, sy, sw, sh)
        _r(s, P["rock_hi"], sx, sy, sw - 1, 1)
        _r(s, P["rock_hi"], sx, sy, 1, sh - 1)
        _r(s, P["rock_dot"], sx + 1, sy + sh - 1, sw - 1, 1)
        _r(s, P["rock_dot"], sx + sw - 1, sy + 1, 1, sh - 1)
    return s


def wall_face(stage: str) -> pygame.Surface:
    """Face frontal alta (32×24): é ela que faz a parede parecer parede, não degrau."""
    P = C.PALETTES[stage]
    s = opaque((C.TILE, 24))
    s.fill(P["face"])
    _r(s, P["face_hi"], 0, 0, 32, 1)
    _r(s, P["face_hi"], 0, 1, 32, 1)
    # estratos de rocha horizontais + rachaduras verticais
    _r(s, P["face_dark"], 0, 8, 13, 1); _r(s, P["face_dark"], 17, 7, 15, 1)
    _r(s, P["face_dark"], 4, 15, 20, 1); _r(s, P["face_dark"], 26, 16, 6, 1)
    _r(s, P["face_hi"], 0, 9, 13, 1); _r(s, P["face_hi"], 4, 16, 20, 1)
    _r(s, P["face_dark"], 11, 2, 1, 6); _r(s, P["face_dark"], 23, 9, 1, 6); _r(s, P["face_dark"], 7, 17, 1, 5)
    _r(s, P["face_dark"], 0, 21, 32, 3)   # base escura, onde encosta no chão
    if "moss" in P:   # cipós descendo pela face no estágio verde
        _r(s, P["moss"], 6, 0, 2, 12); _r(s, P["moss"], 5, 10, 1, 3)
        _r(s, P["moss"], 13, 0, 1, 5)
        _r(s, P["moss2"], 24, 0, 2, 8); _r(s, P["moss"], 26, 6, 1, 4)
    return s


def moss(variant: int) -> pygame.Surface:
    P = C.PALETTES["green"]
    rng = random.Random(f"moss-{variant}")
    s = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
    for _ in range(2):
        mx, my = 2 + rng.randrange(20), 2 + rng.randrange(12)
        _r(s, P["moss"], mx, my, 8, 3)
        _r(s, P["moss"], mx + 2, my - 1, 4, 1)
        _r(s, P["moss2"], mx + 1, my, 4, 1)
    return s


def water(stage: str) -> pygame.Surface:
    s = opaque((C.TILE, C.TILE))
    s.fill(C.PALETTES[stage]["water"])
    return s


def ore(resource: str, variant: int) -> pygame.Surface:
    """Cristais coloridos por cima da parede (fundo transparente)."""
    color, shadow = (Color(c) for c in C.ORE_COLORS[resource])
    rng = random.Random(f"ore-{resource}-{variant}")
    s = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
    for _ in range(3 + variant % 2):
        _crystal(s, 3 + rng.randrange(23), 3 + rng.randrange(9), color, shadow, 3 + rng.randrange(3))
    return s


def terminal() -> pygame.Surface:
    s = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
    _r(s, "#1a1418", 5, 5, 22, 22)
    _r(s, "#3a3f3c", 6, 6, 20, 20)
    _r(s, "#4e5551", 6, 6, 20, 1)
    _r(s, "#0d1a15", 8, 8, 16, 12)
    for i, w in enumerate((12, 9, 13, 6)):
        _r(s, C.C_TERMINAL, 9, 9 + i * 3, w, 1)
    _r(s, "#5a605c", 8, 22, 16, 2)
    _r(s, C.C_ACCENT, 22, 22, 2, 2)
    return s


def icon(resource: str) -> pygame.Surface:
    color, shadow = C.ORE_COLORS[resource]
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, shadow, 1, 1, 15, 15)
    _r(s, color, 0, 0, 15, 15)
    _r(s, (255, 255, 255, 190), 0, 0, 2, 4)
    return s


# ---------------------------------------------------------------- player
# Astronauta chibi 32×32 (§3): capacete grande, visor azul-marinho com reflexo,
# traje branco com detalhes vermelhos e mochila. 3 direções: "down", "up", "side" (olhando pra direita).
_OUT, _SUIT, _SUIT_SH, _RED, _RED_D = "#1a1418", "#ece8e0", "#b9b2a8", "#d64541", "#8f2a2a"
_VISOR, _VISOR_HI, _BOOT, _PACK = "#1c2a4a", "#8fc4f0", "#3b3f46", "#6b717a"


def _astronaut(view: str, frame: int) -> pygame.Surface:
    """Desenha um quadro. frame 0..3: nos quadros 1 e 3 o corpo sobe 1 px e as pernas alternam."""
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    bob = 1 if frame % 2 else 0
    # pernas (não sobem com o bob)
    lift_l = 2 if frame == 1 else 0
    lift_r = 2 if frame == 3 else 0
    if view == "side":
        front = 3 if frame == 1 else -2 if frame == 3 else 0     # passada pra frente/trás
        _r(s, _OUT, 12 + front, 26, 6, 6); _r(s, _BOOT, 13 + front, 27, 4, 4)
        _r(s, _OUT, 14 - front, 26, 6, 6); _r(s, _SUIT_SH, 15 - front, 27, 4, 3); _r(s, _BOOT, 15 - front, 29, 4, 2)
    else:
        _r(s, _OUT, 10, 26 - lift_l, 6, 6); _r(s, _SUIT_SH, 11, 27 - lift_l, 4, 2); _r(s, _BOOT, 11, 29 - lift_l, 4, 2)
        _r(s, _OUT, 16, 26 - lift_r, 6, 6); _r(s, _SUIT_SH, 17, 27 - lift_r, 4, 2); _r(s, _BOOT, 17, 29 - lift_r, 4, 2)
    y = -bob
    # mochila (atrás: aparece do lado esquerdo na vista de lado e inteira de costas)
    if view == "side":
        _r(s, _OUT, 5, 15 + y, 7, 11); _r(s, _PACK, 6, 16 + y, 5, 9); _r(s, _RED, 6, 18 + y, 5, 2)
    # corpo
    _r(s, _OUT, 9, 16 + y, 14, 11)
    _r(s, _SUIT, 10, 17 + y, 12, 9)
    _r(s, _SUIT_SH, 10, 23 + y, 12, 3)
    if view == "down":
        _r(s, _RED, 14, 18 + y, 4, 3); _r(s, _RED_D, 14, 20 + y, 4, 1)          # painel do peito
        _r(s, _OUT, 7, 18 + y, 3, 6); _r(s, _SUIT_SH, 8, 18 + y, 2, 5)           # braços
        _r(s, _OUT, 22, 18 + y, 3, 6); _r(s, _SUIT_SH, 22, 18 + y, 2, 5)
    elif view == "up":
        _r(s, _OUT, 10, 16 + y, 12, 9); _r(s, _PACK, 11, 17 + y, 10, 7); _r(s, _RED, 11, 19 + y, 10, 2)
        _r(s, _OUT, 7, 18 + y, 3, 6); _r(s, _SUIT_SH, 8, 18 + y, 2, 5)
        _r(s, _OUT, 22, 18 + y, 3, 6); _r(s, _SUIT_SH, 22, 18 + y, 2, 5)
    else:
        arm = 1 if frame in (1, 3) else 0
        _r(s, _OUT, 14 + arm, 18 + y, 5, 6); _r(s, _SUIT_SH, 15 + arm, 18 + y, 3, 5); _r(s, _RED, 15 + arm, 22 + y, 3, 1)
    _r(s, _RED, 10, 25 + y, 12, 1)                                                # cinto
    # capacete grande (~metade da altura)
    _r(s, _OUT, 8, 1 + y, 16, 17); _r(s, _OUT, 7, 3 + y, 18, 13)
    _r(s, _SUIT, 9, 2 + y, 14, 15); _r(s, _SUIT, 8, 4 + y, 16, 11)
    _r(s, _SUIT_SH, 8, 13 + y, 16, 2); _r(s, _SUIT_SH, 9, 15 + y, 14, 2)
    _r(s, "#ffffff", 10, 3 + y, 4, 1)                                             # brilho no topo
    if view == "down":       # visor de frente, centralizado
        _r(s, _OUT, 10, 6 + y, 12, 8); _r(s, _VISOR, 11, 7 + y, 10, 6)
        _r(s, _VISOR_HI, 12, 8 + y, 3, 1); _r(s, _VISOR_HI, 12, 9 + y, 1, 2)
    elif view == "side":     # visor deslocado pra direita: é assim que se lê "olhando pro lado"
        _r(s, _OUT, 15, 6 + y, 10, 8); _r(s, _VISOR, 16, 7 + y, 8, 6)
        _r(s, _VISOR_HI, 17, 8 + y, 3, 1); _r(s, _VISOR_HI, 17, 9 + y, 1, 2)
        _r(s, _RED, 9, 9 + y, 3, 2)                                               # detalhe vermelho na nuca
    else:                    # de costas: sem visor, faixa vermelha e antena
        _r(s, _RED, 9, 9 + y, 14, 2)
        _r(s, _PACK, 21, 0 + y, 1, 3); _r(s, _RED, 20, 0 + y, 3, 1)
    return s


def player(view: str) -> pygame.Surface:
    """Player parado, 32×32. view = 'down', 'up' ou 'side' (olhando pra direita)."""
    return _astronaut(view, 0)


def player_walk(view: str) -> pygame.Surface:
    """Folha de caminhada 128×32: 4 quadros de 32×32 lado a lado."""
    sheet = pygame.Surface((128, 32), pygame.SRCALPHA)
    for i in range(4):
        sheet.blit(_astronaut(view, i), (i * 32, 0))
    return sheet


def drill(view: str) -> pygame.Surface:
    """Broca de fallback no mesmo formato da folha do contrato (§6): 4 quadros girando.

    side: 96×16 (quadros 24×16, ponta pra direita) · down/up: 64×24 (quadros 16×24, ponta pra baixo/cima).
    """
    vertical = view != "side"
    fw, fh = (16, 24) if vertical else (24, 16)
    sheet = pygame.Surface((fw * 4, fh), pygame.SRCALPHA)
    for i in range(4):
        f = pygame.Surface((24, 16), pygame.SRCALPHA)        # desenha deitado e gira se precisar
        _r(f, _OUT, 0, 3, 14, 9); _r(f, "#d9dde2", 1, 4, 12, 7); _r(f, C.C_ACCENT, 3, 6, 7, 2)
        _r(f, _OUT, 4, 11, 4, 4); _r(f, _PACK, 5, 11, 2, 3)                         # cabo
        _r(f, "#8a929c", 14, 4, 6, 7); _r(f, "#b9c0c8", 20, 6, 3, 3); _r(f, "#e9edf1", 23, 7, 1, 1)
        for k in range(3):                                                           # rosca girando
            _r(f, "#5d646d", 14 + (k * 3 + i) % 8, 4 + (k % 2), 1, 6)
        if vertical:
            f = pygame.transform.rotate(f, -90 if view == "down" else 90)
        sheet.blit(f, (i * fw, 0))
    return sheet


# ---------------------------------------------------------------- cápsula
def pod() -> pygame.Surface:
    """Cápsula 64×72. Base do desenho em y=70."""
    s = pygame.Surface((64, 72), pygame.SRCALPHA)
    x, y = 0, 70
    _ellipse(s, (0, 0, 0, 100), 32, y - 4, 32, 7)
    _r(s, "#2a2d33", x + 1, y - 5, 10, 3); _r(s, "#2a2d33", x + 53, y - 5, 10, 3)
    _r(s, "#3b3f46", x + 4, y - 16, 4, 11); _r(s, "#3b3f46", x + 56, y - 16, 4, 11)
    _r(s, "#22272e", x + 5, y - 49, 54, 38)
    _bands(s, x + 6, y - 48, 36, [("#f4f6f8", 4), ("#e1e5ea", 20), ("#c8cdd4", 16), ("#abb2bb", 8), ("#8c949e", 4)])
    for i, n in enumerate((14, 10, 7, 5, 3, 1)):   # domo
        yy = y - 54 + i
        _r(s, "#22272e", x + 5 + n, yy, 54 - 2 * n, 1)
        if i > 0:
            _r(s, "#eef1f4" if i < 3 else "#e1e5ea", x + 6 + n, yy, 52 - 2 * n, 1)
    _r(s, "#abb2bb", x + 6, y - 38, 52, 1)
    _r(s, C.C_ACCENT, x + 6, y - 30, 52, 4); _r(s, "#f29a62", x + 6, y - 30, 52, 1); _r(s, "#a8471f", x + 6, y - 26, 52, 1)
    _r(s, "#22272e", x + 11, y - 47, 18, 12); _r(s, "#2b7f99", x + 12, y - 46, 16, 10); _r(s, C.C_O2, x + 12, y - 46, 12, 8)
    _r(s, "#d8fbff", x + 14, y - 45, 3, 1); _r(s, "#d8fbff", x + 14, y - 44, 1, 2); _r(s, "#d8fbff", x + 19, y - 45, 1, 1)
    _r(s, "#22272e", x + 35, y - 25, 16, 14); _r(s, "#34444f", x + 36, y - 24, 14, 13); _r(s, "#22303a", x + 42, y - 24, 1, 13)
    _r(s, C.C_ACCENT, x + 39, y - 18, 2, 2); _r(s, C.C_ACCENT, x + 44, y - 18, 2, 2)
    for i in range(3):
        _r(s, "#8c949e", x + 12, y - 22 + i * 3, 14, 1)
    _r(s, "#8c949e", x + 34, y - 46, 18, 4); _r(s, C.C_ACCENT, x + 34, y - 46, 4, 4)
    _r(s, "#6b717a", x + 50, y - 66, 1, 14); _r(s, "#6b717a", x + 47, y - 58, 7, 1)
    _r(s, "#7a2a24", x + 49, y - 69, 3, 3)   # luz da antena (pisca no render)
    return s


# ---------------------------------------------------------------- máquinas
# Cada máquina é desenhada com "origem" (x, y) = canto esquerdo da base, igual ao mockup.
def _o2gen(s, x, y):
    _ellipse(s, (0, 0, 0, 100), x + 16, y - 2, 17, 5)
    _r(s, "#151a20", x, y - 11, 32, 10); _r(s, "#2b3440", x + 1, y - 10, 30, 8); _r(s, "#3d4856", x + 1, y - 10, 30, 2)
    _r(s, "#8a96a3", x + 3, y - 7, 2, 2); _r(s, "#8a96a3", x + 27, y - 7, 2, 2)
    _r(s, "#14202b", x + 5, y - 45, 22, 35); _r(s, "#14202b", x + 7, y - 47, 18, 2)
    _bands(s, x + 6, y - 44, 34, [("#9ad9f7", 2), ("#64b7e8", 6), ("#3f91c6", 7), ("#2d70a0", 3), ("#1f5379", 2)])
    _r(s, "#2d70a0", x + 8, y - 46, 16, 2); _r(s, "#64b7e8", x + 9, y - 46, 8, 1)
    _r(s, "#1b3448", x + 6, y - 33, 20, 2); _r(s, "#1b3448", x + 6, y - 20, 20, 2)
    _r(s, (255, 255, 255, 150), x + 8, y - 42, 1, 7)
    _r(s, "#e9e5dd", x + 12, y - 29, 8, 6); _r(s, "#1a1418", x + 12, y - 29, 8, 1); _r(s, "#c2281c", x + 15, y - 27, 1, 3)
    _r(s, "#6b717a", x + 13, y - 49, 6, 2); _r(s, C.C_ACCENT, x + 12, y - 52, 8, 3); _r(s, "#a8471f", x + 12, y - 50, 8, 1)
    _r(s, "#6b717a", x + 27, y - 26, 4, 2); _r(s, "#6b717a", x + 29, y - 26, 2, 15)


def _heater(s, x, y):
    _ellipse(s, (0, 0, 0, 100), x + 16, y - 2, 17, 5)
    _r(s, "#2a1712", x + 5, y - 4, 5, 4); _r(s, "#2a1712", x + 22, y - 4, 5, 4)
    _r(s, "#1a1418", x + 2, y - 36, 28, 33)
    _bands(s, x + 3, y - 35, 31, [("#8a6050", 3), ("#6a4538", 14), ("#5a3a2f", 6), ("#462c24", 3)])
    _r(s, "#9a7060", x + 2, y - 38, 28, 3); _r(s, "#1a1418", x + 2, y - 35, 28, 1)
    for i in range(4):
        _r(s, "#1d0f0b", x + 7, y - 30 + i * 5, 18, 4)
        _r(s, "#ff9a3d", x + 8, y - 29 + i * 5, 16, 2)
    for i in range(13):
        _r(s, "#1a1418" if i % 2 else C.C_TI, x + 3 + i * 2, y - 8, 2, 2)
    _r(s, "#1a1418", x + 20, y - 47, 7, 10); _r(s, "#4a3a34", x + 21, y - 46, 5, 9); _r(s, "#6b5a52", x + 19, y - 48, 9, 2)


def _ice_cube(s, x, y, size):
    _r(s, "#4fb3d6", x + 1, y + 1, size, size)
    _r(s, "#bdf1ff", x, y, size, size)
    _r(s, "#eafcff", x, y, size, 1); _r(s, "#eafcff", x, y, 1, size - 1)
    _r(s, "#7fd3ef", x + size - 1, y + 1, 1, size - 1)


def _melter(s, x, y):
    _ellipse(s, (0, 0, 0, 90), x + 16, y - 2, 16, 5)
    _r(s, "#1a1418", x + 3, y - 25, 26, 24)
    _bands(s, x + 4, y - 24, 22, [("#6f8696", 3), ("#4f6370", 13), ("#3e4f5a", 5), ("#2b3740", 3)])
    for i in range(8):
        _r(s, "#1a1418" if i == 0 else "#8aa2b2" if i < 3 else "#64798a", x + i, y - 33 + i, 32 - 2 * i, 1)
    _r(s, "#1a1418", x, y - 34, 32, 1)
    _ice_cube(s, x + 6, y - 41, 7); _ice_cube(s, x + 14, y - 43, 8); _ice_cube(s, x + 23, y - 40, 6)
    _r(s, "#14202b", x + 9, y - 21, 7, 15)
    _r(s, "#6b717a", x + 28, y - 14, 4, 3); _r(s, "#6b717a", x + 30, y - 14, 2, 7)


_MACHINE_PAINTERS = {"o2": _o2gen, "heater": _heater, "melter": _melter}
MACHINE_SIZE = {1: (40, 58), 2: (40, 66)}
T2_LIFT = 7   # quanto o corpo do nv.2 fica "levantado" em cima do pedestal


def solar_panel() -> pygame.Surface:
    """Painel solar 32×40 (fallback até o sprite solar_panel ser aprovado): placa azul-escura inclinada num poste."""
    s = pygame.Surface((32, 40), pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 90), 16, 37, 12, 3)
    _r(s, "#1a1418", 11, 35, 10, 3); _r(s, "#4a4f57", 12, 35, 8, 2)        # pé
    _r(s, "#1a1418", 14, 20, 4, 16); _r(s, "#6b717a", 15, 20, 2, 15)       # poste
    # placa: trapézio (mais estreito em cima = inclinado pra trás, virado pro céu)
    outline = [(5, 4), (26, 4), (31, 24), (0, 24)]
    face = [(6, 5), (25, 5), (29, 23), (2, 23)]
    pygame.draw.polygon(s, Color("#1a1418"), outline)
    pygame.draw.polygon(s, Color("#1d3566"), face)
    for i in range(1, 4):                                                  # células: linhas horizontais
        y = 5 + i * 18 // 4
        k = (y - 5) / 18
        _r(s, "#2c4f8f", round(6 - 4 * k), y, round(19 + 8 * k), 1)
    for i in range(1, 4):                                                  # e "verticais" (abrindo em leque)
        top_x, bot_x = 6 + i * 19 / 4, 2 + i * 27 / 4
        pygame.draw.line(s, Color("#2c4f8f"), (round(top_x), 5), (round(bot_x), 22))
    _r(s, "#6fa0e0", 7, 6, 6, 1); _r(s, "#4a78c0", 6, 7, 3, 1)             # reflexo
    _r(s, "#0f1d3a", 1, 24, 30, 1)                                         # borda de baixo, na sombra
    return s


def workbench() -> pygame.Surface:
    """Bancada T2 32×40 (fallback se o machine_workbench.png sumir): tampo de cobre entre duas colunas."""
    s = pygame.Surface(C.BENCH_SPRITE_SIZE, pygame.SRCALPHA)
    _r(s, "#1b1630", 2, 36, 28, 4)
    _r(s, "#3b3f46", 3, 35, 26, 3)
    _r(s, "#1b1630", 4, 8, 24, 28)
    _r(s, "#d9a066", 5, 9, 22, 8)       # tampo
    _r(s, "#c2cad4", 5, 17, 3, 18); _r(s, "#c2cad4", 24, 17, 3, 18)   # colunas
    _r(s, "#59d0e6", 12, 20, 8, 6)      # visor
    return s


def machine(kind: str) -> pygame.Surface:
    """Máquina nv.1 (40×58) ou nv.2 (40×66: mesma máquina num pedestal com faixas douradas)."""
    if kind == "solar":
        return solar_panel()
    if kind == "workbench":
        return workbench()
    tier = 2 if kind.endswith("_t2") else 1
    base_kind = kind.removesuffix("_t2")
    w, h = MACHINE_SIZE[tier]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    ox, oy = 4, h - 2
    if tier == 2:
        _ellipse(s, (0, 0, 0, 100), ox + 16, oy - 2, 19, 5)
        _r(s, "#1a1418", ox - 2, oy - T2_LIFT - 2, 36, T2_LIFT + 1)
        _r(s, "#3b3f46", ox - 1, oy - T2_LIFT - 1, 34, T2_LIFT - 1)
        for i in range(8):
            _r(s, C.C_TI if i % 2 == 0 else "#1a1418", ox + 1 + i * 4, oy - 4, 4, 2)
        oy -= T2_LIFT
    _MACHINE_PAINTERS[base_kind](s, ox, oy)
    if tier == 2:   # marca "II" dourada no topo
        _r(s, C.C_TI, ox + 1, oy - 30, 2, 6); _r(s, C.C_TI, ox + 4, oy - 30, 2, 6)
    return s


def machine_anim(target: pygame.Surface, kind: str, ax: int, ay: int, t: float) -> None:
    """Partes que mexem (LED, chama, nível d'água). Só usado com o desenho de fallback.

    (ax, ay) = âncora na tela (centro da base). t = tempo em segundos.
    """
    tier = 2 if kind.endswith("_t2") else 1
    base_kind = kind.removesuffix("_t2")
    x, y = ax - 16, ay - 2 - (T2_LIFT if tier == 2 else 0)   # mesma origem usada em machine()
    tick = t * 9   # o mockup animava a ~9 quadros por segundo
    if base_kind == "o2":
        _r(target, C.C_OK if tick % 8 < 4 else "#2f5a2c", x + 4, y - 14, 2, 2)
        _r(target, "#c2281c", x + 15 + (1 if tick % 6 < 3 else 0), y - 27, 1, 3)
        for i in range(4):   # bolhas de O₂ subindo
            p = (tick * 1.2 + i * 9) % 36
            a = int(255 * (1 - p / 36))
            bubble = pygame.Surface((3, 3), pygame.SRCALPHA)
            bubble.fill((170, 235, 255, a))
            target.blit(bubble, (x + 12 + (i * 5) % 9 + round(math.sin((tick + i * 3) * 0.4)), y - 55 - p))
    elif base_kind == "heater":
        for i in range(4):
            f = math.sin(tick * 0.7 + i * 1.3)
            _r(target, "#ffd27a" if f > 0.3 else "#ff9a3d" if f > -0.3 else "#e0602a", x + 8, y - 29 + i * 5, 16, 2)
    elif base_kind == "melter":
        level = 6 + round(4 + math.sin(tick * 0.25) * 3)
        _r(target, "#4aa8d8", x + 10, y - 7 - level, 5, level)
        _r(target, "#9fe0f5", x + 10, y - 7 - level, 5, 1)
        drop = (tick * 1.5) % 10
        _r(target, "#6fc9ef", x + 30, y - 6 + drop * 0.5, 2, 2)


# ---------------------------------------------------------------- plantas
def plant(kind: str) -> pygame.Surface:
    """Planta 32×40 (âncora: centro da base)."""
    s = pygame.Surface((32, 40), pygame.SRCALPHA)
    x, y = 16, 38
    if kind == "bush":
        _ellipse(s, (0, 0, 0, 77), x, y, 11, 3)
        _r(s, "#1d4224", x - 10, y - 11, 20, 10); _r(s, "#1d4224", x - 7, y - 14, 14, 3)
        _r(s, "#2f6a33", x - 9, y - 12, 16, 9); _r(s, "#2f6a33", x - 5, y - 14, 9, 2)
        _r(s, "#4a8f45", x - 7, y - 13, 7, 3); _r(s, "#4a8f45", x + 1, y - 9, 4, 2)
        _r(s, "#7cc45e", x - 6, y - 13, 2, 1)
        for px, py in ((3, -11), (-3, -7), (6, -6)):
            _r(s, "#e94f6a", x + px, y + py, 2, 2)
    elif kind == "tree":
        _ellipse(s, (0, 0, 0, 82), x, y, 13, 4)
        _r(s, "#3d2a1e", x - 3, y - 17, 6, 17); _r(s, "#6b4a33", x - 2, y - 17, 3, 17); _r(s, "#8a6446", x - 2, y - 17, 1, 15)
        for cx, cy, rad, col in [(0, -25, 12, "#1a4322"), (-7, -22, 8, "#1a4322"), (8, -21, 7, "#1a4322"),
                                 (-1, -27, 10, "#2e6a33"), (-6, -23, 6, "#2e6a33"), (6, -23, 6, "#2e6a33"),
                                 (-4, -30, 6, "#4a8f45"), (3, -25, 4, "#4a8f45")]:
            pygame.draw.circle(s, Color(col), (x + cx, y + cy), rad)
        _r(s, "#7cc45e", x - 6, y - 34, 3, 1)
    else:  # flower
        for i in range(3):
            fx, fy = x - 6 + i * 6, y - 2 - (i % 2) * 3
            _r(s, "#3f7a34", fx, fy - 5, 1, 5); _r(s, "#3f7a34", fx + 1, fy - 3, 2, 1)
            _r(s, "#f2a3c8" if i != 1 else "#f5d36b", fx - 1, fy - 8, 3, 3)
            _r(s, "#fff3c4", fx, fy - 7, 1, 1)
    return s


# ---------------------------------------------------------------- efeitos
def radial(radius: int, color: tuple[int, int, int], max_alpha: int) -> pygame.Surface:
    """Círculo com degradê (centro forte, borda transparente). Usado pra luzes, névoa e vinheta.

    Calculamos numa grade pequena (32×32) e esticamos com smoothscale: rápido e suave.
    """
    n = 32
    small = pygame.Surface((n, n), pygame.SRCALPHA)
    for j in range(n):
        for i in range(n):
            d = math.hypot(i + 0.5 - n / 2, j + 0.5 - n / 2) / (n / 2)
            a = max(0.0, 1 - d)
            small.set_at((i, j), (*color, int(max_alpha * a * a)))
    return pygame.transform.smoothscale(small, (radius * 2, radius * 2))


def vignette(w: int, h: int, color: tuple[int, int, int], max_alpha: int) -> pygame.Surface:
    """Bordas escurecidas (ou avermelhadas, no O₂ crítico)."""
    sw, sh = 64, 36
    small = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for j in range(sh):
        for i in range(sw):
            dx, dy = (i + 0.5) / sw - 0.5, (j + 0.5) / sh - 0.5
            d = math.hypot(dx * 1.0, dy * 0.75) / 0.6
            a = min(1.0, max(0.0, (d - 0.45) / 0.55))
            small.set_at((i, j), (*color, int(max_alpha * a)))
    return pygame.transform.smoothscale(small, (w, h))


# ---------------------------------------------------------------- veios e drill automática
def vein(resource: str) -> pygame.Surface:
    """Veio 2×2 (64×64) no chão: mancha escura com cristais. Overlay transparente (serve nos 3 estágios)."""
    color, shadow = (Color(c) for c in C.ORE_COLORS[resource])
    rng = random.Random(f"vein-{resource}")
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (20, 14, 12, 120), (4, 8, 56, 50))
    pygame.draw.ellipse(s, (20, 14, 12, 90), (10, 14, 44, 38))
    for _ in range(9):
        _crystal(s, 10 + rng.randrange(40), 14 + rng.randrange(32), color, shadow, 3 + rng.randrange(4))
    return s


DRILL_FILL_RECT = (12, 54, 7, 10)   # indicador de enchimento dentro do quadro (drill T1 laser, freela r3d v1.2)


def drill_machine() -> pygame.Surface:
    """Drill automática: folha 256×80 com 4 quadros de 64×80 (broca girando). Âncora: centro da base."""
    sheet = pygame.Surface((256, 80), pygame.SRCALPHA)
    for f in range(4):
        s = pygame.Surface((64, 80), pygame.SRCALPHA)
        _ellipse(s, (0, 0, 0, 100), 32, 74, 30, 6)
        for x in (8, 50):                                            # pés
            _r(s, _OUT, x, 60, 6, 16); _r(s, "#6b717a", x + 1, 61, 4, 14)
        _r(s, _OUT, 10, 30, 44, 34)                                  # corpo
        _bands(s, 11, 31, 32, [("#d9dde2", 4), ("#b9c0c8", 22), ("#8c949e", 10), ("#6b717a", 6)])
        _r(s, C.C_ACCENT, 11, 36, 42, 3); _r(s, "#a8471f", 11, 39, 42, 1)
        _r(s, _OUT, 47, 46, 9, 14); _r(s, "#1b1411", 48, 47, 7, 12)   # janelinha do indicador (vazia)
        _r(s, _OUT, 26, 14, 12, 17); _r(s, "#8a929c", 27, 15, 10, 15)   # torre
        _r(s, _OUT, 24, 4, 16, 11); _r(s, "#3b3f46", 25, 5, 14, 9); _r(s, C.C_TI, 30, 7, 4, 3)
        _r(s, _OUT, 28, 64, 8, 12)                                    # broca entrando no chão
        for k in range(3):                                            # rosca girando
            _r(s, "#b9c0c8" if (k + f) % 2 else "#5d646d", 29, 65 + k * 4, 6, 2)
        sheet.blit(s, (f * 64, 0))
    return sheet


def drill_icon() -> pygame.Surface:
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 3, 4, 10, 9); _r(s, "#b9c0c8", 4, 5, 8, 7); _r(s, C.C_ACCENT, 4, 7, 8, 1)
    _r(s, _OUT, 6, 0, 4, 5); _r(s, "#8a929c", 7, 1, 2, 4)
    _r(s, _OUT, 7, 12, 2, 4)
    return s


# ---------------------------------------------------------------- baú (v0.2)
# O sprite chest/chest_open ainda espera o ok do dono (config.CHEST_SPRITE_APPROVED): até lá, é este.
def chest(opened: bool = False) -> pygame.Surface:
    """Baú 32×40, âncora no centro da base: caixote de metal com faixa laranja e trava."""
    s = pygame.Surface(C.CHEST_SPRITE_SIZE, pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 100), 16, 37, 15, 3)
    _r(s, _OUT, 2, 18, 28, 20)                                       # corpo
    _bands(s, 3, 19, 18, [("#c9ced4", 3), ("#9aa2ab", 18), ("#737b85", 5)])
    _r(s, "#5d646d", 3, 33, 26, 4)                                   # rodapé
    _r(s, C.C_ACCENT, 3, 24, 26, 2); _r(s, "#a8471f", 3, 26, 26, 1)  # faixa
    if opened:
        _r(s, _OUT, 2, 6, 28, 13)                                    # tampa levantada pra trás
        _r(s, "#737b85", 3, 7, 26, 4); _r(s, "#5d646d", 3, 11, 26, 7)
        _r(s, "#1b1411", 4, 18, 24, 3)                               # boca escura do baú
        _r(s, C.C_TI, 8, 18, 4, 1); _r(s, C.C_O2, 18, 18, 3, 1)      # brilho do que tem dentro
    else:
        _r(s, _OUT, 1, 12, 30, 9)                                    # tampa fechada
        _bands(s, 2, 13, 7, [("#d9dde2", 3), ("#b9c0c8", 20), ("#8c949e", 5)])
        _r(s, (255, 255, 255, 120), 3, 13, 26, 1)
        _r(s, _OUT, 13, 18, 6, 6); _r(s, C.C_TI, 14, 19, 4, 4)       # trava
        _r(s, "#8a6a2a", 15, 21, 2, 2)
    return s


def chest_icon() -> pygame.Surface:
    """Ícone 16×16 do baú (pra hotbar e inventário)."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 1, 3, 14, 12)
    _r(s, "#b9c0c8", 2, 4, 12, 4); _r(s, "#9aa2ab", 2, 8, 12, 6)
    _r(s, C.C_ACCENT, 2, 9, 12, 1)
    _r(s, _OUT, 6, 7, 4, 4); _r(s, C.C_TI, 7, 8, 2, 2)
    return s


# ---------------------------------------------------------------- estação de drones (Marco 3)
# Fallback dos sprites drone_station / drone / icon_drone_station (config.DRONE_SPRITES_APPROVED).
def drone_station() -> pygame.Surface:
    """Estação 64×72, âncora no centro da base 2×2: plataforma escura com 2 pads (C.DRONE_PADS)."""
    w, h = C.DRONE_STATION_SPRITE_SIZE
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 100), 32, 69, 30, 4)
    _r(s, _OUT, 1, 26, 62, 42)                                       # corpo
    _r(s, "#4a4f57", 2, 27, 60, 33); _r(s, "#3b3f46", 2, 58, 60, 2)
    _r(s, "#b9c0c8", 2, 60, 60, 6)                                   # rodapé claro com faixa
    for i in range(7):
        _r(s, C.C_TI if i % 2 == 0 else "#1a1418", 4 + i * 8, 62, 8, 2)
    _r(s, "#2f3238", 31, 27, 2, 31)                                  # divisória entre os pads
    for px, py in C.DRONE_PADS:                                      # pads: anel laranja com "H"
        _ellipse(s, C.C_ACCENT, px, py, 10, 7)
        _ellipse(s, "#2f3238", px, py, 8, 5)
        _r(s, "#d9dde2", px - 3, py - 3, 1, 6); _r(s, "#d9dde2", px + 2, py - 3, 1, 6)
        _r(s, "#d9dde2", px - 3, py, 6, 1)
    _r(s, _OUT, 6, 13, 18, 14); _r(s, "#d9dde2", 7, 14, 16, 12)      # painelzinho
    _r(s, "#1b1411", 9, 17, 12, 4); _r(s, C.C_O2, 10, 18, 6, 2)
    _r(s, _OUT, 49, 2, 5, 25); _r(s, "#b9c0c8", 50, 3, 3, 23)        # antena
    _r(s, "#ff5a4a", 50, 0, 3, 3)
    return s


def drone_sheet() -> pygame.Surface:
    """Drone 64×16: 4 quadros de 16×16 com as hélices girando. A sombra quem desenha é o jogo."""
    sheet = pygame.Surface((64, 16), pygame.SRCALPHA)
    for f in range(4):
        x = f * 16
        _r(sheet, _OUT, x + 4, 5, 8, 7); _r(sheet, "#d9dde2", x + 5, 6, 6, 5)   # corpo
        _r(sheet, C.C_ACCENT, x + 5, 9, 6, 1)
        _r(sheet, "#1b1411", x + 6, 7, 4, 2); _r(sheet, C.C_O2, x + 7, 7, 2, 1)  # "olho"
        for hx, hy in ((1, 3), (11, 3), (1, 12), (11, 12)):                    # 4 hélices
            if f % 2 == 0:
                _r(sheet, "#9aa2ab", x + hx, hy, 4, 1)
            else:
                _r(sheet, "#9aa2ab", x + hx + 1, hy - 1, 2, 3)
    return sheet


def drone_station_icon() -> pygame.Surface:
    """Ícone 16×16 da estação (hotbar e inventário)."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 0, 6, 16, 10); _r(s, "#4a4f57", 1, 7, 14, 8)
    _r(s, C.C_ACCENT, 3, 9, 4, 3); _r(s, C.C_ACCENT, 9, 9, 4, 3)
    _r(s, _OUT, 5, 0, 6, 5); _r(s, "#d9dde2", 6, 1, 4, 3)
    return s


# ---------------------------------------------------------------- destroços (v0.3 Marco 3)
# Fallback dos sprites wreck_cargo / wreck_module / wreck_probe / loot_crate(_empty) e dos ícones novos,
# usado só se o PNG da Designer faltar. Mesmos tamanhos e âncoras do contrato (game/wrecks.py).
_HULL, _HULL_SH, _HULL_D, _HULL_HI = "#e6dcc4", "#c2b596", "#8f8468", "#f6f0e2"
_SAND_PILE = (150, 92, 58, 210)


def _sand_pile(s, cx, cy, rx, ry):
    """Areia acumulada encostada no destroço (translúcida: funciona nos 3 chãos)."""
    _ellipse(s, (0, 0, 0, 70), cx, cy + 2, rx + 2, ry + 1)
    _ellipse(s, _SAND_PILE, cx, cy, rx, ry)


def wreck(kind: str) -> pygame.Surface:
    """Destroço `kind` ("cargo", "module", "probe") no tamanho do sprite do contrato."""
    return {"cargo": _wreck_cargo, "module": _wreck_module, "probe": _wreck_probe}[kind]()


def _wreck_cargo() -> pygame.Surface:
    """Nave de carga caída, 128×112 (4×3 tiles; os 16 px de cima são deriva e antena)."""
    s = pygame.Surface((128, 112), pygame.SRCALPHA)
    _sand_pile(s, 64, 102, 62, 9)
    # casco: um "pão" deitado, nariz à direita meio enterrado
    pygame.draw.polygon(s, Color(_OUT), [(6, 54), (18, 38), (98, 36), (120, 52), (124, 76), (112, 98), (12, 100), (4, 82)])
    pygame.draw.polygon(s, Color(_HULL_SH), [(8, 56), (19, 40), (97, 38), (118, 53), (121, 76), (110, 96), (13, 98), (6, 82)])
    pygame.draw.polygon(s, Color(_HULL), [(10, 56), (20, 42), (96, 40), (115, 54), (117, 70), (12, 72)])
    _r(s, _HULL_HI, 22, 43, 70, 2)
    _r(s, C.C_ACCENT, 8, 74, 112, 4)                         # faixa laranja
    _r(s, "#a8471f", 8, 78, 112, 1)
    for x in range(24, 96, 14):                              # janelinhas
        _r(s, _OUT, x, 50, 8, 6)
        _r(s, "#3a5068", x + 1, 51, 6, 4)
        _r(s, "#8fc4f0", x + 1, 51, 2, 1)
    _r(s, _OUT, 34, 80, 26, 20)                              # porta de carga aberta (a caixa sai dela)
    _r(s, "#2a2620", 35, 81, 24, 19)
    for y in range(83, 99, 4):
        _r(s, "#4a443a", 36, y, 22, 1)
    _r(s, _OUT, 28, 100, 38, 3)                              # rampa de carga
    _r(s, "#9a9086", 29, 100, 36, 2)
    pygame.draw.polygon(s, Color(_OUT), [(14, 40), (22, 14), (34, 14), (40, 40)])      # deriva
    pygame.draw.polygon(s, Color(_HULL_SH), [(17, 39), (24, 17), (32, 17), (37, 39)])
    _r(s, C.C_ACCENT, 24, 20, 8, 3)
    _r(s, _OUT, 100, 4, 3, 34)                               # antena torta
    _r(s, "#9aa2ab", 101, 5, 1, 32)
    _r(s, "#ff5a4a", 99, 2, 5, 3)
    _r(s, "#5d646d", 84, 84, 18, 8)                          # placa do casco solta
    _r(s, _OUT, 84, 84, 18, 1)
    _r(s, _OUT, 70, 60, 10, 6)                               # "07"
    _r(s, _HULL, 71, 61, 3, 4)
    _r(s, _HULL, 76, 61, 3, 1)
    _r(s, _HULL, 77, 62, 1, 3)
    for x, y in ((50, 66), (88, 62), (104, 80)):              # amassados/queimados
        _ellipse(s, (60, 44, 36, 120), x, y, 5, 3)
    return s


def _wreck_module() -> pygame.Surface:
    """Módulo da colônia, 96×88 (3×2 tiles; teto e antena sobem 24 px). Terminal em (62, 59)–(80, 75)."""
    s = pygame.Surface((96, 88), pygame.SRCALPHA)
    _sand_pile(s, 48, 82, 46, 7)
    _r(s, _OUT, 4, 22, 88, 62)                               # caixa do módulo
    _r(s, _HULL_SH, 5, 23, 86, 60)
    _r(s, _HULL, 5, 23, 74, 52)
    _r(s, _HULL_HI, 5, 23, 86, 2)
    _r(s, _HULL_D, 79, 23, 12, 60)                           # lateral na sombra
    _r(s, C.C_ACCENT, 5, 44, 86, 3)                          # faixa
    _r(s, _OUT, 10, 50, 18, 33)                              # porta
    _r(s, "#5d646d", 11, 51, 16, 32)
    _r(s, "#3b3f46", 18, 51, 1, 32)
    _r(s, C.C_TI, 24, 64, 2, 2)
    for x in (34, 48):                                       # janelas (uma quebrada)
        _r(s, _OUT, x, 28, 10, 10)
        _r(s, "#3a5068", x + 1, 29, 8, 8)
    _r(s, "#8fc4f0", 35, 29, 3, 1)
    pygame.draw.line(s, Color(_OUT), (49, 30), (56, 36))
    _r(s, _OUT, 62, 59, 18, 16)                              # terminal (alvo do E)
    _r(s, "#0d1a15", 63, 60, 16, 12)
    for i, w in enumerate((12, 8, 10)):
        _r(s, C.C_TERMINAL, 65, 62 + i * 3, w, 1)
    _r(s, "#5a605c", 63, 72, 16, 3)
    _r(s, _OUT, 18, 6, 3, 17)                                # antena com prato
    _r(s, "#9aa2ab", 19, 7, 1, 15)
    _ellipse(s, Color(_OUT), 20, 8, 9, 5)
    _ellipse(s, Color("#d9dde2"), 20, 8, 8, 4)
    _r(s, "#ff5a4a", 19, 5, 3, 2)
    _r(s, _OUT, 56, 16, 22, 7)                               # tanque no teto
    _r(s, "#9aa2ab", 57, 17, 20, 5)
    return s


def _wreck_probe() -> pygame.Surface:
    """Sonda pequena, 64×64 (2×2 tiles). LED vermelho em (23, 37)."""
    s = pygame.Surface((64, 64), pygame.SRCALPHA)
    _sand_pile(s, 32, 56, 28, 6)
    _r(s, _OUT, 14, 26, 34, 30)                              # corpo
    _r(s, "#e0a83a", 15, 27, 32, 28)
    _r(s, "#f2c46d", 15, 27, 32, 3)
    _r(s, "#a8701f", 40, 27, 7, 28)
    _r(s, _OUT, 18, 33, 16, 10)                              # painelzinho
    _r(s, "#1b1411", 19, 34, 14, 8)
    _r(s, "#ff5a4a", 23, 37, 2, 1)                           # LED
    _r(s, _OUT, 0, 34, 15, 12)                               # painel solar quebrado
    _r(s, "#2f4a8a", 1, 35, 13, 10)
    _r(s, "#5a7ac8", 1, 35, 13, 1)
    pygame.draw.line(s, Color("#8fa6d6"), (3, 44), (10, 36))
    _r(s, _OUT, 30, 12, 3, 15)                               # mastro + prato
    _ellipse(s, Color(_OUT), 31, 10, 12, 6)
    _ellipse(s, Color("#d9dde2"), 31, 10, 11, 5)
    _ellipse(s, Color("#9aa2ab"), 31, 11, 5, 2)
    for x in (16, 42):                                       # pés
        _r(s, _OUT, x, 54, 5, 5)
        _r(s, "#5d646d", x + 1, 54, 3, 4)
    return s


def loot_crate(empty: bool = False) -> pygame.Surface:
    """Caixa de saque 32×32, blit em (tx·32, ty·32): cheia = tampa fechada com LED âmbar; vazia = aberta."""
    s = pygame.Surface(C.LOOT_CRATE_SIZE, pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 100), 16, 29, 14, 3)
    _r(s, _OUT, 3, 12, 26, 18)                               # corpo
    _bands(s, 4, 13, 16, [("#9aa2ab", 3), ("#7b838d", 17), ("#5d646d", 4)])
    _r(s, "#4a5058", 4, 26, 24, 3)
    for x in (8, 22):                                        # reforços
        _r(s, "#5d646d", x, 13, 2, 16)
    if empty:
        _r(s, _OUT, 3, 4, 26, 9)                             # tampa aberta pra trás
        _r(s, "#6b717a", 4, 5, 24, 4)
        _r(s, "#1b1411", 4, 12, 24, 3)                       # boca escura, vazia
        _r(s, "#3b3f46", 14, 18, 4, 3)                       # LED apagado
    else:
        _r(s, _OUT, 2, 8, 28, 7)                             # tampa fechada
        _bands(s, 3, 9, 5, [("#c9ced4", 3), ("#aab2bb", 19), ("#8c949e", 4)])
        _r(s, (255, 255, 255, 120), 4, 9, 24, 1)
        _r(s, _OUT, 13, 17, 6, 5)
        _r(s, "#f2a33a", 14, 18, 4, 3)                       # LED âmbar
    return s


SEALED_CONTAINER_SIZE = (32, 40)


def sealed_container() -> pygame.Surface:
    """Contêiner lacrado (v0.4 Marco 3 · M3.2), PLACEHOLDER até o sprite da Designer: caixa industrial 32×40 em branco
    quente, faixa laranja, contorno #1b1630 e o lacre da colônia no meio. Ancorado no centro de baixo do tile."""
    out = "#1b1630"
    s = pygame.Surface(SEALED_CONTAINER_SIZE, pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 90), 16, 37, 15, 3)
    _r(s, out, 1, 6, 30, 33)                                 # corpo
    _bands(s, 2, 7, 31, [("#fff6ea", 3), ("#efe5da", 18), ("#d9cbbb", 4), ("#b9ab9c", 3)])
    _r(s, out, 1, 6, 30, 2)                                  # tampo
    _r(s, "#fffaf2", 2, 8, 27, 1)
    for x in (7, 15, 23):                                    # nervuras
        _r(s, "#cdbfae", x, 10, 1, 27)
    _r(s, out, 1, 18, 30, 8)                                 # faixa laranja
    _r(s, "#e2733a", 2, 19, 28, 6)
    _r(s, "#f59a5e", 2, 19, 28, 1)
    _r(s, "#a8481f", 2, 24, 28, 1)
    _r(s, out, 12, 16, 8, 12)                                # lacre da colônia
    _r(s, "#3a3f4a", 13, 17, 6, 10)
    _r(s, "#ffd84a", 15, 20, 2, 4)
    _r(s, out, 1, 35, 30, 4)                                 # base escura
    _r(s, "#6b6258", 2, 36, 28, 2)
    return s


def opened_container(sealed: pygame.Surface) -> pygame.Surface:
    """Contêiner aberto (v0.5 M4), PLACEHOLDER até o container_open.png do dono: o lacrado escurecido, com a tampa
    aberta (uma fenda escura no topo). Serve pra qualquer tamanho de sprite."""
    s = sealed.copy()
    s.fill((120, 120, 130, 255), special_flags=pygame.BLEND_RGBA_MULT)
    w, h = s.get_size()
    _r(s, "#1b1630", w // 8, h // 6, w - 2 * (w // 8), max(3, h // 8))
    _r(s, "#0c0a18", w // 8 + 1, h // 6 + 1, w - 2 * (w // 8) - 2, max(2, h // 8 - 2))
    return s


def hand_drill_icon(side_sheet: pygame.Surface) -> pygame.Surface:
    """Ícone 16×16 da broca de mão (fallback do icon_hand_drill.png): o 1º quadro do drill_side reduzido pra caber,
    centralizado."""
    fw = side_sheet.get_width() // 4
    frame = side_sheet.subsurface((0, 0, fw, side_sheet.get_height()))
    k = 16 / max(frame.get_size())
    small = pygame.transform.scale(frame, (max(1, round(frame.get_width() * k)), max(1, round(frame.get_height() * k))))
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    s.blit(small, (8 - small.get_width() // 2, 8 - small.get_height() // 2))
    return s


def blueprint_icon() -> pygame.Surface:
    """Ícone 16×16 de projeto: chip azul de blueprint com linhas de desenho técnico."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 1, 2, 14, 12)
    _r(s, "#2f6ab8", 2, 3, 12, 10)
    _r(s, "#9fd0ff", 2, 3, 12, 1)
    _r(s, "#cfe8ff", 4, 6, 6, 1)
    _r(s, "#cfe8ff", 4, 6, 1, 5)
    _r(s, "#cfe8ff", 4, 10, 8, 1)
    _r(s, "#cfe8ff", 9, 6, 1, 4)
    _r(s, C.C_TI, 11, 5, 2, 2)
    return s


def o2_tank_icon() -> pygame.Surface:
    """Ícone 16×16 do tanque de O₂: cilindro ciano com válvula."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 4, 3, 8, 13)
    _bands(s, 5, 4, 11, [("#b8f0fa", 2), (C.C_O2, 3), ("#2f8fa8", 1)])
    _r(s, "#ffffff", 5, 5, 1, 3)
    _r(s, _OUT, 6, 0, 4, 4)
    _r(s, "#9aa2ab", 7, 1, 2, 2)
    _r(s, C.C_ACCENT, 5, 9, 6, 1)
    return s


def backpack_icon() -> pygame.Surface:
    """Ícone 16×16 da mochila (fallback do icon_backpack.png): corpo laranja com bolso e alça."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 3, 1, 10, 3)
    _r(s, "#9aa2ab", 5, 2, 6, 1)
    _r(s, _OUT, 2, 3, 12, 13)
    _r(s, C.C_ACCENT, 3, 4, 10, 11)
    _r(s, "#ffd9a0", 4, 5, 8, 1)
    _r(s, _OUT, 5, 9, 6, 5)
    _r(s, "#a8541e", 6, 10, 4, 3)
    return s


def water_capsule_icon() -> pygame.Surface:
    """Ícone 16×16 da cápsula de água (fallback do icon_water_capsule.png): frasco azul com tampa cinza."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 5, 0, 6, 3)
    _r(s, "#9aa2ab", 6, 1, 4, 1)
    _r(s, _OUT, 3, 2, 10, 14)
    _r(s, "#2a7f96", 4, 3, 8, 12)
    _r(s, C.C_O2, 4, 5, 8, 9)
    _r(s, "#bdf2ff", 5, 6, 2, 5)
    return s


def scanner_icon() -> pygame.Surface:
    """Ícone 16×16 do scanner de navegação: tela redonda com varredura verde."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 1, 2, 14, 13)
    _r(s, "#5d646d", 2, 3, 12, 11)
    _ellipse(s, Color("#0d1a15"), 8, 8, 5, 4)
    pygame.draw.line(s, Color(C.C_TERMINAL), (8, 8), (12, 5))
    _r(s, C.C_TERMINAL, 6, 9, 1, 1)
    _r(s, C.C_TI, 9, 10, 1, 1)
    _r(s, _OUT, 11, 0, 2, 3)
    return s


def constructor_icon() -> pygame.Surface:
    """Ícone 16×16 do construtor (placeholder até o icon_constructor.png da Designer): ferramenta de mão de perfil,
    corpo branco com faixa laranja, cabo inclinado e a lente ciano do scanner na frente."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 0, 3, 11, 7)
    _r(s, "#e1e5ea", 1, 4, 9, 5)
    _r(s, C.C_ACCENT, 1, 6, 9, 1)
    _r(s, _OUT, 10, 2, 5, 9)
    _r(s, "#6b717a", 11, 3, 3, 7)
    _r(s, C.C_O2, 12, 4, 2, 5)
    _r(s, "#ffffff", 12, 4, 1, 1)
    _r(s, _OUT, 2, 9, 4, 6)
    _r(s, C.C_ACCENT, 3, 9, 2, 5)
    return s


def lamp_strong() -> pygame.Surface:
    """Luminária forte (16×32, fallback do lamp_t2.png): poste mais alto, cúpula branca-fria maior."""
    s = pygame.Surface(C.LAMP_SPRITE_SIZE, pygame.SRCALPHA)
    _ellipse(s, (0, 0, 0, 90), 8, 30, 7, 2)
    _r(s, _OUT, 2, 26, 12, 5)
    _r(s, "#5d646d", 3, 27, 10, 3)
    _r(s, C.C_ACCENT, 3, 28, 10, 1)
    _r(s, _OUT, 6, 9, 4, 18)
    _r(s, "#9aa2ab", 7, 9, 2, 18)
    _r(s, _OUT, 1, 0, 14, 11)
    _r(s, "#c9a24a", 2, 1, 12, 9)
    _r(s, "#fff3c4", 3, 2, 10, 7)
    _r(s, "#ffffff", 5, 3, 5, 3)
    return s


def lamp_strong_icon() -> pygame.Surface:
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    _r(s, _OUT, 3, 0, 10, 8)
    _r(s, "#fff3c4", 4, 1, 8, 6)
    _r(s, "#ffffff", 5, 2, 4, 2)
    _r(s, _OUT, 7, 8, 2, 5)
    _r(s, _OUT, 3, 13, 10, 3)
    _r(s, C.C_ACCENT, 4, 14, 8, 1)
    return s
