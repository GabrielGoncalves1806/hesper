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
    """Quantas desse tipo o jogador já fabricou (item) ou construiu (máquina, v0.5 M1). Só cresce: desmontar não
    desconta."""
    return state.crafted[kind]


def placed_near_base(state: GameState, kind: str) -> bool:
    bx, by = C.BASE_CENTER
    return any(m.kind == kind and math.hypot((m.tx + 0.5) * C.TILE - bx, (m.ty + 0.5) * C.TILE - by) <= NEAR_BASE
               for m in state.surface.machines)


def visited_cave(state: GameState) -> bool:
    """Já desceu pela rampa? (a caverna só é criada na primeira descida e fica no save)"""
    return "cave" in state.layers


def crater_open(state: GameState) -> bool:
    """O gelo da cratera já derreteu? (v0.4: nasce tampada e derrete com o calor, Marco 3; o F4 de debug abre na
    hora). Quem já desceu, já abriu."""
    return not state.crater_frozen or visited_cave(state)


MAGMATITE_HINT = "Os sensores detectaram calor a oeste. Talvez exista algo por lá pra gerar calor."


def found_magmatite(state: GameState) -> bool:
    """Já minerou magmatita? (ou já fabricou um Aquecedor: o save de antes da magmatita não regride)"""
    return state.mined_total.get("magmatite", 0) >= 1 or crafted(state, "heater") >= 1


@dataclass(frozen=True)
class Objective:
    text: str
    done: Callable[[GameState], bool]
    # Opcional: (recurso, meta). Mostra um contador "(3/10)" usando o TOTAL minerado.
    counter: tuple[str, int] | None = None
    # Opcional: dica que aparece como aviso no topo quando o objetivo vira o atual (App.update_objective_hint).
    hint: str | None = None

    def label(self, state: GameState) -> str:
        if self.counter is None:
            return self.text
        resource, goal = self.counter
        return f"{self.text} ({min(goal, state.mined_total[resource])}/{goal})"


OBJECTIVES = [
    Objective("Minere ferro", lambda s: s.mined_total["iron"] >= 10, ("iron", 10)),
    Objective("Abra o fabricador na base [E]", lambda s: s.fabricator_opened),
    # v0.5 M1: máquina só sai do construtor (item da hotbar, 1ª receita do fabricador)
    Objective("Fabrique o construtor", lambda s: crafted(s, "constructor") >= 1 or s.has_constructor),
    Objective("Minere silício", lambda s: s.mined_total["silicon"] >= 4, ("silicon", 4)),
    Objective("Construa um Gerador de O₂ [E com o construtor]", lambda s: crafted(s, "o2") >= 1),
    Objective("Construa o gerador perto da base", lambda s: placed_near_base(s, "o2")),
    Objective("Construa um baú", lambda s: any(crafted(s, k) >= 1 for k in C.CHEST_KINDS)),
    # v0.4 Marco 3 (ordem decidida pelo dono): o calor só sai do aquecedor, que libera no Ti 500. Então o trio
    # Derretedor -> Ti 500 -> Aquecedor vem antes da cratera.
    Objective("Minere gelo e construa um Derretedor", lambda s: crafted(s, "melter") >= 1),
    Objective("Chegue a Ti 500", lambda s: s.ti >= 500),
    # v0.4 (bíblia §12 "Magmatita"): o Aquecedor custa magmatita, que só nasce em volta das fumarolas do basalto.
    # Quem já fabricou um Aquecedor (save de antes dela) não volta pra cá.
    Objective("Encontre magmatita no basalto (oeste)", found_magmatite, hint=MAGMATITE_HINT),
    Objective("Construa um Aquecedor", lambda s: crafted(s, "heater") >= 1),
    # v0.3 Marco 2: a caverna é onde se minera de verdade (escura: lanterna + luminárias)
    # v0.4 Marco 3: a cratera nasce coberta de gelo e derrete com o calor (game/thaw.py, marcos THAW_CRATER_HEAT)
    Objective("Derreta o gelo da cratera", crater_open),
    Objective("Desça na caverna pela cratera [E]", visited_cave),
    Objective("Construa uma luminária", lambda s: s.lamps_placed >= 1),
    # v0.3 Marco 3: os destroços do deserto (o mais perto, a ~30 tiles, tem o diagrama do tanque de O₂)
    Objective("Ache um destroço", lambda s: len(s.wrecks_visited) >= 1),
    # energia (bíblia §8): o aquecedor é o ponto em que os 5 kW da cápsula começam a apertar
    Objective("Construa um painel solar", lambda s: crafted(s, "solar") >= 1),
    # v0.3: os terminais ficam na caverna (a 19, 31 e 45 tiles da rampa)
    Objective("Leia um terminal", lambda s: len(s.logs_read) >= 1),
    # v0.4 Marco 1: o jogo começa na tempestade de poeira; o Árido é o céu limpando
    Objective("Limpe o céu (Árido)", lambda s: s.stage >= C.ARID_STAGE),
    Objective("Chegue ao estágio Úmido", lambda s: s.stage >= C.MIST_STAGE),
    # v0.6 Fundo M5: a drill pede circuito (cobre do salar → Fundição → fios → Bancada T2). Os três guiam a cadeia.
    Objective("Construa a Bancada T2", lambda s: crafted(s, "workbench") >= 1),
    Objective("Construa uma Fundição", lambda s: crafted(s, C.SMELTER) >= 1),
    Objective("Fabrique um circuito na Bancada T2", lambda s: crafted(s, "circuit") >= 1),
    Objective("Construa uma drill num veio", lambda s: s.drills_placed >= 1),
    Objective("Colete minério de uma drill", lambda s: sum(s.drill_collected.values()) >= 1),
    # drones (bíblia §8, Marco 3): a estação busca o minério das drills sozinha
    Objective("Construa uma estação de drones", lambda s: crafted(s, "drone_station") >= 1),
    # a estação vem vazia: o drone é um item fabricado à parte e colocado pelo painel dela (E)
    Objective("Fabrique um drone", lambda s: crafted(s, "drone") >= 1 or s.drones_docked >= 1),
    Objective("Coloque o drone na estação [E]", lambda s: s.drones_docked >= 1),
    Objective("Receba uma entrega de drone", lambda s: s.drone_deliveries >= 1),
    # v0.6 Fundo M5: o tanque pede circuito e o diagrama dele só se lê na Bancada T2, então os dois descem pra cá
    Objective("Ache e leia o diagrama do tanque de O₂", lambda s: "o2_tank" in s.blueprints),
    Objective("Fabrique e equipe o tanque de O₂", lambda s: "o2_tank" in s.equipped_ever),
    Objective("Construa uma máquina nv.2", lambda s: any(crafted(s, k) >= 1 for k in ("o2_t2", "melter_t2", "heater_t2"))),
    Objective("Deixe o planeta verde", lambda s: s.stage >= C.GREEN_STAGE),
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
        self.hinted: set[int] = set()            # objetivos que já mostraram a dica (Objective.hint) nesta sessão
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

    def take_hint(self) -> str | None:
        """A dica do objetivo atual, uma vez só por objetivo (o App mostra como aviso no topo); None se não tem."""
        if self.shown is None or self.shown in self.hinted or OBJECTIVES[self.shown].hint is None:
            return None
        self.hinted.add(self.shown)
        return OBJECTIVES[self.shown].hint

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
