"""v0.7 Lore M4: prints do interior da VÉSPER-7 (não entra no smoke).

Gera em reports/dev/v07_m4/:
  1. sala_<slot>_<a|b>.png      cada sala (porão, corredor, alojamento, câmara fria, cabine) nas 2 variantes
  2. conteiner_dica.png         câmara fria: mouse no contêiner arrombado, contorno e dica
  3. painel_dica.png            cabine: mouse no painel de energia, contorno e dica
  4. porta_faisca.png           cabine: a porta emperrada com faísca e névoa
  5. fade_entrando.png          o fade "Entrando..." (no meio da viagem)
  6. fora_boca.png              a boca do porão da VÉSPER na superfície, com a dica "[E] Entrar na VÉSPER-7"
Seeds escolhidas pra cobrir as variantes `_a` e `_b` de cada slot. Headless (driver dummy): não abre janela.
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
from game import layers, settings, vesper, viewport, wrecks  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "v07_m4"
DT = 1 / 30
T = C.TILE
SLOTS = ("hold", "hall", "bunks", "cold", "bridge")
PROP_SHOTS = ("prop_container_stack", "prop_repair_bench", "prop_wall_bunk", "prop_briefing_table", "prop_command_table",
              "prop_mess_table", "prop_server_rack_open", "prop_suit_niche")


def variant_of(seed: int, slot: str) -> str:
    return next(plan.key[-1] for s, plan in vesper._pick(seed) if s.key == slot)


def seed_for(slot: str, want: str) -> int:
    return next(s for s in range(1, 400) if variant_of(s, slot) == want)


def new_app(seed: int):
    from game.app import App
    app = App(scale=1, skip_title=True)
    app.start_game(GameState(seed=seed))
    app.set_zoom(1.5, notify=False)
    app.state.storm = 0.0
    return app


def frames(app, n: int) -> None:
    for _ in range(n):
        app.step(DT)


def put_feet(app, px: float, py: float) -> None:
    p = app.state.player
    p.x, p.y = px, py


def save_shot(app, name: str) -> None:
    path = OUT / name
    app.screenshot(str(path))
    print("  screenshot:", path.relative_to(ROOT))


def inside(app) -> None:
    app.state.enter_layer(layers.VESPER)
    app.state.o2 = C.O2_MAX


def room_spot(world, slot) -> tuple[int, int]:
    """Um tile de chão perto do meio da caixa da sala (andável: sem prop, sem fixture sólido)."""
    ox, oy = vesper.ORIGIN
    sx, sy, w, h = slot.box
    cx, cy = ox + sx + w // 2, oy + sy + h // 2
    near = sorted(((x, y) for x in range(cx - w, cx + w) for y in range(cy - h, cy + h)),
                  key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)
    return next(t for t in near if world.is_floor(*t) and not world.is_solid(*t))


def fixture(app, kind) -> tuple[int, int]:
    return next(t for t, k in app.state.world.fixtures.items() if k == kind)


def hover(app, tile) -> None:
    """Mouse no centro do tile (na altura da face, se for de parede)."""
    app.mouse = tuple(round(v) for v in viewport.world_to_canvas(((tile[0] + 0.5) * T, (tile[1] + 0.5) * T), app.cam, app.zoom))
    frames(app, 10)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_v07_m4_settings.json"
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    slots = {s.key: s for s in vesper.SLOTS}
    # 1. cada sala nas duas variantes (uma seed por variante e por sala)
    for slot_key in SLOTS:
        for var in ("a", "b"):
            seed = seed_for(slot_key, var)
            app = new_app(seed)
            inside(app)
            x, y = room_spot(app.state.world, slots[slot_key])
            put_feet(app, (x + 0.5) * T, (y + 1) * T - 2)
            app.mouse = (4, 4)
            frames(app, 25)
            save_shot(app, f"sala_{slot_key}_{var}.png")
            pygame.event.clear()
    # 2-4. contêiner, painel e porta: numa seed só
    seed = 3
    app = new_app(seed)
    inside(app)
    cx, cy = fixture(app, "container_broken")
    put_feet(app, (cx + 0.5) * T, (cy + 2) * T - 2)
    frames(app, 20)
    hover(app, (cx, cy))
    print("  dica do contêiner:", app.hint())
    save_shot(app, "conteiner_dica.png")
    px, py = fixture(app, "power_panel")
    put_feet(app, (px + 0.5) * T, (py + 2) * T - 2)
    frames(app, 20)
    hover(app, (px, py))
    print("  dica do painel:", app.hint())
    save_shot(app, "painel_dica.png")
    dx, dy = fixture(app, "jammed_door")
    put_feet(app, (dx + 0.5) * T, (dy + 3) * T - 2)
    app.mouse = (4, 4)
    frames(app, 90)                                         # a névoa já está no ar
    for _ in range(600):                                    # espera um estalo (a faísca vive 0,25 s) e tira o print 2 quadros depois
        frames(app, 1)
        if len(app.renderer.door_fx.sparks) >= 3:
            frames(app, 2)
            break
    print(f"  faíscas: {len(app.renderer.door_fx.sparks)}  névoa: {len(app.renderer.door_fx.fog)}")
    save_shot(app, "porta_faisca.png")
    # 4b. props novos do kit (Task 5): o jogador na frente (sul) de cada um e, nos grandes, atrás (norte) pra ver a ordem do pé
    for kind in PROP_SHOTS:
        seed = next(s for s in range(0, 200) if kind in vesper.compose(s).props.values())
        app = new_app(seed)
        inside(app)
        ax, ay = next(p.tile for p in app.state.active.props.values() if p.kind == kind)
        w, h = C.PROPS[kind].size
        for side, (fx, fy) in (("sul", (ax, ay + h + 1)), ("norte", (ax, ay - 1))):
            if side == "norte" and (w, h) == (1, 1):
                continue
            if app.state.world.is_solid(fx, fy) or app.state.active.props.get((fx, fy)):
                continue
            put_feet(app, (fx + 0.5) * T, (fy + 1) * T - 2)
            app.mouse = (4, 4)
            frames(app, 25)
            save_shot(app, f"prop_{kind}_{side}.png")
    # 5-6. fora: a boca do porão e o fade
    app = new_app(seed)
    w = wrecks.vesper_wreck(app.state.world)
    put_feet(app, (w.tx + 3.5) * T, (w.ty + 3) * T + 24)
    frames(app, 20)
    hover(app, (w.tx + 3, w.ty + 2))
    print("  dica da boca:", app.hint())
    save_shot(app, "fora_boca.png")
    app.mouse = (4, 4)
    assert app.state.start_hatch()
    frames(app, int(C.RAMP_DURATION * 0.5 / DT))
    save_shot(app, "fade_entrando.png")
    pygame.quit()


if __name__ == "__main__":
    main()
