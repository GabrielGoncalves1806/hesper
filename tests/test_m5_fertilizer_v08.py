"""v0.8 M5 Task 3: o Adubo (acelera só o growth do Cultivador, gasta com o tempo de crescimento, teto, save)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from game import config as C  # noqa: E402
from game import save  # noqa: E402
from game.inventory import Stack  # noqa: E402
from tests.test_cultivator_v08 import base_with_cultivator, plant, tick  # noqa: E402,F401
from tests.test_base import game  # noqa: E402,F401  (fixture)

CYCLE = C.CROPS["algae"].cycle


def test_put_consumes_one_and_adds_time(base_with_cultivator):
    state, cult = base_with_cultivator
    state.inventory.slots[0] = Stack(C.FERTILIZER, 5)
    assert state.cultivator_put(cult, 0) == 1
    assert state.inventory.slots[0].count == 4 and cult.boost == C.FERTILIZER_TIME
    assert state.cultivator_put(cult, 0, 3) == 1 and cult.boost == 2 * C.FERTILIZER_TIME
    assert cult.storage.slots[C.CULT_SEED_SLOT] is None          # não ocupa slot


def test_put_capped_at_max(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.boost = C.FERTILIZER_MAX - 10
    state.inventory.slots[0] = Stack(C.FERTILIZER, 2)
    assert state.cultivator_put(cult, 0) == 1 and cult.boost == C.FERTILIZER_MAX
    assert state.cultivator_put(cult, 0) == 0                    # cheio: recusa e não gasta
    assert state.inventory.slots[0].count == 1


def test_boost_halves_time_to_mature(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, tank=5)
    cult.boost = C.FERTILIZER_MAX
    tick(state, CYCLE / C.FERTILIZER_BOOST * 0.5)
    assert cult.growth == pytest.approx(0.5, abs=0.02)
    assert cult.boost == pytest.approx(C.FERTILIZER_MAX - CYCLE / C.FERTILIZER_BOOST * 0.5, abs=0.5)


def test_biomass_and_water_unchanged(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, tank=5)
    b0 = state.indices["biomass"]
    tick(state, 20)
    plain = (state.indices["biomass"] - b0, 5 - cult.tank)
    cult.growth, cult.tank, cult.boost = 0.0, 5.0, C.FERTILIZER_MAX
    b1 = state.indices["biomass"]
    tick(state, 20)
    assert (state.indices["biomass"] - b1, 5 - cult.tank) == pytest.approx(plain, rel=1e-3)
    assert cult.growth > (20 / CYCLE) * 1.9


def test_boost_runs_out_mid_growth(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, tank=5)
    cult.boost = 10.0
    tick(state, 30)
    assert cult.boost == 0.0
    assert cult.growth == pytest.approx((10 * C.FERTILIZER_BOOST + 20) / CYCLE, abs=0.01)


def test_no_spend_when_stopped(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.boost = 100.0
    tick(state, 10)                                               # sem muda
    assert cult.boost == 100.0
    plant(cult, water=0, tank=0)                                  # seco
    tick(state, 10)
    assert cult.boost == 100.0 and cult.growth == 0.0


def test_save_roundtrip_and_old_default(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.boost = 77.5
    data = save.machine_to_dict(cult)
    assert data["boost"] == 77.5
    back = save.machine_from_dict(data)
    assert back.boost == 77.5
    data["boost"] = 99999
    assert save.machine_from_dict(data).boost == C.FERTILIZER_MAX
    del data["boost"]
    assert save.machine_from_dict(data).boost == 0.0
