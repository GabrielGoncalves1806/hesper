"""Contador de desempenho (F5): FPS da janela, média e pior quadro de trabalho, cor pelo orçamento."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game.perf_meter import PerfMeter  # noqa: E402


def feed(m: PerfMeter, n: int, dt: float, work: float) -> None:
    for _ in range(n):
        m.add(dt, work)


def test_averages_and_worst_over_the_window():
    m = PerfMeter()
    feed(m, 29, 1 / 60, 5.0)
    m.add(1 / 60, 12.0)                     # fecha a janela de 0,5 s (30 quadros a 60 FPS)
    assert round(m.fps) == 60
    assert abs(m.avg_ms - (29 * 5 + 12) / 30) < 1e-9 and m.worst_ms == 12.0
    assert m.text().startswith("60 FPS · 5,2 ms (pior 12,0)")


def test_color_follows_the_budget():
    m = PerfMeter()
    feed(m, 30, 1 / 60, 5.0)
    assert m.color() == C.C_OK
    feed(m, 30, 1 / 60, 12.0)
    assert m.color() != C.C_OK
    feed(m, 30, 1 / 60, 20.0)
    assert m.color() == "#ff6a55"


def test_toggle_and_draw_in_the_bottom_left():
    pygame.init()
    win = pygame.display.set_mode((320, 200))
    m = PerfMeter()
    feed(m, 30, 1 / 60, 5.0)
    m.visible = True
    win.fill((0, 0, 0))
    m.draw(win)
    assert win.get_at((10, 190))[:3] != (0, 0, 0)     # pintou o canto de baixo à esquerda
    m.toggle()
    win.fill((0, 0, 0))
    m.draw(win)
    assert win.get_at((10, 190))[:3] == (0, 0, 0)
