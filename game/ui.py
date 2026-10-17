"""Interface: HUD, fabricador, inventários, pausa, mapa, terminal, banner de estágio, O₂ crítico e fim.

Estilo B2 (redesign aprovado pelo dono, reports/design/ui_redesign/): cartões escuros e planos com o
pixel de cada canto cortado (round_rect), cor como informação (laranja = ação/seleção, verde = tem,
vermelho = falta), abas com ícone, ajuda em pares "tecla em caixinha + texto" (help_line). As
coordenadas saem de tools/sprites/ui_mockups.py (px da UI no tamanho Grande).

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
import random
import re

import pygame

from game import art
from game import config as C
from game import dust
from game import energy
from game import map_markers
from game import map_view
from game.assets import Sprites, load_font
from game.floaters import LANE_PX, RISE, FloatingTexts, dodge_labels, hud_fade  # noqa: F401 (FloatingTexts: app)
from game.inventory import Inventory, Stack, max_stack
from game.systems import GameState, dispenser_capsule_time, eta_label, stage_progress
from game.wrecks import Crate

UW, UH = C.UI_W, C.UI_H           # tamanho da UI no Grande (e o mínimo em qualquer tamanho)
TI_PANEL_W = 150                 # painel do Ti (em cima à direita, encostado na borda: ti_panel_x)
# inventário e hotbar (coordenadas da UI): slot de 20×20 com 2 de vão
SLOT, SLOT_GAP = 20, 2
SLOT_STEP = SLOT + SLOT_GAP
GRID_W = 8 * SLOT_STEP - SLOT_GAP                # 8 colunas = 174
# seção "DRONES" dos painéis de baú e drill (draw_logistics): Envia, Recebe e Lote
LOGI_ROW = 25                                    # passo entre as linhas Envia / Recebe
LOGI_BTN = 22                                    # botão de drone: o ícone do material é o botão (22×22)
LOGI_BATCH_H = 16                                # botões do lote: 1 / 5 / 10 / 20 (22×16)
SMELT_COLOR = "#ff8a3d"                                # laranja da Fundição (o do aquecedor)
SHORT_NAME = {"water_capsule": "cápsula"}          # só no resumo do título da seção DRONES (C.RESOURCE_NAME fica como está)
LOGI_COL = 52                                    # onde começam os botões (depois de "Recebe")
SMELT_LOGI_Y = 102                               # ...e nela, a da Fundição (3 slots, barra, carga e ajuda em cima)
COLLECT_LOGI_Y = 92                              # v0.8 M2: ...e a do Coletor de água (2 slots, barra, estado e o ritmo)
CULT_LOGI_Y = 152                                # v0.8 M3: ...e a do Cultivador (barras, cilindro, colheita e a fileira dos slots)
MIC_LOGI_Y = 156                                 # v0.8 M4: ...a do Microscópio (mock A: máquina, faixa de chances, estado)
CENT_LOGI_Y = 152                                # v0.8 M4: ...e a da Centrífuga (mock A: máquina, cartão da amostra, estado)
DISP_LOGI_Y = 92                                 # onde a seção DRONES começa nos painéis da drill, derretedor e dispersor
LOGI_H = 14 + 2 * LOGI_ROW + 2 + LOGI_BATCH_H    # altura da seção com Envia e Recebe, 1 linha de botões cada (82)
LOGI_WIDE_AFTER = 5                              # com mais materiais que isso (o baú tem 8), a fileira vira "larga":
LOGI_WIDE_BTN, LOGI_WIDE_GAP = 16, 1             # o rótulo (Envia/Recebe) sobe pra uma linha própria e os botões
LOGI_WIDE_ROW = 9 + LOGI_WIDE_BTN + 2            # (16×16, o ícone justo) ficam 10 por linha: 10 × 16 + 9 × 1 = 169 ≤ GRID_W
LOGI_WIDE_COLS = 10                              # v0.8 M5: 16 materiais no baú = 2 linhas por fileira (10 + 6); eram 4 de 20×20


def wide_label_inline(n: int) -> bool:
    """A última linha da fileira larga é curta (o baú: 6 de 10)? Então o rótulo (Envia/Recebe) vai no vão à direita
    dela, em vez de gastar uma linha própria em cima. Precisa de 48 px livres ("Recebe" tem 41)."""
    last = n % LOGI_WIDE_COLS or LOGI_WIDE_COLS
    return GRID_W - last * (LOGI_WIDE_BTN + LOGI_WIDE_GAP) >= 48


def wide_row_height(n: int) -> int:
    """Altura de uma fileira larga (botões 16×16 em linhas de 10; rótulo em cima, ou no vão da última linha) com `n`."""
    lines = -(-n // LOGI_WIDE_COLS)
    return (0 if wide_label_inline(n) else 9) + lines * (LOGI_WIDE_BTN + 2)


def logi_row_cap(machine) -> int:
    """Quantos botões cabem numa fileira normal (não larga) da seção DRONES: com chip, o slot dele ocupa a ponta
    direita (o Cultivador manda 5 itens: o 5º ficava debaixo do chip), então a fileira quebra antes."""
    room = GRID_W - LOGI_COL - (SLOT + 4 if machine.needs_chip else 0)
    return max(1, (room + 3) // (LOGI_BTN + 3))
# painéis lado a lado (baú, drill, estação, caixa): inventário | botões do meio | o outro lado
HELP_CURSOR = [("CLIQUE", "pega/solta"), ("DIR", "metade/1"), ("SHIFT+CLIQUE", "manda direto"), ("ESC", "fecha")]
SIDE_W = GRID_W + 16                             # 8 de margem dos dois lados da grade
SIDE_MID = 58                                    # coluna do meio: "GUARDAR RECURSOS >>" / "<< PEGAR TUDO"
SIDE_GRID_Y = 26                                 # grade do lado (abaixo do título e do rótulo "BAÚ")
SIDE_INV_H = 84                                  # janela "Inventário" do lado esquerdo (mochila + hotbar)
# abas do Tab (Inventário / Fabricar / LOGs): controle segmentado embaixo do título
INV_TABS_Y = 20                                  # y das abas dentro da janela
INV_TABS_H = 15
INV_CONTENT_Y = 40                               # onde começa o conteúdo das 3 abas
TAB_INVENTORY, TAB_LOGS = range(2)               # índices das abas do Tab (a Fabricar saiu no v0.5 M1)
# v0.8 M5 · Tab A (mock reports/design/v08_m5_itens/tab_A.png): 3 colunas, grades | TRAJE | detalhe
TAB_SUIT_W = 96                                  # coluna do TRAJE: o Explorador em cima e os 4 slots em 2×2
TAB_DETAIL_W = 142                               # coluna do detalhe do item ("USADO EM")
TAB_COL_GAP = 8                                  # vão entre as colunas
TAB_INV_W = 10 + GRID_W + TAB_COL_GAP + TAB_SUIT_W + TAB_COL_GAP + TAB_DETAIL_W + 8   # 446
BACKPACK_ROW_H = 32                              # cada linha da mochila: rótulo/vão (10) + slots (20) + vão (2)
TAB_INV_H = INV_CONTENT_Y + 4 * BACKPACK_ROW_H - 2 + 8   # 174: a mesma com ou sem mochila (o TRAJE manda)
TAB_BARE_H = 104                                 # sem traje (fora do Tab): só as grades e o detalhe
SUIT_ROW_Y = (44, 85)                            # linhas dos slots do TRAJE, do topo do cartão
SUIT_CELL_W = (TAB_SUIT_W - 4) // 2              # 46: cada slot centrado na sua célula


def backpack_extra(slots: int) -> int:
    """Altura que a mochila põe nas grades: BACKPACK_ROW_H por linha (1 com a nv.1, 2 com a T2 de 32 slots)."""
    rows = -(-max(0, slots - 2 * C.HOTBAR_SLOTS) // C.HOTBAR_SLOTS)
    return BACKPACK_ROW_H * rows


def backpack_label(slots: int) -> str:
    """Rótulo da grade da mochila: "MOCHILA T2" com as 2 linhas da T2, "MOCHILA" com a nv.1."""
    return "MOCHILA T2" if slots > C.INVENTORY_SLOTS + C.BACKPACK_SLOTS else "MOCHILA"


FAB_W, FAB_H, FAB_LIST_W = 456, 258, 176         # fabricador da base
RECIPE_ROW_H, RECIPE_ROW_STEP = 22, 24           # linha da lista de receitas
RECIPE_PEEK_H = RECIPE_ROW_H // 2                 # v0.6 Fundo M5: a meia linha que avisa que a lista rola
LOG_ROW_H, LOG_ROW_STEP = 15, 16                 # linha da aba LOGs e o passo entre elas
HELP_H = 18                                      # linha de ajuda embaixo das janelas (7 de vão + tecla de 11)

# ---- paleta da direção B (mockup) ------------------------------------------------------------
B_HUD = (15, 17, 25, 236)        # cartão do HUD por cima do mundo
B_WINDOW = (15, 17, 25, 246)     # janela (inventário, fabricador, pausa, mapa)
B_CARD = "#141722"               # cartão dentro de janela
B_CARD2 = "#1b1f2c"              # botão neutro, caixinha de tecla
B_HOVER = "#232838"              # linha/aba ativa ou com o mouse
B_LINE = "#2b3145"               # borda e divisória
B_LINE2 = "#3a4259"              # borda mais clara (botão, tecla, tooltip, linhas do traje)
B_TEXT = "#eef0f6"
B_MUTED = "#8b93a8"
B_DIM = "#4f566b"
B_WELL = "#0d0f16"               # fundo afundado (prévia, controle segmentado, botão apagado)
B_DEEP = "#0b0d13"               # faixa do número do Ti, sombra do Explorador
B_TRACK = "#262b3b"              # trilho das barras
B_SLOT_OUT, B_SLOT_IN, B_SLOT_LIGHT = "#0c0e15", "#181c28", "#22273a"
B_DARK_TEXT = "#1b1411"          # texto em cima do laranja
B_SCREEN_DIM = (8, 5, 4, 130)    # escurece o mundo atrás das janelas
LAB_OK = "#7fd67a"               # v0.8 M4: o verde de "trabalhando" (barra e estado do Microscópio/Centrífuga)
SAMPLE_SHORT = {"sample_basic": "SIMPLES", "sample_mutant": "MUTAÇÃO", "sample_rare": "RARA"}   # a legenda curta (mock A)
SAMPLE_COLOR = {"sample_basic": "#7fd6b0", "sample_mutant": "#5f7ee0", "sample_rare": "#f2c46d"}   # a cor de cada amostra (do ícone)
OK_TEXT, ALERT_TEXT = "#b6f0b0", "#ff8a7a"
OK_BG, OK_BORDER = (127, 214, 122, 18), "#2f4a33"
BAD_BG, BAD_BORDER = (255, 106, 85, 30), "#6a302b"
# ícone de cada aba do fabricador (só a ativa mostra o nome: cabe nos 3 tamanhos)
FAB_TAB_ICON = {"t2": "workbench", "tools": "constructor", "terraform": "o2", "energy": "solar", "automation": "drill", "storage": "chest", "light": "lamp",
                "suit": "o2_tank", "base": "tab_base", "decor": "prop_table"}


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

# Marcas desenhadas em pixels (a fonte não tem o glifo): o "✓" do "Vedado ✓" do Dispersor (v0.5 M2). 5×5, no tamanho
# das maiúsculas, 1 px de margem à direita.
MARKS = {"✓": ["    #", "   # ", "#  # ", " ##  ", "  #  "]}
MARK_ADVANCE = 7


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
        if ch in MARKS:
            return "mark"
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
        if kind == "mark":
            return MARK_ADVANCE * len(run)
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
                elif kind == "mark":
                    glyph, top, s = MARKS[ch], self.digit_top + 1, 1
                    ox = x + 1
                else:
                    glyph, top, s = SUBSCRIPTS[ch][self.sub_rows], self.sub_top, self.sub_scale
                    ox = x
                for dy, row in enumerate(glyph):
                    for dx, cell in enumerate(row):
                        if cell == "#":
                            surf.fill(color, (ox + dx * s, top + dy * s, s, s))
                x += DIGIT_ADVANCE if kind == "digit" else MARK_ADVANCE if kind == "mark" else self.sub_advance
        return surf


# ---- chiado do scanner na tempestade (v0.4 Marco 1, trilha C) -------------------------------------
NOISE_TILE = 64            # ladrilho de ruído (px nativos), repetido com deslocamento sorteado
NOISE_LEVELS = 8           # densidades em cache (amount quantizado)
NOISE_FRAMES = 4           # quadros de ruído por densidade (alterna rápido: cara de TV fora do ar)
NOISE_FPS = 24
NOISE_DENSITY = 0.22       # fração de pixels com ruído no amount 1
NOISE_LIGHT, NOISE_DARK = (226, 222, 210), (14, 16, 22)
NOISE_LINE = (64, 60, 52)  # somado (BLEND_RGB_ADD) nas linhas de interferência
# v0.5 M3.7: na faixa gelada o chiado fica branco-azulado (mesmos 3 tons, interpolados pelo fator de neve)
NOISE_LIGHT_SNOW, NOISE_DARK_SNOW, NOISE_LINE_SNOW = (244, 249, 252), (18, 26, 40), (56, 66, 82)
NOISE_SNOW_STEPS = 4       # degraus de cor do chiado em cache
_noise_tiles: dict[tuple[int, int], pygame.Surface] = {}


def _noise_tile(level: int, frame: int, snow_step: int = 0) -> pygame.Surface:
    tile = _noise_tiles.get((level, frame, snow_step))
    if tile is None:
        k = snow_step / NOISE_SNOW_STEPS
        light = tuple(round(a + (b - a) * k) for a, b in zip(NOISE_LIGHT, NOISE_LIGHT_SNOW))
        dark = tuple(round(a + (b - a) * k) for a, b in zip(NOISE_DARK, NOISE_DARK_SNOW))
        rng = random.Random(level * 131 + frame * 17 + 5)
        tile = pygame.Surface((NOISE_TILE, NOISE_TILE), pygame.SRCALPHA)
        tile.fill((0, 0, 0, 0))
        for _ in range(round(NOISE_TILE * NOISE_TILE * NOISE_DENSITY * level / NOISE_LEVELS)):
            rgb = light if rng.random() < 0.5 else dark
            tile.set_at((rng.randrange(NOISE_TILE), rng.randrange(NOISE_TILE)), (*rgb, rng.randrange(150, 256)))
        _noise_tiles[(level, frame, snow_step)] = tile
    return tile


def static_noise(surf: pygame.Surface, amount: float, t: float, snow: float = 0.0) -> None:
    """Chiado no minimapa/mapa (in-place): pixels claros e escuros sorteados mais 1 ou 2 linhas de
    interferência, proporcional a `amount` (0..1, rajada × tempestade). Com amount 0 não toca em nada.
    `snow` (0..1, dust.snow_of) esfria o chiado: mais branco-azulado na faixa gelada.
    Ruído em ladrilhos pré-sorteados: custa uns blits, não um laço por pixel."""
    if amount <= 0:
        return
    amount = min(1.0, amount)
    level = max(1, math.ceil(amount * NOISE_LEVELS))
    tick = int(t * NOISE_FPS)
    sk = round(max(0.0, min(1.0, snow)) * NOISE_SNOW_STEPS)
    tile = _noise_tile(level, tick % NOISE_FRAMES, sk)
    rng = random.Random(tick)
    ox, oy = rng.randrange(NOISE_TILE), rng.randrange(NOISE_TILE)
    w, h = surf.get_size()
    for y in range(-oy, h, NOISE_TILE):
        for x in range(-ox, w, NOISE_TILE):
            surf.blit(tile, (x, y))
    k = max(1, h // 64)                                   # espessura da linha: 1 px a cada 64 de altura
    for i in range(1 + (amount > 0.5)):
        y = int((t * (41 + 29 * i) * k + rng.random() * h) % h)
        line = tuple(round((a + (b - a) * sk / NOISE_SNOW_STEPS) * amount) for a, b in zip(NOISE_LINE, NOISE_LINE_SNOW))
        surf.fill(line, (0, y, w, k), special_flags=pygame.BLEND_RGB_ADD)


def unlock_text(kind: str) -> str:
    """Texto do "locked" de uma receita: o estágio (se ela trava por estágio) ou o Ti."""
    m = C.MACHINES[kind]
    if m.unlock_stage > 0:
        return f"LIBERA NO ESTÁGIO {C.STAGES[m.unlock_stage - 1].name}"
    return f"LIBERA EM TI {fmt(m.unlock_ti)}"


def fmt(n: float) -> str:
    """12400 -> '12.400' (separador de milhar brasileiro)."""
    return f"{round(n):,}".replace(",", ".")


def next_stage_line(nxt, remaining_ti: float, remaining_bio: float, eta: str) -> str:
    """Linha de baixo do "próximo estágio" (v0.8 M1): o que falta, Ti e/ou biomassa. Só biomassa não tem estimativa."""
    if remaining_bio > 0 and remaining_ti <= 0:
        return f"falta biomassa {fmt(remaining_bio)}"
    if remaining_bio > 0:
        return f"faltam {fmt(remaining_ti)} · biomassa {fmt(remaining_bio)}"
    return f"faltam {fmt(remaining_ti)} · {eta}"


def fmt_rate(n: float) -> str:
    return (f"{n:.1f}".replace(".", ",") if n % 1 else str(int(n)))


def zoom_label(zoom: float) -> str:
    """1.5 -> '1,5×' (o mesmo texto do aviso de zoom)."""
    return f"{zoom:g}".replace(".", ",") + "×"


def bench_short(bench: str) -> str:
    """"t2" -> "T2" (o botão apagado do diagrama que se lê em outra bancada)."""
    return bench.upper()


def item_name(item: str) -> str:
    """Nome de um item do inventário pra mostrar ao jogador ('Ferro', 'Gerador de O₂', 'Baú')."""
    if item in C.RESOURCE_NAME:
        return C.RESOURCE_NAME[item].capitalize()
    if item in C.DIAGRAM_ITEMS:
        return f"Diagrama: {C.BLUEPRINTS[C.DIAGRAM_ITEMS[item]]}"
    return C.MACHINES[item].name


def submerged_notice(kinds: list[str]) -> str:
    """v0.4 M3.4: aviso de máquina que o lago cobriu. Uma: "Aquecedor submerso · segure [Clique direito]" (concorda
    com o nome); várias juntas: "3 máquinas submersas · segure [Clique direito]" (v0.5 M1: desmontar é segurar)."""
    if len(kinds) == 1:
        word = "submersa" if kinds[0] in C.MACHINE_FEMININE else "submerso"
        return f"{item_name(kinds[0])} {word} · segure [{C.DISMANTLE_KEY}]"
    return f"{len(kinds)} máquinas submersas · segure [{C.DISMANTLE_KEY}]"


def used_in(item: str) -> list[str]:
    """"USADO EM": as receitas que gastam `item` (busca reversa nos custos), na ordem do MACHINE_ORDER."""
    return [k for k in C.MACHINE_ORDER if item in C.MACHINES[k].cost]


def item_category(item: str) -> tuple[str, str]:
    """(rótulo, cor) da categoria do item no painel de detalhe do inventário."""
    if item in C.RESOURCES:
        return "RECURSO", C.C_O2
    if item in C.DIAGRAM_ITEMS:
        return "DIAGRAMA", "#9fd0ff"
    if item in C.EQUIP_SLOT_OF:                   # v0.8 M5: o nv.2 e as botas também
        return "TRAJE", C.C_TERMINAL
    if item in ("drone", C.DRONE_T2, "constructor"):
        return "ITEM", C.C_TI
    if item in C.HAND_DRILLS:
        return "FERRAMENTA", C.C_TI
    if item in C.PART_ITEMS:
        return "PEÇA", C.C_TERMINAL
    return "MÁQUINA", C.C_ACCENT


def gust_warning(state) -> bool:
    """Mostra o aviso RAJADA? Só enquanto a rajada está forte (some quando ela baixa)."""
    weather = getattr(state, "weather", None)
    return weather is not None and weather.gust > C.STORM_GUST_WARN


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


KEY_RE = re.compile(r"\[([^\]]+)\]")


def key_parts(text: str) -> list[tuple[str, str]]:
    """'[E] Abrir baú · [Shift+E] coletar' -> [('key','E'), ('text','Abrir baú ·'), ('key','Shift+E'),
    ('text','coletar')]: as teclas entre colchetes viram caixinhas (help_line, dica do E)."""
    parts = []
    pos = 0
    for m in KEY_RE.finditer(text):
        before = text[pos:m.start()].strip()
        if before:
            parts.append(("text", before))
        parts.append(("key", m.group(1)))
        pos = m.end()
    rest = text[pos:].strip()
    if rest:
        parts.append(("text", rest))
    return parts


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
        self.left_bottom = 23                    # fundo da coluna da esquerda do HUD (O₂ e objetivo), px da UI
        self.gust_rect: pygame.Rect | None = None   # aviso RAJADA deste frame (tempestade)
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
        self._icon_cache: dict[tuple, pygame.Surface] = {}
        self._explorer: pygame.Surface | None = None
        self._blank = pygame.Surface((32, 32), pygame.SRCALPHA)
        # fabricador e aba Fabricar (lista + detalhe): retângulos clicáveis (coord. da UI)
        self.fabricator_buttons: list[tuple[pygame.Rect, str]] = []   # FABRICAR (só da receita escolhida, se dá)
        self.fabricator_rows: list[tuple[pygame.Rect, str]] = []
        self.fabricator_tabs: list[tuple[pygame.Rect, int]] = []      # abas: (retângulo, índice da aba)
        self.fabricator_batch: list[tuple[pygame.Rect, int]] = []     # seletor do lote: (retângulo, 1 ou 5)
        self.diagram_buttons: list[tuple[pygame.Rect, str]] = []      # LER (só dos que a bancada lê): (retângulo, id)
        self.diagram_rows: list[tuple[pygame.Rect, str]] = []         # linhas da área "Diagramas"
        self.fabricator_panel: pygame.Rect | None = None              # janela do fabricador (a última desenhada)
        self.craft_label = ""                                          # o que o botão principal diz ("FALTAM 2 SILÍCIO")
        self.pause_items: list[pygame.Rect] = []      # linhas clicáveis do menu de pausa (coord. da UI)
        self.pause_sliders: list[pygame.Rect] = []    # barras dos sliders de volume
        # Opções: segmentos dos controles (retângulo, (índice da linha, valor)): Não|Sim, zoom e interface
        self.pause_segments: list[tuple[pygame.Rect, tuple[int, object]]] = []
        self.pause_page_buttons: list[tuple[pygame.Rect, int]] = []   # Controles: "<" (-1) e ">" (+1)
        self.controls_pages = 1                       # quantas páginas a tela de Controles teve no último desenho
        self.help_rect: pygame.Rect | None = None     # a última linha de ajuda desenhada (help_line)
        # slots clicáveis da tela de inventário/baú: (retângulo na UI, inventário, índice do slot)
        self.slot_rects: list[tuple[pygame.Rect, Inventory, int]] = []
        # títulos de janela, abas e rótulos de seção dos painéis com slots: o tooltip nunca cobre (tooltip_rect)
        self.header_rects: list[pygame.Rect] = []
        # painel da estação: slots de drone (retângulo, nº do slot) e do buffer (retângulo, minério)
        self.bay_rects: list[tuple[pygame.Rect, int]] = []
        self.buffer_rects: list[tuple[pygame.Rect, str]] = []
        self.panel_buttons: list[tuple[pygame.Rect, str]] = []   # "take_all", "store_all", "take_buffer"...
        self.name_rect: pygame.Rect | None = None                 # nome do baú (clique = editar)
        self.notice_y = self.hotbar_y - 58                            # altura do aviso nos painéis (draw_inventory)
        # seção DRONES do baú/drill: (retângulo, ("send"|"recv", item) ou ("batch", n))
        self.logistics_buttons: list[tuple[pygame.Rect, tuple[str, object]]] = []
        self.chip_rects: list[tuple[pygame.Rect, object]] = []   # v0.6 M2: slot do chip de cada máquina aberta
        self.equip_rects: list[tuple[pygame.Rect, str]] = []      # slots de equipamento (Tab): (retângulo, tipo)
        # v0.8 M5 Tab A: a janela "Inventário" (Tab ou painel lateral), as colunas do TRAJE e do detalhe, e a caixa
        # da tinta de cada texto do cartão do TRAJE (rótulos e estados), pros testes de "não encosta"
        self.inv_window = pygame.Rect(0, 0, 0, 0)
        self.suit_rect = pygame.Rect(0, 0, 0, 0)
        self.detail_rect = pygame.Rect(0, 0, 0, 0)
        self.suit_text_rects: list[tuple[str, pygame.Rect]] = []
        self.inv_tab_rects: list[tuple[pygame.Rect, int]] = []    # abas do Tab: (retângulo, TAB_INVENTORY/CRAFT/LOGS)
        self.detail_item: str | None = None                        # item do painel de detalhe do Tab (último desenho)
        self.detail_uses: list[str] = []                           # receitas listadas em "USADO EM" (último desenho)
        self.log_rows: list[tuple[pygame.Rect, int]] = []         # aba LOGs: linhas clicáveis (retângulo, índice em LOGS)
        self.log_visible = len(C.LOGS)                             # quantas linhas da aba LOGs couberam no último desenho
        self.energy_bottom = 110                                   # onde acaba o medidor de energia (minimapa embaixo)
        self.right_bottom = 110                                    # onde acaba a coluna da direita ("Jogo salvo" embaixo)
        # mapa grande (M): janela, botão FECHAR e marcadores com nome (tooltip)
        self.map_rect: pygame.Rect | None = None
        self.map_close_rect: pygame.Rect | None = None
        self.map_area: pygame.Rect | None = None                   # área de desenho (zoom, arrasto, marcadores)
        self.map_markers: list = []                                # (retângulo, map_view.Entry) de cada marcador
        self.map_layer_rects: list[tuple[pygame.Rect, str]] = []   # Superfície | Caverna no cabeçalho
        self.map_buttons: list[tuple[pygame.Rect, str]] = []       # + / − / centralizar
        self.map_chips: list[tuple[pygame.Rect, str]] = []         # filtros embaixo (retângulo, categoria)
        self.map_hover = None                                      # marcador com o mouse (tooltip)
        self.name_pill: pygame.Rect | None = None                  # pílula com o nome do item da hotbar (draw_hotbar)

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

    def window_top(self, h: int) -> int:
        """y de uma janela de altura `h` com a linha de ajuda embaixo: no meio da tela, mas a ajuda nunca
        encosta na moldura da hotbar (hotbar_y - 11); se não couber, gruda no topo."""
        return max(4, min((self.h - h) // 2 - 8, self.hotbar_y - 11 - 1 - HELP_H - h))

    @property
    def window_room(self) -> int:
        """Altura máxima de uma janela com ajuda embaixo, sem chegar na hotbar."""
        return self.hotbar_y - 11 - 1 - HELP_H - 4

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
            if len(self._text_cache) > 900:
                self._text_cache.clear()
            text = text.replace("→", ">")   # v0.8 M4: as fontes não têm a seta (saía um quadrado: "minério [] lingote")
            if font in (self.body, self.body_big):
                # A Pixelify Sans junta "fi"/"fl" numa ligadura que fica ilegível em 10 px.
                # Um "zero-width non-joiner" (invisível) entre as letras impede isso.
                text = text.replace("fi", "f‌i").replace("fl", "f‌l")
            surf = font.render(text, False, pygame.Color(color))
            self._text_cache[key] = surf
        return surf

    def text(self, s: str, x: float, y: float, color: str, font=None, align: str = "left", target=None,
             alpha: float = 1.0, shadow: bool = True) -> int:
        """Texto (com sombrinha preta por padrão: o que fica por cima do mundo). Devolve a largura.
        `alpha` < 1: esmaecido. Nos cartões do estilo B o texto é plano (tx)."""
        font = font or self.font
        target = target or self.surf
        img = self._render(font, s, color)
        w = img.get_width()
        x = x - w if align == "right" else x - w // 2 if align == "center" else x
        x, y = int(x), int(y)
        if alpha < 1.0:                  # as imagens do cache são compartilhadas: esmaece uma cópia
            img = img.copy()
            img.set_alpha(round(255 * alpha))
        if shadow:
            shadow_img = self._render(font, s, "#000000")
            if alpha < 1.0:
                shadow_img = shadow_img.copy()
            shadow_img.set_alpha(round(165 * alpha))
            target.blit(shadow_img, (x + 1, y + 1))
        target.blit(img, (x, y))
        return w

    def tx(self, s: str, x: float, y: float, color: str, font=None, align: str = "left", target=None) -> int:
        """Texto plano (sem sombra), o dos cartões do estilo B."""
        return self.text(s, x, y, color, font, align, target, shadow=False)

    def fill(self, rgba, rect, target=None) -> None:
        """Retângulo com transparência que MISTURA com o que já está embaixo."""
        target = target or self.surf
        rect = pygame.Rect(rect)
        if rect.w <= 0 or rect.h <= 0:
            return
        color = rgba if isinstance(rgba, pygame.Color) else pygame.Color(rgba)
        if color.a == 255:
            target.fill(color, rect)
            return
        if color.a == 0:
            return
        key = (rect.w, rect.h)
        tmp = self._tmp.get(key)
        if tmp is None:
            tmp = self._tmp[key] = pygame.Surface(key, pygame.SRCALPHA)
        tmp.fill(color)
        target.blit(tmp, rect.topleft)

    def round_rect(self, rect, color, border=None, target=None) -> None:
        """Retângulo com o pixel de cada canto cortado (o "arredondado" da pixel art), com borda opcional."""
        x, y, w, h = pygame.Rect(rect)
        if w < 3 or h < 3:
            self.fill(color, (x, y, w, h), target)
            return
        self.fill(color, (x + 1, y, w - 2, h), target)
        self.fill(color, (x, y + 1, 1, h - 2), target)
        self.fill(color, (x + w - 1, y + 1, 1, h - 2), target)
        if border:
            self.fill(border, (x + 1, y, w - 2, 1), target)
            self.fill(border, (x + 1, y + h - 1, w - 2, 1), target)
            self.fill(border, (x, y + 1, 1, h - 2), target)
            self.fill(border, (x + w - 1, y + 1, 1, h - 2), target)

    def card(self, x, y, w, h, bg=B_HUD, border=None, shadow=True, target=None) -> None:
        """Cartão do estilo B: plano, canto de 1 px e uma sombrinha de 1 px embaixo."""
        if shadow:
            self.fill((0, 0, 0, 110), (x + 1, y + h, w - 2, 1), target)
        self.round_rect((x, y, w, h), bg, border, target)

    def panel(self, x, y, w, h, bg=B_HUD, target=None) -> None:
        """Cartão com borda (avisos, rótulo do baú, "Jogo salvo")."""
        self.card(x, y, w, h, bg, B_LINE, shadow=False, target=target)

    def hud_panel(self, x, y, w, h, bg=B_HUD) -> None:
        """Cartão do HUD (O₂, Ti, energia, objetivos, minimapa, hotbar...): guarda o retângulo em hud_rects."""
        self.card(x, y, w, h, bg)
        self.hud_rects.append(pygame.Rect(x, y, w, h))

    def bar(self, x, y, w, frac, color, h=3, track=B_TRACK) -> None:
        """Barra fina do estilo B: trilho + parte cheia com 1 px de brilho em cima."""
        self.fill(track, (x, y, w, h))
        fw = round(w * max(0.0, min(1.0, frac)))
        if fw > 0:
            self.fill(color, (x, y, fw, h))
            if fw > 1:
                c = pygame.Color(color)
                self.fill(c.lerp((255, 255, 255), 0.35), (x, y, fw, 1))

    def segments(self, x, y, n, lit, color, seg_w=4, h=4, off=B_TRACK) -> int:
        """Barra segmentada (próximo estágio no painel do Ti). Devolve a largura."""
        hi = pygame.Color(color).lerp((255, 255, 255), 0.35)
        for i in range(n):
            self.fill(color if i < lit else off, (x + i * (seg_w + 1), y, seg_w, h))
            if i < lit:
                self.fill(hi, (x + i * (seg_w + 1), y, seg_w, 1))
        return n * (seg_w + 1) - 1

    def window(self, x, y, w, h, title: str, right: str | None = None, title_color: str = B_TEXT) -> None:
        """Janela do estilo B: cartão com borda, título em Pixelify e um rótulo à direita. A faixa do
        título entra nos cabeçalhos que o tooltip não cobre."""
        self.card(x, y, w, h, B_WINDOW, B_LINE)
        if title:
            self.tx(title, x + 8, y + 2, title_color, self.body)
        if right:
            self.tx(right, x + w - 8, y + 4, B_MUTED, align="right")
        self.header_rects.append(pygame.Rect(x, y, w, 17))

    def dim_screen(self) -> None:
        self.fill(B_SCREEN_DIM, (0, 0, self.w, self.h))

    def key_cap(self, x: int, y: int, label: str, accent: bool = False, h: int = 11) -> int:
        """Tecla em caixinha ("E", "ESC", "A/D"). Devolve a largura."""
        label = label.upper()
        w = max(11, self.font.size(label)[0] + 6)
        if accent:
            self.round_rect((x, y, w, h), C.C_ACCENT)
        else:
            self.round_rect((x, y, w, h), B_CARD2, B_LINE2)
        self.tx(label, x + w / 2 + 0.5, y - 2 + (h - 11) // 2, B_DARK_TEXT if accent else B_TEXT, align="center")
        return w

    def key_cap_width(self, label: str) -> int:
        return max(11, self.font.size(label.upper())[0] + 6)

    def help_width(self, pairs) -> int:
        return sum(self.key_cap_width(k) + 3 + self.body.size(lab)[0] + 9 for k, lab in pairs) - 9

    def help_line(self, y: int, pairs, center: float | None = None) -> None:
        """Linha de ajuda: pares (tecla, o que faz), centralizada em `center` (meio da tela por padrão)."""
        total = self.help_width(pairs)
        x = int((self.w / 2 if center is None else center) - total / 2)
        x0 = x
        for key, lab in pairs:
            x += self.key_cap(x, y, key) + 3
            x += self.tx(lab, x, y - 2, B_MUTED, self.body) + 9
        self.help_rect = pygame.Rect(x0, y, total, 12)

    def button(self, rect, label: str, kind: str = "primary", hover: bool = False, font=None) -> None:
        """Botão do estilo B: primary (laranja), ghost (neutro), danger (o que falta) ou off (apagado).
        `label` com "\\n" vira várias linhas (os botões do meio do baú)."""
        rect = pygame.Rect(rect)
        font = font or self.font
        x, y, w, h = rect
        if kind == "primary":
            self.round_rect(rect, "#f08a52" if hover else C.C_ACCENT)
            self.fill("#f6b088" if hover else "#f29a62", (x + 1, y, w - 2, 1))
            color = B_DARK_TEXT
        elif kind == "ghost":
            self.round_rect(rect, B_HOVER if hover else B_CARD2, C.C_ACCENT if hover else B_LINE2)
            color = B_TEXT
        elif kind == "danger":
            self.round_rect(rect, BAD_BG, "#7a3a33")
            color = ALERT_TEXT
        else:
            self.round_rect(rect, B_CARD2, B_LINE)
            color = B_DIM
        lines = label.split("\n")
        line_h = 9 if font is self.font else 12
        top = y + (h - (len(lines) * line_h - (line_h - 5 if font is self.font else line_h - 8))) // 2
        for i, line in enumerate(lines):
            ty = top + i * line_h - 4
            self.tx(line, x + w / 2, ty, color, font, align="center")

    def draw_check(self, x: int, y: int, color: str) -> None:
        """Tique ✓ de pixels (7×6)."""
        c = pygame.Color(color)
        for dx, dy in [(0, 3), (1, 4), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (1, 3), (2, 4), (3, 3), (4, 2), (5, 1), (6, 0)]:
            self.surf.fill(c, (x + dx, y + dy, 1, 1))

    def draw_cross(self, x: int, y: int, color: str) -> None:
        """Xis ✗ de pixels (5×5)."""
        c = pygame.Color(color)
        for i in range(5):
            self.surf.fill(c, (x + i, y + i, 1, 1))
            self.surf.fill(c, (x + 4 - i, y + i, 1, 1))

    def draw_lock(self, x: int, y: int, color: str) -> None:
        """Cadeado de pixels (7×8)."""
        c = pygame.Color(color)
        pygame.draw.rect(self.surf, c, (x + 1, y, 5, 4), 1)
        self.surf.fill(c, (x, y + 3, 7, 5))
        self.surf.fill((0, 0, 0), (x + 3, y + 5, 1, 1))

    def draw_bolt(self, x: int, y: int, color: str, shadow: bool = True) -> None:
        """Raio de pixels (5×8): a fonte não tem o "⚡"."""
        rows = ["  ###", " ### ", " ##  ", "#####", "  ## ", " ##  ", " #   ", "#    "]
        c = pygame.Color(color)
        if shadow:
            for dy, row in enumerate(rows):
                for dx, cell in enumerate(row):
                    if cell == "#":
                        self.surf.fill((0, 0, 0), (x + dx + 1, y + dy + 1, 1, 1))
        for dy, row in enumerate(rows):
            for dx, cell in enumerate(row):
                if cell == "#":
                    self.surf.fill(c, (x + dx, y + dy, 1, 1))

    def text_tilde(self, s: str, x: int, y: int, color: str, shadow: bool = True) -> int:
        """Texto da Pixelify com "~" desenhado à mão: em 11 px o til da fonte vira um borrão. Devolve a largura."""
        x0 = x
        parts = s.split("~")
        for i, part in enumerate(parts):
            if i > 0:
                for dx, dy in [(0, 1), (1, 0), (2, 0), (3, 1), (4, 1), (5, 0)]:     # zigue-zague de 6×2
                    if shadow:
                        self.surf.fill((0, 0, 0), (x + dx + 1, y + 6 + dy + 1, 1, 1))
                    self.surf.fill(pygame.Color(color), (x + dx, y + 6 + dy, 1, 1))
                x += 8
            if part:
                x += self.text(part, x, y, color, self.body, shadow=shadow)
        return x - x0

    def tilde_width(self, s: str) -> int:
        parts = s.split("~")
        return sum(self.body.size(p)[0] for p in parts if p) + 8 * (len(parts) - 1)

    # ---- ícones derivados (cache) -------------------------------------------------
    def small_icon(self, item_icon, item: str) -> pygame.Surface:
        """Ícone 16×16 (8 px da UI) a partir do 32×32 do item_icon: o desenho original, pixel a pixel."""
        src = item_icon(item)
        key = ("small", item, id(src), src.get_size())
        if key not in self._icon_cache:
            self._icon_cache[key] = pygame.transform.scale(src, (src.get_width() // 2, src.get_height() // 2))
        return self._icon_cache[key]

    def dark_icon(self, src: pygame.Surface, factor: int = 95) -> pygame.Surface:
        """O mesmo ícone escurecido (só onde tem pixel: o fundo continua transparente)."""
        key = ("dark", id(src), src.get_size(), factor)
        if key not in self._icon_cache:
            img = src.copy()
            img.fill((factor, factor, factor + 10), special_flags=pygame.BLEND_RGB_MULT)
            self._icon_cache[key] = img
        return self._icon_cache[key]

    def explorer_image(self) -> pygame.Surface:
        """O Explorador do cartão do traje: quadro 0 do player_idle_down, 2× (64×64 nativos = 32 px da UI)."""
        if self._explorer is None:
            sheet = Sprites().get("player_idle_down")
            frame = sheet.subsurface((0, 0, 32, 32)).copy() if sheet else art.player("down")
            self._explorer = pygame.transform.scale_by(frame, 2)
        return self._explorer

    # ---- HUD ------------------------------------------------------------------
    def draw_hud(self, state: GameState, t: float, hint: str | None, icons: dict[str, pygame.Surface],
                 item_icon=None) -> None:
        crit = state.o2 < C.O2_LOW
        blink = crit and (t * 9) % 6 < 3
        o2 = min(1.0, state.o2 / state.o2_max)          # proporcional ao máximo (com o tanque, 220 s)
        # ---- O₂: pílula numa linha só (rótulo, barra, segundos ou %, tanque)
        self.hud_panel(6, 6, 132, 17)
        self.tx("O₂", 11, 7, C.C_ALERT if crit else C.C_O2)
        bar = (C.C_ALERT if blink else "#c2281c") if crit else C.C_O2
        self.bar(26, 12, 60, o2, bar, h=4)
        tank = state.equipment.slots.get("o2_tank")     # o nv.1 ou o nv.2 (v0.8 M5)
        value = f"{round(state.o2)}s" if tank else f"{round(o2 * 100)}%"
        self.tx(value, 90, 3, ALERT_TEXT if crit else B_TEXT, self.body)
        if tank and item_icon is not None:           # tanque equipado: a barra vale 220 s
            self.native.append((self.small_icon(item_icon, tank), (124 * 2, 10 * 2)))
        self.left_bottom = 6 + 17                     # fundo da coluna da esquerda (o objetivo empurra pra baixo)

        # painel do Ti e, logo embaixo, o medidor de energia
        self.draw_ti_panel(state)
        self.draw_energy(state)

        if hint:
            self.draw_hint(hint)

        debug = ([f"DEBUG · TEMPO x{state.time_scale}"] if state.time_scale != 1 else []) \
            + ([f"DEBUG · RAPIDO x{C.DEBUG_SPEED:g} · BROCA x{C.DEBUG_MINE:g}", "DEBUG · MAPA REVELADO"]
               if state.fast else []) \
            + (["DEBUG · CRATERA ABERTA (F4)"] if state.debug_crater else [])
        for i, line in enumerate(debug):          # F1, F3 e F4: uma linha cada, no topo (não alcança o painel do Ti)
            self.text(line, self.w // 2, 8 + 10 * i, C.C_TI, align="center")

    def hint_width(self, hint: str) -> int:
        parts = key_parts(hint)
        w = 3
        for kind, value in parts:
            w += (self.key_cap_width(value) if kind == "key" else self.body.size(value)[0]) + 3
        return w + 3

    def draw_hint(self, hint: str) -> None:
        """Dica do canto (o que o E abre, desmontar...) com as teclas em caixinha; a 1ª, laranja."""
        w = self.hint_width(hint)
        x = self.w - 6 - w
        y = self.h - 6 - 15
        hotbar_right = self.hotbar_x + GRID_W + 4
        if x < hotbar_right + 6:                     # comprida: sobe acima da hotbar
            y = self.hotbar_y - 11 - 4 - 15
            # e acima da pílula com o nome do item da hotbar, se chegar nela (a pílula é desenhada depois,
            # no draw_hotbar: vale o lugar dela no frame anterior)
            pill = self.name_pill
            if pill is not None and pill.colliderect((x, y, w, 15)):
                y = pill.top - 4 - 15
        self.hud_panel(x, y, w, 15)
        cx = x + 3
        for i, (kind, value) in enumerate(key_parts(hint)):
            if kind == "key":
                cx += self.key_cap(cx, y + 3, value, accent=i == 0, h=9) + 3
            else:
                cx += self.tx(value, cx, y - 1, B_TEXT, self.body) + 3

    INDEX_NAME = {"water": "ÁGUA"}               # no painel cabe o acento (o floater "+AGUA" segue o config)

    def draw_ti_panel(self, state: GameState) -> None:
        """Painel "ÍNDICE TI" (organização da direção A no cartão da B): +/s, Ti grande numa faixa escura,
        os 4 índices com valor e unidade alinhados à direita e o próximo estágio com barra segmentada,
        % e "faltam X · ~Y"."""
        px, w, y = self.ti_panel_x, TI_PANEL_W, 6
        right = px + w - 6
        nxt, fraction, remaining, remaining_bio = stage_progress(state.ti, state.indices["biomass"])
        eta = eta_label(remaining, state.smoothed_rate)
        line2 = next_stage_line(nxt, remaining, remaining_bio, eta)
        wrap_eta = nxt is not None and " · " in line2 and self.tilde_width(line2) > w - 12   # não coube: o resto desce
        h = 83 if nxt is None else 109 if wrap_eta else 97          # v0.8 M1: +9 px da linha da biomassa
        self.hud_panel(px, y, w, h)
        self.ti_panel_bottom = y + h      # o medidor de energia encaixa logo abaixo (draw_energy)

        self.tx("ÍNDICE TI", px + 6, y - 1, C.C_TI)
        rate = state.ti_rate * state.time_scale
        if rate:
            self.tx(f"+{fmt_rate(rate)}/s", right, y - 3, C.C_OK, self.body, "right")
        self.round_rect((px + 4, y + 12, w - 8, 19), B_DEEP)
        self.tx("TI", px + 9, y + 15, B_DIM)
        self.tx(fmt(state.ti), px + w - 9, y + 11, C.C_TI, self.font_big, "right")
        for i, key in enumerate(("o2", "heat", "water", "biomass")):
            yy = y + 34 + i * 9
            self.fill(C.INDEX_COLOR[key], (px + 6, yy + 1, 3, 3))
            self.tx(self.INDEX_NAME.get(key, C.INDEX_LABEL[key]), px + 13, yy - 4, B_TEXT)
            unit = C.INDEX_UNIT[key].upper()
            uw = self.tx(unit, right, yy - 4, B_DIM, align="right")
            self.tx(fmt(state.indices[key]), right - uw - 3, yy - 4, B_TEXT, align="right")

        # ---- próximo estágio
        self.fill(B_LINE, (px + 6, y + 71, w - 12, 1))
        if nxt is None:
            done = C.STAGE_COLOR[C.GREEN_STAGE]
            label_w = self.tx("PLANETA VERDE", px + 6, y + 70, done)
            self.draw_check(px + 6 + label_w + 5, y + 74, done)   # a fonte não tem "✓": desenhamos um
            return
        name_w = self.tx(nxt.name, px + 6, y + 70, B_TEXT)
        pct_w = self.tx(f"{int(fraction * 100)}%", right, y + 70, C.C_TI, align="right")
        seg_x = max(px + 40, px + 6 + name_w + 5)
        n = max(4, min(16, (right - pct_w - 4 - seg_x + 1) // 5))
        self.segments(seg_x, y + 75, n, round(n * fraction), C.C_TI)
        if wrap_eta:
            head, _, tail = line2.partition(" · ")
            self.tx(head, px + 6, y + 79, B_MUTED, self.body)
            self.text_tilde(tail, px + 6, y + 91, B_MUTED, shadow=False)
        else:
            self.text_tilde(line2, px + 6, y + 79, B_MUTED, shadow=False)

    # ---- energia (lógica em energy.py) ----------------------------------------
    ENERGY_COLOR = {"ok": C.C_OK, "tight": "#ffd84a", "deficit": C.C_ALERT}

    def draw_energy(self, state: GameState) -> None:
        """Pílula embaixo do painel do Ti: raio + barrinha + "produção/consumo kW".

        Verde quando sobra, amarelo perto do limite e vermelho no déficit (com o aviso embaixo, e aí o
        cartão ocupa a largura do painel do Ti).
        """
        power = state.power
        color = self.ENERGY_COLOR[power.level]
        px, w = self.ti_panel_x, TI_PANEL_W
        y = getattr(self, "ti_panel_bottom", 94) + 4
        value = f"{fmt_rate(power.production)}/{fmt_rate(power.consumption)} kW"
        warning = []
        if power.deficit:
            warning = [f"Energia insuficiente · máquinas a {int(power.factor * 100)}%"]
            if self.body.size(warning[0])[0] > w - 12:    # não coube numa linha: quebra no "·"
                warning = warning[0].split(" · ")
        pw = w if warning else min(w, max(90, 14 + 26 + 6 + self.body.size(value)[0] + 6))
        x = px + w - pw
        h = 15 + 12 * len(warning)
        self.hud_panel(x, y, pw, h)
        self.energy_bottom = y + h
        self.right_bottom = self.energy_bottom        # fim da coluna da direita (Ti, energia, minimapa)
        self.draw_bolt(x + 5, y + 3, C.C_ENERGY if not power.deficit else C.C_ALERT, shadow=False)
        used = 1.0 if power.production <= 0 else min(1.0, power.consumption / power.production)
        self.bar(x + 14, y + 7, 26, used, color, h=3)
        self.tx(value, x + pw - 6, y - 2, color, self.body, "right")
        for i, line in enumerate(warning):
            self.tx(line, x + 6, y + 11 + 12 * i, ALERT_TEXT, self.body)

    # ---- objetivos (tutorial leve, lógica em objectives.py) -------------------
    OBJECTIVE_W = 132                           # cartão do objetivo no Grande (o da pílula do O₂)
    OBJECTIVE_W_MAX = 220
    TOP_GAP_MIN = 196                           # vão do topo que o banner/aviso de diagrama precisam

    @property
    def objective_w(self) -> int:
        """Largura do cartão do objetivo: 132 no Grande (texto comprido quebra) e mais larga quando o espaço da UI
        deixa, sem apertar o vão do topo entre ele e o painel do Ti."""
        room = self.ti_panel_x - 6 - self.TOP_GAP_MIN - 6
        return max(self.OBJECTIVE_W, min(self.OBJECTIVE_W_MAX, room))

    def objective_lines(self, lines) -> list[tuple[str, str]]:
        """As linhas do painel já quebradas na largura do cartão: [(estilo, texto)]."""
        out = []
        for line in lines:
            room = self.objective_w - (22 if line.style == "done" else 12)     # a cumprida tem o ✓ na frente
            for part in wrap(self.body, line.text, room):
                out.append((line.style, part))
        return out

    def draw_objectives(self, lines) -> None:
        """Cartão logo abaixo do O₂, com a barra laranja à esquerda: 'OBJETIVO' + as metas (atual em branco,
        próxima apagada, a cumprida em verde com ✓). Texto comprido quebra: o cartão não alarga."""
        if not lines:
            return
        rows = self.objective_lines(lines)
        x, y, w = 6, 27, self.objective_w
        h = 17 + 12 * len(rows)
        self.hud_panel(x, y, w, h)
        self.left_bottom = y + h
        self.fill(C.C_ACCENT, (x, y + 1, 2, h - 2))
        self.tx("OBJETIVO", x + 6, y, C.C_ACCENT)
        first = {}
        for i, (style, text) in enumerate(rows):
            ly = y + 6 + 12 * i
            if style == "done":              # acabou de cumprir: verde com ✓
                if style not in first:
                    self.fill((127, 214, 122, 36), (x + 3, ly + 4, w - 5, 11))
                    self.draw_check(x + 6, ly + 7, C.C_OK)
                    first[style] = True
                self.tx(text, x + 16, ly, C.C_OK, self.body)
            elif style == "current":
                self.tx(text, x + 6, ly, B_TEXT, self.body)
            else:                                 # próximo: apagado
                self.tx(text, x + 6, ly, B_DIM, self.body)

    # ---- tempestade: aviso de rajada ------------------------------------------
    GUST_W, GUST_H = 58, 15

    def draw_gust_warning(self, state: GameState, t: float) -> None:
        """Pílula "RAJADA" com ícone de vento logo abaixo da coluna do O₂/objetivo, enquanto a rajada
        está forte (gust > STORM_GUST_WARN). Guarda o retângulo em gust_rect (None sem aviso)."""
        self.gust_rect = None
        self.thaw_rect = None                  # o aviso do degelo (se vier) é desenhado depois, neste frame
        if not gust_warning(state):
            return
        x, y = 6, self.left_bottom + 4
        w, h = self.GUST_W, self.GUST_H
        self.hud_panel(x, y, w, h)
        self.fill(C.C_ACCENT, (x, y + 1, 2, h - 2))
        # ícone de vento: 3 traços que correm pra direita (o de baixo com a pontinha virada)
        shift = int(t * 6) % 3
        for i, (dx, length) in enumerate(((2, 7), (0, 9), (3, 6))):
            ly = y + 4 + 3 * i
            lx = x + 5 + (dx + shift + i) % 4
            self.fill(C.C_ACCENT if i == 1 else B_TEXT, (lx, ly, length, 1))
        self.fill(B_TEXT, (x + 5 + (3 + shift + 2) % 4 + 6, y + 9, 1, 1))
        self.tx("RAJADA", x + 18, y - 1, C.C_ACCENT)
        self.gust_rect = pygame.Rect(x, y, w, h)

    THAW_ICE = "#9fd8ec"            # gelo (ícone e barrinha do aviso do degelo: neutro, sem o laranja da RAJADA)

    def draw_thaw_notice(self, text: str, alpha: float) -> None:
        """v0.4 M3.1: pílula no estilo da RAJADA, só que neutra (barra e cristal de gelo em azul-gelo, texto claro),
        logo abaixo da coluna do O₂/objetivo (e abaixo da RAJADA, se ela estiver na tela). Some com `alpha`."""
        if not text or alpha <= 0:
            return
        y = (self.gust_rect.bottom if self.gust_rect is not None else self.left_bottom) + 4
        x, h = 6, self.GUST_H
        w = self.body.size(text)[0] + 22
        layer = pygame.Surface((w, h + 1), pygame.SRCALPHA)
        self.card(0, 0, w, h, B_HUD, target=layer)
        self.fill(self.THAW_ICE, (0, 1, 2, h - 2), layer)
        cx, cy = 10, h // 2                                   # cristal de gelo: 3 traços cruzados
        self.fill(self.THAW_ICE, (cx - 3, cy, 7, 1), layer)
        self.fill(self.THAW_ICE, (cx, cy - 3, 1, 7), layer)
        for d in (-2, -1, 1, 2):
            self.fill(B_TEXT, (cx + d, cy + d, 1, 1), layer)
            self.fill(B_TEXT, (cx + d, cy - d, 1, 1), layer)
        self.tx(text, 18, 1, B_TEXT, self.body, target=layer)
        layer.set_alpha(round(255 * min(1.0, alpha)))
        self.surf.blit(layer, (x, y))
        self.hud_rects.append(pygame.Rect(x, y, w, h))
        self.thaw_rect = pygame.Rect(x, y, w, h)

    def draw_objective_hint(self, text: str, alpha: float) -> None:
        """Dica do objetivo atual (v0.4, a da magmatita): cartão da largura do objetivo, com a barra no laranja do
        calor, logo abaixo da coluna da esquerda (O₂/objetivo, RAJADA e aviso do degelo, o que estiver na tela).
        Texto quebra na largura do cartão. Some com `alpha`."""
        if not text or alpha <= 0:
            return
        below = [self.left_bottom] + [r.bottom for r in (self.gust_rect, getattr(self, "thaw_rect", None)) if r]
        x, y, w = 6, max(below) + 4, self.objective_w
        lines = wrap(self.body, text, w - 12)
        h = 7 + 12 * len(lines)
        layer = pygame.Surface((w, h + 1), pygame.SRCALPHA)
        self.card(0, 0, w, h, B_HUD, target=layer)
        self.fill(C.C_HEAT, (0, 1, 2, h - 2), layer)
        for i, line in enumerate(lines):
            self.tx(line, 6, 12 * i, B_TEXT, self.body, target=layer)
        layer.set_alpha(round(255 * min(1.0, alpha)))
        self.surf.blit(layer, (x, y))
        self.hud_rects.append(pygame.Rect(x, y, w, h))

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

    # ---- fabricador e aba Fabricar: lista à esquerda + detalhe à direita ----------------
    def _fab_reset(self) -> None:
        self.fabricator_buttons.clear()
        self.fabricator_rows.clear()
        self.fabricator_tabs.clear()
        self.fabricator_batch.clear()
        self.diagram_buttons.clear()
        self.diagram_rows.clear()

    def draw_fabricator(self, state: GameState, menu, machine_preview, t: float, item_icon=None,
                        mouse=(-1, -1), shift: bool = False, build: bool = False,
                        bench: str = "t1") -> None:
        """Fabricador da base (`menu`: game/fabricator.FabMenu): abas com ícone (só a ativa mostra o nome),
        lista de receitas à esquerda e o detalhe da escolhida à direita. `machine_preview(kind)` = imagem da
        máquina (resolução cheia); `item_icon(item)` = ícone 32×32. Hit-test: fabricator_tabs,
        fabricator_rows, fabricator_batch e fabricator_buttons (o FABRICAR, só se dá pra fabricar).
        `build` = o menu do construtor (v0.5 M1): mesmo painel, materiais só do inventário, sem lote, e o botão
        CONSTRUIR escolhe a máquina (entra no modo de construir). `bench` = a bancada deste painel ("t1"/"t2"):
        a área "Diagramas" (só no fabricador) lista os diagramas do inventário, com o LER nos que ela lê."""
        item_icon = item_icon or (lambda _item: self._blank)
        self._fab_reset()
        self.header_rects.clear()
        self.dim_screen()
        tabs_w = self.fab_tabs_width(menu)
        w, h = min(self.w - 8, max(FAB_W, tabs_w + 16)), min(self.h - 4, FAB_H)
        x, y = (self.w - w) // 2, (self.h - h) // 2       # no centro
        self.fabricator_panel = pygame.Rect(x, y, w, h)
        t2 = bench == "t2" and not build                  # Bancada T2: posto avançado, só o inventário
        inv_only = build or t2
        if build:
            self.window(x, y, w, h, "Construtor", "MATERIAIS: SÓ O INVENTÁRIO")
        elif t2:
            self.window(x, y, w, h, "Bancada T2", "MATERIAIS: SÓ O INVENTÁRIO")
        else:
            self.window(x, y, w, h, "Fabricador", "MATERIAIS: INVENTÁRIO + BAÚS")
        # abas com ícone
        tx = x + 8
        for i, (tab_id, label) in enumerate(menu.tabs):
            on = i == menu.tab
            tw = 22 + (self.body.size(label)[0] + 4 if on else 0)
            rect = pygame.Rect(tx, y + 18, tw, 20)
            unlocked = not menu.kinds_of(tab_id) or any(state.recipe_status(k, inv_only) not in ("locked", "blueprint")
                                                        for k in menu.kinds_of(tab_id))
            hover = not on and rect.collidepoint(mouse)
            self.round_rect(rect, B_HOVER if on or hover else B_WELL, C.C_ACCENT if on else B_LINE)
            icon = item_icon(FAB_TAB_ICON.get(tab_id, "chest"))
            self.native.append((icon if unlocked or on else self.dark_icon(icon, 70), ((tx + 3) * 2, (y + 20) * 2)))
            if on:
                self.tx(label, tx + 21, y + 19, B_TEXT, self.body)
            self.fabricator_tabs.append((rect, i))
            tx += tw + 3
        self.fill(B_LINE, (x + 8, y + 42, w - 16, 1))
        list_y = y + 48
        detail = pygame.Rect(x + 8 + FAB_LIST_W + 6, list_y, w - FAB_LIST_W - 22, h - 72)
        self._recipe_list(state, menu, x + 8, list_y, FAB_LIST_W, detail.h, item_icon, mouse, inv_only=inv_only)
        if not build:
            top = list_y + menu.visible * RECIPE_ROW_STEP + 2
            if len(menu.kinds) > menu.visible:          # a meia linha da rolagem (M5) empurra os Diagramas
                top += RECIPE_PEEK_H + 2
            self._diagram_area(state, menu, x + 8, top, FAB_LIST_W, list_y + detail.h - top, item_icon, mouse, bench)
        kind = menu.current
        if kind is not None:
            batch = 5 if shift else menu.batch
            self._recipe_detail(state, kind, detail, machine_preview, item_icon, batch, mouse,
                                max_rows=max((len(C.MACHINES[k].cost) for k in menu.kinds), default=1),
                                inv_only=inv_only, build=build)
        else:
            self.round_rect(detail, B_CARD)
            self.tx("Nenhuma receita ainda", detail.centerx, detail.centery - 6, B_MUTED, self.body, "center")
        if build:
            pairs = [("A/D", "aba"), ("W/S", "escolhe"), ("ENTER", "constrói"), ("E", "fecha")]
        else:
            pairs = [("A/D", "aba"), ("W/S", "escolhe"),
                     ("ENTER", "lê" if menu.diag is not None else "fabrica"), ("SHIFT", f"×{C.CRAFT_BATCH}"),
                     ("E", "fecha")]
        self.help_line(y + h - 15, pairs, center=x + w / 2)

    def _diagram_area(self, state: GameState, menu, x: int, y: int, w: int, h: int, item_icon, mouse,
                      bench: str) -> None:
        """Área "Diagramas" embaixo da lista do fabricador: um cartão por diagrama do inventário (ícone, nome, ×n e o
        botão LER). Bancada errada ou receita já liberada: o botão fica apagado e diz por quê (nada é gasto).
        Teclado: `menu.diag` é o diagrama com foco (borda laranja)."""
        self.tx("DIAGRAMAS", x, y, B_MUTED)
        held = state.diagrams_held()
        y += 11
        if not held:
            self.tx("nenhum no inventário", x + 2, y + 2, B_DIM, self.body)
            return
        for i, (diagram, count) in enumerate(held[:max(1, (h - 11 + 2) // RECIPE_ROW_STEP)]):
            ry = y + i * RECIPE_ROW_STEP
            row = pygame.Rect(x, ry, w, RECIPE_ROW_H)
            focus = menu.diag == i
            self.round_rect(row, B_HOVER if focus else B_CARD, C.C_ACCENT if focus else None)
            self.native.append((item_icon(f"diagram_{diagram}"), ((x + 3) * 2, (ry + 3) * 2)))
            if not state.bench_reads(diagram, bench):
                label, ok = f"NA {bench_short(C.DIAGRAM_BENCH[diagram])}", False
            elif diagram in state.blueprints:
                label, ok = "JÁ LIDO", False
            else:
                label, ok = "LER", True
            button = pygame.Rect(row.right - 44, ry + 3, 40, 16)
            name = C.BLUEPRINTS[diagram] + (f" x{count}" if count > 1 else "")
            self.tx(self.fit(name, button.x - 3 - (x + 22)), x + 22, ry + 2, B_TEXT if ok else B_DIM, self.body)
            self.button(button, label, "primary" if ok else "off", hover=ok and button.collidepoint(mouse))
            self.diagram_rows.append((row, diagram))
            if ok:
                self.diagram_buttons.append((button, diagram))

    def fab_tabs_width(self, menu) -> int:
        """Largura das abas com ícone (a ativa mais larga: a pior é a de nome mais comprido)."""
        tabs = menu.tabs
        longest = max(self.body.size(label)[0] for _, label in tabs)
        return 22 * len(tabs) + longest + 4 + 3 * (len(tabs) - 1)

    def _recipe_list(self, state: GameState, menu, x: int, y: int, w: int, h: int, item_icon, mouse,
                     inv_only: bool = False) -> None:
        """Lista de receitas da aba atual do `menu`: ícone, nome e o estado à direita (✓ dá pra fabricar,
        "falta" em vermelho, cadeado trancado ou sem diagrama). Rola com a barra quando não cabe."""
        kinds = menu.kinds
        if not kinds:                                  # aba sem receita (a Bancada T2 no M1): estado vazio
            self.round_rect((x, y, w, RECIPE_ROW_H), B_CARD)
            self.tx("nenhuma receita", x + 6, y + 2, B_DIM, self.body)
            return
        selected, first = menu.selected[menu.tab], menu.first[menu.tab]
        scroll = len(kinds) > menu.visible
        row_w = w - 6 if scroll else w
        if scroll:                                     # barra de rolagem na margem direita da lista
            track = pygame.Rect(x + w - 3, y, 3, menu.visible * RECIPE_ROW_STEP - 2)
            self.fill(B_WELL, track)
            thumb_h = max(8, round(track.h * menu.visible / len(kinds)))
            thumb_y = track.y + round((track.h - thumb_h) * first / max(1, menu.max_first))
            self.fill(C.C_ACCENT, (track.x, thumb_y, 3, thumb_h))
        for i, kind in menu.window():
            status = state.recipe_status(kind, inv_only)
            ry = y + (i - first) * RECIPE_ROW_STEP
            row = pygame.Rect(x, ry, row_w, RECIPE_ROW_H)
            on = i == selected
            hover = not on and row.collidepoint(mouse)
            self.round_rect(row, B_HOVER if on or hover else B_CARD, C.C_ACCENT if on else None)
            hidden = status == "blueprint"
            locked = status == "locked" or hidden
            icon = item_icon(f"diagram_{C.RECIPE_BLUEPRINT[kind]}") if hidden else item_icon(kind)
            self.native.append((self.dark_icon(icon, 80) if locked else icon, ((x + 3) * 2, (ry + 3) * 2)))
            name = "???" if hidden else C.MACHINES[kind].name
            right = row.right - 6
            if status == "ok":
                self.draw_check(right - 7, ry + 8, C.C_OK)
                status_w = 9
            elif status == "missing":
                status_w = self.tx("falta", right, ry + 2, ALERT_TEXT, self.body, "right")
            elif status in ("known", "made"):          # diagrama lido / item de uma vez só já fabricado (M5)
                status_w = self.tx("lido" if status == "known" else "feito", right, ry + 2, B_DIM, self.body, "right")
            else:
                self.draw_lock(right - 7, ry + 7, B_DIM)
                status_w = 9
            self.tx(self.fit(name, row.right - 6 - status_w - 4 - (x + 22)), x + 22, ry + 2,
                    B_DIM if locked else B_TEXT, self.body)
            self.fabricator_rows.append((row, kind))
        below = first + menu.visible
        if scroll and below < len(kinds):              # v0.6 Fundo M5 (dono): meia linha do próximo = "tem mais, rola"
            peek = pygame.Rect(x, y + menu.visible * RECIPE_ROW_STEP, row_w, RECIPE_PEEK_H)
            old_clip = self.surf.get_clip()
            self.surf.set_clip(peek.clip(old_clip) if old_clip else peek)
            self.round_rect((x, peek.y, row_w, RECIPE_ROW_H), B_CARD)
            nxt = kinds[below]
            hidden = state.recipe_status(nxt, inv_only) == "blueprint"
            name = "???" if hidden else C.MACHINES[nxt].name
            icon = self.dark_icon(item_icon(f"diagram_{C.RECIPE_BLUEPRINT[nxt]}" if hidden else nxt), 110)
            cut = min(icon.get_height(), (RECIPE_PEEK_H - 3) * 2)   # o ícone também sai pela metade (nativo é 2×)
            if cut > 0:
                self.native.append((icon.subsurface((0, 0, icon.get_width(), cut)), ((x + 3) * 2, (peek.y + 3) * 2)))
            self.tx(self.fit(name, row_w - 28), x + 22, peek.y + 2, B_DIM, self.body)
            self.surf.set_clip(old_clip)

    def fit(self, s: str, max_w: int, font=None) -> str:
        """Corta o texto (com "..") até caber em `max_w`."""
        font = font or self.body
        if font.size(s)[0] <= max_w:
            return s
        while s and font.size(s + "..")[0] > max_w:
            s = s[:-1]
        return s.rstrip() + ".."

    @staticmethod
    def detail_fit(h: int, max_rows: int) -> tuple[int, int]:
        """(lado da vitrine, passo das linhas de custo) do painel de detalhe que cabem na altura `h`:
        o do mockup (64, 21) e, se não couber, versões mais compactas."""
        for pv, step in ((64, 21), (64, 19), (56, 19), (48, 19), (48, 17), (40, 17)):
            if pv + max_rows * step + 48 <= h:
                return pv, step
        return 40, 17

    def _recipe_detail(self, state: GameState, kind: str, rect: pygame.Rect, machine_preview, item_icon,
                       batch: int, mouse, max_rows: int, inv_only: bool = False, build: bool = False) -> None:
        """Detalhe da receita escolhida: prévia, nome, descrição, energia, quantas já tem, uma linha por material
        (ícone, "tem/precisa", barrinha e ✓/✗), seletor ×1/×5 e o botão FABRICAR (ou o que falta).
        `build` (menu do construtor): sem o "no inventário" nem o lote; o botão CONSTRUIR (ou o que falta, que
        também escolhe: o fantasma fica vermelho até ter o material)."""
        x, y, w, h = rect
        m = C.MACHINES[kind]
        status = state.recipe_status(kind, inv_only)
        hidden = status == "blueprint"
        locked = status == "locked" or hidden
        self.round_rect(rect, B_CARD)
        pv, step = self.detail_fit(h, max_rows)
        # vitrine: prévia em pixel inteiro, com uma faixa de "chão"
        box = pygame.Rect(x + 6, y + 6, pv, pv)
        self.round_rect(box, B_WELL)
        self.fill("#151926", (box.x + 1, box.bottom - 12, pv - 2, 11))
        preview = machine_preview(kind)
        room = pv * 2 - 8
        pw, ph = preview.get_size()
        scale = max(1, min(2, room // max(1, pw), room // max(1, ph)))
        if pw * scale > room or ph * scale > room:          # maior que a vitrine: encolhe pra caber
            ratio = min(room / pw, room / ph)
            preview = pygame.transform.scale(preview, (max(1, int(pw * ratio)), max(1, int(ph * ratio))))
        elif scale > 1:
            preview = pygame.transform.scale_by(preview, scale)
        if locked:
            preview = preview.copy()
            preview.fill((40, 40, 50) if hidden else (110, 110, 120), special_flags=pygame.BLEND_RGB_MULT)
        self.native.append((preview, (box.centerx * 2 - preview.get_width() // 2,
                                      (box.bottom - 4) * 2 - preview.get_height())))
        tx = box.right + 6
        text_w = x + w - 6 - tx
        if hidden:
            self.tx("???", tx, y + 4, B_TEXT, self.body)
            self.tx("precisa do diagrama", tx, y + 15, B_MUTED, self.body)
        else:
            made = C.CRAFT_YIELD.get(kind, 1)                # fabricar rende mais de 1 (fios): "Fios ×3"
            self.tx(self.fit(m.name if build or made == 1 else f"{m.name} ×{made}", text_w), tx, y + 4, B_TEXT, self.body)
            self.tx(self.fit(m.desc, text_w), tx, y + 15, C.C_TI, self.body)
            use, gen = energy.machine_use(kind), energy.machine_gen(kind)
            if use or gen:
                kw = f"+{fmt_rate(gen)} kW" if gen else f"-{fmt_rate(use)} kW"
                kw_color = C.C_OK if gen else C.C_ENERGY
                cw = 13 + self.body.size(kw)[0] + 4
                chip_y = y + 31 if pv >= 64 else y + 28
                self.round_rect((tx, chip_y, cw, 13), B_WELL, B_LINE)
                self.draw_bolt(tx + 4, chip_y + 2, kw_color, shadow=False)
                self.tx(kw, tx + 13, chip_y - 1, kw_color, self.body)
        owned = state.inventory.count(kind)
        if pv >= 56 and not build:                   # vitrine compacta demais: a linha não cabe
            self.tx(f"x{owned} no inventário", tx, box.bottom - 22, C.C_OK if owned else B_DIM, self.body)
        # custo: uma linha por material
        cy = box.bottom + 3
        self.tx("CUSTO", x + 6, cy, B_MUTED)
        self.tx("TEM / PRECISA", x + w - 6, cy, B_DIM, align="right")
        row_h = step - 1
        if hidden:
            where = ("Ache o diagrama num destroço do deserto e leia no fabricador"
                     if C.RECIPE_BLUEPRINT.get(kind) in C.WRECK_DIAGRAMS          # v0.6: os outros se fabricam no T1
                     else "Fabrique o diagrama no fabricador T1 e leia na bancada")
            for k, line in enumerate(wrap(self.body, where, w - 12)[:3]):
                self.tx(line, x + 6, cy + 11 + k * 12, B_MUTED, self.body)
        else:
            done = locked or status in ("known", "made")   # v0.6 Fundo M5: lido/feito não pinta o custo de vermelho
            for i, (res, n) in enumerate(m.cost.items()):
                yy = cy + 11 + i * step
                have = state.available(res, inv_only)
                ok = have >= n
                if done:
                    bg, border, num_color, bar_color = B_CARD2, B_LINE, B_DIM, B_DIM
                else:
                    bg, border = (OK_BG, OK_BORDER) if ok else (BAD_BG, BAD_BORDER)
                    num_color, bar_color = (OK_TEXT, C.C_OK) if ok else (ALERT_TEXT, C.C_ALERT)
                row = pygame.Rect(x + 6, yy, w - 12, row_h)
                self.round_rect(row, bg, border)
                icon = item_icon(res)
                self.native.append((self.dark_icon(icon, 110) if done else icon,
                                    ((x + 8) * 2, (yy + (row_h - 16) // 2) * 2)))
                text_y = yy + (row_h - 20) // 2 + 1
                self.tx(item_name(res), x + 27, text_y, B_TEXT if not done else B_DIM, self.body)
                self.tx(f"{have}/{n}", x + w - 21, text_y, num_color, self.body, "right")
                if not done:
                    if ok:
                        self.draw_check(x + w - 17, yy + row_h // 2 - 3, C.C_OK)
                    else:
                        self.draw_cross(x + w - 16, yy + row_h // 2 - 2, C.C_ALERT)
                self.bar(x + 27, yy + row_h - 4, w - 52, min(1.0, have / n), bar_color, h=1, track="#2a2f40")
        # lote + botão
        by = y + h - 24
        for k, amount in enumerate(() if build else (1, C.CRAFT_BATCH)):
            rect_b = pygame.Rect(x + 6 + k * 23, by, 21, 18)
            on = amount == batch
            hover = not on and rect_b.collidepoint(mouse)
            self.round_rect(rect_b, B_HOVER if on or hover else B_WELL, C.C_ACCENT if on else B_LINE)
            self.tx(f"×{amount}", rect_b.centerx, by + 1, B_TEXT if on else B_MUTED, self.body, "center")
            self.fabricator_batch.append((rect_b, amount))
        button = pygame.Rect(x + 6, by, w - 12, 18) if build else pygame.Rect(x + 54, by, w - 60, 18)
        if status == "ok":
            label, kind_b = ("CONSTRUIR" if build else "FABRICAR"), "primary"
            self.fabricator_buttons.append((button, kind))
        elif status == "missing":
            res = state.missing_resource(kind, inv_only)
            short = m.cost[res] - state.available(res, inv_only)
            label, kind_b = f"FALTAM {short} {item_name(res).upper()}", "danger"
            if build:                                # escolhe mesmo assim: o fantasma vermelho diz o que falta
                self.fabricator_buttons.append((button, kind))
        elif hidden:
            label, kind_b = "SEM DIAGRAMA", "off"
        elif status in ("known", "made"):
            label, kind_b = ("JÁ LIDO" if status == "known" else "JÁ FEITO"), "off"
        else:
            label, kind_b = unlock_text(kind), "off"
        self.button(button, label, kind_b, hover=kind_b == "primary" and button.collidepoint(mouse))
        self.craft_label = label

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
        """Slot do estilo B: quadradinho escuro com canto de 1 px e uma luz bem sutil em cima."""
        self.round_rect((x, y, SLOT, SLOT), B_SLOT_OUT)
        self.surf.fill(pygame.Color(B_SLOT_IN), (x + 1, y + 1, SLOT - 2, SLOT - 2))
        self.surf.fill(pygame.Color(B_SLOT_LIGHT), (x + 2, y + 1, SLOT - 4, 1))
        if hover:
            self.round_rect((x + 1, y + 1, SLOT - 2, SLOT - 2), B_HOVER)
        if selected:
            self.round_rect((x - 1, y - 1, SLOT + 2, SLOT + 2), (0, 0, 0, 0), C.C_ACCENT)
            self.fill((226, 115, 58, 40), (x + 1, y + 1, SLOT - 2, SLOT - 2))
        if stack:
            self.native.append((item_icon(stack.item), (x * 2 + 4, y * 2 + 4)))
            if stack.count > 1:
                self.native_text(str(stack.count), x + SLOT - 1, y + SLOT - 9, C.C_TEXT, "right")

    def draw_hotbar(self, inventory: Inventory, selected: int, item_icon, show_name: bool = False) -> None:
        """Os 8 primeiros slots do inventário no rodapé central, com o número da tecla em cima de cada
        slot e o selecionado destacado. `show_name` (jogando): o nome e a quantidade do item escolhido numa
        pílula em cima da hotbar."""
        hx, hy = self.hotbar_x, self.hotbar_y
        self.hud_panel(hx - 4, hy - 11, GRID_W + 8, SLOT + 15)
        for i in range(C.HOTBAR_SLOTS):
            x = hx + i * SLOT_STEP
            self.tx(str(i + 1), x + SLOT / 2, hy - 11, C.C_ACCENT if i == selected else B_DIM, align="center")
            self.draw_slot(x, hy, inventory.slots[i], item_icon, selected=i == selected)
        stack = inventory.slots[selected] if 0 <= selected < len(inventory) else None
        self.name_pill = None
        if show_name and stack is not None:
            name = f"{item_name(stack.item)} · {stack.count}"
            nw = self.body.size(name)[0] + 12
            nx = self.w // 2 - nw // 2
            self.hud_panel(nx, hy - 27, nw, 13, bg=(15, 17, 25, 200))
            self.tx(name, self.w // 2, hy - 29, B_TEXT, self.body, "center")
            self.name_pill = pygame.Rect(nx, hy - 27, nw, 13)

    def draw_notice(self, text: str, alpha: float, y: int | None = None) -> None:
        """Aviso curto no meio da tela, acima da hotbar ("Inventário cheio"). `y` muda a altura (nos
        painéis de inventário ele vai abaixo da linha de ajuda, pra não cobrir texto)."""
        w = self.body.size(text)[0] + 16
        layer = pygame.Surface((w, 18), pygame.SRCALPHA)
        self.card(0, 0, w, 18, (34, 16, 18, 240), "#7a3a33", shadow=False, target=layer)
        layer.fill(pygame.Color(C.C_ALERT), (2, 1, w - 4, 1))
        self.text(text, w / 2, 1, "#ffd0c8", self.body, "center", target=layer, shadow=False)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (self.w // 2 - w // 2, self.hotbar_y - 58 if y is None else y))

    def draw_toast(self, text: str, alpha: float) -> None:
        """Aviso neutro e rápido no topo do centro ("Zoom 1,5×", "Tela cheia"). Texto que não cabe na tela (a dica
        de lore do contêiner lacrado, v0.4 M3.2) quebra em duas linhas no último " · "."""
        text = text.upper()            # Silkscreen: na Pixelify de 11 px o "Z" parece um "2"
        lines = [text]
        if self.font.size(text)[0] + 16 > self.w - 16 and " · " in text:
            head, _, tail = text.rpartition(" · ")
            lines = [head, tail]
        w = max(self.font.size(line)[0] for line in lines) + 16
        h = 15 + 11 * (len(lines) - 1)
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        self.card(0, 0, w, h, B_WINDOW, B_LINE, shadow=False, target=layer)
        layer.fill(pygame.Color(C.C_ACCENT), (2, 1, w - 4, 1))
        for i, line in enumerate(lines):
            self.text(line, w / 2, 1 + 11 * i, B_TEXT, target=layer, align="center", shadow=False)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, (self.w // 2 - w // 2, 40))   # logo abaixo do banner de estágio
        self.hud_rects.append(pygame.Rect(self.w // 2 - w // 2, 40, w, h))

    def _grid(self, inv: Inventory, indexes: list[int], x: int, y: int, item_icon, mouse, selected=None) -> None:
        """Desenha os slots `indexes` de `inv` em linhas de 8, a partir de (x, y), e guarda os retângulos."""
        for n, i in enumerate(indexes):
            sx, sy = x + (n % 8) * SLOT_STEP, y + (n // 8) * SLOT_STEP
            rect = pygame.Rect(sx, sy, SLOT, SLOT)
            self.draw_slot(sx, sy, inv.slots[i], item_icon, selected=i == selected, hover=rect.collidepoint(mouse))
            self.slot_rects.append((rect, inv, i))

    def _section_label(self, label: str, x: int, y: int, color: str = B_MUTED) -> int:
        """Rótulo de seção ("INVENTÁRIO", "MOCHILA", "HOTBAR", "TRAJE", "DRONES"): entra nos cabeçalhos que o tooltip evita."""
        w = self.tx(label, x, y, color)
        self.header_rects.append(pygame.Rect(x, y + 3, w + 1, 7))      # a letra (5 px) com 1 px de folga
        return w

    def _reset_panels(self) -> None:
        self.slot_rects.clear()
        self.header_rects.clear()
        self.bay_rects.clear()
        self.buffer_rects.clear()
        self.panel_buttons.clear()
        self.logistics_buttons.clear()
        self.chip_rects.clear()
        self.equip_rects.clear()
        self.inv_tab_rects.clear()
        self.log_rows.clear()
        self.suit_text_rects.clear()
        self.name_rect = None

    def draw_inventory(self, inventory: Inventory, side, hotbar_selected: int, item_icon,
                       mouse: tuple[float, float], t: float = 0.0, editing=None, status: str = "",
                       info: str | None = None, equipment=None, state: GameState | None = None,
                       held: Stack | None = None) -> None:
        """Tela do Tab (só o inventário) ou com um painel do lado: baú, drill, estação ou caixa.
        No Tab, com `state`, ganha as abas Inventário / LOGs no topo (a outra aba é o draw_logs).

        `side` = None (Tab) ou a Machine/Crate aberta. `editing` = TextField do nome do baú sendo editado
        (ou None). `status` = linha de estado da estação/drill. `held` = pilha na mão (painel de detalhe).
        Inventário: mochila (slots 8–15) em cima, hotbar (slots 0–7) embaixo, igual à ordem da tela."""
        self._reset_panels()
        self.dim_screen()
        if side is None:
            self._tab_inventory(inventory, hotbar_selected, item_icon, mouse, equipment, state, held)
        else:
            self._side_panels(inventory, side, hotbar_selected, item_icon, mouse, t, editing, status, info)

    NOTICE_H = 18                                      # altura do aviso (draw_notice)

    def _tab_inventory(self, inventory, hotbar_selected, item_icon, mouse, equipment, state, held) -> None:
        """Aba Inventário do Tab (v0.8 M5, Tab A): 3 colunas. À esquerda as grades (MOCHILA ou MOCHILA T2 em cima,
        INVENTÁRIO e HOTBAR); no meio o cartão do TRAJE (Explorador + os 4 slots em 2×2); à direita o detalhe do item
        com o mouse (ou da mão, ou o da hotbar) com "USADO EM". A altura é a mesma com ou sem mochila (o TRAJE é a
        coluna mais alta). Sem `equipment` (fora do Tab) a coluna do TRAJE some."""
        tabbed = state is not None
        suit = equipment is not None
        extra = backpack_extra(len(inventory))     # linha(s) da mochila (equipada)
        content = INV_CONTENT_Y if tabbed else 22
        grids_h = extra + 2 * SLOT_STEP + 2 * 10 - SLOT_GAP      # INVENTÁRIO (rótulo + slots) e HOTBAR (rótulo + slots)
        if suit:
            w, h = TAB_INV_W, max(TAB_INV_H, content + grids_h + 8)
        else:
            w, h = TAB_INV_W - TAB_SUIT_W - TAB_COL_GAP, max(TAB_BARE_H, content + grids_h + 8)
        if tabbed:
            w = max(w, self.inv_tabs_width() + 16)
        x = (self.w - w) // 2
        y = self.inv_tabs_top(h) if tabbed else self.window_top(h)
        self.inv_window = pygame.Rect(x, y, w, h)
        used = sum(1 for s in inventory.slots if s)
        self.window(x, y, w, h, "Inventário", f"{used}/{len(inventory)}")
        if tabbed:
            self._inventory_tabs(x, y, w, TAB_INVENTORY, state, mouse)
        top = y + content
        gx = x + 10
        hb = C.HOTBAR_SLOTS
        gy = top
        if extra:                                    # mochila equipada: as linhas dela (16–23, e 24–31 na T2) em cima
            self._section_label(backpack_label(len(inventory)), gx, gy, C.C_ACCENT)
            self._grid(inventory, list(range(2 * hb, len(inventory))), gx, gy + 10, item_icon, mouse)
            gy += extra
        self._section_label("INVENTÁRIO", gx, gy)
        self._grid(inventory, list(range(hb, 2 * hb)), gx, gy + 10, item_icon, mouse)
        self._section_label("HOTBAR", gx, gy + 32)
        self._grid(inventory, list(range(hb)), gx, gy + 42, item_icon, mouse, hotbar_selected)
        col_h = y + h - 8 - top
        dx = gx + GRID_W + TAB_COL_GAP
        if suit:
            self.suit_rect = pygame.Rect(dx, top, TAB_SUIT_W, col_h)
            self._suit_card(equipment, self.suit_rect, item_icon, mouse, state.o2_max if state is not None else None)
            dx += TAB_SUIT_W + TAB_COL_GAP
        # painel do item: o do mouse, a pilha da mão ou o da hotbar (da coluna até a borda, 8 px)
        detail = pygame.Rect(dx, top, x + w - 8 - dx, col_h)
        self.detail_rect = detail
        item, count = None, 0
        hovered = next(((inv.slots[i]) for r, inv, i in self.slot_rects if r.collidepoint(mouse)), None)
        equip = next((k for r, k in self.equip_rects if r.collidepoint(mouse)), None)
        if hovered is not None:
            item, count = hovered.item, hovered.count
        elif equip is not None and equipment is not None and equipment.filled(equip):
            item, count = equipment.slots[equip], 1
        elif held is not None:
            item, count = held.item, held.count
        elif inventory.slots[hotbar_selected] is not None:
            item, count = inventory.slots[hotbar_selected].item, inventory.slots[hotbar_selected].count
        self._item_detail(item, count, detail, item_icon, state)
        if not tabbed:
            pairs = [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("ESC", "fecha")]
        else:
            pairs = [("CLIQUE", "pega/solta"), ("DIR", "metade"), ("A/D", "aba"), ("ESC", "fecha")]
        self.help_line(y + h + 7, pairs)
        self.notice_y = self.panel_notice_y(y, y + h + HELP_H + 2)

    def _item_detail(self, item: str | None, count: int, rect: pygame.Rect, item_icon,
                     state: GameState | None) -> None:
        """Detalhe do item: ícone 2×, nome, categoria, "pilha / máximo" e "USADO EM" (as receitas que gastam
        o item, achadas pelos custos; as de diagrama ainda não lido ficam de fora)."""
        x, y, w, h = rect
        self.round_rect(rect, B_CARD)
        self.detail_item, self.detail_uses = item, []
        if item is None:
            for k, line in enumerate(wrap(self.body, "Passe o mouse num item pra ver onde ele entra", w - 16)):
                self.tx(line, x + w / 2, y + h // 2 - 12 + 12 * k, B_DIM, self.body, "center")
            return
        self.round_rect((x + 6, y + 6, 36, 36), B_WELL)
        self.native.append((pygame.transform.scale_by(item_icon(item), 2), ((x + 8) * 2, (y + 8) * 2)))
        names = wrap(self.body, item_name(item), w - 54)[:2]
        ny = y + 5 if len(names) == 1 else y + 2
        for k, line in enumerate(names):
            self.tx(self.fit(line, w - 54), x + 48, ny + 11 * k, B_TEXT, self.body)
        cat, color = item_category(item)
        cy = ny + 11 * len(names)
        self.tx(cat, x + 48, cy, color)
        self.tx(f"{count} / {max_stack(item)}", x + 48, cy + 10, B_MUTED, self.body)
        self.fill(B_LINE, (x + 6, y + 48, w - 12, 1))
        self.tx("USADO EM", x + 6, y + 47, B_MUTED)
        uses = [k for k in used_in(item) if state is None or state.recipe_status(k) != "blueprint"]
        self.detail_uses = uses
        if not uses:
            for k, line in enumerate(wrap(self.body, "Não entra em nenhuma receita", w - 12)):
                self.tx(line, x + 6, y + 58 + 12 * k, B_DIM, self.body)
            return
        room = max(1, (y + h - 2 - (y + 58)) // 20)
        shown = uses if len(uses) <= room else uses[:room - 1]
        for i, kind in enumerate(shown):
            yy = y + 58 + i * 20
            self.native.append((item_icon(kind), ((x + 6) * 2, yy * 2)))
            self.tx(self.fit(C.MACHINES[kind].name, w - 28), x + 26, yy + 1, B_TEXT, self.body)
        if len(shown) < len(uses):
            rest = len(uses) - len(shown)
            self.tx(f"+ {rest} receita{'s' if rest > 1 else ''}", x + 26, y + 58 + len(shown) * 20 + 1, B_MUTED,
                    self.body)

    def _suit_card(self, equipment, rect: pygame.Rect, item_icon, mouse, o2_max) -> None:
        """TRAJE em coluna (v0.8 M5, Tab A): o Explorador em cima e os 4 slots (C.EQUIP_SLOTS: tanque, scanner,
        mochila, botas) em 2×2 embaixo, cada um centrado na sua célula com o rótulo embaixo. Estado só onde diz
        alguma coisa: os segundos do tanque ("220 s", "400 s") e "vazio". Uma linha liga o tanque e o scanner
        ao corpo. Os slots são os equip_rects (o clique e o detalhe usam eles)."""
        x, y, w, h = rect
        self.round_rect(rect, B_CARD)
        self._section_label("TRAJE", x + 6, y - 1, C.C_O2)
        ex, ey = x + w // 2 - 16, y + 6
        self.round_rect((ex - 2, ey + 30, 36, 3), B_DEEP)               # sombrinha no chão
        self.native.append((self.explorer_image(), (ex * 2, ey * 2)))
        centers = []
        for k, kind in enumerate(C.EQUIP_SLOTS):
            cx = x + 2 + (k % 2) * SUIT_CELL_W + SUIT_CELL_W // 2
            sy = y + SUIT_ROW_Y[k // 2]
            centers.append(cx)
            item = self._equip_slot(equipment, kind, cx - SLOT // 2, sy, item_icon, mouse)
            label = C.EQUIP_LABEL[kind]
            self.tx(label, cx, sy + 21, B_TEXT if item else B_MUTED, align="center")
            self.suit_text_rects.append((label, self._ink(self.font, label, cx, sy + 21, "center")))
            if item:
                sub = f"{round(o2_max)} s" if kind == "o2_tank" and o2_max else ""
            else:
                sub = "vazio"
            if sub:                                  # ponto 3×3 + texto, o par centrado na célula
                color = C.C_OK if item else B_DIM
                tw = self.body.size(sub)[0]
                sx = cx - (tw + 5) // 2
                self.fill(color, (sx, sy + 33, 3, 3))
                self.tx(sub, sx + 5, sy + 28, color, self.body)
                ink = self._ink(self.body, sub, sx + 5, sy + 28).union(pygame.Rect(sx, sy + 33, 3, 3))
                self.suit_text_rects.append((sub, ink))
        # linhas do tanque e do scanner até o corpo: sobem do slot, dobram e chegam no corpo (ponto ciano)
        top_y = y + SUIT_ROW_Y[0] - 2
        for k, (body_x, body_y) in enumerate(((ex + 6, ey + 18), (ex + 26, ey + 22))):
            cx = centers[k]
            dot = C.C_O2 if equipment.filled(C.EQUIP_SLOTS[k]) else B_DIM
            self.fill(B_LINE2, (cx, body_y, 1, top_y - body_y + 1))
            if k == 0:
                self.fill(B_LINE2, (cx, body_y, body_x + 2 - cx + 1, 1))
                self.fill(dot, (body_x, body_y - 1, 3, 3))
            else:
                self.fill(B_LINE2, (body_x - 2, body_y, cx - body_x + 3, 1))
                self.fill(dot, (body_x - 2, body_y - 1, 3, 3))

    def _ink(self, font, s: str, x: int, y: int, align: str = "left") -> pygame.Rect:
        """Caixa da tinta de um texto desenhado em (x, y) (sem a folga da fonte em volta)."""
        img = self._render(font, s, "#ffffff")
        box = img.get_bounding_rect()
        w = img.get_width()
        x = x - w if align == "right" else x - w // 2 if align == "center" else x
        return box.move(int(x), int(y))

    def _equip_slot(self, equipment, kind: str, sx: int, sy: int, item_icon, mouse) -> str | None:
        """Um slot do TRAJE: o item equipado (nv.1 ou nv.2) com a borda ciana, ou o fantasma do nv.1 (alpha 45;
        o das botas é o placeholder até o PNG chegar). Devolve o item equipado."""
        rect = pygame.Rect(sx, sy, SLOT, SLOT)
        item = equipment.slots.get(kind)
        self.draw_slot(sx, sy, Stack(item, 1) if item else None, item_icon, hover=rect.collidepoint(mouse))
        if item:
            self.round_rect((sx - 1, sy - 1, SLOT + 2, SLOT + 2), (0, 0, 0, 0), C.C_O2)
        else:
            ghost = item_icon(kind).copy()
            ghost.set_alpha(45)
            self.native.append((ghost, (sx * 2 + 4, sy * 2 + 4)))
        self.equip_rects.append((rect, kind))
        return item

    # ---- painéis lado a lado: inventário | botões do meio | baú, drill, estação ou caixa ----
    def _side_layout(self, side_h: int) -> tuple[int, int, int, int]:
        """(x do inventário, x do outro painel, y do topo, altura total) dos painéis lado a lado."""
        total_w = 2 * SIDE_W + SIDE_MID
        lx = (self.w - total_w) // 2
        h = max(SIDE_INV_H, side_h)
        return lx, lx + SIDE_W + SIDE_MID, self.window_top(h), h

    def _side_panels(self, inventory, side, hotbar_selected, item_icon, mouse, t, editing, status, info) -> None:
        if isinstance(side, Crate):
            side_h = 100
        elif side.is_chest:
            side_h = self._chest_logi_y(side) + self.logistics_height(side) + 14
        elif side.is_drill or side.is_melter or side.is_dispenser:
            side_h = 92 + self.logistics_height(side) + 10
        elif side.is_smelter:
            side_h = SMELT_LOGI_Y + self.logistics_height(side) + 10
        elif side.is_collector:
            side_h = COLLECT_LOGI_Y + self.logistics_height(side) + 10
        elif side.is_cultivator:
            side_h = CULT_LOGI_Y + self.logistics_height(side) + 10
        elif side.is_microscope:
            side_h = MIC_LOGI_Y + max(LOGI_H, self.logistics_height(side)) + 10
        elif side.is_centrifuge:
            side_h = CENT_LOGI_Y + max(LOGI_H, self.logistics_height(side)) + 10
        else:
            side_h = 164
        hb = C.HOTBAR_SLOTS
        extra = backpack_extra(len(inventory))                                    # linha(s) da mochila (equipada)
        inv_h = SIDE_INV_H + extra
        side_h = max(side_h, inv_h)                  # o painel do lado cresce junto, pras duas janelas ficarem iguais
        lx, rx, y, h = self._side_layout(side_h)
        used = sum(1 for s in inventory.slots if s)
        self.window(lx, y, SIDE_W, inv_h, "Inventário", f"{used}/{len(inventory)}")
        self.inv_window = pygame.Rect(lx, y, SIDE_W, inv_h)
        gx = lx + 8
        gy = y
        if extra:                                    # 1 linha (nv.1) ou 2 (T2): BACKPACK_ROW_H cada, em cima
            self._section_label(backpack_label(len(inventory)), gx, gy + 16, C.C_ACCENT)
            self._grid(inventory, list(range(2 * hb, len(inventory))), gx, gy + 26, item_icon, mouse)
            gy += extra
        self._section_label("INVENTÁRIO", gx, gy + 16)
        self._grid(inventory, list(range(hb, 2 * hb)), gx, gy + 26, item_icon, mouse)
        self._section_label("HOTBAR", gx, gy + 48)
        self._grid(inventory, list(range(hb)), gx, gy + 58, item_icon, mouse, hotbar_selected)
        mid = pygame.Rect(lx + SIDE_W + 4, y + 22, SIDE_MID - 8, 40)
        if isinstance(side, Crate):
            self._crate_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, mid)
            pairs = HELP_CURSOR
        elif side.is_chest:
            self._chest_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, t, editing, mid)
            pairs = ([("ENTER", "ok"), ("ESC", "cancela")] if editing is not None else
                     HELP_CURSOR)
        elif side.is_drill:
            self._drill_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, mid)
            pairs = HELP_CURSOR
        elif side.is_melter:
            self._melter_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, mid)
            pairs = HELP_CURSOR
        elif side.is_smelter:
            self._smelter_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, mid)
            pairs = HELP_CURSOR
        elif side.is_collector:
            self._collector_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, info, mid)
            pairs = HELP_CURSOR
        elif side.is_cultivator:
            self._cultivator_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, mid)
            pairs = HELP_CURSOR
        elif side.is_microscope:
            self._microscope_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, info, mid)
            pairs = HELP_CURSOR
        elif side.is_centrifuge:
            self._centrifuge_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, info, mid)
            pairs = HELP_CURSOR
        elif side.is_dispenser:
            self._dispenser_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, info, mid)
            pairs = HELP_CURSOR
        else:
            self._station_panel(side, rx, y, SIDE_W, side_h, item_icon, mouse, status, info, mid)
            pairs = HELP_CURSOR
        self.help_line(y + h + 7, pairs)
        self.notice_y = self.panel_notice_y(y, y + h + HELP_H + 2)

    # ---- abas do Tab: Inventário / LOGs ---------------------------------
    INV_TAB_LABELS = ("Inventário", "LOGs")
    TAB_DOT = 5                                        # espaço do ponto laranja de LOG novo

    def inv_tab_labels(self, state: GameState) -> list[str]:
        found = len(state.logs_read)
        return [*self.INV_TAB_LABELS[:TAB_LOGS], f"{self.INV_TAB_LABELS[TAB_LOGS]} {found}/{len(C.LOGS)}"]

    def inv_tabs_width(self) -> int:
        """Largura do controle segmentado no pior caso (contador 7/7 e o ponto de NOVO): a janela não muda
        conforme acha."""
        labels = [*self.INV_TAB_LABELS[:TAB_LOGS], f"{self.INV_TAB_LABELS[TAB_LOGS]} {len(C.LOGS)}/{len(C.LOGS)}"]
        return sum(self.body.size(lb)[0] + 14 for lb in labels) + 2 + self.TAB_DOT

    def inv_tabs_top(self, h: int = TAB_INV_H) -> int:
        """y do topo da janela do Tab: o mesmo nas 3 abas (sai da mais alta), pra as abas não pularem; a
        linha de ajuda da mais alta fica acima da hotbar."""
        tallest = max(h, TAB_INV_H, self.logs_window_size()[1])
        return self.window_top(tallest)

    def _inventory_tabs(self, x: int, y: int, w: int, active: int, state: GameState, mouse) -> None:
        """Abas como controle segmentado, centralizado embaixo do título. A de LOGs leva o contador (3/7) e
        um ponto laranja se tem LOG lido que ainda não foi aberto por ela."""
        self.inv_tab_rects.clear()
        labels = self.inv_tab_labels(state)
        widths = [self.body.size(lb)[0] + 14 for lb in labels]
        widths[TAB_LOGS] += self.TAB_DOT
        total = sum(widths) + 2
        # no meio da TELA (as janelas do Tab são centradas): com larguras de paridade diferente (Inventário 446,
        # LOGs 375), o meio da janela arredondava 1 px pra cada lado e a barra pulava ao trocar de aba
        sx = (self.w - total) // 2 if x == (self.w - w) // 2 else x + (w - total) // 2
        ty = y + INV_TABS_Y
        self.round_rect((sx, ty, total, INV_TABS_H), B_WELL, B_LINE)
        xx = sx + 1
        for i, (label, lw) in enumerate(zip(labels, widths)):
            rect = pygame.Rect(xx, ty + 1, lw, INV_TABS_H - 2)
            on = i == active
            hover = not on and rect.collidepoint(mouse)
            if on or hover:
                self.round_rect(rect, B_HOVER)
            if on:
                self.fill(C.C_ACCENT, (xx + 3, ty + 13, lw - 6, 1))
            self.tx(label, xx + 7, ty, B_TEXT if on else B_MUTED, self.body)
            if i == TAB_LOGS and state.new_logs > 0:
                self.fill(C.C_ACCENT, (xx + lw - 5, ty + 3, 2, 2))
            self.inv_tab_rects.append((rect, i))
            xx += lw
        self.header_rects.append(pygame.Rect(x, ty, w, INV_TABS_H))   # abas: o tooltip não cobre

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
        room = self.window_room - INV_CONTENT_Y - 2 - 6
        rows = max(1, min(len(C.LOGS), room // LOG_ROW_STEP))
        self.log_visible = rows
        return w, INV_CONTENT_Y + 2 + rows * LOG_ROW_STEP + 6

    def draw_logs(self, state: GameState, selected: int, first: int, mouse) -> None:
        """Aba LOGs do Tab: os LOGs na ordem da história (config.LOG_ORDER). Lido = "LOG 0N · Dia X · título"
        e clicável (abre a tela de leitura); não achado = "LOG 0N · ???" apagado. "NOVO" nos lidos que a aba
        ainda não abriu. `selected`/`first` = linha escolhida (W/S) e a primeira visível (rolagem).
        Hit-test: log_rows (só os lidos) e inv_tab_rects."""
        self._reset_panels()
        self.dim_screen()
        w, h = self.logs_window_size()
        x = (self.w - w) // 2
        y = self.inv_tabs_top()                        # mesmo topo da aba Inventário
        self.window(x, y, w, h, "LOGs encontrados", f"{len(state.logs_read)}/{len(C.LOGS)}", C.C_TERMINAL)
        self._inventory_tabs(x, y, w, TAB_LOGS, state, mouse)
        entries = state.log_entries()
        rows = self.log_visible
        first = max(0, min(first, len(entries) - rows))
        list_y = y + INV_CONTENT_Y + 2
        tag_w = self.font.size(self.NEW_TAG)[0] + 6
        for k, (log, number, read, new) in enumerate(entries[first:first + rows]):
            i = first + k
            row = pygame.Rect(x + 8, list_y + k * LOG_ROW_STEP, w - 16 - (5 if rows < len(entries) else 0), LOG_ROW_H)
            hover = read and row.collidepoint(mouse)
            sel = i == selected
            bg = B_HOVER if hover or (sel and read) else B_CARD if read else B_WELL
            self.round_rect(row, bg, C.C_ACCENT if sel else None)
            color = B_TEXT if read else B_DIM
            self.tx(self.log_row_text(log, number, read), row.x + 6, row.y, color, self.body)
            if new:                                     # selo "NOVO" encostado na direita
                tag = pygame.Rect(row.right - 4 - tag_w, row.y + 3, tag_w, 9)
                self.round_rect(tag, C.C_ACCENT)
                self.tx(self.NEW_TAG, tag.centerx + 1, tag.y - 2, B_DARK_TEXT, align="center")
            if read:
                self.log_rows.append((row, log))
        if rows < len(entries):                         # barra de rolagem na margem direita
            track = pygame.Rect(x + w - 10, list_y, 3, rows * LOG_ROW_STEP - 1)
            self.fill(B_WELL, track)
            thumb_h = max(8, round(track.h * rows / len(entries)))
            thumb_y = track.y + round((track.h - thumb_h) * first / max(1, len(entries) - rows))
            self.fill(C.C_ACCENT, (track.x, thumb_y, 3, thumb_h))
        self.help_line(y + h + 7, [("CLIQUE", "lê de novo"), ("W/S", "escolhe"), ("A/D", "aba"), ("ESC", "fecha")])
        self.notice_y = self.panel_notice_y(y, y + h + HELP_H + 2)

    def _crate_panel(self, crate, cx: int, y: int, pw: int, h: int, item_icon, mouse, mid: pygame.Rect) -> None:
        """Caixa de saque de um destroço (ou contêiner) aberta: tira e guarda (clique = pilha, direito = 1),
        "<< PEGAR TUDO" no meio e, na nave e na sonda, Ler registro (o LOG que apareceu ao abrir)."""
        box = crate.storage
        used = sum(1 for st in box.slots if st)
        self.window(cx, y, pw, h, f"{crate.wreck.name} · caixa", f"{used}/{len(box)}", "#f2a33a")
        self._section_label("CAIXA", cx + 8, y + 16)
        self._grid(box, list(range(len(box))), cx + 8, y + SIDE_GRID_Y, item_icon, mouse)
        line_y = y + SIDE_GRID_Y + SLOT + 4 + (len(box) - 1) // 8 * SLOT_STEP
        if crate.empty:
            vw = self.tx("VAZIA", cx + 8, line_y, C.C_ALERT)
            self.tx("dá pra guardar coisas", cx + 8 + vw + 6, line_y - 2, B_MUTED, self.body)
        else:
            for k, text in enumerate(wrap(self.body, "O saque não reabastece. Dá pra guardar coisas aqui.", GRID_W)[:2]):
                self.tx(text, cx + 8, line_y - 2 + k * 12, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_crate", mouse, not crate.empty, "ghost")
        if crate.wreck.log is not None and crate.wreck.terminal is None:
            log_w = self.font.size("LER REGISTRO")[0] + 12
            self._button(pygame.Rect(cx + 8, y + h - 21, log_w, 15), "Ler registro", "crate_log", mouse)

    def panel_notice_y(self, panel_top: int, below_help: int) -> int:
        """Onde vai o aviso ("Inventário cheio") com um painel aberto: logo abaixo da linha de ajuda,
        se couber sem encostar na hotbar (moldura começa em hotbar_y - 11); senão, em cima do painel.
        Nunca cobre a linha de ajuda nem a hotbar, em qualquer tamanho de interface."""
        if below_help + self.NOTICE_H <= self.hotbar_y - 11 - 2:
            return below_help
        return max(0, panel_top - self.NOTICE_H - 4)

    def _button(self, rect: pygame.Rect, label: str, action: str, mouse, enabled: bool = True,
                kind: str = "ghost") -> None:
        """Botão de painel ("Pegar tudo", "Guardar recursos"). Só entra em `panel_buttons` se estiver ativo."""
        hover = enabled and rect.collidepoint(mouse)
        self.button(rect, label.upper(), kind if enabled else "off", hover=hover)
        if enabled:
            self.panel_buttons.append((rect, action))

    def _pencil(self, x: int, y: int, color: str) -> None:
        """Lapisinho de pixels (6×6): o nome do baú é clicável."""
        c = pygame.Color(color)
        for i in range(5):
            self.surf.fill(c, (x + 1 + i, y + 4 - i, 1, 1))
            self.surf.fill(c, (x + 2 + i, y + 5 - i, 1, 1))
        self.surf.fill(c, (x, y + 5, 2, 1))

    def _chest_panel(self, chest, cx: int, y: int, pw: int, h: int, item_icon, mouse, t: float, editing,
                     mid: pygame.Rect) -> None:
        """Baú: nome (clique edita), os 24 slots, a seção DRONES e, no meio, "GUARDAR RECURSOS >>" e
        "<< PEGAR TUDO"."""
        box = chest.storage
        used = sum(1 for s in box.slots if s)
        self.window(cx, y, pw, h, "", f"{used}/{len(box)}")
        if editing is not None:                       # campo de texto com cursor piscando
            field = pygame.Rect(cx + 4, y + 2, pw - 44, 14)
            self.round_rect(field, B_WELL, C.C_ACCENT)
            w = self.tx(editing.text, field.x + 4, field.y, B_TEXT, self.body) if editing.text else 0
            if (t % C.CHEST_NAME_BLINK) < C.CHEST_NAME_BLINK / 2:
                self.surf.fill(pygame.Color(C.C_TI), (field.x + 5 + w, field.y + 3, 1, 9))
            self.tx(f"{len(editing.text)}/{editing.max_len}", field.right - 3, field.y + 2,
                    C.C_ALERT if editing.full else B_MUTED, align="right")
            self.name_rect = field
        else:
            name = chest.name or C.CHEST_DEFAULT_NAME
            w = self.body.size(name)[0]
            rect = pygame.Rect(cx + 4, y + 2, w + 20, 14)
            hover = rect.collidepoint(mouse)
            if hover:
                self.round_rect(rect, B_HOVER, B_LINE2)
            self.tx(name, cx + 8, y + 2, C.C_ACCENT, self.body)
            self._pencil(cx + 13 + w, y + 6, C.C_TI if hover else B_MUTED)
            self.name_rect = rect
        self._section_label("BAÚ", cx + 8, y + 16)
        self._grid(box, list(range(len(box))), cx + 8, y + SIDE_GRID_Y, item_icon, mouse)
        self._button(mid, ">>\nGUARDAR\nRECURSOS", "store_all", mouse, True, "primary")
        self._button(mid.move(0, 44), "<<\nPEGAR\nTUDO", "take_all", mouse, not box.is_empty(), "ghost")
        self.draw_logistics(cx + 8, y + self._chest_logi_y(chest), GRID_W, chest, item_icon, mouse)

    @staticmethod
    def _chest_logi_y(chest) -> int:
        """y (relativo ao painel) da seção DRONES: logo abaixo da grade, que tem uma linha por 8 slots (3 linhas = 100)."""
        rows = -(-len(chest.storage) // C.CHEST_ROW)
        return 100 - (3 - rows) * SLOT_STEP

    def _drill_panel(self, drill, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str,
                     mid: pygame.Rect) -> None:
        """Drill: o inventário dela (1 slot, só tirar), quanto encheu, "<< PEGAR TUDO" no meio e a seção DRONES."""
        ore = C.RESOURCE_NAME[drill.resource]
        self.window(cx, y, pw, h, f"Drill · {ore}", f"{drill.stored}/{C.DRILL_CAPACITY}", C.C_ACCENT)
        self._section_label("DRILL", cx + 8, y + 16)
        self._grid(drill.storage, list(range(len(drill.storage))), cx + 8, y + SIDE_GRID_Y, item_icon, mouse)
        # barra de enchimento do lado do slot, na cor do minério (cheia: verde)
        bx, bw = cx + 8 + SLOT_STEP + 4, GRID_W - SLOT_STEP - 4
        fill = drill.stored / C.DRILL_CAPACITY
        self.bar(bx, y + SIDE_GRID_Y + 3, bw, fill, "#7ad46a" if drill.full else C.ORE_COLORS[drill.resource][0], h=4)
        self.tx(status, bx, y + SIDE_GRID_Y + 7, C.C_ALERT if drill.full else B_MUTED)
        for k, line in enumerate(wrap(self.body, "Os drones levam daqui o que estiver marcado em Envia.",
                                      GRID_W)[:2]):
            self.tx(line, cx + 8, y + SIDE_GRID_Y + 22 + k * 12, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_drill", mouse, drill.stored > 0, "ghost")
        self.draw_logistics(cx + 8, y + 92, GRID_W, drill, item_icon, mouse)

    def _melter_panel(self, melter, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str,
                      mid: pygame.Rect) -> None:
        """Derretedor (v0.5 M2): entrada de gelo e saída de cápsulas de água, a barra da próxima cápsula, o estado,
        "<< PEGAR TUDO" no meio e a seção DRONES (só Envia: os drones tiram as cápsulas)."""
        t2 = melter.kind.endswith("_t2")
        self.window(cx, y, pw, h, "Derretedor nv.2" if t2 else "Derretedor", f"{melter.capsules} cáps.", C.C_O2)
        gx = cx + 8
        self._section_label("GELO", gx, y + 16)
        self._section_label("CÁPSULA", gx + SLOT_STEP + 18, y + 16, C.C_O2)
        self._grid(melter.storage, [C.MELTER_ICE_SLOT], gx, y + SIDE_GRID_Y, item_icon, mouse)
        self.tx(">", gx + SLOT + 6, y + SIDE_GRID_Y + 3, B_MUTED)
        self._grid(melter.storage, [C.MELTER_CAPSULE_SLOT], gx + SLOT_STEP + 18, y + SIDE_GRID_Y, item_icon, mouse)
        bx = gx + 2 * SLOT_STEP + 26
        bw = GRID_W - (bx - gx)
        working = melter.ice >= C.MELTER_ICE_PER_CAPSULE and melter.capsule_room > 0
        fill = melter.timer / C.MELTER_CAPSULE_TIME[melter.kind] if working else 0.0
        self.bar(bx, y + SIDE_GRID_Y + 3, bw, fill, "#7ad46a" if melter.capsules_full else C.C_O2, h=4)
        self.tx(self.fit(status, bw), bx, y + SIDE_GRID_Y + 7, C.C_ALERT if melter.capsules_full else B_MUTED)
        for k, line in enumerate(wrap(self.body, "Clique no gelo pra pôr. Drones levam as cápsulas.", GRID_W)[:2]):
            self.tx(line, gx, y + SIDE_GRID_Y + 22 + k * 12, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_melter", mouse, not melter.storage.is_empty(), "ghost")
        self.draw_logistics(gx, y + 92, GRID_W, melter, item_icon, mouse)

    def _smelter_panel(self, smelter, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str,
                       mid: pygame.Rect) -> None:
        """Fundição (v0.6 Fundo M3): minério e magmatita (entram), saída (só tira: lingote ou wafer), a barra do item atual, 4
        pontinhos da carga de magmatita acesa, o estado, "<< PEGAR TUDO" no meio e a seção DRONES."""
        out = smelter.storage.slots[C.SMELTER_OUT_SLOT]
        self.window(cx, y, pw, h, "Fundição", f"{out.count if out else 0} prontos", SMELT_COLOR)
        gx, sy = cx + 8, y + SIDE_GRID_Y
        for label, slot, dx, color in (("MINÉRIO", C.SMELTER_ORE_SLOT, 0, B_MUTED),
                                       ("MAGMATITA", C.SMELTER_FUEL_SLOT, 50, B_MUTED),
                                       ("SAÍDA", C.SMELTER_OUT_SLOT, 112, SMELT_COLOR)):
            self._section_label(label, gx + dx, y + 16, color)
            self._grid(smelter.storage, [slot], gx + dx, sy, item_icon, mouse)
        self.tx(">", gx + 88, sy + 3, B_MUTED)
        working = smelter.smelter_blocker is None
        by = sy + SLOT + 6
        bw = GRID_W - 44
        self.bar(gx, by, bw, smelter.timer / C.SMELTER_TIME if working else 0.0, SMELT_COLOR, h=4)
        for k in range(C.SMELTER_BURNS_PER_FUEL):                       # a carga acesa: fuel pontinhos de 4
            self.fill(SMELT_COLOR if k < smelter.fuel else B_TRACK, (gx + bw + 8 + k * 9, by, 6, 4))
        self.tx(self.fit(status, GRID_W), gx, by + 6, B_MUTED if working else C.C_ALERT)
        for k, line in enumerate(wrap(self.body, "Ponha minério e magmatita. Drones levam o que sair.",
                                      GRID_W)[:2]):
            self.tx(line, gx, by + 20 + k * 12, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_smelter", mouse, not smelter.storage.is_empty(), "ghost")
        self.draw_logistics(gx, y + SMELT_LOGI_Y, GRID_W, smelter, item_icon, mouse)

    def _collector_panel(self, m, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str, info: str | None,
                         mid: pygame.Rect) -> None:
        """Coletor de água (v0.8 M2): vazias (entram) e cheias (só tira), a barra da cápsula atual, o estado, o ritmo
        (com a chuva), "<< PEGAR TUDO" no meio e a seção DRONES."""
        out = m.storage.slots[C.COLLECTOR_OUT_SLOT]
        self.window(cx, y, pw, h, "Coletor de água", f"{out.count if out else 0} cheias", C.C_O2)
        gx, sy = cx + 8, y + SIDE_GRID_Y
        self._section_label("VAZIAS", gx, y + 16, B_MUTED)
        self._section_label("CHEIAS", gx + SLOT_STEP + 18, y + 16, C.C_O2)
        self._grid(m.storage, [C.COLLECTOR_IN_SLOT], gx, sy, item_icon, mouse)
        self.tx(">", gx + SLOT + 6, sy + 3, B_MUTED)
        self._grid(m.storage, [C.COLLECTOR_OUT_SLOT], gx + SLOT_STEP + 18, sy, item_icon, mouse)
        bx = gx + 2 * SLOT_STEP + 26
        bw = GRID_W - (bx - gx)
        working = status == "COLETANDO"
        self.bar(bx, sy + 3, bw, min(1.0, m.timer / m.cycle) if working else 0.0, C.C_O2, h=4)
        self.tx(self.fit(status, bw), bx, sy + 7, "#7fd67a" if working else C.C_ALERT)
        for k, line in enumerate(wrap(self.body, info or "", GRID_W)[:2]):
            self.tx(line, gx, sy + 26 + k * 12, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_collector", mouse, not m.storage.is_empty(), "ghost")
        self.draw_logistics(gx, y + COLLECT_LOGI_Y, GRID_W, m, item_icon, mouse)

    def _vbar(self, x: int, y: int, w: int, h: int, frac: float, color: str) -> None:
        """Barra vertical (v0.8 M3): trilho e a parte cheia de baixo pra cima, com 1 px de brilho no topo dela."""
        self.fill(B_TRACK, (x, y, w, h))
        fh = round(h * max(0.0, min(1.0, frac)))
        if fh > 0:
            self.fill(color, (x, y + h - fh, w, fh))
            if fh > 1:
                self.fill(pygame.Color(color).lerp((255, 255, 255), 0.35), (x, y + h - fh, w, 1))

    cultivator_art: list | None = None      # as surfaces do Cultivador aberto (App: Renderer.cultivator_surfaces), de baixo pra cima

    def _cultivator_panel(self, m, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str,
                          mid: pygame.Rect) -> None:
        """Cultivador (v0.8 M3, mock reports/design/v08_plantas/ui_cultivador_A.png). Esquerda: barras ÁGUA (tanque) e CRESCE.
        Centro: o cilindro ×2 com a planta na etapa de agora e o ritmo de biomassa. Direita: COLHEITA (4 slots). Embaixo:
        CHEIAS, VAZIAS e MUDA, a linha de estado, "<< PEGAR TUDO" no meio e a seção DRONES."""
        m.sync_crop()
        crop = C.CROP_NAME.get(m.crop, "").upper() if m.crop else None
        right = f"{crop} · ETAPA {m.crop_stage + 1}/4" if crop else "SEM MUDA"
        self.window(cx, y, pw, h, "Cultivador", right, C.C_ACCENT)
        gx = cx + 8
        top = y + SIDE_GRID_Y + 1
        bar_h = 56
        self._section_label("ÁGUA", gx, y + 16, C.C_O2)
        self._section_label("CRESCE", gx + 30, y + 16, C.C_TI)
        self._vbar(gx, top, 18, bar_h, m.tank / C.CULTIVATOR_TANK, C.C_O2)
        for k in range(1, int(C.CULTIVATOR_TANK)):                         # um risquinho por cápsula
            self.fill(B_WINDOW, (gx, top + round(bar_h * k / C.CULTIVATOR_TANK), 18, 1))
        self._vbar(gx + 34, top, 8, bar_h, m.growth, C.C_TI)
        self.tx(f"{m.tank:.0f}/{C.CULTIVATOR_TANK:.0f}", gx + 9, top + bar_h + 3, B_MUTED, align="center")
        self.tx(f"{m.growth * 100:.0f}%", gx + 38, top + bar_h + 3, B_MUTED, align="center")
        cyl_x, cyl_w = cx + 68, 40                                        # o cilindro: sprite 40×56 ampliado ×2 (nativo)
        if self.cultivator_art:
            art = pygame.Surface((40, 56), pygame.SRCALPHA)
            for surf in self.cultivator_art:
                art.blit(surf, (20 - surf.get_width() // 2, 56 - surf.get_height()))
            self.native.append((pygame.transform.scale_by(art, 2), (cyl_x * 2, (y + 22) * 2)))
        spec = C.CROPS.get(m.crop)
        rate = spec.biomass if spec is not None and status == "Crescendo" else 0.0
        self.tx(f"{rate:g} BIO/S".replace(".", ","), cyl_x + cyl_w / 2, y + 79, "#7fd67a" if rate else B_MUTED, align="center")
        if m.boost > 0:                                                    # v0.8 M5: selo do adubo (min:s) sob o ritmo de biomassa
            sec = int(m.boost + 0.999)
            self.tx(f"ADUBO {sec // 60}:{sec % 60:02d}", cyl_x + cyl_w / 2, y + 90, "#7fd67a", align="center")
        hx = cx + pw - 8 - 2 * SLOT_STEP + 2                              # COLHEITA: 2×2 slots à direita
        self._section_label("COLHEITA", hx, y + 16, C.C_ACCENT)
        self._grid(m.storage, [C.CULT_HARVEST_SLOTS[0], C.CULT_HARVEST_SLOTS[1]], hx, top, item_icon, mouse)
        self._grid(m.storage, [C.CULT_HARVEST_SLOTS[2], C.CULT_HARVEST_SLOTS[3]], hx, top + SLOT_STEP, item_icon, mouse)
        self.tx("1-2 POR", hx, y + 76, B_MUTED)
        self.tx("COLHEITA", hx, y + 85, B_MUTED)
        ry = y + 104
        self._section_label("CHEIAS", gx, ry, C.C_O2)
        self._section_label("VAZIAS", gx + SLOT_STEP + 18, ry, B_MUTED)
        self._section_label("MUDA", gx + 2 * SLOT_STEP + 36, ry, C.C_ACCENT)
        self._grid(m.storage, [C.CULT_WATER_SLOT], gx, ry + 10, item_icon, mouse)
        self._grid(m.storage, [C.CULT_EMPTY_SLOT], gx + SLOT_STEP + 18, ry + 10, item_icon, mouse)
        self._grid(m.storage, [C.CULT_SEED_SLOT], gx + 2 * SLOT_STEP + 36, ry + 10, item_icon, mouse)
        self.tx(self.fit(status, GRID_W), gx, y + 138, "#7fd67a" if status == "Crescendo" else C.C_ALERT, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_cultivator", mouse,
                     any(m.storage.slots[i] is not None for i in (C.CULT_EMPTY_SLOT, *C.CULT_HARVEST_SLOTS)), "ghost")
        self.draw_logistics(gx, y + CULT_LOGI_Y, GRID_W, m, item_icon, mouse)

    machine_art: pygame.Surface | None = None   # v0.8 M4: o sprite 40×56 do Microscópio/Centrífuga aberto (App.panel_machine_art)

    def _lab_machine(self, gx: int, y: int) -> None:
        """O cartão do meio com a máquina ×2 (v0.8 M4, mock A): 44×66 em gx+68, o sprite 40×56 ampliado no nativo."""
        x = gx + 68
        self.card(x, y + 22, 44, 66, B_WELL, B_LINE2, shadow=False)
        if self.machine_art is not None:
            self.native.append((pygame.transform.scale_by(self.machine_art, 2), ((x + 2) * 2, (y + 26) * 2)))

    def _lab_bar(self, gx: int, y: int, label: str, frac: float, working: bool) -> None:
        """A barra vertical do trabalho (9×56) em gx+44, com o rótulo em cima e o % embaixo (v0.8 M4, mock A; o mock
        punha em gx+40, mas o "AMOSTRA" da Centrífuga na fonte do jogo encostava nela)."""
        top = y + SIDE_GRID_Y + 1
        self._section_label(label, max(gx + 27, gx + 48 - self.font.size(label)[0] // 2), y + 16, LAB_OK)
        self._vbar(gx + 44, top, 9, 56, frac, LAB_OK if working else B_DIM)
        self.tx(f"{frac * 100:.0f}%", gx + 48, top + 59, B_TEXT if working else B_MUTED, align="center")

    def _lab_output(self, inv, slot: int, x: int, y: int, name: str, pct: str, color, item_icon, mouse,
                    lit: bool = True, ring: bool = True) -> None:
        """Um slot de saída com a legenda de 2 linhas ao lado (nome e chance). `lit` False: tudo apagado; `ring`: a borda
        do slot na cor (a planta que a amostra atual dá)."""
        self._grid(inv, [slot], x, y, item_icon, mouse)
        if lit and ring and color is not None:
            self.round_rect((x - 1, y - 1, SLOT + 2, SLOT + 2), (0, 0, 0, 0), color)
        self.tx(name, x + 24, y + 1, (color or B_MUTED) if lit else B_MUTED)
        self.tx(pct, x + 24, y + 10, (color or B_MUTED) if lit else B_DIM)

    def _microscope_panel(self, m, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str, info: str | None,
                          mid: pygame.Rect) -> None:
        """Microscópio (v0.8 M4, mock reports/design/v08_m4_paineis/ui_microscopio_A.png). Esquerda: GELO e o tempo da
        análise; a barra ANÁLISE; no meio a máquina ×2; à direita as 3 amostras (slot fixo cada) com a chance. Embaixo a
        faixa CHANCE POR GELO (NADA 50% em cinza), o estado, a explicação, "<< PEGAR TUDO" (só as amostras) e DRONES."""
        samples = sum(m.storage.count(s) for s in C.MIC_OUT_SLOTS)
        self.window(cx, y, pw, h, "Microscópio", f"{samples} AMOSTRA{'S' if samples != 1 else ''}", C.C_O2)
        gx = cx + 8
        top = y + SIDE_GRID_Y + 1
        working = status == "Analisando"
        self._section_label("GELO", gx, y + 16, C.C_O2)
        self._grid(m.storage, [C.MIC_ICE_SLOT], gx, top, item_icon, mouse)
        self.tx(f"{C.MICROSCOPE_TIME:g} S", gx, top + 24, B_TEXT)
        self._lab_bar(gx, y, "ANÁLISE", m.timer / C.MICROSCOPE_TIME, working)
        self._lab_machine(gx, y)
        hx = gx + 114
        self._section_label("SAÍDA", hx, y + 16, C.C_TI)
        odds = dict(C.MICROSCOPE_ODDS)
        for k, item in enumerate(C.MIC_OUT_SLOTS):
            self._lab_output(m.storage, C.MIC_OUT_SLOTS[item], hx, top + k * 23, SAMPLE_SHORT[item],
                             f"{odds[item] * 100:.0f}%", SAMPLE_COLOR[item], item_icon, mouse, ring=False)
        self._section_label("CHANCE POR GELO", gx, y + 98)
        nothing = 1.0 - sum(odds.values())
        segs = [(nothing, B_DIM)] + [(odds[i], SAMPLE_COLOR[i]) for i in C.MIC_OUT_SLOTS]
        sx, sy = gx, y + 108
        for k, (frac, color) in enumerate(segs):
            sw = round(GRID_W * frac) if k < len(segs) - 1 else gx + GRID_W - sx
            self.fill(color, (sx, sy, sw, 10))
            self.fill(pygame.Color(color).lerp((255, 255, 255), 0.3), (sx, sy, sw, 1))
            if k:
                self.fill(B_WELL, (sx, sy, 1, 10))
            sx += sw
        self.tx(f"NADA {nothing * 100:.0f}%", gx + 4, sy, B_TEXT)
        self.tx(self.fit(status, GRID_W), gx, y + 121, LAB_OK if working else C.C_ALERT, self.body)
        self.tx(self.fit(info or "", GRID_W), gx, y + 134, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_microscope", mouse, samples > 0, "ghost")
        self.draw_logistics(gx, y + MIC_LOGI_Y, GRID_W, m, item_icon, mouse)

    def _centrifuge_panel(self, m, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str, info: str | None,
                          mid: pygame.Rect) -> None:
        """Centrífuga (v0.8 M4, mock reports/design/v08_m4_paineis/ui_centrifuga_A.png). Esquerda: ALGA e AMOSTRA; a
        barra CICLO; no meio a máquina ×2; à direita as 3 plantas, acesa só a que a amostra atual dá. Embaixo o cartão da
        amostra (some sem amostra), o estado, a explicação, "<< PEGAR TUDO" (só as plantas) e DRONES."""
        plants = sum(m.storage.count(p) for p in C.CENT_OUT_SLOTS)
        self.window(cx, y, pw, h, "Centrífuga", f"{plants} PLANTA{'S' if plants != 1 else ''}", C.C_TI)
        gx = cx + 8
        top = y + SIDE_GRID_Y + 1
        working = status == "Girando"
        stack = m.storage.slots[C.CENT_SAMPLE_SLOT]
        sample = stack.item if stack is not None and stack.item in C.CENTRIFUGE_RECIPES else None
        self._section_label("ALGA", gx, y + 16, LAB_OK)
        self._grid(m.storage, [C.CENT_ALGAE_SLOT], gx, top, item_icon, mouse)
        self._section_label("AMOSTRA", gx, y + 51, C.C_O2)
        self._grid(m.storage, [C.CENT_SAMPLE_SLOT], gx, y + 61, item_icon, mouse)
        if sample is not None:
            self.round_rect((gx - 1, y + 60, SLOT + 2, SLOT + 2), (0, 0, 0, 0), C.C_ACCENT)
        self._lab_bar(gx, y, "CICLO", m.timer / C.CENTRIFUGE_TIME, working)
        self._lab_machine(gx, y)
        hx = gx + 114
        self._section_label("SAÍDA", hx, y + 16, C.C_TI)
        chance = {plant: pct for plant, pct in C.CENTRIFUGE_RECIPES.values()}
        active = C.CENTRIFUGE_RECIPES[sample][0] if sample else None
        for k, plant in enumerate(C.CENT_OUT_SLOTS):
            lit = plant == active
            self._lab_output(m.storage, C.CENT_OUT_SLOTS[plant], hx, top + k * 23, C.RESOURCE_LABEL[plant],
                             f"{chance[plant] * 100:.0f}%", SAMPLE_COLOR[sample] if lit else None, item_icon, mouse, lit)
        if sample is not None:                       # o cartão da amostra atual: o que ela dá e a chance
            plant, pct = C.CENTRIFUGE_RECIPES[sample]
            color = SAMPLE_COLOR[sample]
            ry = y + 96
            self.round_rect((gx, ry, GRID_W, 26), B_CARD, pygame.Color(B_CARD).lerp(pygame.Color(color), 0.6))
            self.native.append((item_icon(sample), ((gx + 5) * 2, (ry + 5) * 2)))
            pct_w = self.font.size(f"{pct * 100:.0f}%")[0]
            self.tx(self.fit(f"Amostra {SAMPLE_SHORT[sample].lower()}", GRID_W - 34 - pct_w), gx + 26, ry + 1, color, self.body)
            self.tx(self.fit(f"dá {C.CROP_NAME[plant]}", GRID_W - 34 - pct_w), gx + 26, ry + 12, B_TEXT, self.body)
            self.tx(f"{pct * 100:.0f}%", gx + GRID_W - 6, ry + 9, color, align="right")
        sw = self.tx(self.fit(status, GRID_W), gx, y + 121, LAB_OK if working else C.C_ALERT, self.body)
        rate = f"{C.CENTRIFUGE_TIME:g} s por ciclo"
        if sw + 12 + self.body.size(rate)[0] <= GRID_W:
            self.tx(rate, gx + max(56, sw + 12), y + 121, B_MUTED, self.body)
        self.tx(self.fit(info or "", GRID_W), gx, y + 135, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_centrifuge", mouse, plants > 0, "ghost")
        self.draw_logistics(gx, y + CENT_LOGI_Y, GRID_W, m, item_icon, mouse)

    def _dispenser_panel(self, m, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str, info: str | None,
                         mid: pygame.Rect) -> None:
        """Dispersor de O₂ (v0.5 M2): o slot da cápsula de água, o das vazias (v0.8 M2, só tira), a barra da cápsula que
        está sendo gasta, o estado (Vedado ✓ / Vazamento / Sem água / Sem energia), a explicação do estado e "<< PEGAR" no meio."""
        self.window(cx, y, pw, h, "Dispersor de O₂", f"{m.capsules} cáps.", C.C_O2)
        gx = cx + 8
        self._section_label("CHEIAS", gx, y + 16, C.C_O2)
        self._section_label("VAZIAS", gx + SLOT_STEP + 18, y + 16, B_MUTED)
        self._grid(m.storage, [C.DISPENSER_CAPSULE_SLOT], gx, y + SIDE_GRID_Y, item_icon, mouse)
        self.tx(">", gx + SLOT + 6, y + SIDE_GRID_Y + 3, B_MUTED)
        self._grid(m.storage, [C.DISPENSER_EMPTY_SLOT], gx + SLOT_STEP + 18, y + SIDE_GRID_Y, item_icon, mouse)
        bx = gx + 2 * SLOT_STEP + 26
        bw = GRID_W - (bx - gx)
        total = dispenser_capsule_time(len(m.seal.floor)) if m.seal is not None and m.seal.ok else C.DISPENSER_CAPSULE_TIME
        self.bar(bx, y + SIDE_GRID_Y + 3, bw, min(1.0, m.burn / total), C.C_O2, h=4)
        ok = status.startswith("VEDADO")
        self.tx(self.fit(status, bw), bx, y + SIDE_GRID_Y + 7, "#7fd67a" if ok else C.C_ALERT)
        for k, line in enumerate(wrap(self.body, info or "", GRID_W)[:3]):
            self.tx(line, gx, y + SIDE_GRID_Y + 26 + k * 12, B_MUTED, self.body)
        self._button(mid, "<<\nPEGAR\nTUDO", "take_dispenser", mouse, not m.storage.is_empty(), "ghost")
        self.draw_logistics(gx, y + DISP_LOGI_Y, GRID_W, m, item_icon, mouse)

    def _station_panel(self, machine, cx: int, y: int, pw: int, h: int, item_icon, mouse, status: str,
                       info: str | None, mid: pygame.Rect) -> None:
        """Estação: os 4 slots de drone (travados em voo), o buffer como slots (só tirar) e o estado."""
        from game import drones                      # (import local, como os outros da UI)
        st = machine.station
        self.window(cx, y, pw, h, "Estação de drones", f"{len(st.drones)}/{C.STATION_DRONE_SLOTS}", C.C_O2)
        self._section_label("DRONES", cx + 8, y + 16, C.C_O2)
        self.tx("ALCANCE: ESTA CAMADA", cx + pw - 8, y + 16, B_MUTED, align="right")
        n = C.STATION_DRONE_SLOTS
        margin = 6
        step = (GRID_W - 2 * margin - SLOT) // (n - 1)    # espalhados na largura: cabe "POUSADO" embaixo de cada
        for slot in range(n):
            sx, sy = cx + 8 + margin + slot * step, y + SIDE_GRID_Y
            rect = pygame.Rect(sx, sy, SLOT, SLOT)
            drone = st.drone_in(slot)
            self.draw_slot(sx, sy, None, item_icon, hover=rect.collidepoint(mouse))
            if drone is not None:
                icon = item_icon(drones.item_of(drone))     # v0.8 M5: o ícone do tier
                if drone.busy:                         # em viagem: travado, ícone apagado e moldura azul
                    icon = icon.copy()
                    icon.set_alpha(90)
                    self.round_rect((sx - 1, sy - 1, SLOT + 2, SLOT + 2), (0, 0, 0, 0), C.C_O2)
                    self.tx("EM VOO", sx + SLOT / 2, sy + SLOT + 1, C.C_O2, align="center")
                else:
                    self.tx("POUSADO", sx + SLOT / 2, sy + SLOT + 1, B_MUTED, align="center")
                self.native.append((icon, (sx * 2 + 4, sy * 2 + 4)))
            else:
                self.tx("VAZIO", sx + SLOT / 2, sy + SLOT + 1, B_DIM, align="center")
            self.bay_rects.append((rect, slot))
        by = y + 62
        stacks = st.buffer_stacks()
        if stacks:                                     # sobras do buffer antigo (save ≤ v4): só tirar
            self.fill(B_LINE, (cx + 8, by - 2, GRID_W, 1))
            self._section_label("SOBRAS (SÓ TIRAR)", cx + 8, by - 1)
            for k in range(len(C.RESOURCES)):
                sx, sy = cx + 8 + k * SLOT_STEP, by + 9
                rect = pygame.Rect(sx, sy, SLOT, SLOT)
                stack = Stack(*stacks[k]) if k < len(stacks) else None
                self.draw_slot(sx, sy, stack, item_icon, hover=stack is not None and rect.collidepoint(mouse))
                if stack is not None:
                    self.buffer_rects.append((rect, stack.item))
            self._button(mid, "<<\nPEGAR\nTUDO", "take_buffer", mouse, True, "ghost")
        else:                                          # o lugar vira a dica de como a logística funciona
            tip = ("Os drones levam itens de quem ENVIA pra quem RECEBE, na camada da estação. "
                   "Configure no painel de cada baú e drill (seção DRONES).")
            for k, line in enumerate(wrap(self.body, tip, GRID_W)[:5]):
                self.tx(line, cx + 8, by + k * 12, B_MUTED, self.body)
        if info:                                       # o que está debaixo do mouse (no lugar do tooltip)
            self.tx(self.fit(info, GRID_W), cx + 8, y + h - 30, C.C_TI, self.body)
        self.tx(status, cx + 8, y + h - 16, B_TEXT, self.body)

    # ---- seção DRONES do baú/drill: Envia, Recebe e Lote (bloco autocontido: desenho + hit-test) ----
    def _toggle(self, rect: pygame.Rect, item: str, active: bool, color: str, item_icon, mouse) -> None:
        """O ícone do material é o botão: aceso = fundo tingido, borda e filete de baixo na cor da linha
        (laranja no Envia, ciano no Recebe), ícone cheio; apagado = fundo escuro e ícone escurecido."""
        hover = rect.collidepoint(mouse)
        if active:
            c = pygame.Color(color)
            self.round_rect(rect, (c.r, c.g, c.b, 46), color)
            self.fill(color, (rect.x + 2, rect.bottom - 2, rect.w - 4, 1))
        else:
            self.round_rect(rect, B_WELL, B_LINE2 if hover else B_LINE)
        if hover:
            self.fill((255, 255, 255, 22), rect.inflate(-2, -2))
        icon = item_icon(item)
        if not active:
            icon = self.dark_icon(icon, 90)
        off = (rect.w - 16) // 2
        self.native.append((icon, ((rect.x + off) * 2, (rect.y + off - (1 if active else 0)) * 2)))

    def logistics_summary(self, machine, short: bool = False) -> str:
        """O que vai no título da seção DRONES: "envia ferro", "envia ferro · recebe gelo", "nada configurado".
        `short` usa os nomes curtos (cápsula em vez de cápsula de água) quando o título não cabe."""
        def names(chosen):
            return [(SHORT_NAME.get(i) if short else None) or C.RESOURCE_NAME[i] for i in C.LOGISTIC_ITEMS if i in chosen]
        parts = []
        if machine.sends:
            parts.append("envia " + ", ".join(names(machine.sends)))
        if machine.receives:
            parts.append("recebe " + ", ".join(names(machine.receives)))
        return " · ".join(parts) if parts else "nada configurado"

    def logistics_height(self, machine) -> int:
        """Altura da seção DRONES dessa máquina: uma linha por Envia/Recebe que ela tem, mais o Lote se ela envia.
        Quem precisa de chip nunca fica abaixo de 2 linhas, pro painel não pular de tamanho quando o chip entra."""
        from game import drones
        rows = 0
        for allowed in (drones.can_send, drones.can_receive):
            n = len([i for i in C.LOGISTIC_ITEMS if allowed(machine, i)])
            rows += 0 if n == 0 else wide_row_height(n) if n > LOGI_WIDE_AFTER else -(-n // logi_row_cap(machine)) * LOGI_ROW
        batch = 2 + LOGI_BATCH_H if any(drones.can_send(machine, i) for i in C.LOGISTIC_ITEMS) else 0
        height = 14 + rows + batch
        return max(height, 14 + 2 * LOGI_ROW) if machine.needs_chip else height

    def chip_at(self, pos):
        """A máquina cujo slot de chip está debaixo de `pos` (coordenadas da UI), ou None."""
        return next((m for r, m in self.chip_rects if r.collidepoint(pos)), None)

    def _chip_slot(self, x: int, y: int, machine, item_icon, mouse) -> None:
        """O slot do chip (v0.6 M2) com a legenda CHIP embaixo. Vazio mostra a silhueta `chip_slot_empty`."""
        rect = pygame.Rect(x, y, SLOT, SLOT)
        self.draw_slot(x, y, None, item_icon, hover=rect.collidepoint(mouse))
        icon = item_icon("chip" if machine.chip else "chip_slot_empty")
        self.native.append((icon, ((x + 2) * 2, (y + 2) * 2)))
        self.tx("CHIP", x + SLOT / 2, y + SLOT + 1, B_TEXT if machine.chip else B_DIM, align="center")
        self.chip_rects.append((rect, machine))

    def draw_logistics(self, x: int, y: int, w: int, machine, item_icon, mouse) -> None:
        """Seção "DRONES" a partir de (x, y), largura `w`, uma coisa por linha:

            DRONES · envia ferro                 [chip]
            Envia    [fe][si][ge]
            Recebe   [fe][si][ge]
            Lote     [1][5][10][20]

        Só entra a linha que a máquina pode ter (a drill não tem Recebe, o dispersor não tem Envia nem Lote).
        Com mais de LOGI_WIDE_AFTER materiais (o baú tem 16) a fileira vira larga: botões 16×16, 10 por linha, na grade; o
        rótulo vai no vão da última linha (ou sobe pra uma linha própria se não houver vão).
        Quem precisa de chip mostra o slot dele à direita; sem chip, no lugar das linhas vai o texto
        "Coloque um chip pra ligar aos drones". Guarda os botões em `logistics_buttons`."""
        from game import drones                      # (import local: a UI não depende da lógica no topo)
        self.fill(B_LINE, (x, y, w, 1))
        label_w = self._section_label("DRONES", x, y + 1, C.C_O2)
        if machine.needs_chip:
            self._chip_slot(x + w - SLOT, y + 14, machine, item_icon, mouse)
            if not machine.chip:
                for k, line in enumerate(wrap(self.body, "Coloque um chip pra ligar aos drones", w - SLOT - 8)[:2]):
                    self.tx(line, x, y + 16 + k * 12, B_MUTED, self.body)
                return
        summary = self.logistics_summary(machine)
        room = w - label_w - 4
        if self.body.size("· " + summary)[0] > room:            # comprido: nomes curtos, depois só as quantidades
            summary = self.logistics_summary(machine, short=True)
        if self.body.size("· " + summary)[0] > room:
            parts = []
            if machine.sends:
                parts.append(f"envia {len(machine.sends)}")
            if machine.receives:
                parts.append(f"recebe {len(machine.receives)}")
            summary = " · ".join(parts)
        sw = self.tx("· " + summary, x + label_w + 4, y - 1, C.C_TI if drones.configured(machine) else B_MUTED,
                     self.body)
        self.header_rects.append(pygame.Rect(x + label_w + 4, y + 2, sw, 10))
        col = x + LOGI_COL
        ry = y + 14
        rows = [("Envia", "send", machine.sends, C.C_ACCENT, drones.can_send),
                ("Recebe", "recv", machine.receives, C.C_O2, drones.can_receive)]
        for label, kind, chosen, color, allowed in rows:
            items = [i for i in C.LOGISTIC_ITEMS if allowed(machine, i)]
            if not items:
                continue
            wide = len(items) > LOGI_WIDE_AFTER
            if wide:                                     # o baú: botões 16×16, 10 por linha, na largura da grade
                inline = wide_label_inline(len(items))
                top = ry if inline else ry + 9
                lines = -(-len(items) // LOGI_WIDE_COLS)
                if inline:                               # rótulo no vão à direita da última linha (curta)
                    last = len(items) % LOGI_WIDE_COLS or LOGI_WIDE_COLS
                    self.tx(label, x + last * (LOGI_WIDE_BTN + LOGI_WIDE_GAP) + 6,
                            top + (lines - 1) * (LOGI_WIDE_BTN + 2) + 1, B_MUTED, self.body)
                else:
                    self.tx(label, x, ry - 3, B_MUTED, self.body)
                row = [pygame.Rect(x + (k % LOGI_WIDE_COLS) * (LOGI_WIDE_BTN + LOGI_WIDE_GAP),
                                   top + (k // LOGI_WIDE_COLS) * (LOGI_WIDE_BTN + 2), LOGI_WIDE_BTN, LOGI_WIDE_BTN)
                       for k in range(len(items))]
            else:
                self.tx(label, x, ry + 2, B_MUTED, self.body)
                cap = logi_row_cap(machine)
                row = [pygame.Rect(col + (k % cap) * (LOGI_BTN + 3), ry + (k // cap) * LOGI_ROW, LOGI_BTN, LOGI_BTN)
                       for k in range(len(items))]
            for rect, item in zip(row, items):
                self._toggle(rect, item, item in chosen, color, item_icon, mouse)
                self.logistics_buttons.append((rect, (kind, item)))
            ry += wide_row_height(len(items)) if wide else -(-len(items) // logi_row_cap(machine)) * LOGI_ROW
        if not any(drones.can_send(machine, i) for i in C.LOGISTIC_ITEMS):
            return                                   # quem só recebe não tem Lote ("quanto o drone tira daqui")
        ry += 2
        self.tx("Lote", x, ry + 1, B_MUTED, self.body)
        for k, amount in enumerate(C.DRONE_BATCH_OPTIONS):
            rect = pygame.Rect(col + k * (LOGI_BTN + 3), ry, LOGI_BTN, LOGI_BATCH_H)
            active, hover = amount == machine.batch, rect.collidepoint(mouse)
            self.round_rect(rect, B_HOVER if active or hover else B_WELL, C.C_ACCENT if active else B_LINE)
            self.tx(str(amount), rect.centerx, ry, B_TEXT if active else B_MUTED, self.body, "center")
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
            top = ay - C.CHEST_SPRITE_SIZES[chest.kind][1] - 2                 # logo acima da tampa (mundo)
            sx, sy = self.world_to_ui((ax, top), cam, zoom)
            x, y = int(sx - w / 2), int(sy - 15)
            while any(r.colliderect((x, y, w, 14)) for r in placed):   # baús vizinhos: empilha
                y -= 15
            placed.append(pygame.Rect(x, y, w, 14))
            if not (-w < x < self.w and -14 < y < self.h):
                continue
            self.chest_label_rects.append(pygame.Rect(x, y, w, 14))
            self.panel(x, y, w, 14, (15, 17, 25, 220))
            px = x + 4
            for n, ((kind, value), pw) in enumerate(zip(parts, widths)):
                if kind == "icon":
                    self.native.append((icons[value], (px * 2, (y + 3) * 2)))
                elif kind == "arrow":
                    self._label_arrow(px, y + 4, value == "down")
                else:
                    self.tx(value, px, y + 1, B_TEXT, self.body)
                px += pw + (gaps[n] if n < len(gaps) else 0)

    def draw_dispenser_labels(self, labels, cam: tuple[int, int], zoom: float) -> None:
        """O estado do Dispersor escrito em cima dele ("Vedado ✓", "Vazamento", "Sem água", "Sem energia") só com o mouse
        em cima; sem hover e parado por problema, só um selo "!" na cor do estado. Preso no mundo (acompanha o zoom),
        letra de tamanho fixo, com a bolinha da cor do estado."""
        for m, state, hover in labels:
            text = C.STATE_LABEL[state]
            w = self.body.size(text)[0] + 16 if hover else 10
            ax, ay = m.anchor
            sx, sy = self.world_to_ui((ax, ay - C.DISPENSER_SPRITE_SIZE[1] - 2), cam, zoom)
            x, y = int(sx - w / 2), int(sy - 15)
            if not (-w < x < self.w and -14 < y < self.h):
                continue
            if not hover:
                self.panel(x, y, w, 14, (15, 17, 25, 220))
                self.tx("!", x + w / 2, y + 1, C.STATE_COLOR[state], self.body, "center")
                continue
            self.panel(x, y, w, 14, (15, 17, 25, 220))
            self.native.append((self._dot_icon(C.STATE_COLOR[state]), ((x + 4) * 2, (y + 5) * 2)))
            self.tx(text, x + 12, y + 1, B_TEXT, self.body)

    def _dot_icon(self, color: str) -> pygame.Surface:
        """Bolinha 3×3 (resolução cheia: 6×6) da cor do estado, no cache."""
        cache = self.__dict__.setdefault("_dots", {})
        if color not in cache:
            dot = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.rect(dot, color, (0, 0, 6, 6), border_radius=2)
            cache[color] = dot
        return cache[color]

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
            self.draw_tooltip_box(rect, label)

    def draw_tooltip_box(self, rect: pygame.Rect, label: str) -> None:
        self.round_rect(rect, (11, 13, 20, 255), B_LINE2)     # opaco: o número da pilha vizinha não vaza
        self.tx(label, rect.x + 6, rect.y + (rect.h - 16) // 2, B_TEXT, self.body)

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
                   *(r for r, _ in self.buffer_rects), *(r for r, _ in self.map_markers)]
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
            self.surf.fill(pygame.Color(B_MUTED), (cx - row, y + k, 2 * row + 1, 1))

    # ---- terminal -------------------------------------------------------------
    def draw_terminal(self, index: int, t: float) -> None:
        dw, dh = min(self.w - 36, 560), 92        # largura limitada: linha comprida demais cansa de ler
        dx, dy = (self.w - dw) // 2, self.h - 100
        self.card(dx, dy, dw, dh, (10, 16, 13, 240), "#1f3a2c")
        self.fill(C.C_TERMINAL, (dx, dy + 1, 2, dh - 2))
        self.tx(f"{C.LOG_TITLES[index]} · {C.log_label(index)}", dx + 10, dy + 4, C.C_TERMINAL)
        for i, line in enumerate(wrap(self.body, C.LOGS[index], dw - 20)):
            self.tx(line, dx + 10, dy + 16 + i * 13, "#d6eadf", self.body)
        if (t * 9) % 10 < 6:
            label_w = self.body.size("continuar")[0]
            kx = dx + dw - 10 - label_w - 3 - self.key_cap_width("E")
            self.key_cap(kx, dy + dh - 15, "E")
            self.tx("continuar", dx + dw - 10, dy + dh - 17, C.C_TERMINAL, self.body, "right")

    # ---- banner de estágio ----------------------------------------------------
    @property
    def BANNER_GAP(self) -> tuple[int, int]:
        """Vão livre no topo, entre a coluna da esquerda (O₂ e objetivo) e o painel do Ti, em px da UI."""
        return 6 + self.objective_w, self.ti_panel_x

    def draw_banner(self, stage: int, alpha: float) -> None:
        """Faixa compacta no topo da tela (fora da área de jogo): título em cima, subtítulo embaixo."""
        s = C.STAGES[stage - 1]
        color = C.STAGE_COLOR[stage]
        left, right = self.BANNER_GAP
        max_w = right - left - 6                      # 3 px de folga de cada painel (o texto mais comprido cabe no Grande)
        w = min(max_w, max(self.font.size(s.title)[0], self.body.size(s.subtitle)[0]) + 16)
        h = 30
        x, y = (left + right) // 2 - w // 2, 6
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        self.card(0, 0, w, h, B_WINDOW, B_LINE, shadow=False, target=layer)
        layer.fill(pygame.Color(color), (2, 1, w - 4, 1))
        self.text(s.title, w / 2, 3, color, self.font, "center", target=layer, shadow=False)
        self.text(s.subtitle, w / 2, 13, B_TEXT, self.body, "center", target=layer, shadow=False)
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
            text = trip.text or ("Descendo..." if trip.to == "cave" else "Subindo...")
            self.text(text, self.w / 2, self.h / 2 - 6, "#d9cfc4", self.body, "center")

    # ---- fim do MVP -----------------------------------------------------------
    def draw_end(self, state: GameState, t: float) -> None:
        self.fill((6, 12, 6, 200), (0, 0, self.w, self.h))
        w, h = 340, 190
        x, y = (self.w - w) // 2, (self.h - h) // 2          # no centro (no Grande: 70, 40)
        self.card(x, y, w, h, B_WINDOW, B_LINE)
        self.fill(C.STAGE_COLOR[C.GREEN_STAGE], (x + 2, y + 1, w - 4, 1))
        self.tx("FIM DO MVP", self.w / 2, y + 10, C.STAGE_COLOR[C.GREEN_STAGE], self.font_big, "center")
        body = ("O primeiro verde brotou na cratera. A Colônia Hesper tentou e sumiu; "
                "tu chegou até aqui. O que tem dentro do gelo fica pra próxima.")
        for i, line in enumerate(wrap(self.body, body, w - 40)):
            self.tx(line, self.w / 2, y + 40 + i * 13, "#d6eadf", self.body, "center")
        minutes, seconds = divmod(int(state.play_time), 60)
        stats = [("TEMPO", f"{minutes}:{seconds:02d}"), ("MAQUINAS", str(sum(not m.broken for m in state.machines))),
                 ("TI", fmt(state.ti)), ("LOGS", f"{len(state.logs_read)}/{len(C.LOGS)}")]
        for i, (label, value) in enumerate(stats):
            sx = x + 30 + i * 74
            self.round_rect((sx, y + 92, 60, 32), B_CARD)
            self.tx(label, sx + 30, y + 93, B_MUTED, align="center")
            self.tx(value, sx + 30, y + 106, C.C_TI, self.body_big, "center")
        self.tx("Obrigado por testar o v0.3", self.w / 2, y + 136, "#a6e07a", self.body, "center")
        if (t * 9) % 10 < 6:
            self.help_line(y + h - 18, [("ENTER", "continuar explorando")], center=self.w / 2)

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
        ("E · CLIQUE · R", "Construtor na mão: menu · construir · girar"),
        ("M", "Mapa (com o scanner de navegação)"),
        ("TAB", "Inventário e LOGs (A/D: aba)"),
        ("SEGURAR DIREITO", "Desmontar (a receita volta pro inventário)"),
        ("ESC", "Cancelar / fechar / pausar"),
        ("+ / -", "Aproximar / afastar (ou Ctrl+rodinha)"),
        ("F11 · ALT+ENTER", "Tela cheia"),
        ("ESC > OPÇÕES", "Tamanho da interface (HUD e menus)"),
        ("F1 · F2 · F3 · F4", "Debug: x10 · +10.000 Ti · rápido · gelo da cratera"),
        ("F5", "Contador de FPS e ms do quadro"),
        ("F7", "Debug: +500 de biomassa"),
    ]

    def _pause_frame(self, x, y, w, h, title, right: str | None = "PAUSA") -> None:
        self.fill((6, 4, 3, 150), (0, 0, self.w, self.h))
        self.window(x, y, w, h, title, right)

    def _menu_row(self, rect: pygame.Rect, selected: bool, enabled: bool = True) -> None:
        """Linha de menu do estilo B: a escolhida ganha o fundo claro e a barrinha laranja à esquerda."""
        if selected:
            self.round_rect(rect, B_HOVER)
            self.fill(C.C_ACCENT, (rect.x, rect.y + 2, 2, rect.h - 4))
        else:
            self.round_rect(rect, B_CARD if enabled else B_WELL)

    def menu_row(self, rect: pygame.Rect, selected: bool, enabled: bool = True) -> None:
        self._menu_row(rect, selected, enabled)

    # linhas de "escolha" das Opções, depois dos volumes (segmentos, Enter/clique/A/D trocam o valor)
    OPTION_ROWS = ("TELA CHEIA", "ZOOM", "INTERFACE")

    def option_segments(self, mix: dict) -> list[tuple[list[str], list, object]]:
        """(rótulos, valores, valor atual) dos 3 controles segmentados das Opções. A Interface vai na ordem da
        lista (Grande, Média, Pequena): A anda pra esquerda e D pra direita, igual ao teclado de sempre."""
        from game import viewport
        sizes = list(viewport.UI_SIZES)
        size_names = {"grande": "Grande", "media": "Média", "pequena": "Pequena"}
        return [(["Não", "Sim"], [False, True], bool(mix.get("fullscreen"))),
                ([zoom_label(z) for z in C.ZOOM_LEVELS], list(C.ZOOM_LEVELS), mix.get("zoom", C.ZOOM_DEFAULT)),
                ([size_names.get(s, s) for s in sizes], sizes, mix.get("ui_size", "media"))]

    def draw_pause(self, screen: str, selected: int, mix: dict, zoom_label: str = "1×",
                   ui_label: str = "MÉDIA", page: int = 0) -> None:
        """Menu de pausa. screen = 'main', 'volumes' (Opções: volumes, tela cheia, zoom, interface)
        ou 'controls'. `mix` é o dicionário das settings (volumes, "fullscreen", "zoom", "ui_size")."""
        self.pause_items.clear()
        self.pause_sliders.clear()
        self.pause_segments.clear()
        self.pause_page_buttons.clear()
        self.header_rects.clear()
        if screen == "main":
            ox, oy = self.center_offset                   # menus feitos pra 480×270, centralizados
            x, y, w = 170 + ox, 64 + oy, 140
            h = 22 + 22 * len(self.PAUSE_OPTIONS) + 4
            self._pause_frame(x, y, w, h, "Pausa", None)
            for i, label in enumerate(self.PAUSE_OPTIONS):
                row = pygame.Rect(x + 6, y + 22 + i * 22, w - 12, 19)
                self._menu_row(row, i == selected)
                self.tx(label, row.x + 8, row.y + 2, B_TEXT if i == selected else B_MUTED, self.body)
                self.pause_items.append(row)
            self.help_line(y + h + 7, [("W/S", "escolhe"), ("ENTER", "ok"), ("ESC", "volta")])
        elif screen == "volumes":
            self._draw_options(selected, mix)
        else:  # controls
            self.draw_controls(page)

    OPTIONS_W, OPTIONS_H = 260, 196

    def _draw_options(self, selected: int, mix: dict) -> None:
        """Opções: sliders de som, Tela cheia Não|Sim, Zoom e Interface como controles segmentados (hit-test
        por segmento em pause_segments) e o botão VOLTAR."""
        w, h = self.OPTIONS_W, self.OPTIONS_H
        x, y = (self.w - w) // 2, self.window_top(h)
        self._pause_frame(x, y, w, h, "Opções")
        n = len(self.VOLUME_ROWS)
        yy = y + 22
        self.tx("SOM", x + 10, yy - 3, B_MUTED)
        for i, (key, label) in enumerate(self.VOLUME_ROWS):
            ry = yy + 8 + i * 17
            row = pygame.Rect(x + 5, ry, w - 10, 16)
            if i == selected:
                self._menu_row(row, True)
            self.tx(label, x + 10, ry + 2, B_TEXT)
            bar = pygame.Rect(x + 80, ry + 7, 130, 2)
            self.bar(bar.x, bar.y, bar.w, mix[key], C.C_ACCENT, h=2)
            kx = bar.x + round(bar.w * mix[key])
            self.round_rect((kx - 3, ry + 4, 7, 8), B_TEXT)
            self.tx(f"{round(mix[key] * 100)}%", x + w - 10, ry, B_MUTED, self.body, "right")
            self.pause_items.append(row)
            self.pause_sliders.append(pygame.Rect(bar.x, bar.y - 2, bar.w, 6))
        yy += 64
        self.fill(B_LINE, (x + 10, yy, w - 20, 1))
        self.tx("TELA", x + 10, yy + 1, B_MUTED)
        for k, ((labels, values, current), name) in enumerate(zip(self.option_segments(mix), self.OPTION_ROWS)):
            index = n + k
            ry = yy + 12 + k * 21
            row = pygame.Rect(x + 5, ry - 2, w - 10, 20)
            if index == selected:
                self._menu_row(row, True)
            self.tx(name, x + 10, ry + 3, B_TEXT)
            widths = [self.body.size(lb)[0] + 10 for lb in labels]
            sx = x + w - 10 - sum(widths) - 2
            self.round_rect((sx, ry, sum(widths) + 2, 16), B_WELL, B_LINE)
            xx = sx + 1
            for lb, value, ow in zip(labels, values, widths):
                seg = pygame.Rect(xx, ry + 1, ow, 14)
                on = value == current
                if on:
                    self.round_rect(seg, C.C_ACCENT)
                self.tx(lb, xx + ow // 2, ry, B_DARK_TEXT if on else B_MUTED, self.body, "center")
                self.pause_segments.append((seg, (index, value)))
                xx += ow
            self.pause_items.append(row)
        back = pygame.Rect(x + 10, y + h - 26, 70, 18)
        self.button(back, "VOLTAR", "ghost", hover=selected == n + len(self.OPTION_ROWS))
        self.pause_items.append(back)
        self.help_line(y + h + 7, [("W/S", "escolhe"), ("A/D", "ajusta"), ("ESC", "volta")])

    def segment_at(self, pos) -> tuple[int, object] | None:
        """Qual segmento das Opções está debaixo de `pos`: (índice da linha, valor) ou None."""
        return next((value for rect, value in self.pause_segments if rect.collidepoint(pos)), None)

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
        self._pause_frame(x, y, w, h, "Controles")
        for i, row in enumerate(rows):
            if row is None:
                continue
            keys, action = row
            yy = y + 24 + i * self.CONTROL_STEP
            self.tx(keys, x + 12, yy + 1, C.C_TI)
            self.tx(action, x + col, yy - 1, B_TEXT, self.body)
        back = pygame.Rect(x + 8, y + h - 26, 80, 19)
        self.button(back, "VOLTAR", "ghost", hover=True)
        self.pause_items.append(back)
        self.controls_pages = len(pages)
        if len(pages) > 1:                               # < 1/2 >  (A/D ou clique trocam a página)
            nxt = pygame.Rect(x + w - 8 - 19, back.y, 19, 19)
            label = f"{page + 1}/{len(pages)}"
            lw = self.font.size(label)[0]
            prev = pygame.Rect(nxt.x - lw - 12 - 19, back.y, 19, 19)
            for rect, arrow in ((prev, "<"), (nxt, ">")):
                self.button(rect, arrow, "ghost")
                self.pause_page_buttons.append((rect, -1 if arrow == "<" else 1))
            self.tx(label, prev.right + 6, back.y + 3, C.C_TI)
            label_w = self.body.size("página")[0]
            kx = prev.x - 8 - label_w - 3 - self.key_cap_width("A/D")
            if kx > back.right + 4:
                self.key_cap(kx, back.y + 4, "A/D")
                self.tx("página", prev.x - 8, back.y + 2, B_MUTED, self.body, "right")

    # ---- diagrama encontrado (Marco 3, v0.5 M1: "leia no fabricador") -----------------------------------------------
    # Aviso em 2 linhas, igual nos 3 tamanhos: rótulo pequeno em cima e o nome do item embaixo, com o
    # ícone do diagrama (icon_diagram, o mesmo da caixa e do inventário) à esquerda.
    BLUEPRINT_LABEL = "DIAGRAMA · LEIA NA BANCADA"
    BLUEPRINT_PAD, BLUEPRINT_ICON = 6, 16            # margem e ícone (px da UI); 5 px entre ícone e texto

    def blueprint_notice_layout(self, blueprint: str) -> tuple[pygame.Rect, pygame.Rect]:
        """(aviso, ícone) em px da UI: no vão do topo entre o painel de O₂ e o do Ti, sem encostar neles.
        Só se nem assim couber (não acontece com os diagramas de hoje), desce pro meio da tela, abaixo do HUD."""
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
        """Aviso de diagrama encontrado no topo do centro: ícone do diagrama + "DIAGRAMA · LEIA NA BANCADA" +
        o nome do que ele libera. `icon`: o ícone 32×32 (resolução cheia) do item do diagrama."""
        rect, icon_rect = self.blueprint_notice_layout(blueprint)
        tx = icon_rect.right - rect.x + 5
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        self.card(0, 0, rect.w, rect.h, (12, 18, 30, 240), "#2c4a6a", shadow=False, target=layer)
        layer.fill(pygame.Color("#9fd0ff"), (2, 1, rect.w - 4, 1))
        # fundinho escuro atrás do ícone: o diagrama é azul e sumia no azul do aviso
        back = icon_rect.move(-rect.x, -rect.y).inflate(2, 2)
        self.round_rect(back, (4, 8, 14, 255), "#2c4a6a", target=layer)
        self.text(self.BLUEPRINT_LABEL, tx, 2, "#9fd0ff", target=layer, shadow=False)
        self.text(C.BLUEPRINTS[blueprint], tx, 12, "#eef6ff", self.body, target=layer, shadow=False)
        layer.set_alpha(int(255 * alpha))
        self.surf.blit(layer, rect.topleft)
        ic = icon.copy()
        ic.set_alpha(int(255 * alpha))
        self.native.append((ic, (icon_rect.x * 2, icon_rect.y * 2)))

    # ---- scanner: minimapa e mapa aberto (M), panorâmico do redesign B2 --------------------------
    MINIMAP_SIZE = 64                                  # px da UI (= C.MINIMAP_TILES tiles a 2 px nativos)
    # no minimapa só os pontos de referência (máquina e baú amontoam em volta da base); sem filtro
    MINIMAP_SKIP = ("machine", "chest")
    MAP_INK, MAP_DOT, MAP_FOG = "#0b0d13", "#202638", "#1d2231"   # não visto, grade de pontos, névoa da borda
    MAP_DOT_STEP = 8                                   # um ponto a cada 8 tiles
    MAP_TOOLTIP_H = 28

    def draw_minimap(self, state: GameState, tex: pygame.Surface, t: float, item_icon=None) -> None:
        """Minimapa no canto direito, embaixo do medidor de energia: 64×64 tiles em volta do player, com os
        pictogramas do mapa em 1× (game/map_markers.py)."""
        size = self.MINIMAP_SIZE
        n = C.MINIMAP_TILES
        k = size * 2 // n                                            # px nativos por tile
        w, h = tex.get_size()
        ptx, pty = state.player.tile
        ox = max(0, min(w - n, ptx - n // 2))
        oy = max(0, min(h - n, pty - n // 2))
        view = pygame.transform.scale_by(tex.subsurface((ox, oy, min(n, w), min(n, h))), k)
        for e in map_view.visible(map_view.map_entries(state, state.layer), ()):
            if e.category not in self.MINIMAP_SKIP:
                map_markers.put(view, map_markers.marker(e.kind, e.color, e.direction), (e.x - ox) * k, (e.y - oy) * k)
        static_noise(view, dust.static_amount(state), t, dust.snow_of(state))          # chiado da rajada (tempestade)
        px = self.w - 6 - (size + 8)
        py = self.energy_bottom + 4
        self.hud_panel(px, py, size + 8, size + 8)
        self.right_bottom = py + size + 8
        self.surf.fill((0, 0, 0), (px + 3, py + 3, size + 2, size + 2))
        self.native.append((view, ((px + 4) * 2, (py + 4) * 2)))
        # rótulo e tecla por cima do mapa: vão numa camada nativa depois da textura
        over = pygame.Surface((size + 8, size + 8), pygame.SRCALPHA)
        self.round_rect((5, 5, 22, 9), (15, 17, 25, 220), target=over)
        self.text("MAPA", 7, 2, B_MUTED, target=over, shadow=False)
        kw = self.key_cap_width("M")
        self.round_rect((size + 3 - kw, 5, kw, 11), B_CARD2, B_LINE2, target=over)
        self.text("M", size + 3 - kw / 2 + 0.5, 3, B_TEXT, target=over, align="center", shadow=False)
        self.native.append((pygame.transform.scale_by(over, 2), (px * 2, py * 2)))
        if item_icon is not None:
            self.native.append((self.small_icon(item_icon, "scanner"), ((px + size - 6) * 2, (py + size - 7) * 2)))

    def map_layout(self) -> tuple[pygame.Rect, pygame.Rect]:
        """(janela, área de desenho) do mapa aberto, em px da UI. No Grande: janela 464×258 e área 444×196
        (o mockup); no Média/Pequena e em janela grande a janela cresce junto e mostra mais tiles."""
        win = pygame.Rect(8, 6, self.w - 16, self.h - 12)
        return win, pygame.Rect(win.x + 10, win.y + 28, win.w - 20, win.h - 62)

    def map_styled(self, tex: pygame.Surface) -> pygame.Surface:
        """A textura da camada (1 px por tile) com o "não visto" do mockup: fundo escuro da B com um ponto a
        cada 8 tiles e 1 tile de névoa mais clara em volta do explorado. Tudo com máscaras (rápido)."""
        w, h = tex.get_size()
        key = ("map_bg", w, h)
        bg = self._icon_cache.get(key)
        if bg is None:
            bg = pygame.Surface((w, h), 0, 24)          # sem alfa (ver _map_surface)
            bg.fill(self.MAP_INK)
            step = self.MAP_DOT_STEP
            for y in range(0, h, step):
                for x in range(0, w, step):
                    bg.set_at((x, y), pygame.Color(self.MAP_DOT))
            self._icon_cache[key] = bg
        seen = pygame.mask.from_threshold(tex, (0, 0, 0), (1, 1, 1, 255))   # preto = não visto
        seen.invert()
        fog = seen.copy()
        for off in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            fog.draw(seen, off)
        fog.erase(seen, (0, 0))
        out = bg.copy()
        out.blit(fog.to_surface(setcolor=pygame.Color(self.MAP_FOG), unsetcolor=(0, 0, 0, 0)), (0, 0))
        top = tex.copy()
        top.set_colorkey((0, 0, 0))
        out.blit(top, (0, 0))
        return out

    def _map_reset(self) -> None:
        self.slot_rects.clear()
        self.equip_rects.clear()
        self.logistics_buttons.clear()
        self.chip_rects.clear()
        self.bay_rects.clear()
        self.buffer_rects.clear()
        self.header_rects.clear()
        self.map_markers = []
        self.map_layer_rects = []
        self.map_buttons = []
        self.map_chips = []
        self.map_hover = None

    def draw_map(self, state: GameState, view, texture, t: float, mouse=(-1, -1)) -> None:
        """Mapa aberto (M), variação panorâmica: cabeçalho (Mapa, Superfície | Caverna, EXPLORADO, FECHAR [M]),
        a área com zoom/arrasto (`view`, game/map_view.MapView) e a fileira de filtros embaixo.
        `texture(key)` = textura da camada (game/minimap.py). Hit-test: map_rect (fora fecha), map_close_rect,
        map_layer_rects, map_buttons (zoom_in/zoom_out/center), map_chips, map_area e map_markers."""
        self._map_reset()
        self.fill((4, 6, 8, 200), (0, 0, self.w, self.h))
        win, area = self.map_layout()
        self.map_rect, self.map_area = win, area
        x, y, w, h = win
        view.set_area(area.w, area.h)
        key = view.layer
        tex = texture(key)
        layer = state.layers[key]
        self.card(x, y, w, h, B_WINDOW, B_LINE)
        self.header_rects.append(pygame.Rect(x, y, w, 22))
        self._map_header(state, layer, win, key, mouse)
        self.fill(B_LINE, (x + 8, y + 22, w - 16, 1))
        # área: textura recortada na janela visível e esticada por inteiro (2·zoom px nativos por tile)
        self.round_rect(area.inflate(4, 4), B_WELL, B_LINE)
        entries = map_view.map_entries(state, key)
        # máquinas/baús colados viram um marcador só (depende do zoom); o filtro vem antes, os chips usam `entries`
        shown = map_view.cluster(map_view.visible(entries, view.hidden), view.zoom, *map_view.origin_of(state, key))
        surf, k, off = self._map_surface(tex, view, area)
        self._map_overlay_buttons(area)
        hits = []
        for e in shown:
            img = map_markers.marker(e.kind, e.color, e.direction, scale=2)
            nx, ny = e.x * k - off[0], e.y * k - off[1]
            if e.category == "you":
                map_markers.put(surf, map_markers.marker("ring", scale=2), nx, ny)
            map_markers.put(surf, img, nx, ny)
            if e.count > 1:
                self._map_count_badge(surf, e.count, nx + img.get_width() // 2, ny - img.get_height() // 2)
            rect = pygame.Rect(0, 0, max(8, img.get_width() // 2 + 2), max(8, img.get_height() // 2 + 2))
            rect.center = (round(area.x + nx / 2), round(area.y + ny / 2))
            if area.collidepoint(rect.center):
                hits.append((rect, e))
        self.map_markers = hits
        on_button = any(r.collidepoint(mouse) for r, _ in self.map_buttons)
        self.map_hover = None if view.dragging or on_button or not area.collidepoint(mouse) \
            else self.map_marker_at(mouse)
        if self.map_hover is not None:                                 # cantoneiras laranja no marcador
            e = self.map_hover
            self._map_brackets(surf, e.x * k - off[0], e.y * k - off[1])
        static_noise(surf, dust.static_amount(state), t, dust.snow_of(state))           # chiado da rajada (tempestade)
        self.native.append((surf, (area.x * 2, area.y * 2)))
        self._map_overlay(view, area, mouse)
        self._map_chips(entries, view, area, key, mouse)

    def _map_surface(self, tex: pygame.Surface, view, area: pygame.Rect):
        """A janela visível da camada em px nativos. Devolve (superfície, px nativos por tile, deslocamento do
        canto em px nativos). Fora da camada continua o fundo pontilhado (igual ao mockup)."""
        k = 2 * view.zoom
        ox, oy = view.origin()
        off = (round(ox * k), round(oy * k))
        vw, vh = area.w * 2, area.h * 2
        # 24 bits, sem canal alfa: na janela de verdade do macOS o formato padrão é ARGB, e aí a textura saía
        # com alfa 0 (mapa preto) e os marcadores viravam quadrados. No driver dummy do smoke isso não aparece.
        surf = pygame.Surface((vw, vh), 0, 24)
        surf.fill(self.MAP_INK)
        step = self.MAP_DOT_STEP
        dot = pygame.Color(self.MAP_DOT)
        tx0, ty0 = math.floor(off[0] / k / step) * step, math.floor(off[1] / k / step) * step
        for ty in range(ty0, math.ceil((off[1] + vh) / k) + 1, step):
            for tx in range(tx0, math.ceil((off[0] + vw) / k) + 1, step):
                surf.fill(dot, (tx * k - off[0], ty * k - off[1], k, k))
        tw, th = tex.get_size()
        x0, y0 = max(0, math.floor(off[0] / k)), max(0, math.floor(off[1] / k))
        x1, y1 = min(tw, math.ceil((off[0] + vw) / k)), min(th, math.ceil((off[1] + vh) / k))
        if x1 > x0 and y1 > y0:
            styled = self.map_styled(tex)
            part = pygame.transform.scale_by(styled.subsurface((x0, y0, x1 - x0, y1 - y0)), k)
            surf.blit(part, (x0 * k - off[0], y0 * k - off[1]))
        return surf, k, off

    def _map_count_badge(self, surf: pygame.Surface, n: int, x: float, y: float) -> None:
        """Quantos marcadores o grupo junta: pílula escura com o número, no canto de cima à direita do
        pictograma ((x, y) em px nativos)."""
        key = ("map_badge", n)
        badge = self._icon_cache.get(key)
        if badge is None:
            label = str(n) if n < 100 else "99+"
            w = self.font.size(label)[0] + 4
            small = pygame.Surface((w, 8), pygame.SRCALPHA)
            self.round_rect((0, 0, w, 8), (11, 13, 20, 255), C.C_ACCENT, target=small)
            self.tx(label, 2, -3, B_TEXT, target=small)
            badge = pygame.transform.scale_by(small, 2)
            self._icon_cache[key] = badge
        surf.blit(badge, (round(x) - 4, round(y) - badge.get_height() + 4))

    @staticmethod
    def _map_brackets(surf: pygame.Surface, x: float, y: float) -> None:
        """Cantoneiras laranja (15×15 do desenho, 2×) em volta do marcador com o mouse (o hover do mockup)."""
        c = pygame.Color(C.C_ACCENT)
        left, top = round(x) - 15, round(y) - 15
        right, bottom = left + 28, top + 28
        for ax, ay, sx, sy in ((left, top, 1, 1), (right, top, -1, 1), (left, bottom, 1, -1), (right, bottom, -1, -1)):
            surf.fill(c, (ax if sx > 0 else ax - 6, ay, 8, 2))
            surf.fill(c, (ax, ay if sy > 0 else ay - 6, 2, 8))

    def _map_header(self, state: GameState, layer, win: pygame.Rect, key: str, mouse) -> None:
        x, y, w, _ = win
        title_w = self.tx("Mapa", x + 8, y + 2, B_TEXT, self.body)
        # Superfície | Caverna (a caverna fica apagada e sem clique até a primeira descida)
        labels = [("surface", "Superfície"), ("cave", "Caverna")]
        if "vesper" in state.layers:                    # v0.7 M4: a aba da nave só aparece depois de entrar nela
            labels.append(("vesper", "VÉSPER-7"))
        widths = [self.body.size(lb)[0] + 14 for _, lb in labels]
        sx, sy = x + 8 + title_w + 6, y + 3
        self.round_rect((sx, sy, sum(widths) + 2, 15), B_WELL, B_LINE)
        xx = sx + 1
        for (lk, label), lw in zip(labels, widths):
            rect = pygame.Rect(xx, sy + 1, lw, 13)
            on, enabled = lk == key, lk in state.layers
            if on or (enabled and rect.collidepoint(mouse)):
                self.round_rect(rect, B_HOVER)
            if on:
                self.fill(C.C_ACCENT, (xx + 3, sy + 13, lw - 6, 1))
            self.tx(label, xx + 7, sy, B_TEXT if on else B_MUTED if enabled else B_DIM, self.body)
            if enabled:
                self.map_layer_rects.append((rect, lk))
            xx += lw
        # FECHAR [M]: botão fantasma com a tecla por dentro
        bw = 62
        close = pygame.Rect(x + w - bw - 6, y + 3, bw, 15)
        hover = close.collidepoint(mouse)
        self.round_rect(close, B_HOVER if hover else B_CARD2, C.C_ACCENT if hover else B_LINE2)
        self.tx("FECHAR", close.x + 6, y + 2, B_TEXT if hover else B_MUTED)
        self.round_rect((close.right - 15, y + 5, 11, 11), B_WELL, B_LINE2)
        self.tx("M", close.right - 9, y + 3, B_TEXT, align="center")
        self.map_close_rect = close
        # EXPLORADO N% com a barrinha
        explored = layer.explored
        frac = explored.count / max(1, explored.width * explored.height)
        ex = close.x - 100
        self.tx("EXPLORADO", ex, y + 2, B_MUTED)
        self.tx(f"{round(frac * 100)}%", close.x - 8, y + 2, C.C_TI, align="right")
        self.bar(ex, y + 13, 92, frac, C.C_TI, h=2)

    def _map_overlay_buttons(self, area: pygame.Rect) -> None:
        """Retângulos dos botões + / − / centralizar (no canto de cima à direita da área)."""
        bx = area.right - 18
        self.map_buttons = [(pygame.Rect(bx, area.y + 4, 14, 14), "zoom_in"),
                            (pygame.Rect(bx, area.y + 20, 14, 14), "zoom_out"),
                            (pygame.Rect(bx, area.y + 38, 14, 14), "center")]

    def _map_overlay(self, view, area: pygame.Rect, mouse) -> None:
        """Por cima da textura (camada nativa): selo do zoom, botões, escala "16 tiles" e o N."""
        over = pygame.Surface(area.size, pygame.SRCALPHA)
        ax, ay = area.topleft
        label = f"ZOOM {view.zoom}×"
        self.round_rect((4, 4, self.font.size(label)[0] + 8, 11), (15, 17, 25, 230), B_LINE, target=over)
        self.tx(label, 8, 1, B_MUTED, target=over)
        for rect, action in self.map_buttons:
            r = rect.move(-ax, -ay)
            enabled = not (action == "zoom_in" and view.zoom >= map_view.ZOOMS[-1]) and \
                not (action == "zoom_out" and view.zoom <= map_view.ZOOMS[0])
            hover = enabled and rect.collidepoint(mouse)
            self.round_rect(r, (35, 40, 56, 240) if hover else (15, 17, 25, 230), C.C_ACCENT if hover else B_LINE2,
                            target=over)
            color = B_TEXT if enabled else B_DIM
            if action in ("zoom_in", "zoom_out"):
                self.fill(color, (r.x + 4, r.y + 6, 6, 2), over)
            if action == "zoom_in":
                self.fill(color, (r.x + 6, r.y + 4, 2, 6), over)
        # escala: 16 tiles (16·zoom px da UI) e o N, cada um num fundinho pra ler em cima da areia
        sl = 16 * view.zoom
        tw = self.body.size("16 tiles")[0]
        self.round_rect((2, area.h - 15, sl + tw + 12, 13), (15, 17, 25, 200), target=over)
        self.fill(B_MUTED, (5, area.h - 6, sl, 1), over)
        self.fill(B_MUTED, (5, area.h - 8, 1, 3), over)
        self.fill(B_MUTED, (5 + sl - 1, area.h - 8, 1, 3), over)
        self.tx("16 tiles", 9 + sl, area.h - 16, B_MUTED, self.body, target=over)
        nx = area.w - 15
        self.round_rect((nx, area.h - 21, 13, 19), (15, 17, 25, 200), target=over)
        for i in range(3):                                         # setinha pro norte em cima do N
            self.fill(B_MUTED, (nx + 6 - i, area.h - 18 + i, 2 * i + 1, 1), over)
        self.tx("N", nx + 7, area.h - 15, B_TEXT, align="center", target=over)
        self.native.append((pygame.transform.scale_by(over, 2), (ax * 2, ay * 2)))
        # centralizar: a setinha de "você" apontando pra cima (1 px nativo por pixel do desenho)
        rect = self.map_buttons[2][0]
        icon = map_markers.marker("you", direction="up")
        self.native.append((icon, (rect.centerx * 2 - icon.get_width() // 2, rect.centery * 2 - icon.get_height() // 2)))

    def _map_chips(self, entries, view, area: pygame.Rect, key: str, mouse) -> None:
        """Fileira de filtros embaixo: um chip por categoria que existe na camada (o mesmo pictograma do
        marcador). Ligado = fundo hover + borda line2; desligado = escuro, ícone e texto apagados."""
        fy = area.bottom + 6
        xx = area.x
        chips = []
        for cat in map_view.categories(entries):
            kind = {"crater": "crater" if key == "surface" else "ramp_up", "vein": "veins"}.get(cat, cat)
            chips.append((cat, map_markers.marker(kind, direction="right", scale=2), map_view.chip_label(cat, key)))
        # o espaçamento do mockup (8 entre ícone e texto, 3 entre chips); não coube: aperta; nem assim: só ícone
        for pad, gap, labels in ((8, 3, True), (6, 2, True), (8, 3, False)):
            total = sum(icon.get_width() // 2 + (pad + self.body.size(label)[0] + 4 if labels else 8)
                        for _, icon, label in chips) + gap * (len(chips) - 1)
            if total <= area.w:
                break
        for cat, icon, label in chips:
            iw = icon.get_width() // 2
            cw = iw + (pad + self.body.size(label)[0] + 4 if labels else 8)
            rect = pygame.Rect(xx, fy, cw, 16)
            on = cat not in view.hidden
            hover = rect.collidepoint(mouse)
            border = C.C_ACCENT if hover else B_LINE2 if on else B_LINE
            self.round_rect(rect, B_HOVER if on else B_WELL, border)
            self.native.append((icon if on else self.dark_icon(icon, 70),
                                ((xx + 4) * 2, (fy + 8) * 2 - icon.get_height() // 2)))
            if labels:
                self.tx(label, xx + pad - 2 + iw + 2, fy, B_TEXT if on else B_DIM, self.body)
            self.map_chips.append((rect, cat))
            xx += cw + gap
        # ajuda à direita, se couber
        pairs = [("Q/E", "camada"), ("C", "centrar")]
        hw = self.help_width(pairs)
        if xx + 8 + hw <= area.right:
            self.help_line(fy + 3, pairs, center=area.right - hw / 2)

    def map_marker_at(self, pos):
        """Marcador do mapa (map_view.Entry) debaixo de `pos` (px da UI), ou None. Encostou em dois: ganha
        a prioridade (você › base › destroço › terminal › rampa › veio › máquina › baú)."""
        if self.map_rect is None:
            return None
        under = [e for rect, e in self.map_markers if rect.collidepoint(pos)]
        return min(under, key=lambda e: e.priority) if under else None

    def map_tooltip_rect(self, entry, mouse) -> pygame.Rect:
        """Cartão do tooltip: abaixo do cursor, preso dentro da área do mapa (sem espaço embaixo: em cima)."""
        lines = (entry.title, entry.detail, entry.sub) if entry.detail else (entry.title, entry.sub)
        w = max(self.body.size(t)[0] for t in lines) + 28
        h = self.MAP_TOOLTIP_H + (12 if entry.detail else 0)      # grupo: uma linha a mais (os tipos)
        area = self.map_area or pygame.Rect(0, 0, self.w, self.h)
        mx, my = int(mouse[0]), int(mouse[1])
        x = max(area.x + 2, min(mx - 10, area.right - 2 - w))
        y = my + 14
        if y + h > area.bottom - 2:
            y = my - 6 - h
        return pygame.Rect(x, max(area.y + 2, y), w, h)

    def draw_map_tooltip(self, entry, mouse) -> None:
        """Tooltip do marcador (cartão B2: pictograma, nome e "estado · distância direção"; o grupo de máquinas
        ou baús tem a linha dos tipos no meio). Vai numa camada
        depois da textura (senão o mapa cobre ele)."""
        rect = self.map_tooltip_rect(entry, mouse)
        self.round_rect(rect, (11, 13, 20, 255), B_LINE2)
        icon = map_markers.marker(entry.kind, entry.color, entry.direction, scale=2)
        self.native.append((icon, ((rect.x + 10) * 2 - icon.get_width() // 2,
                                   (rect.y + 14) * 2 - icon.get_height() // 2)))
        self.tx(entry.title, rect.x + 21, rect.y, B_TEXT, self.body)
        if entry.detail:                                  # grupo: "3 geradores de O₂, 2 aquecedores, 1 drill"
            self.tx(entry.detail, rect.x + 21, rect.y + 12, B_TEXT, self.body)
        self.tx(entry.sub, rect.x + 21, rect.y + (24 if entry.detail else 12), B_MUTED, self.body)

    # ---- cursor ---------------------------------------------------------------
    def draw_cursor(self, x: float, y: float) -> None:
        pts = [(x, y), (x, y + 9), (x + 2, y + 7), (x + 4, y + 11), (x + 5, y + 10), (x + 4, y + 6), (x + 7, y + 6)]
        pygame.draw.polygon(self.surf, (255, 255, 255), pts)
        pygame.draw.polygon(self.surf, (0, 0, 0), pts, 1)
