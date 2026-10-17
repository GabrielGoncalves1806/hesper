"""Redesign B2 da UI (reports/design/ui_redesign/): controle segmentado das Opções, toggles de drone (o ícone
é o botão), seletor ×1/×5 do fabricador, "USADO EM" do inventário e o mouse no mapa (bug do dono: o mapa
só fechava com M/Esc). Desenho headless (SDL dummy) nos 3 tamanhos de interface e cliques pelo App."""

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
from game.systems import GameState, Machine  # noqa: E402
from game.ui import UI, used_in  # noqa: E402
from tests.helpers import give  # noqa: E402

SIZES = [(480, 270), (640, 360), (960, 540)]


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    return UI()


def icon(_item):
    return art.icon("iron")


def base_chest(s: GameState, **items) -> Machine:
    tx, ty = C.BASE_CENTER[0] // C.TILE + 3, C.BASE_CENTER[1] // C.TILE + 3
    chest = Machine("chest", tx, ty)
    for item, n in items.items():
        chest.storage.add(item, n)
    s.surface.machines.append(chest)
    return chest


# ---- controle segmentado das Opções -------------------------------------------------------------
@pytest.mark.parametrize("size", SIZES)
def test_option_segments_hit_test(ui, size):
    """Cada segmento (Não|Sim, os 4 zooms, os 3 tamanhos de interface) tem o próprio retângulo: o centro dele
    devolve (linha, valor) dele, os segmentos de uma linha não se sobrepõem e ficam dentro da linha."""
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    mix = {**settings.DEFAULTS, "zoom": 1.5, "ui_size": "media", "fullscreen": False}
    ui.draw_pause("volumes", 0, mix)
    n = len(ui.VOLUME_ROWS)
    by_row: dict[int, list] = {}
    for rect, (index, value) in ui.pause_segments:
        assert ui.segment_at(rect.center) == (index, value)
        by_row.setdefault(index, []).append((rect, value))
    assert sorted(by_row) == [n, n + 1, n + 2]
    assert [v for _, v in by_row[n]] == [False, True]
    assert [v for _, v in by_row[n + 1]] == list(C.ZOOM_LEVELS)
    assert [v for _, v in by_row[n + 2]] == ["grande", "media", "pequena"]
    for index, segs in by_row.items():
        row = ui.pause_items[index]
        for (a, _), (b, _) in zip(segs, segs[1:]):
            assert a.right <= b.left
        assert all(row.contains(r) for r, _ in segs), (index, row)
    # fora de qualquer segmento (rótulo da linha, slider): nada
    assert ui.segment_at((ui.pause_items[n].x + 4, ui.pause_items[n].centery)) is None
    assert ui.segment_at(ui.pause_sliders[0].center) is None


# ---- painel do baú: toggles de drone e lote ------------------------------------------------------
@pytest.mark.parametrize("size", SIZES)
def test_drone_toggles_hit_test(ui, size):
    """Envia/Recebe: um botão por material (o ícone é o botão), Lote: 1/5/10/20. Mesmo hit-test de antes
    (logistics_at): cada botão devolve o seu (tipo, valor), sem sobrepor. A drill só tem o Envia do minério dela."""
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = GameState(rng=random.Random(1))
    chest = Machine("chest", 0, 0)
    chest.sends.add("iron")
    ui.begin()
    ui.draw_inventory(s.inventory, chest, 0, icon, (0, 0))
    values = [v for _, v in ui.logistics_buttons]
    assert values == ([("send", r) for r in C.LOGISTIC_ITEMS] + [("recv", r) for r in C.LOGISTIC_ITEMS]
                      + [("batch", n) for n in C.DRONE_BATCH_OPTIONS])
    rects = [r for r, _ in ui.logistics_buttons]
    for rect, value in ui.logistics_buttons:
        assert ui.logistics_at(rect.center) == value
        assert rect.w >= 16 and rect.h >= 16                       # o ícone (16×16) é o botão: moldura justa
        assert pygame.Rect(0, 0, *size).contains(rect)
    assert all(a.collidelist([b for b in rects if b is not a]) < 0 for a in rects)
    assert ui.logistics_summary(chest) == "envia ferro"
    drill = Machine("drill", 0, 0, resource="silicon", chip=True)       # v0.6 M2: sem chip a seção DRONES some
    ui.begin()
    ui.draw_inventory(s.inventory, drill, 0, icon, (0, 0))
    assert [v for _, v in ui.logistics_buttons if v[0] != "batch"] == [("send", "silicon")]


def test_logistics_summary_texts(ui):
    chest = Machine("chest", 0, 0)
    assert ui.logistics_summary(chest) == "nada configurado"
    chest.sends.update({"iron", "ice"})
    chest.receives.add("silicon")
    assert ui.logistics_summary(chest) == "envia ferro, gelo · recebe silício"


# ---- "USADO EM" ----------------------------------------------------------------------------------
def test_used_in_is_the_reverse_of_the_costs():
    for item in (*C.RESOURCES, "drone", "chest"):
        expected = [k for k in C.MACHINE_ORDER if item in C.MACHINES[k].cost]
        assert used_in(item) == expected
    assert "melter" in used_in("ice") and "lamp_t2" in used_in("ice") and "o2" not in used_in("ice")
    assert used_in("o2") == []                          # máquina pronta não entra em receita


def test_detail_panel_shows_hovered_item_and_hides_unfound_blueprints(ui):
    """Tab: o painel de detalhe mostra o item debaixo do mouse com "USADO EM" (sem as receitas de projeto ainda
    não encontrado); sem mouse num slot, mostra o da hotbar selecionado."""
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    s = GameState(rng=random.Random(1))
    s.inventory.slots[:] = [None] * len(s.inventory)
    give(s, iron=10)
    s.inventory.slots[9] = type(s.inventory.slots[0])("ice", 18)
    s.blueprints.discard("lamp_t2")
    ui.begin()
    ui.draw_inventory(s.inventory, None, 0, icon, (0, 0), equipment=s.equipment, state=s)
    assert ui.detail_item == "iron"                     # nada no mouse: o da hotbar (slot 0)
    ice = next(r for r, inv, i in ui.slot_rects if i == 9)
    ui.begin()
    ui.draw_inventory(s.inventory, None, 0, icon, ice.center, equipment=s.equipment, state=s)
    assert ui.detail_item == "ice"
    assert "lamp_t2" not in ui.detail_uses and "melter" in ui.detail_uses
    s.blueprints.add("lamp_t2")
    ui.begin()
    ui.draw_inventory(s.inventory, None, 0, icon, ice.center, equipment=s.equipment, state=s)
    assert "lamp_t2" in ui.detail_uses


# ---- App headless: cliques ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_ui_b2_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def to_window(app, point):
    from game import viewport
    (x, y, _, _), k, _ = viewport.ui_layout(app.window.get_size(), app.settings["ui_size"])
    return round(x + point[0] * k), round(y + point[1] * k)


def click(app, target, button=1):
    point = target.center if isinstance(target, pygame.Rect) else target
    pos = to_window(app, point)
    app.mouse_window = pos
    app.mouse = app.window_to_canvas(pos)
    app.on_click(button)


def reset(app):
    s = app.state
    app.mode = "play"
    app.held = None
    app.placing = None
    s.inventory.slots[:] = [None] * len(s.inventory)
    return s


def test_click_option_segments_changes_zoom_and_interface(app):
    reset(app)
    app.open_pause()
    app.pause_screen, app.pause_selected = "volumes", 0
    app.draw()
    n = len(UI.VOLUME_ROWS)
    seg = next(r for r, (i, v) in app.ui.pause_segments if i == n + 1 and v == 2.0)
    click(app, seg)
    assert app.zoom == 2.0 and app.pause_selected == n + 1
    app.draw()
    seg = next(r for r, (i, v) in app.ui.pause_segments if i == n + 2 and v == "pequena")
    click(app, seg)
    assert app.settings["ui_size"] == "pequena"
    app.draw()
    seg = next(r for r, (i, v) in app.ui.pause_segments if i == n + 1 and v == 1.0)
    click(app, seg)
    assert app.zoom == 1.0
    app.set_ui_size("media")
    app.set_mode("play")


def test_click_drone_toggles_in_the_chest(app):
    s = reset(app)
    chest = base_chest(s, iron=5)
    app.open_chest = app.renderer.open_chest = chest
    app.mode = "chest"
    app.draw()
    send_iron = next(r for r, v in app.ui.logistics_buttons if v == ("send", "iron"))
    click(app, send_iron)
    assert "iron" in chest.sends
    app.draw()
    click(app, next(r for r, v in app.ui.logistics_buttons if v == ("send", "iron")))
    assert "iron" not in chest.sends
    app.draw()
    click(app, next(r for r, v in app.ui.logistics_buttons if v == ("recv", "ice")))
    assert "ice" in chest.receives
    app.draw()
    click(app, next(r for r, v in app.ui.logistics_buttons if v == ("batch", 20)))
    assert chest.batch == 20
    app.set_mode("play")
    s.surface.machines.remove(chest)


def test_batch_selector_crafts_five_without_shift(app):
    """Fabricador: ×5 faz o FABRICAR (e o Enter) fazer até 5 sem segurar Shift; ×1 volta a fazer 1."""
    s = reset(app)
    s.player.x, s.player.y = C.BASE_CENTER[0], C.BASE_CENTER[1] + 40
    give(s, copper_ingot=40)                              # v0.6 Fundo M5: lote com os fios (o construtor é de uma vez só)
    app.hotbar_selected = 7                               # a mão vazia (o E não abre o construtor)
    app.mode = "play"
    app.on_key(pygame.K_e)
    assert app.mode == "fabricator"
    app.fab.select("wire")
    app.draw()
    assert [n for _, n in app.ui.fabricator_batch] == [1, C.CRAFT_BATCH]
    click(app, next(r for r, n in app.ui.fabricator_batch if n == C.CRAFT_BATCH))
    assert app.fab.batch == C.CRAFT_BATCH
    app.draw()
    click(app, next(r for r, k in app.ui.fabricator_buttons if k == "wire"))
    assert s.inventory.count("wire") == 5 * C.CRAFT_YIELD["wire"] and app.mode == "fabricator"   # M5: continua aberto
    app.draw()
    click(app, next(r for r, n in app.ui.fabricator_batch if n == 1))
    assert app.fab.batch == 1
    app.on_key(pygame.K_RETURN)
    assert s.inventory.count("wire") == 6 * C.CRAFT_YIELD["wire"]
    app.set_mode("play")


def test_build_menu_has_no_batch_selector(app):
    """v0.5 M1: o menu do construtor reaproveita o painel, mas sem ×1/×5 (constrói um por clique no mundo)."""
    s = reset(app)
    s.player.x, s.player.y = 40.0 * C.TILE, 40.0 * C.TILE
    give(s, constructor=1, iron=20, silicon=20)
    app.hotbar_selected = 0
    app.mouse = (0, 0)
    app.on_key(pygame.K_e)
    assert app.mode == "build"
    app.build_menu.select("lamp")
    app.draw()
    assert app.ui.fabricator_batch == [] and app.ui.craft_label == "CONSTRUIR"
    app.set_mode("play")


def test_missing_button_says_what_is_missing(app):
    s = reset(app)
    s.player.x, s.player.y = C.BASE_CENTER[0], C.BASE_CENTER[1] + 40
    for k in s.indices:
        s.indices[k] = 0
    s.indices["o2"] = 600                                 # aquecedor liberado (Ti 500)
    for chest in list(s.base_chests()):
        s.surface.machines.remove(chest)
    give(s, iron=3)                                       # fabricador: o construtor custa 5
    app.hotbar_selected = 7
    app.on_key(pygame.K_e)
    assert app.mode == "fabricator"
    app.fab.select("constructor")
    app.draw()
    assert app.ui.fabricator_buttons == []               # falta: não tem FABRICAR clicável
    assert app.ui.craft_label == "FALTAM 2 FERRO"
    app.set_mode("play")
    reset(app)
    give(s, constructor=1, iron=30, silicon=6, magmatite=3)
    app.hotbar_selected = 0
    app.mouse = (0, 0)
    app.on_key(pygame.K_e)
    assert app.mode == "build"
    app.build_menu.select("heater")
    app.draw()
    assert app.ui.craft_label == "FALTAM 2 SILÍCIO"      # 8 de silício, tem 6
    assert [k for _, k in app.ui.fabricator_buttons] == ["heater"]   # no construtor escolhe mesmo assim
    app.build_menu.select("o2")
    app.draw()
    assert app.ui.craft_label == "CONSTRUIR" and [k for _, k in app.ui.fabricator_buttons] == ["o2"]
    app.build_menu.select("o2_t2")
    app.draw()
    assert app.ui.craft_label == "LIBERA EM TI 10.000" and app.ui.fabricator_buttons == []
    app.set_mode("play")


# ---- mouse no mapa (bug do dono) -----------------------------------------------------------------
def open_map(app):
    s = app.state
    s.equipment.slots["scanner"] = "scanner"
    app.mode = "play"
    app.open_map()
    assert app.mode == "map"
    app.draw()
    return s


def test_map_close_button_and_click_outside(app):
    reset(app)
    open_map(app)
    ui = app.ui
    assert ui.map_close_rect is not None and ui.map_rect.contains(ui.map_close_rect)
    click(app, ui.map_close_rect)
    assert app.mode == "play"
    open_map(app)
    click(app, ui.map_rect.center)                       # dentro da janela: continua aberto
    assert app.mode == "map"
    click(app, (ui.map_rect.left + 4, ui.map_rect.bottom - 4))
    assert app.mode == "map"
    click(app, (1, 1))                                   # fora da janela: fecha
    assert app.mode == "play"


def test_map_marker_tooltip(app):
    s = reset(app)
    open_map(app)
    ui = app.ui
    names = [e.title for _, e in ui.map_markers]
    assert "Você" in names and "Base" in names
    you = next(r for r, e in ui.map_markers if e.category == "you")
    assert ui.map_marker_at(you.center).title == "Você"         # base embaixo: "você" tem a prioridade
    assert ui.map_rect.contains(you)
    corner = (ui.map_rect.left + 2, ui.map_rect.top + 2)
    assert ui.map_marker_at(corner) is None
    # o tooltip vai na última camada, por cima da textura do mapa (antes até o cursor sumia embaixo dela)
    app.mouse_window = to_window(app, you.center)
    app.draw()
    assert ui.map_hover is not None and ui.map_hover.title == "Você"
    rect = ui.map_tooltip_rect(ui.map_hover, you.center)
    assert not rect.collidepoint(you.center) and ui.map_area.contains(rect)
    assert ui.surf.get_at(rect.center).a == 255          # a caixa do tooltip está na camada de cima
    assert ui.surf.get_at((round(you.centerx), round(you.centery))).a > 0     # e o cursor também
    app.set_mode("play")
    assert s.layer == "surface"


def test_map_clicks_do_not_reach_the_game(app):
    """Com o mapa aberto, nenhum clique minera, coloca ou desmonta, e a rodinha não troca a hotbar."""
    s = reset(app)
    give(s, iron=5)
    s.inventory.slots[2] = type(s.inventory.slots[0])("lamp", 2)
    app.hotbar_selected = 0
    machines = len(s.machines)
    open_map(app)
    ui = app.ui
    for point, button in ((ui.map_rect.center, 1), (ui.map_rect.center, 3), ((1, 1), 3)):
        click(app, point, button)
        assert app.mode == "map" and not app.mouse_held and app.placing is None
    app.update(1 / 60)
    assert app.controls().mine_tile is None and len(s.machines) == machines
    pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=to_window(app, ui.map_rect.center), button=5))
    app.handle_events()
    assert app.hotbar_selected == 0 and app.mode == "map"
    # o clique que fecha (fora da janela) também não vira mineração
    click(app, (1, 1))
    assert app.mode == "play" and not app.mouse_held
    app.update(1 / 60)
    assert app.controls().mine_tile is None


# ---- HUD: a dica comprida não encavala com a pílula do nome do item -------------------------------
@pytest.mark.parametrize("size", SIZES)
def test_long_hint_clear_of_hotbar_and_item_name(ui, size):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = GameState(rng=random.Random(1))
    give(s, iron=10)
    icons = {r: art.icon(r) for r in C.RESOURCES}
    hint = "[E] Drill · [Shift+E] coletar 20 Silício e mais um texto bem comprido pra subir"
    for _ in range(2):                                   # 2º frame: a dica já sabe onde ficou a pílula
        ui.begin()
        ui.draw_hud(s, 0.0, hint, icons)
        ui.draw_hotbar(s.inventory, 0, icon, show_name=True)
    assert ui.name_pill is not None
    hint_rect = next(r for r in ui.hud_rects if r.h == 15 and r.right == size[0] - 6)
    hotbar = pygame.Rect(ui.hotbar_x - 4, ui.hotbar_y - 11, 182, 35)
    assert not hint_rect.colliderect(ui.name_pill) and not hint_rect.colliderect(hotbar)


@pytest.mark.parametrize("size", SIZES)
def test_objective_card_wraps_inside_and_leaves_the_top_gap(ui, size):
    """O cartão do objetivo não alarga com texto comprido (quebra a linha) e fica à esquerda do vão do topo,
    onde entram o banner de estágio e o aviso de projeto."""
    from game.objectives import ObjectiveLine as Line
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    lines = [Line("Minere gelo e fabrique um Derretedor", "current"), Line("Desça na caverna pela cratera [E]", "next")]
    ui.draw_objectives(lines)
    card = ui.hud_rects[-1]
    assert card.x == 6 and card.right <= ui.BANNER_GAP[0] and card.w == ui.objective_w
    for style, text in ui.objective_lines(lines):
        assert ui.body.size(text)[0] <= card.w - 12, text
    if ui.objective_w > ui.OBJECTIVE_W:                  # alargou: só se o vão do topo continua folgado
        assert ui.BANNER_GAP[1] - ui.BANNER_GAP[0] >= ui.TOP_GAP_MIN
    else:
        assert size == (480, 270)


@pytest.mark.parametrize("size", SIZES)
def test_stage_banner_text_fits_in_the_top_gap(ui, size):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    left, right = ui.BANNER_GAP
    for stage, s in enumerate(C.STAGES, 1):
        ui.begin()
        ui.draw_banner(stage, 1.0)
        rect = ui.hud_rects[-1]
        assert left < rect.left and rect.right < right, (size, stage, rect)
        assert max(ui.font.size(s.title)[0], ui.body.size(s.subtitle)[0]) <= rect.w - 4, (size, stage)


def test_map_surface_is_opaque_even_when_the_texture_has_an_alpha_channel(ui):
    """Regressão: na janela real do macOS o formato padrão é ARGB, e o mapa aberto saía preto (textura com
    alfa 0) e com os marcadores virando quadrados. A superfície do mapa tem que ser opaca, sem canal alfa."""
    from game.map_view import MapView
    tex = pygame.Surface((192, 192), pygame.SRCALPHA)       # simula o formato com alfa da janela de verdade
    tex.fill((138, 106, 78, 255))
    view = MapView(1)
    area = pygame.Rect(0, 0, 444, 196)
    view.set_area(area.w, area.h)
    surf, _k, _off = ui._map_surface(tex, view, area)
    assert surf.get_masks()[3] == 0 and surf.get_flags() & pygame.SRCALPHA == 0
    assert surf.get_at((surf.get_width() // 2, surf.get_height() // 2))[:3] == (138, 106, 78)


# ---- Diagramas no fabricador (v0.5 M1) ---------------------------------------------------------
@pytest.mark.parametrize("size", SIZES)
def test_diagram_area_fits_and_has_read_buttons(ui, size):
    """Área "Diagramas" embaixo da lista: uma linha por diagrama do inventário com LER, dentro do painel e sem
    cobrir a lista de receitas, nos 3 tamanhos de interface."""
    from game.fabricator import craft_menu
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = GameState(rng=random.Random(1))
    give(s, diagram_o2_tank=2, diagram_scanner=1, diagram_lamp_t2=1)
    ui.begin()
    menu = craft_menu()
    ui.draw_fabricator(s, menu, lambda kind: art.icon("iron"), 0.0, bench="t2")   # v0.6 Fundo M5: a T2 lê todos
    assert [d for _, d in ui.diagram_rows] == ["o2_tank", "scanner", "lamp_t2"]
    assert [d for _, d in ui.diagram_buttons] == ["o2_tank", "scanner", "lamp_t2"]
    panel = ui.fabricator_panel
    last_recipe = max(r.bottom for r, _ in ui.fabricator_rows)
    for row, _ in ui.diagram_rows:
        assert panel.contains(row) and row.top > last_recipe, (size, row)
    for btn, _ in ui.diagram_buttons:
        assert any(row.contains(btn) for row, _ in ui.diagram_rows)
    s.blueprints.add("scanner")                        # já liberada: o botão apaga (não gasta)
    ui.begin()
    ui.draw_fabricator(s, menu, lambda kind: art.icon("iron"), 0.0, bench="t2")
    assert "scanner" not in [d for _, d in ui.diagram_buttons]
    ui.begin()
    ui.draw_fabricator(s, menu, lambda kind: art.icon("iron"), 0.0)               # o tanque é da T2: sem LER no T1
    assert [d for _, d in ui.diagram_buttons] == ["lamp_t2"]


def test_diagram_area_empty_and_hidden_in_build_menu(ui):
    from game.fabricator import build_menu, craft_menu
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    s = GameState(rng=random.Random(1))
    ui.begin()
    ui.draw_fabricator(s, craft_menu(), lambda kind: art.icon("iron"), 0.0)
    assert ui.diagram_rows == [] and ui.diagram_buttons == []
    give(s, diagram_scanner=1)
    ui.begin()
    ui.draw_fabricator(s, build_menu(), lambda kind: art.icon("iron"), 0.0, build=True)
    assert ui.diagram_rows == []


def test_locked_recipe_says_diagram(ui):
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    from game.fabricator import t2_menu
    s = GameState(rng=random.Random(1))
    ui.begin()
    menu = t2_menu()                                    # v0.6 Fundo M5: o tanque mora na Bancada T2
    menu.select("o2_tank")
    ui.draw_fabricator(s, menu, lambda kind: art.icon("iron"), 0.0, bench="t2")
    assert ui.craft_label == "SEM DIAGRAMA"


def test_click_read_spends_diagram_and_unlocks(app):
    s = reset(app)
    give(s, diagram_lamp_t2=1)                          # v0.6 Fundo M5: o do tanque só se lê na Bancada T2
    s.blueprints.discard("lamp_t2")
    app.fab.diag = None
    app.mode = "fabricator"
    app.draw()
    button = next(r for r, d in app.ui.diagram_buttons if d == "lamp_t2")
    click(app, button)
    assert "lamp_t2" in s.blueprints and s.inventory.count("diagram_lamp_t2") == 0
    app.draw()
    assert app.ui.diagram_rows == []
    app.mode = "play"


def test_keyboard_reads_diagram_from_the_list(app):
    s = reset(app)
    give(s, diagram_lamp_t2=1)                          # v0.6 Fundo M5: o do scanner só se lê na Bancada T2
    s.blueprints.discard("lamp_t2")
    app.fab.diag = None
    app.fab.tab = 0
    app.mode = "fabricator"
    last = len(app.fab.kinds) - 1
    app.fab.selected[0] = last
    app.on_key(pygame.K_s)                              # fim da lista -> foco no 1º diagrama
    assert app.fab.diag == 0
    app.on_key(pygame.K_RETURN)
    assert "lamp_t2" in s.blueprints and s.inventory.count("diagram_lamp_t2") == 0
    assert app.fab.diag is None                         # acabaram os diagramas: o foco volta pra lista
    app.mode = "play"


def test_read_repeated_in_app_keeps_diagram(app):
    s = reset(app)
    give(s, diagram_scanner=1)
    s.blueprints.add("scanner")
    app.mode = "fabricator"
    app.read_diagram("scanner")
    assert s.inventory.count("diagram_scanner") == 1
    app.mode = "play"
