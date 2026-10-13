"""Visual da tempestade de poeira (v0.4 Marco 1, trilha C). Só desenha: quanto de tempestade tem é o
`systems.storm_level(state)` (trilha A) e o vento/rajada é o `state.weather` (trilha B).

COMO FUNCIONA (v2, depois do feedback do dono: "parece uma imagem com um furo no meio")
    Tudo é montado numa superfície pequena (1 célula = 4 px do mundo, grade presa no mundo, igual ao
    game/lighting.py), esticada com suavização e blitada uma vez por cima do mundo.

    1. DENSIDADE = campo de nuvens. Um ruído fbm ladrilhável (gerado uma vez) vira duas camadas que rolam
       com o vento em velocidades e direções um pouco diferentes: uma SOMA alfa (e clareia a cor), a outra
       SUBTRAI (e escurece). Cada camada é blitada 3× deslocada ao longo do vento ("borrão de movimento"):
       as nuvens ficam esticadas na direção do vento, qualquer que seja ela, e o ladrilho continua
       ladrilhável. As duas deslizando uma sobre a outra fazem as formas mudarem o tempo todo.
    2. VISIBILIDADE = uma máscara (alfa 255 = poeira cheia) multiplicada na densidade. Cada ponto de vista
       (player, cápsula, máquinas) subtrai um degradê CONTÍNUO (smoothstep, sem anéis) que não chega a
       limpar tudo: perto do player ainda tem véu. Depois a própria máscara ganha ruído (soma, então só
       mexe dentro dos buracos): a borda da visão é irregular e anda com o vento. Não se vê círculo.
    3. FAIXAS de vento longas (80 a 250 px), finas e levemente curvas, com alfa baixo e rápidas, mais os
       grãos. Desenhadas dentro da camada (BLEND_RGBA_MAX nas faixas: clareiam sem abrir buraco).
    4. RAJADA: a densidade sobe, as nuvens e as faixas aceleram, a visão encolhe (weather.view_tiles) e
       entram mais faixas e grãos.

    Com storm 0 nada disso roda (o Renderer sai antes): custo zero fora da tempestade.

ORDEM (Renderer.draw, superfície)
    mundo -> luz/clima do estágio -> POEIRA + faixas + grãos -> indicadores das máquinas -> HUD (ui.py).

CORES: proposta B · Ocre da Designer (assets/sprites/_pending/storm/storm_palettes.json), pendente do dono.
"""

from __future__ import annotations

import math
import random

import pygame

from game import config as C
from game import viewport
from game.lighting import FACING_DIR
from game.systems import storm_level

T = C.TILE

# ---- cores (paleta B · Ocre) ------------------------------------------------------------------------
DUST_COLOR = (0xAD, 0x87, 0x5F)                 # fundo da poeira
CLOUD_LIGHT = (32, 28, 20)                      # quanto a nuvem densa clareia (#ad875f -> ~#c19970)
CLOUD_DARK = (46, 40, 30)                       # quanto a faixa escura escurece (#ad875f -> ~#836343)
GRAIN_TONES = ((0xD8, 0xB5, 0x85), (0xF3, 0xE0, 0xB6), (0x74, 0x55, 0x3A))
STREAK_COLOR = (0xE4, 0xC7, 0x97)

# ---- densidade -------------------------------------------------------------------------------------
CELL = 4                       # px do mundo por célula da camada
DENSITY_BASE = 0.56            # opacidade média com storm 1, sem rajada
DENSITY_GUST = 0.18            # quanto a rajada cheia soma
CLOUD_AMP = 0.40               # quanto a nuvem densa soma no pico do ruído
CLOUD_THIN = 0.30              # quanto a camada escura tira de alfa (o resto do contraste é cor)
NOISE_SIZE = 256               # lado do ladrilho de ruído (células = 1024 px do mundo)
NOISE_SEED = 7
SMEAR = 5                      # cópias de cada camada ao longo do vento (nuvem esticada no vento)
SMEAR_STEP = 8                 # células entre as cópias
CLOUD_SPEED = (34.0, 90.0)     # px/s do mundo da camada A: (calmo, a mais na rajada cheia); a B anda a 0,6×
CLOUD_B_TURN = 22.0            # graus: a camada B anda um pouco torta em relação ao vento
DETAIL_DARK = (26, 22, 16)     # manchinhas escuras finas (só cor: 2× a frequência, sem borrão)

# ---- visibilidade ----------------------------------------------------------------------------------
VIEW_REACH = 1.3               # o degradê da visão acaba em view_px × isso (meia visão ~5 tiles com 7)
VIEW_INNER = 0.12              # dentro disso (fração do alcance) a visão é a mais limpa
PLAYER_CLEAR = 0.56            # quanto da poeira o player tira no centro (o resto fica de véu)
MACHINE_CLEAR = 0.62
EDGE_AMP = 0.45                # ruído somado na máscara: bagunça a borda e põe manchas dentro da visão
BREATH = 0.05                  # o raio da visão "respira" ±5% devagar
MACHINE_VIEW_TILES = 2.5       # cada máquina da base abre isso de vista em volta dela
POD_VIEW_TILES = 3.0           # a cápsula (o coração da base) abre um pouco mais
FACING_BIAS = 10               # px: o centro da visão anda pra onde o player olha (igual helmet_lamp)
EYE_LIFT = 18                  # px: a visão sai da altura do capacete, não do pé
HOLE_BASE = 64                 # raio (células) do degradê de referência; os outros são escalas dele
HOLE_CACHE_MAX = 32

# ---- partículas ------------------------------------------------------------------------------------
MAX_GRAINS = 210
MAX_STREAKS = 40
MAX_PARTICLES = MAX_GRAINS + MAX_STREAKS      # 250
GRAIN_SPEED = (70.0, 170.0)    # px/s do mundo: (calmo, a mais na rajada cheia), vezes storm
STREAK_SPEED = (190.0, 260.0)  # px/s das faixas (bem mais rápidas que as nuvens: são elas que dão o "vento")
STREAK_LEN = (80, 250)
STREAK_ANGLES = 32             # direções da faixa em cache
STREAK_SHAPES = 6              # comprimentos/curvas diferentes


# ---- leitura do estado ------------------------------------------------------------------------------
def storm_of(state) -> float:
    """Intensidade da tempestade pro visual: a mesma do jogo (0 na caverna), limitada a 0..1."""
    return max(0.0, min(1.0, storm_level(state)))


def weather_of(state) -> tuple[tuple[float, float], float, float]:
    """(vento, rajada 0..1, visão em tiles), do state.weather."""
    w = state.weather
    return tuple(w.wind), float(w.gust), float(w.view_tiles)


def static_amount(state) -> float:
    """Quanto o scanner chia (0..1): rajada × tempestade."""
    storm = storm_of(state)
    if storm <= 0:
        return 0.0
    return max(0.0, min(1.0, state.weather.gust * storm))


def vision_lights(state, cam, view_px: float) -> list[tuple[float, float, float]]:
    """Pontos que abrem a vista, em px da visão: [(x, y, raio)]. O primeiro é sempre o player."""
    p = state.player
    dx, dy = FACING_DIR.get(p.facing, (0, 0))
    out = [(*viewport.world_to_canvas((p.x + dx * FACING_BIAS, p.y - EYE_LIFT + dy * FACING_BIAS), cam, 1.0),
            view_px)]
    if not state.active.has_base:
        return out
    px, py = C.POD_ANCHOR
    out.append((*viewport.world_to_canvas((px, py - T), cam, 1.0), POD_VIEW_TILES * T))
    for m in state.machines:
        if m.is_chest:
            continue
        tiles = C.LAMP_RADIUS.get(m.kind, MACHINE_VIEW_TILES) if m.is_lamp else MACHINE_VIEW_TILES
        ax, ay = m.anchor
        out.append((*viewport.world_to_canvas((ax, ay - T / 2 - (T / 2 if m.size > 1 else 0)), cam, 1.0), tiles * T))
    return out


# ---- ruído ------------------------------------------------------------------------------------------
def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def fbm_noise(size: int = NOISE_SIZE, seed: int = NOISE_SEED, periods=(64, 32, 16, 8),
              weights=(0.3, 0.36, 0.22, 0.12)) -> list[list[float]]:
    """Ruído de valor fbm LADRILHÁVEL (size×size, 0..1): a grade de cada oitava dá a volta no ladrilho."""
    rng = random.Random(seed)
    out = [[0.0] * size for _ in range(size)]
    for period, weight in zip(periods, weights):
        n = size // period
        lattice = [[rng.random() for _ in range(n)] for _ in range(n)]
        for y in range(size):
            gy, fy = divmod(y / period, 1.0)
            y0, y1 = int(gy) % n, (int(gy) + 1) % n
            sy = _smooth(fy)
            row0, row1, orow = lattice[y0], lattice[y1], out[y]
            for x in range(size):
                gx, fx = divmod(x / period, 1.0)
                x0, x1 = int(gx) % n, (int(gx) + 1) % n
                sx = _smooth(fx)
                top = row0[x0] + (row0[x1] - row0[x0]) * sx
                bot = row1[x0] + (row1[x1] - row1[x0]) * sx
                orow[x] += weight * (top + (bot - top) * sy)
    return out


def _contrast(v: float) -> float:
    """Puxa o fbm (que vive perto de 0,5) pras pontas: manchas com forma, não um cinza uniforme."""
    return _smooth(max(0.0, min(1.0, (v - 0.34) / 0.32)))


_NOISE_CACHE: dict[tuple, pygame.Surface] = {}


def noise_tile(kind: str) -> pygame.Surface:
    """Ladrilho SRCALPHA (NOISE_SIZE de lado) de uma camada. Em cache no módulo.
    kind: "add" (nuvem densa: alfa + clareia), "sub" (véu ralo: alfa − escurece), "detail" (manchas finas,
    só escurece) e "edge" (ruído da máscara)."""
    tile = _NOISE_CACHE.get(kind)
    if tile is not None:
        return tile
    if "noise" not in _NOISE_CACHE:
        field = fbm_noise()
        base = pygame.Surface((NOISE_SIZE, NOISE_SIZE), pygame.SRCALPHA)
        for y, row in enumerate(field):
            for x, v in enumerate(row):
                a = round(255 * _contrast(v))
                base.set_at((x, y), (a, a, a, a))
        _NOISE_CACHE["noise"] = base
    base = _NOISE_CACHE["noise"]
    if kind == "add":         # as SMEAR cópias somam: cada uma leva 1/SMEAR (cor e alfa)
        src, rgb, amp = base, tuple(round(c / SMEAR) for c in CLOUD_LIGHT), CLOUD_AMP / SMEAR
    elif kind == "sub":       # outra parte do mesmo ruído: virado e transposto (continua ladrilhável)
        src = pygame.transform.flip(pygame.transform.rotate(base, 90), True, False)
        rgb, amp = tuple(round(c / SMEAR) for c in CLOUD_DARK), CLOUD_THIN / SMEAR
    elif kind == "detail":  # metade do tamanho = o dobro da frequência (continua ladrilhável); alfa 0: só escurece
        half = pygame.transform.scale(pygame.transform.flip(base, True, False), (NOISE_SIZE // 2, NOISE_SIZE // 2))
        src, rgb, amp = half, DETAIL_DARK, 0.0
    else:
        src, rgb, amp = pygame.transform.flip(base, True, True), (0, 0, 0), EDGE_AMP
    tile = pygame.Surface(src.get_size(), pygame.SRCALPHA)
    # canal a canal: cor = ruído × rgb/255, alfa = ruído × amp
    tile.fill((*rgb, round(255 * amp)))
    tile.blit(src, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    _NOISE_CACHE[kind] = tile
    return tile


def _blit_tiled(dst: pygame.Surface, tile: pygame.Surface, off: tuple[float, float], flags: int) -> None:
    """Cobre `dst` com `tile` repetido, com o ladrilho deslocado de `off` (células)."""
    tw, th = tile.get_size()
    w, h = dst.get_size()
    x0, y0 = -int(off[0] % tw), -int(off[1] % th)
    blit = dst.blit
    for y in range(y0, h, th):
        for x in range(x0, w, tw):
            blit(tile, (x, y), special_flags=flags)


# ---- camada de poeira -------------------------------------------------------------------------------
class DustLayer:
    """Poeira (nuvens + visão) numa superfície pequena, esticada suave. `noise=False` desliga as nuvens e o
    ruído da borda (só pros testes medirem o degradê)."""

    def __init__(self, cell: int = CELL, noise: bool = True):
        self.cell = cell
        self.noise = noise
        self.origin = (0, 0)           # onde o último render vai no target (≤ 0: grade presa no mundo)
        self.scroll_a = [0.0, 0.0]     # deslocamento das camadas de nuvem (px do mundo)
        self.scroll_b = [0.0, 0.0]
        self.time = 0.0
        self._last_t: float | None = None
        self._small: pygame.Surface | None = None
        self._mask: pygame.Surface | None = None
        self._big: pygame.Surface | None = None
        self._holes: dict[tuple[int, int], pygame.Surface] = {}
        self._hole_base: dict[int, pygame.Surface] = {}
        self._last = None

    # -- tempo --
    def tick(self, t: float, wind, storm: float, gust: float) -> None:
        """Avança pelo relógio do frame: dt = diferença do `t`, travado em 0,1 s."""
        dt = 0.0 if self._last_t is None else max(0.0, min(0.1, t - self._last_t))
        self._last_t = t
        self.advance(dt, wind, storm, gust)

    def advance(self, dt: float, wind, storm: float, gust: float) -> None:
        if dt <= 0 or storm <= 0:
            return
        self.time += dt
        g = max(0.0, min(1.0, gust))
        v = (CLOUD_SPEED[0] + CLOUD_SPEED[1] * g) * min(1.0, storm) * dt
        wx, wy = wind
        self.scroll_a[0] += wx * v
        self.scroll_a[1] += wy * v
        a = math.radians(CLOUD_B_TURN)
        bx, by = wx * math.cos(a) - wy * math.sin(a), wx * math.sin(a) + wy * math.cos(a)
        self.scroll_b[0] += bx * v * 0.6
        self.scroll_b[1] += by * v * 0.6

    # -- degradê de visão --
    def hole(self, r: int, clear: float) -> pygame.Surface:
        """Degradê de visão de raio `r` células (alfa a subtrair da máscara), contínuo. Em cache."""
        q = round(clear * 32)
        key = (r, q)
        tex = self._holes.get(key)
        if tex is None:
            base = self._hole_base.get(q)
            if base is None:
                base = self._hole_base[q] = self._make_hole(HOLE_BASE, q / 32)
            if len(self._holes) >= HOLE_CACHE_MAX:
                self._holes.clear()
            tex = self._holes[key] = pygame.transform.smoothscale(base, (2 * r, 2 * r))
        return tex

    @staticmethod
    def _make_hole(r: int, clear: float) -> pygame.Surface:
        size = 2 * r
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        for j in range(size):
            for i in range(size):
                d = math.hypot(i + 0.5 - r, j + 0.5 - r) / r
                if d >= 1:
                    continue
                k = 1.0 - _smooth(max(0.0, (d - VIEW_INNER) / (1 - VIEW_INNER)))
                surf.set_at((i, j), (0, 0, 0, round(255 * clear * k)))
        return surf

    # -- montagem --
    def render(self, view_size: tuple[int, int], storm: float, gust: float, view_px: float, lights,
               player: tuple[float, float], cam: tuple[float, float] = (0, 0),
               wind=(1.0, 0.0)) -> pygame.Surface | None:
        """Superfície SRCALPHA da poeira (já esticada) ou None sem tempestade. `player`, `lights`
        [(x, y, raio)] e `view_px` em px da visão. Vai no target em `self.origin`."""
        if storm <= 0:
            return None
        storm = min(1.0, storm)
        gust = max(0.0, min(1.0, gust))
        cell = self.cell
        w, h = view_size
        ox, oy = -int(cam[0] % cell), -int(cam[1] % cell)
        sw, sh = (w - ox + cell - 1) // cell, (h - oy + cell - 1) // cell
        if self._small is None or self._small.get_size() != (sw, sh):
            self._small = pygame.Surface((sw, sh), pygame.SRCALPHA)
            self._mask = pygame.Surface((sw, sh), pygame.SRCALPHA)
            self._big = pygame.Surface((sw * cell, sh * cell), pygame.SRCALPHA)
        small, mask = self._small, self._mask
        gx0, gy0 = math.floor(cam[0] / cell), math.floor(cam[1] / cell)    # célula do mundo no canto

        # 1. densidade: fundo + nuvem densa (soma) + véu ralo (subtrai), borrados ao longo do vento
        small.fill((*DUST_COLOR, round(255 * (DENSITY_BASE + DENSITY_GUST * gust))))
        if self.noise:
            sx, sy = wind[0] * SMEAR_STEP, wind[1] * SMEAR_STEP
            add, sub = noise_tile("add"), noise_tile("sub")
            ax, ay = gx0 - self.scroll_a[0] / cell, gy0 - self.scroll_a[1] / cell
            bx, by = gx0 - self.scroll_b[0] / cell, gy0 - self.scroll_b[1] / cell
            for k in range(SMEAR):
                _blit_tiled(small, add, (ax + k * sx, ay + k * sy), pygame.BLEND_RGBA_ADD)
                _blit_tiled(small, sub, (bx + k * sx + 61, by + k * sy + 37), pygame.BLEND_RGBA_SUB)
            dx, dy = gx0 - self.scroll_a[0] * 1.4 / cell, gy0 - self.scroll_a[1] * 1.4 / cell   # anda mais rápido
            _blit_tiled(small, noise_tile("detail"), (dx + 13, dy + 5), pygame.BLEND_RGBA_SUB)

        # 2. visibilidade: máscara branca, os pontos de vista tiram um degradê, o ruído bagunça a borda
        mask.fill((255, 255, 255, 255))
        breath = 1.0 + BREATH * math.sin(self.time * 0.7)
        max_r = sw + sh
        sub_flag = pygame.BLEND_RGBA_SUB
        for i, (x, y, radius) in enumerate(((player[0], player[1], view_px), *lights)):
            if not math.isfinite(radius):
                radius = max_r * cell
            reach = radius * VIEW_REACH * (breath if i == 0 else 1.0)
            r = max(2, min(max_r, round(reach / cell)))
            cx, cy = int((x - ox) // cell), int((y - oy) // cell)
            if cx + r < 0 or cy + r < 0 or cx - r >= sw or cy - r >= sh:
                continue                                # fora da tela
            mask.blit(self.hole(r, PLAYER_CLEAR if i == 0 else MACHINE_CLEAR), (cx - r, cy - r), special_flags=sub_flag)
        if self.noise:
            ex, ey = gx0 - self.scroll_a[0] * 0.8 / cell + 23, gy0 - self.scroll_a[1] * 0.8 / cell + 91
            _blit_tiled(mask, noise_tile("edge"), (ex, ey), pygame.BLEND_RGBA_ADD)
        small.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if storm < 1.0:                                 # saindo da tempestade: tudo afina junto
            small.fill((255, 255, 255, round(255 * storm)), special_flags=pygame.BLEND_RGBA_MULT)

        self.origin = (ox, oy)
        self._last = (cam, ox, oy)
        big = self._big
        pygame.transform.smoothscale(small, big.get_size(), big)
        return big

    def apply(self, target: pygame.Surface, cam, storm: float, gust: float, view_px: float, lights,
              player, particles: DustParticles | None = None, wind=(1.0, 0.0)) -> None:
        """Desenha a poeira (e as partículas, se vierem) em `target`. Sem tempestade não faz nada."""
        surf = self.render(target.get_size(), storm, gust, view_px, lights, player, cam, wind)
        if surf is None:
            return
        if particles is not None:
            particles.draw(surf, cam, self.origin, wind, storm, gust)
        target.blit(surf, self.origin)


# ---- partículas e faixas de vento ------------------------------------------------------------------
class DustParticles:
    """Grãos e faixas de poeira andando com o vento. As posições ficam num "espaço de dobra" do mundo e
    são desenhadas com módulo do tamanho da visão: andar com a câmera dá paralaxe sem precisar repor."""

    def __init__(self, seed: int = 0):
        rng = random.Random(seed)
        span = 4096.0
        # grão: [x, y, fator de velocidade, tom, tamanho, fase do balanço]
        self.grains = [[rng.random() * span, rng.random() * span, rng.uniform(0.6, 1.3), rng.choice((0, 0, 1, 2)),
                        1 + (rng.random() < 0.25), rng.random() * math.tau] for _ in range(MAX_GRAINS)]
        # faixa: [x, y, fator de velocidade, forma, alfa]
        self.streaks = [[rng.random() * span, rng.random() * span, rng.uniform(0.75, 1.25),
                         rng.randrange(STREAK_SHAPES), rng.randrange(50, 105)] for _ in range(MAX_STREAKS)]
        self.time = 0.0
        self._last_t: float | None = None
        self._streak_tex: dict[tuple[int, int, int], pygame.Surface] = {}

    @staticmethod
    def counts(storm: float, gust: float) -> tuple[int, int]:
        if storm <= 0:
            return 0, 0
        g = max(0.0, min(1.0, gust))
        s = min(1.0, storm)
        return round(MAX_GRAINS * s * (0.55 + 0.45 * g)), round(MAX_STREAKS * s * (0.35 + 0.65 * g))

    def count(self, storm: float, gust: float) -> int:
        """Quantas partículas (grãos + faixas) aparecem com essa tempestade e rajada (≤ MAX_PARTICLES)."""
        return sum(self.counts(storm, gust))

    def tick(self, t: float, wind, storm: float, gust: float) -> None:
        """Avança pelo relógio do frame (o Renderer só tem o `t`): dt = diferença, travado em 0,1 s."""
        dt = 0.0 if self._last_t is None else max(0.0, min(0.1, t - self._last_t))
        self._last_t = t
        self.update(dt, wind, storm, gust)

    def update(self, dt: float, wind, storm: float, gust: float) -> None:
        if storm <= 0 or dt <= 0:
            return
        self.time += dt
        wx, wy = wind
        g = max(0.0, min(1.0, gust))
        s = min(1.0, storm)
        speed = (GRAIN_SPEED[0] + GRAIN_SPEED[1] * g) * s
        px, py = -wy, wx                               # perpendicular: o balanço dos grãos
        tm = self.time
        for gr in self.grains:
            v = speed * gr[2] * dt
            wob = math.sin(tm * 3.1 + gr[5]) * 9 * dt
            gr[0] += wx * v + px * wob
            gr[1] += wy * v + py * wob
        v = (STREAK_SPEED[0] + STREAK_SPEED[1] * g) * s * dt
        for st in self.streaks:
            st[0] += wx * v * st[2]
            st[1] += wy * v * st[2]

    def streak(self, angle_step: int, shape: int, alpha: int) -> pygame.Surface:
        """Faixa longa e fina, levemente curva, que acende e apaga nas pontas. Em cache por direção."""
        key = (angle_step, shape, alpha // 20)
        tex = self._streak_tex.get(key)
        if tex is not None:
            return tex
        rng = random.Random(shape * 977 + 3)
        length = rng.uniform(*STREAK_LEN)
        bow = rng.uniform(0.04, 0.09) * length * (1 if shape % 2 else -1)
        a = angle_step / STREAK_ANGLES * math.tau
        ca, sa = math.cos(a), math.sin(a)
        n = max(8, int(length / 6))
        pts = []
        for i in range(n + 1):
            u = i / n
            x, y = (u - 0.5) * length, bow * 4 * u * (1 - u) - bow / 2
            pts.append((x * ca - y * sa, x * sa + y * ca))
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0 = min(xs) - 1, min(ys) - 1
        tex = pygame.Surface((int(max(xs) - x0) + 3, int(max(ys) - y0) + 3), pygame.SRCALPHA)
        tex.fill((0, 0, 0, 0))                       # preto transparente: no MAX não mexe na poeira em volta
        peak = (alpha // 20) * 20 + 10
        for i in range(n):
            u = (i + 0.5) / n
            k = math.sin(math.pi * u) ** 1.5
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            pygame.draw.line(tex, (*STREAK_COLOR, round(peak * k)), (ax - x0, ay - y0), (bx - x0, by - y0))
        self._streak_tex[key] = tex
        return tex

    def draw(self, surf: pygame.Surface, cam, origin, wind, storm: float, gust: float) -> None:
        """Desenha na camada de poeira `surf` (que vai no target em `origin`). Faixas com BLEND_RGBA_MAX
        (clareiam e nunca diminuem o alfa da poeira); grãos opacos por cima."""
        n_grains, n_streaks = self.counts(storm, gust)
        if not n_grains and not n_streaks:
            return
        w, h = surf.get_size()
        cx, cy = cam[0] + origin[0], cam[1] + origin[1]   # canto da camada no mundo
        if n_streaks:
            step = round(math.atan2(wind[1], wind[0]) / math.tau * STREAK_ANGLES) % STREAK_ANGLES
            blit = surf.blit
            mx = pygame.BLEND_RGBA_MAX
            pad = STREAK_LEN[1]
            for x, y, _, shape, alpha in self.streaks[:n_streaks]:
                tex = self.streak(step, shape, alpha)
                px = (x - cx) % (w + 2 * pad) - pad
                py = (y - cy) % (h + 2 * pad) - pad
                blit(tex, (int(px) - tex.get_width() // 2, int(py) - tex.get_height() // 2), special_flags=mx)
        a = round(150 + 90 * min(1.0, storm))
        tones = [(*c, a) for c in GRAIN_TONES]
        fill = surf.fill
        for x, y, _, tone, size, _ in self.grains[:n_grains]:
            fill(tones[tone], (int((x - cx) % w), int((y - cy) % h), size, size))
