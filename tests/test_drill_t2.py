"""v0.6 Fundo M4: broca de mão nv.2 (item, receita na T2, nasce no slot da nv.1, mineração ×1,5, rocha dura)."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game.inventory import Stack, max_stack  # noqa: E402
from game.systems import Controls, GameState  # noqa: E402
from tests.helpers import give  # noqa: E402
from tests.test_hard_rock import HARD, cave_state, put_player_next_to  # noqa: E402

T2_COST = {"hand_drill": 1, "iron_ingot": 2, "wire": 4, "circuit": 1}
DT = 1 / 30


def game() -> GameState:
    return GameState(rng=random.Random(1))


def ready_to_craft(g: GameState) -> None:
    give(g, iron_ingot=2, wire=4, circuit=1)          # a nv.1 já vem no slot 0


def run(g, seconds, controls):
    for _ in range(round(seconds / DT)):
        g.update(DT, controls)


def test_item_registered():
    m = C.MACHINES[C.HAND_DRILL_T2]
    assert C.HAND_DRILL_T2 == "hand_drill_t2"
    assert m.name == "Broca de mão nv.2" and not m.placeable
    assert m.cost == T2_COST and m.unlock_ti == 0
    assert C.HAND_DRILLS == ("hand_drill", "hand_drill_t2")
    assert "hand_drill_t2" in C.T2_RECIPES                # v0.8 M5: os materiais e itens das plantas vêm depois
    assert max_stack("hand_drill_t2") == 1
    assert C.HAND_DRILL_T2 not in C.MACHINE_ORDER


def test_crafting_consumes_t1_and_lands_in_its_slot():
    g = game()
    g.inventory.swap(0, 3)                             # a nv.1 no slot 3
    ready_to_craft(g)
    assert g.craft("hand_drill_t2", bench="t2")
    assert g.inventory.count("hand_drill") == 0
    assert g.inventory.slots[3] == Stack("hand_drill_t2", 1)
    assert g.inventory.count("iron_ingot") == 0 and g.inventory.count("wire") == 0
    assert g.inventory.count("circuit") == 0


def test_needs_t1_in_inventory():
    g = game()
    g.inventory.remove("hand_drill", 1)
    ready_to_craft(g)
    assert g.recipe_status("hand_drill_t2", inv_only=True) == "missing"
    assert g.missing_resource("hand_drill_t2", inv_only=True) == "hand_drill"
    assert not g.craft("hand_drill_t2", bench="t2")


def test_not_in_t1_fabricator():
    g = game()
    ready_to_craft(g)
    assert not g.craft("hand_drill_t2")               # bench "t1": a receita é só da T2


def test_ensure_hand_drill_respects_t2():
    g = game()
    ready_to_craft(g)
    g.craft("hand_drill_t2", bench="t2")
    assert not g.ensure_hand_drill()                   # tem a nv.2: não ganha outra nv.1
    assert g.inventory.count("hand_drill") == 0


# --- minerar com a nv.2 ------------------------------------------------------------------------------------------

def test_hard_rock_base_time():
    assert C.MINE_TIME[C.HARD_ROCK] == 2.25            # ~1,5 s com a nv.2


def test_t1_cannot_break_hard_t2_can():
    g = cave_state()
    put_player_next_to(g, HARD)
    run(g, 3.0, Controls(mine_tile=HARD, drill_in_hand=True, drill_tier=1))
    assert g.world.get(*HARD) == C.HARD_ROCK
    run(g, 1.6, Controls(mine_tile=HARD, drill_in_hand=True, drill_tier=2))
    assert g.world.get(*HARD) != C.HARD_ROCK


def test_t2_hard_rock_takes_about_1_5_s():
    g = cave_state()
    put_player_next_to(g, HARD)
    run(g, 1.4, Controls(mine_tile=HARD, drill_in_hand=True, drill_tier=2))
    assert g.world.get(*HARD) == C.HARD_ROCK


def test_t2_mines_faster():
    g = game()
    px, py = g.player.tile
    g.world.set(px + 1, py, C.IRON)                    # ferro: 1,0 s na nv.1, ~0,67 s na nv.2
    run(g, 0.75, Controls(mine_tile=(px + 1, py), drill_in_hand=True, drill_tier=2))
    assert g.world.get(px + 1, py) != C.IRON


def test_speed_and_hard_flags():
    g = game()
    g.drill_tier = 1
    assert g.mine_speed == 1.0 and not g.can_break_hard
    g.drill_tier = 2
    assert g.mine_speed == C.HAND_DRILL_T2_SPEED and g.can_break_hard
    g.fast = True
    assert g.mine_speed == C.DEBUG_MINE * C.HAND_DRILL_T2_SPEED


def test_bedrock_still_unbreakable():
    g = cave_state()
    g.drill_tier = 2
    assert not g.world.is_minable(0, 0)                # borda do sintético é BEDROCK
