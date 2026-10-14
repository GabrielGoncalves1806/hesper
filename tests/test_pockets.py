"""Gelos-portão derretendo com o calor, destroço rico e contêiner lacrado (v0.4 Marco 3 · M3.2 e M3.5 · bíblia §12).

M3.5: o portão é um amontoado de blocos de gelo (game/ice_blocks.py). Os testes do M3.2 que olhavam a pegada em tiles
por etapa (4×2 → 3×2 → 2×1) viraram testes da colisão por retângulo: fechado em p = 0, a fresta abre num p < 1 (e o
player passa andando de verdade), nada sobra em p = 1. Os eventos agora são só 2 por portão (começou a derreter e
abriu a fresta), e não 3. O resto (destroço rico, contêiner, save sem os portões) continua igual.
"""

import json
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from game import config as C
from game import ice_blocks, layers, player
from game import save
from game import thaw
from game import wrecks
from game.surface_gen import generate_surface
from game.systems import GameState

T = C.TILE
SEEDS = (1, 7, 42)


def game(seed: int = C.WORLD_SEED) -> GameState:
    return GameState(seed, rng=random.Random(1))


def heat_for(i: int, p: float) -> float:
    """Calor que deixa o portão `i` exatamente no progresso `p` (0..1, linear entre o 1º e o último marco)."""
    lo, hi = C.THAW_GATE_HEAT[i][0], C.THAW_GATE_HEAT[i][-1]
    return lo + (hi - lo) * p


def set_melt(g: GameState, i: int, p: float) -> None:
    g.indices["heat"] = heat_for(i, p)
    g._apply_thaw()


def open_interior(world, pocket) -> set:
    """O chão de dentro do bolsão (sem o destroço rico e o contêiner, que são sólidos)."""
    return {t for t in pocket.interior if not world.is_solid(*t)}


def real_rects(g: GameState, i: int) -> list:
    """Tudo o que bate na caixa do player em volta do portão `i`, no mundo de verdade (tiles sólidos, máquinas e os
    blocos de gelo), relativo ao base_px: é o que o `solids_near` do movimento devolve ali."""
    bx, by = g.surface.geo.pockets[i].gate.base_px
    x0, x1, y0, y1 = ice_blocks.AREA
    rects = []
    for ty in range(int((by + y0) // T) - 1, int((by + y1) // T) + 2):
        for tx in range(int((bx + x0) // T) - 1, int((bx + x1) // T) + 2):
            if g.surface.world.is_solid(tx, ty):
                rects.append((tx * T, ty * T, T, T))
    rects += [m.rect for m in g.surface.machines] + g.surface.gate_solids
    return [(x - bx, y - by, w, h) for x, y, w, h in rects]


def real_passable(g: GameState, i: int) -> bool:
    """A busca da fresta da Designer, mas com as paredes de verdade do mapa (sem o corredor de mentira)."""
    return ice_blocks.passable(real_rects(g, i), walls=False)


def walk_path(g: GameState, i: int) -> list[tuple[int, int]]:
    """Caminho (px relativos ao base_px, passo de 1 px) do avental pro bolsão na grade de colisão de verdade."""
    return ice_blocks.path_through(real_rects(g, i), walls=False)


# ---- progresso e etapa (funções puras) -------------------------------------------------------------------------
def test_gate_progress_goes_from_first_to_last_mark_and_gate_0_melts_first():
    for i, marks in enumerate(C.THAW_GATE_HEAT):
        assert list(marks) == sorted(marks)
        assert thaw.gate_progress(0, i) == 0.0 and thaw.gate_progress(marks[0], i) == 0.0
        assert thaw.gate_progress(marks[-1], i) == 1.0 and thaw.gate_progress(marks[-1] * 10, i) == 1.0
        assert thaw.gate_progress((marks[0] + marks[-1]) / 2, i) == pytest.approx(0.5)
    for heat in range(0, 12000, 250):                       # o portão 0 nunca fica atrás dos outros
        ps = [thaw.gate_progress(heat, i) for i in range(len(C.THAW_GATE_HEAT))]
        assert ps == sorted(ps, reverse=True), (heat, ps)
    ps = [thaw.gate_progress(heat, 0) for heat in range(0, 5000, 10)]
    assert ps == sorted(ps)                                 # monótona


def test_gate_stage_is_derived_from_progress_and_the_gap():
    assert thaw.gate_stage(0.0, 0.6) == 0
    assert thaw.gate_stage(0.01, 0.6) == thaw.GATE_MELTING == 1
    assert thaw.gate_stage(0.5999, 0.6) == 1
    assert thaw.gate_stage(0.6, 0.6) == thaw.GATE_OPEN == 3
    assert thaw.gate_stage(1.0, 0.6) == 3


# ---- blocos e receitas (o JSON da Designer) --------------------------------------------------------------------
def test_ice_block_strips_have_8_frames_of_the_json_size():
    pygame.init()
    assert len(ice_blocks.BLOCKS) == 6 and ice_blocks.RECIPE_KEYS == ("A", "B", "C")
    for key, info in ice_blocks.BLOCKS.items():
        fw, fh = info["frame"]
        surf = pygame.image.load(str(C.REGIONS_DIR / info["sprite"]))
        assert surf.get_size() == (fw * 8, fh), key
        assert len(info["collision"]) == 8 and 0 <= info["anchor"][0] < fw and 0 < info["anchor"][1] <= fh
    for r in ice_blocks.RECIPES.values():
        assert len(r["blocks"]) >= 3
        assert all(b["b"] in ice_blocks.BLOCKS and 0 <= b["melt"][0] < b["melt"][1] <= 1 for b in r["blocks"])
        assert max(b["melt"][1] for b in r["blocks"]) == 1.0            # em p = 1 não sobra bloco


def test_frame_follows_the_melt_window_and_the_block_vanishes_at_the_end():
    melt = (0.4, 0.8)
    assert ice_blocks.frame_at(melt, 0.0) == 0 and ice_blocks.frame_at(melt, 0.399) == 0
    assert ice_blocks.frame_at(melt, 0.4) == 0 and ice_blocks.frame_at(melt, 0.45) == 1
    assert ice_blocks.frame_at(melt, 0.6) == 4 and ice_blocks.frame_at(melt, 0.7999) == 7
    assert ice_blocks.frame_at(melt, 0.8) is None and ice_blocks.frame_at(melt, 1.0) is None
    frames = [ice_blocks.frame_at(melt, p / 100) for p in range(80)]
    assert frames == sorted(frames)                          # só encolhe


def test_hitbox_shrinks_with_the_block():
    """Cada bloco diminui junto com a hitbox: a área de colisão nunca cresce com o p e zera em p = 1."""
    for recipe in ice_blocks.RECIPE_KEYS:
        last = None
        for k in range(101):
            area = sum(w * h for _, _, w, h in ice_blocks.rel_rects(recipe, k / 100))
            assert last is None or area <= last, (recipe, k)
            last = area
        assert last == 0


def test_gap_opens_before_p1_where_the_designer_measured():
    """A fresta (a caixa 14×8 do player passa) abre antes de p = 1; a Designer mediu 0,60 / 0,57 / 0,58 com passo de
    0,01 (aqui é exato: só testa os p em que a colisão muda)."""
    measured = {k: r["opens_at"] for k, r in ice_blocks.RECIPES.items()}
    for recipe in ice_blocks.RECIPE_KEYS:
        p = ice_blocks.opens_at(recipe)
        assert 0 < p < 1 and abs(p - measured[recipe]) <= 0.0101, (recipe, p)
        assert not ice_blocks.passable(ice_blocks.rel_rects(recipe, 0.0))
        assert not ice_blocks.passable(ice_blocks.rel_rects(recipe, p - 1e-6))
        assert ice_blocks.passable(ice_blocks.rel_rects(recipe, p))


def test_recipe_is_picked_by_the_seed_and_all_three_show_up():
    assert ice_blocks.recipe_for(7, 0) == ice_blocks.recipe_for(7, 0)
    seen = {ice_blocks.recipe_for(seed, i) for seed in range(1, 30) for i in range(3)}
    assert seen == set(ice_blocks.RECIPE_KEYS)


# ---- no jogo: colisão por retângulo, sem pegada em tiles --------------------------------------------------------
@pytest.mark.parametrize("seed", (3, 7, 1, 42))
def test_closed_at_0_gap_opens_before_1_and_nothing_left_at_1(seed):
    """Substitui o teste da pegada por etapa do M3.2: fechado em p = 0 pra caixa do player (no mapa de verdade),
    ainda fechado logo antes da fresta, aberto nela (com gelo sobrando) e sem colisão nenhuma em p = 1."""
    g = game(seed)
    w, geo = g.surface.world, g.surface.geo
    assert g.surface.gate_melt == [0.0] * len(geo.pockets) and g.surface.gate_ice == [0] * len(geo.pockets)
    p0 = geo.pockets[0]
    assert not any(w.get(*t) == C.FORMATION for t in p0.gate.tiles)           # sem pegada em tiles
    assert g.surface.gate_solids                                                 # bate pelos retângulos
    for i in range(len(geo.pockets)):
        assert not real_passable(g, i), (seed, i)                               # p = 0: fechado pra caixa
        assert not w.reachable_from(C.BASE_TILE) & set(geo.pockets[i].interior)
    opens = ice_blocks.opens_at(g.surface.gate_recipes[0])
    set_melt(g, 0, opens - 0.001)
    assert g.surface.gate_ice[0] == 1 and not real_passable(g, 0)
    set_melt(g, 0, opens)
    assert g.surface.gate_ice[0] == 3 and real_passable(g, 0) and g.surface.gate_melt[0] < 1
    assert [b for b in g.surface.gate_blocks if b.gate == 0]                     # ainda tem gelo derretendo
    assert open_interior(w, p0) <= w.reachable_from(C.BASE_TILE)                # a sombra em tiles saiu
    for j, q in enumerate(geo.pockets[1:], 1):                                  # os outros continuam fechados
        if g.surface.gate_melt[j] == 0:
            assert not real_passable(g, j) and not w.reachable_from(C.BASE_TILE) & set(q.interior)
    set_melt(g, 0, 1.0)
    assert not [b for b in g.surface.gate_blocks if b.gate == 0]                # p = 1: nenhum bloco nem colisão
    bx, by = p0.gate.base_px
    assert not [r for r in g.surface.gate_solids if abs(r[0] - bx) < 200 and abs(r[1] - by) < 200]
    assert all(w.get(*t) == C.BEDROCK and not w.is_minable(*t) for t in p0.ring)   # o anel continua inteiro


@pytest.mark.parametrize("seed", (3, 7, 1))                       # o portão 0 nelas usa a receita A, B e C
def test_the_player_walks_through_the_gap(seed):
    """No primeiro p em que a fresta abre, o player anda de verdade (Player.move com o solids_near do jogo) do
    avental pro bolsão pelo caminho da busca, 1 px por passo, sem ser empurrado por nada."""
    g = game(seed)
    assert g.surface.gate_recipes[0] == {3: "A", 7: "B", 1: "C"}[seed]
    set_melt(g, 0, ice_blocks.opens_at(g.surface.gate_recipes[0]))
    gate = g.surface.geo.pockets[0].gate
    bx, by = gate.base_px
    path = walk_path(g, 0)
    assert path
    g.player.x, g.player.y = bx + path[0][0], by + path[0][1]
    dt = 1.0 / C.PLAYER_SPEED
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        g.player.move(x1 - x0, y1 - y0, dt, g.solids_near)
        assert abs(g.player.x - (bx + x1)) < 1e-6 and abs(g.player.y - (by + y1)) < 1e-6, (seed, x1, y1)
        g.player.x, g.player.y = bx + x1, by + y1
    assert g.player.y < gate.ty * T - 8                                          # dentro do bolsão
    assert g.player.tile in g.surface.geo.pockets[0].interior


def test_events_when_it_starts_melting_and_when_the_gap_opens():
    """Substitui o "um evento por etapa" do M3.2: agora são 2 (1 = começou a derreter, 3 = a fresta abriu)."""
    g = game()
    set_melt(g, 0, 0.1)
    assert [e for e in g.events if e[0] == "gate_thaw"] == [("gate_thaw", 0, 1)]
    g.events.clear()
    set_melt(g, 0, 0.3)
    assert not g.events                                                          # derretendo: nada de novo
    set_melt(g, 0, 1.0)
    assert [e for e in g.events if e[0] == "gate_thaw"] == [("gate_thaw", 0, 3)]
    g.events.clear()
    g._apply_thaw()
    assert not g.events
    g.indices["heat"] = 0.0
    g._apply_thaw()                                          # o índice não desce no jogo, mas mesmo assim
    assert g.surface.gate_melt[0] == 1.0 and g.surface.gate_ice[0] == 3 and not g.events


def test_a_jump_straight_to_open_emits_both_events_in_order():
    g = game()
    set_melt(g, 0, 1.0)
    assert [e for e in g.events if e[0] == "gate_thaw" and e[1] == 0] == [("gate_thaw", 0, 1), ("gate_thaw", 0, 3)]


def test_machines_tick_melts_the_gates():
    """O _apply_thaw roda no fim do _update_machines (depois de somar os índices)."""
    g = game()
    g.indices["heat"] = heat_for(0, 0.2)
    g._update_machines(0.016)
    assert g.surface.gate_melt[0] == pytest.approx(0.2) and ("gate_thaw", 0, 1) in g.events


def test_third_gate_only_counts_when_it_exists():
    for seed in range(1, 40):
        w = generate_surface(seed)
        if len(w.geo.pockets) == 3:
            g = game(seed)
            g.indices["heat"] = float(C.THAW_GATE_HEAT[2][-1])
            g._apply_thaw()
            assert g.surface.gate_ice == [3, 3, 3] and g.surface.gate_melt == [1.0] * 3
            assert g.surface.gate_blocks == []
            return
    pytest.skip("nenhuma seed com 3 bolsões")


def test_gate_melt_is_derived_and_load_rebuilds_the_blocks():
    g = game()
    set_melt(g, 0, 0.5)
    data = save.state_to_dict(g)
    assert save.SAVE_VERSION == 8                    # v8 (v0.5 M1): o formato das camadas não mudou
    for name in ("gate_ice", "gate_melt", "gate_blocks", "gate_recipes"):
        assert name not in data["layers"]["surface"]
    loaded = save.state_from_dict(json.loads(json.dumps(data)))
    assert loaded.surface.gate_melt == g.surface.gate_melt and loaded.surface.gate_ice == g.surface.gate_ice
    assert loaded.surface.gate_blocks == g.surface.gate_blocks and loaded.surface.gate_blocks
    assert not [e for e in loaded.events if e[0] == "gate_thaw"]      # o load não solta aviso


def test_load_with_high_heat_opens_the_gates():
    """Save com o calor alto (o save não guarda os portões): o load derrete na hora, sem aviso."""
    g = game()
    data = save.state_to_dict(g)
    data["progress"]["indices"]["heat"] = float(C.THAW_GATE_HEAT[1][-1])
    loaded = save.state_from_dict(json.loads(json.dumps(data)))
    assert loaded.surface.gate_melt[:2] == [1.0, 1.0] and loaded.surface.gate_ice[:2] == [3, 3]
    p = loaded.surface.geo.pockets[1]
    assert open_interior(loaded.surface.world, p) <= loaded.surface.world.reachable_from(C.BASE_TILE)


@pytest.mark.parametrize("seed", SEEDS)
def test_blocks_are_deterministic_by_seed(seed):
    a, b = game(seed), game(seed)
    for g in (a, b):
        set_melt(g, 0, 0.45)
    assert a.surface.gate_recipes == b.surface.gate_recipes
    assert a.surface.gate_recipes == [ice_blocks.recipe_for(seed, i) for i in range(len(a.surface.geo.pockets))]
    assert a.surface.gate_blocks == b.surface.gate_blocks


def test_geo_is_never_mutated_by_the_thaw():
    """O geo é dividido entre os mundos da mesma seed (cache): o derretimento mexe só na camada."""
    g = game()
    gate = g.surface.geo.pockets[0].gate
    before = (gate.variant, list(gate.footprint), gate.base_px)
    set_melt(g, 0, 1.0)
    assert (gate.variant, list(gate.footprint), gate.base_px) == before
    fresh = game()
    assert fresh.surface.gate_melt[0] == 0.0 and fresh.world.closed_gate_tiles >= set(gate.tiles)


def test_current_formations_leave_the_gate_out():
    """Substitui o "troca o sprite pela etapa" do M3.2: o portão não é mais um sprite inteiro, vai em blocos."""
    g = game()
    geo = g.surface.geo
    forms = layers.current_formations(g.surface)
    assert len(forms) == len(geo.formations) - len(geo.pockets) and all(f.kind != "ice_gate" for f in forms)


def test_cannot_place_a_machine_on_an_ice_block():
    g = game()
    p = g.surface.geo.pockets[0]
    tile = next(t for t in p.gate.tiles if any(
        player.overlaps((t[0] * T, t[1] * T, T, T), r) for r in g.surface.gate_solids))
    g.inventory.add("o2", 1)
    g.player.x, g.player.y = (tile[0] + 0.5) * T, (p.gate.ty + 3.5) * T          # no avental, no alcance
    assert not g.can_place("o2", tile)
    set_melt(g, 0, 1.0)
    assert g.can_place("o2", tile)                                                # sem gelo: chão livre


def test_ice_blocks_collide_only_on_the_surface():
    g = game()
    assert g.surface.gate_solids
    g.enter_layer("cave")
    assert g.active.gate_solids == [] and g.active.gate_blocks == []


def test_map_tooltip_says_melting_with_the_percent():
    from game import map_view
    g = game()
    assert map_view._gate_state(g.surface, 0) == "fecha a passagem · gelo"
    set_melt(g, 0, 0.42)
    assert map_view._gate_state(g.surface, 0) == "derretendo · 42%"
    set_melt(g, 0, 1.0)
    assert map_view._gate_state(g.surface, 0) == "aberto · passagem livre"


def test_scanner_map_paints_the_closed_gate_until_the_gap_opens():
    from game import minimap
    g = game()
    tile = g.surface.geo.pockets[0].gate.tiles[0]
    assert minimap.tile_color(g.world, *tile) == minimap.TILE_COLORS[C.FORMATION]
    set_melt(g, 0, 1.0)
    assert minimap.tile_color(g.world, *tile) != minimap.TILE_COLORS[C.FORMATION]


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


# ---- render: um objeto por bloco, pelo pé, recolorido pela rampa ICE, e a geada no chão ------------------------
def test_render_draws_each_ice_block_by_its_foot_and_the_frost_ring():
    """Substitui o "sprite pela etapa" do M3.2: cada bloco é um objeto próprio no desenho (pé = base_px + (x, y) da
    receita, âncora do JSON), some quando derrete, e a geada vai no chão a partir de p > 0."""
    pygame.init()
    from game.assets import Sprites
    from game.render import Renderer
    g = game()
    r = Renderer(Sprites())
    gate = g.surface.geo.pockets[0].gate
    bx, by = gate.base_px
    cam = (int(bx - 480), int(by - 270))
    r.view_w, r.view_h = C.SCREEN_W, C.SCREEN_H

    def drawn():
        return [(f, s, x, y) for f, s, x, y in r.visible_formations(g, cam) if f.kind == "ice_block" and f.gate == 0]

    recipe = ice_blocks.RECIPES[g.surface.gate_recipes[0]]
    vis = drawn()
    assert len(vis) == len(recipe["blocks"]) and r.gate_frost(g, cam) == []
    for (b, surf, x, y), spec in zip(vis, recipe["blocks"]):
        info = ice_blocks.BLOCKS[spec["b"]]
        assert b.key == spec["b"] and b.frame == 0 and b.foot == (bx + spec["x"], by + spec["y"])
        assert surf.get_size() == tuple(info["frame"])
        assert (x + info["anchor"][0], y + info["anchor"][1]) == (round(b.foot[0]), round(b.foot[1]))
    set_melt(g, 0, 0.5)
    assert sorted(b.frame for b, *_ in drawn()) != [0] * len(drawn())            # encolhendo
    assert len(r.gate_frost(g, cam)) == 1
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    items = r.collect_objects(canvas, g, cam, 0.0)
    feet = {b.foot[1] for b, *_ in drawn()}
    assert feet <= {ay for ay, _ in items}                                       # cada um ordena pelo pé dele
    set_melt(g, 0, 1.0)
    assert drawn() == []
    rings = r.gate_frost(g, cam)
    assert len(rings) == 1
    surf, x, y = rings[0]
    assert surf.get_size() == (176, 72) and x == round(bx - 88) and y == round(by - 60)
    r.draw(canvas, g, cam, 0.0)                                       # desenha sem quebrar


def test_ice_blocks_recolor_by_stage_and_fall_back_without_art():
    pygame.init()
    from game import hills
    b = ice_blocks.blocks_at((0, 0), "A", 0.0)[0]
    sprites = hills.IceBlockSprites()
    arid, green = sprites.surface(b, 2), sprites.surface(b, 4)
    assert arid.get_size() == green.get_size() == b.frame_size
    ax, ay = b.anchor
    probe = [(x, y) for x in range(arid.get_width()) for y in range(arid.get_height())
             if arid.get_at((x, y)).a == 255]
    assert probe and any(arid.get_at(p) != green.get_at(p) for p in probe)        # a rampa ICE muda com o estágio
    fb = hills.IceBlockSprites._fallback(b)
    assert fb.get_size() == b.frame_size


def test_ice_block_in_front_turns_on_the_xray():
    """Player logo atrás (acima do pé) de um bloco que o cobre: o raio-x acende, igual às formações."""
    pygame.init()
    from game.assets import Sprites
    from game.render import Renderer
    g = game()
    r = Renderer(Sprites())
    r.view_w, r.view_h = C.SCREEN_W, C.SCREEN_H
    b = max(g.surface.gate_blocks, key=lambda b: b.foot[1])                      # o da frente
    g.player.x, g.player.y = b.foot[0], b.foot[1] - 6
    assert r.formation_occludes(g)


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


def test_hovering_the_ice_gate_shows_the_heat_it_needs(app, monkeypatch):
    """Dono: com o mouse em cima do gelo do portão, a dica mostra o calor em que a passagem abre e o de agora."""
    s = app.state
    s.indices["heat"] = 0.0
    layer = s.surface                                    # o app é compartilhado e o degelo só sobe: volta pro inteiro
    layer.gate_melt = [0.0] * len(layer.gate_melt)
    layer.gate_ice = [0] * len(layer.gate_ice)
    layer.refresh_gates()
    pocket = s.surface.geo.pockets[0]
    xs = [x for x, _ in pocket.gate.tiles]
    ys = [y for _, y in pocket.gate.tiles]
    spot = ((min(xs) + max(xs) + 1) / 2 * T, (max(ys) + 0.5) * T)
    monkeypatch.setattr(app, "mouse_world", lambda: spot)
    monkeypatch.setattr(app, "e_target", lambda: None)
    assert app.gate_under_mouse() == 0
    need = heat_for(0, ice_blocks.opens_at(s.surface.gate_recipes[0]))
    from game.ui import fmt
    assert app.hint() == f"Gelo-portão · a passagem abre com ~{fmt(need)} pK (agora 0)"
    set_melt(s, 0, 1.0)                                  # derreteu tudo: sem bloco, sem dica do portão
    assert app.gate_under_mouse() is None


def test_crater_ice_hint_shows_the_heat_it_needs(app):
    s = app.state
    s.surface.crater_ice = 0
    s.indices["heat"] = 12.0
    need = f"{C.THAW_CRATER_HEAT[-1]:,}".replace(",", ".")      # o HUD escreve milhar com ponto
    assert app.crater_ice_hint().endswith(f"abre com {need} pK (agora 12)")
