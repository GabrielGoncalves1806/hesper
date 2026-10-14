"""Print avulso da nevasca (v0.5 M3.7), fora do smoke:

    uv run python tools/dev/shot_nevasca.py

Gera reports/dev/nevasca.png: a tempestade no deserto (fator 0), no meio da transição (0,5) e na faixa gelada (1),
na linha de baixo o chiado do minimapa/mapa nos mesmos três fatores. Seed 598929664, headless, sem janela.
"""

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.geo import FROST, PLATEAU  # noqa: E402
from game.render import Renderer  # noqa: E402
from game.systems import GameState  # noqa: E402
from game.ui import static_noise  # noqa: E402

OUT = ROOT / "reports" / "dev" / "nevasca.png"
SEED = 598929664


def tile_in(geo, region):
    """Um tile da região, escolhido do meio da lista (determinístico)."""
    ys, xs = np.nonzero(geo.region == region)
    return int(xs[len(xs) // 2]), int(ys[len(ys) // 2])


def main() -> None:
    pygame.init()
    pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    font = pygame.font.Font(None, 22)
    renderer = Renderer(Sprites())
    state = GameState(SEED, rng=random.Random(1))
    state.storm = 1.0
    state.weather.gust = 0.6                           # rajada média: chiado e faixas bem visíveis
    renderer.use_seed(SEED)
    renderer.stage_map = renderer.surface_map
    renderer.stage_map.update(state.indices["o2"], [])
    geo = state.surface.geo
    shots, statics = [], []
    for label, region, snow in (("deserto · neve 0,0", PLATEAU, 0.0), ("transição · neve 0,5", FROST, 0.5),
                                ("faixa gelada · neve 1,0", FROST, 1.0)):
        tx, ty = tile_in(geo, region)
        state.player.x, state.player.y = tx * C.TILE + 8, ty * C.TILE + 8
        state.weather.snow = snow
        cam = (int(state.player.x - C.SCREEN_W / 2), int(state.player.y - C.SCREEN_H / 2))
        canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        for i in range(90):                            # deixa as nuvens e os grãos andarem
            renderer.draw(canvas, state, cam, i / 30)
        shot = pygame.transform.scale_by(canvas, 0.6)
        shot.blit(font.render(label, True, (255, 255, 255), (0, 0, 0)), (4, 4))
        shots.append(shot)
        mm = pygame.Surface((shot.get_width(), 150))      # fundo de mapa fake (o mesmo cinza nos três) só pra ver o chiado
        mm.fill((80, 84, 88))
        static_noise(mm, 1.0, 3.3, snow)
        statics.append(mm)
    w, h = shots[0].get_size()
    sheet = pygame.Surface((w * 3 + 16, h + 150 + 8))
    sheet.fill((20, 20, 24))
    for k, (shot, mm) in enumerate(zip(shots, statics)):
        sheet.blit(shot, (k * (w + 8), 0))
        sheet.blit(mm, (k * (w + 8), h + 8))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(OUT))
    print(f"salvo: {OUT}")


if __name__ == "__main__":
    main()
