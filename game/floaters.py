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

E um terceiro, na hora de desenhar (`dodge_labels`): o rótulo flutuante do baú (mouse em cima) não
deixa floater passar por trás dele. Quem ia cruzar o rótulo sobe junto com os vizinhos e nasce acima.
"""

import itertools
import re
from dataclasses import dataclass, field

LIFE = 1.2            # segundos na tela
RISE = 22.0           # px do mundo por segundo
MERGE_AGE = 0.6       # só mescla com um floater de até 0,6 s de idade
MERGE_DIST = 12.0     # px do mundo: "o mesmo ponto"
NEAR_X, NEAR_Y = 56.0, 40.0   # px do mundo: nascidos tão perto assim dividem a pilha de faixas
LANE_PX = 12          # px da UI (metade da tela) entre uma faixa e a de cima

_IDS = itertools.count(1)

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
    uid: int = field(default_factory=lambda: next(_IDS), compare=False)   # chave estável (desvio do rótulo)

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



def dodge_labels(boxes: dict, labels: list[tuple[float, float, float, float]],
                 known: dict | None = None, gap: float = 1.0) -> dict:
    """Quanto (px da UI, pra cima) cada floater sobe pra não passar por trás de nenhum rótulo.

    boxes: {chave: (esquerda, direita, topo agora, quanto ainda vai subir, altura)} em px da UI.
    labels: (esquerda, topo, direita, baixo) de cada rótulo.
    known: deslocamentos já decididos em frames anteriores (chave -> px). Eles não mudam: todo floater
    sobe na mesma velocidade, então um deslocamento constante não gera pulo nem encontro novo.

    Pros novos (do mais velho pro mais novo): se a subida que falta cruza um rótulo, ele passa a ficar
    logo acima do rótulo; e se assim encosta em outro floater que já desviou, sobe pra cima dele
    (igual às faixas do FloatingTexts). Quem não cruza nada fica onde está (0).
    """
    shifts = {k: v for k, v in (known or {}).items() if k in boxes}
    fresh = sorted((k for k in boxes if k not in shifts), key=lambda k: boxes[k][3])   # menos subida = mais velho
    for k in fresh:
        x0, x1, top, travel, h = boxes[k]
        s = 0.0
        for _ in range(len(boxes) + len(labels) + 1):
            moved = False
            for lx0, ly0, lx1, ly1 in labels:
                if x0 < lx1 and x1 > lx0 and top - s - travel < ly1 and top - s + h > ly0:
                    s = top + h - ly0 + gap                     # o de baixo dele logo acima do rótulo
                    moved = True
            for j, sj in shifts.items():
                jx0, jx1, jtop, _, jh = boxes[j]
                if (s > 0 or sj > 0) and x0 < jx1 and x1 > jx0:
                    a, b = top - s, jtop - sj                   # topos na tela agora
                    if b - h - gap < a < b + jh + gap:          # encostados: este vai pra cima do outro
                        s = top - (b - h - gap)
                        moved = True
            if not moved:
                break
        shifts[k] = s
    return shifts
