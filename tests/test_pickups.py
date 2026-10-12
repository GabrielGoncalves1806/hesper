"""Recursos soltos no chão da superfície (game/pickups.py) e como o jogador pega."""

import random

from game import config as C
from game.pickups import Pickup, Pickups, hidden_from
from game.surface_gen import generate_surface

W = generate_surface()


def test_generate_is_deterministic_and_on_free_sand():
    a, b = Pickups.generate(W, 7), Pickups.generate(W, 7)
    assert [(p.resource, p.amount, p.x, p.y) for p in a.items] == [(p.resource, p.amount, p.x, p.y) for p in b.items]
    assert len(a.items) == C.PICKUP_START
    assert {p.resource for p in a.items} == set(C.RESOURCES)
    for p in a.items:
        assert C.PICKUP_AMOUNT[0] <= p.amount <= C.PICKUP_AMOUNT[1]
        assert W.is_floor(*p.tile) and W.vein_at(*p.tile) is None
        assert not W.is_water(*p.tile, 3)                       # nunca dentro de um lago futuro
        assert W.dist_from_center(*p.tile) >= C.PICKUP_START_BASE_DIST
    assert len({p.tile for p in a.items}) == len(a.items)


def test_respawn_rate_cap_offscreen_and_far_from_base():
    pk = Pickups([], 0.0)
    rng = random.Random(1)
    player = C.SPAWN_POS
    new = pk.update(W, rng, 60.0, player)
    assert len(new) == round(60 / C.PICKUP_RESPAWN)                 # ~4 por minuto
    for p in new:
        assert hidden_from(player, *p.tile)
        assert W.dist_from_center(*p.tile) >= C.PICKUP_BASE_DIST
        assert W.is_floor(*p.tile)
    pk.update(W, rng, 10_000.0, player)
    assert len(pk.items) == C.PICKUP_MAX                            # teto


def test_respawn_timer_accumulates_small_steps():
    pk = Pickups([], 0.0)
    rng = random.Random(2)
    spawned = sum(len(pk.update(W, rng, 1 / 60, C.SPAWN_POS)) for _ in range(round(C.PICKUP_RESPAWN * 2 * 60) + 2))
    assert spawned == 2


def test_hidden_from_uses_half_screen_box():
    px, py = C.SPAWN_POS
    tx, ty = int(px // C.TILE), int(py // C.TILE)
    hx, hy = C.PICKUP_HIDDEN
    assert not hidden_from((px, py), tx + hx - 1, ty)
    assert hidden_from((px, py), tx + hx + 1, ty)
    assert hidden_from((px, py), tx, ty - hy - 1)


def test_touching_and_at_point():
    pk = Pickups([Pickup("iron", 2, 100.0, 100.0)], 0.0)
    assert pk.touching(105, 104) and not pk.touching(130, 100)
    assert pk.at_point(100, 96) is pk.items[0] and pk.at_point(140, 140) is None
    pk.remove(pk.items[0])
    assert pk.items == []


def test_data_roundtrip_and_sanitize():
    pk = Pickups([Pickup("ice", 3, 10.5, 20.0)], 4.25)
    back = Pickups.from_data(pk.to_data())
    assert back.items == pk.items and back.timer == 4.25
    dirty = {"items": [["unobtanium", 2, 1, 1], ["iron", 0, 1, 1], ["iron", 99, 5, 5]], "timer": 1}
    assert [(p.resource, p.amount) for p in Pickups.from_data(dirty).items] == [("iron", C.PICKUP_AMOUNT[1])]
