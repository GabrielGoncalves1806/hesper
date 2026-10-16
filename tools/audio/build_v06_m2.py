"""v0.6 Fundo M2 · ambiente sonoro por bioma da caverna (salar, basalto, gelo). Fora do jogo.

Uso:  python3 tools/audio/build_v06_m2.py

Saída (tudo em reports/audio/v06_fundo_m2_biomas/, NADA em assets/audio/):
  amb_cave_{salar,basalt,frost}.wav, demos de crossfade (xf_*.wav) e v06_meta.js.
O centro/planalto continua sendo assets/audio/amb_cave.wav (lido, nunca escrito).

Família do amb_cave: Lá, drone grave num passa-baixa, reverb grande, brilhos agudos raros, quase
nada de chiado, nenhum bicho. Cada loop é periódico (ciclos inteiros, ruído filtrado e reverb
circulares) e tem comprimento próprio (salar 30 s, basalto 26 s, gelo 34 s; o centro tem 28 s), então
a soma deles não repete junto. Loudness-alvo: a do amb_cave (-28 dB), pra trocar sem salto de volume.
Sem ressonância estreita: todo ruído é banda larga (Butterworth ordem 1 ou 2, razão >= 2:1).
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, add_circ, bump, cave_space, filt, finalize, glints, loudness, midi, noise_burst,  # noqa: E402
                         noise_sweep, norm_rms, ns, pad_voice, periodic_ctrl, plink, reverb, rng_for,
                         space_mix, waveform_peaks, write_wav)

REP = B.ROOT / "reports" / "audio" / "v06_fundo_m2_biomas"
TARGET = -28.0   # a mesma do amb_cave


def drone(n, L, rng, voices, detune=(-0.1, 0.0, 0.1), harm=(1.0, 0.15, 0.04), swell=(1, 3)):
    return sum(g * pad_voice(n, L, rng, midi(m), detune=detune, harm=harm, swell=swell) for m, g in voices)


def slow_noise(n, L, rng, lo, hi, order, kmin=1, kmax=4, depth=0.6):
    """Ruído de banda larga (circular) com amplitude respirando num ciclo inteiro."""
    x = norm_rms(filt(rng.standard_normal(n), lo, hi, order, circular=True))
    return x * (1 - depth + depth * periodic_ctrl(n, L, rng, kmin, kmax))


def amb_salar(rng):
    """Salar: Lá sus2 aberto e seco (Lá1, Mi2, Si2, Lá2, Mi3), pouca reverb. Infiltração úmida:
    gotas macias e mais frequentes, com eco curto de poço. Chiado seco de grão: pó de sal/areia
    escorrendo em grãos minúsculos de banda larga, em rajadinhas irregulares, quase inaudível."""
    L = 30.0
    n = ns(L)
    pad = norm_rms(filt(drone(n, L, rng, ((33, 0.35), (40, 0.6), (47, 0.4), (45, 1.0), (52, 0.5)),
                              harm=(1.0, 0.12, 0.03)), 30, 1000, 2, circular=True))
    shimmer = filt(glints(n, rng, (64, 69, 71, 76), 3, (3.5, 6.0), (0.2, 0.3)), None, 3200, 1, circular=True)
    drops = np.zeros(n)
    gaps = rng.uniform(0.5, 3.0, 18) ** 1.4
    starts = np.cumsum(gaps / gaps.sum() * L) + rng.uniform(0, 1)
    for t in starts:   # 18 gotas por volta: umidade escorrendo, mais leves e mais agudas que as do centro
        f0 = rng.uniform(1100, 2200)
        amp = rng.uniform(0.9, 2.4)
        add_circ(drops, filt(plink(rng, f0, 0.07), 400, 4000, 1) * amp, ns(t) % n)
        if rng.uniform() < 0.25:
            add_circ(drops, filt(plink(rng, f0 * rng.uniform(1.15, 1.4), 0.05), 400, 4000, 1) * amp * 0.45,
                     ns(t + rng.uniform(0.1, 0.25)) % n)
    drops = cave_space(drops, rng, circular=True, decay=2.2, mix=0.8, lp=3000)
    grains = np.zeros(n)   # grãos secos, em rajadinhas
    for _ in range(9):
        t0 = rng.uniform(0, L)
        for _ in range(int(rng.integers(10, 30))):
            t0 += rng.exponential(0.05)
            hi = rng.uniform(3000, 7000)
            add_circ(grains, noise_burst(rng, hi / 3, hi, 0.0003, rng.uniform(0.002, 0.006), 0.02, order=1),
                     ns(t0) % n, rng.uniform(0.3, 1.0))
    grains = norm_rms(grains) * 0.12 if np.any(grains) else grains
    air = slow_noise(n, L, rng, 200, 1200, 1) * 0.06
    return space_mix(rng, pad, shimmer, drops + grains + air, pad_rev=(4.5, 0.4, 2000), sh_rev=(5.0, 0.55, 4500))


def amb_basalt(rng):
    """Basalto: ar quente e abafado. Drone de Lá com mais corpo (Lá1, Mi2, Lá2 mais harmônicos, um Dó
    bem baixo de sombra), rumor grave de rocha respirando, ar morno de ruído escuro e estalos de brasa
    esparsos (grãos de banda larga, tempo irregular, sem ressonância). Sem brilho agudo."""
    L = 26.0
    n = ns(L)
    pad = norm_rms(filt(drone(n, L, rng, ((33, 0.7), (40, 0.6), (45, 1.0), (52, 0.3)), detune=(-0.15, 0.0, 0.15),
                              harm=(1.0, 0.35, 0.14), swell=(1, 3)), 28, 650, 2, circular=True))
    shade = pad_voice(n, L, rng, midi(48), harm=(1.0, 0.1), swell=(2, 4)) * 0.1
    pad = pad + norm_rms(filt(shade, 40, 500, 2, circular=True)) * 0.1
    shimmer = filt(glints(n, rng, (57, 64), 2, (5.0, 8.0), (0.1, 0.15)), None, 1200, 1, circular=True)  # quase só calor
    rumble = slow_noise(n, L, rng, 25, 150, 2, 1, 3, 0.7) * 0.10
    warm = slow_noise(n, L, rng, 120, 800, 1, 1, 4, 0.5) * 0.18      # ar abafado
    embers = np.zeros(n)
    starts = np.cumsum(rng.uniform(0.4, 3.2, 14) ** 1.3)
    starts = starts / starts[-1] * L * 0.97 + rng.uniform(0, 0.5)
    for t in starts:    # estalo de brasa: pop curto de banda larga + 0 a 3 grãozinhos depois
        hi = rng.uniform(2500, 5500)
        amp = rng.uniform(0.4, 1.0)
        add_circ(embers, noise_burst(rng, hi / 4, hi, 0.0002, rng.uniform(0.002, 0.005), 0.03, order=1), ns(t) % n, amp)
        add_circ(embers, noise_burst(rng, 150, 1200, 0.0004, 0.01, 0.06, order=1), ns(t) % n, amp * 0.5)
        tt = t
        for _ in range(int(rng.integers(0, 4))):
            tt += rng.exponential(0.04)
            add_circ(embers, noise_burst(rng, 800, 4500, 0.0002, 0.003, 0.02, order=1), ns(tt) % n, amp * rng.uniform(0.15, 0.5))
    embers = cave_space(embers, rng, circular=True, decay=2.0, mix=0.5, lp=2200) * 0.1 / 0.7
    return space_mix(rng, pad, shimmer, rumble + warm + embers, pad_rev=(5.0, 0.38, 1300), sh_rev=(6.0, 0.5, 1800))


def amb_frost(rng):
    """Gelo: quinta vazia fria (Lá1, Mi2, Lá2) bem baixa, vento fino e largo em fenda subindo e
    descendo devagar, brilho cristalino (Mi5, Lá5, Si5) mais presente que nas outras e um rangido
    de gelo raro (varredura de ruído larga e descendo + estalinhos), duas vezes por volta."""
    L = 34.0
    n = ns(L)
    pad = norm_rms(filt(drone(n, L, rng, ((33, 0.4), (40, 0.6), (45, 1.0)), detune=(-0.125, 0.0, 0.125),
                              harm=(1.0, 0.18, 0.05), swell=(1, 3)), 30, 900, 2, circular=True))
    shimmer = filt(glints(n, rng, (69, 76, 81, 83), 6, (3.0, 6.0), (0.2, 0.3)), None, 6500, 1, circular=True)
    # vento fino na fenda: banda larga (700 a 3000 Hz, ordem 1), respirando devagar
    wind = slow_noise(n, L, rng, 700, 3000, 1, 1, 3, 0.85) * 0.22
    wind2 = slow_noise(n, L, rng, 250, 1000, 1, 1, 2, 0.6) * 0.12
    ice = np.zeros(n)
    for t in (rng.uniform(4, 13), rng.uniform(21, 31)):
        dur = rng.uniform(0.9, 1.4)
        m = ns(dur)
        creak = noise_sweep(rng, dur, 2200, 450, 3.0) * bump(m, 0.25) ** 1.2
        add_circ(ice, creak, ns(t) % n, 0.35)
        tt = t
        for _ in range(int(rng.integers(3, 7))):    # estalinhos do gelo cedendo
            tt += rng.exponential(0.12)
            hi = rng.uniform(3500, 8000)
            add_circ(ice, noise_burst(rng, hi / 3, hi, 0.0002, 0.003, 0.02, order=1), ns(tt) % n, rng.uniform(0.15, 0.5))
    ice = cave_space(ice, rng, circular=True, decay=3.2, mix=0.8, lp=4500) * 0.14 / 0.6
    return space_mix(rng, pad, shimmer, wind + wind2 + ice, pad_rev=(6.5, 0.5, 1800), sh_rev=(7.0, 0.8, 6500))


LOOPS = {"amb_cave_salar": amb_salar, "amb_cave_basalt": amb_basalt, "amb_cave_frost": amb_frost}


def bands(x):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    p = np.abs(np.fft.rfft(x)) ** 2
    ed = [(20, 150), (150, 600), (600, 2500), (2500, 6000), (6000, 16000)]
    return [round(float(100 * p[(f >= a) & (f < b)].sum() / p.sum()), 1) for a, b in ed]


def tonal_peak(x):
    """Maior pico espectral acima de 1,2 kHz contra a mediana de +-200 Hz em volta (dB). Alto = apito."""
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / SR)
    sm = np.convolve(X, np.ones(7) / 7, "same")
    best = (0.0, 0.0)
    k = int(200 / (f[1]))
    for i in np.nonzero((f > 1200) & (f < 12000))[0][::7]:
        med = np.median(X[max(0, i - k):i + k])
        r = 20 * np.log10(sm[i] / (med + 1e-12))
        if r > best[0]:
            best = (float(r), float(f[i]))
    return round(best[0], 1), round(best[1])


def seam(xi):
    x = xi.astype(float)
    d = np.abs(np.diff(x))
    return round(float(abs(x[0] - x[-1])), 1), round(float(np.percentile(d, 99.9)), 1)


def read(path):
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")


def tile(x, secs):
    return np.tile(x, int(np.ceil(secs * SR / len(x))))[: ns(secs)]


def crossfade_demo(a, b, lead=6.0, tail=6.0):
    """Como o jogo faz: o que sai cai em 1,5 s, o que entra sobe em 2,5 s, 0,5 s depois (lineares)."""
    total = lead + 3.0 + tail
    out = np.zeros(ns(total))
    A, Bb = tile(a, total), tile(b, total)
    ga = np.ones(ns(total))
    t = np.arange(ns(total)) / SR
    ga = np.where(t < lead, 1.0, np.clip(1 - (t - lead) / 1.5, 0, 1))
    gb = np.clip((t - lead - 0.5) / 2.5, 0, 1)
    out = A * ga + Bb * gb
    return out


def main():
    REP.mkdir(parents=True, exist_ok=True)
    meta = {}
    ref = read(B.OUT_DIR / "amb_cave.wav")

    def info(key, file, xi, loop=True):
        xf = xi.astype(float) / 32768
        j, d = seam(xi)
        tp = tonal_peak(xf) if loop else (0, 0)
        meta[key] = {"file": file, "loop": loop, "duration": round(len(xi) / SR, 3),
                     "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
                     "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(xf ** 2)))), 1),
                     "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(xi),
                     "bands": bands(xf), "seam": j, "seam_ref": d, "tonal_db": tp[0], "tonal_hz": tp[1]}
        m = meta[key]
        print(f"{key:<18}{m['duration']:>6.1f} s  pico {m['peak_db']:>6}  rms {m['rms_db']:>6}  loud {m['loudness_db']:>6}"
              f"  emenda {j}/{d}  tonal {tp[0]} dB@{tp[1]}  bandas% {m['bands']}")

    info("amb_cave", "../../../assets/audio/amb_cave.wav", ref)
    wavs = {"amb_cave": ref}
    for name, fn in LOOPS.items():
        xi = write_wav(REP / f"{name}.wav", finalize(fn(rng_for("v06m2:" + name)), True, TARGET))
        info(name, f"{name}.wav", xi)
        wavs[name] = xi
    for name in LOOPS:
        demo = crossfade_demo(ref.astype(float), wavs[name].astype(float))
        xi = write_wav(REP / f"xf_cave_to_{name[9:]}.wav", demo / 32768 * 0.9)
        info("xf_" + name[9:], f"xf_cave_to_{name[9:]}.wav", xi, loop=False)
    # passeio: centro -> salar -> basalto -> gelo -> centro, 8 s em cada, trocando como o jogo
    seq = ["amb_cave", "amb_cave_salar", "amb_cave_basalt", "amb_cave_frost", "amb_cave"]
    total = 8.0 * 4 + 3.0
    t = np.arange(ns(total)) / SR
    out = np.zeros(ns(total))
    for i, k in enumerate(seq):
        s = tile(wavs[k].astype(float), total)
        if i == 0:
            g = np.clip(1 - (t - 8.0) / 1.5, 0, 1)
        else:
            t0 = 8.0 * i
            g = np.clip((t - t0 - 0.5) / 2.5, 0, 1)
            if i < 4:
                g = np.where(t < t0 + 8.0, g, np.clip(1 - (t - t0 - 8.0) / 1.5, 0, 1))
        out += s * g
    xi = write_wav(REP / "xf_tour.wav", out / 32768 * 0.9)
    info("xf_tour", "xf_tour.wav", xi, loop=False)
    (REP / "v06_meta.js").write_text("// gerado por tools/audio/build_v06_m2.py, não editar\nwindow.V06_META = "
                                     + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
