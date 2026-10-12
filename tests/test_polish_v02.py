"""Polimento final do v0.2: fabricar em lote, decolagem do drone, volumes padrão, ícone de sem energia
e as contas do alcance da estação (o que o fantasma mostra)."""

import random

import pytest

from game import config as C
from game import drones, energy, settings
from game.systems import GameState, Machine
from tests.helpers import give


@pytest.fixture
def game() -> GameState:
    return GameState(rng=random.Random(3))


# ---------------------------------------------------------------- fabricar em lote
def test_craft_many_makes_up_to_five(game):
    give(game, iron=100, silicon=100)
    assert game.craft_many("o2") == C.CRAFT_BATCH == 5
    assert game.inventory.count("o2") == 5
    assert game.inventory.count("iron") == 100 - 5 * C.MACHINES["o2"].cost["iron"]


def test_craft_many_stops_when_resources_run_out(game):
    cost = C.MACHINES["o2"].cost
    give(game, **{r: n * 3 + 1 for r, n in cost.items()})   # dá pra 3 e sobra 1 de cada
    assert game.craft_many("o2") == 3
    assert game.inventory.count("o2") == 3
    assert all(game.inventory.count(r) == 1 for r in cost)


def test_craft_many_emits_a_single_craft_event(game):
    give(game, iron=100, silicon=100)
    game.pop_events()
    game.craft_many("o2")
    crafts = [e for e in game.pop_events() if e[0] == "craft"]
    assert crafts == [("craft", "o2", 5)]                     # um som só, com a quantidade
    assert game.crafted["o2"] == 5


def test_craft_many_without_resources(game):
    assert game.craft_many("o2") == 0
    assert not [e for e in game.pop_events() if e[0] == "craft"]


# ---------------------------------------------------------------- decolagem/pouso do drone
def _station_with_drone():
    m = Machine("drone_station", 60, 70)
    m.station = drones.new_station(m, 1)
    return m, m.station.drones[0]


def test_lift_is_zero_when_landed_and_grows_with_distance():
    m, d = _station_with_drone()
    assert drones.lift(m, d) == 0.0
    ramp = C.DRONE_SPEED * C.TILE * drones.LIFT_TIME
    px, py = drones.pad_position(m, d.pad)
    d.state = drones.OUTBOUND
    assert drones.lift(m, d) == 0.0                     # acabou de decolar: ainda no chão
    d.x = px + ramp / 2
    assert drones.lift(m, d) == pytest.approx(0.5)      # subindo
    d.x = px + ramp * 3
    assert drones.lift(m, d) == 1.0                     # lá em cima
    d.state, d.x = drones.RETURNING, px + ramp / 4
    assert drones.lift(m, d) == pytest.approx(0.25)     # descendo pro pad
    d.state, d.x = drones.DELIVERING, px
    assert drones.lift(m, d) == 0.0


def test_takeoff_takes_lift_time_at_full_speed():
    m, d = _station_with_drone()
    d.state = drones.OUTBOUND
    far = Machine("drill", 80, 70, resource="iron", stored=10)
    d.target = far
    for _ in range(round(drones.LIFT_TIME * 60) - 2):
        drones._fly(d, *drones.hover_position(far), 1 / 60)
    assert 0.8 < drones.lift(m, d) < 1.0
    for _ in range(4):
        drones._fly(d, *drones.hover_position(far), 1 / 60)
    assert drones.lift(m, d) == 1.0


# ---------------------------------------------------------------- volumes padrão
def test_default_mix():
    assert settings.DEFAULTS["master"] == 1.0
    assert settings.DEFAULTS["sfx"] == 0.4 and settings.DEFAULTS["ambient"] == 0.5


# ---------------------------------------------------------------- ícone de sem energia
def test_starved_only_consumers_in_deficit():
    for kind in ("o2", "melter", "heater", "o2_t2", "drill", "drone_station"):
        assert energy.starved(kind, 0.6), kind
        assert not energy.starved(kind, 1.0), kind
    for kind in ("solar", "chest"):
        assert not energy.starved(kind, 0.2), kind


# ---------------------------------------------------------------- alcance da estação
def test_drills_in_range_uses_the_same_rule_as_the_drones():
    st = drones.Spot(60, 70)
    near = Machine("drill", 60 + 29, 70, resource="iron")
    far = Machine("drill", 60 + 31, 70, resource="iron")
    assert drones.drills_in_range(st, [near, far]) == [near]
    assert drones.pick_drill(st, [Machine("drill", 60 + 31, 70, resource="iron", stored=10)], set()) is None


def test_delivery_area_is_the_six_tile_square():
    st = Machine("drone_station", 60, 70)
    assert drones.delivery_rect(st) == (54, 64, 14, 14)
    assert drones.delivers_to([st], (54, 64))             # canto do quadrado (gap 6 nos dois eixos)
    assert drones.delivers_to([st], (67, 77))
    assert not drones.delivers_to([st], (53, 70))         # 7 tiles à esquerda
    assert not drones.delivers_to([st], (68, 70))
    assert not drones.delivers_to([], (60, 70))


def test_spot_matches_a_real_station():
    real, spot = Machine("drone_station", 60, 70), drones.Spot(60, 70)
    assert spot.anchor == real.anchor and spot.size == real.size
    assert drones.range_center(spot) == ((61) * C.TILE, (71) * C.TILE)
