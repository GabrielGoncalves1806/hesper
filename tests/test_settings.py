"""settings.json: volumes, tela cheia e zoom persistem, e arquivo ausente/estragado não quebra o jogo."""

from game import settings


def test_missing_file_uses_defaults(tmp_path):
    assert settings.load(tmp_path / "nao_existe.json") == settings.DEFAULTS


def test_corrupted_file_uses_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{isso não é json", encoding="utf-8")
    assert settings.load(path) == settings.DEFAULTS
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert settings.load(path) == settings.DEFAULTS


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    values = {"master": 0.5, "sfx": 0.3, "ambient": 0.9, "fullscreen": True, "zoom": 1.5}
    settings.save(values, path)
    assert settings.load(path) == values


def test_values_are_clamped_and_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"master": 7, "sfx": -1, "ambient": "alto", "hack": 1}', encoding="utf-8")
    assert settings.load(path) == {**settings.DEFAULTS, "master": 1.0, "sfx": 0.0, "ambient": 1.0}


def test_old_file_without_display_keys_gets_defaults(tmp_path):
    """settings.json de antes (só volumes): tela cheia desligada e zoom 1×."""
    path = tmp_path / "settings.json"
    path.write_text('{"master": 1.0, "sfx": 0.15, "ambient": 0.3}', encoding="utf-8")
    loaded = settings.load(path)
    assert loaded["fullscreen"] is False and loaded["zoom"] == 1.0
    assert settings.mix(loaded) == {"master": 1.0, "sfx": 0.15, "ambient": 0.3}


def test_invalid_display_values_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"fullscreen": 1, "zoom": 3.7}', encoding="utf-8")       # 1 não é bool; 3.7 não é nível
    assert settings.load(path) == settings.DEFAULTS
    path.write_text('{"fullscreen": true, "zoom": 2}', encoding="utf-8")      # inteiro de um nível vale
    loaded = settings.load(path)
    assert loaded["fullscreen"] is True and loaded["zoom"] == 2.0
