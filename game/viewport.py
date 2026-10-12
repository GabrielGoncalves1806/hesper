"""Contas de tela: janela -> tela interna (com tarja preta) e tela interna -> mundo (com zoom).

Três espaços de coordenada:
  janela   pixels de verdade da janela (ou do monitor, na tela cheia)
  canvas   a tela interna de 960×540, onde o mundo e a UI são montados
  mundo    pixels do mapa (tile = 32 px)

O canvas é esticado pra janela mantendo 16:9: se a proporção não bater, sobra uma tarja
preta (letterbox) dos lados ou em cima/embaixo. O zoom só mexe no mundo: com zoom 2 a câmera
enxerga metade da largura (480×270 px do mundo) e isso é esticado pra 960×540.
Funções puras (sem pygame), testadas em tests/test_viewport.py.
"""

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
