"""v0.6 Fundo M2: print avulso da cara dos biomas da caverna (não entra no smoke).

Gera em reports/dev/v06_fundo_m2/, pra seed 7, 5 pontos de fronteira (os da seção 0.5 do report da Designer),
cada um claro (sem a escuridão, pra ver a cor) e escuro (o normal do jogo, com a luz da região):
  <ponto>_claro.png  e  <ponto>_escuro.png
No fim imprime o tempo do assado do chão da caverna (média e máximo por bloco, assado inteiro de uma vez) e quantos
blocos de rocha foram assados. Headless (driver dummy): não abre janela.
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

OUT = ROOT / "reports" / "dev" / "v06_fundo_m2"
DT = 1 / 30
SEED = 7
SPOTS = {"centro_salar": (155, 132), "basalto_centro": (77, 132), "gelo_centro": (128, 71),
         "juncao_no": (82, 88), "juncao_ne": (188, 82)}


def shot(app, tile, path: Path, steps: int) -> None:
    p = app.state.player
    p.x, p.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 0.5) * C.TILE
    for _ in range(steps):
        app.step(DT)
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_fundo_m2_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    state = app.state
    state.fast = False
    cave = layers.make_cave(SEED)
    state.enter_layer(layers.CAVE, layers.ramp_arrival(cave.world))
    app.set_zoom(1.0, notify=False)
    r = app.renderer
    r.cave_ground.sync = True                       # assa tudo que a tela pede na hora (mede o bloco inteiro)
    darkness = r.draw_cave_darkness
    for name, tile in SPOTS.items():
        shot(app, tile, OUT / f"{name}_escuro.png", 90)      # 3 s: a luz da região assenta
        r.draw_cave_darkness = lambda *a, **k: None          # claro: só sem a escuridão
        shot(app, tile, OUT / f"{name}_claro.png", 3)
        r.draw_cave_darkness = darkness
    ms = r.cave_ground.bake_ms
    print(f"  assado do chão da caverna: {len(ms)} blocos, média {sum(ms) / len(ms):.0f} ms, máx {max(ms):.0f} ms")
    print(f"  blocos de rocha assados: {r.cave_rock_blocks().bakes}")
    pygame.quit()


if __name__ == "__main__":
    main()
