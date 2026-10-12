"""Camadas do mundo (v0.3, bíblia §9): SUPERFÍCIE (deserto, onde fica a base) e CAVERNA.

Cada camada tem o próprio mapa (`world`), as máquinas colocadas nela (baús e drills incluídos)
e os recursos soltos no chão (só a superfície tem). O resto do jogo é global e fica no GameState:
inventário, energia (soma as máquinas das duas camadas), Ti, objetivos e drones (que no v0.3 só
atendem a superfície).

No Marco 1 só a superfície existe num jogo normal. A caverna já funciona pela estrutura
(`GameState.enter_layer(CAVE)` cria ela com o gerador antigo, `World.generate`): é o ponto de
partida do Marco 2 (rampa na cratera). Python puro, testado em tests/test_layers.py.
"""

from dataclasses import dataclass, field

from game.pickups import Pickups
from game.surface_gen import generate_surface
from game.world import World

SURFACE, CAVE = "surface", "cave"
ORDER = (SURFACE, CAVE)


@dataclass
class Layer:
    key: str
    world: World
    machines: list = field(default_factory=list)
    pickups: Pickups | None = None        # recursos soltos (só na superfície)

    @property
    def has_base(self) -> bool:
        """A cápsula (e a zona de O₂) fica na superfície."""
        return self.key == SURFACE


def make_surface(seed: int) -> Layer:
    world = generate_surface(seed)
    return Layer(SURFACE, world, pickups=Pickups.generate(world, seed))


def make_cave(seed: int) -> Layer:
    return Layer(CAVE, World.generate(seed))


MAKERS = {SURFACE: make_surface, CAVE: make_cave}
