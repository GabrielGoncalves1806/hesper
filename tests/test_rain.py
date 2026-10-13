"""v0.4 Marco 3 · M3.3: chuva (game/rain.py · bíblia §12, "Chuva e lagos").

Pancadas determinísticas pela seed, no estilo das rajadas do weather.py: na Névoa 30–60 s de chuva a cada
60–120 s (de começo a começo), no Verde mais curtas; intensidade 0..1 com 2 s de subida e descida; só na
superfície. Na tela, traços diagonais no ângulo do vento (≤ RAIN_MAX_DROPS)."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game.audio import rain_volume  # noqa: E402
from game.rain import Rain, RainDrops, rain_level  # noqa: E402
from game.systems import Controls, GameState  # noqa: E402

DT = 0.05


def run(rain: Rain, seconds: float, stage: int) -> tuple[list[float], list[float], list[float]]:
    """Anda a chuva e devolve (começos, durações, intensidades por passo)."""
    starts, lengths, values = [], [], []
    on_since = None
    for i in range(int(seconds / DT)):
        t = i * DT
        if rain.update(DT, stage):
            starts.append(t)
            on_since = t
        if on_since is not None and not rain.raining:
            lengths.append(t - on_since)
            on_since = None
        values.append(rain.intensity)
    return starts, lengths, values


def test_no_rain_before_the_mist():
    for stage in (C.STORM_STAGE, C.ARID_STAGE):
        r = Rain(1)
        starts, _, values = run(r, 900, stage)
        assert not starts and max(values) == 0.0


@pytest.mark.parametrize("seed", [1, 7, 42, 1234])
def test_mist_showers_follow_the_config(seed):
    starts, lengths, _ = run(Rain(seed), 1500, C.MIST_STAGE)
    assert len(starts) >= 8
    lo, hi = C.RAIN_FIRST
    assert lo - DT <= starts[0] <= hi + DT
    for a, b in zip(starts, starts[1:]):
        assert C.RAIN_MIST_EVERY[0] - DT <= b - a <= C.RAIN_MIST_EVERY[1] + DT
    for n in lengths:
        assert C.RAIN_MIST_LEN[0] - DT <= n <= C.RAIN_MIST_LEN[1] + DT


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_green_showers_are_shorter(seed):
    _, lengths, _ = run(Rain(seed), 1500, C.GREEN_STAGE)
    assert lengths
    assert max(lengths) <= C.RAIN_GREEN_LEN[1] + DT
    assert C.RAIN_GREEN_LEN[1] <= C.RAIN_MIST_LEN[0]


def test_same_seed_same_rain():
    a = run(Rain(5), 600, C.MIST_STAGE)
    b = run(Rain(5), 600, C.MIST_STAGE)
    assert a == b
    assert run(Rain(6), 600, C.MIST_STAGE)[0] != a[0]


def test_intensity_ramps_in_two_seconds():
    r = Rain(3)
    while not r.update(DT, C.MIST_STAGE):
        pass
    steps = 0
    while r.intensity < 1.0:
        r.update(DT, C.MIST_STAGE)
        steps += 1
        assert 0.0 < r.intensity <= 1.0
    assert abs((steps + 1) * DT - C.RAIN_RAMP) <= DT + 1e-9
    while r.raining:
        r.update(DT, C.MIST_STAGE)
    down = 0
    while r.intensity > 0.0:
        r.update(DT, C.MIST_STAGE)
        down += 1
    assert abs(down * DT - C.RAIN_RAMP) <= 2 * DT + 1e-9


def test_rain_only_on_the_surface():
    s = GameState(rng=random.Random(1))
    s.stage = C.MIST_STAGE
    s.rain.intensity = 0.7
    assert rain_level(s) == 0.7
    s.enter_layer("cave")
    assert rain_level(s) == 0.0


def test_game_state_runs_the_rain():
    s = GameState(rng=random.Random(1))
    s.stage = C.MIST_STAGE
    s.rain.next_shower = 0.01
    s.update(DT, Controls())
    assert s.rain.raining
    assert ("rain", True) in s.pop_events()


def test_rain_volume_is_the_intensity():
    assert rain_volume(0.0) == 0.0
    assert rain_volume(0.5) == pytest.approx(0.5 * C.VOLUME["amb_rain"])
    assert rain_volume(1.0) == pytest.approx(C.VOLUME["amb_rain"])
    assert rain_volume(3.0) == pytest.approx(C.VOLUME["amb_rain"])


# ---------------------------------------------------------------- traços na tela
def test_drop_count_follows_intensity_and_has_a_cap():
    d = RainDrops(seed=1)
    assert d.count(0.0) == 0
    assert 0 < d.count(0.3) < d.count(1.0) <= C.RAIN_MAX_DROPS


def test_draw_paints_streaks_only_with_rain():
    pygame.init()
    canvas = pygame.Surface((320, 180))
    d = RainDrops(seed=1)
    canvas.fill((10, 10, 10))
    d.draw(canvas, 0.0, (1.0, 0.0), 1.0)
    assert pygame.image.tobytes(canvas, "RGB") == bytes([10]) * (320 * 180 * 3)
    d.draw(canvas, 1.0, (1.0, 0.0), 1.0)
    assert pygame.image.tobytes(canvas, "RGB") != bytes([10]) * (320 * 180 * 3)


def test_streaks_lean_with_the_wind():
    d = RainDrops(seed=1)
    right, left = d.velocity((1.0, 0.0)), d.velocity((-1.0, 0.0))
    assert right[1] > 0 and left[1] > 0                   # sempre caindo
    assert right[0] > 0 > left[0]                         # e tortos pro lado do vento
    assert d.velocity((0.0, 1.0))[0] == pytest.approx(0.0)
