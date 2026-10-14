"""Trilha do trailer do Hesper (90 s) + sfx de trailer. Tudo reprodutível (seeds fixas).

    python3 marketing/trailer/audio/build_trailer_audio.py

Saída (nesta pasta):
  trailer_music.wav   44,1 kHz, 16-bit, estéreo, 90,000 s, ~-14 LUFS, true peak <= -1 dBTP
  trailer_music.json  seções, hits e grade de tempo pro vídeo sincronizar
  sfx/                cópias (byte a byte) de sons do jogo + 4 sfx de trailer novos
  _meta.json          medições (usado pelo index.html)

Usa os utilitários de síntese do tools/audio/build_audio.py (só importa, não regera nada do
jogo) e gravações CC0 do tools/audio/vendor/ (gelo IgnasD, pedra rubberduck, chuva Kresiek),
decodificadas via ffmpeg. O reverb da música é sintético: o IR da capela de Aachen (CC BY)
NÃO entra na trilha. Ele só existe dentro das cópias ice_crack*/ice_collapse do sfx/.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import wave
import zlib
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audio"))
import build_audio as ba  # noqa: E402
from build_audio import (SR, bl_wave, bump, band_gain, bw_mag, filt, make_ir, midi, norm_rms,  # noqa: E402
                         ns, repitch, sand_veil, slow_noise, tv_filter, tvec)

DUR = 90.0
N = ns(DUR)
SEED = 20261014
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
SFX_DIR = HERE / "sfx"
ASSETS = ROOT / "assets" / "audio"


def R(name: str) -> np.random.Generator:
    return np.random.default_rng(SEED + zlib.crc32(name.encode()))


# ---------------------------------------------------------------------------
# utilidades estéreo
# ---------------------------------------------------------------------------

def st(x: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """mono -> estéreo com pan de potência constante (pan -1..1, 0 = centro sem ganho extra)."""
    if x.ndim == 2:
        return x
    gl = np.cos((pan + 1) * np.pi / 4) * np.sqrt(2)
    gr = np.sin((pan + 1) * np.pi / 4) * np.sqrt(2)
    return np.stack([x * gl, x * gr], axis=1)


class Bus:
    """Trecho estéreo da linha do tempo, de t0 a t1 (segundos absolutos)."""

    def __init__(self, t0: float, t1: float) -> None:
        self.t0, self.t1 = t0, t1
        self.x = np.zeros((ns(t1 - t0), 2))

    def add(self, sig: np.ndarray, t: float, gain: float = 1.0, pan: float = 0.0) -> None:
        s = st(sig, pan) * gain
        i = ns(t - self.t0)
        if i < 0:
            s, i = s[-i:], 0
        m = min(len(s), len(self.x) - i)
        if m > 0:
            self.x[i:i + m] += s[:m]

    def time(self) -> np.ndarray:
        return self.t0 + tvec(len(self.x))


def filt2(x: np.ndarray, lo=None, hi=None, order: int = 2) -> np.ndarray:
    """filt() do build_audio canal a canal (ele é 1-D)."""
    if x.ndim == 1:
        return filt(x, lo, hi, order)
    return np.stack([filt(x[:, c], lo, hi, order) for c in range(x.shape[1])], axis=1)


def rms(x) -> float:
    return float(np.sqrt(np.mean(np.asarray(x) ** 2)) + 1e-12)


def ar(n: int, a: float, r: float) -> np.ndarray:
    """Envelope com subida e descida em cosseno (a, r em segundos)."""
    t = tvec(n)
    dur = n / SR
    up = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / max(a, 1e-4), 0, 1))
    dn = 0.5 - 0.5 * np.cos(np.pi * np.clip((dur - t) / max(r, 1e-4), 0, 1))
    return up * dn


def pts(points, t: np.ndarray) -> np.ndarray:
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def perc(n: int, attack: float, decay: float) -> np.ndarray:
    return ba.perc(n, attack, decay)


def st_reverb(x: np.ndarray, name: str, decay: float, lp: float = 5000.0, predelay: float = 0.02) -> np.ndarray:
    """Reverb sintético estéreo (um IR de ruído diferente por canal = largura). Devolve só o
    molhado, mesmo comprimento da entrada + cauda."""
    x = st(x)
    irs = [make_ir(R(f"{name}-ir{c}"), decay, lp, predelay) for c in range(2)]
    n = len(x) + max(len(i) for i in irs)
    F = 1 << (n - 1).bit_length()
    out = np.zeros((n, 2))
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], F) * np.fft.rfft(irs[c], F), F)[:n]
    return out


def with_reverb(x: np.ndarray, name: str, decay: float, mix: float, lp: float = 5000.0,
                predelay: float = 0.02) -> np.ndarray:
    x = st(x)
    w = st_reverb(x, name, decay, lp, predelay)
    out = w * mix
    out[:len(x)] += x
    return out


def lp_sweep(x: np.ndarray, t_abs: np.ndarray, points, lo: float | None = None) -> np.ndarray:
    """Passa-baixa que anda no tempo (cutoff por breakpoints em segundos absolutos)."""
    cut = pts(points, t_abs)
    n = len(x)
    out = np.zeros_like(x)
    for c in range(x.shape[1]):
        out[:, c] = tv_filter(x[:, c], lambda tc, f: bw_mag(f, lo, cut[min(n - 1, max(0, int(tc * SR)))], 2))
    return out


def voice(f: float, dur: float, rng, harm=(1.0, 0.2, 0.07), det: float = 6.0) -> np.ndarray:
    """Voz de pad estéreo: senoides levemente desafinadas (cents) diferentes em cada lado."""
    n = ns(dur)
    t = tvec(n)
    out = np.zeros((n, 2))
    drift = 1 + 0.0015 * (slow_noise(n, rng, 0.3, False) - 0.5)
    for c, cents in ((0, (-det, det * 0.4)), (1, (det, -det * 0.4))):
        for ce in cents:
            fd = f * 2 ** (ce / 1200)
            ph = 2 * np.pi * np.cumsum(fd * drift) / SR
            for k, a in enumerate(harm, 1):
                if k * fd > 15000:
                    break
                out[:, c] += a * np.sin(k * ph + rng.uniform(0, 2 * np.pi))
    return out / (2 * sum(harm))


def saw_voice(f: float, dur: float, rng, cutoff: float, det: float = 8.0) -> np.ndarray:
    n = ns(dur)
    out = np.zeros((n, 2))
    for c, cents in ((0, (-det, det * 0.3)), (1, (det, -det * 0.3))):
        for ce in cents:
            out[:, c] += bl_wave(f * 2 ** (ce / 1200), n, "saw", cutoff, ph0=rng.uniform(0, 6.28))
    return out / 2


def chord(notes, dur, rng, a, r, kind="sine", cutoff=1400.0, harm=(1.0, 0.2, 0.07), low_gain=0.8):
    out = np.zeros((ns(dur), 2))
    for m in notes:
        g = low_gain if m < 40 else (1.0 if m < 62 else 0.6)
        if kind == "saw":
            v = saw_voice(midi(m), dur, rng, cutoff)
        else:
            v = voice(midi(m), dur, rng, harm)
        out += g * v
    return out * ar(len(out), a, r)[:, None] / np.sqrt(len(notes))


# ---------------------------------------------------------------------------
# gravações (CC0) e sons do jogo
# ---------------------------------------------------------------------------

ICE = ba.V11_ICE
BRK = ba.V11_BREAK
RAIN = ba.V11_RAIN


def rec(path: Path) -> np.ndarray:
    return ba.mono(path)


def ice_hit(name: str, semis: float, lp: float = 5000.0, trim: float | None = None) -> np.ndarray:
    x = rec(ICE / f"{name}.ogg")
    x = x / (np.max(np.abs(x)) + 1e-12)
    x = repitch(x, semis)
    if trim:
        x = x[:ns(trim)]
    x = filt(x, 60, lp, 2)
    return ba.fades(x, 0.001, 0.08)


def game_wav(name: str) -> np.ndarray:
    with wave.open(str(ASSETS / f"{name}.wav"), "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768
    return d


def noise(rng, n: int) -> np.ndarray:
    return rng.standard_normal(n)


def boom(rng, dur: float = 2.5, decay: float = 0.8, hi: float = 140.0) -> np.ndarray:
    """Impacto grave só de ruído (nada de seno com pitch caindo: regra do 'tambor')."""
    n = ns(dur)
    sub = norm_rms(filt(filt(noise(rng, n), 22, hi, 4), None, hi, 2)) * perc(n, 0.003, decay)
    body = norm_rms(filt(noise(rng, n), 90, 600, 2)) * perc(n, 0.002, decay * 0.25) * 0.35
    return sub + body


def thump(rng, dur: float = 0.35, decay: float = 0.09, hi: float = 110.0, click: float = 0.12) -> np.ndarray:
    """Pulso grave de ruído filtrado (o 'bumbo' da trilha, sem corpo tonal)."""
    n = ns(dur)
    low = norm_rms(filt(noise(rng, n), 25, hi, 4)) * perc(n, 0.002, decay)
    mid = norm_rms(filt(noise(rng, n), 120, 400, 2)) * perc(n, 0.001, decay * 0.35) * 0.3
    clk = norm_rms(filt(noise(rng, n), 1500, 5000, 2)) * perc(n, 0.0005, 0.003) * click
    return ba.soft_sat(low + mid + clk, 2.2) * 1.1   # segura o pico do ruído (crest menor)


def whoosh(rng, dur: float = 1.3, peak: float = 0.62, lo=200.0, hi=6000.0) -> np.ndarray:
    """Whoosh estéreo: banda larga que sobe e desce passando da esquerda pra direita."""
    n = ns(dur)
    t = tvec(n)
    env = bump(n, peak) ** 1.6
    fc = lo * (hi / lo) ** env
    out = np.zeros((n, 2))
    for c in range(2):
        out[:, c] = tv_filter(noise(rng, n), lambda tc, f: band_gain(f, fc[min(n - 1, max(0, int(tc * SR)))], 2.2))
    out = out / rms(out) * env[:, None]
    pan = np.clip(-0.8 + 1.6 * t / (n / SR), -1, 1)
    out[:, 0] *= np.cos((pan + 1) * np.pi / 4) * np.sqrt(2)
    out[:, 1] *= np.sin((pan + 1) * np.pi / 4) * np.sqrt(2)
    return out


def reverse_swell(rng, dur: float, name: str) -> np.ndarray:
    """'Sugada' antes de um corte: gelo + ruído com reverb, de trás pra frente. Termina no pico."""
    crack = ice_hit("LedasLuzta33", -5, 4500)
    nz = norm_rms(filt(noise(rng, ns(0.6)), 300, 5000, 2)) * perc(ns(0.6), 0.001, 0.12) * 0.3
    src = np.zeros(ns(dur))
    src[:len(crack)] += crack[:len(src)] / np.max(np.abs(crack))
    src[:len(nz)] += nz
    wet = st_reverb(src, name, decay=dur * 1.1, lp=6000, predelay=0.0)[:ns(dur)]
    out = (0.25 * st(src) + wet)[::-1]
    t = tvec(len(out))
    out *= ((t / (dur)) ** 2.2)[:, None]
    return out / (np.max(np.abs(out)) + 1e-12)


# ---------------------------------------------------------------------------
# seções
# ---------------------------------------------------------------------------

def sec_storm() -> Bus:
    """0-12 s · pouso na tempestade: vento, poeira, drone grave, tensão contida. O vento vai
    morrendo até ~18 s por baixo do pulso."""
    rng = R("storm")
    b = Bus(0.0, 19.0)
    n = len(b.x)
    t = b.time()
    lev = pts([(0, 0.0), (1.2, 0.5), (3.0, 0.95), (4.6, 0.7), (6.8, 1.0), (8.6, 0.8), (9.6, 0.65),
               (11.0, 0.55), (12.0, 0.45), (15.0, 0.18), (19.0, 0.0)], t)
    lev = lev * (0.82 + 0.18 * slow_noise(n, rng, 0.6, False))
    cut = 200 + 1500 * lev ** 1.6
    for c in range(2):
        body = tv_filter(noise(rng, n), lambda tc, f: bw_mag(f, 35, cut[min(n - 1, max(0, int(tc * SR)))], 2))
        b.x[:, c] += norm_rms(body) * lev * 0.10
    # uivo distante (banda de ~0,4 oitava passeando), centro levemente à esquerda
    fc = 160 * 2 ** (1.0 * slow_noise(n, rng, 0.15, False))
    hw = tv_filter(noise(rng, n), lambda tc, f: band_gain(f, fc[min(n - 1, max(0, int(tc * SR)))], 0.4))
    b.add(norm_rms(hw) * lev ** 1.3 * 0.045, 0.0, pan=-0.3)
    # poeira bem no fundo
    for c in range(2):
        b.x[:, c] += sand_veil(n, rng, False, 900, 3500) * lev ** 2 * 0.015
    b.add(norm_rms(filt(noise(rng, n), 25, 140, 2)) * lev * 0.06, 0.0)  # tremor grave
    b.x = filt2(b.x, None, 4200, 2)                                  # "capacete"
    # drone grave em Lá (quinta vazia) entrando devagar + Sib meio-tom acima no fim (tensão)
    dr = Bus(0.0, 19.0)
    for m, g in ((33, 0.9), (40, 0.6), (45, 0.5)):
        dr.add(voice(midi(m), 19.0, rng, (1.0, 0.3, 0.1), det=5), 0.0, g)
    dr.x *= pts([(0, 0), (1.0, 0.2), (8, 0.7), (11.8, 1.0), (13, 0.55), (18.5, 0.0)], t)[:, None]
    rub = voice(midi(46), 6.0, rng, (1.0, 0.15), det=4) * ar(ns(6.0), 3.0, 1.8)[:, None]
    dr.add(rub, 7.0, 0.22)                                                # Sib2 roçando o Lá
    hi = voice(midi(76), 13.0, rng, (1.0,), det=9) * ar(ns(13.0), 5.0, 2.0)[:, None]
    dr.add(hi, 0.5, 0.05)                                                 # Mi5 fino, frio
    dr.x = filt2(dr.x, None, 900, 2)
    dr.x += st_reverb(dr.x, "storm-drone", 6.0, 2200)[:len(dr.x)] * 0.5
    b.x += dr.x * 0.4
    # pouso (~9,6 s): baque de ruído + pedrinhas caindo (rubberduck, CC0) abafadas
    land = boom(rng, 3.0, 0.7, 120) * 0.9
    deb = repitch(rec(BRK / "bfh1_rock_falling_03.ogg"), -4)
    deb = filt(deb / np.max(np.abs(deb)), 80, 2500, 2) * 0.35
    lt = Bus(0, 4.0)
    lt.add(land, 0.0)
    lt.add(deb, 0.12, pan=0.25)
    lt.x += st_reverb(lt.x, "land", 2.2, 1800)[:len(lt.x)] * 0.6
    b.add(lt.x, 9.6, 0.4)
    return b


def build_chords():
    # (início, fim, raiz do baixo, voicing do pad, notas do arpejo)
    A = (33, (57, 59, 64, 69, 71), (69, 71, 76, 81))        # A add9
    F = (29, (53, 57, 60, 64, 71), (65, 69, 71, 76))        # F maj7(#11): o Si natural é a estranheza
    D = (38, (54, 57, 62, 64, 69), (66, 69, 74, 76))        # D add9
    E = (28, (52, 57, 59, 64, 71), (64, 69, 71, 76))        # E sus4
    seq = [A, F, D, E, A, F, E]
    out = []
    t = 12.0
    for i, c in enumerate(seq):
        dur = 2 * BAR
        out.append((t, t + dur) + c)
        t += dur
    return out  # termina em 40,0


def sec_build(events: list) -> Bus:
    """12-40 s · construir e explorar: pulso a 120 BPM, crescendo em camadas a cada 8 s."""
    rng = R("build")
    b = Bus(12.0, 41.0)
    chords = build_chords()
    T0, T1 = 12.0, 40.0
    eighths = np.arange(T0, T1 - 1e-6, BEAT / 2)
    # --- baixo em colcheias (ostinato), filtro abrindo 12 -> 40
    bass = Bus(12.0, 41.0)
    pat = [0, 0, 12, 0, 0, 12, 0, 7]
    for k, tt in enumerate(eighths):
        c = next(c for c in chords if c[0] <= tt < c[1])
        root = c[2] + 12 if c[2] < 33 else c[2]
        m = root + pat[k % 8]
        cutoff = float(np.interp(tt, [12, 20, 36, 40], [300, 450, 1300, 1700]))
        n = ns(0.26)
        x = bl_wave(midi(m), n, "saw", cutoff) * 0.8 + 0.5 * np.sin(2 * np.pi * midi(root - 12 if root > 40 else root) * tvec(n))
        x *= perc(n, 0.004, 0.11) * np.clip((0.26 - tvec(n)) / 0.04, 0, 1)
        acc = 1.0 if k % 2 == 0 else 0.75
        bass.add(x, tt, acc)
    bass.x *= pts([(12, 0.0), (12.02, 0.7), (20, 0.85), (28, 1.0), (40, 1.0)], bass.time())[:, None]
    # --- pad (saw filtrado) acompanhando os acordes, crescendo
    pad = Bus(12.0, 41.0)
    for (a, z, _r, voicing, _arp) in chords:
        cut = float(np.interp(a, [12, 28, 36], [700, 1400, 2200]))
        pad.add(chord(voicing, z - a + 0.6, rng, 0.25, 0.6, "saw", cut), a)
    pad.x *= pts([(12, 0.35), (20, 0.55), (28, 0.8), (36, 1.0), (40, 1.0)], pad.time())[:, None]
    pad.x += st_reverb(pad.x, "build-pad", 3.5, 3000)[:len(pad.x)] * 0.35
    # --- pulso grave (semínimas) a partir de 20 s; batida de mão em 2 e 4 a partir de 28 s
    beats = np.arange(20.0, T1 - 1e-6, BEAT)
    kick_times = list(beats)
    kick = Bus(12.0, 41.0)
    for tt in kick_times:
        kick.add(thump(R(f"k{tt:.2f}")), tt, 1.0)
    snare = Bus(12.0, 41.0)
    for tt in np.arange(28.0 + BEAT, T1 - 1e-6, 2 * BEAT):
        r = R(f"s{tt:.2f}")
        n = ns(0.4)
        e = np.zeros(n)
        for off, dc in ((0.0, 0.006), (0.009, 0.006), (0.019, 0.07)):
            i = ns(off)
            e[i:] += perc(n - i, 0.0005, dc)
        x = norm_rms(filt(noise(r, n), 700, 6000, 2)) * e * 0.5
        snare.add(x, tt, pan=0.05)
    snare.x += st_reverb(snare.x, "snare", 1.4, 4500)[:len(snare.x)] * 0.5
    # chimbal em semicolcheias a partir de 24 s (bem baixo, escuro)
    hats = Bus(12.0, 41.0)
    for k, tt in enumerate(np.arange(24.0, T1 - 1e-6, BEAT / 4)):
        r = R(f"h{k}")
        open_ = tt >= 32.0 and k % 4 == 2
        n = ns(0.25 if open_ else 0.06)
        x = filt(noise(r, n), 6000, 11000, 2) * perc(n, 0.0005, 0.05 if open_ else 0.012)
        acc = (1.0, 0.45, 0.7, 0.45)[k % 4]
        hats.add(x * acc, tt, 0.12, pan=0.3 if k % 2 else -0.15)
    hats.x *= pts([(24, 0.5), (32, 1.0), (40, 1.0)], hats.time())[:, None]
    # picaretada de verdade (mine_hit do jogo) como percussão, sincopada, 28-36 s
    tick = game_wav("mine_hit")
    for k, tt in enumerate(np.arange(28.0, 36.0 - 1e-6, BEAT / 4)):
        if k % 16 in (3, 6, 11, 14):
            r = R(f"t{k}")
            x = repitch(tick, float(r.uniform(-1.5, 0.5)))
            hats.add(x, tt, 0.28, pan=float(r.uniform(-0.5, 0.5)))
    # --- arpejo (semicolcheias) a partir de 20 s, com eco ping-pong de colcheia pontuada
    arp = Bus(12.0, 41.0)
    up_down = [0, 1, 2, 3, 2, 1, 2, 3]
    for k, tt in enumerate(np.arange(20.0, T1 - 1e-6, BEAT / 4)):
        c = next(c for c in chords if c[0] <= tt < c[1])
        m = c[4][up_down[k % 8]]
        n = ns(0.3)
        f = midi(m)
        tv = tvec(n)
        x = (np.sin(2 * np.pi * f * tv) + 0.25 * np.sin(4 * np.pi * f * tv) + 0.08 * np.sin(6 * np.pi * f * tv))
        x *= perc(n, 0.002, 0.075)
        arp.add(x, tt, 0.9 if k % 4 == 0 else 0.6, pan=-0.35 if k % 2 else 0.35)
    d = ns(0.75 * BEAT)
    wet = np.zeros_like(arp.x)
    tap = arp.x.copy()
    for i in range(1, 4):
        tap = filt2(tap, None, 3000, 1) * 0.4
        sh = np.roll(tap[:, ::-1] if i % 2 else tap, d * i, axis=0)
        sh[:d * i] = 0
        wet += sh
    arp.x = (arp.x + wet) * pts([(20, 0.45), (28, 0.75), (36, 1.0), (40, 1.0)], arp.time())[:, None]
    # --- máquinas (machine_hum do jogo) quase escondidas, 20-40
    hum = np.tile(game_wav("machine_hum"), 6)[:ns(20.0)] * ar(ns(20.0), 4.0, 1.0)
    # --- sidechain: pad e baixo abaixam a cada pulso
    sc = np.ones(len(b.x))
    for tt in kick_times:
        i = ns(tt - 12.0)
        n = min(ns(0.3), len(sc) - i)
        sc[i:i + n] = np.minimum(sc[i:i + n], 1 - 0.45 * np.exp(-tvec(n) / 0.09))
    # --- subida 36-40: ruído abrindo + rufar
    rise = Bus(36.0, 40.0)
    n = len(rise.x)
    tr = tvec(n)
    env = (tr / 4.0) ** 2.4
    cut = 300 * (30 ** (tr / 4.0))
    for c in range(2):
        y = tv_filter(noise(rng, n), lambda tc, f: bw_mag(f, 150, cut[min(n - 1, max(0, int(tc * SR)))], 2))
        rise.x[:, c] = norm_rms(y) * env * 0.17
    roll = Bus(38.0, 40.0)
    steps = list(np.arange(38.0, 39.0 - 1e-6, BEAT / 4)) + list(np.arange(39.0, 40.0 - 1e-6, BEAT / 8))
    for k, tt in enumerate(steps):
        r = R(f"roll{k}")
        n2 = ns(0.12)
        x = norm_rms(filt(noise(r, n2), 700, 6000, 2)) * perc(n2, 0.0005, 0.03)
        roll.add(x, tt, 0.04 + 0.11 * (tt - 38.0) / 2.0, pan=0.0)
    # --- mix da seção
    b.x += bass.x * sc[:, None] * 0.55
    b.x += pad.x * sc[:, None] * 0.30
    b.x += kick.x * 0.45
    b.x += snare.x * 0.30
    b.x += hats.x
    b.x += arp.x * 0.16
    b.add(hum, 20.0, 0.10)
    b.add(rise.x, 36.0, 1.0)
    b.add(roll.x, 38.0, 1.0)
    # respiro de 70 ms antes do hit de 40 s
    t = b.time()
    b.x[t >= 39.92] = 0
    fo = (t >= 39.90) & (t < 39.92)
    b.x[fo] *= np.linspace(1, 0, int(fo.sum()))[:, None]
    for i, tt in enumerate(np.arange(12.0, 40.0 - 1e-6, BAR)):
        events.append({"t": round(float(tt), 3), "kind": "bar", "label": f"compasso {i + 1}"})
    return b


def sec_open(events: list) -> Bus:
    """40-55 s · o planeta muda: sem bateria, pads largos em Lá maior, melodia lenta, chuva."""
    rng = R("open")
    b = Bus(39.9, 56.0)
    prog = [
        (40.0, 44.6, (33, 45, 52, 57, 61, 64, 71)),        # A add9
        (44.0, 48.6, (38, 50, 57, 61, 66, 69, 73)),        # D maj7
        (48.0, 51.9, (42, 54, 57, 61, 64, 68)),            # F#m9
        (51.3, 54.0, (40, 52, 57, 59, 64, 71)),            # E sus4
        (53.0, 55.0, (41, 53, 57, 60, 64, 71)),            # F maj7(#11): a estranheza volta
    ]
    pad = Bus(39.9, 56.0)
    for i, (a, z, notes) in enumerate(prog):
        att = 0.02 if i == 0 else 0.7
        pad.add(chord(notes, z - a, rng, att, 0.8, "sine", harm=(1.0, 0.25, 0.1, 0.04)), a)
    pad.x = filt2(pad.x, 30, 3200, 1)
    pad.x += st_reverb(pad.x, "open-pad", 6.5, 3200)[:len(pad.x)] * 0.55
    # melodia lenta (triângulo suave com vibrato que chega devagar)
    mel = [(40.6, 76, 1.4), (42.0, 73, 1.0), (43.0, 71, 1.1),
           (44.2, 78, 1.3), (45.5, 76, 1.0), (46.5, 73, 1.6),
           (48.2, 73, 0.9), (49.1, 76, 0.9), (50.0, 80, 1.4),
           (51.5, 81, 1.0), (52.5, 83, 2.4)]
    lead = Bus(39.9, 56.0)
    for (tt, m, d) in mel:
        n = ns(d + 0.4)
        tv = tvec(n)
        vib = 1 + 0.004 * np.clip((tv - 0.25) / 0.4, 0, 1) * np.sin(2 * np.pi * 5.2 * tv)
        x = bl_wave(midi(m) * vib, n, "tri", 3000) * ar(n, 0.07, 0.45)
        lead.add(x, tt, 0.8, pan=0.1)
    lead.x += st_reverb(lead.x, "lead", 4.5, 5000)[:len(lead.x)] * 0.7
    # brilhos em colcheias (arpejo bem leve, delay longo)
    spark = Bus(39.9, 56.0)
    for k, tt in enumerate(np.arange(40.0, 53.5, BEAT / 2)):
        notes = next(p[2] for p in prog[::-1] if p[0] <= tt)
        hi_n = [m + 12 for m in notes if 57 <= m < 72]
        m = hi_n[(k * 3) % len(hi_n)]
        n = ns(0.6)
        tv = tvec(n)
        x = (np.sin(2 * np.pi * midi(m) * tv) + 0.2 * np.sin(4 * np.pi * midi(m) * tv)) * perc(n, 0.002, 0.18)
        spark.add(x, tt, 0.5, pan=float(np.sin(k * 0.9)) * 0.6)
    spark.x += st_reverb(spark.x, "spark", 5.0, 6500)[:len(spark.x)] * 0.9
    # chuva de verdade (Kresiek, CC0), longe e baixa
    rain = ba.decode(RAIN / "amb_rain2_404s-432s.flac")
    rain = rain[ns(2.0):ns(2.0) + ns(14.0)]
    rain = st(rain[:, 0]) if rain.shape[1] == 1 else rain[:, :2]
    rain = filt2(rain, 280, 5000, 2)
    rain = rain / rms(rain) * ar(len(rain), 4.0, 0.3)[:, None]
    # hit de 40 s: abertura (ruído grave + lavada larga), sem tom
    hit = Bus(40.0, 46.0)
    hit.add(boom(R("hit40"), 3.0, 0.9, 130), 40.0, 0.9)
    n = ns(4.0)
    wash = np.stack([filt(noise(R(f"wash{c}"), n), 2500, 9000, 1) for c in range(2)], 1)
    hit.add(wash / rms(wash) * perc(n, 0.004, 1.1)[:, None], 40.0, 0.1)
    hit.x += st_reverb(hit.x, "hit40", 3.5, 5000)[:len(hit.x)] * 0.5
    # mix
    b.x += pad.x * 0.62 + lead.x * 0.15 + spark.x * 0.08
    b.add(rain, 41.0, 0.06)
    b.add(hit.x, 40.0, 0.5)
    t = b.time()
    # o fim: fecha o filtro e afunda 53,6 -> 55,0, depois "cai"
    tail = t >= 53.0
    b.x[tail] = lp_sweep(b.x[tail], t[tail], [(53.0, 16000), (53.6, 9000), (54.95, 260)])
    b.x *= pts([(39.9, 1), (53.6, 1), (54.9, 0.55), (55.0, 0.0), (56, 0)], t)[:, None]
    b.add(reverse_swell(R("rev55"), 1.6, "rev55"), 55.0 - 1.6, 0.16)
    events.append({"t": 40.0, "kind": "hit", "label": "abertura (a cratera derrete)"})
    events.append({"t": 44.0, "kind": "cue", "label": "acorde 2 (Ré maj7)"})
    events.append({"t": 48.0, "kind": "cue", "label": "acorde 3 (Fá# m9)"})
    events.append({"t": 53.0, "kind": "cue", "label": "estranheza volta, filtro começa a fechar"})
    return b


def sec_cold(events: list) -> Bus:
    """55-75 s · a virada: tudo cai pra um drone frio, cluster dissonante, gelo estalando."""
    rng = R("cold")
    b = Bus(55.0, 77.0)
    t = b.time()
    dur = 22.0
    # drone: Lá1 + Sib1 (batimento lento e inquieto) + Mi2, e trítono no meio (Mib3)
    drn = Bus(55.0, 77.0)
    for m, g in ((33, 1.0), (34, 0.55), (40, 0.5), (51, 0.25), (57, 0.12)):
        drn.add(voice(midi(m), dur, rng, (1.0, 0.35, 0.15, 0.06), det=3), 55.0, g)
    drn.x = filt2(drn.x, 25, 900, 2)
    breath = 0.65 + 0.35 * (0.5 - 0.5 * np.cos(2 * np.pi * (t - 55.0) / 6.0))
    drn.x *= (breath * pts([(55, 0.0), (55.08, 1.0), (72, 1.0), (75.2, 0.08), (77, 0.0)], t))[:, None]
    # agudo frio que escorrega meio-tom em 18 s (Mi5 -> Mib5) com trêmolo lento
    n = ns(19.0)
    tv = tvec(n)
    f = midi(76) * 2 ** (-tv / 18.0 / 12)
    gl = np.zeros((n, 2))
    for c, dt in ((0, 0.997), (1, 1.003)):
        gl[:, c] = np.sin(2 * np.pi * np.cumsum(f * dt) / SR + c)
    gl *= (ar(n, 5.0, 3.0) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.23 * tv)))[:, None]
    drn.add(gl, 56.0, 0.07)
    # pad dissonante que respira (Sib3 Mi4 Fá4)
    dpad = chord((58, 64, 65), 16.0, rng, 4.0, 4.0, "sine", harm=(1.0, 0.1))
    drn.add(dpad, 58.0, 0.25)
    drn.x += st_reverb(drn.x, "cold-drone", 8.0, 2400)[:len(drn.x)] * 0.6
    # gelo: estalos grandes nas deixas dos LOGs + creque-creque espalhado
    ice = Bus(55.0, 79.0)
    ice.add(ice_hit("LedasLuzta5", -5, 4500), 55.0, 0.9, pan=-0.1)
    ice.add(boom(R("drop55"), 3.0, 1.1, 110), 55.0, 0.5)
    for i, (tt, name, semis, pan) in enumerate(((59.0, "LedasLuzta4", -4, 0.35),
                                                (65.0, "LedasLuzta33", -5, -0.4),
                                                (71.0, "LedasLuzta2", -6, 0.2))):
        ice.add(ice_hit(name, semis, 4800), tt, 0.55, pan=pan)
        events.append({"t": tt, "kind": "hit", "label": f"estalo de gelo · deixa do LOG {i + 1}"})
    srcs = [rec(ICE / f"{nm}.ogg") for nm in ("LedasLuzta", "LedasLuzta2", "LedasLuzta4")]
    times = np.sort(rng.uniform(56.0, 73.5, 22))
    for k, tt in enumerate(times):
        g = ba.grain(rng, srcs[k % 3], (0.04, 0.14))
        g = filt(repitch(g / (np.max(np.abs(g)) + 1e-12), float(rng.uniform(-8, -2))), 80, 5000, 2)
        ice.add(g, float(tt), float(rng.uniform(0.08, 0.22)), pan=float(rng.uniform(-0.8, 0.8)))
    # gemido do gelo (banda larga ~0,6 oitava descendo devagar, sem Q alto)
    for tt, d in ((61.5, 4.0), (67.5, 4.5)):
        n = ns(d)
        fc = 210 * 2 ** (-0.8 * tvec(n) / d)
        y = tv_filter(noise(rng, n), lambda tc, f, fc=fc: band_gain(f, fc[min(n - 1, max(0, int(tc * SR)))], 0.6))
        ice.add(norm_rms(y) * bump(n, 0.4), tt, 0.10, pan=float(rng.uniform(-0.5, 0.5)))
    ice.x += st_reverb(ice.x, "cold-ice", 3.5, 4000, 0.03)[:len(ice.x)] * 0.7
    b.x += drn.x * 0.42
    b.add(ice.x, 55.0, 0.75)
    b.x *= pts([(55, 1), (74.0, 1), (75.5, 0.25), (77, 0)], t)[:, None]
    events.append({"t": 55.0, "kind": "hit", "label": "a queda (corte pro frio)"})
    return b


def heartbeat(rng, gain_dub: float = 0.6) -> np.ndarray:
    """Um batimento ('tum-tum') de ruído grave filtrado. Sem seno, sem pitch."""
    def beat(r, decay):
        n = ns(0.5)
        low = norm_rms(filt(noise(r, n), 22, 95, 4)) * perc(n, 0.006, decay)
        mid = norm_rms(filt(noise(r, n), 90, 260, 2)) * perc(n, 0.003, decay * 0.5) * 0.3
        return low + mid
    x = np.zeros(ns(1.0))
    a = beat(rng, 0.085)
    d = beat(rng, 0.07) * gain_dub
    x[:len(a)] += a
    x[ns(0.29):ns(0.29) + len(d)] += d[:len(x) - ns(0.29)]
    return x


def sec_giant(events: list) -> Bus:
    """75-85 s · o gelo gigante: quase silêncio, batimento lento, respiração. Termina na sugada."""
    rng = R("giant")
    b = Bus(74.5, 85.0)
    t = b.time()
    # batimentos, de ~1,30 s para ~1,12 s (acelera um pouco)
    beats = []
    tt = 75.7
    while tt < 83.6:
        beats.append(tt)
        tt += float(np.interp(tt, [75.7, 83.6], [1.30, 1.12]))
    hb = Bus(74.5, 85.0)
    for i, tt in enumerate(beats):
        hb.add(heartbeat(R(f"hb{i}")), tt, 0.8 + 0.2 * i / len(beats))
    hb.x += st_reverb(hb.x, "hb", 2.5, 1200)[:len(hb.x)] * 0.35
    # respiração: ar entrando/saindo, banda larga, bem baixa (2 ciclos de ~4 s)
    n = len(b.x)
    br = np.zeros(n)
    for c0, ln in ((76.0, 3.6), (80.0, 3.8)):
        i = ns(c0 - 74.5)
        m = ns(ln)
        e = bump(m, 0.45) ** 1.5
        y = tv_filter(noise(rng, m), lambda tc, f, e=e, m=m: bw_mag(f, 250, 700 + 900 * e[min(m - 1, max(0, int(tc * SR)))], 2))
        br[i:i + m] += norm_rms(y) * e
    # resto do drone: Lá1 quase sumindo + um Mi6 de vidro bem longe
    rest = Bus(74.5, 85.0)
    rest.add(voice(midi(33), 10.5, rng, (1.0, 0.3), det=2) * ar(ns(10.5), 1.0, 1.5)[:, None], 74.5, 0.25)
    rest.add(voice(midi(88), 8.0, rng, (1.0,), det=6) * ar(ns(8.0), 3.0, 2.5)[:, None], 76.0, 0.012)
    rest.x = filt2(rest.x, None, 6000, 1)
    b.x += hb.x * 0.22 + st(br) * 0.012 + rest.x * 0.6
    # sugada pro corte: 84,0 -> 84,85, depois 150 ms de silêncio
    b.add(reverse_swell(R("rev85"), 0.85, "rev85"), 84.0, 0.2)
    b.x[t >= 84.85] = 0
    fo = (t >= 84.83) & (t < 84.85)
    b.x[fo] *= np.linspace(1, 0, int(fo.sum()))[:, None]
    for i, tt in enumerate(beats):
        events.append({"t": round(tt, 3), "kind": "beat", "label": f"batimento {i + 1}"})
    events.append({"t": 84.0, "kind": "cue", "label": "sugada (reverso) começa"})
    events.append({"t": 84.85, "kind": "cue", "label": "silêncio total"})
    return b


def logo_hit(rng) -> np.ndarray:
    """Impacto do logo: baque de ruído grave + gelo partindo + Lá aberto florescendo no reverb."""
    b = Bus(0.0, 9.0)
    b.add(boom(rng, 4.0, 1.0, 120), 0.0, 0.75)
    b.add(ice_hit("LedasLuzta5", -6, 4000), 0.0, 0.45, pan=0.1)
    bloom = chord((33, 40, 45, 52, 59, 64), 6.0, rng, 0.015, 3.5, "sine", harm=(1.0, 0.3, 0.12, 0.05), low_gain=1.0)
    bloom *= np.exp(-tvec(len(bloom)) / 2.2)[:, None]
    b.add(bloom, 0.0, 0.5)
    gl = voice(midi(81), 4.0, rng, (1.0, 0.1), det=7) * perc(ns(4.0), 0.01, 1.2)[:, None]
    b.add(gl, 0.05, 0.05)
    b.x += st_reverb(b.x, "logo", 5.5, 4500, 0.025)[:len(b.x)] * 0.7
    return b.x


def sec_logo(events: list) -> Bus:
    b = Bus(85.0, 90.0)
    b.add(logo_hit(R("logo")), 85.0, 0.5)
    t = b.time()
    b.x *= pts([(85, 1), (88.2, 1), (90.0, 0.0)], t)[:, None] ** 1.5
    events.append({"t": 85.0, "kind": "hit", "label": "corte seco + logo HESPER"})
    return b


# ---------------------------------------------------------------------------
# master, medição e checagens
# ---------------------------------------------------------------------------

def limiter(x: np.ndarray, ceil: float, look: float = 0.004, rel: float = 0.12) -> tuple[np.ndarray, float]:
    """Limitador com lookahead: ganho = mínimo numa janela (±look), média móvel (curva suave
    que nunca passa do necessário) e soltura exponencial. Devolve o sinal e a maior redução (dB)."""
    a = np.max(np.abs(x), axis=1)
    g = np.minimum(1.0, ceil / np.maximum(a, 1e-12))
    w = ns(look)
    pad = np.concatenate([np.ones(w), g, np.ones(w)])
    from numpy.lib.stride_tricks import sliding_window_view
    gmin = sliding_window_view(pad, 2 * w + 1).min(axis=1)
    k = np.ones(w) / w
    gs = np.convolve(np.concatenate([np.ones(w // 2), gmin, np.ones(w)]), k, "valid")[:len(g)]
    gs = np.minimum(gs, gmin)
    # soltura: só sobe devagar (só onde há redução, pra não varrer 4 M amostras à toa)
    coef = np.exp(-1 / (rel * SR))
    out = gs.copy()
    idx = np.nonzero(gs < 0.9999)[0]
    if len(idx):
        lo = max(0, idx[0] - 1)
        for i in range(lo + 1, len(out)):
            prev = out[i - 1]
            if gs[i] < prev:
                out[i] = gs[i]
            else:
                v = coef * prev + (1 - coef) * gs[i]
                out[i] = v
                if v > 0.99995 and i > idx[-1]:
                    out[i:] = gs[i:]
                    break
    return x * out[:, None], float(20 * np.log10(out.min()))


def ebur128(path: Path) -> dict:
    r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind("Summary:"):]
    get = lambda key: float(re.search(rf"{key}:\s+(-?[\d.]+|-inf)", s).group(1))
    return {"I": get("I"), "LRA": get("LRA"), "TP": get("Peak")}


def write_st(path: Path, x: np.ndarray, dither_seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(dither_seed)
    tp = (rng.uniform(-0.5, 0.5, x.shape) + rng.uniform(-0.5, 0.5, x.shape)) / 32768  # TPDF
    silent = np.max(np.abs(x), axis=1) < 1e-7
    tp[silent] = 0
    xi = np.round(np.clip(x + tp, -1, 32767 / 32768) * 32768).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(xi.tobytes())
    return xi


def kw_db(x: np.ndarray) -> float:
    m = x.mean(axis=1) if x.ndim == 2 else x
    return 10 * np.log10(np.mean(ba.weighting(m, False) ** 2) + 1e-20)


def master(x: np.ndarray, target: float = -14.0, tp_max: float = -1.0) -> tuple[np.ndarray, dict]:
    x = filt2(x, 28, 17000, 2)
    x -= x.mean(axis=0)
    # o filtro de fase zero "vaza" pra trás nos respiros: zera de novo os dois silêncios
    t = tvec(len(x))
    for a, z in ((39.92, 40.0), (84.85, 85.0)):
        x[(t >= a) & (t < z)] = 0
    ceil_db = -1.6
    gain_db = 0.0
    tmp = Path(tempfile.mkdtemp()) / "m.wav"
    for it in range(6):
        y, gr = limiter(x * 10 ** (gain_db / 20), 10 ** (ceil_db / 20))
        write_st(tmp, y)
        m = ebur128(tmp)
        print(f"  master it{it}: ganho {gain_db:+.2f} dB, teto {ceil_db:.2f}, I {m['I']:.2f} LUFS, "
              f"TP {m['TP']:.2f} dBTP, redução máx {gr:.1f} dB")
        ok_i = abs(m["I"] - target) <= 0.25
        ok_tp = m["TP"] <= tp_max - 0.05
        if ok_i and ok_tp:
            break
        gain_db += target - m["I"]
        if not ok_tp:
            ceil_db -= (m["TP"] - tp_max) + 0.1
    m["gr_max_db"] = round(gr, 2)
    m["gain_db"] = round(gain_db, 2)
    return y, m


def to_stereo_sfx(x: np.ndarray, peak_db: float) -> np.ndarray:
    x = st(x)
    x = filt2(x, 25, None, 2)
    return x * (10 ** (peak_db / 20) / np.max(np.abs(x)))


def wav_info(path: Path) -> dict:
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, nf = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        d = np.frombuffer(w.readframes(nf), "<i2").astype(float).reshape(-1, ch) / 32768
    pk = float(np.max(np.abs(d)))
    clip = int(np.sum(np.abs(d) >= 32767 / 32768))
    return {"channels": ch, "bits": sw * 8, "sr": sr, "duration": round(nf / sr, 3),
            "peak_db": round(20 * np.log10(pk + 1e-12), 2), "clipped": clip,
            "loud_db": round(kw_db(d), 1), "data": d}


def write_png(path: Path, rgb: np.ndarray) -> None:
    """PNG RGB 8-bit só com zlib (sem matplotlib)."""
    import struct
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].astype(np.uint8).tobytes() for y in range(h))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def spectrogram_png(path: Path, d: np.ndarray, width: int = 1800, height: int = 300) -> None:
    """Espectrograma (eixo de frequência em log, 30 Hz-16 kHz), cores frias->quentes."""
    m = d.mean(axis=1)
    W = 4096
    hops = np.linspace(0, len(m) - W, width).astype(int)
    win = np.hanning(W)
    f = np.fft.rfftfreq(W, 1 / SR)
    edges = np.geomspace(30, 16000, height + 1)
    idx = np.clip(np.searchsorted(f, edges), 1, len(f) - 1)
    img = np.zeros((height, width))
    for x, h in enumerate(hops):
        S = np.abs(np.fft.rfft(m[h:h + W] * win)) ** 2
        c = np.concatenate([[0], np.cumsum(S)])
        cnt = idx[1:] - idx[:-1]
        mid = np.sqrt(edges[1:] * edges[:-1])
        band = np.where(cnt > 0, (c[idx[1:]] - c[idx[:-1]]) / np.maximum(cnt, 1), np.interp(mid, f, S))
        img[:, x] = 10 * np.log10(band + 1e-14)
    img = np.clip((img - (img.max() - 90)) / 90, 0, 1)[::-1]
    stops = np.array([[8, 10, 20], [30, 40, 90], [40, 120, 160], [200, 210, 140], [255, 245, 220]], float)
    pos = np.linspace(0, 1, len(stops))
    rgb = np.stack([np.interp(img, pos, stops[:, k]) for k in range(3)], axis=-1)
    write_png(path, rgb)


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def env_svg(d: np.ndarray, bins: int = 900) -> list[float]:
    m = np.max(np.abs(d), axis=1)
    edges = np.linspace(0, len(m), bins + 1).astype(int)
    return [round(float(m[a:b].max()), 4) for a, b in zip(edges[:-1], edges[1:])]


COPIES = [
    # (arquivo do jogo, sugestão de uso no trailer)
    ("amb_storm", "0-12 s: cama de tempestade (loop 34 s)"),
    ("gust", "0-12 s: rajada forte num corte (uivo grave)"),
    ("gust_2", "0-12 s: rajada 'cinema' (duas vozes de uivo)"),
    ("mine_hit", "12-40 s: picaretada (0,06 s, repita no ritmo ~4/s)"),
    ("mine_break", "12-40 s: bloco quebrando"),
    ("place", "12-40 s: máquina colocada"),
    ("craft", "12-40 s: fabricou"),
    ("machine_hum", "12-40 s: máquinas trabalhando (loop 4 s)"),
    ("drill_loop", "12-40 s: broca automática (loop 3,2 s)"),
    ("stage_up", "40 s: o planeta sobe de estágio"),
    ("sky_clear", "40 s: o céu limpando"),
    ("ice_crack", "40-55 s e 55-75 s: gelo rachando"),
    ("ice_crack_1", "idem, a outra variação"),
    ("ice_collapse", "40 s / 55 s: gelo desabando (a cratera abre)"),
    ("vent_hiss", "40-55 s: chiado da fumarola (loop 20 s)"),
    ("amb_rain", "40-55 s: chuva média (loop 24 s)"),
    ("amb_rain_light", "40-55 s: chuva fraca (loop 24 s)"),
    ("terminal_open", "55-75 s: abriu o terminal do LOG"),
]


def build_sfx() -> list[dict]:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for name, use in COPIES:
        src = ASSETS / f"{name}.wav"
        dst = SFX_DIR / f"{name}.wav"
        shutil.copyfile(src, dst)
        assert md5(src) == md5(dst)
        inf = wav_info(dst)
        inf.pop("data")
        lic = "CC BY 4.0 (reverb) + CC0" if name.startswith("ice_") else (
            "CC0" if name.startswith("amb_rain") else ("domínio público (NPS)" if name == "vent_hiss" else "própria"))
        out.append({"file": f"sfx/{name}.wav", "name": name, "use": use, "copy": True, "license": lic,
                    "md5": md5(dst), **inf})
    new = {
        "trailer_whoosh": (lambda: whoosh(R("sfx-whoosh"), 1.3) * 0.9, -3.0,
                           "Whoosh de corte (1,3 s, passa da esquerda pra direita). Alinhe o pico (~0,8 s) no corte."),
        "trailer_reverse_ice": (lambda: reverse_swell(R("sfx-rev"), 1.6, "sfx-rev"), -3.0,
                                "Sugada de gelo ao contrário (1,6 s). Termina no pico: o fim do arquivo = o corte."),
        "trailer_heartbeat": (lambda: with_reverb(heartbeat(R("sfx-hb")), "sfx-hb", 2.0, 0.3, 1200)[:ns(1.25)], -4.0,
                              "Um batimento 'tum-tum' do gelo (1,25 s). Em sequência dá 48 BPM."),
        "trailer_logo_hit": (lambda: logo_hit(R("logo")), -1.5,
                             "Impacto do logo (9 s com a cauda): baque grave, gelo partindo, Lá aberto no reverb."),
    }
    for name, (fn, pk, use) in new.items():
        x = to_stereo_sfx(fn(), pk)
        x[:ns(0.002)] *= np.linspace(0, 1, ns(0.002))[:, None]   # começa do zero (o passa-alta vaza pra trás)
        x[-ns(0.02):] *= np.linspace(1, 0, ns(0.02))[:, None] if name != "trailer_reverse_ice" else 1
        if name == "trailer_heartbeat":
            x[-ns(0.05):] *= np.linspace(1, 0, ns(0.05))[:, None]
        dst = SFX_DIR / f"{name}.wav"
        write_st(dst, x, dither_seed=zlib.crc32(name.encode()))
        inf = wav_info(dst)
        inf.pop("data")
        out.append({"file": f"sfx/{name}.wav", "name": name, "use": use, "copy": False, "license": "própria (+ gelo CC0)" if "ice" in name or "logo" in name else "própria", "md5": md5(dst), **inf})
    return out


SECTIONS = [
    ("storm", 0.0, 12.0, "Pouso na tempestade",
     "Vento de banda larga respirando, uivo distante, poeira no fundo, drone em Lá (quinta vazia) subindo "
     "devagar e um Sib roçando no fim (tensão contida). Baque do pouso em 9,6 s."),
    ("build", 12.0, 40.0, "Construir e explorar",
     "120 BPM. Baixo em colcheias com o filtro abrindo; a cada 8 s entra uma camada: 20 s pulso grave e "
     "arpejo, 24 s chimbal, 28 s palma e picaretadas do jogo como percussão, 36 s subida e rufar. "
     "Acordes A add9, F maj7(#11), D add9, E sus4: otimista, com o Si natural sobre o Fá dando a estranheza."),
    ("open", 40.0, 55.0, "O planeta muda",
     "Sem bateria. Pads largos em Lá maior (como o amb_green), melodia lenta, brilhos com reverb longo e chuva "
     "de verdade bem baixa. Em 53 s volta o F maj7(#11) e o filtro fecha."),
    ("cold", 55.0, 75.0, "A virada (Dra. Ilves)",
     "Tudo cai. Drone Lá1 + Sib1 (batimento lento), trítono, um agudo que escorrega meio-tom, gelo estalando "
     "(estalos grandes em 59, 65 e 71 s pras falas dos LOGs) e gemidos de gelo."),
    ("giant", 75.0, 85.0, "O gelo gigante",
     "Quase silêncio. Batimento grave lento (1,30 s acelerando pra 1,12 s), respiração de ar bem baixa, "
     "um resto de Lá. Sugada reversa 84,0-84,85 e 150 ms de silêncio absoluto."),
    ("logo", 85.0, 90.0, "Corte seco + logo HESPER",
     "Baque grave de ruído, gelo partindo, Lá aberto florescendo no reverb e cauda até 90 s."),
]


def render_mix(events: list) -> np.ndarray:
    mix = np.zeros((N, 2))
    for name, fn in (("storm", sec_storm), ("build", sec_build), ("open", sec_open), ("cold", sec_cold),
                     ("giant", sec_giant), ("logo", sec_logo)):
        print(f"seção {name}...")
        bus = fn() if name == "storm" else fn(events)
        i = ns(bus.t0)
        m = min(len(bus.x), N - i)
        mix[i:i + m] += bus.x[:m]
    return mix


def main() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    before = {p.name: md5(p) for p in sorted(ASSETS.glob("*.wav"))}
    events: list = []
    mix = render_mix(events)
    events.append({"t": 9.6, "kind": "hit", "label": "pouso (baque)"})
    events.append({"t": 12.0, "kind": "hit", "label": "o pulso começa (1ª nota do baixo)"})
    for tt, lab in ((20.0, "entra o pulso grave e o arpejo"), (24.0, "entra o chimbal"),
                    (28.0, "entra a palma e a picareta"), (36.0, "começa a subida")):
        events.append({"t": tt, "kind": "cue", "label": lab})
    print("master...")
    y, m = master(mix)
    out = HERE / "trailer_music.wav"
    write_st(out, y)
    info = wav_info(out)
    d = info.pop("data")
    m_final = ebur128(out)
    # loudness aproximado por seção (K-weighting aproximado, média, não é LUFS certificado)
    sec_loud = {}
    for key, a, z, *_ in SECTIONS:
        sec_loud[key] = round(kw_db(d[ns(a):ns(z)]), 1)
    gap = d[ns(84.86):ns(84.99)]
    checks = {
        "duration_ok": bool(info["duration"] == 90.0),
        "format_ok": bool(info["channels"] == 2 and info["bits"] == 16 and info["sr"] == SR),
        "true_peak_ok": bool(m_final["TP"] <= -1.0),
        "sample_peak_ok": bool(info["peak_db"] <= -1.0),
        "lufs_ok": bool(abs(m_final["I"] + 14) <= 0.3),
        "no_clipping": bool(info["clipped"] == 0),
        "silence_before_logo_db": round(20 * np.log10(np.max(np.abs(gap)) + 1e-12), 1),
        "last_sample": int(round(float(np.max(np.abs(d[-1])) * 32768))),
        "dc_offset": [round(float(v), 6) for v in d.mean(axis=0)],
        "lr_correlation": round(float(np.corrcoef(d[:, 0], d[:, 1])[0, 1]), 3),
    }
    events.append({"t": 39.92, "kind": "cue", "label": "respiro de 80 ms antes do hit de 40 s (silêncio)"})
    events.sort(key=lambda e: e["t"])
    for e in events:
        e["frame30"] = int(round(e["t"] * 30))
        e["frame60"] = int(round(e["t"] * 60))
    marker = {
        "file": "trailer_music.wav", "duration": DUR, "sample_rate": SR, "channels": 2,
        "bpm": BPM, "beat_grid": {"start": 12.0, "end": 40.0, "beat": BEAT, "bar": BAR,
                                  "note": "grade de 120 BPM só vale de 12 a 40 s; cortes em múltiplos de 2 s caem no compasso"},
        "sections": [{"id": k, "start": a, "end": z, "title": ttl, "description": desc}
                     for k, a, z, ttl, desc in SECTIONS],
        "hits": [e for e in events if e["kind"] == "hit"],
        "cues": [e for e in events if e["kind"] == "cue"],
        "beats_heart": [e["t"] for e in events if e["kind"] == "beat"],
        "bars": [e["t"] for e in events if e["kind"] == "bar"],
        "loudness": {"integrated_lufs": m_final["I"], "true_peak_dbtp": m_final["TP"], "lra_lu": m_final["LRA"]},
    }
    (HERE / "trailer_music.json").write_text(json.dumps(marker, ensure_ascii=False, indent=2))
    print("sfx...")
    sfx = build_sfx()
    after = {p.name: md5(p) for p in sorted(ASSETS.glob("*.wav"))}
    meta = {
        "music": {**info, **{"lufs": m_final["I"], "tp": m_final["TP"], "lra": m_final["LRA"],
                             "gr_max_db": m["gr_max_db"]}, "sections_db": sec_loud,
                  "checks": checks, "md5": md5(out), "env": env_svg(d)},
        "sfx": sfx,
        "assets_untouched": bool(before == after),
    }
    spectrogram_png(HERE / "trailer_music_spectrogram.png", d)
    (HERE / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in meta["music"].items() if k != "env"}, ensure_ascii=False, indent=1))
    write_index(meta, marker)
    for s in sfx:
        print(f"  {s['file']:<34}{s['duration']:>7.2f}s {s['channels']}ch pico {s['peak_db']:>6.2f} dBFS")
    print("assets/audio intacto:", meta["assets_untouched"])


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

SFX_GROUPS = [
    ("Tempestade (0-12 s)", ["amb_storm", "gust", "gust_2"]),
    ("Construir e explorar (12-40 s)", ["mine_hit", "mine_break", "place", "craft", "machine_hum", "drill_loop"]),
    ("O planeta muda (40-55 s)", ["stage_up", "sky_clear", "ice_collapse", "ice_crack", "ice_crack_1",
                                 "vent_hiss", "amb_rain", "amb_rain_light"]),
    ("A virada (55-75 s)", ["terminal_open"]),
    ("Novos, de trailer", ["trailer_whoosh", "trailer_reverse_ice", "trailer_heartbeat", "trailer_logo_hit"]),
]
LOOPS = {"amb_storm", "machine_hum", "drill_loop", "vent_hiss", "amb_rain", "amb_rain_light", "trailer_heartbeat"}
SFX_VOL = {
    "amb_storm": "1.0 (o arquivo já é baixo, ~-13 dBFS de pico)", "gust": "0.8", "gust_2": "0.7",
    "mine_hit": "0.5, até 4 golpes por segundo", "mine_break": "0.5", "place": "0.45", "craft": "0.5",
    "machine_hum": "1.0 (bem baixo)", "drill_loop": "1.0 (bem baixo)", "stage_up": "0.5",
    "sky_clear": "0.8", "ice_collapse": "0.9", "ice_crack": "0.8", "ice_crack_1": "0.9",
    "vent_hiss": "1.0", "amb_rain": "1.0", "amb_rain_light": "1.0", "terminal_open": "0.5",
    "trailer_whoosh": "0.4", "trailer_reverse_ice": "0.5", "trailer_heartbeat": "0.6",
    "trailer_logo_hit": "0.8 (só se o vídeo NÃO usar o 85 s da trilha)",
}


def write_index(meta: dict, marker: dict) -> None:
    import html
    mu = meta["music"]
    ck = mu["checks"]
    env = mu["env"]
    # forma de onda em SVG (envelope de pico)
    w, h = 900, 80
    path = "M0," + str(h / 2) + " " + " ".join(
        f"L{i},{h / 2 - v * h / 2:.1f}" for i, v in enumerate(env)) + " " + " ".join(
        f"L{i},{h / 2 + v * h / 2:.1f}" for i, v in reversed(list(enumerate(env)))) + " Z"
    colors = {"storm": "#7a6a55", "build": "#3e7cb1", "open": "#4fa37a", "cold": "#5b6f9a", "giant": "#3a3f5c",
              "logo": "#c9a227"}
    bands = "".join(
        f'<div class="band" style="left:{s["start"] / DUR * 100:.3f}%;width:{(s["end"] - s["start"]) / DUR * 100:.3f}%;'
        f'background:{colors[s["id"]]}33;border-left:2px solid {colors[s["id"]]}"><span>{html.escape(s["title"])}</span></div>'
        for s in marker["sections"])
    hitlines = "".join(f'<div class="hitline" title="{e["t"]} s · {html.escape(e["label"])}" '
                       f'style="left:{e["t"] / DUR * 100:.3f}%"></div>' for e in marker["hits"])
    sec_rows = "".join(
        f'<tr><td><button onclick="seek({s["start"]})">&#9654; {s["start"]:.0f}-{s["end"]:.0f} s</button></td>'
        f'<td><b style="color:{colors[s["id"]]}">{html.escape(s["title"])}</b><br>{html.escape(s["description"])}</td>'
        f'<td class="num">{mu["sections_db"][s["id"]]:.1f} dB</td></tr>' for s in marker["sections"])
    ev = sorted(marker["hits"] + marker["cues"], key=lambda e: e["t"])
    ev_rows = "".join(
        f'<tr class="{e["kind"]}"><td><button onclick="seek({max(0, e["t"] - 1.5):.2f})">{e["t"]:.2f} s</button></td>'
        f'<td>{e["kind"]}</td><td>{html.escape(e["label"])}</td><td class="num">{e["frame30"]}</td>'
        f'<td class="num">{e["frame60"]}</td></tr>' for e in ev)
    by_name = {s["name"]: s for s in meta["sfx"]}
    sfx_html = ""
    for title, names in SFX_GROUPS:
        cards = ""
        for nm in names:
            s = by_name[nm]
            loop = " loop" if nm in LOOPS else ""
            extra = ""
            if nm == "mine_hit":
                extra = (f'<button onclick="burst(\'{s["file"]}\', 4, 250)">picareta 4&times;</button> '
                         f'<button onclick="burst(\'{s["file"]}\', 12, 250)">12&times;</button>')
            if nm == "trailer_heartbeat":
                extra = f'<button onclick="burst(\'{s["file"]}\', 6, 1250)">6 batidas</button>'
            origin = "cópia do jogo (md5 igual ao de assets/audio)" if s["copy"] else "novo, feito pro trailer"
            cards += (f'<div class="card"><div class="t"><b>{nm}</b> <span class="dim">{s["duration"]:.2f} s · '
                      f'{s["channels"]} canal(is) · pico {s["peak_db"]:.1f} dBFS · {html.escape(s["license"])}</span></div>'
                      f'<audio controls preload="none"{loop} src="{s["file"]}"></audio> {extra}'
                      f'<div class="dim">{html.escape(s["use"])}<br>volume sugerido: {html.escape(SFX_VOL.get(nm, "-"))}'
                      f' · {origin}</div></div>')
        sfx_html += f"<h3>{html.escape(title)}</h3><div class='grid'>{cards}</div>"
    ok = lambda b: '<span class="ok">ok</span>' if b else '<span class="bad">FALHOU</span>'
    doc = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Hesper · áudio do trailer</title>
<style>
body{{background:#0d1017;color:#d8dde6;font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px}}
h1{{margin:0 0 4px}} h2{{margin-top:36px;border-bottom:1px solid #2a3040;padding-bottom:4px}} h3{{margin:22px 0 8px;color:#9fb3c8}}
.note{{background:#1a2230;border-left:4px solid #c9a227;padding:10px 14px;margin:14px 0}}
.dim{{color:#8892a6;font-size:13px}} .num{{text-align:right;white-space:nowrap}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #222a38;padding:6px 8px;vertical-align:top}}
tr.cue td{{color:#9aa4b8}} tr.hit td{{color:#f0d68a}}
button{{background:#253047;color:#d8dde6;border:1px solid #3a4866;border-radius:4px;padding:3px 8px;cursor:pointer;white-space:nowrap}}
button:hover{{background:#31405f}}
#main{{width:100%}}
.viz{{position:relative;width:100%;margin-top:10px;cursor:pointer;user-select:none}}
.viz img{{width:100%;display:block;height:150px;object-fit:fill;border-radius:4px}}
.viz svg{{width:100%;height:60px;display:block;background:#101521}}
.band{{position:absolute;top:0;bottom:0;pointer-events:none}}
.band span{{position:absolute;top:2px;left:4px;font-size:11px;color:#fff;text-shadow:0 0 3px #000}}
.hitline{{position:absolute;top:0;bottom:0;width:1px;background:#f0d68a;opacity:.8}}
#head{{position:absolute;top:0;bottom:0;width:2px;background:#ff5a5a;left:0;pointer-events:none}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.card{{background:#141a26;border:1px solid #232c3e;border-radius:6px;padding:8px 10px}}
.card audio{{width:100%;margin:4px 0}}
.ok{{color:#6fd08c;font-weight:600}} .bad{{color:#ff6b6b;font-weight:600}}
code{{background:#1b2232;padding:1px 4px;border-radius:3px}}
</style></head><body>
<h1>Hesper · áudio do trailer (1:30)</h1>
<div class="dim">Gerado por <code>build_trailer_audio.py</code> (nesta pasta). Seeds fixas: rodar de novo dá o mesmo arquivo.</div>

<div class="note"><b>v1 · primeira versão.</b> Trilha de 90 s em 6 seções (tempestade, construção a 120 BPM,
o planeta muda, a virada fria, o gelo gigante, corte + logo), marcadores em <code>trailer_music.json</code>
e uma pasta <code>sfx/</code> com 18 sons copiados do jogo e 4 novos de trailer. <b>Eu não consigo ouvir:</b>
tudo aqui foi validado por medição (loudness, pico, espectro, silêncios). A palavra final é do teu ouvido.</div>

<h2>Trilha · trailer_music.wav</h2>
<audio id="main" controls preload="auto" src="trailer_music.wav"></audio>
<div class="viz" id="viz" title="clique pra pular">
<img src="trailer_music_spectrogram.png" alt="espectrograma">
<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none"><path d="{path}" fill="#6f8fb8"/></svg>
{bands}{hitlines}<div id="head"></div></div>
<div class="dim">Em cima: espectrograma (30 Hz embaixo, 16 kHz em cima). Embaixo: forma de onda. Linhas amarelas = hits.</div>
<p>{mu["duration"]:.3f} s · 44,1 kHz · 16-bit · estéreo · <b>{mu["lufs"]:.1f} LUFS</b> integrado ·
true peak <b>{mu["tp"]:.1f} dBTP</b> · pico de amostra {mu["peak_db"]:.1f} dBFS · LRA {mu["lra"]:.1f} LU ·
limitador no máximo {mu["gr_max_db"]:.1f} dB (só nos picos do rufar de 39 s e dos hits)</p>

<h2>Seções</h2>
<table><tr><th></th><th>o que tenta passar</th><th class="num">nível*</th></tr>{sec_rows}</table>
<div class="dim">* energia média com ponderação tipo K aproximada (não é LUFS certificado). Serve pra comparar seções:
a construção e a abertura são o "alto", a virada cai ~5 dB e o gelo gigante ~13 dB.</div>

<h2>Hits e deixas pro corte (trailer_music.json)</h2>
<div class="dim">O botão toca a partir de 1,5 s antes do hit. Frames contados a partir do 0 da trilha.
De 12 a 40 s a grade é de 120 BPM: compasso = 2 s, tempo = 0,5 s (cortes em múltiplos de 2 s caem na cabeça do compasso).</div>
<table><tr><th>tempo</th><th>tipo</th><th>o quê</th><th class="num">frame @30</th><th class="num">frame @60</th></tr>{ev_rows}</table>

<h2>Efeitos · sfx/</h2>
<div class="dim">As cópias são idênticas byte a byte aos arquivos do jogo (mono, no volume do jogo: vários são baixos de
propósito). Os 4 novos são estéreo.</div>
{sfx_html}

<h2>Dicas de integração (Remotion)</h2>
<ul>
<li>Copie <code>trailer_music.wav</code> e os sfx que usar pra <code>public/audio/</code> e toque com
<code>&lt;Audio src={{staticFile("audio/trailer_music.wav")}} /&gt;</code> no frame 0. A trilha já está masterizada
(-14 LUFS, -1 dBTP): <b>volume 1.0</b>, sem normalizar de novo.</li>
<li>Os tempos do <code>trailer_music.json</code> são em segundos: frame = <code>Math.round(t * fps)</code>. Os campos
<code>frame30</code>/<code>frame60</code> já vêm prontos.</li>
<li>Sfx por cima da trilha: deixa em <code>&lt;Sequence from={{frame}}&gt;&lt;Audio .../&gt;&lt;/Sequence&gt;</code>.
Nos momentos de sfx forte (pouso, gelo desabando), abaixe a trilha uns 3-4 dB (volume ~0.65) por ~1 s com
<code>volume={{f =&gt; interpolate(...)}}</code>.</li>
<li><b>Não dobre o que já está na trilha:</b> a música já tem o baque do pouso (9,6 s), o hit de 40 s, a queda
com gelo (55 s), estalos de gelo em 59/65/71 s, batimentos (75,7-83,1 s) e o impacto do logo (85 s). Os sfx
<code>trailer_logo_hit</code> e <code>trailer_heartbeat</code> são pra caso o vídeo mude de tempo e precise do
som solto, não pra somar.</li>
<li>Gelo do jogo (<code>ice_collapse</code>, <code>ice_crack*</code>) cai melhor na parte de 40-55 s (a cratera derretendo),
onde a trilha não tem gelo.</li>
<li>Loops (<code>amb_storm</code>, <code>amb_rain*</code>, <code>vent_hiss</code>, <code>machine_hum</code>, <code>drill_loop</code>)
emendam sem estalo: pode usar <code>loop</code> no <code>&lt;Audio&gt;</code> ou repetir em Sequence. Entre num corte com
fade de 0,3-0,5 s.</li>
<li><code>mine_hit</code> tem 0,06 s: pra parecer mineração, repita a cada 0,25 s (no tempo da trilha de 12-40 s cai
certinho na semicolcheia) variando o volume entre 0,4 e 0,55.</li>
<li>O silêncio de 84,85-85,0 s é absoluto (zero digital). Corte a imagem pro preto ali e entre o logo no 85,0.</li>
</ul>

<h2>Checagens</h2>
<ul>
<li>Duração 90,000 s: {ok(ck["duration_ok"])} · formato 44,1 kHz/16-bit/estéreo: {ok(ck["format_ok"])} ·
sem clipping: {ok(ck["no_clipping"])}</li>
<li>Loudness {mu["lufs"]:.1f} LUFS (alvo -14 ±0,3): {ok(ck["lufs_ok"])} · true peak {mu["tp"]:.1f} dBTP (≤ -1): {ok(ck["true_peak_ok"])}
· pico de amostra ≤ -1 dBFS: {ok(ck["sample_peak_ok"])} (medido com o filtro <code>ebur128</code> do ffmpeg)</li>
<li>Silêncio antes do logo: {ck["silence_before_logo_db"]:.0f} dBFS · última amostra: {ck["last_sample"]} · DC: {ck["dc_offset"]}
· correlação L/R: {ck["lr_correlation"]} (estéreo largo, mas mono-compatível)</li>
<li><code>assets/audio/</code> intacto (md5 de todos os wav antes e depois do build): {ok(meta["assets_untouched"])}</li>
</ul>

<h2>Créditos e licenças</h2>
<ul>
<li><b>A trilha</b> é síntese própria + gravações <b>CC0</b> (domínio público): gelo de IgnasD ("Ice breaking/shattering"),
pedrinhas do pouso de rubberduck ("75 CC0 breaking/falling/hit sfx") e a chuva de Kresiek The Furry ("AMB Rain Loop 2"),
todos no OpenGameArt. O reverb da trilha é sintético. <b>Nenhum crédito é obrigatório pra trilha.</b></li>
<li><b>Se o vídeo usar <code>sfx/ice_crack.wav</code>, <code>ice_crack_1.wav</code> ou <code>ice_collapse.wav</code></b>:
eles levam o reverb da capela de Aachen, <b>CC BY 4.0</b>. Aí a descrição do vídeo precisa do crédito
(texto pronto em <code>CREDITS.md</code> desta pasta e em <code>assets/audio/CREDITS.md</code>).</li>
<li><code>vent_hiss</code>: gravação do National Park Service (domínio público). O NPS pede "No claim to original U.S.
Government works" em uso comercial.</li>
</ul>

<script>
const a = document.getElementById('main'), viz = document.getElementById('viz'), head = document.getElementById('head');
function seek(t) {{ a.currentTime = t; a.play(); }}
viz.addEventListener('click', e => {{ const r = viz.getBoundingClientRect(); seek((e.clientX - r.left) / r.width * {DUR}); }});
a.addEventListener('timeupdate', () => {{ head.style.left = (a.currentTime / {DUR} * 100) + '%'; }});
function burst(src, n, ms) {{ for (let i = 0; i < n; i++) setTimeout(() => {{
  const x = new Audio(src); x.volume = 0.45 + 0.1 * Math.random(); x.play(); }}, i * ms); }}
</script>
</body></html>
"""
    (HERE / "index.html").write_text(doc)


if __name__ == "__main__":
    main()
