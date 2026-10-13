"""Gelos-portão derretendo com o calor, destroço rico e contêiner lacrado (v0.4 Marco 3 · M3.2 · bíblia §12)."""

import json
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import layers
from game import save
from game import thaw
from game import wrecks
from game.geo import GATE_FOOTPRINTS, gate_at
from game.surface_gen import generate_surface
from game.systems import GameState

T = C.TILE
SEEDS = (1, 7, 42)


def game(seed: int = C.WORLD_SEED) -> GameState:
    return GameState(seed, rng=random.Random(1))


def heat_for(i: int, stage: int) -> float:
    """Calor que deixa o portão `i` exatamente na etapa `stage` (0..3)."""
    return 0.0 if stage == 0 else float(C.THAW_GATE_HEAT[i][stage - 1])


def formation_tiles(world, gate) -> set:
    """Tiles FORMATION dentro da caixa 4×2 do portão (a pegada da etapa 0)."""
    return {t for t in gate.tiles if world.get(*t) == C.FORMATION}


def open_interior(world, pocket) -> set:
    """O chão de dentro do bolsão (sem o destroço rico e o contêiner, que são sólidos)."""
    return {t for t in pocket.interior if not world.is_solid(*t)}


# ---- gate_stage (função pura) --------------------------------------------------------------------------------
def test_gate_stage_steps_with_heat_and_gate_0_opens_first():
    for i, marks in enumerate(C.THAW_GATE_HEAT):
        assert len(marks) == 3 and list(marks) == sorted(marks)
        assert thaw.gate_stage(0, i) == 0
        assert thaw.gate_stage(marks[0] - 1, i) == 0
        assert thaw.gate_stage(marks[0], i) == 1
        assert thaw.gate_stage(marks[1], i) == 2
        assert thaw.gate_stage(marks[2], i) == 3
        assert thaw.gate_stage(marks[2] * 10, i) == 3
    for heat in range(0, 12000, 250):                       # o portão 0 nunca fica atrás dos outros
        stages = [thaw.gate_stage(heat, i) for i in range(len(C.THAW_GATE_HEAT))]
        assert stages == sorted(stages, reverse=True), (heat, stages)
    stages = [thaw.gate_stage(heat, 0) for heat in range(0, 12000, 50)]
    assert stages == sorted(stages)                         # monótona


# ---- pegada por etapa (bate com o JSON da Designer) ----------------------------------------------------------
def test_gate_footprints_come_from_the_designer_json():
    data = json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8"))["formations"]
    x0 = min(x for x, _ in data["ice_gate_0"]["tiles"])
    y0 = min(y for _, y in data["ice_gate_0"]["tiles"])
    for s in range(3):
        info = data[f"ice_gate_{s}"]
        assert info["foot"] == data["ice_gate_0"]["foot"]             # a âncora não anda entre as etapas
        want = sorted((x - x0, y - y0) for x, y in info["tiles"])
        assert sorted(GATE_FOOTPRINTS[s]) == want
    assert [len(f) for f in GATE_FOOTPRINTS] == [8, 6, 2]              # 4×2 → 3×2 → 2×1


@pytest.mark.parametrize("seed", SEEDS)
def test_gate_formation_keeps_its_anchor_at_every_stage(seed):
    w = generate_surface(seed)
    for p in w.geo.pockets:
        gate = p.gate
        for s in range(3):
            g = gate_at(gate, s)
            assert g.variant == s and g.base_px == gate.base_px and g.size == gate.size
            assert set(g.tiles) <= set(gate.tiles)
        assert gate_at(gate, 3) is None


@pytest.mark.parametrize("seed", SEEDS)
def test_formation_tiles_follow_the_stage_and_the_open_gate_lets_you_in(seed):
    g = game(seed)
    w, geo = g.surface.world, g.surface.geo
    assert g.surface.gate_ice == [0] * len(geo.pockets)
    for i, p in enumerate(geo.pockets):
        assert formation_tiles(w, p.gate) == set(gate_at(p.gate, 0).tiles)
    for stage in range(4):
        g.indices["heat"] = heat_for(0, stage)
        g._apply_thaw()
        p = geo.pockets[0]
        assert g.surface.gate_ice[0] == stage
        want = set() if stage == 3 else set(gate_at(p.gate, stage).tiles)
        assert formation_tiles(w, p.gate) == want
        assert all(w.get(*t) == w.floor_kind for t in set(p.gate.tiles) - want)
        reach = w.reachable_from(C.BASE_TILE)
        if stage == 0:
            assert not reach & set(p.interior)
        if stage == 3:
            assert open_interior(w, p) <= reach
        # nas etapas 1 e 2 a pegada da Designer (3×2, 2×1) já deixa uma fresta de 1 tile no corredor de 4: o
        # player passa (ver a bíblia §12). O teste só fixa o que é contrato: fechado na 0, aberto na 3.
        assert all(w.get(*t) == C.BEDROCK and not w.is_minable(*t) for t in p.ring)   # o anel continua inteiro
        for j, q in enumerate(geo.pockets[1:], 1):                   # os outros, inteiros, ainda fechados
            if g.surface.gate_ice[j] == 0:
                assert not reach & set(q.interior)


def test_state_emits_one_event_per_stage_and_never_goes_back():
    g = game()
    g.indices["heat"] = heat_for(0, 3)
    g._apply_thaw()
    assert [e for e in g.events if e[0] == "gate_thaw" and e[1] == 0] == [("gate_thaw", 0, 1), ("gate_thaw", 0, 2),
                                                           ("gate_thaw", 0, 3)]
    g.events.clear()
    g._apply_thaw()
    assert not g.events
    g.indices["heat"] = 0.0
    g._apply_thaw()                                          # o índice não desce no jogo, mas mesmo assim
    assert g.surface.gate_ice[0] == 3 and not g.events


def test_machines_tick_melts_the_gates():
    """O _apply_thaw roda no fim do _update_machines (depois de somar os índices)."""
    g = game()
    g.indices["heat"] = float(C.THAW_GATE_HEAT[0][0])
    g._update_machines(0.016)
    assert g.surface.gate_ice[0] == 1 and ("gate_thaw", 0, 1) in g.events


def test_third_gate_only_counts_when_it_exists():
    for seed in range(1, 40):
        w = generate_surface(seed)
        if len(w.geo.pockets) == 3:
            g = game(seed)
            g.indices["heat"] = float(C.THAW_GATE_HEAT[2][2])
            g._apply_thaw()
            assert g.surface.gate_ice == [3, 3, 3]
            return
    pytest.skip("nenhuma seed com 3 bolsões")


def test_gate_ice_is_derived_and_load_rebuilds_open_gates():
    g = game()
    g.indices["heat"] = heat_for(0, 3) + 1
    g._apply_thaw()
    data = save.state_to_dict(g)
    assert save.SAVE_VERSION == 7
    assert "gate_ice" not in json.dumps(data["layers"]["surface"].keys().__repr__())
    assert "gate_ice" not in data["layers"]["surface"]
    loaded = save.state_from_dict(json.loads(json.dumps(data)))
    assert loaded.surface.gate_ice == g.surface.gate_ice
    assert not [e for e in loaded.events if e[0] == "gate_thaw"]      # o load não solta aviso
    p = loaded.surface.geo.pockets[0]
    assert not formation_tiles(loaded.surface.world, p.gate)
    assert open_interior(loaded.surface.world, p) <= loaded.surface.world.reachable_from(C.BASE_TILE)


def test_load_with_high_heat_opens_gates_even_without_tile_changes():
    """Save com o calor alto mas os tiles do portão ainda fechados (o save não guarda os portões): o load abre."""
    g = game()
    data = save.state_to_dict(g)
    data["progress"]["indices"]["heat"] = heat_for(1, 2)
    loaded = save.state_from_dict(json.loads(json.dumps(data)))
    assert loaded.surface.gate_ice[:2] == [3, 2]
    pockets = loaded.surface.geo.pockets
    assert formation_tiles(loaded.surface.world, pockets[1].gate) == set(gate_at(pockets[1].gate, 2).tiles)


def test_geo_is_never_mutated_by_the_thaw():
    """O geo é dividido entre os mundos da mesma seed (cache): o derretimento mexe só no world e na camada."""
    g = game()
    gate = g.surface.geo.pockets[0].gate
    before = (gate.variant, list(gate.footprint))
    g.indices["heat"] = heat_for(0, 3)
    g._apply_thaw()
    assert (gate.variant, list(gate.footprint)) == before
    fresh = game()
    assert formation_tiles(fresh.surface.world, fresh.surface.geo.pockets[0].gate) == set(gate.tiles)


def test_current_formations_swap_the_gate_by_stage():
    g = game()
    geo = g.surface.geo
    n = len(geo.formations)
    gates = [f for f in layers.current_formations(g.surface) if f.kind == "ice_gate"]
    assert len(layers.current_formations(g.surface)) == n and all(f.variant == 0 for f in gates)
    g.indices["heat"] = heat_for(0, 2)
    g._apply_thaw()
    gates = [f for f in layers.current_formations(g.surface) if f.kind == "ice_gate"]
    assert sorted(f.variant for f in gates)[-1] == 2
    g.indices["heat"] = heat_for(0, 3)
    g._apply_thaw()
    assert len(layers.current_formations(g.surface)) == n - 1


# ---- destroço rico e contêiner lacrado ------------------------------------------------------------------------
@pytest.mark.parametrize("seed", SEEDS)
def test_rich_wreck_and_sealed_container_sit_in_each_pocket(seed):
    w = generate_surface(seed)
    rich = [x for x in w.wrecks if x.rich]
    assert len(rich) == len(w.geo.pockets) == len(w.containers)
    for p, wreck, box in zip(w.geo.pockets, rich, w.containers):
        assert (wreck.tx, wreck.ty) == p.wreck_spot and box == p.container_spot
        assert all(t in p.interior for t in wreck.tiles + [wreck.crate])
        assert all(w.get(*t) == C.WRECK for t in wreck.tiles) and w.get(*wreck.crate) == C.LOOT_CRATE
        assert w.get(*box) == C.CONTAINER and w.is_solid(*box) and not w.is_wall(*box) and not w.is_minable(*box)
    normal = [x for x in w.wrecks if not x.rich]
    assert C.WRECK_COUNT[0] <= len(normal) <= C.WRECK_COUNT[1]
    assert w.wrecks[:len(normal)] == normal                      # os ricos vêm depois (os ranks de antes não mudam)


@pytest.mark.parametrize("seed", SEEDS)
def test_rich_wreck_and_container_are_reachable_once_the_gate_opens(seed):
    g = game(seed)
    w = g.surface.world
    g.indices["heat"] = 1e9
    g._apply_thaw()
    reach = w.reachable_from(C.BASE_TILE)
    for wreck in (x for x in w.wrecks if x.rich):
        x, y = wreck.crate
        assert any(n in reach for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for x, y in w.containers:
        assert any(n in reach for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))


def test_rich_loot_beats_the_normal_cargo_and_is_fixed_by_seed():
    w = generate_surface(7)
    rich = next(x for x in w.wrecks if x.rich)
    a = dict(wrecks.crate_loot(rich, 7))
    assert a == dict(wrecks.crate_loot(rich, 7))
    for res, (lo, hi) in C.WRECK_RICH_LOOT.items():
        assert lo <= a[res] <= hi
        assert lo > wrecks.SPECS["cargo"].loot[res][1]              # mais material que a melhor nave comum
    crates = wrecks.make_crates(w, 7)
    assert rich.crate in crates


def test_rich_wreck_brings_a_missing_blueprint():
    """Se algum projeto não caiu nos destroços de fora, o 1º destroço rico traz ele."""
    w = generate_surface(7)
    normal = [x for x in w.wrecks if not x.rich]
    assert wrecks.missing_blueprints(normal) == []                  # no mundo normal os 3 já caem
    rich = wrecks.pocket_wrecks(w.geo.pockets, [x for x in normal if x.blueprint != "lamp_t2"])
    assert rich[0].blueprint == "lamp_t2" and all(x.blueprint is None for x in rich[1:])
    assert ("bp_lamp_t2", 1) in wrecks.crate_loot(rich[0], 7)
    assert all(x.blueprint is None for x in w.wrecks if x.rich)


def test_sealed_container_never_opens_and_shows_the_lore_line():
    g = game()
    g.indices["heat"] = 1e9
    g._apply_thaw()
    tx, ty = g.world.containers[0]
    g.player.x, g.player.y = (tx + 0.5) * T, (ty + 2) * T - 2
    assert g.interaction() == ("container", (tx, ty))
    assert g.interactable_at((tx + 0.5) * T, (ty + 0.5) * T) == ("container", (tx, ty))
    assert g.in_reach("container", (tx, ty))
    assert "Contêiner lacrado" in C.CONTAINER_LORE and "Colônia Hesper" in C.CONTAINER_LORE
    g.player.x, g.player.y = (tx + 0.5) * T, (ty + 9) * T
    assert not g.in_reach("container", (tx, ty))


def test_container_marker_appears_on_the_map_once_seen():
    from game import map_view
    g = game()
    tx, ty = g.world.containers[0]
    assert not [e for e in map_view.map_entries(g, "surface") if e.category == "container"]
    g.surface.explored.reveal_rect(tx, ty, 1, 1)
    entries = [e for e in map_view.map_entries(g, "surface") if e.category == "container"]
    assert len(entries) == 1 and entries[0].title == "Contêiner"


# ---- render: sprite pela etapa, aberto sem sprite e com a geada ------------------------------------------------
def test_render_uses_the_stage_sprite_and_frost_ring_when_open():
    pygame.init()
    from game.assets import Sprites
    from game.render import Renderer
    g = game()
    r = Renderer(Sprites())
    gate = g.surface.geo.pockets[0].gate
    bx, by = gate.base_px
    cam = (int(bx - 480), int(by - 270))
    r.view_w, r.view_h = C.SCREEN_W, C.SCREEN_H

    def gate_sprites():
        return [f for f, *_ in r.visible_formations(g, cam) if f.kind == "ice_gate" and f.tx == gate.tx]

    assert [f.variant for f in gate_sprites()] == [0] and r.gate_frost(g, cam) == []
    g.indices["heat"] = heat_for(0, 2)
    g._apply_thaw()
    assert [f.variant for f in gate_sprites()] == [2]
    g.indices["heat"] = heat_for(0, 3)
    g._apply_thaw()
    assert gate_sprites() == []
    rings = r.gate_frost(g, cam)
    assert len(rings) == 1
    surf, x, y = rings[0]
    assert surf.get_size() == (176, 72) and x == round(bx - 88) and y == round(by - 60)
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    r.draw(canvas, g, cam, 0.0)                                       # desenha sem quebrar


def test_save_diff_leaves_out_the_gate_tiles():
    """A pegada dos portões é derivada: abrir um portão não põe tile nenhum no changed_tiles."""
    g = game()
    g.indices["heat"] = 1e9
    g._apply_thaw()
    assert save.state_to_dict(g)["layers"]["surface"]["changed_tiles"] == []


# ---- App: aviso, dica do contêiner e o mapa do scanner -----------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    import tempfile
    from pathlib import Path
    from game import settings
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_pockets_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def test_gate_open_event_shows_the_notice_only_when_open(app):
    app.toast_time = 0.0
    app.on_game_event(("gate_thaw", 0, 1))
    assert app.toast_time == 0.0                                 # derretendo: sem aviso
    app.on_game_event(("gate_thaw", 0, 3))
    assert app.toast == C.THAW_GATE_NOTICE and app.toast_time == C.THAW_GATE_NOTICE_TIME


def test_e_on_the_container_shows_the_lore_and_opens_nothing(app):
    s = app.state
    s.indices["heat"] = 1e9
    s._apply_thaw()
    s.pop_events()
    tx, ty = s.world.containers[0]
    s.player.x, s.player.y = (tx + 0.5) * T, (ty + 2) * T - 2
    app.set_mode("play")
    target = app.e_target()
    assert target == ("container", (tx, ty)) and app.e_label(target) == "[E] Contêiner lacrado"
    assert app.highlight_target() == ("container", (tx, ty))
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, mod=0, unicode="e", scancode=0))
    app.handle_events()
    assert app.mode == "play" and app.toast == C.CONTAINER_LORE
