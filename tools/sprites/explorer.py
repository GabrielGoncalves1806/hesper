"""Explorador 32×32 (v6.0, aprovado pelo dono com a paleta VISOR DOURADO): rig de peças desenhadas à mão,
3 vistas, animações de caminhada, parado (idle) e minerando (mine).

Veio da sessão experimental (gerador/explorer.py + o que ele usava do common.py) e agora é autocontido:
não depende de nada fora desta pasta. O build_sprites.py importa daqui e converte pro Canvas dele.

Peças: capacete em domo com visor em faixa (reflexo duro, sem "olhão"), lanterna presa na lateral,
antena, ombreiras e joelheiras de metal, cinto com bolsa, botas com poeira vermelha, mochila com tanques
e o cachecol cor de ferrugem que balança. Cada peça é desenhada numa camada própria e contornada, então
a da frente separa a de trás. Pé na linha 30 (igual ao jogo: sombra 16×5 em y-5). Luz de cima-esquerda.
"""
import numpy as np

OUTLINE = "#1b1630"
CYAN = "#59d0e6"


def rgb(c):
    if isinstance(c, tuple):
        return c if len(c) == 4 else (*c, 255)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


class Canvas:
    """Canvas mínimo do gerador do explorador (o mesmo do experimento): alpha só 0/255, blit sólido."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = rgb(c)

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.px(xx, yy, c)

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def blit(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                if other.a[y, x, 3] == 255:
                    self.px(x + ox, y + oy, tuple(int(v) for v in other.a[y, x]))

    def outline(self, c=OUTLINE):
        """Contorno externo de 1 px (4-vizinhos) em volta de tudo que é opaco."""
        sol = self.a[:, :, 3] == 255
        add = np.zeros_like(sol)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            sh = np.zeros_like(sol)
            ys = slice(max(dy, 0), self.h + min(dy, 0))
            yd = slice(max(-dy, 0), self.h + min(-dy, 0))
            xs = slice(max(dx, 0), self.w + min(dx, 0))
            xd = slice(max(-dx, 0), self.w + min(-dx, 0))
            sh[yd, xd] = sol[ys, xs]
            add |= sh
        add &= ~sol
        self.a[add] = rgb(c)

    def flip(self):
        c = Canvas(self.w, self.h)
        c.a = self.a[:, ::-1].copy()
        return c


def strip(frames):
    w, h = frames[0].w, frames[0].h
    s = Canvas(w * len(frames), h)
    for i, f in enumerate(frames):
        s.blit(f, i * w, 0)
    return s

PALETTES = {
    # padrão: visor azul-marinho (o aprovado), acento laranja da família das máquinas
    "explorador": dict(
        suit=["#f1ece2", "#d6cec4", "#aaa0a0", "#7b707c"],
        plate=["#a6a1b8", "#77728a", "#565168", "#3c3749"],
        acc=["#f4a06a", "#e2733a", "#a9482a"],
        scarf=["#ea8a5e", "#c4563a", "#8e3a2c"],
        visor=["#121834", "#26387a", "#6a93e0", "#eef6ff"],
        boot=["#5f586e", "#3f3a4c", "#2f2a3a", "#221e2b"],
        dust="#9a5a40", lamp=["#fffbe0", "#ffd36b"], tip="#ff6a55",
    ),
}
# variante: visor dourado refletivo (EVA de verdade)
PALETTES["visor_dourado"] = dict(PALETTES["explorador"], visor=["#4a2e10", "#9a6a28", "#f2c46d", "#fff4cc"])
# variante: o vermelho original da spec no lugar do laranja
PALETTES["acento_vermelho"] = dict(PALETTES["explorador"], acc=["#f08a86", "#dc4a4f", "#962f3f"],
                                   scarf=["#e07a6a", "#b8434a", "#7e2c36"])

MAIN = "visor_dourado"   # paleta aprovada pelo dono (v6.0)
P = PALETTES[MAIN]


def use(name):
    global P
    P = PALETTES[name]


# ---------------------------------------------------------------------------
# primitivas
# ---------------------------------------------------------------------------
def box(cv, x, y, w, h, t, cut=0):
    """Caixa sombreada: brilho em cima/esquerda, sombra à direita/embaixo. t = [brilho, base, meio, escuro]."""
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            i, j = xx - x, yy - y
            if cut and ((i < cut and j < cut - i) or (i >= w - cut and j < cut - (w - 1 - i)) or
                        (i < cut and j >= h - (cut - i)) or (i >= w - cut and j >= h - (cut - (w - 1 - i)))):
                continue
            if i >= w - 1 and w > 2:
                c = t[3]
            elif i >= w - 2 and w > 3:
                c = t[2]
            elif j == 0 or i == 0:
                c = t[0]
            elif j == h - 1 and h > 2:
                c = t[2]
            else:
                c = t[1]
            cv.px(xx, yy, c)


def layer(cv, draw, outline=True):
    tmp = Canvas(cv.w, cv.h)
    draw(tmp)
    if outline:
        tmp.outline()
    cv.blit(tmp, 0, 0)


DARK_SUIT = None


def dsuit():
    s = P["suit"]
    return [s[2], s[2], s[3], s[3]]


# domo do capacete 14×12: largura por linha (simétrico)
DOME = [(4, 10), (2, 12), (1, 13), (0, 14), (0, 14), (0, 14), (0, 14), (0, 14), (0, 14), (0, 14), (1, 13), (2, 12)]


def dome(c, x, y, t=None):
    """Casco em domo com sombreamento esférico em 4 faixas (luz de cima-esquerda)."""
    t = t or P["suit"]
    for j, (a, b) in enumerate(DOME):
        for i in range(a, b):
            u, v = (i + 0.5 - 7) / 7, (j + 0.5 - 6) / 6
            lum = -(u * 0.62 + v * 0.78) + 0.35 * (1 - (u * u + v * v))
            c.px(x + i, y + j, t[0] if lum > 0.45 else t[1] if lum > -0.05 else t[2] if lum > -0.5 else t[3])


def in_dome(i, j):
    return 0 <= j < len(DOME) and DOME[j][0] <= i < DOME[j][1]


def leg_front(c, x, top, lift, dark=False):
    """Perna vista de frente/costas: 4 de largura, joelheira de metal, bota 5 com poeira."""
    t = dsuit() if dark else P["suit"]
    foot = 30 + lift
    box(c, x, top, 4, foot - 2 - top, t)
    box(c, x, top + 2, 4, 2, P["plate"])
    bx = x - (1 if x < 16 else 0)
    box(c, bx, foot - 2, 5, 3, P["boot"])
    for i in range(1, 4):
        c.px(bx + i, foot, P["dust"])


def scarf_wrap(c, x0, x1, y):
    for xx in range(x0, x1 + 1):
        u = (xx - x0) / max(1, x1 - x0)
        c.px(xx, y, P["scarf"][0] if u < 0.35 else P["scarf"][1])
        c.px(xx, y + 1, P["scarf"][1] if u < 0.7 else P["scarf"][2])


def scarf_tail(c, pts):
    """Rabo do cachecol: lista de (x, y, largura). Ponta desfiada no fim."""
    for (x, y, w) in pts:
        for i in range(w):
            c.px(x + i, y, P["scarf"][1] if i == 0 else P["scarf"][2])
    x, y, w = pts[-1]
    c.px(x, y + 1, P["scarf"][2])


# ---------------------------------------------------------------------------
# vista de frente
# ---------------------------------------------------------------------------
def down_frame(bob=0, legL=0, legR=0, armL=0, armR=0, sway=0, pose="stand", blink=False):
    cv = Canvas(32, 32)
    b = bob
    # topo dos tanques da mochila aparecendo por cima dos ombros
    layer(cv, lambda c: (box(c, 8, 13 + b, 3, 4, P["plate"]), box(c, 21, 13 + b, 3, 4, P["plate"]),
                         c.px(9, 13 + b, P["acc"][1]), c.px(22, 13 + b, P["acc"][2])))
    layer(cv, lambda c: leg_front(c, 11, 24, legL))
    layer(cv, lambda c: leg_front(c, 17, 24, legR))

    def torso(c):
        box(c, 11, 16 + b, 10, 8, P["suit"])
        box(c, 15, 19 + b, 4, 3, P["plate"])           # painelzinho com LED
        c.px(16, 20 + b, CYAN)
        c.px(17, 20 + b, P["acc"][1])
        box(c, 11, 23 + b, 10, 2, P["plate"])          # cinto
        c.px(15, 23 + b, P["acc"][0])
        c.px(16, 23 + b, P["acc"][1])
    layer(cv, torso)
    layer(cv, lambda c: (box(c, 18, 23 + b, 3, 3, P["plate"]), c.px(19, 24 + b, P["acc"][2])))   # bolsa

    def arms(c):
        box(c, 8, 17 + b, 3, 5 + armL, P["suit"])
        box(c, 8, 22 + b + armL, 3, 2, P["boot"])
        if pose == "mine":                              # braço direito puxado pra frente, na broca
            box(c, 20, 17 + b, 3, 3, dsuit())
            box(c, 19, 19 + b, 3, 2, P["boot"])
        else:
            box(c, 21, 17 + b, 3, 5 + armR, dsuit())
            box(c, 21, 22 + b + armR, 3, 2, P["boot"])
    layer(cv, arms)
    layer(cv, lambda c: (box(c, 7, 15 + b, 5, 3, P["plate"], cut=1), box(c, 20, 15 + b, 5, 3, P["plate"], cut=1),
                         c.hline(8, 16 + b, 2, P["acc"][1]), c.hline(21, 16 + b, 2, P["acc"][2])))

    def scarf(c):
        scarf_wrap(c, 11, 20, 14 + b)
        scarf_tail(c, [(11, 16 + b, 3), (11, 17 + b, 2), (11 + (sway > 0), 18 + b, 2), (11 + sway, 19 + b, 2)])
    layer(cv, scarf)

    def head(c):
        x, y = 9, 2 + b
        dome(c, x, y)
        v = P["visor"]
        # visor em faixa envolvente: linhas 4-8, acompanhando o domo
        for j in range(4, 9):
            for i in range(1, 13):
                if j == 8 and (i < 3 or i > 10):
                    continue
                c.px(x + i, y + j, v[1] if j == 4 else v[0])
        c.hline(x + 1, y + 3, 12, P["plate"][1])        # aro de metal em cima do visor
        c.px(x + 1, y + 3, P["plate"][0])
        # reflexo duro na diagonal: lê como vidro, não como olho
        for (dx, dy) in ((3, 8), (4, 7), (5, 6), (6, 5)):
            c.px(x + dx, y + dy, v[2])
        c.px(x + 7, y + 5, v[2])
        c.px(x + 7, y + 4, v[3])
        c.px(x + 10, y + 7, v[1])
        # queixo com respiro
        c.hline(x + 5, y + 10, 4, P["plate"][2])
        c.px(x + 6, y + 10, P["plate"][3])
        c.px(x + 8, y + 10, P["plate"][3])
        # lanterna presa na lateral esquerda do capacete
        box(c, x - 1, y + 3, 3, 3, P["plate"])
        c.px(x, y + 4, P["lamp"][1] if blink else P["lamp"][0])
    layer(cv, head)
    layer(cv, lambda c: (c.vline(21, 0 + b, 3, P["plate"][1]), c.px(21, 0 + b, P["tip"])), outline=False)
    return cv


# ---------------------------------------------------------------------------
# vista de costas
# ---------------------------------------------------------------------------
def up_frame(bob=0, legL=0, legR=0, armL=0, armR=0, sway=0, pose="stand", blink=False):
    cv = Canvas(32, 32)
    b = bob
    layer(cv, lambda c: leg_front(c, 11, 24, legL))
    layer(cv, lambda c: leg_front(c, 17, 24, legR))
    layer(cv, lambda c: (box(c, 11, 16 + b, 10, 8, P["suit"]), box(c, 11, 23 + b, 10, 2, P["plate"])))
    up = -2 if pose == "mine" else 0
    layer(cv, lambda c: (box(c, 8, 17 + b + up, 3, 5 + armL, P["suit"]), box(c, 8, 22 + b + armL + up, 3, 2, P["boot"]),
                         box(c, 21, 17 + b + up, 3, 5 + armR, dsuit()), box(c, 21, 22 + b + armR + up, 3, 2, P["boot"])))

    def pack(c):            # mochila com 2 tanques
        box(c, 10, 14 + b, 12, 11, P["boot"], cut=1)
        for tx in (11, 17):
            box(c, tx, 15 + b, 4, 8, P["plate"])
            c.hline(tx, 17 + b, 4, P["acc"][1])
            c.px(tx, 17 + b, P["acc"][0])
        c.rect(15, 17 + b, 2, 3, P["plate"][3])
        c.px(15, 18 + b, CYAN)
    layer(cv, pack)
    layer(cv, lambda c: (box(c, 7, 15 + b, 5, 3, P["plate"], cut=1), box(c, 20, 15 + b, 5, 3, P["plate"], cut=1)))

    def head(c):
        x, y = 9, 2 + b
        dome(c, x, y)
        c.hline(x, y + 5, 14, P["plate"][1])            # alça da lanterna
        c.hline(x, y + 6, 14, P["plate"][2])
        box(c, x + 5, y + 7, 4, 3, P["plate"], cut=1)   # respiro na nuca
        c.px(x + 6, y + 8, P["acc"][1])
        box(c, x + 13, y + 4, 2, 3, P["plate"])         # lanterna vista por trás
    layer(cv, head)
    layer(cv, lambda c: (scarf_wrap(c, 11, 20, 14 + b),
                         scarf_tail(c, [(14, 16 + b, 3), (14 + (sway > 0), 17 + b, 2), (14 + sway, 18 + b, 2),
                                        (15 + sway, 19 + b, 2)])))
    layer(cv, lambda c: (c.vline(10, 0 + b, 3, P["plate"][1]), c.px(10, 0 + b, P["tip"])), outline=False)
    return cv


# ---------------------------------------------------------------------------
# vista de lado (olhando pra direita)
# ---------------------------------------------------------------------------
TAILS = [   # rabo do cachecol voando pra trás, 4 fases (ondula na caminhada)
    [(8, 15, 2), (6, 16, 3), (4, 16, 2), (3, 17, 2)],
    [(8, 15, 2), (6, 15, 3), (4, 16, 2), (2, 16, 2)],
    [(8, 15, 2), (6, 16, 3), (4, 17, 2), (3, 18, 2)],
    [(8, 15, 2), (7, 16, 2), (5, 17, 2), (4, 18, 2)],
]
TAIL_IDLE = [(8, 15, 2), (8, 16, 2), (7, 17, 2), (7, 18, 2), (7, 19, 2)]
TAIL_IDLE2 = [(8, 15, 2), (8, 16, 2), (7, 17, 2), (6, 18, 2), (6, 19, 2)]


def _side_leg(c, top, x0, dx, front):
    t = P["suit"] if front else dsuit()
    rows = list(range(top, 28))
    for i, r in enumerate(rows):
        x = x0 + round(dx * i / len(rows))
        knee = i == len(rows) // 2
        for k in range(3):
            if knee:
                c.px(x + k, r, (P["plate"][0] if k == 0 else P["plate"][1]) if front else P["plate"][2])
            else:
                c.px(x + k, r, t[0] if k == 0 else t[1] if k == 1 else t[2])
    bx = x0 + dx
    bt = P["boot"] if front else [P["boot"][1], P["boot"][1], P["boot"][2], P["boot"][3]]
    box(c, bx - 1, 28, 6, 3, bt)
    for i in range(1, 5):
        c.px(bx - 1 + i, 30, P["dust"])


def side_frame(bob=0, stride=0, arm=0, tail=None, pose="stand", blink=False, shake=0):
    cv = Canvas(32, 32)
    b, sx = bob, shake
    tail = tail if tail is not None else TAIL_IDLE
    layer(cv, lambda c: scarf_tail(c, [(x + sx, y + b, w) for (x, y, w) in tail]))

    def pack(c):
        box(c, 6 + sx, 14 + b, 5, 11, P["boot"], cut=1)
        box(c, 7 + sx, 15 + b, 3, 8, P["plate"])
        c.hline(7 + sx, 17 + b, 3, P["acc"][1])
    layer(cv, pack)
    layer(cv, lambda c: _side_leg(c, 24, 14, -stride, front=False))
    if pose != "mine":
        layer(cv, lambda c: (box(c, 15 - arm + sx, 17 + b, 3, 5, dsuit()), box(c, 15 - arm + sx, 22 + b, 3, 2, P["boot"])))
    layer(cv, lambda c: (box(c, 11 + sx, 16 + b, 8, 8, P["suit"]), c.hline(11 + sx, 19 + b, 7, P["acc"][1]),
                         box(c, 11 + sx, 23 + b, 8, 2, P["plate"]), c.px(17 + sx, 23 + b, P["acc"][1])))
    layer(cv, lambda c: (box(c, 10 + sx, 22 + b, 3, 3, P["plate"]), c.px(11 + sx, 23 + b, P["acc"][2])))   # bolsa
    layer(cv, lambda c: _side_leg(c, 24, 13, stride, front=True))

    def front_arm(c):
        if pose == "mine":      # braço esticado pra frente, mão na pega da broca
            box(c, 13 + sx, 17 + b, 3, 3, P["suit"])
            box(c, 15 + sx, 19 + b, 3, 2, P["suit"])
            box(c, 17 + sx, 19 + b, 3, 3, P["boot"])
        else:
            box(c, 13 + arm + sx, 17 + b, 3, 5, P["suit"])
            box(c, 13 + arm + sx, 22 + b, 3, 2, P["boot"])
    layer(cv, front_arm)
    layer(cv, lambda c: (box(c, 12 + sx, 15 + b, 5, 3, P["plate"], cut=1), c.hline(13 + sx, 16 + b, 2, P["acc"][1])))
    layer(cv, lambda c: scarf_wrap(c, 11 + sx, 18 + sx, 14 + b))

    def head(c):
        x, y = 8 + sx, 2 + b
        dome(c, x, y)
        v = P["visor"]
        # visor na frente, acompanhando a curva do domo
        for j in range(4, 9):
            for i in range(7, 14):
                if in_dome(i, j) and not (j == 8 and i < 9):
                    c.px(x + i, y + j, v[1] if j == 4 else v[0])
        c.hline(x + 7, y + 3, 7, P["plate"][1])
        for (dx, dy) in ((9, 8), (10, 7), (11, 6), (12, 5)):
            c.px(x + dx, y + dy, v[2])
        c.px(x + 12, y + 4, v[3])
        c.hline(x + 9, y + 10, 3, P["plate"][2])         # queixo
        # emenda do casco (nada de "olho" na nuca) + lanterna presa em cima
        for j in range(2, 10):
            c.px(x + 4 + (j > 6), y + j, P["suit"][2])
        box(c, x + 5, y + 1, 4, 3, P["plate"])
        c.px(x + 8, y + 2, P["lamp"][1] if blink else P["lamp"][0])
    layer(cv, head)
    layer(cv, lambda c: (c.vline(10 + sx, 0 + b, 3, P["plate"][1]), c.px(10 + sx, 0 + b, P["tip"])), outline=False)
    return cv


# ---------------------------------------------------------------------------
# folhas (contrato + propostas)
# ---------------------------------------------------------------------------
def make_player(view):
    return {"down": down_frame, "up": up_frame, "side": side_frame}[view]()


def make_walk(view):
    if view == "side":
        return strip([side_frame(0, 3, 2, TAILS[0]), side_frame(-1, 0, 0, TAILS[1]),
                      side_frame(0, -3, -2, TAILS[2]), side_frame(-1, 0, 0, TAILS[3])])
    f = down_frame if view == "down" else up_frame
    return strip([f(0, -1, 0, 1, -1, 1), f(-1, 0, 0, 0, 0, 0), f(0, 0, -1, -1, 1, -1), f(-1, 0, 0, 0, 0, 0)])


def make_idle(view):
    """Parado (idle): respiração lenta, cachecol mexendo, lanterna piscando. 4 quadros, ~4 fps."""
    if view == "side":
        return strip([side_frame(0), side_frame(0, tail=TAIL_IDLE2), side_frame(1, blink=True),
                      side_frame(1, tail=TAIL_IDLE2)])
    f = down_frame if view == "down" else up_frame
    return strip([f(0), f(0, sway=1), f(1, blink=True), f(1, sway=1)])


def make_mine(view):
    """Minerando: pose segurando a broca, com tranco do recuo. 4 quadros, junto da broca (14 fps)."""
    if view == "side":
        return strip([side_frame(0, 1, pose="mine"), side_frame(0, 1, pose="mine", shake=-1, tail=TAIL_IDLE2),
                      side_frame(0, 1, pose="mine"), side_frame(1, 1, pose="mine", shake=-1, tail=TAIL_IDLE2)])
    f = down_frame if view == "down" else up_frame
    return strip([f(0, pose="mine"), f(1, pose="mine"), f(0, pose="mine", sway=1), f(1, pose="mine", sway=1)])
