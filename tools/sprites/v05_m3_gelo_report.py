#!/usr/bin/env python3
"""Report do v0.5 M3 · item 2 (faixa gelada): cenas antes × depois nos 4 estágios, folhas ampliadas e o index.html.

    python3 tools/sprites/v05_m3_gelo_report.py      (o v05_m3_gelo.py chama sozinho no fim)

As cenas usam SÓ os PNGs: antes = assets/sprites/ de hoje + o regions_palettes.json de hoje; depois = os pendentes
(reports/design/v05_m3_gelo/pendentes/) + o JSON novo. Ordem de desenho igual à do jogo: chão assado (textura,
decalques, cobertura do estágio), depois os objetos por linha do pé (morro, rocha pequena, soltos, player), com o
topo do morro em (x, y − 24) e a face em (x, y + 8), e o minério por cima do topo.
A cobertura do estágio (umidade da Névoa, grama do Verde) é a do game/ground.py, refeita aqui só pra prévia.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import regions_core as R  # noqa: E402
import v05_m3_gelo as G  # noqa: E402
from regions_core import grid, hash2  # noqa: E402

OUT = G.OUT
IMG = OUT / "img"
ASSETS = G.ASSETS
REG = G.REGIONS
PEND, PREG = G.PEND, G.PREG
T = 32
SW, SH = 480, 270
STAGE_NAME = {"storm": "Tempestade", "arid": "Árido", "mist": "Névoa", "green": "Verde"}
GRASS = ["#2f5a2a", "#3f6e30", "#4d7a39", "#5f9442", "#79b04f", "#9ccc62"]
MIST_DAMP, MIST_EDGE = (0.80, 0.84, 0.90), 0.90
PAUSED = {"gravel", "ice_chunks"}


def hexrgb(h):
    return G.rgb(h)


class Art:
    """Um "pacote" de arte: antes (assets) ou depois (pendentes por cima dos assets)."""

    def __init__(self, after: bool):
        self.after = after
        self.meta = json.loads(self.path("regions_palettes.json", True).read_text())

    def path(self, name, regions=False):
        """Depois: pendente, senão assets. Antes: a cópia guardada em antes/ (se já existe), senão assets."""
        p = ((PREG if regions else PEND) if self.after else (OUT / "antes" / ("regions" if regions else ""))) / name
        if p.exists():
            return p
        return (REG if regions else ASSETS) / name

    def idx(self, name):
        return np.array(Image.open(self.path(name, True)))

    def rgba(self, name):
        return Image.open(self.path(name)).convert("RGBA")

    def ramp(self, table, region, stage):
        return np.array([hexrgb(c) for c in self.meta["ramps"][table][region][stage]] + [R.OUTLINE, (0, 0, 0)], np.uint8)

    def decal_names(self):
        names = {}
        folders = [REG] + ([PREG] if self.after else [])
        for f in folders:
            for p in f.glob("decal_*.png"):
                n, v = p.stem.removeprefix("decal_").rsplit("_", 1)
                names.setdefault(n, set()).add(int(v))
        return {k: sorted(v) for k, v in names.items()}


def colorize(a, rmp, shadow_a=80):
    out = np.zeros(a.shape + (4,), np.uint8)
    s = a != 255
    out[s, :3] = rmp[np.where(s, a, 0)][s]
    out[s, 3] = 255
    out[a == 9, 3] = shadow_a
    return Image.fromarray(out)


# ---------------------------------------------------------------------------------------------------------------
# cena
# ---------------------------------------------------------------------------------------------------------------
X0, Y0 = 64, 96              # canto da cena no mundo (recorte da textura)


def pick(mix, h):
    tot = sum(w for _, w in mix)
    r = h * tot
    for n, w in mix:
        r -= w
        if r <= 0:
            return n
    return mix[-1][0]


def decal_layer(art: Art, stage):
    """Decalques como no jogo: célula de 96 px presa no mundo, 2 sorteios da v8 + 1 da v9, espelho 50%."""
    code = np.full((SH, SW), 255, np.uint8)
    cell = art.meta["decal_cell"]
    names = art.decal_names()
    passes = [(art.meta["decal_p"]["frost"], art.meta["decal_mix"]["frost"], 700),
              (art.meta["decal_p"]["frost"] * 0.6, art.meta["decal_mix"]["frost"], 800),
              (art.meta["v9_density"]["decal_p"]["frost"], art.meta["v9_density"]["decal_mix"]["frost"], 950)]
    for p, mix, salt in passes:
        for cy in range(-2, SH // cell + 3):
            for cx in range(-2, SW // cell + 3):
                h = lambda s: float(hash2(cx + 40, cy + 40, s + salt))   # noqa: E731
                if h(6) > p:
                    continue
                name = pick(mix, h(8))
                if name in PAUSED or name not in names:
                    continue
                vs = names[name]
                a = art.idx(f"decal_{name}_{vs[int(h(10) * len(vs))]}.png")
                if h(12) < 0.5 and not name.startswith("wind"):
                    a = a[:, ::-1]
                px, py = cx * cell + int(h(2) * cell), cy * cell + int(h(4) * cell)
                x, y = px - a.shape[1] // 2, py - a.shape[0] // 2
                for yy in range(a.shape[0]):
                    ty = y + yy
                    if not 0 <= ty < SH:
                        continue
                    row = a[yy]
                    for xx in np.nonzero((row != 255) & (row != 9))[0]:
                        tx = x + xx
                        if 0 <= tx < SW:
                            code[ty, tx] = row[xx]
    return code


def ground(art: Art, stage):
    tex = art.idx("ground_frost.png")
    ys, xs = np.mgrid[Y0:Y0 + SH, X0:X0 + SW]
    code = tex[ys % 512, xs % 512].copy()
    dl = decal_layer(art, stage)
    code[dl != 255] = dl[dl != 255]
    rmp = art.ramp("BASE", "frost", stage)
    rgb = rmp[code].astype(float)
    # cobertura do estágio (a mesma nos dois: é do jogo, não da arte)
    wx, wy = xs.astype(float), ys.astype(float)
    n = R.fbm(wx / T + 300, wy / T + 170, 5.0, 313, 3)
    if stage == "mist":
        m = n > 0.56
        top = m & ~np.roll(m, 1, 0)
        rgb[m] *= np.array(MIST_DAMP)
        rgb[top] *= MIST_EDGE
    if stage == "green":
        g = n > 0.48
        edge = g & ~(np.roll(g, 1, 0) & np.roll(g, -1, 0) & np.roll(g, 1, 1) & np.roll(g, -1, 1))
        lvl = np.clip((R.organic(xs % 256, ys % 256, 256, 16, 333) * 5).astype(int), 1, 4)
        blade = g & (hash2(xs, ys // 2, 335) < 0.05)
        gi = np.where(edge, 1, np.where(blade, 5, lvl))
        pal = np.array([hexrgb(c) for c in GRASS], float)
        rgb[g] = pal[gi[g]]
    out = np.zeros((SH, SW, 4), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[..., 3] = 255
    return Image.fromarray(out)


def hill_block(art: Art, stage, tiles, ore):
    """Morro: tiles {(tx, ty)} (coordenadas de tela em tiles). Topo da textura hill_top em (x, y − 24), face só
    onde o tile de baixo não é morro, contorno em volta. Devolve [(pé, imagem, (x, y))] por linha."""
    top_t = art.idx("hill_top.png")
    face_t = art.idx("hill_face.png")
    rmp = art.ramp("HILL", "frost", stage)
    rows = {}
    for (tx, ty) in tiles:
        rows.setdefault(ty, []).append(tx)
    out = []
    for ty, txs in sorted(rows.items()):
        w = (max(txs) + 1) * T + 2
        canv = np.full((T + 24 + 2, w), 255, np.uint8)
        for tx in txs:
            wx0, wy0 = X0 + tx * T, Y0 + ty * T
            canv[1:1 + T, 1 + tx * T:1 + tx * T + T] = top_t[wy0 % 512:wy0 % 512 + T, wx0 % 512:wx0 % 512 + T]
            if (tx, ty + 1) not in tiles:
                canv[1 + T:1 + T + 24, 1 + tx * T:1 + tx * T + T] = face_t[:, wx0 % 512:wx0 % 512 + T]
        sol = canv != 255
        ring = np.zeros_like(sol)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ring |= np.roll(np.roll(sol, dy, 0), dx, 1)
        # sem contorno entre linhas do mesmo morro
        ring &= ~sol
        if any((tx, ty - 1) in tiles for tx in txs):
            ring[0, :] = False
        canv[ring] = 8
        im = colorize(canv, rmp)
        for (tx, tty), res in ore.items():
            if tty == ty:
                im.alpha_composite(art.rgba(f"ore_{res}.png"), (1 + tx * T, 1))
        out.append(((ty + 1) * T, im, (-1, ty * T - 24 - 1)))
    return out


SCENE = {
    "hill": {(10, 1), (11, 1), (12, 1), (13, 1), (11, 2), (12, 2), (13, 2), (12, 0), (13, 0)},
    "ore": {(11, 1): "ice", (12, 2): "ice", (13, 1): "iron", (13, 2): "silicon"},
    "rocks": [("rock_small_ice_0", 0, 3, 3), ("rock_small_ice_1", 1, 5, 6), ("rock_small", 0, 9, 5),
              ("rock_small_ice_0", 0, 1, 7), ("rock_small_iron_1", 1, 13, 6)],
    "vein": (6, 2),
    "decor": [("rimed_rock", 0, 2, 2), ("snow_slabs", 0, 8, 7), ("rimed_rock", 1, 10, 4), ("penitentes", 1, 4, 4),
              ("rimed_rock", 2, 14, 4), ("snow_slabs", 1, 0, 4), ("penitentes", 0, 7, 1)],
    "player": (7, 5),
}


def scene(art: Art, stage):
    img = ground(art, stage)
    vx, vy = SCENE["vein"]
    img.alpha_composite(art.rgba("vein_ice.png"), (vx * T, vy * T))
    objs = hill_block(art, stage, SCENE["hill"], SCENE["ore"])
    for name, v, tx, ty in SCENE["rocks"]:
        im = art.rgba(f"{name}.png")
        if art.after:
            im = im.copy()
            im.alpha_composite(art.rgba(f"rock_small_snowcap_{v}.png"))
        objs.append(((ty + 1) * T, im, (tx * T, ty * T)))
    for name, v, tx, ty in SCENE["decor"]:
        fn = f"decor_{name}_{v}.png"
        if not art.path(fn, True).exists():
            fn = f"decor_rimed_rock_{v}.png"            # antes: ainda não existe a laje com neve
        info = art.meta["files"].get(fn, {"ramp": "HILL", "region": "frost"})
        a = art.idx(fn)
        im = colorize(a, art.ramp(info["ramp"], info["region"], stage))
        foot = (ty + 1) * T - 4
        objs.append((foot, im, (tx * T + 16 - im.width // 2, foot - im.height)))
    px, py = SCENE["player"]
    pl = Image.open(ASSETS / "player_down.png").convert("RGBA")
    objs.append(((py + 1) * T, pl, (px * T, py * T)))
    for _foot, im, pos in sorted(objs, key=lambda o: o[0]):
        img.alpha_composite(im, (int(pos[0]), int(pos[1])))
    return img


# ---------------------------------------------------------------------------------------------------------------
# folhas
# ---------------------------------------------------------------------------------------------------------------
def zoom(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def sheet_ground(art: Art, name):
    tex = art.idx("ground_frost.png")
    W = Image.new("RGBA", (4 * 256 + 3 * 4, 256), (21, 16, 14, 255))
    for k, st in enumerate(G.STAGES):
        W.paste(colorize(tex[:256, :256], art.ramp("BASE", "frost", st)), (k * 260, 0))
    W.save(IMG / name)


def sheet_tiling(art: Art, name):
    """A textura 512 repetida 2×1 (emenda) no Árido, pra ver a repetição."""
    tex = art.idx("ground_frost.png")
    big = np.tile(tex, (1, 2))[:256, :]
    colorize(big, art.ramp("BASE", "frost", "arid")).save(IMG / name)


def sheet_decals(stage, name, old=False):
    art = Art(after=not old)
    tex = art.idx("ground_frost.png")
    rmp = art.ramp("BASE", "frost", stage)
    bg = colorize(tex[:220, :480], rmp)
    names = (["icepoly", "icesheet", "rime", "wind"] if old else ["snowbank", "sastrugi", "glaze", "snowdrift", "sparkle"])
    x, y, rowh = 4, 4, 0
    for n in names:
        for v in range(4):
            p = art.path(f"decal_{n}_{v}.png", True)
            if not p.exists():
                continue
            a = np.array(Image.open(p))
            im = colorize(a, rmp)
            if x + im.width > 476:
                x, y = 4, y + rowh + 4
                rowh = 0
            bg.alpha_composite(im, (x, y))
            x += im.width + 6
            rowh = max(rowh, im.height)
    bg.crop((0, 0, 480, min(220, y + rowh + 4))).save(IMG / name)


def sheet_ores():
    """Minérios lado a lado (antes × depois), sobre a parede do morro e sobre a rocha escura da caverna, 1× e 4×."""
    before, after = Art(False), Art(True)
    cave = (58, 50, 62)
    W = Image.new("RGBA", (6 * 36 + 8, 2 * 36 + 4), (0, 0, 0, 0))
    for r, (art, label) in enumerate(((before, "antes"), (after, "depois"))):
        tex = art.idx("hill_top.png")
        top = colorize(tex[64:96, 64:96], art.ramp("HILL", "frost", "arid"))
        for k, res in enumerate(("ice", "iron", "silicon")):
            for j, bgk in enumerate(("hill", "cave")):
                x, y = (k * 2 + j) * 36 + 2, r * 36 + 2
                base = top.copy() if bgk == "hill" else Image.new("RGBA", (32, 32), cave + (255,))
                ore = (after if res == "ice" else before).rgba(f"ore_{res}.png") if art.after else before.rgba(f"ore_{res}.png")
                base.alpha_composite(ore)
                W.alpha_composite(base, (x, y))
    W.save(IMG / "ores_1x.png")
    zoom(W, 4).save(IMG / "ores_4x.png")
    # ícones e pickups
    I = Image.new("RGBA", (6 * 20 + 4, 2 * 20 + 4), (0, 0, 0, 0))
    for r, art in enumerate((before, after)):
        for k, n in enumerate(("icon_ice", "pickup_ice", "icon_iron", "icon_silicon", "pickup_iron", "pickup_silicon")):
            src = art if ("ice" in n and "silicon" not in n) else before
            I.alpha_composite(src.rgba(f"{n}.png"), (k * 20 + 2, r * 20 + 2))
    zoom(I, 6).save(IMG / "icons_6x.png")
    I.save(IMG / "icons_1x.png")
    # rocha pequena com minério e veio
    Rk = Image.new("RGBA", (5 * 36 + 70 + 4, 2 * 68), (0, 0, 0, 0))
    for r, art in enumerate((before, after)):
        x = 2
        for n in ("rock_small_ice_0", "rock_small_ice_1", "rock_small_iron_0", "rock_small_silicon_1"):
            src = art if "ice" in n else before
            Rk.alpha_composite(src.rgba(f"{n}.png"), (x, r * 68 + 32))
            x += 36
        Rk.alpha_composite(art.rgba("vein_ice.png"), (x + 4, r * 68 + 2))
    zoom(Rk, 4).save(IMG / "rocks_ore_4x.png")


def sheet_snowrocks():
    """Rochas da faixa gelada antes × depois, nos 4 estágios (rimed_rock, laje nova, rocha pequena com a capa)."""
    before, after = Art(False), Art(True)
    rows = []
    for art in (before, after):
        W = Image.new("RGBA", (4 * 232, 44), (0, 0, 0, 0))
        tex = art.idx("ground_frost.png")
        for k, st in enumerate(G.STAGES):
            bg = colorize(tex[100:144, 0:228], art.ramp("BASE", "frost", st))
            x = 4
            names = [f"rimed_rock_{v}" for v in range(3)] + ([f"snow_slabs_{v}" for v in range(3)] if art.after else [])
            for n in names:
                fn = f"decor_{n}.png"
                info = art.meta["files"][fn]
                im = colorize(art.idx(fn), art.ramp(info["ramp"], info["region"], st))
                bg.alpha_composite(im, (x, 40 - im.height))
                x += im.width + 3
            for nm, v in (("rock_small", 0), ("rock_small_ice_1", 1)):
                if x + 32 > 228:
                    break
                im = art.rgba(f"{nm}.png").copy()
                if art.after:
                    im.alpha_composite(art.rgba(f"rock_small_snowcap_{v}.png"))
                bg.alpha_composite(im, (x - 4, 44 - 32 + 0))
                x += 30
            W.alpha_composite(bg, (k * 232, 0))
        rows.append(W)
    for W, n in zip(rows, ("snowrocks_before.png", "snowrocks_after.png")):
        zoom(W, 2).save(IMG / n)
    # capa sozinha e por cima das rochas pequenas
    C = Image.new("RGBA", (6 * 34, 34), (0, 0, 0, 0))
    x = 1
    for nm, v in (("rock_small", 0), ("rock_small_iron_1", 1), ("rock_small_silicon_0", 0), ("rock_small_ice_0", 0),
                  ("rock_small_ice_1", 1)):
        im = (after if "ice" in nm else before).rgba(f"{nm}.png").copy()
        im.alpha_composite(after.rgba(f"rock_small_snowcap_{v}.png"))
        C.alpha_composite(im, (x, 1))
        x += 34
    C.alpha_composite(after.rgba("rock_small_snowcap_0.png"), (x, 1))
    zoom(C, 5).save(IMG / "snowcap_5x.png")
    # morro (topo + face) antes × depois nos 4 estágios
    H = Image.new("RGBA", (4 * 164, 2 * 124), (0, 0, 0, 0))
    for r, art in enumerate((before, after)):
        for k, st in enumerate(G.STAGES):
            tex = art.idx("ground_frost.png")
            bg = colorize(tex[0:120, 0:160], art.ramp("BASE", "frost", st))
            for _f, im, (x, y) in hill_block(art, st, {(0, 1), (1, 1), (2, 1), (1, 0), (2, 0), (3, 1)}, {(1, 1): "ice", (2, 0): "ice"}):
                bg.alpha_composite(im, (x + 16, y + 40))
            H.alpha_composite(bg, (k * 164, r * 124))
    zoom(H, 2).save(IMG / "hills_2x.png")


# ---------------------------------------------------------------------------------------------------------------
# index.html
# ---------------------------------------------------------------------------------------------------------------
ANTES = OUT / "antes"
ORE_FILES = ["ore_ice.png", "vein_ice.png", "icon_ice.png", "pickup_ice.png", "rock_small_ice_0.png", "rock_small_ice_1.png"]


def keep_before():
    """Guarda os PNGs de hoje (uma vez só) pra o antes × depois continuar valendo depois de promovido."""
    (ANTES / "regions").mkdir(parents=True, exist_ok=True)
    for n in ORE_FILES:
        if not (ANTES / n).exists():
            (ANTES / n).write_bytes((ASSETS / n).read_bytes())
    for n in ["ground_frost.png", "regions_palettes.json"] + [f"decor_rimed_rock_{v}.png" for v in range(3)]:
        if not (ANTES / "regions" / n).exists():
            (ANTES / "regions" / n).write_bytes((REG / n).read_bytes())


def contract_rows():
    rows = []
    for p in sorted(PEND.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(PEND).as_posix()
        if p.suffix == ".png":
            w, h = Image.open(p).size
            old = (REG if rel.startswith("regions/") else ASSETS) / p.name
            if old.exists():
                ow, oh = Image.open(old).size
                st = "mesmo tamanho" if (ow, oh) == (w, h) else f"MUDOU ({ow}×{oh})"
                kind = "substitui"
            else:
                st, kind = "novo", "NOVO"
            rows.append((rel, f"{w}×{h}", kind, st))
        else:
            rows.append((rel, "—", "substitui", "JSON inteiro, com as mudanças abaixo"))
    return rows


def write_html():
    keep_before()
    rows = contract_rows()
    sizes_ok = all(r[3] in ("mesmo tamanho", "novo", "JSON inteiro, com as mudanças abaixo") for r in rows)
    def cmp(st):
        return (f'<div class="grid2"><figure><img class="px" src="img/cena_{st}_antes_2x.png" alt="">'
                f'<figcaption>antes · {STAGE_NAME[st]}</figcaption></figure>'
                f'<figure><img class="px" src="img/cena_{st}_depois_2x.png" alt="">'
                f'<figcaption>depois · {STAGE_NAME[st]} · <a href="img/cena_{st}_depois.png">1×</a></figcaption></figure></div>')
    scenes = "\n".join(f"<h3 style='margin-top:22px'>{STAGE_NAME[st]}</h3>{cmp(st)}" for st in G.STAGES)
    real = "".join(f'<figure><img src="img/cena_{st}_depois.png" width="480" height="270" alt=""><figcaption>{STAGE_NAME[st]} · 1×</figcaption></figure>' for st in G.STAGES)
    trs = "".join(f"<tr><td><code>{a}</code></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for a, b, c, d in rows)
    ramp_rows = ""
    for st in G.STAGES:
        sw = "".join(f'<span class="sw" style="background:{c}" title="{i}: {c}"></span>' for i, c in enumerate(G.FROST_BASE[st]))
        sh = "".join(f'<span class="sw" style="background:{c}" title="{i}: {c}"></span>' for i, c in enumerate(G.FROST_HILL[st]))
        ramp_rows += f"<tr><td><b>{STAGE_NAME[st]}</b></td><td>{sw}</td><td>{sh}</td></tr>"
    pairs = "".join(
        f'<figure><div class="pair chk"><div><span>antes</span><img src="antes/{n}" width="{Image.open(PEND / n).width * 6}" alt=""></div>'
        f'<div><span>depois</span><img src="pendentes/{n}" width="{Image.open(PEND / n).width * 6}" alt=""></div></div><figcaption>{n} · 6×</figcaption></figure>'
        for n in ORE_FILES)
    v11pairs = "".join(
        f'<figure><div class="pair chk"><div><span>v1.0</span><img src="antes_v1/{n}" width="{Image.open(PEND / n).width * 5}" alt=""></div>'
        f'<div><span>v1.1</span><img src="pendentes/{n}" width="{Image.open(PEND / n).width * 5}" alt=""></div></div><figcaption>{n} · 5×</figcaption></figure>'
        for n in ("ore_ice.png", "vein_ice.png", "icon_ice.png", "rock_small_ice_0.png", "rock_small_ice_1.png"))
    doc = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · v0.5 M3 · Faixa gelada · v1.1</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0f1420;--panel:#161d2c;--line:#2a3550;--fg:#e8eef8;--muted:#9aa8c0;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1300px;margin:0 auto;padding:44px 0 80px}}
.eyebrow{{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--cyan);text-transform:uppercase}}
h1{{font:600 44px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}}h2{{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--cyan);margin-right:10px;vertical-align:middle}}
h3{{font:600 16px "Pixelify Sans",monospace;margin:0 0 6px}}code{{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}}
p,li,td{{color:var(--muted)}}li b,p b,td b{{color:var(--fg)}}
.v2{{background:#18213a;border:1px solid var(--line);border-left:3px solid var(--cyan);padding:12px 18px;max-width:1100px}}
.v2>b{{font:13px "Silkscreen",monospace;color:var(--cyan)}}
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}@media(max-width:1000px){{.grid2{{grid-template-columns:1fr}}}}
img.px{{width:100%;height:auto;border:1px solid var(--line);display:block}}
.flex{{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);padding:16px 20px;margin-top:14px}}
.chk{{padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
.pair{{display:flex;gap:14px;align-items:flex-end}}.pair span{{display:block;font:11px "Silkscreen",monospace;color:var(--muted)}}
table{{border-collapse:collapse}}td,th{{border-bottom:1px solid var(--line);padding:5px 10px;text-align:left;font-size:14px}}th{{color:var(--fg);font:12px "Silkscreen",monospace}}
.sw{{display:inline-block;width:22px;height:22px;margin-right:2px;border:1px solid #0006;vertical-align:middle}}
.swap{{position:relative;display:inline-block}}.swap img{{display:block}}.swap .b{{position:absolute;left:0;top:0;opacity:0;transition:none}}
.swap:hover .b{{opacity:1}}
.tw{{animation:tw 1.6s steps(1) infinite}}@keyframes tw{{0%{{filter:none}}50%{{filter:brightness(1.18)}}}}
</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5 Marco 3 · item 2 · v1.1</div>
<h1>Faixa gelada: neve azul, sem rachadura, e gelo que parece gelo</h1>
<div class="v2"><b>v1.1 · o que mudou</b><ul>
<li><b>Rocha pequena de gelo virou bloco de gelo</b> (<code>rock_small_ice_0/1</code>): mesma silhueta, mas o corpo inteiro agora é gelo, sem a pedra marrom. 3 propostas lado a lado (<a href="#v11" style="color:#59d0e6">seção v1.1</a>); a <b>A</b> (lapidado) está no pendente.</li>
<li><b>Minério e veio acompanham</b> (<code>ore_ice</code>, <code>vein_ice</code>, <code>icon_ice</code>, <code>pickup_ice</code>): o azul ficou um tom mais claro e translúcido, e as pepitas do minério e do veio perderam a faceta escura de baixo. Deixam de puxar pra safira e conversam com o bloco.</li>
<li>Resto da v1.0 (chão, decalques, rochas com neve, morros) <b>aprovado</b>, sem mudança.</li>
</ul></div>
<div class="v2" style="opacity:.75;margin-top:10px"><b>v1.0 · aprovado pelo dono (menos a rocha pequena de gelo)</b><ul>
<li><b>Chão</b> (<code>ground_frost</code> + rampa <code>BASE.frost</code> nos 4 estágios): sai o cinza com rede de rachaduras, entra <b>neve azul</b> com dunas de vento compridas, campos de <b>sastrugi</b> (ondinhas do vento), manchinhas de <b>gelo azul polido</b>, grão e cintilado. <b>Zero rachadura</b>.</li>
<li><b>Decalques da faixa gelada</b>: saem <code>icepoly</code> (polígonos rachados), <code>icesheet</code>, <code>rime</code> (geada em pena, que lia como trinca) e <code>wind</code>. Entram 5 novos: <code>snowbank</code> (camada de neve fofa), <code>sastrugi</code>, <code>glaze</code> (gelo azul / poça de degelo), <code>snowdrift</code> (montinho) e <code>sparkle</code> (cintilado). Mais chance de decalque = chão menos repetido.</li>
<li><b>Minério de gelo</b> (<code>ore_ice</code>, <code>vein_ice</code>, <code>icon_ice</code>, <code>pickup_ice</code>, <code>rock_small_ice_0/1</code>): <b>mesma silhueta, pixel a pixel</b> (conferido por script), agora <b>lapidado</b>: cada pedra é uma pirâmide de 4 facetas (cima clara, esquerda, direita, baixo escura) num azul saturado, com um ponto branco de brilho. Deixa de parecer prata.</li>
<li><b>Rochas com neve</b> (referência nova do dono): pedra cinza-azulada com capa de neve em cima e escorrendo pelas bordas, nos 4 estágios, sem musgo nem verde. Entram no <code>decor_rimed_rock</code> (refeito, mesmos tamanhos), numa laje grande nova (<code>decor_snow_slabs</code>), numa capa por cima das rochas pequenas (<code>rock_small_snowcap</code>) e nos morros da faixa gelada (só rampa <code>HILL.frost</code>).</li>
</ul></div>
<p style="margin-top:14px">Nada disso está em <code>assets/</code> ainda: os arquivos finais estão em <code>reports/design/v05_m3_gelo/pendentes/</code>, prontos pra copiar. Gerado por <code>tools/sprites/v05_m3_gelo.py</code> (determinístico, md5 conferido rodando duas vezes) e este report por <code>tools/sprites/v05_m3_gelo_report.py</code>. As cenas são montadas só com os PNGs, na ordem de desenho do jogo.</p>


<h2 id="v11">v1.1 · Rocha pequena de gelo: bloco de gelo, não pedra com safira</h2>
<div class="flex"><figure><img src="ref/rock_small_ice_feedback.png" alt="" style="width:300px"><figcaption>antes · o print do dono (v1.0): pedra marrom com gemas grudadas</figcaption></figure></div>
<p>Mesma silhueta da rocha pequena (tampo + face de 6 px + pedrinha), conferida por script. O corpo inteiro agora é gelo: tampo azul-claro translúcido, face em faixas de azul cada vez mais fundo, borda de cima branca de brilho, luz refratada em risquinhos na face, bolhas presas e a pedrinha do lado como um cubo de gelo.</p>
<ul>
<li><b>A · lapidado</b> (está no pendente): o tampo é cortado em 4 facetas a partir de um vértice, com <b>aresta branca</b> nas que pegam luz. É o que mais lê "cristal de gelo" e conversa com o minério.</li>
<li><b>B · translúcido</b>: tampo liso em 2 tons com o <b>miolo azul fundo</b> aparecendo por baixo e mais bolhas. Lê mais "gelo maciço" do que "cristal".</li>
<li><b>C · com pedra presa</b>: o B com um caquinho de pedra escura preso no miolo (o resquício de rocha, mas quem domina é o gelo).</li>
</ul>
<figure><img src="img/rock_ice_variantes_4x.png" alt="" style="max-width:100%"><figcaption>linhas: v1.0 (a do print) · A · B · C · colunas: neve do Árido · neve do Verde · chão da caverna · 4×</figcaption></figure>
<div class="flex" style="margin-top:12px"><figure><img src="img/rock_ice_variantes_1x.png" alt=""><figcaption>escala real (1×)</figcaption></figure>
<figure><img src="img/rock_ice_capa_4x.png" alt=""><figcaption>A · B · C com a capa de neve da faixa gelada por cima · 4×</figcaption></figure></div>
<p>Pra trocar de proposta é uma linha no gerador: <code>ROCK_STYLE = "A"</code> em <code>tools/sprites/v05_m3_gelo.py</code> (B ou C), e roda de novo.</p>
<h3 style="margin-top:18px">Minério e veio acompanhando (v1.0 × v1.1)</h3>
<div class="flex">{v11pairs}</div>
<h2>Cena · antes × depois nos 4 estágios (2×)</h2>
<p>Mesma cena nos dois lados: chão + decalques sorteados como no jogo + veio 2×2 + morro com minério (gelo, ferro e silício) + rochas pequenas + soltos + o explorador pra escala. A cobertura do estágio (umidade da Névoa, grama do Verde) é a do jogo.</p>
{scenes}
<h3 style="margin-top:22px">Escala real (1×)</h3><div class="flex">{real}</div>

<h2>O que cada estágio faz com a neve</h2>
<ul>
<li><b>Árido</b>: neve seca e fria, azul-neve de verdade; sombra azul saturada, gelo polido azul-turquesa, cintilado branco.</li>
<li><b>Tempestade</b>: a mesma neve com poeira ocre assentada (os claros amornam, a sombra continua azul). Não volta pro cinza chapado.</li>
<li><b>Névoa</b>: neve molhada, mais escura e fria; o gelo azul vira <b>neve-papa</b> escura. As manchas de umidade do jogo escurecem por cima e ficam com cara de neve encharcada.</li>
<li><b>Verde</b>: neve velha derretendo, verde-água pálido; o gelo azul vira <b>poça de degelo</b>. A grama do jogo brota por cima em manchas. As rochas continuam cinza-azuladas com neve (nada de musgo, como pedido).</li>
</ul>
<table><tr><th>estágio</th><th>BASE.frost (chão e decalques) · 0..7</th><th>HILL.frost (morro e rochas) · 0..7</th></tr>{ramp_rows}</table>

<h2>Chão · textura 512 nos 4 estágios</h2>
<p>Recorte 256×256 do <code>ground_frost.png</code>, Tempestade · Árido · Névoa · Verde.</p>
<figure><img class="px" src="img/chao_antes.png" alt=""><figcaption>antes</figcaption></figure>
<figure style="margin-top:10px"><img class="px" src="img/chao_depois.png" alt=""><figcaption>depois</figcaption></figure>
<h3 style="margin-top:18px">Repetição (a textura colada 2× lado a lado, emenda sem costura)</h3>
<div class="grid2"><figure><img class="px" src="img/repeticao_antes.png" alt=""><figcaption>antes</figcaption></figure><figure><img class="px" src="img/repeticao_depois.png" alt=""><figcaption>depois</figcaption></figure></div>
<p>O que quebra a repetição: as dunas têm escala de 128 px e o campo de sastrugi e o gelo azul caem em lugares diferentes da textura; por cima, os decalques novos (até 196 px) sorteados pela célula de 96 px presa no mundo, com chance maior (v8 0,40 → 0,50; v9 0,30 → 0,45).</p>

<h2>Decalques novos</h2>
<div class="grid2">
<figure><img class="px" src="img/decais_antes_arid.png" alt=""><figcaption>antes · icepoly, icesheet, rime, wind (Árido)</figcaption></figure>
<figure><img class="px tw" src="img/decais_arid.png" alt=""><figcaption>depois · snowbank, sastrugi, glaze, snowdrift, sparkle (Árido)</figcaption></figure>
<figure><img class="px" src="img/decais_storm.png" alt=""><figcaption>Tempestade</figcaption></figure>
<figure><img class="px" src="img/decais_mist.png" alt=""><figcaption>Névoa</figcaption></figure>
<figure><img class="px" src="img/decais_green.png" alt=""><figcaption>Verde (o glaze vira poça de degelo)</figcaption></figure>
</div>

<h2>Minério de gelo · lapidado, mesma silhueta</h2>
<p>Linha de cima = hoje, linha de baixo = proposta. Cada par: sobre o topo do morro da faixa gelada e sobre a rocha escura da caverna. Ferro e silício ficam iguais, só pra comparar a leitura: o gelo agora é o único <b>azul saturado e facetado</b>; o silício continua a lasca cinza-lilás.</p>
<figure><img src="img/ores_4x.png" alt="" style="max-width:100%"><figcaption>ore_ice · ore_iron · ore_silicon · 4×</figcaption></figure>
<div class="flex" style="margin-top:16px">
<figure><img src="img/icons_6x.png" alt=""><figcaption>icon_ice · pickup_ice · icon_iron · icon_silicon · pickup_iron · pickup_silicon · 6× (cima hoje, baixo proposta)</figcaption></figure>
<figure><img src="img/icons_1x.png" alt="" width="124"><figcaption>1×</figcaption></figure>
</div>
<figure style="margin-top:16px"><img src="img/rocks_ore_4x.png" alt="" style="max-width:100%"><figcaption>rock_small_ice_0/1 (v1.1: bloco de gelo lapidado, proposta A) · ferro e silício pra comparar · vein_ice (placas de gelo com aresta de cristal, pepitas claras por cima, sem rachadura) · 4× · cima hoje, baixo proposta</figcaption></figure>
<h3 style="margin-top:18px">Arquivo por arquivo</h3>
<div class="flex">{pairs}</div>

<h2>Rochas com neve (referência do dono)</h2>
<div class="flex"><figure><img src="ref/rochas_com_neve.png" alt="" style="width:270px;image-rendering:auto"><figcaption>referência do dono</figcaption></figure></div>
<p>Do estilo da referência eu aproveitei: pedra <b>cinza-azulada</b> com contorno escuro, grupos de tamanhos variados (uma grande de várias lajes, médias e pequenas soltas), a <b>capa branca grossa no topo</b> com a borda de baixo irregular e neve <b>escorrendo</b> na borda de cima da face. As formas, a quantidade de lajes e o sombreamento são nossos (as lajes são polígonos sorteados por seed, no mesmo motor das placas do veio). Sem musgo e sem verde em nenhum estágio.</p>
<figure><img class="px" src="img/snowrocks_before.png" alt=""><figcaption>antes · decor_rimed_rock_0..2 e as rochas pequenas · Tempestade · Árido · Névoa · Verde</figcaption></figure>
<figure style="margin-top:10px"><img class="px" src="img/snowrocks_after.png" alt=""><figcaption>depois · rimed_rock_0..2 refeitos, snow_slabs_0..2 (novo), rock_small e rock_small_ice com a capa</figcaption></figure>
<div class="flex" style="margin-top:16px"><figure><img src="img/snowcap_5x.png" alt=""><figcaption>rock_small_snowcap_0/1 por cima de rock_small, rock_small_iron_1, rock_small_silicon_0, rock_small_ice_0/1 · e a capa sozinha · 5×</figcaption></figure></div>
<h3 style="margin-top:18px">Morros da faixa gelada (só a rampa HILL.frost muda)</h3>
<figure><img class="px" src="img/hills_2x.png" alt=""><figcaption>cima: hoje · baixo: proposta · o topo vira campo de neve com a pedra aparecendo nas fendas, a face ganha a capa de neve escorrendo da borda de cima · 2×</figcaption></figure>

<h2>Pro Dev integrar</h2>
<div class="box"><h3>1. Copiar (depois do ok do dono)</h3>
<p><code>reports/design/v05_m3_gelo/pendentes/regions/*</code> → <code>assets/sprites/regions/</code> (inclui o <code>regions_palettes.json</code> inteiro) e <code>reports/design/v05_m3_gelo/pendentes/*.png</code> → <code>assets/sprites/</code>.</p>
<table><tr><th>arquivo</th><th>tamanho</th><th>tipo</th><th>conferência</th></tr>{trs}</table>
<p>Checagem: {"todos os substituídos têm o tamanho exato de hoje; ore/vein/icon/pickup/rock_small_ice com o alpha idêntico ao de hoje" if sizes_ok else "ATENÇÃO: tamanho divergente"}.</p></div>
<div class="box"><h3>2. O que muda no JSON (já está no pendente; o código lê sozinho)</h3><ul>
<li><code>ramps.BASE.frost</code> e <code>ramps.HILL.frost</code>: as 4 rampas novas (tabela acima). O minimapa pega a cor média da BASE do Árido: a faixa gelada passa a pintar azul-neve.</li>
<li><code>decal_mix.frost</code> = <code>{json.dumps(G.V8_MIX)}</code>, <code>decal_p.frost</code> = {G.V8_P} (era 0,40). Sai <code>icesheet</code>, <code>wind</code> e <code>gravel</code>.</li>
<li><code>v9_density.decal_mix.frost</code> = <code>{json.dumps(G.V9_MIX)}</code>, <code>v9_density.decal_p.frost</code> = {G.V9_P} (era 0,30). Sai <code>icepoly</code> e <code>rime</code>.</li>
<li><code>v9_density.decor_p.frost</code> = <code>{json.dumps(G.V9_DECOR)}</code> (laje com neve nova; penitentes e rimed_rock um tico menos).</li>
<li><code>files</code>: entradas dos decalques novos (rampa <code>BASE</code>, região <code>frost</code>) e dos <code>decor_snow_slabs_*</code> (rampa <code>HILL</code>, região <code>frost</code>).</li>
<li>Os decalques e soltos são carregados por glob (<code>decal_*.png</code>, <code>decor_*.png</code>), então os nomes novos entram sem código. Os antigos (<code>decal_icepoly_*</code>, <code>decal_icesheet_*</code>, <code>decal_rime_*</code>) podem ficar em <code>assets/</code>: saem do sorteio porque não estão mais em nenhuma mistura.</li>
</ul></div>
<div class="box"><h3>3. Código (o mínimo)</h3><ul>
<li><b>Capa de neve nas rochas pequenas</b> (único trecho novo): na superfície, quando o tile de uma rocha pequena (<code>rock_small</code> e <code>rock_small_{{iron,silicon,ice}}_{{0,1}}</code>) está na região <code>frost</code>, desenhar <code>rock_small_snowcap_{{v}}.png</code> (32×32, RGBA) <b>logo depois da rocha, no mesmo (x, y)</b>. <code>v</code> = a variação da rocha (<code>rock_variant(tx, ty)</code>); a <code>rock_small.png</code> comum usa a <b>0</b> (mesma silhueta). A capa fica dentro da silhueta, não mexe em colisão. Na caverna, não desenha. A magmatita não usa (nasce no basalto).</li>
<li><b>Sugestão (config, opcional)</b>: <code>GROUND_GRASS_THR</code> da classe gelada de 0,48 → ~0,62, pra no Verde a faixa continuar lendo como neve derretendo, com grama em manchas, e não como gramado (nas cenas do Verde dá pra ver os 0,48 de hoje).</li>
<li>Ordem de desenho, âncoras e tamanhos: <b>nada muda</b>. Chão e decalques no assado do chão; <code>vein_ice</code> no mesmo lugar; <code>ore_ice</code> por cima do topo do morro em (x, y − 24); <code>decor_snow_slabs_*</code> como os outros soltos (âncora no centro da base, ordem pelo pé, não colide, até 32×28).</li>
</ul></div>
<div class="box"><h3>Fora do escopo, mas vi</h3><ul>
<li>O <b>silício</b> perde contraste em cima do morro com neve (cinza-claro sobre branco-azulado). Não mexi (não era o pedido); se incomodar no jogo, dá pra escurecer o socket dele.</li>
<li><code>decor_ice_chunks</code> está pausado no <code>SCENERY_PAUSED</code>; não mexi. Os gelos-portão, a cratera e as agulhas usam a rampa <code>ICE</code>, que não muda.</li>
</ul></div>
</div></body></html>
"""
    (OUT / "index.html").write_text(doc)


def sheet_rock_variants():
    """v1.1: as 3 propostas do bloco de gelo (A, B, C), as 2 variações, sobre a neve do Árido, a neve do Verde e o
    chão escuro da caverna; mais a v1.0 (a do print do dono) pra comparar."""
    after = Art(True)
    tex = after.idx("ground_frost.png")
    bgs = [colorize(tex[40:84, 0:80], after.ramp("BASE", "frost", "arid")),
           colorize(tex[40:84, 0:80], after.ramp("BASE", "frost", "green")),
           Image.new("RGBA", (80, 44), (58, 50, 62, 255))]
    rows = [("v1.0", [Image.open(OUT / "antes_v1" / f"rock_small_ice_{v}.png").convert("RGBA") for v in (0, 1)])]
    for st in "ABC":
        rows.append((st, [G.rock_ice_block(v, st).image() for v in (0, 1)]))
    W = Image.new("RGBA", (len(bgs) * 84, len(rows) * 48), (0, 0, 0, 0))
    for r, (_n, ims) in enumerate(rows):
        for k, bg in enumerate(bgs):
            b = bg.copy()
            b.alpha_composite(ims[0], (4, 8))
            b.alpha_composite(ims[1], (42, 8))
            W.alpha_composite(b, (k * 84, r * 48))
    zoom(W, 4).save(IMG / "rock_ice_variantes_4x.png")
    W.save(IMG / "rock_ice_variantes_1x.png")
    # a mesma coisa com a capa de neve da faixa gelada por cima
    C = Image.new("RGBA", (4 * 72, 40), (0, 0, 0, 0))
    for i, st in enumerate("ABC"):
        b = colorize(tex[60:100, 0:72], after.ramp("BASE", "frost", "arid"))
        for v in (0, 1):
            im = G.rock_ice_block(v, st).image()
            im.alpha_composite(after.rgba(f"rock_small_snowcap_{v}.png"))
            b.alpha_composite(im, (2 + v * 36, 4))
        C.alpha_composite(b, (i * 72, 0))
    zoom(C, 4).save(IMG / "rock_ice_capa_4x.png")


def build():
    sheet_rock_variants()
    IMG.mkdir(parents=True, exist_ok=True)
    before, after = Art(False), Art(True)
    for st in G.STAGES:
        for art, tag in ((before, "antes"), (after, "depois")):
            im = scene(art, st)
            im.save(IMG / f"cena_{st}_{tag}.png")
            zoom(im, 2).save(IMG / f"cena_{st}_{tag}_2x.png")
    sheet_ground(before, "chao_antes.png")
    sheet_ground(after, "chao_depois.png")
    sheet_tiling(before, "repeticao_antes.png")
    sheet_tiling(after, "repeticao_depois.png")
    for st in G.STAGES:
        sheet_decals(st, f"decais_{st}.png")
    sheet_decals("arid", "decais_antes_arid.png", old=True)
    sheet_ores()
    sheet_snowrocks()
    write_html()



if __name__ == "__main__":
    build()
