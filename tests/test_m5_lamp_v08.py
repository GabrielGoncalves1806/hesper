"""v0.8 M5 · Task 2: Luminária bio (luz verde-água, raio 6, sem energia)."""
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import energy, layers  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.lighting import LAMP_COLOR, lamp  # noqa: E402
from game.render import Renderer, cave_lights  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402


def renderer() -> Renderer:
    pygame.init()
    pygame.display.set_mode((64, 64))
    return Renderer(Sprites())


def cave_state():
    g = GameState(rng=random.Random(1))
    g.enter_layer(layers.CAVE)
    g.player.x, g.player.y = layers.ramp_arrival(g.world)
    return g


def test_lamp_factory_takes_color():
    assert lamp(3, 4).color == LAMP_COLOR
    assert lamp(3, 4, 6, C.LAMP_BIO_COLOR).color == C.LAMP_BIO_COLOR


def test_cave_light_of_bio_lamp_has_color_and_radius():
    g = cave_state()
    g.machines += [Machine("lamp_bio", 60, 70), Machine("lamp", 62, 70)]
    lights = cave_lights(g)
    bio = [L for L in lights if L.color == C.LAMP_BIO_COLOR]
    assert len(bio) == 1 and bio[0].radius == C.LAMP_RADIUS["lamp_bio"] * C.TILE
    assert sum(L.color == LAMP_COLOR and L.radius == 5 * C.TILE for L in lights) == 1


def test_lamp_surface_is_the_png():
    r = renderer()
    surf = r.lamp_surface("lamp_bio")
    assert surf is r.sprites.get("lamp_bio") and surf.get_size() == C.LAMP_SPRITE_SIZE
    assert surf is not r.lamp_surface("lamp")
    assert r.machine_preview("lamp_bio").get_size() == (32, 64)
    assert r.broken_surface("lamp_bio").get_size() == C.LAMP_SPRITE_SIZE


def test_lamp_surface_falls_back_without_sprite():
    r = Renderer(Sprites(enabled=False))
    assert r.lamp_surface("lamp_bio").get_size() == C.LAMP_SPRITE_SIZE


def test_hotbar_icon_is_the_png():
    r = renderer()
    want = pygame.transform.scale_by(r.sprites.get("icon_lamp_bio"), 2)
    got = r.item_icon("lamp_bio")
    assert got.get_size() == (32, 32) and pygame.image.tobytes(got, "RGBA") == pygame.image.tobytes(want, "RGBA")


def test_bio_lamp_uses_no_power():
    assert energy.machine_use("lamp_bio") == 0
    assert energy.power_report(["o2"]) == energy.power_report(["o2", "lamp_bio"])


def test_surface_halo_uses_bio_color():
    r = renderer()
    g = GameState(rng=random.Random(1))
    g.machines.append(Machine("lamp_bio", g.player.tile[0], g.player.tile[1]))
    seen = []
    orig = r.light_glow
    r.light_glow = lambda rad, rgb, a: (seen.append(rgb), orig(rad, rgb, a))[1]
    canvas = pygame.Surface((r.view_w, r.view_h))
    r.draw_lighting(canvas, g, (g.player.x - r.view_w // 2, g.player.y - r.view_h // 2), "green", 0.0)
    assert C.LAMP_BIO_COLOR in seen
