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
    values = {"master": 0.5, "sfx": 0.3, "ambient": 0.9, "fullscreen": True, "zoom": 1.5, "ui_size": "pequena",
              "map_zoom": 3, "map_hidden": ["wreck_empty", "machine"]}
    settings.save(values, path)
    assert settings.load(path) == values


def test_values_are_clamped_and_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"master": 7, "sfx": -1, "ambient": "alto", "hack": 1}', encoding="utf-8")
    assert settings.load(path) == {**settings.DEFAULTS, "master": 1.0, "sfx": 0.0}   # "alto" vira o padrão


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


def test_map_prefs_persist_and_bad_values_fall_back(tmp_path):
    """Mapa (M): último zoom e filtros escondidos são preferência do jogador (settings.json, não o save).
    Zoom fora de 1-4 e filtro desconhecido caem no padrão; arquivo antigo sem as chaves fica no padrão."""
    path = tmp_path / "settings.json"
    path.write_text('{"map_zoom": 4, "map_hidden": ["chest", "xyz", "chest", "base"]}', encoding="utf-8")
    loaded = settings.load(path)
    assert loaded["map_zoom"] == 4 and loaded["map_hidden"] == ["base", "chest"]
    path.write_text('{"map_zoom": 2.5, "map_hidden": "chest"}', encoding="utf-8")
    loaded = settings.load(path)
    assert loaded["map_zoom"] == 2 and loaded["map_hidden"] == []
    path.write_text('{"map_zoom": true}', encoding="utf-8")
    assert settings.load(path)["map_zoom"] == 2
    assert settings.DEFAULTS["map_zoom"] == 2 and settings.DEFAULTS["map_hidden"] == []


def test_default_volumes():
    """Quem nunca mexeu: master 100%, efeitos 40%, ambiente 50%."""
    assert settings.mix(settings.DEFAULTS) == {"master": 1.0, "sfx": 0.4, "ambient": 0.5}
