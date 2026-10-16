"""v0.7 Lore M1: prints avulsos das estruturas (não entra no smoke).

Gera em reports/dev/v07_m1/, pra seed 3:
  camp.png, lab.png, melters.png, drill_post.png  tela do jogo (zoom 1) na frente da porta de cada estrutura
  mapa.png                                       mapa aberto da superfície com os marcadores das ruínas
  log.png                                        tela de leitura de um LOG de uma ruína
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

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import layers, settings  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v07_m1"
DT = 1 / 30
SEED = 3


def door_view(ruin):
    """Tile onde o player fica pra ver a estrutura: na superfície, 3 tiles pra fora da porta dupla; na caverna (a
    estrutura está dentro da rocha), 2 tiles pra dentro."""
    grid = ruin.grid
    h, w = len(grid), len(grid[0])
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch != "=":
                continue
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):         # a direção em que a porta dá pra fora
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or grid[ny][nx] == " ":
                    k = -4 if ruin.layer == "cave" else 5
                    return ruin.tx + x + dx * k, ruin.ty + y + dy * k
    return int(ruin.center[0]), int(ruin.center[1]) + 8


def shot(app, tile, path: Path) -> None:
    p = app.state.player
    p.x, p.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 0.5) * C.TILE
    for _ in range(20):
        app.step(DT)
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v07_m1_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    state = app.state
    app.set_zoom(1.0, notify=False)
    cave = layers.make_cave(SEED)
    state.layers[layers.CAVE] = cave
    state.storm = 0.0                                         # sem poeira de tempestade: a estrutura aparece inteira
    darkness = app.renderer.draw_cave_darkness
    for layer_key in (layers.SURFACE, layers.CAVE):
        state.enter_layer(layer_key, layers.ramp_arrival(state.layers[layer_key].world))
        app.renderer.draw_cave_darkness = (lambda *a, **k: None) if layer_key == layers.CAVE else darkness   # só pro print
        for ruin in state.world.ruins:
            shot(app, door_view(ruin), OUT / f"{ruin.key}.png")
    app.renderer.draw_cave_darkness = darkness
    state.enter_layer(layers.SURFACE, layers.ramp_arrival(state.surface.world))
    lab = next(r for r in state.world.ruins if r.key == "lab")
    for ruin in state.world.ruins:                           # o mapa: tudo visto; o laboratório já com o nome (LOG lido)
        for t in ruin.tiles:
            state.surface.explored.reveal_rect(t[0], t[1], 0, 0)
    state.logs_read.add(next(iter(lab.terminals.values())))
    app.mode = "map"
    app.map_view.open(state)
    app.step(DT)
    app.screenshot(str(OUT / "mapa.png"))
    print("  screenshot:", (OUT / "mapa.png").relative_to(ROOT))
    app.mode = "play"
    app.show_log(next(iter(lab.terminals.values())))
    for _ in range(5):
        app.step(DT)
    app.screenshot(str(OUT / "log.png"))
    print("  screenshot:", (OUT / "log.png").relative_to(ROOT))
    pygame.quit()


if __name__ == "__main__":
    main()
