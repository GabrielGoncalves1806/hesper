"""Tamanho da interface (Opções > Interface: Grande/Média/Pequena).

Contas de tela (game/viewport.py: ui_layout, window_to_ui), persistência no settings.json e
ancoragem dos painéis (game/ui.py) no espaço lógico de cada tamanho.
"""

import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C  # noqa: E402
from game import settings  # noqa: E402
from game import viewport as V  # noqa: E402

SIZES = ("grande", "media", "pequena")


# ---- escala e espaço lógico ------------------------------------------------------------------
@pytest.mark.parametrize("ui_size, k, size", [("grande", 4.0, (480, 270)), ("media", 3.0, (640, 360)),
                                              ("pequena", 2.0, (960, 540))])
def test_layout_1080p(ui_size, k, size):
    rect, scale, logical = V.ui_layout((1920, 1080), ui_size)
    assert rect == (0, 0, 1920, 1080)
    assert scale == k and logical == size
    assert logical[0] * scale == 1920 and logical[1] * scale == 1080       # escala inteira, sem sobra


@pytest.mark.parametrize("ui_size", SIZES)
def test_small_window_never_below_one_pixel_per_pixel(ui_size):
    """960×540: Grande já é k 2 (o mínimo). Média e Pequena dariam 1,5 e 1: caem pra 2."""
    rect, k, size = V.ui_layout((960, 540), ui_size)
    assert (k, size) == (2.0, (480, 270))


def test_layout_letterbox_4_3():
    """Monitor 4:3 de 1024×768: área de jogo 1024×576 com tarja em cima e embaixo."""
    rect, k, size = V.ui_layout((1024, 768), "grande")
    assert rect == (0, 96, 1024, 576) and size == (480, 270) and k == pytest.approx(1024 / 480)
    for ui_size in ("media", "pequena"):         # 1,6 e 1,07 viram 2 (piso): 512×288
        rect, k, size = V.ui_layout((1024, 768), ui_size)
        assert k == 2.0 and size == (512, 288)


def test_layout_never_smaller_than_480x270():
    """Janela qualquer (2560×1440, 1366×768, 1512×982): o espaço lógico nunca encolhe abaixo do Grande
    e a UI escalada nunca passa da área de jogo."""
    for window in ((2560, 1440), (1366, 768), (1512, 982), (800, 450), (3840, 2160)):
        for ui_size in SIZES:
            (x, y, w, h), k, (uw, uh) = V.ui_layout(window, ui_size)
            assert uw >= 480 and uh >= 270, (window, ui_size)
            assert uw * k <= w + 1 and uh * k <= h + 1, (window, ui_size)   # +1: arredondamento do letterbox
            if ui_size != "grande" and w >= 960:
                assert k == int(k) and k >= 2, (window, ui_size, k)


def test_sizes_shrink_in_order_on_big_screens():
    for window in ((1920, 1080), (2560, 1440), (3840, 2160)):
        ks = [V.ui_layout(window, s)[1] for s in SIZES]
        assert ks[0] > ks[1] > ks[2], (window, ks)
    # 4K: Média ~75% (6 de 8) e Pequena 50% (4 de 8)
    assert [V.ui_layout((3840, 2160), s)[1] for s in SIZES] == [8.0, 6.0, 4.0]


# ---- mouse: janela -> px da UI -----------------------------------------------------------------
def test_window_to_ui_960x540():
    for ui_size in SIZES:
        assert V.window_to_ui((0, 0), (960, 540), ui_size) == (0, 0)
        assert V.window_to_ui((480, 270), (960, 540), ui_size) == (240, 135)


@pytest.mark.parametrize("ui_size, k", [("grande", 4), ("media", 3), ("pequena", 2)])
def test_window_to_ui_1080p(ui_size, k):
    # o centro de um botão em (100, 50) px da UI aparece em (100k + k/2, 50k + k/2) na janela
    ux, uy = V.window_to_ui((100 * k + k / 2, 50 * k + k / 2), (1920, 1080), ui_size)
    assert (int(ux), int(uy)) == (100, 50)
    # canto de baixo à direita da tela = canto de baixo à direita do espaço lógico
    _, _, (uw, uh) = V.ui_layout((1920, 1080), ui_size)
    ux, uy = V.window_to_ui((1919, 1079), (1920, 1080), ui_size)
    assert (int(ux), int(uy)) == (uw - 1, uh - 1)


def test_window_to_ui_letterbox_clamps_on_bars():
    # 1024×768: tarja de 96 px em cima. Clique na tarja gruda na borda de cima da UI.
    assert V.window_to_ui((10, 5), (1024, 768), "pequena")[1] == 0
    ux, uy = V.window_to_ui((1024 // 2, 96 + 576 // 2), (1024, 768), "pequena")
    assert (ux, uy) == (256, 144)                # centro da área de jogo = centro do 512×288
    ux, uy = V.window_to_ui((512, 96 + 576 // 2), (1024, 768), "grande")
    assert (ux, uy) == pytest.approx((240, 135))


def test_ui_and_canvas_agree_on_the_same_point():
    """Um ponto da janela visto como canvas (mundo) e como UI cai no mesmo lugar, via canvas_to_ui_factor
    (é o que prende os floaters e o rótulo do baú no mundo)."""
    for window in ((960, 540), (1920, 1080), (1024, 768)):
        for ui_size in SIZES:
            f = V.canvas_to_ui_factor(window, ui_size)
            pos = (window[0] * 0.3, window[1] * 0.6)
            cx, cy = V.window_to_canvas(pos, window)
            ux, uy = V.window_to_ui(pos, window, ui_size)
            assert cx * f == pytest.approx(ux, abs=1.5) and cy * f == pytest.approx(uy, abs=1.5)


# ---- persistência ------------------------------------------------------------------------------
def test_ui_size_persists(tmp_path):
    path = tmp_path / "settings.json"
    for ui_size in SIZES:
        settings.save({**settings.DEFAULTS, "ui_size": ui_size}, path)
        assert settings.load(path)["ui_size"] == ui_size


def test_ui_size_default_and_invalid(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"master": 0.5}', encoding="utf-8")            # arquivo antigo, sem o campo
    assert settings.load(path)["ui_size"] == settings.DEFAULTS["ui_size"] == "media"
    path.write_text('{"ui_size": "gigante"}', encoding="utf-8")
    assert settings.load(path)["ui_size"] == "media"


# ---- ancoragem e desenho -----------------------------------------------------------------------
@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    from game.ui import UI
    return UI()


def _hud(ui, size):
    from game.systems import GameState
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    icons = {r: art.icon(r) for r in C.RESOURCES}
    state = GameState(rng=random.Random(1))
    ui.draw_hud(state, 0.0, "Uma dica qualquer", icons)
    ui.draw_hotbar(state.inventory, 0, lambda item: art.icon(item) if item in C.RESOURCES else icons["iron"])
    return state


@pytest.mark.parametrize("size", [(480, 270), (640, 360), (960, 540)])
def test_right_panel_touches_right_edge(ui, size):
    """O painel do Ti (canto de cima à direita) e a dica (embaixo à direita) encostam na borda direita
    do espaço lógico (6 px de margem), e a hotbar fica no centro de baixo."""
    from game.ui import GRID_W, SLOT, TI_PANEL_W
    _hud(ui, size)
    w, h = size
    assert ui.surf.get_size() == size
    assert ui.ti_panel_x + TI_PANEL_W == w - 6
    assert ui.surf.get_at((w - 7, 10)).a > 0             # borda do painel do Ti
    assert ui.surf.get_at((w - 3, 10)).a == 0            # margem
    assert ui.surf.get_at((w - 7, h - 10)).a > 0         # painel da dica, embaixo à direita
    assert ui.hotbar_x == (w - GRID_W) // 2 and ui.hotbar_y == h - 6 - SLOT
    assert ui.surf.get_at((w // 2, h - 8)).a > 0         # hotbar no centro de baixo


@pytest.mark.parametrize("size", [(480, 270), (640, 360), (960, 540)])
def test_menus_centered(ui, size):
    """Pausa (e as Opções, com a linha da Interface) e fabricador ficam no meio da tela em qualquer tamanho."""
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    ui.draw_pause("volumes", 0, {**settings.DEFAULTS}, "1×", "MÉDIA")
    rows = ui.pause_items
    assert len(rows) == len(ui.VOLUME_ROWS) + len(ui.OPTION_ROWS) + 1
    left, right = rows[0].left, rows[0].right
    assert abs((left + right) / 2 - size[0] / 2) <= 1
    assert rows[0].top > 0 and rows[-1].bottom < size[1]


@pytest.mark.parametrize("size", [(480, 270), (640, 360), (960, 540)])
def test_inventory_notice_clear_of_hotbar_and_help(ui, size):
    """Aviso temporário com o inventário aberto: não cobre a hotbar (moldura em hotbar_y - 11) nem a
    linha de ajuda, nem com um painel alto (ex.: a logística deixando o baú maior)."""
    from game.inventory import Inventory
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    ui.begin()
    ui.draw_inventory(Inventory(16), None, 0, lambda item: art.icon("iron"), (0, 0))
    hotbar_top = ui.hotbar_y - 11
    assert ui.notice_y + ui.NOTICE_H < hotbar_top
    for panel_h in (150, 180, 200):                      # painel cada vez mais alto (200: o máximo que cabe no Grande)
        top = (size[1] - panel_h) // 2 - 16
        help_y = top + panel_h + 6
        y = ui.panel_notice_y(top, help_y + 12)
        assert y + ui.NOTICE_H < hotbar_top, (size, panel_h, y)
        assert y + ui.NOTICE_H <= top or y >= help_y + 10, (size, panel_h, y)   # nem no painel/ajuda


def test_finish_blends_like_before(ui):
    """Painel semitransparente: a cor final na janela é a mesma em qualquer escala (sem camada alfa
    intermediária escurecendo ou clareando)."""
    colors = []
    for k, size in ((2, (480, 270)), (3, (640, 360)), (4, (480, 270))):
        ui.set_layout((0, 0, size[0] * k, size[1] * k), float(k), size)
        ui.begin()
        ui.panel(20, 20, 40, 30)
        target = pygame.Surface((size[0] * k, size[1] * k))
        target.fill((90, 120, 60))
        ui.finish(target)
        colors.append(tuple(target.get_at((30 * k, 30 * k))))
    # o jeito antigo: a camada esticada 2× colada em cima do mundo
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    ui.begin()
    ui.panel(20, 20, 40, 30)
    old = pygame.Surface((960, 540))
    old.fill((90, 120, 60))
    old.blit(pygame.transform.scale(ui.surf, (960, 540)), (0, 0))
    assert colors == [tuple(old.get_at((60, 60)))] * 3


def test_finish_scales_native_icons(ui):
    """Ícone da camada native (32×32 = 16 px da UI) ocupa 16·k px na janela, no lugar certo."""
    icon = pygame.Surface((32, 32))
    icon.fill((255, 0, 0))
    for k in (2, 3, 4):
        size = (480, 270)
        ui.set_layout((0, 0, size[0] * k, size[1] * k), float(k), size)
        ui.begin()
        ui.native.append((icon, (20, 40)))            # = (10, 20) px da UI
        target = pygame.Surface((size[0] * k, size[1] * k))
        ui.finish(target)
        x0, y0 = 10 * k, 20 * k
        assert tuple(target.get_at((x0, y0)))[:3] == (255, 0, 0)
        assert tuple(target.get_at((x0 + 16 * k - 1, y0 + 16 * k - 1)))[:3] == (255, 0, 0)
        assert tuple(target.get_at((x0 + 16 * k, y0)))[:3] == (0, 0, 0)
