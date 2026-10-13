"""Chão assado da superfície (v0.4 Marco 2 · trilha B · game/ground.py)."""

import numpy as np
import pygame
import pytest

from game import config as C
from game import ground as G
from game.geo import BASALT, FROST, PLATEAU, SALAR, generate_geo
from game.transition import StageMap

BP = G.BP


@pytest.fixture(scope="module")
def geo():
    return generate_geo(7, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)


@pytest.fixture(scope="module")
def art():
    pygame.init()
    a = G.RegionArt()
    assert a.ok, "assets/sprites/regions/ não carregou"
    return a


def bake(geo, art, key, ctx=None):
    out = None
    for out in G.bake_block_codes(geo, art, *key, ctx or G.BakeContext(geo)):
        pass
    return out


def block_with(geo, a, b):
    """Um bloco que tem as duas regiões (pra testar a divisa)."""
    for by in range(C.SURFACE_H // G.BT):
        for bx in range(C.SURFACE_W // G.BT):
            sub = geo.region[by * G.BT:(by + 1) * G.BT, bx * G.BT:(bx + 1) * G.BT]
            if (sub == a).mean() > 0.3 and (sub == b).mean() > 0.3:
                return bx, by
    raise AssertionError("sem bloco com as duas regiões")


def test_indexed_png_keeps_the_index(art):
    for tex in art.textures:
        assert tex.shape == (BP, BP) and tex.dtype == np.uint8 and tex.max() <= 7
    assert {"crack", "gravel", "patch_dark", "wind", "ridges", "scoria", "icesheet"} <= set(art.decals)
    assert set(art.decor) == {"shards", "salt_crystals", "ice_chunks"}


def test_bake_is_deterministic_and_strip_size_does_not_matter(geo, art, monkeypatch):
    key = block_with(geo, PLATEAU, SALAR)
    code, wt = bake(geo, art, key)
    code2, wt2 = bake(geo, art, key)
    assert np.array_equal(code, code2) and np.array_equal(wt, wt2)
    monkeypatch.setattr(C, "GROUND_BAKE_ROWS", 64)
    code3, _ = bake(geo, art, key)
    assert np.array_equal(code, code3)


def test_region_border_follows_region_px(geo, art):
    """A classe de cada pixel é a do geo.region_px (borda orgânica), não a do tile."""
    bx, by = key = block_with(geo, PLATEAU, SALAR)
    code, _ = bake(geo, art, key)
    cls = code // 16
    ys, xs = np.mgrid[by * BP:(by + 1) * BP, bx * BP:(bx + 1) * BP]
    want = geo.region_px(xs, ys)
    sure = cls < G.BED                                   # o leito e a marca d.água são outra classe
    match = (cls[sure] == want[sure]).mean()
    assert match > 0.98, match
    tile = geo.region[ys // C.TILE, xs // C.TILE]
    assert (want != tile).any(), "a divisa devia sair da linha do tile"


def test_bed_and_water_marks_inside_basins(geo, art):
    ys, xs = np.nonzero((geo.basin >= 0) & (geo.region == PLATEAU))
    tx, ty = int(xs[0]), int(ys[0])
    key = (tx // G.BT, ty // G.BT)
    code, _ = bake(geo, art, key)
    cls = code // 16
    assert (cls == G.BED).any(), "planalto em bacia devia virar leito seco"
    assert ((code == G.PALE) | (code == G.PALE2)).any(), "devia ter marca d'água seca"
    deep = (geo.basin == 0) & (geo.region == PLATEAU)
    j, i = np.nonzero(deep[key[1] * G.BT:(key[1] + 1) * G.BT, key[0] * G.BT:(key[0] + 1) * G.BT])
    if len(i):
        assert cls[j[0] * 32 + 16, i[0] * 32 + 16] in (G.BED, G.FIXED)


def test_decals_deterministic_and_not_at_base(geo, art):
    ctx = G.BakeContext(geo)
    bx, by = C.BASE_TILE[0] // G.BT, C.BASE_TILE[1] // G.BT
    a = G.decals_for_block(geo, art, bx, by, ctx.tcls, ctx.skip)
    b = G.decals_for_block(geo, art, bx, by, ctx.tcls, ctx.skip)
    assert [(x, y, c) for x, y, c, _ in a] == [(x, y, c) for x, y, c, _ in b]
    for x, y, c, idx in a:
        cx, cy = (x + idx.shape[1] // 2) // C.TILE, (y + idx.shape[0] // 2) // C.TILE
        assert (cx, cy) not in ctx.skip
    total = sum(len(G.decals_for_block(geo, art, x, y, ctx.tcls, ctx.skip)) for x in range(4) for y in range(4))
    assert total > 20


def test_decor_only_in_basalt_salar_frost(geo):
    items = G.decor_items(geo)
    regions = {int(geo.region[ty, tx]) for ty, row in items.items() for tx, _, _ in row}
    assert regions <= {BASALT, SALAR, FROST} and len(regions) >= 2
    bx, by = C.BASE_TILE
    assert all(abs(tx - bx) + abs(ty - by) > C.GROUND_BASE_CLEAR for ty, row in items.items() for tx, _, _ in row)


class Stub:
    """StageMap parado num estágio, com a mancha só em alguns tiles."""
    def __init__(self, stage, newer=()):
        self.stage, self.step = stage, 1 if newer else 0
        self.newer = set(newer)

    def stage_at(self, x, y):
        return self.stage + 1 if (x, y) in self.newer else self.stage


def test_colorize_uniform_and_mixed(geo, art):
    pygame.init()
    g = G.Ground()
    g.bind(geo)
    key = (C.BASE_TILE[0] // G.BT, C.BASE_TILE[1] // G.BT)
    g._index[key] = bake(geo, art, key, g.ctx)
    arid = g._colorize(key, g.variant(key, Stub(2)))
    mist = g._colorize(key, g.variant(key, Stub(3)))
    assert arid.get_flags() & pygame.SRCALPHA == 0 and arid.get_bitsize() == 32
    a, m = pygame.surfarray.array3d(arid), pygame.surfarray.array3d(mist)
    assert (a != m).any()
    half = {(x, y) for x in range(key[0] * G.BT - 1, key[0] * G.BT + 8) for y in range(key[1] * G.BT - 1,
                                                                                       (key[1] + 1) * G.BT + 1)}
    want = g.variant(key, Stub(2, half))
    assert want[0] == "m"
    mix = pygame.surfarray.array3d(g._colorize(key, want))
    left, right = mix[:200], mix[300:]
    assert (left == m[:200]).mean() > 0.95 and (right == a[300:]).mean() > 0.95


def test_cache_one_job_per_frame_and_flat_fallback(geo, monkeypatch):
    pygame.init()
    g = G.Ground()
    sm = StageMap()
    view = (960, 540)
    cam = (C.BASE_TILE[0] * C.TILE - 480, C.BASE_TILE[1] * C.TILE - 270)
    canvas = pygame.Surface(view, 0, 32)
    g.draw(canvas, geo, cam, view, sm)                     # frio: assa a tela toda na hora
    visible = g._blocks(cam[0], cam[1], cam[0] + view[0], cam[1] + view[1])
    assert all(k in g._index for k in visible)
    # anda 1 bloco pro lado: os blocos novos na tela ficam chapados; no máximo 1 bloco assado por quadro
    cam2 = (cam[0] + BP, cam[1])
    done = len(g._index)
    for _ in range(3):
        g.draw(canvas, geo, cam2, view, sm)
        assert len(g._index) <= done + 1
        done = len(g._index)
    assert any(v[0][0] == "flat" for v in g._color.values())
    for _ in range(400):
        g.draw(canvas, geo, cam2, view, sm)
    assert all(g._color[k][0] == ("u", sm.stage) for k in g._blocks(cam2[0], cam2[1], cam2[0] + 960, cam2[1] + 540))
    assert len(g._index) <= C.GROUND_CACHE_BLOCKS


def test_lru_is_bounded(geo, monkeypatch):
    pygame.init()
    monkeypatch.setattr(C, "GROUND_CACHE_BLOCKS", 6)
    g = G.Ground()
    g.sync = True
    canvas = pygame.Surface((960, 540), 0, 32)
    for i in range(4):
        g.draw(canvas, geo, (i * BP, 0), (960, 540), StageMap())
    assert len(g._index) <= 6


def test_renderer_uses_old_floor_without_geo():
    from game.assets import Sprites
    from game.render import Renderer

    class Layer:
        geo = None

    class State:
        active = Layer()
    assert Renderer(Sprites(enabled=True)).surface_geo(State()) is None
