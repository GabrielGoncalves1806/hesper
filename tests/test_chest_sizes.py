"""v0.6 M1 · Task 1: três tamanhos de baú (Simples 8, Normal 16, Grande 24 com diagrama no T1)."""

import random

import pytest

from game import config as C
from game.inventory import Stack
from game.objectives import OBJECTIVES
from game.systems import GameState, Machine
from tests.helpers import build_now, give

SIZES = {"chest_small": 8, "chest": 16, "chest_large": 24}


def make_state(ti: float = 0) -> GameState:
    s = GameState(rng=random.Random(1))
    for k in s.indices:
        s.indices[k] = 0
    s.indices["o2"] = ti
    return s


def spot(s: GameState, dx: int = 2) -> tuple[int, int]:
    px, py = s.player.tile
    return px + dx, py


@pytest.mark.parametrize("kind,size", SIZES.items())
def test_each_kind_has_its_size_and_is_a_logistic_chest(kind, size):
    s = make_state()
    c = Machine(kind, *spot(s))
    assert len(c.storage) == size == C.CHEST_SIZES[kind]
    assert c.is_chest and c.is_logistic and c.size == 1
    s.machines.append(c)
    assert c in s.chests and c in s.base_chests()


def test_small_builds_from_the_start_normal_at_ti_50k_and_large_needs_the_diagram():
    s = make_state()
    for kind in ("chest_small", "chest"):
        assert s.build_status(kind) == "no_constructor"
    give(s, constructor=1, iron=30, silicon=5, iron_ingot=10)      # M5: o baú e o baú grande pedem lingote
    assert s.build_status("chest_small") == "ok" and s.build_status("chest") == "locked"
    s.indices["o2"] = C.CHEST_UNLOCK_TI - 1
    assert s.build_status("chest") == "locked"
    s.indices["o2"] = C.CHEST_UNLOCK_TI                  # Baú normal libera em Ti 50.000 (dono, 2026-10-15)
    assert C.CHEST_UNLOCK_TI == 50_000 and s.build_status("chest") == "ok"
    assert s.build_status("chest_large") == "blueprint"
    assert not s.can_build("chest_large", spot(s))
    s.blueprints.add("chest_large")
    assert s.build_status("chest_large") == "ok"
    assert s.build("chest_large", spot(s))
    assert s.machines[-1].kind == "chest_large" and len(s.machines[-1].storage) == 24
    assert s.machines[-1].name == C.CHEST_DEFAULT_NAME


def test_chest_diagram_is_locked_by_ti_then_read_unlocks_the_large_chest():
    cost = {"iron_ingot": 4, "circuit": 1}                # v0.6 Fundo M5
    assert C.MACHINES["diagram_chest_large"].cost == cost and not C.MACHINES["diagram_chest_large"].placeable
    assert C.DIAGRAM_BENCH["chest_large"] == "t1"
    s = make_state(ti=89_999)
    give(s, **cost)
    assert s.recipe_status("diagram_chest_large") == "locked"
    s = make_state(ti=90_000)
    assert s.recipe_status("diagram_chest_large") == "missing"
    give(s, **cost)
    assert s.recipe_status("diagram_chest_large") == "ok"
    assert s.craft("diagram_chest_large")
    assert s.read_diagram("diagram_chest_large", "t1") == "ok"
    assert "chest_large" in s.blueprints
    assert s.recipe_status("diagram_chest_large") == "known"


@pytest.mark.parametrize("kind", SIZES)
def test_dismantle_returns_the_cost_and_only_when_empty(kind):
    s = make_state()
    s.blueprints.add("chest_large")
    c = build_now(s, kind, spot(s))
    assert c is not None
    res, n = next(iter(C.CHEST_COST[kind].items()))      # M5: o baú e o baú grande custam lingote
    spent = s.inventory.count(res)
    c.storage.slots[0] = Stack("iron", 5)
    assert not s.dismantle(c) and c in s.machines
    c.storage.slots[0] = None
    assert s.dismantle(c) and c not in s.machines
    assert s.inventory.count(res) == spent + n


@pytest.mark.parametrize("kind", SIZES)
def test_objective_build_a_chest_accepts_any_size(kind):
    obj = next(o for o in OBJECTIVES if o.text == "Construa um baú")
    s = make_state()
    s.blueprints.add("chest_large")
    assert not obj.done(s)
    assert build_now(s, kind, spot(s)) is not None
    assert obj.done(s)


def test_chest_panel_logistics_sits_right_under_the_grid_rows():
    from game.ui import UI
    ys = {k: UI._chest_logi_y(Machine(k, 1, 1)) for k in SIZES}
    assert ys["chest_large"] == 100
    assert ys["chest_large"] - ys["chest"] == ys["chest"] - ys["chest_small"] > 0

