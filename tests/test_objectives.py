"""Testes dos objetivos na tela (game/objectives.py). Nada de pygame aqui."""

import random

import pytest

from game import config as C
from game.objectives import FLASH_TIME, OBJECTIVES, ObjectiveTracker, current_index
from game.systems import GameState, Machine
from tests.helpers import give


@pytest.fixture
def game() -> GameState:
    return GameState(rng=random.Random(42))


def current_text(game: GameState) -> str | None:
    i = current_index(game)
    return None if i is None else OBJECTIVES[i].label(game)


def craft_free(game: GameState, kind: str) -> None:
    """Fabrica sem gastar recurso (o teste é dos objetivos, não do fabricador)."""
    game.crafted[kind] += 1
    give(game, **{kind: 1})


def place_at(game: GameState, kind: str, tile: tuple[int, int]) -> None:
    game.inventory.remove(kind, 1)
    game.machines.append(Machine(kind, *tile))


def mine_one(game: GameState, kind: int) -> int:
    """Quebra um tile de minério do lado do player e devolve quanto caiu."""
    px, py = game.player.tile
    game.world.set(px + 1, py, kind)
    before = sum(game.inventory.counts().values())
    game._break_tile((px + 1, py), kind)
    return sum(game.inventory.counts().values()) - before


# ---------------------------------------------------------------- sequência normal
def test_starts_with_iron_counter(game):
    assert current_text(game) == "Minere ferro (0/10)"


def test_normal_sequence_walks_every_objective(game):
    seen = [current_text(game)]

    def step():
        seen.append(current_text(game))

    game.mined_total["iron"] = 10; step()
    game.mined_total["silicon"] = 4; step()
    game.fabricator_opened = True; step()
    craft_free(game, "o2"); step()
    place_at(game, "o2", (61, 66)); step()
    craft_free(game, "chest"); step()
    craft_free(game, "melter"); step()
    game.indices["o2"] = 500; step()
    craft_free(game, "heater"); step()
    craft_free(game, "solar"); step()
    game.read_terminal(0); step()
    game.debug_add_ti(); step()                 # Ti 10.500 -> Névoa
    vein = game.world.veins[0]                  # drill de verdade num veio de verdade
    game.player.x, game.player.y = (vein.tx + 0.5) * C.TILE, (vein.ty + 3) * C.TILE - 4
    craft_free(game, "drill")
    assert game.place("drill", (vein.tx, vein.ty)); step()
    drill = game.drills[0]
    drill.stored = 3
    assert game.collect(drill) == 3; step()
    craft_free(game, "drone_station"); step()
    craft_free(game, "drone"); step()
    game.drones_docked = 1; step()
    game.drone_deliveries = 1; step()
    craft_free(game, "melter_t2"); step()
    game.debug_add_ti(100_000); step()          # -> Verde

    assert seen == [
        "Minere ferro (0/10)",
        "Minere silício (0/4)",
        "Abra o fabricador na base [E]",
        "Fabrique um Gerador de O2",
        "Coloque o gerador perto da base",
        "Fabrique um baú",
        "Minere gelo e fabrique um Derretedor",
        "Chegue a Ti 500",
        "Fabrique um Aquecedor",
        "Fabrique um painel solar",
        "Leia um terminal",
        "Chegue ao estágio Névoa",
        "Coloque uma drill num veio",
        "Colete minério de uma drill",
        "Fabrique uma estação de drones",
        "Fabrique um drone",
        "Coloque o drone na estação [E]",
        "Receba uma entrega de drone",
        "Fabrique uma máquina nv.2",
        "Deixe o planeta verde",
        None,
    ]


def test_generator_far_from_base_does_not_count(game):
    game.mined_total.update(iron=10, silicon=4)
    game.fabricator_opened = True
    craft_free(game, "o2")
    place_at(game, "o2", (64, 90))              # bem longe da cápsula
    assert current_text(game) == "Coloque o gerador perto da base"
    craft_free(game, "o2")
    place_at(game, "o2", (66, 66))
    assert current_text(game) == "Fabrique um baú"


# ---------------------------------------------------------------- contadores
def test_counter_uses_total_mined_not_inventory(game):
    got = mine_one(game, C.IRON)
    assert game.mined_total["iron"] == got
    assert current_text(game) == f"Minere ferro ({got}/10)"
    game.inventory.remove("iron", 999)          # gastou tudo craftando: o contador não volta
    assert current_text(game) == f"Minere ferro ({got}/10)"


def test_inventory_from_elsewhere_does_not_count(game):
    give(game, iron=50)                         # recurso que não veio de mineração
    assert current_text(game) == "Minere ferro (0/10)"


def test_counter_is_capped_at_goal(game):
    game.mined_total["iron"] = 37
    assert OBJECTIVES[0].label(game) == "Minere ferro (10/10)"


def test_rock_does_not_count_as_ore(game):
    mine_one(game, C.ROCK)
    assert game.mined_total == {"iron": 0, "silicon": 0, "ice": 0}


# ---------------------------------------------------------------- fora de ordem
def test_out_of_order_skips_what_is_done(game):
    game.read_terminal(1)                       # leu terminal antes de tudo
    craft_free(game, "o2")                      # e já fabricou um gerador
    game.mined_total.update(iron=12, silicon=5)
    assert current_text(game) == "Abra o fabricador na base [E]"
    game.fabricator_opened = True
    assert current_text(game) == "Coloque o gerador perto da base"


def test_next_line_skips_done_objectives(game):
    game.mined_total["silicon"] = 4             # silício antes do ferro
    tracker = ObjectiveTracker(game)
    lines = tracker.lines(game)
    assert [(l.text, l.style) for l in lines] == [
        ("Minere ferro (0/10)", "current"),
        ("Abra o fabricador na base [E]", "next"),   # silício (já feito) foi pulado
    ]


def test_big_jump_completes_many_at_once(game):
    game.debug_add_ti(100_000)                  # F2 até o verde: Ti, Névoa e Verde de uma vez
    assert current_text(game) == "Minere ferro (0/10)"
    remaining = [o.text for o in OBJECTIVES if not o.done(game)]
    assert "Chegue a Ti 500" not in remaining
    assert "Chegue ao estágio Névoa" not in remaining
    assert "Deixe o planeta verde" not in remaining


# ---------------------------------------------------------------- feedback e fim
def test_tracker_flashes_completed_objective(game):
    tracker = ObjectiveTracker(game)
    game.mined_total["iron"] = 10
    tracker.update(game, 0.016)
    lines = tracker.lines(game)
    assert [(l.text, l.style) for l in lines] == [
        ("Minere ferro (10/10)", "done"),
        ("Minere silício (0/4)", "current"),
    ]
    tracker.update(game, FLASH_TIME)            # passou o tempo do feedback
    assert [l.style for l in tracker.lines(game)] == ["current", "next"]


def test_everything_done_list_disappears(game):
    game.mined_total.update(iron=10, silicon=4, ice=10)
    game.fabricator_opened = True
    for kind in ("o2", "chest", "melter", "heater", "solar", "o2_t2", "drone_station"):
        craft_free(game, kind)
    place_at(game, "o2", (61, 66))
    game.read_terminal(0)
    game.drills_placed = 1
    game.drill_collected["iron"] = 5
    game.drone_deliveries = 1
    game.drones_docked = 1
    tracker = ObjectiveTracker(game)
    assert current_text(game) == "Chegue a Ti 500"
    game.debug_add_ti(100_000)
    tracker.update(game, 0.016)
    assert current_index(game) is None
    assert tracker.visible                      # ainda mostrando o ✓ do último
    assert [l.style for l in tracker.lines(game)] == ["done"]
    tracker.update(game, FLASH_TIME)
    assert not tracker.visible
    assert tracker.lines(game) == []


def test_crafted_counter_does_not_go_back_when_placed_or_dismantled(game):
    give(game, iron=100, silicon=100)
    assert game.craft("chest")
    px, py = game.player.tile
    assert game.place("chest", (px + 2, py))
    assert game.crafted["chest"] == 1 and game.inventory.count("chest") == 0
    assert game.dismantle(game.chests[0])
    assert game.crafted["chest"] == 1
