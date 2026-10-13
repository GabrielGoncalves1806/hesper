"""Animações do player: minerando > andando > parado, fallback sem PNG e quadro pelo tempo."""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game.render import Renderer  # noqa: E402
from game.systems import GameState, Mining  # noqa: E402


class FakeSprites:
    """Sprites do contrato só com o que o teste põe no dicionário."""

    def __init__(self, sheets: dict[str, pygame.Surface]):
        self.sheets = sheets

    def get(self, name: str):
        return self.sheets.get(name)


def strip(tag: int) -> pygame.Surface:
    """Tira 128×32 em que o pixel (0,0) do quadro i tem cor (tag, i, 0): dá pra saber de onde veio."""
    s = pygame.Surface((128, 32), pygame.SRCALPHA)
    for i in range(4):
        s.fill((tag, i, 0, 255), (i * 32, 0, 32, 32))
    return s


def still(tag: int) -> pygame.Surface:
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    s.fill((tag, 99, 0, 255))
    return s


TAGS = {"walk": 10, "idle": 20, "mine": 30}


def full_sprites() -> FakeSprites:
    sheets = {}
    for view in ("down", "side", "up"):
        for anim, tag in TAGS.items():
            sheets[f"player_{anim}_{view}"] = strip(tag)
        sheets[f"player_{view}"] = still(40)
    return FakeSprites(sheets)


@pytest.fixture(scope="module", autouse=True)
def display():
    pygame.init()
    pygame.display.set_mode((1, 1))


@pytest.fixture
def state() -> GameState:
    return GameState(rng=random.Random(1))


def tag_of(surf: pygame.Surface) -> tuple[int, int]:
    c = surf.get_at((0, 0))
    return c.r, c.g


# ---------------------------------------------------------------- escolha por estado
def test_idle_when_still(state):
    state.player.moving = False
    assert Renderer.player_anim(state) == "idle"
    surf, _ = Renderer(full_sprites())._player_frame(state, 0.0)
    assert tag_of(surf)[0] == TAGS["idle"]


def test_walk_when_moving(state):
    state.player.moving = True
    assert Renderer.player_anim(state) == "walk"
    surf, _ = Renderer(full_sprites())._player_frame(state, 0.0)
    assert tag_of(surf)[0] == TAGS["walk"]


@pytest.mark.parametrize("moving", [False, True])
def test_mine_wins_even_while_walking(state, moving):
    state.player.moving = moving
    state.mining = Mining((1, 1))
    assert Renderer.player_anim(state) == "mine"
    surf, _ = Renderer(full_sprites())._player_frame(state, 0.0)
    assert tag_of(surf)[0] == TAGS["mine"]


def test_fainted_uses_still_sprite(state):
    state.fainted = True
    state.player.moving = True
    surf, _ = Renderer(full_sprites())._player_frame(state, 0.0)
    assert tag_of(surf)[0] == 40


@pytest.mark.parametrize("direction,view,flip", [
    ("down", "down", False), ("up", "up", False), ("right", "side", False), ("left", "side", True)])
def test_view_and_flip(state, direction, view, flip):
    sprites = full_sprites()
    sprites.sheets[f"player_idle_{view}"] = strip(77)
    state.player.direction = direction
    surf, flipped = Renderer(sprites)._player_frame(state, 0.0)
    assert tag_of(surf)[0] == 77
    assert flipped is flip


# ---------------------------------------------------------------- fallback
@pytest.mark.parametrize("anim", ["idle", "mine"])
def test_fallback_repeats_contract_still_sprite(state, anim):
    sprites = full_sprites()
    for view in ("down", "side", "up"):
        del sprites.sheets[f"player_{anim}_{view}"]
    if anim == "mine":
        state.mining = Mining((1, 1))
    r = Renderer(sprites)
    for t in (0.0, 0.3, 0.6, 0.9):
        surf, _ = r._player_frame(state, t)
        assert surf.get_size() == (32, 32)
        assert tag_of(surf) == (40, 99)           # o player parado do contrato, igual a antes


def test_fallback_without_any_png(state):
    """Sem nenhum PNG (sprites desligados): cai no art.py e cada quadro é o player parado."""
    r = Renderer(FakeSprites({}))
    still_surf = art.player("down")
    for t in (0.0, 0.5):
        surf, _ = r._player_frame(state, t)
        assert surf.get_size() == (32, 32)
        assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(still_surf, "RGBA")
    state.mining = Mining((1, 1))
    surf, _ = r._player_frame(state, 0.2)
    assert pygame.image.tobytes(surf, "RGBA") == pygame.image.tobytes(still_surf, "RGBA")


# ---------------------------------------------------------------- quadro pelo tempo
def test_anim_frame_math():
    assert [Renderer.anim_frame(i / 4, 4) for i in range(6)] == [0, 1, 2, 3, 0, 1]
    assert Renderer.anim_frame(1 / 12 + 1e-6, 12) == 1
    assert Renderer.anim_frame(0.99, 12) == 3      # 11.88 → 11 % 4


def test_fps_constants():
    assert Renderer.PLAYER_IDLE_FPS < Renderer.PLAYER_WALK_FPS < Renderer.PLAYER_MINE_FPS


def test_idle_frame_follows_render_clock(state):
    r = Renderer(full_sprites())
    fps = Renderer.PLAYER_IDLE_FPS
    frames = [tag_of(r._player_frame(state, (i + 0.5) / fps)[0])[1] for i in range(5)]
    assert frames == [0, 1, 2, 3, 0]


def test_mine_frame_follows_render_clock(state):
    state.mining = Mining((1, 1))
    r = Renderer(full_sprites())
    fps = Renderer.PLAYER_MINE_FPS
    frames = [tag_of(r._player_frame(state, (i + 0.5) / fps)[0])[1] for i in range(5)]
    assert frames == [0, 1, 2, 3, 0]


def test_walk_frame_follows_walk_time_not_clock(state):
    state.player.moving = True
    r = Renderer(full_sprites())
    state.player.walk_time = 1.5 / Renderer.PLAYER_WALK_FPS
    assert tag_of(r._player_frame(state, 0.0)[0])[1] == 1
    assert tag_of(r._player_frame(state, 123.4)[0])[1] == 1
