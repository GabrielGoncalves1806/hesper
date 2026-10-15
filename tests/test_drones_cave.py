"""v0.6 M3: drones na caverna. Cada camada tem a sua rede e as duas rodam com o player em qualquer camada."""
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import drones, save  # noqa: E402
from game import layers  # noqa: E402
from game.layers import CAVE, SURFACE  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add_station(game, tile=(60, 70)) -> Machine:
    """Estação com 1 drone na camada ATIVA."""
    m = Machine("drone_station", *tile)
    m.station = drones.new_station(m, 1)
    game.machines.append(m)
    return m


def chests(game, a=(80, 70), b=(40, 70)) -> tuple[Machine, Machine]:
    """Baú que envia 10 ferro e baú que recebe ferro, na camada ATIVA."""
    src = Machine("chest_large", *a, sends={"iron"})
    src.storage.add("iron", 10)
    dst = Machine("chest_large", *b, receives={"iron"})
    game.machines += [src, dst]
    return src, dst


def run(game, seconds: float, step: float = 1 / 30) -> None:
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def test_station_can_be_placed_in_the_cave(game):
    game.enter_layer(CAVE)
    game.enter_layer(CAVE, layers.ramp_arrival(game.world))   # chegada real da rampa (o player padrão cai em parede)
    px, py = game.player.tile
    spots = [(px + dx, py + dy) for dx in range(-4, 5) for dy in range(-4, 5)]
    assert any(game.can_place("drone_station", t) for t in spots)


def test_drone_logistics_is_per_layer(game):
    surf_chest = Machine("chest", 70, 70)
    game.machines.append(surf_chest)
    game.enter_layer(CAVE)
    cave_chest = Machine("chest", 60, 60)
    game.machines.append(cave_chest)
    assert cave_chest in game.drone_logistics(CAVE) and surf_chest not in game.drone_logistics(CAVE)
    assert surf_chest in game.drone_logistics(SURFACE) and cave_chest not in game.drone_logistics(SURFACE)
    assert surf_chest in game.drone_logistics()            # padrão = superfície (testes do M2)


def test_cave_drones_work_with_the_player_on_the_surface(game):
    game.enter_layer(CAVE)
    add_station(game)
    src, dst = chests(game)
    game.enter_layer(SURFACE)
    run(game, 40)
    assert dst.storage.count("iron") == 10 and src.storage.count("iron") == 0


def test_surface_drones_work_with_the_player_in_the_cave(game):
    add_station(game)
    src, dst = chests(game)
    game.enter_layer(CAVE)
    run(game, 40)
    assert dst.storage.count("iron") == 10


def test_networks_never_mix(game):
    """Estação só na superfície; os baús da caverna ficam parados. E vice-versa."""
    add_station(game)
    game.enter_layer(CAVE)
    src, dst = chests(game)
    run(game, 40)
    assert dst.storage.count("iron") == 0 and src.storage.count("iron") == 10


def test_cave_station_never_takes_from_the_surface(game):
    surf_src, surf_dst = chests(game)
    game.enter_layer(CAVE)
    st = add_station(game)
    cave_dst = Machine("chest_large", 40, 70, receives={"iron"})
    game.machines.append(cave_dst)
    run(game, 40)
    assert surf_src.storage.count("iron") == 10 and cave_dst.storage.count("iron") == 0
    assert all(d.source is None for d in st.station.drones)


def test_power_deficit_slows_both_layers(game, monkeypatch):
    """Energia global: o mesmo work_dt (dt × fator) chega nas duas chamadas."""
    add_station(game)
    game.enter_layer(CAVE)
    add_station(game)
    seen = []
    monkeypatch.setattr(drones, "update_stations", lambda st, lg, dt, ev: seen.append(dt) or 0)
    game._update_machines(0.1)
    assert len(seen) == 2 and seen[0] == seen[1] == pytest.approx(0.1 * game.power.factor)


def test_stations_property_is_the_active_layer(game):
    """Desenho e som usam state.stations: só a camada do player."""
    surf = add_station(game)
    game.enter_layer(CAVE)
    cave = add_station(game, (50, 50))
    assert game.stations == [cave]
    game.enter_layer(SURFACE)
    assert game.stations == [surf]


def test_save_keeps_stations_and_flying_cargo_of_each_layer(game):
    surf = add_station(game)
    chests(game)
    game.enter_layer(CAVE)
    cave = add_station(game)
    src, dst = chests(game)
    run(game, 6)                                           # drone da caverna já pegou ferro e está voando
    flying = cave.station.drones[0]
    assert flying.in_air and flying.cargo > 0
    carried = flying.cargo
    loaded = save.state_from_dict(save.state_to_dict(game))
    l_cave = [m for m in loaded.layers[CAVE].machines if m.is_station]
    l_surf = [m for m in loaded.layers[SURFACE].machines if m.is_station]
    assert len(l_cave) == 1 and len(l_surf) == 1
    assert (l_cave[0].tx, l_cave[0].ty) == (cave.tx, cave.ty) and (l_surf[0].tx, l_surf[0].ty) == (surf.tx, surf.ty)
    assert l_cave[0].station.drones[0].cargo == carried    # volta pousado, com a carga (entrega no 1º frame)
    run(loaded, 40)
    l_dst = next(m for m in loaded.layers[CAVE].machines if m.is_chest and (m.tx, m.ty) == (dst.tx, dst.ty))
    assert l_dst.storage.count("iron") == 10               # nada some nem duplica no save no meio do voo
