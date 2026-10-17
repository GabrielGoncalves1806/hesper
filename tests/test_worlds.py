"""Mundos com nome e seed, em 3 espaços (game/worlds.py) e a tela de Mundos/Novo mundo do título (game/title.py)."""

import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import save  # noqa: E402
from game import settings  # noqa: E402
from game import worlds  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIZES = [(480, 270), (640, 360), (960, 540)]
OWNER_BACKUPS = ["slot1.antigo.json", "slot1.v5.json", "slot1.v03_antes_tempestade.json",
                 "slot1.v6_backup_manual.json", "slot1.v6.json"]


@pytest.fixture
def saves(tmp_path, monkeypatch):
    monkeypatch.setattr(worlds, "SAVES_DIR", tmp_path)
    monkeypatch.setattr(save, "SAVE_PATH", tmp_path / "slot1.json")
    return tmp_path


def owner_backups(folder: Path) -> dict:
    """Os backups do dono, com conteúdo e data: nada disso pode mudar."""
    out = {}
    for i, name in enumerate(OWNER_BACKUPS):
        file = folder / name
        file.write_text(json.dumps({"version": 5 + i % 2, "seed": 7, "dono": name}), encoding="utf-8")
        os.utime(file, (1_000_000 + i, 1_000_000 + i))
        out[name] = (file.read_bytes(), file.stat().st_mtime)
    return out


def snapshot(folder: Path, names) -> dict:
    return {n: ((folder / n).read_bytes(), (folder / n).stat().st_mtime) for n in names}


# ---- seed --------------------------------------------------------------------------------------
def test_text_seed_is_stable_across_runs():
    """Mesmo texto, mesma seed: valor fixo (sha256) e igual num outro processo com outro PYTHONHASHSEED."""
    assert worlds.text_seed("Hesper") == 575359005
    assert worlds.text_seed("marte vermelho") == 1369017880
    code = "from game.worlds import text_seed; print(text_seed('Hesper'))"
    for hash_seed in ("1", "999"):
        out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                             env={**os.environ, "PYTHONHASHSEED": hash_seed}, check=True)
        assert int(out.stdout) == 575359005


def test_parse_seed():
    assert worlds.parse_seed("") is None and worlds.parse_seed("   ") is None
    assert worlds.parse_seed("123") == 123 and worlds.parse_seed(" 42 ") == 42
    assert worlds.parse_seed("abc") == worlds.text_seed("abc") != worlds.parse_seed("abd")
    assert worlds.parse_seed("-5") == worlds.text_seed("-5")          # só dígitos contam como número
    assert worlds.parse_seed("99999999999999999999") == 99999999999999999999 % 2 ** 31
    assert all(0 <= worlds.parse_seed(t) < 2 ** 31 for t in ("x", "Mundo legal", "0", "2147483648"))


def test_random_seed_is_saved(saves):
    state = worlds.create(2, "Sorteado", None, rng=random.Random(5))
    expected = random.Random(5).randint(1, worlds.RANDOM_SEED_MAX)
    assert state.seed == expected
    data = json.loads(worlds.path(2).read_text(encoding="utf-8"))
    assert data["seed"] == data["world"]["seed"] == expected and data["world"]["name"] == "Sorteado"
    assert worlds.info(2).seed == expected
    assert worlds.load(2)[1].seed == expected


# ---- migração ------------------------------------------------------------------------------------
def test_v7_slot1_becomes_world1_and_backups_are_untouched(saves):
    before = owner_backups(saves)
    state = save.new_state()
    state.play_time = 321.0
    assert save.write_save(state, saves / "slot1.json")
    os.utime(saves / "slot1.json", (2_000_000, 2_000_000))
    legacy = snapshot(saves, ["slot1.json"])
    infos = worlds.list_worlds()
    assert [w.status for w in infos] == ["ok", "empty", "empty"]
    assert infos[0].name == "Mundo 1" and infos[0].seed == C.WORLD_SEED == 7 and infos[0].play_time == 321.0
    assert infos[0].saved == 2_000_000                       # a data é a do save antigo
    assert worlds.load(1)[1].world_name == "Mundo 1" and worlds.continue_slot(infos) == 1
    assert snapshot(saves, OWNER_BACKUPS) == before and snapshot(saves, ["slot1.json"]) == legacy
    # apagou o mundo 1: o slot1.json (backup) não volta a virar mundo
    worlds.delete(1)
    assert [w.status for w in worlds.list_worlds()] == ["empty"] * 3
    assert snapshot(saves, ["slot1.json"]) == legacy and snapshot(saves, OWNER_BACKUPS) == before


def test_v6_slot1_does_not_migrate_and_becomes_backup_on_create(saves):
    before = owner_backups(saves)
    (saves / "slot1.json").write_text(json.dumps({"version": 6, "seed": 7}), encoding="utf-8")
    assert worlds.list_worlds()[0].empty and worlds.legacy_status() == "old"
    worlds.create(1, "Novo", 3)
    assert not (saves / "slot1.json").exists()
    assert json.loads((saves / "slot1.v6-2.json").read_text(encoding="utf-8")) == {"version": 6, "seed": 7}
    assert snapshot(saves, OWNER_BACKUPS) == before            # o slot1.v6.json do dono continua igual


# ---- criar, listar, apagar ------------------------------------------------------------------------
def test_create_list_and_delete(saves):
    assert [w.status for w in worlds.list_worlds()] == ["empty"] * 3
    a = worlds.create(1, "  Marte   azul ", 11)
    b = worlds.create(3, "", 12)
    assert a.world_name == "Marte azul" and b.world_name == "Mundo 3"     # vazio = "Mundo N"
    assert worlds.create(2, "x" * 40, 1).world_name == "x" * worlds.NAME_MAX
    infos = worlds.list_worlds()
    assert [(w.slot, w.status, w.seed) for w in infos] == [(1, "ok", 11), (2, "ok", 1), (3, "ok", 12)]
    assert infos[0].stage_name == C.STAGES[0].name and infos[0].date_label
    assert worlds.last_slot() == 2
    worlds.delete(2)
    assert worlds.info(2).empty and not worlds.path(2).exists() and worlds.last_slot() is None
    assert worlds.continue_slot(worlds.list_worlds()) in (1, 3)


def test_delete_old_or_broken_world_keeps_a_backup(saves):
    worlds.path(1).write_text(json.dumps({"version": 5, "seed": 7}), encoding="utf-8")
    worlds.path(2).write_text("{quebrado", encoding="utf-8")
    assert [w.status for w in worlds.list_worlds()][:2] == ["old", "broken"]
    assert worlds.delete(1).name == "world1.v5.json"
    assert worlds.delete(2).name == "world2.estragado.json"
    assert worlds.info(1).empty and worlds.info(2).empty


def test_world_block_roundtrip(saves):
    state = worlds.create(1, "Vale", 77)
    state.play_time = 90.0
    save.write_save(state, worlds.path(1))
    data = json.loads(worlds.path(1).read_text(encoding="utf-8"))
    assert data["version"] == save.SAVE_VERSION                    # o bloco entrou sem subir a versão
    assert data["world"] == {"name": "Vale", "seed": 77, "created": state.world_created, "played_s": 90.0}
    loaded = worlds.load(1)[1]
    assert (loaded.world_name, loaded.seed, loaded.world_created) == ("Vale", 77, state.world_created)


def test_same_name_and_seed_make_the_same_world(saves):
    seed = worlds.parse_seed("planeta")
    a = worlds.create(1, "Igual", seed)
    b = worlds.create(2, "Igual", worlds.parse_seed("planeta"))
    c = worlds.create(3, "Igual", worlds.parse_seed("planeta2"))
    assert a.seed == b.seed != c.seed
    assert a.world.tiles == b.world.tiles and a.world.tiles != c.world.tiles
    assert np.array_equal(a.surface.geo.region, b.surface.geo.region)
    assert [(f.kind, f.tx, f.ty) for f in a.surface.geo.formations] == \
           [(f.kind, f.tx, f.ty) for f in b.surface.geo.formations]
    assert a.weather.wind == b.weather.wind


# ---- tela (hit-test nos 3 tamanhos) ------------------------------------------------------------------
@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    from game.ui import UI
    return UI()


def title_with(ui, world_list):
    from game.title import TitleScreen
    title = TitleScreen(ui, None, lambda _name: None)
    title.open(None, world_list=world_list)
    return title


def sample_worlds():
    return [worlds.WorldInfo(1, "ok", "Marte azul", 11, 2, 754.0, 1_700_000_000.0),
            worlds.WorldInfo(2),
            worlds.WorldInfo(3, "old", "Mundo 3", 7)]


@pytest.mark.parametrize("size", SIZES)
def test_world_list_hit_test(ui, size):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    title = title_with(ui, sample_worlds())
    title.activate(0)                                              # Mundos
    assert title.screen == "worlds"
    ui.begin()
    title.draw_screen(0.0, (0, 0))
    assert len(title.items) == 4                                   # 3 espaços + Voltar
    screen = pygame.Rect(0, 0, *size)
    assert all(screen.contains(r) for r in title.items)
    assert not any(a.colliderect(b) for i, a in enumerate(title.items) for b in title.items[i + 1:])
    assert [slot for _, slot in title.delete_rects] == [1, 3]       # o vazio não tem APAGAR
    assert title.click(*title.items[0].center) == ("play", 1)
    title.screen = "worlds"
    # APAGAR: o 1º clique arma, o 2º apaga
    rect = title.delete_rects[0][0]
    assert title.items[0].contains(rect)
    assert title.click(*rect.center) is None and title.armed == 1
    ui.begin()
    title.draw_screen(0.0, (0, 0))
    assert title.click(*title.delete_rects[0][0].center) == ("delete", 1) and title.armed is None
    # clicar fora desarma
    title.click(*title.delete_rects[0][0].center)
    title.click(0, 0)
    assert title.armed is None
    # espaço vazio abre o Novo mundo; Voltar volta pro menu
    assert title.click(*title.items[1].center) is None and title.screen == "form" and title.form_slot == 2
    title.screen = "worlds"
    title.click(*title.items[3].center)
    assert title.screen == "main"


def test_world_list_keyboard(ui):
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    title = title_with(ui, sample_worlds())
    title.on_key(pygame.K_RETURN)                                  # Mundos (já selecionado, sem Continuar)
    assert title.screen == "worlds" and title.selected == 0
    title.on_key(pygame.K_x)
    assert title.armed == 1
    title.on_key(pygame.K_ESCAPE)                                  # Esc desarma, não sai
    assert title.armed is None and title.screen == "worlds"
    title.on_key(pygame.K_DELETE)
    assert title.on_key(pygame.K_DELETE) == ("delete", 1)
    title.on_key(pygame.K_s)
    assert title.on_key(pygame.K_x) is None and title.armed is None    # espaço vazio: nada pra apagar
    assert title.on_key(pygame.K_RETURN) is None and title.screen == "form"


@pytest.mark.parametrize("size", SIZES)
def test_new_world_form(ui, size):
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    title = title_with(ui, sample_worlds())
    title.open_form(2, rolled=4242)
    assert title.wants_text and title.focus == 0
    ui.begin()
    title.draw_screen(0.0, (0, 0))
    rects = dict((index, rect) for rect, index in title.form_rects)
    assert sorted(rects) == [0, 1, 2, 3]
    screen = pygame.Rect(0, 0, *size)
    assert all(screen.contains(r) for r in rects.values())
    # vazio: nome padrão e a seed sorteada que está na tela
    assert title.click(*rects[2].center) == ("create", 2, "Mundo 2", 4242)
    # clica no nome e digita, clica na seed e digita texto
    title.click(*rects[0].center)
    title.on_text("Duna")
    title.click(*rects[1].center)
    assert title.focus == 1
    title.on_text("planeta")
    assert title.form_seed() == (worlds.text_seed("planeta"), "texto")
    title.on_key(pygame.K_BACKSPACE)
    assert title.seed_field.text == "planet"
    title.seed_field.text = "123"
    assert title.on_key(pygame.K_RETURN) == ("create", 2, "Duna", 123)
    # nome com limite de 20
    title.click(*rects[0].center)
    title.on_text("a" * 50)
    assert len(title.name_field.text) == worlds.NAME_MAX
    # Esc e VOLTAR voltam pra lista
    title.on_key(pygame.K_ESCAPE)
    assert title.screen == "worlds" and not title.wants_text


# ---- App: título -> Mundos -> Novo mundo -> jogo com a seed ---------------------------------------------
@pytest.fixture(scope="module")
def app_dir():
    folder = Path(tempfile.mkdtemp(prefix="hesper_test_worlds_"))
    settings.SETTINGS_PATH = folder / "settings.json"
    old = worlds.SAVES_DIR, save.SAVE_PATH
    worlds.SAVES_DIR, save.SAVE_PATH = folder / "saves", folder / "saves" / "slot1.json"
    yield folder
    worlds.SAVES_DIR, save.SAVE_PATH = old
    pygame.quit()


def test_app_creates_world_with_seed_and_continue_opens_it(app_dir):
    from game.app import App
    app = App(scale=1)
    assert app.mode == "title" and [a for a, _ in app.title.options()] == ["worlds", "quit"]
    app.on_key(pygame.K_RETURN)                                    # Mundos
    app.on_key(pygame.K_RETURN)                                    # espaço 1 vazio -> Novo mundo
    assert app.title.screen == "form" and app.text_input
    for chunk in ("Ar", "eia"):
        pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=chunk))
    app.handle_events()
    app.on_key(pygame.K_TAB)
    pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text="duna"))
    app.handle_events()
    app.on_key(pygame.K_RETURN)                                    # Criar
    assert app.mode == "play" and app.slot == 1 and not app.text_input
    s = app.state
    assert (s.world_name, s.seed) == ("Areia", worlds.text_seed("duna"))
    # a seed chega no desenho (transição e grãos da poeira), não a C.WORLD_SEED
    app.step(1 / 60)
    assert app.renderer.surface_map.seed == s.seed == app.renderer.seed
    s.play_time = 125.0
    assert app.save_game(notify=False) and worlds.path(1).exists()
    app.open_title()
    assert [a for a, _ in app.title.options()] == ["continue", "worlds", "quit"]
    app.on_key(pygame.K_RETURN)                                    # Continuar
    assert app.mode == "play" and app.state.world_name == "Areia" and app.state.seed == s.seed
    assert app.state.play_time == 125.0


def test_v13_world_list_shows_the_old_green_as_umido(saves):
    state = save.new_state()
    data = save.state_to_dict(state)
    data["version"] = 13
    data["progress"]["stage"] = 4                                  # o Verde antigo
    data["world"] = {"name": "Velho", "seed": 7, "created": "", "played_s": 0.0}
    worlds.path(1).write_text(json.dumps(data), encoding="utf-8")
    info = worlds.info(1)
    assert info.status == "ok" and info.stage == C.MIST_STAGE
    assert C.STAGES[info.stage - 1].name == "ÚMIDO"
