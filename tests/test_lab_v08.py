"""v0.8 M3: o laboratório da Ilves trancado no gelo, o tanque quebrado que dá o Cultivador e a alga."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from game import config as C
from game import ice_blocks, ruins, thaw
from game.systems import GameState

T = C.TILE
SEEDS = (1, 7, 42, 2024)


def new_game(seed: int) -> GameState:
    g = GameState(seed, rng=random.Random(1))
    assert ruins.lab_of(g.world) is not None, f"seed {seed} sem laboratório"
    return g


def set_heat(g: GameState, heat: float) -> None:
    g.indices["heat"] = heat
    g._apply_thaw()


# ---------------------------------------------------------------- Task 1: o gelo da porta
def test_lab_ice_progress():
    lo, hi = C.LAB_ICE_HEAT
    assert thaw.lab_ice_progress(lo - 1) == 0.0 and thaw.lab_ice_progress(hi) == 1.0
    assert thaw.lab_ice_progress((lo + hi) / 2) == pytest.approx(0.5)


def test_lab_orients_are_the_ones_with_the_door_at_the_bottom():
    assert ruins.LAB_ORIENTS == (0, 4)


@pytest.mark.parametrize("seed", SEEDS)
def test_lab_door_faces_south_and_walls_never_fall(seed):
    g = new_game(seed)
    lab = ruins.lab_of(g.world)
    assert lab.orient in ruins.LAB_ORIENTS and lab.level in ruins.LAB_DAMAGE_LEVELS
    door = ruins.lab_door_tiles(g.world)
    assert len(door) == 2 and door[0][1] == door[1][1] == lab.ty + len(lab.grid) - 1
    cx, cy = ruins.lab_door_px(g.world)
    assert cx == (min(x for x, _ in door) + 1) * T and cy == (door[0][1] + 1) * T
    assert not any(ch == "x" and "#" in (lab.grid[y][max(x - 1, 0)], lab.grid[y][min(x + 1, 12)]) and y == 0
                   for y, row in enumerate(lab.grid) for x, ch in enumerate(row))   # sem parede caída na casca de cima


def test_no_lab_no_door():
    class Empty:
        ruins = []
    assert ruins.lab_door_px(Empty()) is None and ruins.lab_door_tiles(Empty()) == []


@pytest.mark.parametrize("seed", SEEDS)
def test_lab_is_closed_until_the_heat_opens_it(seed):
    g = new_game(seed)
    layer = g.active
    assert layer.lab_ice_open is False and layer.lab_ice_p == 0.0
    assert [b for b in layer.gate_blocks if b.gate == ice_blocks.LAB_GATE]
    assert set(ruins.lab_door_tiles(g.world)) <= set(g.world.closed_gate_tiles)
    set_heat(g, C.LAB_ICE_HEAT[0] - 1)
    assert layer.lab_ice_open is False and ("lab_ice_open",) not in g.events
    set_heat(g, C.LAB_ICE_HEAT[1])
    assert layer.lab_ice_open is True and layer.lab_ice_p == 1.0
    assert g.events.count(("lab_ice_open",)) == 1
    assert not [b for b in layer.gate_blocks if b.gate == ice_blocks.LAB_GATE]
    assert not set(ruins.lab_door_tiles(g.world)) & set(g.world.closed_gate_tiles)
    set_heat(g, C.LAB_ICE_HEAT[1] + 500)
    assert g.events.count(("lab_ice_open",)) == 1                          # uma vez só


def lab_rects(g: GameState):
    """O que bate na caixa do player em volta da porta: os blocos do gelo, as paredes e as máquinas do laboratório."""
    bx, by = ruins.lab_door_px(g.world)
    return [(x - bx, y - by, w, h) for x, y, w, h in g.active.gate_solids] + list(ruins.lab_blockers(g.world))


@pytest.mark.parametrize("seed", SEEDS)
def test_the_player_only_passes_the_lab_door_when_the_ice_opens(seed):
    g = new_game(seed)
    corridor = ice_blocks.LAB_CORRIDOR
    set_heat(g, C.LAB_ICE_HEAT[0] - 1)
    assert not ice_blocks.passable(lab_rects(g), walls=False, corridor=corridor)
    assert not ice_blocks.path_through(lab_rects(g), walls=False, corridor=corridor)
    set_heat(g, C.LAB_ICE_HEAT[1])
    assert ice_blocks.path_through(lab_rects(g), walls=False, corridor=corridor)


def test_the_gap_opens_in_the_middle_of_the_melt_and_the_player_walks_it():
    g = new_game(7)
    lo, hi = C.LAB_ICE_HEAT
    opens = g.active.lab_ice_opens_at
    assert 0.3 < opens < 1.0
    set_heat(g, lo + (hi - lo) * (opens - 0.001))
    assert not g.active.lab_ice_open
    set_heat(g, lo + (hi - lo) * opens)
    assert g.active.lab_ice_open and 0 < g.active.lab_ice_p < 1
    bx, by = ruins.lab_door_px(g.world)
    path = ice_blocks.path_through(lab_rects(g), walls=False, corridor=ice_blocks.LAB_CORRIDOR)
    assert path
    for door in g.active.base.door_list:                                    # a porta do lab abre quando o player chega perto
        door.frame = C.DOOR_FRAMES - 1
    g.player.x, g.player.y = bx + path[0][0], by + path[0][1]
    dt = 1.0 / C.PLAYER_SPEED
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        g.player.move(x1 - x0, y1 - y0, dt, g.solids_near)
        assert abs(g.player.x - (bx + x1)) < 1e-6 and abs(g.player.y - (by + y1)) < 1e-6, (x1, y1)
        g.player.x, g.player.y = bx + x1, by + y1
    assert g.player.y < by - T // 2                                         # entrou no laboratório


def test_the_lab_ice_is_rebuilt_from_the_heat_after_a_load():
    g = new_game(7)
    set_heat(g, (C.LAB_ICE_HEAT[0] + C.LAB_ICE_HEAT[1]) / 2)
    p = g.active.lab_ice_p
    h = new_game(7)
    h.indices["heat"] = g.indices["heat"]
    h._apply_thaw()
    assert h.active.lab_ice_p == pytest.approx(p) and h.active.lab_ice_open == g.active.lab_ice_open


# ---------------------------------------------------------------- Task 2: o tanque quebrado dá o Cultivador
def lab_prop(g: GameState, kind: str):
    """O prop `kind` da planta do laboratório, com o player parado 2 tiles abaixo dele."""
    prop = next(p for p in g.active.props.values() if p.kind == kind and p.ruin)
    g.player.x, g.player.y = (prop.tx + 0.5) * C.TILE, (prop.ty + 2) * C.TILE + 16
    return prop


def hold_scan(g: GameState, prop) -> None:
    for _ in range(int(C.SCAN_HOLD / 0.1) + 2):
        g._update_scan(prop, 0.1)


def test_scanning_the_tank_unlocks_the_cultivator_recipe():
    g = new_game(7)
    assert g.recipe_status(C.CULTIVATOR) == "blueprint"
    tank = lab_prop(g, "prop_sample_tank")
    assert g.can_scan(tank)
    hold_scan(g, tank)
    assert C.CULTIVATOR in g.blueprints
    assert "prop_sample_tank" not in g.scanned                         # não vira decoração
    assert ("scan_done", C.CULTIVATOR) in g.events
    assert g.recipe_status(C.CULTIVATOR) != "blueprint"
    assert not g.can_scan(tank)                                         # e não escaneia de novo


def test_microscope_is_not_scannable_yet():
    g = new_game(7)
    mic = lab_prop(g, "prop_microscope_digital")
    assert g.can_scan(mic) is False
    hold_scan(g, mic)
    assert not g.blueprints and "prop_microscope_digital" not in g.scanned


def test_lab_machine_props_are_not_player_decor():
    for kind in C.PROP_MACHINE_ART:
        assert kind not in C.PLAYER_PROPS and kind in C.PROPS
    assert C.SCAN_BLUEPRINT == {"prop_sample_tank": C.CULTIVATOR}
    assert C.BLUEPRINTS[C.CULTIVATOR] == "Cultivador" and C.CULTIVATOR not in C.WRECK_DIAGRAMS


# ---------------------------------------------------------------- Task 3: a cultura-controle na caixa do lab
@pytest.mark.parametrize("seed", SEEDS)
def test_lab_crate_always_has_the_algae(seed):
    g = new_game(seed)
    crate = g.active.crates[ruins.lab_of(g.world).crate]
    assert crate.storage.count("algae") == 1


def test_other_ruin_crates_have_no_algae():
    g = new_game(7)
    lab = ruins.lab_of(g.world)
    others = [c for t, c in g.active.crates.items() if t != lab.crate]
    assert all(c.storage.count("algae") == 0 for c in others)


def test_crop_items_exist_and_are_logistic():
    names = {"algae": "Alga", "plant_1": "Folha-gota", "plant_2": "Espiral-de-geada", "plant_3": "Lírio-de-Ilves"}
    for item, name in names.items():
        t = C.MACHINES[item]
        assert t.name == name and not t.placeable and t.sprite == f"icon_{item}"
        assert item in C.LOGISTIC_ITEMS and C.RESOURCE_NAME[item] and C.ORE_COLORS[item]
    from game.inventory import max_stack
    assert max_stack("algae") == C.STACK_LOOT
    assert C.MACHINES["algae"].desc == "cultura-controle da Ilves"
