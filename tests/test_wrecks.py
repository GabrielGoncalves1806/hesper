"""Destroços no deserto (v0.3 Marco 3): posição, tipos, acesso, conteúdo e projetos."""

import math

import pytest

from game import config as C
from game import wrecks
from game.surface_gen import generate_surface

SEEDS = [7, 1, 2, 3, 42, 99, 1234]


def outside(world):
    """Os destroços de fora (sem os ricos dos bolsões dos gelos-portão, v0.4 M3.2, que ficam atrás do portão)."""
    return [w for w in world.wrecks if not w.rich]


def base_dist(world, w):
    cx, cy = w.center
    bx, by = world.center
    return math.hypot(cx - bx, cy - by)


@pytest.mark.parametrize("seed", SEEDS)
def test_count_and_growing_distance(seed):
    world = generate_surface(seed)
    ws = outside(world)
    lo, hi = C.WRECK_COUNT
    assert lo <= len(ws) <= hi
    dists = [base_dist(world, w) for w in ws]
    assert dists == sorted(dists)
    assert 25 <= dists[0] <= 36
    assert dists[-1] >= 70
    for a in ws:
        for b in ws:
            if a is not b:
                assert math.hypot(a.center[0] - b.center[0], a.center[1] - b.center[1]) >= C.WRECK_SPACING


@pytest.mark.parametrize("seed", SEEDS)
def test_tiles_and_free_access(seed):
    world = generate_surface(seed)
    reach = world.reachable_from((world.center[0], world.center[1] + 1))
    for w in outside(world):
        assert all(world.get(*t) == C.WRECK for t in w.tiles)
        assert world.get(*w.crate) == C.LOOT_CRATE
        assert not any(world.vein_at(*t) for t in w.tiles + [w.crate])
        assert all(world.dist_from_center(*t) > C.SURFACE_CLEAR_RADIUS for t in w.tiles)
        # caixa e terminal: um tile de chão livre do lado, alcançável a pé desde a base
        cx, cy = w.crate
        assert any(n in reach for n in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
        if w.terminal is not None:
            tx, ty = w.terminal
            assert (tx, ty + 1) in reach
        assert world.wreck_at(*w.tiles[0]) is w and world.wreck_at(*w.crate) is w


@pytest.mark.parametrize("seed", SEEDS)
def test_kinds_logs_and_blueprints(seed):
    world = generate_surface(seed)
    ws = outside(world)
    assert ws[0].kind == "cargo" and ws[0].blueprint == "o2_tank" and ws[0].log == 3
    scanner = [w for w in ws if w.blueprint == "scanner"]
    assert len(scanner) == 1 and scanner[0].kind == "module" and scanner[0].log == 4
    assert ws[-1].kind == "module" and ws[-1].log == 6
    probe_log = [w for w in ws if w.log == 5]
    assert len(probe_log) == 1 and probe_log[0].kind == "probe"
    assert any(w.blueprint == "lamp_t2" for w in ws)
    # só módulos têm terminal (é onde o LOG mora); nave e sonda mostram o log ao abrir a caixa
    for w in ws:
        assert (w.terminal is not None) == (w.kind == "module")


def test_loot_is_fixed_by_seed_and_scales_with_size():
    a = wrecks.make_crates(generate_surface(7), 7)
    b = wrecks.make_crates(generate_surface(7), 7)
    assert {k: c.storage.to_data() for k, c in a.items()} == {k: c.storage.to_data() for k, c in b.items()}
    world = generate_surface(7)
    crates = wrecks.make_crates(world, 7)
    total = {}
    for crate in crates.values():
        n = sum(s.count for s in crate.storage.slots if s and s.item in C.RESOURCES)
        total.setdefault(crate.wreck.kind, []).append(n)
    assert min(total["cargo"]) > max(total["module"]) > 0
    assert min(total["module"]) > max(total["probe"]) > 0
    first = crates[world.wrecks[0].crate]
    assert first.storage.count("bp_o2_tank") == 1


def test_specs_match_sprite_contract():
    cargo, module, probe = (wrecks.SPECS[k] for k in ("cargo", "module", "probe"))
    assert cargo.size == (4, 3) and cargo.sprite_size == (128, 112) and cargo.crate == (1, 3)
    assert module.size == (3, 2) and module.sprite_size == (96, 88) and module.crate == (0, 2)
    assert module.terminal == (2, 1)
    assert probe.size == (2, 2) and probe.sprite_size == (64, 64) and probe.crate == (2, 1)
    w = wrecks.Wreck("cargo", 10, 20, 0)
    assert w.blit_pos == (320, 640 - 16) and w.anchor == ((10 + 2) * 32, (20 + 3) * 32)
    assert wrecks.Wreck("module", 10, 20, 0).blit_pos == (320, 640 - 24)


# ---------------------------------------------------------------------------
# Caixa de saque e projetos no GameState
# ---------------------------------------------------------------------------
from game.systems import GameState  # noqa: E402
from tests.helpers import give  # noqa: E402


def stand_at_crate(g, crate):
    """Põe o player no tile livre logo ao lado da caixa (o que estiver alcançável)."""
    cx, cy = crate.tile
    for nx, ny in ((cx, cy + 1), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1)):
        if g.world.is_floor(nx, ny):
            g.player.x, g.player.y = (nx + 0.5) * C.TILE, (ny + 1) * C.TILE - 2
            return
    raise AssertionError("caixa sem acesso")


def first_crate(g):
    return g.crates[g.world.wrecks[0].crate]


def test_recipe_locked_until_blueprint():
    g = GameState(7)
    give(g, iron=50, silicon=50, ice=50)
    assert g.recipe_status("o2_tank") == "blueprint" and not g.craft("o2_tank")
    assert g.recipe_status("scanner") == "blueprint" and g.recipe_status("lamp_t2") == "blueprint"
    g.blueprints.add("o2_tank")
    assert g.recipe_status("o2_tank") == "ok" and g.craft("o2_tank")
    assert g.inventory.count("o2_tank") == 1


def test_open_crate_learns_blueprint_and_it_vanishes():
    g = GameState(7)
    crate = first_crate(g)
    stand_at_crate(g, crate)
    assert g.interaction() == ("crate", crate)
    found = g.open_crate(crate)
    assert found == ["o2_tank"] and "o2_tank" in g.blueprints
    assert crate.storage.count("bp_o2_tank") == 0 and g.inventory.count("bp_o2_tank") == 0
    events = g.pop_events()
    assert ("crate_open", False) in events and ("blueprint", "o2_tank") in events
    assert crate.opened
    # abrir de novo não acha nada de novo
    assert g.open_crate(crate) == []


def test_take_from_crate_stack_one_and_all():
    g = GameState(7)
    crate = first_crate(g)
    g.open_crate(crate)
    i = next(k for k, s in enumerate(crate.storage.slots) if s and s.item == "iron")
    total_iron = crate.storage.count("iron")
    assert g.crate_take(crate, i, 1) == 1 and g.inventory.count("iron") == 1
    assert g.crate_take(crate, i) == total_iron - 1
    assert g.crate_take(crate) > 0
    assert crate.empty and g.inventory.count("iron") == total_iron
    assert g.crate_take(crate) == 0


def test_full_inventory_keeps_loot_in_crate():
    g = GameState(7)
    for k in range(C.INVENTORY_SLOTS):
        g.inventory.add("chest", 5)
    crate = first_crate(g)
    g.open_crate(crate)                         # o projeto entra mesmo sem espaço (ele some na hora)
    assert "o2_tank" in g.blueprints
    before = crate.storage.to_data()
    assert g.crate_take(crate) == 0 and crate.storage.to_data() == before
    assert ("inv_full",) in g.pop_events()


def test_crate_is_solid_and_wreck_terminal_reads_log():
    g = GameState(7)
    crate = first_crate(g)
    assert g.world.is_solid(*crate.tile)
    module = next(w for w in g.world.wrecks if w.kind == "module")
    tx, ty = module.terminal
    g.player.x, g.player.y = (tx + 0.5) * C.TILE, (ty + 2) * C.TILE - 2
    assert g.interaction() == ("wreck_log", module)
    px, py = (tx + 0.5) * C.TILE, (ty + 0.5) * C.TILE
    assert g.interactable_at(px, py) == ("wreck_log", module)
    assert g.read_log(module.log) == C.LOGS[module.log]
    assert module.log in g.logs_read


def test_visiting_a_wreck_counts():
    g = GameState(7)
    w = g.world.wrecks[0]
    assert not g.wrecks_visited
    g.player.x, g.player.y = (w.crate[0] + 0.5) * C.TILE, (w.crate[1] + 2) * C.TILE
    g.update(0.25, __import__("game.systems", fromlist=["Controls"]).Controls())
    assert 0 in g.wrecks_visited
