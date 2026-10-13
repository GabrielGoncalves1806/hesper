#!/usr/bin/env python3
"""v9 · PROPOSTA (pendente do dono): basalto sem a célula retangular + elementos novos por região.

    python3 tools/sprites/regions_v9.py        (PIL + numpy do sistema; determinístico)

APROVADO pelo dono (v9): os sprites e os dados entram em assets/sprites/regions/ pelo regions_mockups.py
(export_pending chama export_assets() daqui). Este script gera as prévias, as cenas e a seção v9 do report;
a cópia em v9/pendentes/ fica como registro do que foi aprovado.

    v9/ground_basalt.png           candidata do chão de basalto (PNG indexado, igual ao contrato)
    v9/pendentes/*.png             os elementos novos, PNG indexado (modo P, paleta do Árido embutida)
    v9/pendentes/regions_v9.json   tamanhos, rampas, âncoras, pegadas e a densidade sugerida
    v9/*.png                       prévias do report (RGBA, Árido) e cenas antes × depois
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import regions_core as R  # noqa: E402
import regions_mockups as M  # noqa: E402
import regions_scene as SC  # noqa: E402
import regions_v9_elements as E  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "reports" / "design" / "regioes" / "v9"
PEND = OUT / "pendentes"
BEFORE = ROOT / "reports" / "design" / "before"
T = 32

# ---------------------------------------------------------------------------------------------------------------
# CATÁLOGO: o que é cada coisa, onde cai e quanto espalhar
# ---------------------------------------------------------------------------------------------------------------
REGION_PT = {"plateau": "planalto", "salar": "salar", "basalt": "basalto", "frost": "faixa gelada", "bed": "leito seco"}

DECALS = {   # nome: (região, nome no report, descrição)
    "vein": ("plateau", "Veio mineral exposto", "faixa clara de mineral mais duro, em relevo, que serpenteia e some na terra"),
    "oxide": ("plateau", "Anéis de oxidação", "faixas concêntricas e tortas de ferrugem e ocre, abertas de um lado"),
    "saltpoly": ("salar", "Polígonos de sal miúdos", "favo torto de cristas de sal empurradas (~14 px)"),
    "efflor": ("salar", "Eflorescência", "rosetas de sal em grupinho"),
    "fumarole": ("basalt", "Respiro de fumarola apagada", "boca escura, crosta mineral clara, halo de óxido"),
    "ropy": ("basalt", "Lava em corda", "frente de um lóbulo de lava lisa com as dobras em arco"),
    "icepoly": ("frost", "Solo poligonal", "polígonos de permafrost com cunha de gelo no sulco"),
    "rime": ("frost", "Geada em pena", "galhos de cristal de gelo se ramificando"),
    "trail": ("bed", "Rastro de seixo", "sulco comprido de pedra que o vento arrastou no lodo, e o seixo no fim"),
    "ripples": ("bed", "Marcas de onda", "cristas paralelas do lago antigo fossilizadas no silte"),
}
DECORS = {   # nome: (região, nome no report, descrição)
    "pebbles": ("plateau", "Seixos", "2 a 4 pedrinhas roladas (também no leito seco)"),
    "boulder": ("plateau", "Pedra média", "pedra achatada roída pelo vento, com uma face de lasca"),
    "slabs": ("plateau", "Lajes lascadas", "placas chatas e angulosas de rocha que esfoliou, uma sobre a outra"),
    "salt_mound": ("salar", "Montinho de sal", "sal em couve-flor (eflorescência que cresceu)"),
    "salt_slabs": ("salar", "Crosta solta", "lascas finas de crosta de sal soltas e encavaladas"),
    "bombs": ("basalt", "Bombas vulcânicas", "pedras porosas de escória, uma em fuso, com vesículas e óxido"),
    "column_stub": ("basalt", "Toco de coluna", "1 a 3 prismas hexagonais curtos, quina quebrada, junta"),
    "penitentes": ("frost", "Penitentes", "lâminas de gelo afiadas pela sublimação, inclinadas pro sol"),
    "rimed_rock": ("frost", "Pedra com geada", "rocha escura com a crosta de geada por cima"),
    "mud_curls": ("bed", "Lascas de lama", "plaquinhas de lodo seco com a borda de trás enrolando"),
}
MOSSY = ("boulder", "column_stub")          # Verde+: ganham o overlay de musgo no Verde

# densidade sugerida (o que as cenas usam)
DECAL_P_V9 = {"plateau": 0.30, "salar": 0.30, "basalt": 0.30, "frost": 0.30, "bed": 0.35}
DECAL_MIX_V9 = {"plateau": [("vein", 3), ("oxide", 2)], "salar": [("saltpoly", 3), ("efflor", 3)],
                "basalt": [("fumarole", 3), ("ropy", 2)], "frost": [("icepoly", 3), ("rime", 3)],
                "bed": [("trail", 2), ("ripples", 3)]}
DECOR_P_V9 = {   # chance por tile de chão livre
    "plateau": [("pebbles", 0.012), ("boulder", 0.006), ("slabs", 0.008)],
    "bed": [("mud_curls", 0.020), ("pebbles", 0.006)],
    "salar": [("salt_mound", 0.010), ("salt_slabs", 0.012)],
    "basalt": [("bombs", 0.012), ("column_stub", 0.008)],
    "frost": [("penitentes", 0.012), ("rimed_rock", 0.010)],
}
SMALL_N = {"split_rock": "4–6 no planalto", "salt_pillar": "3–4 no salar", "lava_tube": "2–4 no basalto",
           "ice_needles": "3–5 na faixa gelada"}

STAGE_WATER = {"storm": None, "arid": None, "mist": R.LEVELS[1], "green": R.LEVELS[2]}
VIEWS = ("plateau", "salar", "basalt", "frost")


# ---------------------------------------------------------------------------------------------------------------
_CACHE: dict = {}


def decals():
    if "d" not in _CACHE:
        _CACHE["d"] = E.decal_set_v9()
    return _CACHE["d"]


def decors():
    if "o" not in _CACHE:
        _CACHE["o"] = E.decor_set_v9()
    return _CACHE["o"]


def forms():
    if "f" not in _CACHE:
        _CACHE["f"] = {k: fn() + (reg, tb) for k, (fn, reg, tb) in E.SMALL_FORMS.items()}
    return _CACHE["f"]


def moss(name):
    key = ("moss", name)
    if key not in _CACHE:
        _CACHE[key] = E.moss_overlay(decors()[name][0], 1100 + int(name.rsplit("_", 1)[1]))
    return _CACHE[key]


def decor_img(name, stage, region=None):
    idx, reg, tb = decors()[name]
    reg = region if (region and tb == "BASE") else reg
    if name.startswith("pebbles") and region == "bed":
        reg = "plateau"
    im = R.colorize(idx, E.ramp_for(reg, tb, stage))
    if stage == "green" and name.rsplit("_", 1)[0] in MOSSY:
        im.alpha_composite(R.colorize(moss(name), E.moss_ramp()))
    return im


# ---------------------------------------------------------------------------------------------------------------
# TAREFA 1 · basalto
# ---------------------------------------------------------------------------------------------------------------
def basalt():
    old = R.tex_basalt(fix=False)
    new = R.tex_basalt(fix=True)
    ref = np.array(Image.open(ROOT / "assets" / "sprites" / "regions" / "ground_basalt.png"))
    assert (new == ref).all() or (old == ref).all(), "a textura do script não bate com o asset"
    M.save_indexed(new, R.ramp("basalt", "arid"), OUT / "ground_basalt.png")
    BEFORE.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "assets" / "sprites" / "regions" / "ground_basalt.png", BEFORE / "regioes_v83_ground_basalt.png")
    rmp = R.ramp("basalt", "arid")
    o, n = R.colorize(old, rmp), R.colorize(new, rmp)
    # recorte 2× em volta da célula (x 64–133, y 215–290), com a caixa marcando o lugar
    box = (16, 168, 208, 344)
    for tag, im in (("antes", o), ("depois", n)):
        c = im.crop(box).resize(((box[2] - box[0]) * 3, (box[3] - box[1]) * 3), Image.NEAREST)
        if tag == "antes":
            d = ImageDraw.Draw(c)
            d.rectangle(((64 - box[0]) * 3, (215 - box[1]) * 3, (134 - box[0]) * 3, (291 - box[1]) * 3),
                        outline=(255, 106, 85), width=3)
        c.save(OUT / f"basalt_zoom_{tag}.png")
        tile = Image.new("RGBA", (TEXT * 3, TEXT * 3))
        for j in range(3):
            for i in range(3):
                tile.paste(im, (i * TEXT, j * TEXT))
        if tag == "antes":
            d = ImageDraw.Draw(tile)
            for j in range(3):
                for i in range(3):
                    d.rectangle((i * TEXT + 64, j * TEXT + 215, i * TEXT + 134, j * TEXT + 291), outline=(255, 106, 85),
                                width=2)
        tile.convert("RGB").save(OUT / f"basalt_tile3x3_{tag}.png")
        im.save(OUT / f"basalt_full_{tag}.png")
    # emenda: a textura nova continua periódica? (os 4 lados batem com o lado oposto no ruído/Voronoi)
    def seam(a):                         # fração de pixels diferentes na emenda × entre colunas/linhas vizinhas
        inner = np.mean([(a[:, i] != a[:, i + 1]).mean() for i in range(0, 511, 8)]
                        + [(a[i] != a[i + 1]).mean() for i in range(0, 511, 8)])
        return round(float(((a[:, -1] != a[:, 0]).mean() + (a[-1] != a[0]).mean()) / 2), 3), round(float(inner), 3)
    return dict(changed=int((old != new).sum()), seam_old=seam(old), seam_new=seam(new))


TEXT = R.TEX


# ---------------------------------------------------------------------------------------------------------------
# EXPORT dos pendentes
# ---------------------------------------------------------------------------------------------------------------
def export(dest=None, clean=True):
    """Salva os 70 PNGs indexados em `dest` (padrão: v9/pendentes) e devolve {arquivo: tamanho/região/rampa}."""
    dest = dest or PEND
    dest.mkdir(parents=True, exist_ok=True)
    if clean and dest == PEND:
        for old in PEND.glob("*.png"):
            old.unlink()
    files = {}
    for k, idx in decals().items():
        reg = DECALS[k.rsplit("_", 1)[0]][0]
        M.save_indexed(idx, R.ramp(reg, "arid"), dest / f"decal_{k}.png")
        files[f"decal_{k}.png"] = dict(size=f"{idx.shape[1]}×{idx.shape[0]}", region=reg, ramp="BASE")
    for k, (idx, reg, tb) in decors().items():
        assert idx.shape[1] <= 32 and idx.shape[0] <= 28, (k, idx.shape)
        M.save_indexed(idx, E.ramp_for(reg, tb, "arid"), dest / f"decor_{k}.png")
        files[f"decor_{k}.png"] = dict(size=f"{idx.shape[1]}×{idx.shape[0]}", region=reg, ramp=tb)
        if k.rsplit("_", 1)[0] in MOSSY:
            M.save_indexed(moss(k), E.moss_ramp(), dest / f"decor_{k.rsplit('_', 1)[0]}_moss_{k.rsplit('_', 1)[1]}.png")
            files[f"decor_{k.rsplit('_', 1)[0]}_moss_{k.rsplit('_', 1)[1]}.png"] = dict(
                size=f"{idx.shape[1]}×{idx.shape[0]}", region=reg, ramp="MOSS (fixa, só Verde)")
    fdata = {}
    for k, (idx, info, reg, tb) in forms().items():
        M.save_indexed(idx, E.ramp_for(reg, tb, "arid"), dest / f"form_{k}.png")
        files[f"form_{k}.png"] = dict(size=f"{idx.shape[1]}×{idx.shape[0]}", region=reg, ramp=tb)
        fdata[k] = dict(info, sprite=f"form_{k}.png", region=reg, ramp=tb, count=SMALL_N[k])
    data = dict(
        note="PROPOSTA v9 (pendente do dono). Mesmo formato do regions_palettes.json: 0..7 rampa, 8 contorno, "
             "9 sombra (alfa %d), 255 transparente. decor_*_moss_*: overlay do Verde+, 0..3 = ramps.MOSS (fixa), "
             "desenhado por cima da pedra de mesmo nome e índice, só no estágio Verde." % R.SHADOW_A,
        decal_p_v9=DECAL_P_V9, decal_mix_v9=DECAL_MIX_V9, decor_p_v9=DECOR_P_V9,
        small_formations=fdata, moss=E.MOSS, basalt_nudge={f"{k[0]},{k[1]}": v for k, v in R.BASALT_NUDGE.items()},
        files=dict(sorted(files.items())))
    if dest == PEND:
        (PEND / "regions_v9.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return files


def export_assets(dest):
    """Chamado pelo regions_mockups.export_pending: os PNGs da v9 em `dest` + o que entra no regions_palettes.json."""
    files = export(dest, clean=False)
    forms_ = {k: dict(info, sprite=f"form_{k}.png", region=reg, ramp=tb, count=SMALL_N[k], small=True)
              for k, (idx, info, reg, tb) in forms().items()}
    density = dict(note="v9 (aprovado): 3º sorteio de decalque na célula de 96 px (decal_p/decal_mix, só os nomes "
                        "da v9) e soltos novos por tile de chão livre (decor_p: chances que somam). Leito seco = bed. "
                        "Formações pequenas: count por mundo. Verde+: decor_{boulder,column_stub}_moss_N por cima da "
                        "pedra de mesmo N, só no Verde, rampa MOSS.",
                   decal_p=DECAL_P_V9, decal_mix=DECAL_MIX_V9, decor_p=DECOR_P_V9,
                   small_formations={k: SMALL_N[k] for k in forms()}, moss_on=list(MOSSY))
    return files, forms_, density


# ---------------------------------------------------------------------------------------------------------------
# PRÉVIAS do catálogo
# ---------------------------------------------------------------------------------------------------------------
def ground_patch(region, stage, w, h, seed=0):
    t = SC.tex(region)
    ox, oy = int(R.hash2(seed, 1, 5) * 300), int(R.hash2(seed, 2, 5) * 300)
    ys, xs = np.mgrid[oy:oy + h, ox:ox + w]
    return R.colorize(t[ys % R.TEX, xs % R.TEX], R.ramp(region, stage))


def catalog_previews():
    pv = OUT / "cat"
    pv.mkdir(parents=True, exist_ok=True)
    for k, idx in decals().items():
        reg = DECALS[k.rsplit("_", 1)[0]][0]
        R.colorize(idx, R.ramp(reg, "arid")).save(pv / f"decal_{k}.png")
    for k in decors():
        decor_img(k, "arid").save(pv / f"decor_{k}.png")
    for k in MOSSY:
        for v in range(3):
            decor_img(f"{k}_{v}", "green").save(pv / f"decor_{k}_{v}_green.png")
    for k, (idx, info, reg, tb) in forms().items():
        R.colorize(idx, E.ramp_for(reg, tb, "arid")).save(pv / f"form_{k}.png")
    # tira dos 4 estágios: cada tipo (as 3 variações) em cima do chão da região no estágio
    for name, (reg, _, _) in list(DECALS.items()) + list(DECORS.items()):
        kind = "decal" if name in DECALS else "decor"
        ims_by_stage = []
        for st in R.STAGES:
            ims = []
            for v in range(3):
                if kind == "decal":
                    ims.append(R.colorize(decals()[f"{name}_{v}"], R.ramp(reg, st)))
                else:
                    ims.append(decor_img(f"{name}_{v}", st, reg))
            ims_by_stage.append(ims)
        cw = sum(i.width for i in ims_by_stage[0]) + 8 * 4
        ch = max(i.height for i in ims_by_stage[0]) + 12
        strip = Image.new("RGBA", (cw * 4 + 6 * 3, ch), (21, 16, 14, 255))
        for s, ims in enumerate(ims_by_stage):
            bg = ground_patch(reg, R.STAGES[s], cw, ch, s)
            x = 8
            for im in ims:
                bg.alpha_composite(im, (x, ch - 6 - im.height))
                x += im.width + 8
            strip.paste(bg, (s * (cw + 6), 0))
        strip.save(pv / f"strip_{name}.png")
    for k, (idx, info, reg, tb) in forms().items():
        ch, cw = idx.shape[0] + 12, idx.shape[1] + 16
        strip = Image.new("RGBA", (cw * 4 + 18, ch), (21, 16, 14, 255))
        for s, st in enumerate(R.STAGES):
            bg = ground_patch(reg, st, cw, ch, s)
            bg.alpha_composite(R.colorize(idx, E.ramp_for(reg, tb, st)), (8, 6))
            strip.paste(bg, (s * (cw + 6), 0))
        strip.save(pv / f"strip_form_{k}.png")
    footprints(pv)


def footprints(pv):
    for k, (idx, info, reg, tb) in forms().items():
        img = R.colorize(idx, E.ramp_for(reg, tb, "arid"))
        fx, fy = info["foot"]
        cols, rows = 5, img.height // T + 2
        bg = Image.new("RGBA", (cols * T, rows * T), tuple(int(c) for c in R.ramp(reg, "arid")[3]) + (255,))
        d = ImageDraw.Draw(bg)
        ftx, fty = cols // 2, rows - 1
        for dx, dy in info["tiles"]:
            d.rectangle(((ftx + dx) * T, (fty + dy) * T, (ftx + dx) * T + T - 1, (fty + dy) * T + T - 1),
                        fill=(255, 106, 85, 255))
        for gx in range(0, cols * T, T):
            d.line((gx, 0, gx, rows * T), fill=(0, 0, 0, 255))
        for gy in range(0, rows * T, T):
            d.line((0, gy, cols * T, gy), fill=(0, 0, 0, 255))
        wx, wy = ftx * T + T // 2, fty * T + T - 2
        bg.alpha_composite(img, (wx - fx, wy - fy))
        for dx, dy in info["tiles"]:
            d.rectangle(((ftx + dx) * T, (fty + dy) * T, (ftx + dx) * T + T - 1, (fty + dy) * T + T - 1),
                        outline=(255, 106, 85, 255))
        d.ellipse((wx - 2, wy - 2, wx + 2, wy + 2), fill=(89, 208, 230, 255))
        bg.save(pv / f"foot_{k}.png")


# ---------------------------------------------------------------------------------------------------------------
# CENAS antes × depois
# ---------------------------------------------------------------------------------------------------------------
def region_at(world, tx, ty):
    reg = R.REG_NAMES[world["region"][ty, tx]]
    if reg == "plateau" and world["h"][ty, tx] < R.LEVELS[2]:
        return "bed"
    return reg


def near_form(tx, ty, r=4):
    return any(abs(tx - f[1][0]) < r and -r < ty - f[1][1] < 2 for f in M.FORMS)


def pick_small_forms(world, x0, y0):
    """Formações pequenas da vista: 1 ou 2 por vista, em tile livre (pegada + 1 de folga), longe das grandes."""
    out = []
    want = {"plateau": "split_rock", "salar": "salt_pillar", "basalt": "lava_tube", "frost": "ice_needles"}
    cands = []
    for ty in range(y0 // T + 3, (y0 + 540) // T - 1):
        for tx in range(x0 // T + 2, (x0 + 960) // T - 2):
            cands.append((R.hash2(tx, ty, 931), tx, ty))
    cands.sort()
    for _, tx, ty in cands:
        reg = region_at(world, tx, ty)
        if reg not in want or np.hypot(tx - 96, ty - 95) < 8 or near_form(tx, ty, 7):
            continue
        k = want[reg]
        info = forms()[k][1]
        ok = True
        for dx in range(-2, 3):
            for dy in range(-3, 2):
                xx, yy = tx + dx, ty + dy
                if world["wall"][yy, xx] or region_at(world, xx, yy) != reg:
                    ok = False
        if not ok or any(abs(tx - a) + abs(ty - b) < 10 for _, a, b in out):
            continue
        out.append((k, tx, ty))
        if len(out) >= 2:
            break
    return out


def add_v9(s, world, stage):
    x0, y0 = s.x0, s.y0
    water = s.water if s.water is not None else -1
    rocks = {(x, y) for x, y, _ in world["rocks"]}
    # formações pequenas
    taken = set()
    for k, tx, ty in pick_small_forms(world, x0, y0):
        idx, info, reg, tb = forms()[k]
        if world["h"][ty, tx] < water + 0.01:
            continue
        M.place_sprite_foot(s, R.colorize(idx, E.ramp_for(reg, tb, stage)), info, (tx, ty))
        for dx in range(-2, 3):
            for dy in range(-2, 2):
                taken.add((tx + dx, ty + dy))
    # decoração solta nova
    for ty in range(y0 // T - 2, (y0 + 540) // T + 3):
        for tx in range(x0 // T - 2, (x0 + 960) // T + 3):
            if not (1 <= tx < R.W - 1 and 1 <= ty < R.H - 1) or world["wall"][ty, tx] or world["wall"][ty + 1, tx]:
                continue
            if (tx, ty) in taken or (tx, ty) in rocks or near_form(tx, ty) or np.hypot(tx - 96, ty - 95) < 6:
                continue
            reg = region_at(world, tx, ty)
            if reg in ("basalt", "salar", "frost") and R.hash2(tx, ty, 601) < 0.035:
                continue                                           # já tem a decoração da v8 aqui
            if world["h"][ty, tx] < water + 0.01:
                continue
            r = R.hash2(tx, ty, 941)
            acc = 0.0
            for name, p in DECOR_P_V9.get(reg, []):
                acc += p
                if r < acc:
                    v = int(R.hash2(tx, ty, 942) * 3)
                    im = decor_img(f"{name}_{v}", stage, reg)
                    if R.hash2(tx, ty, 943) < 0.5:
                        im = im.transpose(Image.FLIP_LEFT_RIGHT)
                    jx = int(R.hash2(tx, ty, 944) * 14) - 7
                    M.place(s, im, tx * T + 16 + jx, ty * T + 26 + int(R.hash2(tx, ty, 945) * 4))
                    break
    # decalques novos: 3º sorteio por célula de 96 px (só os da v9), na camada do chão
    C = R.DECAL_CELL
    d = decals()
    for cy in range((y0 - 200) // C, (y0 + 540 + 200) // C + 1):
        for cx in range((x0 - 260) // C, (x0 + 960 + 260) // C + 1):
            px = cx * C + int(R.hash2(cx, cy, 952) * C)
            py = cy * C + int(R.hash2(cx, cy, 954) * C)
            tx, ty = px // T, py // T
            if not (0 <= tx < R.W and 0 <= ty < R.H) or np.hypot(tx - 96, ty - 95) < 6 or near_form(tx, ty, 3):
                continue
            reg = region_at(world, tx, ty)
            if R.hash2(cx, cy, 956) > DECAL_P_V9[reg]:
                continue
            mix_ = DECAL_MIX_V9[reg]
            tot = sum(w for _, w in mix_)
            r = R.hash2(cx, cy, 958) * tot
            for name, w in mix_:
                r -= w
                if r <= 0:
                    break
            idx = d[f"{name}_{int(R.hash2(cx, cy, 960) * 3)}"]
            if R.hash2(cx, cy, 962) < 0.5:
                idx = idx[:, ::-1]
            img = R.colorize(idx, R.ramp(reg, stage))
            s.ground_decals.append((img, px - img.width // 2, py - img.height // 2))


def scene(world, view, stage, extra):
    x0, y0 = M.view_origin(view)
    s = SC.Scene(world, x0, y0, stage=stage, water=STAGE_WATER[stage])
    cx, cy = M.VIEWS[view]
    M.populate(s, world, stage, player_at=M.nearest_floor(world, M.PLAYER.get(view, (cx, cy)), STAGE_WATER[stage]))
    if extra:
        add_v9(s, world, stage)
    overlay = {"storm": M.storm_overlay, "mist": M.rain_overlay}.get(stage)
    return s.compose(overlay).convert("RGB")


def scenes(world):
    out = []
    for view in VIEWS:
        for st in ("arid", "green"):
            for extra in (False, True):
                name = f"scene_{view}_{st}_{'depois' if extra else 'antes'}"
                scene(world, view, st, extra).save(OUT / f"{name}.png")
                out.append(name)
    for st in ("storm", "mist"):                           # os outros 2 estágios, só o depois, no planalto
        scene(world, "plateau", st, True).save(OUT / f"scene_plateau_{st}_depois.png")
    return out


# ---------------------------------------------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = basalt()
    files = export()
    catalog_previews()
    world = M.build_world()
    scenes(world)
    import regions_v9_report as RR
    page = RR.build(files, b)
    print("ok: basalto", b, "·", len(files), "pendentes ·", page)


if __name__ == "__main__":
    main()
