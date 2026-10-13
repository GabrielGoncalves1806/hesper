"""O calor e a água mudando o mapa (v0.4 Marco 3 · bíblia §12).

Funções puras dos índices (sem pygame e sem estado): o save continua v7, porque tudo o que o Marco 3 muda no mapa
sai daqui a partir de `state.indices` (que só sobem) e é reaplicado no load (`GameState._apply_thaw`).
Cada função é independente das outras.
"""

from __future__ import annotations

import bisect

from game import config as C

DRY = -1.0      # lake_level: seco (nenhum tile tem altura abaixo disso)


GATE_MELTING = 1   # gate_stage: o gelo começou a derreter, mas o corredor ainda está fechado pra caixa do player
GATE_OPEN = 3      # gate_stage: a fresta abriu (o player passa); o resto dos blocos continua derretendo até p = 1


def gate_progress(heat: float, i: int) -> float:
    """Progresso do degelo do gelo-portão `i` (0 = inteiro .. 1 = sem gelo nenhum), linear no calor entre o 1º e o
    último marco de C.THAW_GATE_HEAT[i]. O portão 0 derrete primeiro. Monótona."""
    marks = C.THAW_GATE_HEAT[min(i, len(C.THAW_GATE_HEAT) - 1)]
    lo, hi = marks[0], marks[-1]
    return min(1.0, max(0.0, (heat - lo) / (hi - lo)))


def gate_stage(p: float, opens_at: float) -> int:
    """Etapa derivada do progresso (M3.5): 0 inteiro, GATE_MELTING derretendo e fechado, GATE_OPEN com a fresta
    aberta (`opens_at` = game/ice_blocks.py · opens_at da receita do portão). A etapa 2 do M3.2 não existe mais."""
    if p >= opens_at:
        return GATE_OPEN
    return GATE_MELTING if p > 0 else 0


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
