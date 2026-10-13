"""Chuva (v0.4 Marco 3 · M3.3, bíblia §12 "Chuva e lagos").

Duas partes, no mesmo esquema da tempestade:

- `Rain` (Python puro, determinístico pela seed, mora no GameState): pancadas de chuva no estilo das rajadas do
  game/weather.py. Só começam da Névoa em diante. Na Névoa, C.RAIN_MIST_LEN s de chuva a cada C.RAIN_MIST_EVERY s
  (de começo a começo); no Verde, C.RAIN_GREEN_LEN (mais curtas). A 1ª vem C.RAIN_FIRST s depois de entrar na
  Névoa. `intensity` (0..1) sobe e desce em C.RAIN_RAMP s. Não vai no save: sai da seed.
- `RainDrops` (desenho): traços diagonais no ângulo do vento (`state.weather.wind`), presos à câmera (posições
  num "espaço de dobra" com módulo do tamanho da visão, como os grãos do game/dust.py), no máximo
  C.RAIN_MAX_DROPS com a chuva cheia, mais um véu frio bem leve. Custo zero sem chuva.

A chuva só existe na superfície: `rain_level(state)` dá 0 na caverna (o relógio das pancadas continua lá em cima).
"""

from __future__ import annotations

import math
import random

from game import config as C

# O pygame só entra no desenho (RainDrops): o GameState (e o game/worlds.py, que lê saves sem janela) importa este
# módulo pelo `Rain` e não pode puxar o pygame junto.

DROP_SHAPES = 6                   # variações de comprimento/alfa dos traços
SLANT_STEPS = 4                   # inclinação quantizada: -4..4 (o vento vira devagar, o cache fica pequeno)
DROP_COLOR = (196, 220, 236)
PAD = 24                          # px fora da tela onde o traço ainda "existe" (entra sem pipocar na borda)


def rain_level(state) -> float:
    """Intensidade da chuva que vale agora: a do `state.rain` na superfície, 0 na caverna."""
    if not state.active.has_base:
        return 0.0
    return state.rain.intensity


class Rain:
    def __init__(self, seed: int):
        self.rng = random.Random(f"rain-{seed}")          # sorteio próprio: não mexe no rng do mundo nem no clima
        self.next_shower = self.rng.uniform(*C.RAIN_FIRST)   # s (já na Névoa) até a próxima pancada começar
        self.left = 0.0                                    # s que a pancada atual ainda dura
        self.intensity = 0.0

    @property
    def raining(self) -> bool:
        """A pancada está rolando (a intensidade pode ainda estar subindo)."""
        return self.left > 0

    def update(self, dt: float, stage: int) -> bool:
        """Anda a chuva `dt` s no estágio `stage`. Devolve True no frame em que uma pancada começa."""
        started = False
        if self.left > 0:
            self.left -= dt
        elif stage >= C.MIST_STAGE:
            self.next_shower -= dt
            if self.next_shower <= 0:
                green = stage >= C.GREEN_STAGE
                self.left = self.rng.uniform(*(C.RAIN_GREEN_LEN if green else C.RAIN_MIST_LEN))
                # o intervalo conta do começo desta pancada até o começo da próxima
                every = self.rng.uniform(*(C.RAIN_GREEN_EVERY if green else C.RAIN_MIST_EVERY))
                self.next_shower += every - self.left
                started = True
        target = 1.0 if self.left > 0 else 0.0
        step = dt / C.RAIN_RAMP
        if target > self.intensity:
            self.intensity = min(target, self.intensity + step)
        else:
            self.intensity = max(target, self.intensity - step)
        if abs(self.intensity - target) < 1e-9:              # sem resto de float: chega no 0/1 exato
            self.intensity = target
        return started


class RainDrops:
    """Traços da chuva na tela. Cada traço tem uma posição num espaço de dobra de 4096 px e anda com a velocidade
    da queda; o desenho usa o módulo do tamanho da visão (mais uma folga), então não precisa repor nada."""

    def __init__(self, seed: int = 0):
        rng = random.Random(f"raindrops-{seed}")
        span = 4096.0
        # [x, y, fator de velocidade, forma]
        self.drops = [[rng.random() * span, rng.random() * span, rng.uniform(0.85, 1.15), rng.randrange(DROP_SHAPES)]
                      for _ in range(C.RAIN_MAX_DROPS)]
        self.offset = [0.0, 0.0]                           # quanto a chuva já andou (px), soma da velocidade × dt
        self._last_t: float | None = None
        self._tex: dict = {}

    @staticmethod
    def count(intensity: float) -> int:
        """Quantos traços aparecem com essa intensidade (≤ C.RAIN_MAX_DROPS)."""
        if intensity <= 0:
            return 0
        return max(1, round(C.RAIN_MAX_DROPS * min(1.0, intensity)))

    @staticmethod
    def velocity(wind) -> tuple[float, float]:
        """px/s da queda: sempre pra baixo, torta pro lado do vento (só a componente x do vento entorta)."""
        return wind[0] * C.RAIN_SPEED * C.RAIN_SLANT, C.RAIN_SPEED

    def streak(self, slant: int, shape: int) -> pygame.Surface:
        """Traço fino com a inclinação `slant` (-SLANT_STEPS..SLANT_STEPS), mais forte na ponta de baixo."""
        key = (slant, shape)
        tex = self._tex.get(key)
        if tex is not None:
            return tex
        import pygame
        lo, hi = C.RAIN_LEN
        length = lo + (hi - lo) * shape / (DROP_SHAPES - 1)
        alpha = C.RAIN_ALPHA[0] + (C.RAIN_ALPHA[1] - C.RAIN_ALPHA[0]) * ((shape * 7) % DROP_SHAPES) / (DROP_SHAPES - 1)
        k = slant / SLANT_STEPS * C.RAIN_SLANT              # dx/dy
        n = math.hypot(k, 1.0)
        dx, dy = k / n * length, 1.0 / n * length
        w, h = int(abs(dx)) + 3, int(dy) + 3
        tex = pygame.Surface((w, h), pygame.SRCALPHA)
        tex.fill((0, 0, 0, 0))
        x0 = 1 if dx >= 0 else w - 2
        steps = max(2, int(length))
        for i in range(steps):                                # degradê: a cauda (em cima) some
            u0, u1 = i / steps, (i + 1) / steps
            a = round(alpha * (0.25 + 0.75 * u1))
            pygame.draw.line(tex, (*DROP_COLOR, a), (x0 + dx * u0, 1 + dy * u0), (x0 + dx * u1, 1 + dy * u1))
        self._tex[key] = tex
        return tex

    def draw(self, canvas: pygame.Surface, intensity: float, wind, t: float) -> None:
        """Desenha a chuva em `canvas` (a visão inteira). `t` é o relógio do frame (o dt sai da diferença)."""
        n = self.count(intensity)
        if not n:
            self._last_t = None
            return
        dt = 0.0 if self._last_t is None else max(0.0, min(0.1, t - self._last_t))
        self._last_t = t
        vx, vy = self.velocity(wind)
        self.offset[0] += vx * dt
        self.offset[1] += vy * dt
        ox, oy = self.offset
        import pygame
        w, h = canvas.get_size()
        # véu frio: escurece um pouco e puxa pro azul (multiplicação, barato)
        d = round(C.RAIN_TINT * min(1.0, intensity))
        if d:
            canvas.fill((255 - d, 255 - d * 3 // 4, 255 - d // 3), special_flags=pygame.BLEND_RGB_MULT)
        slant = max(-SLANT_STEPS, min(SLANT_STEPS, round(vx / vy / C.RAIN_SLANT * SLANT_STEPS)))
        texs = [self.streak(slant, s) for s in range(DROP_SHAPES)]
        sw, sh = w + 2 * PAD, h + 2 * PAD
        blit = canvas.blit
        for x, y, k, shape in self.drops[:n]:
            blit(texs[shape], (int((x + ox * k) % sw) - PAD, int((y + oy * k) % sh) - PAD))
