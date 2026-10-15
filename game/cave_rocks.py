"""Blocos de rocha da caverna com borda orgânica (v0.5 Marco 3 · M3.4, bíblia §11).

Só o DESENHO muda: tiles, forma, colisão e minérios da caverna (game/world.py) são os de sempre. Os blocos de rocha
ganham as bordas curvas dos morros da superfície, importando a geometria pura do game/hills.py (`bake_block`,
`window_bounds`, `tile_window`, `edge_noise`, `colorize_block`...) sem copiar nada. O que é da caverna fica aqui:

- COR: uma rampa só (sem regiões nem estágios), montada com as cores que a rocha da caverna já tinha
  (C.PALETTES do estágio névoa = wall_mist_*.png / wall_face_mist.png). Ver `cave_ramp`.
- CACHE: blocos de 8×8 tiles assados e cortados em uma tira por linha de tiles (entra no `build_draw_list` no lugar
  das paredes da linha, como na superfície). Cada bloco guarda a assinatura das paredes em volta: minerou um tile,
  só os blocos que enxergam ele (1, ou 2 na beira) são re-assados.
- LUZ: nada a fazer aqui. A escuridão (game/lighting.py) e o brilho dos minérios são passes por cima do quadro
  inteiro, depois das paredes; a rocha nova recebe luz e sombra igual à de antes.
"""

from __future__ import annotations

from collections import OrderedDict

import numpy as np

from game import config as C
from game import hills

TABLE = bytes(k if k in C.WALL_TILES else 0 for k in range(256))   # assinatura: só o que é parede importa
STAGES = tuple(range(1, len(hills.STAGE_KEYS) + 1))


def cave_ramp(pal: dict | None = None) -> np.ndarray:
    """Rampa da rocha da caverna (10×3), montada com as cores existentes (C.PALETTES do estágio névoa): 0..4 vão da
    base escura da face ao tom médio do topo (o 4 é o que mais aparece na textura), 5 e 7 são o claro do brilho de
    borda e dos pontinhos, 6 o segundo tom, 8 o contorno (a base da face mais escura). O 3 é a média de `rock_dot`
    e `rock`, o único tom que não existia."""
    pal = pal or C.PALETTES[C.STAGE_ART[C.STAGES[C.MIST_STAGE - 1].key]]
    c = lambda k: np.array(hills._rgb(pal[k]), np.int32)           # noqa: E731
    mid = (c("rock_dot") + c("rock")) // 2
    cols = [c("face_dark"), c("face"), c("rock_dot"), mid, c("rock"), c("rock_hi"), c("rock2"), c("rock_hi")]
    outline = (c("face_dark") * 7) // 10
    return np.array(cols + [outline, np.zeros(3, np.int32)], dtype=np.uint8)


def cave_luts() -> dict[int, np.ndarray]:
    """LUT (80×3) no formato do `hills.colorize_block`: a rampa da caverna em cada região (v0.6 Fundo M1: tingida
    pela C.CAVE_REGION_TINT, provisório até a arte do M2) e, +40, a versão escurecida (topo da borda do mapa)."""
    base = cave_ramp().astype(np.float32)
    rows = []
    for region in range(len(hills.REGIONS)):
        r, g, b, a = C.CAVE_REGION_TINT.get(region, (0, 0, 0, 0))
        k = a / 255
        rows.append((base * (1 - k) + np.array([r, g, b], np.float32) * k).astype(np.uint8))
    lut = np.concatenate(rows)
    lut = np.concatenate([lut, (lut * hills.BEDROCK_SHADE).astype(np.uint8)])
    return {n: lut for n in STAGES}


def region_window(region: np.ndarray, i0: int, i1: int, j0: int, j1: int) -> np.ndarray:
    """Regiões da janela [j0, j1) × [i0, i1); fora do mapa repete a borda."""
    h, w = region.shape
    ys = np.clip(np.arange(j0, j1), 0, h - 1)
    xs = np.clip(np.arange(i0, i1), 0, w - 1)
    return region[np.ix_(ys, xs)]


class CaveRocks:
    """Blocos assados da rocha de UMA caverna. `strips(world, bx, by)` devolve {linha: (surf, x, y)}."""

    def __init__(self, ore_rgba: dict[str, np.ndarray]):
        self.ore_rgba = ore_rgba
        self.top_tex = hills.load_indexed("hill_top.png")
        self.face_tex = hills.load_indexed("hill_face.png")
        self.luts = cave_luts()
        self.ok = self.top_tex is not None and self.face_tex is not None
        self.blocks: OrderedDict[tuple[int, int], dict] = OrderedDict()
        self.world_id: int | None = None
        self.bakes = 0                       # quantos assados já fez: pros testes e pro smoke

    def signature(self, world, bx: int, by: int) -> bytes:
        i0, i1, j0, j1 = hills.window_bounds(bx, by)
        if 0 <= i0 and i1 <= world.width and 0 <= j0 and j1 <= world.height:
            return b"".join(bytes(world.tiles[j][i0:i1]) for j in range(j0, j1)).translate(TABLE)
        return hills.tile_window(world.tiles, world.width, world.height, i0, i1, j0, j1).tobytes().translate(TABLE)

    def cached(self, world, bx: int, by: int) -> bool:
        entry = self.blocks.get((bx, by))
        return entry is not None and entry["sig"] == self.signature(world, bx, by)

    def strips(self, world, bx: int, by: int) -> dict:
        if id(world) != self.world_id:
            self.world_id = id(world)
            self.blocks.clear()
        key = (bx, by)
        sig = self.signature(world, bx, by)
        entry = self.blocks.get(key)
        if entry is None or entry["sig"] != sig:
            i0, i1, j0, j1 = hills.window_bounds(bx, by)
            kinds = np.frombuffer(sig, np.uint8).reshape(j1 - j0, i1 - i0)
            regions = (region_window(world.cave_region, i0, i1, j0, j1)
                       if world.cave_region is not None else np.zeros(kinds.shape, np.uint8))
            geo = hills.bake_block(kinds, regions, bx, by, self.top_tex, self.face_tex, hills.edge_noise(),
                                   height=world.height)
            entry = {"sig": sig, "strips": self._cut(geo)}
            self.blocks[key] = entry
            self.bakes += 1
        self.blocks.move_to_end(key)
        while len(self.blocks) > C.HILL_CACHE_BLOCKS:
            self.blocks.popitem(last=False)
        return entry["strips"]

    def _cut(self, blk: dict) -> dict:
        """Colore e corta em uma tira por linha (recortada no retângulo que tem pixel)."""
        rgba = hills.colorize_block(blk, self.luts, STAGES[0], self.ore_rgba)
        rows = blk["row"]
        out = {}
        for r in np.unique(rows[rows >= 0]):
            m = rows == r
            ys = np.nonzero(m.any(axis=1))[0]
            xs = np.nonzero(m.any(axis=0))[0]
            ya, yb, xa, xb = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
            piece = rgba[ya:yb, xa:xb].copy()
            piece[..., 3] = np.where(m[ya:yb, xa:xb], piece[..., 3], 0)
            out[int(r)] = (hills.rgba_surface(piece), blk["x0"] + int(xa), blk["y0"] + int(ya))
        return out
