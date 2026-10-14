"""Render só do mundo (sem HUD): renderer.draw num canvas, repetido pra o chão assado terminar."""
import pygame
from common import *  # noqa
from game import viewport  # noqa: F401


def render_world(bot, cam, size=(960, 540), passes=60):
    app, s = bot.app, bot.state
    canvas = pygame.Surface(size)
    for _ in range(passes):
        app.renderer.draw(canvas, s, cam, app.t, None)
    return canvas


def cam_for(state, center_tile, size=(960, 540)):
    """cam (canto sup. esq. em px do mundo) centralizando um tile, com os limites do mapa."""
    vw, vh = size
    cx = int(center_tile[0] * C.TILE - vw // 2)
    cy = int(center_tile[1] * C.TILE - vh // 2)
    max_x = state.world.width * C.TILE - vw
    max_y = state.world.height * C.TILE - vh
    return (min(max(0, cx), max_x), min(max(0, cy), max_y))
