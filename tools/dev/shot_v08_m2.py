"""v0.8 M2: prints do Dispersor proporcional e do Coletor de água (não entra no smoke).

Gera em reports/dev/ (seed 7):
  v08_m2_dispersor.png       painel do Dispersor numa base vedada 5×5: "1 cápsula = 3 min nesta base" e VAZIAS com 2
  v08_m2_coletor.png         Coletor no chão perto da base, coletando, com o painel aberto
  v08_m2_coletor_mundo.png   o mesmo Coletor visto no mundo (sem painel), animando
  v08_m2_coletor_chuva.png   o painel durante a chuva: "chuva x3.0" e o ciclo de 13 s
  v08_m2_coletor_parado.png  o painel no Árido: "Precisa do estágio Úmido"
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
from game import settings  # noqa: E402
from game.base import BaseBlock  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine, stage_for_ti  # noqa: E402

OUT = ROOT / "reports" / "dev"
DT = 1 / 30
SEED = 7
T = C.TILE


def free_spot(s: GameState, w: int, h: int) -> tuple[int, int]:
    """Canto de uma área w×h de chão livre perto da cápsula (longe dos 3 tiles em volta dela)."""
    bx, by = C.BASE_TILE
    for dy in range(-8, 12):
        for dx in range(-14, 14):
            x0, y0 = bx + dx, by + dy
            tiles = [(x0 + i, y0 + j) for i in range(w) for j in range(h)]
            if all(s.world.is_floor(*t) and t not in C.POD_TILES and not s.world.vein_at(*t)
                   and not s.world.is_water(*t, s.stage) for t in tiles) and abs(dx) > 3:
                return x0, y0
    raise RuntimeError("sem área livre")


def room(s: GameState, x0: int, y0: int, w: int, h: int, door: tuple[int, int]) -> None:
    """Sala de w×h tiles de chão com parede em volta e uma porta."""
    for y in range(y0 - 1, y0 + h + 1):
        for x in range(x0 - 1, x0 + w + 1):
            if x0 <= x < x0 + w and y0 <= y < y0 + h:
                s.base.add(BaseBlock(C.BASE_FLOOR, x, y))
            elif (x, y) == door:
                s.base.add(BaseBlock(C.BASE_DOOR, x, y))
            else:
                s.base.add(BaseBlock(C.BASE_WALL, x, y))


def frames(app, n: int) -> None:
    for _ in range(n):
        app.step(DT)


def set_stage(app, ti: float) -> None:
    s = app.state
    s.indices.update(o2=float(ti), heat=0.0, water=0.0, biomass=0.0)
    s.stage = stage_for_ti(ti, 0.0)
    s.storm = 0.0
    s.o2 = C.O2_MAX


def shot(app, name: str) -> None:
    frames(app, 6)
    path = OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m2_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)                                   # Úmido
    frames(app, 2)

    # base vedada 5×5 com o Dispersor (2 vazias na saída) e o Coletor logo ao lado
    x0, y0 = free_spot(s, 14, 9)
    x0, y0 = x0 + 1, y0 + 1
    room(s, x0, y0, 5, 5, door=(x0 + 2, y0 + 5))
    disp = Machine(C.DISPENSER, x0 + 1, y0, chip=True)
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 1)
    disp.storage.slots[C.DISPENSER_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    collector = Machine(C.COLLECTOR, x0 + 8, y0 + 3, chip=True)
    collector.storage.slots[C.COLLECTOR_IN_SLOT] = Stack(C.EMPTY_CAPSULE, 3)
    collector.storage.slots[C.COLLECTOR_OUT_SLOT] = Stack("water_capsule", 1)
    s.machines += [disp, collector]
    p = s.player
    p.x, p.y = (x0 + 3.5) * T, (y0 + 3.5) * T
    frames(app, 3)
    assert s.dispenser_state(disp) == "sealed", s.dispenser_state(disp)

    def open_panel(mode: str, machine) -> None:
        app.set_mode("play")
        app.open_dispenser = machine if mode == "dispenser" else None
        app.open_collector = machine if mode == "collector" else None
        app.set_mode(mode)

    open_panel("dispenser", disp)
    shot(app, "v08_m2_dispersor.png")
    app.set_mode("play")

    # Coletor no chão, coletando (o mundo sem painel e depois com ele)
    p.x, p.y = (collector.tx + 0.5) * T, (collector.ty + 2) * T
    frames(app, 10)
    assert s.collector_blocker(collector, s.active) is None and collector.collecting
    app.zoom = 2.0
    shot(app, "v08_m2_coletor_mundo.png")
    open_panel("collector", collector)
    collector.timer = 15.0
    shot(app, "v08_m2_coletor.png")

    # chuva cheia: o ciclo cai pra 13 s e o painel mostra "chuva x3.0"
    s.rain.left, s.rain.intensity = 1e6, 1.0
    collector.timer = 5.0
    shot(app, "v08_m2_coletor_chuva.png")
    s.rain.left, s.rain.intensity = 0.0, 0.0
    app.set_mode("play")

    # Árido: parado, "Precisa do estágio Úmido" (Ti em 7.500)
    s.indices.update(o2=7_500.0)                             # Árido: 7.000 a 10.000 de Ti
    s.stage = stage_for_ti(s.ti, 0.0)
    assert s.stage == C.ARID_STAGE, s.stage
    collector.timer = 0.0
    open_panel("collector", collector)
    shot(app, "v08_m2_coletor_parado.png")
    pygame.quit()


if __name__ == "__main__":
    main()
