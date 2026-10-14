"""Transição gradual de estágio: a mancha do próximo estágio se espalhando tile por tile."""

import random

from game import config as C
from game.systems import GameState
from game.transition import BASE_SOURCE, StageMap, front_distance, tile_stage, window_progress
from tests.helpers import build_now

SOURCES = [BASE_SOURCE, (93, 98), (99, 98)]
TILES = [(x, y) for x in range(0, C.SURFACE_W, 5) for y in range(0, C.SURFACE_H, 5)]


def ti_at(stage: int, window_fraction: float) -> float:
    """Ti que fica `window_fraction` dentro da janela de transição do estágio `stage`."""
    start, end = C.STAGES[stage - 1].ti, C.STAGES[stage].ti
    return start + (end - start) * (1 - C.TRANSITION_WINDOW + C.TRANSITION_WINDOW * window_fraction)


def converted(ti: float, sources=SOURCES) -> float:
    """Fração dos tiles de amostra que já estão no estágio seguinte ao oficial."""
    stage = window_progress(ti)[0]
    return sum(tile_stage(x, y, ti, sources) > stage for x, y in TILES) / len(TILES)


def test_window_starts_at_65_percent_of_the_bar():
    assert window_progress(7_000) == (2, 0.0)            # Árido (2.500 -> 10.000): a janela abre em 7.375
    assert window_progress(7_300) == (2, 0.0)
    stage, progress = window_progress(ti_at(2, 0.5))
    assert stage == 2 and abs(progress - 0.5) < 1e-9
    assert window_progress(250_000) == (4, 0.0)          # último estágio: não tem janela


def test_nothing_changes_before_the_window():
    for ti in (0, 3_000, 8_000, 10_000, 50_000, 68_000):   # janelas: 4.225, 8.775 e 68.500
        stage = window_progress(ti)[0]
        assert all(tile_stage(x, y, ti, SOURCES) == stage for x, y in TILES)


def test_everything_is_the_new_stage_at_the_threshold():
    assert all(tile_stage(x, y, C.STAGES[1].ti, SOURCES) == 2 for x, y in TILES)
    assert all(tile_stage(x, y, 10_000, SOURCES) == 3 for x, y in TILES)
    assert all(tile_stage(x, y, 100_000, SOURCES) == 4 for x, y in TILES)


def test_spot_starts_near_the_base_and_reaches_the_edges():
    ti = ti_at(1, 0.25)
    assert tile_stage(*BASE_SOURCE, ti, SOURCES) == 2           # perto da base já virou
    assert tile_stage(2, 2, ti, SOURCES) == 1                   # canto do mapa ainda não
    assert 0 < converted(ti) < 0.1
    assert converted(ti_at(1, 0.99)) > 0.9                      # antes do limiar já quase tudo


def test_machines_are_sources_too():
    far = (100, 100)
    ti = ti_at(1, 0.25)
    assert tile_stage(*far, ti, [BASE_SOURCE]) == 1
    assert tile_stage(*far, ti, [BASE_SOURCE, far]) == 2


def test_is_deterministic():
    ti = ti_at(2, 0.6)
    first = [tile_stage(x, y, ti, SOURCES) for x, y in TILES]
    assert first == [tile_stage(x, y, ti, SOURCES) for x, y in TILES]


def test_is_monotonic_with_ti_and_growing_sources():
    """Ti só sobe e fonte nunca sai: um tile convertido nunca desconverte."""
    rng = random.Random(3)
    sources = [BASE_SOURCE]
    previous = {t: 1 for t in TILES}
    ti = 0.0
    while ti < 120_000:
        ti += rng.uniform(50, 1_500)
        if rng.random() < 0.1:
            sources.append((rng.randrange(C.SURFACE_W), rng.randrange(C.SURFACE_H)))
        for x, y in TILES:
            now = tile_stage(x, y, ti, sources)
            assert now >= previous[(x, y)], (x, y, ti)
            previous[(x, y)] = now


def test_front_grows_and_starts_at_zero():
    values = [front_distance(i / 100) for i in range(101)]
    assert values[0] == 0
    assert all(b > a for a, b in zip(values, values[1:]))


def test_stage_map_matches_pure_function():
    ti = ti_at(1, 0.6)
    m = StageMap()
    m.update(ti, SOURCES)
    for x, y in TILES + [(-3, -3), (130, 5)]:
        assert m.stage_at(x, y) == tile_stage(x, y, ti, SOURCES)


def test_stage_map_only_rebuilds_on_new_step_or_new_source():
    m = StageMap()
    ti = ti_at(1, 0.505)              # meio do degrau 50 (longe da borda do degrau)
    m.update(ti, SOURCES)
    m.stage_at(96, 96)
    assert m._stages
    m.update(ti + 1, SOURCES)                        # mesmo degrau: cache continua
    assert m._stages
    m.update(ti_at(1, 0.52), SOURCES)                # degrau novo: estágios refeitos, distâncias ficam
    assert not m._stages and m._distances
    m.update(ti_at(1, 0.52), SOURCES + [(10, 10)])   # fonte nova: tudo refeito
    assert not m._distances


def test_placed_machines_stay_as_sources_forever():
    game = GameState(rng=random.Random(1))
    game.player.x, game.player.y = C.SPAWN_POS
    assert build_now(game, "o2", (93, 98))
    assert (93, 98) in game.transition_sources
    game.machines.clear()                            # "desmontar" (outro branch): a marca fica
    assert (93, 98) in game.transition_sources
