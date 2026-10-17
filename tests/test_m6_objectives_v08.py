"""v0.8 M6 Task 1: os objetivos novos das plantas, os marcos (GameState.milestones) e a dica do coletor."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import objectives as O  # noqa: E402
from game import ruins, save  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.objectives import OBJECTIVES, ObjectiveTracker, current_index  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from tests.test_base import demo_base, free_spot  # noqa: E402
from tests.test_base import game  # noqa: E402,F401  (fixture)
from tests.test_centrifuge_v08 import make_centrifuge  # noqa: E402
from tests.test_cultivator_v08 import plant, tick  # noqa: E402
from tests.test_lab_v08 import new_game  # noqa: E402
from tests.test_microscope_v08 import make_microscope  # noqa: E402

NEW_TEXTS = [
    "Ache o laboratório da Ilves",
    "Derreta o gelo do laboratório",
    "Escaneie o microscópio e o tanque",
    "Pegue a cultura-controle",
    "Construa um cultivador dentro da base",
    "Colha a primeira alga",
    "Chegue ao estágio Algas",
    "Consiga uma amostra no microscópio",
    "Consiga uma planta nova na centrífuga",
    "Chegue ao estágio Musgo",
]
SCAN = "Escaneie o microscópio e o tanque"


def index_of(text):
    return next(i for i, o in enumerate(OBJECTIVES) if o.text == text)


def current_text(state):
    i = current_index(state)
    return None if i is None else OBJECTIVES[i].text


@pytest.fixture
def game_base(game):
    """Base vedada 5×5 com Dispersor soprando e 1 Cultivador dentro (sem muda)."""
    disp, x0, y0 = demo_base(game, w=5, h=5, water=5)
    cult = Machine(C.CULTIVATOR, x0 + 3, y0 + 2)
    game.machines.append(cult)
    assert game.in_breathing_base((cult.tx, cult.ty), game.active)
    return game, cult


# ---------------------------------------------------------------- a ordem
def test_milestones_config_and_mark():
    assert C.MILESTONES == ("lab_found", "control_culture", "cultivator_in_base", "first_harvest", "first_sample",
                            "first_plant")
    g = GameState(rng=random.Random(1))
    assert g.milestones == set()
    g.mark("first_sample")
    g.mark("first_sample")
    assert g.milestones == {"first_sample"}
    with pytest.raises(AssertionError):
        g.mark("nao_existe")


def test_new_objectives_come_right_after_the_tier2_machine_and_green_is_last():
    t = [o.text for o in OBJECTIVES]
    start = t.index("Construa uma máquina nv.2") + 1
    assert t[start:] == NEW_TEXTS + ["Deixe o planeta verde"] and len(t[start:]) == 11


def test_new_objective_texts_wrap_in_the_card_at_every_size():
    import pygame
    from game.objectives import ObjectiveLine
    from game.ui import UI
    pygame.font.init()
    ui = UI()
    for size in [(480, 270), (640, 360), (960, 540)]:
        ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
        for text in NEW_TEXTS:
            rows = ui.objective_lines([ObjectiveLine(text, "current")])
            assert len(rows) <= 3, (size, text)
            assert all(ui.body.size(r)[0] <= ui.objective_w - 12 for _, r in rows), (size, text)


# ---------------------------------------------------------------- os ganchos
def test_lab_found_when_the_player_gets_near_the_door():
    g = new_game(7)
    g.player.x, g.player.y = 50.0, 50.0
    g._update_explore(0.1)
    assert "lab_found" not in g.milestones
    dx, dy = ruins.lab_door_px(g.world)
    g.explore_timer = 0.0
    g.player.x, g.player.y = dx, dy + (C.WRECK_VISIT_DIST - 1) * C.TILE
    g._update_explore(0.1)
    assert "lab_found" in g.milestones


def test_world_without_lab_never_marks_lab_found(monkeypatch):
    g = GameState(rng=random.Random(1))
    monkeypatch.setattr(ruins, "lab_door_px", lambda world: None)
    g._update_explore(0.1)
    assert "lab_found" not in g.milestones


def test_control_culture_only_from_the_lab_crate():
    g = new_game(7)
    lab_tile = ruins.lab_of(g.world).crate
    lab_crate = g.active.crates[lab_tile]
    other = next(c for t, c in g.active.crates.items() if t != lab_tile)
    other.storage.slots[0] = Stack("algae", 1)           # alga numa caixa que não é a do lab: não conta
    g.crate_take(other)
    assert "control_culture" not in g.milestones
    g.crate_take(lab_crate)
    assert "control_culture" in g.milestones


def test_cultivator_in_base_with_or_without_seed(game_base):
    g, cult = game_base
    assert "cultivator_in_base" not in g.milestones
    tick(g, 0.1)
    assert "cultivator_in_base" in g.milestones and cult.crop is None


def test_cultivator_outside_a_base_does_not_mark(game):
    x0, y0 = free_spot(game, 3, 3)
    game.machines.append(Machine(C.CULTIVATOR, x0, y0))
    tick(game, 0.5)
    assert "cultivator_in_base" not in game.milestones


def test_first_harvest_marks_and_milestones_survive_losing_the_base(game_base):
    g, cult = game_base
    plant(cult, water=5)
    tick(g, C.CROPS["algae"].cycle - 5)
    assert "first_harvest" not in g.milestones
    tick(g, 10)
    assert "first_harvest" in g.milestones
    g.machines[:] = [m for m in g.machines if not m.is_dispenser]       # tira o Dispersor: a base deixa de respirar
    assert not g.in_breathing_base((cult.tx, cult.ty), g.active)
    assert OBJECTIVES[index_of("Construa um cultivador dentro da base")].done(g)
    assert OBJECTIVES[index_of("Colha a primeira alga")].done(g)


def test_first_sample_marks(game, monkeypatch):
    make_microscope(game)
    monkeypatch.setattr(game, "microscope_roll", lambda: None)
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert "first_sample" not in game.milestones              # análise vazia não conta
    monkeypatch.setattr(game, "microscope_roll", lambda: "sample_basic")
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert "first_sample" in game.milestones


def test_first_plant_marks_but_failure_does_not(game, monkeypatch):
    make_centrifuge(game, algae=2, sample=("sample_mutant", 2))
    monkeypatch.setattr(game.rng, "random", lambda: 0.99)
    tick(game, C.CENTRIFUGE_TIME + 0.1)
    assert "first_plant" not in game.milestones
    monkeypatch.setattr(game.rng, "random", lambda: 0.0)
    tick(game, C.CENTRIFUGE_TIME + 0.1)
    assert "first_plant" in game.milestones


# ---------------------------------------------------------------- quem já passou não trava
def test_state_already_green_with_old_save_is_not_stuck():
    g = GameState(rng=random.Random(1))
    g.stage = C.GREEN_STAGE
    g.indices["biomass"] = 15_000.0
    g.debug_add_ti(100_000)
    g.blueprints |= {"cultivator", "microscope", "o2_tank"}
    g.equipped_ever.add("o2_tank")
    g.crafted.update({"o2_t2": 1, C.CULTIVATOR: 1, C.FIBER: 1, C.HYDROGEL: 1})
    assert all(o.done(g) for o in OBJECTIVES[index_of(NEW_TEXTS[0]):])


def test_algae_stage_without_the_microscope_diagram_points_to_scan():
    g = GameState(rng=random.Random(1))
    for i in range(index_of(NEW_TEXTS[0])):                # tudo antes dos novos já cumprido
        pass
    g.stage = C.ALGAE_STAGE
    g.blueprints.add("cultivator")
    first_new, scan = index_of(NEW_TEXTS[0]), index_of(SCAN)
    assert all(OBJECTIVES[i].done(g) for i in range(first_new, scan))
    assert not OBJECTIVES[scan].done(g)


# ---------------------------------------------------------------- a dica do coletor
def test_collector_hint_comes_once_when_harvest_becomes_current():
    assert O.COLLECTOR_HINT == "Pouco gelo? O coletor de água puxa a umidade do ar."
    i = index_of("Colha a primeira alga")
    assert OBJECTIVES[i].hint == O.COLLECTOR_HINT
    g = GameState(rng=random.Random(1))
    tracker = ObjectiveTracker(g)
    tracker.shown = i
    assert tracker.take_hint() == O.COLLECTOR_HINT
    assert tracker.take_hint() is None


def test_scan_hint_explains_the_constructor_when_scan_becomes_current():
    i = index_of(SCAN)
    assert OBJECTIVES[i].hint == O.SCAN_HINT
    assert "construtor" in O.SCAN_HINT and "segure o clique" in O.SCAN_HINT
    tracker = ObjectiveTracker(GameState(rng=random.Random(1)))
    tracker.shown = i
    assert tracker.take_hint() == O.SCAN_HINT
    assert tracker.take_hint() is None


# ---------------------------------------------------------------- save
def test_milestones_roundtrip_unknown_ignored_and_missing_is_empty():
    g = GameState(rng=random.Random(1))
    for k in ("lab_found", "first_harvest", "first_plant"):
        g.mark(k)
    data = save.state_to_dict(g)
    assert data["progress"]["milestones"] == ["first_harvest", "first_plant", "lab_found"]
    assert save.SAVE_VERSION == 17
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.milestones == {"lab_found", "first_harvest", "first_plant"}
    data["progress"]["milestones"] = ["lab_found", "lixo"]
    assert save.state_from_dict(save.migrate(data)).milestones == {"lab_found"}
    del data["progress"]["milestones"]
    assert save.state_from_dict(save.migrate(data)).milestones == set()
