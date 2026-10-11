"""Ordem de desenho das paredes altas e mira do mouse (lógica pura, sem janela)."""

from game import config as C
from game.render import build_draw_list
from game.world import World

T = C.TILE


def small_world() -> World:
    """Mundo 10×10 de chão com uma parede em (4, 5)."""
    w = World(seed=1, width=10, height=10)
    for row in w.tiles:
        row[:] = [C.FLOOR] * 10
    w.set(4, 5, C.ROCK)
    return w


def index_of(order, item):
    return order.index(item)


def test_player_above_wall_is_drawn_before_it():
    w = small_world()
    player_row4 = (4 * T + 20, "player")          # pé na linha 4, logo acima da parede
    order = build_draw_list(w, [player_row4], 0, 9, 0, 9)
    assert index_of(order, ("obj", "player")) < index_of(order, ("wall", 4, 5))


def test_player_below_wall_is_drawn_after_it():
    w = small_world()
    order = build_draw_list(w, [(6 * T + 10, "player")], 0, 9, 0, 9)
    assert index_of(order, ("wall", 4, 5)) < index_of(order, ("obj", "player"))


def test_same_row_walls_first_then_objects_by_feet():
    w = small_world()
    objs = [(6 * T, "machine_row5"), (5 * T + 20, "player_row5")]   # ambos na linha 5
    order = build_draw_list(w, objs, 0, 9, 0, 9)
    wall = index_of(order, ("wall", 4, 5))
    player = index_of(order, ("obj", "player_row5"))
    machine = index_of(order, ("obj", "machine_row5"))
    assert wall < player < machine            # parede da linha, depois quem tem o pé mais alto


def test_objects_outside_visible_rows_are_kept():
    w = small_world()
    order = build_draw_list(w, [(12 * T, "below")], 0, 9, 0, 9)
    assert ("obj", "below") in order


def test_visual_tile_picks_raised_wall_top():
    w = small_world()
    # ponto na metade de baixo do tile (4, 4): coberto pelo topo elevado da parede (4, 5)
    assert w.visual_tile_at(4 * T + 10, 4 * T + 20) == (4, 5)
    # ponto nos 8 px de cima do tile (4, 4): ainda é chão à vista
    assert w.visual_tile_at(4 * T + 10, 4 * T + 3) == (4, 4)
    # longe da parede: tile normal
    assert w.visual_tile_at(1 * T + 10, 1 * T + 20) == (1, 1)
    # na face da própria parede: a própria parede
    assert w.visual_tile_at(4 * T + 10, 5 * T + 20) == (4, 5)
