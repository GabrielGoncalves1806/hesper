"""v0.8 M3: prints do laboratório da Ilves e do Cultivador (não entra no smoke).

Gera em reports/dev/ (seed 7):
  v08_m3_lab_fechado.png        o laboratório com o gelo na porta (calor abaixo da faixa)
  v08_m3_lab_aberto.png         o laboratório por dentro, aberto, com o tanque e o microscópio quebrados e o player na caixa
  v08_m3_cultivador_etapas.png  4 cultivadores com alga dentro da base, um em cada etapa (0 a 3)
  v08_m3_painel.png             o painel do Cultivador (alga, etapa 3/4, tanque 3/5, colheita com algas)
  v08_m3_seco.png               um Cultivador seco (sem água)
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
from game import ruins, settings  # noqa: E402
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


def shot(app, name: str, n: int = 6) -> None:
    app.state.rain.next_shower, app.state.rain.left, app.state.rain.intensity = 1e9, 0.0, 0.0   # sem chuva atrapalhando
    app.banner_time = 99.0                                   # nem o banner de estágio
    frames(app, n)
    path = OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def go(app, x: float, y: float) -> None:
    app.state.player.x, app.state.player.y = x, y


def set_heat(s: GameState, heat: float) -> None:
    s.indices["heat"] = heat
    s._apply_thaw()
    s.events.clear()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m3_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)                                   # Úmido
    frames(app, 2)

    # ---- o laboratório fechado: gelo inteiro na porta, calor abaixo da faixa
    lab = ruins.lab_of(s.world)
    dx, dy = ruins.lab_door_px(s.world)
    set_heat(s, C.LAB_ICE_HEAT[0] - 1)
    assert not s.active.lab_ice_open and s.active.lab_ice_p == 0.0
    app.zoom = 2.0
    go(app, dx, dy + 1.3 * T)
    shot(app, "v08_m3_lab_fechado.png", 12)

    # ---- aberto: o gelo derreteu, o player na caixa por dentro
    set_heat(s, C.LAB_ICE_HEAT[1])
    assert s.active.lab_ice_open
    cx, cy = lab.crate
    go(app, (cx + 0.5) * T, (cy + 2) * T)
    app.zoom = 2.0
    shot(app, "v08_m3_lab_aberto.png", 12)

    # ---- 4 cultivadores com alga, um em cada etapa, numa base vedada
    x0, y0 = free_spot(s, 12, 9)
    x0, y0 = x0 + 1, y0 + 1
    room(s, x0, y0, 8, 5, door=(x0 + 3, y0 + 5))
    disp = Machine(C.DISPENSER, x0, y0, chip=True)
    disp.storage.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", 5)
    s.machines.append(disp)
    growths = (0.05, 0.40, 0.72, 1.0)
    cults = []
    for i, g in enumerate(growths):
        m = Machine(C.CULTIVATOR, x0 + 1 + 2 * i, y0 + 2, chip=True)
        m.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
        m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 5)
        m.sync_crop()                                        # (a muda entrou depois do nascimento: sem isso a planta zera)
        m.growth, m.tank = g, 5.0
        if g >= 1.0:                                         # madura e a colheita cheia: fica parada na etapa 3
            for slot in C.CULT_HARVEST_SLOTS:
                m.storage.slots[slot] = Stack("algae", C.STACK_LOOT)
        cults.append(m)
    s.machines += cults
    go(app, (x0 + 6.3) * T, (y0 + 3.4) * T)                 # a câmera um pouco à direita: as 4 máquinas ficam longe do painel do Ti
    app.mouse = app.mouse_window = (480, 480)                # o mouse no chão da sala (sem a dica da parede)
    app.zoom = 2.0
    frames(app, 3)
    assert [m.crop_stage for m in cults] == [0, 1, 2, 3], [m.crop_stage for m in cults]
    shot(app, "v08_m3_cultivador_etapas.png")

    # ---- o painel: alga na etapa 3/4, tanque 3/5, colheita com algas
    m = cults[2]
    m.growth, m.tank = 0.70, 3.0
    m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    m.storage.slots[C.CULT_EMPTY_SLOT] = Stack(C.EMPTY_CAPSULE, 2)
    m.storage.slots[C.CULT_HARVEST_SLOTS[0]] = Stack("algae", 2)
    s.inventory.add("algae", 3)
    s.inventory.add("water_capsule", 4)
    app.open_cultivator = m
    app.set_mode("cultivator")
    shot(app, "v08_m3_painel.png")
    app.set_mode("play")

    # ---- seco: o 2º cultivador sem água (tanque e reserva vazios)
    dry = cults[1]
    dry.tank = 0.0
    dry.storage.slots[C.CULT_WATER_SLOT] = None
    go(app, (dry.tx + 0.5) * T, (dry.ty + 1.35) * T)
    app.zoom = 3.0
    frames(app, 3)
    assert s.cultivator_blocker(dry, s.active) == "dry"
    shot(app, "v08_m3_seco.png")
    pygame.quit()


if __name__ == "__main__":
    main()
