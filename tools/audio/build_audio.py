"""Gera todos os sons do Hesper por síntese procedural.

Uso:  python3 tools/audio/build_audio.py

Saída: assets/audio/*.wav (44,1 kHz, 16-bit, mono) e reports/audio/audio_meta.js
(duração, pico, loudness e forma de onda de cada arquivo, usado pelo report).

Só depende de numpy. Tudo é determinístico: cada som tem a própria seed derivada
de BASE_SEED + nome, então mexer em um som não muda os outros.

Loops (o2_low, machine_hum, amb_*) são construídos de forma periódica: todo ruído
é filtrado no domínio da frequência de forma circular, toda frequência fixa tem um
número inteiro de ciclos no comprimento do loop, eventos (rajadas, gotas, pássaros)
dão a volta pelo começo e o reverb é convolução circular. Resultado: a amostra
depois da última é exatamente a primeira, sem estalo e sem crossfade.
"""

from __future__ import annotations

import json
import wave
import zlib
from pathlib import Path

import numpy as np

SR = 44100
BASE_SEED = 1337
CEILING = 10 ** (-1.05 / 20)  # pico máximo um tico abaixo de -1 dBFS (folga pro arredondamento)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "assets" / "audio"
REPORT_DIR = ROOT / "reports" / "audio"


# ---------------------------------------------------------------------------
# utilidades básicas
# ---------------------------------------------------------------------------

def rng_for(name: str) -> np.random.Generator:
    return np.random.default_rng(BASE_SEED + zlib.crc32(name.encode()))


def ns(sec: float) -> int:
    return int(round(sec * SR))


def tvec(n: int) -> np.ndarray:
    return np.arange(n) / SR


def fr(f: float, L: float) -> float:
    """Arredonda a frequência pra ter número inteiro de ciclos em L segundos."""
    return round(f * L) / L


def midi(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def phase_of(freq, n: int, ph0: float = 0.0) -> np.ndarray:
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    return 2 * np.pi * np.cumsum(f) / SR + ph0


def bl_wave(freq, n: int, shape: str = "square", cutoff: float = 6000.0,
            duty: float = 0.5, ph0: float = 0.0) -> np.ndarray:
    """Onda limitada em banda por síntese aditiva (sem aliasing).

    `cutoff` funciona como um passa-baixa suave: harmônicos acima dele são
    atenuados, dando o timbre "chip" arredondado em vez do quadrado cru.
    """
    f = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    ph = 2 * np.pi * np.cumsum(f) / SR + ph0
    fmax = float(f.max())
    kmax = max(1, int((SR / 2 - 1000) / fmax))
    out = np.zeros(n)
    for k in range(1, kmax + 1):
        g = 1.0 / np.sqrt(1 + (k * fmax / cutoff) ** 4)
        if g < 0.004:
            break
        if shape == "square":
            if k % 2 == 0:
                continue
            out += g * np.sin(k * ph) / k
        elif shape == "saw":
            out += g * ((-1) ** (k + 1)) * np.sin(k * ph) / k
        elif shape == "tri":
            if k % 2 == 0:
                continue
            out += g * ((-1) ** ((k - 1) // 2)) * np.sin(k * ph) / k ** 2
        elif shape == "pulse":
            out += g * np.sin(np.pi * k * duty) * np.cos(k * ph) / k
        else:
            raise ValueError(shape)
    m = np.max(np.abs(out))
    return out / m if m > 0 else out


def bw_mag(f: np.ndarray, lo, hi, order: int) -> np.ndarray:
    H = np.ones_like(f)
    if hi:
        H = H / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        H = H / np.sqrt(1 + (lo / np.maximum(f, 1e-6)) ** (2 * order))
    return H


def filt(x: np.ndarray, lo=None, hi=None, order: int = 2, circular: bool = False) -> np.ndarray:
    """Filtro Butterworth de fase zero aplicado no domínio da frequência.

    circular=True trata o sinal como periódico (pra loops).
    """
    n = len(x)
    N = n if circular else n + ns(0.15)
    X = np.fft.rfft(x, N)
    f = np.fft.rfftfreq(N, 1 / SR)
    return np.fft.irfft(X * bw_mag(f, lo, hi, order), N)[:n]


def perc(n: int, attack: float, decay: float) -> np.ndarray:
    """Ataque linear + decaimento exponencial (decay = constante de tempo em s)."""
    t = tvec(n)
    a = max(attack, 1e-4)
    env = np.where(t < a, t / a, np.exp(-(t - a) / decay))
    return env


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    t = tvec(n)
    dur = n / SR
    rel_start = max(dur - r, a + d)
    env = np.empty(n)
    env[:] = s
    m = t < a
    env[m] = t[m] / max(a, 1e-4)
    m = (t >= a) & (t < a + d)
    env[m] = 1 - (1 - s) * (t[m] - a) / max(d, 1e-4)
    m = t >= rel_start
    env[m] = s * np.clip(1 - (t[m] - rel_start) / max(r, 1e-4), 0, 1)
    return env


def bump(n: int, rise: float = 0.3) -> np.ndarray:
    """Envelope suave assimétrico (sobe em `rise` da duração, desce no resto)."""
    x = np.linspace(0, 1, n, endpoint=False)
    up = 0.5 - 0.5 * np.cos(np.pi * np.clip(x / rise, 0, 1))
    down = 0.5 + 0.5 * np.cos(np.pi * np.clip((x - rise) / (1 - rise), 0, 1))
    return np.where(x < rise, up, down)


class Track:
    """Mixer simples pra sfx: soma sinais em posições (s) e cresce sozinho."""

    def __init__(self) -> None:
        self.parts: list[tuple[int, np.ndarray]] = []

    def add(self, sig: np.ndarray, at: float = 0.0, gain: float = 1.0) -> None:
        self.parts.append((ns(at), sig * gain))

    def render(self, min_len: float = 0.0) -> np.ndarray:
        n = max([s + len(x) for s, x in self.parts] + [ns(min_len)])
        out = np.zeros(n)
        for s, x in self.parts:
            out[s:s + len(x)] += x
        return out


def add_circ(buf: np.ndarray, sig: np.ndarray, start: int, gain: float = 1.0) -> None:
    n = len(buf)
    idx = (start + np.arange(len(sig))) % n
    buf[idx] += sig * gain


def make_ir(rng, decay: float, lp: float = 5000.0, predelay: float = 0.012) -> np.ndarray:
    n = ns(decay * 1.3)
    t = tvec(n)
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / decay)
    ir = filt(ir, 150, lp, order=1)
    ir = np.concatenate([np.zeros(ns(predelay)), ir])
    return ir / np.sqrt(np.sum(ir ** 2))


def reverb(x: np.ndarray, rng, decay: float = 1.0, mix: float = 0.2, lp: float = 5000.0,
           circular: bool = False) -> np.ndarray:
    ir = make_ir(rng, decay, lp)
    if circular:
        n = len(x)
        assert len(ir) < n
        wet = np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(ir, n), n)
        return x + mix * wet
    n = len(x) + len(ir)
    N = 1 << (n - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:n]
    dry = np.concatenate([x, np.zeros(len(ir))])
    return dry + mix * wet


def echo(x: np.ndarray, delay: float, fb: float, taps: int = 3, lp: float | None = 3500,
         circular: bool = False) -> np.ndarray:
    d = ns(delay)
    if circular:
        out = x.copy()
        tap = x
        for i in range(taps):
            tap = filt(tap, None, lp, 1, circular=True) if lp else tap
            out += np.roll(tap, d * (i + 1)) * fb ** (i + 1)
        return out
    out = np.concatenate([x, np.zeros(d * taps)])
    tap = x
    for i in range(1, taps + 1):
        tap = filt(tap, None, lp, 1) if lp else tap
        out[d * i:d * i + len(x)] += tap * fb ** i
    return out


def periodic_ctrl(n: int, L: float, rng, kmin: int = 1, kmax: int = 6, tilt: float = 1.0) -> np.ndarray:
    """Curva de controle lenta e aleatória, mas exatamente periódica em L. Faixa 0..1."""
    t = tvec(n)
    s = np.zeros(n)
    for k in range(kmin, kmax + 1):
        s += np.sin(2 * np.pi * k * t / L + rng.uniform(0, 2 * np.pi)) / k ** tilt
    s -= s.min()
    return s / s.max()


def gusts(n: int, rng, count: int, dur_range=(2.0, 4.0), rise: float = 0.35) -> np.ndarray:
    env = np.zeros(n)
    slots = np.sort(rng.uniform(0, 1, count)) * n
    for st in slots:
        m = ns(rng.uniform(*dur_range))
        add_circ(env, bump(m, rise) * rng.uniform(0.6, 1.0), int(st))
    return np.clip(env, 0, 1)


# ---------------------------------------------------------------------------
# blocos sonoros reutilizáveis
# ---------------------------------------------------------------------------

def thump(rng, f_start: float, f_end: float, sweep: float, decay: float, dur: float) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    f = f_end + (f_start - f_end) * np.exp(-t / sweep)
    return np.sin(phase_of(f, n)) * perc(n, 0.002, decay)


def noise_burst(rng, lo, hi, attack: float, decay: float, dur: float, order: int = 2) -> np.ndarray:
    n = ns(dur)
    return filt(rng.standard_normal(n), lo, hi, order) * perc(n, attack, decay)


def metal(rng, base: float, ratios, decays, amps, dur: float) -> np.ndarray:
    """Batida metálica: parciais inarmônicos com decaimentos diferentes."""
    n = ns(dur)
    t = tvec(n)
    out = np.zeros(n)
    for r, d, a in zip(ratios, decays, amps):
        out += a * np.sin(2 * np.pi * base * r * t + rng.uniform(0, 6.28)) * np.exp(-t / d)
    out *= np.minimum(1, t / 0.0015)
    return out


def chip_note(freq: float, dur: float, shape: str = "pulse", cutoff: float = 4000.0, duty: float = 0.25,
              a: float = 0.004, decay: float | None = None, sustain: float = 0.7, release: float = 0.04,
              vib: float = 0.0, vib_rate: float = 5.5, vib_delay: float = 0.15) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    f = np.full(n, freq)
    if vib:
        depth = vib * np.clip((t - vib_delay) / 0.2, 0, 1)
        f = freq * (1 + depth * np.sin(2 * np.pi * vib_rate * t))
    x = bl_wave(f, n, shape, cutoff, duty)
    env = perc(n, a, decay) if decay else adsr(n, a, 0.06, sustain, release)
    if decay:
        env *= np.clip((n / SR - t) / release, 0, 1)
    return x * env


def plink(rng, f0: float, dur: float = 0.06) -> np.ndarray:
    """Gota d'água: senoide com pitch subindo rápido e decaimento curto."""
    n = ns(dur)
    t = tvec(n)
    f = f0 * (1 + 0.7 * (1 - np.exp(-t / 0.012)))
    return np.sin(phase_of(f, n)) * perc(n, 0.0008, 0.014)


# ---------------------------------------------------------------------------
# sfx
# ---------------------------------------------------------------------------

def sfx_mine_hit(rng):
    tr = Track()
    tr.add(thump(rng, 230, 115, 0.018, 0.045, 0.16), 0, 1.0)            # "toc" grave da rocha
    tr.add(noise_burst(rng, 1300, 4200, 0.0005, 0.009, 0.06), 0, 0.7)  # estalo do impacto
    tr.add(noise_burst(rng, 350, 1400, 0.001, 0.035, 0.14), 0.002, 0.35)  # cascalho
    tr.add(chip_note(1180, 0.05, "tri", 5000, decay=0.018, release=0.01), 0, 0.18)  # "tink" da ferramenta
    return tr.render()


def sfx_mine_break(rng):
    tr = Track()
    tr.add(thump(rng, 160, 42, 0.05, 0.13, 0.5), 0, 1.0)
    tr.add(noise_burst(rng, 900, 5500, 0.0005, 0.016, 0.1), 0, 0.8)       # crack
    tr.add(noise_burst(rng, 60, 600, 0.004, 0.16, 0.6), 0, 0.55)          # rumor do desabamento
    # pedrinhas caindo: grãos cada vez mais esparsos e fracos
    for i in range(22):
        u = rng.uniform()
        at = 0.02 + 0.42 * u ** 1.5
        amp = (1 - u) ** 1.2 * rng.uniform(0.25, 0.6)
        c = rng.uniform(600, 2600)
        tr.add(noise_burst(rng, c * 0.6, c * 1.6, 0.0005, rng.uniform(0.004, 0.012), 0.04), at, amp)
        if rng.uniform() < 0.35:
            tr.add(chip_note(rng.uniform(700, 1500), 0.03, "tri", 4000, decay=0.008, release=0.005), at, amp * 0.3)
    x = tr.render()
    return reverb(x, rng, decay=0.45, mix=0.18, lp=3500)


def sfx_pickup(rng):
    tr = Track()
    tr.add(chip_note(midi(76), 0.07, "pulse", 4200, 0.25, decay=0.05, release=0.02), 0, 0.8)   # E5
    tr.add(chip_note(midi(83), 0.16, "pulse", 4200, 0.25, decay=0.07, release=0.04), 0.06, 0.8)  # B5
    tr.add(chip_note(midi(71), 0.2, "tri", 3000, decay=0.08, release=0.04), 0.06, 0.35)          # corpo
    x = tr.render()
    return echo(x, 0.085, 0.22, taps=2, lp=2500)


def sfx_craft(rng):
    tr = Track()
    tr.add(metal(rng, 410, [1, 2.76, 5.4, 8.93], [0.09, 0.05, 0.03, 0.015], [1, 0.5, 0.25, 0.12], 0.35), 0, 0.6)
    tr.add(noise_burst(rng, 1500, 6000, 0.0005, 0.006, 0.03), 0, 0.4)
    tr.add(metal(rng, 520, [1, 2.76, 5.4, 8.93], [0.08, 0.045, 0.025, 0.012], [1, 0.5, 0.25, 0.1], 0.3), 0.13, 0.5)
    tr.add(noise_burst(rng, 1500, 6000, 0.0005, 0.006, 0.03), 0.13, 0.35)
    # servo/montagem: dente de serra subindo com trêmolo
    n = ns(0.36)
    t = tvec(n)
    f = 170 * 2 ** (1.6 * t / 0.36)
    whirr = bl_wave(f, n, "saw", 1800) * (0.75 + 0.25 * np.sin(2 * np.pi * 28 * t)) * bump(n, 0.6)
    tr.add(whirr, 0.22, 0.32)
    # "pronto!": sino suave em quinta (A5 + E6)
    for fq, g in ((midi(81), 0.55), (midi(88), 0.3)):
        tr.add(metal(rng, fq, [1, 2.0, 3.0, 4.07], [0.45, 0.2, 0.1, 0.05], [1, 0.25, 0.08, 0.04], 1.0), 0.58, g)
    x = tr.render()
    return reverb(x, rng, decay=0.9, mix=0.22, lp=4500)


def sfx_place(rng):
    tr = Track()
    tr.add(thump(rng, 150, 48, 0.04, 0.13, 0.55), 0, 0.8)
    tr.add(noise_burst(rng, None, 260, 0.002, 0.07, 0.3), 0, 0.6)
    tr.add(metal(rng, 290, [1, 2.4, 4.1], [0.07, 0.04, 0.02], [1, 0.4, 0.2], 0.25), 0.025, 0.6)
    tr.add(noise_burst(rng, 500, 2500, 0.001, 0.02, 0.1), 0.02, 0.35)  # corpo médio pro impacto aparecer em caixinha de som
    tr.add(noise_burst(rng, 1600, 4200, 0.05, 0.06, 0.25) , 0.12, 0.08)    # pneumático assentando
    tr.add(noise_burst(rng, 1800, 5000, 0.0005, 0.004, 0.02), 0.3, 0.3)    # trava
    tr.add(chip_note(1500, 0.03, "tri", 5000, decay=0.008, release=0.005), 0.3, 0.12)
    x = tr.render()
    return reverb(x, rng, decay=0.5, mix=0.16, lp=3500)


def _two_blip(f1, f2, gap=0.045):
    tr = Track()
    tr.add(chip_note(f1, 0.06, "square", 3000, decay=0.03, release=0.015), 0, 0.7)
    tr.add(chip_note(f2, 0.11, "square", 3000, decay=0.045, release=0.03), gap, 0.7)
    tr.add(chip_note(f2 / 2, 0.11, "tri", 2000, decay=0.05, release=0.03), gap, 0.3)
    return tr.render()


def sfx_ui_open(rng):
    return echo(_two_blip(midi(69), midi(76)), 0.07, 0.15, taps=1)   # A4 -> E5


def sfx_ui_close(rng):
    return echo(_two_blip(midi(76), midi(69)), 0.07, 0.15, taps=1)   # E5 -> A4


def sfx_ui_click(rng):
    tr = Track()
    tr.add(chip_note(1480, 0.04, "tri", 5000, decay=0.012, release=0.008), 0, 0.8)
    tr.add(chip_note(2960, 0.025, "tri", 6000, decay=0.006, release=0.005), 0, 0.25)
    tr.add(noise_burst(rng, 2000, 7000, 0.0003, 0.002, 0.012), 0, 0.25)
    return tr.render()


def sfx_o2_refill(rng):
    tr = Track()
    # ar entrando: dois ruídos com crossfade (sobe de escuro pra claro)
    n = ns(0.75)
    t = tvec(n)
    x = t / (n / SR)
    low = filt(rng.standard_normal(n), 500, 1800, 2)
    high = filt(rng.standard_normal(n), 1800, 6500, 2)
    hiss = (low * (1 - x) + high * x * 0.7) * bump(n, 0.2)
    tr.add(hiss, 0, 0.35)
    # arpejo de alívio A4 C#5 E5 + A5 brilhando
    for i, m in enumerate((69, 73, 76, 81)):
        tr.add(chip_note(midi(m), 0.4, "tri", 4000, decay=0.16, release=0.08), 0.06 + 0.075 * i, 0.5)
        tr.add(np.sin(phase_of(midi(m), ns(0.4))) * perc(ns(0.4), 0.004, 0.12), 0.06 + 0.075 * i, 0.25)
    out = tr.render()
    return reverb(out, rng, decay=0.8, mix=0.2, lp=5000)


def sfx_faint(rng):
    tr = Track()
    dur = 2.0
    n = ns(dur)
    t = tvec(n)
    vib = 1 + (0.01 + 0.04 * t / dur) * np.sin(2 * np.pi * (5.5 - 2 * t / dur) * t)
    f = 520 * 2 ** (-2.4 * t / dur) * vib
    tone = bl_wave(f, n, "tri", 2500) * adsr(n, 0.03, 0.2, 0.75, 1.2)
    tone = filt(tone, None, 1600, 1)
    tr.add(tone, 0, 0.55)
    # suspiro / ar escapando, escurecendo
    breath = filt(rng.standard_normal(n), 300, 2500, 2) * (np.exp(-t / 0.35) * np.minimum(1, t / 0.05))
    tr.add(breath, 0, 0.18)
    # coração desacelerando
    for at, g in ((0.08, 1.0), (0.3, 0.7), (0.95, 0.75), (1.22, 0.5), (1.95, 0.4)):
        tr.add(thump(rng, 75, 42, 0.02, 0.07, 0.3), at, g * 0.9)
    out = tr.render()
    out = reverb(out, rng, decay=1.6, mix=0.3, lp=2500)
    fade = np.ones(len(out))
    s = ns(1.6)
    fade[s:] = np.linspace(1, 0, len(out) - s) ** 2
    return out * fade


def sfx_terminal_open(rng):
    tr = Track()
    tr.add(noise_burst(rng, 1500, 8000, 0.0003, 0.003, 0.02), 0, 0.5)           # tec do CRT ligando
    n = ns(0.7)
    hum = bl_wave(120, n, "square", 700) * adsr(n, 0.08, 0.1, 0.6, 0.3)
    tr.add(hum, 0, 0.12)
    scale = [midi(m) for m in (76, 79, 81, 83, 86, 88)]
    for i in range(9):
        tr.add(chip_note(scale[rng.integers(len(scale))], 0.03, "square", 4000, decay=0.012, release=0.008),
               0.06 + 0.038 * i, 0.35)
    # acorde que fica no ar: E5 + G5 (terça menor), meio misterioso
    for m in (64, 71, 76, 79):
        x = np.sin(phase_of(midi(m), ns(0.7), rng.uniform(0, 6.28))) * adsr(ns(0.7), 0.06, 0.1, 0.8, 0.45)
        tr.add(x, 0.42, 0.18)
    out = tr.render()
    out = echo(out, 0.16, 0.25, taps=2, lp=2500)
    return reverb(out, rng, decay=0.9, mix=0.2, lp=4000)


def _footstep(rng, lo, hi, thump_f):
    n = ns(0.14)
    t = tvec(n)
    # crocância: ruído com granulação esparsa (cascalho fino sob a bota)
    grains = (rng.uniform(0, 1, n) < 0.12) * rng.standard_normal(n)
    crunch = filt(grains + 0.3 * rng.standard_normal(n), lo, hi, 2)
    env = perc(n, 0.003, 0.03) + 0.35 * perc(n, 0.03, 0.03) * (t > 0.025)
    tr = Track()
    tr.add(crunch * env, 0, 0.9)
    tr.add(thump(rng, thump_f * 1.4, thump_f, 0.01, 0.03, 0.12), 0, 0.35)
    return tr.render()


def sfx_footstep_0(rng):
    return _footstep(rng, 280, 2600, 85)


def sfx_footstep_1(rng):
    return _footstep(rng, 240, 2200, 78)


def sfx_stage_up(rng):
    """Jingle em Lá maior: I -> IV -> V -> I com a nota final segurada."""
    tr = Track()
    lead = [  # (midi, início, duração)
        (64, 0.00, 0.13), (69, 0.11, 0.13), (73, 0.22, 0.13), (76, 0.33, 0.26),
        (74, 0.62, 0.13), (78, 0.73, 0.13), (81, 0.84, 0.26),
        (80, 1.13, 0.16), (83, 1.27, 0.12),
        (85, 1.40, 1.70),
    ]
    for m, at, d in lead:
        long = d > 1
        x = chip_note(midi(m), d, "pulse", 3800, 0.3 if not long else 0.4, a=0.006, sustain=0.75,
                      release=0.9 if long else 0.05, vib=0.006 if long else 0.0, vib_delay=0.25)
        tr.add(x, at, 0.42)
        tr.add(chip_note(midi(m) * 1.003, d, "tri", 3000, a=0.006, sustain=0.75,
                         release=0.9 if long else 0.05), at, 0.18)  # dobra levemente desafinada
    bass = [(45, 0.0, 0.58), (50, 0.62, 0.5), (52, 1.13, 0.27), (45, 1.40, 1.9)]
    for m, at, d in bass:
        tr.add(chip_note(midi(m), d, "tri", 1500, a=0.008, sustain=0.85, release=0.6 if d > 1 else 0.05), at, 0.5)
    # pad do acorde final (A3 C#4 E4 A4), entrando devagar
    n = ns(2.4)
    for m in (57, 61, 64, 69):
        for det in (-0.004, 0.004):
            x = bl_wave(midi(m) * (1 + det), n, "saw", 1400, ph0=rng.uniform(0, 6.28))
            tr.add(x * adsr(n, 0.35, 0.3, 0.8, 1.2), 1.40, 0.055)
    # brilho: cascata descendente de notas agudas
    sparkle = [93, 88, 85, 81, 88, 85, 81, 76]
    for i, m in enumerate(sparkle):
        x = np.sin(phase_of(midi(m), ns(0.35))) * perc(ns(0.35), 0.002, 0.08)
        tr.add(x, 1.42 + 0.065 * i, 0.16 * (1 - i / 12))
    out = tr.render()
    out = echo(out, 0.18, 0.22, taps=3, lp=3000)
    return reverb(out, rng, decay=1.8, mix=0.28, lp=4500)


# ---------------------------------------------------------------------------
# loops
# ---------------------------------------------------------------------------

def loop_o2_low(rng):
    L = 1.1
    n = ns(L)
    buf = np.zeros(n)
    beeps = [(midi(77), 0.0, 0.12), (midi(72), 0.16, 0.2)]  # F5 -> C5, "ba-dum" descendente
    for f, at, d in beeps:
        x = chip_note(f, d, "square", 2400, a=0.008, sustain=0.8, release=0.06)
        x += 0.35 * chip_note(f / 2, d, "tri", 1200, a=0.008, sustain=0.8, release=0.06)
        add_circ(buf, x, ns(at), 0.7)
    buf = echo(buf, 0.11, 0.18, taps=2, lp=2000, circular=True)
    return reverb(buf, rng, decay=0.45, mix=0.15, lp=3500, circular=True)


def loop_machine_hum(rng):
    L = 4.0
    n = ns(L)
    t = tvec(n)
    base = 60.0  # 240 ciclos em 4 s
    hum = np.zeros(n)
    for k, a in ((1, 0.55), (2, 1.0), (3, 0.3), (4, 0.22), (6, 0.1), (8, 0.05)):
        hum += a * np.sin(2 * np.pi * base * k * t + rng.uniform(0, 6.28))
    throb = 1 + 0.12 * np.sin(2 * np.pi * (2 / L) * 4 * t)  # 2 Hz, 8 ciclos
    hum *= throb
    fan = filt(rng.standard_normal(n), 250, 1100, 2, circular=True)
    fan *= 0.8 + 0.2 * np.sin(2 * np.pi * (12 / L) * 4 * t)  # 12 Hz
    whine = np.sin(2 * np.pi * fr(1240, L) * t) * (0.5 + 0.5 * np.sin(2 * np.pi * (1 / L) * t))
    x = hum * 0.25 + fan * 0.6 * np.std(hum * 0.25) / np.std(fan) + whine * 0.004
    return filt(x, 30, 3000, 2, circular=True)


def norm_rms(x):
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)


def amb_dead(rng):
    L = 32.0
    n = ns(L)
    t = tvec(n)
    slow = periodic_ctrl(n, L, rng, 1, 7)
    g = gusts(n, rng, 5, (2.5, 5.0), 0.4)
    low = norm_rms(filt(rng.standard_normal(n), 70, 380, 2, circular=True))
    mid = norm_rms(filt(rng.standard_normal(n), 380, 1300, 2, circular=True))
    high = norm_rms(filt(rng.standard_normal(n), 1600, 5500, 2, circular=True))
    wind = (low * (0.35 + 0.45 * slow) + mid * (0.08 + 0.28 * g + 0.08 * slow) + high * (0.015 + 0.12 * g ** 1.6))
    # poeira batendo no visor: estalinhos esparsos, mais densos nas rajadas
    imp = np.zeros(n)
    cand = rng.integers(0, n, int(220 * L))
    keep = rng.uniform(0, 1, len(cand)) < (0.05 + 0.95 * g[cand] ** 2)
    imp[cand[keep]] = np.clip(rng.standard_normal(keep.sum()), -2.5, 2.5)
    grit = filt(imp, 2200, 7000, 2, circular=True)
    grit = grit / (np.std(grit) + 1e-12) * 0.06
    # drone grave e solitário: A1 + E2, com batimento lento
    drone = np.zeros(n)
    for f, a in ((55.0, 0.5), (fr(55.0 + 0.125, L), 0.35), (fr(82.41, L), 0.22), (110.0, 0.06)):
        drone += a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    drone *= 0.6 + 0.4 * periodic_ctrl(n, L, rng, 1, 3)
    drone = drone * 0.22
    # gemido metálico distante (o que sobrou da colônia), uma vez por volta
    m = ns(6.0)
    tm = tvec(m)
    groan = bl_wave(74 - 8 * tm / 6.0, m, "saw", 450) * bump(m, 0.35)
    groan = filt(groan, 50, 420, 2) * 0.05
    buf = wind * 0.5 + grit + drone
    add_circ(buf, groan, ns(19.0))
    return reverb(buf, rng, decay=2.6, mix=0.22, lp=3000, circular=True)


def amb_mist(rng):
    L = 32.0
    n = ns(L)
    t = tvec(n)
    slow = periodic_ctrl(n, L, rng, 1, 6)
    g = gusts(n, rng, 3, (4.0, 7.0), 0.45)
    low = norm_rms(filt(rng.standard_normal(n), 60, 450, 2, circular=True))
    mid = norm_rms(filt(rng.standard_normal(n), 450, 1100, 2, circular=True))
    wind = low * (0.3 + 0.3 * slow) + mid * (0.05 + 0.15 * g)
    # chuva fina: chiado + "patter" de microgotas
    rain_hiss = norm_rms(filt(rng.standard_normal(n), 2500, 9000, 2, circular=True))
    imp = np.zeros(n)
    cand = rng.integers(0, n, int(350 * L))
    imp[cand] = np.minimum(rng.exponential(1.0, len(cand)), 3.0) * rng.choice([-1, 1], len(cand))
    patter = norm_rms(filt(imp, 2000, 8000, 2, circular=True))
    rain_level = 0.7 + 0.3 * periodic_ctrl(n, L, rng, 1, 4)
    rain = (rain_hiss * 0.05 + patter * 0.07) * rain_level
    # gotas maiores pingando em poças
    drops = np.zeros(n)
    for _ in range(34):
        f0 = rng.uniform(850, 1900)
        p = plink(rng, f0) * rng.uniform(0.05, 0.16)
        st = rng.integers(0, n)
        add_circ(drops, p, st)
        if rng.uniform() < 0.4:
            add_circ(drops, plink(rng, f0 * rng.uniform(1.05, 1.25)) * 0.4 * rng.uniform(0.05, 0.12),
                     st + ns(rng.uniform(0.18, 0.45)))
    drops = echo(drops, 0.23, 0.3, taps=2, lp=3000, circular=True)
    # drone mais aberto: A2 E3 B3 (sus2), respirando
    drone = np.zeros(n)
    for f, a in ((110.0, 0.5), (fr(164.81, L), 0.35), (fr(246.94, L), 0.2), (fr(110.0 + 0.0625, L), 0.25)):
        sw = 0.5 + 0.5 * periodic_ctrl(n, L, rng, 1, 3)
        drone += a * sw * (np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
                           + 0.15 * np.sin(4 * np.pi * f * t + rng.uniform(0, 6.28)))
    drone *= 0.13
    buf = wind * 0.38 + rain + drops + drone
    return reverb(buf, rng, decay=3.0, mix=0.3, lp=3500, circular=True)


def amb_green(rng):
    L = 32.0
    n = ns(L)
    t = tvec(n)
    slow = periodic_ctrl(n, L, rng, 1, 5)
    g = gusts(n, rng, 4, (3.0, 6.0), 0.5)
    breeze = norm_rms(filt(rng.standard_normal(n), 90, 650, 2, circular=True)) * (0.25 + 0.25 * slow)
    leaves = norm_rms(filt(rng.standard_normal(n), 1800, 6000, 2, circular=True)) * (0.01 + 0.05 * g ** 1.5)
    # pad: alterna A add9 <-> D maj7 (notas em comum = transição lisa)
    w = 0.5 + 0.5 * np.cos(2 * np.pi * t / L)
    chords = [
        (w, (45, 52, 57, 61, 64, 71)),        # A2 E3 A3 C#4 E4 B4
        (1 - w, (50, 57, 61, 66, 69, 73)),    # D3 A3 C#4 F#4 A4 C#5
    ]
    pad = np.zeros(n)
    for weight, notes in chords:
        for m in notes:
            f = midi(m)
            amp = (1.0 if m < 60 else 0.6) * (0.55 + 0.45 * periodic_ctrl(n, L, rng, 1, 3))
            v = np.zeros(n)
            for det in (-0.25, 0.0, 0.25):
                fd = fr(f + det, L)
                v += np.sin(2 * np.pi * fd * t + rng.uniform(0, 6.28))
                v += 0.18 * np.sin(4 * np.pi * fd * t + rng.uniform(0, 6.28))
            pad += weight * amp * v
    pad = filt(pad, 60, 1800, 1, circular=True)
    pad = norm_rms(pad) * 0.09
    # insetos alienígenas: trilos pulsados em frases curtas
    bugs = np.zeros(n)
    for _ in range(9):
        d = rng.uniform(1.2, 2.8)
        m = ns(d)
        tm = tvec(m)
        fc = rng.choice([3900.0, 4400.0, 3300.0])
        rate = rng.uniform(16, 26)
        gate = (0.5 - 0.5 * np.cos(2 * np.pi * rate * tm)) ** 4
        group = (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(1.5, 3.0) * tm)) ** 2
        x = np.sin(2 * np.pi * fc * tm + 0.4 * np.sin(2 * np.pi * 40 * tm)) * gate * group * bump(m, 0.3)
        add_circ(bugs, x * rng.uniform(0.012, 0.025), rng.integers(0, n))
    # pássaros alienígenas: frases de 2-4 notas com glissando e vibrato
    birds = np.zeros(n)
    for _ in range(7):
        st = rng.integers(0, n)
        f0 = rng.uniform(1500, 2600)
        glide = rng.choice([0.35, -0.25, 0.5])
        pos = 0
        for k in range(int(rng.integers(2, 5))):
            d = rng.uniform(0.07, 0.15)
            m = ns(d)
            tm = tvec(m)
            f = f0 * (1 + glide * tm / d) * (1 + 0.03 * np.sin(2 * np.pi * 28 * tm))
            ph = phase_of(f, m)
            x = (np.sin(ph) + 0.15 * np.sin(2 * ph)) * bump(m, 0.15)
            add_circ(birds, x * rng.uniform(0.05, 0.08), st + pos)
            pos += m + ns(rng.uniform(0.04, 0.09))
            f0 *= rng.uniform(0.9, 1.15)
    birds = echo(birds, 0.27, 0.28, taps=2, lp=3500, circular=True)
    buf = breeze * 0.35 + leaves + pad + bugs + birds
    return reverb(buf, rng, decay=2.2, mix=0.25, lp=4500, circular=True)


# ---------------------------------------------------------------------------
# masterização, medição e escrita
# ---------------------------------------------------------------------------

def weighting(x: np.ndarray, circular: bool) -> np.ndarray:
    """Ponderação aproximada estilo K-weighting (passa-alta + shelf de agudos)."""
    n = len(x)
    N = n if circular else n + ns(0.1)
    f = np.fft.rfftfreq(N, 1 / SR)
    H = bw_mag(f, 60, None, 2) * (1 + (10 ** (4 / 20) - 1) * f ** 2 / (f ** 2 + 1500 ** 2))
    return np.fft.irfft(np.fft.rfft(x, N) * H, N)[:n]


def loudness(x: np.ndarray, loop: bool) -> float:
    """dB de energia ponderada. sfx: máximo em janela de 400 ms (tipo LUFS momentâneo).
    loops: média do arquivo todo (tipo LUFS integrado). É aproximação, não LUFS certificado."""
    w = weighting(x, loop)
    if loop:
        return 10 * np.log10(np.mean(w ** 2) + 1e-20)
    win = ns(0.4)
    p = np.concatenate([w ** 2, np.zeros(win)])
    c = np.concatenate([[0], np.cumsum(p)])
    ms = (c[win:] - c[:-win]) / win
    return 10 * np.log10(ms.max() + 1e-20)


SOUNDS = {
    # nome: (função, loop?, alvo de loudness dB)
    "mine_hit": (sfx_mine_hit, False, -22.0),
    "mine_break": (sfx_mine_break, False, -17.0),
    "pickup": (sfx_pickup, False, -20.0),
    "craft": (sfx_craft, False, -17.0),
    "place": (sfx_place, False, -17.0),
    "ui_open": (sfx_ui_open, False, -22.0),
    "ui_close": (sfx_ui_close, False, -22.0),
    "ui_click": (sfx_ui_click, False, -25.0),
    "o2_low": (loop_o2_low, True, -21.0),
    "o2_refill": (sfx_o2_refill, False, -18.0),
    "faint": (sfx_faint, False, -17.0),
    "terminal_open": (sfx_terminal_open, False, -19.0),
    "stage_up": (sfx_stage_up, False, -14.0),
    "footstep_0": (sfx_footstep_0, False, -27.0),
    "footstep_1": (sfx_footstep_1, False, -27.0),
    "machine_hum": (loop_machine_hum, True, -30.0),
    "amb_dead": (amb_dead, True, -27.0),
    "amb_mist": (amb_mist, True, -27.0),
    "amb_green": (amb_green, True, -27.0),
}


def finalize(x: np.ndarray, loop: bool, target: float) -> np.ndarray:
    if loop:
        x = x - x.mean()  # tira DC sem quebrar a periodicidade
        # saturação suave sem memória: segura picos isolados (gota/estalo) a ~15 dB
        # acima do RMS e, por ser amostra a amostra, mantém o loop periódico
        c = np.sqrt(np.mean(x ** 2)) * 10 ** (15 / 20)
        if np.max(np.abs(x)) > c:
            x = c * np.tanh(x / c)
    else:
        x = filt(x, 25, None, 2)  # tira DC/subgrave
        # corta cauda silenciosa e faz fade-out curto pra terminar em zero
        thr = np.max(np.abs(x)) * 10 ** (-62 / 20)
        last = np.nonzero(np.abs(x) > thr)[0][-1]
        x = x[: last + ns(0.01)]
        fo = min(ns(0.012), len(x) // 4)
        x[-fo:] *= np.linspace(1, 0, fo)
        x[0] = 0.0
    x = x * 10 ** ((target - loudness(x, loop)) / 20)
    peak = np.max(np.abs(x))
    if peak > CEILING:
        x = x * (CEILING / peak)
    return x


def write_wav(path: Path, x: np.ndarray) -> np.ndarray:
    xi = np.round(np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(xi.tobytes())
    return xi


def waveform_peaks(xi: np.ndarray, bins: int = 160) -> list[float]:
    x = np.abs(xi.astype(float)) / 32768
    edges = np.linspace(0, len(x), bins + 1).astype(int)
    return [round(float(x[a:b].max()) if b > a else 0.0, 3) for a, b in zip(edges[:-1], edges[1:])]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    print(f"{'arquivo':<20}{'dur(s)':>8}{'pico dBFS':>11}{'loud dB':>9}")
    for name, (fn, loop, target) in SOUNDS.items():
        x = finalize(fn(rng_for(name)), loop, target)
        xi = write_wav(OUT_DIR / f"{name}.wav", x)
        xf = xi.astype(float) / 32768
        peak_db = 20 * np.log10(np.max(np.abs(xf)) + 1e-12)
        loud = loudness(xf, loop)
        meta[name] = {
            "file": f"{name}.wav",
            "loop": loop,
            "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(peak_db), 2),
            "loudness_db": round(float(loud), 1),
            "wave": waveform_peaks(xi),
        }
        if loop:
            adj = np.abs(np.diff(xi.astype(int)))
            jump = abs(int(xi[0]) - int(xi[-1]))
            meta[name]["seam_lsb"] = jump
            meta[name]["seam_pct"] = round(float(100 * np.mean(adj < jump)), 1)
        print(f"{name + '.wav':<20}{len(xi) / SR:>8.2f}{peak_db:>11.2f}{loud:>9.1f}")
    (REPORT_DIR / "audio_meta.js").write_text(
        "// gerado por tools/audio/build_audio.py, não editar\nwindow.AUDIO_META = "
        + json.dumps(meta, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"ok: {len(meta)} arquivos em {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
