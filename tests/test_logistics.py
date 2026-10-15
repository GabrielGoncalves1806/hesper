"""Logística dos drones estilo The Planet Crafter (bíblia §8, Marco 3): Envia/Recebe/Lote em baús e drills,
escolha de tarefa, reservas entre drones, destino cheio no caminho, conservação, alcance global, drill como
inventário, persistência e a migração v4 -> v5."""

import json
import random

import pytest

from game import config as C
from game import drones, save
from game.drones import CARRYING, LANDED, Ledger, OUTBOUND, RETURNING
from game.inventory import Stack
from game.systems import GameState, Machine
from tests.helpers import build_now

ST = (60, 70)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add_station(game, tile=ST, count: int = 1) -> Machine:
    m = Machine("drone_station", *tile)
    m.station = drones.new_station(m, count)
    game.machines.append(m)
    return m


def drill(game, tx, ty, stored=0, resource="iron", send=True, batch=C.DRONE_BATCH_DEFAULT) -> Machine:
    d = Machine("drill", tx, ty, resource=resource, stored_init=stored,
                sends={resource} if send else set(), batch=batch, chip=True)
    game.machines.append(d)
    return d


def chest(game, tx, ty, receives=(), sends=(), batch=C.DRONE_BATCH_DEFAULT, **content) -> Machine:
    c = Machine("chest_large", tx, ty, receives=set(receives), sends=set(sends), batch=batch)
    for item, n in content.items():
        c.storage.add(item, n)
    game.machines.append(c)
    return c


def run(game, seconds: float, step: float = 1 / 30) -> None:
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def total(game, item: str) -> int:
    """Quanto desse item existe no mundo: baús, drills, carga dos drones e sobras das estações."""
    n = sum(m.storage.count(item) for m in game.logistics)
    for st in game.stations:
        n += st.station.buffer.get(item, 0)
        n += sum(d.cargo for d in st.station.drones if d.resource == item)
    return n


# ---------------------------------------------------------------- configuração
def test_new_chest_and_new_drill_start_with_nothing(game):
    game.player.x, game.player.y = 94.5 * C.TILE, 102 * C.TILE
    assert build_now(game, "chest", (94, 100))
    c = game.chests[0]
    assert c.sends == set() and c.receives == set() and c.batch == 10
    assert not drones.configured(c)
    vein = game.world.veins[0]
    game.player.x, game.player.y = (vein.tx + 1) * C.TILE, (vein.ty + 3) * C.TILE + 8
    assert build_now(game, "drill", (vein.tx, vein.ty))
    d = game.drills[0]
    assert d.sends == set() and d.receives == set() and d.batch == 10       # drill nova também vem vazia


def test_same_item_cannot_be_in_send_and_receive():
    c = Machine("chest", 0, 0)
    assert drones.toggle_receive(c, "iron") and c.receives == {"iron"}
    assert drones.toggle_send(c, "iron") and c.sends == {"iron"} and c.receives == set()   # marcar desmarca o outro
    assert drones.toggle_receive(c, "iron") and c.receives == {"iron"} and c.sends == set()
    assert drones.toggle_receive(c, "iron") and c.receives == set()                         # de novo: desliga
    drones.toggle_send(c, "ice")
    drones.toggle_receive(c, "silicon")
    assert c.sends == {"ice"} and c.receives == {"silicon"}
    assert not drones.toggle_send(c, "o2")                                  # só itens logísticos


def test_drill_only_sends_its_own_ore_and_never_receives():
    d = Machine("drill", 0, 0, resource="ice")
    assert not drones.toggle_send(d, "iron")
    assert not drones.toggle_receive(d, "ice")
    assert drones.toggle_send(d, "ice") and d.sends == {"ice"} and d.receives == set()


def test_batch_options():
    c = Machine("chest", 0, 0)
    assert c.batch == C.DRONE_BATCH_DEFAULT == 10
    for n in (1, 5, 10, 20):
        assert drones.set_batch(c, n) and c.batch == n
    assert not drones.set_batch(c, 7) and c.batch == 20


# ---------------------------------------------------------------- escolha da tarefa
def test_task_takes_min_of_batch_stock_and_room(game):
    st = add_station(game)
    src = chest(game, 70, 70, sends={"iron"}, batch=20, iron=35)
    dst = chest(game, 50, 70, receives={"iron"})
    for i in range(C.CHEST_SLOTS):                      # destino com espaço pra só 12 de ferro
        dst.storage.slots[i] = Stack("silicon", 50)
    dst.storage.slots[0] = Stack("iron", 38)
    task = drones.pick_task(st, game.logistics, Ledger())
    assert (task.source, task.dest, task.item, task.amount) == (src, dst, "iron", 12)
    dst.storage.slots[0] = None                        # agora cabe 50: o lote (20) manda
    assert drones.pick_task(st, game.logistics, Ledger()).amount == 20
    src.storage.clear()
    src.storage.add("iron", 3)                          # estoque menor que o lote: baú manda o que tem
    assert drones.pick_task(st, game.logistics, Ledger()).amount == 3


def test_drill_waits_for_a_full_batch_or_full_drill(game):
    st = add_station(game)
    d = drill(game, 70, 70, stored=9, batch=10)
    chest(game, 55, 70, receives={"iron"})
    assert drones.pick_task(st, game.logistics, Ledger()) is None         # 9 < lote 10: não vale a viagem
    d.stored = 10
    assert drones.pick_task(st, game.logistics, Ledger()).amount == 10
    d.batch = 20
    assert drones.pick_task(st, game.logistics, Ledger()) is None
    d.stored = C.DRILL_CAPACITY                                            # cheia: vai mesmo assim
    assert drones.pick_task(st, game.logistics, Ledger()).amount == 20


def test_fullest_source_first_then_shortest_trip(game):
    st = add_station(game)
    near = chest(game, 64, 70, sends={"ice"}, ice=8)
    full = chest(game, 90, 70, sends={"ice"}, ice=30)
    dst_far = chest(game, 30, 70, receives={"ice"})
    dst_near = chest(game, 92, 72, receives={"ice"})
    task = drones.pick_task(st, game.logistics, Ledger())
    assert task.source is full and task.dest is dst_near                   # mais cheia; destino da viagem mais curta
    full.storage.clear()
    full.storage.add("ice", 8)                                             # empate de estoque: a viagem mais curta
    task = drones.pick_task(st, game.logistics, Ledger())
    assert task.source is near
    assert dst_far is not None


def test_no_pair_when_nobody_receives_or_nobody_sends(game):
    st = add_station(game)
    chest(game, 64, 70, iron=30)
    chest(game, 66, 70, receives={"iron"})
    assert drones.pick_task(st, game.logistics, Ledger()) is None
    chest(game, 68, 70, sends={"ice"}, ice=4)
    assert drones.pick_task(st, game.logistics, Ledger()) is None          # ninguém recebe gelo


def test_global_range_drill_across_the_map(game):
    st = add_station(game, (62, 62))
    far = drill(game, 3, 120, stored=20, resource="silicon")              # do outro lado do mapa (~85 tiles)
    dst = chest(game, 60, 64, receives={"silicon"})
    assert drones.tile_distance(st, far) > 80
    run(game, 40)
    assert dst.storage.count("silicon") >= 10 and game.drone_deliveries >= 1


# ---------------------------------------------------------------- reservas entre drones
def test_two_drones_do_not_fight_over_the_same_stock(game):
    st = add_station(game, count=2)
    src = chest(game, 70, 70, sends={"iron"}, batch=10, iron=10)
    chest(game, 55, 70, receives={"iron"})
    run(game, 0.1)
    a, b = st.station.drones
    assert a.state == OUTBOUND and a.planned == 10
    assert b.state == LANDED                                               # o estoque só dava pra um
    src.storage.add("iron", 4)
    run(game, 0.6)
    assert b.state == OUTBOUND and b.planned == 4                          # chegou mais: o 2º pega o resto


def test_reservation_splits_a_bigger_stock(game):
    st = add_station(game, count=2)
    chest(game, 70, 70, sends={"iron"}, batch=10, iron=15)
    chest(game, 55, 70, receives={"iron"})
    run(game, 0.1)
    assert sorted(d.planned for d in st.station.drones) == [5, 10]


def test_destination_space_is_reserved_too(game):
    st = add_station(game, count=2)
    chest(game, 70, 70, sends={"iron"}, iron=10)
    chest(game, 72, 70, sends={"iron"}, iron=10)
    dst = chest(game, 55, 70, receives={"iron"})
    for i in range(C.CHEST_SLOTS):
        dst.storage.slots[i] = Stack("silicon", 50)
    dst.storage.slots[0] = Stack("iron", 40)                                # cabem só 10
    run(game, 0.1)
    assert sum(d.state == OUTBOUND for d in st.station.drones) == 1


def test_two_stations_share_the_reservations(game):
    a = add_station(game)
    b = add_station(game, (ST[0], ST[1] + 6))
    chest(game, 70, 70, sends={"iron"}, iron=10)
    chest(game, 55, 70, receives={"iron"})
    run(game, 0.1)
    busy = [d for m in (a, b) for d in m.station.drones if d.state != LANDED]
    assert len(busy) == 1


# ---------------------------------------------------------------- destino cheio no caminho
def test_destination_filled_midway_goes_to_another_receiver(game):
    st = add_station(game)
    chest(game, 80, 70, sends={"ice"}, ice=10)
    first = chest(game, 70, 70, receives={"ice"})
    second = chest(game, 40, 70, receives={"ice"})
    run(game, 0.1)
    d = st.station.drones[0]
    assert d.dest is first
    for i in range(C.CHEST_SLOTS):                                        # o player enche o destino
        first.storage.slots[i] = Stack("silicon", 50)
    first.storage.slots[0] = Stack("ice", 46)                              # cabem só 4
    run(game, 30)
    assert first.storage.count("ice") == 50 and second.storage.count("ice") == 6
    assert d.state == LANDED and d.cargo == 0


def test_no_other_receiver_returns_with_cargo_and_delivers_later(game):
    st = add_station(game)
    chest(game, 80, 70, sends={"ice"}, ice=10)
    only = chest(game, 70, 70, receives={"ice"})
    run(game, 0.1)
    for i in range(C.CHEST_SLOTS):
        only.storage.slots[i] = Stack("silicon", 50)                       # cheio: não cabe nada
    run(game, 30)
    d = st.station.drones[0]
    assert d.state == LANDED and d.cargo == 10 and d.resource == "ice"     # pousado segurando, nada sumiu
    later = chest(game, 58, 70, receives={"ice"})
    run(game, 10)
    assert later.storage.count("ice") == 10 and d.cargo == 0


def test_destination_dismantled_midway(game):
    st = add_station(game)
    chest(game, 80, 70, sends={"ice"}, ice=10)
    gone = chest(game, 40, 70, receives={"ice"})
    other = chest(game, 30, 76, receives={"ice"})
    run(game, 0.1)
    d = st.station.drones[0]
    assert d.dest is gone
    run(game, 5)                                                          # já pegou e está levando
    assert d.state == CARRYING
    game.machines.remove(gone)
    run(game, 20)
    assert other.storage.count("ice") == 10 and d.cargo == 0


# ---------------------------------------------------------------- nada some
def test_items_are_conserved_in_long_cycles_with_many_drones(game):
    rng = random.Random(11)
    add_station(game, count=4)
    add_station(game, (40, 40), count=4)
    sources = [chest(game, rng.randrange(10, 118), rng.randrange(10, 118), sends={r}, batch=rng.choice((1, 5, 10, 20)),
                     **{r: rng.randrange(20, 120)}) for r in ("iron", "silicon", "ice") for _ in range(2)]
    sinks = [chest(game, rng.randrange(10, 118), rng.randrange(10, 118), receives=set(C.RESOURCES)) for _ in range(3)]
    for s in sinks:                                                       # pouco espaço: vai encher no meio do caminho
        for i in range(C.CHEST_SLOTS - 2):
            s.storage.slots[i] = Stack("o2", 5)
    before = {r: total(game, r) for r in C.RESOURCES}
    for k in range(int(240 * 10)):
        game._update_machines(0.1)
        if k % 50 == 0:
            assert {r: total(game, r) for r in C.RESOURCES} == before
        if k == 900:                                                       # no meio, o player libera espaço
            for s in sinks:
                s.storage.slots[0] = None
    assert {r: total(game, r) for r in C.RESOURCES} == before
    assert sum(s.storage.count(r) for s in sinks for r in C.RESOURCES) > 0
    assert sources


# ---------------------------------------------------------------- drill como inventário
def test_drill_is_an_inventory_and_stops_when_full(game):
    d = drill(game, 70, 70, send=False)
    assert len(d.storage) == C.DRILL_SLOTS == 1
    game._update_drill(d, C.DRILL_INTERVAL * 25)
    assert d.stored == C.DRILL_CAPACITY == 20 and d.full
    assert d.storage.to_data() == [["iron", 20]]
    game._update_drill(d, C.DRILL_INTERVAL * 5)
    assert d.stored == 20                                                  # cheia, para
    d.storage.remove("iron", 5)
    game._update_drill(d, C.DRILL_INTERVAL * 2)
    assert d.stored == 17                                                  # tirou: volta a extrair


def test_take_from_the_drill_stack_one_or_all(game):
    d = drill(game, 70, 70, stored=12, send=False)
    assert game.drill_take(d, 0, 1) == 1 and d.stored == 11
    assert game.drill_take(d, 0) == 11 and d.stored == 0
    assert game.inventory.count("iron") == 12
    assert game.drill_collected["iron"] == 12                              # conta pro objetivo
    d.stored = 9
    assert game.collect(d) == 9 and d.stored == 0                          # Shift+E / Pegar tudo


def test_take_from_the_drill_with_full_inventory(game):
    d = drill(game, 70, 70, stored=12, send=False)
    for i in range(C.INVENTORY_SLOTS):
        game.inventory.slots[i] = Stack("silicon", 50)
    game.inventory.slots[0] = Stack("iron", 45)
    assert game.collect(d) == 5 and d.stored == 7
    assert ("inv_full",) in game.pop_events()


def test_drill_feeds_a_chest_with_the_real_update(game):
    add_station(game)
    d = drill(game, 75, 70, batch=5)
    c = chest(game, 58, 70, receives={"iron"})
    run(game, C.DRILL_INTERVAL * 5 + 15)
    assert c.storage.count("iron") >= 5 and game.drone_deliveries >= 1
    assert d.stored + c.storage.count("iron") + sum(x.cargo for x in game.stations[0].station.drones) >= 6


# ---------------------------------------------------------------- rótulo do baú
def test_chest_label_shows_receive_and_send():
    from game.ui import UI
    c = Machine("chest", 0, 0, name="Base", receives={"ice", "iron"}, sends={"silicon"})
    assert UI.chest_label_parts(c) == [("arrow", "down"), ("icon", "iron"), ("icon", "ice"),
                                       ("arrow", "up"), ("icon", "silicon"), ("text", "Base")]
    assert UI.chest_label_parts(Machine("chest", 0, 0, name="Base")) == [("text", "Base")]


# ---------------------------------------------------------------- save v5 e migração
def test_logistics_config_roundtrip(tmp_path):
    state = save.new_state()
    c = Machine("chest", 62, 68, name="Minério", receives={"iron", "silicon"}, sends={"ice"}, batch=5)
    c.storage.add("ice", 7)
    d = Machine("drill", 70, 70, resource="silicon", stored_init=13, sends={"silicon"}, batch=20, timer=3.5)
    quiet = Machine("drill", 80, 80, resource="ice")
    state.machines += [c, d, quiet]
    path = tmp_path / "slot1.json"
    assert save.write_save(state, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    md = next(m for m in data["layers"]["surface"]["machines"] if m["kind"] == "drill" and m["resource"] == "silicon")
    assert md["storage"] == [["silicon", 13]] and "stored" not in md
    assert md["sends"] == ["silicon"] and md["receives"] == [] and md["batch"] == 20
    loaded = save.load_game(path)
    lc = loaded.chests[0]
    assert (lc.receives, lc.sends, lc.batch, lc.storage.count("ice")) == ({"iron", "silicon"}, {"ice"}, 5, 7)
    ld, lq = loaded.drills
    assert (ld.sends, ld.receives, ld.batch, ld.stored, ld.timer) == ({"silicon"}, set(), 20, 13, 3.5)
    assert lq.sends == set() and lq.stored == 0


def test_load_sanitizes_logistics():
    data = save.state_to_dict(save.new_state())
    data["layers"]["surface"]["machines"] = [
        {"kind": "chest", "tx": 1, "ty": 1, "rotation": 0, "storage": [], "name": "x",
         "sends": ["iron", "o2", "bogus"], "receives": ["iron", "ice"], "batch": 7},
        {"kind": "drill", "tx": 5, "ty": 5, "rotation": 0, "resource": "ice", "timer": 0,
         "storage": [["ice", 99]], "sends": ["iron", "ice"], "receives": ["ice"], "batch": 1},
    ]
    state = save.state_from_dict(data)
    c, d = state.chests[0], state.drills[0]
    assert c.sends == {"iron"} and c.receives == {"ice"} and c.batch == C.DRONE_BATCH_DEFAULT
    assert d.sends == {"ice"} and d.receives == set() and d.batch == 1 and d.stored == C.DRILL_CAPACITY


