"""O que o jogador já viu, por camada (v0.3 Marco 3 · bíblia §9). É a névoa de guerra do scanner.

O registro começa no primeiro frame do jogo, com ou sem scanner: quando o scanner chega, o mapa já vem
com tudo que foi explorado. Cada camada tem um `Explored` (1 byte por tile).

    - Superfície (clara): o retângulo que cabe na tela no zoom mais afastado, em volta do player.
    - Caverna (escura): só o que a luz revelou: os círculos da lanterna, das luminárias, da boca da rampa,
      dos terminais e das máquinas (raios iguais aos do game/lighting.py).

`fresh` junta os tiles revelados desde a última vez que alguém pediu (`take_fresh`): o minimapa usa isso
pra pintar só o que é novo (sem redesenhar 192×192 todo frame).

Save: bitset (1 bit por tile) comprimido com zlib e em base64 (um mapa novo dá ~100 bytes).
Python puro, testado em tests/test_explore.py.
"""

import base64
import math
import zlib

from game import config as C


class Explored:
    def __init__(self, width: int, height: int):
        self.width, self.height = width, height
        self.bits = bytearray(width * height)      # 1 = visto
        self.fresh: list[tuple[int, int]] = []
        self.count = 0

    def seen(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height and self.bits[y * self.width + x] == 1

    def _mark(self, x: int, y: int) -> None:
        i = y * self.width + x
        if not self.bits[i]:
            self.bits[i] = 1
            self.fresh.append((x, y))
            self.count += 1

    def reveal_rect(self, cx: int, cy: int, hx: int, hy: int) -> None:
        """Marca o retângulo (cx ± hx, cy ± hy)."""
        x0, x1 = max(0, cx - hx), min(self.width - 1, cx + hx)
        bits, w = self.bits, self.width
        for y in range(max(0, cy - hy), min(self.height - 1, cy + hy) + 1):
            row = y * w
            if all(bits[row + x0:row + x1 + 1]):   # linha inteira já vista: pula rápido
                continue
            for x in range(x0, x1 + 1):
                if not bits[row + x]:
                    self._mark(x, y)

    def reveal_circle(self, cx: float, cy: float, r: float) -> None:
        """Marca os tiles cujo centro está a até `r` tiles de (cx, cy) (em tiles, pode ser fracionado)."""
        for y in range(max(0, math.floor(cy - r)), min(self.height - 1, math.ceil(cy + r)) + 1):
            dy = y + 0.5 - cy
            span = r * r - dy * dy
            if span < 0:
                continue
            half = math.sqrt(span)
            for x in range(max(0, math.ceil(cx - half - 0.5)), min(self.width - 1, math.floor(cx + half - 0.5)) + 1):
                self._mark(x, y)

    def take_fresh(self) -> list[tuple[int, int]]:
        out, self.fresh = self.fresh, []
        return out

    # ---- save ----------------------------------------------------------------------------
    def to_data(self) -> str:
        packed = bytearray((len(self.bits) + 7) // 8)
        for i, b in enumerate(self.bits):
            if b:
                packed[i >> 3] |= 1 << (i & 7)
        return base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")

    @classmethod
    def from_data(cls, width: int, height: int, text: str | None) -> "Explored":
        ex = cls(width, height)
        if not text:
            return ex
        packed = zlib.decompress(base64.b64decode(text))
        n = width * height
        if len(packed) != (n + 7) // 8:
            raise ValueError("explorado com tamanho errado")
        for i in range(n):
            if packed[i >> 3] >> (i & 7) & 1:
                ex.bits[i] = 1
        ex.count = sum(ex.bits)
        return ex


def light_circles(state) -> list[tuple[float, float, float]]:
    """Caverna: (x, y, raio) em tiles de tudo que ilumina (o que a luz revela). Mesmos raios do lighting."""
    T = C.TILE
    p = state.player
    out = [(p.x / T, (p.y - 18) / T, C.EXPLORE_HELMET)]
    world = state.world
    if world.crater is not None:
        rx, ry = world.crater
        out.append((rx + 1.5, ry + 1, C.EXPLORE_RAMP))
    for m in state.machines:
        if m.is_lamp:
            out.append((m.tx + 0.5, m.ty + 0.25, C.LAMP_RADIUS.get(m.kind, 5)))
        elif not m.is_chest:
            ax, ay = m.anchor
            out.append((ax / T, ay / T - 0.5, C.EXPLORE_MACHINE))
    for tx, ty in world.terminals:
        out.append((tx + 0.5, ty + 1, C.EXPLORE_TERMINAL))
    return out


def reveal_for(state) -> None:
    """Marca o que o player está vendo agora na camada ativa."""
    explored = state.active.explored
    if explored is None:
        return
    if state.active.has_base:                                   # superfície: tudo que cabe na tela
        tx, ty = state.player.tile
        hx, hy = C.EXPLORE_SURFACE
        explored.reveal_rect(tx, ty, hx, hy)
    else:                                                       # caverna: só o que a luz alcança...
        px, py = state.player.x / C.TILE, state.player.y / C.TILE
        hx, hy = C.EXPLORE_SURFACE
        for x, y, r in light_circles(state):                    # ...e que está na tela (terminal aceso lá longe
            if abs(x - px) - r <= hx and abs(y - py) - r <= hy:  # não conta como visto)
                explored.reveal_circle(x, y, r)
