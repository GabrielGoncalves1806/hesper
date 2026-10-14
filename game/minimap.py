"""Textura do mapa do scanner (v0.3 Marco 3): 1 px por tile, só o que já foi visto (o resto é preto).

É incremental: na primeira vez que uma camada é pedida, pinta tudo que o `Explored` dela já marcou; depois,
a cada frame, só os tiles novos (`Explored.take_fresh`) e os que mudaram (mineração: `repaint`). Nunca
redesenha a superfície inteira por frame. Minimapa e mapa grande (game/ui.py) recortam/esticam essa textura e põem os
marcadores por cima.
"""

import json

import pygame

from game import config as C
from game.geo import REGION_NAMES
from game.surfaces import opaque

TILE_COLORS = {
    C.SAND: (138, 106, 78), C.FLOOR: (92, 84, 80),
    C.ROCK: (58, 50, 54), C.BEDROCK: (30, 24, 28), C.TERMINAL: (111, 227, 160),
    C.IRON: (150, 92, 60), C.SILICON: (110, 118, 140), C.ICE: (70, 130, 160),
    C.SMALL_IRON: (106, 90, 80), C.SMALL_SILICON: (106, 90, 80), C.SMALL_ICE: (106, 90, 80),
    C.SMALL_MAGMATITE: (106, 90, 80),   # rocha pequena: a mesma cor neutra das outras
    C.CRATER: (21, 16, 24), C.WRECK: (200, 192, 176), C.LOOT_CRATE: (242, 163, 58),
    C.FORMATION: (46, 38, 42),          # a pegada; o marcador "Formação" do mapa vai por cima
    C.CONTAINER: (239, 229, 218),       # contêiner lacrado (v0.4 M3.2); o marcador "Contêiner" vai por cima
}
VEIN_COLORS = {"iron": (232, 160, 102), "silicon": (195, 209, 226), "ice": (166, 236, 255)}
UNSEEN = (0, 0, 0)
WATER_COLOR = (63, 118, 144)            # v0.4 M3.3: lago nas bacias (a água da Névoa, PALETTES["mist"]["water"])


def _region_colors() -> tuple[tuple, tuple]:
    """v0.4 Marco 2: o chão da superfície no mapa pinta pela região, na cor média da rampa do Árido dela
    (regions_palettes.json da Designer, tabela BASE). A rocha do morro pinta com a sombra (índice 1) da rampa do
    morro da região (tabela HILL): no basalto, a rocha de antes sumia no chão escuro. Sem o arquivo: as cores de
    antes."""
    n = len(REGION_NAMES)
    try:
        ramps = json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8"))["ramps"]
        ground, hill = [], []
        for name in REGION_NAMES:
            cols = [pygame.Color(h) for h in ramps["BASE"][name]["arid"]]
            ground.append(tuple(round(sum(c[i] for c in cols) / len(cols)) for i in range(3)))
            hill.append(tuple(pygame.Color(ramps["HILL"][name]["arid"][1]))[:3])
    except (OSError, ValueError, KeyError, IndexError):
        return (TILE_COLORS[C.SAND],) * n, (TILE_COLORS[C.ROCK],) * n
    return tuple(ground), tuple(hill)


REGION_COLORS, REGION_ROCK_COLORS = _region_colors()   # índice = região (geo.PLATEAU, SALAR, BASALT, FROST)


def tile_color(world, x: int, y: int) -> tuple[int, int, int]:
    vein = world.vein_at(x, y)
    if vein is not None:
        return VEIN_COLORS[vein.resource]
    kind = world.get(x, y)
    if (x, y) in getattr(world, "closed_gate_tiles", ()):          # v0.4 M3.5: gelo-portão fechado (a caixa 4×2)
        return TILE_COLORS[C.FORMATION]
    geo = getattr(world, "geo", None)
    if geo is not None and world.is_water(x, y, C.GREEN_STAGE):   # lago (com geo, o estágio não importa)
        return WATER_COLOR
    if geo is not None and kind in (C.SAND, C.ROCK):
        return (REGION_COLORS if kind == C.SAND else REGION_ROCK_COLORS)[geo.region[y, x]]
    return TILE_COLORS.get(kind, (92, 84, 80))


class Minimap:
    def __init__(self):
        self._tex: dict[str, tuple[int, pygame.Surface]] = {}   # camada -> (id do mundo, textura)
        self._water: dict[str, float] = {}                       # camada -> nível d'água com que foi pintada
        self._full: dict[str, tuple[int, pygame.Surface]] = {}   # F3: camada -> (id do mundo, textura da camada inteira)
        self._full_water: dict[str, float] = {}

    def reset(self) -> None:
        """Jogo novo/carregado: esquece as texturas (o App chama no start_game)."""
        self._tex.clear()
        self._full.clear()
        self._full_water.clear()

    def texture(self, state, key: str | None = None) -> pygame.Surface:
        """Textura atualizada da camada `key` (padrão: a ativa)."""
        key = key or state.layer
        layer = state.layers[key]
        if state.fast:                                          # F3: o mapa inteiro, sem tocar no explorado
            return self._full_texture(layer, key)
        world, explored = layer.world, layer.explored
        cached = self._tex.get(key)
        if cached is None or cached[0] != id(world):            # jogo novo/carregado: pinta do zero (com a água)
            # opaca de propósito: ela vai pra janela (minimapa e mapa aberto) e, no formato padrão (ARGB no
            # macOS), o recorte dela nasce com SRCALPHA e o alfa vira 0 no caminho (o mapa saía preto)
            surf = opaque((world.width, world.height))
            surf.fill(UNSEEN)
            w = world.width
            for i, b in enumerate(explored.bits):
                if b:
                    x, y = i % w, i // w
                    surf.set_at((x, y), tile_color(world, x, y))
            explored.take_fresh()
            self._tex[key] = (id(world), surf)
            self._water[key] = getattr(world, "water_level", -1.0)
            return surf
        surf = cached[1]
        level = getattr(world, "water_level", -1.0)
        if level != self._water.get(key) and world.geo is not None:   # o lago subiu: repinta só as bacias vistas
            self._water[key] = level
            ys, xs = (world.geo.basin >= 0).nonzero()
            for x, y in zip(xs.tolist(), ys.tolist()):
                if explored.seen(x, y):
                    surf.set_at((x, y), tile_color(world, x, y))
        for x, y in explored.take_fresh():
            surf.set_at((x, y), tile_color(world, x, y))
        return surf

    def _full_texture(self, layer, key: str) -> pygame.Surface:
        """Textura da camada inteira (F3 revela o mapa): pinta tudo na primeira vez e guarda; depois só o lago
        (se subiu) e o que a mineração mudar (`repaint`). Não usa nem altera o `Explored`."""
        world = layer.world
        cached = self._full.get(key)
        level = getattr(world, "water_level", -1.0)
        if cached is None or cached[0] != id(world):
            surf = opaque((world.width, world.height))
            for y in range(world.height):
                for x in range(world.width):
                    surf.set_at((x, y), tile_color(world, x, y))
            self._full[key] = (id(world), surf)
            self._full_water[key] = level
            return surf
        surf = cached[1]
        if level != self._full_water.get(key) and world.geo is not None:
            self._full_water[key] = level
            ys, xs = (world.geo.basin >= 0).nonzero()
            for x, y in zip(xs.tolist(), ys.tolist()):
                surf.set_at((x, y), tile_color(world, x, y))
        return surf

    def repaint(self, state, tile: tuple[int, int], key: str | None = None) -> None:
        """Um tile mudou (minerado): se já foi pintado, pinta de novo."""
        key = key or state.layer
        layer = state.layers.get(key)
        if layer is None:
            return
        full = self._full.get(key)                               # a textura do F3 (se já foi pedida) acompanha também
        if full is not None and full[0] == id(layer.world):
            full[1].set_at(tile, tile_color(layer.world, *tile))
        cached = self._tex.get(key)
        if cached is None or cached[0] != id(layer.world):
            return
        if layer.explored.seen(*tile):
            cached[1].set_at(tile, tile_color(layer.world, *tile))
