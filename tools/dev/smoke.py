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
from game import rock_respawn  # noqa: E402
from game import save  # noqa: E402
from game import settings  # noqa: E402
from game.app import NUMBER_KEYS, App  # noqa: E402
from game.ui import TAB_CRAFT, TAB_INVENTORY, TAB_LOGS, TI_PANEL_W  # noqa: E402

# o smoke mexe nos volumes: grava num arquivo temporário, nunca no settings.json de verdade
import tempfile  # noqa: E402
settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_smoke_settings.json"
# ...e o save também: o smoke nunca deixa um saves/slot1.json de verdade pra trás
save.SAVE_PATH = Path(tempfile.gettempdir()) / "hesper_smoke_save" / "slot1.json"

# Tempestade (v0.4): sem rajada sorteada no smoke. Uma rajada no meio de outra cena empurra o player e
# quebra posições e dicas; quem quer rajada (check_storm_gust) liga ela na mão, no pico e sem fim.
C.STORM_GUST_FIRST = C.STORM_GUST_EVERY = (1e9, 1e9)

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
            if w.get(tx, ty) == kind and w.is_floor(tx, ty + 1) and w.is_floor(tx, ty + 2):
                d = w.dist_from_center(tx, ty)
                if best is None or d < best[0]:
                    best = (d, (tx, ty))
    return best[1]


def crop_around_player(bot, w=96, h=80) -> pygame.Surface:
    cx, cy = bot.app.cam
    x, y = int(bot.state.player.x - cx), int(bot.state.player.y - cy)
    return bot.app.frame.subsurface((x - w // 2, y - h + max(16, h // 3), w, h)).copy()


def check_directions_and_order(bot) -> None:
    """Monta 2 imagens ampliadas: o player andando nas 4 direções e a ordem de desenho com uma máquina."""
    s = bot.state
    frames = []
    for key in (pygame.K_s, pygame.K_w, pygame.K_d, pygame.K_a):
        bot.teleport((96, 99))
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
    bot.teleport((96, 98))
    bot.frames(0.1)


def carve(state, tiles, kind=C.SAND):
    for t in tiles:
        state.world.set(*t, kind)


def check_walls_and_hover(bot) -> None:
    """Paredes altas, túnel de 1 tile, player escondido atrás do topo e cursor em cima de máquina."""
    s = bot.state
    # tela interna sem canal alfa (causa do quadrado preto no macOS, playtest 1)
    assert bot.app.canvas.get_masks()[3] == 0, "canvas não pode ter canal alfa"

    # 1) túnel horizontal e vertical de 1 tile cavados num maciço, longe da base
    cx, cy = 96, 128
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
    bot.teleport((96, 98))
    bot.frames(0.1)
    give(s, iron=60, silicon=30, ice=40)
    s.craft("melter")
    s.place("melter", (94, 99))
    s.craft("melter")
    bot.key(hotbar_key(bot, "melter"))
    assert bot.app.placing == "melter"
    bot.mouse_to(bot.tile_on_screen((94, 99)))          # fantasma em cima da máquina colocada (inválido)
    bot.frames(0.2)
    shot_hover = pygame.Surface((240, 120))
    cxp, cyp = bot.tile_on_screen((94, 99))
    shot_hover.blit(bot.app.frame, (0, 0), (cxp - 60, cyp - 80, 120, 120))
    bot.mouse_to(bot.tile_on_screen((92, 99)))          # fantasma num lugar válido, ao lado
    bot.frames(0.2)
    bot.app.placing = None
    shot_hover.blit(bot.app.frame, (120, 0), (cxp - 100, cyp - 80, 120, 120))
    pygame.image.save(pygame.transform.scale_by(shot_hover, 3), str(OUT / "hover_maquina.png"))
    print("  screenshot: reports/dev/hover_maquina.png  (esquerda: fantasma sobre máquina · direita: fantasma ao lado)")
    s.inventory.remove("melter", 99)


def check_storm_gust(bot) -> None:
    """Tempestade (v0.4, trilha B): rajada empurrando o player parado pra leste, o mesmo andando contra, a
    parede segurando, o menu aberto sem empurrão e o aviso RAJADA no HUD. Liga state.storm só na cena."""
    s = bot.state
    saved_storm = s.storm
    s.storm = 1.0
    w = s.weather
    w.dominant = w.angle = w.target = 0.0          # vento pra leste
    w.retarget_in = 1e9
    w._update_wind_vector()
    w.gust, w.gust_left = 1.0, 1e9                 # rajada no pico, sem acabar
    cx, cy = 130, 112                              # campo aberto longe da base, com uma parede à direita
    carve(s, [(x, y) for x in range(cx - 8, cx + 9) for y in range(cy - 4, cy + 4)])
    carve(s, [(cx + 6, y) for y in range(cy - 4, cy + 4)], C.ROCK)
    bot.teleport((cx - 4, cy))
    s.o2 = C.O2_MAX
    bot.frames(0.2)
    x0 = s.player.x
    bot.frames(1.0)                                # parado: desliza com o vento
    slid = s.player.x - x0
    assert slid > C.PLAYER_SPEED * C.STORM_PUSH * 0.8, f"a rajada devia empurrar o player parado ({slid:.1f} px)"
    assert bot.app.ui.gust_rect is not None, "o aviso RAJADA devia aparecer no HUD"
    bot.shot("tempestade_rajada.png")
    x0 = s.player.x
    bot.key(pygame.K_a, hold=0.5)                  # contra o vento: anda, mais devagar
    against = x0 - s.player.x
    assert 0 < against < C.PLAYER_SPEED * 0.6, f"contra o vento devia andar mais devagar ({against:.1f} px)"
    bot.frames(9.0)                                # empurrado até a parede: encosta e para
    wall_left = (cx + 6) * C.TILE
    right = s.player.box[0] + s.player.box[2]
    assert wall_left - 1 <= right <= wall_left + 0.01, f"a rajada devia encostar na parede sem atravessar ({right})"
    bot.shot("tempestade_parede.png")
    x0 = s.player.x
    bot.key(pygame.K_TAB)                          # inventário aberto: sem empurrão
    bot.frames(0.5)
    assert bot.app.mode == "inventory" and s.player.x == x0, "com tela aberta o vento não empurra"
    bot.key(pygame.K_TAB)
    w.gust, w.gust_left = 0.0, 0.0                 # devolve o clima calmo pro resto do smoke
    s.storm = saved_storm
    bot.frames(0.2)
    assert bot.app.ui.gust_rect is None


def check_drill(bot) -> None:
    """Minera nas 4 direções (sem quebrar) e monta reports/dev/broca.png."""
    s = bot.state
    cx, cy = 72, 132
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
    # teclado: desce pro "Efeitos" e abaixa 3 vezes (ex.: padrão 40% -> 10%)
    sfx_before = app.settings["sfx"]
    bot.key(pygame.K_s)
    for _ in range(3):
        bot.key(pygame.K_a)
    assert app.settings["sfx"] == round(max(0.0, sfx_before - 0.3), 2), app.settings
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
    assert ui.controls_pages == 2, "480×270: os controles vão em 2 páginas"
    bot.key(pygame.K_d)                            # D: próxima página
    assert app.controls_page == 1
    bot.frames(DT)
    bot.shot("pausa_controles_2.png")
    prev = next(rect for rect, step in ui.pause_page_buttons if step == -1)
    bot.click((prev.centerx * 2, prev.centery * 2))   # clique no "<": volta
    assert app.controls_page == 0
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
    bot.teleport((96, 98))
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
    tile_check((92, 94))
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
    tile_check((94, 96))
    bot.key(pygame.K_KP_PLUS)
    bot.key(pygame.K_KP_PLUS)
    assert app.zoom == 2.0
    hover_machine_check()
    tile_check((95, 96))
    # fantasma de colocação no tile certo com zoom
    s.inventory.add("o2", 1)
    bot.key(hotbar_key(bot, "o2"))
    assert app.placing == "o2"
    target = (97, 96)
    bot.mouse_to(bot.tile_on_screen(target))
    assert app.place_target() == target
    app.floaters.add("+15 FERRO", s.player.x, s.player.y - 40, C.ORE_COLORS["iron"][0])
    bot.frames(0.3)
    bot.shot("zoom_in.png")
    bot.key(pygame.K_ESCAPE)
    assert app.placing is None
    s.inventory.remove("o2", 1)
    # o HUD não muda de tamanho: a hotbar fica no mesmo lugar em qualquer zoom (compara a faixa de baixo)
    hud_zoom = app.frame.subsurface((0, C.SCREEN_H - 60, C.SCREEN_W, 60)).copy()
    bot.key(pygame.K_KP_MINUS)
    bot.key(pygame.K_MINUS)
    assert app.zoom == 1.0
    hud_normal = app.frame.subsurface((0, C.SCREEN_H - 60, C.SCREEN_W, 60)).copy()
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
    bot.teleport((96, 98))
    bot.frames(0.1)
    give(s, iron=60, silicon=30, ice=40)
    kind = "heater" if s.recipe_status("heater") == "ok" else "o2"   # aquecedor só libera com Ti 500
    s.craft(kind)
    s.place(kind, (98, 98))
    m = s.machine_at((98, 98))
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
    s.place(kind, (98, 98))      # devolve a máquina pro resto do smoke


def check_inventory_and_chest(bot) -> None:
    """Hotbar, Tab, baú (pegar/soltar/metade/Shift+clique), baú com coisa não desmonta, inventário cheio."""
    s, app = bot.state, bot.app
    bot.teleport((96, 98))
    s.o2 = C.O2_MAX
    s.inventory.clear()
    give(s, iron=80, silicon=30, ice=24)                # ferro em 2 pilhas (50 + 30)
    s.inventory.add("o2", 2)
    assert s.craft("chest")
    # hotbar: tecla do baú seleciona o slot e já entra no modo de colocar
    bot.key(hotbar_key(bot, "chest"))
    assert app.placing == "chest"
    site = (95, 99)                                     # dentro da zona de O₂ da base
    assert s.world.is_floor(*site) and s.machine_at(site) is None
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
    # no mundo: o nome flutua em cima do baú só com o mouse em cima dele
    bot.mouse_to((40, 40))
    bot.frames(0.2)
    assert app.labeled_chests() == []                   # perto, mas sem apontar: nada
    from game import viewport
    pos = viewport.world_to_canvas((chest.anchor[0], chest.anchor[1] - 8), app.cam, app.zoom)
    bot.mouse_to((round(pos[0]), round(pos[1])))
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
    bot.teleport((96, 98))
    ore = (96, 100)
    s.world.set(*ore, C.IRON)
    bot.frames(0.1)
    pos = bot.tile_on_screen(ore)
    bot.mouse_to(pos)
    bot.mouse_down(pos)
    bot.frames(1.15)
    bot.mouse_up(pos)
    bot.frames(0.3)
    assert s.world.is_floor(*ore) and s.inventory.count("iron") == 200
    assert app.notice == "Inventário cheio" and app.notice_time > 0
    bot.shot("inventario_cheio.png")
    s.inventory.clear()
    bot.frames(C.NOTICE_TIME)


def check_energy(bot) -> None:
    """Energia (Marco 2): painel solar pela hotbar, medidor verde/amarelo e, forçando um déficit,
    medidor vermelho + aviso + ritmo no hover + power_low disparado uma vez."""
    from game.systems import Machine
    s, app = bot.state, bot.app
    bot.teleport((96, 98))
    bot.frames(0.1)
    give(s, iron=max(8, s.inventory.count("iron")), silicon=max(6, s.inventory.count("silicon")))
    assert s.craft("solar")
    bot.key(hotbar_key(bot, "solar"))
    assert app.placing == "solar"
    spot = next(t for t in [(94, 99), (93, 100), (95, 100), (92, 99), (98, 100)] if s.can_place("solar", t))
    bot.click(bot.tile_on_screen(spot))
    panel = s.machine_at(spot)
    assert panel is not None and panel.kind == "solar", "o painel devia ter sido colocado"
    assert s.power.production == C.POD_POWER + C.POWER_GEN["solar"] and not s.power.deficit
    bot.mouse_to(bot.tile_on_screen((96, 101)))
    bot.frames(0.5)
    bot.shot("energia_ok.png")

    # déficit forçado: máquinas nv.2 direto no mundo (o teste é do HUD, não do fabricador)
    free = [(x, y) for y in range(99, 103) for x in range(90, 103)
            if s.world.is_floor(x, y) and not s.machine_at((x, y)) and (x, y) not in C.POD_TILES
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
    """Prints da mancha do próximo estágio se espalhando a partir da base e das máquinas.
    O estágio oficial fica em `stage` durante os prints (sem banner nem tempestade) e volta no fim."""
    s = bot.state
    before = dict(s.indices)
    stage_before, storm_before = s.stage, s.storm
    s.stage = stage                              # sem stage_up: o banner não aparece nos prints
    s.storm = 1.0 if stage <= C.STORM_STAGE else 0.0
    bot.teleport((96, 98))
    s.o2 = C.O2_MAX
    for name, fraction in shots:
        s.indices.update(o2=ti_in_window(stage, fraction), heat=0.0, water=0.0)
        bot.frames(0.1)
        assert s.stage == stage, "a transição não pode trocar o estágio oficial antes do limiar"
        bot.shot(name)
    s.indices.update(before)
    s.stage, s.storm = stage_before, storm_before
    bot.frames(DT)


def check_arid(bot) -> None:
    """Tempestade -> Árido: o Ti bate o limiar do Árido, aparece o banner "ESTÁGIO 2 · CÉU LIMPO" e a
    tempestade some em STORM_FADE_S (prints: banner_arido, arido)."""
    s, app = bot.state, bot.app
    assert s.stage == C.STORM_STAGE and s.storm == 1.0
    bot.teleport((96, 98))
    s.o2 = C.O2_MAX
    s.indices["o2"] += C.STAGES[C.ARID_STAGE - 1].ti - s.ti
    bot.frames(0.8)
    assert s.stage == C.ARID_STAGE and app.banner_stage == C.ARID_STAGE
    assert 0.9 < s.storm < 1.0, s.storm               # começou a baixar
    bot.shot("banner_arido.png")
    bot.frames(C.STORM_FADE_S)
    assert s.storm == 0.0
    bot.shot("arido.png")


def check_veins(bot) -> None:
    """Estágio 1: um veio de cada minério (longe, no deserto); mouse em cima de um mostra a dica."""
    s, app = bot.state, bot.app
    cx, cy = C.BASE_TILE
    near = [min((v for v in s.world.veins if v.resource == r), key=lambda v: math.hypot(v.tx - cx, v.ty - cy))
            for r in C.RESOURCES]
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
        crop.blit(app.frame, (0, 0), (pos[0] - 104, pos[1] - 90, 240, 200))
        crops.append(crop)
    sheet = pygame.Surface((240 * 3 + 8, 200))
    for i, c in enumerate(crops):
        sheet.blit(c, (i * 244, 0))
    pygame.image.save(pygame.transform.scale_by(sheet, 2), str(OUT / "veios.png"))
    print("  screenshot: reports/dev/veios.png  (ferro, silício, gelo, estágio 1)")
    bot.teleport((96, 97))
    bot.frames(0.1)


def check_drill_feature(bot) -> None:
    """Névoa: fabrica a drill (tecla 7), fantasma gruda no veio, extrai, enche, abre o painel (E), liga o
    Envia, tira 1 e coleta o resto com Shift+E. Prints: drill_*, logistica_drill."""
    s, app = bot.state, bot.app
    assert s.stage >= C.MIST_STAGE and s.recipe_status("drill") != "locked"
    give(s, iron=60, silicon=40)
    bot.teleport((96, 97))
    bot.frames(0.1)
    s.craft("drill")
    s.craft("drill")
    assert s.inventory.count("drill") == 2
    cx, cy = C.BASE_TILE
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
    bot.key(pygame.K_F3)                          # F3: modo rápido (player ×2, broca ×5), junto com o F1 no topo
    assert s.fast and s.player_speed == C.PLAYER_SPEED * C.DEBUG_SPEED
    bot.shot("debug_hud.png")
    bot.key(pygame.K_F3)
    assert not s.fast
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
    # E abre o painel da drill: vem sem nada configurado; liga o Envia e troca o lote
    assert drill.sends == set()
    bot.key(pygame.K_e)
    assert app.mode == "drill" and app.open_drill is drill, app.mode
    bot.frames(DT)
    assert not any(v[0] == "recv" for _, v in app.ui.logistics_buttons)   # a drill não recebe
    bot.shot("logistica_drill_vazia.png")
    send = next(r for r, v in app.ui.logistics_buttons if v == ("send", drill.resource))
    bot.click((send.centerx * 2, send.centery * 2))
    assert drill.sends == {drill.resource} and app.mode == "drill"
    lote = next(r for r, v in app.ui.logistics_buttons if v == ("batch", 5))
    bot.click((lote.centerx * 2, lote.centery * 2))
    assert drill.batch == 5
    inv = s.inventory
    iron_slot = next(i for i, st in enumerate(inv.slots) if st and st.item == "iron")
    bot.click(slot_pos(bot, inv, iron_slot))      # do inventário pra drill: não pode
    assert app.notice == "A drill só produz: não guarda nada"
    right_click(bot, slot_pos(bot, drill.storage, 0))   # direito: tira 1
    assert drill.stored == C.DRILL_CAPACITY - 1 and inv.count(drill.resource) == before + 1
    bot.mouse_to((send.centerx * 2, send.centery * 2))    # tooltip do toggle
    bot.frames(0.1)
    bot.shot("logistica_drill.png")
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    shift_key(bot, pygame.K_e)                     # Shift+E: coleta o resto sem abrir
    assert app.mode == "play"
    bot.frames(0.3)
    assert s.inventory.count(drill.resource) == before + C.DRILL_CAPACITY and drill.stored == 0
    bot.shot("drill_coletou.png")
    bot.teleport((96, 97))
    bot.frames(0.1)


def shot_zoom(bot, name: str, world_xy, w: int = 240, h: int = 135, k: int = 3) -> None:
    """Recorte w×h da tela em volta de um ponto do mundo, ampliado k× (drone é pequeno: 16 px)."""
    cx, cy = bot.app.cam
    z = bot.app.zoom
    x = max(0, min(C.SCREEN_W - w, int((world_xy[0] - cx) * z - w / 2)))
    y = max(0, min(C.SCREEN_H - h, int((world_xy[1] - cy) * z - h / 2)))
    crop = bot.app.frame.subsurface((x, y, w, h)).copy()
    pygame.image.save(pygame.transform.scale_by(crop, k), str(OUT / name))
    print(f"  screenshot: reports/dev/{name}  (recorte ampliado {k}×)")


def check_drones(bot) -> None:
    """Marco 3: fabrica a estação, coloca perto do baú da base, configura o baú (Recebe tudo), e os drones
    levam o lote da drill (Envia) voando por cima de uma parede. Prints: drones_estacao, drones_voando, drones_entrega."""
    from game import drones
    s, app = bot.state, bot.app
    assert s.recipe_status("drone_station") != "locked"
    bot.teleport((96, 97))
    s.o2 = C.O2_MAX
    bot.frames(0.1)
    give(s, iron=60, silicon=40, ice=20)
    assert s.craft("drone_station")
    chest = s.chests[0]
    # canto 2×2 livre perto do baú (até 3 tiles: o alcance é o mapa todo, mas fica bonito junto), player logo abaixo
    site = None
    for ty in range(chest.ty - 3, chest.ty + 3):
        for tx in range(chest.tx - 4, chest.tx + 4):
            s.player.x, s.player.y = (tx + 1) * C.TILE, (ty + 3) * C.TILE + 8
            gap = max(max(tx - chest.tx, 0, chest.tx - (tx + 1)), max(ty - chest.ty, 0, chest.ty - (ty + 1)))
            if s.can_place("drone_station", (tx, ty)) and gap <= 3:
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
    for r in C.RESOURCES:                                 # o baú da base recebe tudo (config. pelo painel no check_logistics)
        drones.toggle_receive(chest, r)
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
    assert hint.startswith("Estação: 2/4 drones · sobras 12") and hint.endswith("· [E] abrir"), hint
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
    drill.batch = 10
    assert drill.sends == {drill.resource}
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
    flyer, best = None, None
    for _ in range(2400):                    # até 40 s: o veio mais perto pode estar a ~70 tiles
        s.o2 = C.O2_MAX
        bot.frames(DT)
        flyer = next((d for d in station.station.drones if d.state == drones.CARRYING), None)
        if flyer is None:
            continue
        # o print sai no ponto da volta mais perto da parede de teste (o drone pode vir de outro pad)
        dist = math.hypot(flyer.x - (mid[0] + 0.5) * C.TILE, flyer.y + C.DRONE_SHADOW_DROP - (mid[1] + 0.5) * C.TILE)
        if best is not None and dist > best and best < 48:
            break
        best = dist if best is None else min(best, dist)
    assert flyer is not None and flyer.cargo == 10, flyer          # o lote da drill
    s.player.x, s.player.y = (mid[0] + 0.5) * C.TILE + 64, (mid[1] + 3) * C.TILE
    bot.frames(DT)
    bot.mouse_to((20, 20))
    shot_zoom(bot, "drones_voando.png", (flyer.x, flyer.y + 10))

    # entrega no baú: espera o drone pousar e entregar
    deliveries = s.drone_deliveries
    in_chest = chest.storage.count(drill.resource)
    s.player.x, s.player.y = ax + 40, ay + 40
    for _ in range(2400):
        s.o2 = C.O2_MAX
        bot.frames(DT)
        if s.drone_deliveries > deliveries:
            break
    bot.frames(0.25)                                       # o "+10" sobe um pouco
    assert chest.storage.count(drill.resource) == in_chest + 10
    cxw, cyw = chest.anchor
    shot_zoom(bot, "drones_entrega.png", ((ax + cxw) / 2, (ay + cyw) / 2 - 30))
    carve(s, [(mid[0] + i, mid[1] + j) for i in (-1, 0, 1) for j in (0, 1)])
    bot.teleport((96, 97))
    bot.frames(0.1)


def check_logistics(bot) -> None:
    """Logística no baú: seção DRONES (Envia/Recebe/Lote), dica de "nada configurado" num baú novo e o
    rótulo ↓recebe ↑envia no mundo. Prints: logistica_bau, logistica_bau_vazio, bau_rotulo*, logistica_mundo."""
    from game import drones
    from game.systems import Machine
    s, app = bot.state, bot.app
    chest = s.chests[0]
    assert chest.receives == set(C.RESOURCES)
    ax, ay = chest.anchor
    s.player.x, s.player.y = ax, ay + 10
    s.o2 = C.O2_MAX
    bot.frames(0.1)
    assert s.interaction() == ("chest", chest)
    bot.key(pygame.K_e)
    assert app.mode == "chest"
    bot.frames(DT)
    send_ice = next(r for r, v in app.ui.logistics_buttons if v == ("send", "ice"))
    bot.click((send_ice.centerx * 2, send_ice.centery * 2))   # Envia gelo: sai do Recebe
    assert chest.sends == {"ice"} and chest.receives == {"iron", "silicon"} and app.mode == "chest"
    lote = next(r for r, v in app.ui.logistics_buttons if v == ("batch", 20))
    bot.click((lote.centerx * 2, lote.centery * 2))
    assert chest.batch == 20 and app.held is None
    recv = next(r for r, v in app.ui.logistics_buttons if v == ("recv", "iron"))
    bot.mouse_to((recv.centerx * 2, recv.centery * 2))        # tooltip "Recebe ferro"
    bot.frames(0.1)
    assert app.hovered_slot_label((recv.centerx, recv.centery)).startswith("Recebe ferro")
    bot.shot("logistica_bau.png")
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    # baú novo do lado: nada configurado (dica no painel)
    fresh = None
    for t in ((chest.tx + 1, chest.ty), (chest.tx - 1, chest.ty), (chest.tx, chest.ty + 1)):
        if not s.machine_at(t) and s.world.is_floor(*t) and t not in C.POD_TILES:
            fresh = Machine("chest", *t, name="Gelo")
            s.machines.append(fresh)
            break
    if fresh is not None:
        s.player.x, s.player.y = fresh.anchor[0], fresh.anchor[1] + 10
        bot.frames(0.1)
        app.open_chest = app.renderer.open_chest = fresh
        app.mode = "chest"
        bot.mouse_to((20, 20))
        bot.frames(DT)
        assert not drones.configured(fresh)
        bot.shot("logistica_bau_vazio.png")
        app.set_mode("play")
        drones.toggle_send(fresh, "ice")
    # rótulo no mundo: só com o mouse em cima do baú
    s.player.x, s.player.y = ax, ay + 10
    bot.frames(0.1)
    from game import viewport
    pos = viewport.world_to_canvas((ax, ay - 8), app.cam, app.zoom)
    bot.mouse_to((round(pos[0]), round(pos[1])))
    bot.frames(0.1)
    assert chest in app.labeled_chests()
    shot_zoom(bot, "bau_rotulo.png", (ax, ay - 30), w=240, h=90)
    bot.shot("bau_rotulo_tela.png")
    zoom = app.zoom
    app.set_zoom(2.0, notify=False)
    bot.frames(0.1)
    bot.shot("bau_rotulo_zoom2.png")
    app.set_zoom(zoom, notify=False)
    bot.frames(0.1)

    # mundo: uma drill LONGE (mapa todo) mandando pro baú da base; 4 drones, voando e chegando
    station = s.stations[0]
    while station.station.free_slots():
        drones.dock(station, station.station)
    far_vein = max((v for v in s.world.veins if not s.machine_at((v.tx, v.ty))),
                   key=lambda v: math.hypot(v.tx - 64, v.ty - 64))
    far = Machine("drill", far_vein.tx, far_vein.ty, resource=far_vein.resource,
                  stored_init=C.DRILL_CAPACITY, sends={far_vein.resource}, batch=5)
    s.machines.append(far)
    chest.receives.add(far.resource)
    chest.sends.discard(far.resource)
    dist = drones.tile_distance(station, far)
    print(f"  drill longe: {dist:.0f} tiles da estação ({far.resource})")
    assert dist > 35
    s.player.x, s.player.y = ax + 8, ay + 12               # no alcance do E: o rótulo ↓↑ aparece
    app.set_zoom(0.75, notify=False)
    near = []
    for _ in range(int(40 / DT)):                          # até um drone chegar perto da base com carga
        s.o2 = C.O2_MAX
        bot.frames(DT)
        # perto da base e no meio da tela (não atrás da hotbar nem dos painéis: o veio pode estar em qualquer lado)
        near = [d for d in station.station.drones if d.state == drones.CARRYING
                and 5 * C.TILE < math.hypot(d.x - ax, d.y - ay) < 11 * C.TILE
                and 140 < (d.x - app.cam[0]) * app.zoom < C.SCREEN_W - 140
                and 120 < (d.y - app.cam[1]) * app.zoom < C.SCREEN_H - 130]
        if near:
            break
    assert near, [(d.state, d.cargo) for d in station.station.drones]
    bot.mouse_to((20, 20))
    bot.frames(DT)
    for d in near:
        print(f"  drone no print: tela ({(d.x - app.cam[0]) * app.zoom:.0f}, {(d.y - app.cam[1]) * app.zoom:.0f}), "
              f"carga {d.cargo} {d.resource}")
    bot.shot("logistica_mundo.png")
    shot_zoom(bot, "logistica_mundo_drone.png", (near[0].x, near[0].y + 10), w=240, h=135, k=3)
    # o mapa todo de longe: estação, drill longe e os drones no caminho (mundo 3840×2160 reduzido)
    for _ in range(int(4 / DT)):                           # mais uns segundos: drones espalhados no caminho
        s.o2 = C.O2_MAX
        bot.frames(DT)
    big = pygame.Surface((3840, 2160), 0, app.canvas)
    mx, my = (station.anchor[0] + far.anchor[0]) / 2, (station.anchor[1] + far.anchor[1]) / 2
    cam = (int(mx - 1920), int(my - 1080))
    app.renderer.draw(big, s, cam, app.t, None)
    small = pygame.transform.smoothscale(big, (960, 540))
    for d in station.station.drones:                       # reduzido o drone some: anel amarelo só neste print
        if d.in_air:
            pygame.draw.circle(small, (255, 210, 90), ((d.x - cam[0]) / 4, (d.y - cam[1]) / 4), 7, 2)
    for m in (station, far):
        pygame.draw.circle(small, (255, 255, 255), ((m.anchor[0] - cam[0]) / 4, (m.anchor[1] - 32 - cam[1]) / 4), 11, 1)
    pygame.image.save(small, str(OUT / "logistica_mapa.png"))
    print("  screenshot: reports/dev/logistica_mapa.png  (mundo reduzido 4×, anéis marcam drones/estação/drill)")
    app.set_zoom(zoom, notify=False)
    for _ in range(int(40 / DT)):                          # deixa entregar pra conferir que chega
        s.o2 = C.O2_MAX
        bot.frames(DT)
        if chest.storage.count(far.resource) >= 5 and far.stored < C.DRILL_CAPACITY:
            break
    assert far.stored < C.DRILL_CAPACITY
    for d in list(station.station.drones)[2:]:
        d.state, d.source, d.dest, d.cargo, d.resource = drones.LANDED, None, None, 0, None
        drones.undock(station.station, d.pad)
    s.machines.remove(far)
    if fresh is not None:
        s.machines.remove(fresh)
    bot.teleport((96, 97))
    bot.frames(0.1)


def check_final_polish(bot) -> None:
    """Polimento final do v0.2: E abre o que está debaixo do mouse (com contorno), drones na mesma rota
    separados e floaters desviando do rótulo do baú. Prints: e_mouse, drones_separados, rotulo_floater."""
    from game import drones, viewport
    from game.systems import Machine
    s, app = bot.state, bot.app
    bot.teleport((96, 97))
    s.o2 = C.O2_MAX
    bot.frames(0.1)
    chest = s.chests[0]
    ax, ay = chest.anchor

    def mouse_on(machine):
        x, y, w, h = machine.sprite_rect
        pos = viewport.world_to_canvas((x + w / 2, y + h / 2), app.cam, app.zoom)
        bot.mouse_to((round(pos[0]), round(pos[1])))
        bot.frames(DT)

    # 1) dois baús no alcance: sem mouse, o E abre o mais perto; com o mouse no outro, abre o outro
    other = None
    for t in ((chest.tx + 1, chest.ty), (chest.tx - 1, chest.ty)):
        if not s.machine_at(t) and s.world.is_floor(*t) and t not in C.POD_TILES:
            other = Machine("chest", *t, name="Ferro")
            s.machines.append(other)
            break
    assert other is not None
    s.player.x, s.player.y = ax, ay + 10
    bot.mouse_to((20, 20))
    bot.frames(DT)
    assert app.e_target() == ("chest", chest), app.e_target()
    mouse_on(other)
    assert s.in_reach("chest", other)
    assert app.e_target() == ("chest", other) and app.renderer.highlight is other
    assert app.hint().endswith("· [E] abrir"), app.hint()
    shot_zoom(bot, "e_mouse.png", (ax, ay - 20), w=160, h=90, k=4)
    bot.key(pygame.K_e)
    assert app.mode == "chest" and app.open_chest is other
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    bot.mouse_to((20, 20))
    bot.frames(DT)
    assert app.hint() == f"[E] Abrir baú: {chest.name}", app.hint()
    s.machines.remove(other)

    # 2) quatro drones na mesma rota (mesmo ponto lógico): cada um na faixa dele
    station = s.stations[0]
    while station.station.free_slots():
        drones.dock(station, station.station)
    chest.receives.add("iron")
    start = (ax - 8 * C.TILE, ay + 3 * C.TILE)                    # embaixo à esquerda (longe do HUD)
    for k, d in enumerate(station.station.drones):
        d.state, d.dest, d.resource, d.cargo = drones.CARRYING, chest, "iron", 1
        d.x, d.y = start[0] + k * 3, start[1] + k                  # praticamente o mesmo ponto
    s.player.x, s.player.y = ax, ay + 2 * C.TILE
    bot.mouse_to((20, 20))
    bot.frames(0.35)
    lead = station.station.drones[0]
    cx, cy = bot.app.cam
    z = bot.app.zoom
    def crop(world_xy, w=150, h=100):
        x = max(0, min(C.SCREEN_W - w, int((world_xy[0] - cx) * z - w / 2)))
        y = max(0, min(C.SCREEN_H - h, int((world_xy[1] - cy) * z - h / 2)))
        return bot.app.frame.subsurface((x, y, w, h)).copy()
    flying = crop((lead.x, lead.y + 8))
    spread = {(round(d.x), round(d.y)) for d in station.station.drones}
    print(f"  drones na rota: {len(spread)} posições lógicas quase iguais, desenho separado por faixa")
    for _ in range(int(3 / DT)):                                  # espera eles soltarem em cima do baú
        s.o2 = C.O2_MAX
        bot.frames(DT)
        if all(d.state == drones.DROPPING for d in station.station.drones):
            break
    bot.frames(0.25)
    over = crop((ax, ay - 50))
    sheet = pygame.Surface((300 + 6, 100), 0, flying)
    sheet.fill((20, 20, 20))
    sheet.blit(flying, (0, 0))
    sheet.blit(over, (156, 0))
    pygame.image.save(pygame.transform.scale_by(sheet, 3), str(OUT / "drones_separados.png"))
    print("  screenshot: reports/dev/drones_separados.png  (esquerda: 4 drones na mesma rota · direita: soltando no baú)")
    for _ in range(int(15 / DT)):                                 # deixa pousar e volta pra 2 drones
        s.o2 = C.O2_MAX
        bot.frames(DT)
        if all(d.state == drones.LANDED for d in station.station.drones):
            break
    for d in list(station.station.drones)[2:]:
        d.state, d.source, d.dest, d.cargo, d.resource = drones.LANDED, None, None, 0, None
        drones.undock(station.station, d.pad)

    # 3) rótulo do baú x floaters: quem ia passar por trás do rótulo nasce acima dele
    s.player.x, s.player.y = ax + 8, ay + 12
    bot.frames(0.5)                                               # a câmera chega no player
    mouse_on(chest)
    assert chest in app.labeled_chests()
    app.floaters.items.clear()
    app.floaters.add("+10 SILICIO", ax, ay - 78, C.ORE_COLORS["silicon"][0])   # entrega do drone
    app.floaters.add("+O₂", ax + 6, ay - 30, C.INDEX_COLOR["o2"])              # máquina logo embaixo
    app.floaters.add("+5 FERRO", ax - 4, ay - 46, C.ORE_COLORS["iron"][0])
    bot.frames(0.35)
    assert chest in app.labeled_chests()
    label = app.ui.chest_label_rects[0]
    print(f"  rótulo do baú (UI): {tuple(label)} · floaters: {[f.text for f in app.floaters.items]}")
    shot_zoom(bot, "rotulo_floater.png", (ax, ay - 70), w=220, h=150, k=3)
    bot.mouse_to((20, 20))
    bot.teleport((96, 97))
    bot.frames(0.1)


def shift_key(bot, key: int) -> None:
    """Tecla com o Shift segurado (Shift+Enter no fabricador)."""
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, mod=0, unicode="", scancode=0))
    bot.frames(DT)
    bot.key(key)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_LSHIFT, mod=0, unicode="", scancode=0))
    bot.frames(DT)


def wait_blink_on(bot) -> None:
    """Espera o raio de "sem energia" estar aceso (ele pisca)."""
    for _ in range(60):
        if (bot.app.t * 2.5) % 1 < 0.3:
            return
        bot.frames(DT)


def check_polish(bot) -> None:
    """Polimento do v0.2: floaters empilhados, barrinha da drill, raio de sem energia, fabricador com abas,
    rolagem e lote (Shift+Enter) e a decolagem do drone."""
    from game import drones
    from game.systems import Machine
    s, app = bot.state, bot.app
    bot.teleport((96, 97))
    s.o2 = C.O2_MAX
    bot.mouse_to((20, 20))
    bot.frames(0.1)

    # floaters: o mesmo recurso no mesmo ponto soma; os outros sobem uma faixa cada
    app.floaters.items.clear()
    x, y = s.player.x + 60, s.player.y - 70
    iron, sil = C.ORE_COLORS["iron"][0], C.ORE_COLORS["silicon"][0]
    a = app.floaters.add("+15 FERRO", x, y, iron)
    assert app.floaters.add("+15 FERRO", x + 3, y, iron) is a and a.text == "+30 FERRO"
    app.floaters.add("+15 SILICIO", x + 8, y + 4, sil)
    app.floaters.add("+O₂", x - 6, y + 8, C.INDEX_COLOR["o2"])
    app.floaters.add("+AGUA", x + 2, y - 2, C.INDEX_COLOR["water"])
    from game.floaters import LANE_PX
    ys = sorted(f.y * app.floaters.scale - f.lane * LANE_PX for f in app.floaters.items)   # y na tela
    assert len(ys) == 4 and min(b - a for a, b in zip(ys, ys[1:])) >= LANE_PX, ys     # um em cima do outro, sem encostar
    bot.frames(0.15)
    shot_zoom(bot, "floaters_empilhados.png", (x, y - 50), w=200, h=135)
    app.floaters.items.clear()

    # barrinha da drill: no meio e cheia (verde)
    drill = s.drills[0]
    drill.stored = 12
    ax, ay = drill.anchor
    s.player.x, s.player.y = ax + 3 * C.TILE, ay + C.TILE
    bot.frames(0.1)
    shot_zoom(bot, "drill_barra.png", (ax, ay - 50), w=160, h=110)
    drill.stored = C.DRILL_CAPACITY
    bot.frames(0.1)
    shot_zoom(bot, "drill_barra_cheia.png", (ax, ay - 50), w=160, h=110)
    drill.stored = 0

    # sem energia: déficit forçado com máquinas nv.2 longe da tela; o raio pisca nas que consomem
    extra = [Machine("heater_t2", 5 + i, 5) for i in range(4)]
    s.machines += extra
    assert s.power.factor < 1
    station = s.stations[0]
    sx, sy = station.anchor
    s.player.x, s.player.y = sx + 2 * C.TILE, sy + 2 * C.TILE
    bot.frames(0.1)
    wait_blink_on(bot)
    bot.shot("sem_energia.png")
    for m in extra:
        s.machines.remove(m)
    assert s.power.factor == 1 or not any(m.kind == "heater_t2" and m.tx < 10 for m in s.machines)

    # fabricador: abas (D vai pra direita), rolagem (W/S e rodinha) e Shift+Enter fabrica 5
    bot.teleport((96, 97))
    give(s, iron=100, silicon=60, ice=30)
    bot.frames(0.1)
    bot.key(pygame.K_e)
    assert app.mode == "fabricator"
    app.fab.set_tab(0)
    bot.key(pygame.K_d)
    bot.key(pygame.K_d)
    assert app.fab.tab_id == "automation"
    bot.mouse_to((40, 40))
    bot.frames(0.1)
    bot.shot("fabricador_abas.png")
    tab = next(r for r, i in app.ui.fabricator_tabs if i == 0)
    bot.click((tab.centerx * 2, tab.centery * 2))            # clique na aba Terraformação
    assert app.fab.tab_id == "terraform"
    # no redesign B2 cabem as 6 receitas da aba (C.FAB_VISIBLE_ROWS): pra ver a rolagem e a barra, o smoke
    # encolhe a lista pra 4 linhas só neste trecho
    app.fab.visible = 4
    pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))
    bot.frames(DT)
    assert app.fab.first[0] == 1, "a rodinha devia rolar a lista"
    app.fab.select("o2")                                     # do topo, 5× S: 6ª receita (a lista rola)
    for _ in range(5):
        bot.key(pygame.K_s)
    assert app.fab.current == "heater_t2" and app.fab.first[0] == 2
    bot.frames(0.1)
    bot.shot("fabricador_scroll.png")
    app.fab.visible = C.FAB_VISIBLE_ROWS
    app.fab.first[0] = 0
    app.fab.select("o2")
    before = s.inventory.count("o2")
    shift_key(bot, pygame.K_RETURN)
    assert s.inventory.count("o2") == before + 5, s.inventory.counts()
    assert app.toast == "Gerador de O₂ x5", app.toast
    bot.frames(0.1)
    bot.shot("fabricar_lote.png")
    app.placing = None
    s.inventory.remove("o2", 5)

    zoom = app.zoom
    # decolagem: drone a 30%/100% da subida, lado a lado com um pousado (sombra colada -> afastada)
    landed = station.station.drones[:2]
    if len(landed) == 2:
        ramp = C.DRONE_SPEED * C.TILE * drones.LIFT_TIME
        saved = [(d.state, d.x, d.y) for d in landed]
        for d, k in zip(landed, (0.3, 1.2)):
            d.x, d.y = drones.pad_position(station, d.pad)
            d.state, d.y = drones.OUTBOUND, d.y + ramp * k
        bot.mouse_to((20, 20))
        app.draw()
        shot_zoom(bot, "drone_decolando.png", (sx, sy), w=120, h=110, k=4)
        for d, (st, dx, dy) in zip(landed, saved):
            d.state, d.x, d.y = st, dx, dy
    app.set_zoom(zoom, notify=False)
    bot.teleport((96, 97))
    bot.frames(0.1)


def ui_to_window(app, rect) -> tuple[int, int]:
    """Centro de um retângulo da UI (px da UI) em px da janela, no tamanho de interface atual."""
    from game import viewport
    (x, y, _, _), k, _ = viewport.ui_layout(app.window.get_size(), app.settings["ui_size"])
    return round(x + rect.centerx * k), round(y + rect.centery * k)


def check_field_craft(bot) -> None:
    """Tab > aba Fabricar (fabricar em campo) nos 3 tamanhos de interface (janela 1920×1080): o kit de campo
    (drill, luminária, luminária forte "???" sem projeto, baú), custo só do inventário (falta em vermelho),
    clique na aba pela posição na janela; na Pequena, clica em CRAFTAR da luminária e confere o modo de colocar.
    Prints: inventario_fabricar_<tamanho>.png."""
    from game.inventory import Stack
    s, app = bot.state, bot.app
    slots_before = [Stack(st.item, st.count) if st else None for st in s.inventory.slots]
    blueprints_before = set(s.blueprints)
    s.blueprints.discard("lamp_t2")
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.inventory.add("iron", 8)
    s.inventory.add("silicon", 3)
    for ui_size in ("grande", "media", "pequena"):
        app.set_ui_size(ui_size)
        bot.key(pygame.K_TAB)
        assert app.mode == "inventory" and app.inv_tab == TAB_INVENTORY
        bot.frames(DT)
        tab = next(r for r, i in app.ui.inv_tab_rects if i == TAB_CRAFT)
        bot.click(ui_to_window(app, tab))
        assert app.inv_tab == TAB_CRAFT, f"clique na aba Fabricar ({ui_size})"
        bot.frames(DT)
        assert [k for _, k in app.ui.fabricator_rows] == list(C.FIELD_RECIPES)
        # lista + detalhe: clique na linha da luminária escolhe; aí o FABRICAR (dela) aparece
        bot.click(ui_to_window(app, next(r for r, k in app.ui.fabricator_rows if k == "lamp")))
        assert app.field.current == "lamp"
        bot.frames(DT)
        assert "lamp" in [k for _, k in app.ui.fabricator_buttons] and s.recipe_status("lamp_t2", True) == "blueprint"
        bot.shot(f"inventario_fabricar_{ui_size}.png")
        if ui_size == "pequena":
            button = next(r for r, k in app.ui.fabricator_buttons if k == "lamp")
            bot.click(ui_to_window(app, button))
            bot.frames(DT)
            assert app.mode == "play" and app.placing == "lamp" and s.inventory.count("lamp") == 1
            app.placing = None
        else:
            bot.key(pygame.K_TAB)
        assert app.mode == "play"
    s.inventory.slots[:] = slots_before
    s.blueprints = blueprints_before


def check_b2_screens(bot) -> None:
    """Redesign B2 nas interfaces Grande e Pequena (janela 1920×1080), tudo pelo mouse na posição da janela:
    HUD, Tab com o detalhe do item, fabricador (×5/×1), baú (toggle de drone), estação, Opções (segmento do
    zoom) e o mapa (tooltip do marcador e FECHAR). Prints: b2_<tela>_<tamanho>.png."""
    from game.inventory import Stack
    s, app = bot.state, bot.app
    slots_before = [Stack(st.item, st.count) if st else None for st in s.inventory.slots]
    equip_before = dict(s.equipment.slots)
    zoom_before = app.zoom
    s.inventory.slots[:] = [None] * len(s.inventory)
    for item, n in [("iron", 42), ("silicon", 6), ("ice", 25), ("o2", 2), ("chest", 1), ("lamp", 3)]:
        s.inventory.add(item, n)
    s.inventory.slots[8], s.inventory.slots[9] = Stack("iron", 50), Stack("ice", 18)
    s.equipment.slots["o2_tank"], s.equipment.slots["scanner"] = "o2_tank", "scanner"
    for ui_size in ("grande", "pequena"):
        app.set_ui_size(ui_size)
        bot.teleport((96, 97))
        s.o2 = s.o2_max
        app.hotbar_selected = 3
        bot.mouse_to(ui_to_window(app, pygame.Rect(app.ui.w // 2 - 60, app.ui.h // 2 - 40, 1, 1)))
        bot.frames(0.2)
        bot.shot(f"b2_hud_{ui_size}.png")
        # Tab: mouse no gelo da mochila -> detalhe com "USADO EM"
        bot.key(pygame.K_TAB)
        bot.frames(DT)
        ice = next(r for r, inv, i in app.ui.slot_rects if inv is s.inventory and i == 9)
        bot.mouse_to(ui_to_window(app, ice))
        bot.frames(DT)
        assert app.ui.detail_item == "ice" and app.ui.detail_uses, app.ui.detail_uses
        bot.shot(f"b2_inventario_{ui_size}.png")
        bot.key(pygame.K_TAB)
        # fabricador: aquecedor (falta silício), ×5 e ×1 pelo clique
        bot.key(pygame.K_e)
        assert app.mode == "fabricator"
        app.fab.set_tab(0)
        app.fab.select("heater")
        bot.frames(DT)
        five = next(r for r, n in app.ui.fabricator_batch if n == C.CRAFT_BATCH)
        bot.click(ui_to_window(app, five))
        assert app.fab.batch == C.CRAFT_BATCH
        bot.mouse_to(ui_to_window(app, next(r for r, _ in app.ui.fabricator_tabs)))
        bot.frames(DT)
        bot.shot(f"b2_fabricador_{ui_size}.png")
        bot.click(ui_to_window(app, next(r for r, n in app.ui.fabricator_batch if n == 1)))
        assert app.fab.batch == 1
        bot.key(pygame.K_e)
        # baú: clique no Envia do gelo liga, de novo desliga
        chest = s.chests[0]
        s.player.x, s.player.y = chest.anchor[0], chest.anchor[1] + 10
        bot.frames(0.1)
        bot.key(pygame.K_e)
        assert app.mode == "chest"
        bot.frames(DT)
        was = "ice" in chest.sends
        toggle = next(r for r, v in app.ui.logistics_buttons if v == ("send", "ice"))
        bot.click(ui_to_window(app, toggle))
        assert ("ice" in chest.sends) != was, "clique no ícone do Envia devia ligar/desligar"
        bot.mouse_to(ui_to_window(app, next(r for r, inv, i in app.ui.slot_rects if inv is chest.storage)))
        bot.frames(DT)
        bot.shot(f"b2_bau_{ui_size}.png")
        bot.click(ui_to_window(app, next(r for r, v in app.ui.logistics_buttons if v == ("send", "ice"))))
        assert ("ice" in chest.sends) == was
        bot.key(pygame.K_ESCAPE)
        # estação de drones
        if s.stations:
            station = s.stations[0]
            app.open_station = station
            app.set_mode("station")
            bot.frames(DT)
            bot.shot(f"b2_estacao_{ui_size}.png")
            bot.key(pygame.K_ESCAPE)
        # Opções: clique no segmento 1,5× do zoom
        bot.key(pygame.K_ESCAPE)
        bot.key(pygame.K_s)
        bot.key(pygame.K_RETURN)
        assert app.pause_screen == "volumes"
        seg = next(r for r, (i, v) in app.ui.pause_segments if v == 1.5 and i == len(app.ui.VOLUME_ROWS) + 1)
        bot.click(ui_to_window(app, seg))
        assert app.zoom == 1.5
        bot.shot(f"b2_opcoes_{ui_size}.png")
        app.set_zoom(zoom_before, notify=False)
        bot.key(pygame.K_ESCAPE)
        bot.key(pygame.K_ESCAPE)
        assert app.mode == "play"
        # mapa: tooltip no marcador da base e FECHAR
        bot.key(pygame.K_m)
        assert app.mode == "map"
        bot.frames(DT)
        base = next(r for r, e in app.ui.map_markers if e.category == "base")
        bot.mouse_to(ui_to_window(app, base))
        bot.frames(DT)
        bot.shot(f"b2_mapa_{ui_size}.png")
        bot.click(ui_to_window(app, app.ui.map_close_rect))
        assert app.mode == "play"
    s.inventory.slots[:] = slots_before
    s.equipment.slots.update(equip_before)
    app.hotbar_selected = 0
    app.placing = None


def check_inventory_logs(bot) -> None:
    """Tab > aba LOGs nos 3 tamanhos de interface (janela 1920×1080): ordem da história, lidos clicáveis,
    não achados "???", um "NOVO". Clique na aba e numa linha pela posição na janela; fechar a leitura volta
    pra aba. Prints: inventario_abas_<tamanho>.png e inventario_logs_<tamanho>.png."""
    s, app = bot.state, bot.app
    read_before, seen_before = set(s.logs_read), set(s.logs_seen)
    # achados: dias 3, 41, 97 (já abertos pela aba) e 188 (NOVO); faltam 140, 212 e 230
    s.logs_read = {0, 5, 1, 3}
    s.logs_seen = {0, 5, 1}
    for ui_size in ("grande", "media", "pequena"):
        app.set_ui_size(ui_size)
        bot.key(pygame.K_TAB)
        assert app.mode == "inventory" and app.inv_tab == TAB_INVENTORY
        bot.frames(DT)
        bot.shot(f"inventario_abas_{ui_size}.png")
        tab = next(r for r, i in app.ui.inv_tab_rects if i == TAB_LOGS)
        bot.click(ui_to_window(app, tab))
        assert app.inv_tab == TAB_LOGS, f"clique na aba LOGs ({ui_size})"
        bot.frames(DT)
        assert [lg for _, lg in app.ui.log_rows] == [0, 5, 1, 3]      # só os lidos, na ordem da história
        assert len(app.ui.log_rows) == 4 and app.ui.log_visible == len(C.LOGS)
        bot.shot(f"inventario_logs_{ui_size}.png")
        if ui_size == "pequena":                   # clique no NOVO: abre a leitura, fechar volta pra aba
            row = next(r for r, lg in app.ui.log_rows if lg == 3)
            bot.click(ui_to_window(app, row))
            assert app.mode == "terminal" and app.terminal_index == 3 and 3 in s.logs_seen
            bot.frames(0.2)
            bot.shot("inventario_logs_leitura.png")
            bot.key(pygame.K_e)
            assert app.mode == "inventory" and app.inv_tab == TAB_LOGS and s.new_logs == 0
        bot.key(pygame.K_TAB)
        assert app.mode == "play"
    s.logs_read, s.logs_seen = read_before, seen_before


def check_ui_size(bot) -> None:
    """Opções > Interface (Grande/Média/Pequena) numa janela 1920×1080: o HUD encolhe, o mundo não muda,
    o mouse acerta botões/slots/abas em qualquer tamanho e também com tarja (4:3).
    Prints: hud_grande, hud_media, hud_pequena, hud_pequena_bau, titulo_pequena, hud_pequena_4x3."""
    from game import viewport
    s, app = bot.state, bot.app
    settings.SETTINGS_PATH.unlink(missing_ok=True)
    app.scale = 2
    app.window = app.open_window(False)
    assert app.window.get_size() == (1920, 1080), app.window.get_size()
    bot.teleport((96, 98))
    s.o2 = C.O2_MAX
    bot.frames(0.2)
    # pela pausa: Opções > INTERFACE, D diminui (Média -> Pequena), A aumenta
    assert app.settings["ui_size"] == "media"
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_s)
    bot.key(pygame.K_RETURN)
    assert app.pause_screen == "volumes"
    for _ in range(len(app.ui.VOLUME_ROWS) + 2):
        bot.key(pygame.K_s)
    bot.key(pygame.K_d)
    assert app.settings["ui_size"] == "pequena" and settings.load()["ui_size"] == "pequena"
    bot.frames(DT)
    bot.shot("pausa_opcoes_pequena.png")
    # mouse na Pequena: clica no "Voltar" (último item) pela posição na janela
    back = app.ui.pause_items[-1]
    bot.click(ui_to_window(app, back))
    assert app.pause_screen == "main"
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"

    # mundo igual nos 3 tamanhos: a câmera e o mouse do mundo não dependem da interface
    tile = (98, 96)
    hover = bot.tile_on_screen(tile)
    times = {}
    for ui_size in ("grande", "media", "pequena"):
        app.set_ui_size(ui_size)
        (x, y, _, _), k, size = viewport.ui_layout(app.window.get_size(), ui_size)
        bot.mouse_to((hover[0] * 2, hover[1] * 2))            # janela 2× o canvas
        assert app.mouse_tile() == tile, (ui_size, app.mouse_tile())
        app.floaters.add("+15 FERRO", s.player.x, s.player.y - 40, C.ORE_COLORS["iron"][0])
        app.show_toast(f"Interface {viewport.UI_SIZE_LABEL[ui_size].lower()}")
        start = len(bot.frame_times)
        bot.frames(0.6)
        times[ui_size] = 1000 * sum(bot.frame_times[start:]) / (len(bot.frame_times) - start)
        assert app.ui.surf.get_size() == size and app.ui.k == k
        # painel do Ti encosta na borda direita da janela (6 px da UI de margem)
        right = app.ui.ti_panel_x + TI_PANEL_W
        assert round(right * k) == 1920 - round(6 * k), (ui_size, right, k)
        bot.shot(f"hud_{ui_size}.png")
        # aviso de projeto com o ícone, no projeto de nome mais comprido (cabe entre O₂ e Ti nos 3 tamanhos)
        app.blueprint_notice, app.blueprint_notice_time = "scanner", C.BLUEPRINT_NOTICE_TIME
        bot.frames(0.1)
        rect, icon = app.ui.blueprint_notice_layout("scanner")
        assert rect.y == 6 and app.ui.BANNER_GAP[0] < rect.left and rect.right < app.ui.BANNER_GAP[1], rect
        bot.shot(f"projeto_{ui_size}.png")
        app.blueprint_notice_time = 0.0
        # floaters subindo pra dentro do painel do Ti/energia e do de O₂: somem antes de entrar embaixo
        ui = app.ui
        kk = app.zoom * ui.canvas_k
        cx, cy = app.cam
        for i, dy in enumerate((2, 8, 16, 26)):
            for ux, bottom in ((ui.ti_panel_x + 60, ui.energy_bottom), (60, 32)):
                app.floaters.add(f"+{i + 1} FERRO", cx + ux / kk, cy + (bottom + dy) / kk, C.ORE_COLORS["iron"][0])
        bot.frames(0.15)
        bot.shot(f"floaters_hud_{ui_size}.png")
        bot.frames(1.2)
    print("  interface 1920×1080, ms/frame: " + " · ".join(f"{n} {v:.1f}" for n, v in times.items()))

    # Pequena: fabricador (clique na aba) e baú (clique no slot transfere)
    app.set_ui_size("pequena")
    bot.teleport((96, 97))
    bot.frames(0.2)
    bot.key(pygame.K_e)
    assert app.mode == "fabricator"
    bot.frames(DT)
    tab_rect, tab_index = app.ui.fabricator_tabs[1]
    bot.click(ui_to_window(app, tab_rect))
    assert app.fab.tab == tab_index, "clique na aba do fabricador (Pequena)"
    bot.shot("hud_pequena_fabricador.png")
    bot.key(pygame.K_e)
    assert app.mode == "play"

    chest = s.chests[0]
    ax, ay = chest.anchor
    s.player.x, s.player.y = ax, ay + 10
    bot.frames(0.1)
    bot.key(pygame.K_e)
    assert app.mode == "chest"
    bot.frames(DT)
    s.inventory.add("iron", 5)
    slot = next(i for i, st in enumerate(s.inventory.slots) if st and st.item == "iron")
    rect = next(r for r, inv, i in app.ui.slot_rects if inv is s.inventory and i == slot)
    before = chest.storage.count("iron")
    bot.click(ui_to_window(app, rect))
    assert chest.storage.count("iron") > before, "clique no slot do inventário devia mandar pro baú (Pequena)"
    box_slot = next(i for i, st in enumerate(chest.storage.slots) if st and st.item == "iron")
    rect = next(r for r, inv, i in app.ui.slot_rects if inv is chest.storage and i == box_slot)
    bot.mouse_to(ui_to_window(app, rect))                  # tooltip do slot do baú
    bot.frames(0.1)
    bot.shot("hud_pequena_bau.png")
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"

    # título na Pequena (e o clique no menu dele)
    saved_state = app.state
    app.open_title()
    bot.frames(0.3)
    row = app.title.items[0]
    bot.mouse_to(ui_to_window(app, row))
    assert app.title.selected == 0
    bot.shot("titulo_pequena.png")
    app.start_game(saved_state)
    bot.frames(0.2)

    # tela cheia 4:3 (1024×768, tarja em cima e embaixo): clique da pausa no lugar certo
    bot.key(pygame.K_F11)
    assert app.window.get_size() != (1920, 1080)
    bot.key(pygame.K_ESCAPE)
    options = app.ui.pause_items[1]
    bot.mouse_to(ui_to_window(app, options))
    assert app.pause_selected == 1
    bot.shot("hud_pequena_4x3.png")
    bot.click(ui_to_window(app, options))
    assert app.pause_screen == "volumes"
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_ESCAPE)
    bot.key(pygame.K_F11)
    assert app.mode == "play"

    check_inventory_logs(bot)
    check_field_craft(bot)
    check_b2_screens(bot)

    # volta pro tamanho do resto do smoke
    app.set_ui_size(settings.DEFAULTS["ui_size"])
    app.scale = 1
    app.window = app.open_window(False)
    app.toast_time = 0.0
    bot.frames(0.1)
    settings.SETTINGS_PATH.unlink(missing_ok=True)


def check_save(bot) -> None:
    """Autosave com o aviso no HUD, "Salvar e sair" pela pausa, tela de título com save e Continuar."""
    s, app = bot.state, bot.app
    bot.teleport((96, 98))
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


def check_surface(bot) -> None:
    """v0.3 Marco 1 · superfície: base, deserto (morros, rochas), rocha reaparecendo, cratera, veio, mapa e perf."""
    s, app = bot.state, bot.app
    w = s.world
    assert s.layer == "surface" and (w.width, w.height) == (C.SURFACE_W, C.SURFACE_H)
    zoom_before = app.zoom
    # 1) base no zoom 0,75 (mostra a área limpa em volta da cápsula)
    app.set_zoom(0.75, notify=False)
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = C.O2_MAX
    bot.mouse_to((700, 420))
    bot.frames(0.3)
    bot.shot("superficie_base.png")

    # 2) um pedaço do deserto com morro e rochas pequenas (o lugar com mais coisa à vista)
    app.set_zoom(1.0, notify=False)
    def score(cx, cy):
        walls = sum(w.is_wall(x, y) for y in range(cy - 7, cy + 8) for x in range(cx - 13, cx + 14))
        rocks = sum(w.get(x, y) in C.SMALL_ROCKS for y in range(cy - 7, cy + 8) for x in range(cx - 13, cx + 14))
        return min(walls, 40) + 4 * rocks if walls and rocks else 0
    spots = [(x, y) for y in range(12, w.height - 12, 3) for x in range(16, w.width - 16, 3)
             if w.is_floor(x, y) and w.dist_from_center(x, y) > 14 and not w.is_solid(x, y - 1)]
    spot = max(spots, key=lambda t: score(*t))
    bot.teleport(spot)
    s.o2 = C.O2_MAX
    near_rock = min(((x, y) for y in range(w.height) for x in range(w.width) if w.get(x, y) in C.SMALL_ROCKS),
                    key=lambda t: math.hypot(t[0] - spot[0], t[1] - spot[1]))
    bot.mouse_to(bot.tile_on_screen(near_rock))
    bot.frames(0.3)
    print(f"  deserto em {spot}: dica = {app.hint()!r}")
    bot.shot("superficie_deserto.png")

    # rocha pequena: quebra com a broca e dá 2–4
    rock = min(((x, y) for y in range(w.height) for x in range(w.width) if w.get(x, y) in C.SMALL_ROCKS),
               key=lambda t: math.hypot(t[0] - spot[0], t[1] - spot[1]))
    res = C.SMALL_ROCKS[w.get(*rock)]
    carve(s, [(rock[0], rock[1] + 1)])
    bot.teleport((rock[0], rock[1] + 1))
    s.o2 = C.O2_MAX
    before = s.inventory.count(res)
    pos = bot.tile_on_screen(rock)
    bot.mouse_to(pos)
    bot.frames(0.05)
    assert "Rocha com" in (app.hint() or ""), app.hint()
    bot.mouse_down(pos)
    bot.frames(0.4)
    shot_zoom(bot, "superficie_rocha.png", ((rock[0] + 0.5) * C.TILE, (rock[1] + 0.5) * C.TILE), w=200, h=120)
    bot.frames(0.5)
    bot.mouse_up(pos)
    bot.frames(0.1)
    assert w.get(*rock) == C.SAND and 2 <= s.inventory.count(res) - before <= 4

    # 3) cratera (rampa de descida no Marco 2): obstáculo, com a dica do E
    tx, ty = w.crater
    bot.teleport((tx + 1, ty + 4))
    s.o2 = C.O2_MAX
    bot.mouse_to(bot.tile_on_screen((tx + 1, ty + 1)))
    bot.frames(0.2)
    assert app.hint() == "[E] Descer pela rampa", app.hint()
    y0 = s.player.y
    bot.key(pygame.K_w, hold=0.8)                  # anda pra cima: a cratera segura
    assert s.player.y >= (ty + 3) * C.TILE + C.PLAYER_BOX_H - 0.01 and s.player.y < y0
    bot.shot("superficie_cratera.png")

    # 4) veio longe da base
    vein = min(w.veins, key=lambda v: w.dist_from_center(v.tx, v.ty))
    bot.teleport((vein.tx + 1, vein.ty + 3))
    s.o2 = C.O2_MAX
    bot.mouse_to(bot.tile_on_screen((vein.tx, vein.ty)))
    bot.frames(0.2)
    print(f"  veio mais perto: {vein.resource} a {w.dist_from_center(vein.tx, vein.ty):.0f} tiles · {len(w.veins)} veios")
    bot.shot("superficie_veio.png")

    # 5) mapa inteiro reduzido 8× (chão, paredes e objetos, sem luz nem clima)
    r = app.renderer
    chunk = 1024
    s.player.x, s.player.y = C.SPAWN_POS

    def full_map(name, note):
        full = pygame.Surface((w.width * C.TILE // 8, w.height * C.TILE // 8))
        piece = pygame.Surface((chunk, chunk))
        for cy in range(0, w.height * C.TILE, chunk):
            for cx in range(0, w.width * C.TILE, chunk):
                piece.fill((0, 0, 0))
                r.view_w, r.view_h = chunk, chunk
                r.stage_map.update(s.ti, [])
                r.draw_floors(piece, s, (cx, cy), "dead", 0.0)
                r.draw_veins(piece, s, (cx, cy))
                r.draw_zone(piece, (cx, cy), 0.0)
                r.draw_walls_and_objects(piece, s, (cx, cy), "dead", 0.0)
                full.blit(pygame.transform.smoothscale(piece, (chunk // 8, chunk // 8)), (cx // 8, cy // 8))
        for v in w.veins:                              # anéis nos veios e na cratera, pra achar no mapa
            pygame.draw.circle(full, C.ORE_COLORS[v.resource][0], ((v.tx + 1) * 4, (v.ty + 1) * 4), 9, 2)
        pygame.draw.circle(full, (255, 255, 255), ((tx + 1.5) * 4, (ty + 1.5) * 4), 10, 1)
        pygame.image.save(full, str(OUT / name))
        print(f"  screenshot: reports/dev/{name}  ({note})")

    full_map("superficie_mapa.png", "mapa 192×192 reduzido 8×; anéis = veios, branco = cratera")

    # 5b) rochas reaparecendo (regra real): enche até o teto com o player na base e olha a densidade no teto
    start_rocks = rock_respawn.count(w)
    saved_tiles = [row[:] for row in w.tiles]
    s.pop_events()
    born = s._update_rocks(C.ROCK_RESPAWN * (C.ROCK_MAX - start_rocks) + 1)
    assert rock_respawn.count(w) == C.ROCK_MAX and len(born) == C.ROCK_MAX - start_rocks
    assert all(rock_respawn.hidden_from(C.SPAWN_POS, *t) and w.dist_from_center(*t) >= C.ROCK_BASE_DIST for t in born)
    print(f"  rochas: {start_rocks} no começo, teto {C.ROCK_MAX} (+{len(born)} reaparecidas)")
    full_map("superficie_mapa_teto.png", f"o mesmo mapa com as rochas no teto ({C.ROCK_MAX})")
    app.set_zoom(0.75, notify=False)
    bot.teleport(spot)
    s.o2 = C.O2_MAX
    bot.frames(0.3)                                # os eventos rock_spawn repintam o minimapa sem quebrar
    bot.shot("superficie_rochas_teto.png")
    for y, row in enumerate(saved_tiles):          # volta o deserto como estava
        w.tiles[y][:] = row
    for t in born:
        r.minimap.repaint(s, t, "surface")

    # 6) perf no deserto, zoom 0,75 (o mais afastado), andando
    app.set_zoom(0.75, notify=False)
    bot.teleport(spot)
    start = len(bot.frame_times)
    for key in (pygame.K_d, pygame.K_s, pygame.K_a, pygame.K_w):
        s.o2 = C.O2_MAX
        bot.key(key, hold=0.75)
    ft = bot.frame_times[start:]
    avg = sum(ft) / len(ft)
    print(f"  perf deserto 192×192, zoom 0,75×: média {avg * 1000:.1f} ms · pior {max(ft) * 1000:.1f} ms "
          f"({len(ft)} frames, orçamento 16,7 ms)")
    assert avg < 1 / 60, "deserto no zoom 0,75 passou do orçamento de 16,7 ms"
    app.set_zoom(zoom_before, notify=False)
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = C.O2_MAX
    bot.frames(0.2)


def region_spot(geo, world, want, other=None, half=(14, 8)):
    """Tile de chão (pros pés do player) no meio da região `want` (ou na divisa com `other`): a janela de
    ~1 tela em volta dele é o mais `want` possível (na divisa: o mais meio a meio), desempate pela base."""
    import numpy as np
    hx, hy = half

    def frac(reg):
        m = np.pad((geo.region == reg).astype(np.int32), ((hy + 1, hy), (hx + 1, hx)))
        cs = m.cumsum(0).cumsum(1)
        win = cs[2 * hy + 1:, 2 * hx + 1:] - cs[:-2 * hy - 1, 2 * hx + 1:] - cs[2 * hy + 1:, :-2 * hx - 1] \
            + cs[:-2 * hy - 1, :-2 * hx - 1]
        return win / ((2 * hy + 1) * (2 * hx + 1))
    score = frac(want) if other is None else np.minimum(frac(want), frac(other))
    best, best_key = None, None
    for ty in range(hy + 2, world.height - hy - 2):
        for tx in range(hx + 2, world.width - hx - 2):
            if not world.is_floor(tx, ty) or world.is_solid(tx, ty - 1):
                continue
            key = (round(float(score[ty, tx]), 2), -world.dist_from_center(tx, ty))
            if best_key is None or key > best_key:
                best, best_key = (tx, ty), key
    return best


def ground_settle(bot, seconds: float = 0.2) -> None:
    """Deixa o chão assado pronto antes do print (assa tudo que está na tela na hora, sem o orçamento)."""
    g = bot.app.renderer.ground
    g.sync = True
    bot.frames(DT)
    g.sync = False
    bot.frames(seconds)


def walk_perf(bot, spot, fast: bool = False) -> list[float]:
    s = bot.state
    bot.teleport(spot)
    bot.frames(0.1)                                  # fora da medida: o quadro frio do teleporte
    s.fast = fast
    start = len(bot.frame_times)
    for key in (pygame.K_d, pygame.K_s, pygame.K_a, pygame.K_w):
        s.o2 = C.O2_MAX
        bot.key(key, hold=0.75)
    s.fast = False
    return bot.frame_times[start:]


def check_ground(bot) -> None:
    """v0.4 Marco 2 · trilha B · chão assado (game/ground.py, com o layer.geo): as 4 regiões no Árido, as
    divisas, o leito seco com as marcas d'água, os 4 estágios, a mancha da transição, o mapa inteiro e o
    desempenho contra o chão por tile de antes (o mesmo passeio sem o geo)."""
    s, app = bot.state, bot.app
    r = app.renderer
    w = s.world
    before = dict(s.indices)
    stage_before, storm_before = s.stage, s.storm
    zoom_before = app.zoom
    app.set_zoom(0.75, notify=False)
    # 0) desempenho de hoje (sem geo), pra comparar: o mesmo passeio
    spot0 = (C.BASE_TILE[0] + 12, C.BASE_TILE[1] + 6)
    carve(s, [spot0])
    geo = s.active.geo
    w.geo = None                                     # o chão por tile de antes, só pra comparar (layer.geo = world.geo)
    base_ft = walk_perf(bot, spot0)
    w.geo = geo
    assert geo is not None and r.surface_geo(s) is geo, "sem geo ou sem a arte das regiões (assets/sprites/regions/)"
    s.stage, s.storm = C.ARID_STAGE, 0.0              # Árido: sem poeira na frente do chão
    s.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    app.set_zoom(1.0, notify=False)
    names = {"planalto": 0, "salar": 1, "basalto": 2, "gelada": 3}
    for name, reg in names.items():
        spot = region_spot(geo, w, reg)
        bot.teleport(spot)
        s.o2 = C.O2_MAX
        bot.mouse_to((900, 500))
        ground_settle(bot)
        print(f"  chão {name}: {spot}")
        bot.shot(f"chao_{name}.png")
    for name, other in (("salar", 1), ("basalto", 2), ("gelada", 3)):
        spot = region_spot(geo, w, 0, other)
        bot.teleport(spot)
        s.o2 = C.O2_MAX
        ground_settle(bot)
        print(f"  divisa planalto -> {name}: {spot}")
        bot.shot(f"chao_divisa_{name}.png")
    # leito seco com as marcas d'água (a depressão pequena mais perto da base)
    import numpy as np
    ys, xs = np.nonzero((geo.basin == 0) & (geo.region == 0))
    k = int(np.argmin(np.hypot(xs - C.BASE_TILE[0], ys - C.BASE_TILE[1])))
    bed = (int(xs[k]), int(ys[k]))
    carve(s, [bed, (bed[0], bed[1] - 1)])
    bot.teleport(bed)
    s.o2 = C.O2_MAX
    ground_settle(bot)
    bot.shot("chao_leito.png")
    # decoração solta: tem que ter algo na tela do basalto e do salar
    for reg in (1, 2):
        spot = region_spot(geo, w, reg)
        n = sum(1 for ty in range(spot[1] - 8, spot[1] + 9) for tx, _, _ in r.ground.decor_row(ty)
                if abs(tx - spot[0]) <= 15)
        assert n > 0, f"sem decoração solta perto de {spot}"
    # 4 estágios na base (cor da rampa; a poeira e o clima por cima, como no jogo)
    for stage in (1, 2, 3, 4):
        s.stage = stage
        s.storm = 1.0 if stage == C.STORM_STAGE else 0.0
        s.indices.update(o2=float(C.STAGES[stage - 1].ti), heat=0.0, water=0.0)
        bot.teleport((C.BASE_TILE[0] + 3, C.BASE_TILE[1] + 4))
        s.o2 = C.O2_MAX
        ground_settle(bot)
        bot.shot(f"chao_estagio{stage}.png")
    # a mancha da transição Árido -> Névoa passando pela base (blocos misturados)
    s.stage, s.storm = C.ARID_STAGE, 0.0
    app.set_zoom(0.75, notify=False)
    s.indices.update(o2=ti_in_window(C.ARID_STAGE, 0.6), heat=0.0, water=0.0)
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 2))
    ground_settle(bot)
    assert any(c[0][0] == "m" for c in r.ground._color.values()), "nenhum bloco misturado na transição"
    bot.shot("chao_transicao.png")
    s.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    # 5) mapa inteiro reduzido 8× (só o chão), pra comparar com o mapa_regioes.png da Designer
    full = pygame.Surface((w.width * C.TILE // 8, w.height * C.TILE // 8), 0, 32)
    piece = pygame.Surface((1024, 1024), 0, 32)
    r.ground.sync = True
    for cy in range(0, w.height * C.TILE, 1024):
        for cx in range(0, w.width * C.TILE, 1024):
            r.view_w, r.view_h = 1024, 1024
            r.stage_map.update(s.ti, [])
            r.draw_floors(piece, s, (cx, cy), "dead", 0.0)
            full.blit(pygame.transform.smoothscale(piece, (128, 128)), (cx // 8, cy // 8))
    r.ground.sync = False
    pygame.image.save(full, str(OUT / "chao_mapa.png"))
    print("  screenshot: reports/dev/chao_mapa.png  (chão 192×192 reduzido 8×)")
    # 6) desempenho: assar 1 bloco, o passeio de antes (zoom 0,75) e o pior quadro andando rápido (F3)
    app.set_zoom(0.75, notify=False)
    r.ground.reset()                                 # cache fria: mede o assado de verdade
    bot.teleport(spot0)
    cold = len(bot.frame_times)
    bot.frames(DT)                                   # 1º quadro frio: assa a tela inteira na hora
    cold_ms = 1000 * bot.frame_times[cold]
    geo_ft = walk_perf(bot, spot0)
    fast_ft = walk_perf(bot, region_spot(geo, w, 2), fast=True)
    bake = r.ground.bake_ms
    avg = lambda ft: 1000 * sum(ft) / len(ft)   # noqa: E731
    print(f"  assar 1 bloco 512×512: média {sum(bake) / len(bake):.0f} ms em faixas de {C.GROUND_BAKE_ROWS} linhas "
          f"(orçamento {C.GROUND_BAKE_MS:g} ms/quadro) · {len(bake)} blocos")
    print(f"  perf chão, zoom 0,75×: hoje {avg(base_ft):.1f} ms · assado {avg(geo_ft):.1f} ms "
          f"({avg(geo_ft) - avg(base_ft):+.1f} ms) · pior {max(geo_ft) * 1000:.1f} ms")
    print(f"  1º quadro com a cache fria (assa a tela inteira): {cold_ms:.0f} ms")
    print(f"  perf andando rápido (F3) no basalto: média {avg(fast_ft):.1f} ms · pior {max(fast_ft) * 1000:.1f} ms")
    assert avg(geo_ft) < 1000 / 60, "chão assado passou do orçamento de 16,7 ms"
    # volta tudo como estava
    s.indices.update(before)
    s.stage, s.storm = stage_before, storm_before
    app.set_zoom(zoom_before, notify=False)
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = C.O2_MAX
    bot.frames(0.2)


def set_weather(state, gust: float, angle: float = 20.0) -> None:
    """Clima de verdade (game/weather.py) preso numa direção e numa rajada: gust 1 = no pico e sem fim,
    gust 0 = calmo (o smoke já desliga as rajadas sorteadas)."""
    w = state.weather
    w.dominant = w.angle = w.target = angle
    w.retarget_in = 1e9
    w._update_wind_vector()
    w.gust, w.gust_left = (1.0, 1e9) if gust > 0 else (0.0, 0.0)
    w._recompute(storm=1.0)


def check_storm(bot) -> None:
    """Visual da tempestade (v0.4 Marco 1, trilha C): nuvens de poeira, visão, faixas e chiado do scanner.
    Liga a tempestade direto no estado (state.storm = 1.0) e força a rajada no state.weather."""
    from game import dust
    from game.systems import Machine
    print("1b) tempestade (visual)")
    app, s = bot.app, bot.state
    old_storm = s.storm
    old_machines = list(s.machines)
    zoom_before = app.zoom
    spot = (C.BASE_TILE[0] + 12, C.BASE_TILE[1] + 4)

    def walk_perf(zoom: float) -> float:
        app.set_zoom(zoom, notify=False)
        bot.teleport(spot)
        bot.frames(0.1)
        start = len(bot.frame_times)
        for key in (pygame.K_d, pygame.K_s, pygame.K_a, pygame.K_w) * 2:
            s.o2 = s.o2_max
            bot.key(key, hold=0.4)
        ft = bot.frame_times[start:]
        return sum(ft) / len(ft)

    # perf: o mesmo passeio sem tempestade e na tempestade com rajada cheia (o pior caso)
    # (alternado, 2 rodadas de cada; vale a melhor média de cada lado: o relógio da máquina oscila)
    base, storm = {}, {}
    for _ in range(2):
        for z in (1.0, 0.75):
            s.storm = 0.0
            set_weather(s, 0.0)
            base[z] = min(base.get(z, 1.0), walk_perf(z))
            s.storm = 1.0
            set_weather(s, 1.0, 35.0)
            storm[z] = min(storm.get(z, 1.0), walk_perf(z))
    for z in (1.0, 0.75):
        print(f"  perf tempestade+rajada, zoom {z:g}×: média {storm[z] * 1000:.1f} ms "
              f"(sem tempestade {base[z] * 1000:.1f} ms, +{(storm[z] - base[z]) * 1000:.1f} ms; orçamento 16,7 ms)")
        assert storm[z] < 1 / 60, f"tempestade no zoom {z:g} passou do orçamento de 16,7 ms"
    print(f"  partículas na rajada cheia: {app.renderer.storm_particles.count(1.0, 1.0)} (teto {dust.MAX_PARTICLES})")

    app.set_zoom(1.0, notify=False)
    # tempestade normal: visão de 7 tiles, longe da base
    set_weather(s, 0.0)
    bot.teleport(spot)
    s.o2 = s.o2_max
    bot.frames(0.6)
    assert app.renderer.storm_dust._last is not None
    bot.shot("tempestade_visual.png")
    # andando: dois quadros seguidos (as nuvens, as faixas e os grãos andam entre eles)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, mod=0, unicode="", scancode=0))
    bot.frames(0.3)
    bot.shot("tempestade_andando_1.png")
    bot.frames(DT)
    bot.shot("tempestade_andando_2.png")
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_d, mod=0, unicode="", scancode=0))
    bot.frames(DT)
    # rajada: visão de 4 tiles, mais poeira e faixas, minimapa chiando
    set_weather(s, 1.0, 35.0)
    bot.teleport(spot)
    bot.frames(0.6)
    bot.shot("tempestade_visual_rajada.png")
    had_scanner = s.has_scanner
    if not had_scanner:
        s.equipment.equip("scanner")              # só pro print (volta no fim)
        bot.frames(0.2)
    assert dust.static_amount(s) == 1.0
    bot.shot("tempestade_minimapa.png")
    bot.key(pygame.K_m)
    assert app.mode == "map"
    bot.frames(0.2)
    bot.shot("tempestade_mapa.png")
    bot.key(pygame.K_m)
    assert app.mode == "play"
    if not had_scanner:
        s.equipment.unequip("scanner")
    # perto da base: a cápsula e as máquinas abrem a vista (o player fica a ~6 tiles)
    bx, by = C.BASE_TILE
    s.machines = old_machines + [Machine("o2", bx - 4, by + 3), Machine("heater", bx + 3, by + 3),
                                 Machine("solar", bx - 1, by + 6), Machine("lamp", bx + 7, by - 1)]
    set_weather(s, 0.0)
    bot.teleport((bx + 6, by + 4))
    bot.frames(0.4)
    bot.shot("tempestade_base.png")
    # caverna: a tempestade não entra
    s.machines = old_machines
    s.enter_layer("cave")
    assert dust.storm_of(s) == 0.0 and dust.static_amount(s) == 0.0
    s.enter_layer("surface")

    s.storm = old_storm
    set_weather(s, 0.0)
    app.set_zoom(zoom_before, notify=False)
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = s.o2_max
    bot.frames(0.2)


def cave_spot(world, lo=14, hi=30):
    """Chão da caverna com mais minério em volta (raio de ~8 tiles), entre `lo` e `hi` tiles da rampa."""
    def score(x, y):
        return sum(world.get(xx, yy) in C.ORE_TILES for yy in range(y - 6, y + 7) for xx in range(x - 10, x + 11))
    spots = [(x, y) for y in range(8, world.height - 8, 2) for x in range(8, world.width - 8, 2)
             if world.is_floor(x, y) and world.is_floor(x, y - 1) and world.is_floor(x + 1, y)
             and lo <= world.dist_from_center(x, y) <= hi]
    return max(spots, key=lambda t: score(*t))


def open_floor_near(world, spot, n, min_gap=3, radius=12):
    """`n` tiles de chão livres (sem veio) em volta de `spot`, com `min_gap` tiles entre eles."""
    out = []
    cx, cy = spot
    cand = sorted(((x, y) for y in range(cy - radius, cy + radius + 1) for x in range(cx - radius, cx + radius + 1)
                   if world.is_floor(x, y) and not world.vein_at(x, y) and (x, y) != spot),
                  key=lambda t: math.hypot(t[0] - cx, t[1] - cy))
    for t in cand:
        if all(max(abs(t[0] - o[0]), abs(t[1] - o[1])) >= min_gap for o in out):
            out.append(t)
        if len(out) == n:
            break
    return out


def check_cave(bot) -> None:
    """v0.3 Marco 2 · caverna: E na cratera, fade, chegada, escuro com luminárias, mineração, mapa, perf, subir."""
    from game import layers
    from game.systems import Machine
    s, app = bot.state, bot.app
    assert s.layer == "surface"
    zoom_before = app.zoom
    app.set_zoom(1.0, notify=False)
    w = s.world
    tx, ty = w.crater
    # 0) a luminária no fabricador, aba "Luz" (1 Fe + 1 Si, liberada desde o começo)
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    bot.key(pygame.K_e)
    assert app.mode == "fabricator"
    app.fab.set_tab([t for t, _ in C.FAB_TABS].index("light"))
    bot.frames(0.1)
    assert app.fab.current == "lamp"
    bot.shot("fabricador_luz.png")
    app.fab.set_tab(0)
    bot.key(pygame.K_ESCAPE)
    # 1) mouse na cratera, no alcance: a dica e o contorno
    bot.teleport((tx + 1, ty + 3))
    s.o2 = C.O2_MAX
    bot.mouse_to(bot.tile_on_screen((tx + 1, ty + 1)))
    bot.frames(0.2)
    assert app.hint() == "[E] Descer pela rampa", app.hint()
    assert app.highlight_target() == ("ramp", (tx, ty))
    bot.shot("caverna_rampa_superficie.png")
    # 2) E: fade com "Descendo..." e troca de camada no preto
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, mod=0, unicode="", scancode=0))
    bot.frames(0.42)
    assert s.ramp is not None and s.layer == "surface"
    bot.shot("caverna_transicao.png")
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_e, mod=0, unicode="", scancode=0))
    bot.frames(C.RAMP_DURATION)
    cave = s.world
    assert s.layer == "cave" and s.ramp is None and (s.player.x, s.player.y) == layers.ramp_arrival(cave)
    bot.mouse_to((700, 300))
    bot.frames(0.3)
    bot.shot("caverna_chegada.png")
    print(f"  caverna: chegou em {s.player.tile} · {len(cave.veins)} veios · ambiente {app.audio.ambient_key!r}")

    # 3) no escuro: lanterna + 6 luminárias + minério brilhando
    spot = cave_spot(cave)
    bot.teleport(spot)
    s.o2 = C.O2_MAX
    lamps = open_floor_near(cave, spot, 6, min_gap=4, radius=11)
    first = lamps[0]
    give(s, lamp=6)
    bot.key(hotbar_key(bot, "lamp"))
    assert app.placing == "lamp"
    s.player.x, s.player.y = (first[0] + 0.5) * C.TILE, (first[1] + 3) * C.TILE - 2    # perto (alcance 4)
    if not cave.is_floor(*s.player.tile):
        s.player.x, s.player.y = (spot[0] + 0.5) * C.TILE, (spot[1] + 1) * C.TILE - 2
    bot.click(bot.tile_on_screen(first))
    assert any(m.is_lamp for m in s.machines), "a luminária devia ter sido colocada pelo clique"
    for t in lamps[1:]:
        s.machines.append(Machine("lamp", *t))
    bot.key(pygame.K_ESCAPE)
    bot.teleport(spot)
    s.player.direction = "right"
    bot.mouse_to((760, 260))
    bot.frames(0.4)
    bot.shot("caverna_escura.png")

    # 4) mineração no escuro (a lanterna ilumina o tile; as rachaduras ficam por cima do escuro)
    ore = min(((x, y) for y in range(2, 126) for x in range(2, 126)
               if cave.get(x, y) in C.ORE_TILES and cave.is_floor(x, y + 1) and cave.is_floor(x, y + 2)),
              key=lambda t: math.hypot(t[0] - spot[0], t[1] - spot[1]))
    bot.teleport((ore[0], ore[1] + 1))
    s.o2 = C.O2_MAX
    s.player.direction = "up"
    pos = bot.tile_on_screen(ore)
    bot.mouse_to(pos)
    bot.mouse_down(pos)
    bot.frames(0.5)
    bot.shot("caverna_mineracao.png")
    bot.frames(0.9)
    bot.mouse_up(pos)
    bot.frames(0.1)
    assert cave.is_floor(*ore), "o minério da caverna devia ter quebrado"

    # 5) mapa da caverna inteiro reduzido 4× (sem escuridão)
    r = app.renderer
    chunk = 1024
    full = pygame.Surface((cave.width * C.TILE // 4, cave.height * C.TILE // 4))
    piece = pygame.Surface((chunk, chunk))
    r.stage_map = r.cave_map
    for cy in range(0, cave.height * C.TILE, chunk):
        for cx in range(0, cave.width * C.TILE, chunk):
            piece.fill((0, 0, 0))
            r.view_w, r.view_h = chunk, chunk
            r.draw_floors(piece, s, (cx, cy), "mist", 0.0)
            r.draw_veins(piece, s, (cx, cy))
            r.draw_walls_and_objects(piece, s, (cx, cy), "mist", 0.0)
            full.blit(pygame.transform.smoothscale(piece, (chunk // 4, chunk // 4)), (cx // 4, cy // 4))
    for v in cave.veins:
        pygame.draw.circle(full, C.ORE_COLORS[v.resource][0], ((v.tx + 1) * 8, (v.ty + 1) * 8), 12, 2)
    for t in cave.terminals:
        pygame.draw.circle(full, C.C_TERMINAL, ((t[0] + 0.5) * 8, (t[1] + 0.5) * 8), 14, 2)
    rx, ry = cave.crater
    pygame.draw.circle(full, (255, 255, 255), ((rx + 1.5) * 8, (ry + 1.5) * 8), 20, 2)
    pygame.image.save(full, str(OUT / "caverna_mapa.png"))
    ores = sum(cave.get(x, y) in C.ORE_TILES for y in range(128) for x in range(128))
    walls = sum(cave.is_wall(x, y) for y in range(128) for x in range(128))
    print(f"  screenshot: reports/dev/caverna_mapa.png  (128×128 reduzido 4×; anéis: veios, verde = terminais, "
          f"branco = rampa) · minério {ores} de {walls} paredes ({100 * ores / walls:.0f}%)")

    # 6) perf: caverna escura com 30 luminárias na tela, zoom 0,75, andando
    app.set_zoom(0.75, notify=False)
    perf_spot = cave_spot(cave, 10, 40)
    extra = open_floor_near(cave, perf_spot, 30, min_gap=2, radius=18)
    s.machines.extend(Machine("lamp", *t) for t in extra)
    bot.teleport(perf_spot)
    start = len(bot.frame_times)
    for key in (pygame.K_d, pygame.K_s, pygame.K_a, pygame.K_w):
        s.o2 = C.O2_MAX
        bot.key(key, hold=0.75)
    ft = bot.frame_times[start:]
    avg = sum(ft) / len(ft)
    lit = sum(1 for m in s.machines if m.is_lamp)
    print(f"  perf caverna escura, {lit} luminárias, zoom 0,75×: média {avg * 1000:.1f} ms · pior {max(ft) * 1000:.1f} ms "
          f"({len(ft)} frames, orçamento 16,7 ms)")
    assert avg < 1 / 60, "caverna escura no zoom 0,75 passou do orçamento de 16,7 ms"
    for m in [m for m in s.machines if m.is_lamp][6:]:
        s.machines.remove(m)
    app.set_zoom(zoom_before, notify=False)

    # 7) sobe pela rampa: volta pra superfície ao lado da cratera
    s.player.x, s.player.y = layers.ramp_arrival(cave)
    s.o2 = C.O2_MAX
    bot.key(pygame.K_e)
    assert s.ramp is not None and s.ramp.to == "surface"
    bot.frames(C.RAMP_DURATION + 0.1)
    assert s.layer == "surface" and (s.player.x, s.player.y) == layers.ramp_arrival(s.world)
    s.inventory.remove("lamp", s.inventory.count("lamp"))     # o resto do smoke conta com o inventário de antes
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = C.O2_MAX
    bot.frames(0.2)


def check_map_panorama(bot) -> None:
    """Mapa aberto panorâmico (B2): superfície 1× e 2×, tooltip de destroço com distância e direção, filtro
    "Máquinas" desligado pelo chip, rodinha ancorada no mouse, arrasto e, numa janela 1920×1080, a interface
    Pequena. Tudo pelo mouse/teclado na posição da janela. Prints: mapa_pan_*.png."""
    from game import map_view as MV
    s, app = bot.state, bot.app
    view = app.map_view
    zoom_before, hidden_before = view.zoom, set(view.hidden)
    view.zoom, view.hidden = 2, set()
    bot.key(pygame.K_m)
    assert app.mode == "map" and view.layer == "surface"
    bot.frames(0.1)
    bot.mouse_to((4, 4))
    bot.shot("mapa_pan_superficie_2x.png")
    # tooltip num destroço (o mais perto que está na área), com cantoneiras e "N tiles a <direção>"
    wreck = next((r, e) for r, e in app.ui.map_markers if e.category in ("wreck", "wreck_empty"))
    bot.mouse_to(ui_to_window(app, wreck[0]))
    bot.frames(0.05)
    hover = app.ui.map_hover
    assert hover is not None and hover.category in ("wreck", "wreck_empty") and " tiles " in hover.sub, hover
    print(f"  tooltip: {hover.title} · {hover.sub}")
    bot.shot("mapa_pan_tooltip.png")
    # chip "Máquinas" desligado: o marcador some e o chip fica apagado (e vai pro settings.json)
    chip = next(r for r, c in app.ui.map_chips if c == "machine")
    bot.click(ui_to_window(app, chip))
    assert "machine" in view.hidden and app.mode == "map"
    assert not any(e.category == "machine" for _, e in app.ui.map_markers)
    assert settings.load()["map_hidden"] == ["machine"]
    bot.mouse_to(ui_to_window(app, wreck[0]))
    bot.shot("mapa_pan_filtro.png")
    bot.click(ui_to_window(app, chip))
    assert "machine" not in view.hidden
    # régua de máquinas coladas na base: no 2× vira um marcador só com o número; tooltip com contagem e tipos
    group = next((r, e) for r, e in app.ui.map_markers if e.category == "machine" and e.count > 1)
    bot.mouse_to(ui_to_window(app, group[0]))
    bot.frames(0.05)
    hover = app.ui.map_hover
    assert hover is not None and hover.title.startswith("Máquinas · ") and hover.detail, hover
    print(f"  grupo: {hover.title} · {hover.detail} · {hover.sub}")
    bot.shot("mapa_pan_grupo.png")
    view.set_zoom(4)
    view.center_on(group[1].x, group[1].y)
    bot.frames(0.05)
    assert sum(1 for _, e in app.ui.map_markers if e.category == "machine") >= 6   # 2 tiles no 4×: separa
    bot.mouse_to((4, 4))
    bot.shot("mapa_pan_grupo_4x.png")
    view.set_zoom(2)
    # rodinha pra trás (1×): a superfície inteira cabe na altura
    pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))
    bot.frames(0.05)
    assert view.zoom == 1 and settings.load()["map_zoom"] == 1
    bot.mouse_to((4, 4))
    bot.shot("mapa_pan_superficie_1x.png")
    # arrasto no 3×: o mapa anda 1:1 com o mouse
    view.set_zoom(3)
    bot.frames(0.05)
    area = app.ui.map_area
    start = (view.cx, view.cy)
    p0 = ui_to_window(app, area)
    bot.mouse_to(p0)
    bot.mouse_down(p0)
    bot.frames(0.05)
    bot.mouse_to((p0[0] - 60, p0[1] - 30))
    bot.mouse_up((p0[0] - 60, p0[1] - 30))
    bot.frames(0.05)
    assert view.cx > start[0] and app.mode == "map" and not app.mouse_held
    bot.key(pygame.K_c)
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    # interface Pequena numa janela 1920×1080
    ui_before = app.settings["ui_size"]
    app.scale = 2
    app.window = app.open_window(False)
    app.set_ui_size("pequena")
    view.zoom = 2
    bot.key(pygame.K_m)
    bot.frames(0.1)
    assert app.mode == "map" and (app.ui.w, app.ui.h) == (960, 540)
    bot.mouse_to((8, 8))
    bot.shot("mapa_pan_pequena.png")
    bot.key(pygame.K_m)
    app.set_ui_size(ui_before)
    app.scale = 1
    app.window = app.open_window(False)
    bot.frames(0.05)
    view.zoom, view.hidden = zoom_before, hidden_before
    app.save_map_prefs()


def check_wrecks(bot) -> None:
    """v0.3 Marco 3 · destroços, caixa, projeto, fabricador trancado, equipamento, tanque, minimapa e mapas."""
    from game import layers
    from game.systems import Machine
    s, app = bot.state, bot.app
    assert s.layer == "surface"
    zoom_before = app.zoom
    app.set_zoom(1.0, notify=False)
    w = s.world
    print(f"  {len(w.wrecks)} destroços: " + ", ".join(
        f"{x.kind}@{w.dist_from_center(*x.crate):.0f}" for x in w.wrecks))
    cargo = w.wrecks[0]
    crate = s.crates[cargo.crate]
    # 1) a nave de carga mais perto, com a caixa na ponta da rampa de carga
    cx, cy = cargo.crate
    bot.teleport((cx + 1, cy + 1))
    s.o2 = C.O2_MAX
    bot.mouse_to(bot.tile_on_screen((cargo.tx + 2, cargo.ty + 1)))
    bot.frames(0.3)
    assert app.hint().startswith("Nave de carga · destroço"), app.hint()
    bot.shot("destrocos_deserto.png")
    assert 0 in s.wrecks_visited
    # 2) E na caixa: 1ª vez = registro de bordo (LOG 04), projeto do tanque já liberado
    bot.mouse_to(bot.tile_on_screen(cargo.crate))
    bot.frames(0.1)
    assert app.hint() == "[E] Abrir caixa de saque", app.hint()
    assert s.recipe_status("o2_tank") == "blueprint"
    bot.key(pygame.K_e)
    assert app.mode == "terminal" and app.terminal_index == 3 and "o2_tank" in s.blueprints
    bot.frames(0.3)
    bot.shot("registro_bordo.png")
    bot.key(pygame.K_e)                         # continua: abre a caixa
    assert app.mode == "crate" and app.open_crate is crate
    bot.mouse_to((480, 420))
    bot.frames(0.3)
    bot.shot("projeto_encontrado.png")
    bot.frames(C.BLUEPRINT_NOTICE_TIME)
    bot.shot("destroco_caixa.png")
    take = next(r for r, a in app.ui.panel_buttons if a == "take_crate")
    before = s.inventory.count("iron")
    bot.click((take.centerx * 2, take.centery * 2))
    assert crate.empty and s.inventory.count("iron") > before
    bot.frames(0.2)
    bot.shot("destroco_caixa_vazia.png")
    bot.key(pygame.K_ESCAPE)
    assert app.mode == "play"
    bot.mouse_to(bot.tile_on_screen(cargo.crate))
    bot.frames(0.1)
    assert app.hint() == "[E] Caixa vazia", app.hint()
    # 3) módulo da colônia: terminal com o LOG 05
    module = next(x for x in w.wrecks if x.blueprint == "scanner")
    tx, ty = module.terminal
    bot.teleport((tx, ty + 1))
    s.o2 = C.O2_MAX
    bot.mouse_to(bot.tile_on_screen((tx, ty)))
    bot.frames(0.2)
    assert app.hint() == "[E] Ler terminal", app.hint()
    bot.shot("destroco_modulo.png")
    bot.key(pygame.K_e)
    assert app.mode == "terminal" and app.terminal_index == 4
    bot.key(pygame.K_e)
    # 4) fabricador: o tanque liberado, o scanner ainda "???"
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = C.O2_MAX
    give(s, iron=30, silicon=20, ice=10)
    bot.key(pygame.K_e)
    assert app.mode == "fabricator"
    app.fab.set_tab([t for t, _ in C.FAB_TABS].index("suit"))
    bot.mouse_to((900, 500))
    bot.frames(0.2)
    assert s.recipe_status("scanner") == "blueprint" and s.recipe_status("o2_tank") == "ok"
    bot.shot("fabricador_projeto_trancado.png")
    bot.key(pygame.K_RETURN)                    # crafta o tanque (é a receita selecionada)
    assert s.inventory.count("o2_tank") == 1 and app.mode == "play"
    app.fab.set_tab(0)                          # o resto do smoke espera a aba de terraformação
    # 5) Tab: clique no tanque equipa (som equip)
    bot.key(pygame.K_TAB)
    i = next(k for k, st in enumerate(s.inventory.slots) if st and st.item == "o2_tank")
    bot.click(slot_pos(bot, s.inventory, i))
    assert s.equipment.has("o2_tank") and s.o2_max == C.O2_TANK_MAX
    eq = next(r for r, k in app.ui.equip_rects if k == "o2_tank")
    bot.mouse_to((eq.centerx * 2, eq.centery * 2))
    bot.frames(0.2)
    bot.shot("equipamento.png")
    bot.key(pygame.K_ESCAPE)
    # 6) HUD com o tanque: fora da base, a barra vale 220 s
    s.o2 = 150
    bot.teleport((C.BASE_TILE[0] + 12, C.BASE_TILE[1] + 4))
    bot.frames(0.3)
    bot.shot("o2_tanque_hud.png")
    # 7) scanner: projeto (direto no estado), fabrica, equipa; anda um pouco; minimapa
    s.learn("scanner")
    give(s, iron=10, silicon=10)
    s.inventory.add("scanner", 1)
    s.equip_from(next(k for k, st in enumerate(s.inventory.slots) if st and st.item == "scanner"))
    assert s.has_scanner
    for tile in [(cx, cy + 4), (cargo.tx - 10, cargo.ty), (module.tx, module.ty + 4)]:
        bot.teleport(tile)
        s.o2 = s.o2_max
        bot.frames(0.25)
    bot.teleport((cx + 1, cy + 1))
    bot.frames(0.3)
    # perf: superfície com minimapa, zoom 0,75, andando
    app.set_zoom(0.75, notify=False)
    start = len(bot.frame_times)
    for key in (pygame.K_d, pygame.K_s, pygame.K_a, pygame.K_w):
        s.o2 = s.o2_max
        bot.key(key, hold=0.75)
    ft = bot.frame_times[start:]
    print(f"  perf superfície com minimapa, zoom 0,75×: média {sum(ft) / len(ft) * 1000:.1f} ms · "
          f"pior {max(ft) * 1000:.1f} ms ({len(ft)} frames)")
    app.set_zoom(1.0, notify=False)
    bot.frames(0.2)
    bot.shot("minimapa.png")
    # baú e máquina perto da base: marcadores novos do mapa (Máquinas e Baús)
    extra = [Machine("chest", C.BASE_TILE[0] + 4, C.BASE_TILE[1] + 2), Machine("o2", C.BASE_TILE[0] - 4, C.BASE_TILE[1] + 2)]
    # régua de máquinas e baús coladas (vira um marcador por categoria no 2×, separa no 4×)
    extra += [Machine(k, C.BASE_TILE[0] - 16 + 2 * i, C.BASE_TILE[1] + 5)
              for i, k in enumerate(["o2", "o2", "o2", "heater", "heater", "solar"])]
    extra += [Machine("chest", C.BASE_TILE[0] + 4 + i, C.BASE_TILE[1] + 5) for i in range(3)]
    s.surface.machines.extend(extra)
    check_map_panorama(bot)
    bot.key(pygame.K_m)
    assert app.mode == "map"
    bot.frames(0.3)
    bot.shot("mapa_grande.png")
    # mouse no mapa (bug do dono): tooltip no marcador, FECHAR com hover, clique dentro não fecha, fora fecha
    you = next(r for r, e in app.ui.map_markers if e.category == "you")
    bot.mouse_to((you.centerx * 2, you.centery * 2))
    bot.frames(0.1)
    assert app.ui.map_hover is not None and app.ui.map_hover.title == "Você"
    bot.shot("mapa_tooltip.png")
    hotbar, map_zoom, world_zoom = app.hotbar_selected, app.map_view.zoom, app.zoom
    pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1, flipped=False))
    bot.click((app.ui.map_area.centerx * 2, app.ui.map_area.centery * 2))
    assert app.mode == "map" and app.hotbar_selected == hotbar and not app.mouse_held and app.zoom == world_zoom
    app.map_view.set_zoom(map_zoom)
    close = app.ui.map_close_rect
    bot.mouse_to((close.centerx * 2, close.centery * 2))
    bot.frames(0.1)
    bot.shot("mapa_fechar_hover.png")
    bot.click((close.centerx * 2, close.centery * 2))
    assert app.mode == "play", "o FECHAR devia fechar o mapa"
    bot.key(pygame.K_m)
    bot.frames(DT)
    bot.click((4, 4))                                    # fora da janela do mapa
    assert app.mode == "play" and not app.mouse_held, "clique fora devia fechar o mapa"
    # 8) caverna: o mapa só tem o que a luz revelou
    s.enter_layer("cave", layers.ramp_arrival(s.layers["cave"].world))     # o check_cave já criou a caverna
    cave = s.world
    spot = cave_spot(cave)
    path = [(spot[0] - 6, spot[1]), spot, (spot[0] + 6, spot[1])]
    for t in open_floor_near(cave, spot, 3, min_gap=5, radius=10):
        s.machines.append(Machine("lamp", *t))
    for tile in path:
        bot.teleport(tile)
        s.o2 = s.o2_max
        bot.frames(0.25)
    bot.frames(0.2)
    bot.key(pygame.K_m)
    bot.frames(0.3)
    # caverna: abre na camada do player; só os chips do que existe nela (sem Base/Destroço/Máquinas)
    assert app.map_view.layer == "cave"
    chips = [c for _, c in app.ui.map_chips]
    assert "base" not in chips and "wreck" not in chips and "crater" in chips, chips
    bot.shot("mapa_caverna.png")
    bot.key(pygame.K_q)                                   # Q: a superfície, centrada na cratera
    assert app.map_view.layer == "surface" and app.mode == "map"
    bot.frames(0.05)
    bot.shot("mapa_pan_outra_camada.png")
    bot.key(pygame.K_ESCAPE)
    bot.shot("caverna_escura_marco3.png")
    for m in [m for m in s.machines if m.is_lamp][-3:]:
        s.machines.remove(m)
    # volta pra superfície e deixa o resto do smoke como estava (sem equipamento)
    s.enter_layer("surface")
    for m in extra:
        s.surface.machines.remove(m)
    s.equipment.unequip("o2_tank")
    s.equipment.unequip("scanner")
    s.inventory.remove("scanner", s.inventory.count("scanner"))
    s.inventory.remove("o2_tank", s.inventory.count("o2_tank"))
    bot.teleport((C.BASE_TILE[0], C.BASE_TILE[1] + 1))
    s.o2 = C.O2_MAX
    app.set_zoom(zoom_before, notify=False)
    bot.frames(0.2)


def water_ponds(world, stage: int) -> list[list[tuple[int, int]]]:
    """Poças (componentes de água ligados pelos lados) da camada, no estágio dado."""
    wet = {(x, y) for y in range(world.height) for x in range(world.width) if world.is_water(x, y, stage)}
    ponds, seen = [], set()
    for start in wet:
        if start in seen:
            continue
        seen.add(start)
        comp, stack = [], [start]
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in wet and n not in seen:
                    seen.add(n)
                    stack.append(n)
        ponds.append(comp)
    return ponds


def check_water(bot, stage: int) -> None:
    """Água com autotile (poça de cantos redondos, não quadrado): recorte de uma poça pequena na Névoa,
    de um lago no Verde e a tela inteira em volta do lago, além da conta de quantos tiles compostos há."""
    s, app = bot.state, bot.app
    w = s.world
    key = C.STAGES[stage - 1].key
    back = (s.player.x, s.player.y)
    zoom_before = app.zoom
    app.set_zoom(1.0, notify=False)
    ponds = water_ponds(w, stage)
    near = lambda comp: min(w.dist_from_center(*t) for t in comp)    # noqa: E731
    assert ponds, f"nenhuma poça no estágio {stage}"
    diag_only = [t for comp in ponds if len(comp) == 1 for t in comp
                 if any(w.is_water(t[0] + dx, t[1] + dy, stage) for dx in (-1, 1) for dy in (-1, 1))]
    assert not diag_only, f"água ligada só pela quina: {diag_only[:5]}"
    if key == "mist":
        comp = min((c for c in ponds if 3 <= len(c) <= 8), key=near)
        name, crop = "agua_poca_mist.png", (200, 140)
    else:
        comp = min((c for c in ponds if len(c) >= 25), key=near)
        name, crop = "agua_lago_green.png", (360, 240)
    xs, ys = [t[0] for t in comp], [t[1] for t in comp]
    mid = ((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)
    bot.teleport((mid[0], max(ys) + 2))
    s.o2 = C.O2_MAX
    bot.frames(0.2)
    world_xy = ((min(xs) + max(xs) + 1) / 2 * C.TILE, (min(ys) + max(ys) + 1) / 2 * C.TILE)
    shot_zoom(bot, name, world_xy, w=crop[0], h=crop[1], k=2)
    print(f"  {len(ponds)} poças no estágio {key} · essa tem {len(comp)} tiles · "
          f"{len(app.renderer.water_tiles)} tiles de água compostos em cache")
    if key == "green":
        bot.shot("agua_tela.png")
    s.player.x, s.player.y = back
    app.set_zoom(zoom_before, notify=False)
    s.o2 = C.O2_MAX
    bot.frames(0.1)


def check_old_save_title(bot) -> None:
    """Save do v0.3 / v0.4 Marco 1 (versão 6): o v0.4 Marco 2 (geografia nova) não carrega, avisa e só deixa
    começar um novo jogo."""
    app = bot.app
    save.SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    save.SAVE_PATH.write_text('{"version": 6, "seed": 7}', encoding="utf-8")
    app.open_title()
    assert app.title.old and [label for _, label in app.title.options()] == ["Continuar", "Novo jogo", "Sair"]
    assert app.title.options()[app.title.selected][0] == "new"
    bot.mouse_to((480, 300))
    bot.frames(0.5)
    bot.shot("titulo_save_antigo.png")
    bot.key(pygame.K_RETURN)                       # Novo jogo: o antigo vira slot1.v6.json
    backup = save.SAVE_PATH.with_name("slot1.v6.json")
    assert app.mode == "play" and backup.exists() and save.probe()[0] == "ok"
    backup.unlink()
    bot.state = app.state


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
    assert s.stage == C.STORM_STAGE and s.storm == 1.0, "jogo novo começa na tempestade"
    bot.shot("stage1.png")
    check_surface(bot)
    check_ground(bot)
    check_cave(bot)
    check_wrecks(bot)
    check_storm(bot)
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
    assert s.world.is_floor(*ore), "o minério devia ter quebrado"
    assert s.inventory.count("iron") >= 1, "devia ter ganhado ferro"
    print(f"  inventário depois de minerar: {s.inventory.counts()}")

    print("3) fabricador")
    give(s, iron=60, silicon=30, ice=24)
    bot.teleport((96, 97))
    bot.frames(0.3)
    bot.key(pygame.K_e)
    bot.frames(0.2)
    assert bot.app.mode == "fabricator"
    bot.mouse_to((560, 150))
    bot.shot("crafting.png")
    button = next(rect for rect, kind in bot.app.ui.fabricator_buttons if kind == "o2")
    bot.click((button.centerx * 2, button.centery * 2))
    assert bot.app.placing == "o2", "craftar devia entrar no modo de colocar"
    bot.mouse_to(bot.tile_on_screen((93, 98)))
    bot.frames(0.3)
    bot.shot("placing.png")
    bot.click(bot.tile_on_screen((93, 98)))
    assert len(s.machines) == 1
    # mais duas máquinas pelo teclado: S (desce) + Enter
    for target, steps in [((99, 98), 1), ((92, 96), 0)]:
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
    check_storm_gust(bot)
    check_drill(bot)
    check_pause(bot)
    check_zoom_and_fullscreen(bot)
    check_dismantle(bot)
    check_inventory_and_chest(bot)
    check_energy(bot)
    # Árido -> Névoa (Tempestade -> Árido tem a mesma arte: quem muda é a poeira, trilha C)
    check_transition(bot, C.ARID_STAGE, [("transicao_25.png", 0.25), ("transicao_60.png", 0.60),
                                         ("transicao_90.png", 0.90)])

    print("4) terminal (na caverna; o check_cave já testou a rampa de verdade)")
    s.enter_layer("cave")
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
    assert s.layer == "surface", "desmaiou na caverna: acorda na cápsula, na superfície"
    bot.frames(0.5)

    print("6) estágios")
    check_arid(bot)
    bot.key(pygame.K_F2)
    bot.frames(1.0)
    assert s.stage == C.MIST_STAGE
    s.indices["o2"] += 12_914 - s.ti          # exemplo do dono: Ti 12.914 = ~3% da Névoa
    bot.key(pygame.K_d, hold=0.5)
    bot.shot("stage2.png")
    check_water(bot, C.MIST_STAGE)
    give(s, iron=40, silicon=30, ice=20)
    bot.key(pygame.K_e)
    bot.frames(0.2)
    bot.shot("crafting_stage2.png")
    bot.key(pygame.K_ESCAPE)
    bot.frames(3.0)                           # deixa o banner do estágio 2 sumir
    check_drill_feature(bot)
    check_drones(bot)
    check_logistics(bot)
    check_polish(bot)
    check_final_polish(bot)
    check_transition(bot, C.MIST_STAGE, [("transicao_verde_60.png", 0.60)])
    for _ in range(9):
        bot.key(pygame.K_F2)
    bot.frames(1.0)
    assert s.stage == C.GREEN_STAGE
    bot.shot("stage3.png")
    bot.frames(5.0)
    assert bot.app.mode == "end"
    bot.shot("fim.png")
    bot.key(pygame.K_RETURN)
    bot.key(pygame.K_a, hold=1.0)
    bot.frames(1.0)
    bot.shot("stage3_explorando.png")
    check_water(bot, C.GREEN_STAGE)

    print("7) tamanho da interface")
    check_ui_size(bot)

    print("8) save/load e tela de título")
    check_save(bot)
    check_old_save_title(bot)

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
