"""Estruturas da Colônia Hesper (v0.7 M1 · bíblia §16): plantas desenhadas à mão + variação pela seed.

As plantas moram em game/ruin_plans/*.txt (cabeçalho "chave: valor" até "---", depois a grade, 1 caractere por tile).
Duas metades: os TILES (chão limpo/escavado, destruição, a caixa) entram na geração e ficam no mapa virgem; os OBJETOS
(blocos `ruin`, máquinas `broken`, a Crate) são recolocados da seed quando a camada nasce e depois do load (nunca vão
no save). Python puro, testado em tests/test_ruins.py.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from game import config as C
from game.props import Prop

PLAN_DIR = Path(__file__).with_name("ruin_plans")
PLAN_KEYS = ("camp", "lab", "melters", "drill_post")
TERMINAL_CHARS = "123"


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    layer: str                      # "surface" ou "cave"
    damage: str                     # "sand", "ice" ou "rock": o que a destruição põe no lugar
    grid: list[str]
    machines: dict[str, str] = field(default_factory=dict)   # letra -> kind da máquina quebrada
    logs: dict[str, int] = field(default_factory=dict)       # dígito -> índice em C.LOGS
    props: dict[str, str] = field(default_factory=dict)      # v0.7 M2: letra -> kind do prop (id em C.PROPS)


def load_plan(key: str, plan_dir: Path = PLAN_DIR) -> Plan:
    head, grid = (plan_dir / f"{key}.txt").read_text(encoding="utf-8").split("\n---\n", 1)
    meta = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    rows = [row for row in grid.splitlines() if row]
    letters = {k: v for k, v in meta.items() if len(k) == 1 and k not in TERMINAL_CHARS}
    machines = {k: v for k, v in letters.items() if v not in C.PROPS}
    props = {k: v for k, v in letters.items() if v in C.PROPS}      # v0.7 M2: a letra que é id de prop é prop
    logs = {k: int(v) for k, v in meta.items() if k in TERMINAL_CHARS}
    return Plan(key, meta["name"], meta["layer"], meta["damage"], rows, machines, logs, props)


def transform(grid: list[str], orient: int) -> list[str]:
    """`orient` 0..7: espelha na horizontal se >= 4, depois gira 90° no sentido horário (orient % 4) vezes."""
    rows = [row[::-1] for row in grid] if orient >= 4 else list(grid)
    for _ in range(orient % 4):
        rows = ["".join(rows[len(rows) - 1 - y][x] for y in range(len(rows))) for x in range(len(rows[0]))]
    return rows


# ---------------------------------------------------------------------------
# Montagem: orientação, terminal reassentado, destruição e caminho garantido
# ---------------------------------------------------------------------------
WALLISH = "#D=123"                 # o que conta como "casca" na vizinhança (porta e terminal fazem parte dela)
FLOORISH = ".~c"                   # chão (a máquina quebrada também tem chão embaixo: ver _is_floor)
DOORS = "D="


@dataclass(frozen=True)
class Ruin:
    key: str
    name: str
    layer: str
    damage: str                                  # "sand", "ice" ou "rock" (o efeito do `x`)
    tx: int                                      # canto de cima à esquerda
    ty: int
    grid: list[str]                              # já girada e destruída: # . D = c letras dígitos x e ' '
    machines: dict[tuple[int, int], str]         # tile -> kind da máquina quebrada
    terminals: dict[tuple[int, int], int]        # tile da parede -> índice em C.LOGS
    crate: tuple[int, int]
    level: int
    props: dict[tuple[int, int], str] = field(default_factory=dict)   # v0.7 M2: tile -> kind do prop (face: tile da parede)

    @property
    def tiles(self) -> list[tuple[int, int]]:
        return [(self.tx + x, self.ty + y) for y, row in enumerate(self.grid) for x, ch in enumerate(row) if ch != " "]

    @property
    def center(self) -> tuple[float, float]:
        return self.tx + len(self.grid[0]) / 2, self.ty + len(self.grid) / 2

    def moved(self, tx: int, ty: int) -> "Ruin":
        dx, dy = tx - self.tx, ty - self.ty
        return replace(self, tx=tx, ty=ty,
                       machines={(x + dx, y + dy): k for (x, y), k in self.machines.items()},
                       terminals={(x + dx, y + dy): v for (x, y), v in self.terminals.items()},
                       props={(x + dx, y + dy): k for (x, y), k in self.props.items()},
                       crate=(self.crate[0] + dx, self.crate[1] + dy))


def _at(grid: list[str], x: int, y: int) -> str:
    return grid[y][x] if 0 <= y < len(grid) and 0 <= x < len(grid[y]) else " "


def _is_floor(ch: str, plan: Plan) -> bool:
    """Chão: o desenho, a máquina quebrada e o prop que não é de face (a letra de face é uma parede)."""
    return ch in FLOORISH or ch in plan.machines or (ch in plan.props and C.PROPS[plan.props[ch]].place != "face")


def ok_in_plan(grid: list[str], x: int, y: int, kind: str) -> bool:
    """O prop `kind` vale em (x, y) da grade (já girada, com `#` e `.` no lugar das letras de prop)? Chão e decal: o tile
    é chão (decisão do dono: colado numa parede ao sul ele fica, a face cobre a parte de baixo). Mesa de parede: casca em
    cima e não embaixo. Face: é parede e o tile de baixo não é casca nem vazio."""
    place = C.PROPS[kind].place
    w, h = C.PROPS[kind].size
    if (w, h) != (1, 1) and any(_at(grid, x + dx, y + dy) != "." for dy in range(h) for dx in range(w)):
        return False                       # v0.7 M4: prop grande pede todos os tiles de chão (a planta não gira aqui)
    here, below, above = _at(grid, x, y), _at(grid, x, y + 1), _at(grid, x, y - 1)
    if place == "face":
        return here == "#" and below not in WALLISH + " "
    if place == "desk":
        return all(_at(grid, x + dx, y - 1) == "#" and _at(grid, x + dx, y + 1) not in WALLISH for dx in range(w))
    return here == "."


def _extract_props(grid: list[str], plan: Plan) -> tuple[list[str], dict[tuple[int, int], str]]:
    """Troca cada letra de prop pelo caractere base (`#` na face, `.` no resto) e guarda {tile: kind}; quem não vale
    depois do giro (ok_in_plan) some, mas o tile fica."""
    rows = [list(r) for r in grid]
    found = {}
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch in plan.props:
                kind = plan.props[ch]
                rows[y][x] = "#" if C.PROPS[kind].place == "face" else "."
                found[(x, y)] = kind
    base = ["".join(r) for r in rows]
    return base, {t: k for t, k in found.items() if ok_in_plan(base, *t, k)}


def _near_door(grid: list[str], x: int, y: int) -> bool:
    return any(_at(grid, x + dx, y + dy) in DOORS for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))


def _reseat_terminals(grid: list[str], plan: Plan) -> list[str]:
    """Terminal que ficou sem chão logo abaixo (depois do giro) vai pra parede `#` mais perto que tem (Chebyshev,
    desempate por (y, x)) e não é vizinha de porta. Ordem 1, 2, 3."""
    rows = [list(r) for r in grid]
    for digit in TERMINAL_CHARS:
        snap = ["".join(r) for r in rows]
        spot = next(((x, y) for y, r in enumerate(snap) for x, ch in enumerate(r) if ch == digit), None)
        if spot is None or _is_floor(_at(snap, spot[0], spot[1] + 1), plan):
            continue
        x0, y0 = spot
        cands = [(max(abs(x - x0), abs(y - y0)), y, x) for y, r in enumerate(snap) for x, ch in enumerate(r)
                 if ch == "#" and _is_floor(_at(snap, x, y + 1), plan) and not _near_door(snap, x, y)]
        def crowded(x: int, y: int) -> bool:           # colado noutro terminal (o que já ficou na planta ou foi reassentado)
            return any(_at(snap, x + dx, y + dy) in TERMINAL_CHARS and (x + dx, y + dy) != spot
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        apart = [c for c in cands if not crowded(c[2], c[1])]
        _, y, x = min(apart or cands)                  # (decisão do Dev: prefere uma parede que não amontoe terminais)
        rows[y0][x0] = "#"
        rows[y][x] = digit
    return ["".join(r) for r in rows]


def _damage(grid: list[str], level: int, rng: random.Random, protected: frozenset = frozenset()) -> list[str]:
    """Cada `~` vira `x` (o efeito) ou chão; cada parede comum (reta, de 2 vizinhos de casca, longe de porta e de
    terminal) pode virar `x`. Sorteio de cima pra baixo, esquerda pra direita, `~` e `#` no mesmo passe.
    `protected` (v0.7 M2): paredes que não caem (a de face com prop e a de cima de uma mesa de parede); o sorteio delas
    acontece do mesmo jeito, só o resultado é ignorado."""
    out = [list(r) for r in grid]
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == "~":
                out[y][x] = "x" if rng.random() < C.RUIN_DAMAGE_FLOOR[level] else "."
            elif ch == "#":
                n = [_at(grid, x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]   # L, R, U, D... de lado
                close = sum(c in WALLISH for c in n)
                horiz = n[0] in WALLISH and n[1] in WALLISH
                vert = n[2] in WALLISH and n[3] in WALLISH
                special = any(c in DOORS or c in TERMINAL_CHARS for c in n)
                if close == 2 and horiz != vert and not special and rng.random() < C.RUIN_DAMAGE_WALL[level] \
                        and (x, y) not in protected:
                    out[y][x] = "x"
    return ["".join(r) for r in out]


def _connected(grid: list[str], plan: Plan, blocked: frozenset = frozenset()) -> bool:
    """Das portas, anda por chão (o `x` bloqueia se o efeito é gelo ou rocha) e alcança o tile de baixo de cada
    terminal e um vizinho da caixa. Máquina e caixa não se pisa; prop que colide (`blocked`) também não."""
    walk = {".", "D", "="} | (set() if plan.damage != "sand" else {"x"})
    doors = [(x, y) for y, r in enumerate(grid) for x, ch in enumerate(r) if ch in DOORS]
    if not doors:
        return False
    seen = {doors[0]}
    queue = [doors[0]]
    while queue:
        x, y = queue.pop()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and n not in blocked and _at(grid, *n) in walk:
                seen.add(n)
                queue.append(n)
    if not all(d in seen for d in doors):
        return False

    def touches(tile):
        x, y = tile
        return tile in seen or any(n in seen for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    for y, r in enumerate(grid):
        for x, ch in enumerate(r):
            if ch in TERMINAL_CHARS and not touches((x, y + 1)):
                return False
            if ch == "c" and not touches((x, y)):
                return False
    return True


def build(plan: Plan, orient: int, level: int, rng: random.Random) -> Ruin | None:
    """Monta a ruína em (0, 0): gira, reassenta terminais, aplica a destruição `level` e confere o caminho.
    None se a destruição isolou porta, terminal ou caixa (quem chama tenta `level - 1`)."""
    grid, props = _extract_props(_reseat_terminals(transform(plan.grid, orient), plan), plan)
    protected = frozenset((x, y) for (x, y), k in props.items() if C.PROPS[k].place == "face") | \
        frozenset((x, y - 1) for (x, y), k in props.items() if C.PROPS[k].place == "desk")
    grid = _damage(grid, level, rng, protected)
    if level >= 1:                                     # a cadeira tomba (sorteio depois da destruição)
        for t in sorted(props, key=lambda t: (t[1], t[0])):
            if props[t] == "prop_chair" and rng.random() < C.RUIN_CHAIR_FALL:
                props[t] = "prop_chair_fallen"
    blocked = frozenset(t for t, k in props.items() if C.PROPS[k].solid)
    if not _connected(grid, plan, blocked):
        return None
    machines, terminals, crate = {}, {}, (0, 0)
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch in plan.machines:
                machines[(x, y)] = plan.machines[ch]
            elif ch in plan.logs:
                terminals[(x, y)] = plan.logs[ch]
            elif ch == "c":
                crate = (x, y)
    return Ruin(plan.key, plan.name, plan.layer, plan.damage, 0, 0, grid, machines, terminals, crate, level, props)


# ---------------------------------------------------------------------------
# Lugar no mapa e carimbo dos tiles (a metade da geração)
# ---------------------------------------------------------------------------
_EFFECT = {"ice": C.ICE, "rock": C.ROCK}      # o `x` (sand = o chão da camada)
# Só no afrouxamento (seed sem lugar com a folga toda de areia): rocha pequena comum na folga em volta é tolerada
# (a pegada em si continua só de areia). Magmatita fica de fora: é das fumarolas.
_LOOSE_MARGIN_OK = (C.SAND, C.SMALL_IRON, C.SMALL_SILICON, C.SMALL_ICE)


def _stamp(world, ruin: Ruin) -> None:
    """Carimba os tiles da ruína: chão limpo/escavado, a caixa e o efeito da destruição nos `x`."""
    for y, row in enumerate(ruin.grid):
        for x, ch in enumerate(row):
            if ch == " ":
                continue
            kind = world.floor_kind
            if ch == "x":
                kind = _EFFECT.get(ruin.damage, world.floor_kind)
                if kind == C.ROCK and world.region_at_cave(ruin.tx + x, ruin.ty + y) in C.CAVE_HARD_REGIONS:
                    kind = C.HARD_ROCK                   # na rocha dura da caverna o entulho também é duro (invariante da região)
            elif ch == "c":
                kind = C.LOOT_CRATE
            world.set(ruin.tx + x, ruin.ty + y, kind)


def _search(plan: Plan, rng: random.Random, tries: int, sample, fits) -> Ruin | None:
    """Sorteia orientação, destruição (desce se isolar) e centro; devolve a primeira que `fits`."""
    for _ in range(tries):
        orient, level = rng.randrange(8), rng.choice(C.RUIN_DAMAGE_LEVELS)
        ruin = build(plan, orient, level, rng)
        while ruin is None:                                  # o nível 0 sempre passa (testado)
            level -= 1
            ruin = build(plan, orient, level, rng)
        cx, cy = sample(rng)
        ruin = ruin.moved(int(round(cx - len(ruin.grid[0]) / 2)), int(round(cy - len(ruin.grid) / 2)))
        if fits(ruin):
            return ruin
    return None


def _finish(world, found: list[Ruin]) -> None:
    for ruin in found:
        _stamp(world, ruin)
    world.ruins = list(found)
    world.ruin_tiles = frozenset(t for r in found for t in r.tiles)
    world.ruin_terminals = {t: log for r in found for t, log in r.terminals.items()}


def _area(ruin: Ruin, margin: int):
    xs, ys = [t[0] for t in ruin.tiles], [t[1] for t in ruin.tiles]
    return range(min(xs) - margin, max(xs) + margin + 1), range(min(ys) - margin, max(ys) + margin + 1)


def place_surface_ruins(world, seed: int) -> None:
    """Acampamento e laboratório na areia livre (v0.7 M1). Rng próprio por estrutura; sem lugar, a estrutura não nasce."""
    from game.geo import FROST
    geo, found = world.geo, []
    frost = None
    if geo is not None:
        ys, xs = (a.tolist() for a in np.nonzero(geo.region == FROST))
        frost = list(zip(xs, ys))
    kx, ky = world.crater if world.crater else (0, 0)

    for i, key in enumerate(PLAN_KEYS):
        plan = load_plan(key)
        if plan.layer != "surface":
            continue
        rng = random.Random(seed * 6151 + i * 97 + 17)

        def sample(rng, key=key, dist=None):
            if key == "lab":
                return rng.choice(frost) if frost else (world.width // 2, world.height // 2)
            d = rng.uniform(*dist)
            a = rng.uniform(0, math.tau)
            return kx + 1.5 + d * math.cos(a), ky + 1.5 + d * math.sin(a)

        def fits(ruin, key=key, margin=C.RUIN_MARGIN, dist=C.RUIN_CAMP_DIST, loose=False):
            cx, cy = ruin.center
            if key == "camp" and not dist[0] <= math.hypot(cx - kx - 1.5, cy - ky - 1.5) <= dist[1]:
                return False
            if key == "lab":
                if frost is None or not all(geo.region_at(*t) == FROST for t in ruin.tiles):
                    return False
                if geo.giant is not None:
                    gx, gy = geo.giant.creature.tile
                    if math.hypot(cx - gx, cy - gy) < C.RUIN_LAB_GIANT_MIN:
                        return False
            if any(math.hypot(cx - o.center[0], cy - o.center[1]) < C.RUIN_SPACING for o in [*world.wrecks, *found]):
                return False
            if world.crater is not None and any(math.hypot(x + 0.5 - kx - 1.5, y + 0.5 - ky - 1.5) < 8
                                                for x, y in ruin.tiles):
                return False
            xr, yr = _area(ruin, margin)
            if xr.start < 4 or yr.start < 4 or xr.stop > world.width - 4 or yr.stop > world.height - 4:
                return False
            foot = set(ruin.tiles)
            for y in yr:
                for x in xr:
                    ok_kinds = _LOOSE_MARGIN_OK if loose and (x, y) not in foot else (C.SAND,)
                    if (world.get(x, y) not in ok_kinds or world.vein_at(x, y) is not None or (x, y) in world.keep_clear
                            or (geo is not None and geo.basin_at(x, y) >= 0)
                            or world.dist_from_center(x, y) < C.SURFACE_CLEAR_RADIUS + 2):
                        return False
            return True

        ruin = _search(plan, rng, 4000, lambda r: sample(r, dist=C.RUIN_CAMP_DIST), fits)
        if ruin is None:                      # afrouxa: folga 1 (pode ter rochinha), no acampamento 30 a 75 tiles
            ruin = _search(plan, rng, 4000, lambda r: sample(r, dist=(30, 75)),
                           lambda r: fits(r, margin=1, dist=(30, 75), loose=True))
        if ruin is not None:
            found.append(ruin)
    _finish(world, found)


def place_cave_ruins(world, seed: int) -> None:
    """Estação de derretedores (gelo) e posto de perfuração (basalto) carimbados dentro da rocha dura: o gerador abre
    o espaço da planta e deixa a rocha em volta."""
    from game.geo import BASALT, FROST
    regions = {"melters": FROST, "drill_post": BASALT}
    found = []
    for i, key in enumerate(PLAN_KEYS):
        plan = load_plan(key)
        if plan.layer != "cave":
            continue
        want = regions[key]
        rng = random.Random(seed * 6151 + i * 97 + 17)
        ys, xs = np.nonzero(world.cave_region == want)
        spots = list(zip(xs.tolist(), ys.tolist()))

        def fits(ruin, margin=C.RUIN_CAVE_MARGIN):
            xr, yr = _area(ruin, margin)
            if xr.start < 2 or yr.start < 2 or xr.stop > world.width - 2 or yr.stop > world.height - 2:
                return False
            if any(math.hypot(ruin.center[0] - o.center[0], ruin.center[1] - o.center[1]) < C.RUIN_SPACING
                   for o in found):
                return False
            for y in yr:
                for x in xr:
                    if (world.get(x, y) not in C.SOLID_TILES or world.get(x, y) in (C.BEDROCK, C.TERMINAL)
                            or int(world.cave_region[y, x]) != want or world.vein_at(x, y) is not None):
                        return False
            return True

        ruin = None
        for margin in range(C.RUIN_CAVE_MARGIN, 0, -1):      # 3, depois 2, depois 1
            ruin = _search(plan, rng, 4000, lambda r: r.choice(spots), lambda r, m=margin: fits(r, m))
            if ruin is not None:
                break
        if ruin is not None:
            found.append(ruin)
    _finish(world, found)


# ---------------------------------------------------------------------------
# Os objetos (a metade que nunca vai no save): caixa, casca e máquinas quebradas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RuinSpot:
    """O "destroço" de mentira da caixa de uma ruína (molde do ContainerSpot): só o que a caixa e a tela precisam."""
    tx: int
    ty: int
    key: str
    name: str
    log: int | None = None
    terminal: tuple[int, int] | None = None
    blueprint: str | None = None
    rich: bool = False

    @property
    def crate(self) -> tuple[int, int]:
        return self.tx, self.ty


def ruin_loot(spot: RuinSpot, seed: int) -> list[tuple[str, int]]:
    """Saque da caixa da ruína: recursos da tabela (C.RUIN_LOOT) e depois as peças."""
    from game import wrecks
    rng = random.Random(seed * 3203 + spot.tx * 41 + spot.ty * 13 + 9)
    resources, parts = C.RUIN_LOOT[spot.key]
    items = []
    for item, (lo, hi) in resources.items():
        n = rng.randint(lo, hi)
        if n > 0:
            items.append((item, n))
    return items + wrecks._roll_parts(rng, parts)


def make_ruin_crates(world, seed: int) -> dict:
    """Uma Crate por ruína do mapa, tile -> Crate."""
    from game.inventory import Inventory
    from game.wrecks import Crate
    out = {}
    for ruin in world.ruins:
        spot = RuinSpot(*ruin.crate, ruin.key, f"Caixa · {ruin.name}")
        storage = Inventory(C.CRATE_SLOTS)
        for item, n in ruin_loot(spot, seed):
            storage.add(item, n)
        out[ruin.crate] = Crate(spot, storage)
    return out


def apply_overlays(layer) -> None:
    """Põe na camada os objetos de cada ruína: blocos `ruin` (casca e chão) e as máquinas `broken` que ainda não foram
    desmontadas (`layer.ruin_salvaged`). Idempotente (tira os que já são de ruína antes). Se a pegada tem máquina ou
    bloco do player (save antigo), a ruína não ganha os objetos neste mundo: vai pra `layer.ruins_off`."""
    from game.base import BaseBlock, H, V
    from game.systems import Machine
    world = layer.world
    for block in [b for b in layer.base.blocks if b.ruin]:
        layer.base.remove(block)
    layer.machines[:] = [m for m in layer.machines if not m.broken]
    for t in [t for t, p in layer.props.items() if p.ruin]:        # v0.7 M2: os props de ruína também voltam da seed
        del layer.props[t]                                          # (v0.7 M4: prop grande tem um tile por parte)
    layer.ruins_off.clear()
    broken = []
    for ruin in world.ruins:
        tiles = set(ruin.tiles)
        if any(t in tiles for m in layer.machines for t in m.tiles) or any(t in tiles for t in layer.base.cells):
            layer.ruins_off.add(ruin.key)
            if layer.crates.pop(ruin.crate, None) is not None and world.get(*ruin.crate) == C.LOOT_CRATE:
                world.set(*ruin.crate, world.floor_kind)
            continue
        used = set()
        for y, row in enumerate(ruin.grid):
            for x, ch in enumerate(row):
                t = (ruin.tx + x, ruin.ty + y)
                if ch in "#123":
                    layer.base.add(BaseBlock(C.BASE_WALL, *t, ruin=True))
                elif ch == "D":
                    layer.base.add(BaseBlock(C.BASE_DOOR, *t, ruin=True))
                elif ch == "=" and t not in used:                  # a dupla é UM bloco (âncora a oeste/norte)
                    if _at(ruin.grid, x + 1, y) == "=":
                        orient, other = H, (t[0] + 1, t[1])
                    else:
                        orient, other = V, (t[0], t[1] + 1)
                    used.update((t, other))
                    layer.base.add(BaseBlock(C.BASE_DOOR2, *t, orient, ruin=True))
                elif ch in ".c" or t in ruin.machines:
                    layer.base.add(BaseBlock(C.BASE_FLOOR, *t, ruin=True))
                    if t in ruin.machines and t not in layer.ruin_salvaged:
                        broken.append(Machine(ruin.machines[t], *t, broken=True))
        for t, kind in ruin.props.items():
            prop = Prop(kind, *t, ruin=True)
            if all(p not in layer.props for p in prop.tiles):
                layer.add_prop(prop)
    layer.machines[:0] = broken                        # sempre na frente das do player (a ordem não muda no load)
