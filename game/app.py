"""O App: abre a janela, roda o game loop e liga input, regras, desenho e som.

Game loop (60 vezes por segundo):
    1. handle_events()  lê teclado/mouse e decide o que cada tecla faz no modo atual
    2. update(dt)       manda os controles pro GameState e reage aos eventos dele
    3. draw()           desenha mundo + UI numa tela de 960×540 e estica pra janela

Tela e zoom (game/viewport.py): o mundo é desenhado numa "visão" de 960×540 / zoom px e esticado
pra 960×540 (sem suavizar); a UI vem por cima, sempre do mesmo tamanho. A tela de 960×540 é
esticada pra janela mantendo 16:9 (na tela cheia sobra tarja preta se o monitor não for 16:9).
F11 ou Alt+Enter alternam a tela cheia; +/- ou Ctrl+rodinha mudam o zoom.

Modos de tela: "play" (jogando), "fabricator" (menu de receitas),
"terminal" (lendo um log), "inventory" (Tab), "chest" (baú aberto com E), "station" (estação com E),
"pause" (menu do Esc) e "end" (tela de fim do MVP).
Em "pause" e "end" o mundo fica congelado (O₂, máquinas e Ti param). No fabricador, no terminal,
no inventário e no baú o mundo continua (o player só fica parado), como em Core Keeper e Planet Crafter.
O jogo abre em "title" (tela de título, game/title.py); o save/load fica em game/save.py.
"""

import math
import random

import warnings

import pygame

from game import art
from game import config as C
from game import audio as sound
from game import save
from game import drones
from game import energy
from game import settings
from game import viewport
from game.assets import Sprites
from game.audio import Audio
from game.fabricator import FabMenu
from game.inventory import Stack
from game.objectives import ObjectiveTracker
from game.render import Renderer, stage_key
from game.systems import Controls, GameState
from game.textedit import TextField
from game.ui import item_name
from game.title import TitleScreen, draw_saved_notice
from game.ui import UI, FloatingTexts

MOVE_KEYS = {
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
}
NUMBER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8]
INVENTORY_MODES = ("inventory", "chest", "station")
PANEL_MODES = ("chest", "station")          # dois painéis: clique transfere pro outro lado (Planet Crafter)
ZOOM_IN_KEYS = (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)     # "=" é a tecla do "+" sem Shift
ZOOM_OUT_KEYS = (pygame.K_MINUS, pygame.K_KP_MINUS)
BANNER_TIME = 3.5          # banner de estágio: entra em 0,4 s, fica, sai em 0,8 s
BANNER_FADE_IN, BANNER_FADE_OUT = 0.4, 0.8
END_SCREEN_DELAY = 4.5
FOOTSTEP_INTERVAL = 0.3


def fmt_kw(kw: float) -> str:
    """1 -> '1', 1.5 -> '1,5'."""
    return f"{kw:g}".replace(".", ",")


def viewport_label(zoom: float) -> str:
    """1.5 -> '1,5×', 2.0 -> '2×', 0.75 -> '0,75×'."""
    return f"{zoom:g}".replace(".", ",") + "×"


def pick_scale() -> int:
    """Maior fator inteiro que cabe na tela (com uma folguinha pra barra do sistema)."""
    try:
        w, h = pygame.display.get_desktop_sizes()[0]
    except (pygame.error, IndexError):
        return 1
    return max(1, min(int(w * 0.92) // C.SCREEN_W, int(h * 0.92) // C.SCREEN_H))


class App:
    def __init__(self, scale: int | None = None, skip_title: bool = False):
        sound.pre_init()   # configura o mixer antes do pygame.init() (só se o áudio estiver ligado)
        pygame.init()
        self.scale = scale or pick_scale()               # escala inteira da janela (fora da tela cheia)
        self.settings = settings.load()
        self.window = self.open_window(self.settings["fullscreen"])
        pygame.display.set_caption("Hesper · v0.1")
        pygame.mouse.set_visible(False)
        # Tela interna SEM canal alfa, com máscaras explícitas. Sem isso, no macOS (driver Cocoa)
        # o Surface herda o formato da janela, que TEM alfa: os blits gravam alfa 0/255 misturado
        # e o macOS mostra retângulos pretos em volta de sprites (bug do playtest 1).
        self.canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H), 0, 32, (0xFF0000, 0x00FF00, 0x0000FF, 0))
        self._world_view: pygame.Surface | None = None   # onde o mundo é desenhado com zoom != 1 (mesmo formato)
        self.clock = pygame.time.Clock()

        self.sprites = Sprites()
        self.audio = Audio()
        self.renderer = Renderer(self.sprites)
        self.ui = UI()
        self.floaters = FloatingTexts()
        self.red_vignette = art.vignette(C.SCREEN_W, C.SCREEN_H, (170, 18, 8), 255)
        self.state = GameState()
        self.objectives = ObjectiveTracker(self.state)

        self.running = True
        self.t = 0.0
        self.mode = "play"
        self.keys_down: set[int] = set()
        self.mouse = (C.SCREEN_W // 2, C.SCREEN_H // 2)   # em pixels da tela interna (960×540)
        self.mouse_held = False
        self.placing: str | None = None                   # máquina sendo posicionada (a do slot selecionado)
        self.hotbar_selected = 0                          # slot da hotbar escolhido (0 a 7, teclas 1–8)
        self.held: Stack | None = None                    # pilha presa no cursor na tela de inventário
        self.open_chest = None                            # baú aberto (Machine), no modo "chest"
        self.open_station = None                          # estação aberta (Machine), no modo "station"
        self.name_edit: TextField | None = None           # editando o nome do baú (texto digitado)
        self.notice: str | None = None                    # aviso curto ("Inventário cheio")
        self.notice_time = 0.0
        self.rotation = 0
        self.fab = FabMenu()            # aba, seleção e rolagem do fabricador (game/fabricator.py)
        self.terminal_index = 0
        self.banner_stage = 1
        self.banner_time = 0.0
        self.end_timer: float | None = None
        self.footstep_timer = 0.0
        self.footstep_side = 0
        self.drills_near: set[tuple[int, int]] = set()          # drills cheias perto do player agora
        self.drill_full_last: dict[tuple[int, int], float] = {}  # quando avisou "cheia" pela última vez
        self.drill_dust_timer = 0.0
        self.pause_screen = "main"      # "main", "volumes" ou "controls"
        self.pause_selected = 0
        self.dragging_slider: int | None = None
        self.zoom = self.settings["zoom"]
        self.toast: str | None = None   # aviso neutro rápido ("Zoom 1,5×")
        self.toast_time = 0.0
        self.audio.set_mix(**settings.mix(self.settings))
        self.audio.start_ambient(stage_key(self.state.stage))
        # save/load e tela de título (game/save.py, game/title.py)
        self.autosave_timer = 0.0       # segundos jogando (modo "play") desde o último save
        self.saved_notice = 0.0         # quanto falta do aviso "Jogo salvo" no HUD
        self.title = TitleScreen(self.ui, self.renderer, self.audio.play)
        try:                            # digitação (TEXTINPUT) só liga enquanto edita o nome do baú
            pygame.key.stop_text_input()
        except pygame.error:
            pass
        if not skip_title:              # skip_title: entra direto num jogo novo (testes)
            self.open_title()

    # ---- loop -----------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000
            self.step(dt)
        pygame.quit()

    def step(self, dt: float) -> None:
        self.handle_events()
        self.update(dt)
        if self.mode == "title":
            self.draw_title()
        else:
            self.draw()
        pygame.display.flip()

    # ---- janela, tela cheia e zoom -----------------------------------------------
    def open_window(self, fullscreen: bool) -> pygame.Surface:
        """Tela cheia na resolução do monitor (size (0, 0) = "desktop fullscreen" do SDL, sem trocar o
        modo de vídeo) ou janela com escala inteira. O desenho se ajusta ao tamanho que vier."""
        if fullscreen:
            try:
                return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except pygame.error as err:
                print(f"[tela] não deu pra abrir em tela cheia: {err}")
        size = (C.SCREEN_W * self.scale, C.SCREEN_H * self.scale)
        surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        # Saindo da tela cheia, o macOS deixa a janela no tamanho do monitor: força o tamanho e centraliza.
        try:
            with warnings.catch_warnings():          # from_display_module avisa de depreciação; aqui é o certo
                warnings.simplefilter("ignore", DeprecationWarning)
                window = pygame.Window.from_display_module()
            if window.size != size:
                window.size = size
                window.position = pygame.WINDOWPOS_CENTERED
            surface = pygame.display.get_surface()
        except (AttributeError, pygame.error):
            pass
        return surface

    def toggle_fullscreen(self) -> None:
        fullscreen = not self.settings["fullscreen"]
        self.window = self.open_window(fullscreen)
        self.settings = settings.clean({**self.settings, "fullscreen": fullscreen})
        settings.save(self.settings)
        pygame.mouse.set_visible(False)

    def set_zoom(self, zoom: float, notify: bool = True) -> None:
        if zoom == self.zoom:
            return
        self.zoom = zoom
        self.settings = settings.clean({**self.settings, "zoom": zoom})
        settings.save(self.settings)
        if notify:
            self.show_toast(f"Zoom {viewport_label(zoom)}")
            self.audio.play("ui_click")

    def zoom_step(self, step: int) -> None:
        self.set_zoom(viewport.step_zoom(self.zoom, step))

    def show_toast(self, text: str) -> None:
        self.toast, self.toast_time = text, C.ZOOM_TOAST_TIME

    @property
    def view_size(self) -> tuple[int, int]:
        """Quanto do mundo (px) aparece na tela com o zoom atual."""
        return viewport.view_size(self.zoom)

    def window_to_canvas(self, pos: tuple[int, int]) -> tuple[int, int]:
        return viewport.window_to_canvas(pos, self.window.get_size())

    def present(self) -> None:
        """Estica a tela de 960×540 pra janela mantendo 16:9 (tarja preta no que sobrar), sem suavizar."""
        x, y, w, h = viewport.letterbox(self.window.get_size())
        if (x, y) != (0, 0):
            self.window.fill((0, 0, 0))          # tarja preta (monitor que não é 16:9)
        # Copiar uma superfície sem alfa pra janela grava alfa 255 (opaco) em todos os pixels.
        if (w, h) == self.canvas.get_size():
            self.window.blit(self.canvas, (x, y))
        else:
            self.window.blit(pygame.transform.scale(self.canvas, (w, h)), (x, y))

    # ---- input ----------------------------------------------------------------
    @property
    def cam(self) -> tuple[int, int]:
        return self.renderer.camera(self.state, self.view_size)

    def mouse_world(self) -> tuple[float, float]:
        """Onde o mouse está, em pixels do mundo (considerando o zoom)."""
        return viewport.canvas_to_world(self.mouse, self.cam, self.zoom)

    def mouse_tile(self) -> tuple[int, int]:
        # mira no que está à vista: o topo elevado de uma parede cobre o tile de cima dela
        return self.state.world.visual_tile_at(*self.mouse_world())

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_game()
            elif event.type in (pygame.VIDEORESIZE, pygame.WINDOWSIZECHANGED):
                self.window = pygame.display.get_surface()     # janela redimensionada: o present ajusta a tarja
            elif self.name_edit is not None and event.type == pygame.TEXTINPUT:
                self.name_edit.insert(event.text)
            elif self.name_edit is not None and event.type == pygame.KEYDOWN:
                self.on_name_key(event.key)       # editando: nenhuma tecla do jogo (E, Tab, 1–8, WASD, +/-)
            elif event.type == pygame.KEYDOWN:
                self.keys_down.add(event.key)
                if not self.on_global_key(event.key, getattr(event, "mod", 0)):
                    self.on_key(event.key)
            elif event.type == pygame.KEYUP:
                self.keys_down.discard(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse = self.window_to_canvas(event.pos)
                if self.mode == "pause":
                    self.pause_hover()
                elif self.mode == "title":
                    self.title.hover(self.mouse[0] / 2, self.mouse[1] / 2)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse = self.window_to_canvas(event.pos)
                self.on_click(event.button)
            elif event.type == pygame.MOUSEWHEEL and self.mode != "title" and self.zoom_modifier():
                self.zoom_step(1 if event.y > 0 else -1)        # Ctrl+rodinha pra cima = aproxima
            elif event.type == pygame.MOUSEWHEEL and self.mode == "fabricator":
                self.fab.scroll(-1 if event.y > 0 else 1)       # rodinha rola a lista de receitas
            elif event.type == pygame.MOUSEWHEEL and self.mode == "play" and not self.state.fainted \
                    and self.name_edit is None:
                # rodinha pra baixo = próximo slot (y < 0), pra cima = anterior
                self.select_hotbar((self.hotbar_selected + (1 if event.y < 0 else -1)) % C.HOTBAR_SLOTS)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_held = False
                if self.dragging_slider is not None:
                    self.dragging_slider = None
                    settings.save(self.settings)

    def zoom_modifier(self) -> bool:
        """Ctrl (ou Cmd no Mac) segurado: a rodinha mexe no zoom em vez da hotbar."""
        held = {pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_LMETA, pygame.K_RMETA} & self.keys_down
        return bool(held) or bool(pygame.key.get_mods() & (pygame.KMOD_CTRL | pygame.KMOD_META))

    def on_global_key(self, key: int, mod: int) -> bool:
        """Teclas que valem em qualquer tela: F11/Alt+Enter (tela cheia) e +/- (zoom, fora do título).
        Devolve True se a tecla foi usada aqui."""
        alt = bool(mod & pygame.KMOD_ALT) or bool({pygame.K_LALT, pygame.K_RALT} & self.keys_down)
        if key == pygame.K_F11 or (alt and key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
            self.toggle_fullscreen()
            return True
        if self.mode != "title" and key in ZOOM_IN_KEYS:
            self.zoom_step(1)
            return True
        if self.mode != "title" and key in ZOOM_OUT_KEYS:
            self.zoom_step(-1)
            return True
        return False

    def on_key(self, key: int) -> None:
        if self.mode == "title":
            self.on_title_action(self.title.on_key(key))
            return
        state = self.state
        if key == pygame.K_F1:
            state.toggle_time_scale()
        elif key == pygame.K_F2:
            state.debug_add_ti()
        if state.fainted:
            return

        if self.mode == "pause":
            self.on_pause_key(key)
        elif self.mode == "fabricator":
            if key in (pygame.K_e, pygame.K_ESCAPE):
                self.set_mode("play")
            elif key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
                self.fab.move(-1 if key in (pygame.K_w, pygame.K_UP) else 1)
                self.audio.play("ui_click")
            elif key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT, pygame.K_TAB):
                self.fab.switch_tab(-1 if key in (pygame.K_a, pygame.K_LEFT) else 1)   # Tab: próxima aba
                self.audio.play("ui_click")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and self.fab.current:
                self.try_craft(self.fab.current, batch=self.shift_held())   # Shift: até 5
        elif self.mode == "terminal":
            if key in (pygame.K_e, pygame.K_ESCAPE, pygame.K_RETURN):
                self.set_mode("play")
        elif self.mode in INVENTORY_MODES:
            if key in (pygame.K_TAB, pygame.K_ESCAPE, pygame.K_e):
                self.close_inventory()
        elif self.mode == "end":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self.set_mode("play")
        else:  # play
            if key == pygame.K_e:
                target = state.interaction()      # terminal ou drill, o que estiver mais perto
                if target and target[0] == "terminal":
                    state.read_terminal(target[1])
                    self.terminal_index = target[1]
                    self.mode = "terminal"
                elif target and target[0] == "drill":
                    state.collect(target[1])
                elif target and target[0] == "station":
                    self.open_station = target[1]
                    self.placing = None
                    self.set_mode("station")
                elif target and target[0] == "chest":
                    self.open_chest = self.renderer.open_chest = target[1]
                    self.placing = None
                    self.mode = "chest"
                    self.mouse_held = False
                    self.audio.play("chest_open")
                elif state.in_base_zone():
                    self.placing = None
                    self.set_mode("fabricator")
                    state.fabricator_opened = True
            elif key == pygame.K_ESCAPE and self.placing:
                self.placing = None
                self.audio.play("ui_close")
            elif key == pygame.K_ESCAPE:
                self.open_pause()
            elif key == pygame.K_r and self.placing:
                self.rotation = (self.rotation + 1) % 4
            elif key == pygame.K_TAB:
                self.placing = None
                self.set_mode("inventory")
            elif key in NUMBER_KEYS:
                self.select_hotbar(NUMBER_KEYS.index(key))

    # ---- hotbar e inventário ----------------------------------------------------
    def select_hotbar(self, index: int) -> None:
        """Escolhe o slot da hotbar. Se tiver máquina nele, já entra no modo de colocar."""
        self.hotbar_selected = index
        stack = self.state.inventory.slots[index]
        placeable = stack and stack.item in C.MACHINES and C.MACHINES[stack.item].placeable
        self.placing = stack.item if placeable else None      # o drone é item, mas não vai pro chão
        self.audio.play("ui_click")

    def show_notice(self, text: str) -> None:
        self.notice, self.notice_time = text, C.NOTICE_TIME

    def other_side(self, inv):
        """Shift+clique: o inventário do outro lado (player <-> baú). None se só o Tab estiver aberto."""
        if self.open_chest is None:
            return None
        return self.open_chest.storage if inv is self.state.inventory else self.state.inventory

    def shift_held(self) -> bool:
        return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) or bool({pygame.K_LSHIFT, pygame.K_RSHIFT} & self.keys_down)

    def on_inventory_click(self, button: int) -> None:
        """Clique na tela de inventário (Tab): pega e solta pilhas (a "mão" é self.held).
        Com baú ou estação aberta, o clique transfere pro outro lado (on_panel_click)."""
        ux, uy = self.mouse[0] / 2, self.mouse[1] / 2
        if self.mode in PANEL_MODES:
            self.on_panel_click(button, (ux, uy))
            return
        hit = next(((inv, i) for rect, inv, i in self.ui.slot_rects if rect.collidepoint(ux, uy)), None)
        if hit is None:
            return
        inv, i = hit
        before = ((self.held.item, self.held.count) if self.held else None, inv.to_data())
        if button == 1:
            self.held = inv.put(i, self.held)            # mão vazia pega; mão cheia solta/junta/troca
        elif self.held is None:
            self.held = inv.take_half(i)                 # direito com a mão vazia: pega metade
        else:                                            # direito com a mão cheia: solta 1 unidade
            slot = inv.slots[i]
            if slot is None or (slot.item == self.held.item and slot.room > 0):
                inv.put(i, Stack(self.held.item, 1))
                self.held.count -= 1
                if self.held.count == 0:
                    self.held = None
        after = ((self.held.item, self.held.count) if self.held else None, inv.to_data())
        if after != before:
            self.audio.play("inv_move")

    def on_panel_click(self, button: int, pos: tuple[float, float]) -> None:
        """Baú ou estação aberta (estilo Planet Crafter): esquerdo manda a pilha inteira pro outro
        lado, direito manda 1, Shift+esquerdo manda todas as pilhas daquele item (só no baú)."""
        ui, state = self.ui, self.state
        if self.name_edit is not None:                   # clicou fora do campo: confirma o nome
            if ui.name_rect is not None and ui.name_rect.collidepoint(pos):
                return
            self.finish_name_edit(confirm=True)
        if button == 1 and self.on_chest_filter_click():   # seletor "Drones trazem" do baú
            return
        if button == 1:
            for rect, action in ui.panel_buttons:
                if rect.collidepoint(pos):
                    self.on_panel_button(action)
                    return
            if self.open_chest is not None and ui.name_rect is not None and ui.name_rect.collidepoint(pos):
                self.start_name_edit()
                return
        amount = None if button == 1 else 1
        if self.open_station is not None:
            station = self.open_station
            bay = next((slot for rect, slot in ui.bay_rects if rect.collidepoint(pos)), None)
            if bay is not None:
                drone = station.station.drone_in(bay)
                if drone is not None and drone.busy:
                    self.show_notice("Drone em voo: espere ele pousar")
                elif drone is not None and state.station_undock(station, bay):
                    self.audio.play("inv_move")
                return
            res = next((r for rect, r in ui.buffer_rects if rect.collidepoint(pos)), None)
            if res is not None:
                if state.station_take(station, res, amount):
                    self.audio.play("inv_move")
                return
        hit = next(((inv, i) for rect, inv, i in ui.slot_rects if rect.collidepoint(pos)), None)
        if hit is None or hit[0].slots[hit[1]] is None:
            return
        inv, i = hit
        item = inv.slots[i].item
        if self.open_station is not None:                # só do inventário pra estação, e só drone
            if item != "drone":
                self.show_notice("Só drones vão na estação")
            elif not self.open_station.station.free_slots():
                self.show_notice("Estação sem slot livre")
            elif state.station_dock(self.open_station, i, amount):
                self.audio.play("inv_move")
            return
        target = self.other_side(inv)
        if button == 1 and self.shift_held():
            moved = inv.quick_move(i, target)            # todas as pilhas desse item vão pro outro lado
        else:
            moved = inv.transfer(i, target, amount)
        if moved:
            self.audio.play("inv_move")
        else:
            self.show_notice("Baú cheio" if target is not self.state.inventory else "Inventário cheio")

    def on_panel_button(self, action: str) -> None:
        state, moved = self.state, 0
        if action == "take_all" and self.open_chest is not None:
            moved = self.open_chest.storage.transfer_all(state.inventory)
            if not self.open_chest.storage.is_empty():
                self.show_notice("Inventário cheio")
        elif action == "store_all" and self.open_chest is not None:
            # "Guardar recursos": só ferro/silício/gelo; máquinas e drones ficam com o player (bíblia §8)
            moved = state.inventory.transfer_all(self.open_chest.storage, C.RESOURCES)
            if any(state.inventory.count(r) for r in C.RESOURCES):
                self.show_notice("Baú cheio")
        elif action == "take_buffer" and self.open_station is not None:
            moved = state.collect_station(self.open_station)
        if moved:
            self.audio.play("inv_move")

    # ---- nome do baú ------------------------------------------------------------
    def start_name_edit(self) -> None:
        name = self.open_chest.name or C.CHEST_DEFAULT_NAME
        self.name_edit = TextField(name, C.CHEST_NAME_MAX)
        self.keys_down.clear()                           # nada de WASD "preso" enquanto digita
        try:
            pygame.key.start_text_input()
        except pygame.error:
            pass
        self.audio.play("ui_click")

    def finish_name_edit(self, confirm: bool) -> None:
        if self.name_edit is None:
            return
        if confirm and self.open_chest is not None:
            self.state.rename_chest(self.open_chest, self.name_edit.text)
        self.name_edit = None
        try:
            pygame.key.stop_text_input()
        except pygame.error:
            pass
        self.audio.play("ui_click" if confirm else "ui_close")

    def on_name_key(self, key: int) -> None:
        """Teclas enquanto edita o nome: Enter confirma, Esc cancela, Backspace apaga. O resto vem
        pelo TEXTINPUT (as letras) e não aciona nada do jogo."""
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.finish_name_edit(confirm=True)
        elif key == pygame.K_ESCAPE:
            self.finish_name_edit(confirm=False)
        elif key == pygame.K_BACKSPACE:
            self.name_edit.backspace()

    def hovered_slot_label(self, mouse_ui) -> str | None:
        """Tooltip do slot debaixo do mouse: "Ferro · 37", "Drone · em voo (travado)"..."""
        ui = self.ui
        hovered = next((inv.slots[i] for rect, inv, i in ui.slot_rects if rect.collidepoint(mouse_ui)), None)
        if hovered is not None:
            return f"{item_name(hovered.item)} · {hovered.count}"
        if self.open_station is not None:
            st = self.open_station.station
            bay = next((slot for rect, slot in ui.bay_rects if rect.collidepoint(mouse_ui)), None)
            if bay is not None:
                drone = st.drone_in(bay)
                if drone is None:
                    return "Slot de drone vazio"
                return "Drone · em voo (travado)" if drone.busy else "Drone · pousado (clique tira)"
            res = next((r for rect, r in ui.buffer_rects if rect.collidepoint(mouse_ui)), None)
            if res is not None:
                return f"{item_name(res)} · {st.buffer.get(res, 0)} (buffer)"
        return None

    def station_status(self) -> str:
        st = self.open_station
        n = len(st.station.drones)
        flying = sum(1 for d in st.station.drones if d.busy)
        kw = energy.machine_use(st.kind)
        text = f"{n} drone{'s' if n != 1 else ''}"
        if flying:
            text += f" · {flying} em voo"
        return text + f" · {fmt_kw(kw)} kW"

    def on_chest_filter_click(self) -> bool:
        """Clique no seletor "Drones trazem" do baú aberto: troca o filtro. True se acertou um botão."""
        value = self.ui.chest_filter_at((self.mouse[0] / 2, self.mouse[1] / 2))
        if value is None or self.open_chest is None:
            return False
        if value != self.open_chest.filter:
            self.open_chest.filter = value
            self.audio.play("ui_click")
        return True

    def labeled_chests(self) -> list:
        """Baús que mostram o rótulo flutuante ([ícone do filtro] Nome): os no alcance do E e o debaixo do mouse."""
        found = []
        for chest in (self.hovered_machine(), *self.state.chests_showing_name()):
            if chest is not None and chest.is_chest and not any(chest is c for c in found):
                found.append(chest)
        return found

    def stash_held(self) -> bool:
        """Devolve a pilha da mão pro inventário (ou pro baú aberto). False se não coube tudo."""
        if self.held is None:
            return True
        left = self.state.inventory.add(self.held.item, self.held.count)
        if left and self.open_chest is not None:
            left = self.open_chest.storage.add(self.held.item, left)
        self.held = Stack(self.held.item, left) if left else None
        return self.held is None

    def close_inventory(self) -> None:
        self.finish_name_edit(confirm=True)
        if not self.stash_held():
            self.show_notice("Sem espaço pro item na mão")
            return
        self.set_mode("play")

    # ---- menu de pausa ---------------------------------------------------------
    def open_pause(self) -> None:
        self.pause_screen, self.pause_selected = "main", 0
        self.set_mode("pause")

    def pause_item_count(self) -> int:
        return {"main": len(UI.PAUSE_OPTIONS), "volumes": len(UI.VOLUME_ROWS) + 3, "controls": 1}[self.pause_screen]

    def on_pause_key(self, key: int) -> None:
        if key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
            step = -1 if key in (pygame.K_w, pygame.K_UP) else 1
            self.pause_selected = (self.pause_selected + step) % self.pause_item_count()
            self.audio.play("ui_click")
        elif key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT) and self.pause_screen == "volumes":
            n = len(UI.VOLUME_ROWS)
            left = key in (pygame.K_a, pygame.K_LEFT)
            if self.pause_selected < n:
                key_name = UI.VOLUME_ROWS[self.pause_selected][0]
                self.set_volume(key_name, self.settings[key_name] + (-0.1 if left else 0.1), save=True)
            elif self.pause_selected == n:            # tela cheia: A/D também alternam
                self.toggle_fullscreen()
                self.audio.play("ui_click")
            elif self.pause_selected == n + 1:        # zoom: A afasta, D aproxima
                self.set_zoom(viewport.step_zoom(self.zoom, -1 if left else 1), notify=False)
                self.audio.play("ui_click")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.pause_activate(self.pause_selected)
        elif key == pygame.K_ESCAPE:
            if self.pause_screen == "main":
                self.set_mode("play")
            else:
                self.pause_screen, self.pause_selected = "main", 0
                self.audio.play("ui_close")

    def pause_activate(self, index: int) -> None:
        if self.pause_screen == "main":
            option = UI.PAUSE_OPTIONS[index]
            if option == "Continuar":
                self.set_mode("play")
            elif option == "Opções":
                self.pause_screen, self.pause_selected = "volumes", 0
                self.audio.play("ui_open")
            elif option == "Controles":
                self.pause_screen, self.pause_selected = "controls", 0
                self.audio.play("ui_open")
            elif option == "Salvar e sair":
                self.save_game()
                self.open_title()
            else:  # Sair
                settings.save(self.settings)
                self.quit_game()
        elif self.pause_screen == "volumes" and index < len(UI.VOLUME_ROWS):
            self.pause_selected = index
        elif self.pause_screen == "volumes" and index == len(UI.VOLUME_ROWS):       # tela cheia
            self.pause_selected = index
            self.toggle_fullscreen()
            self.audio.play("ui_click")
        elif self.pause_screen == "volumes" and index == len(UI.VOLUME_ROWS) + 1:   # zoom: dá a volta
            self.pause_selected = index
            levels = C.ZOOM_LEVELS
            self.set_zoom(levels[(levels.index(self.zoom) + 1) % len(levels)], notify=False)
            self.audio.play("ui_click")
        else:   # "Voltar" (volumes ou controles)
            self.pause_screen, self.pause_selected = "main", 0
            self.audio.play("ui_close")

    def set_volume(self, key: str, value: float, save: bool = False) -> None:
        self.settings = settings.clean({**self.settings, key: round(value, 2)})
        self.audio.set_mix(**settings.mix(self.settings))
        self.audio.play("ui_click")
        if save:
            settings.save(self.settings)

    def pause_hover(self) -> None:
        ux, uy = self.mouse[0] / 2, self.mouse[1] / 2
        if self.dragging_slider is not None:
            bar = self.ui.pause_sliders[self.dragging_slider]
            key = UI.VOLUME_ROWS[self.dragging_slider][0]
            value = round(max(0.0, min(1.0, (ux - bar.x) / bar.w)) * 20) / 20   # passos de 5%
            if value != self.settings[key]:
                self.set_volume(key, value)
            return
        for i, rect in enumerate(self.ui.pause_items):
            if rect.collidepoint(ux, uy):
                self.pause_selected = i

    def on_pause_click(self) -> None:
        ux, uy = self.mouse[0] / 2, self.mouse[1] / 2
        for i, bar in enumerate(self.ui.pause_sliders):
            if bar.inflate(4, 8).collidepoint(ux, uy):     # área de clique um pouco maior que a barra
                self.dragging_slider = i
                self.pause_selected = i
                self.pause_hover()
                return
        for i, rect in enumerate(self.ui.pause_items):
            if rect.collidepoint(ux, uy):
                self.pause_activate(i)
                return

    def on_click(self, button: int) -> None:
        if self.mode == "title":
            if button == 1:
                self.on_title_action(self.title.click(self.mouse[0] / 2, self.mouse[1] / 2))
            return
        if self.mode == "pause":
            if button == 1:
                self.on_pause_click()
            return
        if self.state.fainted:
            return
        if self.mode in INVENTORY_MODES:
            if button in (1, 3):
                self.on_inventory_click(button)
            return
        if button == 3 and self.placing:   # botão direito também cancela
            self.placing = None
            return
        if button == 3 and self.mode == "play":   # botão direito numa máquina: desmonta
            machine = self.hovered_machine()
            if machine:
                self.state.dismantle(machine)
            return
        if button != 1:
            return
        if self.mode == "fabricator":
            ux, uy = self.mouse[0] // 2, self.mouse[1] // 2
            for rect, kind in self.ui.fabricator_buttons:
                if rect.collidepoint(ux, uy):
                    self.try_craft(kind, batch=self.shift_held())
                    return
            for rect, index in self.ui.fabricator_tabs:
                if rect.collidepoint(ux, uy):
                    if index != self.fab.tab:
                        self.fab.set_tab(index)
                        self.audio.play("ui_click")
                    return
            for rect, kind in self.ui.fabricator_rows:     # a lista pode estar rolada: acha pelo tipo
                if rect.collidepoint(ux, uy):
                    self.fab.select(kind)
        elif self.mode == "play":
            if self.placing:
                tile = self.place_target()
                if tile is not None and self.state.place(self.placing, tile, self.rotation, self.hotbar_selected):
                    if self.state.inventory.slots[self.hotbar_selected] is None:   # acabou a pilha do slot
                        self.placing = None
            else:
                self.mouse_held = True

    def set_mode(self, mode: str) -> None:
        if self.mode in INVENTORY_MODES and mode != self.mode:
            self.finish_name_edit(confirm=True)
            self.stash_held()            # devolve a pilha da mão (se não couber, ela espera o próximo Tab)
            self.open_station = None
            if self.mode == "chest":     # fechou o baú: som próprio no lugar do ui_close
                self.audio.play("chest_close")
                self.open_chest = self.renderer.open_chest = None
                self.mode = mode
                self.mouse_held = False
                return
        if mode != self.mode:
            self.audio.play("ui_open" if mode in ("fabricator", "pause", "inventory", "station") else "ui_close")
        self.mode = mode
        self.mouse_held = False

    def try_craft(self, kind: str, batch: bool = False) -> None:
        """Fabrica 1 (ou, com Shift, até C.CRAFT_BATCH: para quando faltar recurso). O lote mostra "Drone x5"."""
        made = self.state.craft_many(kind) if batch else int(self.state.craft(kind))
        if batch and made:
            self.show_toast(f"{item_name(kind)} x{made}")
        if made:
            self.rotation = 0
            self.set_mode("play")
            # fabricou: se a máquina caiu na hotbar, seleciona o slot e já entra no modo de colocar
            slots = self.state.inventory.slots[:C.HOTBAR_SLOTS]
            index = next((i for i, st in enumerate(slots) if st and st.item == kind), None)
            if index is not None:
                self.select_hotbar(index)

    def controls(self) -> Controls:
        if self.mode != "play":
            return Controls()
        mx = sum(MOVE_KEYS[k][0] for k in self.keys_down if k in MOVE_KEYS)
        my = sum(MOVE_KEYS[k][1] for k in self.keys_down if k in MOVE_KEYS)
        mine = self.mouse_tile() if self.mouse_held and not self.placing else None
        return Controls(max(-1, min(1, mx)), max(-1, min(1, my)), mine)

    # ---- update ---------------------------------------------------------------
    def update(self, dt: float) -> None:
        dt = min(dt, C.MAX_DT)
        self.t += dt
        if self.mode == "title":            # nenhum jogo rodando: só o som
            self.audio.update(dt)
            return
        self.update_autosave(dt)
        if self.mode == "pause":            # congelado: só o som continua (pra ouvir o slider mexendo)
            self.audio.update(dt)
            return
        if self.mode != "end":
            self.state.update(dt, self.controls())
        # a máquina na mão tem que continuar no slot selecionado (pode ter sido movida no Tab)
        stack = self.state.inventory.slots[self.hotbar_selected]
        if self.placing and (stack is None or stack.item != self.placing):
            self.placing = None
        self.notice_time = max(0.0, self.notice_time - dt)
        self.toast_time = max(0.0, self.toast_time - dt)
        self.banner_time += dt
        self.renderer.machine_t += dt * self.state.power.factor    # animação das máquinas no ritmo da energia
        self.floaters.update(dt)
        self.renderer.update_particles(dt)
        events = self.state.pop_events()
        broke = any(e[0] == "break" for e in events)
        for event in events:
            if event[0] == "mine_hit" and broke:
                continue   # no frame em que o tile quebra, toca só o mine_break
            self.on_game_event(event)
        if self.end_timer is not None:
            self.end_timer -= dt
            if self.end_timer <= 0:
                self.end_timer = None
                self.set_mode("end")
        self.update_ambient_sounds(dt)
        self.spawn_machine_floaters(dt)
        self.objectives.update(self.state, dt)

    def on_game_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "mine_hit":
            self.audio.play("mine_hit")
            # faíscas saindo da ponta da broca
            self.renderer.spawn_chips(None, "#ffd27a", 2, at=self.renderer.drill_tip(self.state))
            self.renderer.spawn_chips(None, "#b0704f", 2, at=self.renderer.drill_tip(self.state))
        elif kind == "break":
            _, tile, tile_kind = event
            resource = C.ORE_TILES.get(tile_kind)
            color = C.ORE_COLORS[resource][0] if resource else C.PALETTES[stage_key(self.state.stage)]["rock_hi"]
            self.renderer.spawn_chips(tile, color, 12)
            self.audio.play("mine_break")
        elif kind == "pickup":
            _, tile, resource, amount = event
            x, y = (tile[0] + 0.5) * C.TILE, tile[1] * C.TILE - 8
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", x, y, C.ORE_COLORS[resource][0])
            self.audio.play("pickup", delay=0.06)   # 60 ms depois do mine_break, pra não embolar
        elif kind == "drill_collect":
            _, resource, amount, (ax, ay) = event
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", ax, ay - 88, C.ORE_COLORS[resource][0])
            self.audio.play("drill_collect")          # já tem o "poop" do pickup dentro: não toca os dois
        elif kind == "station_collect":         # E na estação: igual à coleta da drill
            _, resource, amount, (ax, ay) = event
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", ax, ay - 80, C.ORE_COLORS[resource][0])
            self.audio.play("drill_collect")
        elif kind == "drone_deliver":           # drone entregou no baú (ou no buffer da estação)
            _, resource, amount, (x, y) = event
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", x, y - 78, C.ORE_COLORS[resource][0])   # acima do rótulo do baú
            distance = math.hypot(x - self.state.player.x, y - self.state.player.y) / C.TILE
            self.audio.play("drone_deliver", gain=sound.drone_deliver_gain(distance))
        elif kind == "station_full":
            self.show_notice("Estação cheia: coloque um baú perto")
        elif kind == "dismantle":
            _, _, tile = event
            self.renderer.spawn_chips(tile, "#9a9086", 14)       # poeirinha
            self.renderer.spawn_chips(tile, "#c8c0b4", 8)
            self.audio.play("place_low")
        elif kind == "inv_full":
            if self.notice != "Inventário cheio" or self.notice_time < C.NOTICE_TIME - 0.5:
                self.audio.play("inv_full")          # não repete o som no mesmo meio segundo
            self.show_notice("Inventário cheio")
        elif kind == "chest_not_empty":
            self.show_notice("Esvazie o baú antes de desmontar")
        elif kind == "craft":
            self.audio.play("craft")
        elif kind == "power_low":             # o déficit de energia começou (sem o arquivo, fica em silêncio)
            self.audio.play("power_low")
        elif kind == "place":
            self.audio.play("place")
        elif kind == "refill":
            self.audio.play("o2_refill")
        elif kind == "faint":
            self.audio.play("faint")
            self.audio.set_alarm(False)
            self.placing = None
            self.set_mode("play")
        elif kind == "wake":
            self.audio.play("o2_refill")
        elif kind == "terminal":
            self.audio.play("terminal_open")
        elif kind == "stage_up":
            self.banner_stage = event[1]
            self.banner_time = 0.0
            self.audio.stage_up(stage_key(event[1]))
            if event[1] == 3:
                self.end_timer = END_SCREEN_DELAY

    def update_ambient_sounds(self, dt: float) -> None:
        state, audio = self.state, self.audio
        # alarme com histerese: liga abaixo de 25%, desliga em 27% (ou desmaiado)
        o2_percent = 100 * state.o2 / C.O2_MAX
        audio.set_alarm(not state.fainted and sound.alarm_should_play(audio.alarm_on, o2_percent))
        # zumbido pela máquina mais próxima
        nearest = min((math.hypot((m.tx + 0.5) * C.TILE - state.player.x, (m.ty + 1) * C.TILE - state.player.y) / C.TILE
                       for m in state.machines if m.type.index is not None), default=None)
        audio.set_hum(sound.hum_volume(nearest))
        self.update_drills_feedback(dt)
        # drones: loop pelos 2 voando mais perto · painel solar: zumbido pelo mais perto
        flying = sorted(math.hypot(d.x - state.player.x, d.y - state.player.y) / C.TILE
                        for m in state.stations for d in m.station.drones if d.in_air)
        audio.set_drone_loops([sound.drone_loop_volume(d) for d in flying[:2]])
        nearest_solar = min((state.drill_distance(m) / C.TILE for m in state.machines if m.kind == "solar"), default=None)
        audio.set_solar_hum(sound.solar_hum_volume(nearest_solar))
        # ambiente: some no desmaio, abaixa lendo terminal
        audio.duck_ambient(0.0 if state.fainted else 0.6 if self.mode == "terminal" else 1.0)
        audio.update(dt)
        if state.player.moving and self.mode == "play":
            self.footstep_timer -= dt
            if self.footstep_timer <= 0:
                self.audio.play(f"footstep_{self.footstep_side}")
                self.footstep_side = 1 - self.footstep_side
                self.footstep_timer = FOOTSTEP_INTERVAL
        else:
            self.footstep_timer = 0.0

    def update_drills_feedback(self, dt: float) -> None:
        """Som e poeira das drills: loop pelas 2 trabalhando mais perto, aviso de cheia, poeirinha na base."""
        state = self.state
        working = sorted(state.drill_distance(d) / C.TILE for d in state.drills if not d.full)
        self.audio.set_drill_loops([sound.drill_loop_volume(d) for d in working[:2]])
        # chegou perto (~4 tiles) de uma drill cheia: avisa uma vez (no máximo a cada 10 s por drill)
        near_now = set()
        for d in state.drills:
            if d.full and state.drill_distance(d) <= C.DRILL_FULL_NOTICE:
                key = (d.tx, d.ty)
                near_now.add(key)
                if key not in self.drills_near and self.t - self.drill_full_last.get(key, -1e9) >= C.DRILL_FULL_COOLDOWN:
                    self.audio.play("drill_full")
                    self.drill_full_last[key] = self.t
        self.drills_near = near_now
        # poeira saindo da base enquanto perfura (só as que estão na tela)
        self.drill_dust_timer -= dt
        if self.drill_dust_timer <= 0:
            self.drill_dust_timer = 0.12 / max(0.2, state.power.factor)   # no déficit, menos poeira
            cx, cy = self.cam
            vw, vh = self.view_size
            for d in state.drills:
                ax, ay = d.anchor
                if not d.full and -64 < ax - cx < vw + 64 and -64 < ay - cy < vh + 64:
                    side = random.choice((-1, 1))
                    self.renderer.spawn_chips(None, random.choice(("#9a9086", "#c8c0b4")), 1,
                                              at=(ax + side * random.uniform(4, 18), ay - 6))

    def spawn_machine_floaters(self, dt: float) -> None:
        """De tempos em tempos cada máquina solta um '+O2', '+CALOR' ou '+AGUA' (como no mockup)."""
        period = 4.0
        t = self.renderer.machine_t          # relógio das máquinas: no déficit, os "+O2" saem mais espaçados
        dt = dt * self.state.power.factor
        for i, m in enumerate(self.state.machines):
            phase = (i * 1.37) % period
            if m.type.index is not None and (t - dt + phase) % period > (t + phase) % period:
                key = m.type.index
                self.floaters.add(f"+{C.INDEX_LABEL[key]}", (m.tx + 0.5) * C.TILE, m.ty * C.TILE - 30, C.INDEX_COLOR[key])

    # ---- desenho --------------------------------------------------------------
    def place_target(self) -> tuple[int, int] | None:
        """Onde a máquina na mão iria. A drill "gruda" no veio debaixo do mouse (canto de cima à esquerda);
        fora de veio, a drill não tem lugar (None)."""
        tile = self.mouse_tile()
        if self.placing != "drill":
            return tile
        vein = self.state.world.vein_at(*tile)
        return (vein.tx, vein.ty) if vein else None

    def hovered_machine(self):
        return self.state.machine_at_point(*self.mouse_world())

    def hint(self) -> str | None:
        state = self.state
        if self.placing == "drill" and self.place_target() is None:
            return "Coloque a drill em cima de um veio"
        if self.placing == "drone_station":
            tile = self.place_target()
            n = len(drones.drills_in_range(drones.Spot(*tile), state.drills)) if tile else 0
            return f"Clique para colocar · alcance {C.DRONE_RANGE} tiles · {n} drill{'s' if n != 1 else ''} · Esc cancela"
        if self.placing == "chest" and state.stations:
            inside = drones.delivers_to(state.stations, self.place_target())
            return "Clique para colocar · " + ("drones entregam aqui" if inside else "fora da entrega dos drones") \
                + " · Esc cancela"
        if self.placing:
            return "Clique para colocar · R gira · Esc cancela"
        machine = self.hovered_machine()
        if machine and machine.is_drill:
            label = C.RESOURCE_NAME[machine.resource]
            content = (f"Drill cheia: {machine.stored} {label}" if machine.full
                       else f"Drill: {machine.stored}/{C.DRILL_CAPACITY} {label}")
            if state.power.deficit and not machine.full:
                content += f" · ritmo {self.power_percent()}%"
            return content + (" · [E] coletar" if state.nearby_drill() is machine and machine.stored else "")
        if machine and machine.is_station:
            st = machine.station
            text = f"Estação: {len(st.drones)}/{C.STATION_DRONE_SLOTS} drones · buffer {st.stored}/{C.STATION_BUFFER}"
            if state.power.deficit:
                text += f" · ritmo {self.power_percent()}%"
            return text + (" · [E] abrir" if state.nearby_station() is machine else "")
        if machine and machine.is_chest:
            used = sum(1 for st in machine.storage.slots if st)
            near = state.nearby_chest() is machine
            return f"{machine.name or C.CHEST_DEFAULT_NAME} ({used}/{C.CHEST_SLOTS})" + (" · [E] abrir" if near else "")
        if machine:
            if state.power.deficit and energy.machine_use(machine.kind) > 0:     # no déficit: mostra o ritmo
                rhythm = f"Ritmo {self.power_percent()}%"
                return (f"{rhythm} · [Clique direito] desmontar" if state.can_dismantle(machine)
                        else f"{rhythm} (falta energia)")
            return "[Clique direito] desmontar" if state.can_dismantle(machine) else "Chegue mais perto pra desmontar"
        vein = state.world.vein_at(*self.mouse_tile())     # mouse em cima de um veio livre
        if vein:
            name = C.RESOURCE_NAME[vein.resource]
            unlocked = state.recipe_status("drill") != "locked"
            return f"Veio de {name} · " + ("coloque uma drill" if unlocked else "drill libera na Névoa")
        target = state.interaction()
        if target and target[0] == "terminal":
            return "[E] Ler terminal"
        if target and target[0] == "chest":
            return "[E] Abrir baú"
        if target and target[0] == "station":
            return "[E] Estação de drones" if target[1].station.drones else "[E] Estação: coloque drones"
        if target and target[0] == "drill" and target[1].stored:
            d = target[1]
            return f"[E] Coletar {d.stored} {C.RESOURCE_NAME[d.resource]}"
        if state.in_base_zone():
            return "[E] Fabricador" if self.t > 6 else "Paredes com cristais têm minério"
        tile = self.mouse_tile()
        if state.world.is_minable(*tile):
            return "Segure o clique para minerar" if state.can_mine(tile) else "Chegue mais perto pra minerar"
        return None

    def range_overlay(self) -> dict | None:
        """O que mostrar do alcance dos drones (render.draw_overlay):
        - colocando a estação: o círculo de 30 tiles, a área de entrega e as drills alcançadas;
        - mouse em cima de uma estação já colocada: o mesmo, pra ela;
        - colocando um baú: a área de entrega de cada estação e se o baú cairia dentro de alguma."""
        state = self.state
        if self.placing == "drone_station":
            tile = self.place_target()
            return {"range": [drones.Spot(*tile)]} if tile is not None else None
        if self.placing == "chest" and state.stations:
            tile = self.place_target()
            return {"delivery": state.stations, "chest": (tile, drones.delivers_to(state.stations, tile))}
        if not self.placing:
            machine = self.hovered_machine()
            if machine is not None and machine.is_station:
                return {"range": [machine]}
        return None

    def power_percent(self) -> int:
        """Ritmo atual das máquinas em % (arredondado pra baixo: 62,5% vira 62%)."""
        return int(self.state.power.factor * 100)

    def draw(self) -> None:
        state, canvas, ui = self.state, self.canvas, self.ui
        cam = self.cam
        ghost = None
        if self.placing and self.mode == "play":
            target = self.place_target()
            tile = target if target is not None else self.mouse_tile()
            ghost = (self.placing, tile, self.rotation, target is not None and state.can_place(self.placing, tile))
        overlay = self.range_overlay() if self.mode == "play" else None
        if self.zoom == 1.0:
            self.renderer.draw(canvas, state, cam, self.t, ghost, overlay)
        else:   # o mundo vai numa visão de 960×540/zoom e é esticado sem suavizar (pixel art continua pixel)
            if self._world_view is None or self._world_view.get_size() != self.view_size:
                self._world_view = pygame.Surface(self.view_size, 0, canvas)
            self.renderer.draw(self._world_view, state, cam, self.t, ghost, overlay)
            pygame.transform.scale(self._world_view, canvas.get_size(), canvas)

        critical = state.o2 < C.O2_LOW and not state.fainted
        if critical:
            pulse = 0.5 + 0.12 * math.sin(self.t * 6.3)
            self.red_vignette.set_alpha(int(255 * pulse))
            canvas.blit(self.red_vignette, (0, 0))

        # camada 1: HUD e textos flutuantes
        ui.begin()
        icons = {r: self.renderer.surface(f"icon_{r}", lambda r=r: art.icon(r))[0] for r in C.RESOURCES}
        if self.mode == "play":
            ui.draw_chest_labels(self.labeled_chests(), cam, self.zoom, icons)
        ui.draw_floaters(self.floaters, cam, self.zoom)
        if critical:
            ui.draw_o2_critical(state, self.t, cam)
        ui.draw_hud(state, self.t, self.hint() if self.mode == "play" else None, icons)
        ui.draw_hotbar(state.inventory, self.hotbar_selected, self.renderer.item_icon)
        if not critical:   # com O₂ crítico o aviso grande ocupa essa área (e o foco é voltar pra base)
            ui.draw_objectives(self.objectives.lines(state))
        if self.saved_notice > 0:
            draw_saved_notice(ui, self.saved_notice)
        if self.toast_time > 0 and self.toast:
            ui.draw_toast(self.toast, min(1.0, self.toast_time / 0.3))
        if self.banner_time < BANNER_TIME:
            alpha = min(1.0, self.banner_time / BANNER_FADE_IN, (BANNER_TIME - self.banner_time) / BANNER_FADE_OUT)
            ui.draw_banner(self.banner_stage, alpha)
        ui.finish(canvas)

        # camada 2: menus e telas por cima do HUD
        mouse_ui = (self.mouse[0] / 2, self.mouse[1] / 2)
        ui.begin()
        if self.mode == "fabricator":
            preview = self.renderer.machine_preview
            ui.draw_fabricator(state, self.fab, preview, self.t)
        elif self.mode == "terminal":
            ui.draw_terminal(self.terminal_index, self.t)
        elif self.mode == "end":
            ui.draw_end(state, self.t)
        elif self.mode == "pause":
            ui.draw_pause(self.pause_screen, self.pause_selected, self.settings, viewport_label(self.zoom))
        elif self.mode in INVENTORY_MODES:
            side = self.open_chest or self.open_station
            status = self.station_status() if self.open_station is not None else ""
            station_info = self.hovered_slot_label(mouse_ui) if self.open_station is not None else None
            ui.draw_inventory(state.inventory, side, self.hotbar_selected, self.renderer.item_icon, mouse_ui,
                              self.t, self.name_edit, status, station_info)
        if self.notice_time > 0 and self.mode not in INVENTORY_MODES:   # por cima do fabricador também
            ui.draw_notice(self.notice, min(1.0, self.notice_time / 0.4))
        if state.fainted:
            ui.draw_faint(state)
        if self.mode not in INVENTORY_MODES:
            ui.draw_cursor(*mouse_ui)
        ui.finish(canvas)

        # camada 3 (só no inventário): pilha na mão ou tooltip, aviso e cursor, por cima dos ícones dos slots
        if self.mode in INVENTORY_MODES:
            ui.begin()
            # na estação a dica vai numa linha do painel (station_info), não flutuando por cima do texto
            label = None if self.name_edit is not None or self.open_station is not None \
                else self.hovered_slot_label(mouse_ui)
            ui.draw_held_and_tooltip(self.held, label, mouse_ui, self.renderer.item_icon)
            if self.notice_time > 0:
                ui.draw_notice(self.notice, min(1.0, self.notice_time / 0.4), ui.notice_y)
            ui.draw_cursor(*mouse_ui)
            ui.finish(canvas)

        self.present()

    def screenshot(self, path: str) -> None:
        pygame.image.save(self.canvas, path)

    # ---- save/load e tela de título (game/save.py, game/title.py) --------------
    def open_title(self) -> None:
        """Vai pra tela de título. Lê o save do disco (se tiver um válido, aparece "Continuar")."""
        self.title.open(save.load_game())
        self.mode = "title"
        self.placing = None
        self.mouse_held = False
        self.keys_down.clear()
        self.audio.set_alarm(False)          # nada de alarme, zumbido ou drill tocando no menu
        self.audio.set_hum(0.0)
        self.audio.set_drill_loops([])
        self.audio.set_drone_loops([])
        self.audio.set_solar_hum(0.0)
        self.audio.duck_ambient(1.0)
        if self.audio.ambient_key != "dead":
            self.audio.start_ambient("dead")

    def on_title_action(self, action: str | None) -> None:
        if action == "continue":
            self.start_game(self.title.saved)
        elif action == "new":
            self.start_game(save.new_state())
            self.save_game(notify=False)     # o save antigo (se existia) é substituído na hora
        elif action == "quit":
            self.quit_game()

    def start_game(self, state: GameState) -> None:
        """Começa a jogar com `state` (novo ou carregado): zera tudo que é do App e não do jogo."""
        self.state = state
        self.objectives = ObjectiveTracker(state)
        self.floaters = FloatingTexts()
        self.renderer.particles.clear()
        self.placing, self.rotation, self.mouse_held = None, 0, False
        self.hotbar_selected, self.held, self.notice_time = 0, None, 0.0
        self.open_chest = self.renderer.open_chest = None
        self.open_station, self.name_edit = None, None
        self.banner_stage, self.banner_time, self.end_timer = state.stage, 0.0, None
        self.drills_near.clear()
        self.drill_full_last.clear()
        self.autosave_timer, self.saved_notice = 0.0, 0.0
        self.mode = "play"
        self.audio.play("ui_close")
        if self.audio.ambient_key != stage_key(state.stage):
            self.audio.start_ambient(stage_key(state.stage))

    def save_game(self, notify: bool = True) -> bool:
        """Salva agora. `notify` mostra o "Jogo salvo" no HUD e toca o som de save."""
        ok = save.write_save(self.state)
        self.autosave_timer = 0.0
        if ok and notify:
            self.saved_notice = C.SAVED_NOTICE_TIME
            self.audio.play("save")
        return ok

    def update_autosave(self, dt: float) -> None:
        """Autosave a cada AUTOSAVE_INTERVAL de jogo. Só conta jogando (pausa e menus não contam)."""
        self.saved_notice = max(0.0, self.saved_notice - dt)
        if self.mode != "play":
            return
        self.autosave_timer += dt
        if self.autosave_timer >= C.AUTOSAVE_INTERVAL:
            self.save_game()

    def quit_game(self) -> None:
        """Fecha o jogo (janela ou "Sair"), salvando antes se tiver um jogo rolando."""
        if self.mode != "title":
            self.save_game(notify=False)
        self.running = False

    def draw_title(self) -> None:
        self.title.draw(self.canvas, self.t, self.mouse)
        self.present()
