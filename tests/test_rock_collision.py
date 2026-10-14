"""Rocha pequena colide só na base do desenho (C.SMALL_ROCK_RECT), não no tile inteiro (playtest do dono)."""
import random

from game import config as C
from game.player import overlaps
from game.systems import GameState


def test_small_rock_blocks_only_its_base():
    g = GameState(rng=random.Random(1))
    w = g.world
    tx, ty = next((x, y) for y in range(w.height) for x in range(w.width) if w.get(x, y) in C.SMALL_ROCKS)
    T = C.TILE
    top = (tx * T + 9, ty * T + 2, 14, 8)                  # pés do player na faixa de cima do tile da rocha
    base = (tx * T + 9, ty * T + 20, 14, 8)                # pés em cima da base do desenho
    assert not any(overlaps(top, r) for r in g.solids_near(top))
    assert any(overlaps(base, r) for r in g.solids_near(base))
