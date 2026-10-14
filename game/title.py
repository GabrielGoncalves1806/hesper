"""Tela de título: Continuar · Mundos · Sair, a lista dos 3 mundos e o formulário de Novo mundo.

Telas (`self.screen`):
    "main"   -> Continuar (o último mundo jogado), Mundos, Sair;
    "worlds" -> os 3 espaços (nome, seed, estágio, tempo de jogo e data; vazio = "Novo mundo") e Voltar.
                Apagar: o botão APAGAR (ou X/Delete no teclado) arma a confirmação e o segundo clique (ou
                tecla) apaga. Esc, mexer a seleção ou clicar em outro lugar desarma;
    "form"   -> Novo mundo: Nome (vazio = "Mundo N"), Seed (vazia = a sorteada que aparece no campo), CRIAR
                e VOLTAR. Enquanto o formulário está aberto a digitação do SDL fica ligada (quem liga e
                desliga é o App, olhando `wants_text`).

Save de uma versão antiga no saves/slot1.json (v1–v9, que o jogo não carrega nem migra): "Continuar"
aparece apagado e embaixo do menu vem o aviso "Save de uma versão antiga · comece um novo mundo".

O App (app.py) repassa teclado/mouse/texto pra cá e recebe de volta uma ação:
    "continue", "quit", ("play", espaço), ("create", espaço, nome, seed) ou ("delete", espaço).
Quem lê, grava e apaga arquivo é o App (com o game/worlds.py); esta tela só desenha e escolhe.

Fundo: a cratera do estágio 1 desenhada pelo próprio Renderer, com a câmera passeando devagar,
borrada (diminui a imagem 4× e estica de volta: blur barato) e escurecida, com poeira por cima.
Igual ao resto da UI, menus e textos são desenhados em px da UI (480×270 no Grande, mais no Média e no
Pequena) e esticados direto na janela: tudo centralizado pelo ui.w/ui.h.
"""

import math

import pygame

from game import config as C
from game import save
from game import worlds
from game.assets import load_font
from game.systems import GameState
from game.textedit import TextField
from game.ui import B_DIM, B_LINE, B_LINE2, B_MUTED, B_TEXT, B_WELL, B_WINDOW
from game.world import hash01

UP_KEYS = (pygame.K_w, pygame.K_UP)
DOWN_KEYS = (pygame.K_s, pygame.K_DOWN)
OK_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
DELETE_KEYS = (pygame.K_x, pygame.K_DELETE, pygame.K_BACKSPACE)

MENU_W, MENU_Y = 240, 132                # caixa do menu (no Grande, 480×270)
ROW_H, ROW_GAP = 19, 22
BLUR = 4                                 # quanto o fundo é reduzido antes de esticar (maior = mais borrado)
LIST_W, SLOT_H, SLOT_GAP = 320, 38, 4    # tela de Mundos
FORM_W = 260                             # Novo mundo
FIELD_H = 16
FORM_FIELDS = ("name", "seed", "create", "back")


def fmt_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes} MIN" if minutes < 60 else f"{minutes // 60} H {minutes % 60:02d} MIN"


class TitleScreen:
    def __init__(self, ui, renderer, play):
        self.ui = ui                    # a UI do jogo (fontes, text(), panel()...)
        self.renderer = renderer        # desenha a cratera do fundo
        self.play = play                # audio.play: sons de menu
        self.font_title = load_font("Silkscreen-Regular.ttf", 32, 48)
        self.screen = "main"
        self.saved: GameState | None = None   # o mundo do "Continuar", já carregado (None = não tem)
        self.saved_slot: int | None = None
        self.old = False                # slot1.json de versão antiga (não carrega; Continuar apagado)
        self.worlds: list = [worlds.WorldInfo(s) for s in range(1, worlds.SLOTS + 1)]
        self.selected = 0
        self.armed: int | None = None   # espaço com o APAGAR armado (esperando o segundo clique)
        # formulário do Novo mundo
        self.form_slot = 1
        self.name_field = TextField("", worlds.NAME_MAX)
        self.seed_field = TextField("", worlds.SEED_MAX)
        self.rolled = 0                 # seed sorteada ao abrir o formulário (vale se o campo ficar vazio)
        self.focus = 0                  # índice em FORM_FIELDS
        # retângulos clicáveis do último desenho (coordenadas da UI)
        self.items: list[pygame.Rect] = []                         # linhas do menu / espaços + Voltar
        self.delete_rects: list[tuple[pygame.Rect, int]] = []      # APAGAR de cada espaço cheio
        self.form_rects: list[tuple[pygame.Rect, int]] = []        # campo/botão -> índice em FORM_FIELDS
        self.ox = self.oy = 0                 # deslocamento pro centro (a UI pode ser maior que 480×270)
        self._background: GameState | None = None
        self._shade = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        self._shade.fill((10, 5, 4, 135))

    def open(self, saved: GameState | None, old: bool = False, world_list=None, slot: int | None = None) -> None:
        """Volta pro menu principal. `saved` é o mundo do Continuar (espaço `slot`), `old` = slot1.json antigo."""
        self.saved, self.saved_slot = saved, slot
        self.old = old and saved is None
        if world_list is not None:
            self.worlds = list(world_list)
        self.screen, self.armed = "main", None
        options = [a for a, _ in self.options()]
        self.selected = options.index("worlds") if self.old or saved is None else 0

    def set_worlds(self, world_list) -> None:
        self.worlds = list(world_list)
        self.armed = None

    @property
    def wants_text(self) -> bool:
        return self.screen == "form"

    @property
    def field(self) -> TextField | None:
        name = FORM_FIELDS[self.focus]
        return self.name_field if name == "name" else self.seed_field if name == "seed" else None

    # ---- opções ----------------------------------------------------------------
    def options(self) -> list[tuple[str, str]]:
        """(ação, texto) de cada linha do menu principal, na ordem."""
        options = [("continue", "Continuar")] if self.saved else [("old", "Continuar")] if self.old else []
        return options + [("worlds", "Mundos"), ("quit", "Sair")]

    def count(self) -> int:
        """Quantas linhas escolhíveis a tela atual tem."""
        if self.screen == "worlds":
            return worlds.SLOTS + 1
        if self.screen == "form":
            return len(FORM_FIELDS)
        return len(self.options())

    # ---- navegação entre telas -------------------------------------------------------
    def open_worlds(self, select: int = 0) -> None:
        self.screen, self.selected, self.armed = "worlds", select, None
        self.play("ui_open")

    def back_to_main(self) -> None:
        self.screen, self.armed = "main", None
        self.selected = [a for a, _ in self.options()].index("worlds")
        self.play("ui_close")

    def open_form(self, slot: int, rolled: int | None = None) -> None:
        self.screen, self.form_slot, self.focus = "form", slot, 0
        self.name_field = TextField("", worlds.NAME_MAX)
        self.seed_field = TextField("", worlds.SEED_MAX)
        self.rolled = worlds.random_seed() if rolled is None else rolled
        self.play("ui_open")

    def form_seed(self) -> tuple[int, str]:
        """(seed que o mundo vai ter, de onde ela vem: "sorteada", "número" ou "texto")."""
        typed = self.seed_field.text.strip()
        seed = worlds.parse_seed(typed)
        if seed is None:
            return self.rolled, "sorteada"
        return seed, "número" if typed.isascii() and typed.isdigit() else "texto"

    def create_action(self) -> tuple:
        self.play("ui_click")
        name = worlds.clean_name(self.name_field.text, self.form_slot)
        return ("create", self.form_slot, name, self.form_seed()[0])

    # ---- ações -----------------------------------------------------------------
    def activate(self, index: int):
        """Executa a linha `index` da tela atual. Devolve a ação pro App ou None."""
        if self.screen == "worlds":
            return self._activate_world(index)
        if self.screen == "form":
            return self._activate_form(index)
        action = self.options()[index][0]
        if action == "old":                         # save antigo: Continuar apagado
            return None
        if action == "worlds":
            self.open_worlds(self.saved_slot - 1 if self.saved_slot else 0)
            return None
        return action

    def _activate_world(self, index: int):
        self.armed = None
        if index >= worlds.SLOTS:                   # Voltar
            self.back_to_main()
            return None
        info = self.worlds[index]
        if info.playable:
            return ("play", info.slot)
        self.open_form(info.slot)                   # vazio, antigo ou estragado: Novo mundo aqui
        return None

    def _activate_form(self, index: int):
        self.focus = index
        name = FORM_FIELDS[index]
        if name == "create":
            return self.create_action()
        if name == "back":
            self.screen, self.selected = "worlds", self.form_slot - 1
            self.play("ui_close")
            return None
        self.play("ui_click")                       # clicou num campo: ele vira o da digitação
        return None

    def delete_press(self, slot: int):
        """APAGAR do espaço `slot`: o 1º arma, o 2º apaga."""
        if self.armed == slot:
            self.armed = None
            self.play("ui_close")
            return ("delete", slot)
        self.armed = slot
        self.play("ui_click")
        return None

    # ---- input -----------------------------------------------------------------
    def on_text(self, text: str) -> None:
        field = self.field if self.screen == "form" else None
        if field is not None:
            field.insert(text)

    def on_key(self, key: int):
        if self.screen == "form":
            return self._form_key(key)
        if key in UP_KEYS or key in DOWN_KEYS:
            step = -1 if key in UP_KEYS else 1
            self.selected = (self.selected + step) % self.count()
            if self.screen == "main" and self.options()[self.selected][0] == "old":
                self.selected = (self.selected + step) % self.count()     # a linha apagada não é escolhível
            self.armed = None
            self.play("ui_click")
        elif key in OK_KEYS:
            if self.screen == "worlds" and self.armed is not None:        # armado: Enter confirma
                return self.delete_press(self.armed)
            return self.activate(self.selected)
        elif key == pygame.K_ESCAPE and self.screen == "worlds":
            if self.armed is not None:
                self.armed = None
                self.play("ui_close")
            else:
                self.back_to_main()
        elif key in DELETE_KEYS and self.screen == "worlds" and self.selected < worlds.SLOTS:
            info = self.worlds[self.selected]
            if not info.empty:
                return self.delete_press(info.slot)
        return None

    def _form_key(self, key: int):
        if key in (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB):           # W/S são letras aqui: só setas e Tab
            self.focus = (self.focus + (-1 if key == pygame.K_UP else 1)) % len(FORM_FIELDS)
            self.play("ui_click")
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return self._activate_form(self.focus if FORM_FIELDS[self.focus] == "back" else 2)
        elif key == pygame.K_ESCAPE:
            return self._activate_form(FORM_FIELDS.index("back"))
        elif key == pygame.K_BACKSPACE and self.field is not None:
            self.field.backspace()
        return None

    def hover(self, ux: float, uy: float) -> None:
        if self.screen == "form":
            return                                  # o foco do formulário só muda com clique/teclas
        for i, rect in enumerate(self.items):
            if rect.collidepoint(ux, uy) and i != self.selected:
                if self.screen == "main" and self.options()[i][0] == "old":
                    continue
                self.selected = i

    def click(self, ux: float, uy: float):
        if self.screen == "form":
            for rect, index in self.form_rects:
                if rect.collidepoint(ux, uy):
                    return self._activate_form(index)
            return None
        if self.screen == "worlds":
            for rect, slot in self.delete_rects:
                if rect.collidepoint(ux, uy):
                    self.selected = slot - 1
                    return self.delete_press(slot)
            self.armed = None
        for i, rect in enumerate(self.items):
            if rect.collidepoint(ux, uy):
                self.selected = i
                return self.activate(i)
        return None

    # ---- desenho ---------------------------------------------------------------
    def draw_background(self, canvas: pygame.Surface, t: float) -> None:
        if self._background is None:
            self._background = save.new_state()
            # o player sai de cena: o fundo é só a cratera (ele iria parar no meio da tela)
            self._background.player.x, self._background.player.y = 2 * C.TILE, 2 * C.TILE
        # passeio lento pela cratera; a cápsula fica escondida atrás do menu (senão briga com o título)
        cx, cy = C.BASE_CENTER
        cam = (int(cx - C.SCREEN_W / 2 + math.sin(t * 0.05) * 80),
               int(cy - 340 + math.sin(t * 0.037) * 20))
        self.renderer.draw(canvas, self._background, cam, t)
        small = pygame.transform.smoothscale(canvas, (C.SCREEN_W // BLUR, C.SCREEN_H // BLUR))
        canvas.blit(pygame.transform.smoothscale(small, (C.SCREEN_W, C.SCREEN_H)), (0, 0))
        canvas.blit(self._shade, (0, 0))

    def draw(self, target: pygame.Surface, t: float, mouse_ui: tuple[float, float]) -> None:
        """Menus e textos (o fundo vem antes, no draw_background). `target` é a janela, `mouse_ui`
        o mouse em px da UI."""
        ui = self.ui
        self.ox, self.oy = ui.center_offset       # o bloco logo + menu fica no meio da tela
        ui.begin()
        self._draw_dust(t)
        self.draw_screen(t, mouse_ui)
        ui.draw_cursor(*mouse_ui)
        ui.finish(target)

    def draw_screen(self, t: float, mouse_ui) -> None:
        """Só o conteúdo da tela atual na camada da UI (sem fundo e sem cursor): também é o que os testes
        chamam pra ter os retângulos clicáveis."""
        ui = self.ui
        self.ox, self.oy = ui.center_offset
        if self.screen == "worlds":
            self._draw_worlds(mouse_ui)
            ui.help_line(ui.h - 16, [("W/S", "escolhe"), ("ENTER", "jogar"), ("X", "apagar"), ("ESC", "voltar")])
        elif self.screen == "form":
            self._draw_form(t, mouse_ui)
            ui.help_line(ui.h - 16, [("TAB", "campo"), ("ENTER", "criar"), ("ESC", "voltar")])
        else:
            self._draw_logo()
            self._draw_menu()
            ui.help_line(ui.h - 16, [("W/S", "escolhe"), ("ENTER", "ok")])

    @property
    def menu_x(self) -> int:
        return (self.ui.w - MENU_W) // 2

    def _draw_dust(self, t: float) -> None:
        """Poeira laranja nítida passando na frente do fundo borrado."""
        for i in range(55):
            speed = 6 + 14 * hash01(i, 2, 31)
            w, h = self.ui.w, self.ui.h
            x = (hash01(i, 1, 31) * w + t * speed) % w
            y = hash01(i, 3, 31) * h + math.sin(t * 0.8 + i) * 4
            alpha = 70 + int(120 * hash01(i, 4, 31))
            self.ui.fill((226, 160, 110, alpha), (int(x), int(y), 1 + (i % 5 == 0), 1))

    def _draw_logo(self) -> None:
        """'HESPER' grande em Silkscreen, com letras espaçadas, sombra e um traço laranja embaixo."""
        surf, font = self.ui.surf, self.font_title
        letters = [font.render(ch, False, pygame.Color(C.C_TEXT)) for ch in "HESPER"]
        shadows = [font.render(ch, False, (0, 0, 0)) for ch in "HESPER"]
        spacing = 6
        total = sum(img.get_width() for img in letters) + spacing * (len(letters) - 1)
        cx = self.ui.w // 2
        x, y = cx - total // 2, 44 + self.oy
        for img, shadow in zip(letters, shadows):
            shadow.set_alpha(170)
            surf.blit(shadow, (x + 2, y + 2))
            surf.blit(img, (x, y))
            x += img.get_width() + spacing
        line_y = y + letters[0].get_height() + 2
        surf.fill(pygame.Color(C.C_ACCENT), (cx - 40, line_y, 80, 2))
        self.ui.text("Planeta sem ar. Por enquanto.", cx, line_y + 8, "#d9cfc4", self.ui.body, "center")

    def _row(self, i: int, label: str, y: int, enabled: bool = True) -> pygame.Rect:
        """Uma linha de menu no estilo do menu de pausa (apagada se `enabled` for False)."""
        ui = self.ui
        row = pygame.Rect(self.menu_x + 8, y, MENU_W - 16, ROW_H)
        selected = i == self.selected and enabled
        ui.menu_row(row, selected, enabled)
        color = B_TEXT if selected else B_MUTED if enabled else B_DIM
        ui.tx(label, row.x + 8, row.y + 2, color, ui.body)
        self.items.append(row)
        return row

    def _draw_menu(self) -> None:
        ui = self.ui
        self.items = []
        options = self.options()
        top = MENU_Y + self.oy
        ui.card(self.menu_x, top, MENU_W, 8 + ROW_GAP * len(options) + 2, B_WINDOW, B_LINE)
        for i, (action, label) in enumerate(options):
            row = self._row(i, label, top + 8 + i * ROW_GAP, enabled=action != "old")
            if action == "old":
                ui.tx("SAVE ANTIGO", row.right - 8, row.y + 4, B_DIM, align="right")
            if action == "continue":     # o mundo e o tempo de jogo, à direita da linha
                minutes = fmt_time(self.saved.play_time)
                name = ui.fit(self.saved.world_name.upper(), row.w - 80 - ui.font.size(minutes)[0], ui.font)
                ui.tx(f"{name} · {minutes}", row.right - 8, row.y + 4,
                      C.C_TI if i == self.selected else B_MUTED, align="right")
        if self.old:                    # aviso embaixo da caixa do menu
            y = top + 8 + ROW_GAP * len(options) + 10
            ui.text("Save de uma versão antiga · comece um novo mundo", ui.w // 2, y, C.C_TI, ui.body, "center")

    # ---- Mundos ------------------------------------------------------------------
    def list_rect(self) -> pygame.Rect:
        h = 22 + worlds.SLOTS * (SLOT_H + SLOT_GAP) + ROW_H + 8
        return pygame.Rect((self.ui.w - LIST_W) // 2, max(4, (self.ui.h - h) // 2 - 8), LIST_W, h)

    def _draw_worlds(self, mouse) -> None:
        ui = self.ui
        self.items, self.delete_rects = [], []
        box = self.list_rect()
        ui.window(box.x, box.y, box.w, box.h, "Mundos", f"{sum(not w.empty for w in self.worlds)}/{worlds.SLOTS}")
        y = box.y + 20
        for i, info in enumerate(self.worlds):
            row = pygame.Rect(box.x + 8, y, box.w - 16, SLOT_H)
            self._world_row(i, info, row, mouse)
            y += SLOT_H + SLOT_GAP
        back = pygame.Rect(box.x + 8, y + 2, box.w - 16, ROW_H)
        selected = self.selected == worlds.SLOTS
        ui.menu_row(back, selected)
        ui.tx("Voltar", back.x + 8, back.y + 2, B_TEXT if selected else B_MUTED, ui.body)
        self.items.append(back)

    def _world_row(self, i: int, info, row: pygame.Rect, mouse) -> None:
        ui = self.ui
        selected = i == self.selected
        armed = self.armed == info.slot
        ui.menu_row(row, selected)
        self.items.append(row)
        x = row.x + 8
        # número do espaço numa caixinha
        ui.round_rect((x, row.y + 5, 13, 13), B_WELL, C.C_ACCENT if selected else B_LINE2)
        ui.tx(str(info.slot), x + 7, row.y + 5, C.C_TI if selected else B_MUTED, align="center")
        x += 20
        if info.empty:
            ui.tx("+ Novo mundo", x, row.y + 4, C.C_ACCENT if selected else B_TEXT, ui.body)
            ui.tx("ESPAÇO VAZIO", x, row.y + 22, B_DIM)
            return
        right = row.right - 8
        button = pygame.Rect(right - 54, row.y + 20, 54, 13)
        hover = button.collidepoint(mouse)
        ui.button(button, "APAGAR?" if armed else "APAGAR", "danger" if armed else "ghost" if hover else "off")
        self.delete_rects.append((button, info.slot))
        if info.date_label:
            ui.tx(info.date_label, right, row.y + 6, B_MUTED, align="right")
        name_w = row.right - x - 60
        ui.tx(ui.fit(info.name, name_w), x, row.y + 4, B_TEXT if info.playable else B_MUTED, ui.body)
        if armed:
            line, color = "APAGAR DE VEZ? CLIQUE DE NOVO", C.C_ALERT
        elif info.status == "old":
            line, color = "VERSÃO ANTIGA · ENTER = NOVO MUNDO AQUI", C.C_TI
        elif info.status == "broken":
            line, color = "SAVE ESTRAGADO · ENTER = NOVO MUNDO AQUI", C.C_ALERT
        else:
            line = f"SEED {info.seed} · {info.stage_name} · {fmt_time(info.play_time)}"
            color = C.STAGE_COLOR.get(info.stage, B_MUTED) if selected else B_MUTED
        ui.tx(ui.fit(line, button.x - x - 6, ui.font), x, row.y + 22, color)

    # ---- Novo mundo ----------------------------------------------------------------
    def form_rect(self) -> pygame.Rect:
        h = 132
        return pygame.Rect((self.ui.w - FORM_W) // 2, max(4, (self.ui.h - h) // 2 - 8), FORM_W, h)

    def _field(self, index: int, field: TextField, placeholder: str, rect: pygame.Rect, t: float) -> None:
        ui = self.ui
        focused = self.focus == index
        ui.round_rect(rect, B_WELL, C.C_ACCENT if focused else B_LINE2)
        if field.text:
            w = ui.tx(ui.fit(field.text, rect.w - 40), rect.x + 4, rect.y, B_TEXT, ui.body)
        else:
            w = 0
            ui.tx(ui.fit(placeholder, rect.w - 40), rect.x + 4, rect.y, B_DIM, ui.body)
        if focused and (t % C.CHEST_NAME_BLINK) < C.CHEST_NAME_BLINK / 2:
            ui.surf.fill(pygame.Color(C.C_TI), (rect.x + 5 + w, rect.y + 3, 1, 9))
        ui.tx(f"{len(field.text)}/{field.max_len}", rect.right - 3, rect.y + 2,
              C.C_ALERT if field.full else B_MUTED, align="right")
        self.form_rects.append((rect, index))

    def _draw_form(self, t: float, mouse) -> None:
        ui = self.ui
        self.form_rects = []
        box = self.form_rect()
        ui.window(box.x, box.y, box.w, box.h, "Novo mundo", f"ESPAÇO {self.form_slot}")
        x, w = box.x + 8, box.w - 16
        ui.tx("NOME", x, box.y + 18, B_MUTED)
        self._field(0, self.name_field, worlds.default_name(self.form_slot),
                    pygame.Rect(x, box.y + 29, w, FIELD_H), t)
        ui.tx("SEED (OPCIONAL)", x, box.y + 49, B_MUTED)
        self._field(1, self.seed_field, f"{self.rolled}  (sorteada)", pygame.Rect(x, box.y + 60, w, FIELD_H), t)
        seed, source = self.form_seed()
        ui.tx(f"SEED DO MUNDO: {seed}", x, box.y + 80, C.C_TI)
        hint = {"sorteada": "VAZIO = ESTA SORTEADA", "número": "O NÚMERO DIGITADO",
                "texto": "DO TEXTO (SEMPRE A MESMA)"}[source]
        ui.tx(hint, box.right - 8, box.y + 80, B_MUTED, align="right")
        info = self.worlds[self.form_slot - 1] if self.form_slot <= len(self.worlds) else None
        if info is not None and info.status in ("old", "broken"):
            ui.tx("O SAVE ANTIGO DESTE ESPAÇO VIRA BACKUP", x, box.y + 92, C.C_TI)
        create = pygame.Rect(x, box.bottom - 26, (w - 6) * 2 // 3, 18)
        back = pygame.Rect(create.right + 6, create.y, w - create.w - 6, 18)
        for index, rect, label, kind in ((2, create, "CRIAR", "primary"), (3, back, "VOLTAR", "ghost")):
            focused = self.focus == index
            ui.button(rect, label, kind, hover=focused or rect.collidepoint(mouse))
            if focused:
                ui.round_rect(rect.inflate(2, 2), (0, 0, 0, 0), C.C_TI)
            self.form_rects.append((rect, index))


def draw_saved_notice(ui, time_left: float) -> None:
    """Aviso discreto "Jogo salvo" logo abaixo da coluna da direita do HUD, sumindo no último meio segundo."""
    alpha = max(0.0, min(1.0, time_left / 0.5))
    label = "Jogo salvo"
    w = ui.body.size(label)[0] + 24
    h = 17
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    ui.panel(0, 0, w, h, target=layer)
    _check(layer, 6, 6)
    ui.tx(label, 17, 1, C.C_OK, ui.body, target=layer)
    layer.set_alpha(int(255 * alpha))
    # encostado na borda direita, embaixo da coluna da direita (Ti, energia e, com o scanner, o minimapa):
    # o painel do Ti muda de altura, então um y fixo (era 100) caía em cima do medidor de energia
    ui.surf.blit(layer, (ui.w - 6 - w, ui.right_bottom + 4))
    ui.hud_rects.append(pygame.Rect(ui.w - 6 - w, ui.right_bottom + 4, w, h))


def _check(surf: pygame.Surface, x: int, y: int) -> None:
    """Tique ✓ de pixels (o mesmo desenho do UI.draw_check, mas numa superfície qualquer)."""
    c = pygame.Color(C.C_OK)
    for dx, dy in [(0, 3), (1, 4), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (1, 3), (2, 4), (3, 3), (4, 2), (5, 1), (6, 0)]:
        surf.fill(c, (x + dx, y + dy, 1, 1))
