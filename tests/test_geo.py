"""Geografia da superfície (v0.4 Marco 2 · game/geo.py): relevo, regiões, bacias, borda orgânica e formações."""

from collections import deque

import numpy as np
import pytest

from game import config as C
from game.geo import BASALT, FROST, PLATEAU, SALAR, FORMATION_SPECS, Geo, generate_geo

T = C.TILE
SEEDS = (1, 7, 42)


def geo(seed: int) -> Geo:
    return generate_geo(seed, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)


def test_deterministic_by_seed():
    a, b, c = geo(7), geo(7), geo(8)
    assert np.array_equal(a.region, b.region) and np.array_equal(a.height, b.height)
    assert np.array_equal(a.basin, b.basin)
    assert [(f.kind, f.tx, f.ty) for f in a.formations] == [(f.kind, f.tx, f.ty) for f in b.formations]
    assert a.region_px(1234.5, 2222.0) == b.region_px(1234.5, 2222.0)
    assert not np.array_equal(a.region, c.region) and not np.array_equal(a.height, c.height)
    assert a.region.dtype == np.uint8 and a.height.dtype == np.float32 and a.basin.dtype == np.int8
    assert a.region.shape == a.height.shape == a.basin.shape == (C.SURFACE_H, C.SURFACE_W)


@pytest.mark.parametrize("seed", SEEDS)
def test_base_in_plateau_and_all_regions_present(seed):
    g = geo(seed)
    bx, by = C.BASE_TILE
    assert g.region[by, bx] == PLATEAU
    assert (g.region[by - 12:by + 13, bx - 12:bx + 13] == PLATEAU).all()
    assert (g.basin[by - 12:by + 13, bx - 12:bx + 13] < 0).all()
    share = np.bincount(g.region.ravel(), minlength=4) / g.region.size
    assert all(share > 0.04), share
    assert share[PLATEAU] == share.max()
    ys, xs = np.nonzero(g.region == SALAR)                 # salar a leste, basalto a oeste, gelo no norte
    assert xs.mean() > bx + 30
    ys, xs = np.nonzero(g.region == BASALT)
    assert xs.mean() < bx - 30
    ys, xs = np.nonzero(g.region == FROST)
    assert ys.max() < 40 and ys.mean() < 20


def _components(mask: np.ndarray) -> list[set]:
    h, w = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        part, q = set(), deque([(x0, y0)])
        seen[y0, x0] = True
        while q:
            x, y = q.popleft()
            part.add((x, y))
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((nx, ny))
        out.append(part)
    return sorted(out, key=len, reverse=True)


@pytest.mark.parametrize("seed", SEEDS)
def test_salar_is_the_biggest_basin_and_levels_nest(seed):
    g = geo(seed)
    parts = _components(g.basin >= 0)
    assert len(parts) >= 3                                 # o salar + as depressões pequenas do planalto
    biggest = parts[0]
    in_salar = sum(g.region[y, x] == SALAR for x, y in biggest)
    assert in_salar > 0.9 * len(biggest)
    assert len(biggest) > 3 * len(parts[1])
    L1, L2, L3 = C.GEO_LEVELS
    assert (g.height[g.basin == 0] < L1).all()
    assert ((g.height[g.basin == 1] >= L1) & (g.height[g.basin == 1] < L2)).all()
    assert ((g.height[g.basin == 2] >= L2) & (g.height[g.basin == 2] < L3)).all()
    assert (g.height[g.basin < 0] >= L3).all()
    assert (g.basin == 0).any() and (g.basin == 1).any()   # o fundo do salar enche já no L1


@pytest.mark.parametrize("seed", SEEDS)
def test_warp_bends_the_border_but_never_more_than_14px(seed):
    """region_px muda a região perto da divisa (borda orgânica), mas o ponto lido nunca passa de 14 px do pixel:
    a região que aparece num pixel sempre é de um tile a até 14 px dele."""
    g = geo(seed)
    ys, xs = np.mgrid[0:C.SURFACE_H * T:5, 0:C.SURFACE_W * T:5]
    px, py = xs.astype(float) + 0.5, ys.astype(float) + 0.5
    got = g.region_px(px, py)
    plain = g.region[(py // T).astype(int), (px // T).astype(int)]
    diff = got != plain
    assert 0.002 < diff.mean() < 0.06
    wp = C.GEO_WARP
    h, w = g.region.shape
    for x, y, r in zip(px[diff], py[diff], got[diff]):
        x0, x1 = int((x - wp) // T), int((x + wp) // T)
        y0, y1 = int((y - wp) // T), int((y + wp) // T)
        box = g.region[max(0, y0):min(h, y1 + 1), max(0, x0):min(w, x1 + 1)]
        assert (box == r).any(), (x, y, r)
    dx, dy = g.warp(px, py)
    assert np.abs(dx).max() <= wp and np.abs(dy).max() <= wp
    assert isinstance(g.region_px(100.0, 100.0), int)


@pytest.mark.parametrize("seed", SEEDS)
def test_formations_and_ice_gates(seed):
    g = geo(seed)
    kinds = [f.kind for f in g.formations]
    for kind, (lo, hi) in C.GEO_FORMATIONS.items():
        assert lo <= kinds.count(kind) <= hi, (kind, kinds)
    assert C.ICE_GATES[0] <= kinds.count("ice_gate") <= C.ICE_GATES[1]
    assert kinds.count("ice_gate") == len(g.pockets)
    for f in g.formations:
        spec = FORMATION_SPECS[f.kind]
        assert f.footprint == list(spec.footprint) and f.anchor == spec.anchor
        assert (min(x for x, _ in f.footprint), min(y for _, y in f.footprint)) == (0, 0)
        assert all(g.region[y, x] == spec.region for x, y in f.tiles)
        bx, by = f.base_px
        assert by == (f.ty + f.size[1]) * T and bx == (f.tx + f.size[0] / 2) * T
    arch = FORMATION_SPECS["arch"]
    assert arch.footprint == ((0, 0), (4, 0))               # só as pernas: o vão de 3 é andável
