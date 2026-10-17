"""v0.8 M5 Task 3: print headless do painel do Cultivador com o selo do adubo (reports/dev/v08_m5_adubo_painel.png)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "dev"))

from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from shot_v08_m3 import OUT, frames, set_stage, shot  # noqa: E402


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m5_adubo_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=7))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)
    frames(app, 2)
    m = Machine(C.CULTIVATOR, 0, 0, chip=True)
    m.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    m.sync_crop()
    m.growth, m.tank, m.boost = 0.70, 3.0, 100.0
    s.inventory.add(C.FERTILIZER, 4)
    s.inventory.add("water_capsule", 4)
    app.open_cultivator = m
    app.set_mode("cultivator")
    shot(app, "v08_m5_adubo_painel.png")


if __name__ == "__main__":
    main()
