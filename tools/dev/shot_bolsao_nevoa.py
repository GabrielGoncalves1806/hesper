"""Print avulso da névoa do bolsão da criatura (v0.5 M3.6.4), fora do smoke:

    uv run python tools/dev/shot_bolsao_nevoa.py

Gera reports/dev/bolsao_nevoa.png (seed 598929664, Árido, headless): de fora com a névoa (portão fechado), o mapa com o
"?", o momento da mensagem com a névoa sumindo e o bolsão aberto. Roda o App de verdade (HUD, aviso e mapa incluídos).
"""

import os
import random
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import ice_blocks, settings  # noqa: E402
from game.systems import GameState  # noqa: E402

OUT = ROOT / "reports" / "dev" / "bolsao_nevoa.png"
SEED = 598929664
DT = 1 / 60


class MuteAudio:
    """Sem som no print (o resto das chamadas do App vira nada)."""

    def has(self, name):
        return False

    def __getattr__(self, name):
        return lambda *a, **k: None


def main() -> None:
    pygame.init()
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_shot_nevoa_settings.json"
    from game.app import App
    app = App(scale=1, skip_title=True)
    font = pygame.font.Font(None, 22)
    state = GameState(SEED, rng=random.Random(1))
    state.stage, state.storm = C.ARID_STAGE, 0.0
    state.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    state.o2 = C.O2_MAX
    state.equipment.slots["scanner"] = "scanner"
    app.start_game(state)
    app.audio = MuteAudio()
    gp = state.active.geo.giant
    ox, oy, ow, oh = gp.outer                 # fora do anel, a leste do meio: com zoom 0,75 cabe o bolsão quase todo
    state.player.x, state.player.y = (ox + ow + 4) * C.TILE, (oy + oh / 2) * C.TILE
    app.set_zoom(0.75, notify=False)
    width = state.surface.world.width
    for tx, ty in (*gp.interior, *gp.giant.tiles, *gp.entry):
        state.surface.explored.bits[ty * width + tx] = 1

    def run(seconds: float) -> None:
        for _ in range(round(seconds / DT)):
            app.step(DT)

    def grab(label: str) -> pygame.Surface:
        img = pygame.transform.smoothscale(app.frame, (640, 360))
        img.blit(font.render(label, True, (255, 255, 255), (0, 0, 0)), (4, 4))
        return img

    shots = []
    run(1.0)
    shots.append(grab("fechado, de fora"))
    app.open_map()
    run(0.5)
    shots.append(grab("mapa fechado: névoa e ?"))
    app.mode = "play"
    lo, hi = C.THAW_GIANT_HEAT[0], C.THAW_GIANT_HEAT[-1]
    state.indices["heat"] = lo + (hi - lo) * (ice_blocks.opens_at("G") + 0.02)
    run(1.6)
    shots.append(grab("1,6 s depois de abrir: mensagem e névoa sumindo"))
    run(4.0)
    shots.append(grab("aberto"))
    w, h = shots[0].get_size()
    sheet = pygame.Surface((w * 2 + 8, h * 2 + 8))
    sheet.fill((20, 20, 24))
    for k, shot in enumerate(shots):
        sheet.blit(shot, ((k % 2) * (w + 8), (k // 2) * (h + 8)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(OUT))
    print(f"salvo: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
