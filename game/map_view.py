"""Mapa aberto (M), variação panorâmica do redesign B2: câmera, camada, filtros e marcadores. Python puro.

Especificação: reports/design/ui_redesign/index.html, "Mapa aberto (B2)" (Pro Dev: câmera do mapa).
- Zoom só em níveis inteiros (ZOOMS): z px da UI por tile (2z px nativos), pra pixel ficar pixel. Padrão 2×.
  A rodinha ancora no tile debaixo do mouse (ele fica parado); as teclas +/- ancoram no centro.
- Arrastar com o botão esquerdo: só vira arrasto depois de DRAG_THRESHOLD px da UI; antes é clique.
- A câmera (centro, em tiles) fica presa nas bordas da camada: a borda do mapa encosta na borda da área
  de desenho e nunca passa. Se no zoom atual a camada é menor que a área, aquele eixo fica centrado e travado.
- Ao abrir, centra no player; trocar de camada mantém o zoom e centra no player (ou na rampa daquela camada,
  se o player estiver na outra). A caverna só existe (e só aparece) depois da primeira descida.
- Filtros (FILTERS) e o último zoom são preferência do jogador: vão no settings.json (map_hidden, map_zoom),
  não no save. A posição da câmera não é salva.
O desenho fica no game/ui.py (draw_map) e os pictogramas no game/map_markers.py.
"""

import math
from dataclasses import dataclass

from game import config as C

ZOOMS = (1, 2, 3, 4)
ZOOM_DEFAULT = 2
DRAG_THRESHOLD = 3            # px da UI até o clique virar arrasto
KEY_PAN_SCREENS = 1.0         # WASD/setas: ~1 área do mapa por segundo
# filtros, na ordem dos chips. "crater" vale pra cratera (superfície) e rampa (caverna). "Você" não é filtro.
FILTERS = ("base", "crater", "wreck", "wreck_empty", "vein", "terminal", "machine", "chest")
# prioridade do hover quando o mouse encosta em dois: você › base › destroço › terminal › rampa › veio › máquina › baú
PRIORITY = {"you": 0, "base": 1, "wreck": 2, "wreck_empty": 2, "terminal": 3, "crater": 4, "vein": 5,
            "machine": 6, "chest": 7}
# ordem do desenho (de baixo pra cima), igual ao mockup
DRAW_ORDER = ("chest", "machine", "vein", "wreck", "wreck_empty", "terminal", "crater", "base", "you")
CARDINALS = ("a leste", "a sudeste", "ao sul", "a sudoeste", "a oeste", "a noroeste", "ao norte", "a nordeste")
FACING = {"up": "olhando ao norte", "down": "olhando ao sul", "left": "olhando a oeste", "right": "olhando a leste"}


def chip_label(category: str, layer_key: str) -> str:
    return {"base": "Base", "crater": "Cratera" if layer_key == "surface" else "Rampa", "wreck": "Destroço",
            "wreck_empty": "Vazio", "vein": "Veios", "terminal": "Terminal", "machine": "Máquinas",
            "chest": "Baús"}[category]


def cardinal(dx: float, dy: float) -> str:
    """Direção em 8 pontos de (dx, dy) em tiles (y cresce pro sul): "a noroeste"."""
    return CARDINALS[round(math.degrees(math.atan2(dy, dx)) / 45) % 8]


def distance_label(origin: tuple[float, float], target: tuple[float, float], suffix: str = "") -> str:
    """ "39 tiles a noroeste" (de `origin` até `target`, em tiles). Pertinho: "aqui"."""
    dx, dy = target[0] - origin[0], target[1] - origin[1]
    dist = round(math.hypot(dx, dy))
    if dist < 1:
        return "aqui" + suffix
    return f"{dist} tile{'s' if dist != 1 else ''} {cardinal(dx, dy)}{suffix}"


@dataclass
class Entry:
    """Um marcador do mapa: categoria (filtro), pictograma, posição em tiles e o texto do tooltip."""
    category: str                 # "you" ou um de FILTERS
    kind: str                     # pictograma (game/map_markers.py)
    x: float
    y: float
    title: str
    state: str                    # "caixa cheia", "LOG 01 · lido"...
    color: str | None = None      # veio: a cor do minério
    direction: str = "down"       # você: pra onde olha
    sub: str = ""                 # estado + distância (preenchido por map_entries)

    @property
    def priority(self) -> int:
        return PRIORITY[self.category]


def player_tile(state) -> tuple[float, float]:
    p = state.player
    return p.x / C.TILE, (p.y - 8) / C.TILE


def ramp_center(world) -> tuple[float, float] | None:
    return None if world.crater is None else (world.crater[0] + 1.5, world.crater[1] + 1.5)


def map_entries(state, key: str) -> list[Entry]:
    """Todos os marcadores da camada `key` que o jogador já viu (sem filtro), com o tooltip pronto.
    A distância é contada do player; na outra camada, da rampa dela ("... da rampa")."""
    layer = state.layers[key]
    world, explored = layer.world, layer.explored
    entries: list[Entry] = []
    if layer.has_base:
        entries.append(Entry("base", "base", C.POD_TILES[0][0] + 1, C.POD_TILES[0][1] + 0.5, "Base",
                             "módulo de pouso"))
    ramp = ramp_center(world)
    if ramp is not None:
        if layer.has_base:
            entries.append(Entry("crater", "crater", *ramp, "Cratera", "desce pra caverna"))
        else:
            entries.append(Entry("crater", "ramp_up", *ramp, "Rampa", "sobe pra superfície"))
    for v in world.veins:
        if any(explored.seen(*t) for t in v.tiles):
            drilled = any(m.is_drill and m.tx <= v.tx < m.tx + m.size and m.ty <= v.ty < m.ty + m.size
                          for m in layer.machines)
            entries.append(Entry("vein", "vein", v.tx + 1, v.ty + 1, f"Veio de {C.RESOURCE_NAME[v.resource]}",
                                 "com drill" if drilled else "livre", color=_vein_color(v.resource)))
    for wreck in world.wrecks:
        if any(explored.seen(*t) for t in wreck.tiles):
            crate = layer.crates.get(wreck.crate)
            empty = crate is not None and crate.empty
            cat = "wreck_empty" if empty else "wreck"
            entries.append(Entry(cat, cat, *wreck.center, f"Destroço · {wreck.name}",
                                 "caixa vazia" if empty else "caixa cheia"))
    for i, (tx, ty) in enumerate(world.terminals):
        if explored.seen(tx, ty) or explored.seen(tx, ty + 1):
            read = "lido" if i in state.logs_read else "não lido"
            entries.append(Entry("terminal", "terminal", tx + 0.5, ty + 0.5, "Terminal da colônia",
                                 f"{C.log_label(i)} · {read}"))
    for m in layer.machines:
        if m.is_lamp:                       # luminária é luz, não ponto de interesse: fica fora do mapa
            continue
        x, y = m.tx + m.size / 2, m.ty + m.size / 2
        if m.is_chest:
            used = sum(1 for st in m.storage.slots if st)
            entries.append(Entry("chest", "chest", x, y, m.name or C.MACHINES["chest"].name,
                                 f"{used}/{len(m.storage.slots)} pilhas" if used else "vazio"))
        else:
            entries.append(Entry("machine", "machine", x, y, m.type.name, _machine_state(m)))
    origin, suffix = None, ""
    if key == state.layer:
        origin = player_tile(state)
        entries.append(Entry("you", "you", *origin, "Você", FACING[state.player.direction],
                             direction=state.player.direction))
    elif ramp is not None:
        origin, suffix = ramp, " da rampa"
    for e in entries:
        if e.category == "you" or origin is None:
            e.sub = e.state
        else:
            e.sub = f"{e.state} · {distance_label(origin, (e.x, e.y), suffix)}"
    return entries


def _vein_color(resource: str) -> str:
    from game.map_markers import VEIN_COLORS
    return VEIN_COLORS.get(resource, "#ffffff")


def _machine_state(m) -> str:
    if m.is_drill:
        return "cheia · parou" if m.full else "minerando"
    if m.is_station:
        n = len(m.station.drones)
        return f"{n} drone{'s' if n != 1 else ''}"
    return m.type.desc


def categories(entries: list[Entry]) -> list[str]:
    """Os filtros que têm chip: só as categorias que existem na camada, na ordem de FILTERS."""
    present = {e.category for e in entries}
    return [c for c in FILTERS if c in present]


def visible(entries: list[Entry], hidden) -> list[Entry]:
    """Sem os escondidos pelos filtros ("você" sempre aparece), na ordem do desenho."""
    shown = [e for e in entries if e.category == "you" or e.category not in hidden]
    return sorted(shown, key=lambda e: DRAW_ORDER.index(e.kind if e.kind != "ramp_up" else "crater"))


class MapView:
    """Câmera do mapa aberto. Posições em tiles; a área de desenho em px da UI (set_area, a cada desenho)."""

    def __init__(self, zoom: int = ZOOM_DEFAULT, hidden=()):
        self.zoom = zoom if zoom in ZOOMS else ZOOM_DEFAULT
        self.hidden: set[str] = {h for h in hidden if h in FILTERS}
        self.layer = "surface"
        self.size = (C.SURFACE_W, C.SURFACE_H)      # tiles da camada aberta
        self.area = (444, 196)                       # área de desenho (px da UI): a do Grande até o 1º desenho
        self.cx, self.cy = self.size[0] / 2, self.size[1] / 2   # centro da câmera, em tiles
        self.press: tuple[float, float] | None = None  # botão esquerdo apertado na área: onde (px da UI)
        self.press_center = (0.0, 0.0)
        self.dragging = False

    # ---- camada -------------------------------------------------------------------
    @staticmethod
    def layers(state) -> list[str]:
        """Camadas que dá pra abrir: a caverna só depois da primeira descida."""
        return [k for k in ("surface", "cave") if k in state.layers]

    def open(self, state) -> None:
        """M: abre na camada do player, centrado nele, no último zoom usado."""
        self.end_drag()
        self.show_layer(state, state.layer)

    def show_layer(self, state, key: str) -> bool:
        """Mostra a camada `key` (mantém o zoom) e centra no player, ou na rampa se ele estiver na outra."""
        if key not in state.layers:
            return False
        self.layer = key
        world = state.layers[key].world
        self.size = (world.width, world.height)
        if key == state.layer:
            self.center_on(*player_tile(state))
        else:
            self.center_on(*(ramp_center(world) or (world.width / 2, world.height / 2)))
        return True

    def cycle_layer(self, state, step: int = 1) -> bool:
        """Q/E: a outra camada (se ela já existir). True se trocou."""
        keys = self.layers(state)
        if len(keys) < 2:
            return False
        nxt = keys[(keys.index(self.layer) + step) % len(keys)] if self.layer in keys else keys[0]
        return nxt != self.layer and self.show_layer(state, nxt)

    # ---- câmera -------------------------------------------------------------------
    def set_area(self, w: float, h: float) -> None:
        self.area = (w, h)
        self.clamp()

    def visible_tiles(self) -> tuple[float, float]:
        return self.area[0] / self.zoom, self.area[1] / self.zoom

    def clamp(self) -> None:
        """Presa nas bordas: a borda da camada encosta na da área e nunca passa; se a camada for menor que a
        área naquele eixo, fica centrada e travada."""
        vw, vh = self.visible_tiles()
        self.cx = self._clamp_axis(self.cx, vw, self.size[0])
        self.cy = self._clamp_axis(self.cy, vh, self.size[1])

    @staticmethod
    def _clamp_axis(c: float, vis: float, size: int) -> float:
        if size <= vis:
            return size / 2
        return max(vis / 2, min(size - vis / 2, c))

    def origin(self) -> tuple[float, float]:
        """Tile no canto de cima à esquerda da área (pode ser negativo com o eixo travado no centro)."""
        vw, vh = self.visible_tiles()
        return self.cx - vw / 2, self.cy - vh / 2

    def center_on(self, tx: float, ty: float) -> None:
        self.cx, self.cy = tx, ty
        self.clamp()

    def tile_at(self, ax: float, ay: float) -> tuple[float, float]:
        """Tile (fracionado) debaixo do ponto (ax, ay) da área (px da UI a partir do canto dela)."""
        ox, oy = self.origin()
        return ox + ax / self.zoom, oy + ay / self.zoom

    def to_area(self, tx: float, ty: float) -> tuple[float, float]:
        """Tile -> px da UI dentro da área."""
        ox, oy = self.origin()
        return (tx - ox) * self.zoom, (ty - oy) * self.zoom

    def set_zoom(self, zoom: int, anchor: tuple[float, float] | None = None) -> bool:
        """Troca o nível de zoom mantendo parado o tile debaixo de `anchor` (px da área; None = centro)."""
        zoom = max(ZOOMS[0], min(ZOOMS[-1], zoom))
        if zoom == self.zoom:
            return False
        if anchor is None:
            anchor = (self.area[0] / 2, self.area[1] / 2)
        tx, ty = self.tile_at(*anchor)
        self.zoom = zoom
        vw, vh = self.visible_tiles()
        self.cx = tx - anchor[0] / zoom + vw / 2
        self.cy = ty - anchor[1] / zoom + vh / 2
        self.end_drag()
        self.clamp()
        return True

    def zoom_step(self, step: int, anchor: tuple[float, float] | None = None) -> bool:
        return self.set_zoom(self.zoom + step, anchor)

    def pan(self, dx: float, dy: float) -> None:
        """Move a câmera (dx, dy) px da UI (positivo = a vista vai pra direita/baixo)."""
        self.cx += dx / self.zoom
        self.cy += dy / self.zoom
        self.clamp()

    def key_pan(self, mx: int, my: int, dt: float) -> None:
        """WASD/setas: ~1 área por segundo."""
        self.pan(mx * self.area[0] * KEY_PAN_SCREENS * dt, my * self.area[1] * KEY_PAN_SCREENS * dt)

    # ---- arrastar -----------------------------------------------------------------
    def start_press(self, pos: tuple[float, float]) -> None:
        """Botão esquerdo apertado dentro da área: ainda é clique (vira arrasto depois de 3 px)."""
        self.press = pos
        self.press_center = (self.cx, self.cy)
        self.dragging = False

    def move_press(self, pos: tuple[float, float]) -> bool:
        """Mouse andou com o botão apertado. Passou de 3 px: arrasta, 1:1 com o mouse desde onde apertou."""
        if self.press is None:
            return False
        dx, dy = pos[0] - self.press[0], pos[1] - self.press[1]
        if not self.dragging and math.hypot(dx, dy) < DRAG_THRESHOLD:
            return False
        self.dragging = True
        self.cx = self.press_center[0] - dx / self.zoom
        self.cy = self.press_center[1] - dy / self.zoom
        self.clamp()
        return True

    def end_drag(self) -> bool:
        """Soltou o botão. True se foi um arrasto (False = foi um clique)."""
        was = self.dragging
        self.press, self.dragging = None, False
        return was

    # ---- filtros ------------------------------------------------------------------
    def toggle(self, category: str) -> None:
        if category in FILTERS:
            self.hidden ^= {category}
