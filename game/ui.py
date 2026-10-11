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
from game.assets import load_font
from game.systems import GameState, eta_label, stage_progress

UW, UH = C.UI_W, C.UI_H
TI_PANEL_W = 160                 # painel do Ti (em cima à direita)
TI_PANEL_X = UW - 6 - TI_PANEL_W
SHORT_NAME = {"o2": "O2", "melter": "DERRET.", "heater": "AQUEC.",
              "o2_t2": "O2 II", "melter_t2": "DERRET. II", "heater_t2": "AQUEC. II", "drill": "DRILL"}


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

        # painel do Ti
        self.draw_ti_panel(state)

        # inventário
        self.panel(6, UH - 26, 232, 20)
        for i, res in enumerate(C.RESOURCES):
            x = 12 + i * 76
            self.native.append((icons[res], (x * 2, (UH - 20) * 2)))
            n = str(state.inventory[res])
            w = self.text(n, x + 12, UH - 20, C.C_TEXT)
            self.text(C.RESOURCE_LABEL[res], x + 14 + w, UH - 20, C.C_MUTED)

        # máquinas fabricadas esperando pra serem colocadas
        owned = [(i, k, n) for i, (k, n) in enumerate(state.machines_owned.items()) if n > 0]
        if owned:
            parts = [f"[{i + 1}] {SHORT_NAME[k]} x{n}" for i, k, n in owned]
            label = "  ".join(parts)
            w = self.font.size(label)[0] + 12
            self.panel(6, UH - 48, w, 18)
            self.text(label, 12, UH - 43, C.C_OK)

        if hint:
            w = self.body.size(hint)[0] + 14
            self.panel(UW - 6 - w, UH - 26, w, 20)
            self.text(hint, UW - 13, UH - 22, C.C_TEXT, self.body, "right")

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

    def draw_floaters(self, floaters: FloatingTexts, cam: tuple[int, int]) -> None:
        for text, x, y, color, life in floaters.items:
            sx, sy = (x - cam[0]) / 2, (y - cam[1]) / 2
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
        x, y, w, h = 66, 2, 348, 266
        row_h = 34       # 7 receitas: a caixa da prévia ocupa a linha toda (68 px reais, nv.2 tem 64)
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.text("FABRICADOR", x + 8, y + 6, C.C_TI)
        self.text("[W/S] ESCOLHE · [ENTER] CRAFTA · [E] FECHA", x + w - 8, y + 6, C.C_MUTED, align="right")
        self.fabricator_buttons.clear()
        self.fabricator_rows.clear()
        for i, kind in enumerate(C.MACHINE_ORDER):
            m = C.MACHINES[kind]
            status = state.recipe_status(kind)
            ry = y + 20 + i * (row_h + 1)
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
            clip.blit(preview, (bw2 // 2 - preview.get_width() // 2, bh2 - 2 - preview.get_height()))
            if status == "locked":   # receita bloqueada: prévia escurecida
                shade = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                shade.fill((18, 13, 11, 184))
                clip.blit(shade, (0, 0))
            self.native.append((clip, (box.x * 2, box.y * 2)))

            locked = status == "locked"
            tx = x + 56
            name_w = self.text(m.name, tx, ry + 4, "#8a7b70" if locked else C.C_TEXT, self.body_big)
            self.text(m.desc, tx + 6 + name_w, ry + 4, C.C_MUTED, self.body)
            owned = state.machines_owned[kind]
            if owned:
                self.text(f"x{owned}", tx + name_w + 6 + self.body.size(m.desc)[0] + 8, ry + 5, C.C_OK)
            cx = tx
            for res, n in m.cost.items():
                have = state.inventory[res]
                label = f"{have}/{n} {C.RESOURCE_LABEL[res]}"
                color = "#6e6058" if locked else C.C_OK if have >= n else C.C_ALERT
                cx += self.text(label, cx, ry + 21, color) + 8

            bx, by, bw, bh = x + w - 86, ry + 7, 72, 20
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
    PAUSE_OPTIONS = ["Continuar", "Volumes", "Controles", "Sair"]
    VOLUME_ROWS = [("master", "GERAL"), ("sfx", "EFEITOS"), ("ambient", "AMBIENTE")]
    CONTROLS = [
        ("WASD / SETAS", "Andar"),
        ("SEGURAR CLIQUE", "Minerar a parede mirada"),
        ("E", "Fabricador (na base) · ler terminal"),
        ("CLIQUE", "Colocar máquina fabricada"),
        ("R", "Girar a máquina (só visual)"),
        ("1 A 7", "Escolher máquina já fabricada"),
        ("CLIQUE DIREITO", "Desmontar máquina (volta pro 1–7)"),
        ("ESC", "Cancelar / fechar / pausar"),
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

    def draw_pause(self, screen: str, selected: int, mix: dict) -> None:
        """Menu de pausa. screen = 'main', 'volumes' ou 'controls'."""
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
            self._pause_frame(x, y, w, 26 + 24 * (n + 1) + 4, "VOLUMES")
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
            back = pygame.Rect(x + 8, y + 26 + n * 24, w - 16, 21)
            self._menu_row(back, selected == n)
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
