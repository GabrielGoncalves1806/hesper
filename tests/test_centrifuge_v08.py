"""v0.8 M4 Task 4: a Centrífuga (1 alga + 1 amostra → planta, por chance)."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import layers  # noqa: E402
from game.inventory import Stack, max_stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from tests.helpers import build_now  # noqa: E402
from tests.test_base import free_spot, stand_at  # noqa: E402
from tests.test_base import game  # noqa: E402,F401  (fixture)
from tests.test_water_v08 import tick  # noqa: E402


def make_centrifuge(state, tile=(74, 70), algae=5, sample=("sample_basic", 5), **kw):
    """Centrífuga na camada ativa (nasce pronta), com `algae` algas e a pilha `sample` de amostra."""
    m = Machine(C.CENTRIFUGE, *tile, **kw)
    if algae:
        m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", algae)
    if sample:
        m.storage.slots[C.CENT_SAMPLE_SLOT] = Stack(*sample)
    state.machines.append(m)
    return m


def test_centrifuge_is_registered():
    t = C.MACHINES[C.CENTRIFUGE]
    assert t.name == "Centrífuga" and t.placeable and t.index is None and t.sprite == "machine_centrifuge"
    assert t.cost == {"iron_ingot": 6, "copper_ingot": 2, "wire": 4} and t.unlock_ti == 0
    assert t.unlock_stage == C.ALGAE_STAGE
    assert C.POWER_USE[C.CENTRIFUGE] == 1 and C.MACHINE_CATEGORY[C.CENTRIFUGE] == "automation"
    assert C.MACHINE_ORDER.index(C.CENTRIFUGE) > C.MACHINE_ORDER.index(C.CULTIVATOR)
    assert (C.CENT_ALGAE_SLOT, C.CENT_SAMPLE_SLOT, C.CENT_SLOTS) == (0, 1, 5)
    assert C.CENT_OUT_SLOTS == {"plant_1": 2, "plant_2": 3, "plant_3": 4}
    assert set(C.CENTRIFUGE_RECIPES) == set(C.SAMPLE_ITEMS) and C.CENTRIFUGE_FPS == 10
    m = Machine(C.CENTRIFUGE, 0, 0)
    assert m.is_centrifuge and len(m.storage) == C.CENT_SLOTS and m.is_logistic and m.needs_chip and not m.in_network


def test_centrifuge_unlocks_at_the_algae_stage():
    state = GameState()
    state.inventory.add("iron_ingot", 20)
    state.inventory.add("copper_ingot", 20)
    state.inventory.add("wire", 20)
    state.stage = C.MIST_STAGE
    assert state.recipe_status(C.CENTRIFUGE) == "locked"
    state.stage = C.ALGAE_STAGE
    assert state.recipe_status(C.CENTRIFUGE) == "ok"


def test_centrifuge_can_be_built(game):
    game.stage = max(game.stage, C.ALGAE_STAGE)              # a trava da receita (Task 1) não atrapalha
    x0, y0 = free_spot(game, 4, 4)
    stand_at(game, x0 + 1, y0 + 1)
    m = build_now(game, C.CENTRIFUGE, (x0, y0))
    assert m is not None and m.is_centrifuge and game.power.consumption >= 1


def test_one_cycle_eats_one_algae_and_one_sample(game):
    m = make_centrifuge(game, algae=3, sample=("sample_basic", 3))
    tick(game, C.CENTRIFUGE_TIME - 1)
    assert m.storage.count("algae") == 3 and m.timer > 0 and m.spinning
    tick(game, 2)
    assert m.storage.count("algae") == 2 and m.storage.count("sample_basic") == 2
    assert any(e[0] == "centrifuge_done" and e[1] is m for e in game.events)


@pytest.mark.parametrize("sample,plant,chance", [("sample_basic", "plant_1", 0.60),
                                                 ("sample_mutant", "plant_2", 0.45),
                                                 ("sample_rare", "plant_3", 0.30)])
def test_centrifuge_odds(sample, plant, chance):
    state = GameState(rng=random.Random(99))
    m = make_centrifuge(state, algae=0, sample=None)
    hits, n = 0, 4_000
    for _ in range(n):
        m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 1)
        m.storage.slots[C.CENT_SAMPLE_SLOT] = Stack(sample, 1)
        m.storage.slots[C.CENT_OUT_SLOTS[plant]] = None
        m.timer = C.CENTRIFUGE_TIME - 1e-6
        state._update_centrifuge(m, 0.01)                    # direto: o tick mexe no rng por outras coisas
        hits += m.storage.count(plant)
    assert hits / n == pytest.approx(chance, abs=0.03)


def test_success_goes_to_the_plant_slot(game, monkeypatch):
    m = make_centrifuge(game, algae=2, sample=("sample_mutant", 2))
    monkeypatch.setattr(game.rng, "random", lambda: 0.0)
    tick(game, C.CENTRIFUGE_TIME + 0.1)
    assert m.storage.slots[C.CENT_OUT_SLOTS["plant_2"]] == Stack("plant_2", 1)
    assert ("centrifuge_done", m, "plant_2") in game.events


def test_failure_eats_both_and_gives_nothing(game, monkeypatch):
    m = make_centrifuge(game, algae=1, sample=("sample_rare", 1))
    monkeypatch.setattr(game.rng, "random", lambda: 0.99)
    tick(game, C.CENTRIFUGE_TIME + 0.1)
    assert m.storage.count("algae") == 0 and m.storage.count("sample_rare") == 0
    assert m.storage.count("plant_3") == 0
    assert ("centrifuge_done", m, None) in game.events
    assert game.centrifuge_blocker(m) == "no_algae" and not m.spinning


def test_full_plant_slot_stops_the_centrifuge(game):
    m = make_centrifuge(game, algae=3, sample=("sample_basic", 3))
    m.storage.slots[C.CENT_OUT_SLOTS["plant_1"]] = Stack("plant_1", max_stack("plant_1"))
    tick(game, C.CENTRIFUGE_TIME * 2)
    assert game.centrifuge_blocker(m) == "out_full" and not m.spinning
    assert m.storage.count("algae") == 3 and m.storage.count("sample_basic") == 3 and m.timer == 0


def test_full_slot_of_another_plant_does_not_stop_it(game):
    m = make_centrifuge(game, algae=3, sample=("sample_basic", 3))
    m.storage.slots[C.CENT_OUT_SLOTS["plant_3"]] = Stack("plant_3", max_stack("plant_3"))
    assert game.centrifuge_blocker(m) is None


def test_centrifuge_blockers(game):
    m = make_centrifuge(game, algae=0, sample=("sample_basic", 1))
    assert game.centrifuge_blocker(m) == "no_algae"
    m = make_centrifuge(game, tile=(78, 70), algae=1, sample=None)
    assert game.centrifuge_blocker(m) == "no_sample"
    tick(game, 5.0)
    assert m.timer == 0.0 and not m.spinning


def test_centrifuge_works_in_the_cave(game):
    game.enter_layer(layers.CAVE)
    m = make_centrifuge(game, tile=(60, 60), algae=2, sample=("sample_basic", 2))
    tick(game, C.CENTRIFUGE_TIME + 0.5)
    assert m.storage.count("algae") == 1


def test_power_deficit_slows_the_centrifuge(game):
    m = make_centrifuge(game)
    game._update_machines(1.0)
    assert m.timer == pytest.approx(1.0 * game.power.factor)


def test_centrifuge_put(game):
    m = make_centrifuge(game, algae=0, sample=("sample_basic", 1))
    game.inventory.slots[0] = Stack("algae", 4)
    assert game.centrifuge_put(m, 0, 1) == 1 and game.centrifuge_put(m, 0) == 3
    assert m.storage.slots[C.CENT_ALGAE_SLOT] == Stack("algae", 4)
    game.inventory.slots[1] = Stack("sample_rare", 2)
    assert game.centrifuge_put(m, 1) == 0                    # o slot da amostra já tem a simples
    game.inventory.slots[1] = Stack("sample_basic", 2)
    assert game.centrifuge_put(m, 1) == 2 and m.storage.slots[C.CENT_SAMPLE_SLOT] == Stack("sample_basic", 3)
    game.inventory.slots[2] = Stack("ice", 2)
    assert game.centrifuge_put(m, 2) == 0
    game.inventory.slots[3] = Stack("plant_1", 2)
    assert game.centrifuge_put(m, 3) == 0                    # a saída só sai


def test_centrifuge_put_any_sample_when_empty(game):
    m = make_centrifuge(game, algae=0, sample=None)
    game.inventory.slots[0] = Stack("sample_rare", 2)
    assert game.centrifuge_put(m, 0) == 2 and m.storage.slots[C.CENT_SAMPLE_SLOT] == Stack("sample_rare", 2)


def test_interaction_opens_centrifuge(game):
    m = make_centrifuge(game, tile=(64, 70))
    game.player.x, game.player.y = (64 + 0.5) * C.TILE, (70 + 1) * C.TILE + 20
    x, y, w, h = m.sprite_rect
    assert game.nearby_centrifuge() is m
    assert game.interactable_at(x + w / 2, y + h / 2) == ("centrifuge", m)
    assert game.interaction() == ("centrifuge", m) and game.in_reach("centrifuge", m)
    m.build = 1.0
    assert game.nearby_centrifuge() is None
    m.build = 0.0
    game.player.x += 5 * C.TILE
    assert game.nearby_centrifuge() is None and not game.in_reach("centrifuge", m)


def test_centrifuge_dismantle_returns_contents(game):
    m = make_centrifuge(game, algae=2, sample=("sample_mutant", 1), chip=True)
    m.storage.slots[C.CENT_OUT_SLOTS["plant_2"]] = Stack("plant_2", 3)
    out = game.dismantle_returns(m)
    assert out["iron_ingot"] == 6 and out["copper_ingot"] == 2 and out["wire"] == 4
    assert out["algae"] == 2 and out["sample_mutant"] == 1 and out["plant_2"] == 3 and out["chip"] == 1
