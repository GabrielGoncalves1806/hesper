"""v0.8 M2 · Água: loop do Coletor de água (collector_loop), 3 variantes A/B/C. Fora do jogo.

Uso:  python3 tools/audio/v08_collector.py
Saída (só reports/audio/v08_m2/, NADA em assets/audio/): collector_loop_A/B/C.wav, mix_*.wav, v08m2_meta.js.

Todos periódicos em L = 5,0 s (smelter 4,0 s, drill 3,2 s: não se repetem juntos). Gota = glissando
curto de seno agudo (900-2200 Hz, sobe rápido, some em ~60 ms) com reverb circular pequeno de
reservatório; sem grave, sem ressonância fixa (cada gota tem pitch diferente). Ventoinha = ruído largo
(250-2200 Hz) respirando + zumbido de condensador em Lá2/Lá3 (110/220 Hz, ciclos inteiros), bem baixo.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, add_circ, filt, finalize, loudness, norm_rms, ns, periodic_ctrl,  # noqa: E402
                         reverb, rng_for, tvec, waveform_peaks, write_wav, fr)

REP = B.ROOT / "reports" / "audio" / "v08_m2"
L = 5.0


def drop(rng, f0):
    n = ns(0.14)
    t = tvec(n)
    f = f0 * (1 + 0.9 * (1 - np.exp(-t / 0.012)))          # sobe rápido (bolha/gota na água)
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.minimum(1, t / 0.002) * np.exp(-t / 0.028)
    tick = filt(rng.standard_normal(n), 1500, 5000, 1) * np.exp(-t / 0.003) * 0.25
    return filt(np.sin(ph) * env + tick, 500, 5500, 1)


def build(rng, n_drops, fan_gain, hum_gain, air_gain):
    n = ns(L)
    t = tvec(n)
    # gotas: espaçamento irregular (jitter em volta de uma grade), alturas variadas
    dry = np.zeros(n)
    slots = (np.arange(n_drops) + rng.uniform(0.1, 0.9, n_drops)) / n_drops * L
    for at in slots:
        f0 = rng.choice([700, 820, 950, 1100, 1250, 1400]) * rng.uniform(0.95, 1.05)
        add_circ(dry, drop(rng, f0), ns(at) % n, rng.uniform(0.45, 1.0))
        if rng.random() < 0.35:                             # gota-eco menor logo depois
            add_circ(dry, drop(rng, f0 * 1.25), ns(at + rng.uniform(0.09, 0.2)) % n, 0.25)
    drops = norm_rms(reverb(dry, rng, decay=0.5, mix=0.55, lp=4500, circular=True)) if n_drops else np.zeros(n)
    breath = 0.6 + 0.4 * periodic_ctrl(n, L, rng, 1, 3)
    fan = norm_rms(filt(rng.standard_normal(n), 250, 2200, 2, circular=True)) * breath
    air = norm_rms(filt(rng.standard_normal(n), 2500, 7000, 1, circular=True)) * breath
    hum = np.zeros(n)
    for k, a in ((110, 1.0), (220, 0.5), (330, 0.12)):
        hum += a * np.sin(2 * np.pi * fr(k, L) * t + rng.uniform(0, 6.28))
    hum *= 1 + 0.05 * np.sin(2 * np.pi * fr(1.0, L) * t)
    hum = norm_rms(hum)
    x = drops * 1.0 + fan * fan_gain + hum * hum_gain + air * air_gain
    return filt(x, 60, 8000, 2, circular=True)


VARS = {
    "A": ("Mais gotejado", dict(n_drops=8, fan_gain=0.10, hum_gain=0.05, air_gain=0.01)),
    "B": ("Mais ventoinha", dict(n_drops=2, fan_gain=0.85, hum_gain=0.30, air_gain=0.06)),
    "C": ("Mistura (recomendada)", dict(n_drops=5, fan_gain=0.40, hum_gain=0.14, air_gain=0.03)),
}


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
            m["label"] = VARS[key[-1]][0]
        meta[key] = m
        print(key, {k: v for k, v in m.items() if k != "wave"})

    out = {}
    for k, (_, kw) in VARS.items():
        xi = write_wav(REP / f"collector_loop_{k}.wav", finalize(build(rng_for(f"v08m2:collector:{k}"), **kw), True, -31.0))
        out[k] = xi
        info(f"collector_loop_{k}", f"collector_loop_{k}.wav", xi, True)
    T = 20.0
    cave, green = tile(read(B.OUT_DIR / "amb_cave.wav"), T), tile(read(B.OUT_DIR / "amb_green.wav"), T)
    sm = tile(read(B.OUT_DIR / "smelter_loop.wav"), T)
    for k in VARS:
        c = tile(out[k].astype(float) / 32768, T)
        for name, mx in ((f"mix_base_{k}", green * 0.7 + c * 0.4 + sm * 0.45 * 0.5),
                         (f"mix_cave_{k}", cave * 0.7 + c * 0.4)):
            info(name, f"{name}.wav", write_wav(REP / f"{name}.wav", mx * 0.95), False)
    (REP / "v08m2_meta.js").write_text("// gerado por tools/audio/v08_collector.py, não editar\nwindow.M2_META = "
                                       + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
