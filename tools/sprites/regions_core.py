"""Núcleo da proposta de REGIÕES da superfície (v0.4 Marco 2 · Geografia nova): paletas, ruído, texturas de chão,
decorações, morros, formações e o gerador de exemplo do mapa 192×192.

Usado por tools/sprites/regions_mockups.py (que monta os mockups, os pendentes e o report). PIL + numpy do sistema,
determinístico (nada de random sem seed: tudo sai de hash fixo ou de np.random.default_rng(seed)).

CONVENÇÃO DOS SPRITES INDEXADOS
    Tudo que muda de cor com o estágio é desenhado em ÍNDICE (uint8), não em RGB:
        0..7  rampa da região (0 = fenda mais escura ... 5 = brilho, 6 e 7 = acentos da região)
        8     contorno #1b1630 (fixo, não muda com o estágio)
        9     sombra no chão (preto com alfa fixo SHADOW_A)
        255   transparente
    A cor final = rampa[região][estágio][índice]. A rampa de cada estágio sai da rampa base (Árido) por uma
    transformação fixa (stage_color). Assim são 4 rampas de 8 cores por região, e não 12 conjuntos desenhados à mão.
"""

from __future__ import annotations

import colorsys
import math

import numpy as np
from PIL import Image

T = 32
OUTLINE = (0x1B, 0x16, 0x30)
SHADOW_A = 80                     # alfa fixo da sombra no chão
TEX = 512                         # textura de chão "grande": 16×16 tiles, emenda nos 4 lados
STAGES = ("storm", "arid", "mist", "green")
STAGE_NAME = {"storm": "Tempestade", "arid": "Árido", "mist": "Névoa", "green": "Verde"}


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hexc(c) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in c[:3])


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------------------------------------------------------
# PALETAS · rampa base (estágio Árido). 0 fenda, 1 sombra, 2 escuro, 3 base, 4 claro, 5 brilho, 6 acento, 7 acento 2
# ---------------------------------------------------------------------------------------------------------------
BASE = {
    # planalto rachado: terra/rocha seca ocre-ferrugem (sai do vermelho de hoje e vai pro ocre da referência)
    "plateau": ["#3a231d", "#5c3727", "#80503a", "#8a573a", "#93603f", "#b48258", "#857469", "#56322a"],
    # salar: crosta de sal creme, um tico rosada (da mesma família do planeta, não branco de neve)
    "salar":   ["#6e5c54", "#978679", "#b2a392", "#c6b8a4", "#d8ccba", "#ebe3d4", "#b48d84", "#fbf7ee"],
    # basalto: escuro, frio, com ferrugem de óxido (gancho do vulcão no acento 7)
    "basalt":  ["#17141b", "#231f28", "#2f2a33", "#3a343e", "#4b444f", "#685e68", "#5a3a30", "#7a4632"],
    # faixa gelada: chão com geada por cima da rocha
    "frost":   ["#33425a", "#536880", "#7f95aa", "#90a6b9", "#a4bacb", "#cfe0ea", "#62bede", "#c6f3ff"],
    # leito seco (fundo das depressões do planalto: silte fino com rachadura de lama)
    "bed":     ["#4a2d24", "#6a4433", "#835a42", "#96694d", "#aa7c5c", "#c39874", "#857469", "#5a372c"],
}
# rocha dos morros (topo e face): mais pedra que o chão, pra ler como "parede"
HILL = {
    "plateau": ["#22161a", "#38242a", "#4d322f", "#62403a", "#7a5244", "#946a55", "#8a5a3c", "#a26c48"],
    "basalt":  ["#100e14", "#1a1720", "#24202b", "#2e2a36", "#3c3745", "#565060", "#5a3a30", "#7a4632"],
    "frost":   ["#28303f", "#3a4456", "#4c586c", "#5e6b80", "#8aa2b8", "#d6e6ef", "#62bede", "#c6f3ff"],
    "salar":   ["#5b4a45", "#7a685f", "#978679", "#b2a392", "#d8ccba", "#f2ece0", "#b48d84", "#fbf7ee"],
}
# arenito dos marcos do planalto (monolito, arco): mais quente e claro que o morro, pra ler como "marco"
SAND = ["#2a1714", "#4a2a22", "#6b3d2e", "#8a5238", "#a86c48", "#c98f62", "#857469", "#56322a"]
# gelo (gelos-portão e gelo da cratera)
ICE = ["#1f3d5c", "#2d5e86", "#3f86b0", "#62b2d6", "#8fd6ee", "#c4f0fb", "#eefcff", "#55636e"]

DUST = rgb("#b08a62")
GREEN_TARGET = {"plateau": ("#4c5e2c", .30), "basalt": ("#34452c", .16), "salar": ("#788a66", .10),
                "frost": ("#4a5e4c", .42), "bed": ("#4c5e2c", .22)}


def stage_color(c, region: str, stage: str):
    """A variação de cor do estágio: uma conta fixa em cima da rampa base."""
    c = tuple(c)
    if stage == "arid":
        return c
    if stage == "storm":                       # poeira assentada: puxa pro ocre e achata o contraste
        c = mix(c, DUST, 0.30)
        return mix(c, (150, 118, 88), 0.12)
    if stage == "mist":                        # úmido e frio: menos saturação, mais escuro, um véu cinza-azulado
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
        s *= 0.55
        l *= 0.84
        c = tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l, s))
        if region == "frost":                   # a geada começa a sumir: rocha molhada aparece
            c = mix(c, rgb("#56606c"), 0.28)
        return mix(c, rgb("#4f5a66"), 0.14)
    if stage == "green":                       # terra com matéria orgânica (a grama vem por cima, à parte)
        tgt, amt = GREEN_TARGET.get(region, ("#4c5e2c", .25))
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
        l *= 0.90
        c = tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l, s * 0.8))
        return mix(c, rgb(tgt), amt)
    raise KeyError(stage)


def ramp(region: str, stage: str, table=None) -> np.ndarray:
    """10×3 uint8: rampa do estágio (0..7), contorno (8) e sombra (9, preto)."""
    table = table or BASE
    cols = [stage_color(rgb(h), region, stage) for h in table[region]]
    return np.array(cols + [OUTLINE, (0, 0, 0)], dtype=np.uint8)


def colorize(idx: np.ndarray, rmp: np.ndarray) -> Image.Image:
    """Índice -> RGBA (255 transparente, 9 = sombra com alfa fixo)."""
    h, w = idx.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    solid = idx != 255
    safe = np.where(solid, idx, 0)
    out[..., :3] = rmp[safe]
    out[..., 3] = np.where(solid, 255, 0)
    out[..., 3][idx == 9] = SHADOW_A
    return Image.fromarray(out)


# ---------------------------------------------------------------------------------------------------------------
# RUÍDO (determinístico, vetorizado)
# ---------------------------------------------------------------------------------------------------------------
M32 = np.uint64(0xFFFFFFFF)


def hash2(x, y, s: int) -> np.ndarray:
    """Hash inteiro -> [0, 1). Aceita arrays."""
    with np.errstate(over="ignore"):
        return _hash2(x, y, s)


def _hash2(x, y, s: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.int64).astype(np.uint64)
    y = np.asarray(y, dtype=np.int64).astype(np.uint64)
    n = (x * np.uint64(374761393) + y * np.uint64(668265263) + np.uint64(s) * np.uint64(2246822519)
         + np.uint64(0x9E3779B9)) & M32
    n = ((n ^ (n >> np.uint64(13))) * np.uint64(1274126177)) & M32
    n = n ^ (n >> np.uint64(16))
    n = (n * np.uint64(2246822519)) & M32
    n = n ^ (n >> np.uint64(15))
    return n.astype(np.float64) / 4294967296.0


def _smooth(t):
    return t * t * (3 - 2 * t)


def vnoise(xs, ys, cell: float, seed: int, period: int | None = None) -> np.ndarray:
    """Value noise em coordenadas (px ou tiles). `period` (em células) faz emendar."""
    fx, fy = np.asarray(xs, float) / cell, np.asarray(ys, float) / cell
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = _smooth(fx - ix), _smooth(fy - iy)

    def L(a, b):
        if period:
            a, b = a % period, b % period
        return hash2(a, b, seed)

    a, b, c, d = L(ix, iy), L(ix + 1, iy), L(ix, iy + 1), L(ix + 1, iy + 1)
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty


def fbm(xs, ys, cell, seed, octaves=3, period=None):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        p = period * (2 ** o) if period else None
        tot = tot + amp * vnoise(xs, ys, cell / (2 ** o), seed + 101 * o, p)
        norm += amp
        amp *= 0.5
    return tot / norm


def organic(xs, ys, p: int, cells: int, seed: int, warp=None) -> np.ndarray:
    """Ruído "orgânico" que emenda em p px: fbm de 3 oitavas com o domínio torcido por outro ruído (tira a cara
    quadrada do value noise quando a gente corta por limiar)."""
    warp = warp if warp is not None else p / cells * 0.9
    wx = (xs + warp * (fbm(xs, ys, p / (cells * 2), seed + 31, 2, cells * 2) - 0.5)) % p
    wy = (ys + warp * (fbm(xs, ys, p / (cells * 2), seed + 37, 2, cells * 2) - 0.5)) % p
    return fbm(wx, wy, p / cells, seed, 3, cells)


def grid(w, h, ox=0, oy=0):
    ys, xs = np.mgrid[oy:oy + h, ox:ox + w]
    return xs, ys


def voronoi(xs, ys, cell: float, seed: int, period: int | None = None, jitter=0.85):
    """(d1, d2 - d1, id) do Voronoi (sítios 1 por célula). Com `period` (células), emenda."""
    fx, fy = np.asarray(xs, float) / cell, np.asarray(ys, float) / cell
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    d1 = np.full(fx.shape, 9e9)
    d2 = np.full(fx.shape, 9e9)
    best = np.zeros(fx.shape, dtype=np.int64)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = ix + ox, iy + oy
            kx, ky = (cx % period, cy % period) if period else (cx, cy)
            sx = cx + 0.5 + (hash2(kx, ky, seed) - 0.5) * jitter
            sy = cy + 0.5 + (hash2(kx, ky, seed + 7) - 0.5) * jitter
            d = np.hypot(fx - sx, fy - sy) * cell
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            best = np.where(closer, kx * 7919 + ky, best)
            d1 = np.where(closer, d, d1)
    return d1, d2 - d1, best


# ---------------------------------------------------------------------------------------------------------------
# TEXTURAS DE CHÃO 512×512 (emendam; o tile (tx, ty) usa o recorte ((tx % 16)·32, (ty % 16)·32))
# ---------------------------------------------------------------------------------------------------------------
def _pebbles(idx, seed, density, top=5, body=4, low=1, step=5):
    """Pedrisco de 2×2 numa grade frouxa (1 por célula `step`, com chance)."""
    n = idx.shape[0]
    for gy in range(0, n, step):
        for gx in range(0, n, step):
            if hash2(gx, gy, seed) < density:
                x = (gx + int(hash2(gx, gy, seed + 1) * (step - 2))) % n
                y = (gy + int(hash2(gx, gy, seed + 2) * (step - 2))) % n
                idx[y, x] = top
                idx[y, (x + 1) % n] = body
                idx[(y + 1) % n, x] = low
                idx[(y + 1) % n, (x + 1) % n] = low
    return idx


def tex_plateau(seed=11) -> np.ndarray:
    xs, ys = grid(TEX, TEX)
    p = TEX
    n = organic(xs, ys, p, 4, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n < np.quantile(n, 0.18)] = 2
    idx[n > np.quantile(n, 0.88)] = 4
    sp = hash2(xs, ys, seed + 3)
    idx[(sp < 0.025) & (idx == 3)] = 2
    idx[(sp > 0.985) & (idx == 3)] = 4
    # rachaduras: Voronoi com o domínio torcido, só onde a máscara deixa (rede quebrada, não favo)
    wx = xs + 6 * (vnoise(xs, ys, p / 16, seed + 4, 16) - 0.5)
    wy = ys + 6 * (vnoise(xs, ys, p / 16, seed + 5, 16) - 0.5)
    _, edge, _ = voronoi(wx % p, wy % p, p / 6, seed + 6, 6)
    keep = vnoise(xs, ys, p / 8, seed + 7, 8) > 0.74
    crack = (edge < 1.0) & keep
    idx[crack] = 0
    lip = np.roll(crack, 1, axis=0) & ~crack
    idx[lip] = 5
    idx = _pebbles(idx, seed + 8, 0.035, step=6)
    return idx


def tex_salar(seed=21) -> np.ndarray:
    xs, ys = grid(TEX, TEX)
    p = TEX
    n = organic(xs, ys, p, 6, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n > np.quantile(n, 0.70)] = 4
    idx[n < np.quantile(n, 0.10)] = 2
    wx = xs + 4 * (vnoise(xs, ys, p / 32, seed + 1, 32) - 0.5)
    wy = ys + 4 * (vnoise(xs, ys, p / 32, seed + 2, 32) - 0.5)
    _, e2, _ = voronoi(wx % p, wy % p, p / 24, seed + 9, 24)          # rede fina, fraquinha
    idx[(e2 < 0.6) & (hash2(xs // 6, ys // 6, seed + 4) < 0.55)] = 2
    _, edge, _ = voronoi(wx % p, wy % p, p / 10, seed + 3, 10)        # polígonos grandes (~50 px)
    ridge = edge < 1.4 + 1.6 * vnoise(xs, ys, p / 32, seed + 8, 32)
    idx[ridge] = 5
    shade = np.roll(ridge, -1, axis=0) & ~ridge                      # sombra embaixo da crista
    shade |= np.roll(ridge, -2, axis=0) & ~ridge & (edge < 4)
    idx[np.roll(ridge, 1, axis=0) & ~ridge] = 2
    idx[np.roll(ridge, 2, axis=0) & ~ridge & ~np.roll(ridge, 1, axis=0)] = 2
    mid = (edge < 0.7) & (vnoise(xs, ys, p / 16, seed + 5, 16) > 0.45)  # fenda no meio de algumas cristas
    idx[mid] = 1
    sp = hash2(xs, ys, seed + 6)
    idx[(sp < 0.012) & (idx == 3)] = 5
    idx[(sp > 0.994) & (idx == 3)] = 7
    return idx


def tex_basalt(seed=31) -> np.ndarray:
    xs, ys = grid(TEX, TEX)
    p = TEX
    n = organic(xs, ys, p, 6, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n < np.quantile(n, 0.24)] = 2
    idx[n < np.quantile(n, 0.03)] = 1
    idx[n > np.quantile(n, 0.90)] = 4
    _, edge, cid = voronoi(xs, ys, p / 9, seed + 2, 9, jitter=0.95)   # fraturas retas e angulosas
    crack = (edge < 1.0) & (hash2(cid, 0, seed + 3) < 0.5) & (vnoise(xs, ys, p / 8, seed + 10, 8) > 0.35)
    idx[crack] = 0
    idx[np.roll(crack, 1, axis=0) & ~crack & (hash2(xs // 3, ys, seed + 4) < 0.6)] = 5
    sp = hash2(xs, ys, seed + 5)
    idx[(sp < 0.03) & (idx >= 2)] = 1
    idx[(sp > 0.975) & (idx >= 2)] = 4
    rust = organic(xs, ys, p, 10, seed + 6)
    idx[(rust > np.quantile(rust, 0.965)) & (idx >= 2) & (hash2(xs // 2, ys // 2, seed + 9) < 0.6)] = 6
    idx = _pebbles(idx, seed + 8, 0.07, top=4, body=3, low=0)
    return idx


def tex_frost(seed=41) -> np.ndarray:
    xs, ys = grid(TEX, TEX)
    p = TEX
    n = organic(xs, ys, p, 5, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n < np.quantile(n, 0.14)] = 2
    idx[n > np.quantile(n, 0.72)] = 4
    idx[n > np.quantile(n, 0.95)] = 5
    _, edge, cid = voronoi(xs, ys, p / 12, seed + 2, 12)
    crack = (edge < 0.9) & (hash2(cid, 0, seed + 3) < 0.4) & (vnoise(xs, ys, p / 8, seed + 6, 8) > 0.4)
    idx[crack] = 1
    sp = hash2(xs, ys, seed + 4)
    idx[(sp < 0.004)] = 7
    idx[(sp > 0.99) & (idx <= 3)] = 2
    idx = _pebbles(idx, seed + 5, 0.04, top=5, body=2, low=1, step=7)
    return idx


def tex_bed(seed=51) -> np.ndarray:
    """Leito seco das depressões do planalto: silte liso e claro, rachadura de lama (polígonos pequenos com a
    borda levantada)."""
    xs, ys = grid(TEX, TEX)
    p = TEX
    n = organic(xs, ys, p, 6, seed)
    idx = np.full((p, p), 3, np.uint8)
    idx[n > np.quantile(n, 0.75)] = 4
    idx[n < np.quantile(n, 0.15)] = 2
    wx = xs + 3 * (vnoise(xs, ys, p / 32, seed + 1, 32) - 0.5)
    wy = ys + 3 * (vnoise(xs, ys, p / 32, seed + 2, 32) - 0.5)
    _, edge, _ = voronoi(wx % p, wy % p, p / 14, seed + 3, 14)        # placas de lama de ~36 px
    crack = edge < 1.0
    idx[crack] = 1
    idx[np.roll(crack, 1, axis=0) & ~crack & (hash2(xs // 4, ys, seed + 4) < 0.6)] = 4   # borda da placa enrolando
    idx[np.roll(crack, -1, axis=0) & ~crack] = 2
    return idx


TEXTURES = {"plateau": tex_plateau, "salar": tex_salar, "basalt": tex_basalt, "frost": tex_frost, "bed": tex_bed}


# ---------------------------------------------------------------------------------------------------------------
# GERADOR DE EXEMPLO (só pra proposta: o Dev reescreve no game/surface_gen.py com a seed do mundo)
# ---------------------------------------------------------------------------------------------------------------
W = H = 192
BASE_T = (96, 96)                      # tile logo abaixo da cápsula
CRATER_T = (110, 99)                   # canto de cima-esquerda da cratera 3×3
REG = {"plateau": 0, "salar": 1, "basalt": 2, "frost": 3}
REG_NAMES = ["plateau", "salar", "basalt", "frost"]
SALAR_C, SALAR_R = (154, 112), (31, 25)
BASINS = [((78, 114), 6.0), ((124, 70), 6.0), ((100, 142), 8.5)]   # depressões pequenas do planalto
# níveis d'água (altura): L1 = começo da Névoa, L2 = Névoa alta, L3 = Verde cheio
LEVELS = (0.19, 0.29, 0.385)


def gen_world(seed=7):
    xs, ys = grid(W, H)
    n = fbm(xs, ys, 26, seed, 3)
    h = 0.62 + 0.20 * (n - 0.5)
    # salar: a maior bacia (elipse com a borda torcida)
    ex = (xs - SALAR_C[0]) / SALAR_R[0]
    ey = (ys - SALAR_C[1]) / SALAR_R[1]
    de = np.hypot(ex, ey) + 0.22 * (fbm(xs, ys, 10, seed + 1, 2) - 0.5)
    bowl = np.clip(1.15 - de, 0, None)
    h -= 0.62 * np.clip(bowl / 1.15, 0, 1) ** 0.55
    salar = de < 1.0
    # bacias pequenas no planalto
    basin = np.zeros((H, W), bool)
    for (cx, cy), r in BASINS:
        d = np.hypot(xs - cx, (ys - cy) * 1.25) / r + 0.35 * (fbm(xs, ys, 4, seed + 2 + cx, 2) - 0.5)
        h -= 0.50 * np.clip(1 - d, 0, 1) ** 0.6
        basin |= d < 1.0
    region = np.zeros((H, W), np.uint8)
    nb = fbm(xs, ys, 14, seed + 3, 2)
    nb2 = fbm(xs, ys, 5, seed + 5, 2)
    basalt = ((xs < 44 + 40 * (nb - 0.5) + 12 * (nb2 - 0.5) + np.clip(ys - 120, 0, None) * 0.55)
              & (ys > 44 + 16 * (nb - 0.5)))
    region[basalt] = REG["basalt"]
    h[basalt] += 0.07
    frost = ys < 24 + 12 * (fbm(xs, ys, 12, seed + 4, 2) - 0.5)
    region[frost] = REG["frost"]
    h[frost] += 0.05
    region[salar & ~frost] = REG["salar"]
    basin &= region == REG["plateau"]
    return dict(h=h, region=region, basin=basin)


def blob(cx, cy, rx, ry, seed, lobes=2):
    """Máscara (192×192) de um morro: elipse + lóbulos, borda tremida, sem ponta nem dente de 1 tile."""
    xs, ys = grid(W, H)
    rng = np.random.default_rng(seed)
    m = (np.hypot((xs - cx) / rx, (ys - cy) / ry) + 0.35 * (fbm(xs, ys, 2.5, seed, 2) - 0.5)) < 1
    for _ in range(lobes):
        a = rng.uniform(0, 2 * math.pi)
        lx, ly = cx + math.cos(a) * rx * 0.8, cy + math.sin(a) * ry * 0.8
        lr = rng.uniform(0.45, 0.7)
        m |= (np.hypot((xs - lx) / (rx * lr), (ys - ly) / (ry * lr)) + 0.3 * (fbm(xs, ys, 2, seed + 9, 2) - 0.5)) < 1
    return smooth(m)


def smooth(m, it=2):
    for _ in range(it):
        p = np.pad(m, 1).astype(int)
        nb = sum(p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W] for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                 if dx or dy)
        m = (m & (nb >= 3)) | (~m & (nb >= 6))
    # sem tile encostando só pela quina e sem coluna/linha de 1 tile
    p = np.pad(m, 1)
    up, dn, lf, rt = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
    m &= (up | dn) & (lf | rt)
    return m


# ---------------------------------------------------------------------------------------------------------------
# DECALQUES (decoração de chão: não colide, não minera). Índice da rampa da região -> recolore com o estágio.
# ---------------------------------------------------------------------------------------------------------------
from PIL import ImageDraw  # noqa: E402


def _canvas(w, h):
    return Image.new("L", (w, h), 255)


def _arr(im):
    a = np.array(im, dtype=np.uint8)
    ys, xs = np.nonzero(a != 255)
    if len(xs) == 0:
        return a
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def d_patch(seed, w, h, tone="dark"):
    """Mancha grande que atravessa vários tiles: esticada no sentido do vento, borda quebrada, com buracos e
    um segundo tom só em pedaços (não concêntrico)."""
    xs, ys = grid(w, h)
    ex = (xs - w / 2) / (w / 2)
    ey = (ys - h / 2) / (h / 2)
    env = 1 - (ex * ex + ey * ey)
    n = fbm(xs + seed * 97, ys + seed * 53, min(w, h) / 2.6, seed, 3)
    n2 = fbm(xs + seed * 31, ys + seed * 17, min(w, h) / 5, seed + 5, 2)
    f = 0.85 * env + 1.1 * (n - 0.5)
    a = np.full((h, w), 255, np.uint8)
    lo, mid, spk = {"dark": (2, 1, 1), "light": (4, 5, 5), "accent": (6, 7, 1), "bed": (2, 1, 0)}[tone]
    m = (f > 0.22) & ~((n2 < 0.30) & (env < 0.75))
    a[m] = lo
    a[m & (f > 0.50) & (n2 > 0.58)] = mid
    sp = hash2(xs, ys, seed + 3)
    a[m & (sp < 0.035)] = spk
    if tone == "accent":
        a[a == 7] = 6                                   # mancha de óxido: pintada, não chapada
        a[m & (hash2(xs // 2, ys // 2, seed + 4) < 0.35)] = 255
    return a


def d_crack(seed, length):
    """Rachadura longa: caminho com deriva de ângulo, abre 2 px no meio, galhos curtos. Lábio claro embaixo."""
    rng = np.random.default_rng(seed)
    size = length + 120
    im = _canvas(size, size)
    px = im.load()
    pts = []
    x, y = 60.0, size / 2
    ang = rng.uniform(-0.5, 0.5)
    for i in range(length):
        ang += rng.normal(0, 0.07)
        ang = max(-0.55, min(0.55, ang * 0.985))
        x += math.cos(ang)
        y += math.sin(ang)
        pts.append((int(x), int(y), i))
    branches = []
    for _ in range(rng.integers(2, 5)):
        k = int(rng.uniform(0.15, 0.85) * len(pts))
        bx, by, _ = pts[k]
        ba = ang + rng.choice([-1, 1]) * rng.uniform(0.6, 1.3)
        bl = int(rng.uniform(14, 48))
        bx, by = float(bx), float(by)
        for j in range(bl):
            ba += rng.normal(0, 0.12)
            bx += math.cos(ba)
            by += math.sin(ba)
            branches.append((int(bx), int(by), j, bl))
    mid0, mid1 = int(length * 0.3), int(length * 0.7)
    ok = lambda cx, cy: 0 <= cx < size and 0 <= cy < size - 2  # noqa: E731
    for (cx, cy, i) in pts:
        if ok(cx, cy):
            px[cx, cy] = 0
            if mid0 < i < mid1 and (i % 7) < 5:
                px[cx, cy + 1] = 0
    for (cx, cy, j, bl) in branches:
        if ok(cx, cy) and (j < bl - 2 or j % 2 == 0):
            px[cx, cy] = 0
    a = np.array(im)
    crack = a == 0
    lip = np.roll(crack, 1, axis=0) & ~crack
    a[lip] = 5
    edge = (np.roll(crack, -1, axis=0) & ~crack & ~lip)
    a[edge] = 2
    return _arr(Image.fromarray(a))


def _poly(rng, cx, cy, r, n=None):
    n = n or int(rng.integers(5, 8))
    angs = np.sort(rng.uniform(0, 2 * math.pi, n))
    return [(cx + math.cos(a) * r * rng.uniform(0.7, 1.0), cy + math.sin(a) * r * 0.62 * rng.uniform(0.7, 1.0))
            for a in angs]


def d_plates(seed):
    """Placas achatadas e angulosas (lajes soltas): face clara, borda de cima brilhando, degrau escuro embaixo."""
    rng = np.random.default_rng(seed)
    w, h = 120, 72
    im = _canvas(w, h)
    dr = ImageDraw.Draw(im)
    n = int(rng.integers(3, 6))
    cx0, cy0 = w / 2, h / 2
    for k in range(n):
        cx = cx0 + rng.uniform(-34, 34)
        cy = cy0 + rng.uniform(-14, 14)
        r = rng.uniform(13, 24)
        poly = _poly(rng, cx, cy, r)
        dr.polygon([(x, y + 2) for x, y in poly], fill=1)        # degrau (sombra da laje levantada)
        dr.polygon(poly, fill=4)
        dr.line(poly + [poly[0]], fill=2)
        top = [p for p in poly if p[1] < cy]
        if len(top) >= 2:
            dr.line(sorted(top), fill=5)
        if rng.uniform() < 0.6:                                  # rachadura dentro da laje
            dr.line([(cx - r * 0.5, cy + rng.uniform(-3, 3)), (cx + r * 0.3, cy + rng.uniform(-3, 3))], fill=2)
    return _arr(im)


def d_gravel(seed, w=56, h=36, n=None, palette=(5, 4, 2, 1), accent=6):
    """Cascalho: pedrinhas de 2 a 5 px com topo claro e sombrinha."""
    rng = np.random.default_rng(seed)
    im = _canvas(w, h)
    px = im.load()
    top, body, low, sh = palette
    for _ in range(n or int(rng.integers(7, 15))):
        pw = int(rng.integers(2, 6))
        ph = max(2, pw - int(rng.integers(0, 2)))
        x0 = int(rng.uniform(1, w - pw - 2))
        y0 = int(rng.uniform(1, h - ph - 2))
        b = accent if rng.uniform() < 0.25 else body
        for yy in range(ph):
            for xx in range(pw):
                if pw >= 4 and (xx in (0, pw - 1)) and (yy in (0, ph - 1)):
                    continue
                c = top if yy == 0 else (low if yy == ph - 1 else b)
                px[x0 + xx, y0 + yy] = c
        for xx in range(1 if pw >= 4 else 0, pw - (1 if pw >= 4 else 0)):
            if px[x0 + xx + 1, y0 + ph] == 255:
                px[x0 + xx + 1, y0 + ph] = sh
    return _arr(im)


def d_wind(seed, length=150, lines=None, light=4, dark=2):
    """Sulcos de vento: linhas paralelas, longas e onduladas, no sentido do vento dominante (leste, 8° descendo)."""
    rng = np.random.default_rng(seed)
    n = lines or int(rng.integers(3, 6))
    h = 16 + n * 7
    im = _canvas(length + 10, h + 30)
    px = im.load()
    for k in range(n):
        y0 = 6 + k * rng.uniform(5, 8)
        L = int(length * rng.uniform(0.45, 1.0))
        x0 = int(rng.uniform(0, length - L))
        ph = rng.uniform(0, 6.28)
        for i in range(L):
            x = x0 + i
            y = int(y0 + i * 0.14 + 1.6 * math.sin(ph + i / 23))
            if hash2(x, k, seed) < 0.12 or (i < 6 or i > L - 6) and i % 2:
                continue
            px[x, y] = dark
            if px[x, y + 1] == 255:
                px[x, y + 1] = light
    return _arr(im)


def d_ridges(seed, w=72, h=40):
    """Salar: cristinhas de sal empurradas (linhas curtas e quebradas de brilho com sombra)."""
    rng = np.random.default_rng(seed)
    im = _canvas(w, h)
    px = im.load()
    for _ in range(int(rng.integers(4, 8))):
        x, y = rng.uniform(4, w - 20), rng.uniform(4, h - 6)
        a = rng.uniform(-0.6, 0.6)
        for i in range(int(rng.uniform(8, 22))):
            xx, yy = int(x + math.cos(a) * i), int(y + math.sin(a) * i)
            if 0 <= xx < w and 0 <= yy < h - 2:
                px[xx, yy] = 5
                px[xx, yy + 1] = 7 if i % 5 == 2 else 5
                if px[xx, yy + 2] == 255:
                    px[xx, yy + 2] = 1
    return _arr(im)


def d_icesheet(seed, w=120, h=70):
    """Faixa gelada: lâmina de gelo lisa (claro chapado, borda escura, reflexos diagonais)."""
    a = d_patch(seed, w, h, "light")
    m = a != 255
    a[m] = 5
    xs, ys = grid(w, h)
    inner = m & np.roll(m, 2, 0) & np.roll(m, -2, 0) & np.roll(m, 2, 1) & np.roll(m, -2, 1)
    a[m & ~inner] = 4
    glint = inner & (((xs + ys) % 23) < 2) & (hash2(xs // 9, ys // 9, seed) < 0.6)
    a[glint] = 7
    a[inner & (((xs + ys) % 23) == 5) & (hash2(xs // 9, ys // 9, seed) < 0.6)] = 6
    return a


def decal_set():
    """Todos os decalques, por nome: {nome: índice}."""
    out = {}
    for v in range(3):
        out[f"patch_dark_{v}"] = d_patch(200 + v, (224, 176, 144)[v], (96, 80, 64)[v], "dark")
        out[f"patch_light_{v}"] = d_patch(210 + v, (192, 150, 120)[v], (80, 64, 56)[v], "light")
        out[f"crack_{v}"] = d_crack(220 + v, (220, 170, 130)[v])
        out[f"plates_{v}"] = d_plates(230 + v)
        out[f"wind_{v}"] = d_wind(250 + v, (180, 140, 110)[v])
        out[f"ridges_{v}"] = d_ridges(260 + v)
        out[f"stain_{v}"] = d_patch(270 + v, (144, 112, 96)[v], (88, 72, 56)[v], "accent")
        out[f"icesheet_{v}"] = d_icesheet(280 + v, (128, 104, 88)[v], (72, 60, 52)[v])
    for v in range(4):
        out[f"gravel_{v}"] = d_gravel(240 + v)
        out[f"scoria_{v}"] = d_gravel(290 + v, 60, 40, None, (4, 3, 1, 0), 6)
        out[f"rubble_{v}"] = d_gravel(300 + v, 72, 18, 9)          # entulho no pé dos morros
    return out


# o que cada região espalha (peso relativo) numa célula de 96 px (≈ 3×3 tiles). Chance de ter algo: DECAL_P
DECAL_MIX = {
    "plateau": [("patch_dark", 3), ("patch_light", 2), ("crack", 5), ("plates", 3), ("gravel", 4), ("wind", 3)],
    "salar":   [("ridges", 4), ("patch_dark", 2), ("crack", 2), ("patch_light", 2)],
    "basalt":  [("scoria", 5), ("stain", 2), ("crack", 3), ("patch_dark", 2), ("plates", 2)],
    "frost":   [("icesheet", 4), ("wind", 4), ("gravel", 2), ("patch_light", 2)],
    "bed":     [("crack", 2), ("patch_light", 2)],
}
DECAL_P = {"plateau": 0.40, "salar": 0.35, "basalt": 0.45, "frost": 0.40, "bed": 0.25}
DECAL_CELL = 96
