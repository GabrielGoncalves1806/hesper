"""Derretimento pelo calor (v0.4 Marco 3 · bíblia §12): funções puras dos índices, sem pygame.

O que o calor muda no mapa sai daqui como função do índice `heat` (que vai no save e nunca desce). O GameState
(`_apply_thaw`, game/systems.py) só sobe as etapas e aplica no mapa; no load é só reaplicar.
"""

import bisect

from game import config as C


def gate_stage(heat: float, i: int) -> int:
    """Etapa do gelo-portão `i` (0 = inteiro .. 3 = aberto) pelos marcos C.THAW_GATE_HEAT[i]. O portão 0 abre
    primeiro. Bater no marco já conta (heat == marco sobe a etapa)."""
    marks = C.THAW_GATE_HEAT[min(i, len(C.THAW_GATE_HEAT) - 1)]
    return bisect.bisect_right(marks, heat)
