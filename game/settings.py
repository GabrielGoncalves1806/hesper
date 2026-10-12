"""Preferências do jogador que sobrevivem entre sessões: volumes, tela cheia e zoom.

Fica num settings.json na raiz do projeto (no .gitignore). Se o arquivo não existir
ou estiver estragado, usa o padrão e segue o jogo sem reclamar.
"""

import json
from pathlib import Path

from game import config as C

VOLUME_KEYS = ("master", "sfx", "ambient")   # multiplicadores de 0 a 1
# padrão de quem nunca mexeu: efeitos em 40% e ambiente em 50% (no 100% o dono achou alto demais)
DEFAULTS = {"master": 1.0, "sfx": 0.4, "ambient": 0.5, "fullscreen": False, "zoom": C.ZOOM_DEFAULT}
SETTINGS_PATH = C.ROOT_DIR / "settings.json"


def clean(data) -> dict:
    """Só aceita as chaves conhecidas, com valores válidos. O resto vira padrão.

    Volumes: números entre 0 e 1. Tela cheia: true/false. Zoom: um dos C.ZOOM_LEVELS."""
    result = dict(DEFAULTS)
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
    return result


def mix(values: dict) -> dict:
    """Só os volumes (o que o Audio.set_mix recebe)."""
    return {key: values[key] for key in VOLUME_KEYS}


def load(path: Path | None = None) -> dict:
    try:
        return clean(json.loads(Path(path or SETTINGS_PATH).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(values: dict, path: Path | None = None) -> None:
    path = Path(path or SETTINGS_PATH)   # resolvido na hora: dá pra apontar pra outro arquivo (smoke/testes)
    try:
        path.write_text(json.dumps(clean(values), indent=2), encoding="utf-8")
    except OSError as err:
        print(f"[settings] não consegui salvar {path}: {err}")
