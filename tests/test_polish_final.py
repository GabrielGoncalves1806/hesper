"""Polimento final do v0.2 (parte 2): E interage com o que está debaixo do mouse, drones na mesma rota
não se empilham (só no desenho) e floaters desviam do rótulo do baú."""

import math
import random

import pytest

from game import config as C
from game import drones
from game.floaters import dodge_labels
from game.systems import GameState, Machine


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add(game, kind, tile, count: int = 0, **kw) -> Machine:
    m = Machine(kind, *tile, **kw)
    if m.is_station:
        m.station = drones.new_station(m, count)
    game.machines.append(m)
    return m


def stand_at(game, tile):
    """Player com os pés no centro de baixo do tile."""
    game.player.x, game.player.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 1) * C.TILE - 2


def point_on(machine) -> tuple[float, float]:
    """Um pixel no meio do desenho da máquina (onde o mouse estaria)."""
    x, y, w, h = machine.sprite_rect
    return x + w / 2, y + h / 2


# ---------------------------------------------------------------- 1. E com o mouse
def test_interactable_at_finds_chest_drill_station_and_terminal(game):
    chest = add(game, "chest", (60, 70))
    station = add(game, "drone_station", (70, 70))
    drill = add(game, "drill", (80, 70), resource="iron")
    o2 = add(game, "o2", (90, 70))
    assert game.interactable_at(*point_on(chest)) == ("chest", chest)
    assert game.interactable_at(*point_on(station)) == ("station", station)
    assert game.interactable_at(*point_on(drill)) == ("drill", drill)
    assert game.interactable_at(*point_on(o2)) is None          # máquina que o E não abre
    tx, ty = game.world.terminals[0]
    assert game.interactable_at((tx + 0.5) * C.TILE, (ty + 0.5) * C.TILE) == ("terminal", 0)


def test_e_prefers_what_is_under_the_mouse_when_in_reach(game):
    near = add(game, "chest", (60, 70))
    far = add(game, "chest", (61, 70))
    game.player.x, game.player.y = 61 * C.TILE - 8, 71 * C.TILE - 6   # mais perto do `near`, `far` no alcance
    assert game.drill_distance(near) < game.drill_distance(far) <= C.CHEST_REACH
    assert game.interaction() == ("chest", near)                 # sem mouse: o mais perto
    hover = game.interactable_at(*point_on(far))
    assert game.interaction(hover) == ("chest", far)             # mouse no outro: é ele


def test_e_falls_back_to_the_closest_when_the_hovered_is_out_of_reach(game):
    near = add(game, "chest", (60, 70))
    far = add(game, "chest", (66, 70))
    stand_at(game, (60, 71))
    assert game.drill_distance(far) > C.CHEST_REACH
    assert game.interaction(game.interactable_at(*point_on(far))) == ("chest", near)


def test_e_hover_beats_a_closer_machine_of_another_kind(game):
    chest = add(game, "chest", (60, 70))
    station = add(game, "drone_station", (60, 68))
    game.player.x, game.player.y = 61 * C.TILE - 8, 71 * C.TILE - 6
    assert game.interaction() == ("chest", chest)
    assert game.drill_distance(station) <= C.STATION_REACH
    assert game.interaction(("station", station)) == ("station", station)
    assert game.interaction(("drill", Machine("drill", 60, 70, resource="iron"))) == ("chest", chest)  # fora do mapa


def test_hovered_drill_gets_shift_e_target(game):
    a = add(game, "drill", (60, 66), resource="iron")
    b = add(game, "drill", (62, 66), resource="silicon")
    game.player.x, game.player.y = 62 * C.TILE - 4, 68 * C.TILE - 4
    assert game.in_reach("drill", a) and game.in_reach("drill", b)
    closest = game.interaction()[1]
    other = b if closest is a else a
    assert game.interaction(game.interactable_at(*point_on(other))) == ("drill", other)


# ---------------------------------------------------------------- 2. drones na mesma rota
def flying_pair(game):
    station = add(game, "drone_station", (60, 70), count=4)
    chest = add(game, "chest", (80, 70))
    for d in station.station.drones:
        d.state, d.dest, d.x, d.y = drones.CARRYING, chest, 1000.0, 2000.0    # todos no mesmo ponto
    return station, chest


def test_drones_on_the_same_route_get_different_places(game):
    station, chest = flying_pair(game)
    offs = [drones.visual_offset(station, d) for d in station.station.drones]
    for i in range(len(offs)):
        for j in range(i + 1, len(offs)):
            sep = math.hypot(offs[i][0] - offs[j][0], offs[i][1] - offs[j][1])
            assert sep >= 10                                     # dá pra ver que são dois (drone: 16 px)
    tx, ty = drones.hover_position(chest)
    d = station.station.drones[0]
    ux, uy = (tx - d.x), (ty - d.y)
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    side0 = -uy * offs[0][0] + ux * offs[0][1]                   # os dois primeiros: lado a lado
    side1 = -uy * offs[1][0] + ux * offs[1][1]
    assert side0 < -5 and side1 > 5
    assert all(math.hypot(*o) <= 15 for o in offs)


def test_visual_offset_does_not_touch_the_logic(game):
    station, _ = flying_pair(game)
    d = station.station.drones[1]
    before = (d.x, d.y, d.state, d.dest)
    drones.visual_offset(station, d)
    assert (d.x, d.y, d.state, d.dest) == before


def test_pickup_spots_around_the_target_are_different(game):
    station = add(game, "drone_station", (60, 70), count=4)
    for d in station.station.drones:
        d.state = drones.COLLECTING
    spots = {tuple(round(v, 3) for v in drones.visual_offset(station, d)) for d in station.station.drones}
    assert len(spots) == 4
    assert all(math.hypot(*s) <= 14 for s in spots)


def test_landed_drone_has_no_offset_and_ease_converges(game):
    station = add(game, "drone_station", (60, 70), count=1)
    assert drones.visual_offset(station, station.station.drones[0]) == (0.0, 0.0)
    pos = (0.0, 0.0)
    for _ in range(120):
        pos = drones.ease(pos, (8.0, -4.0), 1 / 60)
    assert pos == pytest.approx((8.0, -4.0), abs=0.05)
    assert drones.ease((1.0, 1.0), (5.0, 5.0), 0.0) == (1.0, 1.0)   # sem tempo, sem pulo


# ---------------------------------------------------------------- 3. floaters x rótulo do baú
LABEL = (40, 100, 120, 114)                                    # esquerda, topo, direita, baixo (px da UI)


def test_floater_that_would_cross_the_label_goes_above_it():
    below = {1: (60, 90, 120, 26, 9)}                          # embaixo, ainda vai subir 26 px: cruzaria
    shift = dodge_labels(below, [LABEL])[1]
    assert 120 + 9 - shift < 100                               # o de baixo dele fica acima do rótulo


def test_floaters_away_from_the_label_do_not_move():
    beside = (200, 240, 110, 26, 9)                            # outra coluna
    above = (60, 90, 60, 26, 9)                                # já está acima e só sobe
    short = (60, 90, 140, 10, 9)                               # embaixo, mas morre antes de chegar
    assert dodge_labels({1: beside, 2: above, 3: short}, [LABEL]) == {1: 0.0, 2: 0.0, 3: 0.0}


def test_two_dodgers_do_not_land_on_each_other():
    boxes = {1: (60, 90, 120, 26, 9), 2: (55, 95, 104, 30, 9)}   # o 1 é mais velho (sobe menos)
    s = dodge_labels(boxes, [LABEL])
    tops = sorted((boxes[k][2] - s[k], k) for k in boxes)
    assert all(boxes[k][2] + 9 - s[k] < 100 for k in boxes)    # os dois acima do rótulo
    assert tops[1][0] - tops[0][0] >= 9                         # sem encavalar


def test_dodger_steps_over_a_floater_already_above_the_label():
    boxes = {1: (60, 90, 85, 26, 9), 2: (60, 90, 120, 30, 9)}   # 1 já acima (não desvia), 2 cruzaria
    s = dodge_labels(boxes, [LABEL])
    assert s[1] == 0.0
    assert boxes[2][2] + 9 - s[2] <= boxes[1][2]               # o 2 fica em cima do 1, não por cima dele


def test_known_shifts_stay_put_and_dead_ones_are_dropped():
    boxes = {1: (60, 90, 120, 26, 9)}
    first = dodge_labels(boxes, [LABEL])
    moved = {1: (60, 90, 110, 21, 9), 5: (300, 320, 50, 20, 9)}  # um frame depois: subiu; nasceu outro longe
    again = dodge_labels(moved, [LABEL], {**first, 9: 4.0})
    assert again[1] == first[1] and 9 not in again and again[5] == 0.0
