"""Elementos novos das regiões, v9 (v0.4 Marco 3 · M3.0, bíblia §11 "Elementos v9"): decalques no 3º sorteio da
célula de 96 px, soltos novos por tile (com o musgo do Verde) e as formações pequenas no geo.formations."""

import math
import random

import numpy as np
import pygame
import pytest

from game import config as C
from game import ground as G
from game.geo import FORMATION_SPECS, REGION_NAMES, generate_geo
from game.surface_gen import generate_surface

SEEDS = (1, 7, 42)
SMALL = ("split_rock", "salt_pillar", "lava_tube", "ice_needles")
V9_DECALS = {"vein", "oxide", "saltpoly", "efflor", "fumarole", "ropy", "icepoly", "rime", "trail", "ripples"}


def geo(seed):
    return generate_geo(seed, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)


@pytest.fixture(scope="module")
def art():
    pygame.init()
    a = G.RegionArt()
    assert a.ok
    return a


# ---- formações pequenas ------------------------------------------------------------------------------------
def test_small_specs_come_from_the_json():
    for kind in SMALL:
        spec = FORMATION_SPECS[kind]
        assert spec.small, kind
    assert not FORMATION_SPECS["monolith"].small and not FORMATION_SPECS["ice_gate"].small
    assert len(FORMATION_SPECS["lava_tube"].footprint) == 3 and len(FORMATION_SPECS["split_rock"].footprint) == 1


def test_small_formations_deterministic_by_seed():
    a, b = geo(7), geo(7)
    key = lambda g: [(f.kind, f.tx, f.ty) for f in g.formations if f.small]   # noqa: E731
    assert key(a) == key(b) and key(a)


@pytest.mark.parametrize("seed", SEEDS)
def test_small_formations_rules(seed):
    g = geo(seed)
    big = [f for f in g.formations if not f.small]
    small = [f for f in g.formations if f.small]
    kinds = [f.kind for f in small]
    for kind, (lo, hi) in C.GEO_SMALL_FORMATIONS.items():
        assert lo <= kinds.count(kind) <= hi, (kind, kinds)
    bx, by = C.BASE_TILE
    halo = C.SMALL_FORMATION_HALO
    pocket = set()
    for p in g.pockets:
        pocket |= set(p.interior) | set(p.ring) | set(p.apron)
    for f in small:
        spec = FORMATION_SPECS[f.kind]
        w, h = f.size
        reg = g.region[f.ty - halo:f.ty + h + halo, f.tx - halo:f.tx + w + halo]
        assert (reg == spec.region).all(), f                # inteira na região, com a folga
        if f.kind not in C.SMALL_FORMATION_BASIN_OK:      # nada no leito seco (o pilar de sal pode, no salar)
            assert (g.basin[f.ty - halo:f.ty + h + halo, f.tx - halo:f.tx + w + halo] < 0).all(), f
        assert g.region[f.ty, f.tx] != 0 or g.basin[f.ty, f.tx] < 0
        cx, cy = f.center
        assert math.hypot(cx - bx, cy - by) >= C.SMALL_FORMATION_MIN_BASE_DIST
        for o in g.formations:
            if o is not f:
                assert math.hypot(cx - o.center[0], cy - o.center[1]) >= C.SMALL_FORMATION_SPACING, (f, o)
        assert not (set(f.box) & pocket)
    assert all(not f.small for f in big)


@pytest.mark.parametrize("seed", (1, 7))
def test_small_footprint_is_formation_with_no_outcrop_and_no_hill_cut(seed):
    w = generate_surface(seed)
    small = [f for f in w.geo.formations if f.small]
    for f in small:
        assert all(w.get(*t) == C.FORMATION for t in f.tiles)
        ring = {(x + dx, y + dy) for x, y in f.box for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - set(f.box)
        assert all(w.get(*t) not in C.WALL_TILES for t in ring), f      # morro nenhum encostando
        assert all(t in w.keep_clear for t in ring)                     # nada nasce em volta
    reach = w.reachable_from(C.BASE_TILE)
    for v in w.veins:
        assert all(t in reach for t in v.tiles)


def test_small_formations_have_no_map_marker():
    from game.map_view import map_entries
    from game.systems import GameState
    g = GameState(rng=random.Random(1))
    g.active.explored.reveal_rect(C.SURFACE_W // 2, C.SURFACE_H // 2, C.SURFACE_W, C.SURFACE_H)
    names = {e.title for e in map_entries(g, "surface") if e.category == "formation"}
    assert FORMATION_SPECS["monolith"].name in names
    assert not any(FORMATION_SPECS[k].name in names for k in SMALL)


def test_small_formation_sprites_recolor_by_stage():
    from game import hills as H
    from game.geo import Formation
    pygame.init()
    fs = H.FormationSprites()
    for kind in SMALL:
        spec = FORMATION_SPECS[kind]
        f = Formation(kind, 10, 10, list(spec.footprint), spec.anchor)
        a, m = fs.surface(f, 2), fs.surface(f, 3)
        assert H.load_indexed(H.formation_file(kind)) is not None
        assert pygame.image.tobytes(a, "RGBA") != pygame.image.tobytes(m, "RGBA"), kind


# ---- decalques v9 -------------------------------------------------------------------------------------------
def test_v9_decals_in_their_class_deterministic_and_not_at_base(art):
    g = geo(7)
    ctx = G.BakeContext(g)
    mix = art.v9["decal_mix"]
    seen = set()
    n = 0
    for by in range(C.SURFACE_H // G.BT):
        for bx in range(C.SURFACE_W // G.BT):
            a = G.decals_for_block(g, art, bx, by, ctx.tcls, ctx.skip)
            b = G.decals_for_block(g, art, bx, by, ctx.tcls, ctx.skip)
            assert [(x, y, c) for x, y, c, _ in a] == [(x, y, c) for x, y, c, _ in b]
            for x, y, c, idx, name in G.v9_decals_for_block(g, art, bx, by, ctx.tcls, ctx.skip):
                assert name in {m for m, _ in mix[G.CLASS_NAMES[c]]}, (name, c)
                cx, cy = (x + idx.shape[1] // 2) // C.TILE, (y + idx.shape[0] // 2) // C.TILE
                assert (cx, cy) not in ctx.skip
                seen.add(name)
                n += 1
    assert n > 100 and len(seen) >= 8, (n, seen)


def test_v9_decals_go_into_the_bake(art):
    """O 3º sorteio entra no código assado: o bloco com decalque v9 muda em relação ao assado sem ele."""
    g = geo(7)
    ctx = G.BakeContext(g)
    key = next((bx, by) for by in range(6) for bx in range(6)
               if G.v9_decals_for_block(g, art, bx, by, ctx.tcls, ctx.skip))
    with_v9 = None
    for with_v9 in G.bake_block_codes(g, art, *key, ctx):
        pass
    saved = art.v9
    art.v9 = {}
    try:
        without = None
        for without in G.bake_block_codes(g, art, *key, ctx):
            pass
    finally:
        art.v9 = saved
    assert not np.array_equal(with_v9[0], without[0])


# ---- soltos v9 ----------------------------------------------------------------------------------------------
def test_v9_decor_deterministic_by_region_and_never_on_v8_decor(art):
    g = geo(7)
    a = G.decor_items_v9(g, art.v9["decor_p"])
    b = G.decor_items_v9(g, art.v9["decor_p"])
    assert a == b and sum(len(r) for r in a.values()) > 300
    v8 = {(tx, ty) for ty, row in G.decor_items(g).items() for tx, _, _ in row}
    skip = G.decal_skip_tiles(g)
    tcls = G.tile_classes(g)
    names = {}
    for ty, row in a.items():
        for d in row:
            assert (d.tx, ty) not in v8 and (d.tx, ty) not in skip
            assert d.ty == ty and 0 <= d.v < 3
            assert abs(d.foot_x - (d.tx * C.TILE + 16)) <= 7 and 26 <= d.foot_y - ty * C.TILE <= 29
            cls = G.CLASS_NAMES[int(tcls[ty, d.tx])]
            assert d.name in {n for n, _ in art.v9["decor_p"][cls]}, (d.name, cls)
            names[d.name] = names.get(d.name, 0) + 1
    assert {"pebbles", "boulder", "bombs", "column_stub", "penitentes", "salt_mound"} <= set(names), names
    assert len({d.flip for row in a.values() for d in row}) == 2


def test_v9_decor_never_on_rock_machine_vein_wreck_or_wall():
    from game.systems import GameState
    g = GameState(rng=random.Random(1))
    w = g.world
    rock = next((x, y) for y in range(w.height) for x in range(w.width) if w.get(x, y) in C.SMALL_ROCKS)
    wall = next((x, y) for y in range(10, w.height) for x in range(10, w.width) if w.get(x, y) == C.ROCK)
    form = w.geo.formations[0].tiles[0]
    vein = w.veins[0].tiles[0]
    wreck = w.wrecks[0].tiles[0]
    for t in (rock, wall, form, vein, wreck):
        assert not G.decor_tile_free(w, *t, g.machine_at), t
    free = next((x, y) for y in range(w.height) for x in range(w.width)
                if w.is_floor(x, y) and not w.vein_at(x, y) and not w.wreck_at(x, y) and not g.machine_at((x, y)))
    assert G.decor_tile_free(w, *free, g.machine_at)


def test_moss_only_in_green(art):
    for stage in (C.STORM_STAGE, C.ARID_STAGE, C.MIST_STAGE):
        assert G.decor_layers("boulder", stage, art.v9["moss_on"]) == ["boulder"]
    assert G.decor_layers("boulder", C.GREEN_STAGE, art.v9["moss_on"]) == ["boulder", "boulder_moss"]
    assert G.decor_layers("column_stub", C.GREEN_STAGE, art.v9["moss_on"]) == ["column_stub", "column_stub_moss"]
    assert G.decor_layers("pebbles", C.GREEN_STAGE, art.v9["moss_on"]) == ["pebbles"]


def test_decor_surfaces_moss_and_flip(art):
    pygame.init()
    gr = G.Ground()
    stone = gr.decor_surface("boulder", 1, "green")
    moss = gr.decor_surface("boulder_moss", 1, "green")
    assert stone is not None and moss is not None and stone.get_size() == moss.get_size()
    assert pygame.image.tobytes(moss, "RGBA") == pygame.image.tobytes(gr.decor_surface("boulder_moss", 1, "arid"),
                                                                       "RGBA")   # rampa fixa MOSS
    flip = gr.decor_surface("boulder", 1, "green", flip=True)
    assert pygame.image.tobytes(flip, "RGBA") == pygame.image.tobytes(pygame.transform.flip(stone, True, False),
                                                                       "RGBA")
    for name in ("pebbles", "mud_curls", "penitentes", "rimed_rock", "salt_slabs", "bombs"):
        paused = f"decor_{name}" in C.SCENERY_PAUSED                # o dono pausou alguns: sem sprite
        assert (gr.decor_surface(name, 0, "arid") is None) == paused, name
    assert REGION_NAMES                                       # import usado
