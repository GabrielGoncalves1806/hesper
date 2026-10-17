"""v0.8 M6 Task 2: prints dos painéis do Cultivador, do Microscópio e da Centrífuga no Grande (480×270) com a T2 e a
seção DRONES toda ligada (chip, Envia e Recebe com tudo). Headless (driver dummy): não abre janela.

Gera em reports/dev/ (ou na pasta do 1º argumento, seed 7):
  v08_m6_drones_cultivador.png
  v08_m6_drones_microscopio.png
  v08_m6_drones_centrifuga.png
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
from game import drones, settings  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from shot_v08_m3 import frames, set_stage  # noqa: E402
from shot_v08_m5 import equip  # noqa: E402

SEED = 7


def shot(app, name: str, n: int = 6) -> None:
    """O shot do M3 (sem chuva nem banner), mas aceitando a pasta de saída fora do repo."""
    app.state.rain.next_shower, app.state.rain.left, app.state.rain.intensity = 1e9, 0.0, 0.0
    app.banner_time = 99.0
    frames(app, n)
    path = shot_v08_m3.OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path)


def wire(m: Machine) -> Machine:
    """Chip, e Envia/Recebe com tudo o que a máquina aceita (o pior caso da seção DRONES)."""
    m.chip = True
    m.sends = {i for i in C.LOGISTIC_ITEMS if drones.can_send(m, i)}
    m.receives = {i for i in C.LOGISTIC_ITEMS if drones.can_receive(m, i)}
    return m


def main() -> None:
    if len(sys.argv) > 1:
        shot_v08_m3.OUT = Path(sys.argv[1]).resolve()
    shot_v08_m3.OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m6_drones_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)
    frames(app, 2)
    equip(s, (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS))
    print("  ui:", app.ui.w, "×", app.ui.h)

    cult = wire(Machine(C.CULTIVATOR, 0, 0))
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    cult.sync_crop()
    cult.growth, cult.tank, cult.boost = 0.70, 3.0, 100.0
    app.open_cultivator = cult
    app.set_mode("cultivator")
    shot(app, "v08_m6_drones_cultivador.png")
    app.set_mode("play")
    app.open_cultivator = None

    mic = wire(Machine(C.MICROSCOPE, 0, 0))
    mic.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 8)
    app.open_microscope = mic
    app.set_mode("microscope")
    shot(app, "v08_m6_drones_microscopio.png")
    app.set_mode("play")
    app.open_microscope = None

    cent = wire(Machine(C.CENTRIFUGE, 0, 0))
    cent.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 4)
    cent.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_mutant", 1)
    app.open_centrifuge = cent
    app.set_mode("centrifuge")
    shot(app, "v08_m6_drones_centrifuga.png")
    app.set_mode("play")
    app.open_centrifuge = None
    pygame.quit()


if __name__ == "__main__":
    main()
