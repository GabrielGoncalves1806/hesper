"""Autotile da água por minitiles (layout "A2" do RPG Maker), pra poça parecer poça e não quadrado.

Atlas 64×96 em minitiles de 16×16 (colunas 0..3, linhas 0..5):

    linhas 0-1, colunas 0-1  poça isolada (1 tile sozinho, vira gota redonda)
    linhas 0-1, colunas 2-3  cantos internos (a terra só aparece na quina da diagonal)
    linhas 2-5, colunas 0-3  um "lago" 2×2 tiles: cantos externos, bordas e miolo

Cada tile de água é montado com 4 quadrantes (TL, TR, BL, BR). Cada quadrante olha só os 3 vizinhos
do canto dele (o do lado, o de cima/baixo e o da diagonal) e escolhe uma de 5 peças:

    lado e vertical secos      -> canto externo
    só o lado é água           -> borda de cima/baixo (a margem corre na horizontal)
    só a vertical é água       -> borda da esquerda/direita
    os dois e a diagonal       -> miolo
    os dois, diagonal seca     -> canto interno

São 47 combinações de verdade; o `WaterTiles` compõe cada uma uma vez (por estágio) e guarda.

Sem o sprite da Designer (`water_auto_{stage}.png`), `build_atlas` gera o atlas por código a partir do
tile `water_{stage}` e da paleta: máscara de cantos arredondados, margem escura, linha de brilho e
miolo mais fundo, pixel art (sem antialias).
"""

from collections import deque

import pygame

from game import config as C

M = C.TILE // 2   # lado do minitile (16 px)

OUTER, HEDGE, VEDGE, INNER, FULL = "outer", "hedge", "vedge", "inner", "full"
QUADRANTS = ("TL", "TR", "BL", "BR")
# (dx, dy) do canto de cada quadrante
CORNER = {"TL": (-1, -1), "TR": (1, -1), "BL": (-1, 1), "BR": (1, 1)}

# minitile (coluna, linha) no atlas de cada peça por quadrante (mesma tabela do RPG Maker MV)
SOURCE = {
    "TL": {OUTER: (0, 2), HEDGE: (2, 2), VEDGE: (0, 4), FULL: (2, 4), INNER: (2, 0)},
    "TR": {OUTER: (3, 2), HEDGE: (1, 2), VEDGE: (3, 4), FULL: (1, 4), INNER: (3, 0)},
    "BL": {OUTER: (0, 5), HEDGE: (2, 5), VEDGE: (0, 3), FULL: (2, 3), INNER: (2, 1)},
    "BR": {OUTER: (3, 5), HEDGE: (1, 5), VEDGE: (3, 3), FULL: (1, 3), INNER: (3, 1)},
}
ISOLATED = {"TL": (0, 0), "TR": (1, 0), "BL": (0, 1), "BR": (1, 1)}
OFFSET = {"TL": (0, 0), "TR": (M, 0), "BL": (0, M), "BR": (M, M)}


def piece(side: bool, vertical: bool, diagonal: bool) -> str:
    """Peça de um quadrante a partir dos 3 vizinhos do canto dele (True = água)."""
    if side and vertical:
        return FULL if diagonal else INNER
    if side:
        return HEDGE
    if vertical:
        return VEDGE
    return OUTER


def tile_key(wet, tx: int, ty: int) -> tuple[str, str, str, str]:
    """As 4 peças (TL, TR, BL, BR) do tile de água (tx, ty). `wet(x, y)` diz se o vizinho é água."""
    key = []
    for q in QUADRANTS:
        dx, dy = CORNER[q]
        key.append(piece(wet(tx + dx, ty), wet(tx, ty + dy), wet(tx + dx, ty + dy)))
    return tuple(key)


def sources(key: tuple[str, str, str, str]) -> list[tuple[str, tuple[int, int]]]:
    """(quadrante, minitile do atlas) pra montar o tile. Tudo canto externo = poça isolada."""
    if all(p == OUTER for p in key):
        return [(q, ISOLATED[q]) for q in QUADRANTS]
    return [(q, SOURCE[q][p]) for q, p in zip(QUADRANTS, key)]


# ---------------------------------------------------------------------------
# Atlas procedural (fallback até a Designer entregar water_auto_{stage}.png)
# ---------------------------------------------------------------------------
INSET = 3          # px de areia entre a borda do tile e a água, onde o vizinho é seco
RADIUS = 10        # raio dos cantos externos
RIM = 2            # margem escura (px)
DEEP_FROM = 7      # a partir dessa distância da margem, água funda


def _rounded(w: int, h: int, inset: int, radius: int):
    """Máscara (lista de linhas de bool) de um retângulo de cantos arredondados, inset px pra dentro."""
    x0, y0, x1, y1 = inset, inset, w - inset, h - inset

    def inside(x, y):
        px, py = x + 0.5, y + 0.5
        if not (x0 <= px < x1 and y0 <= py < y1):
            return False
        cx = min(max(px, x0 + radius), x1 - radius)
        cy = min(max(py, y0 + radius), y1 - radius)
        return (px - cx) ** 2 + (py - cy) ** 2 <= radius * radius

    return [[inside(x, y) for x in range(w)] for y in range(h)]


def _inner_block():
    """Bloco 32×32 dos cantos internos: água em tudo, menos uma quina de areia em cada canto."""
    size = C.TILE
    r = INSET

    def land(x, y):
        dx = x if x < size / 2 else size - 1 - x
        dy = y if y < size / 2 else size - 1 - y
        if dx >= r or dy >= r:
            return False
        return True

    return [[not land(x, y) for x in range(size)] for y in range(size)]


def _distances(mask, outside_is_water: bool):
    """Distância (em px, 4-vizinhos) de cada pixel de água até a areia mais perto, e de cada pixel
    de areia até a água mais perto (negativa). Fora do bloco conta como água ou areia."""
    h, w = len(mask), len(mask[0])
    dist = [[0] * w for _ in range(h)]
    for want_water in (True, False):
        queue = deque()
        seen = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if mask[y][x] != want_water:
                    continue
                border = any(not (0 <= x + dx < w and 0 <= y + dy < h) and outside_is_water != want_water
                             or (0 <= x + dx < w and 0 <= y + dy < h and mask[y + dy][x + dx] != want_water)
                             for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if border:
                    seen[y][x] = True
                    dist[y][x] = 1
                    queue.append((x, y))
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and mask[ny][nx] == want_water:
                    seen[ny][nx] = True
                    dist[ny][nx] = dist[y][x] + 1
                    queue.append((nx, ny))
        if not want_water:
            for y in range(h):
                for x in range(w):
                    if not mask[y][x]:
                        dist[y][x] = -(dist[y][x] or 99)
    return dist


def _mix(a, b, k: float):
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def _paint(atlas: pygame.Surface, texture: pygame.Surface, ox: int, oy: int, mask, outside_is_water: bool,
           palette: dict) -> None:
    deep = pygame.Color(palette["water_d"])[:3]
    foam = pygame.Color(palette["foam"])[:3]
    dist = _distances(mask, outside_is_water)
    tw, th = texture.get_size()
    for y, row in enumerate(dist):
        for x, d in enumerate(row):
            px, py = ox + x, oy + y
            if d < 0:   # areia molhada logo em volta da água: sombra suave por cima do chão
                if d >= -2:
                    atlas.set_at((px, py), (20, 14, 10, 70 if d == -1 else 36))
                continue
            base = texture.get_at((px % tw, py % th))[:3]
            if d <= RIM:
                color = _mix(base, (12, 22, 34), 0.42 if d == 1 else 0.28)
            elif d == RIM + 1:
                color = _mix(base, foam, 0.45)
            elif d >= DEEP_FROM:
                color = _mix(base, deep, 0.85)
            else:
                color = base
            atlas.set_at((px, py), (*color, 255))


def build_atlas(texture: pygame.Surface, stage: str) -> pygame.Surface:
    """Atlas A2 64×96 gerado por código a partir do tile de água (32×32) e da paleta do estágio."""
    palette = C.PALETTES[stage]
    atlas = pygame.Surface((4 * M, 6 * M), pygame.SRCALPHA)
    atlas.fill((0, 0, 0, 0))
    _paint(atlas, texture, 0, 0, _rounded(C.TILE, C.TILE, INSET, RADIUS), False, palette)
    _paint(atlas, texture, C.TILE, 0, _inner_block(), True, palette)
    _paint(atlas, texture, 0, C.TILE, _rounded(2 * C.TILE, 2 * C.TILE, INSET, RADIUS), False, palette)
    return atlas


class WaterTiles:
    """Compõe e guarda os tiles de água prontos: no máximo 47 por estágio (um por combinação)."""

    def __init__(self):
        self._tiles: dict[tuple, pygame.Surface] = {}

    def get(self, atlas_id: str, atlas: pygame.Surface, key: tuple[str, str, str, str]) -> pygame.Surface:
        cache_key = (atlas_id, key)
        tile = self._tiles.get(cache_key)
        if tile is None:
            tile = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
            for q, (col, row) in sources(key):
                tile.blit(atlas, OFFSET[q], (col * M, row * M, M, M))
            self._tiles[cache_key] = tile
        return tile

    def __len__(self) -> int:
        return len(self._tiles)
