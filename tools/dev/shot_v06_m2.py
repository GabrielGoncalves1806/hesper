"""Prints avulsos do v0.6 Marco 2 (chip nas máquinas), fora do smoke:

    uv run python tools/dev/shot_v06_m2.py

Gera em reports/dev/v06_m2/ os painéis da drill, do derretedor e do dispersor, cada um sem chip (texto "Coloque um
chip pra ligar aos drones" + slot vazio) e com chip (seção DRONES). Headless (driver dummy): não abre janela.
"""

import os
import random
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.systems import Machine  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v06_m2"
DT = 1 / 30


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_m2_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    state = app.state
    state.rng = random.Random(1)
    app.set_mode("play")
    for item, n in (("iron", 20), ("ice", 30), ("chip", 2)):
        state.inventory.add(item, n)

    drill = Machine("drill", 70, 70, resource="iron", stored_init=12)
    melter = Machine("melter", 74, 70)
    melter.storage.add("ice", 8)
    disp = Machine(C.DISPENSER, 78, 70)
    state.machines += [drill, melter, disp]

    def frames(n: int = 20) -> None:
        for _ in range(n):
            app.step(DT)

    def open_panel(mode: str, machine) -> None:
        app.set_mode("play")
        app.open_drill = machine if mode == "drill" else None
        app.open_melter = machine if mode == "melter" else None
        app.open_dispenser = machine if mode == "dispenser" else None
        app.set_mode(mode)

    def shot(name: str) -> None:
        frames()
        app.screenshot(str(OUT / name))
        print(f"  screenshot: reports/dev/v06_m2/{name}")

    for mode, machine, label in (("drill", drill, "drill"), ("melter", melter, "derretedor"),
                                 ("dispenser", disp, "dispersor")):
        open_panel(mode, machine)
        shot(f"{label}_sem_chip.png")
        state.chip_install(machine)
        shot(f"{label}_com_chip.png")
        app.set_mode("play")
    pygame.quit()


if __name__ == "__main__":
    main()
