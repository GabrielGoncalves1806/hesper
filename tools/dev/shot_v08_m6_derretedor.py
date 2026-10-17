"""v0.8 M6 Task 6 (a garrafa é recurso): prints do painel do derretedor no Grande (480×270) com a T2 e a seção DRONES
ligada: um com vazias (enchendo) e um "SEM VAZIA". Headless (driver dummy): não abre janela.

Gera em reports/dev/ (ou na pasta do 1º argumento, seed 7):
  v08_m6_derretedor_vazias.png
  v08_m6_derretedor_sem_vazia.png
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import pygame  # noqa: E402

import shot_v08_m3  # noqa: E402
from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from shot_v08_m3 import frames, set_stage  # noqa: E402
from shot_v08_m5 import equip  # noqa: E402
from shot_v08_m6_drones import shot, wire  # noqa: E402

SEED = 7


def main() -> None:
    if len(sys.argv) > 1:
        shot_v08_m3.OUT = Path(sys.argv[1]).resolve()
    shot_v08_m3.OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m6_derretedor_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)
    frames(app, 2)
    equip(s, (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS))
    s.inventory.add(C.EMPTY_CAPSULE, 4)
    print("  ui:", app.ui.w, "×", app.ui.h)

    m = wire(Machine("melter", 0, 0))
    m.storage.slots[C.MELTER_ICE_SLOT] = Stack("ice", 18)
    m.storage.slots[C.MELTER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 3)
    m.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", 2)
    m.timer = C.MELTER_CAPSULE_TIME["melter"] * 0.6
    app.open_melter = m
    app.set_mode("melter")
    shot(app, "v08_m6_derretedor_vazias.png")

    m.storage.slots[C.MELTER_EMPTY_SLOT] = None
    shot(app, "v08_m6_derretedor_sem_vazia.png")
    app.set_mode("play")
    app.open_melter = None
    pygame.quit()


if __name__ == "__main__":
    main()
