"""Chão assado da caverna (v0.6 Fundo M2 · bíblia §15).

O motor é o da superfície (game/ground.py: `bake_block_codes`, `decals_for_block`, o cache e o desenho do
`Ground`), só com a arte da caverna no lugar da `RegionArt` (assets/sprites/cave_ground/, aprovada pelo dono no
report reports/design/v06_fundo_m2_biomas/). Diferenças:
- 4 classes (geo.REGION_NAMES: centro, salar, basalto, gelo), sem leito: o `basin` é -1 em tudo;
- 1 paleta só (a caverna não tem estágio): o colorir é 1 LUT, sem a variante "m" da transição;
- sem cobertura (grama, umidade) e sem decoração solta; sem decalque num raio de C.CAVE_DECAL_CLEAR da chegada.
A região de cada pixel é a do `world.cave_region` em (x + dx, y + dy), com o `geo.warp_px` da seed da caverna.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pygame

from game import config as C
from game import geo as geo_mod
from game import ground as G
from game.surfaces import opaque

NAMES = geo_mod.REGION_NAMES
STAGE = "cave"                     # a única chave de estágio do cave_ground_palettes.json


class CaveArt:
    """O que a `RegionArt` tem, só que da caverna. `ok` = tudo carregou."""

    def __init__(self, folder=None):
        folder = folder or C.CAVE_GROUND_DIR
        self.ok = False
        path = folder / "cave_ground_palettes.json"
        if not path.exists():
            return
        self.meta = json.loads(path.read_text(encoding="utf-8"))
        self.ramps = self.meta["ramps"]
        self.decal_p = self.meta["decal_p"]
        self.decal_mix = {k: [(n, w) for n, w in v] for k, v in self.meta["decal_mix"].items()}
        self.v9 = {}                               # sem 3º sorteio
        self.cover = False                         # sem grama/umidade (ground.bake_strip)
        textures = []
        for name in NAMES:
            tex = G.load_indexed(folder / f"ground_cave_{name}.png")
            if tex is None or tex.shape != (G.BP, G.BP):
                return
            textures.append(tex)
        self.tex_stack = np.stack(textures)        # (4, 512, 512)
        self.decals: dict[str, list[np.ndarray]] = {}
        for p in sorted(folder.glob("decal_*.png")):
            name, _ = p.stem.removeprefix("decal_").rsplit("_", 1)
            idx = G.load_indexed(p)
            if idx is not None:
                self.decals.setdefault(name, []).append(idx)
        self.ok = True

    def lut(self) -> np.ndarray:
        """128×3: código (classe·16 + índice) -> cor. 8 = contorno, 9 = preto, como a `RegionArt.lut`."""
        out = np.zeros((G.NEW, 3), np.uint8)
        for c, name in enumerate(NAMES):
            cols = [G._hex(h) for h in self.ramps["BASE"][name][STAGE]] + [G.OUTLINE, (0, 0, 0)]
            out[c * 16:c * 16 + len(cols)] = cols
        return out


class CaveGeo:
    """O mínimo que o `ground.bake_strip` pede de um geo, montado do mundo da caverna."""

    def __init__(self, world):
        self.seed = world.seed
        self.region = world.cave_region
        self.basin = np.full(self.region.shape, -1, np.int16)
        self.formations = []
        self.center = world.center

    def warp(self, px, py):
        return geo_mod.warp_px(self.seed, px, py)


def arrival_skip(center, r: int) -> set[tuple[int, int]]:
    """Tiles sem decalque: um disco de raio `r` em volta da chegada."""
    cx, cy = center
    return {(tx, ty) for ty in range(cy - r, cy + r + 1) for tx in range(cx - r, cx + r + 1)
            if math.hypot(tx - cx, ty - cy) < r}


class CaveGround(G.Ground):
    """O `Ground` da superfície com a arte da caverna: troca só o que dependia de estágio ou da superfície."""

    @property
    def art(self) -> CaveArt | None:
        if self._art is None and self.wanted:
            self._art = CaveArt()
        return self._art if self._art is not None and self._art.ok else None

    def bind(self, geo) -> None:
        if geo is self._geo:
            return
        self._geo = geo
        self.ctx = G.BakeContext(geo)
        self.ctx.skip = arrival_skip(geo.center, C.CAVE_DECAL_CLEAR)
        self._index.clear()
        self._color.clear()
        self._jobs.clear()
        self._grid_memo.clear()
        self._decor, self._decor9 = {}, {}
        self.bake_ms.clear()

    def _pal(self) -> np.ndarray:
        if STAGE not in self._lut:
            self._lut[STAGE] = self.art.lut()
        return self._lut[STAGE]

    def variant(self, key, stage_map) -> tuple:
        return ("u", STAGE)

    def _colorize(self, key, want) -> pygame.Surface:
        code = self._index[key][0]
        pal = np.concatenate([self._pal(), self._pal()])          # 256 entradas, como a superfície
        surf8 = pygame.Surface((G.BP, G.BP), 0, 8)
        surf8.set_palette([tuple(int(v) for v in c) for c in pal])
        pygame.surfarray.blit_array(surf8, code.T)
        out = opaque((G.BP, G.BP))
        out.blit(surf8, (0, 0))
        self._color[key] = (want, out)
        return out

    def draw(self, canvas, geo, cam, view, stage_map=None) -> None:
        self.bind(geo)
        self.update(cam, view, None)
        x0, y0 = cam
        for key in self._blocks(x0, y0, x0 + view[0], y0 + view[1]):
            got = self._color.get(key)
            surf = got[1] if got is not None else self._flat(key, ("u", STAGE))
            canvas.blit(surf, (key[0] * G.BP - x0, key[1] * G.BP - y0))
            if key in self._index:
                self._index.move_to_end(key)

    def _flat(self, key, want) -> pygame.Surface:
        bx, by = key
        sub = self.ctx.tcls[by * G.BT:(by + 1) * G.BT, bx * G.BT:(bx + 1) * G.BT]
        small = opaque((sub.shape[1], sub.shape[0]))
        pygame.surfarray.blit_array(small, self._pal()[sub.astype(int) * 16 + 3].transpose(1, 0, 2))
        out = opaque((G.BP, G.BP))
        pygame.transform.scale(small, (sub.shape[1] * G.T, sub.shape[0] * G.T), out)
        self._color[key] = (("flat", STAGE), out)
        return out
