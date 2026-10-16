"""v0.6 Fundo M3: Fundição (minério + magmatita → lingote)."""

import random

import pytest

from game import config as C
from game import drones, save
from game.inventory import Stack, max_stack
from game.systems import GameState, Machine


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add_smelter(game, tile=(64, 70), ore=None, fuel_items=0, out=None, fuel=0, sends=("iron_ingot", "copper_ingot"),
                receives=(), chip=True) -> Machine:
    """Fundição na rede (com chip, por padrão). `ore`/`out` = (item, n); `fuel_items` = magmatita no slot."""
    m = Machine("smelter", *tile, sends=set(sends), receives=set(receives), chip=chip)
    if ore:
        m.storage.slots[C.SMELTER_ORE_SLOT] = Stack(*ore)
    if fuel_items:
        m.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", fuel_items)
    if out:
        m.storage.slots[C.SMELTER_OUT_SLOT] = Stack(*out)
    m.fuel = fuel
    game.machines.append(m)
    return m


def run(game, seconds, step=1 / 30):
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def test_registered_as_machine():
    t = C.MACHINES["smelter"]
    assert t.name == "Fundição" and t.placeable and t.index is None
    assert t.cost == {"iron": 15, "silicon": 6, "magmatite": 4} and t.unlock_ti == 10_000
    assert C.MACHINE_CATEGORY["smelter"] == "automation" and C.POWER_USE["smelter"] == 2
    assert "smelter" in C.MACHINE_ORDER and "smelter" in C.MACHINE_FEMININE


def test_copper_ingot_is_an_item_that_stacks_like_parts():
    item = C.MACHINES["copper_ingot"]
    assert item.name == "Lingote de cobre" and not item.placeable and item.sprite == "icon_copper_ingot"
    assert max_stack("copper_ingot") == max_stack("iron_ingot") == C.STACK_LOOT
    assert "copper_ingot" not in C.LOOT_COMMON and "copper_ingot" not in C.LOOT_CONTAINER   # não cai de loot


def test_three_slots_and_needs_chip():
    m = Machine("smelter", 5, 5)
    assert len(m.storage) == C.SMELTER_SLOTS and m.is_smelter and m.is_logistic and m.needs_chip
    assert not m.in_network and m.fuel == 0


def test_smelts_iron_and_burns_one_magmatite_per_four(game):
    m = add_smelter(game, ore=("iron", 10), fuel_items=2)
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("iron_ingot", 1)
    assert m.storage.count("magmatite") == 1 and m.fuel == C.SMELTER_BURNS_PER_FUEL - 1
    run(game, C.SMELTER_TIME * 4)
    assert m.storage.count("iron_ingot") == 5 and m.storage.count("iron") == 5
    assert m.storage.count("magmatite") == 0 and m.fuel == 3     # a 2ª magmatita acendeu no 5º lingote


def test_copper_makes_copper_ingot(game):
    m = add_smelter(game, ore=("copper", 3), fuel_items=1)
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("copper_ingot", 1)


def test_stops_without_fuel_and_keeps_progress(game):
    m = add_smelter(game, ore=("iron", 5), fuel=1)
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.count("iron_ingot") == 1 and m.fuel == 0
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("iron_ingot") == 1 and m.storage.count("iron") == 4   # parou: sem magmatita
    assert m.smelter_blocker == "no_fuel"


def test_does_not_burn_without_ore(game):
    m = add_smelter(game, fuel_items=3)
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("magmatite") == 3 and m.fuel == 0 and m.smelter_blocker == "no_ore"


def test_output_busy_with_other_ingot_stops(game):
    m = add_smelter(game, ore=("copper", 5), fuel_items=2, out=("iron_ingot", 3))
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("copper") == 5 and m.storage.count("magmatite") == 2
    assert m.smelter_blocker == "out_busy"


def test_output_full_stops(game):
    m = add_smelter(game, ore=("iron", 5), fuel_items=2, out=("iron_ingot", max_stack("iron_ingot")))
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("iron") == 5 and m.smelter_blocker == "out_full"


def test_power_deficit_slows_it(game):
    # déficit do mesmo jeito que o test_energy: máquinas que consomem a mais (cápsula 5 kW; 2 + 4 + 4 = 10 kW)
    game.machines += [Machine("heater_t2", 70, 70), Machine("heater_t2", 72, 70)]
    m = add_smelter(game, ore=("iron", 5), fuel_items=1)
    assert game.power.factor == pytest.approx(0.5)
    run(game, C.SMELTER_TIME + 0.5)                 # metade do ritmo: ainda não deu 15 s de trabalho
    assert m.storage.count("iron_ingot") == 0
    run(game, C.SMELTER_TIME)
    assert m.storage.count("iron_ingot") == 1


# ---------------------------------------------------------------- Task 2: drones, save e desmonte
def test_logistic_items_include_ingots():
    assert "iron_ingot" in C.LOGISTIC_ITEMS and "copper_ingot" in C.LOGISTIC_ITEMS


def test_drones_rules():
    m = Machine("smelter", 5, 5)
    assert drones.can_receive(m, "iron") and drones.can_receive(m, "copper") and drones.can_receive(m, "magmatite")
    assert drones.can_receive(m, "silicon") and not drones.can_receive(m, "iron_ingot")   # v0.6 Fundo M4: silício entra
    assert drones.can_send(m, "iron_ingot") and drones.can_send(m, "copper_ingot")
    assert not drones.can_send(m, "iron") and not drones.can_send(m, "magmatite")
    assert drones.receive_slot(m, "iron") == drones.receive_slot(m, "copper") == C.SMELTER_ORE_SLOT
    assert drones.receive_slot(m, "magmatite") == C.SMELTER_FUEL_SLOT


def test_deliver_ore_respects_other_ore_in_slot():
    m = Machine("smelter", 5, 5)
    m.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 4)
    assert drones.deliver(m, "copper", 5) == 5          # não mistura: o slot é do ferro
    assert drones.deliver(m, "iron", 5) == 0 and m.storage.count("iron") == 9
    assert drones.deliver(m, "magmatite", 3) == 0 and m.storage.slots[C.SMELTER_FUEL_SLOT] == Stack("magmatite", 3)


def test_save_roundtrip():
    m = Machine("smelter", 7, 8, sends={"copper_ingot"}, receives={"copper", "magmatite"}, chip=True)
    m.storage.slots[C.SMELTER_ORE_SLOT] = Stack("copper", 6)
    m.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 2)
    m.storage.slots[C.SMELTER_OUT_SLOT] = Stack("copper_ingot", 3)
    m.fuel, m.timer = 2, 7.5
    back = save.machine_from_dict(save.machine_to_dict(m))
    assert back.storage.slots == m.storage.slots and back.fuel == 2 and back.timer == 7.5
    assert back.sends == {"copper_ingot"} and back.receives == {"copper", "magmatite"} and back.chip


def test_save_cleans_bad_slots():
    data = {"kind": "smelter", "tx": 1, "ty": 1, "rotation": 0, "timer": 99, "fuel": 99,
            "storage": [["ice", 5], ["iron", 3], ["iron_ingot", 2]]}
    m = save.machine_from_dict(data)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] is None and m.storage.slots[C.SMELTER_FUEL_SLOT] is None
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("iron_ingot", 2)
    assert m.timer == C.SMELTER_TIME and m.fuel == C.SMELTER_BURNS_PER_FUEL


def test_dismantle_returns_contents_but_not_burning_fuel(game):
    m = add_smelter(game, ore=("iron", 3), fuel_items=2, out=("iron_ingot", 4), fuel=3)
    out = game.dismantle_returns(m)
    assert out["iron"] == 15 + 3 and out["magmatite"] == 4 + 2 and out["iron_ingot"] == 4 and out["chip"] == 1


# ---------------------------------------------------------------- Task 3: interface
def test_smelter_put_routes_by_item(game):
    m = add_smelter(game)
    game.inventory.slots[0] = Stack("copper", 10)
    game.inventory.slots[1] = Stack("magmatite", 4)
    game.inventory.slots[2] = Stack("iron", 5)
    game.inventory.slots[3] = Stack("silicon", 5)
    assert game.smelter_put(m, 0) == 10 and m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("copper", 10)
    assert game.smelter_put(m, 1, 1) == 1 and m.storage.slots[C.SMELTER_FUEL_SLOT] == Stack("magmatite", 1)
    assert game.smelter_put(m, 2) == 0                    # ferro com cobre na entrada: não mistura
    assert game.smelter_put(m, 3) == 0                    # silício não entra em lugar nenhum


def test_interaction_opens_smelter(game):
    m = add_smelter(game, tile=(64, 70))
    game.player.x, game.player.y = (64 + 0.5) * C.TILE, (70 + 1) * C.TILE + 20      # nos pés dela, como o test_polish_final
    x, y, w, h = m.sprite_rect
    assert game.nearby_smelter() is m
    assert game.interactable_at(x + w / 2, y + h / 2) == ("smelter", m)
    assert game.interaction() == ("smelter", m) and game.in_reach("smelter", m)
    m.build = 1.0                                         # ainda se construindo: não abre
    assert game.nearby_smelter() is None and game.interactable_at(x + w / 2, y + h / 2) is None
    m.build = 0.0
    game.player.x += 5 * C.TILE                           # longe: nem E nem o hover chegam nela
    assert game.nearby_smelter() is None and not game.in_reach("smelter", m)


def test_light_only_while_smelting(game):
    from game.render import cave_lights
    base = len(cave_lights(game))
    m = add_smelter(game)                                 # vazia: sem minério, apagada
    assert len(cave_lights(game)) == base
    m.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 2)
    m.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 1)
    assert len(cave_lights(game)) == base + 1             # fundindo: acende (laranja, como o aquecedor)
    m.storage.slots[C.SMELTER_FUEL_SLOT] = None
    assert len(cave_lights(game)) == base                 # sem combustível: apaga


# ---------------------------------------------------------------- som (Som, aprovado pelo dono)
def test_smelter_sound_volumes_by_distance():
    from game import audio as sound
    assert sound.smelter_loop_volume(1.0) == C.VOLUME["smelter_loop"] == 0.45
    assert sound.smelter_loop_volume(7.0) == 0.0 and 0 < sound.smelter_loop_volume(4.5) < 0.45
    assert sound.smelter_done_gain(2.0) == 1.0 and sound.smelter_done_gain(10.0) == 0.0
    assert (C.AUDIO_DIR / "smelter_loop.wav").exists() and (C.AUDIO_DIR / "smelter_done.wav").exists()


def test_each_ingot_emits_smelter_done_event(game):
    m = add_smelter(game, ore=("iron", 5), fuel_items=1)
    game.events.clear()
    run(game, C.SMELTER_TIME * 2 + 0.5)
    assert [e for e in game.events if e[0] == "smelter_done"] == [("smelter_done", m)] * 2


def test_chip_on_smelter_marks_nothing(game):
    """Dono (2026-10-16): pôr o chip na Fundição não liga Envia nem Recebe; o player escolhe."""
    m = add_smelter(game, sends=(), chip=False)
    assert game.chip_install(m) and m.chip and m.in_network
    assert m.sends == set() and m.receives == set()


# ---------------------------------------------------------------- v0.6 Fundo M4: silício vira wafer
def test_silicon_makes_wafer(game):
    m = add_smelter(game, ore=("silicon", 2), fuel_items=1)
    run(game, C.SMELTER_TIME * 2 + 1)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("silicon_wafer", 2)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] is None


def test_wafer_is_logistic_and_drones_route_silicon(game):
    m = add_smelter(game)
    assert "silicon_wafer" in C.LOGISTIC_ITEMS
    assert drones.can_send(m, "silicon_wafer") and drones.can_receive(m, "silicon")
    assert drones.receive_slot(m, "silicon") == C.SMELTER_ORE_SLOT


def test_save_keeps_silicon_and_wafer():
    data = {"kind": "smelter", "tx": 1, "ty": 1, "rotation": 0, "timer": 0, "fuel": 0,
            "storage": [["silicon", 3], None, ["silicon_wafer", 2]]}
    m = save.machine_from_dict(data)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("silicon", 3)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("silicon_wafer", 2)
