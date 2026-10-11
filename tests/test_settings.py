"""settings.json: volumes persistem, e arquivo ausente/estragado não quebra o jogo."""

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
    settings.save({"master": 0.5, "sfx": 0.3, "ambient": 0.9}, path)
    assert settings.load(path) == {"master": 0.5, "sfx": 0.3, "ambient": 0.9}


def test_values_are_clamped_and_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"master": 7, "sfx": -1, "ambient": "alto", "hack": 1}', encoding="utf-8")
    assert settings.load(path) == {"master": 1.0, "sfx": 0.0, "ambient": 1.0}
