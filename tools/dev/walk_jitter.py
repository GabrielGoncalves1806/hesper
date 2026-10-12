"""Diagnóstico da "tremedeira" andando: simula o player andando N quadros (sem janela) e loga,
por quadro, a posição do player (float), a câmera, onde o sprite cai na visão e a direção/quadro.

    uv run python tools/dev/walk_jitter.py                 # diagonal, zoom 1, dt real (16/17 ms)
    uv run python tools/dev/walk_jitter.py --dir 1,0       # reta
    uv run python tools/dev/walk_jitter.py --zoom 1.5 --frames 40
    uv run python tools/dev/walk_jitter.py --all           # resumo: todas as direções × zooms

Com a câmera seguindo o player, o sprite tem que ficar PARADO na tela (só o mundo anda).
"Saltos na tela" conta quantos quadros o sprite mexeu de lugar na visão.
"""

import argparse
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import viewport as V  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.render import Renderer  # noqa: E402
from game.systems import GameState  # noqa: E402


class Recorder:
    """Finge ser o canvas: guarda onde cada blit caiu."""

    def __init__(self):
        self.blits = []

    def blit(self, surf, pos, *a, **k):
        self.blits.append((surf.get_size(), tuple(pos)))


def simulate(direction=(1, 1), zoom=1.0, frames=30, dts=(0.016, 0.017), walls=False, start=(2000.3, 1500.0)):
    """Lista de dicts por quadro. `dts` repete em ciclo (clock.tick(60) devolve 16 ou 17 ms)."""
    game = GameState(rng=random.Random(1))
    renderer = Renderer(Sprites(enabled=False))
    view = V.view_size(zoom)
    p = game.player
    p.x, p.y = start                     # longe das bordas do mapa (a câmera segue livre)
    if walls:                            # parede horizontal encostada em cima: andando pra cima, desliza nela
        top = p.y - C.PLAYER_BOX_H

        def solids(_box):
            return [(0, top - 32, 99999, 32)]
    else:
        def solids(_box):
            return []
    rows = []
    for i in range(frames):
        dt = dts[i % len(dts)]
        p.move(direction[0], direction[1], dt, solids)
        cam = renderer.camera(game, view)
        rec = Recorder()
        renderer.view_w, renderer.view_h = view
        renderer.collect_objects(rec, game, cam, 0.0)[-1][1]()    # o mesmo caminho do jogo: o player é o último
        sprite = [pos for size, pos in rec.blits if size == (32, 32)][0]
        frame = int(p.walk_time * 9) % 4
        rows.append(dict(i=i, dt=dt, x=p.x, y=p.y, cam=cam, screen=sprite, dir=p.direction, frame=frame))
    return rows


def jumps(rows):
    return sum(1 for a, b in zip(rows, rows[1:]) if a["screen"] != b["screen"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="1,1")
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--frames", type=int, default=24)
    ap.add_argument("--walls", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    pygame.init()
    pygame.display.set_mode((1, 1))
    if a.all:
        print(f"{'direção':>8} {'zoom':>5} {'dt':>9}  saltos do sprite na tela em 120 quadros")
        for d in ((1, 0), (0, 1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            for z in C.ZOOM_LEVELS:
                for name, dts in (("1/60", (1 / 60,)), ("16/17ms", (0.016, 0.017))):
                    rows = simulate(d, z, 120, dts)
                    print(f"{str(d):>8} {z:>5} {name:>9}  {jumps(rows)}")
        for d in ((1, -1), (-1, -1)):
            rows = simulate(d, 1.0, 120, walls=True)
            print(f"{str(d):>8}   1.0   16/17ms  {jumps(rows)}   (deslizando na parede)")
        return
    d = tuple(int(v) for v in a.dir.split(","))
    rows = simulate(d, a.zoom, a.frames, walls=a.walls)
    print(f"dir={d} zoom={a.zoom} view={V.view_size(a.zoom)} walls={a.walls}")
    print(f"{'q':>3} {'dt':>6} {'player.x':>10} {'player.y':>10} {'cam':>12} {'sprite na visão':>16} {'dir':>6} {'quadro':>6}")
    prev = None
    for r in rows:
        mark = "  <-- mexeu" if prev is not None and r["screen"] != prev else ""
        print(f"{r['i']:>3} {r['dt']:>6.3f} {r['x']:>10.3f} {r['y']:>10.3f} {str(r['cam']):>12} "
              f"{str(r['screen']):>16} {r['dir']:>6} {r['frame']:>6}{mark}")
        prev = r["screen"]
    print(f"saltos do sprite na tela: {jumps(rows)} em {len(rows) - 1} quadros")


if __name__ == "__main__":
    main()
