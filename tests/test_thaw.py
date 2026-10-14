"""v0.4 Marco 3 · M3.1: a cratera derrete com o calor e as fumarolas do basalto acordam (game/thaw.py)."""

import math
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import save, thaw
from game.geo import BASALT, generate_geo
from game.objectives import OBJECTIVES, crater_open
from game.surface_gen import generate_surface
from game.systems import GameState

SEEDS = (1, 7, 42)


@pytest.fixture
def new_state():
    return GameState(rng=random.Random(1))


# ---------------------------------------------------------------- cratera
def test_crater_stage_steps_with_heat():
    marks = C.THAW_CRATER_HEAT
    assert len(marks) == C.CRATER_ICE_STAGES and list(marks) == sorted(marks)
    assert thaw.crater_stage(0) == 0
    assert thaw.crater_stage(marks[0] - 0.01) == 0
    assert thaw.crater_stage(marks[0]) == 1
    assert thaw.crater_stage(marks[1]) == 2
    assert thaw.crater_stage(marks[-1]) == C.CRATER_ICE_STAGES
    assert thaw.crater_stage(marks[-1] * 10) == C.CRATER_ICE_STAGES


def test_state_melts_crater_and_emits_events(new_state):
    new_state.indices["heat"] = C.THAW_CRATER_HEAT[1]
    new_state._apply_thaw()
    assert new_state.surface.crater_ice == 2
    assert ("crater_thaw", 1) in new_state.events and ("crater_thaw", 2) in new_state.events
    new_state.events.clear()
    new_state._apply_thaw()                                  # nada subiu: nada de evento repetido
    assert not [e for e in new_state.events if e[0] == "crater_thaw"]


def test_thaw_never_goes_back_and_respects_f4(new_state):
    new_state.debug_melt_crater()
    new_state._apply_thaw()           # calor 0 não fecha de novo
    assert new_state.surface.crater_ice == C.CRATER_ICE_STAGES
    new_state.surface.crater_ice = 3                         # um save antigo com etapa maior que o calor
    new_state.indices["heat"] = C.THAW_CRATER_HEAT[0]
    new_state._apply_thaw()
    assert new_state.surface.crater_ice == 3


def test_heater_heat_opens_the_crater_through_the_update(new_state):
    """O calor sobe no _update_machines (aquecedor de verdade) e a tampa baixa sozinha até abrir."""
    from game.systems import Controls, Machine
    new_state.surface.machines.append(Machine("heater", 90, 98))
    assert new_state.ramp_blocked()
    for _ in range(int(C.THAW_CRATER_HEAT[-1] / C.MACHINES["heater"].rate / 0.05) + 40):
        new_state.update(0.05, Controls())
    assert new_state.indices["heat"] >= C.THAW_CRATER_HEAT[-1]
    assert new_state.surface.crater_ice == C.CRATER_ICE_STAGES
    assert not new_state.ramp_blocked() and crater_open(new_state)
    stages = [e[1] for e in new_state.pop_events() if e[0] == "crater_thaw"]
    assert stages == [1, 2, 3, 4]


def test_load_rebuilds_from_heat_without_events(new_state):
    new_state.indices["heat"] = C.THAW_CRATER_HEAT[2]
    data = save.state_to_dict(new_state)                    # crater_ice ainda 0 no save (calor não aplicado)
    loaded = save.state_from_dict(data)
    assert loaded.surface.crater_ice == 3
    assert not loaded.events


def test_debug_ti_heat_thaws_too(new_state):
    new_state.debug_add_ti()                                 # F2: +3333 de calor
    new_state.update(0.016, __import__("game.systems", fromlist=["Controls"]).Controls())
    assert new_state.surface.crater_ice == C.CRATER_ICE_STAGES


# ---------------------------------------------------------------- objetivos (ordem decidida pelo dono)
def test_heater_trio_comes_right_after_the_chest_and_before_the_crater():
    texts = [o.text for o in OBJECTIVES]
    i = texts.index("Construa um baú")
    assert texts[i + 1:i + 7] == ["Minere gelo e construa um Derretedor", "Chegue a Ti 500",
                                  "Encontre magmatita no basalto (oeste)", "Construa um Aquecedor",
                                  "Derreta o gelo da cratera", "Desça na caverna pela cratera [E]"]
    j = texts.index("Fabrique e equipe o tanque de O₂")
    assert texts.index("Desça na caverna pela cratera [E]") < texts.index("Ache um destroço") < j
    assert texts[j + 1] == "Construa um painel solar"


# ---------------------------------------------------------------- fumarolas
def test_fumarole_active_is_monotone_and_inside_the_crater_window():
    lo, hi = C.THAW_FUMAROLE_HEAT
    for i in range(12):
        assert not thaw.fumarole_active(0, i)
        assert not thaw.fumarole_active(lo - 0.01, i)
        assert thaw.fumarole_active(hi, i)
        assert lo <= thaw.fumarole_threshold(i) <= hi
        was = False
        for h in range(0, int(hi) + 2):
            now = thaw.fumarole_active(h, i)
            assert now or not was                          # nunca volta a dormir com mais calor
            was = now
    # espalhadas: não acordam todas no mesmo calor
    assert len({round(thaw.fumarole_threshold(i)) for i in range(6)}) >= 5


@pytest.mark.parametrize("seed", SEEDS)
def test_vents_spawn_in_the_basalt_following_the_rule(seed):
    w = generate_surface(seed)
    geo = w.geo
    vents = geo.vents
    counts = {k: sum(1 for f in vents if f.kind == f"vent_{k}") for k in ("cone", "pair", "chimney")}
    assert 2 <= counts["cone"] <= 3 and 1 <= counts["pair"] <= 2 and 1 <= counts["chimney"] <= 2, counts
    assert all(f in geo.formations for f in vents)
    others = [f for f in geo.formations if not f.kind.startswith("vent_")]
    bx, by = C.BASE_TILE
    halo = C.THAW_FUMAROLE_HALO
    for f in vents:
        x0, y0 = f.tx - halo, f.ty - halo
        fw, fh = f.size
        for y in range(y0, f.ty + fh + halo):
            for x in range(x0, f.tx + fw + halo):
                assert geo.region_at(x, y) == BASALT and geo.basin_at(x, y) < 0, (f.kind, x, y)
        assert all(w.get(*t) == C.FORMATION for t in f.tiles)
        cx, cy = f.center
        assert math.hypot(cx - bx, cy - by) >= C.FORMATION_MIN_BASE_DIST
        assert all(math.hypot(cx - o.center[0], cy - o.center[1]) >= C.THAW_FUMAROLE_FORM_GAP for o in others)
        assert all(math.hypot(cx - o.center[0], cy - o.center[1]) >= C.THAW_FUMAROLE_SPACING
                   for o in vents if o is not f)


def test_vents_do_not_change_the_rest_of_the_map():
    """Rng próprio e sorteio depois dos morros: a geo (sem as fumarolas) e os morros saem iguais aos de antes delas,
    e a fumarola cai no chão livre, sem encostar em morro."""
    w = generate_surface(7)
    geo = w.geo
    plain = generate_geo(7, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)        # a geo pura não tem fumarola
    assert not plain.vents
    rest = [(f.kind, f.tx, f.ty) for f in geo.formations if not f.kind.startswith("vent_")]
    assert rest == [(f.kind, f.tx, f.ty) for f in plain.formations]
    assert geo.formations[-len(geo.vents):] == geo.vents                    # somadas no fim da lista
    walls = {C.ROCK, C.IRON, C.SILICON, C.ICE, C.BEDROCK}
    for f in geo.vents:
        near = [(x, y) for x in range(f.tx - 2, f.tx + f.size[0] + 2) for y in range(f.ty - 2, f.ty + f.size[1] + 2)]
        assert not any(w.get(*t) in walls for t in near), f.kind


@pytest.mark.parametrize("seed", SEEDS)
def test_world_stays_reachable_with_the_vents(seed):
    w = generate_surface(seed)
    reach = w.reachable_from(C.BASE_TILE)
    for f in w.geo.vents:                       # dá pra chegar do lado de cada fumarola
        ring = {(x + dx, y + dy) for x, y in f.tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - set(f.tiles)
        assert reach & ring, f.kind


def test_state_wakes_fumaroles_and_load_rebuilds(new_state):
    vents = new_state.surface.geo.vents
    assert vents and new_state.surface.vents_awake == [False] * len(vents)
    heat = sorted(thaw.fumarole_threshold(i) for i in range(len(vents)))[1]   # acorda 2 (pelo menos)
    new_state.indices["heat"] = heat
    new_state._apply_thaw()
    awake = new_state.surface.vents_awake
    assert awake == [thaw.fumarole_active(heat, i) for i in range(len(vents))] and sum(awake) >= 2
    woke = sorted(e[1] for e in new_state.events if e[0] == "fumarole_wake")
    assert woke == [i for i, a in enumerate(awake) if a]
    new_state.events.clear()
    new_state._apply_thaw()
    assert not [e for e in new_state.events if e[0] == "fumarole_wake"]
    loaded = save.state_from_dict(save.state_to_dict(new_state))
    assert loaded.surface.vents_awake == awake and not loaded.events
    other = GameState(rng=random.Random(2))                  # a geo é dividida entre estados: nada vaza
    assert other.surface.vents_awake == [False] * len(vents)


def test_save_has_no_new_thaw_fields(new_state):
    new_state.indices["heat"] = 10_000
    new_state._apply_thaw()
    data = save.state_to_dict(new_state)
    assert data["version"] == save.SAVE_VERSION              # v9 (v0.5 M2): sem campo novo do degelo
    assert set(data["layers"]["surface"]) == set(save.state_to_dict(GameState(rng=random.Random(1)))["layers"]["surface"])


# ---------------------------------------------------------------- sprites e fumaça
def test_vent_sprites_switch_with_the_awake_flag():
    pygame.init()
    from game import hills as H
    fs = H.FormationSprites()
    g = GameState(rng=random.Random(1))
    f = g.surface.geo.vents[0]
    dormant = fs.surface(f, 2, 0)
    active = fs.surface(f, 2, 1)
    assert dormant.get_size() == active.get_size()
    assert pygame.image.tobytes(dormant, "RGBA") != pygame.image.tobytes(active, "RGBA")
    # a brasa (12, 13) não muda com o estágio; o enxofre (10, 11) muda
    pal = {st: H.ramp("HILL+VENT", "basalt", st) for st in ("storm", "arid", "mist", "green")}
    assert all(len(p) == 14 for p in pal.values())
    assert len({tuple(map(tuple, p[12:14])) for p in pal.values()}) == 1
    assert len({tuple(map(tuple, p[10:12])) for p in pal.values()}) > 1


def test_smoke_rises_spreads_bends_with_wind_and_culls():
    from game import smoke as S
    sm = S.VentSmoke(seed=7)
    mouth = [(1000.0, 1000.0)]
    view = pygame.Rect(800, 800, 480, 270)
    src = [S.Source(0, "cone", mouth)]
    for _ in range(120):                                     # 2 s sem vento
        sm.update(1 / 60, src, (0.0, 0.0), view)
    assert sm.puffs
    old = max(sm.puffs, key=lambda p: p.age)
    assert old.y < 1000 - 15 and old.radius() > S.SMOKE["radius"][1]
    calm_x = sum(p.x for p in sm.puffs) / len(sm.puffs)
    windy = S.VentSmoke(seed=7)
    for _ in range(120):
        windy.update(1 / 60, src, (20.0, 0.0), view)
    assert sum(p.x for p in windy.puffs) / len(windy.puffs) > calm_x + 5
    far = S.VentSmoke(seed=7)                                # fora da tela: nenhum puff (culling)
    for _ in range(120):
        far.update(1 / 60, src, (0.0, 0.0), pygame.Rect(0, 0, 480, 270))
    assert not far.puffs
    # dormente: sem fumaça
    none = S.VentSmoke(seed=7)
    for _ in range(60):
        none.update(1 / 60, [], (0.0, 0.0), view)
    assert not none.puffs


def test_smoke_override_and_mouth_glow():
    """M3.5: o C.SMOKE_OVERRIDE vale por cima do JSON (fumaça mais clara e que vive mais) e a boca acordada ganha um
    brilho quente leve que só clareia (somado), acendendo junto com a taxa quando a fumarola acorda."""
    from game import smoke as S
    for key, value in C.SMOKE_OVERRIDE.items():
        assert S.SMOKE[key] == value
    pygame.init()
    v = S.VentSmoke(seed=1)
    src = [S.Source(0, "cone", [(50.0, 50.0)])]
    canvas = pygame.Surface((100, 100), 0, 32)
    canvas.fill((40, 30, 34))
    v.draw_glow(canvas, (0, 0), src, 0.0)
    r, g, b, _ = canvas.get_at((50, 50))
    assert r > 40 and g >= 30 and r - 40 > b - 34          # mais quente que o basalto em volta
    assert canvas.get_at((0, 0))[:3] == (40, 30, 34)       # longe da boca não mexe
    v.wake(0)                                              # acabou de acordar: ainda apagado
    canvas.fill((40, 30, 34))
    v.draw_glow(canvas, (0, 0), src, 0.0)
    assert canvas.get_at((50, 50))[:3] == (40, 30, 34)
