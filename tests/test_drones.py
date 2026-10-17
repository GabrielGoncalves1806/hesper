"""Estação de drones (Marco 3): estação, voo, ciclo, coleta das sobras, desmontar e save.
A escolha de tarefa (Envia/Recebe/Lote) fica em tests/test_logistics.py."""

import json
import math
import random

import pytest

from game import config as C
from game import drones, save
from game.drones import CARRYING, COLLECTING, DROPPING, LANDED, OUTBOUND, RETURNING
from game.inventory import Stack
from game.systems import GameState, Machine
from tests.helpers import build_now, give

ST = (60, 70)            # canto da estação nos testes de lógica (não precisa ser chão: a lógica não olha o mapa)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()                                   # Ti 10.000: Névoa, estação liberada
    return g


def add_station(game, tile=ST, count: int = 2) -> Machine:
    """Põe uma estação direto no mapa, com `count` drones nos slots (o teste é da lógica, não do place)."""
    m = Machine("drone_station", *tile)
    m.station = drones.new_station(m, count)
    game.machines.append(m)
    return m


def add_drill(game, dx: int, dy: int = 0, stored: int = 0, resource: str = "iron", station=ST,
              send: bool = True, batch: int = C.DRONE_BATCH_DEFAULT) -> Machine:
    """Drill a (dx, dy) tiles da estação, já com Envia = o minério dela (a não ser que send=False)."""
    d = Machine("drill", station[0] + dx, station[1] + dy, resource=resource, stored_init=stored,
                sends={resource} if send else set(), batch=batch, chip=True)
    game.machines.append(d)
    return d


def add_chest(game, tile, receives=(), sends=(), batch: int = C.DRONE_BATCH_DEFAULT) -> Machine:
    c = Machine("chest", *tile, receives=set(receives), sends=set(sends), batch=batch)
    game.machines.append(c)
    return c


def run(game, seconds: float, step: float = 1 / 30) -> None:
    for _ in range(round(seconds / step)):
        game._update_machines(step)


# ---------------------------------------------------------------- receita
def test_station_recipe_and_power():
    m = C.MACHINES["drone_station"]
    assert m.cost == {"iron_ingot": 10, "circuit": 1, "chip": 1, "wire": 2} and m.unlock_ti == 10_000
    assert m.size == 2 and m.index is None and m.rate == 0          # não soma Ti
    assert C.POWER_USE["drone_station"] == 1
    assert C.MACHINE_ORDER.index("drone_station") == C.MACHINE_ORDER.index("drill") + 1


def test_drone_is_an_item_recipe_unlocked_with_the_station():
    d = C.MACHINES["drone"]
    assert d.cost == {"circuit": 2, "wire": 5, "iron_ingot": 2} and d.unlock_ti == C.MACHINES["drone_station"].unlock_ti
    assert not d.placeable and d.index is None and "drone" not in C.POWER_USE
    assert C.MACHINE_ORDER.index("drone") == C.MACHINE_ORDER.index("drone_station") + 1
    from game.inventory import max_stack
    assert max_stack("drone") == C.STACK_MACHINE


def test_craft_drone_goes_to_the_inventory_and_cannot_be_placed(game):
    game.player.x, game.player.y = C.SPAWN_POS
    assert game.recipe_status("drone") == "missing"
    give(game, circuit=2, wire=5, iron_ingot=2)
    assert not game.craft("drone")                                  # v0.6 Fundo M5: o drone é da Bancada T2
    assert game.craft("drone", bench="t2")
    assert game.inventory.count("drone") == 1 and game.inventory.count("iron_ingot") == 0
    assert game.crafted["drone"] == 1
    assert not game.can_place("drone", (60, 66))                    # não vai pro chão


def test_drone_recipe_locked_before_mist():
    g = GameState(rng=random.Random(1))
    assert g.recipe_status("drone") == "locked"


def test_new_station_is_empty_with_4_free_slots(game):
    m = Machine("drone_station", *ST)
    st = drones.new_station(m)
    assert st.drones == [] and st.free_slots() == [0, 1, 2, 3]


def test_docked_drones_land_on_their_slot(game):
    st = add_station(game)
    assert len(st.station.drones) == 2 and all(d.state == LANDED for d in st.station.drones)
    assert [d.pad for d in st.station.drones] == [0, 1]
    ax, ay = st.anchor                                               # ax = (tx+1)·32, ay = (ty+2)·32
    assert (ax, ay) == ((ST[0] + 1) * 32, (ST[1] + 2) * 32)
    # drone pousado em (sx + px − 8, sy + py − 10): o centro fica 8 px pra dentro
    sx, sy = ax - 32, ay - 72
    for drone, (px, py) in zip(st.station.drones, C.DRONE_PADS):
        assert (drone.x - 8, drone.y - 8) == (sx + px - 8, sy + py - 10)


# ---------------------------------------------------------------- voo e ciclo
def test_flies_straight_over_walls_at_6_tiles_per_second(game):
    st = add_station(game)
    drill = add_drill(game, 20, stored=10)
    add_chest(game, (ST[0] - 2, ST[1]), receives={"iron"})
    # parede maciça no caminho: o drone ignora o mapa
    for x in range(ST[0] + 3, ST[0] + 18):
        game.world.set(x, ST[1], C.BEDROCK)
    run(game, 1 / 30)                                   # decola
    d = st.station.drones[0]
    start = (d.x, d.y)
    run(game, 1.0)
    moved = math.hypot(d.x - start[0], d.y - start[1])
    assert C.DRONE_SPEED == 6
    assert moved == pytest.approx(6 * C.TILE, abs=1)
    assert d.state == OUTBOUND and d.source is drill


def test_low_power_only_makes_them_slower(game):
    st = add_station(game)
    add_drill(game, 20, stored=10)
    add_chest(game, (ST[0] - 2, ST[1]), receives={"iron"})
    # déficit forçado: 3 aquecedores nv.2 (12 kW) + estação (1) + drill (2) = 15 kW contra 5 kW
    game.machines += [Machine("heater_t2", 0, i) for i in range(3)]
    factor = game.power.factor
    assert factor == pytest.approx(5 / 15)
    run(game, 1 / 30)
    d = st.station.drones[0]
    start = (d.x, d.y)
    run(game, 1.0)
    assert math.hypot(d.x - start[0], d.y - start[1]) == pytest.approx(C.DRONE_SPEED * C.TILE * factor, abs=1)


def test_full_cycle_states(game):
    st = add_station(game, count=1)
    drill = add_drill(game, 6, stored=12)
    chest = add_chest(game, (ST[0] - 4, ST[1]), receives={"iron"})
    d = st.station.drones[0]
    seen = []
    for _ in range(900):
        game._update_machines(1 / 30)
        if not seen or seen[-1] != d.state:
            seen.append(d.state)
        if d.state == CARRYING:
            assert d.cargo == 10 and d.resource == "iron" and drill.stored == 2   # pegou o lote (10)
    assert seen[:6] == [OUTBOUND, COLLECTING, CARRYING, DROPPING, RETURNING, LANDED]
    assert chest.storage.count("iron") == 10
    assert (d.x, d.y) == drones.pad_position(st, d.pad)
    assert game.drone_deliveries == 1
    assert any(e[0] == "drone_deliver" and e[1:3] == ("iron", 10) for e in game.pop_events())


def test_source_dismantled_on_the_way_sends_the_drone_back_empty(game):
    st = add_station(game, count=1)
    drill = add_drill(game, 20, stored=10)
    chest = add_chest(game, (ST[0] - 2, ST[1]), receives={"iron"})
    run(game, 0.5)
    game.machines.remove(drill)
    run(game, 10)
    d = st.station.drones[0]
    assert d.state == LANDED and d.cargo == 0 and chest.storage.is_empty()


def test_player_emptied_the_source_before_the_drone_arrived(game):
    st = add_station(game, count=1)
    drill = add_drill(game, 20, stored=10)
    add_chest(game, (ST[0] - 2, ST[1]), receives={"iron"})
    run(game, 0.5)
    drill.stored = 0                                    # o player coletou com Shift+E
    run(game, 15)
    d = st.station.drones[0]
    assert d.state == LANDED and d.cargo == 0


def test_no_receiver_no_trip(game):
    st = add_station(game)
    drill = add_drill(game, 6, stored=20)
    add_chest(game, (ST[0] - 2, ST[1]))                 # baú sem nada configurado
    run(game, 5)
    assert all(d.state == LANDED for d in st.station.drones) and drill.stored == 20


def test_buffer_is_legacy_and_never_receives(game):
    st = add_station(game, count=1)
    st.station.buffer = {"silicon": 4}
    add_drill(game, 6, stored=12)
    run(game, 10)
    assert st.station.buffer == {"silicon": 4}          # sem quem receba: nada vai pro buffer
    assert st.station.drones[0].state == LANDED and st.station.drones[0].cargo == 0


# ---------------------------------------------------------------- jogo: colocar, E, desmontar
def free_station_tile(game) -> tuple[int, int]:
    """Canto de um 2×2 livre perto da base, onde o player (parado embaixo) consegue colocar."""
    for ty in range(66, 72):
        for tx in range(58, 70):
            game.player.x, game.player.y = (tx + 1) * C.TILE, (ty + 3) * C.TILE + 8
            if game.can_place("drone_station", (tx, ty)):
                return tx, ty
    raise AssertionError("sem lugar pra estação perto da base")


def test_build_station_with_the_constructor(game):
    tile = free_station_tile(game)
    assert build_now(game, "drone_station", tile)
    st = game.stations[0]
    assert st.station is not None and st.station.drones == []           # vem vazia
    assert game.inventory.count("drone_station") == 0
    assert all(game.machine_at(t) is st for t in st.tiles)


def test_station_cannot_go_on_a_vein(game):
    vein = game.world.veins[0]
    for corner in [(vein.tx, vein.ty), (vein.tx - 1, vein.ty - 1), (vein.tx + 1, vein.ty)]:
        game.player.x, game.player.y = (corner[0] + 1) * C.TILE, (corner[1] + 3) * C.TILE + 8
        assert not game.can_place("drone_station", corner)


def test_e_opens_the_station_and_takes_the_leftover_buffer(game):
    tile = free_station_tile(game)
    build_now(game, "drone_station", tile)
    game.inventory.clear()
    st = game.stations[0]
    ax, ay = st.anchor
    game.player.x, game.player.y = ax, ay + 10                   # logo abaixo da estação
    assert game.interaction() == ("station", st)                 # E abre o painel (mesmo vazia)
    st.station.buffer = {"iron": 12, "ice": 3}
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


def test_dismantle_returns_buffer_cargo_drones_and_recipe(game):
    tile = free_station_tile(game)
    build_now(game, "drone_station", tile)
    game.inventory.clear()
    give(game, drone=2)
    st = game.stations[0]
    assert game.station_dock(st, game.inventory.slots.index(next(s for s in game.inventory.slots if s and s.item == "drone"))) == 2
    st.station.buffer = {"iron": 30}
    st.station.drones[1].resource, st.station.drones[1].cargo = "ice", 8     # um drone no ar, carregado
    st.station.drones[1].state = RETURNING
    assert game.dismantle(st)
    assert st not in game.machines
    cost = C.MACHINES["drone_station"].cost                          # v0.5 M1: a receita volta, não a estação
    assert game.inventory.count("iron") == 30 and game.inventory.count("ice") == 8
    assert all(game.inventory.count(r) == n for r, n in cost.items())          # v0.6 Fundo M5: a receita nova (lingote, circuito...)
    assert game.inventory.count("drone_station") == 0
    assert game.inventory.count("drone") == 2                       # os 2, até o que estava voando


def test_dismantle_refuses_when_it_does_not_fit(game):
    tile = free_station_tile(game)
    build_now(game, "drone_station", tile)
    st = game.stations[0]
    st.station.buffer = {"iron": 30}
    for i in range(C.INVENTORY_SLOTS):
        game.inventory.slots[i] = Stack("silicon", 50)
    before = game.inventory.to_data()
    assert not game.dismantle(st)
    assert st in game.machines and st.station.buffer == {"iron": 30}
    assert game.inventory.to_data() == before
    assert ("inv_full",) in game.pop_events()


# ---------------------------------------------------------------- save
def drone_state() -> GameState:
    state = save.new_state()
    state.debug_add_ti()
    give(state, drone=1)                                # um item qualquer no inventário (vai no save)
    tile = free_station_tile(state)
    assert build_now(state, "drone_station", tile)
    st = state.stations[0]
    drones.dock(st, st.station, 0)
    drones.dock(st, st.station, 2)                      # slot 2 (o 3º): o save guarda o slot de cada um
    st.station.buffer = {"iron": 11, "silicon": 4}
    flying = st.station.drones[0]                       # no ar, levando 9 de gelo
    flying.state, flying.resource, flying.cargo = CARRYING, "ice", 9
    flying.x += 200
    state.drone_deliveries = 3
    return state


def test_save_roundtrip_keeps_buffer_slots_and_cargo(tmp_path):
    state = drone_state()
    path = tmp_path / "slot1.json"
    assert save.write_save(state, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == save.SAVE_VERSION
    saved = next(m for m in data["layers"]["surface"]["machines"] if m["kind"] == "drone_station")
    assert saved["buffer"] == {"iron": 11, "silicon": 4}
    assert saved["drones"] == [["ice", 9, 1], None, [None, 0, 1], None]   # v0.8 M5: [recurso, carga, tier]
    loaded = save.load_game(path)
    st = loaded.stations[0]
    assert st.station.buffer == {"iron": 11, "silicon": 4}
    assert loaded.drone_deliveries == 3
    # os drones voltam pousados (sem posição no ar), mas a carga não some
    assert [d.pad for d in st.station.drones] == [0, 2]
    assert all(d.state == LANDED and (d.x, d.y) == drones.pad_position(st, d.pad) for d in st.station.drones)
    assert st.station.drones[0].cargo == 9
    # sem ninguém que Receba gelo, ele espera pousado; um baú que recebe aparece e ele entrega
    loaded._update_machines(1 / 60)
    assert st.station.drones[0].cargo == 9 and st.station.drones[0].state == LANDED
    chest = Machine("chest", st.tx - 3, st.ty, receives={"ice"})
    loaded.machines.append(chest)
    for _ in range(600):
        loaded._update_machines(1 / 30)
    assert chest.storage.count("ice") == 9 and st.station.drones[0].cargo == 0
    assert st.station.buffer == {"iron": 11, "silicon": 4}
