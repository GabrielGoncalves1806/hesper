#!/usr/bin/env python3
"""v0.6 bloco Fundo · M2 · cara dos biomas da caverna. PROPOSTA: nada vai pra assets/sprites sem o ok do dono.

    python3 tools/sprites/v06_fundo_m2_biomas.py

Saída: reports/design/v06_fundo_m2_biomas/ (ramps.json, luz.json, floors/, cenas/, index.html).
Só LÊ assets/sprites/ e game/ (reaproveita a geometria da rocha, game/hills.py `bake_block` + `colorize_block`, e
a ordem de desenho: chão -> veios -> linha por linha: parede (topo y-24 + face) e objetos da linha -> escuridão).
O pygame é trocado por um stub: nada de janela, roda no python3 do sistema. Determinístico (seeds fixas).
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.modules.setdefault("pygame", MagicMock())
sys.path.insert(0, str(ROOT))
from game import config as C  # noqa: E402
from game import hills  # noqa: E402
from game import cave_rocks  # noqa: E402

SPR = ROOT / "assets" / "sprites"
OUT = ROOT / "reports" / "design" / "v06_fundo_m2_biomas"
T = 32
LIFT = C.WALL_LIFT
NAMES = ("plateau", "salar", "basalt", "frost")
PT = {"plateau": "centro", "salar": "salar", "basalt": "basalto", "frost": "gelo"}


def hx(s: str) -> tuple[int, int, int]:
    return tuple(int(s[i:i + 2], 16) for i in (1, 3, 5))


# ---------------------------------------------------------------------------
# 1. Rampas da rocha (10 cores: 0..4 base escura da face -> tom médio do topo, 5/7 brilho, 6 2º tom, 8 contorno)
# ---------------------------------------------------------------------------
RAMPS_HEX = {
    # centro: a de hoje (cave_ramp() do estágio névoa), calculada abaixo
    # salar: arenito claro e quente, a rocha "lavada" de infiltração (livre: macio, sem brilho duro)
    "salar": ["#2c2119", "#3d2f24", "#524031", "#665240", "#775f47", "#a38b66", "#6d5640", "#c9b68d", "#241a13", "#000000"],
    # basalto: cinza-chumbo/preto NEUTRO (como o da superfície; v1.1: tirei o roxo-avermelhado) com BORDA DE BRASA só no contorno
    "basalt": ["#0e0e11", "#151519", "#1c1c21", "#242429", "#2d2c32", "#3c3438", "#232227", "#ff9a52", "#c2481f", "#000000"],
    # gelo: azul-marinho profundo com BORDA DE GELO (rocha dura: miolo azul-escuro, contorno branco-azulado)
    "frost": ["#0f1d36", "#162b50", "#1e3b69", "#285084", "#33629c", "#7fb6e6", "#2a5a96", "#a6e6ff", "#c4eeff", "#000000"],
}


def ramps() -> dict[str, list[list[int]]]:
    out = {"plateau": cave_rocks.cave_ramp().tolist()}
    for k, v in RAMPS_HEX.items():
        out[k] = [list(hx(c)) for c in v]
    return out


# ---------------------------------------------------------------------------
# 2. Chão: 32x32 que emenda (ruído em toro), 4 variações por bioma
# ---------------------------------------------------------------------------
def hsh(*a) -> float:
    h = 2166136261
    for v in a:
        h = ((h ^ (int(v) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    return (h ^ (h >> 16)) / 4294967296.0


def tnoise(seed: int, cell: int, sx: float = 1.0) -> np.ndarray:
    """Ruído de valor 32x32 que emenda nas 4 bordas. `cell`: tamanho da célula em px (divisor de 32);
    sx > 1 estica na horizontal (ondulação de vento / de duna)."""
    n = T // cell
    rng = np.random.default_rng(seed)
    g = rng.random((n, n))
    ys, xs = np.mgrid[0:T, 0:T]
    u, v = xs / cell / sx, ys / cell
    i0, j0 = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i0, v - j0
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    gi = lambda j, i: g[j % n, i % n]  # noqa: E731
    top = gi(j0, i0) * (1 - fu) + gi(j0, i0 + 1) * fu
    bot = gi(j0 + 1, i0) * (1 - fu) + gi(j0 + 1, i0 + 1) * fu
    return top * (1 - fv) + bot * fv


class Tile:
    def __init__(self):
        self.a = np.zeros((T, T, 3), np.uint8)

    def px(self, x, y, c):
        self.a[y % T, x % T] = c

    def rect(self, x, y, w, h, c):
        for j in range(h):
            for i in range(w):
                self.px(x + i, y + j, c)

    def image(self) -> Image.Image:
        im = Image.fromarray(self.a).convert("RGBA")
        return im


def base_fill(t: Tile, cols, seed, lo=0.36, hi=0.66, cell=4):
    n = 0.6 * tnoise(seed, cell) + 0.4 * tnoise(seed + 9, 2)
    c0, c1, c2 = (hx(c) for c in cols)
    t.a[:] = np.where((n < lo)[..., None], c1, np.where((n > hi)[..., None], c2, c0))


def blob_mask(seed: int, cell: int, thr: float, sx: float = 1.0) -> np.ndarray:
    return tnoise(seed, cell, sx) > thr


def edge_of(mask: np.ndarray) -> np.ndarray:
    """Borda de dentro da máscara (toro)."""
    e = np.zeros_like(mask)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        e |= mask & ~np.roll(np.roll(mask, dy, 0), dx, 1)
    return e


def paint(t: Tile, mask: np.ndarray, c):
    t.a[mask] = hx(c) if isinstance(c, str) else c


def pebbles(t: Tile, seed, n, body, hi, dark):
    for i in range(n):
        w = 3 + int(hsh(i, 9, seed) * 3)
        ax, ay = int(hsh(i, 10, seed) * T), int(hsh(i, 11, seed) * T)
        t.rect(ax, ay + 2, w, 1, hx(dark))
        t.rect(ax, ay, w, 2, hx(body))
        t.rect(ax, ay, 2, 1, hx(hi))


# --- salar: areia clara com manchas úmidas (infiltração do lençol freático) e flor de sal ---
SALAR = {"sand": ["#b6a279", "#ab9770", "#c1ad84"], "wet": "#9a8863", "wet_d": "#85734f", "wet_ring": "#a08d68",
         "salt": "#efe7d3", "salt_d": "#cdbf9f", "ripple": "#9c8a64", "peb": "#9d8a68", "peb_hi": "#d3c39f",
         "peb_d": "#6f5e44"}


def make_salar(v: int) -> Tile:
    P, t, s = SALAR, Tile(), 700 + v * 13
    base_fill(t, P["sand"], s, 0.30, 0.70, 4)
    # ondulações de vento (linhas curtas mais claras), mais fortes nas variações 1 e 3
    for i in range(3 + v):
        x, y = int(hsh(i, 1, s) * T), int(hsh(i, 2, s) * T)
        w = 4 + int(hsh(i, 3, s) * 5)
        for k in range(w):
            t.px(x + k, y + (1 if 2 < k < w - 2 else 0), hx(P["ripple"]) if k % 2 == 0 else hx(P["sand"][2]))
    # mancha úmida: miolo escuro, anel de transição mais escuro, "franja" clara por fora; v0 não tem (areia seca)
    if v in (1, 2, 3):
        thr = {1: 0.70, 2: 0.60, 3: 0.66}[v]
        m = blob_mask(s + 5, 8, thr, 1.4 if v == 3 else 1.0)
        ring = edge_of(m)
        halo = np.zeros_like(m)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            halo |= np.roll(np.roll(m, dy, 0), dx, 1)
        halo &= ~m
        paint(t, halo, P["wet_ring"])
        paint(t, m, P["wet"])
        paint(t, ring, P["wet_d"])
        inner = blob_mask(s + 5, 8, thr + 0.12, 1.4 if v == 3 else 1.0) & m
        paint(t, inner & np.array([[hsh(x, y, s + 4) < 0.35 for x in range(T)] for y in range(T)]), P["wet_d"])   # umidade mais funda
    # flor de sal: grãos claros soltos (mais na v2 e v3)
    for i in range(3 + 2 * (v >= 2)):
        x, y = int(hsh(i, 4, s) * T), int(hsh(i, 5, s) * T)
        t.px(x, y, hx(P["salt"]))
        if i % 2 == 0:
            t.px(x + 1, y, hx(P["salt_d"]))
    if v == 3:        # crosta de sal rachada
        x, y = 5, 20
        for i in range(14):
            t.px(x, y, hx(P["salt_d"]))
            x += 1
            r = hsh(i, 8, s)
            y += 1 if r < 0.3 else -1 if r < 0.6 else 0
    if v in (0, 2):
        pebbles(t, s, 1, P["peb"], P["peb_hi"], P["peb_d"])
    return t


# --- basalto: carvão avermelhado, rachaduras escuras, fios de brasa ---
BASALT = {"floor": ["#343439", "#2d2c32", "#403f45"], "patch": "#25252a", "dot": "#1c1c20", "crack": "#141418",
          "ember": "#e2733a", "ember_d": "#a8321c", "ember_hi": "#ffb870", "peb": "#545257", "peb_hi": "#6b696e",
          "ash": "#4a4950"}


def make_basalt(v: int) -> Tile:
    P, t, s = BASALT, Tile(), 800 + v * 17
    base_fill(t, P["floor"], s)
    for i in range(5 + v):
        x, y = int(hsh(i, 1, s) * T), int(hsh(i, 2, s) * T)
        t.rect(x, y, 3 + int(hsh(i, 3, s) * 4), 1 + (i % 2), hx(P["patch"]))
    for i in range(7):
        t.px(int(hsh(i, 4, s) * T), int(hsh(i, 5, s) * T), hx(P["dot"]))
    for i in range(4):                                      # cinza clarinha
        t.px(int(hsh(i, 6, s) * T), int(hsh(i, 7, s) * T), hx(P["ash"]))
    # rachaduras: v1 e v3 têm brasa (v1: fio curto, v3: fio longo com mini-ramificação)
    crack = {0: 0, 1: 12, 2: 8, 3: 18}[v]
    if crack:
        x, y = 2 + int(hsh(0, 6, s) * 8), 6 + int(hsh(0, 7, s) * 18)
        for i in range(crack):
            glow = v in (1, 3) and 2 < i < crack - 2
            t.px(x, y, hx(P["ember"]) if glow and i % 3 != 1 else hx(P["crack"]))
            if glow and i % 3 == 1:
                t.px(x, y, hx(P["ember_d"]))
            if glow and i % 5 == 2:
                t.px(x, y - 1, hx(P["ember_d"]))
                t.px(x, y + 1, hx(P["crack"]))
            elif not glow:
                t.px(x, y + 1, hx(P["dot"]))
            x += 1
            r = hsh(i, 8, s)
            y += 1 if r < 0.3 else -1 if r < 0.6 else 0
        if v == 3:
            t.px(x - 8, y, hx(P["ember_hi"]))
    if v == 2:                                              # poça de brasa miúda (3 px)
        t.rect(20, 22, 3, 1, hx(P["ember_d"]))
        t.px(21, 22, hx(P["ember"]))
        t.px(21, 21, hx(P["ember_d"]))
    pebbles(t, s, 1 + (v % 2), P["peb"], P["peb_hi"], P["dot"])
    return t


# --- gelo: chão azul-acinzentado de gelo velho, placas de geada, rachaduras de gelo ---
FROST = {"floor": ["#6880a6", "#5f7599", "#7b93b8"], "frost": "#7f9bc0", "frost_hi": "#e6f6ff", "crack": "#35466a",
         "crack_hi": "#9ac4e0", "dot": "#4a5f84", "sheet": "#8fb0d6", "sheet_hi": "#d5f0fb", "peb": "#7a93b8"}


def make_frost(v: int) -> Tile:
    P, t, s = FROST, Tile(), 900 + v * 19
    base_fill(t, P["floor"], s)
    for i in range(7):
        t.px(int(hsh(i, 4, s) * T), int(hsh(i, 5, s) * T), hx(P["dot"]))
    # geada: placa clara irregular com pontinhos brancos (v0 pouca, v1 e v3 mais)
    thr = {0: 0.78, 1: 0.66, 2: 0.74, 3: 0.64}[v]
    m = blob_mask(s + 3, 8, thr)
    paint(t, m, P["frost"])
    rnd = np.array([[hsh(x, y, s) < 0.16 for x in range(T)] for y in range(T)])
    paint(t, m & rnd, P["frost_hi"])
    # placa de gelo liso (v2): retângulo brilhante com 2 reflexos em diagonal
    if v == 2:
        sh = blob_mask(s + 8, 8, 0.55)
        paint(t, sh, P["sheet"])
        paint(t, edge_of(sh), P["crack_hi"])
        for k in range(3):
            t.px(6 + k, 10 - k, hx(P["sheet_hi"]))
            t.px(18 + k, 22 - k, hx(P["sheet_hi"]))
    # rachadura de gelo (v1 e v3)
    if v in (1, 3):
        x, y = 3 + int(hsh(0, 6, s) * 8), 8 + int(hsh(0, 7, s) * 14)
        for i in range(14 + v):
            t.px(x, y, hx(P["crack"]))
            if i % 3 == 1:
                t.px(x, y + 1, hx(P["crack_hi"]))
            x += 1
            r = hsh(i, 8, s)
            y += 1 if r < 0.3 else -1 if r < 0.6 else 0
    pebbles(t, s, v % 2, P["peb"], P["frost_hi"], P["dot"])
    return t


FLOORS = {"salar": make_salar, "basalt": make_basalt, "frost": make_frost}
SLUG = {"salar": "salar", "basalt": "basalt", "frost": "frost"}


def floor_images() -> dict[str, list[Image.Image]]:
    out = {}
    for k, fn in FLOORS.items():
        out[k] = [fn(v).image() for v in range(4)]
    out["plateau"] = [Image.open(SPR / f"floor_mist_{v}.png").convert("RGBA") for v in range(4)]
    return out


# ---------------------------------------------------------------------------
# 3. Luz: ambiente (cor que a caverna mostra fora dos focos) e tinta do capacete, por região
# ---------------------------------------------------------------------------
LIGHT = {
    #            ambiente RGB (0..255, o `ambient` do Lighting.apply), cor do capacete, intensidade do capacete
    "plateau": {"ambient": [3, 4, 6], "helmet": [255, 236, 206], "helmet_intensity": 1.0},
    "salar": {"ambient": [16, 13, 7], "helmet": [255, 232, 190], "helmet_intensity": 1.0},
    "basalt": {"ambient": [34, 10, 5], "helmet": [255, 214, 178], "helmet_intensity": 0.95},
    "frost": {"ambient": [8, 17, 32], "helmet": [228, 240, 255], "helmet_intensity": 1.0},
}
BAND = (0.18, 0.40, 0.68, 1.0)


def falloff(d):
    if d >= 1:
        return 0.0
    if d <= 0.3:
        return 1.0
    k = (d - 0.3) / 0.7
    return 1.0 - k * k * (3 - 2 * k)


def light_map(w, h, lights, ambient):
    """Mapa de luz (h, w, 3) float 0..1 como o do jogo: células de 4 px, anéis em degraus, soma e trava em 1."""
    cell = 4
    cw, ch = -(-w // cell), -(-h // cell)
    m = np.zeros((ch, cw, 3), np.float32) + np.array(ambient, np.float32) / 255
    jj, ii = np.mgrid[0:ch, 0:cw]
    for (lx, ly, rad, col, inten) in lights:
        d = np.hypot((ii + 0.5) * cell - lx, (jj + 0.5) * cell - ly) / rad
        b = np.vectorize(falloff)(np.clip(d, 0, 1.5))
        lv = np.where(b > 0, np.array(BAND)[np.minimum(3, (b * 4).astype(int))], 0.0) * inten
        m += lv[..., None] * (np.array(col, np.float32) / 255)
    m = np.clip(m, 0, 1)
    return np.kron(m, np.ones((cell, cell, 1), np.float32))[:h, :w]


# ---------------------------------------------------------------------------
# 4. Cenas
# ---------------------------------------------------------------------------
COPPER = 30                                   # tile fictício só pra cena (o Dev cria o do jogo no M1)
C.ORE_TILES = {**C.ORE_TILES, COPPER: "copper"}
C.WALL_TILES = set(C.WALL_TILES) | {COPPER}
RES_KIND = {"iron": C.IRON, "silicon": C.SILICON, "ice": C.ICE, "copper": COPPER}
ORE_RGBA = {r: np.array(Image.open(SPR / f"ore_{r}.png").convert("RGBA")) for r in ("iron", "silicon", "ice", "copper")}
GLINT = {"iron": (232, 140, 72), "silicon": (120, 150, 230), "ice": (60, 196, 240), "copper": (255, 128, 70)}
# minério de parede por região (peso) e veio 2x2 de chão
WALL_ORE = {"plateau": {"iron": 3, "silicon": 3, "ice": 1}, "salar": {"copper": 4, "silicon": 2},
            "frost": {"ice": 5, "iron": 1}, "basalt": {"iron": 1}}
VEIN2 = {"plateau": "iron", "salar": "copper", "frost": "ice", "basalt": "magmatite"}
ROCK_SMALL = {"basalt": "magmatite", "plateau": "silicon", "salar": "copper", "frost": "ice"}


def smooth_field(w, h, seed, passes=4):
    rng = np.random.default_rng(seed)
    f = rng.random((h, w))
    for _ in range(passes):
        p = np.pad(f, 1, mode="edge")
        f = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + f * 2) / 6
    return (f - f.min()) / (f.max() - f.min())


def make_world(W, H, region_fn, seed, floor_thr=0.52, corridor=None):
    """kinds[H][W] (uint8), regions[H][W], veios, rochinhas. Parede por padrão; cavernas naturais por ruído."""
    f = smooth_field(W, H, seed)
    kinds = np.full((H, W), C.ROCK, np.uint8)
    regions = np.zeros((H, W), np.uint8)
    for j in range(H):
        for i in range(W):
            regions[j, i] = region_fn(i, j)
    kinds[f > floor_thr] = C.FLOOR
    kinds[:2], kinds[-2:], kinds[:, :2], kinds[:, -2:] = C.ROCK, C.ROCK, C.ROCK, C.ROCK
    for (ci, cj, rw, rh) in (corridor or []):          # câmaras garantidas
        for j in range(cj, cj + rh):
            for i in range(ci, ci + rw):
                kinds[j, i] = C.FLOOR
    # apara ilhotas de chão de 1 tile e pontas de parede soltas
    rng = np.random.default_rng(seed + 1)
    for _ in range(2):
        k2 = kinds.copy()
        for j in range(2, H - 2):
            for i in range(2, W - 2):
                n = sum(kinds[j + dj, i + di] == C.FLOOR for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if kinds[j, i] == C.FLOOR and n <= 1:
                    k2[j, i] = C.ROCK
                if kinds[j, i] != C.FLOOR and n >= 3:
                    k2[j, i] = C.FLOOR
        kinds = k2
    # minério: veios de 6 a 8 tiles + alguns soltos (colados no chão pra aparecer)
    def wall_next_to_floor():
        out = []
        for j in range(2, H - 2):
            for i in range(2, W - 2):
                if kinds[j, i] == C.ROCK and any(kinds[j + dj, i + di] == C.FLOOR for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    out.append((i, j))
        return out
    cand = wall_next_to_floor()
    rng.shuffle(cand)
    used = set()
    nveins = 0
    for (i0, j0) in cand:
        if (i0, j0) in used or nveins >= (W * H) // 55:
            continue
        reg = NAMES[regions[j0, i0]]
        choices = WALL_ORE[reg]
        res = rng.choice(list(choices), p=np.array(list(choices.values()), float) / sum(choices.values()))
        size = int(rng.integers(6, 9))
        cluster, frontier = [(i0, j0)], [(i0, j0)]
        while frontier and len(cluster) < size:
            ci, cj = frontier.pop(int(rng.integers(len(frontier))))
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (ci + di, cj + dj)
                if 2 <= n[0] < W - 2 and 2 <= n[1] < H - 2 and kinds[n[1], n[0]] == C.ROCK and n not in cluster \
                        and n not in used and len(cluster) < size and regions[n[1], n[0]] == regions[j0, i0]:
                    cluster.append(n)
                    frontier.append(n)
        if len(cluster) < 5:
            continue
        for (i, j) in cluster:
            kinds[j, i] = RES_KIND[res]
            used.add((i, j))
        nveins += 1
    singles = 0
    for (i, j) in cand:
        if (i, j) in used or singles >= (W * H) // 120 or rng.random() > 0.08 or kinds[j, i] != C.ROCK:
            continue
        reg = NAMES[regions[j, i]]
        choices = WALL_ORE[reg]
        res = rng.choice(list(choices), p=np.array(list(choices.values()), float) / sum(choices.values()))
        kinds[j, i] = RES_KIND[res]
        singles += 1
    # veios 2x2 no chão (um por região presente) e rochinhas
    floor_cells = [(i, j) for j in range(3, H - 3) for i in range(3, W - 3) if kinds[j, i] == C.FLOOR]
    veins, rocks, taken = [], [], set()
    for reg_id, reg in enumerate(NAMES):
        mine = [(i, j) for (i, j) in floor_cells if regions[j, i] == reg_id and all(
            kinds[j + dj, i + di] == C.FLOOR for di in (0, 1) for dj in (0, 1)) and all(
            (i + di, j + dj) not in taken for di in (-1, 0, 1, 2) for dj in (-1, 0, 1, 2))]
        if mine:
            i, j = mine[int(rng.integers(len(mine)))]
            veins.append((i, j, VEIN2[reg]))
            for di in range(-1, 3):
                for dj in range(-1, 3):
                    taken.add((i + di, j + dj))
        mine = [(i, j) for (i, j) in floor_cells if regions[j, i] == reg_id and (i, j) not in taken]
        nroc = 5 if reg == "basalt" else 2
        for _ in range(min(nroc, len(mine))):
            i, j = mine[int(rng.integers(len(mine)))]
            if (i, j) in taken:
                continue
            taken.add((i, j))
            rocks.append((i, j, ROCK_SMALL[reg], int(rng.integers(2))))
    return kinds, regions, veins, rocks


def lut_all(ramp_map):
    lut = np.concatenate([np.array(ramp_map[n], np.uint8) for n in NAMES])
    return np.concatenate([lut, (lut * hills.BEDROCK_SHADE).astype(np.uint8)])


def walls_rgba(kinds, regions, lut):
    """RGBA das paredes (um bloco por vez) -> lista (blk, rgba)."""
    H, W = kinds.shape
    top, face = hills.load_indexed("hill_top.png"), hills.load_indexed("hill_face.png")
    noise = hills.edge_noise()
    luts = {n: lut for n in cave_rocks.STAGES}
    out = []
    for by in range((H + 7) // 8):
        for bx in range((W + 7) // 8):
            i0, i1, j0, j1 = hills.window_bounds(bx, by)
            kw = hills.tile_window(kinds.tolist(), W, H, i0, i1, j0, j1)
            rw = np.zeros(kw.shape, np.uint8)
            for jj in range(j0, j1):
                for ii in range(i0, i1):
                    rw[jj - j0, ii - i0] = regions[min(max(jj, 0), H - 1), min(max(ii, 0), W - 1)]
            blk = hills.bake_block(kw, rw, bx, by, top, face, noise, height=H)
            out.append((blk, hills.colorize_block(blk, luts, cave_rocks.STAGES[0], ORE_RGBA)))
    return out


def hard_marks(kinds, regions):
    return None


def render_scene(kinds, regions, veins, rocks, floors, lut, player=None, lit=None, ambient=None, glints=True,
                 size=(960, 540), cam=(64, 64), seed=3):
    H, W = kinds.shape
    img = Image.new("RGBA", (W * T, H * T + 2 * LIFT + 8), (0, 0, 0, 255))
    for j in range(H):
        for i in range(W):
            reg = NAMES[regions[j, i]]
            v = int(hsh(i, j, seed) * 8)
            v = (0, 0, 0, 0, 1, 1, 2, 3)[v]          # FLOOR_PICK do jogo
            img.alpha_composite(floors[reg][v], (i * T, j * T))
    for (vi, vj, res) in veins:
        img.alpha_composite(Image.open(SPR / f"vein_{res}.png").convert("RGBA"), (vi * T, vj * T))
    blocks = walls_rgba(kinds, regions, lut)
    objs = {}
    for (i, j, res, var) in rocks:
        objs.setdefault(j, []).append((i * T, j * T, Image.open(SPR / f"rock_small_{res}_{var}.png").convert("RGBA")))
    if player:
        px, py = player
        objs.setdefault(int(py // T), []).append((int(px - 16), int(py - 28), Image.open(SPR / "player_down.png").convert("RGBA")))
    for r in range(H):
        for blk, rgba in blocks:
            m = blk["row"] == r
            if not m.any():
                continue
            piece = rgba.copy()
            piece[..., 3] = np.where(m, piece[..., 3], 0)
            ys, xs = np.nonzero(m)
            img.alpha_composite(Image.fromarray(piece[ys.min():ys.max() + 1, xs.min():xs.max() + 1], "RGBA"),
                                (blk["x0"] + int(xs.min()), blk["y0"] + int(ys.min()) + 0))
        for (ox, oy, spr) in objs.get(r, []):
            img.alpha_composite(spr, (ox, oy))
    w, h = size
    cx, cy = cam
    crop = img.crop((cx, cy, cx + w, cy + h)).convert("RGB")
    if lit is None:
        return crop
    arr = np.asarray(crop, np.float32) / 255
    lights = [(lx - cx, ly - cy, rad, col, inten) for (lx, ly, rad, col, inten) in lit]
    lm = light_map(w, h, lights, ambient)
    arr = arr * lm
    out = np.clip(arr * 255, 0, 255).astype(np.uint8)
    if glints:
        for j in range(H):
            for i in range(W):
                res = C.ORE_TILES.get(int(kinds[j, i]))
                if not res:
                    continue
                gx = i * T + 7 + int(hsh(i, j, 5) * 18) - cx
                gy = j * T + 6 + int(hsh(i, j, 6) * 14) - cy
                if 4 <= gx < w - 6 and 4 <= gy < h - 6:
                    dark = 1 - float(lm[gy, gx].max())
                    if dark > 0.2:
                        col = np.array(GLINT[res], np.float32) * (0.7 * dark)
                        out[gy:gy + 2, gx:gx + 2] = np.clip(out[gy:gy + 2, gx:gx + 2].astype(np.float32) + col, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def mix_light(w_by_region):
    """Ambiente e capacete como média ponderada das regiões (o que o Dev faria com a região do player)."""
    amb = sum(np.array(LIGHT[r]["ambient"], float) * w for r, w in w_by_region.items())
    col = sum(np.array(LIGHT[r]["helmet"], float) * w for r, w in w_by_region.items())
    inten = sum(LIGHT[r]["helmet_intensity"] * w for r, w in w_by_region.items())
    return tuple(amb), tuple(int(c) for c in col), inten


def pick_floor(kinds, ci, cj, avoid=()):
    """Tile de chão com 3x3 livre mais perto de (ci, cj)."""
    best, bd = None, 1e9
    for j in range(3, kinds.shape[0] - 3):
        for i in range(3, kinds.shape[1] - 3):
            if all(kinds[j + dj, i + di] == C.FLOOR for di in (-1, 0, 1) for dj in (-1, 0, 1)):
                d = math.hypot(i - ci, j - cj) + sum(8 for a in avoid if math.hypot(i - a[0], j - a[1]) < 3.5)
                if d < bd:
                    best, bd = (i, j), d
    return best


def lamp_light(i, j):
    return (i * T + 16, j * T + 8, 5 * T, (255, 222, 184), 1.0)


def helmet(px, py, col, inten):
    return (px, py - 18 + 10, 4 * T, tuple(col), inten)


# --- definições das cenas (34x21 tiles, câmera em (2,2) tiles) ---
W, H = 34, 21


def noise_line(seed, n, amp):
    f = smooth_field(n, 1, seed, 3)[0]
    return (f - 0.5) * 2 * amp


def scenes(floors, ramp_map):
    lut = lut_all(ramp_map)
    out = {}
    # centro x biome: fronteira vertical torta (salar leste, basalto oeste) ou horizontal (gelo norte)
    bnd = noise_line(11, 40, 3)

    def r_salar(i, j):
        return 1 if i >= 17 + bnd[j] else 0

    def r_basalt(i, j):
        return 2 if i <= 16 + bnd[j] else 0

    def r_frost(i, j):
        return 3 if j <= 10 + bnd[i] * 0.8 else 0

    cfg = {
        "salar": (r_salar, 4, [(4, 8, 7, 6), (24, 8, 6, 6), (13, 11, 14, 2)], {"plateau": 0.5, "salar": 0.5}, (15 * T, 11 * T + 24), (0, 0)),
        "basalt": (r_basalt, 5, [(4, 8, 6, 6), (24, 8, 6, 6), (8, 11, 18, 2)], {"plateau": 0.5, "basalt": 0.5}, (17 * T, 11 * T + 24), (0, 0)),
        "frost": (r_frost, 6, [(8, 14, 6, 4), (22, 5, 6, 5), (16, 8, 2, 10)], {"plateau": 0.5, "frost": 0.5}, (17 * T, 10 * T + 8), (0, 0)),
    }
    for name, (fn, seed, ch, wts, ppos, _) in cfg.items():
        k, r, v, ro = make_world(W, H, fn, seed, 0.64, ch)
        pi, pj = pick_floor(k, ppos[0] // T, ppos[1] // T)
        ppos = (pi * T + 16, pj * T + 20)
        li, lj = pick_floor(k, pi + (4 if name != "frost" else 0), pj + (0 if name != "frost" else 4), [(pi, pj)])
        amb, col, inten = mix_light(wts)
        out[f"fronteira_{name}"] = dict(
            dry=render_scene(k, r, v, ro, floors, lut),
            lit=render_scene(k, r, v, ro, floors, lut, player=ppos, lit=[helmet(ppos[0], ppos[1], col, inten), lamp_light(li, lj)], ambient=amb))
    # os 4 juntos (cruz do mapa de verdade: gelo norte, basalto oeste, salar leste, centro no meio)
    b1, b2, b3 = noise_line(21, 40, 2), noise_line(22, 40, 2), noise_line(23, 40, 2)

    def r_all(i, j):
        if j <= 6 + b1[i]:
            return 3
        if i <= 9 + b2[j]:
            return 2
        if i >= 24 + b3[j]:
            return 1
        return 0

    k, r, v, ro = make_world(W, H, r_all, 8, 0.63, [(14, 11, 6, 5), (4, 11, 4, 4), (27, 11, 4, 4), (14, 4, 5, 3), (10, 12, 5, 2), (22, 12, 5, 2), (16, 7, 2, 5)])
    pi, pj = pick_floor(k, 17, 13)
    ppos = (pi * T + 16, pj * T + 20)
    amb, col, inten = mix_light({"plateau": 1.0})
    out["quatro"] = dict(
        dry=render_scene(k, r, v, ro, floors, lut),
        lit=render_scene(k, r, v, ro, floors, lut, player=ppos, lit=[helmet(ppos[0], ppos[1], col, inten)], ambient=amb))
    # 4 painéis (cada bioma puro, jogador no meio, com a luz da região) em 960x540
    panel = Image.new("RGB", (960, 540))
    for n, name in enumerate(NAMES):
        fn = lambda i, j, name=name: NAMES.index(name)  # noqa: E731
        k, r, v, ro = make_world(W, H, fn, 40 + n, 0.60, [(13, 8, 8, 6)])
        pi, pj = pick_floor(k, 17, 11)
        pp = (pi * T + 16, pj * T + 20)
        amb, col, inten = mix_light({name: 1.0})
        im = render_scene(k, r, v, ro, floors, lut, player=pp, lit=[helmet(pp[0], pp[1], col, inten)], ambient=amb,
                          size=(480, 270), cam=(pp[0] - 240, pp[1] - 135 - 10))
        panel.paste(im, ((n % 2) * 480, (n // 2) * 270))
    out["paineis"] = dict(lit=panel)
    out["paineis_seco"] = dict(lit=None)
    return out


HTML_HEAD = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Hesper · v0.6 Fundo M2: cara dos biomas</title>
<style>
:root{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:16px}
.wrap{max-width:1320px;margin:0 auto;padding-block:32px 80px}
h1{font-size:40px;margin:8px 0}h2{margin:44px 0 8px;border-top:1px solid var(--line);padding-top:24px}h3{margin:20px 0 6px;color:var(--gold)}
.eyebrow{font:12px monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
.note{border-left:3px solid var(--cyan);background:var(--panel);padding:10px 16px;margin:16px 0}
.muted{color:var(--muted)}code{background:#2a201b;padding:1px 5px}
img{image-rendering:pixelated;display:block}
.chk{background-color:#342c28;background-image:linear-gradient(45deg,#423835 25%,transparent 25%,transparent 75%,#423835 75%),linear-gradient(45deg,#423835 25%,transparent 25%,transparent 75%,#423835 75%);background-size:16px 16px;background-position:0 0,8px 8px;display:inline-block}
.row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
figure{margin:0}figcaption{font:12px monospace;color:var(--muted);margin-top:4px}
table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:6px 10px;vertical-align:middle}th{font:12px monospace;color:var(--muted)}
.ramp i{display:inline-block;width:38px;height:26px;border:1px solid #0006;font:9px monospace;color:#fff9;padding:2px}
.scene{width:960px;max-width:100%}
pre{background:#1b1411;border:1px solid var(--line);padding:10px;overflow:auto}
</style></head><body><div class="wrap">"""


def hexs(c):
    return "#%02x%02x%02x" % tuple(c)


def write_report(rm):
    FL = OUT / "floors"
    h = [HTML_HEAD]
    h.append("""<div class="eyebrow">v0.6 · bloco Fundo · Marco 2 · PRA APROVAR</div>
<h1>Cara dos biomas da caverna</h1>
<p class="muted">Nada foi promovido pra <code>assets/sprites/</code> e <code>game/</code> não foi tocado. Tudo sai de
<code>tools/sprites/v06_fundo_m2_biomas.py</code> (determinístico), que só lê <code>assets/sprites/</code> e reaproveita a geometria
da rocha do jogo (<code>game/hills.py</code>) pras cenas, então a parede aqui é a parede do jogo, só com a cor nova.</p>
<div class="note"><b>v1.0 · o que tem aqui.</b> (1) Quatro rampas de cor da rocha, uma por região (<code>ramps.json</code>). (2) Chão novo do
salar, do basalto e do gelo, 4 variações cada (12 PNGs, 32×32, emendam). (3) Luz por região (<code>luz.json</code>). (4) Cenas de fronteira
(centro × cada bioma) e as quatro regiões juntas, claras e no escuro com a luz do capacete.
<br><b>Como a rocha dura lê "não dá":</b> o miolo da parede fica quase preto e o <b>contorno</b> (1 px em volta da silhueta, no topo e na base da face) ganha
uma cor própria de perigo: <b>brasa laranja</b> no basalto, <b>branco-gelo</b> no gelo. A rocha livre (centro e salar) tem contorno escuro como sempre.
Além disso o miolo do gelo é azul-marinho profundo (único azul da caverna) e o do basalto é o preto-roxo mais escuro. No escuro, o contorno é a
primeira coisa que aparece na borda da luz.</div>""")
    h.append("<h2>1 · Rampas da rocha</h2><p>10 cores por região, na ordem do <code>cave_ramp()</code>: 0..4 da base escura da face ao tom médio do topo, "
             "5 e 7 os claros (5 é o pontilhado e a faixa de brilho do topo, 7 o brilho de borda), 6 o segundo tom, 8 o <b>contorno</b>, 9 não usado.</p>")
    h.append("<table><tr><th></th>" + "".join(f"<th>{i}</th>" for i in range(9)) + "</tr>")
    for n in NAMES:
        h.append(f"<tr><th>{PT[n]}</th>" + "".join(
            f"<td style='background:{hexs(c)};width:76px;height:34px;font:10px monospace;color:#fff8;text-align:center'>{hexs(c)[1:]}</td>" for c in rm[n][:9]) + "</tr>")
    h.append("</table>")
    h.append("""<p class="muted">O centro é a rampa de hoje (estágio névoa), sem mudança. Salar: arenito marrom-areia (mais escuro que o chão, que é claro).
Basalto: preto avermelhado, contorno de brasa <code>#c2481f</code>, pontilhado ferrugem <code>#5e2c22</code>. Gelo: azul-marinho, contorno <code>#c4eeff</code>, pontilhado azul <code>#7fb6e6</code>.</p>""")
    h.append("<h2>2 · Chão por região</h2><p>1× e ampliado 4× (sobre xadrez). Sorteio das 4 por hash, como o <code>floor_mist</code> (<code>FLOOR_PICK</code>).</p>")
    for reg, txt in (("plateau", "centro: <code>floor_mist_*</code> de hoje (referência)"),
                     ("salar", "salar: areia clara, ondulações de vento, <b>manchas úmidas de infiltração</b> (miolo escuro, borda mais escura, franja) e flor de sal; a v0 é areia seca. Gancho futuro de tirar areia."),
                     ("basalt", "basalto: carvão avermelhado, rachaduras escuras, fios de brasa laranja (v1 e v3), poça de brasa (v2)"),
                     ("frost", "gelo: azul-acinzentado, placas de geada, placa de gelo liso com reflexo (v2), rachadura de gelo (v1 e v3)")):
        h.append(f"<h3>{PT[reg]}</h3><p class='muted'>{txt}</p><div class='row'>")
        for v in range(4):
            src = f"floors/floor_cave_{reg}_{v}.png" if reg != "plateau" else f"floors/ref_floor_mist_{v}.png"
            h.append(f"<figure><div class='chk'><img src='{src}' width='128' height='128'></div><figcaption>{v} · 1×: "
                     f"<img src='{src}' width='32' height='32' style='display:inline-block;vertical-align:middle'></figcaption></figure>")
        h.append("</div>")
    h.append("<h3>Os quatro chãos lado a lado, como o jogo sorteia</h3><div class='row'><img src='cenas/chaos_campo.png' width='960'></div>")
    h.append("""<h2>3 · Cenas de fronteira</h2>
<p>Montadas só com sprites e a geometria da parede do jogo, na ordem de desenho: chão → veios 2×2 → linha por linha (topo da parede em y−24 + face em y+8 e os objetos da linha) → escuridão.
Dentro de cada região os minérios seguem a spec: centro ferro/silício/gelo, salar cobre/silício, gelo gelo/ferro, basalto ferro, em veios de 6 a 8 tiles. Veio 2×2 de magmatita no basalto, de cobre no salar,
rochinha de magmatita no chão do basalto. O seam reto na parede (cor muda no limite do tile) é do motor: a região é por tile.</p>""")
    for name, title in (("salar", "centro × salar (leste)"), ("basalt", "basalto (oeste) × centro"), ("frost", "gelo (norte) × centro")):
        h.append(f"<h3>{title}</h3><div class='row'><figure><img class='scene' src='cenas/fronteira_{name}_claro.png'><figcaption>sem escuridão (pra ver a cor)</figcaption></figure>"
                 f"<figure><img class='scene' src='cenas/fronteira_{name}_escuro.png'><figcaption>caverna escura: capacete + 1 luminária, ambiente misturado 50/50 das duas regiões</figcaption></figure></div>")
    h.append("<h2>4 · As quatro regiões juntas</h2><p>Gelo ao norte, basalto a oeste, salar a leste, centro no meio (a geografia da spec, bem menor).</p>"
             "<div class='row'><figure><img class='scene' src='cenas/quatro_claro.png'><figcaption>sem escuridão</figcaption></figure>"
             "<figure><img class='scene' src='cenas/quatro_escuro.png'><figcaption>no escuro, player no centro</figcaption></figure></div>")
    h.append("<h3>Cada bioma no escuro, com a luz da própria região</h3><div class='row'><img class='scene' src='cenas/paineis_escuro.png'></div>"
             "<p class='muted'>Em cima: centro e salar. Embaixo: basalto e gelo.</p>")
    h.append("<h2>5 · Luz por região (pro Dev testar)</h2><p><code>ambient</code> é o RGB que o <code>Lighting.apply(..., ambient=(r,g,b))</code> aceita (o que se enxerga fora dos focos; hoje é 0 = breu). "
             "<code>helmet</code> é a cor da lanterna do capacete (<code>WARM_WHITE</code> hoje) e <code>helmet_intensity</code> a intensidade dela.</p><table><tr><th>região</th><th>ambient RGB</th><th>cor do capacete</th><th>intensidade</th></tr>")
    for n in NAMES:
        L = LIGHT[n]
        h.append(f"<tr><td>{PT[n]}</td><td><i style='display:inline-block;width:16px;height:16px;background:{hexs([min(255, c * 6) for c in L['ambient']])}'></i> {tuple(L['ambient'])}</td>"
                 f"<td><i style='display:inline-block;width:16px;height:16px;background:{hexs(L['helmet'])}'></i> {tuple(L['helmet'])}</td><td>{L['helmet_intensity']}</td></tr>")
    h.append("</table><p class='muted'>(o quadradinho do ambiente está clareado ×6 só pra dar pra ver). Sugestão: o ambiente e a cor do capacete são a média ponderada pela região do tile do player, "
             "suavizada no tempo (~0,5 s), pra não estalar ao cruzar a fronteira. Nas cenas de fronteira foi 50/50.</p>")
    h.append("""<h2>6 · Pro Dev integrar</h2>
<ul>
<li><b>Rampas:</b> <code>ramps.json</code> = <code>{"plateau","salar","basalt","frost"}</code> → 10×[r,g,b], mesmo formato do <code>cave_ramp()</code>. O <code>cave_luts()</code> hoje faz <code>concatenate([ramp]*4)</code>;
troque por <code>[ramp(plateau), ramp(salar), ramp(basalt), ramp(frost)]</code> (ordem = <code>geo.REGION_NAMES</code> = 0 centro, 1 salar, 2 basalto, 3 gelo) e passe a região de cada tile em <code>regions</code> do <code>bake_block</code>
(hoje <code>np.zeros</code>). A cena de cá foi montada assim (script <code>walls_rgba</code>), então o resultado é o mesmo. A assinatura/cache do bloco precisa incluir a região dos tiles.</li>
<li><b>Chão:</b> <code>floor_cave_{salar,basalt,frost}_{0..3}.png</code> (32×32, opacos), centro continua <code>floor_mist_*</code>. Mesmo sorteio por hash.</li>
<li><b>Luz:</b> <code>luz.json</code>, valores de partida.</li>
<li><b>Minério:</b> nas cenas o cobre na parede é o <code>ore_copper.png</code> recortado pela silhueta, igual aos outros.</li>
<li><b>Nenhum PNG de parede/face novo:</b> a rampa já pinta tudo (<code>wall_face_mist</code> não é usado na caverna orgânica). Se o dono preferir uma face diferente por região, é pedido novo.</li>
<li><b>Promoção:</b> só depois do ok do dono; aí o gerente copia <code>floors/floor_cave_*.png</code> pra <code>assets/sprites/</code> (e o contrato do §6 ganha 12 nomes).</li>
</ul></div></body></html>""")
    (OUT / "index.html").write_text("\n".join(h))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "floors").mkdir(exist_ok=True)
    (OUT / "cenas").mkdir(exist_ok=True)
    rm = ramps()
    (OUT / "ramps.json").write_text(json.dumps(rm, indent=1))
    (OUT / "luz.json").write_text(json.dumps(LIGHT, indent=1))
    floors = floor_images()
    for reg in ("salar", "basalt", "frost"):
        for v in range(4):
            floors[reg][v].save(OUT / "floors" / f"floor_cave_{reg}_{v}.png")
    sc = scenes(floors, rm)
    for name, d in sc.items():
        if d.get("dry") is not None:
            d["dry"].save(OUT / "cenas" / f"{name}_claro.png")
        if d.get("lit") is not None:
            d["lit"].save(OUT / "cenas" / f"{name}_escuro.png")
    # tira das rampas e tira dos chãos (pro report)
    sw = Image.new("RGB", (10 * 24, 4 * 24), (0, 0, 0))
    for r, n in enumerate(NAMES):
        for c in range(10):
            sw.paste(tuple(rm[n][c]), (c * 24, r * 24, c * 24 + 24, r * 24 + 24))
    sw.save(OUT / "cenas" / "rampas.png")
    # referência do centro + campo de chão sorteado
    for v in range(4):
        floors["plateau"][v].save(OUT / "floors" / f"ref_floor_mist_{v}.png")
    campo = Image.new("RGB", (960, 4 * 2 * T))
    for k, reg in enumerate(NAMES):
        x0 = (k % 2) * 480
        y0 = (k // 2) * 4 * T
        for j in range(4):
            for i in range(15):
                v = (0, 0, 0, 0, 1, 1, 2, 3)[int(hsh(i, j, 3 + k) * 8)]
                campo.paste(floors[reg][v].convert("RGB"), (x0 + i * T, y0 + j * T))
    campo.save(OUT / "cenas" / "chaos_campo.png")
    write_report(rm)
    print("ok", OUT)


if __name__ == "__main__":
    main()
