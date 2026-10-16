"""v0.7 Lore M2: prints avulsos dos props e do scanner (não entra no smoke).

Gera em reports/dev/v07_m2/ (seed 3, salvo o item 8):
  1. camp.png, lab.png, melters.png, drill_post.png   as 4 ruínas com os props de dentro
  2. base_props.png                                   uma base do player com props de chão, mesas de parede e de face
  3. scan_contorno.png                                contorno + dica "Escanear (segure)" num prop de ruína
  4. scan_barrinha.png                                a barrinha no meio do scan
  5. decoracao_4.png, decoracao_7.png                 aba Decoração só com os 4 de cara, e com mais 3 depois do scan
  6. ghost_face_verde.png, ghost_face_vermelho.png    fantasma de um prop de face (parede com face / sem face)
  8. ruina_prop_na_parede_sul.png                     ruína com prop de chão colado na parede ao sul (decisão do dono)
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
from game import layers, settings, viewport  # noqa: E402
from game.base import BaseBlock  # noqa: E402
from game.props import Prop  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v07_m2"
DT = 1 / 30
SEED = 3
T = C.TILE


def new_app(seed: int):
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=seed))
    app.set_zoom(1.0, notify=False)
    app.state.storm = 0.0                                    # sem poeira de tempestade
    return app


def frames(app, n: int) -> None:
    for _ in range(n):
        app.step(DT)


def put_player(app, tile) -> None:
    p = app.state.player
    p.x, p.y = (tile[0] + 0.5) * T, (tile[1] + 1) * T - 2


def aim(app, wx: float, wy: float) -> None:
    """Põe o mouse (canvas) em cima do ponto do mundo."""
    app.mouse = tuple(round(v) for v in viewport.world_to_canvas((wx, wy), app.cam, app.zoom))


def hold_constructor(app) -> None:
    s = app.state
    if s.inventory.count("constructor") == 0:
        s.inventory.add("constructor", 1)
    index = next(i for i, st in enumerate(s.inventory.slots[:C.HOTBAR_SLOTS]) if st and st.item == "constructor")
    app.select_hotbar(index)


def save_shot(app, name: str) -> None:
    path = OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def inside_tile(ruin):
    """Um chão da ruína perto do centro, sem prop nem máquina."""
    cx, cy = ruin.center
    floors = [(ruin.tx + x, ruin.ty + y) for y, row in enumerate(ruin.grid) for x, ch in enumerate(row) if ch == "."]
    free = [t for t in floors if t not in ruin.props and t not in ruin.machines]
    return min(free, key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)


def ruin_shots(app) -> None:
    state = app.state
    darkness = app.renderer.draw_cave_darkness
    cave = layers.make_cave(SEED)
    state.layers[layers.CAVE] = cave
    for layer_key in (layers.SURFACE, layers.CAVE):
        state.enter_layer(layer_key, layers.ramp_arrival(state.layers[layer_key].world))
        app.renderer.draw_cave_darkness = (lambda *a, **k: None) if layer_key == layers.CAVE else darkness   # só pro print
        for ruin in state.world.ruins:
            put_player(app, inside_tile(ruin))
            frames(app, 20)
            save_shot(app, f"{ruin.key}.png")
    app.renderer.draw_cave_darkness = darkness
    state.enter_layer(layers.SURFACE, layers.ramp_arrival(state.surface.world))


def scan_shots(app) -> None:
    state = app.state
    ruin = next(r for r in state.world.ruins if r.key == "camp")
    tile, kind = next((t, k) for t, k in ruin.props.items() if C.PROPS[k].scannable and C.PROPS[k].place == "floor")
    prop = state.prop_at(tile)
    put_player(app, (tile[0], tile[1] + 2))
    hold_constructor(app)
    frames(app, 5)
    aim(app, tile[0] * T + 16, tile[1] * T + 14)
    frames(app, 5)
    assert state.can_scan(prop) and app.hint() == "Escanear (segure)", app.hint()
    save_shot(app, "scan_contorno.png")
    app.mouse_held = True
    frames(app, 18)                                           # ~0,6 s de 1,5 s
    assert state.scanning is prop and 0.2 < state.scan_progress < 0.8
    save_shot(app, "scan_barrinha.png")
    frames(app, 30)
    assert kind in state.scanned
    app.mouse_held = False
    print("  aviso:", app.notice)
    frames(app, 3)


def menu_shots(app) -> None:
    state = app.state
    state.scanned.clear()
    app.open_build_menu()
    app.build_menu.set_tab([t for t, _ in C.FAB_TABS].index("decor"))
    frames(app, 6)
    assert app.build_menu.kinds == list(C.PROP_STARTER)
    save_shot(app, "decoracao_4.png")
    app.notice_time = 0.0
    state.scanned.update({"prop_barrel", "prop_bunk", "wall_notice"})
    frames(app, 6)
    assert len(app.build_menu.kinds) == 7
    save_shot(app, "decoracao_7.png")
    app.mode = "play"
    app.set_mode("play")


def room(state, ox: int, oy: int, w: int, h: int) -> None:
    """Sala de w×h de chão em (ox, oy) com parede em volta e uma porta ao sul (direto na grade, sem custo)."""
    for y in range(oy - 1, oy + h + 1):
        for x in range(ox - 1, ox + w + 1):
            inside = ox <= x < ox + w and oy <= y < oy + h
            if inside:
                state.base.add(BaseBlock(C.BASE_FLOOR, x, y))
            elif (x, y) == (ox + w // 2, oy + h):
                state.base.add(BaseBlock(C.BASE_DOOR, x, y))
            else:
                state.base.add(BaseBlock(C.BASE_WALL, x, y))


def base_shots(app) -> None:
    state = app.state
    app.notice_time = 0.0                                     # sem o aviso do scan na frente
    put_player(app, (int(C.SPAWN_POS[0] // T), int(C.SPAWN_POS[1] // T)))   # a base nasce perto da cápsula, não da ruína
    px, py = state.player.tile
    ox, oy = px + 3, py + 2
    room(state, ox, oy, 9, 4)
    put = lambda kind, dx, dy: state.active.props.__setitem__((ox + dx, oy + dy), Prop(kind, ox + dx, oy + dy))   # noqa: E731
    put("prop_wall_desk_a", 1, 0)
    put("wall_monitor_on", 1, -1)
    put("prop_wall_desk_b", 3, 0)
    put("wall_bp_plan", 3, -1)
    put("wall_notice", 6, -1)
    put("prop_bunk", 7, 0)
    put("prop_locker", 8, 0)
    put("prop_table", 4, 2)
    put("prop_chair", 3, 2)
    put("prop_chair", 5, 2)
    put("prop_barrel", 0, 3)
    put("prop_dead_plant", 8, 3)
    put("prop_lab_bench", 6, 2)
    put("prop_microscope", 1, 2)
    put_player(app, (ox + 4, oy + 5))
    app.mouse = (20, 20)
    frames(app, 20)
    save_shot(app, "base_props.png")
    # fantasma de prop de face: verde numa parede com face, vermelho numa parede sem face (outra parede em cima dela)
    state.scanned.add("wall_notice")
    wall_a = (ox + 10, oy + 1)                                # parede lateral: face visível (embaixo é chão... a parede)
    for tile in ((ox + 10, oy - 1), (ox + 10, oy - 2)):
        state.base.add(BaseBlock(C.BASE_WALL, *tile))
    state.inventory.add("iron", 20)
    state.inventory.add("silicon", 5)
    hold_constructor(app)
    put_player(app, (ox + 8, oy + 1))
    app.placing = "wall_notice"
    ok_tile, bad_tile = (ox + 10, oy - 1), (ox + 10, oy - 2)  # embaixo de bad_tile tem parede: sem face
    for name, tile in (("verde", ok_tile), ("vermelho", bad_tile)):
        aim(app, tile[0] * T + 16, tile[1] * T + 20)
        frames(app, 10)
        want = name == "verde"
        assert state.can_build("wall_notice", tile) == want, (name, tile)
        save_shot(app, f"ghost_face_{name}.png")
    app.placing = None
    del wall_a


def south_wall_shot() -> None:
    """Procura uma ruína da superfície com prop de chão colado na parede ao sul e tira o print dela."""
    for seed in range(1, 60):
        world = layers.make_surface(seed).world
        for ruin in world.ruins:
            for (tx, ty), kind in ruin.props.items():
                if C.PROPS[kind].place != "floor" or kind in ("prop_sign", "prop_chair", "prop_chair_fallen"):
                    continue                                  # os baixinhos não mostram a face cobrindo
                x, y = tx - ruin.tx, ty - ruin.ty
                if y + 1 >= len(ruin.grid) or ruin.grid[y + 1][x] != "#":
                    continue
                side = next(((ruin.tx + gx, ruin.ty + gy) for gy in range(max(0, y - 2), y) for gx in range(max(0, x - 3), min(len(ruin.grid[0]), x + 4))
                             if ruin.grid[gy][gx] == "." and (ruin.tx + gx, ruin.ty + gy) not in ruin.props and y - gy >= 2), None)   # 2+ tiles acima, fora da frente do prop
                if side is not None:
                    app = new_app(seed)
                    app.set_zoom(1.5, notify=False)
                    put_player(app, side)
                    frames(app, 20)
                    save_shot(app, "ruina_prop_na_parede_sul.png")
                    print(f"  (seed {seed}, {ruin.key}, {kind} em {(tx, ty)})")
                    return
    raise SystemExit("nenhuma ruína com prop colado na parede sul")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v07_m2_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    app = new_app(SEED)
    ruin_shots(app)
    scan_shots(app)
    menu_shots(app)
    base_shots(app)
    south_wall_shot()
    pygame.quit()


if __name__ == "__main__":
    main()
