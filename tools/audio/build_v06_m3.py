"""v0.6 Fundo M3 · Fundição (smelter): loop de fusão + tink de lingote. Fora do jogo.

Uso:  python3 tools/audio/build_v06_m3.py

Saída (tudo em reports/audio/v06_fundo_m3_fundicao/, NADA em assets/audio/):
  smelter_loop.wav, smelter_done.wav, mix_*.wav (comparações) e v06m3_meta.js.

smelter_loop: periódico em L = 4,0 s. Ronco de máquina em Lá1 (55 Hz, o drill é Mi2, 82,5 Hz, então
não brigam) com ciclos inteiros + fogo grave (ruído de banda larga 70-700 Hz respirando) + estalos
de brasa raros e macios, banda larga, sem tom. Sem ressonância estreita, sem corpo de tambor.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, add_circ, bump, filt, finalize, loudness, noise_burst, norm_rms, ns,  # noqa: E402
                         periodic_ctrl, reverb, rng_for, tvec, waveform_peaks, write_wav, fr)

REP = B.ROOT / "reports" / "audio" / "v06_fundo_m3_fundicao"


def loop_smelter(rng):
    L = 4.0
    n = ns(L)
    t = tvec(n)
    # ronco de máquina: Lá1 e harmônicos baixos, leve pulsação de bomba a 2 Hz (8 ciclos em L)
    hum = np.zeros(n)
    for k, a in ((1, 1.0), (2, 0.55), (3, 0.18), (4, 0.08)):
        hum += a * np.sin(2 * np.pi * fr(55.0 * k, L) * t + rng.uniform(0, 2 * np.pi))
    hum *= 1 + 0.07 * np.sin(2 * np.pi * 2.0 * t + 1.0)
    hum = norm_rms(hum)
    rumble = norm_rms(filt(rng.standard_normal(n), 28, 160, 2, circular=True))
    # fogo grave: ronco largo de chama, respirando devagar
    breath = 0.55 + 0.45 * periodic_ctrl(n, L, rng, 1, 4)
    fire = norm_rms(filt(rng.standard_normal(n), 70, 700, 2, circular=True)) * breath
    # sopro fino de gás/ar, bem baixo
    air = norm_rms(filt(rng.standard_normal(n), 900, 3500, 1, circular=True)) * (0.4 + 0.6 * breath)
    # estalos de brasa: pops curtos de banda larga, irregulares
    pops = np.zeros(n)
    for _ in range(9):
        at = rng.uniform(0, L)
        hi = rng.uniform(900, 3500)
        g = noise_burst(rng, hi / 4, hi, 0.0004, rng.uniform(0.004, 0.012), 0.05, order=1)
        add_circ(pops, g, ns(at) % n, rng.uniform(0.3, 1.0))
    pops = norm_rms(pops)
    x = hum * 0.45 + rumble * 0.3 + fire * 0.6 + air * 0.05 + pops * 0.07
    return filt(x, 30, 4500, 2, circular=True)


def sfx_done(rng):
    """Lingote saindo: baque seco abafado de banda larga, um clique metálico curto (ruído, sem
    ressonância fixa) e um chiado de vapor que some em ~0,35 s."""
    tr = B.Track()
    tr.add(noise_burst(rng, 2000, 6500, 0.0002, 0.0015, 0.012, order=1), 0.0, 0.5)     # clique
    tr.add(noise_burst(rng, 120, 900, 0.001, 0.02, 0.12, order=2), 0.004, 0.6)         # baque
    tr.add(noise_burst(rng, 1800, 5500, 0.0003, 0.0015, 0.01, order=1), 0.07, 0.25)    # tink de assentar
    tr.add(noise_burst(rng, 1500, 5000, 0.02, 0.10, 0.4, order=1), 0.03, 0.35)         # chiado
    return reverb(tr.render(), rng, decay=0.25, mix=0.08, lp=5000)


def bands(x):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    p = np.abs(np.fft.rfft(x)) ** 2
    ed = [(20, 150), (150, 600), (600, 2500), (2500, 6000), (6000, 16000)]
    return [round(float(100 * p[(f >= a) & (f < b)].sum() / p.sum()), 1) for a, b in ed]


def tonal_peak(x):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / SR)
    sm = np.convolve(X, np.ones(7) / 7, "same")
    best = (0.0, 0.0)
    k = int(100 / f[1])
    for i in np.nonzero((f > 150) & (f < 12000))[0][::5]:
        r = 20 * np.log10(sm[i] / (np.median(X[max(0, i - k):i + k]) + 1e-12))
        if r > best[0]:
            best = (float(r), float(f[i]))
    return round(best[0], 1), round(best[1])


def read(p):
    with wave.open(str(p), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768


def tile(x, secs):
    return np.tile(x, int(np.ceil(secs * SR / len(x))))[: ns(secs)]


def main():
    REP.mkdir(parents=True, exist_ok=True)
    meta = {}

    def info(key, file, xi, loop):
        xf = xi.astype(float) / 32768
        m = {"file": file, "loop": loop, "duration": round(len(xi) / SR, 3),
             "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
             "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(xf ** 2)))), 1),
             "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(xi), "bands": bands(xf)}
        if loop:
            d = np.abs(np.diff(xi.astype(float)))
            m["seam"] = float(abs(int(xi[0]) - int(xi[-1])))
            m["seam_ref"] = round(float(np.percentile(d, 99.9)), 1)
            m["tonal_db"], m["tonal_hz"] = tonal_peak(xf)
        meta[key] = m
        print(key, {k: v for k, v in m.items() if k != "wave"})

    loop = write_wav(REP / "smelter_loop.wav", finalize(loop_smelter(rng_for("v06m3:smelter_loop")), True, -30.0))
    done = write_wav(REP / "smelter_done.wav", finalize(sfx_done(rng_for("v06m3:smelter_done")), False, -24.0))
    info("smelter_loop", "smelter_loop.wav", loop, True)
    info("smelter_done", "smelter_done.wav", done, False)
    # mixes com os ganhos sugeridos: AMBIENT_VOLUME 0.7, drill_loop 0.5, smelter_loop 0.45
    cave = read(B.OUT_DIR / "amb_cave.wav")
    drill = read(B.OUT_DIR / "drill_loop.wav")
    sm = loop.astype(float) / 32768
    T = 16.0
    c, d, s = tile(cave, T), tile(drill, T), tile(sm, T)
    dn = tile(done.astype(float) / 32768, T)
    done_t = np.zeros(ns(T))
    for at in (3.0, 11.0):
        a = ns(at)
        done_t[a:a + len(done)] += done.astype(float) / 32768
    mixes = {
        "mix_fundicao_cave": ("amb_cave + fundição perto", c * 0.7 + s * 0.45),
        "mix_fundicao_drill": ("drill + fundição (perto das duas)", d * 0.5 + s * 0.45),
        "mix_tudo": ("amb_cave + drill + fundição + 2 lingotes", c * 0.7 + d * 0.5 + s * 0.45 + done_t * 0.6),
    }
    for k, (_, mx) in mixes.items():
        xi = write_wav(REP / f"{k}.wav", mx * 0.95)
        info(k, f"{k}.wav", xi, False)
    (REP / "v06m3_meta.js").write_text("// gerado por tools/audio/build_v06_m3.py, não editar\nwindow.M3_META = "
                                       + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
