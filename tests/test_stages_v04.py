"""v0.4 Marco 1 · Trilha A: os 4 estágios (Tempestade, Árido, Névoa, Verde), a intensidade da tempestade
(`state.storm`), a migração do save do v0.3 e o que depende do estágio (arte, objetivo, banner, ambiente)."""

import pytest

from game import audio
from game import config as C
from game import save
from game.objectives import OBJECTIVES
from game.render import art_key, stage_key
from game.systems import Controls, GameState, stage_for_ti, storm_level


def step(state: GameState, seconds: float, dt: float = 0.05) -> None:
    """Roda o jogo `seconds` segundos parado na base."""
    for _ in range(round(seconds / dt)):
        state.update(dt, Controls())


def reach_arid(state: GameState) -> None:
    """Ti exato do Árido e a mesma checagem de estágio que as máquinas fazem a cada frame."""
    state.indices["o2"] = C.STAGES[C.ARID_STAGE - 1].ti
    state._check_stage()


# ---------------------------------------------------------------- A1 · estágios e arte
def test_four_stages_in_order():
    assert [s.key for s in C.STAGES] == ["storm", "arid", "mist", "green"]
    assert [s.ti for s in C.STAGES][:1] == [0] and C.STAGES[2].ti == 10_000 and C.STAGES[3].ti == 100_000
    assert [s.number for s in C.STAGES] == [1, 2, 3, 4]
    assert 0 < C.STAGES[1].ti < C.STAGES[2].ti


def test_stage_constants_match_the_table():
    assert stage_key(C.STORM_STAGE) == "storm" and stage_key(C.ARID_STAGE) == "arid"
    assert stage_key(C.MIST_STAGE) == "mist" and stage_key(C.GREEN_STAGE) == "green"
    assert C.GREEN_STAGE == len(C.STAGES)              # o fim do jogo continua no Verde


def test_art_key_maps_storm_and_arid_to_dead():
    assert [art_key(i) for i in (1, 2, 3, 4)] == ["dead", "dead", "mist", "green"]


def test_every_stage_has_a_palette_a_color_and_a_water_threshold():
    for s in C.STAGES:
        assert art_key(s.number) in C.PALETTES
        assert s.number in C.STAGE_COLOR and s.number in C.WATER_THRESHOLD


def test_no_water_before_the_mist():
    assert C.WATER_THRESHOLD[C.STORM_STAGE] == 0.0 and C.WATER_THRESHOLD[C.ARID_STAGE] == 0.0
    assert 0 < C.WATER_THRESHOLD[C.MIST_STAGE] < C.WATER_THRESHOLD[C.GREEN_STAGE]


def test_cave_keeps_the_mist_art():
    from game.render import CAVE_STAGE
    assert art_key(CAVE_STAGE) == "mist"


def test_tier2_machines_still_unlock_in_the_mist():
    for kind in ("o2_t2", "melter_t2", "heater_t2", "drill"):
        assert stage_for_ti(C.MACHINES[kind].unlock_ti) == C.MIST_STAGE


# ---------------------------------------------------------------- A2 · state.storm
def test_storm_fades_over_20s_after_arid():
    s = GameState()
    assert s.storm == 1.0
    reach_arid(s)
    assert s.stage == C.ARID_STAGE
    step(s, 10.0)
    assert 0.4 < s.storm < 0.6
    step(s, 11.0)
    assert s.storm == 0.0


def test_storm_stays_full_during_the_storm_stage():
    s = GameState()
    s.indices["o2"] = C.STAGES[C.ARID_STAGE - 1].ti - 1
    step(s, 30.0)
    assert s.stage == C.STORM_STAGE and s.storm == 1.0


def test_storm_level_is_zero_in_cave():
    s = GameState()
    s.layer = "cave"
    assert storm_level(s) == 0.0
    s.layer = "surface"
    assert storm_level(s) == 1.0


def test_storm_fade_keeps_going_while_in_the_cave():
    """A passagem pro Árido conta o tempo de jogo, esteja o player onde estiver."""
    s = GameState()
    reach_arid(s)
    s.enter_layer("cave")
    step(s, C.STORM_FADE_S + 1)
    s.enter_layer("surface")
    assert s.storm == 0.0 and storm_level(s) == 0.0


def test_storm_is_zero_from_arid_on_after_a_big_jump():
    s = GameState()
    s.debug_add_ti(100_000)                       # F2 até o Verde de uma vez
    step(s, C.STORM_FADE_S)
    assert s.stage == C.GREEN_STAGE and s.storm == 0.0


# ---------------------------------------------------------------- A3 · save
def test_save_keeps_storm_in_the_middle_of_the_fade(tmp_path):
    s = GameState()
    reach_arid(s)
    step(s, 7.0)
    path = tmp_path / "slot1.json"
    assert save.write_save(s, path)
    loaded = save.load_game(path)
    assert loaded.stage == C.ARID_STAGE
    assert loaded.storm == pytest.approx(s.storm) and 0 < loaded.storm < 1


def v03_save(stage: int) -> dict:
    """Um save v6 como o v0.3 gravava: 3 estágios, sem `stage_scheme` nem `storm`."""
    data = save.state_to_dict(save.new_state())
    data["progress"]["stage"] = stage
    del data["progress"]["stage_scheme"], data["progress"]["storm"]
    return data


@pytest.mark.parametrize("old, new", [(1, 2), (2, 3), (3, 4)])
def test_v6_save_moves_stage_up_and_loads_without_storm(old, new):
    loaded = save.state_from_dict(save.migrate(v03_save(old)))
    assert loaded.stage == new and loaded.storm == 0.0


def test_v6_save_from_disk_goes_through_the_migration(tmp_path):
    import json
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(v03_save(2)), encoding="utf-8")
    status, loaded = save.probe(path)
    assert status == "ok" and loaded.stage == C.MIST_STAGE and loaded.storm == 0.0


def test_new_save_does_not_move_the_stage_again(tmp_path):
    s = GameState()
    path = tmp_path / "slot1.json"
    save.write_save(s, path)
    loaded = save.load_game(path)
    assert loaded.stage == C.STORM_STAGE and loaded.storm == 1.0
    assert save.state_to_dict(loaded)["progress"]["stage_scheme"] == save.STAGE_SCHEME
    assert save.state_to_dict(loaded)["version"] == 6          # o formato só sobe no Marco 2


# ---------------------------------------------------------------- A4 · objetivo, banner e ambiente
def test_clear_the_sky_objective_follows_the_arid():
    sky = next(o for o in OBJECTIVES if o.text == "Limpe o céu (Árido)")
    mist = next(i for i, o in enumerate(OBJECTIVES) if o.text == "Chegue ao estágio Névoa")
    assert OBJECTIVES.index(sky) == mist - 1
    s = GameState()
    assert not sky.done(s)
    reach_arid(s)
    assert sky.done(s)


def test_arid_banner_text():
    arid = C.STAGES[C.ARID_STAGE - 1]
    assert arid.title == "ESTÁGIO 2 · CÉU LIMPO" and arid.subtitle == "A poeira baixou"
    assert C.STAGES[0].title == "ESTÁGIO 1 · TEMPESTADE"


@pytest.mark.parametrize("key, has_storm, want", [
    ("storm", True, "storm"),      # com o amb_storm da Som
    ("storm", False, "dead"),      # sem ele: o ambiente do Morto
    ("arid", True, "dead"),
    ("arid", False, "dead"),
    ("mist", True, "mist"),
    ("green", False, "green"),
])
def test_ambient_for_each_stage(key, has_storm, want):
    assert audio.ambient_for("surface", key, True, has_storm) == want


def test_cave_ambient_wins_over_the_storm():
    assert audio.ambient_for("cave", "storm", True, True) == "cave"
    assert audio.ambient_for("cave", "storm", False, False) == "dead"
