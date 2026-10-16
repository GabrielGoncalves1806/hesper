"""v0.6 Fundo M3: print avulso da Fundição (não entra no smoke).

Gera em reports/dev/v06_fundo_m3/:
  smelter_working.png   painel aberto com ferro, magmatita, 2 lingotes e a barra no meio
  smelter_no_fuel.png   status "SEM MAGMATITA"
  smelter_out_busy.png  lingote de ferro na saída e cobre na entrada ("SAÍDA OCUPADA")
  chest_logistics.png   painel do baú com os 8 toggles da seção DRONES
  smelter_world.png     a Fundição de fallback no chão da superfície, acesa, ao lado de um derretedor
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
from game.inventory import Stack  # noqa: E402
from game.systems import GameState  # noqa: E402
from tests.helpers import build_now  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v06_fundo_m3"
DT = 1 / 30
SEED = 7


def save(app, name: str) -> None:
    path = OUT / name
    app.draw()
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def open_smelter(app, smelter) -> None:
    app.open_smelter = smelter
    app.set_mode("smelter")


def close_panels(app) -> None:
    app.set_mode("play")
    app.open_smelter = app.open_chest = None
    app.renderer.open_chest = None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_fundo_m3_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    state = app.state
    state.fast = False
    app.set_zoom(1.0, notify=False)
    px, py = state.player.tile
    smelter = build_now(state, "smelter", (px + 3, py))
    melter = build_now(state, "melter", (px + 1, py))
    print("  smelter", smelter is not None, "melter", melter is not None, "tile", (px, py))
    smelter.chip = True
    smelter.receives = {"iron", "copper", "magmatite"}
    smelter.sends = {"iron_ingot", "copper_ingot"}

    # 1) trabalhando: ferro, magmatita, 2 lingotes, barra no meio, 3 de 4 da carga acesa
    smelter.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 12)
    smelter.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 3)
    smelter.storage.slots[C.SMELTER_OUT_SLOT] = Stack("iron_ingot", 2)
    smelter.fuel, smelter.timer = 3, C.SMELTER_TIME / 2
    state.inventory.add("iron", 40)
    state.inventory.add("magmatite", 8)
    open_smelter(app, smelter)
    save(app, "smelter_working.png")

    # 2) sem magmatita
    smelter.storage.slots[C.SMELTER_FUEL_SLOT] = None
    smelter.fuel, smelter.timer = 0, 0.0
    save(app, "smelter_no_fuel.png")

    # 3) saída ocupada: lingote de ferro na saída e cobre na entrada
    smelter.storage.slots[C.SMELTER_ORE_SLOT] = Stack("copper", 5)
    smelter.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 2)
    smelter.storage.slots[C.SMELTER_OUT_SLOT] = Stack("iron_ingot", 3)
    save(app, "smelter_out_busy.png")
    close_panels(app)

    # 4) baú com os 8 toggles (Envia e Recebe ligados em alguns, pra ver o estado ligado)
    chest = build_now(state, "chest", (px + 3, py + 3))
    chest.sends = {"iron", "iron_ingot"}
    chest.receives = {"copper", "copper_ingot", "magmatite"}
    app.open_chest = app.renderer.open_chest = chest
    app.set_mode("chest")
    save(app, "chest_logistics.png")
    close_panels(app)

    # 5) mundo: Fundição acesa (fundindo) ao lado do derretedor, escala de referência
    smelter.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 12)
    smelter.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 3)
    smelter.storage.slots[C.SMELTER_OUT_SLOT] = None
    smelter.fuel = 3
    state.player.x, state.player.y = (px + 2.5) * C.TILE, (py + 3) * C.TILE
    app.set_zoom(2.0, notify=False)
    for _ in range(20):
        app.step(DT)
    save(app, "smelter_world.png")
    print("  Fundição:", smelter.smelter_blocker, "· derretedor:", melter.kind)
    pygame.quit()


if __name__ == "__main__":
    main()
