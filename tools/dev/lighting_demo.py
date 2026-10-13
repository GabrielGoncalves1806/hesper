"""Demo headless da escuridão da caverna (game/lighting.py).

    uv run python tools/dev/lighting_demo.py

Monta uma cena com o mundo de hoje (game/world.py, paredes + minério) desenhada pelo Renderer
de verdade, põe o player com a lanterna, uma trilha de 8 luminárias seguindo um corredor e os
minérios brilhando, e salva em reports/dev/:
  escuridao_demo.png           o modo recomendado (degraus), zoom 1
  escuridao_demo_banding.png   degraus, zoom 0,75 (a visão maior, a da meta de performance)
  escuridao_demo_suave.png     degradê suave, zoom 0,75
  escuridao_demo_sem_luz.png   a mesma cena sem escuridão (referência)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import viewport  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.lighting import Lighting, helmet_lamp, lamp, ore_glints  # noqa: E402
from game.render import Renderer, art_key  # noqa: E402
from game.systems import GameState  # noqa: E402

T = C.TILE
OUT = ROOT / "reports" / "dev"


def carve_tunnel(world):
    """O mapa de hoje só tem chão na cratera (o resto se cava). Simula o que o jogador faria:
    cava um túnel sinuoso de 3 tiles saindo da cratera, na direção com mais minério, terminando
    numa salinha. Devolve a lista de tiles do eixo do túnel (do começo pro fim)."""
    import math
    cx, cy = C.CRATER_CENTER
    best = None
    for deg in (*range(-20, 25, 5), *range(160, 205, 5)):   # túnel mais deitado: cabe na tela 16:9
        a = math.radians(deg)
        ores = 0
        for d in range(14, 36):
            for w in range(-6, 7):
                tx = round(cx + math.cos(a) * d - math.sin(a) * w)
                ty = round(cy + math.sin(a) * d + math.cos(a) * w)
                ores += world.get(tx, ty) in C.ORE_TILES
        if best is None or ores > best[0]:
            best = (ores, a)
    a = best[1]
    axis = []
    for i in range(0, 220):
        d = 9 + i * 0.22
        wig = math.sin(i * 0.11) * 2.5
        tx = round(cx + math.cos(a) * d - math.sin(a) * wig)
        ty = round(cy + math.sin(a) * d + math.cos(a) * wig)
        if not axis or axis[-1] != (tx, ty):
            axis.append((tx, ty))
    for tx, ty in axis:
        for j in (-1, 0, 1):
            for i in (0, 1):
                world.set(tx + i, ty + j, C.FLOOR)
    ex, ey = axis[-1]
    for j in range(-2, 3):
        for i in range(-3, 4):
            if abs(i) + abs(j) < 5:
                world.set(ex + i, ey + j, C.FLOOR)
    return axis


def draw_lamp_post(surf, cam, tx, ty):
    """Placeholder da luminária (ainda não tem sprite): poste com cúpula quente."""
    x, y = tx * T + 16 - cam[0], ty * T + 16 - cam[1]
    surf.fill((40, 36, 34), (x - 2, y - 12, 4, 16))
    surf.fill((60, 54, 50), (x - 6, y + 2, 12, 4))
    surf.fill((255, 214, 150), (x - 4, y - 18, 8, 6))
    surf.fill((255, 245, 220), (x - 2, y - 17, 4, 3))


def render_scene(zoom, banding, light=True):
    state = GameState()
    world = state.world
    path = carve_tunnel(world)
    start = path[-1]                       # o player está no fundo do túnel, cavando
    # 8 luminárias pra trás, uma a cada ~6 tiles (como um jogador marcando o caminho de volta)
    lamps, last = [], None
    for tx, ty in reversed(path[:-3]):
        if last is None or (tx - last[0]) ** 2 + (ty - last[1]) ** 2 >= 36:
            lamps.append((tx, ty))
            last = (tx, ty)
        if len(lamps) == 8:
            break
    p = state.player
    p.x, p.y = start[0] * T + 16, start[1] * T + 24
    renderer = Renderer(Sprites())
    view = pygame.Surface(viewport.view_size(zoom))
    renderer.view_w, renderer.view_h = view.get_size()
    # câmera: o player um pouco à direita do centro e a trilha indo pra trás (o máximo que couber)
    vw, vh = view.get_size()
    back = lamps[min(len(lamps) - 1, 3 if zoom >= 1 else 7)]
    mid = ((start[0] + back[0]) / 2 * T + 16, (start[1] + back[1]) / 2 * T + 16)
    cam = (int(mid[0] - vw / 2), int(mid[1] - vh / 2))
    cam = (min(cam[0], int(p.x - 3 * T)), cam[1])          # player nunca cola na borda
    cam = (max(cam[0], int(p.x + 3 * T - vw)), cam[1])
    stage = art_key(state.stage)
    t = 1.3
    renderer.draw_floors(view, state, cam, stage, t)
    renderer.draw_veins(view, state, cam)
    renderer.draw_walls_and_objects(view, state, cam, stage, t)
    for tx, ty in lamps:
        draw_lamp_post(view, cam, tx, ty)
    if light:
        lighting = Lighting(banding=banding)
        fx, fy = start[0] - path[-6][0], start[1] - path[-6][1]
        n = max(1, abs(fx) + abs(fy))
        lights = [helmet_lamp(p.x, p.y - 18, (fx / n, fy / n)), *(lamp(tx, ty) for tx, ty in lamps)]
        lighting.apply(view, cam, lights, ambient=0.0, t=t)
        lighting.draw_glints(view, cam, ore_glints(world, *renderer.visible_tiles(cam)), t=t)
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    pygame.transform.scale(view, canvas.get_size(), canvas)
    return canvas


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    OUT.mkdir(parents=True, exist_ok=True)
    shots = {
        "escuridao_demo.png": render_scene(1.0, True),
        "escuridao_demo_banding.png": render_scene(0.75, True),
        "escuridao_demo_suave.png": render_scene(0.75, False),
        "escuridao_demo_sem_luz.png": render_scene(0.75, True, light=False),
    }
    for name, surf in shots.items():
        pygame.image.save(surf, str(OUT / name))
        print("salvo", OUT / name)


if __name__ == "__main__":
    main()
