"""Etapa 2: que tipo de tile tem nos pixels da faixa de baixo, espessura da borda e o dono (linha) de cada pixel
do bloco de morro que cobre a última linha de tiles. Usa game/hills.bake_block direto (sem editar o jogo)."""
from common import *  # noqa
import numpy as np
from game import hills
from game.render import Renderer  # noqa: F401

bot = setup()
s = bot.state
w = s.world
geo = s.active.geo
regions_full = geo.region

def regions(i0, i1, j0, j1):
    out = np.zeros((j1 - j0, i1 - i0), np.uint8)
    a, b, c, d = max(0, i0), min(w.width, i1), max(0, j0), min(w.height, j1)
    out[c - j0:d - j0, a - i0:b - i0] = regions_full[c:d, a:b]
    return out

top_tex = hills.load_indexed("hill_top.png")
face_tex = hills.load_indexed("hill_face.png")
noise = hills.edge_noise()
BS = C.HILL_BLOCK
nbx = -(-w.width // BS)
nby = -(-w.height // BS)
print(f"mapa {w.width}x{w.height}, bloco {BS} tiles, blocos {nbx}x{nby}; ultimo bloco de linha by={nby-1} cobre tiles {(nby-1)*BS}..{nby*BS-1}")
bx, by = 16, nby - 1  # bloco da borda de baixo, x ~ 128..135
blk = hills.bake_block(*[None] * 0, ) if False else None
i0, i1, j0, j1 = hills.window_bounds(bx, by)
kinds = hills.tile_window(w.tiles, w.width, w.height, i0, i1, j0, j1)
regs = regions(i0, i1, j0, j1)
blk = hills.bake_block(kinds, regs, bx, by, top_tex, face_tex, noise)
x0, y0, bw, bh = hills.block_pixels(bx, by)
print(f"bloco ({bx},{by}): retangulo px x0={x0} y0={y0} w={bw} h={bh} -> y {y0}..{y0+bh}")
print(f"  y do fundo do mapa (fim do tile 255) = {C.SURFACE_H*C.TILE}; a janela do bloco vai ate y={y0+bh}")
idx, row = blk["idx"], blk["row"]
# linhas de pixel do bloco que caem na faixa de tile 255 (y 8160..8191)
print("pixels de tile 255 (y 8160..8191) no bloco, por faixa de y: [linha dona (row), transparente?]")
for yy in range(8136, 8200, 4):
    ry = yy - y0
    if 0 <= ry < bh:
        r = row[ry]
        tr = (idx[ry] == 255).sum()
        vals = {}
        for v in np.unique(row[ry]):
            vals[int(v)] = int((row[ry] == v).sum())
        print(f"  y={yy}: owners={vals} transparentes={int(tr)}/{bw}")
print("tipos da janela, ultimas linhas (j0..255):")
for j in range(248, 256):
    print(f"  tile y={j}: " + "".join('#' if w.get(x, j) == C.BEDROCK else '.' for x in range(120, 150)))
# espessura por coluna e onde o fundo tem 2 e onde tem 3
th = []
for x in range(w.width):
    t = 0
    for y in range(w.height - 1, w.height - 6, -1):
        if w.get(x, y) == C.BEDROCK: t += 1
        else: break
    th.append(t)
from collections import Counter
print("espessura do fundo (BEDROCK contado de baixo), contagem por coluna:", dict(Counter(th)))
with open(OUT / "02_tiles.txt", "w") as f:
    f.write(f"seed {SEED} stage {s.stage} mapa {w.width}x{w.height}\n")
    f.write(f"bloco ({bx},{by}) pixels x0={x0} y0={y0} w={bw} h={bh}\n")
    for yy in range(8136, 8200, 4):
        ry = yy - y0
        if 0 <= ry < bh:
            vals = {int(v): int((row[ry] == v).sum()) for v in np.unique(row[ry])}
            f.write(f"y={yy} owners={vals} transparentes={int((idx[ry]==255).sum())}/{bw}\n")
    f.write(f"espessura do fundo por coluna: {dict(Counter(th))}\n")
print("salvo", OUT / "02_tiles.txt")
