"""Animação das máquinas (tiras anim/anim_*.png) e rochas pequenas com veio (rock_small_<minério>_{0,1})."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.render import (ANIM_FRAMES, MACHINE_ANIM_FPS, Renderer, anim_frame_index, rock_variant,  # noqa: E402
                         tile_phase)
from game.systems import GameState, Machine  # noqa: E402


def renderer(enabled: bool = True) -> Renderer:
    pygame.init()
    pygame.display.set_mode((64, 64))
    return Renderer(Sprites(enabled=enabled))


# ---------------------------------------------------------------- escolha do quadro
def test_frame_index_by_time_and_phase():
    step = 1 / MACHINE_ANIM_FPS
    assert [anim_frame_index(i * step + 0.01) for i in range(6)] == [0, 1, 2, 3, 0, 1]
    assert anim_frame_index(0.01, phase=2) == 2
    assert anim_frame_index(3 * step + 0.01, phase=2) == 1           # dá a volta


def test_not_working_is_always_frame_zero():
    assert all(anim_frame_index(t / 10, phase=3, working=False) == 0 for t in range(40))


def test_phase_is_stable_per_tile_and_differs_between_tiles():
    assert tile_phase(5, 9) == tile_phase(5, 9)
    phases = {tile_phase(x, y) for x in range(8) for y in range(8)}
    assert phases == set(range(ANIM_FRAMES))
    assert all(0 <= p < ANIM_FRAMES for p in phases)


def test_machine_frame_zero_when_submerged_or_without_power():
    r = renderer()
    r.machine_t = 7.3
    m = Machine("o2", 4, 6)
    assert r.machine_anim_index(m, True, 3.0) == anim_frame_index(7.3, tile_phase(4, 6))
    assert r.machine_anim_index(m, False, 3.0) == 0                  # sem energia nenhuma
    m.submerged = True
    assert r.machine_anim_index(m, True, 3.0) == 0                   # submersa


def test_solar_ignores_power_and_runs_on_the_clock():
    r = renderer()
    r.machine_t = 0.0
    m = Machine("solar", 2, 2)
    assert r.machine_anim_index(m, False, 0.45) == anim_frame_index(0.45, tile_phase(2, 2))
    m.submerged = True
    assert r.machine_anim_index(m, True, 0.45) == 0


def test_station_animates_only_with_a_drone_inside():
    s = GameState(rng=random.Random(1))
    r = renderer()
    r.machine_t = 0.45
    m = Machine("drone_station", 3, 3)
    assert r.machine_anim_index(m, True, 0.0) == 0                   # sem estação montada / sem drone
    from game import drones
    m.station = drones.Station()
    assert r.machine_anim_index(m, True, 0.0) == 0
    m.station.drones.append(object())
    assert r.machine_anim_index(m, True, 0.0) == anim_frame_index(0.45, tile_phase(3, 3))
    assert s is not None


def test_deficit_runs_slower_because_machine_t_follows_the_factor():
    # o App faz machine_t += dt * power.factor: com fator 0.5 passa metade dos quadros no mesmo tempo
    full = anim_frame_index(2.0)
    half = anim_frame_index(2.0 * 0.5)
    assert (full, half) == (10 % 4, 5 % 4)


# ---------------------------------------------------------------- tiras e fallback
def test_strips_cut_into_four_frames_of_the_still_size_and_cached():
    r = renderer()
    for kind in ("o2", "heater_t2", "melter"):
        still = r.surface(C.MACHINES[kind].sprite, lambda: None)[0]
        frames = r.anim_frames(C.MACHINES[kind].sprite, still)
        assert frames is not None and len(frames) == ANIM_FRAMES
        assert all(f.get_size() == still.get_size() for f in frames)
        assert r.anim_frames(C.MACHINES[kind].sprite, still) is frames       # cache
    pod = r.surface("pod", lambda: None)[0]
    assert r.anim_frames("pod", pod) is not None


def test_missing_strip_falls_back_to_the_still():
    r = renderer()
    still = pygame.Surface((40, 56), pygame.SRCALPHA)
    assert r.anim_frames("nao_existe", still) is None
    assert r.anim_surface("nao_existe", still, 2) is still
    wrong = pygame.Surface((10, 10), pygame.SRCALPHA)                      # tira existe mas não bate: parado
    assert r.anim_surface("machine_o2", wrong, 1) is wrong


def test_sprites_off_always_uses_the_still():
    r = renderer(enabled=False)
    still = pygame.Surface((40, 56), pygame.SRCALPHA)
    assert r.anim_surface("machine_o2", still, 3) is still


def test_ghost_and_icon_use_the_still():
    r = renderer()
    canvas = pygame.Surface((120, 120), pygame.SRCALPHA)
    r.draw_machine(canvas, "o2", 60, 100, 0.0, alpha=128)                  # fantasma: sem frame, sem erro
    still = r.surface("machine_o2", lambda: None)[0]
    assert r.anim_surface("machine_o2", still, None) is still


# ---------------------------------------------------------------- rochas com veio
def test_rock_variant_is_deterministic_per_tile_and_uses_both():
    assert rock_variant(12, 34) == rock_variant(12, 34)
    assert {rock_variant(x, y) for x in range(10) for y in range(10)} == {0, 1}


def test_right_png_per_ore_and_variant():
    r = renderer()
    for res in C.SMALL_ROCKS.values():
        for tx, ty in ((0, 0), (1, 0), (0, 1), (7, 3)):
            surf, old = r.small_rock_surface(res, tx, ty)
            expected = r.sprites.get(f"rock_small_{res}_{rock_variant(tx, ty)}")
            assert not old and surf is expected and surf.get_size() == (32, 32)


def test_small_rock_falls_back_to_old_way_without_png():
    r = renderer(enabled=False)
    surf, old = r.small_rock_surface("iron", 3, 4)
    assert old and surf.get_size() == (32, 32)
    assert r.small_rock_surface("iron", 5, 5)[0] is surf                  # fallback no cache
    canvas = pygame.Surface((32, 32), pygame.SRCALPHA)
    r.draw_small_rock(canvas, 0, 0, "iron", 3, 4)
