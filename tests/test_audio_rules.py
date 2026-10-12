"""Regras puras do áudio (não abrem mixer nem placa de som)."""

from array import array

from game import config as C
from game.audio import HUM_MAX_VOLUME, alarm_should_play, hum_volume, resample


def test_volume_table():
    v = C.VOLUME
    assert v["o2_low"] >= 0.6                         # alarme precisa continuar audível
    assert v["footstep_0"] <= 0.35 and v["footstep_1"] <= 0.35
    assert v["mine_break"] <= 0.5 and v["mine_hit"] <= 0.5
    assert C.AMBIENT_VOLUME == 0.7                    # o dono gostou do ambiente: não mexer
    assert all(0 <= x <= 1 for x in v.values())


def test_alarm_hysteresis():
    assert alarm_should_play(False, 24.9)
    assert not alarm_should_play(False, 25.5)   # desligado e acima de 25: continua desligado
    assert alarm_should_play(True, 26.0)        # ligado: só desliga em 27
    assert not alarm_should_play(True, 27.0)


def test_hum_volume_by_distance():
    assert hum_volume(None) == 0
    assert hum_volume(1.0) == HUM_MAX_VOLUME
    assert hum_volume(2.0) == HUM_MAX_VOLUME
    assert 0 < hum_volume(5.0) < HUM_MAX_VOLUME
    assert hum_volume(8.0) == 0
    assert hum_volume(20.0) == 0


def test_resample_changes_length_and_keeps_channels():
    stereo = array("h", [i % 100 for i in range(2000)])   # 1000 quadros × 2 canais
    faster = resample(stereo, 2, 1.25)
    slower = resample(stereo, 2, 0.8)
    assert len(faster) == 2 * 800
    assert len(slower) == 2 * 1250
    assert resample(stereo, 2, 1.0) == stereo


def test_drill_loop_volume_by_distance():
    from game.audio import drill_loop_volume
    top = C.VOLUME["drill_loop"]
    assert top == 0.5
    assert drill_loop_volume(1) == top and drill_loop_volume(2) == top
    assert 0 < drill_loop_volume(5) < top
    assert drill_loop_volume(8) == 0 and drill_loop_volume(30) == 0


def test_drill_sfx_volumes_from_sound_tips():
    assert C.VOLUME["drill_collect"] == 1.0
    assert 0.6 <= C.VOLUME["drill_full"] <= 0.8


def test_drone_and_solar_volumes_by_distance():
    from game.audio import drone_deliver_gain, drone_loop_volume, solar_hum_volume
    assert C.VOLUME["drone_loop"] == 0.5 and C.VOLUME["drone_deliver"] == 0.8 and C.VOLUME["solar_hum"] == 0.5
    assert drone_loop_volume(0) == drone_loop_volume(3) == 0.5        # cheio até 3 tiles
    assert 0 < drone_loop_volume(6) < 0.5
    assert drone_loop_volume(10) == 0 and drone_loop_volume(25) == 0  # some a partir de 10
    assert drone_deliver_gain(2) == 1 and 0 < drone_deliver_gain(7) < 1 and drone_deliver_gain(15) == 0
    assert solar_hum_volume(None) == 0
    assert solar_hum_volume(2) == 0.5 and 0 < solar_hum_volume(4) < 0.5 and solar_hum_volume(6) == 0


def test_desert_wind_volume_follows_ramp_ducking_and_sliders():
    import pytest
    from game import config as C
    from game.audio import AMBIENT_VOLUME, wind_volume
    full = AMBIENT_VOLUME                                   # ambient_gain com os sliders em 100%
    assert wind_volume(1.0, 1.0, full) == pytest.approx(C.DESERT_WIND_VOLUME)
    assert wind_volume(0.0, 1.0, full) == 0.0               # na caverna: rampa em 0
    assert wind_volume(1.0, 0.0, full) == 0.0               # desmaio: cai junto com o ambiente
    assert wind_volume(1.0, 1.0, full * 0.5) == pytest.approx(C.DESERT_WIND_VOLUME * 0.5)
