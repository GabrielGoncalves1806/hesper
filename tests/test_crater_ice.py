"""Cratera de impacto com a tampa de gelo (v0.4 Marco 2 · trilha C · C4)."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from game import config as C
from game import hills as H
from game import layers
from game import save
from game.assets import Sprites
from game.objectives import OBJECTIVES, crater_open, visited_cave
from game.render import Renderer
from game.systems import GameState

T = C.TILE


def at_crater(g):
    g.player.x, g.player.y = layers.ramp_arrival(g.world)


def test_new_game_starts_with_the_crater_frozen_and_it_blocks_the_way_down():
    g = GameState(rng=random.Random(1))
    assert g.surface.crater_ice == 0 and g.crater_frozen and g.ramp_blocked()
    at_crater(g)
    assert g.interaction() == ("ramp", tuple(g.world.crater))     # o E ainda mira a cratera (pra dar a dica)
    assert not g.start_ramp() and g.layer == layers.SURFACE


def test_partial_melt_still_blocks_and_only_the_empty_crater_opens():
    g = GameState(rng=random.Random(1))
    at_crater(g)
    for level in range(C.CRATER_ICE_STAGES):
        g.surface.crater_ice = level
        assert not g.start_ramp()
    g.surface.crater_ice = C.CRATER_ICE_STAGES
    assert g.start_ramp()


def test_f4_melts_at_once_and_flags_the_debug_hud():
    g = GameState(rng=random.Random(1))
    g.debug_melt_crater()
    assert g.surface.crater_ice == C.CRATER_ICE_STAGES and not g.crater_frozen and g.debug_crater


def test_going_up_from_the_cave_is_never_blocked():
    g = GameState(rng=random.Random(1))
    g.enter_layer("cave")
    g.surface.crater_ice = 0
    assert not g.ramp_blocked()


def test_save_keeps_the_ice_state():
    g = GameState(rng=random.Random(1))
    g.surface.crater_ice = 2
    loaded = save.state_from_dict(save.state_to_dict(g))
    assert loaded.surface.crater_ice == 2
    data = save.state_to_dict(g)
    del data["layers"]["surface"]["crater_ice"]                 # save v7 de antes da C4: tampada
    assert save.state_from_dict(data).surface.crater_ice == 0


def test_objective_melt_comes_right_before_going_down():
    texts = [o.text for o in OBJECTIVES]
    i = texts.index("Derreta o gelo da cratera")
    assert texts[i + 1] == "Desça na caverna pela cratera [E]"
    g = GameState(rng=random.Random(1))
    assert not crater_open(g) and not visited_cave(g)          # no M2 não completa sozinho
    g.debug_melt_crater()
    assert crater_open(g)


def test_five_ice_stages_recolored_by_stage():
    pygame.init()
    cs = H.CraterSprites()
    shots = [cs.crater(k, 2) for k in range(C.CRATER_ICE_STAGES + 1)]
    assert all(s is not None and s.get_size() == (168, 150) for s in shots)
    raw = [pygame.image.tobytes(s, "RGBA") for s in shots]
    assert len(set(raw)) == len(raw)                            # cada etapa é um desenho
    assert pygame.image.tobytes(cs.crater(0, 3), "RGBA") != raw[0]
    assert cs.ejecta(2).get_size() == (256, 216)


def test_renderer_draws_the_impact_crater_anchored_on_the_3x3_center():
    pygame.init()
    pygame.display.set_mode((64, 64))
    g = GameState(rng=random.Random(1))
    r = Renderer(Sprites())
    surf, key, x, y = r.crater_impact(g)
    ctx, cty = g.world.crater
    ax, ay = H.crater_anchor(0)
    assert (x + ax, y + ay) == (ctx * T + 48, cty * T + 48) and key[1] == 0
    g.debug_melt_crater()
    assert r.crater_impact(g)[1][1] == C.CRATER_ICE_STAGES
    g.enter_layer("cave")
    assert r.crater_impact(g) is None                           # a caverna continua com a rampa de subida
