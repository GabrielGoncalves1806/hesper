"""O calor e a água mudando o mapa (v0.4 Marco 3 · bíblia §12).

Funções puras dos índices (sem pygame e sem estado): o save continua v7, porque tudo o que o Marco 3 muda no mapa
sai daqui a partir de `state.indices` (que só sobem) e é reaplicado no load (`GameState._apply_thaw`).
Cada função é independente das outras.
"""

from __future__ import annotations

import bisect

from game import config as C


# ---------------------------------------------------------------------------------------------------------------
# M3.1 · cratera: a tampa de gelo baixa uma etapa em cada marco de calor
# ---------------------------------------------------------------------------------------------------------------
def crater_stage(heat: float) -> int:
    """Etapa da tampa de gelo da cratera (0 = tampada .. C.CRATER_ICE_STAGES = vazia) pro calor `heat` (pK):
    sobe 1 em cada marco de C.THAW_CRATER_HEAT (o marco conta: no calor exato do 1º marco já é a etapa 1)."""
    return min(C.CRATER_ICE_STAGES, bisect.bisect_right(C.THAW_CRATER_HEAT, heat))


# ---------------------------------------------------------------------------------------------------------------
# M3.1 · fumarolas do basalto: cada uma acorda num limiar próprio, entre a etapa 1 e a 4 da cratera
# ---------------------------------------------------------------------------------------------------------------
_GOLDEN = 0.6180339887498949


def fumarole_threshold(i: int) -> float:
    """Calor (pK) em que a fumarola `i` (a ordem de `geo.vents`) acorda. O "sorteio" é a sequência de ouro do
    índice: fica espalhado por igual entre C.THAW_FUMAROLE_HEAT[0] e [1], sem dois limiares colados, e sai igual
    em qualquer mundo (não depende da seed, então o load reconstrói sem guardar nada)."""
    lo, hi = C.THAW_FUMAROLE_HEAT
    frac = (0.5 + i * _GOLDEN) % 1.0
    return lo + (hi - lo) * frac


def fumarole_active(heat: float, i: int) -> bool:
    """A fumarola `i` está acordada (sprite ativo e fumaça) com esse calor? Monótona: com mais calor, nunca dorme."""
    return heat >= fumarole_threshold(i)
