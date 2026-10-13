"""Texto do HUD/UI: "O₂" com subscrito desenhado, tooltip dos slots sem cobrir cabeçalho e floaters que
somem antes de entrar embaixo dos painéis do HUD."""

import os
import random
import re

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game import art  # noqa: E402
from game import config as C  # noqa: E402
from game.floaters import FloatingTexts, hud_fade  # noqa: E402
from game.objectives import OBJECTIVES  # noqa: E402

SIZES = [(480, 270), (640, 360), (960, 540)]


@pytest.fixture(scope="module")
def ui():
    pygame.font.init()
    from game.ui import UI
    return UI()


def _pixels(surf: pygame.Surface) -> list[str]:
    """Linhas de '#'/'.' (pixel aceso ou não), com fundo preto embaixo (a fonte pode vir sem alfa)."""
    bg = pygame.Surface(surf.get_size())
    bg.fill((0, 0, 0))
    bg.blit(surf, (0, 0))
    return ["".join("#" if bg.get_at((x, y)).r > 128 else "." for x in range(bg.get_width()))
            for y in range(bg.get_height())]


# ---- O₂ ----------------------------------------------------------------------------------------
def test_no_display_text_says_O2_with_a_letter_that_reads_as_zero():
    """Nas duas fontes o "O" é igual ao "0": todo texto do jogo escreve "O₂" (subscrito desenhado)."""
    texts = [*C.INDEX_LABEL.values(), *C.BLUEPRINTS.values(), *C.LOGS, *C.LOG_TITLES,
             *(o.text for o in OBJECTIVES)]
    for m in C.MACHINES.values():
        texts += [m.name, m.desc]
    bad = [t for t in texts if re.search(r"(?<![A-Za-z])O2", t)]
    assert not bad, bad


@pytest.mark.parametrize("which", ["font", "body"])
def test_subscript_two_is_drawn_small_and_lowered(ui, which):
    """"O₂" sai diferente de "02", o 2 pequeno passa da linha de base e a medida bate com a imagem."""
    font = getattr(ui, which)
    o2 = font.render("O₂", False, (255, 255, 255))
    assert font.size("O₂")[0] == o2.get_width()
    assert _pixels(o2) != _pixels(font.render("O2", False, (255, 255, 255)))
    rows_o = [y for y, row in enumerate(_pixels(font.render("O", False, (255, 255, 255)))) if "#" in row]
    sub = [row[font.size("O")[0]:] for row in _pixels(o2)]
    rows_sub = [y for y, row in enumerate(sub) if "#" in row]
    assert rows_sub[0] > rows_o[0] and rows_sub[-1] > rows_o[-1], "o 2 começa mais baixo e passa da base"
    assert len(rows_sub) < len(rows_o) or which == "font", "na Pixelify o 2 é menor que a letra"


def test_subscript_is_not_treated_as_a_digit(ui):
    """"₂".isdigit() é True no Python: não pode cair nos dígitos desenhados (DIGITS não tem ele)."""
    assert ui.body.size("+O₂")[0] == ui.body.render("+O₂", False, (255, 255, 255)).get_width()
    assert ui.body.size("Ti 500")[0] == ui.body.render("Ti 500", False, (255, 255, 255)).get_width()


# ---- tooltip ------------------------------------------------------------------------------------
def _panels(ui, size):
    """Abre cada painel com slots (Tab, baú, caixa, drill) no tamanho `size` e devolve o nome de cada um."""
    from game.inventory import Inventory
    from game.systems import GameState, Machine
    ui.set_layout((0, 0, size[0] * 2, size[1] * 2), 2.0, size)
    s = GameState(rng=random.Random(1))
    s.inventory.add("iron", 30)
    icon = lambda item: art.icon("iron")   # noqa: E731
    chest = Machine("chest", 0, 0)
    chest.storage.add("ice", 5)
    drill = Machine("drill", 0, 0, resource="iron")
    crate = next(iter(s.crates.values())) if isinstance(s.crates, dict) else s.crates[0]
    for name, side, kw in [("tab", None, dict(equipment=s.equipment, state=s)), ("bau", chest, {}),
                           ("caixa", crate, {}), ("drill", drill, {})]:
        ui.begin()
        ui.draw_inventory(Inventory(16) if side else s.inventory, side, 0, icon, (0, 0), **kw)
        yield name


@pytest.mark.parametrize("size", SIZES)
def test_tooltip_never_covers_a_title_or_header(ui, size):
    """Tooltip de qualquer slot/botão dos painéis: dentro da tela e fora do título da janela, das abas e dos
    rótulos de seção. (Antes ele ia em cima do slot e, na 1ª linha do baú, tapava o nome do baú.)"""
    label_w = ui.body.size("Recebe silício: drones trazem pra cá")[0] + 12   # o mais comprido
    for name in _panels(ui, size):
        assert ui.header_rects, name
        anchors = [r for r, _, _ in ui.slot_rects] + [r for r, _ in ui.logistics_buttons] + \
                  [r for r, _ in ui.equip_rects]
        for r in anchors:
            for w in (60, label_w):
                tip = ui.tooltip_rect(w, r.center)
                assert pygame.Rect(0, 0, *size).contains(tip), (size, name, r, tip)
                assert tip.collidelist(ui.header_rects) < 0, (size, name, r, tip)
                assert not tip.collidepoint(r.center), (size, name, "cobre o próprio slot")


def test_tooltip_of_first_chest_row_stays_off_the_chest_name(ui):
    """O caso do bug: 1ª linha do baú, tooltip fora da faixa do título (onde fica o nome do baú)."""
    for name in _panels(ui, (480, 270)):
        if name == "bau":
            break
    first = min((r for r, inv, _ in ui.slot_rects if len(inv) == 24), key=lambda r: (r.y, r.x))
    title = next(h for h in ui.header_rects if h.bottom <= first.top and h.x < first.x < h.right)
    assert not ui.tooltip_rect(80, first.center).colliderect(title)


# ---- floaters x HUD -----------------------------------------------------------------------------
def test_hud_fade_goes_to_zero_before_touching_a_panel():
    panel = [(6, 6, 118, 32)]
    assert hud_fade((40, 100, 80, 111), panel) == 1.0              # longe
    assert 0 < hud_fade((40, 36, 80, 47), panel) < 1               # chegando (4 px embaixo)
    assert hud_fade((40, 32, 80, 43), panel) == 0.0                # encostou
    assert hud_fade((40, 20, 80, 31), panel) == 0.0                # embaixo do painel
    assert hud_fade((200, 20, 240, 31), panel) == 1.0              # mesma altura, longe do lado


def test_floater_under_a_hud_panel_is_not_drawn(ui):
    """Floater em cima do painel de O₂ não desenha nada (sumiu antes); longe dele, desenha."""
    from game.systems import GameState
    ui.set_layout((0, 0, 960, 540), 2.0, (480, 270))
    s = GameState(rng=random.Random(1))
    icons = {r: art.icon(r) for r in C.RESOURCES}

    def draw(x, y):
        ui.begin()
        ui.draw_hud(s, 0.0, None, icons)
        before = ui.surf.copy()
        floaters = FloatingTexts()
        k = ui.canvas_k                                            # px da UI por px do mundo (zoom 1)
        floaters.add("+12 FERRO", x / k, y / k, "#ffffff")
        ui.draw_floaters(floaters, (0, 0), 1.0)
        return pygame.image.tobytes(before, "RGBA") != pygame.image.tobytes(ui.surf, "RGBA")

    assert not draw(60, 14), "floater passou por baixo/por cima do painel de O₂"
    assert pygame.Rect(6, 6, 132, 17) in ui.hud_rects                # a pílula do O₂ (redesign B2)
    assert draw(240, 150), "floater no meio da tela tem que aparecer"
