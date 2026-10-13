"""Broca de mão do explorador · v6.0 · 3 candidatas (A, B, C) pro dono escolher.

O dono reprovou a broca do experimento ("feia e muito grande"). Aqui as 3 são bem menores, mas cabem no MESMO
quadro do contrato (lado 24×16, baixo/cima 16×24) e no MESMO DRILL_GRIP do game/render.py, então trocar não
exige código: só o PNG.

  A · "furadeira de bolso": pistola em L minúscula (corpo branco, faixa laranja, pega com a luva, broca cônica)
  B · "caneta-broca": ferramenta reta e fina, segurada por cima como lanterna (cabo emborrachado, broca fina)
  C · "broca de punho": módulo branco preso na luva, a broca sai direto da mão (a menor das três)

Coordenadas pensadas pro encaixe com a pose player_mine (quadro do player 32×32, broca colada no DRILL_GRIP):
  lado  (12, 13): a luva do braço esticado cai em (5..7, 6..8) do quadro da broca
  baixo (13, 16): a luva cai em (6..8, 3..4)
  cima  (20,  4): desenhada ANTES do player; só a broca aparece por cima do ombro direito (x >= 4)
O punho (luva escura do traje) vem desenhado na própria broca, por cima da pega, pra ler "na mão".
O tremor de cada quadro é o MESMO do player_mine (lado: x -1 nos quadros 1 e 3, y +1 no 3; baixo/cima: y +1
nos quadros 1 e 3), então tocando os dois com o mesmo índice de quadro a broca fica colada na mão.
"""
from explorer import P as XP, Canvas, box, strip

WHITE = ["#fbf8f1", "#e6e1dc", "#c3bdc6", "#8f88a0"]
PLATE = ["#a6a1b8", "#77728a", "#565168", "#3c3749"]
DARK = ["#5f586e", "#3f3a4c", "#2f2a3a", "#221e2b"]
STEEL = ["#eef0f6", "#c3c6d4", "#8f92a6", "#5e6176"]
ORANGE, ORANGE_D, ORANGE_L = "#e2733a", "#a9482a", "#f4a06a"
CYAN, CYAN_L = "#59d0e6", "#c8f6ff"
GLOVE = XP["boot"]                       # luva do explorador (mesma tinta das botas)

SIZE = {"side": (24, 16), "down": (16, 24), "up": (16, 24)}
SHAKE = {"side": [(0, 0), (-1, 0), (0, 0), (-1, 1)],        # = tremor do player_mine
         "down": [(0, 0), (0, 1), (0, 0), (0, 1)],
         "up": [(0, 0), (0, 1), (0, 0), (0, 1)]}
# ponta da broca no quadro 0 (coordenada do quadro da broca), pro Dev mirar as faíscas (drill_tip)
TIP = {}


def cone_side(c, x0, x1, cy, half, f):
    """Broca cônica deitada (ponta pra direita), estria em espiral andando com o quadro."""
    L = x1 - x0
    for x in range(x0, x1 + 1):
        hh = half * (1 - (x - x0) / (L + 1))
        for y in range(round(cy - hh), round(cy + hh) + 1):
            st = (x - (y - cy) + f) % 4 < 2
            d = (y - cy) / max(hh, 0.5)
            k = 0 if d < -0.35 else 1 if d < 0.4 else 2
            c.px(x, y, STEEL[k] if st else STEEL[k + 1])


def cone_vert(c, y0, y1, cx, half, f):
    """Broca cônica em pé (de y0 pra y1, ponta em y1), pra baixo ou pra cima."""
    step = 1 if y1 > y0 else -1
    L = abs(y1 - y0)
    for k, y in enumerate(range(y0, y1 + step, step)):
        hw = half * (1 - k / (L + 1))
        for x in range(round(cx - hw), round(cx + hw) + 1):
            st = (k - (x - cx) + f) % 4 < 2
            d = (x - cx) / max(hw, 0.5)
            j = 0 if d < -0.35 else 1 if d < 0.4 else 2
            c.px(x, y, STEEL[j] if st else STEEL[j + 1])


def fist(c, x, y, w=3, h=3):
    box(c, x, y, w, h, GLOVE)
    c.px(x, y, GLOVE[0])


def layer(c, draw, dx, dy):
    t = Canvas(c.w, c.h)
    draw(t, dx, dy)
    t.outline()
    c.blit(t, 0, 0)


# ---------------------------------------------------------------- A · furadeira de bolso (pistola em L)
# corpo cinza-metal (as ombreiras do explorador): separa bem do traje branco que fica atrás
GREY = ["#d6d3e0", "#a6a1b8", "#77728a", "#565168"]
ORANGE_T = [ORANGE_L, ORANGE, ORANGE_D, ORANGE_D]


def a_side(f):
    c = Canvas(24, 16)
    dx, dy = SHAKE["side"][f]

    def body(t, x, y):
        box(t, 5 + x, 8 + y, 3, 3, DARK)                      # pega (a luva fecha em cima)
        t.hline(5 + x, 10 + y, 3, ORANGE_D)                   # pé da bateria
        box(t, 3 + x, 3 + y, 9, 5, GREY, cut=1)               # carcaça 9×5
        t.hline(4 + x, 5 + y, 6, ORANGE)                      # faixa laranja
        t.px(4 + x, 5 + y, ORANGE_L)
        t.px(4 + x, 4 + y, CYAN_L if f % 2 == 0 else CYAN)    # LED
        box(t, 12 + x, 4 + y, 2, 3, DARK)                     # mandril
        cone_side(t, 14 + x, 19 + x, 5 + y, 1.8, f)
        fist(t, 5 + x, 6 + y)
    layer(c, body, dx, dy)
    TIP["A_side"] = (19, 5)
    return c


def a_down(f):
    c = Canvas(16, 24)
    dx, dy = SHAKE["down"][f]

    def body(t, x, y):
        box(t, 1 + x, 0 + y, 7, 6, GREY, cut=1)               # carcaça vista de cima/frente
        t.hline(2 + x, 3 + y, 4, ORANGE)
        t.px(2 + x, 3 + y, ORANGE_L)
        t.px(2 + x, 1 + y, CYAN_L if f % 2 == 0 else CYAN)
        box(t, 3 + x, 6 + y, 3, 1, DARK)                      # mandril
        cone_vert(t, 7 + y, 13 + y, 4 + x, 1.8, f)
        fist(t, 7 + x, 2 + y, 3, 3)                           # pega do lado da mão direita
    layer(c, body, dx, dy)
    TIP["A_down"] = (4, 13)
    return c


def a_up(f):
    c = Canvas(16, 24)
    dx, dy = SHAKE["up"][f]

    def body(t, x, y):
        box(t, 1 + x, 12 + y, 7, 5, GREY, cut=1)              # fica atrás do ombro
        t.hline(2 + x, 14 + y, 4, ORANGE)
        box(t, 3 + x, 11 + y, 3, 1, DARK)
        cone_vert(t, 10 + y, 4 + y, 4 + x, 1.8, f)
    layer(c, body, dx, dy)
    TIP["A_up"] = (4, 4)
    return c


# ---------------------------------------------------------------- B · caneta-broca (reta, segurada por cima)
def b_tube_side(t, x, y, f):
    box(t, 1 + x, 6 + y, 2, 3, ORANGE_T)                      # tampa laranja
    box(t, 3 + x, 6 + y, 6, 3, GREY)                          # cabo de metal com anéis
    t.vline(4 + x, 6 + y, 3, GREY[3])
    box(t, 9 + x, 6 + y, 3, 3, WHITE)                         # nariz branco
    t.px(10 + x, 7 + y, CYAN_L if f % 2 == 0 else CYAN)       # LED
    t.px(12 + x, 7 + y, GREY[1])
    cone_side(t, 13 + x, 18 + x, 7 + y, 1.2, f)


def b_side(f):
    c = Canvas(24, 16)
    dx, dy = SHAKE["side"][f]

    def body(t, x, y):
        b_tube_side(t, x, y, f)
        fist(t, 5 + x, 5 + y, 3, 5)                           # mão fechada em volta do cabo
    layer(c, body, dx, dy)
    TIP["B_side"] = (18, 7)
    return c


def b_down(f):
    c = Canvas(16, 24)
    dx, dy = SHAKE["down"][f]

    def body(t, x, y):
        box(t, 6 + x, 0 + y, 3, 2, ORANGE_T)
        box(t, 6 + x, 2 + y, 3, 4, GREY)
        box(t, 6 + x, 6 + y, 3, 3, WHITE)
        t.px(7 + x, 7 + y, CYAN_L if f % 2 == 0 else CYAN)
        t.px(7 + x, 9 + y, GREY[1])
        cone_vert(t, 10 + y, 15 + y, 7 + x, 1.2, f)
        fist(t, 5 + x, 2 + y, 5, 3)
    layer(c, body, dx, dy)
    TIP["B_down"] = (7, 15)
    return c


def b_up(f):
    c = Canvas(16, 24)
    dx, dy = SHAKE["up"][f]

    def body(t, x, y):
        box(t, 4 + x, 13 + y, 3, 6, GREY)
        box(t, 4 + x, 10 + y, 3, 3, WHITE)
        t.px(5 + x, 11 + y, CYAN_L if f % 2 == 0 else CYAN)
        t.px(5 + x, 9 + y, GREY[1])
        cone_vert(t, 8 + y, 3 + y, 5 + x, 1.2, f)
    layer(c, body, dx, dy)
    TIP["B_up"] = (5, 3)
    return c


# ---------------------------------------------------------------- C · broca de punho (módulo preso na luva)
def c_side(f):
    c = Canvas(24, 16)
    dx, dy = SHAKE["side"][f]

    def body(t, x, y):
        fist(t, 5 + x, 6 + y)
        box(t, 7 + x, 4 + y, 4, 6, WHITE, cut=1)              # módulo branco em volta da mão
        t.vline(8 + x, 4 + y, 6, ORANGE)                      # cinta laranja
        t.px(8 + x, 4 + y, ORANGE_L)
        t.px(10 + x, 5 + y, CYAN_L if f % 2 == 0 else CYAN)
        box(t, 11 + x, 5 + y, 1, 4, DARK)                     # colar
        cone_side(t, 12 + x, 17 + x, 7 + y, 1.8, f)
    layer(c, body, dx, dy)
    TIP["C_side"] = (17, 7)
    return c


def c_down(f):
    c = Canvas(16, 24)
    dx, dy = SHAKE["down"][f]

    def body(t, x, y):
        fist(t, 6 + x, 2 + y)
        box(t, 5 + x, 4 + y, 5, 4, WHITE, cut=1)
        t.hline(5 + x, 5 + y, 5, ORANGE)
        t.px(5 + x, 5 + y, ORANGE_L)
        t.px(8 + x, 6 + y, CYAN_L if f % 2 == 0 else CYAN)
        box(t, 6 + x, 8 + y, 3, 1, DARK)
        cone_vert(t, 9 + y, 14 + y, 7 + x, 1.8, f)
    layer(c, body, dx, dy)
    TIP["C_down"] = (7, 14)
    return c


def c_up(f):
    c = Canvas(16, 24)
    dx, dy = SHAKE["up"][f]

    def body(t, x, y):
        box(t, 2 + x, 12 + y, 5, 5, WHITE, cut=1)             # atrás do ombro
        t.hline(2 + x, 14 + y, 5, ORANGE)
        box(t, 3 + x, 11 + y, 3, 1, DARK)
        cone_vert(t, 10 + y, 5 + y, 4 + x, 1.8, f)
    layer(c, body, dx, dy)
    TIP["C_up"] = (4, 5)
    return c


FUNCS = {"A": (a_side, a_down, a_up), "B": (b_side, b_down, b_up), "C": (c_side, c_down, c_up)}
NAMES = {"A": "furadeira de bolso", "B": "caneta-broca", "C": "broca de punho"}


def make_drill(cand: str, view: str) -> Canvas:
    fn = dict(zip(("side", "down", "up"), FUNCS[cand]))[view]
    return strip([fn(f) for f in range(4)])


# ---------------------------------------------------------------- prévia: broca na mão do explorador
GRIP = {"side": ((12, 13), False), "down": ((13, 16), False), "up": ((20, 4), True)}   # = DRILL_GRIP do render.py
CELL, PAD = (44, 44), (4, 2)            # célula da prévia e onde o quadro 32×32 do player cai nela


def compose(player_sheet, drill_sheet, view):
    """Folha PIL 4×(44×44): player_mine quadro f + broca quadro f no DRILL_GRIP, na ordem do jogo."""
    from PIL import Image
    (gx, gy), behind = GRIP[view]
    fw = drill_sheet.width // 4
    out = Image.new("RGBA", (CELL[0] * 4, CELL[1]), (0, 0, 0, 0))
    for f in range(4):
        cell = Image.new("RGBA", CELL, (0, 0, 0, 0))
        p = player_sheet.crop((32 * f, 0, 32 * f + 32, 32))
        d = drill_sheet.crop((fw * f, 0, fw * f + fw, drill_sheet.height))
        if behind:
            cell.alpha_composite(d, (PAD[0] + gx, PAD[1] + gy))
        cell.alpha_composite(p, PAD)
        if not behind:
            cell.alpha_composite(d, (PAD[0] + gx, PAD[1] + gy))
        out.alpha_composite(cell, (CELL[0] * f, 0))
    return out
