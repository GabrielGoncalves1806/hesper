"""Save/load: ida e volta sem perder nada, arquivo estragado, versão desconhecida e escrita atômica."""

import json
import os
import random

import pytest

from game import config as C
from game import layers
from game import save
from game.objectives import current_index
from game.inventory import Stack
from game.systems import GameState, Machine
from tests.helpers import build_now, give


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
    state._apply_thaw()            # v0.4 M3: no jogo o calor já teria derretido a cratera (o load reaplica)
    state.storm = 0.375                       # tempestade no meio da passagem: tem que voltar igual
    state.smoothed_rate = 51.5
    state.play_time = 1234.5
    state.mined_total.update(iron=37, silicon=12, ice=8)
    state.fabricator_opened = True
    state.read_terminal(1)
    state.lamps_placed = 3
    give(state, iron=17, silicon=9, ice=33)
    # máquinas construídas (uma girada) e uma drill com conteúdo e tempo acumulado (v0.5 M1: pelo construtor)
    state.player.x, state.player.y = 96 * C.TILE, 98 * C.TILE
    assert build_now(state, "o2", (93, 98), rotation=2)
    assert build_now(state, "heater", (99, 98))
    vein = min(world.veins, key=lambda v: abs(v.tx - 96) + abs(v.ty - 96))
    state.player.x, state.player.y = (vein.tx + 1) * C.TILE, (vein.ty + 4) * C.TILE
    assert build_now(state, "drill", (vein.tx, vein.ty), rotation=1)
    drill = state.drills[0]
    drill.stored, drill.timer = 7, 4.75
    state.drill_collected["ice"] = 20
    # baú na base com itens espalhados (slot 0, 5 e o último)
    state.player.x, state.player.y = 96 * C.TILE, 98 * C.TILE
    assert build_now(state, "chest", (94, 100))
    chest = state.chests[0]
    chest.storage.slots[0] = Stack("iron", 50)
    chest.storage.slots[5] = Stack("drone", 2)
    chest.storage.slots[23] = Stack("ice", 3)
    # hotbar com itens em slots escolhidos (a ordem dos slots tem que voltar igual)
    give(state, drone=2)                                  # fabricados e ainda no inventário
    state.inventory.move(state.inventory.slots.index(Stack("drone", 2)), 6)
    state.inventory.slots[12] = Stack("scanner", 1)       # na mochila
    state.crafted.update(o2=2, heater=1, drill=1, melter=2, chest=1, o2_t2=1)
    # Marco 3: caixa da nave saqueada (projeto + um pouco de ferro), tanque equipado, explorado, registro da VÉSPER-7
    crate = state.crates[state.world.wrecks[0].crate]
    state.open_crate(crate)
    iron = next(k for k, s in enumerate(crate.storage.slots) if s and s.item == "iron")
    state.inventory.slots[15] = None
    state.crate_take(crate, iron, 3)
    state.equipment.equip("o2_tank")
    state.equipped_ever.add("o2_tank")
    state.wrecks_visited.add(0)
    state.read_log(3)
    state.read_log(0)
    state.reread_log(0)                                   # aba LOGs: o 0 já foi aberto por lá, o 3 segue "NOVO"
    state.surface.explored.reveal_rect(96, 96, 20, 12)
    state.surface.explored.reveal_circle(150.5, 40.5, 6)
    state.player.x, state.player.y = 102.5 * C.TILE, 112.25 * C.TILE
    state.pop_events()
    return state


def snapshot(state: GameState) -> dict:
    """Tudo que importa num GameState, em tipos fáceis de comparar."""
    p = state.player
    return {
        "seed": state.seed, "layer": state.layer, "layers": sorted(state.layers),
        "tiles": {k: [row[:] for row in layer.world.tiles] for k, layer in state.layers.items()},
        "rock_timer": state.layers["surface"].rocks.timer,
        "player": (p.x, p.y, p.direction),
        "o2": state.o2, "fainted": state.fainted, "faint_time": state.faint_time,
        "was_in_base": state.was_in_base,
        "inventory": state.inventory.to_data(), "crafted": dict(state.crafted),
        "machines": [(m.kind, m.tx, m.ty, m.rotation, m.resource, m.stored, m.timer,
                      m.storage.to_data() if m.storage else None) for m in state.all_machines],
        "indices": dict(state.indices), "stage": state.stage, "storm": state.storm, "ti": state.ti,
        "smoothed_rate": state.smoothed_rate, "play_time": state.play_time,
        "mined_total": dict(state.mined_total), "fabricator_opened": state.fabricator_opened,
        "drills_placed": state.drills_placed, "drill_collected": dict(state.drill_collected),
        "lamps_placed": state.lamps_placed,
        "logs_read": set(state.logs_read), "logs_seen": set(state.logs_seen), "transition_sources": set(state.transition_sources),
        "crates": {k: {t: (c.storage.to_data(), c.opened) for t, c in layer.crates.items()}
                   for k, layer in state.layers.items()},
        "explored": {k: bytes(layer.explored.bits) for k, layer in state.layers.items()},
        "blueprints": set(state.blueprints), "equipment": dict(state.equipment.slots),
        "equipped_ever": set(state.equipped_ever), "wrecks_visited": set(state.wrecks_visited),
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
    assert loaded.stage == C.MIST_STAGE and loaded.drills[0].stored == 7


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
    assert data["version"] == save.SAVE_VERSION == 9
    assert set(data) == {"version", "seed", "layer", "layers", "player", "inventory", "progress", "world"}
    assert set(data["layers"]) == {"surface"} and data["layer"] == "surface"
    assert len(data["layers"]["surface"]["changed_tiles"]) == 6   # 5 minérios + 1 cavado na marra
    # mapa novo, sem mexer em nada: nenhum tile no save
    assert save.state_to_dict(save.new_state())["layers"]["surface"]["changed_tiles"] == []


def test_geo_is_not_saved_and_comes_back_from_the_seed(tmp_path):
    """v7: a geografia (regiões, altura, bacias, formações) sai da seed; o save não guarda nada dela."""
    import numpy as np
    state = rich_state()
    state.indices["heat"] = float(C.THAW_GATE_HEAT[0][-1])      # M4: o calor do rich_state é incidental; abre o 1º portão de vez
    state._apply_thaw()
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    text = path.read_text(encoding="utf-8")
    assert "geo" not in json.loads(text)["layers"]["surface"] and "formation" not in text
    loaded = save.load_game(path)
    a, b = state.surface.geo, loaded.surface.geo
    assert a is not None and loaded.layers["surface"].geo is b
    assert np.array_equal(a.region, b.region) and np.array_equal(a.basin, b.basin)
    assert [(f.kind, f.tx, f.ty) for f in a.formations] == [(f.kind, f.tx, f.ty) for f in b.formations]
    # v0.4 M3.2: o calor (acima) já abriu o 1º gelo-portão; a pegada atual (derivada) volta igual no load
    assert loaded.surface.gate_ice == state.surface.gate_ice and loaded.surface.gate_ice[0] == 3
    assert all(loaded.world.get(*t) == C.FORMATION for f in layers.current_formations(loaded.surface)
               for t in f.tiles)
    state.enter_layer("cave")
    assert state.active.geo is None                                # a caverna não tem geografia


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

    monkeypatch.setattr(save, "SAVE_VERSION", 10)
    monkeypatch.setattr(save, "MIGRATIONS", {**save.MIGRATIONS, 9: old_to_new})
    migrated = save.migrate(data)
    assert migrated["version"] == 10 and migrated["progress"]["play_time"] == 99.0


# ---------------------------------------------------------------- v7 -> v8 (v0.5 M1: máquina não é mais item)
def v7_save(state: GameState) -> dict:
    data = save.state_to_dict(state)
    data["version"] = 7
    return data


def test_v7_machine_items_become_their_recipe():
    state = rich_state()
    data = v7_save(state)
    slots = data["inventory"]["slots"]
    slots[1] = ["o2", 2]                                     # 2 geradores: 20 ferro + 8 silício
    slots[14] = ["lamp", 1]                                  # 1 ferro + 1 silício
    chest = next(m for m in data["layers"]["surface"]["machines"] if m["kind"] == "chest")
    chest["storage"][7] = ["heater", 1]                      # 12 ferro + 8 silício + 3 magmatita
    before = save.state_from_dict(save.migrate(v7_save(state)))
    loaded = save.state_from_dict(save.migrate(data))
    inv = loaded.inventory
    assert not any(s and C.MACHINES.get(s.item) and C.MACHINES[s.item].placeable for s in inv.slots)
    gained = {r: inv.count(r) + loaded.chests[0].storage.count(r)
              - before.inventory.count(r) - before.chests[0].storage.count(r) for r in C.RESOURCES}
    # o slot 1 (ferro) e o 14 já tinham coisa no rich_state; o que somou é exatamente a receita das máquinas
    lost_slot1 = before.inventory.slots[1]
    lost_slot14 = before.inventory.slots[14]
    for lost in (lost_slot1, lost_slot14):
        if lost is not None and lost.item in gained:
            gained[lost.item] += lost.count
    assert gained["iron"] == 20 + 1 + 12 and gained["silicon"] == 8 + 1 + 8 and gained["magmatite"] == 3
    assert loaded.chests[0].storage.count("magmatite") == 3   # a receita do aquecedor ficou no baú dele


def test_v7_overflow_goes_to_the_other_inventories():
    state = save.new_state()
    data = v7_save(state)
    data["inventory"]["slots"] = [["o2_t2", 5]] + [["ice", 50]] * (C.INVENTORY_SLOTS - 1)   # inventário lotado
    chest = {"kind": "chest", "tx": 94, "ty": 100, "rotation": 0, "name": "Baú", "storage": [],
             "sends": [], "receives": [], "batch": 10}
    data["layers"]["surface"]["machines"].append(chest)
    loaded = save.state_from_dict(save.migrate(data))
    cost = C.MACHINES["o2_t2"].cost
    total = {r: loaded.inventory.count(r) + loaded.chests[0].storage.count(r) for r in cost}
    assert total["iron"] == cost["iron"] * 5 and total["silicon"] == cost["silicon"] * 5
    assert total["ice"] == cost["ice"] * 5 + 50 * (C.INVENTORY_SLOTS - 1)
    assert loaded.chests[0].storage.count("iron") > 0      # o que não coube no inventário foi pro baú


def test_v7_with_nowhere_to_put_keeps_what_fits(capsys):
    state = save.new_state()
    data = v7_save(state)
    data["inventory"]["slots"] = [["chest", 1]] + [["ice", 50]] * (C.INVENTORY_SLOTS - 1)
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.inventory.count("iron") == C.MACHINES["chest"].cost["iron"]   # o slot do baú vira o ferro
    assert loaded.inventory.count("chest") == 0


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
@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6])
def test_old_versions_are_reported_as_old_and_kept(tmp_path, version, capsys):
    """v0.4 Marco 2 exige novo jogo: save v1–v6 não migra, é reconhecido como antigo e o arquivo fica."""
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
    assert save.backup_old(path) is None and path.exists()        # v7 não é "antigo"
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


def test_broken_small_rocks_and_respawn_timer_roundtrip(tmp_path):
    state = save.new_state()
    state.rng = random.Random(4)
    world = state.world
    rock = next((x, y) for y in range(world.height) for x in range(world.width) if world.get(x, y) in C.SMALL_ROCKS)
    state._break_tile(rock, world.get(*rock))
    state.surface.rocks.timer = 7.5
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    assert loaded.world.get(*rock) == C.SAND                       # quebrada continua quebrada (até reaparecer outra)
    assert loaded.surface.rocks.timer == 7.5
    assert snapshot(loaded) == snapshot(state)


def test_save_with_old_pickups_field_still_loads(tmp_path):
    """Save com os recursos soltos e sem "rocks" (o formato de antes da troca): carrega, ignora os soltos."""
    data = save.state_to_dict(rich_state())
    surface = data["layers"]["surface"]
    del surface["rocks"]
    surface["pickups"] = {"items": [["iron", 2, 3200.5, 3300.0], ["ice", 1, 100.0, 200.0]], "timer": 3.5}
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert data["version"] == save.SAVE_VERSION == 9
    status, loaded = save.probe(path)
    assert status == "ok" and loaded.surface.rocks.timer == 0.0
    assert not hasattr(loaded.surface, "pickups")


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
    assert loaded.layers["surface"].rocks is not None and loaded.layers["cave"].rocks is None
    assert snapshot(loaded) == snapshot(state)


def test_marco1_save_without_lamps_loads_with_zero(tmp_path):
    data = save.state_to_dict(rich_state())
    del data["progress"]["lamps_placed"]
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.lamps_placed == 0


def test_marco2_save_without_marco3_fields_loads_with_defaults(tmp_path):
    """Save v6 do Marco 1/2: sem caixas, explorado, receitas e equipamento. Carrega com o padrão."""
    data = save.state_to_dict(rich_state())
    for key in ("blueprints", "equipment", "equipped_ever", "wrecks_visited"):
        del data["progress"][key]
    for layer in data["layers"].values():
        layer.pop("crates", None)
        layer.pop("explored", None)
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.blueprints == set() and loaded.equipment.slots == {"o2_tank": None, "scanner": None, "backpack": None}
    assert loaded.surface.explored.count == 0 and not loaded.wrecks_visited
    crate = loaded.crates[loaded.world.wrecks[0].crate]
    assert crate.storage.count("diagram_o2_tank") == 1 and not crate.opened      # caixa cheia, como num jogo novo
    assert loaded.o2 <= loaded.o2_max


def test_crate_save_is_small_and_explored_compressed():
    data = save.state_to_dict(rich_state())
    surface = data["layers"]["surface"]
    assert len(surface["crates"]) == 1                       # só a caixa que mudou vai pro save
    assert isinstance(surface["explored"], str) and len(surface["explored"]) < 1000


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
    assert [a for a, _ in title.options()] == ["old", "worlds", "quit"]
    assert title.selected == 1                                    # começa em "Mundos"
    assert title.activate(0) is None and title.selected == 1      # Continuar apagado: não faz nada
    title.on_key(pygame.K_UP)
    assert title.selected == 2                                    # pula a linha apagada (dá a volta)
    title.on_key(pygame.K_DOWN)
    assert title.selected == 1
    assert title.activate(1) is None and title.screen == "worlds"  # Mundos: abre a lista


def test_title_without_save_shows_worlds_and_quit():
    title, _ = title_screen()
    title.open(None)
    assert [a for a, _ in title.options()] == ["worlds", "quit"] and title.selected == 0


def test_load_converts_bp_items_to_diagram_items():
    """Save com projetos antigos (bp_*) no inventário, hotbar e baú: tudo vira diagram_*; receitas iguais."""
    state = rich_state()
    state.blueprints = {"scanner"}
    data = save.state_to_dict(state)
    data["inventory"]["slots"][0] = ["bp_o2_tank", 2]
    data["inventory"]["slots"][12] = ["bp_scanner", 1]
    chest = next(m for layer in data["layers"].values() for m in layer["machines"] if m["kind"] == "chest")
    chest["storage"][0] = ["bp_lamp_t2", 1]
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.inventory.count("diagram_o2_tank") == 2 and loaded.inventory.count("diagram_scanner") == 1
    assert loaded.inventory.count("bp_o2_tank") == 0
    assert loaded.blueprints == {"scanner"}
    loaded_chest = next(m for m in loaded.machines if m.kind == "chest")
    assert loaded_chest.storage.count("diagram_lamp_t2") == 1
