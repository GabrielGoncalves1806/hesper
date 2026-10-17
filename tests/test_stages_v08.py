"""v0.8 M1: 6 estágios (Tempestade, Árido, Úmido, Algas, Musgo, Verde), a trava dupla Ti + biomassa e o 4º índice."""

import pytest

from game import config as C
from game.render import art_key, stage_key, water_key
from game.systems import GameState, stage_for_ti, stage_progress
from game.transition import StageMap


def test_six_stages_in_order():
    assert [s.key for s in C.STAGES] == ["storm", "arid", "mist", "algae", "moss", "green"]
    assert [s.number for s in C.STAGES] == [1, 2, 3, 4, 5, 6]
    assert [s.name for s in C.STAGES] == ["TEMPESTADE", "ÁRIDO", "ÚMIDO", "ALGAS", "MUSGO", "VERDE"]
    assert [s.ti for s in C.STAGES] == [0, 7_000, 10_000, 25_000, 50_000, 100_000]
    assert [s.biomass for s in C.STAGES] == [0, 0, 0, 500, 3_000, 15_000]


def test_stage_constants():
    assert (C.STORM_STAGE, C.ARID_STAGE, C.MIST_STAGE) == (1, 2, 3)
    assert (C.ALGAE_STAGE, C.MOSS_STAGE, C.GREEN_STAGE) == (4, 5, 6)


def test_algae_and_moss_look_like_the_mist_but_have_their_own_water():
    assert stage_key(C.ALGAE_STAGE) == stage_key(C.MOSS_STAGE) == "mist"
    assert art_key(C.ALGAE_STAGE) == art_key(C.MOSS_STAGE) == "mist"
    assert water_key(C.ALGAE_STAGE) == water_key(C.MOSS_STAGE) == "algae"
    assert water_key(C.MIST_STAGE) == "mist" and water_key(C.GREEN_STAGE) == "green"
    assert water_key(C.STORM_STAGE) == "dead"


def test_every_stage_has_color_threshold_and_palettes():
    for s in C.STAGES:
        assert s.number in C.STAGE_COLOR and s.number in C.WATER_THRESHOLD
        assert art_key(s.number) in C.PALETTES and water_key(s.number) in C.PALETTES
    assert C.WATER_THRESHOLD[C.ALGAE_STAGE] == C.WATER_THRESHOLD[C.MIST_STAGE]
    assert C.WATER_THRESHOLD[C.MOSS_STAGE] == C.WATER_THRESHOLD[C.MIST_STAGE]


def test_algae_palette_only_changes_the_water():
    mist, algae = C.PALETTES["mist"], C.PALETTES["algae"]
    assert algae["water"] == "#3f8a72" and algae["water_d"] == "#2f6e5a"
    assert {k: v for k, v in algae.items() if k not in ("water", "water_d")} == \
        {k: v for k, v in mist.items() if k not in ("water", "water_d")}


def test_biomass_index_labels():
    assert C.INDEX_LABEL["biomass"] == "BIOMASSA" and C.INDEX_UNIT["biomass"] == "kg"
    assert C.INDEX_COLOR["biomass"] == C.C_BIOMASS == "#8fd46a"


def test_hills_ramp_keys_follow_the_look():
    from game import hills
    assert hills.STAGE_KEYS == ("storm", "arid", "mist", "mist", "mist", "green")


# ---- Task 2: trava dupla, índice no estado, transição ----
def test_stage_needs_ti_and_biomass():
    assert stage_for_ti(25_000) == C.MIST_STAGE                     # Ti sem biomassa: para no Úmido
    assert stage_for_ti(25_000, 499) == C.MIST_STAGE
    assert stage_for_ti(25_000, 500) == C.ALGAE_STAGE
    assert stage_for_ti(24_999, 10_000) == C.MIST_STAGE             # biomassa sem Ti também não sobe
    assert stage_for_ti(100_000, 15_000) == C.GREEN_STAGE
    assert stage_for_ti(100_000, 3_000) == C.MOSS_STAGE             # não pula: para no primeiro que falta


def test_progress_reports_the_bottleneck():
    nxt, frac, ti_left, bio_left = stage_progress(25_000, 250)      # Ti cheio, biomassa na metade
    assert nxt.key == "algae" and frac == pytest.approx(0.5)
    assert ti_left == 0 and bio_left == 250
    nxt, frac, ti_left, bio_left = stage_progress(17_500, 500)      # biomassa cheia, Ti na metade (10k -> 25k)
    assert nxt.key == "algae" and frac == pytest.approx(0.5) and ti_left == 7_500 and bio_left == 0


def test_progress_without_biomass_requirement_is_the_old_one():
    nxt, frac, ti_left, bio_left = stage_progress(C.STAGES[1].ti / 2)
    assert nxt.key == "arid" and frac == pytest.approx(0.5) and bio_left == 0


def test_progress_at_the_end():
    assert stage_progress(100_000, 15_000) == (None, 1.0, 0.0, 0.0)


def test_state_has_biomass_and_it_counts_in_ti():
    s = GameState()
    assert s.indices["biomass"] == 0.0
    s.indices["biomass"] = 123.0
    assert s.ti == pytest.approx(123.0)


def test_check_stage_uses_biomass():
    s = GameState()
    s.indices["o2"] = 30_000.0
    s._check_stage()
    assert s.stage == C.MIST_STAGE
    s.debug_add_biomass()                                           # +500
    assert s.indices["biomass"] == C.DEBUG_BIOMASS_BONUS
    assert s.stage == C.ALGAE_STAGE


def test_stage_map_waits_for_biomass():
    m = StageMap()
    m.update(24_999, [(0, 0)])                                      # Ti quase no limiar, sem biomassa
    assert m.stage == C.MIST_STAGE
    m.update(25_000, [(0, 0)], biomass=500)
    assert m.stage == C.ALGAE_STAGE


# ---- Task 4: HUD e objetivos ----
def test_next_stage_line_shows_the_bottleneck():
    from game.ui import next_stage_line
    algae = C.STAGES[C.ALGAE_STAGE - 1]
    assert next_stage_line(algae, 7_500, 0, "~2 min") == "faltam 7.500 · ~2 min"
    assert next_stage_line(algae, 0, 380, "~2 min") == "falta biomassa 380"
    assert next_stage_line(algae, 7_500, 380, "~2 min") == "faltam 7.500 · biomassa 380"


def test_mist_objective_says_umido():
    from game.objectives import OBJECTIVES
    texts = [o.text for o in OBJECTIVES]
    assert "Chegue ao estágio Úmido" in texts and "Chegue ao estágio Névoa" not in texts


# ---- Task 5: musgo ----
def test_moss_overlay_starts_in_the_moss_stage():
    from game.ground import decor_layers
    moss_on = {"pebble_a"}
    assert decor_layers("pebble_a", C.ALGAE_STAGE, moss_on) == ["pebble_a"]
    assert decor_layers("pebble_a", C.MOSS_STAGE, moss_on) == ["pebble_a", "pebble_a_moss"]
    assert decor_layers("pebble_a", C.GREEN_STAGE, moss_on) == ["pebble_a", "pebble_a_moss"]
