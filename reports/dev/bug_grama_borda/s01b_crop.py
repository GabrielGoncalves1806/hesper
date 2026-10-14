"""Etapa 1 (detalhe): recorte ampliado da borda de baixo no pior cam, e mapa de tiles verdes sobre rocha."""
from collections import Counter
from common_render import *  # noqa
import numpy as np
bot = setup()
s = bot.state
s.indices.update(o2=100_000.0, heat=0.0, water=0.0)
bot.frames(0.5)
w = s.world
cam = (4800, C.SURFACE_H * C.TILE - 540)
canvas = render_world(bot, cam)
crop = canvas.subsurface(pygame.Rect(0, 360, 480, 180)).copy()
pygame.image.save(pygame.transform.scale(crop, (1440, 540)), str(OUT / "01b_recorte_zoom.png"))
# mapa de cores por tile: G=verde na tela, sobre tile BEDROCK = bug
a = pygame.surfarray.array3d(canvas).astype(int)
g = (a[..., 1] > a[..., 0] + 12) & (a[..., 1] > a[..., 2] + 12)
xs, ys = np.nonzero(g)
tx = np.floor((xs + cam[0]) / C.TILE).astype(int)
ty = np.floor((ys + cam[1]) / C.TILE).astype(int)
bug = [(int(x), int(y)) for x, y in zip(tx, ty) if w.get(int(x), int(y)) == C.BEDROCK]
print("pixels verdes sobre tile BEDROCK nesta cena:", len(bug))
cnt = Counter(y for _, y in bug)
print("por linha de tile (y):", sorted(cnt.items()))
print("por coluna x (faixas de 16):", sorted(Counter(x // 16 * 16 for x, _ in bug).items())[:30])
# ASCII da área 150..200 x 250..255 com G=grama
print("ASCII (# rocha, . areia, G = pixel verde na tela sobre a rocha, g = verde sobre areia):")
for y in range(248, 256):
    row = ""
    for x in range(146, 200):
        base = "#" if w.get(x, y) == C.BEDROCK else "."
        # pixels verdes desse tile
        px = [(sx, sy) for sx in range(x * 32 - cam[0], x * 32 - cam[0] + 32) for sy in range(y * 32 - cam[1], y * 32 - cam[1] + 32)
              if 0 <= sx < 960 and 0 <= sy < 540 and g[sx, sy]]
        if px:
            row += "G" if base == "#" else "g"
        else:
            row += base
    print(f"{y:3d} " + row)
