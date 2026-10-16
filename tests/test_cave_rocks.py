"""Rocha da caverna com borda orgânica (v0.5 M3.4 · game/cave_rocks.py): só o desenho muda."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from game import cave_rocks
from game import config as C
from game import hills
from game.assets import Sprites
from game.render import Renderer
from game.systems import GameState
from game.world import World

T = C.TILE
B = C.HILL_BLOCK


def cave_world(walls=()):
    w = World(1, 64, 64)
    w.tiles = [[C.FLOOR] * 64 for _ in range(64)]
    for tx, ty in walls:
        w.tiles[ty][tx] = C.ROCK
    return w


def rocks():
    return cave_rocks.CaveRocks({})


def alpha_at(strips, x, y):
    """Alfa do pixel (x, y) do mundo nas tiras de um bloco (0 se nenhuma tira cobre)."""
    for surf, sx, sy in strips.values():
        if 0 <= x - sx < surf.get_width() and 0 <= y - sy < surf.get_height():
            a = surf.get_at((x - sx, y - sy))[3]
            if a:
                return a
    return 0


def test_isolated_rock_tile_is_not_a_square():
    cr = rocks()
    assert cr.ok
    strips = cr.strips(cave_world([(10, 10)]), 1, 1)
    x0, y0 = 10 * T, 10 * T - C.WALL_LIFT              # topo elevado do tile
    assert alpha_at(strips, x0 + 16, y0 + 16)           # o miolo é rocha
    corners = [alpha_at(strips, x0 + dx, y0 + dy) for dx in (0, T - 1) for dy in (0, T - 1)]
    assert corners.count(0) >= 3                        # seixo: os cantos do quadrado ficam vazios


def test_ramp_uses_the_cave_rock_colors():
    pal = C.PALETTES["mist"]
    ramp = cave_rocks.cave_ramp()
    assert ramp.shape == (10, 3)
    got = {tuple(c) for c in ramp}
    for key in ("face_dark", "face", "rock_dot", "rock", "rock2", "rock_hi"):
        assert hills._rgb(pal[key]) in got


def test_mining_rebakes_only_the_neighbour_blocks():
    w = cave_world([(x, y) for x in range(4, 20) for y in range(4, 20)])
    cr = rocks()
    for by in range(4):
        for bx in range(4):
            cr.strips(w, bx, by)
    n = cr.bakes
    for by in range(4):
        for bx in range(4):
            cr.strips(w, bx, by)
    assert cr.bakes == n                                # nada mudou: ninguém re-assa
    w.tiles[12][12] = C.FLOOR                           # miolo do bloco (1, 1): só ele enxerga
    for by in range(4):
        for bx in range(4):
            cr.strips(w, bx, by)
    assert cr.bakes == n + 1
    w.tiles[11][15] = C.FLOOR                           # beira entre os blocos (1,1) e (2,1)
    for by in range(4):
        for bx in range(4):
            cr.strips(w, bx, by)
    assert cr.bakes == n + 3


def test_cave_frame_draws_rock_strips_and_keeps_terminal_and_ore():
    pygame.init()
    pygame.display.set_mode((64, 64))
    g = GameState(rng=random.Random(1))
    g.enter_layer("cave")
    r = Renderer(Sprites())
    assert r.organic_hills(g)
    w = g.world
    spot = next((x, y) for y in range(20, 108) for x in range(20, 108)
                if w.get(x, y) in C.ORE_TILES and w.is_floor(x, y + 1))
    g.player.x, g.player.y = (spot[0] + 0.5) * T, (spot[1] + 2) * T
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    cam = r.camera(g)
    r.draw(canvas, g, cam, 0.0)
    strips = r.cave_strips(g, cam)
    assert strips and any(strips.values())
    assert r.cave_rock_blocks().bakes > 0
    # com o flag desligado volta o desenho por parede (nenhuma tira)
    C.ORGANIC_CAVE = False
    try:
        r.draw(canvas, g, cam, 0.0)
    finally:
        C.ORGANIC_CAVE = True


# ---- v0.6 Fundo M2: rampa por região e divisa por pixel ----------------------------------------------------------
from game.geo import BASALT, FROST, PLATEAU, SALAR  # noqa: E402


def test_ramps_load_and_centre_is_todays_ramp():
    ramps = cave_rocks.load_ramps()
    assert ramps is not None and set(ramps) == {PLATEAU, SALAR, BASALT, FROST}
    assert np.array_equal(ramps[PLATEAU][:9], cave_rocks.cave_ramp()[:9])   # report §1: o centro não muda
    assert tuple(ramps[BASALT][8]) == (194, 72, 31)                          # contorno de brasa


def test_luts_use_one_ramp_per_region():
    ramps = cave_rocks.load_ramps()
    lut = cave_rocks.cave_luts(ramps)[1]
    assert lut.shape == (80, 3)
    for r in range(4):
        assert np.array_equal(lut[r * 10:r * 10 + 10], ramps[r])
    assert np.array_equal(lut[40:], (lut[:40] * hills.BEDROCK_SHADE).astype(np.uint8))


def test_luts_without_file_fall_back_to_single_ramp(tmp_path):
    lut = cave_rocks.cave_luts(cave_rocks.load_ramps(tmp_path / "nada.json"))[1]
    for r in range(4):
        assert np.array_equal(lut[r * 10:r * 10 + 10], cave_rocks.cave_ramp())


def test_wall_region_border_is_curved():
    """Muro inteiro num bloco, região 0 à esquerda da coluna 4 e 1 à direita: a troca de cor não é uma reta."""
    region = np.zeros((64, 64), np.uint8)
    region[:, 4:] = SALAR
    i0, i1, j0, j1 = hills.window_bounds(0, 1)
    kinds = np.full((j1 - j0, i1 - i0), C.ROCK, np.uint8)
    blk = hills.bake_block(kinds, cave_rocks.region_window(region, i0, i1, j0, j1), 0, 1,
                           hills.load_indexed("hill_top.png"), hills.load_indexed("hill_face.png"),
                           hills.edge_noise())
    reg = cave_rocks.pixel_regions(blk, region, seed=7)
    top = blk["top"]
    firsts = {int(np.argmax(reg[y] == SALAR)) for y in range(reg.shape[0]) if top[y].any() and (reg[y] == SALAR).any()}
    assert len(firsts) > 1, "a divisa da rocha virou reta (escadinha por tile)"
