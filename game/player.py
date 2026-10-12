"""O astronauta: posição, direção e movimento com colisão.

A posição (x, y) é o ponto do PÉ do personagem, em pixels do mundo.
A colisão usa só uma caixinha nos pés (14×8 px): isso deixa o corpo passar
"na frente" das paredes, que é o que dá a sensação de visão 3/4.
"""

import math
from collections.abc import Callable, Iterable

from game import config as C

Rect = tuple[float, float, float, float]   # (esquerda, topo, largura, altura)


def overlaps(a: Rect, b: Rect) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


class Player:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.direction = "down"  # pra onde está virado: "down", "up", "left" ou "right"
        self.moving = False
        self.walk_time = 0.0     # acumula tempo andando (pra animação e passos)

    @property
    def facing(self) -> str:
        """Pra onde a lanterna do capacete aponta: a última direção de movimento ou mineração."""
        return self.direction

    @property
    def box(self) -> Rect:
        return (self.x - C.PLAYER_BOX_W / 2, self.y - C.PLAYER_BOX_H, C.PLAYER_BOX_W, C.PLAYER_BOX_H)

    @property
    def tile(self) -> tuple[int, int]:
        """Tile onde estão os pés do player."""
        return int(self.x // C.TILE), int((self.y - 1) // C.TILE)

    def move(self, dx: float, dy: float, dt: float, solids_near: Callable[[Rect], Iterable[Rect]],
             speed: float = C.PLAYER_SPEED) -> None:
        """Anda na direção (dx, dy) e para nas paredes.

        `solids_near(caixa)` devolve os retângulos sólidos perto da caixa (paredes, máquinas, cápsula).
        Movemos um eixo de cada vez: assim, encostando numa parede, o player ainda escorrega ao longo dela.
        `speed` em px/s (o GameState passa a do F3 quando ligado).
        """
        length = math.hypot(dx, dy)
        self.moving = length > 0
        if not self.moving:
            return
        if length > 1:   # diagonal não pode ser mais rápida
            dx, dy = dx / length, dy / length
        self.face(dx, dy)
        self.walk_time += dt
        self._move_axis(dx * speed * dt, 0, solids_near)
        self._move_axis(0, dy * speed * dt, solids_near)

    def face(self, dx: float, dy: float) -> None:
        """Vira o player pra direção (dx, dy). Na diagonal, o lado ganha (o sprite de lado lê melhor)."""
        if dx == 0 and dy == 0:
            return
        if abs(dx) >= abs(dy):
            self.direction = "right" if dx > 0 else "left"
        else:
            self.direction = "down" if dy > 0 else "up"

    def _move_axis(self, mx: float, my: float, solids_near) -> None:
        self.x += mx
        self.y += my
        for solid in solids_near(self.box):
            box = self.box
            if not overlaps(box, solid):
                continue
            # Empurra de volta pra fora do sólido, só no eixo em que estamos andando.
            if mx > 0:
                self.x = solid[0] - C.PLAYER_BOX_W / 2
            elif mx < 0:
                self.x = solid[0] + solid[2] + C.PLAYER_BOX_W / 2
            elif my > 0:
                self.y = solid[1]
            elif my < 0:
                self.y = solid[1] + solid[3] + C.PLAYER_BOX_H
