"""Captura os insumos dos mockups de UI (reports/design/ui_redesign/_src/): o MUNDO sem HUD,
os ícones de item 32×32 e as prévias de máquina, exatamente como o jogo desenha.

    uv run python tools/sprites/ui_capture.py

Só lê o jogo (não mexe em game/). Roda sem janela (SDL dummy), com save/settings temporários.
Depois disso o tools/sprites/ui_mockups.py (python3 do sistema, PIL) monta os mockups.
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
from game import save, settings  # noqa: E402
from game.app import App  # noqa: E402
from game.systems import Machine  # noqa: E402

settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_uicap_settings.json"
save.SAVE_PATH = Path(tempfile.gettempdir()) / "hesper_uicap_save" / "slot1.json"
OUT = ROOT / "reports" / "design" / "ui_redesign" / "_src"
DT = 1 / 60


def frames(app, seconds):
    for _ in range(max(1, round(seconds / DT))):
        app.step(DT)


def put(state, kind, tile):
    """Máquina direto na lista (sem checar alcance do player): é só cenário."""
    m = Machine(kind, tile[0], tile[1], 0)
    if m.is_chest:
        m.name = C.CHEST_DEFAULT_NAME
    state.machines.append(m)
    state.transition_sources.add(tuple(tile))


def world_shot(app, name):
    s = app.state
    cam = app.renderer.camera(s)
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    app.renderer.draw(canvas, s, cam, app.t, None)
    pygame.image.save(canvas, str(OUT / name))
    print("  ", name)


def explored_mask(world, centers):
    """Explorado de mentira, mas plausível e fixo: bolhas em volta de cada centro (tx, ty, raio),
    com borda tremida por uma conta determinística."""
    seen = set()
    for cx, cy, r in centers:
        rr = 21 if r < 0 else r
        for y in range(int(cy - rr - 3), int(cy + rr + 4)):
            for x in range(int(cx - rr - 3), int(cx + rr + 4)):
                if 0 <= x < world.width and 0 <= y < world.height:
                    if r < 0:                        # retângulo da tela (superfície: ±20×±12 tiles)
                        if abs(x - cx) <= 20 and abs(y - cy) <= 12:
                            seen.add((x, y))
                        continue
                    wob = ((x * 7 + y * 13) % 5) / 5 * 2.5
                    if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 < r + wob:
                        seen.add((x, y))
    return seen


def map_layers(s):
    """Textura inteira de cada camada (tile_color onde foi visto, preto no resto) + marcadores em JSON."""
    import json
    from game.minimap import UNSEEN, tile_color
    data = {}
    for key in ("surface", "cave"):
        s.enter_layer(key)
        w = s.world
        pod = C.POD_TILES[0]
        cr = w.crater
        if key == "surface":
            centers = [(pod[0] + 1, pod[1], -1), (cr[0] + 1, cr[1] + 1, -1) if cr else (pod[0], pod[1], -1)]
            # trilhas até os 2 destroços mais perto
            wr = sorted(w.wrecks, key=lambda q: (q.center[0] - pod[0]) ** 2 + (q.center[1] - pod[1]) ** 2)[:2]
            for q in wr:
                for t in range(0, 7):
                    f = t / 6
                    centers.append((pod[0] + (q.center[0] - pod[0]) * f, pod[1] + (q.center[1] - pod[1]) * f, -1))
            for res in C.RESOURCES:                      # o veio mais perto de cada minério
                vs = sorted((v for v in w.veins if v.resource == res),
                            key=lambda v: (v.tx - pod[0]) ** 2 + (v.ty - pod[1]) ** 2)[:1]
                for v in vs:
                    for t in range(0, 7):
                        f = t / 6
                        centers.append((pod[0] + (v.tx - pod[0]) * f, pod[1] + (v.ty - pod[1]) * f, -1))
        else:
            centers = [(cr[0] + 1, cr[1] + 1, 18)] if cr else [(w.width // 2, w.height // 2, 18)]
            tm = sorted(w.terminals, key=lambda q: (q[0] - centers[0][0]) ** 2 + (q[1] - centers[0][1]) ** 2)[:2]
            for q in tm:
                for t in range(0, 31):
                    f = t / 30
                    centers.append((centers[0][0] + (q[0] - centers[0][0]) * f, centers[0][1] + (q[1] - centers[0][1]) * f, 4))
                centers.append((q[0], q[1], 6))
        seen = explored_mask(w, centers)
        tex = pygame.Surface((w.width, w.height))
        tex.fill(UNSEEN)
        for x, y in seen:
            tex.set_at((x, y), tile_color(w, x, y))
        pygame.image.save(tex, str(OUT / f"map_{key}_tex.png"))
        vis = lambda tiles: any(t in seen for t in tiles)  # noqa: E731
        d = {"size": [w.width, w.height], "explored": len(seen) / (w.width * w.height),
             "crater": [cr[0] + 1.5, cr[1] + 1.5] if cr else None,
             "veins": [[v.resource, v.tx + 1, v.ty + 1] for v in w.veins if vis(v.tiles)],
             "wrecks": [[q.kind, *q.center, i % 2 == 1] for i, q in enumerate(w.wrecks) if vis(q.tiles)],
             "wrecks_total": len(w.wrecks),
             "terminals": [[tx + 0.5, ty + 0.5] for tx, ty in w.terminals if (tx, ty) in seen or (tx, ty + 1) in seen],
             "terminals_total": len(w.terminals)}
        if key == "surface":
            d["base"] = [pod[0] + 1, pod[1] + 0.5]
            d["machines"] = [[m.kind, m.tx + 0.5, m.ty + 0.5] for m in s.machines if m.layer == "surface"] \
                if hasattr(s.machines[0], "layer") else [[m.kind, m.tx + 0.5, m.ty + 0.5] for m in s.machines]
            d["player"] = [pod[0] + 1.5, pod[1] + 9.0, "right"]
        else:
            d["player"] = [cr[0] - 4.5, cr[1] + 9.0, "left"] if cr else [w.width / 2, w.height / 2, "down"]
            d["machines"] = []
        data[key] = d
    s.enter_layer("surface")
    (OUT / "map_markers.json").write_text(json.dumps(data, indent=1))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    save.SAVE_PATH.unlink(missing_ok=True)
    app = App(scale=1)
    frames(app, 0.3)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="", scancode=0))
    frames(app, DT)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN, mod=0, unicode="", scancode=0))
    frames(app, 0.5)
    s = app.state
    p = s.player
    p.x, p.y = (96 + 0.5) * C.TILE, (99 + 1) * C.TILE - 2
    for kind, tile in [("o2", (93, 98)), ("melter", (99, 98)), ("o2", (92, 96)), ("chest", (97, 100)),
                       ("heater", (100, 96)), ("solar", (94, 101))]:
        put(s, kind, tile)
    frames(app, 1.5)
    world_shot(app, "world_dead.png")

    # Névoa: um pouco mais de Ti, mesma base
    s.indices.update(o2=9_000.0, heat=2_500.0, water=1_400.0)
    frames(app, 1.0)
    world_shot(app, "world_mist.png")

    # ícones de item (32×32, como na hotbar) e prévias do fabricador
    kinds = list(C.RESOURCES) + list(C.MACHINES)
    for item in kinds:
        try:
            pygame.image.save(app.renderer.item_icon(item), str(OUT / f"item_{item}.png"))
        except Exception as e:  # noqa: BLE001
            print("   sem ícone:", item, e)
        if item in C.MACHINES:
            try:
                pygame.image.save(app.renderer.machine_preview(item), str(OUT / f"prev_{item}.png"))
            except Exception as e:  # noqa: BLE001
                print("   sem prévia:", item, e)
    # minimapa: tudo em volta da base explorado
    from game.minimap import UNSEEN, tile_color
    w = s.world
    px, py = s.player.tile
    tex = pygame.Surface((64, 64))
    tex.fill(UNSEEN)
    for y in range(64):
        for x in range(64):
            tx, ty = px - 32 + x, py - 32 + y
            # "explorado": um borrão irregular em volta da base (determinístico)
            r = ((x - 32) ** 2 + (y - 30) ** 2) ** 0.5
            if r < 22 + 5 * ((tx * 7 + ty * 13) % 5) / 5 and 0 <= tx < w.width and 0 <= ty < w.height:
                tex.set_at((x, y), tile_color(w, tx, ty))
    pygame.image.save(tex, str(OUT / "minimap_tex.png"))
    map_layers(s)
    with open(OUT / "machines.txt", "w") as f:
        for k, m in C.MACHINES.items():
            f.write(f"{k}|{m.name}|{m.desc}|{m.unlock_ti}|{dict(m.cost)}\n")
    print("ok")


if __name__ == "__main__":
    main()
