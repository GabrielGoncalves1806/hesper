"""Nome do baú: campo de texto (edição, limite), limpeza do nome e persistência no save."""

import json

from game import config as C
from game import save
from game.systems import GameState, Machine, clean_chest_name
from game.textedit import TextField
from tests.helpers import build_now


def test_textfield_typing_backspace_and_limit():
    f = TextField("Baú", C.CHEST_NAME_MAX)
    assert f.original == "Baú"
    for _ in range(3):
        f.backspace()
    assert f.text == ""
    f.backspace()                                   # vazio: não quebra
    f.insert("Minério de ferro!")                   # 17 caracteres: corta em 16
    assert f.text == "Minério de ferro" and len(f.text) == 16 and f.full
    f.insert("x")
    assert f.text == "Minério de ferro"
    f.backspace()
    f.insert("\n\t")                                # controle não entra
    assert f.text == "Minério de ferr"


def test_textfield_long_start_is_cut():
    assert TextField("a" * 40, C.CHEST_NAME_MAX).text == "a" * 16


def test_clean_name_rules():
    assert clean_chest_name("  Gelo  ") == "Gelo"
    assert clean_chest_name("") == C.CHEST_DEFAULT_NAME
    assert clean_chest_name("   ") == C.CHEST_DEFAULT_NAME
    assert clean_chest_name("x" * 30) == "x" * C.CHEST_NAME_MAX
    assert clean_chest_name("a\nb") == "ab"


def placed_chest(state: GameState) -> Machine:
    state.player.x, state.player.y = 94.5 * C.TILE, 102 * C.TILE
    assert build_now(state, "chest", (94, 100))
    return state.chests[0]


def test_new_chest_is_called_bau_and_rename_works():
    state = save.new_state()
    chest = placed_chest(state)
    assert chest.name == "Baú"
    assert state.rename_chest(chest, "  Silício  ") == "Silício" and chest.name == "Silício"
    assert state.rename_chest(chest, "") == "Baú"


def test_name_survives_save_and_load(tmp_path):
    state = save.new_state()
    chest = placed_chest(state)
    state.rename_chest(chest, "Ferro do norte")
    path = tmp_path / "slot1.json"
    assert save.write_save(state, path)
    saved = next(m for m in json.loads(path.read_text(encoding="utf-8"))["layers"]["surface"]["machines"] if m["kind"] == "chest")
    assert saved["name"] == "Ferro do norte"
    assert save.load_game(path).chests[0].name == "Ferro do norte"


def test_weird_name_in_save_is_cleaned(tmp_path):
    state = save.new_state()
    placed_chest(state)
    data = save.state_to_dict(state)
    data["layers"]["surface"]["machines"][0]["name"] = "x" * 50
    assert save.state_from_dict(data).chests[0].name == "x" * C.CHEST_NAME_MAX


def test_chest_label_shows_within_e_reach():
    state = save.new_state()
    chest = placed_chest(state)
    ax, ay = chest.anchor
    state.player.x, state.player.y = ax, ay + 10
    assert state.chests_showing_name() == [chest]
    state.player.x, state.player.y = ax + 5 * C.TILE, ay
    assert state.chests_showing_name() == []
