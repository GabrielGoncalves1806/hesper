"""Pictogramas dos marcadores do mapa (M) e do minimapa: o desenho exato do mockup aprovado.

Porte da função marker() de tools/sprites/ui_mockups.py (redesign B2, seção "Mapa aberto"): cada
marcador é um desenho fixo em pixels com contorno escuro (INK). A base é a opção A, "módulo de frente"
(BASE_OPTS["base_a"], 13×11), escolhida pelo dono. Os pictogramas saem em 1 px por pixel do desenho:
o mapa usa 2× (1 px da UI por pixel do desenho) e o minimapa 1× (1 px nativo). Não mudam de tamanho com o
zoom do mapa, só a posição.
"""

import pygame

INK = "#0b0d13"
C_O2, C_ACCENT = "#59d0e6", "#e2733a"
# cor de cada marcador (o veio sai na cor do minério)
COLORS = {"you": "#ffd84a", "base": C_O2, "crater": "#ffffff", "ramp_up": "#7fd6a0", "wreck": "#f2a33a",
          "wreck_empty": "#7a6c62", "terminal": "#7fd6a0", "machine": "#d9dde6", "chest": "#d8b27a",
          "formation": "#cbb79a", "container": "#efe5da", "unknown": "#d6e6f2"}
VEIN_COLORS = {"iron": "#b99b82", "silicon": "#c3d1e2", "ice": "#a6ecff", "copper": "#e0703f", "magmatite": "#ff7a2e"}
RING = "#ffd84a"                 # anel em volta de "você" (alfa 130)

BASE_A = ["........o....", "..ooo..oto...", ".orrro..o....", "ooooooooooooo", "o#####+#####o", "o#w#w####dd#o",
          "osssssss#ddso", "o-------#dd-o", "ooooooooooooo", "okkkkkkkkkkko", ".ooooooooooo."]
BASE_COLORS = {"o": INK, "#": "#efe5da", "+": "#ffffff", "-": "#b9ab9c", "s": C_ACCENT, "d": "#2d3a40",
               "w": C_O2, "r": "#4a5060", "t": "#ff6a55", "k": "#3a3f4a"}
YOU = ["....o....", "...o#o...", "..o#+#o..", ".o##+##o.", "o###+###o", "o##o#o##o", "o#o.o.o#o", "oo.....oo"]
RING_ROWS = ["...ooooo...", "..o#####o..", ".o#ooooo#o.", "o#o.....o#o", "o#o.....o#o", "o#o.....o#o",
             "o#o.....o#o", "o#o.....o#o", ".o#ooooo#o.", "..o#####o..", "...ooooo..."]
ARROW_DOWN = ["#####", ".###.", "..#.."]          # cratera: desce
ARROW_UP = ["..#..", ".###.", "#####"]            # rampa: sobe
WRECK = ["....o....", "...o#o...", "..o#+#o..", ".o#+###o.", "o#######o", ".o#####o.", "..o#-#o..", "...o-o...",
         "....o...."]
WRECK_EMPTY = ["....o....", "...o#o...", "..o#o#o..", ".o#o.o#o.", "o#o...o#o", ".o#o.o#o.", "..o#o#o..",
               "...o#o...", "....o...."]
VEIN = [".ooooo.", "o##+##o", "o#+###o", "o#####o", "o#####o", "o-###-o", ".ooooo."]
TERMINAL = ["ooooooooo", "o#######o", "o#d#####o", "o##d####o", "o#d##dd#o", "o#######o", "ooooooooo"]
MACHINE = ["ooooooo", "o-----o", "o#####o", "o#+###o", "o#####o", "ooooooo"]
CHEST = ["ooooooooo", "o#######o", "o-------o", "o###d###o", "o#######o", "ooooooooo"]
# formação (v0.4 Marco 2): um pico de pedra simples, marco de paisagem (sem filtro)
FORMATION = ["...o...", "..o+o..", ".o#+-o.", ".o##-o.", "o###--o", "ooooooo"]
# contêiner lacrado (v0.4 Marco 3 · M3.2): caixa industrial com a faixa laranja e o lacre no meio
CONTAINER = ["ooooooooo", "o#######o", "o-------o", "osssdssso", "o###d###o", "ooooooooo"]
# desconhecido (v0.5 M3.6.4): o "?" na névoa do bolsão da criatura, até o portão grande abrir
UNKNOWN = [".ooooo.", "o#####o", "o#ooo#o", "ooooo#o", "..o##o.", "..o#oo.", "..ooo..", "..o#o..", "..ooo.."]
ROTATION = {"up": 0, "left": 90, "down": 180, "right": 270}   # graus anti-horário (a seta desenhada aponta pra cima)

_cache: dict[tuple, pygame.Surface] = {}


def _mix(c1, c2, t: float) -> pygame.Color:
    return pygame.Color(c1).lerp(pygame.Color(c2), t)


def _pix(rows: list[str], cmap: dict) -> pygame.Surface:
    w, h = max(len(r) for r in rows), len(rows)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in cmap:
                surf.set_at((x, y), pygame.Color(cmap[ch]))
    return surf


def _draw(kind: str, color, direction: str) -> pygame.Surface:
    c = pygame.Color(color or COLORS.get(kind, "#ffffff"))
    cm = {"o": INK, "#": c, "+": _mix(c, "#ffffff", 0.5), "-": _mix(c, "#000000", 0.35), "d": INK}
    if kind == "you":
        return pygame.transform.rotate(_pix(YOU, cm), ROTATION[direction])
    if kind == "base":
        return _pix(BASE_A, BASE_COLORS)
    if kind in ("crater", "ramp_up"):
        surf = _pix(RING_ROWS, cm)
        for y, row in enumerate(ARROW_DOWN if kind == "crater" else ARROW_UP):
            for x, ch in enumerate(row):
                if ch == "#":
                    surf.set_at((3 + x, 4 + y), c)
        return surf
    if kind == "wreck":
        return _pix(WRECK, cm)
    if kind == "wreck_empty":
        return _pix(WRECK_EMPTY, cm)
    if kind == "vein":
        return _pix(VEIN, cm)
    if kind == "terminal":
        return _pix(TERMINAL, cm)
    if kind == "machine":
        cm["-"] = C_ACCENT
        return _pix(MACHINE, cm)
    if kind == "chest":
        return _pix(CHEST, cm)
    if kind == "formation":
        return _pix(FORMATION, cm)
    if kind == "unknown":
        return _pix(UNKNOWN, cm)
    if kind == "container":
        cm["s"] = C_ACCENT
        return _pix(CONTAINER, cm)
    if kind == "ring":                                   # anel de 16 px em volta de "você"
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        ring = pygame.Color(RING)
        ring.a = 130
        pygame.draw.ellipse(surf, ring, (0, 0, 16, 16), 1)
        return surf
    if kind == "veins":                                  # chip/legenda dos veios: os 3 minérios lado a lado
        surf = pygame.Surface((25, 7), pygame.SRCALPHA)
        for i, res in enumerate(("iron", "silicon", "ice")):
            surf.blit(_draw("vein", VEIN_COLORS[res], "down"), (i * 9, 0))
        return surf
    raise KeyError(kind)


def marker(kind: str, color=None, direction: str = "down", scale: int = 1) -> pygame.Surface:
    """Pictograma do marcador (1 px por pixel do desenho × `scale`). Não modifique a superfície: é do cache."""
    key = (kind, str(color), direction, scale)
    surf = _cache.get(key)
    if surf is None:
        surf = _draw(kind, color, direction)
        if scale != 1:
            surf = pygame.transform.scale_by(surf, scale)
        _cache[key] = surf
    return surf


def put(target: pygame.Surface, surf: pygame.Surface, x: float, y: float) -> None:
    """Desenha centrado em (x, y) (igual ao put_marker do mockup)."""
    target.blit(surf, (round(x - surf.get_width() / 2), round(y - surf.get_height() / 2)))
