"""v0.5 M3.1 · F3 revela o mapa: mapa grande e minimapa inteiros, só exibindo (nada vira explorado)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import map_view as MV  # noqa: E402
from game import minimap, save  # noqa: E402
from game.systems import Controls, GameState  # noqa: E402


def _black(tex, x, y):
    return tuple(tex.get_at((x, y)))[:3] == minimap.UNSEEN


def test_f3_shows_the_whole_map_without_marking_anything_explored():
    pygame.init()
    g = GameState(7)
    g.update(0.016, Controls())
    mm = minimap.Minimap()
    explored = g.surface.explored
    bits_before, count_before, dump_before = bytes(explored.bits), explored.count, save.state_to_dict(g)
    far = (6, 6)                                              # canto do mapa: ninguém andou lá
    assert not explored.seen(*far)
    entries_off = MV.map_entries(g, "surface")
    assert _black(mm.texture(g), *far)
    # só enxerga ao redor do player (marcadores de veio/destroço exigem tile explorado)
    assert len([e for e in entries_off if e.category == "vein"]) < len(g.surface.world.veins)

    g.toggle_fast()
    tex = mm.texture(g)
    assert tex.get_size() == (C.SURFACE_W, C.SURFACE_H)
    assert not any(_black(tex, x, y) for x in range(0, C.SURFACE_W, 7) for y in range(0, C.SURFACE_H, 7))
    entries_on = MV.map_entries(g, "surface")
    world = g.surface.world
    assert len([e for e in entries_on if e.category == "vein"]) == len(world.veins)
    assert len([e for e in entries_on if e.category == "wreck"]) == len(world.wrecks)
    assert any(e.category == "crater" for e in entries_on)
    # F3 não grava nada
    assert bytes(explored.bits) == bits_before and explored.count == count_before and explored.take_fresh() == []

    g.toggle_fast()                                           # desliga: a névoa volta exatamente como estava
    assert _black(mm.texture(g), *far)
    assert bytes(explored.bits) == bits_before and explored.count == count_before
    assert [e.category for e in MV.map_entries(g, "surface")] == [e.category for e in entries_off]
    assert save.state_to_dict(g) == dump_before               # o save não muda por causa do F3


def test_full_texture_follows_mining():
    pygame.init()
    g = GameState(7)
    mm = minimap.Minimap()
    g.toggle_fast()
    tex = mm.texture(g)
    tile = (g.world.width // 2, 10)
    g.world.set(*tile, C.CRATER)                              # um tile longe mudou
    mm.repaint(g, tile)
    assert tuple(tex.get_at(tile))[:3] == minimap.TILE_COLORS[C.CRATER]
