"""Textura do mapa do scanner (v0.3 Marco 3): 1 px por tile, só o que já foi visto (o resto é preto).

É incremental: na primeira vez que uma camada é pedida, pinta tudo que o `Explored` dela já marcou; depois,
a cada frame, só os tiles novos (`Explored.take_fresh`) e os que mudaram (mineração: `repaint`). Nunca
redesenha 192×192 por frame. Minimapa e mapa grande (game/ui.py) recortam/esticam essa textura e põem os
marcadores por cima.
"""

import pygame

from game import config as C

TILE_COLORS = {
    C.SAND: (138, 106, 78), C.FLOOR: (92, 84, 80),
    C.ROCK: (58, 50, 54), C.BEDROCK: (30, 24, 28), C.TERMINAL: (111, 227, 160),
    C.IRON: (150, 92, 60), C.SILICON: (110, 118, 140), C.ICE: (70, 130, 160),
    C.SMALL_IRON: (106, 90, 80), C.SMALL_SILICON: (106, 90, 80), C.SMALL_ICE: (106, 90, 80),
    C.CRATER: (21, 16, 24), C.WRECK: (200, 192, 176), C.LOOT_CRATE: (242, 163, 58),
}
VEIN_COLORS = {"iron": (232, 160, 102), "silicon": (195, 209, 226), "ice": (166, 236, 255)}
UNSEEN = (0, 0, 0)


def tile_color(world, x: int, y: int) -> tuple[int, int, int]:
    vein = world.vein_at(x, y)
    if vein is not None:
        return VEIN_COLORS[vein.resource]
    return TILE_COLORS.get(world.get(x, y), (92, 84, 80))


class Minimap:
    def __init__(self):
        self._tex: dict[str, tuple[int, pygame.Surface]] = {}   # camada -> (id do mundo, textura)

    def reset(self) -> None:
        """Jogo novo/carregado: esquece as texturas (o App chama no start_game)."""
        self._tex.clear()

    def texture(self, state, key: str | None = None) -> pygame.Surface:
        """Textura atualizada da camada `key` (padrão: a ativa)."""
        key = key or state.layer
        layer = state.layers[key]
        world, explored = layer.world, layer.explored
        cached = self._tex.get(key)
        if cached is None or cached[0] != id(world):            # jogo novo/carregado: pinta do zero
            surf = pygame.Surface((world.width, world.height))
            surf.fill(UNSEEN)
            w = world.width
            for i, b in enumerate(explored.bits):
                if b:
                    x, y = i % w, i // w
                    surf.set_at((x, y), tile_color(world, x, y))
            explored.take_fresh()
            self._tex[key] = (id(world), surf)
            return surf
        surf = cached[1]
        for x, y in explored.take_fresh():
            surf.set_at((x, y), tile_color(world, x, y))
        return surf

    def repaint(self, state, tile: tuple[int, int], key: str | None = None) -> None:
        """Um tile mudou (minerado): se já foi pintado, pinta de novo."""
        key = key or state.layer
        cached = self._tex.get(key)
        layer = state.layers.get(key)
        if cached is None or layer is None or cached[0] != id(layer.world):
            return
        if layer.explored.seen(*tile):
            cached[1].set_at(tile, tile_color(layer.world, *tile))
