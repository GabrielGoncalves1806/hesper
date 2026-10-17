"""v0.8 M4 Task 6: desenho do Microscópio e da Centrífuga (animação só trabalhando, ritmo, luz, ícones)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game.inventory import Stack  # noqa: E402
from game.render import Renderer, anim_frame_index, cave_lights, tile_phase  # noqa: E402
from tests.test_base import game  # noqa: E402,F401  (fixture)
from tests.test_base_app import app, fresh  # noqa: E402,F401  (fixtures)
from tests.test_centrifuge_v08 import make_centrifuge  # noqa: E402
from tests.test_microscope_v08 import make_microscope  # noqa: E402
from tests.test_water_v08 import tick  # noqa: E402


def _renderer(t=3.1):
    r = Renderer.__new__(Renderer)
    r.machine_t = t
    return r


def test_microscope_animates_only_while_analyzing(game):
    m = make_microscope(game, ice=0)
    r = _renderer()
    tick(game, 0.1)
    assert r.machine_anim_index(m, True, 0.0) is None                  # sem gelo: parado
    m.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 2)
    tick(game, 0.1)
    assert m.analyzing
    assert r.machine_anim_index(m, True, 0.0) == anim_frame_index(3.1, tile_phase(m.tx, m.ty))
    assert r.machine_anim_index(m, False, 0.0) is None                 # sem energia
    m.submerged = True
    assert r.machine_anim_index(m, True, 0.0) is None                  # submersa


def test_centrifuge_animates_only_while_spinning_at_10_fps(game):
    m = make_centrifuge(game, algae=0)
    tick(game, 0.1)
    r = _renderer(0.0)
    assert r.machine_anim_index(m, True, 0.0) is None
    m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 2)
    tick(game, 0.1)
    assert m.spinning
    ph = tile_phase(m.tx, m.ty)
    r.machine_t = 0.0
    a = r.machine_anim_index(m, True, 0.0)
    r.machine_t = 0.1
    b = r.machine_anim_index(m, True, 0.0)
    assert (b - a) % 4 == 1                                            # 0,1 s a 10 fps: anda 1 quadro
    assert b == anim_frame_index(0.1, ph, fps=C.CENTRIFUGE_FPS)
    assert anim_frame_index(0.1, ph) == anim_frame_index(0.0, ph)      # a 5 fps não andaria
    assert r.machine_anim_index(m, False, 0.0) is None
    m.submerged = True
    assert r.machine_anim_index(m, True, 0.0) is None


def test_lab_machines_light_only_while_working(game):
    base = len(cave_lights(game))
    mic = make_microscope(game, ice=0)
    cen = make_centrifuge(game, algae=0)
    assert len(cave_lights(game)) == base
    mic.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 1)
    assert len(cave_lights(game)) == base + 1
    cen.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 1)
    assert len(cave_lights(game)) == base + 2


def test_lab_machine_lights_have_their_colors():
    from game.render import MACHINE_LIGHT
    assert MACHINE_LIGHT["microscope"] == (170, 210, 255)
    assert MACHINE_LIGHT["centrifuge"] == (190, 255, 160)


def test_lab_machine_icons_and_previews(fresh):
    for kind in (C.MICROSCOPE, C.CENTRIFUGE):
        assert fresh.renderer.item_icon(kind).get_size() == (32, 32)
        assert fresh.renderer.machine_preview(kind).get_width() > 0
        assert f"icon_{kind}" in fresh.renderer._surfaces               # o PNG do ícone, não o sprite encolhido
