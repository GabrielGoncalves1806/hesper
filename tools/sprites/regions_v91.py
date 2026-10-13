#!/usr/bin/env python3
"""v9.1 · APROVADO pelo dono: fumarolas ativas que acordam com o calor (Marco 3).

    python3 tools/sprites/regions_v91.py

Os sprites e os dados entram em assets/sprites/regions/ pelo regions_mockups.py (export_pending chama
export_assets() daqui). Este script gera as prévias, a fumaça, as cenas, o GIF e a seção v9.1 do report
(reports/design/regioes/v91/, injetada no index acima da v9); v91/pendentes/ fica de registro.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import regions_core as R  # noqa: E402
import regions_mockups as M  # noqa: E402
import regions_scene as SC  # noqa: E402
import regions_v9 as V9  # noqa: E402
import regions_vents as VT  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "reports" / "design" / "regioes" / "v91"
PEND = OUT / "pendentes"
T = 32
KINDS = ("cone", "pair", "chimney")
KIND_PT = {"cone": "Cone baixo", "pair": "Par de cones", "chimney": "Chaminé"}
COUNT = {"cone": [2, 3], "pair": [1, 2], "chimney": [1, 2]}      # por mundo, no basalto
WIND = {"storm": (34.0, 5.0), "arid": (9.0, 1.0), "mist": (5.0, 0.5), "green": (7.0, 1.0)}
FPS = 8
LOOP = 4.0
DENSITY = dict(per_world="5–8 no basalto (cone 2–3, par 1–2, chaminé 1–2)",
               rule="inteira no basalto com 2 tiles de folga na mesma região, fora de bacia, a 26+ tiles da base, "
                    "a 8+ tiles uma da outra e 6+ das formações grandes; de preferência em grupo (campo de fumarolas): "
                    "60% sorteadas num raio de 10–30 tiles do cone de escória, o resto livre no basalto. Não "
                    "nascem no bolsão nem no avental dos gelos-portão.",
               wake="cada fumarola sorteia um limiar de calor entre o calor da etapa 1 e o da etapa 4 da tampa da "
                    "cratera (o mesmo índice de calor do Marco 3): abaixo, dormente; acima, ativa. Assim elas "
                    "acordam aos poucos enquanto o gelo da cratera derrete. Na troca, 1 s de transição: a fumaça "
                    "começa com 1/3 da taxa e sobe; o sprite troca na hora (o brilho é leve).")

_C: dict = {}


def vent(kind, active):
    key = (kind, active)
    if key not in _C:
        _C[key] = VT.vent(kind, active)
    return _C[key]


def export(dest=None):
    dest = dest or PEND
    dest.mkdir(parents=True, exist_ok=True)
    if dest == PEND:
        for old in PEND.glob("*.png"):
            old.unlink()
    forms, files = {}, {}
    for kind in KINDS:
        for st, act in (("dormant", False), ("active", True)):
            idx, info = vent(kind, act)
            name = f"form_vent_{kind}_{st}.png"
            M.save_indexed(idx, VT.vent_ramp("arid"), dest / name)
            files[name] = dict(size=f"{idx.shape[1]}×{idx.shape[0]}", region="basalt", ramp="HILL+VENT")
        forms[f"vent_{kind}"] = dict(foot=info["foot"], tiles=info["tiles"], size=info["size"], name=info["name"],
                                     sprites={"dormant": f"form_vent_{kind}_dormant.png",
                                              "active": f"form_vent_{kind}_active.png"},
                                     sprite=f"form_vent_{kind}_dormant.png",
                                     mouths=info["mouths"], region="basalt", ramp="HILL+VENT",
                                     count=COUNT[kind], small=True)
    vent_ramps = {st: [R.hexc(c) for c in VT.vent_ramp(st)[10:14]] for st in R.STAGES}
    data = dict(note="v9.1 (aprovado pelo dono). 0..9 = HILL do basalto (como as formações), 10..13 = ramps.VENT[estágio]: "
                     "10 enxofre escuro, 11 enxofre claro (seguem o estágio), 12 brasa, 13 brasa clara (fixas). "
                     "mouths = px do sprite de onde sai a fumaça (partícula, não sprite).",
                formations=forms, ramps={"VENT": vent_ramps}, smoke=VT.SMOKE, density=DENSITY, files=files)
    if dest == PEND:
        (PEND / "regions_v91.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return files, forms


def export_assets(dest):
    """Chamado pelo regions_mockups.export_pending: os 6 PNGs em `dest` + o que entra no regions_palettes.json."""
    files, forms = export(dest)
    vent = {"basalt": {st: [R.hexc(c) for c in VT.vent_ramp(st)[10:14]] for st in R.STAGES}}
    density = dict(DENSITY, count=COUNT, note="v9.1 (aprovado): fumarolas do basalto. Sprite _dormant abaixo do "
                   "limiar de calor, _active acima. Paleta 0..9 = ramps.HILL.basalt, 10..13 = ramps.VENT.basalt "
                   "(10, 11 enxofre, seguem o estágio; 12, 13 brasa, fixas). A fumaça é partícula (bloco smoke), "
                   "saindo das mouths (px do sprite).")
    return files, forms, vent, VT.SMOKE, density


def bg_color(stage="arid"):
    return tuple(int(c) for c in R.ramp("basalt", stage)[3]) + (255,)


def previews():
    cat = OUT / "cat"
    cat.mkdir(parents=True, exist_ok=True)
    for kind in KINDS:
        for st, act in (("dormant", False), ("active", True)):
            idx, info = vent(kind, act)
            R.colorize(idx, VT.vent_ramp("arid")).save(cat / f"vent_{kind}_{st}.png")
        # tira dos 4 estágios: dormente e ativa lado a lado em cada estágio
        idx0, info = vent(kind, False)
        idx1, _ = vent(kind, True)
        w, h = idx0.shape[1], idx0.shape[0]
        cw, ch = 2 * w + 18, h + 12
        strip = Image.new("RGBA", (cw * 4 + 18, ch), (21, 16, 14, 255))
        for s, stg in enumerate(R.STAGES):
            bg = V9.ground_patch("basalt", stg, cw, ch, s + 7)
            bg.alpha_composite(R.colorize(idx0, VT.vent_ramp(stg)), (6, 6))
            bg.alpha_composite(R.colorize(idx1, VT.vent_ramp(stg)), (12 + w, 6))
            strip.paste(bg, (s * (cw + 6), 0))
        strip.save(cat / f"strip_vent_{kind}.png")
        # pegada
        img = R.colorize(idx0, VT.vent_ramp("arid"))
        fx, fy = info["foot"]
        cols, rows = 5, img.height // T + 2
        g = Image.new("RGBA", (cols * T, rows * T), bg_color())
        d = ImageDraw.Draw(g)
        ftx, fty = 2, rows - 1
        for dx, dy in info["tiles"]:
            d.rectangle(((ftx + dx) * T, (fty + dy) * T, (ftx + dx) * T + T - 1, (fty + dy) * T + T - 1),
                        fill=(255, 106, 85, 255))
        for gx in range(0, cols * T, T):
            d.line((gx, 0, gx, rows * T), fill=(0, 0, 0, 255))
        for gy in range(0, rows * T, T):
            d.line((0, gy, cols * T, gy), fill=(0, 0, 0, 255))
        fw = max(dx for dx, _ in info["tiles"]) + 1
        wx, wy = ftx * T + fw * T // 2, fty * T + T            # centro de baixo da pegada
        g.alpha_composite(img, (wx - fx, wy - fy))
        for dx, dy in info["tiles"]:
            d.rectangle(((ftx + dx) * T, (fty + dy) * T, (ftx + dx) * T + T - 1, (fty + dy) * T + T - 1),
                        outline=(255, 106, 85, 255))
        d.ellipse((wx - 2, wy - 2, wx + 2, wy + 2), fill=(89, 208, 230, 255))
        for mx, my in info["mouths"]:
            d.rectangle((wx - fx + mx - 1, wy - fy + my - 1, wx - fx + mx + 1, wy - fy + my + 1), outline=(242, 196, 109, 255))
        g.save(cat / f"foot_vent_{kind}.png")


def smoke_strips():
    """Folha de quadros (1 linha, LOOP·FPS quadros) de cada fumarola ativa soltando fumaça, pro CSS animar."""
    out = {}
    n = int(LOOP * FPS)
    for kind in KINDS:
        idx, info = vent(kind, True)
        spr = R.colorize(idx, VT.vent_ramp("arid"))
        fw, fh = max(80, spr.width + 24), spr.height + 70
        sheet = Image.new("RGBA", (fw * n, fh))
        ox, oy = (fw - spr.width) // 2, fh - spr.height - 4
        for f in range(n):
            fr = Image.new("RGBA", (fw, fh), bg_color())
            fr.alpha_composite(spr, (ox, oy))
            for j, (mx, my) in enumerate(info["mouths"]):
                sm = VT.smoke_frame(fw, fh, f / FPS, (ox + mx, oy + my), seed=40 + j, kind=kind, wind=WIND["arid"])
                fr.alpha_composite(Image.fromarray(sm))
            sheet.paste(fr, (f * fw, 0))
        sheet.save(OUT / f"smoke_{kind}.png")
        out[kind] = (fw, fh, n)
    # o puff sozinho: a vida de 1 puff em 8 passos (sem vento)
    life = Image.new("RGBA", (8 * 40, 80), bg_color())
    for i in range(8):
        f = i / 7
        rad = 2 + (7 - 2) * (1 - (1 - f) ** 2)
        a = VT.SMOKE["alpha"][0] if f < 0.35 else (VT.SMOKE["alpha"][1] if f < 0.7 else VT.SMOKE["alpha"][2])
        cols = [np.array(R.rgb(c)) for c in VT.SMOKE["color"]]
        ys, xs = np.mgrid[0:80, 0:40]
        py = 70 - 50 * f
        d = np.hypot(xs - 20, (ys - py) * 1.1)
        body = d <= rad
        core = np.hypot(xs - (20 - rad * .3), ys - (py - rad * .3)) <= rad * .55
        low = body & (ys > py + rad * .35)
        arr = np.zeros((80, 40, 4), np.uint8)
        col = np.where(core[..., None], cols[0], np.where(low[..., None], cols[2], cols[1]))
        arr[body, :3] = col[body]
        arr[body, 3] = a
        life.alpha_composite(Image.fromarray(arr), (i * 40, 0))
    life.save(OUT / "smoke_puff_life.png")
    return out


def place_vents(world, x0, y0):
    """3 fumarolas na vista do basalto: tiles livres (pegada + folga), longe das formações e uma da outra."""
    taken = [(k, tx, ty) for k, tx, ty in V9.pick_small_forms(world, x0, y0)]
    out = []
    # campo de fumarolas: as 3 juntas numa janela de 15×8 tiles (cabe no recorte animado de 480×270)
    wx0, wy0 = x0 // T + 15, y0 // T + 8
    cands = sorted((R.hash2(tx, ty, 971), tx, ty) for ty in range(wy0, wy0 + 8) for tx in range(wx0, wx0 + 13))
    for _, tx, ty in cands:
        if V9.region_at(world, tx, ty) != "basalt" or V9.near_form(tx, ty, 6):
            continue
        if any(abs(tx - a) + abs(ty - b) < 5 for _, a, b in taken + out):
            continue
        ok = all(not world["wall"][ty + dy, tx + dx] and V9.region_at(world, tx + dx, ty + dy) == "basalt"
                 for dx in range(-2, 4) for dy in range(-3, 2))
        if not ok:
            continue
        out.append((KINDS[len(out)], tx, ty))
        if len(out) == 3:
            break
    return out


def vent_scene(world, stage, active):
    """Cena do basalto (como a v9 aprovada) com as fumarolas. Devolve (imagem sem fumaça, [(boca px na tela, tipo)])."""
    x0, y0 = M.view_origin("basalt")
    s = SC.Scene(world, x0, y0, stage=stage, water=V9.STAGE_WATER[stage])
    cx, cy = M.VIEWS["basalt"]
    M.populate(s, world, stage, player_at=M.nearest_floor(world, M.PLAYER.get("basalt", (cx, cy)),
                                                           V9.STAGE_WATER[stage]))
    V9.add_v9(s, world, stage)
    mouths = []
    for kind, tx, ty in place_vents(world, x0, y0):
        idx, info = vent(kind, active)
        img = R.colorize(idx, VT.vent_ramp(stage))
        fw = max(dx for dx, _ in info["tiles"]) + 1
        bx, by = tx * T + fw * T // 2, ty * T + T                # centro de baixo da pegada
        fx, fy = info["foot"]
        s.objects.append((by - 1, img, bx - fx, by - fy))
        for mx, my in info["mouths"]:
            mouths.append(((bx - fx + mx - x0, by - fy + my - y0), kind))
    overlay = {"storm": M.storm_overlay, "mist": M.rain_overlay}.get(stage)
    return s.compose(overlay), mouths


def with_smoke(img, mouths, t, stage):
    im = img.copy()
    for j, ((mx, my), kind) in enumerate(mouths):
        w, h = 140, 120
        sm = VT.smoke_frame(w, h, t, (w // 2, h - 6), seed=60 + j, kind=kind, wind=WIND[stage], stage=stage)
        part = Image.fromarray(sm)
        im.alpha_composite(part, (mx - w // 2, my - h + 6))
    return im


def scenes(world):
    out = {}
    for stage in ("arid", "storm", "mist", "green"):
        dormant, _ = vent_scene(world, stage, False)
        active, mouths = vent_scene(world, stage, True)
        dormant.convert("RGB").save(OUT / f"scene_{stage}_dormant.png")
        with_smoke(active, mouths, 1.3, stage).convert("RGB").save(OUT / f"scene_{stage}_active.png")
        out[stage] = mouths
        if stage == "arid":
            # recorte animado em volta das fumarolas: GIF + quadros pro CSS
            xs = [m[0][0] for m in mouths]
            ys = [m[0][1] for m in mouths]
            cx = int(np.clip((min(xs) + max(xs)) / 2 - 240, 0, 480))
            cy = int(np.clip(max(ys) + 60 - 270, 0, 270))
            box = (cx, cy, cx + 480, cy + 270)
            frames = []
            n = int(LOOP * FPS)
            for f in range(n):
                frames.append(with_smoke(active, mouths, f / FPS, stage).crop(box).convert("RGB"))
            pal = frames[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
            q = [fr.quantize(palette=pal, dither=Image.Dither.NONE) for fr in frames]
            q[0].save(OUT / "vents_active.gif", save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0,
                      optimize=False, disposal=1)
            sheet = Image.new("RGB", (480 * n, 270))
            for f, fr in enumerate(frames):
                sheet.paste(fr, (f * 480, 0))
            sheet.save(OUT / "vents_active_frames.png")
            dormant.crop(box).convert("RGB").save(OUT / "vents_dormant_crop.png")
            panel = Image.new("RGB", (480 * 2 + 8, 270 * 2 + 8), (21, 16, 14))
            for i, f in enumerate((0, 8, 16, 24)):
                panel.paste(frames[f], ((i % 2) * 488, (i // 2) * 278))
            panel.save(OUT / "vents_active_panel.png")
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files, forms = export()
    previews()
    strips = smoke_strips()
    world = M.build_world()
    scenes(world)
    import regions_v91_report as RR
    page = RR.build(files, forms, strips)
    print("ok:", len(files), "pendentes v9.1 ·", page)


if __name__ == "__main__":
    main()
