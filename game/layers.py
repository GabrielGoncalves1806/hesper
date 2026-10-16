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
from game import ice_blocks, pocket_fog, ruins, thaw, vesper
from game.base import BaseGrid
from game.explore import Explored
from game.rock_respawn import RockRespawn
from game.surface_gen import generate_surface
from game.world import World
from game.wrecks import make_container_crates, make_crates

SURFACE, CAVE = "surface", "cave"
VESPER = vesper.VESPER                  # v0.7 M4: o interior da VÉSPER-7 (game/vesper.py)
ORDER = (SURFACE, CAVE, VESPER)


@dataclass
class Layer:
    key: str
    world: World
    machines: list = field(default_factory=list)
    rocks: RockRespawn | None = None      # reaparecimento das rochas pequenas (só na superfície)
    crates: dict = field(default_factory=dict)   # caixas de saque dos destroços: tile -> Crate (Marco 3)
    containers: dict = field(default_factory=dict)   # v0.5 M4: contêineres lacrados dos bolsões: tile -> Crate (a caixa deles)
    removed_crates: set = field(default_factory=set)   # v0.6 M1: caixas de destroço desmontadas (tile); não voltam da seed
    # v0.7 M1 · Estruturas (game/ruins.py): `ruin_salvaged` = tiles das máquinas quebradas de ruína já desmontadas (vai no
    # save); `ruins_off` = keys das ruínas sem objetos neste mundo (save antigo com construção na pegada; derivado)
    ruin_salvaged: set = field(default_factory=set)
    ruins_off: set = field(default_factory=set)
    # v0.7 M2 · Props (game/props.py): tile -> Prop, um por tile. Os do player vão no save; os de ruína (`ruin=True`) saem
    # da seed no `ruins.apply_overlays`
    props: dict = field(default_factory=dict)
    explored: Explored | None = None      # o que o jogador já viu nesta camada (Marco 3, game/explore.py)
    # v0.4 Marco 2: tampa de gelo da cratera (só a superfície usa): 0 = tampada ... CRATER_ICE_STAGES (4) = vazia,
    # com a rampa exposta. No M2 fica sempre tampada (o derretimento pelo calor é do M3); F4 abre na hora (debug).
    # Vai no save.
    crater_ice: int = 0
    base: BaseGrid = field(default_factory=BaseGrid)   # v0.5 M2: chão, parede e porta da base (game/base.py); vai no save
    # v0.4 Marco 3 · gelos-portão (índice = geo.pockets[i]), tudo DERIVADO do índice de calor pelo
    # GameState._apply_thaw (NÃO vai no save, o load reconstrói). M3.5: `gate_melt` = progresso p (0..1,
    # thaw.gate_progress), `gate_ice` = a etapa derivada (0 inteiro, 1 derretendo, 3 fresta aberta: thaw.gate_stage),
    # `gate_recipes` = a receita de cada um (A, B ou C, pela seed) e `gate_blocks` = os blocos que ainda existem no p
    # atual (game/ice_blocks.py · IceBlock: quadro, pé e retângulo de colisão), refeitos pelo `refresh_gates`.
    gate_ice: list = field(default_factory=list)
    gate_melt: list = field(default_factory=list)
    gate_recipes: list = field(default_factory=list)
    gate_blocks: list = field(default_factory=list)
    # v0.4 Marco 3 · M3.1: fumarola i (geo.vents[i]) acordada pelo calor. Derivado dos índices (thaw.fumarole_active),
    # NÃO vai no save: o load reaplica. Fica na camada porque a geo é dividida entre estados da mesma seed.
    vents_awake: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.explored is None:
            self.explored = Explored(self.world.width, self.world.height)
        geo = self.world.geo
        if geo is not None and not self.gate_ice:
            n = ice_blocks.gate_count(geo)       # os dos bolsões + o portão grande por último (M3.6.3)
            self.gate_ice = [0] * n
            self.gate_melt = [0.0] * n
            self.gate_recipes = [ice_blocks.gate_recipe(geo.seed, geo, i) for i in range(n)]
            self.refresh_gates()
        if self.world.geo is not None and not self.vents_awake:
            self.vents_awake = [False] * len(self.world.geo.vents)

    def refresh_gates(self) -> None:
        """Refaz a etapa, os blocos (colisão e desenho) e os tiles fechados de cada gelo-portão pelo `gate_melt`."""
        geo = self.world.geo
        if geo is None:
            return
        blocks, closed = [], set()
        for i in range(ice_blocks.gate_count(geo)):
            p, recipe = self.gate_melt[i], self.gate_recipes[i]
            self.gate_ice[i] = thaw.gate_stage(p, ice_blocks.opens_at(recipe))
            blocks += ice_blocks.blocks_at(ice_blocks.gate_base_px(geo, i), recipe, p, i)
            if self.gate_ice[i] < thaw.GATE_OPEN:
                closed.update(ice_blocks.gate_tiles(geo, i))
        self.gate_blocks = blocks
        self.world.closed_gate_tiles = frozenset(closed)
        self.world.hidden_tiles = pocket_fog.hidden_tiles(geo) if pocket_fog.closed(self) else frozenset()   # M3.6.4

    @property
    def gate_solids(self) -> list:
        """Os retângulos de colisão (px do mundo) dos blocos de gelo que ainda existem (o movimento do player bate)."""
        return [b.rect for b in self.gate_blocks if b.rect is not None]

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
    def buildable(self) -> bool:
        """Dá pra construir aqui? Não dentro da VÉSPER-7 (v0.7 M4)."""
        return self.key != VESPER

    @property
    def has_base(self) -> bool:
        """A cápsula (e a zona de O₂) fica na superfície."""
        return self.key == SURFACE


def current_formations(layer: Layer) -> list:
    """As formações que se desenham como sprite inteiro: todas menos o gelo-portão, que desde o M3.5 é um
    amontoado de blocos (`layer.gate_blocks`, cada um um objeto próprio no desenho)."""
    geo = layer.geo
    if geo is None:
        return []
    return [f for f in geo.formations if f.kind != "ice_gate"]


def make_surface(seed: int) -> Layer:
    world = generate_surface(seed)
    layer = Layer(SURFACE, world, rocks=RockRespawn(),
                  crates={**make_crates(world, seed), **ruins.make_ruin_crates(world, seed)},
                  containers=make_container_crates(world, seed))
    ruins.apply_overlays(layer)                 # v0.7 M1: casca e máquinas quebradas das ruínas (nunca vão no save)
    return layer


def make_cave(seed: int) -> Layer:
    world = World.generate(seed)
    layer = Layer(CAVE, world, crates=ruins.make_ruin_crates(world, seed))
    ruins.apply_overlays(layer)
    return layer


def make_vesper(seed: int) -> Layer:
    world = vesper.generate_world(seed)
    layer = Layer(VESPER, world, crates=vesper.make_crates(world, seed))
    ruins.apply_overlays(layer)
    return layer


MAKERS = {SURFACE: make_surface, CAVE: make_cave, VESPER: make_vesper}


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
