"""v0.6 Fundo M2: chão assado da caverna (game/cave_ground.py)."""
import numpy as np
import pytest

from game import cave_gen
from game import cave_ground as CG
from game import config as C
from game import ground as G
from game.geo import BASALT, FROST, PLATEAU, SALAR


@pytest.fixture(scope="module")
def art():
    a = CG.CaveArt()
    assert a.ok, "assets/sprites/cave_ground/ incompleto"
    return a


@pytest.fixture(scope="module")
def world():
    return cave_gen.generate_cave(7)


def test_art_loads_four_textures_and_decals(art):
    assert art.tex_stack.shape == (4, G.BP, G.BP)
    assert {"scoria", "icesheet", "wet", "soil"} <= set(art.decals)
    assert art.cover is False and art.v9 == {}


def test_lut_has_eight_colours_per_class_plus_outline(art):
    lut = art.lut()
    assert lut.shape == (G.NEW, 3)
    for c in range(4):
        assert tuple(lut[c * 16 + 8]) == G.OUTLINE
    assert tuple(lut[BASALT * 16 + 7]) == (0xFF, 0x8A, 0x45)       # brasa do basalto (seção 0.1 do report)


def test_missing_folder_is_not_ok(tmp_path):
    assert CG.CaveArt(tmp_path).ok is False


def test_bake_is_deterministic_and_has_no_bed(world, art):
    geo = CG.CaveGeo(world)
    bx, by = world.center[0] // G.BT, world.center[1] // G.BT
    a = _bake(geo, art, bx, by)
    b = _bake(geo, art, bx, by)
    assert np.array_equal(a, b)
    assert not np.any((a // 16) == G.BED)                            # sem leito na caverna
    assert set(np.unique(a // 16)) <= {PLATEAU, SALAR, BASALT, FROST}


def test_border_is_curved_not_on_tile_lines(world, art):
    """Num bloco que tem duas regiões, a troca de classe não fica só nas linhas de 32 px."""
    geo = CG.CaveGeo(world)
    reg = world.cave_region
    for by in range(reg.shape[0] // G.BT):
        for bx in range(reg.shape[1] // G.BT):
            sub = reg[by * G.BT:(by + 1) * G.BT, bx * G.BT:(bx + 1) * G.BT]
            if len(np.unique(sub)) > 1:
                cls = _bake(geo, art, bx, by) // 16
                change = np.nonzero(cls[:, 1:] != cls[:, :-1])[1] + 1
                assert np.any(change % G.T != 0)
                return
    pytest.fail("nenhum bloco com fronteira na seed 7")


def test_no_decals_near_arrival(world, art):
    geo = CG.CaveGeo(world)
    skip = CG.arrival_skip(world.center, C.CAVE_DECAL_CLEAR)
    ctx = G.BakeContext(geo)
    ctx.skip = skip
    bx, by = world.center[0] // G.BT, world.center[1] // G.BT
    for x, y, _, idx in G.decals_for_block(geo, art, bx, by, ctx.tcls, skip):
        cx, cy = (x + idx.shape[1] // 2) // G.T, (y + idx.shape[0] // 2) // G.T
        assert (cx, cy) not in skip


def test_cave_ground_draws_and_bakes(world, monkeypatch):
    import pygame
    pygame.init()
    gr = CG.CaveGround()
    gr.sync = True
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    cam = (world.center[0] * G.T - 480, world.center[1] * G.T - 270)
    gr.draw(canvas, CG.CaveGeo(world), cam, (C.SCREEN_W, C.SCREEN_H), None)
    assert gr.bake_ms, "assou pelo menos 1 bloco"
    assert canvas.get_at((480, 270))[:3] != (0, 0, 0)


def _bake(geo, art, bx, by):
    ctx = G.BakeContext(geo)
    ctx.skip = set()
    gen = G.bake_block_codes(geo, art, bx, by, ctx)
    out = None
    while out is None:
        out = next(gen)
    return out[0]
