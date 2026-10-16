"""Chão assado da superfície (v0.4 Marco 2 · trilha B · bíblia §11).

Porta a receita da Designer (tools/sprites/regions_scene.py, `Scene.ground` + `scatter`) pro jogo. Só vale
na superfície e só com `layer.geo` (o mapa de regiões da trilha A); sem geo, o render desenha o chão de hoje.

Como funciona, em uma frase: o chão é ASSADO em blocos de 16×16 tiles (512×512 px, o tamanho da textura) com
numpy, uma vez, e no quadro é só 1 blit por bloco visível (~6) em vez de ~550 blits por tile.

    assar (caro, ~80 ms por bloco, em faixas de 32 linhas: até GROUND_BAKE_MS por quadro)
      1. deslocamento de domínio (`geo.warp`, ±14 px, o mesmo do `geo.region_px`, calculado a cada 2 px e
         interpolado): a região de cada pixel é a do tile em (x + dx, y + dy), então a divisa entre regiões
         vira curva e nunca linha de tile
      2. classe do pixel: planalto, salar, basalto, gelada ou LEITO (planalto dentro de bacia: silte com
         rachadura de lama). 1 px de fenda (índice 1) na divisa entre classes
      3. textura da classe (ground_<classe>.png, PNG indexado 512×512 que emenda: o bloco é a textura inteira)
      4. marcas d'água secas (curvas de nível L1, L2, L3 das bacias): linha mineral clara; no salar, anel escuro
      5. decalques (manchas, rachaduras longas, placas, cascalho, sulcos...) sorteados numa grade de 96 px
         presa no mundo, pela seed
    O resultado NÃO tem cor: é um CÓDIGO por pixel (classe·16 + índice da rampa), igual em todos os estágios.

    colorir (barato, ~1 ms): o código vira uma Surface de 8 bits com a paleta do estágio (regions_palettes.json,
    tabela BASE, chave storm/arid/mist/green) e é copiado pra uma superfície opaca. Trocar de estágio = trocar
    a paleta, sem assar de novo.

Transição de estágio (a mancha do game/transition.py): o bloco que está metade num estágio e metade no outro
usa os códigos 128..255 pro estágio novo (paleta = 128 cores do velho + 128 do novo). Cada pixel pergunta ao
StageMap o estágio do tile em (x + dx, y + dy), com o MESMO warp das regiões: a frente da mancha vira uma
curva orgânica, como a borda das regiões, no lugar do pontilhado por tile de antes. O bloco misturado é refeito
quando o degrau da janela muda (1% da janela) e, até ficar pronto, o bloco anterior continua na tela.

Cache: LRU de GROUND_CACHE_BLOCKS blocos. Por quadro faz no máximo UM trabalho: assar (por faixas, dentro do
orçamento) ou colorir 1 bloco, com prioridade pro que está na tela; depois o que está a até GROUND_PREFETCH_PX
dela. Bloco na tela sem assado nenhum aparece com a cor chapada da região de cada tile. Exceção: se NENHUM
bloco da tela tem assado (começo do jogo, teleporte), assa a tela inteira na hora (um "carregando" de ~0,5 s,
melhor que meio segundo de chão chapado).

Funções puras (sem pygame) pra testar: `warp_half`, `depth_field`, `smooth_sample`, `bake_block_codes`,
`decals_for_block`, `decor_items`, e os da v9 (M3.0): `v9_decals_for_block`, `decor_items_v9`, `decor_tile_free`,
`decor_layers`.
"""

from __future__ import annotations

import json
import math
import time
import zlib
from collections import OrderedDict
from typing import NamedTuple

import numpy as np
import pygame

from game import config as C
from game import geo as geo_mod
from game.surfaces import opaque

T = C.TILE
BT = C.GROUND_BLOCK_TILES
BP = BT * T                           # 512 px: lado do bloco = lado da textura
PLATEAU, SALAR, BASALT, FROST = 0, 1, 2, 3
BED = 4                               # leito seco (planalto dentro de bacia)
FIXED = 5                             # cores fixas (marca d'água clara), não mudam com a rampa
CLASS_NAMES = ("plateau", "salar", "basalt", "frost", "bed")
PALE, PALE2 = FIXED * 16, FIXED * 16 + 1
FIXED_COLORS = {PALE: (0xDC, 0xD0, 0xBB), PALE2: (0xC4, 0xB5, 0x9C)}
OUTLINE = (0x1B, 0x16, 0x30)
NEW = 128                             # código + 128 = o mesmo pixel no estágio novo (transição)
COVER_BASE = 81                       # códigos 82..92 = cores da cobertura do Verde (grama 1..5, musgo 7..11)
COVER_STEP = 4                        # o ruído das manchas é calculado a cada 4 px e interpolado
MIST_DAMP, MIST_EDGE = 16, 32         # bits do mapa de cobertura: mancha de umidade da Névoa e a borda dela
WT_SIDE = BT + 2                      # tile local do warp: -1..16 -> 0..17
PAD = 2                               # px a mais em volta de cada faixa (bordas e anéis olham o vizinho)
DECOR = {BASALT: "shards", SALAR: "salt_crystals", FROST: "ice_chunks"}   # decoração solta por região


def stage_key(stage: int) -> str:
    return C.STAGES[stage - 1].key


# ---------------------------------------------------------------------------------------------------------------
# Ruído e warp: os do game/geo.py (o mesmo hash, o mesmo deslocamento da borda que o geo.region_px usa)
# ---------------------------------------------------------------------------------------------------------------
_smooth = geo_mod._smooth
hash2 = geo_mod.hash2


def seed_salt(seed: int) -> int:
    """Mistura a seed do mundo nos sorteios do chão (o hash quer um inteiro >= 0)."""
    return (int(seed) * 7919) & 0xFFFFF


def _up2(a: np.ndarray) -> np.ndarray:
    """Amostras a cada 2 px ((h/2+1)×(w/2+1)) -> grade cheia h×w, bilinear."""
    h, w = (a.shape[0] - 1) * 2, (a.shape[1] - 1) * 2
    out = np.empty((h, w), a.dtype)
    tl, tr, bl, br = a[:-1, :-1], a[:-1, 1:], a[1:, :-1], a[1:, 1:]
    out[0::2, 0::2] = tl
    out[0::2, 1::2] = (tl + tr) / 2
    out[1::2, 0::2] = (tl + bl) / 2
    out[1::2, 1::2] = (tl + tr + bl + br) / 4
    return out


def warp_half(geo, xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """O `geo.warp` (o deslocamento do `geo.region_px`), calculado a cada 2 px (nos px de mundo pares) e interpolado: 4× menos ruído pra
    calcular (o assado cai de ~65 pra ~35 ms por bloco) e a diferença é de fração de px. `xs`/`ys` vêm de um
    mgrid que começa em px par e tem lados pares."""
    x0, y0 = int(xs[0, 0]), int(ys[0, 0])
    h, w = xs.shape
    cy, cx = np.mgrid[y0:y0 + h + 1:2, x0:x0 + w + 1:2]
    dx, dy = geo.warp(cx, cy)
    return _up2(np.asarray(dx, float)), _up2(np.asarray(dy, float))


def depth_field(basin: np.ndarray) -> np.ndarray:
    """Profundidade por tile pras curvas de nível: 3 no que alaga no L1, 2 no L2, 1 no L3, 0 fora de bacia.
    A curva do nível k (0..2) é onde o campo interpolado cruza 2,5 - k."""
    b = np.asarray(basin)
    return np.where(b >= 0, 3 - b, 0).astype(np.float32)


def smooth_sample(field: np.ndarray, u, v) -> np.ndarray:
    """Bilinear com smoothstep entre os CENTROS dos tiles (a "grade dual"): a curva fica redonda, sem escada."""
    h, w = field.shape
    i = np.floor(u).astype(np.int64)
    j = np.floor(v).astype(np.int64)
    fu, fv = _smooth(np.clip(u - i, 0, 1)), _smooth(np.clip(v - j, 0, 1))
    i0, i1 = np.clip(i, 0, w - 1), np.clip(i + 1, 0, w - 1)
    j0, j1 = np.clip(j, 0, h - 1), np.clip(j + 1, 0, h - 1)
    return (field[j0, i0] * (1 - fu) * (1 - fv) + field[j0, i1] * fu * (1 - fv) + field[j1, i0] * (1 - fu) * fv
            + field[j1, i1] * fu * fv)


def tile_classes(geo) -> np.ndarray:
    """Classe de cada TILE (sem warp): a região, ou LEITO no planalto dentro de bacia. Pra cor chapada e decalques."""
    cls = np.asarray(geo.region, dtype=np.uint8).copy()
    cls[(cls == PLATEAU) & (np.asarray(geo.basin) >= 0)] = BED
    return cls


# ---------------------------------------------------------------------------------------------------------------
# Arte (assets/sprites/regions/): texturas, decalques, rampas
# ---------------------------------------------------------------------------------------------------------------
def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _unfilter(raw: bytes, w: int, h: int) -> np.ndarray:
    """Desfaz os filtros de linha do PNG (1 byte por pixel)."""
    rows = np.frombuffer(raw, np.uint8).reshape(h, w + 1)
    out = np.zeros((h, w), np.uint8)
    prev = np.zeros(w, np.int32)
    for y in range(h):
        f, line = rows[y, 0], rows[y, 1:].astype(np.int32)
        if f == 0:
            cur = line
        elif f == 1:                                   # Sub
            cur = np.cumsum(line) & 0xFF
        elif f == 2:                                   # Up
            cur = (line + prev) & 0xFF
        else:                                          # Average / Paeth: pixel a pixel (raro; a Designer usa 0)
            cur = np.zeros(w, np.int32)
            for x in range(w):
                a = int(cur[x - 1]) if x else 0
                b = int(prev[x])
                if f == 3:
                    cur[x] = (line[x] + (a + b) // 2) & 0xFF
                else:
                    c = int(prev[x - 1]) if x else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    cur[x] = (line[x] + pred) & 0xFF
        out[y] = cur
        prev = cur
    return out


def load_indexed(path) -> np.ndarray | None:
    """PNG indexado (modo P, 8 bits) -> array (altura, largura) dos ÍNDICES. None se não existe ou não é P8.

    O pygame converte PNG indexado com tRNS pra 32 bits e perde o índice; então lê o PNG direto (zlib)."""
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        pos, idat, head = 8, [], None
        while pos < len(data):
            n = int.from_bytes(data[pos:pos + 4], "big")
            kind = data[pos + 4:pos + 8]
            if kind == b"IHDR":
                head = data[pos + 8:pos + 21]
            elif kind == b"IDAT":
                idat.append(data[pos + 8:pos + 8 + n])
            pos += 12 + n
        w, h = int.from_bytes(head[0:4], "big"), int.from_bytes(head[4:8], "big")
        depth, color, interlace = head[8], head[9], head[12]
        if (depth, color, interlace) != (8, 3, 0):
            print(f"[ground] {path.name} não é PNG indexado de 8 bits sem entrelaçar")
            return None
        return _unfilter(zlib.decompress(b"".join(idat)), w, h)
    except (OSError, ValueError, TypeError, zlib.error) as err:
        print(f"[ground] não consegui ler {path.name}: {err}")
        return None


class RegionArt:
    """Texturas de chão, decalques, decoração solta e rampas (regions_palettes.json). `ok` = tudo carregou."""

    def __init__(self, folder=None):
        folder = folder or C.REGIONS_DIR
        self.ok = False
        meta_path = folder / "regions_palettes.json"
        if not meta_path.exists():
            return
        self.meta = json.loads(meta_path.read_text())
        self.ramps = self.meta["ramps"]
        self.decal_p = self.meta["decal_p"]
        self.decal_mix = {k: [(n, w) for n, w in v] for k, v in self.meta["decal_mix"].items()}
        self.v9 = self.meta.get("v9_density", {})          # v9 (M3.0): decal_p/decal_mix, decor_p, moss_on
        self.files = self.meta["files"]
        self.textures = []
        for name in CLASS_NAMES:
            tex = load_indexed(folder / f"ground_{name}.png")
            if tex is None or tex.shape != (BP, BP):
                return
            self.textures.append(tex)
        self.tex_stack = np.stack(self.textures)          # (5, 512, 512)
        self.decals: dict[str, list[np.ndarray]] = {}      # nome -> variantes (índices, 255 = vazio)
        for path in sorted(folder.glob("decal_*.png")):
            name, v = path.stem.removeprefix("decal_").rsplit("_", 1)
            idx = load_indexed(path)
            if idx is not None:
                self.decals.setdefault(name, []).append(idx)
        self.decor: dict[str, list[np.ndarray]] = {}
        for path in sorted(folder.glob("decor_*.png")):
            name, v = path.stem.removeprefix("decor_").rsplit("_", 1)
            idx = load_indexed(path)
            if idx is not None:
                self.decor.setdefault(name, []).append(idx)
        # Itens pausados pelo dono (C.SCENERY_PAUSED, nomes de arquivo sem a variação): o sorteio continua igual
        # e só o desenho some (o render pula decalque/solto sem sprite), então os outros não ocupam o lugar.
        for key in C.SCENERY_PAUSED:
            kind, _, name = key.partition("_")
            (self.decals if kind == "decal" else self.decor).pop(name, None)
        self.ok = True

    def ramp(self, table: str, region: str, stage: str) -> list[tuple[int, int, int]]:
        return [_hex(c) for c in self.ramps[table][region][stage]]

    def lut(self, stage: str) -> np.ndarray:
        """128×3: as cores dos códigos do chão (classe·16 + índice) no estágio."""
        out = np.zeros((NEW, 3), np.uint8)
        for c, name in enumerate(CLASS_NAMES):
            cols = self.ramp("BASE", name, stage) + [OUTLINE, (0, 0, 0)]
            out[c * 16:c * 16 + len(cols)] = cols
        for code, col in FIXED_COLORS.items():
            out[code] = col
        if stage == "green":                           # cobertura: grama (1..5) e musgo do basalto (7..11)
            for i in range(1, 6):
                out[COVER_BASE + i] = _hex(C.GROUND_GRASS[i])
                out[COVER_BASE + 6 + i] = _hex(C.GROUND_MOSS[i])
        return out


# ---------------------------------------------------------------------------------------------------------------
# Assar (puro numpy): códigos de uma faixa do bloco
# ---------------------------------------------------------------------------------------------------------------
def _sh(a, dy, dx, fill):
    """a deslocado: out[y, x] = a[y - dy, x - dx] (o que sai da borda vira `fill`)."""
    out = np.full_like(a, fill)
    h, w = a.shape
    out[max(0, dy):min(h, h + dy), max(0, dx):min(w, w + dx)] = \
        a[max(0, -dy):min(h, h - dy), max(0, -dx):min(w, w - dx)]
    return out


def bake_strip(geo, art: RegionArt, bx: int, by: int, y0: int, y1: int, depth=None):
    """Códigos (y1-y0, 512), o tile local do warp (pra transição) e o mapa de cobertura das linhas y0..y1 do bloco."""
    H, W = geo.region.shape
    ox, oy = bx * BP, by * BP
    ys, xs = np.mgrid[oy + y0 - PAD:oy + y1 + PAD, ox - PAD:ox + BP + PAD]
    dx, dy = warp_half(geo, xs, ys)
    ux, uy = (xs + dx) / T, (ys + dy) / T
    ti = np.clip(np.floor(ux).astype(np.int64), 0, W - 1)
    tj = np.clip(np.floor(uy).astype(np.int64), 0, H - 1)
    reg = np.asarray(geo.region)[tj, ti]
    d = smooth_sample(depth if depth is not None else depth_field(geo.basin), ux - 0.5, uy - 0.5)
    cls = reg.astype(np.uint8)
    cls[(d > 0.5) & (reg == PLATEAU)] = BED
    # 1 px de fenda na divisa: o pixel cujo vizinho de baixo ou da direita é de outra classe
    edge = (cls != _sh(cls, -1, 0, 255)) | (cls != _sh(cls, 0, -1, 255))
    # marcas d'água secas: L1, L2 (tracejadas) e L3 (contínua, a borda do leito)
    sal = cls == SALAR
    marks = np.full(cls.shape, 255, np.uint8)
    for k in range(3):
        below = d > 2.5 - k
        if not below.any():
            continue
        ring = below & ~(_sh(below, 1, 0, True) & _sh(below, -1, 0, True) & _sh(below, 0, 1, True)
                         & _sh(below, 0, -1, True))
        ring |= _sh(ring, 0, 1, False) & below
        if k < 2:
            ring &= hash2(xs // 5, ys // 5, 77 + k + seed_salt(geo.seed)) < 0.7
        marks[ring & ~sal] = PALE if k == 2 else PALE2
        marks[ring & sal] = SALAR * 16 + 1
        under = _sh(ring, 1, 0, False) & ~ring & below
        marks[under & ~sal] = BED * 16 + 2
        marks[under & sal] = SALAR * 16 + 0
    crop = (slice(PAD, -PAD), slice(PAD, -PAD))
    cls_c = cls[crop]
    idx = np.take_along_axis(art.tex_stack[:, y0:y1, :], cls_c[None].astype(np.int64), 0)[0]
    idx = np.where(edge[crop], 1, idx)
    code = (cls_c * 16 + idx).astype(np.uint8)
    m = marks[crop]
    code = np.where(m != 255, m, code)
    wt = (np.clip(tj[crop] - by * BT + 1, 0, WT_SIDE - 1) * WT_SIDE
          + np.clip(ti[crop] - bx * BT + 1, 0, WT_SIDE - 1)).astype(np.uint16)
    if getattr(art, "cover", True):
        cover = cover_strip(geo, depth if depth is not None else depth_field(geo.basin), xs, ys, cls, d)[crop]
    else:                                          # caverna (v0.6 Fundo M2): sem grama nem umidade
        cover = np.zeros(code.shape, np.uint8)
    return code, wt[::2, ::2], cover


# ---------------------------------------------------------------------------------------------------------------
# Cobertura do estágio (porte do `Scene.cover_layer` da Designer): umidade na Névoa, grama/musgo no Verde
# ---------------------------------------------------------------------------------------------------------------
# O chão assado não tem cor nem estágio, então a cobertura é assada num MAPA À PARTE (1 byte por pixel), igual em
# todos os estágios: bits 0..3 = a grama (0 nada, 1..5 = índice da rampa, +6 no musgo do basalto), bit 4 = mancha de
# umidade da Névoa, bit 5 = a borda de cima dela. Quem decide o que aparece é o `_colorize`, pelo estágio de cada pixel.
_TN: list = []


def _pvnoise(xs, ys, cell: float, seed: int, period: int) -> np.ndarray:
    """Value noise que emenda a cada `period` células (o `vnoise` da Designer com `period`)."""
    fx, fy = np.asarray(xs, float) / cell, np.asarray(ys, float) / cell
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = _smooth(fx - ix), _smooth(fy - iy)
    a, b = hash2(ix % period, iy % period, seed), hash2((ix + 1) % period, iy % period, seed)
    c, d = hash2(ix % period, (iy + 1) % period, seed), hash2((ix + 1) % period, (iy + 1) % period, seed)
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty


def _pfbm(xs, ys, cell: float, seed: int, octaves: int, period: int) -> np.ndarray:
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * _pvnoise(xs, ys, cell / (2 ** o), seed + 101 * o, period * (2 ** o))
        norm += amp
        amp *= 0.5
    return tot / norm


def grass_levels() -> np.ndarray:
    """Tabela 256×256 (que emenda) do nível da grama 1..4: o `R.organic(x % 256, y % 256, 256, 16, 333)` da Designer."""
    if not _TN:
        p, cells, seed = 256, 16, 333
        ys, xs = np.mgrid[0:p, 0:p]
        warp = p / cells * 0.9
        wx = (xs + warp * (_pfbm(xs, ys, p / (cells * 2), seed + 31, 2, cells * 2) - 0.5)) % p
        wy = (ys + warp * (_pfbm(xs, ys, p / (cells * 2), seed + 37, 2, cells * 2) - 0.5)) % p
        tn = _pfbm(wx, wy, p / cells, seed, 3, cells)
        _TN.append(np.clip((tn * 5).astype(np.int64), 1, 4).astype(np.uint8))
    return _TN[0]


def near_basin(geo, depth: np.ndarray, x0: int, y0: int, h: int, w: int):
    """Máscara (h, w) dos px de mundo [x0, x0+w) × [y0, y0+h) que estão a até ~14 px da bacia (a água do Verde, o
    nível máximo L3 = `d > 0.5`), ou None se não tem bacia por perto. A Designer dilata a água com 4 deslocamentos
    (2, 5, 9, 14 px) nas 4 direções; aqui é a mesma ideia a cada 2 px (1, 2, 4, 7 amostras = 2, 4, 8, 14 px).
    Usa a BACIA, não o `water_level`: a cobertura não depende de o lago já ter subido e nada é reassado quando sobe."""
    H, W = geo.basin.shape
    m = 16 + C.GEO_WARP + 2
    ty0, ty1 = max(0, (y0 - m) // T), min(H - 1, (y0 + h + m) // T)
    tx0, tx1 = max(0, (x0 - m) // T), min(W - 1, (x0 + w + m) // T)
    if not (geo.basin[ty0:ty1 + 1, tx0:tx1 + 1] >= 0).any():
        return None
    pad = 16
    cy, cx = np.mgrid[y0 - pad:y0 + h + pad + 1:2, x0 - pad:x0 + w + pad + 1:2]
    dx, dy = geo.warp(cx, cy)
    d = smooth_sample(depth, (cx + dx) / T - 0.5, (cy + dy) / T - 0.5)
    wet = d > 0.5
    near = np.zeros_like(wet)
    for k in (1, 2, 4, 7):
        near |= _sh(wet, k, 0, False) | _sh(wet, -k, 0, False) | _sh(wet, 0, k, False) | _sh(wet, 0, -k, False)
    near = near[pad // 2:pad // 2 + h // 2, pad // 2:pad // 2 + w // 2]
    return np.repeat(np.repeat(near, 2, 0), 2, 1)


def _upn(a: np.ndarray, k: int) -> np.ndarray:
    """Amostras a cada k px ((h/k+1)×(w/k+1)) -> grade cheia h×w, bilinear."""
    h, w = (a.shape[0] - 1) * k, (a.shape[1] - 1) * k
    fy, fx = np.arange(h) / k, np.arange(w) / k
    i, j = fy.astype(np.int64), fx.astype(np.int64)
    ty, tx = (fy - i)[:, None], (fx - j)[None, :]
    i1, j1 = np.minimum(i + 1, a.shape[0] - 1), np.minimum(j + 1, a.shape[1] - 1)
    top = a[i][:, j] * (1 - tx) + a[i][:, j1] * tx
    bot = a[i1][:, j] * (1 - tx) + a[i1][:, j1] * tx
    return top * (1 - ty) + bot * ty


def cover_strip(geo, depth: np.ndarray, xs: np.ndarray, ys: np.ndarray, cls: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Mapa de cobertura (uint8, ver acima) dos px `xs`/`ys` (mgrid com PAD em volta, começa em px par, lados pares),
    com `cls` a classe de cada px e `d` a profundidade de bacia suavizada (as mesmas do `bake_strip`).

    Porte do `Scene.cover_layer`: o ruído n é um fbm (célula de 5 tiles) com o domínio deformado por OUTRO warp
    (as coordenadas deslocadas de +3000/+1700, como a Designer), calculado a cada 4 px e interpolado (as feições têm 40 px ou mais)."""
    salt = seed_salt(geo.seed)
    h, w = xs.shape
    x0, y0 = int(xs[0, 0]), int(ys[0, 0])
    cy, cx = np.mgrid[y0:y0 + h + 1:COVER_STEP, x0:x0 + w + 1:COVER_STEP]
    dx, dy = geo.warp(cx + 3000, cy + 1700)
    n = _upn(geo_mod.fbm((cx + dx) / T, (cy + dy) / T, C.GROUND_COVER_CELL, C.GROUND_COVER_SEED + salt, 3), COVER_STEP)
    # Verde: grama em manchas; o limiar depende da classe e cai perto da bacia; nunca na água (a bacia inteira)
    thr = np.array(C.GROUND_GRASS_THR)[cls]
    near = near_basin(geo, depth, x0, y0, h, w)
    if near is not None:
        thr = np.where(near, thr - C.GROUND_GRASS_NEAR, thr)
    g = (n > thr) & (d <= 0.5)
    edge = g & ~(_sh(g, 1, 0, True) & _sh(g, -1, 0, True) & _sh(g, 0, 1, True) & _sh(g, 0, -1, True))
    cand = _sh(edge, 1, 0, False) & ~g                                           # folhinhas de 1×2 px saindo da borda
    tuft = np.zeros_like(g)
    tuft[cand] = hash2(xs[cand], ys[cand], 337 + salt) < 0.35
    lvl = grass_levels()[ys % 256, xs % 256]
    blade = np.zeros_like(g)
    blade[g] = hash2(xs[g], ys[g] // 2, 335 + salt) < 0.05
    idx = np.where(edge, 1, np.where(blade, 5, lvl)).astype(np.uint8)
    grass = np.where(g, idx, np.where(tuft, 3, 0)).astype(np.uint8)
    grass[(grass > 0) & (cls == BASALT)] += 6                                    # no basalto é musgo
    # Névoa: mancha de umidade (fora da água do nível L2) e a borda de cima dela
    m = (n > C.GROUND_MIST_THR) & (d <= 1.5)
    top = m & ~_sh(m, 1, 0, True)
    return (grass + m * MIST_DAMP + top * MIST_EDGE).astype(np.uint8)


def decal_skip_tiles(geo) -> set[tuple[int, int]]:
    """Tiles onde não sorteia decalque: em volta da base e das formações."""
    skip = set()
    bx, by = C.BASE_TILE
    r = C.GROUND_BASE_CLEAR
    for ty in range(by - r, by + r + 1):
        for tx in range(bx - r, bx + r + 1):
            if math.hypot(tx - bx, ty - by + 1) < r:
                skip.add((tx, ty))
    for f in geo.formations:
        for fx, fy in f.box:                    # a caixa inteira (no arco, o vão também) + folga
            for ddy in range(-1, 3):
                for ddx in range(-2, 3):
                    skip.add((fx + ddx, fy + ddy))
    return skip


def decals_for_block(geo, art: RegionArt, bx: int, by: int, tcls: np.ndarray, skip: set) -> list[tuple]:
    """Decalques que tocam o bloco: [(x, y, classe, índices)] em px de mundo (canto de cima-esquerda).
    1 sorteio grande e 1 miúdo por célula de 96 px presa no mundo; a mesma célula dá sempre o mesmo decalque."""
    cell = art.meta["decal_cell"]
    margin = C.GROUND_DECAL_MARGIN
    H, W = tcls.shape
    salt = seed_salt(geo.seed)
    x0, y0 = bx * BP, by * BP
    out = []
    for cy in range((y0 - margin) // cell, (y0 + BP + margin) // cell + 1):
        for cx in range((x0 - margin) // cell, (x0 + BP + margin) // cell + 1):
            for layer in (0, 1):
                h = lambda s: float(hash2(cx, cy, s + layer + salt))   # noqa: E731
                px = cx * cell + int(h(702) * cell)
                py = cy * cell + int(h(704) * cell)
                tx, ty = px // T, py // T
                if not (0 <= tx < W and 0 <= ty < H) or (tx, ty) in skip:
                    continue
                c = int(tcls[ty, tx])
                reg = CLASS_NAMES[c]
                if h(706) > art.decal_p[reg] * (1.0 if layer == 0 else 0.6):
                    continue
                mix = art.decal_mix[reg]
                if layer == 1:                         # o 2º sorteio é sempre coisa miúda
                    mix = [m for m in mix if m[0] in ("gravel", "scoria", "plates", "ridges", "crack")] or mix
                r = h(708) * sum(wt for _, wt in mix)
                for name, wt in mix:
                    r -= wt
                    if r <= 0:
                        break
                variants = art.decals.get(name)
                if not variants:
                    continue
                idx = variants[int(h(710) * len(variants))]
                if h(712) < 0.5 and not name.startswith("wind"):
                    idx = idx[:, ::-1]
                dh, dw = idx.shape
                x, y = px - dw // 2, py - dh // 2
                if x < x0 + BP and y < y0 + BP and x + dw > x0 and y + dh > y0:
                    out.append((x, y, c, idx))
    out += [d[:4] for d in v9_decals_for_block(geo, art, bx, by, tcls, skip)]   # por cima dos da v8
    return out


def v9_decals_for_block(geo, art: RegionArt, bx: int, by: int, tcls: np.ndarray, skip: set) -> list[tuple]:
    """v9 (M3.0): o 3º sorteio por célula de 96 px, com hash e posição próprios (os da Designer, 952..962, mais
    a seed) e só a lista da v9 da classe (`v9_density.decal_mix`, chance `decal_p`). [(x, y, classe, índices,
    nome)]. Mesmas exclusões dos outros (base, volta das formações); espelho horizontal com 50%."""
    v9 = getattr(art, "v9", None) or {}
    if not v9.get("decal_p"):
        return []
    cell = art.meta["decal_cell"]
    margin = C.GROUND_DECAL_MARGIN
    H, W = tcls.shape
    salt = seed_salt(geo.seed)
    x0, y0 = bx * BP, by * BP
    out = []
    for cy in range((y0 - margin) // cell, (y0 + BP + margin) // cell + 1):
        for cx in range((x0 - margin) // cell, (x0 + BP + margin) // cell + 1):
            h = lambda s: float(hash2(cx, cy, s + salt))   # noqa: E731
            px = cx * cell + int(h(952) * cell)
            py = cy * cell + int(h(954) * cell)
            tx, ty = px // T, py // T
            if not (0 <= tx < W and 0 <= ty < H) or (tx, ty) in skip:
                continue
            c = int(tcls[ty, tx])
            reg = CLASS_NAMES[c]
            mix = v9["decal_mix"].get(reg)
            if not mix or h(956) > v9["decal_p"].get(reg, 0.0):
                continue
            r = h(958) * sum(wt for _, wt in mix)
            for name, wt in mix:
                r -= wt
                if r <= 0:
                    break
            variants = art.decals.get(name)
            if not variants:
                continue
            idx = variants[int(h(960) * len(variants))]
            if h(962) < 0.5:
                idx = idx[:, ::-1]
            dh, dw = idx.shape
            x, y = px - dw // 2, py - dh // 2
            if x < x0 + BP and y < y0 + BP and x + dw > x0 and y + dh > y0:
                out.append((x, y, c, idx, name))
    return out


def paste_decals(code: np.ndarray, decals, bx: int, by: int) -> None:
    x0, y0 = bx * BP, by * BP
    for x, y, c, idx in decals:
        lx, ly = x - x0, y - y0
        sx0, sy0 = max(0, -lx), max(0, -ly)
        sx1, sy1 = min(idx.shape[1], BP - lx), min(idx.shape[0], BP - ly)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        part = idx[sy0:sy1, sx0:sx1]
        dst = code[ly + sy0:ly + sy1, lx + sx0:lx + sx1]
        solid = part != 255
        dst[solid] = c * 16 + part[solid]


def bake_block_codes(geo, art: RegionArt, bx: int, by: int, ctx=None):
    """Gerador: assa o bloco faixa por faixa (cada `next` faz uma) e no fim devolve (código, warp, cobertura)."""
    ctx = ctx or BakeContext(geo)
    code = np.zeros((BP, BP), np.uint8)
    wt = np.zeros((BP // 2, BP // 2), np.uint16)
    cover = np.zeros((BP, BP), np.uint8)
    rows = C.GROUND_BAKE_ROWS
    for y0 in range(0, BP, rows):
        c, w, cv = bake_strip(geo, art, bx, by, y0, y0 + rows, ctx.depth)
        code[y0:y0 + rows] = c
        wt[y0 // 2:(y0 + rows) // 2] = w
        cover[y0:y0 + rows] = cv
        yield None
    paste_decals(code, decals_for_block(geo, art, bx, by, ctx.tcls, ctx.skip), bx, by)
    yield code, wt, cover


class BakeContext:
    """O que todo bloco do mesmo geo reaproveita (campo de profundidade, classe por tile, tiles sem decalque)."""

    def __init__(self, geo):
        self.depth = depth_field(geo.basin)
        self.tcls = tile_classes(geo)
        self.skip = decal_skip_tiles(geo)


def decor_items(geo) -> dict[int, list[tuple[int, str, int]]]:
    """Decoração solta com altura (lascas no basalto, cristais no salar, gelo na faixa gelada): por linha,
    [(tx, nome, variante)]. Não colide nem minera; quem decide se aparece (tile livre) é o render."""
    region = np.asarray(geo.region)
    H, W = region.shape
    ys, xs = np.mgrid[0:H, 0:W]
    salt = seed_salt(geo.seed)
    pick = hash2(xs, ys, 601 + salt) < C.GROUND_DECOR_P
    var = (hash2(xs, ys, 602 + salt) * 3).astype(int)
    skip = decal_skip_tiles(geo)
    out: dict[int, list] = {}
    for ty, tx in zip(*np.nonzero(pick)):
        reg = int(region[ty, tx])
        if reg not in DECOR or (int(tx), int(ty)) in skip:
            continue
        out.setdefault(int(ty), []).append((int(tx), DECOR[reg], int(var[ty, tx])))
    return out


class Decor9(NamedTuple):
    """Um solto da v9: o pé (px do mundo, onde cai o centro de baixo do sprite), o tipo, a variação e o espelho."""
    tx: int
    ty: int
    name: str
    v: int
    foot_x: int
    foot_y: int
    flip: bool


def decor_items_v9(geo, decor_p: dict) -> dict[int, list[Decor9]]:
    """v9 (M3.0): soltos novos com altura, 1 sorteio por tile (as chances da classe em `v9_density.decor_p` somam;
    leito seco = bed). Pé em (tx·32 + 16 ± 7, ty·32 + 26..29), espelho com 50%. Nunca no tile de um solto da v8,
    na volta da base nem das formações; máquina, veio, destroço, rocha e parede quem tira é o render
    (`decor_tile_free`), porque mudam no jogo. Por linha, como o `decor_items`."""
    if not decor_p:
        return {}
    tcls = tile_classes(geo)
    H, W = tcls.shape
    ys, xs = np.mgrid[0:H, 0:W]
    salt = seed_salt(geo.seed)
    r = hash2(xs, ys, 941 + salt)
    v8 = {(tx, ty) for ty, row in decor_items(geo).items() for tx, _, _ in row}
    skip = decal_skip_tiles(geo)
    total = np.zeros((H, W))
    for c, cname in enumerate(CLASS_NAMES):
        total[tcls == c] = sum(p for _, p in decor_p.get(cname, ()))
    out: dict[int, list[Decor9]] = {}
    for ty, tx in zip(*np.nonzero(r < total)):
        tx, ty = int(tx), int(ty)
        if (tx, ty) in v8 or (tx, ty) in skip:
            continue
        acc, pick = 0.0, None
        for name, p in decor_p[CLASS_NAMES[int(tcls[ty, tx])]]:
            acc += p
            if r[ty, tx] < acc:
                pick = name
                break
        if pick is None:
            continue
        h = lambda s: float(hash2(tx, ty, s + salt))   # noqa: E731
        out.setdefault(ty, []).append(Decor9(
            tx, ty, pick, int(h(942) * 3), tx * T + 16 + int(h(944) * 14) - 7, ty * T + 26 + int(h(945) * 4),
            h(943) < 0.5))
    return out


def decor_tile_free(world, tx: int, ty: int, machine_at) -> bool:
    """O solto (v8 ou v9) aparece nesse tile? Só em chão livre e seco: some onde tem máquina, veio, destroço, rocha,
    parede ou formação (os três últimos não são chão) e debaixo d'água (v0.4 M3.3: o lago cobre o leito)."""
    return world.is_floor(tx, ty) and not world.vein_at(tx, ty) and not world.wreck_at(tx, ty) \
        and not machine_at((tx, ty)) and not world.is_water(tx, ty, C.GREEN_STAGE)


def decor_layers(name: str, stage: int, moss_on) -> list[str]:
    """O que desenhar no lugar do solto, em ordem: a pedra e, só no Verde, o overlay de musgo de mesmo N."""
    if stage >= C.GREEN_STAGE and name in moss_on:
        return [name, f"{name}_moss"]
    return [name]


# ---------------------------------------------------------------------------------------------------------------
# Cache e desenho (pygame)
# ---------------------------------------------------------------------------------------------------------------
class Ground:
    """Chão assado da superfície: cache LRU de blocos + desenho. Uma por Renderer."""

    def __init__(self, enabled: bool = True):
        self.wanted = enabled and C.ENABLE_SPRITES
        self._art: RegionArt | None = None
        self._geo = None
        self.ctx: BakeContext | None = None
        self._index: OrderedDict = OrderedDict()   # (bx, by) -> (código, warp, cobertura)    (o caro, sem estágio)
        self._color: dict = {}                      # (bx, by) -> (variante, Surface opaca)
        self._jobs: dict = {}                       # (bx, by) -> gerador do assado em andamento
        self._grid_memo: dict = {}                  # estágios dos tiles de um bloco na transição
        self._grid_tag = None
        self._lut: dict[str, np.ndarray] = {}
        self._decor: dict[int, list] = {}
        self._decor9: dict[int, list[Decor9]] = {}
        self._decor_surf: dict = {}
        self.sync = False                           # True = assa tudo que pedir na hora (prints do mapa)
        self.bake_ms: list[float] = []              # tempo de cada bloco assado (B4)
        self._bake_started: dict = {}

    # ---- arte e geo --------------------------------------------------------------------------------------
    @property
    def art(self) -> RegionArt | None:
        if self._art is None and self.wanted:
            self._art = RegionArt()
        return self._art if self._art is not None and self._art.ok else None

    @property
    def enabled(self) -> bool:
        return self.art is not None

    def bind(self, geo) -> None:
        """Troca de mundo (novo jogo, load): joga a cache fora."""
        if geo is self._geo:
            return
        self._geo = geo
        self.ctx = BakeContext(geo)
        self._index.clear()
        self._color.clear()
        self._jobs.clear()
        self._grid_memo.clear()
        self._decor = decor_items(geo)
        art = self.art
        self._decor9 = decor_items_v9(geo, art.v9.get("decor_p", {})) if art is not None else {}
        self.bake_ms.clear()

    def reset(self) -> None:
        """Esquece o geo e a cache (o próximo quadro assa a tela de novo)."""
        self._geo = None
        self._index.clear()
        self._color.clear()
        self._jobs.clear()

    def lut(self, stage: str) -> np.ndarray:
        if stage not in self._lut:
            self._lut[stage] = self.art.lut(stage)
        return self._lut[stage]

    # ---- quais blocos ------------------------------------------------------------------------------------
    def _blocks(self, x0, y0, x1, y1) -> list[tuple[int, int]]:
        H, W = self._geo.region.shape
        nbx, nby = math.ceil(W / BT), math.ceil(H / BT)
        bx0, by0 = max(0, x0 // BP), max(0, y0 // BP)
        bx1, by1 = min(nbx - 1, (x1 - 1) // BP), min(nby - 1, (y1 - 1) // BP)
        return [(bx, by) for by in range(by0, by1 + 1) for bx in range(bx0, bx1 + 1)]

    def variant(self, key, stage_map) -> tuple:
        """Qual versão do bloco o quadro quer: ("u", estágio) inteiro num estágio, ou ("m", velho, novo, grade)
        quando a mancha da transição passa por ele (grade = estágio de cada tile, 18×18 com a borda)."""
        if stage_map.step == 0:
            return ("u", stage_map.stage)
        tag = (stage_map.stage, stage_map.step, getattr(stage_map, "_sources", None))
        if tag != self._grid_tag:
            self._grid_tag = tag
            self._grid_memo.clear()
        got = self._grid_memo.get(key)
        if got is None:
            bx, by = key
            tx0, ty0 = bx * BT - 1, by * BT - 1
            grid = bytes(stage_map.stage_at(tx0 + i, ty0 + j) for j in range(WT_SIDE) for i in range(WT_SIDE))
            lo, hi = min(grid), max(grid)
            got = ("u", lo) if lo == hi else ("m", lo, hi, grid)
            self._grid_memo[key] = got
        return got

    # ---- trabalho ----------------------------------------------------------------------------------------
    def _step_bake(self, key, budget_s: float) -> bool:
        """Avança o assado do bloco dentro do orçamento (no mínimo 1 faixa). True = terminou."""
        job = self._jobs.get(key)
        if job is None:
            job = self._jobs[key] = bake_block_codes(self._geo, self.art, *key, self.ctx)
            self._bake_started[key] = 0.0
        start = time.perf_counter()
        while True:
            out = next(job)
            if out is not None:
                self._bake_started[key] += time.perf_counter() - start
                self.bake_ms.append(self._bake_started.pop(key) * 1000)
                del self._jobs[key]
                self._index[key] = out
                self._index.move_to_end(key)
                return True
            if time.perf_counter() - start >= budget_s:
                self._bake_started[key] += time.perf_counter() - start
                return False

    def _colorize(self, key, want) -> pygame.Surface:
        code, wt, cover = self._index[key]
        gc = cover & 15
        if want[0] == "u":
            keys = (stage_key(want[1]),)
            pal = self.lut(keys[0])
            pal = np.concatenate([pal, pal])
            codes, newer = code, None
            green = (keys[0] == "green") or None
            mist = (keys[0] == "mist") or None
        else:
            _, lo, hi, grid = want
            keys = (stage_key(lo), stage_key(hi))
            g = np.frombuffer(grid, np.uint8)
            newer = np.repeat(np.repeat((g[wt] != lo).astype(np.uint8), 2, 0), 2, 1)
            codes = code | (newer << 7)
            pal = np.concatenate([self.lut(keys[0]), self.lut(keys[1])])
            nb = newer.astype(bool)
            green = nb if keys[1] == "green" else (~nb if keys[0] == "green" else None)
            mist = nb if keys[1] == "mist" else (~nb if keys[0] == "mist" else None)
        if green is not None:                       # grama: códigos próprios da paleta do Verde
            sel = (gc > 0) if green is True else ((gc > 0) & green)
            cov_code = COVER_BASE + gc
            if newer is not None:
                cov_code = cov_code | (newer << 7)
            codes = np.where(sel, cov_code, codes).astype(np.uint8)
        if mist is None:
            surf8 = pygame.Surface((BP, BP), 0, 8)
            surf8.set_palette([tuple(int(v) for v in c) for c in pal])
            pygame.surfarray.blit_array(surf8, codes.T)
            out = opaque((BP, BP))
            out.blit(surf8, (0, 0))
        else:                                       # umidade da Névoa: escurece a cor que já está no pixel
            rgb = pal[codes]
            damp = ((cover & MIST_DAMP) > 0) & mist
            rgb[damp] = (rgb[damp].astype(int) * np.array(C.GROUND_MIST_DAMP)).astype(np.uint8)
            top = ((cover & MIST_EDGE) > 0) & mist
            rgb[top] = (rgb[top] * C.GROUND_MIST_EDGE).astype(np.uint8)
            out = opaque((BP, BP))
            pygame.surfarray.blit_array(out, rgb.transpose(1, 0, 2))
        self._color[key] = (want, out)
        return out

    def _flat(self, key, want) -> pygame.Surface:
        """Cor chapada (a base da rampa da classe de cada tile) enquanto o bloco não foi assado."""
        bx, by = key
        sub = self.ctx.tcls[by * BT:(by + 1) * BT, bx * BT:(bx + 1) * BT]
        stage = want[1]
        lut = self.lut(stage_key(stage))
        small = opaque((sub.shape[1], sub.shape[0]))
        pygame.surfarray.blit_array(small, lut[sub.astype(int) * 16 + 3].transpose(1, 0, 2))
        out = opaque((BP, BP))
        pygame.transform.scale(small, (sub.shape[1] * T, sub.shape[0] * T), out)
        self._color[key] = (("flat", stage), out)
        return out

    def _evict(self, keep: set) -> None:
        while len(self._index) > C.GROUND_CACHE_BLOCKS:
            victim = next((k for k in self._index if k not in keep), None)
            if victim is None:
                return
            del self._index[victim]
            self._color.pop(victim, None)

    def update(self, cam, view, stage_map) -> None:
        """Faz o trabalho do quadro (no máximo 1 bloco: assar por faixas ou colorir), com prioridade pra tela."""
        x0, y0 = cam
        vw, vh = view
        visible = self._blocks(x0, y0, x0 + vw, y0 + vh)
        m = C.GROUND_PREFETCH_PX
        near = [k for k in self._blocks(x0 - m, y0 - m, x0 + vw + m, y0 + vh + m) if k not in visible]
        cx, cy = x0 + vw / 2, y0 + vh / 2
        dist = lambda k: math.hypot((k[0] + 0.5) * BP - cx, (k[1] + 0.5) * BP - cy)   # noqa: E731
        visible.sort(key=dist)
        near.sort(key=dist)
        if self.sync or not any(k in self._index for k in visible):
            for k in visible:                    # frio (começo do jogo, teleporte) ou print: tudo na hora
                while k not in self._index:
                    self._step_bake(k, 1e9)
                want = self.variant(k, stage_map)
                if self._color.get(k, (None,))[0] != want:
                    self._colorize(k, want)
            self._evict(set(visible) | set(near))
            return
        for group in (visible, near):
            for k in group:                      # 1) falta assar
                if k not in self._index:
                    if self._step_bake(k, C.GROUND_BAKE_MS / 1000):
                        self._evict(set(visible) | set(near))
                    return
            for k in group:                      # 2) assado, mas sem a cor que o quadro quer
                want = self.variant(k, stage_map)
                if self._color.get(k, (None,))[0] != want:
                    self._colorize(k, want)
                    return

    def draw(self, canvas, geo, cam, view, stage_map) -> None:
        self.bind(geo)
        self.update(cam, view, stage_map)
        x0, y0 = cam
        for key in self._blocks(x0, y0, x0 + view[0], y0 + view[1]):
            got = self._color.get(key)
            surf = got[1] if got is not None else self._flat(key, ("u", stage_map.stage))
            canvas.blit(surf, (key[0] * BP - x0, key[1] * BP - y0))
            if key in self._index:
                self._index.move_to_end(key)

    # ---- decoração solta ---------------------------------------------------------------------------------
    def decor_row(self, ty: int) -> list[tuple[int, str, int]]:
        return self._decor.get(ty, [])

    def decor_row_v9(self, ty: int) -> list[Decor9]:
        return self._decor9.get(ty, [])

    @property
    def moss_on(self) -> tuple:
        art = self.art
        return tuple(art.v9.get("moss_on", ())) if art is not None else ()

    def decor_surface(self, name: str, v: int, stage: str, flip: bool = False) -> pygame.Surface | None:
        if flip:
            key = (name, v, stage, True)
            if key not in self._decor_surf:
                base = self.decor_surface(name, v, stage)
                self._decor_surf[key] = None if base is None else pygame.transform.flip(base, True, False)
            return self._decor_surf[key]
        key = (name, v, stage)
        if key not in self._decor_surf:
            art = self.art
            variants = art.decor.get(name) if art else None
            if not variants:
                self._decor_surf[key] = None
                return None
            idx = variants[v % len(variants)]
            info = art.files.get(f"decor_{name}_{v % len(variants)}.png", {})
            region, table = info.get("region", "plateau"), info.get("ramp", "BASE")
            if table.startswith("MOSS"):            # overlay de musgo do Verde (v9): rampa fixa, 0..3 + contorno
                moss = [_hex(c) for c in art.ramps["MOSS"]]
                ramp = moss + [moss[-1]] * (8 - len(moss)) + [OUTLINE, (0, 0, 0)]
            else:
                ramp = art.ramp(table, region, stage) + [OUTLINE, (0, 0, 0)]
            lut = np.zeros((256, 4), np.uint8)
            lut[:len(ramp), :3] = ramp
            lut[:len(ramp), 3] = 255
            lut[9, 3] = 80                         # sombra no chão: preto com alfa fixo
            rgba = lut[idx]
            surf = pygame.Surface((idx.shape[1], idx.shape[0]), pygame.SRCALPHA)
            pygame.surfarray.pixels3d(surf)[...] = rgba[..., :3].transpose(1, 0, 2)
            pygame.surfarray.pixels_alpha(surf)[...] = rgba[..., 3].T
            self._decor_surf[key] = surf
        return self._decor_surf[key]
