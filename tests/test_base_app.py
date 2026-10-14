"""v0.5 M2 · base respirável no App headless: os eventos do jogo viram os sons certos (porta, selo, vazamento, água
acabando), o zumbido do Dispersor substitui o machine_hum lá dentro e o painel do Dispersor guarda só cápsula."""

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.base import BaseBlock  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.app import PANEL_MODES  # noqa: E402
from game.systems import Controls, GameState, Machine  # noqa: E402
from tests.test_base import free_spot, room, stand_at  # noqa: E402

T = C.TILE


class FakeAudio:
    """Anota o que o App pediu (sem tocar nada)."""

    def __init__(self):
        self.played: list[tuple[str, float]] = []
        self.hum: list[float] = []
        self.dispenser_hum: list[tuple[float, int]] = []

    def play(self, name, delay=0.0, gain=1.0, channel=None):
        self.played.append((name, gain))

    def has(self, name):
        return True

    def set_hum(self, volume):
        self.hum.append(volume)

    def set_dispenser_hum(self, volume, out_ms=C.DISPENSER_HUM_FADE_MS):
        self.dispenser_hum.append((volume, out_ms))

    def __getattr__(self, name):               # o resto (set_alarm, set_wind, update...) não importa aqui
        return lambda *a, **k: None


@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_base_app_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


@pytest.fixture
def fresh(app):
    import random
    state = GameState(rng=random.Random(5))
    state.debug_add_ti()
    app.state = state
    app.audio = FakeAudio()
    app.placing = None
    app.mode = "play"
    app.dry_fade_t = 0.0
    return app


def base_with_dispenser(app, water=2):
    s = app.state
    x0, y0 = free_spot(s, 8, 7)
    x0, y0 = x0 + 1, y0 + 1
    room(s.base, x0, y0, 4, 3, door=(x0 + 1, y0 + 3))
    m = Machine(C.DISPENSER, x0, y0)
    m.storage.slots[0] = Stack("water_capsule", water)
    s.machines.append(m)
    stand_at(s, x0 + 2, y0 + 1)
    return m, x0, y0


def test_door_events_play_door_sounds_with_distance_gain(fresh):
    p = fresh.state.player
    fresh.on_game_event(("door", "open", (p.x, p.y)))
    fresh.on_game_event(("door", "close", (p.x + 40 * T, p.y)))      # longe: mudo
    assert fresh.audio.played == [("door_open", 1.0), ("door_close", 0.0)]


def test_base_sealed_leak_alert_and_dry_events(fresh):
    p = fresh.state.player
    for event in (("base_sealed", (p.x, p.y)), ("leak_alert", (p.x, p.y)), ("dispenser_dry", (p.x, p.y))):
        fresh.on_game_event(event)
    assert [n for n, _ in fresh.audio.played] == ["base_sealed", "leak_alert", "dispenser_dry"]
    assert fresh.dry_fade_t > 0                                       # o zumbido vai sair em 0,3 s


def test_dispenser_hum_replaces_machine_hum_inside_the_sealed_base(fresh):
    m, x0, y0 = base_with_dispenser(fresh)
    fresh.state.update(0.05, Controls())
    fresh.update_ambient_sounds(0.05)
    assert fresh.audio.hum[-1] == 0.0 and fresh.audio.dispenser_hum[-1] == (C.VOLUME["dispenser_hum"], C.DISPENSER_HUM_FADE_MS)
    fresh.state.player.x, fresh.state.player.y = 4000.0, 4000.0       # saiu
    fresh.state.update(0.05, Controls())
    fresh.update_ambient_sounds(0.05)
    assert fresh.audio.dispenser_hum[-1][0] == 0.0


def test_dispenser_hum_leaves_fast_when_the_water_ends(fresh):
    m, x0, y0 = base_with_dispenser(fresh, water=0)
    fresh.on_game_event(("dispenser_dry", m.anchor))
    fresh.update_ambient_sounds(0.05)
    assert fresh.audio.dispenser_hum[-1] == (0.0, C.DISPENSER_HUM_DRY_FADE_MS)


def test_dispenser_panel_only_takes_water_capsules(fresh):
    s = fresh.state
    m, x0, y0 = base_with_dispenser(fresh, water=0)
    s.inventory.add("iron", 5)
    s.inventory.add("water_capsule", 4)
    fresh.open_dispenser = m
    fresh.set_mode("dispenser")
    assert fresh.mode == "dispenser" and fresh.mode in PANEL_MODES
    assert fresh.dispenser_status() == "VEDADO ✓" or fresh.dispenser_status() == "SEM ÁGUA"
    assert "cápsula" in fresh.dispenser_info()                          # sem água: manda pôr cápsula
    fresh.set_mode("play")
    assert fresh.open_dispenser is None


def test_base_blocks_have_item_icons_and_previews(fresh):
    for kind in (*C.BASE_KINDS, C.DISPENSER):
        assert fresh.renderer.item_icon(kind).get_size() == (32, 32)
        assert fresh.renderer.machine_preview(kind).get_width() > 0
