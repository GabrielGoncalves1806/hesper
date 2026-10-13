"""v0.4 Marco 3 · M3.5: margem orgânica do lago (game/lake.py, bíblia §12 "Chuva e lagos").

Só desenho: a água continua por tile no jogo (`World.is_water`). A regra do desenho é o campo do geo.height
interpolado entre os centros dos tiles; no centro de cada tile ele vale o height do tile, então o pixel do centro é
água exatamente onde `is_water` diz que o tile é água."""

import os

import numpy as np
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import lake  # noqa: E402
from game.surface_gen import generate_surface  # noqa: E402

T = C.TILE
WET = {lake.SHADE1, lake.SHADE2, lake.FOAM1, lake.FOAM2, lake.WATER}
_WORLD = {}


def surface():
    if "w" not in _WORLD:
        _WORLD["w"] = generate_surface(C.WORLD_SEED)
    return _WORLD["w"]


def basin_blocks(world) -> list[tuple[int, int]]:
    b = np.asarray(world.geo.basin) >= 0
    out = set()
    for ty, tx in zip(*np.nonzero(b)):
        out.add((int(tx) // lake.BT, int(ty) // lake.BT))
    return sorted(out)


@pytest.mark.parametrize("k", range(3))
def test_tile_centre_matches_is_water(k):
    world = surface()
    world.water_level = C.GEO_LEVELS[k]
    blocks = lake.LakeBlocks()
    checked = wet = 0
    for bx, by in basin_blocks(world):
        code = blocks.bake(world, bx, by)["code"]
        for ly in range(lake.BT):
            for lx in range(lake.BT):
                tx, ty = bx * lake.BT + lx, by * lake.BT + ly
                if tx >= world.width or ty >= world.height:
                    continue
                centre = code is not None and code[ly * T + T // 2, lx * T + T // 2] in WET
                assert centre == world.is_water(tx, ty, C.MIST_STAGE), (tx, ty, k)
                checked += 1
                wet += centre
    assert wet > 0 and checked > wet
    world.water_level = -1.0


def test_block_without_basin_has_nothing():
    world = surface()
    world.water_level = C.GEO_LEVELS[2]
    bx, by = C.BASE_TILE[0] // lake.BT, C.BASE_TILE[1] // lake.BT     # a base nunca alaga
    assert lake.LakeBlocks().bake(world, bx, by)["code"] is None
    world.water_level = -1.0


def test_shore_is_curved_not_staircase():
    """Na margem, a linha d'água não fica presa na grade: tem pixels de borda fora das linhas/colunas de tile."""
    world = surface()
    world.water_level = C.GEO_LEVELS[1]
    blocks = lake.LakeBlocks()
    offsets = set()
    for bx, by in basin_blocks(world)[:40]:
        code = blocks.bake(world, bx, by)["code"]
        if code is None:
            continue
        water = np.isin(code, list(WET))
        edge_x = np.nonzero(water[:, 1:] != water[:, :-1])[1] + 1
        offsets.update((edge_x % T).tolist())
    assert len(offsets) > T // 2, offsets
    world.water_level = -1.0


def test_shore_bands_inside_and_bank_outside():
    water = np.zeros((40, 40), bool)
    water[10:30, 10:30] = True
    code = lake.shore_codes(water)
    assert code[20, 20] == lake.WATER
    assert code[10, 20] == lake.SHADE1 and code[11, 20] == lake.SHADE2     # margem de cima: sombra
    assert code[29, 20] == lake.FOAM1 and code[28, 20] == lake.FOAM2       # margem de baixo: espuma
    assert code[9, 20] == lake.BANK and code[8, 20] == lake.BANK and code[7, 20] == lake.OUTER
    assert code[0, 0] == lake.NONE


def test_reflexes_stay_in_deep_water():
    world = surface()
    world.water_level = C.GEO_LEVELS[1]
    blocks = lake.LakeBlocks()
    for bx, by in basin_blocks(world)[:30]:
        entry = blocks.bake(world, bx, by)
        for left, row, a, b, h, which in entry["spans"].astype(int).tolist():
            ly = row - by * lake.BP
            assert (entry["code"][ly, a - bx * lake.BP:b - bx * lake.BP] == lake.WATER).all()
    world.water_level = -1.0


def test_rebakes_only_when_level_or_tiles_change():
    world = surface()
    world.water_level = C.GEO_LEVELS[0]
    blocks = lake.LakeBlocks()
    bx, by = basin_blocks(world)[0]
    blocks.bake(world, bx, by)
    assert blocks.current(world, bx, by) is not None
    world.water_level = C.GEO_LEVELS[0] + C.LAKE_STEP
    assert blocks.current(world, bx, by) is None
    blocks.bake(world, bx, by)
    tx, ty = bx * lake.BT + 2, by * lake.BT + 2
    old = world.tiles[ty][tx]
    world.tiles[ty][tx] = C.ROCK if old != C.ROCK else C.SAND
    assert blocks.current(world, bx, by) is None
    world.tiles[ty][tx] = old
    world.water_level = -1.0
