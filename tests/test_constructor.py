"""v0.5 M1 · construtor e desmontar (spec docs/superpowers/specs/2026-10-14-v05-base-e-expedicao-design.md).

Antes era o "fabricar em campo" (aba Fabricar do Tab); a aba saiu e as receitas dela (todas máquinas) foram pro
construtor. Aqui: construir gastando só o inventário, travas (Ti, projeto, construtor), sem material, o tempo de
construir sem funcionar, o fabricador só com itens, desmontar segurando (cancelar, inventário cheio, clique rápido)
e o fluxo pelo App headless (E abre o menu, escolhe, clique constrói)."""

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
from game.fabricator import build_menu, craft_menu  # noqa: E402
from game.systems import Controls, GameState, Machine  # noqa: E402
from game.ui import TAB_INVENTORY, TAB_LOGS  # noqa: E402
from tests.helpers import build_now, give  # noqa: E402

FAR = (40.0 * C.TILE, 40.0 * C.TILE)        # longe da base (fora da zona de O₂)
MACHINE_KINDS = [k for k in C.MACHINE_ORDER if C.MACHINES[k].placeable]
ITEM_KINDS = [k for k in C.MACHINE_ORDER if not C.MACHINES[k].placeable]


def make_state(ti: float = 0) -> GameState:
    s = GameState(rng=random.Random(1))
    set_ti(s, ti)
    return s


def set_ti(s: GameState, ti: float) -> None:
    """Ti = soma dos índices: põe tudo no O₂."""
    for k in s.indices:
        s.indices[k] = 0
    s.indices["o2"] = ti


def spot(s: GameState) -> tuple[int, int]:
    px, py = s.player.tile
    return px + 2, py


def base_chest(s: GameState, **items) -> Machine:
    """Um baú dentro da zona da base, com recursos."""
    tx, ty = C.BASE_CENTER[0] // C.TILE + 3, C.BASE_CENTER[1] // C.TILE + 3
    chest = Machine("chest", tx, ty)
    for item, n in items.items():
        chest.storage.add(item, n)
    s.surface.machines.append(chest)
    assert chest in s.base_chests()
    return chest


def hold(s: GameState, machine, seconds: float, step: float = 0.05) -> None:
    """Segura o botão direito em cima de `machine` por `seconds` (None = soltou)."""
    t = 0.0
    while t < seconds - 1e-9:
        s.update(step, Controls(dismantle=machine))
        t += step


# ---- o fabricador da cápsula: só itens ------------------------------------------------------------
def test_constructor_is_the_first_cheap_iron_recipe():
    m = C.MACHINES["constructor"]
    assert C.MACHINE_ORDER[0] == "constructor" and not m.placeable
    assert set(m.cost) == {"iron"} and m.cost["iron"] <= 6 and m.unlock_ti == 0
    assert craft_menu().current == "constructor"                       # 1ª aba, 1ª linha


def test_fabricator_lists_only_items_and_the_constructor_only_machines():
    fab = craft_menu()
    fab_kinds = [k for t, _ in fab.tabs for k in fab.kinds_of(t)]
    assert sorted(fab_kinds) == sorted(["constructor", "drone", "o2_tank", "scanner"])
    build = build_menu()
    build_kinds = [k for t, _ in build.tabs for k in build.kinds_of(t)]
    assert sorted(build_kinds) == sorted(MACHINE_KINDS)
    assert build.tabs == C.FAB_TABS and ("suit", "Traje") not in C.FAB_TABS


@pytest.mark.parametrize("kind", MACHINE_KINDS)
def test_fabricator_does_not_make_machines(kind):
    s = make_state(ti=50_000)
    s.blueprints |= set(C.BLUEPRINTS)
    give(s, iron=50, silicon=50, ice=50, magmatite=20)
    assert not s.craft(kind)
    assert s.inventory.count(kind) == 0 and s.inventory.count("iron") == 50


def test_craft_the_constructor_at_the_base():
    s = make_state()
    give(s, iron=C.MACHINES["constructor"].cost["iron"])
    assert s.craft("constructor") and s.has_constructor
    assert s.inventory.count("iron") == 0 and s.crafted["constructor"] == 1


# ---- construir: só o inventário, travas, sem material ---------------------------------------------
def test_build_spends_only_inventory_and_ignores_base_chests():
    s = make_state()
    chest = base_chest(s, iron=20)
    give(s, constructor=1, iron=2)
    assert s.available("iron") == 22 and s.available("iron", inv_only=True) == 2
    assert s.build_status("chest") == "missing" and not s.can_build("chest", spot(s))
    assert not s.build("chest", spot(s))
    assert chest.storage.count("iron") == 20
    give(s, iron=5)                                        # 7 no inventário: dá um baú (6 de ferro)
    assert s.build("chest", spot(s))
    assert s.inventory.count("iron") == 1 and chest.storage.count("iron") == 20   # o baú da base não foi tocado
    assert s.inventory.count("chest") == 0                                        # máquina não é item
    built = s.machine_at(spot(s))
    assert built is not None and built.kind == "chest" and built.build == C.BUILD_TIME
    assert s.crafted["chest"] == 1 and ("build", "chest", spot(s)) in s.events


def test_build_works_far_from_base():
    s = make_state()
    s.player.x, s.player.y = FAR
    assert not s.in_base_zone()
    give(s, constructor=1, iron=1, silicon=1)
    tile = next(t for t in [(40, 40), (41, 40), (42, 40), (40, 42), (38, 40)] if s.can_place("lamp", t))
    assert s.build("lamp", tile) and s.lamps_placed == 1


def test_build_needs_the_constructor():
    s = make_state()
    give(s, iron=10, silicon=4)
    assert s.build_status("o2") == "no_constructor" and not s.build("o2", spot(s))
    give(s, constructor=1)
    assert s.build("o2", spot(s)) and s.has_constructor          # o construtor não gasta


def test_lamp_t2_locked_without_diagram():
    s = make_state()
    give(s, constructor=1, iron=10, silicon=10, ice=10)
    assert s.build_status("lamp_t2") == "blueprint" and not s.build("lamp_t2", spot(s))
    s.blueprints.add("lamp_t2")
    assert s.build("lamp_t2", spot(s))


def test_drill_locked_by_ti():
    s = make_state(ti=0)
    give(s, constructor=1, iron=20, silicon=20)
    assert s.build_status("drill") == "locked"
    set_ti(s, C.DRILL_UNLOCK_TI)
    assert s.build_status("drill") == "ok"


def test_keeps_building_while_there_is_material():
    s = make_state()
    give(s, constructor=1, iron=2, silicon=2)
    px, py = s.player.tile
    assert s.build("lamp", (px + 2, py)) and s.build("lamp", (px - 2, py))
    assert s.build_status("lamp") == "missing" and not s.build("lamp", (px, py + 2))
    assert s.missing_resource("lamp", inv_only=True) == "iron"


# ---- o tempo de construir: parada ------------------------------------------------------------------
def test_machine_under_construction_does_not_work():
    s = make_state()
    o2 = build_now(s, "o2", spot(s), finish=False)
    panel = build_now(s, "solar", (spot(s)[0], spot(s)[1] + 2), finish=False)
    assert o2.build > 0 and panel.build > 0
    assert o2 not in s.working_machines and s.ti_rate == 0
    assert s.power.consumption == 0 and s.power.production == C.POD_POWER
    s.update(C.BUILD_TIME / 2, Controls())
    assert s.indices["o2"] == 0 and o2.build > 0
    for _ in range(int(C.BUILD_TIME / 0.05) + 2):
        s.update(0.05, Controls())
    assert o2.build == 0 and o2 in s.working_machines
    assert s.power.production == C.POD_POWER + C.POWER_GEN["solar"]
    before = s.indices["o2"]
    s.update(0.05, Controls())
    assert s.indices["o2"] > before


def test_station_under_construction_does_not_launch_drones():
    s = make_state(ti=C.DRONE_STATION_UNLOCK_TI)
    px, py = s.player.tile
    tile = next((x, y) for x in range(px - 4, px + 4) for y in range(py - 4, py + 4)
                if s.can_place("drone_station", (x, y)))
    st = build_now(s, "drone_station", tile, finish=False)
    assert st.build > 0 and st not in s.working_machines


# ---- desmontar segurando -------------------------------------------------------------------------
def test_hold_dismantle_returns_the_recipe():
    s = make_state()
    m = build_now(s, "o2", spot(s))
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.events.clear()
    hold(s, m, C.DISMANTLE_HOLD - 0.1)
    assert m in s.machines and s.dismantling is m and 0 < s.dismantle_progress < 1
    assert ("dismantle_charge",) in s.events
    hold(s, m, 0.15)
    assert m not in s.machines and s.dismantling is None
    for r, n in C.MACHINES["o2"].cost.items():
        assert s.inventory.count(r) == n
    assert s.inventory.count("o2") == 0
    assert ("dismantle", "o2", (m.tx, m.ty)) in s.events


def test_releasing_or_leaving_the_machine_cancels():
    s = make_state()
    m = build_now(s, "o2", spot(s))
    hold(s, m, 1.0)
    s.events.clear()
    s.update(0.05, Controls())                         # soltou
    assert s.dismantling is None and s.dismantle_t == 0 and m in s.machines
    assert ("dismantle_cancel",) in s.events
    hold(s, m, 1.0)                                    # recomeça do zero
    other = build_now(s, "lamp", (spot(s)[0], spot(s)[1] + 2))
    hold(s, other, 0.05)                               # o mouse foi pra outra máquina: a 1ª cancela
    assert s.dismantling is other and s.dismantle_t <= 0.06 and m in s.machines


def test_full_inventory_keeps_the_machine():
    s = make_state()
    m = build_now(s, "o2", spot(s))
    s.inventory.slots[:] = [None] * len(s.inventory)
    give(s, ice=50 * len(s.inventory))
    s.events.clear()
    hold(s, m, C.DISMANTLE_HOLD + 0.1)
    assert m in s.machines and ("inv_full",) in s.events and ("dismantle_cancel",) in s.events
    assert s.inventory.count("iron") == 0
    s.events.clear()
    hold(s, m, C.DISMANTLE_HOLD + 0.1)                 # segurando sem soltar: não tenta de novo
    assert ("inv_full",) not in s.events


def test_drill_dismantle_is_all_or_nothing():
    s = make_state(ti=C.DRILL_UNLOCK_TI)
    vein = next(v for v in s.world.veins if True)
    s.player.x, s.player.y = (vein.tx + 1) * C.TILE, (vein.ty + 3) * C.TILE + 8
    drill = build_now(s, "drill", (vein.tx, vein.ty))
    drill.stored = 10
    s.inventory.slots[:] = [None] * len(s.inventory)
    give(s, ice=50 * (len(s.inventory) - 1))           # 1 slot livre: não cabe minério + receita
    assert not s.dismantle(drill)
    assert drill in s.machines and drill.stored == 10
    s.inventory.slots[:] = [None] * len(s.inventory)
    assert s.dismantle(drill)
    assert s.inventory.count(drill.resource) >= 10


def test_chest_with_items_does_not_charge():
    s = make_state()
    chest = build_now(s, "chest", spot(s))
    chest.storage.add("iron", 3)
    s.events.clear()
    hold(s, chest, C.DISMANTLE_HOLD + 0.1)
    assert chest in s.machines and s.dismantling is None
    assert s.events.count(("chest_not_empty",)) == 1


def test_out_of_reach_does_not_charge():
    s = make_state()
    m = build_now(s, "o2", spot(s))
    s.player.x, s.player.y = FAR
    hold(s, m, C.DISMANTLE_HOLD + 0.1)
    assert m in s.surface.machines and s.dismantling is None


# ---- App headless -------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_constructor_settings.json"
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


def point_at_tile(app, tile):
    """Põe o mouse no meio do tile (mundo)."""
    cam_x, cam_y = app.cam
    wx, wy = (tile[0] + 0.5) * C.TILE, (tile[1] + 0.5) * C.TILE
    app.mouse = (round((wx - cam_x) * app.zoom), round((wy - cam_y) * app.zoom))


def reset(app):
    s = app.state
    app.mode = "play"
    app.held = None
    app.placing = None
    app.right_held = False
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.surface.machines[:] = []
    s.player.x, s.player.y = C.SPAWN_POS
    set_ti(s, 0)
    return s


def test_tab_has_only_inventory_and_logs(app):
    reset(app)
    app.on_key(pygame.K_TAB)
    app.draw()
    assert [i for _, i in app.ui.inv_tab_rects] == [TAB_INVENTORY, TAB_LOGS]
    app.on_key(pygame.K_d)
    assert app.inv_tab == TAB_LOGS
    app.on_key(pygame.K_d)
    assert app.inv_tab == TAB_INVENTORY
    app.on_key(pygame.K_ESCAPE)
    assert app.mode == "play"


def test_e_with_constructor_opens_the_build_menu_and_click_builds(app):
    s = reset(app)
    give(s, constructor=1, iron=20, silicon=8)
    app.select_hotbar(0)
    point_at_tile(app, (s.player.tile[0] + 2, s.player.tile[1] + 3))
    app.on_key(pygame.K_e)
    assert app.mode == "build"
    app.draw()
    assert "CONSTRUIR" == app.ui.craft_label
    app.build_menu.select("o2")
    app.draw()
    click(app, next(r for r, k in app.ui.fabricator_buttons if k == "o2"))
    assert app.mode == "play" and app.placing == "o2"
    tile = spot(s)
    point_at_tile(app, tile)
    app.on_click(1)
    assert s.machine_at(tile) is not None and s.machine_at(tile).kind == "o2"
    assert app.placing == "o2"                          # continua construindo
    assert s.inventory.count("iron") == 10
    tile2 = (tile[0], tile[1] + 2)
    point_at_tile(app, tile2)
    app.on_click(1)                                     # 2º gerador: 10 Fe + 4 Si
    assert s.machine_at(tile2) is not None and s.inventory.count("iron") == 0
    tile3 = (tile[0] - 4, tile[1])
    point_at_tile(app, tile3)
    app.on_click(1)                                     # sem material: não constrói, continua no modo
    assert s.machine_at(tile3) is None and app.placing == "o2"
    assert app.hint().startswith("Falta 10 ferro")
    app.draw()                                          # fantasma vermelho (can_build False) sem quebrar


def test_switching_hotbar_slot_leaves_build_mode(app):
    s = reset(app)
    give(s, constructor=1)
    app.select_hotbar(0)
    app.placing = "lamp"
    app.select_hotbar(1)
    assert app.placing is None


def test_quick_right_click_does_nothing_and_holding_dismantles(app):
    s = reset(app)
    m = build_now(s, "lamp", spot(s))
    s.inventory.slots[:] = [None] * len(s.inventory)
    point_at_tile(app, (m.tx, m.ty))
    app.mouse = (app.mouse[0], app.mouse[1] - 4)        # no corpo da luminária
    assert app.hovered_machine() is m
    app.on_click(3)
    app.update(1 / 60)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=3, pos=app.mouse_window))
    app.handle_events()
    app.update(1 / 60)
    assert m in s.machines and not app.right_held and s.dismantling is None
    app.on_click(3)
    for _ in range(int(C.DISMANTLE_HOLD * 60) + 5):
        app.update(1 / 60)
        if m not in s.machines:
            break
        if s.dismantling is m:
            app.draw()                                  # barrinha e scanner ao contrário sem quebrar
    assert m not in s.machines and s.inventory.count("iron") == 1


def test_build_menu_fits_in_all_ui_sizes():
    pygame.font.init()
    from game import art
    from game.ui import UI
    for size in [(480, 270), (640, 360), (960, 540)]:
        ui = UI()
        ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
        s = make_state()
        give(s, constructor=1)
        menu = build_menu()
        ui.begin()
        ui.draw_fabricator(s, menu, lambda kind: pygame.Surface((40, 56)), 0.0, lambda item: art.icon("iron"),
                           build=True)
        assert ui.fabricator_panel.width <= size[0] and len(ui.fabricator_tabs) == len(C.FAB_TABS)
        assert ui.fabricator_batch == []                # sem ×1/×5 no construtor
