#!/usr/bin/env python3
"""Trailer do Hesper · cutscenes da Dra. Ilves (arte pro vídeo de 1:30).

    python3 tools/sprites/trailer_ilves.py

Gera em marketing/trailer/art/:
    cenaN_slug/          as camadas de cada cena (PNG RGBA, alpha 0/255) e as tiras de animação (quadros na horizontal)
    personagem/          a Dra. Ilves: corpo inteiro (perfil, sentada, de costas) e o busto, + a folha de personagem
    preview/             prévias 480×270 (quadro 0) e GIF ×2 de cada cena, montadas só com as camadas
    cenas.json           pra cada cena: arquivos, ordem, posição, quadros, fps e a sugestão de movimento
    index.html           a prévia de tudo (abre local, caminhos relativos)

Formato: cada cena tem um CANVAS de 512×288 = o quadro 16:9 de 480×270 + 16 px de folga dos lados e 9 em cima/embaixo,
pra dar pan/parallax sem sobrar borda. O recorte visível no quadro "parado" é (16, 9, 480, 270). O vídeo amplia ×4 sem
suavizar (480×270 → 1920×1080). As camadas animadas são tiras horizontais de N quadros com a posição (x, y) delas no
canvas (cenas.json). Determinístico: rodar duas vezes dá o mesmo md5.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import trailer_ilves_char as C  # noqa: E402
from trailer_lib import (OUTLINE, Cv, aa_outline, blob, fbm, hash2, light_bands, mix, part, relight, rgb,  # noqa: E402
                         rim_mix, strip, stroke, tube)

ROOT = HERE.parents[1]
OUT = ROOT / "marketing" / "trailer" / "art"
SPR = ROOT / "assets" / "sprites"
GELO = ROOT / "reports" / "design" / "gelo_gigante" / "pendentes"

CW, CH = 512, 288           # canvas com folga
VX, VY = 16, 9              # recorte visível 480×270
VW, VH = 480, 270

# paleta da noite (fria) usada nas cenas internas
NIGHT = ["#0c0b18", "#131226", "#1a1932", "#22223f", "#2b2d4e", "#363a5e", "#454c74"]
COLD = "#a6ecff"
CYAN = "#59d0e6"
GREEN = ["#d6ffd0", "#7fd67a", "#3f8f56", "#1f4a34", "#10261c"]
ORANGE = ["#f4a06a", "#e2733a", "#a9482a"]
WHITE = ["#f1ece2", "#d6cec4", "#aaa0a0", "#7b707c"]
METAL = ["#a6a1b8", "#77728a", "#565168", "#3c3749"]
NIGHT_TINT = (0.42, 0.46, 0.66)


# =================================================================================================================
# registro de camadas
# =================================================================================================================
class Scene:
    def __init__(self, key, slug, title, motion, base_fps=8, duration=""):
        self.key, self.slug, self.title, self.motion = key, slug, title, motion
        self.base_fps = base_fps
        self.duration = duration
        self.layers = []
        self.dir = OUT / f"{key}_{slug}"
        self.dir.mkdir(parents=True, exist_ok=True)

    def add(self, name, frames, x=0, y=0, fps=0, parallax=1.0, move="", loop=True, desc="", alt=None):
        """frames: Cv ou lista de Cv (tira). Salva o PNG e registra a camada na ordem (de trás pra frente)."""
        if isinstance(frames, Cv):
            frames = [frames]
        fname = f"{len(self.layers):02d}_{name}.png"
        img = strip(frames).im if len(frames) > 1 else frames[0].im
        save(img, self.dir / fname)
        self.layers.append(dict(
            order=len(self.layers), name=name, file=f"{self.dir.name}/{fname}", x=int(x), y=int(y),
            w=frames[0].w, h=frames[0].h, frames=len(frames), fps=fps if len(frames) > 1 else 0,
            loop=loop, parallax=parallax, move=move, desc=desc, _frames=[f.im for f in frames]))
        if alt:
            self.layers[-1]["replaces"] = alt
            self.layers[-1]["draw_at_order"] = next(L["order"] for L in self.layers if L["name"] == alt)

    def compose(self, t, alt=False):
        """Quadro t (no fps base) do canvas inteiro 512×288. alt=True troca a camada pela alternativa dela."""
        out = Image.new("RGBA", (CW, CH), (0, 0, 0, 255))
        alts = {L["replaces"]: L for L in self.layers if "replaces" in L} if alt else {}
        for L in self.layers:
            if "replaces" in L:
                continue
            L = alts.get(L["name"], L)
            n = L["frames"]
            i = 0
            if n > 1:
                i = int(t * L["fps"] / self.base_fps)
                i = i % n if L["loop"] else min(i, n - 1)
            out.alpha_composite(L["_frames"][i], (L["x"], L["y"]))
        return out

    def meta(self):
        return dict(id=self.key, slug=self.slug, title=self.title, motion=self.motion, duration=self.duration,
                    canvas=[CW, CH], visible=[VX, VY, VW, VH],
                    layers=[{k: v for k, v in L.items() if not k.startswith("_")} for L in self.layers])


def save(img, path):
    a = np.array(img.convert("RGBA"))
    a[:, :, 3] = np.where(a[:, :, 3] >= 128, 255, 0)
    a[a[:, :, 3] == 0] = 0
    Image.fromarray(a).save(path, optimize=True)


def sprite(name):
    c = Cv(1, 1)
    c.im = Image.open(SPR / name).convert("RGBA")
    c.w, c.h = c.im.size
    from PIL import ImageDraw
    c.d = ImageDraw.Draw(c.im)
    return c


def night(cv, tint=NIGHT_TINT):
    return relight(cv, tint)


def bands_rect(cv, x, y, w, h, ramp, horizontal=True, seed=0):
    """Gradiente em faixas chapadas (com 1 linha de dither ordenado entre faixas)."""
    n = len(ramp)
    for j in range(h) if horizontal else range(w):
        L = (h if horizontal else w)
        v = j / max(1, L - 1) * (n - 1)
        lo = int(v)
        fr = v - lo
        for i in range(w if horizontal else h):
            xx, yy = (x + i, y + j) if horizontal else (x + j, y + i)
            k = lo + (1 if (fr > 0.75 and (xx + yy) % 2 == 0) else 0)
            cv.px(xx, yy, ramp[min(k, n - 1)])


def particles(w, h, n, seed, t, frames, speed=(0.3, 1.0), drift=0.2, cols=("#d6e6ff",), big=0.15, mask=None):
    """Neve/poeira caindo em loop perfeito de `frames` quadros (cada floco percorre a altura em ciclos inteiros)."""
    cv = Cv(w, h)
    for k in range(n):
        x0 = hash2(k, 1, seed) * w
        y0 = hash2(k, 2, seed) * h
        cyc = 1 + int(hash2(k, 3, seed) * 2)           # voltas por loop (inteiro → loop perfeito)
        sway = (hash2(k, 4, seed) - 0.5) * 2
        p = t / frames
        y = (y0 + p * cyc * h) % h
        x = (x0 + p * cyc * h * drift + math.sin((p * 2 + hash2(k, 5, seed)) * math.pi * 2) * 1.5 * sway) % w
        col = cols[k % len(cols)]
        xi, yi = int(x), int(y)
        if mask is not None and not mask(xi, yi):
            continue
        cv.px(xi, yi, col)
        if hash2(k, 6, seed) < big:
            cv.px(xi + 1, yi, col)
            cv.px(xi, yi + 1, col)
            cv.px(xi + 1, yi + 1, col)
    return cv


# =================================================================================================================
# CENA 1 · Laboratório, noite: Ilves curvada no microscópio
# =================================================================================================================
WIN = (36, 44, 150, 112)       # janela (x, y, w, h) no canvas
FLOOR_Y = 252
SIT_X, SIT_Y = 212, FLOOR_Y - C.SIT_FOOT       # a pose sentada (o pé do banco na linha SIT_FOOT da pose)
BENCH_Y = SIT_Y + C.SIT_BENCH                  # tampo da bancada: os antebraços dela apoiam aqui
_EYE, _LENS = C.sit_eye(0.0)
LENS = (round(SIT_X + _LENS[0]), round(SIT_Y + _LENS[1]))   # a lente dos óculos dela (a ocular encosta aqui)
SCOPE_X = LENS[0] - 1          # microscópio


def sky(w, h, seed=3, moon=(118, 30)):
    cv = Cv(w, h)
    bands_rect(cv, 0, 0, w, h, ["#0b0a1a", "#0f0f24", "#14162e", "#1a1f3c", "#22294a"])
    for k in range(40):
        x, y = int(hash2(k, 1, seed) * w), int(hash2(k, 2, seed) * h * 0.7)
        cv.px(x, y, "#8a93c4" if k % 3 else "#d6e6ff")
    if moon:
        mx, my = moon
        cv.ell(mx - 9, my - 9, mx + 9, my + 9, "#c9d3ee")
        cv.ell(mx - 9, my - 9, mx + 5, my + 9, "#e6eeff")
        cv.ell(mx - 6, my - 12, mx + 12, my + 6, "#0f0f24")   # lua minguante: a sombra come a borda
        cv.px(mx - 4, my + 2, "#aab6dc")
    return cv


def ridge(w, h, top, ramp, seed, rough=18, scale=40):
    cv = Cv(w, h)
    f = fbm(w, 1, scale, seed, 3)[0]
    for x in range(w):
        y0 = int(top + (f[x] - 0.5) * rough * 2)
        for y in range(max(0, y0), h):
            k = min(len(ramp) - 1, (y - y0) // 6)
            cv.px(x, y, ramp[0] if y == y0 else ramp[min(k, len(ramp) - 1)])
    return cv


def scene1():
    S = Scene("cena1", "laboratorio", "Laboratório, noite · Dia 140",
              "Pan lento da esquerda pra direita (camadas com parallax), terminando parado em Ilves. Neve na janela "
              "em loop. A luz do microscópio pulsa de leve. No fim, corte seco pro close (cena 1b).",
              duration="6 s")
    wx, wy, ww, wh = WIN

    # ---- 0: céu + serra lá fora (só aparece pela janela)
    out = Cv(CW, CH)
    sk = sky(ww + 24, wh, moon=(96, 26))
    out.paste(sk, wx - 12, wy)
    out.paste(ridge(ww + 24, wh, 70, ["#2a3156", "#222846", "#1b2038"], seed=11), wx - 12, wy)
    out.paste(ridge(ww + 24, wh, 88, ["#3a4470", "#2b3358", "#22294a"], seed=12, rough=10, scale=24), wx - 12, wy)
    S.add("ceu", out, parallax=0.2, desc="céu, lua minguante e a serra (só aparece pela janela)")

    # ---- 1: neve lá fora (tira 8 q.)
    fr = [particles(ww, wh, 70, 21, t, 8, drift=0.35, cols=("#d6e6ff", "#8a9ccf", "#b8c8ee")) for t in range(8)]
    S.add("neve_janela", fr, wx, wy, fps=8, parallax=0.35, desc="neve caindo na janela, loop de 8 quadros")

    # ---- 2: a sala
    room = Cv(CW, CH)
    # parede de painéis
    room.rect(0, 0, CW, FLOOR_Y, NIGHT[2])
    for px in range(0, CW, 64):
        room.vline(px, 0, FLOOR_Y, NIGHT[1])
        room.vline(px + 1, 0, FLOOR_Y, NIGHT[3])
    for py in (36, 176):
        room.hline(0, py, CW, NIGHT[1])
        room.hline(0, py + 1, CW, NIGHT[3])
    for px in range(0, CW, 64):                                  # rebites
        for py in (40, 172):
            room.px(px + 6, py, NIGHT[4])
            room.px(px + 58, py, NIGHT[4])
    room.rect(0, 0, CW, 14, NIGHT[1])                             # teto + canaleta
    room.rect(0, 14, CW, 6, NIGHT[3])
    room.hline(0, 14, CW, NIGHT[4])
    room.hline(0, 19, CW, NIGHT[1])
    for x in range(8, CW, 40):
        room.rect(x, 15, 3, 4, NIGHT[1])
    # cano com faixa laranja
    room.rect(0, 26, CW, 5, NIGHT[3])
    room.hline(0, 26, CW, NIGHT[5])
    room.hline(0, 30, CW, NIGHT[1])
    for x in range(30, CW, 120):
        room.rect(x, 25, 6, 7, ORANGE[2])
        room.hline(x, 25, 6, ORANGE[1])
    # rodapé
    room.rect(0, FLOOR_Y - 8, CW, 8, NIGHT[1])
    room.hline(0, FLOOR_Y - 8, CW, NIGHT[3])
    # janela (moldura grossa + buraco)
    room.rect(wx - 8, wy - 8, ww + 16, wh + 16, NIGHT[4])
    room.rect(wx - 8, wy - 8, ww + 16, 2, NIGHT[5])
    room.rect(wx - 8, wy + wh + 4, ww + 16, 4, NIGHT[1])
    room.rect(wx - 4, wy - 4, ww + 8, wh + 8, NIGHT[1])
    room.rect(wx + ww // 2 - 2, wy, 4, wh, NIGHT[3])              # montante do meio
    room.vline(wx + ww // 2 - 2, wy, wh, NIGHT[4])
    a = room.arr()
    a[wy:wy + wh, wx:wx + ww] = 0
    a[wy:wy + wh, wx + ww // 2 - 2:wx + ww // 2 + 2] = np.array(rgb(NIGHT[3]))
    room.set_arr(a)
    room.vline(wx + ww // 2 - 2, wy, wh, NIGHT[4])
    # geada no canto da janela (cristais em faixa)
    for i in range(18):
        room.px(wx + i, wy + wh - 1 - (i * 7 % 5) // 2, "#8a9ccf")
        room.px(wx + i // 2, wy + wh - 2 - (i % 3), "#6a7cb0")
        room.px(wx + ww - 1 - i, wy + wh - 1 - (i * 5 % 4) // 2, "#8a9ccf")
    # prateleiras com amostras
    for sy in (92, 134):
        room.rect(200, sy, 128, 4, NIGHT[4])
        room.hline(200, sy, 128, NIGHT[5])
        room.hline(200, sy + 4, 128, NIGHT[0])
        room.rect(206, sy + 4, 3, 8, NIGHT[1])
        room.rect(318, sy + 4, 3, 8, NIGHT[1])
    jars = [(206, 92, 10, 14), (220, 92, 8, 10), (232, 92, 12, 16), (262, 92, 9, 12), (276, 92, 9, 12),
            (300, 92, 14, 10), (210, 134, 12, 14), (226, 134, 9, 10), (256, 134, 16, 12), (290, 134, 10, 16),
            (304, 134, 9, 12)]
    for k, (jx, jy, jw, jh) in enumerate(jars):
        def jar(c, jx=jx, jy=jy, jw=jw, jh=jh, k=k):
            c.rect(jx, jy - jh, jw, jh, "#2e3a5c")
            c.rect(jx + 1, jy - jh + 3, jw - 2, jh - 4, "#3d5b80" if k % 3 else "#3c4f6e")
            c.rect(jx + 2, jy - jh // 2, jw - 4, jh // 2 - 1, "#4f7fa6" if k % 2 else "#476a8c")
            c.vline(jx + 1, jy - jh + 2, jh - 3, "#7aa6c8")
            c.rect(jx - 1, jy - jh - 2, jw + 2, 3, NIGHT[5])                 # tampa
            c.hline(jx - 1, jy - jh - 2, jw + 2, NIGHT[6])
        part(room, jar)
    # etiquetas com o laranja da colônia
    for jx in (208, 234, 258, 292):
        room.hline(jx, 86 + (jx % 3), 4, ORANGE[2])
    # caixa de amostras na prateleira de baixo
    part(room, lambda c: (c.rect(240, 160 - 14, 12, 14, NIGHT[4]), c.hline(240, 146, 12, NIGHT[6]),
                          c.rect(243, 150, 6, 3, ORANGE[2])))
    # quadro de avisos/diagrama do gelo colado na parede (papel azulado)
    def board(c):
        c.rect(350, 60, 70, 52, "#2a3050")
        c.rect(352, 62, 30, 22, "#5a6a96")
        c.rect(386, 62, 30, 30, "#4e5d88")
        c.rect(354, 88, 28, 20, "#4e5d88")
        for i in range(6):                                                    # hexágonos de cristal desenhados
            hx, hy = 358 + (i % 3) * 8, 66 + (i // 3) * 8
            c.line([(hx, hy + 2), (hx + 2, hy), (hx + 5, hy), (hx + 7, hy + 2), (hx + 5, hy + 4), (hx + 2, hy + 4),
                    (hx, hy + 2)], "#9fb6e0")
        c.line([(390, 86), (396, 76), (402, 82), (410, 66)], "#9fb6e0")
        c.hline(388, 88, 26, "#9fb6e0")
        for i in range(4):
            c.hline(357, 92 + i * 4, 18 - (i % 2) * 6, "#7f90bc")
        c.ell(374, 92, 379, 97, "#1b1630")                                     # a "mancha" circulada
        c.line([(371, 90), (381, 90), (382, 99), (370, 99), (371, 90)], ORANGE[1])
        c.px(366, 61, ORANGE[1])
        c.px(400, 61, ORANGE[1])
        c.px(368, 87, ORANGE[1])
    part(room, board)
    # piso de grade
    room.rect(0, FLOOR_Y, CW, CH - FLOOR_Y, NIGHT[1])
    room.hline(0, FLOOR_Y, CW, NIGHT[4])
    for y in range(FLOOR_Y + 3, CH, 7):
        room.hline(0, y, CW, NIGHT[0])
    for x in range(0, CW, 22):
        room.line([(x, FLOOR_Y + 1), (x - 12, CH)], NIGHT[0])
    # bancada
    bx0, bx1 = 252, 500

    def bench(c):
        c.rect(bx0, BENCH_Y, bx1 - bx0, 6, "#3a3a5c")
        c.hline(bx0, BENCH_Y, bx1 - bx0, "#555a82")
        c.rect(bx0, BENCH_Y + 6, bx1 - bx0, 3, "#24243f")
        c.rect(bx0 + 6, BENCH_Y + 9, 4, FLOOR_Y - BENCH_Y - 9, "#24243f")
        c.rect(bx0 + 120, BENCH_Y + 9, bx1 - bx0 - 126, FLOOR_Y - BENCH_Y - 9, "#202039")    # gaveteiro
        for i in range(3):
            yy = BENCH_Y + 12 + i * 12
            c.hline(bx0 + 122, yy + 10, bx1 - bx0 - 130, "#161530")
            c.rect(bx0 + 170, yy + 4, 12, 2, "#3a3a5c")
        c.hline(bx0 + 120, BENCH_Y + 9, bx1 - bx0 - 126, "#2c2c4c")
    part(room, bench)
    # caixa térmica de amostras no chão (o container_sealed azul, ofuscado pela noite)
    cont = night(sprite("container_sealed.png"), (0.32, 0.36, 0.52))
    room.paste(cont, 128, FLOOR_Y - 40)
    # microscópio
    sx = SCOPE_X

    def scope(c):
        B = BENCH_Y
        ex, ey = LENS
        c.rect(sx - 2, B - 3, 24, 3, METAL[2])                      # pé
        c.hline(sx - 2, B - 3, 24, METAL[1])
        c.poly([(sx + 14, B - 3), (sx + 20, B - 3), (sx + 20, B - 26), (sx + 16, B - 31), (sx + 9, B - 31),
                (sx + 9, B - 27), (sx + 14, B - 25)], WHITE[2])     # braço em C
        c.line([(sx + 15, B - 4), (sx + 15, B - 25)], WHITE[1])
        c.hline(sx + 10, B - 30, 6, WHITE[1])
        c.rect(sx + 15, B - 17, 5, 2, ORANGE[2])
        c.rect(sx + 19, B - 12, 3, 3, METAL[1])                     # botão de foco
        c.rect(sx + 1, B - 10, 16, 2, METAL[1])                     # platina
        c.hline(sx + 1, B - 10, 16, METAL[0])
        c.rect(sx + 6, B - 26, 5, 12, WHITE[2])                     # canhão
        c.vline(sx + 6, B - 26, 12, WHITE[1])
        c.rect(sx + 7, B - 14, 3, 3, METAL[2])                      # objetiva
        c.poly([(sx + 6, B - 26), (sx + 10, B - 26), (ex + 5, ey + 1), (ex + 3, ey - 2)], WHITE[2])  # ocular
        c.rect(ex + 1, ey - 2, 3, 4, METAL[3])
    part(room, scope)
    # pote de gelo com a coisa escura dentro (camada própria pra animar)
    # monitor
    mx, my = 398, BENCH_Y - 52

    def monitor(c):
        c.rect(mx + 22, my + 40, 8, 12, METAL[3])
        c.rect(mx + 12, BENCH_Y - 3, 28, 3, METAL[2])
        c.rect(mx, my, 52, 40, "#2a2840")
        c.hline(mx, my, 52, "#3e3b5a")
        c.rect(mx + 3, my + 3, 46, 32, "#0b1612")
        c.rect(mx + 3, my + 36, 4, 2, ORANGE[1])
    part(room, monitor)
    # cabo do microscópio até o monitor
    room.line([(sx + 20, BENCH_Y - 1), (mx + 10, BENCH_Y - 1)], "#16152c")
    # caneca, bloco, lápis (vida na bancada)
    part(room, lambda c: (c.rect(470, BENCH_Y - 9, 8, 9, WHITE[3]), c.vline(478, BENCH_Y - 7, 4, WHITE[3]),
                          c.hline(470, BENCH_Y - 9, 8, WHITE[2])))
    part(room, lambda c: (c.rect(330, BENCH_Y - 2, 20, 2, "#8a8fb0"), c.line([(334, BENCH_Y - 3), (346, BENCH_Y - 5)],
                                                                               ORANGE[1])))
    # lâmpada pendurada (apagada)
    part(room, lambda c: (c.vline(300, 20, 30, "#16152c"), c.poly([(292, 50), (308, 50), (312, 58), (288, 58)],
                                                                    NIGHT[4]), c.hline(290, 57, 20, NIGHT[1])))

    # luzes: janela (lua), microscópio (ciano), monitor (verde)
    lights = [
        (wx + ww / 2, wy + wh / 2 + 30, 120, 110, "#7f93d6", 0.55),
        (sx + 6, BENCH_Y - 14, 64, 52, COLD, 1.0),
        (mx + 26, my + 20, 70, 60, "#7fd6a8", 0.7),
    ]
    room = light_bands(room, lights, levels=(0.12, 0.24, 0.38))
    # luz da lua no chão (paralelogramo em faixa)
    a = room.arr()
    for y in range(FLOOR_Y, CH):
        k = y - FLOOR_Y
        x0 = wx + 30 + k * 2
        x1 = wx + ww + 30 + k * 2
        for x in range(max(0, x0), min(CW, x1)):
            if (k < 30) and not (x == x0 and y % 2):
                a[y, x, :3] = np.round(a[y, x, :3] * 0.7 + np.array([80, 96, 150]) * 0.3)
    room.set_arr(a)
    S.add("sala", room, parallax=1.0, desc="parede, janela vazada, prateleiras, bancada, microscópio, monitor")

    # ---- 3: tela do monitor (tira 8 q.: a onda corre e um pico aparece)
    frames = []
    for t in range(8):
        c = Cv(46, 32)
        c.rect(0, 0, 46, 32, "#0b1612")
        for gy in range(4, 32, 7):
            c.hline(0, gy, 46, "#12261c")
        for gx in range(5, 46, 9):
            c.vline(gx, 0, 32, "#12261c")
        pts = []
        for x in range(46):
            ph = (x + t * 6) / 46 * math.pi * 4
            y = 16 + math.sin(ph) * 4 + (8 * math.exp(-((x - (t * 6) % 46) ** 2) / 6) if t in (3, 4, 5) else 0)
            pts.append((x, y))
        c.line(pts, GREEN[1])
        c.hline(2, 2, 14, GREEN[2])
        c.hline(2, 28, 8 + (t % 2) * 6, GREEN[2])
        c.px(42, 2, GREEN[0] if t % 2 else GREEN[3])
        frames.append(c)
    S.add("monitor_tela", frames, mx + 3, my + 3, fps=6, parallax=1.0, desc="osciloscópio verde: onda + pico (3..5)")

    # ---- 4: pote de gelo (tira 6 q.: a mancha escura muda de lugar só um pouquinho)
    frames = []
    jx, jy = sx + 30, BENCH_Y
    for t in range(6):
        c = Cv(18, 24)
        c.rect(2, 4, 14, 20, "#5f86b0")                      # vidro
        c.rect(1, 1, 16, 4, METAL[1])                        # tampa
        c.hline(1, 1, 16, METAL[0])
        c.rect(4, 9, 10, 13, "#a6ecff")                      # gelo
        c.rect(4, 9, 10, 2, "#eef6ff")
        c.rect(11, 11, 3, 11, "#59b8d6")
        c.hline(4, 21, 10, "#4fb3d6")
        dx = [0, 0, 1, 1, 0, -1][t]
        dy = [0, 0, 0, -1, -1, 0][t]
        c.rect(7 + dx, 14 + dy, 3, 3, "#1b2a44")             # a coisa dentro
        c.px(6 + dx, 15 + dy, "#2e4766")
        c.px(10 + dx, 16 + dy + (t % 2), "#2e4766")
        c.vline(3, 6, 16, "#c9e8ff")                         # reflexo do vidro
        c.outline()
        frames.append(c)
    S.add("pote_gelo", frames, jx, jy - 24, fps=3, parallax=1.0,
          desc="pote de amostra: gelo com a mancha escura que se mexe um pixel (vê quem olha fixo)")

    # ---- 5: Ilves (tira 12 q.: respira no ombro e nas costas, chega o rosto na ocular com easing, a mão gira o
    #      foco, o coque/mecha/barra do jaleco atrasam, pisca nos q. 8-10). O rosto ganha a luz forte da lâmina.
    frames = []
    lx, ly = _LENS
    for v in C.sit_cycle(12, light=(1, 0)):
        v = night(v, (0.56, 0.58, 0.76))
        v = light_bands(v, [(lx + 2, ly + 5, 12, 12, "#e6f4f8", 1.0), (lx + 6, ly + 14, 34, 30, COLD, 0.6)],
                        x0=SIT_X, y0=SIT_Y, levels=(0.12, 0.26, 0.42), dw=0.05)
        near = np.zeros((v.h, v.w), bool)
        near[0:56, 44:] = True
        v = rim_mix(v, (1, 0), COLD, 0.6, depth=1, only=near)
        frames.append(v)
    S.add("ilves", frames, SIT_X, SIT_Y, fps=6, parallax=1.0,
          desc="Ilves curvada na ocular: loop de 12 q. (2 s) com respiração, easing, coque/jaleco atrasando, piscada")

    # ---- 6: brilho da lâmina do microscópio (tira 4 q.: pulsa)
    frames = []
    for t in range(4):
        c = Cv(20, 8)
        r = [3, 4, 4, 3][t]
        c.ell(10 - r - 2, 4 - 1, 10 + r + 2, 4 + 1, CYAN)
        c.ell(10 - r, 3, 10 + r, 5, COLD)
        c.hline(9, 4, 3, "#eef6ff")
        frames.append(c)
    S.add("lamina_brilho", frames, sx - 1, BENCH_Y - 14, fps=4, parallax=1.0, desc="a lâmina acesa pulsa")

    # ---- 7: primeiro plano (silhueta de equipamento à esquerda e cabos pendurados)
    fg = Cv(CW, CH)
    fg.poly([(0, 190), (24, 186), (30, 288), (0, 288)], NIGHT[0])
    fg.rect(0, 200, 40, 6, NIGHT[1])
    fg.poly([(470, 0), (512, 0), (512, 60), (494, 56)], NIGHT[0])
    fg.line([(480, 0), (488, 40), (486, 90)], NIGHT[0], 2)
    fg.line([(500, 0), (497, 70), (505, 120)], NIGHT[0], 2)
    S.add("primeiro_plano", fg, parallax=1.4, desc="silhuetas escuras na frente: mexem mais rápido no pan")
    return S


# =================================================================================================================
# CENA 1b · Close: o rosto dela na ocular, iluminado de baixo pela lâmina
# =================================================================================================================
def scene1b():
    S = Scene("cena1b", "close_rosto", "Close: Ilves na ocular",
              "Zoom bem lento pra dentro (1.00 → 1.06) ancorado no olho dela. Ela pisca uma vez no meio. A poeira "
              "flutua no feixe de luz. O fundo fica parado (ou com parallax mínimo).", duration="3 s")
    bx, by = 130, 90                      # posição do busto (200×200)
    _e = C.rot([(33.6, -10.4)], 0.2, *C.BH)[0]
    eye = (round(bx + _e[0]), round(by + _e[1]))

    # ---- 0: fundo fora de foco (manchas de luz grandes e chapadas)
    bg = Cv(CW, CH, NIGHT[1])
    bands_rect(bg, 0, 0, CW, CH, [NIGHT[0], NIGHT[1], NIGHT[1], NIGHT[2]])
    # formas fora de foco: potes na prateleira, o monitor verde, a janela
    for (x, y, w, h, col) in [(20, 96, 22, 40, "#22305a"), (50, 104, 16, 32, "#1f2a4c"), (76, 92, 26, 44, "#243460"),
                              (420, 40, 70, 54, "#173a2c"), (300, 20, 40, 60, "#1b2140"), (120, 100, 18, 36, "#1f2a4c")]:
        col = mix(NIGHT[1], col, 0.7)
        bg.rect(x + 3, y, w - 6, h, col)
        bg.rect(x, y + 3, w, h - 6, col)
        bg.rect(x + 4, y + 4, w - 8, 3, mix(col, "#7f93d6", 0.12))
    # prateleira borrada (faixas horizontais)
    bg.rect(0, 150, CW, 6, "#1e1d38")
    bg.rect(0, 156, CW, 3, NIGHT[0])
    bg = light_bands(bg, [(eye[0] + 40, eye[1] + 50, 200, 150, COLD, 0.6)], levels=(0.06, 0.12, 0.2), dw=0.08)
    S.add("fundo", bg, parallax=0.4, desc="laboratório fora de foco: manchas de luz chapadas")

    # ---- 1: Ilves busto (tira 12 q.: concentração. Respira no ombro, chega na ocular com easing, micro-sacada,
    #      piscada natural nos q. 7-9; o coque e a mecha atrasam)
    def light_bust(v):
        v = night(v, (0.52, 0.52, 0.7))
        v = light_bands(v, [(150, 100, 120, 90, COLD, 1.0)], x0=bx, y0=by, levels=(0.12, 0.24, 0.36), dw=0.1)
        near = np.zeros((v.h, v.w), bool)
        near[10:150, 100:] = True
        v = rim_mix(v, (1, 0), COLD, 0.65, depth=2, only=near)
        return rim_mix(v, (0, 1), CYAN, 0.35, depth=1, only=near)
    S.add("ilves_busto", [light_bust(v) for v in C.bust_cycle(12)], bx, by, fps=6, parallax=1.0,
          desc="busto de perfil, concentrada: loop de 12 q. (2 s), respiração, piscada nos q. 7-9")
    reacao = [light_bust(v) for v in C.bust_reaction(10)]

    # ---- 2: poeira no feixe (tira 8 q.)
    def in_beam(x, y):
        return (x - 70) ** 2 / 90 ** 2 + (y - 60) ** 2 / 60 ** 2 < 1
    fr = [particles(160, 120, 24, 77, t, 8, drift=-0.1, cols=(COLD, "#8fb6d6"), big=0.0, mask=in_beam)
          for t in range(8)]
    S.add("poeira_feixe", fr, eye[0] - 20, eye[1] - 20, fps=4, parallax=1.1, desc="poeira flutuando na luz fria")

    # ---- 3: a ocular entrando pela direita, em primeiro plano
    fg = Cv(CW, CH)
    ex, ey = eye[0] + 30, eye[1] + 4

    def tube(c):
        c.poly([(ex, ey - 12), (ex + 20, ey - 14), (ex + 120, ey + 60), (ex + 100, ey + 92), (ex + 8, ey + 22),
                (ex, ey + 18)], WHITE[2])
        c.poly([(ex + 8, ey + 22), (ex + 100, ey + 92), (ex + 120, ey + 60), (ex + 112, ey + 70), (ex + 14, ey + 14)],
               WHITE[3])
        c.line([(ex + 20, ey - 12), (ex + 118, ey + 58)], WHITE[1])
        c.poly([(ex + 40, ey + 2), (ex + 52, ey + 4), (ex + 50, ey + 30), (ex + 34, ey + 26)], ORANGE[2])
        c.rect(ex - 6, ey - 14, 8, 34, METAL[3])                      # borracha da ocular
        c.vline(ex - 6, ey - 14, 34, METAL[2])
        c.rect(ex + 120, ey + 60, 60, 120, "#232238")                 # corpo do microscópio
    part(fg, tube)
    fg = night(fg, (0.5, 0.55, 0.75))
    fg = light_bands(fg, [(ex, ey + 30, 60, 60, COLD, 1.0)], levels=(0.15, 0.3), dw=0.12)
    # anel de luz que sai da ocular no olho dela
    for i, col in enumerate([CYAN, COLD]):
        fg.vline(ex - 7 - i, ey - 6 + i * 2, 18 - i * 4, col)
    S.add("ocular", fg, parallax=1.3, desc="a ocular do microscópio em primeiro plano (sai pela direita)")

    # ---- 4: alternativa da camada 01 · medo contido (10 q., sem loop): usar DEPOIS da cena 2, no lugar da 01
    S.add("ilves_reacao", reacao, bx, by, fps=6, loop=False, parallax=1.0, alt="ilves_busto",
          desc="ALTERNATIVA da 01 (desenha na mesma posição/ordem dela): ela afasta o rosto devagar, os olhos "
               "abrem, a sobrancelha sobe, a boca entreabre; coque e mecha chegam atrasados. Para no último q.")
    return S


# =================================================================================================================
# texto pixelado (Silkscreen 8 px, sem anti-aliasing)
# =================================================================================================================
FONT_DIR = ROOT / "game" / "fonts"


def text(cv, x, y, s, col, size=8, font="Silkscreen-Regular.ttf"):
    from PIL import ImageDraw, ImageFont
    f = ImageFont.truetype(str(FONT_DIR / font), size)
    m = Image.new("L", (cv.w, cv.h), 0)
    d = ImageDraw.Draw(m)
    d.fontmode = "1"
    d.text((x, y), s, fill=255, font=f)
    a = cv.arr()
    sel = np.array(m) > 127
    a[sel] = rgb(col)
    cv.set_arr(a)
    return f.getlength(s)


# =================================================================================================================
# CENA 2 · Close no microscópio: cristais de gelo e a forma escura que se mexe
# =================================================================================================================
LENS_C = (256, 144)
LENS_R = 118
ICE = ["#2f6f96", "#4fb3d6", "#7fd0ea", "#a6ecff", "#d4f6ff", "#eef6ff"]
DEEP = ["#0f1830", "#1b2a44", "#2e4766", "#3f6588"]


def voronoi_field(w, h, n, seed, cell_ramp):
    """Células de gelo: Voronoi com borda escura e miolo mais claro em faixas."""
    pts = np.array([(hash2(k, 1, seed) * w, hash2(k, 2, seed) * h) for k in range(n)])
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    d = np.stack([np.hypot(xx - px, yy - py) for px, py in pts])
    o = np.sort(d, axis=0)
    edge = o[1] - o[0]                       # distância até a borda da célula
    nearest = np.argmin(d, axis=0)
    shade = np.array([hash2(k, 3, seed) for k in range(n)])[nearest]
    v = np.clip(edge / 14, 0, 1) * 0.75 + shade * 0.25
    from trailer_lib import bands
    a = bands(v, cell_ramp, dither=0.25)
    a[edge < 1.6] = rgb(cell_ramp[0])
    return a, pts, edge


def creature_small(cv, cx, cy, t, scale=1.0):
    """A coisa escura em C, pequena (vista no microscópio). t = quadro (0..7): enrola/desenrola e a cauda bate."""
    curl = 0.82 + 0.12 * math.sin(t / 8 * math.pi * 2)
    tail = math.sin(t / 8 * math.pi * 4) * 0.35
    a0 = -0.6 * math.pi
    n = 13
    segs = []
    for i in range(n):
        u = i / (n - 1)
        ang = a0 + u * 2 * math.pi * curl + (tail * u * u if u > 0.7 else 0)
        r = (14 - 3 * u) * scale
        rad = (6.5 - 4.5 * u) * scale if u > 0.12 else (5.0 + 12 * u) * scale
        segs.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r * 0.9, rad))
    # véu (o gelo escurece em volta)
    for (x, y, rad) in segs:
        cv.ell(x - rad - 4, y - rad - 4, x + rad + 4, y + rad + 4, DEEP[3])
    for (x, y, rad) in segs:
        cv.ell(x - rad - 2, y - rad - 2, x + rad + 2, y + rad + 2, DEEP[2])
    for (x, y, rad) in segs:
        cv.ell(x - rad, y - rad, x + rad, y + rad, DEEP[1])
    for i, (x, y, rad) in enumerate(segs):
        if i % 2 == 0 and rad > 2:
            cv.ell(x - rad + 2, y - rad + 2, x + rad - 2, y + rad - 2, DEEP[0])
    # cabeça: um ponto mais escuro (sem olho, só a sugestão)
    hx, hy, hr = segs[0]
    k = max(2, int(2 * scale))
    cv.ell(hx - k, hy - k, hx + k, hy + k, OUTLINE)
    # dobras dos segmentos
    for i in range(1, n - 1, 2):
        x, y, rad = segs[i]
        cv.px(int(x), int(y - rad), DEEP[2])


def creature_big(cx, cy, t=0, R0=74, T=34, contract=0.0):
    """A criatura em C grande (close 6b), como campo de distância: tubo contínuo com cabeça bulbosa, anéis de
    segmento, perninhas recolhidas do lado de dentro, luz de recorte fria na borda. Devolve (Cv, mapa u)."""
    breath = math.sin(t / 8 * math.pi * 2)
    curl = 0.80 + 0.02 * breath + 0.06 * contract
    a0 = -0.62 * math.pi
    N = 260
    us = np.linspace(0, 1, N)
    ang = a0 + us * 2 * math.pi * curl
    rr = R0 * (1 - 0.28 * us) * (1 - 0.05 * contract)
    sx = cx + np.cos(ang) * rr
    sy = cy + np.sin(ang) * rr * 0.92
    rad = T * (1.0 - 0.68 * us) + T * 0.28 * np.exp(-(us / 0.09) ** 2) + 0.6 * breath
    yy, xx = np.mgrid[0:CH, 0:CW].astype(float)
    best = np.full((CH, CW), 9.0)
    bu = np.zeros((CH, CW))
    bdx = np.zeros((CH, CW))
    bdy = np.zeros((CH, CW))
    for i in range(N):
        dx, dy = xx - sx[i], yy - sy[i]
        d = np.hypot(dx, dy) / rad[i]
        sel = d < best
        best[sel] = d[sel]
        bu[sel] = us[i]
        bdx[sel] = dx[sel] / rad[i]
        bdy[sel] = dy[sel] / rad[i]
    inside = best < 1
    # perninhas: nubs do lado de dentro do C
    nub = np.zeros_like(inside)
    for k, u in enumerate(np.arange(0.18, 0.62, 0.075)):
        i = int(u * (N - 1))
        nx, ny = cx - sx[i], cy - sy[i]
        L = math.hypot(nx, ny)
        px_, py_ = sx[i] + nx / L * rad[i] * 1.05, sy[i] + ny / L * rad[i] * 1.05
        r = 4.5 - k * 0.3 + (1.2 * contract if k % 2 else 0)
        nub |= (xx - px_) ** 2 / (r * 1.4) ** 2 + (yy - py_) ** 2 / r ** 2 < 1
    nub &= ~inside
    # sombreamento em faixas
    light = -(bdx * 0.6 + bdy * 0.8)                       # luz de cima-esquerda
    ring = ((bu * 15) % 1) < 0.1
    v = 1 - best                                            # 0 na borda, 1 no miolo
    idx = np.where(v < 0.12, 3, np.where(v < 0.35, 2, np.where(v < 0.7, 1, 0)))
    idx = np.where((light > 0.45) & (v < 0.5), np.minimum(idx + 1, 4), idx)
    idx = np.where(ring & (v > 0.1), np.maximum(idx - 1, 0), idx)
    ramp = ["#0a0f22", "#152340", "#223a5e", "#335a80", "#4f84aa"]
    cols = np.array([rgb(c) for c in ramp], np.uint8)
    a = np.zeros((CH, CW, 4), np.uint8)
    a[inside] = cols[idx[inside]]
    a[nub] = rgb(ramp[1])
    # cabeça: fenda escura (sem olho, só a sugestão)
    hx, hy = sx[0], sy[0]
    slit = ((xx - hx - 6) ** 2 / 10 ** 2 + (yy - hy + 4) ** 2 / 2.2 ** 2 < 1) & inside
    a[slit] = rgb(OUTLINE)
    c = Cv(CW, CH)
    c.set_arr(a)
    c.outline("#0a0f22")
    um = np.where(inside | nub, bu, -1)
    return c, um


def scene2():
    S = Scene("cena2", "microscopio", "Close no microscópio",
              "Câmera parada. O campo de cristais deriva bem devagar (pan de ~12 px em 4 s). A forma escura se mexe "
              "de um quadro pro outro (8 q.). No fim, ela PARA e a tela corta pro preto, como se tivesse percebido.",
              duration="4 s")
    cx, cy = LENS_C
    fw, fh = 2 * LENS_R + 40, 2 * LENS_R + 40
    ox, oy = cx - fw // 2, cy - fh // 2

    # ---- 0: campo de cristais (maior que a lente pra poder derivar)
    a, pts, edge = voronoi_field(fw, fh, 22, 5, ["#1f5578", ICE[0], ICE[1], ICE[2], ICE[3]])
    f = Cv(fw, fh)
    f.set_arr(a)
    # bolhas presas no gelo
    for k in range(22):
        bx, by = int(hash2(k, 7, 9) * fw), int(hash2(k, 8, 9) * fh)
        r = 1 + int(hash2(k, 9, 9) * 4)
        f.ell(bx - r, by - r, bx + r, by + r, ICE[2])
        f.ell(bx - r + 1, by - r + 1, bx + r - 1, by + r - 1, ICE[3])
        f.px(bx - r // 2, by - r // 2, ICE[5])
    # rachaduras finas
    for k in range(5):
        x, y = hash2(k, 11, 3) * fw, hash2(k, 12, 3) * fh
        pp = [(x, y)]
        for j in range(6):
            x += (hash2(k, j, 31) - 0.5) * 16 + 8
            y += (hash2(k, j, 32) - 0.5) * 10 + 4
            pp.append((x, y))
        f.line(pp, "#1f5578")
    S.add("campo_cristais", f, ox, oy, parallax=0.6,
          desc="células de gelo (Voronoi em faixas), bolhas e rachaduras; 40 px de folga pra derivar")

    # ---- 1: a forma escura (tira 8 q. + 2 de "parou")
    frames = []
    for t in range(10):
        c = Cv(110, 110)
        tt = t if t < 8 else 2
        creature_small(c, 55 + [0, 1, 2, 2, 1, 0, -1, -1, 0, 0][t], 55 + [0, 0, 1, 1, 2, 1, 1, 0, 0, 0][t], tt,
                       scale=2.2)
        frames.append(c)
    S.add("forma_escura", frames, cx - 55 + 14, cy - 55 + 8, fps=5, parallax=0.6,
          desc="a coisa em C: enrola/desenrola e a cauda bate (q. 0..7 em loop); q. 8..9 = parada (usar no fim)")

    # ---- 2: lente (máscara preta com o círculo vazado, vinheta em faixas, retículo)
    m = Cv(CW, CH, "#000000")
    a = m.arr()
    yy, xx = np.mgrid[0:CH, 0:CW].astype(float)
    d = np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
    a[d < LENS_R] = 0
    ring = [(LENS_R + 3, "#0b1630"), (LENS_R, "#16284a"), (LENS_R - 3, None)]
    a[(d >= LENS_R) & (d < LENS_R + 3)] = rgb("#1a2c50")
    a[(d >= LENS_R + 3) & (d < LENS_R + 5)] = rgb("#0c1428")
    # vinheta: 3 faixas escuras por dentro da borda, com dither
    from trailer_lib import BAYER4
    b = BAYER4[(yy.astype(int)) % 4, (xx.astype(int)) % 4]
    for k, (r0, col, dens) in enumerate([(LENS_R - 4, "#0f2236", 1.0), (LENS_R - 10, "#1c4462", 0.5),
                                         (LENS_R - 16, "#1c4462", 0.25)]):
        sel = (d < LENS_R) & (d >= r0) & (a[:, :, 3] == 0) & (b < dens)
        a[sel] = rgb(col)
    m.set_arr(a)
    # retículo: régua no meio e cruz fina
    for i in range(-60, 61, 6):
        h = 4 if i % 30 == 0 else 2
        m.vline(cx + i, cy + 70 - h, h, "#a6ecff")
    m.hline(cx - 60, cy + 70, 121, "#a6ecff")
    m.vline(cx, cy - 8, 5, "#7fd0ea")
    m.vline(cx, cy + 4, 5, "#7fd0ea")
    m.hline(cx - 8, cy, 5, "#7fd0ea")
    m.hline(cx + 4, cy, 5, "#7fd0ea")
    text(m, 30, 250, "AMOSTRA 07 · GELO DO FUNDO", "#3f6588")
    text(m, 30, 262, "400X  ·  -71 C", "#3f6588")
    text(m, 400, 262, "DIA 140", "#3f6588")
    S.add("lente", m, parallax=1.0, desc="máscara da ocular: preto fora, vinheta em faixas, régua do retículo, legenda")

    # ---- 3: plâncton de gelo (pontinhos derivando dentro da lente, tira 8 q.)
    def in_lens(x, y):
        return (x - LENS_R) ** 2 + (y - LENS_R) ** 2 < (LENS_R - 6) ** 2
    fr = [particles(2 * LENS_R, 2 * LENS_R, 30, 41, t, 8, drift=0.6, cols=(ICE[5], "#1b2a44"), big=0.3, mask=in_lens)
          for t in range(8)]
    S.add("particulas", fr, cx - LENS_R, cy - LENS_R, fps=2, parallax=0.6,
          desc="partículas presas no filme de água derivando devagar")
    return S


# =================================================================================================================
# CENA 3 · Ilves trancando o laboratório (de costas, corredor escuro) + 3b insert da chave
# =================================================================================================================
DOOR = (238, 100, 72, 152)      # x, y, w, h (pé em FLOOR_Y)
LOCK_Y = FLOOR_Y - C.BACK_FOOT + C.BACK_HAND[1]   # altura da fechadura = altura da mão dela


def corridor_lamp(cv, x, y, on=True):
    cv.rect(x - 14, y, 28, 4, NIGHT[4])
    cv.hline(x - 14, y, 28, NIGHT[5])
    cv.rect(x - 11, y + 4, 22, 2, "#d6e6ff" if on else NIGHT[3])


def scene3():
    S = Scene("cena3", "trancando", "Ilves tranca o laboratório · Dia 140, noite",
              "Plano parado e longo. A lâmpada do corredor mais perto pisca. Ela gira a chave (o LED do painel vai "
              "de verde pra vermelho: usar a tira sem loop). Corte pro insert 3b (a mão e a chave) e volta. "
              "Opcional: pan lento pra esquerda revelando o corredor escuro.", duration="5 s")
    dx, dy, dw, dh = DOOR
    room = Cv(CW, CH, NIGHT[1])
    # parede do corredor: faixa de painéis em 3 alturas
    room.rect(0, 0, CW, 40, NIGHT[0])                                    # teto
    room.rect(0, 40, CW, 6, NIGHT[2])
    room.hline(0, 45, CW, NIGHT[0])
    for x in range(0, CW, 48):
        room.vline(x, 46, FLOOR_Y - 46, NIGHT[0])
        room.vline(x + 1, 46, FLOOR_Y - 46, NIGHT[2])
    room.rect(0, 186, CW, 4, NIGHT[3])                                   # corrimão / faixa
    room.hline(0, 186, CW, NIGHT[4])
    for x in range(10, CW, 96):
        room.rect(x, 187, 30, 2, ORANGE[2])
    room.rect(0, FLOOR_Y - 10, CW, 10, NIGHT[0])
    # canos no alto
    room.rect(0, 52, CW, 4, NIGHT[3])
    room.hline(0, 52, CW, NIGHT[4])
    room.rect(0, 60, CW, 3, NIGHT[2])
    # porta do laboratório (moldura grossa, folha com janelinha)
    room.rect(dx - 10, dy - 10, dw + 20, dh + 10, NIGHT[3])
    room.hline(dx - 10, dy - 10, dw + 20, NIGHT[5])
    room.rect(dx - 4, dy - 4, dw + 8, dh + 4, NIGHT[0])
    room.rect(dx, dy, dw, dh, "#2a2c4c")
    room.vline(dx + dw // 2, dy, dh, NIGHT[0])                          # porta dupla de correr
    room.vline(dx + dw // 2 + 1, dy, dh, "#33365a")
    for k in (0, 1):
        x0 = dx + k * (dw // 2)
        room.rect(x0 + 6, dy + 8, dw // 2 - 12, 30, NIGHT[0])           # janelinha (o brilho entra em camada)
        room.rect(x0 + 4, dy + 48, dw // 2 - 8, 4, "#3a3d64")           # faixa
        room.rect(x0 + 4, dy + 54, dw // 2 - 8, 3, ORANGE[2])
        for yy in range(dy + 66, dy + dh - 6, 10):
            room.hline(x0 + 4, yy, dw // 2 - 8, "#222340")
    # placa em cima da porta
    room.rect(dx + 6, dy - 30, dw - 12, 14, NIGHT[0])
    room.rect(dx + 7, dy - 29, dw - 14, 12, "#1c2a3e")
    text(room, dx + 12, dy - 28, "LAB 2 ·", "#7fd0ea")
    text(room, dx + 12 + 34, dy - 28, "CRIO", ORANGE[1])
    # aviso de risco ao lado
    part(room, lambda c: (c.poly([(380, 120), (396, 148), (364, 148)], ORANGE[1]),
                          c.poly([(380, 126), (391, 145), (369, 145)], "#2a1a20"),
                          c.rect(379, 132, 2, 7, ORANGE[1]), c.px(379, 141, ORANGE[1]), c.px(380, 141, ORANGE[1])))
    # painel da fechadura (o LED entra em camada)
    room.rect(dx + dw + 10, LOCK_Y - 10, 14, 22, NIGHT[3])
    room.hline(dx + dw + 10, LOCK_Y - 10, 14, NIGHT[5])
    room.rect(dx + dw + 13, LOCK_Y - 3, 8, 8, NIGHT[0])
    room.rect(dx + dw + 16, LOCK_Y - 1, 2, 4, "#000000")                       # fechadura
    # lâmpadas do teto (as caixas; o acender/apagar é camada)
    for lx in (60, 180, 300):
        corridor_lamp(room, lx, 32)
    corridor_lamp(room, 420, 32, on=False)
    # chão: grade com reflexo
    room.rect(0, FLOOR_Y, CW, CH - FLOOR_Y, NIGHT[0])
    room.hline(0, FLOOR_Y, CW, NIGHT[3])
    for y in range(FLOOR_Y + 4, CH, 6):
        room.hline(0, y, CW, NIGHT[1])
    lights = [(60, 40, 40, 60, "#b8c8ee", 0.5), (180, 40, 40, 60, "#b8c8ee", 0.5), (300, 40, 40, 60, "#b8c8ee", 0.5),
              (dx + dw / 2, dy + 30, 70, 100, CYAN, 0.8)]
    room = light_bands(room, lights, levels=(0.08, 0.16, 0.26), dw=0.15)
    # reflexo da janelinha da porta no chão
    for k in (0, 1):
        x0 = dx + k * (dw // 2) + 6
        for y in range(FLOOR_Y + 2, FLOOR_Y + 22, 2):
            room.hline(x0, y, dw // 2 - 12, "#1c4462")
    # escuro nos dois cantos (o corredor some)
    a = room.arr().astype(float)
    xx = np.arange(CW)
    dark = np.clip(np.maximum((90 - xx) / 90, (xx - 430) / 82), 0, 1)
    from trailer_lib import BAYER4
    yy = np.arange(CH)[:, None]
    bb = BAYER4[yy % 4, xx[None, :] % 4]
    sel = (dark[None, :] * 1.0) > bb
    a[sel] = np.array(rgb(NIGHT[0]), float)
    room.set_arr(a)
    S.add("corredor", room, parallax=1.0, desc="corredor, porta do LAB 2, placa, painel da fechadura, chão de grade")

    # ---- 1: brilho da janelinha (o microscópio ficou ligado lá dentro) · tira 4 q.
    frames = []
    for t in range(4):
        c = Cv(dw, 32)
        for k in (0, 1):
            x0 = k * (dw // 2) + 6
            c.rect(x0, 0, dw // 2 - 12, 30, "#1c4462")
            c.rect(x0, 18, dw // 2 - 12, 12, "#2f6f96")
            c.rect(x0 + 2 + k * 4, 22 - (t % 2), 8, 8 + (t % 2), CYAN if t != 2 else "#4fb3d6")
            c.hline(x0, 0, dw // 2 - 12, "#0f2236")
            c.line([(x0 + 2, 2), (x0 + 8, 8)], "#4f7fa6")                # reflexo do vidro
        frames.append(c)
    S.add("janelinha_brilho", frames, dx, dy + 8, fps=3, desc="luz fria lá dentro, tremendo")

    # ---- 2: lâmpada que pisca (tira 8 q.)
    frames = []
    pat = [1, 1, 0, 1, 0, 0, 1, 1]
    for t in range(8):
        c = Cv(80, 230)
        if pat[t]:
            corridor_lamp(c, 40, 0)
            cone = Cv(80, 230)
            cone.poly([(32, 6), (48, 6), (70, 218), (10, 218)], "#2a2d55")
            cone.poly([(36, 6), (44, 6), (56, 218), (24, 218)], "#33376a")
            a2 = cone.arr()
            yy2, xx2 = np.mgrid[0:230, 0:80]
            a2[((xx2 + yy2) % 2 == 1) & (yy2 > 30)] = 0                       # pontilhado: lê como luz, não parede
            a2[(yy2 > 120) & ((xx2 + yy2 // 2) % 3 != 0)] = 0
            cone.set_arr(a2)
            c.paste(cone)
            corridor_lamp(c, 40, 0)
        else:
            corridor_lamp(c, 40, 0, on=False)
        frames.append(c)
    S.add("lampada_pisca", frames, 380, 32, fps=6,
          desc="a lâmpada sobre a porta falha (cone de luz chapado quando acesa)")

    # ---- 3: Ilves de costas (tira 12 q.: respira no ombro, a cabeça pesa e baixa um pouco com easing, o coque e a
    #      barra do jaleco atrasam)
    frames = []
    for v in C.back_cycle(12):
        v = night(v, (0.42, 0.46, 0.66))
        top = np.zeros((v.h, v.w), bool)
        top[:50, :] = True
        v = rim_mix(v, (0, -1), CYAN, 0.45, depth=1, only=top)
        v = rim_mix(v, (-1, 0), CYAN, 0.35, depth=1)
        v = rim_mix(v, (1, 0), "#b8c8ee", 0.3, depth=1)
        frames.append(v)
    ix, iy = dx + dw + 16 - C.BACK_HAND[0], FLOOR_Y - C.BACK_FOOT
    S.add("ilves_costas", frames, ix, iy, fps=6,
          desc="Ilves de costas com a mão na fechadura: loop de 12 q. (2 s), respiração e a cabeça pesando")

    # ---- 4: LED da fechadura (tira 6 q., SEM loop: verde → âmbar → vermelho)
    frames = []
    for t in range(6):
        c = Cv(8, 4)
        col = ["#7fd67a", "#7fd67a", "#f2c46d", "#ff6a55", "#ff6a55", "#ff6a55"][t]
        c.rect(0, 0, 8, 3, "#151428")
        c.rect(1, 1, 6, 1, col)
        frames.append(c)
    S.add("led_trava", frames, dx + dw + 13, LOCK_Y - 8, fps=2, loop=False,
          desc="LED do painel: verde, verde, âmbar, vermelho... (não faz loop: para no vermelho)")

    # ---- 5: primeiro plano
    fg = Cv(CW, CH)
    fg.rect(0, 0, 26, CH, NIGHT[0])
    fg.rect(26, 0, 4, CH, "#08070f")
    fg.poly([(490, 288), (512, 288), (512, 230), (500, 236)], "#08070f")
    S.add("primeiro_plano", fg, parallax=1.4, desc="batente escuro à esquerda (parallax no pan)")
    return S


def scene3b():
    S = Scene("cena3b", "chave", "Insert: a chave girando",
              "Câmera parada, bem perto. A mão gira a chave em 4 quadros (sem loop) e o LED vai pro vermelho com "
              "\"TRAVADO\". Segura 1 s no último quadro. Sem música, só o clique.", duration="2 s")
    bg = Cv(CW, CH, "#22243f")
    # chapa da porta: faixas horizontais e rebites
    for y in range(0, CH, 36):
        bg.hline(0, y, CW, NIGHT[0])
        bg.hline(0, y + 1, CW, "#2c2f52")
    for x in range(20, CW, 60):
        for y in range(8, CH, 36):
            bg.rect(x, y, 3, 3, "#2c2f52")
            bg.px(x, y, "#3a3d64")
    # painel grande
    px0, py0, pw, ph = 220, 50, 150, 200
    part(bg, lambda c: (c.rect(px0, py0, pw, ph, "#31345a"), c.hline(px0, py0, pw, "#454a78"),
                        c.rect(px0 + 10, py0 + 10, pw - 20, 26, "#151428"),
                        c.rect(px0 + 30, py0 + 44, 90, 90, "#1c1d36"),
                        c.ell(px0 + 45, py0 + 59, px0 + 105, py0 + 119, "#2a2c4c"),
                        c.ell(px0 + 50, py0 + 64, px0 + 100, py0 + 114, "#3a3d64")))
    cx, cy = px0 + 75, py0 + 89
    bg.rect(cx - 3, cy - 12, 6, 24, "#05050a")                          # buraco da fechadura (vertical)
    for i in range(4):
        bg.rect(px0 + 16 + i * 32, py0 + ph - 26, 22, 12, "#26294a")
        bg.hline(px0 + 16 + i * 32, py0 + ph - 26, 22, "#3a3d64")
    bg = light_bands(bg, [(cx, cy, 200, 160, "#7f93d6", 0.6)], levels=(0.06, 0.12, 0.18), dw=0.1)
    S.add("painel", bg, desc="chapa da porta e o painel da fechadura, de perto")

    # ---- o giro: 12 q. sem loop, com antecipação (a mão aperta e volta um tiquinho), aceleração, desaceleração e um
    #      assentamento no fim. A manga atrasa ~1 quadro. O LED acompanha (fica âmbar no meio do giro).
    N = 12
    ANG = [0.0, 0.0, 0.03, 0.0, -0.08, -0.24, -0.48, -0.72, -0.9, -0.99, -1.03, -1.0]   # × 60°
    PRESS = [0, 0.5, 1, 1, 1, 1, 1, 1, 1, 0.8, 0.5, 0.3]                                # o polegar aperta
    th = [a * math.pi / 3 for a in ANG]

    frames = []
    for t in range(N):
        c = Cv(pw - 20, 26)
        c.rect(0, 0, pw - 20, 26, "#151428")
        st = 0 if ANG[t] > -0.3 else (1 if ANG[t] > -0.95 else 2)
        col = ["#7fd67a", "#f2c46d", "#ff6a55"][st]
        c.rect(6, 8, 10, 10, col)
        c.rect(8, 10, 3, 3, mix(col, "#ffffff", 0.5))
        text(c, 24, 9, ["ABERTO", "...", "TRAVADO"][st], col)
        frames.append(c)
    S.add("led_texto", frames, px0 + 10, py0 + 10, fps=8, loop=False,
          desc="ABERTO → ... → TRAVADO, sincronizado com o giro da chave (para no vermelho)")

    GOLD = ["#fff4cc", "#f2c46d", "#c98a3c", "#8a5a2a"]
    SK = [C.SKIN[0], C.SKIN[1], C.SKIN[2], C.SKIN[3]]
    K = 1.6                                                              # escala do insert
    frames = []
    for t in range(N):
        a0 = th[t] * 0.75                                                # 45° de giro
        a_lag = (th[max(0, t - 1)] * 0.6 + th[t] * 0.4) * 0.75           # a manga chega atrasada
        p = PRESS[t]
        R = lambda pts, a=a0: C.rot(pts, a, cx, cy, K)  # noqa: E731
        W = lambda ws: [K * w for w in ws]  # noqa: E731
        c = Cv(CW, CH)
        L = (-1, -1)
        # indicador dobrado POR TRÁS do anel: a lateral dele aparece embaixo/à esquerda (o anel fica preso entre ele e
        # o polegar)
        C.piece(c, lambda k: tube(k, R([(-34, -10), (-28, 8), (-14, 21), (4, 22)]), W([14, 13, 12, 11]), "#ffffff"),
                SK, L, hi=1, sh=3, deep=1, details=lambda d: stroke(d, R([(-22, 12), (-18, 20)]), SK[2], 4))
        # a chave: anel gordinho com furo
        C.piece(c, lambda k: blob(k, R([(-21, -2), (-16, -17), (0, -23), (16, -17), (21, -2), (16, 13), (0, 19),
                                        (-16, 13)]), "#ffffff", 6), GOLD, L, hi=2, sh=3, deep=1, details=lambda d: (
            blob(d, R([(-5, -12), (5, -12), (5, -4), (-5, -4)]), "#26171e", 3),
            stroke(d, R([(-8, 9), (8, 9)]), GOLD[2], 4),
            stroke(d, R([(-14, -12), (-6, -18)]), GOLD[0], 4)))
        # punho fechado: dedos médio/anelar/mínimo dobrados (vincos), nós dos dedos, dorso até o pulso
        fist = [(-46, -22), (-34, -18), (-30, -4), (-32, 12), (-26, 26), (-32, 36), (-46, 40), (-62, 40), (-78, 34),
                (-82, 14), (-72, -6), (-60, -18)]
        C.piece(c, lambda k: blob(k, R(fist), "#ffffff", 6), SK, L, hi=2, sh=4, deep=2, details=lambda d: (
            stroke(d, R([(-44, 4), (-36, 12), (-33, 22)]), SK[2], 6),          # vincos dos dedos dobrados
            stroke(d, R([(-50, 16), (-42, 26), (-38, 34)]), SK[2], 6),
            stroke(d, R([(-60, 24), (-54, 32), (-50, 38)]), SK[2], 6),
            stroke(d, R([(-70, -2), (-54, -10), (-44, -14)]), SK[2], 6),       # tendão
            [d.px(*map(round, R([(x, y)])[0]), SK[0]) for x, y in ((-44, -18), (-40, 0), (-44, 14), (-52, 26))]))
        # polegar por cima do anel, apertando (a ponta afunda quando aperta)
        tip = (2 - p * 1.4, -4 + p * 0.6)
        C.piece(c, lambda k: tube(k, R([(-60, -10), (-40, -12), (-18, -9), tip]), W([19, 16.6, 14.4, 12.4]),
                                  "#ffffff"), SK, L, hi=2, sh=3, deep=1, details=lambda d: (
            blob(d, R([(tip[0] - 9, tip[1] - 6), (tip[0] - 1, tip[1] - 6.4), (tip[0] + 3, tip[1] - 2),
                       (tip[0] - 1, tip[1] + 1.4), (tip[0] - 9, tip[1] + 0.8)]), "#f9e2d0", 4),   # unha
            stroke(d, R([(tip[0] - 9, tip[1] - 6), (tip[0] - 9, tip[1] + 0.8)]), SK[2], 4),
            stroke(d, R([(-32, -16), (-28, -8)]), SK[2], 4)))                                    # dobra da junta
        # punho laranja + manga (atrasada), saindo pela esquerda-embaixo com largura constante
        w1 = C.rot([(-80, 24)], a_lag, cx, cy, K)[0]
        A = (cx - 300, CH + 60)
        ddx, ddy = A[0] - w1[0], A[1] - w1[1]
        Ln = math.hypot(ddx, ddy)
        ux, uy = ddx / Ln, ddy / Ln
        qx, qy = -uy, ux

        def P(base, along, side):
            return (base[0] + ux * along + qx * side, base[1] + uy * along + qy * side)
        C.piece(c, lambda k: blob(k, [P(w1, 4, 40), P(w1, 120, 50), P(A, 0, 58), P(A, 0, -58), P(w1, 120, -50),
                                      P(w1, 4, -40)], "#ffffff", 4), C.COAT, L, hi=2, sh=6, deep=2,
                details=lambda d: (stroke(d, [P(w1, 40, 14), P(w1, 110, 24), P(w1, 180, 18)], C.COAT[2], 6),
                                   stroke(d, [P(w1, 70, -26), P(w1, 140, -32)], C.COAT[2], 6)))
        C.piece(c, lambda k: blob(k, [P(w1, -8, 36), P(w1, 16, 41), P(w1, 16, -41), P(w1, -8, -36)], "#ffffff", 4),
                C.ACC, L, hi=1, sh=2, deep=1)
        aa_outline(c)
        c = night(c, (0.6, 0.62, 0.8))
        c = rim_mix(c, (0, -1), "#b8c8ee", 0.35, depth=2)
        frames.append(c)
    S.add("mao_chave", frames, fps=8, loop=False,
          desc="a mão gira a chave 45° em 12 q. (1,5 s): aperta, antecipa, acelera, desacelera e assenta; para no fim")
    return S


# =================================================================================================================
# CENA 4 · A cargueira VÉSPER-7 carregando os contêineres frios à noite
# =================================================================================================================
GROUND_Y = 240
HULL = ["#a3a8c6", "#7d82a4", "#5c6084", "#43456a", "#2e2f4c"]


def crew(t, lamp=True, carry=False):
    """Tripulante pequeno (12×18) de traje e capacete, andando pra esquerda. t = 0..3."""
    c = Cv(14, 20)
    leg = [(0, 2), (1, 1), (2, 0), (1, 1)][t]
    c.rect(4, 13, 2, 5 - leg[0] // 2, "#4e5274")
    c.rect(7, 13, 2, 5 - leg[1] // 2, "#3a3d5c")
    c.rect(3, 17, 3, 2, "#26263c")
    c.rect(7, 17, 3, 2, "#26263c")
    c.rect(3, 7, 8, 7, HULL[1])
    c.rect(3, 7, 2, 7, HULL[0])
    c.rect(9, 8, 3, 5, "#4e5274")                     # mochila
    c.ell(3, 0, 10, 7, HULL[0])
    c.rect(3, 3, 4, 2, "#26387a")                     # visor (olhando pra esquerda)
    c.px(3, 3, "#6a93e0")
    c.hline(3, 10, 8, ORANGE[2])
    if carry:
        c.rect(0, 9, 4, 2, HULL[2])
    c.outline()
    if lamp:
        c.px(2, 4, "#fffbe0")
    return c


def scene4():
    S = Scene("cena4", "vesper7", "A cargueira VÉSPER-7 · Dia 188",
              "Plano geral parado ou pan bem lento pra direita (parallax: céu 0.1, serra 0.3, nave 1.0, neve na "
              "frente 1.5). Contêiner subindo a rampa no trenó, tripulantes andando, holofotes falhando, a luz "
              "vermelha da antena piscando. Texto do manifesto pode entrar por cima.", duration="6 s")
    # ---- 0: céu
    sk = sky(CW, CH, seed=8, moon=(70, 40))
    # faixa de aurora fria bem apagada
    for x in range(CW):
        y0 = int(60 + math.sin(x / 50) * 10 + math.sin(x / 17) * 3)
        for k in range(10):
            if (x + k) % 2 == 0:
                sk.px(x, y0 + k, "#1c3a4a" if k < 5 else "#182c40")
    S.add("ceu", sk, parallax=0.1, desc="céu noturno, estrelas, lua e uma aurora fria apagada")

    # ---- 1/2: serras
    S.add("serra_longe", ridge(CW, CH, 150, ["#2a3156", "#222846", "#1b2038"], seed=31, rough=30, scale=70),
          parallax=0.3, desc="serra distante")
    S.add("serra_perto", ridge(CW, CH, 196, ["#353d66", "#262c4c", "#1b2038", "#141729"], seed=32, rough=16,
                               scale=34), parallax=0.5, desc="serra perto")

    # ---- 3: plataforma de pouso + nave + contêineres parados
    L = Cv(CW, CH)
    # chão / plataforma
    L.rect(0, GROUND_Y, CW, CH - GROUND_Y, "#2a2b45")
    L.hline(0, GROUND_Y, CW, "#4e5274")
    for y in range(GROUND_Y + 6, CH, 8):
        L.hline(0, y, CW, "#22233a")
    for x in range(-40, CW, 70):
        L.line([(x, GROUND_Y + 1), (x - 40, CH)], "#22233a")
    for x in range(120, 480, 40):                               # faixas de pouso
        L.rect(x, GROUND_Y + 14, 20, 3, "#8a4630")
    # nave (voltada pra esquerda; rampa de carga aberta na barriga)
    def ship(c):
        c.poly([(230, 120), (300, 96), (440, 92), (500, 104), (520, 150), (500, 186), (250, 190), (214, 160)], HULL[1])
        c.poly([(214, 160), (250, 190), (500, 186), (512, 170), (230, 172)], HULL[3])     # barriga em sombra
        c.poly([(230, 120), (300, 96), (440, 92), (440, 102), (300, 106), (236, 128)], HULL[0])   # dorso com luz
        c.rect(300, 140, 200, 8, ORANGE[2])                                               # faixa da companhia
        c.hline(300, 140, 200, ORANGE[1])
        for i in range(5):                                                                # janelas da cabine
            c.rect(238 + i * 9, 132 - i * 2, 6, 5, "#7fd0ea" if i in (1, 2) else "#1b2a44")
        for x in range(300, 470, 12):                                                     # vigias
            c.rect(x, 154, 4, 3, "#1b2a44" if x % 36 else "#f2c46d")
        c.poly([(214, 160), (222, 150), (232, 166)], HULL[2])                             # nariz
        c.rect(330, 110, 150, 2, HULL[2])                                                 # chapas
        for x in range(320, 500, 30):
            c.vline(x, 104, 34, HULL[2])
        # motores
        c.rect(470, 112, 50, 24, HULL[2])
        c.rect(470, 154, 50, 24, HULL[2])
        c.rect(514, 114, 6, 20, "#1b1b30")
        c.rect(514, 156, 6, 20, "#1b1b30")
        # pernas de pouso
        for lx in (270, 450):
            c.poly([(lx, 186), (lx + 8, 186), (lx + 18, GROUND_Y - 4), (lx + 6, GROUND_Y - 4)], HULL[2])
            c.rect(lx + 2, GROUND_Y - 5, 22, 5, HULL[3])
        # antena
        c.rect(420, 70, 2, 24, HULL[2])
        c.rect(410, 84, 22, 2, HULL[2])
        # boca da baía de carga
        c.rect(320, 160, 100, 26, "#121225")
        c.rect(322, 162, 96, 22, "#3a4a6a")
        c.rect(322, 176, 96, 8, "#2a3654")
    part(L, ship)
    # rampa
    part(L, lambda c: (c.poly([(322, 186), (418, 186), (418, 190), (300, GROUND_Y), (220, GROUND_Y)], HULL[2]),
                       c.line([(322, 187), (222, GROUND_Y - 1)], HULL[0]),
                       [c.line([(330 + i * 14, 187), (236 + i * 14 - 6, GROUND_Y - 1)], HULL[3]) for i in range(6)]))
    text(L, 350, 116, "VÉSPER-7", "#e0e4f4", size=16)
    text(L, 452, 150, "GN-04", "#5c6084")
    # contêineres frios empilhados na plataforma (o container_sealed do jogo)
    cs = night(sprite("container_sealed.png"), (0.72, 0.76, 0.86))
    for (x, y) in [(60, 0), (100, 0), (140, 0), (80, -40), (120, -40), (100, -80), (170, 0)]:
        L.paste(cs, x, GROUND_Y - 44 + 2 + y)
    # guindaste de pórtico sobre a pilha
    part(L, lambda c: (c.rect(40, 100, 6, GROUND_Y - 100, HULL[3]), c.rect(210, 100, 6, GROUND_Y - 100, HULL[3]),
                       c.rect(36, 94, 186, 8, HULL[2]), c.hline(36, 94, 186, HULL[1]),
                       [c.line([(46 + i * 20, 102), (56 + i * 20, 94)], HULL[3]) for i in range(8)],
                       c.rect(38, 112, 10, 3, ORANGE[1]), c.rect(208, 112, 10, 3, ORANGE[1])))
    # holofotes (postes)
    for hx in (20, 260):
        part(L, lambda c, hx=hx: (c.rect(hx, 60, 4, GROUND_Y - 60, HULL[3]), c.rect(hx - 6, 54, 16, 8, HULL[2]),
                                  c.rect(hx - 4, 62, 12, 2, "#fffbe0")))
    L = night(L, (0.62, 0.66, 0.86))
    lights = [(22, 150, 90, 120, "#d6e6ff", 0.7), (262, 160, 90, 110, "#d6e6ff", 0.7), (370, 176, 80, 40, "#7fd0ea", 0.8)]
    L = light_bands(L, lights, levels=(0.1, 0.2, 0.3), dw=0.12)
    S.add("plataforma_nave", L, parallax=1.0,
          desc="plataforma, a VÉSPER-7 com a baía aberta, rampa, pilha de contêineres frios, pórtico e holofotes")

    # ---- 4: vapor frio saindo dos contêineres (tira 8 q.)
    frames = []
    for t in range(8):
        c = Cv(180, 60)
        for k in range(14):
            x0 = 10 + hash2(k, 1, 5) * 150
            ph = (t / 8 + hash2(k, 2, 5)) % 1
            y = 56 - ph * 50
            x = x0 + math.sin(ph * 6 + k) * 4
            r = 1 + int(ph * 3)
            col = "#7f93b6" if ph < 0.5 else "#5c6a90"
            if ph < 0.85:
                for dy2 in range(r):
                    for dx2 in range(r * 2):
                        if (dx2 + dy2 + k) % 2 == 0:
                            c.px(int(x) + dx2 - r, int(y) + dy2, col)
        frames.append(c)
    S.add("vapor_frio", frames, 50, GROUND_Y - 130, fps=6, desc="vapor gelado subindo da pilha (pontilhado)")

    # ---- 5: contêiner subindo a rampa no trenó (tira 12 q., loop)
    frames = []
    cn = night(sprite("container_sealed.png"), (0.45, 0.5, 0.62))
    for t in range(12):
        c = Cv(140, 90)
        u = t / 12
        x = int(0 + u * 96)
        y = int(54 - u * 54)
        c.rect(x - 2, y + 40, 46, 4, HULL[3])
        c.hline(x - 2, y + 40, 46, HULL[2])
        c.px(x, y + 44, CYAN if t % 2 else "#2f6f96")
        c.px(x + 40, y + 44, CYAN if t % 2 else "#2f6f96")
        c.paste(cn, x + 1, y - 2)
        frames.append(c)
    S.add("conteiner_rampa", frames, 222, GROUND_Y - 88, fps=4,
          desc="um contêiner num trenó flutuante subindo a rampa (loop de 12 q.)")

    # ---- 6: tripulantes (tira 4 q. cada, andando)
    S.add("tripulante_a", [night(crew(t), (0.8, 0.82, 1.0)) for t in range(4)], 290, GROUND_Y - 18, fps=6,
          move="anda pra esquerda ~8 px/s (x 290 → 200)", desc="tripulante com lanterna, andando")
    S.add("tripulante_b", [night(crew((t + 2) % 4, carry=True), (0.8, 0.82, 1.0)) for t in range(4)], 200,
          GROUND_Y - 18, fps=6, move="anda pra direita (espelhar) ~6 px/s", desc="tripulante carregando um painel")
    S.add("tripulante_c", [night(crew(0, lamp=True), (0.7, 0.72, 0.9))], 344, 168, parallax=1.0,
          desc="tripulante parado na boca da baía, olhando a carga")

    # ---- 7: luz vermelha da antena (tira 4 q.) e holofote falhando (tira 8 q.)
    S.add("antena_luz", [Cv(4, 4), (lambda c: (c.rect(0, 0, 4, 4, "#ff6a55"), c.rect(1, 1, 2, 2, "#ffd0c8"), c)[2])(Cv(4, 4)),
                         Cv(4, 4), Cv(4, 4)], 419, 66, fps=2, desc="luz vermelha no topo da antena")
    frames = []
    for t in range(8):
        c = Cv(140, 190)
        if [1, 1, 1, 0, 1, 0, 1, 1][t]:
            cone = Cv(140, 190)
            cone.poly([(64, 4), (76, 4), (130, 186), (10, 186)], "#3a3f6a")
            a2 = cone.arr()
            yy2, xx2 = np.mgrid[0:190, 0:140]
            a2[((xx2 + yy2) % 2 == 1)] = 0
            a2[(yy2 > 100) & ((xx2 + yy2 // 2) % 3 != 0)] = 0
            cone.set_arr(a2)
            c.paste(cone)
            c.rect(62, 0, 16, 4, "#fffbe0")
        frames.append(c)
    S.add("holofote", frames, 194, 56, fps=8, desc="o holofote do meio falha (cone pontilhado)")

    # ---- 8: neve na frente (tira 8 q.)
    fr = [particles(CW, CH, 120, 61, t, 8, drift=0.5, cols=("#d6e6ff", "#8a9ccf"), big=0.2) for t in range(8)]
    S.add("neve", fr, fps=8, parallax=1.5, desc="neve/poeira fria caindo na frente de tudo")
    return S


# =================================================================================================================
# CENA 5 · Terminal da última mensagem (Dia 230): sala vazia, derretedor desligado ao fundo
# =================================================================================================================
MSG = ["TERMINAL · MODULO DA COLONIA", "", "> DIA 230", "> ULTIMA MENSAGEM DA COLONIA HESPER.",
       "> DESLIGAMOS OS DERRETEDORES. TODOS.", "> SE ALGUEM ACHAR ISTO:", "", "> O PLANETA NAO ESTA MORTO.",
       "> ELE ESTA ESPERANDO.", "", "> NAO ACORDE O GELO."]


def char_stops(s, size=8):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONT_DIR / "Silkscreen-Regular.ttf"), size)
    return [int(round(f.getlength(s[:i + 1]))) for i in range(len(s))]


def scene5():
    S = Scene("cena5", "terminal", "Terminal da última mensagem · Dia 230",
              "Começa no plano aberto (sala vazia, derretedor apagado ao fundo) e faz zoom lento até a tela "
              "(1.0 → 1.35, ancorado no meio da tela). As linhas aparecem letra por letra (cenas.json traz o x de "
              "cada letra), o cursor pisca. A última linha entra depois de uma pausa. Sem música.", duration="10 s")
    FY = 238
    sx0, sy0, sw, sh = 46, 52, 236, 140         # a tela
    room = Cv(CW, CH, NIGHT[1])
    room.rect(0, 0, CW, 20, NIGHT[0])
    room.rect(0, 20, CW, 5, NIGHT[3])
    room.hline(0, 20, CW, NIGHT[4])
    for x in range(0, CW, 56):
        room.vline(x, 25, FY - 25, NIGHT[0])
        room.vline(x + 1, 25, FY - 25, NIGHT[2])
    # janela ao fundo (direita)
    wx, wy, ww, wh = 330, 54, 140, 84
    room.rect(wx - 6, wy - 6, ww + 12, wh + 12, NIGHT[4])
    room.rect(wx - 3, wy - 3, ww + 6, wh + 6, NIGHT[0])
    a = room.arr()
    a[wy:wy + wh, wx:wx + ww] = 0
    room.set_arr(a)
    room.rect(wx + ww // 2 - 1, wy, 3, wh, NIGHT[3])
    # chão
    room.rect(0, FY, CW, CH - FY, NIGHT[0])
    room.hline(0, FY, CW, NIGHT[3])
    for y in range(FY + 5, CH, 7):
        room.hline(0, y, CW, NIGHT[1])
    # cadeira vazia virada
    part(room, lambda c: (c.rect(300, 196, 30, 6, "#2c2d4e"), c.rect(326, 166, 6, 36, "#2c2d4e"),
                          c.rect(312, 202, 4, 24, "#1f1f3a"), c.poly([(298, 232), (330, 232), (322, 226), (306, 226)],
                                                                      "#1f1f3a")))
    # mesa do terminal
    part(room, lambda c: (c.rect(10, 214, 300, 8, "#2e2f50"), c.hline(10, 214, 300, "#45486e"),
                          c.rect(20, 222, 8, FY - 222, "#1f1f3a"), c.rect(290, 222, 8, FY - 222, "#1f1f3a")))
    # derretedor desligado ao fundo (o sprite do jogo, apagado)
    mel = sprite("machine_melter.png")
    ma = mel.arr().astype(float)
    sel = ma[:, :, 3] > 0
    ma[sel, :3] *= np.array([0.3, 0.33, 0.48])
    mel.set_arr(np.round(ma))
    room.paste(mel, 420, FY - 54)
    room.paste(mel, 372, FY - 50)
    # caneca e papéis na mesa
    part(room, lambda c: (c.rect(250, 204, 8, 10, WHITE[3]), c.vline(258, 206, 5, WHITE[3]),
                          c.poly([(190, 212), (226, 210), (230, 214), (192, 214)], "#5a6086")))
    # monitor (carcaça)
    def mon(c):
        c.rect(sx0 - 14, sy0 - 14, sw + 28, sh + 28, "#38395c")
        c.hline(sx0 - 14, sy0 - 14, sw + 28, "#4e5078")
        c.rect(sx0 - 14, sy0 + sh + 6, sw + 28, 8, "#2a2b48")
        c.rect(sx0 - 4, sy0 - 4, sw + 8, sh + 8, "#141426")
        c.rect(sx0 + sw // 2 - 20, sy0 + sh + 14, 40, 8, "#2a2b48")
        c.rect(sx0 + sw - 20, sy0 + sh + 8, 4, 2, "#7fd67a")             # LED de ligado
        c.rect(sx0 + 4, sy0 + sh + 8, 20, 2, ORANGE[2])
        text(c, sx0 + 30, sy0 + sh + 5, "HESPER", "#5c6084")
    part(room, mon)
    a = room.arr()
    a[sy0:sy0 + sh, sx0:sx0 + sw] = 0                                    # a tela entra em camada
    room.set_arr(a)
    room = light_bands(room, [(sx0 + sw / 2, sy0 + sh / 2 + 30, 240, 170, "#7fd67a", 0.75),
                              (wx + ww / 2, wy + wh, 120, 120, "#7f93d6", 0.5)], levels=(0.08, 0.16, 0.26), dw=0.1)
    # recoloca a tela vazada (o light_bands não mexe em transparente, então só garante)
    S_room = room

    # ---- 0: lá fora + neve
    out = Cv(CW, CH)
    out.paste(sky(ww, wh, seed=14, moon=None), wx, wy)
    out.paste(ridge(ww, wh, 50, ["#2a3156", "#222846", "#1b2038"], seed=41, rough=10, scale=30), wx, wy)
    S.add("fora", out, parallax=0.3, desc="noite lá fora (só pela janela)")
    S.add("neve_janela", [particles(ww, wh, 50, 71, t, 8, drift=0.6, cols=("#d6e6ff", "#8a9ccf")) for t in range(8)],
          wx, wy, fps=8, parallax=0.4, desc="neve na janela")

    # ---- 2: tela (fundo verde-escuro com scanlines e vinheta)
    scr = Cv(sw, sh, GREEN[4])
    for y in range(0, sh, 2):
        scr.hline(0, y, sw, "#0c1f16")
    for (r, col) in [(0, "#0a1812"), (1, "#0a1812"), (2, "#0c1f16")]:
        scr.rect(r, r, sw - 2 * r, 1, col)
        scr.rect(r, sh - 1 - r, sw - 2 * r, 1, col)
        scr.vline(r, r, sh - 2 * r, col)
        scr.vline(sw - 1 - r, r, sh - 2 * r, col)
    S.add("tela_fundo", scr, sx0, sy0, desc="fundo da tela: verde escuro com scanline")
    S.add("sala", S_room, desc="sala vazia: mesa, monitor (tela vazada), cadeira, janela, 2 derretedores apagados")

    # ---- 3..: as linhas do texto (uma camada por linha, pra digitar)
    tx, ty = sx0 + 8, sy0 + 8
    for i, line in enumerate(MSG):
        if not line:
            continue
        c = Cv(sw - 12, 10)
        col = GREEN[2] if i == 0 else (GREEN[0] if i == len(MSG) - 1 else GREEN[1])
        text(c, 0, 0, line, col)
        S.add(f"linha_{i:02d}", c, tx, ty + i * 11, desc=f"\"{line}\"")
        S.layers[-1]["type"] = dict(text=line, char_x=char_stops(line))
    # ---- cursor (2 q.)
    last = MSG[-1]
    cxp = tx + char_stops(last)[-1] + 2
    cur = [Cv(5, 8), Cv(5, 8)]
    cur[0].rect(0, 0, 5, 8, GREEN[1])
    S.add("cursor", cur, cxp, ty + (len(MSG) - 1) * 11, fps=2,
          desc="cursor piscando (move pro fim da linha que está sendo digitada; y = linha × 11)")
    # ---- brilho/rolagem da tela (tira 6 q.: uma faixa clara desce)
    frames = []
    for t in range(6):
        c = Cv(sw, sh)
        y0 = int(t / 6 * sh)
        for y in range(y0, min(sh, y0 + 6)):
            for x in range(0, sw, 2):
                c.px(x + (y % 2), y, "#1f4a34")
        frames.append(c)
    S.add("tela_varredura", frames, sx0, sy0, fps=6, desc="faixa de varredura descendo (pontilhada), por cima do texto")
    # ---- poeira na luz da tela
    fr = [particles(260, 200, 30, 91, t, 8, drift=0.2, cols=("#3f8f56", "#7fd67a"), big=0.0) for t in range(8)]
    S.add("poeira", fr, 30, 40, fps=3, parallax=1.2, desc="poeira na luz verde")
    return S


# =================================================================================================================
# CENA 6 · O gelo gigante (a criatura em C dentro) + 6b close no gelo
# =================================================================================================================
# Qual forma da criatura usar (pendentes da Designer, reports/design/gelo_gigante/pendentes/). O dono ainda não
# escolheu: "cocoon" é a recomendada; pra trocar, rode com HESPER_CRIATURA=larva (ou embryo / fetal).
import os  # noqa: E402
CREATURE = os.environ.get("HESPER_CRIATURA", "cocoon")
GIANT_W, GIANT_H, GIANT_OX, GIANT_OY = 256, 220, 120, 216
ROCK = ["#141322", "#1c1a2c", "#25233a", "#2f2d48", "#3b3a58"]


def giant_frames():
    im = Image.open(GELO / f"form_ice_giant_{CREATURE}_anim.png")
    idx = np.array(im)
    rgba = np.array(im.convert("RGBA"))
    rgba[idx == 9] = rgb("#0e0d1c")            # sombra semitransparente do jogo vira sombra chapada (a cena é escura)
    rgba[:, :, 3] = np.where(idx == 255, 0, 255)
    n = im.width // GIANT_W
    out = []
    for i in range(n):
        c = Cv(GIANT_W, GIANT_H)
        c.set_arr(rgba[:, i * GIANT_W:(i + 1) * GIANT_W].copy())
        out.append(c)
    return out


def rock_mass(w, h, seed, top_fn, ramp, strata=7):
    """Rocha da caverna: massa irregular com estratos horizontais e fissuras (nada de junta vertical regular)."""
    cv = Cv(w, h)
    n = fbm(w, h, 26, seed, 3)
    a = np.zeros((h, w, 4), np.uint8)
    for x in range(w):
        y0 = int(top_fn(x))
        for y in range(max(0, y0), h):
            depth = y - y0
            band = int((y + n[y, x] * 10) // strata) % 3
            k = 3 if depth < 2 else (2 if band == 0 else 1)
            if n[y, x] > 0.62:
                k = min(k + 1, len(ramp) - 1)
            if n[y, x] < 0.24:
                k = 0
            a[y, x] = rgb(ramp[k])
    cv.set_arr(a)
    return cv


def scene6():
    S = Scene("cena6", "gelo_gigante", f"O gelo gigante · forma: {CREATURE}",
              "Plano parado, zoom lento pra dentro (1.0 → 1.15) ancorado na criatura. O brilho frio passa pelo gelo "
              "(tira do jogo, 8 q.), cristais flutuam. Termina cortando pro close 6b.", duration="5 s")
    FY = 252
    # ---- 0: fundo da caverna
    bg = Cv(CW, CH, ROCK[0])
    back = rock_mass(CW, CH, 51, lambda x: 20 + 30 * math.sin(x / 60) + 14 * math.sin(x / 23),
                     [ROCK[0], ROCK[1], ROCK[1], ROCK[2], ROCK[3]], strata=9)
    bg.paste(back)
    bg = light_bands(bg, [(256, 170, 220, 150, "#59d0e6", 1.0)], levels=(0.06, 0.12, 0.18), dw=0.06)
    bg.rect(0, 0, CW, 10, ROCK[0])
    # estalactites
    for k in range(14):
        x = int(hash2(k, 1, 4) * CW)
        L = 8 + int(hash2(k, 2, 4) * 28)
        bg.poly([(x - 4, 0), (x + 4, 0), (x, L)], ROCK[2])
        bg.line([(x - 3, 0), (x, L - 2)], ROCK[3])
    S.add("caverna_fundo", bg, parallax=0.5, desc="parede do fundo: rocha em estratos e estalactites")

    # ---- 1: chão de gelo e geada + paredes laterais
    fl = Cv(CW, CH)
    edge_n = fbm(CW, 1, 30, 9, 2)[0]
    for x in range(CW):
        top = int(FY - 14 + (edge_n[x] - 0.5) * 12)
        fl.vline(x, top, CH - top, "#24314f")
        fl.vline(x, top, 2, "#3d5b80")
    for k in range(60):
        x, y = int(hash2(k, 1, 7) * CW), int(FY - 8 + hash2(k, 2, 7) * 40)
        fl.hline(x, y, 2 + int(hash2(k, 3, 7) * 6), "#3d5b80")
    SIDE = [ROCK[0], ROCK[0], ROCK[1], ROCK[2], ROCK[3]]
    left = rock_mass(140, CH, 61, lambda x: 40 + (x / 140) ** 2 * 260, SIDE)
    right = rock_mass(150, CH, 62, lambda x: 40 + ((150 - x) / 150) ** 2 * 250, SIDE)
    fl.paste(left, 0, 0)
    fl.paste(right, CW - 150, 0)
    fl = light_bands(fl, [(256, 200, 240, 120, "#7fd0ea", 1.0)], levels=(0.08, 0.16, 0.24), dw=0.06)
    S.add("chao_paredes", fl, parallax=1.0, desc="chão de gelo, geada e as paredes de rocha iluminadas pelo gelo")

    # ---- 2: o gelo gigante (tira do jogo, 8 q.)
    gf = giant_frames()
    gx, gy = CW // 2 - GIANT_OX + 8, FY + 6 - GIANT_OY
    S.add("gelo_gigante", gf, gx, gy, fps=4, parallax=1.0,
          desc=f"form_ice_giant_{CREATURE}_anim.png (pendente): respira e o brilho frio passa")
    S.layers[-1]["source"] = f"reports/design/gelo_gigante/pendentes/form_ice_giant_{CREATURE}_anim.png"

    # ---- 3: cristais suspensos
    fr = [particles(CW, 220, 40, 81, t, 16, drift=-0.15, cols=("#a6ecff", "#59d0e6", "#eef6ff"), big=0.1)
          for t in range(16)]
    S.add("cristais_no_ar", fr, 0, 0, fps=4, parallax=1.2, desc="poeira de gelo flutuando (loop 16 q.)")

    # ---- 4: rochas em primeiro plano
    fg = Cv(CW, CH)
    fg.poly([(0, 200), (30, 214), (70, 250), (90, 288), (0, 288)], ROCK[0])
    fg.poly([(0, 210), (24, 222), (56, 254), (66, 288), (0, 288)], "#08070f")
    fg.poly([(512, 180), (476, 220), (450, 288), (512, 288)], ROCK[0])
    fg.poly([(512, 196), (486, 230), (468, 288), (512, 288)], "#08070f")
    fg.poly([(150, 288), (180, 270), (240, 266), (270, 288)], "#08070f")
    S.add("rochas_frente", fg, parallax=1.5, desc="silhuetas de rocha na frente (parallax forte)")
    return S


def scene6b():
    S = Scene("cena6b", "close_gelo", "Close: a coisa dentro do gelo",
              "Zoom bem lento pra dentro (1.0 → 1.1). O brilho frio atravessa o gelo em diagonal (tira 12 q.). "
              "A criatura quase não mexe: no último quadro ela se contrai uma vez (q. 7 da tira dela). Corte pro "
              "preto + \"NÃO ACORDE O GELO\".", duration="4 s")
    # ---- 0: o gelo (células grandes, faixas fundas)
    a, pts, edge = voronoi_field(CW, CH, 18, 13, ["#1f4a6e", "#24547a", "#2f6f96", "#3a80a6", "#4592b8"])
    g = Cv(CW, CH)
    g.set_arr(a)
    for k in range(40):
        bx, by = int(hash2(k, 7, 19) * CW), int(hash2(k, 8, 19) * CH)
        r = 1 + int(hash2(k, 9, 19) * 3)
        g.ell(bx - r, by - r, bx + r, by + r, "#7fd0ea")
        g.px(bx - r // 2, by - r // 2, "#eef6ff")
    S.add("gelo", g, parallax=0.8, desc="o interior do gelo: células grandes em faixas, bolhas")

    # ---- 1: a criatura (tira 8 q.: respira devagar; q. 7 = contração)
    from trailer_lib import BAYER4
    frames = []
    yy, xx = np.mgrid[0:CH, 0:CW]
    bb = BAYER4[yy % 4, xx % 4]
    for t in range(8):
        c, um = creature_big(262, 148, t, contract=1.0 if t == 7 else 0.0)
        ar = c.arr()
        # véu de gelo: quanto mais fundo (cauda), mais pontilhado da cor do gelo por cima
        dens = np.where(um < 0, 0, 0.12 + 0.3 * np.clip(um, 0, 1))
        veil = (ar[:, :, 3] > 0) & (bb < dens)
        ar[veil] = rgb("#2f6f96")
        c.set_arr(ar)
        frames.append(c)
    S.add("criatura", frames, fps=2, parallax=0.8,
          desc="a criatura em C, enorme, vista através do gelo (pontilhado = gelo na frente); q. 7 se contrai")

    # ---- 2: rachaduras e geada na superfície (mais perto que a criatura)
    cr = Cv(CW, CH)
    for k in range(5):
        x, y = hash2(k, 11, 23) * CW, hash2(k, 12, 23) * CH
        pp = [(x, y)]
        for j in range(5):
            x += (hash2(k, j, 41) - 0.5) * 10 + 14
            y += (hash2(k, j, 42) - 0.5) * 14 + 4
            pp.append((x, y))
        cr.line(pp, "#a6ecff")
        cr.line([(px + 1, py + 1) for px, py in pp], "#1f4a6e")
    for x in range(CW):                                     # geada nas bordas de cima/baixo
        h1 = int(6 + fbm(CW, 1, 14, 3, 2)[0][x] * 16)
        for y in range(h1):
            if (x + y) % 2 == 0 or y < h1 // 2:
                cr.px(x, y, "#d4f6ff" if y < h1 // 2 else "#7fd0ea")
            if (x + y) % 2 == 0 or y < h1 // 3:
                cr.px(x, CH - 1 - y, "#7fd0ea" if y < h1 // 3 else "#4fa0c6")
    S.add("superficie", cr, parallax=1.0, desc="rachaduras e geada na superfície do gelo")

    # ---- 3: brilho frio passando (tira 12 q.: faixa diagonal da esquerda pra direita)
    frames = []
    yy, xx = np.mgrid[0:CH, 0:CW]
    for t in range(12):
        c = Cv(CW, CH)
        pos = -200 + t / 12 * (CW + 400)
        d = (xx + yy * 0.6) - pos
        ar = np.zeros((CH, CW, 4), np.uint8)
        core = np.abs(d) < 6
        edge = (np.abs(d) < 18) & ((xx + yy) % 2 == 0)
        far = (np.abs(d) < 34) & ((xx % 2 == 0) & (yy % 2 == 0))
        ar[far] = rgb("#7fd0ea")
        ar[edge] = rgb("#a6ecff")
        ar[core] = rgb("#eef6ff")
        c.set_arr(ar)
        frames.append(c)
    S.add("brilho_frio", frames, fps=6, parallax=1.0, desc="o brilho frio passando em diagonal (faixas + pontilhado)")
    return S


# =================================================================================================================
# personagem: a Dra. Ilves sozinha (luz neutra) + folha
# =================================================================================================================
def character_sheet():
    d = OUT / "personagem"
    d.mkdir(parents=True, exist_ok=True)
    items = [
        ("ilves_perfil", C.stand_cycle(12),
         "em pé de perfil (64×120, pé na linha 117): 12 q., respira no ombro, pisca nos q. 7-9"),
        ("ilves_sentada_microscopio", C.sit_cycle(12, light=(-1, -1)),
         "sentada e curvada na ocular (84×96, chão na linha 93): 12 q., respiração, rosto chegando na ocular, "
         "mão girando o foco, coque/jaleco atrasando, piscada"),
        ("ilves_costas_fechadura", C.back_cycle(12, light=(-1, -1)),
         "de costas com a mão na fechadura (72×120, pé na linha 117): 12 q., respiração e a cabeça pesando"),
        ("ilves_busto", C.bust_cycle(12, light=(-1, -1)),
         "busto de perfil pros closes (200×200), concentrada: 12 q., respiração, micro-sacada, piscada nos q. 7-9"),
        ("ilves_busto_reacao", C.bust_reaction(10, light=(-1, -1)),
         "busto · medo contido (10 q., sem loop): afasta da ocular, olhos abrem, sobrancelha sobe, boca entreabre"),
    ]
    meta = []
    for name, frames, desc in items:
        save(frames[0].im, d / f"{name}.png")
        save(strip(frames).im, d / f"{name}_anim.png")
        meta.append(dict(name=name, file=f"personagem/{name}.png", anim=f"personagem/{name}_anim.png",
                         w=frames[0].w, h=frames[0].h, frames=len(frames), desc=desc))
    # folha: as 4 poses lado a lado sobre o fundo da noite
    sheet = Cv(480, 210, NIGHT[1])
    x = 8
    for name, frames, desc in items[:3]:
        sheet.paste(frames[0], x, 210 - frames[0].h - 6)
        x += frames[0].w + 4
    sheet.paste(items[3][1][0], 480 - 200, 10)
    text(sheet, 10, 8, "DRA. ILVES", "#e0e4f4")
    text(sheet, 10, 20, "CIENTISTA · COLONIA HESPER", "#7fd0ea")
    save(sheet.im, d / "folha_ilves.png")
    return meta


# =================================================================================================================
# report (index.html)
# =================================================================================================================
def html_report(doc):
    css_anims = []
    k = 0

    def sprite_html(file, w, h, frames, fps, scale):
        nonlocal k
        k += 1
        W, H = round(w * scale), round(h * scale)
        if frames <= 1:
            return f'<div class="chk"><img src="{file}" style="width:{W}px;height:{H}px"></div>'
        dur = frames / max(1, fps or 4)
        css_anims.append(f"@keyframes a{k}{{from{{background-position:0 0}}to{{background-position:-{W * frames}px 0}}}}"
                         f".s{k}{{width:{W}px;height:{H}px;background:url('{file}') 0 0/{W * frames}px {H}px;"
                         f"image-rendering:pixelated;animation:a{k} {dur:.2f}s steps({frames}) infinite}}")
        return f'<div class="chk"><div class="s{k}"></div></div>'

    def esc(t):
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sec = []
    for sc in doc["scenes"]:
        rows = []
        for L in sc["layers"]:
            sc_ = 0.5 if L["w"] > 300 else (1 if L["w"] > 120 else 3)
            extra = ""
            if "type" in L:
                extra = "<br><small>digitar: char_x no cenas.json</small>"
            rows.append(
                f"<tr><td>{L['order']}</td><td><code>{esc(L['file'])}</code><br><small>{esc(L['desc'])}</small>"
                f"{extra}</td><td>{L['x']}, {L['y']}</td><td>{L['w']}×{L['h']}</td>"
                f"<td>{L['frames']}{'' if L['frames'] == 1 else ' @ ' + str(L['fps']) + ' fps'}"
                f"{'' if L['loop'] else ' · sem loop'}</td><td>{L['parallax']}</td>"
                f"<td>{sprite_html(L['file'], L['w'], L['h'], L['frames'], L['fps'], sc_)}</td></tr>")
        sec.append(f"""
<section id="{sc['id']}">
<h2>{esc(sc['title'])} <small>({sc['id']} · {esc(sc['duration'])})</small></h2>
<img class="prev" src="preview/{sc['id']}.gif" width="960" height="540" alt="{sc['id']}">
<p class="mov"><b>Movimento sugerido:</b> {esc(sc['motion'])}</p>
<details><summary>Camadas ({len(sc['layers'])}) · ordem de desenho, de trás pra frente</summary>
<table><tr><th>#</th><th>arquivo</th><th>x, y</th><th>tamanho</th><th>quadros</th><th>parallax</th><th>prévia</th></tr>
{''.join(rows)}</table></details>
</section>""")
    chars = []
    for c in doc["character"]:
        sc_ = 1 if c["w"] > 100 else 3
        chars.append(f"<div class='card'>{sprite_html(c['anim'], c['w'], c['h'], c['frames'], 3, sc_)}"
                     f"<p><code>{c['file']}</code><br><small>{esc(c['desc'])}</small></p></div>")
    nav = " · ".join(f"<a href='#{sc['id']}'>{sc['id']}</a>" for sc in doc["scenes"])
    html = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Hesper · trailer · cutscenes da Dra. Ilves</title>
<style>
body{{background:#14131f;color:#d6d3e6;font:15px/1.5 system-ui,sans-serif;max-width:1180px;margin:0 auto;padding:24px}}
h1{{color:#f2c46d}} h2{{color:#a6ecff;margin-top:48px}} h2 small{{color:#7b7896;font-weight:normal}}
a{{color:#e2733a}} code{{color:#f4a06a}} small{{color:#9c99b4}}
.note{{background:#1f1d33;border-left:4px solid #e2733a;padding:12px 16px;margin:16px 0}}
img,.chk div{{image-rendering:pixelated}}
.prev{{display:block;border:2px solid #2b2840;background:#000;max-width:100%;height:auto}}
.chk{{display:inline-block;background:conic-gradient(#2a2838 25%,#34324a 0 50%,#2a2838 0 75%,#34324a 0) 0 0/16px 16px}}
.chk img{{display:block}}
table{{border-collapse:collapse;width:100%;margin-top:8px}} td,th{{border-bottom:1px solid #2b2840;padding:6px;text-align:left;vertical-align:top}}
.mov{{background:#1b1a2b;padding:8px 12px}}
.ba img{{max-width:100%;height:auto;image-rendering:pixelated;background:#000}}
.cards{{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end}} .card p{{max-width:260px}}
{''.join(css_anims)}
</style></head><body>
<h1>Hesper · trailer 1:30 · cutscenes da Dra. Ilves</h1>
<div class="note"><b>v1.1 · a Dra. Ilves mais humana</b> (feedback do dono). Personagem refeita do zero
(<code>tools/sprites/trailer_ilves_char.py</code>): silhueta de <b>curvas</b> (Catmull-Rom) em vez de blocos, ombros
caídos, costas arqueando no microscópio, caimento do jaleco; proporção humana (cabeça ~1/7 da altura, pescoço que não
é caixa); sombreamento que <b>segue a forma</b>; <b>antialias manual</b> nos cantos do contorno. Animação: <b>12
quadros</b> (antes 4-6) com <b>easing</b>, respiração no ombro, <b>movimento secundário</b> (coque, mecha solta e
barra do jaleco atrasam o corpo) e piscada natural (meio → fechado → meio). Close com feição (pálpebra, íris,
sobrancelha, nariz, lábios): loop de <b>concentração</b> + uma tira nova de <b>medo contido</b> (10 q., sem loop).
Insert da chave refeito: punho fechado, polegar apertando o anel, indicador por trás, giro de 45° em 12 q. com
antecipação e assentamento, manga atrasando. Rosto do wide da cena 1 agora pega a luz da lâmina.
<a href="#antes">antes × depois</a></div>
<div class="note"><b>v1.0 · primeira versão.</b> 6 cenas pedidas + 3 inserts (1b close do rosto, 3b a chave, 6b close no
gelo), a Dra. Ilves (perfil, sentada, de costas e busto) e o <code>cenas.json</code> pro vídeo. Tudo em pixel art 1:1 no
estilo do jogo (contorno <code>#1b1630</code>, luz em faixas com dither só na borda, alpha 0/255), quadros 16:9 de
480×270 pra ampliar ×4 sem suavizar. Sem referência externa: tudo original, derivado do próprio jogo (paleta da
bíblia, o <code>container_sealed</code> e o <code>machine_melter</code> do jogo reaproveitados, a criatura das pendentes
do gelo gigante).</div>
<div class="note"><b>Criatura da cena 6:</b> usa a forma <code>{CREATURE}</code> das pendentes (a recomendada). O dono
ainda não escolheu; pra trocar: <code>HESPER_CRIATURA=larva python3 tools/sprites/trailer_ilves.py</code>
(ou <code>embryo</code>, <code>fetal</code>). O close 6b é desenho próprio da criatura em C, feito pra combinar com
qualquer uma das formas.</div>
<p>{nav} · <a href="#ilves">a Dra. Ilves</a> · <a href="#editor">pro editor do vídeo</a></p>
<section id="antes"><h2>Antes × depois (v1.0 → v1.1)</h2>
<table class="ba"><tr><th>antes (v1.0)</th><th>depois (v1.1)</th></tr>
<tr><td><img src="before/folha_ilves.png" width="480"></td><td><img src="personagem/folha_ilves.png" width="480"></td></tr>
<tr><td><img src="before/cena1.gif" width="480"></td><td><img src="preview/cena1.gif" width="480"></td></tr>
<tr><td><img src="before/cena1b.gif" width="480"></td><td><img src="preview/cena1b.gif" width="480"><br>
<img src="preview/cena1b_alt.gif" width="480"><br><small>nova: a reação (medo contido), camada 04 no lugar da 01</small></td></tr>
<tr><td><img src="before/cena3.gif" width="480"></td><td><img src="preview/cena3.gif" width="480"></td></tr>
<tr><td><img src="before/cena3b.gif" width="480"></td><td><img src="preview/cena3b.gif" width="480"></td></tr>
</table></section>
{''.join(sec)}
<section id="ilves"><h2>A Dra. Ilves</h2>
<p>Cientista da colônia: cabelo escuro num coque com prendedor laranja, óculos de aro fino (o reflexo das lentes é o
"olho" dela nas cenas escuras), jaleco branco aberto por cima do macacão azul-acinzentado da colônia, gola e punhos
laranja <code>#e2733a</code>, crachá com LED ciano, botas escuras. Mesma família do Explorador (cabeça grande,
contorno por peça, sombreamento em faixas), mas sem capacete: é a única pessoa de rosto à mostra no jogo.
Aqui na luz neutra; em cada cena ela é re-iluminada (tinta da noite + luz de recorte da fonte da cena).</p>
<img src="personagem/folha_ilves.png" width="960" style="max-width:100%;height:auto">
<div class="cards">{''.join(chars)}</div></section>
<section id="editor"><h2>Pro editor do vídeo</h2>
<ul>
<li><b>Canvas 512×288</b> por cena; o quadro visível é o recorte <code>(16, 9, 480, 270)</code>. A folga de 16/9 px dá
pan e parallax sem mostrar borda. Amplie ×4 com <b>nearest neighbor</b> (480×270 → 1920×1080).</li>
<li><b>Ordem de desenho</b> = o número no começo do arquivo (00 é o fundo). Posição (x, y) e tudo mais no
<code>cenas.json</code>.</li>
<li><b>Tiras</b>: quadros lado a lado na horizontal, cada um com o w×h da camada. <code>fps</code> sugerido;
<code>loop: false</code> = toca uma vez e para no último quadro (LED e chave).</li>
<li><b>Parallax</b>: 1.0 anda junto com o cenário; &lt;1 fica pra trás (céu, serra), &gt;1 é primeiro plano.</li>
<li>Pra não borrar o pixel art: mexa as camadas em <b>pixel inteiro do canvas</b> (= passos de 4 px no 1080p). Zoom
lento: o ideal é fazer no 1080p já ampliado.</li>
<li><b>Camada alternativa</b> (<code>replaces</code> no json): a <code>04_ilves_reacao</code> da cena 1b entra
no lugar da <code>01_ilves_busto</code> (mesma posição, desenha na ordem 1, embaixo da ocular). Prévia em
<code>preview/cena1b_alt.gif</code>.</li>
<li><b>Mudou no v1.1</b> (cenas 1, 1b, 3, 3b): mesmos nomes de arquivo; número de quadros, fps, posições e tamanhos
das camadas da Ilves mudaram (está tudo no <code>cenas.json</code>). A cena 3 ganhou porta mais alta e a fechadura
subiu pra altura da mão dela; na 3b o buraco da fechadura subiu 26 px.</li>
<li><b>Cena 5 (texto)</b>: cada linha é uma camada; <code>type.char_x</code> traz o x (em px, a partir do começo da
linha) do fim de cada letra pra revelar letra por letra com uma máscara. O cursor anda pro fim da linha atual.</li>
<li>Tudo sai de <code>tools/sprites/trailer_ilves.py</code> (determinístico).</li>
</ul></section>
</body></html>"""
    (OUT / "index.html").write_text(html)


SCENES = [scene1, scene1b, scene2, scene3, scene3b, scene4, scene5, scene6, scene6b]


def preview(S, n=16, alt=False):
    if not alt and any("replaces" in L for L in S.layers):
        preview(S, n, alt=True)
    frames = [S.compose(t, alt).crop((VX, VY, VX + VW, VY + VH)).convert("RGB") for t in range(n)]
    pdir = OUT / "preview"
    pdir.mkdir(parents=True, exist_ok=True)
    key = S.key + ("_alt" if alt else "")
    frames[0].save(pdir / f"{key}.png", optimize=True)
    big = [f.resize((VW * 2, VH * 2), Image.NEAREST).quantize(255, method=Image.Quantize.MEDIANCUT, dither=0)
           for f in frames]
    big[0].save(pdir / f"{key}.gif", save_all=True, append_images=big[1:], duration=1000 // S.base_fps, loop=0,
                optimize=False, disposal=1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[1:]
    metas = []
    for fn in SCENES:
        if only and fn.__name__ not in only:
            continue
        S = fn()
        preview(S)
        metas.append(S.meta())
    if not only:
        chars = character_sheet()
        doc = dict(
            about="Trailer do Hesper · cutscenes da Dra. Ilves. Gerado por tools/sprites/trailer_ilves.py.",
            format=dict(
                canvas=[CW, CH], visible=[VX, VY, VW, VH], scale="x4 nearest (480×270 → 1920×1080), sem suavizar",
                layers="lista em ordem de desenho (0 = fundo). x, y = posição do canto de cima-esquerda no canvas "
                       "512×288. Tiras: quadros de w×h lado a lado na horizontal; fps = velocidade sugerida; "
                       "loop=false para no último quadro. parallax = fator do pan (1.0 = anda junto com o cenário; "
                       "<1 mais longe, >1 primeiro plano).",
                pixel_art="alpha só 0/255; mover só em px inteiros (no canvas 512×288) pra não borrar",
                creature=f"cena6 usa form_ice_giant_{CREATURE}; pra trocar: HESPER_CRIATURA=larva python3 "
                         "tools/sprites/trailer_ilves.py"),
            order=["cena1", "cena1b", "cena2", "cena3", "cena3b", "cena4", "cena5", "cena6", "cena6b"],
            scenes=metas, character=chars)
        (OUT / "cenas.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        html_report(doc)


if __name__ == "__main__":
    main()
