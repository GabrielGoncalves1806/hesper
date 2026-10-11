"""Energia global sem fios (game/energy.py + GameState). Nada de pygame aqui."""

import random

import pytest

from game import config as C
from game.energy import PowerAlert, machine_gen, machine_use, power_report
from game.systems import GameState, Machine


@pytest.fixture
def game() -> GameState:
    return GameState(rng=random.Random(42))


def add(game: GameState, kind: str, tile: tuple[int, int]) -> Machine:
    """Põe a máquina direto no mundo (o teste é da energia, não do fabricador)."""
    machine = Machine(kind, *tile)
    game.machines.append(machine)
    return machine


# ---------------------------------------------------------------- produção e consumo
def test_consumption_table_matches_the_bible():
    expected = {"o2": 1, "melter": 1, "heater": 2, "o2_t2": 3, "melter_t2": 3, "heater_t2": 4,
                "drill": 2, "drone_station": 3}
    assert {k: machine_use(k) for k in expected} == expected
    assert machine_use("solar") == 0 and machine_use("chest") == 0     # painel e baú não consomem
    assert machine_gen("solar") == 3 and machine_gen("o2") == 0


def test_only_the_pod_at_the_start(game):
    power = game.power
    assert (power.production, power.consumption, power.factor) == (5, 0, 1.0)
    assert not power.deficit and power.level == "ok"


def test_production_and_consumption_add_up():
    power = power_report(["o2", "melter", "heater", "solar", "solar", "drill"])
    assert power.production == 5 + 3 + 3
    assert power.consumption == 1 + 1 + 2 + 2


# ---------------------------------------------------------------- fator
@pytest.mark.parametrize("kinds, factor", [
    (["o2", "melter", "heater"], 1.0),                 # 4 de 5 kW: sobra
    (["heater", "heater", "o2"], 1.0),                 # 5 de 5 kW: no limite, ainda 100%
    (["heater_t2", "o2"], 1.0),
    (["heater_t2", "heater"], 5 / 6),                  # 6 kW pra 5 de produção
    (["heater_t2", "heater_t2"], 5 / 8),
    (["heater_t2", "heater_t2", "solar"], 1.0),        # o painel resolve
])
def test_factor_is_production_over_consumption_capped_at_1(kinds, factor):
    assert power_report(kinds).factor == pytest.approx(factor)


def test_meter_colors():
    assert power_report(["o2"]).level == "ok"                    # 1 de 5
    assert power_report(["heater", "heater"]).level == "tight"   # 4 de 5 = 80%
    assert power_report(["heater_t2", "heater"]).level == "deficit"


# ---------------------------------------------------------------- déficit desacelera
def test_deficit_slows_down_ti(game):
    for i in range(4):
        add(game, "heater", (60 + i * 2, 66))          # 8 kW pra 5 de produção -> 62,5%
    assert game.power.factor == pytest.approx(5 / 8)
    full_rate = 4 * C.MACHINES["heater"].rate
    assert game.ti_rate == pytest.approx(full_rate * 5 / 8)
    game._update_machines(10)
    assert game.indices["heat"] == pytest.approx(full_rate * 10 * 5 / 8)


def test_no_total_shutdown_even_with_huge_deficit(game):
    for i in range(10):
        add(game, "heater_t2", (56 + i * 2, 66))       # 40 kW pra 5: fator 0,125, mas nunca 0
    game._update_machines(10)
    assert game.indices["heat"] > 0


def test_solar_panel_brings_the_rate_back(game):
    for i in range(4):
        add(game, "heater", (60 + i * 2, 66))
    add(game, "solar", (60, 68))
    assert game.power.factor == 1.0
    assert game.ti_rate == 4 * C.MACHINES["heater"].rate


def test_deficit_slows_down_drills(game):
    game.debug_add_ti()                                # Névoa
    drill = add(game, "drill", (10, 10))
    drill.resource = "iron"
    for i in range(2):
        add(game, "heater", (60 + i * 2, 66))          # 2 + 4 = 6 kW pra 5 de produção
    factor = game.power.factor
    assert factor == pytest.approx(5 / 6)
    game._update_machines(C.DRILL_INTERVAL * 6)        # no ritmo cheio daria 6 unidades
    assert drill.stored == int(6 * factor)             # 5 unidades
    add(game, "solar", (60, 68))
    drill.stored, drill.timer = 0, 0.0
    game._update_machines(C.DRILL_INTERVAL * 6)
    assert drill.stored == 6


# ---------------------------------------------------------------- aviso (histerese)
def test_alert_plays_once_when_deficit_starts():
    alert = PowerAlert()
    assert not alert.update(False, 1.0)
    assert alert.update(True, 0.016)                   # começou o déficit: toca
    assert not any(alert.update(True, 0.016) for _ in range(100))   # continua no déficit: não repete


def test_alert_does_not_flap_on_the_edge():
    alert = PowerAlert()
    assert alert.update(True, 0.016)
    assert not alert.update(False, C.ENERGY_REARM_TIME / 2)    # resolveu por pouco tempo...
    assert not alert.update(True, 0.016)                       # ...e voltou: não toca de novo
    assert not alert.update(False, C.ENERGY_REARM_TIME)        # agora ficou 5 s sem déficit: rearma
    assert alert.update(True, 0.016)                           # novo déficit: toca


def test_game_emits_power_low_event_once(game):
    add(game, "heater_t2", (60, 66))
    add(game, "heater", (62, 66))
    game._update_machines(0.016)
    game._update_machines(0.016)
    events = [e for e in game.pop_events() if e[0] == "power_low"]
    assert events == [("power_low",)]


# ---------------------------------------------------------------- painel solar
def test_solar_panel_recipe():
    panel = C.MACHINES["solar"]
    assert panel.cost == {"iron": 8, "silicon": 6}
    assert panel.unlock_ti == 0 and panel.size == 1 and panel.index is None
    assert panel.sprite == "solar_panel"
    assert "solar" in C.MACHINE_ORDER


def test_solar_panel_craft_place_dismantle(game):
    game.inventory.update(iron=8, silicon=6)
    assert game.recipe_status("solar") == "ok"
    assert game.craft("solar")
    px, py = game.player.tile
    assert game.place("solar", (px + 2, py))
    assert game.power.production == 8
    ti = game.ti
    game._update_machines(30)
    assert game.ti == ti                                # painel não soma Ti
    panel = game.machine_at((px + 2, py))
    assert game.dismantle(panel)
    assert game.machines_owned["solar"] == 1 and game.power.production == 5
