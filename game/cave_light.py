"""Luz por região da caverna (v0.6 Fundo M2 · bíblia §15).

Cada região tem um ambiente (o que se enxerga fora dos focos, o `ambient` do Lighting.apply), a cor e a
intensidade da lanterna do capacete (cave_light.json, aprovado pelo dono no report do M2). O que vale no quadro é
a média das regiões num quadrado em volta do player (C.CAVE_LIGHT_SAMPLE_R), suavizada no tempo
(C.CAVE_LIGHT_TAU): na fronteira a luz mistura e ao cruzar não estala. Entrar na caverna (ou trocar de mundo)
pega o valor na hora. A cor do capacete é arredondada de 8 em 8 (o Lighting guarda uma textura por cor).
"""

from __future__ import annotations

import json
import math

import numpy as np

from game import config as C
from game import geo as geo_mod
from game.lighting import WARM_WHITE

NAMES = geo_mod.REGION_NAMES
DEFAULT = {"ambient": (0, 0, 0), "helmet": WARM_WHITE, "helmet_intensity": 1.0}
QUANT = 8


def load(path=None) -> list[dict]:
    path = path or C.CAVE_GROUND_DIR / "cave_light.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [{"ambient": tuple(int(v) for v in data[n]["ambient"]),
                 "helmet": tuple(int(v) for v in data[n]["helmet"]),
                 "helmet_intensity": float(data[n]["helmet_intensity"])} for n in NAMES]
    except (OSError, KeyError, ValueError, TypeError):
        return [dict(DEFAULT) for _ in NAMES]


def region_weights(region: np.ndarray, tx: int, ty: int, r: int = C.CAVE_LIGHT_SAMPLE_R) -> np.ndarray:
    """Fração de cada região no quadrado (2r+1)² em volta do tile (cortado na borda do mapa)."""
    h, w = region.shape
    win = region[max(0, ty - r):min(h, ty + r + 1), max(0, tx - r):min(w, tx + r + 1)]
    counts = np.bincount(win.ravel(), minlength=len(NAMES))[:len(NAMES)].astype(np.float64)
    total = counts.sum()
    return counts / total if total else np.eye(len(NAMES))[0]


def blend(table: list[dict], weights: np.ndarray) -> np.ndarray:
    """(7,): ambiente RGB, capacete RGB, intensidade do capacete."""
    vecs = np.array([[*e["ambient"], *e["helmet"], e["helmet_intensity"]] for e in table], np.float64)
    return weights @ vecs


class CaveLight:
    def __init__(self, table: list[dict] | None = None):
        self.table = table if table is not None else load()
        self.value: np.ndarray | None = None
        self._t: float | None = None
        self._world = None

    def update(self, world, tx: int, ty: int, t: float) -> None:
        region = world.cave_region
        weights = np.eye(len(NAMES))[0] if region is None else region_weights(region, tx, ty)
        target = blend(self.table, weights)
        if self.value is None or world is not self._world or self._t is None:
            self.value = target
        else:
            dt = min(max(t - self._t, 0.0), 0.25)
            self.value = self.value + (target - self.value) * (1 - math.exp(-dt / C.CAVE_LIGHT_TAU))
        self._t, self._world = t, world

    @property
    def ambient(self) -> tuple[int, int, int]:
        return tuple(int(round(v)) for v in self.value[:3])

    @property
    def helmet(self) -> tuple[int, int, int]:
        return tuple(min(255, int(round(v / QUANT)) * QUANT) for v in self.value[3:6])

    @property
    def helmet_intensity(self) -> float:
        return float(self.value[6])
