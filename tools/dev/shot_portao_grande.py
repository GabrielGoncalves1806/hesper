"""Print avulso do portão grande (v0.5 M3.6.3), fora do smoke:

    uv run python tools/dev/shot_portao_grande.py

Gera reports/dev/portao_grande.png: a entrada do bolsão da criatura (seed 598929664, estágio Árido) com o portão
fechado, derretendo e aberto (a fresta). Headless, não abre janela.
"""

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import ice_blocks  # noqa: E402
from game.assets import Sprites  # noqa: E402
from game.render import Renderer  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "portao_grande.png"
SEED = 598929664


def heat_at(p: float) -> float:
    lo, hi = C.THAW_GIANT_HEAT[0], C.THAW_GIANT_HEAT[-1]
    return lo + (hi - lo) * p


def main() -> None:
    pygame.init()
    pygame.display.set_mode((C.SCREEN_W, C.SCREEN_H))
    font = pygame.font.Font(None, 22)
    renderer = Renderer(Sprites())
    state = GameState(SEED, rng=random.Random(1))
    state.stage, state.storm = C.ARID_STAGE, 0.0
    state.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    state.o2 = C.O2_MAX
    geo = state.active.geo
    gi = ice_blocks.gate_count(geo) - 1
    bx, by = ice_blocks.gate_base_px(geo, gi)
    state.player.x, state.player.y = bx, by + 60
    cam = (int(bx - C.SCREEN_W / 2), int(by - C.SCREEN_H / 2 - 50))
    renderer.use_seed(SEED)
    renderer.stage_map = renderer.surface_map
    renderer.stage_map.update(state.indices["o2"], [])
    opens = ice_blocks.opens_at("G")
    shots = []
    for label, p in (("fechado", 0.0), ("derretendo", 0.35), ("aberto (fresta)", opens)):
        state.indices["heat"] = C.THAW_GATE_HEAT[-1][-1] if p == 0 else heat_at(p)
        state._apply_thaw()
        canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        for _ in range(3):
            renderer.draw(canvas, state, cam, 1.0)
        shot = pygame.transform.scale_by(canvas, 0.6)
        shot.blit(font.render(f"{label} · p={state.surface.gate_melt[gi]:.2f} · calor {state.indices['heat']:,.0f} pK",
                              True, (255, 255, 255), (0, 0, 0)), (4, 4))
        shots.append(shot)
    w, h = shots[0].get_size()
    sheet = pygame.Surface((w * 3 + 16, h))
    sheet.fill((20, 20, 24))
    for k, shot in enumerate(shots):
        sheet.blit(shot, (k * (w + 8), 0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(OUT))
    print(f"salvo: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
