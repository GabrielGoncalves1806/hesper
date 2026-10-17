"""v0.8 M3 · Cultivador: loop (cultivator_loop), 3 variantes A/B/C. Fora do jogo.

Uso:  python3 tools/audio/v08_cultivator.py
Saída (só reports/audio/v08_m3/, NADA em assets/audio/): cultivator_loop_A/B/C.wav, mix_*.wav, v08m3_meta.js.

Todos periódicos em L = 6,1 s (collector 5,0, smelter 4,0, drill 3,2: nenhum múltiplo do outro).
Bolha = glissando curto e macio de seno (260-900 Hz, sobe devagar, ~90-200 ms), envelope sem ataque duro,
sem "tick" e sem grave; cada uma com altura/duração diferente. Bomba = zumbido bem baixo em Lá2 (110 Hz)
com 220 Hz mais fraco e um sopro de ruído estreito-ish bem abafado; ciclos inteiros, respiração lenta.
Reverb circular pequeno de tubo de vidro. Ruído de bolha só em banda média e baixíssimo.
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

REP = B.ROOT / "reports" / "audio" / "v08_m3"
M2 = B.ROOT / "reports" / "audio" / "v08_m2"
L = 6.1


def bubble(rng, f0, dur):
    n = ns(dur)
    t = tvec(n)
    f = f0 * (1 + 0.75 * (1 - np.exp(-t / (dur * 0.35))))   # sobe devagar, bolha subindo
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.sin(np.pi * np.minimum(1, t / dur)) ** 1.5 * np.exp(-t / (dur * 0.6))  # macio, sem ataque duro
    env *= np.minimum(1, t / 0.008)
    return filt(np.sin(ph) * env, 150, 2600, 1)


def build(rng, n_bub, clusters, hum_gain, breath_gain):
    n = ns(L)
    t = tvec(n)
    dry = np.zeros(n)
    starts = []
    if clusters:   # grupos de 2-4 bolhas rápidas, com vazios entre eles
        slots = (np.arange(n_bub) + rng.uniform(0.1, 0.9, n_bub)) / n_bub * L
        for s in slots:
            for j in range(int(rng.integers(2, 5))):
                starts.append(s + j * rng.uniform(0.07, 0.17))
    else:
        starts = list((np.arange(n_bub) + rng.uniform(0.1, 0.9, n_bub)) / n_bub * L)
    for at in starts:
        f0 = rng.choice([280, 340, 420, 520, 640]) * rng.uniform(0.94, 1.06)
        add_circ(dry, bubble(rng, f0, rng.uniform(0.09, 0.2)), ns(at) % n, rng.uniform(0.35, 1.0))
    bub = norm_rms(reverb(dry, rng, decay=0.45, mix=0.45, lp=3500, circular=True))
    breath = 0.7 + 0.3 * periodic_ctrl(n, L, rng, 1, 3)
    hum = np.zeros(n)
    for k, a in ((110, 1.0), (220, 0.28), (165, 0.12)):
        hum += a * np.sin(2 * np.pi * fr(k, L) * t + rng.uniform(0, 6.28))
    hum *= 1 + 0.06 * np.sin(2 * np.pi * fr(1.0, L) * t)
    hum = norm_rms(hum)
    blow = norm_rms(filt(rng.standard_normal(n), 180, 700, 2, circular=True)) * breath
    x = bub + hum * hum_gain + blow * breath_gain
    return filt(x, 70, 4000, 2, circular=True)


VARS = {
    "A": ("Borbulhar leve", dict(n_bub=7, clusters=False, hum_gain=0.10, breath_gain=0.05)),
    "B": ("Bomba com poucas bolhas", dict(n_bub=3, clusters=False, hum_gain=0.38, breath_gain=0.16)),
    "C": ("Aquário em rajadas (recomendada)", dict(n_bub=3, clusters=True, hum_gain=0.18, breath_gain=0.08)),
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


def tile(x, secs, off=0.0):
    x = np.roll(x, -int(off * SR))
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
        xi = write_wav(REP / f"cultivator_loop_{k}.wav", finalize(build(rng_for(f"v08m3:cultivator:{k}"), **kw), True, -34.0))
        out[k] = xi
        info(f"cultivator_loop_{k}", f"cultivator_loop_{k}.wav", xi, True)
    T = 20.0
    mist = tile(read(B.OUT_DIR / "amb_mist.wav"), T)
    coll = tile(read(M2 / "collector_loop_C.wav"), T)
    GAIN = 0.4
    for k in VARS:
        c = out[k].astype(float) / 32768
        three = sum(tile(c, T, off) * g for off, g in ((0.0, 1.0), (2.3, 0.8), (4.1, 0.6)))  # 3 cultivadores a distâncias/fases diferentes
        one = tile(c, T)
        for name, mx in ((f"mix_base3_{k}", mist * 0.7 + coll * 0.4 * 0.7 + three * GAIN),
                         (f"mix_solo_{k}", mist * 0.7 + one * GAIN)):
            info(name, f"{name}.wav", write_wav(REP / f"{name}.wav", mx * 0.95), False)
    (REP / "v08m3_meta.js").write_text("// gerado por tools/audio/v08_cultivator.py, não editar\nwindow.M3_META = "
                                       + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
