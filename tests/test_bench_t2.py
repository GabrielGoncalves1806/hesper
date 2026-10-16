"""v0.5 M1 · B2 · Bancada T2: diagrama fabricado no T1 que libera a máquina no construtor, construir/desmontar, E perto
abre o painel `bench="t2"`, a T2 lê só os diagramas dela (e os de máquina), fabricar gasta só o inventário, a
animação de N quadros pela largura da tira e o estado vazio do painel."""

import os
import random
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.fabricator import craft_kinds, t2_kinds, t2_menu  # noqa: E402
from game.render import Renderer, bench_frame_index  # noqa: E402
from game.systems import Controls, GameState, Machine  # noqa: E402
from game.ui import UI  # noqa: E402
from tests.helpers import build_now, give  # noqa: E402

SIZES = [(480, 270), (640, 360), (960, 540)]
FAR = (40.0 * C.TILE, 40.0 * C.TILE)


def make_state() -> GameState:
    return GameState(rng=random.Random(1))


def spot(s: GameState, dx: int = 1) -> tuple[int, int]:
    px, py = s.player.tile
    return px + dx, py


@pytest.fixture
def fake_recipe(monkeypatch):
    """Uma receita fake da T2 (o M1 não tem item próprio ainda): "gadget", 6 ferro + 3 silício."""
    machines = dict(C.MACHINES)
    machines["gadget"] = C.MachineType("gadget", "Gadget", "teste", {"iron": 6, "silicon": 3}, None, 0, 0,
                                       "icon_diagram", placeable=False)
    monkeypatch.setattr(C, "MACHINES", machines)
    monkeypatch.setattr(C, "T2_RECIPES", ("gadget",))
    return "gadget"


# ---- o diagrama da T2 no T1 ---------------------------------------------------------------------
def test_bench_is_locked_until_the_diagram_is_read():
    s = make_state()
    give(s, constructor=1, iron=20, silicon=10)
    assert s.build_status("workbench") == "blueprint"
    assert not s.can_build("workbench", spot(s, 2))
    assert build_now(s, "workbench", spot(s, 2)) is None


def test_craft_diagram_at_t1_then_read_unlocks_the_bench():
    s = make_state()
    give(s, iron=15, silicon=8)
    assert s.recipe_status("diagram_workbench") == "ok"
    assert s.craft("diagram_workbench")
    assert s.inventory.count("diagram_workbench") == 1
    assert s.inventory.count("iron") == 0 and s.inventory.count("silicon") == 0
    assert s.diagrams_held() == [("workbench", 1)]
    assert s.build_status("workbench") == "no_constructor"          # o diagrama ainda não foi lido
    assert s.recipe_status("workbench") == "blueprint"
    assert s.read_diagram("diagram_workbench", "t1") == "ok"
    assert "workbench" in s.blueprints and s.inventory.count("diagram_workbench") == 0
    give(s, constructor=1, iron=20, silicon=10)
    assert s.build_status("workbench") == "ok"


def test_diagram_recipe_is_gone_after_reading():
    s = make_state()
    give(s, iron=40, silicon=20)
    s.craft("diagram_workbench")
    s.read_diagram("diagram_workbench", "t1")
    assert s.recipe_status("diagram_workbench") == "known"
    assert not s.craft("diagram_workbench")                         # não fabrica de novo
    assert s.craft_many("diagram_workbench") == 0
    assert s.inventory.count("diagram_workbench") == 0 and s.inventory.count("iron") == 25


def test_diagram_is_not_in_the_wrecks():
    from game import wrecks
    assert "workbench" not in C.WRECK_DIAGRAMS
    assert "workbench" not in wrecks.missing_blueprints([])


def test_diagram_reads_at_t1_and_t2_because_it_is_a_machine_diagram():
    s = make_state()
    give(s, diagram_workbench=2)
    assert s.bench_reads("workbench", "t1") and s.bench_reads("workbench", "t2")
    assert s.read_diagram("diagram_workbench", "t2") == "ok"
    assert s.read_diagram("diagram_workbench", "t2") == "known"     # já liberada: não gasta
    assert s.inventory.count("diagram_workbench") == 1


def test_t2_reads_every_diagram_and_t1_only_its_own():
    """v0.6 Fundo M5: a Bancada T2 lê todos; os do tanque e do scanner (receita na T2) só se leem nela."""
    s = make_state()
    give(s, diagram_o2_tank=1, diagram_scanner=1, diagram_lamp_t2=1)
    assert s.read_diagram("diagram_scanner", "t1") == "wrong_bench"   # receita da Bancada T2
    assert s.read_diagram("diagram_o2_tank", "t1") == "wrong_bench"
    assert s.read_diagram("diagram_lamp_t2", "t1") == "ok"            # luminária forte é máquina: lê em qualquer uma
    assert s.read_diagram("diagram_scanner", "t2") == "ok"
    assert s.read_diagram("diagram_o2_tank", "t2") == "ok"


# ---- construir e desmontar ----------------------------------------------------------------------
def unlocked_state() -> GameState:
    s = make_state()
    s.blueprints.add("workbench")
    return s


def test_build_and_dismantle_the_bench():
    s = unlocked_state()
    m = build_now(s, "workbench", spot(s, 2), finish=False)
    assert m is not None and m.kind == "workbench" and m.build > 0 and m.is_bench
    assert s.inventory.count("iron") == 0 and s.inventory.count("silicon") == 0   # gastou só o inventário
    assert m.tiles == [spot(s, 2)]                                    # 1 tile
    for _ in range(40):
        s.update(0.05, Controls())
    assert m.build == 0
    s.inventory.slots[:] = [None] * len(s.inventory)                  # esvazia, pra ver o que volta
    t = 0.0
    while t < C.DISMANTLE_HOLD + 0.1:
        s.update(0.05, Controls(dismantle=m))
        t += 0.05
    assert m not in s.machines
    assert s.inventory.count("iron") == C.BENCH_COST["iron"]
    assert s.inventory.count("silicon") == C.BENCH_COST["silicon"]
    assert s.inventory.count("diagram_workbench") == 0                # o diagrama não volta
    assert "workbench" in s.blueprints                                # a receita continua liberada


def test_bench_works_in_the_cave_and_uses_one_kw():
    s = unlocked_state()
    assert C.POWER_USE["workbench"] == 1
    base = s.power.consumption
    build_now(s, "workbench", spot(s, 2))
    assert s.power.consumption == base + 1


def test_bench_is_in_the_build_menu_automation_tab():
    from game.fabricator import build_kinds
    assert "workbench" in build_kinds("automation")


# ---- E perto abre o painel / longe não -----------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_bench_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def reset(app):
    s = app.state
    app.mode = "play"
    app.held = None
    app.placing = None
    app.fab_bench = "t1"
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.surface.machines[:] = []
    s.player.x, s.player.y = C.SPAWN_POS
    s.blueprints.add("workbench")
    return s


def stand_near(s: GameState, m: Machine) -> None:
    """Os pés do player 24 px ao lado da base da bancada (dentro do alcance do E)."""
    ax, ay = m.anchor
    s.player.x, s.player.y = ax - 24, ay - 4


def aim_away(app):
    app.mouse = (0, 0)


def test_e_near_the_bench_opens_the_t2_panel_and_far_does_not(app):
    s = reset(app)
    m = build_now(s, "workbench", spot(s, 1))
    s.inventory.slots[:] = [None] * len(s.inventory)                    # sem o construtor na mão (ele abriria o menu dele)
    aim_away(app)
    s.player.x, s.player.y = FAR
    app.on_key(pygame.K_e)
    assert app.mode == "play"                                          # longe: nada abre (e fora da base, sem fabricador)
    stand_near(s, m)
    assert s.drill_distance(m) <= C.BENCH_REACH
    app.on_key(pygame.K_e)
    assert app.mode == "fabricator" and app.fab_bench == "t2" and app.open_bench is m
    assert app.menu_of_mode() is app.fab_t2
    app.draw()
    assert app.ui.fabricator_panel is not None
    app.on_key(pygame.K_e)
    assert app.mode == "play"


def test_capsule_fabricator_is_still_t1(app):
    s = reset(app)
    app.fab_bench = "t2"                                               # sobra de uma bancada aberta antes
    aim_away(app)
    assert s.in_base_zone()
    app.on_key(pygame.K_e)
    assert app.mode == "fabricator" and app.fab_bench == "t1" and app.menu_of_mode() is app.fab
    app.on_key(pygame.K_e)


def test_bench_still_building_does_not_open(app):
    s = reset(app)
    build_now(s, "workbench", spot(s, 1), finish=False)
    aim_away(app)
    assert s.nearby_bench() is None


# ---- fabricar na T2 gasta só o inventário ---------------------------------------------------------
def test_craft_at_t2_spends_only_the_inventory(fake_recipe):
    s = unlocked_state()
    m = build_now(s, "workbench", spot(s, 1))
    tx, ty = C.BASE_CENTER[0] // C.TILE + 3, C.BASE_CENTER[1] // C.TILE + 3
    chest = Machine("chest", tx, ty)
    chest.storage.add("iron", 50)
    chest.storage.add("silicon", 50)
    s.surface.machines.append(chest)
    assert chest in s.base_chests()
    assert s.recipe_status(fake_recipe, inv_only=True) == "missing"
    assert not s.craft(fake_recipe, "t2", m)                          # os baús não contam
    give(s, iron=6, silicon=3)
    assert s.craft(fake_recipe, "t2", m)
    assert s.inventory.count(fake_recipe) == 1
    assert s.inventory.count("iron") == 0 and s.inventory.count("silicon") == 0
    assert chest.storage.count("iron") == 50 and chest.storage.count("silicon") == 50
    assert m.work == C.BENCH_WORK_TIME                                # ela anima
    assert not s.craft(fake_recipe)                                   # no T1 essa receita não existe


def test_craft_at_t2_works_outside_the_base(fake_recipe):
    s = unlocked_state()
    s.player.x, s.player.y = FAR
    assert not s.in_base_zone()
    give(s, iron=12, silicon=6)
    assert s.craft_many(fake_recipe, bench="t2") == 2
    assert s.inventory.count(fake_recipe) == 2


def test_t1_recipes_do_not_craft_on_t2():
    s = make_state()
    give(s, iron=5)
    assert not s.craft("constructor", "t2")


def test_work_timer_runs_down_and_the_frame_follows_it():
    s = unlocked_state()
    m = build_now(s, "workbench", spot(s, 1))
    assert bench_frame_index(m.work) == 0                              # parada
    m.work = C.BENCH_WORK_TIME
    seen = []
    while m.work > 0:
        seen.append(bench_frame_index(m.work))
        s.update(0.05, Controls())
    assert seen[0] == 0 and max(seen) == 7 and seen == sorted(seen)    # 0 -> 7 uma vez
    assert bench_frame_index(m.work) == 0                              # terminou: volta pra parada


def test_app_craft_on_t2_animates_the_open_bench(app, fake_recipe):
    s = reset(app)
    s.crafted[fake_recipe] = 0                                          # o estado do App nasceu antes da receita fake
    m = build_now(s, "workbench", spot(s, 1))
    s.inventory.slots[:] = [None] * len(s.inventory)
    give(s, iron=6, silicon=3)
    stand_near(s, m)
    aim_away(app)
    app.on_key(pygame.K_e)
    assert app.mode == "fabricator" and app.fab_bench == "t2"
    app.fab_t2.select(fake_recipe)
    app.draw()
    assert app.ui.craft_label == "FABRICAR"
    app.on_key(pygame.K_RETURN)
    assert s.inventory.count(fake_recipe) == 1 and m.work > 0 and app.mode == "play"


# ---- animação com N quadros pela largura -----------------------------------------------------------
def test_bench_strip_has_eight_frames_read_from_the_width():
    pygame.init()
    pygame.display.set_mode((64, 64))
    r = Renderer(Sprites())
    still = r.surface("machine_workbench", lambda: art.machine("workbench"))[0]
    assert still.get_size() == C.BENCH_SPRITE_SIZE
    frames = r.anim_frames("machine_workbench", still)
    assert frames is not None and len(frames) == 8
    assert all(f.get_size() == C.BENCH_SPRITE_SIZE for f in frames)
    assert r.anim_surface("machine_workbench", still, 9) is frames[1]  # dá a volta pelo nº de quadros


def test_other_machines_keep_four_frames():
    pygame.init()
    pygame.display.set_mode((64, 64))
    r = Renderer(Sprites())
    still = r.surface("machine_o2", lambda: art.machine("o2"))[0]
    frames = r.anim_frames("machine_o2", still)
    assert frames is not None and len(frames) == 4


def test_strip_width_must_be_a_multiple_of_the_still():
    pygame.init()
    pygame.display.set_mode((64, 64))
    r = Renderer(Sprites())
    r.sprites._cache["anim/anim_fake"] = pygame.Surface((70, 10), pygame.SRCALPHA)
    assert r.anim_frames("fake", pygame.Surface((32, 10))) is None
    r.sprites._cache["anim/anim_fake2"] = pygame.Surface((96, 10), pygame.SRCALPHA)
    assert len(r.anim_frames("fake2", pygame.Surface((32, 10)))) == 3


def test_bench_only_animates_while_crafting():
    pygame.init()
    pygame.display.set_mode((64, 64))
    r = Renderer(Sprites())
    m = Machine("workbench", 5, 5)
    assert r.machine_anim_index(m, True, 3.3) == 0
    m.work = C.BENCH_WORK_TIME - 0.6
    assert r.machine_anim_index(m, True, 3.3) == 2


# ---- painel ---------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def icon(_item):
    return art.icon("iron")


@pytest.mark.parametrize("size", SIZES)
def test_empty_t2_panel_is_clean(ui, size, monkeypatch):
    monkeypatch.setattr(C, "T2_RECIPES", ())                           # o estado vazio (sem a mochila)
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = make_state()
    give(s, diagram_workbench=1, diagram_scanner=1)
    ui.begin()
    ui.draw_fabricator(s, t2_menu(), lambda kind: art.icon("iron"), 0.0, bench="t2")
    panel = ui.fabricator_panel
    assert t2_menu().tab_id == "tools"                                  # M5: a aba "Bancada" vazia some, sobram as do T1
    assert [d for _, d in ui.diagram_buttons] == ["scanner", "workbench"]          # M5: a T2 lê a do scanner também
    for row, _ in ui.diagram_rows:
        assert panel.contains(row)


@pytest.mark.parametrize("size", SIZES)
def test_t2_panel_with_a_recipe_fits(ui, size, fake_recipe):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = make_state()
    give(s, iron=6, silicon=3)
    ui.begin()
    ui.draw_fabricator(s, t2_menu(), lambda kind: art.icon("iron"), 0.0, bench="t2")
    assert [k for _, k in ui.fabricator_rows] == [fake_recipe]
    assert [k for _, k in ui.fabricator_buttons] == [fake_recipe]
    assert ui.craft_label == "FABRICAR"
    for rect, _ in ui.fabricator_rows + ui.fabricator_buttons:
        assert ui.fabricator_panel.contains(rect)


def test_t2_panel_title_and_header(ui, monkeypatch):
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    s = make_state()
    seen = []
    orig = ui.window
    monkeypatch.setattr(ui, "window", lambda *a, **k: (seen.append(a[4:6]), orig(*a, **k))[1])
    ui.begin()
    ui.draw_fabricator(s, t2_menu(), icon, 0.0, bench="t2")
    ui.draw_fabricator(s, __import__("game.fabricator", fromlist=["x"]).craft_menu(), icon, 0.0)
    assert seen[0] == ("Bancada T2", "MATERIAIS: SÓ O INVENTÁRIO")
    assert seen[1] == ("Fabricador", "MATERIAIS: INVENTÁRIO + BAÚS")


def test_known_diagram_recipe_shows_ja_lido(ui):
    from game.fabricator import craft_menu
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    s = make_state()
    s.blueprints.add("workbench")
    give(s, iron=15, silicon=8)
    menu = craft_menu()
    menu.select("diagram_workbench")
    ui.begin()
    ui.draw_fabricator(s, menu, icon, 0.0)
    assert ui.craft_label == "JÁ LIDO"
    assert ui.fabricator_buttons == []


def test_t1_panel_has_diagram_recipe_ok(ui):
    from game.fabricator import craft_menu
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    s = make_state()
    give(s, iron=15, silicon=8)
    menu = craft_menu()
    menu.select("diagram_workbench")
    ui.begin()
    ui.draw_fabricator(s, menu, icon, 0.0)
    assert ui.craft_label == "FABRICAR" and [k for _, k in ui.fabricator_buttons] == ["diagram_workbench"]


# ---- save: máquina comum ----------------------------------------------------------------------------
def test_bench_roundtrips_in_the_save_without_a_new_field():
    from game import save
    s = unlocked_state()
    m = build_now(s, "workbench", spot(s, 2))
    data = save.machine_to_dict(m)
    assert data == {"kind": "workbench", "tx": m.tx, "ty": m.ty, "rotation": 0}
    loaded = save.machine_from_dict(data)
    assert loaded.is_bench and loaded.work == 0 and loaded.build == 0


def test_backpack_is_a_t2_recipe_and_not_t1():
    s = unlocked_state()
    m = build_now(s, "workbench", spot(s, 1))
    give(s, iron_ingot=5)
    assert not s.craft("backpack")                                    # o T1 não fabrica a mochila
    assert s.craft("backpack", "t2", m) and s.inventory.count("backpack") == 1
    assert "backpack" not in craft_kinds("suit") and t2_kinds("t2") == list(C.T2_RECIPES)


@pytest.mark.parametrize("bench", ["t1", "t2"])
def test_every_recipe_detail_draws(ui, bench):
    """v0.6: abrir a receita do diagrama do Baú grande no T1 crashava (KeyError 'iron_ingot' no RESOURCE_NAME).
    Desenha o detalhe de toda receita de todas as abas, com e sem Ti, sem o material (linha "FALTAM")."""
    from game.fabricator import craft_menu
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    for ti in (0, 100_000):
        s = make_state()
        s.indices["o2"] = ti
        menu = craft_menu() if bench == "t1" else t2_menu()
        for tab in range(len(menu.tabs)):
            menu.tab = tab
            for kind in menu.kinds_of(menu.tabs[tab][0]):
                menu.select(kind)
                ui.begin()
                ui.draw_fabricator(s, menu, icon, 0.0, **({"bench": "t2"} if bench == "t2" else {}))
