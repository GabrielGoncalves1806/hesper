"""v0.8 M6 · Task 3: o balance_sim conhece as plantas (tabela do Cultivador com a regra real, biomassa virtual, marcas
com o gargalo Ti/bio e a trava da Centrífuga). O sim é lento: 1 seed, 1 estratégia, o mínimo."""

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))

import balance_sim as sim  # noqa: E402

from game import config as C  # noqa: E402


@pytest.fixture(scope="module")
def proposal():
    return sim.load_overrides()


@pytest.fixture(scope="module")
def casual(proposal):
    """O casual da seed 1 com a proposta (3 cultivadores virtuais, o padrão)."""
    return sim.simulate("casual", seed=1, overrides=proposal)


# ---------------------------------------------------------------- 3a · tabela das plantas
def test_algae_row_follows_the_real_cultivator_rule():
    rows = sim.crop_table(hours=1.0)
    algae = next(r for r in rows if r["crop"] == "algae" and not r["fertilizer"])
    expected = 3600 / (C.CROPS["algae"].cycle * (1 - C.CULTIVATOR_HARVEST_AFTER))
    assert algae["harvests_h"] == pytest.approx(expected, rel=0.10)
    assert algae["bio_s"] == pytest.approx(C.CROPS["algae"].biomass, rel=0.01)   # água sempre cheia
    assert algae["water"] == pytest.approx(1.0, abs=0.01)
    assert algae["harvests_h"] <= algae["items_h"] <= 2 * algae["harvests_h"]   # 1 ou 2 por colheita
    assert algae["capsules_h"] == pytest.approx(3600 / C.CROPS["algae"].water_s, rel=0.05)
    fert = next(r for r in rows if r["crop"] == "algae" and r["fertilizer"])
    assert fert["harvests_h"] == pytest.approx(C.FERTILIZER_BOOST * algae["harvests_h"], rel=0.05)
    assert fert["bio_s"] == pytest.approx(algae["bio_s"], rel=0.01)             # o adubo não muda a biomassa/s
    assert fert["fertilizer_h"] == pytest.approx(3600 / C.FERTILIZER_TIME, rel=0.05)
    assert {r["crop"] for r in rows} == set(C.CROP_ITEMS) and len(rows) == 2 * len(C.CROP_ITEMS)


def test_crops_override_changes_the_cycle_and_is_restored():
    before = dict(C.CROPS)
    with sim.patched_config({"CROPS": {"algae": {"cycle": 150}}}):
        assert C.CROPS["algae"].cycle == 150 and C.CROPS["algae"].biomass == before["algae"].biomass
        assert C.CROPS["plant_1"] == before["plant_1"]
        row = sim._measure_crop("algae", False, 1.0)
    assert row["cycle"] == 150
    assert row["harvests_h"] == pytest.approx(3600 / (150 * (1 - C.CULTIVATOR_HARVEST_AFTER)), rel=0.10)
    assert C.CROPS == before


def test_plant_costs_come_from_the_real_recipes():
    assert sim.plant_cost(C.BACKPACK_T2) == {"algae": 2 * C.MACHINES[C.BACKPACK_T2].cost[C.FIBER]}
    per = C.CRAFT_YIELD[C.FERTILIZER]                     # o adubo sai 2 por receita
    assert sim.plant_cost(C.FERTILIZER) == pytest.approx({"algae": 1 / per, "plant_1": 2 / per})


def test_plant_times_closed_form_matches_the_rng():
    closed, rng = sim.plant_times(), sim.plant_times_rng(rounds=600)
    p = sim.sample_odds()
    assert closed["plant_3"] == pytest.approx(C.MICROSCOPE_TIME / p["plant_3"] + C.CENTRIFUGE_TIME)
    for key in (*sim.PLANTS, "all"):
        assert rng[key] == pytest.approx(closed[key], rel=0.10)
    assert closed["plant_1"] < closed["plant_2"] < closed["plant_3"] <= closed["all"]


# ---------------------------------------------------------------- 3b · simulação principal
def test_lab_opens_before_algae(casual):
    assert casual.finished
    assert casual.lab_at is not None and casual.lab_at < casual.milestones["Algas"]
    assert casual.bio_at >= max(casual.lab_at, casual.milestones["Úmido"])


def test_marks_use_ti_and_biomass(casual):
    assert set(casual.milestones) == {"Ti 500", "Árido", "Úmido", "Algas", "Musgo", "Verde"}
    assert set(casual.bottleneck) == {"Algas", "Musgo", "Verde"}
    assert set(casual.bottleneck.values()) <= {"Ti", "bio"}
    assert casual.biomass >= C.STAGES[-1].biomass and casual.ti_done <= casual.total + 1e-6
    order = [casual.milestones[m] for m in ("Ti 500", "Árido", "Úmido", "Algas", "Musgo", "Verde")]
    assert order == sorted(order)


def test_without_cultivators_algae_never_comes(proposal):
    none = dataclasses.replace(sim.STRATEGIES["casual"], cultivators=0)
    r = sim.simulate(none, seed=1, overrides=proposal, max_time=1.5 * 3600)
    assert "Úmido" in r.milestones and "Algas" not in r.milestones and not r.finished
    assert r.biomass == 0.0 and r.centrifuge_at is None


def test_centrifuge_only_after_algae_and_nothing_locked_is_tried(casual):
    assert casual.centrifuge_at is not None and casual.centrifuge_at >= casual.milestones["Algas"]
    assert casual.locked_tries == 0
    assert casual.machines.get(C.CENTRIFUGE, 0) == 0          # o sim não fabrica a centrífuga (é virtual)
    switches = casual.switch_at
    assert set(switches) <= set(sim.PLANTS) and all(t >= casual.centrifuge_at for t in switches.values())
