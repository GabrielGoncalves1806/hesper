"""O App: abre a janela, roda o game loop e liga input, regras, desenho e som.

Game loop (60 vezes por segundo):
    1. handle_events()  lê teclado/mouse e decide o que cada tecla faz no modo atual
    2. update(dt)       manda os controles pro GameState e reage aos eventos dele
    3. draw()           desenha mundo + UI numa tela de 960×540 e estica pra janela

Modos de tela: "play" (jogando), "fabricator" (menu de receitas),
"terminal" (lendo um log), "inventory" (Tab), "chest" (baú aberto com E),
"pause" (menu do Esc) e "end" (tela de fim do MVP).
Em "pause" e "end" o mundo fica congelado (O₂, máquinas e Ti param). No fabricador, no terminal,
no inventário e no baú o mundo continua (o player só fica parado), como em Core Keeper e Planet Crafter.
O jogo abre em "title" (tela de título, game/title.py); o save/load fica em game/save.py.
"""

import math
import random

import pygame

from game import art
from game import config as C
from game import audio as sound
from game import save
from game import energy
from game import settings
from game.assets import Sprites
from game.audio import Audio
from game.inventory import Stack
from game.objectives import ObjectiveTracker
from game.render import Renderer, stage_key
from game.systems import Controls, GameState
from game.title import TitleScreen, draw_saved_notice
from game.ui import UI, FloatingTexts

MOVE_KEYS = {
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
}
NUMBER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8]
INVENTORY_MODES = ("inventory", "chest")
BANNER_TIME = 3.5          # banner de estágio: entra em 0,4 s, fica, sai em 0,8 s
BANNER_FADE_IN, BANNER_FADE_OUT = 0.4, 0.8
END_SCREEN_DELAY = 4.5
FOOTSTEP_INTERVAL = 0.3


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
        self.scale = scale or pick_scale()
        self.window = pygame.display.set_mode((C.SCREEN_W * self.scale, C.SCREEN_H * self.scale))
        pygame.display.set_caption("Hesper · v0.1")
        pygame.mouse.set_visible(False)
        # Tela interna SEM canal alfa, com máscaras explícitas. Sem isso, no macOS (driver Cocoa)
        # o Surface herda o formato da janela, que TEM alfa: os blits gravam alfa 0/255 misturado
        # e o macOS mostra retângulos pretos em volta de sprites (bug do playtest 1).
        self.canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H), 0, 32, (0xFF0000, 0x00FF00, 0x0000FF, 0))
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
        self.notice: str | None = None                    # aviso curto ("Inventário cheio")
        self.notice_time = 0.0
        self.rotation = 0
        self.fab_selected = 0
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
        self.settings = settings.load()
        self.audio.set_mix(**self.settings)
        self.audio.start_ambient(stage_key(self.state.stage))
        # save/load e tela de título (game/save.py, game/title.py)
        self.autosave_timer = 0.0       # segundos jogando (modo "play") desde o último save
        self.saved_notice = 0.0         # quanto falta do aviso "Jogo salvo" no HUD
        self.title = TitleScreen(self.ui, self.renderer, self.audio.play)
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

    # ---- input ----------------------------------------------------------------
    @property
    def cam(self) -> tuple[int, int]:
        return self.renderer.camera(self.state)

    def mouse_tile(self) -> tuple[int, int]:
        cx, cy = self.cam
        # mira no que está à vista: o topo elevado de uma parede cobre o tile de cima dela
        return self.state.world.visual_tile_at(self.mouse[0] + cx, self.mouse[1] + cy)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_game()
            elif event.type == pygame.KEYDOWN:
                self.keys_down.add(event.key)
                self.on_key(event.key)
            elif event.type == pygame.KEYUP:
                self.keys_down.discard(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse = (event.pos[0] // self.scale, event.pos[1] // self.scale)
                if self.mode == "pause":
                    self.pause_hover()
                elif self.mode == "title":
                    self.title.hover(self.mouse[0] / 2, self.mouse[1] / 2)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse = (event.pos[0] // self.scale, event.pos[1] // self.scale)
                self.on_click(event.button)
            elif event.type == pygame.MOUSEWHEEL and self.mode == "play" and not self.state.fainted:
                # rodinha pra baixo = próximo slot (y < 0), pra cima = anterior
                self.select_hotbar((self.hotbar_selected + (1 if event.y < 0 else -1)) % C.HOTBAR_SLOTS)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_held = False
                if self.dragging_slider is not None:
                    self.dragging_slider = None
                    settings.save(self.settings)

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
            elif key in (pygame.K_w, pygame.K_UP):
                self.fab_selected = (self.fab_selected - 1) % len(C.MACHINE_ORDER)
                self.audio.play("ui_click")
            elif key in (pygame.K_s, pygame.K_DOWN):
                self.fab_selected = (self.fab_selected + 1) % len(C.MACHINE_ORDER)
                self.audio.play("ui_click")
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.try_craft(C.MACHINE_ORDER[self.fab_selected])
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
                    state.collect_station(target[1])
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
        self.placing = stack.item if stack and stack.item in C.MACHINES else None
        self.audio.play("ui_click")

    def show_notice(self, text: str) -> None:
        self.notice, self.notice_time = text, C.NOTICE_TIME

    def other_side(self, inv):
        """Shift+clique: o inventário do outro lado (player <-> baú). None se só o Tab estiver aberto."""
        if self.open_chest is None:
            return None
        return self.open_chest.storage if inv is self.state.inventory else self.state.inventory

    def on_inventory_click(self, button: int) -> None:
        """Clique na tela de inventário/baú: pega e solta pilhas (a "mão" é self.held)."""
        ux, uy = self.mouse[0] / 2, self.mouse[1] / 2
        hit = next(((inv, i) for rect, inv, i in self.ui.slot_rects if rect.collidepoint(ux, uy)), None)
        if hit is None:
            return
        inv, i = hit
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) or bool({pygame.K_LSHIFT, pygame.K_RSHIFT} & self.keys_down)
        target = self.other_side(inv)
        before = ((self.held.item, self.held.count) if self.held else None, inv.to_data())
        if button == 1 and shift and target is not None and self.held is None:
            inv.quick_move(i, target)                    # todas as pilhas desse item vão pro outro lado
        elif button == 1:
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
        if not self.stash_held():
            self.show_notice("Sem espaço pro item na mão")
            return
        self.set_mode("play")

    # ---- menu de pausa ---------------------------------------------------------
    def open_pause(self) -> None:
        self.pause_screen, self.pause_selected = "main", 0
        self.set_mode("pause")

    def pause_item_count(self) -> int:
        return {"main": len(UI.PAUSE_OPTIONS), "volumes": len(UI.VOLUME_ROWS) + 1, "controls": 1}[self.pause_screen]

    def on_pause_key(self, key: int) -> None:
        if key in (pygame.K_w, pygame.K_UP, pygame.K_s, pygame.K_DOWN):
            step = -1 if key in (pygame.K_w, pygame.K_UP) else 1
            self.pause_selected = (self.pause_selected + step) % self.pause_item_count()
            self.audio.play("ui_click")
        elif key in (pygame.K_a, pygame.K_LEFT, pygame.K_d, pygame.K_RIGHT) and self.pause_screen == "volumes":
            if self.pause_selected < len(UI.VOLUME_ROWS):
                key_name = UI.VOLUME_ROWS[self.pause_selected][0]
                delta = -0.1 if key in (pygame.K_a, pygame.K_LEFT) else 0.1
                self.set_volume(key_name, self.settings[key_name] + delta, save=True)
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
            elif option == "Volumes":
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
        else:   # "Voltar" (volumes ou controles)
            self.pause_screen, self.pause_selected = "main", 0
            self.audio.play("ui_close")

    def set_volume(self, key: str, value: float, save: bool = False) -> None:
        self.settings = settings.clean({**self.settings, key: round(value, 2)})
        self.audio.set_mix(**self.settings)
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
                    self.try_craft(kind)
                    return
            for rect, kind in self.ui.fabricator_rows:     # a lista pode estar rolada: acha pelo tipo
                if rect.collidepoint(ux, uy):
                    self.fab_selected = C.MACHINE_ORDER.index(kind)
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
            self.stash_held()            # devolve a pilha da mão (se não couber, ela espera o próximo Tab)
            if self.mode == "chest":     # fechou o baú: som próprio no lugar do ui_close
                self.audio.play("chest_close")
                self.open_chest = self.renderer.open_chest = None
                self.mode = mode
                self.mouse_held = False
                return
        if mode != self.mode:
            self.audio.play("ui_open" if mode in ("fabricator", "pause", "inventory") else "ui_close")
        self.mode = mode
        self.mouse_held = False

    def try_craft(self, kind: str) -> None:
        if self.state.craft(kind):
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
            self.floaters.add(f"+{amount} {C.RESOURCE_LABEL[resource]}", x, y - 48, C.ORE_COLORS[resource][0])
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
            for d in state.drills:
                ax, ay = d.anchor
                if not d.full and -64 < ax - cx < C.SCREEN_W + 64 and -64 < ay - cy < C.SCREEN_H + 64:
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
        cx, cy = self.cam
        return self.state.machine_at_point(self.mouse[0] + cx, self.mouse[1] + cy)

    def hint(self) -> str | None:
        state = self.state
        if self.placing == "drill" and self.place_target() is None:
            return "Coloque a drill em cima de um veio"
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
            text = f"Estação: {len(st.drones)} drones · buffer {st.stored}/{C.STATION_BUFFER}"
            if state.power.deficit:
                text += f" · ritmo {self.power_percent()}%"
            return text + (" · [E] coletar" if state.nearby_station() is machine else "")
        if machine and machine.is_chest:
            used = sum(1 for st in machine.storage.slots if st)
            near = state.nearby_chest() is machine
            return f"Baú ({used}/{C.CHEST_SLOTS})" + (" · [E] abrir" if near else "")
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
            return f"[E] Coletar {target[1].station.stored} da estação"
        if target and target[0] == "drill" and target[1].stored:
            d = target[1]
            return f"[E] Coletar {d.stored} {C.RESOURCE_NAME[d.resource]}"
        if state.in_base_zone():
            return "[E] Fabricador" if self.t > 6 else "Paredes com cristais têm minério"
        tile = self.mouse_tile()
        if state.world.is_minable(*tile):
            return "Segure o clique para minerar" if state.can_mine(tile) else "Chegue mais perto pra minerar"
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
        self.renderer.draw(canvas, state, cam, self.t, ghost)

        critical = state.o2 < C.O2_LOW and not state.fainted
        if critical:
            pulse = 0.5 + 0.12 * math.sin(self.t * 6.3)
            self.red_vignette.set_alpha(int(255 * pulse))
            canvas.blit(self.red_vignette, (0, 0))

        # camada 1: HUD e textos flutuantes
        ui.begin()
        ui.draw_floaters(self.floaters, cam)
        if critical:
            ui.draw_o2_critical(state, self.t, cam)
        icons = {r: self.renderer.surface(f"icon_{r}", lambda r=r: art.icon(r))[0] for r in C.RESOURCES}
        ui.draw_hud(state, self.t, self.hint() if self.mode == "play" else None, icons)
        ui.draw_hotbar(state.inventory, self.hotbar_selected, self.renderer.item_icon)
        if not critical:   # com O₂ crítico o aviso grande ocupa essa área (e o foco é voltar pra base)
            ui.draw_objectives(self.objectives.lines(state))
        if self.saved_notice > 0:
            draw_saved_notice(ui, self.saved_notice)
        if self.banner_time < BANNER_TIME:
            alpha = min(1.0, self.banner_time / BANNER_FADE_IN, (BANNER_TIME - self.banner_time) / BANNER_FADE_OUT)
            ui.draw_banner(self.banner_stage, alpha)
        ui.finish(canvas)

        # camada 2: menus e telas por cima do HUD
        mouse_ui = (self.mouse[0] / 2, self.mouse[1] / 2)
        ui.begin()
        if self.mode == "fabricator":
            preview = self.renderer.machine_preview
            ui.draw_fabricator(state, self.fab_selected, preview, self.t)
        elif self.mode == "terminal":
            ui.draw_terminal(self.terminal_index, self.t)
        elif self.mode == "end":
            ui.draw_end(state, self.t)
        elif self.mode == "pause":
            ui.draw_pause(self.pause_screen, self.pause_selected, self.settings)
        elif self.mode in INVENTORY_MODES:
            chest = self.open_chest.storage if self.open_chest else None
            ui.draw_inventory(state.inventory, chest, self.hotbar_selected, self.renderer.item_icon, mouse_ui)
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
            hovered = next((inv.slots[i] for rect, inv, i in ui.slot_rects if rect.collidepoint(mouse_ui)), None)
            ui.draw_held_and_tooltip(self.held, hovered, mouse_ui, self.renderer.item_icon)
            if self.notice_time > 0:
                ui.draw_notice(self.notice, min(1.0, self.notice_time / 0.4))
            ui.draw_cursor(*mouse_ui)
            ui.finish(canvas)

        # Copiar uma superfície sem alfa pra janela grava alfa 255 (opaco) em todos os pixels.
        if self.scale == 1:
            self.window.blit(canvas, (0, 0))
        else:
            self.window.blit(pygame.transform.scale(canvas, self.window.get_size()), (0, 0))

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
        if self.scale == 1:
            self.window.blit(self.canvas, (0, 0))
        else:
            self.window.blit(pygame.transform.scale(self.canvas, self.window.get_size()), (0, 0))
