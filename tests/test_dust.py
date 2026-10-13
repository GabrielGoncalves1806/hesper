"""Visual da tempestade (v0.4 Marco 1, trilha C): nuvens de poeira, visão sem borda de círculo, faixas e
grãos de vento, e o chiado do scanner."""

import math
import os
from itertools import pairwise

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import dust
from game.dust import DustLayer, DustParticles
from game.systems import GameState, Machine
from game.ui import static_noise

pygame.init()
VIEW = (480, 270)
MID = (240, 135)


def alpha_ring(surf, center, radius, n=48) -> float:
    """Alfa médio num círculo de raio `radius` em volta de `center`."""
    vals = []
    for i in range(n):
        a = i / n * math.tau
        x, y = round(center[0] + math.cos(a) * radius), round(center[1] + math.sin(a) * radius)
        if 0 <= x < surf.get_width() and 0 <= y < surf.get_height():
            vals.append(surf.get_at((x, y)).a)
    return sum(vals) / len(vals)


def mean_alpha(surf, step=6) -> float:
    w, h = surf.get_size()
    vals = [surf.get_at((x, y)).a for x in range(0, w, step) for y in range(0, h, step)]
    return sum(vals) / len(vals)


# ---- leitura do estado ------------------------------------------------------------------------------
def test_storm_level_is_zero_in_cave():
    s = GameState()
    s.storm = 1.0
    assert dust.storm_of(s) == 1.0
    s.enter_layer("cave")
    assert dust.storm_of(s) == 0.0 and dust.static_amount(s) == 0.0


def test_weather_comes_from_state_weather():
    s = GameState()
    s.weather.gust = 0.8
    wind, gust, view = dust.weather_of(s)
    assert wind == tuple(s.weather.wind) and gust == 0.8 and view == s.weather.view_tiles


def test_vision_center_leans_where_the_player_faces():
    s = GameState()
    p = s.player
    p.direction = "right"
    (x, y, r), *_ = dust.vision_lights(s, (0, 0), 7 * C.TILE)
    assert x == pytest.approx(p.x + dust.FACING_BIAS) and y == pytest.approx(p.y - 18) and r == 7 * C.TILE


def test_vision_lights_include_base_machines_but_not_chests():
    s = GameState()
    s.machines = [Machine("o2", C.BASE_TILE[0] + 3, C.BASE_TILE[1] + 2),
                  Machine("chest", C.BASE_TILE[0] - 3, C.BASE_TILE[1] + 2)]
    lights = dust.vision_lights(s, (0, 0), 7 * C.TILE)
    assert dust.MACHINE_VIEW_TILES * C.TILE in [r for _, _, r in lights[1:]]
    assert len(lights) == 3                             # player + cápsula + o2 (o baú não abre a vista)


# ---- C1: camada de poeira ---------------------------------------------------------------------------
def test_no_dust_when_storm_is_zero():
    surf = DustLayer().render(view_size=VIEW, storm=0.0, gust=0.0, view_px=224, lights=[], player=MID)
    assert surf is None


def test_near_player_is_veiled_but_much_clearer_than_far():
    surf = DustLayer().render(VIEW, 1.0, 0.0, 7 * C.TILE, [], MID)
    assert surf.get_flags() & pygame.SRCALPHA
    near, far = alpha_ring(surf, MID, 8), mean_alpha(surf.subsurface((0, 0, 60, 60)))
    assert near < 0.65 * far and far > 100
    assert near > 10                                    # ainda tem véu perto do player (não é um furo)


def test_vision_gradient_is_continuous_without_rings():
    """Sem as nuvens, o alfa do centro pra fora sobe aos poucos: nenhum degrau grande (os anéis da v1)."""
    surf = DustLayer(noise=False).render(VIEW, 1.0, 0.0, 7 * C.TILE, [], MID)
    line = [surf.get_at((MID[0] + dx, MID[1])).a for dx in range(239)]
    jumps = [abs(b - a) for a, b in pairwise(line)]
    assert max(jumps) <= 8, max(jumps)
    assert line[-1] - line[0] > 60                      # e ainda assim vai do véu até a poeira cheia


def test_dust_density_varies_like_clouds():
    surf = DustLayer().render(VIEW, 1.0, 0.0, 2 * C.TILE, [], (-500, -500))    # sem visão na tela
    vals = [surf.get_at((x, y)).a for x in range(0, 480, 8) for y in range(0, 270, 8)]
    assert max(vals) - min(vals) > 60                   # manchas mais densas e mais ralas
    colors = {surf.get_at((x, y))[:3] for x in range(0, 480, 16) for y in range(0, 270, 16)}
    assert len(colors) > 10                             # e a cor também varia (clara e escura)


def test_clouds_move_with_the_wind():
    layer = DustLayer()
    a = layer.render(VIEW, 1.0, 0.0, 2 * C.TILE, [], (-500, -500)).copy()
    layer.advance(1.0, (1.0, 0.0), 1.0, 0.0)
    b = layer.render(VIEW, 1.0, 0.0, 2 * C.TILE, [], (-500, -500))
    diff = sum(1 for x in range(0, 480, 8) for y in range(0, 270, 8) if a.get_at((x, y)) != b.get_at((x, y)))
    assert diff > 100
    # e a rajada acelera as nuvens
    calm, windy = DustLayer(), DustLayer()
    calm.advance(1.0, (1.0, 0.0), 1.0, 0.0)
    windy.advance(1.0, (1.0, 0.0), 1.0, 1.0)
    assert windy.scroll_a[0] > calm.scroll_a[0] > 0


def test_opacity_follows_storm_and_grows_with_gust():
    calm = mean_alpha(DustLayer().render(VIEW, 1.0, 0.0, 7 * C.TILE, [], MID))
    gust = mean_alpha(DustLayer().render(VIEW, 1.0, 1.0, 7 * C.TILE, [], MID))
    half = mean_alpha(DustLayer().render(VIEW, 0.5, 0.0, 7 * C.TILE, [], MID))
    assert gust > calm + 10
    assert abs(half - calm / 2) < 4


def test_view_radius_shrinks_in_gust():
    wide = DustLayer().render(VIEW, 1.0, 0.0, C.STORM_VIEW_TILES * C.TILE, [], MID)
    narrow = DustLayer().render(VIEW, 1.0, 0.0, C.STORM_GUST_VIEW_TILES * C.TILE, [], MID)
    assert alpha_ring(narrow, MID, 4 * C.TILE) > alpha_ring(wide, MID, 4 * C.TILE) + 30


def test_machines_open_the_view():
    far = (420, 135)
    without = DustLayer(noise=False).render(VIEW, 1.0, 0.0, 3 * C.TILE, [], (60, 135))
    with_m = DustLayer(noise=False).render(VIEW, 1.0, 0.0, 3 * C.TILE, [(420, 135, 2.5 * C.TILE)], (60, 135))
    assert with_m.get_at(far).a < 0.6 * without.get_at(far).a


def test_huge_view_does_not_build_huge_textures():
    layer = DustLayer()
    surf = layer.render(VIEW, 0.3, 0.0, math.inf, [], MID)
    assert surf is not None
    assert all(t.get_width() <= 4 * (480 + 270) for t in layer._holes.values())


# ---- C2: partículas e faixas de vento ---------------------------------------------------------------
def test_particle_count_is_zero_without_storm_and_capped_in_full_gust():
    p = DustParticles(seed=1)
    assert p.count(0.0, 0.0) == 0 and p.count(0.0, 1.0) == 0
    assert 0 < p.count(1.0, 0.0) < p.count(1.0, 1.0) <= dust.MAX_PARTICLES == 250
    assert p.counts(1.0, 1.0)[1] > 2 * p.counts(1.0, 0.0)[1]     # rajada: bem mais faixas


def test_streaks_are_long_thin_and_curved():
    p = DustParticles(seed=1)
    for shape in range(dust.STREAK_SHAPES):
        tex = p.streak(0, shape, 100)                    # vento pra leste: faixa deitada
        w, h = tex.get_size()
        assert dust.STREAK_LEN[0] <= w <= dust.STREAK_LEN[1] + 4
        assert 3 < h < 0.2 * w                           # curva, mas fina
        assert max(tex.get_at((x, y)).a for x in range(w) for y in range(h)) <= 140   # alfa baixo


def test_particles_move_with_the_wind_and_are_deterministic():
    a, b = DustParticles(seed=7), DustParticles(seed=7)
    for _ in range(30):
        a.update(1 / 60, (0.0, 1.0), 1.0, 0.5)
        b.update(1 / 60, (0.0, 1.0), 1.0, 0.5)
    assert a.grains == b.grains and a.streaks == b.streaks
    c = DustParticles(seed=7)
    y0 = [g[1] for g in c.grains]
    x0 = [g[0] for g in c.grains]
    c.update(0.5, (0.0, 1.0), 1.0, 0.0)
    assert all(g[1] > y for g, y in zip(c.grains, y0))       # vento pra baixo: tudo desce
    assert max(abs(g[0] - x) for g, x in zip(c.grains, x0)) < 10


def test_particles_do_not_move_without_storm():
    p = DustParticles(seed=3)
    before = [list(g) for g in p.grains]
    p.update(1.0, (1.0, 0.0), 0.0, 0.0)
    assert p.grains == before


def test_streaks_never_open_holes_in_the_dust():
    layer = DustLayer()
    surf = layer.render(VIEW, 1.0, 1.0, 224, [], MID)
    clear = surf.copy()
    p = DustParticles(seed=2)
    p.grains = []                                        # só as faixas
    p.draw(surf, (0, 0), (0, 0), (1.0, 0.0), 1.0, 1.0)
    changed = 0
    for x in range(0, 480, 2):
        for y in range(0, 270, 2):
            before, after = clear.get_at((x, y)), surf.get_at((x, y))
            assert after.a >= before.a
            changed += before != after
    assert changed > 20
    # e fora do traço a faixa não toca em nada (nada de "caixa" em volta dela na nuvem escura)
    tex = p.streak(round(0 / math.tau * dust.STREAK_ANGLES), 0, 100)
    assert tex.get_at((0, 0)) == (0, 0, 0, 0)


# ---- C3: chiado do minimapa e do mapa ---------------------------------------------------------------
def _changed(a: pygame.Surface, b: pygame.Surface) -> float:
    w, h = a.get_size()
    return sum(1 for x in range(w) for y in range(h) if a.get_at((x, y)) != b.get_at((x, y))) / (w * h)


def test_static_noise_zero_does_nothing():
    surf = pygame.Surface((96, 64), 0, 24)
    surf.fill((60, 90, 70))
    before = surf.copy()
    static_noise(surf, 0.0, 1.3)
    assert _changed(surf, before) == 0


def test_static_noise_full_changes_many_pixels():
    surf = pygame.Surface((96, 64), 0, 24)
    surf.fill((60, 90, 70))
    before = surf.copy()
    static_noise(surf, 1.0, 1.3)
    assert _changed(surf, before) > 0.05


def test_static_noise_scales_with_amount_and_moves_with_time():
    a = pygame.Surface((96, 64), 0, 24)
    a.fill((60, 90, 70))
    base = a.copy()
    low, high = a.copy(), a.copy()
    static_noise(low, 0.15, 2.0)
    static_noise(high, 1.0, 2.0)
    assert _changed(low, base) < _changed(high, base)
    later = a.copy()
    static_noise(later, 1.0, 2.5)
    assert _changed(later, high) > 0


def test_static_amount_needs_storm_and_gust():
    s = GameState()
    s.weather.gust = 1.0
    s.storm = 0.0
    assert dust.static_amount(s) == 0.0
    s.storm = 1.0
    assert dust.static_amount(s) == 1.0
    s.weather.gust = 0.0
    assert dust.static_amount(s) == 0.0
