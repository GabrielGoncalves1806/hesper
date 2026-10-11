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
from game.systems import GameState

UW, UH = C.UI_W, C.UI_H
SHORT_NAME = {"o2": "O2", "melter": "DERRET.", "heater": "AQUEC.",
              "o2_t2": "O2 II", "melter_t2": "DERRET. II", "heater_t2": "AQUEC. II"}


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
        self.body = load_font("PixelifySans.ttf", 11, 13)             # textos (11 px: em 10 e 12 o "G" vira "Q")
        self.body_big = load_font("PixelifySans.ttf", 11, 16)   # títulos: mesmo tamanho (o "G" só fica certo em 11), destaque pela cor
        self._text_cache: dict[tuple, pygame.Surface] = {}
        self._tmp: dict[tuple, pygame.Surface] = {}
        self.fabricator_buttons: list[tuple[pygame.Rect, str]] = []   # retângulos clicáveis (coord. da UI)
        self.fabricator_rows: list[tuple[pygame.Rect, str]] = []

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
        px = UW - 146
        self.panel(px, 6, 140, 50)
        self.text("TI", px + 6, 10, C.C_TI)
        rate = state.ti_rate * state.time_scale
        if rate:
            self.text(f"+{fmt_rate(rate)}/S", px + 22, 10, C.C_OK)
        self.text(fmt(state.ti), px + 134, 10, C.C_TI, align="right")
        self.fill((255, 255, 255, 30), (px + 6, 20, 128, 1))
        for i, key in enumerate(("o2", "heat", "water")):
            yy = 24 + i * 10
            self.surf.fill(pygame.Color(C.INDEX_COLOR[key]), (px + 6, yy + 2, 4, 4))
            self.text(C.INDEX_LABEL[key], px + 14, yy, "#d9cfc4")
            self.text(f"{fmt(state.indices[key])} {C.INDEX_UNIT[key]}", px + 134, yy, C.C_TEXT, align="right")

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
        x, y, w, h = 66, 4, 348, 262
        row_h = 39       # linha alta o bastante pra prévia das máquinas nv.2 (64 px) caber inteira
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
            ry = y + 22 + i * (row_h + 1)
            sel = i == selected
            row = pygame.Rect(x + 8, ry, w - 16, row_h)
            self.fabricator_rows.append((row, kind))
            self.surf.fill(pygame.Color("#2c1e18" if sel else "#211915"), row)
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if sel else "#3a2c25"), row, 1)
            # prévia da máquina em resolução cheia, sem redimensionar: caixa de 72×74 px reais,
            # base da máquina 4 px acima do fundo (nv.2 tem 64 px de altura: sobram 6 px em cima)
            box = pygame.Rect(x + 12, ry + 1, 36, 37)
            self.surf.fill(pygame.Color("#120d0b"), box)
            preview = machine_preview(kind)
            bw2, bh2 = box.w * 2, box.h * 2
            clip = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
            clip.blit(preview, (bw2 // 2 - preview.get_width() // 2, bh2 - 4 - preview.get_height()))
            if status == "locked":   # receita bloqueada: prévia escurecida
                shade = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                shade.fill((18, 13, 11, 184))
                clip.blit(shade, (0, 0))
            self.native.append((clip, (box.x * 2, box.y * 2)))

            locked = status == "locked"
            tx = x + 56
            name_w = self.text(m.name, tx, ry + 7, "#8a7b70" if locked else C.C_TEXT, self.body_big)
            self.text(m.desc, tx + 6 + name_w, ry + 7, C.C_MUTED, self.body)
            owned = state.machines_owned[kind]
            if owned:
                self.text(f"x{owned}", tx + name_w + 6 + self.body.size(m.desc)[0] + 8, ry + 8, C.C_OK)
            cx = tx
            for res, n in m.cost.items():
                have = state.inventory[res]
                label = f"{have}/{n} {C.RESOURCE_LABEL[res]}"
                color = "#6e6058" if locked else C.C_OK if have >= n else C.C_ALERT
                cx += self.text(label, cx, ry + 25, color) + 8

            bx, by, bw, bh = x + w - 86, ry + 10, 72, 20
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
    # Vão livre no topo, entre o painel de O₂ (x 6–118) e o do Ti (x 334–474), em coordenadas da UI.
    BANNER_GAP = (118, 334)

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

    # ---- cursor ---------------------------------------------------------------
    def draw_cursor(self, x: float, y: float) -> None:
        pts = [(x, y), (x, y + 9), (x + 2, y + 7), (x + 4, y + 11), (x + 5, y + 10), (x + 4, y + 6), (x + 7, y + 6)]
        pygame.draw.polygon(self.surf, (255, 255, 255), pts)
        pygame.draw.polygon(self.surf, (0, 0, 0), pts, 1)
