"""v0.8 M1: prints dos estágios novos (não entra no smoke).

Gera em reports/dev/ (seed 7):
  v08_m1_umido.png   lago do Úmido (Ti 10.000, biomassa 0): a água azul de sempre
  v08_m1_algas.png   o mesmo lugar nas Algas (Ti 25.000, biomassa 500): a água esverdeada (placeholder do dono)
  v08_m1_musgo.png   o mesmo lugar no Musgo (Ti 50.000, biomassa 3.000): musgo nas pedras soltas
  v08_m1_hud.png     o painel do Ti com a biomassa faltando ("falta biomassa ...")
Headless (driver dummy): não abre janela.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.geo import PLATEAU  # noqa: E402
from game.systems import GameState, stage_for_ti  # noqa: E402

OUT = ROOT / "reports" / "dev"
DT = 1 / 30
SEED = 7
T = C.TILE


def lake_spot(world) -> tuple[int, int]:
    """A depressão mais funda do planalto (a bacia do geo): onde o lago do smoke fica."""
    g = world.geo
    y, x = np.unravel_index(np.argmin(np.where((g.region == PLATEAU) & (g.basin >= 0), g.height, 9.0)), g.height.shape)
    return int(x), int(y)


def boulder_near(app, lake: tuple[int, int]) -> tuple[int, int]:
    """O pedregulho (um dos que ganham musgo, ground.moss_on) mais perto do lago: o musgo dá pra ver ao lado da água."""
    ground, world = app.renderer.ground, app.state.world
    best = min(((abs(d.tx - lake[0]) + abs(y - lake[1]), d.tx, y) for y in range(world.height)
                for d in ground.decor_row_v9(y) if d.name in ground.moss_on))
    return best[1], best[2]


def frames(app, n: int) -> None:
    for _ in range(n):
        app.step(DT)


def settle(app) -> None:
    """Assa o chão que está na tela na hora (sem o orçamento por quadro), como o smoke faz."""
    ground = app.renderer.ground
    ground.sync = True
    frames(app, 1)
    ground.sync = False
    frames(app, 6)


def set_progress(app, ti: float, biomass: float) -> None:
    s = app.state
    s.indices.update(o2=float(ti), heat=0.0, water=0.0, biomass=float(biomass))
    s.stage = stage_for_ti(ti, biomass)
    s.storm = 0.0
    s.world.water_level = C.GEO_LEVELS[2]
    s.o2 = C.O2_MAX


def shot(app, name: str) -> None:
    path = OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m1_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.set_zoom(1.5, notify=False)
    app.mouse = (20, 20)
    frames(app, 2)                                           # o chão se liga ao mundo no primeiro quadro desenhado
    bx, by = boulder_near(app, lake_spot(app.state.world))
    p = app.state.player
    p.x, p.y = (bx + 0.5) * T, (by + 3) * T                  # 3 tiles embaixo do pedregulho, com o lago por perto
    for ti, biomass, name in ((10_000, 0, "umido"), (25_000, 500, "algas"), (50_000, 3_000, "musgo")):
        set_progress(app, ti, biomass)
        settle(app)
        shot(app, f"v08_m1_{name}.png")
    set_progress(app, 25_000, 100)                           # Ti cheio, biomassa faltando: ainda Úmido
    frames(app, 10)
    print("  estágio no print do HUD:", C.STAGES[app.state.stage - 1].name)
    shot(app, "v08_m1_hud.png")
    pygame.quit()


if __name__ == "__main__":
    main()
