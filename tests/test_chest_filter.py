"""Filtro do baú pros drones (bíblia §8, Marco 3): qual baú recebe a entrega e o save do filtro."""

import random

import pytest

from game import config as C
from game import drones, save
from game.drones import LANDED
from game.inventory import Inventory, Stack
from game.systems import GameState, Machine

ST = (60, 70)            # canto da estação (a lógica não olha o mapa)


def station() -> Machine:
    m = Machine("drone_station", *ST)
    m.station = drones.new_station(m, 2)     # a estação vem vazia (v4): 2 drones nos slots 1 e 2
    return m


def chest(dx: int, dy: int = 0, filter: str = "all") -> Machine:
    """Baú a (dx, dy) tiles do canto da estação. A estação ocupa (ST) e (ST + 1): dx = 2 é encostado à direita."""
    return Machine("chest", ST[0] + dx, ST[1] + dy, storage=Inventory(C.CHEST_SLOTS), filter=filter)


def fill(c: Machine, leave_for: tuple[str, int] | None = None) -> None:
    """Enche o baú de silício; com `leave_for=(item, n)`, o último slot fica com espaço pra só n desse item."""
    for i in range(C.CHEST_SLOTS):
        c.storage.slots[i] = Stack("silicon", 50)
    if leave_for:
        item, n = leave_for
        c.storage.slots[-1] = Stack(item, 50 - n)


# ---------------------------------------------------------------- pick_delivery_chest
def test_filtered_chest_beats_all_even_if_farther():
    st = station()
    near_all = chest(2)                       # encostado
    far_iron = chest(6, filter="iron")        # 5 tiles
    assert drones.pick_delivery_chest(st, [near_all, far_iron], "iron") is far_iron
    assert drones.pick_delivery_chest(st, [near_all, far_iron], "ice") is near_all


def test_chest_filtered_for_another_ore_never_receives():
    st = station()
    ice_only = chest(2, filter="ice")
    assert drones.pick_delivery_chest(st, [ice_only], "iron") is None
    assert drones.pick_delivery_chest(st, [ice_only], "ice") is ice_only


def test_without_chest_returns_none_so_it_goes_to_the_buffer():
    assert drones.pick_delivery_chest(station(), [], "iron") is None


def test_tie_breaks_by_distance_to_the_station():
    st = station()
    a, b = chest(5, filter="iron"), chest(-2, filter="iron")    # 4 e 2 tiles
    assert drones.pick_delivery_chest(st, [a, b], "iron") is b
    c, d = chest(-4), chest(3)                                  # "all": 4 e 1 tile
    assert drones.pick_delivery_chest(st, [c, d], "silicon") is d


def test_full_chest_is_skipped():
    st = station()
    full_iron, spare_all = chest(2, filter="iron"), chest(4)
    fill(full_iron)
    assert drones.pick_delivery_chest(st, [full_iron, spare_all], "iron") is spare_all


def test_radius_is_6_tiles():
    assert C.DRONE_CHEST_RADIUS == 6
    st = station()
    edge, out = chest(7), chest(-7)            # 6 tiles da borda direita / 7 da esquerda
    assert drones.pick_delivery_chest(st, [edge], "iron") is edge
    assert drones.pick_delivery_chest(st, [out], "iron") is None
    assert drones.pick_delivery_chest(st, [chest(0, 8)], "iron") is None   # 7 tiles abaixo da borda de baixo


# ---------------------------------------------------------------- unload: carga dividida
def test_partial_load_splits_filtered_then_all_then_buffer():
    st = station()
    iron = chest(2, filter="iron")
    fill(iron, ("iron", 5))                    # cabe 5
    gen = chest(-2)
    fill(gen, ("iron", 4))                     # cabe 4
    other = chest(3, filter="ice")             # vazio, mas é de gelo: não recebe
    drone = st.station.drones[0]
    drone.resource, drone.cargo = "iron", 20
    events = []
    delivered = drones.unload(st, drone, [gen, other, iron], events)
    assert delivered == 20 and drone.cargo == 0 and drone.resource is None
    assert iron.storage.count("iron") == 50 and gen.storage.count("iron") == 50
    assert other.storage.is_empty() and st.station.buffer == {"iron": 11}
    assert events == [("drone_deliver", "iron", 20, iron.anchor)]          # um aviso só, no 1º baú


def test_nothing_is_lost_when_everything_is_full():
    st = station()
    st.station.buffer = {"ice": C.STATION_BUFFER - 3}
    c = chest(2)
    fill(c, ("iron", 2))
    drone = st.station.drones[0]
    drone.resource, drone.cargo = "iron", 10
    assert drones.unload(st, drone, [c], []) == 5
    assert drone.cargo == 5 and drone.resource == "iron" and st.station.buffer["iron"] == 3


def test_can_accept_ignores_chests_filtered_away():
    st = station()
    st.station.buffer = {"iron": C.STATION_BUFFER}
    assert not drones.can_accept(st, [])
    assert drones.can_accept(st, [chest(2, filter="ice")])        # aceita gelo
    full = chest(2, filter="ice")
    fill(full)
    assert not drones.can_accept(st, [full])


def test_drone_cycle_fills_the_filtered_chest():
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    st = station()
    g.machines.append(st)
    general, ice_chest = chest(2), chest(-5, filter="ice")
    g.machines += [general, ice_chest]
    g.machines.append(Machine("drill", ST[0] + 6, ST[1], resource="ice", stored=12))
    for _ in range(8 * 30):
        g._update_machines(1 / 30)
    assert ice_chest.storage.count("ice") == 12 and general.storage.is_empty()
    assert all(d.state == LANDED for d in st.station.drones)


# ---------------------------------------------------------------- save
@pytest.mark.parametrize("value", C.CHEST_FILTERS)
def test_filter_roundtrip(value):
    c = chest(2, filter=value)
    data = save.machine_to_dict(c)
    assert data["filter"] == value
    assert save.machine_from_dict(data).filter == value


def test_old_save_without_filter_loads_as_all():
    data = save.machine_to_dict(chest(2, filter="iron"))
    del data["filter"]
    assert save.machine_from_dict(data).filter == "all"
    data["filter"] = "lava"                                    # valor estranho: também vira "all"
    assert save.machine_from_dict(data).filter == "all"


def test_new_chest_starts_as_all():
    assert Machine("chest", 1, 1).filter == "all"
