"""O App: abre a janela, roda o game loop e liga input, regras, desenho e som.

Game loop (60 vezes por segundo):
    1. handle_events()  lê teclado/mouse e decide o que cada tecla faz no modo atual
    2. update(dt)       manda os controles pro GameState e reage aos eventos dele
    3. draw()           desenha o mundo numa tela de 960×540, estica pra janela e põe a UI por cima

Tela e zoom (game/viewport.py): o mundo é desenhado numa "visão" de 960×540 / zoom px e esticado
pra 960×540 (sem suavizar). A tela de 960×540 é esticada pra janela mantendo 16:9 (na tela cheia
sobra tarja preta se o monitor não for 16:9). A UI (HUD e menus) é desenhada depois, direto na
janela, no tamanho escolhido em Opções > Interface (Grande/Média/Pequena): ela não muda com o zoom
e o mundo não muda com ela. F11 ou Alt+Enter alternam a tela cheia; +/- ou Ctrl+rodinha mudam o zoom.

Modos de tela: "play" (jogando), "fabricator" (menu de receitas),
"terminal" (lendo um log), "inventory" (Tab: abas Inventário, Fabricar em campo e LOGs), "chest" (baú aberto com E), "drill" (drill aberta com E;
Shift+E coleta direto), "station" (estação com E),
"crate" (caixa de saque de um destroço, só tirar), "map" (mapa grande do scanner, M),
"pause" (menu do Esc) e "end" (tela de fim do MVP).
Em "pause" e "end" o mundo fica congelado (O₂, máquinas e Ti param). No fabricador, no terminal,
no inventário e no baú o mundo continua (o player só fica parado), como em Core Keeper e Planet Crafter.
O jogo abre em "title" (tela de título, game/title.py); o save/load fica em game/save.py.
"""

import math
from pathlib import Path
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
from game import worlds
from game import viewport
from game.assets import Sprites
from game.audio import Audio
from game.equipment import is_equipment
from game.fabricator import FabMenu, field_menu
from game.inventory import Stack
from game.map_view import MapView
from game.objectives import ObjectiveTracker
from game.rain import rain_level
from game.render import Renderer, art_key, stage_key
from game.surfaces import opaque
from game.systems import Controls, GameState
from game.textedit import TextField
from game.ui import item_name, submerged_notice
from game.title import TitleScreen, draw_saved_notice
from game.ui import TAB_CRAFT, TAB_INVENTORY, TAB_LOGS, UI, FloatingTexts

MOVE_KEYS = {
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
}
NUMBER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8]
INVENTORY_MODES = ("inventory", "chest", "drill", "station", "crate")
PANEL_MODES = ("chest", "drill", "station", "crate")          # dois painéis: clique transfere pro outro lado (Planet Crafter)
ZOOM_IN_KEYS = (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)     # "=" é a tecla do "+" sem Shift
ZOOM_OUT_KEYS = (pygame.K_MINUS, pygame.K_KP_MINUS)
BANNER_TIME = 3.5          # banner de estágio: entra em 0,4 s, fica, sai em 0,8 s
BANNER_FADE_IN, BANNER_FADE_OUT = 0.4, 0.8
SKY_CLEAR_DELAY = 5.0   # s depois do stage_up do Árido
END_SCREEN_DELAY = 4.5
FOOTSTEP_INTERVAL = 0.3
CRATER_ICE_HINT = "Gelo · derrete com o calor"   # v0.4 M2: no lugar do "[E] Descer" com a cratera tampada
CRATER_THAW_TEXT = "O gelo da cratera está cedendo"   # v0.4 M3.1: aviso nas etapas 1–3 do degelo
CRATER_OPEN_TEXT = "A cratera abriu · desça [E]"      # ...e na etapa 4
FUMAROLE_WAKE_TEXT = "Uma fumarola acordou com o calor"   # fumarola acordando na tela


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
        icon = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
        if icon.exists():                                # o "H" sobre a poeira (tools/dev/mac_icon.py): no macOS
            pygame.display.set_icon(pygame.image.load(icon))   # vira o ícone do Dock, no lugar da cobrinha do pygame
        self.scale = scale or pick_scale()               # escala inteira da janela (fora da tela cheia)
        self.settings = settings.load()
        self.window = self.open_window(self.settings["fullscreen"])
        pygame.display.set_caption("Hesper · v0.4")
        pygame.mouse.set_visible(False)
        # Tela interna SEM canal alfa, com máscaras explícitas. Sem isso, no macOS (driver Cocoa)
        # o Surface herda o formato da janela, que TEM alfa: os blits gravam alfa 0/255 misturado
        # e o macOS mostra retângulos pretos em volta de sprites (bug do playtest 1).
        self.canvas = opaque((C.SCREEN_W, C.SCREEN_H))
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
        self.mouse = (C.SCREEN_W // 2, C.SCREEN_H // 2)   # em pixels da tela interna (960×540): mundo
        self.mouse_window = (self.window.get_width() // 2, self.window.get_height() // 2)   # px da janela
        self.mouse_held = False
        self.placing: str | None = None                   # máquina sendo posicionada (a do slot selecionado)
        self.hotbar_selected = 0                          # slot da hotbar escolhido (0 a 7, teclas 1–8)
        self.held: Stack | None = None                    # pilha presa no cursor na tela de inventário
        self.open_chest = None                            # baú aberto (Machine), no modo "chest"
        self.open_station = None                          # estação aberta (Machine), no modo "station"
        self.open_drill = None                            # drill aberta (Machine), no modo "drill"
        self.open_crate = None                            # caixa de saque aberta (Crate), no modo "crate"
        self.after_terminal = None                        # registro de bordo lido ao abrir a caixa: depois abre ela
        self.blueprint_notice: str | None = None          # projeto do aviso "PROJETO: ..." (Marco 3)
        self.blueprint_notice_time = 0.0
        self.blueprint_duck = 0.0                         # s com o ambiente abaixado (projeto encontrado)
        self.crate_open_t = -10.0                         # quando tocou o crate_open (o blueprint_found vem 0,4 s depois)
        self.map_sound_t = -10.0                          # M: no máximo 1 som de abrir a cada 0,3 s
        # mapa aberto (M): câmera, camada e filtros. Zoom e filtros vêm do settings.json (preferência do jogador)
        self.map_view = MapView(self.settings["map_zoom"], self.settings["map_hidden"])
        self.name_edit: TextField | None = None           # editando o nome do baú (texto digitado)
        self.notice: str | None = None                    # aviso curto ("Inventário cheio")
        self.notice_time = 0.0
        self.rotation = 0
        self.fab = FabMenu()            # aba, seleção e rolagem do fabricador (game/fabricator.py)
        self.terminal_index = 0
        self.inv_tab = TAB_INVENTORY    # Tab: Inventário / Fabricar (em campo) / LOGs
        self.field = field_menu()       # aba Fabricar do Tab: seleção do kit de campo (C.FIELD_RECIPES)
        self.log_selected = 0           # aba LOGs: linha escolhida (posição na cronologia) e a 1ª visível
        self.log_first = 0
        self.banner_stage = 1
        self.banner_time = 0.0
        self.end_timer: float | None = None
        self.footstep_timer = 0.0
        self.footstep_side = 0
        self.drills_near: set[tuple[int, int]] = set()          # drills cheias perto do player agora
        self.drill_full_last: dict[tuple[int, int], float] = {}  # quando avisou "cheia" pela última vez
        self.drill_dust_timer = 0.0
        self.pause_screen = "main"      # "main", "volumes" ou "controls"
        self.controls_page = 0          # página da tela de Controles (no Grande ela não cabe numa só)
        self.pause_selected = 0
        self.dragging_slider: int | None = None
        self.zoom = self.settings["zoom"]
        self.toast: str | None = None   # aviso neutro rápido ("Zoom 1,5×")
        self.thaw_notice: str | None = None   # v0.4 M3.1: "O gelo da cratera está cedendo" (pílula no estilo RAJADA)
        self.thaw_notice_time = 0.0
        self.submerged_kinds: list[str] = []  # v0.4 M3.4: máquinas do aviso "submersa" que está na tela (agrupa)
        self.toast_time = 0.0
        self.audio.set_mix(**settings.mix(self.settings))
        self.audio.start_ambient(self.ambient_want())
        # save/load e tela de título (game/save.py, game/title.py)
        self.autosave_timer = 0.0       # segundos jogando (modo "play") desde o último save
        self.saved_notice = 0.0         # quanto falta do aviso "Jogo salvo" no HUD
        self.title = TitleScreen(self.ui, self.renderer, self.audio.play)
        self.slot: int | None = None    # espaço do mundo jogando agora (1–3, game/worlds.py)
        self.text_input = False         # digitação do SDL ligada (sync_text_input)
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

    def show_thaw_notice(self, text: str) -> None:
        """Aviso do degelo (v0.4 M3.1). "A cratera abriu" não é trocado por uma fumarola acordando logo depois."""
        if self.thaw_notice == CRATER_OPEN_TEXT and self.thaw_notice_time > 0 and text == FUMAROLE_WAKE_TEXT:
            return
        self.thaw_notice, self.thaw_notice_time = text, C.THAW_CRATER_NOTICE_S

    def vent_on_screen(self, index: int) -> bool:
        """A fumarola `index` (geo.vents) aparece na tela agora? (na superfície, pelo sprite com a câmera atual)"""
        state = self.state
        geo = getattr(state.active, "geo", None)
        if geo is None or not 0 <= index < len(geo.vents):
            return False
        f = geo.vents[index]
        return any(v[0] is f for v in self.renderer.visible_formations(state, self.cam))

    def show_toast(self, text: str, seconds: float = C.ZOOM_TOAST_TIME) -> None:
        self.toast, self.toast_time = text, seconds

    @property
    def view_size(self) -> tuple[int, int]:
        """Quanto do mundo (px) aparece na tela com o zoom atual."""
        return viewport.view_size(self.zoom)

    def window_to_canvas(self, pos: tuple[int, int]) -> tuple[int, int]:
        return viewport.window_to_canvas(pos, self.window.get_size())

    # ---- tamanho da interface ----------------------------------------------------
    @property
    def mouse_ui(self) -> tuple[float, float]:
        """O mouse em px da UI (hit-test de botões, slots, abas, sliders), no tamanho de interface atual."""
        return viewport.window_to_ui(self.mouse_window, self.window.get_size(), self.settings["ui_size"])

    def apply_ui_layout(self) -> None:
        """Passa pra UI onde ela fica na janela e o tamanho lógico (muda com a janela e com a opção)."""
        self.ui.set_layout(*viewport.ui_layout(self.window.get_size(), self.settings["ui_size"]))

    def set_ui_size(self, ui_size: str) -> None:
        self.settings = settings.clean({**self.settings, "ui_size": ui_size})
        settings.save(self.settings)
        self.apply_ui_layout()

    def ui_size_step(self, step: int) -> None:
        sizes = viewport.UI_SIZES
        self.set_ui_size(sizes[(sizes.index(self.settings["ui_size"]) + step) % len(sizes)])
        self.audio.play("ui_click")

    @property
    def frame(self) -> pygame.Surface:
        """A área de jogo na janela (sem a tarja), com mundo + UI: o que aparece pro jogador."""
        return self.window.subsurface(viewport.letterbox(self.window.get_size()))

    def present(self) -> None:
        """Estica o mundo (960×540) pra janela mantendo 16:9 (tarja preta no que sobrar), sem suavizar.
        A UI vem depois, por cima, direto na janela (ui.finish)."""
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
            elif self.mode == "title" and event.type == pygame.TEXTINPUT:
                self.title.on_text(event.text)            # Novo mundo: nome e seed
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
                self.mouse_window = event.pos
                self.mouse = self.window_to_canvas(event.pos)
                if self.mode == "map":
                    self.map_view.move_press(self.mouse_ui)       # passou de 3 px com o botão apertado: arrasta
                elif self.mode == "pause":
                    self.pause_hover()
                elif self.mode == "title":
                    self.title.hover(*self.mouse_ui)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_window = event.pos
                self.mouse = self.window_to_canvas(event.pos)
                self.on_click(event.button)
            elif event.type == pygame.MOUSEWHEEL and self.mode == "map":
                self.map_zoom(1 if event.y > 0 else -1, self.mouse_ui)   # zoom do mapa (com ou sem Ctrl)
            elif event.type == pygame.MOUSEWHEEL and self.mode != "title" and self.zoom_modifier():
                self.zoom_step(1 if event.y > 0 else -1)        # Ctrl+rodinha pra cima = aproxima
            elif event.type == pygame.MOUSEWHEEL and self.mode == "inventory" and self.inv_tab == TAB_LOGS:
                self.scroll_logs(-1 if event.y > 0 else 1)      # rodinha rola a aba LOGs (se não couber)
            elif event.type == pygame.MOUSEWHEEL and self.mode == "fabricator":
                self.fab.scroll(-1 if event.y > 0 else 1)       # rodinha rola a lista de receitas
            elif event.type == pygame.MOUSEWHEEL and self.mode == "play" and not self.state.fainted \
                    and self.name_edit is None:
                # rodinha pra baixo = próximo slot (y < 0), pra cima = anterior
                self.select_hotbar((self.hotbar_selected + (1 if event.y < 0 else -1)) % C.HOTBAR_SLOTS)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_held = False
                self.map_view.end_drag()
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
        if self.mode == "map" and key in ZOOM_IN_KEYS + ZOOM_OUT_KEYS:   # mapa aberto: +/- é o zoom do mapa
            self.map_zoom(1 if key in ZOOM_IN_KEYS else -1)
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
        elif key == pygame.K_F3:
            state.toggle_fast()
        elif key == pygame.K_F4 and C.DEBUG_MELT_CRATER:   # debug (v0.4 M2): derrete o gelo da cratera na hora
            state.debug_melt_crater()
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
                self.try_craft(self.fab.current, batch=self.craft_batch(self.fab))   # ×5 ou Shift: até 5
        elif self.mode == "terminal":
            if key in (pygame.K_e, pygame.K_ESCAPE, pygame.K_RETURN):
                self.close_terminal()
        elif self.mode == "map":
            if key in (pygame.K_m, pygame.K_ESCAPE, pygame.K_TAB):
                self.close_map()
            elif key in (pygame.K_q, pygame.K_e):                 # troca a camada (a caverna só depois de descer)
                if self.map_view.cycle_layer(state, -1 if key == pygame.K_q else 1):
                    self.audio.play("ui_click")
            elif key == pygame.K_c:                                # centra em você (ou na rampa da outra camada)
                self.map_view.show_layer(state, self.map_view.layer)
        elif self.mode in INVENTORY_MODES:
            if key in (pygame.K_TAB, pygame.K_ESCAPE, pygame.K_e):
                self.close_inventory()
            elif self.mode == "inventory" and key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT):
                step = -1 if key in (pygame.K_a, pygame.K_LEFT) else 1
                self.switch_inv_tab((self.inv_tab + step) % len(UI.INV_TAB_LABELS))   # dá a volta
            elif self.mode == "inventory" and self.inv_tab == TAB_LOGS:
                self.on_logs_key(key)
            elif self.mode == "inventory" and self.inv_tab == TAB_CRAFT:
                self.on_field_key(key)
        elif self.mode == "end":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self.set_mode("play")
        else:  # play
            if key == pygame.K_e:
                target = self.e_target()          # o do mouse (no alcance) ou o mais perto
                if target and target[0] == "ramp":
                    state.start_ramp()                    # cratera/rampa: desce ou sobe (fade)
                elif target and target[0] == "terminal":
                    state.read_terminal(target[1])
                    self.terminal_index = target[1]
                    self.mode = "terminal"
                elif target and target[0] == "wreck_log":          # terminal do módulo da colônia
                    self.show_log(target[1].log)
                elif target and target[0] == "crate":
                    self.open_loot(target[1])
                elif target and target[0] == "container":          # v0.4 M3.2: lacrado, só a dica de lore
                    self.show_toast(C.CONTAINER_LORE, C.CONTAINER_LORE_TIME)
                elif target and target[0] == "drill" and self.shift_held():
                    state.collect(target[1])              # Shift+E: coleta tudo sem abrir o painel
                elif target and target[0] == "drill":
                    self.open_drill = target[1]
                    self.placing = None
                    self.set_mode("drill")
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
                self.inv_tab = TAB_INVENTORY         # o Tab sempre abre na aba Inventário
                self.set_mode("inventory")
            elif key == pygame.K_m:
                self.open_map()
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

    # ---- destroços e scanner (Marco 3) --------------------------------------------
    def show_log(self, log: int, after=None) -> None:
        """Abre a tela de leitura do LOG `log`. `after` = caixa pra abrir quando fechar (registro de bordo)."""
        self.state.read_log(log)
        self.terminal_index = log
        self.after_terminal = after
        self.placing = None
        self.mode = "terminal"
        self.mouse_held = False

    def close_terminal(self) -> None:
        crate, self.after_terminal = self.after_terminal, None
        if crate == "logs":                      # aberto pela aba LOGs do Tab: volta pra ela
            self.mode = "inventory"
            self.mouse_held = False
            return
        if crate is not None:
            self.mode = "play"
            self.show_crate(crate)
        else:
            self.set_mode("play")

    def open_loot(self, crate) -> None:
        """E na caixa: abre (o projeto sai sozinho). Nave e sonda: na 1ª vez, o registro de bordo aparece
        antes (a nave e a sonda não têm terminal; o LOG vem com a caixa)."""
        first = not crate.opened
        self.state.open_crate(crate)
        log = crate.wreck.log
        if first and log is not None and crate.wreck.terminal is None and log not in self.state.logs_read:
            self.show_log(log, after=crate)
        else:
            self.show_crate(crate)

    def show_crate(self, crate) -> None:
        self.open_crate = crate
        self.placing = None
        self.mode = "crate"
        self.mouse_held = False

    # ---- abas do Tab: Fabricar (em campo) e LOGs ---------------------------------------
    def switch_inv_tab(self, tab: int) -> None:
        """Troca a aba do Tab. Saindo do Inventário (Fabricar ou LOGs, sem slots), a pilha da mão volta pro
        inventário antes (sem lugar: não troca e avisa)."""
        if tab == self.inv_tab:
            return
        if tab != TAB_INVENTORY and not self.stash_held():
            self.show_notice("Sem espaço pro item na mão")
            return
        self.inv_tab = tab
        if tab == TAB_LOGS:                      # começa no 1º NOVO (ou no 1º lido)
            entries = self.state.log_entries()
            pick = next((i for i, e in enumerate(entries) if e[3]), None)
            if pick is None:
                pick = next((i for i, e in enumerate(entries) if e[2]), 0)
            self.log_selected = pick
            self.scroll_logs(0)
        self.audio.play("ui_click")

    def on_field_key(self, key: int) -> None:
        """Aba Fabricar: W/S escolhem a receita, Enter/Espaço fabricam (Shift: até 5), igual ao fabricador."""
        if key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
            self.field.move(-1 if key in (pygame.K_w, pygame.K_UP) else 1)
            self.audio.play("ui_click")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and self.field.current:
            self.try_craft(self.field.current, batch=self.craft_batch(self.field), field=True)

    def craft_batch(self, menu: FabMenu) -> bool:
        """Fabrica em lote (até C.CRAFT_BATCH)? Sim com o seletor em ×5 ou com o Shift segurado."""
        return menu.batch > 1 or self.shift_held()

    def on_craft_click(self, pos, menu: FabMenu, field: bool = False) -> bool:
        """Clique na lista + detalhe (fabricador ou aba Fabricar): FABRICAR fabrica (×5 ou Shift: até 5), ×1/×5
        trocam o lote e a linha escolhe a receita. True se usou o clique."""
        ui = self.ui
        kind = next((k for rect, k in ui.fabricator_buttons if rect.collidepoint(pos)), None)
        if kind is not None:
            self.try_craft(kind, batch=self.craft_batch(menu), field=field)
            return True
        amount = next((n for rect, n in ui.fabricator_batch if rect.collidepoint(pos)), None)
        if amount is not None:
            if menu.set_batch(amount):
                self.audio.play("ui_click")
            return True
        kind = next((k for rect, k in ui.fabricator_rows if rect.collidepoint(pos)), None)
        if kind is not None:
            if kind != menu.current:
                self.audio.play("ui_click")
            menu.select(kind)
            return True
        return False

    def on_field_click(self, pos) -> None:
        """Clique na aba Fabricar: igual ao fabricador (lista, ×1/×5 e FABRICAR), só com o inventário."""
        self.on_craft_click(pos, self.field, field=True)

    def on_logs_key(self, key: int) -> None:
        """W/S escolhem a linha (pulando os não achados), Enter/Espaço leem de novo."""
        entries = self.state.log_entries()
        if key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
            step = -1 if key in (pygame.K_w, pygame.K_UP) else 1
            i = self.log_selected + step
            while 0 <= i < len(entries) and not entries[i][2]:
                i += step
            if 0 <= i < len(entries):
                self.log_selected = i
                self.scroll_logs(0)
                self.audio.play("ui_click")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            log, _, read, _ = entries[self.log_selected]
            if read:
                self.reopen_log(log)

    def scroll_logs(self, step: int) -> None:
        """Rola a aba LOGs (rodinha) e mantém a linha escolhida visível (só rola quando não cabem todas)."""
        rows, n = self.ui.log_visible, len(C.LOGS)
        self.log_first = max(0, min(n - rows, self.log_first + step))
        if self.log_selected < self.log_first:
            self.log_first = self.log_selected
        elif self.log_selected >= self.log_first + rows:
            self.log_first = self.log_selected - rows + 1

    def reopen_log(self, log: int) -> None:
        """Clique num LOG lido da aba: a mesma tela de leitura do terminal; fechar volta pra aba LOGs."""
        if self.state.reread_log(log) is None:
            return
        self.log_selected = C.LOG_ORDER.index(log)
        self.terminal_index = log
        self.after_terminal = "logs"
        self.mode = "terminal"
        self.mouse_held = False

    def on_logs_click(self, pos) -> bool:
        """Clique nas abas do Tab, na aba Fabricar ou numa linha da aba LOGs. Devolve True se usou o clique."""
        tab = next((i for rect, i in self.ui.inv_tab_rects if rect.collidepoint(pos)), None)
        if tab is not None:
            self.switch_inv_tab(tab)
            return True
        if self.inv_tab == TAB_CRAFT:
            self.on_field_click(pos)
            return True
        if self.inv_tab != TAB_LOGS:
            return False
        log = next((lg for rect, lg in self.ui.log_rows if rect.collidepoint(pos)), None)
        if log is not None:
            self.reopen_log(log)
        return True

    def open_map(self) -> None:
        if not self.state.has_scanner:
            if "scanner" in self.state.blueprints:
                self.show_notice("Fabrique e equipe o scanner de navegação [Tab]")
            else:
                self.show_notice("Sem scanner de navegação: o projeto está num destroço")
            return
        self.placing = None
        if self.t - self.map_sound_t >= C.MAP_OPEN_COOLDOWN:
            self.audio.play("map_open")
            self.map_sound_t = self.t
        self.mode = "map"
        self.mouse_held = False
        self.map_view.open(self.state)                     # sempre abre centrado em você, no último zoom
        self.ui.map_rect = self.ui.map_close_rect = self.ui.map_area = None   # até o 1º desenho, clique nenhum fecha
        self.ui.map_buttons, self.ui.map_chips, self.ui.map_layer_rects = [], [], []

    def close_map(self) -> None:
        self.map_view.end_drag()
        self.set_mode("play")

    def save_map_prefs(self) -> None:
        """Último zoom e filtros do mapa: preferência do jogador (settings.json), não vai no save."""
        view = self.map_view
        self.settings = settings.clean({**self.settings, "map_zoom": view.zoom, "map_hidden": sorted(view.hidden)})
        settings.save(self.settings)

    def map_zoom(self, step: int, mouse=None) -> None:
        """Zoom do mapa: ancorado no tile debaixo do mouse (rodinha) ou no centro (teclas e botões)."""
        area = self.ui.map_area
        anchor = None
        if mouse is not None and area is not None and area.collidepoint(mouse):
            anchor = (mouse[0] - area.x, mouse[1] - area.y)
        if self.map_view.zoom_step(step, anchor):
            self.save_map_prefs()

    def on_map_click(self) -> None:
        """Mapa aberto: FECHAR e clique fora da janela fecham; Superfície | Caverna troca a camada; + / − /
        centralizar; um chip liga/desliga o filtro; na área, o botão apertado pode virar arrasto (3 px).
        Nada disso chega no jogo."""
        ui, view = self.ui, self.map_view
        pos = self.mouse_ui
        if ui.map_close_rect is not None and ui.map_close_rect.collidepoint(pos):
            self.close_map()
            return
        if ui.map_rect is not None and not ui.map_rect.collidepoint(pos):
            self.close_map()
            return
        for rect, key in ui.map_layer_rects:
            if rect.collidepoint(pos):
                if key != view.layer and view.show_layer(self.state, key):
                    self.audio.play("ui_click")
                return
        for rect, action in ui.map_buttons:
            if rect.collidepoint(pos):
                if action == "center":
                    view.show_layer(self.state, view.layer)
                else:
                    self.map_zoom(1 if action == "zoom_in" else -1)
                self.audio.play("ui_click")
                return
        for rect, category in ui.map_chips:
            if rect.collidepoint(pos):
                view.toggle(category)
                self.save_map_prefs()
                self.audio.play("ui_click")
                return
        if ui.map_area is not None and ui.map_area.collidepoint(pos):
            view.start_press(pos)

    def show_notice(self, text: str) -> None:
        self.notice, self.notice_time = text, C.NOTICE_TIME

    def other_side(self, inv):
        """Shift+clique: o inventário do outro lado (player <-> baú/drill). None se só o Tab estiver aberto."""
        side = self.open_chest or self.open_drill
        if side is None:
            return None
        return side.storage if inv is self.state.inventory else self.state.inventory

    def shift_held(self) -> bool:
        return bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) or bool({pygame.K_LSHIFT, pygame.K_RSHIFT} & self.keys_down)

    def on_inventory_click(self, button: int) -> None:
        """Clique na tela de inventário (Tab): pega e solta pilhas (a "mão" é self.held).
        Com baú ou estação aberta, o clique transfere pro outro lado (on_panel_click)."""
        ux, uy = self.mouse_ui
        if self.mode in PANEL_MODES:
            self.on_panel_click(button, (ux, uy))
            return
        if self.mode == "inventory" and button == 1 and self.on_logs_click((ux, uy)):
            return
        if self.mode == "inventory" and self.inv_tab != TAB_INVENTORY:   # Fabricar e LOGs: sem slots
            return
        if self.mode == "inventory" and self.on_equip_click(button, (ux, uy)):
            return
        hit = next(((inv, i) for rect, inv, i in self.ui.slot_rects if rect.collidepoint(ux, uy)), None)
        if hit is None:
            return
        inv, i = hit
        stack = inv.slots[i]
        if (self.mode == "inventory" and button == 1 and self.held is None and stack is not None
                and is_equipment(stack.item) and inv is self.state.inventory):
            self.state.equip_from(i)                      # clique num equipamento: vai pro slot do traje
            return
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

    def on_equip_click(self, button: int, pos) -> bool:
        """Clique num slot do traje (Tab): mão vazia tira o equipamento; com o item certo na mão, encaixa."""
        kind = next((k for rect, k in self.ui.equip_rects if rect.collidepoint(pos)), None)
        if kind is None:
            return False
        state = self.state
        if self.held is not None:
            if self.held.item != kind:
                self.show_notice(f"Só {item_name(kind).lower()} nesse slot")
                return True
            self.held.count -= 1
            item = self.held.item
            if self.held.count == 0:
                self.held = None
            old = state.equip_item(item)
            if old is not None and state.inventory.add(old, 1):
                self.held = Stack(old, 1) if self.held is None else Stack(old, self.held.count + 1)
        elif button == 1:
            state.unequip(kind)
        return True

    def on_panel_click(self, button: int, pos: tuple[float, float]) -> None:
        """Baú ou estação aberta (estilo Planet Crafter): esquerdo manda a pilha inteira pro outro
        lado, direito manda 1, Shift+esquerdo manda todas as pilhas daquele item (só no baú)."""
        ui, state = self.ui, self.state
        if self.name_edit is not None:                   # clicou fora do campo: confirma o nome
            if ui.name_rect is not None and ui.name_rect.collidepoint(pos):
                return
            self.finish_name_edit(confirm=True)
        if button == 1 and self.on_logistics_click(pos):  # seção DRONES do baú/drill (Envia/Recebe/Lote)
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
        if self.open_crate is not None:                  # caixa de saque: só tirar
            hit = next(((inv, i) for rect, inv, i in ui.slot_rects if rect.collidepoint(pos)), None)
            if hit is None or hit[0].slots[hit[1]] is None:
                return
            if hit[0] is self.open_crate.storage:
                if state.crate_take(self.open_crate, hit[1], amount):
                    self.audio.play("inv_move")
            else:
                self.show_notice("A caixa só deixa tirar")
            return
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
        if self.open_drill is not None:                  # a drill só produz: só dá pra tirar dela
            drill = self.open_drill
            if inv is drill.storage:
                if button == 1 and self.shift_held():
                    moved = state.drill_take(drill)
                else:
                    moved = state.drill_take(drill, i, amount)
                if moved:
                    self.audio.play("inv_move")
            else:
                self.show_notice("A drill só produz: não guarda nada")
            return
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
        elif action == "take_drill" and self.open_drill is not None:
            moved = state.collect(self.open_drill)
        elif action == "take_buffer" and self.open_station is not None:
            moved = state.collect_station(self.open_station)
        elif action == "take_crate" and self.open_crate is not None:
            moved = state.crate_take(self.open_crate)
        elif action == "crate_log" and self.open_crate is not None:
            crate = self.open_crate
            self.open_crate = None
            self.show_log(crate.wreck.log, after=crate)
            return
        if moved:
            self.audio.play("inv_move")

    # ---- nome do baú ------------------------------------------------------------
    def start_name_edit(self) -> None:
        name = self.open_chest.name or C.CHEST_DEFAULT_NAME
        self.name_edit = TextField(name, C.CHEST_NAME_MAX)
        self.keys_down.clear()                           # nada de WASD "preso" enquanto digita
        self.sync_text_input()
        self.audio.play("ui_click")

    def finish_name_edit(self, confirm: bool) -> None:
        if self.name_edit is None:
            return
        if confirm and self.open_chest is not None:
            self.state.rename_chest(self.open_chest, self.name_edit.text)
        self.name_edit = None
        self.sync_text_input()
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
            if is_equipment(hovered.item) and self.mode == "inventory":
                return f"{item_name(hovered.item)} · {hovered.count} · clique equipa"
            return f"{item_name(hovered.item)} · {hovered.count}"
        if self.mode == "inventory":
            kind = next((k for rect, k in ui.equip_rects if rect.collidepoint(mouse_ui)), None)
            if kind is not None:
                if self.state.equipment.has(kind):
                    return f"{item_name(kind)} · equipado (clique tira)"
                return f"Slot do {item_name(kind).lower()} (vazio)"
        if self.open_station is not None:
            st = self.open_station.station
            bay = next((slot for rect, slot in ui.bay_rects if rect.collidepoint(mouse_ui)), None)
            if bay is not None:
                drone = st.drone_in(bay)
                if drone is None:
                    return "Slot de drone vazio"
                if drone.busy:
                    return "Drone · em voo (travado)"
                if drone.cargo:
                    return f"Drone · segurando {drone.cargo} {C.RESOURCE_NAME[drone.resource]} (sem quem receba)"
                return "Drone · pousado (clique tira)"
            res = next((r for rect, r in ui.buffer_rects if rect.collidepoint(mouse_ui)), None)
            if res is not None:
                return f"{item_name(res)} · {st.buffer.get(res, 0)} (sobras)"
        # seção DRONES só existe no baú/drill (na estação a lista podia vir do painel aberto antes)
        hit = ui.logistics_at(mouse_ui) if (self.open_chest or self.open_drill) is not None else None
        if hit is not None:
            kind, value = hit
            if kind == "batch":
                return f"Lote: drones tiram até {value} daqui por viagem"
            name = C.RESOURCE_NAME[value]
            return f"Envia {name}: drones tiram daqui" if kind == "send" else f"Recebe {name}: drones trazem pra cá"
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

    def on_logistics_click(self, pos) -> bool:
        """Clique na seção DRONES do baú/drill aberto: liga/desliga Envia e Recebe, ou troca o lote.
        True se acertou um botão."""
        hit = self.ui.logistics_at(pos)
        side = self.open_chest or self.open_drill
        if hit is None or side is None:
            return False
        kind, value = hit
        if kind == "send":
            changed = drones.toggle_send(side, value)
        elif kind == "recv":
            changed = drones.toggle_receive(side, value)
        else:
            changed = value != side.batch and drones.set_batch(side, value)
        if changed:
            self.audio.play("ui_click")
        return True

    def drill_status(self) -> str:
        """Linha de estado no painel da drill: "1 a cada 12 s", "CHEIA · PAROU", com o ritmo no déficit."""
        drill = self.open_drill
        if drill.full:
            return "CHEIA · PAROU"
        text = f"1 A CADA {C.DRILL_INTERVAL:g} S"
        if self.state.power.deficit:
            text += f" · RITMO {self.power_percent()}%"
        return text

    def labeled_chests(self) -> list:
        """Baús que mostram o rótulo flutuante (↓recebe ↑envia Nome): só o que está debaixo do mouse."""
        chest = self.hovered_machine()
        return [chest] if chest is not None and chest.is_chest else []

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
        volumes = len(UI.VOLUME_ROWS) + len(UI.OPTION_ROWS) + 1     # + "Voltar"
        return {"main": len(UI.PAUSE_OPTIONS), "volumes": volumes, "controls": 1}[self.pause_screen]

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
            elif self.pause_selected == n + 2:        # interface: A aumenta, D diminui (ordem da lista)
                self.ui_size_step(-1 if left else 1)
        elif key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT) and self.pause_screen == "controls":
            self.turn_controls_page(-1 if key in (pygame.K_a, pygame.K_LEFT) else 1)
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
                self.controls_page = 0
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
        elif self.pause_screen == "volumes" and index == len(UI.VOLUME_ROWS) + 2:   # interface: dá a volta
            self.pause_selected = index
            self.ui_size_step(1)
        else:   # "Voltar" (volumes ou controles)
            self.pause_screen, self.pause_selected = "main", 0
            self.audio.play("ui_close")

    def turn_controls_page(self, step: int) -> None:
        pages = self.ui.controls_pages
        if pages > 1:
            self.controls_page = (self.controls_page + step) % pages
            self.audio.play("ui_click")

    def set_volume(self, key: str, value: float, save: bool = False) -> None:
        self.settings = settings.clean({**self.settings, key: round(value, 2)})
        self.audio.set_mix(**settings.mix(self.settings))
        self.audio.play("ui_click")
        if save:
            settings.save(self.settings)

    def pause_hover(self) -> None:
        ux, uy = self.mouse_ui
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

    def set_option(self, index: int, value) -> None:
        """Clique num segmento das Opções: tela cheia Não|Sim, um nível de zoom ou um tamanho de interface."""
        n = len(UI.VOLUME_ROWS)
        self.pause_selected = index
        if index == n:
            if value != self.settings["fullscreen"]:
                self.toggle_fullscreen()
        elif index == n + 1:
            self.set_zoom(value, notify=False)
        elif index == n + 2 and value != self.settings["ui_size"]:
            self.set_ui_size(value)
        self.audio.play("ui_click")

    def on_pause_click(self) -> None:
        ux, uy = self.mouse_ui
        if self.pause_screen == "volumes":
            hit = self.ui.segment_at((ux, uy))
            if hit is not None:
                self.set_option(*hit)
                return
        for i, bar in enumerate(self.ui.pause_sliders):
            if bar.inflate(4, 8).collidepoint(ux, uy):     # área de clique um pouco maior que a barra
                self.dragging_slider = i
                self.pause_selected = i
                self.pause_hover()
                return
        for rect, step in self.ui.pause_page_buttons:
            if rect.collidepoint(ux, uy):
                self.turn_controls_page(step)
                return
        for i, rect in enumerate(self.ui.pause_items):
            if rect.collidepoint(ux, uy):
                self.pause_activate(i)
                return

    def on_click(self, button: int) -> None:
        if self.mode == "title":
            if button == 1:
                self.on_title_action(self.title.click(*self.mouse_ui))
            return
        if self.mode == "pause":
            if button == 1:
                self.on_pause_click()
            return
        if self.mode == "map":
            if button == 1:
                self.on_map_click()
            return               # nenhum clique com o mapa aberto chega no jogo (minerar, colocar, desmontar)
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
            ux, uy = self.mouse_ui
            for rect, index in self.ui.fabricator_tabs:
                if rect.collidepoint(ux, uy):
                    if index != self.fab.tab:
                        self.fab.set_tab(index)
                        self.audio.play("ui_click")
                    return
            self.on_craft_click((ux, uy), self.fab)        # a lista pode estar rolada: acha pelo tipo
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
            self.open_station = self.open_drill = None
            if self.mode == "crate":     # fechou a caixa de saque: o som do baú fechando
                self.audio.play("chest_close")
                self.open_crate = None
                self.mode = mode
                self.mouse_held = False
                return
            if self.mode == "chest":     # fechou o baú: som próprio no lugar do ui_close
                self.audio.play("chest_close")
                self.open_chest = self.renderer.open_chest = None
                self.mode = mode
                self.mouse_held = False
                return
        if mode != self.mode:
            self.audio.play("ui_open" if mode in ("fabricator", "pause", "inventory", "station", "drill") else "ui_close")
        self.mode = mode
        self.mouse_held = False

    def try_craft(self, kind: str, batch: bool = False, field: bool = False) -> None:
        """Fabrica 1 (ou, com Shift, até C.CRAFT_BATCH: para quando faltar recurso). O lote mostra "Drone x5".
        `field` = aba Fabricar do Tab (kit de campo, só do inventário). Fabricou: fecha o menu e, se a máquina
        caiu na hotbar, já entra no modo de colocar (nos dois casos)."""
        made = (self.state.craft_many(kind, field=field) if batch
                else int(self.state.craft(kind, field=field)))
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
        if self.mode != "play" or self.state.ramp is not None:
            return Controls(in_menu=self.mode != "play")   # tela aberta: o vento não empurra
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
        if self.mode == "map" and not self.map_view.dragging:     # WASD/setas andam a câmera do mapa
            mx = max(-1, min(1, sum(MOVE_KEYS[k][0] for k in self.keys_down if k in MOVE_KEYS)))
            my = max(-1, min(1, sum(MOVE_KEYS[k][1] for k in self.keys_down if k in MOVE_KEYS)))
            if mx or my:
                self.map_view.key_pan(mx, my, dt)
        # a máquina na mão tem que continuar no slot selecionado (pode ter sido movida no Tab)
        stack = self.state.inventory.slots[self.hotbar_selected]
        if self.placing and (stack is None or stack.item != self.placing):
            self.placing = None
        self.notice_time = max(0.0, self.notice_time - dt)
        self.toast_time = max(0.0, self.toast_time - dt)
        self.thaw_notice_time = max(0.0, self.thaw_notice_time - dt)
        self.blueprint_notice_time = max(0.0, self.blueprint_notice_time - dt)
        self.blueprint_duck = max(0.0, self.blueprint_duck - dt)
        self.banner_time += dt
        self.renderer.machine_t += dt * self.state.power.factor    # animação das máquinas no ritmo da energia
        self.floaters.update(dt)
        self.floaters.scale = self.zoom * self.ui.canvas_k     # faixas dos floaters em px da tela
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
            resource = C.TILE_RESOURCE.get(tile_kind)
            color = C.ORE_COLORS[resource][0] if resource else C.PALETTES[art_key(self.state.stage)]["rock_hi"]
            self.renderer.spawn_chips(tile, color, 12)
            self.audio.play("mine_break")
            self.renderer.minimap.repaint(self.state, tile)      # o mapa do scanner acompanha a mineração
        elif kind == "rock_spawn":                                # rocha nova na superfície (fora da vista)
            self.renderer.minimap.repaint(self.state, event[1], "surface")
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
        elif kind == "drone_deliver":           # drone entregou num baú que Recebe aquele item
            _, resource, amount, (x, y) = event
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", x, y - 78, C.ORE_COLORS[resource][0])   # acima do rótulo do baú
            distance = math.hypot(x - self.state.player.x, y - self.state.player.y) / C.TILE
            self.audio.play("drone_deliver", gain=sound.drone_deliver_gain(distance))
        elif kind == "dismantle":
            _, _, tile = event
            self.renderer.spawn_chips(tile, "#9a9086", 14)       # poeirinha
            self.renderer.spawn_chips(tile, "#c8c0b4", 8)
            self.audio.play("place_low")
        elif kind == "crate_open":            # caixa de saque (vazia: mais baixo, dica do Som)
            self.audio.play("crate_open", gain=0.67 if event[1] else 1.0)
            self.crate_open_t = self.t
        elif kind == "blueprint":             # projeto: aviso, jingle 0,4 s depois do crate_open, ambiente a 60%
            self.blueprint_notice, self.blueprint_notice_time = event[1], C.BLUEPRINT_NOTICE_TIME
            delay = max(0.0, C.BLUEPRINT_SOUND_DELAY - (self.t - self.crate_open_t))
            self.audio.play("blueprint_found", delay=delay)
            self.blueprint_duck = delay + C.BLUEPRINT_DUCK[1]
        elif kind == "loot":
            _, resource, amount, (ax, ay) = event
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", ax, ay - 40, C.ORE_COLORS[resource][0])
        elif kind == "gate_thaw":             # v0.4 M3.5: um gelo-portão começou a derreter (1) ou abriu a fresta (3)
            _, i, stage = event
            pockets = self.state.surface.geo.pockets if self.state.surface.geo is not None else []
            if i < len(pockets) and stage >= 3:   # o mapa do scanner tira a caixa fechada do portão
                for tile in pockets[i].gate.tiles:
                    self.renderer.minimap.repaint(self.state, tile, "surface")
            if stage >= 3:
                self.show_toast(C.THAW_GATE_NOTICE, C.THAW_GATE_NOTICE_TIME)
                self.audio.play("ice_crack")      # sem ice_crack.wav (Som), silêncio
        elif kind == "gust":                  # rajada começou (tempestade): volume pelo storm, sem gust.wav fica mudo
            self.audio.play("gust", gain=sound.gust_gain(event[1]))
        elif kind == "crater_thaw":           # v0.4 M3.1: a tampa baixou uma etapa (sem ice_crack.wav, silêncio)
            opened = event[1] >= C.CRATER_ICE_STAGES
            self.show_thaw_notice(CRATER_OPEN_TEXT if opened else CRATER_THAW_TEXT)
            self.audio.play("ice_crack")
        elif kind == "submerged":             # v0.4 M3.4: o lago cobriu uma máquina (várias juntas: um aviso só)
            showing = self.submerged_kinds and self.thaw_notice_time > 0 \
                and self.thaw_notice == submerged_notice(self.submerged_kinds)
            if not showing:                       # o aviso anterior já saiu (ou é outro): começa a contar de novo
                self.submerged_kinds = []
            self.submerged_kinds.append(event[1])
            self.thaw_notice, self.thaw_notice_time = submerged_notice(self.submerged_kinds), C.THAW_CRATER_NOTICE_S
        elif kind == "fumarole_wake":         # só um aviso visual, e só com a fumarola na tela (sem som por ora)
            if self.vent_on_screen(event[1]):
                self.show_thaw_notice(FUMAROLE_WAKE_TEXT)
        elif kind == "equip":
            self.audio.play("equip")
        elif kind == "unequip":
            self.audio.play("inv_move")
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
            # luminária: o som próprio dela no lugar do place (sem o arquivo, o place de sempre)
            self.audio.play("lamp_place" if event[1] == "lamp" and self.audio.has("lamp_place") else "place")
        elif kind == "ramp":                  # começou a descer/subir: passos na rampa (sem arquivo, silêncio)
            self.audio.play("ramp_down" if event[1] == "cave" else "ramp_up")
            self.mouse_held = False
        elif kind == "layer":                 # trocou de camada no meio do fade: o que era de lá fica lá
            self.floaters = FloatingTexts()
            self.renderer.particles.clear()
            self.drills_near.clear()
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
            self.audio.stage_up(self.ambient_want(event[1]))   # na caverna o ambiente não troca lá embaixo
            if event[1] == C.ARID_STAGE and self.state.layer != "cave":
                self.audio.play("sky_clear", delay=SKY_CLEAR_DELAY)   # a última lufada indo embora (Som v9)
            if event[1] == C.GREEN_STAGE:      # fim do jogo
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
        duck = C.BLUEPRINT_DUCK[0] if self.mode == "terminal" or self.blueprint_duck > 0 else 1.0
        audio.duck_ambient(0.0 if state.fainted else duck)
        # vento e ambiente seguem a camada de DESTINO: descendo, já começam a sair junto com o fade
        audio.set_wind(self.ambient_layer() == "surface")    # vento do deserto: só na superfície
        audio.set_rain(sound.rain_volume(rain_level(state)))   # chuva (M3.3): só na superfície, volume = intensidade
        want = self.ambient_want()
        if want != audio.ambient_key and not audio.busy_with_stage:
            audio.crossfade_to(want)              # amb_{estágio} <-> amb_cave (1,5 s sai, 2,5 s entra)
        audio.update(dt)
        if state.player.moving and self.mode == "play":
            self.footstep_timer -= dt
            if self.footstep_timer <= 0:
                self.audio.play(f"footstep_{self.footstep_side}")
                self.footstep_side = 1 - self.footstep_side
                self.footstep_timer = FOOTSTEP_INTERVAL
        else:
            self.footstep_timer = 0.0

    def ambient_layer(self) -> str:
        """Camada que o som deve seguir: a de destino se estiver passando pela rampa."""
        ramp = self.state.ramp
        return ramp.to if ramp is not None else self.state.layer

    def ambient_want(self, stage: int | None = None) -> str:
        """Ambiente que deveria tocar agora (game/audio.ambient_for)."""
        key = stage_key(stage or self.state.stage)
        return sound.ambient_for(self.ambient_layer(), key, self.audio.has("amb_cave"), self.audio.has("amb_storm"))

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
                if not d.full and not d.submerged and -64 < ax - cx < vw + 64 and -64 < ay - cy < vh + 64:
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
            if m.type.index is not None and not m.submerged and (t - dt + phase) % period > (t + phase) % period:
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

    def e_target(self) -> tuple[str, object] | None:
        """O que o E abre agora: o interagível debaixo do mouse, se estiver no alcance; senão o mais
        perto do player (None = nada; aí, na base, o E abre o fabricador)."""
        return self.state.interaction(self.state.interactable_at(*self.mouse_world()))

    def hint(self) -> str | None:
        state = self.state
        if self.placing == "drill" and self.place_target() is None:
            return "Coloque a drill em cima de um veio"
        target_tile = self.place_target() if self.placing else None
        if target_tile is not None and state.world.is_water(*target_tile, state.stage):   # v0.4 M3.4
            return "Não dá pra construir na água · Esc cancela"
        if self.placing == "drone_station" and not state.active.has_base:
            return "Drones só funcionam na superfície · Esc cancela"
        if self.placing == "drone_station":
            return "Clique para colocar · drones atendem o mapa todo · Esc cancela"
        if self.placing:
            return "Clique para colocar · R gira · Esc cancela"
        machine = self.hovered_machine()
        target = self.e_target()
        # mouse numa máquina que o E não vai abrir (longe, ou outra está no alcance): diz qual ele abre
        other = f" · {self.e_label(target)}" if target and target[1] is not machine else ""
        if machine and machine.submerged:                  # v0.4 M3.4: parada debaixo d'água
            if target and target[1] is machine:
                return self.e_label(target) + f" · [{C.DISMANTLE_KEY}] recolher"
            return (f"Submersa · [{C.DISMANTLE_KEY}] recolher" if state.can_dismantle(machine)
                    else "Submersa · chegue mais perto pra recolher")
        if machine and machine.is_drill:
            label = C.RESOURCE_NAME[machine.resource]
            content = (f"Drill cheia: {machine.stored} {label}" if machine.full
                       else f"Drill: {machine.stored}/{C.DRILL_CAPACITY} {label}")
            if state.power.deficit and not machine.full:
                content += f" · ritmo {self.power_percent()}%"
            return content + (" · [E] abrir · [Shift+E] coletar" if target and target[1] is machine else other)
        if machine and machine.is_station:
            st = machine.station
            text = f"Estação: {len(st.drones)}/{C.STATION_DRONE_SLOTS} drones"
            if st.stored:
                text += f" · sobras {st.stored}"
            if state.power.deficit:
                text += f" · ritmo {self.power_percent()}%"
            return text + (" · [E] abrir" if target and target[1] is machine else other)
        if machine and machine.is_chest:
            used = sum(1 for st in machine.storage.slots if st)
            mine = target is not None and target[1] is machine
            return f"{machine.name or C.CHEST_DEFAULT_NAME} ({used}/{C.CHEST_SLOTS})" + (" · [E] abrir" if mine else other)
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
        hover = state.interactable_at(*self.mouse_world())
        wreck = state.world.wreck_at(*self.mouse_tile())
        if wreck is not None and hover is None:                         # corpo do destroço (não a caixa/terminal)
            return f"{wreck.name} · destroço" + (f" · {self.e_label(target)}" if target else "")
        if target:
            return self.e_label(target)
        if hover is not None and hover[0] == "crate":                   # caixa debaixo do mouse, longe
            return "Caixa vazia" if hover[1].empty else "Caixa de saque · chegue mais perto"
        if hover is not None and hover[0] == "wreck_log":
            return "Terminal · chegue mais perto"
        if hover is not None and hover[0] == "container":
            return "Contêiner lacrado · chegue mais perto"
        tile = self.mouse_tile()
        if state.world.get(*tile) == C.CRATER:            # rampa debaixo do mouse, mas longe
            if state.ramp_blocked():
                return CRATER_ICE_HINT
            return ("Cratera · chegue mais perto pra descer" if state.active.has_base
                    else "Rampa · chegue mais perto pra subir")
        if state.in_base_zone():
            return "[E] Fabricador" if self.t > 6 else "As rochas pequenas do deserto têm minério"
        if state.world.is_minable(*tile):
            if state.world.get(*tile) in C.SMALL_ROCKS:
                name = C.RESOURCE_NAME[C.SMALL_ROCKS[state.world.get(*tile)]]
                return (f"Rocha com {name} · segure o clique para quebrar" if state.can_mine(tile)
                        else f"Rocha com {name} · chegue mais perto")
            return "Segure o clique para minerar" if state.can_mine(tile) else "Chegue mais perto pra minerar"
        return None

    def highlight_target(self):
        """O que ganha o contorno no mundo: o alvo do E, só jogando (sem máquina na mão)."""
        if self.mode != "play" or self.placing or self.state.fainted:
            return None
        target = self.e_target()
        if target is None:
            return None
        if target[0] == "terminal":
            return "terminal", tuple(self.state.world.terminals[target[1]])
        if target[0] == "ramp":
            return "ramp", target[1]
        if target[0] == "wreck_log":
            return "wreck_log", target[1]
        if target[0] == "container":
            return "container", target[1]
        return target[1]                          # máquina ou caixa de saque

    def e_label(self, target: tuple[str, object]) -> str:
        """Texto do canto pro alvo do E ("[E] Abrir baú", "[E] Ler terminal"...). Máquina submersa (v0.4 M3.4):
        "Submersa · " na frente (o E continua abrindo, pra tirar o que estava dentro)."""
        if getattr(target[1], "submerged", False):
            return "Submersa · " + self._e_label(target)
        return self._e_label(target)

    def _e_label(self, target: tuple[str, object]) -> str:
        kind, obj = target
        if kind == "terminal":
            return "[E] Ler terminal"
        if kind == "ramp":
            if self.state.ramp_blocked():                 # v0.4: a cratera nasce tampada de gelo
                return CRATER_ICE_HINT
            return "[E] Descer pela rampa" if self.state.active.has_base else "[E] Subir pela rampa"
        if kind == "crate":
            return "[E] Caixa vazia" if obj.empty else "[E] Abrir caixa de saque"
        if kind == "wreck_log":
            return "[E] Ler terminal"
        if kind == "container":
            return "[E] Contêiner lacrado"
        if kind == "chest":
            name = obj.name or C.CHEST_DEFAULT_NAME
            return "[E] Abrir baú" if name == C.CHEST_DEFAULT_NAME else f"[E] Abrir baú: {name}"
        if kind == "station":
            return "[E] Estação de drones" if obj.station.drones else "[E] Estação: coloque drones"
        return (f"[E] Drill · [Shift+E] coletar {obj.stored} {C.RESOURCE_NAME[obj.resource]}" if obj.stored
                else "[E] Abrir drill")

    def power_percent(self) -> int:
        """Ritmo atual das máquinas em % (arredondado pra baixo: 62,5% vira 62%)."""
        return int(self.state.power.factor * 100)

    def draw(self) -> None:
        state, canvas, ui = self.state, self.canvas, self.ui
        cam = self.cam
        ghost = None
        self.renderer.highlight = self.highlight_target()
        if self.placing and self.mode == "play":
            target = self.place_target()
            tile = target if target is not None else self.mouse_tile()
            ghost = (self.placing, tile, self.rotation, target is not None and state.can_place(self.placing, tile))
        if self.zoom == 1.0:
            self.renderer.draw(canvas, state, cam, self.t, ghost)
        else:   # o mundo vai numa visão de 960×540/zoom e é esticado sem suavizar (pixel art continua pixel)
            if self._world_view is None or self._world_view.get_size() != self.view_size:
                self._world_view = pygame.Surface(self.view_size, 0, canvas)
            self.renderer.draw(self._world_view, state, cam, self.t, ghost)
            pygame.transform.scale(self._world_view, canvas.get_size(), canvas)

        critical = state.o2 < C.O2_LOW and not state.fainted
        if critical:
            pulse = 0.5 + 0.12 * math.sin(self.t * 6.3)
            self.red_vignette.set_alpha(int(255 * pulse))
            canvas.blit(self.red_vignette, (0, 0))
        self.present()                     # mundo na janela; as camadas da UI vão por cima
        window = self.window
        self.apply_ui_layout()

        # camada 1: HUD e textos flutuantes
        ui.begin()
        icons = {r: self.renderer.surface(f"icon_{r}", lambda r=r: art.icon(r))[0] for r in C.RESOURCES}
        labels = []
        if self.mode == "play":
            ui.draw_chest_labels(self.labeled_chests(), cam, self.zoom, icons)
            labels = ui.chest_label_rects
        if critical:
            ui.draw_o2_critical(state, self.t, cam)
        ui.draw_hud(state, self.t, self.hint() if self.mode == "play" else None, icons, self.renderer.item_icon)
        ui.draw_hotbar(state.inventory, self.hotbar_selected, self.renderer.item_icon,
                       show_name=self.mode == "play" and not state.fainted)
        if not critical:   # com O₂ crítico o aviso grande ocupa essa área (e o foco é voltar pra base)
            ui.draw_objectives(self.objectives.lines(state))
        ui.draw_gust_warning(state, self.t)
        if self.thaw_notice_time > 0 and self.thaw_notice:
            ui.draw_thaw_notice(self.thaw_notice, min(1.0, self.thaw_notice_time / 0.4))
        if state.has_scanner and self.mode != "map":           # scanner equipado: minimapa
            ui.draw_minimap(state, self.renderer.minimap.texture(state), self.t, self.renderer.item_icon)
        if self.saved_notice > 0:
            draw_saved_notice(ui, self.saved_notice)
        if self.toast_time > 0 and self.toast:
            ui.draw_toast(self.toast, min(1.0, self.toast_time / 0.3))
        if self.banner_time < BANNER_TIME:
            alpha = min(1.0, self.banner_time / BANNER_FADE_IN, (BANNER_TIME - self.banner_time) / BANNER_FADE_OUT)
            ui.draw_banner(self.banner_stage, alpha)
        # floaters por último na camada: já sabem onde ficou cada painel do HUD (ui.hud_rects) e somem
        # antes de entrar embaixo deles
        ui.draw_floaters(self.floaters, cam, self.zoom, labels)
        ui.finish(window)

        # camada 2: menus e telas por cima do HUD
        mouse_ui = self.mouse_ui
        ui.begin()
        if self.mode == "fabricator":
            preview = self.renderer.machine_preview
            ui.draw_fabricator(state, self.fab, preview, self.t, self.renderer.item_icon, mouse_ui, self.shift_held())
        elif self.mode == "terminal":
            ui.draw_terminal(self.terminal_index, self.t)
        elif self.mode == "map":
            ui.draw_map(state, self.map_view, lambda key: self.renderer.minimap.texture(state, key), self.t, mouse_ui)
        elif self.mode == "end":
            ui.draw_end(state, self.t)
        elif self.mode == "pause":
            ui.draw_pause(self.pause_screen, self.pause_selected, self.settings, viewport_label(self.zoom),
                          viewport.UI_SIZE_LABEL[self.settings["ui_size"]], self.controls_page)
        elif self.mode == "inventory" and self.inv_tab == TAB_LOGS:
            ui.draw_logs(state, self.log_selected, self.log_first, mouse_ui)
        elif self.mode == "inventory" and self.inv_tab == TAB_CRAFT:
            ui.draw_field_craft(state, self.field, self.renderer.machine_preview, mouse_ui, self.renderer.item_icon,
                                self.shift_held())
        elif self.mode in INVENTORY_MODES:
            side = self.open_chest or self.open_drill or self.open_station or self.open_crate
            status = (self.station_status() if self.open_station is not None
                      else self.drill_status() if self.open_drill is not None else "")
            station_info = self.hovered_slot_label(mouse_ui) if self.open_station is not None else None
            ui.draw_inventory(state.inventory, side, self.hotbar_selected, self.renderer.item_icon, mouse_ui,
                              self.t, self.name_edit, status, station_info,
                              equipment=state.equipment if self.mode == "inventory" else None,
                              state=state if self.mode == "inventory" else None, held=self.held)
        if self.notice_time > 0 and self.mode not in INVENTORY_MODES:   # por cima do fabricador também
            ui.draw_notice(self.notice, min(1.0, self.notice_time / 0.4))
        if state.fainted:
            ui.draw_faint(state)
        ui.draw_ramp_fade(state)
        ui.finish(window)

        # camada 3: pilha na mão ou tooltip, aviso e cursor, por cima dos ícones (slots, prévias, textura do
        # mapa). Antes o cursor ia na camada 2 e sumia embaixo do mapa e dos ícones (desenhados depois dela).
        ui.begin()
        if self.mode in INVENTORY_MODES:
            # na estação a dica vai numa linha do painel (station_info), não flutuando por cima do texto
            label = None if self.name_edit is not None or self.open_station is not None \
                else self.hovered_slot_label(mouse_ui)
            ui.draw_held_and_tooltip(self.held, label, mouse_ui, self.renderer.item_icon)
            if self.notice_time > 0:
                ui.draw_notice(self.notice, min(1.0, self.notice_time / 0.4), ui.notice_y)
        elif self.mode == "map" and ui.map_hover is not None:     # marcador escondido não tem tooltip
            ui.draw_map_tooltip(ui.map_hover, mouse_ui)
        ui.draw_cursor(*mouse_ui)
        ui.finish(window)

        # camada 4: "PROJETO: ..." por cima de tudo (até dos ícones dos painéis)
        if self.blueprint_notice_time > 0 and self.blueprint_notice:
            ui.begin()
            ui.draw_blueprint_notice(self.blueprint_notice, min(1.0, self.blueprint_notice_time / 0.5),
                                     self.renderer.item_icon(f"bp_{self.blueprint_notice}"))
            ui.finish(window)

    def screenshot(self, path: str) -> None:
        """Salva o que o jogador vê (mundo + UI), sem a tarja preta."""
        pygame.image.save(self.frame, path)

    # ---- save/load e tela de título (game/save.py, game/title.py) --------------
    def open_title(self) -> None:
        """Vai pra tela de título. Lê os mundos (game/worlds.py) e carrega o do "Continuar" (o último jogado)."""
        world_list = worlds.list_worlds()             # 1ª vez: o saves/slot1.json v7 vira o mundo 1
        slot = worlds.continue_slot(world_list)
        saved = None
        if slot is not None and world_list[slot - 1].playable:
            saved = worlds.load(slot)[1]
        old = saved is None and worlds.legacy_status() == "old"   # slot1.json v1–v6: avisa "save antigo"
        if saved is None and slot is not None and world_list[slot - 1].status == "old":
            old = True
        self.title.open(saved, old=old, world_list=world_list, slot=slot if saved else None)
        self.mode = "title"
        self.sync_text_input()
        self.placing = None
        self.mouse_held = False
        self.keys_down.clear()
        self.audio.set_alarm(False)          # nada de alarme, zumbido ou drill tocando no menu
        self.audio.set_hum(0.0)
        self.audio.set_drill_loops([])
        self.audio.set_drone_loops([])
        self.audio.set_solar_hum(0.0)
        self.audio.set_wind(False)
        self.audio.set_rain(0.0)
        self.audio.duck_ambient(1.0)
        if self.audio.ambient_key != "dead":
            self.audio.start_ambient("dead")

    def sync_text_input(self) -> None:
        """Digitação do SDL ligada só enquanto tem campo de texto aberto (nome do baú ou Novo mundo)."""
        want = self.name_edit is not None or (self.mode == "title" and self.title.wants_text)
        if want == self.text_input:
            return
        self.text_input = want
        try:
            pygame.key.start_text_input() if want else pygame.key.stop_text_input()
        except pygame.error:
            pass
        if want:
            self.keys_down.clear()

    def on_title_action(self, action) -> None:
        if action == "continue":
            self.start_game(self.title.saved, self.title.saved_slot)
        elif action == "quit":
            self.quit_game()
        elif isinstance(action, tuple) and action[0] == "play":
            status, state = worlds.load(action[1])
            if state is None:                     # sumiu ou estragou entre a lista e o clique
                self.title.set_worlds(worlds.list_worlds())
                self.show_toast(f"Não deu pra abrir o mundo ({status})")
                return
            self.start_game(state, action[1])
        elif isinstance(action, tuple) and action[0] == "create":
            _, slot, name, seed = action
            state = worlds.create(slot, name, seed)   # libera o espaço (antigo vira backup) e grava
            self.start_game(state, slot)
            self.show_toast(f"{state.world_name} · seed {state.seed}")
        elif isinstance(action, tuple) and action[0] == "delete":
            worlds.delete(action[1])
            self.title.set_worlds(worlds.list_worlds())
            if self.title.saved_slot == action[1]:
                self.title.saved = self.title.saved_slot = None
        self.sync_text_input()

    def start_game(self, state: GameState, slot: int | None = None) -> None:
        """Começa a jogar com `state` (novo ou carregado) no espaço de mundo `slot` (None = mantém o atual):
        zera tudo que é do App e não do jogo."""
        if slot is not None:
            self.slot = slot
            worlds.mark_played(slot)              # o "Continuar" abre este
        self.state = state
        self.objectives = ObjectiveTracker(state)
        self.floaters = FloatingTexts()
        self.renderer.particles.clear()
        self.placing, self.rotation, self.mouse_held = None, 0, False
        self.hotbar_selected, self.held, self.notice_time = 0, None, 0.0
        self.open_chest = self.renderer.open_chest = None
        self.open_station, self.open_drill, self.name_edit = None, None, None
        self.open_crate = self.after_terminal = None
        self.renderer.minimap.reset()
        self.blueprint_notice, self.blueprint_notice_time, self.blueprint_duck = None, 0.0, 0.0
        self.thaw_notice, self.thaw_notice_time = None, 0.0
        self.submerged_kinds = []
        self.banner_stage, self.banner_time, self.end_timer = state.stage, 0.0, None
        self.drills_near.clear()
        self.drill_full_last.clear()
        self.autosave_timer, self.saved_notice = 0.0, 0.0
        self.mode = "play"
        self.audio.play("ui_close")
        if self.audio.ambient_key != self.ambient_want():
            self.audio.start_ambient(self.ambient_want())

    def save_game(self, notify: bool = True) -> bool:
        """Salva agora. `notify` mostra o "Jogo salvo" no HUD e toca o som de save."""
        # sem espaço de mundo (testes, smoke com skip_title) grava no save.SAVE_PATH, igual a antes dos mundos
        ok = save.write_save(self.state, worlds.path(self.slot) if self.slot else None)
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
        self.title.draw_background(self.canvas, self.t)
        self.present()
        self.apply_ui_layout()
        self.title.draw(self.window, self.t, self.mouse_ui)
