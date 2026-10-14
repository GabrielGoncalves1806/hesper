"""Mapa aberto (M), panorâmico do redesign B2: câmera (zoom ancorado, limites, arrasto, centralizar), camadas
(Q/E, caverna travada antes de descer), filtros com persistência no settings.json, tooltip com distância e
direção e nada vazando pro jogo. Lógica pura em game/map_view.py; o resto pelo App headless (SDL dummy)."""

import json
import os
import random
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import layers  # noqa: E402
from game import map_view as MV  # noqa: E402
from game import settings  # noqa: E402
from game.map_view import MapView  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402

AREA = (444, 196)                 # área do mapa no Grande (px da UI)


def view_at(size=(192, 192), zoom=2, center=(96, 96)):
    v = MapView(zoom)
    v.size = size
    v.set_area(*AREA)
    v.center_on(*center)
    return v


def edges(v: MapView):
    ox, oy = v.origin()
    vw, vh = v.visible_tiles()
    return ox, oy, ox + vw, oy + vh


# ---- câmera (lógica pura) -------------------------------------------------------------------------
@pytest.mark.parametrize("anchor", [(100, 50), (10, 180), (AREA[0] / 2, AREA[1] / 2), (400, 20)])
def test_wheel_zoom_keeps_the_tile_under_the_cursor(anchor):
    """No 3× e no 4× a superfície (192) passa da área nos dois eixos: o tile debaixo do mouse fica parado.
    (No 2× do Grande a largura cabe, 222 tiles > 192, e o eixo x fica travado no meio.)"""
    v = view_at(zoom=3)
    before = v.tile_at(*anchor)
    assert v.zoom_step(1, anchor) and v.zoom == 4
    assert v.tile_at(*anchor) == pytest.approx(before)
    assert v.zoom_step(-1, anchor) and v.zoom == 3
    assert v.tile_at(*anchor) == pytest.approx(before)
    v.set_zoom(2, anchor)
    assert v.cx == 96                                          # 2×: largura cabe, x centrado e travado
    assert v.tile_at(*anchor)[1] == pytest.approx(before[1])   # o y continua ancorado


def test_zoom_levels_are_integers_1_to_4_and_keys_anchor_in_the_center():
    v = view_at(zoom=4)
    assert not v.zoom_step(1) and v.zoom == 4                 # passou do 4×: nada muda
    center = v.tile_at(AREA[0] / 2, AREA[1] / 2)
    v.zoom_step(-1)                                           # teclas +/-: âncora no centro
    assert v.zoom == 3 and v.tile_at(AREA[0] / 2, AREA[1] / 2) == pytest.approx(center)
    v.set_zoom(0)
    assert v.zoom == 1
    assert MapView(7).zoom == MV.ZOOM_DEFAULT == 2


def test_camera_stops_at_the_layer_edges():
    v = view_at(zoom=3)
    v.pan(-10_000, -10_000)
    assert edges(v)[:2] == (0, 0)                             # a borda do mapa encosta na da área
    v.pan(10_000, 10_000)
    ox, oy, ex, ey = edges(v)
    assert ex == pytest.approx(192) and ey == pytest.approx(192)
    # zoom perto da borda também não deixa passar
    v.set_zoom(4, (AREA[0] - 1, AREA[1] - 1))
    ox, oy, ex, ey = edges(v)
    assert ox >= 0 and oy >= 0 and ex <= 192 + 1e-9 and ey <= 192 + 1e-9


def test_smaller_axis_is_centered_and_locked():
    """Caverna (128) no 1×: os dois eixos cabem na área (444×196) e ficam centrados e travados. No 2× só o x
    (256 > 196 na altura) trava."""
    v = view_at(size=(128, 128), zoom=1, center=(10, 10))
    assert (v.cx, v.cy) == (64, 64)
    v.pan(300, -300)
    assert (v.cx, v.cy) == (64, 64)
    v.set_zoom(2)
    v.pan(500, 500)
    ox, oy, ex, ey = edges(v)
    assert v.cx == 64 and ey == pytest.approx(128)          # x travado no meio; y presa na borda de baixo


def test_drag_only_after_3px_and_pans_one_to_one():
    v = view_at(zoom=4)
    start = (v.cx, v.cy)
    v.start_press((200, 100))
    assert not v.move_press((202, 100))                        # 2 px: ainda é clique
    assert (v.cx, v.cy) == start
    assert v.end_drag() is False                               # soltou: foi clique
    v.start_press((200, 100))
    assert v.move_press((203, 100))                            # 3 px: virou arrasto
    assert v.move_press((220, 90))                             # 1:1 com o mouse desde onde apertou
    assert (v.cx, v.cy) == pytest.approx((start[0] - 20 / 4, start[1] + 10 / 4))
    assert v.end_drag() is True and v.press is None and not v.dragging


def test_cardinal_and_distance():
    assert MV.cardinal(1, 0) == "a leste" and MV.cardinal(0, 1) == "ao sul" and MV.cardinal(0, -1) == "ao norte"
    assert MV.cardinal(-1, -1) == "a noroeste" and MV.cardinal(1, 1) == "a sudeste" and MV.cardinal(-1, 0.1) == "a oeste"
    assert MV.distance_label((50, 50), (50 - 27.6, 50 - 27.6)) == "39 tiles a noroeste"
    assert MV.distance_label((0, 0), (1, 0)) == "1 tile a leste"
    assert MV.distance_label((0, 0), (0.2, 0.1)) == "aqui"


def test_tooltip_texts_have_state_distance_and_direction():
    g = GameState(rng=random.Random(1))
    g.surface.explored.bits[:] = b"\x01" * len(g.surface.explored.bits)
    entries = MV.map_entries(g, "surface")
    px, py = MV.player_tile(g)
    wreck = next(e for e in entries if e.category == "wreck")
    assert wreck.title.startswith("Destroço · ") and wreck.sub.startswith("caixa cheia · ")
    assert wreck.sub.endswith(MV.distance_label((px, py), (wreck.x, wreck.y)))
    you = next(e for e in entries if e.category == "you")
    assert you.sub == MV.FACING[g.player.direction]          # "você" não tem distância
    # caixa vazia: vira "Vazio" (outro filtro e outro pictograma)
    crate = g.surface.crates[g.surface.world.wrecks[0].crate]
    crate.storage.slots[:] = [None] * len(crate.storage.slots)
    entries = MV.map_entries(g, "surface")
    assert any(e.category == "wreck_empty" and e.sub.startswith("caixa vazia · ") for e in entries)
    # na outra camada: a distância é da rampa
    g.enter_layer("cave")
    surface = MV.map_entries(g, "surface")
    assert not any(e.category == "you" for e in surface)
    base = next(e for e in surface if e.category == "base")
    assert base.sub.endswith(" da rampa")
    # máquinas e baús são marcadores novos; luminária não entra
    g.enter_layer("surface")
    g.surface.machines += [Machine("o2", 90, 100), Machine("chest", 92, 100), Machine("lamp", 94, 100)]
    cats = [e.category for e in MV.map_entries(g, "surface")]
    assert cats.count("machine") == 1 and cats.count("chest") == 1


def test_hover_priority_and_filters():
    g = GameState(rng=random.Random(1))
    entries = MV.map_entries(g, "surface")
    assert sorted(e.priority for e in entries)[0] == MV.PRIORITY["you"]
    hidden = {"base", "crater"}
    shown = MV.visible(entries, hidden)
    assert not any(e.category in hidden for e in shown) and any(e.category == "you" for e in shown)
    assert [e.category for e in shown][-1] == "you"           # "você" por cima de tudo


# ---- App headless ---------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_map_view_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def to_window(app, point):
    from game import viewport
    (x, y, _, _), k, _ = viewport.ui_layout(app.window.get_size(), app.settings["ui_size"])
    return round(x + point[0] * k), round(y + point[1] * k)


def post(app, *events):
    for ev in events:
        pygame.event.post(ev)
    app.handle_events()


def mouse(kind, app, point, button=1):
    pos = to_window(app, point)
    if kind == "motion":
        return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(1, 0, 0))
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN if kind == "down" else pygame.MOUSEBUTTONUP, pos=pos,
                              button=button)


def key(app, k):
    post(app, pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0),
         pygame.event.Event(pygame.KEYUP, key=k, mod=0, unicode="", scancode=0))


def open_map(app, ui_size="grande"):
    s = app.state
    if s.layer != "surface":
        s.enter_layer("surface")
    app.set_ui_size(ui_size)
    s.equipment.slots["scanner"] = "scanner"
    app.mode, app.held, app.placing = "play", None, None
    app.open_map()
    assert app.mode == "map"
    app.draw()
    return s


def test_map_opens_centered_on_the_player_in_the_last_zoom(app):
    s = open_map(app)
    view = app.map_view
    view.pan(-500, -500)
    app.close_map()
    view.zoom = 3
    app.open_map()
    app.draw()
    assert view.zoom == 3 and (view.cx, view.cy) == pytest.approx(MV.player_tile(s))
    view.zoom = 2


def test_wheel_zooms_the_map_at_the_cursor_and_is_saved(app):
    open_map(app)
    ui, view = app.ui, app.map_view
    view.zoom = 2
    view.clamp()
    point = (ui.map_area.x + 120, ui.map_area.y + 60)
    app.mouse_window = to_window(app, point)
    before = view.tile_at(120, 60)
    world_zoom, hotbar = app.zoom, app.hotbar_selected
    post(app, pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=False))
    assert view.zoom == 3 and view.tile_at(120, 60) == pytest.approx(before, abs=0.01)
    assert app.zoom == world_zoom and app.hotbar_selected == hotbar          # nem o mundo nem a hotbar
    assert json.loads(settings.SETTINGS_PATH.read_text())["map_zoom"] == 3
    key(app, pygame.K_MINUS)                                                  # tecla: zoom do mapa, não do mundo
    assert view.zoom == 2 and app.zoom == world_zoom
    key(app, pygame.K_EQUALS)
    assert view.zoom == 3
    key(app, pygame.K_KP_MINUS)
    assert view.zoom == 2 and json.loads(settings.SETTINGS_PATH.read_text())["map_zoom"] == 2
    # botões + / −
    app.draw()
    plus = next(r for r, a in ui.map_buttons if a == "zoom_in")
    post(app, mouse("down", app, plus.center), mouse("up", app, plus.center))
    assert view.zoom == 3 and app.mode == "map"
    view.set_zoom(2)
    app.save_map_prefs()


def test_drag_vs_click_through_the_app(app):
    s = open_map(app)
    ui, view = app.ui, app.map_view
    view.set_zoom(3)                     # no 3× a superfície passa da área nos dois eixos
    app.draw()
    start = (view.cx, view.cy)
    p = ui.map_area.center
    post(app, mouse("down", app, p), mouse("motion", app, (p[0] + 2, p[1])))
    assert (view.cx, view.cy) == start and not view.dragging
    post(app, mouse("up", app, (p[0] + 2, p[1])))
    assert app.mode == "map" and (view.cx, view.cy) == start
    post(app, mouse("down", app, p), mouse("motion", app, (p[0] + 12, p[1] + 6)))
    assert view.dragging and (view.cx, view.cy) == pytest.approx((start[0] - 4, start[1] - 2))
    app.draw()
    assert ui.map_hover is None                                  # arrastando: sem tooltip
    post(app, mouse("up", app, (p[0] + 12, p[1] + 6)))
    assert not view.dragging and app.mode == "map" and not app.mouse_held
    app.update(1 / 60)
    assert app.controls().mine_tile is None
    # C centraliza em você
    key(app, pygame.K_c)
    assert (view.cx, view.cy) == pytest.approx(MV.player_tile(s))
    # o botão também
    view.pan(80, 40)
    app.draw()
    center = next(r for r, a in ui.map_buttons if a == "center")
    post(app, mouse("down", app, center.center), mouse("up", app, center.center))
    assert (view.cx, view.cy) == pytest.approx(MV.player_tile(s))
    view.set_zoom(2)


def test_wasd_moves_the_map_camera_not_the_player(app):
    s = open_map(app)
    view = app.map_view
    view.set_zoom(3)
    view.clamp()
    p0 = (s.player.x, s.player.y)
    cx = view.cx
    post(app, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, mod=0, unicode="", scancode=0))
    for _ in range(10):
        app.update(1 / 60)
    post(app, pygame.event.Event(pygame.KEYUP, key=pygame.K_d, mod=0, unicode="", scancode=0))
    assert view.cx > cx and (s.player.x, s.player.y) == p0
    view.set_zoom(2)


def test_layers_q_e_and_cave_locked_before_first_descent(app):
    s = open_map(app)
    ui, view = app.ui, app.map_view
    if "cave" in s.layers:
        del s.layers["cave"]
    app.draw()
    assert [k for _, k in ui.map_layer_rects] == ["surface"]       # Caverna apagada, sem clique
    key(app, pygame.K_e)
    key(app, pygame.K_q)
    assert view.layer == "surface" and app.mode == "map"            # E não fecha mais o mapa: troca camada
    # desce e volta: a caverna passa a existir
    pos = (s.player.x, s.player.y)
    s.enter_layer("cave", layers.ramp_arrival(layers.make_cave(s.seed).world))
    s.enter_layer("surface", pos)
    view.set_zoom(3)
    app.close_map()
    app.open_map()
    app.draw()
    assert [k for _, k in ui.map_layer_rects] == ["surface", "cave"]
    key(app, pygame.K_e)
    assert view.layer == "cave" and view.zoom == 3                  # mantém o zoom
    ramp = MV.ramp_center(s.layers["cave"].world)
    expect = view_at(size=(128, 128), zoom=3, center=ramp)      # na rampa (com os limites da caverna)
    expect.set_area(*view.area)
    expect.center_on(*ramp)
    assert view.size == (128, 128) and (view.cx, view.cy) == pytest.approx((expect.cx, expect.cy))
    app.draw()
    assert not any(e.category == "you" for _, e in ui.map_markers)  # você está na superfície
    key(app, pygame.K_q)
    assert view.layer == "surface"
    assert (view.cx, view.cy) == pytest.approx(MV.player_tile(s))     # player perto do meio: sem limite
    # clique no segmento
    app.draw()
    cave = next(r for r, k in ui.map_layer_rects if k == "cave")
    post(app, mouse("down", app, cave.center), mouse("up", app, cave.center))
    assert view.layer == "cave" and app.mode == "map"
    view.set_zoom(2)
    app.close_map()


def test_filter_chips_hide_markers_and_their_tooltip_and_persist(app):
    s = open_map(app)
    ui, view = app.ui, app.map_view
    view.hidden.clear()
    app.draw()
    cats = [c for _, c in ui.map_chips]
    assert "base" in cats and "you" not in cats
    assert set(cats) == set(MV.categories(MV.map_entries(s, view.layer)))
    s.player.x += 6 * C.TILE                                       # sai de cima da base
    app.draw()
    base = next(r for r, e in ui.map_markers if e.category == "base")
    app.mouse_window = to_window(app, base.center)
    app.draw()
    assert ui.map_hover is not None and ui.map_hover.category == "base"
    chip = next(r for r, c in ui.map_chips if c == "base")
    post(app, mouse("down", app, chip.center), mouse("up", app, chip.center))
    assert "base" in view.hidden and app.mode == "map"
    assert json.loads(settings.SETTINGS_PATH.read_text())["map_hidden"] == ["base"]
    app.mouse_window = to_window(app, base.center)
    app.draw()
    assert not any(e.category == "base" for _, e in ui.map_markers)
    assert ui.map_hover is None or ui.map_hover.category != "base"   # escondido não ganha tooltip
    assert "base" in [c for _, c in ui.map_chips]                   # o chip continua (pra ligar de novo)
    # um App novo lê os filtros e o zoom do settings.json; a câmera não é salva
    from game.app import App
    other = App.__new__(App)
    other.settings = settings.load()
    assert other.settings["map_hidden"] == ["base"]
    assert "cx" not in other.settings and "map_center" not in other.settings
    post(app, mouse("down", app, chip.center), mouse("up", app, chip.center))
    assert view.hidden == set() and json.loads(settings.SETTINGS_PATH.read_text())["map_hidden"] == []
    s.player.x -= 6 * C.TILE


def test_nothing_leaks_to_the_game(app):
    """Com o mapa aberto: cliques, arrasto, rodinha, +/-, WASD e Q/E não mineram, não colocam, não trocam a hotbar
    nem o zoom do mundo. Esc e M fecham."""
    s = open_map(app)
    ui = app.ui
    s.inventory.slots[2] = type(s.inventory.slots[0])("lamp", 2) if s.inventory.slots[0] else None
    machines, hotbar, zoom = len(s.machines), app.hotbar_selected, app.zoom
    p = ui.map_area.center
    for button in (1, 3, 2):
        post(app, mouse("down", app, p, button), mouse("motion", app, (p[0] + 30, p[1] + 10)),
             mouse("up", app, (p[0] + 30, p[1] + 10), button))
        app.update(1 / 60)
        assert app.mode == "map" and not app.mouse_held and app.placing is None
        assert app.controls().mine_tile is None and len(s.machines) == machines
    post(app, pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False),
         pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=to_window(app, p), button=5))
    for k in (pygame.K_1, pygame.K_MINUS, pygame.K_PLUS):
        key(app, k)
    assert app.hotbar_selected == hotbar and app.zoom == zoom and len(s.machines) == machines
    key(app, pygame.K_ESCAPE)
    assert app.mode == "play" and not app.map_view.dragging
    app.open_map()
    key(app, pygame.K_m)
    assert app.mode == "play"
    # o clique que fecha (fora da janela) também não vira mineração
    app.open_map()
    app.draw()
    post(app, mouse("down", app, (1, 1)), mouse("up", app, (1, 1)))
    assert app.mode == "play" and not app.mouse_held
    app.update(1 / 60)
    assert app.controls().mine_tile is None


@pytest.mark.parametrize("ui_size, window", [("grande", (960, 540)), ("media", (1920, 1080)),
                                             ("pequena", (1920, 1080)), ("media", (1366, 768))])
def test_map_layout_fits_every_interface_size(app, ui_size, window):
    """Grande/Média/Pequena e janela de tamanho livre: área, botões, cabeçalho e chips dentro da janela, sem
    sobrepor; a câmera continua presa nas bordas."""
    from game import viewport
    app.window = pygame.display.set_mode(window)
    s = open_map(app, ui_size)
    s.surface.explored.bits[:] = b"\x01" * len(s.surface.explored.bits)
    s.surface.machines += [Machine("o2", 90, 100), Machine("chest", 92, 100)]
    s.surface.crates[s.surface.world.wrecks[0].crate].storage.slots[:] = [None] * 24
    app.draw()
    ui, view = app.ui, app.map_view
    assert (ui.w, ui.h) == viewport.ui_layout(window, ui_size)[2]
    win, area = ui.map_rect, ui.map_area
    assert win.contains(area) and win.contains(ui.map_close_rect)
    for r, _ in ui.map_buttons:
        assert area.contains(r)
    chips = [r for r, _ in ui.map_chips]
    assert len(chips) == 7                                       # Base, Cratera, Destroço, Vazio, Veios, Máquinas, Baús
    for r in chips:
        assert win.contains(r) and r.top >= area.bottom
    assert all(a.right < b.left for a, b in zip(chips, chips[1:]))
    seg = [r for r, _ in ui.map_layer_rects]
    assert seg and seg[-1].right < ui.map_close_rect.left - 100     # seletor não encosta no EXPLORADO
    for _ in range(2):
        view.pan(-100_000, -100_000)
        for axis in (0, 1):
            vis = view.visible_tiles()[axis]
            o = view.origin()[axis]
            assert (o == pytest.approx(0)) if vis < C.SURFACE_W else (o == pytest.approx(C.SURFACE_W / 2 - vis / 2)), (axis, o, vis)
        view.pan(100_000, 100_000)
    s.surface.machines[:] = [m for m in s.surface.machines if m.kind not in ("o2", "chest")]
    app.close_map()
    app.window = pygame.display.set_mode((960, 540))
    app.set_ui_size("grande")


# ---- agrupamento de máquinas e baús (réguas na base) ---------------------------------------------
def _m(kind, x, y, cat="machine"):
    return MV.Entry(cat, cat, x, y, kind, "", key=kind, stacks=(2, 24) if cat == "chest" else (0, 0))


def test_cluster_groups_close_machines_by_distance():
    """Máquinas a menos de CLUSTER_TILES[zoom] tiles viram um marcador só, no centro do grupo; longe, não."""
    row = [_m("o2", 100 + i, 100) for i in range(4)]                  # régua colada (1 tile entre elas)
    far = _m("heater", 140, 100)
    out = MV.cluster(row + [far], 2)
    groups = [e for e in out if e.count > 1]
    assert len(out) == 2 and len(groups) == 1
    g = groups[0]
    assert g.count == 4 and (g.x, g.y) == pytest.approx((101.5, 100))
    assert far in out                                                  # sozinha continua o marcador dela
    # cadeia: A perto de B, B perto de C (A longe de C) = um grupo só
    chain = [_m("o2", 100, 100), _m("o2", 104, 100), _m("o2", 108, 100)]
    assert [e.count for e in MV.cluster(chain, 2)] == [3]
    assert sorted(e.count for e in MV.cluster(chain, 4)) == [1, 1, 1]


@pytest.mark.parametrize("gap, expected", [(1, {1: 1, 2: 1, 3: 1, 4: 1}),     # encostadas: grupo em todo zoom
                                           (2, {1: 1, 2: 1, 3: 1, 4: 2}),     # 4×: 2 tiles = 8 px, separa
                                           (4, {1: 1, 2: 1, 3: 2, 4: 2}),
                                           (8, {1: 1, 2: 2, 3: 2, 4: 2}),
                                           (12, {1: 2, 2: 2, 3: 2, 4: 2})])
def test_cluster_depends_on_zoom(gap, expected):
    """No 1× e no 2× agrupa mais; no 4× separa o que não encosta."""
    pair = [_m("o2", 50, 50), _m("drill", 50 + gap, 50)]
    for zoom in MV.ZOOMS:
        assert len(MV.cluster(pair, zoom)) == expected[zoom], (gap, zoom)


def test_cluster_keeps_categories_apart_and_respects_filters():
    """Máquina agrupa com máquina e baú com baú (cada filtro some com o seu grupo); o resto não agrupa."""
    stuff = [_m("o2", 10, 10), _m("o2", 11, 10), _m("chest", 10, 11, "chest"), _m("chest", 11, 11, "chest"),
             MV.Entry("vein", "vein", 10, 12, "Veio", "livre"), MV.Entry("vein", "vein", 11, 12, "Veio", "livre")]
    out = MV.cluster(stuff, 2)
    assert sorted((e.category, e.count) for e in out) == [("chest", 2), ("machine", 2), ("vein", 1), ("vein", 1)]
    hidden = MV.cluster(MV.visible(stuff, {"machine"}), 2)
    assert not any(e.category == "machine" for e in hidden) and any(e.category == "chest" for e in hidden)
    assert [e.kind for e in out] == sorted((e.kind for e in out), key=MV.DRAW_ORDER.index)   # ordem do desenho
    # o grupo tem a prioridade da categoria dele (tooltip: você › ... › máquina › baú)
    assert next(e for e in out if e.category == "machine").priority == MV.PRIORITY["machine"]


def test_group_tooltip_has_count_types_and_distance():
    from game.inventory import Stack
    g = GameState(rng=random.Random(1))
    g.surface.explored.bits[:] = b"\x01" * len(g.surface.explored.bits)
    for i, kind in enumerate(["o2", "heater", "o2", "drill", "o2", "heater"]):
        g.surface.machines.append(Machine(kind, 120 + 2 * i, 60))
    g.surface.machines += [Machine("chest", 120, 64), Machine("chest", 121, 64)]
    g.surface.machines[-1].storage.slots[0] = Stack("iron", 5)
    origin, suffix = MV.origin_of(g, "surface")
    out = MV.cluster(MV.visible(MV.map_entries(g, "surface"), ()), 2, origin, suffix)
    machines = next(e for e in out if e.category == "machine" and e.count > 1)
    assert machines.title == "Máquinas · 6"
    assert machines.detail == "3 geradores de O₂, 2 aquecedores, 1 drill"
    assert machines.sub == MV.distance_label(origin, (machines.x, machines.y))
    chests = next(e for e in out if e.category == "chest")
    assert chests.title == "Baús · 2" and chests.detail == "1/48 pilhas"
    # na outra camada a distância do grupo também é "da rampa"
    g.enter_layer("cave")
    origin, suffix = MV.origin_of(g, "surface")
    out = MV.cluster(MV.visible(MV.map_entries(g, "surface"), ()), 2, origin, suffix)
    assert next(e for e in out if e.count > 1 and e.category == "machine").sub.endswith(" da rampa")


def test_type_summary_plural_and_overflow():
    assert MV.type_summary(["drill"]) == "1 drill"
    assert MV.type_summary(["solar", "solar"]) == "2 painéis solares"
    assert MV.type_summary(["o2", "heater", "melter", "solar", "solar"]) == \
        "2 painéis solares, 1 aquecedor, 1 derretedor +1"


# ---- spoiler: só o que já foi visto -----------------------------------------------------------------
def test_map_only_shows_what_was_explored():
    """Nada de spoiler: veio, destroço, terminal, cratera/rampa e máquina só entram com algum tile no
    `explored` da camada. Exceções: "você" e a base."""
    g = GameState(rng=random.Random(1))
    g.surface.explored.bits[:] = bytearray(len(g.surface.explored.bits))
    g.surface.machines.append(Machine("o2", 150, 150))
    assert {e.category for e in MV.map_entries(g, "surface")} == {"base", "you"}
    g.surface.explored.bits[:] = b"\x01" * len(g.surface.explored.bits)
    assert {"crater", "wreck", "vein", "machine"} <= {e.category for e in MV.map_entries(g, "surface")}
    # caverna: só a luz revela. Sem nada visto, só "você"; a luz do terminal na tela revela o terminal
    g.enter_layer("cave")
    cave = g.layers["cave"]
    cave.explored.bits[:] = bytearray(len(cave.explored.bits))
    assert {e.category for e in MV.map_entries(g, "cave")} == {"you"}
    tx, ty = cave.world.terminals[0]
    cave.explored.reveal_circle(tx + 0.5, ty + 1, C.EXPLORE_TERMINAL)
    terms = [e for e in MV.map_entries(g, "cave") if e.category == "terminal"]
    assert len(terms) == 1 and (terms[0].x, terms[0].y) == (tx + 0.5, ty + 0.5)


def test_group_marker_and_tooltip_through_the_app(app):
    """No app: a régua de máquinas da base vira um marcador com o número, e o tooltip do grupo tem 3 linhas
    e cabe na área. No 4× (2 tiles entre elas) se separam."""
    s = open_map(app)
    ui, view = app.ui, app.map_view
    view.hidden.clear()
    s.surface.explored.bits[:] = b"\x01" * len(s.surface.explored.bits)
    bx, by = C.BASE_TILE
    extra = [Machine(k, bx + 6 + 2 * i, by + 6) for i, k in enumerate(["o2", "o2", "heater", "solar"])]
    s.surface.machines += extra
    view.set_zoom(2)
    view.center_on(bx + 9, by + 6)
    app.draw()
    groups = [(r, e) for r, e in ui.map_markers if e.category == "machine" and e.count > 1]
    assert len(groups) == 1 and groups[0][1].count == 4
    rect = groups[0][0]
    app.mouse_window = to_window(app, rect.center)
    app.draw()
    assert ui.map_hover is not None and ui.map_hover.title == "Máquinas · 4"
    assert ui.map_hover.detail == "2 geradores de O₂, 1 aquecedor, 1 painel solar"
    tip = ui.map_tooltip_rect(ui.map_hover, rect.center)
    assert tip.h == ui.MAP_TOOLTIP_H + 12 and ui.map_area.contains(tip)
    view.set_zoom(4)
    view.center_on(bx + 9, by + 6)
    app.draw()
    assert sum(1 for _, e in ui.map_markers if e.category == "machine") == 4
    view.set_zoom(2)
    for m in extra:
        s.surface.machines.remove(m)
    app.close_map()


# ---- v0.4 Marco 2: formações e chão por região ------------------------------------------------------
def test_formations_are_fixed_landmarks_without_filter():
    """Formação vista vira marcador "Formação" (pictograma próprio, tooltip com o nome e a região). Não tem chip
    de filtro e nenhum filtro esconde; só entra depois de vista, como o resto."""
    from game import map_markers
    g = GameState(rng=random.Random(1))
    bits = g.surface.explored.bits
    bits[:] = bytearray(len(bits))
    assert not [e for e in MV.map_entries(g, "surface") if e.category == "formation"]
    bits[:] = b"\x01" * len(bits)
    entries = MV.map_entries(g, "surface")
    forms = [e for e in entries if e.category == "formation"]
    big = [f for f in g.surface.geo.formations if not f.small and not f.kind.startswith("vent_")]   # pequenas e fumarolas: sem marcador
    assert len(forms) == len(big) and len(big) < len(g.surface.geo.formations)
    assert "formation" not in MV.categories(entries) and "formation" not in MV.FILTERS
    assert len([e for e in MV.visible(entries, set(MV.FILTERS)) if e.category == "formation"]) == len(forms)
    arch = next(e for e in forms if e.title == "Arco de pedra")
    assert arch.state == "Planalto rachado" and "tiles" in arch.sub
    assert map_markers.marker("formation").get_size() == (7, 6)
    assert MV.visible(entries, ())[0].category == "formation"                 # desenhada por baixo de tudo


def test_minimap_paints_the_ground_by_region():
    from game import minimap
    from game.geo import REGION_NAMES
    g = GameState(rng=random.Random(1))
    world, geo = g.surface.world, g.surface.geo
    assert len(set(minimap.REGION_COLORS)) == len(REGION_NAMES)
    seen = set()
    for y in range(0, world.height, 3):
        for x in range(0, world.width, 3):
            if world.get(x, y) == C.SAND and world.vein_at(x, y) is None:
                assert minimap.tile_color(world, x, y) == minimap.REGION_COLORS[geo.region[y, x]]
                seen.add(int(geo.region[y, x]))
    assert seen == {0, 1, 2, 3}
    cave = layers.make_cave(1).world
    assert minimap.tile_color(cave, *C.CAVE_CENTER) == minimap.TILE_COLORS[C.FLOOR]
