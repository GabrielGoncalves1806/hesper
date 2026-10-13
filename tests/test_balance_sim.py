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
    # meta do v0.2: ~25 min (20 a 35). v0.3 Marco 1: só a superfície (pouco minério de propósito, a
    # caverna vem no Marco 2), então a partida fica mais lenta: o casual da proposta passa de ~33 pra ~43 min.
    # Teto provisório de 50 min até o Marco 2/4 (referência do v0.3: 25–40 min).
    # Rochas reaparecendo no lugar dos soltos: a média do casual em 5 seeds caiu de 52,2 pra 48,3 min, mas a
    # seed 1 sozinha oscila (48,1 -> 50,5; com reaparecimento a cada 12 s ela dá 39,8 e a cada 20 s, 50,5).
    # O teto ganhou 2 min de folga pra esse ruído de uma seed só.
    ceiling = 52
    assert 20 * 60 <= r.total <= ceiling * 60
    # Névoa por volta dos 10–12 min. Marco 2: quem só minera na caverna começa mais devagar (não pega rocha da
    # superfície e cada viagem paga ~20 tiles de rampa: base -> cratera -> fade), ~14 min na proposta.
    cave = strategy in ("caverna", "destrocos")     # Marco 3: "destrocos" = caverna + nave mais perto (tanque)
    nevoa_max = 15 if cave else 13
    assert 9 * 60 <= r.milestones["Névoa"] <= nevoa_max * 60
    # nenhuma espera longa no meio do jogo; a da reta final ("o fim chega antes da próxima máquina") é o
    # jogador esperando o Ti fechar: no Marco 1 (superfície) chega a ~3 min, na caverna (proposta) a ~5 min
    # Marco 3: os destroços mudaram o deserto (área sólida + folga sem rocha pequena) e o guloso da seed 1 passou
    # a fechar com ~10 min de espera final (ele decide que nenhuma máquina nova fica pronta antes do fim; o total
    # continua dentro do teto). Teto da espera final: 11 min; espera no MEIO do jogo continua ≤ 2,5 min.
    end_wait = r.idle_longest_reason == "fim chega antes da próxima máquina"
    assert r.idle_longest <= ((6 if cave else 11) if end_wait else 2.5) * 60
    assert sum(r.machines[k] for k in ("o2_t2", "melter_t2", "heater_t2")) > 0


def test_destrocos_pega_o_tanque_cedo(proposal):
    """Marco 3: a estratégia "destrocos" equipa o tanque no primeiro minuto e saqueia a nave mais perto."""
    r = sim.simulate("destrocos", seed=1, overrides=proposal)
    assert r.tank_at is not None and r.tank_at < 90
    assert r.loot_units >= 25 and r.finished


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


def test_estrategia_caverna_minera_la_embaixo():
    """Marco 2: a estratégia "caverna" minera na caverna (drills nos veios de lá, sem drones, sem rochas da superfície) e
    fecha a partida na referência do v0.3 (25–40 min) com os números atuais."""
    sim_ = sim.Sim(sim.STRATEGIES["caverna"], seed=1)
    r = sim_.run()
    assert r.finished and 25 * 60 <= r.total <= 40 * 60
    cave = sim_.gs.layers["cave"]
    assert sum(m.is_drill for m in cave.machines) == 3 and not any(m.is_drill for m in sim_.gs.surface.machines)
    assert r.drill_units > 0 and r.drone_units == 0 and r.faints == 0
    assert sim_.ramp_k > 15                       # a viagem até a caverna custa (cratera a 15–20 tiles)
