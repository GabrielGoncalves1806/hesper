"""v0.8 M4: prints do Microscópio, da Centrífuga e dos Cultivadores com as plantas (não entra no smoke).

Gera em reports/dev/ (seed 7):
  v08_m4_lab_scan.png               o player escaneando o microscópio quebrado do lab (barra do scan na metade)
  v08_m4_maquinas.png               Microscópio e Centrífuga lado a lado, trabalhando, e um Cultivador com Folha-gota
  v08_m4_painel_microscopio.png     o painel do Microscópio (gelo, barra no meio, 1 simples e 1 rara na saída)
  v08_m4_painel_centrifuga.png      o painel da Centrífuga (algas, amostra com mutação, Espiral-de-geada na saída)
  v08_m4_fabricador.png             o menu do construtor com a Centrífuga travada ("Libera no estágio Algas")
  v08_m4_cultivadores.png           3 Cultivadores com Folha-gota, Espiral-de-geada e Lírio-de-Ilves maduras
  v08_m4_bau_drones.png             o painel de um baú com a seção DRONES (as 16 fileiras de toggle)
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
sys.path.insert(0, str(ROOT / "tools" / "dev"))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings, viewport  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from shot_v08_m3 import OUT, T, free_spot, frames, go, room, set_heat, set_stage, shot  # noqa: E402

SEED = 7
PLANTS = tuple(C.CENT_OUT_SLOTS)


def at_stage(app, stage: int) -> None:
    """Põe o jogo no estágio `stage` (o Ti e a biomassa que ele pede)."""
    s = app.state
    st = C.STAGES[stage - 1]
    set_stage(app, st.ti)
    s.indices["biomass"] = float(st.biomass)
    s.stage = stage


def mature_cultivator(s, x, y, crop: str) -> Machine:
    m = Machine(C.CULTIVATOR, x, y, chip=True)
    m.storage.slots[C.CULT_SEED_SLOT] = Stack(crop, 1)
    m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 5)
    m.sync_crop()
    m.growth, m.tank = 1.0, 5.0
    for slot in C.CULT_HARVEST_SLOTS:
        m.storage.slots[slot] = Stack(crop, 3)
    s.machines.append(m)
    return m


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m4_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    at_stage(app, 3)
    frames(app, 2)

    # ---- o scan do microscópio quebrado do lab (barra na metade)
    set_heat(s, C.LAB_ICE_HEAT[1])
    prop = next(p for p in s.active.props.values() if p.kind == "prop_microscope_digital" and p.ruin)
    s.inventory.slots[C.HOTBAR_SLOTS - 1] = Stack("constructor", 1)
    app.hotbar_selected = C.HOTBAR_SLOTS - 1
    go(app, (prop.tx + 0.5) * T, (prop.ty + 2) * T + 16)
    app.zoom = 2.0
    frames(app, 2)
    px, py = (prop.tx + 0.5) * T, (prop.ty + 0.5) * T
    app.mouse = app.mouse_window = tuple(viewport.world_to_canvas((px, py), app.cam, app.zoom))
    app.mouse_held = True
    s.scanning, s.scan_t = prop, C.SCAN_HOLD * 0.5 - 0.1
    assert s.can_scan(prop)
    shot(app, "v08_m4_lab_scan.png", 3)
    assert s.scanning is prop and 0.4 < s.scan_progress < 0.8, s.scan_progress
    app.mouse_held = False
    s.scanning, s.scan_t = None, 0.0
    app.mouse = app.mouse_window = (20, 20)

    # ---- as máquinas trabalhando, perto de um Cultivador com Folha-gota (estágio Algas)
    at_stage(app, 4)
    x0, y0 = free_spot(s, 12, 9)
    x0, y0 = x0 + 1, y0 + 1
    room(s, x0, y0, 8, 5, door=(x0 + 3, y0 + 5))
    s.machines.append(Machine("solar", x0, y0))
    s.machines.append(Machine("solar", x0 + 7, y0))
    mic = Machine(C.MICROSCOPE, x0 + 1, y0 + 2, chip=True)
    mic.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 14)
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 3)
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", 1)
    mic.timer = C.MICROSCOPE_TIME * 0.4
    cent = Machine(C.CENTRIFUGE, x0 + 3, y0 + 2, chip=True)
    cent.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 5)
    cent.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_mutant", 2)
    cent.storage.slots[C.CENT_OUT_SLOTS["plant_1"]] = Stack("plant_1", 4)
    cent.timer = C.CENTRIFUGE_TIME * 0.4
    s.machines += [mic, cent]
    cult = mature_cultivator(s, x0 + 5, y0 + 2, "plant_1")
    go(app, (x0 + 4.0) * T, (y0 + 3.6) * T)
    app.mouse = app.mouse_window = (480, 480)
    app.zoom = 2.0
    frames(app, 6)
    assert s.microscope_blocker(mic) is None and s.centrifuge_blocker(cent) is None and s.power.factor >= 1
    assert mic.analyzing and cent.spinning, (mic.analyzing, cent.spinning)
    shot(app, "v08_m4_maquinas.png", 4)
    assert mic.analyzing and cent.spinning

    # ---- os painéis
    app.mouse = app.mouse_window = (20, 20)
    s.inventory.add("ice", 10)
    s.inventory.add("algae", 3)
    s.inventory.add("sample_basic", 1)
    mic.sends, mic.receives = set(C.SAMPLE_ITEMS), {"ice"}
    mic.timer = C.MICROSCOPE_TIME * 0.5
    app.open_microscope = mic
    app.set_mode("microscope")
    shot(app, "v08_m4_painel_microscopio.png")
    app.set_mode("play")
    cent.sends, cent.receives = set(PLANTS), {"algae", "sample_basic", "sample_mutant"}
    cent.storage.slots[C.CENT_OUT_SLOTS["plant_1"]] = None
    cent.storage.slots[C.CENT_OUT_SLOTS["plant_2"]] = Stack("plant_2", 1)
    cent.timer = C.CENTRIFUGE_TIME * 0.4
    app.open_centrifuge = cent
    app.set_mode("centrifuge")
    shot(app, "v08_m4_painel_centrifuga.png")
    app.set_mode("play")

    # ---- o construtor com a Centrífuga travada (estágio Úmido, abaixo das Algas)
    at_stage(app, 3)
    s.machines.remove(cent)
    s.machines.remove(mic)
    s.inventory.add("iron_ingot", 10)
    s.inventory.add("copper_ingot", 4)
    s.inventory.add("wire", 6)
    s.blueprints.add("microscope")
    assert s.recipe_status(C.CENTRIFUGE) == "locked", s.recipe_status(C.CENTRIFUGE)
    app.build_menu.select(C.CENTRIFUGE)
    app.set_mode("build")
    shot(app, "v08_m4_fabricador.png")
    app.set_mode("play")

    # ---- 3 Cultivadores dentro da base com as plantas maduras
    at_stage(app, 6)
    s.machines.remove(cult)
    cults = [mature_cultivator(s, x0 + 1 + 2 * i, y0 + 2, crop) for i, crop in enumerate(PLANTS)]
    go(app, (x0 + 3.6) * T, (y0 + 3.6) * T)
    app.mouse = app.mouse_window = (480, 480)
    app.zoom = 2.0
    shot(app, "v08_m4_cultivadores.png")
    assert [m.crop_stage for m in cults] == [3, 3, 3], [m.crop_stage for m in cults]

    # ---- o baú com a seção DRONES (16 fileiras de toggle)
    chest = Machine("chest", x0 + 6, y0 + 4, chip=True, name="Amostras")
    s.machines.append(chest)
    chest.sends = {"sample_basic", "plant_1"}
    chest.receives = {"ice", "algae"}
    app.mouse = app.mouse_window = (20, 20)
    app.open_chest = app.renderer.open_chest = chest
    app.set_mode("chest")
    shot(app, "v08_m4_bau_drones.png")
    app.set_mode("play")
    pygame.quit()


if __name__ == "__main__":
    main()
