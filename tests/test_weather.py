"""Tempestade (v0.4 Marco 1, trilha B): clima determinístico (vento, rajadas, visão), empurrão da rajada,
O₂ ×1,25 fora da base e o aviso RAJADA no HUD.

A intensidade da tempestade (`state.storm`) é da trilha A: aqui ela é ligada direto no objeto."""

import math
import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game.audio import gust_gain  # noqa: E402
from game.player import overlaps  # noqa: E402
from game.systems import Controls, GameState  # noqa: E402
from game.ui import UI, gust_warning  # noqa: E402
from game.weather import Weather  # noqa: E402

DT = 0.05


# ---- B1: clima ------------------------------------------------------------------------------------
def gust_starts(w: Weather, seconds: float, storm: float = 1.0) -> list[float]:
    times = []
    for i in range(int(seconds / DT)):
        prev = w.gust
        w.update(DT, storm)
        if prev == 0 and w.gust > 0:
            times.append(i * DT)
    return times


def test_gusts_happen_on_schedule_and_only_in_storm():
    w = Weather(1)
    times = gust_starts(w, 120)
    assert 3 <= len(times) <= 6
    w2 = Weather(1)
    for _ in range(2400):
        w2.update(DT, 0.0)
    assert w2.gust == 0 and w2.view_tiles == math.inf


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 1234])
def test_gust_intervals_and_lengths_follow_config(seed):
    w = Weather(seed)
    starts, lengths, t, on = [], [], 0.0, None
    for _ in range(int(400 / DT)):
        started = w.update(DT, 1.0)
        t += DT
        if started:
            starts.append(t)
            on = t
        if on is not None and w.gust_left <= 0:
            lengths.append(t - on)
            on = None
    lo, hi = C.STORM_GUST_FIRST
    assert lo - DT <= starts[0] <= hi + DT
    for a, b in zip(starts, starts[1:]):
        assert C.STORM_GUST_EVERY[0] - DT <= b - a <= C.STORM_GUST_EVERY[1] + DT
    for length in lengths:
        assert C.STORM_GUST_LEN[0] - DT <= length <= C.STORM_GUST_LEN[1] + DT


def test_weather_is_deterministic_by_seed():
    a, b, c = Weather(7), Weather(7), Weather(8)
    ta, tb, tc = gust_starts(a, 200), gust_starts(b, 200), gust_starts(c, 200)
    assert ta == tb and a.wind == b.wind
    assert ta != tc or a.wind != c.wind


def test_gust_ramps_in_about_half_a_second():
    w = Weather(1)
    while not w.update(DT, 1.0):
        pass
    steps = 1
    while w.gust < 1.0:
        w.update(DT, 1.0)
        steps += 1
    assert steps * DT == pytest.approx(C.STORM_GUST_RAMP, abs=DT)


def test_wind_turns_slowly():
    w = Weather(3)
    prev = w.wind
    for _ in range(int(300 / DT)):
        w.update(DT, 1.0)
        turn = math.degrees(math.acos(max(-1.0, min(1.0, prev[0] * w.wind[0] + prev[1] * w.wind[1]))))
        assert turn <= 15 * DT + 1e-6
        assert math.hypot(*w.wind) == pytest.approx(1.0)
        prev = w.wind


def test_view_shrinks_in_gust():
    w = Weather(1)
    w.gust = 1.0
    w._recompute(storm=1.0)
    assert w.view_tiles == pytest.approx(C.STORM_GUST_VIEW_TILES)
    w.gust = 0.0
    w._recompute(storm=1.0)
    assert w.view_tiles == pytest.approx(C.STORM_VIEW_TILES)
    w.gust = 0.5
    w._recompute(storm=1.0)
    assert C.STORM_GUST_VIEW_TILES < w.view_tiles < C.STORM_VIEW_TILES


def test_view_opens_as_storm_fades():
    w = Weather(1)
    views = []
    for storm in (1.0, 0.75, 0.5, 0.25, 0.01):
        w._recompute(storm=storm)
        views.append(w.view_tiles)
    assert views == sorted(views) and views[-1] > 100
    w._recompute(storm=0.0)
    assert w.view_tiles == math.inf


def test_no_new_gust_while_storm_is_fading():
    """Transição pro Árido: as rajadas param (a que estava rolando termina, nova não começa)."""
    w = Weather(1)
    assert gust_starts(w, 300, storm=0.8) == []


# ---- B2: empurrão --------------------------------------------------------------------------------
def open_field(g: GameState, wall_at: int | None = None) -> tuple[int, int]:
    """Campo aberto longe da base (12×5 tiles de chão) com o player no meio. `wall_at`: coluna (relativa)
    de uma parede inteira à direita. Devolve o tile do player."""
    bx, by = C.BASE_TILE
    tx, ty = bx + 30, by
    for x in range(tx - 6, tx + 7):
        for y in range(ty - 3, ty + 3):
            g.world.set(x, y, g.world.floor_kind)
    if wall_at is not None:
        for y in range(ty - 3, ty + 3):
            g.world.set(tx + wall_at, y, C.ROCK)
    g.player.x, g.player.y = (tx + 0.5) * C.TILE, (ty + 1) * C.TILE - 2
    return tx, ty


def stormy(g: GameState, gust: float = 1.0) -> None:
    """Liga a tempestade cheia com o vento pra leste e uma rajada que não acaba."""
    g.storm = 1.0
    w = g.weather
    w.dominant = w.angle = w.target = 0.0
    w.retarget_in = 1e9
    w._update_wind_vector()
    w.gust, w.gust_left = gust, 1e9


def run(g: GameState, seconds: float, controls: Controls | None = None) -> None:
    for _ in range(round(seconds / DT)):
        g.update(DT, controls or Controls())


def test_standing_player_slides_with_the_gust():
    g = GameState(seed=C.WORLD_SEED)
    open_field(g)
    stormy(g)
    x0, y0 = g.player.x, g.player.y
    run(g, 1.0)
    assert g.player.x - x0 == pytest.approx(C.PLAYER_SPEED * C.STORM_PUSH, rel=0.05)
    assert g.player.y == pytest.approx(y0)
    assert not g.player.moving            # desliza sem animar a caminhada


def test_walking_against_the_wind_still_moves_forward():
    g = GameState()
    open_field(g)
    stormy(g)
    x0 = g.player.x
    run(g, 1.0, Controls(move_x=-1))
    moved = x0 - g.player.x
    assert moved > 0
    assert moved == pytest.approx(C.PLAYER_SPEED * (1 - C.STORM_PUSH), rel=0.05)
    assert g.player.direction == "left"   # o vento não vira o player


def test_gust_never_pushes_through_walls():
    g = GameState()
    tx, ty = open_field(g, wall_at=2)
    stormy(g)
    wall = ((tx + 2) * C.TILE, ty * C.TILE, C.TILE, C.TILE)
    for _ in range(int(5 / DT)):
        g.update(DT, Controls())
        assert not overlaps(g.player.box, wall)
    assert g.player.box[0] + g.player.box[2] == pytest.approx(wall[0])   # encostado na parede


def test_no_push_without_storm_or_in_cave():
    g = GameState()
    open_field(g)
    stormy(g)
    g.storm = 0.0
    x0 = g.player.x
    run(g, 1.0)
    assert g.player.x == pytest.approx(x0)


def test_no_push_when_fainted_on_ramp_or_in_menu():
    g = GameState()
    open_field(g)
    stormy(g)
    x0 = g.player.x
    run(g, 1.0, Controls(in_menu=True))          # inventário/fabricador/mapa aberto
    assert g.player.x == pytest.approx(x0)
    g.ramp = __import__("game.systems", fromlist=["RampTrip"]).RampTrip("cave")
    g.ramp.time = -100.0                          # fade que não troca de camada durante o teste
    run(g, 0.5)
    assert g.player.x == pytest.approx(x0)
    g.ramp = None
    g.fainted, g.faint_time = True, -100.0        # desmaiado (sem chegar no respawn)
    run(g, 0.5)
    assert g.player.x == pytest.approx(x0)


def test_push_scales_with_storm_and_gust():
    w = Weather(1)
    w.wind, w.gust = (0.0, 1.0), 0.5
    vx, vy = w.push(0.5)
    assert vx == pytest.approx(0.0)
    assert vy == pytest.approx(C.PLAYER_SPEED * C.STORM_PUSH * 0.25)
    w.gust = 0.0
    assert w.push(1.0) == (0.0, 0.0)


# ---- B3: O₂ -------------------------------------------------------------------------------------
def o2_after(g: GameState, seconds: float) -> float:
    start = g.o2
    run(g, seconds)
    return start - g.o2


def test_o2_drains_faster_outside_base_in_storm():
    g = GameState()
    open_field(g)
    g.storm = 1.0
    assert o2_after(g, 4.0) == pytest.approx(4.0 * C.O2_DRAIN * C.STORM_O2_MULT, rel=0.01)
    g.storm = 0.5
    assert o2_after(g, 4.0) == pytest.approx(4.0 * C.O2_DRAIN * (1 + (C.STORM_O2_MULT - 1) * 0.5), rel=0.01)
    g.storm = 0.0
    assert o2_after(g, 4.0) == pytest.approx(4.0 * C.O2_DRAIN, rel=0.01)


def test_o2_inside_base_is_unchanged_by_storm():
    calm, storm = GameState(), GameState()
    storm.storm = 1.0
    for g in (calm, storm):
        g.o2 = 50.0
        g.player.x, g.player.y = C.BASE_CENTER[0], C.BASE_CENTER[1] + 40
        g.weather.next_gust = 1e9            # sem rajada: o player fica na zona
        run(g, 1.0)
    assert storm.in_base_zone() and storm.o2 == pytest.approx(calm.o2)


def test_o2_in_cave_is_unchanged_by_storm():
    g = GameState()
    g.storm = 1.0
    g.enter_layer("cave")
    assert g.o2_drain_mult == 1.0
    assert o2_after(g, 2.0) == pytest.approx(2.0 * C.O2_DRAIN, rel=0.01)


# ---- B4: aviso no HUD e som ----------------------------------------------------------------------
def test_gust_warning_shows_above_threshold_and_goes_away():
    g = GameState()
    g.storm = 1.0
    seen = []
    for _ in range(int(80 / DT)):
        g.update(DT, Controls())
        seen.append(gust_warning(g))
        assert gust_warning(g) == (g.weather.gust > C.STORM_GUST_WARN)
    assert any(seen)
    first_on = seen.index(True)
    assert False in seen[first_on:]           # depois de aparecer, some quando a rajada baixa


def test_gust_warning_is_drawn_below_left_column():
    pygame.font.init()
    ui = UI()
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    g = GameState()
    g.storm = 1.0
    ui.begin()
    ui.draw_hud(g, 0.0, None, {r: pygame.Surface((8, 8), pygame.SRCALPHA) for r in C.RESOURCES})
    ui.draw_gust_warning(g, 0.0)
    assert ui.gust_rect is None
    g.weather.gust = 0.8
    ui.begin()
    ui.draw_hud(g, 0.0, None, {r: pygame.Surface((8, 8), pygame.SRCALPHA) for r in C.RESOURCES})
    ui.draw_objectives([])
    ui.draw_gust_warning(g, 0.0)
    assert ui.gust_rect is not None and ui.gust_rect.top > 23 and ui.gust_rect in ui.hud_rects


def test_gust_event_and_sound_gain():
    g = GameState()
    g.storm = 1.0
    events = []
    for _ in range(int(60 / DT)):
        g.update(DT, Controls())
        events += [e for e in g.pop_events() if e[0] == "gust"]
    assert events and all(e[1] == 1.0 for e in events)
    assert gust_gain(1.0) == 1.0 and gust_gain(0.5) == 0.5 and gust_gain(0.0) == 0.0
    assert 0 < C.VOLUME["gust"] <= 1
