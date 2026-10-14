"""Escuridão e luz da caverna (v0.3, Marco 2). Módulo isolado: só pygame, sem estado do jogo.

COMO FUNCIONA (a ideia em uma frase)
    Monta um "mapa de luz" pequeno (1/4 da resolução, por padrão), preto onde é breu e claro onde
    tem luz, estica ele sem suavizar e MULTIPLICA o mundo por ele (BLEND_RGB_MULT). Branco deixa o
    pixel como está, preto apaga, cor quente tinge. Duas luzes se somam (BLEND_RGB_ADD) e o pygame
    trava em 255, então nunca "estoura": no máximo o mundo aparece com a cor original.

    - Texturas de luz em cache por (raio em células, cor, intensidade quantizada, modo).
    - Culling: luz cujo quadrado não encosta na tela nem é desenhada.
    - A grade das células fica PRESA NO MUNDO (não na tela): a câmera andando não faz o contorno
      da luz "tremer". Só a própria luz anda em degraus de uma célula (4 px do mundo), o que
      combina com pixel art.

MODOS (flag `banding` do Lighting)
    banding=True   anéis em degraus (4 níveis: 100%, 68%, 40%, 18%), cara de pixel art.  ← RECOMENDADO
    banding=False  degradê suave (ainda em células de 4 px, então continua com cara de pixel)

API
    LightSource(x, y, radius, color=None, intensity=1.0, flicker=0.0)
        x, y e radius em PX DO MUNDO. color None = branco quente. flicker 0..1 = quanto a
        intensidade oscila (tocha/lâmpada velha); 0 = estável.
    Glint(x, y, color)
        brilho de minério: pontinho desenhado POR CIMA da escuridão. Não é luz (não ilumina nada).

    helmet_lamp(px, py, facing)        lanterna do capacete (~4 tiles, viés de 10 px pra frente)
    lamp(tx, ty)                       luminária num tile (~5 tiles, quente, flicker leve)
    machine_light(tx, ty, color)       luz fraca de máquina (~1,8 tile)
    ore_glints(world, tx0, tx1, ty0, ty1)  pontinhos dos minérios visíveis (world.py)

    lighting = Lighting(cell=4, banding=True)      # crie UMA vez (guarda os caches)
    lighting.apply(target, cam, lights, ambient=0.0, scale=1.0, t=0.0)
        escurece `target` (in-place). `cam` = canto de cima/esquerda da visão no mundo (o mesmo
        `cam` do Renderer). `scale` = px do target por px do mundo: 1.0 quando o target é a visão
        de SCREEN/zoom que o App já usa (é o caso normal); `zoom` se for aplicar direto no canvas
        960×540 já esticado.
    lighting.light_map(size, cam, lights, ambient, scale, t) -> (Surface, (ox, oy))
        só monta o mapa (pra quem quiser compor de outro jeito); `apply` é ele + um blit MULT.
    lighting.draw_glints(target, cam, glints, scale=1.0, t=0.0)
        brilho dos minérios. Chame DEPOIS do apply do mesmo frame: ele consulta o mapa de luz e
        o pontinho só aparece no escuro (no claro o próprio sprite do minério já se vê).
    lighting.brightness_at(x, y) -> 0..1   luz num ponto do target (último mapa montado).

    ambient: 0 = breu total, 1 = sem escuridão. Aceita também uma cor (r, g, b) pra luz ambiente
    tingida (ex.: superfície à noite, no futuro).

INTEGRAÇÃO (Marco 2, em Renderer.draw quando a camada atual é a caverna)
    Ordem: mundo -> ESCURIDÃO -> brilho de minério -> indicadores/floaters -> HUD.

        # __init__ do Renderer
        self.lighting = Lighting()
        # Renderer.draw(canvas, state, cam, t, ...)   (canvas aqui é a visão SCREEN/zoom)
        self.draw_floors(...); self.draw_veins(...); self.draw_walls_and_objects(...)
        self.draw_particles(...)
        if state.layer == "cave":
            lights = [helmet_lamp(p.x, p.y - 18, p.facing)]
            lights += [lamp(m.tx, m.ty) for m in machines if m.kind == "lamp"]
            lights += [machine_light(m.tx, m.ty, cor) for m in outras_maquinas]
            self.lighting.apply(canvas, cam, lights, ambient=0.0, t=t)
            self.lighting.draw_glints(canvas, cam, ore_glints(world, *self.visible_tiles(cam)), t=t)
        else:
            self.draw_lighting(...)   # a luz/clima de hoje, só na superfície
        self.draw_machine_status(...)  # por cima da escuridão, como já é hoje
        # floaters e HUD vêm depois, na UI: já ficam por cima de tudo.

    Na caverna NÃO chame o draw_lighting/draw_atmosphere atual (seria escuridão em dobro).
    Benchmark: `uv run python tools/dev/bench_lighting.py`. Demo: tools/dev/lighting_demo.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from game import config as C
from game import viewport
from game.surfaces import opaque

T = C.TILE

WARM_WHITE = (255, 236, 206)     # lanterna do capacete
LAMP_COLOR = (255, 222, 184)     # luminária: quente
BAND_LEVELS = (0.18, 0.40, 0.68, 1.0)   # do anel de fora pro centro
INTENSITY_STEPS = 16             # intensidade quantizada (cache finito mesmo com flicker)


@dataclass(frozen=True)
class LightSource:
    x: float
    y: float
    radius: float
    color: tuple[int, int, int] | None = None
    intensity: float = 1.0
    flicker: float = 0.0


@dataclass(frozen=True)
class Glint:
    x: float
    y: float
    color: tuple[int, int, int]


# ---- fábricas dos tipos de luz do design ----------------------------------------------------------
FACING_DIR = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def helmet_lamp(px: float, py: float, facing: str | tuple[float, float] | None = None) -> LightSource:
    """Lanterna do capacete: ~4 tiles, centro levemente deslocado pra onde o player olha."""
    dx, dy = FACING_DIR.get(facing, (0, 0)) if isinstance(facing, str) or facing is None else facing
    bias = 10
    return LightSource(px + dx * bias, py + dy * bias, 4 * T, WARM_WHITE, 1.0)


def lamp(tx: int, ty: int, radius_tiles: float = 5) -> LightSource:
    """Luminária no tile (tx, ty): ~5 tiles (a forte, do Marco 3: 7), quente, com uma tremidinha bem leve."""
    return LightSource(tx * T + T / 2, ty * T + T / 2 - 8, radius_tiles * T, LAMP_COLOR, 1.0, flicker=0.06)


def machine_light(tx: int, ty: int, color: tuple[int, int, int] = (150, 210, 230)) -> LightSource:
    """Luz fraca de uma máquina (o2, aquecedor, drill...)."""
    return LightSource(tx * T + T / 2, ty * T + T / 2, 1.8 * T, color, 0.55)


# Cor do brilho no escuro: saturada de propósito. O silício (#c3d1e2) e o gelo (#a6ecff) na cor do sprite
# saem quase brancos no breu e parecem estrelas (bug visto no Marco 2: "céu estrelado" na caverna).
GLINT_COLORS = {"iron": (232, 140, 72), "silicon": (120, 150, 230), "ice": (60, 196, 240),
                "magmatite": (255, 110, 40)}   # não tem minério de parede hoje (só rocha solta): fica pronto


def ore_glints(world, tx0: int, tx1: int, ty0: int, ty1: int) -> list[Glint]:
    """Um pontinho por tile de minério visível, numa posição fixa (sorteada pelo tile) dentro dele.

    Só minério na BORDA de um túnel/salão (com chão em algum dos 4 lados): é a parede que o jogador
    enxerga. O miolo da rocha (todo cercado de parede) não brilha, senão o breu vira um céu estrelado."""
    out = []
    is_wall = world.is_wall
    for ty in range(max(0, ty0), min(world.height, ty1 + 1)):
        for tx in range(max(0, tx0), min(world.width, tx1 + 1)):
            kind = world.get(tx, ty)
            name = C.ORE_TILES.get(kind)
            if name is None:
                continue
            h = (tx * 73856093 ^ ty * 19349663) & 0xFFFF
            if h % 5 >= 2:              # só ~40% dos tiles brilham: pontinhos esparsos
                continue
            if is_wall(tx + 1, ty) and is_wall(tx - 1, ty) and is_wall(tx, ty + 1) and is_wall(tx, ty - 1):
                continue
            ox, oy = 7 + h % 18, 6 + (h >> 5) % 14     # cai na face da rocha, longe da borda
            out.append(Glint(tx * T + ox, ty * T + oy, GLINT_COLORS[name]))
    return out


# ---- o sistema --------------------------------------------------------------------------------------
def _falloff(d: float) -> float:
    """Brilho (0..1) a uma distância relativa d (0 = centro, 1 = borda): núcleo cheio, borda macia."""
    if d >= 1.0:
        return 0.0
    if d <= 0.3:
        return 1.0
    k = (d - 0.3) / 0.7
    return 1.0 - k * k * (3 - 2 * k)      # smoothstep invertido


def _flicker_value(t: float, seed: float) -> float:
    """Ruído suave 0..1 (soma de senos com fases do seed): barato e sem estado."""
    return 0.5 + 0.25 * math.sin(t * 7.3 + seed) + 0.25 * math.sin(t * 13.1 + seed * 1.7)


class Lighting:
    def __init__(self, cell: int = 4, banding: bool = True):
        self.cell = cell              # tamanho da célula do mapa de luz, em px do target
        self.banding = banding
        self._tex: dict[tuple, pygame.Surface] = {}
        self._small: pygame.Surface | None = None
        self._big: pygame.Surface | None = None
        self._last = None             # (cam, scale, ox, oy) do último mapa: o draw_glints consulta

    # -- texturas --
    def texture(self, radius_cells: int, color: tuple[int, int, int], intensity: float) -> pygame.Surface:
        """Disco de luz (fundo preto, RGB pré-multiplicado) de raio `radius_cells` células. Em cache."""
        q = max(0, min(INTENSITY_STEPS, round(intensity * INTENSITY_STEPS)))
        key = (radius_cells, color, q, self.banding)
        tex = self._tex.get(key)
        if tex is None:
            tex = self._tex[key] = self._make_texture(radius_cells, color, q / INTENSITY_STEPS)
        return tex

    def _make_texture(self, r: int, color, intensity: float) -> pygame.Surface:
        size = 2 * r
        surf = opaque((size, size))
        surf.fill((0, 0, 0))
        cr, cg, cb = color
        for j in range(size):
            for i in range(size):
                d = math.hypot(i + 0.5 - r, j + 0.5 - r) / r
                b = _falloff(d)
                if b <= 0:
                    continue
                if self.banding:
                    b = BAND_LEVELS[min(len(BAND_LEVELS) - 1, int(b * len(BAND_LEVELS)))]
                b *= intensity
                surf.set_at((i, j), (int(cr * b), int(cg * b), int(cb * b)))
        return surf

    # -- mapa de luz --
    def light_map(self, size: tuple[int, int], cam: tuple[float, float], lights, ambient=0.0,
                  scale: float = 1.0, t: float = 0.0) -> tuple[pygame.Surface, tuple[int, int]]:
        """Mapa de luz já esticado e o ponto (ox, oy) do target onde ele vai (ox, oy ≤ 0).

        A grade de células é presa ao mundo: a origem do mapa é o múltiplo de `cell` logo antes de
        cam*scale, por isso o (ox, oy) vai de 0 a -(cell-1)."""
        cell = self.cell
        w, h = size
        cx, cy = cam[0] * scale, cam[1] * scale
        ox, oy = -int(cx % cell), -int(cy % cell)
        sw, sh = (w - ox + cell - 1) // cell, (h - oy + cell - 1) // cell
        if self._small is None or self._small.get_size() != (sw, sh):
            # opacos e no formato da tela interna: o BLEND_RGB_MULT final vira cópia direta, sem conversão
            self._small = opaque((sw, sh))
            self._big = opaque((sw * cell, sh * cell))
        small = self._small

        if isinstance(ambient, (int, float)):
            a = max(0, min(255, round(ambient * 255)))
            small.fill((a, a, a))
        else:
            small.fill(ambient)

        blit = small.blit
        add = pygame.BLEND_RGB_ADD
        for L in lights:
            sx, sy = viewport.world_to_canvas((L.x, L.y), cam, scale)
            r = max(1, round(L.radius * scale / cell))
            # posição em células (grade presa no mundo: soma o resto da câmera)
            gx, gy = int((sx - ox) // cell), int((sy - oy) // cell)
            if gx + r < 0 or gy + r < 0 or gx - r >= sw or gy - r >= sh:
                continue                                 # culling: fora da tela
            inten = L.intensity
            if L.flicker:
                inten *= 1.0 - L.flicker * _flicker_value(t, L.x * 0.37 + L.y * 0.91)
            blit(self.texture(r, L.color or WARM_WHITE, inten), (gx - r, gy - r), special_flags=add)

        self._last = (cam, scale, ox, oy)
        big = self._big
        pygame.transform.scale(small, big.get_size(), big)
        return big, (ox, oy)

    def apply(self, target: pygame.Surface, cam, lights, ambient=0.0, scale: float = 1.0, t: float = 0.0) -> None:
        """Escurece `target` in-place (multiplica pelo mapa de luz)."""
        big, pos = self.light_map(target.get_size(), cam, lights, ambient, scale, t)
        target.blit(big, pos, special_flags=pygame.BLEND_RGB_MULT)

    def brightness_at(self, x: float, y: float) -> float:
        """Luz (0..1, o canal mais forte) no ponto (x, y) do target, segundo o último mapa montado."""
        if self._last is None:
            return 0.0
        _, _, ox, oy = self._last
        gx, gy = int((x - ox) // self.cell), int((y - oy) // self.cell)
        sw, sh = self._small.get_size()
        if not (0 <= gx < sw and 0 <= gy < sh):
            return 0.0
        c = self._small.get_at((gx, gy))
        return max(c.r, c.g, c.b) / 255

    # -- brilho de minério (por cima da escuridão) --
    def draw_glints(self, target: pygame.Surface, cam, glints, scale: float = 1.0, t: float = 0.0) -> None:
        """Pontinho na cor do minério + um "+" apagado em volta que pulsa devagar. Não ilumina nada:
        é desenhado DEPOIS da escuridão. Chame depois do `apply` do mesmo frame: no claro o brilho
        some (no escuro ele aparece inteiro, na penumbra fica pela metade)."""
        w, h = target.get_size()
        px = max(1, round(scale))          # 1 px do mundo na tela
        fill = target.fill
        add = pygame.BLEND_RGB_ADD     # soma: na penumbra não apaga o que já está claro
        for g in glints:
            x, y = viewport.world_to_canvas((g.x, g.y), cam, scale)
            x, y = int(x), int(y)
            if x < -4 or y < -4 or x > w + 4 or y > h + 4:
                continue
            dark = 1.0 - self.brightness_at(x, y)
            if dark < 0.2:
                continue
            r, gg, b = g.color
            phase = 0.5 + 0.5 * math.sin(t * 2.2 + g.x * 0.13 + g.y * 0.07)
            k = (0.15 + 0.3 * phase) * dark
            dim = (int(r * k), int(gg * k), int(b * k))
            fill(dim, (x - px, y, px, 2 * px), add)          # "+" de 1 px em volta do miolo 2×2
            fill(dim, (x + 2 * px, y, px, 2 * px), add)
            fill(dim, (x, y - px, 2 * px, px), add)
            fill(dim, (x, y + 2 * px, 2 * px, px), add)
            k = (0.55 + 0.45 * phase) * dark
            fill((int(r * k), int(gg * k), int(b * k)), (x, y, 2 * px, 2 * px), add)   # sem "+branco": não vira estrela
