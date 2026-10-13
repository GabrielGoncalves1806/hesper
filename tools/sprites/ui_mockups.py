#!/usr/bin/env python3
"""Mockups do redesign da UI do Hesper: 3 direções visuais, pixel de verdade.

    python3 tools/sprites/ui_mockups.py

Monta tudo em "px da UI" (480×270, o tamanho Grande do jogo) e estica 2× pra 960×540, igual ao
ui.finish() do jogo. Ícones e prévias de máquina vão na camada "native" (1 px de imagem = 1 px da
tela 960×540), igual à lista `native` do game/ui.py. Fontes reais (game/fonts), sprites reais
(assets/sprites) e o mundo/ícones capturados do jogo em reports/design/ui_redesign/_src/
(gerados por tools/sprites/ui_capture.py, que roda com uv).

Saídas:
  reports/design/ui_redesign/{a,b,c}_{hud,inventario,fabricar,fabricador,bau,opcoes,componentes}.png
  reports/design/ui_redesign/before_*.png (cópias dos prints atuais do smoke)
  assets/sprites/_pending/ui/*.png (molduras/9-slices que as direções usariam)
Determinístico: sem aleatório nenhum (os "ruídos" saem de contas fixas).
"""

import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "reports" / "design" / "ui_redesign" / "_src"
OUT = ROOT / "reports" / "design" / "ui_redesign"
SPR = ROOT / "assets" / "sprites"
PEND = SPR / "_pending" / "ui"
FONTS = ROOT / "game" / "fonts"
K = 2                      # px da tela por px da UI (Grande numa tela 960×540)
UW, UH = 480, 270

# ---- cores da bíblia (§3) --------------------------------------------------------------------
C_O2, C_ACCENT, C_TI, C_OK, C_ALERT = "#59d0e6", "#e2733a", "#f2c46d", "#7fd67a", "#ff6a55"
C_TEXT, C_MUTED, C_OUT = "#efe5da", "#9c8d82", "#1b1630"
C_HEAT, C_WATER, C_ENERGY = "#e2733a", "#4f9de0", "#ffd84a"
RES_COLOR = {"iron": "#e8a066", "silicon": "#c3d1e2", "ice": "#a6ecff"}


def rgba(c, a=255):
    if isinstance(c, tuple):
        return c if len(c) == 4 else (*c, a)
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a


def mix(c1, c2, t):
    a, b = rgba(c1), rgba(c2)
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


# ---- fonte pixel (cópia do PixelFont do game/ui.py: dígitos e subscrito desenhados) -----------
DIGITS = {
    "0": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
}
SUB2 = {4: ["## ", "  #", " # ", "###"], 5: ["## ", "  #", " # ", "#  ", "###"]}


class PFont:
    def __init__(self, file, size, digits):
        self.f = ImageFont.truetype(str(FONTS / file), size, layout_engine=ImageFont.Layout.BASIC)
        self.digits = digits
        asc, desc = self.f.getmetrics()
        self.asc, self.h = asc, asc + desc
        self.digit_top = max(0, asc - 7)
        m = Image.new("L", (40, 40))
        d = ImageDraw.Draw(m)
        d.fontmode = "1"
        d.text((0, 0), "O", font=self.f, fill=255)
        bb = m.getbbox()
        cap_top, cap_bottom = bb[1], bb[3] - 1
        cap = cap_bottom - cap_top + 1
        self.sub_scale = max(1, round(cap / 6))
        self.sub_rows = 4 if cap / self.sub_scale <= 5 else 5
        self.sub_top = cap_bottom + self.sub_scale - self.sub_rows * self.sub_scale + 1
        self.sub_adv = 3 * self.sub_scale + 1

    def kind(self, ch):
        if ch == "₂":
            return "sub"
        if ch == "~" and self.digits:
            return "tilde"
        if self.digits and ch in DIGITS:
            return "digit"
        return "text"

    def runs(self, s):
        out = []
        for ch in s:
            if out and self.kind(out[-1][-1]) == self.kind(ch):
                out[-1] += ch
            else:
                out.append(ch)
        return out

    def run_w(self, r):
        k = self.kind(r[0])
        if k == "digit":
            return 7 * len(r)
        if k == "sub":
            return self.sub_adv * len(r)
        if k == "tilde":
            return 8 * len(r)
        return round(self.f.getlength(r))

    def width(self, s):
        return sum(self.run_w(r) for r in self.runs(s))

    def mask(self, s):
        w = max(1, self.width(s)) + 2
        m = Image.new("L", (w, self.h + 2))
        d = ImageDraw.Draw(m)
        d.fontmode = "1"
        x = 0
        for r in self.runs(s):
            k = self.kind(r[0])
            if k == "text":
                d.text((x, 0), r, font=self.f, fill=255)
                x += self.run_w(r)
                continue
            if k == "tilde":
                for _ in r:
                    for dx, dy in [(0, 1), (1, 0), (2, 0), (3, 1), (4, 1), (5, 0)]:
                        d.point((x + dx, 6 + dy), 255)
                    x += 8
                continue
            for ch in r:
                if k == "digit":
                    glyph, top, sc, ox = DIGITS[ch], self.digit_top, 1, x + 1
                else:
                    glyph, top, sc, ox = SUB2[self.sub_rows], self.sub_top, self.sub_scale, x
                for dy, row in enumerate(glyph):
                    for dx, cell in enumerate(row):
                        if cell == "#":
                            d.rectangle((ox + dx * sc, top + dy * sc, ox + dx * sc + sc - 1, top + dy * sc + sc - 1), 255)
                x += 7 if k == "digit" else self.sub_adv
        return m


F = PFont("Silkscreen-Regular.ttf", 8, False)        # rótulos
FB = PFont("Silkscreen-Regular.ttf", 16, False)      # títulos grandes
P = PFont("PixelifySans.ttf", 11, True)              # textos


# ---- contexto de desenho: coordenadas em px da UI, imagem em px da tela ----------------------
class Ctx:
    def __init__(self, bg=None, size=(960, 540)):
        self.img = bg.convert("RGBA").copy() if bg is not None else Image.new("RGBA", size, (0, 0, 0, 0))

    def fill(self, x, y, w, h, c):
        if w <= 0 or h <= 0:
            return
        c = rgba(c)
        if c[3] == 0:
            return
        if c[3] == 255:
            self.img.paste(c, (x * K, y * K, (x + w) * K, (y + h) * K))
        else:
            self.img.alpha_composite(Image.new("RGBA", (w * K, h * K), c), (x * K, y * K))

    def px(self, x, y, c):
        self.fill(x, y, 1, 1, c)

    def rect(self, x, y, w, h, c, t=1):
        self.fill(x, y, w, t, c)
        self.fill(x, y + h - t, w, t, c)
        self.fill(x, y + t, t, h - 2 * t, c)
        self.fill(x + w - t, y + t, t, h - 2 * t, c)

    def round_rect(self, x, y, w, h, c, border=None):
        """Retângulo com o pixel de cada canto cortado (o "arredondado" da pixel art)."""
        self.fill(x + 1, y, w - 2, h, c)
        self.fill(x, y + 1, 1, h - 2, c)
        self.fill(x + w - 1, y + 1, 1, h - 2, c)
        if border:
            self.fill(x + 1, y, w - 2, 1, border)
            self.fill(x + 1, y + h - 1, w - 2, 1, border)
            self.fill(x, y + 1, 1, h - 2, border)
            self.fill(x + w - 1, y + 1, 1, h - 2, border)

    def chamfer(self, x, y, w, h, c, cut=4, border=None):
        """Painel com os cantos cortados a 45° (estilo visor)."""
        for i in range(h):
            inset = max(0, cut - i, cut - (h - 1 - i))
            self.fill(x + inset, y + i, w - 2 * inset, 1, c)
        if border:
            for i in range(h):
                inset = max(0, cut - i, cut - (h - 1 - i))
                if i == 0 or i == h - 1:
                    self.fill(x + inset, y + i, w - 2 * inset, 1, border)
                else:
                    self.px(x + inset, y + i, border)
                    self.px(x + w - 1 - inset, y + i, border)
                    if inset > 0:                      # diagonal contínua
                        pass

    def text(self, s, x, y, c, font=None, align="left", shadow=True, outline=None, alpha=255):
        font = font or F
        m = font.mask(s)
        w = font.width(s)
        x = x - w if align == "right" else x - w // 2 if align == "center" else x
        x, y = int(x), int(y)
        big = m.resize((m.width * K, m.height * K), Image.NEAREST)
        if outline:
            oc = rgba(outline)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                self.img.paste(oc, ((x + dx) * K, (y + dy) * K), big)
        elif shadow:
            sm = big.point(lambda v: 165 if v else 0)
            self.img.paste((0, 0, 0, 255), ((x + 1) * K, (y + 1) * K), sm)
        col = rgba(c)
        if alpha < 255:
            big = big.point(lambda v: alpha if v else 0)
        self.img.paste(col, (x * K, y * K), big)
        return w

    def native(self, im, nx, ny):
        im = im.convert("RGBA")
        self.img.alpha_composite(im, (int(nx), int(ny)))

    def icon(self, im, x, y):
        """Imagem na camada native, posicionada em px da UI."""
        self.native(im, x * K, y * K)

    def blit_ui(self, im, x, y):
        """Imagem desenhada em px da UI (moldura, 9-slice): esticada 2× sem suavizar."""
        im = im.convert("RGBA")
        self.img.alpha_composite(im.resize((im.width * K, im.height * K), Image.NEAREST), (x * K, y * K))

    def nine(self, sprite, x, y, w, h, b):
        self.blit_ui(nine_slice(sprite, w, h, b), x, y)


def nine_slice(sp, w, h, b):
    """9-slice: cantos fixos, bordas e miolo repetidos (repetição, não esticamento: textura fica nítida)."""
    sw, sh = sp.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def tile(src, dx, dy, dw, dh):
        if dw <= 0 or dh <= 0 or src.width == 0 or src.height == 0:
            return
        for yy in range(0, dh, src.height):
            for xx in range(0, dw, src.width):
                piece = src.crop((0, 0, min(src.width, dw - xx), min(src.height, dh - yy)))
                out.paste(piece, (dx + xx, dy + yy))

    c = sp.crop
    tile(c((0, 0, b, b)), 0, 0, b, b)
    tile(c((sw - b, 0, sw, b)), w - b, 0, b, b)
    tile(c((0, sh - b, b, sh)), 0, h - b, b, b)
    tile(c((sw - b, sh - b, sw, sh)), w - b, h - b, b, b)
    tile(c((b, 0, sw - b, b)), b, 0, w - 2 * b, b)
    tile(c((b, sh - b, sw - b, sh)), b, h - b, w - 2 * b, b)
    tile(c((0, b, b, sh - b)), 0, b, b, h - 2 * b)
    tile(c((sw - b, b, sw, sh - b)), w - b, b, b, h - 2 * b)
    tile(c((b, b, sw - b, sh - b)), b, b, w - 2 * b, h - 2 * b)
    return out


# ---- insumos ------------------------------------------------------------------------------------
def load(path):
    return Image.open(path).convert("RGBA")


WORLD = {k: load(SRC / f"world_{k}.png") for k in ("dead", "mist")}
MINI = load(SRC / "minimap_tex.png")
_cache = {}


def item(kind):
    """Ícone 32×32 de item (como na hotbar do jogo)."""
    if kind not in _cache:
        _cache[kind] = load(SRC / f"item_{kind}.png")
    return _cache[kind]


def icon16(res):
    return load(SPR / f"icon_{res}.png")


def preview(kind):
    return load(SRC / f"prev_{kind}.png")


MACHINES = {}
for line in (SRC / "machines.txt").read_text().splitlines():
    k, name, desc, unlock, cost = line.split("|")
    MACHINES[k] = dict(name=name, desc=desc, unlock=int(unlock), cost=eval(cost))   # noqa: S307 (arquivo nosso)

# ---- o "estado" mostrado nos mockups ----------------------------------------------------------
TI = 4812
TI_RATE = 12
INDICES = [("o2", "O₂", "2.940", "PPQ", C_O2), ("heat", "CALOR", "1.020", "PK", C_HEAT),
           ("water", "ÁGUA", "852", "PPM", C_WATER)]
NEXT_STAGE, NEXT_PCT, REMAINING, ETA = "NÉVOA", 0.48, "5.188", "~7 min"
O2_SECONDS, O2_MAX = 158, 220
ENERGY = (5, 4)
HOTBAR = [("iron", 42), ("silicon", 6), ("ice", 25), ("o2", 2), ("chest", 1), ("lamp", 3), None, None]
BACKPACK = [("iron", 50), ("ice", 18), ("solar", 1), None, None, None, None, None]
HOT_SEL = 3
HAVE = {"iron": 92, "silicon": 6, "ice": 43}
CHEST = [("iron", 50), ("iron", 50), ("iron", 38), ("silicon", 22), ("ice", 50), ("ice", 31)] + [None] * 18
OBJECTIVES = [("current", "Fabrique um Aquecedor"), ("next", "Chegue a Ti 10.000")]
HINT = "[E] Abrir baú: Minérios"
RES = ("iron", "silicon", "ice")
RES_NAME = {"iron": "Ferro", "silicon": "Silício", "ice": "Gelo"}
RES_LABEL = {"iron": "FERRO", "silicon": "SILÍCIO", "ice": "GELO"}
USE_KW = {"o2": 1, "melter": 1, "heater": 2, "o2_t2": 3, "melter_t2": 3, "heater_t2": 4, "drill": 2,
          "drone_station": 1}
FAB_TABS = ["Terraformação", "Energia", "Automação", "Armazenamento", "Luz", "Traje"]
TAB_KINDS = ["o2", "melter", "heater", "o2_t2", "melter_t2", "heater_t2"]
TAB_ICON = ["o2", "solar", "drill", "chest", "lamp", "o2_tank"]
FIELD_KINDS = ["chest", "lamp", "lamp_t2", "drill"]
FIELD_HAVE = {"iron": 42, "silicon": 6, "ice": 25}
SEL_RECIPE = 2                        # o Aquecedor (falta silício) fica selecionado: mostra o estado "falta"


def status(kind, have=HAVE):
    m = MACHINES[kind]
    if m["unlock"] > TI:
        return "locked"
    if any(have[r] < n for r, n in m["cost"].items()):
        return "missing"
    return "ok"


def fmt(n):
    return f"{n:,}".replace(",", ".")


def ti_parts():
    return fmt(TI)


def bolt(ctx, x, y, c, shadow=True):
    rows = ["  ###", " ### ", " ##  ", "#####", "  ## ", " ##  ", " #   ", "#    "]
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == "#":
                if shadow:
                    ctx.px(x + dx + 1, y + dy + 1, (0, 0, 0, 255))
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == "#":
                ctx.px(x + dx, y + dy, c)


def check(ctx, x, y, c):
    for dx, dy in [(0, 2), (1, 3), (2, 4), (3, 3), (4, 2), (5, 1), (6, 0)]:
        ctx.px(x + dx, y + dy, c)
        ctx.px(x + dx, y + dy + 1, c)


def cross(ctx, x, y, c):
    for i in range(5):
        ctx.px(x + i, y + i, c)
        ctx.px(x + 4 - i, y + i, c)


def lock(ctx, x, y, c):
    ctx.rect(x + 1, y, 5, 4, c)
    ctx.fill(x, y + 3, 7, 5, c)
    ctx.px(x + 3, y + 5, (0, 0, 0, 255))


def stack_count(ctx, n, x, y, color=C_TEXT):
    """Número da pilha no canto do slot (em cima do ícone)."""
    if n > 1:
        ctx.text(str(n), x, y, color, F, align="right")


def cursor(ctx, x, y):
    """Setinha do mouse do jogo (pixel art simples)."""
    rows = ["#", "##", "#.#", "#..#", "#...#", "#....#", "#..###", "#.#", "##"]
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == "#":
                ctx.px(x + dx, y + dy, C_OUT)
            elif ch == ".":
                ctx.px(x + dx, y + dy, "#ffffff")


def minimap_view(scale=2, new=False):
    """Textura do minimapa (64×64 tiles) com os marcadores: base ciano, você amarelo.
    `new`: os pictogramas do mapa B2 em 1× (a nave da base, a seta, losango, veios)."""
    m = MINI.resize((64 * scale, 64 * scale), Image.NEAREST)
    if new:
        cx, cy = 32 * scale, 32 * scale
        for (vx, vy, res) in [(12, 20, "iron"), (50, 44, "ice"), (44, 14, "silicon")]:
            put_marker(m, marker("vein", VEIN_C[res]), vx * scale, vy * scale)
        put_marker(m, marker("wreck"), 20 * scale, 50 * scale)
        put_marker(m, marker("base"), cx - 1, cy - 9)
        put_marker(m, marker("you", direction="down"), cx, cy + 4)
        return m
    d = ImageDraw.Draw(m)
    cx, cy = 32 * scale, 32 * scale
    d.rectangle((cx - 3 * scale, cy - 6 * scale, cx + 2 * scale, cy - 3 * scale), outline=rgba(C_O2), width=2)
    d.polygon([(cx, cy - 3), (cx + 4, cy + 4), (cx, cy + 2), (cx - 4, cy + 4)], fill=rgba("#ffe066"))
    for (vx, vy, c) in [(12, 20, RES_COLOR["iron"]), (50, 44, RES_COLOR["ice"]), (44, 14, RES_COLOR["silicon"])]:
        d.rectangle((vx * scale, vy * scale, vx * scale + 3, vy * scale + 3), fill=rgba(c))
    d.polygon([(20 * scale, 50 * scale - 4), (20 * scale + 4, 50 * scale), (20 * scale, 50 * scale + 4),
               (20 * scale - 4, 50 * scale)], fill=rgba(C_ACCENT))
    return m


# =================================================================================================
# A · COLÔNIA: terminal industrial. Chapas de metal aparafusadas (9-slice), faixas de perigo,
# telas embutidas com texto âmbar, botões físicos com "lábio", slots como soquetes, barras de LED.
# =================================================================================================
A = dict(out=C_OUT, hi="#7d7377", plate="#463e42", plate2="#3d3539", lo="#272023", rec_hi="#5d5457",
         rec_lo="#141012", screen="#16110f", screen2="#1b1513", amber=C_TI, text=C_TEXT, muted="#a3958b",
         dim="#5f534c", stripe="#2a201d")


def a_sprites():
    """Gera as molduras da direção A (px da UI). Vão pra assets/sprites/_pending/ui/."""
    sp = {}
    # janela: 24×24, borda 7 (contorno, chanfro claro/escuro, chapa com rebite, rebaixo da tela)
    im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 23, 23), fill=rgba(A["out"]))
    d.rectangle((1, 1, 22, 22), fill=rgba(A["lo"]))
    d.rectangle((1, 1, 21, 21), fill=rgba(A["hi"]))
    d.rectangle((2, 2, 21, 21), fill=rgba(A["plate"]))
    d.rectangle((5, 5, 18, 18), fill=rgba(A["rec_lo"]))          # rebaixo: sombra em cima/esquerda
    d.rectangle((6, 6, 18, 18), fill=rgba(A["rec_hi"]))          # luz embaixo/direita
    d.rectangle((6, 6, 17, 17), fill=rgba("#0d0a09"))
    d.rectangle((7, 7, 16, 16), fill=rgba(A["screen"]))
    for rx, ry in [(3, 3), (19, 3), (3, 19), (19, 19)]:           # rebites 2×2
        d.point((rx, ry), rgba("#b9afb1"))
        d.point((rx + 1, ry), rgba("#8c8285"))
        d.point((rx, ry + 1), rgba("#8c8285"))
        d.point((rx + 1, ry + 1), rgba(A["out"]))
    sp["ui_a_panel"] = (im, 7)
    # plaquinha do HUD: 12×12, borda 4 (sem tela embutida, miolo é chapa escura translúcida)
    im = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 11, 11), fill=rgba(A["out"]))
    d.rectangle((1, 1, 10, 10), fill=rgba(A["lo"]))
    d.rectangle((1, 1, 9, 9), fill=rgba(A["hi"]))
    d.rectangle((2, 2, 9, 9), fill=rgba(A["plate2"]))
    d.rectangle((3, 3, 8, 8), fill=rgba("#201a1a", 235))
    for rx, ry in [(2, 2), (9, 2), (2, 9), (9, 9)]:
        d.point((rx, ry), rgba("#9d9396"))
    sp["ui_a_plate"] = (im, 4)
    # botão: 12×12, borda 4: contorno, luz em cima, corpo laranja, lábio de 2 px embaixo
    for name, body, top, lip in [("ui_a_button", C_ACCENT, "#f6a874", "#9c4f27"),
                                 ("ui_a_button_off", "#4b4245", "#62585c", "#2a2326")]:
        im = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 11, 11), fill=rgba(A["out"]))
        d.rectangle((1, 1, 10, 10), fill=rgba(body))
        d.line((1, 1, 10, 1), fill=rgba(top))
        d.rectangle((1, 9, 10, 10), fill=rgba(lip))
        im.putpixel((0, 0), (0, 0, 0, 0)); im.putpixel((11, 0), (0, 0, 0, 0))
        im.putpixel((0, 11), (0, 0, 0, 0)); im.putpixel((11, 11), (0, 0, 0, 0))
        sp[name] = (im, 4)
    # soquete (slot 20×20): rebaixo com luz embaixo/direita
    im = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 19, 19), fill=rgba(A["rec_hi"]))
    d.rectangle((0, 0, 18, 18), fill=rgba(A["rec_lo"]))
    d.rectangle((1, 1, 18, 18), fill=rgba("#0b0908"))
    d.line((2, 2, 17, 2), fill=rgba("#000000"))
    d.line((2, 2, 2, 17), fill=rgba("#000000"))
    for p in [(3, 17), (17, 3), (17, 17)]:
        im.putpixel(p, rgba("#221b1c"))
    sp["ui_a_slot"] = (im, 0)
    # faixa de perigo: 8×8 repetível, diagonal 45° (4 laranja / 4 escuro)
    im = Image.new("RGBA", (8, 8))
    for y in range(8):
        for x in range(8):
            im.putpixel((x, y), rgba(C_ACCENT if ((x + y) // 4) % 2 == 0 else A["stripe"]))
    sp["ui_a_hazard"] = (im, 0)
    return sp


ASP = a_sprites()


def a_window(ctx, x, y, w, h, title, right=None, tag=C_TI):
    sp, b = ASP["ui_a_panel"]
    ctx.nine(sp, x, y, w, h, b)
    # faixa do título: chapa com listras de perigo na ponta e o título estampado
    ctx.fill(x + 7, y + 7, w - 14, 14, "#241d1c")
    ctx.fill(x + 7, y + 21, w - 14, 1, A["rec_lo"])
    haz = nine_slice(ASP["ui_a_hazard"][0], 14, 14, 0)
    ctx.blit_ui(haz, x + 7, y + 7)
    ctx.fill(x + 21, y + 7, 1, 14, A["out"])
    ctx.text(title, x + 26, y + 10, tag)
    if right:
        ctx.text(right, x + w - 11, y + 10, A["muted"], align="right")


def a_plate(ctx, x, y, w, h):
    sp, b = ASP["ui_a_plate"]
    ctx.nine(sp, x, y, w, h, b)


def a_tag(ctx, x, y, label, color=C_TI, bg="#120e0d"):
    w = F.width(label) + 6
    ctx.fill(x, y, w, 9, bg)
    ctx.text(label, x + 3, y - 2, color, shadow=False)
    return w


def a_leds(ctx, x, y, n, lit, color, seg_w=5, h=5, off="#211b1b"):
    ctx.fill(x - 1, y - 1, n * (seg_w + 1) + 1, h + 2, "#0b0908")
    for i in range(n):
        sx = x + i * (seg_w + 1)
        if i < lit:
            ctx.fill(sx, y, seg_w, h, color)
            ctx.fill(sx, y, seg_w, 1, mix(color, "#ffffff", 0.45))
            ctx.fill(sx, y + h - 1, seg_w, 1, mix(color, "#000000", 0.35))
        else:
            ctx.fill(sx, y, seg_w, h, off)
    return n * (seg_w + 1)


def a_slot(ctx, x, y, st, sel=False, hover=False):
    ctx.blit_ui(ASP["ui_a_slot"][0], x, y)
    if hover:
        ctx.fill(x + 2, y + 2, 16, 16, (255, 255, 255, 26))
    if sel:
        ctx.rect(x - 2, y - 2, 24, 24, A["out"])
        ctx.rect(x - 1, y - 1, 22, 22, C_ACCENT, 2)
        ctx.fill(x - 1, y - 1, 22, 1, "#f6a874")
    if st:
        ctx.icon(item(st[0]), x + 2, y + 2)
        stack_count(ctx, st[1], x + 20, y + 11)


def a_button(ctx, x, y, w, h, label, on=True, color="#1b1411"):
    sp, b = ASP["ui_a_button" if on else "ui_a_button_off"]
    ctx.nine(sp, x, y, w, h, b)
    ctx.text(label, x + w / 2, y + (h - 8) // 2 - 3, color if on or color != "#1b1411" else "#9a8f92",
             align="center", shadow=False)


def a_cost(ctx, x, y, res, need, have, locked=False):
    """Custo estilo A: soquete com o ícone, quantidade em âmbar/vermelho e LED de tem/falta."""
    ok = have >= need
    w = 27 + (P.width(f"{have}/{need}") if not locked else P.width(str(need)))
    ctx.fill(x, y, w, 17, "#0e0b0a")
    ctx.fill(x, y + 17, w, 1, A["rec_hi"])
    ic = item(res).copy()
    if locked:
        ic.alpha_composite(Image.new("RGBA", ic.size, (14, 11, 10, 170)))
    ctx.native(ic, x * K + 1, y * K + 1)
    led = A["dim"] if locked else C_OK if ok else C_ALERT
    ctx.fill(x + w - 5, y + 7, 3, 3, led)
    if not locked:
        ctx.px(x + w - 5, y + 7, mix(led, "#ffffff", 0.5))
    col = A["dim"] if locked else C_TEXT if ok else C_ALERT
    hx = x + 18
    if not locked and not ok:
        hx += ctx.text(str(have), hx, y + 1, C_ALERT, P, shadow=False)
        ctx.text(f"/{need}", hx, y + 1, "#c9b9ad", P, shadow=False)
    else:
        ctx.text(f"{have}/{need}" if not locked else f"{need}", hx, y + 1, col, P, shadow=False)
    return w


def a_key(ctx, x, y, label):
    """Tecla física (keycap) pra dicas de controle."""
    w = max(13, F.width(label) + 7)
    ctx.fill(x, y, w, 12, A["out"])
    ctx.fill(x + 1, y, w - 2, 10, "#d9cfc4")
    ctx.fill(x + 1, y + 9, w - 2, 2, "#8c8285")
    ctx.text(label, x + w / 2 + 0.5, y - 1, "#1b1411", align="center", shadow=False)
    return w


def a_hud(world="dead"):
    ctx = Ctx(WORLD[world])
    # ---- O₂ (em cima à esquerda): tag, LEDs, segundos, tanque
    a_plate(ctx, 6, 6, 128, 32)
    a_tag(ctx, 10, 10, "O₂", C_O2)
    lit = round(14 * O2_SECONDS / O2_MAX)
    a_leds(ctx, 27, 11, 14, lit, C_O2, seg_w=6, h=6, off="#14262b")
    ctx.text(f"{O2_SECONDS} S", 27, 22, C_O2)
    ctx.text("TANQUE", 125, 22, A["muted"], align="right")
    # ---- objetivos
    a_plate(ctx, 6, 42, 140, 42)
    haz = nine_slice(ASP["ui_a_hazard"][0], 6, 9, 0)
    ctx.blit_ui(haz, 10, 46)
    a_tag(ctx, 16, 46, "OBJETIVO", C_ACCENT)
    ctx.fill(12, 61, 3, 3, C_TI)
    ctx.text(OBJECTIVES[0][1], 19, 57, C_TEXT, P)
    ctx.fill(12, 73, 3, 3, A["dim"])
    ctx.text(OBJECTIVES[1][1], 19, 69, "#7f7168", P)
    # ---- Ti (em cima à direita): console com tela embutida
    px, w = UW - 6 - 156, 156
    a_plate(ctx, px, 6, w, 98)
    a_tag(ctx, px + 4, 10, "ÍNDICE TI", C_TI)
    ctx.text(f"+{TI_RATE}/S", px + w - 6, 11, C_OK, align="right")
    ctx.fill(px + 4, 22, w - 8, 19, "#0e0b0a")
    ctx.fill(px + 4, 41, w - 8, 1, A["rec_hi"])
    for yy in range(23, 41, 2):
        ctx.fill(px + 5, yy, w - 10, 1, (255, 200, 120, 10))
    ctx.text(ti_parts(), px + w - 9, 23, C_TI, FB, align="right", shadow=False)
    ctx.text("TI", px + 9, 30, "#8a6f3e", shadow=False)
    for i, (key, label, val, unit, col) in enumerate(INDICES):
        yy = 45 + i * 9
        ctx.fill(px + 6, yy + 2, 4, 4, col)
        ctx.px(px + 6, yy + 2, mix(col, "#ffffff", 0.5))
        ctx.text(label, px + 14, yy, "#d9cfc4")
        ctx.text(f"{val} {unit}", px + w - 6, yy, C_TEXT, align="right")
    ctx.fill(px + 5, 73, w - 10, 1, A["lo"])
    ctx.text(NEXT_STAGE, px + 6, 77, C_TEXT)
    n = a_leds(ctx, px + 44, 78, 16, round(16 * NEXT_PCT), C_TI, seg_w=4, h=5)
    ctx.text(f"{int(NEXT_PCT * 100)}%", px + w - 6, 77, C_TI, align="right")
    ctx.text(f"faltam {REMAINING} · {ETA}", px + 6, 85, "#8f8076", P)
    # ---- energia
    a_plate(ctx, px, 107, w, 17)
    bolt(ctx, px + 6, 111, C_ENERGY)
    ctx.text("ENERGIA", px + 14, 111, C_TEXT)
    a_leds(ctx, px + 56, 112, 10, 8, C_OK, seg_w=4, h=5)
    ctx.text(f"{ENERGY[0]}/{ENERGY[1]} KW", px + w - 6, 111, C_OK, align="right")
    # ---- minimapa: tela com moldura aparafusada
    mx, my = UW - 6 - 78, 127
    a_plate(ctx, mx, my, 78, 88)
    a_tag(ctx, mx + 4, my + 4, "MAPA", "#7fd6a0")
    ctx.text("[M]", mx + 74, my + 5, A["muted"], align="right")
    ctx.fill(mx + 6, my + 16, 66, 66, "#0b0908")
    ctx.fill(mx + 6, my + 82, 66, 1, A["rec_hi"])
    ctx.native(minimap_view(), (mx + 7) * K, (my + 17) * K)
    # ---- hotbar: "cinto" de ferramentas com soquetes e teclas estampadas
    hx = (UW - 174) // 2
    hy = UH - 6 - 20
    a_plate(ctx, hx - 5, hy - 13, 184, 40)
    for i, st in enumerate(HOTBAR):
        sx = hx + i * 22
        sel = i == HOT_SEL
        ctx.fill(sx + 5, hy - 10, 11, 8, "#120e0d" if not sel else C_ACCENT)
        ctx.text(str(i + 1), sx + 11, hy - 12, C_TI if not sel else "#ffffff", align="center", shadow=False)
        a_slot(ctx, sx, hy, st, sel=sel)
    # ---- traje: 2 soquetes presos na ponta do cinto
    ex = hx + 184 - 5
    a_plate(ctx, ex, hy - 13, 54, 40)
    a_tag(ctx, ex + 4, hy - 10, "TRAJE", C_O2)
    for i, kind in enumerate(("o2_tank", "scanner")):
        sx = ex + 5 + i * 23
        ctx.blit_ui(ASP["ui_a_slot"][0], sx, hy)
        ctx.icon(item(kind), sx + 2, hy + 2)
        ctx.fill(sx + 17, hy + 1, 2, 2, C_OK)
    # ---- recursos (embaixo à esquerda)
    a_plate(ctx, 6, UH - 26, 110, 20)
    x = 11
    for res, n in zip(RES, (92, 6, 43)):
        ctx.native(icon16(res), x * K, (UH - 20) * K)
        x += 11 + ctx.text(str(n), x + 10, UH - 20, C_TI) + 6
    # ---- dica do E (embaixo à direita): tecla física
    tw = P.width("Abrir baú: Minérios") + 30
    hy2 = hy - 13 - 23            # a ponta do cinto (TRAJE) ocupa o canto: a dica vai pro meio, acima do cinto
    a_plate(ctx, UW // 2 - tw // 2, hy2, tw, 20)
    kx = UW // 2 - tw // 2 + 5
    a_key(ctx, kx, hy2 + 4, "E")
    ctx.text("Abrir baú: Minérios", kx + 17, hy2 + 4, C_TEXT, P)
    return ctx



def dim_world(world="dead", a=150):
    ctx = Ctx(WORLD[world])
    ctx.fill(0, 0, UW, UH, (8, 5, 4, a))
    return ctx


def a_tabs(ctx, x, y, labels, active, icons=None, muted_from=None):
    """Abas de pasta em chapa: a ativa é mais clara, tem a faixa laranja e "encaixa" na tela."""
    tx = x
    for i, label in enumerate(labels):
        w = P.width(label) + 8 + (10 if icons else 0)
        on = i == active
        ctx.fill(tx, y, w, 14, A["out"])
        ctx.fill(tx + 1, y + 1, w - 2, 13, A["plate"] if on else "#2c2528")
        ctx.fill(tx + 1, y + 1, w - 2, 1, A["hi"] if on else "#3d3539")
        if on:
            ctx.fill(tx + 1, y + 1, w - 2, 2, C_ACCENT)
            ctx.fill(tx + 1, y + 13, w - 2, 2, A["plate"])
        lx = tx + 4
        if icons:
            ctx.native(icon16(icons[i]) if icons[i] in RES else item(icons[i]).resize((16, 16), Image.NEAREST),
                       lx * K - 2, (y + 3) * K)
            lx += 10
        col = C_TEXT if on else (A["dim"] if muted_from is not None and i >= muted_from else A["muted"])
        ctx.text(label, lx, y + 1, col, P, shadow=on)
        tx += w + 1
    ctx.fill(x, y + 14, tx - x - 2 if False else 0, 1, A["out"])
    return tx


def a_section(ctx, x, y, label, color=None):
    haz = nine_slice(ASP["ui_a_hazard"][0], 4, 7, 0)
    ctx.blit_ui(haz, x, y + 1)
    ctx.text(label, x + 7, y - 2, color or A["muted"])


def a_tooltip(ctx, x, y, title, sub=None):
    w = max(P.width(title), P.width(sub) if sub else 0) + 14
    h = 17 if not sub else 29
    a_plate(ctx, x, y, w, h)
    ctx.text(title, x + 7, y + 2, C_TEXT, P)
    if sub:
        ctx.text(sub, x + 7, y + 14, A["muted"], P)
    return w


def a_inventory_body(ctx, x, y, w, store_button=False):
    """Mochila + hotbar (+ traje) dentro de uma janela A, a partir de (x, y)."""
    a_section(ctx, x, y, "MOCHILA")
    for i, st in enumerate(BACKPACK):
        a_slot(ctx, x + i * 22, y + 9, st, hover=i == 1)
    a_section(ctx, x, y + 35, "HOTBAR")
    for i, st in enumerate(HOTBAR):
        a_slot(ctx, x + i * 22, y + 44, st, sel=i == HOT_SEL)
    return y + 66


def a_inventario():
    ctx = dim_world("dead", 120)
    w, h = 214, 160
    x, y = (UW - w) // 2, 40
    a_window(ctx, x, y, w, h, "INVENTÁRIO", "11/16")
    a_tabs(ctx, x + 9, y + 24, ["Inventário", "Fabricar", "LOGs 3/7"], 0)
    ctx.fill(x + 7, y + 38, w - 14, 1, A["out"])
    ctx.fill(x + 9 + P.width("Inventário") + P.width("Fabricar") + P.width("LOGs 3/7") + 3 * 8 + 2 - 5, y + 27, 3, 3,
             C_ACCENT)                                  # LOG novo
    gx = x + 20
    a_inventory_body(ctx, gx, y + 46, w)
    a_section(ctx, gx, y + 120, "TRAJE", C_O2)
    for i, (kind, lab) in enumerate([("o2_tank", "TANQUE"), ("scanner", "SCANNER")]):
        sx = gx + i * 80
        ctx.blit_ui(ASP["ui_a_slot"][0], sx, y + 129)
        ctx.icon(item(kind), sx + 2, y + 131)
        ctx.text(lab, sx + 24, y + 129, A["muted"])
        ctx.fill(sx + 24, y + 141, 3, 3, C_OK)
        ctx.text("EQUIPADO", sx + 30, y + 137, C_OK)
    # tooltip do slot com o mouse
    a_tooltip(ctx, gx + 22 + 14, y + 46 + 9 + 14, "Gelo · 18", "minério · empilha até 50")
    cursor(ctx, gx + 22 + 12, y + 46 + 9 + 10)
    # ajuda com teclas físicas
    hy = y + h + 6
    kx = x + 4
    for key, lab in [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")]:
        kx += a_key(ctx, kx, hy, key) + 3
        kx += ctx.text(lab, kx, hy - 1, "#cfc2b6", P) + 8
    return ctx


def a_recipe_row(ctx, x, y, w, h, kind, sel, have):
    m = MACHINES[kind]
    st = status(kind, have)
    locked = st == "locked"
    ctx.fill(x, y, w, h, A["out"])
    ctx.fill(x + 1, y + 1, w - 2, h - 2, "#2a2325" if sel else "#221c1d")
    ctx.fill(x + 1, y + 1, w - 2, 1, "#3a3134" if sel else "#2c2527")
    if sel:
        ctx.rect(x, y, w, h, C_ACCENT)
        ctx.fill(x - 3, y + h // 2 - 3, 2, 7, C_ACCENT)
    # prévia: tela embutida 36×(h-4)
    bx, by, bw, bh = x + 3, y + 2, 36, h - 4
    ctx.fill(bx, by, bw, bh, "#0b0908")
    ctx.fill(bx, by + bh, bw, 1, A["rec_hi"])
    pv = preview(kind)
    maxh = bh * K - 2
    if pv.height > maxh:
        r = maxh / pv.height
        pv = pv.resize((round(pv.width * r), maxh), Image.NEAREST)
    pv_img = Image.new("RGBA", (bw * K, bh * K), (0, 0, 0, 0))
    pv_img.alpha_composite(pv, (bw * K // 2 - pv.width // 2, bh * K - 2 - pv.height))
    if locked:
        pv_img.alpha_composite(Image.new("RGBA", pv_img.size, (14, 11, 10, 190)))
    ctx.native(pv_img, bx * K, by * K)
    tx = x + 46
    nw = ctx.text(m["name"], tx, y - 1, "#8a7d78" if locked else C_TEXT, P)
    ctx.text(m["desc"], tx + nw + 6, y - 1, A["dim"] if locked else A["muted"], P)
    cx = tx
    for res, n in m["cost"].items():
        cx += a_cost(ctx, cx, y + h - 20, res, n, have[res], locked) + 4
    # energia + botões
    bxr = x + w - 4
    if st == "ok":
        a_button(ctx, bxr - 86, y + (h - 18) // 2, 62, 18, "FABRICAR")
        a_button(ctx, bxr - 21, y + (h - 18) // 2, 21, 18, "X5")
    elif st == "missing":
        miss = next(r for r, n in m["cost"].items() if have[r] < n)
        a_button(ctx, bxr - 86, y + (h - 18) // 2, 86, 18, f"FALTA {RES_LABEL[miss]}", on=False, color="#ff8a7a")
        ctx.fill(bxr - 82, y + (h - 18) // 2 + 6, 3, 3, C_ALERT)
    else:
        a_button(ctx, bxr - 86, y + (h - 18) // 2, 86, 18, "", on=False)
        lock(ctx, bxr - 76, y + (h - 18) // 2 + 4, "#9a8f92")
        ctx.text(f"TI {fmt(m['unlock'])}", bxr - 38, y + (h - 18) // 2 + 2, "#9a8f92", align="center", shadow=False)
    kw = USE_KW.get(kind)
    top_end = tx + nw + 6 + P.width(m["desc"])
    if kw and bxr - 92 - F.width(f"-{kw} KW") - 8 > top_end + 4:
        kc = A["dim"] if locked else C_ENERGY
        kx = bxr - 92 - F.width(f"-{kw} KW")
        ctx.text(f"-{kw} KW", kx, y - 1, kc)
        bolt(ctx, kx - 8, y + 3, kc)


def a_fabricador():
    ctx = dim_world("dead", 150)
    w, h = 452, 262
    x, y = (UW - w) // 2, 4
    a_window(ctx, x, y, w, h, "FABRICADOR", "MATERIAIS: INVENTÁRIO + BAÚS DA BASE")
    a_tabs(ctx, x + 9, y + 24, FAB_TABS, 0)
    ctx.fill(x + 7, y + 38, w - 14, 1, A["out"])
    rows_y, row_h = y + 42, 38
    for i, kind in enumerate(TAB_KINDS[:5]):
        a_recipe_row(ctx, x + 11, rows_y + i * (row_h + 1), w - 28, row_h, kind, i == SEL_RECIPE, HAVE)
    # barra de rolagem: trilho embutido
    tx = x + w - 14
    ctx.fill(tx, rows_y, 4, 5 * (row_h + 2) - 2, "#0b0908")
    ctx.fill(tx, rows_y, 4, 150, "#5d5457")
    ctx.fill(tx, rows_y, 4, 1, A["hi"])
    # rodapé com teclas
    fy = y + h - 21
    ctx.fill(x + 7, fy - 2, w - 14, 1, A["out"])
    kx = x + 14
    for key, lab in [("A/D", "aba"), ("W/S", "escolhe"), ("ENTER", "fabrica"), ("SHIFT+ENTER", "x5"), ("E", "fecha")]:
        kx += a_key(ctx, kx, fy + 1, key) + 3
        kx += ctx.text(lab, kx, fy, "#cfc2b6", P) + 9
    return ctx


def a_fabricar_campo():
    ctx = dim_world("mist", 120)
    w, h = 330, 200
    x, y = (UW - w) // 2, 24
    a_window(ctx, x, y, w, h, "FABRICAR EM CAMPO", "SÓ DO INVENTÁRIO")
    a_tabs(ctx, x + 9, y + 24, ["Inventário", "Fabricar", "LOGs 3/7"], 1)
    ctx.fill(x + 7, y + 38, w - 14, 1, A["out"])
    for i, kind in enumerate(FIELD_KINDS):
        a_recipe_row(ctx, x + 11, y + 42 + i * 37, w - 22, 36, kind, i == 0, FIELD_HAVE)
    return ctx


def a_switch(ctx, x, y, on, res, color):
    """Interruptor com ícone: LED aceso quando ligado."""
    ctx.fill(x, y, 18, 18, A["out"])
    ctx.fill(x + 1, y + 1, 16, 16, "#3a3134" if on else "#161212")
    ctx.fill(x + 1, y + 1, 16, 1, A["hi"] if on else "#221c1d")
    img = item(res).copy()
    if not on:
        img.alpha_composite(Image.new("RGBA", img.size, (22, 18, 18, 160)))
    ctx.native(img, (x + 1) * K, (y + 1) * K)
    ctx.fill(x + 14, y + 1, 3, 3, color if on else "#2a2326")


def a_bau():
    ctx = dim_world("dead", 120)
    lw, rw, h = 208, 208, 214
    lx, ty = (UW - lw - rw - 10) // 2, 18
    rx = lx + lw + 10
    a_window(ctx, lx, ty, lw, h, "INVENTÁRIO", "11/16")
    a_inventory_body(ctx, lx + 17, ty + 32, lw)
    a_button(ctx, lx + 17, ty + 102, 174, 18, "GUARDAR RECURSOS  >>")
    ctx.text("ferro, silício e gelo de todos os slots", lx + 17, ty + 120, A["muted"], P)
    ctx.text("máquinas e drones ficam com você", lx + 17, ty + 132, A["dim"], P)
    # baú
    a_window(ctx, rx, ty, rw, h, "BAÚ ·", "6/24")
    ctx.text("Minérios", rx + 26 + F.width("BAÚ ·") + 4, ty + 7, C_ACCENT, P)
    # lápis
    px0 = rx + 26 + F.width("BAÚ ·") + 8 + P.width("Minérios")
    for i in range(5):
        ctx.px(px0 + i, ty + 16 - i, A["muted"])
    for i, st in enumerate(CHEST):
        a_slot(ctx, rx + 17 + (i % 8) * 22, ty + 32 + (i // 8) * 22, st, hover=i == 3)
    a_button(ctx, rx + 17, ty + 102, 174, 18, "<<  PEGAR TUDO")
    # drones
    dy = ty + 126
    ctx.fill(rx + 9, dy, rw - 18, 1, A["out"])
    a_section(ctx, rx + 17, dy + 6, "DRONES", C_O2)
    ctx.text("ENVIA FERRO", rx + rw - 11, dy + 4, C_TI, align="right")
    for r, (label, chosen, color) in enumerate([("ENVIA", {"iron"}, C_ACCENT), ("RECEBE", set(), C_O2)]):
        yy = dy + 16 + r * 21
        ctx.text(label, rx + 17, yy + 2, A["muted"])
        for k, res in enumerate(RES):
            a_switch(ctx, rx + 98 + k * 21, yy, res in chosen, res, color)
    yy = dy + 58
    ctx.text("LOTE", rx + 17, yy + 2, A["muted"])
    for k, n in enumerate((1, 5, 10, 20)):
        bx = rx + 98 + k * 21
        on = n == 10
        ctx.fill(bx, yy, 19, 15, A["out"])
        ctx.fill(bx + 1, yy + 1, 17, 13, C_ACCENT if on else "#221c1d")
        ctx.fill(bx + 1, yy + 12, 17, 2, "#9c4f27" if on else "#161212")
        ctx.text(str(n), bx + 10, yy + 1, "#1b1411" if on else A["muted"], P, align="center", shadow=False)
    # tooltip
    a_tooltip(ctx, rx + 17 + 3 * 22 + 12, ty + 32 + 14, "Silício · 22", "clique: pega a pilha")
    cursor(ctx, rx + 17 + 3 * 22 + 10, ty + 32 + 10)
    kx = lx + 2
    hy = ty + h + 8
    for key, lab in [("CLIQUE", "pilha"), ("DIR", "1"), ("SHIFT+CLIQUE", "todas"), ("ESC", "fecha")]:
        kx += a_key(ctx, kx, hy, key) + 3
        kx += ctx.text(lab, kx, hy - 1, "#cfc2b6", P) + 9
    return ctx


def a_fader(ctx, x, y, w, v):
    ctx.fill(x, y + 3, w, 3, "#0b0908")
    ctx.fill(x, y + 6, w, 1, A["rec_hi"])
    ctx.fill(x + 1, y + 4, round((w - 2) * v), 1, C_TI)
    kx = x + round((w - 2) * v) - 3
    ctx.fill(kx, y - 1, 8, 11, A["out"])
    ctx.fill(kx + 1, y, 6, 8, "#d9cfc4")
    ctx.fill(kx + 1, y + 8, 6, 1, "#8c8285")
    ctx.fill(kx + 3, y + 2, 2, 4, "#8c8285")


def a_opcoes():
    ctx = dim_world("dead", 150)
    w, h = 250, 200
    x, y = (UW - w) // 2, 26
    a_window(ctx, x, y, w, h, "OPÇÕES", "PAUSA")
    rows = [("GERAL", 1.0), ("EFEITOS", 0.4), ("AMBIENTE", 0.5)]
    for i, (lab, v) in enumerate(rows):
        ry = y + 28 + i * 22
        ctx.fill(x + 10, ry, w - 20, 19, "#221c1d")
        ctx.text(lab, x + 16, ry + 3, C_TEXT)
        a_fader(ctx, x + 84, ry + 5, 110, v)
        ctx.fill(x + w - 46, ry + 3, 32, 13, "#0b0908")
        ctx.text(f"{round(v * 100)}%", x + w - 16, ry + 2, C_TI, align="right", shadow=False)
    ry = y + 28 + 3 * 22
    # tela cheia: interruptor
    ctx.fill(x + 10, ry, w - 20, 19, "#221c1d")
    ctx.text("TELA CHEIA", x + 16, ry + 3, C_TEXT)
    ctx.fill(x + w - 60, ry + 3, 46, 13, A["out"])
    ctx.fill(x + w - 59, ry + 4, 22, 11, "#4b4245")
    ctx.text("NÃO", x + w - 48, ry + 2, C_TEXT, align="center", shadow=False)
    ctx.fill(x + w - 36, ry + 4, 21, 11, "#161212")
    ctx.text("SIM", x + w - 25, ry + 2, A["dim"], align="center", shadow=False)
    # zoom: seletor (selecionado)
    ry += 22
    ctx.fill(x + 10, ry, w - 20, 19, "#2a2325")
    ctx.rect(x + 10, ry, w - 20, 19, C_ACCENT)
    ctx.text("ZOOM", x + 16, ry + 3, C_TEXT)
    a_button(ctx, x + w - 92, ry + 2, 15, 15, "<")
    ctx.fill(x + w - 75, ry + 3, 40, 13, "#0b0908")
    ctx.text("1,5×", x + w - 55, ry + 1, C_TI, P, align="center", shadow=False)
    a_button(ctx, x + w - 33, ry + 2, 15, 15, ">")
    # interface: chave de 3 posições
    ry += 22
    ctx.fill(x + 10, ry, w - 20, 19, "#221c1d")
    ctx.text("INTERFACE", x + 16, ry + 3, C_TEXT)
    for k, lab in enumerate(["P", "M", "G"]):
        bx = x + w - 76 + k * 21
        a_button(ctx, bx, ry + 2, 19, 15, lab, on=k == 1)
    ry += 24
    a_button(ctx, x + 10, ry, 70, 18, "VOLTAR", on=False)
    ctx.text("Voltar", x + 45, ry + 1, C_TEXT, P, align="center", shadow=False) if False else None
    kx = x + 4
    hy = y + h + 6
    for key, lab in [("W/S", "escolhe"), ("A/D", "ajusta"), ("ESC", "volta")]:
        kx += a_key(ctx, kx, hy, key) + 3
        kx += ctx.text(lab, kx, hy - 1, "#cfc2b6", P) + 9
    return ctx



# =================================================================================================
# B · LIMPA: moderna e plana. Cartões escuros frios com canto arredondado (1 px), sem moldura
# pesada, hierarquia por tamanho e cor, custos em "chips" com ícone, fabricador em 2 painéis
# (lista + detalhe), abas com ícone. Quase tudo em código (só o slot vira sprite).
# =================================================================================================
B = dict(bg=(15, 17, 25, 236), card="#141722", card2="#1b1f2c", hover="#232838", line="#2b3145",
         line2="#3a4259", text="#eef0f6", muted="#8b93a8", dim="#4f566b", sel="#2a2420")


def b_sprites():
    sp = {}
    im = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((1, 0, 18, 19), fill=rgba("#0c0e15"))
    d.rectangle((0, 1, 19, 18), fill=rgba("#0c0e15"))
    d.rectangle((1, 1, 18, 18), fill=rgba("#181c28"))
    d.line((2, 1, 17, 1), fill=rgba("#22273a"))           # luz de cima, bem sutil
    sp["ui_b_slot"] = (im, 0)
    return sp


BSP = b_sprites()


def b_card(ctx, x, y, w, h, bg=None, border=None, shadow=True):
    if shadow:
        ctx.fill(x + 1, y + h, w - 2, 1, (0, 0, 0, 110))
    ctx.round_rect(x, y, w, h, bg or B["bg"])
    if border:
        ctx.fill(x + 1, y, w - 2, 1, border)
        ctx.fill(x + 1, y + h - 1, w - 2, 1, border)
        ctx.fill(x, y + 1, 1, h - 2, border)
        ctx.fill(x + w - 1, y + 1, 1, h - 2, border)


def b_bar(ctx, x, y, w, frac, color, h=3, track="#262b3b"):
    ctx.fill(x, y, w, h, track)
    fw = round(w * frac)
    ctx.fill(x, y, fw, h, color)
    if fw > 1:
        ctx.fill(x, y, fw, 1, mix(color, "#ffffff", 0.35))


def b_slot(ctx, x, y, st, sel=False, hover=False, num=None):
    ctx.blit_ui(BSP["ui_b_slot"][0], x, y)
    if hover:
        ctx.round_rect(x + 1, y + 1, 18, 18, B["hover"])
    if sel:
        ctx.round_rect(x - 1, y - 1, 22, 22, (0, 0, 0, 0), border=C_ACCENT)
        ctx.fill(x + 1, y + 1, 18, 18, (226, 115, 58, 40))
    if num is not None:
        ctx.text(str(num), x + 10, y - 11, C_ACCENT if sel else B["dim"], align="center", shadow=False)
    if st:
        ctx.icon(item(st[0]), x + 2, y + 2)
        stack_count(ctx, st[1], x + 20, y + 11)


def b_button(ctx, x, y, w, h, label, kind="primary", font=None):
    font = font or F
    if kind == "primary":
        ctx.round_rect(x, y, w, h, C_ACCENT)
        ctx.fill(x + 1, y, w - 2, 1, "#f29a62")
        col = "#1b1411"
    elif kind == "ghost":
        ctx.round_rect(x, y, w, h, B["card2"], border=B["line2"])
        col = B["text"]
    elif kind == "danger":
        ctx.round_rect(x, y, w, h, (255, 106, 85, 30), border="#7a3a33")
        col = "#ff8a7a"
    else:
        ctx.round_rect(x, y, w, h, B["card2"], border=B["line"])
        col = B["dim"]
    ty = y + (h - 5) // 2 - 4 if font is F else y + (h - 8) // 2 - 4
    ctx.text(label, x + w / 2, ty, col, font, align="center", shadow=False)


def b_key(ctx, x, y, label):
    w = max(11, F.width(label) + 6)
    ctx.round_rect(x, y, w, 11, B["card2"], border=B["line2"])
    ctx.text(label, x + w / 2 + 0.5, y - 2, B["text"], align="center", shadow=False)
    return w


def b_help(ctx, x, y, pairs, center=None):
    total = 0
    for key, lab in pairs:
        total += max(11, F.width(key) + 6) + 3 + P.width(lab) + 9
    if center is not None:
        x = center - total // 2
    for key, lab in pairs:
        x += b_key(ctx, x, y, key) + 3
        x += ctx.text(lab, x, y - 2, B["muted"], P) + 9


def b_chip(ctx, x, y, res, need, have, locked=False, big=False):
    """Chip de custo: ícone + "tem/precisa", fundo verde (tem) ou vermelho (falta)."""
    ok = have >= need
    label = f"{need}" if locked else f"{have}/{need}"
    w = 21 + P.width(label) + 4
    h = 18
    if locked:
        bg, bd, col = B["card2"], B["line"], B["dim"]
    elif ok:
        bg, bd, col = (127, 214, 122, 28), "#355a3a", "#b6f0b0"
    else:
        bg, bd, col = (255, 106, 85, 36), "#7a3a33", "#ff8a7a"
    ctx.round_rect(x, y, w, h, bg, border=bd)
    ic = item(res).copy()
    if locked:
        ic.alpha_composite(Image.new("RGBA", ic.size, (20, 23, 34, 170)))
    ctx.native(ic, (x + 2) * K, (y + 1) * K)
    ctx.text(label, x + 19, y + 1, col, P, shadow=False)
    return w


def b_hud(world="dead", v2=False):
    ctx = Ctx(WORLD[world])
    # ---- O₂: pílula numa linha só (rótulo, barra, segundos, tanque)
    b_card(ctx, 6, 6, 132, 17)
    ctx.text("O₂", 11, 7, C_O2, shadow=False)
    b_bar(ctx, 26, 12, 60, O2_SECONDS / O2_MAX, C_O2, h=4)
    ctx.text(f"{O2_SECONDS}s", 90, 3, B["text"], P, shadow=False)
    ctx.native(icon16("o2_tank"), 124 * K, 10 * K)
    # ---- objetivo: cartão com a barra laranja na esquerda
    b_card(ctx, 6, 27, 132, 41)
    ctx.fill(6, 28, 2, 39, C_ACCENT)
    ctx.text("OBJETIVO", 12, 27, C_ACCENT, shadow=False)
    ctx.text(OBJECTIVES[0][1], 12, 33, B["text"], P, shadow=False)
    ctx.text(OBJECTIVES[1][1], 12, 45, B["dim"], P, shadow=False)
    # ---- Ti: número grande, barra empilhada (O₂/calor/água) e próximo estágio
    w = 146 if not v2 else 150
    px = UW - 6 - w
    if v2:
        ey = b2_ti_panel(ctx, px, 6, w) + 4
    else:
        ey = 72
        b_card(ctx, px, 6, w, 62)
        ctx.text("TI", px + 6, 4, C_TI, shadow=False)
        ctx.text(ti_parts(), px + 6, 8, C_TI, FB, shadow=False) if False else None
        ctx.text(ti_parts(), px + w - 6, 3, C_TI, FB, align="right", shadow=False)
        ctx.text(f"+{TI_RATE}/s", px + 20, 3, C_OK, P, shadow=False)
        vals = [2940, 1020, 852]
        total = sum(vals)
        bx, bw = px + 6, w - 12
        xx = bx
        for v, (_, _, _, _, col) in zip(vals, INDICES):
            seg = round(bw * v / total)
            ctx.fill(xx, 24, seg - 1, 3, col)
            xx += seg
        for i, ((key, label, val, unit, col), cx) in enumerate(zip(INDICES, (bx, bx + 54, bx + 98))):
            ctx.fill(cx, 33, 3, 3, col)
            ctx.text(f"{label} {val}" if key == "o2" else val, cx + 6, 28, B["text"], shadow=False)
        ctx.fill(px + 6, 41, w - 12, 1, B["line"])
        ctx.text("NÉVOA", px + 6, 42, B["text"], shadow=False)
        b_bar(ctx, px + 42, 47, 70, NEXT_PCT, C_TI, h=3)
        ctx.text(f"{int(NEXT_PCT * 100)}%", px + w - 6, 42, C_TI, align="right", shadow=False)
        ctx.text(f"faltam {REMAINING} · {ETA}", px + 6, 50, B["muted"], P, shadow=False)
    # ---- energia: pílula
    b_card(ctx, px + w - 90, ey, 90, 15)
    bolt(ctx, px + w - 85, ey + 3, C_ENERGY, shadow=False)
    b_bar(ctx, px + w - 76, ey + 7, 26, 0.8, C_OK, h=3)
    ctx.text(f"{ENERGY[0]}/{ENERGY[1]} kW", px + w - 6, ey - 2, C_OK, P, align="right", shadow=False)
    # ---- minimapa: cartão quadrado, rótulo por dentro
    mx, my = UW - 6 - 72, ey + 19
    b_card(ctx, mx, my, 72, 72)
    ctx.native(minimap_view(new=v2), (mx + 4) * K, (my + 4) * K)
    ctx.round_rect(mx + 5, my + 5, 22, 9, (15, 17, 25, 220))
    ctx.text("MAPA", mx + 7, my + 2, B["muted"], shadow=False)
    b_key(ctx, mx + 57, my + 5, "M")
    ctx.native(icon16("scanner"), (mx + 58) * K, (my + 57) * K)
    # ---- hotbar: slots arredondados, número dentro, item selecionado com nome em cima
    hx = (UW - 174) // 2
    hy = UH - 6 - 20
    b_card(ctx, hx - 4, hy - 11, 182, 35)
    for i, st in enumerate(HOTBAR):
        b_slot(ctx, hx + i * 22, hy, st, sel=i == HOT_SEL, num=i + 1)
    name = "Gerador de O₂ · 2"
    nw = P.width(name) + 12
    b_card(ctx, UW // 2 - nw // 2, hy - 27, nw, 13, bg=(15, 17, 25, 200), shadow=False)
    ctx.text(name, UW // 2, hy - 29, B["text"], P, align="center", shadow=False)
    # ---- recursos: pílulas
    x = 6
    for res, n in zip(RES, (92, 6, 43)):
        lab = str(n)
        pw = 14 + F.width(lab) + 5
        b_card(ctx, x, UH - 6 - 13, pw, 13)
        ctx.native(icon16(res), (x + 2) * K, (UH - 6 - 13 + 2) * K)
        ctx.text(lab, x + 12, UH - 6 - 13 - 1, B["text"], shadow=False)
        x += pw + 3
    # ---- dica do E
    lab = "Abrir baú: Minérios"
    tw = P.width(lab) + 22
    b_card(ctx, UW - 6 - tw, UH - 6 - 15, tw, 15)
    ctx.round_rect(UW - 6 - tw + 3, UH - 6 - 12, 11, 9, C_ACCENT)
    ctx.text("E", UW - 6 - tw + 9, UH - 6 - 15, "#1b1411", align="center", shadow=False)
    ctx.text(lab, UW - 6 - tw + 17, UH - 6 - 16, B["text"], P, shadow=False)
    return ctx


def b_segmented(ctx, x, y, labels, active, dot=None):
    """Abas como controle segmentado (pílula com a ativa preenchida)."""
    widths = [P.width(lb) + 14 for lb in labels]
    w = sum(widths) + 2
    ctx.round_rect(x, y, w, 15, "#0d0f16", border=B["line"])
    xx = x + 1
    for i, (lb, lw) in enumerate(zip(labels, widths)):
        if i == active:
            ctx.round_rect(xx, y + 1, lw, 13, B["hover"])
            ctx.fill(xx + 3, y + 13, lw - 6, 1, C_ACCENT)
        ctx.text(lb, xx + 7, y, B["text"] if i == active else B["muted"], P, shadow=False)
        if dot == i:
            ctx.fill(xx + lw - 4, y + 3, 2, 2, C_ACCENT)
        xx += lw
    return w


def b_window(ctx, x, y, w, h, title, right=None):
    b_card(ctx, x, y, w, h, bg=(15, 17, 25, 246), border=B["line"])
    ctx.text(title, x + 8, y + 2, B["text"], P, shadow=False)
    if right:
        ctx.text(right, x + w - 8, y + 4, B["muted"], align="right", shadow=False)


def b_inventario():
    ctx = dim_world("dead", 110)
    w, h = 330, 172
    x, y = (UW - w) // 2, 36
    b_window(ctx, x, y, w, h, "Inventário", "11/16")
    b_segmented(ctx, x + w // 2 - 85, y + 3, ["Inventário", "Fabricar", "LOGs 3/7"], 0, dot=2) if False else None
    sw = b_segmented(ctx, 0, -100, ["Inventário", "Fabricar", "LOGs 3/7"], 0)
    b_segmented(ctx, x + (w - sw) // 2, y + 22, ["Inventário", "Fabricar", "LOGs 3/7"], 0, dot=2)
    gx, gy = x + 10, y + 46
    ctx.text("MOCHILA", gx, gy - 4, B["muted"], shadow=False)
    for i, st in enumerate(BACKPACK):
        b_slot(ctx, gx + i * 22, gy + 6, st, hover=i == 1)
    ctx.text("HOTBAR", gx, gy + 28, B["muted"], shadow=False)
    for i, st in enumerate(HOTBAR):
        b_slot(ctx, gx + i * 22, gy + 38, st, sel=i == HOT_SEL)
    ctx.text("TRAJE", gx, gy + 60, C_O2, shadow=False)
    for i, (kind, lab) in enumerate([("o2_tank", "Tanque de O₂"), ("scanner", "Scanner")]):
        sx = gx + i * 96
        b_slot(ctx, sx, gy + 70, (kind, 1))
        ctx.text(lab, sx + 24, gy + 68, B["text"], P, shadow=False)
        ctx.fill(sx + 24, gy + 83, 3, 3, C_OK)
        ctx.text("equipado", sx + 30, gy + 78, C_OK, P, shadow=False)
    # painel de detalhe (item com o mouse / selecionado)
    dx, dw = x + w - 134, 126
    ctx.round_rect(dx, y + 42, dw, h - 50, B["card"])
    big = item("ice").resize((64, 64), Image.NEAREST)
    ctx.round_rect(dx + 6, y + 48, 36, 36, "#0d0f16")
    ctx.native(big, (dx + 8) * K, (y + 50) * K)
    ctx.text("Gelo", dx + 48, y + 47, B["text"], P, shadow=False)
    ctx.text("RECURSO", dx + 48, y + 58, C_O2, shadow=False)
    ctx.text("18 / 50", dx + 48, y + 68, B["muted"], P, shadow=False)
    ctx.fill(dx + 6, y + 90, dw - 12, 1, B["line"])
    ctx.text("USADO EM", dx + 6, y + 89, B["muted"], shadow=False)
    for i, k in enumerate(["melter", "o2_tank", "lamp_t2"]):
        yy = y + 100 + i * 20
        ctx.native(item(k), (dx + 6) * K, yy * K)
        ctx.text(MACHINES[k]["name"], dx + 26, yy + 1, B["text"], P, shadow=False)
    b_help(ctx, 0, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")],
           center=UW // 2)
    cursor(ctx, gx + 22 + 12, gy + 6 + 10)
    return ctx


def b_icon_tabs(ctx, x, y, active, labels=FAB_TABS, icons=TAB_ICON, locked=()):
    """Abas com ícone: só a ativa mostra o nome (cabe nos 3 tamanhos de UI)."""
    xx = x
    for i, ic in enumerate(icons):
        on = i == active
        w = 22 + (P.width(labels[i]) + 4 if on else 0)
        ctx.round_rect(xx, y, w, 20, B["hover"] if on else "#0d0f16", border=C_ACCENT if on else B["line"])
        img = item(ic).copy()
        if i in locked:
            img.alpha_composite(Image.new("RGBA", img.size, (13, 15, 22, 160)))
        ctx.native(img, (xx + 3) * K, (y + 2) * K)
        if on:
            ctx.text(labels[i], xx + 21, y + 1, B["text"], P, shadow=False)
        xx += w + 3
    return xx


def b_recipe_list(ctx, x, y, w, kinds, sel, have, row_h=22):
    for i, kind in enumerate(kinds):
        m = MACHINES[kind]
        st = status(kind, have)
        ry = y + i * (row_h + 2)
        on = i == sel
        ctx.round_rect(x, ry, w, row_h, B["hover"] if on else B["card"], border=C_ACCENT if on else None)
        img = item(kind).copy()
        if st == "locked":
            img.alpha_composite(Image.new("RGBA", img.size, (20, 23, 34, 170)))
        ctx.native(img, (x + 3) * K, (ry + 3) * K)
        ctx.text(m["name"], x + 22, ry + 2, B["dim"] if st == "locked" else B["text"], P, shadow=False)
        rx = x + w - 6
        if st == "ok":
            check(ctx, rx - 7, ry + 8, C_OK)
        elif st == "missing":
            ctx.text("falta", rx, ry + 2, "#ff8a7a", P, align="right", shadow=False)
        else:
            lock(ctx, rx - 7, ry + 7, B["dim"])


def b_detail(ctx, x, y, w, h, kind, have, batch=1):
    m = MACHINES[kind]
    st = status(kind, have)
    ctx.round_rect(x, y, w, h, B["card"])
    # vitrine: prévia 2× (pixel inteiro), fundo com o chão do estágio sugerido por uma faixa
    ctx.round_rect(x + 6, y + 6, 64, 64, "#0d0f16")
    ctx.fill(x + 7, y + 58, 62, 11, "#151926")
    pv = preview(kind)
    sc = 2 if pv.height * 2 <= 120 else 1
    pv = pv.resize((pv.width * sc, pv.height * sc), Image.NEAREST)
    ctx.native(pv, (x + 38) * K - pv.width // 2, (y + 66) * K - pv.height)
    ctx.text(m["name"], x + 76, y + 4, B["text"], P, shadow=False)
    ctx.text(m["desc"], x + 76, y + 15, C_TI, P, shadow=False)
    kw = USE_KW.get(kind, 0)
    if kw:
        ctx.round_rect(x + 76, y + 31, 44, 13, "#0d0f16", border=B["line"])
        bolt(ctx, x + 80, y + 33, C_ENERGY, shadow=False)
        ctx.text(f"-{kw} kW", x + 89, y + 30, C_ENERGY, P, shadow=False)
    ctx.text("x0 no inventário", x + 76, y + 48, B["dim"], P, shadow=False)
    # custo: uma linha por material
    ctx.text("CUSTO", x + 6, y + 73, B["muted"], shadow=False)
    ctx.text("tem / precisa", x + w - 6, y + 73, B["dim"], align="right", shadow=False)
    for i, (res, n) in enumerate(m["cost"].items()):
        yy = y + 84 + i * 21
        hv = have[res]
        ok = hv >= n
        ctx.round_rect(x + 6, yy, w - 12, 20, (127, 214, 122, 18) if ok else (255, 106, 85, 30),
                       border="#2f4a33" if ok else "#6a302b")
        ctx.native(item(res), (x + 8) * K, (yy + 2) * K)
        ctx.text(RES_NAME[res], x + 27, yy + 1, B["text"], P, shadow=False)
        num = f"{hv}/{n}"
        ctx.text(num, x + w - 21, yy + 1, "#b6f0b0" if ok else "#ff8a7a", P, align="right", shadow=False)
        if ok:
            check(ctx, x + w - 17, yy + 7, C_OK)
        else:
            cross(ctx, x + w - 16, yy + 7, C_ALERT)
        b_bar(ctx, x + 27, yy + 16, w - 52, min(1, hv / n), C_OK if ok else C_ALERT, h=1, track="#2a2f40")
    by = y + h - 24
    # lote + botão
    for k, lab in enumerate(["×1", "×5"]):
        bx = x + 6 + k * 23
        on = (k == 0) if batch == 1 else (k == 1)
        ctx.round_rect(bx, by, 21, 18, B["hover"] if on else "#0d0f16", border=C_ACCENT if on else B["line"])
        ctx.text(lab, bx + 11, by + 1, B["text"] if on else B["muted"], P, align="center", shadow=False)
    if st == "ok":
        b_button(ctx, x + 54, by, w - 60, 18, "FABRICAR")
    elif st == "missing":
        miss = [(r, n - have[r]) for r, n in m["cost"].items() if have[r] < n]
        b_button(ctx, x + 54, by, w - 60, 18, f"FALTAM {miss[0][1]} {RES_LABEL[miss[0][0]]}", kind="danger")
    else:
        b_button(ctx, x + 54, by, w - 60, 18, f"LIBERA EM TI {fmt(m['unlock'])}", kind="off")


def b_fabricador():
    ctx = dim_world("dead", 150)
    w, h = 456, 258
    x, y = (UW - w) // 2, 6
    b_window(ctx, x, y, w, h, "Fabricador", "MATERIAIS: INVENTÁRIO + BAÚS")
    b_icon_tabs(ctx, x + 8, y + 18, 0, locked=(2,))
    ctx.fill(x + 8, y + 42, w - 16, 1, B["line"])
    lw = 176
    b_recipe_list(ctx, x + 8, y + 48, lw, TAB_KINDS, SEL_RECIPE, HAVE)
    b_detail(ctx, x + 8 + lw + 6, y + 48, w - lw - 22, h - 72, TAB_KINDS[SEL_RECIPE], HAVE)
    b_help(ctx, 0, y + h - 17, [("A/D", "aba"), ("W/S", "escolhe"), ("ENTER", "fabrica"), ("SHIFT", "×5"), ("E", "fecha")],
           center=x + w // 2)
    return ctx


def b_fabricar_campo():
    ctx = dim_world("mist", 110)
    w, h = 400, 226
    x, y = (UW - w) // 2, 14
    b_window(ctx, x, y, w, h, "Fabricar em campo", "SÓ DO INVENTÁRIO")
    sw = b_segmented(ctx, 0, -100, ["Inventário", "Fabricar", "LOGs 3/7"], 1)
    b_segmented(ctx, x + (w - sw) // 2, y + 20, ["Inventário", "Fabricar", "LOGs 3/7"], 1)
    lw = 150
    b_recipe_list(ctx, x + 8, y + 42, lw, FIELD_KINDS, 2, FIELD_HAVE)
    b_detail(ctx, x + 8 + lw + 6, y + 42, w - lw - 22, h - 50, FIELD_KINDS[2], FIELD_HAVE)
    return ctx


def b_bau():
    ctx = dim_world("dead", 110)
    cw, h = 184, 196
    mid = 58
    lx = (UW - 2 * cw - mid) // 2
    rx = lx + cw + mid
    ty = 14
    b_window(ctx, lx, ty, cw, 84, "Inventário", "11/16")
    gx = lx + 8
    ctx.text("MOCHILA", gx, ty + 16, B["muted"], shadow=False)
    for i, st in enumerate(BACKPACK):
        b_slot(ctx, gx + i * 22, ty + 26, st)
    ctx.text("HOTBAR", gx, ty + 48, B["muted"], shadow=False)
    for i, st in enumerate(HOTBAR):
        b_slot(ctx, gx + i * 22, ty + 58, st, sel=i == HOT_SEL)
    # baú
    b_window(ctx, rx, ty, cw, h, "", "6/24")
    ctx.text("Minérios", rx + 8, ty + 2, C_ACCENT, P, shadow=False)
    px0 = rx + 12 + P.width("Minérios")
    for i in range(5):
        ctx.px(px0 + i, ty + 11 - i, B["muted"])
    ctx.text("BAÚ", rx + 8, ty + 16, B["muted"], shadow=False)
    for i, st in enumerate(CHEST):
        b_slot(ctx, rx + 8 + (i % 8) * 22, ty + 26 + (i // 8) * 22, st, hover=i == 3)
    # coluna do meio: ações com seta
    cx = lx + cw + 4
    for k, (lab1, lab2, arrow) in enumerate([("GUARDAR", "RECURSOS", ">"), ("PEGAR", "TUDO", "<")]):
        by = ty + 22 + k * 44
        ctx.round_rect(cx, by, mid - 8, 40, C_ACCENT if k == 0 else B["card2"], border=None if k == 0 else B["line2"])
        col = "#1b1411" if k == 0 else B["text"]
        ctx.text(arrow * 2, cx + (mid - 8) // 2, by + 1, col, FB if False else F, align="center", shadow=False)
        ctx.text(lab1, cx + (mid - 8) // 2, by + 11, col, align="center", shadow=False)
        ctx.text(lab2, cx + (mid - 8) // 2, by + 20, col, align="center", shadow=False)
    # drones
    dy = ty + 100
    ctx.fill(rx + 8, dy, cw - 16, 1, B["line"])
    ctx.text("DRONES", rx + 8, dy + 1, C_O2, shadow=False)
    ctx.text("envia ferro", rx + cw - 8, dy - 1, C_TI, P, align="right", shadow=False)
    for r, (label, chosen, color) in enumerate([("Envia", {"iron"}, C_ACCENT), ("Recebe", set(), C_O2)]):
        yy = dy + 14 + r * 24
        ctx.text(label, rx + 8, yy + 1, B["muted"], P, shadow=False)
        for k, res in enumerate(RES):
            bx = rx + 56 + k * 40
            on = res in chosen
            ctx.round_rect(bx, yy, 38, 20, (226, 115, 58, 40) if on else "#0d0f16", border=color if on else B["line"])
            img = item(res).copy()
            if not on:
                img.alpha_composite(Image.new("RGBA", img.size, (13, 15, 22, 140)))
            ctx.native(img, (bx + 2) * K, (yy + 2) * K)
            # interruptorzinho
            ctx.round_rect(bx + 22, yy + 7, 12, 6, color if on else B["line2"])
            ctx.fill(bx + (29 if on else 23), yy + 8, 4, 4, "#ffffff" if on else B["muted"])
    yy = dy + 64
    ctx.text("Lote", rx + 8, yy + 1, B["muted"], P, shadow=False)
    for k, n in enumerate((1, 5, 10, 20)):
        bx = rx + 56 + k * 30
        on = n == 10
        ctx.round_rect(bx, yy, 28, 16, B["hover"] if on else "#0d0f16", border=C_ACCENT if on else B["line"])
        ctx.text(str(n), bx + 14, yy, B["text"] if on else B["muted"], P, align="center", shadow=False)
    # tooltip
    tx, tyy = rx + 8 + 3 * 22 + 14, ty + 26 + 16
    ctx.round_rect(tx, tyy, 92, 28, (11, 13, 20, 250), border=B["line2"])
    ctx.text("Silício · 22", tx + 6, tyy, B["text"], P, shadow=False)
    ctx.text("clique: pega a pilha", tx + 6, tyy + 11, B["muted"], P, shadow=False) if False else None
    ctx.text("CLIQUE: PEGA A PILHA", tx + 6, tyy + 14, B["muted"], shadow=False)
    cursor(ctx, rx + 8 + 3 * 22 + 10, ty + 26 + 10)
    b_help(ctx, 0, ty + h + 8, [("CLIQUE", "pilha"), ("DIR", "1"), ("SHIFT+CLIQUE", "todas"), ("ESC", "fecha")],
           center=UW // 2)
    return ctx


def b_opcoes():
    ctx = dim_world("dead", 150)
    w, h = 260, 196
    x, y = (UW - w) // 2, 28
    b_window(ctx, x, y, w, h, "Opções", "PAUSA")
    yy = y + 22
    ctx.text("SOM", x + 10, yy - 3, B["muted"], shadow=False)
    for i, (lab, v) in enumerate([("GERAL", 1.0), ("EFEITOS", 0.4), ("AMBIENTE", 0.5)]):
        ry = yy + 8 + i * 17
        ctx.text(lab, x + 10, ry + 2, B["text"], shadow=False)
        b_bar(ctx, x + 80, ry + 7, 130, v, C_ACCENT, h=2, track="#262b3b")
        kx = x + 80 + round(130 * v)
        ctx.round_rect(kx - 3, ry + 4, 7, 8, B["text"])
        ctx.text(f"{round(v * 100)}%", x + w - 10, ry, B["muted"], P, align="right", shadow=False)
    yy += 64
    ctx.fill(x + 10, yy, w - 20, 1, B["line"])
    ctx.text("TELA", x + 10, yy + 1, B["muted"], shadow=False)
    rows = [("TELA CHEIA", ["Não", "Sim"], 0), ("ZOOM", ["0,75×", "1×", "1,5×", "2×"], 2),
            ("INTERFACE", ["Pequena", "Média", "Grande"], 1)]
    for i, (lab, opts, act) in enumerate(rows):
        ry = yy + 12 + i * 21
        if i == 1:
            ctx.round_rect(x + 5, ry - 2, w - 10, 20, B["hover"])
            ctx.fill(x + 5, ry, 2, 16, C_ACCENT)
        ctx.text(lab, x + 10, ry + 3, B["text"], shadow=False)
        widths = [P.width(o) + 10 for o in opts]
        sx = x + w - 10 - sum(widths) - 2
        ctx.round_rect(sx, ry, sum(widths) + 2, 16, "#0d0f16", border=B["line"])
        xx = sx + 1
        for k, (o, ow) in enumerate(zip(opts, widths)):
            if k == act:
                ctx.round_rect(xx, ry + 1, ow, 14, C_ACCENT)
            ctx.text(o, xx + ow // 2, ry, "#1b1411" if k == act else B["muted"], P, align="center", shadow=False)
            xx += ow
    b_button(ctx, x + 10, y + h - 26, 70, 18, "VOLTAR", kind="ghost")
    b_help(ctx, 0, y + h + 7, [("W/S", "escolhe"), ("A/D", "ajusta"), ("ESC", "volta")], center=UW // 2)
    return ctx



# =================================================================================================
# C · VISOR: a UI é o que o Explorador vê projetado no visor dourado. HUD sem caixas (traço
# dourado/ciano e texto com contorno), borda do capacete escurecendo os cantos, O₂ num arco,
# minimapa redondo de radar, menus como hologramas de canto chanfrado com linhas de varredura.
# =================================================================================================
CV = dict(gold=C_TI, gold2="#b8893e", cyan=C_O2, text="#e9f3f5", muted="#7d97a0", dim="#3d5058",
          bg=(7, 15, 21, 222), bg2=(12, 24, 32, 235), line="#24414d", ink="#05090c")


def c_sprites():
    sp = {}
    # borda do capacete: 480×270 (px da UI), 3 níveis fixos de alfa + o filete dourado
    w, h = UW, UH
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()
    cx, cy = (w - 1) / 2, (h - 1) / 2
    a, b, n = w / 2 + 1, h / 2 + 1, 6.0
    for y in range(h):
        for x in range(w):
            e = (abs(x - cx) / a) ** n + (abs(y - cy) / b) ** n
            if e > 1.0:
                px[x, y] = (5, 7, 10, 235)
            elif e > 0.93:
                px[x, y] = (5, 7, 10, 120)
            elif e > 0.80:
                px[x, y] = (5, 7, 10, 50)
    # filete dourado na borda interna (só onde a borda escura começa)
    edge = []
    for y in range(h):
        for x in range(w):
            if px[x, y][3] == 235:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h and px[xx, yy][3] == 120:
                        edge.append((xx, yy))
    for x, y in edge:
        px[x, y] = (242, 196, 109, 110)
    sp["ui_c_visor"] = (im, 0)
    # canto de colchete (8×8): o "L" dourado usado nos slots e painéis do HUD
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line((0, 0, 4, 0), fill=rgba(C_TI))
    d.line((0, 0, 0, 4), fill=rgba(C_TI))
    d.point((1, 1), rgba(CV["gold2"]))
    sp["ui_c_corner"] = (im, 0)
    return sp


CSP = c_sprites()


def c_brackets(ctx, x, y, w, h, c=C_TI, arm=4):
    for (bx, by, sx, sy) in [(x, y, 1, 1), (x + w - 1, y, -1, 1), (x, y + h - 1, 1, -1), (x + w - 1, y + h - 1, -1, -1)]:
        for i in range(arm):
            ctx.px(bx + i * sx, by, c)
            ctx.px(bx, by + i * sy, c)


def c_text(ctx, s, x, y, c, font=None, align="left"):
    return ctx.text(s, x, y, c, font, align=align, shadow=False, outline=CV["ink"])


def c_panel(ctx, x, y, w, h, title=None, code=None, cut=5):
    ctx.chamfer(x, y, w, h, CV["bg"], cut=cut)
    for yy in range(y + 2, y + h - 2, 3):                 # linhas de varredura (alfa fixo)
        ctx.fill(x + 3, yy, w - 6, 1, (89, 208, 230, 9))
    # contorno chanfrado
    for i in range(h):
        inset = max(0, cut - i, cut - (h - 1 - i))
        if i in (0, h - 1):
            ctx.fill(x + inset, y + i, w - 2 * inset, 1, CV["line"])
        else:
            ctx.px(x + inset, y + i, CV["line"])
            ctx.px(x + w - 1 - inset, y + i, CV["line"])
    # cantos chanfrados em dourado
    for i in range(cut + 1):
        for (ox, oy) in ((x + cut - i, y + i), (x + w - 1 - cut + i, y + i), (x + cut - i, y + h - 1 - i),
                         (x + w - 1 - cut + i, y + h - 1 - i)):
            ctx.px(ox, oy, C_TI)
    if title:
        ctx.fill(x + cut + 3, y + 3, 3, 9, C_TI)
        ctx.text(title, x + cut + 9, y + 1, C_TI, shadow=False)
        ctx.fill(x + cut + 9, y + 12, F.width(title), 1, CV["gold2"])
    if code:
        ctx.text(code, x + w - cut - 4, y + 1, CV["muted"], align="right", shadow=False)


def c_slot(ctx, x, y, st, sel=False, hover=False, dim=False):
    ctx.fill(x + 1, y + 1, 18, 18, (10, 22, 30, 170) if not sel else (242, 196, 109, 42))
    c_brackets(ctx, x, y, 20, 20, C_TI if sel else ("#4f7f8c" if not hover else C_O2), arm=5 if sel else 4)
    if sel:
        c_brackets(ctx, x - 2, y - 2, 24, 24, C_TI, arm=3)
    if hover:
        ctx.fill(x + 1, y + 1, 18, 18, (89, 208, 230, 30))
    if st:
        img = item(st[0])
        if dim:
            img = img.copy()
            img.alpha_composite(Image.new("RGBA", img.size, (7, 15, 21, 160)))
        ctx.icon(img, x + 2, y + 2)
        if st[1] > 1:
            c_text(ctx, str(st[1]), x + 20, y + 11, CV["text"], align="right")


def c_ring(ctx, cx, cy, r0, r1, frac, color, off="#14303a", start=135, sweep=270, segs=18):
    for y in range(cy - r1 - 1, cy + r1 + 2):
        for x in range(cx - r1 - 1, cx + r1 + 2):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            r = math.hypot(dx, dy)
            if r0 <= r <= r1:
                ang = (math.degrees(math.atan2(dy, dx)) - start) % 360
                if ang <= sweep:
                    seg = ang / sweep * segs
                    if seg % 1 > 0.82:
                        continue
                    lit = seg < frac * segs
                    ctx.px(x, y, color if lit else off)


def c_hud(world="dead"):
    ctx = Ctx(WORLD[world])
    ctx.blit_ui(CSP["ui_c_visor"][0], 0, 0)
    # ---- O₂: arco de 270° em volta do número
    gx, gy = 44, 40
    c_ring(ctx, gx, gy, 20, 25, O2_SECONDS / O2_MAX, C_O2)
    c_text(ctx, str(O2_SECONDS), gx + 1, gy - 15, CV["text"], FB, align="center")
    c_text(ctx, "O₂", gx, gy + 3, C_O2, align="center")
    ctx.native(icon16("o2_tank"), (gx - 4) * K, (gy + 17) * K)
    # ---- objetivo: texto solto ao lado do arco
    ox = 76
    c_text(ctx, "OBJETIVO", ox, 14, C_ACCENT)
    ctx.fill(ox, 26, 3, 3, C_TI)
    c_text(ctx, OBJECTIVES[0][1], ox + 6, 20, CV["text"], P)
    ctx.fill(ox, 38, 3, 3, CV["dim"])
    c_text(ctx, OBJECTIVES[1][1], ox + 6, 32, CV["muted"], P)
    # ---- Ti: colchetes, número grande, índices em barras finas, fita do estágio
    w = 142
    px = UW - 22 - w
    c_brackets(ctx, px, 12, w, 64, CV["gold2"], arm=6)
    c_text(ctx, "TI", px + 6, 13, C_TI)
    c_text(ctx, f"+{TI_RATE}/s", px + 20, 10, C_OK, P)
    c_text(ctx, ti_parts(), px + w - 6, 12, C_TI, FB, align="right")
    for i, (key, label, val, unit, col) in enumerate(INDICES):
        yy = 31 + i * 8
        c_text(ctx, label, px + 6, yy - 3, col)
        bw = [0.9, 0.35, 0.29][i]
        ctx.fill(px + 40, yy + 2, 50, 1, "#1d3a44")
        ctx.fill(px + 40, yy + 2, round(50 * bw), 1, col)
        c_text(ctx, val, px + w - 6, yy - 3, CV["text"], align="right")
    # fita do próximo estágio
    ty = 60
    c_text(ctx, NEXT_STAGE, px + 6, ty - 4, CV["text"])
    tx0, tw = px + 40, 72
    ctx.fill(tx0, ty + 3, tw, 1, "#1d3a44")
    ctx.fill(tx0, ty + 3, round(tw * NEXT_PCT), 1, C_TI)
    for k in range(0, 11):
        ctx.fill(tx0 + round(tw * k / 10), ty + (1 if k % 5 == 0 else 2), 1, 3 if k % 5 == 0 else 1,
                 C_TI if k / 10 <= NEXT_PCT else "#2c5260")
    cxp = tx0 + round(tw * NEXT_PCT)
    ctx.fill(cxp - 1, ty - 1, 3, 1, C_TI)
    ctx.px(cxp, ty, C_TI)
    c_text(ctx, f"{int(NEXT_PCT * 100)}%", px + w - 6, ty - 4, C_TI, align="right")
    c_text(ctx, f"faltam {REMAINING} · {ETA}", px + 6, ty + 4, CV["muted"], P)
    # ---- energia
    ey = 86
    bolt(ctx, px + 6, ey, C_ENERGY)
    for k in range(10):
        ctx.fill(px + 16 + k * 5, ey + 2, 4, 4, C_OK if k < 8 else "#1d3a44")
    c_text(ctx, f"{ENERGY[0]}/{ENERGY[1]} kW", px + w - 6, ey - 3, C_OK, P, align="right")
    # ---- radar (minimapa redondo)
    r = 31
    rcx, rcy = UW - 22 - r - 4, 108 + r + 6
    view = minimap_view()
    mask = Image.new("L", view.size, 0)
    ImageDraw.Draw(mask).ellipse((2, 2, view.width - 3, view.height - 3), fill=255)
    disc = Image.new("RGBA", view.size, (0, 0, 0, 0))
    disc.paste(view, (0, 0), mask)
    ctx.native(disc, (rcx - 32) * K, (rcy - 32) * K)
    c_ring(ctx, rcx, rcy, 32, 33, 1.0, CV["gold2"], start=0, sweep=360, segs=36)
    for ang in range(0, 360, 90):
        a = math.radians(ang)
        ctx.fill(round(rcx + math.cos(a) * 35) - 1, round(rcy + math.sin(a) * 35) - 1, 2, 2, C_TI)
    c_text(ctx, "N", rcx, rcy - r - 14, C_TI, align="center")
    c_text(ctx, "[M]", rcx + r + 2, rcy + r - 4, CV["muted"], align="right")
    ctx.native(icon16("scanner"), (rcx - r - 2) * K, (rcy + r - 8) * K)
    # ---- hotbar: colchetes, sem caixa; número embaixo
    hx = (UW - 174) // 2
    hy = UH - 36
    for i, st in enumerate(HOTBAR):
        sx = hx + i * 22
        c_slot(ctx, sx, hy, st, sel=i == HOT_SEL)
        c_text(ctx, str(i + 1), sx + 10, hy + 18, C_TI if i == HOT_SEL else CV["muted"], align="center")
    c_text(ctx, "Gerador de O₂", UW // 2, hy - 17, C_TI, P, align="center")
    # ---- recursos: ícone + número, sem caixa
    x = 22
    for res, n in zip(RES, (92, 6, 43)):
        ctx.native(icon16(res), x * K, (UH - 30) * K)
        x += 11 + c_text(ctx, str(n), x + 10, UH - 34, CV["text"]) + 8
    # ---- dica
    lab = "Abrir baú: Minérios"
    tw = P.width(lab)
    rx = UW - 22 - tw
    c_brackets(ctx, rx - 16, UH - 33, 12, 12, C_TI, arm=3)
    c_text(ctx, "E", rx - 10, UH - 35, C_TI, align="center")
    c_text(ctx, lab, rx, UH - 36, CV["text"], P)
    return ctx


def c_button(ctx, x, y, w, h, label, kind="primary"):
    if kind == "primary":
        ctx.chamfer(x, y, w, h, C_TI, cut=3)
        ctx.fill(x + 3, y + 1, w - 6, 1, "#f8dca0")
        col = "#1b1411"
    elif kind == "ghost":
        ctx.chamfer(x, y, w, h, (20, 40, 50, 220), cut=3)
        c_brackets(ctx, x, y, w, h, C_O2, arm=3)
        col = C_O2
    elif kind == "danger":
        ctx.chamfer(x, y, w, h, (255, 106, 85, 40), cut=3)
        c_brackets(ctx, x, y, w, h, C_ALERT, arm=3)
        col = "#ff8a7a"
    else:
        ctx.chamfer(x, y, w, h, (20, 40, 50, 200), cut=3)
        c_brackets(ctx, x, y, w, h, CV["dim"], arm=3)
        col = CV["muted"]
    ctx.text(label, x + w / 2, y + (h - 5) // 2 - 4, col, align="center", shadow=False)


def c_key(ctx, x, y, label):
    w = F.width(label) + 6
    c_brackets(ctx, x, y, w, 11, C_TI, arm=2)
    ctx.text(label, x + w / 2 + 0.5, y - 2, C_TI, align="center", shadow=False)
    return w


def c_help(ctx, y, pairs, center=UW // 2):
    total = sum(F.width(k) + 6 + 3 + P.width(lab) + 9 for k, lab in pairs)
    x = center - total // 2
    for key, lab in pairs:
        x += c_key(ctx, x, y, key) + 3
        x += c_text(ctx, lab, x, y - 2, CV["muted"], P) + 9


def c_world(world="dead", a=120):
    ctx = Ctx(WORLD[world])
    ctx.fill(0, 0, UW, UH, (4, 10, 14, a))
    ctx.blit_ui(CSP["ui_c_visor"][0], 0, 0)
    return ctx


def c_vtabs(ctx, x, y, labels, active, icons=None, w=92):
    for i, lb in enumerate(labels):
        yy = y + i * 18
        on = i == active
        if on:
            ctx.fill(x, yy, w, 16, (242, 196, 109, 36))
            ctx.fill(x, yy, 2, 16, C_TI)
        if icons:
            ctx.native(item(icons[i]), (x + 4) * K, yy * K)
        ctx.text(lb, x + (22 if icons else 6), yy, C_TI if on else CV["muted"], P, shadow=False)


def c_card(ctx, x, y, w, h, kind, sel, have):
    m = MACHINES[kind]
    st = status(kind, have)
    ctx.chamfer(x, y, w, h, (242, 196, 109, 26) if sel else (12, 26, 34, 200), cut=3)
    c_brackets(ctx, x, y, w, h, C_TI if sel else ("#3d6b78" if st != "locked" else CV["dim"]), arm=5 if sel else 3)
    # prévia (1:1) apoiada numa linha de "chão"
    pv = preview(kind)
    maxh = 58 * K // 2 * 2
    if pv.height > 60:
        pv = pv.crop((0, pv.height - 60, pv.width, pv.height)) if False else pv
    img = pv.copy()
    if st == "locked":
        img.alpha_composite(Image.new("RGBA", img.size, (7, 15, 21, 190)))
    base = y + 38
    ctx.fill(x + 10, base, w - 20, 1, "#1d3a44")
    ctx.native(img, (x + w // 2) * K - img.width // 2, base * K - img.height)
    nm = m["name"].replace(" de gelo", "")
    if P.width(nm) > w - 4:
        nm = nm.replace("Luminária", "Lum.")
    if P.width(nm) > w - 4:
        nm = nm.split()[0]
    ctx.text(nm, x + w // 2, y + 38, CV["text"] if st != "locked" else CV["dim"], P, align="center", shadow=False)
    # custos: ícone + número
    chips = list(m["cost"].items())
    cw = 0
    for res, n in chips:
        cw += 16 + P.width(str(n)) + 4
    cx = x + (w - cw) // 2
    for res, n in chips:
        ok = have[res] >= n
        img = item(res).copy()
        if st == "locked":
            img.alpha_composite(Image.new("RGBA", img.size, (7, 15, 21, 170)))
        ctx.native(img, cx * K, (y + 52) * K)
        col = CV["dim"] if st == "locked" else C_OK if ok else C_ALERT
        cx += 16 + ctx.text(str(n), cx + 15, y + 53, col, P, shadow=False) + 4
        if not ok and st != "locked":
            ctx.fill(cx - 4 - P.width(str(n)) - 1, y + 67, P.width(str(n)) + 1, 1, C_ALERT)
    if st == "locked":
        lock(ctx, x + w - 12, y + 5, CV["muted"])
        ctx.text(f"TI {fmt(m['unlock'])}", x + 5, y + 1, CV["muted"], shadow=False)
    elif st == "missing":
        ctx.chamfer(x + w - 13, y + 3, 10, 10, C_ALERT, cut=1)
        ctx.fill(x + w - 9, y + 5, 2, 4, "#1b1411")
        ctx.fill(x + w - 9, y + 10, 2, 1, "#1b1411")
    else:
        check(ctx, x + w - 12, y + 5, C_OK)
    kw = USE_KW.get(kind)
    if kw and st != "locked":
        bolt(ctx, x + 5, y + 4, C_ENERGY, shadow=False)
        ctx.text(f"{kw}", x + 12, y + 1, C_ENERGY, shadow=False)


def c_fabricador():
    ctx = c_world("dead", 140)
    w, h = 452, 238
    x, y = (UW - w) // 2, 8
    c_panel(ctx, x, y, w, h, "FABRICADOR", "SIS.FAB · BASE")
    c_vtabs(ctx, x + 8, y + 22, FAB_TABS, 0, icons=TAB_ICON, w=106)
    ctx.fill(x + 118, y + 20, 1, h - 30, CV["line"])
    gx, gy = x + 123, y + 20
    cw, chh = 104, 72
    for i, kind in enumerate(TAB_KINDS):
        c_card(ctx, gx + (i % 3) * (cw + 3), gy + (i // 3) * (chh + 3), cw, chh, kind, i == SEL_RECIPE, HAVE)
    # faixa de detalhe embaixo: custo completo do selecionado + botões
    dy = gy + 2 * (chh + 3) + 2
    dw = 3 * cw + 6
    ctx.chamfer(gx, dy, dw, 54, (12, 26, 34, 220), cut=3)
    m = MACHINES[TAB_KINDS[SEL_RECIPE]]
    ctx.text(m["name"], gx + 6, dy, C_TI, P, shadow=False)
    ctx.text(m["desc"] + " · -2 kW", gx + 8 + P.width(m["name"]), dy, CV["muted"], P, shadow=False)
    cx = gx + 6
    for res, n in m["cost"].items():
        hv = HAVE[res]
        ok = hv >= n
        ctx.native(item(res), cx * K, (dy + 14) * K)
        ctx.text(RES_NAME[res], cx + 18, dy + 11, CV["text"], P, shadow=False)
        ctx.text(f"{hv}/{n}", cx + 18, dy + 22, C_OK if ok else C_ALERT, P, shadow=False)
        if ok:
            check(ctx, cx + 20 + P.width(f"{hv}/{n}"), dy + 27, C_OK)
        else:
            ctx.text(f"falta {n - hv}", cx + 22 + P.width(f"{hv}/{n}"), dy + 22, "#ff8a7a", P, shadow=False)
        cx += 80
    c_button(ctx, gx + dw - 92, dy + 14, 86, 18, "FALTA SILÍCIO", kind="danger")
    ctx.text("ENTER fabrica · SHIFT ×5", gx + dw - 6, dy + 35, CV["dim"], align="right", shadow=False)
    c_help(ctx, y + h + 3, [("A/D", "aba"), ("WASD", "escolhe"), ("ENTER", "fabrica"), ("E", "fecha")])
    return ctx


def c_explorer():
    sheet = load(SPR / "player_idle_down.png")
    return sheet.crop((0, 0, 32, 32)).resize((64, 64), Image.NEAREST)


def c_inventario():
    ctx = c_world("dead", 110)
    w, h = 330, 150
    x, y = (UW - w) // 2, 48
    c_panel(ctx, x, y, w, h, "MOCHILA", "11/16")
    # abas no topo, como texto de sistema
    tx = x + 100
    for i, lb in enumerate(["INVENTÁRIO", "FABRICAR", "LOGS 3/7"]):
        on = i == 0
        ww = F.width(lb) + 8
        if on:
            ctx.fill(tx, y + 3, ww, 10, (242, 196, 109, 40))
            ctx.fill(tx, y + 12, ww, 1, C_TI)
        ctx.text(lb, tx + 4, y + 1, C_TI if on else CV["muted"], shadow=False)
        tx += ww + 4
    gx, gy = x + 12, y + 26
    ctx.text("CARGA", gx, gy - 6, CV["muted"], shadow=False)
    for i, st in enumerate(BACKPACK):
        c_slot(ctx, gx + i * 22, gy + 4, st, hover=i == 1)
    ctx.text("HOTBAR", gx, gy + 26, CV["muted"], shadow=False)
    for i, st in enumerate(HOTBAR):
        c_slot(ctx, gx + i * 22, gy + 36, st, sel=i == HOT_SEL)
    # status do traje: o Explorador com linhas até os módulos
    sx, sy = x + w - 128, y + 20
    ctx.chamfer(sx, sy, 118, h - 30, (12, 26, 34, 200), cut=3)
    ctx.text("TRAJE", sx + 6, sy - 1, C_O2, shadow=False)
    ctx.native(c_explorer(), (sx + 6) * K, (sy + 24) * K)
    for i, (kind, lab, ay, slot_y) in enumerate([("o2_tank", "TANQUE", sy + 40, sy + 12),
                                                  ("scanner", "SCANNER", sy + 47, sy + 62)]):
        slot_x = sx + 84
        c_slot(ctx, slot_x, slot_y, (kind, 1))
        # linha do traje até o módulo: sai do corpo, dobra e entra no slot
        ax, kx, cy = sx + 33, sx + 62, slot_y + 10
        ctx.fill(ax, ay, kx - ax, 1, CV["gold2"])
        ctx.fill(kx, min(ay, cy), 1, abs(cy - ay) + 1, CV["gold2"])
        ctx.fill(kx, cy, slot_x - kx - 2, 1, CV["gold2"])
        ctx.fill(ax - 1, ay - 1, 3, 3, C_TI)
        ctx.text(lab, slot_x + 10, slot_y + 18, C_O2, align="center", shadow=False)
    ctx.text("O₂ 220 S", sx + 6, sy + 58, CV["muted"], shadow=False)
    # leitura do item com o mouse (rodapé do painel)
    ry = y + h - 34
    ctx.fill(gx, ry - 2, 180, 1, CV["line"])
    ctx.native(item("ice"), gx * K, ry * K)
    ctx.text("Gelo · 18/50", gx + 20, ry - 2, CV["text"], P, shadow=False)
    ctx.text("usado em: derretedor, tanque, luminária forte", gx + 20, ry + 9, CV["muted"], P, shadow=False) if False else None
    ctx.text("DERRETEDOR · TANQUE · LUMINÁRIA", gx + 20, ry + 10, CV["muted"], shadow=False)
    cursor(ctx, gx + 22 + 12, gy + 4 + 10)
    c_help(ctx, y + h + 6, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")])
    return ctx


def c_bau():
    ctx = c_world("dead", 110)
    cw, h = 196, 196
    gap = 24
    lx = (UW - 2 * cw - gap) // 2
    rx = lx + cw + gap
    ty = 22
    c_panel(ctx, lx, ty, cw, 100, "MOCHILA", "11/16")
    gx = lx + 10
    for i, st in enumerate(BACKPACK):
        c_slot(ctx, gx + i * 22, ty + 22, st)
    for i, st in enumerate(HOTBAR):
        c_slot(ctx, gx + i * 22, ty + 48, st, sel=i == HOT_SEL)
    c_button(ctx, gx, ty + 76, 176, 16, "GUARDAR RECURSOS  >>")
    c_panel(ctx, rx, ty, cw, h, "BAÚ", "6/24")
    ctx.text("Minérios", rx + 5 + 9 + F.width("BAÚ") + 6, ty - 1, CV["text"], P, shadow=False)
    gx2 = rx + 10
    for i, st in enumerate(CHEST):
        c_slot(ctx, gx2 + (i % 8) * 22, ty + 22 + (i // 8) * 22, st, hover=i == 3)
    c_button(ctx, gx2, ty + 92, 176, 16, "<<  PEGAR TUDO", kind="ghost")
    # feixe de transferência entre os painéis
    for k in range(0, gap - 4, 3):
        ctx.fill(lx + cw + 2 + k, ty + 60, 2, 1, C_TI)
        ctx.fill(lx + cw + 2 + k + 1, ty + 64, 2, 1, CV["cyan"])
    # drones
    dy = ty + 114
    ctx.fill(rx + 8, dy, cw - 16, 1, CV["line"])
    ctx.text("DRONES", rx + 10, dy + 1, C_O2, shadow=False)
    ctx.text("ENVIA FERRO", rx + cw - 10, dy + 1, C_TI, align="right", shadow=False)
    for r, (label, chosen, color) in enumerate([("ENVIA", {"iron"}, C_TI), ("RECEBE", set(), C_O2)]):
        yy = dy + 13 + r * 22
        ctx.text(label, rx + 10, yy + 3, CV["muted"], shadow=False)
        for k, res in enumerate(RES):
            on = res in chosen
            c_slot(ctx, rx + 70 + k * 24, yy, (res, 1), sel=on, dim=not on)
    yy = dy + 58
    ctx.text("LOTE", rx + 10, yy + 1, CV["muted"], shadow=False)
    for k, n in enumerate((1, 5, 10, 20)):
        bx = rx + 70 + k * 24
        on = n == 10
        if on:
            ctx.fill(bx, yy, 20, 13, (242, 196, 109, 40))
        c_brackets(ctx, bx, yy, 20, 13, C_TI if on else "#3d6b78", arm=3)
        ctx.text(str(n), bx + 10, yy - 1, C_TI if on else CV["muted"], P, align="center", shadow=False)
    # tooltip
    tx, tyy = gx2 + 3 * 22 + 14, ty + 22 + 16
    ctx.chamfer(tx, tyy, 112, 26, (5, 12, 17, 245), cut=2)
    c_brackets(ctx, tx, tyy, 112, 26, C_O2, arm=3)
    ctx.text("Silício · 22", tx + 6, tyy - 1, CV["text"], P, shadow=False)
    ctx.text("CLIQUE: PEGA A PILHA", tx + 6, tyy + 13, CV["muted"], shadow=False)
    cursor(ctx, gx2 + 3 * 22 + 10, ty + 22 + 10)
    c_help(ctx, ty + h + 6, [("CLIQUE", "pilha"), ("DIR", "1"), ("SHIFT+CLIQUE", "todas"), ("ESC", "fecha")])
    return ctx


def c_fabricar_campo():
    ctx = c_world("mist", 110)
    w, h = 380, 172
    x, y = (UW - w) // 2, 34
    c_panel(ctx, x, y, w, h, "FABRICAR EM CAMPO", "SÓ DO INVENTÁRIO")
    gx, gy = x + 10, y + 22
    cw, chh = 87, 72
    for i, kind in enumerate(FIELD_KINDS):
        c_card(ctx, gx + i * (cw + 3), gy, cw, chh, kind, i == 2, FIELD_HAVE)
    dy = gy + chh + 6
    dw = w - 20
    ctx.chamfer(gx, dy, dw, 60, (12, 26, 34, 220), cut=3)
    m = MACHINES["lamp_t2"]
    ctx.text(m["name"], gx + 6, dy, C_TI, P, shadow=False)
    ctx.text(m["desc"], gx + 10 + P.width(m["name"]), dy, CV["muted"], P, shadow=False)
    cx = gx + 6
    for res, n in m["cost"].items():
        hv = FIELD_HAVE[res]
        ctx.native(item(res), cx * K, (dy + 16) * K)
        ctx.text(RES_NAME[res], cx + 18, dy + 13, CV["text"], P, shadow=False)
        ctx.text(f"{hv}/{n}", cx + 18, dy + 24, C_OK, P, shadow=False)
        check(ctx, cx + 20 + P.width(f"{hv}/{n}"), dy + 29, C_OK)
        cx += 70
    c_button(ctx, gx + dw - 92, dy + 18, 86, 18, "FABRICAR")
    ctx.text("SHIFT ×5", gx + dw - 49, dy + 37, CV["dim"], align="center", shadow=False)
    return ctx


def c_opcoes():
    ctx = c_world("dead", 150)
    w, h = 250, 186
    x, y = (UW - w) // 2, 34
    c_panel(ctx, x, y, w, h, "OPÇÕES", "PAUSA")
    rows = [("GERAL", 1.0), ("EFEITOS", 0.4), ("AMBIENTE", 0.5)]
    for i, (lab, v) in enumerate(rows):
        ry = y + 24 + i * 18
        ctx.text(lab, x + 12, ry, CV["text"], shadow=False)
        for k in range(20):
            on = k < round(20 * v)
            ctx.fill(x + 84 + k * 6, ry + 3, 4, 5 if on else 3, C_TI if on else "#1d3a44")
        ctx.text(f"{round(v * 100)}%", x + w - 12, ry, C_TI, align="right", shadow=False)
    vals = [("TELA CHEIA", "NÃO"), ("ZOOM", "1,5×"), ("INTERFACE", "MÉDIA")]
    for i, (lab, v) in enumerate(vals):
        ry = y + 84 + i * 18
        sel = i == 1
        if sel:
            ctx.fill(x + 6, ry - 2, w - 12, 16, (242, 196, 109, 34))
            ctx.fill(x + 6, ry - 2, 2, 16, C_TI)
        ctx.text(lab, x + 12, ry, CV["text"], shadow=False)
        vv = f"<  {v}  >" if sel else v
        ctx.text(vv, x + w - 12, ry - 3, C_TI if sel else CV["muted"], P, align="right", shadow=False)
    c_button(ctx, x + 12, y + h - 30, 80, 16, "VOLTAR", kind="off")
    c_help(ctx, y + h + 6, [("W/S", "escolhe"), ("A/D", "ajusta"), ("ESC", "volta")])
    return ctx



# =================================================================================================
# Tiras de componentes (botão, aba, slot, barra, tooltip, custo) de cada direção
# =================================================================================================
def strip_bg():
    ctx = Ctx(WORLD["dead"].crop((0, 0, 960, 300)), size=(960, 300))
    ctx.fill(0, 0, UW, 150, (8, 6, 6, 205))
    return ctx


def label(ctx, s, x, y):
    ctx.text(s, x, y, "#c9bdb3")


def a_components():
    ctx = strip_bg()
    label(ctx, "BOTÕES", 10, 4)
    a_button(ctx, 10, 16, 62, 18, "FABRICAR")
    a_button(ctx, 76, 16, 21, 18, "X5")
    a_button(ctx, 101, 16, 86, 18, "FALTA SILÍCIO", on=False, color="#ff8a7a")
    a_button(ctx, 191, 16, 50, 18, "VOLTAR", on=False)
    label(ctx, "ABAS", 10, 40)
    a_tabs(ctx, 10, 52, ["Ativa", "Normal", "Bloqueada"], 0, muted_from=2)
    label(ctx, "SLOTS", 10, 72)
    a_slot(ctx, 12, 86, None)
    a_slot(ctx, 36, 86, ("iron", 42))
    a_slot(ctx, 60, 86, ("ice", 18), hover=True)
    a_slot(ctx, 86, 86, ("o2", 2), sel=True)
    label(ctx, "TECLA", 120, 72)
    a_key(ctx, 120, 88, "E")
    a_key(ctx, 137, 88, "SHIFT")
    label(ctx, "BARRAS (LED)", 260, 4)
    a_leds(ctx, 261, 18, 14, 10, C_O2, seg_w=6, h=6, off="#14262b")
    a_leds(ctx, 261, 30, 16, 8, C_TI, seg_w=4, h=5)
    a_leds(ctx, 261, 41, 10, 8, C_OK, seg_w=4, h=5)
    a_leds(ctx, 330, 41, 10, 10, C_ALERT, seg_w=4, h=5)
    label(ctx, "CUSTO: TEM · FALTA · TRANCADO", 260, 52)
    xx = 260
    xx += a_cost(ctx, xx, 64, "iron", 12, 92) + 4
    xx += a_cost(ctx, xx, 64, "silicon", 8, 6) + 4
    a_cost(ctx, xx, 64, "ice", 30, 0, locked=True)
    label(ctx, "TOOLTIP", 260, 88)
    a_tooltip(ctx, 260, 100, "Gelo · 18", "minério · empilha até 50")
    label(ctx, "MOLDURA 9-SLICE", 400, 88)
    a_window(ctx, 400, 100, 72, 44, "TÍTULO")
    return ctx


def b_components():
    ctx = strip_bg()
    label(ctx, "BOTÕES", 10, 4)
    b_button(ctx, 10, 16, 64, 18, "FABRICAR")
    b_button(ctx, 78, 16, 50, 18, "VOLTAR", kind="ghost")
    b_button(ctx, 132, 16, 90, 18, "FALTAM 2 SILÍCIO", kind="danger")
    b_button(ctx, 226, 16, 28, 18, "TI", kind="off")
    label(ctx, "ABAS (SEGMENTADA · COM ÍCONE)", 10, 40)
    b_segmented(ctx, 10, 52, ["Ativa", "Normal", "LOGs"], 0, dot=2)
    b_icon_tabs(ctx, 10, 72, 0, labels=["Terraformação", "", "", ""], icons=["o2", "solar", "drill", "chest"],
                locked=(2,))
    label(ctx, "SLOTS", 10, 96)
    b_slot(ctx, 12, 118, None)
    b_slot(ctx, 36, 118, ("iron", 42))
    b_slot(ctx, 60, 118, ("ice", 18), hover=True)
    b_slot(ctx, 86, 118, ("o2", 2), sel=True, num=4)
    label(ctx, "TECLA", 130, 96)
    b_key(ctx, 130, 110, "E")
    b_key(ctx, 145, 110, "SHIFT")
    label(ctx, "BARRAS", 290, 4)
    b_bar(ctx, 290, 18, 90, 0.72, C_O2, h=4)
    b_bar(ctx, 290, 26, 90, 0.48, C_TI, h=3)
    b_bar(ctx, 290, 33, 90, 0.8, C_OK, h=3)
    b_bar(ctx, 290, 40, 90, 1.0, C_ALERT, h=3)
    label(ctx, "CUSTO: CHIP (LISTA) · LINHA (DETALHE)", 290, 52)
    xx = 290
    xx += b_chip(ctx, xx, 64, "iron", 12, 92) + 3
    xx += b_chip(ctx, xx, 64, "silicon", 8, 6) + 3
    b_chip(ctx, xx, 64, "ice", 30, 0, locked=True)
    label(ctx, "TOOLTIP", 290, 92)
    ctx.round_rect(290, 104, 104, 28, (11, 13, 20, 250), border=B["line2"])
    ctx.text("Gelo · 18", 296, 104, B["text"], P, shadow=False)
    ctx.text("RECURSO · USADO EM 3", 296, 118, B["muted"], shadow=False)
    return ctx


def c_components():
    ctx = strip_bg()
    label(ctx, "BOTÕES", 10, 4)
    c_button(ctx, 10, 16, 64, 16, "FABRICAR")
    c_button(ctx, 78, 16, 64, 16, "PEGAR TUDO", kind="ghost")
    c_button(ctx, 146, 16, 82, 16, "FALTA SILÍCIO", kind="danger")
    c_button(ctx, 232, 16, 40, 16, "VOLTAR", kind="off")
    label(ctx, "ABAS (VERTICAIS)", 10, 40)
    ctx.chamfer(10, 52, 116, 40, CV["bg"], cut=3)
    c_vtabs(ctx, 12, 54, ["Terraformação", "Energia"], 0, icons=["o2", "solar"], w=110)
    label(ctx, "SLOTS (COLCHETE)", 140, 40)
    c_slot(ctx, 142, 54, None)
    c_slot(ctx, 166, 54, ("iron", 42))
    c_slot(ctx, 190, 54, ("ice", 18), hover=True)
    c_slot(ctx, 216, 54, ("o2", 2), sel=True)
    label(ctx, "TECLA", 140, 80)
    c_key(ctx, 140, 94, "E")
    c_key(ctx, 154, 94, "SHIFT")
    label(ctx, "ARCO DE O₂ · BARRA · FITA", 290, 4)
    c_ring(ctx, 310, 36, 14, 18, 0.7, C_O2, segs=14)
    c_text(ctx, "158", 311, 27, CV["text"], align="center")
    for k in range(10):
        ctx.fill(336 + k * 5, 26, 4, 4, C_OK if k < 8 else "#1d3a44")
    ctx.fill(336, 38, 72, 1, "#1d3a44")
    ctx.fill(336, 38, 35, 1, C_TI)
    for k in range(11):
        ctx.fill(336 + round(72 * k / 10), 36 if k % 5 == 0 else 37, 1, 3 if k % 5 == 0 else 1,
                 C_TI if k <= 4 else "#2c5260")
    label(ctx, "CARTÃO DE RECEITA", 290, 60)
    c_card(ctx, 290, 72, 92, 72, "heater", True, HAVE)
    c_card(ctx, 386, 72, 92, 72, "o2_t2", False, HAVE)
    label(ctx, "TOOLTIP", 10, 98)
    ctx.chamfer(10, 110, 112, 26, (5, 12, 17, 245), cut=2)
    c_brackets(ctx, 10, 110, 112, 26, C_O2, arm=3)
    ctx.text("Gelo · 18", 16, 109, CV["text"], P, shadow=False)
    ctx.text("CLIQUE: PEGA A PILHA", 16, 123, CV["muted"], shadow=False)
    label(ctx, "PAINEL", 140, 112) if False else None
    c_panel(ctx, 140, 108, 140, 38, "PAINEL", "SIS")
    return ctx


def export_pending():
    """Molduras que as direções usariam no jogo (px da UI). Ficam em _pending até o dono escolher."""
    PEND.mkdir(parents=True, exist_ok=True)
    for f in PEND.glob("ui_*.png"):
        f.unlink()
    for sp in (ASP, BSP, CSP):
        for name, (im, _) in sp.items():
            im.save(PEND / f"{name}.png")


BEFORE = {"hud": "minimapa.png", "inventario": "equipamento.png", "fabricador": "crafting.png",
          "fabricar": "inventario_fabricar_grande.png", "bau": "bau.png", "opcoes": "pausa_opcoes.png",
          "mapa_superficie": "mapa_grande.png", "mapa_caverna": "mapa_caverna.png"}


def copy_before():
    dst = OUT / "before"
    dst.mkdir(parents=True, exist_ok=True)
    for key, name in BEFORE.items():
        src = ROOT / "reports" / "dev" / name
        if src.exists():
            im = Image.open(src).convert("RGB")
            if im.size != (960, 540):                  # print do tamanho Grande em 1920×1080: reduz 2× exato
                im = im.resize((960, 540), Image.NEAREST)
            im.save(dst / f"{key}.png")



# =================================================================================================
# B2 · versão final: base B + 3 misturas pedidas pelo dono
#   1. painel do Ti com a organização da A (ÍNDICE TI, número grande, índices alinhados, barra
#      segmentada do estágio) desenhado no estilo da B;
#   2. traje do inventário com o Explorador e linhas até os módulos (ideia da C) no estilo da B;
#   3. drones do baú: o ícone do material é o botão (aceso/apagado, como na A), estilo da B.
# =================================================================================================
def b2_segments(ctx, x, y, n, lit, color, seg_w=4, h=4, off="#262b3b"):
    for i in range(n):
        ctx.fill(x + i * (seg_w + 1), y, seg_w, h, color if i < lit else off)
        if i < lit:
            ctx.fill(x + i * (seg_w + 1), y, seg_w, 1, mix(color, "#ffffff", 0.35))
    return n * (seg_w + 1) - 1


def b2_ti_panel(ctx, px, y, w):
    """Organização da A (título, +/s, número grande, índices, estágio segmentado, faltam) no cartão da B.
    Devolve onde o cartão acaba."""
    h = 88
    b_card(ctx, px, y, w, h)
    ctx.text("ÍNDICE TI", px + 6, y - 1, C_TI, shadow=False)
    ctx.text(f"+{TI_RATE}/s", px + w - 6, y - 3, C_OK, P, align="right", shadow=False)
    ctx.round_rect(px + 4, y + 12, w - 8, 19, "#0b0d13")
    ctx.text("TI", px + 9, y + 15, B["dim"], shadow=False)
    ctx.text(ti_parts(), px + w - 9, y + 11, C_TI, FB, align="right", shadow=False)
    for i, (key, label, val, unit, col) in enumerate(INDICES):
        yy = y + 34 + i * 9
        ctx.fill(px + 6, yy + 1, 3, 3, col)
        ctx.text(label, px + 13, yy - 4, B["text"], shadow=False)
        uw = F.width(unit)
        ctx.text(unit, px + w - 6, yy - 4, B["dim"], align="right", shadow=False)
        ctx.text(val, px + w - 9 - uw, yy - 4, B["text"], align="right", shadow=False)
    ctx.fill(px + 6, y + 62, w - 12, 1, B["line"])
    ctx.text(NEXT_STAGE, px + 6, y + 61, B["text"], shadow=False)
    b2_segments(ctx, px + 40, y + 66, 16, round(16 * NEXT_PCT), C_TI)
    ctx.text(f"{int(NEXT_PCT * 100)}%", px + w - 6, y + 61, C_TI, align="right", shadow=False)
    ctx.text(f"faltam {REMAINING} · {ETA}", px + 6, y + 70, B["muted"], P, shadow=False)
    return y + h


def b2_hud(world="dead"):
    return b_hud(world, v2=True)


def b2_explorer():
    return load(SPR / "player_idle_down.png").crop((0, 0, 32, 32)).resize((64, 64), Image.NEAREST)


def b2_traje(ctx, x, y, w, h):
    """Cartão do traje: o Explorador no meio, uma linha até cada módulo (tanque à esquerda, scanner à direita)."""
    ctx.round_rect(x, y, w, h, B["card"])
    ctx.text("TRAJE", x + 6, y - 1, C_O2, shadow=False)
    ex = x + w // 2 - 16
    ey = y + 12
    ctx.round_rect(ex - 2, ey + 30, 36, 3, "#0b0d13")              # sombrinha no chão
    ctx.native(b2_explorer(), ex * K, ey * K)
    mods = [("o2_tank", "TANQUE", "220 s", x + 8, ey + 18, ex + 6), ("scanner", "SCANNER", "equipado", x + w - 28, ey + 22, ex + 26)]
    for kind, lab, sub, sx, body_y, body_x in mods:
        sy = ey + 6
        b_slot(ctx, sx, sy, (kind, 1))
        cy = sy + 10
        left = sx < ex
        x0 = sx + 21 if left else body_x + 2
        x1 = body_x - 2 if left else sx - 2
        kx = (x0 + 8) if left else (x1 - 8)
        # linha: sai do slot reta, dobra e chega no corpo
        if left:
            ctx.fill(x0, cy, kx - x0 + 1, 1, B["line2"])
            ctx.fill(kx, min(cy, body_y), 1, abs(body_y - cy) + 1, B["line2"])
            ctx.fill(kx, body_y, x1 - kx, 1, B["line2"])
            ctx.fill(x1 - 1, body_y - 1, 3, 3, C_O2)
        else:
            ctx.fill(x0, body_y, kx - x0 + 1, 1, B["line2"])
            ctx.fill(kx, min(cy, body_y), 1, abs(body_y - cy) + 1, B["line2"])
            ctx.fill(kx, cy, x1 - kx + 1, 1, B["line2"])
            ctx.fill(x0 - 1, body_y - 1, 3, 3, C_O2)
        if left:
            ctx.text(lab, sx, sy + 19, B["text"], shadow=False)
            ctx.fill(sx, sy + 31, 3, 3, C_OK)
            ctx.text(sub, sx + 5, sy + 26, C_OK, P, shadow=False)
        else:
            ctx.text(lab, sx + 20, sy + 19, B["text"], align="right", shadow=False)
            sw_ = P.width(sub)
            ctx.fill(sx + 20 - sw_ - 5, sy + 31, 3, 3, C_OK)
            ctx.text(sub, sx + 20, sy + 26, C_OK, P, align="right", shadow=False)


def b2_inventario():
    ctx = dim_world("dead", 110)
    w, h = 330, 186
    x, y = (UW - w) // 2, 30
    b_window(ctx, x, y, w, h, "Inventário", "11/16")
    sw = b_segmented(ctx, 0, -100, ["Inventário", "Fabricar", "LOGs 3/7"], 0)
    b_segmented(ctx, x + (w - sw) // 2, y + 22, ["Inventário", "Fabricar", "LOGs 3/7"], 0, dot=2)
    gx, gy = x + 10, y + 46
    ctx.text("MOCHILA", gx, gy - 4, B["muted"], shadow=False)
    for i, st in enumerate(BACKPACK):
        b_slot(ctx, gx + i * 22, gy + 6, st, hover=i == 1)
    ctx.text("HOTBAR", gx, gy + 28, B["muted"], shadow=False)
    for i, st in enumerate(HOTBAR):
        b_slot(ctx, gx + i * 22, gy + 38, st, sel=i == HOT_SEL)
    b2_traje(ctx, gx, gy + 64, 174, h - 64 - 46 - 8)
    # painel do item (igual à B)
    dx, dw = x + w - 134, 126
    ctx.round_rect(dx, y + 42, dw, h - 50, B["card"])
    big = item("ice").resize((64, 64), Image.NEAREST)
    ctx.round_rect(dx + 6, y + 48, 36, 36, "#0d0f16")
    ctx.native(big, (dx + 8) * K, (y + 50) * K)
    ctx.text("Gelo", dx + 48, y + 47, B["text"], P, shadow=False)
    ctx.text("RECURSO", dx + 48, y + 58, C_O2, shadow=False)
    ctx.text("18 / 50", dx + 48, y + 68, B["muted"], P, shadow=False)
    ctx.fill(dx + 6, y + 90, dw - 12, 1, B["line"])
    ctx.text("USADO EM", dx + 6, y + 89, B["muted"], shadow=False)
    for i, k in enumerate(["melter", "o2_tank", "lamp_t2"]):
        yy = y + 100 + i * 20
        ctx.native(item(k), (dx + 6) * K, yy * K)
        ctx.text(MACHINES[k]["name"], dx + 26, yy + 1, B["text"], P, shadow=False)
    b_help(ctx, 0, y + h + 7, [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")],
           center=UW // 2)
    cursor(ctx, gx + 22 + 12, gy + 6 + 10)
    return ctx


def b2_icon_button(ctx, x, y, res, on, color, size=20):
    """Toggle de drone: o ícone é o botão. Aceso = fundo tingido, borda na cor da linha, ícone cheio;
    apagado = fundo escuro, borda neutra, ícone escurecido."""
    if on:
        c = rgba(color)
        ctx.round_rect(x, y, size, size, (c[0], c[1], c[2], 46), border=color)
        ctx.fill(x + 2, y + size - 2, size - 4, 1, color)
    else:
        ctx.round_rect(x, y, size, size, "#0d0f16", border=B["line"])
    img = item(res).copy()
    if not on:
        img.alpha_composite(Image.new("RGBA", img.size, (13, 15, 22, 175)))
    ctx.native(img, (x + (size - 16) // 2) * K, (y + (size - 16) // 2 - (1 if on else 0)) * K)


def b2_bau():
    ctx = b_bau()
    # apaga a seção DRONES da B e redesenha no padrão novo (mesmas coordenadas do b_bau)
    cw, h, mid = 184, 196, 58
    lx = (UW - 2 * cw - mid) // 2
    rx = lx + cw + mid
    ty = 14
    dy = ty + 100
    ctx2 = b2_drones_base(ctx, rx, dy, cw, ty + h)
    return ctx2


def b2_drones_base(ctx, rx, dy, cw, bottom):
    ctx.fill(rx + 1, dy, cw - 2, bottom - dy - 1, (15, 17, 25, 255))
    ctx.fill(rx + 8, dy, cw - 16, 1, B["line"])
    ctx.text("DRONES", rx + 8, dy + 1, C_O2, shadow=False)
    ctx.text("· envia ferro", rx + 12 + F.width("DRONES"), dy - 1, C_TI, P, shadow=False)
    for r, (label, chosen, color) in enumerate([("Envia", {"iron"}, C_ACCENT), ("Recebe", set(), C_O2)]):
        yy = dy + 14 + r * 25
        ctx.text(label, rx + 8, yy + 2, B["muted"], P, shadow=False)
        for k, res in enumerate(RES):
            b2_icon_button(ctx, rx + 60 + k * 25, yy, res, res in chosen, color, size=22)
    yy = dy + 66
    ctx.text("Lote", rx + 8, yy + 1, B["muted"], P, shadow=False)
    for k, n in enumerate((1, 5, 10, 20)):
        bx = rx + 60 + k * 25
        on = n == 10
        ctx.round_rect(bx, yy, 22, 16, B["hover"] if on else "#0d0f16", border=C_ACCENT if on else B["line"])
        ctx.text(str(n), bx + 11, yy, B["text"] if on else B["muted"], P, align="center", shadow=False)
    return ctx


def b2_components():
    ctx = strip_bg()
    label(ctx, "PAINEL DO TI (A + B)", 10, 4)
    b2_ti_panel(ctx, 10, 18, 150)
    label(ctx, "TRAJE (C + B)", 172, 4)
    b2_traje(ctx, 172, 18, 174, 76)
    label(ctx, "DRONES: O ÍCONE É O BOTÃO", 172, 100)
    for k, (res, on, col) in enumerate([("iron", True, C_ACCENT), ("silicon", False, C_ACCENT),
                                         ("ice", True, C_O2), ("ice", False, C_O2)]):
        b2_icon_button(ctx, 172 + k * 26, 114, res, on, col, size=22)
    ctx.text("envia: aceso / apagado · recebe: aceso / apagado", 172, 136, B["muted"], P, shadow=False) if False else None
    label(ctx, "ENVIA ↑ · RECEBE ↓", 280, 120) if False else None
    label(ctx, "BOTÕES", 356, 4)
    b_button(ctx, 356, 16, 64, 18, "FABRICAR")
    b_button(ctx, 356, 38, 112, 18, "FALTAM 2 SILÍCIO", kind="danger")
    b_button(ctx, 424, 16, 44, 18, "VOLTAR", kind="ghost")
    label(ctx, "CUSTO (CHIP)", 356, 62)
    xx = 356
    xx += b_chip(ctx, xx, 74, "iron", 12, 92) + 3
    b_chip(ctx, xx, 74, "silicon", 8, 6)
    label(ctx, "SLOTS", 356, 98)
    b_slot(ctx, 358, 112, ("iron", 42))
    b_slot(ctx, 382, 112, ("o2", 2), sel=True)
    b_slot(ctx, 406, 112, None)
    return ctx


def b2_crops():
    """Recortes antes (B) × depois (B2) só das 3 partes que mudaram, 2× pra ver o pixel."""
    parts = {
        "ti": ("b_hud.png", "b2_hud.png", (UW - 6 - 152, 4, 154, 92)),
        "traje": ("b_inventario.png", "b2_inventario.png", None),
        "drones": ("b_bau.png", "b2_bau.png", None),
    }
    out = {}
    cw, mid = 184, 58
    rx = (UW - 2 * cw - mid) // 2 + cw + mid
    boxes = {"ti": (UW - 6 - 152, 4, 154, 132), "traje": ((UW - 330) // 2, 76, 192, 140),
             "drones": (rx - 2, 110, cw + 4, 100)}
    for key, (a, b, _) in parts.items():
        x, y, w, h = boxes[key]
        box = (x * K, y * K, (x + w) * K, (y + h) * K)
        for tag, name in (("antes", a), ("depois", b)):
            im = Image.open(OUT / name).crop(box)
            im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
            im.save(OUT / f"b2_cmp_{key}_{tag}.png")



# =================================================================================================
# MAPA ABERTO (M) no estilo B2 · proposta principal (mapa + coluna lateral) e 1 variação (panorâmico)
# =================================================================================================
import json  # noqa: E402

MAPD = json.loads((SRC / "map_markers.json").read_text())
MAPTEX = {k: load(SRC / f"map_{k}_tex.png") for k in ("surface", "cave")}
INK = "#0b0d13"
MK = {"you": "#ffd84a", "base": C_O2, "crater": "#ffffff", "ramp_up": "#7fd6a0", "wreck": "#f2a33a",
      "wreck_empty": "#7a6c62", "terminal": "#7fd6a0", "machine": "#d9dde6", "chest": "#d8b27a"}
VEIN_C = {"iron": "#e8a066", "silicon": "#c3d1e2", "ice": "#a6ecff"}
WRECK_NAME = {"cargo": "Nave de carga", "module": "Módulo da colônia", "probe": "Sonda"}


def map_texture(layer, k, window=None):
    """Textura da camada esticada k× (px nativos por tile). Não visto = fundo da B com grade de pontos
    a cada 8 tiles; a borda do explorado ganha 1 tile de "névoa" mais clara."""
    tex = MAPTEX[layer]
    if window:
        tex = tex.crop(window)
    w, h = tex.size
    src = tex.load()
    out = Image.new("RGBA", (w, h), rgba(INK))
    o = out.load()
    x0, y0 = (window[0], window[1]) if window else (0, 0)
    for y in range(h):
        for x in range(w):
            c = src[x, y]
            if c[:3] != (0, 0, 0):
                o[x, y] = c
                continue
            near = any(0 <= x + dx < w and 0 <= y + dy < h and src[x + dx, y + dy][:3] != (0, 0, 0)
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if near:
                o[x, y] = rgba("#1d2231")
            elif (x + x0) % 8 == 0 and (y + y0) % 8 == 0:
                o[x, y] = rgba("#202638")
    return out.resize((w * k, h * k), Image.NEAREST)


# Marcador da base: o módulo de pouso (pod.png) em pictograma. 3 opções; o dono escolheu a A (módulo de frente).
BASE_OPTS = {
    "base_a": [  # módulo de frente: telhado, antena com luz vermelha, janelas, faixa laranja, porta, base escura
        "........o....", "..ooo..oto...", ".orrro..o....", "ooooooooooooo", "o#####+#####o", "o#w#w####dd#o",
        "osssssss#ddso", "o-------#dd-o", "ooooooooooooo", "okkkkkkkkkkko", ".ooooooooooo."],
    "base_b": [  # o mesmo módulo de pé nas 4 pernas de pouso: lê como nave
        "..........o....", "...ooo...oto...", "..orrro...o....", ".ooooooooooooo.", ".o#####+#####o.",
        ".o#w#w####dd#o.", ".osssssss#ddso.", ".o-------#dd-o.", ".ooooooooooooo.", "..o.o.....o.o..",
        ".o..o.....o..o.", "oo..oo...oo..oo"],
    "base_c": [  # cápsula clássica: domo, escotilha, faixa, pernas
        ".......o.......", "......oto......", ".....ooooo.....", "...oo#####oo...", "..o##+######o..",
        "..o###owwo##o..", ".o####owwo###o.", ".o#####oo####o.", "osssssssssssssо".replace("о", "o"),
        "o-------------o", ".ooooooooooooo.", "..o..o...o..o..", ".oo..oo.oo..oo."],
}
BASE_CHOSEN = "base_a"


def _pix(rows, cmap):
    h, w = len(rows), max(len(r) for r in rows)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in cmap:
                im.putpixel((x, y), rgba(cmap[ch]))
    return im


def marker(kind, color=None, direction="down", big=False):
    """Pictograma do marcador em px nativos (contorno INK). Centro = meio da imagem."""
    c = color or MK.get(kind, "#ffffff")
    hi = mix(c, "#ffffff", 0.5)
    sh = mix(c, "#000000", 0.35)
    cm = {"o": INK, "#": c, "+": hi, "-": sh, "d": INK}
    if kind == "you":
        rows = ["....o....", "...o#o...", "..o#+#o..", ".o##+##o.", "o###+###o", "o##o#o##o", "o#o.o.o#o",
                "oo.....oo"]
        im = _pix(rows, cm)
        rot = {"up": 0, "left": 90, "down": 180, "right": 270}[direction]
        return im.rotate(rot, expand=True)
    if kind in BASE_OPTS or kind == "base":
        rows = BASE_OPTS[BASE_CHOSEN if kind == "base" else kind]
        return _pix(rows, {"o": INK, "#": "#efe5da", "+": "#ffffff", "-": "#b9ab9c", "s": C_ACCENT, "d": "#2d3a40",
                           "w": C_O2, "r": "#4a5060", "t": "#ff6a55", "k": "#3a3f4a"})
    if kind in ("crater", "ramp_up"):
        rows = ["...ooooo...", "..o#####o..", ".o#ooooo#o.", "o#o.....o#o", "o#o.....o#o", "o#o.....o#o",
                "o#o.....o#o", "o#o.....o#o", ".o#ooooo#o.", "..o#####o..", "...ooooo..."]
        im = _pix(rows, cm)
        arrow = ["#####", ".###.", "..#.."] if kind == "crater" else ["..#..", ".###.", "#####"]
        for y, r in enumerate(arrow):
            for x, ch in enumerate(r):
                if ch == "#":
                    im.putpixel((3 + x, 4 + y), rgba(c))
        return im
    if kind in ("wreck", "wreck_empty"):
        rows = ["....o....", "...o#o...", "..o#+#o..", ".o#+###o.", "o#######o", ".o#####o.", "..o#-#o..",
                "...o-o...", "....o...."]
        if kind == "wreck_empty":
            rows = ["....o....", "...o#o...", "..o#o#o..", ".o#o.o#o.", "o#o...o#o", ".o#o.o#o.", "..o#o#o..",
                    "...o#o...", "....o...."]
        return _pix(rows, cm)
    if kind == "vein":
        rows = [".ooooo.", "o##+##o", "o#+###o", "o#####o", "o#####o", "o-###-o", ".ooooo."]
        return _pix(rows, cm)
    if kind == "terminal":
        rows = ["ooooooooo", "o#######o", "o#d#####o", "o##d####o", "o#d##dd#o", "o#######o", "ooooooooo"]
        return _pix(rows, cm)
    if kind == "machine":
        rows = ["ooooooo", "o-----o", "o#####o", "o#+###o", "o#####o", "ooooooo"]
        cm["-"] = C_ACCENT
        return _pix(rows, cm)
    if kind == "chest":
        rows = ["ooooooooo", "o#######o", "o-------o", "o###d###o", "o#######o", "ooooooooo"]
        return _pix(rows, cm)
    raise KeyError(kind)


def put_marker(img, im, x, y):
    img.alpha_composite(im, (round(x - im.width / 2), round(y - im.height / 2)))


def m2(im):
    """Pictograma no px da UI (2 px nativos por pixel): o tamanho que lê no mapa."""
    return im.resize((im.width * 2, im.height * 2), Image.NEAREST)


def map_markers(img, layer, k, origin=(0, 0), hover=None):
    """Desenha os marcadores na imagem do mapa (px nativos, k por tile). Devolve {nome: (x, y)} pro tooltip."""
    d = MAPD[layer]
    ox, oy = origin
    at = lambda tx, ty: (round((tx - ox) * k), round((ty - oy) * k))  # noqa: E731
    pos = {}
    for kind, tx, ty in d["machines"]:
        put_marker(img, m2(marker("chest" if kind == "chest" else "machine")), *at(tx, ty))
    for res, tx, ty in d["veins"]:
        put_marker(img, m2(marker("vein", VEIN_C[res])), *at(tx, ty))
    for i, (kind, tx, ty, empty) in enumerate(d["wrecks"]):
        x, y = at(tx, ty)
        put_marker(img, m2(marker("wreck_empty" if empty else "wreck")), x, y)
        pos[f"wreck{i}"] = (x, y)
    for i, (tx, ty) in enumerate(d["terminals"]):
        x, y = at(tx, ty)
        put_marker(img, m2(marker("terminal")), x, y)
        pos[f"terminal{i}"] = (x, y)
    if d["crater"]:
        put_marker(img, m2(marker("crater" if d.get("base") else "ramp_up")), *at(*d["crater"]))
    if d.get("base"):
        put_marker(img, m2(marker("base")), *at(*d["base"]))
    px, py, pdir = d["player"]
    x, y = at(px, py)
    ring = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, 15, 15), outline=rgba("#ffd84a", 130), width=1)
    put_marker(img, m2(ring), x, y)
    put_marker(img, m2(marker("you", direction=pdir)), x, y)
    pos["you"] = (x, y)
    if hover and hover in pos:
        hx, hy = pos[hover]
        hl = Image.new("RGBA", (15, 15), (0, 0, 0, 0))
        dr = ImageDraw.Draw(hl)
        for (a, b) in [((0, 0), (3, 0)), ((0, 0), (0, 3)), ((11, 0), (14, 0)), ((14, 0), (14, 3)),
                       ((0, 11), (0, 14)), ((0, 14), (3, 14)), ((14, 11), (14, 14)), ((11, 14), (14, 14))]:
            dr.line((a, b), fill=rgba(C_ACCENT))
        put_marker(img, m2(hl), hx, hy)
    return pos


def legend_rows(layer):
    d = MAPD[layer]
    rows = [("you", None, "Você", {"right": "olhando a leste", "down": "olhando ao sul", "up": "olhando ao norte",
                                   "left": "olhando a oeste"}[d["player"][2]])]
    if layer == "surface":
        rows.append(("base", None, "Base", "cápsula"))
        rows.append(("crater", None, "Cratera", "desce pra caverna"))
        full = sum(1 for w in d["wrecks"] if not w[3])
        rows.append(("wreck", None, "Destroço", f"{full} com caixa"))
        rows.append(("wreck_empty", None, "Destroço vazio", str(len(d["wrecks"]) - full)))
    else:
        rows.append(("ramp_up", None, "Rampa", "sobe pra superfície"))
        rows.append(("terminal", None, "Terminal", f"{len(d['terminals'])} vistos"))
    rows.append(("vein", "veins", "Veios", str(len(d["veins"]))))
    if layer == "surface":
        n_m = sum(1 for m in d["machines"] if m[0] != "chest")
        n_c = sum(1 for m in d["machines"] if m[0] == "chest")
        rows.append(("machine", None, "Máquinas", str(n_m)))
        rows.append(("chest", None, "Baús", str(n_c)))
    return rows


def legend_icon(kind, special):
    if special == "veins":
        im = Image.new("RGBA", (25, 7), (0, 0, 0, 0))
        for i, res in enumerate(RES):
            im.alpha_composite(marker("vein", VEIN_C[res]), (i * 9, 0))
        return m2(im)
    return m2(marker(kind, direction="right"))


def map_tooltip(ctx, x, y, layer, key, right=UW):
    d = MAPD[layer]
    if key.startswith("wreck"):
        kind, tx, ty, empty = d["wrecks"][int(key[5:])]
        icon, title, sub = marker("wreck_empty" if empty else "wreck"), f"Destroço · {WRECK_NAME[kind]}", \
            ("caixa vazia" if empty else "caixa cheia")
        px, py = d["player"][:2]
    else:
        tx, ty = d["terminals"][int(key[8:])]
        icon, title, sub = marker("terminal"), "Terminal da colônia", "LOG 06 · lido"
        px, py = d["player"][:2]
    dist = round(((tx - px) ** 2 + (ty - py) ** 2) ** 0.5)
    ang = math.degrees(math.atan2(ty - py, tx - px))
    card = ["a leste", "a sudeste", "ao sul", "a sudoeste", "a oeste", "a noroeste", "ao norte",
            "a nordeste"][round(ang / 45) % 8]
    sub = f"{sub} · {dist} tiles {card}"
    w = max(P.width(title), P.width(sub)) + 28
    x = max(4, min(x, right - w))
    ctx.round_rect(x, y, w, 28, (11, 13, 20, 250), border=B["line2"])
    icon = m2(icon)
    ctx.native(icon, (x + 10) * K - icon.width // 2, (y + 14) * K - icon.height // 2)
    ctx.text(title, x + 21, y, B["text"], P, shadow=False)
    ctx.text(sub, x + 21, y + 12, B["muted"], P, shadow=False)


def map_header(ctx, x, y, w, layer, close_hover=False):
    ctx.text("Mapa", x + 8, y + 2, B["text"], P, shadow=False)
    labels = ["Superfície", "Caverna"]
    b_segmented(ctx, x + 40, y + 3, labels, 0 if layer == "surface" else 1)
    pct = MAPD[layer]["explored"]
    # fechar: botão fantasma com a tecla
    bw = 62
    bx = x + w - bw - 6
    if close_hover:
        ctx.round_rect(bx, y + 3, bw, 15, B["hover"], border=C_ACCENT)
    else:
        ctx.round_rect(bx, y + 3, bw, 15, B["card2"], border=B["line2"])
    ctx.text("FECHAR", bx + 6, y + 2, B["text"] if close_hover else B["muted"], shadow=False)
    ctx.round_rect(bx + bw - 15, y + 5, 11, 11, "#0d0f16", border=B["line2"])
    ctx.text("M", bx + bw - 9, y + 3, B["text"], align="center", shadow=False)
    ex = bx - 100
    ctx.text("EXPLORADO", ex, y + 2, B["muted"], shadow=False)
    ctx.text(f"{round(pct * 100)}%", bx - 8, y + 2, C_TI, align="right", shadow=False)
    b_bar(ctx, ex, y + 13, 92, pct, C_TI, h=2)


def map_main(layer, hover=None, close_hover=False):
    """Proposta principal: mapa inteiro à esquerda, coluna com a legenda (marcador + nome + contagem)."""
    ctx = dim_world("dead" if layer == "surface" else "mist", 200)
    x, y, w, h = 8, 17, 464, 236
    b_window(ctx, x, y, w, h, "")
    map_header(ctx, x, y, w, layer, close_hover)
    ctx.fill(x + 8, y + 22, w - 16, 1, B["line"])
    size = MAPD[layer]["size"][0]
    k = 2 if size >= 192 else 3                          # px nativos por tile (a caverna é menor: 3)
    ms = size * k // 2                                   # px da UI
    mx, my = x + 10, y + 28
    ctx.round_rect(mx - 2, my - 2, ms + 4, ms + 4, "#0d0f16", border=B["line"])
    img = map_texture(layer, k)
    pos = map_markers(img, layer, k, hover=hover)
    ctx.native(img, mx * K, my * K)
    # norte e escala
    ctx.text("N", mx + ms - 6, my + 1, B["muted"], shadow=False)
    ctx.fill(mx + ms - 5, my + 2, 1, 2, B["muted"]) if False else None
    sl = 16 * k // 2
    ctx.fill(mx + 4, my + ms - 5, sl, 1, B["muted"])
    ctx.fill(mx + 4, my + ms - 7, 1, 3, B["muted"])
    ctx.fill(mx + 4 + sl - 1, my + ms - 7, 1, 3, B["muted"])
    ctx.text("16 tiles", mx + 8 + sl, my + ms - 11, B["muted"], P, shadow=False)
    # coluna da legenda
    lx, lw = mx + ms + 10, x + w - (mx + ms + 10) - 8
    ctx.round_rect(lx, my - 2, lw, ms + 4, B["card"])
    ctx.text("LEGENDA", lx + 6, my - 1, B["muted"], shadow=False)
    rows = legend_rows(layer)
    for i, (kind, special, name, count) in enumerate(rows):
        ry = my + 12 + i * 17
        hov = hover == "legend" and kind == "wreck"
        if hov:
            ctx.round_rect(lx + 3, ry - 1, lw - 6, 16, B["hover"])
        im = legend_icon(kind, special)
        ctx.native(im, (lx + 17) * K - im.width // 2, (ry + 7) * K - im.height // 2)
        ctx.text(name, lx + 34, ry, B["text"], P, shadow=False)
        ctx.text(count, lx + lw - 7, ry, B["muted"], P, align="right", shadow=False)
    hy = my + ms - 30
    ctx.fill(lx + 6, hy, lw - 12, 1, B["line"])
    tip = "Mouse num marcador: detalhes" if layer == "surface" else "Só aparece o que a luz revelou"
    ctx.text(tip, lx + 6, hy + 2, B["dim"], P, shadow=False)
    xx = lx + 6
    for key, lab in [("Q/E", "camada"), ("M", "fecha")]:
        xx += b_key(ctx, xx, hy + 17, key) + 3
        xx += ctx.text(lab, xx, hy + 15, B["muted"], P, shadow=False) + 8
    if hover and hover in pos:
        hx, hy2 = pos[hover]
        tx, ty = mx + hx // K - 20, my + hy2 // K + 12
        map_tooltip(ctx, tx, ty, layer, hover, right=mx + ms - 2)
        cursor(ctx, mx + hx // K + 2, my + hy2 // K + 2)
    if close_hover:
        cursor(ctx, x + w - 30, y + 12)
    return ctx


def map_pan(layer, hover=None):
    """Variação: panorâmico. Mapa ocupa a largura toda com zoom 2× (2 px da UI por tile), centrado no
    player; legenda vira uma fileira de filtros clicáveis embaixo (um deles desligado)."""
    ctx = dim_world("dead" if layer == "surface" else "mist", 200)
    x, y, w, h = 8, 6, 464, 258
    b_window(ctx, x, y, w, h, "")
    map_header(ctx, x, y, w, layer)
    ctx.fill(x + 8, y + 22, w - 16, 1, B["line"])
    vw, vh = w - 20, 196                               # px da UI
    k = 4                                              # px nativos por tile
    tw, th = vw * K // k, vh * K // k                  # tiles visíveis
    size = MAPD[layer]["size"]
    px, py, _ = MAPD[layer]["player"]
    ox = max(0, min(size[0] - tw, round(px - tw / 2))) if size[0] > tw else -((tw - size[0]) // 2)
    oy = max(0, min(size[1] - th, round(py - th / 2))) if size[1] > th else -((th - size[1]) // 2)
    pad = Image.new("RGBA", (max(size[0], ox + tw) - min(0, ox), max(size[1], oy + th) - min(0, oy)), (0, 0, 0, 255))
    pad.paste(MAPTEX[layer], (-min(0, ox), -min(0, oy)))
    MAPTEX["_pad"] = pad
    win = (ox - min(0, ox), oy - min(0, oy), ox - min(0, ox) + tw, oy - min(0, oy) + th)
    img = map_texture("_pad", k, window=win)
    filt = {"machine"} if layer == "surface" else set()
    d0 = MAPD[layer]
    MAPD["_v"] = dict(d0, machines=[m for m in d0["machines"] if "machine" not in filt or m[0] == "chest"])
    pos = map_markers(img, "_v", k, origin=(ox, oy), hover=hover)
    mx, my = x + 10, y + 28
    ctx.round_rect(mx - 2, my - 2, vw + 4, vh + 4, "#0d0f16", border=B["line"])
    ctx.native(img, mx * K, my * K)
    # zoom e centralizar (canto do mapa)
    for i, lab in enumerate(["+", "-"]):
        bx = mx + vw - 18
        by = my + 4 + i * 16
        ctx.round_rect(bx, by, 14, 14, (15, 17, 25, 230), border=B["line2"])
        ctx.text(lab, bx + 7, by - 1, B["text"], P, align="center", shadow=False)
    ctx.round_rect(mx + vw - 18, my + 38, 14, 14, (15, 17, 25, 230), border=B["line2"])
    put = marker("you", direction="up")
    ctx.native(put, (mx + vw - 11) * K - put.width // 2, (my + 45) * K - put.height // 2)
    ctx.round_rect(mx + 4, my + 4, F.width("ZOOM 2×") + 8, 11, (15, 17, 25, 230), border=B["line"])
    ctx.text("ZOOM 2×", mx + 8, my + 1, B["muted"], shadow=False)
    # fileira de filtros
    fy = my + vh + 6
    xx = mx
    for kind, special, name, count in legend_rows(layer)[1:]:      # "você" sempre aparece: não é filtro
        on = kind not in filt
        im = legend_icon(kind, special)
        lab = name if kind != "wreck_empty" else "Vazio"
        cw = im.width // K + 8 + P.width(lab) + 4
        ctx.round_rect(xx, fy, cw, 16, B["hover"] if on else "#0d0f16", border=B["line2"] if on else B["line"])
        if not on:
            im = im.copy()
            im.alpha_composite(Image.new("RGBA", im.size, (13, 15, 22, 170)))
        ctx.native(im, (xx + 4) * K, (fy + 8) * K - im.height // 2)
        ctx.text(lab, xx + 6 + im.width // K + 2, fy, B["text"] if on else B["dim"], P, shadow=False)
        xx += cw + 3
    if hover and hover in pos:
        hx, hy = pos[hover]
        map_tooltip(ctx, mx + hx // K + 8, my + hy // K - 30, "_v" if False else layer, hover)
        cursor(ctx, mx + hx // K + 2, my + hy // K + 2)
    return ctx


def map_legend_strip():
    """Em cima: as 3 opções do marcador da base no mapa (2×) e no minimapa (1×), sobre o chão de verdade.
    Embaixo: todos os marcadores do mapa, 4×."""
    W, H = 960, 384
    img = Image.new("RGBA", (W, H), rgba("#0f1119"))
    ctx = Ctx(img, size=(W, H))
    ground = MAPTEX["surface"].crop((88, 88, 100, 100))
    ctx.text("BASE · 3 OPÇÕES  (MAPA 2× · MINIMAPA 1× · AMPLIADO 4×)", 8, 0, B["muted"], shadow=False)
    names = {"base_a": "A · módulo de frente", "base_b": "B · módulo nas pernas", "base_c": "C · cápsula clássica"}
    for i, key in enumerate(("base_a", "base_b", "base_c")):
        x0 = 8 + i * 156
        chosen = key == BASE_CHOSEN
        ctx.round_rect(x0, 12, 148, 116, B["hover"] if chosen else B["card"], border=C_ACCENT if chosen else B["line"])
        pic = marker(key)
        g = ground.resize((40 * K // 2 * 2 // 2 * 2, 40 * K), Image.NEAREST)
        gx, gy = x0 + 6, 18
        ctx.native(ground.resize((60 * K // 2 * 2, 60 * K // 2 * 2), Image.NEAREST), gx * K, gy * K) if False else None
        # chão (textura do mapa) e o ícone no tamanho do mapa (2×) e do minimapa (1×)
        patch = ground.resize((96, 96), Image.NEAREST)
        ctx.native(patch, gx * K, gy * K)
        put = m2(pic)
        ctx.native(put, (gx + 24) * K - put.width // 2, (gy + 16) * K - put.height // 2)
        ctx.native(pic, (gx + 24) * K - pic.width // 2, (gy + 38) * K - pic.height // 2)
        big = pic.resize((pic.width * 4, pic.height * 4), Image.NEAREST)
        ctx.native(big, (x0 + 104) * K - big.width // 2, (gy + 26) * K - big.height // 2)
        ctx.text(names[key], x0 + 6, 84, B["text"], P, shadow=False)
        note = {"base_a": "igual ao pod do jogo", "base_b": "mais nave, menos pod", "base_c": "lê como óvni"}[key]
        ctx.text("ESCOLHIDA" if chosen else note, x0 + 6, 98,
                 C_ACCENT if chosen else B["dim"], shadow=False)
        del g
    kinds = [("you", None, "Você"), ("base", None, "Base"), ("crater", None, "Cratera"), ("ramp_up", None, "Rampa"),
             ("wreck", None, "Destroço"), ("wreck_empty", None, "Vazio"), ("vein", "veins", "Veios"),
             ("terminal", None, "Terminal"), ("machine", None, "Máquina"), ("chest", None, "Baú")]
    ctx.text("TODOS OS MARCADORES (4×)", 8, 132, B["muted"], shadow=False)
    for i, (kind, special, name) in enumerate(kinds):
        cx = 26 + i * 47
        im = legend_icon(kind, special)
        big = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
        ctx.native(big, cx * K - big.width // 2, 156 * K - big.height // 2)
        ctx.text(name, cx, 176, B["muted"], P, align="center", shadow=False)
    return ctx


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in [("a_hud", a_hud), ("a_inventario", a_inventario), ("a_fabricador", a_fabricador),
                     ("a_fabricar", a_fabricar_campo), ("a_bau", a_bau), ("a_opcoes", a_opcoes),
                     ("b_hud", b_hud), ("b_inventario", b_inventario), ("b_fabricador", b_fabricador),
                     ("b_fabricar", b_fabricar_campo), ("b_bau", b_bau), ("b_opcoes", b_opcoes),
                     ("c_hud", c_hud), ("c_inventario", c_inventario), ("c_fabricador", c_fabricador),
                     ("c_fabricar", c_fabricar_campo), ("c_bau", c_bau), ("c_opcoes", c_opcoes)]:
        fn().img.convert("RGB").save(OUT / f"{name}.png")
    for name, fn in [("a_componentes", a_components), ("b_componentes", b_components), ("c_componentes", c_components)]:
        fn().img.convert("RGB").save(OUT / f"{name}.png")
    for name, fn in [("b2_hud", b2_hud), ("b2_inventario", b2_inventario), ("b2_fabricador", b_fabricador),
                     ("b2_fabricar", b_fabricar_campo), ("b2_bau", b2_bau), ("b2_opcoes", b_opcoes),
                     ("b2_componentes", b2_components)]:
        fn().img.convert("RGB").save(OUT / f"{name}.png")
    b2_crops()
    for name, fn in [("map_superficie", lambda: map_main("surface", hover="wreck0")),
                     ("map_caverna", lambda: map_main("cave", hover="terminal0", close_hover=True)),
                     ("map_var_superficie", lambda: map_pan("surface", hover="wreck0")),
                     ("map_var_caverna", lambda: map_pan("cave")),
                     ("map_marcadores", map_legend_strip)]:
        fn().img.convert("RGB").save(OUT / f"{name}.png")
    export_pending()
    copy_before()


if __name__ == "__main__":
    main()
