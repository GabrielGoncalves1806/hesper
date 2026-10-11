"""O App: abre a janela, roda o game loop e liga input, regras, desenho e som.

Game loop (60 vezes por segundo):
    1. handle_events()  lê teclado/mouse e decide o que cada tecla faz no modo atual
    2. update(dt)       manda os controles pro GameState e reage aos eventos dele
    3. draw()           desenha mundo + UI numa tela de 960×540 e estica pra janela

Modos de tela: "play" (jogando), "fabricator" (menu de receitas),
"terminal" (lendo um log), "pause" (menu do Esc) e "end" (tela de fim do MVP).
Em "pause" e "end" o mundo fica congelado (O₂, máquinas e Ti param).
"""

import math
import random

import pygame

from game import art
from game import config as C
from game import audio as sound
from game import settings
from game.assets import Sprites
from game.audio import Audio
from game.objectives import ObjectiveTracker
from game.render import Renderer, stage_key
from game.systems import Controls, GameState
from game.ui import UI, FloatingTexts

MOVE_KEYS = {
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
}
NUMBER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7]
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
    def __init__(self, scale: int | None = None):
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
        self.placing: str | None = None                   # máquina sendo posicionada
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

    # ---- loop -----------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000
            self.step(dt)
        pygame.quit()

    def step(self, dt: float) -> None:
        self.handle_events()
        self.update(dt)
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
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self.keys_down.add(event.key)
                self.on_key(event.key)
            elif event.type == pygame.KEYUP:
                self.keys_down.discard(event.key)
            elif event.type == pygame.MOUSEMOTION:
                self.mouse = (event.pos[0] // self.scale, event.pos[1] // self.scale)
                if self.mode == "pause":
                    self.pause_hover()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse = (event.pos[0] // self.scale, event.pos[1] // self.scale)
                self.on_click(event.button)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_held = False
                if self.dragging_slider is not None:
                    self.dragging_slider = None
                    settings.save(self.settings)

    def on_key(self, key: int) -> None:
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
            elif key in NUMBER_KEYS:
                kind = C.MACHINE_ORDER[NUMBER_KEYS.index(key)]
                if state.machines_owned[kind] > 0:
                    self.placing = kind
                    self.audio.play("ui_click")

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
            else:  # Sair
                settings.save(self.settings)
                self.running = False
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
        if self.mode == "pause":
            if button == 1:
                self.on_pause_click()
            return
        if self.state.fainted:
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
            for i, (rect, _) in enumerate(self.ui.fabricator_rows):
                if rect.collidepoint(ux, uy):
                    self.fab_selected = i
        elif self.mode == "play":
            if self.placing:
                tile = self.place_target()
                if tile is not None and self.state.place(self.placing, tile, self.rotation):
                    if self.state.machines_owned[self.placing] == 0:
                        self.placing = None
            else:
                self.mouse_held = True

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.audio.play("ui_open" if mode in ("fabricator", "pause") else "ui_close")
        self.mode = mode
        self.mouse_held = False

    def try_craft(self, kind: str) -> None:
        if self.state.craft(kind):
            self.placing = kind      # fabricou: já entra no modo de colocar
            self.rotation = 0
            self.set_mode("play")

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
        if self.mode == "pause":            # congelado: só o som continua (pra ouvir o slider mexendo)
            self.audio.update(dt)
            return
        if self.mode != "end":
            self.state.update(dt, self.controls())
        self.banner_time += dt
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
        elif kind == "dismantle":
            _, _, tile = event
            self.renderer.spawn_chips(tile, "#9a9086", 14)       # poeirinha
            self.renderer.spawn_chips(tile, "#c8c0b4", 8)
            self.audio.play("place_low")
        elif kind == "craft":
            self.audio.play("craft")
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
                       for m in state.machines if not m.is_drill), default=None)
        audio.set_hum(sound.hum_volume(nearest))
        self.update_drills_feedback(dt)
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
            self.drill_dust_timer = 0.12
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
        for i, m in enumerate(self.state.machines):
            phase = (i * 1.37) % period
            if m.type.index is not None and (self.t - dt + phase) % period > (self.t + phase) % period:
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
            return content + (" · [E] coletar" if state.nearby_drill() is machine and machine.stored else "")
        if machine:
            return "[Clique direito] desmontar" if state.can_dismantle(machine) else "Chegue mais perto pra desmontar"
        vein = state.world.vein_at(*self.mouse_tile())     # mouse em cima de um veio livre
        if vein:
            name = C.RESOURCE_NAME[vein.resource]
            unlocked = state.recipe_status("drill") != "locked"
            return f"Veio de {name} · " + ("coloque uma drill" if unlocked else "drill libera na Névoa")
        target = state.interaction()
        if target and target[0] == "terminal":
            return "[E] Ler terminal"
        if target and target[0] == "drill" and target[1].stored:
            d = target[1]
            return f"[E] Coletar {d.stored} {C.RESOURCE_NAME[d.resource]}"
        if state.in_base_zone():
            return "[E] Fabricador" if self.t > 6 else "Paredes com cristais têm minério"
        tile = self.mouse_tile()
        if state.world.is_minable(*tile):
            return "Segure o clique para minerar" if state.can_mine(tile) else "Chegue mais perto pra minerar"
        return None

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
        if not critical:   # com O₂ crítico o aviso grande ocupa essa área (e o foco é voltar pra base)
            ui.draw_objectives(self.objectives.lines(state))
        if self.banner_time < BANNER_TIME:
            alpha = min(1.0, self.banner_time / BANNER_FADE_IN, (BANNER_TIME - self.banner_time) / BANNER_FADE_OUT)
            ui.draw_banner(self.banner_stage, alpha)
        ui.finish(canvas)

        # camada 2: menus e telas por cima do HUD
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
        if state.fainted:
            ui.draw_faint(state)
        ui.draw_cursor(self.mouse[0] / 2, self.mouse[1] / 2)
        ui.finish(canvas)

        # Copiar uma superfície sem alfa pra janela grava alfa 255 (opaco) em todos os pixels.
        if self.scale == 1:
            self.window.blit(canvas, (0, 0))
        else:
            self.window.blit(pygame.transform.scale(canvas, self.window.get_size()), (0, 0))

    def screenshot(self, path: str) -> None:
        pygame.image.save(self.canvas, path)
