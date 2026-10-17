"""v0.8 M5: prints dos materiais e itens (não entra no smoke). Headless (driver dummy): não abre janela.

Gera em reports/dev/ (seed 7):
  v08_m5_bancada.png         a Bancada T2 na aba Bancada, com os materiais no inventário
  v08_m5_tab.png             o Tab com a Mochila T2, o tanque nv.2 e as botas equipados
  v08_m5_luminarias.png      a caverna escura com a luminária comum, a forte e a bio lado a lado
  v08_m5_adubo.png           o painel do Cultivador com o selo do adubo
  v08_m5_drones.png          uma estação com 1 drone nv.1 e 1 nv.2 voando
  v08_m5_bau_grande_t2.png   o baú grande aberto com a T2 e os 16 toggles de Envia e Recebe (escala Grande, 480×270)
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
from game import drones, layers, settings  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402
from shot_v08_m3 import T, free_spot, frames, go, set_stage, shot  # noqa: E402
from tests.helpers import give  # noqa: E402

SEED = 7
HOT = [("hand_drill_t2", 1), ("fiber", 12), ("hydrogel", 4), ("frost_resin", 3), ("water_capsule", 5),
       ("fertilizer", 2), ("lamp_bio", 3), ("ice", 40)]
INV = [("algae", 9), ("plant_1", 4), ("plant_2", 2), ("plant_3", 1), ("lily_essence", 1), ("iron", 22),
       ("silicon", 18), None]
BAG1 = [("copper", 31), ("iron_ingot", 12), ("drone_t2", 2), None, None, None, None, None]
BAG2 = [("ice", 50), ("silicon_wafer", 6), None, None, None, None, None, None]
FULL32 = [("iron", 50), ("copper", 50), ("silicon", 44), ("ice", 50), ("algae", 20), ("plant_1", 8),
          ("plant_2", 5), ("plant_3", 3)]


def equip(s, items) -> None:
    for item in items:
        give(s, **{item: 1})
        i = next(k for k, st in enumerate(s.inventory.slots) if st and st.item == item)
        assert s.equip_from(i), item


def put(s, rows) -> None:
    for i, it in enumerate(rows):
        s.inventory.slots[i] = Stack(*it) if it else None


def main() -> None:
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v08_m5_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=SEED))
    app.mouse = app.mouse_window = (20, 20)
    s = app.state
    set_stage(app, 10_000)
    frames(app, 2)

    # ---- a Bancada T2 (aba Bancada) com os materiais no inventário
    equip(s, ("backpack", "o2_tank"))
    put(s, HOT + INV + BAG1)
    bench = Machine("workbench", 0, 0)
    app.open_bench = bench
    app.fab_bench = "t2"
    app.fab_t2.diag = None
    app.fab_t2.set_tab(0)
    kinds = app.fab_t2.kinds
    app.fab_t2.selected[0] = kinds.index(C.BACKPACK_T2) if C.BACKPACK_T2 in kinds else 0
    app.set_mode("fabricator")
    shot(app, "v08_m5_bancada.png")
    app.set_mode("play")
    app.open_bench = None

    # ---- o Tab com a Mochila T2, tanque nv.2 e botas, 32 casas cheias
    equip(s, (C.BACKPACK_T2, C.O2_TANK_T2, C.BOOTS))
    assert len(s.inventory) == 32
    put(s, HOT + INV + BAG1 + BAG2)
    for i in range(32):
        if s.inventory.slots[i] is None:
            s.inventory.slots[i] = Stack(*FULL32[i % 8])
    app.hotbar_selected = 1
    app.set_mode("inventory")
    shot(app, "v08_m5_tab.png")
    app.set_mode("play")

    # ---- o painel do Cultivador com o selo do adubo
    m = Machine(C.CULTIVATOR, 0, 0, chip=True)
    m.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    m.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 2)
    m.sync_crop()
    m.growth, m.tank, m.boost = 0.70, 3.0, 100.0
    app.open_cultivator = m
    app.set_mode("cultivator")
    shot(app, "v08_m5_adubo.png")
    app.set_mode("play")
    app.open_cultivator = None

    # ---- o baú grande aberto com a T2 (mostra o conserto do painel na escala Grande)
    x0, y0 = free_spot(s, 8, 6)
    chest = Machine("chest_large", x0 + 2, y0 + 2, chip=True, name="Baú grande")
    for i, it in enumerate(FULL32 + [("fiber", 20), ("hydrogel", 12), ("frost_resin", 9)]):
        chest.storage.slots[i] = Stack(*it)
    chest.sends = {"algae", "plant_1", "fiber", "sample_basic"}
    chest.receives = {"ice", "iron", "hydrogel"}
    s.machines.append(chest)
    go(app, (x0 + 2.5) * T, (y0 + 4) * T)
    app.open_chest = app.renderer.open_chest = chest
    app.set_mode("chest")
    shot(app, "v08_m5_bau_grande_t2.png")
    app.set_mode("play")
    app.open_chest = app.renderer.open_chest = None

    # ---- a estação com 1 drone nv.1 e 1 nv.2 voando
    st_x, st_y = free_spot(s, 10, 6)
    st = Machine("drone_station", st_x + 3, st_y + 2, chip=True)
    st.station = drones.new_station(st)
    drones.dock(st, st.station)
    drones.dock(st, st.station, tier=2)
    s.machines.append(st)
    for k in range(2):
        s.machines.append(Machine("drill", st_x + 8, st_y + 1 + 2 * k, resource="iron", stored_init=12,
                                  sends={"iron"}, batch=5, chip=True))
    s.machines.append(Machine("chest", st_x, st_y + 3, receives={"iron"}))
    s.machines.append(Machine("solar", st_x + 3, st_y + 5))
    app.zoom = 2.0
    app.mouse = app.mouse_window = (480, 480)
    go(app, (st_x + 6.0) * T, (st_y + 3.0) * T)
    flying = False
    for _ in range(600):
        frames(app, 1)
        air = [d for d in st.station.drones if d.state in (drones.OUTBOUND, drones.CARRYING, drones.RETURNING)]
        far = [d for d in air if abs(d.x - (st.tx + 1) * T) + abs(d.y - (st.ty + 1) * T) > 2 * T]
        if len(far) == 2:
            flying = True
            break
    assert flying, [(d.tier, d.state, d.x, d.y) for d in st.station.drones]
    print("  drones:", [(d.tier, d.state, round(d.x), round(d.y)) for d in st.station.drones], "station", st.tx, st.ty, "cam", app.cam)
    shot(app, "v08_m5_drones.png", 0)

    # ---- a caverna escura com as 3 luminárias lado a lado
    s.enter_layer(layers.CAVE)
    s.player.x, s.player.y = layers.ramp_arrival(s.world)
    frames(app, 2)
    px, py = s.player.tile
    spots = [(tx, ty) for ty in range(py - 6, py + 6) for tx in range(px - 8, px + 14)
             if all(s.world.is_floor(tx + dx, ty) and not s.world.is_wall(tx + dx, ty) for dx in range(-1, 2))]
    cx, cy = s.world.crater
    far = [t for t in spots if abs(t[0] - cx) + abs(t[1] - cy) >= 14] or spots     # longe da luz da rampa
    base = next((t for t in far if (t[0] + 3, t[1]) in spots and (t[0] + 6, t[1]) in spots), None)
    assert base is not None, "sem chão pras 3 luminárias"
    for k, kind in enumerate(("lamp", "lamp_t2", C.LAMP_BIO)):
        s.machines.append(Machine(kind, base[0] + 3 * k, base[1]))
    go(app, (base[0] + 3.5) * T, (base[1] + 2.0) * T)          # no meio das 3, um pouco à frente
    app.zoom = 1.5
    shot(app, "v08_m5_luminarias.png", 4)
    pygame.quit()


if __name__ == "__main__":
    main()
