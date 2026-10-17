"""v0.8 M4: a trava de receita por estágio (MachineType.unlock_stage)."""

import dataclasses

from game import config as C
from game import ui
from game.systems import GameState


def test_stage_lock_blocks_until_the_stage(monkeypatch):
    monkeypatch.setitem(C.MACHINES, "o2", dataclasses.replace(C.MACHINES["o2"], unlock_stage=C.ALGAE_STAGE))
    state = GameState()
    state.inventory.add("iron", 50)
    state.inventory.add("silicon", 50)
    state.stage = C.MIST_STAGE
    assert state.recipe_status("o2") == "locked"
    state.stage = C.ALGAE_STAGE
    assert state.recipe_status("o2") != "locked"


def test_default_machines_have_no_stage_lock():
    centrifuge = getattr(C, "CENTRIFUGE", None)
    assert all(m.unlock_stage == 0 for k, m in C.MACHINES.items() if k != centrifuge)


def test_unlock_text_names_the_stage_or_the_ti(monkeypatch):
    monkeypatch.setitem(C.MACHINES, "o2", dataclasses.replace(C.MACHINES["o2"], unlock_stage=C.ALGAE_STAGE))
    assert ui.unlock_text("o2") == "LIBERA NO ESTÁGIO ALGAS"
    assert ui.unlock_text("heater") == "LIBERA EM TI 500"
