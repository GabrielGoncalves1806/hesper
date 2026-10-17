"""v0.7 M2 · Props e scanner (bíblia §16): tabela, custos, colisão, colocar/desmontar, save e scan."""

import json
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import save  # noqa: E402
from game.props import Prop, face_visible  # noqa: E402
from game.systems import Controls, GameState  # noqa: E402
from tests.helpers import give  # noqa: E402


@pytest.fixture
def state_with_constructor() -> GameState:
    """Estado novo na superfície, com o construtor no inventário e o player num chão livre."""
    s = GameState(rng=random.Random(1))
    give(s, constructor=1)
    return s


def make_state_seed7() -> GameState:
    """Estado da seed 7 (acampamento e laboratório na superfície, com props de ruína)."""
    return save.new_state(7)


def near(s: GameState, prop: Prop) -> None:
    """Põe o player 2 tiles abaixo do prop."""
    s.player.x, s.player.y = (prop.tx + 0.5) * C.TILE, (prop.ty + 2) * C.TILE + 16


def a_scannable(s: GameState) -> Prop:
    return next(p for p in s.active.props.values() if C.PROPS[p.kind].scannable)


def spot(s: GameState) -> tuple[int, int]:
    px, py = s.player.tile
    return px + 2, py


# ---- Task 1: config, Prop e assets ----------------------------------------------------------------
def test_tabela_de_props():
    assert len(C.PROPS) == 42                                   # v0.7 M4: +17 do kit da VÉSPER-7
    assert set(C.PROP_STARTER) == {"prop_table", "prop_chair", "prop_crate", "prop_sign"}
    assert set(C.PROP_SCENERY) == {"prop_chair_fallen", "prop_rubble", "prop_ice_stain", "prop_uniforms"}
    assert len(C.PLAYER_PROPS) == 38
    for k in C.PROP_STARTER + C.PROP_SCENERY:
        assert not C.PROPS[k].scannable
    assert C.PROPS["prop_dead_plant"].scannable
    assert C.PROPS["wall_bp_ice"].scannable and C.PROPS["wall_bp_ice"].place == "face"
    assert C.PROPS["prop_wall_desk_a"].place == "desk"
    assert C.PROPS["prop_ice_stain"].place == "decal"


def test_custos():
    tech = {"prop_lab_bench", "prop_microscope", "prop_console", "prop_sample_tank",
            "wall_monitor_on", "wall_monitor_off",
            "prop_microscope_digital", "prop_command_table", "prop_server_rack", "prop_server_rack_open", "prop_workstation",
            "prop_suit_locker", "prop_suit_niche", "prop_briefing_table", "prop_nav_table"}      # v0.7 M4
    for k in C.PLAYER_PROPS:
        want = {"iron": 2, "silicon": 1} if k in tech else {"iron": 2}
        assert C.MACHINES[k].cost == want, k
        assert C.MACHINE_CATEGORY[k] == "decor"
    for k in C.PROP_SCENERY:
        assert k not in C.MACHINES


def test_aba_decoracao_e_a_ultima():
    assert C.FAB_TABS[-1] == ("decor", "Decoração")


def test_colisao():
    assert Prop("prop_table", 3, 4).rect == (3 * 32 + 4, 4 * 32 + 14, 24, 18)
    assert Prop("prop_wall_desk_b", 3, 4).rect == (96, 128, 32, 32)
    for k in ("prop_chair", "prop_sign", "prop_dead_plant", "prop_chair_fallen", "prop_ice_stain", "wall_notice"):
        assert Prop(k, 0, 0).rect is None, k
    assert Prop("prop_microscope", 0, 0).rect is not None


def test_face_visivel():
    walls = {(5, 5), (5, 6)}
    is_wall = lambda x, y: (x, y) in walls
    assert not face_visible(is_wall, 5, 5)   # parede embaixo: sem face
    assert face_visible(is_wall, 5, 6)


def test_assets_promovidos():
    from pathlib import Path
    sprites = Path("assets/sprites")
    for k in C.PROPS:
        for name in ((f"{k}_a", f"{k}_b") if k in C.PROP_VARIANT_KINDS else (k,)):
            assert (sprites / f"{name}.png").exists(), name
        if k in C.PLAYER_PROPS:
            assert (sprites / f"icon_{k}.png").exists(), k


# ---- Task 3: conhecer, colocar, colidir, desmontar e salvar ---------------------------------------
def test_desconhecido_nao_constroi(state_with_constructor):
    s = state_with_constructor
    give(s, iron=10)
    tile = spot(s)
    assert s.recipe_status("prop_bunk", inv_only=True) == "blueprint"
    assert not s.build("prop_bunk", tile)
    s.scanned.add("prop_bunk")
    assert s.build("prop_bunk", tile)
    assert s.prop_at(tile).kind == "prop_bunk" and not s.prop_at(tile).ruin
    assert s.inventory.count("iron") == 8
    assert not [m for m in s.machines if m.kind == "prop_bunk"]      # prop não é Machine


def test_prop_bloqueia_maquina_e_colide(state_with_constructor):
    s = state_with_constructor
    give(s, iron=50, silicon=50)
    tile = spot(s)
    assert s.build("prop_table", tile)
    assert not s.can_place("o2", tile)
    assert not s.can_place(C.BASE_FLOOR, tile) and not s.can_place(C.BASE_WALL, tile)
    box = (tile[0] * 32, tile[1] * 32, 32, 32)
    assert s.prop_at(tile).rect in s.solids_near(box)


def test_cadeira_nao_colide(state_with_constructor):
    s = state_with_constructor
    give(s, iron=10)
    tile = spot(s)
    assert s.build("prop_chair", tile)
    box = (tile[0] * 32, tile[1] * 32, 32, 32)
    assert all(r != (tile[0] * 32 + 4, tile[1] * 32 + 14, 24, 18) for r in s.solids_near(box))


def test_prop_nao_entra_em_maquina(state_with_constructor):
    s = state_with_constructor
    give(s, iron=50, silicon=50)
    assert s.build("lamp", spot(s))
    assert not s.can_place("prop_table", spot(s))


def test_desmonta_prop_do_player_devolve_custo(state_with_constructor):
    s = state_with_constructor
    give(s, iron=2)
    tile = spot(s)
    s.build("prop_crate", tile)
    assert s.inventory.count("iron") == 0
    assert s.dismantle(s.prop_at(tile))
    assert s.prop_at(tile) is None and s.inventory.count("iron") == 2


def test_desmonta_segurando_o_direito_num_prop(state_with_constructor):
    s = state_with_constructor
    give(s, iron=2)
    tile = spot(s)
    s.build("prop_crate", tile)
    prop = s.prop_at(tile)
    for _ in range(int(C.DISMANTLE_HOLD / 0.05) + 2):
        s.update(0.05, Controls(dismantle=prop))
    assert s.prop_at(tile) is None and s.inventory.count("iron") == 2


def test_prop_de_ruina_nao_desmonta():
    s = make_state_seed7()
    prop = next(iter(s.active.props.values()))
    near(s, prop)
    assert prop.ruin and not s.can_dismantle(prop)


def test_face_so_em_parede_do_player_com_face(state_with_constructor):
    s = state_with_constructor
    give(s, iron=50, silicon=50)
    px, py = s.player.tile
    wall, below = (px + 2, py - 1), (px + 2, py)
    assert not s.can_place("wall_notice", wall)            # sem parede
    assert s.build(C.BASE_WALL, wall)
    s.scanned.add("wall_notice")
    assert s.can_place("wall_notice", wall)
    assert s.build(C.BASE_WALL, below)                     # parede embaixo: a de cima perde a face
    assert not s.can_place("wall_notice", wall)


def test_mesa_de_parede_precisa_de_parede_em_cima(state_with_constructor):
    s = state_with_constructor
    give(s, iron=50)
    s.scanned.add("prop_wall_desk_a")
    px, py = s.player.tile
    tile = (px + 2, py)
    assert not s.can_place("prop_wall_desk_a", tile)
    assert s.build(C.BASE_WALL, (px + 2, py - 1))
    assert s.can_place("prop_wall_desk_a", tile)


def test_prop_nao_prende_o_player(state_with_constructor):
    s = state_with_constructor
    give(s, iron=10)
    assert not s.can_place("prop_table", s.player.tile)


def test_prop_nao_vai_dentro_de_ruina():
    s = make_state_seed7()
    give(s, iron=10, constructor=1)
    tile = next(t for t in s.world.ruin_tiles if t not in s.active.props)
    s.player.x, s.player.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 2) * C.TILE
    assert not s.can_place("prop_table", tile)


def test_desmontar_parede_leva_o_quadro(state_with_constructor):
    s = state_with_constructor
    give(s, iron=4)
    px, py = s.player.tile
    wall = (px + 2, py - 1)
    assert s.build(C.BASE_WALL, wall)
    s.scanned.add("wall_notice")
    assert s.build("wall_notice", wall)
    assert s.inventory.count("iron") == 0
    assert s.dismantle(s.base.get(wall))
    assert s.prop_at(wall) is None and s.inventory.count("iron") == 4


def test_prop_at_point(state_with_constructor):
    s = state_with_constructor
    give(s, iron=10)
    tx, ty = spot(s)
    assert s.build("prop_table", (tx, ty))
    prop = s.prop_at((tx, ty))
    assert s.prop_at_point(tx * 32 + 16, ty * 32 - 4) is prop          # a parte que sobe 8 px
    assert s.prop_at_point(tx * 32 + 16, ty * 32 + 20) is prop
    assert s.prop_at_point(tx * 32 + 16, ty * 32 - 12) is None
    assert s.prop_at_point(tx * 32 + 16, (ty + 1) * 32 + 2) is None


def test_prop_at_point_de_face(state_with_constructor):
    s = state_with_constructor
    give(s, iron=10)
    px, py = s.player.tile
    wall = (px + 2, py - 1)
    s.build(C.BASE_WALL, wall)
    s.scanned.add("wall_notice")
    s.build("wall_notice", wall)
    prop = s.prop_at(wall)
    assert s.prop_at_point(wall[0] * 32 + 16, wall[1] * 32 + 12) is prop
    assert s.prop_at_point(wall[0] * 32 + 16, wall[1] * 32 + 4) is None     # acima da face (topo da parede)


def test_menu_decoracao_so_conhecidos():
    from game.fabricator import build_kinds
    starter = ["prop_table", "prop_chair", "prop_crate", "prop_sign"]
    assert build_kinds("decor", set(starter)) == starter
    assert "prop_bunk" in build_kinds("decor", {"prop_bunk"})
    assert build_kinds("decor") == starter
    assert "prop_bunk" not in build_kinds("terraform")


def test_save_props_e_scanned(state_with_constructor):
    s = state_with_constructor
    give(s, iron=10)
    tile = spot(s)
    s.build("prop_table", tile)
    s.scanned.add("prop_bunk")
    data = json.loads(json.dumps(save.state_to_dict(s)))
    assert data["version"] == 14 and data["scanned"] == ["prop_bunk"]
    assert data["layers"]["surface"]["props"] == [["prop_table", *tile]]
    t = save.state_from_dict(data)
    assert t.scanned == {"prop_bunk"}
    assert t.prop_at(tile).kind == "prop_table" and not t.prop_at(tile).ruin
    ruina = [p for p in t.active.props.values() if p.ruin]
    assert len(t.active.props) == len(ruina) + 1


def test_save_nao_leva_props_de_ruina():
    s = make_state_seed7()
    assert s.active.props
    data = save.state_to_dict(s)
    assert "props" not in data["layers"]["surface"] and "scanned" not in data


def test_save_antigo_sem_campos(state_with_constructor):
    data = save.state_to_dict(state_with_constructor)
    data.pop("scanned", None)
    for layer in data["layers"].values():
        layer.pop("props", None)
    t = save.state_from_dict(data)
    assert t.scanned == set()
    assert all(p.ruin for p in t.active.props.values())


def test_save_ignora_prop_desconhecido(state_with_constructor):
    data = save.state_to_dict(state_with_constructor)
    data["scanned"] = ["prop_bunk", "lixo", "prop_rubble"]
    data["layers"]["surface"]["props"] = [["lixo", 1, 1], ["prop_rubble", 2, 2]]
    t = save.state_from_dict(data)
    assert t.scanned == {"prop_bunk"}
    assert (1, 1) not in t.active.props and (2, 2) not in t.active.props


# ---- Task 4: scan ---------------------------------------------------------------------------------
def test_scan_libera_depois_de_segurar():
    s = make_state_seed7()
    prop = a_scannable(s)
    near(s, prop)
    assert s.can_scan(prop)
    s._update_scan(prop, 1.0)
    assert ("scan_charge",) in s.pop_events()
    assert prop.kind not in s.scanned
    s._update_scan(prop, 0.6)
    assert ("scan_done", prop.kind) in s.pop_events()
    assert prop.kind in s.scanned and not s.can_scan(prop)


def test_soltar_cancela():
    s = make_state_seed7()
    prop = a_scannable(s)
    near(s, prop)
    s._update_scan(prop, 1.0)
    s.pop_events()
    s._update_scan(None, 0.1)
    assert ("scan_cancel",) in s.pop_events()
    s._update_scan(prop, 1.0)
    assert prop.kind not in s.scanned       # recomeçou do zero


def test_trocar_de_alvo_cancela_e_recomeca():
    s = make_state_seed7()
    a = a_scannable(s)
    near(s, a)
    b = Prop(next(k for k, t in C.PROPS.items() if t.scannable and k != a.kind), a.tx + 1, a.ty, ruin=True)
    s.active.props[b.tile] = b
    s._update_scan(a, 1.0)
    s.pop_events()
    s._update_scan(b, 0.1)
    assert s.pop_events() == [("scan_cancel",), ("scan_charge",)]
    assert s.scanning is b and abs(s.scan_t - 0.1) < 1e-9


def test_cenario_conhecido_e_do_player_nao_escaneiam():
    s = make_state_seed7()
    for kind in C.PROP_SCENERY + C.PROP_STARTER:
        assert not s.can_scan(Prop(kind, 0, 0, ruin=True)), kind
    player_prop = Prop("prop_bunk", 0, 0, ruin=False)
    s.active.props[(0, 0)] = player_prop
    s.player.x, s.player.y = 16, 48
    assert not s.can_scan(player_prop)


def test_longe_nao_escaneia():
    s = make_state_seed7()
    prop = a_scannable(s)
    s.player.x, s.player.y = (prop.tx + 20) * 32, prop.ty * 32
    assert not s.can_scan(prop)


def test_scan_pelo_update_com_controls():
    s = make_state_seed7()
    prop = a_scannable(s)
    near(s, prop)
    for _ in range(100):
        s.update(0.02, Controls(scan=prop))
    assert prop.kind in s.scanned
    assert ("scan_done", prop.kind) in s.pop_events()
    assert s.scan_progress == 0.0


def test_scan_para_se_desmaiar():
    s = make_state_seed7()
    prop = a_scannable(s)
    near(s, prop)
    s.update(0.1, Controls(scan=prop))
    assert s.scanning is prop
    s.fainted = True
    s.update(0.1, Controls(scan=prop))
    assert s.scanning is None and s.scan_t == 0.0


def test_prop_escaneado_aparece_no_menu_e_constroi(state_with_constructor):
    from game.fabricator import build_kinds
    s = state_with_constructor
    s.scanned.add("prop_barrel")
    assert "prop_barrel" in build_kinds("decor", s.known_props())
    give(s, iron=2)
    assert s.build("prop_barrel", spot(s))


# ---- Task 5: App (sem janela) ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    import tempfile
    from pathlib import Path
    from game import settings
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_props_app_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    import pygame
    pygame.quit()


class FakeAudio:
    def __init__(self):
        self.played, self.calls = [], []

    def play(self, name, delay=0.0, gain=1.0, channel=None):
        self.played.append(name)

    def has(self, name):
        return True

    def start_scan(self):
        self.calls.append("start_scan")

    def stop_scan(self):
        self.calls.append("stop_scan")

    def __getattr__(self, name):
        return lambda *a, **k: None


def test_menu_do_app_muda_depois_do_scan(app):
    app.start_game(make_state_seed7())
    assert app.build_menu.kinds_of("decor") == list(C.PROP_STARTER)
    app.state.scanned.add("prop_bunk")
    assert "prop_bunk" in app.build_menu.kinds_of("decor")
    app.start_game(make_state_seed7())                 # outro save: o menu volta aos de cara
    assert app.build_menu.kinds_of("decor") == list(C.PROP_STARTER)


def test_eventos_de_scan_viram_som_e_aviso(app):
    app.start_game(make_state_seed7())
    app.audio = FakeAudio()
    app.on_game_event(("scan_charge",))
    app.on_game_event(("scan_cancel",))
    app.on_game_event(("scan_done", "prop_bunk"))
    assert app.audio.calls == ["start_scan", "stop_scan", "stop_scan"]
    assert app.audio.played == ["scan_done"]
    assert app.notice == "Projeto liberado: Beliche"


def test_r_nao_gira_prop_e_hint_de_scan(app):
    import pygame
    s = make_state_seed7()
    app.start_game(s)
    give(s, constructor=1)
    app.select_hotbar(next(i for i, st in enumerate(s.inventory.slots) if st and st.item == "constructor"))
    prop = a_scannable(s)
    near(s, prop)
    app.mouse_held = False
    from game import viewport
    app.step(1 / 30)
    app.mouse = tuple(round(v) for v in viewport.world_to_canvas((prop.tx * 32 + 16, prop.ty * 32 + 14), app.cam, app.zoom))
    assert app.hovered_prop() is prop
    assert app.hint() == "Escanear (segure)" and app.highlight_target() is prop
    app.mouse_held = True
    assert app.controls().scan is prop
    app.placing, app.rotation = "prop_table", 0
    app.on_key(pygame.K_r)
    assert app.rotation == 0
    app.placing = "lamp"
    app.on_key(pygame.K_r)
    assert app.rotation == 1                          # máquina gira
