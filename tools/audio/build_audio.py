"""Gera todos os sons do Hesper por síntese procedural.

Uso:  python3 tools/audio/build_audio.py

Saída: assets/audio/*.wav (44,1 kHz, 16-bit, mono) e reports/audio/audio_meta.js
(duração, pico, loudness e forma de onda de cada arquivo, usado pelo report).

Só depende de numpy. Tudo é determinístico: cada som tem a própria seed derivada
de BASE_SEED + nome, então mexer em um som não muda os outros.

Loops (o2_low, machine_hum, amb_*) são construídos de forma periódica: todo ruído
é filtrado no domínio da frequência de forma circular, toda frequência fixa tem um
número inteiro de ciclos no comprimento do loop, eventos (brilhos, gotas)
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

def soft_sat(x: np.ndarray, drive: float) -> np.ndarray:
    """Saturação suave (tanh) pra domar o pico de transientes de ruído. Em sinal
    só de ruído não cria tom nenhum, só segura o pico e deixa o corpo aparecer."""
    x = x / np.max(np.abs(x))
    return np.tanh(drive * x) / np.tanh(drive)


def sfx_mine_hit(rng):
    """v3: ferramenta batendo em pedra, "tchk" seco. Só ruído com filtros de banda
    larga (Q baixo, sem ressonância): nada de seno, nada de grave com pitch."""
    tr = Track()
    tr.add(noise_burst(rng, 2000, 8000, 0.0002, 0.0005, 0.004, order=1), 0, 0.7)        # clique 1-2 ms
    tr.add(noise_burst(rng, 1000, 5000, 0.0004, 0.011, 0.06, order=2), 0, 0.8)          # rajada 1-5 kHz
    tr.add(noise_burst(rng, 600, 1500, 0.0004, 0.005, 0.03, order=1), 0, 0.7)          # "toc" pétreo amortecido
    for _ in range(int(rng.integers(2, 4))):                                            # lascas
        tr.add(noise_burst(rng, 1500, 6000, 0.0002, rng.uniform(0.0012, 0.0025), 0.012, order=2),
               rng.uniform(0.014, 0.045), rng.uniform(0.2, 0.35))
    return soft_sat(tr.render(), 2.0)


def sfx_mine_break(rng):
    """v3: rocha se partindo e desmoronando em chão de terra. Zero componente tonal:
    só ruído com filtros de 1ª ordem (Q baixo), cortes aleatórios por grão."""
    tr = Track()
    tr.add(noise_burst(rng, 300, 10000, 0.0002, 0.003, 0.02, order=1), 0, 0.45)          # estalo da rachadura
    tr.add(noise_burst(rng, None, 350, 0.002, 0.04, 0.22, order=2), 0.002, 1.6)         # baque surdo do bloco
    for _ in range(5):                                                                  # pedaços maiores
        hi = rng.uniform(600, 1500)
        tr.add(noise_burst(rng, hi / 5, hi, 0.0005, rng.uniform(0.008, 0.015), 0.06, order=1),
               rng.uniform(0.02, 0.14), rng.uniform(0.6, 0.9))
    t = 0.015
    while True:                                                                         # entulho caindo
        t += rng.exponential(1 / (160 * np.exp(-t / 0.15) + 10))
        if t > 0.6:
            break
        hi = rng.uniform(800, 4000)
        amp = np.exp(-t / 0.2) * rng.uniform(0.3, 0.9)
        tr.add(noise_burst(rng, hi / 4, hi, 0.0003, rng.uniform(0.0015, 0.006), 0.025, order=1), t, amp)
    n = ns(0.6)                                                                         # rabo de poeira
    dust = filt(rng.standard_normal(n), 300, 3000, 1) * np.minimum(1, tvec(n) / 0.03) * np.exp(-tvec(n) / 0.25)
    tr.add(dust, 0.02, 0.035)
    return reverb(soft_sat(tr.render(), 2.5), rng, decay=0.3, mix=0.1, lp=4000)


def sfx_pickup(rng):
    """v2: "poop" de bolha. Seno com subida rápida de pitch, ~110 ms, sem arpejo."""
    n = ns(0.11)
    t = tvec(n)
    f = 330 + 420 * (1 - np.exp(-t / 0.025))
    ph = phase_of(f, n)
    x = (np.sin(ph) + 0.12 * np.sin(2 * ph)) * perc(n, 0.002, 0.03)
    return x * np.clip((n / SR - t) / 0.02, 0, 1)


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


# v2: ambientes "espaciais". O protagonista é o drone/pad com reverb longo e brilhos
# agudos lentos; textura de ruído só bem baixa e escura, no fundo. Sem bichos.

def pad_voice(n: int, L: float, rng, f: float, detune=(-0.19, 0.0, 0.19),
              harm=(1.0, 0.12, 0.04), swell=(1, 3)) -> np.ndarray:
    """Voz de pad periódica: senoides levemente desafinadas (chorus) + poucos harmônicos,
    respirando com swell lento. Toda frequência tem ciclos inteiros em L."""
    t = tvec(n)
    v = np.zeros(n)
    for d in detune:
        fd = fr(f + d, L)
        for k, a in enumerate(harm, 1):
            v += a * np.sin(2 * np.pi * k * fd * t + rng.uniform(0, 2 * np.pi))
    return v * (0.4 + 0.6 * periodic_ctrl(n, L, rng, *swell)) / len(detune)


def glints(n: int, rng, notes, count: int, dur=(2.5, 5.0), amp=(0.2, 0.35)) -> np.ndarray:
    """Brilhos: notas agudas que surgem e somem devagar (pro reverb espalhar)."""
    buf = np.zeros(n)
    for _ in range(count):
        f = midi(float(rng.choice(notes)))
        m = ns(rng.uniform(*dur))
        tm = tvec(m)
        wob = 1 + 0.002 * np.sin(2 * np.pi * 4.5 * tm)
        ph = phase_of(f * wob, m)
        x = np.sin(ph) + 0.15 * np.sin(2 * ph) + 0.5 * np.sin(phase_of(f * 1.003 * wob, m, 1.0))
        add_circ(buf, x * bump(m, 0.4) ** 1.5 * rng.uniform(*amp), int(rng.integers(0, n)))
    return buf


def space_mix(rng, pad, shimmer, texture, pad_rev=(6.0, 0.45, 2800), sh_rev=(7.5, 0.8, 6000)):
    pad = reverb(pad, rng, decay=pad_rev[0], mix=pad_rev[1], lp=pad_rev[2], circular=True)
    shimmer = reverb(shimmer, rng, decay=sh_rev[0], mix=sh_rev[1], lp=sh_rev[2], circular=True)
    return pad + shimmer + texture


def amb_dead(rng):
    """Frio, vazio, grave: quinta vazia em Lá bem embaixo, brilhos raros e gelados."""
    L = 32.0
    n = ns(L)
    t = tvec(n)
    drone = sum(g * pad_voice(n, L, rng, midi(m), detune=(-0.125, 0.0, 0.125), harm=(1.0, 0.2, 0.06))
                for m, g in ((33, 0.45), (40, 0.5), (45, 1.0), (52, 0.45)))  # A1 E2 A2 E3
    cold = sum(pad_voice(n, L, rng, midi(m), harm=(1.0,), swell=(2, 4)) for m in (57, 64)) * 0.25  # A3 E4 fino
    pad = norm_rms(drone + cold)
    shimmer = glints(n, rng, (76, 81, 88), 5, (3.0, 6.0), (0.2, 0.35))     # E5 A5 E6
    # o que sobrou da colônia: gemido metálico distante, uma vez por volta
    m = ns(6.0)
    groan = filt(bl_wave(74 - 8 * tvec(m) / 6.0, m, "saw", 450) * bump(m, 0.35), 50, 380, 2) * 0.25
    add_circ(shimmer, groan, ns(19.0))
    rumble = norm_rms(filt(rng.standard_normal(n), 25, 180, 2, circular=True))
    rumble *= 0.07 * (0.5 + 0.5 * periodic_ctrl(n, L, rng, 1, 4))
    return space_mix(rng, pad, shimmer, rumble, pad_rev=(6.0, 0.4, 2200))


def amb_mist(rng):
    """Abre e fica úmido: sus2 uma oitava acima, mais brilho, gotas raras e discretas."""
    L = 32.0
    n = ns(L)
    pad = sum(g * pad_voice(n, L, rng, midi(m), harm=(1.0, 0.1), swell=(1, 3))
              for m, g in ((45, 1.0), (52, 0.7), (59, 0.45), (64, 0.3)))   # A2 E3 B3 E4
    pad = norm_rms(pad)
    shimmer = glints(n, rng, (71, 76, 78, 83), 8, (3.0, 6.0), (0.22, 0.38))  # B4 E5 F#5 B5
    drops = np.zeros(n)
    for _ in range(6):
        p = filt(plink(rng, rng.uniform(800, 1400), 0.08), None, 2500, 1)
        add_circ(drops, p * rng.uniform(0.08, 0.14), int(rng.integers(0, n)))
    shimmer += echo(drops, 0.37, 0.35, taps=3, lp=2000, circular=True)
    mist = norm_rms(filt(rng.standard_normal(n), 40, 300, 2, circular=True))
    mist *= 0.05 * (0.5 + 0.5 * periodic_ctrl(n, L, rng, 1, 3))
    return space_mix(rng, pad, shimmer, mist, pad_rev=(7.0, 0.5, 3000))


def amb_green(rng):
    """Quente e aberto: pad em Lá maior (A add9 <-> D maj7) e brilhos nas notas do acorde."""
    L = 32.0
    n = ns(L)
    t = tvec(n)
    w = 0.5 + 0.5 * np.cos(2 * np.pi * t / L)
    chords = [
        (w, (33, 45, 52, 57, 61, 64, 71)),        # A1 A2 E3 A3 C#4 E4 B4
        (1 - w, (38, 50, 57, 61, 66, 69, 73)),    # D2 D3 A3 C#4 F#4 A4 C#5
    ]
    pad = np.zeros(n)
    for weight, notes in chords:
        for m in notes:
            g = 0.8 if m < 40 else (1.0 if m < 60 else 0.55)
            pad += weight * g * pad_voice(n, L, rng, midi(m), harm=(1.0, 0.18, 0.06), swell=(1, 3))
    pad = norm_rms(filt(pad, 40, 2200, 1, circular=True))
    shimmer = glints(n, rng, (73, 76, 81, 83, 85, 88), 11, (2.5, 5.0), (0.22, 0.4))
    air = norm_rms(filt(rng.standard_normal(n), 60, 400, 2, circular=True))
    air *= 0.04 * (0.5 + 0.5 * periodic_ctrl(n, L, rng, 1, 3))
    return space_mix(rng, pad, shimmer, air, pad_rev=(5.5, 0.45, 3200))


# ---------------------------------------------------------------------------
# v5: drill automática
# ---------------------------------------------------------------------------

def loop_drill(rng):
    """Motor elétrico grave e estável + rosca raspando pedra a 2,5 voltas/s.
    Periódico em L = 3,2 s (8 voltas): frequências com ciclos inteiros, ruído
    filtrado de forma circular e grãos de pedra que dão a volta no começo."""
    L = 3.2
    n = ns(L)
    t = tvec(n)
    rot = 2.5                                                    # voltas por segundo (8 em L)
    # motor: fundamental grave com poucos harmônicos e um leve "ronco" na rotação
    motor = np.zeros(n)
    for k, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1), (6, 0.04)):
        motor += a * np.sin(2 * np.pi * fr(82.5 * k, L) * t + rng.uniform(0, 2 * np.pi))
    motor *= 1 + 0.06 * np.sin(2 * np.pi * rot * t)
    motor = norm_rms(motor)
    # rosca raspando: ruído médio, banda larga, que incha uma vez por volta
    turn = (0.5 - 0.5 * np.cos(2 * np.pi * rot * t)) ** 2
    scrape = norm_rms(filt(rng.standard_normal(n), 350, 2200, 2, circular=True)) * (0.25 + 0.75 * turn)
    # pedrinhas sendo moídas: grãos curtos, mais densos no pico de cada volta
    grains = np.zeros(n)
    for c in range(8):
        for _ in range(int(rng.integers(5, 9))):
            at = (c + 0.5 + rng.normal(0, 0.12)) / rot
            hi = rng.uniform(700, 2800)
            g = noise_burst(rng, hi / 4, hi, 0.0005, rng.uniform(0.002, 0.006), 0.02, order=1)
            add_circ(grains, g * rng.uniform(0.3, 1.0), ns(at) % n)
    grains = norm_rms(grains)
    rumble = norm_rms(filt(rng.standard_normal(n), 30, 220, 2, circular=True))
    x = motor * 0.5 + scrape * 0.32 + grains * 0.22 + rumble * 0.25
    return filt(x, 35, 4000, 2, circular=True)


def sfx_drill_collect(rng):
    """Clique da trava, despejo de pedrinhas/minério num coletor e o "poop" da coleta."""
    tr = Track()
    tr.add(noise_burst(rng, 1500, 6000, 0.0002, 0.0015, 0.01, order=1), 0, 0.6)       # trava abrindo
    tr.add(noise_burst(rng, None, 450, 0.001, 0.012, 0.06, order=2), 0.002, 0.5)      # tranco mecânico
    tr.add(noise_burst(rng, 1500, 6000, 0.0002, 0.0012, 0.01, order=1), 0.045, 0.35)  # segundo clique
    t = 0.06                                                                          # despejo
    while True:
        u = (t - 0.06) / 0.34
        t += rng.exponential(1 / (20 + 220 * np.sin(np.pi * min(u, 1)) ** 1.5))
        if t > 0.42:
            break
        hi = rng.uniform(800, 4000)
        env = np.sin(np.pi * min((t - 0.06) / 0.36, 1)) ** 0.7
        tr.add(noise_burst(rng, hi / 4, hi, 0.0003, rng.uniform(0.0015, 0.005), 0.025, order=1),
               t, 0.5 * env * rng.uniform(0.3, 1.0))
    n = ns(0.36)
    pile = filt(rng.standard_normal(n), 80, 600, 2) * bump(n, 0.3)                    # monte assentando
    tr.add(pile, 0.07, 0.12)
    tr.add(sfx_pickup(rng), 0.4, 0.45)                                                 # recompensa
    return reverb(tr.render(), rng, decay=0.3, mix=0.1, lp=4000)


def sfx_drill_full(rng):
    """Dois bipes suaves subindo, Mi5 -> Lá5. Seno com um tico de triângulo."""
    tr = Track()
    for m, at in ((76, 0.0), (81, 0.13)):
        f = midi(m)
        nn = ns(0.22)
        x = np.sin(phase_of(f, nn)) + 0.25 * bl_wave(f, nn, "tri", 3000)
        tr.add(x * perc(nn, 0.008, 0.06) * np.clip((0.22 - tvec(nn)) / 0.05, 0, 1), at, 0.6)
    return reverb(echo(tr.render(), 0.16, 0.18, taps=2, lp=2500), rng, decay=0.6, mix=0.15, lp=4000)


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
    "pickup": (sfx_pickup, False, -23.0),
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
    "drill_loop": (loop_drill, True, -29.0),
    "drill_collect": (sfx_drill_collect, False, -19.0),
    "drill_full": (sfx_drill_full, False, -27.0),
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


# ---------------------------------------------------------------------------
# v4: candidatas pro som de mineração (o dono escolhe no report)
# ---------------------------------------------------------------------------

CAND_DIR = OUT_DIR / "candidates"
VENDOR = Path(__file__).resolve().parent / "vendor" / "kenney_impact" / "Audio"


def rock_hit(rng, body=(300, 2000), body_decay=0.018, grains=30, spread=0.025, crumble=6,
             low=0.3, bright=6000.0):
    """Impacto de pedra: "toc/crack" de ruído com corpo médio (banda larga, sem tom),
    rajada de microestalos sobrepostos e um pedrisco curto esmigalhando depois."""
    tr = Track()
    tr.add(noise_burst(rng, 1500, bright + 1000, 0.0002, 0.0018, 0.012, order=1), 0, 0.45)   # crack
    tr.add(noise_burst(rng, body[0], body[1], 0.0005, body_decay, 0.09, order=2), 0, 1.0)     # corpo médio
    tr.add(noise_burst(rng, None, 420, 0.001, 0.014, 0.07, order=2), 0, low)                  # peso (ruído, não seno)
    for _ in range(grains):                                                                   # microestalos
        at = float(rng.gamma(1.5, spread / 3))
        hi = rng.uniform(1200, bright)
        tr.add(noise_burst(rng, hi / 4, hi, 0.0002, rng.uniform(0.0005, 0.002), 0.008, order=1),
               at, rng.uniform(0.1, 0.35) * np.exp(-at / 0.03))
    for _ in range(crumble):                                                                  # pedrisco
        at = rng.uniform(0.035, 0.13)
        hi = rng.uniform(1000, 4000)
        tr.add(noise_burst(rng, hi / 4, hi, 0.0003, rng.uniform(0.0015, 0.004), 0.015, order=1),
               at, rng.uniform(0.08, 0.2) * np.exp(-(at - 0.035) / 0.06))
    return soft_sat(reverb(tr.render(), rng, decay=0.15, mix=0.08, lp=3500), 2.0)


def cand_A1(rng):
    return rock_hit(rng)


def cand_A2(rng):
    return rock_hit(rng, body=(250, 1500), body_decay=0.025, grains=40, crumble=9, low=0.45, bright=4500)


def cand_A3(rng):
    return rock_hit(rng, body=(400, 2500), body_decay=0.012, grains=22, spread=0.015, crumble=4,
                    low=0.2, bright=7000)


def kenney(file: str):
    """Decodifica um .ogg do pack do Kenney (CC0) pra mono 44,1 kHz via ffmpeg.
    Se o pack ou o ffmpeg não existirem, devolve None e a candidata é pulada."""
    import shutil
    import subprocess
    p = VENDOR / f"{file}.ogg"
    if not p.exists() or not shutil.which("ffmpeg"):
        return None
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<i2").astype(float) / 32768


def kenney_cut(file: str, trim: float, hp=None):
    x = kenney(file)
    if x is None:
        return None
    x = x[: ns(trim)].copy()
    if hp:
        x = filt(x, hp, None, 2)
    fo = ns(0.04)
    x[-fo:] *= np.linspace(1, 0, fo) ** 2
    return x


def cand_B1(rng):
    return kenney_cut("impactMining_001", 0.28, hp=40)


def cand_B2(rng):
    return kenney_cut("impactMining_004", 0.25, hp=180)


def cand_B3(rng):
    return kenney_cut("impactMining_002", 0.25, hp=100)


def cand_break_B1(rng):
    k = kenney_cut("impactMining_003", 0.55, hp=40)
    if k is None:
        return None
    tr = Track()
    tr.add(k, 0, 1.0)
    tr.add(sfx_mine_break(rng_for("mine_break")), 0.01, 0.6)
    return tr.render()


CANDIDATES = {
    # nome: (função, alvo de loudness)
    "mine_hit_A1": (cand_A1, -22.0),
    "mine_hit_A2": (cand_A2, -22.0),
    "mine_hit_A3": (cand_A3, -22.0),
    "mine_hit_B1": (cand_B1, -22.0),
    "mine_hit_B2": (cand_B2, -22.0),
    "mine_hit_B3": (cand_B3, -22.0),
    "mine_break_B1": (cand_break_B1, -17.0),
}


# ---------------------------------------------------------------------------
# v6 (v0.2): sons novos, entregues em assets/audio/_pending/ até o dono aprovar
# ---------------------------------------------------------------------------

PENDING_DIR = OUT_DIR / "_pending"


def noise_sweep(rng, dur: float, lo_start: float, lo_end: float, width: float = 2.5) -> np.ndarray:
    """Ruído cuja banda "anda" de lo_start pra lo_end (crossfade entre 4 bandas largas).
    Serve de dobradiça/ar sem nenhum modo ressonante."""
    n = ns(dur)
    x = np.linspace(0, 1, n)
    centers = np.geomspace(lo_start, lo_end, 4)
    out = np.zeros(n)
    for i, c in enumerate(centers):
        w = np.clip(1 - np.abs(x * 3 - i), 0, 1)
        out += filt(rng.standard_normal(n), c, c * width, 1) * w
    return out


def sfx_chest_open(rng):
    tr = Track()
    tr.add(noise_burst(rng, 1500, 5000, 0.0002, 0.0015, 0.01, order=2), 0, 0.4)         # trava soltando
    tr.add(noise_burst(rng, 120, 700, 0.001, 0.016, 0.08, order=2), 0.003, 0.7)         # tranco macio
    n = ns(0.22)
    tr.add(filt(rng.standard_normal(n), 1200, 4500, 2) * bump(n, 0.12) ** 1.5, 0.03, 0.14)  # pssh
    n = ns(0.3)
    tr.add(noise_sweep(rng, 0.3, 500, 1400) * bump(n, 0.3), 0.08, 0.2)                  # dobradiça abrindo
    tr.add(noise_burst(rng, None, 350, 0.004, 0.02, 0.08, order=2), 0.36, 0.25)         # tampa no batente
    return reverb(tr.render(), rng, decay=0.3, mix=0.1, lp=4000)


def sfx_chest_close(rng):
    tr = Track()
    n = ns(0.25)
    tr.add(noise_sweep(rng, 0.25, 1300, 450) * bump(n, 0.4), 0, 0.16)                   # dobradiça fechando
    tr.add(noise_burst(rng, 120, 700, 0.001, 0.02, 0.1, order=2), 0.24, 0.8)             # tampa assentando
    tr.add(noise_burst(rng, 1500, 5000, 0.0002, 0.0015, 0.01, order=2), 0.25, 0.35)     # trava
    n = ns(0.16)
    tr.add(filt(rng.standard_normal(n), 1200, 4500, 2) * bump(n, 0.1) ** 1.5, 0.26, 0.1)   # pssh vedando
    return reverb(tr.render(), rng, decay=0.3, mix=0.1, lp=4000)


def sfx_inv_move(rng):
    tr = Track()
    tr.add(noise_burst(rng, 600, 2200, 0.0003, 0.004, 0.025, order=2), 0, 1.0)          # tok
    tr.add(noise_burst(rng, 2000, 6000, 0.0002, 0.0008, 0.006, order=1), 0, 0.3)        # cliquezinho
    return tr.render()


def sfx_inv_full(rng):
    n = ns(0.16)
    t = tvec(n)
    f = midi(76) * 2 ** (-(7 / 12) * np.clip(t / 0.1, 0, 1))                           # Mi5 desliza pra Lá4
    x = np.sin(phase_of(f, n)) + 0.2 * bl_wave(f, n, "tri", 2500)
    x *= adsr(n, 0.006, 0.05, 0.6, 0.06)
    return echo(x, 0.09, 0.15, taps=1, lp=2000)


def sfx_power_low(rng):
    tr = Track()
    n = ns(1.1)
    t = tvec(n)
    f = 55 + 165 * np.exp(-t / 0.35)                                                   # motor perdendo força
    motor = bl_wave(f, n, "saw", 900) * np.exp(-t / 0.45) * np.minimum(1, t / 0.02)
    tr.add(filt(motor, 40, 1200, 1), 0, 0.5)
    air = noise_sweep(rng, 0.9, 1200, 200) * np.exp(-tvec(ns(0.9)) / 0.3)
    tr.add(air, 0, 0.12)
    for at in (0.55, 0.75):                                                            # bipe duplo baixo, Lá4
        tr.add(chip_note(midi(69), 0.12, "square", 1800, a=0.008, sustain=0.7, release=0.05), at, 0.22)
    return reverb(tr.render(), rng, decay=0.7, mix=0.15, lp=3500)


def loop_solar_hum(rng):
    L = 4.0
    n = ns(L)
    t = tvec(n)
    hum = (np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t + 1.0)
           + 0.15 * np.sin(2 * np.pi * 300 * t + 2.0))
    hum *= 1 + 0.08 * np.sin(2 * np.pi * (1 / L) * t)
    air = norm_rms(filt(rng.standard_normal(n), 900, 3000, 2, circular=True))
    air *= 0.5 + 0.5 * periodic_ctrl(n, L, rng, 1, 3)
    whine = np.sin(2 * np.pi * fr(2400, L) * t) * (0.5 + 0.5 * np.sin(2 * np.pi * (2 / L) * t))
    return norm_rms(hum) + air * 0.08 + whine * 0.03


def loop_drone(rng):
    """Dois rotores pequenos com rotações próximas (batimento leve), passa-baixa
    pra tirar a parte irritante do zumbido e um balanço lento de quem paira."""
    L = 4.0
    n = ns(L)
    t = tvec(n)
    out = np.zeros(n)
    for f0, g in ((fr(172.0, L), 1.0), (fr(178.5, L), 0.8)):
        ph = 2 * np.pi * f0 * t + rng.uniform(0, 2 * np.pi)
        buzz = sum(np.sin(k * ph) / k ** 1.3 for k in range(1, 12))
        out += g * buzz
    out = filt(out, 120, 1800, 1, circular=True)
    wash = filt(rng.standard_normal(n), 300, 1800, 2, circular=True)
    blade = 0.6 + 0.4 * np.sin(2 * np.pi * fr(172.0, L) * t) ** 2                       # ar cortado pela pá
    x = norm_rms(out) + norm_rms(wash * blade) * 0.45
    return x * (1 + 0.12 * np.sin(2 * np.pi * (2 / L) * t))


def sfx_drone_deliver(rng):
    tr = Track()
    tr.add(noise_burst(rng, 1200, 5000, 0.0002, 0.002, 0.012, order=1), 0, 0.5)        # garra soltando
    n = ns(0.12)
    tr.add(filt(rng.standard_normal(n), 2500, 7000, 1) * bump(n, 0.1) ** 1.5, 0.01, 0.15)   # pssh curto
    t = 0.09                                                                          # carga caindo (mais curto
    while True:                                                                       # e agudo que a drill)
        u = (t - 0.09) / 0.22
        t += rng.exponential(1 / (20 + 180 * np.sin(np.pi * min(u, 1)) ** 1.5))
        if t > 0.32:
            break
        hi = rng.uniform(1200, 4500)
        env = np.sin(np.pi * min((t - 0.09) / 0.24, 1)) ** 0.7
        tr.add(noise_burst(rng, hi / 4, hi, 0.0003, rng.uniform(0.0012, 0.004), 0.02, order=1),
               t, 0.45 * env * rng.uniform(0.3, 1.0))
    tr.add(noise_burst(rng, None, 450, 0.002, 0.03, 0.12, order=2), 0.1, 0.35)         # carga batendo no coletor
    for m, at in ((81, 0.4), (88, 0.47)):                                              # confirmação: Lá5, Mi6
        nn = ns(0.12)
        x = np.sin(phase_of(midi(m), nn)) * perc(nn, 0.004, 0.035)
        tr.add(x, at, 0.3)
    return reverb(tr.render(), rng, decay=0.35, mix=0.12, lp=4000)


def sfx_save(rng):
    """Chime em Lá maior: Lá5, Dó#6, Mi6 dedilhados, timbre de sino macio (parciais harmônicos)."""
    tr = Track()
    for i, m in enumerate((81, 85, 88)):
        nn = ns(0.9)
        f = midi(m)
        ph = phase_of(f, nn)
        x = np.sin(ph) + 0.18 * np.sin(2 * ph) * np.exp(-tvec(nn) / 0.15) + 0.06 * np.sin(3 * ph)
        tr.add(x * perc(nn, 0.004, 0.28), 0.07 * i, 0.32)
    out = echo(tr.render(), 0.19, 0.2, taps=2, lp=3000)
    return reverb(out, rng, decay=1.0, mix=0.2, lp=5000)


# ---------------------------------------------------------------------------
# v7 (v0.3 · Marco 1 · Superfície): vento do deserto
# ---------------------------------------------------------------------------

def loop_desert_wind(rng):
    """Vento seco e espaçoso, camada baixíssima por cima do amb_{stage} na superfície.

    Sem ruído branco chapado: o ruído é dividido em 6 bandas largas (filtros de ordem 1-2,
    nada de Q alto, então nenhum tom/assobio) e o peso de cada banda segue curvas lentas
    e periódicas, o que faz o "filtro" do vento passear. As rajadas (lentas, 4-9 s) sobem
    o volume e puxam o peso pras bandas de cima, como vento que aperta e clareia.
    Quase tudo abaixo de 1,5 kHz; areia/chiado acima de 2,5 kHz só um fio.
    Periódico em L = 36 s (não bate com os 32 s dos ambientes, então a mistura não
    se repete igual). Ruído circular, controles periódicos, rajadas com add_circ e
    reverb circular: emenda exata, sem crossfade."""
    L = 36.0
    n = ns(L)
    # rajadas lentas e esparsas + respiração de fundo
    g = gusts(n, rng, 5, (4.0, 9.0), rise=0.45)
    g = filt(g, None, 0.5, 1, circular=True)                         # sem quina no envelope
    base = periodic_ctrl(n, L, rng, 1, 4)                           # maré lenta
    level = 0.35 + 0.25 * base + 0.55 * g
    # turbulência: oscilação de 0,2-0,8 Hz por cima, bem sutil
    turb = periodic_ctrl(n, L, rng, 8, 28, tilt=0.6)
    level *= 0.85 + 0.15 * turb
    bright = np.clip(0.25 * base + 0.85 * g, 0, 1)                 # 0 = escuro, 1 = claro
    bands = [  # (lo, hi, ordem, ganho, quanto depende do "bright")
        (40, 110, 2, 0.55, -0.4),
        (90, 220, 2, 0.75, -0.2),
        (180, 420, 1, 0.70, 0.0),
        (350, 800, 1, 0.50, 0.4),
        (700, 1500, 1, 0.30, 0.8),
        (1400, 3200, 1, 0.025, 1.0),  # areia fininha, quase nada
    ]
    out = np.zeros(n)
    for lo, hi, order, gain, dep in bands:
        nb = norm_rms(filt(rng.standard_normal(n), lo, hi, order, circular=True))
        wander = periodic_ctrl(n, L, rng, 2, 9, tilt=0.8)          # cada banda passeia sozinha
        w = (0.55 + 0.45 * wander) * (1 + dep * (bright - 0.5) * 1.6)
        out += gain * nb * np.clip(w, 0.05, None)
    out = filt(out, 35, 1500, 3, circular=True) * level
    # espaço: reverb longo e escuro, pouco (o vento é seco; o espaço vem da cauda)
    return reverb(out, rng, decay=4.5, mix=0.35, lp=1600, circular=True)


# v6.1: os 9 sons do v0.2 foram aprovados e entraram no SOUNDS.
# Próximas rodadas: o que for novo entra aqui e sai em assets/audio/_pending/.
# v7: desert_wind (v0.3 Marco 1) aprovado e promovido pro SOUNDS.
PENDING: dict = {}

SOUNDS.update({
    "chest_open": (sfx_chest_open, False, -21.0),
    "chest_close": (sfx_chest_close, False, -21.0),
    "inv_move": (sfx_inv_move, False, -28.0),
    "inv_full": (sfx_inv_full, False, -25.0),
    "power_low": (sfx_power_low, False, -19.0),
    "solar_hum": (loop_solar_hum, True, -38.0),
    "drone_loop": (loop_drone, True, -30.0),
    "drone_deliver": (sfx_drone_deliver, False, -20.0),
    "save": (sfx_save, False, -23.0),
    "desert_wind": (loop_desert_wind, True, -36.0),
})


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
    CAND_DIR.mkdir(parents=True, exist_ok=True)
    for name, (fn, target) in CANDIDATES.items():
        x = fn(rng_for(name))
        if x is None:
            print(f"{name}: pulada (pack do Kenney ou ffmpeg ausente)")
            continue
        xi = write_wav(CAND_DIR / f"{name}.wav", finalize(x, False, target))
        xf = xi.astype(float) / 32768
        peak_db = 20 * np.log10(np.max(np.abs(xf)) + 1e-12)
        loud = loudness(xf, False)
        meta["cand:" + name] = {
            "file": f"candidates/{name}.wav", "loop": False, "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(peak_db), 2), "loudness_db": round(float(loud), 1),
            "wave": waveform_peaks(xi),
        }
        print(f"{'candidates/' + name + '.wav':<20}{len(xi) / SR:>8.2f}{peak_db:>11.2f}{loud:>9.1f}")
    if PENDING:
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
    for name, (fn, loop, target) in PENDING.items():
        xi = write_wav(PENDING_DIR / f"{name}.wav", finalize(fn(rng_for(name)), loop, target))
        xf = xi.astype(float) / 32768
        peak_db = 20 * np.log10(np.max(np.abs(xf)) + 1e-12)
        loud = loudness(xf, loop)
        meta["pend:" + name] = {
            "file": f"_pending/{name}.wav", "loop": loop, "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(peak_db), 2), "loudness_db": round(float(loud), 1),
            "wave": waveform_peaks(xi),
        }
        if loop:
            adj = np.abs(np.diff(xi.astype(int)))
            jump = abs(int(xi[0]) - int(xi[-1]))
            meta["pend:" + name]["seam_lsb"] = jump
            meta["pend:" + name]["seam_pct"] = round(float(100 * np.mean(adj < jump)), 1)
        print(f"{'_pending/' + name + '.wav':<20}{len(xi) / SR:>8.2f}{peak_db:>11.2f}{loud:>9.1f}")
    (REPORT_DIR / "audio_meta.js").write_text(
        "// gerado por tools/audio/build_audio.py, não editar\nwindow.AUDIO_META = "
        + json.dumps(meta, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"ok: {len(meta)} arquivos em {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
