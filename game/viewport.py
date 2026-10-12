"""Contas de tela: janela -> tela interna (com tarja preta) e tela interna -> mundo (com zoom).

Três espaços de coordenada:
  janela   pixels de verdade da janela (ou do monitor, na tela cheia)
  canvas   a tela interna de 960×540, onde o mundo é montado
  mundo    pixels do mapa (tile = 32 px)
  UI       px da interface (HUD, menus): espaço lógico próprio, que muda com o "Tamanho da
           interface" (ver ui_layout, lá embaixo)

O canvas é esticado pra janela mantendo 16:9: se a proporção não bater, sobra uma tarja
preta (letterbox) dos lados ou em cima/embaixo. O zoom só mexe no mundo: com zoom 2 a câmera
enxerga metade da largura (480×270 px do mundo) e isso é esticado pra 960×540.
A UI é desenhada por cima, direto na janela, dentro do mesmo retângulo do letterbox.
Funções puras (sem pygame), testadas em tests/test_viewport.py.
"""

import math

from game import config as C


def letterbox(window_size: tuple[int, int], canvas_size: tuple[int, int] = (C.SCREEN_W, C.SCREEN_H)) -> tuple[int, int, int, int]:
    """Retângulo (x, y, w, h) da janela onde o canvas aparece: o maior 16:9 que cabe, centralizado."""
    ww, wh = window_size
    cw, ch = canvas_size
    k = min(ww / cw, wh / ch)
    w, h = max(1, round(cw * k)), max(1, round(ch * k))
    return (ww - w) // 2, (wh - h) // 2, w, h


def window_to_canvas(pos: tuple[float, float], window_size: tuple[int, int],
                     canvas_size: tuple[int, int] = (C.SCREEN_W, C.SCREEN_H)) -> tuple[int, int]:
    """Ponto da janela -> pixel do canvas. Em cima da tarja preta, gruda na borda mais próxima."""
    x, y, w, h = letterbox(window_size, canvas_size)
    cw, ch = canvas_size
    cx = int((pos[0] - x) * cw / w)
    cy = int((pos[1] - y) * ch / h)
    return max(0, min(cw - 1, cx)), max(0, min(ch - 1, cy))


def view_size(zoom: float) -> tuple[int, int]:
    """Quanto do mundo (em px) cabe na tela com esse zoom. Zoom 2 -> 480×270, zoom 0,75 -> 1280×720."""
    return round(C.SCREEN_W / zoom), round(C.SCREEN_H / zoom)


def canvas_to_world(pos: tuple[float, float], cam: tuple[int, int], zoom: float) -> tuple[float, float]:
    """Pixel do canvas -> pixel do mundo. `cam` é o canto de cima à esquerda da visão, no mundo."""
    return cam[0] + pos[0] / zoom, cam[1] + pos[1] / zoom


def world_to_canvas(pos: tuple[float, float], cam: tuple[int, int], zoom: float) -> tuple[float, float]:
    """Pixel do mundo -> pixel do canvas (o contrário do canvas_to_world)."""
    return (pos[0] - cam[0]) * zoom, (pos[1] - cam[1]) * zoom


def step_zoom(zoom: float, step: int, levels=C.ZOOM_LEVELS) -> float:
    """Próximo nível de zoom (step +1 aproxima, -1 afasta). Para nas pontas; valor fora da lista
    vai pro nível mais perto antes de andar."""
    nearest = min(range(len(levels)), key=lambda i: abs(levels[i] - zoom))
    return levels[max(0, min(len(levels) - 1, nearest + step))]


# ---- tamanho da interface (HUD, menus, inventários) -------------------------------------------
# A UI tem o próprio espaço lógico, separado do canvas do mundo. Ela é desenhada em "px da UI"
# (a fonte pixel art tem 1 px da UI por traço) e cada px da UI vira `k` px da janela.
#   Grande   k = largura_do_jogo / 480: a UI ocupa a mesma fração da tela de sempre (480×270)
#   Média    ~75% disso   (1920×1080: k 3 -> espaço de 640×360)
#   Pequena  ~50% disso   (1920×1080: k 2 -> espaço de 960×540)
# Em Média/Pequena o k é arredondado pra baixo pra um inteiro (traço da fonte limpo) e nunca fica
# abaixo de 2: a camada "native" (ícones 32×32, 2 px de imagem por px da UI) nunca encolhe, então
# 1 px de imagem vira pelo menos 1 px de tela. E o espaço lógico nunca fica menor que 480×270 (o
# tamanho pra que os painéis foram desenhados): numa janela pequena os três tamanhos dão no mesmo.
UI_SIZES = ("grande", "media", "pequena")
UI_SIZE_FACTOR = {"grande": 1.0, "media": 0.75, "pequena": 0.5}
UI_SIZE_LABEL = {"grande": "GRANDE", "media": "MÉDIA", "pequena": "PEQUENA"}


def ui_scale(game_w: int, ui_size: str) -> float:
    """Px da janela por px da UI, pra área de jogo (letterbox) com largura `game_w`."""
    full = game_w / C.UI_W                          # "Grande": a UI do tamanho de sempre
    factor = UI_SIZE_FACTOR.get(ui_size, 1.0)
    if factor == 1.0:
        return full
    wanted = math.floor(full * factor + 1e-6)
    return float(max(min(2.0, full), wanted))       # piso 2 (ou o Grande, se a janela for menor que isso)


def ui_layout(window_size: tuple[int, int], ui_size: str) -> tuple[tuple[int, int, int, int], float, tuple[int, int]]:
    """(retângulo do jogo na janela, k, tamanho lógico da UI em px da UI).
    Ex.: 1920×1080 Média -> ((0, 0, 1920, 1080), 3.0, (640, 360))."""
    rect = letterbox(window_size)
    k = ui_scale(rect[2], ui_size)
    if k * C.UI_W >= rect[2] - 1e-6:                # escala do Grande (ou janela pequena): 480×270 exato
        return rect, rect[2] / C.UI_W, (C.UI_W, C.UI_H)
    # arredonda pra baixo: sobra no máximo 1 px da UI sem desenho na borda, nunca corta painel
    return rect, k, (int(rect[2] / k + 1e-6), int(rect[3] / k + 1e-6))


def window_to_ui(pos: tuple[float, float], window_size: tuple[int, int], ui_size: str) -> tuple[float, float]:
    """Ponto da janela -> px da UI (hit-test de botões, slots, abas, sliders). Na tarja, gruda na borda."""
    (x, y, _, _), k, (uw, uh) = ui_layout(window_size, ui_size)
    ux, uy = (pos[0] - x) / k, (pos[1] - y) / k
    return max(0.0, min(uw - 0.01, ux)), max(0.0, min(uh - 0.01, uy))


def canvas_to_ui_factor(window_size: tuple[int, int], ui_size: str) -> float:
    """Px da UI por px do canvas (pra prender texto da UI num ponto do mundo). Grande = 0,5."""
    (_, _, w, _), k, _ = ui_layout(window_size, ui_size)
    return w / C.SCREEN_W / k
