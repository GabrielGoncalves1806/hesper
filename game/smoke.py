"""Fumaça das fumarolas do basalto (v0.4 Marco 3 · M3.1, arte e números da v9.1 da Designer · bíblia §12).

A fumaça é PARTÍCULA, não sprite (no padrão do game/dust.py): cada boca (`mouths` do regions_palettes.json, px do
sprite) de uma fumarola acordada solta puffs a `rate` por segundo. O puff sobe (`rise`, freando até ~35% no fim
da vida), abre (`radius` do inicial ao final), treme de lado (`jitter`), é arrastado pelo vento do `state.weather`
(`wind` = fração do vento da superfície) e some em degraus de alfa (`alpha`, por terço da vida). As cores são 3
tons chapados (miolo, corpo e a borda de baixo), puxadas pro `stage_tint` na Tempestade e na Névoa.

Só na superfície e só na tela: boca fora da tela (com folga) não solta puff, e puff que saiu da área some.
Quando uma fumarola acorda, a taxa começa em 1/3 e sobe até a cheia em THAW_FUMAROLE_WAKE_S (o `wake` do JSON).

Desenhada pelo Renderer depois dos objetos e antes da luz/clima e da HUD (game/render.py · draw_vent_smoke).
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import NamedTuple

import pygame

from game import config as C

# Números da Designer (regions_palettes.json → smoke). Se o arquivo sumir, os mesmos valores aqui. Por cima de tudo,
# o C.SMOKE_OVERRIDE (M3.5: mais visível no basalto escuro, sem mexer no asset).
_DEFAULT = {
    "rate": {"cone": 2.5, "pair": 2.0, "chimney": 3.5}, "life": [2.6, 3.4], "rise": [16.0, 22.0],
    "radius": [1.5, 2.5, 7.0, 10.0], "jitter": 3.0, "wind": 0.45,
    "color": ["#e9e4dc", "#c4bdb4", "#958e88"], "alpha": [150, 110, 70],
    "stage_tint": {"storm": "#c9a37e", "arid": None, "mist": "#aab3bb", "green": None},
}


def _load() -> dict:
    try:
        data = json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8")).get("smoke") or {}
    except (OSError, ValueError):
        data = {}
    return {**_DEFAULT, **data, **getattr(C, "SMOKE_OVERRIDE", {})}


SMOKE = _load()
CULL_MARGIN = 48          # px: boca até essa distância fora da tela ainda solta (a fumaça entra subindo)
CULL_BELOW = 120          # px a mais embaixo: a fumaça sobe, então a boca abaixo da tela ainda aparece


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def colors(stage: str) -> tuple[tuple[int, int, int], ...]:
    """(miolo, corpo, borda de baixo) no estágio: com `stage_tint`, 60% da cor + 40% do tom."""
    cols = [_rgb(c) for c in SMOKE["color"]]
    tint = SMOKE["stage_tint"].get(stage)
    if tint:
        t = _rgb(tint)
        cols = [tuple(round(c[k] * 0.6 + t[k] * 0.4) for k in range(3)) for c in cols]
    return tuple(cols)


class Source(NamedTuple):
    """Uma fumarola acordada: o índice (geo.vents), o tipo curto ("cone", "pair", "chimney") e as bocas em px do mundo."""
    index: int
    kind: str
    mouths: list


@dataclass(slots=True)
class Puff:
    x: float
    y: float
    ox: float             # x sem a tremida (a tremida é um seno em volta dele)
    age: float
    life: float
    v0: float
    r0: float
    r1: float
    phase: float

    def radius(self) -> float:
        f = min(1.0, self.age / self.life)
        return self.r0 + (self.r1 - self.r0) * (1 - (1 - f) ** 2)

    def alpha(self) -> int:
        f = self.age / self.life
        a = SMOKE["alpha"]
        return a[0] if f < 0.35 else a[1] if f < 0.7 else a[2]


class VentSmoke:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(f"smoke-{seed}")
        self.puffs: list[Puff] = []
        self._acc: dict[tuple[int, int], float] = {}     # (fumarola, boca) -> fração acumulada do próximo puff
        self._waking: dict[int, float] = {}              # fumarola acordando -> s desde que acordou
        self._sprites: dict[tuple, pygame.Surface] = {}
        self._layer: pygame.Surface | None = None        # camada reaproveitada do desenho (cresce quando precisa)

    def wake(self, index: int) -> None:
        """A fumarola acabou de acordar: a taxa começa em 1/3 e sobe até a cheia (THAW_FUMAROLE_WAKE_S)."""
        self._waking[index] = 0.0

    def _spawn(self, x: float, y: float, age: float) -> None:
        r, s = self.rng, SMOKE
        self.puffs.append(Puff(x, y, x, age, r.uniform(*s["life"]), r.uniform(*s["rise"]),
                               r.uniform(s["radius"][0], s["radius"][1]), r.uniform(s["radius"][2], s["radius"][3]),
                               r.uniform(0, 2 * math.pi)))

    def update(self, dt: float, sources: list[Source], wind: tuple[float, float], view: pygame.Rect) -> None:
        """Anda `dt` s. `wind` = vento da superfície em px/s (a fumaça pega SMOKE["wind"] dele); `view` = a área
        do mundo na tela (px)."""
        if dt <= 0:
            return
        area = pygame.Rect(view.x - CULL_MARGIN, view.y - CULL_MARGIN,
                           view.w + 2 * CULL_MARGIN, view.h + 2 * CULL_MARGIN + CULL_BELOW)
        live: set[tuple[int, int]] = set()
        for src in sources:
            ramp = 1.0
            if src.index in self._waking:
                t = self._waking[src.index] = self._waking[src.index] + dt
                ramp = 1 / 3 + 2 / 3 * min(1.0, t / C.THAW_FUMAROLE_WAKE_S)
                if t >= C.THAW_FUMAROLE_WAKE_S:
                    del self._waking[src.index]
            rate = SMOKE["rate"].get(src.kind, 2.5) * ramp
            for k, (mx, my) in enumerate(src.mouths):
                if not area.collidepoint(mx, my):
                    continue
                key = (src.index, k)
                live.add(key)
                acc = self._acc.get(key)
                if acc is None:
                    acc = self.rng.random()               # bocas fora de fase (não soltam todas juntas)
                acc += rate * dt
                while acc >= 1.0 and len(self.puffs) < C.THAW_FUMAROLE_MAX_PUFFS:
                    acc -= 1.0
                    self._spawn(mx, my, acc / rate)       # nasce com a idade que "sobrou" do quadro
                self._acc[key] = min(acc, 1.0)
        for key in [k for k in self._acc if k not in live]:
            del self._acc[key]
        wx, wy = wind[0] * SMOKE["wind"], wind[1] * SMOKE["wind"]
        jitter = SMOKE["jitter"]
        keep = []
        for p in self.puffs:
            p.age += dt
            if p.age >= p.life:
                continue
            f = p.age / p.life
            p.y += (wy - p.v0 * (1 - 0.65 * f)) * dt       # sobe freando até ~35% (o rise da Designer)
            p.ox += wx * dt
            p.x = p.ox + jitter * math.sin(p.age * 2.1 + p.phase)
            if area.collidepoint(p.x, p.y):
                keep.append(p)
        self.puffs = keep

    def clear(self) -> None:
        self.puffs.clear()
        self._acc.clear()
        self._waking.clear()

    # ---- desenho ------------------------------------------------------------------------------------------------
    def sprite(self, r2: int, alpha: int, cols) -> pygame.Surface:
        """Puff de raio r2/2 px em pixel art: corpo (elipse levemente achatada), borda de baixo mais escura e o
        miolo claro puxado pra cima-esquerda. Um por (raio, alfa, cores), guardado."""
        key = (r2, alpha, cols)
        surf = self._sprites.get(key)
        if surf is None:
            rad = r2 / 2
            n = int(math.ceil(rad)) * 2 + 2
            c = n / 2
            surf = pygame.Surface((n, n), pygame.SRCALPHA)
            core, body, low = cols
            for y in range(n):
                for x in range(n):
                    px, py = x + 0.5 - c, y + 0.5 - c
                    if math.hypot(px, py * 1.1) > rad:
                        continue
                    if math.hypot(px + rad * 0.3, py + rad * 0.3) <= rad * 0.55:
                        col = core
                    elif py > rad * 0.35:
                        col = low
                    else:
                        col = body
                    surf.set_at((x, y), (*col, alpha))
            self._sprites[key] = surf
        return surf

    def glow_sprite(self, k: int) -> pygame.Surface:
        """Brilho quente da boca (radial, pra somar na tela), no degrau de intensidade k (0..7)."""
        key = ("glow", k)
        surf = self._sprites.get(key)
        if surf is None:
            r = C.THAW_FUMAROLE_GLOW_R
            n = 2 * r + 1
            surf = pygame.Surface((n, n), pygame.SRCALPHA)
            peak = C.THAW_FUMAROLE_GLOW_MAX * k / 7
            for y in range(n):
                for x in range(n):
                    d = math.hypot(x - r, (y - r) * 1.4) / r      # achatado: a boca é vista de cima-lado
                    if d < 1:
                        f = peak * (1 - d) ** 2 / 255
                        surf.set_at((x, y), (*(round(c * f) for c in C.THAW_FUMAROLE_GLOW), 255))
            self._sprites[key] = surf
        return surf

    def draw_glow(self, target: pygame.Surface, cam: tuple[int, int], sources: list[Source], t: float) -> None:
        """Brilho quente bem leve em cada boca acordada (somado: só clareia), pulsando devagar. Fica embaixo dos
        puffs. Ao acordar, acende junto com a taxa da fumaça."""
        cx, cy = cam
        tw, th = target.get_size()
        r = C.THAW_FUMAROLE_GLOW_R
        for src in sources:
            ramp = 1.0
            if src.index in self._waking:
                ramp = min(1.0, self._waking[src.index] / C.THAW_FUMAROLE_WAKE_S)
            for j, (mx, my) in enumerate(src.mouths):
                x, y = round(mx - cx) - r, round(my - cy) - r
                if x < -2 * r or y < -2 * r or x > tw or y > th:
                    continue
                pulse = 0.5 + 0.5 * math.sin(t * 1.7 + src.index * 2.3 + j * 1.1)
                k = int(round(7 * ramp * (0.6 + 0.4 * pulse)))
                if k <= 0:
                    continue
                target.blit(self.glow_sprite(k), (x, y), special_flags=pygame.BLEND_RGB_ADD)

    def draw(self, target: pygame.Surface, cam: tuple[int, int], stage: str) -> None:
        """Os puffs vão numa camada do tamanho da caixa deles com BLEND_RGBA_MAX (o alfa de dois puffs que se
        cruzam é o MAIOR, não a soma: igual à prévia da Designer, a coluna não vira um borrão opaco) e a camada vai
        uma vez pra tela."""
        if not self.puffs:
            return
        cols = colors(stage)
        cx, cy = cam
        items = []
        for p in self.puffs:
            s = self.sprite(max(2, round(p.radius() * 2)), p.alpha(), cols)
            h = s.get_width() // 2
            items.append((s, round(p.x - cx) - h, round(p.y - cy) - h))
        tw, th = target.get_size()
        x0 = max(0, min(x for _, x, _ in items))
        y0 = max(0, min(y for _, _, y in items))
        x1 = min(tw, max(x + s.get_width() for s, x, _ in items))
        y1 = min(th, max(y + s.get_height() for s, _, y in items))
        if x1 <= x0 or y1 <= y0:
            return
        w, h = x1 - x0, y1 - y0
        layer = self._layer
        if layer is None or layer.get_width() < w or layer.get_height() < h:
            layer = self._layer = pygame.Surface((max(w, 64), max(h, 64)), pygame.SRCALPHA)
        layer.fill((0, 0, 0, 0), (0, 0, w, h))
        layer.blits([(s, (x - x0, y - y0), None, pygame.BLEND_RGBA_MAX) for s, x, y in items], doreturn=False)
        target.blit(layer, (x0, y0), (0, 0, w, h))
