"""Textinhos que sobem e somem ("+15 FERRO", "+O2"), sem encavalar (Python puro, testado em
tests/test_floaters.py; quem desenha é o ui.py).

Dois truques pra eles não nascerem um em cima do outro:
  1. **Mesclar**: o mesmo texto de recurso ("+N FERRO", mesma cor) nascendo quase no mesmo ponto
     enquanto o anterior ainda é novinho (< MERGE_AGE) vira um só, com os números somados
     ("+15 FERRO" + "+15 FERRO" = "+30 FERRO") e a vida renovada. Texto sem número ("+O2") só
     renova a vida.
  2. **Faixas**: se já tem floater vivo nascido perto, o novo vai pra primeira faixa livre acima
     dele. A faixa é um deslocamento em pixels da TELA (UI), não do mundo: com qualquer zoom a
     distância entre as linhas é a altura da letra (que não muda com o zoom).
"""

import re
from dataclasses import dataclass

LIFE = 1.2            # segundos na tela
RISE = 22.0           # px do mundo por segundo
MERGE_AGE = 0.6       # só mescla com um floater de até 0,6 s de idade
MERGE_DIST = 12.0     # px do mundo: "o mesmo ponto"
NEAR_X, NEAR_Y = 56.0, 40.0   # px do mundo: nascidos tão perto assim dividem a pilha de faixas
LANE_PX = 12          # px da UI (metade da tela) entre uma faixa e a de cima

_AMOUNT = re.compile(r"^\+(\d+) (.+)$")


@dataclass
class Floater:
    text: str
    x: float              # onde nasceu (mundo)
    y: float              # sobe com o tempo (mundo)
    color: str
    life: float = LIFE
    lane: int = 0         # 0 = no ponto; 1 = uma linha acima...
    y0: float = 0.0       # y em que nasceu (pra achar os vizinhos mesmo depois de subir)

    @property
    def age(self) -> float:
        return LIFE - self.life


def split_amount(text: str) -> tuple[int, str] | None:
    """"+15 FERRO" -> (15, "FERRO"). Texto sem número ("+O2") -> None."""
    m = _AMOUNT.match(text)
    return (int(m.group(1)), m.group(2)) if m else None


class FloatingTexts:
    def __init__(self):
        self.items: list[Floater] = []

    def add(self, text: str, x: float, y: float, color: str) -> Floater:
        # 1) mesmo texto, mesmo lugar, ainda novinho: soma no que já existe
        for it in self.items:
            if (it.color == color and it.age < MERGE_AGE
                    and abs(it.x - x) <= MERGE_DIST and abs(it.y0 - y) <= MERGE_DIST):
                mine, theirs = split_amount(text), split_amount(it.text)
                if mine and theirs and mine[1] == theirs[1]:
                    it.text = f"+{mine[0] + theirs[0]} {mine[1]}"
                elif text != it.text:
                    continue
                it.life = LIFE        # sem voltar o y: nada de pulo, ele só fica mais um tempo
                return it
        # 2) faixa livre: a menor que nenhum vizinho vivo está usando
        taken = {it.lane for it in self.items if abs(it.x - x) <= NEAR_X and abs(it.y0 - y) <= NEAR_Y}
        lane = next(i for i in range(len(taken) + 1) if i not in taken)
        floater = Floater(text, x, y, color, lane=lane, y0=y)
        self.items.append(floater)
        return floater

    def update(self, dt: float) -> None:
        for it in self.items:
            it.y -= RISE * dt
            it.life -= dt
        self.items = [it for it in self.items if it.life > 0]
