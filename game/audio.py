"""Som do jogo: efeitos, loops (alarme, zumbido) e ambiente com crossfade entre estágios.

Segue as dicas de integração do Som (reports/audio/index.html, seção 08).
Se ENABLE_AUDIO = False, se não houver placa de som ou se faltar arquivo, tudo vira "não faz nada".

Canais reservados (o pygame não usa eles pra efeitos comuns):
    0 e 1 = ambiente A/B (alterna entre eles pra fazer crossfade)
    2     = alarme de O₂
    3     = zumbido das máquinas
    4 e 5 = loop das 2 drills trabalhando mais perto
    6 e 7 = loop dos 2 drones voando mais perto
    8     = zumbido do painel solar mais perto
    9     = vento do deserto
    10    = chuva (v0.4 M3.3, amb_rain.wav: volume = intensidade da chuva)
    11    = chiado da fumarola acordada mais perto (v11, vent_hiss.wav)
    12    = o "carregando" do desmonte · 13 = zumbido do Dispersor
    14 e 15 = loop das 2 Fundições fundindo mais perto (v0.6 Fundo M3, smelter_loop.wav)
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
    "build": (0.97, 1.0, 1.03),            # v0.5 M1 (Som): construir e desmontar variam um pouco
    "dismantle_done": (0.97, 1.0, 1.03),
    "door_open": (0.95, 1.0, 1.05),        # v0.5 M2 (Som): a porta varia o pitch 0,95–1,05
    "door_close": (0.95, 1.0, 1.05),
    "smelter_done": (0.96, 1.0, 1.04),     # v0.6 Fundo M3 (Som): várias Fundições não soam iguais
}
VOLUME_JITTER = {"mine_hit": 0.10}   # ±10% de volume no mine_hit
DERIVED = {"place_low": ("place", 0.8)}   # nome -> (arquivo base, fator de pitch); 0.8 = mais grave

ALARM_ON_BELOW = 25.0    # % de O₂ que liga o alarme
ALARM_OFF_AT = 27.0      # % que desliga (histerese: não fica ligando/desligando na borda)
STAGE_JINGLE_TIME = 4.5  # duração do stage_up; o ambiente fica baixo durante ele
CROSSFADE_MS = 7000
AMB_ROTATE_S = 34.0         # ambiente com variações (amb_storm, amb_storm_1, _2): troca de variação a cada volta do loop
AMB_ROTATE_MS = 6000        # crossfade entre variações do mesmo ambiente
WIND_FADE_IN, WIND_FADE_OUT = 2.5, 1.5   # s: vento sobe devagar ao sair pra superfície, desce mais rápido


# ---------------------------------------------------------------- regras puras (testáveis)
def ambient_for(layer: str, stage_key: str, has_cave: bool, has_storm: bool = False,
                cave_region: str | None = None) -> str:
    """Qual ambiente toca: na caverna o amb_cave (se o arquivo existir; senão fica o do estágio), na
    superfície o amb_{arte do estágio}. Mudar de estágio lá embaixo não troca o ambiente: o novo entra ao subir.
    Tempestade: amb_storm se o arquivo existir, senão amb_dead. Árido: amb_dead (mesma arte do Morto).
    v0.6 Fundo M2: na caverna, fora do centro, amb_cave_<região> (o chamador passa `cave_region` só se o
    arquivo existir)."""
    if layer == "cave" and has_cave:
        return f"cave_{cave_region}" if cave_region and cave_region != "plateau" else "cave"
    if stage_key == "storm" and has_storm:
        return "storm"
    return C.STAGE_ART.get(stage_key, stage_key)


class CaveRegionPicker:
    """Histerese do ambiente por bioma: a região "estável" só troca depois de C.CAVE_AMB_HOLD_S seguidos na nova
    (cruzar a fronteira e voltar não troca o som)."""

    def __init__(self):
        self.stable: str | None = None
        self._cand: str | None = None
        self._held = 0.0

    def reset(self, region: str | None) -> None:
        self.stable, self._cand, self._held = region, None, 0.0

    def update(self, region: str | None, dt: float) -> str | None:
        if region == self.stable:
            self._cand, self._held = None, 0.0
        elif region == self._cand:
            self._held += dt
            if self._held >= C.CAVE_AMB_HOLD_S:
                self.reset(region)
        else:
            self._cand, self._held = region, dt
            if self._held >= C.CAVE_AMB_HOLD_S:
                self.reset(region)
        return self.stable


def alarm_should_play(currently_on: bool, o2: float) -> bool:
    """Histerese do alarme: liga abaixo de 25%, só desliga quando voltar a 27%."""
    if currently_on:
        return o2 < ALARM_OFF_AT
    return o2 < ALARM_ON_BELOW


def drill_loop_volume(distance_tiles: float) -> float:
    """Loop da drill: cheio (VOLUME['drill_loop']) até 2 tiles, some a partir de 8 (dica do Som)."""
    k = 1 - (distance_tiles - 2) / 6
    return VOLUME.get("drill_loop", 0.5) * max(0.0, min(1.0, k))


def fade_by_distance(distance_tiles: float, full_until: float, silent_from: float) -> float:
    """1 até `full_until` tiles, cai em linha reta e chega a 0 em `silent_from` tiles."""
    k = 1 - (distance_tiles - full_until) / (silent_from - full_until)
    return max(0.0, min(1.0, k))


def drone_loop_volume(distance_tiles: float) -> float:
    """Loop do drone: cheio (0,5) até 3 tiles, some a partir de 10."""
    return VOLUME.get("drone_loop", 0.5) * fade_by_distance(distance_tiles, 3, 10)


def smelter_loop_volume(distance_tiles: float) -> float:
    """Loop da Fundição fundindo: cheio (0,45) até 2 tiles, some a partir de 7 (dica do Som)."""
    return VOLUME.get("smelter_loop", 0.45) * fade_by_distance(distance_tiles, 2, 7)


def smelter_done_gain(distance_tiles: float) -> float:
    """smelter_done (lingote saiu, 0,6 no VOLUME) atenuado: inteiro até 3 tiles, some a partir de 10."""
    return fade_by_distance(distance_tiles, 3, 10)


def drone_deliver_gain(distance_tiles: float) -> float:
    """drone_deliver (0,8 no VOLUME) atenuado pela distância: inteiro até 3 tiles, some a partir de 12."""
    return fade_by_distance(distance_tiles, 3, 12)


def solar_hum_volume(distance_tiles: float | None) -> float:
    """Zumbido do painel solar mais perto: cheio (0,5) até 2 tiles, some a partir de 6."""
    if distance_tiles is None:
        return 0.0
    return VOLUME.get("solar_hum", 0.5) * fade_by_distance(distance_tiles, 2, 6)


def wind_volume(level: float, ambient_level: float, ambient_gain: float) -> float:
    """Volume do vento: DESERT_WIND_VOLUME (relativo ao 0,7 do ambiente) × rampa × ducking × sliders."""
    return C.DESERT_WIND_VOLUME / AMBIENT_VOLUME * level * ambient_level * ambient_gain


def gust_gain(storm: float) -> float:
    """Som da rajada (VOLUME['gust'] no config) proporcional à tempestade: cheia = inteiro, sumindo = mais baixo."""
    return max(0.0, min(1.0, storm))


def rain_volume(intensity: float) -> float:
    """Loop da chuva (amb_rain): VOLUME['amb_rain'] (0,55) × intensidade (0..1). Sem o arquivo fica em silêncio."""
    return VOLUME.get("amb_rain", 1.0) * max(0.0, min(1.0, intensity))


def vent_hiss_volume(distance_tiles: float | None) -> float:
    """Chiado da fumarola acordada mais perto: VOLUME['vent_hiss'] (0,6) cheio até 2 tiles, some a partir de 7."""
    if distance_tiles is None:
        return 0.0
    return VOLUME.get("vent_hiss", 0.6) * fade_by_distance(distance_tiles, 2, 7)


def ice_collapse_gain(in_cave: bool) -> float:
    """Gain do ice_collapse: 1 na superfície; na caverna o desabamento sai a ICE_COLLAPSE_CAVE_VOLUME (0,5)."""
    return C.ICE_COLLAPSE_CAVE_VOLUME / VOLUME["ice_collapse"] if in_cave else 1.0


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
        self._amb_age = 0.0                      # segundos tocando a variação atual do ambiente (pra trocar)
        self._amb_level = 1.0                    # 1 = normal; abaixa no jingle, no terminal e no desmaio
        self._amb_target = 1.0
        self._pending_ambient: list | None = None  # [segundos até o crossfade, chave do estágio novo]
        self._pending_start: list | None = None    # [segundos, chave, fade_ms]: ambiente novo entrando atrasado
        self._fade_busy = 0.0                    # enquanto > 0 não mexe no volume do ambiente (fade rolando)
        self.mix = {"master": 1.0, "sfx": 1.0, "ambient": 1.0}   # sliders do menu de pausa
        self.wind_on = False                     # pediu vento (superfície)
        self._wind_level = 0.0                   # 0 a 1 (rampa: sobe em WIND_FADE_IN s, desce em WIND_FADE_OUT s)
        self._wind_started = False
        if not (C.ENABLE_AUDIO if enabled is None else enabled):
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(20)
            pygame.mixer.set_reserved(17)
            self.amb = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
            self.alarm_channel = pygame.mixer.Channel(2)
            self.hum_channel = pygame.mixer.Channel(3)
            self.drill_channels = [pygame.mixer.Channel(4), pygame.mixer.Channel(5)]
            self._drill_on = [False, False]       # pra pedir o fadeout uma vez só (não reiniciar o fade)
            self.drone_channels = [pygame.mixer.Channel(6), pygame.mixer.Channel(7)]
            self._drone_on = [False, False]
            self.solar_channel = pygame.mixer.Channel(8)
            self._solar_on = [False]
            # vento do deserto (v0.3): canal próprio (não os A/B do crossfade, senão a troca de estágio
            # corta o vento). Toca em loop sempre; só o volume sobe/desce (não reinicia indo e voltando).
            self.wind_channel = pygame.mixer.Channel(9)
            self.rain_channel = pygame.mixer.Channel(10)   # chuva (v0.4 M3.3): loop com o volume da intensidade
            self._rain_on = [False]
            self._rain_name = "amb_rain"                   # variação tocando (v11: fraca, média ou forte)
            self.vent_channel = pygame.mixer.Channel(11)   # chiado da fumarola (v11): pela mais perto
            self._vent_on = [False]
            self.charge_channel = pygame.mixer.Channel(12)   # v0.5 M1: o "carregando" do desmonte (canal único)
            self.dispenser_channel = pygame.mixer.Channel(13)   # v0.5 M2: o zumbido do Dispersor (loop com fade)
            self._dispenser_on = [False]
            self.scan_channel = pygame.mixer.Channel(16)   # v0.7 M2: o loop do scan (canal único)
            self.smelter_channels = [pygame.mixer.Channel(14), pygame.mixer.Channel(15)]   # v0.6 Fundo M3
            self._smelter_on = [False, False]
            self.ok = True
        except pygame.error as err:
            print(f"[audio] sem áudio ({err}). Seguindo em silêncio.")

    # ---- mixagem (menu de pausa) ----------------------------------------------
    @property
    def sfx_gain(self) -> float:
        return self.mix["master"] * self.mix["sfx"]

    @property
    def ambient_gain(self) -> float:
        return AMBIENT_VOLUME * self.mix["master"] * self.mix["ambient"]

    def set_mix(self, master: float, sfx: float, ambient: float) -> None:
        """Aplica os sliders na hora: multiplicam a tabela VOLUME do config.py."""
        self.mix = {"master": master, "sfx": sfx, "ambient": ambient}
        if not self.ok:
            return
        if self.alarm_on:
            self.alarm_channel.set_volume(VOLUME["o2_low"] * self.sfx_gain)
        if self._fade_busy <= 0:
            self.amb[self._amb_index].set_volume(self.ambient_gain * self._amb_level)

    # ---- carregar --------------------------------------------------------------
    def _get(self, name: str) -> list[pygame.mixer.Sound]:
        """Lista de variações do som (vazia se o arquivo não existir)."""
        if name not in self._sounds:
            self._sounds[name] = self._load(name)
        return self._sounds[name]

    @staticmethod
    def _load(name: str) -> list[pygame.mixer.Sound]:
        if name in DERIVED:   # som gerado a partir de outro (ex.: "place" mais grave pro desmontar)
            base, factor = DERIVED[name]
            sounds = Audio._load(base)
            _, size, channels = pygame.mixer.get_init()
            if not sounds or size != -16:
                return sounds
            samples = array("h")
            samples.frombytes(sounds[0].get_raw())
            return [pygame.mixer.Sound(buffer=resample(samples, channels, factor).tobytes())]
        path = C.AUDIO_DIR / f"{name}.wav"
        if not path.exists():
            return []
        try:
            sound = pygame.mixer.Sound(str(path))
        except pygame.error as err:
            print(f"[audio] não consegui ler {path.name}: {err}")
            return []
        extra = []                    # variações gravadas: <nome>_1.wav, <nome>_2.wav... (ex.: gust, amb_storm)
        i = 1
        while (C.AUDIO_DIR / f"{name}_{i}.wav").exists():
            try:
                extra.append(pygame.mixer.Sound(str(C.AUDIO_DIR / f"{name}_{i}.wav")))
            except pygame.error as err:
                print(f"[audio] não consegui ler {name}_{i}.wav: {err}")
            i += 1
        if extra:
            return [sound] + extra
        factors = PITCH_VARIANTS.get(name)
        _, size, channels = pygame.mixer.get_init()
        if not factors or size != -16:
            return [sound]
        samples = array("h")
        samples.frombytes(sound.get_raw())
        return [sound if f == 1.0 else pygame.mixer.Sound(buffer=resample(samples, channels, f).tobytes())
                for f in factors]

    def has(self, name: str) -> bool:
        """Tem arquivo desse efeito em assets/audio? (som que ainda não chegou usa outro no lugar)"""
        return bool(self.ok and self._get(name))

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
    def play(self, name: str, delay: float = 0.0, gain: float = 1.0, channel=None):
        """Toca um efeito. `gain` (0 a 1) abaixa o volume, ex.: som longe do player. `channel` = toca nesse canal
        (senão, num livre). Devolve o Channel em que tocou (None: sem áudio, sem arquivo ou com `delay`)."""
        if not self.ok or gain <= 0:
            return None
        if delay > 0:
            self._delayed.append([delay, name])
            return None
        sound = self._pick(name)
        if not sound:
            return None
        volume = VOLUME.get(name, 1.0) * gain
        jitter = VOLUME_JITTER.get(name, 0.0)
        sound.set_volume(volume * self.sfx_gain * random.uniform(1 - jitter, 1 + jitter))
        if channel is not None:
            channel.play(sound)
            return channel
        return sound.play()

    # ---- desmontar segurando (v0.5 M1) ----------------------------------------
    def start_charge(self) -> None:
        """Começou a encher a barrinha do desmonte: o dismantle_charge no canal dele (reinicia se já tocava)."""
        if self.ok:
            self.play("dismantle_charge", channel=self.charge_channel)

    def stop_charge(self, fade_ms: int = C.DISMANTLE_CHARGE_FADE_MS) -> None:
        """Soltou antes (ou tirou o mouse): o charge sai num fadeout curto, nunca num stop seco."""
        if self.ok and self.charge_channel.get_busy():
            self.charge_channel.fadeout(fade_ms)

    # ---- scan do construtor (v0.7 M2) -------------------------------------------
    def start_scan(self) -> None:
        """Começou a escanear: o scan_loop (um sweep só de ~1,66 s que acompanha a barrinha, não é loop) no canal dele."""
        sound = self._pick("scan_loop") if self.ok else None
        if sound:
            sound.set_volume(VOLUME["scan_loop"] * self.sfx_gain)
            self.scan_channel.play(sound)

    def stop_scan(self, fade_ms: int = 40) -> None:
        if self.ok and self.scan_channel.get_busy():
            self.scan_channel.fadeout(fade_ms)

    # ---- loops -----------------------------------------------------------------
    def set_alarm(self, on: bool) -> None:
        if not self.ok or on == self.alarm_on:
            return
        self.alarm_on = on
        if on:
            sounds = self._get("o2_low")
            if sounds:
                self.alarm_channel.set_volume(VOLUME["o2_low"] * self.sfx_gain)
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
        self.hum_channel.set_volume(volume * self.sfx_gain)

    def set_dispenser_hum(self, volume: float, out_ms: int = C.DISPENSER_HUM_FADE_MS) -> None:
        """dispenser_hum.wav (v0.5 M2): loop num canal próprio, entra com fade de 0,8 s e sai com `out_ms` (0,3 s quando a
        água acabou). Volume 0 = sai. Sem o arquivo, silêncio."""
        if not self.ok:
            return
        sounds = self._get("dispenser_hum")
        if not sounds:
            return
        channel = self.dispenser_channel
        if volume > 0:
            if not self._dispenser_on[0] or not channel.get_busy():
                channel.play(sounds[0], loops=-1, fade_ms=C.DISPENSER_HUM_FADE_MS)
                self._dispenser_on[0] = True
            channel.set_volume(volume * self.sfx_gain)
        elif self._dispenser_on[0]:
            channel.fadeout(out_ms)
            self._dispenser_on[0] = False

    def set_drill_loops(self, volumes: list[float]) -> None:
        """Loop da drill em até 2 canais (as 2 trabalhando mais perto). Volume 0 = some com fadeout(400)."""
        if self.ok:
            self._set_loops("drill_loop", self.drill_channels, self._drill_on, volumes)

    def set_drone_loops(self, volumes: list[float]) -> None:
        """Loop do drone em até 2 canais (os 2 voando mais perto do player)."""
        if self.ok:
            self._set_loops("drone_loop", self.drone_channels, self._drone_on, volumes)

    def set_smelter_loops(self, volumes: list[float]) -> None:
        """Loop da Fundição em até 2 canais (as 2 fundindo mais perto). Volume 0 = some com fadeout(400)."""
        if self.ok:
            self._set_loops("smelter_loop", self.smelter_channels, self._smelter_on, volumes)

    def set_solar_hum(self, volume: float) -> None:
        """Um canal só, com o volume do painel solar mais perto."""
        if self.ok:
            self._set_loops("solar_hum", [self.solar_channel], self._solar_on, [volume])

    def set_rain(self, volume: float, name: str = "amb_rain") -> None:
        """Loop da chuva com o volume da intensidade. `name` é a variação da pancada (amb_rain, _light ou _heavy):
        se mudar com a chuva rolando, o canal troca de arquivo. Sem o arquivo, silêncio."""
        if not self.ok:
            return
        if name != self._rain_name:
            self._rain_name = name
            self._rain_on[0] = False          # força o play() da variação nova (corta a antiga)
        self._set_loops(name, [self.rain_channel], self._rain_on, [volume])

    def set_vent(self, volume: float) -> None:
        """Chiado (vent_hiss.wav) da fumarola acordada mais perto, num canal próprio. Volume 0 = some."""
        if self.ok:
            self._set_loops("vent_hiss", [self.vent_channel], self._vent_on, [volume])

    def _set_loops(self, name: str, channels, on: list[bool], volumes: list[float]) -> None:
        """Loop `name` em vários canais, um volume por canal. Volume 0 = some com fadeout(400)."""
        sounds = self._get(name)
        if not sounds:
            return
        for i, channel in enumerate(channels):
            volume = volumes[i] if i < len(volumes) else 0.0
            if volume > 0:
                if not on[i] or not channel.get_busy():
                    channel.play(sounds[0], loops=-1, fade_ms=200)
                    on[i] = True
                channel.set_volume(volume * self.sfx_gain)
            elif on[i]:
                channel.fadeout(400)          # parou (ou ficou longe): sai suave
                on[i] = False

    # ---- ambiente --------------------------------------------------------------
    def start_ambient(self, stage_key: str) -> None:
        if not self.ok:
            return
        sounds = self._get(f"amb_{stage_key}")
        self.ambient_key = stage_key
        if sounds:
            channel = self.amb[self._amb_index]
            channel.set_volume(self.ambient_gain)
            channel.play(self._pick(f"amb_{stage_key}"), loops=-1, fade_ms=2000)
            self._amb_age = 0.0
            self._fade_busy = 2.0

    def stage_up(self, stage_key: str) -> None:
        """Toca o jingle, abaixa o ambiente durante ele e depois faz crossfade pro ambiente novo."""
        self.play("stage_up")
        if not self.ok:
            return
        self._amb_target = 0.4
        self._pending_ambient = [STAGE_JINGLE_TIME, stage_key]

    def has(self, name: str) -> bool:
        """O som existe (arquivo em assets/audio/ e áudio ligado)?"""
        return self.ok and bool(self._get(name))

    def crossfade_to(self, key: str, out_ms: int = C.CAVE_AMBIENT_OUT_MS, in_ms: int = C.CAVE_AMBIENT_IN_MS,
                     delay: float = C.CAVE_AMBIENT_DELAY) -> None:
        """Troca de ambiente na rampa (dica do Som): o atual some em `out_ms` e o novo entra em `in_ms`,
        `delay` s depois. Mesmos canais A/B do ambiente (substitui, não soma)."""
        if self.ok:
            self._crossfade(key, out_ms, in_ms, delay)

    def _crossfade(self, stage_key: str, out_ms: int = CROSSFADE_MS, in_ms: int = CROSSFADE_MS,
                   delay: float = 0.0) -> None:
        if stage_key == self.ambient_key:              # já é esse (ex.: estágio mudou com o player na caverna)
            self._amb_level = self._amb_target = 1.0
            self.amb[self._amb_index].set_volume(self.ambient_gain)
            return
        old = self.amb[self._amb_index]
        old.fadeout(out_ms)
        self._amb_index = 1 - self._amb_index
        self.ambient_key = stage_key
        self._amb_level = self._amb_target = 1.0
        self._pending_start = None
        if delay > 0:
            self._pending_start = [delay, stage_key, in_ms]
        else:
            self._start_on_channel(stage_key, in_ms)
        self._fade_busy = delay + in_ms / 1000

    def _start_on_channel(self, key: str, fade_ms: int) -> None:
        sounds = self._get(f"amb_{key}")
        if sounds:
            new = self.amb[self._amb_index]
            new.set_volume(self.ambient_gain)
            new.play(self._pick(f"amb_{key}"), loops=-1, fade_ms=fade_ms)
            self._amb_age = 0.0

    def _rotate_ambient(self) -> None:
        """Ambiente com variações: crossfade pra outra variação do mesmo ambiente, no outro canal A/B."""
        self.amb[self._amb_index].fadeout(AMB_ROTATE_MS)
        self._amb_index = 1 - self._amb_index
        self._start_on_channel(self.ambient_key, AMB_ROTATE_MS)
        self._fade_busy = AMB_ROTATE_MS / 1000

    def set_wind(self, on: bool) -> None:
        """Vento do deserto por cima do ambiente (desert_wind.wav). Sem o arquivo, silêncio."""
        self.wind_on = on

    def _update_wind(self, dt: float) -> None:
        target = 1.0 if self.wind_on else 0.0
        step = dt / (WIND_FADE_IN if target > self._wind_level else WIND_FADE_OUT)
        self._wind_level = target if abs(target - self._wind_level) <= step else \
            self._wind_level + (step if target > self._wind_level else -step)
        if not self._wind_started and self._wind_level > 0:
            sounds = self._get("desert_wind")
            if not sounds:
                return
            self.wind_channel.play(sounds[0], loops=-1)
            self._wind_started = True
        if self._wind_started:   # cai junto com o ambiente (desmaio, terminal)
            self.wind_channel.set_volume(wind_volume(self._wind_level, self._amb_level, self.ambient_gain))

    @property
    def busy_with_stage(self) -> bool:
        """O jingle de estágio está tocando e o crossfade dele ainda não aconteceu."""
        return self._pending_ambient is not None

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

        self._update_wind(dt)
        if self._pending_start:
            self._pending_start[0] -= dt
            if self._pending_start[0] <= 0:
                _, key, fade_ms = self._pending_start
                self._pending_start = None
                if key == self.ambient_key:
                    self._start_on_channel(key, fade_ms)
        if self._pending_ambient:
            self._pending_ambient[0] -= dt
            if self._pending_ambient[0] <= 0:
                key = self._pending_ambient[1]
                self._pending_ambient = None
                self._crossfade(key)

        self._amb_age += dt
        if (self.ambient_key and self._amb_age >= AMB_ROTATE_S and self._fade_busy <= 0
                and not self._pending_ambient and not self._pending_start
                and len(self._get(f"amb_{self.ambient_key}")) > 1):
            self._rotate_ambient()
        if self._fade_busy > 0:
            self._fade_busy -= dt
            return
        # aproxima o volume do ambiente do alvo devagar (~2 s de 1 até 0)
        step = dt / 2.0
        if abs(self._amb_level - self._amb_target) <= step:
            self._amb_level = self._amb_target
        else:
            self._amb_level += step if self._amb_target > self._amb_level else -step
        self.amb[self._amb_index].set_volume(self.ambient_gain * self._amb_level)
