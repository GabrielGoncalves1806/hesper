"""Gerador da SUPERFÍCIE (bíblia §9 e §11 · v0.4 Marco 2, "Geografia nova").

Monta um `World` de 192×192 com a mesma interface do mapa antigo, então todo o resto do jogo
(colisão, mineração, render, transição de estágio, água e plantas) funciona igual. Ordem:

    geografia (game/geo.py: relevo, regiões, bacias, formações, bolsões)  →  areia + lowness
    →  borda (cordilheira, 2–3 tiles)  →  bolsões dos gelos-portão (anel de BEDROCK)  →  morros por região
    →  limpa a área da cápsula  →  pegadas das formações (C.FORMATION)  →  cratera 3×3 no planalto
    →  veios (3 a 5, longe)  →  destroços (6 a 8, game/wrecks.py)  →  destroço rico e contêiner lacrado nos bolsões
    (v0.4 M3.2)  →  afloramentos  →  rochas pequenas

Nada nasce em bacia (a água do Marco 3 sobe ali), nem no halo das formações, nem no bolsão ou no avental de
um gelo-portão (`world.keep_clear`). O que fica atrás de um portão só é alcançável passando por ele.

Tudo sai da seed: mesma seed, mesmo deserto. A geração custa ~0,3 s, então o mapa virgem de cada
seed fica num cache e `generate_surface` devolve uma CÓPIA (o jogador mexe na cópia).

Python puro (sem pygame), testado em tests/test_surface_gen.py.
"""

import math
import random

import numpy as np

from game import config as C
from game import wrecks as wreck_gen
from game.geo import REGION_NAMES, add_vents, generate_geo
from game.world import Vein, World, hash01, value_noise

_cache: dict[int, World] = {}


def generate_surface(seed: int = C.WORLD_SEED) -> World:
    """Deserto da seed `seed`: uma cópia nova (pode mexer à vontade)."""
    if seed not in _cache:
        _cache[seed] = _build(seed)
    return _copy(_cache[seed])


def pristine_tiles(seed: int) -> list[list[int]]:
    """Os tiles do deserto recém-gerado (só leitura: é o que o save usa pra saber o que mudou)."""
    if seed not in _cache:
        _cache[seed] = _build(seed)
    return _cache[seed].tiles


# ---------------------------------------------------------------------------
# Variação da areia (sand_{stage}_{v}): lógica da Designer (tools/sprites/build_sprites.py · sand_variant),
# copiada aqui igual, com o mesmo hash e ruído, pra o jogo bater com as prévias aprovadas.
# 0 areia lisa (~72% fora das zonas) · 1 cascalho (~20%) · 2 dunas (faixas largas) · 3 laje (rara)
# ---------------------------------------------------------------------------
SAND_SEED = 5


def _hsh(x: int, y: int, s: int) -> float:
    n = (x * 374761393 + y * 668265263 + s * 2246822519 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    n = (n * 2246822519) & 0xFFFFFFFF
    n ^= n >> 15
    return n / 4294967296.0


def _vnoise(x: float, y: float, s: int) -> float:
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hsh(ix, iy, s), _hsh(ix + 1, iy, s)
    c, d = _hsh(ix, iy + 1, s), _hsh(ix + 1, iy + 1, s)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


def sand_variant(x: int, y: int, seed: int = SAND_SEED) -> int:
    dune = _vnoise(x * 0.11 + 3.1, y * 0.23 + 1.7, seed)        # faixas mais largas que altas = vento
    rock = _vnoise(x * 0.17 + 40.3, y * 0.17 + 9.2, seed + 1)
    r = _hsh(x, y, seed + 2)
    if dune > 0.6 and r < 0.55:
        return 2
    if rock > 0.66 and r < 0.12:
        return 3
    return 0 if r < 0.72 else 1 if r < 0.92 else 2 if r < 0.965 else 3


def _copy(src: World) -> World:
    world = World(src.seed, src.width, src.height)
    world.tiles = [row[:] for row in src.tiles]
    world.lowness = src.lowness                 # só leitura: dá pra dividir
    world.veins = list(src.veins)
    world._vein_tiles = dict(src._vein_tiles)
    world.center, world.floor_kind, world.crater = src.center, src.floor_kind, src.crater
    world.terminals = list(src.terminals)
    world.sand_variants = src.sand_variants     # só leitura
    world.wrecks = list(src.wrecks)             # destroços: geometria fixa (o conteúdo das caixas fica na camada)
    world.geo, world.keep_clear = src.geo, src.keep_clear   # só leitura
    world.containers = list(src.containers)
    world.closed_gate_tiles = src.closed_gate_tiles
    world._geo_rows = src._geo_rows             # só leitura (altura/bacia/beira em listas, se já calculou)
    return world


# ---------------------------------------------------------------------------
def _build(seed: int) -> World:
    world = World(seed, C.SURFACE_W, C.SURFACE_H)
    world.center = C.BASE_TILE
    world.floor_kind = C.SAND
    rng = random.Random(seed * 7919 + 101)
    W, H = world.width, world.height
    geo = world.geo = generate_geo(seed, W, H, world.center)
    for y in range(H):
        for x in range(W):
            world.tiles[y][x] = C.SAND
            world.lowness[y][x] = value_noise(x * 0.22 + 200, y * 0.22 + 50, seed + 21)
    _border(world)
    _pockets(world)
    world.keep_clear = frozenset(_keep_clear(geo))
    _hills(world, rng)
    for y in range(H):                           # a área da cápsula fica sempre limpa
        for x in range(W):
            if world.dist_from_center(x, y) < C.SURFACE_CLEAR_RADIUS:
                world.tiles[y][x] = C.SAND
    # v0.4 M3.1: fumarolas do basalto depois dos morros (no chão livre; os morros não mudam) e o keep_clear de novo
    add_vents(geo, world.center, np.array(world.tiles, dtype=np.int16) == C.SAND)
    world.keep_clear = frozenset(_keep_clear(geo))
    for f in geo.formations:                     # a pegada bloqueia; quem desenha é o objeto da formação
        if f.kind == "ice_gate":                 # M3.5: o gelo-portão bate por retângulo (blocos), o chão fica areia
            world.closed_gate_tiles = world.closed_gate_tiles | set(f.tiles)
            continue
        for t in f.tiles:
            world.set(*t, C.FORMATION)
    _crater(world, rng)
    _veins(world, rng)
    wreck_gen.place_wrecks(world, rng)           # Marco 3: destroços (antes das rochas pequenas, com folga livre)
    _pocket_finds(world)                         # v0.4 M3.2: destroço rico e contêiner lacrado atrás dos portões
    _outcrops(world)
    _small_rocks(world)
    world.sand_variants = [bytes(sand_variant(x, y) for x in range(W)) for y in range(H)]
    return world


def _border(world: World) -> None:
    """Cordilheira intransponível: 2 tiles sempre, 3 onde o noise mandar (borda irregular)."""
    lo, hi = C.SURFACE_BORDER
    W, H = world.width, world.height
    for y in range(H):
        for x in range(W):
            edge = min(x, y, W - 1 - x, H - 1 - y)
            thick = hi if value_noise(x * 0.17, y * 0.17, world.seed + 31) > 0.5 else lo
            if edge < thick:
                world.tiles[y][x] = C.BEDROCK


def _pockets(world: World) -> None:
    """Bolsões dos gelos-portão: o anel vira BEDROCK (cordilheira, não minera: o portão não dá pra contornar
    cavando); o interior, o portão e o avental ficam de areia (M3.5: o portão continua areia; quem bloqueia são os
    retângulos dos blocos de gelo, game/ice_blocks.py)."""
    for pocket in world.geo.pockets:
        for t in pocket.ring:
            world.set(*t, C.BEDROCK)
        for t in pocket.interior + pocket.apron + pocket.gate.tiles:
            world.set(*t, C.SAND)


def _pocket_finds(world: World) -> None:
    """v0.4 Marco 3 · M3.2: em cada bolsão, o destroço rico no wreck_spot (game/wrecks.py · pocket_wrecks, depois dos
    destroços de fora, então os ranks deles não mudam) e o contêiner lacrado (C.CONTAINER) no container_spot."""
    rich = wreck_gen.pocket_wrecks(world.geo.pockets, world.wrecks)
    for wreck in rich:
        for t in wreck.tiles:
            world.set(*t, C.WRECK)
        world.set(*wreck.crate, C.LOOT_CRATE)
    world.wrecks = world.wrecks + rich
    world.containers = [p.container_spot for p in world.geo.pockets]
    for t in world.containers:
        world.set(*t, C.CONTAINER)


def _ring(tiles, r: int) -> set[tuple[int, int]]:
    """Os `tiles` e tudo a até `r` tiles deles (distância de Chebyshev)."""
    return {(x + dx, y + dy) for x, y in tiles for dx in range(-r, r + 1) for dy in range(-r, r + 1)}


def _keep_clear(geo) -> set[tuple[int, int]]:
    """Onde nada nasce: a caixa da pegada + o halo de cada formação, e o bolsão inteiro de cada gelo-portão."""
    out: set[tuple[int, int]] = set()
    for f in geo.formations:
        out |= _ring(f.box, C.FORMATION_HALO)
    for p in geo.pockets:
        out |= set(p.interior) | set(p.ring) | set(p.apron)
    return out


def _hills(world: World, rng: random.Random) -> None:
    """Morros: blobs de rocha de 3 a 8 tiles, com um pouco de minério. Não encostam um no outro.

    A forma sai de `_hill_shape` (lóbulos redondos + suavização), então o morro não fica com cara de
    bloco escalonado nem solta tile pendurado na diagonal. Os morros têm o próprio gerador aleatório
    (`hrng`), assim mexer na forma deles não embaralha o resto do mapa daqui pra frente.

    Marco 2: a região do centro decide a chance de o morro ficar (HILL_REGION_WEIGHT: o salar quase sem morro,
    o basalto com mais) e o minério de cada tile sai da região dele (HILL_REGION_ORE). Morro nenhum em bacia,
    perto de formação (FORMATION_HILL_GAP) ou encostando num bolsão de gelo-portão."""
    lo, hi = C.HILLS
    geo = world.geo
    hrng = random.Random(world.seed * 104729 + 7)
    target = rng.randint(lo, hi)
    placed, tries = 0, 0
    cx0, cy0 = world.center
    top = max(C.HILL_REGION_WEIGHT.values())
    taken: set[tuple[int, int]] = set()
    for f in geo.formations:                     # + o halo de 2 do morro = a folga toda (as pequenas: 3 tiles)
        taken |= set(f.box) if f.small else _ring(f.box, C.FORMATION_HILL_GAP - 2)
    for p in geo.pockets:
        taken |= set(p.ring) | set(p.apron) | set(p.interior)
    while placed < target and tries < 4000:
        tries += 1
        size = hrng.randint(*C.HILL_SIZE)
        x0 = hrng.randint(5, world.width - 6 - size)
        y0 = hrng.randint(5, world.height - 6 - size)
        if math.hypot(x0 + size / 2 - cx0, y0 + size / 2 - cy0) < C.SURFACE_CLEAR_RADIUS + size:
            continue
        region = REGION_NAMES[geo.region_at(x0 + size // 2, y0 + size // 2)]
        if hrng.random() >= C.HILL_REGION_WEIGHT[region] / top:
            continue
        blob = [(x0 + dx, y0 + dy) for dx, dy in _hill_shape(size, hrng)]
        if len(blob) < 3 or any(geo.basin_at(x, y) >= 0 for x, y in blob):
            continue
        # folga de 2 tiles entre morros (senão viram um paredão maior que 8)
        halo = _ring(blob, 2)
        if halo & taken:
            continue
        for x, y in blob:
            kind = C.ROCK
            tile_region = REGION_NAMES[geo.region_at(x, y)]
            if hrng.random() < C.HILL_REGION_ORE_CHANCE[tile_region]:
                ores = C.HILL_REGION_ORE[tile_region]
                kind = _weighted(hrng.random(), {C.IRON: ores["iron"], C.SILICON: ores["silicon"], C.ICE: ores["ice"]})
            world.tiles[y][x] = kind
        taken |= set(blob)
        placed += 1


def _hill_shape(size: int, rng: random.Random) -> set[tuple[int, int]]:
    """Forma de um morro dentro de uma caixa size×size (coordenadas locais).

    1. um lóbulo principal (elipse um pouco achatada pra um lado) e 1 ou 2 lóbulos menores colados nele,
       com a borda tremida por um ruído de ângulo (contorno irregular, não um quadrado nem um círculo);
    2. suavização por autômato celular (fica rocha quem tem ≥ 5 de 9 em volta);
    3. limpeza: tira ponta solta (tile com ≤ 1 vizinho de lado), tapa dente de 1 tile (vazio com ≥ 3
       vizinhos de rocha) e fecha encontro só pela quina (2×2 em xadrez), até parar de mudar;
    4. fica só o maior pedaço ligado pelos lados.
    """
    cells = {(x, y) for y in range(size) for x in range(size)}
    r = size / 2
    lobes = [(r, r, r * rng.uniform(0.95, 1.1), r * rng.uniform(0.8, 1.0))]
    if rng.random() < 0.5:                       # elipse deitada ou em pé
        cx, cy, rx, ry = lobes[0]
        lobes[0] = (cx, cy, ry, rx)
    if size >= 5:
        for _ in range(rng.randint(1, 2)):
            ang = rng.uniform(0, math.tau)
            d = r * rng.uniform(0.35, 0.55)
            lr = r * rng.uniform(0.45, 0.65)
            lobes.append((r + d * math.cos(ang), r + d * math.sin(ang), lr, lr))
    phase, wobble = rng.uniform(0, math.tau), rng.uniform(0.08, 0.18)
    k = rng.choice((2, 3))
    shape = set()
    for x, y in cells:
        px, py = x + 0.5, y + 0.5
        for cx, cy, rx, ry in lobes:
            ang = math.atan2(py - cy, px - cx)
            edge = 1.0 + wobble * math.sin(k * ang + phase)
            if ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= edge * edge:
                shape.add((x, y))
                break

    def around(t):
        return sum((t[0] + dx, t[1] + dy) in shape for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    if size >= 5:                                # nos pequenos a suavização come o morro inteiro
        shape = {t for t in cells if around(t) >= 5}
    return _tidy(shape, cells)


def _sides(shape, x: int, y: int) -> int:
    return sum(n in shape for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))


def _tidy(shape: set, cells: set) -> set:
    """Limpeza do contorno (ver `_hill_shape`, passo 3 e 4)."""
    shape = set(shape)
    for _ in range(20):
        changed = False
        for t in sorted(shape):                  # ponta solta / tile ilhado
            if _sides(shape, *t) <= 1:
                shape.discard(t)
                changed = True
        for t in sorted(cells - shape):          # dente de 1 tile entrando no morro
            if _sides(shape, *t) >= 3:
                shape.add(t)
                changed = True
        for x, y in sorted(cells):               # só encosta pela quina: fecha a quina com um tile
            a, b, c, d = (x, y) in shape, (x + 1, y) in shape, (x, y + 1) in shape, (x + 1, y + 1) in shape
            if (a and d and not b and not c) or (b and c and not a and not d):
                gaps = ((x + 1, y), (x, y + 1)) if a else ((x, y), (x + 1, y + 1))
                shape.add(gaps[0] if gaps[0] in cells else gaps[1])
                changed = True
        if not changed:
            break
    best: set = set()                            # o maior pedaço ligado pelos lados
    left = set(shape)
    while left:
        part, stack = set(), [left.pop()]
        while stack:
            x, y = stack.pop()
            part.add((x, y))
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in left:
                    left.discard(n)
                    stack.append(n)
        if len(part) > len(best):
            best = part
    return best


def _crater(world: World, rng: random.Random) -> None:
    """Cratera 3×3 a 15–20 tiles da base, com uma folga de areia em volta.

    Ponto de extensão (Marco 2): `world.crater` guarda o canto de cima à esquerda; a rampa de descida
    vai ser desenhada aqui (crater_ramp.png) e o E nesse ponto troca de camada.
    v0.4 Marco 2: a cratera e a folga ficam inteiras no planalto, fora de bacia e de formação."""
    cx, cy = world.center
    lo, hi = C.SURFACE_CRATER_DIST
    geo = world.geo

    def fits(mx, my):                            # a folga de areia não corta morro (senão sobra um toco solto)
        area = [(x, y) for y in range(my - 4, my + 5) for x in range(mx - 4, mx + 5)]
        return all(geo.region_at(x, y) == 0 and geo.basin_at(x, y) < 0 and (x, y) not in world.keep_clear
                   and world.get(x, y) == C.SAND for x, y in area)

    for _ in range(500):
        angle, dist = rng.uniform(0, math.tau), rng.uniform(lo + 0.5, hi - 0.5)
        mx, my = int(cx + dist * math.cos(angle)), int(cy + dist * math.sin(angle))
        if lo <= world.dist_from_center(mx, my) <= hi and fits(mx, my):
            break
    tx, ty = mx - 1, my - 1
    for y in range(ty - 2, ty + 5):              # areia limpa em volta (dá pra chegar de todo lado)
        for x in range(tx - 2, tx + 5):
            world.set(x, y, C.SAND)
    for dy in range(3):
        for dx in range(3):
            world.set(tx + dx, ty + dy, C.CRATER)
    world.crater = (tx, ty)


def _veins(world: World, rng: random.Random) -> None:
    """3 a 5 veios 2×2, longe da base, em areia aberta, um de cada recurso primeiro."""
    lo, hi = C.SURFACE_VEINS
    count = rng.randint(lo, hi)
    resources = list(C.RESOURCES)
    rng.shuffle(resources)
    resources += [rng.choice(C.RESOURCES) for _ in range(count - len(resources))]
    cx, cy = world.center
    max_dist = min(world.width, world.height) / 2 - 8
    crater = world.crater

    def ok(tx, ty):
        area = [(tx + dx, ty + dy) for dx in range(-1, 3) for dy in range(-1, 4)]   # 2×2 + linha de baixo + folga
        if not all(world.get(*t) == C.SAND for t in area):
            return False
        if any(t in world.keep_clear or world.geo.basin_at(*t) >= 0 for t in area):   # Marco 2: nem bacia nem marco
            return False
        if any(world.dist_from_center(tx + dx, ty + dy) < C.SURFACE_VEIN_MIN_DIST for dx in (0, 1) for dy in (0, 1)):
            return False
        if crater and math.hypot(tx - crater[0], ty - crater[1]) < 8:
            return False
        return all(math.hypot(tx - v.tx, ty - v.ty) >= C.SURFACE_VEIN_SPACING for v in world.veins)

    for resource in resources:
        for _ in range(3000):
            angle = rng.uniform(0, math.tau)
            dist = rng.uniform(C.SURFACE_VEIN_MIN_DIST + 2, max_dist)
            tx, ty = int(cx + dist * math.cos(angle)) - 1, int(cy + dist * math.sin(angle)) - 1
            if ok(tx, ty):
                world.veins.append(Vein(resource, tx, ty))
                for t in world.veins[-1].tiles:
                    world._vein_tiles[t] = world.veins[-1]
                break


def _outcrops(world: World) -> None:
    """Afloramentos: 3 ou 4 rochas pequenas a 1–2 tiles da pegada de cada formação (o gelo-portão não tem), com o
    minério da região (OUTCROP_ORE). Nunca no vão do arco, e espaçadas (nenhuma encosta na outra pelo lado)."""
    for i, f in enumerate(world.geo.formations):
        if f.kind == "ice_gate" or f.small:          # o portão e as pequenas da v9 (miúdas) não têm
            continue
        if f.kind.startswith("vent_"):           # M3.1: fumarola é formação pequena (sem afloramento)
            continue
        rng = random.Random(world.seed * 6151 + i * 97 + 3)
        box = set(f.box)
        w, _ = f.size
        cands = sorted(t for t in _ring(f.tiles, 2) - box
                       if world.get(*t) == C.SAND and world.geo.basin_at(*t) < 0     # nem na bacia (vira lago)
                       and not (f.kind == "arch" and f.tx < t[0] < f.tx + w - 1))
        rng.shuffle(cands)
        ores = C.OUTCROP_ORE[REGION_NAMES[f.region]]
        kinds = {C.SMALL_IRON: ores.get("iron", 0), C.SMALL_SILICON: ores.get("silicon", 0),
                 C.SMALL_ICE: ores.get("ice", 0)}
        want = rng.randint(*C.OUTCROPS)
        got: list[tuple[int, int]] = []
        for x, y in cands:
            if len(got) >= want:
                break
            if any(abs(x - gx) + abs(y - gy) <= 1 for gx, gy in got):
                continue
            world.set(x, y, _weighted(rng.random(), kinds))
            got.append((x, y))


def _small_rocks(world: World) -> None:
    """Rochas pequenas espalhadas pela areia (por hash, sem formar padrão). Nunca na bacia: no Marco 3 ela vira lago."""
    geo = world.geo
    keep_free = set(world._vein_tiles) | wreck_gen.keep_free(world.wrecks) | world.keep_clear
    for v in world.veins:                         # a linha de baixo do veio fica livre (o player para ali)
        keep_free |= {(v.tx + dx, v.ty + 2) for dx in (0, 1)}
    kinds = {C.SMALL_IRON: C.SMALL_ROCK_WEIGHTS["iron"], C.SMALL_SILICON: C.SMALL_ROCK_WEIGHTS["silicon"],
             C.SMALL_ICE: C.SMALL_ROCK_WEIGHTS["ice"]}
    for y in range(world.height):
        for x in range(world.width):
            if world.tiles[y][x] != C.SAND or (x, y) in keep_free:
                continue
            if world.dist_from_center(x, y) < C.SMALL_ROCK_MIN_DIST:
                continue
            if geo is not None and geo.basin_at(x, y) >= 0:
                continue
            if hash01(x, y, world.seed + 61) < C.SMALL_ROCK_CHANCE:
                world.tiles[y][x] = _weighted(hash01(x, y, world.seed + 62), kinds)


def _weighted(r: float, weights: dict):
    acc = 0.0
    total = sum(weights.values())
    for key, w in weights.items():
        acc += w / total
        if r < acc:
            return key
    return key
