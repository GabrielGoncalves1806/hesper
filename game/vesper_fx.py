"""Faísca e névoa da porta emperrada da VÉSPER-7 (v0.7 M4). Só o visual: lógica pura (sem pygame além do desenho),
testada em tests/test_vesper_trip.py.

- Faísca: a cada 0,6–1,8 s, 3–6 pontinhos amarelos/brancos saem do leitor de crachá (px (24,12) da face), vida 0,25 s,
  com gravidade. `update` devolve a posição do estalo (pro app tocar o `spark`) ou None.
- Névoa: 2–3 por segundo, azul-clara translúcida, nasce na soleira, anda pros lados e pra baixo (4–8 px/s) e morre antes
  de 1 tile da soleira.
Só acontece com o player a até FX_RANGE tiles da porta.
"""

from __future__ import annotations

import math
import random

import pygame

from game import config as C

T = C.TILE
FX_RANGE = 8                           # tiles
SPARK_COLORS = ((255, 236, 140), (255, 255, 255))
SPARK_GRAVITY = 220.0
SPARK_LIFE = 0.25
SPARK_GAP = (0.6, 1.8)                 # s entre dois estalos
SPARK_COUNT = (3, 6)
READER = (24, 12)                      # px do leitor dentro da face 32×24 (a face fica em (tx·32, ty·32 + 8))
FOG_COLOR = (190, 225, 255)
FOG_RATE = (2.0, 3.0)                  # partículas por segundo
FOG_LIFE = (1.5, 2.5)
FOG_VY = (4.0, 8.0)
FOG_ALPHA = (60, 90)


class DoorFx:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.sparks: list[list] = []   # [x, y, vx, vy, vida, cor]
        self.fog: list[list] = []      # [x, y, vx, vy, vida, vida_total, alfa]
        self._spark_in = self.rng.uniform(*SPARK_GAP)
        self._fog_acc = 0.0

    def clear(self) -> None:
        self.sparks.clear()
        self.fog.clear()

    @staticmethod
    def reader_pos(door: tuple[int, int]) -> tuple[float, float]:
        return door[0] * T + READER[0], door[1] * T + C.BASE_FACE_Y + READER[1]

    def update(self, dt: float, door: tuple[int, int] | None, player: tuple[float, float]) -> tuple[float, float] | None:
        """Anda `dt` s. `door` = tile da porta emperrada (None = fora da nave). Devolve onde estalou uma faísca neste
        passo (pro som) ou None."""
        for p in self.sparks:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += SPARK_GRAVITY * dt
            p[4] -= dt
        for p in self.fog:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[4] -= dt
        self.sparks = [p for p in self.sparks if p[4] > 0]
        self.fog = [p for p in self.fog if p[4] > 0]
        if door is None or math.hypot(player[0] - (door[0] + 0.5) * T, player[1] - (door[1] + 1) * T) > FX_RANGE * T:
            self._spark_in = max(self._spark_in, 0.3)
            return None
        rng = self.rng
        self._fog_acc += rng.uniform(*FOG_RATE) * dt
        while self._fog_acc >= 1:
            self._fog_acc -= 1
            life = rng.uniform(*FOG_LIFE)
            vy = rng.uniform(*FOG_VY)
            sill = (door[1] + 1) * T
            # morre antes de 1 tile da soleira: vida × vy < T (com folga, o vy máximo de 8 px/s × 2,5 s = 20 px)
            self.fog.append([(door[0] + rng.uniform(0.1, 0.9)) * T, sill, rng.uniform(-6, 6), vy, life, life,
                             rng.randint(*FOG_ALPHA)])
        self._spark_in -= dt
        if self._spark_in > 0:
            return None
        self._spark_in = rng.uniform(*SPARK_GAP)
        x, y = self.reader_pos(door)
        for _ in range(rng.randint(*SPARK_COUNT)):
            a = rng.uniform(-math.pi * 0.9, -math.pi * 0.1)          # pra cima e pros lados
            sp = rng.uniform(30, 80)
            self.sparks.append([x, y, math.cos(a) * sp, math.sin(a) * sp, SPARK_LIFE, rng.choice(SPARK_COLORS)])
        return x, y

    def draw(self, canvas, cam) -> None:
        for x, y, _, _, life, total, alpha in self.fog:
            k = min(1.0, life / total * 2)                            # some no final
            size = 6
            puff = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(puff, (*FOG_COLOR, int(alpha * k)), (size // 2, size // 2), size // 2)
            canvas.blit(puff, (round(x - cam[0]) - size // 2, round(y - cam[1]) - size // 2))
        for x, y, _, _, _, color in self.sparks:
            canvas.fill(color, (round(x - cam[0]), round(y - cam[1]), 2, 2))
