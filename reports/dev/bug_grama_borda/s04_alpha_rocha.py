"""Etapa 4: a camada dos blocos de rocha sozinha (sem chão), sobre fundo magenta, pro mesmo cam.

Magenta = transparente. Onde a rocha tem buraco, aparece magenta (e lá o chão com grama apareceria no jogo)."""
import numpy as np
from common_render import *  # noqa
import pygame
from common_render import render_world

SIZE = (960, 540)
CAM = (4800, C.SURFACE_H * C.TILE - SIZE[1])
bot = setup()
s = bot.state
s.indices.update(o2=100_000.0, heat=0.0, water=0.0)
bot.frames(0.5)
render_world(bot, CAM, SIZE)                          # define stage_map e view_w/h
r = bot.app.renderer
r.view_w, r.view_h = SIZE
strips = r.hill_strips(s, CAM)
canvas = pygame.Surface(SIZE)
canvas.fill((255, 0, 255))
n_pieces = 0
for key, rows in strips.items():
    for row, (surf, x, y) in rows.items():
        canvas.blit(surf, (x - CAM[0], y - CAM[1]))
        n_pieces += 1
print("blocos com tiras:", len(strips), "tiras:", n_pieces)
a = pygame.surfarray.array3d(canvas).astype(int)
magenta = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)
band = magenta[:, 500:540]
print("pixels magenta (sem rocha) na faixa de baixo (tela y 500..540):", int(band.sum()), "de", band.size)
# por linha de tela na faixa de baixo
for yy in range(484, 540, 4):
    print(f"  tela y={yy} (mundo {yy + CAM[1]}, tile {(yy + CAM[1]) // 32}): magenta {int(magenta[:, yy].sum())}/{SIZE[0]}")
pygame.image.save(canvas, str(OUT / "04_alpha_rocha.png"))
print("salvo 04_alpha_rocha.png")
