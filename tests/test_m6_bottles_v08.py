"""v0.8 M6 Task 6 · A garrafa é recurso (bíblia §17): a cápsula vazia é fabricada (1 silício → 2, aba Materiais) e o
derretedor só enche vazia (slot VAZIAS, o 2). Sem vazia ele para e não gasta gelo; a terraformação não muda. Ninguém
ganha vazia de graça, então o total de garrafas só muda quando o jogador fabrica."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from game import art, drones, fabricator, save  # noqa: E402
from game import config as C  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.objectives import OBJECTIVES  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from game.ui import DISP_LOGI_Y, GRID_W, HELP_H, UI, wrap  # noqa: E402
from tests.helpers import give  # noqa: E402
from tests.test_base import demo_base, run  # noqa: E402
from tests.test_base_app import app, fresh  # noqa: E402,F401  (fixtures)
from tests.test_m5_chest_fit_v08 import SIZES, SUITS, suited  # noqa: E402

TIME = C.MELTER_CAPSULE_TIME["melter"]
CAPS = ("water_capsule", C.EMPTY_CAPSULE)


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def melter(game, ice=0, empties=0, full=0, **kw) -> Machine:
    m = Machine("melter", 64, 70, **kw)
    if ice:
        m.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", ice)
    if empties:
        m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, empties)
    if full:
        m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", full)
    game.machines.append(m)
    return m


def tick(game, seconds, step=1 / 30):
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def slot_of(game, item):
    return next(i for i, s in enumerate(game.inventory.slots) if s and s.item == item)


# ---------------------------------------------------------------- config
def test_slots_keep_their_indices():
    assert (C.MELTER_ICE_SLOT, C.MELTER_CAPSULE_SLOT, C.MELTER_EMPTY_SLOT, C.MELTER_SLOTS) == (0, 1, 2, 3)
    assert len(Machine("melter", 1, 1).storage) == 3 and len(Machine("melter_t2", 1, 1).storage) == 3


def test_empty_capsule_recipe_is_in_the_materials_tab():
    item = C.MACHINES[C.EMPTY_CAPSULE]
    assert item.cost == {"silicon": 1} and C.CRAFT_YIELD[C.EMPTY_CAPSULE] == 2 and not item.placeable
    assert C.MACHINE_CATEGORY[C.EMPTY_CAPSULE] == "materials"
    assert C.EMPTY_CAPSULE in fabricator.craft_kinds("materials")
    assert C.EMPTY_CAPSULE not in C.T2_RECIPES
    assert "derretedor" in item.desc and "Coletor" in item.desc


def test_crafting_gives_two_empties_for_one_silicon():
    g = GameState(rng=random.Random(1))                                  # nasce na base (o craft exige in_base_zone)
    g.inventory.add("silicon", 3)
    assert g.craft(C.EMPTY_CAPSULE)
    assert g.inventory.count(C.EMPTY_CAPSULE) == 2 and g.inventory.count("silicon") == 2


# ---------------------------------------------------------------- derretedor
def test_one_cycle_spends_one_empty_and_the_ice_and_makes_one_full(game):
    m = melter(game, ice=10, empties=3)
    tick(game, TIME + 0.5)
    assert m.capsules == 1 and m.storage.count(C.EMPTY_CAPSULE) == 2
    assert m.ice == 10 - C.MELTER_ICE_PER_CAPSULE


def test_without_empty_it_stops_keeps_the_ice_and_progress_but_water_rises(game):
    m = melter(game, ice=10, empties=1)
    water0 = game.indices["water"]
    tick(game, TIME * 1.5)                         # 1 cheia, e meio caminho na 2ª... que não tem vazia
    assert m.capsules == 1 and m.storage.count(C.EMPTY_CAPSULE) == 0
    timer = m.timer
    ice = m.ice
    tick(game, TIME * 3)
    assert m.capsules == 1 and m.ice == ice and m.timer == timer          # parou: não gasta gelo, guarda o progresso
    assert m.melter_blocker == "no_empty"
    assert game.indices["water"] > water0                                 # a terraformação segue
    w1 = game.indices["water"]
    tick(game, 5)
    assert game.indices["water"] > w1
    m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 1)      # voltou a vazia: termina a que estava no meio
    tick(game, TIME - timer + 0.2)
    assert m.capsules == 2


def test_blocker_order(game):
    m = melter(game)
    assert m.melter_blocker == "no_empty"
    m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    assert m.melter_blocker == "no_ice"
    m.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", 4)
    assert m.melter_blocker is None
    m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", C.STACK_MACHINE)
    assert m.melter_blocker == "out_full"


# ---------------------------------------------------------------- slots
def test_player_put_routes_ice_and_empties_and_refuses_the_rest(game):
    m = melter(game)
    give(game, ice=6, **{C.EMPTY_CAPSULE: 4, "iron": 2, "water_capsule": 1})
    assert game.melter_put(m, slot_of(game, C.EMPTY_CAPSULE)) == 4
    assert m.storage.slots[C.MELTER_EMPTY_SLOT] == Stack(C.EMPTY_CAPSULE, 4)
    assert game.melter_put(m, slot_of(game, "ice")) == 6
    assert m.storage.slots[C.MELTER_ICE_SLOT] == Stack("ice", 6)
    assert game.melter_put(m, slot_of(game, "iron")) == 0
    assert game.melter_put(m, slot_of(game, "water_capsule")) == 0


def test_panel_refuses_wrong_items_per_slot(fresh):
    app = fresh
    m = melter(app.state)
    app.open_melter = m
    app.set_mode("melter")
    assert app.panel_refusal(m.storage, C.MELTER_EMPTY_SLOT, C.EMPTY_CAPSULE) is None
    assert app.panel_refusal(m.storage, C.MELTER_EMPTY_SLOT, "ice") is not None
    assert app.panel_refusal(m.storage, C.MELTER_EMPTY_SLOT, "iron") is not None
    assert app.panel_refusal(m.storage, C.MELTER_ICE_SLOT, C.EMPTY_CAPSULE) is not None
    assert app.panel_refusal(m.storage, C.MELTER_ICE_SLOT, "ice") is None
    assert app.panel_refusal(m.storage, C.MELTER_CAPSULE_SLOT, C.EMPTY_CAPSULE) is not None
    app.set_mode("play")


def test_panel_status_says_sem_vazia(fresh):
    app = fresh
    m = melter(app.state, ice=10)
    app.open_melter = m
    app.set_mode("melter")
    assert app.melter_status() == "SEM VAZIA"
    m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 1)
    assert app.melter_status().startswith("1 A CADA")
    app.set_mode("play")


def test_shift_click_routes_ice_and_empties(fresh):
    s = fresh.state
    m = melter(s)
    fresh.open_melter = m
    fresh.set_mode("melter")
    s.inventory.slots[0] = Stack(C.EMPTY_CAPSULE, 3)
    s.inventory.slots[1] = Stack("ice", 4)
    s.inventory.slots[2] = Stack("iron", 2)
    ui = fresh.ui
    ui.begin()
    ui.draw_inventory(s.inventory, m, 0, fresh.renderer.item_icon, (0, 0), 0.0, None, fresh.melter_status(), None)
    rect = {(inv is s.inventory, i): r for r, inv, i in ui.slot_rects}
    fresh.panel_shift_click(rect[(True, 0)].center)
    fresh.panel_shift_click(rect[(True, 1)].center)
    fresh.panel_shift_click(rect[(True, 2)].center)
    assert m.storage.slots[C.MELTER_EMPTY_SLOT] == Stack(C.EMPTY_CAPSULE, 3)
    assert m.storage.slots[C.MELTER_ICE_SLOT] == Stack("ice", 4)
    assert s.inventory.count("iron") == 2 and fresh.notice == "O derretedor só aceita gelo e cápsula vazia"
    fresh.set_mode("play")


def test_clicking_an_empty_into_the_empty_slot(fresh):
    s = fresh.state
    m = melter(s)
    fresh.open_melter = m
    fresh.set_mode("melter")
    fresh.held = Stack(C.EMPTY_CAPSULE, 2)
    assert fresh.panel_put(m.storage, C.MELTER_EMPTY_SLOT, 1) and fresh.held is None
    assert m.storage.slots[C.MELTER_EMPTY_SLOT] == Stack(C.EMPTY_CAPSULE, 2)
    fresh.held = Stack(C.EMPTY_CAPSULE, 1)
    assert not fresh.panel_put(m.storage, C.MELTER_ICE_SLOT, 1)           # o gelo não aceita vazia
    fresh.held = None
    fresh.set_mode("play")


# ---------------------------------------------------------------- drones
def test_drone_config():
    m = Machine("melter", 1, 1)
    assert drones.can_receive(m, "ice") and drones.can_receive(m, C.EMPTY_CAPSULE)
    assert drones.can_send(m, "water_capsule") and not drones.can_send(m, C.EMPTY_CAPSULE)
    assert not drones.can_receive(m, "water_capsule")
    assert drones.receive_slot(m, C.EMPTY_CAPSULE) == C.MELTER_EMPTY_SLOT
    assert drones.receive_slot(m, "ice") == C.MELTER_ICE_SLOT
    assert not drones.toggle_send(m, C.EMPTY_CAPSULE)


def test_drone_brings_empties_to_the_melter_and_never_takes_them(game):
    chest = Machine("chest", 60, 66, sends={C.EMPTY_CAPSULE})
    chest.storage.add(C.EMPTY_CAPSULE, 6)
    m = melter(game, chip=True, receives={C.EMPTY_CAPSULE}, sends={"water_capsule"})
    sink = Machine("chest", 68, 66, receives={C.EMPTY_CAPSULE})
    station = Machine("drone_station", 62, 72)
    station.station = drones.new_station(station, 1)
    game.machines += [chest, sink, station]
    tick(game, 30)
    assert m.storage.slots[C.MELTER_EMPTY_SLOT] is not None
    assert m.storage.count(C.EMPTY_CAPSULE) + sink.storage.count(C.EMPTY_CAPSULE) >= 1
    chest.storage.clear()
    chest.sends.clear()
    sink.storage.clear()
    before = m.storage.count(C.EMPTY_CAPSULE)
    tick(game, 30)
    assert m.storage.count(C.EMPTY_CAPSULE) == before                     # o sink quer vazia, mas do derretedor não sai
    assert sink.storage.count(C.EMPTY_CAPSULE) == 0


def test_conservation_melter_dispenser_and_a_drone():
    """Derretedor + Dispersor + 1 estação com drone: as garrafas circulam e o total nunca muda."""
    g = GameState(rng=random.Random(5))
    g.debug_add_ti()
    disp, x0, y0 = demo_base(g, w=7, h=7)
    disp.chip = True
    disp.sends, disp.receives = {C.EMPTY_CAPSULE}, {"water_capsule"}
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 1)
    m = Machine("melter", x0 + 3, y0 + 9, chip=True, sends={"water_capsule"}, receives={C.EMPTY_CAPSULE})
    m.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", C.STACK_RESOURCE)
    m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 3)
    station = Machine("drone_station", x0 + 9, y0 + 4)
    station.station = drones.new_station(station, 1)
    g.machines += [m, station]
    total0 = 4

    def total():
        stored = sum(mm.storage.count(i) for mm in (m, disp) for i in CAPS)
        flying = sum(d.cargo for d in station.station.drones if d.resource in CAPS)
        burning = 1 if disp.burn > 0 else 0
        return stored + flying + burning

    for _ in range(40):
        run(g, 10, step=0.1)
        assert total() == total0, total()
    assert disp.burn > 0 or disp.capsules > 0                             # a água chegou de volta no Dispersor
    made = (C.STACK_RESOURCE - m.ice) // C.MELTER_ICE_PER_CAPSULE
    assert made >= 4, made                                                # encheu mais que as 3 do começo: a vazia voltou


# ---------------------------------------------------------------- save e desmontar
def test_save_roundtrip_with_empties():
    m = Machine("melter_t2", 4, 4, chip=True, sends={"water_capsule"}, receives={"ice", C.EMPTY_CAPSULE})
    m.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", 7)
    m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", 2)
    m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 5)
    m.timer = 3.0
    back = save.machine_from_dict(save.machine_to_dict(m))
    assert back.storage.slots == m.storage.slots and back.timer == 3.0
    assert back.receives == {"ice", C.EMPTY_CAPSULE}


def test_v17_melter_with_two_slots_loads_with_the_empty_slot_free():
    assert save.SAVE_VERSION == 17
    data = {"kind": "melter", "tx": 1, "ty": 1, "rotation": 0, "timer": 4.0,
            "storage": [["ice", 12], ["water_capsule", 2]], "sends": ["water_capsule"], "receives": ["ice"]}
    m = save.machine_from_dict(data)
    assert len(m.storage) == 3 and m.ice == 12 and m.capsules == 2
    assert m.storage.slots[C.MELTER_EMPTY_SLOT] is None                 # sem vazia de presente


def test_save_cleans_a_wrong_item_in_the_empty_slot():
    data = {"kind": "melter", "tx": 1, "ty": 1, "rotation": 0, "storage": [None, None, ["water_capsule", 3]]}
    assert save.machine_from_dict(data).storage.slots[C.MELTER_EMPTY_SLOT] is None


def test_dismantle_returns_the_empties(game):
    m = melter(game, ice=4, empties=3, full=1)
    out = game.dismantle_returns(m)
    assert out[C.EMPTY_CAPSULE] == 3 and out["water_capsule"] == 1 and out["ice"] >= 4


# ---------------------------------------------------------------- dica
def test_melter_objective_hint():
    obj = next(o for o in OBJECTIVES if o.text == "Minere gelo e construa um Derretedor")
    assert obj.hint == "O derretedor enche cápsulas vazias: fabrique algumas (silício) e ponha nele."


def test_melter_hint_fits_the_card():
    pygame.font.init()
    ui = UI()
    from game.objectives import SCAN_HINT
    hint = next(o for o in OBJECTIVES if o.text == "Minere gelo e construa um Derretedor").hint
    assert len(wrap(ui.body, hint, ui.objective_w - 12)) <= len(wrap(ui.body, SCAN_HINT, ui.objective_w - 12))


# ---------------------------------------------------------------- painel: cabe
@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def wired(kind) -> Machine:
    m = Machine(kind, 10, 10)
    m.chip = True
    m.sends = {i for i in C.LOGISTIC_ITEMS if drones.can_send(m, i)}
    m.receives = {i for i in C.LOGISTIC_ITEMS if drones.can_receive(m, i)}
    return m


def draw(ui, kind, size, suit, status="SEM VAZIA"):
    g = suited(suit)
    m = wired(kind)
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    ui.draw_inventory(g.inventory, m, 0, lambda _i: art.icon("iron"), (0, 0), state=g, status=status)
    return m, ui.hotbar_y - 11 - 1 - HELP_H


@pytest.mark.parametrize("kind", C.MELTER_KINDS)
@pytest.mark.parametrize("size", SIZES, ids=lambda s: str(s[0]))
@pytest.mark.parametrize("suit", list(SUITS))
def test_melter_panel_stays_above_the_hotbar_frame(ui, kind, size, suit):
    _m, frame = draw(ui, kind, size, suit)
    btns = [r for r, _ in ui.logistics_buttons]
    assert max(r.bottom for r in btns) <= frame, (max(r.bottom for r in btns), frame)
    assert ui.inv_window.bottom <= frame
    assert ui.side_window.bottom <= frame, (ui.side_window.bottom, frame)
    assert ui.side_window.bottom + HELP_H <= ui.hotbar_y - 11 - 1


def test_melter_panel_uses_disp_logi_y_and_text_stays_above_it(ui):
    m, _ = draw(ui, "melter", (480, 270), "t2")
    top = min(r.top for r, _ in ui.logistics_buttons)
    assert top >= ui.side_window.y + DISP_LOGI_Y
    for text in ("Fabrique cápsulas vazias (silício) e ponha aqui.", "Gelo + 1 vazia = 1 cheia. Drones levam as cheias."):
        assert len(wrap(ui.body, text, GRID_W)) <= 2
    # 2 linhas de ajuda em y+48 e y+60 (14 de altura) acabam antes da linha DRONES
    assert 48 + 12 + ui.body.get_height() <= DISP_LOGI_Y


def test_melter_panel_labels_and_status_fit(ui):
    from game import ui as ui_mod
    gaps = ui_mod.MELT_SLOT_X                     # x dos 3 slots: GELO, VAZIAS, CHEIAS
    assert gaps[1] - gaps[0] >= ui.font.size("GELO")[0] + 2 and gaps[1] - gaps[0] >= ui_mod.SLOT + 4
    assert gaps[2] - gaps[1] >= ui.font.size("VAZIAS")[0] + 2
    bw = GRID_W - ui_mod.MELT_BAR_X
    for status in ("SEM VAZIA", "SEM GELO", "SAÍDA CHEIA", "1 A CADA 20 S", "1 A CADA 10 S"):
        assert ui.body.size(status)[0] <= bw, status


def test_melter_panel_draws_three_slots(ui):
    _m, _ = draw(ui, "melter", (480, 270), "nv1")
    assert ui.side_window is not None


