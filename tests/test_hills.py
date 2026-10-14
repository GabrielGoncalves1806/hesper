"""Morros orgânicos da superfície (v0.4 Marco 2 · trilha C · game/hills.py)."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from game import config as C
from game import hills as H
from game.assets import Sprites
from game.render import Renderer, build_draw_list
from game.systems import GameState
from game.world import World

T = C.TILE
B = C.HILL_BLOCK


def flat_world(walls=()):
    w = World(1, 64, 64)
    w.tiles = [[C.SAND] * 64 for _ in range(64)]
    for tx, ty in walls:
        w.tiles[ty][tx] = C.ROCK
    return w


def plateau(i0, i1, j0, j1):
    return np.zeros((j1 - j0, i1 - i0), np.uint8)


def blocks():
    return H.HillBlocks({})


def test_indexed_png_keeps_the_indices():
    top, face = H.load_indexed("hill_top.png"), H.load_indexed("hill_face.png")
    assert top.shape == (512, 512) and face.shape == (24, 512)
    assert top.max() <= 8 and face.max() <= 8          # índices da rampa, não cores


def test_every_stage_and_region_has_a_hill_ramp():
    for key in H.STAGE_KEYS:
        lut = H.hill_lut(key)
        assert lut is not None and lut.shape == (80, 3)


def geometry(world, bx, by, with_height=False):
    i0, i1, j0, j1 = H.window_bounds(bx, by)
    kinds = H.tile_window(world.tiles, world.width, world.height, i0, i1, j0, j1)
    return H.bake_block(kinds, plateau(i0, i1, j0, j1), bx, by, H.load_indexed("hill_top.png"),
                        H.load_indexed("hill_face.png"), H.edge_noise(),
                        height=world.height if with_height else None)


def px(blk, x, y):
    """(índice, linha dona) no pixel (x, y) do mundo."""
    return blk["idx"][y - blk["y0"], x - blk["x0"]], blk["row"][y - blk["y0"], x - blk["x0"]]


def test_the_wall_keeps_its_place_top_lifted_and_face_below():
    walls = [(x, y) for x in range(10, 14) for y in range(10, 13)]   # 4×3 de rocha, longe da borda do mapa
    blk = geometry(flat_world(walls), 1, 1)
    # topo no meio do morro, 24 px acima do tile (o mesmo topo elevado de hoje)
    idx, row = px(blk, 11 * T + 16, 11 * T + 16 - C.WALL_LIFT)
    assert idx != H.TRANSPARENT and row == 11
    # face embaixo da última linha (ela pende do topo da linha 12)
    idx, row = px(blk, 11 * T + 16, 12 * T + 20)
    assert idx != H.TRANSPARENT and row == 12
    # chão longe: vazio
    assert px(blk, 15 * T + 16, 15 * T + 16)[0] == H.TRANSPARENT
    assert px(blk, 8 * T + 16, 8 * T + 16)[0] == H.TRANSPARENT


def test_the_corner_rounds_off():
    """Grade dual: o canto convexo arredonda (o pixel da quina do tile não é morro)."""
    blk = geometry(flat_world([(x, y) for x in range(10, 14) for y in range(10, 13)]), 1, 1)
    corner = px(blk, 10 * T + 1, 10 * T + 1 - C.WALL_LIFT)[0]     # quina de cima-esquerda do topo
    middle = px(blk, 10 * T + 16, 10 * T + 16 - C.WALL_LIFT)[0]
    assert corner == H.TRANSPARENT and middle != H.TRANSPARENT


def test_each_row_owns_only_its_pixels():
    blk = geometry(flat_world([(x, y) for x in range(10, 14) for y in range(10, 15)]), 1, 1)
    rows = blk["row"]
    assert set(np.unique(rows)) == {-1} | set(range(10, 15))      # só linhas com parede, todas deste bloco
    for r in range(10, 15):                                        # cada linha perto do lugar dela (± o ruído)
        ys = np.nonzero((rows == r).any(axis=1))[0] + blk["y0"]
        assert ys.min() >= r * T - C.WALL_LIFT - H.MARGIN and ys.max() < (r + 1) * T + H.MARGIN


def test_bottom_edge_has_no_hole_below_the_last_row():
    """O topo é erguido 24 px: os 24 px de baixo do mapa são da "linha de fora" e não podem sair transparentes
    (virava buraco na rocha, com o chão aparecendo por baixo)."""
    w = flat_world([(x, y) for x in range(0, 64) for y in (62, 63)])      # cordilheira na borda de baixo
    bottom = 64 * T                                                        # 1º px de fora do mapa
    for bx in range(64 // B):
        blk = geometry(w, bx, 64 // B - 1, with_height=True)
        x_lo, x_hi = max(0, blk["x0"]), min(64 * T, blk["x0"] + blk["idx"].shape[1])
        for y in range(bottom - C.WALL_LIFT - 2, bottom):
            line = blk["idx"][y - blk["y0"], x_lo - blk["x0"]:x_hi - blk["x0"]]
            assert (line != H.TRANSPARENT).all(), (bx, y)
            assert (blk["row"][y - blk["y0"], x_lo - blk["x0"]:x_hi - blk["x0"]] == 63).all()
    # sem `height` o buraco existe (a linha 64 não é de nenhum bloco): o teste pega a regressão
    blk = geometry(w, 1, 64 // B - 1)
    assert (blk["idx"][bottom - 1 - blk["y0"]] == H.TRANSPARENT).any()


def test_other_edges_have_no_hole():
    """Topo, esquerda e direita: a cordilheira cobre até o limite do mapa, sem frestas dentro dele."""
    w = flat_world([(x, y) for x in range(64) for y in range(64) if x < 2 or x >= 62 or y < 2 or y >= 62])
    for bx, by in ((0, 0), (7, 0), (0, 7), (7, 7), (3, 0), (0, 3), (7, 3)):
        blk = geometry(w, bx, by, with_height=True)
        ys = np.arange(blk["y0"], blk["y0"] + blk["idx"].shape[0])[:, None]
        xs = np.arange(blk["x0"], blk["x0"] + blk["idx"].shape[1])[None, :]
        dentro = (xs >= 0) & (xs < 64 * T) & (ys >= 0) & (ys < 64 * T)
        # px dentro do mapa e dentro das linhas do bloco (±o que o ruído empurra): tudo coberto na última fileira de tiles da borda
        faixa = dentro & ((xs < T) | (xs >= 63 * T) | (ys < T) | (ys >= 63 * T))
        faixa &= (xs >= bx * B * T) & (xs < (bx + 1) * B * T) & (ys >= by * B * T) & (ys < (by + 1) * B * T - C.WALL_LIFT)   # os 24 de baixo são do bloco de baixo
        assert (blk["idx"][faixa] != H.TRANSPARENT).all(), (bx, by)


def test_lone_tile_becomes_a_boulder_not_a_square():
    blk = geometry(flat_world([(11, 11)]), 1, 1)
    solid = (blk["idx"] != H.TRANSPARENT).sum()
    assert 0 < solid < T * (T + C.WALL_LIFT)                       # menor que o tile + a face de hoje


def test_mining_rebakes_only_the_touched_block():
    pygame.init()
    walls = [(x, y) for x in range(2, 30) for y in range(2, 30)]
    w = flat_world(walls)
    hb = blocks()
    for by in range(4):
        for bx in range(4):
            hb.strips(w, plateau, (("all", 2), 2), bx, by)
    before = hb.bakes
    w.set(12, 12, C.SAND)                                          # no meio do bloco (1, 1)
    for by in range(4):
        for bx in range(4):
            hb.strips(w, plateau, (("all", 2), 2), bx, by)
    assert hb.bakes - before == 1
    w.set(16, 12, C.SAND)                                          # na beira: o vizinho da esquerda também enxerga
    before = hb.bakes
    for by in range(4):
        for bx in range(4):
            hb.strips(w, plateau, (("all", 2), 2), bx, by)
    assert hb.bakes - before == 2
    # tile que não é parede (rocha pequena nascendo) não re-assa nada
    before = hb.bakes
    w.set(40, 40, C.SMALL_IRON)
    for by in range(6):
        for bx in range(6):
            hb.strips(w, plateau, (("all", 2), 2), bx, by)
    assert hb.bakes - before == 6 * 6 - 16                         # só os 20 blocos novos (os 16 de antes ficam)


def test_stage_change_only_recolors():
    pygame.init()
    w = flat_world([(3, 3), (4, 3)])
    hb = blocks()
    hb.strips(w, plateau, (("all", 2), 2), 0, 0)
    bakes, recolors = hb.bakes, hb.recolors
    hb.strips(w, plateau, (("all", 3), 3), 0, 0)
    assert hb.bakes == bakes and hb.recolors == recolors + 1


def test_draw_list_uses_one_hill_strip_per_row():
    w = flat_world([(3, 3)])
    order = build_draw_list(w, [(3 * T - 10, "player")], 0, 10, 0, 10, hill_rows={3})
    assert ("wall", 3, 3) not in order
    # o player com o pé na linha 2 (logo acima do morro) vem antes do topo da linha 3: fica atrás
    assert order.index(("obj", "player")) < order.index(("hills", 3))
    order = build_draw_list(w, [(4 * T - 2, "player")], 0, 10, 0, 10, hill_rows={3})
    assert order.index(("hills", 3)) < order.index(("obj", "player"))   # logo abaixo: na frente da face


def test_cave_keeps_the_old_walls_and_surface_goes_organic():
    pygame.init()
    pygame.display.set_mode((64, 64))
    g = GameState(rng=random.Random(1))
    r = Renderer(Sprites())
    assert r.organic_hills(g)
    g.enter_layer("cave")
    assert not r.organic_hills(g)


def test_surface_frame_draws_hill_strips():
    pygame.init()
    pygame.display.set_mode((64, 64))
    g = GameState(rng=random.Random(1))
    w = g.world
    wall = next((x, y) for y in range(20, w.height - 20) for x in range(20, w.width - 20)
                if w.get(x, y) == C.ROCK and w.is_floor(x, y + 1))
    g.player.x, g.player.y = (wall[0] + 0.5) * T, (wall[1] + 3) * T
    r = Renderer(Sprites())
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    cam = r.camera(g)
    r.draw(canvas, g, cam, 0.0)
    strips = r.hill_strips(g, cam)
    assert any(wall[1] in rows for rows in strips.values())


# ---- formações (C3) -------------------------------------------------------------------------------------
from game import geo as G  # noqa: E402


def surface_game():
    pygame.init()
    pygame.display.set_mode((64, 64))
    return GameState(rng=random.Random(1))


def test_every_formation_has_an_indexed_sprite_recolored_by_stage():
    pygame.init()
    fs = H.FormationSprites()
    for kind in ("monolith", "arch", "basalt_spires", "salt_ridge", "cone", "ice_gate"):
        assert H.load_indexed(H.formation_file(kind)) is not None, kind
        f = G.Formation(kind, 10, 10, list(G.FORMATION_SPECS[kind].footprint), G.FORMATION_SPECS[kind].anchor)
        arid, mist = fs.surface(f, 2), fs.surface(f, 3)
        assert arid.get_size() == mist.get_size()
        assert pygame.image.tobytes(arid, "RGBA") != pygame.image.tobytes(mist, "RGBA"), kind


def test_anchor_lands_on_base_px():
    pygame.init()
    fs = H.FormationSprites()
    spec = G.FORMATION_SPECS["arch"]
    f = G.Formation("arch", 20, 30, list(spec.footprint), spec.anchor)
    surf, x, y = fs.placement(f, 2)
    assert (x + spec.anchor[0], y + spec.anchor[1]) == (round(f.base_px[0]), round(f.base_px[1]))


def test_formations_are_drawn_as_objects_by_their_foot():
    g = surface_game()
    r = Renderer(Sprites())
    f = g.active.geo.formations[0]
    bx, by = f.base_px
    g.player.x, g.player.y = bx, by - 3 * T           # acima do pé: atrás
    cam = r.camera(g)
    vis = r.visible_formations(g, cam)
    assert any(v[0] is f for v in vis)
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    items = r.collect_objects(canvas, g, cam, 0.0)
    ys = sorted(ay for ay, _ in items)
    assert by in ys and g.player.y in ys and g.player.y < by   # o player vem antes (fica atrás)


def test_arch_gap_is_walkable_and_legs_block():
    g = surface_game()
    arch = next(f for f in g.active.geo.formations if f.kind == "arch")
    w = g.world
    legs = set(arch.tiles)
    gap = [t for t in arch.box if t not in legs]
    assert len(gap) == 3 and all(not w.is_solid(*t) for t in gap)
    assert all(w.get(*t) == C.FORMATION for t in legs)


def test_player_behind_a_formation_gets_the_xray():
    g = surface_game()
    r = Renderer(Sprites())
    f = next(f for f in g.active.geo.formations if f.kind == "monolith")
    bx, by = f.base_px
    g.player.x, g.player.y = bx, by - T - 4            # logo atrás do pé, coberto pelo pilar
    assert r.player_occluded(g)
    g.player.x, g.player.y = bx, by + T                # na frente: nada cobre
    assert not r.formation_occludes(g)
