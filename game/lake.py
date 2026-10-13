"""Margem orgânica dos lagos (v0.4 Marco 3 · M3.5 · bíblia §12, "Chuva e lagos").

O lago das bacias (M3.3) continua sendo decidido POR TILE no jogo (`World.is_water`: colisão, `can_place`, máquina
submersa). Aqui é só o DESENHO: a silhueta da água segue o `geo.height` contínuo em vez da escadinha do autotile.

Regra (a mesma grade dual dos morros e das marcas d'água secas do chão, `ground.smooth_sample`):
  - campo por tile = `geo.height` nos tiles que podem alagar (chão e rocha pequena, sem veio), e ALTO (9) no resto
    (morro, veio, formação, cratera, destroço...): a água contorna eles em curva, como ilhota;
  - o campo é interpolado entre os CENTROS dos tiles (bilinear com smoothstep) e o pixel é água onde ele fica abaixo
    do `world.water_level`.
  No centro de cada tile o campo vale exatamente o height do tile, então o pixel do centro é água ⇔ `is_water`
  do tile. Entre os centros a margem corre suave.

Visual: o miolo é o tile de água cheia do atlas A2 do estágio (`water_auto_<estágio>`, a mesma textura de hoje,
presa na grade do mundo), com os reflexos andando (desenhados no quadro, presos dentro da água). Na margem, as
cores do próprio atlas: 2 px de sombra azul-escura (margem de cima e dos lados) ou de espuma (margem de baixo)
pra dentro, e 3 px de barranco marrom pra fora, acompanhando a curva.

Desempenho: assado em blocos de LAKE_BLOCK_TILES tiles (códigos sem cor, numpy) e colorido por estágio numa
Surface opaca com colorkey (1 blit por bloco). Refeito só quando o `water_level` muda (poucas vezes por minuto),
quando os tiles do bloco mudam (assinatura, como os morros) ou na troca de estágio (só a cor). Enquanto o bloco
novo não fica pronto, o anterior continua na tela; bloco nunca assado cai no autotile por tile de antes.
"""

from __future__ import annotations

import math
import time
from collections import OrderedDict

import numpy as np
import pygame

from game import autotile
from game import config as C
from game.ground import smooth_sample
from game.surfaces import opaque

T = C.TILE
BT = C.LAKE_BLOCK_TILES
BP = BT * T
PAD = 4                      # px em volta do bloco pras faixas da margem (a mais larga tem 3 px)
HIGH = 9.0                   # campo dos tiles que não alagam (sempre acima de qualquer nível)
KEY = (255, 0, 255)          # colorkey: pixel sem água nem barranco

# códigos do assado (sem cor)
NONE, OUTER, BANK, SHADE1, SHADE2, FOAM1, FOAM2, WATER = range(8)
REFLEX = (170, 214, 230)     # o brilho que anda (o mesmo do autotile por tile)


# ---------------------------------------------------------------------------------------------------------------
# Puro numpy (testável sem pygame)
# ---------------------------------------------------------------------------------------------------------------
def tile_field(height: np.ndarray, floodable: np.ndarray) -> np.ndarray:
    """Campo por tile: o height onde o tile pode alagar, HIGH no resto."""
    return np.where(floodable, np.asarray(height, np.float32), np.float32(HIGH)).astype(np.float32)


def water_mask(field: np.ndarray, i0: int, j0: int, x0: int, y0: int, w: int, h: int, level: float) -> np.ndarray:
    """Máscara (h, w) da água nos px de mundo [x0, x0+w) × [y0, y0+h). `field` é o campo da janela de tiles que
    começa no tile (i0, j0). O px (x, y) cai em u = x/T - 0,5 (o centro do tile tx é exatamente u = tx)."""
    ys, xs = np.mgrid[y0:y0 + h, x0:x0 + w]
    u = xs / T - 0.5 - i0
    v = ys / T - 0.5 - j0
    return smooth_sample(field, u, v) < level


def _sh(a: np.ndarray, dy: int, dx: int, fill: bool) -> np.ndarray:
    """a deslocado: out[y, x] = a[y - dy, x - dx]."""
    out = np.full_like(a, fill)
    hh, ww = a.shape
    out[max(0, dy):min(hh, hh + dy), max(0, dx):min(ww, ww + dx)] = \
        a[max(0, -dy):min(hh, hh - dy), max(0, -dx):min(ww, ww - dx)]
    return out


def _erode(a):
    return a & _sh(a, 1, 0, True) & _sh(a, -1, 0, True) & _sh(a, 0, 1, True) & _sh(a, 0, -1, True)


def _dilate(a):
    return a | _sh(a, 1, 0, False) | _sh(a, -1, 0, False) | _sh(a, 0, 1, False) | _sh(a, 0, -1, False)


def shore_codes(water: np.ndarray) -> np.ndarray:
    """Códigos da margem a partir da máscara: pra dentro 2 px de sombra (ou de espuma, onde a terra está logo
    embaixo: a margem de baixo), pra fora 2 px de barranco escuro e 1 px de barranco claro. O resto da água é
    WATER e o resto da terra é NONE."""
    code = np.zeros(water.shape, np.uint8)
    land = ~water
    land_below = _sh(land, -1, 0, False) | _sh(land, -2, 0, False) | _sh(land, -3, 0, False)
    cur = water
    for k in range(2):
        inner = _erode(cur)
        ring = cur & ~inner
        code[ring] = np.where(land_below[ring], FOAM1 + k, SHADE1 + k)
        cur = inner
    code[cur] = WATER
    grown = water
    for k in range(3):
        ring = _dilate(grown) & ~grown
        code[ring] = OUTER if k == 2 else BANK
        grown = grown | ring
    return code


def bake_block(field: np.ndarray, i0: int, j0: int, bx: int, by: int, level: float) -> np.ndarray | None:
    """Códigos (BP, BP) do bloco (bx, by), ou None se não tem nem água nem barranco. `field` = campo da janela de
    tiles que começa em (i0, j0) e cobre o bloco com 1 tile de folga."""
    if not (field < level).any():
        return None
    x0, y0 = bx * BP - PAD, by * BP - PAD
    water = water_mask(field, i0, j0, x0, y0, BP + 2 * PAD, BP + 2 * PAD, level)
    if not water.any():
        return None
    return shore_codes(water)[PAD:-PAD, PAD:-PAD]


def reflex_spans(code: np.ndarray, bx: int, by: int) -> list[tuple[int, int, int, int, float, int]]:
    """Onde os 2 reflexos de cada tile podem andar: [(x_tile, linha, x_ini, x_fim, h, qual)] em px de mundo, no
    trecho mais comprido de água funda (WATER) daquela linha dentro do tile. As linhas e o `h` são os do autotile
    por tile (`hash01(tx, ty, 5)`), então o lago parece o de antes."""
    from game.world import hash01
    out = []
    deep = code == WATER
    for ly in range(BT):
        for lx in range(BT):
            tile = deep[ly * T:(ly + 1) * T, lx * T:(lx + 1) * T]
            if not tile.any():
                continue
            tx, ty = bx * BT + lx, by * BT + ly
            h = hash01(tx, ty, 5)
            for which, row in enumerate((10 + int(h * 12), 21 + int(h * 5))):
                line = tile[row]
                if not line.any():
                    continue
                best, start = (0, 0), None
                for x in range(T + 1):
                    on = x < T and line[x]
                    if on and start is None:
                        start = x
                    elif not on and start is not None:
                        if x - start > best[1] - best[0]:
                            best = (start, x)
                        start = None
                a, b = best
                if b - a >= 2:
                    out.append((tx * T, ty * T + row, tx * T + a, tx * T + b, h, which))
    return out


# ---------------------------------------------------------------------------------------------------------------
# Cores (do atlas A2 do estágio)
# ---------------------------------------------------------------------------------------------------------------
# px do atlas (64×96, ver game/autotile.py) de onde sai cada cor da margem: a coluna do meio do lago 2×2
ATLAS_PICK = {OUTER: (40, 32), BANK: (40, 33), SHADE1: (40, 35), SHADE2: (40, 36), FOAM1: (40, 92),
              FOAM2: (40, 91)}
FALLBACK_BANK = {OUTER: (94, 69, 53), BANK: (74, 56, 44)}


def shore_colors(atlas: pygame.Surface, palette: dict) -> dict[int, tuple[int, int, int]]:
    """Cor de cada código da margem. Do atlas da Designer; no atlas gerado por código (outro layout) as cores
    vêm da paleta do estágio."""
    out = {}
    for code, (x, y) in ATLAS_PICK.items():
        c = atlas.get_at((x, y))
        out[code] = tuple(c[:3]) if c.a == 255 else None
    if any(v is None for v in out.values()):
        deep = tuple(pygame.Color(palette["water_d"])[:3])
        foam = tuple(pygame.Color(palette["foam"])[:3])
        out = {**FALLBACK_BANK, SHADE1: deep, SHADE2: deep, FOAM1: foam, FOAM2: foam}
    return out


# ---------------------------------------------------------------------------------------------------------------
# Cache e desenho
# ---------------------------------------------------------------------------------------------------------------
FLOODABLE = None   # tabela bytes.translate: tile -> 1 se pode alagar (montada na 1ª vez)


def _floodable_table() -> bytes:
    global FLOODABLE
    if FLOODABLE is None:
        from game.world import LAKE_TILES
        FLOODABLE = bytes(1 if i in LAKE_TILES else 0 for i in range(256))
    return FLOODABLE


class LakeBlocks:
    """Blocos assados da água de UM mundo (a superfície com geo). Uma por Renderer."""

    def __init__(self):
        self.blocks: OrderedDict[tuple[int, int], dict] = OrderedDict()
        self.world_id: int | None = None
        self.sync = False            # True = assa na hora tudo o que a tela pede (prints)
        self.bakes = 0               # quantos assados (pros testes e pro smoke)
        self.bake_ms: list[float] = []
        self._full: dict[str, np.ndarray] = {}      # estágio -> tile de água cheia (T, T, 3)
        self._colors: dict[str, dict] = {}
        self._low: dict[tuple[int, int], float] = {}   # menor height da janela de cada bloco (não muda com o geo)

    def reset(self) -> None:
        self.blocks.clear()
        self._low.clear()

    # ---- janela de tiles ---------------------------------------------------------------------------------
    @staticmethod
    def window(bx: int, by: int) -> tuple[int, int, int, int]:
        return bx * BT - 1, (bx + 1) * BT + 1, by * BT - 1, (by + 1) * BT + 1

    def signature(self, world, bx: int, by: int) -> bytes:
        """Quais tiles da janela podem alagar (minerou um morro na beira, carregou save: muda)."""
        i0, i1, j0, j1 = self.window(bx, by)
        a, b = max(0, i0), min(world.width, i1)
        rows = [bytes(world.tiles[j][a:b]) for j in range(max(0, j0), min(world.height, j1))]
        return b"".join(rows).translate(_floodable_table())

    def field(self, world, bx: int, by: int) -> tuple[np.ndarray, int, int]:
        i0, i1, j0, j1 = self.window(bx, by)
        H, W = world.height, world.width
        out = np.full((j1 - j0, i1 - i0), HIGH, np.float32)
        a, b, c, d = max(0, i0), min(W, i1), max(0, j0), min(H, j1)
        kinds = np.array([world.tiles[j][a:b] for j in range(c, d)], np.uint8).reshape(d - c, b - a)
        flood = np.frombuffer(bytes(kinds.tobytes()).translate(_floodable_table()), np.uint8).reshape(kinds.shape) > 0
        veins = getattr(world, "_vein_tiles", ())
        for (vx, vy) in veins:
            if a <= vx < b and c <= vy < d:
                flood[vy - c, vx - a] = False
        out[c - j0:d - j0, a - i0:b - i0] = tile_field(world.geo.height[c:d, a:b], flood)
        return out, i0, j0

    def low_point(self, world, bx: int, by: int) -> float:
        """O menor height da janela (com folga): bloco com o nível abaixo disso não tem água nem barranco."""
        low = self._low.get((bx, by))
        if low is None:
            i0, i1, j0, j1 = self.window(bx, by)
            win = world.geo.height[max(0, j0):max(0, j1), max(0, i0):max(0, i1)]
            low = self._low[(bx, by)] = float(win.min()) if win.size else HIGH
        return low

    # ---- assar -------------------------------------------------------------------------------------------
    def current(self, world, bx: int, by: int) -> dict | None:
        """A entrada do bloco se está em dia com o nível e os tiles; senão None."""
        entry = self.blocks.get((bx, by))
        if entry is None or entry["level"] != world.water_level:
            return None
        if entry["sig"] != self.signature(world, bx, by):
            return None
        return entry

    def bake(self, world, bx: int, by: int) -> dict:
        start = time.perf_counter()
        field, i0, j0 = self.field(world, bx, by)
        code = bake_block(field, i0, j0, bx, by, world.water_level)
        spans = np.array(reflex_spans(code, bx, by) if code is not None else [], np.float64).reshape(-1, 6)
        entry = {"level": world.water_level, "sig": self.signature(world, bx, by), "code": code,
                 "spans": spans, "surf": None, "tag": None}
        self.blocks[(bx, by)] = entry
        self.blocks.move_to_end((bx, by))
        self.bakes += 1
        self.bake_ms.append((time.perf_counter() - start) * 1000)
        self._evict()
        return entry

    def _evict(self) -> None:
        while len(self.blocks) > C.LAKE_CACHE_BLOCKS:
            self.blocks.popitem(last=False)

    # ---- cor ---------------------------------------------------------------------------------------------
    def full_tile(self, stage: str, atlas: pygame.Surface, tiles: autotile.WaterTiles) -> np.ndarray:
        if stage not in self._full:
            surf = tiles.get(stage, atlas, (autotile.FULL,) * 4)
            self._full[stage] = pygame.surfarray.array3d(surf).transpose(1, 0, 2).copy()
            self._colors[stage] = shore_colors(atlas, C.PALETTES[stage])
        return self._full[stage]

    def colorize(self, entry: dict, bx: int, by: int, stages, art_of) -> pygame.Surface:
        """Surface opaca com colorkey do bloco. `stages` = estágio (art key) do bloco inteiro, ou array (BT, BT)
        de art keys por tile (transição). `art_of(stage)` -> (atlas, WaterTiles)."""
        code = entry["code"]
        rgb = np.empty((BP, BP, 3), np.uint8)
        rgb[...] = KEY
        keys = [stages] if isinstance(stages, str) else sorted(set(np.asarray(stages).ravel().tolist()))
        for st in keys:
            atlas, tiles = art_of(st)
            full = self.full_tile(st, atlas, tiles)
            cols = self._colors[st]
            if isinstance(stages, str):
                where = np.ones((BP, BP), bool)
            else:
                where = np.repeat(np.repeat(np.asarray(stages) == st, T, 0), T, 1)
            tex = np.tile(full, (BT, BT, 1))
            m = where & (code == WATER)
            rgb[m] = tex[m]
            for c, col in cols.items():
                rgb[where & (code == c)] = col
        surf = opaque((BP, BP))
        pygame.surfarray.blit_array(surf, rgb.transpose(1, 0, 2))
        surf.set_colorkey(KEY, pygame.RLEACCEL)
        return surf

    # ---- quadro ------------------------------------------------------------------------------------------
    def visible(self, world, cam, view) -> list[tuple[int, int]]:
        x0, y0 = cam
        nbx, nby = math.ceil(world.width / BT), math.ceil(world.height / BT)
        bx0, by0 = max(0, x0 // BP), max(0, y0 // BP)
        bx1, by1 = min(nbx - 1, (x0 + view[0] - 1) // BP), min(nby - 1, (y0 + view[1] - 1) // BP)
        return [(bx, by) for by in range(by0, by1 + 1) for bx in range(bx0, bx1 + 1)]

    def prepare(self, world, cam, view) -> tuple[dict, set]:
        """Faz o assado do quadro e devolve ({bloco: entrada pra desenhar}, {blocos sem nada: autotile}).
        Prioridade: o que está na tela. Se nenhum bloco com água na tela tem assado (teleporte, load) ou com
        `sync`, assa a tela toda na hora; senão, até LAKE_BAKE_MS por quadro (no mínimo 1 bloco), e de folga
        os blocos a até 1 bloco da tela."""
        if id(world) != self.world_id:
            self.world_id = id(world)
            self.reset()
        level = world.water_level
        vis = [k for k in self.visible(world, cam, view) if self.low_point(world, *k) < level]
        draw, missing = {}, set()
        stale = []
        for k in vis:
            cur = self.current(world, *k)
            if cur is not None:
                draw[k] = cur
            else:
                stale.append(k)
        cold = stale and not draw and not any(k in self.blocks for k in stale)
        budget = math.inf if (self.sync or cold) else C.LAKE_BAKE_MS / 1000
        start = time.perf_counter()
        for k in stale:
            if time.perf_counter() - start < budget or k == stale[0] and not draw:
                draw[k] = self.bake(world, *k)
            elif k in self.blocks:
                draw[k] = self.blocks[k]            # o de antes (nível velho) até ficar pronto
            else:
                missing.add(k)
        if not stale and time.perf_counter() - start < budget:   # folga: a volta da tela
            m = BP
            for k in self.visible(world, (cam[0] - m, cam[1] - m), (view[0] + 2 * m, view[1] + 2 * m)):
                if k in draw or self.low_point(world, *k) >= level:
                    continue
                if self.current(world, *k) is None:
                    self.bake(world, *k)
                    break
        for k in draw:
            self.blocks.move_to_end(k)
        return draw, missing

    def draw(self, canvas, entries: dict, cam, stage_of, art_of, t: float) -> None:
        """Blit dos blocos e os reflexos andando. `stage_of(bx, by)` -> (etiqueta, estágios) do bloco."""
        cx, cy = cam
        vw, vh = canvas.get_size()
        fill = canvas.fill
        for (bx, by), entry in entries.items():
            if entry["code"] is None:
                continue
            tag, stages = stage_of(bx, by)
            if entry["surf"] is None or entry["tag"] != tag:
                entry["surf"] = self.colorize(entry, bx, by, stages, art_of)
                entry["tag"] = tag
            canvas.blit(entry["surf"], (bx * BP - cx, by * BP - cy))
            sp = entry["spans"]
            if not len(sp):
                continue
            # reflexos (os do autotile por tile: 5 px e 4 px andando 5,4 px/s), presos no trecho de água funda
            left, row, a, b, h, which = sp.T
            o = np.floor((t * 5.4 + h * 24) % 24)
            first = which == 0
            x = np.where(first, left + 4 + o, left + 4 + (o + 12) % 22)
            x0 = np.maximum(x, a) - cx
            x1 = np.minimum(x + np.where(first, 5, 4), b) - cx
            y = row - cy
            ok = (x1 > x0) & (x1 > 0) & (x0 < vw) & (y >= 0) & (y < vh)
            for xa, xb, yy in zip(x0[ok].astype(int).tolist(), x1[ok].astype(int).tolist(), y[ok].astype(int).tolist()):
                fill(REFLEX, (xa, yy, xb - xa, 1))
