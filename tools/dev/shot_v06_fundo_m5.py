"""v0.6 Fundo M5: prints avulsos do remapeamento de crafts (não entram no smoke).

Gera em reports/dev/v06_fundo_m5/:
  bench_tab_bancada.png     Bancada T2, aba "Bancada" (as exclusivas), com o wafer selecionado
  bench_tab_materiais.png   Bancada T2, aba Materiais (os fios do T1)
  bench_made.png            Bancada T2 com a mochila já fabricada ("feito" na lista, "JÁ FEITO" no botão)
  fab_t1_tools.png          fabricador T1, aba Ferramentas (construtor "feito", diagrama do baú grande)
  smelter_3to1.png          Fundição com 6 ferro e o estado "3:1 A CADA 15 S"
  chest_logistics.png       painel do baú com os 8 toggles da seção DRONES
  build_dispenser.png       menu do construtor com o Dispersor selecionado (custo longo)
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

OUT = ROOT / "reports" / "dev" / "v06_fundo_m5"
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


def open_bench(app, bench, kind: str) -> None:
    app.open_bench = bench
    app.fab_bench = "t2"
    app.fab_t2.diag = None
    app.fab_t2.select(kind)
    app.set_mode("fabricator")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v06_fundo_m5_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    state = app.state
    state.fast = False
    app.set_zoom(1.0, notify=False)
    state.debug_add_ti(100_000)                              # as receitas de Ti alto destravadas
    px, py = state.player.tile
    state.blueprints.add("workbench")
    bench = build_now(state, "workbench", (px + 3, py))
    print("  bench", bench is not None, "tile", (px, py))
    state.player.x, state.player.y = (px + 2) * C.TILE, (py + 1) * C.TILE

    # 1) Bancada T2, aba "Bancada", wafer selecionado, 10 silício no inventário
    state.inventory.add("silicon", 10)
    open_bench(app, bench, "silicon_wafer")
    save(app, "bench_tab_bancada.png")

    # 2) aba Materiais da Bancada (os fios, 3 por lingote de cobre)
    state.inventory.add("copper_ingot", 4)
    app.fab_t2.select("wire")
    save(app, "bench_tab_materiais.png")
    close_panels(app)

    # 3) mochila já fabricada: "feito" na lista e "JÁ FEITO" no botão
    state.inventory.add("iron_ingot", 5)
    ok = state.craft("backpack", bench="t2", at=bench)
    print("  craft mochila:", ok)
    open_bench(app, bench, "backpack")
    save(app, "bench_made.png")
    close_panels(app)

    # 4) fabricador T1, aba Ferramentas: o construtor "feito" e o diagrama do baú grande (4 lingotes + 1 circuito)
    state.inventory.add("iron_ingot", 4)
    state.inventory.add("circuit", 1)
    app.fab_bench = "t1"
    app.open_bench = None
    app.fab.diag = None
    app.fab.select("diagram_chest_large")
    app.set_mode("fabricator")
    save(app, "fab_t1_tools.png")
    close_panels(app)

    # 5) Fundição 3:1 com 6 ferro e magmatita
    smelter = build_now(state, "smelter", (px + 3, py + 3))
    smelter.chip = True
    smelter.receives = {"iron", "magmatite"}
    smelter.sends = {"iron_ingot"}
    smelter.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 6)
    smelter.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 3)
    smelter.fuel, smelter.timer = 3, C.SMELTER_TIME / 2
    state.inventory.add("iron", 20)
    app.open_smelter = smelter
    app.set_mode("smelter")
    save(app, "smelter_3to1.png")
    close_panels(app)

    # 6) baú com os 8 toggles (o wafer saiu)
    chest = build_now(state, "chest", (px + 6, py + 3))
    chest.sends = {"iron", "iron_ingot"}
    chest.receives = {"copper", "silicon", "magmatite"}
    app.open_chest = app.renderer.open_chest = chest
    app.set_mode("chest")
    save(app, "chest_logistics.png")
    close_panels(app)

    # 7) construtor: Dispersor selecionado (5 linhas de custo), com o material no inventário
    for item, n in (("circuit", 3), ("chip", 2), ("iron_ingot", 15), ("wire", 5), ("water_capsule", 2)):
        state.inventory.add(item, n)
    if state.inventory.count("constructor") == 0:
        state.inventory.add("constructor", 1)
    app.build_menu.select(C.DISPENSER)
    app.set_mode("build")
    save(app, "build_dispenser.png")
    # o mesmo sem material (linha "FALTAM ...")
    for item in ("circuit", "chip", "iron_ingot", "wire", "water_capsule"):
        state.inventory.remove(item, state.inventory.count(item))
    save(app, "build_dispenser_missing.png")
    close_panels(app)
    pygame.quit()


if __name__ == "__main__":
    main()
