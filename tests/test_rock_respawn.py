"""Rochas pequenas de minério reaparecendo na superfície (game/rock_respawn.py)."""

import random

import pytest

from game import config as C
from game import layers, save
from game.rock_respawn import RockRespawn, blocked_tiles, can_spawn, count, hidden_from, pick_kind
from game.surface_gen import generate_surface
from game.systems import Machine

W0 = generate_surface()


@pytest.fixture
def world():
    return generate_surface()          # cópia nova a cada teste (o cache devolve cópia)


def spawn(world, seconds, player=C.SPAWN_POS, machines=(), seed=1, rocks=None):
    rocks = rocks or RockRespawn()
    return rocks, rocks.update(world, random.Random(seed), seconds, player, machines)


def test_start_count_matches_the_generator():
    n = count(W0)
    assert 400 <= n <= 470                          # ~430: as ~357 de antes + ~70 no lugar dos soltos
    assert n < C.ROCK_MAX


def test_rate_one_every_respawn_seconds_and_timer_accumulates(world):
    rocks, born = spawn(world, 60.0)
    assert len(born) == round(60 / C.ROCK_RESPAWN)          # 4 por minuto
    rocks2, total = RockRespawn(), 0
    rng = random.Random(2)
    for _ in range(round(C.ROCK_RESPAWN * 2 * 60) + 2):     # passos de 1/60 s somam
        total += len(rocks2.update(world, rng, 1 / 60, C.SPAWN_POS))
    assert total == 2


def test_new_rocks_are_off_screen_and_far_from_base(world):
    player = (150.5 * C.TILE, 60.5 * C.TILE)                # longe da base: as duas regras valem juntas
    _, born = spawn(world, 40 * C.ROCK_RESPAWN, player=player)
    assert len(born) == 40
    for t in born:
        assert hidden_from(player, *t)
        assert world.dist_from_center(*t) >= C.ROCK_BASE_DIST
        assert world.get(*t) in C.SMALL_ROCKS


def test_hidden_from_uses_half_screen_box():
    px, py = C.SPAWN_POS
    tx, ty = int(px // C.TILE), int(py // C.TILE)
    hx, hy = C.ROCK_HIDDEN
    assert not hidden_from((px, py), tx + hx - 1, ty)
    assert hidden_from((px, py), tx + hx + 1, ty)
    assert hidden_from((px, py), tx, ty - hy - 1)


def test_only_on_free_sand(world):
    blocked = blocked_tiles(world)
    _, born = spawn(world, 60 * C.ROCK_RESPAWN)
    pristine = generate_surface()
    for tx, ty in born:
        assert pristine.get(tx, ty) == C.SAND and pristine.vein_at(tx, ty) is None
        assert not pristine.is_water(tx, ty, 3)                       # nunca num lago futuro
        assert (tx, ty) not in blocked                                # destroço, veio, cratera
        assert not any(pristine.is_solid(tx + dx, ty + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def test_can_spawn_rejects_each_forbidden_spot(world):
    sand = next((x, y) for y in range(20, world.height - 20) for x in range(20, world.width - 20)
                if can_spawn(world, x, y) and world.dist_from_center(x, y) > 30)
    assert can_spawn(world, *sand)
    # máquina no tile ou encostada nele
    for m in (Machine("chest", *sand), Machine("solar", sand[0] + 1, sand[1])):
        assert not can_spawn(world, *sand, blocked_tiles(world, [m]))
    # vizinho sólido (rocha, morro) ou o próprio tile ocupado
    w2 = generate_surface()
    w2.set(sand[0], sand[1] - 1, C.SMALL_ICE)
    assert not can_spawn(w2, *sand)
    w2.set(*sand, C.SMALL_IRON)
    assert not can_spawn(w2, *sand)
    # perto da base
    cx, cy = world.center
    near = (int(cx) + 5, int(cy) + 5)
    assert world.dist_from_center(*near) < C.ROCK_BASE_DIST and not can_spawn(world, *near)
    # destroço, veio e rampa (cratera) ficam bloqueados
    blocked = blocked_tiles(world)
    assert world.wrecks and all(t in blocked for wk in world.wrecks for t in wk.tiles + [wk.crate])
    assert world.veins and all(t in blocked for v in world.veins for t in v.tiles)
    assert all(t in blocked for t in layers.ramp_tiles(world))
    assert (world.crater[0] + 1, world.crater[1] + 3) in blocked     # onde o player chega da caverna


def test_never_on_or_next_to_a_machine(world):
    """Mapa cheio de máquinas espalhadas: nenhuma rocha cai em cima nem do lado delas."""
    rng = random.Random(5)
    machines = []
    while len(machines) < 300:
        x, y = rng.randrange(world.width), rng.randrange(world.height)
        if world.get(x, y) == C.SAND and world.dist_from_center(x, y) > 14:
            machines.append(Machine("chest", x, y))
    _, born = spawn(world, 80 * C.ROCK_RESPAWN, machines=machines)
    near_machine = {(m.tx + dx, m.ty + dy) for m in machines for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    assert born and not set(born) & near_machine


def test_cap_stops_respawn(world):
    rocks, born = spawn(world, 100_000.0)
    assert count(world) == C.ROCK_MAX and rocks.timer == 0.0
    assert spawn(world, 10 * C.ROCK_RESPAWN, rocks=rocks)[1] == []   # no teto: nada
    world.set(*born[0], C.SAND)                                         # quebrou uma: volta a contar
    assert len(spawn(world, C.ROCK_RESPAWN, rocks=rocks)[1]) == 1 and count(world) == C.ROCK_MAX


def test_weights_follow_small_rock_weights():
    kinds = [pick_kind(i / 1000) for i in range(1000)]
    for res, kind in (("iron", C.SMALL_IRON), ("silicon", C.SMALL_SILICON), ("ice", C.SMALL_ICE)):
        assert abs(kinds.count(kind) / 1000 - C.SMALL_ROCK_WEIGHTS[res]) < 0.01


def test_respawned_rocks_survive_save_roundtrip(tmp_path):
    state = save.new_state()
    state.rng = random.Random(9)
    world = state.world
    rock = next((x, y) for y in range(world.height) for x in range(world.width) if world.get(x, y) in C.SMALL_ROCKS)
    state._break_tile(rock, world.get(*rock))
    born = state._update_rocks(3 * C.ROCK_RESPAWN + 2.0)
    assert len(born) == 3 and ("rock_spawn", born[0]) in state.pop_events()
    path = tmp_path / "slot1.json"
    save.write_save(state, path)
    loaded = save.load_game(path)
    assert [loaded.world.get(*t) for t in born] == [world.get(*t) for t in born]
    assert loaded.world.get(*rock) == C.SAND
    assert loaded.world.tiles == world.tiles
    assert loaded.surface.rocks.timer == pytest.approx(2.0)


def test_respawn_keeps_running_while_player_is_in_the_cave():
    state = save.new_state()
    state.rng = random.Random(3)
    state.enter_layer(layers.CAVE)
    before = count(state.surface.world)
    born = state._update_rocks(2 * C.ROCK_RESPAWN)
    assert len(born) == 2 and count(state.surface.world) == before + 2
    assert all(state.surface.world.get(*t) in C.SMALL_ROCKS for t in born)
