"""v0.7 Lore M3: prints dos 5 destroços (não entra no smoke).

Gera em reports/dev/v07_m3/ (seed 3):
  1. cargo.png, module.png, probe.png, robot.png, liner.png   cada destroço com o player ao lado da caixa
  2. module_frente.png, module_atras.png                      player embaixo (na frente) e em cima (atrás) do módulo
  3. module_terminal.png                                      player em reads_from, contorno no terminal desenhado
Os destroços são montados à mão numa área livre de chão (a geração do mundo não depende disto).
Headless (driver dummy): não abre janela.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings, viewport  # noqa: E402
from game.systems import GameState  # noqa: E402
from game.wrecks import SPECS, Wreck, make_crates  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v07_m3"
DT = 1 / 30
SEED = 3
T = C.TILE
KINDS = ("cargo", "module", "probe", "robot", "liner")


def new_app(seed: int):
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=seed))
    app.set_zoom(1.5, notify=False)
    app.state.storm = 0.0
    return app


def frames(app, n: int) -> None:
    for _ in range(n):
        app.step(DT)


def put_feet(app, px: float, py: float) -> None:
    p = app.state.player
    p.x, p.y = px, py


def save_shot(app, name: str) -> None:
    path = OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def free_rect(world, x0: int, y0: int, w: int, h: int) -> bool:
    return all(world.is_floor(x, y) and not world.vein_at(x, y) and not world.wreck_at(x, y)
               for y in range(y0, y0 + h) for x in range(x0, x0 + w))


def build_wrecks(state) -> dict[str, Wreck]:
    """Um destroço de cada tipo, em áreas livres perto do spawn (margem de 3 tiles em volta)."""
    world = state.world
    sx, sy = int(C.SPAWN_POS[0] // T), int(C.SPAWN_POS[1] // T)
    spots = sorted(((x, y) for x in range(sx - 60, sx + 60) for y in range(sy - 60, sy + 60)),
                   key=lambda t: (t[0] - sx) ** 2 + (t[1] - sy) ** 2)
    wrecks: dict[str, Wreck] = {}
    taken: list[tuple[int, int, int, int]] = []
    for rank, kind in enumerate(KINDS):
        w, h = SPECS[kind].size
        for x, y in spots:
            box = (x - 3, y - 6, w + 6, h + 11)            # sobra em cima (lift), embaixo e nos lados pro player
            if any(box[0] < t[0] + t[2] and t[0] < box[0] + box[2] and box[1] < t[1] + t[3] and t[1] < box[1] + box[3]
                   for t in taken):
                continue
            if not free_rect(world, *box):
                continue
            wreck = Wreck(kind, x, y, rank)
            taken.append(box)
            for t in wreck.tiles:
                world.set(*t, C.WRECK)
            world.set(*wreck.crate, C.LOOT_CRATE)
            wrecks[kind] = wreck
            break
        else:
            raise SystemExit(f"sem área livre pro {kind}")
    world.wrecks = list(wrecks.values())
    world._wreck_index = None
    state.crates.update(make_crates(world, SEED))
    return wrecks


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v07_m3_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    app = new_app(SEED)
    wrecks = build_wrecks(app.state)
    app.mouse = (20, 20)
    for kind, wreck in wrecks.items():
        cx, cy = wreck.crate
        put_feet(app, (cx + 0.5) * T + 40, (cy + 1) * T)      # ao lado da caixa
        frames(app, 20)
        save_shot(app, f"{kind}.png")

    m = wrecks["module"]
    w, h = SPECS["module"].size
    put_feet(app, (m.tx + 1.5) * T, (m.ty + h + 1) * T - 2)    # embaixo da pegada: na frente do sprite
    frames(app, 20)
    save_shot(app, "module_frente.png")
    put_feet(app, (m.tx + 6.5) * T, m.ty * T - 1)            # em cima: atrás do teto
    frames(app, 20)
    save_shot(app, "module_atras.png")

    rx, ry = m.reads_from
    put_feet(app, (rx + 0.5) * T, ry * T + 6)                  # lendo o terminal
    frames(app, 20)
    assert app.state.nearby_wreck_terminal() is m
    wx, wy, rw, rh = SPECS["module"].terminal_rect
    bx, by = m.blit_pos
    app.mouse = tuple(round(v) for v in viewport.world_to_canvas((bx + wx + rw / 2, by + wy + rh / 2), app.cam, app.zoom))
    frames(app, 10)
    print("  dica:", app.hint())
    save_shot(app, "module_terminal.png")
    pygame.quit()


if __name__ == "__main__":
    main()
