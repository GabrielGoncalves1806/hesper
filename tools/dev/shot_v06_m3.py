"""v0.6 M3: print avulso dos drones na caverna (não entra no smoke).

Gera em reports/dev/v06_m3/: cave_drones.png (estação na caverna com dois baús e drones voando) e
cave_place_hint.png (fantasma da estação na caverna com a dica "drones atendem esta camada").
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
from game import drones, layers, settings  # noqa: E402
from game.layers import CAVE  # noqa: E402
from game.systems import Machine  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v06_m3"
DT = 1 / 30


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_m3_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    state = app.state
    state.rng = random.Random(1)
    app.set_mode("play")
    state.enter_layer(CAVE, layers.ramp_arrival(state.layers[CAVE].world if CAVE in state.layers
                                                else layers.MAKERS[CAVE](state.seed).world))
    px, py = state.player.tile

    def free(kind: str, tile: tuple[int, int]) -> bool:
        return all(state.world.is_floor(*t) and not state.world.vein_at(*t)
                   for t in Machine(kind, *tile).tiles)

    # 3 pontos de chão livres numa linha: baú de origem, estação, baú de destino (o mais perto do player)
    spots = [(px + dx, py + dy) for dy in range(-4, 5) for dx in range(-8, 9)]
    best = None
    for (x, y) in spots:
        row = [(x, y), (x + 3, y), (x + 6, y)]
        if all(free("chest_large", t) for t in row) and all(abs(t[0] - px) <= 6 for t in row):
            best = row
            break
    assert best is not None, "sem chão pra montar a cena"
    a, mid, b = best
    station = Machine("drone_station", *mid)
    station.station = drones.new_station(station, 2)
    src = Machine("chest_large", *a, sends={"iron"})
    src.storage.add("iron", 20)
    dst = Machine("chest_large", *b, receives={"iron"})
    state.machines += [station, src, dst]
    for m in (station, src, dst):
        m.build = 0

    p = state.player
    p.x, p.y = (mid[0] + 1) * C.TILE, (mid[1] + 3) * C.TILE

    # roda até ter drone no ar (≤ 6 s de jogo) e tira o print
    for _ in range(int(6 / DT)):
        app.step(DT)
        if any(d.in_air for d in station.station.drones):
            break
    for _ in range(15):
        app.step(DT)
    assert any(d.in_air for d in station.station.drones), "nenhum drone no ar"
    app.screenshot(str(OUT / "cave_drones.png"))
    print("  screenshot: reports/dev/v06_m3/cave_drones.png")

    # fantasma da estação na caverna, com a dica nova
    state.debug_add_ti()                                   # F2: libera a receita da estação
    state.inventory.add("constructor", 1)
    for item, n in (("iron", 20), ("silicon", 20), ("ice", 10)):
        state.inventory.add(item, n)
    app.select_hotbar(next(i for i, st in enumerate(state.inventory.slots) if st and st.item == "constructor"))
    app.placing = "drone_station"
    gx, gy = mid[0], mid[1] + 6
    from game import viewport
    pos = viewport.world_to_canvas(((gx + 1) * C.TILE, (gy + 1) * C.TILE), app.cam, app.zoom)
    app.mouse = (round(pos[0]), round(pos[1]))
    app.mouse_window = app.mouse
    for _ in range(10):
        app.step(DT)
    print("  dica:", app.hint())
    app.screenshot(str(OUT / "cave_place_hint.png"))
    print("  screenshot: reports/dev/v06_m3/cave_place_hint.png")
    pygame.quit()


if __name__ == "__main__":
    main()
