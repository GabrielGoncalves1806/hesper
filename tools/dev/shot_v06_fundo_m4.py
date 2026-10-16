"""v0.6 Fundo M4: prints avulsos da broca nv.2, do wafer e do circuito (não entram no smoke).

Gera em reports/dev/v06_fundo_m4/:
  bench_t2_drill.png      Bancada T2 com a receita da nv.2 selecionada, tudo no inventário (nv.1 no slot 0)
  bench_t2_missing.png    a mesma receita sem a nv.1 (o que falta)
  fabricator_materials.png  fabricador T1, aba Materiais, com fios e circuito
  smelter_wafer.png       Fundição fundindo silício, 2 wafers na saída
  chest_logistics.png     painel do baú com os 9 toggles da seção DRONES
  hotbar_t2.png           hotbar com a nv.2 no slot onde estava a nv.1 (depois do craft)
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

OUT = ROOT / "reports" / "dev" / "v06_fundo_m4"
SEED = 7


def save(app, name: str) -> None:
    path = OUT / name
    app.draw()
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def close_panels(app) -> None:
    app.set_mode("play")
    app.open_smelter = app.open_chest = app.open_bench = None
    app.renderer.open_chest = None


def open_bench(app, bench) -> None:
    app.open_bench = bench
    app.fab_bench = "t2"
    app.fab_t2.diag = None
    app.set_mode("fabricator")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_fundo_m4_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    state = app.state
    state.fast = False
    app.set_zoom(1.0, notify=False)
    px, py = state.player.tile
    state.blueprints.add("workbench")                       # a Bancada T2 só sai com o diagrama
    bench = build_now(state, "workbench", (px + 3, py))
    print("  bench", bench is not None, "tile", (px, py))
    state.player.x, state.player.y = (px + 2) * C.TILE, (py + 1) * C.TILE

    # 1) Bancada T2 com a nv.2 selecionada e tudo no inventário (a nv.1 já vem no slot 0)
    state.inventory.add("iron_ingot", 4)
    state.inventory.add("wire", 6)
    state.inventory.add("circuit", 2)
    app.fab_t2.selected[0] = C.T2_RECIPES.index(C.HAND_DRILL_T2)
    open_bench(app, bench)
    save(app, "bench_t2_drill.png")

    # 2) sem a nv.1 (guarda de lado e volta depois)
    state.inventory.remove("hand_drill", 1)
    save(app, "bench_t2_missing.png")
    close_panels(app)

    # 3) fabricador T1, aba Materiais, com fios e circuito (cobre e wafer no inventário)
    state.inventory.add("copper_ingot", 3)
    state.inventory.add("silicon_wafer", 2)
    app.fab_bench = "t1"
    app.open_bench = None
    app.fab.diag = None
    app.fab.tab = [t for t, _ in C.CRAFT_TABS].index("materials")
    app.fab.selected[app.fab.tab] = 1                      # o circuito
    app.set_mode("fabricator")
    save(app, "fabricator_materials.png")
    close_panels(app)

    # 4) Fundição fundindo silício, 2 wafers na saída
    smelter = build_now(state, "smelter", (px + 3, py + 3))
    smelter.chip = True
    smelter.receives = {"silicon", "magmatite"}
    smelter.sends = {"silicon_wafer"}
    smelter.storage.slots[C.SMELTER_ORE_SLOT] = Stack("silicon", 8)
    smelter.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 3)
    smelter.storage.slots[C.SMELTER_OUT_SLOT] = Stack("silicon_wafer", 2)
    smelter.fuel, smelter.timer = 3, C.SMELTER_TIME / 2
    state.inventory.add("silicon", 20)
    app.open_smelter = smelter
    app.set_mode("smelter")
    save(app, "smelter_wafer.png")
    close_panels(app)

    # 5) baú com os 9 toggles
    chest = build_now(state, "chest", (px + 6, py + 3))
    chest.sends = {"iron", "silicon_wafer"}
    chest.receives = {"copper", "silicon", "magmatite"}
    app.open_chest = app.renderer.open_chest = chest
    app.set_mode("chest")
    save(app, "chest_logistics.png")
    close_panels(app)

    # 6) hotbar com a nv.2 no slot da nv.1 (a nv.1 volta pro slot 3 e é consumida no craft)
    state.inventory.slots[3] = Stack("hand_drill", 1)
    for item, n in (("iron_ingot", 4), ("wire", 6), ("circuit", 2)):   # construir a Fundição/baú gastou parte
        state.inventory.add(item, max(0, n - state.inventory.count(item)))
    app.hotbar_selected = 3
    ok = state.craft(C.HAND_DRILL_T2, bench="t2", at=bench)
    print("  craft nv.2:", ok, "slot 3:", state.inventory.slots[3])
    state.player.x, state.player.y = (px + 2) * C.TILE, (py + 1) * C.TILE
    save(app, "hotbar_t2.png")
    pygame.quit()


if __name__ == "__main__":
    main()
