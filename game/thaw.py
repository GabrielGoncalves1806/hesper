"""Derretimento e água (v0.4 Marco 3 · bíblia §12): funções puras dos índices, sem pygame.

O que o calor e a água mudam no mapa sai daqui como função dos índices (que vão no save e nunca descem). O GameState
(`_apply_thaw`, game/systems.py) só sobe as etapas e aplica no mapa; no load é só reaplicar.
"""

import bisect

from game import config as C

DRY = -1.0      # lake_level: seco (nenhum tile tem altura abaixo disso)


def gate_stage(heat: float, i: int) -> int:
    """Etapa do gelo-portão `i` (0 = inteiro .. 3 = aberto) pelos marcos C.THAW_GATE_HEAT[i]. O portão 0 abre
    primeiro. Bater no marco já conta (heat == marco sobe a etapa)."""
    marks = C.THAW_GATE_HEAT[min(i, len(C.THAW_GATE_HEAT) - 1)]
    return bisect.bisect_right(marks, heat)


def lake_level(water: float) -> float:
    """Altura (na escala do geo.height) até onde a água das bacias sobe com o índice de água (ppm).

    Abaixo de C.LAKE_WATER[0] é seco (DRY). Em C.LAKE_WATER[k] é exatamente C.GEO_LEVELS[k] (L1, L2, L3); entre
    eles interpola linear, e acima do último fica em L3. Monótona: mais água, nível igual ou mais alto."""
    marks, levels = C.LAKE_WATER, C.GEO_LEVELS
    if water < marks[0]:
        return DRY
    for k in range(len(marks) - 1):
        if water < marks[k + 1]:
            u = (water - marks[k]) / (marks[k + 1] - marks[k])
            return levels[k] + (levels[k + 1] - levels[k]) * u
    return levels[-1]
