"""Contas de tela (game/viewport.py): janela -> canvas com tarja preta, canvas <-> mundo com zoom."""

import pytest

from game import config as C
from game import viewport as V


def test_letterbox_exact_multiple_fills_window():
    assert V.letterbox((960, 540)) == (0, 0, 960, 540)
    assert V.letterbox((1920, 1080)) == (0, 0, 1920, 1080)


def test_letterbox_wider_monitor_gets_side_bars():
    # 2560×1080 (21:9): altura manda, sobra dos lados
    assert V.letterbox((2560, 1080)) == (320, 0, 1920, 1080)


def test_letterbox_taller_monitor_gets_top_bars():
    # 1512×982 (MacBook 14"): largura manda, escala 1,575 (não inteira)
    x, y, w, h = V.letterbox((1512, 982))
    assert (x, w) == (0, 1512)
    assert h == round(540 * 1512 / 960) and y == (982 - h) // 2


def test_window_to_canvas_integer_scale():
    assert V.window_to_canvas((0, 0), (1920, 1080)) == (0, 0)
    assert V.window_to_canvas((1000, 500), (1920, 1080)) == (500, 250)
    assert V.window_to_canvas((1919, 1079), (1920, 1080)) == (959, 539)


def test_window_to_canvas_with_letterbox():
    # 2560×1080: canvas começa em x=320 e tem escala 2
    assert V.window_to_canvas((320, 0), (2560, 1080)) == (0, 0)
    assert V.window_to_canvas((320 + 960, 540), (2560, 1080)) == (480, 270)
    # em cima da tarja preta: gruda na borda
    assert V.window_to_canvas((10, 500), (2560, 1080)) == (0, 250)
    assert V.window_to_canvas((2550, 500), (2560, 1080)) == (959, 250)


def test_window_to_canvas_non_integer_scale():
    x, y, w, h = V.letterbox((1512, 982))
    mid = V.window_to_canvas((x + w / 2, y + h / 2), (1512, 982))
    assert mid == (480, 270)


def test_view_size_per_zoom():
    assert V.view_size(1.0) == (C.SCREEN_W, C.SCREEN_H)
    assert V.view_size(2.0) == (480, 270)
    assert V.view_size(1.5) == (640, 360)
    assert V.view_size(0.75) == (1280, 720)


@pytest.mark.parametrize("zoom", C.ZOOM_LEVELS)
def test_canvas_world_roundtrip(zoom):
    cam = (1234, 987)
    world = V.canvas_to_world((300, 200), cam, zoom)
    assert world == pytest.approx((cam[0] + 300 / zoom, cam[1] + 200 / zoom))
    assert V.world_to_canvas(world, cam, zoom) == pytest.approx((300, 200))


def test_canvas_center_hits_same_world_point_when_camera_follows():
    """Com a câmera centrada num ponto, o centro da tela aponta pra ele em qualquer zoom."""
    target = (2000.0, 1500.0)
    for zoom in C.ZOOM_LEVELS:
        vw, vh = V.view_size(zoom)
        cam = (target[0] - vw / 2, target[1] - vh / 2)
        assert V.canvas_to_world((C.SCREEN_W / 2, C.SCREEN_H / 2), cam, zoom) == pytest.approx(target)


def test_step_zoom_stops_at_ends():
    assert V.step_zoom(1.0, 1) == 1.5
    assert V.step_zoom(1.5, 1) == 2.0
    assert V.step_zoom(2.0, 1) == 2.0
    assert V.step_zoom(1.0, -1) == 0.75
    assert V.step_zoom(0.75, -1) == 0.75
    assert V.step_zoom(1.2, 1) == 1.5          # fora da lista: vai pro mais perto e anda


def test_camera_uses_view_size():
    """A câmera centra o player na visão do zoom, e mouse no centro da tela cai no player."""
    import random

    from game.render import Renderer
    from game.systems import GameState
    game = GameState(rng=random.Random(1))
    p = game.player
    for zoom in C.ZOOM_LEVELS:
        view = V.view_size(zoom)
        cam = Renderer.camera(game, view)
        wx, wy = V.canvas_to_world((C.SCREEN_W / 2, C.SCREEN_H / 2), cam, zoom)
        assert abs(wx - p.x) <= 1 and abs(wy - (p.y - 16)) <= 1
    # encostado no canto do mapa: a visão não sai do mundo
    p.x, p.y = 10.0, 10.0
    assert Renderer.camera(game, V.view_size(0.75)) == (0, 0)
    p.x, p.y = game.world.width * C.TILE - 5, game.world.height * C.TILE - 5
    vw, vh = V.view_size(0.75)
    assert Renderer.camera(game, (vw, vh)) == (game.world.width * C.TILE - vw, game.world.height * C.TILE - vh)
