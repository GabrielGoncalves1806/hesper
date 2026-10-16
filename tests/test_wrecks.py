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
            assert w.reads_from in reach
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
    assert first.storage.count("diagram_o2_tank") == 1


def test_specs_match_sprite_contract():
    s = wrecks.SPECS
    assert set(s) == {"cargo", "module", "probe", "robot", "liner"}
    contract = {   # kind: (pegada, sprite_size, lift, caixa)
        "cargo": ((5, 3), (160, 128), 32, (1, 3)),
        "module": ((8, 4), (256, 168), 40, (5, 4)),
        "probe": ((2, 2), (64, 64), 0, (2, 1)),
        "robot": ((3, 2), (96, 64), 0, (3, 1)),
        "liner": ((5, 3), (160, 120), 24, (2, 3)),
    }
    for kind, (size, sprite_size, lift, crate) in contract.items():
        spec = s[kind]
        assert (spec.size, spec.sprite_size, spec.lift, spec.crate) == (size, sprite_size, lift, crate), kind
        assert spec.sprite == f"wreck_{kind}"
        assert spec.sprite_size == (size[0] * 32, size[1] * 32 + lift), kind   # só passa da pegada pra cima
        assert (spec.terminal is None) == (kind != "module")
    assert s["module"].terminal == (4, 2) and s["module"].reads_from == (4, 4)
    assert s["module"].terminal_rect == (138, 117, 20, 17)
    w = wrecks.Wreck("cargo", 10, 20, 0)
    assert w.blit_pos == (320, 640 - 32) and w.anchor == ((10 + 2.5) * 32, (20 + 3) * 32)
    assert w.sprite_rect == (320, 640 - 32, 160, 128)
    m = wrecks.Wreck("module", 10, 20, 0)
    assert m.terminal == (14, 22) and m.reads_from == (14, 24)


def test_reads_from_defaults_to_tile_below_terminal():
    spec = wrecks.WreckSpec("x", (2, 2), "x", (64, 64), 0, (2, 1), (1, 0), {})
    assert spec.reads_from is None
    # sem reads_from: terminal relativo (1, 0) no canto (5, 7) -> lê de (6, 8)
    assert wrecks._read_tile(5, 7, spec) == (6, 8)
    assert wrecks._read_tile(5, 7, wrecks.SPECS["probe"]) is None


@pytest.mark.parametrize("seed", [1, 7, 42, 99, 1234])
def test_robot_always_gives_circuit(seed):
    robot = wrecks.Wreck("robot", 50, 50, 6)
    items = dict(wrecks.crate_loot(robot, seed))
    assert 1 <= items["circuit"] <= 2
    assert set(items) <= {"iron", "silicon", "circuit", "chip"}
    assert "ice" not in items


def test_robot_chip_chance_is_about_40_percent():
    hits = sum("chip" in dict(wrecks.crate_loot(wrecks.Wreck("robot", 50, 50, 6), s)) for s in range(400))
    assert 120 <= hits <= 200


def test_liner_resources_are_between_cargo_and_probe():
    liner = dict(wrecks.crate_loot(wrecks.Wreck("liner", 50, 50, 3), 7))
    assert 10 <= liner["iron"] <= 14 and 4 <= liner["silicon"] <= 6 and 4 <= liner["ice"] <= 8


# ---------------------------------------------------------------------------
# Caixa de saque e diagramas no GameState
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


def test_recipe_locked_until_diagram_is_read():
    g = GameState(7)
    give(g, iron_ingot=50, circuit=10)
    assert g.recipe_status("o2_tank") == "blueprint" and not g.craft("o2_tank", bench="t2")
    assert g.recipe_status("scanner") == "blueprint" and g.recipe_status("lamp_t2") == "blueprint"
    g.blueprints.add("o2_tank")
    assert g.recipe_status("o2_tank") == "ok" and g.craft("o2_tank", bench="t2")     # v0.6 Fundo M5: receita da Bancada T2
    assert g.inventory.count("o2_tank") == 1


def test_open_crate_announces_diagram_and_keeps_it_as_item():
    g = GameState(7)
    crate = first_crate(g)
    stand_at_crate(g, crate)
    assert g.interaction() == ("crate", crate)
    found = g.open_crate(crate)
    assert found == ["o2_tank"] and "o2_tank" not in g.blueprints         # achar não libera a receita
    assert crate.storage.count("diagram_o2_tank") == 1                    # fica na caixa, é item
    events = g.pop_events()
    assert ("crate_open", False) in events and ("diagram_found", "o2_tank") in events
    assert g.recipe_status("o2_tank") == "blueprint"
    # pegar da caixa põe o diagrama no inventário (item normal), ainda sem receita
    g.crate_take(crate)
    assert g.inventory.count("diagram_o2_tank") == 1 and "o2_tank" not in g.blueprints
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
    g.open_crate(crate)                         # o diagrama é item: sem espaço, fica na caixa como o resto
    assert "o2_tank" not in g.blueprints
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


# ---------------------------------------------------------------------------
# Diagrama (v0.5 M1): item no inventário, lido na bancada
# ---------------------------------------------------------------------------
def test_read_diagram_spends_one_and_unlocks_forever():
    g = GameState(7)
    give(g, diagram_o2_tank=2)
    assert g.read_diagram("diagram_o2_tank", "t2") == "ok"          # v0.6 Fundo M5: o tanque se lê na Bancada T2
    assert g.inventory.count("diagram_o2_tank") == 1 and "o2_tank" in g.blueprints
    assert ("diagram_read", "o2_tank") in g.pop_events()
    give(g, iron_ingot=50, circuit=10)
    assert g.recipe_status("o2_tank") == "ok"


def test_read_repeated_diagram_does_not_spend():
    g = GameState(7)
    g.blueprints.add("scanner")
    give(g, diagram_scanner=1)
    assert g.read_diagram("diagram_scanner", "t2") == "known"
    assert g.inventory.count("diagram_scanner") == 1 and not g.pop_events()


def test_read_diagram_on_wrong_bench_or_without_it():
    g = GameState(7)
    give(g, diagram_o2_tank=1)
    assert g.read_diagram("diagram_o2_tank", "t1") == "wrong_bench"      # o tanque é da Bancada T2 (v0.6 Fundo M5)
    assert g.inventory.count("diagram_o2_tank") == 1 and "o2_tank" not in g.blueprints
    assert g.read_diagram("diagram_scanner", "t1") == "none"             # não tem
    assert g.read_diagram("iron", "t1") == "none"                        # nem é diagrama


def test_machine_diagram_reads_on_any_bench():
    g = GameState(7)
    give(g, diagram_lamp_t2=1)
    assert g.read_diagram("diagram_lamp_t2", "t2") == "ok" and "lamp_t2" in g.blueprints


def test_diagrams_held_lists_inventory_diagrams():
    g = GameState(7)
    assert g.diagrams_held() == []
    give(g, diagram_scanner=2, diagram_o2_tank=1)
    assert g.diagrams_held() == [("o2_tank", 1), ("scanner", 2)]


def test_diagram_names():
    from game.ui import item_name
    assert item_name("diagram_o2_tank") == "Diagrama: Tanque de O₂"
    assert all(f"diagram_{k}" in C.DIAGRAM_ITEMS for k in C.BLUEPRINTS)


def test_module_terminal_reads_from_below_footprint():
    g = GameState(seed=7)
    module = next(w for w in g.world.wrecks if w.kind == "module")
    rx, ry = module.reads_from
    assert g.world.is_floor(rx, ry)
    g.player.x, g.player.y = (rx + 0.5) * C.TILE, ry * C.TILE + 6       # pés logo abaixo da pegada
    assert g.wreck_terminal_distance(module) <= C.TERMINAL_REACH
    assert g.nearby_wreck_terminal() is module


def test_wreck_at_px_covers_the_sprite_above_the_footprint():
    world = generate_surface(7)
    module = next(w for w in world.wrecks if w.kind == "module")
    x, y, w, h = module.sprite_rect
    assert world.wreck_at_px(x + w / 2, y + 4) is module           # no teto do sprite (fora da pegada)
    assert world.wreck_at_px(x - 40, y - 40) is not module
