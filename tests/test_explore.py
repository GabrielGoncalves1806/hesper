"""Explorado por camada (v0.3 Marco 3): névoa de guerra do scanner."""

from game import config as C
from game.explore import Explored
from game.systems import Controls, GameState, Machine


def test_rect_circle_and_fresh():
    ex = Explored(20, 10)
    assert not ex.seen(5, 5)
    ex.reveal_rect(5, 5, 1, 1)
    assert ex.seen(4, 4) and ex.seen(6, 6) and not ex.seen(7, 5) and ex.count == 9
    assert len(ex.take_fresh()) == 9 and ex.take_fresh() == []
    ex.reveal_rect(5, 5, 1, 1)
    assert ex.take_fresh() == []
    ex.reveal_circle(15.5, 5.5, 2)
    assert ex.seen(15, 5) and ex.seen(13, 5) and not ex.seen(13, 3) and not ex.seen(18, 5)
    ex.reveal_rect(0, 0, 50, 50)                  # passa da borda sem quebrar
    assert ex.count == 200


def test_save_roundtrip_is_small():
    ex = Explored(192, 192)
    ex.reveal_rect(96, 96, 20, 12)
    text = ex.to_data()
    assert len(text) < 400
    back = Explored.from_data(192, 192, text)
    assert back.bits == ex.bits and back.count == ex.count
    assert Explored.from_data(192, 192, None).count == 0


def test_surface_sees_the_screen_from_the_start():
    g = GameState(7)
    g.update(0.016, Controls())
    ex = g.surface.explored
    tx, ty = g.player.tile
    hx, hy = C.EXPLORE_SURFACE
    assert ex.seen(tx + hx, ty + hy) and ex.seen(tx - hx, ty - hy)
    assert not ex.seen(tx + hx + 1, ty) and ex.count == (2 * hx + 1) * (2 * hy + 1)


def test_cave_only_sees_what_light_reveals():
    g = GameState(7)
    g.enter_layer("cave", (40 * C.TILE, 40 * C.TILE))
    g.update(0.016, Controls())
    ex = g.layers["cave"].explored
    assert ex.seen(39, 38) and not ex.seen(39 + 8, 38)
    rx, ry = C.CAVE_RAMP
    assert not ex.seen(rx + 1, ry + 1)                      # a rampa está fora da tela daqui
    g.player.x, g.player.y = 52 * C.TILE, 52 * C.TILE
    g.machines.append(Machine("lamp", 50, 50))
    g.machines.append(Machine("lamp_t2", 64, 50))
    for _ in range(5):
        g.update(0.05, Controls())
    assert ex.seen(50, 46) and ex.seen(54, 50)              # o círculo da luminária (5 tiles)
    assert ex.seen(70, 50) and not ex.seen(72, 50)          # a forte ilumina 7
    assert ex.seen(rx + 1, ry + 1)                          # a boca da rampa (luz do dia) entrou na tela


def test_minimap_texture_is_incremental(monkeypatch):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    from game import minimap
    g = GameState(7)
    g.update(0.016, Controls())
    mm = minimap.Minimap()
    tex = mm.texture(g)
    tx, ty = g.player.tile
    assert tex.get_size() == (C.SURFACE_W, C.SURFACE_H)
    assert tex.get_at((tx, ty))[:3] != minimap.UNSEEN and tex.get_at((tx + 40, ty))[:3] == minimap.UNSEEN
    painted = []
    monkeypatch.setattr(minimap, "tile_color", lambda w, x, y: painted.append((x, y)) or (1, 2, 3))
    assert mm.texture(g) is tex and painted == []          # nada novo: não pinta nada
    g.player.x += 3 * C.TILE
    for _ in range(5):
        g.update(0.05, Controls())
    mm.texture(g)
    hx, hy = C.EXPLORE_SURFACE
    assert 0 < len(painted) <= 3 * (2 * hy + 1)            # só a faixa nova


def test_cave_far_lights_are_not_seen():
    """Terminal aceso do outro lado da caverna não conta como visto: só o que está na tela."""
    g = GameState(7)
    g.enter_layer("cave")
    g.update(0.016, Controls())
    ex = g.layers["cave"].explored
    for tx, ty in g.world.terminals:
        assert not ex.seen(tx, ty + 1)
