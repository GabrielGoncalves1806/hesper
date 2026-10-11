"""O App: abre a janela, roda o game loop e liga input, regras, desenho e som.

Game loop (60 vezes por segundo):
    1. handle_events()  lê teclado/mouse e decide o que cada tecla faz no modo atual
    2. update(dt)       manda os controles pro GameState e reage aos eventos dele
    3. draw()           desenha mundo + UI numa tela de 960×540 e estica pra janela

Modos de tela: "play" (jogando), "fabricator" (menu de receitas),
"terminal" (lendo um log) e "end" (tela de fim do MVP).
"""

import math

import pygame

from game import art
from game import config as C
from game import audio as sound
from game.assets import Sprites
from game.audio import Audio
from game.render import Renderer, stage_key
from game.systems import Controls, GameState
from game.ui import UI, FloatingTexts

MOVE_KEYS = {
    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0),
    pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1), pygame.K_UP: (0, -1),
    pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
}
NUMBER_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]
BANNER_TIME = 5.0
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
        self.canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        self.clock = pygame.time.Clock()

        self.sprites = Sprites()
        self.audio = Audio()
        self.renderer = Renderer(self.sprites)
        self.ui = UI()
        self.floaters = FloatingTexts()
        self.red_vignette = art.vignette(C.SCREEN_W, C.SCREEN_H, (170, 18, 8), 255)
        self.state = GameState()

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
        return (self.mouse[0] + cx) // C.TILE, (self.mouse[1] + cy) // C.TILE

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
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse = (event.pos[0] // self.scale, event.pos[1] // self.scale)
                self.on_click(event.button)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.mouse_held = False

    def on_key(self, key: int) -> None:
        state = self.state
        if key == pygame.K_F1:
            state.toggle_time_scale()
        elif key == pygame.K_F2:
            state.debug_add_ti()
        if state.fainted:
            return

        if self.mode == "fabricator":
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
                terminal = state.nearby_terminal()
                if terminal is not None:
                    state.read_terminal(terminal)
                    self.terminal_index = terminal
                    self.mode = "terminal"
                elif state.in_base_zone():
                    self.placing = None
                    self.set_mode("fabricator")
            elif key == pygame.K_ESCAPE and self.placing:
                self.placing = None
                self.audio.play("ui_close")
            elif key == pygame.K_r and self.placing:
                self.rotation = (self.rotation + 1) % 4
            elif key in NUMBER_KEYS:
                kind = C.MACHINE_ORDER[NUMBER_KEYS.index(key)]
                if state.machines_owned[kind] > 0:
                    self.placing = kind
                    self.audio.play("ui_click")

    def on_click(self, button: int) -> None:
        if self.state.fainted:
            return
        if button == 3 and self.placing:   # botão direito também cancela
            self.placing = None
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
                if self.state.place(self.placing, self.mouse_tile(), self.rotation):
                    if self.state.machines_owned[self.placing] == 0:
                        self.placing = None
            else:
                self.mouse_held = True

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.audio.play("ui_open" if mode == "fabricator" else "ui_close")
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

    def on_game_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "mine_hit":
            self.audio.play("mine_hit")
            self.renderer.spawn_chips(event[1], "#b0704f", 2)
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
                       for m in state.machines), default=None)
        audio.set_hum(sound.hum_volume(nearest))
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

    def spawn_machine_floaters(self, dt: float) -> None:
        """De tempos em tempos cada máquina solta um '+O2', '+CALOR' ou '+AGUA' (como no mockup)."""
        period = 4.0
        for i, m in enumerate(self.state.machines):
            phase = (i * 1.37) % period
            if (self.t - dt + phase) % period > (self.t + phase) % period:
                key = m.type.index
                self.floaters.add(f"+{C.INDEX_LABEL[key]}", (m.tx + 0.5) * C.TILE, m.ty * C.TILE - 30, C.INDEX_COLOR[key])

    # ---- desenho --------------------------------------------------------------
    def hint(self) -> str | None:
        state = self.state
        if self.placing:
            return "Clique para colocar · R gira · Esc cancela"
        if state.nearby_terminal() is not None:
            return "[E] Ler terminal"
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
            tile = self.mouse_tile()
            ghost = (self.placing, tile, self.rotation, state.can_place(self.placing, tile))
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
        if self.banner_time < BANNER_TIME:
            ui.draw_banner(self.banner_stage, min(1.0, (BANNER_TIME - self.banner_time) / 1.0))
        ui.finish(canvas)

        # camada 2: menus e telas por cima do HUD
        ui.begin()
        if self.mode == "fabricator":
            preview = lambda kind: self.renderer.surface(C.MACHINES[kind].sprite, lambda: art.machine(kind))[0]
            ui.draw_fabricator(state, self.fab_selected, preview, self.t)
        elif self.mode == "terminal":
            ui.draw_terminal(self.terminal_index, self.t)
        elif self.mode == "end":
            ui.draw_end(state, self.t)
        if state.fainted:
            ui.draw_faint(state)
        ui.draw_cursor(self.mouse[0] / 2, self.mouse[1] / 2)
        ui.finish(canvas)

        if self.scale == 1:
            self.window.blit(canvas, (0, 0))
        else:
            pygame.transform.scale(canvas, self.window.get_size(), self.window)

    def screenshot(self, path: str) -> None:
        pygame.image.save(self.canvas, path)
