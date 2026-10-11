"""Carregador de assets opcionais: sprites (PNG), sons (WAV) e fontes (TTF).

Regra de ouro (bíblia §5): nada pode quebrar por falta de asset.
- `Sprites.get(nome)` devolve a imagem de assets/sprites/<nome>.png, ou None.
  Quem chama (render.py) desenha a versão "de retângulos" quando recebe None.
- `Audio.play(nome)` toca assets/audio/<nome>.wav, ou não faz nada.
As flags ENABLE_SPRITES / ENABLE_AUDIO em config.py ligam e desligam isso.
"""

import pygame

from game import config as C


class Sprites:
    def __init__(self, enabled: bool = C.ENABLE_SPRITES):
        self.enabled = enabled
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


class Audio:
    """Sons de efeito e loops. Se não tiver placa de som ou arquivo, fica em silêncio."""

    def __init__(self, enabled: bool = C.ENABLE_AUDIO):
        self.ok = False
        self._sounds: dict[str, pygame.mixer.Sound | None] = {}
        self._loops: dict[str, pygame.mixer.Channel] = {}
        if not enabled:
            return
        try:
            pygame.mixer.init(44100, -16, 1, 512)
            pygame.mixer.set_num_channels(24)
            self.ok = True
        except pygame.error as err:
            print(f"[audio] sem áudio ({err}). Seguindo em silêncio.")

    def _get(self, name: str) -> pygame.mixer.Sound | None:
        if name not in self._sounds:
            path = C.AUDIO_DIR / f"{name}.wav"
            sound = None
            if path.exists():
                try:
                    sound = pygame.mixer.Sound(str(path))
                except pygame.error as err:
                    print(f"[audio] não consegui ler {path.name}: {err}")
            self._sounds[name] = sound
        return self._sounds[name]

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.ok:
            return
        sound = self._get(name)
        if sound:
            sound.set_volume(volume)
            sound.play()

    def loop(self, name: str, on: bool, volume: float = 1.0) -> None:
        """Liga/desliga um som em loop (alarme de O₂, zumbido das máquinas, ambiente)."""
        if not self.ok:
            return
        playing = name in self._loops
        if on and not playing:
            sound = self._get(name)
            if sound:
                channel = sound.play(loops=-1, fade_ms=400)
                if channel:
                    channel.set_volume(volume)
                    self._loops[name] = channel
        elif not on and playing:
            self._loops.pop(name).fadeout(400)


def load_font(filename: str, size: int, fallback_size: int) -> pygame.font.Font:
    """Fonte do mockup (game/fonts/) ou a fonte padrão do pygame se o arquivo sumir."""
    path = C.FONTS_DIR / filename
    if path.exists():
        try:
            return pygame.font.Font(str(path), size)
        except (pygame.error, OSError):
            pass
    return pygame.font.Font(None, fallback_size)
