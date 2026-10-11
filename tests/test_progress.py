"""Quanto falta pro próximo estágio: progresso relativo, tempo estimado e formatação."""

import random

import pytest

from game import config as C
from game.systems import Controls, GameState, eta_label, format_eta, smooth_rate, stage_progress
from tests.helpers import give


def test_progress_stage1_goes_from_0_to_10k():
    nxt, frac, left = stage_progress(0)
    assert nxt.name == "NÉVOA" and frac == 0 and left == 10_000
    nxt, frac, left = stage_progress(2_500)
    assert frac == pytest.approx(0.25) and left == 7_500


def test_progress_is_relative_to_current_stage():
    nxt, frac, left = stage_progress(12_914)          # exemplo do dono
    assert nxt.name == "VERDE"
    assert frac == pytest.approx((12_914 - 10_000) / 90_000)   # ~3%
    assert round(frac * 100) == 3
    assert left == 87_086


def test_progress_at_thresholds():
    assert stage_progress(10_000)[0].name == "VERDE"
    assert stage_progress(10_000)[1] == 0
    assert stage_progress(9_999.9)[0].name == "NÉVOA"
    assert stage_progress(100_000) == (None, 1.0, 0.0)          # estágio 3: acabou
    assert stage_progress(250_000) == (None, 1.0, 0.0)


def test_eta_with_zero_rate():
    assert eta_label(10_000, 0) == "coloque máquinas"


def test_eta_example():
    assert eta_label(87_086, 29) == "~50 min (ritmo atual)"   # deixa claro que não é previsão


@pytest.mark.parametrize("seconds,text", [
    (0.2, "~1 s"), (45, "~45 s"), (59.4, "~59 s"), (60, "~1 min"), (12 * 60 + 10, "~12 min"),
    (59 * 60 + 20, "~59 min"), (3600, "~1 h"), (80 * 60, "~1 h 20 min"), (2 * 3600 + 29, "~2 h"),
])
def test_format_eta(seconds, text):
    assert format_eta(seconds) == text


def test_smoothed_rate_does_not_jump_and_converges():
    r = smooth_rate(0, 10, 1 / 60)
    assert 0 < r < 1                         # um frame depois ainda está longe do alvo
    for _ in range(60 * 30):                 # 30 s = 10× a "memória" de 3 s
        r = smooth_rate(r, 10, 1 / 60)
    assert r == pytest.approx(10, abs=0.01)


def test_game_rate_counts_time_scale():
    game = GameState(rng=random.Random(1))
    give(game, iron=10, silicon=4)
    game.craft("o2")
    px, py = game.player.tile
    game.place("o2", (px + 2, py))
    game.toggle_time_scale()                 # F1: ×10
    for _ in range(60 * 20):
        game.update(1 / 60, Controls())
    assert game.smoothed_rate == pytest.approx(3 * C.DEBUG_TIME_SCALE, rel=0.01)


def test_pixel_digits_font_measures_and_renders():
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.font.init()
    from game.assets import load_font
    from game.ui import DIGIT_ADVANCE, PixelDigitsFont
    font = PixelDigitsFont(load_font("PixelifySans.ttf", 11, 13))
    assert font._runs("Ti 500 ok") == ["Ti ", "500", " ok"]
    w, h = font.size("Ti 500")
    assert w == font.font.size("Ti ")[0] + 3 * DIGIT_ADVANCE
    img = font.render("Ti 500", False, (255, 255, 255))
    assert img.get_size() == (w, h)
    assert font.render("sem número", False, (255, 255, 255)).get_width() == font.size("sem número")[0]
