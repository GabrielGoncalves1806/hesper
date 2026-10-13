"""v11 do Som ligado no jogo: gelo (ice_crack / ice_collapse), chuva por pancada e chiado da fumarola (vent_hiss).

Regras puras e eventos com um App falso (não abre janela nem mixer). Mesmo estilo de test_audio_rules.py.
"""

import os
import random
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from game import audio as sound  # noqa: E402
from game import config as C  # noqa: E402
from game.audio import Audio, ice_collapse_gain, vent_hiss_volume  # noqa: E402
from game.rain import Rain, pick_rain_variant, rain_level  # noqa: E402
from game.systems import GameState  # noqa: E402

DT = 0.5


class RecordingAudio:
    """Anota os play() em vez de tocar."""

    def __init__(self):
        self.plays: list[tuple[str, float]] = []

    def play(self, name, delay=0.0, gain=1.0):
        self.plays.append((name, gain))


def fake_app(layer: str = "surface"):
    """O suficiente do App pro on_game_event dos eventos de gelo (sem janela)."""
    from game.app import App
    state = SimpleNamespace(layer=layer, surface=SimpleNamespace(geo=None))
    app = SimpleNamespace(
        state=state,
        audio=RecordingAudio(),
        show_thaw_notice=lambda text: None,
        show_toast=lambda text, seconds=0.0: None,
        renderer=SimpleNamespace(minimap=SimpleNamespace(repaint=lambda *a, **k: None)),
    )
    app.play_ice_break = lambda collapse: App.play_ice_break(app, collapse)
    return app, App.on_game_event


# ---------------------------------------------------------------- gelo
def test_crater_thaw_stages_1_to_3_crack_and_stage_4_collapses():
    app, on_event = fake_app()
    for stage in (1, 2, 3):
        on_event(app, ("crater_thaw", stage))
    on_event(app, ("crater_thaw", C.CRATER_ICE_STAGES))
    names = [name for name, _ in app.audio.plays]
    assert names == ["ice_crack", "ice_crack", "ice_crack", "ice_collapse"]
    assert all(gain == 1.0 for _, gain in app.audio.plays)     # na superfície, volume cheio


def test_gate_thaw_collapses_only_when_the_gate_opens():
    app, on_event = fake_app()
    on_event(app, ("gate_thaw", 0, 1))
    on_event(app, ("gate_thaw", 0, 2))
    assert app.audio.plays == []                               # etapas 1 e 2: ainda sem som
    on_event(app, ("gate_thaw", 0, 3))
    assert app.audio.plays == [("ice_collapse", 1.0)]


def test_collapse_in_the_cave_is_quieter():
    app, on_event = fake_app(layer="cave")
    on_event(app, ("crater_thaw", C.CRATER_ICE_STAGES))
    (name, gain), = app.audio.plays
    assert name == "ice_collapse"
    assert C.VOLUME["ice_collapse"] * gain == pytest.approx(C.ICE_COLLAPSE_CAVE_VOLUME)
    assert ice_collapse_gain(in_cave=False) == 1.0


def test_ice_crack_never_repeats_twice_in_a_row(monkeypatch):
    audio = Audio(enabled=False)
    monkeypatch.setattr(audio, "_get", lambda name: ["crack_a", "crack_b"] if name == "ice_crack" else [])
    picks = [audio._pick("ice_crack") for _ in range(200)]
    assert all(a != b for a, b in zip(picks, picks[1:]))
    assert set(picks) == {"crack_a", "crack_b"}


def test_ice_volumes_from_the_v11_table():
    assert C.VOLUME["ice_crack"] == 0.7
    assert C.VOLUME["ice_collapse"] == 0.8
    assert C.ICE_COLLAPSE_CAVE_VOLUME == 0.5


# ---------------------------------------------------------------- chuva
def test_rain_does_not_play_in_the_cave():
    s = GameState(rng=random.Random(1))
    s.stage = C.MIST_STAGE
    s.rain.intensity = 0.9
    assert rain_level(s) == 0.9
    s.enter_layer("cave")
    assert rain_level(s) == 0.0
    assert sound.rain_volume(rain_level(s)) == 0.0


def test_rain_volume_is_055_times_intensity():
    assert C.VOLUME["amb_rain"] == 0.55
    assert sound.rain_volume(1.0) == pytest.approx(0.55)
    assert sound.rain_volume(0.5) == pytest.approx(0.275)


def test_rain_variant_weights_in_the_mist():
    table = C.RAIN_VARIANTS_MIST
    assert pick_rain_variant(0.0, table) == "amb_rain"          # a média é a principal
    assert pick_rain_variant(0.59, table) == "amb_rain"
    assert pick_rain_variant(0.7, table) == "amb_rain_light"
    assert pick_rain_variant(0.99, table) == "amb_rain_heavy"


def test_green_rain_never_gets_the_heavy_variant():
    names = {name for name, _ in C.RAIN_VARIANTS_GREEN}
    assert names == {"amb_rain", "amb_rain_light"}
    rain = Rain(seed=5)
    seen = set()
    for _ in range(4000):
        if rain.update(DT, C.GREEN_STAGE):
            seen.add(rain.variant)
    assert seen == {"amb_rain", "amb_rain_light"}


def test_each_shower_draws_a_variant_by_seed():
    def variants(seed):
        rain = Rain(seed)
        out = []
        for _ in range(20000):
            if rain.update(DT, C.MIST_STAGE):
                out.append(rain.variant)
        return out

    first = variants(11)
    assert len(first) > 10                                      # várias pancadas
    assert variants(11) == first                                # mesma seed, mesmo sorteio
    assert set(first) >= {"amb_rain", "amb_rain_light"}         # a mistura aparece
    assert variants(12) != first


# ---------------------------------------------------------------- fumarola
def test_vent_hiss_is_full_close_and_silent_far():
    full = C.VOLUME["vent_hiss"]
    assert full == 0.6
    assert vent_hiss_volume(0.0) == full
    assert vent_hiss_volume(2.0) == full
    assert 0 < vent_hiss_volume(4.5) < full
    assert vent_hiss_volume(7.0) == 0.0
    assert vent_hiss_volume(20.0) == 0.0
    assert vent_hiss_volume(None) == 0.0                        # nenhuma fumarola acordada


def test_vent_distance_takes_the_nearest_awake_vent():
    from game import systems
    vents = [SimpleNamespace(tx=10, ty=10, size=(2, 2)), SimpleNamespace(tx=40, ty=40, size=(2, 2))]
    fake = SimpleNamespace(
        surface=SimpleNamespace(geo=SimpleNamespace(vents=vents), vents_awake=[False, True]),
        player=SimpleNamespace(x=(41 + 0.5) * C.TILE, y=(41 + 1) * C.TILE),   # em cima da 2ª (pé em 41, 41)
    )
    assert systems.GameState.vent_distance(fake) == pytest.approx(0.0)  # a 1ª (dormente) nem conta
    fake.surface.vents_awake = [False, False]
    assert systems.GameState.vent_distance(fake) is None
    fake.surface.vents_awake = [True, False]
    assert systems.GameState.vent_distance(fake) > 20
