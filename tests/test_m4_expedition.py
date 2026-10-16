"""v0.5 Marco 4: broca de mão, peças de loot e contêiner que abre (bíblia §13 "Marco 4")."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import layers, save, wrecks
from game.inventory import Inventory, Stack, max_stack
from game.systems import Controls, GameState, Machine

T = C.TILE
SEEDS = tuple(range(1, 21))
DT = 1 / 30


def game(seed: int = C.WORLD_SEED) -> GameState:
    return GameState(seed, rng=random.Random(1))


def wall_next_to_player(g: GameState) -> tuple[int, int]:
    px, py = g.player.tile
    g.world.set(px + 1, py, C.IRON)
    return px + 1, py


def run(g: GameState, seconds: float, controls: Controls) -> None:
    for _ in range(round(seconds / DT)):
        g.update(DT, controls)


# ---------------------------------------------------------------- broca de mão
def test_new_game_starts_with_one_hand_drill_in_the_first_hotbar_slot():
    g = game()
    assert g.inventory.slots[0] == Stack("hand_drill", 1)
    assert max_stack("hand_drill") == 1
    g.inventory.add("hand_drill", 1)                        # não empilha: a 2ª vai pra outro slot
    assert g.inventory.slots[0].count == 1 and g.inventory.slots[1] == Stack("hand_drill", 1)
    assert C.MACHINES["hand_drill"].name == "Broca de mão" and "hand_drill" not in C.MACHINE_ORDER


def test_mining_needs_the_hand_drill_in_hand():
    g = game()
    tile = wall_next_to_player(g)
    run(g, 2.0, Controls(mine_tile=tile, drill_in_hand=False))
    assert g.world.get(*tile) == C.IRON and g.mining is None
    assert ("mine_hit", tile) not in g.pop_events()          # nem som de mineração
    run(g, 2.0, Controls(mine_tile=tile, drill_in_hand=True))
    assert g.world.get(*tile) == C.SAND and g.inventory.count("iron") > 0


def test_hand_drill_can_be_stored_in_a_chest_and_taken_back():
    g = game()
    chest = Inventory(C.CHEST_SLOTS)
    assert g.inventory.transfer(0, chest) == 1 and g.inventory.count("hand_drill") == 0
    assert chest.transfer(0, g.inventory) == 1 and g.inventory.count("hand_drill") == 1


def test_hand_drill_is_not_a_drone_item():
    from game import drones
    assert "hand_drill" not in C.LOGISTIC_ITEMS
    assert not drones.can_send(Machine("chest", 10, 10), "hand_drill")


def test_old_v10_save_without_the_drill_gets_one_and_never_a_second():
    g = game()
    data = save.state_to_dict(g)
    data["inventory"]["slots"][0] = None                    # save do M3: sem broca
    loaded = save.state_from_dict(data)
    assert loaded.inventory.count("hand_drill") == 1 and loaded.inventory.slots[0] == Stack("hand_drill", 1)
    again = save.state_from_dict(save.state_to_dict(loaded))
    assert again.inventory.count("hand_drill") == 1


def test_drill_stored_in_a_chest_is_not_duplicated_on_load():
    g = game()
    chest = Machine("chest", 60, 60)
    g.inventory.transfer(0, chest.storage)
    g.machines.append(chest)
    loaded = save.state_from_dict(save.state_to_dict(g))
    assert loaded.inventory.count("hand_drill") == 0
    assert sum(m.storage.count("hand_drill") for m in loaded.machines if m.storage) == 1


# ---------------------------------------------------------------- peças de loot
def test_loot_items_stack_and_ride_in_chests_and_saves():
    for item in C.LOOT_ITEMS:
        assert max_stack(item) == C.STACK_LOOT
    g = game()
    g.inventory.add("chip", 25)
    assert sorted(s.count for s in g.inventory.slots if s and s.item == "chip") == [5, 20]
    chest = Machine("chest", 60, 60)
    chest.storage.add("circuit", 3)
    g.machines.append(chest)
    loaded = save.state_from_dict(save.state_to_dict(g))
    assert loaded.inventory.count("chip") == 25
    assert next(m for m in loaded.machines if m.kind == "chest").storage.count("circuit") == 3


def test_loot_item_icons_exist_in_assets():
    for item in C.LOOT_ITEMS:
        assert (C.SPRITES_DIR / f"icon_{item}.png").exists()


@pytest.mark.parametrize("seed", SEEDS)
def test_crate_loot_parts_follow_the_tables_and_are_deterministic(seed):
    g = game(seed)
    for wreck in g.world.wrecks:
        loot = wrecks.crate_loot(wreck, seed)
        assert loot == wrecks.crate_loot(wreck, seed)
        table = C.LOOT_RICH if wreck.rich else (wreck.spec.parts or C.LOOT_COMMON)   # v0.7 M3: robô e ARCA-2 têm as suas
        parts = {i: n for i, n in loot if i in C.LOOT_ITEMS}
        assert set(parts) <= set(table)
        for item, n in parts.items():
            lo, hi = table[item][1]
            assert lo <= n <= hi
        assert len(loot) <= C.CRATE_SLOTS


def test_common_wrecks_give_simple_parts_and_rich_wrecks_the_better_ones():
    common, rich = set(), set()
    for seed in SEEDS:
        for wreck in game(seed).world.wrecks:
            if wreck.kind == "robot":                     # v0.7 M3: o robô dá circuito de propósito
                continue
            parts = {i for i, _ in wrecks.crate_loot(wreck, seed) if i in C.LOOT_ITEMS}
            (rich if wreck.rich else common).update(parts)
    assert {"wire", "iron_ingot"} <= common and not common & {"circuit", "chip"}
    assert {"silicon_wafer", "circuit"} <= rich and "wire" not in rich


@pytest.mark.parametrize("seed", SEEDS[:5])
def test_container_loot_is_the_top_haul(seed):
    for spot in (wrecks.ContainerSpot(*t) for t in game(seed).world.containers):
        loot = dict(wrecks.container_loot(spot, seed))
        assert set(loot) == set(C.CONTAINER_RESOURCES) | set(C.LOOT_ITEMS)
        for item, (_, (lo, hi)) in C.LOOT_CONTAINER.items():
            assert lo <= loot[item] <= hi
        assert wrecks.container_loot(spot, seed) == list(loot.items())


# ---------------------------------------------------------------- contêiner que abre
def stand_at_container(g: GameState):
    tx, ty = g.world.containers[0]
    g.player.x, g.player.y = (tx + 0.5) * T, (ty + 2) * T - 2
    return tx, ty


def test_container_opens_once_gives_the_haul_and_stays_open():
    g = game()
    tile = stand_at_container(g)
    box = g.container_crate(tile)
    assert not box.opened and g.interaction() == ("container", tile)
    g.pop_events()
    g.open_crate(box)
    assert box.opened and ("container_open", False) in g.pop_events()
    g.crate_take(box)
    assert box.empty and g.inventory.count("chip") >= 2 and g.inventory.count("circuit") >= 3
    g.open_crate(box)                                        # abrir de novo não devolve nada
    assert box.empty
    loaded = save.state_from_dict(save.state_to_dict(g))
    again = loaded.container_crate(tile)
    assert again.opened and again.empty


def test_untouched_container_adds_nothing_to_the_save_and_partial_loot_is_kept():
    g = game()
    assert save.state_to_dict(g)["layers"]["surface"].get("crates", []) == []
    tile = stand_at_container(g)
    box = g.container_crate(tile)
    g.open_crate(box)
    g.crate_take(box, 0)                                     # pegou só o 1º slot
    left = box.storage.to_data()
    loaded = save.state_from_dict(save.state_to_dict(g)).container_crate(tile)
    assert loaded.opened and loaded.storage.to_data() == left and not loaded.empty


def test_container_map_entry_follows_the_state():
    from game import map_view
    g = game()
    tile = stand_at_container(g)
    g.surface.explored.reveal_rect(*tile, 1, 1)
    entry = lambda: next(e for e in map_view.map_entries(g, "surface") if e.category == "container")
    assert entry().state == "lacrado"
    g.open_crate(g.container_crate(tile))
    assert entry().state == "aberto"


# ---------------------------------------------------------------- app e render
@pytest.fixture(scope="module")
def app():
    import tempfile
    from pathlib import Path
    from game import settings
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_m4_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def test_app_only_mines_with_the_drill_selected(app):
    app.set_mode("play")
    app.state.inventory.slots[1] = Stack("iron", 3)
    app.hotbar_selected = 0
    assert app.hand_drill_selected() and app.controls().drill_in_hand
    app.hotbar_selected = 1
    assert not app.hand_drill_selected() and not app.controls().drill_in_hand
    app.hotbar_selected = 5                                  # slot vazio
    assert not app.controls().drill_in_hand
    app.hotbar_selected = 0


def test_app_container_label_and_open_surface(app):
    s = app.state
    tx, ty = s.world.containers[0]
    s.player.x, s.player.y = (tx + 0.5) * T, (ty + 2) * T - 2
    app.set_mode("play")
    box = s.container_crate((tx, ty))
    assert app.e_label(("container", (tx, ty))) == "[E] Abrir contêiner"
    s.open_crate(box)
    s.crate_take(box)
    assert app.e_label(("container", (tx, ty))) == "Contêiner aberto"
    closed, opened = app.renderer.container_surface(False), app.renderer.container_surface(True)
    assert closed.get_size() == opened.get_size() and closed is not opened
    assert app.renderer.item_icon("hand_drill").get_size() == (32, 32)
    for item in C.LOOT_ITEMS:
        assert app.renderer.item_icon(item).get_size() == (32, 32)
