"""Testes da lógica do jogo. Nenhum deles abre janela nem importa pygame."""

import random

import pytest

from game import config as C
from game.systems import Controls, GameState, stage_for_ti
from game.layers import CAVE
from game.world import World
from tests.helpers import give

DT = 1 / 60


@pytest.fixture
def game() -> GameState:
    return GameState(rng=random.Random(42))


def run(game: GameState, seconds: float, controls: Controls | None = None) -> None:
    controls = controls or Controls()
    for _ in range(round(seconds / DT)):
        game.update(DT, controls)


def put_wall_next_to_player(game: GameState, kind: int) -> tuple[int, int]:
    px, py = game.player.tile
    tile = (px + 1, py)
    game.world.set(*tile, kind)
    return tile


def teleport_outside_base(game: GameState) -> None:
    """Põe o player num 'quartinho' de chão longe da base (fora da zona de O₂)."""
    tx, ty = 64, 80
    for x in range(tx - 1, tx + 2):
        game.world.set(x, ty, C.FLOOR)
    game.player.x, game.player.y = (tx + 0.5) * C.TILE, (ty + 1) * C.TILE - 2
    assert not game.in_base_zone()


# ---------------------------------------------------------------- mundo
def test_world_is_deterministic():
    a, b = World.generate(123), World.generate(123)
    assert a.tiles == b.tiles
    assert a.terminals == b.terminals
    assert World.generate(124).tiles != a.tiles


def test_world_size_and_border():
    w = World.generate()
    assert (w.width, w.height) == (128, 128)
    assert all(w.tiles[0][x] == C.BEDROCK for x in range(128))
    assert w.get(-1, 5) == C.BEDROCK   # fora do mapa conta como parede


def test_crater_center_is_free():
    """O salão da caverna é chão, menos a rampa de subida 3×3 (Marco 2)."""
    w = World.generate()
    rx, ry = C.CAVE_RAMP
    ramp = {(rx + dx, ry + dy) for dx in range(3) for dy in range(3)}
    for y in range(128):
        for x in range(128):
            if w.dist_from_center(x, y) < C.CAVE_SAFE_RADIUS:
                assert w.tiles[y][x] == (C.CRATER if (x, y) in ramp else C.FLOOR), (x, y)


def test_more_ore_far_from_center():
    w = World.generate()

    def ore_ratio(lo, hi):
        cells = [w.tiles[y][x] for y in range(128) for x in range(128)
                 if lo <= w.dist_from_center(x, y) < hi and w.tiles[y][x] != C.FLOOR]
        return sum(t in C.ORE_TILES for t in cells) / len(cells)

    assert ore_ratio(40, 60) > ore_ratio(13, 22) > 0.1


def test_three_terminals_at_growing_distance():
    w = World.generate()
    assert len(w.terminals) == 3
    dists = [w.dist_from_center(*t) for t in w.terminals]
    assert dists == sorted(dists)
    for tx, ty in w.terminals:
        assert w.get(tx, ty) == C.TERMINAL
        assert w.get(tx, ty + 1) == C.FLOOR   # salinha na frente


# ---------------------------------------------------------------- mineração
@pytest.mark.parametrize("kind", [C.ROCK, C.IRON, C.SILICON, C.ICE])
def test_mining_time_depends_on_hardness(game, kind):
    tile = put_wall_next_to_player(game, kind)
    hold = Controls(mine_tile=tile)
    run(game, C.MINE_TIME[kind] - 0.1, hold)
    assert game.world.get(*tile) == kind          # ainda não quebrou
    run(game, 0.15, hold)
    assert game.world.get(*tile) == C.SAND        # agora quebrou (no deserto vira areia)


@pytest.mark.parametrize("kind,resource", [(C.IRON, "iron"), (C.SILICON, "silicon"), (C.ICE, "ice")])
def test_ore_drops_1_to_2(kind, resource):
    for seed in range(20):
        game = GameState(rng=random.Random(seed))
        tile = put_wall_next_to_player(game, kind)
        run(game, 1.5, Controls(mine_tile=tile))
        assert 1 <= game.inventory.count(resource) <= 2


def test_rock_drops_nothing(game):
    tile = put_wall_next_to_player(game, C.ROCK)
    run(game, 1.0, Controls(mine_tile=tile))
    assert game.world.get(*tile) == C.SAND
    assert game.inventory.is_empty()


def test_switching_target_resets_progress(game):
    a = put_wall_next_to_player(game, C.IRON)
    b = (a[0], a[1] - 1)
    game.world.set(*b, C.IRON)
    run(game, 0.8, Controls(mine_tile=a))
    run(game, 0.8, Controls(mine_tile=b))
    assert game.world.get(*a) == C.IRON and game.world.get(*b) == C.IRON


def test_cannot_mine_out_of_reach_or_bedrock(game):
    px, py = game.player.tile
    far = (px + C.MINE_REACH + 1, py)
    game.world.set(*far, C.ROCK)
    assert not game.can_mine(far)
    near = (px + 1, py)
    game.world.set(*near, C.BEDROCK)
    assert not game.can_mine(near)


# ---------------------------------------------------------------- O₂
def test_o2_drains_outside_base(game):
    game.storm = 0.0                               # céu limpo (a tempestade gasta mais: test_weather.py)
    teleport_outside_base(game)
    run(game, 10)
    assert game.o2 == pytest.approx(C.O2_MAX - 10, abs=0.1)


def test_o2_refills_inside_base(game):
    game.o2 = 30
    assert game.in_base_zone()
    run(game, 1)
    assert game.o2 == pytest.approx(50, abs=0.1)
    run(game, 5)
    assert game.o2 == C.O2_MAX


def test_faint_and_respawn_keeps_inventory(game):
    give(game, iron=7, o2=1)
    teleport_outside_base(game)
    game.o2 = 0.5
    run(game, 0.6)
    assert game.fainted
    run(game, C.FAINT_RESPAWN_AT)
    assert (game.player.x, game.player.y) == C.SPAWN_POS
    assert game.o2 == C.O2_MAX
    run(game, C.FAINT_DURATION)
    assert not game.fainted
    assert game.inventory.count("iron") == 7 and game.inventory.count("o2") == 1


# ---------------------------------------------------------------- fabricador
def test_craft_consumes_resources(game):
    give(game, iron=12, silicon=5)
    assert game.recipe_status("o2") == "ok"
    assert game.craft("o2")
    assert game.inventory.counts() == {"iron": 2, "silicon": 1, "o2": 1}


def test_craft_fails_without_resources(game):
    give(game, iron=6, ice=9)
    assert game.recipe_status("melter") == "missing"
    assert game.missing_resource("melter") == "ice"
    assert not game.craft("melter")
    assert game.inventory.count("iron") == 6


def test_recipes_locked_by_ti(game):
    give(game, iron=100, silicon=100, ice=100)
    assert game.recipe_status("heater") == "locked"
    assert not game.craft("heater")
    game.indices["o2"] = 500
    assert game.recipe_status("heater") == "ok"
    assert game.recipe_status("o2_t2") == "locked"
    game.indices["o2"] = 10_000
    assert game.recipe_status("o2_t2") == "ok"


def test_craft_only_in_base(game):
    give(game, iron=50, silicon=50)
    teleport_outside_base(game)
    assert not game.craft("o2")


def test_place_machine(game):
    give(game, iron=10, silicon=4)
    game.craft("o2")
    px, py = game.player.tile
    assert not game.can_place("o2", (px, py))            # em cima do player, não
    assert not game.can_place("o2", C.POD_TILES[0])      # em cima da cápsula, não
    assert not game.can_place("o2", (px + 10, py))       # longe demais, não
    assert game.place("o2", (px + 2, py))
    assert game.inventory.count("o2") == 0
    assert not game.place("o2", (px - 2, py))            # acabou o estoque


# ---------------------------------------------------------------- Ti e estágios
def test_machines_raise_their_index(game):
    give(game, iron=100, silicon=100, ice=100)
    px, py = game.player.tile
    for kind, dx in [("o2", 2), ("melter", -2)]:
        game.craft(kind)
        game.place(kind, (px + dx, py))
    run(game, 10)
    assert game.indices["o2"] == pytest.approx(30, abs=0.2)
    assert game.indices["water"] == pytest.approx(20, abs=0.2)
    assert game.ti == pytest.approx(50, abs=0.4)
    assert game.ti_rate == 5


def test_time_scale_speeds_up_machines(game):
    give(game, iron=10, silicon=4)
    game.craft("o2")
    px, py = game.player.tile
    game.place("o2", (px + 2, py))
    game.toggle_time_scale()
    run(game, 1)
    assert game.indices["o2"] == pytest.approx(30, abs=0.2)


def test_f3_fast_mode_off_by_default_keeps_normal_speeds(game):
    assert not game.fast
    assert game.player_speed == C.PLAYER_SPEED and game.mine_speed == 1.0
    y0 = game.player.y
    run(game, 0.5, Controls(move_y=1))                     # área da cápsula: areia limpa embaixo
    assert game.player.y - y0 == pytest.approx(C.PLAYER_SPEED * 0.5, abs=1)


def test_f3_fast_mode_doubles_walk_and_mines_5x_faster(game):
    game.toggle_fast()
    assert game.fast and C.DEBUG_SPEED == 2.0 and C.DEBUG_MINE == 5.0
    assert game.player_speed == C.PLAYER_SPEED * C.DEBUG_SPEED
    y0 = game.player.y
    run(game, 0.5, Controls(move_y=1))
    assert game.player.y - y0 == pytest.approx(C.PLAYER_SPEED * C.DEBUG_SPEED * 0.5, abs=1)
    for kind in (C.ROCK, C.IRON, C.SMALL_ICE):              # parede, minério e rocha pequena
        tile = put_wall_next_to_player(game, kind)
        run(game, C.MINE_TIME[kind] / C.DEBUG_MINE + 2 * DT, Controls(mine_tile=tile))
        assert game.world.get(*tile) == game.world.floor_kind
    game.toggle_fast()                                      # F3 de novo: volta ao normal
    assert not game.fast and game.player_speed == C.PLAYER_SPEED and game.mine_speed == 1.0
    tile = put_wall_next_to_player(game, C.ROCK)
    run(game, C.MINE_TIME[C.ROCK] / 2, Controls(mine_tile=tile))
    assert game.world.get(*tile) == C.ROCK


def test_stage_thresholds():
    assert stage_for_ti(0) == 1
    assert stage_for_ti(9_999) == 1
    assert stage_for_ti(10_000) == 2
    assert stage_for_ti(99_999) == 2
    assert stage_for_ti(100_000) == 3


def test_stage_changes_and_emits_event(game):
    game.debug_add_ti()
    assert game.stage == 2
    assert ("stage_up", 2) in game.pop_events()
    for _ in range(9):
        game.debug_add_ti()
    assert game.ti == pytest.approx(100_000)
    assert game.stage == 3
    assert ("stage_up", 3) in game.pop_events()


# ---------------------------------------------------------------- player e terminais
def test_player_collides_with_walls(game):
    tile = put_wall_next_to_player(game, C.ROCK)
    run(game, 2, Controls(move_x=1))
    assert game.player.x + C.PLAYER_BOX_W / 2 <= tile[0] * C.TILE + 0.01


def test_terminal_read(game):
    game.enter_layer(CAVE)                       # v0.3: os terminais ficam na caverna
    tx, ty = game.world.terminals[0]
    game.player.x, game.player.y = (tx + 0.5) * C.TILE, (ty + 2) * C.TILE - 4
    assert game.nearby_terminal() == 0
    assert game.read_terminal(0).startswith("Dia 3.")
    assert game.logs_read == {0}


def test_player_remembers_direction(game):
    assert game.player.direction == "down"
    for controls, expected in [(Controls(move_y=-1), "up"), (Controls(move_x=-1), "left"),
                               (Controls(move_x=1), "right"), (Controls(move_y=1), "down")]:
        run(game, 0.1, controls)
        assert game.player.direction == expected
    run(game, 0.5)                      # parado: mantém a última direção
    assert game.player.direction == "down"


def test_mining_turns_player_to_target(game):
    px, py = game.player.tile
    run(game, 0.1, Controls(move_y=-1))          # olhando pra cima...
    px, py = game.player.tile
    game.world.set(px, py + 1, C.ROCK)
    run(game, 0.1, Controls(mine_tile=(px, py + 1)))
    assert game.player.direction == "down"       # ...minerou embaixo, virou pra baixo


def test_no_water_in_stage1_but_water_later():
    """A caverna nunca tem água (Marco 2); o mesmo World com terraforms ligado tem poças da Névoa em diante.
    (A água da superfície de verdade é testada em tests/test_water.py.)"""
    w = World.generate()
    tiles = [(x, y) for y in range(128) for x in range(128)]
    assert not any(w.is_water(x, y, 3) for x, y in tiles)       # caverna: rocha fria, sem poça
    w.terraforms = True
    assert not any(w.is_water(x, y, 1) for x, y in tiles)       # Morto: nenhuma poça
    stage2 = {t for t in tiles if w.is_water(*t, 2)}
    stage3 = {t for t in tiles if w.is_water(*t, 3)}
    assert stage2 and stage2 <= stage3                         # Névoa tem poças; Verde mantém e cresce


# ---------------------------------------------------------------- desmontar
def placed(game, kind="o2", dx=2):
    give(game, iron=100, silicon=100, ice=100)
    game.craft(kind)
    px, py = game.player.tile
    game.place(kind, (px + dx, py))
    return game.machines[-1]


def test_dismantle_returns_machine_to_stock_and_stops_index(game):
    m = placed(game)
    assert game.inventory.count("o2") == 0
    run(game, 1)
    o2_before = game.indices["o2"]
    assert game.dismantle(m)
    assert m not in game.machines and game.inventory.count("o2") == 1
    assert ("dismantle", "o2", (m.tx, m.ty)) in game.pop_events()
    run(game, 2)
    assert game.indices["o2"] == o2_before        # parou de somar
    assert game.ti_rate == 0
    px, py = game.player.tile
    assert game.place("o2", (px - 2, py))         # dá pra recolocar


def test_dismantle_needs_reach(game):
    m = placed(game)
    game.player.x += 10 * C.TILE
    assert not game.can_dismantle(m)
    assert not game.dismantle(m)
    assert m in game.machines


def test_machine_hit_by_sprite_area_and_pod_is_not_a_machine(game):
    m = placed(game, "o2")
    cx = (m.tx + 0.5) * C.TILE
    assert game.machine_at_point(cx, (m.ty + 1) * C.TILE - 2) is m       # na base
    assert game.machine_at_point(cx, (m.ty + 1) * C.TILE - 50) is m      # no topo do sprite (tile de cima)
    assert game.machine_at_point(cx, (m.ty + 1) * C.TILE - 60) is None   # acima do sprite de 56 px
    pod_x, pod_y = C.POD_ANCHOR
    assert game.machine_at_point(pod_x, pod_y - 20) is None              # a cápsula não é desmontável
