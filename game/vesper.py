"""Interior da VÉSPER-7 (v0.7 M4 · bíblia §16): a camada `vesper`, 48×48, montada pela seed.

Esqueleto fixo de 5 salas (SLOTS); cada uma tem 2 plantas em game/vesper_plans/ (formato das ruínas: ruins.load_plan) e
a seed escolhe qual entra. A nave inteira vira UM ruins.Ruin, então casca, chão, props, máquinas quebradas e terminais
de parede saem do ruins.apply_overlays (nunca vão no save). O que é só da nave fica em world.fixtures: a escotilha de
saída, o contêiner arrombado, o painel de energia, a porta emperrada e as luzes de emergência. Python puro, testado em
tests/test_vesper.py.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from game import config as C
from game import ruins

VESPER = "vesper"
SIZE = (48, 48)
ORIGIN = (5, 6)
PLAN_DIR = Path(__file__).with_name("vesper_plans")
FIXTURES = ("hatch", "container_broken", "power_panel", "jammed_door", "emergency_light")
WALL_FIXTURES = frozenset({"power_panel", "jammed_door", "emergency_light"})   # na parede, face pro sul


@dataclass(frozen=True)
class Slot:
    key: str
    box: tuple[int, int, int, int]            # (x, y, w, h) relativo ao ORIGIN
    passages: tuple[tuple[int, int], ...]     # tiles locais que têm de ser chão (abrem a parede da sala vizinha)


SLOTS = (
    Slot("bridge", (11, 0, 18, 10), ((9, 9),)),
    Slot("hall", (17, 9, 7, 16), ((3, 0), (0, 7), (6, 7), (3, 15))),
    Slot("bunks", (4, 11, 14, 11), ((13, 5),)),
    Slot("cold", (23, 11, 14, 11), ((0, 5),)),
    Slot("hold", (10, 24, 21, 12), ((10, 0),)),
)
VARIANTS = {s.key: (f"{s.key}_a", f"{s.key}_b") for s in SLOTS}


@cache
def load(key: str) -> ruins.Plan:
    """A planta `key` (as letras de fixture vêm no `machines` do ruins.Plan e saem em _split)."""
    return ruins.load_plan(key, PLAN_DIR)


def _split(plan: ruins.Plan) -> tuple[dict[str, str], dict[str, str]]:
    """(máquinas quebradas, fixtures) da legenda: o load_plan põe toda letra que não é prop em `machines`."""
    machines = {k: v for k, v in plan.machines.items() if v not in FIXTURES}
    fixtures = {k: v for k, v in plan.machines.items() if v in FIXTURES}
    return machines, fixtures


def _pick(seed: int) -> list[tuple[Slot, ruins.Plan]]:
    rng = random.Random(seed * 7919 + 4243)
    return [(slot, load(rng.choice(VARIANTS[slot.key]))) for slot in SLOTS]


def _cells(seed: int) -> dict[tuple[int, int], tuple[str, ruins.Plan]]:
    """Tile do mundo -> (caractere, planta). Duas plantas no mesmo tile: o que não é `#` ganha."""
    ox, oy = ORIGIN
    out: dict[tuple[int, int], tuple[str, ruins.Plan]] = {}
    for slot, plan in _pick(seed):
        sx, sy, _, _ = slot.box
        for y, row in enumerate(plan.grid):
            for x, ch in enumerate(row):
                if ch == " ":
                    continue
                t = (ox + sx + x, oy + sy + y)
                if t not in out or out[t][0] == "#":
                    out[t] = (ch, plan)
    return out


@cache
def _built(seed: int) -> tuple[ruins.Ruin, tuple]:
    w, h = SIZE
    rows = [[" "] * w for _ in range(h)]
    machines, terminals, props, fixtures, crates = {}, {}, {}, {}, []
    for (x, y), (ch, plan) in _cells(seed).items():
        broken, fx = _split(plan)
        base = ch
        if ch in fx:
            kind = fx[ch]
            fixtures[(x, y)] = kind
            base = "#" if kind in WALL_FIXTURES else "."
        elif ch in plan.props:
            kind = plan.props[ch]
            props[(x, y)] = kind
            base = "#" if C.PROPS[kind].place == "face" else "."
        elif ch in broken:
            machines[(x, y)] = broken[ch]
            base = "."
        elif ch in plan.logs:
            terminals[(x, y)] = plan.logs[ch]
        elif ch == "c":
            crates.append((x, y))
        rows[y][x] = base
    for (x, y), kind in list(props.items()):       # prop grande (v0.7 M4): todos os tiles têm de ser chão
        w, h = C.PROPS[kind].size
        if any(rows[y + dy][x + dx] != "." for dy in range(h) for dx in range(w)):
            del props[(x, y)]
    grid = ["".join(r) for r in rows]
    crates.sort(key=lambda t: (t[1], t[0]))
    ship = ruins.Ruin(VESPER, "VÉSPER-7", VESPER, "rock", 0, 0, grid, machines, terminals, crates[0], 0, props)
    return ship, (tuple(sorted(fixtures.items())), tuple(crates))


def compose(seed: int) -> ruins.Ruin:
    return _built(seed)[0]


def fixtures_of(seed: int) -> dict[tuple[int, int], str]:
    return dict(_built(seed)[1][0])


def crate_tiles(seed: int) -> list[tuple[int, int]]:
    return list(_built(seed)[1][1])


def generate_world(seed: int):
    """O mapa da camada: BEDROCK em tudo, FLOOR na pegada da nave, LOOT_CRATE nas caixas, WRECK (sólido baixo) no
    contêiner arrombado. world.ruins = [a nave] (o apply_overlays põe casca, chão, props e máquinas quebradas)."""
    from game.world import World
    w, h = SIZE
    world = World(seed, w, h)
    world.tiles = [[C.BEDROCK] * w for _ in range(h)]
    world.floor_kind = C.FLOOR
    world.terraforms = False
    ship = compose(seed)
    for x, y in ship.tiles:
        world.set(x, y, C.FLOOR)
    for t in crate_tiles(seed):
        world.set(*t, C.LOOT_CRATE)
    world.fixtures = fixtures_of(seed)
    for t, kind in world.fixtures.items():
        if kind == "container_broken":
            world.set(*t, C.WRECK)
    world.ruins = [ship]
    world.ruin_tiles = frozenset(ship.tiles)
    world.ruin_terminals = dict(ship.terminals)
    hx, hy = hatch_tile(world)
    world.center = (hx, hy - 1)
    return world


def crate_loot(tx: int, ty: int, seed: int) -> list[tuple[str, int]]:
    """Saque inicial da caixa do porão em (tx, ty): recursos do destroço rico (C.WRECK_RICH_LOOT) + peças boas
    (C.LOOT_RICH). O save usa (wrecks.loot_for) pra saber se a caixa mudou."""
    from game.wrecks import _roll_parts
    rng = random.Random(seed * 3209 + tx * 43 + ty * 17 + 11)
    items = [(item, rng.randint(lo, hi)) for item, (lo, hi) in C.WRECK_RICH_LOOT.items()]
    return items + list(_roll_parts(rng, C.LOOT_RICH))


def make_crates(world, seed: int) -> dict:
    """As 2 caixas do porão (ver crate_loot)."""
    from game.inventory import Inventory
    from game.wrecks import Crate
    out = {}
    for tx, ty in crate_tiles(world.seed):
        storage = Inventory(C.CRATE_SLOTS)
        for item, n in crate_loot(tx, ty, seed):
            storage.add(item, n)
        out[(tx, ty)] = Crate(ruins.RuinSpot(tx, ty, VESPER, "Caixa · VÉSPER-7"), storage)
    return out


def hold_variant(seed: int) -> str:
    """Qual porão saiu no sorteio ("a" ou "b"): o render escolhe a escotilha (vesper_hatch_exit_a/_b) por ela."""
    return next(plan.key[-1] for slot, plan in _pick(seed) if slot.key == "hold")


def hatch_tile(world) -> tuple[int, int]:
    return next(t for t, k in world.fixtures.items() if k == "hatch")


def arrival(world) -> tuple[float, float]:
    """Onde o player aparece ao entrar (pés): no tile logo ao norte da escotilha."""
    hx, hy = hatch_tile(world)
    return (hx + 0.5) * C.TILE, (hy - 1) * C.TILE + 24


def walkable_from(world, layer, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Tiles que o player alcança a pé a partir de `start` (chão do mundo, sem parede da casca, sem prop sólido)."""
    blocked = {t for t, p in layer.props.items() if p.solid} | set(layer.base.cells_blocking())
    blocked |= {t for m in layer.machines for t in m.tiles}
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and world.in_bounds(*n) and not world.is_solid(*n) and n not in blocked:
                seen.add(n)
                queue.append(n)
    return seen
