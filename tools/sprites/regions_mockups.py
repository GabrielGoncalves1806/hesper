#!/usr/bin/env python3
"""Proposta de GEOGRAFIA NOVA da superfície (v0.4 Marco 2): 3 regiões + faixa gelada, formações fixas, decoração
que quebra a grade, morros de borda orgânica, relevo e água. Tudo PENDENTE, pro dono aprovar.

    python3 tools/sprites/regions_mockups.py        (PIL + numpy do sistema; determinístico, sem random sem seed)

Módulos:
    tools/sprites/regions_core.py        paletas, transformação por estágio, ruído, texturas, decalques, gerador
    tools/sprites/regions_scene.py       renderizador da cena (a "receita" pro Dev)
    tools/sprites/regions_formations.py  formações e decoração solta com altura
    tools/sprites/ui_mockups.py          HUD B2 (importado, não é alterado)

Saídas:
    assets/sprites/regions/*.png               sprites INDEXADOS (PNG modo P, paleta do Árido embutida), APROVADOS
    assets/sprites/regions/regions_palettes.json   as rampas dos 4 estágios + pegadas das formações
    reports/design/regioes/*.png               mockups 960×540, diagramas, prévias
    reports/design/regioes/index.html          o report (tools/sprites/regions_report.py)
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import regions_core as R  # noqa: E402
import regions_formations as F  # noqa: E402
import regions_scene as SC  # noqa: E402
import regions_report  # noqa: E402
import ui_mockups as U  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
PEND = SPR / "regions"            # aprovado pelo dono (v8.1, hoodoo v8.3): sai direto na pasta definitiva
OUT = ROOT / "reports" / "design" / "regioes"
T = 32


def load(name):
    return Image.open(SPR / f"{name}.png").convert("RGBA")


# =================================================================================================================
# MUNDO DE EXEMPLO
# =================================================================================================================
# formações: (tipo, tile do pé). O pé é o tile da âncora (centro da base do sprite)
FORMS = [
    ("arch", (63, 112)),
    ("monolith", (69, 108)),
    ("monolith", (100, 76)),
    ("basalt_spires", (24, 99)),
    ("cone", (36, 103)),
    ("basalt_spires", (30, 150)),
    ("salt_ridge", (136, 109)),
    ("salt_ridge", (160, 124)),
]
GATES = [((96, 16), 1.0), ((52, 20), 1.0), ((150, 19), 1.0)]    # gelos-portão (faixa gelada)
POD_FOOT = (96 * T, 96 * T)

FORM_TABLE = {"monolith": ("plateau", {"plateau": R.SAND}), "arch": ("plateau", {"plateau": R.SAND}),
              "basalt_spires": ("basalt", R.HILL), "cone": ("basalt", R.HILL), "salt_ridge": ("salar", R.BASE)}
ICE_TABLE = ("frost", {"frost": R.ICE})

# vistas (centro em tiles) ------------------------------------------------------------------------------------
VIEWS = {
    "base":      (101, 95),     # planalto com a base e a cratera (com gelo)
    "crater":    (111, 100),    # a cratera no meio da tela (etapas do gelo)
    "plateau":   (74, 112),     # planalto: arco, monolito, depressão pequena (usada nos 4 estágios e na água)
    "salar":     (134, 107),    # beira do salar: crosta elevada, marcas d'água
    "basalt":    (29, 99),      # basalto: pináculos e cone
    "frost":     (96, 13),      # faixa gelada: gelo-portão fechando um corredor
    "t_salar":   (122, 119),    # passagem planalto -> salar
    "t_basalt":  (47, 78),      # passagem planalto -> basalto
    "t_frost":   (128, 26),     # passagem planalto -> faixa gelada
    "hills":     (112, 62),     # morros: antes x depois
}


# onde o player fica em cada vista (fora do HUD e fora de parede); o resto usa o centro
PLAYER = {"plateau": (71, 113), "frost": (91, 17), "hills": (115, 66), "base": (101, 95), "salar": (130, 106)}


def view_origin(name):
    cx, cy = VIEWS[name]
    return cx * T - 480, cy * T - 270


def build_world():
    w = R.gen_world()
    wall = np.zeros((R.H, R.W), bool)
    rng = np.random.default_rng(1234)
    xs, ys = R.grid(R.W, R.H)
    keep_out = np.zeros_like(wall)
    def clear(cx, cy, r):  # noqa: E306
        keep_out[np.hypot(xs - cx, ys - cy) < r] = True
    clear(96, 95, 13)
    clear(111, 100, 5)
    for kind, (fx, fy) in FORMS:
        clear(fx, fy - 1, 6.5)
    for (gx, gy), _ in GATES:
        clear(gx, gy - 1, 4.5)
    clear(78, 114, 9)
    for vx, vy in (VIEWS["t_salar"], VIEWS["t_basalt"], VIEWS["t_frost"]):
        clear(vx, vy, 7)
    # morros espalhados (mais no basalto e na faixa gelada, nenhum no salar)
    for i in range(110):
        cx, cy = rng.uniform(6, R.W - 6), rng.uniform(6, R.H - 6)
        reg = w["region"][int(cy), int(cx)]
        if reg == R.REG["salar"]:
            continue
        if reg == R.REG["plateau"] and rng.uniform() < 0.35:
            continue
        rx, ry = rng.uniform(2.2, 4.5), rng.uniform(1.8, 3.4)
        b = R.blob(cx, cy, rx, ry, 4000 + i)
        if (b & keep_out).any():
            continue
        wall |= b
    # morros colocados à mão nas vistas
    wall |= R.blob(108, 62, 4, 3, 5) | R.blob(122, 66, 3, 2.5, 9) | R.blob(101, 59, 2.4, 2, 11)
    wall |= R.blob(59, 118, 2.6, 1.8, 21) | R.blob(88, 106, 2.2, 1.8, 22)
    wall |= R.blob(87, 14, 3.2, 3.5, 31) | R.blob(106, 14, 3.4, 3.6, 32)       # o corredor do portão
    wall |= R.blob(24, 108, 3, 2.2, 41) | R.blob(13, 92, 2.5, 3, 42)
    wall &= w["region"] != R.REG["salar"]
    wall &= w["h"] > R.LEVELS[2] + 0.01
    wall = R.smooth(wall, 1)
    w["wall"] = wall
    # minério nos morros, pela região
    ore = {}
    pick = {0: ("iron", "silicon"), 2: ("iron", "iron", "silicon"), 3: ("ice", "ice", "iron"), 1: ("silicon",)}
    for ty, tx in zip(*np.nonzero(wall)):
        if R.hash2(tx, ty, 9) < 0.13:
            opts = pick[int(w["region"][ty, tx])]
            ore[(int(tx), int(ty))] = opts[int(R.hash2(tx, ty, 10) * len(opts))]
    w["ore"] = ore
    # afloramentos (rochas pequenas com minério) em volta das formações e dos portões
    rocks = []
    anchors = [(f, p) for f, p in FORMS] + [("gate", p) for p, _ in GATES]
    for k, (kind, (fx, fy)) in enumerate(anchors):
        reg = R.REG_NAMES[w["region"][fy, fx]]
        res_opts = {"plateau": ("iron", "silicon"), "basalt": ("iron", "iron"), "salar": ("silicon", "silicon"),
                    "frost": ("ice", "ice", "silicon")}[reg]
        n = 0
        for j in range(40):
            a = R.hash2(k, j, 91) * 2 * math.pi
            d = 2.4 + R.hash2(k, j, 92) * 2.6
            tx, ty = int(round(fx + math.cos(a) * d * 1.3)), int(round(fy - 0.5 + math.sin(a) * d))
            if wall[ty, tx] or any(abs(tx - rx) + abs(ty - ry) < 2 for rx, ry, _ in rocks):
                continue
            if abs(tx - fx) <= 2 and fy - 2 <= ty <= fy:
                continue
            rocks.append((tx, ty, res_opts[int(R.hash2(k, j, 93) * len(res_opts))]))
            n += 1
            if n >= 4:
                break
    w["rocks"] = rocks
    return w


# =================================================================================================================
# OBJETOS NA CENA
# =================================================================================================================
_FORM_CACHE: dict = {}


def form_idx(kind):
    if kind not in _FORM_CACHE:
        _FORM_CACHE[kind] = F.FORMATIONS[kind]()
    return _FORM_CACHE[kind]


def form_ramp(kind, stage):
    """Rampa do sprite da formação no estágio."""
    reg, table = FORM_TABLE[kind]
    return R.ramp(reg, stage, table)


def form_img(kind, stage):
    idx, info = form_idx(kind)
    return R.colorize(idx, form_ramp(kind, stage)), info


_GATE: dict = {}
_CRATER: dict = {}
METAL = np.array([R.rgb("#b9bcc4"), R.rgb("#5b6070"), R.rgb("#e2733a")], np.uint8)
CRATER_STAGES = 5


def gate_idx(scale):
    if scale not in _GATE:
        _GATE[scale] = F.ice_block(scale)
    return _GATE[scale]


def gate_img(scale, stage):
    idx, info = gate_idx(scale)
    reg, table = ICE_TABLE
    return R.colorize(idx, R.ramp(reg, stage, table)), info


def crater_idx(k):
    if k not in _CRATER:
        _CRATER[k] = F.crater(k)
    return _CRATER[k]


def crater_ramp(stage):
    """Paleta da cratera: 0..9 rampa do planalto no estágio, 10..17 gelo (ICE), 18..20 metal da rampa."""
    terra = R.ramp("plateau", stage)
    ice = R.ramp("frost", stage, {"frost": R.ICE})[:8]
    return np.concatenate([terra, ice, METAL])


def crater_img(k, stage):
    idx, info = crater_idx(k)
    return R.colorize(idx, crater_ramp(stage)), info


_ROCKS: dict = {}


def rock_img(region, res):
    """rock_small de hoje recolorido pra rocha da região (LUT pela luminância) + pepita do minério em cima."""
    key = (region, res)
    if key in _ROCKS:
        return _ROCKS[key]
    base = load("rock_small")
    a = np.array(base)
    if region in ("basalt", "frost", "salar"):
        table = R.HILL[region]
        ramp_ = np.array([R.rgb(c) for c in table[:6]], float)
        m = a[..., 3] > 0
        lum = a[..., :3].astype(float).mean(axis=2)
        dark = (a[..., :3] == R.OUTLINE).all(axis=2)
        k = np.clip(((lum - 40) / 190 * 5).round().astype(int), 0, 5)
        a[m & ~dark, :3] = ramp_[k[m & ~dark]].astype(np.uint8)
    im = Image.fromarray(a)
    nug = load(f"pickup_{res}").crop((2, 2, 14, 14))
    im.alpha_composite(nug, (11, 6))
    _ROCKS[key] = im
    return im


def player_img(frame=0, view="down"):
    return load(f"player_idle_{view}").crop((frame * 32, 0, frame * 32 + 32, 32))


def place(scene, img, foot_x, foot_y):
    """Objeto ancorado no centro da base (igual ao _blit_anchored do jogo)."""
    scene.objects.append((foot_y, img, foot_x - img.width // 2, foot_y - img.height))


def place_sprite_foot(scene, img, info, tile):
    """Formação: o pé do sprite (info['foot']) cai no meio da borda de baixo do tile `tile`."""
    fx, fy = info["foot"]
    wx, wy = tile[0] * T + T // 2, tile[1] * T + T - 2
    scene.objects.append((wy, img, wx - fx, wy - fy))


def populate(scene, world, stage, decor=True, crater_stage=0, gate_scale=None, player_at=None, base=False,
             skip_forms=False):
    x0, y0 = scene.x0, scene.y0
    vis = lambda tx, ty, m=6: (x0 // T - m <= tx <= (x0 + 960) // T + m and y0 // T - m <= ty <= (y0 + 540) // T + m)  # noqa: E731
    if not skip_forms:
        for kind, tile in FORMS:
            if vis(*tile):
                img, info = form_img(kind, stage)
                place_sprite_foot(scene, img, info, tile)
    for (tile, sc) in GATES:
        if vis(*tile):
            s = gate_scale if gate_scale is not None else sc
            if s > 0:
                img, info = gate_img(s, stage)
                place_sprite_foot(scene, img, info, tile)
            if s < 1:
                ring = R.colorize(F.frost_ring(), R.ramp("frost", stage))
                scene.under_decals.append((ring, tile[0] * T + 16 - ring.width // 2, tile[1] * T - 30))
    for tx, ty, res in world["rocks"]:
        if scene.water is not None and world["h"][ty, tx] < scene.water + 0.01:
            continue                      # rocha no fundo do lago: no jogo ela nem nasce onde a água vai chegar
        if vis(tx, ty, 2):
            reg = R.REG_NAMES[world["region"][ty, tx]]
            place(scene, rock_img(reg, res), tx * T + 16, ty * T + 31)
    # cratera de impacto (bacia nos 3×3) com a tampa de gelo na etapa `crater_stage` + a ejeção no chão
    cx, cy = R.CRATER_T
    if vis(cx, cy):
        ccx, ccy = cx * T + 48, cy * T + 48                     # centro dos 3×3 = âncora do sprite
        ej = R.colorize(F.ejecta(), R.ramp("plateau", stage))
        scene.under_decals.append((ej, ccx - ej.width // 2, ccy - ej.height // 2))
        cr, info = crater_img(crater_stage, stage)
        ax, ay = info["anchor"]
        scene.objects.append((cy * T + 95, cr, ccx - ax, ccy - ay))
    # decoração solta com altura (não colide): lascas no basalto, cristais no salar, pedaços de gelo na faixa
    if decor:
        small = {"basalt": (F.shards, R.HILL), "salar": (F.salt_crystals, R.BASE), "frost": (F.ice_chunks, None)}
        for ty in range(y0 // T - 2, (y0 + 540) // T + 3):
            for tx in range(x0 // T - 2, (x0 + 960) // T + 3):
                if not (0 <= tx < R.W and 0 <= ty < R.H) or world["wall"][ty, tx]:
                    continue
                reg = R.REG_NAMES[world["region"][ty, tx]]
                if reg not in small or R.hash2(tx, ty, 601) > 0.035:
                    continue
                if any(abs(tx - f[1][0]) < 4 and abs(ty - f[1][1]) < 3 for f in FORMS):
                    continue
                if reg == "salar" and world["h"][ty, tx] < (scene.water or -1):
                    continue
                fn, table = small[reg]
                idx = fn(int(R.hash2(tx, ty, 602) * 5) + 1)
                rmp = R.ramp("frost", stage, {"frost": R.ICE}) if reg == "frost" else R.ramp(reg, stage, table)
                place(scene, R.colorize(idx, rmp), tx * T + 16, ty * T + 26)
    # entulho no pé dos morros (decalque: quebra a linha do pé da face)
    d = SC.decals()
    for ty in range(y0 // T - 2, (y0 + 540) // T + 2):
        for tx in range(x0 // T - 2, (x0 + 960) // T + 2):
            if world["wall"][ty, tx] and not world["wall"][ty + 1, tx] and R.hash2(tx, ty, 620) < 0.45:
                reg = R.REG_NAMES[world["region"][ty, tx]]
                key = f"rubble_{int(R.hash2(tx, ty, 621) * 4)}"
                img = R.colorize(d[key], R.ramp(reg if reg in R.HILL else "plateau", stage, R.HILL))
                scene.under_decals.append((img, tx * T + 16 - img.width // 2 + int(R.hash2(tx, ty, 622) * 12) - 6,
                                           (ty + 1) * T - 4))
    if base:
        place(scene, load("pod"), *POD_FOOT)
        for (name, tx, ty) in (("machine_o2", 92, 97), ("machine_heater", 100, 97), ("machine_melter", 99, 93),
                               ("solar_panel", 93, 93), ("solar_panel", 94, 99), ("chest", 97, 99)):
            place(scene, load(name), tx * T + 16, ty * T + 30)
    if player_at:
        place(scene, player_img(), player_at[0] * T + 16, player_at[1] * T + 30)
    # plantas no Verde: preferem a beira d'água e a grama
    if stage == "green":
        for ty in range(y0 // T, (y0 + 540) // T + 1):
            for tx in range(x0 // T, (x0 + 960) // T + 1):
                if world["wall"][ty, tx]:
                    continue
                hh = world["h"][ty, tx]
                near = (scene.water or 0) + 0.03 < hh < (scene.water or 0) + 0.09
                p = 0.20 if near else 0.025
                if R.hash2(tx, ty, 650) < p and world["region"][ty, tx] != R.REG["salar"] \
                        and hh > (scene.water or 0) + 0.03:
                    kind = ("plant_bush", "plant_flower", "plant_tree")[int(R.hash2(tx, ty, 651) * 3)]
                    if any(abs(tx - f[1][0]) < 4 and abs(ty - f[1][1]) < 3 for f in FORMS):
                        continue
                    place(scene, load(kind), tx * T + 8 + int(R.hash2(tx, ty, 652) * 16), ty * T + 24)
    if decor:
        def skip(tx, ty):
            if np.hypot(tx - 96, ty - 95) < 6:
                return True
            return any(abs(tx - f[1][0]) < 3 and -3 < ty - f[1][1] < 2 for f in FORMS)
        scene.ground_decals = SC.scatter(world, x0, y0, stage, skip=skip)


# =================================================================================================================
# EFEITOS DE ESTÁGIO (aproximação do que o jogo já faz: a poeira é o game/dust.py, aqui só pra dar o clima)
# =================================================================================================================
def storm_overlay(img, scene):
    cloud = Image.open(SPR / "_pending" / "storm" / "dust_cloud_b.png").convert("RGB")
    big = Image.new("RGB", (1280, 1024))           # 960 + 256 e 540 + 256: o recorte nunca passa da borda
    for yy in range(0, 1024, 256):
        for xx in range(0, 1280, 256):
            big.paste(cloud, (xx, yy))
    ox, oy = scene.x0 % 256, scene.y0 % 256
    big = big.crop((ox, oy, ox + 960, oy + 540))
    xs, ys = R.grid(960, 540)
    d = np.hypot(xs - 480, ys - 262) / (7 * T)
    n = R.fbm(xs + scene.x0, ys + scene.y0, 60, 801, 2)
    a = np.clip((d - 0.35 + 0.35 * (n - 0.5)) / 0.65, 0, 1)
    a = a * a * (3 - 2 * a)
    alpha = (0.28 + 0.62 * a) * 255
    layer = np.dstack([np.array(big), alpha.astype(np.uint8)])
    img.alpha_composite(Image.fromarray(layer))
    px = img.load()
    for i in range(18):
        x = int(R.hash2(i, 0, 811) * 960)
        y = int(R.hash2(i, 1, 811) * 540)
        L = 60 + int(R.hash2(i, 2, 811) * 160)
        for k in range(L):
            xx, yy = x + k, y + int(k * 0.14 + 3 * math.sin(k / 40 + i))
            if 0 <= xx < 960 and 0 <= yy < 540 and (k % 9) < 7:
                px[xx, yy] = (228, 199, 151, 255)


def rain_overlay(img, scene):
    px = img.load()
    for i in range(260):
        x = int(R.hash2(i, 0, 821) * 960)
        y = int(R.hash2(i, 1, 821) * 540)
        for k in range(5):
            xx, yy = x - k // 2, y + k
            if 0 <= xx < 960 and 0 <= yy < 540:
                r, g, b, _ = px[xx, yy]
                px[xx, yy] = (min(255, r + 55), min(255, g + 62), min(255, b + 70), 255)


# =================================================================================================================
# HUD B2 (do ui_mockups.py) + minimapa do mundo novo
# =================================================================================================================
STAGE_HUD = {
    "storm": dict(ti=820, rate=6, idx=("410", "260", "150"), nxt="ÁRIDO", pct=0.33, rem="1.680", eta="~5 min",
                  obj=("Sobreviva e monte a base", "Limpe o céu (Árido)")),
    "arid": dict(ti=4812, rate=12, idx=("2.940", "1.020", "852"), nxt="NÉVOA", pct=0.48, rem="5.188", eta="~7 min",
                 obj=("Derreta o gelo da cratera", "Chegue a Ti 10.000")),
    "mist": dict(ti=31400, rate=48, idx=("18.200", "8.400", "4.800"), nxt="VERDE", pct=0.31, rem="68.600",
                 eta="~24 min", obj=("Abra o gelo do norte", "Encha o salar")),
    "green": dict(ti=118000, rate=96, idx=("62.000", "31.000", "25.000"), nxt="VERDE", pct=1.0, rem="0",
                  eta="fim", obj=("Planeta vivo", "Explore o salar alagado")),
}


def minimap_tex(world, cx, cy, stage, water=None):
    """64×64 tiles em volta de (cx, cy), 1 px por tile, nas cores da região no estágio."""
    out = np.zeros((64, 64, 3), np.uint8)
    for j in range(64):
        for i in range(64):
            tx, ty = cx - 32 + i, cy - 32 + j
            if not (0 <= tx < R.W and 0 <= ty < R.H):
                out[j, i] = (20, 22, 30)
                continue
            reg = R.REG_NAMES[world["region"][ty, tx]]
            hh = world["h"][ty, tx]
            if world["wall"][ty, tx]:
                c = R.ramp(reg, stage, R.HILL)[2]
            elif water is not None and hh < water:
                c = R.rgb("#3f7690" if stage == "mist" else "#2c7ea6")
            elif reg == "plateau" and hh < R.LEVELS[2]:
                c = R.ramp("bed", stage)[4]
            else:
                c = R.ramp(reg, stage)[3]
            out[j, i] = c
    return Image.fromarray(out).convert("RGBA")


def hud(img, stage, world, center, water=None):
    st = STAGE_HUD[stage]
    U.TI, U.TI_RATE = st["ti"], st["rate"]
    U.INDICES = [("o2", "O₂", st["idx"][0], "PPQ", U.C_O2), ("heat", "CALOR", st["idx"][1], "PK", U.C_HEAT),
                 ("water", "ÁGUA", st["idx"][2], "PPM", U.C_WATER)]
    U.NEXT_STAGE, U.NEXT_PCT, U.REMAINING, U.ETA = st["nxt"], st["pct"], st["rem"], st["eta"]
    B, K = U.B, U.K
    ctx = U.Ctx(img)
    U.b_card(ctx, 6, 6, 132, 17)
    ctx.text("O₂", 11, 7, U.C_O2, shadow=False)
    U.b_bar(ctx, 26, 12, 60, U.O2_SECONDS / U.O2_MAX, U.C_O2, h=4)
    ctx.text(f"{U.O2_SECONDS}s", 90, 3, B["text"], U.P, shadow=False)
    ctx.native(U.icon16("o2_tank"), 124 * K, 10 * K)
    U.b_card(ctx, 6, 27, 132, 41)
    ctx.fill(6, 28, 2, 39, U.C_ACCENT)
    ctx.text("OBJETIVO", 12, 27, U.C_ACCENT, shadow=False)
    ctx.text(st["obj"][0], 12, 33, B["text"], U.P, shadow=False)
    ctx.text(st["obj"][1], 12, 45, B["dim"], U.P, shadow=False)
    w = 150
    px = U.UW - 6 - w
    ey = U.b2_ti_panel(ctx, px, 6, w) + 4
    U.b_card(ctx, px + w - 90, ey, 90, 15)
    U.bolt(ctx, px + w - 85, ey + 3, U.C_ENERGY, shadow=False)
    U.b_bar(ctx, px + w - 76, ey + 7, 26, 0.8, U.C_OK, h=3)
    ctx.text("9/5 kW", px + w - 6, ey - 2, U.C_OK, U.P, align="right", shadow=False)
    mx, my = U.UW - 6 - 72, ey + 19
    U.b_card(ctx, mx, my, 72, 72)
    mm = minimap_tex(world, center[0], center[1], stage, water).resize((128, 128), Image.NEAREST)
    bx, by = (96 - center[0] + 32) * 2, (95 - center[1] + 32) * 2
    if 0 <= bx < 128 and 0 <= by < 128:
        U.put_marker(mm, U.marker("base"), bx, by - 8)
    U.put_marker(mm, U.marker("you", direction="down"), 64, 66)
    ctx.native(mm, (mx + 4) * K, (my + 4) * K)
    ctx.round_rect(mx + 5, my + 5, 22, 9, (15, 17, 25, 220))
    ctx.text("MAPA", mx + 7, my + 2, B["muted"], shadow=False)
    U.b_key(ctx, mx + 57, my + 5, "M")
    hx = (U.UW - 174) // 2
    hy = U.UH - 6 - 20
    U.b_card(ctx, hx - 4, hy - 11, 182, 35)
    for i, sl in enumerate(U.HOTBAR):
        U.b_slot(ctx, hx + i * 22, hy, sl, sel=i == 0, num=i + 1)
    x = 6
    for res, n in zip(U.RES, (92, 6, 43)):
        lab = str(n)
        pw = 14 + U.F.width(lab) + 5
        U.b_card(ctx, x, U.UH - 6 - 13, pw, 13)
        ctx.native(U.icon16(res), (x + 2) * K, (U.UH - 6 - 13 + 2) * K)
        ctx.text(lab, x + 12, U.UH - 6 - 13 - 1, B["text"], shadow=False)
        x += pw + 3
    return ctx.img


# =================================================================================================================
# CENAS
# =================================================================================================================
def scene(world, view, stage="arid", decor=True, hills="new", water=None, crater_stage=0, gate_scale=None,
          player=True, base=False, with_hud=True, cover=True, skip_forms=False, tiles=False, player_tile=None):
    x0, y0 = view_origin(view)
    s = SC.Scene(world, x0, y0, stage=stage, decor=decor, hills=hills, water=water, cover=cover, tiles=tiles)
    cx, cy = VIEWS[view]
    populate(s, world, stage, decor=decor, crater_stage=crater_stage, gate_scale=gate_scale,
             player_at=(player_tile or nearest_floor(world, PLAYER.get(view, (cx, cy)), water)) if player else None,
             base=base,
             skip_forms=skip_forms)
    overlay = {"storm": storm_overlay, "mist": rain_overlay}.get(stage)
    img = s.compose(overlay)
    if with_hud:
        img = hud(img, stage, world, (cx, cy), water)
    return img.convert("RGB")


def nearest_floor(world, p, water=None):
    x, y = p
    for r in range(0, 14):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if world["wall"][y + dy, x + dx] or world["wall"][y + dy + 1, x + dx]:
                    continue
                if water is not None and world["h"][y + dy, x + dx] < water + 0.02:
                    continue
                return x + dx, y + dy
    return p


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png")
    return name


# =================================================================================================================
# DIAGRAMAS
# =================================================================================================================
FONT = ImageFont.truetype(str(ROOT / "game" / "fonts" / "PixelifySans.ttf"), 16)
FONT_S = ImageFont.truetype(str(ROOT / "game" / "fonts" / "Silkscreen-Regular.ttf"), 8)


def txt(d, xy, s, fill=(239, 229, 218), font=FONT, anchor="la"):
    d.fontmode = "1"
    x, y = xy
    d.text((x + 1, y + 1), s, font=font, fill=(0, 0, 0), anchor=anchor)
    d.text((x, y), s, font=font, fill=fill, anchor=anchor)


def overview(world, k=3):
    """Mapa 192×192 da proposta: regiões, morros, bacias com as marcas d'água, formações, portões, base."""
    reg = world["region"]
    hh = world["h"]
    img = np.zeros((R.H, R.W, 3), np.uint8)
    for c, name in enumerate(R.REG_NAMES):
        img[reg == c] = R.ramp(name, "arid")[3]
    bed = (reg == 0) & (hh < R.LEVELS[2])
    img[bed] = R.ramp("bed", "arid")[4]
    for L, col in zip(R.LEVELS, ("#2c5a72", "#3f7690", "#6fa3bd")):
        pass
    img[world["wall"]] = R.ramp("plateau", "arid", R.HILL)[2]
    im = Image.fromarray(img).resize((R.W * k, R.H * k), Image.NEAREST)
    d = ImageDraw.Draw(im)
    # curvas de nível L1..L3 (tracejadas)
    for L, col in zip(R.LEVELS, ((44, 90, 114), (63, 118, 144), (111, 163, 189))):
        below = hh < L
        edge = below & ~(np.roll(below, 1, 0) & np.roll(below, -1, 0) & np.roll(below, 1, 1) & np.roll(below, -1, 1))
        for ty, tx in zip(*np.nonzero(edge)):
            d.rectangle((tx * k, ty * k, tx * k + k - 1, ty * k + k - 1), fill=col)
    for kind, (fx, fy) in FORMS:
        x, y = fx * k + k // 2, fy * k
        d.polygon([(x, y - 7), (x + 6, y + 3), (x - 6, y + 3)], fill=(242, 196, 109), outline=(27, 22, 48))
    for (gx, gy), _ in GATES:
        x, y = gx * k + k // 2, gy * k
        d.rectangle((x - 6, y - 5, x + 6, y + 4), fill=(166, 236, 255), outline=(27, 22, 48))
    cx, cy = R.CRATER_T
    d.ellipse((cx * k, cy * k, cx * k + 3 * k, cy * k + 3 * k), fill=(166, 236, 255), outline=(27, 22, 48))
    bx, by = 96 * k, 95 * k
    d.rectangle((bx - 6, by - 5, bx + 6, by + 5), fill=(239, 229, 218), outline=(27, 22, 48))
    d.rectangle((bx - 6, by - 1, bx + 6, by), fill=(226, 115, 58))
    for name, (vx, vy) in VIEWS.items():
        x0, y0 = view_origin(name)
        d.rectangle((x0 / T * k, y0 / T * k, (x0 + 960) / T * k, (y0 + 540) / T * k), outline=(255, 255, 255))
    txt(d, (40 * k, 4 * k), "FAIXA GELADA", anchor="ma")
    txt(d, (154 * k, 100 * k), "SALAR", anchor="ma")
    txt(d, (14 * k, 128 * k), "BASALTO", anchor="la")
    txt(d, (80 * k, 150 * k), "PLANALTO RACHADO", anchor="ma")
    return im


def cross_section(world):
    """Corte do relevo: da base (planalto) até o meio do salar, com os 3 níveis d'água."""
    W_, H_ = 960, 300
    im = Image.new("RGB", (W_, H_), (21, 16, 14))
    d = ImageDraw.Draw(im)
    y_line = 112
    xs = np.linspace(60, 185, W_ - 80)
    hs = SC.bilinear(world["h"], xs - 0.5, np.full_like(xs, y_line - 0.5))
    top, bot = 60, 270
    to_y = lambda h: bot - (h + 0.05) / 0.85 * (bot - top)  # noqa: E731
    for L, col, name in zip(R.LEVELS[::-1], ((76, 156, 192), (63, 118, 144), (44, 90, 114)),
                            ("L3 · Verde cheio", "L2 · Névoa alta", "L1 · começo da Névoa")):
        yy = to_y(L)
        for i, hv in enumerate(hs):
            if hv < L:
                d.line((40 + i, yy, 40 + i, to_y(hv)), fill=col)
    for i, hv in enumerate(hs):
        reg = world["region"][y_line, int(xs[i])]
        col = R.ramp(R.REG_NAMES[reg], "arid")[3] if not (reg == 0 and hv < R.LEVELS[2]) else R.ramp("bed", "arid")[4]
        d.line((40 + i, to_y(hv), 40 + i, bot), fill=tuple(int(c) for c in col))
        d.point((40 + i, to_y(hv)), fill=(27, 22, 48))
    for L, name in zip(R.LEVELS, ("L1 · começo da Névoa", "L2 · Névoa alta", "L3 · Verde cheio")):
        yy = to_y(L)
        for x in range(40, W_ - 40, 6):
            d.line((x, yy, x + 2, yy), fill=(200, 220, 230))
        txt(d, (W_ - 44, yy - 18), name, anchor="ra", fill=(200, 220, 230))
    txt(d, (40, 14), "Corte na linha y = 112: planalto (com a bacia pequena) -> salar", fill=(242, 196, 109))
    txt(d, (40 + (70 - 60) / 125 * (W_ - 80), bot + 8), "planalto", fill=(168, 150, 138))
    txt(d, (40 + (154 - 60) / 125 * (W_ - 80), bot + 8), "salar (a maior depressão)", anchor="ma",
        fill=(168, 150, 138))
    return im


def palette_strip():
    """Rampas: região × estágio (8 cores cada), pra mostrar a regra 'base + variação'."""
    regs = ["plateau", "salar", "basalt", "frost", "bed"]
    sw = 14
    im = Image.new("RGB", (4 * (8 * sw + 18) + 120, len(regs) * (sw + 10) + 30), (21, 16, 14))
    d = ImageDraw.Draw(im)
    for j, st in enumerate(R.STAGES):
        txt(d, (120 + j * (8 * sw + 18), 4), R.STAGE_NAME[st], font=FONT)
    for i, rg in enumerate(regs):
        y = 28 + i * (sw + 10)
        txt(d, (4, y - 2), {"plateau": "planalto", "salar": "salar", "basalt": "basalto", "frost": "gelada",
                            "bed": "leito seco"}[rg])
        for j, st in enumerate(R.STAGES):
            r = R.ramp(rg, st)
            for c in range(8):
                x = 120 + j * (8 * sw + 18) + c * sw
                d.rectangle((x, y, x + sw - 1, y + sw - 1), fill=tuple(int(v) for v in r[c]))
    return im


# =================================================================================================================
# PENDENTES (PNG indexado, paleta do Árido) + JSON das rampas
# =================================================================================================================
def save_indexed(idx, ramp_rgb, path):  # noqa: D401
    """PNG modo P: índices 0..9 com a rampa, 255 transparente. Sombra (9) com alfa SHADOW_A no tRNS."""
    im = Image.frombytes("P", (idx.shape[1], idx.shape[0]), np.ascontiguousarray(idx).tobytes())
    pal = [0] * 768
    for i, c in enumerate(ramp_rgb):
        pal[i * 3:i * 3 + 3] = [int(v) for v in c]
    im.putpalette(pal)
    trns = bytes([255] * 9 + [R.SHADOW_A] + [255] * (255 - 10) + [0])
    im.save(path, transparency=trns)


def export_pending():
    PEND.mkdir(parents=True, exist_ok=True)
    for old in PEND.glob("*.png"):
        old.unlink()
    files = {}
    for name in ("plateau", "salar", "basalt", "frost", "bed"):
        save_indexed(SC.tex(name), R.ramp(name, "arid"), PEND / f"ground_{name}.png")
        files[f"ground_{name}.png"] = ("512×512", name, "BASE")
    save_indexed(SC.hill_top_tex(), R.ramp("plateau", "arid", R.HILL), PEND / "hill_top.png")
    files["hill_top.png"] = ("512×512", "região do morro", "HILL")
    xs, ys = R.grid(512, 24)
    face = SC.face_index(xs, ys)
    save_indexed(face, R.ramp("plateau", "arid", R.HILL), PEND / "hill_face.png")
    files["hill_face.png"] = ("512×24", "região do morro", "HILL")
    for k, idx in SC.decals().items():
        save_indexed(idx, R.ramp("plateau", "arid"), PEND / f"decal_{k}.png")
        files[f"decal_{k}.png"] = (f"{idx.shape[1]}×{idx.shape[0]}", "região onde cai", "BASE")
    forms = {}
    for kind in F.FORMATIONS:
        idx, info = form_idx(kind)
        reg, table = FORM_TABLE[kind]
        save_indexed(idx, form_ramp(kind, "arid"), PEND / f"form_{kind}.png")
        tname = "SAND" if table is not R.HILL and table is not R.BASE else ("HILL" if table is R.HILL else "BASE")
        files[f"form_{kind}.png"] = (f"{idx.shape[1]}×{idx.shape[0]}", reg, tname)
        forms[kind] = dict(info, sprite=f"form_{kind}.png", region=reg, ramp=tname)
    for k, sc in enumerate((1.0, 0.72, 0.45)):
        idx, info = gate_idx(sc)
        save_indexed(idx, R.ramp("frost", "arid", {"frost": R.ICE}), PEND / f"ice_gate_{k}.png")
        files[f"ice_gate_{k}.png"] = (f"{idx.shape[1]}×{idx.shape[0]}", "frost", "ICE")
        forms[f"ice_gate_{k}"] = dict(info, sprite=f"ice_gate_{k}.png", region="frost", ramp="ICE")
    for k in range(CRATER_STAGES):
        idx, info = crater_idx(k)
        save_indexed(idx, crater_ramp("arid"), PEND / f"crater_impact_{k}.png")
        files[f"crater_impact_{k}.png"] = (f"{idx.shape[1]}×{idx.shape[0]}", "plateau", "BASE+ICE+METAL")
        forms[f"crater_impact_{k}"] = dict(info, sprite=f"crater_impact_{k}.png", region="plateau",
                                           ramp="BASE+ICE+METAL")
    ej = F.ejecta()
    save_indexed(ej, R.ramp("plateau", "arid"), PEND / "crater_ejecta.png")
    files["crater_ejecta.png"] = (f"{ej.shape[1]}×{ej.shape[0]}", "plateau", "BASE")
    save_indexed(F.frost_ring(), R.ramp("frost", "arid"), PEND / "frost_ring.png")
    files["frost_ring.png"] = ("176×72", "frost", "BASE")
    for name, fn, reg, tname in (("shards", F.shards, "basalt", "HILL"), ("salt_crystals", F.salt_crystals, "salar",
                                                                          "BASE"),
                                 ("ice_chunks", F.ice_chunks, "frost", "ICE")):
        for v in range(3):
            idx = fn(v + 1)
            table = {"HILL": R.HILL, "BASE": R.BASE, "ICE": {"frost": R.ICE}}[tname]
            save_indexed(idx, R.ramp(reg, "arid", table), PEND / f"decor_{name}_{v}.png")
            files[f"decor_{name}_{v}.png"] = (f"{idx.shape[1]}×{idx.shape[0]}", reg, tname)
    # v9 (aprovado pelo dono): decalques, soltos, musgo do Verde+ e formações pequenas
    import regions_v9 as V9
    v9_files, v9_forms, v9_density = V9.export_assets(PEND)
    files.update({k: (v["size"], v["region"], v["ramp"]) for k, v in v9_files.items()})
    forms.update(v9_forms)
    # v9.1 (aprovado pelo dono): fumarolas dormente/ativa, rampa VENT, partícula de fumaça e densidade
    import regions_v91 as V91
    v91_files, v91_forms, vent_ramp, smoke, vent_density = V91.export_assets(PEND)
    files.update({k: (v["size"], v["region"], v["ramp"]) for k, v in v91_files.items()})
    forms.update(v91_forms)
    ramps = {}
    for tname, table in (("BASE", R.BASE), ("HILL", R.HILL), ("SAND", {"plateau": R.SAND}),
                         ("ICE", {"frost": R.ICE})):
        ramps[tname] = {}
        for reg in table:
            ramps[tname][reg] = {st: [R.hexc(c) for c in R.ramp(reg, st, table)[:8]] for st in R.STAGES}
    ramps["METAL"] = [R.hexc(c) for c in METAL]
    ramps["MOSS"] = list(V9.E.MOSS)              # v9: overlay de musgo do Verde+ (fixa, não muda com estágio)
    ramps["VENT"] = vent_ramp                     # v9.1: ramps.VENT.basalt[estágio] = 4 cores (índices 10..13)
    data = dict(note="Sprites indexados: 0..7 = rampa, 8 = contorno #1b1630, 9 = sombra (preto, alfa %d), "
                     "255 = transparente. Cor final = ramps[tabela][região][estágio][índice]. crater_impact_*: 10..17 = ramps.ICE.frost, "
                     "18..20 = ramps.METAL. decor_*_moss_*: 0..3 = ramps.MOSS (só no Verde). Formações com small=true "
                     "são as pequenas da v9; vent_* (v9.1) têm sprites dormant/active, paleta HILL.basalt + 10..13 = "
                     "ramps.VENT.basalt e mouths (px de onde sai a fumaça do bloco smoke)." % R.SHADOW_A,
                levels=R.LEVELS, warp_px=SC.WARP, decal_cell=R.DECAL_CELL, decal_p=R.DECAL_P,
                decal_mix=R.DECAL_MIX, v9_density=v9_density, vent_density=vent_density, smoke=smoke,
                formations=forms, ramps=ramps,
                files={k: dict(size=v[0], region=v[1], ramp=v[2]) for k, v in sorted(files.items())})
    (PEND / "regions_palettes.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return files


def preview_sprites():
    """Prévias RGBA (Árido) pro report, com fundo transparente (o report põe o xadrez)."""
    out = OUT / "sprites"
    out.mkdir(parents=True, exist_ok=True)
    names = []
    for kind in F.FORMATIONS:
        img, info = form_img(kind, "arid")
        img.save(out / f"form_{kind}.png")
        names.append(f"form_{kind}")
    for k, sc in enumerate((1.0, 0.72, 0.45)):
        gate_img(sc, "arid")[0].save(out / f"ice_gate_{k}.png")
    for k in range(CRATER_STAGES):
        crater_img(k, "arid")[0].save(out / f"crater_impact_{k}.png")
    R.colorize(F.ejecta(), R.ramp("plateau", "arid")).save(out / "crater_ejecta.png")
    for name, fn, reg, table in (("shards", F.shards, "basalt", R.HILL), ("salt_crystals", F.salt_crystals,
                                                                          "salar", R.BASE),
                                 ("ice_chunks", F.ice_chunks, "frost", {"frost": R.ICE})):
        R.colorize(fn(1), R.ramp(reg, "arid", table)).save(out / f"decor_{name}.png")
    # decalques numa folha por região
    d = SC.decals()
    for reg, keys in (("plateau", ("patch_dark_0", "patch_light_1", "crack_0", "plates_0", "gravel_0", "wind_0")),
                      ("salar", ("ridges_0", "stain_1", "crack_2", "patch_light_2")),
                      ("basalt", ("scoria_0", "stain_0", "crack_1", "patch_dark_2", "plates_1")),
                      ("frost", ("icesheet_0", "wind_1", "gravel_2", "patch_light_0"))):
        ims = [R.colorize(d[k], R.ramp(reg, "arid")) for k in keys]
        Wd = sum(i.width for i in ims) + 12 * (len(ims) + 1)
        Hd = max(i.height for i in ims) + 24
        sheet = Image.new("RGBA", (Wd, Hd), tuple(int(c) for c in R.ramp(reg, "arid")[3]) + (255,))
        x = 12
        for im in ims:
            sheet.alpha_composite(im, (x, (Hd - im.height) // 2))
            x += im.width + 12
        sheet.save(out / f"decals_{reg}.png")
    # textura do chão (recorte 256×128) por região × estágio
    for reg in ("plateau", "salar", "basalt", "frost", "bed"):
        for st in R.STAGES:
            R.colorize(SC.tex(reg)[:128, :256], R.ramp(reg, st)).save(out / f"ground_{reg}_{st}.png")
    return names


# =================================================================================================================
def footprint_sheet():
    """Cada formação em cima da grade de tiles, com os tiles que bloqueiam pintados (a 'colisão')."""
    items = [(kind,) + form_img(kind, "arid") for kind in F.FORMATIONS]
    for k, sc in enumerate((1.0, 0.72, 0.45)):
        im, info = gate_img(sc, "arid")
        items.append((f"ice_gate_{k}", im, info))
    im, info = crater_img(4, "arid")
    ax, ay = info["anchor"]
    items.append(("crater_impact", im, dict(info, foot=(ax, ay + 46))))     # pé = meio da borda de baixo dos 3×3
    out = []
    for kind, img, info in items:
        fx, fy = info["foot"]
        cols = max(6, img.width // T + 3)
        rows = img.height // T + 2
        W_, H_ = cols * T, rows * T
        rows = max(rows, -min(dy for _, dy in info["tiles"]) + 3)
        H_ = rows * T
        bg = Image.new("RGBA", (W_, H_), tuple(int(c) for c in R.ramp(
            "frost" if kind.startswith("ice") else FORM_TABLE.get(kind, ("plateau",))[0], "arid")[3]) + (255,))
        d = ImageDraw.Draw(bg)
        ftx, fty = cols // 2, rows - 2
        for dx, dy in info["tiles"]:
            x, y = (ftx + dx) * T, (fty + dy) * T
            d.rectangle((x, y, x + T - 1, y + T - 1), fill=(255, 106, 85, 255))
        for gx in range(0, W_, T):
            d.line((gx, 0, gx, H_), fill=(0, 0, 0, 255))
        for gy in range(0, H_, T):
            d.line((0, gy, W_, gy), fill=(0, 0, 0, 255))
        wx, wy = ftx * T + T // 2, fty * T + T - 2
        bg.alpha_composite(img, (wx - fx, wy - fy))
        # o pé bloqueado também por cima (contorno vermelho), pra ver mesmo atrás do sprite
        for dx, dy in info["tiles"]:
            x, y = (ftx + dx) * T, (fty + dy) * T
            d.rectangle((x, y, x + T - 1, y + T - 1), outline=(255, 106, 85, 255))
        d.ellipse((wx - 2, wy - 2, wx + 2, wy + 2), fill=(89, 208, 230, 255))
        bg.save(OUT / "sprites" / f"foot_{kind}.png")
        out.append((kind, info))
    return out


def main():
    world = build_world()
    OUT.mkdir(parents=True, exist_ok=True)
    shots = {}
    # 2 · as regiões no Árido
    shots["arid_base"] = save(scene(world, "base", base=True, crater_stage=0), "arid_base")
    shots["arid_plateau"] = save(scene(world, "plateau"), "arid_plateau")
    shots["arid_salar"] = save(scene(world, "salar"), "arid_salar")
    shots["arid_basalt"] = save(scene(world, "basalt"), "arid_basalt")
    shots["arid_frost"] = save(scene(world, "frost"), "arid_frost")
    for v in ("t_salar", "t_basalt", "t_frost"):
        shots[v] = save(scene(world, v), f"arid_{v}")
    # 3 · os 4 estágios no planalto (mesma vista)
    lv = {"storm": None, "arid": None, "mist": R.LEVELS[1], "green": R.LEVELS[2]}
    for st in R.STAGES:
        save(scene(world, "plateau", stage=st, water=lv[st]), f"stage_{st}")
    # 5 · decoração: sem x com (sem HUD, pra ver o chão)
    save(scene(world, "plateau", decor=False, with_hud=False, cover=False, skip_forms=True, player=False,
               tiles=True), "decor_off")
    save(scene(world, "plateau", decor=True, with_hud=False, skip_forms=True, player=False), "decor_on")
    save(scene(world, "t_salar", decor=False, with_hud=False, tiles=True), "decor_border_off")
    save(scene(world, "t_salar", decor=True, with_hud=False), "decor_border_on")
    # 6 · morros: antes (jogo de hoje) x depois
    save(scene(world, "hills", hills="old", decor=False, with_hud=False, player=True), "hills_before")
    save(scene(world, "hills", hills="new", decor=True, with_hud=False, player=True), "hills_after")
    # 7 · água: a mesma bacia nos níveis
    save(scene(world, "plateau", stage="arid", with_hud=False, player=False), "water_arid")
    save(scene(world, "plateau", stage="mist", water=R.LEVELS[0], with_hud=False, player=False), "water_mist_l1")
    save(scene(world, "plateau", stage="mist", water=R.LEVELS[1], with_hud=False, player=False), "water_mist_l2")
    save(scene(world, "plateau", stage="green", water=R.LEVELS[2], with_hud=False, player=False), "water_green_l3")
    save(scene(world, "salar", stage="green", water=R.LEVELS[2], with_hud=True, player_tile=(123, 113)),
         "water_salar_green")
    save(scene(world, "salar", stage="mist", water=R.LEVELS[1], with_hud=False), "water_salar_mist")
    # gelo: portão derretendo e a cratera
    # recorte 320×180 em volta do objeto (o report amplia 3× com pixelated)
    for k, sc in enumerate((1.0, 0.72, 0.45, 0.0)):
        im = scene(world, "frost", gate_scale=sc, with_hud=False, player=False)
        save(im.crop((336, 244, 656, 424)), f"gate_melt_{k}")
    for k in range(CRATER_STAGES):
        im = scene(world, "crater", crater_stage=k, with_hud=False, player=False)
        save(im.crop((336, 196, 656, 376)), f"crater_melt_{k}")
    save(scene(world, "crater", crater_stage=0, player=True, player_tile=(111, 104)), "arid_crater")
    # diagramas
    overview(world).save(OUT / "mapa_regioes.png")
    cross_section(world).save(OUT / "corte_relevo.png")
    palette_strip().save(OUT / "paletas.png")
    files = export_pending()
    preview_sprites()
    feet = footprint_sheet()
    (OUT / "_meta.json").write_text(json.dumps(dict(files=files, feet=[(k, i) for k, i in feet], views=VIEWS,
                                                    forms=FORMS), ensure_ascii=False, indent=1, default=str))
    page = regions_report.build()
    print("ok:", len(list(OUT.glob("*.png"))), "png no report,", len(files), "pendentes ->", page)


if __name__ == "__main__":
    main()
