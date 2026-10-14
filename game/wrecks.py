"""Destroços da superfície (v0.3 Marco 3 · bíblia §9): nave de carga, módulo da colônia e sonda.

Duas partes:
    - GEOMETRIA (fixa, sai da seed): `place_wrecks(world, rng)` sorteia 6 a 8 destroços a distâncias
      crescentes da base e carimba no mapa: os tiles do destroço viram `WRECK` (sólido baixo, o sprite é
      desenhado como objeto) e a caixa vira `LOOT_CRATE`. Cada `Wreck` sabe onde fica a caixa, o terminal
      (só o módulo tem), qual LOG ele guarda e qual diagrama vem na caixa.
    - ESTADO (muda jogando): `make_crates(world, seed)` cria uma `Crate` por destroço, com o saque sorteado
      pela seed (fixo, não reabastece). Quem guarda é a camada (`Layer.crates`).

Ordem por distância (rank 0 = o mais perto): nave (tanque de O₂ + LOGS[3]), sonda, módulo (scanner + LOGS[4]),
nave (luminária forte), sonda (LOGS[5]), [nave, sonda extras quando há 7 ou 8] e módulo (LOGS[6], o mais longe).
O número que o jogador vê ("LOG 05") é a posição na cronologia (config.LOG_ORDER), não o índice.

v0.4 Marco 3 · M3.2: atrás de cada gelo-portão vai um destroço RICO (`pocket_wrecks`, `rich=True`, depois dos de fora
na lista `world.wrecks`), com a tabela C.WRECK_RICH_LOOT e, se faltar algum, um diagrama que não caiu lá fora.

Python puro (sem pygame), testado em tests/test_wrecks.py e tests/test_pockets.py.
"""

import math
import random
from dataclasses import dataclass

from game import config as C
from game.inventory import Inventory

T = C.TILE


@dataclass(frozen=True)
class WreckSpec:
    name: str
    size: tuple[int, int]               # tiles (largura, altura) da área sólida
    sprite: str
    sprite_size: tuple[int, int]
    lift: int                           # px que o sprite sobe acima da área (antena, teto)
    crate: tuple[int, int]              # tile da caixa, relativo ao canto do destroço
    terminal: tuple[int, int] | None    # tile do terminal (dentro da área), relativo ao canto
    loot: dict                          # recurso -> (mín, máx) na caixa


SPECS = {
    "cargo": WreckSpec("Nave de carga", (4, 3), "wreck_cargo", (128, 112), 16, (1, 3), None,
                       {"iron": (14, 20), "silicon": (8, 12), "ice": (6, 10)}),
    "module": WreckSpec("Módulo da colônia", (3, 2), "wreck_module", (96, 88), 24, (0, 2), (2, 1),
                        {"iron": (8, 12), "silicon": (4, 7), "ice": (3, 5)}),
    "probe": WreckSpec("Sonda", (2, 2), "wreck_probe", (64, 64), 0, (2, 1), None,
                       {"iron": (2, 4), "silicon": (1, 3), "ice": (0, 2)}),
}
# Retângulo do terminal desenhado no wreck_module.png (contorno do alvo do E vai só nele)
MODULE_TERMINAL_RECT = (62, 59, 18, 16)


@dataclass(frozen=True)
class Wreck:
    kind: str
    tx: int                      # canto de cima à esquerda da área sólida
    ty: int
    rank: int                    # 0 = o mais perto da base
    log: int | None = None       # índice em config.LOGS
    blueprint: str | None = None  # id em config.BLUEPRINTS
    rich: bool = False           # v0.4 M3.2: destroço rico atrás de um gelo-portão (saque C.WRECK_RICH_LOOT)

    @property
    def spec(self) -> WreckSpec:
        return SPECS[self.kind]

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def tiles(self) -> list[tuple[int, int]]:
        w, h = self.spec.size
        return [(self.tx + dx, self.ty + dy) for dy in range(h) for dx in range(w)]

    @property
    def crate(self) -> tuple[int, int]:
        dx, dy = self.spec.crate
        return self.tx + dx, self.ty + dy

    @property
    def terminal(self) -> tuple[int, int] | None:
        if self.spec.terminal is None:
            return None
        dx, dy = self.spec.terminal
        return self.tx + dx, self.ty + dy

    @property
    def center(self) -> tuple[float, float]:
        """Centro da área sólida, em tiles."""
        w, h = self.spec.size
        return self.tx + w / 2, self.ty + h / 2

    @property
    def anchor(self) -> tuple[float, float]:
        """Centro da base (px do mundo): entra na ordenação de desenho pelo y."""
        w, h = self.spec.size
        return (self.tx + w / 2) * T, (self.ty + h) * T

    @property
    def blit_pos(self) -> tuple[int, int]:
        """Onde o canto do sprite vai no mundo (px)."""
        return self.tx * T, self.ty * T - self.spec.lift


def kinds_for(n: int) -> list[str]:
    """Tipo de cada destroço, do mais perto pro mais longe (n de 6 a 8)."""
    extras = ["cargo", "probe"][:max(0, n - 6)]
    return ["cargo", "probe", "module", "cargo", "probe", *extras, "module"]


def extras_for(rank: int, n: int) -> tuple[int | None, str | None]:
    """(LOG, diagrama) do destroço de posição `rank` (de n)."""
    if rank == 0:
        return 3, "o2_tank"            # VÉSPER-7 (exibido LOG 05) · o primeiro grande achado
    if rank == 2:
        return 4, "scanner"            # dia 140 (exibido LOG 04) · o segundo
    if rank == 3:
        return None, "lamp_t2"
    if rank == 4:
        return 5, None                 # sonda S-3 (exibido LOG 02) · sonda longe
    if rank == n - 1:
        return 6, None                 # dia 230 (exibido LOG 07) · o mais longe de todos
    return None, None


def _fits(world, wreck: Wreck, placed: list[Wreck]) -> bool:
    """Área + caixa + folga são areia livre (sem morro, veio, cratera, borda), longe da base e dos outros.
    v0.4 Marco 2: e fora de bacia (a água sobe ali no Marco 3), do halo das formações e dos bolsões."""
    m = C.WRECK_MARGIN
    w, h = wreck.spec.size
    cx, cy = wreck.crate
    x0, y0 = min(wreck.tx, cx) - m, min(wreck.ty, cy) - m
    x1, y1 = max(wreck.tx + w - 1, cx) + m, max(wreck.ty + h - 1, cy) + m
    if x0 < 4 or y0 < 4 or x1 >= world.width - 4 or y1 >= world.height - 4:
        return False
    geo, keep = getattr(world, "geo", None), getattr(world, "keep_clear", ())
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if world.get(x, y) != C.SAND or world.vein_at(x, y) is not None:
                return False
            if (x, y) in keep or (geo is not None and geo.basin_at(x, y) >= 0):
                return False
            if world.dist_from_center(x, y) < C.SURFACE_CLEAR_RADIUS + 2:
                return False
    if world.crater is not None:
        kx, ky = world.crater
        if math.hypot(wreck.center[0] - kx - 1.5, wreck.center[1] - ky - 1.5) < 8:
            return False
    return all(math.hypot(wreck.center[0] - o.center[0], wreck.center[1] - o.center[1]) >= C.WRECK_SPACING
               for o in placed)


def place_wrecks(world, rng: random.Random) -> list[Wreck]:
    """Sorteia e carimba os destroços no mapa (tiles WRECK e LOOT_CRATE). Guarda em `world.wrecks`."""
    n = rng.randint(*C.WRECK_COUNT)
    kinds = kinds_for(n)
    lo, hi = C.WRECK_DIST
    bx, by = world.center
    placed: list[Wreck] = []
    last = 0.0
    for rank, kind in enumerate(kinds):
        target = lo + (hi - lo) * rank / (n - 1)
        log, blueprint = extras_for(rank, n)
        w, h = SPECS[kind].size
        for attempt in range(6000):
            jitter = 3 + attempt // 600                   # sem lugar perto do alvo: aceita mais longe dele
            dist = target + rng.uniform(-jitter, jitter)
            angle = rng.uniform(0, math.tau)
            tx = int(round(bx + dist * math.cos(angle) - w / 2))
            ty = int(round(by + dist * math.sin(angle) - h / 2))
            wreck = Wreck(kind, tx, ty, rank, log, blueprint)
            d = math.hypot(wreck.center[0] - bx, wreck.center[1] - by)
            if d <= last + 1 or not _fits(world, wreck, placed):   # distâncias sempre crescentes
                continue
            for t in wreck.tiles:
                world.set(*t, C.WRECK)
            world.set(*wreck.crate, C.LOOT_CRATE)
            placed.append(wreck)
            last = d
            break
    world.wrecks = placed
    return placed


def missing_blueprints(wrecks: list[Wreck]) -> list[str]:
    """Diagramas de C.WRECK_DIAGRAMS que nenhum desses destroços traz (na ordem do config)."""
    have = {w.blueprint for w in wrecks}
    return [bp for bp in C.WRECK_DIAGRAMS if bp not in have]


def pocket_wrecks(pockets, outside: list[Wreck]) -> list[Wreck]:
    """v0.4 Marco 3 · M3.2: um destroço rico (C.WRECK_RICH_KIND) no wreck_spot de cada bolsão de gelo-portão, com
    rank depois dos de fora. Se algum diagrama não caiu nos destroços de fora, cada rico traz um dos que faltam."""
    missing = missing_blueprints(outside)
    out = []
    for i, p in enumerate(pockets):
        bp = missing[i] if i < len(missing) else None
        out.append(Wreck(C.WRECK_RICH_KIND, *p.wreck_spot, len(outside) + i, None, bp, rich=True))
    return out


def keep_free(wrecks: list[Wreck]) -> set[tuple[int, int]]:
    """Tiles em volta de cada destroço que ficam livres (sem rocha pequena): a caixa e o terminal têm acesso."""
    m = C.WRECK_MARGIN
    out = set()
    for wreck in wrecks:
        for x, y in wreck.tiles + [wreck.crate]:
            out |= {(x + dx, y + dy) for dx in range(-m, m + 1) for dy in range(-m, m + 1)}
    return out


# ---------------------------------------------------------------------------
# Caixa de saque (estado que muda)
# ---------------------------------------------------------------------------
@dataclass
class Crate:
    wreck: Wreck
    storage: Inventory
    opened: bool = False          # já foi aberta (o registro de bordo já apareceu, o projeto já deu o aviso)

    @property
    def tile(self) -> tuple[int, int]:
        return self.wreck.crate

    @property
    def empty(self) -> bool:
        return self.storage.is_empty()

    @property
    def anchor(self) -> tuple[float, float]:
        tx, ty = self.tile
        return (tx + 0.5) * T, (ty + 1) * T


def crate_loot(wreck: Wreck, seed: int) -> list[tuple[str, int]]:
    """Saque da caixa: o diagrama (se tiver) primeiro, depois os recursos pelo tamanho do destroço."""
    rng = random.Random(seed * 1009 + wreck.rank * 7919 + wreck.tx * 31 + wreck.ty)
    items = []
    if wreck.blueprint:
        items.append((f"diagram_{wreck.blueprint}", 1))
    for resource, (lo, hi) in (C.WRECK_RICH_LOOT if wreck.rich else wreck.spec.loot).items():
        n = rng.randint(lo, hi)
        if n > 0:
            items.append((resource, n))
    return items


def make_crates(world, seed: int) -> dict[tuple[int, int], Crate]:
    crates = {}
    for wreck in getattr(world, "wrecks", []):
        storage = Inventory(C.CRATE_SLOTS)
        for item, n in crate_loot(wreck, seed):
            storage.add(item, n)
        crates[wreck.crate] = Crate(wreck, storage)
    return crates
