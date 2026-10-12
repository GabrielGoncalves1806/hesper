"""Camadas do mundo (v0.3, bíblia §9): SUPERFÍCIE (deserto, onde fica a base) e CAVERNA.

Cada camada tem o próprio mapa (`world`), as máquinas colocadas nela (baús e drills incluídos)
e os recursos soltos no chão (só a superfície tem). O resto do jogo é global e fica no GameState:
inventário, energia (soma as máquinas das duas camadas), Ti, objetivos e drones (que no v0.3 só
atendem a superfície).

A troca de camada é pela RAMPA (Marco 2): um 3×3 de tiles CRATER em `world.crater` nas duas camadas
(a cratera na superfície, a rampa de subida no meio do salão da caverna). O E mira no tile do meio de
baixo e o player sempre chega logo abaixo dela. A caverna é criada na primeira descida
(`GameState.enter_layer`). Python puro, testado em tests/test_layers.py e tests/test_cave.py.
"""

from dataclasses import dataclass, field

from game import config as C

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


def other_layer(key: str) -> str:
    """Pra onde a rampa leva: superfície <-> caverna."""
    return CAVE if key == SURFACE else SURFACE


def ramp_tiles(world: World) -> list[tuple[int, int]]:
    """Os 9 tiles da rampa da camada (vazio se a camada não tem rampa)."""
    if world.crater is None:
        return []
    tx, ty = world.crater
    return [(tx + dx, ty + dy) for dy in range(3) for dx in range(3)]


def ramp_target(world: World) -> tuple[int, int]:
    """Tile que o E mira: o do meio, na linha de baixo do 3×3."""
    tx, ty = world.crater
    return tx + 1, ty + 2


def ramp_arrival(world: World) -> tuple[float, float]:
    """Onde o player aparece (pés), no tile logo abaixo do meio da rampa."""
    tx, ty = world.crater
    return (tx + 1.5) * C.TILE, (ty + 3) * C.TILE + 24


def ramp_mouth(world: World) -> tuple[float, float]:
    """Ponto de referência da rampa (px): o meio da borda de baixo. Mede o alcance do E e a seta do O₂."""
    tx, ty = world.crater
    return (tx + 1.5) * C.TILE, (ty + 3) * C.TILE
