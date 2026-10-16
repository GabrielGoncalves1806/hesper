#!/usr/bin/env python3
"""Hesper v0.7 M4 · rodada 2: candidatas A/B do contêiner arrombado (motor r3d, molde do chests_r3d), da escotilha de
saída e da luz de emergência menor. Rode DEPOIS do build_vesper_v07.py (a rodada 1 aprovada não é sobrescrita).

Saída: reports/design/v07_m4/pendentes/{vesper_container_broken,vesper_hatch,vesper_emergency_light}_{A,B}.png
       reports/design/v07_m4/sala_r2_{A,B}_{clara,escura}.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chests_r3d as CH  # noqa: E402
import build_vesper_v07 as V  # noqa: E402
from r3d import Pal  # noqa: E402

S, T, FACE_H = V.S, V.T, V.FACE_H
PEND, REP = V.PEND, V.REP
P_ICE = Pal(["#e4f6ff", "#bfe4f4", "#a6d4ea", "#7fb4d2", "#4f86a8"])
P_POOL = Pal(["#a6d4ea", "#8fc3dc", "#7fb4d2", "#7fb4d2", "#4f86a8"])


# ---------------------------------------------------------------------------------------------------------------------
# Contêiner arrombado (r3d): o mesmo case do container_sealed (hw 17, hd 8.5, corpo 13, tampa 5), por dentro estourado
# ---------------------------------------------------------------------------------------------------------------------
def broken(variant):
    hw, hd, body, lid, r = 17, 8.5, 13, 5, 2.6
    sc = CH.scene(40, 44, -hd - 1.5)
    zb = body
    spec = CH._spec()
    sc.rbox((0, 0, zb / 2), (hw, hd, zb / 2), r, CH.P_ROYAL, paint=spec, extra=(CH.P_SPEC,))
    sc.rbox((0, 0, zb), (hw + 0.45, hd + 0.45, 0.7), r + 0.45, CH.P_SILVER)                    # faixa da emenda
    sc.rbox((-hw - 0.9, -hd * 0.25, zb * 0.55), (0.9, 2.0, 1.1), 0.6, CH.P_SILVER)             # alça
    # cintas e selo arrancados: só os tocos (a esquerda cortada, a direita pendurada) e o selo dourado rachado
    sc.rbox((-hw * 0.62, -hd - 0.5, zb + 0.3), (1.0, 0.5, 1.6), 0.5, CH.P_SILVER)
    sc.rbox((hw * 0.78, -hd - 0.5, zb - 1.6), (1.0, 0.5, 2.4), 0.5, CH.P_SILVER)
    sc.rbox((-hw * 0.18 - 0.8, -hd - 0.5, zb - 3.8), (1.0, 0.5, 1.0), 0.5, CH.P_GOLD)
    # boca: miolo escuro com a geada na borda e um bloco de gelo dentro
    lz0 = zb + 0.85
    sc.box((-hw + 1.4, hw - 1.4), (-hd + 1.4, hd - 1.4), (zb, lz0 + 0.1), CH.P_DARK)
    for xr, yr in (((-hw + 1.4, hw - 5), (-hd + 1.4, -hd + 2.1)), ((-hw + 1.4, -hw + 2.1), (-hd + 1.4, hd - 3)),
                   ((hw - 2.1, hw - 1.4), (-hd + 2, hd - 1.4))):
        sc.box(xr, yr, (lz0 - 0.1, lz0 + 0.4), P_ICE)
    sc.box((-4, 2), (0, 3.5), (zb, lz0 + 0.8), P_ICE)
    # chapas da frente dobradas de dentro pra fora (giram na borda de cima da frente)
    flaps = ((-9.5, 4.2, 0.85), (5.5, 5.0, 1.25)) if variant == "A" else ((-6.0, 6.0, 1.05), (8.5, 3.2, 0.6))
    for cx, w2, ang in flaps:
        sc.rbox((cx, -hd + 0.3, zb + 3.0), (w2, 0.5, 3.0), 0.4, CH.P_ROYAL, paint=spec, extra=(CH.P_SPEC,),
                rot_x=ang, pivot=(cx, -hd + 0.3, zb))
    # a tampa (a mesma do lacrado: gomos em cima), só que estourada
    lid_c = (0, 0, lz0 + lid / 2)

    def parts(dz=0.0):
        out = [((0, 0, lz0 + lid / 2 + dz), (hw, hd, lid / 2), r, CH.P_ROYAL,
                lambda L, N: np.where(N[:, 2] > 0.85, 2, np.where(N @ CH._HV > 0.93, 1, 0)),
                (CH.P_SPEC, CH.P_ROYAL_IN))]
        m, g, ridges = 1.3, 1.3, 4
        wr = (2 * (hw - m) - (ridges - 1) * g) / ridges
        for i in range(ridges):
            cx = -hw + m + wr / 2 + i * (wr + g)
            out.append(((cx, 0, lz0 + lid + dz + 1.4), (wr / 2, hd - 1.0, 1.6), min(1.4, wr / 2 - 0.1), CH.P_ROYAL,
                        spec, (CH.P_SPEC,)))
        return out
    pivot = (0, hd, lz0)
    if variant == "A":                                 # tampa em pé, girada além da vertical pra trás: estourou pra cima
        def inside(L, N):
            return np.where(N[:, 2] < -0.85, 2, np.where(N @ CH._HV > 0.93, 1, 0))
        for k, (c, half, rr, pal, pnt, ex) in enumerate(parts()):
            sc.rbox(c, half, rr, pal, paint=inside if k == 0 else pnt, extra=ex if k else (CH.P_SPEC, CH.P_ROYAL_IN),
                    rot_x=-1.8, pivot=pivot)
    else:                                              # tampa arrancada: voa por cima da caixa, torta, com estilhaços
        dz = 9.5
        piv = (0, 0, lz0 + lid / 2 + dz)
        for c, half, rr, pal, pnt, ex in parts(dz):
            sc.rbox(c, half, rr, pal, paint=pnt, extra=ex, rot_x=-0.42, pivot=piv)
        for (x, y, z, hx, hz, a) in ((-hw - 1.5, -3, 4.5, 1.6, 1.1, 0.7), (hw + 1.2, -2, 6.5, 1.3, 1.0, -0.6),
                                     (-12, 5.5, zb + 5, 1.4, 1.0, 0.5)):
            sc.rbox((x, y, z), (hx, 0.8, hz), 0.5, CH.P_ROYAL, rot_x=a)
    # poça de gelo derretido na frente e fios escorrendo pela frente do corpo
    sc.box((-14, 14), (-hd - 3.2, -hd - 0.2), (0, 0.5), P_POOL)
    sc.box((-8, 7), (-hd - 3.8, -hd - 3), (0, 0.5), P_POOL)
    for x0, z1 in ((-6, 9.5), (1, 12.0), (10, 8.0)):
        sc.box((x0, x0 + 1.1), (-hd - 0.6, -hd - 0.2), (0.4, z1), P_ICE)
    return sc.render()


# ---------------------------------------------------------------------------------------------------------------------
# Escotilha de SAÍDA: tem que ler "luz do dia lá fora, sobe por aqui"
# ---------------------------------------------------------------------------------------------------------------------
DAY = dict(w="#fffbe6", y1="#fff0a8", y2="#ffd96a", y3="#e8b04a", sand="#e9b867", sand_d="#c98f4c", sand_l="#f6d98e")


def spill(f, cx, cy, rx, ry):
    """Mancha de luz quente no chão ao redor (xadrez de 2 níveis, sem antialias): só nos pixels de chapa."""
    for y in range(T):
        for x in range(T):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d < 1 and f.get(x, y)[:3] not in (V.rgb(V.OUT)[:3],):
                c = f.get(x, y)
                a = 0.5 if d < 0.5 else 0.28 if (x + y) % 2 == 0 else 0.0
                if a:
                    f.px(x, y, (int(c[0] + (255 - c[0]) * a), int(c[1] + (226 - c[1]) * a), int(c[2] + (140 - c[2]) * a * 0.5), 255))


def hatch(variant):
    f = V.hull_floor(0)
    if variant == "A":                                 # alçapão aberto: poço claro com escada e a tampa deitada no alto
        f.rect(4, 6, 27, 28, V.OUT)
        f.rect(5, 7, 26, 27, S["panel_d"])
        f.rect(6, 8, 25, 26, V.OUT)
        # o poço vira céu: degradê quente do centro pra borda
        for y in range(9, 26):
            for x in range(7, 25):
                d = max(abs(x - 15.5) / 9, abs(y - 17.5) / 8.5)
                f.px(x, y, DAY["w"] if d < .45 else DAY["y1"] if d < .7 else DAY["y2"] if d < .9 else DAY["y3"])
        # escada: dois montantes e degraus (silhueta escura contra a luz)
        for x in (11, 20):
            f.rect(x, 9, x + 1, 25, "#4a3a3a")
            f.px(x, 9, V.OUT)
        for y in (11, 14, 17, 20, 23):
            f.rect(13, y, 18, y, "#4a3a3a")
            f.rect(13, y + 1, 18, y + 1, "#8c6a44")
        # tampa aberta deitada acima do poço, com a dobradiça
        f.rect(4, 1, 27, 5, V.OUT)
        f.rect(5, 2, 26, 4, S["panel"])
        f.rect(5, 2, 26, 2, S["panel_l"])
        f.rect(5, 4, 26, 4, S["panel_d"])
        for x in (8, 23):
            f.px(x, 3, S["rivet"])
        # luz transbordando pelas quinas do poço e as setas "sobe"
        for x, y in ((4, 17), (27, 17), (15, 28), (16, 28)):
            f.px(x, y, DAY["y2"])
        spill(f, 15.5, 17.5, 18, 17)
        for x, y in ((16, 1), (15, 1)):
            f.px(x, y, V.OUT)
    else:                                              # rampa entreaberta vista de cima, deserto entrando pela fresta
        f.rect(2, 3, 29, 28, V.OUT)
        f.rect(3, 4, 28, 27, S["panel_d"])
        # fresta larga em baixo: areia ao sol, uma duna e grãos
        f.rect(3, 19, 28, 27, V.OUT)
        for y in range(20, 27):
            for x in range(4, 28):
                base = DAY["sand_l"] if y < 22 else DAY["sand"] if y < 25 else DAY["sand_d"]
                if (x * 3 + y * 5) % 11 == 0:
                    base = DAY["y1"]
                f.px(x, y, base)
        for x in range(4, 28):                          # duna ao fundo + clarão forte na borda de cima da fresta
            f.px(x, 20, DAY["w"])
            f.px(x, 23 - (1 if 9 < x < 20 else 0) + (1 if x > 22 else 0), DAY["sand_d"])
        # a rampa (folha) inclinada: placa com degraus de grip cobrindo o alto, levemente erguida
        f.rect(3, 4, 28, 17, S["panel"])
        f.rect(3, 4, 28, 5, S["panel_l"])
        for y in (8, 11, 14):
            f.rect(5, y, 26, y, S["panel_d"])
            f.rect(5, y + 1, 26, y + 1, S["panel_l"])
        f.rect(3, 17, 28, 18, S["low2"])
        for x, y in ((4, 5), (27, 5), (4, 16), (27, 16)):
            f.px(x, y, S["rivet"])
        for x in (4, 26):                               # dobradiças laranja
            f.rect(x, 18, x + 1, 19, S["orange"])
        for i in range(3):                              # seta "sobe" no alto da rampa
            f.px(15 - i, 8 + i - 0, S["orange"]) if False else None
        for x, y in ((15, 6), (16, 6), (14, 7), (17, 7)):
            f.px(x, y, S["orange"])
        spill(f, 15.5, 27, 20, 9)
    return f


# ---------------------------------------------------------------------------------------------------------------------
# Luz de emergência pequena
# ---------------------------------------------------------------------------------------------------------------------
def light(variant):
    f = V.face_base(False, False)
    cx, cy = 16, 9
    # brilho curto: 1 anel de xadrez em volta da cúpula (raio ≈ 6 px) e só
    rg = 6 if variant == "A" else 8
    for y in range(1, FACE_H - 1):
        for x in range(2, T - 2):
            d = ((x - cx + .5) ** 2 + ((y - cy) * 1.3) ** 2) ** .5
            if d < rg and (d < rg * .55 or (x + y) % 2 == 0):
                c = f.get(x, y)
                if c[:3] == V.rgb(V.OUT)[:3]:
                    continue
                k = .4 if d < rg * .55 else .22
                f.px(x, y, (int(c[0] + (224 - c[0]) * k), int(c[1] * (1 - k * .4)), int(c[2] * (1 - k * .4)), 255))
    if variant == "A":                                 # 6×5 de cúpula, base de 8
        f.rect(13, 6, 18, 11, V.OUT)
        f.rect(14, 7, 17, 10, S["red"])
        f.rect(14, 7, 15, 8, S["red_l"])
        f.px(14, 7, "#ffd0b8")
        f.rect(14, 10, 17, 10, S["red_d"])
        f.rect(12, 11, 19, 12, V.OUT)
        f.rect(13, 11, 18, 11, S["panel_l"])
    else:                                              # 8×6 de cúpula com grade fina e suporte
        f.rect(12, 5, 19, 11, V.OUT)
        f.rect(13, 6, 18, 10, S["red"])
        f.rect(13, 6, 18, 7, S["red_l"])
        f.rect(13, 6, 14, 6, "#ffd0b8")
        f.rect(13, 10, 18, 10, S["red_d"])
        for x in (15, 17):
            f.rect(x, 7, x, 9, S["red_d"])
        f.rect(11, 11, 20, 12, V.OUT)
        f.rect(12, 11, 19, 11, S["panel_l"])
        f.rect(15, 13, 16, 14, S["panel_d"])
    return f


# ---------------------------------------------------------------------------------------------------------------------
def dark_scene(room, lantern_xy, glows):
    """Escuro da caverna + luzes coloridas: glows = [(x, y, raio, (r,g,b) fator)]."""
    a = np.array(room.convert("RGB")).astype(float)
    H, W, _ = a.shape
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt((xx - lantern_xy[0]) ** 2 + ((yy - lantern_xy[1]) * 1.1) ** 2)
    steps = np.array([1.0, 0.72, 0.48, 0.28, 0.14])
    light_ = steps[np.clip((d / 84 * 4).astype(int), 0, 4)]
    tint = np.stack([light_ * 1 + (1 - light_) * .3, light_ * 1 + (1 - light_) * .35, light_ * 1 + (1 - light_) * .6], -1)
    out = a * tint * np.clip(light_[..., None] + .05, 0, 1)
    for (ex, ey, er, col) in glows:
        de = np.sqrt((xx - ex) ** 2 + ((yy - ey) * 1.1) ** 2)
        l2 = np.floor(np.clip(1 - de / er, 0, 1) * 3) / 3
        for i in range(3):
            out[..., i] += a[..., i] * l2 * col[i]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for v in "AB":
        cb = broken(v)
        CH.check(cb, "broken", (40, 44))
        cb.image().save(PEND / f"vesper_container_broken_{v}.png")
        out[f"c{v}"] = Image.open(PEND / f"vesper_container_broken_{v}.png").convert("RGBA")
        hatch(v).im.save(PEND / f"vesper_hatch_{v}.png")
        light(v).im.save(PEND / f"vesper_emergency_light_{v}.png")
        out[f"h{v}"] = Image.open(PEND / f"vesper_hatch_{v}.png").convert("RGBA")
        out[f"l{v}"] = Image.open(PEND / f"vesper_emergency_light_{v}.png").convert("RGBA")
    base = dict(top=Image.open(PEND / "hull_wall_top.png").convert("RGBA"), face=Image.open(PEND / "hull_wall_face.png").convert("RGBA"),
                floor=[Image.open(PEND / f"hull_floor_{i}.png").convert("RGBA") for i in range(4)],
                door=Image.open(PEND / "vesper_jammed_door.png").convert("RGBA"),
                panel=Image.open(PEND / "vesper_power_panel.png").convert("RGBA"))
    for v in "AB":
        sp = dict(base, hatch=out[f"h{v}"], light=out[f"l{v}"], container=out[f"c{v}"])
        room = V.build_room(sp)
        room.save(REP / f"sala_r2_{v}_clara.png")
        dk = dark_scene(room, (4 * T + 16, 4 * T + 50), [
            (T + 16, 24 + 22, 30, (.7, .08, .08)),                                     # luz de emergência (pequena)
            (T + 16, 5 * T + 24 + 16, 52, (.55, .42, .1)) if v == "A" else (T + 16, 5 * T + 24 + 22, 52, (.55, .42, .12))])
        dk.save(REP / f"sala_r2_{v}_escura.png")
    print("ok")


if __name__ == "__main__":
    main()
