"""Interface: HUD, fabricador, terminal, banner de estágio, O₂ crítico, desmaio e tela de fim.

Igual ao mockup, a UI é desenhada numa superfície pequena em "px da UI" e depois esticada sem
suavizar, direto na janela. Isso deixa as fontes pixeladas nítidas e permite copiar as
coordenadas do mockup quase direto.
O tamanho dessa superfície (self.w × self.h) depende do "Tamanho da interface" (Opções):
480×270 no Grande (o tamanho de sempre) e maior no Média/Pequena, que encolhem tudo na tela.
Por isso nada aqui usa posição absoluta da tela: os painéis se ancoram nos cantos/centro pelo
self.w/self.h (contas em game/viewport.py: ui_layout).
Algumas coisas precisam de mais resolução (ícones 16×16 desenhados a 32×32, prévia das máquinas):
essas vão pra lista `self.native`, em coordenadas de 2 px por px da UI, desenhada por cima depois
da escala.
"""

import math

import pygame

from game import config as C
from game import energy
from game.assets import Sprites, load_font
from game.fabricator import field_kinds, tab_kinds
from game.floaters import LANE_PX, RISE, FloatingTexts, dodge_labels, hud_fade
from game.inventory import Inventory, Stack
from game.systems import GameState, eta_label, stage_progress
from game.wrecks import Crate

UW, UH = C.UI_W, C.UI_H           # tamanho da UI no Grande (e o mínimo em qualquer tamanho)
TI_PANEL_W = 160                 # painel do Ti (em cima à direita, encostado na borda: ti_panel_x)
# inventário e hotbar (coordenadas da UI, metade da tela): slot de 20×20 (= ui_slot.png) com 2 de vão
SLOT, SLOT_GAP = 20, 2
SLOT_STEP = SLOT + SLOT_GAP
GRID_W = 8 * SLOT_STEP - SLOT_GAP                # 8 colunas = 174
# seção "DRONES" dos painéis de baú e drill (draw_logistics): Envia, Recebe e Lote
LOGI_ROW = 20                                    # passo entre as linhas ENVIA / RECEBE / LOTE
LOGI_H = 13 + 3 * LOGI_ROW - 2                   # altura da seção: cabeçalho + 3 linhas de botões
LOGI_BTN = 18                                    # toggle com ícone: 18×18 (ícone 16 + 1 de borda)
LOGI_LABEL_W = 42                                # coluna dos rótulos "ENVIA" / "RECEBE"
BATCH_BTN_W = 17                                 # botões do lote: 1 / 5 / 10 / 20
# painel do lado (baú/drill): título, grade de 3 linhas, botões e a seção DRONES
SIDE_GRID_Y = 22
SIDE_BUTTONS_Y = SIDE_GRID_Y + 3 * (20 + 2) - 2 + 5
SIDE_LOGI_Y = SIDE_BUTTONS_Y + 15 + 4
# abas do Tab (Inventário / Fabricar / LOGs), no estilo das abas do fabricador
INV_TABS_H = 17                                  # faixa das abas embaixo do título (aba de 15 + linha + respiro)
TAB_INVENTORY, TAB_CRAFT, TAB_LOGS = range(3)    # índices das abas do Tab
FIELD_ROW_H = 36                                 # linha de receita da aba Fabricar (o fabricador usa ~41)
LOG_ROW_H, LOG_ROW_STEP = 15, 16                 # linha da aba LOGs e o passo entre elas
# altura da janela do Tab na aba Inventário (título, abas, mochila, HOTBAR, TRAJE): a aba LOGs usa pro mesmo topo
TAB_INV_H = 20 + INV_TABS_H + 6 + SLOT + 14 + SLOT + 8 + 14 + SLOT + 2


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

# Subscrito desenhado em pixels: nas duas fontes o "O" maiúsculo é igual ao zero ("O2" lia "02") e
# nenhuma das duas tem o "₂". O texto do jogo escreve "O₂" e a fonte desenha o 2 pequeno e rebaixado.
# Dois tamanhos: 3×4 pra letra de 5 px (Silkscreen 8) e 3×5 pra de 7 px (Pixelify 11).
SUBSCRIPTS = {
    "₂": {4: ["## ", "  #", " # ", "###"],
          5: ["## ", "  #", " # ", "#  ", "###"]},
}


class PixelFont:
    """Uma fonte do jogo com os pedaços que ela desenha mal trocados por pixels desenhados à mão.

    - `digits=True` (Pixelify): os números saem de DIGITS ("5" virava "S", "2" virava "Z").
    - sempre: o subscrito "₂" (O₂) sai de SUBSCRIPTS, menor e rebaixado, em vez do glifo que a fonte não tem.
    Tem os mesmos size() e render() de uma pygame.font.Font, então serve em qualquer lugar onde a
    fonte era usada (medidas, quebra de linha, HUD, menus).
    """

    def __init__(self, font: pygame.font.Font, digits: bool = True):
        self.font = font
        self.digits = digits
        # topo dos dígitos alinhado com o das letras maiúsculas (7 px acima da linha de base)
        self.digit_top = max(0, font.get_ascent() - 7)
        # caixa das maiúsculas (pelo "O"): o subscrito se apoia nela
        probe = font.render("O", False, (255, 255, 255), (0, 0, 0))
        rows = [y for y in range(probe.get_height()) if any(probe.get_at((x, y)).r for x in range(probe.get_width()))]
        cap_top, cap_bottom = (rows[0], rows[-1]) if rows else (0, font.get_height() - 1)
        cap = cap_bottom - cap_top + 1
        self.sub_scale = max(1, round(cap / 6))
        self.sub_rows = 4 if cap / self.sub_scale <= 5 else 5
        # o subscrito começa no meio da letra e passa 1 px (na escala) da linha de base
        self.sub_top = cap_bottom + self.sub_scale - self.sub_rows * self.sub_scale + 1
        self.sub_advance = 3 * self.sub_scale + 1

    def _kind(self, ch: str) -> str:
        if ch in SUBSCRIPTS:
            return "sub"
        if self.digits and ch in DIGITS:          # "₂".isdigit() é True: por isso a lista, não isdigit()
            return "digit"
        return "text"

    def _runs(self, text: str) -> list[str]:
        """'Ti 500 x' -> ['Ti ', '500', ' x']: separa dígitos e subscritos do resto."""
        runs: list[str] = []
        for ch in text:
            if runs and self._kind(runs[-1][-1]) == self._kind(ch):
                runs[-1] += ch
            else:
                runs.append(ch)
        return runs

    def _run_width(self, run: str) -> int:
        kind = self._kind(run[0])
        if kind == "digit":
            return DIGIT_ADVANCE * len(run)
        if kind == "sub":
            return self.sub_advance * len(run)
        return self.font.size(run)[0]

    def size(self, text: str) -> tuple[int, int]:
        return sum(self._run_width(r) for r in self._runs(text)), self.font.get_height()

    def get_height(self) -> int:
        return self.font.get_height()

    def get_ascent(self) -> int:
        return self.font.get_ascent()

    def render(self, text: str, antialias: bool, color) -> pygame.Surface:
        if all(self._kind(ch) == "text" for ch in text):
            return self.font.render(text, antialias, color)
        surf = pygame.Surface(self.size(text), pygame.SRCALPHA)
        x = 0
        for run in self._runs(text):
            kind = self._kind(run[0])
            if kind == "text":
                surf.blit(self.font.render(run, antialias, color), (x, 0))
                x += self.font.size(run)[0]     # avança pela medida (a imagem perde o espaço do fim)
                continue
            for ch in run:
                if kind == "digit":
                    glyph, top, s = DIGITS[ch], self.digit_top, 1
                    ox = x + 1
                else:
                    glyph, top, s = SUBSCRIPTS[ch][self.sub_rows], self.sub_top, self.sub_scale
                    ox = x
                for dy, row in enumerate(glyph):
                    for dx, cell in enumerate(row):
                        if cell == "#":
                            surf.fill(color, (ox + dx * s, top + dy * s, s, s))
                x += DIGIT_ADVANCE if kind == "digit" else self.sub_advance
        return surf


def fmt(n: float) -> str:
    """12400 -> '12.400' (separador de milhar brasileiro)."""
    return f"{round(n):,}".replace(",", ".")


def fmt_rate(n: float) -> str:
    return (f"{n:.1f}".replace(".", ",") if n % 1 else str(int(n)))


def item_name(item: str) -> str:
    """Nome de um item do inventário pra mostrar ao jogador ('Ferro', 'Gerador de O₂', 'Baú')."""
    if item in C.RESOURCE_NAME:
        return C.RESOURCE_NAME[item].capitalize()
    if item in C.BLUEPRINT_ITEMS:
        return f"Projeto: {C.BLUEPRINTS[C.BLUEPRINT_ITEMS[item]]}"
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


class UI:
    def __init__(self):
        # tamanho lógico (px da UI) e onde ela aparece na janela: set_layout() muda isso a cada frame
        self.w, self.h = UW, UH
        self.origin = (0, 0)              # canto da área de jogo (letterbox) na janela
        self.k = 2.0                      # px da janela por px da UI
        self.canvas_k = 0.5               # px da UI por px do canvas (texto preso no mundo)
        self.surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.native: list[tuple[pygame.Surface, tuple[int, int]]] = []
        self.chest_label_rects: list[pygame.Rect] = []
        # painéis do HUD desenhados nesta camada (hud_panel): os floaters somem antes de entrar embaixo deles
        self.hud_rects: list[pygame.Rect] = []   # rótulos de baú deste frame (os floaters desviam)
        self._dodge: dict[int, float] = {}                # desvio de cada floater (uid) do rótulo atual
        self._dodge_key = None
        # Silkscreen: letras da fonte, só o subscrito do "O₂" desenhado (os números dela são legíveis)
        self.font = PixelFont(load_font("Silkscreen-Regular.ttf", 8, 12), digits=False)        # rótulos
        self.font_big = PixelFont(load_font("Silkscreen-Regular.ttf", 16, 22), digits=False)   # títulos
        # textos: Pixelify 11 px (em 10 e 12 o "G" vira "Q"), com os dígitos desenhados em pixels
        self.body = PixelFont(load_font("PixelifySans.ttf", 11, 13))
        self.body_big = PixelFont(load_font("PixelifySans.ttf", 11, 16))   # títulos: mesmo tamanho (o "G" só fica certo em 11), destaque pela cor
        self._text_cache: dict[tuple, pygame.Surface] = {}
        self._tmp: dict[tuple, pygame.Surface] = {}
        self.fabricator_buttons: list[tuple[pygame.Rect, str]] = []   # retângulos clicáveis (coord. da UI)
        self.fabricator_rows: list[tuple[pygame.Rect, str]] = []
        self.fabricator_tabs: list[tuple[pygame.Rect, int]] = []      # abas: (retângulo, índice da aba)
        self.pause_items: list[pygame.Rect] = []      # linhas clicáveis do menu de pausa (coord. da UI)
        self.pause_sliders: list[pygame.Rect] = []    # barras dos sliders de volume
        self.pause_page_buttons: list[tuple[pygame.Rect, int]] = []   # Controles: "<" (-1) e ">" (+1)
        self.controls_pages = 1                       # quantas páginas a tela de Controles teve no último desenho
        # slots clicáveis da tela de inventário/baú: (retângulo na UI, inventário, índice do slot)
        self.slot_rects: list[tuple[pygame.Rect, Inventory, int]] = []
        # títulos de janela, abas e rótulos de seção dos painéis com slots: o tooltip nunca cobre (tooltip_rect)
        self.header_rects: list[pygame.Rect] = []
        # painel da estação: slots de drone (retângulo, nº do slot) e do buffer (retângulo, minério)
        self.bay_rects: list[tuple[pygame.Rect, int]] = []
        self.buffer_rects: list[tuple[pygame.Rect, str]] = []
        self.panel_buttons: list[tuple[pygame.Rect, str]] = []   # "take_all", "store_all", "take_buffer"
        self.name_rect: pygame.Rect | None = None                 # nome do baú (clique = editar)
        self.notice_y = self.hotbar_y - 58                            # altura do aviso nos painéis (draw_inventory)
        # seção DRONES do baú/drill: (retângulo, ("send"|"recv", item) ou ("batch", n))
        self.logistics_buttons: list[tuple[pygame.Rect, tuple[str, object]]] = []
        self.slot_img = Sprites().get("ui_slot")      # moldura opcional (bíblia §8); sem ela, desenhamos
        self.equip_rects: list[tuple[pygame.Rect, str]] = []      # slots de equipamento (Tab): (retângulo, tipo)
        self.inv_tab_rects: list[tuple[pygame.Rect, int]] = []    # abas do Tab: (retângulo, TAB_INVENTORY/CRAFT/LOGS)
        self.log_rows: list[tuple[pygame.Rect, int]] = []         # aba LOGs: linhas clicáveis (retângulo, índice em LOGS)
        self.log_visible = len(C.LOGS)                             # quantas linhas da aba LOGs couberam no último desenho
        self.energy_bottom = 110                                   # onde acaba o medidor de energia (minimapa embaixo)
        self.right_bottom = 110                                    # onde acaba a coluna da direita ("Jogo salvo" embaixo)

    # ---- tamanho e âncoras -------------------------------------------------------
    def set_layout(self, rect: tuple[int, int, int, int], k: float, size: tuple[int, int]) -> None:
        """Onde a UI aparece na janela (`rect` = área de jogo), a escala `k` e o tamanho lógico.
        Vem de game/viewport.ui_layout. Muda o self.w/self.h: tudo se ancora por eles."""
        self.origin, self.k = (rect[0], rect[1]), k
        self.canvas_k = rect[2] / C.SCREEN_W / k
        if size != (self.w, self.h):
            self.w, self.h = size
            self.surf = pygame.Surface(size, pygame.SRCALPHA)
            self.notice_y = self.hotbar_y - 58

    @property
    def ti_panel_x(self) -> int:
        return self.w - 6 - TI_PANEL_W

    @property
    def hotbar_x(self) -> int:
        return (self.w - GRID_W) // 2

    @property
    def hotbar_y(self) -> int:
        return self.h - 6 - SLOT

    @property
    def center_offset(self) -> tuple[int, int]:
        """Quanto somar nas coordenadas de um painel feito pra 480×270 pra ele ficar no centro."""
        return (self.w - UW) // 2, (self.h - UH) // 2

    def world_to_ui(self, pos: tuple[float, float], cam: tuple[int, int], zoom: float) -> tuple[float, float]:
        """Ponto do mundo -> px da UI (floaters, rótulo do baú, seta da base)."""
        k = zoom * self.canvas_k
        return (pos[0] - cam[0]) * k, (pos[1] - cam[1]) * k

    # ---- primitivas -----------------------------------------------------------
    def begin(self) -> None:
        self.surf.fill((0, 0, 0, 0))
        self.native.clear()
        self.hud_rects.clear()

    # Fatias da UI esticadas uma a uma em finish(): o HUD é quase todo transparente, então esticar
    # só o que tem desenho (os cantos, a hotbar) poupa muito trabalho numa janela 1920×1080.
    TILES = (4, 4)

    def finish(self, target: pygame.Surface) -> None:
        """Estica a camada (sem suavizar) e desenha na janela `target`, dentro da área de jogo,
        com os ícones da lista `native` por cima. Desenha direto na janela (que é opaca): nenhuma
        camada alfa intermediária, então o painel semitransparente mistura igual a sempre."""
        ox, oy = self.origin
        k = self.k
        clip = target.get_clip()
        target.set_clip(pygame.Rect(ox, oy, round(self.w * k), round(self.h * k)).clip(clip))
        if k == int(k):
            k_int = int(k)
            cols, rows = self.TILES
            tw, th = -(-self.w // cols), -(-self.h // rows)
            for ty in range(0, self.h, th):
                for tx in range(0, self.w, tw):
                    tile = self.surf.subsurface((tx, ty, min(tw, self.w - tx), min(th, self.h - ty)))
                    used = tile.get_bounding_rect()
                    if used.w and used.h:
                        part = tile.subsurface(used)
                        target.blit(pygame.transform.scale_by(part, k_int),
                                    (ox + (tx + used.x) * k_int, oy + (ty + used.y) * k_int))
        else:                                  # escala quebrada (janela de tamanho livre): estica tudo junto
            target.blit(pygame.transform.scale(self.surf, (round(self.w * k), round(self.h * k))), (ox, oy))
        s = k / 2                              # a lista native é em 2 px por px da UI
        for surf, (nx, ny) in self.native:
            if s != 1:
                surf = pygame.transform.scale(surf, (max(1, round(surf.get_width() * s)),
                                                     max(1, round(surf.get_height() * s))))
            target.blit(surf, (ox + round(nx * s), oy + round(ny * s)))
        target.set_clip(clip)

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

    def text(self, s: str, x: float, y: float, color: str, font=None, align: str = "left", target=None,
             alpha: float = 1.0) -> int:
        """Texto com sombrinha preta (igual ao mockup). Devolve a largura. `alpha` < 1: esmaecido."""
        font = font or self.font
        target = target or self.surf
        img = self._render(font, s, color)
        shadow = self._render(font, s, "#000000")
        w = img.get_width()
        x = x - w if align == "right" else x - w // 2 if align == "center" else x
        x, y = int(x), int(y)
        if alpha < 1.0:                  # as imagens do cache são compartilhadas: esmaece uma cópia
            img = img.copy()
            img.set_alpha(round(255 * alpha))
            shadow = shadow.copy()
        shadow.set_alpha(round(165 * alpha))
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

    def hud_panel(self, x, y, w, h) -> None:
        """Painel do HUD (O₂, Ti, energia, objetivos, minimapa, hotbar...): guarda o retângulo em hud_rects."""
        self.panel(x, y, w, h)
        self.hud_rects.append(pygame.Rect(x, y, w, h))

    # ---- HUD ------------------------------------------------------------------
    def draw_hud(self, state: GameState, t: float, hint: str | None, icons: dict[str, pygame.Surface]) -> None:
        crit = state.o2 < C.O2_LOW
        blink = crit and (t * 9) % 6 < 3
        o2 = min(1.0, state.o2 / state.o2_max)          # proporcional ao máximo (com o tanque, 220 s)
        # barra de O₂
        self.hud_panel(6, 6, 112, 26)
        self.text("O₂", 11, 10, C.C_ALERT if crit else C.C_O2)
        self.fill((20, 35, 42), (30, 11, 82, 7))
        bar = (C.C_ALERT if blink else "#c2281c") if crit else C.C_O2
        self.surf.fill(pygame.Color(bar), (30, 11, round(82 * o2), 7))
        self.fill((255, 255, 255, 64), (30, 11, round(82 * o2), 1))
        for i in range(1, 10):
            self.fill((0, 0, 0, 90), (30 + int(i * 8.2), 11, 1, 7))
        if state.equipment.has("o2_tank"):           # tanque equipado: a barra vale 220 s (mostra os segundos)
            self.text(f"{round(state.o2)} S", 30, 21, "#ff8a7a" if crit else "#a8c9d2")
            self.text("TANQUE", 112, 21, C.C_O2, align="right")
        else:
            self.text(f"{round(o2 * 100)}%", 30, 21, "#ff8a7a" if crit else "#a8c9d2")

        # painel do Ti e, logo embaixo, o medidor de energia
        self.draw_ti_panel(state)
        self.draw_energy(state)

        # resumo do inventário (total de cada recurso, somando as pilhas); os slots ficam na hotbar e no Tab
        counts = [str(state.inventory.count(res)) for res in C.RESOURCES]
        w = 6 + sum(14 + self.font.size(n)[0] + 6 for n in counts)
        self.hud_panel(6, self.h - 26, w, 20)
        x = 12
        for res, n in zip(C.RESOURCES, counts):
            self.native.append((icons[res], (x * 2, (self.h - 20) * 2)))
            x += 14 + self.text(n, x + 12, self.h - 20, C.C_TEXT) + 6

        if hint:
            w = self.body.size(hint)[0] + 14
            # dica embaixo à direita; se for comprida e encostar na hotbar, sobe uma linha
            y = self.h - 26 if self.w - 6 - w >= self.hotbar_x + GRID_W + 6 else self.hotbar_y - 34
            self.hud_panel(self.w - 6 - w, y, w, 20)
            self.text(hint, self.w - 13, y + 4, C.C_TEXT, self.body, "right")

        debug = ([f"DEBUG · TEMPO x{state.time_scale}"] if state.time_scale != 1 else []) \
            + ([f"DEBUG · RAPIDO x{C.DEBUG_SPEED:g} · BROCA x{C.DEBUG_MINE:g}"] if state.fast else [])
        for i, line in enumerate(debug):          # F1 e F3: uma linha cada, no topo (não alcança o painel do Ti)
            self.text(line, self.w // 2, 8 + 10 * i, C.C_TI, align="center")

    def draw_ti_panel(self, state: GameState) -> None:
        """Ti total, os 3 índices e, embaixo, quanto falta pro próximo estágio."""
        px, w = self.ti_panel_x, TI_PANEL_W
        right = px + w - 6            # borda direita do texto
        inner = w - 12                # largura útil
        nxt, fraction, remaining = stage_progress(state.ti)
        eta = eta_label(remaining, state.smoothed_rate)
        line2 = f"faltam {fmt(remaining)} · {eta}"
        wrap_eta = self.body.size(line2)[0] > inner      # não coube: o tempo desce pra uma 3ª linha
        h = 64 if nxt is None else 90 if wrap_eta else 78
        self.hud_panel(px, 6, w, h)
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
        px, w = self.ti_panel_x, TI_PANEL_W
        right = px + w - 6
        y = getattr(self, "ti_panel_bottom", 84) + 4
        warning = []
        if power.deficit:
            warning = [f"Energia insuficiente · máquinas a {int(power.factor * 100)}%"]
            if self.body.size(warning[0])[0] > w - 12:    # não coube numa linha: quebra no "·"
                warning = warning[0].split(" · ")
        self.hud_panel(px, y, w, 15 + 12 * len(warning))
        self.energy_bottom = y + 15 + 12 * len(warning)
        self.right_bottom = self.energy_bottom        # fim da coluna da direita (Ti, energia, minimapa)
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
        self.hud_panel(x, y, w, h)
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

    def draw_floaters(self, floaters: FloatingTexts, cam: tuple[int, int], zoom: float = 1.0,
                      labels: list[pygame.Rect] = ()) -> None:
        """Textos presos num ponto do mundo: a posição acompanha o zoom, o tamanho da letra não
        (a letra segue o tamanho da interface, igual ao resto do texto). `labels`: rótulos de baú já
        desenhados neste frame; quem ia passar por trás deles nasce/fica acima (dodge_labels). O desvio
        de cada floater é decidido uma vez e guardado enquanto o mesmo rótulo estiver na tela.
        Vem depois do HUD na mesma camada: quem chega perto de um painel do HUD (hud_rects) esmaece e
        some antes de entrar embaixo dele (hud_fade), em vez de passar por trás."""
        k = zoom * self.canvas_k
        h = self.font.get_height()
        pos, boxes = {}, {}
        for f in floaters.items:
            # a faixa (lane) é em px da UI: a distância entre as linhas não muda com o zoom
            sx, sy = self.world_to_ui((f.x, f.y), cam, zoom)
            sy -= f.lane * LANE_PX
            half = self.font.size(f.text)[0] / 2
            pos[f.uid] = (f, sx, sy)
            boxes[f.uid] = (sx - half, sx + half, sy, RISE * max(0.0, f.life) * k, h)
        key = (tuple((r.w, r.h) for r in labels), round(zoom, 3))
        if not labels or key != self._dodge_key:
            self._dodge, self._dodge_key = {}, key
        if labels:
            self._dodge = dodge_labels(boxes, [(r.left, r.top, r.right, r.bottom) for r in labels], self._dodge)
        for fid, (f, sx, sy) in pos.items():
            sy -= self._dodge.get(fid, 0.0)
            if -40 < sx < self.w + 40 and -20 < sy < self.h + 20:
                half = self.font.size(f.text)[0] / 2
                alpha = hud_fade((sx - half, sy, sx + half, sy + h), [tuple(r.topleft + r.bottomright)
                                                                      for r in self.hud_rects])
                if alpha > 0:
                    self.text(f.text, sx, sy, f.color, align="center", alpha=alpha)

    # ---- O₂ crítico -----------------------------------------------------------
    def draw_o2_critical(self, state: GameState, t: float, cam: tuple[int, int]) -> None:
        tick = t * 9
        if tick % 8 < 5:
            self.text("OXIGENIO CRITICO", self.w / 2, 62, "#ff5a4a", self.font_big, "center")
        sx, sy, label = state.safe_point()      # a base, ou a rampa de subida na caverna (não tem O₂ lá embaixo)
        meters = round(math.hypot(state.player.x - sx, state.player.y - sy) / C.TILE)
        call = "Volte para a base" if label == "BASE" else "Suba pela rampa"
        self.text(f"{call} · {meters} m", self.w / 2, 84, "#ffd0c8", self.body, "center")
        # seta apontando pra base, numa elipse em volta do centro da tela
        # só a direção importa (o zoom não muda o ângulo); a elipse acompanha o tamanho da área de jogo
        px, py = state.player.x - cam[0], state.player.y - 16 - cam[1]
        bx, by = sx - cam[0], sy - cam[1]
        ang = math.atan2(by - py, bx - px)
        wobble = math.sin(t * 7) * 3
        rx, ry = 200 * self.w / UW, 105 * self.h / UH
        if math.sin(ang) > 0:                    # pra baixo: a seta não desce na hotbar (moldura em hotbar_y - 11)
            ry = min(ry, self.hotbar_y - 11 - 12 - self.h / 2)
        cx, cy = self.w / 2 + math.cos(ang) * (rx + wobble), self.h / 2 + math.sin(ang) * (ry + wobble)
        tip = (cx + math.cos(ang) * 8, cy + math.sin(ang) * 8)
        left = (cx + math.cos(ang + 2.4) * 9, cy + math.sin(ang + 2.4) * 9)
        right = (cx + math.cos(ang - 2.4) * 9, cy + math.sin(ang - 2.4) * 9)
        pygame.draw.polygon(self.surf, pygame.Color(C.C_ALERT), [tip, left, right])
        lx, ly = cx - math.cos(ang) * 16, cy - math.sin(ang) * 14
        self.text(label, lx, ly - 4, "#ff9a8a", align="center")

    # ---- fabricador -----------------------------------------------------------
    def draw_fabricator(self, state: GameState, menu, machine_preview, t: float) -> None:
        """Menu de receitas com abas (`menu`: game/fabricator.FabMenu). `machine_preview(kind)` devolve
        a imagem da máquina (resolução cheia). Hit-test: fabricator_tabs, fabricator_rows, fabricator_buttons."""
        self.fill((8, 5, 4, 158), (0, 0, self.w, self.h))
        # 400 px; se as abas não cabem (6 abas com a "Traje" do Marco 3), alarga até caber (no Grande: 434)
        tabs_w = sum(self.body.size(label)[0] + 10 for _, label in C.FAB_TABS) + 3 * (len(C.FAB_TABS) - 1)
        w, h = min(self.w - 8, max(400, tabs_w + 16)), 268
        x, y = (self.w - w) // 2, (self.h - h) // 2       # no centro
        list_y = y + 38                                 # título (18) + abas (16) + respiro
        footer_y = y + h - 14                           # linha de ajuda embaixo
        row_h = (footer_y - 2 - list_y) // menu.visible - 1
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.text("FABRICADOR", x + 8, y + 6, C.C_TI)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, footer_y, w - 2, 13))
        self.text(f"[A/D] ABA · [W/S] ESCOLHE · [ENTER] CRAFTA · [SHIFT+ENTER] X{C.CRAFT_BATCH} · [E] FECHA",
                  x + w / 2, footer_y + 3, C.C_MUTED, align="center")
        self.fabricator_buttons.clear()
        self.fabricator_rows.clear()
        self.fabricator_tabs.clear()
        # abas: largura pelo texto; aba sem nada liberado fica apagada (mas abre e mostra as bloqueadas)
        tx = x + 8
        for i, (tab_id, label) in enumerate(C.FAB_TABS):
            tw = self.body.size(label)[0] + 10
            rect = pygame.Rect(tx, y + 21, tw, 15)
            active = i == menu.tab
            unlocked = any(state.recipe_status(k) not in ("locked", "blueprint") for k in tab_kinds(tab_id))
            self.surf.fill(pygame.Color("#2c1e18" if active else "#160f0d"), rect)
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if active else "#3a2c25"), rect, 1)
            if active:                                  # a aba ativa "abre" pra lista
                self.surf.fill(pygame.Color("#2c1e18"), (rect.x + 1, rect.bottom - 1, rect.w - 2, 2))
            color = C.C_TEXT if active else C.C_MUTED if unlocked else "#5a4a40"
            self.text(label, rect.x + 5, rect.y + 1, color, self.body)
            self.fabricator_tabs.append((rect, i))
            tx += tw + 3
        pygame.draw.line(self.surf, pygame.Color("#3a2c25"), (x + 8, y + 35), (x + w - 9, y + 35))
        self._recipe_list(state, menu, x, w, list_y, row_h, machine_preview)

    def _recipe_list(self, state: GameState, menu, x: int, w: int, list_y: int, row_h: int, machine_preview,
                     field: bool = False) -> None:
        """As linhas de receita (prévia, nome, custo com falta em vermelho e o botão CRAFTAR) da aba atual do
        `menu`, numa janela de largura `w` em `x`. Usada pelo fabricador e pela aba Fabricar do Tab (`field`:
        o custo conta só o inventário). Preenche fabricator_rows e fabricator_buttons."""
        kinds = menu.kinds
        selected, first = menu.selected[menu.tab], menu.first[menu.tab]
        if len(kinds) > menu.visible:                   # barra de rolagem na margem direita
            track = pygame.Rect(x + w - 6, list_y, 3, menu.visible * (row_h + 1) - 1)
            self.surf.fill(pygame.Color("#120d0b"), track)
            thumb_h = max(8, round(track.h * menu.visible / len(kinds)))
            thumb_y = track.y + round((track.h - thumb_h) * first / max(1, menu.max_first))
            self.surf.fill(pygame.Color(C.C_ACCENT), (track.x, thumb_y, 3, thumb_h))
        for i, kind in menu.window():
            m = C.MACHINES[kind]
            status = state.recipe_status(kind, field)
            ry = list_y + (i - first) * (row_h + 1)
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
            if status in ("locked", "blueprint"):   # receita bloqueada: prévia escurecida (sem projeto: quase some)
                shade = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                shade.fill((18, 13, 11, 184 if status == "locked" else 238))
                clip.blit(shade, (0, 0))
            self.native.append((clip, (box.x * 2, box.y * 2)))

            hidden = status == "blueprint"          # receita de projeto ainda não encontrado (Marco 3)
            locked = status == "locked" or hidden
            tx = x + 56
            text_y = ry + (row_h - 32) // 2      # centraliza as 2 linhas de texto na linha
            name, desc = ("???", "projeto não encontrado") if hidden else (m.name, m.desc)
            name_w = self.text(name, tx, text_y + 4, "#8a7b70" if locked else C.C_TEXT, self.body_big)
            self.text(desc, tx + 6 + name_w, text_y + 4, C.C_MUTED, self.body)
            owned = state.inventory.count(kind)       # já fabricadas, no inventário
            top_end = tx + name_w + 6 + self.body.size(desc)[0]     # onde acaba o texto da 1ª linha
            if owned:
                top_end += 8 + self.text(f"x{owned}", top_end + 8, text_y + 5, C.C_OK)
            cx = tx
            if hidden:
                self.text("Ache o projeto num destroço do deserto", cx, text_y + 18, "#6e6058", self.body)
            for res, n in ({} if hidden else m.cost).items():
                have = state.available(res, field)       # inventário + baús da base (em campo: só o inventário)
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
                if kw_x >= top_end + 4:              # e o kW também (senão encavala na descrição)
                    self.text(kw, kw_x, text_y + 5, kw_color)
            button = pygame.Rect(bx, by, bw, bh)
            if status == "ok":
                self.surf.fill(pygame.Color(C.C_ACCENT), button)
                self.surf.fill(pygame.Color("#f29a62"), (bx, by, bw, 1))
                self.text("CRAFTAR", bx + bw / 2, by + 6, "#1b1411", align="center")
                self.fabricator_buttons.append((button, kind))
            elif status == "missing":
                pygame.draw.rect(self.surf, pygame.Color(C.C_ALERT), button, 1)
                res = state.missing_resource(kind, field)
                self.text(f"SEM {C.RESOURCE_LABEL[res]}", bx + bw / 2, by + 6, C.C_ALERT, align="center")
            elif hidden:
                pygame.draw.rect(self.surf, pygame.Color("#5a4a40"), button, 1)
                self.text("SEM PROJETO", bx + bw / 2, by + 6, C.C_MUTED, align="center")
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
        self.hud_panel(self.hotbar_x - 3, self.hotbar_y - 11, GRID_W + 6, SLOT + 14)
        for i in range(C.HOTBAR_SLOTS):
            x = self.hotbar_x + i * SLOT_STEP
            self.text(str(i + 1), x + SLOT / 2 + 1, self.hotbar_y - 10, C.C_TI if i == selected else C.C_MUTED, align="center")
            self.draw_slot(x, self.hotbar_y, inventory.slots[i], item_icon, selected=i == selected)

    def draw_notice(self, text: str, alpha: float, y: int | None = None) -> None:
        """Aviso curto no meio da tela, acima da hotbar ("Inventário cheio"). `y` muda a altura (nos
        painéis de inventário ele vai abaixo da linha de ajuda, pra não cobrir texto)."""
        w = self.body.size(text)[0] + 16
        layer = pygame.Surface((w, 18), pygame.SRCALPHA)
        self.panel(0, 0, w, 18, (40, 12, 9, 225), target=layer)
        layer.fill(pygame.Color(C.C_ALERT), (0, 0, w, 1))
        self.text(text, w / 2, 3, "#ffd0c8", self.body, "center", target=layer)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (self.w // 2 - w // 2, self.hotbar_y - 58 if y is None else y))

    def draw_toast(self, text: str, alpha: float) -> None:
        """Aviso neutro e rápido no topo do centro ("Zoom 1,5×", "Tela cheia")."""
        text = text.upper()            # Silkscreen: na Pixelify de 11 px o "Z" parece um "2"
        w = self.font.size(text)[0] + 16
        layer = pygame.Surface((w, 15), pygame.SRCALPHA)
        self.panel(0, 0, w, 15, target=layer)
        layer.fill(pygame.Color(C.C_ACCENT), (0, 0, w, 1))
        self.text(text, w / 2, 4, C.C_TEXT, target=layer, align="center")
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (self.w // 2 - w // 2, 40))   # logo abaixo do banner de estágio
        self.hud_rects.append(pygame.Rect(self.w // 2 - w // 2, 40, w, 15))

    def _grid(self, inv: Inventory, indexes: list[int], x: int, y: int, item_icon, mouse, selected=None) -> None:
        """Desenha os slots `indexes` de `inv` em linhas de 8, a partir de (x, y), e guarda os retângulos."""
        for n, i in enumerate(indexes):
            sx, sy = x + (n % 8) * SLOT_STEP, y + (n // 8) * SLOT_STEP
            rect = pygame.Rect(sx, sy, SLOT, SLOT)
            self.draw_slot(sx, sy, inv.slots[i], item_icon, selected=i == selected, hover=rect.collidepoint(mouse))
            self.slot_rects.append((rect, inv, i))

    def _section_label(self, label: str, x: int, y: int, color: str = C.C_MUTED) -> None:
        """Rótulo de seção de painel ("HOTBAR", "TRAJE", "DRONES"): entra nos cabeçalhos que o tooltip evita."""
        w = self.text(label, x, y, color)
        self.header_rects.append(pygame.Rect(x, y + 3, w + 1, 7))      # a letra (5 px) + sombra, com 1 px de folga

    def _window(self, x: int, y: int, w: int, h: int, title: str, color: str) -> None:
        self.header_rects.append(pygame.Rect(x, y, w, 20))      # faixa do título: o tooltip não cobre
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.surf.fill(pygame.Color(color), (x, y, w, 2))
        self.text(title, x + 8, y + 6, color)

    def draw_inventory(self, inventory: Inventory, side, hotbar_selected: int, item_icon,
                       mouse: tuple[float, float], t: float = 0.0, editing=None, status: str = "",
                       info: str | None = None, equipment=None, state: GameState | None = None) -> None:
        """Tela do Tab (só o inventário) ou com um painel do lado: baú ou estação de drones.
        No Tab, com `state`, ganha as abas Inventário / Fabricar / LOGs no topo (as outras abas são
        draw_field_craft e draw_logs).

        `side` = None (Tab) ou a Machine aberta (baú ou estação). `editing` = TextField do nome do
        baú sendo editado (ou None). `status` = linha de estado da estação ("2 drones · 1 kW").
        Inventário: mochila (slots 8–15) em cima, hotbar (slots 0–7) embaixo, igual à ordem da tela."""
        self.slot_rects.clear()
        self.header_rects.clear()
        self.bay_rects.clear()
        self.buffer_rects.clear()
        self.panel_buttons.clear()
        self.logistics_buttons.clear()
        self.equip_rects.clear()
        self.inv_tab_rects.clear()
        self.log_rows.clear()
        self.name_rect = None
        self.fill((8, 5, 4, 158), (0, 0, self.w, self.h))
        pw = GRID_W + 16
        tabbed = side is None and state is not None             # Tab: abas Inventário / Fabricar / LOGs no topo
        if tabbed:                                              # alarga pra as 3 abas caberem
            pw = max(pw, self.inv_tabs_width() + 16)
        x_pad = (pw - GRID_W) // 2                              # grade centralizada (8 px sem as abas)
        top = 20 + (INV_TABS_H if tabbed else 0)                # onde começa a mochila (título + abas)
        ph_inv = top + 6 + SLOT + 14 + SLOT + 8                 # título, mochila, rótulo HOTBAR, hotbar
        if side is None and equipment is not None:
            ph_inv += 14 + SLOT + 2                             # Marco 3: rótulo TRAJE + slots de equipamento
        ph_side = SIDE_LOGI_Y + LOGI_H + 5                      # baú/drill: grade, botões e a seção DRONES
        total_w = pw if side is None else 2 * pw + 10
        x = (self.w - total_w) // 2
        if isinstance(side, Crate):                             # caixa: grade de 1 linha, texto e botões
            ph_side = SIDE_GRID_Y + SLOT + 6 + 26 + 15 + 8
        h = ph_inv if side is None else max(ph_inv, ph_side)
        y = (self.h - h) // 2 - 16
        if tabbed:                                              # topo no mesmo lugar nas duas abas
            y = self.inv_tabs_top(h)

        self._window(x, y, pw, h, "INVENTÁRIO", C.C_TI)
        used = sum(1 for s in inventory.slots if s)
        self.text(f"{used}/{len(inventory)}", x + pw - 8, y + 6, C.C_MUTED, align="right")
        if tabbed:
            self._inventory_tabs(x, y, pw, TAB_INVENTORY, state, mouse)
        hb = C.HOTBAR_SLOTS
        gx, gy = x + x_pad, y + top + 6
        self._grid(inventory, list(range(hb, len(inventory))), gx, gy, item_icon, mouse)
        self._section_label("HOTBAR", gx, gy + SLOT + 4)
        self._grid(inventory, list(range(hb)), gx, gy + SLOT + 14, item_icon, mouse, hotbar_selected)
        if side is None and equipment is not None:
            self._equipment_row(equipment, gx, gy + 2 * SLOT + 14 + 6, item_icon, mouse)

        if side is None:
            keys = ("[CLIQUE] PEGA/SOLTA · [DIREITO] METADE · [ESC] FECHA" if equipment is None else
                    "[CLIQUE] PEGA/SOLTA · EQUIPA · [DIREITO] METADE · [ESC] FECHA")
            if tabbed:
                keys = "[CLIQUE] PEGA/SOLTA · EQUIPA · [DIREITO] METADE · [A/D] ABA · [ESC] FECHA"
        elif isinstance(side, Crate):
            self._crate_panel(side, x + pw + 10, y, pw, h, item_icon, mouse)
            keys = "[CLIQUE] TIRA A PILHA · [DIREITO] 1 · [ESC] FECHA"
        elif side.is_chest:
            self._chest_panel(side, x + pw + 10, y, pw, h, item_icon, mouse, t, editing)
            keys = ("DIGITE O NOME · [ENTER] OK · [ESC] CANCELA" if editing is not None else
                    "[CLIQUE] PILHA · [DIREITO] 1 · [SHIFT+CLIQUE] TODAS · [ESC] FECHA")
        elif side.is_drill:
            self._drill_panel(side, x + pw + 10, y, pw, h, item_icon, mouse, status)
            keys = "[CLIQUE] TIRA A PILHA · [DIREITO] 1 · [ESC] FECHA"
        else:
            self._station_panel(side, x + pw + 10, y, pw, h, item_icon, mouse, status, info)
            keys = "[CLIQUE] PILHA/DRONE · [DIREITO] 1 · [ESC] FECHA"
        self.text(keys, self.w / 2, y + h + 6, C.C_MUTED, align="center")
        self.notice_y = self.panel_notice_y(y, y + h + 18)

    NOTICE_H = 18                                      # altura do aviso (draw_notice)

    # ---- abas do Tab: Inventário / Fabricar / LOGs ---------------------------------
    INV_TAB_LABELS = ("Inventário", "Fabricar", "LOGs")
    TAB_DOT = 5                                        # espaço do ponto laranja de LOG novo

    def inv_tab_labels(self, state: GameState) -> list[str]:
        found = len(state.logs_read)
        return [*self.INV_TAB_LABELS[:TAB_LOGS], f"{self.INV_TAB_LABELS[TAB_LOGS]} {found}/{len(C.LOGS)}"]

    def inv_tabs_width(self) -> int:
        """Largura das 3 abas no pior caso (contador 7/7 e o ponto de NOVO): a janela não muda conforme acha."""
        labels = [*self.INV_TAB_LABELS[:TAB_LOGS], f"{self.INV_TAB_LABELS[TAB_LOGS]} {len(C.LOGS)}/{len(C.LOGS)}"]
        return sum(self.body.size(lb)[0] + 10 for lb in labels) + self.TAB_DOT + 3 * (len(labels) - 1)

    def inv_tabs_top(self, h: int) -> int:
        """y do topo da janela do Tab: o mesmo nas 3 abas (sai da mais alta), pra as abas não pularem."""
        tallest = max(h, self.logs_window_size()[1], self.field_window_size()[1])
        return max(4, (self.h - tallest) // 2 - 16)

    def _inventory_tabs(self, x: int, y: int, w: int, active: int, state: GameState, mouse) -> None:
        """Abas embaixo do título, iguais às do fabricador. A de LOGs leva o contador (3/7) e um ponto
        laranja se tem LOG lido que ainda não foi aberto por ela."""
        self.inv_tab_rects.clear()
        labels = self.inv_tab_labels(state)
        tx = x + 8
        for i, label in enumerate(labels):
            dot = i == TAB_LOGS and state.new_logs > 0
            tw = self.body.size(label)[0] + 10 + (self.TAB_DOT if dot else 0)
            rect = pygame.Rect(tx, y + 20, tw, 15)
            on = i == active
            hover = not on and rect.collidepoint(mouse)
            self.surf.fill(pygame.Color("#2c1e18" if on else "#211915" if hover else "#160f0d"), rect)
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if on else "#3a2c25"), rect, 1)
            if on:                                      # a aba ativa "abre" pro conteúdo
                self.surf.fill(pygame.Color("#2c1e18"), (rect.x + 1, rect.bottom - 1, rect.w - 2, 2))
            self.text(label, rect.x + 5, rect.y + 1, C.C_TEXT if on else C.C_MUTED, self.body)
            if dot:
                self.surf.fill(pygame.Color(C.C_ACCENT), (rect.right - 7, rect.y + 6, 3, 3))
            self.inv_tab_rects.append((rect, i))
            tx += tw + 3
        pygame.draw.line(self.surf, pygame.Color("#3a2c25"), (x + 8, y + 34), (x + w - 9, y + 34))
        self.header_rects.append(pygame.Rect(x, y + 20, w, INV_TABS_H - 1))   # abas: o tooltip não cobre

    # ---- aba Fabricar do Tab (fabricar em campo) -------------------------------------
    FIELD_SAMPLE_HAVE = 999                            # largura do custo reservada pra "999/12 FERRO"
    FIELD_HIDDEN_LINE = "Ache o projeto num destroço do deserto"

    def field_window_size(self) -> tuple[int, int]:
        """(largura, altura) da janela da aba Fabricar. A largura sai do texto mais comprido das receitas do kit
        (nome + descrição + "x5", custo com 3 dígitos, linha de projeto não encontrado) mais a prévia e o botão;
        não muda conforme o inventário. Altura: o kit inteiro, sem rolagem."""
        text_w = self.body.size(self.FIELD_HIDDEN_LINE)[0]
        for kind in field_kinds():
            m = C.MACHINES[kind]
            line1 = self.body_big.size(m.name)[0] + 6 + self.body.size(m.desc)[0] + 8 + self.font.size("x5")[0]
            line2 = sum(self.font.size(f"{self.FIELD_SAMPLE_HAVE}/{n} {C.RESOURCE_LABEL[r]}")[0] + 8
                        for r, n in m.cost.items())
            text_w = max(text_w, line1, line2)
        w = min(self.w - 8, max(self.inv_tabs_width() + 16, 56 + text_w + 8 + 86))
        rows = len(field_kinds())
        return w, 20 + INV_TABS_H + 4 + rows * (FIELD_ROW_H + 1) + 3

    def draw_field_craft(self, state: GameState, menu, machine_preview, mouse) -> None:
        """Aba Fabricar do Tab: o kit de campo (C.FIELD_RECIPES) com o mesmo visual das linhas do fabricador
        (_recipe_list), mas o custo conta só o inventário. `menu` = fabricator.field_menu().
        Hit-test: fabricator_rows, fabricator_buttons e inv_tab_rects."""
        self.slot_rects.clear()
        self.header_rects.clear()
        self.equip_rects.clear()
        self.log_rows.clear()
        self.fabricator_rows.clear()
        self.fabricator_buttons.clear()
        self.fill((8, 5, 4, 158), (0, 0, self.w, self.h))
        w, h = self.field_window_size()
        x = (self.w - w) // 2
        y = self.inv_tabs_top(TAB_INV_H)               # mesmo topo das outras abas
        self._window(x, y, w, h, "FABRICAR EM CAMPO", C.C_TI)
        self.text("SÓ DO INVENTÁRIO", x + w - 8, y + 6, C.C_MUTED, align="right")
        self._inventory_tabs(x, y, w, TAB_CRAFT, state, mouse)
        self._recipe_list(state, menu, x, w, y + 20 + INV_TABS_H + 4, FIELD_ROW_H, machine_preview, field=True)
        keys = f"[W/S] ESCOLHE · [ENTER] CRAFTA · [SHIFT+ENTER] X{C.CRAFT_BATCH} · [A/D] ABA · [ESC] FECHA"
        self.text(keys, self.w / 2, y + h + 6, C.C_MUTED, align="center")
        self.notice_y = self.panel_notice_y(y, y + h + 18)

    NEW_TAG = "NOVO"

    def log_row_text(self, log: int, number: int, read: bool) -> str:
        """"LOG 03 · Dia 97 · <título>" (lido) ou "LOG 03 · ???" (não achado: não revela dia nem título)."""
        if not read:
            return f"LOG {number:02d} · ???"
        return f"LOG {number:02d} · Dia {C.LOG_DAYS[log]} · {C.LOG_TITLES[log]}"

    def logs_window_size(self) -> tuple[int, int]:
        """(largura, altura) da janela da aba LOGs. A largura sai do texto mais comprido de TODOS os LOGs (lidos
        ou não), então não muda conforme acha; se a altura não cabe na tela, mostra menos linhas (rola)."""
        tag_w = self.font.size(self.NEW_TAG)[0] + 6
        text_w = max(self.body.size(self.log_row_text(log, n, True))[0] for n, log in enumerate(C.LOG_ORDER, 1))
        w = min(self.w - 8, max(GRID_W + 16, self.inv_tabs_width() + 16, 8 + 6 + text_w + 8 + tag_w + 6 + 8 + 4))
        room = self.h - 20 - INV_TABS_H - 6 - 6 - 40       # tela menos título, abas, margens e ajuda/hotbar
        rows = max(1, min(len(C.LOGS), room // LOG_ROW_STEP))
        self.log_visible = rows
        return w, 20 + INV_TABS_H + 4 + rows * LOG_ROW_STEP + 4

    def draw_logs(self, state: GameState, selected: int, first: int, mouse) -> None:
        """Aba LOGs do Tab: os LOGs na ordem da história (config.LOG_ORDER). Lido = "LOG 0N · Dia X · título"
        e clicável (abre a tela de leitura); não achado = "LOG 0N · ???" apagado. "NOVO" nos lidos que a aba
        ainda não abriu. `selected`/`first` = linha escolhida (W/S) e a primeira visível (rolagem).
        Hit-test: log_rows (só os lidos) e inv_tab_rects."""
        self.slot_rects.clear()
        self.header_rects.clear()
        self.equip_rects.clear()
        self.log_rows.clear()
        self.fill((8, 5, 4, 158), (0, 0, self.w, self.h))
        w, h = self.logs_window_size()
        x = (self.w - w) // 2
        y = self.inv_tabs_top(TAB_INV_H)               # mesmo topo da aba Inventário
        self._window(x, y, w, h, "LOGS ENCONTRADOS", C.C_TERMINAL)
        self._inventory_tabs(x, y, w, TAB_LOGS, state, mouse)
        entries = state.log_entries()
        rows = self.log_visible
        first = max(0, min(first, len(entries) - rows))
        list_y = y + 20 + INV_TABS_H + 4
        tag_w = self.font.size(self.NEW_TAG)[0] + 6
        for k, (log, number, read, new) in enumerate(entries[first:first + rows]):
            i = first + k
            row = pygame.Rect(x + 8, list_y + k * LOG_ROW_STEP, w - 16 - (5 if rows < len(entries) else 0), LOG_ROW_H)
            hover = read and row.collidepoint(mouse)
            sel = i == selected
            self.surf.fill(pygame.Color("#2c1e18" if hover or (sel and read) else "#211915" if read else "#171110"), row)
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if sel else "#3a2c25" if read else "#261c18"), row, 1)
            color = C.C_TEXT if read else "#5a4a40"
            self.text(self.log_row_text(log, number, read), row.x + 6, row.y, color, self.body)
            if new:                                     # selo "NOVO" encostado na direita
                tag = pygame.Rect(row.right - 4 - tag_w, row.y + 3, tag_w, 9)
                self.surf.fill(pygame.Color(C.C_ACCENT), tag)
                self.text(self.NEW_TAG, tag.centerx, tag.y - 2, "#1b1411", align="center")   # letra de 5 px no meio
            if read:
                self.log_rows.append((row, log))
        if rows < len(entries):                         # barra de rolagem na margem direita
            track = pygame.Rect(x + w - 10, list_y, 3, rows * LOG_ROW_STEP - 1)
            self.surf.fill(pygame.Color("#120d0b"), track)
            thumb_h = max(8, round(track.h * rows / len(entries)))
            thumb_y = track.y + round((track.h - thumb_h) * first / max(1, len(entries) - rows))
            self.surf.fill(pygame.Color(C.C_ACCENT), (track.x, thumb_y, 3, thumb_h))
        keys = "[CLIQUE/ENTER] LÊ DE NOVO · [W/S] ESCOLHE · [A/D] ABA · [ESC] FECHA"
        self.text(keys, self.w / 2, y + h + 6, C.C_MUTED, align="center")
        self.notice_y = self.panel_notice_y(y, y + h + 18)

    def _equipment_row(self, equipment, x: int, y: int, item_icon, mouse) -> None:
        """TRAJE: um slot por equipamento (tanque, scanner). Vazio mostra o ícone apagado como dica."""
        self._section_label("TRAJE", x, y)
        sx = x
        for kind in C.EQUIP_SLOTS:
            sy = y + 10
            rect = pygame.Rect(sx, sy, SLOT, SLOT)
            item = equipment.slots.get(kind)
            self.draw_slot(sx, sy, Stack(item, 1) if item else None, item_icon, hover=rect.collidepoint(mouse))
            if item:
                pygame.draw.rect(self.surf, pygame.Color(C.C_O2), (sx - 1, sy - 1, SLOT + 2, SLOT + 2), 1)
            else:
                ghost = item_icon(kind).copy()
                ghost.set_alpha(45)
                self.native.append((ghost, (sx * 2 + 4, sy * 2 + 4)))
            self.equip_rects.append((rect, kind))
            label = C.EQUIP_LABEL[kind]
            self.text(label, sx + SLOT + 4, sy + 6, C.C_O2 if item else "#6e6058")
            sx += SLOT + 4 + self.font.size(label)[0] + 12

    def _crate_panel(self, crate, cx: int, y: int, pw: int, h: int, item_icon, mouse) -> None:
        """Caixa de saque de um destroço: só tirar (clique = pilha, direito = 1), Pegar tudo e, na nave e na
        sonda, Ler registro (o LOG que apareceu ao abrir)."""
        amber = "#f2a33a"
        self._window(cx, y, pw, h, f"{crate.wreck.name.upper()} · CAIXA", amber)
        box = crate.storage
        used = sum(1 for st in box.slots if st)
        self.text(f"{used}/{len(box)}", cx + pw - 8, y + 6, C.C_MUTED, align="right")
        self._grid(box, list(range(len(box))), cx + 8, y + SIDE_GRID_Y, item_icon, mouse)
        line_y = y + SIDE_GRID_Y + SLOT + 6
        if crate.empty:
            self.text("VAZIA", cx + 8, line_y, C.C_ALERT)
            self.text("o saque não volta", cx + 8 + self.font.size("VAZIA")[0] + 6, line_y - 2, C.C_MUTED, self.body)
        else:
            for k, text in enumerate(wrap(self.body, "Só dá pra tirar. O conteúdo é fixo: não reabastece.", GRID_W)[:2]):
                self.text(text, cx + 8, line_y - 2 + k * 12, "#a89a8e", self.body)
        by = line_y + 26
        take_w = self.font.size("PEGAR TUDO")[0] + 12
        self._button(pygame.Rect(cx + 8, by, take_w, 15), "Pegar tudo", "take_crate", mouse, not crate.empty)
        if crate.wreck.log is not None and crate.wreck.terminal is None:
            log_w = self.font.size("LER REGISTRO")[0] + 12
            self._button(pygame.Rect(cx + 8 + GRID_W - log_w, by, log_w, 15), "Ler registro", "crate_log", mouse)

    def panel_notice_y(self, panel_top: int, below_help: int) -> int:
        """Onde vai o aviso ("Inventário cheio") com um painel aberto: logo abaixo da linha de ajuda,
        se couber sem encostar na hotbar (moldura começa em hotbar_y - 11); senão, em cima do painel.
        Nunca cobre a linha de ajuda nem a hotbar, em qualquer tamanho de interface."""
        if below_help + self.NOTICE_H <= self.hotbar_y - 11 - 2:
            return below_help
        return max(0, panel_top - self.NOTICE_H - 4)

    def _button(self, rect: pygame.Rect, label: str, action: str, mouse, enabled: bool = True) -> None:
        """Botão pequeno de painel ("Pegar tudo"). Só entra em `panel_buttons` se estiver ativo."""
        hover = enabled and rect.collidepoint(mouse)
        self.surf.fill(pygame.Color("#3a2a20" if hover else "#2a1e19"), rect)
        pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if enabled else "#3a2c25"), rect, 1)
        self.text(label.upper(), rect.centerx, rect.y + 4, C.C_TEXT if enabled else "#6e6058", align="center")
        if enabled:
            self.panel_buttons.append((rect, action))

    def _pencil(self, x: int, y: int, color: str) -> None:
        """Lapisinho de pixels (6×6): o nome do baú é clicável."""
        c = pygame.Color(color)
        for i in range(5):
            self.surf.fill(c, (x + 1 + i, y + 4 - i, 1, 1))
            self.surf.fill(c, (x + 2 + i, y + 5 - i, 1, 1))
        self.surf.fill(c, (x, y + 5, 2, 1))

    def _chest_panel(self, chest, cx: int, y: int, pw: int, h: int, item_icon, mouse, t: float, editing) -> None:
        """Baú: nome (clique edita), os 24 slots e os botões Pegar tudo / Guardar tudo."""
        self._window(cx, y, pw, h, "", C.C_ACCENT)
        box = chest.storage
        used = sum(1 for s in box.slots if s)
        self.text(f"{used}/{len(box)}", cx + pw - 8, y + 6, C.C_MUTED, align="right")
        if editing is not None:                       # campo de texto com cursor piscando
            field = pygame.Rect(cx + 4, y + 3, pw - 44, 15)
            self.surf.fill(pygame.Color("#0d0907"), field)
            pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT), field, 1)
            w = self.text(editing.text, field.x + 4, field.y + 1, C.C_TEXT, self.body) if editing.text else 0
            if (t % C.CHEST_NAME_BLINK) < C.CHEST_NAME_BLINK / 2:
                self.surf.fill(pygame.Color(C.C_TI), (field.x + 5 + w, field.y + 3, 1, 9))
            self.text(f"{len(editing.text)}/{editing.max_len}", field.right - 3, field.y + 4,
                      C.C_ALERT if editing.full else C.C_MUTED, align="right")
            self.name_rect = field
        else:
            name = chest.name or C.CHEST_DEFAULT_NAME
            w = self.body.size(name)[0]
            rect = pygame.Rect(cx + 4, y + 3, w + 20, 15)
            hover = rect.collidepoint(mouse)
            if hover:
                self.fill((255, 255, 255, 24), rect)
                pygame.draw.rect(self.surf, pygame.Color("#5a4034"), rect, 1)
            self.text(name, cx + 8, y + 4, C.C_ACCENT, self.body)
            self._pencil(cx + 13 + w, y + 7, C.C_TI if hover else C.C_MUTED)
            self.name_rect = rect
        self._grid(box, list(range(len(box))), cx + 8, y + SIDE_GRID_Y, item_icon, mouse)
        by = y + SIDE_BUTTONS_Y
        # largura pelo texto (o "Guardar recursos" é mais comprido): um encostado em cada ponta da grade
        take_w = self.font.size("PEGAR TUDO")[0] + 12
        store_w = self.font.size("GUARDAR RECURSOS")[0] + 12
        self._button(pygame.Rect(cx + 8, by, take_w, 15), "Pegar tudo", "take_all", mouse, not box.is_empty())
        self._button(pygame.Rect(cx + 8 + GRID_W - store_w, by, store_w, 15), "Guardar recursos", "store_all", mouse)
        self.draw_logistics(cx + 8, y + SIDE_LOGI_Y, GRID_W, chest, item_icon, mouse)

    def _drill_panel(self, drill, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str) -> None:
        """Drill: o inventário dela (1 slot, só tirar), quanto encheu, Pegar tudo e a seção DRONES."""
        ore = C.RESOURCE_NAME[drill.resource]
        self._window(cx, y, pw, h, f"DRILL · {ore.upper()}", C.C_ACCENT)
        self.text(f"{drill.stored}/{C.DRILL_CAPACITY}", cx + pw - 8, y + 6, C.C_MUTED, align="right")
        self._grid(drill.storage, list(range(len(drill.storage))), cx + 8, y + SIDE_GRID_Y + 4, item_icon, mouse)
        # barra de enchimento do lado do slot, na cor do minério (cheia: verde)
        bx, bw = cx + 8 + SLOT_STEP + 4, GRID_W - SLOT_STEP - 4
        fill = drill.stored / C.DRILL_CAPACITY
        self.surf.fill(pygame.Color("#120d0b"), (bx, y + SIDE_GRID_Y + 6, bw, 6))
        pygame.draw.rect(self.surf, pygame.Color("#3a2c25"), (bx, y + SIDE_GRID_Y + 6, bw, 6), 1)
        if fill > 0:
            color = "#7ad46a" if drill.full else C.ORE_COLORS[drill.resource][0]
            self.surf.fill(pygame.Color(color), (bx + 1, y + SIDE_GRID_Y + 7, round((bw - 2) * fill), 4))
        self.text(status, bx, y + SIDE_GRID_Y + 15, C.C_ALERT if drill.full else C.C_MUTED)
        for k, line in enumerate(wrap(self.body, "Os drones levam daqui o que estiver marcado em ENVIA.",
                                      GRID_W)[:2]):
            self.text(line, cx + 8, y + SIDE_GRID_Y + 36 + k * 12, "#a89a8e", self.body)
        self._button(pygame.Rect(cx + 8, y + SIDE_BUTTONS_Y, self.font.size("PEGAR TUDO")[0] + 12, 15),
                     "Pegar tudo", "take_drill", mouse, drill.stored > 0)
        self.draw_logistics(cx + 8, y + SIDE_LOGI_Y, GRID_W, drill, item_icon, mouse)

    def _station_panel(self, machine, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str,
                       info: str | None = None) -> None:
        """Estação: os 4 slots de drone (travados em voo), o buffer como slots (só tirar) e o estado."""
        st = machine.station
        self._window(cx, y, pw, h, "ESTAÇÃO DE DRONES", C.C_O2)
        self.text(f"{len(st.drones)}/{C.STATION_DRONE_SLOTS}", cx + pw - 8, y + 6, C.C_MUTED, align="right")
        self._section_label("DRONES", cx + 8, y + 24)
        self.text("ALCANCE: MAPA TODO", cx + pw - 8, y + 24, C.C_MUTED, align="right")
        n = C.STATION_DRONE_SLOTS
        margin = 6
        step = (GRID_W - 2 * margin - SLOT) // (n - 1)    # espalhados na largura: cabe "POUSADO" embaixo de cada
        for slot in range(n):
            sx, sy = cx + 8 + margin + slot * step, y + 33
            rect = pygame.Rect(sx, sy, SLOT, SLOT)
            drone = st.drone_in(slot)
            self.draw_slot(sx, sy, None, item_icon, hover=rect.collidepoint(mouse))
            if drone is not None:
                icon = item_icon("drone")
                if drone.busy:                         # em viagem: travado, ícone apagado e moldura azul
                    icon = icon.copy()
                    icon.set_alpha(90)
                    pygame.draw.rect(self.surf, pygame.Color(C.C_O2), (sx - 1, sy - 1, SLOT + 2, SLOT + 2), 1)
                    self.text("EM VOO", sx + SLOT / 2, sy + SLOT + 2, C.C_O2, align="center")
                else:
                    self.text("POUSADO", sx + SLOT / 2, sy + SLOT + 2, C.C_MUTED, align="center")
                self.native.append((icon, (sx * 2 + 4, sy * 2 + 4)))
            else:
                self.text("VAZIO", sx + SLOT / 2, sy + SLOT + 2, "#5a4a40", align="center")
            self.bay_rects.append((rect, slot))
        by = y + 72
        stacks = st.buffer_stacks()
        if stacks:                                     # sobras do buffer antigo (save ≤ v4): só tirar
            self.text("SOBRAS (SÓ TIRAR)", cx + 8, by, C.C_MUTED)
            for k in range(len(C.RESOURCES)):
                sx, sy = cx + 8 + k * SLOT_STEP, by + 10
                rect = pygame.Rect(sx, sy, SLOT, SLOT)
                stack = Stack(*stacks[k]) if k < len(stacks) else None
                self.draw_slot(sx, sy, stack, item_icon, hover=stack is not None and rect.collidepoint(mouse))
                if stack is not None:
                    self.buffer_rects.append((rect, stack.item))
            self._button(pygame.Rect(cx + 8 + 3 * SLOT_STEP + 6, by + 12, GRID_W - 3 * SLOT_STEP - 6, 15),
                         "Pegar tudo", "take_buffer", mouse, True)
        else:                                          # o lugar vira a dica de como a logística funciona
            tip = ("Os drones levam itens de quem ENVIA pra quem RECEBE, no mapa todo. "
                   "Configure no painel de cada baú e drill (seção DRONES).")
            for k, line in enumerate(wrap(self.body, tip, GRID_W)):
                self.text(line, cx + 8, by + k * 12, "#a89a8e", self.body)
        if info:                                       # o que está debaixo do mouse (no lugar do tooltip)
            self.text(info, cx + 8, y + h - 30, C.C_TI, self.body)
        self.text(status, cx + 8, y + h - 16, "#d9cfc4", self.body)

    # ---- seção DRONES do baú/drill: Envia, Recebe e Lote (bloco autocontido: desenho + hit-test) ----
    def _toggle(self, rect: pygame.Rect, item: str, active: bool, color: str, item_icon, mouse) -> None:
        """Botão 18×18 com o ícone do item: ativo com fundo e borda na cor da linha, inativo apagado."""
        hover = rect.collidepoint(mouse)
        self.surf.fill(pygame.Color("#33261e" if active else "#120d0b"), rect)
        if hover:
            self.fill((255, 255, 255, 30), rect.inflate(-2, -2))
        pygame.draw.rect(self.surf, pygame.Color(color if active else "#3a2c25"), rect, 1)
        icon = item_icon(item)
        if not active:
            icon = icon.copy()
            icon.set_alpha(95)
        self.native.append((icon, (rect.x * 2 + 2, rect.y * 2 + 2)))

    def draw_logistics(self, x: int, y: int, w: int, machine, item_icon, mouse) -> None:
        """Seção "DRONES" a partir de (x, y), largura `w`, altura LOGI_H, uma coisa por linha:

            DRONES                          NADA CONFIGURADO
            ENVIA            [fe][si][ge]
            RECEBE           [fe][si][ge]
            LOTE POR VIAGEM  [1][5][10][20]

        A drill pula o RECEBE (ela só produz) e só mostra o minério dela no ENVIA.
        Guarda os botões em `logistics_buttons`."""
        from game import drones                      # (import local: a UI não depende da lógica no topo)
        self.fill((255, 255, 255, 28), (x, y, w, 1))
        self._section_label("DRONES", x, y + 4, C.C_O2)
        if not drones.configured(machine):
            self.text("NADA CONFIGURADO", x + w, y + 4, C.C_TI, align="right")
        col = x + self.font.size("LOTE POR VIAGEM")[0] + 8     # todos os botões começam na mesma coluna
        ry = y + 13
        rows = [("ENVIA", "send", machine.sends, C.C_ACCENT, drones.can_send)]
        if not machine.is_drill:
            rows.append(("RECEBE", "recv", machine.receives, C.C_O2, drones.can_receive))
        for label, kind, chosen, color, allowed in rows:
            self.text(label, x, ry + 6, C.C_MUTED)
            for k, item in enumerate(i for i in C.LOGISTIC_ITEMS if allowed(machine, i)):
                rect = pygame.Rect(col + k * (LOGI_BTN + 2), ry, LOGI_BTN, LOGI_BTN)
                self._toggle(rect, item, item in chosen, color, item_icon, mouse)
                self.logistics_buttons.append((rect, (kind, item)))
            ry += LOGI_ROW
        self.text("LOTE POR VIAGEM", x, ry + 6, C.C_MUTED)
        for k, amount in enumerate(C.DRONE_BATCH_OPTIONS):
            rect = pygame.Rect(col + k * (BATCH_BTN_W + 2), ry, BATCH_BTN_W, LOGI_BTN)
            active, hover = amount == machine.batch, rect.collidepoint(mouse)
            self.surf.fill(pygame.Color("#3a2a22" if active else "#120d0b"), rect)
            if hover and not active:
                self.fill((255, 255, 255, 30), rect.inflate(-2, -2))
            pygame.draw.rect(self.surf, pygame.Color(C.C_TI if active else "#3a2c25"), rect, 1)
            self.text(str(amount), rect.centerx + 1, rect.y + 6, C.C_TEXT if active else C.C_MUTED, align="center")
            self.logistics_buttons.append((rect, ("batch", amount)))

    def logistics_at(self, pos) -> tuple[str, object] | None:
        """Qual botão da seção DRONES está debaixo de `pos` (coordenadas da UI): ("send", item),
        ("recv", item), ("batch", n) ou None."""
        return next((value for rect, value in self.logistics_buttons if rect.collidepoint(pos)), None)

    # ---- rótulo flutuante do baú no mundo: ↓[recebe] ↑[envia] Nome ------------------
    @staticmethod
    def chest_label_parts(chest) -> list[tuple[str, str]]:
        """O que vai no rótulo em cima do baú: ("arrow", "down") + ícones do que recebe, ("arrow", "up")
        + ícones do que envia, e ("text", nome). Sem configuração, só o nome."""
        parts = []
        for arrow, chosen in (("down", chest.receives), ("up", chest.sends)):
            items = [i for i in C.LOGISTIC_ITEMS if i in chosen]
            if items:
                parts.append(("arrow", arrow))
                parts += [("icon", i) for i in items]
        parts.append(("text", chest.name or C.CHEST_DEFAULT_NAME))
        return parts

    def _label_arrow(self, x: int, y: int, down: bool) -> None:
        """Setinha 5×6 do rótulo: ↓ (recebe, azul) ou ↑ (envia, laranja)."""
        color = pygame.Color(C.C_O2 if down else C.C_ACCENT)
        self.surf.fill(color, (x + 2, y + (0 if down else 2), 1, 4))
        for k in range(3):
            row = k if not down else 2 - k
            self.surf.fill(color, (x + 2 - row, y + (3 + k if down else k), 2 * row + 1, 1))

    def draw_chest_labels(self, chests, cam: tuple[int, int], zoom: float, icons: dict) -> None:
        """Rótulo em cima de cada baú de `chests`: preso no mundo (acompanha o zoom), letra de tamanho fixo.
        `icons`: ícones 16×16 dos minérios (desenhados em resolução cheia, 8 px na UI)."""
        placed: list[pygame.Rect] = []
        self.chest_label_rects = []                       # os desenhados agora (os floaters desviam deles)
        for chest in sorted(chests, key=lambda c: -c.anchor[1]):  # o da frente primeiro; os de trás sobem
            parts = self.chest_label_parts(chest)
            widths = [8 if kind == "icon" else 5 if kind == "arrow" else self.body.size(value)[0]
                      for kind, value in parts]
            gaps = [1 if kind == "arrow" or (kind == "icon" and nxt[0] == "icon") else 3
                    for (kind, _), nxt in zip(parts, parts[1:])]
            w = sum(widths) + sum(gaps) + 8
            ax, ay = chest.anchor
            top = ay - C.CHEST_SPRITE_SIZE[1] - 2                 # logo acima da tampa (mundo)
            sx, sy = self.world_to_ui((ax, top), cam, zoom)
            x, y = int(sx - w / 2), int(sy - 15)
            while any(r.colliderect((x, y, w, 14)) for r in placed):   # baús vizinhos: empilha
                y -= 15
            placed.append(pygame.Rect(x, y, w, 14))
            if not (-w < x < self.w and -14 < y < self.h):
                continue
            self.chest_label_rects.append(pygame.Rect(x, y, w, 14))
            self.panel(x, y, w, 14, (14, 10, 9, 210))
            px = x + 4
            for n, ((kind, value), pw) in enumerate(zip(parts, widths)):
                if kind == "icon":
                    self.native.append((icons[value], (px * 2, (y + 3) * 2)))
                elif kind == "arrow":
                    self._label_arrow(px, y + 4, value == "down")
                else:
                    self.text(value, px, y + 1, C.C_TEXT, self.body)
                px += pw + (gaps[n] if n < len(gaps) else 0)

    def draw_held_and_tooltip(self, held: Stack | None, label: str | None, mouse, item_icon) -> None:
        """Por cima de tudo: a pilha presa no cursor ou, sem nada na mão, o texto do slot debaixo do
        mouse (nome · quantidade, ou o estado do drone)."""
        mx, my = mouse
        if held is not None:
            self.native.append((item_icon(held.item), (int(mx * 2) + 6, int(my * 2) + 6)))
            if held.count > 1:
                self.native_text(str(held.count), mx + 20, my + 14, C.C_TEXT, "right")
        elif label:
            w = self.body.size(label)[0] + 12
            rect = self.tooltip_rect(w, mouse)
            self.panel(*rect, (14, 10, 9, 255))     # opaco: o número da pilha vizinha não vaza
            self.text(label, rect.x + 6, rect.y + (rect.h - 16) // 2 + 2, C.C_TEXT, self.body)

    TOOLTIP_H = 16

    def tooltip_rect(self, w: int, mouse) -> pygame.Rect:
        """Onde vai o tooltip de largura `w`: ancorado no elemento debaixo do mouse (slot, slot do traje ou
        botão da seção DRONES). Primeiro do lado direito dele, na faixa da linha (cobre só os vizinhos da
        linha, nunca o título da janela, as abas ou um rótulo); se não couber na tela, do lado esquerdo;
        senão, a posição embaixo/em cima mais perto do elemento que cabe na tela sem cobrir cabeçalho
        (header_rects). Antes ia sempre em cima do slot e, na 1ª linha do baú, tapava o nome dele."""
        h = self.TOOLTIP_H
        anchors = [*(r for r, _, _ in self.slot_rects), *(r for r, _ in self.equip_rects),
                   *(r for r, _ in self.logistics_buttons), *(r for r, _ in self.bay_rects),
                   *(r for r, _ in self.buffer_rects)]
        under = next((r for r in anchors if r.collidepoint(mouse)), None)
        if under is None:
            mx, my = int(mouse[0]), int(mouse[1])
            under = pygame.Rect(mx - 2, my - 2, 4, 4)     # sem elemento: em volta do cursor
        screen = pygame.Rect(0, 0, self.w, self.h).inflate(-4, -4)

        def free(rect: pygame.Rect) -> bool:
            return screen.contains(rect) and rect.collidelist(self.header_rects) < 0

        # do lado, cobre a altura inteira do slot vizinho (senão o número da pilha dele aparece pela beirada)
        side_h = max(h, under.h)
        for x in (under.right + 2, under.left - 2 - w):
            rect = pygame.Rect(x, under.centery - side_h // 2, w, side_h)
            if free(rect):
                return rect
        x = max(2, min(under.x, self.w - w - 2))
        for dy in range(0, self.h, 2):
            for y in (under.bottom + 2 + dy, under.top - 2 - h - dy):
                rect = pygame.Rect(x, y, w, h)
                if free(rect):
                    return rect
        return pygame.Rect(x, under.bottom + 2, w, h).clamp(screen)

    def _arrow(self, cx: int, y: int, up: bool) -> None:
        """Setinha de 5×3 (tem mais receita pra cima/baixo)."""
        for k in range(3):
            row = k if up else 2 - k
            self.surf.fill(pygame.Color(C.C_MUTED), (cx - row, y + k, 2 * row + 1, 1))

    # ---- terminal -------------------------------------------------------------
    def draw_terminal(self, index: int, t: float) -> None:
        dw, dh = min(self.w - 36, 560), 92        # largura limitada: linha comprida demais cansa de ler
        dx, dy = (self.w - dw) // 2, self.h - 100
        self.panel(dx, dy, dw, dh, (10, 16, 13, 237))
        self.surf.fill(pygame.Color(C.C_TERMINAL), (dx, dy, dw, 2))
        self.text(f"{C.LOG_TITLES[index]} · {C.log_label(index)}", dx + 10, dy + 8, C.C_TERMINAL)
        for i, line in enumerate(wrap(self.body, C.LOGS[index], dw - 20)):
            self.text(line, dx + 10, dy + 22 + i * 13, "#d6eadf", self.body)
        if (t * 9) % 10 < 6:
            self.text("[E] CONTINUAR", dx + dw - 10, dy + dh - 13, C.C_TERMINAL, align="right")

    # ---- banner de estágio ----------------------------------------------------
    @property
    def BANNER_GAP(self) -> tuple[int, int]:
        """Vão livre no topo, entre o painel de O₂ (x 6–118) e o do Ti, em coordenadas da UI."""
        return 118, self.ti_panel_x

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
        self.hud_rects.append(pygame.Rect(x, y, w, h))

    # ---- desmaio --------------------------------------------------------------
    def draw_faint(self, state: GameState) -> None:
        ft = state.faint_time
        a = ft / C.FAINT_RESPAWN_AT if ft < C.FAINT_RESPAWN_AT else (C.FAINT_DURATION - ft) / (C.FAINT_DURATION - C.FAINT_RESPAWN_AT)
        a = max(0.0, min(1.0, a))
        self.fill((0, 0, 0, int(255 * a)), (0, 0, self.w, self.h))
        if a > 0.6:
            self.text("Tu apagou. Acordando na cápsula...", self.w / 2, self.h / 2 - 6, "#d9cfc4", self.body, "center")

    def draw_ramp_fade(self, state: GameState) -> None:
        """Descendo/subindo pela rampa: escurece até o RAMP_SWITCH_AT (troca de camada no preto) e clareia."""
        trip = state.ramp
        if trip is None:
            return
        t, mid, end = trip.time, C.RAMP_SWITCH_AT, C.RAMP_DURATION
        a = t / mid if t < mid else (end - t) / (end - mid)
        a = max(0.0, min(1.0, a * 1.25))                # fica um tiquinho no preto inteiro
        self.fill((0, 0, 0, int(255 * a)), (0, 0, self.w, self.h))
        if a > 0.5:
            text = "Descendo..." if trip.to == "cave" else "Subindo..."
            self.text(text, self.w / 2, self.h / 2 - 6, "#d9cfc4", self.body, "center")

    # ---- fim do MVP -----------------------------------------------------------
    def draw_end(self, state: GameState, t: float) -> None:
        self.fill((6, 12, 6, 200), (0, 0, self.w, self.h))
        w, h = 340, 190
        x, y = (self.w - w) // 2, (self.h - h) // 2          # no centro (no Grande: 70, 40)
        self.panel(x, y, w, h, (16, 22, 14, 240))
        self.surf.fill(pygame.Color(C.STAGE_COLOR[3]), (x, y, w, 2))
        self.text("FIM DO MVP", self.w / 2, y + 14, C.STAGE_COLOR[3], self.font_big, "center")
        body = ("O primeiro verde brotou na cratera. A Colônia Hesper tentou e sumiu; "
                "tu chegou até aqui. O que tem dentro do gelo fica pra próxima.")
        for i, line in enumerate(wrap(self.body, body, w - 40)):
            self.text(line, self.w / 2, y + 42 + i * 13, "#d6eadf", self.body, "center")
        minutes, seconds = divmod(int(state.play_time), 60)
        stats = [("TEMPO", f"{minutes}:{seconds:02d}"), ("MAQUINAS", str(len(state.machines))),
                 ("TI", fmt(state.ti)), ("LOGS", f"{len(state.logs_read)}/{len(C.LOGS)}")]
        for i, (label, value) in enumerate(stats):
            sx = x + 30 + i * 74
            self.text(label, sx + 30, y + 100, C.C_MUTED, align="center")
            self.text(value, sx + 30, y + 112, C.C_TI, self.body_big, "center")
        self.text("Obrigado por testar o v0.3", self.w / 2, y + 142, "#a6e07a", self.body, "center")
        if (t * 9) % 10 < 6:
            self.text("[ENTER] CONTINUAR EXPLORANDO", self.w / 2, y + h - 18, C.C_TEXT, align="center")

    # ---- menu de pausa ---------------------------------------------------------
    PAUSE_OPTIONS = ["Continuar", "Opções", "Controles", "Salvar e sair", "Sair"]
    VOLUME_ROWS = [("master", "GERAL"), ("sfx", "EFEITOS"), ("ambient", "AMBIENTE")]
    CONTROLS = [
        ("WASD / SETAS", "Andar"),
        ("SEGURAR CLIQUE", "Minerar a parede mirada"),
        ("E", "Abrir o que está no mouse (ou o mais perto)"),
        ("E NA CRATERA", "Descer pra caverna (e subir pela rampa)"),
        ("SHIFT+E", "Coletar a drill sem abrir o painel"),
        ("1 A 8 · RODINHA", "Escolher slot da hotbar"),
        ("CLIQUE · R", "Colocar a máquina da hotbar · girar"),
        ("M", "Mapa (com o scanner de navegação)"),
        ("TAB", "Inventário, fabricar em campo e LOGs (A/D: aba)"),
        ("CLIQUE DIREITO", "Desmontar (volta pro inventário)"),
        ("ESC", "Cancelar / fechar / pausar"),
        ("+ / -", "Aproximar / afastar (ou Ctrl+rodinha)"),
        ("F11 · ALT+ENTER", "Tela cheia"),
        ("ESC > OPÇÕES", "Tamanho da interface (HUD e menus)"),
        ("F1 · F2 · F3", "Debug: tempo x10 · +10.000 Ti · rápido"),
    ]

    def _pause_frame(self, x, y, w, h, title) -> None:
        self.fill((6, 4, 3, 170), (0, 0, self.w, self.h))
        self.surf.fill(pygame.Color("#1b1411"), (x, y, w, h))
        pygame.draw.rect(self.surf, pygame.Color("#5a4034"), (x, y, w, h), 1)
        self.surf.fill(pygame.Color("#2a1e19"), (x + 1, y + 1, w - 2, 18))
        self.surf.fill(pygame.Color(C.C_ACCENT), (x, y, w, 2))
        self.text(title, x + 8, y + 6, C.C_TI)

    def _menu_row(self, rect: pygame.Rect, selected: bool) -> None:
        self.surf.fill(pygame.Color("#2c1e18" if selected else "#211915"), rect)
        pygame.draw.rect(self.surf, pygame.Color(C.C_ACCENT if selected else "#3a2c25"), rect, 1)

    # linhas de "escolha" das Opções, depois dos volumes (Enter/clique/A/D trocam o valor)
    OPTION_ROWS = ("TELA CHEIA", "ZOOM", "INTERFACE")

    def draw_pause(self, screen: str, selected: int, mix: dict, zoom_label: str = "1×",
                   ui_label: str = "MÉDIA", page: int = 0) -> None:
        """Menu de pausa. screen = 'main', 'volumes' (Opções: volumes, tela cheia, zoom, interface)
        ou 'controls'. `mix` é o dicionário das settings (volumes + "fullscreen")."""
        self.pause_items.clear()
        self.pause_sliders.clear()
        self.pause_page_buttons.clear()
        if screen == "main":
            ox, oy = self.center_offset                   # menus feitos pra 480×270, centralizados
            x, y, w = 170 + ox, 64 + oy, 140
            self._pause_frame(x, y, w, 26 + 22 * len(self.PAUSE_OPTIONS) + 4, "PAUSA")
            for i, label in enumerate(self.PAUSE_OPTIONS):
                row = pygame.Rect(x + 8, y + 26 + i * 22, w - 16, 19)
                self._menu_row(row, i == selected)
                self.text(label, row.x + 8, row.y + 3, C.C_TEXT if i == selected else "#d9cfc4", self.body)
                self.pause_items.append(row)
            self.text("[W/S] ESCOLHE · [ENTER] OK · [ESC] VOLTA", self.w / 2, y + 26 + 22 * len(self.PAUSE_OPTIONS) + 10,
                      C.C_MUTED, align="center")
        elif screen == "volumes":
            n = len(self.VOLUME_ROWS)
            m = len(self.OPTION_ROWS)
            step = 22                                     # linha de 20 + 2 de vão
            h = 26 + step * (n + m + 1) + 14              # + a linha de ajuda dentro da moldura
            w = 240
            # no meio da tela, sem encostar na hotbar (no Grande a ajuda caía em cima dela)
            x, y = (self.w - w) // 2, max(2, min((self.h - h) // 2, self.hotbar_y - 11 - 4 - h))
            self._pause_frame(x, y, w, h, "OPÇÕES")
            for i, (key, label) in enumerate(self.VOLUME_ROWS):
                row = pygame.Rect(x + 8, y + 26 + i * step, w - 16, step - 2)
                self._menu_row(row, i == selected)
                self.text(label, row.x + 8, row.y + 6, C.C_TEXT)
                bar = pygame.Rect(row.x + 76, row.y + 6, 110, 7)
                self.surf.fill(pygame.Color("#4a3b2a"), bar)
                self.surf.fill(pygame.Color("#120d0b"), bar.inflate(-2, -2))
                fill_w = round((bar.w - 2) * mix[key])
                self.surf.fill(pygame.Color(C.C_TI), (bar.x + 1, bar.y + 1, fill_w, bar.h - 2))
                self.surf.fill(pygame.Color(C.C_TEXT), (bar.x + fill_w - 1, bar.y - 2, 3, bar.h + 4))   # puxador
                self.text(f"{round(mix[key] * 100)}%", row.right - 8, row.y + 6, C.C_TI, align="right")
                self.pause_items.append(row)
                self.pause_sliders.append(bar)
            # tela cheia, zoom e interface: Enter/clique alternam, A/D também
            values = ("SIM" if mix.get("fullscreen") else "NÃO", zoom_label, ui_label)
            for i, (label, value) in enumerate(zip(self.OPTION_ROWS, values), start=n):
                row = pygame.Rect(x + 8, y + 26 + i * step, w - 16, step - 2)
                self._menu_row(row, i == selected)
                self.text(label, row.x + 8, row.y + 6, C.C_TEXT)
                self.text(f"< {value} >" if i == selected else value, row.right - 8, row.y + 4, C.C_TI,
                          self.body, align="right")
                self.pause_items.append(row)
            back = pygame.Rect(x + 8, y + 26 + (n + m) * step, w - 16, step - 2)
            self._menu_row(back, selected == n + m)
            self.text("Voltar", back.x + 8, back.y + 3, C.C_TEXT, self.body)
            self.pause_items.append(back)
            self.text("[W/S] ESCOLHE · [A/D] AJUSTA · [ESC] VOLTA", self.w / 2, y + h - 12, C.C_MUTED, align="center")
        else:  # controls
            self.draw_controls(page)

    CONTROL_STEP = 15                                   # altura de cada linha da tela de Controles

    def controls_layout(self) -> tuple[int, int, list[list[tuple[str, str]]]]:
        """(largura do painel, x da coluna da ação, páginas). Cabe no espaço lógico atual: se as linhas
        não cabem na altura (Grande, 480×270), divide em páginas; a largura sai do texto mais comprido."""
        key_w = max(self.font.size(keys)[0] for keys, _ in self.CONTROLS)
        act_w = max(self.body.size(action)[0] for _, action in self.CONTROLS)
        col = 12 + key_w + 12
        w = min(self.w - 12, col + act_w + 12)
        per_page = max(1, (self.h - 12 - 26 - 30) // self.CONTROL_STEP)
        rows = list(self.CONTROLS)
        n_pages = -(-len(rows) // per_page)
        per_page = -(-len(rows) // n_pages)              # páginas equilibradas (8 + 7, não 13 + 2)
        return w, col, [rows[i:i + per_page] for i in range(0, len(rows), per_page)]

    def draw_controls(self, page: int = 0) -> None:
        w, col, pages = self.controls_layout()
        page %= len(pages)
        rows = pages[page] if len(pages) == 1 else pages[page] + [None] * (len(pages[0]) - len(pages[page]))
        h = 26 + self.CONTROL_STEP * len(rows) + 30
        x, y = (self.w - w) // 2, (self.h - h) // 2
        self._pause_frame(x, y, w, h, "CONTROLES")
        for i, row in enumerate(rows):
            if row is None:
                continue
            keys, action = row
            yy = y + 26 + i * self.CONTROL_STEP
            self.text(keys, x + 12, yy + 3, C.C_TI)
            self.text(action, x + col, yy, "#d9cfc4", self.body)
        back = pygame.Rect(x + 8, y + h - 26, 80, 19)
        self._menu_row(back, True)
        self.text("Voltar", back.x + 8, back.y + 3, C.C_TEXT, self.body)
        self.pause_items.append(back)
        self.controls_pages = len(pages)
        if len(pages) > 1:                               # < 1/2 >  (A/D ou clique trocam a página)
            nxt = pygame.Rect(x + w - 8 - 19, back.y, 19, 19)
            label = f"{page + 1}/{len(pages)}"
            lw = self.font.size(label)[0]
            prev = pygame.Rect(nxt.x - lw - 12 - 19, back.y, 19, 19)
            for rect, arrow in ((prev, "<"), (nxt, ">")):
                self._menu_row(rect, False)
                self.text(arrow, rect.centerx, rect.y + 6, C.C_TEXT, align="center")
                self.pause_page_buttons.append((rect, -1 if arrow == "<" else 1))
            self.text(label, prev.right + 6, back.y + 6, C.C_TI)
            self.text("[A/D] PÁGINA", prev.x - 8, back.y + 6, C.C_MUTED, align="right")

    # ---- projeto encontrado (Marco 3) -----------------------------------------------
    # Aviso em 2 linhas, igual nos 3 tamanhos: rótulo pequeno em cima e o nome do item embaixo, com o
    # ícone do projeto (icon_blueprint, o mesmo da caixa e do inventário) à esquerda. O formato antigo
    # ("PROJETO: SCANNER DE NAVEGAÇÃO" / "receita liberada no fabricador") não cabia com o ícone no vão
    # de 196 px do Grande; assim o mais comprido fica com ~170 px.
    BLUEPRINT_LABEL = "PROJETO · RECEITA LIBERADA"
    BLUEPRINT_PAD, BLUEPRINT_ICON = 6, 16            # margem e ícone (px da UI); 5 px entre ícone e texto

    def blueprint_notice_layout(self, blueprint: str) -> tuple[pygame.Rect, pygame.Rect]:
        """(aviso, ícone) em px da UI: no vão do topo entre o painel de O₂ e o do Ti, sem encostar neles.
        Só se nem assim couber (não acontece com os projetos de hoje), desce pro meio da tela, abaixo do HUD."""
        text_w = max(self.font.size(self.BLUEPRINT_LABEL)[0], self.body.size(C.BLUEPRINTS[blueprint])[0])
        pad, icon = self.BLUEPRINT_PAD, self.BLUEPRINT_ICON
        w, h = pad + icon + 5 + text_w + pad, 30
        left, right = self.BANNER_GAP
        if w <= right - left - 4:
            rect = pygame.Rect((left + right) // 2 - w // 2, 6, w, h)
        else:
            rect = pygame.Rect((self.w - w) // 2, self.h // 2 - 60, w, h)
        return rect, pygame.Rect(rect.x + pad, rect.y + (h - icon) // 2, icon, icon)

    def draw_blueprint_notice(self, blueprint: str, alpha: float, icon: pygame.Surface) -> None:
        """Aviso de projeto encontrado no topo do centro: ícone do projeto + "PROJETO · RECEITA LIBERADA" +
        o nome do que ele libera. `icon`: o ícone 32×32 (resolução cheia) do item do projeto."""
        rect, icon_rect = self.blueprint_notice_layout(blueprint)
        tx = icon_rect.right - rect.x + 5
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        self.panel(0, 0, rect.w, rect.h, (10, 18, 30, 235), target=layer)
        layer.fill(pygame.Color("#9fd0ff"), (0, 0, rect.w, 2))
        # fundinho escuro atrás do ícone: o projeto é azul e sumia no azul do aviso
        back = icon_rect.move(-rect.x, -rect.y).inflate(2, 2)
        layer.fill((4, 8, 14, 255), back)
        pygame.draw.rect(layer, pygame.Color("#2c4a6a"), back, 1)
        self.text(self.BLUEPRINT_LABEL, tx, 6, "#9fd0ff", target=layer)
        self.text(C.BLUEPRINTS[blueprint], tx, 14, "#eef6ff", self.body, target=layer)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, rect.topleft)
        ic = icon.copy()
        ic.set_alpha(int(255 * alpha))
        self.native.append((ic, (icon_rect.x * 2, icon_rect.y * 2)))

    # ---- scanner: minimapa e mapa grande (Marco 3) -------------------------------------
    MINIMAP_SIZE = 64                                  # px da UI (= C.MINIMAP_TILES tiles a 2 px nativos)

    # Cada marcador tem forma e cor próprias (a legenda usa o mesmo desenho): (forma, cor).
    # Veio não tem cor fixa: o ponto sai na cor do minério (MAP_VEIN_COLORS).
    MAP_MARKERS = {
        "you": ("arrow", "#ffd84a"),          # você: seta amarela piscando, apontando pra onde olha
        "crater": ("ring", "#ffffff"),        # cratera (superfície) / rampa (caverna): anel branco
        "wreck": ("diamond", "#f2a33a"),      # destroço: losango laranja (cinza quando a caixa esvaziou)
        "vein": ("dot", None),                # veio: ponto cheio na cor do minério
        "terminal": ("square", C.C_TERMINAL),  # terminal da caverna: quadrado verde
        "base": ("capsule", C.C_O2),          # base: a cápsula (retângulo 2×1) ciano
    }
    MAP_VEIN_COLORS = {r: C.ORE_COLORS[r][0] for r in C.RESOURCES}
    MAP_WRECK_EMPTY = "#7a6c62"

    @staticmethod
    def draw_marker(surf: pygame.Surface, shape: str, x: int, y: int, m: int, color, direction=(0, 1)) -> None:
        """Um marcador do mapa centrado em (x, y), com contorno preto. `m` = meia-largura base (px nativos)."""
        color = pygame.Color(color)
        black = (0, 0, 0)
        if shape == "arrow":
            dx, dy = direction
            px, py = -dy, dx                                       # perpendicular
            r = m + 2
            tip = (x + dx * r, y + dy * r)
            left = (x - dx * r + px * r, y - dy * r + py * r)
            right = (x - dx * r - px * r, y - dy * r - py * r)
            back = (x - dx * (r - 2), y - dy * (r - 2))
            pts = [tip, left, back, right]
            grow = (r + 1.5) / r                                   # contorno: a mesma seta, um pouco maior
            pygame.draw.polygon(surf, black, [(x + (a - x) * grow, y + (b - y) * grow) for a, b in pts])
            pygame.draw.polygon(surf, color, pts)
        elif shape == "ring":
            r = m + 3
            pygame.draw.circle(surf, black, (x, y), r + 1, 4)
            pygame.draw.circle(surf, color, (x, y), r, 2)
        elif shape == "diamond":
            r = m + 2
            pygame.draw.polygon(surf, black, [(x, y - r - 1), (x + r + 1, y), (x, y + r + 1), (x - r - 1, y)])
            pygame.draw.polygon(surf, color, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)])
        elif shape == "dot":
            pygame.draw.circle(surf, black, (x, y), m + 1)
            pygame.draw.circle(surf, color, (x, y), m)
        elif shape == "square":
            pygame.draw.rect(surf, black, (x - m, y - m, 2 * m, 2 * m))
            pygame.draw.rect(surf, color, (x - m + 1, y - m + 1, 2 * m - 2, 2 * m - 2))
        elif shape == "capsule":
            w, h = 2 * m + 2, m + 2
            pygame.draw.rect(surf, black, (x - w // 2 - 1, y - h // 2 - 1, w + 2, h + 2))
            pygame.draw.rect(surf, color, (x - w // 2, y - h // 2, w, h))

    def _map_markers(self, surf: pygame.Surface, state: GameState, origin, k: int, t: float) -> None:
        """Marcadores por cima da textura já esticada (`k` px por tile, `origin` = tile do canto)."""
        ox, oy = origin
        world = state.world
        explored = state.active.explored
        mk = self.MAP_MARKERS

        def at(tx, ty):
            return round((tx - ox) * k), round((ty - oy) * k)

        m = max(2, k)
        if state.active.has_base:                                   # base: a cápsula
            x, y = at(C.POD_TILES[0][0] + 1, C.POD_TILES[0][1] + 0.5)
            self.draw_marker(surf, "capsule", x, y, m, mk["base"][1])
        if world.crater is not None:                                # cratera / rampa
            x, y = at(world.crater[0] + 1.5, world.crater[1] + 1.5)
            self.draw_marker(surf, "ring", x, y, max(m, round(1.5 * k)), mk["crater"][1])
        for v in world.veins:                                       # veios vistos
            if any(explored.seen(*tt) for tt in v.tiles):
                x, y = at(v.tx + 1, v.ty + 1)
                self.draw_marker(surf, "dot", x, y, m + 1, self.MAP_VEIN_COLORS[v.resource])
        for wreck in world.wrecks:                                  # destroços vistos
            if any(explored.seen(*tt) for tt in wreck.tiles):
                x, y = at(*wreck.center)
                crate = state.crates.get(wreck.crate)
                empty = crate is not None and crate.empty
                self.draw_marker(surf, "diamond", x, y, m, self.MAP_WRECK_EMPTY if empty else mk["wreck"][1])
        for tx, ty in world.terminals:                              # terminais da caverna vistos
            if explored.seen(tx, ty) or explored.seen(tx, ty + 1):
                x, y = at(tx + 0.5, ty + 0.5)
                self.draw_marker(surf, "square", x, y, m, mk["terminal"][1])
        p = state.player                                            # você: seta amarela piscando
        x, y = at(p.x / C.TILE, (p.y - 8) / C.TILE)
        d = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[p.direction]
        bright = (t * 3) % 2 < 1.4
        self.draw_marker(surf, "arrow", x, y, m if bright else m - 1, mk["you"][1] if bright else "#b89a2e", d)

    def map_legend(self, state: GameState) -> list[tuple[str, str]]:
        """Itens da legenda do mapa da camada ativa: (marcador, rótulo). Só o que existe na camada."""
        world = state.world
        items = [("base", "BASE")] if state.active.has_base else []
        if world.crater is not None:
            items.append(("crater", "CRATERA" if state.active.has_base else "RAMPA"))
        if world.wrecks:
            items.append(("wreck", "DESTROÇO"))
        if world.terminals:
            items.append(("terminal", "TERMINAL"))
        if world.veins:
            items.append(("vein", "VEIO"))
        items.append(("you", "VOCÊ"))
        return items

    def draw_minimap(self, state: GameState, tex: pygame.Surface, t: float) -> None:
        """Minimapa no canto direito, embaixo do medidor de energia: 64×64 tiles em volta do player."""
        size = self.MINIMAP_SIZE
        n = C.MINIMAP_TILES
        k = size * 2 // n                                            # px nativos por tile
        w, h = tex.get_size()
        ptx, pty = state.player.tile
        ox = max(0, min(w - n, ptx - n // 2))
        oy = max(0, min(h - n, pty - n // 2))
        view = pygame.transform.scale_by(tex.subsurface((ox, oy, min(n, w), min(n, h))), k)
        self._map_markers(view, state, (ox, oy), k, t)
        px = self.w - 6 - (size + 8)
        py = self.energy_bottom + 4
        self.hud_panel(px, py, size + 8, size + 17)
        self.right_bottom = py + size + 17
        self.text("MAPA", px + 4, py + 4, C.C_TERMINAL)
        self.text("[M]", px + size + 4, py + 4, C.C_MUTED, align="right")
        self.surf.fill((0, 0, 0), (px + 3, py + 12, size + 2, size + 2))
        self.native.append((view, ((px + 4) * 2, (py + 13) * 2)))

    def draw_map(self, state: GameState, tex: pygame.Surface, t: float) -> None:
        """Mapa grande (M): a camada inteira, preto onde não foi visto, com legenda."""
        self.fill((4, 6, 8, 200), (0, 0, self.w, self.h))
        w, h = tex.get_size()
        k = max(1, min((self.w * 2 - 48) // w, (self.h * 2 - 96) // h))   # px nativos por tile (inteiro)
        mw, mh = w * k // 2, h * k // 2                                      # tamanho do mapa em px da UI
        # legenda: o mesmo desenho dos marcadores (veio: os 3 minérios). Mede antes pra janela caber tudo.
        legend = []
        for kind, label in self.map_legend(state):
            shape, color = self.MAP_MARKERS[kind]
            colors = list(self.MAP_VEIN_COLORS.values()) if kind == "vein" else [color]
            icon = pygame.Surface((8 * len(colors) + 6, 16), pygame.SRCALPHA)
            for i, c in enumerate(colors):
                self.draw_marker(icon, shape, 7 + 8 * i, 8, 3 if kind != "vein" else 2, c, (1, 0))
            legend.append((icon, label))
        legend_w = sum(icon.get_width() // 2 + 2 + self.font.size(label)[0] + 8 for icon, label in legend)
        close_w = self.font.size("[M] FECHA")[0]
        pw, ph = min(self.w - 4, max(mw + 16, 300, legend_w + close_w + 20)), mh + 50
        x, y = (self.w - pw) // 2, (self.h - ph) // 2
        self.header_rects.clear()
        self._window(x, y, pw, ph, "MAPA · " + ("SUPERFÍCIE" if state.active.has_base else "CAVERNA"), C.C_TERMINAL)
        explored = state.active.explored
        pct = 100 * explored.count / (w * h)
        self.text(f"EXPLORADO {pct:.0f}%", x + pw - 8, y + 6, C.C_MUTED, align="right")
        mx, my = x + (pw - mw) // 2, y + 22
        self.surf.fill((0, 0, 0), (mx - 1, my - 1, mw + 2, mh + 2))
        view = pygame.transform.scale_by(tex, k)
        self._map_markers(view, state, (0, 0), k, t)
        self.native.append((view, (mx * 2, my * 2)))
        ly = my + mh + 6
        lx = x + 8
        for icon, label in legend:
            self.native.append((icon, (lx * 2, ly * 2 - 1)))
            iw = icon.get_width() // 2
            lx += iw + 2 + self.text(label, lx + iw + 2, ly, C.C_MUTED) + 8
        self.text("[M] FECHA", x + pw - 8, ly, C.C_TEXT, align="right")

    # ---- cursor ---------------------------------------------------------------
    def draw_cursor(self, x: float, y: float) -> None:
        pts = [(x, y), (x, y + 9), (x + 2, y + 7), (x + 4, y + 11), (x + 5, y + 10), (x + 4, y + 6), (x + 7, y + 6)]
        pygame.draw.polygon(self.surf, (255, 255, 255), pts)
        pygame.draw.polygon(self.surf, (0, 0, 0), pts, 1)
