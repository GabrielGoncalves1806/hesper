"""v0.8 M4 Task 2: as 3 amostras (itens de loot, logística, ícones, rótulo e seção DRONES do baú)."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game import ui as ui_mod  # noqa: E402
from game.systems import Machine  # noqa: E402
from tests.test_base_app import app, fresh  # noqa: E402,F401  (fixtures)


def test_samples_are_logistic_items():
    for item in C.SAMPLE_ITEMS:
        assert item in C.MACHINES and not C.MACHINES[item].placeable
        assert item in C.LOGISTIC_ITEMS
        assert C.RESOURCE_NAME[item] and C.RESOURCE_LABEL[item]


def test_chest_label_has_an_icon_for_every_logistic_item(fresh):
    """O crash do 03e1cbe0: faltava ícone no rótulo do baú e dava KeyError."""
    icons = fresh.chest_label_icons()
    assert set(C.LOGISTIC_ITEMS) <= set(icons)
    assert all(icons[i].get_size() == (16, 16) for i in C.SAMPLE_ITEMS)


def test_chest_label_draws_with_every_item_configured(fresh):
    chest = Machine("chest", 70, 70)
    chest.sends = set(C.LOGISTIC_ITEMS)
    chest.receives = set(C.LOGISTIC_ITEMS)
    ui = fresh.ui
    ui.begin()
    ui.draw_chest_labels([chest], (0, 0), 1.0, fresh.chest_label_icons())    # não pode dar KeyError


def test_sample_icons_are_the_approved_pngs(fresh):
    import pygame
    r = fresh.renderer
    for item in C.SAMPLE_ITEMS:
        png = pygame.image.load(os.path.join(os.path.dirname(C.__file__), "..", "assets", "sprites", f"icon_{item}.png"))
        assert png.get_size() == (16, 16)
        want = pygame.transform.scale_by(png.convert_alpha(), 2)
        got = r.item_icon(item)
        assert got.get_size() == (32, 32)
        assert pygame.image.tobytes(got, "RGBA") == pygame.image.tobytes(want, "RGBA")   # o PNG aprovado, não o sprite encolhido
        assert r._m4_icon(item).get_size() == (16, 16)


def test_drones_section_fits_with_all_sixteen_items(fresh):
    chest = Machine("chest", 70, 70)
    n = len(C.LOGISTIC_ITEMS)
    assert n == 16
    ui = fresh.ui
    ui.begin()
    ui.logistics_buttons.clear()
    ui.draw_logistics(0, 0, ui_mod.GRID_W, chest, fresh.renderer.item_icon, (0, 0))
    rects = [r for r, (kind, *_x) in ui.logistics_buttons if kind in ("send", "recv")]
    assert len(rects) == 2 * n and all(r.right <= ui_mod.GRID_W for r in rects)
    assert ui.logistics_height(chest) >= 14 + 2 * ui_mod.wide_row_height(n)


def test_sample_names_fit_the_drones_title_and_chest_label(fresh):
    chest = Machine("chest", 70, 70)
    chest.sends = set(C.SAMPLE_ITEMS)
    chest.receives = set(C.LOGISTIC_ITEMS)
    ui = fresh.ui
    ui.begin()
    full = ui.logistics_summary(chest)
    assert "amostra com mutação" in full and "amostra rara" in full
    # o título cai pros nomes curtos / contagem quando não cabe: o que for desenhado tem de caber na grade
    ui.header_rects.clear()
    ui.draw_logistics(0, 0, ui_mod.GRID_W, chest, fresh.renderer.item_icon, (0, 0))
    assert ui.header_rects and all(r.right <= ui_mod.GRID_W for r in ui.header_rects)
    # o rótulo do baú usa só ícones pras amostras: largura fixa de 8 por ícone, e o nome do baú não muda
    parts = ui.chest_label_parts(chest)
    assert [v for k, v in parts if k == "icon"].count("sample_rare") == 2


def test_samples_have_a_drone_pellet_color():
    """Sem cor em ORE_COLORS o drone carregando a amostra (render.py, pepita) e o aviso flutuante dão KeyError."""
    for item in C.SAMPLE_ITEMS:
        assert len(C.ORE_COLORS[item]) == 2


def test_samples_stack_like_loot():
    from game.inventory import max_stack
    assert all(max_stack(i) == C.STACK_LOOT for i in C.SAMPLE_ITEMS)
