#!/usr/bin/env python3
"""v0.6 Fundo · M2 · CHÃO ASSADO da caverna (a receita da superfície, game/ground.py, aplicada à caverna).
PROPOSTA: nada vai pra assets/sprites sem o ok do dono. NÃO mexe em game/.

    python3 tools/sprites/v06_fundo_m2_assado.py

Saída: reports/design/v06_fundo_m2_biomas/assado/
    ground_cave_{plateau,salar,basalt,frost}.png   PNG indexado (P, 8 bits) 512x512 que emenda nos 4 lados
    decal_<nome>_<v>.png                           decalques indexados (255 = vazio), índice = rampa da classe
    cave_ground_palettes.json                      rampas (BASE, stage "cave"), decal_p/mix/cell, files
    cenas/, previews/                              o que o report mostra
e reescreve a seção "Chão assado" no index.html do M2 (primeiro regenera o index do M2 com o v06_fundo_m2_biomas).

Índices (igual à superfície, 1 paleta só porque a caverna não tem estágio):
    0 fenda mais funda · 1 fenda/sombra (é o 1 px da DIVISA entre regiões, `bake_strip` pinta idx 1) · 2 escuro
    3 BASE · 4 claro · 5 brilho · 6, 7 acentos da classe (brasa no basalto, sal e grão no salar, brilho no gelo)
    código no pixel = classe·16 + índice, classes 0 plateau, 1 salar, 2 basalt, 3 frost (geo.REGION_NAMES)
Pra montar as cenas usa o PRÓPRIO game/ground.py (pygame trocado por stub): bake_block_codes + decals_for_block
com uma arte da caverna no lugar da RegionArt, então o que está nas cenas é o que o motor faz.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import regions_core as R  # noqa: E402

m2 = importlib.import_module("v06_fundo_m2_biomas")   # põe o stub do pygame, o ROOT no path e importa game.*
from game import cave_gen, surface_gen  # noqa: E402
from game import config as C  # noqa: E402
from game import geo as geo_mod  # noqa: E402
from game import ground as G  # noqa: E402

ROOT = m2.ROOT
OUT = m2.OUT / "assado"
T = 32
TEX = 512
NAMES = ("plateau", "salar", "basalt", "frost")
PT = m2.PT

# ---------------------------------------------------------------------------------------------------------------
# 1. Paletas (8 cores por classe; a caverna só tem 1 estágio, chave "cave")
# ---------------------------------------------------------------------------------------------------------------
BASE = {
    # centro: as cores do floor_mist de hoje (54443b 5e4c42 685448 6e5a4f 75604f 85715f a08b78), com 2 fendas mais escuras
    "plateau": ["#3f322c", "#4c3d35", "#685448", "#6e5a4f", "#75604f", "#85715f", "#a08b78", "#5e4c42"],
    # salar: areia clara e quente. 0/1/2 = a mancha úmida (borda funda, miolo, franja), 5 flor de sal, 6 grão escuro, 7 grão claro
    "salar": ["#85734f", "#9a8863", "#a8946c", "#b6a279", "#c3b087", "#efe7d3", "#9c8a64", "#d3c39f"],
    # basalto: cinza-chumbo/preto (rampa névoa do basalto da superfície), 6/7 = brasa só como detalhe pequeno
    "basalt": ["#141418", "#1c1c20", "#2d2c32", "#343439", "#403f45", "#545257", "#b8381d", "#ff8a45"],
    # gelo: azul-acinzentado de gelo velho, 5 placa lisa, 6 brilho, 7 faísca
    "frost": ["#2f3d5a", "#40527a", "#566d93", "#6880a6", "#7b93b8", "#9fc0e0", "#c2dcf3", "#eef8ff"],
}

# ---------------------------------------------------------------------------------------------------------------
# 2. Texturas 512x512 (emendam: todo ruído tem `period`, todo deslocamento é em toro)
# ---------------------------------------------------------------------------------------------------------------
roll = np.roll


def dil(m):
    return m | roll(m, 1, 0) | roll(m, -1, 0) | roll(m, 1, 1) | roll(m, -1, 1)


def ero(m):
    return m & roll(m, 1, 0) & roll(m, -1, 0) & roll(m, 1, 1) & roll(m, -1, 1)


def tex_plateau(seed=111) -> np.ndarray:
    """Centro: o chão marrom de hoje, em manchas grandes e macias, com pontos escuros, pedrisco e poucas rachaduras."""
    xs, ys = R.grid(TEX, TEX)
    p = TEX
    n = R.organic(xs, ys, p, 5, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n < np.quantile(n, 0.24)] = 2
    idx[n > np.quantile(n, 0.80)] = 4
    idx[n > np.quantile(n, 0.955)] = 5
    n2 = R.organic(xs, ys, p, 12, seed + 5)
    idx[(n2 < np.quantile(n2, 0.09)) & (idx <= 3)] = 7
    sp = R.hash2(xs, ys, seed + 3)
    idx[(sp < 0.022) & (idx >= 2)] = 7
    idx[(sp > 0.985) & (idx == 3)] = 4
    wx = xs + 5 * (R.vnoise(xs, ys, p / 16, seed + 4, 16) - 0.5)
    wy = ys + 5 * (R.vnoise(xs, ys, p / 16, seed + 5, 16) - 0.5)
    _, edge, _ = R.voronoi(wx % p, wy % p, p / 6, seed + 6, 6)
    crack = (edge < 0.9) & (R.vnoise(xs, ys, p / 8, seed + 7, 8) > 0.74)       # só uns pedaços, nada de rede
    idx[crack] = 1
    idx[roll(crack, 1, 0) & ~crack] = 4
    idx = R._pebbles(idx, seed + 8, 0.05, top=5, body=4, low=1, step=6)
    idx = R._pebbles(idx, seed + 9, 0.02, top=6, body=5, low=7, step=9)
    return idx


def tex_salar(seed=121) -> np.ndarray:
    """Salar: areia clara, ondulações de vento, manchas úmidas de infiltração (franja, miolo, borda funda),
    crosta de sal rachada e flor de sal."""
    xs, ys = R.grid(TEX, TEX)
    p = TEX
    n = R.organic(xs, ys, p, 6, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n > np.quantile(n, 0.70)] = 4
    idx[n < np.quantile(n, 0.10)] = 2
    # ondulações de vento: linhas finas e quebradas (período 16 px, emenda)
    wy = ys + 6 * (R.vnoise(xs, ys, p / 8, seed + 1, 8) - 0.5)
    line = (wy % 16) < 1.0
    seg = (R.vnoise(xs, ys, p / 16, seed + 2, 16) > 0.66) & (R.hash2(xs // 13, ys // 16, seed + 3) < 0.55)
    idx[line & seg] = 7
    idx[roll(line & seg, 1, 0) & ~(line & seg) & (R.hash2(xs // 3, ys, seed + 4) < 0.5)] = 6
    # infiltração: manchas úmidas grandes
    w = R.organic(xs, ys, p, 4, seed + 10)
    m = w > np.quantile(w, 0.87)
    halo = dil(m) & ~m
    ring = m & ~ero(m)
    deep = ero(ero(ero(m))) & (R.hash2(xs, ys, seed + 11) < 0.14)
    dry = ~dil(dil(m))
    idx[halo] = 2
    idx[m] = 1
    idx[ring & (R.hash2(xs // 2, ys // 2, seed + 12) < 0.8)] = 0
    idx[deep] = 0
    # crosta de sal rachada (só no seco)
    wx2 = xs + 4 * (R.vnoise(xs, ys, p / 32, seed + 5, 32) - 0.5)
    wy2 = ys + 4 * (R.vnoise(xs, ys, p / 32, seed + 6, 32) - 0.5)
    _, e, cid = R.voronoi(wx2 % p, wy2 % p, p / 8, seed + 20, 8)
    crack = (e < 0.9) & (R.hash2(cid, 0, seed + 21) < 0.42) & (R.vnoise(xs, ys, p / 8, seed + 22, 8) > 0.42) & dry
    idx[crack] = 6
    idx[roll(crack, 1, 0) & ~crack & dry] = 7
    # flor de sal: grãos claros soltos e uns tufinhos
    sp = R.hash2(xs, ys, seed + 7)
    grain = (sp > 0.9955) & dry
    idx[grain] = 5
    idx[roll(grain, 1, 1) & ~grain & (idx != 5)] = 7
    tuft = (sp < 0.0012) & dry
    idx[tuft | roll(tuft, 1, 1)] = 5
    idx[roll(tuft, 1, 0) & ~tuft] = 6
    idx = R._pebbles(idx, seed + 30, 0.012, top=7, body=3, low=6, step=8)
    return idx


def tex_basalt(seed=131) -> np.ndarray:
    """Basalto: carvão avermelhado, fraturas retas e angulosas, pedrisco e fios de BRASA (poucos, nas fraturas)."""
    xs, ys = R.grid(TEX, TEX)
    p = TEX
    n = R.organic(xs, ys, p, 6, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n < np.quantile(n, 0.24)] = 2
    idx[n < np.quantile(n, 0.05)] = 1
    idx[n > np.quantile(n, 0.90)] = 4
    _, edge, cid = R.voronoi(xs, ys, p / 9, seed + 2, 9, jitter=0.95)
    crack = (edge < 1.0) & (R.hash2(cid, 0, seed + 3) < 0.5) & (R.vnoise(xs, ys, p / 8, seed + 10, 8) > 0.35)
    idx[crack] = 0
    idx[roll(crack, 1, 0) & ~crack & (R.hash2(xs // 3, ys, seed + 4) < 0.6)] = 4
    sp = R.hash2(xs, ys, seed + 5)
    idx[(sp < 0.03) & (idx >= 2)] = 1
    idx[(sp > 0.975) & (idx >= 2)] = 4
    idx[(sp > 0.996) & (idx >= 2)] = 5
    # brasa: outra rede de fraturas, só uns fios (22% das células, e só onde o ruído deixa)
    _, e3, c3 = R.voronoi(xs, ys, p / 7, seed + 40, 7, jitter=0.95)
    wd = 1.0 + 1.0 * R.vnoise(xs, ys, p / 24, seed + 44, 24)          # largura do fio varia (1 a 3 px)
    ember = (e3 < wd) & (R.hash2(c3, 1, seed + 41) < 0.17) & (R.vnoise(xs, ys, p / 8, seed + 42, 8) > 0.5)
    idx[roll(ember, -1, 0) & ~ember] = 0          # tampa escura em cima
    idx[roll(ember, 1, 0) & ~ember] = 1           # e embaixo
    idx[ember] = 6
    idx[ember & (R.hash2(xs // 2, ys // 2, seed + 43) < 0.42)] = 7
    idx = R._pebbles(idx, seed + 8, 0.07, top=5, body=4, low=0)
    return idx


def tex_frost(seed=141) -> np.ndarray:
    """Gelo: azul-acinzentado, geada em manchas, placas lisas, rachaduras de gelo com lábio claro, faíscas."""
    xs, ys = R.grid(TEX, TEX)
    p = TEX
    n = R.organic(xs, ys, p, 5, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n < np.quantile(n, 0.14)] = 2
    idx[n > np.quantile(n, 0.70)] = 4
    idx[n > np.quantile(n, 0.93)] = 5
    _, edge, cid = R.voronoi(xs, ys, p / 12, seed + 2, 12)
    crack = (edge < 0.9) & (R.hash2(cid, 0, seed + 3) < 0.4) & (R.vnoise(xs, ys, p / 8, seed + 6, 8) > 0.4)
    idx[crack] = 0
    idx[roll(crack, 1, 0) & ~crack] = 5
    idx[roll(crack, -1, 0) & ~crack & (R.hash2(xs, ys // 2, seed + 8) < 0.5)] = 1
    sp = R.hash2(xs, ys, seed + 4)
    idx[(sp < 0.0022)] = 7
    idx[(sp >= 0.0022) & (sp < 0.006) & (idx >= 3)] = 6
    idx[(sp > 0.99) & (idx <= 3)] = 2
    idx = R._pebbles(idx, seed + 5, 0.04, top=6, body=4, low=1, step=7)
    return idx


TEXTURES = {"plateau": tex_plateau, "salar": tex_salar, "basalt": tex_basalt, "frost": tex_frost}

# ---------------------------------------------------------------------------------------------------------------
# 3. Decalques (índices da rampa da classe onde o centro cai; 255 = vazio)
# ---------------------------------------------------------------------------------------------------------------


def remap(a: np.ndarray, table: dict) -> np.ndarray:
    out = a.copy()
    for k, v in table.items():
        out[a == k] = v
    return out


def pad_crop(a: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(a != 255)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def d_wet(seed, w, h):
    """Infiltração: mancha úmida do lençol. Franja (2) por fora, miolo (1), borda funda (0) em pedaços, miolo fundo salpicado."""
    a = R.d_patch(seed, w, h, "dark")
    m = np.zeros((h + 8, w + 8), bool)
    m[4:-4, 4:-4] = a != 255
    out = np.full(m.shape, 255, np.uint8)
    ys, xs = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    halo = dil(m) & ~m
    out[halo & (R.hash2(xs, ys, seed + 1) < 0.85)] = 2
    out[m] = 1
    ring = m & ~ero(m)
    out[ring & (R.hash2(xs // 2, ys // 2, seed + 2) < 0.8)] = 0
    out[ero(ero(m)) & (R.hash2(xs, ys, seed + 3) < 0.16)] = 0
    return pad_crop(out)


def d_efflor(seed, w=84, h=56):
    """Flor de sal: mancha clara irregular de cristalzinhos (7 miolo, 5 pontas brilhando), franja de grãos soltos, sombra embaixo."""
    a = R.d_patch(seed, w, h, "light")
    m = np.zeros((h + 8, w + 8), bool)
    m[4:-4, 4:-4] = a != 255
    ys, xs = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    out = np.full(m.shape, 255, np.uint8)
    fr = dil(dil(m)) & ~m
    out[fr & (R.hash2(xs, ys, seed + 1) < 0.14)] = 5
    out[m] = 7
    out[m & (R.hash2(xs // 2, ys // 2, seed + 2) < 0.34)] = 5
    out[m & (R.hash2(xs, ys, seed + 3) < 0.10)] = 6
    shade = roll(m, 1, 0) & ~m
    out[shade & (R.hash2(xs, ys, seed + 4) < 0.6)] = 6
    return pad_crop(out)


def d_ember_crack(seed, length):
    """Fissura de brasa: a rachadura do núcleo (0) cheia de brasa (6, com 7 em pedaços), lábio escuro embaixo."""
    a = R.d_crack(seed, length)
    crack = a == 0
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    out = np.full(a.shape, 255, np.uint8)
    out[a == 2] = 1
    out[a == 5] = 4
    out[roll(crack, -1, 0) & ~crack] = 0
    out[crack] = 6
    glow = crack & (R.hash2(xs // 2, ys // 3, seed + 3) < 0.5)
    out[glow] = 7
    out[crack & (R.hash2(xs, ys, seed + 4) < 0.12)] = 0
    return out


def d_ember_pool(seed, w=44, h=30):
    """Poça de brasa: lasca de rocha derretida, miolo vivo (7), borda 6, anel escuro (0) e sombra (1)."""
    a = R.d_patch(seed, w, h, "dark")
    m = np.zeros((h + 8, w + 8), bool)
    m[4:-4, 4:-4] = a != 255
    ys, xs = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    out = np.full(m.shape, 255, np.uint8)
    out[dil(m) & ~m] = 0
    out[roll(dil(m) & ~m, 1, 0) & ~dil(m)] = 1
    out[m] = 6
    inner = ero(ero(m))
    out[inner] = 7
    out[inner & (R.hash2(xs, ys, seed + 5) < 0.25)] = 6
    return pad_crop(out)


def d_ice_crack(seed, length):
    a = R.d_crack(seed, length)
    return remap(a, {5: 6, 2: 1})


def d_sparkle(seed, w=44, h=28):
    """Gelo: um punhado de faíscas (cruzinhas de 3 px, 7 no centro, 6 nas pontas)."""
    rng = np.random.default_rng(seed)
    a = np.full((h, w), 255, np.uint8)
    for _ in range(int(rng.integers(3, 6))):
        x, y = int(rng.integers(3, w - 3)), int(rng.integers(3, h - 3))
        a[y, x] = 7
        if rng.random() < 0.7:
            a[y - 1, x] = a[y + 1, x] = a[y, x - 1] = a[y, x + 1] = 6
    return pad_crop(a)


def decal_set() -> dict[str, np.ndarray]:
    out = {}
    for v in range(3):
        out[f"soil_{v}"] = remap(R.d_patch(300 + v, (224, 176, 144)[v], (96, 80, 64)[v], "dark"), {2: 7})   # centro: 7 = marrom escuro
        out[f"patch_dark_{v}"] = R.d_patch(305 + v, (176, 144, 112)[v], (80, 64, 56)[v], "dark")           # basalto: 2/1 = cinza escuro
        out[f"patch_light_{v}"] = R.d_patch(310 + v, (192, 150, 120)[v], (80, 64, 56)[v], "light")
        out[f"crack_{v}"] = R.d_crack(320 + v, (220, 170, 130)[v])
        out[f"wet_{v}"] = d_wet(330 + v, (150, 112, 84)[v], (80, 64, 52)[v])
        out[f"efflor_{v}"] = d_efflor(340 + v, (96, 76, 60)[v], (60, 52, 40)[v])
        out[f"ridges_{v}"] = R.d_wind(350 + v, (150, 120, 96)[v], None, light=7, dark=6)
        out[f"ember_crack_{v}"] = d_ember_crack(360 + v, (190, 150, 120)[v])
        out[f"ember_pool_{v}"] = d_ember_pool(370 + v, (30, 26, 22)[v], (20, 18, 16)[v])
        out[f"ash_{v}"] = remap(R.d_patch(380 + v, (170, 130, 100)[v], (70, 56, 48)[v], "light"), {5: 4, 4: 4})
        out[f"ice_crack_{v}"] = d_ice_crack(390 + v, (200, 160, 120)[v])
        out[f"icesheet_{v}"] = R.d_icesheet(400 + v, (128, 104, 88)[v], (72, 60, 52)[v])
        out[f"frostpatch_{v}"] = remap(R.d_patch(410 + v, (180, 140, 110)[v], (76, 60, 52)[v], "light"), {5: 5})
        out[f"sparkle_{v}"] = d_sparkle(420 + v)
    for v in range(4):
        out[f"gravel_{v}"] = R.d_gravel(430 + v, palette=(5, 4, 2, 1), accent=4)
        out[f"scoria_{v}"] = R.d_gravel(440 + v, 60, 40, None, (5, 4, 2, 0), 3)
    return out


# `crack` serve pra todas as classes (rampa troca a cor): na caverna o nome do arquivo é crack_*, ice_crack_* sobra só
# no gelo. Pra o filtro do 2º sorteio do `decals_for_block` (só gravel/scoria/plates/ridges/crack), os miúdos têm esses nomes.
SHARED_CRACK = True
DECAL_P = {"plateau": 0.40, "salar": 0.40, "basalt": 0.45, "frost": 0.45}
DECAL_MIX = {
    "plateau": [("soil", 3), ("patch_light", 2), ("crack", 4), ("gravel", 4)],
    "salar": [("wet", 4), ("efflor", 3), ("ridges", 3), ("crack", 2)],
    "basalt": [("scoria", 5), ("ember_crack", 3), ("ash", 3), ("crack", 2), ("patch_dark", 2), ("ember_pool", 0.5)],
    "frost": [("icesheet", 3), ("frostpatch", 3), ("ice_crack", 3), ("sparkle", 3), ("gravel", 1)],
}
# no frost o 2º sorteio (só miúdos) cai em ("gravel","crack")... `ice_crack` não está na lista do motor, então o frost usa `crack` também
DECAL_MIX["frost"] = [("icesheet", 3), ("frostpatch", 3), ("crack", 3), ("sparkle", 3), ("gravel", 1)]


# ---------------------------------------------------------------------------------------------------------------
# 4. Gravar PNGs indexados, JSON
# ---------------------------------------------------------------------------------------------------------------
def indexed_image(idx: np.ndarray, ramp_hex: list[str], transparent: bool = False) -> Image.Image:
    im = Image.fromarray(idx.astype(np.uint8), "P")
    pal = []
    for c in ramp_hex:
        pal += list(m2.hx(c))
    pal += [0x1B, 0x16, 0x30, 0, 0, 0]               # 8 = contorno, 9 = sombra (convenção; o chão não usa)
    pal += [0] * (768 - len(pal))
    im.putpalette(pal)
    if transparent:
        im.info["transparency"] = 255
    return im


def save_assets():
    OUT.mkdir(parents=True, exist_ok=True)
    tex = {}
    for name, fn in TEXTURES.items():
        tex[name] = fn()
        indexed_image(tex[name], BASE[name]).save(OUT / f"ground_cave_{name}.png")
    decals = decal_set()
    # só grava o que algum mix usa
    used = {n for mix in DECAL_MIX.values() for n, _ in mix}
    files = {}
    for k, a in decals.items():
        base = k.rsplit("_", 1)[0]
        if base not in used:
            continue
        cls = next(c for c in NAMES if any(base == n for n, _ in DECAL_MIX[c]))
        indexed_image(a, BASE[cls], transparent=True).save(OUT / f"decal_{k}.png", transparency=255)
        files[f"decal_{k}.png"] = {"size": f"{a.shape[1]}×{a.shape[0]}", "classes": [c for c in NAMES if any(base == n for n, _ in DECAL_MIX[c])]}
    for name in NAMES:
        files[f"ground_cave_{name}.png"] = {"size": "512×512", "class": name}
    meta = {
        "note": "Chão assado da CAVERNA (v0.6 Fundo M2). Mesmo formato do regions_palettes.json da superfície: ramps.BASE[classe][estágio] "
                "(8 cores; índice 8 = contorno e 9 = sombra vêm do código, como `RegionArt.lut`). A caverna não tem estágios: o estágio é sempre \"cave\". "
                "Classes: plateau, salar, basalt, frost (SEM leito 'bed'). Código no pixel = classe·16 + índice.",
        "stage": "cave",
        "classes": list(NAMES),
        "ramps": {"BASE": {c: {"cave": BASE[c]} for c in NAMES}},
        "decal_cell": 96,
        "decal_p": DECAL_P,
        "decal_mix": {c: [[n, w] for n, w in v] for c, v in DECAL_MIX.items()},
        "decal_small": ["gravel", "scoria", "plates", "ridges", "crack"],
        "files": files,
    }
    (OUT / "cave_ground_palettes.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    return tex, {k: v for k, v in decals.items() if k.rsplit("_", 1)[0] in used}, meta


# ---------------------------------------------------------------------------------------------------------------
# 5. Assar com o motor (game/ground.py) e colorir
# ---------------------------------------------------------------------------------------------------------------
class CaveArt:
    """O que o `RegionArt` tem, só que da caverna (4 classes, sem leito, sem v9). `ok` = True."""

    def __init__(self, tex: dict, decals: dict, meta: dict):
        self.ok = True
        self.meta = meta
        self.decal_p = meta["decal_p"]
        self.decal_mix = {k: [(n, w) for n, w in v] for k, v in meta["decal_mix"].items()}
        self.v9 = {}
        self.textures = [tex[n] for n in NAMES]
        self.tex_stack = np.stack(self.textures)
        self.decals: dict[str, list] = {}
        for k in sorted(decals):
            name, _ = k.rsplit("_", 1)
            self.decals.setdefault(name, []).append(decals[k])

    def lut(self) -> np.ndarray:
        out = np.zeros((128, 3), np.uint8)
        for c, n in enumerate(NAMES):
            out[c * 16:c * 16 + 8] = [m2.hx(h) for h in BASE[n]]
            out[c * 16 + 8] = G.OUTLINE
        return out


class CaveGeo:
    """O mínimo que `bake_strip` pede de um Geo: region, basin, seed, warp, formations."""

    def __init__(self, seed: int, region: np.ndarray):
        self.seed = seed
        self.region = region
        self.basin = np.full(region.shape, -1, np.int16)
        self.formations = []

    def warp(self, px, py):
        return geo_mod.warp_px(self.seed, px, py)


_BAKE_CACHE: dict = {}


def bake_blocks(geo: CaveGeo, art: CaveArt, bx0, by0, bx1, by1) -> np.ndarray:
    """Códigos (uint8) do retângulo de blocos [bx0..bx1]×[by0..by1], montado de bake_block_codes."""
    ctx = G.BakeContext(geo)
    ctx.skip = set()
    H = (by1 - by0 + 1) * G.BP
    W = (bx1 - bx0 + 1) * G.BP
    out = np.zeros((H, W), np.uint8)
    for by in range(by0, by1 + 1):
        for bx in range(bx0, bx1 + 1):
            key = (id(geo), bx, by)
            if key not in _BAKE_CACHE:
                gen = G.bake_block_codes(geo, art, bx, by, ctx)
                res = None
                while res is None:
                    res = next(gen)
                _BAKE_CACHE[key] = res[0]
            out[(by - by0) * G.BP:(by - by0 + 1) * G.BP, (bx - bx0) * G.BP:(bx - bx0 + 1) * G.BP] = _BAKE_CACHE[key]
    return out


def ground_rgb(geo, art, x0, y0, w, h) -> np.ndarray:
    """RGB (h, w) do chão assado em px de mundo [x0, x0+w) × [y0, y0+h)."""
    bx0, by0 = x0 // G.BP, y0 // G.BP
    bx1, by1 = (x0 + w - 1) // G.BP, (y0 + h - 1) // G.BP
    codes = bake_blocks(geo, art, bx0, by0, bx1, by1)
    ox, oy = x0 - bx0 * G.BP, y0 - by0 * G.BP
    return art.lut()[codes[oy:oy + h, ox:ox + w]]


# ---------------------------------------------------------------------------------------------------------------
# 6. Cenas (mesma ordem de desenho do jogo: chão assado -> veios -> linha por linha: parede e objetos -> escuridão)
# ---------------------------------------------------------------------------------------------------------------
W, H = 34, 21
SEED = 7
CAM = (64, 64)


def render_scene2(kinds, regions, veins, rocks, ground, lut, player=None, lit=None, ambient=None, size=(960, 540),
                  cam=CAM, walls=True):
    Hh, Ww = kinds.shape
    img = Image.new("RGBA", (Ww * T, Hh * T + 2 * m2.LIFT + 8), (0, 0, 0, 255))
    img.paste(Image.fromarray(ground), (0, 0))
    w, h = size
    cx, cy = cam
    if not walls:
        return img.crop((cx, cy, cx + w, cy + h)).convert("RGB")
    SPR = m2.SPR
    for (vi, vj, res) in veins:
        img.alpha_composite(Image.open(SPR / f"vein_{res}.png").convert("RGBA"), (vi * T, vj * T))
    blocks = m2.walls_rgba(kinds, regions, lut)
    objs = {}
    for (i, j, res, var) in rocks:
        objs.setdefault(j, []).append((i * T, j * T, Image.open(SPR / f"rock_small_{res}_{var}.png").convert("RGBA")))
    if player:
        px, py = player
        objs.setdefault(int(py // T), []).append((int(px - 16), int(py - 28), Image.open(SPR / "player_down.png").convert("RGBA")))
    for r in range(Hh):
        for blk, rgba in blocks:
            m = blk["row"] == r
            if not m.any():
                continue
            piece = rgba.copy()
            piece[..., 3] = np.where(m, piece[..., 3], 0)
            ys, xs = np.nonzero(m)
            img.alpha_composite(Image.fromarray(piece[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA"),
                                (blk["x0"] + int(xs.min()), blk["y0"] + int(ys.min())))
        for (ox, oy, spr) in objs.get(r, []):
            img.alpha_composite(spr, (ox, oy))
    crop = img.crop((cx, cy, cx + w, cy + h)).convert("RGB")
    if lit is None:
        return crop
    arr = np.asarray(crop, np.float32) / 255
    lights = [(lx - cx, ly - cy, rad, col, inten) for (lx, ly, rad, col, inten) in lit]
    lm = m2.light_map(w, h, lights, ambient)
    out = np.clip(arr * lm * 255, 0, 255).astype(np.uint8)
    for j in range(Hh):                                   # brilhinho do minério no escuro (como no M2)
        for i in range(Ww):
            res = C.ORE_TILES.get(int(kinds[j, i]))
            if not res:
                continue
            gx = i * T + 7 + int(m2.hsh(i, j, 5) * 18) - cx
            gy = j * T + 6 + int(m2.hsh(i, j, 6) * 14) - cy
            if 4 <= gx < w - 6 and 4 <= gy < h - 6:
                dark = 1 - float(lm[gy, gx].max())
                if dark > 0.2:
                    col = np.array(m2.GLINT[res], np.float32) * (0.7 * dark)
                    out[gy:gy + 2, gx:gx + 2] = np.clip(out[gy:gy + 2, gx:gx + 2].astype(np.float32) + col, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def region_weights(regions, i, j, rad=5):
    cnt = {}
    n = 0
    for jj in range(max(0, j - rad), min(regions.shape[0], j + rad + 1)):
        for ii in range(max(0, i - rad), min(regions.shape[1], i + rad + 1)):
            if np.hypot(ii - i, jj - j) <= rad:
                cnt[NAMES[regions[jj, ii]]] = cnt.get(NAMES[regions[jj, ii]], 0) + 1
                n += 1
    return {k: v / n for k, v in cnt.items()}


def find_spots(R):
    """Pontos do mapa real: fronteira de cada bioma ao longo do eixo e as duas junções com o gelo."""
    my = R.shape[0] // 2
    mx = R.shape[1] // 2
    out = {}
    row = R[my + 4]
    out["salar"] = (mx + int(np.argmax(row[mx:] == 1)), my + 4)
    out["basalt"] = (int(np.nonzero(row[:mx] == 2)[0].max()), my + 4)
    col = R[:, mx]
    out["frost"] = (mx, int(np.nonzero(col == 3)[0].max()) + 1)
    for name, want in (("juncao_no", {0, 2, 3}), ("juncao_ne", {0, 1, 3})):
        best = None
        for j in range(20, my, 2):
            for i in range(20, R.shape[1] - 20, 2):
                if set(np.unique(R[j - 4:j + 5, i - 4:i + 5]).tolist()) >= want and (i < mx) == (name == "juncao_no"):
                    best = (i, j)
                    break
            if best:
                break
        out[name] = best
    return out


def world_for(R, cx, cy):
    i0, j0 = cx - W // 2, cy - H // 2
    fn = lambda i, j: int(R[j0 + j, i0 + i])  # noqa: E731
    return i0, j0, fn


def scene_set(R, geo, art, lut, i0, j0, seedw, halls, thr=0.66, pref=(W // 2, H // 2 + 1)):
    fn = lambda i, j: int(R[j0 + j, i0 + i])  # noqa: E731
    k, r, v, ro = m2.make_world(W, H, fn, seedw, thr, halls)
    pi, pj = m2.pick_floor(k, *pref)
    ppos = (pi * T + 16, pj * T + 20)
    li, lj = m2.pick_floor(k, pi + 5, pj, [(pi, pj)])
    wts = region_weights(r, pi, pj)
    amb, col, inten = m2.mix_light(wts)
    g = ground_rgb(geo, art, i0 * T, j0 * T, W * T, H * T)
    ground = np.zeros((H * T + 2 * m2.LIFT + 8, W * T, 3), np.uint8)
    ground[:H * T] = g
    out = {
        "chao": render_scene2(k, r, v, ro, ground, lut, walls=False),
        "claro": render_scene2(k, r, v, ro, ground, lut),
        "escuro": render_scene2(k, r, v, ro, ground, lut, player=ppos,
                                lit=[m2.helmet(ppos[0], ppos[1], col, inten), m2.lamp_light(li, lj)], ambient=amb),
    }
    return out


def synthetic_four():
    """Os 4 juntos numa janela só (o mapa real tem fronteira a 36-54 tiles, não cabe): mesma geografia, bem menor."""
    b1, b2, b3 = m2.noise_line(21, 40, 2), m2.noise_line(22, 40, 2), m2.noise_line(23, 40, 2)
    Rm = np.zeros((H, W), np.uint8)
    for j in range(H):
        for i in range(W):
            Rm[j, i] = 3 if j <= 6 + b1[i] else 2 if i <= 9 + b2[j] else 1 if i >= 24 + b3[j] else 0
    return Rm


def divisa_zoom(chao: Image.Image, cx_px: int, cy_px: int) -> Image.Image:
    """Recorte 240x135 ampliado 4x (a divisa por pixel, com a fenda de 1 px)."""
    x0, y0 = max(0, min(960 - 240, cx_px - 120)), max(0, min(540 - 135, cy_px - 67))
    return chao.crop((x0, y0, x0 + 240, y0 + 135)).resize((960, 540), Image.NEAREST)


def build_scenes(art, meta):
    (OUT / "cenas").mkdir(exist_ok=True)
    rm = m2.ramps()
    lut = m2.lut_all(rm)
    c = surface_gen.crater_of(SEED)
    R = cave_gen.region_map(SEED, (c[0] + 1, c[1] + 3), 256, 256)
    geo = CaveGeo(SEED, R)
    spots = find_spots(R)
    info = {"seed": SEED, "center": [c[0] + 1, c[1] + 3], "spots": spots}
    plan = {"salar": (11, [(5, 5, 24, 11), (3, 14, 6, 5), (26, 3, 6, 5)]),
            "basalt": (12, [(5, 5, 24, 11), (3, 14, 6, 5), (26, 3, 6, 5)]),
            "frost": (13, [(5, 6, 24, 10), (3, 15, 6, 4), (26, 3, 6, 4)]),
            "juncao_no": (14, [(4, 4, 26, 13), (3, 15, 7, 4)]),
            "juncao_ne": (15, [(4, 4, 26, 13), (24, 15, 7, 4)])}
    for key, (sw, halls) in plan.items():
        cx, cy = spots[key]
        res = scene_set(R, geo, art, lut, cx - W // 2, cy - H // 2, sw, halls)
        for n, im in res.items():
            im.save(OUT / "cenas" / f"{key}_{n}.png")
        divisa_zoom(res["chao"], 480, 270).save(OUT / "cenas" / f"{key}_divisa.png")
        print("cena", key)
    # os 4 juntos (sintético) com o chão assado
    Rs = synthetic_four()
    geo4 = CaveGeo(SEED, Rs)
    res = scene_set(Rs, geo4, art, lut, 0, 0, 8, [(14, 11, 6, 5), (4, 11, 4, 4), (27, 11, 4, 4), (14, 4, 5, 3), (10, 12, 5, 2),
                                                    (22, 12, 5, 2), (16, 7, 2, 5)], 0.63, (17, 13))
    for n, im in res.items():
        im.save(OUT / "cenas" / f"quatro_{n}.png")
    # mapa real inteiro (o chão assado sem paredes, 1/8)
    big = np.zeros((256 * T // 8, 256 * T // 8, 3), np.uint8)
    for by in range(16):
        for bx in range(16):
            g = ground_rgb(geo, art, bx * G.BP, by * G.BP, G.BP, G.BP)
            sm = np.asarray(Image.fromarray(g).resize((64, 64), Image.BOX))
            big[by * 64:(by + 1) * 64, bx * 64:(bx + 1) * 64] = sm
    Image.fromarray(big).save(OUT / "cenas" / "mapa_real.png")
    # antes (tiles 32x32) x depois, mesmo mundo do salar
    cx, cy = spots["salar"]
    i0, j0 = cx - W // 2, cy - H // 2
    fn = lambda i, j: int(R[j0 + j, i0 + i])  # noqa: E731
    k, r, v, ro = m2.make_world(W, H, fn, 11, 0.66, plan["salar"][1])
    m2.render_scene(k, r, v, ro, m2.floor_images(), lut).save(OUT / "cenas" / "salar_tiles_claro.png")
    return info


def previews(tex, decals):
    (OUT / "previews").mkdir(exist_ok=True)
    for n in NAMES:
        lut = np.array([m2.hx(h) for h in BASE[n]], np.uint8)
        rgb = lut[tex[n]]
        Image.fromarray(rgb).save(OUT / "previews" / f"tex_{n}.png")
        sh = lut[np.roll(np.roll(tex[n], 256, 0), 256, 1)]            # a emenda passa pelo meio
        Image.fromarray(sh).save(OUT / "previews" / f"seam_{n}.png")
        # decalques da classe sobre a cor base
        names = [d for d, _ in DECAL_MIX[n]]
        sheet = Image.new("RGB", (1240, 0))
        rows, x, y, rh = [], 4, 4, 0
        canvas = Image.new("RGB", (1240, 520), tuple(lut[3]))
        for nm in names:
            for v in range(4):
                key = f"{nm}_{v}"
                if key not in decals:
                    continue
                a = decals[key]
                if x + a.shape[1] + 4 > 1240:
                    x, y, rh = 4, y + rh + 6, 0
                tile = np.zeros((*a.shape, 4), np.uint8)
                ok = a != 255
                tile[..., :3] = lut[np.where(ok, np.minimum(a, 7), 0)]
                tile[..., 3] = np.where(ok, 255, 0)
                canvas.paste(Image.fromarray(tile, "RGBA"), (x, y), Image.fromarray(tile, "RGBA"))
                x += a.shape[1] + 8
                rh = max(rh, a.shape[0])
        canvas.crop((0, 0, 1240, min(520, y + rh + 8))).save(OUT / "previews" / f"decais_{n}.png")


def sw_table(meta):
    h = ["<table><tr><th>classe</th>" + "".join(f"<th>{i}</th>" for i in range(8)) + "</tr>"]
    for n in NAMES:
        h.append(f"<tr><th>{PT[n]}<br>({n})</th>" + "".join(
            f"<td style='background:{c};width:84px;height:36px;font:10px monospace;color:#fffa;text-align:center;text-shadow:0 0 2px #000'>{c[1:]}</td>"
            for c in BASE[n]) + "</tr>")
    h.append("</table>")
    return "".join(h)


def section_html(info) -> str:
    sp = info["spots"]
    h = ['<!--ASSADO-->', '<h2>0 · Chão assado (a receita da superfície, na caverna)</h2>']
    h.append("""<p>O dono imaginou o chão da caverna como o da superfície: <b>não são mais tiles 32×32 sorteados</b>. É o <code>game/ground.py</code> da superfície
(<code>bake_block_codes</code> + <code>decals_for_block</code>, importados de verdade, sem mudar nada), só com a arte da caverna no lugar da <code>RegionArt</code>:
a divisa entre regiões é uma <b>curva orgânica por pixel</b> (o mesmo deslocamento de ±14 px do <code>geo.warp</code>) com <b>1 px de fenda</b> (índice 1 da rampa),
a textura é grande (512×512, emenda) e os <b>decalques</b> (manchas, rachaduras, flor de sal, brasa, geada) são espalhados pela seed. As paredes são as 4 rampas aprovadas
(só o basalto e o gelo foram reajustados, ver a nota lá em cima). Tudo abaixo vem do mapa real da caverna: <code>cave_gen.region_map(seed 7, chegada, 256, 256)</code>,
com a chegada em %s.</p>""" % tuple([tuple(info["center"])]))
    h.append("<h3>0.1 · Paletas (uma por classe, a caverna não tem estágios)</h3>" + sw_table(None))
    h.append("""<p class="muted">Índices iguais aos da superfície: 0 fenda funda · <b>1 fenda da divisa</b> · 2 escuro · 3 base · 4 claro · 5 brilho · 6 e 7 acentos
(salar: 6 grão escuro, 7 grão claro, 5 flor de sal; basalto: 6/7 brasa; gelo: 6/7 brilho e faísca). Basalto = rampa <i>névoa</i> do basalto da superfície (cinza-chumbo/preto);
gelo = a rampa <i>névoa</i> da faixa gelada, azul. O centro mantém as cores do <code>floor_mist</code> de hoje.</p>""")
    h.append("<h3>0.2 · Texturas 512×512 (esquerda: inteira 1×; direita: a mesma rolada 256 px, a emenda passa pelo meio das duas)</h3>")
    for n in NAMES:
        h.append(f"<h4 style='margin:14px 0 4px'>{PT[n]} · <code>ground_cave_{n}.png</code></h4><div class='row'>"
                 f"<img src='assado/previews/tex_{n}.png' width='512' height='512'><img src='assado/previews/seam_{n}.png' width='512' height='512'></div>")
    h.append("<h3>0.3 · Decalques por classe</h3><p class='muted'>Cada um está nos índices da rampa da classe onde o centro cai. Mix e chance (<code>decal_p</code>) no JSON.</p>")
    for n in NAMES:
        mix = ", ".join(f"{a} ({b})" for a, b in DECAL_MIX[n])
        h.append(f"<h4 style='margin:14px 0 4px'>{PT[n]} · chance {DECAL_P[n]} por célula de 96 px · {mix}</h4><img src='assado/previews/decais_{n}.png'>")
    h.append("<h3>0.4 · Divisa por pixel (recorte de 240×135 ampliado 4×, sem paredes)</h3><div class='row'>")
    for key, t in (("salar", "centro × salar"), ("basalt", "basalto × centro"), ("frost", "gelo × centro"), ("juncao_no", "junção gelo / basalto / centro")):
        h.append(f"<figure><img class='scene' src='assado/cenas/{key}_divisa.png'><figcaption>{t}</figcaption></figure>")
    h.append("</div>")
    h.append("<h3>0.5 · Fronteiras reais (recortes do mapa da caverna, com as paredes e rampas aprovadas)</h3>"
             "<p class='muted'>Cada linha: só o chão · claro (com parede) · escuro (capacete + 1 luminária, ambiente misturado pelas regiões em volta do jogador). "
             "A parede ainda troca de cor por tile (região por tile, é o motor); o chão não.</p>")
    for key, t in (("salar", "centro × salar (leste)"), ("basalt", "basalto (oeste) × centro"), ("frost", "gelo (norte) × centro"),
                   ("juncao_no", "junção NO: gelo, basalto e centro"), ("juncao_ne", "junção NE: gelo, salar e centro")):
        h.append(f"<h4 style='margin:18px 0 4px'>{t} · tile do mapa {sp[key]}</h4><div class='row'>"
                 f"<figure><img class='scene' src='assado/cenas/{key}_chao.png'><figcaption>só o chão assado</figcaption></figure>"
                 f"<figure><img class='scene' src='assado/cenas/{key}_claro.png'><figcaption>claro</figcaption></figure>"
                 f"<figure><img class='scene' src='assado/cenas/{key}_escuro.png'><figcaption>escuro</figcaption></figure></div>")
    h.append("<h3>0.6 · Os quatro juntos</h3><p class='muted'>No mapa real as fronteiras ficam a 36–54 tiles do centro, então não cabem numa tela: esta é a geografia encolhida (gelo ao norte, basalto a oeste, salar a leste, centro no meio) e, embaixo, o mapa real inteiro (só o chão assado, reduzido 8×).</p>"
             "<div class='row'><figure><img class='scene' src='assado/cenas/quatro_chao.png'><figcaption>só o chão</figcaption></figure>"
             "<figure><img class='scene' src='assado/cenas/quatro_claro.png'><figcaption>claro</figcaption></figure>"
             "<figure><img class='scene' src='assado/cenas/quatro_escuro.png'><figcaption>escuro, jogador no centro</figcaption></figure>"
             "<figure><img src='assado/cenas/mapa_real.png' width='768' height='768'><figcaption>mapa real inteiro (seed 7), reduzido</figcaption></figure></div>")
    h.append("<h3>0.7 · Antes × depois (mesmo mundo, centro × salar)</h3><div class='row'>"
             "<figure><img class='scene' src='assado/cenas/salar_tiles_claro.png'><figcaption>antes: tiles 32×32 sorteados (histórico, não será usado)</figcaption></figure>"
             "<figure><img class='scene' src='assado/cenas/salar_claro.png'><figcaption>depois: chão assado</figcaption></figure></div>")
    h.append("<h3>0.8 · Ajuste do basalto e do gelo (feedback do dono jogando)</h3><div class='row'>"
             "<figure><img src='assado/antes_v10/fronteira_basalt_claro.png' width='640'><figcaption>antes (v1.0): basalto avermelhado</figcaption></figure>"
             "<figure><img src='assado/cenas/basalt_claro.png' width='640'><figcaption>depois: cinza-chumbo/preto, brasa só no detalhe</figcaption></figure></div>"
             "<div class='row'><figure><img src='assado/antes_v10/fronteira_frost_claro.png' width='640'><figcaption>antes: gelo acinzentado (cenas antigas em tiles)</figcaption></figure>"
             "<figure><img src='assado/cenas/frost_claro.png' width='640'><figcaption>depois: gelo mais azul</figcaption></figure></div>")
    h.append('<!--/ASSADO-->')
    return "\n".join(h)


DEV_HTML = """<!--DEVASSADO--><h2>7 · Chão assado: pro Dev plugar</h2>
<ul>
<li><b>Arquivos</b> (hoje em <code>reports/design/v06_fundo_m2_biomas/assado/</code>; ao promover, sugiro uma pasta nova tipo <code>assets/sprites/cave_ground/</code>, já que os nomes de decalque repetem os da superfície):
<code>ground_cave_{plateau,salar,basalt,frost}.png</code> (PNG indexado P8, 512×512, emenda), <code>decal_&lt;nome&gt;_&lt;v&gt;.png</code> (indexados, 255 = vazio) e <code>cave_ground_palettes.json</code>.</li>
<li><b>Classes e código:</b> 0 plateau, 1 salar, 2 basalt, 3 frost (<code>geo.REGION_NAMES</code>), <b>sem leito (bed)</b>. Código no pixel = <code>classe·16 + índice</code>, igual à superfície.
O <code>bake_strip</code> funciona sem mudar: com <code>basin = -1</code> em tudo o <code>depth_field</code> dá 0 (sem leito nem marca d'água); a <code>cover_strip</code> (grama/umidade) não serve pra caverna, pode devolver zeros.</li>
<li><b>Paleta:</b> <code>cave_ground_palettes.json → ramps.BASE[classe]["cave"]</code> = 8 hex. É a tabela BASE do <code>regions_palettes.json</code> com um estágio só, de chave <code>"cave"</code>:
<code>RegionArt.ramp("BASE", classe, "cave")</code> + <code>[OUTLINE, (0,0,0)]</code> e o resto do <code>lut()</code> igual (4 classes, sem FIXED_COLORS nem cobertura). Como não tem estágio, o colorir é 1 LUT só, sem variante "m" de transição.</li>
<li><b>Decalques:</b> <code>decal_p</code> (por classe), <code>decal_mix</code> (nome, peso), <code>decal_cell = 96</code>, tudo no mesmo JSON, mesmo formato. O <code>decals_for_block</code> filtra o 2º sorteio por nomes fixos
(<code>gravel, scoria, plates, ridges, crack</code>) e eu respeitei: os miúdos da caverna têm esses nomes (a lista também está em <code>decal_small</code>). <code>art.v9 = {}</code> (sem 3º sorteio).
Um nome vale pra todas as classes que o listam (a rampa da classe pinta); <code>decal_&lt;nome&gt;_&lt;v&gt;.png</code> com <code>v</code> = 0..2 (gravel e scoria 0..3). O <code>skip</code> do motor (base e formações) não se aplica; sugiro só um raio de ~6 tiles em volta da chegada.</li>
<li><b>Região por pixel:</b> o <code>geo.region</code> é o <code>region_map(seed, chegada, 256, 256)</code> inteiro (as regiões embaixo de parede também contam, o chão é assado em tudo) e o <code>geo.warp</code> é o <code>geo.warp_px(seed, x, y)</code> da superfície, com a seed da caverna. Foi assim que as cenas foram montadas (script <code>CaveGeo</code> + <code>CaveArt</code> em <code>tools/sprites/v06_fundo_m2_assado.py</code>, 40 linhas, pode copiar).</li>
<li><b>Custo:</b> assar 1 bloco ~100 ms (com a cover inútil; sem ela menos), igual à superfície. 16×16 blocos no mapa de 256×256.</li>
<li><b>Paredes:</b> <code>ramps.json</code> continua o mesmo formato; só mudaram as cores do <b>basalto</b> (miolo cinza neutro, sem roxo; o contorno de brasa fica) e do <b>gelo</b> (um pouco mais azul). Ordem de desenho: chão assado → veios 2×2 → linha por linha (parede + objetos) → escuridão.</li>
<li><b>Não incluí:</b> soltos com altura (lascas, cristais, gelo solto) no chão da caverna: não foi pedido. Os 12 <code>floor_cave_*</code> 32×32 são histórico.</li>
</ul><!--/DEVASSADO-->"""


def patch_index(info):
    m2.write_report(m2.ramps())                               # regenera o index do M2 (idempotente)
    p = m2.OUT / "index.html"
    s = p.read_text()
    note = ('<!--NOTA--><div class="note" style="border-color:#f2c46d"><b>v1.1 · o que mudou.</b> (1) <b>Chão assado</b> da caverna (seção 0): texturas 512×512, '
            'decalques e paletas no formato da superfície, divisa curva por pixel; os 12 chãos em tiles viram histórico. (2) <b>Feedback do dono jogando:</b> '
            'o <b>basalto</b> agora é cinza-chumbo/preto como o da superfície (sem roxo/vermelho; a brasa fica só no contorno da rocha dura e em fios pequenos no chão) '
            'e o <b>gelo</b> ficou um pouco mais azul. Mudou em <code>ramps.json</code>, no chão assado e nas cenas antigas do M2 (regeradas). '
            'As rampas do centro e do salar e a <code>luz.json</code> não mudaram.</div><!--/NOTA-->')
    s = s.replace('<div class="note"><b>v1.0 · o que tem aqui.</b>', note + '<div class="note"><b>v1.0 · o que tem aqui.</b>', 1)
    s = s.replace("<h2>1 · Rampas da rocha</h2>", section_html(info) + "<h2>1 · Rampas da rocha</h2>", 1)
    s = s.replace("<h2>2 · Chão por região</h2>", "<h2>2 · Chão por região em tiles 32×32 (HISTÓRICO, não será usado)</h2>", 1)
    s = s.replace("<h2>3 · Cenas de fronteira</h2>", "<h2>3 · Cenas de fronteira com o chão em tiles (histórico)</h2>", 1)
    s = s.replace("<h2>4 · As quatro regiões juntas</h2>", "<h2>4 · As quatro regiões juntas, chão em tiles (histórico)</h2>", 1)
    s = s.replace("</div></body></html>", DEV_HTML + "</div></body></html>", 1)
    p.write_text(s)


def main():
    tex, decals, meta = save_assets()
    art = CaveArt(tex, decals, meta)
    previews(tex, decals)
    info = build_scenes(art, meta)
    (OUT / "mapa_info.json").write_text(json.dumps(info, indent=1))
    patch_index(info)
    print("ok", OUT)


if __name__ == "__main__":
    main()
