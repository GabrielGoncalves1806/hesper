"""Print avulso do bolsão grande da criatura (v0.5 M3.6.2), fora do smoke:

    uv run python tools/dev/shot_bolsao.py

Gera reports/dev/bolsao_criatura.png: em cima o mapa de regiões de 3 seeds (o bolsão grande em vermelho, os bolsões dos
gelos-portão em amarelo, a base em branco) e embaixo o jogo dentro do bolsão (headless, estágio Árido) de uma seed com
a Larva e uma com o Casulo. Não abre janela.
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
from game.geo import generate_geo  # noqa: E402
from game.render import Renderer  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "bolsao_criatura.png"
MAP_SEEDS = (598929664, 7, 1234)
REGION_COLORS = ((150, 108, 76), (205, 195, 175), (70, 62, 66), (150, 200, 225))   # planalto, salar, basalto, faixa
K = 2                                                                                # px por tile no mapa


def region_map(seed: int, font: pygame.font.Font) -> pygame.Surface:
    geo = generate_geo(seed, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE)
    img = np.array(REGION_COLORS, np.uint8)[geo.region]                            # (H, W, 3)
    surf = pygame.surfarray.make_surface(img.swapaxes(0, 1))
    surf = pygame.transform.scale_by(surf, K)
    for p in geo.pockets:
        for t in p.ring:
            surf.fill((230, 200, 60), (t[0] * K, t[1] * K, K, K))
    g = geo.giant
    for t in g.ring:
        surf.fill((220, 50, 50), (t[0] * K, t[1] * K, K, K))
    x, y, w, h = g.entry_rect
    surf.fill((60, 220, 90), (x * K, y * K, w * K, h * K))                         # a entrada (aberta por enquanto)
    surf.fill((255, 255, 255), (C.BASE_TILE[0] * K - 3, C.BASE_TILE[1] * K - 3, 7, 7))
    label = font.render(f"seed {seed} · {g.creature.variant} · bolsão em {g.outer[0]},{g.outer[1]}", True, (255, 255, 255), (0, 0, 0))
    surf.blit(label, (4, 4))
    return surf


def game_shot(seed: int, renderer: Renderer) -> pygame.Surface:
    """O jogo (estágio Árido) com o player andando na entrada do bolsão, o gelo gigante à frente."""
    state = GameState(seed, rng=random.Random(1))
    state.stage, state.storm = C.ARID_STAGE, 0.0
    state.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    gp = state.active.geo.giant
    ex, ey, ew, _ = gp.entry_rect
    state.player.x, state.player.y = (ex + ew / 2) * C.TILE, (ey + 0.5) * C.TILE
    state.o2 = C.O2_MAX
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    fx, fy = gp.giant.base_px
    cam = (int(fx - C.SCREEN_W / 2), int(fy - C.SCREEN_H / 2 - 40))
    renderer.use_seed(seed)
    renderer.stage_map = renderer.surface_map
    renderer.stage_map.update(state.indices["o2"], [])
    for _ in range(3):                                                             # deixa os caches/estágio assentarem
        renderer.draw(canvas, state, cam, 1.0)
    return canvas


def main() -> None:
    pygame.init()
    pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    font = pygame.font.Font(None, 20)
    renderer = Renderer(Sprites())
    maps = [region_map(s, font) for s in MAP_SEEDS]
    shots = []
    larva = next(s for s in range(1, 60) if generate_geo(s, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE).giant.creature.variant == "larva")
    cocoon = next(s for s in range(1, 60) if generate_geo(s, C.SURFACE_W, C.SURFACE_H, C.BASE_TILE).giant.creature.variant == "cocoon")
    for s in (larva, cocoon):
        shot = game_shot(s, renderer)
        shot = pygame.transform.scale_by(shot, 0.8)
        shot.blit(font.render(f"seed {s}", True, (255, 255, 255), (0, 0, 0)), (4, 4))
        shots.append(shot)
    mw = sum(m.get_width() for m in maps) + 8 * (len(maps) - 1)
    sw = sum(s.get_width() for s in shots) + 8
    W = max(mw, sw)
    H = maps[0].get_height() + 8 + shots[0].get_height()
    sheet = pygame.Surface((W, H))
    sheet.fill((20, 20, 24))
    x = 0
    for m in maps:
        sheet.blit(m, (x, 0))
        x += m.get_width() + 8
    x = 0
    for s in shots:
        sheet.blit(s, (x, maps[0].get_height() + 8))
        x += s.get_width() + 8
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(OUT))
    print(f"salvo: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
