"""v0.8 M6: prints dos objetivos novos, das dicas e do painel do Cultivador no Grande (não entra no smoke).
Headless (driver dummy): não abre janela.

Gera em reports/dev/ (seed 7, tamanho Grande 480×270):
  v08_m6_objetivos.png          a caixa de objetivos: "Ache o laboratório da Ilves" atual e o próximo embaixo
  v08_m6_dica_scan.png          o cartão da dica do objetivo "Escaneie o microscópio e o tanque" (SCAN_HINT)
  v08_m6_dica_coletor.png       o cartão da dica do objetivo "Colha a primeira alga" (COLLECTOR_HINT)
  v08_m6_drones_grande.png      o painel do Cultivador com a Mochila T2 e a seção DRONES toda ligada

Os objetivos são fixados com um patch em `objectives.current_index` (o save de teste não passou por todos os
anteriores); o texto, o "próximo" e a dica saem do código real do tracker.
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

from game import config as C  # noqa: E402
from game import objectives, settings  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from shot_v08_m3 import frames, set_stage, shot  # noqa: E402
from shot_v08_m5 import equip  # noqa: E402
from shot_v08_m6_drones import wire  # noqa: E402

SEED = 7


def index_of(text: str) -> int:
    return next(i for i, o in enumerate(objectives.OBJECTIVES) if o.text == text)


def main() -> None:
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m6_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)
    frames(app, 2)
    print("  ui:", app.ui.w, "×", app.ui.h)
    real = objectives.current_index

    def pin(text: str) -> None:
        """Fixa o objetivo atual e deixa o tracker andar: a dica entra pelo caminho de verdade."""
        i = index_of(text)
        objectives.current_index = lambda state: i
        app.objectives.shown = i
        app.objectives.hinted.clear()
        app.objectives.flash = None
        app.objective_hint, app.objective_hint_time = None, 0.0
        frames(app, 2)

    try:
        pin("Ache o laboratório da Ilves")
        shot(app, "v08_m6_objetivos.png")

        pin("Escaneie o microscópio e o tanque")
        assert app.objective_hint == objectives.SCAN_HINT
        shot(app, "v08_m6_dica_scan.png", 2)

        pin("Colha a primeira alga")
        assert app.objective_hint == objectives.COLLECTOR_HINT
        shot(app, "v08_m6_dica_coletor.png", 2)
    finally:
        objectives.current_index = real

    app.objective_hint, app.objective_hint_time = None, 0.0
    equip(s, (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS))
    cult = wire(Machine(C.CULTIVATOR, 0, 0))
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    cult.sync_crop()
    cult.growth, cult.tank, cult.boost = 0.70, 3.0, 100.0
    app.open_cultivator = cult
    app.set_mode("cultivator")
    shot(app, "v08_m6_drones_grande.png")
    pygame.quit()


if __name__ == "__main__":
    main()
