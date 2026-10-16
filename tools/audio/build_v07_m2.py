"""v0.7 Lore M2 · Props e scanner do construtor: scan_loop e scan_done (A/B). Fora do jogo.

Uso:  python3 tools/audio/build_v07_m2.py

Saída (tudo em reports/audio/v07_m2_scanner/pendentes/, NADA em assets/audio/):
  scan_loop_A.wav (loop periódico 1,6 s), scan_loop_B.wav (sweep único 1,6 s),
  scan_done_A.wav, scan_done_B.wav, mix_*.wav (simulações) e ../v07m2_meta.js.

Família do construtor (build, dismantle_charge): feixe de scanner + tiquinhos digitais. Aqui mais
agudo e fino que o dismantle (sem serra grave), sem tom de tambor, sem ressonância estreita.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, Track, add_circ, bl_wave, bump, filt, finalize, loudness, midi,  # noqa: E402
                         noise_burst, noise_sweep, norm_rms, ns, perc, phase_of, reverb, rng_for,
                         tail_cut, tvec, waveform_peaks, write_wav, fr)

REP = B.ROOT / "reports" / "audio" / "v07_m2_scanner"
PEND = REP / "pendentes"


def loop_scan_A(rng):
    """Feixe vai-e-vem (loop periódico de 1,6 s): um tom fino varre 500 -> 1500 -> 500 Hz
    (cos suave, então a emenda é contínua em fase e em frequência), com um hum em Lá4 por
    baixo e tremulação de 5 Hz (8 ciclos), um véu de ar agudo que acompanha a varredura e
    tiquinhos de linha de scan irregulares. Reverb circular curto."""
    L = 1.6
    n = ns(L)
    t = tvec(n)
    u = 0.5 - 0.5 * np.cos(2 * np.pi * t / L)           # 0 -> 1 -> 0
    f0, d = 500.0, 1000.0                                # média 1000 Hz = 1600 ciclos em L
    ph = 2 * np.pi * (f0 * t + d * (0.5 * t - L / (4 * np.pi) * np.sin(2 * np.pi * t / L)))
    beam = np.sin(ph) + 0.22 * np.sin(2 * ph + 0.7)
    beam *= 0.55 + 0.45 * u
    hum = np.sin(2 * np.pi * fr(440, L) * t) + 0.3 * np.sin(2 * np.pi * fr(660, L) * t + 1.1)
    hum *= 0.8 + 0.2 * np.sin(2 * np.pi * 5 * t)
    air = norm_rms(filt(rng.standard_normal(n), 2200, 7500, 1, circular=True)) * u ** 1.5
    ticks = np.zeros(n)
    at = 0.0
    while at < L:
        add_circ(ticks, noise_burst(rng, 2500, 7000, 0.0002, 0.0012, 0.008, order=1), ns(at) % n,
                 rng.uniform(0.5, 1.0))
        at += rng.uniform(0.6, 1.4) / 16
    x = norm_rms(beam) * 0.5 + norm_rms(hum) * 0.12 + air * 0.07 + norm_rms(ticks) * 0.07
    x = filt(x, 120, 9000, 1, circular=True)
    return reverb(x, rng, decay=0.5, mix=0.12, lp=4500, circular=True)


def sweep_scan_B(rng):
    """Varredura única que sobe (1,6 s): tom fino de triângulo filtrado Mi4 -> Mi6 (duas
    oitavas) em curva suave, uma segunda voz em quinta que entra no meio, véu de ar subindo,
    tiquinhos acelerando. Entra em 40 ms; termina em fade, mas pode ser cortado em qualquer
    ponto (o Dev põe fade de ~40 ms no stop). Não é pra repetir em loop."""
    tr = Track()
    L = 1.58
    n = ns(L)
    t = tvec(n)
    k = t / L
    f = 330 * 4 ** (k ** 0.9)
    beam = filt(bl_wave(f, n, "tri", 5000), None, 3600, 1)
    beam2 = np.sin(phase_of(f * 1.5 * 1.002, n)) * k ** 1.4
    trem = 0.85 + 0.15 * np.sin(2 * np.pi * np.cumsum(4 + 10 * k) / SR)
    env = np.minimum(1, t / 0.04) * (0.4 + 0.6 * k ** 0.8) * np.clip((L - t) / 0.06, 0, 1)
    tr.add((beam * 0.6 + beam2 * 0.22) * trem * env, 0, 0.5)
    tr.add(noise_sweep(rng, L, 1500, 6000, 2.5) * env * k, 0, 0.07)
    B.scan_ticks(rng, tr, 0.08, L - 0.05, 8, 26, 0.12)
    return tail_cut(reverb(tr.render(), rng, decay=0.4, mix=0.1, lp=4000), 1.66, 0.08)


def _soft_note(m, dur, decay, harm=0.18, att=0.004):
    q = ns(dur)
    tt = tvec(q)
    f = midi(m)
    x = np.sin(phase_of(f, q)) + harm * np.sin(phase_of(2 * f, q, 0.5))
    return x * perc(q, att, decay)


def sfx_done_A(rng):
    """"Salvo" (~0,55 s): duas notas macias de seno subindo uma quinta (Lá4 -> Mi5, 90 ms
    entre elas), um tiquinho de trava de ruído bem baixo no começo e reverb curto. Mais grave
    e mais calmo que o diagram_read (sem varredura, sem sino de 1 s) e sem o clack do
    dismantle_done."""
    tr = Track()
    tr.add(noise_burst(rng, 1800, 6000, 0.0002, 0.001, 0.008, order=1), 0, 0.12)
    tr.add(_soft_note(69, 0.4, 0.09), 0.0, 0.5)
    tr.add(_soft_note(76, 0.5, 0.15), 0.09, 0.5)
    tr.add(_soft_note(88, 0.3, 0.05, 0.0), 0.09, 0.05)   # brilho Mi6 curtinho
    return tail_cut(reverb(tr.render(), rng, decay=0.55, mix=0.2, lp=4500), 0.62, 0.15)


def sfx_done_B(rng):
    """"Dado travado" (~0,6 s): glide curto e fino subindo (Lá4 -> Lá5, 90 ms) que pousa num
    acorde aberto de Ré5 + Lá5 + Mi6 em triângulo filtrado, ataque macio e decaimento
    médio. Sem arpejo: soa como uma coisa só que assenta."""
    tr = Track()
    n = ns(0.1)
    t = tvec(n)
    f = 440 * 2 ** (t / 0.1)
    tr.add(np.sin(phase_of(f, n)) * bump(n, 0.8), 0, 0.2)
    for m, g, dec in ((74, 0.34, 0.16), (81, 0.3, 0.2), (88, 0.14, 0.1)):
        q = ns(0.55)
        v = filt(bl_wave(midi(m), q, "tri", 5000), None, 4200, 1)
        tr.add(v * perc(q, 0.012, dec), 0.085, g)
    tr.add(noise_burst(rng, 2000, 6500, 0.001, 0.02, 0.1, order=1), 0.08, 0.05)
    return tail_cut(reverb(tr.render(), rng, decay=0.6, mix=0.2, lp=4500), 0.68, 0.15)


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


def tile(x, secs):
    return np.tile(x, int(np.ceil(secs * SR / len(x))))[: ns(secs)]


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    meta = {}

    def info(key, file, xi, loop):
        xf = xi.astype(float) / 32768
        m = {"file": "pendentes/" + file, "loop": loop, "duration": round(len(xi) / SR, 3),
             "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
             "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(xf ** 2)))), 1),
             "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(xi), "bands": bands(xf),
             "clip": int(np.sum(np.abs(xi) >= 32767)), "first": int(xi[0]), "last": int(xi[-1])}
        if loop:
            d = np.abs(np.diff(xi.astype(float)))
            m["seam"] = float(abs(int(xi[0]) - int(xi[-1])))
            m["seam_ref"] = round(float(np.percentile(d, 99.9)), 1)
        if key.startswith("scan"):
            m["tonal_db"], m["tonal_hz"] = tonal_peak(xf)
        meta[key] = m
        print(key, {k: v for k, v in m.items() if k != "wave"})

    out = {}
    out["scan_loop_A"] = (write_wav(PEND / "scan_loop_A.wav",
                          finalize(loop_scan_A(rng_for("v07m2:scan_loop_A")), True, -28.0)), True)
    out["scan_loop_B"] = (write_wav(PEND / "scan_loop_B.wav",
                          finalize(sweep_scan_B(rng_for("v07m2:scan_loop_B")), False, -25.0)), False)
    out["scan_done_A"] = (write_wav(PEND / "scan_done_A.wav",
                          finalize(sfx_done_A(rng_for("v07m2:scan_done_A")), False, -22.0)), False)
    out["scan_done_B"] = (write_wav(PEND / "scan_done_B.wav",
                          finalize(sfx_done_B(rng_for("v07m2:scan_done_B")), False, -22.0)), False)
    for k, (xi, lp) in out.items():
        info(k, k + ".wav", xi, lp)

    # simulação: segura 1,5 s (volume 0.4), solta e toca o done (0.6); 2 scans seguidos
    def f(k):
        return out[k][0].astype(float) / 32768
    for lk in ("A", "B"):
        for dk in ("A", "B"):
            T = 7.0
            mix = np.zeros(ns(T))
            for start in (0.5, 4.0):
                sl = f("scan_loop_" + lk)
                seg = tile(sl, 1.5) if lk == "A" else sl[: ns(1.5)]
                seg = seg.copy()
                fo = ns(0.04)
                seg[-fo:] *= np.linspace(1, 0, fo)
                a = ns(start)
                mix[a:a + len(seg)] += seg * 0.4
                d = f("scan_done_" + dk)
                b = a + len(seg) + ns(0.03)
                mix[b:b + len(d)] += d * 0.6
            key = f"mix_{lk}{dk}"
            xi = write_wav(PEND / f"{key}.wav", mix * 0.95)
            info(key, f"{key}.wav", xi, False)
    (REP / "v07m2_meta.js").write_text("// gerado por tools/audio/build_v07_m2.py, não editar\nwindow.M2_META = "
                                       + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
