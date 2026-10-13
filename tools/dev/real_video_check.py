"""Checador de vídeo real: as telas principais na janela de verdade comparadas com o driver dummy.

    uv run python tools/dev/real_video_check.py            # roda os dois lados e compara
    uv run python tools/dev/real_video_check.py --out DIR  # guarda os prints (real e dummy) em DIR

Por que existe: o smoke usa o driver "dummy" do SDL, onde `pygame.Surface(size)` nasce SEM canal alfa.
Na janela de verdade do macOS (Cocoa) o formato padrão é ARGB, e aí uma superfície no formato padrão
pode chegar na janela com alfa 0: o mapa aberto saiu preto e os marcadores viraram quadrados (e11a7af),
e nenhum teste pegou. Aqui o jogo roda nos DOIS drivers, cada um num subprocesso:

- real:  o driver de vídeo do sistema, numa janela escondida (`set_mode` ganha `pygame.HIDDEN` por
         monkeypatch: nada aparece na tela) e o áudio no dummy;
- dummy: o mesmo do smoke.

Os dois passam pelas mesmas telas (título, superfície, mapa aberto na superfície e na caverna,
tempestade com rajada e o mapa chiando, inventário, fabricador, baú, caverna escura e opções). Cada print é dividido numa grade de células e, em
cada célula, conta quanto é preto (depois de compor a janela sobre preto, que é o que o macOS mostra
onde o alfa é 0) e quanto tem alfa < 255. Falha se, em alguma célula, o real tiver bem mais preto ou
transparente que o dummy. Save e settings vão pra uma pasta temporária, nunca os de verdade.
"""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CELL = 40                 # lado da célula da grade (px da janela 960×540): 24×14 células
BLACK_MAX = 12            # canal <= isso conta como "preto"
BLACK_SLACK = 0.25        # o real pode ter até +25% de preto numa célula sem falhar (partículas, cursor)
CLEAR_SLACK = 0.01        # alfa < 255 em mais de 1% da célula já é bug (a janela é opaca)
SCENES = ("titulo", "superficie", "chao_regioes", "morros", "formacoes", "cratera", "mapa_superficie", "tempestade", "mapa_tempestade", "inventario", "fabricador",
          "bau", "opcoes", "caverna_escura", "mapa_caverna")


# ---------------------------------------------------------------------------- lado do jogo (subprocesso)
def run_worker(driver: str, out: Path) -> None:
    original = os.environ.get("SDL_VIDEODRIVER")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    if driver == "dummy":
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tools" / "dev"))
    import pygame
    import smoke                                    # o smoke põe SDL_VIDEODRIVER=dummy se não tiver nada
    if driver == "real":
        if original is None or original == "dummy":
            os.environ.pop("SDL_VIDEODRIVER", None)  # volta pro driver do sistema (Cocoa, Windows, X11...)
        else:
            os.environ["SDL_VIDEODRIVER"] = original
    from game import config as C
    from game import save, settings
    from game.app import App
    from game.surfaces import opaque

    # janela escondida: soma HIDDEN em todo set_mode (o App abre e reabre a janela)
    real_set_mode = pygame.display.set_mode

    def hidden_set_mode(size=(0, 0), flags=0, *args, **kwargs):
        return real_set_mode(size, flags | pygame.HIDDEN, *args, **kwargs)

    pygame.display.set_mode = hidden_set_mode

    tmp = Path(tempfile.mkdtemp(prefix=f"hesper_video_{driver}_"))
    settings.SETTINGS_PATH = tmp / "settings.json"
    save.SAVE_PATH = tmp / "saves" / "slot1.json"
    smoke.worlds.SAVES_DIR = tmp / "saves"
    random.seed(1)

    class Checker(smoke.Bot):
        """O Bot do smoke, sem os prints dele: aqui cada tela vira estatística + PNG."""

        def __init__(self):
            self.app = App(scale=1)
            self.frame_times = []
            self.stats = {}
            assert self.app.mode == "title"

        def capture(self, name: str) -> None:
            frame = self.app.frame
            visible = opaque(frame.get_size())
            visible.fill((0, 0, 0))
            visible.blit(frame, (0, 0))          # janela sobre preto: o que aparece onde o alfa é 0
            pygame.image.save(visible, str(out / f"{name}_{driver}.png"))
            self.stats[name] = cell_stats(frame, visible)

    bot = Checker()
    app = bot.app
    print(f"[{driver}] driver de vídeo: {pygame.display.get_driver()} · janela {app.window.get_size()} "
          f"· máscaras {app.window.get_masks()}")
    mouse = (900, 500)                            # cursor longe do meio, igual nos dois lados
    bot.mouse_to(mouse)
    bot.frames(0.5)
    bot.capture("titulo")
    bot.new_world(1, "Video", str(C.WORLD_SEED))   # Mundos -> Novo mundo (seed 7: as cenas contam com ela)
    assert app.mode == "play"
    s = bot.state = app.state
    s.equipment.slots["scanner"] = "scanner"     # minimapa no HUD (a textura dele vem do game/minimap.py)
    bot.mouse_to(mouse)
    bot.frames(1.0)
    bot.capture("superficie")

    # chão assado (v0.4 M2, game/ground.py): a divisa planalto/salar no Árido, sem poeira na frente
    stage0, storm0, ind0, pos0 = s.stage, s.storm, dict(s.indices), (s.player.x, s.player.y)
    s.stage, s.storm = C.ARID_STAGE, 0.0
    s.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    bot.teleport(smoke.region_spot(s.active.geo, s.world, 0, 1))
    s.o2 = C.O2_MAX
    bot.mouse_to(mouse)
    smoke.ground_settle(bot, 0.3)
    bot.capture("chao_regioes")
    # morros orgânicos (v0.4 M2, game/hills.py): tiras SRCALPHA assadas, no basalto (o que tem mais morro)
    bot.teleport(smoke.hill_spot(s.active.geo, s.world, 2))
    s.o2 = C.O2_MAX
    bot.mouse_to(mouse)
    smoke.ground_settle(bot, 0.3)
    bot.capture("morros")
    # formações (v0.4 M2 · C3): sprite indexado recolorido (SRCALPHA, com a sombra de alfa 80), no arco
    arch = next(f for f in s.active.geo.formations if f.kind == "arch")
    s.player.x, s.player.y = arch.base_px[0] + 2.5 * C.TILE, arch.base_px[1] + 3 * C.TILE
    s.o2 = C.O2_MAX
    bot.mouse_to(mouse)
    smoke.ground_settle(bot, 0.3)
    bot.capture("formacoes")
    # cratera de impacto tampada de gelo + ejeção no chão (v0.4 M2 · C4)
    ctx, cty = s.world.crater
    s.player.x, s.player.y = (ctx + 1.5) * C.TILE, (cty + 4) * C.TILE
    s.o2 = C.O2_MAX
    bot.mouse_to(mouse)
    smoke.ground_settle(bot, 0.3)
    bot.capture("cratera")
    s.stage, s.storm = stage0, storm0
    s.indices.update(ind0)
    s.player.x, s.player.y = pos0
    bot.frames(0.3)

    bot.key(pygame.K_m)
    assert app.mode == "map" and app.map_view.layer == "surface"
    bot.frames(0.1)
    bot.capture("mapa_superficie")
    bot.key(pygame.K_m)

    # tempestade com rajada (v0.4): camada de poeira SRCALPHA + faixas + minimapa e mapa chiando
    old_storm = s.storm
    s.storm = 1.0
    smoke.set_weather(s, 1.0, 35.0)
    bot.mouse_to(mouse)
    bot.frames(0.5)
    bot.capture("tempestade")
    bot.key(pygame.K_m)
    assert app.mode == "map"
    bot.frames(0.1)
    bot.capture("mapa_tempestade")
    bot.key(pygame.K_m)
    s.storm = old_storm
    smoke.set_weather(s, 0.0)

    smoke.give(s, iron=40, silicon=12, ice=20, chest=1)
    bot.key(pygame.K_TAB)
    assert app.mode == "inventory"
    bot.frames(0.1)
    bot.capture("inventario")
    bot.key(pygame.K_TAB)

    bot.teleport((96, 97))
    bot.frames(0.2)
    bot.key(pygame.K_e)
    assert app.mode == "fabricator"
    bot.frames(0.1)
    bot.capture("fabricador")
    bot.key(pygame.K_ESCAPE)

    spot = next(t for t in ((96, 100), (94, 100), (98, 100), (93, 98), (99, 98)) if s.can_place("chest", t))
    assert s.place("chest", spot)
    chest = s.chests[0]
    chest.storage.add("iron", 20)
    chest.storage.add("ice", 7)
    s.player.x, s.player.y = chest.anchor[0], chest.anchor[1] + 10
    bot.frames(0.1)
    bot.key(pygame.K_e)
    assert app.mode == "chest"
    bot.frames(0.1)
    bot.capture("bau")
    bot.key(pygame.K_ESCAPE)

    bot.key(pygame.K_ESCAPE)
    assert app.mode == "pause"
    bot.key(pygame.K_s)
    bot.key(pygame.K_RETURN)
    assert app.pause_screen == "volumes"
    bot.frames(0.1)
    bot.capture("opcoes")
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"

    s.enter_layer("cave")
    spot = smoke.cave_spot(s.world)
    bot.teleport(spot)
    s.active.explored.reveal_circle(spot[0] + 0.5, spot[1] + 0.5, 14)   # só a lanterna revela pouco: o mapa
    #                                                                      da caverna precisa de textura pra testar
    s.o2 = C.O2_MAX
    bot.mouse_to(mouse)
    bot.frames(0.5)
    bot.capture("caverna_escura")
    bot.key(pygame.K_m)
    assert app.mode == "map" and app.map_view.layer == "cave"
    bot.frames(0.1)
    bot.capture("mapa_caverna")
    bot.key(pygame.K_m)

    (out / f"stats_{driver}.json").write_text(json.dumps(bot.stats))
    pygame.quit()


def cell_stats(frame, visible) -> list[list[float]]:
    """Por célula da grade (linha a linha): [fração preta, fração com alfa < 255]."""
    import pygame
    w, h = frame.get_size()
    black = pygame.mask.from_threshold(visible, (0, 0, 0, 255), (BLACK_MAX + 1, BLACK_MAX + 1, BLACK_MAX + 1, 255))
    alpha_mask = frame.get_masks()[3]
    clear = None
    if alpha_mask:                                  # janela com canal alfa: conta quem não está opaco
        # o alfa guardado de verdade (get_at mente: numa superfície sem SRCALPHA ele sempre diz 255)
        alpha = pygame.image.tobytes(frame, "ARGB")[0::4]
        clear = pygame.mask.Mask((w, h))
        for y in range(h):
            row = alpha[y * w:(y + 1) * w]
            if row.count(255) != w:
                for x, a in enumerate(row):
                    if a != 255:
                        clear.set_at((x, y))
    out = []
    for y0 in range(0, h, CELL):
        for x0 in range(0, w, CELL):
            rect = pygame.Rect(x0, y0, min(CELL, w - x0), min(CELL, h - y0))
            n = rect.w * rect.h
            cut = pygame.mask.Mask(rect.size, fill=True)
            b = black.overlap_area(cut, rect.topleft) / n
            c = clear.overlap_area(cut, rect.topleft) / n if clear is not None else 0.0
            out.append([round(b, 4), round(c, 4)])
    return out


# ---------------------------------------------------------------------------- comparação
def compare(real: dict, dummy: dict, cols: int) -> list[str]:
    problems = []
    for scene in SCENES:
        if scene not in real or scene not in dummy:
            problems.append(f"{scene}: não chegou a ser capturada")
            continue
        bad_black, bad_clear = [], []
        for i, ((rb, rc), (db, dc)) in enumerate(zip(real[scene], dummy[scene])):
            cell = (i % cols, i // cols)
            if rc > dc + CLEAR_SLACK:
                bad_clear.append((cell, rc))
            if rb > db + BLACK_SLACK:
                bad_black.append((cell, rb - db))
        if bad_clear:
            worst = max(bad_clear, key=lambda c: c[1])
            problems.append(f"{scene}: {len(bad_clear)} células com alfa < 255 na janela real "
                            f"(pior: célula {worst[0]}, {worst[1]:.0%} transparente)")
        if bad_black:
            worst = max(bad_black, key=lambda c: c[1])
            problems.append(f"{scene}: {len(bad_black)} células pretas no real que não são pretas no dummy "
                            f"(pior: célula {worst[0]}, +{worst[1]:.0%} de preto)")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--worker", choices=("real", "dummy"), help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help="pasta pros prints e estatísticas (padrão: temporária)")
    args = parser.parse_args()
    out = args.out or Path(tempfile.mkdtemp(prefix="hesper_video_check_"))
    out.mkdir(parents=True, exist_ok=True)
    if args.worker:
        run_worker(args.worker, out)
        return 0

    for driver in ("dummy", "real"):
        env = {k: v for k, v in os.environ.items() if k != "SDL_VIDEODRIVER"}
        done = subprocess.run([sys.executable, __file__, "--worker", driver, "--out", str(out)], env=env)
        if done.returncode != 0:
            print(f"FALHOU: o lado {driver} quebrou (código {done.returncode})")
            return 1
    real = json.loads((out / "stats_real.json").read_text())
    dummy = json.loads((out / "stats_dummy.json").read_text())
    from math import ceil
    problems = compare(real, dummy, ceil(960 / CELL))
    print(f"prints em {out} (<tela>_real.png e <tela>_dummy.png)")
    if problems:
        print("FALHOU: a janela real não bate com o dummy")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK · {len(SCENES)} telas iguais nos dois drivers (sem preto nem transparência a mais no real)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
