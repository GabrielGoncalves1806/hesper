#!/usr/bin/env python3
"""v0.8 · Plantas (rodada 1) · prévias, cenas, mock da UI do cultivador e o index.html do report.

    python3 tools/sprites/v08_plantas.py          # 1º: os sprites (pendentes/)
    python3 tools/sprites/v08_plantas_report.py   # 2º: cenas + html

Só LÊ assets/sprites/ e escreve em reports/design/v08_plantas/. Determinístico.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v08_plants_art as PA  # noqa: E402
from v07_lib import hsh  # noqa: E402
from v07_lore_report import wall_piece  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REG = SPR / "regions"
REP = ROOT / "reports" / "design" / "v08_plantas"
PEND = REP / "pendentes"
T = 32
LIFT = 24
PALJ = json.loads((REG / "regions_palettes.json").read_text())
FONT_DIR = ROOT / "game" / "fonts"


def A(name):
    return Image.open(SPR / name).convert("RGBA")


def P(name):
    return Image.open(PEND / name).convert("RGBA")


def frame(strip, i, w=40):
    return strip.crop((i * w, 0, i * w + w, strip.height))


def region_img(name, ramp):
    """PNG indexado das regiões com a rampa do estágio (0..7 rampa, 8 contorno, 9 sombra)."""
    im = Image.open(REG / name)
    idx = np.array(im)
    lut = np.zeros((256, 4), np.uint8)
    for i, c in enumerate(ramp):
        c = c.lstrip("#")
        lut[i] = (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    lut[8] = (27, 22, 48, 255)
    lut[9] = (0, 0, 0, 80)
    return Image.fromarray(lut[idx])


def ground(region, stage, w, h, ox=0, oy=0):
    g = region_img(f"ground_{region}.png", PALJ["ramps"]["BASE"][region][stage])
    out = Image.new("RGBA", (w, h))
    for y in range(0, h, 512):
        for x in range(0, w, 512):
            out.alpha_composite(g, (x - ox % 512, y - oy % 512))
            out.alpha_composite(g, (x - ox % 512 + 512, y - oy % 512))
    return out


def cultivator_img(culture=None, stage=0, state="lit", f=0):
    """Corpo do cultivador (parado / aceso quadro f / seco) + miolo da cultura, do jeito que o jogo compõe."""
    if state == "lit":
        body = frame(P("anim/anim_machine_cultivator.png"), f)
    elif state == "dry":
        body = P("machine_cultivator_dry.png")
    else:
        body = P("machine_cultivator.png")
    if culture:
        body = body.copy()
        body.alpha_composite(P(f"cultivator_crop_{culture}_{stage}.png"))
    return body


# =====================================================================================================================
# Cena montada (chão, parede da base, porta, objetos ordenados pelo pé)
# =====================================================================================================================
class SceneBuilder:
    def __init__(self, tw, th, bg):
        self.tw, self.th = tw, th
        self.img = Image.new("RGBA", (tw * T, th * T), (20, 18, 24, 255))
        self.img.alpha_composite(bg, (0, 0))
        self.walls = set()
        self.floors = set()
        self.objs = []          # (pé_y, ordem, função)

    def floor(self, tx, ty):
        self.floors.add((tx, ty))

    def wall(self, tx, ty):
        self.walls.add((tx, ty))

    def obj(self, spr, tx, ty, dx=0, dy=0):
        """Âncora no centro da base do tile (padrão das máquinas e props)."""
        x = tx * T + T // 2 - spr.width // 2 + dx
        y = (ty + 1) * T - spr.height + dy
        self.objs.append(((ty + 1) * T + dy, len(self.objs), lambda spr=spr, x=x, y=y: self.img.alpha_composite(spr, (x, y))))

    def at(self, spr, x, y, foot):
        self.objs.append((foot, len(self.objs), lambda: self.img.alpha_composite(spr, (x, y))))

    def render(self):
        for (tx, ty) in sorted(self.floors):
            self.img.alpha_composite(A(f"base_floor_{int(hsh(tx, ty, 2) * 4)}.png"), (tx * T, ty * T))
        isw = lambda x, y: (x, y) in self.walls
        face = A("base_wall_face.png")
        for (tx, ty) in self.walls:
            def draw(tx=tx, ty=ty):
                self.img.alpha_composite(wall_piece(isw, tx, ty), (tx * T, ty * T - LIFT))
                if not isw(tx, ty + 1):
                    idx = int(isw(tx - 1, ty)) + 2 * int(isw(tx + 1, ty))
                    self.img.alpha_composite(face.crop((idx * T, 0, idx * T + T, 24)), (tx * T, ty * T + 8))
            self.objs.append((ty * T + 1, -1, draw))
        for _, _, fn in sorted(self.objs, key=lambda o: (o[0], o[1])):
            fn()
        return self.img


def door2(sb, tx, ty, fr=0, ice=None):
    """Porta dupla horizontal (h_s: chão da base ao norte) em (tx, ty) e (tx+1, ty), mais o gelo por cima."""
    strip = A("base_door2_h_s.png")
    left, right = strip.crop((fr * 32, 0, fr * 32 + 32, 56)), strip.crop(((4 + fr) * 32, 0, (4 + fr) * 32 + 32, 56))
    x, y = tx * T, ty * T - LIFT
    def draw():
        sb.img.alpha_composite(left, (x, y))
        sb.img.alpha_composite(right, (x + 32, y))
        if ice:
            sb.img.alpha_composite(P(f"{ice}.png"), (x, y))
    sb.objs.append(((ty + 1) * T, 0, draw))


# ---- 1 · cena da base no Úmido --------------------------------------------------------------------------------------
def scene_base(stage="mist"):
    sb = SceneBuilder(30, 17, ground("plateau", stage, 960, 544, 37, 91))
    x0, y0, x1, y1 = 2, 2, 19, 13
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            edge = tx in (x0, x1) or ty in (y0, y1)
            if edge and not (ty == y1 and tx in (10, 11)):
                sb.wall(tx, ty)
            elif not edge:
                sb.floor(tx, ty)
    door2(sb, 10, y1, 0)
    for t in ((10, y1), (11, y1)):
        sb.floor(*t)
    # fileira de cultivadores (as 4 culturas maduras + etapas), aceso em quadros diferentes
    row = [("algae", 3), ("plant_1", 3), ("plant_2", 3), ("plant_3", 3), ("plant_3", 1)]
    for i, (c, s) in enumerate(row):
        sb.obj(cultivator_img(c, s, "lit", i % 4), 4 + i * 2, 4)
    row2 = [("algae", 0, "lit"), ("algae", 1, "lit"), ("plant_1", 2, "lit"), (None, 0, "idle"), ("plant_2", 1, "dry")]
    for i, (c, s, st) in enumerate(row2):
        sb.obj(cultivator_img(c, s, st, (i + 1) % 4), 4 + i * 2, 7)
    sb.obj(frame(P("anim/anim_machine_microscope.png"), 1), 15, 4)
    sb.obj(frame(P("anim/anim_machine_centrifuge.png"), 0), 17, 4)
    sb.obj(A("machine_o2_dispenser.png"), 17, 7)
    sb.obj(A("machine_melter.png"), 15, 7)
    sb.obj(A("chest.png"), 15, 11)
    sb.obj(A("player_down.png"), 9, 10)
    # lá fora: coletores, O2, painel
    sb.obj(frame(P("anim/anim_machine_water_collector.png"), 2), 23, 5)
    sb.obj(frame(P("anim/anim_machine_water_collector.png"), 0), 25, 5)
    sb.obj(P("machine_water_collector.png"), 27, 5)
    sb.obj(A("machine_o2.png"), 23, 10)
    sb.obj(A("machine_heater.png"), 25, 10)
    sb.obj(A("solar_panel.png"), 27, 10)
    sb.obj(A("machine_melter.png"), 23, 14)
    return sb.render().crop((0, 0, 960, 540))


# ---- 2 · sequência do gelo na porta do lab --------------------------------------------------------------------------
def lab_door_panel(stage):
    """Pedaço da fachada sul do lab (6×5 tiles) na faixa gelada, Úmido. stage 0..3 (3 = aberto)."""
    bg = ground("frost", "mist", 192, 192, 140, 77)
    sb = SceneBuilder(6, 6, bg)
    for tx in range(6):
        sb.wall(tx, 0) if False else None
    for tx in range(6):
        for ty in (0, 1):
            sb.floor(tx, ty)
    for tx in range(6):
        if tx not in (2, 3):
            sb.wall(tx, 2)
    for tx in (0, 5):
        for ty in (0, 1):
            sb.wall(tx, ty)
    ice = {0: "lab_ice_door2_h_0", 1: "lab_ice_door2_h_1", 2: "lab_ice_door2_h_2", 3: "lab_ice_puddle_h"}[stage]
    door2(sb, 2, 2, 0 if stage < 3 else 3, ice)
    if stage == 3:
        sb.obj(A("player_up.png"), 3, 3, dx=-16)
    else:
        sb.obj(A("player_up.png"), 3, 4, dx=-16)
    img = sb.render()
    return img.crop((0, 8, 192, 192))


def lab_door_blocks_panel(k):
    """Opção A: os blocos dos gelos-portão (ice_block_*) amontoados na frente da porta, no quadro k (0..7)."""
    bg = ground("frost", "mist", 192, 192, 140, 77)
    sb = SceneBuilder(6, 6, bg)
    for tx in range(6):
        for ty in (0, 1):
            sb.floor(tx, ty)
    for tx in range(6):
        if tx not in (2, 3):
            sb.wall(tx, 2)
    for tx in (0, 5):
        for ty in (0, 1):
            sb.wall(tx, ty)
    door2(sb, 2, 2, 0 if k < 7 else 3)
    ramp = PALJ["ramps"]["ICE"]["frost"]["mist"]
    for (b, x, y, fk) in (("slab_1", 96 - 6, 112, k), ("boulder_0", 70, 120, min(7, k + 1)), ("shard_0", 128, 118, min(7, k + 2))):
        if fk >= 7:
            continue
        info = PALJ["blocks"][b]
        fw, fh = info["frame"]
        strip = region_img(info["sprite"], ramp)
        spr = strip.crop((fk * fw, 0, fk * fw + fw, fh))
        ax, ay = info["anchor"]
        sb.at(spr, x - ax, y - ay, y)
    sb.obj(A("player_up.png"), 3, 4, dx=-16)
    return sb.render().crop((0, 8, 192, 192))


# ---- 3 · o lab da Ilves por dentro (lab.txt), com as máquinas quebradas no lugar dos props -------------------------
def scene_lab():
    plan = (ROOT / "game" / "ruin_plans" / "lab.txt").read_text().split("---")[1].strip().splitlines()
    tw, th = 30, 17
    ox, oy = 8, 4
    sb = SceneBuilder(tw, th, ground("frost", "mist", 960, 544, 300, 120))
    props = {"w": "prop_lab_bench", "s": "prop_microscope", "e": "prop_sample_shelf", "z": "prop_ice_stain",
             "u": "prop_console", "i": "prop_chair_fallen"}
    for y, row in enumerate(plan):
        for x, ch in enumerate(row):
            tx, ty = ox + x, oy + y
            if ch == "#" or ch.isdigit() or ch == "y" or ch == "f":
                sb.wall(tx, ty)
                continue
            if ch == "~":
                continue                         # chão destruído: o gelo de fora aparece
            sb.floor(tx, ty)
            if ch == "D":                        # porta solo fechada: horizontal se tem parede dos lados
                horiz = x > 0 and plan[y][x - 1] == "#"
                strip = A("base_door_h_s.png" if horiz else "base_door_v_e.png")
                spr = strip.crop((0, 0, 32, 56))
                sb.at(spr, tx * T, ty * T - LIFT, (ty + 1) * T)
            if ch in props:
                if ch == "z":
                    sb.at(A("prop_ice_stain.png"), tx * T, ty * T - 8, ty * T)
                else:
                    sb.obj(A(f"{props[ch]}.png"), tx, ty, dy=0)
            elif ch == "d":
                sb.obj(P("machine_microscope_broken.png"), tx, ty)
            elif ch == "q":
                sb.obj(P("machine_cultivator_broken.png"), tx, ty)
            elif ch == "c":
                sb.obj(A("loot_crate.png"), tx, ty)
            elif ch in "mho":
                kind = {"m": "machine_melter", "h": "machine_heater", "o": "machine_o2"}[ch]
                im = A(f"{kind}.png")
                arr = np.array(im).astype(np.int32)
                arr[:, :, :3] = arr[:, :, :3] * np.array([120, 112, 108]) // 255
                sb.obj(Image.fromarray(arr.astype(np.uint8)), tx, ty)
            elif ch == "l":
                sb.obj(A("lamp.png"), tx, ty)
    # porta dupla com o gelo (linha de baixo, "==")
    dy = len(plan) - 1
    dx = plan[-1].index("==")
    for k in (0, 1):
        sb.floor(ox + dx + k, oy + dy)
    door2(sb, ox + dx, oy + dy, 0, "lab_ice_door2_h_0")
    sb.obj(A("player_up.png"), ox + dx + 1, oy + dy + 2, dx=-16)
    return sb.render().crop((0, 0, 960, 540))


# =====================================================================================================================
# Mock da UI do cultivador (desenhado em px lógicos 480×270 e ampliado ×2, texto em resolução nativa como no jogo)
# =====================================================================================================================
B_WINDOW = (15, 17, 25, 246)
B_CARD, B_CARD2, B_LINE, B_LINE2 = "#141722", "#1b1f2c", "#2b3145", "#3a4259"
B_TEXT, B_MUTED, B_DIM = "#eef0f6", "#8b93a8", "#4f566b"
B_WELL, B_TRACK = "#0d0f16", "#262b3b"
B_SLOT_OUT, B_SLOT_IN, B_SLOT_LIGHT = "#0c0e15", "#181c28", "#22273a"
ACCENT, CYAN_UI, GOLD_UI, OK_UI = "#e2733a", "#59d0e6", "#f2c46d", "#7fd67a"
SLOT, STEP = 20, 22


def _font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)


class UIMock:
    def __init__(self, bg):
        self.lo = Image.new("RGBA", (480, 270), (0, 0, 0, 0))           # camada lógica
        self.d = ImageDraw.Draw(self.lo)
        self.bg = bg
        self.texts = []                                                  # (x, y, txt, cor, fonte, align) em px lógicos
        self.icons = []                                                  # (img 16×16, x, y) nativo ×2
        self.label = _font("Silkscreen-Regular.ttf", 16)
        self.body = _font("PixelifySans.ttf", 22)

    def rr(self, x, y, w, h, fill, border=None):
        d = self.d
        d.rectangle((x + 1, y, x + w - 2, y + h - 1), fill=fill)
        d.rectangle((x, y + 1, x + w - 1, y + h - 2), fill=fill)
        if border:
            d.line((x + 1, y, x + w - 2, y), fill=border)
            d.line((x + 1, y + h - 1, x + w - 2, y + h - 1), fill=border)
            d.line((x, y + 1, x, y + h - 2), fill=border)
            d.line((x + w - 1, y + 1, x + w - 1, y + h - 2), fill=border)

    def window(self, x, y, w, h):
        self.d.rectangle((x + 1, y + h, x + w - 2, y + h), fill=(0, 0, 0, 110))
        self.rr(x, y, w, h, B_WINDOW, B_LINE)

    def slot(self, x, y, icon=None, count=None, hl=None):
        self.rr(x, y, SLOT, SLOT, B_SLOT_OUT)
        self.d.rectangle((x + 1, y + 1, x + SLOT - 2, y + SLOT - 2), fill=B_SLOT_IN)
        self.d.rectangle((x + 2, y + 1, x + SLOT - 3, y + 1), fill=B_SLOT_LIGHT)
        if hl:
            self.rr(x - 1, y - 1, SLOT + 2, SLOT + 2, None, hl)
        if icon is not None:
            self.icons.append((icon, x * 2 + 4, y * 2 + 4))
        if count and count > 1:
            self.text(x + SLOT - 1, y + SLOT - 9, str(count), B_TEXT, "body", "right")

    def text(self, x, y, txt, col, font="label", align="left"):
        self.texts.append((x, y, txt, col, font, align))

    def bar_v(self, x, y, w, h, frac, cols):
        self.rr(x, y, w, h, B_WELL, B_LINE2)
        fh = round((h - 2) * frac)
        for k in range(fh):
            t = k / max(1, h - 3)
            c = cols[min(len(cols) - 1, int(t * len(cols)))]
            self.d.line((x + 1, y + h - 2 - k, x + w - 2, y + h - 2 - k), fill=c)
        if fh:
            self.d.line((x + 1, y + h - 1 - fh, x + w - 2, y + h - 1 - fh), fill="#ffffff")

    def finish(self, path):
        dim = Image.new("RGBA", self.bg.size, (8, 5, 4, 130))
        out = self.bg.copy()
        out.alpha_composite(dim)
        out.alpha_composite(self.lo.resize((960, 540), Image.NEAREST))
        d = ImageDraw.Draw(out)
        d.fontmode = "1"
        for (img, x, y) in self.icons:
            if img.width <= 16:
                img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
            out.alpha_composite(img, (x, y))
        for (x, y, txt, col, font, align) in self.texts:
            f = self.label if font == "label" else self.body
            w = d.textlength(txt, font=f)
            X = x * 2 - (w if align == "right" else w / 2 if align == "center" else 0)
            d.text((X, y * 2 - (2 if font == "label" else 6)), txt, font=f, fill=col)
        out.convert("RGB").save(path)


def tank_cylinder(culture, stage, scale=3):
    """O cilindro grande do meio da UI: tampa e base creme com faixa laranja, vidro com o líquido, terra e a planta
    (o mesmo PNG da planta do tanque, ampliado inteiro). Desenhado em px lógicos."""
    pl = PA.plant(culture, stage) if culture else None
    W, H = 52, 82
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    INK = "#1b1630"
    # tampa
    d.rounded_rectangle((3, 0, W - 4, 9), 3, fill=INK)
    d.rectangle((4, 1, W - 5, 4), fill="#fdf8ec")
    d.rectangle((4, 5, W - 5, 6), fill="#e2733a")
    d.rectangle((4, 7, W - 5, 8), fill="#d6c9b4")
    d.rectangle((W // 2 - 5, 2, W // 2 + 4, 3), fill="#7fd67a")
    # vidro
    gx0, gx1, gy0, gy1 = 5, W - 6, 10, H - 13
    d.rectangle((gx0 - 1, gy0, gx1 + 1, gy1), fill=INK)
    liq = ["#d2f7e6", "#a8e6cf", "#86ceba", "#66b0a6"]
    for x in range(gx0, gx1 + 1):
        u = (x - gx0) / (gx1 - gx0)
        c = liq[0] if u < 0.1 else liq[1] if u < 0.55 else liq[2] if u < 0.85 else liq[3]
        d.line((x, gy0 + 4, x, gy1), fill=c)
    d.rectangle((gx0, gy0, gx1, gy0 + 3), fill="#3a5266")                       # ar acima do líquido
    # terra
    d.rectangle((gx0, gy1 - 7, gx1, gy1), fill="#4a3427")
    d.rectangle((gx0, gy1 - 9, gx1, gy1 - 8), fill="#8f6c50")
    for x in range(gx0 + 2, gx1, 5):
        d.point((x, gy1 - 4), fill="#5a4030")
    # planta
    if pl is not None:
        p = Image.fromarray(pl).resize((pl.shape[1] * 2, pl.shape[0] * 2), Image.NEAREST)
        im.alpha_composite(p, ((W - p.width) // 2, gy1 - 9 - p.height + 2))
    # anéis e reflexo
    for ry in (gy0 + 18, gy0 + 38):
        d.line((gx0, ry, gx1, ry), fill="#7fd67a")
    d.line((gx0 + 3, gy0 + 6, gx0 + 3, gy1 - 11), fill="#f4fffa")
    d.line((gx0 + 5, gy0 + 6, gx0 + 5, gy0 + 14), fill="#f4fffa")
    # base
    d.rounded_rectangle((1, H - 13, W - 2, H - 1), 2, fill=INK)
    d.rectangle((2, H - 12, W - 3, H - 9), fill="#fdf8ec")
    d.rectangle((2, H - 8, W - 3, H - 7), fill="#e2733a")
    d.rectangle((2, H - 6, W - 3, H - 2), fill="#d6c9b4")
    d.point((W // 2 - 3, H - 4), fill="#7fd67a")
    d.point((W // 2 + 1, H - 4), fill="#59d0e6")
    return im


def icon(name):
    p = PEND / f"{name}.png"
    return Image.open(p if p.exists() else SPR / f"{name}.png").convert("RGBA")


def inv_contents():
    hot = [("hand_drill", 1), ("algae", 3), ("water_capsule", 6), ("water_capsule_empty", 2), ("ice", 40),
           ("iron", 22), ("sample_basic", 1), ("plant_1", 2)]
    bag = [("silicon", 18), ("copper", 9), (None, 0), ("plant_3", 1), (None, 0), (None, 0), (None, 0), (None, 0)]
    return bag, hot


def machine_panel(m, x, y, w=216, h=206, culture="algae", stage=2, compact=False):
    """Painel do cultivador (lado direito no padrão atual)."""
    m.window(x, y, w, h)
    m.text(x + 8, y + 6, "Cultivador", ACCENT, "body")
    m.text(x + w - 8, y + 8, "ALGA · ETAPA 3/4", B_MUTED, "label", "right")
    # esquerda: tanque de água (marcas das 5 cápsulas) + barra de crescimento; embaixo reserva e vazias
    tx, ty = x + 8, y + 24
    m.text(tx, ty, "ÁGUA", CYAN_UI)
    m.bar_v(tx, ty + 10, 20, 62, 0.62, ["#1f5a85", "#2f7fb3", "#4aa8d8"])
    for k in range(1, 5):
        yy = ty + 10 + round(62 * k / 5)
        m.d.line((tx + 1, yy, tx + 4, yy), fill="#9fe0f5")
    m.text(tx + 10, ty + 75, "3/5", B_TEXT, "label", "center")
    m.text(tx + 30, ty, "CRESCE", OK_UI)
    m.bar_v(tx + 36, ty + 10, 9, 62, 0.55, ["#e2733a", "#f2c46d", "#c4ec7a", "#7fd67a"])
    m.text(tx + 40, ty + 75, "55%", B_TEXT, "label", "center")
    m.text(tx - 1, ty + 90, "CHEIAS", B_MUTED)
    m.slot(tx - 1, ty + 100, icon("icon_water_capsule"), 4)
    m.text(tx + 38, ty + 90, "VAZIAS", B_MUTED)
    m.slot(tx + 38, ty + 100, icon("icon_water_capsule_empty"), 2)
    # meio: cilindro
    cyl = tank_cylinder(culture, stage)
    cx = x + 90
    m.lo.alpha_composite(cyl, (cx, y + 22))
    m.text(cx + cyl.width // 2, y + 22 + cyl.height + 4, "0,5 BIO/S", OK_UI, "label", "center")
    # direita: colheita 2×2
    hx = x + w - 8 - (2 * STEP - 2)
    m.text(hx, y + 24, "COLHEITA", GOLD_UI)
    items = [("icon_algae", 2), (None, 0), (None, 0), (None, 0)]
    for k, (it, n) in enumerate(items):
        m.slot(hx + (k % 2) * STEP, y + 34 + (k // 2) * STEP, icon(it) if it else None, n)
    m.text(hx, y + 84, "1-2 POR", B_MUTED)
    m.text(hx, y + 93, "COLHEITA", B_MUTED)
    if compact:                                   # B: sem descrição e sem a faixa dos drones (não cabe em 270)
        return
    # rodapé: descrição + drones
    m.text(x + 8, y + 146, "Cresce com água dentro da base.", B_MUTED, "body")
    m.d.line((x + 8, y + 162, x + w - 9, y + 162), fill=B_LINE)
    m.text(x + 8, y + 167, "DRONES", CYAN_UI)
    m.text(x + 48, y + 165, "· envia 2 · recebe 1", GOLD_UI, "body")
    m.text(x + 8, y + 184, "Envia", B_MUTED, "body")
    m.slot(x + 42, y + 180, icon("icon_algae"), hl=ACCENT)
    m.slot(x + 64, y + 180, icon("icon_water_capsule_empty"), hl=ACCENT)
    m.text(x + 104, y + 184, "Recebe", B_MUTED, "body")
    m.slot(x + 152, y + 180, icon("icon_water_capsule"), hl=CYAN_UI)


def inv_panel(m, x, y, title=True):
    w = 8 * STEP - 2 + 16
    bag, hot = inv_contents()
    m.window(x, y, w, 84)
    m.text(x + 8, y + 6, "Inventário", B_TEXT, "body")
    m.text(x + w - 8, y + 8, "11/16", B_MUTED, "label", "right")
    m.text(x + 8, y + 20, "INVENTÁRIO", B_MUTED)
    for i, (it, n) in enumerate(bag):
        m.slot(x + 8 + i * STEP, y + 29, icon(f"icon_{it}") if it else None, n)
    m.text(x + 8, y + 52, "HOTBAR", B_MUTED)
    for i, (it, n) in enumerate(hot):
        m.slot(x + 8 + i * STEP, y + 61, icon(f"icon_{it}") if it else None, n, hl=ACCENT if i == 0 else None)


def help_line(m, y):
    """Linha de ajuda embaixo das janelas."""
    for (x, key, txt) in ((28, "CLIQUE", "pega/solta"), (140, "DIR", "metade/1"), (232, "SHIFT+CLIQUE", "manda direto"),
                          (392, "ESC", "fecha")):
        kw = len(key) * 5 + 6
        m.rr(x, y, kw, 11, B_CARD2, B_LINE2)
        m.text(x + 3, y + 2, key, B_TEXT)
        m.text(x + kw + 4, y, txt, B_MUTED, "body")


def ui_mock_A(bg, path):
    m = UIMock(bg)
    inv_panel(m, 21, 20)
    m.rr(214, 42, 40, 38, B_WINDOW, B_LINE)
    m.text(234, 49, "<<", B_TEXT, "label", "center")
    m.text(234, 58, "PEGAR", B_TEXT, "label", "center")
    m.text(234, 67, "TUDO", B_TEXT, "label", "center")
    machine_panel(m, 258, 20)
    help_line(m, 234)
    m.finish(path)


def ui_mock_B(bg, path):
    """Igual ao rascunho do dono: a máquina em cima, larga, e o inventário embaixo, numa coluna só."""
    m = UIMock(bg)
    machine_panel(m, 132, 6, h=150, compact=True)
    inv_panel(m, 145, 162)
    help_line(m, 252)
    m.finish(path)


# =====================================================================================================================
# HTML
# =====================================================================================================================
def zoom(img, k):
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def save_previews():
    REP.mkdir(parents=True, exist_ok=True)
    base = scene_base("mist")
    base.convert("RGB").save(REP / "preview_base_mist.png")
    scene_base("green").convert("RGB").save(REP / "preview_base_green.png")
    scene_lab().convert("RGB").save(REP / "preview_lab_mist.png")
    seq = Image.new("RGBA", (4 * 192 + 3 * 8, 184), (21, 16, 14, 255))
    for i in range(4):
        seq.alpha_composite(lab_door_panel(i), (i * 200, 0))
    zoom(seq, 2).save(REP / "lab_door_B.png")
    seq = Image.new("RGBA", (4 * 192 + 3 * 8, 184), (21, 16, 14, 255))
    for i, k in enumerate((0, 3, 5, 7)):
        seq.alpha_composite(lab_door_blocks_panel(k), (i * 200, 0))
    zoom(seq, 2).save(REP / "lab_door_A.png")
    ui_mock_A(base, REP / "ui_cultivador_A.png")
    ui_mock_B(base, REP / "ui_cultivador_B.png")
    # cultivador: todas as culturas × etapas (composto como no jogo)
    grid = Image.new("RGBA", (4 * 44 + 4, 4 * 60 + 4), (0, 0, 0, 0))
    for r, c in enumerate(("algae", "plant_1", "plant_2", "plant_3")):
        for s in range(4):
            grid.alpha_composite(cultivator_img(c, s, "lit", s), (4 + s * 44, 4 + r * 60))
    grid.save(REP / "cultivador_grade.png")
    # escala: máquinas novas ao lado das aprovadas + o player
    row = [A("machine_melter.png"), A("machine_o2.png"), cultivator_img("plant_1", 3, "lit"), P("machine_microscope.png"),
           P("machine_centrifuge.png"), P("machine_water_collector.png"), A("machine_smelter.png"), A("player_down.png")]
    W = sum(i.width for i in row) + 6 * (len(row) + 1)
    sc = Image.new("RGBA", (W, 62), (0, 0, 0, 0))
    x = 6
    for im in row:
        sc.alpha_composite(im, (x, 60 - im.height))
        x += im.width + 6
    sc.save(REP / "escala.png")
    # cultivador A × B
    ab = Image.new("RGBA", (4 * 46, 60), (0, 0, 0, 0))
    a_body = P("_compare/cultivator_A_plant_1_3.png")
    ab.alpha_composite(P("_compare/machine_cultivator_A.png"), (2, 2))
    ab.alpha_composite(a_body, (48, 2))
    ab.alpha_composite(P("machine_cultivator.png"), (94, 2))
    ab.alpha_composite(cultivator_img("plant_1", 3, "idle"), (140, 2))
    ab.save(REP / "cultivador_A_B.png")


CSS = """
:root{--bg:#15100e;--panel:#1e1714;--panel2:#241b17;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding-inline:16px}
.wrap{max-width:1320px;margin:0 auto;padding-block:40px 80px}
.eyebrow{font:12px Silkscreen,ui-monospace,monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
h1{font:600 clamp(30px,5vw,50px)/1.05 "Pixelify Sans",ui-monospace,monospace;margin:10px 0 14px}
h2{font:600 24px/1.2 "Pixelify Sans",ui-monospace,monospace;margin:48px 0 12px}
h2::before{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}
h3{font:600 17px "Pixelify Sans",monospace;margin:22px 0 8px;color:var(--gold)}
p,li{color:var(--muted);max-width:92ch}p b,li b{color:var(--fg)}
code{font-family:"IBM Plex Mono",monospace;font-size:.9em;color:var(--gold)}
.note{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--gold);padding:12px 18px;max-width:980px}
.rec{border-left-color:var(--ok)}.q{border-left-color:var(--cyan)}
.chk{background-color:#2a211d;background-image:conic-gradient(#3a2e28 25%,transparent 0 50%,#3a2e28 0 75%,transparent 0);background-size:16px 16px;padding:10px;display:inline-block}
img.px,.px img{image-rendering:pixelated}
.row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
figure{margin:0;background:var(--panel);border:1px solid var(--line);padding:10px}
figcaption{font:12px "IBM Plex Mono",monospace;color:var(--muted);margin-top:6px}
.anim{image-rendering:pixelated;animation:play .8s steps(4) infinite;flex:none}
@keyframes play{from{background-position:0 0}to{background-position:var(--end) 0}}
.full{display:block;max-width:100%;height:auto;border:1px solid var(--line);image-rendering:pixelated}
table{border-collapse:collapse;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{font:11px Silkscreen,monospace;color:var(--muted)}
.cycle{image-rendering:pixelated;flex:none}
"""


def size(p):
    with Image.open(p) as im:
        return im.size


def fig(src, k, cap):
    w, h = size(REP / src)
    return f'<figure><div class="chk"><img class="px" src="{src}" width="{w * k}" height="{h * k}"></div><figcaption>{cap}</figcaption></figure>'


def fig1(src, cap):
    w, h = size(REP / src)
    return (f'<figure><div class="chk" style="display:flex;gap:14px;align-items:flex-end"><img class="px" src="{src}" width="{w}" height="{h}">'
            f'<img class="px" src="{src}" width="{w * 4}" height="{h * 4}"></div><figcaption>{cap}</figcaption></figure>')


def animfig(src, k, cap, fps=5):
    w, h = size(REP / src)
    fw = w // 4
    dur = 4 / fps
    return (f'<figure><div class="chk"><div class="anim" style="width:{fw * k}px;height:{h * k}px;background:url({src}) 0 0/{w * k}px {h * k}px;'
            f'--end:-{w * k}px;animation-duration:{dur:.2f}s"></div></div><figcaption>{cap}</figcaption></figure>')


def crop_cycle_css():
    """Animação CSS do cultivador crescendo: corpo aceso + miolo trocando de etapa."""
    rules = []
    for c in ("algae", "plant_1", "plant_2", "plant_3"):
        steps = " ".join(f"{k * 25}%{{background-image:url(pendentes/cultivator_crop_{c}_{k}.png)}}" for k in range(4))
        rules.append(f"@keyframes grow_{c}{{{steps} 100%{{background-image:url(pendentes/cultivator_crop_{c}_3.png)}}}}")
        rules.append(f".grow_{c}{{animation:grow_{c} 4s steps(1) infinite}}")
    return "\n".join(rules)


def write_html(sizes_ok):
    o = []
    a = o.append
    a('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a('<title>Hesper · v0.8 Plantas · arte rodada 1</title>')
    a('<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@400;600&family=Silkscreen&display=swap" rel="stylesheet">')
    a(f"<style>{CSS}\n{crop_cycle_css()}</style></head><body><div class='wrap'>")
    a('<div class="eyebrow">Hesper · Designer · v0.8 Plantas · rodada 1 (v1.0)</div>')
    a('<h1>Plantas: cultivador, microscópio, centrífuga, coletor, ícones e o gelo do lab</h1>')
    a('<div class="note"><b>v1.0 · o que tem aqui.</b> Todos os itens de arte da v0.8 de uma vez, pra tu aprovar ou mandar mexer. '
      'Tudo gerado por <code>tools/sprites/v08_plantas.py</code> (sprites) e <code>tools/sprites/v08_plantas_report.py</code> (cenas e esta página), '
      'saída em <code>reports/design/v08_plantas/pendentes/</code>. <b>Nada foi pra <code>assets/</code></b>: quem copia depois do teu ok é o gerente. '
      f'{sizes_ok}</div>')
    a('<div class="note rec" style="margin-top:12px"><b>Recomendações rápidas.</b><ul>'
      '<li><b>Cultivador com base cheia (B)</b>, não com pernas (A): em 40×56 as pernas viram dois "colchetes" brancos e o vidro parece flutuar.</li>'
      '<li><b>Gelo colado na porta (B)</b> pro lab: lê na hora como "porta congelada". A opção A (os blocos dos gelos-portão) custa zero arte e fica de reserva.</li>'
      '<li><b>UI no padrão atual (A)</b>, com o inventário à esquerda e a máquina à direita. A B segue o teu rascunho (inventário embaixo), mas foge do resto do jogo.</li>'
      '<li>Nomes que eu escolheria: <b>Folha-gota</b> (planta 1), <b>Espiral-de-geada</b> (planta 2) e <b>Lírio-de-Ilves</b> (planta 3).</li></ul></div>')

    a('<h2>1 · Prévias (960×540, só com os sprites)</h2>')
    a('<p>Base no <b>Úmido</b> (rampa da névoa) e no <b>Verde</b>. Na fileira de cima, as 4 culturas maduras e uma planta 3 na etapa 2. Na de baixo: alga muda, alga pequena, planta 1 média, cultivador vazio parado e planta 2 <b>seca</b> (sem líquido, LED vermelho). '
      'Do lado do cultivador ficam o microscópio analisando e a centrífuga girando, e no fundo o Dispersor, o derretedor e o baú aprovados. Lá fora, 3 coletores de água (2 trabalhando, 1 parado) do lado do O₂, do aquecedor e do painel.</p>')
    a('<img class="full" src="preview_base_mist.png" width="960" height="540">')
    a('<p></p><img class="full" src="preview_base_green.png" width="960" height="540">')
    a('<h3>O lab da Ilves por dentro (a planta <code>lab.txt</code>, faixa gelada, Úmido)</h3>')
    a('<p>O <code>prop_microscope_digital</code> virou o <b>microscópio quebrado</b> e o <code>prop_sample_tank</code> virou o <b>cultivador quebrado</b>. As máquinas quebradas das salas (derretedor, aquecedor, O₂) aparecem com o escurecimento de hoje (<code>RUIN_BROKEN_TINT</code>). '
      'As 2 máquinas novas quebradas <b>já são desenhadas apagadas</b> (sem luz, geada, vidro estourado), então aparecem sem o escurecimento. A porta dupla de baixo está tampada pelo gelo.</p>')
    a('<img class="full" src="preview_lab_mist.png" width="960" height="540">')

    a('<h2>2 · Cultivador</h2>')
    a('<p><b>Como montei:</b> o corpo é um só (sapata B, pedestal creme com faixa laranja, anel de luz verde, cilindro de vidro com o nutriente verde-água, 2 anéis de luz, tampa com a luz de cultivo), e o que muda é o <b>miolo</b>: '
      'um PNG 40×56 transparente só com os pixels da planta, já recortado pelo vidro. O jogo desenha o corpo e o miolo por cima, no mesmo (x, y). '
      'O risco de brilho do vidro fica na frente da planta, e os anéis ficam atrás dela, de propósito: na frente eles "engradavam" a planta.</p>')
    a('<h3>Referências do dono: o que eu aproveitei</h3><ul>'
      '<li><b>Ref A</b> (cilindro sobre pernas): o vidro com líquido verde, o anel no meio do vidro e o tampo creme. As pernas eu testei (variante A abaixo).</li>'
      '<li><b>Ref B</b> (base cheia): o pedestal largo, o <b>anel de luz verde</b> na junção vidro/base, os anéis finos no vidro e o tampo arredondado. O desenho é original, no r3d das nossas máquinas.</li>'
      '<li><b>Rascunho da UI</b>: a terra no fundo do cilindro. No mundo ela virou um canteiro visto pelo vidro.</li></ul>')
    a('<h3>A × B (pernas × base cheia): recomendo B</h3><div class="row">')
    a(fig("cultivador_A_B.png", 5, "A vazio · A com planta 1 · B vazio · B com planta 1"))
    a('</div><p>Na A, as pernas viram 2 colchetes brancos colados na sapata (a sapata B das máquinas já ocupa o lugar dos pés) e o vidro parece flutuar. A B tem a silhueta mais firme e do mesmo tamanho do derretedor.</p>')
    a('<h3>Estados do corpo</h3><div class="row">')
    a(fig1("pendentes/machine_cultivator.png", "machine_cultivator · parado (sem energia ou vazio)"))
    a(animfig("pendentes/anim/anim_machine_cultivator.png", 4, "anim_machine_cultivator · 160×56 · 4 quadros ~5 fps (anel pulsando, bolhas)"))
    a(fig1("pendentes/machine_cultivator_dry.png", "machine_cultivator_dry · seco (sem líquido, LED vermelho)"))
    a(fig1("pendentes/machine_cultivator_broken.png", "machine_cultivator_broken · ruína do lab"))
    a('</div>')
    a('<h3>As 4 culturas × 4 etapas (muda · pequena · média · madura), compostas como no jogo</h3>')
    a(fig("cultivador_grade.png", 4, "linhas: alga · planta 1 · planta 2 · planta 3"))
    a('<div class="row" style="margin-top:12px">')
    for c, nm in (("algae", "alga"), ("plant_1", "planta 1"), ("plant_2", "planta 2"), ("plant_3", "planta 3")):
        a(f'<figure><div class="chk"><div class="anim" style="position:relative;width:160px;height:224px;background:url(pendentes/anim/anim_machine_cultivator.png) 0 0/640px 224px;--end:-640px">'
          f'<div class="cycle grow_{c}" style="position:absolute;inset:0;background:url(pendentes/cultivator_crop_{c}_0.png) 0 0/160px 224px no-repeat"></div></div></div>'
          f'<figcaption>{nm} crescendo (CSS)</figcaption></figure>')
    a('</div>')
    a('<table style="margin-top:14px"><tr><th>Cultura</th><th>Visual</th><th>Por quê</th></tr>'
      '<tr><td><b>Alga</b> (cultura-controle)</td><td>fitas de alga onduladas, verde da Terra, bolinhas amarelas de flutuação na madura</td><td>é da Terra: o verde mais "normal" do jogo, sem nada do gelo</td></tr>'
      '<tr><td><b>Planta 1</b> (amostra simples)</td><td>talo com folhas redondas e gordinhas, verde-menta; madura dá frutinhas-gota azul-água</td><td>a 1ª mistura: ainda planta de folha, só a "gota" denuncia o gelo</td></tr>'
      '<tr><td><b>Planta 2</b> (mutação)</td><td>báculos de samambaia enrolados, azul-petróleo, ponta de geada e nós que brilham</td><td>o gelo começa a mandar: cor fria, forma estranha, brilho</td></tr>'
      '<tr><td><b>Planta 3</b> (rara)</td><td>lírio de gelo: bulbo e talo violeta, flor de pétalas de cristal gordinhas e o miolo aceso</td><td>a mais "do gelo": cristal e luz própria, sem virar espinho (regra dos minérios: nada pontudo)</td></tr></table>')

    a('<h2>3 · Microscópio, centrífuga e coletor de água</h2>')
    a('<p>Mesma família das máquinas nv.1: sapata B, corpo creme, faixa laranja, painel escuro com LED, contorno <code>#1b1630</code>. Abaixo, ao lado do derretedor e do O₂ aprovados e do player, em 1:1 e ×4.</p>')
    a(fig("escala.png", 1, "1:1 · derretedor · O₂ · cultivador · microscópio · centrífuga · coletor · fundição · player"))
    a(fig("escala.png", 4, "×4"))
    a('<h3>Microscópio</h3><p>Bancada com o <b>funil de gelo</b> atrás à esquerda (entra gelo), platina com a lâmina acesa embaixo da objetiva com a lente ciano, braço em C, ocular, monitor do lado mostrando a célula verde e o <b>rack com 3 frascos</b> (verde, azul, dourado: as 3 amostras) na frente à direita (sai amostra). '
      'O quebrado tem a cabeça tombada pra frente, o monitor rachado, o funil vazio, só 1 frasco e geada na bancada.</p><div class="row">')
    a(fig1("pendentes/machine_microscope.png", "machine_microscope · parado"))
    a(animfig("pendentes/anim/anim_machine_microscope.png", 4, "anim_machine_microscope · analisando (lente e tela piscando)"))
    a(fig1("pendentes/machine_microscope_broken.png", "machine_microscope_broken"))
    a('</div><h3>Centrífuga</h3><p>Tambor baixo de cantos redondos com a boca aberta mostrando o <b>rotor de 4 braços</b>: 2 frascos verdes (alga) e 2 violeta (amostra), que é a receita dela. A tampa de acrílico fumê fica aberta atrás, e uma torre de controle à esquerda tem a tela. '
      'A tira gira 45° por quadro (os frascos alternam a cor, então o laço fecha sem pulo).</p><div class="row">')
    a(fig1("pendentes/machine_centrifuge.png", "machine_centrifuge · parada"))
    a(animfig("pendentes/anim/anim_machine_centrifuge.png", 4, "anim_machine_centrifuge · girando, 5 fps", fps=5))
    a(animfig("pendentes/anim/anim_machine_centrifuge.png", 4, "a mesma tira a 10 fps (se o Dev quiser mais rápido)", fps=10))
    a('</div><h3>Coletor de água</h3><p>Corpo creme com um <b>condensador de aletas</b> no alto (pega o orvalho, com gotinhas brilhando), ventoinha no tampo, e na frente a <b>doca da cápsula</b>: dá pra ver a cápsula enchendo e o bico pingando. À direita, o medidor de umidade (barras ciano). '
      'É diferente o bastante do gerador de O₂ (que é um cilindro liso com janela).</p><div class="row">')
    a(fig1("pendentes/machine_water_collector.png", "machine_water_collector · parado (cápsula vazia)"))
    a(animfig("pendentes/anim/anim_machine_water_collector.png", 4, "anim_machine_water_collector · enchendo"))
    a('</div>')

    a('<h2>4 · Ícones 16×16</h2><p>Em 1:1 e ×6, ao lado dos aprovados (<code>icon_water_capsule</code>, <code>icon_ice</code>, <code>icon_drill</code>).</p><div class="row">')
    icons = ["icon_algae", "icon_plant_1", "icon_plant_2", "icon_plant_3", "icon_sample_basic", "icon_sample_mutant",
             "icon_sample_rare", "icon_water_capsule_empty", "icon_cultivator", "icon_microscope", "icon_centrifuge",
             "icon_water_collector"]
    for n in icons:
        a(f'<figure><div class="chk" style="display:flex;gap:8px;align-items:flex-end"><img class="px" src="pendentes/{n}.png" width="16" height="16"><img class="px" src="pendentes/{n}.png" width="96" height="96"></div><figcaption>{n}</figcaption></figure>')
    for n in ("icon_water_capsule", "icon_ice", "icon_drill"):
        a(f'<figure style="opacity:.8"><div class="chk" style="display:flex;gap:8px;align-items:flex-end"><img class="px" src="../../../assets/sprites/{n}.png" width="16" height="16"><img class="px" src="../../../assets/sprites/{n}.png" width="96" height="96"></div><figcaption>{n} (aprovado)</figcaption></figure>')
    a('</div><p>Amostras: frasco com tampa, um por tipo: <b>simples</b> verde-água com tampa ciano, <b>mutação</b> azul-violeta com um redemoinho claro dentro, <b>rara</b> dourada com brilhinhos em volta. '
      'A <b>cápsula vazia</b> é o desenho aprovado da cápsula com a água trocada por vidro e uma gotinha no fundo (pra ler "vazia", não "transparente").</p>')

    a('<h2>5 · Gelo na porta do lab</h2>')
    a('<p>Sequência <b>inteiro → derretendo → quase → aberto</b>, na fachada sul do lab (porta dupla <code>==</code>), faixa gelada no Úmido, com o player pra escala. Os 2 caminhos:</p>')
    a('<h3>B · gelo colado na porta (recomendo)</h3>')
    a('<img class="full px" src="lab_door_B.png" style="max-width:1560px">')
    a('<p>Uma placa grossa de gelo tampando o vão, feita de blocos em pé lado a lado (topo em degraus, nada de agulha), com blocos soltos no pé e veios de geada. Derretendo, a placa baixa pra metade, racha e pinga, e a porta aparece em cima. Quase, ficam só os cacos e a poça. '
      'Aberto, a porta abre normal e fica a poça. Usa a rampa <code>ICE</code> da faixa gelada no Úmido (a mesma dos gelos-portão nesse estágio), então combina com o gelo em volta.</p>')
    a('<h3>A · blocos dos gelos-portão na frente (zero arte nova)</h3>')
    a('<img class="full px" src="lab_door_A.png" style="max-width:1560px">')
    a('<p>Laje, pedra e lasca dos <code>ice_block_*</code> aprovados, amontoadas na frente da porta, encolhendo pelos quadros (0, 3, 5 e 7). Reaproveita tudo do portão: colisão por quadro, <code>melt</code>, o som. '
      'Funciona, mas lê como "tem gelo no caminho" e não como "a porta está congelada", e o monte tampa a fachada do lab.</p>')

    a('<h2>6 · Mock da UI do cultivador</h2>')
    a('<p>Seguindo o teu rascunho: <b>esquerda</b> tanque com o nível de água (marcas das 5 cápsulas), barra vertical de crescimento ao lado e, embaixo, o slot de <b>reserva</b> e o de <b>vazias</b> (a spec diz que o cultivador solta cápsula vazia); '
      '<b>meio</b> o cilindro com a planta na etapa atual, sobre a terra (é o mesmo PNG da planta do mundo, ampliado ×2: o Dev não precisa de arte nova); <b>direita</b> os 4 slots de colheita. '
      'Embaixo, a faixa dos drones no padrão dos outros painéis (recebe cápsula, envia colheita e vazias). As cores, slots, fontes e cartões são os do <code>game/ui.py</code> (estilo B).</p>')
    a('<h3>A · padrão atual (inventário à esquerda, máquina à direita): recomendo</h3><img class="full" src="ui_cultivador_A.png" width="960" height="540">')
    a('<h3>B · como no rascunho (máquina em cima, inventário embaixo)</h3><img class="full" src="ui_cultivador_B.png" width="960" height="540">')
    a('<p>Na B, máquina + inventário empilhados não cabem nos 270 px lógicos da tela com tudo: tive que tirar a descrição e a faixa dos drones (que hoje todo painel de máquina tem). A A é o jeito que o derretedor, a fundição e o Dispersor já abrem, então o player não estranha e o Dev reaproveita o layout. A B fica mais parecida com o rascunho, mas seria a única janela do jogo nesse formato.</p>')

    a('<h2>7 · Nomes das plantas</h2><table><tr><th>Chave</th><th>Opção 1</th><th>Opção 2</th><th>Por quê</th></tr>'
      '<tr><td><code>plant_1</code></td><td><b>Folha-gota</b> ✓</td><td>Trevo-d\'água</td><td>folhas redondas e as frutinhas-gota de água do gelo</td></tr>'
      '<tr><td><code>plant_2</code></td><td><b>Espiral-de-geada</b> ✓</td><td>Samambaia-fria</td><td>os báculos enrolados com ponta de geada</td></tr>'
      '<tr><td><code>plant_3</code></td><td><b>Lírio-de-Ilves</b> ✓</td><td>Lanterna-de-gelo</td><td>a flor de cristal acesa; a 1ª homenageia a Dra. Ilves, que desconfiava do gelo</td></tr></table>'
      '<p>✓ = a que eu escolheria. A alga continua <b>Alga</b> (ou "Cultura-controle" no tooltip da 1ª unidade, se tu quiser).</p>')

    a('<h2>8 · Decisões que tomei sozinha</h2><ul>'
      '<li><b>Líquido verde-água claro</b> (não o verde forte das refs): com o líquido escuro as plantas sumiam; claro, elas leem pelo contorno.</li>'
      '<li><b>Contorno da planta numa cor escura da própria planta</b> (não o <code>#1b1630</code>): ela está atrás do vidro, e o contorno roxo deixava ela "colada" na frente.</li>'
      '<li><b>Anéis de luz atrás da planta</b> e o risco de brilho do vidro na frente.</li>'
      '<li><b>Etapa madura = colheita pronta</b>: a alga ganha as bolinhas, a planta 1 as frutinhas-gota, a 2 os nós acesos e a 3 abre a flor. Assim dá pra ver de longe qual cultivador tem colheita.</li>'
      '<li><b>Seco = sem líquido no tubo e LED vermelho</b>, com a planta parada (não morre, como na spec).</li>'
      '<li><b>Máquinas quebradas desenhadas apagadas</b>: o jogo não deve escurecer de novo com o <code>RUIN_BROKEN_TINT</code> (fica preto demais). Ver "Pro Dev".</li>'
      '<li><b>Ícones das 4 máquinas desenhados à mão</b> (o r3d reduzido virava borrão em 16×16).</li>'
      '<li>Gelo da porta só na <b>orientação h_s</b> (a do <code>lab.txt</code>) nesta rodada. As outras 3 (h_n, v_e, v_w) saem do mesmo script depois do teu ok no visual, porque as ruínas giram.</li></ul>')

    a('<h2>9 · Dúvidas pro dono</h2><ul>'
      '<li>Cultivador: <b>B (base cheia)</b> fechado? E as 4 culturas, cada uma lendo diferente o bastante?</li>'
      '<li>Gelo da porta: <b>B (colado)</b> ou <b>A (blocos do portão)</b>?</li>'
      '<li>UI: <b>A (padrão)</b> ou <b>B (rascunho)</b>? E o slot de vazias no painel do cultivador, pode ficar?</li>'
      '<li>Nomes: qual de cada par (ou outro)?</li>'
      '<li>A centrífuga gira a 5 fps igual às outras ou mais rápido (10 fps)?</li>'
      '<li>O lago verde das Algas e o musgo nas pedras (também da lista de arte da v0.8) ficam pra rodada 2, junto com o M1. Pode ser?</li></ul>')

    a('<h2>Pro Dev integrar</h2><div class="note q">')
    a('<p><b>Âncora:</b> todas as máquinas são 40×56 (tira 160×56, 4 quadros de 40, ~5 fps), ancoradas no centro da base como as nv.1 (<code>_blit_anchored</code>). Parado = PNG sem tira; trabalhando = tira.</p>')
    a('<table><tr><th>Arquivo</th><th>Tamanho</th><th>Quando</th></tr>'
      '<tr><td><code>machine_cultivator.png</code></td><td>40×56</td><td>parado: sem energia, ou sem cultura (com água)</td></tr>'
      '<tr><td><code>anim/anim_machine_cultivator.png</code></td><td>160×56</td><td>crescendo (energia + água + cultura, dentro da base)</td></tr>'
      '<tr><td><code>machine_cultivator_dry.png</code></td><td>40×56</td><td>tanque vazio (seco), com ou sem cultura</td></tr>'
      '<tr><td><code>machine_cultivator_broken.png</code></td><td>40×56</td><td>ruína do lab (troca o <code>prop_sample_tank</code>). <b>Sem</b> <code>RUIN_BROKEN_TINT</code></td></tr>'
      '<tr><td><code>cultivator_crop_{algae,plant_1,plant_2,plant_3}_{0..3}.png</code></td><td>40×56</td><td>miolo: desenhar <b>depois</b> do corpo, no mesmo (x, y). Etapa 0 muda, 1 pequena, 2 média, 3 madura. Serve em cima do parado, de qualquer quadro da tira e do seco</td></tr>'
      '<tr><td><code>machine_microscope.png</code> · <code>anim/anim_machine_microscope.png</code></td><td>40×56 · 160×56</td><td>parado · analisando</td></tr>'
      '<tr><td><code>machine_microscope_broken.png</code></td><td>40×56</td><td>ruína do lab (troca o <code>prop_microscope_digital</code>). Sem tint</td></tr>'
      '<tr><td><code>machine_centrifuge.png</code> · <code>anim/anim_machine_centrifuge.png</code></td><td>40×56 · 160×56</td><td>parada · girando</td></tr>'
      '<tr><td><code>machine_water_collector.png</code> · <code>anim/anim_machine_water_collector.png</code></td><td>40×56 · 160×56</td><td>parado (cápsula vazia) · enchendo</td></tr>'
      '<tr><td><code>icon_{algae,plant_1,plant_2,plant_3,sample_basic,sample_mutant,sample_rare,water_capsule_empty}.png</code></td><td>16×16</td><td>itens</td></tr>'
      '<tr><td><code>icon_{cultivator,microscope,centrifuge,water_collector}.png</code></td><td>16×16</td><td>menu do construtor / estoque de máquinas</td></tr>'
      '<tr><td><code>lab_ice_door2_h_{0,1,2}.png</code></td><td>64×72</td><td>gelo da porta (opção B): em <b>(x, y − 24)</b> do 1º tile da porta dupla (o mesmo ponto do <code>base_door2_h_s</code>), <b>depois</b> dos 2 quadros fechados da porta. Os 16 px de baixo caem no tile de chão de fora. Etapa pela fração do <code>thaw.gate_progress</code>: 0 até 1/3, 1 até 2/3, 2 até abrir</td></tr>'
      '<tr><td><code>lab_ice_puddle_h.png</code></td><td>64×72</td><td>aberto: poça no chão de fora, mesmo ponto, desenhada na passada do chão (sem colisão)</td></tr></table>')
    a('<p><b>Ordem de desenho:</b> corpo do cultivador → miolo (mesmo ponto); porta dupla → gelo (mesmo ponto, mesma ordem pelo pé da porta). '
      '<b>UI:</b> o cilindro do painel pode usar o PNG da planta do <code>tools/sprites/v08_plants_art.py</code> (grade 20×19, pé no meio da última linha), ampliado ×2 em px lógicos. Se o Dev quiser os 16 em arquivo, eu exporto como <code>ui_crop_*.png</code>.</p>')
    a('</div></div></body></html>')
    (REP / "index.html").write_text("\n".join(o), encoding="utf-8")


EXPECT = {
    "machine_cultivator.png": (40, 56), "machine_cultivator_dry.png": (40, 56), "machine_cultivator_broken.png": (40, 56),
    "anim/anim_machine_cultivator.png": (160, 56),
    "machine_microscope.png": (40, 56), "machine_microscope_broken.png": (40, 56), "anim/anim_machine_microscope.png": (160, 56),
    "machine_centrifuge.png": (40, 56), "anim/anim_machine_centrifuge.png": (160, 56),
    "machine_water_collector.png": (40, 56), "anim/anim_machine_water_collector.png": (160, 56),
    **{f"cultivator_crop_{c}_{s}.png": (40, 56) for c in ("algae", "plant_1", "plant_2", "plant_3") for s in range(4)},
    **{f"icon_{n}.png": (16, 16) for n in ("algae", "plant_1", "plant_2", "plant_3", "sample_basic", "sample_mutant",
                                           "sample_rare", "water_capsule_empty", "cultivator", "microscope", "centrifuge",
                                           "water_collector")},
    **{f"lab_ice_door2_h_{i}.png": (64, 72) for i in range(3)}, "lab_ice_puddle_h.png": (64, 72),
}


def check():
    bad = []
    for n, sz in EXPECT.items():
        p = PEND / n
        if not p.exists():
            bad.append(f"falta {n}")
            continue
        im = Image.open(p)
        if im.size != sz:
            bad.append(f"{n} {im.size} != {sz}")
        al = set(np.unique(np.array(im.convert("RGBA"))[:, :, 3]).tolist())
        if not al <= {0, 255}:
            bad.append(f"{n} alpha {sorted(al)}")
    found = {str(p.relative_to(PEND)) for p in PEND.rglob("*.png") if not str(p.relative_to(PEND)).startswith("_compare")}
    extra = found - set(EXPECT)
    if extra:
        bad.append(f"extras: {sorted(extra)}")
    return bad, len(EXPECT)


def main():
    save_previews()
    bad, n = check()
    msg = (f"Checagem: <b>{n} arquivos</b> nos tamanhos exatos, alpha só 0/255, sem extras (a variante A fica em <code>pendentes/_compare/</code>)."
           if not bad else "Checagem com problema: " + "; ".join(bad))
    print(msg if bad else f"ok: {n} arquivos")
    write_html(msg)


if __name__ == "__main__":
    main()
