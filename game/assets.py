"""Carregador de assets opcionais: sprites (PNG) e fontes (TTF). O som fica em audio.py.

Regra de ouro (bíblia §5): nada pode quebrar por falta de asset.
`Sprites.get(nome)` devolve a imagem de assets/sprites/<nome>.png, ou None.
Quem chama (render.py) desenha a versão "de retângulos" quando recebe None.
A flag ENABLE_SPRITES em config.py liga e desliga isso.
"""

import pygame

from game import config as C


class Sprites:
    def __init__(self, enabled: bool | None = None):
        self.enabled = C.ENABLE_SPRITES if enabled is None else enabled
        self._cache: dict[str, pygame.Surface | None] = {}

    def get(self, name: str) -> pygame.Surface | None:
        if not self.enabled:
            return None
        if name not in self._cache:
            self._cache[name] = self._load(name)
        return self._cache[name]

    @staticmethod
    def _load(name: str) -> pygame.Surface | None:
        path = C.SPRITES_DIR / f"{name}.png"
        if not path.exists():
            return None
        try:
            image = pygame.image.load(str(path))
            return image.convert_alpha() if pygame.display.get_surface() else image
        except pygame.error as err:
            print(f"[assets] não consegui ler {path.name}: {err}")
            return None


def load_font(filename: str, size: int, fallback_size: int) -> pygame.font.Font:
    """Fonte do mockup (game/fonts/) ou a fonte padrão do pygame se o arquivo sumir."""
    path = C.FONTS_DIR / filename
    if path.exists():
        try:
            return pygame.font.Font(str(path), size)
        except (pygame.error, OSError):
            pass
    return pygame.font.Font(None, fallback_size)
