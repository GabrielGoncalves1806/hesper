"""Camadas do mundo (v0.3, bíblia §9): SUPERFÍCIE (deserto, onde fica a base) e CAVERNA.

Cada camada tem o próprio mapa (`world`), as máquinas colocadas nela (baús e drills incluídos)
e o relógio do reaparecimento das rochas pequenas (só a superfície tem). O resto do jogo é global e fica no GameState:
inventário, energia (soma as máquinas das duas camadas), Ti, objetivos e drones (que no v0.3 só
atendem a superfície).

A troca de camada é pela RAMPA (Marco 2): um 3×3 de tiles CRATER em `world.crater` nas duas camadas
(a cratera na superfície, a rampa de subida no meio do salão da caverna). O E mira no tile do meio de
baixo e o player sempre chega logo abaixo dela. A caverna é criada na primeira descida
(`GameState.enter_layer`). Python puro, testado em tests/test_layers.py e tests/test_cave.py.
"""

from dataclasses import dataclass, field

from game import config as C

from game.explore import Explored
from game.rock_respawn import RockRespawn
from game.surface_gen import generate_surface
from game.world import World
from game.wrecks import make_crates

SURFACE, CAVE = "surface", "cave"
ORDER = (SURFACE, CAVE)


@dataclass
class Layer:
    key: str
    world: World
    machines: list = field(default_factory=list)
    rocks: RockRespawn | None = None      # reaparecimento das rochas pequenas (só na superfície)
    crates: dict = field(default_factory=dict)   # caixas de saque dos destroços: tile -> Crate (Marco 3)
    explored: Explored | None = None      # o que o jogador já viu nesta camada (Marco 3, game/explore.py)
    # v0.4 Marco 2: tampa de gelo da cratera (só a superfície usa): 0 = tampada ... CRATER_ICE_STAGES (4) = vazia,
    # com a rampa exposta. No M2 fica sempre tampada (o derretimento pelo calor é do M3); F4 abre na hora (debug).
    # Vai no save.
    crater_ice: int = 0

    def __post_init__(self) -> None:
        if self.explored is None:
            self.explored = Explored(self.world.width, self.world.height)

    @property
    def geo(self):
        """A geografia da superfície (game/geo.py · Geo: regiões, altura, bacias, formações); None na caverna.
        Sai da seed junto com o mapa (não vai no save)."""
        return self.world.geo

    @property
    def water_level(self) -> float:
        """v0.4 Marco 3 (M3.3): até que altura do geo a água das bacias subiu (-1 = seco). Derivado do índice de
        água no GameState._apply_thaw (não vai no save); mora no World, que é quem responde o is_water."""
        return self.world.water_level

    @water_level.setter
    def water_level(self, value: float) -> None:
        self.world.water_level = value

    @property
    def has_base(self) -> bool:
        """A cápsula (e a zona de O₂) fica na superfície."""
        return self.key == SURFACE


def make_surface(seed: int) -> Layer:
    world = generate_surface(seed)
    return Layer(SURFACE, world, rocks=RockRespawn(), crates=make_crates(world, seed))


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
