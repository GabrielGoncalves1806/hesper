"""Interface: HUD, fabricador, terminal, banner de estágio, O₂ crítico, desmaio e tela de fim.

Igual ao mockup, a UI é desenhada numa superfície de 480×270 (metade da tela)
e depois esticada 2× sem suavizar. Isso deixa as fontes pixeladas nítidas e
permite copiar as coordenadas do mockup quase direto.
Algumas coisas precisam da resolução cheia (ícones 16×16, prévia das máquinas):
essas vão pra lista `self.native`, desenhada por cima depois da escala.
"""

import math

import pygame

from game import config as C
from game import energy
from game.assets import Sprites, load_font
from game.inventory import Inventory, Stack
from game.systems import GameState, eta_label, stage_progress

UW, UH = C.UI_W, C.UI_H
TI_PANEL_W = 160                 # painel do Ti (em cima à direita)
TI_PANEL_X = UW - 6 - TI_PANEL_W
# inventário e hotbar (coordenadas da UI, metade da tela): slot de 20×20 (= ui_slot.png) com 2 de vão
SLOT, SLOT_GAP = 20, 2
SLOT_STEP = SLOT + SLOT_GAP
GRID_W = 8 * SLOT_STEP - SLOT_GAP                # 8 colunas = 174
HOTBAR_X, HOTBAR_Y = (UW - GRID_W) // 2, UH - 6 - SLOT
# seletor "Drones entregam" do baú (draw_chest_filter): uma linha logo abaixo do título do painel
FILTER_ROW = 22                                  # altura que a linha ocupa (o grid do baú desce isso)
FILTER_BTN = 18                                  # botão com ícone: 18×18 (ícone 16 + 1 de borda)
FILTER_ALL_W = 26                                # botão "TUDO"
FILTER_NAME = {"all": "TUDO", **C.RESOURCE_LABEL}


# Dígitos 5×7 desenhados à mão, no traço fino da Pixelify. Em 11 px a fonte desenha o "5" igual
# a um "S" (Ti 500 vira "Ti S00"), o "2" parece "Z" e o "6" sai torto.
DIGITS = {
    "0": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
}
DIGIT_ADVANCE = 7      # 1 px de margem + 5 px de dígito + 1 de espaço (igual ao avanço da Pixelify)


class PixelDigitsFont:
    """A Pixelify Sans, mas com os números desenhados em pixels (DIGITS).

    Tem os mesmos size() e render() de uma pygame.font.Font, então serve em qualquer lugar onde a
    fonte era usada (medidas, quebra de linha, HUD, menus). Só os dígitos mudam; as letras são da fonte.
    """

    def __init__(self, font: pygame.font.Font):
        self.font = font
        # topo dos dígitos alinhado com o das letras maiúsculas (7 px acima da linha de base)
        self.digit_top = max(0, font.get_ascent() - 7)

    @staticmethod
    def _runs(text: str) -> list[str]:
        """'Ti 500 x' -> ['Ti ', '500', ' x']: separa sequências de dígitos do resto."""
        runs: list[str] = []
        for ch in text:
            if runs and runs[-1][-1].isdigit() == ch.isdigit():
                runs[-1] += ch
            else:
                runs.append(ch)
        return runs

    def size(self, text: str) -> tuple[int, int]:
        width = sum(DIGIT_ADVANCE * len(r) if r[0].isdigit() else self.font.size(r)[0] for r in self._runs(text))
        return width, self.font.get_height()

    def get_height(self) -> int:
        return self.font.get_height()

    def render(self, text: str, antialias: bool, color) -> pygame.Surface:
        if not any(ch.isdigit() for ch in text):
            return self.font.render(text, antialias, color)
        surf = pygame.Surface(self.size(text), pygame.SRCALPHA)
        x = 0
        for run in self._runs(text):
            if run[0].isdigit():
                for ch in run:
                    for dy, row in enumerate(DIGITS[ch]):
                        for dx, cell in enumerate(row):
                            if cell == "#":
                                surf.fill(color, (x + 1 + dx, self.digit_top + dy, 1, 1))
                    x += DIGIT_ADVANCE
            else:
                surf.blit(self.font.render(run, antialias, color), (x, 0))
                x += self.font.size(run)[0]     # avança pela medida (a imagem perde o espaço do fim)
        return surf


def fmt(n: float) -> str:
    """12400 -> '12.400' (separador de milhar brasileiro)."""
    return f"{round(n):,}".replace(",", ".")


def fmt_rate(n: float) -> str:
    return (f"{n:.1f}".replace(".", ",") if n % 1 else str(int(n)))


def item_name(item: str) -> str:
    """Nome de um item do inventário pra mostrar ao jogador ('Ferro', 'Gerador de O2', 'Baú')."""
    if item in C.RESOURCE_NAME:
        return C.RESOURCE_NAME[item].capitalize()
    return C.MACHINES[item].name


def wrap(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split(" "):
        test = f"{line} {word}" if line else word
        if font.size(test)[0] > max_w and line:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    return lines


class FloatingTexts:
    """Textinhos que sobem e somem ('+2 FERRO', '+O2'). Posição em pixels do mundo."""

    def __init__(self):
        self.items: list[list] = []   # [texto, x, y, cor, vida]

    def add(self, text: str, x: float, y: float, color: str) -> None:
        self.items.append([text, x, y, color, 1.2])

    def update(self, dt: float) -> None:
        for it in self.items:
            it[2] -= 22 * dt
            it[4] -= dt
        self.items = [it for it in self.items if it[4] > 0]


class UI:
    def __init__(self):
        self.surf = pygame.Surface((UW, UH), pygame.SRCALPHA)
        self.native: list[tuple[pygame.Surface, tuple[int, int]]] = []
        self.font = load_font("Silkscreen-Regular.ttf", 8, 12)        # rótulos
        self.font_big = load_font("Silkscreen-Regular.ttf", 16, 22)   # títulos
        # textos: Pixelify 11 px (em 10 e 12 o "G" vira "Q"), com os dígitos desenhados em pixels
        self.body = PixelDigitsFont(load_font("PixelifySans.ttf", 11, 13))
        self.body_big = PixelDigitsFont(load_font("PixelifySans.ttf", 11, 16))   # títulos: mesmo tamanho (o "G" só fica certo em 11), destaque pela cor
        self._text_cache: dict[tuple, pygame.Surface] = {}
        self._tmp: dict[tuple, pygame.Surface] = {}
        self.fabricator_buttons: list[tuple[pygame.Rect, str]] = []   # retângulos clicáveis (coord. da UI)
        self.fabricator_rows: list[tuple[pygame.Rect, str]] = []
        self.pause_items: list[pygame.Rect] = []      # linhas clicáveis do menu de pausa (coord. da UI)
        self.pause_sliders: list[pygame.Rect] = []    # barras dos sliders de volume
        # slots clicáveis da tela de inventário/baú: (retângulo na UI, inventário, índice do slot)
        self.slot_rects: list[tuple[pygame.Rect, Inventory, int]] = []
        self.filter_buttons: list[tuple[pygame.Rect, str]] = []   # seletor de filtro do baú: (retângulo, filtro)
        self.slot_img = Sprites().get("ui_slot")      # moldura opcional (bíblia §8); sem ela, desenhamos

    # ---- primitivas -----------------------------------------------------------
    def begin(self) -> None:
        self.surf.fill((0, 0, 0, 0))
        self.native.clear()

    def finish(self, canvas: pygame.Surface) -> None:
        canvas.blit(pygame.transform.scale(self.surf, (C.SCREEN_W, C.SCREEN_H)), (0, 0))
        for surf, pos in self.native:
            canvas.blit(surf, pos)

    def _render(self, font, text, color) -> pygame.Surface:
        key = (id(font), text, color)
        surf = self._text_cache.get(key)
        if surf is None:
            if len(self._text_cache) > 600:
                self._text_cache.clear()
            if font in (self.body, self.body_big):
                # A Pixelify Sans junta "fi"/"fl" numa ligadura que fica ilegível em 10 px.
                # Um "zero-width non-joiner" (invisível) entre as letras impede isso.
                text = text.replace("fi", "f\u200ci").replace("fl", "f\u200cl")
            surf = font.render(text, False, pygame.Color(color))
            self._text_cache[key] = surf
        return surf

    def text(self, s: str, x: float, y: float, color: str, font=None, align: str = "left", target=None) -> int:
        """Texto com sombrinha preta (igual ao mockup). Devolve a largura."""
        font = font or self.font
        target = target or self.surf
        img = self._render(font, s, color)
        shadow = self._render(font, s, "#000000")
        w = img.get_width()
        x = x - w if align == "right" else x - w // 2 if align == "center" else x
        x, y = int(x), int(y)
        shadow.set_alpha(165)
        target.blit(shadow, (x + 1, y + 1))
        target.blit(img, (x, y))
        return w

    def fill(self, rgba, rect, target=None) -> None:
        """Retângulo com transparência que MISTURA com o que já está embaixo."""
        target = target or self.surf
        rect = pygame.Rect(rect)
        if len(rgba) == 3 or rgba[3] == 255:
            target.fill(rgba, rect)
            return
        key = (rect.w, rect.h)
        tmp = self._tmp.get(key)
        if tmp is None:
            tmp = self._tmp[key] = pygame.Surface(key, pygame.SRCALPHA)
        tmp.fill(rgba)
        target.blit(tmp, rect.topleft)

    def panel(self, x, y, w, h, bg=(14, 10, 9, 204), target=None) -> None:
        self.fill(bg, (x, y, w, h), target)
        pygame.draw.rect(target or self.surf, (255, 255, 255, 40), (x, y, w, h), 1)

    # ---- HUD ------------------------------------------------------------------
    def draw_hud(self, state: GameState, t: float, hint: str | None, icons: dict[str, pygame.Surface]) -> None:
        crit = state.o2 < C.O2_LOW
        blink = crit and (t * 9) % 6 < 3
        o2 = state.o2 / C.O2_MAX
        # barra de O₂
        self.panel(6, 6, 112, 26)
        self.text("O2", 11, 10, C.C_ALERT if crit else C.C_O2)
        self.fill((20, 35, 42), (30, 11, 82, 7))
        bar = (C.C_ALERT if blink else "#c2281c") if crit else C.C_O2
        self.surf.fill(pygame.Color(bar), (30, 11, round(82 * o2), 7))
        self.fill((255, 255, 255, 64), (30, 11, round(82 * o2), 1))
        for i in range(1, 10):
            self.fill((0, 0, 0, 90), (30 + int(i * 8.2), 11, 1, 7))
        self.text(f"{round(o2 * 100)}%", 30, 21, "#ff8a7a" if crit else "#a8c9d2")

        # painel do Ti e, logo embaixo, o medidor de energia
        self.draw_ti_panel(state)
        self.draw_energy(state)

        # resumo do inventário (total de cada recurso, somando as pilhas); os slots ficam na hotbar e no Tab
        counts = [str(state.inventory.count(res)) for res in C.RESOURCES]
        w = 6 + sum(14 + self.font.size(n)[0] + 6 for n in counts)
        self.panel(6, UH - 26, w, 20)
        x = 12
        for res, n in zip(C.RESOURCES, counts):
            self.native.append((icons[res], (x * 2, (UH - 20) * 2)))
            x += 14 + self.text(n, x + 12, UH - 20, C.C_TEXT) + 6

        if hint:
            w = self.body.size(hint)[0] + 14
            # dica embaixo à direita; se for comprida e encostar na hotbar, sobe uma linha
            y = UH - 26 if UW - 6 - w >= HOTBAR_X + GRID_W + 6 else HOTBAR_Y - 34
            self.panel(UW - 6 - w, y, w, 20)
            self.text(hint, UW - 13, y + 4, C.C_TEXT, self.body, "right")

        if state.time_scale != 1:
            self.text(f"DEBUG · TEMPO x{state.time_scale}", UW // 2, 8, C.C_TI, align="center")

    def draw_ti_panel(self, state: GameState) -> None:
        """Ti total, os 3 índices e, embaixo, quanto falta pro próximo estágio."""
        px, w = TI_PANEL_X, TI_PANEL_W
        right = px + w - 6            # borda direita do texto
        inner = w - 12                # largura útil
        nxt, fraction, remaining = stage_progress(state.ti)
        eta = eta_label(remaining, state.smoothed_rate)
        line2 = f"faltam {fmt(remaining)} · {eta}"
        wrap_eta = self.body.size(line2)[0] > inner      # não coube: o tempo desce pra uma 3ª linha
        h = 64 if nxt is None else 90 if wrap_eta else 78
        self.panel(px, 6, w, h)
        self.ti_panel_bottom = 6 + h      # o medidor de energia encaixa logo abaixo (draw_energy)

        self.text("TI", px + 6, 10, C.C_TI)
        rate = state.ti_rate * state.time_scale
        if rate:
            self.text(f"+{fmt_rate(rate)}/S", px + 22, 10, C.C_OK)
        self.text(fmt(state.ti), right, 10, C.C_TI, align="right")
        self.fill((255, 255, 255, 30), (px + 6, 20, inner, 1))
        for i, key in enumerate(("o2", "heat", "water")):
            yy = 24 + i * 10
            self.surf.fill(pygame.Color(C.INDEX_COLOR[key]), (px + 6, yy + 2, 4, 4))
            self.text(C.INDEX_LABEL[key], px + 14, yy, "#d9cfc4")
            self.text(f"{fmt(state.indices[key])} {C.INDEX_UNIT[key]}", right, yy, C.C_TEXT, align="right")

        # ---- próximo estágio
        self.fill((255, 255, 255, 30), (px + 6, 55, inner, 1))
        if nxt is None:
            done = C.STAGE_COLOR[3]
            label_w = self.text("PLANETA VERDE", px + 6, 59, done)
            self.draw_check(px + 6 + label_w + 5, 59, done)   # a fonte não tem "✓": desenhamos um
            return
        label_w = self.text(f"PRÓXIMO: {nxt.name}", px + 6, 59, C.C_TEXT)
        percent = f"{int(fraction * 100)}%"
        pct_w = self.text(percent, right, 59, C.C_TI, align="right")
        bar_x = px + 6 + label_w + 5
        bar_w = right - pct_w - 5 - bar_x
        self.surf.fill(pygame.Color("#4a3b2a"), (bar_x, 60, bar_w, 6))          # trilho (visível mesmo em 0%)
        self.surf.fill(pygame.Color("#1b1411"), (bar_x + 1, 61, bar_w - 2, 4))
        self.surf.fill(pygame.Color(C.C_TI), (bar_x + 1, 61, round((bar_w - 2) * fraction), 4))
        if wrap_eta:
            self.text(f"faltam {fmt(remaining)}", px + 6, 68, C.C_MUTED, self.body)
            self.text_tilde(eta, px + 6, 80, C.C_MUTED)
        else:
            self.text_tilde(line2, px + 6, 68, C.C_MUTED)

    # ---- energia (lógica em energy.py) ----------------------------------------
    ENERGY_COLOR = {"ok": C.C_OK, "tight": "#ffd84a", "deficit": C.C_ALERT}

    def draw_energy(self, state: GameState) -> None:
        """Medidor discreto embaixo do painel do Ti: raio + barrinha + "produção/consumo KW".

        Verde quando sobra, amarelo perto do limite e vermelho no déficit (com o aviso embaixo).
        """
        power = state.power
        color = self.ENERGY_COLOR[power.level]
        px, w = TI_PANEL_X, TI_PANEL_W
        right = px + w - 6
        y = getattr(self, "ti_panel_bottom", 84) + 4
        warning = []
        if power.deficit:
            warning = [f"Energia insuficiente · máquinas a {int(power.factor * 100)}%"]
            if self.body.size(warning[0])[0] > w - 12:    # não coube numa linha: quebra no "·"
                warning = warning[0].split(" · ")
        self.panel(px, y, w, 15 + 12 * len(warning))
        self.draw_bolt(px + 6, y + 4, C.C_ENERGY if not power.deficit else C.C_ALERT)
        label_w = self.text("ENERGIA", px + 14, y + 4, C.C_TEXT)
        value_w = self.text(f"{fmt_rate(power.production)}/{fmt_rate(power.consumption)} KW", right, y + 4, color,
                            align="right")
        # barrinha de uso: quanto do que é produzido está sendo consumido (cheia e vermelha no déficit)
        bar_x = px + 14 + label_w + 5
        bar_w = right - value_w - 5 - bar_x
        used = 1.0 if power.production <= 0 else min(1.0, power.consumption / power.production)
        self.surf.fill(pygame.Color("#4a3b2a"), (bar_x, y + 5, bar_w, 6))
        self.surf.fill(pygame.Color("#1b1411"), (bar_x + 1, y + 6, bar_w - 2, 4))
        self.surf.fill(pygame.Color(color), (bar_x + 1, y + 6, round((bar_w - 2) * used), 4))
        for i, line in enumerate(warning):
            self.text(line, px + 6, y + 14 + 12 * i, "#ff8a7a", self.body)

    def draw_bolt(self, x: int, y: int, color: str) -> None:
        """Raio de pixels (5×8): a fonte não tem o "⚡"."""
        rows = ["  ###", " ### ", " ##  ", "#####", "  ## ", " ##  ", " #   ", "#    "]
        c = pygame.Color(color)
        for dy, row in enumerate(rows):
            for dx, cell in enumerate(row):
                if cell == "#":
                    self.surf.fill((0, 0, 0), (x + dx + 1, y + dy + 1, 1, 1))
        for dy, row in enumerate(rows):
            for dx, cell in enumerate(row):
                if cell == "#":
                    self.surf.fill(c, (x + dx, y + dy, 1, 1))

    def text_tilde(self, s: str, x: int, y: int, color: str) -> None:
        """Texto da Pixelify com "~" desenhado à mão: em 11 px o til da fonte vira um borrão."""
        parts = s.split("~")
        for i, part in enumerate(parts):
            if i > 0:
                for dx, dy in [(0, 1), (1, 0), (2, 0), (3, 1), (4, 1), (5, 0)]:     # zigue-zague de 6×2
                    self.surf.fill((0, 0, 0), (x + dx + 1, y + 6 + dy + 1, 1, 1))
                    self.surf.fill(pygame.Color(color), (x + dx, y + 6 + dy, 1, 1))
                x += 8
            if part:
                x += self.text(part, x, y, color, self.body)

    def draw_check(self, x: int, y: int, color: str) -> None:
        """Tique ✓ de pixels (7×6)."""
        c = pygame.Color(color)
        for dx, dy in [(0, 3), (1, 4), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (1, 3), (2, 4), (3, 3), (4, 2), (5, 1), (6, 0)]:
            self.surf.fill(c, (x + dx, y + dy, 1, 1))

    # ---- objetivos (tutorial leve, lógica em objectives.py) -------------------
    def draw_objectives(self, lines) -> None:
        """Painel logo abaixo do de O₂: 'OBJETIVO' + até 2 linhas (concluído/atual/próximo)."""
        if not lines:
            return
        x, y = 6, 40                              # O₂ ocupa y 6–32 e o banner de estágio vai até y 36
        w = max(112, max(self.body.size(line.text)[0] for line in lines) + 26)
        h = 15 + 13 * len(lines)
        self.panel(x, y, w, h)
        self.text("OBJETIVO", x + 6, y + 4, C.C_ACCENT)
        for i, line in enumerate(lines):
            ly = y + 13 + i * 13
            if line.style == "done":              # acabou de cumprir: verde com ✓
                self.fill((127, 214, 122, 40), (x + 2, ly + 1, w - 4, 12))
                self.draw_check(x + 6, ly + 4, C.C_OK)
                self.text(line.text, x + 16, ly, C.C_OK, self.body)
            elif line.style == "current":
                self.surf.fill(pygame.Color(C.C_TI), (x + 8, ly + 5, 3, 3))
                self.text(line.text, x + 16, ly, C.C_TEXT, self.body)
            else:                                 # próximo: esmaecido
                self.surf.fill(pygame.Color("#5a4a40"), (x + 8, ly + 5, 3, 3))
                self.text(line.text, x + 16, ly, "#7a6c62", self.body)

    def draw_floaters(self, floaters: FloatingTexts, cam: tuple[int, int], zoom: float = 1.0) -> None:
        """Textos presos num ponto do mundo: a posição acompanha o zoom, o tamanho da letra não."""
        for text, x, y, color, life in floaters.items:
            sx, sy = (x - cam[0]) * zoom / 2, (y - cam[1]) * zoom / 2
            if -40 < sx < UW + 40 and -20 < sy < UH + 20:
                self.text(text, sx, sy, color, align="center")

    # ---- O₂ crítico -----------------------------------------------------------
    def draw_o2_critical(self, state: GameState, t: float, cam: tuple[int, int]) -> None:
        tick = t * 9
        if tick % 8 < 5:
            self.text("OXIGENIO CRITICO", UW / 2, 62, "#ff5a4a", self.font_big, "center")
        meters = round(state.dist_to_base() / C.TILE)
        self.text(f"Volte para a base · {meters} m", UW / 2, 84, "#ffd0c8", self.body, "center")
        # seta apontando pra base, numa elipse em volta do centro da tela
        px, py = (state.player.x - cam[0]) / 2, (state.player.y - 16 - cam[1]) / 2
        bx, by = (C.BASE_CENTER[0] - cam[0]) / 2, (C.BASE_CENTER[1] - cam[1]) / 2
        ang = math.atan2(by - py, bx - px)
        wobble = math.sin(t * 7) * 3
        cx, cy = UW / 2 + math.cos(ang) * (200 + wobble), UH / 2 + math.sin(ang) * (105 + wobble)
        tip = (cx + math.cos(ang) * 8, cy + math.sin(ang) * 8)
        left = (cx + math.cos(ang + 2.4) * 9, cy + math.sin(ang + 2.4) * 9)
        right = (cx + math.cos(ang - 2.4) * 9, cy + math.sin(ang - 2.4) * 9)
        pygame.draw.polygon(self.surf, pygame.Color(C.C_ALERT), [tip, left, right])
        lx, ly = cx - math.cos(ang) * 16, cy - math.sin(ang) * 14
        self.text("BASE", lx, ly - 4, "#ff9a8a", align="center")

    # ---- fabricador -----------------------------------------------------------
    def draw_fabricator(self, state: GameState, selected: int, machine_preview, t: float) -> None:
        """Menu de receitas. `machine_preview(kind)` devolve a imagem da máquina (resolução cheia)."""
        self.fill((8, 5, 4, 158), (0, 0, UW, UH))
        x, y, w, h = 66, 1, 348, 268
        # cabem 7 receitas de 34 de altura: com mais, a lista rola junto com a seleção (setinhas mostram
        # que tem mais); com menos, a altura se ajusta ao número de receitas
        visible = min(7, len(C.MACHINE_ORDER))
        row_h = min(34, (h - 20) // visible - 1)
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.text("FABRICADOR", x + 8, y + 6, C.C_TI)
        self.text("[W/S] ESCOLHE · [ENTER] CRAFTA · [E] FECHA", x + w - 8, y + 6, C.C_MUTED, align="right")
        self.fabricator_buttons.clear()
        self.fabricator_rows.clear()
        first = max(0, min(selected - visible + 1, len(C.MACHINE_ORDER) - visible))
        if first > 0:                                   # setinhas do lado do título
            self._arrow(x + 82, y + 5, up=True)
        if first + visible < len(C.MACHINE_ORDER):
            self._arrow(x + 82, y + 11, up=False)
        for i, kind in enumerate(C.MACHINE_ORDER[first:first + visible], start=first):
            m = C.MACHINES[kind]
            status = state.recipe_status(kind)
            ry = y + 20 + (i - first) * (row_h + 1)
            sel = i == selected
            row = pygame.Rect(x + 8, ry, w - 16, row_h)
            self.fabricator_rows.append((row, kind))
            self.surf.fill(pygame.Color("#2c1e18" if sel else "#211915"), row)
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if sel else "#3a2c25"), row, 1)
            # prévia da máquina em resolução cheia, sem redimensionar: caixa de 72×68 px reais,
            # base da máquina 2 px acima do fundo (nv.2 tem 64 px de altura: sobram 2 px em cima)
            box = pygame.Rect(x + 12, ry, 36, row_h)
            self.surf.fill(pygame.Color("#120d0b"), box)
            preview = machine_preview(kind)
            bw2, bh2 = box.w * 2, box.h * 2
            clip = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
            if preview.get_height() > bh2 - 2:     # linha baixa demais pra prévia (ex.: nv.2): encolhe pra caber
                ratio = (bh2 - 2) / preview.get_height()
                preview = pygame.transform.scale(preview, (round(preview.get_width() * ratio), bh2 - 2))
            clip.blit(preview, (bw2 // 2 - preview.get_width() // 2, bh2 - 2 - preview.get_height()))
            if status == "locked":   # receita bloqueada: prévia escurecida
                shade = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                shade.fill((18, 13, 11, 184))
                clip.blit(shade, (0, 0))
            self.native.append((clip, (box.x * 2, box.y * 2)))

            locked = status == "locked"
            tx = x + 56
            text_y = ry + (row_h - 32) // 2      # centraliza as 2 linhas de texto na linha
            name_w = self.text(m.name, tx, text_y + 4, "#8a7b70" if locked else C.C_TEXT, self.body_big)
            self.text(m.desc, tx + 6 + name_w, text_y + 4, C.C_MUTED, self.body)
            owned = state.inventory.count(kind)       # já fabricadas, no inventário
            top_end = tx + name_w + 6 + self.body.size(m.desc)[0]     # onde acaba o texto da 1ª linha
            if owned:
                top_end += 8 + self.text(f"x{owned}", top_end + 8, text_y + 5, C.C_OK)
            cx = tx
            for res, n in m.cost.items():
                have = state.available(res)              # inventário + baús da base
                label = f"{have}/{n} {C.RESOURCE_LABEL[res]}"
                color = "#6e6058" if locked else C.C_OK if have >= n else C.C_ALERT
                cx += self.text(label, cx, text_y + 21, color) + 8

            bx, by, bw, bh = x + w - 86, ry + (row_h - 20) // 2, 72, 20
            # energia: "-2 KW" (consome) ou "+3 KW" (gera), encostado à esquerda do botão
            use, gen = energy.machine_use(kind), energy.machine_gen(kind)
            if use or gen:
                kw = f"+{fmt_rate(gen)} KW" if gen else f"-{fmt_rate(use)} KW"
                kw_color = "#6e6058" if locked else C.C_OK if gen else "#ffd84a"
                kw_x = bx - 6 - self.font.size(kw)[0]
                if kw_x - 8 >= top_end + 4:          # o raio só entra se couber sem encostar no nome
                    self.draw_bolt(kw_x - 8, text_y + 4, kw_color)
                self.text(kw, kw_x, text_y + 5, kw_color)
            button = pygame.Rect(bx, by, bw, bh)
            if status == "ok":
                self.surf.fill(pygame.Color(C.C_ACCENT), button)
                self.surf.fill(pygame.Color("#f29a62"), (bx, by, bw, 1))
                self.text("CRAFTAR", bx + bw / 2, by + 6, "#1b1411", align="center")
                self.fabricator_buttons.append((button, kind))
            elif status == "missing":
                pygame.draw.rect(self.surf, pygame.Color(C.C_ALERT), button, 1)
                res = state.missing_resource(kind)
                self.text(f"SEM {C.RESOURCE_LABEL[res]}", bx + bw / 2, by + 6, C.C_ALERT, align="center")
            else:
                pygame.draw.rect(self.surf, pygame.Color("#5a4a40"), button, 1)
                self.surf.fill(pygame.Color(C.C_MUTED), (bx + 7, by + 9, 7, 6))          # cadeado
                pygame.draw.rect(self.surf, pygame.Color(C.C_MUTED), (bx + 8, by + 5, 5, 5), 1)
                self.text(f"TI {fmt(m.unlock_ti)}", bx + 42, by + 6, C.C_MUTED, align="center")

    # ---- inventário: slots, hotbar, tela do Tab e do baú ------------------------
    # Os ícones são 32×32 em resolução cheia (lista `native`), então o número da pilha também precisa
    # ir pra `native`, senão o ícone cobre ele.
    def native_text(self, s: str, x: float, y: float, color: str, align: str = "left") -> None:
        img, shadow = self._render(self.font, s, color), self._render(self.font, s, "#000000")
        layer = pygame.Surface((img.get_width() + 1, img.get_height() + 1), pygame.SRCALPHA)
        layer.blit(shadow, (1, 1))
        layer.blit(img, (0, 0))
        if align == "right":
            x -= img.get_width()
        self.native.append((pygame.transform.scale_by(layer, 2), (int(x * 2), int(y * 2))))

    def draw_slot(self, x: int, y: int, stack: Stack | None, item_icon, selected=False, hover=False) -> None:
        if self.slot_img:
            self.surf.blit(self.slot_img, (x, y))
        else:
            self.surf.fill(pygame.Color("#120d0b"), (x, y, SLOT, SLOT))
            pygame.draw.rect(self.surf, pygame.Color("#3a2c25"), (x, y, SLOT, SLOT), 1)
            self.surf.fill(pygame.Color("#000000"), (x + 1, y + 1, SLOT - 2, 1))      # sombrinha de "fundo"
        if hover:
            self.fill((255, 255, 255, 30), (x + 1, y + 1, SLOT - 2, SLOT - 2))
        if selected:
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT), (x - 1, y - 1, SLOT + 2, SLOT + 2), 2)
        if stack:
            self.native.append((item_icon(stack.item), (x * 2 + 4, y * 2 + 4)))
            if stack.count > 1:
                self.native_text(str(stack.count), x + SLOT - 1, y + SLOT - 9, C.C_TEXT, "right")

    def draw_hotbar(self, inventory: Inventory, selected: int, item_icon) -> None:
        """Os 8 primeiros slots do inventário no rodapé central, com o número da tecla (em cima de
        cada slot, pra não cobrir o ícone) e o selecionado destacado."""
        self.panel(HOTBAR_X - 3, HOTBAR_Y - 11, GRID_W + 6, SLOT + 14)
        for i in range(C.HOTBAR_SLOTS):
            x = HOTBAR_X + i * SLOT_STEP
            self.text(str(i + 1), x + SLOT / 2 + 1, HOTBAR_Y - 10, C.C_TI if i == selected else C.C_MUTED, align="center")
            self.draw_slot(x, HOTBAR_Y, inventory.slots[i], item_icon, selected=i == selected)

    def draw_notice(self, text: str, alpha: float) -> None:
        """Aviso curto no meio da tela, acima da hotbar ("Inventário cheio")."""
        w = self.body.size(text)[0] + 16
        layer = pygame.Surface((w, 18), pygame.SRCALPHA)
        self.panel(0, 0, w, 18, (40, 12, 9, 225), target=layer)
        layer.fill(pygame.Color(C.C_ALERT), (0, 0, w, 1))
        self.text(text, w / 2, 3, "#ffd0c8", self.body, "center", target=layer)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (UW // 2 - w // 2, HOTBAR_Y - 58))

    def draw_toast(self, text: str, alpha: float) -> None:
        """Aviso neutro e rápido no topo do centro ("Zoom 1,5×", "Tela cheia")."""
        text = text.upper()            # Silkscreen: na Pixelify de 11 px o "Z" parece um "2"
        w = self.font.size(text)[0] + 16
        layer = pygame.Surface((w, 15), pygame.SRCALPHA)
        self.panel(0, 0, w, 15, target=layer)
        layer.fill(pygame.Color(C.C_ACCENT), (0, 0, w, 1))
        self.text(text, w / 2, 4, C.C_TEXT, target=layer, align="center")
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (UW // 2 - w // 2, 40))   # logo abaixo do banner de estágio

    def _grid(self, inv: Inventory, indexes: list[int], x: int, y: int, item_icon, mouse, selected=None) -> None:
        """Desenha os slots `indexes` de `inv` em linhas de 8, a partir de (x, y), e guarda os retângulos."""
        for n, i in enumerate(indexes):
            sx, sy = x + (n % 8) * SLOT_STEP, y + (n // 8) * SLOT_STEP
            rect = pygame.Rect(sx, sy, SLOT, SLOT)
            self.draw_slot(sx, sy, inv.slots[i], item_icon, selected=i == selected, hover=rect.collidepoint(mouse))
            self.slot_rects.append((rect, inv, i))

    def _window(self, x: int, y: int, w: int, h: int, title: str, color: str) -> None:
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.surf.fill(pygame.Color(color), (x, y, w, 2))
        self.text(title, x + 8, y + 6, color)

    def draw_inventory(self, inventory: Inventory, chest: Inventory | None, hotbar_selected: int,
                       item_icon, mouse: tuple[float, float], chest_filter: str | None = None) -> None:
        """Tela do Tab (só o inventário) ou do baú (inventário à esquerda, baú à direita).
        Inventário: mochila (slots 8–15) em cima, hotbar (slots 0–7) embaixo, igual à ordem da tela."""
        self.slot_rects.clear()
        self.filter_buttons.clear()
        self.fill((8, 5, 4, 158), (0, 0, UW, UH))
        pw = GRID_W + 16
        ph_inv = 20 + 6 + SLOT + 14 + SLOT + 8                  # título, mochila, rótulo HOTBAR, hotbar
        ph_chest = 20 + 6 + 3 * SLOT_STEP - SLOT_GAP + 8 + FILTER_ROW
        total_w = pw if chest is None else 2 * pw + 10
        x = (UW - total_w) // 2
        h = ph_inv if chest is None else max(ph_inv, ph_chest)
        y = (UH - h) // 2 - 16

        self._window(x, y, pw, h, "INVENTÁRIO", C.C_TI)
        used = sum(1 for s in inventory.slots if s)
        self.text(f"{used}/{len(inventory)}", x + pw - 8, y + 6, C.C_MUTED, align="right")
        hb = C.HOTBAR_SLOTS
        self._grid(inventory, list(range(hb, len(inventory))), x + 8, y + 26, item_icon, mouse)
        self.text("HOTBAR", x + 8, y + 26 + SLOT + 4, C.C_MUTED)
        self._grid(inventory, list(range(hb)), x + 8, y + 26 + SLOT + 14, item_icon, mouse, hotbar_selected)

        if chest is not None:
            cx = x + pw + 10
            self._window(cx, y, pw, h, "BAÚ", C.C_ACCENT)
            used = sum(1 for s in chest.slots if s)
            self.text(f"{used}/{len(chest)}", cx + pw - 8, y + 6, C.C_MUTED, align="right")
            self.draw_chest_filter(cx + 8, y + 22, pw - 16, chest_filter or "all", item_icon, mouse)
            self._grid(chest, list(range(len(chest))), cx + 8, y + 26 + FILTER_ROW, item_icon, mouse)

        keys = "[CLIQUE] PEGA/SOLTA · [DIREITO] METADE"
        keys += " · [SHIFT+CLIQUE] MANDA PRO OUTRO LADO" if chest is not None else ""
        keys += " · [ESC] FECHA"
        self.text(keys, UW / 2, y + h + 6, C.C_MUTED, align="center")

    # ---- filtro do baú pros drones (bloco autocontido: desenho + hit-test) ---------
    def draw_chest_filter(self, x: int, y: int, w: int, current: str, item_icon, mouse) -> None:
        """Linha "DRONES TRAZEM: [TUDO] [ferro] [silício] [gelo]" a partir de (x, y), largura `w`.
        O ativo fica com a borda laranja. Guarda os botões em `filter_buttons` (ver chest_filter_at)."""
        self.fill((0, 0, 0, 70), (x, y, w, FILTER_BTN + 2))
        self.text("DRONES TRAZEM:", x + 3, y + 6, C.C_MUTED)
        bx = x + w - 1 - FILTER_ALL_W - len(C.RESOURCES) * (FILTER_BTN + 2)
        for value in C.CHEST_FILTERS:
            bw = FILTER_ALL_W if value == "all" else FILTER_BTN
            rect = pygame.Rect(bx, y + 1, bw, FILTER_BTN)
            active, hover = value == current, rect.collidepoint(mouse)
            self.surf.fill(pygame.Color("#3a2a22" if active else "#120d0b"), rect)
            if hover and not active:
                self.fill((255, 255, 255, 30), rect.inflate(-2, -2))
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if active else "#3a2c25"), rect, 1)
            if value == "all":
                self.text("TUDO", rect.centerx + 1, y + 6, C.C_TEXT if active else C.C_MUTED, align="center")
            else:
                icon = item_icon(value)
                if not active:                      # inativo: ícone apagado, o ativo salta aos olhos
                    icon = icon.copy()
                    icon.set_alpha(150)
                self.native.append((icon, (rect.x * 2 + 2, rect.y * 2 + 2)))
            self.filter_buttons.append((rect, value))
            bx += bw + 2

    def chest_filter_at(self, pos) -> str | None:
        """Qual filtro está debaixo de `pos` (coordenadas da UI), ou None."""
        return next((value for rect, value in self.filter_buttons if rect.collidepoint(pos)), None)

    # ---- rótulo flutuante do baú no mundo -------------------------------------------
    @staticmethod
    def chest_label_parts(chest) -> list[tuple[str, str]]:
        """O que vai no rótulo em cima do baú: [("icon", minério)] e/ou [("text", ...)]. Vazio = sem rótulo."""
        parts = []
        if chest.filter != "all":
            parts.append(("icon", chest.filter))
        return parts

    def draw_chest_labels(self, chests, cam: tuple[int, int], zoom: float, icons: dict) -> None:
        """Rótulo pequeno em cima de cada baú de `chests` (presos no mundo, tamanho fixo na tela).
        `icons`: ícones 16×16 dos minérios (desenhados em resolução cheia, 8 px na UI)."""
        for chest in chests:
            parts = self.chest_label_parts(chest)
            if not parts:
                continue
            widths = [8 if kind == "icon" else self.font.size(value)[0] for kind, value in parts]
            w = sum(widths) + 3 * (len(parts) - 1) + 6
            ax, ay = chest.anchor
            top = ay - C.CHEST_SPRITE_SIZE[1] - 4                 # um pouco acima da tampa (mundo)
            sx, sy = (ax - cam[0]) * zoom / 2, (top - cam[1]) * zoom / 2
            x, y = int(sx - w / 2), int(sy - 12)
            if not (-w < x < UW and -12 < y < UH):
                continue
            self.panel(x, y, w, 12, (14, 10, 9, 215))
            px = x + 3
            for (kind, value), pw in zip(parts, widths):
                if kind == "icon":
                    self.native.append((icons[value], (px * 2, (y + 2) * 2)))
                else:
                    self.text(value, px, y + 3, C.C_TEXT)
                px += pw + 3

    def draw_held_and_tooltip(self, held: Stack | None, hovered: Stack | None, mouse, item_icon) -> None:
        """Por cima de tudo: a pilha presa no cursor ou, sem nada na mão, o nome do item debaixo do mouse."""
        mx, my = mouse
        if held is not None:
            self.native.append((item_icon(held.item), (int(mx * 2) + 6, int(my * 2) + 6)))
            if held.count > 1:
                self.native_text(str(held.count), mx + 20, my + 14, C.C_TEXT, "right")
        elif hovered is not None:
            label = f"{item_name(hovered.item)} · {hovered.count}"
            w = self.body.size(label)[0] + 12
            tx, ty = min(mx + 8, UW - w - 2), my - 18
            self.panel(tx, ty, w, 16, (14, 10, 9, 235))
            self.text(label, tx + 6, ty + 2, C.C_TEXT, self.body)

    def _arrow(self, cx: int, y: int, up: bool) -> None:
        """Setinha de 5×3 (tem mais receita pra cima/baixo)."""
        for k in range(3):
            row = k if up else 2 - k
            self.surf.fill(pygame.Color(C.C_MUTED), (cx - row, y + k, 2 * row + 1, 1))

    # ---- terminal -------------------------------------------------------------
    def draw_terminal(self, index: int, t: float) -> None:
        dx, dy, dw, dh = 18, UH - 100, UW - 36, 92
        self.panel(dx, dy, dw, dh, (10, 16, 13, 237))
        self.surf.fill(pygame.Color(C.C_TERMINAL), (dx, dy, dw, 2))
        self.text(f"TERMINAL · COLONIA HESPER · LOG 0{index + 1}", dx + 10, dy + 8, C.C_TERMINAL)
        for i, line in enumerate(wrap(self.body, C.LOGS[index], dw - 20)):
            self.text(line, dx + 10, dy + 22 + i * 13, "#d6eadf", self.body)
        if (t * 9) % 10 < 6:
            self.text("[E] CONTINUAR", dx + dw - 10, dy + dh - 13, C.C_TERMINAL, align="right")

    # ---- banner de estágio ----------------------------------------------------
    # Vão livre no topo, entre o painel de O₂ (x 6–118) e o do Ti, em coordenadas da UI.
    BANNER_GAP = (118, TI_PANEL_X)

    def draw_banner(self, stage: int, alpha: float) -> None:
        """Faixa compacta no topo da tela (fora da área de jogo): título em cima, subtítulo embaixo."""
        s = C.STAGES[stage - 1]
        color = C.STAGE_COLOR[stage]
        left, right = self.BANNER_GAP
        max_w = right - left - 16                     # 8 px de folga de cada painel
        w = min(max_w, max(self.font.size(s.title)[0], self.body.size(s.subtitle)[0]) + 16)
        h = 30
        x, y = (left + right) // 2 - w // 2, 6
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        self.panel(0, 0, w, h, (14, 10, 9, 219), target=layer)
        layer.fill(pygame.Color(color), (0, 0, w, 2))
        self.text(s.title, w / 2, 5, color, self.font, "center", target=layer)
        self.text(s.subtitle, w / 2, 15, "#d9cfc4", self.body, "center", target=layer)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (x, y))

    # ---- desmaio --------------------------------------------------------------
    def draw_faint(self, state: GameState) -> None:
        ft = state.faint_time
        a = ft / C.FAINT_RESPAWN_AT if ft < C.FAINT_RESPAWN_AT else (C.FAINT_DURATION - ft) / (C.FAINT_DURATION - C.FAINT_RESPAWN_AT)
        a = max(0.0, min(1.0, a))
        self.fill((0, 0, 0, int(255 * a)), (0, 0, UW, UH))
        if a > 0.6:
            self.text("Tu apagou. Acordando na cápsula...", UW / 2, UH / 2 - 6, "#d9cfc4", self.body, "center")

    # ---- fim do MVP -----------------------------------------------------------
    def draw_end(self, state: GameState, t: float) -> None:
        self.fill((6, 12, 6, 200), (0, 0, UW, UH))
        x, y, w, h = 70, 40, 340, 190
        self.panel(x, y, w, h, (16, 22, 14, 240))
        self.surf.fill(pygame.Color(C.STAGE_COLOR[3]), (x, y, w, 2))
        self.text("FIM DO MVP", UW / 2, y + 14, C.STAGE_COLOR[3], self.font_big, "center")
        body = ("O primeiro verde brotou na cratera. A Colônia Hesper tentou e sumiu; "
                "tu chegou até aqui. O que tem dentro do gelo fica pra próxima.")
        for i, line in enumerate(wrap(self.body, body, w - 40)):
            self.text(line, UW / 2, y + 42 + i * 13, "#d6eadf", self.body, "center")
        minutes, seconds = divmod(int(state.play_time), 60)
        stats = [("TEMPO", f"{minutes}:{seconds:02d}"), ("MAQUINAS", str(len(state.machines))),
                 ("TI", fmt(state.ti)), ("LOGS", f"{len(state.logs_read)}/{len(C.LOGS)}")]
        for i, (label, value) in enumerate(stats):
            sx = x + 30 + i * 74
            self.text(label, sx + 30, y + 100, C.C_MUTED, align="center")
            self.text(value, sx + 30, y + 112, C.C_TI, self.body_big, "center")
        self.text("Obrigado por testar o v0.1", UW / 2, y + 142, "#a6e07a", self.body, "center")
        if (t * 9) % 10 < 6:
            self.text("[ENTER] CONTINUAR EXPLORANDO", UW / 2, y + h - 18, C.C_TEXT, align="center")

    # ---- menu de pausa ---------------------------------------------------------
    PAUSE_OPTIONS = ["Continuar", "Opções", "Controles", "Salvar e sair", "Sair"]
    VOLUME_ROWS = [("master", "GERAL"), ("sfx", "EFEITOS"), ("ambient", "AMBIENTE")]
    CONTROLS = [
        ("WASD / SETAS", "Andar"),
        ("SEGURAR CLIQUE", "Minerar a parede mirada"),
        ("E", "Fabricador (na base) · terminal · baú"),
        ("1 A 8 · RODINHA", "Escolher slot da hotbar"),
        ("CLIQUE", "Colocar a máquina da hotbar"),
        ("R", "Girar a máquina (só visual)"),
        ("TAB", "Inventário"),
        ("CLIQUE DIREITO", "Desmontar (volta pro inventário)"),
        ("ESC", "Cancelar / fechar / pausar"),
        ("+ / -", "Aproximar / afastar (ou Ctrl+rodinha)"),
        ("F11 · ALT+ENTER", "Tela cheia"),
        ("F1 · F2", "Debug: tempo x10 · +10.000 Ti"),
    ]

    def _pause_frame(self, x, y, w, h, title) -> None:
        self.fill((6, 4, 3, 170), (0, 0, UW, UH))
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.surf.fill(pygame.Color(C.C_ACCENT), (x, y, w, 2))
        self.text(title, x + 8, y + 6, C.C_TI)

    def _menu_row(self, rect: pygame.Rect, selected: bool) -> None:
        self.surf.fill(pygame.Color("#2c1e18" if selected else "#211915"), rect)
        pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if selected else "#3a2c25"), rect, 1)

    def draw_pause(self, screen: str, selected: int, mix: dict, zoom_label: str = "1×") -> None:
        """Menu de pausa. screen = 'main', 'volumes' (Opções: volumes, tela cheia, zoom) ou 'controls'.
        `mix` é o dicionário das settings (volumes + "fullscreen")."""
        self.pause_items.clear()
        self.pause_sliders.clear()
        if screen == "main":
            x, y, w = 170, 64, 140
            self._pause_frame(x, y, w, 26 + 22 * len(self.PAUSE_OPTIONS) + 4, "PAUSA")
            for i, label in enumerate(self.PAUSE_OPTIONS):
                row = pygame.Rect(x + 8, y + 26 + i * 22, w - 16, 19)
                self._menu_row(row, i == selected)
                self.text(label, row.x + 8, row.y + 3, C.C_TEXT if i == selected else "#d9cfc4", self.body)
                self.pause_items.append(row)
            self.text("[W/S] ESCOLHE · [ENTER] OK · [ESC] VOLTA", UW / 2, y + 26 + 22 * len(self.PAUSE_OPTIONS) + 10,
                      C.C_MUTED, align="center")
        elif screen == "volumes":
            x, y, w = 120, 60, 240
            n = len(self.VOLUME_ROWS)
            self._pause_frame(x, y, w, 26 + 24 * (n + 3) + 4, "OPÇÕES")
            for i, (key, label) in enumerate(self.VOLUME_ROWS):
                row = pygame.Rect(x + 8, y + 26 + i * 24, w - 16, 21)
                self._menu_row(row, i == selected)
                self.text(label, row.x + 8, row.y + 7, C.C_TEXT)
                bar = pygame.Rect(row.x + 76, row.y + 7, 110, 7)
                self.surf.fill(pygame.Color("#4a3b2a"), bar)
                self.surf.fill(pygame.Color("#120d0b"), bar.inflate(-2, -2))
                fill_w = round((bar.w - 2) * mix[key])
                self.surf.fill(pygame.Color(C.C_TI), (bar.x + 1, bar.y + 1, fill_w, bar.h - 2))
                self.surf.fill(pygame.Color(C.C_TEXT), (bar.x + fill_w - 1, bar.y - 2, 3, bar.h + 4))   # puxador
                self.text(f"{round(mix[key] * 100)}%", row.right - 8, row.y + 7, C.C_TI, align="right")
                self.pause_items.append(row)
                self.pause_sliders.append(bar)
            # tela cheia e zoom: Enter/clique alternam, A/D também
            for i, (label, value) in enumerate((("TELA CHEIA", "SIM" if mix.get("fullscreen") else "NÃO"),
                                                ("ZOOM", zoom_label)), start=n):
                row = pygame.Rect(x + 8, y + 26 + i * 24, w - 16, 21)
                self._menu_row(row, i == selected)
                self.text(label, row.x + 8, row.y + 7, C.C_TEXT)
                self.text(f"< {value} >" if i == selected else value, row.right - 8, row.y + 5, C.C_TI,
                          self.body, align="right")
                self.pause_items.append(row)
            back = pygame.Rect(x + 8, y + 26 + (n + 2) * 24, w - 16, 21)
            self._menu_row(back, selected == n + 2)
            self.text("Voltar", back.x + 8, back.y + 4, C.C_TEXT, self.body)
            self.pause_items.append(back)
            self.text("[W/S] ESCOLHE · [A/D] AJUSTA · [ESC] VOLTA", UW / 2, back.bottom + 10, C.C_MUTED, align="center")
        else:  # controls
            x, y, w = 72, 28, 336
            rows = len(self.CONTROLS)
            h = 26 + 15 * rows + 30
            self._pause_frame(x, y, w, h, "CONTROLES")
            for i, (keys, action) in enumerate(self.CONTROLS):
                yy = y + 26 + i * 15
                self.text(keys, x + 12, yy + 3, C.C_TI)
                self.text(action, x + 112, yy, "#d9cfc4", self.body)
            back = pygame.Rect(x + 8, y + h - 26, 80, 19)
            self._menu_row(back, True)
            self.text("Voltar", back.x + 8, back.y + 3, C.C_TEXT, self.body)
            self.pause_items.append(back)

    # ---- cursor ---------------------------------------------------------------
    def draw_cursor(self, x: float, y: float) -> None:
        pts = [(x, y), (x, y + 9), (x + 2, y + 7), (x + 4, y + 11), (x + 5, y + 10), (x + 4, y + 6), (x + 7, y + 6)]
        pygame.draw.polygon(self.surf, (255, 255, 255), pts)
        pygame.draw.polygon(self.surf, (0, 0, 0), pts, 1)
