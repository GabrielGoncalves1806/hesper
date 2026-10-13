"""Ícone do atalho de Mac (tools/dev/make_mac_app.sh): um "H" no estilo do logo da tela de título (Silkscreen, sombra,
traço laranja) sobre a nuvem de poeira borrada do fundo do título, com os grãos de poeira nítidos passando na frente.

O fundo é desenhado pelo próprio jogo (Title.draw_background, janela escondida), então segue igual à tela inicial.
Uso: SDL_VIDEODRIVER=dummy uv run python tools/dev/mac_icon.py <saída.png>
"""
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game.assets import load_font  # noqa: E402
from game.world import hash01  # noqa: E402

S = 1024
MARGIN = 80                     # a forma arredondada do macOS: o ícone ocupa 824×824 no meio
RADIUS = 190


def title_background() -> pygame.Surface:
    """Um quadro do fundo da tela de título (cratera borrada + sombra), no tamanho da tela do jogo."""
    from game.app import App
    app = App()
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    app.title.draw_background(canvas, 40.0)
    return canvas


def main(out: str) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    bg = title_background()
    side = C.SCREEN_H                                   # recorte quadrado do meio do fundo
    crop = bg.subsurface(((C.SCREEN_W - side) // 2, 0, side, side)).copy()
    inner = S - 2 * MARGIN
    crop = pygame.transform.smoothscale(crop, (inner, inner))

    mask = pygame.Surface((inner, inner), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, inner, inner), border_radius=RADIUS)
    tile = pygame.Surface((inner, inner), pygame.SRCALPHA)
    tile.blit(crop, (0, 0))
    tile.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    # grãos de poeira nítidos, como o _draw_dust do título (em pixels grandes, 1 px do jogo = 8 px aqui)
    px = 8
    for i in range(70):
        x = int(hash01(i, 1, 31) * inner)
        y = int(hash01(i, 3, 31) * inner + math.sin(i) * 4)
        alpha = 70 + int(120 * hash01(i, 4, 31))
        w = px * (2 if i % 5 == 0 else 1)
        dot = pygame.Surface((w, px), pygame.SRCALPHA)
        dot.fill((226, 160, 110, alpha))
        tile.blit(dot, (x - x % px, y - y % px))
    tile.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    # o "H" do logo: Silkscreen sem suavizar, ampliado em pixels inteiros, sombra preta e o traço laranja embaixo
    font = load_font("Silkscreen-Regular.ttf", 32, 48)
    letter = font.render("H", False, pygame.Color(C.C_TEXT))
    shadow = font.render("H", False, (0, 0, 0))
    lb = letter.get_bounding_rect()
    letter, shadow = letter.subsurface(lb).copy(), shadow.subsurface(lb).copy()
    k = int(inner * 0.5) // letter.get_height()
    letter = pygame.transform.scale(letter, (letter.get_width() * k, letter.get_height() * k))
    shadow = pygame.transform.scale(shadow, letter.get_size())
    shadow.set_alpha(170)
    lx = (inner - letter.get_width()) // 2
    ly = (inner - letter.get_height()) // 2 - k * 2
    tile.blit(shadow, (lx + 2 * k, ly + 2 * k))
    tile.blit(letter, (lx, ly))
    line_w, line_h = letter.get_width() + 4 * k, 2 * k
    tile.fill(pygame.Color(C.C_ACCENT), ((inner - line_w) // 2, ly + letter.get_height() + 3 * k, line_w, line_h))

    icon = pygame.Surface((S, S), pygame.SRCALPHA)
    icon.blit(tile, (MARGIN, MARGIN))
    pygame.image.save(icon, out)


if __name__ == "__main__":
    main(sys.argv[1])
