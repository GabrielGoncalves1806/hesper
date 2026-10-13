"""Formato das superfícies opacas (sem canal alfa).

`pygame.Surface(size)` sem flag nem profundidade herda o formato da janela. No driver dummy (smoke e
testes) é XRGB, sem alfa; na janela de verdade do macOS (Cocoa) é ARGB. Numa superfície ARGB sem
SRCALPHA, blitar um sprite com alfa por pixel grava alfa 0 no destino, e uma subsuperfície dela já nasce
com SRCALPHA. Quando isso chega na janela, o macOS mostra preto (o mapa aberto) ou quadrados em volta dos
sprites (playtest 1). Os testes não pegam porque no dummy o formato é outro.

Regra: superfície sem transparência usa `opaque()`, com transparência usa `pygame.SRCALPHA`. Nunca o
formato padrão. Quem confere na janela de verdade é o tools/dev/real_video_check.py.
"""

import pygame

# XRGB8888: o mesmo formato da tela interna (App.canvas). Blit entre os dois é cópia direta, sem conversão.
OPAQUE_MASKS = (0xFF0000, 0x00FF00, 0x0000FF, 0)


def opaque(size: tuple[int, int]) -> pygame.Surface:
    """Superfície opaca de 32 bits sem canal alfa, igual em qualquer driver de vídeo."""
    return pygame.Surface(size, 0, 32, OPAQUE_MASKS)
