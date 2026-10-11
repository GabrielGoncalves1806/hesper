"""Smoke test: roda o jogo sem janela, simula input e salva screenshots em reports/dev/.

    uv run python tools/dev/smoke.py

Usa os drivers "dummy" do SDL (sem vídeo e sem som de verdade). O input é simulado
postando eventos de teclado/mouse na fila do pygame, igual a um jogador de verdade.
"""

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game.app import App  # noqa: E402

# o smoke mexe nos volumes: grava num arquivo temporário, nunca no settings.json de verdade
import tempfile  # noqa: E402
settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_smoke_settings.json"

OUT = ROOT / "reports" / "dev"
DT = 1 / 60


class Bot:
    def __init__(self):
        self.app = App(scale=1)
        self.state = self.app.state
        self.frame_times: list[float] = []

    def frames(self, seconds: float) -> None:
        for _ in range(max(1, round(seconds / DT))):
            start = time.perf_counter()
            self.app.step(DT)
            self.frame_times.append(time.perf_counter() - start)

    def key(self, key: int, hold: float = DT) -> None:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
        self.frames(hold)
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0, unicode="", scancode=0))
        self.frames(DT)

    def mouse_to(self, pos: tuple[int, int]) -> None:
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
        self.frames(DT)

    def tile_on_screen(self, tile: tuple[int, int]) -> tuple[int, int]:
        cx, cy = self.app.cam
        return tile[0] * C.TILE + 16 - cx, tile[1] * C.TILE + 16 - cy

    def mouse_down(self, pos):
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))

    def mouse_up(self, pos):
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1))

    def click(self, pos) -> None:
        self.mouse_to(pos)
        self.mouse_down(pos)
        self.frames(DT)
        self.mouse_up(pos)
        self.frames(DT)

    def teleport(self, tile: tuple[int, int]) -> None:
        p = self.state.player
        p.x, p.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 1) * C.TILE - 2

    def shot(self, name: str) -> None:
        path = OUT / name
        self.app.screenshot(str(path))
        print(f"  screenshot: {path.relative_to(ROOT)}")


def find_ore_with_floor_below(state, kind=C.IRON):
    """Minério que tem chão logo embaixo (dá pra minerar de frente), o mais perto da base."""
    w = state.world
    best = None
    for ty in range(1, w.height - 1):
        for tx in range(1, w.width - 1):
            if w.get(tx, ty) == kind and w.get(tx, ty + 1) == C.FLOOR and w.get(tx, ty + 2) == C.FLOOR:
                d = w.dist_from_center(tx, ty)
                if best is None or d < best[0]:
                    best = (d, (tx, ty))
    return best[1]


def crop_around_player(bot, w=96, h=80) -> pygame.Surface:
    cx, cy = bot.app.cam
    x, y = int(bot.state.player.x - cx), int(bot.state.player.y - cy)
    return bot.app.canvas.subsurface((x - w // 2, y - h + max(16, h // 3), w, h)).copy()


def check_directions_and_order(bot) -> None:
    """Monta 2 imagens ampliadas: o player andando nas 4 direções e a ordem de desenho com uma máquina."""
    s = bot.state
    frames = []
    for key in (pygame.K_s, pygame.K_w, pygame.K_d, pygame.K_a):
        bot.teleport((64, 67))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))
        bot.frames(0.25)
        frames.append(crop_around_player(bot))      # tirado no meio da caminhada
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key, mod=0, unicode="", scancode=0))
        bot.frames(0.1)
        frames.append(crop_around_player(bot))      # parado, virado pra mesma direção
    sheet = pygame.Surface((96 * 4, 80 * 2))
    for i, f in enumerate(frames):
        sheet.blit(f, ((i // 2) * 96, (i % 2) * 80))
    pygame.image.save(pygame.transform.scale_by(sheet, 2), str(OUT / "player_direcoes.png"))
    print("  screenshot: reports/dev/player_direcoes.png  (colunas: baixo, cima, direita, esquerda · linha 1 andando, 2 parado)")

    # ordem de desenho: pés acima da base da máquina = atrás; abaixo = na frente
    m = s.machines[0]
    order = pygame.Surface((96 * 2, 80))
    for i, feet_y in enumerate(((m.ty + 1) * C.TILE - 14, (m.ty + 1) * C.TILE + 10)):
        s.player.x, s.player.y = (m.tx + 0.5) * C.TILE + 6, feet_y
        bot.frames(DT)
        order.blit(crop_around_player(bot), (i * 96, 0))
    pygame.image.save(pygame.transform.scale_by(order, 3), str(OUT / "ordem_desenho.png"))
    print("  screenshot: reports/dev/ordem_desenho.png  (esquerda: player atrás da máquina · direita: na frente)")
    bot.teleport((64, 66))
    bot.frames(0.1)


def carve(state, tiles, kind=C.FLOOR):
    for t in tiles:
        state.world.set(*t, kind)


def check_walls_and_hover(bot) -> None:
    """Paredes altas, túnel de 1 tile, player escondido atrás do topo e cursor em cima de máquina."""
    s = bot.state
    # tela interna sem canal alfa (causa do quadrado preto no macOS, playtest 1)
    assert bot.app.canvas.get_masks()[3] == 0, "canvas não pode ter canal alfa"

    # 1) túnel horizontal e vertical de 1 tile cavados num maciço, longe da base
    cx, cy = 64, 96
    carve(s, [(x, y) for x in range(cx - 8, cx + 9) for y in range(cy - 6, cy + 7)], C.ROCK)
    carve(s, [(x, cy) for x in range(cx - 7, cx + 1)])                 # túnel horizontal
    carve(s, [(cx, y) for y in range(cy - 5, cy + 6)])                 # túnel vertical
    carve(s, [(x, y) for x in range(cx + 3, cx + 8) for y in range(cy + 2, cy + 6)])   # salinha
    bot.teleport((cx - 4, cy))
    s.o2 = C.O2_MAX
    bot.key(pygame.K_a, hold=0.2)
    bot.frames(0.2)
    bot.shot("tunel.png")

    # 2) player logo acima de uma parede (pé na linha de cima): metade de baixo escondida
    s.player.x, s.player.y = (cx + 5 + 0.5) * C.TILE, (cy + 2) * C.TILE - 2
    carve(s, [(cx + 5, cy + 2)], C.ROCK)
    bot.frames(0.1)
    sheet = pygame.Surface((96 * 2, 80))
    sheet.blit(crop_around_player(bot), (0, 0))
    carve(s, [(cx + 5, cy + 2)])          # tira a parede: player inteiro, pra comparar
    bot.frames(DT)
    sheet.blit(crop_around_player(bot), (96, 0))
    pygame.image.save(pygame.transform.scale_by(sheet, 3), str(OUT / "atras_da_parede.png"))
    print("  screenshot: reports/dev/atras_da_parede.png  (esquerda: parede logo abaixo do player · direita: sem parede)")
    s.o2 = C.O2_MAX

    # 3) cursor em cima de máquina colocada (com e sem fantasma) — playtest 1 mostrou quadrado preto aqui
    bot.teleport((64, 66))
    bot.frames(0.1)
    s.inventory.update(iron=60, silicon=30, ice=40)
    s.craft("melter")
    s.place("melter", (62, 67))
    s.craft("melter")
    bot.app.placing = "melter"
    bot.mouse_to(bot.tile_on_screen((62, 67)))          # fantasma em cima da máquina colocada (inválido)
    bot.frames(0.2)
    shot_hover = pygame.Surface((240, 120))
    cxp, cyp = bot.tile_on_screen((62, 67))
    shot_hover.blit(bot.app.canvas, (0, 0), (cxp - 60, cyp - 80, 120, 120))
    bot.mouse_to(bot.tile_on_screen((60, 67)))          # fantasma num lugar válido, ao lado
    bot.frames(0.2)
    bot.app.placing = None
    shot_hover.blit(bot.app.canvas, (120, 0), (cxp - 100, cyp - 80, 120, 120))
    pygame.image.save(pygame.transform.scale_by(shot_hover, 3), str(OUT / "hover_maquina.png"))
    print("  screenshot: reports/dev/hover_maquina.png  (esquerda: fantasma sobre máquina · direita: fantasma ao lado)")
    s.machines_owned["melter"] = 0


def check_drill(bot) -> None:
    """Minera nas 4 direções (sem quebrar) e monta reports/dev/broca.png."""
    s = bot.state
    cx, cy = 40, 100
    carve(s, [(x, y) for x in range(cx - 3, cx + 4) for y in range(cy - 3, cy + 4)])          # salinha
    crops = []
    for target in [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]:                   # dir, esq, baixo, cima
        carve(s, [(x, y) for x in range(cx - 3, cx + 4) for y in range(cy - 3, cy + 4)])
        carve(s, [target], C.ROCK)                         # só a rocha que vai ser minerada
        bot.teleport((cx, cy))
        s.o2 = C.O2_MAX
        bot.frames(0.05)
        # mira no topo elevado da parede (é onde ela aparece na tela)
        camx, camy = bot.app.cam
        pos = (target[0] * C.TILE + 16 - camx, target[1] * C.TILE - 8 - camy)
        bot.mouse_to(pos)
        bot.mouse_down(pos)
        bot.frames(0.3)                                    # rocha quebra em 0,6 s: aqui ainda está inteira
        assert s.mining and s.mining.tile == target, (s.mining, target)
        crops.append(crop_around_player(bot, 96, 96))
        bot.mouse_up(pos)
        bot.frames(0.05)
    sheet = pygame.Surface((96 * 4, 96))
    for i, c in enumerate(crops):
        sheet.blit(c, (i * 96, 0))
    pygame.image.save(pygame.transform.scale_by(sheet, 3), str(OUT / "broca.png"))
    print("  screenshot: reports/dev/broca.png  (direita, esquerda, baixo, cima)")


def check_pause(bot) -> None:
    """Esc pausa (mundo congela), menu com mouse e teclado, sliders de volume, controles."""
    s, app = bot.state, bot.app
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    assert s.machines, "precisa de máquina pra ver o Ti congelar"
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "pause"
    ti_before, o2_before = s.ti, s.o2
    bot.frames(1.0)
    assert s.ti == ti_before and s.o2 == o2_before, "pausa tem que congelar Ti e O2"
    ui = app.ui
    bot.mouse_to((ui.pause_items[1].centerx * 2, ui.pause_items[1].centery * 2))   # mouse em "Volumes"
    assert app.pause_selected == 1
    bot.shot("pausa.png")
    bot.click((ui.pause_items[1].centerx * 2, ui.pause_items[1].centery * 2))
    assert app.pause_screen == "volumes"
    bot.frames(DT)
    # teclado: desce pro "Efeitos" e abaixa 3 vezes (100% -> 70%)
    bot.key(pygame.K_s)
    for _ in range(3):
        bot.key(pygame.K_a)
    assert app.settings["sfx"] == 0.7, app.settings
    # mouse: clica no meio da barra do "Geral" (≈50%) e arrasta até ~80%
    bar = ui.pause_sliders[0]
    bot.mouse_to((bar.x * 2 + bar.w, bar.centery * 2))
    bot.mouse_down((bar.x * 2 + bar.w, bar.centery * 2))
    bot.frames(DT)
    bot.mouse_to((int((bar.x + bar.w * 0.8) * 2), bar.centery * 2))
    bot.mouse_up((int((bar.x + bar.w * 0.8) * 2), bar.centery * 2))
    bot.frames(DT)
    assert abs(app.settings["master"] - 0.8) < 0.051, app.settings
    assert settings.load() == app.settings, "volumes têm que ir pro settings.json"
    assert app.audio.mix == app.settings
    bot.shot("pausa_volumes.png")
    bot.key(pygame.K_ESCAPE)
    assert app.pause_screen == "main"
    bot.key(pygame.K_s)
    bot.key(pygame.K_s)
    bot.key(pygame.K_RETURN)
    assert app.pause_screen == "controls"
    bot.frames(DT)
    bot.shot("pausa_controles.png")
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    app.settings = dict(settings.DEFAULTS)
    app.audio.set_mix(**app.settings)
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    # Esc com máquina na mão só cancela (não pausa)
    s.machines_owned["o2"] += 1
    bot.key(pygame.K_1)
    assert app.placing == "o2"
    bot.key(pygame.K_ESCAPE)
    assert app.placing is None and app.mode == "play"
    s.machines_owned["o2"] -= 1


def check_dismantle(bot) -> None:
    """Clique direito numa máquina: volta pro estoque, para de somar; dica com o mouse em cima."""
    s, app = bot.state, bot.app
    bot.teleport((64, 66))
    bot.frames(0.1)
    s.inventory.update(iron=60, silicon=30, ice=40)
    kind = "heater" if s.recipe_status("heater") == "ok" else "o2"   # aquecedor só libera com Ti 500
    s.craft(kind)
    s.place(kind, (66, 66))
    m = s.machine_at((66, 66))
    camx, camy = app.cam
    body = (int((m.tx + 0.5) * C.TILE - camx), int((m.ty + 1) * C.TILE - 40 - camy))   # no corpo, acima do tile
    bot.mouse_to(body)
    bot.frames(0.1)
    assert app.hint() == "[Clique direito] desmontar", app.hint()
    bot.shot("desmontar.png")
    owned = s.machines_owned[kind]
    rate = s.ti_rate
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=body, button=3))
    bot.frames(0.15)
    assert m not in s.machines and s.machines_owned[kind] == owned + 1
    assert s.ti_rate == rate - C.MACHINES[kind].rate
    bot.shot("desmontar_depois.png")
    # a cápsula não desmonta
    pod = (C.POD_ANCHOR[0] - camx, C.POD_ANCHOR[1] - 30 - camy)
    n = len(s.machines)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pod, button=3))
    bot.frames(0.1)
    assert len(s.machines) == n
    s.place(kind, (66, 66))      # devolve a máquina pro resto do smoke


def check_objectives_midway(bot) -> None:
    """Objetivos no meio do caminho: com ferro e silício 'minerados', o atual vira "Chegue a Ti 500"."""
    s = bot.state
    s.mined_total.update(iron=10, silicon=4)     # o bot pôs recurso direto no inventário, sem minerar
    bot.frames(1.6)                              # deixa passar o ✓ verde do objetivo concluído
    assert s.ti < 500 and s.fabricator_opened
    shown = bot.app.objectives.lines(s)
    assert shown[0].text == "Chegue a Ti 500", shown
    bot.shot("objetivos_meio.png")


def ti_in_window(stage: int, window_fraction: float) -> float:
    """Ti que fica `window_fraction` (0 a 1) dentro da janela de transição do estágio `stage` pro próximo."""
    start, end = C.STAGES[stage - 1].ti, C.STAGES[stage].ti
    bar = 1 - C.TRANSITION_WINDOW + C.TRANSITION_WINDOW * window_fraction
    return start + (end - start) * bar


def check_transition(bot, stage: int, shots: list[tuple[str, float]]) -> None:
    """Prints da mancha do próximo estágio se espalhando a partir da base e das máquinas."""
    s = bot.state
    before = dict(s.indices)
    bot.teleport((64, 66))
    s.o2 = C.O2_MAX
    for name, fraction in shots:
        s.indices.update(o2=ti_in_window(stage, fraction), heat=0.0, water=0.0)
        bot.frames(0.1)
        assert s.stage == stage, "a transição não pode trocar o estágio oficial antes do limiar"
        bot.shot(name)
    s.indices.update(before)
    bot.frames(DT)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bot = Bot()
    s = bot.state
    print("1) pouso")
    bot.frames(1.0)
    bot.shot("objetivos.png")           # objetivos na tela: começa em "Minere ferro (0/10)"
    bot.key(pygame.K_d, hold=0.6)       # anda um pouco pra direita
    bot.key(pygame.K_s, hold=0.3)
    bot.frames(0.5)
    bot.shot("stage1.png")

    print("2) mineração")
    ore = find_ore_with_floor_below(s)
    bot.teleport((ore[0], ore[1] + 1))
    bot.frames(0.2)
    pos = bot.tile_on_screen(ore)
    bot.mouse_to(pos)
    bot.mouse_down(pos)
    bot.frames(0.55)
    bot.shot("mining.png")
    bot.frames(0.6)
    bot.mouse_up(pos)
    bot.frames(0.3)
    assert s.world.get(*ore) == C.FLOOR, "o minério devia ter quebrado"
    assert s.inventory["iron"] >= 1, "devia ter ganhado ferro"
    print(f"  inventário depois de minerar: {s.inventory}")

    print("3) fabricador")
    s.inventory.update(iron=60, silicon=30, ice=24)
    bot.teleport((64, 65))
    bot.frames(0.3)
    bot.key(pygame.K_e)
    bot.frames(0.2)
    assert bot.app.mode == "fabricator"
    bot.mouse_to((560, 150))
    bot.shot("crafting.png")
    button = next(rect for rect, kind in bot.app.ui.fabricator_buttons if kind == "o2")
    bot.click((button.centerx * 2, button.centery * 2))
    assert bot.app.placing == "o2", "craftar devia entrar no modo de colocar"
    bot.mouse_to(bot.tile_on_screen((61, 66)))
    bot.frames(0.3)
    bot.shot("placing.png")
    bot.click(bot.tile_on_screen((61, 66)))
    assert len(s.machines) == 1
    # mais duas máquinas pelo teclado: S (desce) + Enter
    for target, steps in [((67, 66), 1), ((60, 64), 0)]:
        bot.key(pygame.K_e)
        for _ in range(steps):
            bot.key(pygame.K_s)
        bot.key(pygame.K_RETURN)
        bot.click(bot.tile_on_screen(target))
    print(f"  máquinas colocadas: {[m.kind for m in s.machines]}")
    bot.frames(2.0)
    bot.shot("base.png")
    check_objectives_midway(bot)
    check_directions_and_order(bot)
    check_walls_and_hover(bot)
    check_drill(bot)
    check_pause(bot)
    check_dismantle(bot)
    check_transition(bot, 1, [("transicao_25.png", 0.25), ("transicao_60.png", 0.60), ("transicao_90.png", 0.90)])

    print("4) terminal")
    tx, ty = s.world.terminals[0]
    bot.teleport((tx, ty + 1))
    bot.frames(0.2)
    bot.key(pygame.K_e)
    bot.frames(0.3)
    assert bot.app.mode == "terminal"
    bot.shot("terminal.png")
    bot.key(pygame.K_e)

    print("5) O2 crítico e desmaio")
    tx, ty = s.world.terminals[2]
    bot.teleport((tx, ty + 2))
    s.o2 = 14
    bot.frames(0.6)
    bot.shot("o2_critico.png")
    inventory_before = dict(s.inventory)
    s.o2 = 0.2
    bot.frames(1.4)
    bot.shot("desmaio.png")
    bot.frames(2.0)
    assert not s.fainted and s.o2 == C.O2_MAX and s.inventory == inventory_before
    bot.frames(0.5)

    print("6) estágios")
    bot.key(pygame.K_F2)
    bot.frames(1.0)
    assert s.stage == 2
    s.indices["o2"] += 12_914 - s.ti          # exemplo do dono: Ti 12.914 = ~3% do estágio 2
    bot.key(pygame.K_d, hold=0.5)
    bot.shot("stage2.png")
    s.inventory.update(iron=40, silicon=30, ice=20)
    bot.key(pygame.K_e)
    bot.frames(0.2)
    bot.shot("crafting_stage2.png")
    bot.key(pygame.K_ESCAPE)
    bot.frames(3.0)                           # deixa o banner do estágio 2 sumir
    check_transition(bot, 2, [("transicao_verde_60.png", 0.60)])
    for _ in range(9):
        bot.key(pygame.K_F2)
    bot.frames(1.0)
    assert s.stage == 3
    bot.shot("stage3.png")
    bot.frames(5.0)
    assert bot.app.mode == "end"
    bot.shot("fim.png")
    bot.key(pygame.K_RETURN)
    bot.key(pygame.K_a, hold=1.0)
    bot.frames(1.0)
    bot.shot("stage3_explorando.png")

    # folha ampliada (4×) com o player de fallback: parado e andando, nas 3 direções
    from game import art
    sheet = pygame.Surface((5 * 32, 3 * 32), pygame.SRCALPHA)
    sheet.fill((60, 40, 34))
    for row, view in enumerate(("down", "up", "side")):
        sheet.blit(art.player(view), (0, row * 32))
        sheet.blit(art.player_walk(view), (32, row * 32))
    pygame.image.save(pygame.transform.scale_by(sheet, 4), str(OUT / "player_fallback.png"))
    print("  screenshot: reports/dev/player_fallback.png")

    ft = sorted(bot.frame_times)
    avg = sum(ft) / len(ft)
    p95 = ft[int(len(ft) * 0.95)]
    print(f"OK · {len(ft)} frames · média {avg * 1000:.1f} ms · p95 {p95 * 1000:.1f} ms (orçamento: 16,7 ms)")
    pygame.quit()


if __name__ == "__main__":
    main()
