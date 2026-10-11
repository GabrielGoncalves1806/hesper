"""Tela de título (Continuar · Novo jogo · Sair) e o aviso "Jogo salvo" do HUD.

O App (app.py) só repassa teclado/mouse pra cá e recebe de volta uma ação:
"continue", "new" ou "quit". Quem carrega, salva e troca de modo é o App.

Fundo: a cratera do estágio 1 desenhada pelo próprio Renderer, com a câmera passeando devagar,
borrada (diminui a imagem 4× e estica de volta: blur barato) e escurecida, com poeira por cima.
Igual ao resto da UI, menus e textos são desenhados em 480×270 e esticados 2×.
"""

import math

import pygame

from game import config as C
from game import save
from game.assets import load_font
from game.systems import GameState
from game.ui import UH, UW, fmt
from game.world import hash01

UP_KEYS = (pygame.K_w, pygame.K_UP)
DOWN_KEYS = (pygame.K_s, pygame.K_DOWN)
OK_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)

MENU_X, MENU_W, MENU_Y = 140, 200, 132   # caixa do menu (coordenadas da UI, 480×270)
ROW_H, ROW_GAP = 19, 22
BLUR = 4                                 # quanto o fundo é reduzido antes de esticar (maior = mais borrado)


class TitleScreen:
    def __init__(self, ui, renderer, play):
        self.ui = ui                    # a UI do jogo (fontes, text(), panel()...)
        self.renderer = renderer        # desenha a cratera do fundo
        self.play = play                # audio.play: sons de menu
        self.font_title = load_font("Silkscreen-Regular.ttf", 32, 48)
        self.saved: GameState | None = None   # o save já carregado (None = não tem save válido)
        self.confirming = False         # "Novo jogo" com save existente: pedindo confirmação
        self.selected = 0
        self.items: list[pygame.Rect] = []    # linhas clicáveis (coordenadas da UI)
        self._background: GameState | None = None
        self._shade = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        self._shade.fill((10, 5, 4, 135))

    def open(self, saved: GameState | None) -> None:
        self.saved = saved
        self.confirming = False
        self.selected = 0

    # ---- opções ----------------------------------------------------------------
    def options(self) -> list[tuple[str, str]]:
        """(ação, texto) de cada linha do menu, na ordem."""
        if self.confirming:
            return [("cancel", "Não, voltar"), ("confirm_new", "Sim, começar do zero")]
        options = [("continue", "Continuar")] if self.saved else []
        return options + [("new", "Novo jogo"), ("quit", "Sair")]

    def activate(self, index: int) -> str | None:
        """Executa a linha `index`. Devolve a ação pro App ("continue", "new", "quit") ou None."""
        action = self.options()[index][0]
        if action == "new" and self.saved:          # já tem save: confirma antes de apagar
            self.confirming, self.selected = True, 0
            self.play("ui_open")
            return None
        if action == "cancel":
            self._cancel()
            return None
        return "new" if action == "confirm_new" else action

    def _cancel(self) -> None:
        self.confirming = False
        self.selected = [a for a, _ in self.options()].index("new")
        self.play("ui_close")

    # ---- input -----------------------------------------------------------------
    def on_key(self, key: int) -> str | None:
        if key in UP_KEYS or key in DOWN_KEYS:
            step = -1 if key in UP_KEYS else 1
            self.selected = (self.selected + step) % len(self.options())
            self.play("ui_click")
        elif key in OK_KEYS:
            return self.activate(self.selected)
        elif key == pygame.K_ESCAPE and self.confirming:
            self._cancel()
        return None

    def hover(self, ux: float, uy: float) -> None:
        for i, rect in enumerate(self.items):
            if rect.collidepoint(ux, uy) and i != self.selected:
                self.selected = i

    def click(self, ux: float, uy: float) -> str | None:
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

    def draw(self, canvas: pygame.Surface, t: float, mouse: tuple[int, int]) -> None:
        ui = self.ui
        self.draw_background(canvas, t)
        ui.begin()
        self._draw_dust(t)
        self._draw_logo()
        if self.confirming:
            self._draw_confirm()
        else:
            self._draw_menu()
        ui.text("[W/S] ESCOLHE · [ENTER] OK", UW / 2, UH - 16, C.C_MUTED, align="center")
        ui.draw_cursor(mouse[0] / 2, mouse[1] / 2)
        ui.finish(canvas)

    def _draw_dust(self, t: float) -> None:
        """Poeira laranja nítida passando na frente do fundo borrado."""
        for i in range(55):
            speed = 6 + 14 * hash01(i, 2, 31)
            x = (hash01(i, 1, 31) * UW + t * speed) % UW
            y = hash01(i, 3, 31) * UH + math.sin(t * 0.8 + i) * 4
            alpha = 70 + int(120 * hash01(i, 4, 31))
            self.ui.fill((226, 160, 110, alpha), (int(x), int(y), 1 + (i % 5 == 0), 1))

    def _draw_logo(self) -> None:
        """'HESPER' grande em Silkscreen, com letras espaçadas, sombra e um traço laranja embaixo."""
        surf, font = self.ui.surf, self.font_title
        letters = [font.render(ch, False, pygame.Color(C.C_TEXT)) for ch in "HESPER"]
        shadows = [font.render(ch, False, (0, 0, 0)) for ch in "HESPER"]
        spacing = 6
        total = sum(img.get_width() for img in letters) + spacing * (len(letters) - 1)
        x, y = UW // 2 - total // 2, 44
        for img, shadow in zip(letters, shadows):
            shadow.set_alpha(170)
            surf.blit(shadow, (x + 2, y + 2))
            surf.blit(img, (x, y))
            x += img.get_width() + spacing
        line_y = y + letters[0].get_height() + 2
        surf.fill(pygame.Color(C.C_ACCENT), (UW // 2 - 40, line_y, 80, 2))
        self.ui.text("Planeta sem ar. Por enquanto.", UW / 2, line_y + 8, "#d9cfc4", self.ui.body, "center")

    def _row(self, i: int, label: str, y: int) -> pygame.Rect:
        """Uma linha de menu no estilo do menu de pausa."""
        ui = self.ui
        row = pygame.Rect(MENU_X + 8, y, MENU_W - 16, ROW_H)
        selected = i == self.selected
        ui.surf.fill(pygame.Color("#2c1e18" if selected else "#211915"), row)
        pygame.draw.rect(ui.surf, pygame.Color(C.C_ACCENT if selected else "#3a2c25"), row, 1)
        ui.text(label, row.x + 8, row.y + 3, C.C_TEXT if selected else "#d9cfc4", ui.body)
        self.items.append(row)
        return row

    def _box(self, y: int, h: int, title: str | None = None) -> None:
        ui = self.ui
        ui.panel(MENU_X, y, MENU_W, h, (20, 14, 12, 225))
        ui.surf.fill(pygame.Color(C.C_ACCENT), (MENU_X, y, MENU_W, 2))
        if title:
            ui.text(title, MENU_X + 8, y + 7, C.C_TI)

    def _draw_menu(self) -> None:
        self.items = []
        options = self.options()
        self._box(MENU_Y, 8 + ROW_GAP * len(options) + 2)
        for i, (action, label) in enumerate(options):
            row = self._row(i, label, MENU_Y + 8 + i * ROW_GAP)
            if action == "continue":     # resumo do save, à direita da linha
                minutes = int(self.saved.play_time // 60)
                info = f"TI {fmt(self.saved.ti)} · {minutes} MIN"
                self.ui.text(info, row.right - 8, row.y + 6, C.C_TI if i == self.selected else C.C_MUTED,
                             align="right")

    def _draw_confirm(self) -> None:
        self.items = []
        y = MENU_Y - 8
        h = 46 + ROW_GAP * 2 + 2
        self._box(y, h, "NOVO JOGO")
        self.ui.text("O save atual vai ser apagado.", MENU_X + 8, y + 20, "#d9cfc4", self.ui.body)
        for i, (_, label) in enumerate(self.options()):
            self._row(i, label, y + 38 + i * ROW_GAP)


def draw_saved_notice(ui, time_left: float) -> None:
    """Aviso discreto "Jogo salvo" logo abaixo do painel do Ti, sumindo no último meio segundo."""
    alpha = max(0.0, min(1.0, time_left / 0.5))
    label = "Jogo salvo"
    w = ui.body.size(label)[0] + 24
    h = 17
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    ui.panel(0, 0, w, h, target=layer)
    _check(layer, 6, 6)
    ui.text(label, 17, 2, C.C_OK, ui.body, target=layer)
    layer.set_alpha(int(255 * alpha))
    ui.surf.blit(layer, (UW - 6 - w, 100))


def _check(surf: pygame.Surface, x: int, y: int) -> None:
    """Tique ✓ de pixels (o mesmo desenho do UI.draw_check, mas numa superfície qualquer)."""
    c = pygame.Color(C.C_OK)
    for dx, dy in [(0, 3), (1, 4), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (1, 3), (2, 4), (3, 3), (4, 2), (5, 1), (6, 0)]:
        surf.fill(c, (x + dx, y + dy, 1, 1))
