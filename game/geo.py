"""Geografia da superfície (v0.4 Marco 2 · bíblia §11): relevo, regiões, bacias, formações e gelos-portão.

Dados puros (numpy, sem pygame). `generate_geo(seed, w, h, base)` devolve um `Geo` que o gerador da superfície
(game/surface_gen.py) usa pra pôr morros, formações, cratera, veios e destroços, e que o chão (game/ground.py),
os morros (game/hills.py), o minimapa e o mapa leem. O `Geo` não vai no save: sai sempre igual da seed.

Porte do gerador de exemplo da Designer (tools/sprites/regions_core.gen_world, `fbm`, `vnoise`, `hash2`) e do
deslocamento de borda (tools/sprites/regions_scene.warp_field), com o mapa aprovado (mapa_regioes.png) como alvo:

    altura   fbm de 3 oitavas (0,52..0,72) menos a tigela do salar e as depressões pequenas do planalto
    regiões  planalto em volta da base (o núcleo GEO_PLATEAU_CORE é sempre planalto), salar a leste (elipse com
             a borda torcida), basalto a oeste/sudoeste (borda com ruído), faixa gelada no norte (y < ~24)
    bacias   onde a altura fica abaixo de L3: o nível (L1, L2 ou L3) em que o tile alaga no Marco 3
    borda    a região num PIXEL é a do tile em (x + dx, y + dy), com dx, dy de um ruído preso no mundo,
             limitados a ±GEO_WARP px: a divisa vira curva e nunca passa de 14 px da divisa por tile
    marcos   formações fixas (monolito, arco, pináculos, cone, crosta de sal) na região de cada uma, longe da
             base e umas das outras; e 2 ou 3 bolsões na cordilheira do norte, cada um fechado por um gelo-portão

A seed mexe em tudo: o ruído, a posição e o tamanho do salar e das depressões, as bordas do basalto e da faixa
gelada, e o sorteio das formações e dos bolsões. Testado em tests/test_geo.py.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from typing import Callable

import numpy as np

from game import config as C

PLATEAU, SALAR, BASALT, FROST = 0, 1, 2, 3
REGION_NAMES = ("plateau", "salar", "basalt", "frost")
REGION_LABELS = ("Planalto rachado", "Salar", "Basalto", "Faixa gelada")
REGION_OF = {name: i for i, name in enumerate(REGION_NAMES)}
NO_BASIN = -1


# ---------------------------------------------------------------------------------------------------------------
# Formações: pegada, âncora e região de cada uma (do regions_palettes.json da Designer)
# ---------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FormationSpec:
    kind: str
    name: str
    region: int
    footprint: tuple[tuple[int, int], ...]   # tiles que bloqueiam, relativos ao canto de cima-esquerda
    anchor: tuple[int, int]                  # px do sprite que cai no centro de baixo da pegada
    foot: tuple[int, int]                    # o tile do pé (o (0, 0) da Designer), relativo ao canto
    small: bool = False                      # formação pequena da v9 (sem afloramento nem marcador no mapa)


def _load_specs() -> dict[str, FormationSpec]:
    data = json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8"))["formations"]
    specs = {}
    for key, info in data.items():
        if key.startswith("crater_impact"):            # sprites da cratera (v8.1): não são formação colocada
            continue
        kind = "ice_gate" if key.startswith("ice_gate") else key
        if kind == "ice_gate" and key != "ice_gate_0":     # etapa 0 (inteiro): as outras são do Marco 3
            continue
        tiles = [tuple(t) for t in info["tiles"]]
        x0, y0 = min(x for x, _ in tiles), min(y for _, y in tiles)
        specs[kind] = FormationSpec(kind, info["name"], REGION_OF[info["region"]],
                                    tuple(sorted((x - x0, y - y0) for x, y in tiles)),
                                    tuple(info["foot"]), (-x0, -y0), bool(info.get("small")))
    return specs


FORMATION_SPECS = _load_specs()


def _load_gate_footprints() -> tuple[tuple[tuple[int, int], ...], ...]:
    """Pegada do gelo-portão em cada etapa 0..2 (ice_gate_0..2 do JSON), relativa ao canto da etapa 0: as três
    usam o mesmo pé (`foot`), então o sprite não anda quando o gelo baixa (v0.4 Marco 3 · M3.2)."""
    data = json.loads(C.REGIONS_PALETTES.read_text(encoding="utf-8"))["formations"]
    full = data["ice_gate_0"]["tiles"]
    x0, y0 = min(x for x, _ in full), min(y for _, y in full)
    return tuple(tuple(sorted((x - x0, y - y0) for x, y in data[f"ice_gate_{s}"]["tiles"])) for s in range(3))


GATE_FOOTPRINTS = _load_gate_footprints()
GATE_OPEN = len(GATE_FOOTPRINTS)         # etapa 3: aberto (sem gelo, sem sprite, só a geada no chão)


@dataclass
class Formation:
    kind: str                            # "monolith" | "arch" | "basalt_spires" | "cone" | "salt_ridge" | "ice_gate"
    tx: int                              # canto de cima-esquerda da pegada (tiles)
    ty: int
    footprint: list[tuple[int, int]]     # tiles que bloqueiam, relativos a (tx, ty)
    anchor: tuple[int, int]              # px do sprite que cai no centro de baixo da pegada
    variant: int = 0                     # gelo-portão: a etapa (0 = inteiro; o Marco 3 derrete)
    frame: tuple[int, int] | None = None   # caixa fixa (largura, altura): o gelo-portão guarda a da etapa 0, pra
                                           # o base_px (onde a âncora cai) não andar quando a pegada encolhe

    @property
    def tiles(self) -> list[tuple[int, int]]:
        """Os tiles que bloqueiam (viram C.FORMATION), em coordenadas do mapa."""
        return [(self.tx + dx, self.ty + dy) for dx, dy in self.footprint]

    @property
    def size(self) -> tuple[int, int]:
        """(largura, altura) da caixa da pegada, em tiles (o arco tem 5×1, com o vão de 3 no meio)."""
        if self.frame is not None:
            return self.frame
        return (max(x for x, _ in self.footprint) + 1, max(y for _, y in self.footprint) + 1)

    @property
    def box(self) -> list[tuple[int, int]]:
        """Todos os tiles da caixa da pegada (no arco, inclui o vão andável)."""
        w, h = self.size
        return [(self.tx + dx, self.ty + dy) for dy in range(h) for dx in range(w)]

    @property
    def base_px(self) -> tuple[float, float]:
        """Centro de baixo da pegada, em px do mundo: é onde a `anchor` do sprite cai (e o y da ordem de desenho)."""
        w, h = self.size
        return (self.tx + w / 2) * C.TILE, (self.ty + h) * C.TILE

    @property
    def center(self) -> tuple[float, float]:
        """Centro da caixa da pegada, em tiles."""
        w, h = self.size
        return self.tx + w / 2, self.ty + h / 2

    @property
    def name(self) -> str:
        return FORMATION_SPECS[self.kind].name

    @property
    def region(self) -> int:
        return FORMATION_SPECS[self.kind].region

    @property
    def small(self) -> bool:
        """Formação pequena da v9 (pedra rachada, pilar de sal, tubo de lava, agulhas de gelo)."""
        spec = FORMATION_SPECS.get(self.kind)
        return spec is not None and spec.small


def gate_at(gate: Formation, stage: int) -> Formation | None:
    """O gelo-portão na etapa `stage` (0..2): uma CÓPIA com a pegada da etapa e a mesma caixa/âncora; None se aberto.
    Não mexe no `gate` (o Geo é dividido entre os mundos da mesma seed)."""
    if stage >= GATE_OPEN:
        return None
    return replace(gate, footprint=list(GATE_FOOTPRINTS[stage]), variant=stage, frame=gate.size)


@dataclass
class Pocket:
    """Bolsão atrás de um gelo-portão: um vão na cordilheira do norte com um anel de rocha que não minera.
    O Marco 3 põe o destroço melhor e o contêiner lacrado nas posições marcadas aqui."""
    gate: Formation
    interior: list[tuple[int, int]]      # chão de dentro (só se chega passando pelo portão)
    ring: list[tuple[int, int]]          # anel de rocha (vira C.BEDROCK)
    apron: list[tuple[int, int]]         # chão livre na frente do portão (nada nasce aqui)
    wreck_spot: tuple[int, int]          # canto de cima-esquerda do destroço do Marco 3
    container_spot: tuple[int, int]      # tile do contêiner lacrado do Marco 3


@dataclass
class Geo:
    seed: int
    region: np.ndarray                   # (H, W) uint8, região de cada tile (PLATEAU, SALAR, BASALT, FROST)
    height: np.ndarray                   # (H, W) float32, 0..1
    basin: np.ndarray                    # (H, W) int8: -1 fora de bacia; 0..2 = marca d'água L1..L3 em que alaga
    formations: list[Formation]
    region_px: Callable = None           # region_px(px, py) -> região num pixel do mundo (borda orgânica)
    pockets: list[Pocket] = field(default_factory=list)   # bolsões dos gelos-portão (as formações "ice_gate")

    def region_at(self, tx: int, ty: int) -> int:
        """Região do tile (fora do mapa: a do tile mais perto)."""
        h, w = self.region.shape
        return int(self.region[min(max(ty, 0), h - 1), min(max(tx, 0), w - 1)])

    def basin_at(self, tx: int, ty: int) -> int:
        h, w = self.region.shape
        if not (0 <= tx < w and 0 <= ty < h):
            return NO_BASIN
        return int(self.basin[ty, tx])

    def warp(self, px, py):
        """Deslocamento (dx, dy) da borda das regiões no pixel (px, py) do mundo: até ±GEO_WARP px."""
        return warp_px(self.seed, px, py)


# ---------------------------------------------------------------------------------------------------------------
# Ruído (determinístico, vetorizado): porte de tools/sprites/regions_core.py
# ---------------------------------------------------------------------------------------------------------------
M32 = np.uint64(0xFFFFFFFF)


def hash2(x, y, s: int) -> np.ndarray:
    """Hash inteiro -> [0, 1). Aceita arrays."""
    with np.errstate(over="ignore"):
        x = np.asarray(x, dtype=np.int64).astype(np.uint64)
        y = np.asarray(y, dtype=np.int64).astype(np.uint64)
        n = (x * np.uint64(374761393) + y * np.uint64(668265263) + np.uint64(s & 0xFFFFFFFF) * np.uint64(2246822519)
             + np.uint64(0x9E3779B9)) & M32
        n = ((n ^ (n >> np.uint64(13))) * np.uint64(1274126177)) & M32
        n = n ^ (n >> np.uint64(16))
        n = (n * np.uint64(2246822519)) & M32
        n = n ^ (n >> np.uint64(15))
    return n.astype(np.float64) / 4294967296.0


def _smooth(t):
    return t * t * (3 - 2 * t)


def vnoise(xs, ys, cell: float, seed: int) -> np.ndarray:
    """Value noise em coordenadas (px ou tiles), célula de `cell`."""
    fx, fy = np.asarray(xs, float) / cell, np.asarray(ys, float) / cell
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = _smooth(fx - ix), _smooth(fy - iy)
    a, b = hash2(ix, iy, seed), hash2(ix + 1, iy, seed)
    c, d = hash2(ix, iy + 1, seed), hash2(ix + 1, iy + 1, seed)
    return a + (b - a) * tx + (c - a) * ty + (a - b - c + d) * tx * ty


def fbm(xs, ys, cell, seed, octaves=3) -> np.ndarray:
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * vnoise(xs, ys, cell / (2 ** o), seed + 101 * o)
        norm += amp
        amp *= 0.5
    return tot / norm


def warp_px(seed: int, px, py):
    """(dx, dy) da borda orgânica no pixel do mundo: o warp_field da Designer, preso em ±GEO_WARP px."""
    s = (seed & 0xFFFF) * 16
    px, py = np.asarray(px, float), np.asarray(py, float)
    wp = C.GEO_WARP
    dx = wp * (2 * fbm(px, py, 44, 901 + s, 2) - 1) + 3 * (2 * vnoise(px, py, 7, 903 + s) - 1)
    dy = wp * (2 * fbm(px, py, 44, 905 + s, 2) - 1) + 3 * (2 * vnoise(px, py, 7, 907 + s) - 1)
    return np.clip(dx, -wp, wp), np.clip(dy, -wp, wp)


def _region_px(region: np.ndarray, seed: int, px, py):
    """Região no pixel (px, py) do mundo = a do tile em (px + dx, py + dy). Escalar -> int; array -> array uint8."""
    dx, dy = warp_px(seed, px, py)
    h, w = region.shape
    tx = np.clip(np.floor((np.asarray(px, float) + dx) / C.TILE).astype(np.int64), 0, w - 1)
    ty = np.clip(np.floor((np.asarray(py, float) + dy) / C.TILE).astype(np.int64), 0, h - 1)
    out = region[ty, tx]
    return int(out) if np.ndim(out) == 0 else out


# ---------------------------------------------------------------------------------------------------------------
# Gerador
# ---------------------------------------------------------------------------------------------------------------
def generate_geo(seed: int, w: int, h: int, base: tuple[int, int]) -> Geo:
    rng = np.random.default_rng([seed & 0xFFFFFFFF, 2026, 13])
    s = (seed & 0xFFFF) * 16                      # desloca as sementes do ruído pela seed do mundo
    sx, sy = w / 192, h / 192                     # os números do config são pra um deserto 192×192
    bx, by = base
    ys, xs = np.mgrid[0:h, 0:w].astype(float)

    def pick(lo_hi):
        lo, hi = lo_hi
        return float(rng.uniform(lo, hi))

    height = 0.62 + 0.20 * (fbm(xs, ys, 26, 7 + s, 3) - 0.5)

    # salar: a maior bacia (elipse a leste, borda torcida)
    scx, scy = bx + pick(C.GEO_SALAR_OFFSET[0]) * sx, by + pick(C.GEO_SALAR_OFFSET[1]) * sy
    srx, sry = pick(C.GEO_SALAR_RADII[0]) * sx, pick(C.GEO_SALAR_RADII[1]) * sy
    de = np.hypot((xs - scx) / srx, (ys - scy) / sry) + 0.22 * (fbm(xs, ys, 10, 8 + s, 2) - 0.5)
    bowl = np.clip(1.15 - de, 0, None)
    height -= 0.62 * np.clip(bowl / 1.15, 0, 1) ** 0.55
    salar = de < 1.0

    # depressões pequenas do planalto
    j = C.GEO_BASIN_JITTER
    for k, ((ox, oy), r) in enumerate(C.GEO_BASINS):
        cx = bx + ox * sx + rng.uniform(-j, j)
        cy = by + oy * sy + rng.uniform(-j, j)
        r = r * rng.uniform(0.9, 1.12)
        d = np.hypot(xs - cx, (ys - cy) * 1.25) / r + 0.35 * (fbm(xs, ys, 4, 9 + 13 * k + s, 2) - 0.5)
        height -= 0.50 * np.clip(1 - d, 0, 1) ** 0.6

    # regiões
    region = np.full((h, w), PLATEAU, np.uint8)
    nb = fbm(xs, ys, 14, 10 + s, 2)
    nb2 = fbm(xs, ys, 5, 12 + s, 2)
    bas_x, bas_y = pick(C.GEO_BASALT_X) * sx, pick(C.GEO_BASALT_Y) * sy
    widen = by + pick((18, 30)) * sy                     # o basalto alarga pro sudoeste a partir daqui
    basalt = ((xs < bas_x + 40 * sx * (nb - 0.5) + 12 * sx * (nb2 - 0.5) + np.clip(ys - widen, 0, None) * 0.55)
              & (ys > bas_y + 16 * sy * (nb - 0.5)))
    region[basalt] = BASALT
    height[basalt] += 0.07
    frost = ys < pick(C.GEO_FROST_Y) * sy + 12 * sy * (fbm(xs, ys, 12, 11 + s, 2) - 0.5)
    region[frost] = FROST
    height[frost] += 0.05
    region[salar & ~frost] = SALAR

    # a base fica sempre no planalto, e o núcleo dela é seco
    core = np.hypot(xs + 0.5 - bx, ys + 0.5 - by) < C.GEO_PLATEAU_CORE
    region[core] = PLATEAU
    height[core] = np.maximum(height[core], C.GEO_LEVELS[2] + 0.06)

    geo = Geo(seed, region, height.astype(np.float32), np.zeros((h, w), np.int8), [])
    geo.pockets = _pockets(geo, rng)                     # antes das bacias: o bolsão é seco
    geo.basin = _basins(geo.height)
    geo.formations = _formations(geo, rng, base) + [p.gate for p in geo.pockets]
    geo.formations += _small_formations(geo, base)       # v9: no fim, com gerador próprio (o resto não muda)
    geo.region_px = lambda px, py: _region_px(geo.region, seed, px, py)
    return geo


def _basins(height: np.ndarray) -> np.ndarray:
    """-1 fora de bacia; senão o primeiro nível (0 = L1, 1 = L2, 2 = L3) que cobre o tile."""
    basin = np.full(height.shape, NO_BASIN, np.int8)
    for k in (2, 1, 0):                                  # do mais alto pro mais baixo: o mais fundo ganha
        basin[height < C.GEO_LEVELS[k]] = k
    return basin


def _pockets(geo: Geo, rng: np.random.Generator) -> list[Pocket]:
    """2 ou 3 bolsões na borda norte. Cada um: interior POCKET_SIZE começando na linha 3, anel de POCKET_WALL tiles
    (ligado à cordilheira da borda), com um gelo-portão 4×2 no meio do muro de baixo e um avental livre na frente."""
    h, w = geo.region.shape
    pw, ph = C.POCKET_SIZE
    wall = C.POCKET_WALL
    spec = FORMATION_SPECS["ice_gate"]
    gate_w = max(x for x, _ in spec.footprint) + 1
    gate_h = max(y for _, y in spec.footprint) + 1
    top = 3
    gate_y = top + ph                                    # o portão ocupa as linhas do muro de baixo
    count = int(rng.integers(C.ICE_GATES[0], C.ICE_GATES[1] + 1))
    margin = pw // 2 + wall + 8
    centers: list[int] = []
    for _ in range(400):
        if len(centers) >= count:
            break
        cx = int(rng.integers(margin, w - margin))
        if all(abs(cx - o) >= C.POCKET_SPACING for o in centers):
            centers.append(cx)
    pockets = []
    for cx in sorted(centers):
        x0 = cx - pw // 2                               # interior: x0..x0+pw-1, top..top+ph-1
        gx = x0 + (pw - gate_w) // 2
        interior = {(x, y) for x in range(x0, x0 + pw) for y in range(top, top + ph)}
        interior -= {(x0, top + ph - 1), (x0 + pw - 1, top + ph - 1)}          # cantos de baixo arredondados
        gate = Formation("ice_gate", gx, gate_y, list(spec.footprint), spec.anchor)
        gate_tiles = set(gate.tiles)
        outer = {(x, y) for x in range(x0 - wall, x0 + pw + wall) for y in range(0, gate_y + gate_h)}
        ring = outer - interior - gate_tiles
        apron = {(x, y) for x in range(gx - 1, gx + gate_w + 1) for y in range(gate_y + gate_h, gate_y + gate_h + 2)}
        # contorno de fora irregular: um tile a mais aqui e ali (nunca no avental nem na frente do portão)
        for x, y in sorted(outer):
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y + 1)):
                if (nx, ny) in outer or (nx, ny) in apron or abs(nx - (gx + gate_w / 2)) < gate_w / 2 + 2:
                    continue
                if ny < gate_y + gate_h + 1 and hash2(nx, ny, geo.seed + 71) < 0.4:
                    ring.add((nx, ny))
        ring = {(x, y) for x, y in ring if 0 <= x < w and 0 <= y < h}
        for x, y in interior | ring | gate_tiles | apron:
            if 0 <= x < w and 0 <= y < h:
                geo.region[y, x] = FROST
                geo.height[y, x] = max(geo.height[y, x], C.GEO_LEVELS[2] + 0.06)
        pockets.append(Pocket(gate, sorted(interior), sorted(ring), sorted(apron),
                              wreck_spot=(x0 + 1, top + 1), container_spot=(x0 + pw - 2, top + 1)))
    return pockets


def _formations(geo: Geo, rng: np.random.Generator, base: tuple[int, int]) -> list[Formation]:
    """Formações na região de cada uma: a caixa da pegada + o halo inteiro na mesma região, fora de bacia (a
    crosta de sal pode: no Verde vira ilhota), longe da base, da borda e das outras formações."""
    h, w = geo.region.shape
    bx, by = base
    halo = C.FORMATION_HALO + 1
    placed: list[Formation] = []
    for kind, (lo, hi) in C.GEO_FORMATIONS.items():
        spec = FORMATION_SPECS[kind]
        fw = max(x for x, _ in spec.footprint) + 1
        fh = max(y for _, y in spec.footprint) + 1
        want = int(rng.integers(lo, hi + 1))
        cands = np.argwhere(geo.region == spec.region)
        if len(cands) == 0:
            continue
        order = rng.permutation(len(cands))
        got = 0
        for i in order[:3000]:
            if got >= want:
                break
            ty, tx = (int(v) for v in cands[i])
            if tx - halo < 6 or ty - halo < 6 or tx + fw + halo > w - 6 or ty + fh + halo > h - 6:
                continue
            f = Formation(kind, tx, ty, list(spec.footprint), spec.anchor)
            cx, cy = f.center
            if math.hypot(cx - bx, cy - by) < C.FORMATION_MIN_BASE_DIST:
                continue
            if any(math.hypot(cx - o.center[0], cy - o.center[1]) < C.FORMATION_SPACING for o in placed):
                continue
            area_r = geo.region[ty - halo:ty + fh + halo, tx - halo:tx + fw + halo]
            if (area_r != spec.region).any():
                continue
            if kind != "salt_ridge" and (geo.basin[ty - halo:ty + fh + halo, tx - halo:tx + fw + halo] >= 0).any():
                continue
            placed.append(f)
            got += 1
    return placed


def _small_formations(geo: Geo, base: tuple[int, int]) -> list[Formation]:
    """Formações pequenas da v9 (M3.0), pelas regras das grandes com números menores: a caixa da pegada + a folga
    (SMALL_FORMATION_HALO) inteiras na região e fora de bacia (nenhuma no leito seco; o pilar de sal pode, como a
    crosta de sal: o salar é quase todo bacia e ele vira ilhota no Verde), longe da base, da borda, dos
    bolsões e de qualquer outra formação. O gerador é próprio, então as grandes e os bolsões não mudam."""
    rng = np.random.default_rng([geo.seed & 0xFFFFFFFF, 2026, 30])
    h, w = geo.region.shape
    bx, by = base
    halo = C.SMALL_FORMATION_HALO
    blocked = set()
    for p in geo.pockets:
        blocked |= set(p.interior) | set(p.ring) | set(p.apron)
    others = list(geo.formations)
    placed: list[Formation] = []
    for kind, (lo, hi) in C.GEO_SMALL_FORMATIONS.items():
        spec = FORMATION_SPECS[kind]
        fw = max(x for x, _ in spec.footprint) + 1
        fh = max(y for _, y in spec.footprint) + 1
        want = int(rng.integers(lo, hi + 1))
        cands = np.argwhere(geo.region == spec.region)
        if len(cands) == 0:
            continue
        got = 0
        for i in rng.permutation(len(cands))[:4000]:
            if got >= want:
                break
            ty, tx = (int(v) for v in cands[i])
            if tx - halo < 6 or ty - halo < 6 or tx + fw + halo > w - 6 or ty + fh + halo > h - 6:
                continue
            f = Formation(kind, tx, ty, list(spec.footprint), spec.anchor)
            cx, cy = f.center
            if math.hypot(cx - bx, cy - by) < C.SMALL_FORMATION_MIN_BASE_DIST:
                continue
            if any(math.hypot(cx - o.center[0], cy - o.center[1]) < C.SMALL_FORMATION_SPACING
                   for o in others + placed):
                continue
            ys, xs = slice(ty - halo, ty + fh + halo), slice(tx - halo, tx + fw + halo)
            if (geo.region[ys, xs] != spec.region).any():
                continue
            if kind not in C.SMALL_FORMATION_BASIN_OK and (geo.basin[ys, xs] >= 0).any():
                continue
            if any((x, y) in blocked for x in range(xs.start, xs.stop) for y in range(ys.start, ys.stop)):
                continue
            placed.append(f)
            got += 1
    return placed
