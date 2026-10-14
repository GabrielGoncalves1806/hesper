"""Etapa 3: mesmo trecho com a grama desligada (monkeypatch no script; o jogo não é editado).

Desliga so o `ground.cover_strip` (é ele que põe grama/musgo/tufos). Se a mancha some, é ele."""
import numpy as np
from common_render import *  # noqa
import pygame
from game import ground as ground_mod
from common_render import render_world, cam_for

def green_mask(surf):
    a = pygame.surfarray.array3d(surf).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (g > r + 12) & (g > b + 12)

SIZE = (960, 540)
CAM = (4800, C.SURFACE_H * C.TILE - SIZE[1])   # o mesmo pior cam da etapa 1

bot = setup()
s = bot.state
s.indices.update(o2=100_000.0, heat=0.0, water=0.0)
bot.frames(0.5)
bot.app.renderer.ground.reset()
before = render_world(bot, CAM, SIZE)
n_before = int(green_mask(before)[:, 500:540].sum())   # faixa da última linha (y 8160..8192 -> tela 508..540)

_real = ground_mod.cover_strip
def sem_grama(geo, depth, xs, ys, cls, d):
    return np.zeros(xs.shape, np.uint8)               # zero = sem grama, sem tufo, sem musgo, sem folha
ground_mod.cover_strip = sem_grama
try:
    bot.app.renderer.ground.reset()                    # refaz o chão assado sem a cobertura
    after = render_world(bot, CAM, SIZE)
finally:
    ground_mod.cover_strip = _real
n_after = int(green_mask(after)[:, 500:540].sum())
print(f"pixels verdes na faixa de baixo (tela y 500..540): com grama {n_before}, sem grama {n_after}")
pygame.image.save(after, str(OUT / "03_sem_grama.png"))
pygame.image.save(before, str(OUT / "03_com_grama_mesmo_cam.png"))
print("salvo 03_sem_grama.png e 03_com_grama_mesmo_cam.png")
