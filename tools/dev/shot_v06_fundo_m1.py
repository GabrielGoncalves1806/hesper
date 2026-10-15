"""v0.6 Fundo M1: print avulso da caverna nova (não entra no smoke).

Gera em reports/dev/v06_fundo_m1/, pra seed 7 e pra seed 42:
  mapa_caverna_seed{N}.png  a caverna inteira (256×256, 3 px por tile, rampa marcada com um anel branco)
  borda_gelo_seed{N}.png    tela do jogo (zoom 1) na borda do gelo, F3 desligado
  cobre_salar_seed{N}.png   tela do jogo perto de um veio de parede de cobre no salar
Headless (driver dummy): não abre janela.
"""

import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import geo, layers, minimap, settings  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v06_fundo_m1"
DT = 1 / 30
PX = 3


def save_map(world, path: Path) -> None:
    surf = pygame.Surface((world.width * PX, world.height * PX))
    for y in range(world.height):
        for x in range(world.width):
            surf.fill(minimap.tile_color(world, x, y, reveal=True), (x * PX, y * PX, PX, PX))
    rx, ry = world.crater
    pygame.draw.circle(surf, (255, 255, 255), ((rx + 1.5) * PX, (ry + 1.5) * PX), 14, 2)
    pygame.image.save(surf, str(path))


def pick_frost_edge(world):
    """Chão (não gelo) a até 3 tiles de rocha dura do gelo, o mais perto da chegada."""
    region = world.cave_region
    ax, ay = world.center
    best = None
    for y in range(3, world.height - 3):
        for x in range(3, world.width - 3):
            if not world.is_floor(x, y) or region[y, x] == geo.FROST:
                continue
            near = any(world.get(x + dx, y + dy) == C.HARD_ROCK and region[y + dy, x + dx] == geo.FROST
                       for dy in range(-3, 4) for dx in range(-3, 4))
            if near:
                d = math.hypot(x - ax, y - ay)
                if best is None or d < best[0]:
                    best = (d, (x, y))
    assert best is not None, "sem borda de gelo"
    return best[1]


def pick_copper(world):
    """Chão a até 2 tiles de um tile de cobre na parede, no salar, o mais perto da chegada."""
    region = world.cave_region
    ax, ay = world.center
    best = None
    for y in range(3, world.height - 3):
        for x in range(3, world.width - 3):
            if world.get(x, y) != C.COPPER or region[y, x] != geo.SALAR:
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    if world.is_floor(x + dx, y + dy):
                        d = math.hypot(x - ax, y - ay)
                        if best is None or d < best[0]:
                            best = (d, (x + dx, y + dy))
    assert best is not None, "sem cobre no salar"
    return best[1]


def shot(app, tile, path: Path) -> None:
    p = app.state.player
    p.x, p.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 0.5) * C.TILE
    for _ in range(20):
        app.step(DT)
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_fundo_m1_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    for seed in (7, 42):
        app.start_game(GameState(seed=seed))
        state = app.state
        state.fast = False
        cave = layers.make_cave(seed)
        state.enter_layer(layers.CAVE, layers.ramp_arrival(cave.world))
        world = state.world
        assert world.cave_region is not None
        save_map(world, OUT / f"mapa_caverna_seed{seed}.png")
        print("  screenshot:", (OUT / f"mapa_caverna_seed{seed}.png").relative_to(ROOT))
        app.set_zoom(1.0, notify=False)
        shot(app, pick_frost_edge(world), OUT / f"borda_gelo_seed{seed}.png")
        shot(app, pick_copper(world), OUT / f"cobre_salar_seed{seed}.png")
    pygame.quit()


if __name__ == "__main__":
    main()
