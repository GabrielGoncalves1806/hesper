"""Fabricar em campo (aba Fabricar do Tab, bíblia §9): kit de campo (C.FIELD_RECIPES), gasta só do inventário,
mesmas travas do fabricador (Ti e projeto), inventário cheio e o clique pelo App headless."""

import os
import random
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.fabricator import field_menu  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from game.ui import TAB_CRAFT, TAB_INVENTORY, TAB_LOGS  # noqa: E402
from tests.helpers import give  # noqa: E402

FAR = (40.0 * C.TILE, 40.0 * C.TILE)        # longe da base (fora da zona de O₂)


def make_state(ti: float = 0) -> GameState:
    s = GameState(rng=random.Random(1))
    set_ti(s, ti)
    return s


def set_ti(s: GameState, ti: float) -> None:
    """Ti = soma dos índices: põe tudo no O₂."""
    for k in s.indices:
        s.indices[k] = 0
    s.indices["o2"] = ti


def base_chest(s: GameState, **items) -> Machine:
    """Um baú dentro da zona da base, com recursos."""
    tx, ty = C.BASE_CENTER[0] // C.TILE + 3, C.BASE_CENTER[1] // C.TILE + 3
    chest = Machine("chest", tx, ty)
    for item, n in items.items():
        chest.storage.add(item, n)
    s.surface.machines.append(chest)
    assert chest in s.base_chests()
    return chest


# ---- kit de campo -------------------------------------------------------------------------------
def test_field_kit_is_the_decided_list():
    assert C.FIELD_RECIPES == ("drill", "lamp", "lamp_t2", "chest")
    assert field_menu().kinds == list(C.FIELD_RECIPES)
    for kind in C.FIELD_RECIPES:
        assert kind in C.MACHINES


@pytest.mark.parametrize("kind", ["o2", "melter", "heater", "o2_t2", "solar", "drone_station", "drone",
                                  "o2_tank", "scanner"])
def test_recipe_outside_the_kit_is_not_listed_nor_craftable(kind):
    assert kind not in field_menu().kinds
    s = make_state(ti=50_000)
    s.blueprints |= set(C.BLUEPRINTS)
    give(s, iron=50, silicon=50, ice=50)
    s.player.x, s.player.y = FAR
    assert not s.craft(kind, field=True)
    assert s.inventory.count(kind) == 0 and s.inventory.count("iron") == 50


# ---- gasta só do inventário ---------------------------------------------------------------------
def test_field_spends_only_inventory_and_ignores_base_chests():
    s = make_state()
    chest = base_chest(s, iron=20)
    give(s, iron=2)
    # na base, o fabricador enxerga 22; em campo, só os 2 do inventário
    assert s.available("iron") == 22 and s.available("iron", field=True) == 2
    assert s.recipe_status("chest") == "ok" and s.recipe_status("chest", field=True) == "missing"
    assert s.missing_resource("chest", field=True) == "iron"
    assert not s.craft("chest", field=True)
    assert chest.storage.count("iron") == 20
    give(s, iron=5)                                        # 7 no inventário: dá um baú (6 de ferro)
    assert s.craft("chest", field=True)
    assert s.inventory.count("iron") == 1 and chest.storage.count("iron") == 20   # o baú não foi tocado
    assert s.inventory.count("chest") == 1 and s.crafted["chest"] == 1
    assert ("craft", "chest") in s.events


def test_field_works_far_from_base_and_the_fabricator_does_not():
    s = make_state()
    give(s, iron=2, silicon=2)
    s.player.x, s.player.y = FAR
    assert not s.in_base_zone()
    assert not s.craft("lamp")                            # fabricador: só na base
    assert s.craft("lamp", field=True)
    assert s.inventory.count("lamp") == 1 and s.inventory.count("iron") == 1


def test_field_batch_stops_when_inventory_runs_out():
    s = make_state()
    base_chest(s, iron=50, silicon=50)
    give(s, iron=3, silicon=3)
    assert s.craft_many("lamp", field=True) == 3          # 3 luminárias: o que está no inventário
    assert s.inventory.count("lamp") == 3 and s.inventory.count("iron") == 0
    assert ("craft", "lamp", 3) in s.events


# ---- travas iguais às do fabricador ----------------------------------------------------------------
def test_lamp_t2_locked_without_blueprint():
    s = make_state()
    give(s, iron=10, silicon=10, ice=10)
    assert "lamp_t2" in field_menu().kinds
    assert s.recipe_status("lamp_t2", field=True) == "blueprint"
    assert not s.craft("lamp_t2", field=True)
    s.learn("lamp_t2")
    assert s.recipe_status("lamp_t2", field=True) == "ok"
    assert s.craft("lamp_t2", field=True) and s.inventory.count("lamp_t2") == 1


def test_drill_locked_by_ti_like_the_fabricator():
    s = make_state(ti=0)
    give(s, iron=20, silicon=20)
    assert s.recipe_status("drill", field=True) == "locked"
    assert not s.craft("drill", field=True)
    set_ti(s, C.DRILL_UNLOCK_TI)
    assert s.craft("drill", field=True) and s.inventory.count("drill") == 1


# ---- inventário cheio ---------------------------------------------------------------------------
def test_full_inventory_keeps_resources_and_warns():
    s = make_state()
    give(s, iron=C.STACK_RESOURCE)
    for slot in range(len(s.inventory)):                  # enche todos os slots com outra coisa
        if s.inventory.slots[slot] is None:
            s.inventory.add("ice", 50)
    assert not s.inventory.has_space("chest")
    iron = s.inventory.count("iron")
    s.events.clear()
    assert not s.craft("chest", field=True)
    assert ("inv_full",) in s.events
    assert s.inventory.count("iron") == iron and s.inventory.count("chest") == 0


# ---- App headless: aba, clique e teclado ---------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_field_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def click(app, rect):
    from game import viewport
    (x, y, _, _), k, _ = viewport.ui_layout(app.window.get_size(), app.settings["ui_size"])
    pos = round(x + rect.centerx * k), round(y + rect.centery * k)
    app.mouse_window = pos
    app.mouse = app.window_to_canvas(pos)
    app.on_click(1)


def reset(app):
    s = app.state
    app.mode = "play"
    app.held = None
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.player.x, s.player.y = FAR
    return s


def test_tabs_order_and_a_d_cycle(app):
    reset(app)
    app.on_key(pygame.K_TAB)
    app.draw()
    assert app.inv_tab == TAB_INVENTORY
    assert [i for _, i in app.ui.inv_tab_rects] == [TAB_INVENTORY, TAB_CRAFT, TAB_LOGS]
    rects = [r for r, _ in app.ui.inv_tab_rects]
    # Inventário | Fabricar | LOGs: controle segmentado (encostadas, sem sobrepor)
    assert all(a.right <= b.left for a, b in zip(rects, rects[1:]))
    app.on_key(pygame.K_d)
    assert app.inv_tab == TAB_CRAFT
    app.on_key(pygame.K_d)
    assert app.inv_tab == TAB_LOGS
    app.on_key(pygame.K_d)
    assert app.inv_tab == TAB_INVENTORY
    app.on_key(pygame.K_a)
    assert app.inv_tab == TAB_LOGS
    app.on_key(pygame.K_ESCAPE)
    assert app.mode == "play"


def test_click_craft_in_the_field_from_inventory_only(app):
    s = reset(app)
    chest = base_chest(s, iron=30, silicon=30)
    give(s, iron=1, silicon=1)
    app.on_key(pygame.K_TAB)
    app.draw()
    click(app, next(r for r, i in app.ui.inv_tab_rects if i == TAB_CRAFT))
    assert app.inv_tab == TAB_CRAFT
    app.draw()
    assert [k for _, k in app.ui.fabricator_rows] == list(C.FIELD_RECIPES)
    # lista + detalhe: o FABRICAR é da receita escolhida e só aparece se dá. Escolhendo cada uma (clique na
    # linha), só a luminária dá com 1 Fe + 1 Si
    craftable = []
    for kind in C.FIELD_RECIPES:
        click(app, next(r for r, k in app.ui.fabricator_rows if k == kind))
        assert app.field.current == kind
        app.draw()
        craftable += [k for _, k in app.ui.fabricator_buttons]
    assert craftable == ["lamp"]
    click(app, next(r for r, k in app.ui.fabricator_rows if k == "lamp"))
    app.draw()
    click(app, next(r for r, k in app.ui.fabricator_buttons if k == "lamp"))
    app.update(1 / 60)
    assert s.inventory.count("lamp") == 1
    assert s.inventory.count("iron") == 0 and chest.storage.count("iron") == 30
    assert app.mode == "play" and app.placing == "lamp"               # igual ao fabricador: já vai colocar
    s.surface.machines.remove(chest)


def test_keyboard_craft_and_full_inventory_notice(app):
    s = reset(app)
    set_ti(s, C.DRILL_UNLOCK_TI)
    give(s, iron=12, silicon=6)
    for slot in range(len(s.inventory)):                  # o resto do inventário cheio de gelo
        if s.inventory.slots[slot] is None:
            s.inventory.add("ice", 50)
    app.on_key(pygame.K_TAB)
    app.switch_inv_tab(TAB_CRAFT)
    app.field.select("drill")                 # o teste anterior escolheu a luminária com o clique na linha
    app.draw()
    assert app.field.current == "drill"
    app.on_key(pygame.K_RETURN)                           # a drill (12 Fe + 6 Si) libera os 2 slots: cabe
    app.update(1 / 60)
    assert s.inventory.count("drill") == 1 and app.mode == "play"
    s.inventory.slots[:] = [None] * len(s.inventory)    # agora tudo cheio: ferro, silício e gelo (pilhas de 50)
    give(s, iron=50, silicon=50, ice=50 * (len(s.inventory) - 2))
    assert not s.inventory.has_space("lamp")
    app.on_key(pygame.K_TAB)
    app.switch_inv_tab(TAB_CRAFT)
    app.field.select("lamp")
    app.on_key(pygame.K_RETURN)
    app.update(1 / 60)
    assert s.inventory.count("lamp") == 0 and app.mode == "inventory"
    assert app.notice == "Inventário cheio"
    app.on_key(pygame.K_ESCAPE)
    assert app.mode == "play"


# ---- desenho nos 3 tamanhos ---------------------------------------------------------------------
@pytest.mark.parametrize("size", [(480, 270), (640, 360), (960, 540)])
def test_field_window_fits_with_tabs_in_place(size):
    pygame.font.init()
    from game import art
    from game.ui import UI
    ui = UI()
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = make_state()
    ui.begin()
    ui.draw_inventory(s.inventory, None, 0, lambda item: art.icon("iron"), (0, 0), equipment=s.equipment, state=s)
    tabs_inv = [r.copy() for r, _ in ui.inv_tab_rects]
    ui.begin()
    ui.draw_field_craft(s, field_menu(), lambda kind: pygame.Surface((40, 56)), (0, 0))
    assert [r.y for r, _ in ui.inv_tab_rects] == [r.y for r in tabs_inv]    # abas não pulam
    w, h = ui.field_window_size()
    assert w <= size[0] - 8
    rows = [r for r, _ in ui.fabricator_rows]
    assert len(rows) == len(C.FIELD_RECIPES)
    for a, b in zip(rows, rows[1:]):
        assert a.bottom <= b.top
    assert rows[-1].bottom < ui.hotbar_y - 11 - 12          # lista e linha de ajuda acima da hotbar
