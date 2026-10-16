"""v0.7 M4: prop maior que 1 tile (um prop fake 2×1 via monkeypatch; os props reais da Designer entram na Task 5)."""

import json
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import ruins, save  # noqa: E402
from game.props import Prop  # noqa: E402
from game.systems import GameState  # noqa: E402
from tests.helpers import give  # noqa: E402

KIND = "prop_fake_stack"


@pytest.fixture
def s(monkeypatch) -> GameState:
    ptype = C.PropType(KIND, "Pilha fake", dict(C.PROP_COST_SIMPLE), True, "floor", False, (2, 1))
    monkeypatch.setitem(C.PROPS, KIND, ptype)
    monkeypatch.setitem(C.MACHINES, KIND, C.MachineType(KIND, ptype.name, "decoração", dict(ptype.cost), None, 0, 0, "icon_" + KIND))
    monkeypatch.setattr(C, "PLAYER_PROPS", C.PLAYER_PROPS + (KIND,))
    state = GameState(rng=random.Random(1))
    give(state, constructor=1, iron=20)
    state.scanned.add(KIND)
    return state


def anchor(state):
    px, py = state.player.tile
    return px + 2, py


def test_tiles_and_both_tiles_point_to_the_prop(s):
    a = anchor(s)
    assert Prop(KIND, *a).tiles == [a, (a[0] + 1, a[1])]
    assert s.build(KIND, a)
    prop = s.prop_at(a)
    assert s.prop_at((a[0] + 1, a[1])) is prop and prop.tile == a


def test_collides_on_both_tiles(s):
    a = anchor(s)
    s.build(KIND, a)
    for dx in (0, 1):
        t = (a[0] + dx, a[1])
        assert s.prop_at(t).rect_at(t) in s.solids_near((t[0] * 32, t[1] * 32, 32, 32))


def test_not_placed_with_one_tile_occupied(s):
    a = anchor(s)
    assert s.build("prop_crate", (a[0] + 1, a[1]))
    assert not s.can_place(KIND, a)
    assert not s.can_place("prop_crate", (a[0] + 1, a[1]))


def test_not_placed_over_a_machine_tile(s):
    a = anchor(s)
    give(s, iron=50, silicon=50)
    assert s.build("lamp", (a[0] + 1, a[1]))
    assert not s.can_place(KIND, a)


def test_dismantle_takes_both_tiles_and_refunds_once(s):
    a = anchor(s)
    s.build(KIND, a)
    before = s.inventory.count("iron")
    assert s.dismantle(s.prop_at((a[0] + 1, a[1])))
    assert s.prop_at(a) is None and s.prop_at((a[0] + 1, a[1])) is None
    assert s.inventory.count("iron") == before + C.PROP_COST_SIMPLE["iron"]


def test_save_keeps_only_the_anchor_and_load_rebuilds(s):
    a = anchor(s)
    s.build(KIND, a)
    data = json.loads(json.dumps(save.state_to_dict(s)))
    assert data["layers"]["surface"]["props"] == [[KIND, *a]]
    t = save.state_from_dict(data)
    assert t.prop_at(a) is t.prop_at((a[0] + 1, a[1])) and t.prop_at(a).kind == KIND


def test_plan_needs_floor_on_every_tile():
    grid = ["#####", "#...#", "#####"]
    assert ruins.ok_in_plan(grid, 1, 1, "prop_table")
    C.PROPS[KIND] = C.PropType(KIND, "x", {}, True, "floor", False, (2, 1))
    try:
        assert ruins.ok_in_plan(grid, 1, 1, KIND) and ruins.ok_in_plan(grid, 2, 1, KIND)
        assert not ruins.ok_in_plan(grid, 3, 1, KIND)          # o tile da direita é parede
    finally:
        del C.PROPS[KIND]
