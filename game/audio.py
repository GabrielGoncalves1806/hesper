"""Som do jogo: efeitos, loops (alarme, zumbido) e ambiente com crossfade entre estágios.

Segue as dicas de integração do Som (reports/audio/index.html, seção 08).
Se ENABLE_AUDIO = False, se não houver placa de som ou se faltar arquivo, tudo vira "não faz nada".

Canais reservados (o pygame não usa eles pra efeitos comuns):
    0 e 1 = ambiente A/B (alterna entre eles pra fazer crossfade)
    2     = alarme de O₂
    3     = zumbido das máquinas
"""

import random
from array import array

import pygame

from game import config as C

# Volumes ficam no config.py (VOLUME, AMBIENT_VOLUME, HUM_MAX_VOLUME), pra ajustar fácil entre playtests.
VOLUME = C.VOLUME
AMBIENT_VOLUME = C.AMBIENT_VOLUME
HUM_MAX_VOLUME = C.HUM_MAX_VOLUME

# Variações de pitch geradas no load (fator de velocidade) pra não soar repetitivo.
PITCH_VARIANTS = {
    "mine_hit": (0.95, 0.98, 1.0, 1.03, 1.06),
    "footstep_0": (0.96, 1.0, 1.04),
    "footstep_1": (0.96, 1.0, 1.04),
    "mine_break": (0.96, 1.0, 1.04),
    "pickup": (0.97, 1.0, 1.03),
    "ui_click": (0.98, 1.0, 1.02),
}
VOLUME_JITTER = {"mine_hit": 0.10}   # ±10% de volume no mine_hit

ALARM_ON_BELOW = 25.0    # % de O₂ que liga o alarme
ALARM_OFF_AT = 27.0      # % que desliga (histerese: não fica ligando/desligando na borda)
STAGE_JINGLE_TIME = 4.5  # duração do stage_up; o ambiente fica baixo durante ele
CROSSFADE_MS = 7000


# ---------------------------------------------------------------- regras puras (testáveis)
def alarm_should_play(currently_on: bool, o2: float) -> bool:
    """Histerese do alarme: liga abaixo de 25%, só desliga quando voltar a 27%."""
    if currently_on:
        return o2 < ALARM_OFF_AT
    return o2 < ALARM_ON_BELOW


def hum_volume(distance_tiles: float | None) -> float:
    """Zumbido pela máquina mais próxima: cheio até 2 tiles, some a partir de 8."""
    if distance_tiles is None:
        return 0.0
    k = 1 - (distance_tiles - 2) / 6
    return HUM_MAX_VOLUME * max(0.0, min(1.0, k))


def resample(samples: array, channels: int, factor: float) -> array:
    """Muda o pitch reamostrando (interpolação linear). factor > 1 = mais agudo e mais curto.

    Feito em Python puro pra não depender de numpy; os sons variados são todos curtinhos.
    """
    frames = len(samples) // channels
    n = max(1, int(frames / factor))
    out = array("h", bytes(2 * n * channels))
    last = frames - 1
    for i in range(n):
        pos = i * factor
        j = min(int(pos), last)
        j2 = min(j + 1, last)
        frac = pos - j
        for c in range(channels):
            a, b = samples[j * channels + c], samples[j2 * channels + c]
            out[i * channels + c] = int(a + (b - a) * frac)
    return out


def pre_init() -> None:
    """Tem que ser chamado ANTES do pygame.init(). Buffer baixo = mine_hit sem atraso."""
    if C.ENABLE_AUDIO:
        pygame.mixer.pre_init(44100, -16, 2, 512)


class Audio:
    def __init__(self, enabled: bool | None = None):
        self.ok = False
        self._sounds: dict[str, list[pygame.mixer.Sound]] = {}
        self._last_variant: dict[str, int] = {}
        self._delayed: list[list] = []          # [segundos que faltam, nome]
        self.alarm_on = False
        self.ambient_key: str | None = None
        self._amb_index = 0                      # qual dos canais 0/1 está tocando o ambiente
        self._amb_level = 1.0                    # 1 = normal; abaixa no jingle, no terminal e no desmaio
        self._amb_target = 1.0
        self._pending_ambient: list | None = None  # [segundos até o crossfade, chave do estágio novo]
        self._fade_busy = 0.0                    # enquanto > 0 não mexe no volume do ambiente (fade rolando)
        if not (C.ENABLE_AUDIO if enabled is None else enabled):
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(4)
            self.amb = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
            self.alarm_channel = pygame.mixer.Channel(2)
            self.hum_channel = pygame.mixer.Channel(3)
            self.ok = True
        except pygame.error as err:
            print(f"[audio] sem áudio ({err}). Seguindo em silêncio.")

    # ---- carregar --------------------------------------------------------------
    def _get(self, name: str) -> list[pygame.mixer.Sound]:
        """Lista de variações do som (vazia se o arquivo não existir)."""
        if name not in self._sounds:
            self._sounds[name] = self._load(name)
        return self._sounds[name]

    @staticmethod
    def _load(name: str) -> list[pygame.mixer.Sound]:
        path = C.AUDIO_DIR / f"{name}.wav"
        if not path.exists():
            return []
        try:
            sound = pygame.mixer.Sound(str(path))
        except pygame.error as err:
            print(f"[audio] não consegui ler {path.name}: {err}")
            return []
        factors = PITCH_VARIANTS.get(name)
        _, size, channels = pygame.mixer.get_init()
        if not factors or size != -16:
            return [sound]
        samples = array("h")
        samples.frombytes(sound.get_raw())
        return [sound if f == 1.0 else pygame.mixer.Sound(buffer=resample(samples, channels, f).tobytes())
                for f in factors]

    def _pick(self, name: str) -> pygame.mixer.Sound | None:
        """Sorteia uma variação, sem repetir a mesma duas vezes seguidas."""
        variants = self._get(name)
        if not variants:
            return None
        options = [i for i in range(len(variants)) if i != self._last_variant.get(name)] or [0]
        i = random.choice(options)
        self._last_variant[name] = i
        return variants[i]

    # ---- efeitos ---------------------------------------------------------------
    def play(self, name: str, delay: float = 0.0) -> None:
        if not self.ok:
            return
        if delay > 0:
            self._delayed.append([delay, name])
            return
        sound = self._pick(name)
        if sound:
            volume = VOLUME.get(name, 1.0)
            jitter = VOLUME_JITTER.get(name, 0.0)
            sound.set_volume(volume * random.uniform(1 - jitter, 1 + jitter))
            sound.play()

    # ---- loops -----------------------------------------------------------------
    def set_alarm(self, on: bool) -> None:
        if not self.ok or on == self.alarm_on:
            return
        self.alarm_on = on
        if on:
            sounds = self._get("o2_low")
            if sounds:
                self.alarm_channel.set_volume(VOLUME["o2_low"])
                self.alarm_channel.play(sounds[0], loops=-1)
        else:
            self.alarm_channel.fadeout(300)

    def set_hum(self, volume: float) -> None:
        """Um canal só pra todas as máquinas; o volume vem da máquina mais próxima."""
        if not self.ok:
            return
        sounds = self._get("machine_hum")
        if not sounds:
            return
        if volume > 0 and not self.hum_channel.get_busy():
            self.hum_channel.play(sounds[0], loops=-1)
        self.hum_channel.set_volume(volume)

    # ---- ambiente --------------------------------------------------------------
    def start_ambient(self, stage_key: str) -> None:
        if not self.ok:
            return
        sounds = self._get(f"amb_{stage_key}")
        self.ambient_key = stage_key
        if sounds:
            channel = self.amb[self._amb_index]
            channel.set_volume(AMBIENT_VOLUME)
            channel.play(sounds[0], loops=-1, fade_ms=2000)
            self._fade_busy = 2.0

    def stage_up(self, stage_key: str) -> None:
        """Toca o jingle, abaixa o ambiente durante ele e depois faz crossfade pro ambiente novo."""
        self.play("stage_up")
        if not self.ok:
            return
        self._amb_target = 0.4
        self._pending_ambient = [STAGE_JINGLE_TIME, stage_key]

    def _crossfade(self, stage_key: str) -> None:
        sounds = self._get(f"amb_{stage_key}")
        old = self.amb[self._amb_index]
        old.fadeout(CROSSFADE_MS)
        self._amb_index = 1 - self._amb_index
        self.ambient_key = stage_key
        self._amb_level = self._amb_target = 1.0
        if sounds:
            new = self.amb[self._amb_index]
            new.set_volume(AMBIENT_VOLUME)
            new.play(sounds[0], loops=-1, fade_ms=CROSSFADE_MS)
        self._fade_busy = CROSSFADE_MS / 1000

    def duck_ambient(self, level: float) -> None:
        """Nível alvo do ambiente: 1 normal, 0.6 lendo terminal, 0 desmaiado."""
        if self._pending_ambient is None:   # durante o jingle quem manda é o stage_up
            self._amb_target = level

    # ---- por frame -------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self.ok:
            return
        for item in self._delayed:
            item[0] -= dt
        for _, name in [it for it in self._delayed if it[0] <= 0]:
            self.play(name)
        self._delayed = [it for it in self._delayed if it[0] > 0]

        if self._pending_ambient:
            self._pending_ambient[0] -= dt
            if self._pending_ambient[0] <= 0:
                key = self._pending_ambient[1]
                self._pending_ambient = None
                self._crossfade(key)

        if self._fade_busy > 0:
            self._fade_busy -= dt
            return
        # aproxima o volume do ambiente do alvo devagar (~2 s de 1 até 0)
        step = dt / 2.0
        if abs(self._amb_level - self._amb_target) <= step:
            self._amb_level = self._amb_target
        else:
            self._amb_level += step if self._amb_target > self._amb_level else -step
        self.amb[self._amb_index].set_volume(AMBIENT_VOLUME * self._amb_level)
