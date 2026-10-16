"""v0.7 M4: entrar e sair da VÉSPER-7, e as regras lá dentro."""

from game import config as C
from game import layers, save, vesper, wrecks
from game.systems import Controls, GameState

DT = 1 / 60


def run(state, seconds):
    for _ in range(int(seconds / DT) + 1):
        state.update(DT, Controls())


def at_hatch_in(state):
    w = wrecks.vesper_wreck(state.surface.world)
    state.player.x, state.player.y = (w.tx + 3.5) * C.TILE, (w.ty + 3) * C.TILE + 20
    return w


def test_enter_and_exit():
    state = GameState(3)
    w = at_hatch_in(state)
    assert state.interaction() == ("hatch_in", (w.tx + 3, w.ty + 2))
    assert state.start_hatch()
    run(state, C.RAMP_DURATION)
    assert state.layer == layers.VESPER and state.ramp is None
    assert (state.player.x, state.player.y) == vesper.arrival(state.world)
    assert state.interaction()[0] == "hatch_out"
    assert state.start_hatch()
    run(state, C.RAMP_DURATION)
    assert state.layer == layers.SURFACE
    assert (state.player.x, state.player.y) == state.surface_exit()


def test_trip_texts():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    assert state.ramp.text == "Entrando..."
    run(state, C.RAMP_DURATION)
    state.start_hatch()
    assert state.ramp.text == "Saindo..."


def test_no_build_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    tx, ty = state.player.tile
    assert not state.active.buildable
    assert not state.can_place("prop_table", (tx + 1, ty))


def test_fixture_texts():
    state = GameState(3)
    assert state.fixture_text("jammed_door") == "Porta emperrada · energizar a nave pode resolver"
    assert state.fixture_text("power_panel") == "Painel de energia · sem bateria"
    assert state.fixture_text("container_broken") == "Vazio. A tampa foi forçada por dentro."


def test_o2_drops_and_no_storm_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    state.storm = 1.0
    before = state.o2
    run(state, 2.0)
    assert state.o2 < before
    from game.systems import storm_level
    assert storm_level(state) == 0.0
    assert state.safe_point()[2] == "SAÍDA"


def test_save_inside_loads_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    crate = next(iter(state.active.crates.values()))
    crate.opened = True
    data = save.state_to_dict(state)
    back = save.state_from_dict(data)
    assert back.layer == layers.VESPER
    assert back.active.crates[crate.tile].opened


def test_save_mid_trip_lands_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    data = save.state_to_dict(state)
    back = save.state_from_dict(data)
    assert back.layer == layers.VESPER
    assert (back.player.x, back.player.y) == vesper.arrival(back.world)


def test_faint_inside_wakes_at_base():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    state.o2 = 0
    run(state, C.FAINT_DURATION + 0.5)
    assert state.layer == layers.SURFACE


def test_fixture_targets_and_reach():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    tile, kind = next((t, k) for t, k in state.world.fixtures.items() if k == "power_panel")
    px, py = (tile[0] + 0.5) * C.TILE, (tile[1] + 0.5) * C.TILE
    assert state.interactable_at(px, py) == ("fixture", tile)
    state.player.x, state.player.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 1) * C.TILE + 8
    assert state.in_reach("fixture", tile)
    assert state.interaction() == ("fixture", tile)
    state.player.y += 200
    assert not state.in_reach("fixture", tile)


def test_ambient_for_vesper():
    from game import audio
    assert audio.ambient_for("vesper", "dead", True, has_vesper=True) == "vesper"
    assert audio.ambient_for("vesper", "dead", True, has_vesper=False) == "cave"
