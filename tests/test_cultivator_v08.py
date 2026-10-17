"""v0.8 M3: o Cultivador (água, 4 etapas, perene, biomassa por segundo, colheita)."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import drones, ruins, save  # noqa: E402
from game.inventory import Inventory, Stack, max_stack  # noqa: E402
from game.systems import Machine  # noqa: E402
from tests.helpers import build_now  # noqa: E402
from tests.test_base import demo_base, free_spot, stand_at  # noqa: E402,F401
from tests.test_base import game  # noqa: E402,F401  (fixture)


def tick(state, seconds, step=1 / 30):
    """Só as máquinas (sem a chuva e o resto do update inteiro)."""
    for _ in range(round(seconds / step)):
        state._update_machines(step)


def plant(cult, crop="algae", water=5, tank=None):
    """Põe a muda e a reserva de água no Cultivador (e o tanque, se `tank`)."""
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack(crop, 1)
    if water:
        cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", water)
    if tank is not None:
        cult.tank = tank
    cult.sync_crop()


@pytest.fixture
def base_with_cultivator(game):
    """Base vedada 5×5 com o Dispersor soprando (água de sobra) e 1 Cultivador dentro. Devolve (state, cultivador)."""
    disp, x0, y0 = demo_base(game, w=5, h=5, water=5)
    cult = Machine(C.CULTIVATOR, x0 + 3, y0 + 2)
    game.machines.append(cult)
    assert game.in_breathing_base((cult.tx, cult.ty), game.active)
    return game, cult


# ---------------------------------------------------------------- registro
def test_cultivator_is_registered():
    t = C.MACHINES[C.CULTIVATOR]
    assert t.name == "Cultivador" and t.placeable and t.index is None and t.unlock_ti == 0
    assert t.cost == {"iron_ingot": 4, "silicon": 6, "ice": 4} and t.sprite == "machine_cultivator"
    assert C.POWER_USE[C.CULTIVATOR] == 1 and C.MACHINE_CATEGORY[C.CULTIVATOR] == "automation"
    assert C.MACHINE_ORDER.index(C.CULTIVATOR) == C.MACHINE_ORDER.index(C.COLLECTOR) + 1
    assert (C.CULT_WATER_SLOT, C.CULT_EMPTY_SLOT, C.CULT_SEED_SLOT, C.CULT_HARVEST_SLOTS, C.CULT_SLOTS) == \
        (0, 1, 2, (3, 4, 5, 6), 7)
    assert C.CULTIVATOR_TANK == 5.0 and C.CROP_ITEMS == ("algae", "plant_1", "plant_2", "plant_3")
    assert C.CROPS["algae"] == C.Crop(0.5, 120.0, 90.0) and C.CROPS["plant_3"] == C.Crop(10.0, 45.0, 180.0)
    assert (C.CROPS["plant_1"].biomass, C.CROPS["plant_2"].water_s, C.CROPS["plant_2"].cycle) == (1.5, 60.0, 150.0)


def test_cultivator_needs_the_diagram_then_can_be_built(game):
    x0, y0 = free_spot(game, 4, 4)
    stand_at(game, x0 + 1, y0 + 1)
    assert game.recipe_status(C.CULTIVATOR) == "blueprint" and build_now(game, C.CULTIVATOR, (x0, y0)) is None
    game.blueprints.add(C.CULTIVATOR)
    m = build_now(game, C.CULTIVATOR, (x0, y0))
    assert m is not None and m.is_cultivator and len(m.storage) == C.CULT_SLOTS and m.is_logistic and m.needs_chip
    assert m.tank == 0.0 and m.growth == 0.0 and m.crop is None
    assert game.power.consumption >= 1


# ---------------------------------------------------------------- crescer
def test_algae_grows_through_4_stages_in_a_sealed_base(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=5)
    stages = set()
    for _ in range(int(C.CROPS["algae"].cycle / 0.5) - 2):
        tick(state, 0.5)
        stages.add(cult.crop_stage)
    assert stages == {0, 1, 2}                                     # ainda não amadureceu aos 89 s
    assert sum(cult.storage.slots[s].count for s in C.CULT_HARVEST_SLOTS if cult.storage.slots[s]) == 0
    tick(state, 2.0)
    harvest = sum(cult.storage.slots[s].count for s in C.CULT_HARVEST_SLOTS
                  if cult.storage.slots[s] and cult.storage.slots[s].item == "algae")
    assert harvest in (1, 2)                                       # 1 ou 2 de colheita
    assert cult.storage.slots[C.CULT_SEED_SLOT] == Stack("algae", 1)   # a muda fica: é perene
    assert cult.crop_stage == 1                                    # voltou pra "pequena"
    harvests = [e for e in state.events if e[0] == "harvest"]
    assert len(harvests) == 1 and harvests[0][1:] == (cult, "algae", harvest)


@pytest.mark.parametrize("growth, stage", [(0.0, 0), (0.32, 0), (1 / 3, 1), (0.66, 1), (2 / 3, 2), (0.99, 2), (1.0, 3)])
def test_crop_stage_thresholds(growth, stage):
    cult = Machine(C.CULTIVATOR, 0, 0)
    cult.growth = growth
    assert cult.crop_stage == stage


def test_biomass_per_second(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    before = state.indices["biomass"]
    tick(state, 10.0)
    assert state.indices["biomass"] - before == pytest.approx(10.0 * C.CROPS["algae"].biomass, rel=0.02)


def test_each_crop_uses_its_own_rate(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, "plant_2")
    before = state.indices["biomass"]
    tick(state, 10.0)
    assert state.indices["biomass"] - before == pytest.approx(10.0 * C.CROPS["plant_2"].biomass, rel=0.02)


def test_outside_the_base_it_does_not_grow(game):
    x0, y0 = free_spot(game, 4, 4)
    stand_at(game, x0 + 1, y0 + 1)
    game.blueprints.add(C.CULTIVATOR)
    cult = build_now(game, C.CULTIVATOR, (x0, y0))
    plant(cult)
    assert game.cultivator_blocker(cult, game.active) == "no_base"
    before = game.indices["biomass"]
    tick(game, 5.0)
    assert cult.growth == 0.0 and game.indices["biomass"] == before and cult.grow_blocker == "no_base"


def test_a_dispenser_without_water_is_not_a_base(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    disp = next(m for m in state.machines if m.is_dispenser)
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = None
    disp.burn = 0.0
    assert state.cultivator_blocker(cult, state.active) == "no_base"


def test_without_the_seed_nothing_happens(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 3)
    tick(state, 5.0)
    assert state.cultivator_blocker(cult, state.active) == "no_seed" and cult.tank == 0.0
    assert cult.storage.count("water_capsule") == 3                # nem puxa água sem planta


# ---------------------------------------------------------------- água
def test_water_is_injected_and_leaves_an_empty(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=3)
    tick(state, 0.1)
    assert cult.tank == pytest.approx(3.0, abs=0.01)               # as 3 cápsulas entraram (o tanque nasce vazio)
    assert cult.storage.count("water_capsule") == 0 and cult.storage.count(C.EMPTY_CAPSULE) == 3


def test_the_tank_never_goes_over_5_and_pulls_one_at_a_time(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=5, tank=0.0)
    tick(state, 0.1)
    assert cult.tank == pytest.approx(C.CULTIVATOR_TANK, abs=0.01) and cult.storage.count("water_capsule") == 0
    plant(cult, water=2)
    cult.tank = 4.6                                                 # ainda sobra mais de 1 de espaço? não: só 0,4
    tick(state, 0.1)
    assert cult.storage.count("water_capsule") == 2                 # não puxa: tem menos de 1 cápsula de espaço
    cult.tank = 3.9
    tick(state, 0.1)
    assert cult.storage.count("water_capsule") == 1 and cult.tank == pytest.approx(4.9, abs=0.01)


def test_tank_drains_at_the_crop_rate(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, "plant_3", water=0, tank=5.0)
    tick(state, 9.0)
    assert cult.tank == pytest.approx(5.0 - 9.0 / C.CROPS["plant_3"].water_s, abs=0.01)


def test_empty_slot_full_drops_the_empty_capsule(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, max_stack(C.EMPTY_CAPSULE))
    plant(cult, water=2)
    tick(state, 0.1)
    assert cult.storage.count(C.EMPTY_CAPSULE) == max_stack(C.EMPTY_CAPSULE) and cult.tank == pytest.approx(2.0, abs=0.01)


def test_dry_stops_growth_and_biomass(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=0, tank=0.0)
    before, g = state.indices["biomass"], cult.growth
    tick(state, 5.0)
    assert state.cultivator_blocker(cult, state.active) == "dry"
    assert state.indices["biomass"] == before and cult.growth == g
    assert cult.crop == "algae"                                     # a planta não morre
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 1)    # chegou água: volta a crescer
    tick(state, 1.0)
    assert cult.growth > g and state.indices["biomass"] > before


def test_runs_dry_in_the_middle_and_stops_exactly(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=0, tank=0.5)                                  # 0,5 cápsula = 60 s de alga
    tick(state, 100.0)
    assert cult.growth == pytest.approx(60.0 / C.CROPS["algae"].cycle, abs=0.01) and cult.tank == 0.0
    assert state.indices["biomass"] == pytest.approx(60.0 * C.CROPS["algae"].biomass, rel=0.02)


# ---------------------------------------------------------------- colheita
def test_full_harvest_holds_the_plant_mature(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    for s in C.CULT_HARVEST_SLOTS:
        cult.storage.slots[s] = Stack("algae", max_stack("algae"))
    cult.growth = 0.999
    tick(state, 1.0)
    assert cult.crop_stage == 3 and cult.growth == 1.0 and state.cultivator_blocker(cult, state.active) == "full"
    biomass, tank = state.indices["biomass"], cult.tank
    tick(state, 5.0)                                                # parada: sem água e sem biomassa
    assert state.indices["biomass"] == biomass and cult.tank == tank
    cult.storage.slots[C.CULT_HARVEST_SLOTS[0]] = None              # alguém esvaziou um slot
    tick(state, 0.1)
    assert cult.growth < 1.0 and cult.storage.count("algae") > 3 * max_stack("algae") + 1   # colheu e voltou a crescer


def test_part_of_the_harvest_that_does_not_fit_is_lost(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    for s in C.CULT_HARVEST_SLOTS:
        cult.storage.slots[s] = Stack("algae", max_stack("algae"))
    cult.storage.slots[C.CULT_HARVEST_SLOTS[0]].count -= 1          # cabe só 1
    cult.growth = 1.0
    tick(state, 0.1)
    harvest = sum(cult.storage.slots[i].count for i in C.CULT_HARVEST_SLOTS)
    assert harvest == 4 * max_stack("algae") and cult.growth == pytest.approx(1 / 3, abs=0.01)
    assert [e for e in state.events if e[0] == "harvest"][0][3] == 1


def test_harvest_is_deterministic_with_the_state_rng():
    from game.systems import GameState
    counts = []
    for _ in range(2):
        state = GameState(rng=random.Random(11))
        cult = Machine(C.CULTIVATOR, 0, 0)
        plant(cult)
        got = []
        for _ in range(8):
            cult.growth = 1.0
            state._cultivator_harvest(cult)
            got.append(cult.storage.count("algae"))
        counts.append(got)
    assert counts[0] == counts[1] and set(counts[0][0:1]) <= {1, 2}


def test_removing_the_seed_resets_growth(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    tick(state, 20.0)
    assert cult.growth > 0.2
    cult.storage.slots[C.CULT_SEED_SLOT] = None
    tick(state, 0.1)
    assert cult.growth == 0.0 and cult.crop is None and state.cultivator_blocker(cult, state.active) == "no_seed"


def test_taking_the_seed_through_the_state_also_resets(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    tick(state, 20.0)
    assert state.melter_take(cult, C.CULT_SEED_SLOT) == 1 and cult.growth == 0.0 and state.inventory.count("algae") == 1


def test_swapping_the_crop_restarts_the_plant(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    tick(state, 20.0)
    state.inventory.add("plant_1", 1)
    index = next(i for i, s in enumerate(state.inventory.slots) if s and s.item == "plant_1")
    assert state.cultivator_put(cult, index) == 1
    assert cult.crop == "plant_1" and cult.growth == 0.0 and state.inventory.count("algae") == 1   # a antiga voltou


def test_no_power_nothing_moves(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    state.machines.extend(Machine(C.CULTIVATOR, 1 + i, 1) for i in range(1, 9))     # consumo > geração: o fator cai
    factor = state.power.factor
    assert 0 < factor < 1.0
    before = state.indices["biomass"]
    tick(state, 10.0)
    assert state.indices["biomass"] - before == pytest.approx(10.0 * factor * C.CROPS["algae"].biomass, rel=0.02)


# ---------------------------------------------------------------- put / logística / sobrevivência
def test_only_crop_items_go_in_the_seed_slot(base_with_cultivator):
    state, cult = base_with_cultivator
    state.inventory.slots[0] = Stack("iron", 4)
    state.inventory.slots[1] = Stack("algae", 3)
    state.inventory.slots[2] = Stack("water_capsule", 5)
    state.inventory.slots[3] = Stack(C.EMPTY_CAPSULE, 2)
    assert state.cultivator_put(cult, 0) == 0 and state.cultivator_put(cult, 3) == 0   # ferro e vazia: recusa
    assert state.cultivator_put(cult, 1) == 1                       # a muda é uma só, mesmo com 3 na mão
    assert cult.storage.slots[C.CULT_SEED_SLOT] == Stack("algae", 1) and state.inventory.slots[1].count == 2
    assert state.cultivator_put(cult, 1) == 0                       # a mesma já está lá
    assert state.cultivator_put(cult, 2, 1) == 1 and state.cultivator_put(cult, 2) == 4
    assert cult.storage.slots[C.CULT_WATER_SLOT] == Stack("water_capsule", 5) and state.inventory.slots[2] is None


def test_swap_without_room_changes_nothing(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult)
    state.inventory.slots[:] = [Stack("iron", 1) for _ in state.inventory.slots]
    state.inventory.slots[0] = Stack("plant_1", 2)                  # a pilha não esvazia: a antiga muda não tem onde ficar
    assert state.cultivator_put(cult, 0) == 0
    assert cult.crop == "algae" and state.inventory.slots[0] == Stack("plant_1", 2) and ("inv_full",) in state.events
    state.inventory.slots[0] = Stack("plant_1", 1)                  # a pilha esvazia: o lugar dela serve pra antiga
    assert state.cultivator_put(cult, 0) == 1 and cult.crop == "plant_1" and state.inventory.slots[0] == Stack("algae", 1)


def test_take_all_never_takes_the_seed_or_the_water(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=3)
    cult.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    cult.storage.slots[C.CULT_HARVEST_SLOTS[1]] = Stack("algae", 4)
    assert state.cultivator_take_all(cult) == 6
    assert cult.storage.slots[C.CULT_SEED_SLOT] is not None and cult.storage.count("water_capsule") == 3
    assert state.inventory.count("algae") == 4 and state.inventory.count(C.EMPTY_CAPSULE) == 2


def test_cultivator_logistics():
    m = Machine(C.CULTIVATOR, 0, 0, chip=True)
    assert m.is_logistic and m.needs_chip and m.in_network
    assert drones.can_receive(m, "water_capsule") and drones.receive_slot(m, "water_capsule") == C.CULT_WATER_SLOT
    assert not drones.can_receive(m, "algae") and not drones.can_receive(m, C.EMPTY_CAPSULE) and not drones.can_receive(m, "iron")
    assert drones.can_send(m, C.EMPTY_CAPSULE) and all(drones.can_send(m, c) for c in C.CROP_ITEMS)
    assert not drones.can_send(m, "water_capsule") and not drones.can_send(m, "iron")


def test_drones_never_take_the_seed(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=3)
    cult.storage.slots[C.CULT_HARVEST_SLOTS[2]] = Stack("algae", 2)
    assert drones.stock(cult, "algae") == 2                         # a muda (slot 2) não conta
    assert drones.pick_up(cult, "algae", 5) == 2
    assert cult.storage.slots[C.CULT_SEED_SLOT] == Stack("algae", 1)
    cult.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 3)
    assert drones.stock(cult, C.EMPTY_CAPSULE) == 3 and drones.pick_up(cult, C.EMPTY_CAPSULE, 2) == 2
    assert drones.stock(cult, "water_capsule") == 0                 # a reserva não sai


def test_drones_fill_the_water_reserve(base_with_cultivator):
    state, cult = base_with_cultivator
    assert drones.slot_room(cult.storage, C.CULT_WATER_SLOT, "water_capsule") == 5
    assert drones.deliver(cult, "water_capsule", 7) == 2            # só cabem 5 na reserva
    assert cult.storage.slots[C.CULT_WATER_SLOT] == Stack("water_capsule", 5)


def test_cultivator_dismantle_returns_contents(base_with_cultivator):
    state, cult = base_with_cultivator
    plant(cult, water=2, tank=3.4)
    cult.storage.slots[C.CULT_HARVEST_SLOTS[0]] = Stack("algae", 3)
    cult.chip = True
    out = state.dismantle_returns(cult)
    assert out["iron_ingot"] == 4 and out["silicon"] == 6 and out["ice"] == 4
    assert out["algae"] == 4 and out["water_capsule"] == 2 + 3 and out["chip"] == 1


def test_interaction_opens_the_cultivator(game):
    cult = Machine(C.CULTIVATOR, 64, 70)
    game.machines.append(cult)
    game.player.x, game.player.y = (64 + 0.5) * C.TILE, (70 + 1) * C.TILE + 20
    x, y, w, h = cult.sprite_rect
    assert game.nearby_cultivator() is cult
    assert game.interactable_at(x + w / 2, y + h / 2) == ("cultivator", cult)
    assert game.interaction() == ("cultivator", cult) and game.in_reach("cultivator", cult)
    cult.build = 1.0
    assert game.nearby_cultivator() is None
    cult.build = 0.0
    game.player.x += 5 * C.TILE
    assert game.nearby_cultivator() is None and not game.in_reach("cultivator", cult)


# ---------------------------------------------------------------- Task 5: desenho no mundo
from game.render import cave_lights, cultivator_layers  # noqa: E402
from tests.test_base_app import app, fresh  # noqa: E402,F401  (fixtures)


def test_cultivator_layers_names():
    m = Machine(C.CULTIVATOR, 3, 3)
    assert cultivator_layers(m, "no_seed") == ["machine_cultivator"]
    plant(m, "algae", water=0)
    m.growth = 0.7
    assert m.crop_stage == 2
    assert cultivator_layers(m, None) == ["machine_cultivator", "cultivator_crop_algae_2"]
    assert cultivator_layers(m, "full") == ["machine_cultivator", "cultivator_crop_algae_2"]
    assert cultivator_layers(m, "dry") == ["machine_cultivator_dry", "cultivator_crop_algae_2"]    # o miolo aparece seco também
    m.growth = 1.0
    plant(m, "plant_3", water=0)
    assert cultivator_layers(m, None)[1] == "cultivator_crop_plant_3_0"                            # trocou a muda: recomeça


def test_cultivator_art_is_in_assets_and_has_the_machine_size():
    from pathlib import Path
    sprites = Path("assets/sprites")
    names = ["machine_cultivator", "machine_cultivator_dry", "machine_cultivator_broken", "machine_microscope_broken",
             *(f"cultivator_crop_{c}_{i}" for c in C.CROP_ITEMS for i in range(4)), "anim/anim_machine_cultivator"]
    for name in names:
        assert (sprites / f"{name}.png").exists(), name
    for item in ("cultivator", *C.CROP_ITEMS):
        assert (sprites / f"icon_{item}.png").exists(), item


def test_cultivator_is_drawn_still_animated_or_dry(fresh):
    r = fresh.renderer
    m = Machine(C.CULTIVATOR, 3, 3)
    plant(m, "algae", water=0)
    m.growth = 0.5
    r.machine_t = 0.0
    m.grow_blocker = "dry"
    body, crop = r.cultivator_surfaces(m, True)
    assert body is r.sprites.get("machine_cultivator_dry") and crop is r.sprites.get("cultivator_crop_algae_1")
    m.grow_blocker = "no_base"
    assert r.cultivator_surfaces(m, True)[0] is r.sprites.get("machine_cultivator")           # parado: o sprite parado
    m.grow_blocker = None
    assert r.cultivator_surfaces(m, False)[0] is r.sprites.get("machine_cultivator")          # sem energia: parado
    frames = set()
    for r.machine_t in (0.0, 0.2, 0.4, 0.6):
        frames.add(id(r.cultivator_surfaces(m, True)[0]))
    assert len(frames) > 1                                                                     # crescendo: anda na tira
    assert all(s.get_size() == (40, 56) for s in r.cultivator_surfaces(m, True))


def test_cultivator_draws_on_the_canvas(fresh):
    import pygame
    r = fresh.renderer
    m = Machine(C.CULTIVATOR, 3, 3)
    plant(m, "algae", water=0)
    canvas = pygame.Surface((80, 80), pygame.SRCALPHA)
    r.draw_cultivator(canvas, m, 40, 70)
    assert pygame.mask.from_surface(canvas).count() > 100


def test_cultivator_light_only_while_growing(game):
    base = len(cave_lights(game))
    cult = Machine(C.CULTIVATOR, 70, 70)
    game.machines.append(cult)
    assert len(cave_lights(game)) == base                      # sem muda: apagado (grow_blocker = no_seed)
    cult.grow_blocker = None
    assert len(cave_lights(game)) == base + 1


# ---------------------------------------------------------------- Task 6: painel (UI A)
from game.app import PANEL_MODES  # noqa: E402


def open_panel(app, m):
    app.open_cultivator = m
    app.set_mode("cultivator")


def test_cultivator_panel_modes_and_status(fresh):
    s = fresh.state
    x0, y0 = free_spot(s, 8, 7)
    disp, bx, by = demo_base(s, w=5, h=5, water=5)
    m = Machine(C.CULTIVATOR, bx + 3, by + 2)
    s.machines.append(m)
    open_panel(fresh, m)
    assert fresh.mode == "cultivator" and fresh.mode in PANEL_MODES
    assert fresh.cultivator_status() == "Sem muda"
    plant(m, "algae", water=0, tank=3.0)
    assert fresh.cultivator_status() == "Crescendo"
    m.storage.slots[C.CULT_SEED_SLOT] = Stack("plant_1", 1)
    assert fresh.cultivator_status() == "Crescendo" and m.growth == 0.0                    # trocou a muda: zera
    m.tank = 0.0
    assert fresh.cultivator_status() == "Sem água"
    m.tank, m.growth = 2.0, 1.0
    for slot in C.CULT_HARVEST_SLOTS:
        m.storage.slots[slot] = Stack("plant_1", max_stack("plant_1"))
    assert fresh.cultivator_status() == "Colheita cheia"
    s.machines.remove(disp)                                                                  # sem Dispersor soprando
    assert fresh.cultivator_status() == "Fora da base vedada"
    fresh.set_mode("play")
    assert fresh.open_cultivator is None


def test_cultivator_panel_refusals(fresh):
    s = fresh.state
    m = Machine(C.CULTIVATOR, 70, 70)
    s.machines.append(m)
    open_panel(fresh, m)
    st = m.storage
    assert fresh.panel_refusal(st, C.CULT_WATER_SLOT, "water_capsule") is None
    assert fresh.panel_refusal(st, C.CULT_WATER_SLOT, C.EMPTY_CAPSULE) is not None
    assert fresh.panel_refusal(st, C.CULT_SEED_SLOT, "algae") is None and fresh.panel_refusal(st, C.CULT_SEED_SLOT, "plant_3") is None
    assert fresh.panel_refusal(st, C.CULT_SEED_SLOT, "iron") is not None
    assert fresh.panel_refusal(st, C.CULT_SEED_SLOT, "water_capsule") is not None
    assert fresh.panel_refusal(st, C.CULT_EMPTY_SLOT, C.EMPTY_CAPSULE) is not None          # vazias só saem
    for slot in C.CULT_HARVEST_SLOTS:
        assert fresh.panel_refusal(st, slot, "algae") is not None                          # colheita só sai
    fresh.set_mode("play")


def test_cultivator_panel_held_seed_is_one_at_a_time(fresh):
    s = fresh.state
    m = Machine(C.CULTIVATOR, 70, 70)
    s.machines.append(m)
    open_panel(fresh, m)
    fresh.held = Stack("algae", 3)
    assert fresh.panel_put(m.storage, C.CULT_SEED_SLOT, 1)
    assert m.storage.slots[C.CULT_SEED_SLOT] == Stack("algae", 1) and fresh.held == Stack("algae", 2)
    assert not fresh.panel_put(m.storage, C.CULT_SEED_SLOT, 1)                              # a mesma: nada muda
    fresh.held = Stack("plant_1", 2)
    assert not fresh.panel_put(m.storage, C.CULT_SEED_SLOT, 1) and m.crop == "algae"        # troca com pilha > 1: recusa
    fresh.held = Stack("plant_1", 1)
    m.growth = 0.5
    assert fresh.panel_put(m.storage, C.CULT_SEED_SLOT, 1)
    assert m.crop == "plant_1" and fresh.held == Stack("algae", 1) and m.growth == 0.0      # trocou: a antiga no cursor
    fresh.held = None
    assert fresh.panel_put(m.storage, C.CULT_SEED_SLOT, 1) and fresh.held == Stack("plant_1", 1) and m.crop is None
    fresh.held = None
    fresh.set_mode("play")


def test_cultivator_panel_take_all_button(fresh):
    s = fresh.state
    m = Machine(C.CULTIVATOR, 70, 70)
    s.machines.append(m)
    plant(m, "algae", water=2)
    m.storage.slots[C.CULT_HARVEST_SLOTS[0]] = Stack("algae", 3)
    m.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    open_panel(fresh, m)
    fresh.on_panel_button("take_cultivator")
    assert s.inventory.count("algae") == 3 and s.inventory.count(C.EMPTY_CAPSULE) == 1
    assert m.crop == "algae" and m.storage.count("water_capsule") == 2
    fresh.set_mode("play")


def test_cultivator_panel_draws_and_has_the_drone_section(fresh):
    import pygame
    s = fresh.state
    m = Machine(C.CULTIVATOR, 70, 70, chip=True)
    s.machines.append(m)
    plant(m, "algae", water=2, tank=3.0)
    m.growth = 0.55
    m.storage.slots[C.CULT_HARVEST_SLOTS[0]] = Stack("algae", 2)
    open_panel(fresh, m)
    ui = fresh.ui
    ui.cultivator_art = fresh.renderer.cultivator_surfaces(m, True)
    ui.begin()
    ui.draw_inventory(s.inventory, m, 0, fresh.renderer.item_icon, (0, 0), 0.0, None, fresh.cultivator_status(), None)
    assert len(ui.logistics_buttons) == len([i for i in C.LOGISTIC_ITEMS if drones.can_send(m, i)]) + \
        len([i for i in C.LOGISTIC_ITEMS if drones.can_receive(m, i)]) + len(C.DRONE_BATCH_OPTIONS)
    assert {kind for _, (kind, *_x) in ui.logistics_buttons} == {"send", "recv", "batch"}
    fresh.set_mode("play")


def test_chest_toggles_wrap_with_the_crops(fresh):
    """O baú passou de 8 materiais (v0.8 M4: 16, com as amostras): os botões quebram em linhas de 8 e continuam dentro da grade."""
    from game import ui as ui_mod
    chest = Machine("chest", 70, 70)
    n = len(C.LOGISTIC_ITEMS)
    assert n == 16 and ui_mod.wide_row_height(8) == ui_mod.LOGI_WIDE_ROW
    ui = fresh.ui
    ui.begin()
    ui.logistics_buttons.clear()
    ui.draw_logistics(0, 0, ui_mod.GRID_W, chest, fresh.renderer.item_icon, (0, 0))
    rects = [r for r, (kind, *_x) in ui.logistics_buttons if kind in ("send", "recv")]
    assert len(rects) == 2 * n and all(r.right <= ui_mod.GRID_W for r in rects)
    assert ui.logistics_height(chest) >= 14 + 2 * ui_mod.wide_row_height(n)
    assert len({r.y for r in rects}) == 4                                                    # 2 linhas de botões por fileira


def test_harvest_event_shows_a_floater(fresh):
    s = fresh.state
    m = Machine(C.CULTIVATOR, 70, 70)
    s.machines.append(m)
    fresh.floaters.items.clear()
    fresh.on_game_event(("harvest", m, "algae", 2))
    assert [f.text for f in fresh.floaters.items] == ["+2 ALGA"]
    fresh.on_game_event(("harvest", m, "algae", 0))                 # nada coube: sem aviso
    assert len(fresh.floaters.items) == 1


# ---------------------------------------------------------------- Task 7: save v16
def test_save_version_16_and_migration():
    assert save.SAVE_VERSION >= 16 and 15 in save.MIGRATIONS
    data = {"version": 15, "x": 1}
    assert save.MIGRATIONS[15](dict(data)) == {**data, "_lab_algae": True}      # só a marca da alga do lab
    assert save.migrate({"version": 15, "layers": {}})["version"] == save.SAVE_VERSION


def test_cultivator_save_roundtrip():
    m = Machine(C.CULTIVATOR, 7, 8, sends={"algae"}, receives={"water_capsule"}, chip=True)
    m.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    m.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    m.storage.slots[C.CULT_HARVEST_SLOTS[0]] = Stack("algae", 3)
    m.growth, m.tank = 0.55, 3.4
    assert m.crop_stage == 1
    data = save.machine_to_dict(m)
    assert data["growth"] == 0.55 and data["tank"] == 3.4 and len(data["storage"]) == C.CULT_SLOTS
    back = save.machine_from_dict(data)
    assert back.storage.slots == m.storage.slots and back.growth == 0.55 and back.tank == 3.4
    assert back.crop == "algae" and back.crop_stage == 1 and back.chip and back.grow_crop == "algae"
    assert back.sends == {"algae"} and back.receives == {"water_capsule"}


def test_cultivator_save_plant_in_stage_2_with_everything():
    m = Machine(C.CULTIVATOR, 7, 8)
    m.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    m.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    m.storage.slots[C.CULT_HARVEST_SLOTS[0]] = Stack("algae", 3)
    m.growth, m.tank = 0.7, 3.4
    back = save.machine_from_dict(save.machine_to_dict(m))
    assert back.crop_stage == 2 and back.tank == 3.4 and back.storage.count("water_capsule") == 2
    assert back.storage.count(C.EMPTY_CAPSULE) == 1 and back.storage.count("algae") == 4


def test_cultivator_save_cleans_bad_data():
    data = {"kind": C.CULTIVATOR, "tx": 1, "ty": 1, "rotation": 0, "growth": 7.0, "tank": 99,
            "storage": [["algae", 3], ["water_capsule", 2], ["iron", 4], ["plant_1", 99], ["iron", 2], ["algae", -1], None]}
    m = save.machine_from_dict(data)
    assert m.storage.slots == [None, None, None, Stack("plant_1", max_stack("plant_1")), None, None, None]
    assert m.growth == 0.0 and m.tank == C.CULTIVATOR_TANK                   # sem muda: a planta não existe
    data["storage"] = [None, None, ["algae", 9]]
    m = save.machine_from_dict({**data, "growth": 7.0})
    assert m.storage.slots[C.CULT_SEED_SLOT] == Stack("algae", 1) and m.growth == 1.0   # muda é 1; growth no teto
    assert save.machine_from_dict({"kind": C.CULTIVATOR, "tx": 1, "ty": 1, "rotation": 0}).storage.is_empty()


def test_cultivator_survives_a_full_state_roundtrip(game):
    disp, x0, y0 = demo_base(game, w=5, h=5, water=2)
    cult = Machine(C.CULTIVATOR, x0 + 3, y0 + 2)
    plant(cult, "plant_1", water=0, tank=2.5)
    cult.growth = 0.4
    game.machines.append(cult)
    game.blueprints.add(C.CULTIVATOR)
    back = save.state_from_dict(save.migrate(save.state_to_dict(game)))
    loaded = next(m for m in back.machines if m.is_cultivator)
    assert (loaded.crop, loaded.growth, loaded.tank) == ("plant_1", 0.4, 2.5) and C.CULTIVATOR in back.blueprints
    assert back.recipe_status(C.CULTIVATOR) != "blueprint"
    tick(back, 1.0)
    assert loaded.growth > 0.4                                                  # e volta a crescer sem zerar


def test_lab_ice_is_rebuilt_from_the_heat_after_a_real_load():
    g = save.new_state(7)
    assert ruins.lab_of(g.world) is not None
    g.indices["heat"] = C.LAB_ICE_HEAT[1]
    g._apply_thaw()
    assert g.active.lab_ice_open
    data = save.state_to_dict(g)
    assert "lab_ice_p" not in str(data["layers"]["surface"].keys())             # derivado: nada no save
    back = save.state_from_dict(save.migrate(data))
    assert back.surface.lab_ice_open and back.surface.lab_ice_p == 1.0 and ("lab_ice_open",) not in back.events


# ---------------------------------------------------------------- v15 -> v16: a alga na caixa do lab já saqueada
def _lab_crate(state):
    return state.surface.crates[ruins.lab_of(state.surface.world).crate]


def _v15_save_with_lab_crate(looted: bool) -> dict:
    """Um save v15 de verdade: gera o estado, esvazia (ou não toca) a caixa do lab e tira a alga que o v16 põe."""
    g = save.new_state(7)
    crate = _lab_crate(g)
    if looted:
        crate.storage = Inventory(C.CRATE_SLOTS)
        crate.opened = True
    else:
        crate.storage.remove("algae", 1)         # (a do v15 nunca teve; sem mexer, a caixa não vai no save)
    data = save.state_to_dict(g)
    data["version"] = 15
    return data


def test_v15_looted_lab_crate_gets_one_algae():
    data = _v15_save_with_lab_crate(looted=True)
    lab = ruins.lab_of(save.new_state(7).surface.world)
    assert any((x, y) == lab.crate for x, y, *_ in data["layers"]["surface"]["crates"])
    back = save.state_from_dict(save.migrate(data))
    assert _lab_crate(back).storage.count("algae") == 1 and _lab_crate(back).storage.to_data().count(None) == C.CRATE_SLOTS - 1


def test_v15_without_the_lab_crate_in_the_save_loads_the_seed_crate_with_algae():
    g = save.new_state(7)
    data = save.state_to_dict(g)
    data["layers"]["surface"]["crates"] = [c for c in data["layers"]["surface"]["crates"]
                                           if (c[0], c[1]) != ruins.lab_of(g.surface.world).crate]
    data["version"] = 15
    back = save.state_from_dict(save.migrate(data))
    assert _lab_crate(back).storage.count("algae") == 1


def test_v15_full_lab_crate_changes_nothing():
    data = _v15_save_with_lab_crate(looted=True)
    lab = ruins.lab_of(save.new_state(7).surface.world)
    row = next(c for c in data["layers"]["surface"]["crates"] if (c[0], c[1]) == lab.crate)
    row[2] = [["iron", 20] for _ in range(C.CRATE_SLOTS)]
    back = save.state_from_dict(save.migrate(data))
    assert _lab_crate(back).storage.count("algae") == 0


def test_v16_roundtrip_does_not_add_more_algae():
    data = _v15_save_with_lab_crate(looted=True)
    once = save.state_from_dict(save.migrate(data))
    assert _lab_crate(once).storage.count("algae") == 1
    saved = save.state_to_dict(once)
    assert "_lab_algae" not in saved and saved["version"] == save.SAVE_VERSION
    twice = save.state_from_dict(save.migrate(saved))
    assert _lab_crate(twice).storage.count("algae") == 1
    _lab_crate(twice).storage.remove("algae", 1)                      # o jogador tirou: um v16 não devolve
    again = save.state_from_dict(save.migrate(save.state_to_dict(twice)))
    assert _lab_crate(again).storage.count("algae") == 0


def test_cultivator_send_row_does_not_run_under_the_chip(fresh):
    """O Cultivador manda 5 itens e tem chip: o 5º botão do Envia ficava debaixo do slot do chip (print do dono)."""
    from game import ui as ui_mod
    m = Machine(C.CULTIVATOR, 70, 70, chip=True)
    ui = fresh.ui
    ui.begin()
    ui.logistics_buttons.clear()
    ui.chip_rects.clear()
    ui.draw_logistics(0, 0, ui_mod.GRID_W, m, fresh.renderer.item_icon, (0, 0))
    chip = ui.chip_rects[0][0].inflate(0, 10)                                    # o slot e a legenda CHIP embaixo
    rects = [r for r, (kind, *_x) in ui.logistics_buttons if kind in ("send", "recv")]
    assert rects and not any(r.colliderect(chip) for r in rects)
    assert all(r.right <= ui_mod.GRID_W for r in rects)
    bottom = max(r.bottom for r, _ in ui.logistics_buttons)
    assert bottom <= ui.logistics_height(m)                                      # a altura acompanha a quebra


def test_chest_label_has_an_icon_for_every_logistic_item(fresh):
    """Baú configurado pra mandar alga e cápsula vazia: o rótulo no mundo dava KeyError (o jogo fechava)."""
    icons = fresh.chest_label_icons()
    assert set(C.LOGISTIC_ITEMS) <= set(icons)
    chest = Machine("chest", 70, 70)
    chest.sends = {"algae", C.EMPTY_CAPSULE}
    chest.receives = set(C.CROP_ITEMS)
    fresh.ui.begin()
    fresh.ui.draw_chest_labels([chest], (0, 0), 1.0, icons)
