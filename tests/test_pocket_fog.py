"""Névoa do bolsão da criatura e mensagem ao abrir (v0.5 Marco 3 · M3.6.4 · game/pocket_fog.py)."""

import os
import random
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from game import config as C  # noqa: E402
from game import ice_blocks, map_view, minimap, pocket_fog, save, settings  # noqa: E402
from game.systems import GameState  # noqa: E402

SEED = 598929664


def game() -> GameState:
    return GameState(SEED, rng=random.Random(1))


def set_heat(g: GameState, heat: float) -> None:
    g.indices["heat"] = heat
    g._apply_thaw()


def open_heat() -> float:
    lo, hi = C.THAW_GIANT_HEAT[0], C.THAW_GIANT_HEAT[-1]
    return lo + (hi - lo) * (ice_blocks.opens_at("G") + 0.02)


def test_fog_active_while_closed_and_gone_after_open():
    g = game()
    layer, geo = g.surface, g.surface.geo
    assert pocket_fog.closed(layer) and layer.world.hidden_tiles >= set(geo.giant.interior)
    fog = pocket_fog.PocketFog()
    assert fog.update(layer, 0.0) == 1.0 and fog.update(layer, 0.5) == 1.0        # fechado: cheia
    set_heat(g, open_heat())
    assert not pocket_fog.closed(layer) and not layer.world.hidden_tiles
    a = fog.update(layer, 0.55)
    assert 0 < a < 1                                                                 # dissipando, não some de uma vez
    t = 0.55
    while a > 0 and t < 10:
        t += 0.05
        a = fog.update(layer, t)
    assert a == 0 and 3.0 <= t <= 4.2                                                # ~C.GIANT_FOG_FADE_S s
    assert pocket_fog.PocketFog().update(layer, 0.0) == 0.0                          # load já aberto: nasce sem névoa


def test_fog_draws_only_over_the_pocket():
    g = game()
    geo = g.surface.geo
    x, y, w, h = geo.giant.outer
    cx, cy = (x + w / 2) * C.TILE, (y + h / 2) * C.TILE
    fog, canvas = pocket_fog.PocketFog(), pygame.Surface((320, 200), pygame.SRCALPHA)
    fog.draw(canvas, geo, (cx - 160, cy - 100), 1.0, 1.0)
    assert canvas.get_at((160, 100)).a > 200                                         # no meio do interior: densa
    far = pygame.Surface((320, 200), pygame.SRCALPHA)
    fog.draw(far, geo, (0, 0), 1.0, 1.0)
    assert far.get_bounding_rect().size == (0, 0)                                    # bolsão fora da tela: nada


def test_map_hides_closed_pocket_and_shows_open_or_f3():
    g = game()
    geo = g.surface.geo
    gp = geo.giant
    inner = gp.interior[len(gp.interior) // 2]
    mm = minimap.Minimap()
    # fechado: o interior é só névoa (mesmo se visto), o gelo gigante e o chão não aparecem
    assert minimap.tile_color(g.surface.world, *inner) == minimap.FOG_COLOR
    assert minimap.tile_color(g.surface.world, *gp.giant.tiles[0]) == minimap.FOG_COLOR
    assert minimap.tile_color(g.surface.world, *inner, reveal=True) != minimap.FOG_COLOR     # F3 mostra tudo
    tex = mm.texture(g, "surface")
    g.fast = True
    assert tuple(mm.texture(g, "surface").get_at(inner))[:3] != minimap.FOG_COLOR
    g.fast = False
    del tex
    _seen_all(g)
    kinds = [(e.kind, e.title) for e in map_view.map_entries(g, "surface")]
    assert ("unknown", "Desconhecido") in kinds
    assert not any(n == gp.giant.name for _, n in kinds)                             # sem marcador do gelo gigante
    assert ("formation", "Grande gelo") in kinds                                      # o do portão continua
    g.fast = True
    kinds = [e.kind for e in map_view.map_entries(g, "surface")]
    assert "unknown" not in kinds                                                    # F3: nada de "?"
    g.fast = False
    set_heat(g, open_heat())                                                         # aberto: o interior e o gelo aparecem
    assert minimap.tile_color(g.surface.world, *inner) != minimap.FOG_COLOR
    entries = map_view.map_entries(g, "surface")
    assert not any(e.kind == "unknown" for e in entries) and any(e.title == gp.giant.name for e in entries)


def _seen_all(g: GameState) -> None:
    ex = g.surface.explored
    gp = g.surface.geo.giant
    for t in (*gp.interior, *gp.giant.tiles, *gp.entry):
        ex.bits[t[1] * g.surface.world.width + t[0]] = 1


@pytest.fixture(scope="module")
def app():
    settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_test_pocket_fog_settings.json"
    from game.app import App
    a = App(scale=1, skip_title=True)
    yield a
    pygame.quit()


def test_message_once_on_open_and_never_on_load(app):
    g = game()
    app.state = g
    app.thaw_notice, app.thaw_notice_time = None, 0.0
    set_heat(g, C.THAW_GIANT_HEAT[0] + 100)                                          # derretendo: ainda sem mensagem
    for ev in g.events:
        if ev[0] == "giant_gate_thaw":
            app.on_game_event(ev)
    g.events.clear()
    assert app.thaw_notice is None
    set_heat(g, open_heat())
    opened = [e for e in g.events if e == ("giant_gate_thaw", 3)]
    for ev in opened:
        app.on_game_event(ev)
    assert len(opened) == 1 and app.thaw_notice == C.GIANT_OPEN_NOTICE and app.thaw_notice_time > 0
    app.thaw_notice, app.thaw_notice_time = None, 0.0
    g.events.clear()
    set_heat(g, open_heat() + 500)                                                   # mais calor: não repete
    assert not g.events
    path = Path(tempfile.gettempdir()) / "hesper_test_pocket_fog.json"
    assert save.write_save(g, path)
    _, loaded = save.probe(path)                                                     # load já aberto: sem névoa, sem aviso
    assert loaded is not None and not loaded.events and not pocket_fog.closed(loaded.surface)
    assert app.thaw_notice is None
