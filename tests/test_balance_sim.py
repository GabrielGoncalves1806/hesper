"""Testes leves do simulador de balanceamento (tools/dev/balance_sim.py). Sem pygame, sem janela."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dev"))

import balance_sim as sim  # noqa: E402

from game import config as C  # noqa: E402


@pytest.fixture(scope="module")
def proposal():
    return sim.load_overrides()


@pytest.mark.parametrize("strategy", list(sim.STRATEGIES))
def test_proposta_chega_no_fim_dentro_da_meta(proposal, strategy):
    r = sim.simulate(strategy, seed=1, overrides=proposal)
    assert r.finished
    assert set(r.milestones) == {"Ti 500", "Névoa", "Verde"}
    # meta: ~25 min (20 a 35 aceitável). Com o painel solar em 4 kW o casual da proposta fica em ~33 min.
    ceiling = 35
    assert 20 * 60 <= r.total <= ceiling * 60
    assert 9 * 60 <= r.milestones["Névoa"] <= 13 * 60     # Névoa por volta dos 10–12 min
    assert r.idle_longest <= 2.5 * 60                     # nenhuma espera longa
    assert sum(r.machines[k] for k in ("o2_t2", "melter_t2", "heater_t2")) > 0


def test_deterministico_com_seed_fixa(proposal):
    a = sim.simulate("casual", seed=7, overrides=proposal)
    b = sim.simulate("casual", seed=7, overrides=proposal)
    assert a == b


def test_overrides_nao_vazam_pro_config(proposal):
    before = (dict(C.MACHINES), list(C.STAGES), dict(C.MINE_TIME), C.PLAYER_SPEED)
    with sim.patched_config({**proposal, "PLAYER_SPEED": 999, "MINE_TIME": {"IRON": 9},
                             "STAGES": {"mist": 1, "green": 2}}):
        assert C.MACHINES["o2"].rate == proposal["MACHINES"]["o2"]["rate"]
        assert C.PLAYER_SPEED == 999 and C.MINE_TIME[C.IRON] == 9 and C.STAGES[1].ti == 1
    assert (dict(C.MACHINES), list(C.STAGES), dict(C.MINE_TIME), C.PLAYER_SPEED) == before


def test_desmaio_usa_a_regra_real_e_o_jogo_continua(proposal):
    afobado = sim.Strategy("afobado", pick="balanced", walk_factor=2.5, o2_margin=0.0)
    r = sim.simulate(afobado, seed=1, overrides=proposal)
    assert r.faints > 0
    assert r.finished
