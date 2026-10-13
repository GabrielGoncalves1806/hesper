"""Morros orgânicos da superfície (v0.4 Marco 2 · trilha C, bíblia §11). A caverna não usa isto.

Porta a receita da Designer (tools/sprites/regions_scene.py · `hill_layers`, aprovada no report
reports/design/regioes/, v8.0) pro jogo:

MORROS (grade dual). A colisão continua a de hoje, por tile. Só o DESENHO muda:
    1. o campo "tem parede" é interpolado (bilinear com smoothstep) entre os CENTROS dos tiles e cortado em
       0,5, com um ruído somado. A borda reta cai exatamente na borda do tile (a colisão bate), a escada
       diagonal vira diagonal, o canto convexo arredonda e o tile sozinho vira seixo;
    2. o topo é desenhado 24 px acima (igual à parede de hoje) com a textura hill_top.png (512×512) e a FACE é
       a silhueta extrudada 24 px pra baixo, com a textura hill_face.png (512×24). Contorno e brilho na borda;
    3. os minérios de hoje (ore_*.png) vão por cima do topo, recortados pela silhueta.

    Assar isso é caro (numpy em ~70 mil px), então os morros são ASSADOS EM BLOCOS de 8×8 tiles e guardados.
    Cada bloco vira uma tira por LINHA de tiles (topo + face daquela linha), porque o desenho intercala os
    morros com os objetos linha por linha (render.build_draw_list): o player logo acima de um morro fica atrás
    do topo, logo abaixo fica na frente da face. A tira de cada linha é exatamente o que a parede daquela linha
    desenhava antes, só que com a borda curva.

    Quando um tile é minerado, só os blocos que enxergam aquele tile (o dele e, na beira, o vizinho) são
    re-assados: cada bloco guarda uma "assinatura" das paredes em volta (bytes dos tiles) e compara a cada frame.
    A cor sai de uma rampa por região e estágio (regions_palettes.json → ramps.HILL): na transição de estágio o
    bloco só é recolorido (a geometria fica).

FORMAÇÕES (C3): sprites indexados (form_<kind>.png, ice_gate_<n>.png) recoloridos pela rampa da região no
estágio (regions_palettes.json → formations[kind].ramp/region) e desenhados como objetos ordenados pelo pé, a
`anchor` do sprite caindo no `Formation.base_px` (centro de baixo da pegada). A pegada é C.FORMATION (geo.py).

Sem pygame só a parte pura (`bake_block`, `hill_field`): testada em tests/test_hills.py.
"""

from __future__ import annotations

import json
import zlib
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pygame

from game import config as C
from game import geo

T = C.TILE
LIFT = C.WALL_LIFT
FACE = C.HILL_FACE
TEX = 512                                  # textura do topo e da face: emenda a cada 512 px
REGIONS = geo.REGION_NAMES                                  # PLATEAU, SALAR, BASALT, FROST (0..3)
STAGE_KEYS = ("storm", "arid", "mist", "green")             # estágio 1..4 -> rampa
OUTLINE = (0x1B, 0x16, 0x30)                                # índice 8 dos sprites indexados
SHADOW_ALPHA = 80                                           # índice 9: sombra preta com alfa fixo
TRANSPARENT = 255
MARGIN = 8                                                  # px: o ruído empurra a borda até ~6 px
BEDROCK_SHADE = 1 - 110 / 255                               # a borda do mapa é mais escura (igual ao bedrock_shade)
OUTSIDE = C.BEDROCK                                         # fora do mapa conta como borda (igual ao World.get)


# ---------------------------------------------------------------------------
# Arte: arquivos indexados + rampas do regions_palettes.json
# ---------------------------------------------------------------------------
def region_file(name: str) -> Path | None:
    """Caminho do arquivo da arte das regiões (assets/sprites/regions/), ou None se não existir."""
    path = C.REGIONS_DIR / name
    return path if path.exists() else None


_PALETTES: dict | None = None


def palettes() -> dict:
    """O regions_palettes.json (rampas, pegadas e âncoras das formações). Vazio se o arquivo sumir."""
    global _PALETTES
    if _PALETTES is None:
        path = region_file("regions_palettes.json")
        _PALETTES = json.loads(path.read_text()) if path else {}
    return _PALETTES


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ramp(table: str, region: str, stage: str) -> np.ndarray | None:
    """10×3 uint8: as 8 cores da rampa (tabela/região/estágio), o contorno (8) e a sombra (9, preto).
    Tabela composta "A+B" (v9.1, fumarolas: "HILL+VENT"): os 10 da A e, nos índices 10.., as cores da B."""
    if "+" in table:
        first, extra = table.split("+", 1)
        base = ramp(first, region, stage)
        try:
            more = palettes()["ramps"][extra][region][stage]
        except KeyError:
            return None
        return None if base is None else np.concatenate([base, np.array([_rgb(c) for c in more], np.uint8)])
    try:
        cols = palettes()["ramps"][table][region][stage]
    except KeyError:
        return None
    return np.array([_rgb(c) for c in cols] + [OUTLINE, (0, 0, 0)], dtype=np.uint8)


_INDEXED: dict[str, np.ndarray | None] = {}


def read_png_indices(data: bytes) -> np.ndarray:
    """Índices (altura, largura) de um PNG indexado de 8 bits sem entrelaçamento (o que a Designer gera).

    O pygame converte PNG indexado pra RGBA ao carregar e o índice se perde (e é ele que dá a cor do estágio),
    então o arquivo é lido aqui: junta os IDAT, descomprime e desfaz o filtro de cada linha."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("não é PNG")
    pos, idat, w = 8, [], 0
    while pos < len(data):
        n = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h = int.from_bytes(body[0:4], "big"), int.from_bytes(body[4:8], "big")
            depth, color, interlace = body[8], body[9], body[12]
            if depth != 8 or color != 3 or interlace:
                raise ValueError(f"PNG não é indexado de 8 bits (bits {depth}, cor {color})")
        elif kind == b"IDAT":
            idat.append(body)
        pos += 12 + n
    raw = np.frombuffer(zlib.decompress(b"".join(idat)), np.uint8).reshape(h, w + 1)
    out = np.zeros((h, w), np.uint8)
    prev = np.zeros(w, np.uint8)
    for y in range(h):
        filt, line = raw[y, 0], raw[y, 1:]
        if filt == 0:
            cur = line.copy()
        elif filt == 1:                                  # Sub: soma acumulada (o uint8 já dá a volta em 256)
            cur = np.cumsum(line, dtype=np.uint8)
        elif filt == 2:                                  # Up
            cur = line + prev
        else:                                            # Average / Paeth: raros, pixel a pixel
            cur = np.zeros(w, np.uint8)
            for x in range(w):
                a = int(cur[x - 1]) if x else 0
                b = int(prev[x])
                c = int(prev[x - 1]) if x else 0
                if filt == 3:
                    pred = (a + b) // 2
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
                cur[x] = (int(line[x]) + pred) & 0xFF
        out[y] = prev = cur
    return out


def load_indexed(name: str) -> np.ndarray | None:
    """Índices (altura, largura) de um PNG indexado da arte das regiões, ou None se não existir."""
    if name not in _INDEXED:
        path = region_file(name)
        arr = None
        if path is not None:
            try:
                arr = read_png_indices(path.read_bytes())
            except (OSError, ValueError, zlib.error) as err:
                print(f"[hills] não consegui ler {path.name}: {err}")
        _INDEXED[name] = arr
    return _INDEXED[name]


def colorize(idx: np.ndarray, rmp: np.ndarray) -> np.ndarray:
    """Índice -> RGBA (255 transparente, 9 = sombra com alfa fixo). Igual ao regions_core.colorize."""
    out = np.zeros(idx.shape + (4,), np.uint8)
    solid = idx != TRANSPARENT
    out[..., :3] = rmp[np.where(solid, idx, 0)]
    out[..., 3] = np.where(solid, 255, 0)
    out[..., 3][idx == 9] = SHADOW_ALPHA
    return out


def rgba_surface(rgba: np.ndarray) -> pygame.Surface:
    """Surface SRCALPHA a partir de um array (altura, largura, 4)."""
    h, w = rgba.shape[:2]
    surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(), (w, h), "RGBA")
    return surf.convert_alpha() if pygame.display.get_surface() else surf.copy()


# ---------------------------------------------------------------------------
# Ruído (determinístico, igual ao regions_core: mesmo hash), periódico em 512 px
# ---------------------------------------------------------------------------
_M32 = np.uint64(0xFFFFFFFF)


def hash2(x, y, s: int) -> np.ndarray:
    with np.errstate(over="ignore"):
        x = np.asarray(x, dtype=np.int64).astype(np.uint64)
        y = np.asarray(y, dtype=np.int64).astype(np.uint64)
        n = (x * np.uint64(374761393) + y * np.uint64(668265263) + np.uint64(s) * np.uint64(2246822519)
             + np.uint64(0x9E3779B9)) & _M32
        n = ((n ^ (n >> np.uint64(13))) * np.uint64(1274126177)) & _M32
        n = n ^ (n >> np.uint64(16))
        n = (n * np.uint64(2246822519)) & _M32
        n = n ^ (n >> np.uint64(15))
        return n.astype(np.float64) / 4294967296.0


def vnoise(xs, ys, cell: float, seed: int, period: int) -> np.ndarray:
    fx, fy = np.asarray(xs, float) / cell, np.asarray(ys, float) / cell
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a = hash2(ix % period, iy % period, seed)
    b = hash2((ix + 1) % period, iy % period, seed)
    c = hash2(ix % period, (iy + 1) % period, seed)
    d = hash2((ix + 1) % period, (iy + 1) % period, seed)
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty


_EDGE_NOISE: np.ndarray | None = None


def edge_noise() -> np.ndarray:
    """Ruído que treme a borda da silhueta (512×512, emenda). É o `0,42·(fbm−0,5) + 0,10·(vnoise−0,5)` do
    regions_scene, com células de 16/8/4 px (em vez de 15) pra emendar em 512: calculado uma vez só."""
    global _EDGE_NOISE
    if _EDGE_NOISE is None:
        ys, xs = np.mgrid[0:TEX, 0:TEX]
        fbm = sum(0.5 ** o * vnoise(xs, ys, 16 / 2 ** o, 517 + 101 * o, 32 * 2 ** o) for o in range(3)) / 1.75
        _EDGE_NOISE = (0.42 * (fbm - 0.5) + 0.10 * (vnoise(xs, ys, 4, 519, 128) - 0.5)).astype(np.float32)
    return _EDGE_NOISE


def _sm(t):
    return t * t * (3 - 2 * t)


def _shift(a: np.ndarray, dy: int, dx: int, fill=False) -> np.ndarray:
    """out[y, x] = a[y - dy, x - dx] (fora = fill)."""
    out = np.full_like(a, fill)
    h, w = a.shape[:2]
    out[max(0, dy):min(h, h + dy), max(0, dx):min(w, w + dx)] = \
        a[max(0, -dy):min(h, h - dy), max(0, -dx):min(w, w - dx)]
    return out


# ---------------------------------------------------------------------------
# O bloco: geometria (pura) e cor
# ---------------------------------------------------------------------------
def block_pixels(bx: int, by: int, block: int = C.HILL_BLOCK) -> tuple[int, int, int, int]:
    """(x0, y0, largura, altura) em px do mundo do que o bloco desenha: as colunas dele e, na vertical, do topo
    da 1ª linha (24 px acima) até a face da última (que acaba na borda de baixo do tile), com MARGIN px de folga
    em cima e embaixo (o ruído empurra a silhueta um pouco pra fora da linha)."""
    bp = block * T
    return bx * bp, by * bp - LIFT - MARGIN, bp, bp + LIFT + 2 * MARGIN


def tile_window(tiles, width: int, height: int, i0: int, i1: int, j0: int, j1: int) -> np.ndarray:
    """Tipos dos tiles [j0, j1) × [i0, i1) como array uint8, com a borda (BEDROCK) fora do mapa."""
    out = np.full((j1 - j0, i1 - i0), OUTSIDE, np.uint8)
    a, b = max(0, i0), min(width, i1)
    if a < b:
        for j in range(max(0, j0), min(height, j1)):
            out[j - j0, a - i0:b - i0] = tiles[j][a:b]
    return out


def window_bounds(bx: int, by: int, block: int = C.HILL_BLOCK) -> tuple[int, int, int, int]:
    """Tiles (i0, i1, j0, j1) que influenciam o bloco: o bloco + 1 de cada lado e +2 em cima e embaixo (a
    linha dona de um pixel na beira olha a linha vizinha)."""
    return bx * block - 1, (bx + 1) * block + 1, by * block - 2, (by + 1) * block + 2


def bake_block(kinds: np.ndarray, regions: np.ndarray, bx: int, by: int, top_tex: np.ndarray,
               face_tex: np.ndarray, noise: np.ndarray, block: int = C.HILL_BLOCK) -> dict:
    """Geometria de um bloco (sem pygame, sem cor).

    kinds/regions: tipos e regiões dos tiles da `window_bounds` do bloco (mesma forma).
    Devolve um dict com, por pixel do retângulo `block_pixels`:
        idx    índice da rampa (0..8) ou 255 (vazio)
        reg    região (0..3)
        row    linha de tiles dona do pixel (-1 = não é deste bloco)
        top    True no topo (False na face)
        col    coluna de tiles do pixel
    e `ore`: [(recurso, x, y)] dos minérios a desenhar (px relativos ao retângulo)."""
    i0, i1, j0, j1 = window_bounds(bx, by, block)
    x0, y0, w, h = block_pixels(bx, by, block)
    # 1 px de folga em volta pros testes de vizinho (borda de cima, de lado)
    xs = np.arange(x0 - 1, x0 + w + 1)
    ys = np.arange(y0 - 1, y0 + h + 1)
    wall = np.isin(kinds, list(C.WALL_TILES)).astype(np.float32)
    # campo da grade dual: centros dos tiles, smoothstep; o topo está 24 px acima do tile
    u = xs / T - 0.5
    v = (ys + LIFT) / T - 0.5
    iu, jv = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = _sm(u - iu)[None, :], _sm(v - jv)[:, None]
    ci, rj = iu - i0, jv - j0                      # índices na janela
    ci = np.clip(ci, 0, wall.shape[1] - 2)
    rj = np.clip(rj, 0, wall.shape[0] - 2)
    a = wall[rj][:, ci]
    b = wall[rj][:, ci + 1]
    c = wall[rj + 1][:, ci]
    d = wall[rj + 1][:, ci + 1]
    f = a * (1 - fu) * (1 - fv) + b * fu * (1 - fv) + c * (1 - fu) * fv + d * fu * fv
    f += noise[(ys % TEX)[:, None], (xs % TEX)[None, :]]
    M = f > 0.5
    # face: a silhueta extrudada pra baixo (distância até o último pixel de topo em cima, na mesma coluna)
    yy = np.broadcast_to(np.arange(len(ys))[:, None], M.shape)
    last = np.maximum.accumulate(np.where(M, yy, -10_000), axis=0)
    dist = yy - last
    F = ~M & (dist >= 1) & (dist <= FACE)
    depth = np.where(F, dist - 1, 0)
    # Linha dona do pixel de topo: o topo do tile ty fica em [ty·32−24, ty·32+8). Onde o ruído empurrou a
    # silhueta pra uma linha sem parede (a linha de cima ou a de baixo), o pixel fica com a vizinha que tem.
    row_top = np.broadcast_to((ys + LIFT) // T, (len(xs), len(ys))).T
    cols = np.broadcast_to(xs // T, M.shape)
    has = wall.astype(bool)

    def wall_at(r):
        rr, cc = np.clip(r - j0, 0, has.shape[0] - 1), np.clip(cols - i0, 0, has.shape[1] - 1)
        return has[rr, cc]

    here = wall_at(row_top)
    row_top = np.where(here, row_top, np.where(wall_at(row_top - 1), row_top - 1,
                                               np.where(wall_at(row_top + 1), row_top + 1, row_top)))
    # a face fica com a linha do pixel de topo de onde ela pende
    row_last = np.take_along_axis(row_top, np.clip(last, 0, len(ys) - 1), axis=0)
    row = np.where(M, row_top, np.where(F, row_last, -1))
    tcol = np.broadcast_to((xs // T)[None, :], M.shape)
    # índices: textura do topo e da face, contorno e brilho (receita do regions_scene.hill_layers)
    top = top_tex[((ys + LIFT) % TEX)[:, None], (xs % TEX)[None, :]].copy()
    up_open = M & ~_shift(M, 1, 0)
    top[up_open] = 8
    top[M & ~up_open & _shift(up_open, 1, 0)] = 5
    left_open = M & ~_shift(M, 0, 1)
    right_open = M & ~_shift(M, 0, -1)
    top[left_open | right_open] = 8
    top[M & _shift(left_open, 0, 1) & ~left_open] = 4
    fidx = face_tex[np.clip(depth, 0, FACE - 1), (xs % TEX)[None, :]].copy()
    fl = F & ~_shift(F, 0, 1) & ~_shift(M, 0, 1)
    fr = F & ~_shift(F, 0, -1) & ~_shift(M, 0, -1)
    fidx[fl | fr] = 8
    fidx[F & (depth == FACE - 1)] = 8
    idx = np.where(M, top, np.where(F, fidx, TRANSPARENT)).astype(np.uint8)
    # tira a folga e fica só com as linhas deste bloco
    sl = (slice(1, 1 + h), slice(1, 1 + w))
    idx, row, M, tcol = idx[sl], row[sl], M[sl], tcol[sl]
    r0 = by * block
    mine = (row >= r0) & (row < r0 + block)
    idx = np.where(mine, idx, TRANSPARENT).astype(np.uint8)
    row = np.where(mine, row, -1)
    rr = np.clip(row - j0, 0, regions.shape[0] - 1)
    cc = np.clip(tcol - i0, 0, regions.shape[1] - 1)
    reg = regions[rr, cc]
    kind = kinds[rr, cc]
    ore = []
    for j in range(max(r0, j0), min(r0 + block, j1)):
        for i in range(bx * block, (bx + 1) * block):
            res = C.ORE_TILES.get(int(kinds[j - j0, i - i0]))
            if res:
                ore.append((res, i * T - x0, j * T - LIFT - y0))
    return {"idx": idx, "reg": reg, "row": row, "top": M & mine, "col": tcol, "kind": kind, "ore": ore,
            "x0": x0, "y0": y0, "r0": r0}


def hill_lut(stage: str) -> np.ndarray | None:
    """LUT (80×3): código = região·10 + índice (0..39); +40 = a mesma cor escurecida (topo da borda do mapa)."""
    rows = []
    for region in REGIONS:
        r = ramp("HILL", region, stage)
        if r is None:
            return None
        rows.append(r)
    lut = np.concatenate(rows)
    return np.concatenate([lut, (lut * BEDROCK_SHADE).astype(np.uint8)])


def colorize_block(blk: dict, luts: dict[int, np.ndarray], stages: np.ndarray | int,
                   ore_rgba: dict[str, np.ndarray]) -> np.ndarray:
    """RGBA do bloco. `stages`: estágio (1..4) do bloco inteiro ou por tile (array da janela do bloco)."""
    idx = blk["idx"]
    solid = idx != TRANSPARENT
    code = blk["reg"].astype(np.int32) * 10 + np.where(solid, idx, 0)
    code += np.where(blk["top"] & (blk["kind"] == C.BEDROCK), 40, 0)
    out = np.zeros(idx.shape + (4,), np.uint8)
    if isinstance(stages, (int, np.integer)):
        out[..., :3] = luts[int(stages)][code]
    else:
        i0, _, j0, _ = window_bounds(blk["x0"] // (C.HILL_BLOCK * T), blk["r0"] // C.HILL_BLOCK)
        rr = np.clip(blk["row"] - j0, 0, stages.shape[0] - 1)
        cc = np.clip(blk["col"] - i0, 0, stages.shape[1] - 1)
        per_px = stages[rr, cc]
        for st in np.unique(per_px[solid]) if solid.any() else ():
            m = per_px == st
            out[m, :3] = luts[int(st)][code[m]]
    out[..., 3] = np.where(solid, 255, 0)
    # minério por cima do topo (o sprite de hoje recortado pela silhueta)
    hgt, wid = idx.shape
    for res, ox, oy in blk["ore"]:
        spr = ore_rgba.get(res)
        if spr is None:
            continue
        sh, sw = spr.shape[:2]
        ya, yb, xa, xb = max(0, oy), min(hgt, oy + sh), max(0, ox), min(wid, ox + sw)
        if ya >= yb or xa >= xb:
            continue
        piece = spr[ya - oy:yb - oy, xa - ox:xb - ox]
        m = (piece[..., 3] > 0) & blk["top"][ya:yb, xa:xb]
        out[ya:yb, xa:xb][m] = piece[m]
    return out


# ---------------------------------------------------------------------------
# Cache dos blocos (o que o render usa)
# ---------------------------------------------------------------------------
WALL_TABLE = bytes(k if k in C.WALL_TILES else 0 for k in range(256))   # assinatura: só o que é parede importa


class HillBlocks:
    """Blocos assados dos morros de UM mundo (a superfície). `strips(bx, by)` devolve {linha: (surf, x, y)}.

    - geometria: refeita quando a assinatura das paredes em volta muda (minerou, carregou save);
    - cor: refeita quando o estágio dos tiles do bloco muda (transição);
    - LRU com teto (C.HILL_CACHE_BLOCKS)."""

    def __init__(self, ore_rgba: dict[str, np.ndarray]):
        self.ore_rgba = ore_rgba
        self.top_tex = load_indexed("hill_top.png")
        self.face_tex = load_indexed("hill_face.png")
        self.luts: dict[int, np.ndarray] = {}
        for n, key in enumerate(STAGE_KEYS, start=1):
            lut = hill_lut(key)
            if lut is not None:
                self.luts[n] = lut
        self.ok = self.top_tex is not None and self.face_tex is not None and len(self.luts) == len(STAGE_KEYS)
        self.blocks: OrderedDict[tuple[int, int], dict] = OrderedDict()
        self.world_id: int | None = None
        self.bakes = 0                       # quantos assados (geometria) já fez: pros testes e pro smoke
        self.recolors = 0

    def reset(self) -> None:
        self.blocks.clear()

    def signature(self, world, bx: int, by: int) -> bytes:
        i0, i1, j0, j1 = window_bounds(bx, by)
        if 0 <= i0 and i1 <= world.width and 0 <= j0 and j1 <= world.height:
            return b"".join(bytes(world.tiles[j][i0:i1]) for j in range(j0, j1)).translate(WALL_TABLE)
        return tile_window(world.tiles, world.width, world.height, i0, i1, j0, j1).tobytes().translate(WALL_TABLE)

    def cached(self, world, bx: int, by: int) -> bool:
        """O bloco está assado e em dia (sem precisar refazer a geometria)?"""
        entry = self.blocks.get((bx, by))
        return entry is not None and entry["sig"] == self.signature(world, bx, by)

    def strips(self, world, regions, stage_sig, bx: int, by: int) -> dict:
        """Tiras do bloco (assando/recolorindo se preciso). `regions(i0, i1, j0, j1)` -> regiões da janela;
        `stage_sig` = (assinatura, estágio inteiro ou array por tile da janela)."""
        if id(world) != self.world_id:
            self.world_id = id(world)
            self.blocks.clear()
        key = (bx, by)
        sig = self.signature(world, bx, by)
        entry = self.blocks.get(key)
        if entry is None or entry["sig"] != sig:
            i0, i1, j0, j1 = window_bounds(bx, by)
            kinds = np.frombuffer(sig, np.uint8).reshape(j1 - j0, i1 - i0)
            entry = {"sig": sig, "geo": bake_block(kinds, regions(i0, i1, j0, j1), bx, by, self.top_tex,
                                                    self.face_tex, edge_noise()),
                     "stage": None, "strips": {}}
            self.blocks[key] = entry
            self.bakes += 1
        self.blocks.move_to_end(key)
        while len(self.blocks) > C.HILL_CACHE_BLOCKS:
            self.blocks.popitem(last=False)
        tag, stages = stage_sig
        if entry["stage"] != tag:
            entry["stage"] = tag
            entry["strips"] = self._cut(entry["geo"], stages)
            self.recolors += 1
        return entry["strips"]

    def _cut(self, blk: dict, stages) -> dict:
        """Recolore e corta em uma tira por linha (recortada no retângulo que tem pixel)."""
        rgba = colorize_block(blk, self.luts, stages, self.ore_rgba)
        rows = blk["row"]
        out = {}
        for r in np.unique(rows[rows >= 0]):
            m = rows == r
            ys = np.nonzero(m.any(axis=1))[0]
            xs = np.nonzero(m.any(axis=0))[0]
            ya, yb, xa, xb = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
            piece = rgba[ya:yb, xa:xb].copy()
            piece[..., 3] = np.where(m[ya:yb, xa:xb], piece[..., 3], 0)
            out[int(r)] = (rgba_surface(piece), blk["x0"] + int(xa), blk["y0"] + int(ya))
        return out


# ---------------------------------------------------------------------------
# Formações fixas (v0.4 Marco 2 · C3): sprites indexados recoloridos pela rampa da região no estágio
# ---------------------------------------------------------------------------
def formation_key(kind: str, variant: int = 0) -> str:
    """Chave no regions_palettes.json: o gelo-portão tem uma por etapa (ice_gate_0..2)."""
    return f"ice_gate_{variant}" if kind == "ice_gate" else kind


def formation_file(kind: str, variant: int = 0) -> str:
    """form_<kind>.png; o gelo-portão é ice_gate_<etapa>.png; a fumarola (M3.1) é form_<kind>_dormant/_active.png
    (variant 0 = dormente, 1 = acordada)."""
    if kind.startswith("vent_"):
        return f"form_{kind}_{'active' if variant else 'dormant'}.png"
    return f"ice_gate_{variant}.png" if kind == "ice_gate" else f"form_{kind}.png"


def formation_ramp(kind: str, variant: int = 0) -> tuple[str, str]:
    """(tabela, região) da rampa do sprite, pelo regions_palettes.json (hoodoo e arco: SAND do planalto)."""
    info = palettes().get("formations", {}).get(formation_key(kind, variant), {})
    return info.get("ramp", "HILL"), info.get("region", "plateau")


class FormationSprites:
    """Superfície de cada formação por estágio (1..4), recolorida pela rampa (PNG indexado). Se o PNG não for
    indexado, usa as cores dele; se faltar, um bloco de pedra do tamanho da pegada (nada quebra sem asset)."""

    def __init__(self):
        self._cache: dict[tuple, pygame.Surface] = {}
        self._masks: dict[int, pygame.mask.Mask] = {}

    def surface(self, formation, stage: int, variant: int | None = None) -> pygame.Surface:
        """`variant` (opcional) passa por cima do `formation.variant`: a fumarola acordada (M3.1) vem do estado,
        não da formação (a geo é dividida entre os estados da mesma seed)."""
        variant = getattr(formation, "variant", 0) if variant is None else variant
        name = formation_file(formation.kind, variant)
        stage = max(1, min(len(STAGE_KEYS), stage))
        key = (name, stage)
        if key not in self._cache:
            surf = None
            idx = load_indexed(name)
            rmp = ramp(*formation_ramp(formation.kind, variant), STAGE_KEYS[stage - 1])
            if idx is not None and rmp is not None:
                surf = rgba_surface(colorize(idx, rmp))
            else:
                path = region_file(name)
                if path is not None:
                    try:
                        surf = pygame.image.load(str(path))
                        surf = surf.convert_alpha() if pygame.display.get_surface() else surf
                    except pygame.error:
                        surf = None
            self._cache[key] = surf if surf is not None else self._fallback(formation)
        return self._cache[key]

    @staticmethod
    def _fallback(formation) -> pygame.Surface:
        w, h = formation.size
        surf = pygame.Surface((w * T, h * T + 2 * T), pygame.SRCALPHA)
        surf.fill((74, 52, 46), (2, 0, w * T - 4, h * T + 2 * T - 2))
        surf.fill((110, 80, 66), (2, 0, w * T - 4, 6))
        pygame.draw.rect(surf, OUTLINE, surf.get_rect(), 1)
        return surf

    def anchor(self, formation, surf: pygame.Surface) -> tuple[int, int]:
        """Pixel do sprite que cai no `base_px` (o `anchor` da formação; sem ele, o meio da borda de baixo)."""
        ax, ay = getattr(formation, "anchor", None) or (surf.get_width() // 2, surf.get_height())
        if not (0 <= ax <= surf.get_width() and 0 <= ay <= surf.get_height()):
            return surf.get_width() // 2, surf.get_height()
        return ax, ay

    def placement(self, formation, stage: int, variant: int | None = None) -> tuple[pygame.Surface, int, int]:
        """(sprite, x, y) do canto de cima-esquerda do sprite no mundo (px): a âncora cai no base_px."""
        surf = self.surface(formation, stage, variant)
        ax, ay = self.anchor(formation, surf)
        bx, by = formation.base_px
        return surf, round(bx - ax), round(by - ay)

    def mask(self, surf: pygame.Surface) -> pygame.mask.Mask:
        """Silhueta sólida (sem a sombra de alfa 80): pra saber se a formação cobre o player."""
        key = id(surf)
        if key not in self._masks:
            self._masks[key] = pygame.mask.from_surface(surf, 127)
        return self._masks[key]


def foot_tile(formation) -> tuple[int, int]:
    """Um tile da linha de baixo da pegada (pro estágio da transição): o do meio."""
    w, h = formation.size
    return formation.tx + w // 2, formation.ty + h - 1


# ---------------------------------------------------------------------------
# Cratera de impacto (v0.4 Marco 2 · C4): crater_impact_0..4 (a tampa de gelo baixando) + crater_ejecta
# ---------------------------------------------------------------------------
CRATER_ANCHOR = (84, 70)                       # centro dos 3×3 no sprite 168×150 (o JSON manda, este é o padrão)


def crater_palette(stage: str) -> np.ndarray | None:
    """21×3: 0..9 planalto (BASE, com contorno e sombra), 10..17 gelo (ICE), 18..20 metal da rampa (METAL)."""
    terra = ramp("BASE", "plateau", stage)
    ice = ramp("ICE", "frost", stage)
    metal = palettes().get("ramps", {}).get("METAL")
    if terra is None or ice is None or not metal:
        return None
    return np.concatenate([terra, ice[:8], np.array([_rgb(c) for c in metal], np.uint8)])


def crater_anchor(level: int) -> tuple[int, int]:
    info = palettes().get("formations", {}).get(f"crater_impact_{level}", {})
    return tuple(info.get("anchor", CRATER_ANCHOR))


class CraterSprites:
    """A cratera de impacto na etapa do gelo (0 tampada .. 4 vazia) e o manto de ejeção, por estágio (1..4).
    Sem a arte: None (o render volta pro crater_ramp de antes)."""

    def __init__(self):
        self._cache: dict[tuple, pygame.Surface | None] = {}

    def _get(self, name: str, stage: int, palette) -> pygame.Surface | None:
        stage = max(1, min(len(STAGE_KEYS), stage))
        key = (name, stage)
        if key not in self._cache:
            idx = load_indexed(name)
            rmp = palette(STAGE_KEYS[stage - 1])
            self._cache[key] = None if idx is None or rmp is None else rgba_surface(colorize(idx, rmp))
        return self._cache[key]

    def crater(self, level: int, stage: int) -> pygame.Surface | None:
        level = max(0, min(C.CRATER_ICE_STAGES, level))
        return self._get(f"crater_impact_{level}.png", stage, crater_palette)

    def ejecta(self, stage: int) -> pygame.Surface | None:
        return self._get("crater_ejecta.png", stage, lambda st: ramp("BASE", "plateau", st))
