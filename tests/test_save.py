"""Save/load: ida e volta sem perder nada, arquivo estragado, versão desconhecida e escrita atômica."""

import json
import os
import random

import pytest

from game import config as C
from game import save
from game.objectives import current_index
from game.systems import GameState


def rich_state() -> GameState:
    """Um jogo "no meio do caminho": tiles minerados, máquinas, drill com conteúdo, Ti alto..."""
    state = save.new_state()
    state.rng = random.Random(1)
    world = state.world
    # minera umas paredes de verdade (pela regra) e cava um pedaço "na marra"
    ores = [(x, y) for y in range(world.height) for x in range(world.width) if world.get(x, y) == C.IRON][:5]
    for tile in ores:
        state._break_tile(tile, C.IRON)
    world.set(10, 10, C.FLOOR)
    # player longe da base, virado pra esquerda, com O₂ pela metade
    state.player.x, state.player.y = 70.5 * C.TILE, 80.25 * C.TILE
    state.player.direction = "left"
    state.o2 = 42.125
    state.was_in_base = False
    # progresso: Ti alto (Névoa), objetivos avançados, terminal lido
    state.debug_add_ti(12_345)
    state.indices["heat"] += 0.375
    state.smoothed_rate = 51.5
    state.play_time = 1234.5
    state.mined_total.update(iron=37, silicon=12, ice=8)
    state.fabricator_opened = True
    state.read_terminal(1)
    state.inventory.update(iron=17, silicon=9, ice=33)
    # máquinas colocadas (uma girada) e uma drill com conteúdo e tempo acumulado
    state.machines_owned.update(o2=1, heater=1, drill=1)
    state.player.x, state.player.y = 64 * C.TILE, 66 * C.TILE
    assert state.place("o2", (61, 66), rotation=2)
    assert state.place("heater", (67, 66))
    vein = min(world.veins, key=lambda v: abs(v.tx - 64) + abs(v.ty - 64))
    state.player.x, state.player.y = (vein.tx + 1) * C.TILE, (vein.ty + 4) * C.TILE
    assert state.place("drill", (vein.tx, vein.ty), rotation=1)
    drill = state.drills[0]
    drill.stored, drill.timer = 7, 4.75
    state.drill_collected["ice"] = 20
    state.machines_owned["melter"] = 2                    # fabricadas e ainda no estoque
    state.player.x, state.player.y = 70.5 * C.TILE, 80.25 * C.TILE
    state.pop_events()
    return state


def snapshot(state: GameState) -> dict:
    """Tudo que importa num GameState, em tipos fáceis de comparar."""
    p = state.player
    return {
        "seed": state.world.seed,
        "tiles": [row[:] for row in state.world.tiles],
        "player": (p.x, p.y, p.direction),
        "o2": state.o2, "fainted": state.fainted, "faint_time": state.faint_time,
        "was_in_base": state.was_in_base,
        "inventory": dict(state.inventory), "machines_owned": dict(state.machines_owned),
        "machines": [(m.kind, m.tx, m.ty, m.rotation, m.resource, m.stored, m.timer) for m in state.machines],
        "indices": dict(state.indices), "stage": state.stage, "ti": state.ti,
        "smoothed_rate": state.smoothed_rate, "play_time": state.play_time,
        "mined_total": dict(state.mined_total), "fabricator_opened": state.fabricator_opened,
        "drills_placed": state.drills_placed, "drill_collected": dict(state.drill_collected),
        "logs_read": set(state.logs_read), "transition_sources": set(state.transition_sources),
    }


def test_roundtrip_keeps_everything(tmp_path):
    state = rich_state()
    path = tmp_path / "slot1.json"
    assert save.write_save(state, path)
    loaded = save.load_game(path)
    assert loaded is not None
    before, after = snapshot(state), snapshot(loaded)
    for key in before:                       # campo a campo, pra o erro dizer qual se perdeu
        assert after[key] == before[key], key
    # o que os objetivos enxergam também bate
    assert current_index(loaded) == current_index(state)
    assert loaded.stage == 2 and loaded.drills[0].stored == 7


def test_loaded_game_keeps_running(tmp_path):
    """Depois de carregar, a drill continua do tempo acumulado e as máquinas somam Ti."""
    state = rich_state()
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    ti = loaded.ti
    loaded._update_machines(C.DRILL_INTERVAL - 4.75)     # completa a unidade que estava no meio
    assert loaded.drills[0].stored == 8
    assert loaded.ti > ti


def test_save_only_stores_what_changed(tmp_path):
    state = rich_state()
    data = save.state_to_dict(state)
    assert data["version"] == save.SAVE_VERSION
    assert set(data) == {"version", "seed", "world", "player", "inventory", "machines", "progress"}
    assert len(data["world"]["changed_tiles"]) == 6       # 5 minérios + 1 cavado na marra
    # mapa novo, sem mexer em nada: nenhum tile no save
    assert save.state_to_dict(save.new_state())["world"]["changed_tiles"] == []


def test_fainted_state_roundtrip(tmp_path):
    state = rich_state()
    state._faint()
    state.faint_time = 0.8
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    assert loaded.fainted and loaded.faint_time == 0.8


def test_missing_file_is_no_save(tmp_path):
    assert save.load_game(tmp_path / "nao_existe.json") is None
    assert not save.has_save(tmp_path / "nao_existe.json")


@pytest.mark.parametrize("content", [
    "{isso não é json",
    "[1, 2, 3]",
    "",
    '{"version": 1, "seed": 7}',                                   # faltam as seções
    '{"version": 1, "seed": 7, "world": {"changed_tiles": "x"}}',  # tipo errado
])
def test_corrupted_file_is_no_save(tmp_path, content, capsys):
    path = tmp_path / "slot1.json"
    path.write_text(content, encoding="utf-8")
    assert save.load_game(path) is None
    assert "[save]" in capsys.readouterr().out                    # avisou no terminal


def test_truncated_save_is_no_save(tmp_path):
    path = tmp_path / "slot1.json"
    save.write_save(rich_state(), path)
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: len(text) // 2], encoding="utf-8")     # arquivo cortado no meio
    assert save.load_game(path) is None


@pytest.mark.parametrize("version", [save.SAVE_VERSION + 1, 0, -3, "1", None, True])
def test_unknown_version_is_no_save(tmp_path, version, capsys):
    data = save.state_to_dict(rich_state())
    data["version"] = version
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert save.load_game(path) is None
    assert "vers" in capsys.readouterr().out


def test_missing_version_is_no_save(tmp_path):
    data = save.state_to_dict(rich_state())
    del data["version"]
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert save.load_game(path) is None


def test_migration_hook_runs(tmp_path, monkeypatch):
    """Uma migração registrada leva um save antigo até a versão atual."""
    data = save.state_to_dict(rich_state())
    data["version"] = 1
    data["progress"]["play_time"] = 1.0

    def old_to_new(d):
        d["progress"]["play_time"] = 99.0
        return d

    monkeypatch.setattr(save, "SAVE_VERSION", 2)
    monkeypatch.setattr(save, "MIGRATIONS", {1: old_to_new})
    migrated = save.migrate(data)
    assert migrated["version"] == 2 and migrated["progress"]["play_time"] == 99.0


def test_atomic_write_keeps_old_save_on_crash(tmp_path, monkeypatch):
    """Se a troca do arquivo falhar no meio, o save antigo fica intacto e não sobra temporário."""
    path = tmp_path / "slot1.json"
    old = rich_state()
    assert save.write_save(old, path)
    old_text = path.read_text(encoding="utf-8")

    def crash(src, dst):
        raise OSError("disco cheio (simulado)")

    monkeypatch.setattr(os, "replace", crash)
    newer = rich_state()
    newer.play_time = 9999.0
    assert not save.write_save(newer, path)
    assert path.read_text(encoding="utf-8") == old_text
    assert sorted(p.name for p in tmp_path.iterdir()) == ["slot1.json"]
    assert save.load_game(path).play_time == old.play_time


def test_write_creates_folder_and_overwrites(tmp_path):
    path = tmp_path / "saves" / "slot1.json"
    state = rich_state()
    assert save.write_save(state, path)
    state.play_time = 2000.0
    assert save.write_save(state, path)
    assert save.load_game(path).play_time == 2000.0
    assert sorted(p.name for p in path.parent.iterdir()) == ["slot1.json"]
