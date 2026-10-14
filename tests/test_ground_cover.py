"""Cobertura do estágio no chão assado (porte do `Scene.cover_layer` da Designer · game/ground.py · bíblia §11):
grama e musgo no Verde, umidade na Névoa."""

import numpy as np
import pygame
import pytest

from game import config as C
from game import ground as G
from game.geo import BASALT, PLATEAU, generate_geo

ARID, MIST, GREEN = C.ARID_STAGE, C.MIST_STAGE, C.GREEN_STAGE


@pytest.fixture(scope="module")
def geo():
    return generate_geo(7, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)


@pytest.fixture(scope="module")
def art():
    pygame.init()
    a = G.RegionArt()
    assert a.ok
    return a


def bake(geo, art, key, ctx=None):
    out = None
    for out in G.bake_block_codes(geo, art, *key, ctx or G.BakeContext(geo)):
        pass
    return out


def blocks_where(geo, mask, n, frac=0.5):
    """Os n primeiros blocos em que `mask` (por tile) cobre mais de `frac` do bloco."""
    found = []
    for by in range(C.SURFACE_H // G.BT):
        for bx in range(C.SURFACE_W // G.BT):
            sub = mask[by * G.BT:(by + 1) * G.BT, bx * G.BT:(bx + 1) * G.BT]
            if sub.mean() > frac:
                found.append((bx, by))
    return found[:n]


class Stub:
    step = 0

    def __init__(self, stage):
        self.stage = stage


def colorize(geo, art, key, out, stage):
    g = G.Ground()
    g.bind(geo)
    g._index[key] = out
    return pygame.surfarray.array3d(g._colorize(key, ("u", stage)))


def test_cover_is_deterministic_by_seed(geo, art):
    key = blocks_where(geo, geo.region == PLATEAU, 1)[0]
    a, b = bake(geo, art, key)[2], bake(geo, art, key)[2]
    assert np.array_equal(a, b)
    other = generate_geo(8, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)
    assert not np.array_equal(a, bake(other, art, key)[2])


def test_cover_does_not_depend_on_strip_size(geo, art, monkeypatch):
    key = blocks_where(geo, geo.region == PLATEAU, 1)[0]
    a = bake(geo, art, key)[2]
    monkeypatch.setattr(C, "GROUND_BAKE_ROWS", 64)
    assert np.array_equal(a, bake(geo, art, key)[2])


def test_green_plateau_is_a_reasonable_share_grass(geo, art):
    """No design as manchas cobrem 40–60% do planalto; aqui o planalto (fora do leito) dá ~58%."""
    ctx = G.BakeContext(geo)
    grass = total = 0
    for key in blocks_where(geo, geo.region == PLATEAU, 24, 0.6):
        code, _, cover = bake(geo, art, key, ctx)
        m = code // 16 == G.PLATEAU
        grass += ((cover & 15) > 0)[m].sum()
        total += m.sum()
    assert total > 2_000_000
    assert 0.40 <= grass / total <= 0.65, grass / total


def test_arid_has_no_grass_and_mist_has_no_grass(geo, art):
    key = blocks_where(geo, geo.region == PLATEAU, 1, 0.9)[0]
    out = bake(geo, art, key)
    assert ((out[2] & 15) > 0).any(), "o mapa tem grama (ela só aparece no Verde)"
    no_cover = (out[0], out[1], np.zeros_like(out[2]))
    assert np.array_equal(colorize(geo, art, key, out, ARID), colorize(geo, art, key, no_cover, ARID))
    assert np.array_equal(colorize(geo, art, key, out, C.STORM_STAGE), colorize(geo, art, key, no_cover, C.STORM_STAGE))
    green = {tuple(int(v) for v in G._hex(c)) for c in C.GROUND_GRASS + C.GROUND_MOSS}
    mist = colorize(geo, art, key, out, MIST).reshape(-1, 3)
    assert not green & {tuple(c) for c in np.unique(mist, axis=0)}


def test_green_grass_and_basalt_moss_use_their_palettes(geo, art):
    grass = {tuple(G._hex(c)) for c in C.GROUND_GRASS[1:]}
    moss = {tuple(G._hex(c)) for c in C.GROUND_MOSS[1:]}
    # planalto: só grama; basalto: musgo
    for region, want, other in ((PLATEAU, grass, moss), (BASALT, moss, grass)):
        key = blocks_where(geo, geo.region == region, 1, 0.9)[0]
        out = bake(geo, art, key)
        rgb = colorize(geo, art, key, out, GREEN)
        cov = (out[2] & 15) > 0
        colors = {tuple(int(v) for v in c) for c in np.unique(rgb.transpose(1, 0, 2)[cov], axis=0)}
        assert colors <= want, (region, colors - want)
        assert colors, region
        assert not colors & other


def test_more_grass_near_the_basin_than_far(geo, art):
    """Perto da bacia o limiar da grama cai: sobra mais grama na beira (mesma classe, fora d'água)."""
    ctx = G.BakeContext(geo)
    near_g = near_n = far_g = far_n = 0
    for key in blocks_where(geo, (geo.basin >= 0) & (geo.region == PLATEAU), 8, 0.05):
        bx, by = key
        code, _, cover = bake(geo, art, key, ctx)
        near = G.near_basin(geo, ctx.depth, bx * G.BP, by * G.BP, G.BP, G.BP)
        assert near is not None
        ok = code // 16 == G.PLATEAU                    # só planalto seco: nem leito nem outra região
        grass = (cover & 15) > 0
        near_g += grass[near & ok].sum()
        near_n += (near & ok).sum()
        far_g += grass[~near & ok].sum()
        far_n += (~near & ok).sum()
    assert near_n > 20_000 and far_n > 100_000
    assert near_g / near_n > far_g / far_n + 0.08, (near_g / near_n, far_g / far_n)


def test_no_grass_on_the_future_lake(geo, art):
    """A bacia inteira (a água do Verde) fica sem grama; só sobram tufinhos e borda na divisa (poucos %)."""
    ctx = G.BakeContext(geo)
    grass = total = 0
    for key in blocks_where(geo, (geo.basin >= 0) & (geo.region == PLATEAU), 3, 0.05):
        code, _, cover = bake(geo, art, key, ctx)
        bed = code // 16 == G.BED
        grass += ((cover & 15) > 0)[bed].sum()
        total += bed.sum()
    assert total > 10_000 and grass / total < 0.05, grass / total


def test_mist_damp_darkens_the_ground_by_the_designer_factors(geo, art):
    key = blocks_where(geo, geo.region == PLATEAU, 1, 0.9)[0]
    out = bake(geo, art, key)
    cover = out[2]
    share = ((cover & G.MIST_DAMP) > 0).mean()
    assert 0.15 < share < 0.55, share
    plain = colorize(geo, art, key, (out[0], out[1], np.zeros_like(cover)), MIST).transpose(1, 0, 2)
    damp = colorize(geo, art, key, out, MIST).transpose(1, 0, 2)
    d = (cover & G.MIST_DAMP) > 0
    top = (cover & G.MIST_EDGE) > 0
    assert top.any() and (top <= d).all()
    body = d & ~top
    want = (plain[body].astype(int) * np.array(C.GROUND_MIST_DAMP)).astype(np.uint8)
    assert np.array_equal(damp[body], want)
    assert np.array_equal(damp[~d], plain[~d])
    want_top = (plain[top].astype(int) * np.array(C.GROUND_MIST_DAMP)).astype(np.uint8)
    assert np.array_equal(damp[top], (want_top * C.GROUND_MIST_EDGE).astype(np.uint8))


def test_transition_block_brings_the_grass_per_pixel(geo, art):
    """Bloco metade Árido, metade Verde: a grama só aparece no lado que já virou (por pixel)."""
    key = blocks_where(geo, geo.region == PLATEAU, 1, 0.9)[0]
    out = bake(geo, art, key)
    g = G.Ground()
    g.bind(geo)
    g._index[key] = out
    half = {(x, y) for x in range(key[0] * G.BT - 1, key[0] * G.BT + 8) for y in range(key[1] * G.BT - 1,
                                                                                       (key[1] + 1) * G.BT + 1)}

    class Mixed(Stub):
        step = 5
        _sources = None

        def stage_at(self, x, y):
            return GREEN if (x, y) in half else ARID

    want = g.variant(key, Mixed(ARID))
    assert want[0] == "m" and (want[1], want[2]) == (ARID, GREEN)
    mix = pygame.surfarray.array3d(g._colorize(key, want)).transpose(1, 0, 2)
    green = {tuple(G._hex(c)) for c in C.GROUND_GRASS[1:]}
    has = np.array([[tuple(p) in green for p in row[::8]] for row in mix[::8]])
    left, right = has[:, :24], has[:, 40:]
    assert left.mean() > 0.2 and right.sum() == 0
