"""Prints avulsos do Marco 4 do v0.5 (broca de mão, peças de loot, contêiner aberto), fora do smoke:

    uv run python tools/dev/shot_m4_loot.py

Gera em reports/dev/: m4_hotbar_broca.png (jogo com a hotbar e a broca no 1º slot), m4_inventario_loot.png (inventário
com as 5 peças novas), m4_conteiner_fechado.png / m4_conteiner_aberto.png (o mesmo contêiner antes e depois do E, com
o fallback por código enquanto o container_open.png não vem) e m4_conteiner_saque.png (a tela de saque dele).
Headless (driver dummy): não abre janela.
"""

import os
import random
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings  # noqa: E402

OUT = ROOT / "reports" / "dev"
DT = 1 / 30


def main() -> None:
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_m4_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    state = app.state
    state.rng = random.Random(1)
    app.set_mode("play")

    def frames(n: int = 60) -> None:
        for _ in range(n):
            app.step(DT)

    def shot(name: str) -> None:
        frames()
        app.screenshot(str(OUT / name))
        print(f"  screenshot: reports/dev/{name}")

    for item, n in (("iron", 20), ("iron_ingot", 3), ("silicon_wafer", 2), ("circuit", 4), ("chip", 1), ("wire", 12)):
        state.inventory.add(item, n)
    app.hotbar_selected = 0
    shot("m4_hotbar_broca.png")

    app.set_mode("inventory")
    shot("m4_inventario_loot.png")
    app.set_mode("play")

    tx, ty = state.world.containers[0]
    state.player.x, state.player.y = (tx + 0.5) * C.TILE, (ty + 2) * C.TILE - 2
    state.indices["heat"] = max(h[-1] for h in C.THAW_GATE_HEAT) + 100.0
    state._apply_thaw()
    shot("m4_conteiner_fechado.png")
    box = state.container_crate((tx, ty))
    app.open_loot(box)
    shot("m4_conteiner_saque.png")
    state.crate_take(box)
    app.set_mode("play")
    state.player.y += 6                                   # um passo atrás pra tirar o contorno do alvo do E
    shot("m4_conteiner_aberto.png")
    pygame.quit()


if __name__ == "__main__":
    main()
