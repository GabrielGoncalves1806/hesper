"""Regras puras do áudio (não abrem mixer nem placa de som)."""

from array import array

from game import config as C
from game.audio import HUM_MAX_VOLUME, alarm_should_play, hum_volume, resample


def test_audio_and_sprites_flags():
    assert C.ENABLE_AUDIO is True       # som v3 aprovado
    assert C.ENABLE_SPRITES is True     # sprites v2 aprovados


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
