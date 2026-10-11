"""Objetivos na tela (tutorial leve): a lista de metas e como saber se já foram cumpridas.

Tudo aqui é Python puro (nada de pygame), testado em tests/test_objectives.py.

Ideia central: cada objetivo é só um texto + uma função que olha o `GameState` e responde
"já cumpriu?". O objetivo ATUAL é sempre o primeiro que ainda não foi cumprido. Por isso,
se o jogador fizer as coisas fora de ordem, os objetivos que ele já cumpriu são pulados sozinhos.

Todas as condições olham pra coisas que só crescem (total minerado, Ti, estágio, logs lidos...),
então um objetivo cumprido nunca "descumpre".
"""

import math
from dataclasses import dataclass
from typing import Callable

from game import config as C
from game.systems import GameState

NEAR_BASE = 8 * C.TILE      # "perto da base": até 8 tiles do centro da zona de O₂
FLASH_TIME = 1.4            # segundos que o objetivo concluído fica na tela (verde, com ✓)


def crafted(state: GameState, kind: str) -> int:
    """Quantas máquinas desse tipo o jogador já fabricou (guardadas + colocadas no mundo)."""
    return state.machines_owned[kind] + sum(1 for m in state.machines if m.kind == kind)


def placed_near_base(state: GameState, kind: str) -> bool:
    bx, by = C.BASE_CENTER
    return any(m.kind == kind and math.hypot((m.tx + 0.5) * C.TILE - bx, (m.ty + 0.5) * C.TILE - by) <= NEAR_BASE
               for m in state.machines)


@dataclass(frozen=True)
class Objective:
    text: str
    done: Callable[[GameState], bool]
    # Opcional: (recurso, meta). Mostra um contador "(3/10)" usando o TOTAL minerado.
    counter: tuple[str, int] | None = None

    def label(self, state: GameState) -> str:
        if self.counter is None:
            return self.text
        resource, goal = self.counter
        return f"{self.text} ({min(goal, state.mined_total[resource])}/{goal})"


OBJECTIVES = [
    Objective("Minere ferro", lambda s: s.mined_total["iron"] >= 10, ("iron", 10)),
    Objective("Minere silício", lambda s: s.mined_total["silicon"] >= 4, ("silicon", 4)),
    Objective("Abra o fabricador na base [E]", lambda s: s.fabricator_opened),
    Objective("Fabrique um Gerador de O2", lambda s: crafted(s, "o2") >= 1),
    Objective("Coloque o gerador perto da base", lambda s: placed_near_base(s, "o2")),
    Objective("Minere gelo e fabrique um Derretedor", lambda s: crafted(s, "melter") >= 1),
    Objective("Chegue a Ti 500", lambda s: s.ti >= 500),
    Objective("Fabrique um Aquecedor", lambda s: crafted(s, "heater") >= 1),
    # energia (bíblia §8): o aquecedor é o ponto em que os 5 kW da cápsula começam a apertar
    Objective("Fabrique um painel solar", lambda s: crafted(s, "solar") >= 1),
    Objective("Leia um terminal", lambda s: len(s.logs_read) >= 1),
    Objective("Chegue ao estágio Névoa", lambda s: s.stage >= 2),
    Objective("Coloque uma drill num veio", lambda s: s.drills_placed >= 1),
    Objective("Colete minério de uma drill", lambda s: sum(s.drill_collected.values()) >= 1),
    Objective("Fabrique uma máquina nv.2", lambda s: any(crafted(s, k) >= 1 for k in ("o2_t2", "melter_t2", "heater_t2"))),
    Objective("Deixe o planeta verde", lambda s: s.stage >= 3),
]


def current_index(state: GameState) -> int | None:
    """Índice do primeiro objetivo ainda não cumprido, ou None se acabou tudo."""
    for i, objective in enumerate(OBJECTIVES):
        if not objective.done(state):
            return i
    return None


@dataclass
class ObjectiveLine:
    """Uma linha pronta pra desenhar."""
    text: str
    style: str      # "done" (acabou de cumprir: verde com ✓), "current" ou "next" (esmaecido)


class ObjectiveTracker:
    """Guarda o que está na tela e cuida do feedback de 'concluído'.

    O App chama `update(state, dt)` todo frame e desenha `lines()`.
    Quando o objetivo atual é cumprido, ele fica alguns instantes em verde com ✓
    (embaixo já aparece o próximo) e depois a lista anda.
    """

    def __init__(self, state: GameState):
        self.shown = current_index(state)       # objetivo atual na tela
        self.flash: str | None = None            # texto do objetivo que acabou de ser cumprido
        self.flash_time = 0.0

    def update(self, state: GameState, dt: float) -> None:
        if self.flash is not None:
            self.flash_time -= dt
            if self.flash_time <= 0:
                self.flash = None
        now = current_index(state)
        if self.shown is not None and now != self.shown:
            # cumpriu o que estava na tela (talvez vários de uma vez): pisca o que estava na tela
            self.flash = OBJECTIVES[self.shown].label(state)
            self.flash_time = FLASH_TIME
        self.shown = now

    @property
    def visible(self) -> bool:
        return self.shown is not None or self.flash is not None

    def lines(self, state: GameState) -> list[ObjectiveLine]:
        """No máximo 2 linhas: [concluído + atual] durante o feedback, senão [atual + próximo]."""
        lines = []
        if self.flash is not None:
            lines.append(ObjectiveLine(self.flash, "done"))
        if self.shown is not None:
            lines.append(ObjectiveLine(OBJECTIVES[self.shown].label(state), "current"))
            if self.flash is None:
                # próximo ainda não cumprido (pula os que o jogador já fez fora de ordem)
                nxt = next((o for o in OBJECTIVES[self.shown + 1:] if not o.done(state)), None)
                if nxt is not None:
                    lines.append(ObjectiveLine(nxt.label(state), "next"))
        return lines
