"""v0.6 Fundo M1: rocha dura (a nv.1 não quebra, o F3 quebra), dica, cores e o visual provisório por região.

A caverna aqui é SINTÉTICA (um World 40×40 montado na mão), pra o teste não depender do gerador (game/cave_gen.py):
faixas de região em `cave_region` (basalto a oeste, centro no meio, salar a leste, gelo nas 10 linhas de cima) e
tiles conhecidos em lugares conhecidos (ver `HARD`, `FROST_ICE`, `COPPER_AT`, `PLAIN_ROCK`)."""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import cave_rocks, hills, layers, minimap, settings  # noqa: E402
from game import config as C  # noqa: E402
from game.geo import BASALT, FROST, PLATEAU, SALAR  # noqa: E402
from game.systems import GameState  # noqa: E402
from game.world import World  # noqa: E402

SIZE = 40
HARD = (5, 20)          # rocha dura, basalto
FROST_ICE = (8, 5)      # minério de gelo dentro do gelo (duro)
COPPER_AT = (32, 20)    # cobre no salar (normal)
PLAIN_ROCK = (20, 20)   # rocha comum no centro (normal)
BASALT_IRON = (3, 25)   # minério de ferro no basalto (duro)


def synthetic_cave(seed=7) -> World:
    w = World(seed, SIZE, SIZE)
    region = np.full((SIZE, SIZE), PLATEAU, np.uint8)
    region[:, :13] = BASALT
    region[:, 27:] = SALAR
    region[:10, :] = FROST
    w.cave_region = region
    w.terraforms = False
    for y in range(SIZE):
        for x in range(SIZE):
            edge = x in (0, SIZE - 1) or y in (0, SIZE - 1)
            w.set(x, y, C.BEDROCK if edge else C.FLOOR if 12 <= y <= 36 and 2 <= x <= SIZE - 3 else C.ROCK)
    w.set(*HARD, C.HARD_ROCK)
    w.set(*FROST_ICE, C.ICE)
    w.set(*COPPER_AT, C.COPPER)
    w.set(*PLAIN_ROCK, C.ROCK)
    w.set(*BASALT_IRON, C.IRON)
    w.center = (20, 28)
    return w


def cave_state(seed=7) -> GameState:
    g = GameState(seed=seed)
    g.layers[layers.CAVE] = layers.Layer(layers.CAVE, synthetic_cave(seed))
    g.layer = layers.CAVE
    return g


def put_player_next_to(g, tile):
    tx, ty = tile
    g.world.set(tx, ty + 1, C.FLOOR)
    g.player.x, g.player.y = (tx + 0.5) * C.TILE, (ty + 1) * C.TILE + 24


def test_nv1_cannot_mine_hard_rock_and_f3_can():
    g = cave_state()
    put_player_next_to(g, HARD)
    assert g.hard_blocked(HARD) and not g.can_mine(HARD)
    g.fast = True
    assert g.can_break_hard and not g.hard_blocked(HARD) and g.can_mine(HARD)


def test_f3_breaks_hard_rock_in_the_end():
    g = cave_state()
    put_player_next_to(g, HARD)
    g.fast = True
    for _ in range(200):
        g._update_mining(0.05, HARD)
        if g.world.get(*HARD) != C.HARD_ROCK:
            break
    assert g.world.get(*HARD) == g.world.floor_kind


def test_plain_rock_in_the_center_is_not_hard():
    g = cave_state()
    put_player_next_to(g, PLAIN_ROCK)
    assert not g.world.is_hard(*PLAIN_ROCK) and g.can_mine(PLAIN_ROCK)


def test_ore_inside_hard_region_is_hard_too():
    g = cave_state()
    assert g.world.region_at_cave(*FROST_ICE) == FROST
    put_player_next_to(g, FROST_ICE)
    assert g.world.is_hard(*FROST_ICE) and not g.can_mine(FROST_ICE)
    assert g.world.region_at_cave(*BASALT_IRON) == BASALT
    put_player_next_to(g, BASALT_IRON)
    assert g.world.is_hard(*BASALT_IRON) and not g.can_mine(BASALT_IRON)


def test_copper_in_the_salar_mines_normally_and_drops_copper():
    g = cave_state()
    assert g.world.region_at_cave(*COPPER_AT) == SALAR
    put_player_next_to(g, COPPER_AT)
    assert g.can_mine(COPPER_AT)
    for _ in range(200):
        g._update_mining(0.05, COPPER_AT)
        if g.world.get(*COPPER_AT) != C.COPPER:
            break
    assert g.inventory.count("copper") >= 1


@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_hard_rock_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def test_hard_rock_hint(app):
    app.state = cave_state()
    put_player_next_to(app.state, HARD)
    app.mouse_tile = lambda: HARD
    app.hand_drill_selected = lambda: True
    try:
        assert app.hint() == "Rocha dura demais · precisa da broca nv.2"
        app.state.fast = True
        assert app.hint() != "Rocha dura demais · precisa da broca nv.2"
    finally:
        del app.mouse_tile, app.hand_drill_selected


def test_surface_has_no_hard_rule():
    g = GameState(seed=7)
    tile = next((x, y) for y in range(2, g.world.height - 2) for x in range(2, g.world.width - 2)
                if g.world.get(x, y) == C.ROCK)
    assert g.world.cave_region is None and g.world.region_at_cave(*tile) is None
    assert not g.world.is_hard(*tile) and not g.hard_blocked(tile)


def test_minimap_colors_the_cave_by_region_and_knows_copper():
    w = cave_state().world
    cx, cy = w.center
    assert minimap.tile_color(w, cx, cy) == minimap.CAVE_REGION_COLORS[PLATEAU]
    assert minimap.tile_color(w, 4, 20) == minimap.CAVE_REGION_COLORS[BASALT]
    assert minimap.tile_color(w, 33, 20) == minimap.CAVE_REGION_COLORS[SALAR]
    assert minimap.tile_color(w, *COPPER_AT) == minimap.TILE_COLORS[C.COPPER]
    assert minimap.tile_color(w, *HARD) == minimap.TILE_COLORS[C.HARD_ROCK]
    assert {"copper", "magmatite"} <= set(minimap.VEIN_COLORS)


def test_region_window_clips_to_the_map_edge():
    region = np.arange(12, dtype=np.uint8).reshape(3, 4)
    win = cave_rocks.region_window(region, -1, 2, 2, 5)
    assert win.shape == (3, 3)
    assert (win == region[[2, 2, 2]][:, [0, 0, 1]]).all()
