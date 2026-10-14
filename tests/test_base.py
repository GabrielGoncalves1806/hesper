"""v0.5 M2 · base respirável: blocos, vedação (flood fill), portas, Dispersor de O₂, sons e save.

A vedação é testada direto na grade (game/base.py, sem mundo); o resto, pelo GameState de verdade."""

import json
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import save  # noqa: E402
from game.base import BaseBlock, BaseGrid, floor_variant  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import Controls, GameState, Machine  # noqa: E402
from tests.helpers import build_now, give  # noqa: E402

T = C.TILE


# ---------------------------------------------------------------- montar bases na mão
def room(grid: BaseGrid, x0: int, y0: int, w: int, h: int, door=(None, None), gap=None) -> None:
    """Sala de w×h tiles de chão em (x0, y0), com parede em volta. `door` = tile da porta; `gap` = tile da parede que
    fica faltando (o furo)."""
    for y in range(y0 - 1, y0 + h + 1):
        for x in range(x0 - 1, x0 + w + 1):
            inside = x0 <= x < x0 + w and y0 <= y < y0 + h
            if (x, y) == gap:
                continue
            if inside:
                grid.add(BaseBlock(C.BASE_FLOOR, x, y))
            elif (x, y) == tuple(door):
                grid.add(BaseBlock(C.BASE_DOOR, x, y))
            else:
                grid.add(BaseBlock(C.BASE_WALL, x, y))


def sealed_room(**kw) -> BaseGrid:
    g = BaseGrid()
    room(g, 10, 10, 4, 3, door=(11, 13), **kw)
    return g


# ---------------------------------------------------------------- vedação: flood fill
def test_closed_room_with_a_door_is_sealed():
    seal = sealed_room().seal_from((11, 11))
    assert seal.ok and len(seal.floor) == 12 and seal.doors == 1 and seal.leak is None
    assert (11, 13) in seal.inside and (11, 11) in seal.inside


def test_hole_in_the_wall_is_a_leak_at_the_right_tile():
    g = BaseGrid()
    room(g, 10, 10, 4, 3, door=(11, 13), gap=(14, 11))        # falta um tile da parede da direita
    seal = g.seal_from((11, 11))
    assert seal.reason == "leak" and not seal.ok and seal.leak == (14, 11)


def test_leak_tile_is_the_first_one_found_outside_the_floor():
    g = BaseGrid()
    room(g, 10, 10, 4, 3, door=(11, 13), gap=(11, 9))         # furo no teto
    seal = g.seal_from((11, 11))
    assert seal.leak == (11, 9) and g.get(seal.leak) is None


def test_too_small_base():
    g = BaseGrid()
    room(g, 10, 10, 2, 4, door=(10, 14))                      # 8 tiles de chão (< 9)
    seal = g.seal_from((10, 10))
    assert seal.reason == "small" and len(seal.floor) == 8 and not seal.ok
    g2 = BaseGrid()
    room(g2, 10, 10, 3, 3, door=(10, 13))                     # o 3×3 mínimo: 9 vale
    assert g2.seal_from((10, 10)).ok


def test_non_square_shapes_count_by_tiles_not_by_rectangle():
    g = BaseGrid()
    room(g, 10, 10, 9, 1, door=(10, 11))                      # um corredor de 9 tiles
    assert g.seal_from((10, 10)).ok


def test_no_door_is_not_valid():
    g = BaseGrid()
    room(g, 10, 10, 4, 3)
    seal = g.seal_from((10, 10))
    assert seal.reason == "nodoor" and seal.doors == 0 and seal.leak is None


def test_too_big_base_stops_the_flood_fill():
    g = BaseGrid()
    room(g, 10, 10, 21, 10, door=(10, 20))                    # 210 > 200
    seal = g.seal_from((10, 10))
    assert seal.reason == "big" and len(seal.floor) == C.BASE_MAX_FLOOR + 1
    g2 = BaseGrid()
    room(g2, 10, 10, 20, 10, door=(10, 20))                   # 200 vale
    assert g2.seal_from((10, 10)).ok


def test_start_without_floor_is_a_leak_at_the_dispenser():
    g = BaseGrid()
    seal = g.seal_from((5, 5))
    assert seal.reason == "nofloor" and seal.leak == (5, 5)


def test_door_open_or_closed_does_not_break_the_seal():
    g = sealed_room()
    door = g.get((11, 13))
    for frame in (0.0, 1.5, 3.0):
        door.frame = frame
        assert g.seal_from((11, 11)).ok


def test_double_door_counts_as_one_door_and_both_tiles_seal():
    g = BaseGrid()
    room(g, 10, 10, 4, 3, door=(None, None), gap=None)
    # troca 2 tiles da parede de baixo por uma porta dupla
    for t in ((10, 13), (11, 13)):
        g.remove(g.get(t))
    g.add(BaseBlock(C.BASE_DOOR2, 10, 13, "h"))
    seal = g.seal_from((10, 10))
    assert seal.ok and seal.doors == 1
    assert g.get((10, 13)) is g.get((11, 13))
    g.remove(g.get((11, 13)))                                  # tirar qualquer metade tira as duas
    assert g.get((10, 13)) is None and len(g.blocks) == 12 + 16


def test_recalc_only_when_a_block_changes_near():
    g = sealed_room()
    s = GameState(rng=random.Random(1))
    s.active.base = g
    d = Machine(C.DISPENSER, 11, 11)
    s.machines.append(d)
    first = s.seal_of(d)
    assert first.ok and s.seal_of(d) is first                  # sem mudança: o mesmo objeto
    g.add(BaseBlock(C.BASE_WALL, 40, 40))                      # bloco longe: não recalcula
    assert s.seal_of(d) is first
    g.remove(g.get((14, 11)))                                  # parede da direita some: recalcula
    again = s.seal_of(d)
    assert again is not first and again.reason == "leak" and again.leak == (14, 11)
    for i in range(C.BASE_LOG_KEEP + 5):                       # log estourou: recalcula por garantia
        g.add(BaseBlock(C.BASE_WALL, 50 + i, 50))
    assert s.seal_of(d) is not again


def test_floor_variant_follows_the_pick_table():
    seen = {floor_variant(x, y) for x in range(40) for y in range(40)}
    assert seen == {0, 1, 2, 3}
    assert all(floor_variant(x, y) == C.FLOOR_PICK[((x * 73856093) ^ (y * 19349663)) & 7]
               for x in range(10) for y in range(10))


# ---------------------------------------------------------------- portas: orientação, borda e colisão
def test_door_layout_picks_the_outer_edge():
    g = sealed_room()
    door = g.get((11, 13))                                     # parede de baixo, chão ao norte -> folha em "s"
    assert g.layout(door) == ("h", "s")
    top = BaseGrid()
    room(top, 10, 10, 4, 3, door=(11, 9))
    assert top.layout(top.get((11, 9))) == ("h", "n")          # parede de cima, chão ao sul -> "n"
    right = BaseGrid()
    room(right, 10, 10, 4, 3, door=(14, 11))
    assert right.layout(right.get((14, 11))) == ("v", "e")     # parede da direita, chão a oeste -> "e"
    left = BaseGrid()
    room(left, 10, 10, 4, 3, door=(9, 11))
    assert left.layout(left.get((9, 11))) == ("v", "w")
    lone = BaseGrid()
    lone.add(BaseBlock(C.BASE_DOOR, 3, 3))
    assert lone.layout(lone.get((3, 3))) == ("h", "s")         # solta: h_s


def test_door_collision_table():
    g = sealed_room()
    door = g.get((11, 13))
    x, y = 11 * T, 13 * T
    door.frame = 0.0
    assert g.door_rects(door) == [(x, y + 27, 32, 5)]          # solo h_s fechada
    door.frame = 3.0
    assert g.door_rects(door) == [(x, y + 27, 2, 5), (x + 30, y + 27, 2, 5)]
    right = BaseGrid()
    room(right, 10, 10, 4, 3, door=(14, 11))
    d = right.get((14, 11))
    assert right.door_rects(d) == [(14 * T + 26, 11 * T, 6, 32)]  # solo v_e fechada
    big = BaseGrid()
    room(big, 10, 10, 4, 3)
    for t in ((10, 13), (11, 13)):
        big.remove(big.get(t))
    dd = BaseBlock(C.BASE_DOOR2, 10, 13, "h")
    big.add(dd)
    assert big.door_rects(dd) == [(10 * T, 13 * T + 27, 64, 5)]
    dd.frame = 3.0
    assert big.door_rects(dd) == [(10 * T, 13 * T + 27, 2, 5), (10 * T + 62, 13 * T + 27, 2, 5)]


def test_walls_and_closed_doors_block_the_player_and_open_ones_let_through():
    s = GameState(rng=random.Random(1))
    g = sealed_room()
    s.active.base = g
    wall_box = (13 * T + 30, 11 * T, 4, 4)
    assert s.solids_near(wall_box)
    box = (11 * T + 2, 13 * T + 26, 28, 6)
    door = g.get((11, 13))
    strip = lambda: [r for r in s.solids_near(box) if r[3] == 5]   # a faixa da moldura (as paredes do lado têm 32 de altura)
    assert strip() == [(11 * T, 13 * T + 27, 32, 5)]           # fechada: a faixa inteira
    door.frame = 3.0
    assert strip() == [(11 * T, 13 * T + 27, 2, 5), (11 * T + 30, 13 * T + 27, 2, 5)]   # aberta: só as jambas de 2 px


def test_door_opens_by_itself_when_the_player_is_near_and_closes_after():
    s = GameState(rng=random.Random(1))
    g = sealed_room()
    s.active.base = g
    door = g.get((11, 13))
    s.player.x, s.player.y = 11.5 * T, 11.5 * T                # a 2 tiles
    s.update(0.05, Controls())
    assert door.frame == 0.0 and not door.opening
    s.player.x, s.player.y = 11.5 * T, 12.5 * T + 8            # a ~1 tile
    for _ in range(12):
        s.update(0.05, Controls())
    assert door.frame == C.DOOR_FRAMES - 1 and not door.closed
    assert ("door", "open", (11.5 * T, 13.5 * T)) in s.events
    s.events.clear()
    s.player.x, s.player.y = 11.5 * T, 9.5 * T                 # saiu
    for _ in range(12):
        s.update(0.05, Controls())
    assert door.frame == 0.0 and ("door", "close", (11.5 * T, 13.5 * T)) in s.events


def test_door_open_sound_event_is_not_repeated_while_reopening():
    s = GameState(rng=random.Random(1))
    g = sealed_room()
    s.active.base = g
    door = g.get((11, 13))
    s.player.x, s.player.y = 11.5 * T, 12.5 * T
    for _ in range(4):
        s.update(0.05, Controls())
    s.player.x, s.player.y = 11.5 * T, 9.5 * T
    s.update(0.05, Controls())                                 # começou a fechar, ainda não chegou no 0
    s.player.x, s.player.y = 11.5 * T, 12.5 * T
    s.update(0.05, Controls())
    opens = [e for e in s.events if e[:2] == ("door", "open")]
    assert len(opens) == 1 and door.frame > 0


def test_double_door_opens_near_either_tile():
    s = GameState(rng=random.Random(1))
    g = BaseGrid()
    room(g, 10, 10, 4, 3)
    for t in ((10, 13), (11, 13)):
        g.remove(g.get(t))
    dd = BaseBlock(C.BASE_DOOR2, 10, 13, "h")
    g.add(dd)
    s.active.base = g
    s.player.x, s.player.y = 11.5 * T + 20, 12.5 * T + 8        # perto só da metade de leste
    for _ in range(12):
        s.update(0.05, Controls())
    assert not dd.closed


def test_xray_counts_walls_and_doors_in_frames_0_and_1_only():
    g = sealed_room()
    door = g.get((11, 13))
    assert g.get((10, 13)).xray
    door.frame = 1.9
    assert door.xray
    door.frame = 2.0
    assert not door.xray
    assert not g.get((11, 11)).xray                             # chão nunca


# ---------------------------------------------------------------- construtor: blocos
def free_spot(s: GameState, w: int, h: int) -> tuple[int, int]:
    """Canto de uma área w×h de chão livre perto da cápsula (e o player em cima, no meio)."""
    bx, by = C.BASE_TILE
    for dy in range(-8, 12):
        for dx in range(-14, 14):
            x0, y0 = bx + dx, by + dy
            tiles = [(x0 + i, y0 + j) for i in range(w) for j in range(h)]
            if all(s.world.is_floor(*t) and t not in C.POD_TILES and not s.world.vein_at(*t)
                   and not s.world.is_water(*t, s.stage) for t in tiles) and abs(dx) > 3:
                return x0, y0
    raise AssertionError("sem área livre")


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(5))
    g.debug_add_ti()
    return g


def stand_at(game, tx, ty):
    game.player.x, game.player.y = (tx + 0.5) * T, (ty + 0.5) * T + 8


def test_block_recipes_are_cheap_and_in_the_base_tab():
    for kind in C.BASE_KINDS:
        m = C.MACHINES[kind]
        assert m.placeable and sum(m.cost.values()) <= 12 and C.MACHINE_CATEGORY[kind] == "base"
    assert C.MACHINES[C.BASE_FLOOR].cost == {"iron": 1}
    assert ("base", "Base") in C.FAB_TABS and ("base", "Base") not in C.CRAFT_TABS


def test_build_floor_wall_and_door_spend_the_recipe(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0 + 2, y0 + 1)
    give(game, constructor=1, iron=30, silicon=10)
    for kind, tile in ((C.BASE_FLOOR, (x0, y0)), (C.BASE_WALL, (x0 + 4, y0)), (C.BASE_DOOR, (x0 + 5, y0))):
        before = game.inventory.count("iron")
        assert game.build(kind, tile)
        assert game.inventory.count("iron") == before - C.MACHINES[kind].cost["iron"]
        assert game.base.get(tile).kind == kind
    assert game.crafted[C.BASE_WALL] == 1 and ("build", C.BASE_WALL, (x0 + 4, y0)) in game.events


def test_floor_accepts_a_machine_on_top_but_wall_does_not(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0 + 2, y0 + 2)
    give(game, constructor=1, iron=60, silicon=20)
    assert game.build(C.BASE_FLOOR, (x0, y0))
    assert not game.build(C.BASE_FLOOR, (x0, y0))               # tile ocupado por bloco
    assert not game.can_place(C.BASE_WALL, (x0, y0))            # parede/porta não entram em cima do chão
    assert game.can_place("o2", (x0, y0))                        # máquina entra
    assert build_now(game, "o2", (x0, y0)) is not None
    assert game.base.get((x0, y0)).is_floor and game.machine_at((x0, y0)) is not None


def test_machine_cannot_sit_on_wall_or_door(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0, y0 + 2)
    game.base.add(BaseBlock(C.BASE_WALL, x0 + 1, y0))
    game.base.add(BaseBlock(C.BASE_DOOR, x0 + 2, y0))
    assert not game.can_place("o2", (x0 + 1, y0)) and not game.can_place("o2", (x0 + 2, y0))
    assert not game.can_place(C.BASE_WALL, (x0 + 1, y0))


def test_wall_cannot_trap_the_player(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0 + 1, y0 + 1)
    assert not game.can_place(C.BASE_WALL, (x0 + 1, y0 + 1))
    assert game.can_place(C.BASE_FLOOR, (x0 + 1, y0 + 1))       # chão pode


def test_block_placing_needs_reach_and_dry_land(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0, y0)
    assert game.can_place(C.BASE_FLOOR, (x0 + C.PLACE_REACH, y0))
    assert not game.can_place(C.BASE_WALL, (x0 + C.PLACE_REACH + 3, y0 + 2))
    assert not game.can_place(C.BASE_FLOOR, C.POD_TILES[0])      # em cima da cápsula não


def test_double_door_one_item_two_tiles_rotates_and_dismantles_as_one(game):
    x0, y0 = free_spot(game, 6, 5)
    stand_at(game, x0 + 2, y0 + 3)
    give(game, constructor=1, iron=30, silicon=20)
    iron0, si0 = game.inventory.count("iron"), game.inventory.count("silicon")
    assert game.base_tiles(C.BASE_DOOR2, (x0, y0), 0) == [(x0, y0), (x0 + 1, y0)]
    assert game.base_tiles(C.BASE_DOOR2, (x0, y0), 1) == [(x0, y0), (x0, y0 + 1)]
    assert game.build(C.BASE_DOOR2, (x0, y0), 0)
    cost = C.MACHINES[C.BASE_DOOR2].cost
    assert game.inventory.count("iron") == iron0 - cost["iron"] and game.inventory.count("silicon") == si0 - cost["silicon"]
    block = game.base.get((x0, y0))
    assert block is game.base.get((x0 + 1, y0)) and block.orient == "h" and len(game.base.blocks) == 1
    assert not game.can_place(C.BASE_DOOR2, (x0 + 1, y0), 0)    # a metade de leste já é porta
    assert game.build(C.BASE_DOOR2, (x0, y0 + 2), 1)             # rotação 1: um em cima do outro
    assert game.base.get((x0, y0 + 3)).orient == "v"
    # desmontar a metade de leste tira as duas e devolve 1 receita
    iron1, si1 = game.inventory.count("iron"), game.inventory.count("silicon")
    stand_at(game, x0 + 1, y0 + 4)
    assert game.dismantle(game.base.get((x0 + 1, y0)))
    assert game.base.get((x0, y0)) is None and game.base.get((x0 + 1, y0)) is None
    assert game.inventory.count("iron") == iron1 + cost["iron"] and game.inventory.count("silicon") == si1 + cost["silicon"]
    assert ("dismantle", C.BASE_DOOR2, (x0, y0)) in game.events


def test_dismantle_block_by_holding_the_right_button(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0 + 1, y0 + 2)
    give(game, constructor=1, iron=10)
    assert game.build(C.BASE_WALL, (x0 + 2, y0))
    wall = game.base.get((x0 + 2, y0))
    t = 0.0
    while t < C.DISMANTLE_HOLD + 0.1:
        game.update(0.05, Controls(dismantle=wall))
        t += 0.05
    assert game.base.get((x0 + 2, y0)) is None and game.inventory.count("iron") == 10
    assert game.base.blocks == []


def test_dismantle_block_needs_room_in_the_inventory(game):
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0 + 1, y0 + 2)
    game.base.add(BaseBlock(C.BASE_WALL, x0 + 2, y0))
    wall = game.base.get((x0 + 2, y0))
    for i in range(len(game.inventory)):
        game.inventory.slots[i] = Stack("silicon", 99)
    assert not game.dismantle(wall) and ("inv_full",) in game.events and game.base.get((x0 + 2, y0)) is wall


def test_block_at_point_finds_the_wall_by_its_raised_top(game):
    game.base.add(BaseBlock(C.BASE_FLOOR, 20, 20))
    game.base.add(BaseBlock(C.BASE_WALL, 20, 21))
    assert game.block_at_point(20 * T + 16, 20 * T + 4).is_floor           # parte de cima do tile do chão
    assert game.block_at_point(20 * T + 16, 20 * T + 28).is_wall           # o topo da parede cobre o fim do tile de cima
    assert game.block_at_point(20 * T + 16, 21 * T + 10).is_wall


# ---------------------------------------------------------------- Dispersor de O₂
def demo_base(game, w=4, h=3, dispenser=True, door=True, water=0, gap=None):
    """Sala vedada (w×h) com o Dispersor no canto; o player no meio. Devolve (dispersor, x0, y0)."""
    x0, y0 = free_spot(game, w + 2, h + 2)
    x0, y0 = x0 + 1, y0 + 1
    room(game.base, x0, y0, w, h, door=(x0 + 1, y0 + h) if door else (None, None), gap=gap)
    m = Machine(C.DISPENSER, x0, y0)
    if water:
        m.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", water)
    if dispenser:
        game.machines.append(m)
    stand_at(game, x0 + 2, y0 + 1)
    return m, x0, y0


def run(game, seconds, step=0.05):
    for _ in range(round(seconds / step)):
        game.update(step, Controls())


def test_dispenser_recipe_power_and_placing(game):
    m = C.MACHINES[C.DISPENSER]
    assert m.name == "Dispersor de O₂" and C.POWER_USE[C.DISPENSER] == 1 and C.MACHINE_CATEGORY[C.DISPENSER] == "base"
    assert len(Machine(C.DISPENSER, 3, 3).storage) == C.DISPENSER_SLOTS == 1
    x0, y0 = free_spot(game, 6, 4)
    stand_at(game, x0 + 2, y0 + 2)
    d = build_now(game, C.DISPENSER, (x0, y0))
    assert d is not None and d.is_dispenser
    assert game.power.consumption == 1


def test_dispenser_states(game):
    d, x0, y0 = demo_base(game, water=1)
    assert game.dispenser_state(d) == "sealed"
    d.storage.slots[0] = None
    assert game.dispenser_state(d) == "dry"
    d.storage.slots[0] = Stack("water_capsule", 1)
    game.base.remove(game.base.get((x0 + 4, y0)))                # abre um furo
    assert game.dispenser_state(d) == "leak" and game.seal_of(d).leak == (x0 + 4, y0)
    game.base.add(BaseBlock(C.BASE_WALL, x0 + 4, y0))
    assert game.dispenser_state(d) == "sealed"
    for label in ("sealed", "leak", "dry", "nopower"):
        assert label in C.STATE_LABEL
    assert C.STATE_LABEL["sealed"] == "Vedado ✓" and C.STATE_LABEL["leak"] == "Vazamento" and C.STATE_LABEL["dry"] == "Sem água"


def test_dispenser_without_power_is_stopped(game, monkeypatch):
    d, *_ = demo_base(game, water=2)
    monkeypatch.setattr(C, "POD_POWER", 0)
    assert game.dispenser_state(d) == "nopower" and not game.air_ok(d)
    game.player.o2 = 10
    assert not game.in_sealed_base()


def test_dispenser_burns_one_capsule_every_x_minutes_and_only_when_sealed(game):
    d, x0, y0 = demo_base(game, water=2)
    game.base.remove(game.base.get((x0 + 4, y0)))                # furado: não gasta
    run(game, 10)
    assert d.capsules == 2 and d.burn == 0
    game.base.add(BaseBlock(C.BASE_WALL, x0 + 4, y0))
    game._update_machines(1.0)
    assert d.capsules == 1 and 0 < d.burn < C.DISPENSER_CAPSULE_TIME      # a 1ª saiu do slot pra queimar
    game._update_machines(C.DISPENSER_CAPSULE_TIME)
    assert d.capsules == 0 and d.burn > 0                          # a 2ª começou
    assert game.dispenser_state(d) == "sealed"
    game._update_machines(C.DISPENSER_CAPSULE_TIME)
    assert d.capsules == 0 and d.burn == 0 and game.dispenser_state(d) == "dry"
    assert [e for e in game.events if e[0] == "dispenser_dry"] == [("dispenser_dry", d.anchor)]   # uma vez só
    game._update_machines(30)
    assert len([e for e in game.events if e[0] == "dispenser_dry"]) == 1


def test_o2_recharges_inside_the_sealed_base_and_not_outside(game):
    d, x0, y0 = demo_base(game, water=1)
    game.player.x, game.player.y = 900.0, 900.0                    # fora de tudo (longe da cápsula)
    game.update(0.05, Controls())
    game.o2 = 50.0
    run(game, 1.0)
    assert game.o2 < 50.0                                          # fora: gasta
    stand_at(game, x0 + 2, y0 + 1)
    game.o2 = 50.0
    run(game, 1.0)
    assert game.o2 == pytest.approx(50.0 + C.O2_REFILL * 1.0, abs=0.01)   # dentro: igual à zona da cápsula
    assert game.in_sealed_base()


def test_o2_does_not_recharge_when_leaking_or_dry(game):
    d, x0, y0 = demo_base(game, water=1)
    game.base.remove(game.base.get((x0 + 4, y0)))
    game.o2 = 50.0
    run(game, 1.0)
    assert game.o2 < 50.0
    game.base.add(BaseBlock(C.BASE_WALL, x0 + 4, y0))
    d.storage.slots[0] = None
    game.o2 = 50.0
    run(game, 1.0)
    assert game.o2 < 50.0                                          # selada mas sem água


def test_player_standing_on_the_door_still_breathes(game):
    d, x0, y0 = demo_base(game, water=1)
    stand_at(game, x0 + 1, y0 + 3)                                 # no tile da porta
    assert game.in_sealed_base()


def test_dispenser_slot_takes_only_capsules(game):
    d, *_ = demo_base(game)
    give(game, water_capsule=3, iron=2)
    cap = next(i for i, s in enumerate(game.inventory.slots) if s and s.item == "water_capsule")
    ir = next(i for i, s in enumerate(game.inventory.slots) if s and s.item == "iron")
    assert game.dispenser_put(d, ir) == 0
    assert game.dispenser_put(d, cap, 1) == 1 and d.capsules == 1
    assert game.dispenser_put(d, cap) == 2 and d.capsules == 3
    assert game.melter_take(d) == 3 and d.capsules == 0 and game.inventory.count("water_capsule") == 3


def test_dispenser_returns_its_water_when_dismantled(game):
    d, x0, y0 = demo_base(game, water=2)
    stand_at(game, x0 + 1, y0 + 1)
    before = game.inventory.count("water_capsule")
    assert game.dismantle(d)
    assert game.inventory.count("water_capsule") == before + 2


# ---------------------------------------------------------------- sons (eventos)
def test_sealing_plays_once_with_cooldown_and_never_on_load(game, tmp_path):
    d, x0, y0 = demo_base(game, water=1, gap=None)
    d.sealed_prev = False                                         # recém-construído
    game.events.clear()
    game.update(0.05, Controls())
    assert [e[0] for e in game.events if e[0] == "base_sealed"] == ["base_sealed"]
    game.events.clear()
    # tirar e pôr a parede de novo dentro do cooldown de 3 s: não soa
    wall = game.base.get((x0 + 4, y0))
    game.base.remove(wall)
    game.update(0.05, Controls())
    game.base.add(wall)
    game.update(0.05, Controls())
    assert not any(e[0] == "base_sealed" for e in game.events)
    # passado o cooldown, vedar de novo soa
    game.base.remove(wall)
    game.update(0.05, Controls())
    run(game, C.SEAL_SOUND_COOLDOWN + 0.5)
    game.base.add(wall)
    game.update(0.05, Controls())
    assert any(e[0] == "base_sealed" for e in game.events)
    # o load nunca soa
    path = tmp_path / "slot1.json"
    assert save.write_save(game, path)
    loaded = save.load_game(path)
    assert not any(e[0] == "base_sealed" for e in loaded.events)
    loaded.update(0.05, Controls())
    assert not any(e[0] == "base_sealed" for e in loaded.events)


def test_leak_alert_every_4_seconds_while_leaking_and_near(game):
    d, x0, y0 = demo_base(game, water=1)
    game.update(0.05, Controls())                                  # vedada: marca que já esteve
    assert d.sealed_once
    game.base.remove(game.base.get((x0 + 4, y0)))
    game.events.clear()
    run(game, 9.0)
    alerts = [e for e in game.events if e[0] == "leak_alert"]
    assert len(alerts) == 3                                        # t≈0, 4 e 8
    game.player.x, game.player.y = d.anchor[0] + (C.LEAK_ALERT_RANGE + 8) * T, d.anchor[1]   # longe demais
    game.events.clear()
    run(game, 9.0)
    assert not any(e[0] == "leak_alert" for e in game.events)


def test_unfinished_base_does_not_nag_with_leak_alerts(game):
    d, x0, y0 = demo_base(game, water=1, gap=(0, 0))               # sala vedada...
    game.base.remove(game.base.get((x0 + 4, y0)))                  # ...mas com furo desde o começo (nunca vedou)
    game.events.clear()
    run(game, 9.0)
    assert not any(e[0] == "leak_alert" for e in game.events)
    assert game.dispenser_state(d) == "leak"                        # o tile ainda pisca


def test_leak_alert_stops_when_sealed(game):
    d, x0, y0 = demo_base(game, water=1)
    game.update(0.05, Controls())
    wall = game.base.get((x0 + 4, y0))
    game.base.remove(wall)
    run(game, 1.0)
    game.base.add(wall)
    game.events.clear()
    run(game, 9.0)
    assert not any(e[0] == "leak_alert" for e in game.events)


# ---------------------------------------------------------------- save v10 (os blocos da base entraram no v9)
def test_save_version_is_10_and_blocks_roundtrip(game, tmp_path):
    d, x0, y0 = demo_base(game, water=2)
    d.burn = 42.5
    dd = BaseBlock(C.BASE_DOOR2, x0 - 1 - 3, y0, "v")
    game.base.add(dd)
    data = save.state_to_dict(game)
    assert data["version"] == save.SAVE_VERSION == 10
    entries = data["layers"]["surface"]["base"]
    double = [e for e in entries if e["kind"] == C.BASE_DOOR2]
    assert double == [{"kind": C.BASE_DOOR2, "tx": dd.tx, "ty": dd.ty, "orient": "v"}]    # um objeto só, com âncora e orientação
    assert len(entries) == len(game.base.blocks)
    path = tmp_path / "slot1.json"
    assert save.write_save(game, path)
    loaded = save.load_game(path)
    assert len(loaded.base.blocks) == len(game.base.blocks)
    lb = loaded.base.get((dd.tx, dd.ty))
    assert lb.is_double and lb.orient == "v" and lb is loaded.base.get((dd.tx, dd.ty + 1))
    ld = next(m for m in loaded.machines if m.is_dispenser)
    assert ld.capsules == 2 and ld.burn == pytest.approx(42.5) and ld.sealed_prev is None
    assert loaded.seal_of(ld).ok                                  # a vedação é recalculada no load
    assert loaded.dispenser_state(ld) == "sealed"


def test_dispenser_save_sanitizes_the_slot():
    m = Machine(C.DISPENSER, 3, 3)
    m.storage.slots[0] = Stack("water_capsule", 4)
    data = save.machine_to_dict(m)
    data["storage"] = [["iron", 9]]
    data["burn"] = 99999
    back = save.machine_from_dict(data)
    assert back.capsules == 0 and back.burn == C.DISPENSER_CAPSULE_TIME


def test_load_ignores_unknown_and_overlapping_blocks():
    grid = save.base_from_list([{"kind": "base_wall", "tx": 3, "ty": 3}, {"kind": "base_wall", "tx": 3, "ty": 3},
                                {"kind": "banana", "tx": 1, "ty": 1},
                                {"kind": "base_door2", "tx": 3, "ty": 3, "orient": "h"},
                                {"kind": "base_door2", "tx": 5, "ty": 3, "orient": "h"}])
    assert len(grid.blocks) == 2 and grid.get((6, 3)) is grid.get((5, 3))


def test_no_base_no_cost_in_a_plain_save(game, tmp_path):
    data = save.state_to_dict(game)
    assert "base" not in data["layers"]["surface"]


# ---------------------------------------------------------------- assets e sons promovidos
@pytest.mark.parametrize("name", ["door_open", "door_close", "base_sealed", "dispenser_hum", "leak_alert", "dispenser_dry"])
def test_audio_files_are_in_assets(name):
    assert (C.AUDIO_DIR / f"{name}.wav").exists() and name in C.VOLUME


@pytest.mark.parametrize("name", [
    "base_floor_0", "base_floor_1", "base_floor_2", "base_floor_3", "base_wall_top", "base_wall_face",
    "base_door_h_n", "base_door_h_s", "base_door_v_e", "base_door_v_w",
    "base_door2_h_n", "base_door2_h_s", "base_door2_v_e", "base_door2_v_w",
    "icon_base_floor", "icon_base_wall", "icon_base_door", "icon_base_door_double", "icon_o2_dispenser",
    "icon_water_capsule", "leak_blink", "machine_o2_dispenser", "anim/anim_machine_o2_dispenser",
    "anim/anim_machine_o2_dispenser_leak"])
def test_sprites_are_in_assets(name):
    assert (C.SPRITES_DIR / f"{name}.png").exists()
