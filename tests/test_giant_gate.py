"""Portão grande da entrada do bolsão da criatura (v0.5 Marco 3 · M3.6.3 · game/ice_blocks.py, receita "G")."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import ice_blocks, thaw
from game.systems import GameState

T = C.TILE
SEEDS = (1, 7, 42, 598929664)


def game(seed: int) -> GameState:
    return GameState(seed, rng=random.Random(1))


def giant_index(g: GameState) -> int:
    return len(g.surface.geo.pockets)            # o portão grande é o último da lista


def heat_for(p: float) -> float:
    lo, hi = C.THAW_GIANT_HEAT[0], C.THAW_GIANT_HEAT[-1]
    return lo + (hi - lo) * p


def set_heat(g: GameState, heat: float) -> None:
    g.indices["heat"] = heat
    g._apply_thaw()


def real_rects(g: GameState) -> list:
    """Tudo o que bate na caixa do player em volta da entrada (tiles sólidos de verdade e os blocos), relativo ao pé."""
    geo = g.surface.geo
    bx, by = ice_blocks.gate_base_px(geo, giant_index(g))
    x0, x1, y0, y1 = ice_blocks.area_of(ice_blocks.corridor_of("G"))
    rects = [(tx * T, ty * T, T, T)
             for ty in range(int((by + y0) // T) - 1, int((by + y1) // T) + 2)
             for tx in range(int((bx + x0) // T) - 1, int((bx + x1) // T) + 2) if g.surface.world.is_solid(tx, ty)]
    rects += g.surface.gate_solids
    return [(x - bx, y - by, w, h) for x, y, w, h in rects]


def reach(g: GameState) -> set:
    return g.surface.world.reachable_from(C.BASE_TILE)


# ---- a receita ---------------------------------------------------------------------------------------------------
def test_giant_recipe_is_big_stable_and_not_drawn_by_the_seed():
    r = ice_blocks.RECIPES["G"]
    assert len(r["blocks"]) == 11 and "G" not in ice_blocks.RECIPE_KEYS
    assert all(b["b"] in ice_blocks.BLOCKS and 0 <= b["melt"][0] < b["melt"][1] <= 1 for b in r["blocks"])
    assert max(b["melt"][1] for b in r["blocks"]) == 1.0
    assert {b["b"].split("_")[0] for b in r["blocks"]} == {"shard", "slab", "boulder"}      # os 3 tipos
    assert ice_blocks.corridor_of("G") == C.GIANT_ENTRY_W * T
    assert {ice_blocks.recipe_for(s, i) for s in range(1, 40) for i in range(3)} <= set(ice_blocks.RECIPE_KEYS)
    cor = ice_blocks.corridor_of("G")
    p = ice_blocks.opens_at("G")
    assert 0.4 < p < 1 and abs(p - r["opens_at"]) <= 0.0101
    assert not ice_blocks.passable(ice_blocks.rel_rects("G", 0.0), corridor=cor)
    assert not ice_blocks.passable(ice_blocks.rel_rects("G", p - 1e-6), corridor=cor)
    assert ice_blocks.passable(ice_blocks.rel_rects("G", p), corridor=cor)
    assert not ice_blocks.rel_rects("G", 1.0)


# ---- fechado, ordem e abertura (no jogo) ------------------------------------------------------------------------
@pytest.mark.parametrize("seed", SEEDS)
def test_closed_blocks_the_entry_then_opens_after_all_the_others(seed):
    g = game(seed)
    geo, layer, gi = g.surface.geo, g.surface, giant_index(g)
    assert ice_blocks.gate_count(geo) == gi + 1 and layer.gate_recipes[gi] == "G"
    assert not ice_blocks.passable(real_rects(g), walls=False, corridor=ice_blocks.corridor_of("G"))
    assert not reach(g) & set(geo.giant.interior)                          # fechado: o interior é inalcançável
    assert not reach(g) & set(geo.giant.entry)
    set_heat(g, C.THAW_GATE_HEAT[-1][-1])                                  # todos os outros derretidos por completo
    assert all(m == 1.0 for m in layer.gate_melt[:gi]) and layer.gate_melt[gi] == 0.0 and layer.gate_ice[gi] == 0
    assert not reach(g) & set(geo.giant.interior)
    set_heat(g, heat_for(ice_blocks.opens_at("G") - 0.001))
    assert layer.gate_ice[gi] == thaw.GATE_MELTING and not reach(g) & set(geo.giant.interior)
    assert all(m == 1.0 for m in layer.gate_melt[:gi])                     # (e os outros já tinham aberto antes)
    set_heat(g, heat_for(ice_blocks.opens_at("G")))
    assert layer.gate_ice[gi] == thaw.GATE_OPEN and 0 < layer.gate_melt[gi] < 1
    assert ice_blocks.passable(real_rects(g), walls=False, corridor=ice_blocks.corridor_of("G"))
    assert set(geo.giant.interior) - {t for t in geo.giant.interior if g.surface.world.is_solid(*t)} \
        <= reach(g)
    set_heat(g, C.THAW_GIANT_HEAT[-1])
    assert not [b for b in layer.gate_blocks if b.gate == gi] and layer.gate_melt[gi] == 1.0


def test_the_player_walks_through_the_gap_of_the_giant_gate():
    g = game(598929664)
    gi = giant_index(g)
    set_heat(g, heat_for(ice_blocks.opens_at("G")))
    bx, by = ice_blocks.gate_base_px(g.surface.geo, gi)
    path = ice_blocks.path_through(real_rects(g), walls=False, corridor=ice_blocks.corridor_of("G"))
    assert path
    g.player.x, g.player.y = bx + path[0][0], by + path[0][1]
    dt = 1.0 / C.PLAYER_SPEED
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        g.player.move(x1 - x0, y1 - y0, dt, g.solids_near)
        assert abs(g.player.x - (bx + x1)) < 1e-6 and abs(g.player.y - (by + y1)) < 1e-6, (x1, y1)
        g.player.x, g.player.y = bx + x1, by + y1
    assert g.player.tile in set(g.surface.geo.giant.interior)              # dentro do bolsão


def test_events_use_the_giant_name_and_the_old_gates_stay_the_same():
    g = game(42)
    gi = giant_index(g)
    set_heat(g, C.THAW_GATE_HEAT[-1][-1])
    g.events.clear()
    set_heat(g, heat_for(0.1))
    assert g.events == [("giant_gate_thaw", thaw.GATE_MELTING)]
    g.events.clear()
    set_heat(g, heat_for(1.0))
    assert g.events == [("giant_gate_thaw", thaw.GATE_OPEN)]
    assert not [e for e in g.events if e[0] == "gate_thaw" and e[1] == gi]
    assert [thaw.gate_progress(0, i) for i in range(3)] == [0.0, 0.0, 0.0]
    assert C.THAW_GATE_HEAT == ((2800, 4300, 5800), (5800, 8000, 10200), (14000, 18000, 22000))
    assert C.THAW_GIANT_HEAT[0] >= C.THAW_GATE_HEAT[-1][-1]                # começa depois do fim de todos os outros


# ---- App: dica e marcador ---------------------------------------------------------------------------------------
def test_hint_and_map_marker_of_the_big_ice(monkeypatch, tmp_path):
    from game import map_view, settings
    settings.SETTINGS_PATH = tmp_path / "settings.json"
    from game.app import App
    from game.ui import fmt
    app = App(scale=1, skip_title=True)
    try:
        s = app.state
        gi = giant_index(s)
        ex, ey, ew, eh = s.surface.geo.giant.entry_rect
        monkeypatch.setattr(app, "mouse_world", lambda: ((ex + ew / 2) * T, (ey + eh - 0.5) * T))
        monkeypatch.setattr(app, "e_target", lambda: None)
        assert app.gate_under_mouse() == gi
        need = heat_for(ice_blocks.opens_at("G"))
        assert app.hint() == f"Grande gelo · a passagem abre com ~{fmt(need)} pK (agora 0)"
        set_heat(s, heat_for(1.0))
        assert app.gate_ice_hint(gi) == "Grande gelo · a passagem já abriu"
        s.surface.explored.reveal_circle(ex + ew / 2, ey + eh / 2, 6)        # o jogador viu a entrada
        set_heat(s, 0.0)                                                      # (o degelo só sobe: o p fica onde está)
        marks = [e for e in map_view.map_entries(s, "surface") if e.title == "Grande gelo"]
        assert len(marks) == 1 and marks[0].state.startswith("aberto")
    finally:
        pygame.quit()
