"""Benchmark da escuridão (game/lighting.py): custo por frame com 1, 10, 30 e 60 luminárias.

    uv run python tools/dev/bench_lighting.py

Mede `Lighting.apply` (mapa de luz + blit MULT) + `draw_glints` numa visão do tamanho que o App
usa em cada zoom (960×540 / zoom). A câmera anda a cada frame (pega o caso real do cache da grade)
e as luminárias têm flicker (pega o cache de intensidade). Meta: ≤ 3 ms com 30 luzes no zoom 0,75.
"""

import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import viewport  # noqa: E402
from game.lighting import Glint, Lighting, helmet_lamp, lamp  # noqa: E402

FRAMES = 300


def bench(zoom: float, n_lights: int, cell: int, banding: bool) -> float:
    size = viewport.view_size(zoom)
    target = pygame.Surface(size, 0, 32)
    lighting = Lighting(cell=cell, banding=banding)
    rnd = random.Random(1)
    # pior caso: todas as luminárias DENTRO da tela (sem ajuda do culling)
    lights = [lamp(rnd.randint(size[0] // 2 // C.TILE, size[0] * 3 // 2 // C.TILE), rnd.randint(size[1] // 2 // C.TILE, size[1] * 3 // 2 // C.TILE))
              for _ in range(n_lights)]
    glints = [Glint(rnd.randint(0, size[0] * 2), rnd.randint(0, size[1] * 2), (232, 160, 102)) for _ in range(150)]
    # aquece o cache (as texturas são feitas uma vez só no jogo)
    for i in range(40):
        lighting.apply(target, (i, i), [helmet_lamp(600, 400, "right"), *lights], t=i / 60)
    times = []
    for i in range(FRAMES):
        cam = (size[0] // 2 + i % 37, size[1] // 2 + i % 23)
        t = i / 60
        target.fill((90, 80, 70))
        start = time.perf_counter()
        lighting.apply(target, cam, [helmet_lamp(cam[0] + size[0] / 2, cam[1] + size[1] / 2, "right"), *lights], t=t)
        lighting.draw_glints(target, cam, glints, t=t)
        times.append(time.perf_counter() - start)
    times.sort()
    return times[len(times) // 2] * 1000, times[int(len(times) * 0.95)] * 1000


def main() -> None:
    pygame.init()
    print(f"pygame-ce {pygame.version.ver} · {FRAMES} frames · mediana / p95 em ms (inclui lanterna + 150 minérios)")
    for cell, banding in ((4, True), (4, False), (2, True)):
        print(f"\ncell={cell} banding={banding}")
        print("  zoom   visão        " + "".join(f"{n:>16}" for n in (1, 10, 30, 60)))
        for zoom in C.ZOOM_LEVELS:
            vw, vh = viewport.view_size(zoom)
            row = [bench(zoom, n, cell, banding) for n in (1, 10, 30, 60)]
            print(f"  {zoom:<5}  {vw:>4}×{vh:<4}  " + "".join(f"{m:>8.2f} /{p:>5.2f}" for m, p in row))


if __name__ == "__main__":
    main()
