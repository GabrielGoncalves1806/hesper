"""Preferências do jogador que sobrevivem entre sessões (hoje: só os volumes).

Fica num settings.json na raiz do projeto (no .gitignore). Se o arquivo não existir
ou estiver estragado, usa o padrão e segue o jogo sem reclamar.
"""

import json
from pathlib import Path

from game import config as C

DEFAULTS = {"master": 1.0, "sfx": 1.0, "ambient": 1.0}   # multiplicadores de 0 a 1
SETTINGS_PATH = C.ROOT_DIR / "settings.json"


def clean(data) -> dict:
    """Só aceita as chaves conhecidas, com números entre 0 e 1. O resto vira padrão."""
    result = dict(DEFAULTS)
    if isinstance(data, dict):
        for key in DEFAULTS:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[key] = round(max(0.0, min(1.0, float(value))), 2)
    return result


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
