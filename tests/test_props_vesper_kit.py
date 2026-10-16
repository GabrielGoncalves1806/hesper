"""v0.7 M4 Task 5: o kit de props da VÉSPER-7 (tamanhos, lugares, variantes de sprite e plantas)."""

import os

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import vesper  # noqa: E402
from game.props import Prop  # noqa: E402

KIT = {
    "prop_container_stack": ((2, 1), "floor", True), "prop_command_table": ((2, 1), "floor", True),
    "prop_o2_cylinders": ((1, 1), "floor", True), "prop_server_rack": ((1, 1), "floor", True),
    "prop_server_rack_open": ((1, 1), "floor", True), "prop_workstation": ((1, 1), "floor", True),
    "prop_pilot_chair": ((1, 1), "floor", False), "wall_cable_panel": ((1, 1), "face", False),
    "prop_wall_bunk": ((2, 1), "desk", True), "prop_suit_locker": ((1, 1), "floor", True),
    "prop_suit_niche": ((1, 1), "floor", True), "prop_uniforms": ((1, 1), "decal", False),
    "prop_briefing_table": ((2, 2), "floor", True), "prop_mess_table": ((2, 1), "floor", True),
    "prop_repair_bench": ((2, 1), "floor", True), "prop_nav_table": ((1, 1), "floor", True),
    "prop_side_table": ((1, 1), "floor", True),
}


@pytest.mark.parametrize("kind", sorted(KIT))
def test_kit_contract(kind):
    size, place, solid = KIT[kind]
    t = C.PROPS[kind]
    assert (t.size, t.place, t.solid) == (size, place, solid)
    assert t.scannable == (kind != "prop_uniforms")
    assert (kind in C.PLAYER_PROPS) == (kind != "prop_uniforms")


def test_briefing_table_footprint_and_collision():
    p = Prop("prop_briefing_table", 5, 5)
    assert p.tiles == [(5, 5), (6, 5), (5, 6), (6, 6)]
    assert all(p.rect_at(t) is not None for t in p.tiles)


def test_uniforms_variant_is_deterministic_and_uses_both():
    from game.render import Renderer
    from game.assets import Sprites
    pygame.init()
    pygame.display.set_mode((64, 64))
    r = Renderer(Sprites())
    seen = set()
    for x in range(30):
        a = r.prop_surface("prop_uniforms", (x, 3))
        assert a is r.prop_surface("prop_uniforms", (x, 3))
        seen.add(id(a))
    assert len(seen) == 2


def test_ships_use_the_new_props():
    used = set()
    for slot in vesper.SLOTS:
        for key in vesper.VARIANTS[slot.key]:
            used |= set(vesper.load(key).props.values())
    assert {"prop_wall_bunk", "prop_briefing_table", "prop_command_table", "prop_container_stack",
            "prop_repair_bench", "wall_cable_panel", "prop_uniforms"} <= used
