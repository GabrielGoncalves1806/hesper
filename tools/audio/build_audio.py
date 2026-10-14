"""Gera todos os sons do Hesper por síntese procedural.

Uso:  uv run python tools/audio/build_audio.py   (ou python3 ...: pula a v11)

Saída: assets/audio/*.wav (44,1 kHz, 16-bit, mono) e reports/audio/audio_meta.js
(duração, pico, loudness e forma de onda de cada arquivo, usado pelo report).

Os sons oficiais só dependem de numpy. A proposta v11 (gravações tratadas) lê os
arquivos de tools/audio/vendor/ com ffmpeg e usa o pedalboard; rode tudo com
`uv run python tools/audio/build_audio.py` (sem o pedalboard a v11 é pulada e o resto
sai igual, byte a byte). Tudo é determinístico: cada som tem a própria seed derivada
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
# v8.1: opção com passos gravados (Kenney footstep_concrete, CC0) pras rampas.
# Registradas aqui embaixo porque as funções ficam na seção do v8.1.


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


# ---------------------------------------------------------------------------
# v8 (v0.3 · Marcos 2 e 3 · Caverna e Destroços): pendentes de aprovação
# ---------------------------------------------------------------------------

def cave_space(x: np.ndarray, rng, circular: bool = False, decay: float = 4.5, mix: float = 0.9,
               lp: float = 2200.0) -> np.ndarray:
    """Espaço de caverna: reflexões iniciais em atrasos irregulares (paredes a distâncias
    diferentes, nada periódico, então nenhum pente/tom) + cauda longa e escura."""
    taps = [(0.071, 0.42), (0.113, 0.33), (0.187, 0.27), (0.262, 0.2), (0.349, 0.14), (0.458, 0.09)]
    if circular:
        er = x.copy()
        for d, g in taps:
            er += np.roll(filt(x, 120, lp, 1, circular=True), ns(d)) * g
    else:
        er = np.concatenate([x, np.zeros(ns(0.5))])
        xf = filt(x, 120, lp, 1)
        for d, g in taps:
            er[ns(d):ns(d) + len(x)] += xf * g
    return reverb(er, rng, decay=decay, mix=mix, lp=lp, circular=circular)


def amb_cave(rng):
    """Caverna: o mesmo Lá dos ambientes, uma oitava mais escuro. Drone grave em quinta
    (Lá1, Mi2, Lá2) bem fechado num passa-baixa, um fio de Dó3 (terça menor, sombra sem
    medo) que só aparece no swell, gotas esparsas em tempo irregular com eco de caverna,
    dois brilhos frios bem apagados e um rumor de rocha quase inaudível. Sem bicho.
    Periódico em L = 28 s (≠ 32 s dos ambientes e 36 s do vento)."""
    L = 28.0
    n = ns(L)
    drone = sum(g * pad_voice(n, L, rng, midi(m), detune=(-0.1, 0.0, 0.1), harm=(1.0, 0.15, 0.04),
                              swell=(1, 3))
                for m, g in ((33, 0.4), (40, 0.6), (45, 1.0), (52, 0.55)))       # A1 E2 A2 E3
    shade = pad_voice(n, L, rng, midi(48), harm=(1.0,), swell=(2, 4)) * 0.15      # C3, só respirando
    pad = norm_rms(filt(drone + shade, 30, 900, 2, circular=True))
    # brilhos: só 2 por volta, graves pra brilho (Mi4, Lá4), atrás do passa-baixa
    shimmer = filt(glints(n, rng, (64, 69), 2, (4.0, 7.0), (0.12, 0.18)), None, 1800, 1, circular=True)
    # gotas: esparsas e irregulares (às vezes uma dupla), com o espaço da caverna
    drops = np.zeros(n)
    gaps = rng.uniform(0.6, 4.6, 10) ** 1.3                    # intervalos bem desiguais (0,5 a 7 s)
    starts = np.cumsum(gaps / gaps.sum() * L) + rng.uniform(0, 1)  # 10 gotas por volta, espalhadas
    for t in starts:
        f0 = rng.uniform(900, 1700)
        amp = rng.uniform(1.6, 3.6)
        add_circ(drops, filt(plink(rng, f0, 0.08), 300, 3200, 1) * amp, ns(t) % n)
        if rng.uniform() < 0.3:                                                  # gota que respinga
            add_circ(drops, filt(plink(rng, f0 * rng.uniform(1.1, 1.35), 0.06), 300, 3200, 1) * amp * 0.5,
                     ns(t + rng.uniform(0.12, 0.3)) % n)
    drops = cave_space(drops, rng, circular=True, decay=4.0, mix=1.1, lp=2400)
    # rocha assentando bem longe: um sopro de ruído grave, sem tom, uma vez por volta
    m = ns(3.5)
    settle = filt(rng.standard_normal(m), 30, 160, 2) * bump(m, 0.2) * 0.35
    rumble = norm_rms(filt(rng.standard_normal(n), 22, 140, 2, circular=True))
    rumble *= 0.06 * (0.5 + 0.5 * periodic_ctrl(n, L, rng, 1, 4))
    add_circ(rumble, settle * 0.25, ns(17.0))
    air = norm_rms(filt(rng.standard_normal(n), 150, 900, 1, circular=True)) * 0.006  # ar parado, um fio
    # as gotas já têm o espaço da caverna, então entram fora do reverb dos brilhos
    return space_mix(rng, pad, shimmer, drops + rumble + air,
                     pad_rev=(6.5, 0.5, 1600), sh_rev=(6.0, 0.6, 3500))


def metal_step(rng, weight: float = 1.0) -> np.ndarray:
    """Bota em degrau de grade metálica: tranco de ruído grave, corpo médio de banda larga,
    um "tinc" curtíssimo (parciais inarmônicos sorteados a cada passo, decaimento de
    poucos ms, então não fica nota) e a grade chacoalhando de leve."""
    tr = Track()
    tr.add(noise_burst(rng, None, 300, 0.002, 0.02, 0.09, order=2), 0, 0.7 * weight)        # peso
    tr.add(noise_burst(rng, 400, 3500, 0.0004, 0.012, 0.06, order=1), 0, 0.8)               # corpo
    base = rng.uniform(700, 1100)
    ratios = sorted(rng.uniform(1.0, 6.5, 6))
    tr.add(metal(rng, base, ratios, rng.uniform(0.003, 0.006, 6), rng.uniform(0.3, 1.0, 6), 0.05),
           0.001, 0.07)                                                                    # tinc abafado
    for _ in range(int(rng.integers(3, 6))):                                               # grade chacoalhando
        at = rng.uniform(0.012, 0.06)
        hi = rng.uniform(1500, 5000)
        tr.add(noise_burst(rng, hi / 3, hi, 0.0002, rng.uniform(0.001, 0.003), 0.01, order=1),
               at, rng.uniform(0.1, 0.25))
    return tr.render()


def _ramp_v8(rng, down: bool):
    """v8, REPROVADO pelo dono ("muito estranho"); fica só pra comparação no report.
    3 passos na escada de metal + a mudança de espaço. Descer: o ar escurece e o eco
    cresce passo a passo (cada passo com mais caverna). Subir: o eco encolhe e o vento abre."""
    tr = Track()
    times = (0.0, 0.27, 0.55)
    for i, at in enumerate(times):
        k = i / 2 if down else 1 - i / 2                                   # 0 = superfície, 1 = caverna
        step = metal_step(rng, 1.0 - 0.15 * i if down else 0.85 + 0.1 * i)
        step = filt(step, None, 6000 - 3500 * k, 1)                         # mais fundo, mais abafado
        dry = 1 - 0.35 * k
        wet = cave_space(step, rng, decay=0.4 + 1.1 * k, mix=0.15 + 0.9 * k, lp=2800)
        wet[:len(step)] -= step                                            # só o eco
        tr.add(step * dry, at, 0.9)
        tr.add(wet, at, 0.9)
    # o ar: banda de ruído larga que fecha (desce) ou abre (sobe)
    dur = 1.15
    n = ns(dur)
    x = np.linspace(0, 1, n)
    if down:
        air = noise_sweep(rng, dur, 1400, 160, width=4.0) * bump(n, 0.25) * 0.5
        dark = filt(rng.standard_normal(n), 25, 140, 2) * np.clip(x * 1.4, 0, 1) ** 1.5 * bump(n, 0.75)
        tr.add(air, 0.0, 0.16)
        tr.add(dark, 0.15, 0.3)                                             # caverna "fechando" em volta
    else:
        air = noise_sweep(rng, dur, 160, 1200, width=4.0) * bump(n, 0.7)    # vento abrindo
        tr.add(air, 0.05, 0.2)
        tr.add(filt(rng.standard_normal(n), 25, 140, 2) * (1 - x) ** 2, 0.0, 0.2)  # caverna ficando pra trás
    out = tr.render()
    t = tvec(len(out))
    return out * np.clip((1.45 - t) / 0.4, 0, 1) ** 2                       # ~1,4 s no total


def sfx_ramp_down_v8(rng):
    return _ramp_v8(rng, True)


def sfx_ramp_up_v8(rng):
    return _ramp_v8(rng, False)


def sfx_lamp_place(rng):
    """Base apoiando no chão, clique do interruptor e a luz acendendo: um "fuum" macio e
    um brilho quente em Lá (Lá3 + Mi4 + Lá4) que abre o filtro e assenta, com um zumbido
    de filamento bem baixo."""
    tr = Track()
    tr.add(noise_burst(rng, 150, 1200, 0.001, 0.012, 0.06, order=1), 0, 0.6)               # base no chão
    tr.add(noise_burst(rng, 2000, 7000, 0.0002, 0.0008, 0.006, order=1), 0.07, 0.55)        # clique
    tr.add(noise_burst(rng, 900, 3000, 0.0003, 0.003, 0.015, order=1), 0.072, 0.35)
    n = ns(0.45)
    t = tvec(n)
    tr.add(filt(rng.standard_normal(n), 200, 1500, 1) * bump(n, 0.15) ** 2, 0.08, 0.18)     # fuum
    glow = np.zeros(n)
    for m, g in ((57, 1.0), (64, 0.6), (69, 0.35)):
        f = midi(m) * (1 - 0.03 * np.exp(-t / 0.05))                                      # sobe e assenta
        glow += g * np.sin(phase_of(f, n, rng.uniform(0, 6.28)))
    glow *= np.minimum(1, t / 0.04) * np.exp(-t / 0.22) * (1 - np.exp(-t / 0.015))
    tr.add(glow, 0.085, 0.22)
    hum = bl_wave(110, n, "saw", 600) * np.minimum(1, t / 0.05) * np.exp(-t / 0.18)        # filamento
    tr.add(hum, 0.085, 0.04)
    return reverb(tr.render(), rng, decay=0.5, mix=0.15, lp=3500)


def sfx_crate_open_v8(rng):
    """v8, REPROVADO pelo dono ("muito estranho"); fica só pra comparação no report.
    Tampa metálica pesada de caixa de carga: trava dupla soltando, ar velado escapando,
    a dobradiça arrastando (atrito de ruído largo com "agarra-solta" irregular, sem
    rangido tonal), a tampa tombando no batente (baque de ruído grave) e poeira caindo."""
    tr = Track()
    for at in (0.0, 0.05):                                                                  # trava dupla
        tr.add(noise_burst(rng, 1200, 5000, 0.0002, 0.0015, 0.012, order=1), at, 0.45)
        tr.add(noise_burst(rng, 150, 900, 0.0008, 0.012, 0.06, order=2), at + 0.002, 0.45)
    n = ns(0.35)
    tr.add(filt(rng.standard_normal(n), 900, 4000, 1) * bump(n, 0.08) ** 1.8, 0.08, 0.13)   # ar velado
    # dobradiça arrastando: banda larga que sobe devagar + agarra-solta irregular
    dur = 0.42
    n = ns(dur)
    t = tvec(n)
    drag = noise_sweep(rng, dur, 180, 520, width=3.5)
    stick = np.zeros(n)
    tt = 0.0
    while tt < dur:
        tt += rng.uniform(0.012, 0.035)                                     # irregular: não vira tom
        i = ns(tt)
        if i < n:
            stick[i:i + ns(0.006)] += rng.uniform(0.4, 1.0)
    stick = filt(stick, None, 120, 1)
    drag *= (0.35 + stick / (stick.max() + 1e-9)) * bump(n, 0.4)
    tr.add(drag, 0.16, 0.5)
    tr.add(noise_burst(rng, None, 260, 0.003, 0.05, 0.25, order=2), 0.6, 1.0)              # tampa no batente
    tr.add(noise_burst(rng, 300, 2000, 0.0008, 0.015, 0.08, order=1), 0.6, 0.45)           # corpo do metal
    for _ in range(9):                                                                     # poeira/ferrugem
        at = 0.62 + rng.gamma(1.5, 0.05)
        hi = rng.uniform(1500, 5000)
        tr.add(noise_burst(rng, hi / 4, hi, 0.0003, rng.uniform(0.001, 0.003), 0.012, order=1),
               at, rng.uniform(0.05, 0.14))
    return reverb(tr.render(), rng, decay=0.45, mix=0.13, lp=3500)


def sfx_blueprint_found(rng):
    """Mini-jingle de conquista, da família do stage_up (pulse + tri dobrado, Lá maior),
    só que menor: arpejo rápido Mi-Lá-Dó#-Mi subindo até Lá5 segurado, baixo em Lá e
    três brilhos. ~1,5 s com a cauda."""
    tr = Track()
    lead = [(64, 0.00, 0.09), (69, 0.075, 0.09), (73, 0.15, 0.09), (76, 0.225, 0.11), (81, 0.31, 0.75)]
    for m, at, d in lead:
        long = d > 0.5
        tr.add(chip_note(midi(m), d, "pulse", 3600, 0.35 if long else 0.3, a=0.005, sustain=0.7,
                         release=0.45 if long else 0.04, vib=0.005 if long else 0.0, vib_delay=0.2), at, 0.38)
        tr.add(chip_note(midi(m) * 1.003, d, "tri", 3000, a=0.005, sustain=0.7,
                         release=0.45 if long else 0.04), at, 0.16)
    tr.add(chip_note(midi(45), 0.3, "tri", 1500, a=0.006, sustain=0.8, release=0.05), 0.0, 0.4)
    tr.add(chip_note(midi(45), 0.85, "tri", 1500, a=0.006, sustain=0.8, release=0.4), 0.31, 0.45)
    for i, m in enumerate((88, 85, 93)):
        x = np.sin(phase_of(midi(m), ns(0.3))) * perc(ns(0.3), 0.002, 0.07)
        tr.add(x, 0.33 + 0.07 * i, 0.13)
    out = echo(tr.render(), 0.16, 0.2, taps=2, lp=3000)
    return reverb(out, rng, decay=1.2, mix=0.22, lp=4500)


def sfx_equip(rng):
    """Encaixe no traje: deslizar curto, "clack" de trava (ruído médio, sem tom), selo
    pneumático e um bipezinho Mi5->Lá5 bem baixo confirmando."""
    tr = Track()
    tr.add(noise_sweep(rng, 0.07, 600, 2000, width=2.5) * bump(ns(0.07), 0.7), 0, 0.2)      # deslizando
    tr.add(noise_burst(rng, 500, 2800, 0.0003, 0.006, 0.035, order=1), 0.07, 0.9)          # clack
    tr.add(noise_burst(rng, 2000, 7000, 0.0002, 0.0008, 0.006, order=1), 0.07, 0.4)
    tr.add(noise_burst(rng, None, 350, 0.001, 0.012, 0.05, order=2), 0.071, 0.4)           # peso do tanque
    n = ns(0.12)
    tr.add(filt(rng.standard_normal(n), 1500, 5000, 1) * bump(n, 0.1) ** 2, 0.09, 0.1)      # pssh
    for m, at in ((76, 0.12), (81, 0.17)):
        nn = ns(0.12)
        tr.add(np.sin(phase_of(midi(m), nn)) * perc(nn, 0.003, 0.03), at, 0.16)
    return reverb(tr.render(), rng, decay=0.35, mix=0.1, lp=4000)


def sfx_map_open(rng):
    """Mapa holográfico abrindo: um "fsss" curto de desdobrar (ruído com grão irregular,
    banda subindo) e dois bipes macios Lá5 -> Mi6. Discreto, de interface."""
    tr = Track()
    dur = 0.16
    n = ns(dur)
    grain = (rng.uniform(0, 1, n) < 0.08) * rng.standard_normal(n) + 0.35 * rng.standard_normal(n)
    unfold = (filt(grain, 900, 3000, 1) * np.linspace(1, 0.3, n)
              + filt(grain, 2500, 6500, 1) * np.linspace(0.2, 1, n)) * bump(n, 0.5)
    tr.add(unfold, 0, 0.35)
    for m, at in ((81, 0.06), (88, 0.12)):
        nn = ns(0.16)
        f = midi(m)
        x = np.sin(phase_of(f, nn)) + 0.15 * bl_wave(f, nn, "tri", 3000)
        tr.add(x * perc(nn, 0.004, 0.04), at, 0.32)
    return reverb(echo(tr.render(), 0.11, 0.15, taps=1, lp=2500), rng, decay=0.5, mix=0.12, lp=4500)


# ---------------------------------------------------------------------------
# v8.1: crate_open, ramp_down e ramp_up refeitos (os do v8 foram reprovados: "muito
# estranhos"). O que mudou de abordagem:
#  - rampa: saiu a grade metálica com "tinc" de parciais, saiu a banda de ruído que
#    andava de 1,4 kHz pra 160 Hz (soava como glissando) e saíram as reflexões em
#    atrasos fixos (repetiam o passo). Agora são 4 passos de cascalho num ritmo de
#    caminhada, só o filtro e a quantidade de reverb difuso mudam passo a passo, e o
#    "ar" por baixo é uma banda grave PARADA que só sobe e desce de volume.
#  - caixa: saiu o arrasto de 0,4 s com banda andando e o baque longo. Agora é
#    trava (clique) + rangido curto de dobradiça (atrito agarra-solta de verdade:
#    trem de pulsos com jitter, filtro largo) + batidinha seca da tampa. ~0,5 s.
# ---------------------------------------------------------------------------

def wet_only(x: np.ndarray, rng, decay: float, lp: float, predelay: float = 0.02) -> np.ndarray:
    """Só o retorno do reverb difuso (sem o seco), com o comprimento de x + cauda."""
    ir = make_ir(rng, decay, lp, predelay)
    n = len(x) + len(ir)
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:n]


def gravel_step(rng, weight: float = 1.0) -> np.ndarray:
    """Bota em cascalho/pedra, ~0,15 s: peso do calcanhar (ruído grave, sem seno), o
    contato, dezenas de grãos esmagando (microestalos de banda larga em tempo irregular,
    densidade caindo) e a ponta do pé rolando logo depois, com menos grãos."""
    tr = Track()
    tr.add(noise_burst(rng, 40, 260, 0.003, 0.016, 0.1, order=2), 0, 0.8 * weight)       # peso
    tr.add(noise_burst(rng, 250, 2500, 0.0008, 0.008, 0.05, order=1), 0, 0.45)           # contato
    tr.add(noise_burst(rng, 60, 400, 0.004, 0.012, 0.06, order=2),
           0.05 + rng.uniform(0, 0.012), 0.3 * weight)                                   # ponta do pé
    for t0, count, spread, amp in ((0.001, 26, 0.045, 1.0), (0.05, 12, 0.04, 0.55)):
        for _ in range(count):                                                           # grãos
            at = t0 + float(rng.gamma(1.3, spread / 2.5))
            hi = rng.uniform(1200, 5000)
            tr.add(noise_burst(rng, hi / 4, hi, 0.0002, rng.uniform(0.0006, 0.0025), 0.01, order=1),
                   at, amp * rng.uniform(0.15, 0.45) * np.exp(-(at - t0) / 0.05))
    return tr.render()


def kenney_step(rng, i: int):
    """Passo gravado do pack do Kenney (footstep_concrete, CC0), sem o subgrave."""
    x = kenney(f"footstep_concrete_{i % 5:03d}")
    if x is None:
        return None
    x = filt(x, 60, None, 2)
    return x / np.max(np.abs(x))


def _ramp(rng, down: bool, step_fn=None):
    """4 passos num ritmo de caminhada (~0,29 s, com um tico de irregularidade) + um ar
    grave parado por baixo. k vai de 0 (superfície: claro e seco) a 1 (caverna: abafado,
    com reverb difuso escuro). Descer anda 0 -> 1, subir anda 1 -> 0. Nenhum filtro com
    Q alto, nenhuma frequência que anda: só o passa-baixa de cada passo e o reverb mudam."""
    tr = Track()
    times = [0.0, 0.29, 0.575, 0.86]
    for i, at in enumerate(times):
        at = max(0.0, at + rng.uniform(-0.012, 0.012))
        k = i / 3 if down else 1 - i / 3
        step = step_fn(rng, i) if step_fn else gravel_step(rng, 1.0 if i % 2 == 0 else 0.85)
        step = filt(step, None, 5500 * (1600 / 5500) ** k, 2) * 10 ** (-3.5 * k / 20)  # abafa e afasta
        tr.add(step, at, 1.0 if i % 2 == 0 else 0.88)
        wet = wet_only(step, rng, decay=0.35 + 1.15 * k, lp=4000 - 2200 * k)
        tr.add(wet, at, 0.03 + 0.4 * k ** 2)                                       # seco -> caverna
    # o ar: uma banda grave e larga, parada no tom, que só respira (sobe e some)
    n = ns(1.15)
    air = filt(rng.standard_normal(n), 50, 380 if down else 520, 2)
    air /= np.sqrt(np.mean(air ** 2))
    tr.add(air * bump(n, 0.3 if down else 0.6), 0.0, 0.018)
    out = soft_sat(tr.render(), 1.6)                                  # segura só a ponta do 1º estalo
    t = tvec(len(out))
    end = 1.3 if down else 1.15                                                     # a descida deixa o eco
    return out * np.clip((end - t) / 0.3, 0, 1) ** 2


def sfx_ramp_down(rng):
    return _ramp(rng, True)


def sfx_ramp_up(rng):
    return _ramp(rng, False)


def cand_ramp_down_B1(rng):
    return _ramp(rng, True, kenney_step) if kenney("footstep_concrete_000") is not None else None


def cand_ramp_up_B1(rng):
    return _ramp(rng, False, kenney_step) if kenney("footstep_concrete_000") is not None else None


def hinge_creak(rng, dur: float, f0: float, f1: float, jitter: float = 0.12) -> np.ndarray:
    """Rangido de dobradiça como na física: atrito agarra-solta. Um trem de pulsos cujo
    ritmo sobe de f0 pra f1 com jitter de ~12% por pulso (por isso fica áspero e não vira
    nota), cada pulso um grãozinho de ruído, tudo passando por filtros LARGOS de 1ª ordem."""
    n = ns(dur)
    imp = np.zeros(n)
    t = 0.0
    while True:
        f = f0 + (f1 - f0) * np.sin(0.5 * np.pi * min(1.0, t / dur))
        t += (1 / f) * (1 + rng.uniform(-jitter, jitter))
        if t >= dur:
            break
        if rng.uniform() > 0.06:                                         # às vezes "pula" um
            imp[ns(t)] += rng.uniform(0.5, 1.0)
    g = ns(0.0015)
    grain = rng.standard_normal(g) * np.exp(-tvec(g) / 0.0004)
    x = np.convolve(imp, grain)[:n]
    x = filt(x, 500, 3500, 1) + 0.2 * filt(x, 1800, 6000, 1)
    return x * bump(n, 0.3)


def sfx_crate_open(rng):
    """v8.1: caixa de carga de metal abrindo, ~0,5 s. Trava (clique seco + o ferrolho
    assentando), um rangido curto de dobradiça e a tampa batendo de leve no batente.
    Tudo ruído e pulsos com filtro largo: nada de seno, de modo fixo ou de cauda longa."""
    tr = Track()
    tr.add(noise_burst(rng, 2500, 7000, 0.0002, 0.0007, 0.006, order=1), 0, 0.3)         # tic
    tr.add(noise_burst(rng, 700, 3500, 0.0003, 0.004, 0.03, order=1), 0, 0.7)            # clac
    tr.add(noise_burst(rng, 150, 700, 0.0008, 0.008, 0.05, order=2), 0.001, 0.35)        # peso da trava
    tr.add(noise_burst(rng, 1500, 6000, 0.0002, 0.0012, 0.01, order=1), 0.024, 0.32)     # ferrolho assenta
    tr.add(hinge_creak(rng, 0.19, 190, 330), 0.075, 0.4)                                 # rangido
    n = ns(0.19)
    tr.add(filt(rng.standard_normal(n), 800, 3000, 1) * bump(n, 0.4), 0.075, 0.025)       # atrito por baixo
    lid = 0.3
    tr.add(noise_burst(rng, 400, 3500, 0.0004, 0.007, 0.05, order=1), lid, 0.85)         # batidinha
    tr.add(noise_burst(rng, None, 250, 0.002, 0.016, 0.09, order=2), lid, 0.55)          # peso da tampa
    tr.add(noise_burst(rng, 2500, 7000, 0.0002, 0.0008, 0.006, order=1), lid, 0.2)
    tr.add(noise_burst(rng, 500, 3000, 0.0003, 0.004, 0.03, order=1), lid + 0.034, 0.22)  # quique
    return reverb(filt(soft_sat(tr.render(), 1.8), None, 7000, 1), rng, decay=0.3, mix=0.08, lp=3500)


# v6.1: os 9 sons do v0.2 foram aprovados e entraram no SOUNDS.
# Próximas rodadas: o que for novo entra aqui e sai em assets/audio/_pending/.
# v7: desert_wind (v0.3 Marco 1) aprovado e promovido pro SOUNDS.
# v8/v8.1: Marcos 2 (caverna) e 3 (destroços) do v0.3 aprovados e promovidos pro SOUNDS
# (rampas na opção B1, com os passos gravados do Kenney).
PENDING: dict = {}

SOUNDS.update({
    "amb_cave": (amb_cave, True, -28.0),
    # seed do nome da candidata, pra sair idêntico ao que o dono ouviu
    "ramp_down": (lambda _rng: cand_ramp_down_B1(rng_for("ramp_down_B1")), False, -22.0),
    "ramp_up": (lambda _rng: cand_ramp_up_B1(rng_for("ramp_up_B1")), False, -22.0),
    "lamp_place": (sfx_lamp_place, False, -21.0),
    "crate_open": (sfx_crate_open, False, -21.0),
    "blueprint_found": (sfx_blueprint_found, False, -16.0),
    "equip": (sfx_equip, False, -23.0),
    "map_open": (sfx_map_open, False, -24.0),
})

CANDIDATES.update({
    "ramp_down_B1": (cand_ramp_down_B1, -22.0),
    "ramp_up_B1": (cand_ramp_up_B1, -22.0),
})

# v8.1: as versões reprovadas do v8, regeradas idênticas (mesma seed) em
# assets/audio/_pending/rejected_v8/ só pra comparação no report.
REJECTED: dict = {
    "ramp_down": (sfx_ramp_down_v8, False, -21.0),
    "ramp_up": (sfx_ramp_up_v8, False, -21.0),
    "crate_open": (sfx_crate_open_v8, False, -20.0),
}

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


# ---------------------------------------------------------------------------
# v9 (v0.4 · Marco 1 · Tempestade): amb_storm, gust e sky_clear, pendentes
#
# Ideias que valem pros três:
#  - vento é só ruído: bandas largas cujo peso passeia, nada de seno nem de filtro
#    estreito fixo. O "uivo" das rajadas é ruído numa banda de ~1/3 de oitava que
#    ANDA (sobe com a rajada e desce com ela), então não vira nota parada;
#  - "areia batendo no capacete" são grãos curtíssimos (0,3-1,5 ms) em tempo de
#    Poisson, com densidade seguindo a força do vento, numa banda larga de 1,2 a
#    6,5 kHz (passa-baixa de 1ª ordem: o visor abafa o brilho), mais umas pedrinhas
#    esparsas e mais graves. Sem grão idêntico: 8 núcleos de ruído sorteados;
#  - o amb_storm leva por baixo o mesmo drone de Lá do amb_dead (quinta vazia),
#    abafado pela poeira, pra passagem pro Árido soar como "o vento morre e sobra o
#    mesmo lugar".
# ---------------------------------------------------------------------------

def slow_noise(n: int, rng, hi: float, circular: bool = True) -> np.ndarray:
    """Curva aleatória lenta (ruído com passa-baixa em `hi` Hz), normalizada pra 0..1."""
    s = filt(rng.standard_normal(n), None, hi, 2, circular=circular)
    s -= s.min()
    return s / (s.max() + 1e-12)


def tv_filter(x: np.ndarray, gain_fn, circular: bool = False, hop: int = 882) -> np.ndarray:
    """Filtro que muda no tempo (STFT, janela raiz-de-Hann na análise e na síntese, 4 hops
    por janela: a soma das janelas é constante, então sem filtro (ganho 1) volta igual).
    gain_fn(t_segundos, freqs) -> ganho por bin. circular=True trata x como periódico
    (precisa de len(x) múltiplo de hop)."""
    W = 4 * hop
    win = np.sqrt(0.5 - 0.5 * np.cos(2 * np.pi * np.arange(W) / W))
    f = np.fft.rfftfreq(W, 1 / SR)
    if circular:
        assert len(x) % hop == 0
        src, pad = x, 0
    else:
        pad = W
        m = len(x) + 2 * W
        m += (-m) % hop
        src = np.zeros(m)
        src[pad:pad + len(x)] = x
    n = len(src)
    out = np.zeros(n)
    for k in range(n // hop):
        idx = (k * hop + np.arange(W)) % n
        tc = ((k * hop + W / 2 - pad) % n if circular else (k * hop + W / 2 - pad)) / SR
        y = np.fft.irfft(np.fft.rfft(src[idx] * win) * gain_fn(tc, f), W) * win
        out[idx] += y
    out /= 2.0                                   # soma de Hann com 4 hops = 2
    return out if circular else out[pad:pad + len(x)]


def band_gain(f: np.ndarray, fc: float, octaves: float) -> np.ndarray:
    """Banda gaussiana em escala log, largura total a -6 dB = `octaves` (sem Q alto)."""
    sig = octaves / 2.355
    return np.exp(-0.5 * (np.log2(np.maximum(f, 1.0) / fc) / sig) ** 2)


def sand_veil(n: int, rng, circular: bool, lo: float = 600.0, hi: float = 2800.0,
              breathe: float = 0.6) -> np.ndarray:
    """v9.1: areia como véu contínuo, no lugar dos grãos (v9) que estalavam. Ruído numa
    banda larga (2ª ordem dos dois lados) com o volume respirando devagar. Sem impulso
    nenhum, sem ataque: a areia vira "textura do ar", não "tic"."""
    s_ = filt(filt(rng.standard_normal(n), lo, None, 2, circular=circular), None, hi, 2, circular=circular)
    return norm_rms(s_) * (0.55 + 0.45 * slow_noise(n, rng, breathe, circular))


def storm_roar(n: int, L: float, rng, level: np.ndarray, bright: np.ndarray,
               bands, wander_hi: float = 0.6) -> np.ndarray:
    """Corpo do vento: bandas largas (ordem 1-2) com peso passeando, como o desert_wind,
    mas mais grave, mais cheio e sem pausa."""
    out = np.zeros(n)
    for lo, hi, order, gain, dep in bands:
        nb = norm_rms(filt(rng.standard_normal(n), lo, hi, order, circular=True))
        w = (0.5 + 0.5 * slow_noise(n, rng, wander_hi)) * (1 + dep * (bright - 0.5) * 1.6)
        out += gain * nb * np.clip(w, 0.05, None)
    return norm_rms(out * level)


def amb_storm(rng, *, roar=1.0, buffet=0.25, sand=0.12, howl=0.25, swells=0.35, drone=0.22,
              top=2400.0):
    """Tempestade de poeira em loop de 34 s (não bate com 32 dos ambientes, 36 do vento e
    28 da caverna). v9.1: o caráter vem só do vento. Bandas largas respirando devagar,
    rajadas internas lentas e suaves (5-10 s, no máximo uns +3 dB), um uivo distante que
    passeia, o vento tremendo de leve no capacete e a areia como véu contínuo. Nada de
    grão, pedrinha ou impulso. Rajada forte é o gust.wav, não o fundo."""
    L = 34.0
    n = ns(L)
    tide = periodic_ctrl(n, L, rng, 1, 5)                  # maré lenta (dezenas de segundos)
    turb = slow_noise(n, rng, 0.35)                        # turbulência lenta (2-3 s)
    sw = filt(gusts(n, rng, 6, (5.0, 10.0), rise=0.45), None, 0.4, 1, circular=True)
    sw = np.clip(sw, 0, None) / (sw.max() + 1e-12)         # rajadas internas suaves
    level = 0.68 + 0.14 * tide + 0.08 * turb + 0.3 * swells * sw
    bright = np.clip(0.3 * tide + 0.4 * turb + 0.6 * sw, 0, 1)
    bands = [  # (lo, hi, ordem, ganho, quanto depende do "bright")
        (30, 85, 2, 0.75, -0.3),
        (70, 190, 2, 1.0, -0.2),
        (160, 420, 1, 0.95, 0.0),
        (380, 950, 1, 0.7, 0.35),
        (850, 2100, 1, 0.4, 0.7),
    ]
    body = filt(storm_roar(n, L, rng, level, bright, bands, wander_hi=0.3), 28, top, 2, circular=True)
    # o vento tremendo no capacete: grave com ondulação lenta (até ~4 Hz), sem pancada
    tremor = slow_noise(n, rng, 4.0) ** 1.2
    buf = norm_rms(filt(rng.standard_normal(n), 25, 150, 2, circular=True)) * (0.55 + 0.45 * tremor) * level
    veil = sand_veil(n, rng, True) * (0.4 + 0.6 * bright) * level
    x = roar * body + buffet * buf + sand * veil
    if howl:
        # uivo distante: ruído numa banda de ~0,4 oitava que passeia entre ~170 e ~330 Hz,
        # mais presente quando o vento aperta
        fc_curve = 170 * 2 ** (0.95 * slow_noise(n, rng, 0.12))
        hw = tv_filter(rng.standard_normal(n), lambda t, f: band_gain(f, fc_curve[int(t * SR) % n], 0.4),
                       circular=True)
        x = x + howl * norm_rms(hw) * (0.25 + 0.75 * np.maximum(tide, sw))
    x = filt(x, None, 3800, 2, circular=True)            # dentro do capacete: sem chiado fino
    x = reverb(x, rng, decay=1.8, mix=0.2, lp=2000, circular=True)
    if drone:
        # o mesmo drone do amb_dead (Lá1 Mi2 Lá2 Mi3), abafado pela poeira
        pad = sum(g * pad_voice(n, L, rng, midi(m), detune=(-0.125, 0.0, 0.125), harm=(1.0, 0.2, 0.06))
                  for m, g in ((33, 0.45), (40, 0.5), (45, 1.0), (52, 0.45)))
        pad = reverb(filt(norm_rms(pad), None, 700, 2, circular=True), rng, decay=6.0, mix=0.45,
                     lp=1800, circular=True)
        x = norm_rms(x) + drone * norm_rms(pad)
    return x


def amb_storm_A(rng):
    """A · capacete: vento cheio, véu de areia, uivo distante discreto e o drone do morto por baixo."""
    return amb_storm(rng)


def amb_storm_B(rng):
    """B · paredão: mais grave e mais pesado, tremor no capacete mais forte, uivo distante mais
    presente, rajadas internas maiores, pouca areia e o drone quase sumido."""
    return amb_storm(rng, roar=1.15, buffet=0.4, sand=0.07, howl=0.55, swells=0.5, drone=0.1, top=1900)


def amb_storm_C(rng):
    """C · o planeta por baixo: vento um pouco mais contido e o drone de Lá mais presente,
    a mais perto da estética espacial aprovada."""
    return amb_storm(rng, roar=0.85, buffet=0.2, sand=0.08, howl=0.18, swells=0.3, drone=0.5)


def gust_env(n: int, rng, peak_at: float = 1.35, fall_from: float = 2.9) -> np.ndarray:
    """Envelope de rajada: cresce (curva lenta no começo), fica forte com uns
    sub-empurrões lentos e cai devagar. Tudo suave: nenhuma quina."""
    t = tvec(n)
    dur = n / SR
    up = np.clip(t / peak_at, 0, 1)
    up = up ** 1.8 * (3 - 2 * up)
    down = 0.5 + 0.5 * np.cos(np.pi * np.clip((t - fall_from) / (dur - fall_from), 0, 1))
    env = up * down
    wob = slow_noise(n, rng, 1.5, circular=False)
    return env * (0.85 + 0.15 * wob) * (1 + 0.12 * np.exp(-((t - 2.1) / 0.35) ** 2))


def gust(rng, *, dur=4.6, howl=1.0, howl_path=(190, 410, 230), voices=1, sand=0.25,
         body=1.0, low=0.45):
    """v9.1: sem grãos e sem pedrinhas. Sopro que abre e fecha, uivo de banda que anda,
    tremor grave lento e a areia como véu que incha com a rajada."""
    n = ns(dur)
    env = gust_env(n, rng)
    t = tvec(n)
    # corpo: ruído largo cujo passa-baixa abre com a rajada (escuro -> claro -> escuro)
    def lp_gain(tc, f):
        e = env[min(n - 1, max(0, int(tc * SR)))]
        return bw_mag(f, 55, 250 + 1700 * e ** 1.4, 2)
    whoosh = norm_rms(tv_filter(rng.standard_normal(n), lp_gain)) * env
    trem = slow_noise(n, rng, 4.0, circular=False) ** 1.2
    rum = norm_rms(filt(rng.standard_normal(n), 25, 150, 2)) * env ** 1.5 * (0.55 + 0.45 * trem)
    veil = sand_veil(n, rng, False, 700, 3000, 1.2) * env ** 1.8
    x = body * whoosh + low * rum + sand * veil
    if howl:
        f0, f1, f2 = howl_path
        tp = 1.6
        fc = np.where(t < tp, f0 + (f1 - f0) * np.clip(env / env.max(), 0, 1),
                      f2 + (f1 - f2) * np.clip(env / env.max(), 0, 1))
        hw = np.zeros(n)
        for v in range(voices):
            ratio = (1.0, 1.36)[v]
            drift = 1 + 0.03 * (slow_noise(n, rng, 0.8, circular=False) - 0.5)
            curve = fc * ratio * drift
            hw += (1.0, 0.6)[v] * norm_rms(tv_filter(
                rng.standard_normal(n), lambda tc, f, c=curve: band_gain(f, c[min(n - 1, max(0, int(tc * SR)))], 0.33)))
        x = x + howl * hw * env ** 1.3
    x = filt(x, None, 4000, 2)                                   # capacete
    return reverb(x, rng, decay=1.6, mix=0.25, lp=2800)


def gust_A(rng):
    """A · uivo grave: corpo cheio, uivo de ~1/3 de oitava subindo de ~190 pra ~410 Hz e
    voltando pra ~230, véu de areia inchando no pico."""
    return gust(rng)


def gust_B(rng):
    """B · sopro e areia: sem uivo. O sopro abrindo e fechando, com mais véu de areia."""
    return gust(rng, howl=0.0, sand=0.45, body=1.1, low=0.55)


def gust_C(rng):
    """C · uivo aberto: duas vozes de uivo (a segunda 1,36x acima, intervalo que não fecha
    acorde), mais altas e mais agudas, quase sem areia. A mais 'cinema'."""
    return gust(rng, howl=1.7, howl_path=(240, 560, 290), voices=2, sand=0.15)


def sfx_sky_clear(rng):
    """Céu limpando, ~7 s: a última lufada da tempestade indo embora (sopro que escurece e
    afina) e, por baixo, a quinta vazia de Lá abrindo devagar, com quatro brilhos subindo
    (Lá4, Mi5, Lá5, Mi6). Sem terça: o Árido ainda é morto. v9.1: sem os grãos de areia."""
    dur = 7.2
    n = ns(dur)
    t = tvec(n)
    tail = np.exp(-t / 1.3) * np.clip(t / 0.25, 0, 1) ** 2
    def lp_gain(tc, f):
        return bw_mag(f, 50, 160 + 1300 * np.exp(-max(tc, 0) / 1.1), 2)
    wind = norm_rms(tv_filter(rng.standard_normal(n), lp_gain)) * tail
    tr = Track()
    tr.add(wind, 0, 1.0)
    m = ns(6.2)
    for mm, g in ((45, 1.0), (52, 0.7), (57, 0.5), (64, 0.3)):   # Lá2 Mi3 Lá3 Mi4
        v = sum(np.sin(phase_of(midi(mm) * (1 + d), m, rng.uniform(0, 6.28))) for d in (-0.0012, 0, 0.0012))
        tr.add(v * adsr(m, 2.0, 0.5, 0.85, 2.6) / 3, 0.9, 0.16 * g)
    for i, mm in enumerate((69, 76, 81, 88)):
        k = ns(2.6)
        ph = phase_of(midi(mm), k)
        x = (np.sin(ph) + 0.12 * np.sin(2 * ph)) * bump(k, 0.25) ** 1.5
        tr.add(x, 2.0 + 0.55 * i, 0.07 * (1 - 0.12 * i))
    out = tr.render(dur)
    return reverb(out, rng, decay=5.0, mix=0.5, lp=4000)


# v9.1 aprovado pelo dono (sem escolher letra, valeu a recomendação): amb_storm = A
# (capacete), gust = A (uivo grave) e sky_clear. Promovidos pro SOUNDS com a seed do nome
# da candidata, pra sair idêntico byte a byte ao que ele ouviu. As B e C ficam aqui só como
# histórico (amb_storm_B/C, gust_B/C), sem gerar arquivo. (v9.3: viraram _1/_2, abaixo.)
SOUNDS.update({
    "amb_storm": (lambda _rng: amb_storm_A(rng_for("amb_storm_A")), True, -27.0),
    "gust": (lambda _rng: gust_A(rng_for("gust_A")), False, -21.0),
    "sky_clear": (sfx_sky_clear, False, -21.0),
    # v9.3: o dono quis as 3 como variações (o jogo troca entre elas). B e C viram _1 e _2,
    # com a seed da candidata (idênticas à v9.1) e o mesmo alvo de loudness da A
    "amb_storm_1": (lambda _rng: amb_storm_B(rng_for("amb_storm_B")), True, -27.0),
    "amb_storm_2": (lambda _rng: amb_storm_C(rng_for("amb_storm_C")), True, -27.0),
    "gust_1": (lambda _rng: gust_B(rng_for("gust_B")), False, -21.0),
    "gust_2": (lambda _rng: gust_C(rng_for("gust_C")), False, -21.0),
})


# ---------------------------------------------------------------------------
# v10 (v0.4 · Marco 3 · gelo e água): PROPOSTA. Os wavs saem em reports/audio/v10/
# (não em assets/audio/) até o dono aprovar; ao aprovar, promove pro SOUNDS com a
# seed do nome daqui (rng_for(nome)), pra sair idêntico byte a byte.
#
# Regras que valem pros três:
#  - gelo é ruído: rachadura = cascata de grãos curtos de banda larga (filtro de
#    1ª ordem) em tempo irregular; peso = ruído grave, nunca seno ("tambor") nem
#    modo fixo ("latinha"). O único elemento com altura é o "piu" dispersivo do gelo
#    (varredura rápida de 2,6 kHz pra ~400 Hz, que não para em nota nenhuma);
#  - de longe: tudo passa por passa-baixa (~5-6 kHz) e reverb grande de cratera;
#  - chuva sem "estalado": o corpo é um véu de ruído (gotas tão densas que viram
#    textura) e as gotas que aparecem são "tup" abafados (ataque de 2-4 ms, passa-
#    baixa ~3 kHz), nunca "tic". Sem plink tonal (o amb_mist já tem as gotas dele).
#    Pouco grave (abaixo de ~250 Hz fica o pad do amb_mist/amb_green).
# ---------------------------------------------------------------------------

PROP_DIR = REPORT_DIR / "v10"


def tail_cut(x: np.ndarray, max_dur: float, fade: float) -> np.ndarray:
    """Limita a duração com fade-out em cosseno (pro rabo do reverb não passar do teto)."""
    n = min(len(x), ns(max_dur))
    x = x[:n].copy()
    f = min(ns(fade), n)
    x[-f:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0, 1, f))
    return x


def crack_cascade(rng, tr: Track, at: float, count: int, span: float, lo=(500, 1400),
                  hi=(4500, 8000), amp: float = 1.0) -> None:
    """Rachadura correndo: `count` microestalos de ruído largo em intervalos irregulares
    (exponenciais) dentro de `span` s, o primeiro mais forte, o resto oscilando."""
    t = at
    for i in range(count):
        a = amp * (1.0 if i == 0 else rng.uniform(0.25, 0.8) * np.exp(-(t - at) / (span * 1.2)))
        tr.add(noise_burst(rng, rng.uniform(*lo), rng.uniform(*hi), rng.uniform(0.0004, 0.0012),
                           rng.uniform(0.003, 0.011), 0.05, order=1), t, a)
        t += rng.exponential(span / count)


def ice_pew(rng, f0: float = 2600.0, f1: float = 420.0, dur: float = 0.32) -> np.ndarray:
    """O "piu" do gelo grosso rachando (dispersão na placa): varredura exponencial
    rápida, decaindo junto. Nunca fica parado numa frequência."""
    n = ns(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / (dur / 4.0))
    x = np.sin(phase_of(f, n, rng.uniform(0, 6.28)))
    return x * perc(n, 0.002, dur / 4.5)


def sfx_ice_crack(rng, *, pew: float = 0.0, settle: int = 3):
    """Estalo seco de gelo rachando, de longe (~1,8 s). Cascata de microestalos de ruído
    largo, um "corpo" de placa (ruído 80-700 Hz, não seno), uns estalinhos de acomodação
    depois e reverb grande de cratera."""
    tr = Track()
    crack_cascade(rng, tr, 0.0, int(rng.integers(5, 9)), 0.16)
    tr.add(noise_burst(rng, 80, 700, 0.003, 0.11, 0.6, order=1), 0.004, 0.55)    # placa cedendo
    tr.add(noise_burst(rng, 40, 220, 0.012, 0.22, 0.9, order=2), 0.01, 0.7)      # peso, só ruído
    if pew:
        tr.add(ice_pew(rng), 0.012, pew)
    for _ in range(settle):                                                      # gelo se acomodando
        crack_cascade(rng, tr, rng.uniform(0.25, 0.95), int(rng.integers(1, 4)), 0.05,
                      lo=(900, 1800), hi=(3500, 6000), amp=rng.uniform(0.15, 0.3))
    x = filt(soft_sat(tr.render(1.0), 2.0), None, 6000, 1)                       # de longe
    x = reverb(x, rng, decay=2.2, mix=0.5, lp=4200)
    return tail_cut(x, 1.9, 0.6)


def sfx_ice_crack_0(rng):
    """Estalo A · seco: só ruído, sem o "piu"."""
    return sfx_ice_crack(rng)


def sfx_ice_crack_1(rng):
    """Estalo B · com o "piu" do gelo grosso bem baixo por baixo do estalo."""
    return sfx_ice_crack(rng, pew=0.18, settle=4)


def sfx_ice_collapse(rng):
    """Desabamento (~2,4 s): rachadura grande e mais grave, a placa cede (ronco de ruído
    grave crescendo e um "whump" de ruído quando bate no fundo), blocos e lascas caindo
    em tempo de Poisson cada vez mais raros, um chiado de gelo escorregando e reverb
    grande. Nenhum seno, nenhum filtro estreito."""
    tr = Track()
    crack_cascade(rng, tr, 0.0, 10, 0.22, lo=(300, 900), hi=(3500, 6500))
    tr.add(ice_pew(rng, 1900, 300, 0.4), 0.02, 0.12)
    n = ns(1.9)                                                                  # placa cedendo
    t = tvec(n)
    env = np.clip(t / 0.18, 0, 1) ** 1.5 * np.exp(-t / 0.7) * (0.75 + 0.25 * slow_noise(n, rng, 6.0, False))
    tr.add(norm_rms(filt(rng.standard_normal(n), 30, 260, 2)) * env, 0.05, 0.22)
    tr.add(noise_burst(rng, 35, 320, 0.01, 0.16, 0.8, order=1), 0.42, 0.9)        # "whump" no fundo
    m = ns(1.3)                                                                  # gelo escorregando
    slide = filt(rng.standard_normal(m), 700, 3800, 1) * bump(m, 0.3) * (0.6 + 0.4 * slow_noise(m, rng, 8.0, False))
    tr.add(slide, 0.15, 0.05)
    t0 = 0.3
    while True:                                                                  # blocos e lascas
        t0 += rng.exponential(1 / (26 * np.exp(-(t0 - 0.3) / 0.55) + 2.5))
        if t0 > 1.9:
            break
        fade = np.exp(-(t0 - 0.3) / 0.8)
        if rng.random() < 0.45:                                                  # bloco: grave, 2-3 batidas
            for k in range(int(rng.integers(2, 4))):
                hi = rng.uniform(900, 2200)
                tr.add(noise_burst(rng, hi / 6, hi, 0.0015, rng.uniform(0.012, 0.03), 0.12, order=1),
                       t0 + k * rng.uniform(0.012, 0.035), fade * rng.uniform(0.35, 0.7))
        else:                                                                    # lasca: curta e mais aguda
            hi = rng.uniform(3000, 6500)
            tr.add(noise_burst(rng, hi / 4, hi, 0.0006, rng.uniform(0.002, 0.006), 0.03, order=1),
                   t0, fade * rng.uniform(0.15, 0.35))
    x = filt(soft_sat(tr.render(2.0), 1.8), None, 5500, 1)
    x = reverb(x, rng, decay=2.6, mix=0.55, lp=3800)
    return tail_cut(x, 2.45, 0.7)


def rain_loop(rng, *, L: float = 10.0, drops: float = 12.0, plops: int = 8, wash=1.0,
              air: float = 0.08, low: float = 0.12, sheets: float = 0.25, top: float = 4200.0,
              near_gain: float = 0.35):
    """Chuva em loop periódico de L s. Véu de ruído (o grosso das gotas, longe) respirando
    devagar, "cortinas" lentas de chuva mais forte, gotas próximas como "tup" abafado
    (Poisson, `drops` por s, uns 4-5 dB acima do véu no envelope de 5 ms), uns "plops" maiores raros e reverb curto de céu aberto."""
    n = ns(L)
    breath = 0.8 + 0.2 * slow_noise(n, rng, 0.25)
    sh = filt(gusts(n, rng, 3, (2.5, 4.5), rise=0.4), None, 0.6, 1, circular=True)
    sh = np.clip(sh, 0, None) / (sh.max() + 1e-12)
    level = breath * (1 + sheets * sh)
    body = norm_rms(filt(filt(rng.standard_normal(n), 300, None, 2, circular=True), None, 2600, 2, circular=True))
    hiss = norm_rms(filt(rng.standard_normal(n), 2500, 5500, 2, circular=True))
    patter = norm_rms(filt(rng.standard_normal(n), 140, 480, 2, circular=True)) * (0.7 + 0.3 * slow_noise(n, rng, 1.5))
    x = (wash * body + air * hiss * (0.6 + 0.4 * sh) + low * patter) * level
    near = np.zeros(n)
    k = rng.poisson(drops * L)
    for _ in range(k):                                                           # gotas perto: "tup"
        hi = rng.uniform(1400, 2600)
        d = noise_burst(rng, hi / 3.2, hi, rng.uniform(0.002, 0.004), rng.uniform(0.006, 0.016), 0.06, order=1)
        add_circ(near, norm_rms(d) * rng.lognormal(0, 0.35), int(rng.integers(0, n)))
    for _ in range(plops):                                                       # gotas grandes
        d = noise_burst(rng, 220, rng.uniform(1100, 1700), 0.003, rng.uniform(0.018, 0.03), 0.12, order=1)
        add_circ(near, norm_rms(d) * rng.uniform(1.0, 1.6), int(rng.integers(0, n)))
    x = x + near_gain * near * level
    x = filt(x, 120, top, 2, circular=True)
    return reverb(x, rng, decay=1.1, mix=0.22, lp=3500, circular=True)


def amb_rain(rng):
    """Médio: a pancada típica da Névoa."""
    return rain_loop(rng)


def amb_rain_light(rng):
    """Fraca: garoa. Gotas raras, véu mais fino e mais escuro, sem cortinas fortes."""
    return rain_loop(rng, drops=5.0, plops=3, air=0.05, low=0.05, sheets=0.12, top=3600,
                     near_gain=0.45)


def amb_rain_heavy(rng):
    """Forte: aguaceiro. Mais gotas, cortinas mais fortes e o "tamborilar" grave do chão."""
    return rain_loop(rng, drops=24.0, plops=14, air=0.11, low=0.24, sheets=0.4, top=4600)


def loop_vent_hiss(rng):
    """Fumarola: chiado baixo e grave em loop de 7 s. Banda principal 150-1000 Hz que
    respira irregular (pressão subindo e soltando), um sopro mais claro só nos surtos e
    um ronco de ruído bem grave por baixo (a terra). Sem tom, sem impulso."""
    L = 7.0
    n = ns(L)
    press = 0.65 + 0.35 * slow_noise(n, rng, 0.9)
    surge = filt(gusts(n, rng, 3, (0.9, 1.8), rise=0.3), None, 1.5, 1, circular=True)
    surge = np.clip(surge, 0, None) / (surge.max() + 1e-12)
    main = norm_rms(filt(filt(rng.standard_normal(n), 150, None, 2, circular=True), None, 1000, 2, circular=True))
    bright = norm_rms(filt(rng.standard_normal(n), 900, 2800, 1, circular=True))
    rumble = norm_rms(filt(rng.standard_normal(n), 25, 120, 2, circular=True)) * (0.6 + 0.4 * slow_noise(n, rng, 3.0))
    x = main * press * (1 + 0.35 * surge) + 0.15 * bright * surge + 0.5 * rumble
    x = filt(x, 22, 2400, 2, circular=True)
    return reverb(x, rng, decay=0.9, mix=0.15, lp=2500, circular=True)


# nome: (função, loop?, alvo de loudness dB). Saem em reports/audio/v10/.
PROPOSALS: dict = {
    "ice_crack": (sfx_ice_crack_0, False, -24.0),
    "ice_crack_1": (sfx_ice_crack_1, False, -24.0),
    "ice_collapse": (sfx_ice_collapse, False, -22.0),
    "amb_rain": (amb_rain, True, -29.0),
    "amb_rain_light": (amb_rain_light, True, -32.0),
    "amb_rain_heavy": (amb_rain_heavy, True, -27.0),
    "vent_hiss": (loop_vent_hiss, True, -33.0),
}


# ---------------------------------------------------------------------------
# v11 (v0.4 · Marco 3 · gelo e água, refeito HÍBRIDO): PROPOSTA. O dono achou que a
# síntese pura soava "imitação" nos sons de natureza; a v11 parte de GRAVAÇÕES livres
# (em tools/audio/vendor/, só lidas, nunca executadas) tratadas aqui. Saem em
# reports/audio/v11/, mesmos nomes e papéis da v10, até o dono escolher.
#
# Fontes (detalhes, URLs e licenças em assets/audio/CREDITS.md e nos SOURCE.txt):
#  - chuva: "AMB Rain Loop 2" (Kresiek The Furry, OpenGameArt, CC0), GoPro em áudio
#    bruto, 12 min; vendor guarda só os 4 recortes usados, sem perda;
#  - gelo: "Ice breaking/shattering" (IgnasD, OGA, CC0) e "75 CC0 breaking / falling /
#    hit sfx" (rubberduck, OGA, CC0);
#  - fumarola: "Fumarole (large)", Norris Geyser Basin (NPS/Jennifer Jerrett, Yellowstone
#    Sound Library, domínio público, obra do governo dos EUA);
#  - reverb da cratera: resposta ao impulso medida na capela de São Nicolau da catedral
#    de Aachen (Zerwas e Kayku, Zenodo, CC BY 4.0), canal W, fonte na galeria e o
#    microfone no ponto mais distante (S3 → R12, 14,4 m). Não achei IR medido em CC0
#    que baixe sem login; este é o único item que pede crédito.
#
# Regras que continuam valendo: nada de vidro nem de ressonância estreita (os sons de
# vidro dos packs ficaram de fora por isso), o peso grave do gelo é ruído sintético
# (nunca seno) e a chuva fica acima de ~250 Hz pra não brigar com os pads.
# Precisa do pedalboard (uv add --dev pedalboard): rode com
#   uv run python tools/audio/build_audio.py
# Sem ele (ou sem ffmpeg/vendor), a v11 é pulada com aviso e o resto sai igual.
# ---------------------------------------------------------------------------

V11_DIR = REPORT_DIR / "v11"
VENDOR_ROOT = Path(__file__).resolve().parent / "vendor"
V11_RAIN = VENDOR_ROOT / "oga_rain_gopro"
V11_ICE = VENDOR_ROOT / "oga_ice_shatters" / "IceShatters"
V11_BREAK = VENDOR_ROOT / "oga_breaking_falling" / "Audio"
V11_VENT = VENDOR_ROOT / "nps_yellowstone" / "yell-NorrisPorcelainBasinFumerole.mp3"
V11_IR = VENDOR_ROOT / "aachen_chapel_ir" / "Nikolauskapelle_Source3_BRIR" / "S3-Do_R12.wav"
_DECODED: dict = {}


def decode(path: Path) -> np.ndarray:
    """Decodifica qualquer áudio do vendor pra float 44,1 kHz via ffmpeg (só leitura).
    Devolve (n, canais). Guarda em cache: vários sons usam o mesmo arquivo."""
    import subprocess
    key = str(path)
    if key not in _DECODED:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "stream=channels", "-of", "csv=p=0", str(path)],
                               capture_output=True, text=True, check=True).stdout
        ch = int(probe.split()[0])
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ar", str(SR), "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        _DECODED[key] = np.frombuffer(raw, "<f4").astype(float).reshape(-1, ch)
    return _DECODED[key]


def mono(path: Path) -> np.ndarray:
    x = decode(path)
    return x.mean(axis=1)


def repitch(x: np.ndarray, semis: float) -> np.ndarray:
    """Muda a altura reamostrando (como fita mais lenta): -4 st = 26% mais longo e mais grave.
    Reamostragem por FFT (limitada em banda, sem serrilhado)."""
    if semis == 0:
        return x.copy()
    n = len(x)
    m = int(round(n * 2 ** (-semis / 12)))
    X = np.fft.rfft(x)
    Y = np.zeros(m // 2 + 1, dtype=complex)
    k = min(len(X), len(Y))
    Y[:k] = X[:k]
    return np.fft.irfft(Y, m) * (m / n)


def fades(x: np.ndarray, fi: float = 0.002, fo: float = 0.03) -> np.ndarray:
    x = x.copy()
    a, b = min(ns(fi), len(x) // 2), min(ns(fo), len(x) // 2)
    if a:
        x[:a] *= np.linspace(0, 1, a)
    if b:
        x[-b:] *= np.linspace(1, 0, b) ** 2
    return x


def pb(x: np.ndarray, *plugins) -> np.ndarray:
    """Passa um sinal mono por uma cadeia do pedalboard (determinístico)."""
    from pedalboard import Pedalboard
    y = Pedalboard(list(plugins))(x.astype(np.float32), SR)
    return np.asarray(y, dtype=float).reshape(-1)


_CRATER_IR: list = []


def crater_ir() -> np.ndarray:
    """IR da capela (canal W) virado "cratera": começa na primeira chegada (o direto já
    vem atrasado e encoberto pela galeria), passa-alta de 120 Hz e passa-baixa de 4,5 kHz
    (pedra longe e ar frio), e a cauda de ~4,2 s encurtada pra ~2,3 s com um envelope
    exponencial e fade final. Normalizado pela energia."""
    if not _CRATER_IR:
        w = decode(V11_IR)[:, 0]
        on = int(np.nonzero(np.abs(w) > np.abs(w).max() * 0.05)[0][0])
        ir = w[on: on + ns(2.6)].copy()
        t = tvec(len(ir))
        ir *= np.exp(-t * (6.9 / 2.3 - 6.9 / 4.2))          # RT ~4,2 s -> ~2,3 s
        f = ns(0.4)
        ir[-f:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0, 1, f))
        ir = filt(ir, 120, 4500, 2)
        _CRATER_IR.append(ir / np.sqrt(np.sum(ir ** 2)))
    return _CRATER_IR[0]


def crater_reverb(x: np.ndarray, wet: float, predelay: float = 0.03) -> np.ndarray:
    """Convolução (pedalboard.Convolution) com o IR medido. Seco + `wet` × molhado, com o
    molhado no mesmo RMS do seco antes do ganho (pra `wet` ser comparável entre sons)."""
    from pedalboard import Convolution
    ir = np.concatenate([np.zeros(ns(predelay)), crater_ir()]).astype(np.float32)
    pad = np.concatenate([x, np.zeros(len(ir))])
    y = np.asarray(Convolution(ir, mix=1.0, sample_rate=SR)(pad.astype(np.float32), SR), dtype=float).reshape(-1)
    y = y * (np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(y ** 2)) + 1e-12))
    return pad + wet * y


def ice_rec(name: str) -> np.ndarray:
    return mono(V11_ICE / f"{name}.ogg")


def break_rec(name: str) -> np.ndarray:
    return mono(V11_BREAK / f"bfh1_{name}.ogg")


def grain(rng, src: np.ndarray, dur=(0.03, 0.09)) -> np.ndarray:
    """Pedacinho de uma gravação (janela de Hann): um microestalo de gelo de verdade."""
    n = ns(rng.uniform(*dur))
    hot = np.nonzero(np.abs(src) > np.abs(src).max() * 0.08)[0]   # só onde tem som
    a = int(rng.choice(hot[hot < len(src) - n])) if np.any(hot < len(src) - n) else 0
    return src[a:a + n] * np.hanning(n)


def ice_master(x: np.ndarray, lp: float, wet: float, max_dur: float, fade: float) -> np.ndarray:
    """Cadeia comum do gelo: compressão leve (os originais vêm estourados no ataque),
    passa-baixa de distância, reverb de cratera e corte da cauda."""
    from pedalboard import Compressor, LowpassFilter
    x = x / (np.max(np.abs(x)) + 1e-12)
    x = pb(x, Compressor(threshold_db=-14, ratio=3.0, attack_ms=0.5, release_ms=90))
    x = pb(x, LowpassFilter(lp), LowpassFilter(lp * 1.3))
    x = filt(x, 35, None, 2)
    x = crater_reverb(x, wet)
    return tail_cut(x, max_dur, fade)


def sfx_ice_crack_v11(rng, *, crack: str, crack_st: float, body: str, body_st: float,
                      second: str | None = None, second_at: float = 0.0, settle: int = 4):
    """Estalo de gelo gravado (~1,9 s). Camadas: a quebra de gelo do IgnasD (gelo de
    verdade) uns 3-5 semitons abaixo (vira placa maior), o corpo de uma quebra seca do
    rubberduck por baixo, o peso grave sintético de ruído (o mesmo da v10, nunca seno),
    uns microestalos tirados das próprias gravações de gelo se acomodando depois, e a
    convolução com o IR da capela pra soar de longe dentro da cratera."""
    tr = Track()
    tr.add(fades(repitch(ice_rec(crack), crack_st)), 0.0, 1.0)
    tr.add(fades(repitch(break_rec(body), body_st)), 0.004, 0.45)
    if second:
        tr.add(fades(repitch(ice_rec(second), crack_st - 1.5)), second_at, 0.55)
    tr.add(noise_burst(rng, 40, 220, 0.012, 0.22, 0.9, order=2), 0.01, 0.55)    # peso: só ruído
    pool = [ice_rec(n) for n in ("LedasLuzta", "LedasLuzta2", "LedasLuzta4")]
    for _ in range(settle):                                                      # acomodando
        g = repitch(grain(rng, pool[int(rng.integers(0, len(pool)))]), rng.uniform(-6, -2))
        tr.add(g, rng.uniform(0.3, 1.0), rng.uniform(0.08, 0.2))
    return ice_master(tr.render(1.0), lp=5200, wet=0.55, max_dur=1.95, fade=0.6)


def sfx_ice_crack_v11_0(rng):
    """Estalo A: uma quebra curta e seca (LedasLuzta4 a -4 st) sobre a quebra seca 02."""
    return sfx_ice_crack_v11(rng, crack="LedasLuzta4", crack_st=-4, body="breaking_02", body_st=-2)


def sfx_ice_crack_v11_1(rng):
    """Estalo B: a rachadura mais comprida do pack (LedasLuzta33, 1,3 s de cascata) a
    -3 st, com um segundo estalo menor 0,22 s depois, como a rachadura correndo."""
    return sfx_ice_crack_v11(rng, crack="LedasLuzta33", crack_st=-3, body="breaking_03", body_st=-3,
                             second="LedasLuzta2", second_at=0.22, settle=5)


def sfx_ice_collapse_v11(rng):
    """Desabamento (~2,4 s): a quebra grande de gelo (LedasLuzta5 a -5 st) com a quebra
    de pedra 01 por baixo, a placa cedendo (ronco grave de ruído, sintético, como na
    v10), o "whump" de ruído quando bate no fundo e os pedaços caindo: grãos e quebras
    curtas de gelo gravado e quedas de pedra gravadas, 2 a 7 semitons abaixo, cada vez
    mais raros. Tudo com o reverb da cratera um pouco mais molhado."""
    tr = Track()
    tr.add(fades(repitch(ice_rec("LedasLuzta5"), -5)), 0.0, 1.0)
    tr.add(fades(repitch(break_rec("rock_breaking_01"), -3)), 0.01, 0.5)
    tr.add(fades(repitch(ice_rec("LedasLuzta33"), -6)), 0.09, 0.45)
    n = ns(1.9)                                                                  # placa cedendo
    t = tvec(n)
    env = np.clip(t / 0.18, 0, 1) ** 1.5 * np.exp(-t / 0.7) * (0.75 + 0.25 * slow_noise(n, rng, 6.0, False))
    tr.add(norm_rms(filt(rng.standard_normal(n), 30, 260, 2)) * env, 0.05, 0.12)
    tr.add(noise_burst(rng, 35, 320, 0.01, 0.16, 0.8, order=1), 0.42, 0.55)      # "whump" no fundo
    ice_pool = [ice_rec(n_) for n_ in ("LedasLuzta", "LedasLuzta2", "LedasLuzta4")]
    rock_pool = [break_rec(n_) for n_ in ("rock_falling_03", "rock_falling_04", "rock_falling_06",
                                          "rock_falling_07", "rock_falling_08")]
    t0 = 0.3
    while True:                                                                  # pedaços caindo
        t0 += rng.exponential(1 / (16 * np.exp(-(t0 - 0.3) / 0.55) + 2.0))
        if t0 > 1.9:
            break
        fade = np.exp(-(t0 - 0.3) / 0.8)
        if rng.random() < 0.5:                                                   # bloco: queda gravada
            r = rock_pool[int(rng.integers(0, len(rock_pool)))]
            tr.add(fades(repitch(r[: ns(0.25)], rng.uniform(-7, -3)), 0.001, 0.06), t0, fade * rng.uniform(0.2, 0.4))
        else:                                                                    # lasca de gelo gravada
            g = repitch(grain(rng, ice_pool[int(rng.integers(0, len(ice_pool)))], (0.04, 0.12)), rng.uniform(-5, -1))
            tr.add(g, t0, fade * rng.uniform(0.15, 0.35))
    return ice_master(tr.render(2.0), lp=4800, wet=0.62, max_dur=2.45, fade=0.7)


def rec_loop(x: np.ndarray, L: float, X: float, pre=(0.3, 0.9)) -> np.ndarray:
    """Loop de L s a partir de uma gravação (já tratada) com crossfade de potência
    constante de X s: o fim do trecho entra por baixo do começo. A amostra depois da
    última é a continuação natural dela, então emenda sem estalo. O ponto de emenda é
    escolhido (determinístico) dentro de `pre` s: o lugar com menos agudo em volta, pra
    não cair em cima de uma gota mais forte."""
    n, m = ns(L), ns(X)
    hp = filt(x, 3000, None, 2)
    w = ns(0.004)
    best, a = None, ns(pre[0])
    for c in range(ns(pre[0]), ns(pre[1]), ns(0.002)):
        s = c + n                                    # amostra que vira a primeira do loop
        e = np.sum(hp[s - w:s + w] ** 2) + 4 * w * (x[s] - x[s - 1]) ** 2
        if best is None or e < best:
            best, a = e, c
    assert len(x) >= a + n + m, "trecho curto demais pro loop"
    out = x[a:a + n].copy()
    th = np.linspace(0, np.pi / 2, m, endpoint=False)
    out[:m] = x[a:a + m] * np.sin(th) + x[a + n:a + n + m] * np.cos(th)
    return out


def soften_drops(x: np.ndarray, ceil_db: float = 5.0) -> np.ndarray:
    """De-click leve: na banda acima de 2 kHz, segura cada gota mais forte a no máximo
    `ceil_db` acima do véu em volta (mediana de 1 s), com ganho suavizado em 3 ms. É a
    lição da tempestade: o véu fica, o "tic" isolado que se repetiria a cada volta do
    loop some. O resto do espectro não é tocado."""
    from numpy.lib.stride_tricks import sliding_window_view
    hi = filt(x, 2000, None, 4)
    lo = x - hi
    w = ns(0.005)
    env = np.sqrt(np.convolve(hi ** 2, np.ones(w) / w, "same")) + 1e-9
    e = env[::w]
    k = 100                                              # 100 × 5 ms = ±0,5 s
    med = np.median(sliding_window_view(np.pad(e, (k, k), mode="edge"), 2 * k + 1), axis=1)[: len(e)]
    g = np.minimum(1.0, med * 10 ** (ceil_db / 20) / e)
    g = np.interp(np.arange(len(x)), np.arange(len(g)) * w, g)
    s = ns(0.003)
    g = np.convolve(g, np.ones(s) / s, "same")
    return lo + hi * g


def rain_rec(seg: str) -> np.ndarray:
    return soften_drops(mono(V11_RAIN / f"amb_rain2_{seg}.flac"))


def amb_rain_v11_mid(rng):
    """Média: o trecho 404-432 s da gravação, passa-alta de 250 Hz (o grave é dos pads e
    do ronco do microfone), um passa-baixa suave de 6 kHz e loop de 24 s."""
    x = filt(rain_rec("404s-432s"), 250, 6000, 2)
    return rec_loop(x, 24.0, 3.0)


def amb_rain_v11_light(rng):
    """Fraca: o trecho mais calmo (520-548 s), mais escuro (passa-baixa de 3,2 kHz), como
    a chuva mais longe e mais fina. Loop de 24 s."""
    x = filt(rain_rec("520s-548s"), 280, 3200, 2)
    return rec_loop(x, 24.0, 3.0)


def amb_rain_v11_heavy(rng):
    """Forte: dois trechos diferentes somados (282-310 s e 318-346 s, sem relação entre
    si): o dobro de gotas por segundo, como um aguaceiro, com o topo um pouco mais
    aberto (passa-baixa de 7 kHz). Loop de 24 s."""
    x = rain_rec("282s-310s") + 0.85 * rain_rec("318s-346s")
    x = filt(x, 220, 7000, 2)
    return rec_loop(x, 24.0, 3.0)


def loop_vent_hiss_v11(rng):
    """Fumarola: o vapor da fumarola grande de Norris (NPS), do 4,5 s em diante (antes
    disso é o fade de entrada do arquivo), passa-alta de 60 Hz e passa-baixa de 3 kHz
    (é chiado grave, como na v10), loop de 20 s."""
    x = mono(V11_VENT)
    x = x[ns(4.0):]
    x = filt(x, 60, 3000, 2)
    return rec_loop(x, 20.0, 3.0)


# v11 APROVADA pelo dono ("por hora tá bom, deixa assim"): os 7 viraram oficiais e saem
# em assets/audio/ com a seed do nome (rng_for(nome)) e os mesmos alvos, idênticos byte
# a byte ao que ele ouviu em reports/audio/v11/. Precisam do pedalboard e do vendor: se
# faltar, o main() pula só esses 7 (o arquivo que já está lá fica) e avisa.
# Nota pra próxima rodada (dono): o gelo lembra um pouco "bater no esqueleto do
# Minecraft", meio osso/clack. Não mexer agora; revisitar quando refatorar os sons.
RECORDED: dict = {
    "ice_crack": (sfx_ice_crack_v11_0, False, -24.0),
    "ice_crack_1": (sfx_ice_crack_v11_1, False, -24.0),
    "ice_collapse": (sfx_ice_collapse_v11, False, -22.0),
    "amb_rain": (amb_rain_v11_mid, True, -29.0),
    "amb_rain_light": (amb_rain_v11_light, True, -32.0),
    "amb_rain_heavy": (amb_rain_v11_heavy, True, -27.0),
    "vent_hiss": (loop_vent_hiss_v11, True, -33.0),
}
SOUNDS.update(RECORDED)
PROPOSALS_V11: dict = {}   # promovidas; reports/audio/v11/ deixou de ser gerado


# ---------------------------------------------------------------------------
# v0.5 Marco 1 · construtor (v12, APROVADOS pelo dono)
# ---------------------------------------------------------------------------

def click(rng, at_gain=1.0, lo=500, hi=2800, dur=0.035):
    """Trava mecânica: ruído de banda larga + estalinho agudo, sem tom."""
    tr = Track()
    tr.add(noise_burst(rng, lo, hi, 0.0003, 0.006, dur, order=1), 0, 0.9 * at_gain)
    tr.add(noise_burst(rng, 2000, 7000, 0.0002, 0.0008, 0.006, order=1), 0, 0.4 * at_gain)
    tr.add(noise_burst(rng, None, 350, 0.001, 0.012, 0.05, order=2), 0.001, 0.35 * at_gain)
    return tr.render()


def scan_ticks(rng, tr, t0, t1, r0, r1, gain, lo=2500, hi=7000):
    """Tiquinhos de varredura, taxa subindo de r0 a r1 por segundo, timing irregular."""
    t = t0
    while t < t1:
        k = (t - t0) / (t1 - t0)
        tr.add(noise_burst(rng, lo, hi, 0.0002, 0.0012, 0.008, order=1), t, gain * (0.5 + 0.5 * k) * rng.uniform(0.6, 1.0))
        t += rng.uniform(0.6, 1.4) / (r0 + (r1 - r0) * k)


def sfx_build(rng):
    """Scanner construindo (~1,5 s): feixe de dente de serra filtrado subindo duas oitavas
    (Lá2 -> Lá4) com uma segunda voz em quinta e trêmolo de varredura, tiquinhos digitais
    acelerando; corta seco no 1,3 s e fecha com a trava: clack de banda larga + selo
    pneumático + bipe Mi5->Lá5 baixinho (família do equip)."""
    tr = Track()
    L = 1.3
    n = ns(L)
    t = tvec(n)
    k = t / L
    f = 110 * 4 ** k
    cut = 500 + 2600 * k
    beam = bl_wave(f, n, "saw", 3800)
    beam = filt(beam, None, 3200, 1)
    beam2 = bl_wave(f * 1.5 * 1.002, n, "tri", 3000)
    trem = 0.8 + 0.2 * np.sin(2 * np.pi * np.cumsum(14 + 22 * k) / SR)
    env = np.minimum(1, t / 0.06) * (0.35 + 0.65 * k ** 0.7) * np.clip((L - t) / 0.03, 0, 1)
    tr.add((beam * 0.6 + beam2 * 0.25) * trem * env, 0, 0.5)
    # brilho do feixe: banda de ruído larga subindo junto, bem baixa
    tr.add(noise_sweep(rng, L, 1200, 5000, 2.5) * env * 0.5, 0, 0.12)
    scan_ticks(rng, tr, 0.05, L, 14, 38, 0.16)
    # encaixe
    at = L + 0.04
    tr.add(click(rng), at, 0.85)
    nn = ns(0.12)
    tr.add(filt(rng.standard_normal(nn), 1500, 5000, 1) * bump(nn, 0.1) ** 2, at + 0.02, 0.1)
    for m, d in ((76, 0.06), (81, 0.11)):
        q = ns(0.14)
        tr.add(np.sin(phase_of(midi(m), q)) * perc(q, 0.003, 0.035), at + d, 0.15)
    return tail_cut(reverb(tr.render(), rng, decay=0.4, mix=0.1, lp=4000), 1.55, 0.12)


def sfx_dismantle_charge(rng):
    """Carga do desmonte (2,0 s), sobe até o fim. Zumbido de serra baixo (Lá2 -> Mi4, só
    uma oitava e meia), filtro abrindo, trêmolo acelerando de 5 a 26 Hz (a barrinha
    enchendo) e tiquinhos de contagem mais densos no fim. Entra em 15 ms e termina em
    fade de 25 ms. Sem estalo no começo. Pode ser cortado com fadeout (ver report)."""
    tr = Track()
    L = 1.98
    n = ns(L)
    t = tvec(n)
    k = t / L
    f = 110 * 2 ** (1.6 * k ** 1.3 * 1.0)
    saw = bl_wave(f, n, "saw", 3500)
    # filtro abrindo (mistura de duas versões filtradas)
    dark = filt(saw, None, 700, 1)
    bright = filt(saw, 300, 3200, 1)
    body = dark * (1 - k) + bright * k
    trem = 0.72 + 0.28 * np.sin(2 * np.pi * np.cumsum(5 + 21 * k ** 1.5) / SR)
    env = np.minimum(1, t / 0.015) * (0.3 + 0.7 * k ** 1.2) * np.clip((L - t) / 0.025, 0, 1)
    tr.add(body * trem * env, 0, 0.5)
    body2 = bl_wave(f * 2.0 * 1.003, n, "tri", 3000)
    tr.add(body2 * trem * env * k ** 1.5, 0, 0.18)
    tr.add(noise_sweep(rng, L, 800, 4500, 2.5) * env * k, 0, 0.07)
    scan_ticks(rng, tr, 0.1, L - 0.03, 5, 30, 0.14, 1800, 6000)
    return tr.render()   # sem reverb: a duração tem que ser a da barrinha (2,0 s)


def sfx_dismantle_done(rng):
    """Desmonte pronto (~0,6 s), o build ao contrário e menor: destrava (clack mais grave e
    seco), o feixe cai rápido (Lá4 -> Lá3, 0,16 s), selo pneumático soltando e três
    tiquinhos agudos espalhados (os materiais voltando). Sem bolha de seno, pra não
    lembrar o pickup."""
    tr = Track()
    tr.add(click(rng, 1.0, 350, 2000, 0.04), 0, 0.85)
    n = ns(0.17)
    t = tvec(n)
    f = 440 * 2 ** (-1.0 * t / 0.17)
    beam = filt(bl_wave(f, n, "saw", 3000), None, 2600, 1) * bump(n, 0.15) ** 1.2
    tr.add(beam, 0.04, 0.3)
    nn = ns(0.22)
    tr.add(filt(rng.standard_normal(nn), 1200, 5000, 1) * bump(nn, 0.12) ** 2, 0.06, 0.13)
    for at, m, g in ((0.2, 88, 0.1), (0.275, 93, 0.08), (0.35, 85, 0.07)):
        q = ns(0.06)
        tr.add(bl_wave(midi(m), q, "tri", 6000) * perc(q, 0.001, 0.012), at + rng.uniform(0, 0.012), g)
        tr.add(noise_burst(rng, 3000, 8000, 0.0002, 0.001, 0.006, order=1), at, 0.1)
    return reverb(tr.render(), rng, decay=0.35, mix=0.1, lp=4000)


def sfx_diagram_read(rng):
    """Leitura de diagrama (~1 s): "aprendi algo". Varredura curta de dados subindo
    (feixe rápido + quatro blips digitais Mi5-Lá5-Si5-Dó#6, mais lentos que o arpejo do
    blueprint_found e sem o pulse) e um sino macio de seno em Lá4 + Mi5 que assenta com
    o reverb. Termina mais baixo e calmo, enquanto o blueprint_found festeja no alto."""
    tr = Track()
    n = ns(0.2)
    t = tvec(n)
    f = 300 * 4 ** (t / 0.2)
    beam = filt(bl_wave(f, n, "saw", 4500), None, 4000, 1) * bump(n, 0.7)
    tr.add(beam, 0, 0.22)
    tr.add(noise_sweep(rng, 0.2, 1500, 6000, 2.5) * bump(n, 0.7), 0, 0.1)
    for i, m in enumerate((76, 81, 83, 85)):
        at = 0.14 + 0.065 * i
        q = ns(0.09)
        tr.add(bl_wave(midi(m), q, "square", 3500, 0.5) * perc(q, 0.002, 0.03), at, 0.15)
        q2 = ns(0.09)
        tr.add(np.sin(phase_of(midi(m + 12), q2)) * perc(q2, 0.002, 0.02), at, 0.06)
    for m, g in ((69, 0.5), (76, 0.32)):
        q = ns(0.9)
        tt = tvec(q)
        bell = (np.sin(phase_of(midi(m), q)) + 0.2 * np.sin(phase_of(midi(m) * 2.0, q))) * np.exp(-tt / 0.28)
        bell *= np.minimum(1, tt / 0.006)
        tr.add(bell, 0.43, g)
    return tail_cut(reverb(tr.render(), rng, decay=1.1, mix=0.24, lp=4500), 1.25, 0.35)


SOUNDS.update({
    "build": (sfx_build, False, -20.0),
    "dismantle_charge": (sfx_dismantle_charge, False, -26.0),
    "dismantle_done": (sfx_dismantle_done, False, -22.0),
    "diagram_read": (sfx_diagram_read, False, -22.0),
})


# ---------------------------------------------------------------------------
# v0.5 Marco 2 · base respirável (v13.1, APROVADOS pelo dono): porta (B, "shhhiii"), selo, zumbido do Dispersor,
# vazamento e Dispersor sem água. Geradores promovidos de tools/audio/build_v05_m2.py (que importa daqui). Cada som
# mantém a seed da proposta (4º item do SOUNDS), então o wav sai byte a byte igual ao aprovado.
# ---------------------------------------------------------------------------

def click_m2(rng, gain=1.0, lo=500, hi=2600, dur=0.03):
    """Trava mecânica leve: ruído de banda larga, sem tom."""
    tr = Track()
    tr.add(noise_burst(rng, lo, hi, 0.0003, 0.005, dur, order=1), 0, 0.8 * gain)
    tr.add(noise_burst(rng, 2000, 7000, 0.0002, 0.0007, 0.005, order=1), 0, 0.3 * gain)
    tr.add(noise_burst(rng, None, 300, 0.001, 0.010, 0.04, order=2), 0.001, 0.3 * gain)
    return tr.render()


def slide(rng, dur, lo=110, hi=1100, irregular=True):
    """Corrimão da porta: ruído de banda larga, envelope suave com leve tremor irregular."""
    n = ns(dur)
    x = filt(rng.standard_normal(n), lo, hi, 2)
    env = bump(n, 0.35)
    if irregular:
        wob = filt(rng.standard_normal(n), 8, 40, 1)
        wob = wob / (np.max(np.abs(wob)) + 1e-9)
        env = env * (0.8 + 0.2 * wob)
    return x * env


def servo(dur, f0, f1, gain_env=None):
    """Zumbido de servo bem discreto (dente de serra filtrada), glissando suave."""
    n = ns(dur)
    t = tvec(n)
    f = f0 + (f1 - f0) * t / dur
    x = filt(bl_wave(f, n, "saw", 1800), 80, 1500, 1) * bump(n, 0.3)
    return x


def sfx_base_sealed(rng):
    """~2,3 s. 'Pressurizou'. Selo pneumático (clack + 'tchss'), um sopro de ar que ENCHE e
    sobe (banda larga 300 Hz -> 4 kHz, crescendo) e um acorde de Lá maior sus2 -> maior (Lá3,
    Mi4, Lá4, Dó#5) que abre por baixo do sopro e assenta, com um sininho suave de seno em
    Lá5+Mi5 no fim ('ok, estável'). Sem seno grave com pitch (nada de tambor)."""
    tr = Track()
    tr.add(click_m2(rng, 1.0, 400, 2400, 0.04), 0.0, 0.8)
    m = ns(0.3)
    tr.add(filt(rng.standard_normal(m), 1200, 6000, 1) * bump(m, 0.06) ** 1.5, 0.01, 0.35)
    # sopro subindo
    L = 1.5
    n = ns(L)
    sweep = noise_sweep(rng, L, 300, 3800, 2.5)
    tr.add(sweep * bump(n, 0.75) ** 1.3, 0.12, 0.55)
    # acorde que abre
    for mn, d, g in ((57, 0.30, 0.22), (64, 0.42, 0.20), (69, 0.54, 0.17), (73, 0.66, 0.13)):
        q = ns(1.7)
        tt = tvec(q)
        x = (np.sin(phase_of(midi(mn), q)) + 0.25 * np.sin(phase_of(midi(mn) * 2, q))
             + 0.12 * np.sin(phase_of(midi(mn) * 3, q)))
        env = np.minimum(1, tt / 0.45) * np.exp(-np.maximum(0, tt - 0.5) / 0.7)
        tr.add(x * env, d, g)
    # sininho de confirmação
    for mn, d, g in ((81, 1.18, 0.20), (88, 1.27, 0.12)):
        q = ns(1.0)
        tt = tvec(q)
        bell = (np.sin(phase_of(midi(mn), q)) + 0.15 * np.sin(phase_of(midi(mn) * 2.0, q))) * np.exp(-tt / 0.3)
        tr.add(bell * np.minimum(1, tt / 0.005), d, g)
    return tail_cut(filt(reverb(tr.render(), rng, decay=1.3, mix=0.28, lp=4500), None, 7000, 2), 2.5, 0.5)


def shhh(rng, dur, up=True, attack=0.01, decay=0.2, rise=None):
    """Sibilo pneumático 'shhhiii': ruído de banda larga em 2 a 9 kHz cujo brilho sobe
    (ou desce) durante o som. Duas bandas em crossfade (média 1,8-4,5 kHz e aguda 4,5-9 kHz)."""
    n = ns(dur)
    t = tvec(n)
    k = t / dur
    if not up:
        k = 1 - k
    mid = filt(rng.standard_normal(n), 1800, 4500, 2)
    hi = filt(rng.standard_normal(n), 4500, 9000, 2)
    body = filt(rng.standard_normal(n), 700, 2200, 1)
    x = mid * (1 - 0.8 * k) + hi * (0.25 + 0.9 * k) + 0.25 * body
    if rise is None:
        env = np.minimum(1, t / attack) * np.exp(-t / decay)
    else:
        env = bump(n, rise) ** 1.2
    flut = 0.9 + 0.1 * filt(rng.standard_normal(n), 6, 30, 1) / 0.3
    return x * env * np.clip(flut, 0.7, 1.1)


def sfx_door_open_B(rng):
    """~0,75 s. Trava leve (clack) e na sequência o 'shhhiii' pneumático: ataque rápido, o
    brilho sobe de 2 para 9 kHz e a cauda some em ~0,6 s. Desliza por baixo, bem baixinho."""
    tr = Track()
    tr.add(click_m2(rng, 0.9), 0.0, 0.5)
    tr.add(shhh(rng, 0.72, True, 0.012, 0.22), 0.02, 0.8)
    tr.add(slide(rng, 0.4, 110, 900), 0.05, 0.22)
    tr.add(servo(0.3, 210, 330), 0.05, 0.06)
    return tail_cut(filt(reverb(tr.render(), rng, decay=0.35, mix=0.1, lp=6000), None, 9500, 2), 0.78, 0.12)


def sfx_door_close_B(rng):
    """~0,75 s. O ar entra: o 'shhhiii' cresce rápido, o brilho DESCE (pressão se igualando)
    e corta na trava seca (clack mais grave + 'tss'), que fecha o som. Open e close se
    distinguem pela trava: leve no começo, seca no fim."""
    tr = Track()
    tr.add(shhh(rng, 0.5, False, rise=0.3), 0.0, 0.8)
    tr.add(slide(rng, 0.4, 110, 900), 0.0, 0.22)
    tr.add(servo(0.3, 330, 200), 0.0, 0.06)
    tr.add(click_m2(rng, 1.0, 380, 2200, 0.035), 0.48, 1.0)
    m = ns(0.12)
    tr.add(filt(rng.standard_normal(m), 2500, 8000, 1) * bump(m, 0.08) ** 2, 0.495, 0.2)
    return tail_cut(filt(reverb(tr.render(), rng, decay=0.35, mix=0.1, lp=6000), None, 9500, 2), 0.74, 0.12)


def loop_dispenser_hum(rng):
    """Loop de 8 s: ar circulando, pra ficar 10 min dentro da base. Só banda larga escura
    (130 Hz a 1,3 kHz) com um sopro lento que vai e vem (circulação, período inteiro no
    loop), um drone muito baixo em Lá (55/110 Hz) e uma quinta bem leve, sem apito, sem
    tom estreito e sem agudo. Reverb circular curto pra dar volume de sala."""
    L = 8.0
    n = ns(L)
    t = tvec(n)
    air = norm_rms(filt(rng.standard_normal(n), 130, 1300, 2, circular=True))
    air_hi = norm_rms(filt(rng.standard_normal(n), 900, 2600, 1, circular=True))
    circ = 0.55 + 0.45 * periodic_ctrl(n, L, rng, 1, 3, 1.2)          # sopro lento
    bright = 0.3 + 0.7 * periodic_ctrl(n, L, rng, 1, 2, 1.0)
    x = air * circ * 0.9 + air_hi * bright * circ * 0.18
    drone = (np.sin(2 * np.pi * fr(55.0, L) * t + 0.3)
             + 0.6 * np.sin(2 * np.pi * fr(110.0, L) * t + 1.1)
             + 0.22 * np.sin(2 * np.pi * fr(164.8, L) * t + 2.0))
    drone *= 1 + 0.1 * np.sin(2 * np.pi * (1 / L) * t)
    x = x + norm_rms(drone) * 0.22
    x = reverb(x, rng, decay=1.1, mix=0.35, lp=2500, circular=True)
    return filt(x, 35, 2800, 2, circular=True)


def sfx_leak_alert(rng):
    """~0,85 s. Vazamento. Ar escapando: 'fsssh' de banda larga que cai de brilho (5 kHz -> 700 Hz),
    com tremor rápido de 17 Hz (ar passando por uma fresta) e um glissando suave descendo (Lá5
    -> Mi4, triângulo filtrada) que lê como 'pressão caindo'. Dominado por ruído e queda, sem
    nenhum bipe de onda quadrada: o o2_low são bipes quadrados F5->C5 em loop e o power_low
    é motor + bipe duplo Lá4. Aqui é sopro, nunca bipe."""
    tr = Track()
    L = 0.7
    n = ns(L)
    t = tvec(n)
    hiss = noise_sweep(rng, L, 3500, 600, 2.6)
    flutter = 0.65 + 0.35 * np.sin(2 * np.pi * np.cumsum(17 + 6 * np.exp(-t / 0.3)) / SR)
    env = np.minimum(1, t / 0.012) * np.exp(-t / 0.33)
    tr.add(hiss * flutter * env, 0, 0.7)
    q = ns(0.5)
    tq = tvec(q)
    f = 880 * 2 ** (-1.5 * (tq / 0.5) ** 0.8)
    gl = filt(bl_wave(f, q, "tri", 2500), 200, 2200, 1) * bump(q, 0.12) ** 1.1
    tr.add(gl, 0.02, 0.28)
    tr.add(click_m2(rng, 0.7, 600, 3000, 0.02), 0, 0.4)
    return tail_cut(filt(reverb(tr.render(), rng, decay=0.5, mix=0.12, lp=4000), None, 6500, 2), 0.95, 0.15)


def sfx_dispenser_dry(rng):
    """~1,6 s. Dispersor sem água: engasga e desliga. Três tossidas mecânicas (rajadas de ruído
    escuro 200 Hz-1,8 kHz com chacoalhar rápido, cada uma mais fraca e mais grave), o motor
    perdendo rotação (dente de serra filtrada 120 -> 38 Hz sumindo) e um 'clique' de relé +
    sopro curto de ar morrendo. Mecânico e pesado, o oposto do sopro agudo do leak_alert."""
    tr = Track()
    cough = [(0.0, 1.0, 1800), (0.30, 0.75, 1400), (0.62, 0.5, 1000)]
    for at, g, hi in cough:
        d = ns(0.2)
        td = tvec(d)
        x = filt(rng.standard_normal(d), 180, hi, 2)
        rattle = 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(np.full(d, 38.0)) / SR)
        tr.add(x * rattle * perc(d, 0.006, 0.07), at, 0.7 * g)
        tr.add(noise_burst(rng, None, 250, 0.004, 0.05, 0.12, order=2), at, 0.25 * g)
    L = 1.3
    n = ns(L)
    t = tvec(n)
    f = 38 + 85 * np.exp(-t / 0.45)
    mot = filt(bl_wave(f, n, "saw", 700), 40, 700, 1) * np.exp(-t / 0.55) * np.minimum(1, t / 0.02)
    tr.add(mot, 0.0, 0.55)
    tr.add(click_m2(rng, 0.8, 350, 2000, 0.035), 1.12, 0.7)
    m = ns(0.25)
    tr.add(filt(rng.standard_normal(m), 400, 2500, 1) * bump(m, 0.1) ** 2, 1.1, 0.1)
    return tail_cut(reverb(tr.render(), rng, decay=0.5, mix=0.14, lp=3500), 1.6, 0.2)

SOUNDS.update({
    "door_open": (sfx_door_open_B, False, -25.0, "v05m2:door_open_B"),
    "door_close": (sfx_door_close_B, False, -25.0, "v05m2:door_close_B"),
    "base_sealed": (sfx_base_sealed, False, -19.0, "v05m2:base_sealed"),
    "dispenser_hum": (loop_dispenser_hum, True, -34.0, "v05m2:dispenser_hum"),
    "leak_alert": (sfx_leak_alert, False, -21.0, "v05m2:leak_alert"),
    "dispenser_dry": (sfx_dispenser_dry, False, -23.0, "v05m2:dispenser_dry"),
})


def v11_ready() -> str | None:
    """None se dá pra gerar a v11; senão, o motivo."""
    import importlib.util
    import shutil
    if importlib.util.find_spec("pedalboard") is None:
        return "pedalboard não instalado (rode com: uv run python tools/audio/build_audio.py)"
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return "ffmpeg/ffprobe ausente"
    for p in (V11_RAIN, V11_ICE, V11_BREAK, V11_VENT, V11_IR):
        if not p.exists():
            return f"faltando {p.relative_to(ROOT)}"
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    meta = {}
    print(f"{'arquivo':<20}{'dur(s)':>8}{'pico dBFS':>11}{'loud dB':>9}")
    rec_skip = v11_ready()
    for name, (fn, loop, target, *seed) in SOUNDS.items():
        if name in RECORDED and rec_skip:
            print(f"{name}: pulado ({rec_skip}); o wav que já está em assets/audio fica")
            continue
        x = finalize(fn(rng_for(seed[0] if seed else name)), loop, target)
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
    rej_dir = PENDING_DIR / "rejected_v8"
    if REJECTED:
        rej_dir.mkdir(parents=True, exist_ok=True)
    for name, (fn, loop, target) in REJECTED.items():
        xi = write_wav(rej_dir / f"{name}.wav", finalize(fn(rng_for(name)), loop, target))
        xf = xi.astype(float) / 32768
        peak_db = 20 * np.log10(np.max(np.abs(xf)) + 1e-12)
        meta["rej:" + name] = {
            "file": f"_pending/rejected_v8/{name}.wav", "loop": False, "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(peak_db), 2), "loudness_db": round(float(loudness(xf, False)), 1),
            "wave": waveform_peaks(xi),
        }
        print(f"{'rejected_v8/' + name + '.wav':<20}{len(xi) / SR:>8.2f}{peak_db:>11.2f}")
    if PROPOSALS:
        PROP_DIR.mkdir(parents=True, exist_ok=True)
    for name, (fn, loop, target) in PROPOSALS.items():
        xi = write_wav(PROP_DIR / f"{name}.wav", finalize(fn(rng_for(name)), loop, target))
        xf = xi.astype(float) / 32768
        peak_db = 20 * np.log10(np.max(np.abs(xf)) + 1e-12)
        meta["prop:" + name] = {
            "file": f"v10/{name}.wav", "loop": loop, "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(peak_db), 2), "loudness_db": round(float(loudness(xf, loop)), 1),
            "wave": waveform_peaks(xi),
        }
        if loop:
            adj = np.abs(np.diff(xi.astype(int)))
            jump = abs(int(xi[0]) - int(xi[-1]))
            meta["prop:" + name]["seam_lsb"] = jump
            meta["prop:" + name]["seam_pct"] = round(float(100 * np.mean(adj < jump)), 1)
        print(f"{'v10/' + name + '.wav':<20}{len(xi) / SR:>8.2f}{peak_db:>11.2f}{loudness(xf, loop):>9.1f}")
    why = v11_ready() if PROPOSALS_V11 else "promovida pro SOUNDS"
    if why:
        print(f"v11 (proposta): {why}")
    else:
        V11_DIR.mkdir(parents=True, exist_ok=True)
        for name, (fn, loop, target) in PROPOSALS_V11.items():
            xi = write_wav(V11_DIR / f"{name}.wav", finalize(fn(rng_for(name)), loop, target))
            xf = xi.astype(float) / 32768
            peak_db = 20 * np.log10(np.max(np.abs(xf)) + 1e-12)
            meta["v11:" + name] = {
                "file": f"v11/{name}.wav", "loop": loop, "duration": round(len(xi) / SR, 3),
                "peak_db": round(float(peak_db), 2), "loudness_db": round(float(loudness(xf, loop)), 1),
                "wave": waveform_peaks(xi),
            }
            if loop:
                adj = np.abs(np.diff(xi.astype(int)))
                jump = abs(int(xi[0]) - int(xi[-1]))
                meta["v11:" + name]["seam_lsb"] = jump
                meta["v11:" + name]["seam_pct"] = round(float(100 * np.mean(adj < jump)), 1)
            print(f"{'v11/' + name + '.wav':<20}{len(xi) / SR:>8.2f}{peak_db:>11.2f}{loudness(xf, loop):>9.1f}")
    (REPORT_DIR / "audio_meta.js").write_text(
        "// gerado por tools/audio/build_audio.py, não editar\nwindow.AUDIO_META = "
        + json.dumps(meta, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"ok: {len(meta)} arquivos em {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
