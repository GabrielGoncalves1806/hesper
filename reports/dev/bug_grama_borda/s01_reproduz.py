"""Etapa 1: reproduz o bug no Verde (seed 598929664), câmera na borda de baixo.

Renderiza SÓ o mundo (sem HUD: o FPS e a barra de baixo têm verde e sujariam a conta).
Pixel verde -> tile do mundo (cam + zoom) -> tipo do tile e do de baixo. Conta por tipo.
"""
from collections import Counter
from common_render import *  # noqa
import numpy as np

bot = setup()
app, s = bot.app, bot.state
s.indices.update(o2=100_000.0, heat=0.0, water=0.0)   # Ti do Verde
bot.frames(0.5)
w = s.world
SIZE = (960, 540)


def green_mask(surf):
    a = pygame.surfarray.array3d(surf).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (g > r + 12) & (g > b + 12)


def scan(cam):
    canvas = render_world(bot, cam, SIZE)
    m = green_mask(canvas)
    xs, ys = np.nonzero(m)
    wx = np.floor((xs + cam[0]) / C.TILE).astype(int)
    wy = np.floor((ys + cam[1]) / C.TILE).astype(int)
    sel = wy >= C.SURFACE_H - 4
    hits = list(zip(wx[sel].tolist(), wy[sel].tolist()))
    kinds = Counter()
    for a, b in hits:
        below = w.get(a, b + 1)
        kinds[(w.get(a, b), below)] += 1
    return canvas, len(hits), kinds, hits


# cam fixo na borda de baixo, varrendo x
results = []
for cx in range(0, C.SURFACE_W * C.TILE - SIZE[0] + 1, 480):
    cam = (cx, C.SURFACE_H * C.TILE - SIZE[1])
    canvas, n, kinds, hits = scan(cam)
    results.append((n, cam, kinds, hits))
    print(f"cam={cam}: verdes na faixa y>=252: {n}  (tile, tile de baixo): {dict(kinds)}")
n, cam, kinds, hits = max(results, key=lambda r: r[0])
print("PIOR cam", cam, "n", n)
if hits:
    xs_ = [h[0] for h in hits]; ys_ = [h[1] for h in hits]
    print(f"tiles verdes x {min(xs_)}..{max(xs_)}, y {min(ys_)}..{max(ys_)}")
canvas = render_world(bot, cam, SIZE)
pygame.image.save(canvas, str(OUT / "01_reproduz.png"))
print("screenshot:", OUT / "01_reproduz.png")
