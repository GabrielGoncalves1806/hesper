"""Água com autotile (layout A2): escolha de minitile, cache dos tiles montados e suavização das poças."""

import ast
import itertools
from pathlib import Path

import pygame
import pytest

from game import autotile as A
from game import config as C
from game.surface_gen import generate_surface
from game.world import World

ROOT = Path(__file__).resolve().parents[1]
DIRS = {"u": (0, -1), "d": (0, 1), "l": (-1, 0), "r": (1, 0),
        "ul": (-1, -1), "ur": (1, -1), "dl": (-1, 1), "dr": (1, 1)}


def key_for(*wet_tiles):
    """tile_key do tile (0, 0) com água só nos vizinhos dados (dx, dy)."""
    wet = set(wet_tiles) | {(0, 0)}
    return A.tile_key(lambda x, y: (x, y) in wet, 0, 0)


ALL8 = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]


# ---------------------------------------------------------------- escolha de minitile
def test_isolated_uses_the_round_puddle_block():
    key = key_for()
    assert key == (A.OUTER,) * 4
    assert A.sources(key) == [("TL", (0, 0)), ("TR", (1, 0)), ("BL", (0, 1)), ("BR", (1, 1))]
    # só diagonais também é "isolada" pro desenho (a geração nem deixa isso acontecer, ver abaixo)
    assert A.sources(key_for((1, 1), (-1, -1))) == A.sources(key)


def test_interior_uses_the_middle_of_the_lake():
    key = key_for(*ALL8)
    assert key == (A.FULL,) * 4
    assert dict(A.sources(key)) == {"TL": (2, 4), "TR": (1, 4), "BL": (2, 3), "BR": (1, 3)}


def test_horizontal_line_uses_top_and_bottom_edges_and_rounded_ends():
    mid = key_for((-1, 0), (1, 0))
    assert mid == (A.HEDGE,) * 4
    assert dict(A.sources(mid)) == {"TL": (2, 2), "TR": (1, 2), "BL": (2, 5), "BR": (1, 5)}
    left_end = key_for((1, 0))                       # ponta esquerda: cantos externos à esquerda
    assert left_end == (A.OUTER, A.HEDGE, A.OUTER, A.HEDGE)
    assert dict(A.sources(left_end)) == {"TL": (0, 2), "TR": (1, 2), "BL": (0, 5), "BR": (1, 5)}


def test_vertical_line_uses_side_edges():
    key = key_for((0, -1), (0, 1))
    assert key == (A.VEDGE,) * 4
    assert dict(A.sources(key)) == {"TL": (0, 4), "TR": (3, 4), "BL": (0, 3), "BR": (3, 3)}


def test_outer_corner_of_a_lake():
    key = key_for((1, 0), (0, 1), (1, 1))            # canto de cima à esquerda de um lago
    assert key == (A.OUTER, A.HEDGE, A.VEDGE, A.FULL)
    assert dict(A.sources(key))["TL"] == (0, 2)


def test_inner_corner_when_only_the_diagonal_is_dry():
    key = key_for(*[d for d in ALL8 if d != (-1, -1)])
    assert key == (A.INNER, A.FULL, A.FULL, A.FULL)
    assert dict(A.sources(key))["TL"] == (2, 0)
    key = key_for(*[d for d in ALL8 if d != (1, 1)])
    assert dict(A.sources(key))["BR"] == (3, 1)


def _designer_autotile_quads():
    """autotile_quads() do script da Designer (tools/sprites/build_sprites.py), sem importar o script
    inteiro (ele precisa de PIL/numpy): pega só a função pelo AST."""
    src = (ROOT / "tools" / "sprites" / "build_sprites.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "autotile_quads")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "build_sprites.py", "exec"), ns)
    return ns["autotile_quads"]


def test_same_rule_as_the_designer_script_for_all_256_neighbourhoods():
    quads = _designer_autotile_quads()
    for bits in itertools.product((False, True), repeat=8):
        n = dict(zip(DIRS, bits))
        wet = {DIRS[k] for k, v in n.items() if v}
        ours = {(A.OFFSET[q][0], A.OFFSET[q][1]): (c * A.M, r * A.M)
                for q, (c, r) in A.sources(key_for(*wet))}
        theirs = {(dx, dy): (sx, sy) for sx, sy, dx, dy in quads(n)}
        assert ours == theirs, n


@pytest.mark.parametrize("stage", ["mist", "green"])
def test_pending_designer_sprite_composes_like_her_script(stage):
    """Monta os 256 casos com o sprite da Designer (ainda em _pending) pelos dois caminhos e compara pixel a pixel."""
    path = C.SPRITES_DIR / "_pending" / f"water_auto_{stage}.png"
    if not path.exists():
        pytest.skip("sprite pendente não está mais em _pending")
    sheet = pygame.image.load(str(path))
    assert sheet.get_size() == (64, 96)
    quads = _designer_autotile_quads()
    tiles = A.WaterTiles()
    for bits in itertools.product((False, True), repeat=8):
        n = dict(zip(DIRS, bits))
        ours = tiles.get(stage, sheet, key_for(*{DIRS[k] for k, v in n.items() if v}))
        theirs = pygame.Surface((C.TILE, C.TILE), pygame.SRCALPHA)
        for sx, sy, dx, dy in quads(n):
            theirs.blit(sheet, (dx, dy), (sx, sy, 16, 16))
        assert pygame.image.tobytes(ours, "RGBA") == pygame.image.tobytes(theirs, "RGBA"), n


# ---------------------------------------------------------------- cache e atlas
def test_cache_composes_each_combination_once():
    atlas = pygame.Surface((64, 96), pygame.SRCALPHA)
    tiles = A.WaterTiles()
    keys = {key_for(*{d for d, b in zip(ALL8, bits) if b}) for bits in itertools.product((0, 1), repeat=8)}
    assert len(keys) == 47                           # as 47 combinações do A2
    first = {k: tiles.get("mist", atlas, k) for k in keys}
    assert len(tiles) == 47
    assert all(tiles.get("mist", atlas, k) is first[k] for k in keys)   # 2ª vez: mesma surface, sem recompor
    tiles.get("green", atlas, (A.FULL,) * 4)
    assert len(tiles) == 48                          # cada estágio tem o seu


def test_procedural_atlas_is_a_round_puddle():
    tex = pygame.Surface((C.TILE, C.TILE))
    tex.fill(C.PALETTES["mist"]["water"])
    atlas = A.build_atlas(tex, "mist")
    assert atlas.get_size() == (64, 96)
    alpha = lambda x, y: atlas.get_at((x, y)).a       # noqa: E731
    assert alpha(16, 16) == 255                        # miolo da poça isolada
    assert alpha(0, 0) < 255 and alpha(4, 4) < 255     # canto arredondado: areia
    assert alpha(16, 3) == 255 and alpha(16, 1) < 255  # borda reta 3 px pra dentro
    assert alpha(32 + 16, 16) == 255 and alpha(32, 0) < 255   # cantos internos: só a quina é areia
    assert alpha(32, 64) == 255 and alpha(1, 64) < 255        # lago 2×2: borda da esquerda
    # pixel art: alfa só 0, a sombrinha da areia molhada ou 255 (sem antialias no contorno da água)
    assert {atlas.get_at((x, y)).a for y in range(96) for x in range(64)} <= {0, 36, 70, 255}


# ---------------------------------------------------------------- formato das poças
def _diagonal_only(world, stage):
    w = lambda x, y: world.is_water(x, y, stage)      # noqa: E731
    bad = []
    for y in range(world.height):
        for x in range(world.width):
            if not w(x, y):
                continue
            for dx, dy in ((1, 1), (-1, 1)):
                if w(x + dx, y + dy) and not w(x + dx, y) and not w(x, y + dy) \
                        and not any(w(x + a, y + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    bad.append((x, y))
    return bad


@pytest.mark.parametrize("stage", [2, 3])
def test_no_water_tile_touches_others_only_by_the_corner(stage):
    world = generate_surface(C.WORLD_SEED)
    assert not _diagonal_only(world, stage)
    # e nenhuma água sozinha com vizinho na diagonal (xadrez)
    for y in range(world.height):
        for x in range(world.width):
            if world.is_water(x, y, stage) and not any(
                    world.is_water(x + a, y + b, stage) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                assert not any(world.is_water(x + a, y + b, stage) for a in (-1, 1) for b in (-1, 1))


def test_smoothing_rules_on_a_handmade_field():
    world = World(1, 12, 12)
    world.center = (0, 0)
    for row in world.tiles:
        row[:] = [C.SAND] * 12
    world.lowness = [[1.0] * 12 for _ in range(12)]
    for x, y in ((8, 8), (9, 9), (10, 10),          # escadinha só pela diagonal: some tudo
                 (8, 2), (9, 2), (10, 3),           # dupla + um na quina: a dupla fica, o da quina sai
                 (3, 9)):                           # gota sozinha: fica (vira poça redonda)
        world.lowness[y][x] = 0.0
    wet = {(x, y) for y in range(12) for x in range(12) if world.is_water(x, y, 3)}
    assert wet == {(8, 2), (9, 2), (3, 9)}


def test_stage2_water_is_inside_stage3_water_on_the_surface():
    world = generate_surface(C.WORLD_SEED)
    tiles = [(x, y) for y in range(world.height) for x in range(world.width)]
    stage2 = {t for t in tiles if world.is_water(*t, 2)}
    stage3 = {t for t in tiles if world.is_water(*t, 3)}
    assert stage2 and stage2 <= stage3
