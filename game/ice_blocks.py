"""Gelo-portão em blocos (v0.4 Marco 3 · M3.5 · bíblia §12, "Gelos-portão").

Cada gelo-portão é um amontoado de blocos de gelo (receita A, B ou C do `regions_palettes.json`, chaves `blocks` e
`recipes`, arte v9.2 da Designer). O progresso `p` do portão (0 inteiro .. 1 sem gelo, `thaw.gate_progress`) decide o
quadro de cada bloco: antes de `melt[0]` o inteiro (quadro 0), entre `melt[0]` e `melt[1]` os 8 quadros da tira
(do 100% ao 23%) e em `melt[1]` o bloco some. A colisão é o retângulo `collision[quadro]` de cada bloco, relativo ao
pé, no chão (como o `Machine.rect`): quando os retângulos deixam uma fresta da largura da caixa do player, ele passa.

Python puro (numpy só na busca da fresta), sem pygame e sem estado: tudo sai do `p`, que sai do calor.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from game import config as C
from game.geo import hash2

Rect = tuple[float, float, float, float]

CORRIDOR = 4 * C.TILE        # o corredor do portão (a caixa 4×2 da geo): paredes de BEDROCK em |x| > 64 do base_px
DEPTH = 2 * C.TILE


def _load() -> tuple[dict, dict]:
    data = json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8"))
    return data["blocks"], data["recipes"]


BLOCKS, RECIPES = _load()
GIANT_RECIPE = "G"                              # v0.5 M3.6.3: o portão grande (entrada de 8 tiles do bolsão da criatura)
RECIPE_KEYS = tuple(sorted(k for k in RECIPES if k != GIANT_RECIPE))   # ("A", "B", "C"): os sorteados pela seed


@dataclass(frozen=True)
class IceBlock:
    """Um bloco do amontoado no progresso atual. `foot` = onde a âncora cai (px do mundo), `rect` = colisão no chão
    (px do mundo) ou None (o caquinho final da lasca não colide)."""
    gate: int                    # índice do portão (geo.pockets[i]; o portão grande é o len(geo.pockets), ver gate_count)
    key: str                     # "slab_1", "shard_0"... (chave em BLOCKS)
    frame: int                   # 0..7
    foot: tuple[float, float]
    rect: Rect | None

    kind = "ice_block"

    @property
    def base_px(self) -> tuple[float, float]:
        """O pé (y da ordem de desenho), igual ao `Formation.base_px`."""
        return self.foot

    @property
    def sprite(self) -> str:
        return BLOCKS[self.key]["sprite"]

    @property
    def frame_size(self) -> tuple[int, int]:
        return tuple(BLOCKS[self.key]["frame"])

    @property
    def anchor(self) -> tuple[int, int]:
        return tuple(BLOCKS[self.key]["anchor"])


def recipe_for(seed: int, i: int) -> str:
    """A receita do portão `i` (A, B ou C), pela seed do mundo: igual em todo load, sem ir no save."""
    k = int(float(hash2(i, 0, seed + C.THAW_GATE_RECIPE_SALT)) * len(RECIPE_KEYS))
    return RECIPE_KEYS[min(k, len(RECIPE_KEYS) - 1)]


def gate_count(geo) -> int:
    """Quantos gelos-portão o mundo tem: os dos bolsões (geo.pockets) e, por último, o grande da criatura (M3.6.3)."""
    return len(geo.pockets) + (1 if getattr(geo, "giant", None) is not None else 0)


def is_giant_gate(geo, i: int) -> bool:
    return i >= len(geo.pockets)


def gate_base_px(geo, i: int) -> tuple[float, float]:
    """O pé do portão `i`: o `base_px` do gelo-portão do bolsão ou, no grande, o meio da borda de baixo da entrada
    (o vão reto de GIANT_ENTRY_W × POCKET_WALL tiles, `geo.giant.entry_rect`: x, y, largura, altura em tiles)."""
    if not is_giant_gate(geo, i):
        return geo.pockets[i].gate.base_px
    ex, ey, ew, eh = geo.giant.entry_rect
    return (ex + ew / 2) * C.TILE, (ey + eh) * C.TILE


def gate_tiles(geo, i: int) -> list[tuple[int, int]]:
    """Os tiles da caixa do portão `i` (a sombra dele em tiles quando fechado): a caixa 4×2 ou a entrada grande."""
    return list(geo.giant.entry) if is_giant_gate(geo, i) else list(geo.pockets[i].gate.tiles)


def gate_recipe(seed: int, geo, i: int) -> str:
    return GIANT_RECIPE if is_giant_gate(geo, i) else recipe_for(seed, i)


def corridor_of(recipe: str) -> int:
    """Largura do corredor do portão em px: 4 tiles, ou a da receita (`corridor_tiles`: 8 no portão grande)."""
    return RECIPES[recipe].get("corridor_tiles", 4) * C.TILE


def frame_at(melt, p: float) -> int | None:
    """Quadro (0..7) do bloco no progresso `p`, ou None se ele já sumiu (p ≥ melt[1])."""
    t0, t1 = melt
    if p < t0:
        return 0
    if p >= t1:
        return None
    frames = 8
    # + 1e-9: no p exato de uma troca (t0 + (t1 − t0)·k/8) o float às vezes dá k − 0,0000001 e o quadro atrasava
    return min(frames - 1, int((p - t0) / (t1 - t0) * frames + 1e-9))


def blocks_at(base_px: tuple[float, float], recipe: str, p: float, gate: int = 0) -> list[IceBlock]:
    """Os blocos do portão (pé no `base_px` + o (x, y) da receita) que ainda existem no progresso `p`."""
    bx, by = base_px
    out = []
    for b in RECIPES[recipe]["blocks"]:
        k = frame_at(b["melt"], p)
        if k is None:
            continue
        fx, fy = bx + b["x"], by + b["y"]
        r = BLOCKS[b["b"]]["collision"][k]
        rect = None if r is None else (fx + r[0], fy + r[1], r[2], r[3])
        out.append(IceBlock(gate, b["b"], k, (fx, fy), rect))
    return out


def breakpoints(recipe: str) -> list[float]:
    """Os valores de `p` em que algum bloco troca de quadro ou some (entre eles a colisão não muda)."""
    pts = {0.0}
    for b in RECIPES[recipe]["blocks"]:
        t0, t1 = b["melt"]
        pts.update(t0 + (t1 - t0) * k / 8 for k in range(1, 9))
    return sorted(round(min(1.0, v), 6) for v in pts)


AREA = (-96, 96, -DEPTH - 24, 28)     # x0, x1, y0, y1 da busca da fresta, relativo ao base_px


def area_of(corridor: int = CORRIDOR) -> tuple[int, int, int, int]:
    """A AREA pra um corredor de `corridor` px (a mesma folga de 32 px de cada lado das paredes)."""
    half = corridor // 2 + 32
    return -half, half, AREA[2], AREA[3]


def occupancy(rects, walls: bool = True, box: tuple[int, int] = (C.PLAYER_BOX_W, C.PLAYER_BOX_H),
              corridor: int = CORRIDOR) -> np.ndarray:
    """Grade (y, x) da área AREA: True onde o pé do player (px inteiro) não cabe. O player em (px, py) ocupa
    [px − 7, px + 7) × [py − 8, py) e bate num retângulo se cruza ele (o `overlaps` do movimento). `rects` relativos
    ao base_px; `walls` põe as paredes de BEDROCK do corredor (|x| ≥ 64 na faixa −64 ≤ y < 0)."""
    x0, x1, y0, y1 = area_of(corridor)
    pw, ph = box
    occ = np.zeros((y1 - y0, x1 - x0), bool)
    half = corridor // 2
    extra = [(-half - 136, -DEPTH, 136, DEPTH), (half, -DEPTH, 136, DEPTH)] if walls else []
    for rx, ry, rw, rh in list(rects) + extra:
        ax0, ax1 = max(math.floor(rx) - pw // 2 + 1, x0), min(math.ceil(rx + rw) + pw // 2, x1)
        ay0, ay1 = max(math.floor(ry) + 1, y0), min(math.ceil(ry + rh) + ph, y1)
        if ax0 < ax1 and ay0 < ay1:
            occ[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0] = True
    return occ


def passable(rects, walls: bool = True, corridor: int = CORRIDOR) -> bool:
    """A caixa do player vai do avental (y = +26) pro bolsão (y = −87) passando pelo corredor? A mesma busca da
    Designer (tools/sprites/regions_v92.py · passable), pixel a pixel, com flood fill em numpy."""
    free = ~occupancy(rects, walls, corridor=corridor)
    h = free.shape[0]
    seen = np.zeros_like(free)
    seen[h - 2] = free[h - 2]
    while True:
        grow = seen.copy()
        grow[1:] |= seen[:-1]
        grow[:-1] |= seen[1:]
        grow[:, 1:] |= seen[:, :-1]
        grow[:, :-1] |= seen[:, 1:]
        grow &= free
        if grow[1].any():
            return True
        if (grow == seen).all():
            return False
        seen = grow


def path_through(rects, walls: bool = True, corridor: int = CORRIDOR) -> list[tuple[int, int]]:
    """Um caminho (px relativos ao base_px, passo de 1 px) do meio do avental pro bolsão, ou [] se fechado. Busca em
    largura em Python: é pros testes e o smoke (no jogo só o `passable`, que é mais rápido, é usado)."""
    occ = occupancy(rects, walls, corridor=corridor)
    x0, _, y0, _ = area_of(corridor)
    h, w = occ.shape
    start = (h - 2, w // 2)
    if occ[start]:
        return []
    prev = {start: None}
    queue = deque([start])
    while queue:
        y, x = queue.popleft()
        if y == 1:
            path = []
            node = (y, x)
            while node is not None:
                path.append((node[1] + x0, node[0] + y0))
                node = prev[node]
            return path[::-1]
        for ny, nx in ((y - 1, x), (y, x - 1), (y, x + 1), (y + 1, x)):
            if 0 <= ny < h and 0 <= nx < w and not occ[ny, nx] and (ny, nx) not in prev:
                prev[(ny, nx)] = (y, x)
                queue.append((ny, nx))
    return []


def rel_rects(recipe: str, p: float) -> list[Rect]:
    return [b.rect for b in blocks_at((0.0, 0.0), recipe, p) if b.rect is not None]


@lru_cache(maxsize=None)
def opens_at(recipe: str) -> float:
    """O primeiro `p` em que a fresta abre (a caixa do player passa). Exato: só testa os `p` em que a colisão muda."""
    for p in breakpoints(recipe):
        if passable(rel_rects(recipe, p), corridor=corridor_of(recipe)):
            return p
    return 1.0
