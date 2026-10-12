"""Save/load: ida e volta sem perder nada, arquivo estragado, versão desconhecida e escrita atômica."""

import json
import os
import random

import pytest

from game import config as C
from game import save
from game.objectives import current_index
from game.inventory import Stack
from game.systems import GameState, Machine
from tests.helpers import give


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
    state.player.x, state.player.y = 102.5 * C.TILE, 112.25 * C.TILE
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
    state.lamps_placed = 3
    give(state, iron=17, silicon=9, ice=33)
    # máquinas colocadas (uma girada) e uma drill com conteúdo e tempo acumulado
    give(state, o2=1, heater=1, drill=1, chest=1)
    state.player.x, state.player.y = 96 * C.TILE, 98 * C.TILE
    assert state.place("o2", (93, 98), rotation=2)
    assert state.place("heater", (99, 98))
    vein = min(world.veins, key=lambda v: abs(v.tx - 96) + abs(v.ty - 96))
    state.player.x, state.player.y = (vein.tx + 1) * C.TILE, (vein.ty + 4) * C.TILE
    assert state.place("drill", (vein.tx, vein.ty), rotation=1)
    drill = state.drills[0]
    drill.stored, drill.timer = 7, 4.75
    state.drill_collected["ice"] = 20
    # baú na base com itens espalhados (slot 0, 5 e o último)
    state.player.x, state.player.y = 96 * C.TILE, 98 * C.TILE
    assert state.place("chest", (94, 100))
    chest = state.chests[0]
    chest.storage.slots[0] = Stack("iron", 50)
    chest.storage.slots[5] = Stack("solar", 2)
    chest.storage.slots[23] = Stack("ice", 3)
    # hotbar com máquinas em slots escolhidos (a ordem dos slots tem que voltar igual)
    give(state, melter=2)                                 # fabricadas e ainda no inventário
    state.inventory.move(state.inventory.slots.index(Stack("melter", 2)), 6)
    state.inventory.slots[12] = Stack("o2_t2", 1)         # na mochila
    state.crafted.update(o2=2, heater=1, drill=1, melter=2, chest=1, o2_t2=1)
    state.player.x, state.player.y = 102.5 * C.TILE, 112.25 * C.TILE
    state.pop_events()
    return state


def snapshot(state: GameState) -> dict:
    """Tudo que importa num GameState, em tipos fáceis de comparar."""
    p = state.player
    return {
        "seed": state.seed, "layer": state.layer, "layers": sorted(state.layers),
        "tiles": {k: [row[:] for row in layer.world.tiles] for k, layer in state.layers.items()},
        "pickups": [(p.resource, p.amount, p.x, p.y) for p in state.layers["surface"].pickups.items],
        "pickup_timer": state.layers["surface"].pickups.timer,
        "player": (p.x, p.y, p.direction),
        "o2": state.o2, "fainted": state.fainted, "faint_time": state.faint_time,
        "was_in_base": state.was_in_base,
        "inventory": state.inventory.to_data(), "crafted": dict(state.crafted),
        "machines": [(m.kind, m.tx, m.ty, m.rotation, m.resource, m.stored, m.timer,
                      m.storage.to_data() if m.storage else None) for m in state.all_machines],
        "indices": dict(state.indices), "stage": state.stage, "ti": state.ti,
        "smoothed_rate": state.smoothed_rate, "play_time": state.play_time,
        "mined_total": dict(state.mined_total), "fabricator_opened": state.fabricator_opened,
        "drills_placed": state.drills_placed, "drill_collected": dict(state.drill_collected),
        "lamps_placed": state.lamps_placed,
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
    assert data["version"] == save.SAVE_VERSION == 6
    assert set(data) == {"version", "seed", "layer", "layers", "player", "inventory", "progress"}
    assert set(data["layers"]) == {"surface"} and data["layer"] == "surface"
    assert len(data["layers"]["surface"]["changed_tiles"]) == 6   # 5 minérios + 1 cavado na marra
    # mapa novo, sem mexer em nada: nenhum tile no save
    assert save.state_to_dict(save.new_state())["layers"]["surface"]["changed_tiles"] == []


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
    data["progress"]["play_time"] = 1.0

    def old_to_new(d):
        d["progress"]["play_time"] = 99.0
        return d

    monkeypatch.setattr(save, "SAVE_VERSION", 7)
    monkeypatch.setattr(save, "MIGRATIONS", {6: old_to_new})
    migrated = save.migrate(data)
    assert migrated["version"] == 7 and migrated["progress"]["play_time"] == 99.0


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


# ---------------------------------------------------------------- v0.3: saves antigos e camadas
@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_old_versions_are_reported_as_old_and_kept(tmp_path, version, capsys):
    """v0.3 exige novo jogo: save v1–v5 não migra, é reconhecido como antigo e o arquivo fica."""
    path = tmp_path / "slot1.json"
    text = json.dumps({"version": version, "seed": 7, "world": {"changed_tiles": []}})
    path.write_text(text, encoding="utf-8")
    assert save.probe(path) == ("old", None)
    assert save.load_game(path) is None and path.read_text(encoding="utf-8") == text
    assert "versão" in capsys.readouterr().out
    backup = save.backup_old(path)
    assert backup == tmp_path / f"slot1.v{version}.json"
    assert backup.read_text(encoding="utf-8") == text and not path.exists()


def test_backup_old_never_overwrites_and_ignores_new_saves(tmp_path):
    path = tmp_path / "slot1.json"
    assert save.backup_old(path) is None                           # sem arquivo
    save.write_save(rich_state(), path)
    assert save.backup_old(path) is None and path.exists()        # v6 não é "antigo"
    (tmp_path / "slot1.v5.json").write_text("antes", encoding="utf-8")
    path.write_text(json.dumps({"version": 5}), encoding="utf-8")
    assert save.backup_old(path).name == "slot1.v5-2.json"
    assert (tmp_path / "slot1.v5.json").read_text(encoding="utf-8") == "antes"


def test_probe_statuses(tmp_path):
    path = tmp_path / "slot1.json"
    assert save.probe(path) == ("none", None)
    path.write_text("{quebrado", encoding="utf-8")
    assert save.probe(path) == ("broken", None)
    save.write_save(rich_state(), path)
    status, state = save.probe(path)
    assert status == "ok" and state.ti > 10_000


def test_broken_small_rocks_and_pickups_roundtrip(tmp_path):
    state = save.new_state()
    state.rng = random.Random(4)
    world = state.world
    rock = next((x, y) for y in range(world.height) for x in range(world.width) if world.get(x, y) in C.SMALL_ROCKS)
    state._break_tile(rock, world.get(*rock))
    taken = state.pickups.items[0]
    state.take_pickup(taken)
    state.pickups.timer = 7.5
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    assert loaded.world.get(*rock) == C.SAND                       # a rocha quebrada não volta
    assert len(loaded.pickups.items) == C.PICKUP_START - 1
    assert snapshot(loaded) == snapshot(state)


def test_cave_layer_roundtrip(tmp_path):
    state = rich_state()
    state.enter_layer("cave")
    tile = next((x, y) for y in range(state.world.height) for x in range(state.world.width)
                if state.world.get(x, y) == C.ICE)
    state._break_tile(tile, C.ICE)
    cave_chest = Machine("chest", 60, 70, name="Fundo")
    cave_chest.storage.add("iron", 9)
    state.machines.append(cave_chest)
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    assert loaded.layer == "cave" and loaded.world.get(*tile) == C.FLOOR
    assert loaded.chests[0].name == "Fundo" and loaded.chests[0].storage.count("iron") == 9
    assert loaded.layers["surface"].pickups is not None and loaded.layers["cave"].pickups is None
    assert snapshot(loaded) == snapshot(state)


def test_marco1_save_without_lamps_loads_with_zero(tmp_path):
    data = save.state_to_dict(rich_state())
    del data["progress"]["lamps_placed"]
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.lamps_placed == 0


def test_cave_with_lamps_and_drill_roundtrip(tmp_path):
    """Caverna com luminárias e uma drill: tudo volta, e a rampa (tile CRATER) não vira "tile mudado"."""
    state = rich_state()
    state.enter_layer("cave")
    state.machines += [Machine("lamp", 60, 70), Machine("lamp", 66, 58)]
    vein = state.world.veins[0]
    state.machines.append(Machine("drill", vein.tx, vein.ty, resource=vein.resource, stored_init=5))
    data = save.state_to_dict(state)
    assert data["layers"]["cave"]["changed_tiles"] == []
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    assert [m.kind for m in loaded.machines] == ["lamp", "lamp", "drill"] and loaded.drills[0].stored == 5
    assert snapshot(loaded) == snapshot(state)


def test_unknown_layer_is_no_save(tmp_path):
    data = save.state_to_dict(rich_state())
    data["layers"]["lua"] = data["layers"]["surface"]
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert save.load_game(path) is None


def test_unknown_items_become_empty_slots():
    data = save.state_to_dict(rich_state())
    data["inventory"]["slots"][0] = ["unobtanium", 3]
    state = save.state_from_dict(data)
    assert state.inventory.slots[0] is None and len(state.inventory) == C.INVENTORY_SLOTS


# ---------------------------------------------------------------- tela de título com save antigo
def title_screen():
    import pygame
    pygame.font.init()
    from game.title import TitleScreen
    played = []
    return TitleScreen(ui=None, renderer=None, play=played.append), played


def test_title_with_old_save_shows_disabled_continue():
    import pygame
    title, played = title_screen()
    title.open(None, old=True)
    assert [a for a, _ in title.options()] == ["old", "new", "quit"]
    assert title.selected == 1                                    # começa em "Novo jogo"
    assert title.activate(0) is None and title.selected == 1      # Continuar apagado: não faz nada
    title.on_key(pygame.K_UP)
    assert title.selected == 2                                    # pula a linha apagada (dá a volta)
    title.on_key(pygame.K_DOWN)
    assert title.selected == 1
    assert title.activate(1) == "new"                             # sem confirmação: o antigo vira backup


def test_title_without_old_save_is_unchanged():
    title, _ = title_screen()
    title.open(None)
    assert [a for a, _ in title.options()] == ["new", "quit"] and title.selected == 0
