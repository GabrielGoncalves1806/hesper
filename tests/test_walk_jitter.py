"""Player "com frio" andando na diagonal: com a câmera seguindo, o sprite tem que ficar parado na tela.

O bug: a câmera truncava (int) a posição do player e o sprite arredondava (round). Na diagonal o
player anda ~1,41 px por quadro, a parte quebrada cruzava 0,5 quase todo quadro e o sprite pulava
1 px pra lá e pra cá (119 saltos em 120 quadros). Diagnóstico: tools/dev/walk_jitter.py.
"""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import viewport as V  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.render import Renderer  # noqa: E402
from game.systems import GameState  # noqa: E402

DTS = (0.016, 0.017)          # o clock.tick(60) devolve 16 ou 17 ms
DIAGONALS = ((1, 1), (-1, 1), (1, -1), (-1, -1))
STRAIGHT = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Recorder:
    def __init__(self):
        self.blits = []

    def blit(self, surf, pos, *a, **k):
        self.blits.append((surf.get_size(), tuple(pos)))


@pytest.fixture(scope="module")
def renderer():
    pygame.init()
    pygame.display.set_mode((1, 1))
    return Renderer(Sprites(enabled=False))


def walk(renderer, direction, zoom, frames=120, start=(2000.3, 1500.0), solids=lambda _box: []):
    """Anda N quadros e devolve [(posição do sprite na visão, direção, player.x, player.y)]."""
    game = GameState(rng=random.Random(1))
    p = game.player
    p.x, p.y = start
    view = V.view_size(zoom)
    renderer.view_w, renderer.view_h = view
    out = []
    for i in range(frames):
        p.move(direction[0], direction[1], DTS[i % 2], solids)
        cam = renderer.camera(game, view)
        rec = Recorder()
        renderer.collect_objects(rec, game, cam, 0.0)[-1][1]()     # o player é o último objeto
        sprite = next(pos for size, pos in rec.blits if size == (32, 32))
        out.append((sprite, p.direction, p.x, p.y))
    return out


@pytest.mark.parametrize("zoom", C.ZOOM_LEVELS)
@pytest.mark.parametrize("direction", DIAGONALS + STRAIGHT)
def test_sprite_fica_parado_na_tela_com_camera_seguindo(renderer, zoom, direction):
    rows = walk(renderer, direction, zoom)
    positions = {r[0] for r in rows}
    assert len(positions) == 1, f"sprite mexeu na tela: {sorted(positions)}"
    # e ele está no centro da visão (pé no meio na horizontal, 16 px abaixo do meio na vertical)
    vw, vh = V.view_size(zoom)
    (sx, sy), = positions
    assert (sx + 16, sy + 32) == (vw // 2, vh // 2 + 16)


@pytest.mark.parametrize("direction", ((1, -1), (-1, -1)))
def test_sprite_parado_deslizando_na_parede(renderer, direction):
    """Diagonal empurrando uma parede em cima: o player escorrega de lado e o sprite não treme."""
    top = 1500.0 - C.PLAYER_BOX_H
    rows = walk(renderer, direction, 1.0, solids=lambda _box: [(0, top - 32, 99999, 32)])
    assert all(r[3] == 1500.0 for r in rows)               # não subiu: está deslizando
    assert len({r[0] for r in rows}) == 1


@pytest.mark.parametrize("zoom", C.ZOOM_LEVELS)
def test_na_borda_do_mapa_o_sprite_anda_sem_voltar(renderer, zoom):
    """Câmera presa no canto (0, 0): agora quem anda na tela é o sprite, sempre pra frente, nunca de volta."""
    rows = walk(renderer, (1, 1), zoom, frames=60, start=(40.3, 60.0))
    xs = [r[0][0] for r in rows]
    ys = [r[0][1] for r in rows]
    assert all(b >= a for a, b in zip(xs, xs[1:]))
    assert all(b >= a for a, b in zip(ys, ys[1:]))
    assert all(b - a <= 2 for a, b in zip(xs, xs[1:]))
    assert xs[-1] > xs[0]


@pytest.mark.parametrize("direction", DIAGONALS)
def test_direcao_do_sprite_nao_alterna_na_diagonal(renderer, direction):
    rows = walk(renderer, direction, 1.0, frames=60)
    assert {r[1] for r in rows} == {"right" if direction[0] > 0 else "left"}
