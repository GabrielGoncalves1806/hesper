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

Modos de tela: "play" (jogando), "fabricator" (menu de receitas), "build" (menu do construtor, v0.5 M1),
"terminal" (lendo um log), "inventory" (Tab: abas Inventário e LOGs), "chest" (baú aberto com E), "drill" (drill aberta com E;
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
import time

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
from game import ice_blocks, ruins, thaw
from game.perf_meter import PerfMeter
from game.assets import Sprites
from game.audio import Audio
from game.equipment import is_equipment
from game.geo import REGION_NAMES
from game.fabricator import FabMenu, build_menu, craft_menu, t2_menu
from game.inventory import Stack
from game.map_view import MapView
from game.objectives import ObjectiveTracker
from game.rain import rain_level
from game.render import Renderer, art_key, stage_key
from game.surfaces import opaque
from game.systems import Controls, GameState, collector_time, dispenser_capsule_time
from game.textedit import TextField
from game.ui import fmt, item_name, submerged_notice
from game.title import TitleScreen, draw_saved_notice
from game.ui import TAB_INVENTORY, TAB_LOGS, UI, FloatingTexts

MOVE_KEYS = {
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
}
NUMBER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8]
INVENTORY_MODES = ("inventory", "chest", "drill", "melter", "smelter", "collector", "cultivator", "dispenser", "station", "crate")
PANEL_MODES = ("chest", "drill", "melter", "smelter", "collector", "cultivator", "dispenser", "station", "crate")          # dois painéis: clique transfere pro outro lado (Planet Crafter)
ZOOM_IN_KEYS = (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)     # "=" é a tecla do "+" sem Shift
ZOOM_OUT_KEYS = (pygame.K_MINUS, pygame.K_KP_MINUS)
BANNER_TIME = 3.5          # banner de estágio: entra em 0,4 s, fica, sai em 0,8 s
BANNER_FADE_IN, BANNER_FADE_OUT = 0.4, 0.8
SKY_CLEAR_DELAY = 5.0   # s depois do stage_up do Árido
END_SCREEN_DELAY = 4.5
FOOTSTEP_INTERVAL = 0.3
DOOR_STUCK_COOLDOWN = 0.4   # s entre dois "tunk" da porta emperrada da VÉSPER-7 (dica do Som)
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


def capsule_time_text(seconds: float) -> str:
    """v0.8 M2: '45 s' até 90 s, '3 min' / '2.5 min' acima."""
    return f"{seconds:.0f} s" if seconds <= 90 else f"{seconds / 60:.1f} min".replace(".0 min", " min")


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
        self.perf = PerfMeter()                          # F5: FPS e ms do quadro no canto de baixo à esquerda

        self.sprites = Sprites()
        self.audio = Audio()
        self.cave_amb = sound.CaveRegionPicker()   # v0.6 Fundo M2: ambiente por bioma da caverna
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
        self.placing: str | None = None                   # máquina escolhida no menu do construtor (modo de construir)
        self.right_held = False                           # botão direito segurado (v0.5 M1: desmontar segurando)
        self.hotbar_selected = 0                          # slot da hotbar escolhido (0 a 7, teclas 1–8)
        self.held: Stack | None = None                    # pilha presa no cursor na tela de inventário
        self.open_chest = None                            # baú aberto (Machine), no modo "chest"
        self.open_station = None                          # estação aberta (Machine), no modo "station"
        self.open_drill = None                            # drill aberta (Machine), no modo "drill"
        self.open_melter = None                           # derretedor aberto (Machine), no modo "melter" (v0.5 M2)
        self.open_smelter = None                          # Fundição aberta (Machine), no modo "smelter" (v0.6 Fundo M3)
        self.open_collector = None                        # Coletor de água aberto (Machine), no modo "collector" (v0.8 M2)
        self.open_cultivator = None                       # Cultivador aberto (Machine), no modo "cultivator" (v0.8 M3)
        self.open_dispenser = None                        # Dispersor de O₂ aberto (Machine), no modo "dispenser" (v0.5 M2)
        self.dry_fade_t = 0.0                             # s desde o dispenser_dry: o zumbido sai em 0,3 s em vez de 0,8
        self.open_crate = None                            # caixa de saque aberta (Crate), no modo "crate"
        self.after_terminal = None                        # registro de bordo lido ao abrir a caixa: depois abre ela
        self.blueprint_notice: str | None = None          # diagrama do aviso "DIAGRAMA: ..." (Marco 3)
        self.blueprint_notice_time = 0.0
        self.blueprint_duck = 0.0                         # s com o ambiente abaixado (diagrama encontrado)
        self.crate_open_t = -10.0                         # quando tocou o crate_open (o blueprint_found vem 0,4 s depois)
        self.map_sound_t = -10.0                          # M: no máximo 1 som de abrir a cada 0,3 s
        # mapa aberto (M): câmera, camada e filtros. Zoom e filtros vêm do settings.json (preferência do jogador)
        self.map_view = MapView(self.settings["map_zoom"], self.settings["map_hidden"])
        self.name_edit: TextField | None = None           # editando o nome do baú (texto digitado)
        self.notice: str | None = None                    # aviso curto ("Inventário cheio")
        self.notice_time = 0.0
        self.rotation = 0
        self.fab_bench = "t1"           # bancada do painel de fabricar aberto ("t2" = a Bancada T2): qual diagrama ela lê
        self.fab = craft_menu()         # aba, seleção e rolagem do fabricador (só itens · game/fabricator.py)
        self.fab_t2 = t2_menu()         # o mesmo, da Bancada T2 (receitas dela)
        self.open_bench = None          # Bancada T2 aberta (Machine): quem anima quando fabrica
        self.build_menu = build_menu(lambda: self.state.known_props())  # v0.5 M1: menu do construtor (E com ele na mão); v0.7 M2: props só os conhecidos
        self.terminal_index = 0
        self.inv_tab = TAB_INVENTORY    # Tab: Inventário / LOGs (a aba Fabricar saiu no v0.5 M1)
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
        self.objective_hint: str | None = None   # v0.4: dica do objetivo atual (magmatita), embaixo da coluna da esquerda
        self.objective_hint_time = 0.0
        self.submerged_kinds: list[str] = []  # v0.4 M3.4: máquinas do aviso "submersa" que está na tela (agrupa)
        self.toast_time = 0.0
        self.door_stuck_at = -9.0       # v0.7 M4: quando a porta emperrada fez tunk pela última vez (cooldown)
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
        start = time.perf_counter()
        self.handle_events()
        self.update(dt)
        if self.mode == "title":
            self.draw_title()
        else:
            self.draw()
        self.perf.add(dt, (time.perf_counter() - start) * 1000)   # o trabalho do quadro, sem a espera do vsync
        self.perf.draw(self.window)
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
            elif event.type == pygame.MOUSEWHEEL and self.mode in ("fabricator", "build"):
                self.menu_of_mode().scroll(-1 if event.y > 0 else 1)   # rodinha rola a lista de receitas
            elif event.type == pygame.MOUSEWHEEL and self.mode == "play" and not self.state.fainted \
                    and self.name_edit is None:
                # rodinha pra baixo = próximo slot (y < 0), pra cima = anterior
                self.select_hotbar((self.hotbar_selected + (1 if event.y < 0 else -1)) % C.HOTBAR_SLOTS)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                self.right_held = False                         # soltou: o desmonte segurado cancela
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
        elif key == pygame.K_F5:                          # contador de FPS e ms do quadro
            self.perf.toggle()
        elif key == pygame.K_F7:                          # debug (v0.8 M1): +biomassa (F6 fica pro overlay de colisão)
            state.debug_add_biomass()
        if state.fainted:
            return

        if self.mode == "pause":
            self.on_pause_key(key)
        elif self.mode in ("fabricator", "build"):
            menu = self.menu_of_mode()
            if key in (pygame.K_e, pygame.K_ESCAPE):
                self.set_mode("play")
            elif key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
                menu.move(-1 if key in (pygame.K_w, pygame.K_UP) else 1, self.diagram_count())
                self.audio.play("ui_click")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and menu.diag is not None:
                held = self.state.diagrams_held()
                if menu.diag < len(held):
                    self.read_diagram(held[menu.diag][0])
            elif key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT, pygame.K_TAB):
                menu.switch_tab(-1 if key in (pygame.K_a, pygame.K_LEFT) else 1)   # Tab: próxima aba
                self.audio.play("ui_click")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) and menu.current:
                if self.mode == "build":
                    self.choose_build(menu.current)
                else:
                    self.try_craft(menu.current, batch=self.craft_batch(menu))   # ×5 ou Shift: até 5
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
        elif self.mode == "end":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self.set_mode("play")
        else:  # play
            if key == pygame.K_e and self.constructor_selected() and not self.hover_in_reach():
                self.open_build_menu()            # v0.5 M1: construtor na mão abre o menu de construção
            elif key == pygame.K_e:
                target = self.e_target()          # o do mouse (no alcance) ou o mais perto
                if target and target[0] == "ramp":
                    state.start_ramp()                    # cratera/rampa: desce ou sobe (fade)
                elif target and target[0] in ("hatch_in", "hatch_out"):
                    state.start_hatch()                   # v0.7 M4: boca do porão / escotilha da VÉSPER-7 (fade)
                elif target and target[0] == "fixture":
                    self.use_fixture(target[1])
                elif target and target[0] == "terminal":
                    state.read_terminal(target[1])
                    self.terminal_index = target[1]
                    self.mode = "terminal"
                elif target and target[0] == "wreck_log":          # terminal do módulo da colônia
                    self.show_log(target[1].log)
                elif target and target[0] == "ruin_log":           # v0.7 M1: terminal de uma estrutura
                    self.show_log(state.world.ruin_terminals[tuple(target[1])])
                elif target and target[0] == "crate":
                    self.open_loot(target[1])
                elif target and target[0] == "container":          # v0.5 M4: abre de graça, mesma tela da caixa de saque
                    self.open_loot(state.container_crate(target[1]))
                elif target and target[0] == "drill" and self.shift_held():
                    state.collect(target[1])              # Shift+E: coleta tudo sem abrir o painel
                elif target and target[0] == "drill":
                    self.open_drill = target[1]
                    self.placing = None
                    self.set_mode("drill")
                elif target and target[0] == "melter":
                    self.open_melter = target[1]
                    self.placing = None
                    self.set_mode("melter")
                elif target and target[0] == "smelter":
                    self.open_smelter = target[1]
                    self.placing = None
                    self.set_mode("smelter")
                elif target and target[0] == "collector":
                    self.open_collector = target[1]
                    self.placing = None
                    self.set_mode("collector")
                elif target and target[0] == "cultivator":
                    self.open_cultivator = target[1]
                    self.placing = None
                    self.set_mode("cultivator")
                elif target and target[0] == "dispenser":
                    self.open_dispenser = target[1]
                    self.placing = None
                    self.set_mode("dispenser")
                elif target and target[0] == "bench":              # Bancada T2: o painel do fabricador, receitas dela
                    self.open_bench = target[1]
                    self.fab_bench = "t2"
                    self.fab_t2.diag = None
                    self.placing = None
                    self.set_mode("fabricator")
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
                    self.fab.diag = None
                    self.fab_bench = "t1"
                    self.open_bench = None
                    self.set_mode("fabricator")
                    state.fabricator_opened = True
            elif key == pygame.K_ESCAPE and self.placing:
                self.placing = None
                self.audio.play("ui_close")
            elif key == pygame.K_ESCAPE:
                self.open_pause()
            elif key == pygame.K_r and self.placing and self.placing not in C.PLAYER_PROPS:   # v0.7 M2: prop não gira
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
        """Escolhe o slot da hotbar. Trocar de slot sai do modo de construir (v0.5 M1: máquina não é item; quem
        constrói é o construtor, pelo menu do E)."""
        if index != self.hotbar_selected:
            self.placing = None
        self.hotbar_selected = index
        self.audio.play("ui_click")

    # ---- construtor (v0.5 M1) -----------------------------------------------------
    def held_drill_tier(self) -> int:
        """v0.6 Fundo M4: 0 sem broca na mão, 1 a nv.1, 2 a nv.2 (slot escolhido da hotbar)."""
        stack = self.state.inventory.slots[self.hotbar_selected]
        if stack is None or stack.item not in C.HAND_DRILLS:
            return 0
        return 2 if stack.item == C.HAND_DRILL_T2 else 1

    def hand_drill_selected(self) -> bool:
        """v0.5 M4: uma broca de mão (nv.1 ou nv.2) é o slot escolhido da hotbar? (só com ela o clique minera)"""
        return self.held_drill_tier() > 0

    def constructor_selected(self) -> bool:
        stack = self.state.inventory.slots[self.hotbar_selected]
        return stack is not None and stack.item == "constructor"

    def hover_in_reach(self) -> bool:
        """Tem algo do E debaixo do mouse e no alcance? (com o construtor na mão, o E abre o que está apontado;
        apontando pro nada, abre o menu de construção)"""
        hover = self.state.interactable_at(*self.mouse_world())
        return hover is not None and self.state.in_reach(*hover)

    def open_build_menu(self) -> None:
        if self.placing:                          # já construindo: o menu abre na máquina da mão
            self.build_menu.select(self.placing)
        self.placing = None
        self.set_mode("build")

    def choose_build(self, kind: str) -> None:
        """Escolheu a máquina no menu: fecha e entra no modo de construir (o fantasma; o clique constrói). Trancada
        (Ti ou diagrama) não entra; sem material entra (o fantasma fica vermelho e a dica diz o que falta)."""
        if self.state.build_status(kind) in ("locked", "blueprint", "no_constructor"):
            return
        self.set_mode("play")
        self.placing = kind
        self.rotation = 0

    def menu_of_mode(self) -> FabMenu:
        if self.mode == "build":
            return self.build_menu
        return self.fab_t2 if self.fab_bench == "t2" else self.fab

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
        """E na caixa: abre (o diagrama fica na caixa pra pegar). Nave e sonda: na 1ª vez, o registro de bordo aparece
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
        """Troca a aba do Tab. Saindo do Inventário (LOGs, sem slots), a pilha da mão volta pro
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

    def diagram_count(self) -> int:
        """Quantos diagramas a área "Diagramas" mostra (só no fabricador; o construtor não tem a área)."""
        return len(self.state.diagrams_held()) if self.mode == "fabricator" else 0

    def read_diagram(self, diagram: str) -> None:
        """LER: gasta 1 diagrama e libera a receita (o som e o aviso saem pelo evento diagram_read). Bancada errada
        ou receita já liberada: avisa e não gasta."""
        result = self.state.read_diagram(f"diagram_{diagram}", self.fab_bench)
        if result == "wrong_bench":
            self.show_notice(f"Esse diagrama se lê na {C.BENCH_LABEL[C.DIAGRAM_BENCH[diagram]].title()}")
        elif result == "known":
            self.show_notice("Receita já liberada")
        self.menu_of_mode().clamp_diag(self.diagram_count())

    def craft_batch(self, menu: FabMenu) -> bool:
        """Fabrica em lote (até C.CRAFT_BATCH)? Sim com o seletor em ×5 ou com o Shift segurado."""
        return menu.batch > 1 or self.shift_held()

    def on_craft_click(self, pos, menu: FabMenu) -> bool:
        """Clique na lista + detalhe (fabricador ou construtor): FABRICAR fabrica (×5 ou Shift: até 5), CONSTRUIR
        escolhe a máquina, ×1/×5 trocam o lote e a linha escolhe a receita. True se usou o clique."""
        ui = self.ui
        diagram = next((d for rect, d in ui.diagram_buttons if rect.collidepoint(pos)), None)
        if diagram is not None:
            self.read_diagram(diagram)
            return True
        kind = next((k for rect, k in ui.fabricator_buttons if rect.collidepoint(pos)), None)
        if kind is not None:
            if menu is self.build_menu:
                self.choose_build(kind)
            else:
                self.try_craft(kind, batch=self.craft_batch(menu))
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
        """Clique nas abas do Tab ou numa linha da aba LOGs. Devolve True se usou o clique."""
        tab = next((i for rect, i in self.ui.inv_tab_rects if rect.collidepoint(pos)), None)
        if tab is not None:
            self.switch_inv_tab(tab)
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
                self.show_notice("Sem scanner de navegação: o diagrama está num destroço")
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
        side = self.open_chest or self.open_drill or self.open_melter or self.open_smelter or self.open_collector or self.open_cultivator or self.open_dispenser
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
        if self.mode == "inventory" and self.inv_tab != TAB_INVENTORY:   # LOGs: sem slots
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
        if button == 1 and self.on_chip_click(pos):       # v0.6 M2: o slot do chip
            return
        if button == 3 and self.held is not None and self.held.item == "chip" and self.on_chip_click(pos):
            return                                        # direito com chip na mão: encaixa 1, igual ao esquerdo
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
        if button == 1 and self.shift_held():
            self.panel_shift_click(pos)                  # Shift+clique: manda direto pro outro lado
        else:
            self.panel_cursor_click(button, pos)

    def on_chip_click(self, pos) -> bool:
        """Clique no slot do chip. Mão vazia: o chip vai pro cursor (Shift: pro inventário). Chip na mão: encaixa 1.
        Outro item na mão: recusa. Devolve se o clique era no slot. O som sai do evento chip_on/chip_off."""
        machine = self.ui.chip_at(pos)
        if machine is None:
            return False
        state, held = self.state, self.held
        if held is None:
            if not machine.chip:
                return True
            if self.shift_held():
                state.chip_take(machine)
            elif state.chip_remove(machine):
                self.held = Stack("chip", 1)
        elif held.item != "chip":
            self.show_notice("Só chip vai nesse slot")
        elif machine.chip:
            self.show_notice("Essa máquina já tem chip")
        elif state.chip_install(machine):
            held.count -= 1
            if held.count == 0:
                self.held = None
        return True

    # ---- painel com a pilha no cursor (v0.6 M1) ---------------------------------------
    def panel_cursor_click(self, button: int, pos: tuple[float, float]) -> None:
        """Clique esquerdo pega/solta/junta/troca a pilha do slot; direito pega metade (mão vazia) ou solta 1."""
        ui, state = self.ui, self.state
        if self.open_station is not None:
            station = self.open_station
            bay = next((slot for rect, slot in ui.bay_rects if rect.collidepoint(pos)), None)
            if bay is not None:
                self.station_bay_click(station, bay)
                return
            res = next((r for rect, r in ui.buffer_rects if rect.collidepoint(pos)), None)
            if res is not None:                          # as sobras só tiram (direto pro inventário)
                if self.held is not None:
                    self.show_notice("As sobras só tiram")
                elif state.station_take(station, res, None if button == 1 else 1):
                    self.audio.play("inv_move")
                return
        hit = next(((inv, i) for rect, inv, i in ui.slot_rects if rect.collidepoint(pos)), None)
        if hit is not None and self.panel_put(hit[0], hit[1], button):
            self.audio.play("inv_move")

    def station_bay_click(self, station, bay: int) -> None:
        """Baia da estação: mão vazia tira o drone pousado (vai pro inventário); com drone na mão, põe 1 na baia livre."""
        state = self.state
        drone = station.station.drone_in(bay)
        if self.held is None:
            if drone is not None and drone.busy:
                self.show_notice("Drone em voo: espere ele pousar")
            elif drone is not None and state.station_undock(station, bay):
                self.audio.play("inv_move")
        elif self.held.item != "drone":
            self.show_notice("Só drones vão na estação")
        elif drone is not None:
            self.show_notice("Drone em voo: espere ele pousar" if drone.busy else "Baia ocupada")
        elif state.station_dock_slot(station, bay):
            self.held.count -= 1
            if self.held.count == 0:
                self.held = None
            self.audio.play("inv_move")

    def panel_refusal(self, inv, index: int, item: str) -> str | None:
        """Por que `item` não pode ser solto no slot `index` de `inv` (texto do aviso), ou None se pode."""
        if inv is self.state.inventory:
            return None
        if self.open_drill is not None and inv is self.open_drill.storage:
            return "A drill só produz: não guarda nada"
        if self.open_melter is not None and inv is self.open_melter.storage:
            return None if (index == C.MELTER_ICE_SLOT and item == "ice") else "O derretedor só aceita gelo"
        if self.open_smelter is not None and inv is self.open_smelter.storage:
            smelter = self.open_smelter                  # v0.6 Fundo M3: [0] ferro/cobre, [1] magmatita, [2] só tira
            if index == C.SMELTER_ORE_SLOT and item in C.SMELTER_RECIPES:
                have = smelter.storage.slots[index]
                return None if have is None or have.item == item else "Tire o minério que está na Fundição antes"
            if index == C.SMELTER_FUEL_SLOT and item == C.SMELTER_FUEL:
                return None
            return "A Fundição só aceita ferro, cobre e magmatita"
        if self.open_collector is not None and inv is self.open_collector.storage:
            if index == C.COLLECTOR_IN_SLOT and item == C.EMPTY_CAPSULE:     # v0.8 M2: [0] vazias entram, [1] só tira
                return None
            return "O Coletor só aceita cápsula vazia" if index == C.COLLECTOR_IN_SLOT else "A saída do Coletor só dá pra tirar"
        if self.open_cultivator is not None and inv is self.open_cultivator.storage:     # v0.8 M3
            if index == C.CULT_WATER_SLOT:
                return None if item == "water_capsule" else "A reserva só aceita cápsula de água"
            if index == C.CULT_SEED_SLOT:
                return None if item in C.CROP_ITEMS else "O Cultivador só aceita uma muda: alga ou planta"
            return "A saída só dá pra tirar" if index != C.CULT_EMPTY_SLOT else "As vazias só dá pra tirar"
        if self.open_dispenser is not None and inv is self.open_dispenser.storage:
            if index == C.DISPENSER_EMPTY_SLOT:
                return "A saída de vazias só dá pra tirar"      # v0.8 M2
            return None if item == "water_capsule" else "O Dispersor só aceita cápsula de água"
        return None

    def panel_put(self, inv, index: int, button: int) -> bool:
        """Um clique no slot `index` de `inv` com a pilha do cursor (`self.held`). Devolve se algo mudou. A regra do
        slot (drill só tira, derretedor só gelo na entrada...) e os efeitos de tirar (drill_collected, loot) moram aqui."""
        state, held, slot = self.state, self.held, inv.slots[index]
        right = button != 1
        if held is None:
            if slot is None:
                return False
            taken = inv.take_half(index) if right else inv.take(index)
            self.held = taken
            self._took_from_panel(inv, taken)
            if self.open_cultivator is not None and inv is self.open_cultivator.storage:
                self.open_cultivator.sync_crop()         # v0.8 M3: tirou a muda, a planta zera
            return True
        refusal = self.panel_refusal(inv, index, held.item)
        if refusal is None and inv is not state.inventory and self.open_melter is not None                 and inv is self.open_melter.storage and slot is not None and slot.item != held.item:
            refusal = "O derretedor só aceita gelo"
        if refusal is not None:
            self.show_notice(refusal)
            return False
        cult = self.open_cultivator
        if cult is not None and inv is cult.storage and index == C.CULT_SEED_SLOT:      # v0.8 M3: a muda é uma só
            if slot is not None and slot.item == held.item:
                return False
            if slot is not None and held.count > 1:
                self.show_notice("Tire a muda de lá antes (ou solte uma só)")
                return False
            old = slot
            inv.slots[index] = Stack(held.item, 1)
            held.count -= 1
            self.held = held if held.count > 0 else None
            if old is not None:                          # trocou: a antiga sai pro cursor (que ficou vazio)
                self.held = old
            cult.sync_crop()
            return True
        if right:                                        # solta 1
            if slot is not None and (slot.item != held.item or slot.room <= 0):
                return False
            inv.put(index, Stack(held.item, 1))
            held.count -= 1
            if held.count == 0:
                self.held = None
            return True
        before = ((held.item, held.count), inv.to_data())
        self.held = inv.put(index, held)                 # solta, junta ou troca
        if self.held is slot and slot is not None:       # trocou: o que estava no slot saiu pro cursor
            self._took_from_panel(inv, slot)
        return before != (((self.held.item, self.held.count) if self.held else None), inv.to_data())

    def _took_from_panel(self, inv, stack: Stack) -> None:
        """Efeitos de tirar `stack` de um painel pro cursor: a drill conta como coletado, a caixa solta o evento loot."""
        state = self.state
        if self.open_drill is not None and inv is self.open_drill.storage:
            state.drill_collected[stack.item] += stack.count
            state.events.append(("drill_collect", stack.item, stack.count, self.open_drill.anchor))
        elif self.open_crate is not None and inv is self.open_crate.storage and stack.item in C.RESOURCES:
            state.events.append(("loot", stack.item, stack.count, self.open_crate.anchor))

    def panel_shift_click(self, pos: tuple[float, float]) -> None:
        """Shift+clique esquerdo: manda a pilha clicada direto pro outro lado (só ela, não todas as do item: dono, v0.6)."""
        ui, state = self.ui, self.state
        amount = None
        if self.open_crate is not None:                  # caixa de saque / contêiner: tira e guarda
            hit = next(((inv, i) for rect, inv, i in ui.slot_rects if rect.collidepoint(pos)), None)
            if hit is None or hit[0].slots[hit[1]] is None:
                return
            if hit[0] is self.open_crate.storage:
                moved = state.crate_take(self.open_crate, hit[1], amount)
            else:
                moved = state.crate_put(self.open_crate, hit[1], amount)
                if not moved:
                    self.show_notice("Caixa cheia")
            if moved:
                self.audio.play("inv_move")
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
        target = (self.open_drill or self.open_melter or self.open_smelter or self.open_collector or self.open_cultivator
                  or self.open_dispenser)
        if item == "chip" and inv is state.inventory and target is not None:
            if target.chip:                              # v0.6 M2: Shift+clique no chip encaixa na máquina aberta
                self.show_notice("Essa máquina já tem chip")
            else:
                state.chip_install_from(target, i)       # o som sai do evento chip_on
            return
        if self.open_drill is not None:                  # a drill só produz: só dá pra tirar dela
            drill = self.open_drill
            if inv is drill.storage:
                moved = state.drill_take(drill, i, amount)
                if moved:
                    self.audio.play("inv_move")
            else:
                self.show_notice("A drill só produz: não guarda nada")
            return
        if self.open_melter is not None:                 # gelo entra na entrada, a cápsula (e o gelo) sai
            melter = self.open_melter
            if inv is melter.storage:
                moved = state.melter_take(melter, i, amount)
            elif item != "ice":
                self.show_notice("O derretedor só aceita gelo")
                return
            else:
                moved = state.melter_put(melter, i, amount)
                if not moved:
                    self.show_notice("Entrada de gelo cheia")
            if moved:
                self.audio.play("inv_move")
            return
        if self.open_smelter is not None:                # minério e magmatita entram, o lingote (e o resto) sai
            smelter = self.open_smelter
            if inv is smelter.storage:
                moved = state.melter_take(smelter, i, amount)
            elif item not in C.SMELTER_RECIPES and item != C.SMELTER_FUEL:
                self.show_notice("A Fundição só aceita ferro, cobre e magmatita")
                return
            else:
                moved = state.smelter_put(smelter, i, amount)
                if not moved:
                    have = smelter.storage.slots[C.SMELTER_ORE_SLOT]
                    self.show_notice("Tire o minério que está na Fundição antes"
                                     if item in C.SMELTER_RECIPES and have is not None and have.item != item
                                     else "Slot da Fundição cheio")
            if moved:
                self.audio.play("inv_move")
            return
        if self.open_collector is not None:              # v0.8 M2: só entra cápsula vazia; a cheia (e a vazia) sai
            collector = self.open_collector
            if inv is collector.storage:
                moved = state.melter_take(collector, i, amount)
            elif item != C.EMPTY_CAPSULE:
                self.show_notice("O Coletor só aceita cápsula vazia")
                return
            else:
                moved = state.collector_put(collector, i, amount)
                if not moved:
                    self.show_notice("Entrada de vazias cheia")
            if moved:
                self.audio.play("inv_move")
            return
        if self.open_cultivator is not None:             # v0.8 M3: cápsula cheia e muda entram; a colheita, as vazias e a muda saem
            cult = self.open_cultivator
            if inv is cult.storage:
                moved = state.melter_take(cult, i, amount)
            elif item != "water_capsule" and item not in C.CROP_ITEMS:
                self.show_notice("O Cultivador só aceita cápsula de água e muda")
                return
            else:
                moved = state.cultivator_put(cult, i, amount)
                if not moved:
                    self.show_notice("Reserva de água cheia" if item == "water_capsule" else "Essa muda já está plantada")
            if moved:
                self.audio.play("inv_move")
            return
        if self.open_dispenser is not None:              # só entra cápsula de água; a que está no slot volta pro player
            dispenser = self.open_dispenser
            if inv is dispenser.storage:
                moved = state.melter_take(dispenser, i, amount)
            elif item != "water_capsule":
                self.show_notice("O Dispersor só aceita cápsula de água")
                return
            else:
                moved = state.dispenser_put(dispenser, i, amount)
                if not moved:
                    self.show_notice("Slot de cápsula cheio")
            if moved:
                self.audio.play("inv_move")
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
        elif action == "take_melter" and self.open_melter is not None:
            moved = state.melter_take(self.open_melter)
        elif action == "take_smelter" and self.open_smelter is not None:
            moved = state.melter_take(self.open_smelter)
        elif action == "take_collector" and self.open_collector is not None:
            moved = state.melter_take(self.open_collector)
        elif action == "take_cultivator" and self.open_cultivator is not None:
            moved = state.cultivator_take_all(self.open_cultivator)       # a colheita e as vazias; a muda e a água ficam
        elif action == "take_dispenser" and self.open_dispenser is not None:
            moved = state.melter_take(self.open_dispenser)
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
        hit = (ui.logistics_at(mouse_ui)
               if (self.open_chest or self.open_drill or self.open_melter or self.open_smelter or self.open_collector
                   or self.open_cultivator) is not None else None)
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
        side = (self.open_chest or self.open_drill or self.open_melter or self.open_smelter or self.open_collector
                or self.open_cultivator or self.open_dispenser)
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

    def melter_status(self) -> str:
        """Linha de estado no painel do derretedor: "1 A CADA 20 S", "SEM GELO", "SAÍDA CHEIA"."""
        melter = self.open_melter
        if melter.capsules_full:
            return "SAÍDA CHEIA"
        if melter.ice < C.MELTER_ICE_PER_CAPSULE:
            return "SEM GELO"
        text = f"1 A CADA {C.MELTER_CAPSULE_TIME[melter.kind]:g} S"
        if self.state.power.deficit:
            text += f" · RITMO {self.power_percent()}%"
        return text

    def smelter_status(self) -> str:
        """Linha de estado no painel da Fundição: "3:1 A CADA 15 S", "SEM MINÉRIO", "SEM MAGMATITA", "SAÍDA OCUPADA"..."""
        label = {"no_ore": "SEM MINÉRIO", "no_fuel": "SEM MAGMATITA", "out_busy": "SAÍDA OCUPADA",
                 "out_full": "SAÍDA CHEIA"}.get(self.open_smelter.smelter_blocker)
        if label is not None:
            return label
        text = f"{C.SMELTER_ORE_PER_INGOT}:1 A CADA {C.SMELTER_TIME:g} S"
        if self.state.power.deficit:
            text += f" · RITMO {self.power_percent()}%"
        return text

    def cultivator_label(self, m) -> str:
        """O estado do Cultivador em palavras curtas (painel e dica do mouse; v0.8 M3)."""
        blocker = self.state.cultivator_blocker(m, self.state.active)
        return {None: "Crescendo", "no_seed": "Sem muda", "no_base": "Fora da base vedada", "dry": "Sem água",
                "full": "Colheita cheia"}[blocker]

    def cultivator_status(self) -> str:
        """Linha de estado no painel do Cultivador: "Crescendo" ou o que trava."""
        return self.cultivator_label(self.open_cultivator)

    def collector_status(self) -> str:
        """Linha de estado no painel do Coletor: "COLETANDO" ou o que trava (curto: a barra é estreita; v0.8 M2)."""
        blocker = self.state.collector_blocker(self.open_collector, self.state.active)
        return {None: "COLETANDO", "cave": "PARADO", "stage": "PARADO", "no_empty": "SEM VAZIA",
                "out_full": "SAÍDA CHEIA"}[blocker]

    def collector_info(self) -> str:
        """Embaixo da barra do painel do Coletor: o motivo da parada ou o ritmo ("1 cápsula a cada 40 s" e, chovendo,
        " · chuva x2.5"). v0.8 M2."""
        m, state = self.open_collector, self.state
        blocker = state.collector_blocker(m, state.active)
        if blocker == "cave":
            return "Só funciona na superfície: lá em cima o ar tem umidade."
        if blocker == "stage":
            return "Precisa do estágio Úmido: antes disso o ar é seco demais."
        rain = state.collector_rain(m, state.active)
        text = f"1 cápsula a cada {collector_time(rain):.0f} s"
        if rain > 0:
            text += f" · chuva x{1 + C.COLLECTOR_RAIN_BONUS * rain:.1f}"
        if state.power.deficit:
            text += f" · ritmo {self.power_percent()}%"
        return text

    def dispenser_status(self) -> str:
        """Linha de estado no painel do Dispersor: "VEDADO ✓", "VAZAMENTO", "SEM ÁGUA", "SEM ENERGIA"..."""
        return C.STATE_LABEL[self.state.dispenser_state(self.open_dispenser)].upper()

    def dispenser_info(self) -> str:
        """A explicação do estado no painel do Dispersor."""
        m = self.open_dispenser
        seal = self.state.seal_of(m)
        state = self.state.dispenser_state(m)
        n = len(seal.floor)
        if seal.ok:                                              # v0.8 M2: a cápsula dura conforme o tamanho da base
            time_line = f"1 cápsula = {capsule_time_text(dispenser_capsule_time(n))} nesta base."
        else:
            time_line = "1 cápsula: vede a base pra calcular."
        return {
            "sealed": f"Base vedada: {n} tiles de chão, {seal.doors} porta(s). {time_line}",
            "leak": f"Furo na parede (o tile pisca no mundo): feche com parede ou porta. {time_line}",
            "small": f"Base pequena: precisa de {C.BASE_MIN_FLOOR}+ tiles de chão ({n} agora).",
            "nodoor": "A base precisa de pelo menos 1 porta.",
            "big": f"Base grande demais (no máximo {C.BASE_MAX_FLOOR} tiles de chão).",
            "nofloor": "Ponha chão da base debaixo do Dispersor.",
            "dry": f"Ponha uma cápsula de água no slot (o derretedor faz). {time_line}",
            "nopower": f"Falta energia na rede ({energy.machine_use(m.kind):g} kW). {time_line}",
        }[state]

    def dispenser_labels(self) -> list:
        """(Dispersor, estado, hover): o de baixo do mouse mostra o estado escrito; os outros só aparecem parados por
        problema (o selo "!"). Vedado sem hover não aparece. Pedido do dono, v0.6 M2."""
        factor, hovered = self.state.power.factor, self.hovered_machine()
        out = []
        for m in self.state.machines:
            if not m.is_dispenser or m.build > 0 or m.submerged:
                continue
            st = self.state.dispenser_state(m, factor)
            if m is hovered or st != "sealed":
                out.append((m, st, m is hovered))
        return out

    def labeled_chests(self) -> list:
        """Baús que mostram o rótulo flutuante (↓recebe ↑envia Nome): só o que está debaixo do mouse."""
        chest = self.hovered_machine()
        return [chest] if chest is not None and chest.is_chest else []

    def stash_held(self) -> bool:
        """Devolve a pilha da mão pro inventário (ou pro baú / caixa / contêiner aberto). False se não coube tudo."""
        if self.held is None:
            return True
        left = self.state.inventory.add(self.held.item, self.held.count)
        box = self.open_chest or self.open_crate
        if left and box is not None:
            left = box.storage.add(self.held.item, left)
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
        if button == 3 and self.mode == "play":   # v0.5 M1: o clique rápido não faz nada; segurar desmonta
            self.right_held = True                # (quem enche a barrinha é o state, pelo Controls.dismantle)
            return
        if button != 1:
            return
        if self.mode in ("fabricator", "build"):
            menu = self.menu_of_mode()
            ux, uy = self.mouse_ui
            for rect, index in self.ui.fabricator_tabs:
                if rect.collidepoint(ux, uy):
                    if index != menu.tab:
                        menu.set_tab(index)
                        self.audio.play("ui_click")
                    return
            self.on_craft_click((ux, uy), menu)            # a lista pode estar rolada: acha pelo tipo
        elif self.mode == "play":
            if self.placing:                      # constrói e continua no modo (sem material: fantasma vermelho)
                tile = self.place_target()
                if tile is not None:
                    self.state.build(self.placing, tile, self.rotation)
            else:
                self.mouse_held = True

    def set_mode(self, mode: str) -> None:
        if self.mode in INVENTORY_MODES and mode != self.mode:
            self.finish_name_edit(confirm=True)
            self.stash_held()            # devolve a pilha da mão (se não couber, ela espera o próximo Tab)
            self.open_station = self.open_drill = self.open_melter = self.open_smelter = self.open_dispenser = None
            self.open_collector = self.open_cultivator = None
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
            self.audio.play("ui_open" if mode in ("fabricator", "build", "pause", "inventory", "station", "drill", "melter",
                                                  "smelter", "collector", "cultivator", "dispenser")
                            else "ui_close")
        self.mode = mode
        self.mouse_held = False
        if mode != "play":
            self.right_held = False

    def try_craft(self, kind: str, batch: bool = False) -> None:
        """Fabrica 1 (ou, com Shift, até C.CRAFT_BATCH: para quando faltar recurso). O lote mostra "Drone x5".
        Fabricou: o painel continua aberto pra fabricar mais (v0.6 Fundo M5, pedido do dono) e, se o item caiu na
        hotbar, seleciona o slot."""
        bench = self.fab_bench if self.mode == "fabricator" else "t1"
        at = self.open_bench if bench == "t2" else None            # a Bancada T2 anima enquanto fabrica
        made = self.state.craft_many(kind, bench=bench, at=at) if batch else int(self.state.craft(kind, bench, at))
        if batch and made:
            self.show_toast(f"{item_name(kind)} x{made}")
        if made:
            self.rotation = 0
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
        scan = self.hovered_prop() if self.mouse_held and not self.placing and self.constructor_selected() else None   # v0.7 M2
        dismantle = ((self.hovered_prop(own=True) or self.hovered_machine() or self.hovered_block() or self.hovered_crate())   # v0.6: só com o construtor na mão; v0.7 M2: prop primeiro
                     if self.right_held and not self.placing and self.constructor_selected() else None)
        return Controls(max(-1, min(1, mx)), max(-1, min(1, my)), mine, dismantle=dismantle, scan=scan,
                        drill_in_hand=self.hand_drill_selected(), drill_tier=max(1, self.held_drill_tier()))

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
        # construindo: o construtor tem que continuar no slot selecionado (pode ter sido movido no Tab)
        if self.placing and not self.constructor_selected():
            self.placing = None
        self.notice_time = max(0.0, self.notice_time - dt)
        self.toast_time = max(0.0, self.toast_time - dt)
        self.thaw_notice_time = max(0.0, self.thaw_notice_time - dt)
        self.objective_hint_time = max(0.0, self.objective_hint_time - dt)
        self.blueprint_notice_time = max(0.0, self.blueprint_notice_time - dt)
        self.blueprint_duck = max(0.0, self.blueprint_duck - dt)
        self.banner_time += dt
        self.renderer.machine_t += dt * self.state.power.factor    # animação das máquinas no ritmo da energia
        self.floaters.update(dt)
        self.floaters.scale = self.zoom * self.ui.canvas_k     # faixas dos floaters em px da tela
        self.renderer.update_particles(dt)
        spark = self.renderer.update_door_fx(self.state, dt)         # v0.7 M4: faísca da porta emperrada
        if spark is not None and self.audio.has("spark"):
            p = self.state.player
            gain = sound.fade_by_distance(math.hypot(spark[0] - p.x, spark[1] - p.y) / C.TILE, 1.5, 5.5)
            self.audio.play("spark", gain=gain)
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
        hint = self.objectives.take_hint()
        if hint:                                  # objetivo com dica virou o atual (magmatita): aviso embaixo dele
            self.objective_hint, self.objective_hint_time = hint, C.OBJECTIVE_HINT_TIME

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
        elif kind == "smelter_done":            # v0.6 Fundo M3: saiu um lingote (só a Fundição desta camada soa)
            smelter = event[1]
            if any(m is smelter for m in self.state.machines):
                distance = self.state.drill_distance(smelter) / C.TILE
                self.audio.play("smelter_done", gain=sound.smelter_done_gain(distance))
        elif kind == "dismantle":
            _, _, tile = event
            self.renderer.spawn_chips(tile, "#9a9086", 14)       # poeirinha
            self.renderer.spawn_chips(tile, "#c8c0b4", 8)
            if event[1] not in C.BASE_KINDS and event[1] != "crate" and event[1] not in C.PLAYER_PROPS:
                self.renderer.start_blink(tile, self.t)          # o holograma dela pisca e some (bloco da base não tem)
            # v0.5 M1: o dismantle_done (Som) entra no mesmo frame, sem cortar o charge; sem o arquivo, o place_low
            self.audio.play("dismantle_done" if self.audio.has("dismantle_done") else "place_low")
        elif kind == "door":                  # v0.5 M2: a porta começou a abrir / fechou de vez (Som: pitch variado)
            self.audio.play("door_open" if event[1] == "open" else "door_close", gain=self.sound_gain_at(event[2], *C.DOOR_VOLUME_RANGE))
        elif kind == "base_sealed":           # a base virou vedada (nunca no load; cooldown de 3 s no state)
            self.audio.play("base_sealed", gain=self.sound_gain_at(event[1], 6, 20))
        elif kind == "leak_alert":            # a cada 4 s enquanto vaza, com o player por perto
            self.audio.play("leak_alert")
        elif kind == "dispenser_dry":         # acabou a última cápsula: uma vez; o zumbido sai em 0,3 s
            self.dry_fade_t = 1.0
            self.audio.play("dispenser_dry", gain=self.sound_gain_at(event[1], 6, 20))
        elif kind == "harvest":               # v0.8 M3: o Cultivador colheu (aviso flutuante em cima dele, se for desta camada)
            _, machine, crop, n = event
            if n and any(m is machine for m in self.state.machines):
                ax, ay = machine.anchor
                self.floaters.add(f"+{n} {C.RESOURCE_LABEL[crop]}", ax, ay - 64, C.ORE_COLORS[crop][0])
        elif kind == "dismantle_charge":      # começou a encher a barrinha do desmonte
            self.audio.start_charge()
        elif kind == "dismantle_cancel":      # soltou antes (ou tirou o mouse): o charge sai em fadeout curto
            self.audio.stop_charge()
        elif kind == "scan_charge":           # v0.7 M2: começou a escanear um prop de ruína (o sweep do scan_loop, 1x)
            self.audio.start_scan()
        elif kind == "scan_cancel":
            self.audio.stop_scan()
        elif kind == "scan_done":             # projeto liberado: para o loop, toca o done e avisa
            self.audio.stop_scan()
            self.audio.play("scan_done")
            self.show_notice(f"Projeto liberado: {C.BLUEPRINTS[event[1]] if event[1] in C.BLUEPRINTS else C.PROPS[event[1]].name}")
        elif kind in ("chip_on", "chip_off"):    # v0.6 M2: encaixar/tirar o chip (nunca no load do save: ele não solta evento)
            sfx = "chip_connect" if kind == "chip_on" else "chip_disconnect"
            self.audio.play(sfx if self.audio.has(sfx) else "ui_click")
        elif kind in ("crate_open", "container_open"):   # caixa de saque / contêiner (vazia: mais baixo, dica do Som)
            sfx = "container_open" if kind == "container_open" and self.audio.has("container_open") else "crate_open"
            self.audio.play(sfx, gain=0.67 if event[1] else 1.0)
            self.crate_open_t = self.t
        elif kind == "diagram_read":          # lido na bancada: som calmo e o aviso
            self.audio.play("diagram_read")
            self.show_notice(f"Receita liberada: {C.BLUEPRINTS[event[1]]}")
        elif kind == "diagram_found":         # diagrama achado: aviso, jingle 0,4 s depois do crate_open, ambiente a 60%
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
                self.play_ice_break(collapse=True)
        elif kind == "lab_ice_open":          # v0.8 M3: o gelo da porta do laboratório cedeu
            for tile in ruins.lab_door_tiles(self.state.surface.world):
                self.renderer.minimap.repaint(self.state, tile, "surface")
            self.show_toast(C.LAB_ICE_NOTICE, C.THAW_GATE_NOTICE_TIME)
            self.play_ice_break(collapse=True)
        elif kind == "giant_gate_thaw":       # v0.5 M3.6.3: o portão grande começou a derreter (1) ou abriu a fresta (3)
            if event[1] >= 3:                     # v0.5 M3.6.4: abriu. O mapa mostra o interior e o gelo gigante, a névoa
                geo = self.state.surface.geo      # se dissipa (renderer, pocket_fog) e sai a mensagem (a pílula da cratera)
                for tile in [*ice_blocks.gate_tiles(geo, ice_blocks.gate_count(geo) - 1), *geo.giant.interior,
                             *geo.giant.giant.tiles]:
                    self.renderer.minimap.repaint(self.state, tile, "surface")
                self.show_thaw_notice(C.GIANT_OPEN_NOTICE)
                self.play_ice_break(collapse=True)
        elif kind == "gust":                  # rajada começou (tempestade): volume pelo storm, sem gust.wav fica mudo
            self.audio.play("gust", gain=sound.gust_gain(event[1]))
        elif kind == "crater_thaw":           # v0.4 M3.1: a tampa baixou uma etapa (etapa 4 = a cratera abriu)
            opened = event[1] >= C.CRATER_ICE_STAGES
            self.show_thaw_notice(CRATER_OPEN_TEXT if opened else CRATER_THAW_TEXT)
            self.play_ice_break(collapse=opened)
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
        elif kind == "backpack_not_empty":
            self.show_notice("Esvazie a mochila primeiro")
        elif kind == "crate_not_empty":
            self.show_notice("Esvazie a caixa antes de desmontar")
        elif kind == "chest_not_empty":
            self.show_notice("Esvazie o baú antes de desmontar")
        elif kind == "craft":
            self.audio.play("craft")
        elif kind == "power_low":             # o déficit de energia começou (sem o arquivo, fica em silêncio)
            self.audio.play("power_low")
        elif kind == "build":                 # v0.5 M1: construiu (o scanner começa); sem o build.wav, o place de sempre
            if self.audio.has("build"):
                self.audio.play("build")
            else:
                self.audio.play("lamp_place" if event[1] == "lamp" and self.audio.has("lamp_place") else "place")
        elif kind == "ramp":                  # começou a descer/subir: passos na rampa (sem arquivo, silêncio)
            self.audio.play("ramp_down" if event[1] in ("cave", "vesper") else "ramp_up")
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
            if event[1] == C.ARID_STAGE and self.state.layer == "surface":
                self.audio.play("sky_clear", delay=SKY_CLEAR_DELAY)   # a última lufada indo embora (Som v9)
            if event[1] == C.GREEN_STAGE:      # fim do jogo
                self.end_timer = END_SCREEN_DELAY

    def play_ice_break(self, collapse: bool) -> None:
        """Gelo quebrando: estalo (ice_crack, sorteia entre as 2 variações sem repetir) ou desabamento (ice_collapse)."""
        if collapse:
            self.audio.play("ice_collapse", gain=sound.ice_collapse_gain(self.state.layer in ("cave", "vesper")))
        else:
            self.audio.play("ice_crack")

    def sound_gain_at(self, pos, full_until: float, silent_from: float) -> float:
        """Volume de um som que veio de `pos` (px do mundo): inteiro até `full_until` tiles do player, some em `silent_from`."""
        p = self.state.player
        return sound.fade_by_distance(math.hypot(pos[0] - p.x, pos[1] - p.y) / C.TILE, full_until, silent_from)

    def update_ambient_sounds(self, dt: float) -> None:
        state, audio = self.state, self.audio
        # alarme com histerese: liga abaixo de 25%, desliga em 27% (ou desmaiado)
        o2_percent = 100 * state.o2 / C.O2_MAX
        audio.set_alarm(not state.fainted and sound.alarm_should_play(audio.alarm_on, o2_percent))
        # zumbido pela máquina mais próxima
        nearest = min((math.hypot((m.tx + 0.5) * C.TILE - state.player.x, (m.ty + 1) * C.TILE - state.player.y) / C.TILE
                       for m in state.machines if m.type.index is not None and not m.broken), default=None)
        in_sealed = state.in_sealed_base()
        audio.set_hum(0.0 if in_sealed else sound.hum_volume(nearest))   # dentro da base vedada, o hum do Dispersor entra no lugar
        self.dry_fade_t = max(0.0, self.dry_fade_t - dt)
        audio.set_dispenser_hum(C.VOLUME["dispenser_hum"] if in_sealed else 0.0,
                                C.DISPENSER_HUM_DRY_FADE_MS if self.dry_fade_t > 0 else C.DISPENSER_HUM_FADE_MS)
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
        audio.set_rain(sound.rain_volume(rain_level(state)), state.rain.variant)   # chuva (M3.3): só na superfície
        # chiado da fumarola acordada mais perto (v11): só na superfície; dormente não entra no cálculo
        vent = state.vent_distance() if self.ambient_layer() == "surface" else None
        audio.set_vent(sound.vent_hiss_volume(vent))
        self.update_cave_biome(dt)
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

    def update_cave_biome(self, dt: float) -> None:
        """Região da caverna que manda no ambiente (histerese em audio.CaveRegionPicker). Descendo, a chegada é no
        centro (stable None toca amb_cave); já lá embaixo, o primeiro quadro toca o bioma do ponto sem esperar."""
        state = self.state
        if self.ambient_layer() != "cave":
            self.cave_amb.reset(None)
        elif state.layer == "cave":
            i = state.world.region_at_cave(*state.player.tile)
            name = REGION_NAMES[i] if i is not None else None
            if self.cave_amb.stable is None:
                self.cave_amb.reset(name)
            else:
                self.cave_amb.update(name, dt)

    def ambient_want(self, stage: int | None = None) -> str:
        """Ambiente que deveria tocar agora (game/audio.ambient_for)."""
        key = stage_key(stage or self.state.stage)
        region = self.cave_amb.stable
        if region and not self.audio.has(f"amb_cave_{region}"):
            region = None
        return sound.ambient_for(self.ambient_layer(), key, self.audio.has("amb_cave"), self.audio.has("amb_storm"),
                                 cave_region=region, has_vesper=self.audio.has("amb_vesper"))

    def update_drills_feedback(self, dt: float) -> None:
        """Som e poeira das drills: loop pelas 2 trabalhando mais perto, aviso de cheia, poeirinha na base."""
        state = self.state
        working = sorted(state.drill_distance(d) / C.TILE for d in state.drills if not d.full)
        self.audio.set_drill_loops([sound.drill_loop_volume(d) for d in working[:2]])
        smelting = sorted(state.drill_distance(m) / C.TILE for m in state.machines            # v0.6 Fundo M3
                          if m.is_smelter and m.build <= 0 and not m.submerged and m.smelter_blocker is None)
        on = state.power.factor > 0
        self.audio.set_smelter_loops([sound.smelter_loop_volume(d) for d in smelting[:2]] if on else [])
        collecting = [state.drill_distance(m) / C.TILE for m in state.machines              # v0.8 M2: o gotejar do Coletor
                      if m.is_collector and m.build <= 0 and not m.submerged and m.collecting]
        self.audio.set_collector_loop(sound.collector_loop_volume(min(collecting)) if collecting and on else 0.0)
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
            if m.type.index is not None and not m.submerged and not m.broken and (t - dt + phase) % period > (t + phase) % period:
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

    def hovered_prop(self, own: bool = False):
        """Prop debaixo do mouse (v0.7 M2). `own`: só o do player (o de ruína não desmonta e não pode tapar a máquina atrás)."""
        prop = self.state.prop_at_point(*self.mouse_world())
        return prop if prop is not None and not (own and prop.ruin) else None

    def hovered_machine(self):
        return self.state.machine_at_point(*self.mouse_world())

    def hovered_crate(self):
        """Caixa de saque de destroço debaixo do mouse (v0.6 M1: a única caixa que desmonta; contêiner não)."""
        hover = self.state.interactable_at(*self.mouse_world())
        return hover[1] if hover is not None and hover[0] == "crate" else None

    def hovered_block(self):
        """Bloco da base (chão, parede, porta) debaixo do mouse; a máquina em cima do chão tem prioridade (hovered_machine)."""
        return self.state.block_at_point(*self.mouse_world())

    def use_fixture(self, tile) -> None:
        """E num fixture da VÉSPER-7 (v0.7 M4): o texto vira aviso (~3 s). Porta emperrada faz tunk (cooldown 0,4 s);
        painel sem bateria faz power_low. Sem o WAV, fica em silêncio."""
        kind = self.state.world.fixtures.get(tuple(tile))
        if kind not in C.VESPER_FIXTURE_TEXT:
            return
        self.show_toast(self.state.fixture_text(kind), 3.0)
        if kind == "jammed_door" and self.t - self.door_stuck_at >= DOOR_STUCK_COOLDOWN and self.audio.has("door_stuck"):
            self.door_stuck_at = self.t
            self.audio.play("door_stuck")
        elif kind == "power_panel" and self.audio.has("power_low"):
            self.audio.play("power_low")

    def e_target(self) -> tuple[str, object] | None:
        """O que o E abre agora: o interagível debaixo do mouse, se estiver no alcance; senão o mais
        perto do player (None = nada; aí, na base, o E abre o fabricador)."""
        return self.state.interaction(self.state.interactable_at(*self.mouse_world()))

    def crater_ice_hint(self) -> str:
        """Tampa de gelo da cratera: quanto calor falta pra abrir (o último marco de C.THAW_CRATER_HEAT)."""
        need, now = C.THAW_CRATER_HEAT[-1], self.state.indices["heat"]
        return f"{CRATER_ICE_HINT} · abre com {fmt(need)} pK (agora {fmt(now)})"

    def gate_under_mouse(self) -> int | None:
        """Índice do gelo-portão (geo.pockets) debaixo do mouse, enquanto ainda tem bloco de gelo: a caixa do portão
        e uns tiles pra cima (os blocos são altos)."""
        layer = self.state.active
        geo = getattr(layer, "geo", None)
        if geo is None:
            return None
        mx, my = self.mouse_world()
        T = C.TILE
        for i in range(ice_blocks.gate_count(geo)):          # os dos bolsões e, por último, o grande (M3.6.3)
            if not any(b.gate == i for b in layer.gate_blocks):
                continue
            tiles = ice_blocks.gate_tiles(geo, i)
            xs = [x for x, _ in tiles]
            ys = [y for _, y in tiles]
            x0, x1, y1 = min(xs) * T, (max(xs) + 1) * T, (max(ys) + 1) * T
            if x0 <= mx < x1 and y1 - C.GATE_HINT_HEIGHT_TILES * T <= my < y1:
                return i
        return None

    def lab_ice_under_mouse(self) -> bool:
        """v0.8 M3: o mouse está em cima do gelo da porta do laboratório (enquanto ainda tem bloco)."""
        layer = self.state.active
        if not any(b.gate == ice_blocks.LAB_GATE for b in layer.gate_blocks):
            return False
        tiles = ruins.lab_door_tiles(layer.world)
        mx, my = self.mouse_world()
        T = C.TILE
        x0, x1, y1 = min(x for x, _ in tiles) * T, (max(x for x, _ in tiles) + 1) * T, (max(y for _, y in tiles) + 1) * T
        return x0 <= mx < x1 and y1 - C.GATE_HINT_HEIGHT_TILES * T <= my < y1

    def lab_ice_hint(self) -> str:
        """Gelo da porta do laboratório: o calor em que a fresta abre e o calor de agora."""
        lo, hi = C.LAB_ICE_HEAT
        need = lo + self.state.active.lab_ice_opens_at * (hi - lo)
        return f"Gelo · a porta do laboratório abre com ~{fmt(need)} pK (agora {fmt(self.state.indices['heat'])})"

    def gate_ice_hint(self, i: int) -> str:
        """Gelo-portão: o calor em que a fresta abre (o p da receita no calor do portão) e o calor de agora."""
        layer, heat = self.state.active, self.state.indices["heat"]
        giant = ice_blocks.is_giant_gate(layer.geo, i)     # M3.6.3: o portão grande tem nome e marcos próprios
        name = "Grande gelo" if giant else "Gelo-portão"
        if i < len(layer.gate_ice) and layer.gate_ice[i] >= thaw.GATE_OPEN:
            return f"{name} · a passagem já abriu"
        marks = C.THAW_GIANT_HEAT if giant else C.THAW_GATE_HEAT[min(i, len(C.THAW_GATE_HEAT) - 1)]
        need = marks[0] + ice_blocks.opens_at(layer.gate_recipes[i]) * (marks[-1] - marks[0])
        return f"{name} · a passagem abre com ~{fmt(need)} pK (agora {fmt(heat)})"

    def hint(self) -> str | None:
        state = self.state
        if self.placing == "drill" and self.place_target() is None:
            return "Coloque a drill em cima de um veio"
        target_tile = self.place_target() if self.placing else None
        if target_tile is not None and state.world.is_water(*target_tile, state.stage):   # v0.4 M3.4
            return "Não dá pra construir na água · Esc cancela"
        if self.placing and not state.active.buildable:    # v0.7 M4: dentro da VÉSPER-7
            return "Não dá pra construir aqui · Esc cancela"
        if self.placing:
            missing = self.build_missing(self.placing)
            if missing:                                    # v0.5 M1: sem material, o fantasma fica vermelho
                return f"{missing} · Esc cancela"
        if self.placing == "drone_station":
            return "Clique para construir · drones atendem esta camada · Esc cancela"
        if self.placing in C.PLAYER_PROPS:
            return "Clique para construir · [E] outro projeto · Esc cancela"
        if self.placing:
            return "Clique para construir · R gira · [E] outra máquina · Esc cancela"
        prop = self.hovered_prop()
        if prop is not None:                               # v0.7 M2: decoração debaixo do mouse
            if self.constructor_selected() and state.can_scan(prop):
                return "Escanear (segure)"
            if not prop.ruin:
                return f"{C.PROPS[prop.kind].name} · " + (f"segure [{C.DISMANTLE_KEY}] desmontar" if self.constructor_selected()
                                                          and state.can_dismantle(prop) else "construtor na mão pra desmontar")
        machine = self.hovered_machine()
        target = self.e_target()
        held = self.constructor_selected()                 # v0.6: desmontar só com o construtor na mão
        can_dis = lambda m: held and state.can_dismantle(m)   # noqa: E731
        far = "chegue mais perto pra" if held else "construtor na mão pra"   # o porquê de não dar
        # mouse numa máquina que o E não vai abrir (longe, ou outra está no alcance): diz qual ele abre
        other = f" · {self.e_label(target)}" if target and target[1] is not machine else ""
        if machine and machine.submerged:                  # v0.4 M3.4: parada debaixo d'água
            if target and target[1] is machine:
                return self.e_label(target) + (f" · segure [{C.DISMANTLE_KEY}] recolher" if held else "")
            return (f"Submersa · segure [{C.DISMANTLE_KEY}] recolher" if can_dis(machine)
                    else f"Submersa · {far} recolher")
        if machine and machine.build > 0:                  # v0.5 M1: ainda se construindo
            return f"{C.MACHINES[machine.kind].name} · construindo..."
        if machine and machine.is_drill:
            label = C.RESOURCE_NAME[machine.resource]
            content = (f"Drill cheia: {machine.stored} {label}" if machine.full
                       else f"Drill: {machine.stored}/{C.DRILL_CAPACITY} {label}")
            if state.power.deficit and not machine.full:
                content += f" · ritmo {self.power_percent()}%"
            return content + (" · [E] abrir · [Shift+E] coletar" if target and target[1] is machine else other)
        if machine and machine.is_melter:                  # v0.5 M2: gelo dentro, cápsulas prontas
            content = f"{C.MACHINES[machine.kind].name}: {machine.ice} gelo · {machine.capsules} cápsula(s)"
            return content + (" · [E] abrir" if target and target[1] is machine else other)
        if machine and machine.is_smelter:                 # v0.6 Fundo M3: minério, magmatita e lingotes dentro
            ore = machine.storage.slots[C.SMELTER_ORE_SLOT]
            ore_text = f"{ore.count} {C.RESOURCE_NAME[ore.item]}" if ore else "sem minério"
            out = machine.storage.slots[C.SMELTER_OUT_SLOT]
            content = (f"Fundição: {ore_text} · {machine.storage.count(C.SMELTER_FUEL)} magmatita"
                       f" · {out.count if out else 0} pronto(s)")
            return content + (" · [E] abrir" if target and target[1] is machine else other)
        if machine and machine.is_collector:               # v0.8 M2: vazias e cheias dentro
            content = (f"Coletor: {machine.storage.count(C.EMPTY_CAPSULE)} vazia(s)"
                       f" · {machine.storage.count('water_capsule')} cheia(s)")
            return content + (" · [E] abrir" if target and target[1] is machine else other)
        if machine and machine.is_cultivator:              # v0.8 M3: a cultura, a etapa e o estado
            state.cultivator_blocker(machine, state.active)
            plant = (f"{C.CROP_NAME[machine.crop]} · etapa {machine.crop_stage + 1}/4" if machine.crop else "sem muda")
            content = f"Cultivador: {plant} · {self.cultivator_label(machine).lower()}"
            return content + (" · [E] abrir" if target and target[1] is machine else other)
        if machine and machine.is_dispenser:               # v0.5 M2: estado da vedação e da água
            content = f"Dispersor de O₂: {C.STATE_LABEL[state.dispenser_state(machine)]}"
            return content + (" · [E] abrir" if target and target[1] is machine else other) + (
                f" · segure [{C.DISMANTLE_KEY}] desmontar" if can_dis(machine) else "")
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
            return f"{machine.name or C.CHEST_DEFAULT_NAME} ({used}/{len(machine.storage)})" + (" · [E] abrir" if mine else other)
        if machine and machine.is_bench:
            mine = target is not None and target[1] is machine
            return "Bancada T2" + (" · [E] abrir" if mine else other) + (
                f" · segure [{C.DISMANTLE_KEY}] desmontar" if can_dis(machine) else "")
        if machine:
            if state.power.deficit and energy.machine_use(machine.kind) > 0:     # no déficit: mostra o ritmo
                rhythm = f"Ritmo {self.power_percent()}%"
                return (f"{rhythm} · segure [{C.DISMANTLE_KEY}] desmontar" if can_dis(machine)
                        else f"{rhythm} (falta energia)")
            return (f"Segure [{C.DISMANTLE_KEY}] para desmontar" if can_dis(machine)
                    else f"{far.capitalize()} desmontar")
        hover_fx = state.interactable_at(*self.mouse_world())    # v0.7 M4: fixture/escotilha da VÉSPER-7 sob o mouse, no alcance
        if hover_fx is not None and hover_fx[0] in ("fixture", "hatch_out") and target == hover_fx:
            return self.e_label(target)
        block = self.hovered_block()                        # v0.5 M2: chão, parede ou porta da base
        if block and not block.ruin:                        # (a casca de ruína e da nave não desmonta: sem dica)
            name = C.MACHINES[block.kind].name
            return f"{name} · " + (f"segure [{C.DISMANTLE_KEY}] desmontar" if can_dis(block)
                                   else f"{far} desmontar")
        vein = state.world.vein_at(*self.mouse_tile())     # mouse em cima de um veio livre
        if vein:
            name = C.RESOURCE_NAME[vein.resource]
            unlocked = state.recipe_status("drill") != "locked"
            return f"Veio de {name} · " + ("coloque uma drill" if unlocked else "drill libera no Úmido")
        hover = state.interactable_at(*self.mouse_world())
        wreck = state.world.wreck_at_px(*self.mouse_world())
        if wreck is not None and hover is None:                         # corpo do destroço (não a caixa/terminal)
            return f"{wreck.name} · destroço" + (f" · {self.e_label(target)}" if target else "")
        if target and target[0] == "crate" and target[1].empty and state.can_dismantle(target[1]):   # v0.6 M1
            return self.e_label(target) + (f" · segure [{C.DISMANTLE_KEY}] desmontar" if held
                                           else " · construtor na mão pra desmontar")
        if target:
            return self.e_label(target)
        if hover is not None and hover[0] == "crate":                   # caixa debaixo do mouse, longe
            return "Caixa vazia" if hover[1].empty else "Caixa de saque · chegue mais perto"
        if hover is not None and hover[0] in ("wreck_log", "ruin_log"):
            return "Terminal · chegue mais perto"
        if hover is not None and hover[0] == "container":
            box = state.container_crate(hover[1])
            return "Contêiner aberto" if box is not None and box.opened else "Contêiner lacrado · chegue mais perto"
        gate = self.gate_under_mouse()                    # v0.4 M3.5: gelo-portão debaixo do mouse
        if gate is not None:
            return self.gate_ice_hint(gate)
        if self.lab_ice_under_mouse():                    # v0.8 M3: o gelo da porta do laboratório
            return self.lab_ice_hint()
        tile = self.mouse_tile()
        if state.world.get(*tile) == C.CRATER:            # rampa debaixo do mouse, mas longe
            if state.ramp_blocked():
                return self.crater_ice_hint()
            return ("Cratera · chegue mais perto pra descer" if state.active.has_base
                    else "Rampa · chegue mais perto pra subir")
        if self.constructor_selected():                    # v0.5 M1: construtor na mão, apontando pro nada
            return "[E] Construir"
        if state.in_base_zone():
            return "[E] Fabricador" if self.t > 6 else "As rochas pequenas do deserto têm minério"
        if state.world.is_minable(*tile):
            if not self.hand_drill_selected():              # v0.5 M4: sem a broca na mão, o clique não minera
                return "Selecione a broca de mão pra minerar"
            state.drill_tier = max(1, self.held_drill_tier())   # v0.6 Fundo M4: a dica vale no frame da troca de slot
            if state.hard_blocked(tile):                     # v0.6 Fundo: gelo e basalto da caverna
                return "Rocha dura demais · precisa da broca nv.2"
            if state.world.get(*tile) in C.SMALL_ROCKS:
                name = C.RESOURCE_NAME[C.SMALL_ROCKS[state.world.get(*tile)]]
                return (f"Rocha com {name} · segure o clique para quebrar" if state.can_mine(tile)
                        else f"Rocha com {name} · chegue mais perto")
            return "Segure o clique para minerar" if state.can_mine(tile) else "Chegue mais perto pra minerar"
        return None

    def build_missing(self, kind: str) -> str | None:
        """Por que não dá pra construir essa máquina agora (fora o lugar): "Falta 3 ferro", ou None se dá."""
        state = self.state
        status = state.build_status(kind)
        if status == "missing":
            res = state.missing_resource(kind, inv_only=True)
            short = C.MACHINES[kind].cost[res] - state.available(res, inv_only=True)
            return f"Falta {short} {item_name(res).lower()} no inventário"
        if status == "locked":
            return f"Libera em Ti {fmt(C.MACHINES[kind].unlock_ti)}"
        if status == "blueprint":
            return "Precisa do diagrama"
        if status == "no_constructor":
            return "Sem o construtor"
        return None

    def highlight_target(self):
        """O que ganha o contorno no mundo: o alvo do E, só jogando (sem máquina na mão)."""
        if self.mode != "play" or self.placing or self.state.fainted:
            return None
        if self.constructor_selected():                    # v0.7 M2: o prop de ruína que o scan pode liberar
            prop = self.hovered_prop()
            if prop is not None and self.state.can_scan(prop):
                return prop
        target = self.e_target()
        if target is None:
            return None
        if target[0] == "terminal":
            return "terminal", tuple(self.state.world.terminals[target[1]])
        if target[0] == "ramp":
            return "ramp", target[1]
        if target[0] in ("hatch_in", "hatch_out", "fixture"):
            return target[0], tuple(target[1])
        if target[0] == "wreck_log":
            return "wreck_log", target[1]
        if target[0] == "ruin_log":
            return "ruin_log", tuple(target[1])
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
        if kind == "hatch_in":
            return "[E] Entrar na VÉSPER-7"
        if kind == "hatch_out":
            return "[E] Sair da nave"
        if kind == "fixture":
            return self.state.fixture_text(self.state.world.fixtures[tuple(obj)])
        if kind == "ramp":
            if self.state.ramp_blocked():                 # v0.4: a cratera nasce tampada de gelo
                return self.crater_ice_hint()
            return "[E] Descer pela rampa" if self.state.active.has_base else "[E] Subir pela rampa"
        if kind == "crate":
            return "[E] Abrir caixa" if obj.empty else "[E] Abrir caixa de saque"
        if kind in ("wreck_log", "ruin_log"):
            return "[E] Ler terminal"
        if kind == "container":                       # v0.5 M4
            box = self.state.container_crate(obj)
            if box is not None and box.opened and box.empty:
                return "Contêiner aberto"
            return "[E] Abrir contêiner"
        if kind == "chest":
            name = obj.name or C.CHEST_DEFAULT_NAME
            return "[E] Abrir baú" if name == C.CHEST_DEFAULT_NAME else f"[E] Abrir baú: {name}"
        if kind == "bench":
            return "[E] Bancada T2"
        if kind == "dispenser":
            return "[E] Abrir Dispersor de O₂"
        if kind == "melter":
            return "[E] Abrir derretedor"
        if kind == "smelter":
            return "[E] Abrir Fundição"
        if kind == "collector":
            return "[E] Abrir Coletor de água"
        if kind == "cultivator":
            return "[E] Abrir Cultivador"
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
            ghost = (self.placing, tile, self.rotation,
                     target is not None and state.can_build(self.placing, tile, self.rotation))
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
        icons["water_capsule"] = self.renderer.surface("icon_water_capsule", art.water_capsule_icon)[0]   # rótulo do baú
        icons.update({r: self.renderer._m4_icon(r) for r in ("iron_ingot", "copper_ingot", "silicon_wafer")})   # v0.6 M3: lingotes (M4: e o wafer) no rótulo
        labels = []
        if self.mode == "play":
            ui.draw_chest_labels(self.labeled_chests(), cam, self.zoom, icons)
            labels = ui.chest_label_rects
            ui.draw_dispenser_labels(self.dispenser_labels(), cam, self.zoom)
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
        if self.objective_hint_time > 0 and self.objective_hint and not critical:
            ui.draw_objective_hint(self.objective_hint, min(1.0, self.objective_hint_time / 0.4))
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
        if self.mode in ("fabricator", "build"):
            preview = self.renderer.machine_preview
            ui.draw_fabricator(state, self.menu_of_mode(), preview, self.t, self.renderer.item_icon, mouse_ui,
                               self.shift_held(), build=self.mode == "build", bench=self.fab_bench)
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
        elif self.mode in INVENTORY_MODES:
            side = (self.open_chest or self.open_drill or self.open_melter or self.open_smelter or self.open_collector
                    or self.open_cultivator or self.open_dispenser or self.open_station or self.open_crate)
            if self.open_cultivator is not None:         # v0.8 M3: o cilindro do painel é o do mundo, ×2
                ui.cultivator_art = self.renderer.cultivator_surfaces(self.open_cultivator, self.renderer.powered)
            status = (self.station_status() if self.open_station is not None
                      else self.drill_status() if self.open_drill is not None
                      else self.melter_status() if self.open_melter is not None
                      else self.smelter_status() if self.open_smelter is not None
                      else self.collector_status() if self.open_collector is not None
                      else self.cultivator_status() if self.open_cultivator is not None
                      else self.dispenser_status() if self.open_dispenser is not None else "")
            station_info = (self.hovered_slot_label(mouse_ui) if self.open_station is not None
                            else self.collector_info() if self.open_collector is not None
                            else self.dispenser_info() if self.open_dispenser is not None else None)
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

        # camada 4: "DIAGRAMA: ..." por cima de tudo (até dos ícones dos painéis)
        if self.blueprint_notice_time > 0 and self.blueprint_notice:
            ui.begin()
            ui.draw_blueprint_notice(self.blueprint_notice, min(1.0, self.blueprint_notice_time / 0.5),
                                     self.renderer.item_icon(f"diagram_{self.blueprint_notice}"))
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
        old = saved is None and worlds.legacy_status() == "old"   # slot1.json v1–v9: avisa "save antigo"
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
        self.audio.set_smelter_loops([])
        self.audio.set_collector_loop(0.0)
        self.audio.set_solar_hum(0.0)
        self.audio.set_wind(False)
        self.audio.set_rain(0.0)
        self.audio.set_vent(0.0)
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
        self.build_menu = build_menu(lambda: self.state.known_props())   # v0.7 M2: outro save, outros projetos (seleção zerada)
        self.objectives = ObjectiveTracker(state)
        self.floaters = FloatingTexts()
        self.renderer.particles.clear()
        self.placing, self.rotation, self.mouse_held = None, 0, False
        self.hotbar_selected, self.held, self.notice_time = 0, None, 0.0
        self.open_chest = self.renderer.open_chest = None
        self.open_station, self.open_drill, self.open_melter, self.name_edit = None, None, None, None
        self.open_dispenser = self.open_smelter = self.open_collector = self.open_cultivator = None
        self.open_crate = self.after_terminal = None
        self.renderer.minimap.reset()
        self.blueprint_notice, self.blueprint_notice_time, self.blueprint_duck = None, 0.0, 0.0
        self.thaw_notice, self.thaw_notice_time = None, 0.0
        self.objective_hint, self.objective_hint_time = None, 0.0
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
