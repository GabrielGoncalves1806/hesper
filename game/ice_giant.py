"""Gelo gigante da criatura (v0.5 Marco 3 · M3.6.2 · bíblia §13): a "respirada" e os estilhaços em volta.

A geografia (bolsão, pegada, variação sorteada pela seed) mora em `game/geo.py` (`Geo.giant`, `IceCreature`). Aqui ficam
só as regras do desenho que o contrato da Designer pede (`regions_palettes.json → formations.ice_giant`):

    respirar   parado no quadro 0; a cada 9–14 s (sorteio) toca a tira de 8 quadros uma vez a 6 fps e volta pro 0
    estilhaços blocos de gelo do portão (mesmos PNG, quadro = tamanho) espalhados em volta, sem colisão

Python puro (sem pygame): o render só pede o quadro (`Breath.frame`) e os blocos (`shards`).
"""

from __future__ import annotations

import bisect
import json

from game import config as C
from game.geo import hash2
from game.ice_blocks import IceBlock


def _spec() -> dict:
    return json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8"))["formations"]["ice_giant"]


SPEC = _spec()
FRAMES = int(SPEC["anim"]["frames"])
FPS = float(SPEC["anim"]["fps"])
PLAY_TIME = FRAMES / FPS                      # s que a tira leva pra tocar uma vez


class Breath:
    """Linha do tempo da respirada: o tempo parado de cada ciclo (C.GIANT_BREATH_PAUSE) sai do hash da seed e do número
    do ciclo, então a mesma seed respira nos mesmos instantes. `frame(t)` devolve o quadro (0 = parado) no tempo `t`."""

    def __init__(self, seed: int):
        self.seed = seed
        self._starts: list[float] = []        # instante em que o ciclo k começa a tocar a tira

    def _extend(self, t: float) -> None:
        lo, hi = C.GIANT_BREATH_PAUSE
        while not self._starts or self._starts[-1] + PLAY_TIME < t:
            k = len(self._starts)
            prev_end = self._starts[-1] + PLAY_TIME if self._starts else 0.0
            self._starts.append(prev_end + lo + (hi - lo) * float(hash2(k, 3, self.seed + C.GIANT_SALT)))

    def frame(self, t: float) -> int:
        if t < 0:
            return 0
        self._extend(t)
        i = bisect.bisect_right(self._starts, t) - 1
        if i < 0:
            return 0
        k = int((t - self._starts[i]) * FPS)
        return k if k < FRAMES else 0


def shards(giant) -> list[IceBlock]:
    """Os estilhaços em volta (contrato: `shards`, x e y do pé relativos à âncora do gigante = o `base_px`), como
    `IceBlock` sem colisão (rect None): entram na ordem de desenho pelo pé e no raio-x como os blocos do portão."""
    bx, by = giant.base_px
    out = []
    for s in SPEC["shards"]:
        key = s["sprite"].removeprefix("ice_block_").removesuffix(".png")
        out.append(IceBlock(-1, key, int(s["frame"]), (bx + s["x"], by + s["y"]), None))
    return out
