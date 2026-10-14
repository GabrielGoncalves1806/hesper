from common import *  # noqa
from game.config import TILE
bot = setup()
s = bot.state
w = s.world
print("size", w.width, w.height, "seed", s.seed, "stage", s.stage, "center", w.center)
print("BASE_TILE", C.BASE_TILE, "SURFACE", C.SURFACE_W, C.SURFACE_H, "BORDER", C.SURFACE_BORDER)
# espessura da borda por coluna (quantos BEDROCK do fundo pra cima)
H, W = w.height, w.width
for x in range(0, W, 32):
    col = [w.get(x, y) for y in range(H - 8, H)]
    print(x, col)
print("geo", s.world.geo is not None if hasattr(w, "geo") else "no geo attr")
