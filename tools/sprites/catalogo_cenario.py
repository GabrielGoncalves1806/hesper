#!/usr/bin/env python3
"""Catalogo do cenario NAO destrutivel (formacoes, fumarolas, soltos, decalques, cratera, blocos de gelo).

Gera reports/design/catalogo_cenario/index.html + img/*.png a partir do que o jogo USA hoje:
assets/sprites/regions/*.png (indexados) + regions_palettes.json + numeros de game/config.py.
So leitura: nao escreve em assets/ nem em game/.

  python3 tools/sprites/catalogo_cenario.py            # monta o report (PIL + numpy)
  uv run python tools/sprites/catalogo_cenario.py --counts   # (opcional) conta o que o gerador do jogo espalha
                                                            # nas seeds 1, 7 e 42 -> catalogo_cenario/counts.json
"""
from __future__ import annotations

import ast
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "assets" / "sprites" / "regions"
OUT = ROOT / "reports" / "design" / "catalogo_cenario"
IMG = OUT / "img"
SEEDS = (1, 7, 42)


# ---------------------------------------------------------------------------------------------------------------
# Modo --counts: roda o gerador real do jogo (precisa de pygame, entao via `uv run`)
# ---------------------------------------------------------------------------------------------------------------
def counts_mode():
    import collections
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from game import config as C
    from game import ground
    from game.geo import add_vents, generate_geo

    meta = json.loads(C.REGIONS_PALETTES.read_text())
    art = ground.RegionArt()
    ids = {id(v): n for n, vs in art.decals.items() for v in vs}
    res = {"seeds": list(SEEDS), "formations": {}, "v8": {}, "v9": {}, "decals": {}}

    def put(bucket, name, i, val):
        res[bucket].setdefault(name, [0] * len(SEEDS))[i] = val

    for i, seed in enumerate(SEEDS):
        geo = generate_geo(seed, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)
        add_vents(geo, C.BASE_TILE)
        for k, n in collections.Counter(f.kind for f in geo.formations).items():
            put("formations", k, i, n)
        for k, n in collections.Counter(n for row in ground.decor_items(geo).values() for _, n, _ in row).items():
            put("v8", k, i, n)
        v9 = ground.decor_items_v9(geo, meta["v9_density"]["decor_p"])
        for k, n in collections.Counter(d.name for row in v9.values() for d in row).items():
            put("v9", k, i, n)
        tcls, skip = ground.tile_classes(geo), ground.decal_skip_tiles(geo)
        nb = -(-C.SURFACE_W * C.TILE // ground.BP)
        seen, cnt = set(), collections.Counter()
        for by in range(nb):
            for bx in range(nb):
                for d in ground.decals_for_block(geo, art, bx, by, tcls, skip):
                    x, y, _, idx = d[:4]
                    b = idx
                    while id(b) not in ids and getattr(b, "base", None) is not None:
                        b = b.base
                    name = ids.get(id(b))
                    if name and (x, y, name) not in seen:
                        seen.add((x, y, name))
                        cnt[name] += 1
        for k, n in cnt.items():
            put("decals", k, i, n)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "counts.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print("counts.json ok")


# ---------------------------------------------------------------------------------------------------------------
# Cores: mesma logica do jogo (indice 0..7 rampa, 8 contorno, 9 sombra alfa 80, 255 transparente)
# ---------------------------------------------------------------------------------------------------------------
if "--counts" in sys.argv:
    counts_mode()
    sys.exit(0)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

META = json.loads((REG / "regions_palettes.json").read_text())
RAMPS = META["ramps"]
FORM = META["formations"]
FILES = META["files"]
OUTLINE = (0x1b, 0x16, 0x30)
STAGES = ("storm", "arid", "mist", "green")
STAGE_PT = {"storm": "Tempestade", "arid": "Árido", "mist": "Névoa", "green": "Verde"}
REGION_PT = {"plateau": "Planalto", "salar": "Salar", "basalt": "Basalto", "frost": "Faixa gelada", "bed": "Leito seco"}


def hexrgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def ramp(table, region, stage):
    """Lista de cores: as da rampa (8) + contorno + preto; 'A+B' = A e, a partir do indice 10, as da B."""
    if "+" in table:
        first, extra = table.split("+", 1)
        base = ramp(first, region, stage)
        return base + [hexrgb(c) for c in RAMPS[extra][region][stage]]
    return [hexrgb(c) for c in RAMPS[table][region][stage]] + [OUTLINE, (0, 0, 0)]


def load_idx(name):
    return np.array(Image.open(REG / name))


def colorize(idx, pal):
    h, w = idx.shape
    out = np.zeros((h, w, 4), np.uint8)
    for i in np.unique(idx):
        if i == 255:
            continue
        m = idx == i
        if i < len(pal):
            out[m, :3] = pal[i]
            out[m, 3] = 80 if i == 9 else 255
        else:
            out[m] = (255, 0, 255, 255)     # indice fora da paleta: aparece magenta (nao deveria)
    return Image.fromarray(out)


def ground_crop(region, stage, w, h, pad=10, at=(48, 48)):
    """Pedaco do chao da regiao (textura ground_*.png recolorida) pra mostrar o decalque no lugar certo."""
    tex = load_idx(f"ground_{region}.png")
    ox, oy = at
    crop = tex[oy:oy + h + 2 * pad, ox:ox + w + 2 * pad]
    return colorize(crop, ramp("BASE", region, stage))


def sprite(name, table, region, stage):
    return colorize(load_idx(name), ramp(table, region, stage))


# ---------------------------------------------------------------------------------------------------------------
# Numeros do jogo (config.py lido por texto: nada de importar o jogo)
# ---------------------------------------------------------------------------------------------------------------
CFG = (ROOT / "game" / "config.py").read_text(encoding="utf-8")


def cfg(name):
    m = re.search(rf"^{name}\s*=\s*(.+?)(?:\s+#.*)?$", CFG, re.M)
    return ast.literal_eval(m.group(1))


GEO_FORMATIONS = cfg("GEO_FORMATIONS")
GEO_SMALL = cfg("GEO_SMALL_FORMATIONS")
DECOR_P = cfg("GROUND_DECOR_P")
ICE_GATES = cfg("ICE_GATES")
V9 = META["v9_density"]
DECAL_P = META["decal_p"]
DECAL_MIX = META["decal_mix"]
V9_P, V9_MIX, V9_DECOR = V9["decal_p"], V9["decal_mix"], V9["decor_p"]
VENT = META["vent_density"]
COUNTS = {}
if (OUT / "counts.json").exists():
    COUNTS = json.loads((OUT / "counts.json").read_text())
SMALL_LAYER1 = ("gravel", "scoria", "plates", "ridges", "crack")


def obs(bucket, key):
    v = COUNTS.get(bucket, {}).get(key)
    if v is None:
        return "" if not COUNTS else " · obs. 0/0/0"
    return " · obs. " + "/".join(str(x) for x in v)


def rng_txt(r):
    return f"{r[0]}–{r[1]}" if r[0] != r[1] else str(r[0])


# ---------------------------------------------------------------------------------------------------------------
# Imagens
# ---------------------------------------------------------------------------------------------------------------
IMG.mkdir(parents=True, exist_ok=True)
for f in IMG.glob("*.png"):
    f.unlink()


def save(im, key):
    path = IMG / f"{key}.png"
    im.save(path)
    return {"src": f"img/{key}.png", "w": im.width, "h": im.height}


def zoom_of(w, h, wmax=400, hmax=280):
    return max(1, min(4, wmax // w, hmax // h))


class Item:
    def __init__(self, key, group, name, files, region, density, collide, status, maker, note="", extra=None,
                 variants_label="Variantes no Árido (cores embutidas no PNG)", thumb_file=None):
        self.key, self.group, self.name, self.files = key, group, name, files
        self.region, self.density, self.collide, self.status = region, density, collide, status
        self.maker, self.note, self.extra = maker, note, extra or []
        self.variants_label = variants_label
        self.strips = []      # [(rotulo, [ {src,w,h,cap} ])]
        self.thumb = None


ITEMS: list[Item] = []
GROUPS = [
    ("g1", "1 · Formações grandes", "Marcos fixos do mapa (bíblia §11). Bloqueiam o andar na pegada; o resto da caixa é livre."),
    ("g2", "2 · Formações pequenas", "Formações miúdas da v9 (sem afloramento nem marcador no mapa). Bloqueiam o tile da pegada."),
    ("g3", "3 · Fumarolas", "Formações pequenas do basalto (v9.1). Dormente abaixo do limiar de calor, ativa acima; a fumaça é partícula."),
    ("g4", "4 · Decoração solta com altura", "Soltos ordenados pelo pé, NÃO colidem nem mineram. Somem onde tem máquina, veio, destroço, rocha, parede ou formação."),
    ("g5", "5 · Decalques de chão", "Planos, pintados no chão assado (célula de 96 px). Não colidem, não mineram. Cores = rampa BASE da região onde caem."),
    ("g6", "6 · Peças da paisagem fixas", "Cratera de impacto, manto de ejeção, geada do portão e os blocos de gelo do portão."),
]


# ---- formacoes ------------------------------------------------------------------------------------------------
def form_maker(kind):
    info = FORM[kind]

    def mk(f, stage):
        return sprite(f, info["ramp"], info["region"], stage)
    return mk


def add_form(group, kind, key_cfg, collide, extra_note="", counts_key=None, density_override=None, files=None):
    info = FORM[kind]
    rng = key_cfg
    off = rng == (0, 0)
    dens = density_override or (f"config: {rng_txt(rng)} por mundo" + obs("formations", counts_key or kind))
    if off:
        dens = f"config: {rng_txt(rng)} por mundo (0–0 = não nasce)"
    ITEMS.append(Item(kind, group, info["name"], files or [info["sprite"]], REGION_PT[info["region"]], dens, collide,
                      "off" if off else "on", form_maker(kind), extra_note))


add_form("g1", "monolith", GEO_FORMATIONS["monolith"], "Sim · 1 tile (a pegada). Hoodoo de 1×1.",
         "Rampa SAND do planalto. Pedra de topo no v8.3.")
add_form("g1", "arch", GEO_FORMATIONS["arch"], "Sim · 2 tiles (os 2 pilares das pontas). O vão de 3 tiles do meio é livre e dá pra passar por baixo.",
         "Caixa 5×1; só os pilares bloqueiam. Rampa SAND.")
add_form("g1", "basalt_spires", GEO_FORMATIONS["basalt_spires"], "Sim · 6 tiles (3×2).", "Basalto colunar. Rampa HILL do basalto.")
add_form("g1", "cone", GEO_FORMATIONS["cone"], "Sim · 6 tiles (3×2).",
         "Cone de escória. As fumarolas sorteiam 60% da posição num raio de 10–30 tiles dele.")
add_form("g1", "salt_ridge", GEO_FORMATIONS["salt_ridge"], "Seria sim · 5 tiles (5×1), mas não nasce.",
         "DESLIGADA por decisão do dono (config 0–0): o sprite continua em assets/, o jogo não espalha.")
add_form("g2", "split_rock", GEO_SMALL["split_rock"], "Sim · 1 tile.", "Rampa HILL.")
add_form("g2", "ice_needles", GEO_SMALL["ice_needles"], "Sim · 3 tiles (3×1).", "Rampa ICE da faixa gelada.")
add_form("g2", "salt_pillar", GEO_SMALL["salt_pillar"], "Seria sim · 1 tile, mas não nasce.",
         "DESLIGADO por decisão do dono (config 0–0): sal no lago dissolveria.")
add_form("g2", "lava_tube", GEO_SMALL["lava_tube"], "Seria sim · 3 tiles (3×1), mas não nasce.",
         "DESLIGADO por decisão do dono (config 0–0).")


# ---- fumarolas ------------------------------------------------------------------------------------------------
def vent_item(kind, label):
    info = FORM[kind]
    cnt = VENT["count"][kind.removeprefix("vent_")]
    d, a = info["sprites"]["dormant"], info["sprites"]["active"]
    tiles = len(info["tiles"])

    def mk(f, stage):
        return sprite(f, info["ramp"], info["region"], stage)
    it = Item(kind, "g3", info["name"], [d, a], "Basalto",
              f"{rng_txt(cnt)} por mundo (total 5–8: cone 2–3, par 1–2, chaminé 1–2)" + obs("formations", kind),
              f"Sim · {tiles} tile{'s' if tiles > 1 else ''} ({info['size'][0]}×{info['size'][1]}).", "on", mk,
              "Dormente (boca escura) abaixo do limiar de calor; ativa (brasa na boca, crosta de enxofre) acima. "
              "Cada uma sorteia o limiar entre o calor da etapa 1 e o da 4 da cratera. A fumaça sai das bocas "
              f"{info['mouths']} (px do sprite).",
              variants_label="Dormente × ativa no Árido")
    it.extra = [("Dormente nos 4 estágios", [(d, s, STAGE_PT[s]) for s in STAGES], mk),
                ("Ativa nos 4 estágios", [(a, s, STAGE_PT[s]) for s in STAGES], mk)]
    # a tira padrao ("os 4 estagios") mostraria so a dormente: troca pelas duas tiras acima
    it.skip_default_stages = True
    ITEMS.append(it)


vent_item("vent_cone", "cone")
vent_item("vent_pair", "par")
vent_item("vent_chimney", "chaminé")


# ---- soltos ---------------------------------------------------------------------------------------------------
def decor_maker(f, stage):
    info = FILES[f]
    return sprite(f, info["ramp"], info["region"], stage)


def decor_chance(name):
    out = []
    for cls, lst in V9_DECOR.items():
        for n, p in lst:
            if n == name:
                out.append(f"{p * 100:g}% dos tiles de {REGION_PT[cls].lower()}")
    return out


def add_decor(name, label, ver, region_txt, v8_region=None):
    files = [f"decor_{name}_{i}.png" for i in range(3)]
    if v8_region:
        dens = f"{DECOR_P * 100:g}% dos tiles de {REGION_PT[v8_region].lower()}" + obs("v8", name)
    else:
        dens = " + ".join(decor_chance(name)) + obs("v9", name)
    ITEMS.append(Item("decor_" + name, "g4", f"{label} ({ver})", files, region_txt, dens + " (antes de filtrar tile ocupado)",
                      "Não colide", "on", decor_maker,
                      f"Rampa {FILES[files[0]]['ramp']} da região do arquivo ({FILES[files[0]]['region']})."))


add_decor("shards", "Lascas de basalto", "v8", "Basalto", "basalt")
add_decor("salt_crystals", "Cristais de sal", "v8", "Salar", "salar")
add_decor("ice_chunks", "Pedaços de gelo", "v8", "Faixa gelada", "frost")
add_decor("pebbles", "Seixos", "v9", "Planalto e leito seco")
add_decor("boulder", "Matacão", "v9", "Planalto")
add_decor("slabs", "Lajes", "v9", "Planalto")
add_decor("mud_curls", "Lama enrolada", "v9", "Leito seco")
add_decor("salt_mound", "Montinho de sal", "v9", "Salar")
add_decor("salt_slabs", "Placas de sal", "v9", "Salar")
add_decor("bombs", "Bombas vulcânicas", "v9", "Basalto")
add_decor("column_stub", "Toco de coluna", "v9", "Basalto")
add_decor("penitentes", "Penitentes", "v9", "Faixa gelada")
add_decor("rimed_rock", "Rocha com geada", "v9", "Faixa gelada")


def moss_maker(f, stage):
    """Pedra do mesmo N + overlay de musgo (rampa MOSS fixa, so no Verde)."""
    stone_name = f.replace("_moss", "")
    info = FILES[stone_name]
    base = sprite(stone_name, info["ramp"], info["region"], "green")
    moss = [hexrgb(c) for c in RAMPS["MOSS"]]
    mpal = moss + [moss[-1]] * (8 - len(moss)) + [OUTLINE, (0, 0, 0)]
    ov = colorize(load_idx(f), mpal)
    base.alpha_composite(ov)
    return base


moss_files = [f"decor_{n}_moss_{i}.png" for n in ("boulder", "column_stub") for i in range(3)]
mi = Item("decor_moss", "g4", "Musgo do Verde (v9) · sobre matacão e toco", moss_files, "Planalto (matacão) e Basalto (toco)",
          "Sempre que o matacão ou o toco de mesmo N existe, só no Verde (moss_on: boulder, column_stub)", "Não colide", "on",
          moss_maker, "Overlay em cima da pedra de mesmo N: rampa MOSS fixa (4 cores, não muda com estágio), índices 0..3. "
          "Aparece só no estágio 4. Abaixo: a pedra com o musgo, sempre no Verde.",
          variants_label="Pedra + musgo no Verde (matacão 0..2, toco 0..2)")
mi.only_green = True
ITEMS.append(mi)

# ---- decalques ------------------------------------------------------------------------------------------------
V8_ORDER = ["patch_dark", "patch_light", "crack", "plates", "gravel", "wind", "ridges", "scoria", "stain", "icesheet"]
V9_ORDER = ["vein", "oxide", "saltpoly", "efflor", "ropy", "icepoly", "rime", "trail", "ripples"]
DECAL_PT = {"patch_dark": "Mancha escura", "patch_light": "Mancha clara", "crack": "Rachadura longa", "plates": "Placas",
            "gravel": "Cascalho", "wind": "Sulcos de vento", "ridges": "Cristas", "scoria": "Escória", "stain": "Mancha de óxido/ferrugem",
            "icesheet": "Placa de gelo", "vein": "Veio no chão", "oxide": "Óxido", "saltpoly": "Polígonos de sal", "efflor": "Eflorescência",
            "ropy": "Lava encordoada", "icepoly": "Polígonos de gelo", "rime": "Geada", "trail": "Rastro", "ripples": "Ondulações",
            "fumarole": "Respiro de fumarola"}


def decal_regions(name):
    """[(região, onde, chance por célula)] pelo decal_mix de cada região (v8 e v9)."""
    out = []
    for reg in ("plateau", "salar", "basalt", "frost", "bed"):
        p = 0.0
        if reg in DECAL_MIX:
            mix = DECAL_MIX[reg]
            tot = sum(w for _, w in mix)
            w = dict(mix).get(name, 0)
            if w:
                p += DECAL_P[reg] * w / tot
            small = [m for m in mix if m[0] in SMALL_LAYER1] or mix
            ws = dict(small).get(name, 0)
            if ws:
                p += DECAL_P[reg] * 0.6 * ws / sum(x for _, x in small)
        if reg in V9_MIX:
            mix = V9_MIX[reg]
            w = dict(mix).get(name, 0)
            if w:
                p += V9_P[reg] * w / sum(x for _, x in mix)
        if p > 0:
            out.append((reg, p))
    return out


def decal_item(name, ver):
    files = sorted(f.name for f in REG.glob(f"decal_{name}_*.png"))
    regs = decal_regions(name)
    off = not regs
    if off:
        reg_txt, dens = "Basalto (saiu do sorteio)", "0 · fora do decal_mix do basalto"
        regs = [("basalt", 0)]
    else:
        reg_txt = ", ".join(REGION_PT[r] for r, _ in regs)
        dens = "; ".join(f"{REGION_PT[r]} {p * 100:.0f}% das células" for r, p in regs)
        dens += obs("decals", name)
    first = regs[0][0]
    w0, h0 = Image.open(REG / files[0]).size

    def mk(f, stage, region=None):
        r = region or first
        d = colorize(load_idx(f), ramp("BASE", r, stage))
        w, h = d.size
        bg = ground_crop(r, stage, w, h)
        bg.alpha_composite(d, (10, 10))
        return bg
    it = Item("decal_" + name, "g5", f"{DECAL_PT[name]} ({ver})", files, reg_txt, dens, "Não colide (plano, só pintura)",
              "off" if off else "on", mk,
              ("DESLIGADO por decisão do dono: saiu do decal_mix do basalto ('a gente já tem a fumarola pra isso'); "
               "o PNG fica em assets/. " if off else "") +
              f"Mostrado sobre o chão de {REGION_PT[first].lower()}; cores = BASE da região onde cai. "
              f"Cada decalque tem {len(files)} variações e 50% de espelho (menos vento).",
              variants_label=f"Variações no Árido sobre o chão de {REGION_PT[first].lower()}")
    if len(regs) > 1:
        it.extra = [("Mesma variação 0 em cada região onde nasce (Árido)",
                     [(files[0], "arid", REGION_PT[r]) for r, _ in regs], None)]
        it.extra_regions = [r for r, _ in regs]
    ITEMS.append(it)


for n in V8_ORDER:
    decal_item(n, "v8")
for n in V9_ORDER:
    decal_item(n, "v9")
decal_item("fumarole", "v9")

# ---- paisagem -------------------------------------------------------------------------------------------------
CRATER_PAL = lambda stage: ramp("BASE", "plateau", stage)[:10] + ramp("ICE", "frost", stage)[:8] + [hexrgb(c) for c in RAMPS["METAL"]]  # noqa: E731


def crater_mk(f, stage):
    return colorize(load_idx(f), CRATER_PAL(stage))


ci = Item("crater", "g6", "Cratera de impacto · etapas 0..4 (tampa de gelo)", [f"crater_impact_{i}.png" for i in range(5)],
          "Planalto (a 15–20 tiles da base)", "1 por mundo (a etapa vai de 0 tampada a 4 vazia, conforme o calor)",
          "Sim · 9 tiles (3×3); o E no tile do meio de baixo desce quando a etapa é 4", "on", crater_mk,
          f"Âncora {FORM['crater_impact_0']['anchor']} no 168×150. Paleta: 0..9 BASE do planalto, 10..17 ICE, 18..20 METAL; "
          "cor pelo estágio do tile do meio. Aparece como a tampa derrete (F4 derrete na hora).",
          variants_label="Etapas 0 (tampada) a 4 (vazia) no Árido")
ITEMS.append(ci)
ITEMS.append(Item("ejecta", "g6", "Manto de ejeção da cratera", ["crater_ejecta.png"], "Planalto (em volta da cratera)",
                  "1 por mundo, centrado no mesmo ponto da cratera", "Não colide (camada de decalque, vai depois do chão)",
                  "on", lambda f, s: sprite(f, "BASE", "plateau", s), "Rampa BASE do planalto. Desenhado antes dos veios."))
ITEMS.append(Item("frost_ring", "g6", "Geada do gelo-portão (frost_ring)", ["frost_ring.png"], "Faixa gelada (em volta de cada portão)",
                  f"1 por gelo-portão ({rng_txt(ICE_GATES)} portões por mundo); aparece enquanto o gelo derrete",
                  "Não colide (plano no chão)", "on", lambda f, s: sprite(f, "BASE", "frost", s),
                  "Rampa BASE da faixa gelada. Centrada no pé do portão e 60 px acima dele."))

RECIPES = META["recipes"]
BLK = META["blocks"]


def ice_block_item(kind, label):
    keys = [f"{kind}_0", f"{kind}_1"]
    files = [BLK[k]["sprite"] for k in keys]
    where = {k: [r for r, rec in RECIPES.items() if any(b["b"] == k for b in rec["blocks"])] for k in keys}
    fr = {k: BLK[k]["frame"] for k in keys}

    def mk(f, stage):
        full = sprite(f, "ICE", "frost", stage)
        k = next(k for k in keys if BLK[k]["sprite"] == f)
        return full.crop((0, 0, fr[k][0], fr[k][1]))   # quadro 0 (inteiro)

    def strip(f, stage):
        return sprite(f, "ICE", "frost", stage)
    it = Item("iceblock_" + kind, "g6", f"Bloco de gelo do portão · {label}", files, "Faixa gelada (bolsões da cordilheira norte)",
              f"{rng_txt(ICE_GATES)} portões por mundo, 3–5 blocos cada. " +
              "; ".join(f"{BLK[k]['name']} entra nas receitas {', '.join(where[k])}" for k in keys),
              "Sim, por retângulo do bloco (caixa por quadro); some ao derreter (melt), não se quebra nem se minera",
              "on", mk,
              "Tira de 8 quadros = 8 escalas, do bloco inteiro ao último caquinho (derretimento por fração `melt` da receita). "
              "Rampa ICE. O sprite antigo ice_gate_0..2 não é mais desenhado desde o M3.5.",
              variants_label="Quadro 0 (inteiro) das 2 variações no Árido")
    it.extra = [(f"Tira completa de 8 quadros · {files[0]} (Árido)", [(files[0], "arid", "8 escalas")], strip),
                (f"Tira completa de 8 quadros · {files[1]} (Árido)", [(files[1], "arid", "8 escalas")], strip)]
    it.raw_strip = True
    ITEMS.append(it)


ice_block_item("shard", "lasca")
ice_block_item("slab", "laje")
ice_block_item("boulder", "pedra")

# ---------------------------------------------------------------------------------------------------------------
# Monta as imagens
# ---------------------------------------------------------------------------------------------------------------
for it in ITEMS:
    k = it.key
    vs = [it.maker(f, "arid") for f in it.files]
    it.strips.append((it.variants_label, [dict(save(im, f"{k}_v{i}"), cap=f) for i, (im, f) in enumerate(zip(vs, it.files))]))
    it.thumb = it.strips[0][1][0]
    if getattr(it, "only_green", False):
        pass
    elif getattr(it, "skip_default_stages", False):
        pass
    elif k.startswith("decor_moss"):
        pass
    else:
        stg = [dict(save(it.maker(it.files[0], s), f"{k}_{s}"), cap=STAGE_PT[s]) for s in STAGES]
        it.strips.append((f"Os 4 estágios · {it.files[0]}", stg))
    for j, (label, files, mk) in enumerate(it.extra):
        if mk is None:        # decalque por região
            ims = []
            for (f, s, c), r in zip(files, it.extra_regions):
                d = colorize(load_idx(f), ramp("BASE", r, s))
                bg = ground_crop(r, s, d.width, d.height)
                bg.alpha_composite(d, (10, 10))
                ims.append(dict(save(bg, f"{k}_x{j}_{r}"), cap=c))
        else:
            ims = [dict(save(mk(f, s), f"{k}_x{j}_{i}_{s}"), cap=c) for i, (f, s, c) in enumerate(files)]
        it.strips.append((label, ims))
    # crateras e portoes: tira de estagios extra pra etapa 0 e 4
    if k == "crater":
        for lv in (0, 4):
            f = f"crater_impact_{lv}.png"
            it.strips.append((f"Etapa {lv} nos 4 estágios", [dict(save(crater_mk(f, s), f"{k}_e{lv}_{s}"), cap=STAGE_PT[s])
                                                              for s in STAGES]))

# ---------------------------------------------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------------------------------------------
n_on = sum(i.status == "on" for i in ITEMS)
n_off = sum(i.status == "off" for i in ITEMS)


def status_tag(s):
    return '<span class="tag on">no jogo</span>' if s == "on" else '<span class="tag off">desligado (fora do jogo)</span>'


def fig(im, z, cap, real=False):
    w, h = im["w"] * z, im["h"] * z
    return (f'<figure><div class="chk"><img class="px" src="{im["src"]}" width="{w}" height="{h}" alt=""></div>'
            f'<figcaption>{escape(cap)} <i>{im["w"]}×{im["h"]}{" · ×" + str(z) if z > 1 else " · 1:1"}</i></figcaption></figure>')


def strip_html(label, ims, item):
    # zoom: sprites largos (tiras de 8 quadros) ficam 1:1
    w0, h0 = ims[0]["w"], ims[0]["h"]
    if w0 > 400:
        z = 1
    else:
        z = zoom_of(w0, h0)
        if len(ims) >= 4:
            z = max(1, min(z, 880 // (len(ims) * w0 + 1)))
    body = "".join(fig(im, z, im["cap"]) for im in ims)
    if w0 > 400:
        return f'<h4>{escape(label)}</h4><div class="scroll"><div class="row">{body}</div></div>'
    return f'<h4>{escape(label)}</h4><div class="row">{body}</div>'


def real_html(item):
    im = item.thumb
    return (f'<div class="real"><b>Tamanho real (1:1)</b><div class="chk small"><img class="px" src="{im["src"]}" '
            f'width="{im["w"]}" height="{im["h"]}" alt=""></div></div>')


def item_html(n, it):
    meta = [("Arquivos", ", ".join(f"<code>{escape(f)}</code>" for f in it.files)),
            ("Nasce em", escape(it.region)), ("Quantidade", escape(it.density)),
            ("Colide?", escape(it.collide)), ("Status", status_tag(it.status))]
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in meta)
    strips = "".join(strip_html(l, ims, it) for l, ims in it.strips)
    note = f'<p class="note">{escape(it.note)}</p>' if it.note else ""
    cls = " off" if it.status == "off" else ""
    return (f'<article class="item{cls}" id="{it.key}"><header><span class="num">{n:02d}</span><h3>{escape(it.name)}</h3>'
            f'{status_tag(it.status)}</header><div class="cols"><div class="info"><table class="meta">{rows}</table>{note}'
            f'{real_html(it)}</div><div class="shots">{strips}</div></div></article>')


gname = dict((g[0], g) for g in GROUPS)
summary_rows = []
sections = []
n = 0
for gid, gtitle, gdesc in GROUPS:
    body = ""
    for it in [i for i in ITEMS if i.group == gid]:
        n += 1
        it.n = n
        body += item_html(n, it)
        t = it.thumb
        summary_rows.append(
            f'<tr class="{it.status}"><td>{n:02d}</td><td><img class="px th" src="{t["src"]}" alt=""></td>'
            f'<td><a href="#{it.key}"><b>{escape(it.name)}</b></a><br><small>{gtitle.split(" · ")[1]}</small></td>'
            f'<td>{escape(it.region)}</td><td>{escape(it.density)}</td><td>{escape(it.collide)}</td><td>{status_tag(it.status)}</td></tr>')
    sections.append(f'<section id="{gid}"><h2>{gtitle}</h2><p class="lede">{gdesc}</p>{body}</section>')

off_names = ", ".join(i.name for i in ITEMS if i.status == "off")
counts_note = (f"As colunas “obs.” são o que o gerador real do jogo espalha nas seeds {'/'.join(map(str, COUNTS['seeds']))} "
               "(antes de tirar tile ocupado por máquina, veio ou destroço)." if COUNTS else
               "Sem contagem real do gerador (rode com --counts); os números são os do config e do JSON.")

CSS = """
:root{--bg:#15100e;--panel:#1e1714;--panel2:#241b17;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;--alert:#ff6a55;
--f-label:"Silkscreen",ui-monospace,monospace;--f-display:"Pixelify Sans",ui-monospace,monospace;--f-body:"IBM Plex Sans",system-ui,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,monospace}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.55 var(--f-body);padding-inline:16px}
.wrap{max-width:1560px;margin:0 auto;padding-block:48px 90px}
.eyebrow{font:12px var(--f-label);letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
h1{font:600 clamp(32px,5vw,48px)/1.05 var(--f-display);margin:10px 0 14px}
h2{font:600 24px/1.2 var(--f-display);margin:0 0 8px}
h2::before{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px}
h3{font:600 19px var(--f-display);margin:0}
h4{font:11px var(--f-label);color:var(--gold);letter-spacing:.06em;text-transform:uppercase;margin:16px 0 8px}
section{margin-top:56px}.lede{color:var(--muted);max-width:100ch;margin:0 0 18px}
code{font-family:var(--f-mono);font-size:.88em;color:var(--gold)}
a{color:var(--cyan);text-decoration:none}a:hover{text-decoration:underline}
.v2{margin-top:20px;max-width:1100px;background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--gold);padding:14px 18px}
.v2 b{font:13px var(--f-label);color:var(--gold)}.v2 ul{margin:8px 0 0;padding-left:18px;color:var(--muted)}.v2 li{margin-bottom:5px}.v2 li b{color:var(--fg);font:inherit}
.tag{font:10px var(--f-label);padding:3px 7px;border:1px solid;letter-spacing:.05em;white-space:nowrap}
.tag.on{color:var(--ok);border-color:var(--ok)}.tag.off{color:var(--alert);border-color:var(--alert)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{font:11px var(--f-label);color:var(--gold);background:var(--panel2)}td{color:var(--muted)}td b{color:var(--fg)}
tr.off td{background:#2a1512}tr.off td b{color:#e9b3aa}
img.px{image-rendering:pixelated;display:block}img.th{max-width:84px;max-height:56px;width:auto;height:auto}
.chk{display:inline-block;background:conic-gradient(#2a211d 25%,#332822 0 50%,#2a211d 0 75%,#332822 0) 0 0/16px 16px;border:1px solid var(--line);line-height:0}
.chk.small{margin-top:6px}
figure{margin:0}figcaption{font:11px var(--f-label);color:var(--muted);margin-top:5px;letter-spacing:.03em;max-width:420px;word-break:break-all}figcaption i{color:var(--cyan);font-style:normal}
.row{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}.scroll{overflow-x:auto;padding-bottom:6px}.scroll .row{flex-wrap:nowrap}
.item{margin-top:24px;background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--rust);padding:16px 18px}
.item.off{border-top-color:var(--alert);background:#1f1513}.item.off .shots{opacity:.72}
.item header{display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap}.num{font:12px var(--f-label);color:var(--rust)}
.cols{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:22px}
@media (max-width:1000px){.cols{grid-template-columns:1fr}}
.meta th{width:92px;white-space:nowrap}.note{color:var(--muted);font-size:13px;margin:10px 0}
.real{margin-top:10px;font-size:12px;color:var(--muted)}
.dev{border-left:3px solid var(--cyan)}
nav.idx{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}nav.idx a{font:11px var(--f-label);border:1px solid var(--line);padding:5px 9px;background:var(--panel)}
"""

legend = (
    "<ul>"
    "<li><b>Fonte da verdade:</b> <code>assets/sprites/regions/</code> + <code>regions_palettes.json</code> (formations, v9_density, vent_density, ramps) "
    "e os números de <code>game/config.py</code> (<code>GEO_FORMATIONS</code>, <code>GEO_SMALL_FORMATIONS</code>, <code>GROUND_DECOR_P</code>, <code>ICE_GATES</code>). "
    "As cores seguem a regra do jogo: índice do PNG → rampa da região no estágio.</li>"
    f"<li><b>Placar:</b> {len(ITEMS)} itens · <b>{n_on} no jogo</b> · <b>{n_off} desligados</b> ({escape(off_names)}).</li>"
    "<li>Desligados por decisão do dono: crosta e pilar de sal (config 0–0), tubo de lava (config 0–0) e o decalque de respiro do basalto (saiu do <code>decal_mix</code>). Os PNGs seguem em assets/.</li>"
    f"<li>{counts_note} Decalques: “% das células” = chance por célula de 96×96 px (≈9 tiles), somando o sorteio grande, o miúdo (60%) e o da v9.</li>"
    "<li>O gelo-portão antigo (<code>ice_gate_0..2.png</code>) não é mais desenhado desde o M3.5 (vira blocos); o <code>hill_top/hill_face</code> e os chãos <code>ground_*</code> não entram aqui porque são terreno, não componentes.</li>"
    "</ul>")

# Seleção do dono: "pausar/remover temporariamente" (marcação no localStorage + botão que copia a lista)
PICK_SNIPPET = r"""
<!-- Seleção do dono: "pausar/remover temporariamente". Marcação fica no navegador (localStorage) e o botão copia a lista. -->
<style>
.pick{display:inline-flex;align-items:center;gap:6px;margin-left:auto;font-size:13px;cursor:pointer;color:#ffb38a}
.pick input{width:18px;height:18px;accent-color:#e2733a;cursor:pointer}
tr.picked td,article.picked{outline:2px solid #e2733a;outline-offset:-2px;background:rgba(226,115,58,.10)}
#pickbar{position:fixed;left:16px;right:16px;bottom:16px;z-index:50;display:flex;gap:12px;align-items:center;
 background:#1b1630;border:1px solid #e2733a;border-radius:10px;padding:10px 14px;color:#f3ece4;font:14px system-ui;
 box-shadow:0 6px 24px rgba(0,0,0,.5)}
#pickbar b{color:#ffb38a}#pickbar button{background:#e2733a;color:#1b1630;border:0;border-radius:6px;padding:7px 12px;
 font-weight:700;cursor:pointer}#pickbar button.ghost{background:transparent;color:#f3ece4;border:1px solid #6b5a62}
#pickbar .list{flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;opacity:.85}
body{padding-bottom:80px}
</style>
<div id="pickbar"><span><b id="pickn">0</b> pra pausar/remover</span><span class="list" id="picklist">marque os itens no ✓ de cada um</span>
<button id="pickcopy">Copiar lista</button><button class="ghost" id="pickclear">Limpar</button></div>
<script>
(function(){
  var KEY='hesper_catalogo_pausar', sel={};
  try{sel=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){sel={}}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(sel))}catch(e){}}
  var items=[].slice.call(document.querySelectorAll('article.item'));
  var names={};
  items.forEach(function(a){
    var num=(a.querySelector('.num')||{}).textContent||'', h=(a.querySelector('h3')||{}).textContent||a.id;
    names[a.id]=num+' '+h;
    var lab=document.createElement('label');lab.className='pick';
    lab.innerHTML='<input type="checkbox" data-id="'+a.id+'"> pausar/remover';
    a.querySelector('header').appendChild(lab);
  });
  // coluna na tabela-resumo
  var rows=[].slice.call(document.querySelectorAll('table tr'));
  rows.forEach(function(tr){
    var link=tr.querySelector('a[href^="#"]');
    if(!link){ if(tr.querySelector('th')&&!tr.dataset.p){var th=document.createElement('th');th.textContent='Pausar?';tr.appendChild(th);tr.dataset.p=1} return; }
    var id=link.getAttribute('href').slice(1); if(!names[id]) return;
    var td=document.createElement('td');td.innerHTML='<label class="pick"><input type="checkbox" data-id="'+id+'"></label>';
    tr.appendChild(td); tr.dataset.id=id;
  });
  function render(){
    var ids=Object.keys(sel).filter(function(k){return sel[k]});
    document.querySelectorAll('input[data-id]').forEach(function(i){i.checked=!!sel[i.dataset.id]});
    items.forEach(function(a){a.classList.toggle('picked',!!sel[a.id])});
    rows.forEach(function(tr){if(tr.dataset.id)tr.classList.toggle('picked',!!sel[tr.dataset.id])});
    document.getElementById('pickn').textContent=ids.length;
    document.getElementById('picklist').textContent=ids.length?ids.map(function(k){return names[k]}).join(' · '):'marque os itens no ✓ de cada um';
  }
  document.addEventListener('change',function(e){var i=e.target;if(!i.dataset||!i.dataset.id)return;sel[i.dataset.id]=i.checked;save();render()});
  document.getElementById('pickclear').onclick=function(){sel={};save();render()};
  document.getElementById('pickcopy').onclick=function(){
    var ids=Object.keys(sel).filter(function(k){return sel[k]});
    var txt='Pausar/remover temporariamente ('+ids.length+'):\n'+ids.map(function(k){return '- '+names[k]+' ('+k+')'}).join('\n');
    var done=function(){var b=document.getElementById('pickcopy');b.textContent='Copiado!';setTimeout(function(){b.textContent='Copiar lista'},1500)};
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(done,function(){prompt('Copie:',txt)})}else{prompt('Copie:',txt)}
  };
  render();
})();
</script>
"""

html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Catálogo do cenário não destrutível</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Pixelify+Sans:wght@400;600&family=Silkscreen&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · catálogo</div>
<h1>Cenário que não quebra</h1>
<p class="lede">Tudo o que o jogo espalha no terreno e que não minera nem quebra: formações, fumarolas, soltos com altura, decalques de chão e as peças fixas da paisagem. Nada aqui é arte nova: é o que está nos assets de hoje, recolorido pelo mesmo caminho do jogo.</p>
<div class="v2"><b>catálogo v1.0 · o que é isto</b>{legend}</div>
<nav class="idx">{"".join(f'<a href="#{g[0]}">{g[1]}</a>' for g in GROUPS)}<a href="#resumo">Tabela-resumo</a></nav>

<section id="resumo"><h2>Tabela-resumo</h2>
<p class="lede">{len(ITEMS)} itens: {n_on} no jogo, {n_off} desligados (linhas vermelhas). Clique no nome pra ir ao item.</p>
<table><tr><th>#</th><th></th><th>Item</th><th>Nasce em</th><th>Quantidade / densidade</th><th>Colide?</th><th>Status</th></tr>
{"".join(summary_rows)}</table></section>

{"".join(sections)}
</div>{PICK_SNIPPET}</body></html>"""
(OUT / "index.html").write_text(html, encoding="utf-8")
print(f"ok: {len(ITEMS)} itens, {n_on} no jogo, {n_off} desligados, {len(list(IMG.glob('*.png')))} imagens")
