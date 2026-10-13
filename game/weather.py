"""Clima da tempestade de poeira (v0.4 Marco 1): direção do vento, rajadas e o raio de visão.

Python puro e determinístico pela seed. O GameState cria um `Weather` e chama `update(dt, storm)` a cada
frame, com `storm` = intensidade efetiva da tempestade (0 na caverna e a partir do Árido).

- `wind`: vetor unitário pra onde o vento sopra. Tem uma direção dominante sorteada pela seed e foge dela
  devagar (no máximo STORM_WIND_TURN °/s, até STORM_WIND_SWAY ° pra cada lado).
- `gust`: 0..1, a rajada agora. Uma rajada começa a cada STORM_GUST_EVERY s (a 1ª em STORM_GUST_FIRST),
  dura STORM_GUST_LEN s, e o `gust` sobe/desce em STORM_GUST_RAMP s. Rajada nova só começa com a tempestade cheia
  (storm ≥ STORM_GUST_MIN_STORM): na transição pro Árido as rajadas param, e com storm 0 nenhuma começa.
- `view_tiles`: raio de visão em tiles. Vai de STORM_VIEW_TILES até STORM_GUST_VIEW_TILES conforme o gust
  e cresce até o infinito conforme a tempestade some (storm 0 = `math.inf`).
"""

import math
import random

from game import config as C


class Weather:
    def __init__(self, seed: int):
        self.rng = random.Random(f"weather-{seed}")       # sorteio próprio: não mexe no rng do mundo
        self.dominant = self.rng.uniform(0, 360)          # graus; 0 = leste, 90 = sul (y da tela pra baixo)
        self.angle = self.dominant
        self.target = self.dominant
        self.retarget_in = self.rng.uniform(*C.STORM_WIND_RETARGET)
        self.next_gust = self.rng.uniform(*C.STORM_GUST_FIRST)   # s até a próxima rajada começar
        self.gust_left = 0.0                              # s que a rajada atual ainda segura o pico
        self.gust = 0.0
        self.wind = (1.0, 0.0)
        self.view_tiles = C.STORM_VIEW_TILES
        self._update_wind_vector()
        self._recompute(storm=1.0)

    def update(self, dt: float, storm: float) -> bool:
        """Anda o clima `dt` s. Devolve True no frame em que uma rajada começa (pro som e pro aviso)."""
        self._turn(dt)
        started = False
        if storm <= 0:
            self.gust_left = 0.0                          # sem tempestade: a rajada atual morre suave
        elif self.gust_left > 0:
            self.gust_left -= dt
        elif storm >= C.STORM_GUST_MIN_STORM:             # baixando pro Árido: a atual termina, nova não começa
            self.next_gust -= dt
            if self.next_gust <= 0:
                self.gust_left = self.rng.uniform(*C.STORM_GUST_LEN)
                # o intervalo conta do começo desta rajada até o começo da próxima
                self.next_gust += self.rng.uniform(*C.STORM_GUST_EVERY) - self.gust_left
                started = True
        target = 1.0 if self.gust_left > 0 else 0.0
        step = dt / C.STORM_GUST_RAMP
        self.gust = min(target, self.gust + step) if target > self.gust else max(target, self.gust - step)
        if abs(self.gust - target) < 1e-9:                # sem resto de ponto flutuante: chega no 0/1 exato
            self.gust = target
        self._recompute(storm)
        return started

    def _recompute(self, storm: float) -> None:
        """Raio de visão a partir do gust e da intensidade da tempestade."""
        if storm <= 0:
            self.view_tiles = math.inf
            return
        base = C.STORM_VIEW_TILES + (C.STORM_GUST_VIEW_TILES - C.STORM_VIEW_TILES) * self.gust
        self.view_tiles = base / min(1.0, storm)

    def push(self, storm: float) -> tuple[float, float]:
        """Empurrão da rajada agora, em px/s: vento × PLAYER_SPEED × STORM_PUSH × gust × storm."""
        k = C.PLAYER_SPEED * C.STORM_PUSH * self.gust * max(0.0, storm)
        return self.wind[0] * k, self.wind[1] * k

    def _turn(self, dt: float) -> None:
        self.retarget_in -= dt
        if self.retarget_in <= 0:
            self.retarget_in += self.rng.uniform(*C.STORM_WIND_RETARGET)
            self.target = self.dominant + self.rng.uniform(-C.STORM_WIND_SWAY, C.STORM_WIND_SWAY)
        diff = self.target - self.angle
        max_step = C.STORM_WIND_TURN * dt
        self.angle += max(-max_step, min(max_step, diff))
        self._update_wind_vector()

    def _update_wind_vector(self) -> None:
        rad = math.radians(self.angle)
        self.wind = (math.cos(rad), math.sin(rad))
