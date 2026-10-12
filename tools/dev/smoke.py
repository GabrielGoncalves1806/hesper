"""Smoke test: roda o jogo sem janela, simula input e salva screenshots em reports/dev/.

    uv run python tools/dev/smoke.py

Usa os drivers "dummy" do SDL (sem vídeo e sem som de verdade). O input é simulado
postando eventos de teclado/mouse na fila do pygame, igual a um jogador de verdade.
"""

import math
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
from game import save  # noqa: E402
from game import settings  # noqa: E402
from game.app import NUMBER_KEYS, App  # noqa: E402

# o smoke mexe nos volumes: grava num arquivo temporário, nunca no settings.json de verdade
import tempfile  # noqa: E402
settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_smoke_settings.json"
# ...e o save também: o smoke nunca deixa um saves/slot1.json de verdade pra trás
save.SAVE_PATH = Path(tempfile.gettempdir()) / "hesper_smoke_save" / "slot1.json"

OUT = ROOT / "reports" / "dev"
DT = 1 / 60


class Bot:
    def __init__(self):
        save.SAVE_PATH.unlink(missing_ok=True)
        self.app = App(scale=1)
        self.frame_times: list[float] = []
        # o jogo abre na tela de título: sem save, só "Novo jogo" e "Sair"
        assert self.app.mode == "title"
        assert [label for _, label in self.app.title.options()] == ["Novo jogo", "Sair"]
        self.frames(0.5)
        self.shot("titulo.png")
        self.key(pygame.K_RETURN)               # "Novo jogo" já vem selecionado
        assert self.app.mode == "play"
        self.state = self.app.state

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
        """Centro do tile na janela (escala 1, sem tarja): considera o zoom."""
        cx, cy = self.app.cam
        z = self.app.zoom
        return round((tile[0] * C.TILE + 16 - cx) * z), round((tile[1] * C.TILE + 16 - cy) * z)

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


def give(state, **amounts) -> None:
    """Deixa o inventário com EXATAMENTE essas quantidades (igual ao antigo inventory.update)."""
    for item, n in amounts.items():
        state.inventory.remove(item, state.inventory.count(item))
        assert state.inventory.add(item, n) == 0, f"não coube {n} {item} no inventário"


def hotbar_key(bot, kind) -> int:
    """Tecla (1–8) do slot da hotbar que tem essa máquina."""
    slots = bot.state.inventory.slots[:C.HOTBAR_SLOTS]
    return NUMBER_KEYS[next(i for i, st in enumerate(slots) if st and st.item == kind)]


def slot_pos(bot, inv, index) -> tuple[int, int]:
    """Centro (na janela) do slot `index` de `inv` na tela de inventário/baú aberta."""
    rect = next(r for r, i, k in bot.app.ui.slot_rects if i is inv and k == index)
    return rect.centerx * 2, rect.centery * 2


def right_click(bot, pos) -> None:
    bot.mouse_to(pos)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=3))
    bot.frames(DT)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=3))
    bot.frames(DT)


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
    give(s, iron=60, silicon=30, ice=40)
    s.craft("melter")
    s.place("melter", (62, 67))
    s.craft("melter")
    bot.key(hotbar_key(bot, "melter"))
    assert bot.app.placing == "melter"
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
    s.inventory.remove("melter", 99)


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
    bot.mouse_to((ui.pause_items[1].centerx * 2, ui.pause_items[1].centery * 2))   # mouse em "Opções"
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
    assert app.audio.mix == settings.mix(app.settings)
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
    app.audio.set_mix(**settings.mix(app.settings))
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    # Esc com máquina na mão só cancela (não pausa)
    s.inventory.add("o2", 1)
    bot.key(hotbar_key(bot, "o2"))
    assert app.placing == "o2"
    bot.key(pygame.K_ESCAPE)
    assert app.placing is None and app.mode == "play"
    s.inventory.remove("o2", 1)


def check_zoom_and_fullscreen(bot) -> None:
    """Zoom (+/-, Ctrl+rodinha) só no mundo; mouse acerta tile/máquina em qualquer zoom; tela cheia com
    tarja preta (o driver dummy finge um monitor 4:3 de 1024×768). Prints: zoom_out, zoom_in, tela_cheia."""
    from game import viewport
    s, app = bot.state, bot.app
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    assert app.zoom == 1.0
    bot.teleport((64, 66))
    s.o2 = C.O2_MAX
    bot.frames(0.2)
    machine = s.machines[0]

    def hover_machine_check():
        ax, ay = machine.anchor
        pos = viewport.world_to_canvas((ax, ay - 8), app.cam, app.zoom)
        bot.mouse_to((round(pos[0]), round(pos[1])))
        assert app.hovered_machine() is machine, (app.zoom, pos)

    def tile_check(tile):
        bot.mouse_to(bot.tile_on_screen(tile))
        assert app.mouse_tile() == tile, (app.zoom, app.mouse_tile(), tile)

    # zoom out (0,75×): visão de 1280×720 do mundo
    bot.key(pygame.K_MINUS)
    assert app.zoom == 0.75 and settings.load()["zoom"] == 0.75, "zoom tem que ir pro settings.json"
    assert app.cam == app.renderer.camera(s, (1280, 720))
    hover_machine_check()
    tile_check((60, 62))
    app.floaters.add("+15 FERRO", s.player.x, s.player.y - 40, C.ORE_COLORS["iron"][0])
    start = len(bot.frame_times)
    bot.frames(1.0)
    zoom_out_ms = 1000 * sum(bot.frame_times[start:]) / (len(bot.frame_times) - start)
    app.floaters.add("+15 FERRO", s.player.x, s.player.y - 40, C.ORE_COLORS["iron"][0])
    app.show_toast("Zoom 0,75×")
    bot.frames(0.2)
    bot.shot("zoom_out.png")
    print(f"  zoom 0,75×: {zoom_out_ms:.1f} ms por frame (visão 1280×720)")
    # Ctrl+rodinha: mexe no zoom e NÃO troca a hotbar
    slot = app.hotbar_selected
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_LCTRL, unicode="", scancode=0))
    pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=False, precise_x=0.0, precise_y=1.0))
    bot.frames(DT)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_LCTRL, mod=0, unicode="", scancode=0))
    bot.frames(DT)
    assert app.zoom == 1.0 and app.hotbar_selected == slot, (app.zoom, app.hotbar_selected)
    # sem Ctrl a rodinha continua na hotbar
    pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False, precise_x=0.0, precise_y=-1.0))
    bot.frames(DT)
    assert app.zoom == 1.0 and app.hotbar_selected == (slot + 1) % C.HOTBAR_SLOTS
    bot.key(NUMBER_KEYS[slot])
    # zoom in até o máximo (= e + do teclado numérico), e para no 2×
    bot.key(pygame.K_EQUALS)
    assert app.zoom == 1.5
    tile_check((62, 64))
    bot.key(pygame.K_KP_PLUS)
    bot.key(pygame.K_KP_PLUS)
    assert app.zoom == 2.0
    hover_machine_check()
    tile_check((63, 64))
    # fantasma de colocação no tile certo com zoom
    s.inventory.add("o2", 1)
    bot.key(hotbar_key(bot, "o2"))
    assert app.placing == "o2"
    target = (65, 64)
    bot.mouse_to(bot.tile_on_screen(target))
    assert app.place_target() == target
    app.floaters.add("+15 FERRO", s.player.x, s.player.y - 40, C.ORE_COLORS["iron"][0])
    bot.frames(0.3)
    bot.shot("zoom_in.png")
    bot.key(pygame.K_ESCAPE)
    assert app.placing is None
    s.inventory.remove("o2", 1)
    # o HUD não muda de tamanho: a hotbar fica no mesmo lugar em qualquer zoom (compara a faixa de baixo)
    hud_zoom = app.canvas.subsurface((0, C.SCREEN_H - 60, C.SCREEN_W, 60)).copy()
    bot.key(pygame.K_KP_MINUS)
    bot.key(pygame.K_MINUS)
    assert app.zoom == 1.0
    hud_normal = app.canvas.subsurface((0, C.SCREEN_H - 60, C.SCREEN_W, 60)).copy()
    hotbar = pygame.Rect(C.SCREEN_W // 2 - 180, 10, 360, 50)
    same = sum(hud_zoom.get_at((x, y)) == hud_normal.get_at((x, y))
               for x in range(hotbar.x, hotbar.right, 3) for y in range(hotbar.y, hotbar.bottom, 3))
    total = len(range(hotbar.x, hotbar.right, 3)) * len(range(hotbar.y, hotbar.bottom, 3))
    assert same / total > 0.6, f"hotbar mudou com o zoom? só {same}/{total} pixels iguais"

    # tela cheia: F11 abre no tamanho do "monitor" (1024×768, 4:3 -> tarja em cima e embaixo)
    bot.key(pygame.K_F11)
    assert app.settings["fullscreen"] and settings.load()["fullscreen"], "tela cheia tem que ir pro settings.json"
    ww, wh = app.window.get_size()
    x, y, w, h = viewport.letterbox((ww, wh))
    print(f"  tela cheia: janela {ww}×{wh}, jogo em {w}×{h} a partir de ({x}, {y})")
    assert (ww, wh) != (C.SCREEN_W, C.SCREEN_H) and y > 0
    # mouse em cima da máquina, em coordenada de janela (com tarja e escala não inteira)
    ax, ay = machine.anchor
    cx_, cy_ = viewport.world_to_canvas((ax, ay - 8), app.cam, app.zoom)
    bot.mouse_to((round(x + cx_ * w / C.SCREEN_W), round(y + cy_ * h / C.SCREEN_H)))
    assert abs(app.mouse[0] - cx_) <= 2 and abs(app.mouse[1] - cy_) <= 2, (app.mouse, (cx_, cy_))
    assert app.hovered_machine() is machine
    bot.frames(0.2)
    pygame.image.save(app.window, str(OUT / "tela_cheia.png"))
    print("  screenshot: reports/dev/tela_cheia.png  (janela inteira, com a tarja preta)")
    # Alt+Enter volta pra janela
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=pygame.KMOD_LALT, unicode="", scancode=0))
    bot.frames(DT)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN, mod=0, unicode="", scancode=0))
    bot.frames(DT)
    assert not app.settings["fullscreen"] and app.window.get_size() == (C.SCREEN_W, C.SCREEN_H)
    assert app.mode == "play"
    # pausa > Opções: tela cheia e zoom também estão lá (A/D mexem)
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_s)
    bot.key(pygame.K_RETURN)
    assert app.pause_screen == "volumes"
    for _ in range(len(app.ui.VOLUME_ROWS) + 1):
        bot.key(pygame.K_s)
    bot.key(pygame.K_d)
    assert app.zoom == 1.5
    bot.shot("pausa_opcoes.png")
    bot.key(pygame.K_a)
    assert app.zoom == 1.0
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    app.toast_time = 0.0
    settings.SETTINGS_PATH.unlink(missing_ok=True)


def check_dismantle(bot) -> None:
    """Clique direito numa máquina: volta pro estoque, para de somar; dica com o mouse em cima."""
    s, app = bot.state, bot.app
    bot.teleport((64, 66))
    bot.frames(0.1)
    give(s, iron=60, silicon=30, ice=40)
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
    owned = s.inventory.count(kind)
    rate = s.ti_rate
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=body, button=3))
    bot.frames(0.15)
    assert m not in s.machines and s.inventory.count(kind) == owned + 1
    assert s.ti_rate == rate - C.MACHINES[kind].rate
    bot.shot("desmontar_depois.png")
    # a cápsula não desmonta
    pod = (C.POD_ANCHOR[0] - camx, C.POD_ANCHOR[1] - 30 - camy)
    n = len(s.machines)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pod, button=3))
    bot.frames(0.1)
    assert len(s.machines) == n
    s.place(kind, (66, 66))      # devolve a máquina pro resto do smoke


def check_inventory_and_chest(bot) -> None:
    """Hotbar, Tab, baú (pegar/soltar/metade/Shift+clique), baú com coisa não desmonta, inventário cheio."""
    s, app = bot.state, bot.app
    bot.teleport((64, 66))
    s.o2 = C.O2_MAX
    s.inventory.clear()
    give(s, iron=80, silicon=30, ice=24)                # ferro em 2 pilhas (50 + 30)
    s.inventory.add("o2", 2)
    assert s.craft("chest")
    # hotbar: tecla do baú seleciona o slot e já entra no modo de colocar
    bot.key(hotbar_key(bot, "chest"))
    assert app.placing == "chest"
    site = (63, 67)                                     # dentro da zona de O₂ da base
    assert s.world.get(*site) == C.FLOOR and s.machine_at(site) is None
    bot.mouse_to(bot.tile_on_screen(site))
    bot.frames(0.2)
    bot.shot("hotbar.png")
    bot.click(bot.tile_on_screen(site))
    chest = s.machine_at(site)
    assert chest is not None and chest.is_chest and s.inventory.count("chest") == 0
    assert app.placing is None                          # a pilha do slot acabou
    assert chest in s.base_chests()

    # abre com E (parado logo abaixo do baú)
    s.player.x, s.player.y = (site[0] + 0.5) * C.TILE, (site[1] + 1) * C.TILE + 10
    bot.frames(0.1)
    assert s.interaction() == ("chest", chest) and app.hint() == "[E] Abrir baú", app.hint()
    chest.storage.add("ice", 37)
    chest.storage.add("melter", 1)
    bot.key(pygame.K_e)
    assert app.mode == "chest"
    bot.frames(DT)
    inv, box = s.inventory, chest.storage
    # clique esquerdo (estilo Planet Crafter): a pilha de 50 ferro vai inteira pro baú
    iron_slot = inv.slots.index(next(st for st in inv.slots if st and st.item == "iron" and st.count == 50))
    bot.click(slot_pos(bot, inv, iron_slot))
    assert app.held is None and inv.slots[iron_slot] is None and box.count("iron") == 50
    # clique direito no gelo do baú: 1 unidade vem pro inventário
    right_click(bot, slot_pos(bot, box, 0))
    assert box.slots[0].count == 36 and inv.count("ice") == 25
    # Shift+clique no silício do inventário: vai tudo pro baú
    silicon_slot = inv.slots.index(next(st for st in inv.slots if st and st.item == "silicon"))
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, mod=pygame.KMOD_LSHIFT, unicode="", scancode=0))
    bot.frames(DT)
    bot.click(slot_pos(bot, inv, silicon_slot))
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_LSHIFT, mod=0, unicode="", scancode=0))
    bot.frames(DT)
    assert inv.count("silicon") == 0 and box.count("silicon") == 30
    # print com o tooltip em cima do gelo do baú
    bot.mouse_to(slot_pos(bot, box, 0))
    bot.frames(0.1)
    bot.shot("bau.png")
    # Pegar tudo e Guardar recursos (só ferro/silício/gelo: os geradores ficam no inventário)
    button = {a: r for r, a in app.ui.panel_buttons}
    bot.click((button["take_all"].centerx * 2, button["take_all"].centery * 2))
    assert box.is_empty() and inv.count("iron") == 74 and inv.count("melter") == 1
    button = {a: r for r, a in app.ui.panel_buttons}
    bot.click((button["store_all"].centerx * 2, button["store_all"].centery * 2))
    assert inv.counts() == {"o2": 2, "melter": 1}
    assert box.counts() == {"iron": 74, "silicon": 30, "ice": 61}

    # nome do baú: clique no nome, apaga, digita (E, 1 e WASD viram texto, não ação), Enter confirma
    rect = app.ui.name_rect
    bot.click((rect.centerx * 2, rect.centery * 2))
    assert app.name_edit is not None
    for _ in range(3):
        bot.key(pygame.K_BACKSPACE)
    for ch in "Minérios da base 2":                  # 18 caracteres: corta em 16
        key = {"e": pygame.K_e, "s": pygame.K_s, "a": pygame.K_a, "2": pygame.K_2}.get(ch, 0)
        if key:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=ch, scancode=0))
        pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=ch))
        bot.frames(DT)
    assert app.mode == "chest" and app.name_edit.text == "Minérios da base", app.name_edit.text
    bot.mouse_to((slot_pos(bot, box, 20)[0], slot_pos(bot, box, 20)[1]))   # mouse longe do campo
    while app.t % C.CHEST_NAME_BLINK >= C.CHEST_NAME_BLINK / 2 - 0.05:    # print com o cursor aceso
        bot.frames(DT)
    bot.shot("bau_nome.png")
    bot.key(pygame.K_RETURN)
    assert app.name_edit is None and chest.name == "Minérios da base" and app.mode == "chest"
    # Esc cancela uma edição sem mudar o nome (e não fecha o baú)
    bot.click((app.ui.name_rect.centerx * 2, app.ui.name_rect.centery * 2))
    pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text="xyz"))
    bot.frames(DT)
    bot.key(pygame.K_ESCAPE)
    assert app.name_edit is None and chest.name == "Minérios da base" and app.mode == "chest"
    bot.key(pygame.K_ESCAPE)                            # agora fecha
    assert app.mode == "play" and app.held is None and inv.count("o2") == 2
    # no mundo: o nome flutua em cima do baú (player no alcance do E)
    bot.mouse_to((40, 40))
    bot.frames(0.2)
    assert chest in app.labeled_chests()
    assert app.ui.chest_label_parts(chest) == [("text", "Minérios da base")]   # sem filtro: só o nome
    shot_zoom(bot, "bau_nome_mundo.png", (chest.anchor[0], chest.anchor[1] - 30), k=2)
    bot.shot("bau_nome_mundo_tela.png")
    # o rótulo acompanha o zoom (posição), sem mudar o tamanho da letra
    bot.key(pygame.K_EQUALS)
    bot.frames(0.1)
    bot.shot("bau_nome_zoom.png")
    bot.key(pygame.K_MINUS)

    # o fabricador enxerga o baú da base: os 74 ferro (80 - 6 do baú) e os 30 silício estão no baú
    assert s.available("iron") == 74 and s.available("silicon") == 30

    # Tab: inventário sozinho, com tooltip
    bot.key(pygame.K_TAB)
    assert app.mode == "inventory"
    bot.frames(DT)
    bot.mouse_to(slot_pos(bot, inv, 0))
    bot.frames(0.1)
    bot.shot("inventario.png")
    bot.key(pygame.K_TAB)
    assert app.mode == "play"

    # baú com coisa dentro não desmonta (aviso)
    camx, camy = app.cam
    body = (int((site[0] + 0.5) * C.TILE - camx), int((site[1] + 1) * C.TILE - 20 - camy))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=body, button=3))
    bot.frames(0.1)
    assert chest in s.machines and app.notice == "Esvazie o baú antes de desmontar"

    # inventário cheio: o tile quebra, o minério não entra, aparece o aviso
    s.inventory.clear()
    give(s, iron=200, silicon=150, ice=350)            # 4 + 3 + 7 slots
    s.inventory.add("o2", 1)
    s.inventory.add("melter", 1)
    assert None not in s.inventory.slots
    bot.teleport((64, 66))
    ore = (64, 68)
    s.world.set(*ore, C.IRON)
    bot.frames(0.1)
    pos = bot.tile_on_screen(ore)
    bot.mouse_to(pos)
    bot.mouse_down(pos)
    bot.frames(1.15)
    bot.mouse_up(pos)
    bot.frames(0.3)
    assert s.world.get(*ore) == C.FLOOR and s.inventory.count("iron") == 200
    assert app.notice == "Inventário cheio" and app.notice_time > 0
    bot.shot("inventario_cheio.png")
    s.inventory.clear()
    bot.frames(C.NOTICE_TIME)


def check_energy(bot) -> None:
    """Energia (Marco 2): painel solar pela hotbar, medidor verde/amarelo e, forçando um déficit,
    medidor vermelho + aviso + ritmo no hover + power_low disparado uma vez."""
    from game.systems import Machine
    s, app = bot.state, bot.app
    bot.teleport((64, 66))
    bot.frames(0.1)
    give(s, iron=max(8, s.inventory.count("iron")), silicon=max(6, s.inventory.count("silicon")))
    assert s.craft("solar")
    bot.key(hotbar_key(bot, "solar"))
    assert app.placing == "solar"
    spot = next(t for t in [(62, 67), (61, 68), (63, 68), (60, 67), (66, 68)] if s.can_place("solar", t))
    bot.click(bot.tile_on_screen(spot))
    panel = s.machine_at(spot)
    assert panel is not None and panel.kind == "solar", "o painel devia ter sido colocado"
    assert s.power.production == C.POD_POWER + 3 and not s.power.deficit
    bot.mouse_to(bot.tile_on_screen((64, 69)))
    bot.frames(0.5)
    bot.shot("energia_ok.png")

    # déficit forçado: máquinas nv.2 direto no mundo (o teste é do HUD, não do fabricador)
    free = [(x, y) for y in range(67, 71) for x in range(58, 71)
            if s.world.get(x, y) == C.FLOOR and not s.machine_at((x, y)) and (x, y) not in C.POD_TILES
            and s.world.vein_at(x, y) is None and (x, y) != s.player.tile]
    extra = [Machine("heater_t2", *t) for t in free[::3][:3]]
    s.machines += extra
    assert s.power.deficit and s.power_alert.armed
    bot.frames(0.6)
    assert not s.power_alert.armed, "o power_low devia ter disparado"
    m = extra[0]
    camx, camy = app.cam
    bot.mouse_to((int((m.tx + 0.5) * C.TILE - camx), int((m.ty + 1) * C.TILE - 30 - camy)))
    bot.frames(0.3)
    percent = int(s.power.factor * 100)
    assert app.hint().startswith(f"Ritmo {percent}%"), app.hint()
    bot.shot("energia_deficit.png")
    for machine in extra:
        s.machines.remove(machine)
    bot.frames(0.1)


def check_objectives_midway(bot) -> None:
    """Objetivos no meio do caminho: com ferro e silício 'minerados', o atual vira "Fabrique um baú"."""
    s = bot.state
    s.mined_total.update(iron=10, silicon=4)     # o bot pôs recurso direto no inventário, sem minerar
    bot.frames(1.6)                              # deixa passar o ✓ verde do objetivo concluído
    assert s.ti < 500 and s.fabricator_opened
    shown = bot.app.objectives.lines(s)
    assert shown[0].text == "Fabrique um baú", shown
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


def check_veins(bot) -> None:
    """Estágio 1: os 3 veios perto da base aparecem; mouse em cima de um mostra a dica."""
    s, app = bot.state, bot.app
    cx, cy = C.CRATER_CENTER
    near = [v for v in s.world.veins if math.hypot(v.tx + 1 - cx, v.ty + 1 - cy) <= 20]
    assert sorted(v.resource for v in near) == sorted(C.RESOURCES), near
    # os 3 não cabem juntos na tela (HUD em cima e embaixo): monta um recorte de cada
    # (a dica "Veio de ... · drill libera na Névoa" é conferida pelo assert)
    crops = []
    for vein in sorted(near, key=lambda v: C.RESOURCES.index(v.resource)):
        s.player.x, s.player.y = (vein.tx + 1) * C.TILE, (vein.ty + 4) * C.TILE   # player logo abaixo do veio
        bot.frames(0.1)
        pos = bot.tile_on_screen((vein.tx, vein.ty))
        bot.mouse_to(pos)
        bot.frames(0.05)
        name = C.RESOURCE_NAME[vein.resource]
        assert app.hint() == f"Veio de {name} · drill libera na Névoa", app.hint()
        crop = pygame.Surface((240, 200))
        crop.blit(app.canvas, (0, 0), (pos[0] - 104, pos[1] - 90, 240, 200))
        crops.append(crop)
    sheet = pygame.Surface((240 * 3 + 8, 200))
    for i, c in enumerate(crops):
        sheet.blit(c, (i * 244, 0))
    pygame.image.save(pygame.transform.scale_by(sheet, 2), str(OUT / "veios.png"))
    print("  screenshot: reports/dev/veios.png  (ferro, silício, gelo perto da base, estágio 1)")
    bot.teleport((64, 65))
    bot.frames(0.1)


def check_drill_feature(bot) -> None:
    """Névoa: fabrica a drill (tecla 7), fantasma gruda no veio, extrai, enche, coleta com E, desmonta."""
    s, app = bot.state, bot.app
    assert s.stage >= 2 and s.recipe_status("drill") != "locked"
    give(s, iron=60, silicon=40)
    bot.teleport((64, 65))
    bot.frames(0.1)
    s.craft("drill")
    s.craft("drill")
    assert s.inventory.count("drill") == 2
    cx, cy = C.CRATER_CENTER
    vein = min(s.world.veins, key=lambda v: math.hypot(v.tx - cx, v.ty - cy))
    bot.teleport((vein.tx, vein.ty + 2))          # logo abaixo do veio
    bot.frames(0.1)
    bot.key(hotbar_key(bot, "drill"))
    assert app.placing == "drill"
    # fora de veio: dica e fantasma vermelho
    bot.mouse_to(bot.tile_on_screen((vein.tx + 3, vein.ty + 3)))
    assert app.place_target() is None and app.hint() == "Coloque a drill em cima de um veio"
    # mouse no tile de baixo à direita do veio: o fantasma gruda no canto do veio
    bot.mouse_to(bot.tile_on_screen((vein.tx + 1, vein.ty + 1)))
    bot.frames(0.1)
    assert app.place_target() == (vein.tx, vein.ty) and s.can_place("drill", (vein.tx, vein.ty))
    bot.shot("drill_colocando.png")
    bot.click(bot.tile_on_screen((vein.tx + 1, vein.ty + 1)))
    drill = s.machine_at((vein.tx, vein.ty))
    assert drill is not None and drill.is_drill
    bot.key(pygame.K_ESCAPE)                      # larga a segunda drill da mão
    # deixa trabalhar um pouco (F1 acelera ×10)
    bot.key(pygame.K_F1)
    for _ in range(25):                           # com F1 o O₂ também cai ×10: mantém cheio pra não desmaiar
        s.o2 = C.O2_MAX
        bot.frames(C.DRILL_INTERVAL / C.DEBUG_TIME_SCALE / 4)
    bot.key(pygame.K_F1)
    assert not s.fainted
    assert 0 < drill.stored < C.DRILL_CAPACITY, drill.stored
    ax, ay = drill.anchor
    camx, camy = app.cam
    bot.mouse_to((int(ax - camx), int(ay - 50 - camy)))
    bot.frames(0.3)
    label = C.RESOURCE_NAME[drill.resource]
    assert app.hint().startswith(f"Drill: {drill.stored}/{C.DRILL_CAPACITY} {label}"), app.hint()
    bot.shot("drill_trabalhando.png")
    drill.stored = C.DRILL_CAPACITY - 1
    s._update_machines(C.DRILL_INTERVAL)          # extrai a última unidade (regra real) e enche
    assert drill.full
    bot.frames(0.3)
    assert app.hint().startswith(f"Drill cheia: {C.DRILL_CAPACITY} {label}"), app.hint()
    bot.shot("drill_cheia.png")
    before = s.inventory.count(drill.resource)
    bot.key(pygame.K_e)                            # coleta
    bot.frames(0.3)
    assert s.inventory.count(drill.resource) == before + C.DRILL_CAPACITY and drill.stored == 0
    bot.shot("drill_coletou.png")
    bot.teleport((64, 65))
    bot.frames(0.1)


def shot_zoom(bot, name: str, world_xy, w: int = 240, h: int = 135, k: int = 3) -> None:
    """Recorte w×h da tela em volta de um ponto do mundo, ampliado k× (drone é pequeno: 16 px)."""
    cx, cy = bot.app.cam
    x = max(0, min(C.SCREEN_W - w, int(world_xy[0] - cx - w / 2)))
    y = max(0, min(C.SCREEN_H - h, int(world_xy[1] - cy - h / 2)))
    crop = bot.app.canvas.subsurface((x, y, w, h)).copy()
    pygame.image.save(pygame.transform.scale_by(crop, k), str(OUT / name))
    print(f"  screenshot: reports/dev/{name}  (recorte ampliado {k}×)")


def check_drones(bot) -> None:
    """Marco 3: fabrica a estação, coloca perto do baú da base, drones buscam a drill voando por cima
    de uma parede e entregam no baú. Prints: drones_estacao, drones_voando, drones_entrega."""
    from game import drones
    s, app = bot.state, bot.app
    assert s.recipe_status("drone_station") != "locked"
    bot.teleport((64, 65))
    s.o2 = C.O2_MAX
    bot.frames(0.1)
    give(s, iron=60, silicon=40, ice=20)
    assert s.craft("drone_station")
    chest = s.chests[0]
    # canto 2×2 livre perto do baú (até 3 tiles, dentro do raio de entrega de 6), com o player parado logo abaixo
    site = None
    for ty in range(chest.ty - 3, chest.ty + 3):
        for tx in range(chest.tx - 4, chest.tx + 4):
            s.player.x, s.player.y = (tx + 1) * C.TILE, (ty + 3) * C.TILE + 8
            if s.can_place("drone_station", (tx, ty)) and drones.gap_tiles(type("M", (), {"tx": tx, "ty": ty, "size": 2})(), chest) <= 3:
                site = (tx, ty)
                break
        if site:
            break
    assert site, "sem lugar pra estação perto do baú"
    bot.frames(0.1)
    bot.key(hotbar_key(bot, "drone_station"))
    assert app.placing == "drone_station"
    bot.click(bot.tile_on_screen(site))
    station = s.machine_at(site)
    assert station is not None and station.is_station and station.station.drones == []   # vem vazia
    assert drones.pick_delivery_chest(station, s.chests, "iron") is chest
    # fabrica 2 drones (item) e põe na estação pelo painel (E): clique no drone do inventário
    give(s, iron=20, silicon=10)
    assert s.craft("drone") and s.craft("drone") and s.inventory.count("drone") == 2
    station.station.buffer = {"iron": 12, "ice": 3}
    ax, ay = station.anchor
    s.player.x, s.player.y = ax, ay + 10
    bot.frames(0.1)
    assert s.interaction() == ("station", station)
    bot.key(pygame.K_e)
    assert app.mode == "station" and app.open_station is station
    bot.frames(DT)
    inv = s.inventory
    iron_slot = inv.slots.index(next(st for st in inv.slots if st and st.item == "iron"))
    bot.click(slot_pos(bot, inv, iron_slot))              # minério não entra na estação
    assert app.notice == "Só drones vão na estação" and not station.station.drones
    drone_slot = inv.slots.index(next(st for st in inv.slots if st and st.item == "drone"))
    right_click(bot, slot_pos(bot, inv, drone_slot))      # direito: 1 drone
    assert len(station.station.drones) == 1
    bot.click(slot_pos(bot, inv, drone_slot))             # esquerdo: o resto
    assert [d.pad for d in station.station.drones] == [0, 1] and inv.count("drone") == 0
    bay = next(r for r, k in app.ui.bay_rects if k == 1)
    bot.mouse_to((bay.centerx * 2, bay.centery * 2))      # tooltip do slot de drone
    bot.frames(0.1)
    bot.shot("estacao_inventario.png")
    # buffer: clique direito tira 1, "Pegar tudo" leva o resto
    res_rect = next(r for r, res in app.ui.buffer_rects if res == "iron")
    before = inv.count("iron")
    right_click(bot, (res_rect.centerx * 2, res_rect.centery * 2))
    assert inv.count("iron") == before + 1 and station.station.buffer["iron"] == 11
    button = {a: r for r, a in app.ui.panel_buttons}["take_buffer"]
    bot.click((button.centerx * 2, button.centery * 2))
    assert station.station.stored == 0 and inv.count("iron") == before + 12
    bot.key(pygame.K_e)
    assert app.mode == "play"
    # hover na estação: dica do HUD
    station.station.buffer = {"iron": 12}
    camx, camy = app.cam
    bot.mouse_to((int(ax + 27 - camx), int(ay - 14 - camy)))  # na beirada direita, pra não cobrir os pads
    bot.frames(0.2)
    hint = app.hint()          # no déficit de energia entra um "· ritmo N%" no meio
    assert hint.startswith("Estação: 2/4 drones · buffer 12/50") and hint.endswith("· [E] abrir"), hint
    bot.shot("drones_estacao.png")
    station.station.buffer = {}
    # os 4 slots cheios: 1 e 2 nos pads, 3 e 4 estacionados na frente (recorte ampliado)
    extra = [drones.dock(station, station.station) for _ in range(2)]
    s.player.x, s.player.y = ax + 4 * C.TILE, ay + 2 * C.TILE        # player fora do recorte
    bot.mouse_to((20, 20))
    app.floaters.items.clear()
    app.draw()
    shot_zoom(bot, "estacao_4_drones.png", (ax, ay - 36), w=120, h=80, k=4)
    s.player.x, s.player.y = ax, ay + 10
    for d in extra:
        drones.undock(station.station, d.pad)

    # voo: drill com minério e uma parede no meio do caminho (o drone passa por cima)
    drill = s.drills[0]
    drill.stored = 15
    (sx, sy), (dx, dy) = drones.pad_position(station, 0), drones.hover_position(drill)
    mid = None
    for f in (0.5, 0.4, 0.6, 0.3, 0.7):                   # um ponto do caminho sem máquina embaixo
        x, y = int((sx + (dx - sx) * f) // C.TILE), int((sy + (dy - sy) * f) // C.TILE) + 1
        block = [(x + i, y + j) for i in (-2, -1, 0, 1, 2) for j in (-1, 0, 1, 2)]
        if not any(s.machine_at(t) or t in C.POD_TILES for t in block):
            mid = (x, y)
            break
    assert mid, "sem lugar livre no caminho do drone pra parede de teste"
    carve(s, [(mid[0] + i, mid[1] + j) for i in (-1, 0, 1) for j in (0, 1)], C.ROCK)
    # decolou: abre o painel da estação, o slot dele aparece travado ("EM VOO") e não sai
    for _ in range(60):
        bot.frames(DT)
        if any(d.busy for d in station.station.drones):
            break
    busy = next(d for d in station.station.drones if d.busy)
    s.player.x, s.player.y = ax, ay + 10
    bot.key(pygame.K_e)
    assert app.mode == "station"
    bot.frames(DT)
    bay = next(r for r, k in app.ui.bay_rects if k == busy.pad)
    bot.click((bay.centerx * 2, bay.centery * 2))
    assert busy in station.station.drones and app.notice == "Drone em voo: espere ele pousar"
    bot.mouse_to((bay.centerx * 2 + 2, bay.centery * 2 + 2))
    bot.frames(0.1)
    bot.shot("estacao_drone_voo.png")
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    flyer = None
    for _ in range(600):
        s.o2 = C.O2_MAX
        bot.frames(DT)
        flyer = next((d for d in station.station.drones if d.state == drones.RETURNING), None)
        if flyer and math.hypot(flyer.x - (mid[0] + 0.5) * C.TILE, flyer.y + C.DRONE_SHADOW_DROP
                                - (mid[1] + 0.5) * C.TILE) < 20:
            break
    assert flyer is not None and flyer.cargo == 15, flyer
    s.player.x, s.player.y = (mid[0] + 0.5) * C.TILE + 64, (mid[1] + 3) * C.TILE
    bot.frames(DT)
    bot.mouse_to((20, 20))
    shot_zoom(bot, "drones_voando.png", (flyer.x, flyer.y + 10))

    # entrega no baú: espera o drone pousar e entregar
    deliveries = s.drone_deliveries
    in_chest = chest.storage.count(drill.resource)
    s.player.x, s.player.y = ax + 40, ay + 40
    for _ in range(600):
        s.o2 = C.O2_MAX
        bot.frames(DT)
        if s.drone_deliveries > deliveries:
            break
    bot.frames(0.25)                                       # o "+15" sobe um pouco
    assert chest.storage.count(drill.resource) == in_chest + 15
    cxw, cyw = chest.anchor
    shot_zoom(bot, "drones_entrega.png", ((ax + cxw) / 2, (ay + cyw) / 2 - 30))
    carve(s, [(mid[0] + i, mid[1] + j) for i in (-1, 0, 1) for j in (0, 1)])
    bot.teleport((64, 65))
    bot.frames(0.1)


def check_chest_filter(bot) -> None:
    """Filtro do baú pros drones: clica em "ferro" no seletor do painel e mostra o rótulo no mundo.
    Prints: bau_filtro (painel com o seletor), bau_rotulo (recorte do rótulo em cima do baú)."""
    s, app = bot.state, bot.app
    chest = s.chests[0]
    assert chest.filter == "all"
    ax, ay = chest.anchor
    s.player.x, s.player.y = ax, ay + 10
    s.o2 = C.O2_MAX
    bot.frames(0.1)
    assert s.interaction() == ("chest", chest)
    bot.key(pygame.K_e)
    assert app.mode == "chest"
    bot.frames(DT)
    rect = next(r for r, value in app.ui.filter_buttons if value == "iron")
    bot.click((rect.centerx * 2, rect.centery * 2))
    assert chest.filter == "iron" and app.mode == "chest" and app.held is None
    other = next(r for r, value in app.ui.filter_buttons if value == "ice")
    bot.mouse_to((other.centerx * 2, other.centery * 2))    # hover num botão inativo
    bot.frames(0.1)
    bot.shot("bau_filtro.png")
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    # rótulo no mundo: player perto (sem o mouse em cima)
    bot.mouse_to((20, 20))
    bot.frames(0.1)
    assert chest in app.labeled_chests()
    shot_zoom(bot, "bau_rotulo.png", (ax, ay - 30), w=160, h=90)
    bot.shot("bau_rotulo_tela.png")
    # zoom 2: o rótulo continua em cima do baú
    zoom = app.zoom
    app.set_zoom(2.0, notify=False)
    bot.frames(0.1)
    bot.shot("bau_rotulo_zoom2.png")
    app.set_zoom(zoom, notify=False)
    bot.frames(0.1)


def check_save(bot) -> None:
    """Autosave com o aviso no HUD, "Salvar e sair" pela pausa, tela de título com save e Continuar."""
    s, app = bot.state, bot.app
    bot.teleport((64, 66))
    s.o2 = C.O2_MAX
    bot.frames(0.2)
    # autosave: só conta jogando (pausado o relógio não anda)
    app.autosave_timer = C.AUTOSAVE_INTERVAL - 0.1
    bot.key(pygame.K_ESCAPE)
    bot.frames(0.5)
    assert app.autosave_timer < C.AUTOSAVE_INTERVAL and app.saved_notice == 0, "pausa não pode contar pro autosave"
    bot.key(pygame.K_ESCAPE)
    save.SAVE_PATH.unlink(missing_ok=True)
    bot.frames(0.3)
    assert save.SAVE_PATH.exists() and app.saved_notice > 0, "o autosave devia ter salvo"
    bot.shot("salvo.png")
    bot.frames(C.SAVED_NOTICE_TIME)
    assert app.saved_notice == 0
    # "Salvar e sair" (4ª opção da pausa) volta pra tela de título
    bot.key(pygame.K_ESCAPE)
    for _ in range(3):
        bot.key(pygame.K_s)
    assert app.ui.PAUSE_OPTIONS[app.pause_selected] == "Salvar e sair"
    bot.key(pygame.K_RETURN)
    assert app.mode == "title"
    saved = app.title.saved
    assert saved is not None and saved is not s
    assert saved.world.tiles == s.world.tiles and saved.inventory.to_data() == s.inventory.to_data()
    assert saved.ti == s.ti and len(saved.machines) == len(s.machines) and saved.logs_read == s.logs_read
    assert [label for _, label in app.title.options()] == ["Continuar", "Novo jogo", "Sair"]
    bot.frames(0.5)
    bot.shot("titulo_continuar.png")
    # "Novo jogo" com save existente: pede confirmação; Esc volta
    bot.key(pygame.K_s)
    bot.key(pygame.K_RETURN)
    assert app.title.confirming and app.mode == "title"
    bot.frames(0.2)
    bot.shot("titulo_confirmar.png")
    bot.key(pygame.K_ESCAPE)
    assert not app.title.confirming
    # Continuar pelo mouse
    row = app.title.items[0]
    bot.click((row.centerx * 2, row.centery * 2))
    assert app.mode == "play" and app.state is saved
    bot.frames(0.5)
    bot.state = app.state
    save.SAVE_PATH.unlink(missing_ok=True)


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
    check_veins(bot)

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
    assert s.inventory.count("iron") >= 1, "devia ter ganhado ferro"
    print(f"  inventário depois de minerar: {s.inventory.counts()}")

    print("3) fabricador")
    give(s, iron=60, silicon=30, ice=24)
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
    check_zoom_and_fullscreen(bot)
    check_dismantle(bot)
    check_inventory_and_chest(bot)
    check_energy(bot)
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
    inventory_before = s.inventory.to_data()
    s.o2 = 0.2
    bot.frames(1.4)
    bot.shot("desmaio.png")
    bot.frames(2.0)
    assert not s.fainted and s.o2 == C.O2_MAX and s.inventory.to_data() == inventory_before
    bot.frames(0.5)

    print("6) estágios")
    bot.key(pygame.K_F2)
    bot.frames(1.0)
    assert s.stage == 2
    s.indices["o2"] += 12_914 - s.ti          # exemplo do dono: Ti 12.914 = ~3% do estágio 2
    bot.key(pygame.K_d, hold=0.5)
    bot.shot("stage2.png")
    give(s, iron=40, silicon=30, ice=20)
    bot.key(pygame.K_e)
    bot.frames(0.2)
    bot.shot("crafting_stage2.png")
    bot.key(pygame.K_ESCAPE)
    bot.frames(3.0)                           # deixa o banner do estágio 2 sumir
    check_drill_feature(bot)
    check_drones(bot)
    check_chest_filter(bot)
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

    print("7) save/load e tela de título")
    check_save(bot)

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
