"""Preferências do jogador que sobrevivem entre sessões: volumes, tela cheia, zoom, tamanho da interface e o
mapa (M): filtros escondidos (map_hidden) e último zoom do mapa (map_zoom). Valem pra qualquer save e não
entram no save do jogo; a posição da câmera do mapa não é guardada (ele sempre abre em você).

Fica num settings.json na raiz do projeto (no .gitignore). Se o arquivo não existir
ou estiver estragado, usa o padrão e segue o jogo sem reclamar.
"""

import json
from pathlib import Path

from game import config as C
from game.map_view import FILTERS as MAP_FILTERS, ZOOM_DEFAULT as MAP_ZOOM_DEFAULT, ZOOMS as MAP_ZOOMS
from game.viewport import UI_SIZES    # "grande", "media", "pequena"

VOLUME_KEYS = ("master", "sfx", "ambient")   # multiplicadores de 0 a 1
# padrão de quem nunca mexeu: efeitos em 40% e ambiente em 50% (no 100% o dono achou alto demais)
# interface "media": em 1920×1080 dá escala inteira 3 (fonte limpa) e o HUD em 75% do Grande, que era
# o que o dono achava gigante; em janela pequena (960×540) ela fica igual à Grande (game/viewport.py)
DEFAULTS = {"master": 1.0, "sfx": 0.4, "ambient": 0.5, "fullscreen": False, "zoom": C.ZOOM_DEFAULT,
            "ui_size": "media", "map_zoom": MAP_ZOOM_DEFAULT, "map_hidden": []}
SETTINGS_PATH = C.ROOT_DIR / "settings.json"


def clean(data) -> dict:
    """Só aceita as chaves conhecidas, com valores válidos. O resto vira padrão.

    Volumes: números entre 0 e 1. Tela cheia: true/false. Zoom: um dos C.ZOOM_LEVELS.
    Interface: "grande", "media" ou "pequena" (arquivo antigo, sem o campo, fica no padrão).
    Mapa: map_zoom é 1, 2, 3 ou 4; map_hidden é uma lista de filtros conhecidos (sem repetir)."""
    result = dict(DEFAULTS)
    result["map_hidden"] = []
    if isinstance(data, dict):
        for key in VOLUME_KEYS:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[key] = round(max(0.0, min(1.0, float(value))), 2)
        if isinstance(data.get("fullscreen"), bool):
            result["fullscreen"] = data["fullscreen"]
        zoom = data.get("zoom")
        if isinstance(zoom, (int, float)) and not isinstance(zoom, bool) and float(zoom) in C.ZOOM_LEVELS:
            result["zoom"] = float(zoom)
        if data.get("ui_size") in UI_SIZES:
            result["ui_size"] = data["ui_size"]
        map_zoom = data.get("map_zoom")
        if isinstance(map_zoom, int) and not isinstance(map_zoom, bool) and map_zoom in MAP_ZOOMS:
            result["map_zoom"] = map_zoom
        hidden = data.get("map_hidden")
        if isinstance(hidden, (list, tuple, set)):
            result["map_hidden"] = [f for f in MAP_FILTERS if f in hidden]
    return result


def mix(values: dict) -> dict:
    """Só os volumes (o que o Audio.set_mix recebe)."""
    return {key: values[key] for key in VOLUME_KEYS}


def load(path: Path | None = None) -> dict:
    try:
        return clean(json.loads(Path(path or SETTINGS_PATH).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return clean(None)


def save(values: dict, path: Path | None = None) -> None:
    path = Path(path or SETTINGS_PATH)   # resolvido na hora: dá pra apontar pra outro arquivo (smoke/testes)
    try:
        path.write_text(json.dumps(clean(values), indent=2), encoding="utf-8")
    except OSError as err:
        print(f"[settings] não consegui salvar {path}: {err}")
