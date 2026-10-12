"""Estação de drones (Marco 3): escolha da drill, voo, entrega, buffer, coleta com E, desmontar e save."""

import json
import math
import random

import pytest

from game import config as C
from game import drones, save
from game.drones import COLLECTING, DELIVERING, LANDED, OUTBOUND, RETURNING
from game.inventory import Stack
from game.systems import GameState, Machine
from tests.helpers import give

ST = (60, 70)            # canto da estação nos testes de lógica (não precisa ser chão: a lógica não olha o mapa)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()                                   # Ti 10.000: Névoa, estação liberada
    return g


def add_station(game, tile=ST) -> Machine:
    """Põe uma estação direto no mapa (o teste é da lógica, não do place)."""
    m = Machine("drone_station", *tile)
    m.station = drones.new_station(m)
    game.machines.append(m)
    return m


def add_drill(game, dx: int, dy: int = 0, stored: int = 0, resource: str = "iron", station=ST) -> Machine:
    """Drill a (dx, dy) tiles da estação (mesma medida de centro a centro que os drones usam)."""
    d = Machine("drill", station[0] + dx, station[1] + dy, resource=resource, stored=stored)
    game.machines.append(d)
    return d


def add_chest(game, tile) -> Machine:
    from game.inventory import Inventory
    c = Machine("chest", *tile, storage=Inventory(C.CHEST_SLOTS))
    game.machines.append(c)
    return c


def run(game, seconds: float, step: float = 1 / 30) -> None:
    for _ in range(round(seconds / step)):
        game._update_machines(step)


# ---------------------------------------------------------------- receita
def test_station_recipe_and_power():
    m = C.MACHINES["drone_station"]
    assert m.cost == {"iron": 20, "silicon": 15, "ice": 5} and m.unlock_ti == 10_000
    assert m.size == 2 and m.index is None and m.rate == 0          # não soma Ti
    assert C.POWER_USE["drone_station"] == 3
    assert C.MACHINE_ORDER.index("drone_station") == C.MACHINE_ORDER.index("drill") + 1


def test_station_comes_with_two_landed_drones_on_the_pads(game):
    st = add_station(game)
    assert len(st.station.drones) == 2 and all(d.state == LANDED for d in st.station.drones)
    ax, ay = st.anchor                                               # ax = (tx+1)·32, ay = (ty+2)·32
    assert (ax, ay) == ((ST[0] + 1) * 32, (ST[1] + 2) * 32)
    # drone pousado em (sx + px − 8, sy + py − 10): o centro fica 8 px pra dentro
    sx, sy = ax - 32, ay - 72
    for drone, (px, py) in zip(st.station.drones, C.DRONE_PADS):
        assert (drone.x - 8, drone.y - 8) == (sx + px - 8, sy + py - 10)


# ---------------------------------------------------------------- escolha da drill
def test_picks_the_fullest_drill_in_range_with_at_least_5(game):
    st = add_station(game)
    a = add_drill(game, 10, stored=8)
    b = add_drill(game, -20, stored=12)
    add_drill(game, 3, 5, stored=4)                     # abaixo do mínimo
    add_drill(game, 31, stored=20)                      # fora do alcance (31 tiles)
    assert drones.pick_drill(st, game.drills, set()) is b
    assert drones.pick_drill(st, game.drills, {id(b)}) is a      # b já tem drone indo


def test_range_is_30_tiles(game):
    st = add_station(game)
    edge = add_drill(game, 30, stored=6)
    assert drones.tile_distance(st, edge) == 30
    assert drones.pick_drill(st, game.drills, set()) is edge


def test_never_two_drones_on_the_same_drill(game):
    st = add_station(game)
    only = add_drill(game, 8, stored=15)
    run(game, 0.1)
    first, second = st.station.drones
    assert first.state == OUTBOUND and first.target is only
    assert second.state == LANDED and second.target is None      # a única drill já tem drone


def test_two_drones_split_two_drills_fullest_first(game):
    st = add_station(game)
    small = add_drill(game, 8, stored=6)
    big = add_drill(game, -8, stored=18)
    run(game, 0.1)
    assert [d.target for d in st.station.drones] == [big, small]


def test_two_stations_do_not_share_a_drill(game):
    a = add_station(game)
    b = add_station(game, (ST[0], ST[1] + 6))
    add_drill(game, 10, stored=10)
    run(game, 0.1)
    busy = [d for m in (a, b) for d in m.station.drones if d.state != LANDED]
    assert len(busy) == 1


# ---------------------------------------------------------------- voo
def test_flies_straight_over_walls_at_4_tiles_per_second(game):
    st = add_station(game)
    drill = add_drill(game, 20, stored=10)
    # parede maciça no caminho: o drone ignora o mapa
    for x in range(ST[0] + 3, ST[0] + 18):
        game.world.set(x, ST[1], C.BEDROCK)
    run(game, 1 / 30)                                   # decola
    d = st.station.drones[0]
    start = (d.x, d.y)
    run(game, 1.0)
    moved = math.hypot(d.x - start[0], d.y - start[1])
    assert moved == pytest.approx(4 * C.TILE, abs=1)
    assert d.state == OUTBOUND and d.target is drill


def test_low_power_only_makes_them_slower(game):
    st = add_station(game)
    add_drill(game, 20, stored=10)
    # déficit forçado: 3 aquecedores nv.2 (12 kW) + estação (3) + drill (2) = 17 kW contra 5 kW
    game.machines += [Machine("heater_t2", 0, i) for i in range(3)]
    factor = game.power.factor
    assert factor == pytest.approx(5 / 17)
    run(game, 1 / 30)
    d = st.station.drones[0]
    start = (d.x, d.y)
    run(game, 1.0)
    assert math.hypot(d.x - start[0], d.y - start[1]) == pytest.approx(4 * C.TILE * factor, abs=1)


def test_full_cycle_states_and_takes_everything(game):
    st = add_station(game)
    drill = add_drill(game, 6, stored=9)
    d = st.station.drones[0]
    seen = []
    for _ in range(600):
        game._update_machines(1 / 30)
        if not seen or seen[-1] != d.state:
            seen.append(d.state)
        if d.state == RETURNING:
            assert drill.stored == 0 and d.cargo == 9 and d.resource == "iron"   # pegou TUDO
    assert seen[:5] == [OUTBOUND, COLLECTING, RETURNING, DELIVERING, LANDED]
    assert (d.x, d.y) == drones.pad_position(st, d.pad)


def test_drill_dismantled_on_the_way_sends_the_drone_back_empty(game):
    st = add_station(game)
    drill = add_drill(game, 20, stored=10)
    run(game, 0.5)
    game.machines.remove(drill)
    run(game, 10)
    d = st.station.drones[0]
    assert d.state == LANDED and d.cargo == 0 and st.station.stored == 0


# ---------------------------------------------------------------- entrega
def test_delivers_to_the_nearest_chest_within_6_tiles(game):
    st = add_station(game)
    far = add_chest(game, (ST[0] - 7, ST[1]))           # 7 tiles da borda: longe demais
    near = add_chest(game, (ST[0] + 7, ST[1] + 1))      # 6 tiles da borda direita (que é tx+1): ainda vale
    add_drill(game, 6, stored=12, resource="ice")
    run(game, 8)
    assert near.storage.count("ice") == 12 and far.storage.is_empty()
    assert st.station.stored == 0
    assert game.drone_deliveries == 1
    assert any(e[0] == "drone_deliver" and e[1:3] == ("ice", 12) for e in game.pop_events())


def test_without_chest_it_goes_to_the_buffer(game):
    st = add_station(game)
    add_drill(game, 6, stored=12)
    run(game, 8)
    assert st.station.buffer == {"iron": 12}
    assert game.drone_deliveries == 1


def test_full_chest_overflows_to_the_buffer(game):
    st = add_station(game)
    chest = add_chest(game, (ST[0] + 2, ST[1]))
    for i in range(C.CHEST_SLOTS - 1):                  # só sobra lugar pra 1 pilha incompleta de ferro
        chest.storage.slots[i] = Stack("silicon", 50)
    chest.storage.slots[-1] = Stack("iron", 45)
    add_drill(game, 6, stored=12)
    run(game, 8)
    assert chest.storage.count("iron") == 50 and st.station.buffer == {"iron": 7}


def test_full_buffer_keeps_the_rest_on_the_drone_and_warns_once(game):
    st = add_station(game)
    st.station.buffer = {"iron": 45}
    add_drill(game, 6, stored=12, resource="ice")
    run(game, 8)
    d = st.station.drones[0]
    assert st.station.buffer == {"iron": 45, "ice": 5} and st.station.full
    assert d.state == LANDED and d.cargo == 7 and d.resource == "ice"      # pousado com a pepita
    assert [e for e in game.pop_events() if e[0] == "station_full"] == [("station_full", st.anchor)]
    run(game, 2)
    assert not [e for e in game.pop_events() if e[0] == "station_full"]  # não repete


def test_full_buffer_and_no_room_keeps_drones_landed(game):
    st = add_station(game)
    st.station.buffer = {"iron": C.STATION_BUFFER}
    drill = add_drill(game, 6, stored=20)
    run(game, 5)
    assert all(d.state == LANDED for d in st.station.drones) and drill.stored == 20
    # um baú perto com espaço destrava
    chest = add_chest(game, (ST[0] - 1, ST[1]))
    run(game, 8)
    assert chest.storage.count("iron") == 20 and drill.stored == 0


def test_landed_drone_with_cargo_delivers_as_soon_as_there_is_room(game):
    st = add_station(game)
    st.station.buffer = {"iron": C.STATION_BUFFER}
    d = st.station.drones[0]
    d.resource, d.cargo = "ice", 6
    run(game, 0.5)
    assert d.cargo == 6
    st.station.buffer = {"iron": 40}                    # o player coletou um pouco
    run(game, 0.1)
    assert d.cargo == 0 and st.station.buffer == {"iron": 40, "ice": 6}


# ---------------------------------------------------------------- jogo: colocar, E, desmontar
def free_station_tile(game) -> tuple[int, int]:
    """Canto de um 2×2 livre perto da base, onde o player (parado embaixo) consegue colocar."""
    for ty in range(66, 72):
        for tx in range(58, 70):
            game.player.x, game.player.y = (tx + 1) * C.TILE, (ty + 3) * C.TILE + 8
            if game.can_place("drone_station", (tx, ty)):
                return tx, ty
    raise AssertionError("sem lugar pra estação perto da base")


def test_place_station_from_the_inventory(game):
    give(game, drone_station=1)
    tile = free_station_tile(game)
    assert game.place("drone_station", tile)
    st = game.stations[0]
    assert st.station is not None and len(st.station.drones) == 2
    assert game.inventory.count("drone_station") == 0
    assert all(game.machine_at(t) is st for t in st.tiles)


def test_station_cannot_go_on_a_vein(game):
    give(game, drone_station=1)
    vein = game.world.veins[0]
    for corner in [(vein.tx, vein.ty), (vein.tx - 1, vein.ty - 1), (vein.tx + 1, vein.ty)]:
        game.player.x, game.player.y = (corner[0] + 1) * C.TILE, (corner[1] + 3) * C.TILE + 8
        assert not game.can_place("drone_station", corner)


def test_e_collects_the_buffer(game):
    give(game, drone_station=1)
    tile = free_station_tile(game)
    game.place("drone_station", tile)
    st = game.stations[0]
    ax, ay = st.anchor
    game.player.x, game.player.y = ax, ay + 10                   # logo abaixo da estação
    assert game.interaction() is None                            # buffer vazio: E fica pro fabricador
    st.station.buffer = {"iron": 12, "ice": 3}
    assert game.interaction() == ("station", st)
    assert game.collect_station(st) == 15
    assert st.station.buffer == {} and game.inventory.count("iron") == 12 and game.inventory.count("ice") == 3
    assert ("station_collect", "iron", 12, st.anchor) in game.pop_events()


def test_e_with_full_inventory_keeps_the_rest(game):
    st = add_station(game)
    for i in range(C.INVENTORY_SLOTS - 1):
        game.inventory.slots[i] = Stack("silicon", 50)
    st.station.buffer = {"iron": 70}
    assert game.collect_station(st) == 50
    assert st.station.buffer == {"iron": 20}
    assert ("inv_full",) in game.pop_events()


def test_dismantle_returns_buffer_cargo_and_station(game):
    give(game, drone_station=1)
    tile = free_station_tile(game)
    game.place("drone_station", tile)
    st = game.stations[0]
    st.station.buffer = {"iron": 30}
    st.station.drones[1].resource, st.station.drones[1].cargo = "ice", 8     # um drone no ar, carregado
    st.station.drones[1].state = RETURNING
    assert game.dismantle(st)
    assert st not in game.machines
    assert game.inventory.count("iron") == 30 and game.inventory.count("ice") == 8
    assert game.inventory.count("drone_station") == 1


def test_dismantle_refuses_when_it_does_not_fit(game):
    give(game, drone_station=1)
    tile = free_station_tile(game)
    game.place("drone_station", tile)
    st = game.stations[0]
    st.station.buffer = {"iron": 30}
    for i in range(C.INVENTORY_SLOTS):
        game.inventory.slots[i] = Stack("silicon", 50)
    before = game.inventory.to_data()
    assert not game.dismantle(st)
    assert st in game.machines and st.station.buffer == {"iron": 30}
    assert game.inventory.to_data() == before
    assert ("inv_full",) in game.pop_events()


# ---------------------------------------------------------------- save v3
def drone_state() -> GameState:
    state = save.new_state()
    state.debug_add_ti()
    give(state, drone_station=1, chest=1)
    tile = free_station_tile(state)
    assert state.place("drone_station", tile)
    st = state.stations[0]
    st.station.buffer = {"iron": 11, "silicon": 4}
    flying = st.station.drones[0]                       # no ar, voltando com 9 de gelo
    flying.state, flying.resource, flying.cargo = RETURNING, "ice", 9
    flying.x += 200
    state.drone_deliveries = 3
    return state


def test_save_v3_roundtrip_keeps_buffer_and_cargo(tmp_path):
    state = drone_state()
    path = tmp_path / "slot1.json"
    assert save.write_save(state, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 3
    saved = next(m for m in data["machines"] if m["kind"] == "drone_station")
    assert saved["buffer"] == {"iron": 11, "silicon": 4}
    assert saved["drone_cargo"] == [["ice", 9], None]
    loaded = save.load_game(path)
    st = loaded.stations[0]
    assert st.station.buffer == {"iron": 11, "silicon": 4}
    assert loaded.drone_deliveries == 3
    # os drones voltam pousados (sem posição no ar), mas a carga não some
    assert all(d.state == LANDED and (d.x, d.y) == drones.pad_position(st, d.pad) for d in st.station.drones)
    assert st.station.drones[0].cargo == 9
    loaded._update_machines(1 / 60)                     # no primeiro frame ele entrega
    assert st.station.buffer == {"iron": 11, "silicon": 4, "ice": 9}
    assert st.station.drones[0].cargo == 0


def test_migration_v2_to_v3(tmp_path):
    data = save.state_to_dict(save.new_state())
    data["version"] = 2
    del data["progress"]["drone_deliveries"]            # v2 não tinha drones
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = save.load_game(path)
    assert loaded is not None and loaded.drone_deliveries == 0 and loaded.stations == []
    save.write_save(loaded, path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 3
