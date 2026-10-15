#!/usr/bin/env python3
"""v0.6 bloco Fundo · família do COBRE (nova) e FERRO com paleta nova. PROPOSTA: nada vai pra assets/sprites sem o
ok do dono.

    python3 tools/sprites/v06_fundo_cobre_ferro.py

Saída: reports/design/v06_fundo_cobre_ferro/ (pendentes/ + before/ + cells/ + prévias + index.html).
Só LÊ assets/sprites/. Reaproveita o gerador do minério (tools/sprites/ores_raw.py): o desenho do ferro fica
IDÊNTICO (mesmas máscaras), só a paleta troca; o cobre usa as mesmas funções com formas/seeds próprios e uma
passada de pátina (verdete) por cima. Determinístico (seeds fixas), alpha só 0/255, contorno #1b1630.
"""
from __future__ import annotations
import math
import os
import random
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ores_raw as o  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v06_fundo_cobre_ferro"
PEND, BEFORE, CELLS = REP / "pendentes", REP / "before", REP / "cells"

# ---------------------------------------------------------------------------
# Paletas (brilho, claro, base, sombra, fundo-do-buraco)
# ---------------------------------------------------------------------------
IRON_OLD = list(o.MIN["iron"])
# ferro novo: bege/cinza-acastanhado de pedra (ref: topo rosado-bege #d8b296, flanco #716452, sombra #3a3226)
IRON_NEW = ["#f3e2cf", "#dcc0a3", "#b99b82", "#7a6552", "#3b3027"]
# cobre: laranja-salmão vivo; pátina verde-azulada (verdete) nas mesmas 4 faixas
COPPER = ["#ffd2ae", "#f7966a", "#e0703f", "#aa4a2a", "#52210f"]
PATINA = ["#c9fbe9", "#74dcbd", "#3fb094", "#26796d", "#52210f"]

o.MIN["copper"] = COPPER
o.MIN["iron"] = IRON_NEW
# (x, y, forma, grande?): pintas MAIS GORDAS que as do ferro (o veio de parede repete 6 a 8 tiles) e o verdete
# cai em pintas inteiras (pixel verde solto vira ruído)
o.ORE_SPOTS["copper"] = [(2, 2, 0, 1), (11, 1, 2, 1), (20, 4, 1, 1), (26, 1, 3, 1), (6, 10, 3, 1), (14, 13, 0, 1),
                         (23, 12, 2, 1), (2, 19, 1, 1), (10, 21, 1, 1), (19, 21, 3, 1), (26, 24, 0, 1), (4, 27, 2, 0)]
PATINA_SPOTS = {1, 4, 7, 10}
o.RAW_BUMPS["copper"] = [(5.5, 5, 3.2), (10.5, 5.5, 2.8), (12.5, 9.5, 2.6), (4.5, 10, 3.0), (9, 9, 3.6),
                         (7, 12.8, 2.6), (12, 13, 2.2)]


def patina(cv, seed, cover=0.36, freq=1.0):
    """Troca por verdete parte dos pixels de cobre (mesma faixa de luz): um campo suave de senos define as manchas,
    corta no `cover` dos pixels de minério e tira pixels soltos (mancha tem que ter pelo menos 2 px)."""
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.3) for _ in range(4)]
    fr = [rnd.uniform(0.28, 0.5) * freq for _ in range(4)]
    tone = {tuple(int(COPPER[i][j:j + 2], 16) for j in (1, 3, 5)): i for i in range(4)}
    h, w = cv.a.shape[:2]
    pts = [(y, x) for y in range(h) for x in range(w) if cv.a[y, x, 3] == 255 and tuple(cv.a[y, x, :3]) in tone]
    if not pts:
        return cv
    fld = {(y, x): math.sin(x * fr[0] + ph[0]) + math.sin(y * fr[1] + ph[1]) + math.sin((x + y) * fr[2] + ph[2])
           + math.sin((x - y) * fr[3] + ph[3]) for (y, x) in pts}
    thr = sorted(fld.values())[int(len(pts) * (1 - cover))]
    sel = {p for p in pts if fld[p] >= thr}
    sel = {(y, x) for (y, x) in sel if sum(((y + dy, x + dx) in sel) for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1))) >= 1}
    for (y, x) in sel:
        cv.a[y, x, :3] = o.rgb(PATINA[tone[tuple(cv.a[y, x, :3])]])[:3]
    return cv


def ore_copper():
    cv = o.Canvas(32, 32)
    for i, (x, y, sh, big) in enumerate(o.ORE_SPOTS["copper"]):
        o.speck(cv, x, y, o.BIG[sh] if big else o.SPECKS[sh], PATINA if i in PATINA_SPOTS else COPPER)
    return cv


def vein_organic_copper():
    """Cópia de ores_raw.vein_organic_parts com seed própria (o dict de seeds do original não tem o cobre)."""
    rnd = random.Random(9 * 131)
    rock = [o.mix(c, COPPER[3], 0.28) for c in o.ROCK]
    cv = o.Canvas(64, 64)
    slabs = [(15, 21, 15, 7), (40, 16, 17, 6), (12, 43, 15, 7), (38, 40, 17, 8), (55, 29, 8, 6), (53, 52, 9, 6),
             (27, 56, 12, 5)]
    items = [(cy, o.poly_slab(rnd, cx, cy, r, n)) for (cx, cy, r, n) in slabs]
    for _cy, top in sorted(items, key=lambda i: i[0]):
        cv.blit(o.extrude(top, 3, rock[0], rock[1], rock[2], rock[3], glint=False, outline=True), 0, 0)
    allowed = o._solid_noline(cv)
    m = np.zeros((64, 64), bool)
    for (cx, cy, r, n) in slabs:
        a = rnd.choice([-1, 1]) * rnd.uniform(0.15, 0.6) + (0 if rnd.random() < 0.5 else math.pi)
        o.crack(m, rnd, cx - math.cos(a) * r * 0.9, cy - math.sin(a) * r * 0.5, a, r * 1.9, rnd.choice([2, 3]))
    for (x, y, ang, ln, wd) in [(3, 27, 0.15, 58, 2), (9, 52, -0.25, 50, 2), (34, 4, 1.2, 38, 2)]:
        o.crack(m, rnd, x, y, ang, ln, wd)
    cv2 = cv
    o.paint_crack(cv2, m & allowed, COPPER)
    return cv2


def family(kind):
    """nome -> Canvas, com o mesmo formato da família do ferro."""
    d = {}
    if kind == "copper":
        d["ore_copper.png"] = ore_copper()
        d["vein_copper.png"] = patina(vein_organic_copper(), 32, 0.34, 0.9)
        d["rock_small_copper_0.png"] = patina(o.rock_vein("copper", 0), 33, 0.38, 1.2)
        d["rock_small_copper_1.png"] = patina(o.rock_vein("copper", 1), 34, 0.38, 1.2)
        d["icon_copper.png"] = patina(o.raw("copper"), 35, 0.34, 1.7)
        d["pickup_copper.png"] = patina(o.raw("copper", 16, 0.75, 2), 36, 0.34, 1.7)
    else:
        d["ore_iron.png"] = o.ore("iron")
        d["vein_iron.png"] = o.vein_organic("iron")
        d["rock_small_iron_0.png"] = o.rock_vein("iron", 0)
        d["rock_small_iron_1.png"] = o.rock_vein("iron", 1)
        d["icon_iron.png"] = o.raw("iron")
        d["pickup_iron.png"] = o.raw("iron", 16, 0.75, 2)
    return d


SIZES = {"ore": (32, 32), "vein": (64, 64), "rock": (32, 32), "icon": (16, 16), "pickup": (16, 16)}


def build_sprites():
    for p in (PEND, BEFORE, CELLS):
        shutil.rmtree(p, ignore_errors=True)
        p.mkdir(parents=True)
    for k in ("iron", "copper"):
        for n, cv in family(k).items():
            cv.image().save(PEND / n) if hasattr(cv, "image") else Image.fromarray(cv.a).save(PEND / n)
    for n in family("iron"):
        shutil.copy(SPR / n, BEFORE / n)
    # confere que o ferro "antes" gerado == o que está no jogo (prova que só a paleta mudou)
    o.MIN["iron"] = IRON_OLD
    for n, cv in family("iron").items():
        assert (np.array(Image.open(SPR / n)) == cv.a).all(), n
    o.MIN["iron"] = IRON_NEW


# ---------------------------------------------------------------------------
# Cenas
# ---------------------------------------------------------------------------
T = 32


def load(n, d=SPR):
    return Image.open(d / n).convert("RGBA")


def hsh(x, y, s):
    return ((x * 73856093) ^ (y * 19349663) ^ (s * 83492791)) % 1000 / 1000


def cave(grid, ores, pend, w, h, seedshift=0):
    """grid: lista de strings ('#' parede, '.' chão, letra = parede com minério). ores: letra -> nome do ore png.
    Ordem do jogo: chão, depois paredes de cima pra baixo (topo elevado 24 + minério + face)."""
    img = Image.new("RGBA", (w * T, h * T + 24), (0, 0, 0, 255))
    wall = lambda x, y: 0 <= y < h and 0 <= x < w and grid[y][x] != "."
    off = 24
    for y in range(h):
        for x in range(w):
            if not wall(x, y):
                img.alpha_composite(load(f"floor_mist_{int(hsh(x, y, 77) * 4)}.png"), (x * T, y * T + off))
    for y in range(h):
        for x in range(w):
            if wall(x, y):
                img.alpha_composite(load(f"wall_mist_{int(hsh(x, y, 91) * 3)}.png"), (x * T, y * T + off - 24))
                ch = grid[y][x]
                if ch in ores:
                    nm = ores[ch]
                    src = pend if (pend / nm).exists() else SPR
                    img.alpha_composite(load(nm, src), (x * T, y * T + off - 24))
                if y + 1 < h and not wall(x, y + 1):
                    img.alpha_composite(load("wall_face_mist.png"), (x * T, y * T + off + 8))
    return img


def checker(w, h, s=8, a=(52, 44, 40), b=(66, 56, 51)):
    im = Image.new("RGBA", (w, h))
    for y in range(0, h, s):
        for x in range(0, w, s):
            im.paste((*(a if (x // s + y // s) % 2 == 0 else b), 255), (x, y, x + s, y + s))
    return im


def build_scenes():
    # 1) veio de parede de 7 tiles de cobre (L irregular), 2 linhas de parede
    g1 = ["#########",
          "##CC#C###",
          "#CCC#C###",
          "####C####",
          "#########",
          ".........",
          "........."]
    # parede de 5 linhas; cobre embutido, o resto rocha comum
    g1 = ["##########",
          "###CC#####",
          "##CCCC####",
          "###C#C####",
          "##########",
          "..........",
          ".........."]
    cave(g1, {"C": "ore_copper.png"}, PEND, 10, 7).save(REP / "cena_cobre_veio7.png")
    # 7 em linha reta, o pior caso de repetição
    g1b = ["##########",
           "#CCCCCCC##",
           "##########",
           "..........",
           ".........."]
    cave(g1b, {"C": "ore_copper.png"}, PEND, 10, 5).save(REP / "cena_cobre_linha7.png")
    # 2) caverna com todos os minérios: antes (sem cobre, ferro velho) e depois
    g2 = ["############",
          "#II##SS#CC##",
          "#II#ISS#CC##",
          "##II#GG#C###",
          "#GGG####M###",
          "#GGG#######.",
          "............",
          "............"]
    g2b = [r.replace("C", "#") for r in g2]
    ores_old = {"I": "ore_iron.png", "S": "ore_silicon.png", "G": "ore_ice.png", "M": "ore_magmatite.png"}
    ores_new = dict(ores_old, C="ore_copper.png")
    cave(g2b, ores_old, BEFORE, 12, 8).save(REP / "cena_mix_antes.png")
    cave(g2, ores_new, PEND, 12, 8).save(REP / "cena_mix_depois.png")


def cell(bg, parts, size):
    im = Image.new("RGBA", size, (0, 0, 0, 255))
    if bg == "floor":
        for yy in range(0, size[1], T):
            for xx in range(0, size[0], T):
                im.alpha_composite(load("floor_mist_0.png"), (xx, yy))
    for (n, src, pos) in parts:
        im.alpha_composite(load(n, src), pos)
    return im


def build_matrix():
    """colunas = minérios; linhas = formas. antes e depois."""
    cols = [("Ferro", "iron"), ("Silício", "silicon"), ("Gelo", "ice"), ("Magmatita", "magmatite"), ("Cobre", "copper"),
            ("Rocha comum", None)]
    rows = ["Parede", "Veio 2×2", "Rocha pequena", "Ícone", "Pickup"]
    out = {}
    for ver in ("antes", "depois"):
        for ci, (_, k) in enumerate(cols):
            if k == "copper" and ver == "antes":
                continue
            src = (BEFORE if ver == "antes" else PEND) if k in ("iron", "copper") else SPR
            nm = lambda base: f"{base}_{k}.png"
            face = lambda: ("wall_face_mist.png", SPR, (0, 32))
            # parede: topo + (minério) + face
            parts = [("wall_mist_0.png", SPR, (0, 0))] + ([(nm("ore"), src, (0, 0))] if k else []) + [face()]
            out[(ver, 0, ci)] = cell("none", parts, (32, 56))
            out[(ver, 1, ci)] = cell("floor", [(nm("vein"), src, (0, 0))] if k else [], (64, 64)) if k else None
            out[(ver, 2, ci)] = cell("floor", [((f"rock_small_{k}_0.png" if k != "magmatite" else "rock_small_magmatite_0.png")
                                               if k else "rock_small.png", src, (0, 0))], (32, 32))
            out[(ver, 3, ci)] = cell("none", [(nm("icon"), src, (0, 0))] if k else [], (16, 16)) if k else None
            out[(ver, 4, ci)] = cell("none", [(nm("pickup"), src, (0, 0))] if k else [], (16, 16)) if k else None
    for key, im in out.items():
        if im is not None:
            im.save(CELLS / f"{key[0]}_{key[1]}_{key[2]}.png")
    return cols, rows, out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
CSS = """
:root{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:16px}
.wrap{max-width:1320px;margin:0 auto;padding-block:32px 80px}
h1{font-size:40px;margin:8px 0}h2{margin:44px 0 8px;border-top:1px solid var(--line);padding-top:24px}h3{margin:20px 0 6px;color:var(--gold)}
.eyebrow{font:12px monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
.note{border-left:3px solid var(--cyan);background:var(--panel);padding:10px 16px;margin:16px 0}
.muted{color:var(--muted)}code{background:#2a201b;padding:1px 5px}
img{image-rendering:pixelated;display:block}
.chk{background-color:#342c28;background-image:linear-gradient(45deg,#423835 25%,transparent 25%,transparent 75%,#423835 75%),linear-gradient(45deg,#423835 25%,transparent 25%,transparent 75%,#423835 75%);background-size:16px 16px;background-position:0 0,8px 8px;padding:8px;display:inline-block}
.row{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end}
figure{margin:0}figcaption{font:12px monospace;color:var(--muted);margin-top:4px;max-width:30ch}
table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:6px 10px;text-align:center;vertical-align:middle}th{font:12px monospace;color:var(--muted)}
.ba{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.tag{font:11px monospace;padding:2px 8px;border:1px solid var(--line);background:var(--panel)}.ok{color:var(--ok)}
.pal i{display:inline-block;width:34px;height:22px;margin-right:2px;vertical-align:middle;border:1px solid #0006}
"""


def im(src, scale=1, cls="", cap=None, w=None):
    p = REP / src
    iw, ih = Image.open(p).size
    t = f'<img src="{src}" width="{iw * scale}" height="{ih * scale}" alt="">'
    box = f'<div class="chk">{t}</div>' if cls == "chk" else t
    return f"<figure>{box}" + (f"<figcaption>{cap}</figcaption>" if cap else "") + "</figure>"


def pal(p):
    return '<span class="pal">' + "".join(f'<i style="background:{c}" title="{c}"></i>' for c in p) + "</span> " + \
        " ".join(f"<code>{c}</code>" for c in p)


def report(cols, rows, mat):
    cop = ["ore_copper", "vein_copper", "rock_small_copper_0", "rock_small_copper_1", "icon_copper", "pickup_copper"]
    iron = ["ore_iron", "vein_iron", "rock_small_iron_0", "rock_small_iron_1", "icon_iron", "pickup_iron"]
    sc = {"ore": 6, "vein": 4, "rock": 6, "icon": 12, "pickup": 12}

    def sprites(names, folder):
        s = ""
        for n in names:
            kind = "ore" if n.startswith("ore") else "vein" if n.startswith("vein") else "rock" if n.startswith("rock") \
                else "icon" if n.startswith("icon") else "pickup"
            wpx = SIZES[kind][0]
            s += f'<div><div class="muted" style="font:12px monospace">{n}.png · {wpx}×{SIZES[kind][1]}</div>' \
                 f'<div class="row"><div>{im(f"{folder}/{n}.png", 1, "chk", "1×")}</div>' \
                 f'<div>{im(f"{folder}/{n}.png", sc[kind], "chk", f"{sc[kind]}×")}</div></div></div>'
        return f'<div class="row" style="align-items:flex-start;gap:36px">{s}</div>'

    def matrix(ver):
        h = "<tr><th></th>" + "".join(f"<th>{c[0]}</th>" for c in cols) + "</tr>"
        for ri, rn in enumerate(rows):
            h += f"<tr><th>{rn}</th>"
            for ci in range(len(cols)):
                m = mat.get((ver, ri, ci))
                if m is None:
                    h += '<td class="muted">·</td>'
                else:
                    z = 3 if ri in (0, 3, 4) else 2
                    if ri == 3 or ri == 4:
                        z = 5
                    h += f'<td>{im(f"cells/{ver}_{ri}_{ci}.png", z)}</td>'
            h += "</tr>"
        return f"<table>{h}</table>"

    ba_rows = ""
    for n in iron:
        kind = "ore" if n.startswith("ore") else "vein" if n.startswith("vein") else "rock" if n.startswith("rock") \
            else "icon" if n.startswith("icon") else "pickup"
        z = {"ore": 5, "vein": 3, "rock": 5, "icon": 10, "pickup": 10}[kind]
        ba_rows += f'<tr><th>{n}</th><td>{im(f"before/{n}.png", z, "chk")}</td><td>{im(f"pendentes/{n}.png", z, "chk")}</td></tr>'
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Hesper · v0.6 Fundo: cobre e ferro</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="eyebrow">v0.6 · bloco Fundo · PRA APROVAR</div>
<h1>Cobre novo e ferro com paleta nova</h1>
<p class="muted">Nada foi promovido pra <code>assets/sprites/</code>. Tudo em <code>pendentes/</code>, gerado por
<code>tools/sprites/v06_fundo_cobre_ferro.py</code> (determinístico). Mesmos nomes, tamanhos e âncoras da família do ferro.</p>
<div class="note"><b>v1.0 · o que tem aqui.</b> (1) Família do cobre: laranja-salmão com manchas de verdete (verde-azulado), 6 PNGs.
(2) Ferro recolorido pra bege/cinza-acastanhado de pedra, mesmo desenho (conferido: com a paleta velha o script reproduz
byte a byte os PNGs do jogo). (3) Trecho de parede com 7 tiles de cobre colados e comparação de todos os minérios, antes × depois.</div>

<h2>1 · Cobre</h2>
<p>Referência do dono (só estilo, nada copiado): a pepita laranja-avermelhada com a mancha verde-azulada de oxidação na parte
iluminada. Aproveitei: a mistura de salmão claro + vermelho-terroso nas sombras, e o verdete em manchas que seguem as 4 faixas
de luz do minério (cada faixa laranja tem a sua irmã verde, então a mancha continua com brilho e sombra). Forma igual ao resto da
família "chunky": pintas gordas cravadas na parede, lajes angulosas rachadas no veio, calombos no bruto.</p>
<div class="row"><figure><img src="ref/cobre_ref.png" height="120" style="image-rendering:auto" alt=""><figcaption>ref do dono</figcaption></figure></div>
<p>Cobre: {pal(COPPER[:4])}<br>Verdete: {pal(PATINA[:4])}<br><span class="muted">a 5ª cor (fundo do buraco, <code>#52210f</code>) é compartilhada.</span></p>
{sprites(cop, "pendentes")}

<h3>Trecho de parede com veio de 7 tiles (chão e parede do estágio névoa)</h3>
<p>Mesma ordem de desenho do jogo: chão, topo da parede elevado 24 px com o <code>ore_copper</code> por cima, face 32×24.
Aglomerado irregular de 7 e, embaixo, o pior caso: 7 em linha reta.</p>
<div class="row"><figure>{im("cena_cobre_veio7.png", 2)}<figcaption>aglomerado de 7 · 2×</figcaption></figure></div>
<div class="row" style="margin-top:12px"><figure>{im("cena_cobre_linha7.png", 2)}<figcaption>7 em linha reta · 2×</figcaption></figure></div>

<h2>2 · Ferro com paleta nova</h2>
<p>Referência do dono: tons bege-rosado no topo, cinza-acastanhado nos flancos. Aproveitei esses tons, sem copiar o desenho.</p>
<div class="row"><figure><img src="ref/ferro_paleta_ref.png" height="120" style="image-rendering:auto" alt=""><figcaption>ref do dono</figcaption></figure></div>
<p>Antes: {pal(IRON_OLD[:4])}<br>Depois: {pal(IRON_NEW[:4])}<br><span class="muted">fundo do buraco: {IRON_OLD[4]} → {IRON_NEW[4]}.</span></p>
{sprites(iron, "pendentes")}
<h3>Antes × depois</h3>
<table><tr><th></th><th>antes (no jogo)</th><th>depois (pendente)</th></tr>{ba_rows}</table>
<div class="note"><code>icon_iron_ingot</code> ficou como está (barra de aço cinza-azulada, <code>#1b1630</code>): não destoa do ferro bege, ao contrário,
lê como "ferro refinado" ao lado do bruto. Não mexi.</div>

<h2>3 · Leitura dos minérios lado a lado</h2>
<p>Cada coluna é um minério, cada linha uma forma (parede sobre <code>wall_mist</code>, veio e rocha sobre <code>floor_mist</code>).</p>
<h3>Antes</h3>{matrix("antes")}
<h3>Depois (ferro novo + cobre)</h3>{matrix("depois")}
<h3>Na caverna, tudo junto (2×)</h3>
<div class="ba"><figure>{im("cena_mix_antes.png", 2)}<figcaption>antes: ferro, silício, gelo, magmatita</figcaption></figure>
<figure>{im("cena_mix_depois.png", 2)}<figcaption>depois: ferro bege + cobre (dir.)</figcaption></figure></div>

<h2>Pro Dev integrar</h2>
<ul>
<li>Novos (6): <code>ore_copper</code> 32×32 (overlay no topo elevado em (x, y−24), igual ao ferro), <code>vein_copper</code> 64×64 (2×2, overlay),
<code>rock_small_copper_{{0,1}}</code> 32×32, <code>icon_copper</code> 16×16, <code>pickup_copper</code> 16×16. Mesmas âncoras do ferro.</li>
<li>Ferro (6): substitui <code>ore_iron</code>, <code>vein_iron</code>, <code>rock_small_iron_{{0,1}}</code>, <code>icon_iron</code>, <code>pickup_iron</code>. Mesmos nomes e tamanhos.</li>
<li>Cores que o jogo usa por código pra "brilho do minério no escuro" e afins (<code>game/</code>, ex. cor do ferro <code>(232,160,102)</code>) precisam acompanhar: ferro novo base <code>{IRON_NEW[2]}</code>, cobre base <code>{COPPER[2]}</code>.</li>
<li>Sem animação. Contorno só nos pedaços soltos (icon/pickup/rocha); parede e veio são overlay sem contorno, como o ferro.</li>
</ul>
</div></body></html>"""
    (REP / "index.html").write_text(html, encoding="utf-8")


def main():
    build_sprites()
    for p in sorted(PEND.iterdir()):
        a = np.array(Image.open(p))
        ok = set(np.unique(a[:, :, 3])) <= {0, 255}
        exp = SIZES["ore" if p.name.startswith("ore") else "vein" if p.name.startswith("vein") else "rock"
                    if p.name.startswith("rock") else "icon" if p.name.startswith("icon") else "pickup"]
        print(p.name, Image.open(p).size, "tamanho OK" if Image.open(p).size == exp else "TAMANHO ERRADO", "alpha OK" if ok else "ALPHA RUIM")
    build_scenes()
    cols, rows, mat = build_matrix()
    report(cols, rows, mat)


if __name__ == "__main__":
    main()
