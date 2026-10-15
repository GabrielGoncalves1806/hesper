"""Testes do inventário com slots (game/inventory.py) e de como o jogo usa ele. Nada de pygame aqui."""

import random

import pytest

from game import config as C
from game.inventory import Inventory, Stack, max_stack
from game.systems import GameState
from tests.helpers import build_now, give


# ================================================================ modelo puro
def test_stack_limits():
    assert max_stack("iron") == C.STACK_RESOURCE == 50
    assert max_stack("o2") == max_stack("drill") == max_stack("chest") == C.STACK_MACHINE == 5


def test_add_fills_existing_stack_then_empty_slots():
    inv = Inventory(4)
    assert inv.add("iron", 30) == 0
    assert inv.add("iron", 30) == 0                     # completa a 1ª (50) e abre outra com 10
    assert inv.to_data() == [["iron", 50], ["iron", 10], None, None]
    assert inv.add("o2", 7) == 0                        # máquina: pilhas de 5
    assert inv.to_data() == [["iron", 50], ["iron", 10], ["o2", 5], ["o2", 2]]


def test_add_returns_what_did_not_fit():
    inv = Inventory(2)
    assert inv.add("ice", 120) == 20
    assert inv.count("ice") == 100
    assert inv.add("iron", 1) == 1                      # cheio de gelo: ferro não entra


def test_count_counts_and_space():
    inv = Inventory(3)
    inv.add("iron", 60)
    inv.add("silicon", 4)
    assert inv.count("iron") == 60 and inv.count("silicon") == 4 and inv.count("ice") == 0
    assert inv.counts() == {"iron": 60, "silicon": 4}
    assert inv.space_for("iron") == 40                  # só sobra na pilha de 10
    assert inv.space_for("silicon") == 46
    assert not inv.has_space("ice")
    assert inv.has_space("iron", 40) and not inv.has_space("iron", 41)


def test_remove_by_type_takes_from_the_last_stacks_first():
    inv = Inventory(4)
    inv.add("iron", 70)                                 # [50, 20]
    assert inv.remove("iron", 25) == 25
    assert inv.to_data() == [["iron", 45], None, None, None]   # a de 20 sumiu, a da hotbar ficou
    assert inv.remove("iron", 100) == 45                # tira só o que tem
    assert inv.is_empty()


def test_remove_from_slot():
    inv = Inventory(2)
    inv.add("o2", 2)
    assert inv.remove_from_slot(0) == 1 and inv.slots[0].count == 1
    assert inv.remove_from_slot(0) == 1 and inv.slots[0] is None
    assert inv.remove_from_slot(0) == 0


def test_take_and_put_pick_and_drop():
    inv = Inventory(3)
    inv.add("iron", 20)
    hand = inv.take(0)
    assert hand == Stack("iron", 20) and inv.slots[0] is None
    assert inv.put(2, hand) is None                     # slot vazio: solta tudo
    assert inv.slots[2] == Stack("iron", 20)
    assert inv.put(1, None) is None                     # mão vazia em slot vazio: nada


def test_put_merges_same_item_and_keeps_the_rest():
    inv = Inventory(1)
    inv.add("iron", 40)
    hand = inv.put(0, Stack("iron", 25))
    assert inv.slots[0].count == 50 and hand == Stack("iron", 15)


def test_put_swaps_different_items():
    inv = Inventory(1)
    inv.add("ice", 3)
    hand = inv.put(0, Stack("o2", 2))
    assert inv.slots[0] == Stack("o2", 2) and hand == Stack("ice", 3)


def test_take_half_rounds_up():
    inv = Inventory(2)
    inv.add("silicon", 5)
    assert inv.take_half(0) == Stack("silicon", 3) and inv.slots[0].count == 2
    inv.add("o2", 1)
    assert inv.take_half(1) == Stack("o2", 1) and inv.slots[1] is None
    assert inv.take_half(1) is None


def test_move_swap_and_merge_between_inventories():
    a, b = Inventory(2), Inventory(2)
    a.add("iron", 10)
    a.move(0, 1)                                        # dentro do mesmo inventário
    assert a.to_data() == [None, ["iron", 10]]
    b.add("iron", 45)
    a.move(1, 0, b)                                     # junta no outro: 45 + 5 = 50, sobram 5 na origem
    assert b.slots[0].count == 50 and a.slots[1] == Stack("iron", 5)
    b.add("ice", 2)                                     # b: [ferro 50, gelo 2]
    a.move(1, 1, b)                                     # item diferente: troca
    assert a.slots[1] == Stack("ice", 2) and b.slots[1] == Stack("iron", 5)
    a.swap(0, 1)
    assert a.slots[0] == Stack("ice", 2) and a.slots[1] is None


def test_split_puts_half_in_the_first_empty_slot():
    inv = Inventory(3)
    inv.add("iron", 9)
    assert inv.split(0)
    assert inv.to_data() == [["iron", 4], ["iron", 5], None]
    full = Inventory(1)
    full.add("iron", 9)
    assert not full.split(0)                            # sem slot vazio
    assert not Inventory(2).split(0)                    # slot vazio


def test_quick_move_sends_every_stack_of_that_item():
    player, chest = Inventory(4), Inventory(2)
    player.add("iron", 70)                              # [50, 20]
    player.add("ice", 3)
    assert player.quick_move(1, chest) == 70
    assert player.counts() == {"ice": 3} and chest.count("iron") == 70


def test_quick_move_keeps_what_does_not_fit():
    player, chest = Inventory(2), Inventory(1)
    player.add("iron", 70)
    assert player.quick_move(0, chest) == 50
    assert player.count("iron") == 20 and chest.count("iron") == 50


def test_copy_is_independent_and_data_roundtrip():
    inv = Inventory(3)
    inv.add("iron", 12)
    inv.add("drill", 1)
    clone = inv.copy()
    clone.remove("iron", 12)
    assert inv.count("iron") == 12
    assert Inventory.from_data(inv.to_data()).to_data() == inv.to_data() == [["iron", 12], ["drill", 1], None]


# ================================================================ o jogo usando o inventário
@pytest.fixture
def game() -> GameState:
    return GameState(rng=random.Random(42))


def fill_with_ice(game: GameState) -> None:
    game.inventory.add("ice", C.INVENTORY_SLOTS * C.STACK_RESOURCE)


def test_player_has_16_slots_and_the_hotbar_is_the_first_row(game):
    assert len(game.inventory) == C.INVENTORY_SLOTS == 16
    assert C.HOTBAR_SLOTS == 8
    assert game.inventory.slots[0] == Stack("hand_drill", 1)   # v0.5 M4: nasce com a broca de mão no 1º slot
    game.inventory.add("iron", 1)
    assert game.inventory.slots[1] == Stack("iron", 1)  # o que chega primeiro vai pra hotbar


def test_mining_with_full_inventory_breaks_the_tile_but_loses_the_ore(game):
    fill_with_ice(game)
    px, py = game.player.tile
    game.world.set(px + 1, py, C.IRON)
    game._break_tile((px + 1, py), C.IRON)
    assert game.world.get(px + 1, py) == C.SAND         # quebrou (areia, no deserto)
    assert game.inventory.count("iron") == 0            # mas não pegou
    assert game.mined_total["iron"] == 0
    events = game.pop_events()
    assert ("inv_full",) in events and not [e for e in events if e[0] == "pickup"]


def test_mining_with_room_for_part_of_the_drop(game):
    game.inventory.remove("hand_drill", 1)
    game.inventory.add("ice", (C.INVENTORY_SLOTS - 1) * C.STACK_RESOURCE)
    game.inventory.add("iron", C.STACK_RESOURCE - 1)    # sobra lugar pra 1 ferro
    game.rng = random.Random(0)
    while True:                                         # força um drop de 2
        px, py = game.player.tile
        game.world.set(px + 1, py, C.IRON)
        state = game.rng.getstate()
        if game.rng.randint(C.DROP_MIN, C.DROP_MAX) == 2:
            game.rng.setstate(state)
            break
    game._break_tile((px + 1, py), C.IRON)
    assert game.inventory.count("iron") == C.STACK_RESOURCE
    events = game.pop_events()
    assert ("pickup", (px + 1, py), "iron", 1) in events and ("inv_full",) in events


def test_craft_turns_into_an_item(game):
    give(game, iron=5)
    assert game.craft("constructor")
    assert game.inventory.counts() == {"constructor": 1, "hand_drill": 1}


def test_craft_counts_the_slot_freed_by_the_recipe(game):
    fill_with_ice(game)
    game.inventory.remove("ice", 50)                    # libera o último slot...
    give(game, iron=5)                                  # ...e o ferro ocupa ele: inventário lotado
    assert not game.inventory.has_space("constructor")
    assert game.craft("constructor")                    # o ferro é gasto todo: o slot dele vira o construtor
    assert game.inventory.count("constructor") == 1 and game.inventory.count("iron") == 0


def test_craft_with_full_inventory_warns(game):
    fill_with_ice(game)
    chest = place_chest_with(game, iron=10, silicon=4)  # recurso só no baú
    assert game.recipe_status("constructor") == "ok"
    assert not game.craft("constructor")                # o item não teria onde ficar
    assert ("inv_full",) in game.pop_events()
    assert chest.storage.count("iron") == 10            # não gastou nada


def place_chest_with(game: GameState, **content) -> object:
    """Constrói um baú do lado do player (na base) e enche com `content`."""
    saved = game.inventory.copy()
    game.inventory.clear()
    px, py = game.player.tile
    assert build_now(game, "chest", (px + 2, py))
    game.inventory = saved
    chest = game.chests[-1]
    for item, n in content.items():
        chest.storage.add(item, n)
    return chest


def test_chest_is_a_machine_without_index(game):
    chest = place_chest_with(game)
    assert chest.is_chest and len(chest.storage) == C.CHEST_SIZES["chest"] == 16
    assert C.MACHINES["chest"].cost == {"iron": 6} and C.MACHINES["chest"].unlock_ti == C.CHEST_UNLOCK_TI
    ti = game.ti
    game._update_machines(100)
    assert game.ti == ti and game.ti_rate == 0          # não soma Ti


def test_fabricator_uses_inventory_first_then_base_chests(game):
    chest = place_chest_with(game, iron=20)
    give(game, iron=2)
    assert game.available("iron") == 22
    assert game.craft("constructor")                    # 5 ferro
    assert game.inventory.count("iron") == 0            # gastou os 2 do inventário primeiro
    assert chest.storage.count("iron") == 17            # e 3 do baú


def test_chests_outside_the_base_do_not_count(game):
    chest = place_chest_with(game, iron=20, silicon=10)
    assert chest in game.base_chests()
    chest.ty += 30                                      # "leva" o baú pra longe da zona de O₂
    assert chest not in game.base_chests()
    assert game.recipe_status("constructor") == "missing"


def test_e_opens_the_closest_chest(game):
    chest = place_chest_with(game)
    game.player.x, game.player.y = (chest.tx + 0.5) * C.TILE, (chest.ty + 1) * C.TILE + 8
    assert game.interaction() == ("chest", chest)
    game.player.x += 5 * C.TILE
    assert game.interaction() is None or game.interaction()[0] != "chest"


def test_chest_with_content_cannot_be_dismantled(game):
    chest = place_chest_with(game, ice=3)
    assert not game.dismantle(chest)
    assert chest in game.machines and ("chest_not_empty",) in game.pop_events()
    chest.storage.clear()
    assert game.dismantle(chest)
    assert game.inventory.count("chest") == 0 and game.inventory.count("iron") == 6   # v0.5 M1: a receita


def test_dismantle_needs_room_for_the_recipe(game):
    px, py = game.player.tile
    m = build_now(game, "o2", (px + 2, py))
    fill_with_ice(game)
    assert not game.dismantle(m)
    assert m in game.machines and ("inv_full",) in game.pop_events()


def test_build_spends_from_the_inventory_not_from_a_slot(game):
    give(game, constructor=1, iron=100, silicon=100)
    px, py = game.player.tile
    assert game.build("o2", (px + 2, py))
    assert game.inventory.count("iron") == 90 and game.inventory.count("silicon") == 96
    assert game.inventory.count("o2") == 0


# ================================================================ drill e inventário
def mist_game_with_drill():
    game = GameState(rng=random.Random(5))
    game.debug_add_ti()
    vein = game.world.veins[0]
    game.player.x, game.player.y = (vein.tx + 0.5) * C.TILE, (vein.ty + 3) * C.TILE - 4
    assert build_now(game, "drill", (vein.tx, vein.ty))
    game.inventory.clear()
    return game, game.drills[0]


def test_drill_collect_keeps_what_does_not_fit():
    game, drill = mist_game_with_drill()
    drill.stored = 20
    fill_with_ice(game)
    game.inventory.remove("ice", 50)                    # 1 slot livre...
    game.inventory.add(drill.resource, 43)              # ...e sobra lugar pra só 7 do minério da drill
    assert game.collect(drill) == 7
    assert drill.stored == 13 and ("inv_full",) in game.pop_events()


def test_dismantling_a_drill_that_does_not_fit_keeps_it_in_place():
    game, drill = mist_game_with_drill()
    drill.stored = 20
    fill_with_ice(game)
    game.inventory.remove("ice", 50)
    game.inventory.add(drill.resource, 45)              # cabem só 5 dos 20
    assert not game.dismantle(drill)                    # v0.5 M1: ou cabe tudo (minério + receita), ou nada muda
    assert drill in game.machines and drill.stored == 20
    assert game.inventory.count(drill.resource) == 45
