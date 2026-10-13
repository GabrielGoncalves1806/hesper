#!/usr/bin/env python3
"""v9.2 · PROPOSTA (M3.5): gelo-portão em blocos que derretem cada um no seu ritmo.

    python3 tools/sprites/regions_v92.py

Gera em reports/design/regioes/v92/: os pendentes (pendentes/ice_block_*.png + regions_v92.json), as prévias de
cada bloco nas 8 escalas e nos 4 estágios, a sequência de derretimento de cada arranjo com as caixas de colisão
e a busca de caminho (quando abre a fresta), um GIF, as cenas no Árido e no Verde e a seção v9.2 do report
(injetada no reports/design/regioes/index.html, acima da v9.1). Nada vai pra assets/ sem o ok do dono.
"""

from __future__ import annotations

import json
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import regions_core as R  # noqa: E402
import regions_ice_blocks as B  # noqa: E402

ROOT = HERE.parents[1]
REG = ROOT / "reports" / "design" / "regioes"
OUT = REG / "v92"
PEND = OUT / "pendentes"
T = 32
PLAYER_BOX = (14, 8)                 # C.PLAYER_BOX_W, C.PLAYER_BOX_H (caixa nos pés, âncora no meio de baixo)
CORRIDOR = 128                       # 4 tiles
DEPTH = 64                           # 2 tiles (a pegada 4×2 de hoje)
ICE_RAMP_TABLE = {"frost": R.ICE}

# ---- receitas de amontoado ----------------------------------------------------------------------------------------
# (x, y) = onde a âncora do bloco cai, relativo ao base_px do portão (centro da borda de baixo da caixa 4×2 de hoje).
# melt = (começa, termina) na fração p do derretimento do portão (0 = inteiro, 1 = aberto). Entre os dois o bloco
# passa pelas 8 escalas; depois de `termina` ele some (sem sprite, sem colisão).
RECIPES = {
    "A": dict(name="Muralha (5 blocos)", blocks=[
        dict(b="slab_1", x=-30, y=-30, melt=(0.46, 1.00)),
        dict(b="shard_1", x=22, y=-34, melt=(0.26, 0.80)),
        dict(b="boulder_0", x=50, y=-26, melt=(0.41, 0.92)),
        dict(b="boulder_1", x=-44, y=-2, melt=(0.16, 0.70)),
        dict(b="shard_0", x=4, y=-4, melt=(0.36, 0.88)),
    ]),
    "B": dict(name="Lasca no meio (4 blocos)", blocks=[
        dict(b="boulder_1", x=-46, y=-28, melt=(0.44, 0.90)),
        dict(b="shard_1", x=-6, y=-34, melt=(0.54, 1.00)),
        dict(b="slab_0", x=34, y=-28, melt=(0.29, 0.85)),
        dict(b="slab_1", x=-22, y=-2, melt=(0.24, 0.72)),
    ]),
    "C": dict(name="Duas lajes (3 blocos)", blocks=[
        dict(b="slab_0", x=-30, y=-28, melt=(0.40, 0.95)),
        dict(b="slab_1", x=28, y=-32, melt=(0.30, 0.85)),
        dict(b="boulder_0", x=-2, y=-4, melt=(0.50, 1.00)),
    ]),
}


def block_key(b):
    kind, v = b.rsplit("_", 1)
    return kind, int(v)


def frame_at(melt, p):
    """Índice da escala (0..7) no progresso p, ou None se o bloco já sumiu."""
    t0, t1 = melt
    if p < t0:
        return 0
    if p >= t1:
        return None
    return min(len(B.SCALES) - 1, int((p - t0) / (t1 - t0) * len(B.SCALES)))


_COL: dict = {}


def col(kind, v, k):
    key = (kind, v, k)
    if key not in _COL:
        _COL[key] = B.collision(kind, v, B.SCALES[k])
    return _COL[key]


def rects_at(recipe, p):
    out = []
    for blk in RECIPES[recipe]["blocks"]:
        k = frame_at(blk["melt"], p)
        if k is None:
            continue
        kind, v = block_key(blk["b"])
        r = col(kind, v, k)
        if r:
            out.append((blk["x"] + r[0], blk["y"] + r[1], r[2], r[3]))
    return out


def passable(rects, path=False):
    """Busca de caminho em px: o player (14×8, âncora no meio de baixo) vai do avental (y = +20) pro bolsão
    (y = −DEPTH − 16)? Paredes de BEDROCK em |x| > 64 na faixa −64 ≤ y ≤ 0."""
    x0, x1, y0, y1 = -96, 96, -DEPTH - 24, 28
    W, H = x1 - x0, y1 - y0
    pw, ph = PLAYER_BOX
    occ = np.zeros((H, W), bool)
    walls = [(-200, -DEPTH, 200 - CORRIDOR // 2, DEPTH), (CORRIDOR // 2, -DEPTH, 200, DEPTH)]
    for rx, ry, rw, rh in list(rects) + walls:
        # o player em (px, py) ocupa [px − 7, px + 7) × [py − 8, py): bate se cruza o retângulo
        ax0, ax1 = rx - pw // 2 + 1, rx + rw + pw // 2
        ay0, ay1 = ry + 1, ry + rh + ph
        ax0, ax1 = max(ax0, x0), min(ax1, x1)
        ay0, ay1 = max(ay0, y0), min(ay1, y1)
        if ax0 < ax1 and ay0 < ay1:
            occ[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0] = True
    start = [(H - 2, x) for x in range(W) if not occ[H - 2, x]]
    seen = np.zeros_like(occ)
    prev = {}
    q = deque()
    for s in start:
        seen[s] = True
        q.append(s)
    goal = None
    while q:
        y, x = q.popleft()
        if y == 1:
            goal = (y, x)
            break
        for dy, dx in ((-1, 0), (0, -1), (0, 1), (1, 0)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and not occ[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                prev[(ny, nx)] = (y, x)
                q.append((ny, nx))
    if not path:
        return goal is not None
    pts = []
    while goal is not None:
        pts.append((goal[1] + x0, goal[0] + y0))
        goal = prev.get(goal)
    return pts


def open_at(recipe, step=0.01):
    p = 0.0
    while p <= 1.0001:
        if passable(rects_at(recipe, p)):
            return round(p, 2)
        p += step
    return None


# ---- export ---------------------------------------------------------------------------------------------------
def save_indexed(idx, ramp_rgb, path):
    im = Image.frombytes("P", (idx.shape[1], idx.shape[0]), np.ascontiguousarray(idx).tobytes())
    pal = [0] * 768
    for i, c in enumerate(ramp_rgb):
        pal[i * 3:i * 3 + 3] = [int(v) for v in c]
    im.putpalette(pal)
    trns = bytes([255] * 9 + [R.SHADOW_A] + [255] * (255 - 10) + [0])
    im.save(path, transparency=trns)


def ice_ramp(stage):
    return R.ramp("frost", stage, ICE_RAMP_TABLE)


def blocks_data():
    out, files = {}, {}
    for kind in B.KINDS:
        for v in (0, 1):
            w, h, ox, oy, _ = B.frame_box(kind, v)
            name = f"ice_block_{kind}_{v}.png"
            out[f"{kind}_{v}"] = dict(
                name=f"{B.BLOCKS[kind]['name']} {v + 1}", sprite=name, frame=[w, h], frames=len(B.SCALES),
                scales=list(B.SCALES), anchor=[ox, oy],
                collision=[col(kind, v, k) for k in range(len(B.SCALES))])
            files[name] = dict(size=f"{w * len(B.SCALES)}×{h}", frame=f"{w}×{h}", region="frost", ramp="ICE")
    return out, files


def export(dest=None):
    dest = dest or PEND
    dest.mkdir(parents=True, exist_ok=True)
    if dest == PEND:
        for old in PEND.glob("*.png"):
            old.unlink()
    for kind in B.KINDS:
        for v in (0, 1):
            save_indexed(B.strip(kind, v), ice_ramp("arid"), dest / f"ice_block_{kind}_{v}.png")
    blocks, files = blocks_data()
    recipes = {k: dict(name=r["name"], blocks=r["blocks"], opens_at=open_at(k)) for k, r in RECIPES.items()}
    data = dict(
        note="v9.2 (PROPOSTA, M3.5): gelo-portão em blocos. Cada ice_block_<tipo>_<v>.png é uma tira de "
             "`frames` quadros de `frame` px, um por escala (`scales`, do inteiro ao último caquinho), todos com a "
             "mesma âncora (centro da base no chão). collision[k] = [x, y, w, h] da base no quadro k, em px do mundo "
             "relativos à âncora (y negativo = pra trás). PNG indexado como as formações: 1..6 rampa ICE, 8 "
             "contorno, 9 sombra (alfa 80), 255 transparente; recolore por ramps.ICE.frost[estágio].",
        blocks=blocks, recipes=recipes,
        recipe_rule="(x, y) = âncora do bloco relativa ao base_px do portão (centro da borda de baixo da caixa 4×2). "
                    "melt = (começa, termina) na fração p do derretimento do portão. Antes de `começa`: quadro 0. "
                    "Entre os dois: quadro = int((p − começa)/(termina − começa)·8). Em `termina` some. "
                    "A seed do portão escolhe A, B ou C.",
        draw="cada bloco é um objeto do build_draw_list, ordenado pelo y do pé (base_px.y + y); frost_ring no chão "
             "a partir de p > 0 (camada de decalques, como hoje)",
        player_box=list(PLAYER_BOX), files=files)
    if dest == PEND:
        (PEND / "regions_v92.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return data


# ---- prévias --------------------------------------------------------------------------------------------------
def bg(stage="arid"):
    return tuple(int(c) for c in R.ramp("frost", stage)[3]) + (255,)


def previews():
    cat = OUT / "cat"
    cat.mkdir(parents=True, exist_ok=True)
    import regions_v9 as V9
    for kind in B.KINDS:
        for v in (0, 1):
            st = B.strip(kind, v)
            R.colorize(st, ice_ramp("arid")).save(cat / f"ice_block_{kind}_{v}.png")
            # tira com as caixas de colisão e a âncora (fundo do chão gelado)
            w, h, ox, oy, _ = B.frame_box(kind, v)
            n = len(B.SCALES)
            im = V9.ground_patch("frost", "arid", w * n, h, 3 + v)
            im.alpha_composite(R.colorize(st, ice_ramp("arid")))
            d = ImageDraw.Draw(im)
            for k in range(n):
                r = col(kind, v, k)
                if r:
                    d.rectangle((k * w + ox + r[0], oy + r[1], k * w + ox + r[0] + r[2] - 1, oy + r[1] + r[3] - 1),
                                outline=(255, 106, 85, 255))
                d.point((k * w + ox, oy), fill=(89, 208, 230, 255))
                if k:
                    d.line((k * w, 0, k * w, h), fill=(0, 0, 0, 90))
            im.save(cat / f"boxes_{kind}_{v}.png")
        # 4 estágios: o quadro 0 e o 4 de cada variação
        cells = []
        for stg in R.STAGES:
            for v in (0, 1):
                w, h, ox, oy, _ = B.frame_box(kind, v)
                for k in (0, 4):
                    cells.append((stg, v, k, w, h))
        cw = max(c[3] for c in cells)
        chh = max(c[4] for c in cells)
        out = Image.new("RGBA", (cw * 4 * len(R.STAGES) + 6 * (len(R.STAGES) - 1), chh), (21, 16, 14, 255))
        for si, stg in enumerate(R.STAGES):
            patch = V9.ground_patch("frost", stg, cw * 4, chh, si + 11)
            for j, (v, k) in enumerate(((0, 0), (0, 4), (1, 0), (1, 4))):
                w, h, ox, oy, _ = B.frame_box(kind, v)
                idx = B.render(kind, v, B.SCALES[k])
                patch.alpha_composite(R.colorize(idx, ice_ramp(stg)), (j * cw + (cw - w) // 2, chh - h))
            out.paste(patch, (si * (cw * 4 + 6), 0))
        out.save(cat / f"stages_{kind}.png")


# ---- diagrama do derretimento ---------------------------------------------------------------------------------
DW, DH = 232, 200
BX, BY = 116, 150                    # base_px do portão no diagrama


def hill_cols(stage):
    rmp = R.ramp("frost", stage, R.HILL)
    return [tuple(int(c) for c in rmp[i]) + (255,) for i in range(8)]


def corridor_bg(stage, seed=5):
    import regions_v9 as V9
    im = V9.ground_patch("frost", stage, DW, DH, seed)
    return im


def draw_walls(im, stage, front):
    """Paredes de BEDROCK dos dois lados (topo elevado 24 px + face), igual aos morros: `front` = só a face."""
    d = ImageDraw.Draw(im)
    hc = hill_cols(stage)
    out = (27, 22, 48, 255)
    for x0, x1 in ((0, BX - CORRIDOR // 2), (BX + CORRIDOR // 2, DW)):
        top0, top1 = BY - DEPTH - 24, BY - 24
        if not front:
            d.rectangle((x0, top0, x1 - 1, top1 - 1), fill=hc[4])
            d.rectangle((x0, top0, x1 - 1, top0 + 1), fill=hc[5])
        else:
            d.rectangle((x0, top1, x1 - 1, BY - 1), fill=hc[2])
            for yy in range(top1 + 5, BY, 7):
                d.line((x0, yy, x1 - 1, yy), fill=hc[1])
            d.line((x0, BY - 1, x1 - 1, BY - 1), fill=hc[0])
        xe = x1 - 1 if x0 == 0 else x0
        d.line((xe, top0 if not front else top1, xe, BY - 1), fill=out)


def gate_layer(recipe, p, stage):
    """Os blocos do arranjo no progresso p, ordenados pelo pé: [(pé_y, img, x, y)] no espaço do diagrama."""
    objs = []
    for blk in RECIPES[recipe]["blocks"]:
        k = frame_at(blk["melt"], p)
        if k is None:
            continue
        kind, v = block_key(blk["b"])
        w, h, ox, oy, _ = B.frame_box(kind, v)
        img = R.colorize(B.render(kind, v, B.SCALES[k]), ice_ramp(stage))
        objs.append((blk["y"], img, BX + blk["x"] - ox, BY + blk["y"] - oy))
    return sorted(objs, key=lambda o: o[0])


def melt_frame(recipe, p, stage="arid", boxes=True):
    from regions_formations import frost_ring
    im = corridor_bg(stage)
    if p > 0:
        ring = R.colorize(frost_ring(), R.ramp("frost", stage))
        im.alpha_composite(ring, (BX - ring.width // 2, BY - 60 - ring.height // 2 + 4))
    draw_walls(im, stage, front=False)
    for _, img, x, y in gate_layer(recipe, p, stage):
        im.alpha_composite(img, (x, y))
    draw_walls(im, stage, front=True)
    if boxes:
        d = ImageDraw.Draw(im)
        rects = rects_at(recipe, p)
        path = passable(rects, path=True)
        for rx, ry, rw, rh in rects:
            d.rectangle((BX + rx, BY + ry, BX + rx + rw - 1, BY + ry + rh - 1), outline=(255, 106, 85, 255))
        if path:
            pts = [(BX + x, BY + y) for x, y in path[::3]]
            d.line(pts, fill=(127, 214, 122, 255), width=1)
            # a caixa do player no ponto mais apertado (no meio da faixa do portão)
            mid = min(path, key=lambda q: abs(q[1] + DEPTH // 2))
            d.rectangle((BX + mid[0] - 7, BY + mid[1] - 8, BX + mid[0] + 6, BY + mid[1] - 1), outline=(127, 214, 122, 255))
        d.point((BX, BY), fill=(89, 208, 230, 255))
    return im


PS = (0.0, 0.15, 0.3, 0.45, 0.6, 0.7, 0.8, 0.9, 1.0)


def melt_strips():
    out = {}
    for rk in RECIPES:
        frames = [melt_frame(rk, p) for p in PS]
        sheet = Image.new("RGBA", (DW * len(PS) + 4 * (len(PS) - 1), DH), (21, 16, 14, 255))
        for i, f in enumerate(frames):
            sheet.paste(f, (i * (DW + 4), 0))
        sheet.save(OUT / f"melt_{rk}.png")
        out[rk] = [(p, passable(rects_at(rk, p))) for p in PS]
    # GIF do arranjo A (com caixas) + versão limpa, 60 passos
    n = 60
    for rk in RECIPES:
        for tag, boxes in (("boxes", True), ("clean", False)):
            fr = []
            for i in range(n + 12):
                p = min(1.0, i / n)
                fr.append(melt_frame(rk, p, boxes=boxes).convert("RGB"))
            pal = fr[0].quantize(colors=255, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
            q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in fr]
            q[0].save(OUT / f"melt_{rk}_{tag}.gif", save_all=True, append_images=q[1:], duration=120, loop=0,
                      disposal=1)
    return out


# ---- cenas ----------------------------------------------------------------------------------------------------
def scene(stage, recipe, p):
    import regions_mockups as M
    import regions_scene as SC
    import regions_v9 as V9
    from regions_formations import frost_ring
    world = _world()
    x0, y0 = M.view_origin("frost")
    s = SC.Scene(world, x0, y0, stage=stage, water=V9.STAGE_WATER[stage])
    saved = M.GATES
    M.GATES = []
    try:
        M.populate(s, world, stage, player_at=M.nearest_floor(world, M.PLAYER["frost"], V9.STAGE_WATER[stage]))
        V9.add_v9(s, world, stage)
    finally:
        M.GATES = saved
    gx, gy = saved[0][0]
    bx, by = gx * T + T // 2, gy * T + T - 2
    # nada solto em cima do amontoado (no jogo o avental e a pegada do portão ficam no keep_clear)
    s.objects = [o for o in s.objects if o[1].width <= 32 and o[1].height <= 32 and o[3] + o[1].height < by - 90
                 or not (abs(o[2] + o[1].width / 2 - bx) < 110 and -40 < o[0] - by < 50)]
    if p > 0:
        ring = R.colorize(frost_ring(), R.ramp("frost", stage))
        s.under_decals.append((ring, bx - ring.width // 2, by - 60 - ring.height // 2 + 4))
    for blk in RECIPES[recipe]["blocks"]:
        k = frame_at(blk["melt"], p)
        if k is None:
            continue
        kind, v = block_key(blk["b"])
        w, h, ox, oy, _ = B.frame_box(kind, v)
        img = R.colorize(B.render(kind, v, B.SCALES[k]), ice_ramp(stage))
        s.objects.append((by + blk["y"], img, bx + blk["x"] - ox, by + blk["y"] - oy))
    overlay = {"storm": M.storm_overlay, "mist": M.rain_overlay}.get(stage)
    return s.compose(overlay).convert("RGB")


_W: dict = {}


def _world():
    if "w" not in _W:
        import regions_mockups as M
        _W["w"] = M.build_world()
    return _W["w"]


def scenes():
    for stage in ("arid", "green"):
        for p, tag in ((0.0, "inteiro"), (0.62, "derretendo")):
            im = scene(stage, "A", p)
            im.save(OUT / f"scene_{stage}_{tag}.png")
            im.crop((336, 230, 656, 410)).save(OUT / f"crop_{stage}_{tag}.png")


# ---- report ---------------------------------------------------------------------------------------------------
def inject(sec, note, css):
    page = REG / "index.html"
    html = page.read_text(encoding="utf-8")
    html = re.sub(r"<!-- v92:begin -->.*?<!-- v92:end -->\n*", "", html, flags=re.S)
    html = re.sub(r"<!-- v92note:begin -->.*?<!-- v92note:end -->\n?", "", html, flags=re.S)
    html = re.sub(r"/\* v92css \*/.*?/\* /v92css \*/\n?", "", html, flags=re.S)
    html = html.replace("</style>", "/* v92css */" + css + "/* /v92css */\n</style>", 1)
    html = html.replace("<!-- v91note:begin -->", note + "\n<!-- v91note:begin -->", 1)
    html = html.replace("<!-- v91:begin -->", sec + "\n\n<!-- v91:begin -->", 1)
    html = re.sub(r"<title>.*?</title>", "<title>Hesper · Geografia nova · v9.2</title>", html, count=1)
    html = re.sub(r'<div class="eyebrow">.*?</div>',
                  '<div class="eyebrow">Hesper · Designer · v9.2 · proposta: gelo-portão em blocos (a v9.1 e a v9 '
                  'aprovadas continuam abaixo)</div>', html, count=1)
    page.write_text(html, encoding="utf-8")
    return page


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = export()
    previews()
    opens = melt_strips()
    scenes()
    import regions_v92_report as RR
    sec, note, css = RR.build(data, opens)
    page = inject(sec, note, css)
    for k, r in data["recipes"].items():
        print(f"arranjo {k}: fresta abre em p = {r['opens_at']}")
    print("ok: v9.2 ->", page)


if __name__ == "__main__":
    main()
