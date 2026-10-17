"""v0.8 M4 · Task 3: o Microscópio (gelo → amostra por chance) e o diagrama dele no laboratório da Ilves."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game.inventory import Stack, max_stack  # noqa: E402
from game.layers import CAVE  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from tests.helpers import build_now  # noqa: E402
from tests.test_base import free_spot, stand_at  # noqa: E402
from tests.test_base import game  # noqa: E402,F401  (fixture)
from tests.test_cultivator_v08 import tick  # noqa: E402
from tests.test_lab_v08 import hold_scan, lab_prop, new_game  # noqa: E402


def make_microscope(state, tile=(70, 70), ice=5, **kw):
    """Microscópio na camada ativa (a máquina nasce pronta), com `ice` gelo na entrada."""
    m = Machine(C.MICROSCOPE, *tile, **kw)
    if ice:
        m.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", ice)
    state.machines.append(m)
    return m


# ---------------------------------------------------------------- registro e diagrama
def test_microscope_is_registered():
    t = C.MACHINES[C.MICROSCOPE]
    assert t.name == "Microscópio" and t.cost == {"iron_ingot": 4, "silicon": 6, "circuit": 1}
    assert t.unlock_ti == 0 and t.unlock_stage == 0 and t.sprite == "machine_microscope"
    assert C.POWER_USE[C.MICROSCOPE] == 1 and C.MACHINE_CATEGORY[C.MICROSCOPE] == "automation"
    assert C.MACHINE_ORDER.index(C.MICROSCOPE) == C.MACHINE_ORDER.index(C.CULTIVATOR) + 1
    assert C.MIC_SLOTS == 4 and C.MIC_ICE_SLOT == 0
    assert C.MIC_OUT_SLOTS == {"sample_basic": 1, "sample_mutant": 2, "sample_rare": 3}
    assert C.MICROSCOPE_TIME == 20.0 and C.MICROSCOPE_REACH == C.MELTER_REACH
    assert C.BLUEPRINTS[C.MICROSCOPE] == "Microscópio" and C.RECIPE_BLUEPRINT[C.MICROSCOPE] == C.MICROSCOPE
    assert C.DIAGRAM_BENCH[C.MICROSCOPE] == "t1" and C.MICROSCOPE not in C.WRECK_DIAGRAMS
    assert len(Machine(C.MICROSCOPE, 0, 0).storage) == C.MIC_SLOTS


def test_microscope_is_a_diagram_from_the_lab():
    state = new_game(7)
    assert state.recipe_status(C.MICROSCOPE) == "blueprint"
    mic = lab_prop(state, "prop_microscope_digital")
    assert state.can_scan(mic) is True
    hold_scan(state, mic)
    assert C.MICROSCOPE in state.blueprints
    assert "prop_microscope_digital" not in state.scanned
    assert ("scan_done", C.MICROSCOPE) in state.events
    assert state.recipe_status(C.MICROSCOPE) != "blueprint"
    assert state.can_scan(mic) is False                       # já tem o diagrama


def test_scan_notice_text_comes_from_blueprints():
    # o App avisa f"Projeto liberado: {C.BLUEPRINTS[id]}" no ("scan_done", id)
    assert f"Projeto liberado: {C.BLUEPRINTS[C.MICROSCOPE]}" == "Projeto liberado: Microscópio"


def test_microscope_needs_the_diagram_then_can_be_built(game):
    x0, y0 = free_spot(game, 4, 4)
    stand_at(game, x0 + 1, y0 + 1)
    assert build_now(game, C.MICROSCOPE, (x0, y0)) is None
    game.blueprints.add(C.MICROSCOPE)
    m = build_now(game, C.MICROSCOPE, (x0, y0))
    assert m is not None and m.is_microscope and len(m.storage) == C.MIC_SLOTS


# ---------------------------------------------------------------- análise
def test_one_analysis_eats_one_ice(game):
    mic = make_microscope(game, ice=3)
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert mic.storage.count("ice") == 2


def test_odds_match_in_a_big_sample():
    state = GameState(rng=random.Random(1234))
    n = 20_000
    got = [state.microscope_roll() for _ in range(n)]
    assert got.count("sample_basic") / n == pytest.approx(0.30, abs=0.015)
    assert got.count("sample_mutant") / n == pytest.approx(0.15, abs=0.015)
    assert got.count("sample_rare") / n == pytest.approx(0.05, abs=0.01)
    assert got.count(None) / n == pytest.approx(0.50, abs=0.015)


@pytest.mark.parametrize("r, want", [(0.0, "sample_basic"), (0.2999, "sample_basic"), (0.30, "sample_mutant"),
                                     (0.4499, "sample_mutant"), (0.45, "sample_rare"), (0.4999, "sample_rare"),
                                     (0.50, None), (0.99, None)])
def test_roll_thresholds(r, want):
    state = GameState(rng=random.Random(1))
    state.rng.random = lambda: r
    assert state.microscope_roll() == want


def test_sample_goes_to_its_own_slot(game, monkeypatch):
    mic = make_microscope(game)
    monkeypatch.setattr(game, "microscope_roll", lambda: "sample_mutant")
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert mic.storage.slots[C.MIC_OUT_SLOTS["sample_mutant"]] == Stack("sample_mutant", 1)
    assert any(e[0] == "sample_found" and e[1] is mic and e[2] == "sample_mutant" for e in game.events)
    tick(game, C.MICROSCOPE_TIME)
    assert mic.storage.slots[C.MIC_OUT_SLOTS["sample_mutant"]] == Stack("sample_mutant", 2)


def test_nothing_found_still_eats_the_ice(game, monkeypatch):
    mic = make_microscope(game, ice=2)
    monkeypatch.setattr(game, "microscope_roll", lambda: None)
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert mic.storage.count("ice") == 1
    assert all(mic.storage.slots[s] is None for s in C.MIC_OUT_SLOTS.values())
    assert ("microscope_done", mic, None) in game.events


def test_full_output_stops_before_eating_ice(game):
    mic = make_microscope(game, ice=3)
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", max_stack("sample_rare"))
    tick(game, C.MICROSCOPE_TIME * 2)
    assert game.microscope_blocker(mic) == "out_full"
    assert mic.storage.count("ice") == 3 and mic.timer == 0.0 and not mic.analyzing


def test_progress_is_kept_when_it_stops(game):
    mic = make_microscope(game, ice=3)
    tick(game, 5.0)
    assert mic.timer == pytest.approx(5.0, abs=0.05) and mic.analyzing
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", max_stack("sample_basic"))
    tick(game, 30.0)
    assert mic.timer == pytest.approx(5.0, abs=0.05) and mic.storage.count("ice") == 3


def test_no_ice_no_analysis(game):
    mic = make_microscope(game, ice=0)
    assert game.microscope_blocker(mic) == "no_ice"
    tick(game, 5.0)
    assert mic.timer == 0.0 and not mic.analyzing


def test_microscope_works_in_the_cave(game):
    game.enter_layer(CAVE)
    mic = make_microscope(game, tile=(60, 60), ice=3)
    assert mic in game.layers[CAVE].machines
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert mic.storage.count("ice") == 2


def test_power_deficit_slows_the_microscope(game):
    mic = make_microscope(game)
    game._update_machines(1.0)
    assert mic.timer == pytest.approx(1.0 * game.power.factor)


def test_microscope_uses_power(game):
    before = game.power.consumption
    make_microscope(game)
    assert game.power.consumption == before + C.POWER_USE[C.MICROSCOPE]


def test_microscope_put_only_takes_ice(game):
    mic = make_microscope(game, ice=0)
    game.inventory.slots[0] = Stack("iron", 5)
    assert game.microscope_put(mic, 0) == 0
    game.inventory.slots[0] = Stack("ice", 5)
    assert game.microscope_put(mic, 0, 1) == 1 and game.microscope_put(mic, 0) == 4
    assert mic.storage.slots[C.MIC_ICE_SLOT] == Stack("ice", 5) and game.inventory.slots[0] is None


# ---------------------------------------------------------------- E, logística e desmonte
def test_interaction_opens_microscope(game):
    m = make_microscope(game, tile=(64, 70))
    game.player.x, game.player.y = (64 + 0.5) * C.TILE, (70 + 1) * C.TILE + 20
    x, y, w, h = m.sprite_rect
    assert game.nearby_microscope() is m
    assert game.interactable_at(x + w / 2, y + h / 2) == ("microscope", m)
    assert game.interaction() == ("microscope", m) and game.in_reach("microscope", m)
    m.build = 1.0
    assert game.nearby_microscope() is None
    m.build = 0.0
    game.player.x += 5 * C.TILE
    assert game.nearby_microscope() is None and not game.in_reach("microscope", m)


def test_microscope_is_logistic_with_a_chip():
    m = Machine(C.MICROSCOPE, 0, 0)
    assert m.is_logistic and m.needs_chip and not m.in_network


def test_microscope_dismantle_returns_contents(game):
    m = make_microscope(game, ice=2, chip=True)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 3)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", 1)
    out = game.dismantle_returns(m)
    assert out["iron_ingot"] == 4 and out["silicon"] == 6 and out["circuit"] == 1
    assert out["ice"] == 2 and out["sample_basic"] == 3 and out["sample_rare"] == 1 and out["chip"] == 1
