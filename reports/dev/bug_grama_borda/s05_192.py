"""Etapa 5: o mesmo bug no código de ANTES do 256 (git archive cf1faf5, mapa 192), seed e estágio iguais.

Roda com o repo antigo extraído na scratchpad (não mexe no repo). Mede: pixels transparentes da rocha na
última linha de tiles e pixels verdes sobre rocha. Argumento: raiz do repo a usar."""
import sys
from pathlib import Path
ROOT_OLD = Path(sys.argv[1])
sys.path.insert(0, str(ROOT_OLD))
sys.path.insert(0, str(ROOT_OLD / "tools" / "dev"))
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import numpy as np
import pygame
import smoke
from game import config as C
from game import hills

OUT = Path("/Users/gabrieloliveira/personal_projects/hesper/reports/dev/bug_grama_borda")
smoke.OUT = ROOT_OLD / "reports" / "dev"
(ROOT_OLD / "reports" / "dev").mkdir(parents=True, exist_ok=True)
C.WORLD_SEED = 598929664
print("SURFACE", C.SURFACE_W, C.SURFACE_H, "BASE", C.BASE_TILE, "root", ROOT_OLD.name)
bot = smoke.Bot()
s = bot.state
s.stage = C.GREEN_STAGE; s.storm = 0.0
s.indices.update(o2=100_000.0, heat=0.0, water=0.0)
bot.frames(0.5)
W, H = s.world.width, s.world.height
w = s.world
T = C.TILE
cam = (max(0, (W // 2) * T - 480), H * T - 540)
cam = (min(cam[0], W * T - 960), cam[1])
bot.app.renderer.ground.reset()
for _ in range(60):
    canvas = pygame.Surface((960, 540))
    bot.app.renderer.draw(canvas, s, cam, bot.app.t, None)
r = bot.app.renderer
r.view_w, r.view_h = 960, 540
strips = r.hill_strips(s, cam)
rock = pygame.Surface((960, 540)); rock.fill((255, 0, 255))
for key, rows in strips.items():
    for row, (surf, x, y) in rows.items():
        rock.blit(surf, (x - cam[0], y - cam[1]))
a = pygame.surfarray.array3d(rock).astype(int)
magenta = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)
print(f"mapa {W}x{H}, cam {cam}: linhas de tela com magenta (buraco na rocha) na faixa de baixo:")
bottom_sc = H * T - cam[1]
for yy in range(bottom_sc - 36, min(540, bottom_sc + 2)):
    m = int(magenta[:, yy].sum())
    if m:
        print(f"  tela y={yy} (mundo {yy + cam[1]}, tile {(yy + cam[1]) // T}): {m}/960 magenta")
ga = pygame.surfarray.array3d(canvas).astype(int)
gm = (ga[..., 1] > ga[..., 0] + 12) & (ga[..., 1] > ga[..., 2] + 12)
band_top = H * T - 24 - cam[1]
print(f"pixels verdes (chão com grama) na faixa transparente da rocha (tela y {band_top}..540): {int(gm[:, band_top:540].sum())}")
pygame.image.save(rock, str(OUT / "05_192_rocha_sozinha.png"))
pygame.image.save(canvas, str(OUT / "05_192_cena_completa.png"))
ret = bot.app
print("salvo 05_192_rocha_sozinha.png")
