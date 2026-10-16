import random

from game import config as C
from game import layers, ruins
from game.world import World


def test_all_plans_load_and_are_rectangular():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        assert plan.key == key and plan.name
        assert len({len(row) for row in plan.grid}) == 1


def test_plan_letters_are_declared():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        used = {ch for row in plan.grid for ch in row} - set("#.D=~c ")
        assert used <= set(plan.machines) | set(plan.logs) | set(plan.props)


def test_terminals_have_floor_below_in_the_drawing():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for y, row in enumerate(plan.grid):
            for x, ch in enumerate(row):
                if ch in plan.logs:
                    assert plan.grid[y + 1][x] not in "# 123"


def test_transform_has_8_distinct_orientations_and_keeps_counts():
    grid = ruins.load_plan("camp").grid
    seen = set()
    for orient in range(8):
        out = ruins.transform(grid, orient)
        seen.add(tuple(out))
        assert sorted("".join(out)) == sorted("".join(grid))
    assert len(seen) == 8
    assert ruins.transform(grid, 0) == grid


def test_rotate_90_clockwise():
    assert ruins.transform(["ab", "cd"], 1) == ["ca", "db"]
    assert ruins.transform(["ab", "cd"], 4) == ["ba", "dc"]


def test_logs_7_to_18_are_used_once():
    used = sorted(i for key in ruins.PLAN_KEYS for i in ruins.load_plan(key).logs.values())
    assert used == list(range(7, 19))


# ---- Task 2: montagem, destruição e lugar no mapa --------------------------------------------------
def test_build_level0_always_passes_every_orientation():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            r = ruins.build(plan, orient, 0, random.Random(1))
            assert r is not None
            assert sorted(r.terminals.values()) == sorted(plan.logs.values())
            for (tx, ty) in r.terminals:
                assert r.grid[ty + 1][tx] in ".c" or r.grid[ty + 1][tx] in plan.machines


def test_same_seed_same_ruin():
    a, b = layers.make_surface(7).world, layers.make_surface(7).world
    assert [(r.key, r.tx, r.ty, r.grid) for r in a.ruins] == [(r.key, r.tx, r.ty, r.grid) for r in b.ruins]


def test_four_ruins_on_seeds_1_to_20():
    for seed in range(1, 21):
        surf = layers.make_surface(seed).world
        cave = World.generate(seed)
        assert {r.key for r in surf.ruins} == {"camp", "lab"}, seed
        assert {r.key for r in cave.ruins} == {"melters", "drill_post"}, seed


def test_camp_distance_and_lab_region():
    for seed in range(1, 11):
        w = layers.make_surface(seed).world
        camp = next(r for r in w.ruins if r.key == "camp")
        kx, ky = w.crater
        d = ((camp.center[0] - kx - 1.5) ** 2 + (camp.center[1] - ky - 1.5) ** 2) ** 0.5
        assert 30 <= d <= 75
        lab = next(r for r in w.ruins if r.key == "lab")
        assert all(w.geo.region_at(*t) == 3 for t in lab.tiles)       # FROST


def test_cave_ruins_are_inside_hard_rock_region():
    from game.geo import BASALT, FROST
    for seed in range(1, 6):
        w = World.generate(seed)
        for r in w.ruins:
            want = FROST if r.key == "melters" else BASALT
            assert all(int(w.cave_region[y, x]) == want for x, y in r.tiles)
            x0, y0 = r.tx - 1, r.ty - 1                                # a borda logo fora é rocha (dura ou destruição)
            assert w.get(x0, y0) in C.SOLID_TILES


def test_ruin_tiles_and_crate_tile():
    w = layers.make_surface(3).world
    for r in w.ruins:
        assert set(r.tiles) <= w.ruin_tiles
        assert w.get(*r.crate) == C.LOOT_CRATE


# ---- Task 3: os objetos (casca, máquinas quebradas, caixa, terminais) -------------------------------
def _state_at_ruin(seed=3, key="camp"):
    from game import save
    s = save.new_state(seed)
    r = next(r for r in s.world.ruins if r.key == key)
    return s, r


def test_overlays_add_walls_and_broken_machines():
    s, r = _state_at_ruin()
    assert [b for b in s.base.blocks if b.ruin]
    broken = [m for m in s.machines if m.broken]
    assert {(m.tx, m.ty) for m in broken} == {t for ru in s.world.ruins for t in ru.machines}   # camp e lab
    assert all(m not in s.working_machines for m in broken)


def test_apply_overlays_is_idempotent():
    s, _ = _state_at_ruin()
    n_blocks, n_machines = len(s.base.blocks), len(s.machines)
    ruins.apply_overlays(s.active)
    assert (len(s.base.blocks), len(s.machines)) == (n_blocks, n_machines)


def test_ruin_wall_cannot_be_dismantled_and_blocks_building():
    s, r = _state_at_ruin()
    wall = next(b for b in s.base.blocks if b.ruin and b.is_wall)
    s.player.x, s.player.y = (wall.tx + 0.5) * C.TILE, (wall.ty + 2) * C.TILE
    assert not s.can_dismantle(wall)
    floor = next(t for t, b in s.base.cells.items() if b.ruin and b.is_floor and t not in r.machines and t != r.crate)
    s.player.x, s.player.y = (floor[0] + 0.5) * C.TILE, (floor[1] + 3.5) * C.TILE
    assert not s.can_place("lamp", floor)
    assert not s.can_place(C.BASE_WALL, floor)


def test_broken_machine_does_nothing_and_salvages_once():
    s, r = _state_at_ruin()
    m = next(m for m in s.machines if m.broken)
    s.player.x, s.player.y = (m.tx + 0.5) * C.TILE, (m.ty + 2) * C.TILE
    assert s.interactable_at(*m.anchor) is None
    assert s.dismantle_returns(m) == C.RUIN_SALVAGE[m.kind]
    before = s.inventory.count("iron")
    assert s.dismantle(m)
    assert s.inventory.count("iron") == before + C.RUIN_SALVAGE[m.kind].get("iron", 0)
    assert (m.tx, m.ty) in s.active.ruin_salvaged
    ruins.apply_overlays(s.active)
    assert all((x.tx, x.ty) != (m.tx, m.ty) for x in s.machines)


def test_broken_machines_give_no_index_or_power():
    s, _ = _state_at_ruin()
    assert s.ti_rate == 0 and s.working_machines == []
    assert s.power.consumption == 0


def test_ruin_crate_has_loot_and_terminals_are_readable():
    s, r = _state_at_ruin()
    crate = s.crates[r.crate]
    assert not crate.empty
    tile, log = next(iter(r.terminals.items()))
    s.player.x, s.player.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 1.4) * C.TILE
    assert s.in_reach("ruin_log", tile)
    assert s.interactable_at((tile[0] + 0.5) * C.TILE, (tile[1] + 0.7) * C.TILE) == ("ruin_log", tile)
    assert s.interaction() == ("ruin_log", tile)


def test_ruin_crate_dismantle_leaves_floor_of_the_layer():
    from game import save
    s = save.new_state(3)
    s.enter_layer("cave")
    r = next(r for r in s.world.ruins if r.key == "melters")
    crate = s.crates[r.crate]
    crate.storage.clear()
    s.player.x, s.player.y = (r.crate[0] + 0.5) * C.TILE, (r.crate[1] + 1.2) * C.TILE
    assert s.dismantle(crate)
    assert s.world.get(*r.crate) == C.FLOOR


def test_rocks_never_respawn_inside_a_ruin():
    from game import rock_respawn
    w = layers.make_surface(3).world
    assert not any(rock_respawn.can_spawn(w, *t) for t in w.ruin_tiles)


# ---- Task 4: save -----------------------------------------------------------------------------------
def test_save_roundtrip_keeps_ruins_and_salvage():
    import json
    from game import save
    s = save.new_state(3)
    m = next(m for m in s.machines if m.broken)
    s.player.x, s.player.y = (m.tx + 0.5) * 32, (m.ty + 2) * 32
    assert s.dismantle(m)
    data = save.state_to_dict(s)
    surf = data["layers"]["surface"]
    assert all(d["tx"] != m.tx or d["ty"] != m.ty for d in surf["machines"])
    assert surf["machines"] == []                                  # nenhuma quebrada vai no save
    assert surf["ruin_salvaged"] == [[m.tx, m.ty]]
    assert all(not d.get("ruin") for d in surf.get("base", []))
    t = save.state_from_dict(json.loads(json.dumps(data)))
    assert (m.tx, m.ty) not in {(x.tx, x.ty) for x in t.machines if x.broken}
    assert len([x for x in t.machines if x.broken]) == len([x for x in s.machines if x.broken])
    assert len([b for b in t.base.blocks if b.ruin]) == len([b for b in s.base.blocks if b.ruin])
    assert t.active.ruins_off == set()


# ---- Task 5: LOGs, E e mapa -------------------------------------------------------------------------
def test_logs_7_to_18():
    assert len(C.LOGS) == len(C.LOG_DAYS) == len(C.LOG_TITLES) == 19
    for i, text in enumerate(C.LOGS):
        assert text.startswith(f"Dia {C.LOG_DAYS[i]}."), i
        assert "→" not in text
    assert C.LOG_ORDER[0] == 7                                      # Dia 1 é o primeiro da história
    assert C.LOG_DAYS[7:] == [1, 9, 22, 120, 152, 175, 198, 205, 219, 61, 209, 224]


def test_map_shows_ruin_after_seen_and_names_it_after_reading():
    from game import map_view, save
    s = save.new_state(3)
    r = next(r for r in s.world.ruins if r.key == "lab")
    assert not [e for e in map_view.map_entries(s, "surface") if e.category == "ruin"]
    for x, y in r.tiles:
        s.active.explored.reveal_rect(x, y, 0, 0)
    e = next(e for e in map_view.map_entries(s, "surface") if e.category == "ruin")
    assert e.title == "Ruína"
    s.logs_read.add(next(iter(r.terminals.values())))
    e = next(e for e in map_view.map_entries(s, "surface") if e.category == "ruin")
    assert e.title == "Laboratório da Ilves"
    assert "ruin" in map_view.FILTERS and "ruin" in map_view.PRIORITY and "ruin" in map_view.DRAW_ORDER


def test_reading_a_ruin_terminal_counts_as_log():
    s, r = _state_at_ruin()
    tile, log = next(iter(r.terminals.items()))
    s.read_log(log)
    assert log in s.logs_read


def test_save_without_changes_has_no_ruin_field():
    from game import save
    s = save.new_state(3)
    assert "ruin_salvaged" not in save.state_to_dict(s)["layers"]["surface"]


def test_old_save_with_player_machine_on_footprint_skips_that_ruin():
    from game import save
    s = save.new_state(3)
    r = next(r for r in s.world.ruins if r.key == "camp")
    data = save.state_to_dict(s)
    x, y = next(t for t in r.tiles if t != r.crate and t not in r.machines)
    data["layers"]["surface"]["machines"].append({"kind": "lamp", "tx": x, "ty": y, "rotation": 0})
    t = save.state_from_dict(data)
    assert "camp" in t.active.ruins_off
    assert not any(b.ruin and (b.tx, b.ty) in set(r.tiles) for b in t.base.blocks)
    assert r.crate not in t.crates and t.world.get(*r.crate) != C.LOOT_CRATE
    assert any(b.ruin for b in t.base.blocks)                      # o laboratório continua inteiro


def test_opened_ruin_crate_survives_the_roundtrip():
    import json
    from game import save
    s = save.new_state(3)
    r = next(r for r in s.world.ruins if r.key == "camp")
    crate = s.crates[r.crate]
    crate.storage.clear()
    crate.opened = True
    t = save.state_from_dict(json.loads(json.dumps(save.state_to_dict(s))))
    assert t.crates[r.crate].opened and t.crates[r.crate].empty


# ---- v0.7 M2 · Task 2: props nas plantas ------------------------------------------------------------
def test_planta_le_props():
    plans = [ruins.load_plan(k) for k in ruins.PLAN_KEYS]
    for p in plans:
        assert p.props, p.key
        assert all(k in C.PROPS for k in p.props.values())
        assert not set(p.props) & set(p.machines)
    seen = {k for p in plans for k in p.props.values()}
    scannable = {k for k, t in C.PROPS.items() if t.scannable}
    assert scannable <= seen


def test_props_validos_em_toda_orientacao():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            for level in C.RUIN_DAMAGE_LEVELS:
                ruin = ruins.build(plan, orient, level, random.Random(orient * 10 + level))
                if ruin is None:
                    continue
                for (x, y), kind in ruin.props.items():
                    assert ruins.ok_in_plan(ruin.grid, x, y, kind), (key, orient, (x, y), kind)
                    if C.PROPS[kind].place == "face":
                        assert ruin.grid[y][x] == "#", (key, orient)     # a parede com quadro não caiu
                    else:
                        assert ruin.grid[y][x] == ".", (key, orient)


def test_destruicao_nao_derruba_parede_de_face_nem_de_mesa():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            ruin = ruins.build(plan, orient, 0, random.Random(1))
            if ruin is None:
                continue
            for seed in range(30):
                hit = ruins.build(plan, orient, 3, random.Random(seed))
                if hit is None:
                    continue
                for (x, y), kind in ruin.props.items():
                    if C.PROPS[kind].place == "face":
                        assert hit.grid[y][x] == "#"


def test_cadeira_so_tomba_com_destruicao():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            ruin = ruins.build(plan, orient, 0, random.Random(1))
            assert "prop_chair_fallen" not in ruin.props.values()
    plan = ruins.load_plan("camp")
    tombou = {k for seed in range(40) for k in ruins.build(plan, 0, 1, random.Random(seed)).props.values()}
    assert "prop_chair_fallen" in tombou and "prop_chair" in tombou


def test_nivel_0_passa_com_props_em_toda_orientacao():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            ruin = ruins.build(plan, orient, 0, random.Random(5))
            assert ruin is not None and ruin.props, (key, orient)


def test_mesma_seed_mesmos_props():
    a = {t: p.kind for t, p in layers.make_surface(7).props.items()}
    b = {t: p.kind for t, p in layers.make_surface(7).props.items()}
    assert a == b and a
    assert all(p.ruin for p in layers.make_surface(7).props.values())
    cave = layers.make_cave(7)
    assert cave.props and all(p.ruin for p in cave.props.values())


def test_props_de_ruina_so_dentro_da_pegada_e_apply_overlays_idempotente():
    layer = layers.make_surface(7)
    foot = layer.world.ruin_tiles
    assert all(t in foot for t in layer.props)
    before = {t: p.kind for t, p in layer.props.items()}
    ruins.apply_overlays(layer)
    assert {t: p.kind for t, p in layer.props.items()} == before


def test_ruina_desligada_nao_ganha_props():
    from game import save
    s = save.new_state(3)
    r = next(r for r in s.world.ruins if r.key == "camp")
    data = save.state_to_dict(s)
    x, y = next(t for t in r.tiles if t != r.crate and t not in r.machines and t not in r.props)
    data["layers"]["surface"]["machines"].append({"kind": "lamp", "tx": x, "ty": y, "rotation": 0})
    t = save.state_from_dict(data)
    assert "camp" in t.active.ruins_off
    assert not any(tile in t.active.props for tile in r.props)
    assert any(tile in t.active.props for ru in t.world.ruins if ru.key == "lab" for tile in ru.props)


def test_prop_de_chao_e_decal_nunca_somem_na_rotacao():
    """Decisão do dono: prop de chão/decal fica mesmo colado numa parede ao sul (a face cobre a parte de baixo)."""
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        want = sum(C.PROPS[k].place in ("floor", "decal") for k in plan.props.values())
        for orient in range(8):
            ruin = ruins.build(plan, orient, 0, random.Random(1))
            got = sum(C.PROPS[k].place in ("floor", "decal") for k in ruin.props.values())
            assert got == want, (key, orient)


def test_ok_in_plan_chao_aceita_parede_ao_sul():
    assert ruins.ok_in_plan(["...", ".#.", "###"], 1, 1 - 1, "prop_barrel") is True   # parede logo abaixo
    assert ruins.ok_in_plan(["#.#"], 0, 0, "prop_barrel") is False                    # tile de parede não é chão
