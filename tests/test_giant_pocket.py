"""Bolsão grande da criatura e gelo gigante (v0.5 Marco 3 · M3.6.2 · game/geo.py · _giant_pocket, game/ice_giant.py)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import hills, ice_giant
from game.geo import FROST, generate_geo
from game.surface_gen import generate_surface

GEO_SEEDS = range(30)                    # o Dev validou 200 seeds na hora; aqui 30 bastam (custo do pytest)
WORLD_SEEDS = (1, 7, 42, 598929664)


def geo(seed: int):
    return generate_geo(seed, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)


def box_around(giant, r: int) -> set:
    """A caixa da pegada do gelo gigante mais `r` tiles em volta (o corredor de andar em volta dele)."""
    return {(x + dx, y + dy) for x, y in giant.box for dx in range(-r, r + 1) for dy in range(-r, r + 1)}


@pytest.mark.parametrize("seed", GEO_SEEDS)
def test_giant_pocket_exists_in_frost_and_clear_of_the_rest(seed):
    g = geo(seed)
    gp = g.giant
    assert gp is not None and gp.giant in g.formations and gp.giant.kind == "ice_giant"
    area = set(gp.interior) | set(gp.ring) | set(gp.apron) | set(gp.entry)
    assert all(g.region_at(*t) == FROST for t in area)                     # tudo dentro da faixa gelada
    assert all(g.basin_at(*t) < 0 for t in area)                           # nenhuma água
    assert len(gp.interior) == C.GIANT_POCKET_SIZE[0] * C.GIANT_POCKET_SIZE[1]
    assert gp.entry_rect[2] == C.GIANT_ENTRY_W and len(gp.entry) == C.GIANT_ENTRY_W * C.POCKET_WALL
    assert not (set(gp.entry) & set(gp.ring))
    for p in g.pockets:                                                    # longe dos bolsões de hoje (e do portão deles)
        theirs = set(p.interior) | set(p.ring) | set(p.apron) | set(p.gate.tiles)
        assert not any(abs(x - tx) < C.GIANT_GAP and abs(y - ty) < C.GIANT_GAP for x, y in area for tx, ty in theirs)
    for f in g.formations:
        if f is gp.giant:
            continue
        assert not (set(f.box) & area), f.kind                             # nem encosta nas formações
    assert gp.giant.size == (7, 3)
    assert len(g.pockets) in range(C.ICE_GATES[0], C.ICE_GATES[1] + 1)     # os bolsões de hoje continuam 2 ou 3


@pytest.mark.parametrize("seed", GEO_SEEDS)
def test_giant_has_corridor_all_around(seed):
    gp = geo(seed).giant
    near = box_around(gp.giant, 3) - set(gp.giant.box)
    assert near <= set(gp.interior)                                        # 3 tiles livres em cada lado, dentro do bolsão


def test_giant_pocket_entry_faces_away_from_the_mountains():
    for seed in range(40):
        gp = geo(seed).giant
        ex, ey, ew, eh = gp.entry_rect
        assert gp.side == "s" and ey > max(y for _, y in gp.interior)      # entrada no muro de baixo (cordilheira é ao norte)
        assert min(x for x, _ in gp.interior) <= ex and ex + ew - 1 <= max(x for x, _ in gp.interior)


def test_giant_position_varies_by_seed():
    spots = {(geo(s).giant.giant.tx // 40, geo(s).giant.giant.ty // 8) for s in range(30)}
    xs = [geo(s).giant.outer[0] for s in range(30)]
    assert len(spots) > 8 and min(xs) < 60 and max(xs) > C.SURFACE_W - 100   # de um canto ao outro da faixa


def test_variant_is_stable_by_seed_and_both_appear():
    kinds = {s: geo(s).giant.creature.variant for s in range(40)}
    assert set(kinds.values()) == set(C.GIANT_VARIANTS)
    assert all(geo(s).giant.creature.variant == k for s, k in kinds.items())
    gp = geo(5).giant
    assert gp.giant.variant == C.GIANT_VARIANTS.index(gp.creature.variant) and gp.creature.trapped


@pytest.mark.parametrize("seed", WORLD_SEEDS)
def test_world_ring_entry_reachable_and_giant_solid(seed):
    w = generate_surface(seed)
    gp = w.geo.giant
    assert all(w.get(*t) == C.BEDROCK and not w.is_minable(*t) for t in gp.ring)   # anel não minera
    assert all(w.get(*t) == C.SAND for t in gp.entry)                              # entrada aberta
    assert all(w.get(*t) == C.FORMATION and w.is_solid(*t) and not w.is_minable(*t) for t in gp.giant.tiles)
    reach = w.reachable_from(C.BASE_TILE)
    assert set(gp.entry) <= reach and set(gp.apron) <= reach                        # dá pra chegar na entrada
    corridor = box_around(gp.giant, 3) - set(gp.giant.box)
    assert corridor <= reach                                                        # e andar em volta dele por todos os lados
    area = set(gp.interior) | set(gp.ring) | set(gp.apron) | set(gp.entry)
    assert not any(t in area for v in w.veins for t in v.tiles)                     # veio fora do bolsão
    assert all(w.get(*t) in (C.SAND,) or t in set(gp.giant.tiles) for t in gp.interior)   # nada nasce lá dentro


def test_breath_waits_9_to_14_seconds_then_plays_the_strip():
    b = ice_giant.Breath(42)
    frames = [b.frame(i / 20) for i in range(20 * 120)]                    # 2 minutos a 20 quadros/s
    assert frames[0] == 0 and set(frames) == set(range(ice_giant.FRAMES))
    runs, i = [], 0
    while i < len(frames):                                                 # tamanho de cada trecho parado no 0
        if frames[i] == 0:
            j = i
            while j < len(frames) and frames[j] == 0:
                j += 1
            runs.append((j - i) / 20)
            i = j
        else:
            i += 1
    lo, hi = C.GIANT_BREATH_PAUSE
    assert all(lo - 0.2 <= r <= hi + 0.2 for r in runs[1:-1])              # (o quadro 0 da tira conta como parado)
    assert ice_giant.Breath(42).frame(33.3) == ice_giant.Breath(42).frame(33.3)    # mesma seed, mesmo instante


def test_sprites_and_shards_load():
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    gp = generate_surface(1).geo.giant
    for variant in (0, 1):
        f = gp.giant
        for frame in (0, 3):
            for stage in (1, 2, 3, 4):
                surf = hills.FormationSprites().surface(f, stage, variant, frame)
                assert surf.get_size() == (256, 220)
        assert hills.formation_file("ice_giant", variant) == f"form_ice_giant_{C.GIANT_VARIANTS[variant]}.png"
    assert hills.formation_ramp("ice_giant") == ("ICE+ICE_DEEP", "frost")
    assert hills.ramp("ICE+ICE_DEEP", "frost", "arid").shape == (13, 3)
    assert len(ice_giant.shards(gp.giant)) == 12 and all(b.rect is None for b in ice_giant.shards(gp.giant))
    assert hills.FrostRing("frost_field.png").surface(2).get_size() == (420, 200)
