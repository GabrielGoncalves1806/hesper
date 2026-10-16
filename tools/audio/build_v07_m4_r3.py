"""v0.7 M4 · rodada 3 do amb_vesper: E e F. Fora do jogo.

Uso:  python3 tools/audio/build_v07_m4_r3.py   (rode DEPOIS do build_v07_m4.py; acrescenta E/F no meta)

Base = o próprio amb_cave aprovado: mesmo rng, mesmo drone (Lá1/Mi2/Lá2 + fio de Dó3), mesmos brilhos
frios, mesmo eco de caverna. Trocam-se só os eventos: no lugar das gotas entram "zzt" de fio solto
longe (amostra CC0 do BMacZero processada), rangidos de casco lentos e abafados e metal assentando
(síntese). Sem ruído largo de ventilação.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
import build_v07_m4 as M  # noqa: E402
from build_audio import (SR, add_circ, bump, cave_space, filt, finalize, loudness, midi, norm_rms, ns,  # noqa: E402
                         pad_voice, periodic_ctrl, rng_for, space_mix, tvec, waveform_peaks, write_wav)

VEND = B.ROOT / "tools" / "audio" / "vendor" / "oga_electricity"
L = 28.0


def read(p):
    with wave.open(str(p), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768


def zap(src, rate, lp, hp=90, fade_in=0.03):
    """Amostra de faísca empurrada pra longe: tocada mais lenta (grave), passa-baixa, entrada suave."""
    n = int(len(src) / rate)
    x = np.interp(np.arange(n) * rate, np.arange(len(src)), src)
    x = filt(x, hp, lp, 2)
    f = ns(fade_in)
    x[:f] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(f) / f)
    x *= np.exp(-np.arange(n) / SR / 0.18)
    return x / (np.abs(x).max() + 1e-9)


def settle(rng, dur):
    """Metal assentando: sopro de banda larga e grave (sem tom), ataque lento."""
    n = ns(dur)
    x = filt(rng.standard_normal(n), 50, 260, 2) * bump(n, 0.4)
    return x / np.abs(x).max()


def amb_vesper_ef(variant):
    rng = rng_for("amb_cave")                       # mesma sequência do amb_cave: pad e brilhos idênticos
    n = ns(L)
    drone = sum(g * pad_voice(n, L, rng, midi(m), detune=(-0.1, 0.0, 0.1), harm=(1.0, 0.15, 0.04), swell=(1, 3))
                for m, g in ((33, 0.4), (40, 0.6), (45, 1.0), (52, 0.55)))
    shade = pad_voice(n, L, rng, midi(48), harm=(1.0,), swell=(2, 4)) * 0.15
    pad = norm_rms(filt(drone + shade, 30, 900, 2, circular=True))
    shimmer = filt(B.glints(n, rng, (64, 69), 2, (4.0, 7.0), (0.12, 0.18)), None, 1800, 1, circular=True)
    r = rng_for("v07m4:amb_vesper_" + variant)
    F = variant == "F"
    sp = read(VEND / "spark.wav")
    cs = read(VEND / "continuousspark.wav")
    ev = np.zeros(n)
    zaps = ([(2.5, sp, 0.55, 1100, 1.0), (9.0, cs, 0.6, 900, 0.8), (16.5, sp, 0.7, 1300, 0.9), (23.0, sp, 0.5, 800, 1.0)]
            if not F else
            [(1.5, sp, 0.55, 1100, 1.0), (5.5, cs, 0.6, 900, 0.8), (8.8, sp, 0.7, 1300, 0.9), (13.0, sp, 0.5, 800, 1.0),
             (17.2, cs, 0.5, 1000, 0.9), (21.0, sp, 0.6, 1200, 0.8), (25.2, sp, 0.65, 900, 0.9)])
    for at, s_, rate, lp, g in zaps:
        add_circ(ev, zap(s_, rate, lp) * g * ZAP_GAIN, ns(at) % n)
    creaks = ([(6.0, 5.0, 38, 30), (19.5, 5.5, 34, 45)] if not F
              else [(3.5, 5.0, 40, 31), (11.0, 5.5, 34, 46), (19.0, 6.0, 44, 32)])
    for at, d, f0, f1 in creaks:
        add_circ(ev, M.far_creak(r, d, f0, f1) * CREAK_GAIN, ns(at) % n)
    for at in ((13.5,) if not F else (7.0, 15.0, 23.5)):
        add_circ(ev, settle(r, 2.2) * SETTLE_GAIN, ns(at) % n)
    ev = cave_space(ev, r, circular=True, decay=4.0, mix=1.1, lp=2400)
    rumble = norm_rms(filt(r.standard_normal(n), 22, 140, 2, circular=True))
    rumble *= 0.06 * (0.5 + 0.5 * periodic_ctrl(n, L, r, 1, 4))
    x = space_mix(rng, pad, shimmer, ev + rumble, pad_rev=(6.5, 0.5, 1600), sh_rev=(6.0, 0.6, 3500))
    if F:   # F: um pouco mais de nave, um zumbido de transformador grave entrando e saindo em fade
        hum = pad_voice(n, L, r, midi(33), detune=(-0.05, 0.05), harm=(0.3, 1.0, 0.7, 0.3), swell=(1, 2))
        hum = norm_rms(filt(hum, 60, 500, 2, circular=True)) * M.presence(n, [(10.0, 12.0)])
        x = x + norm_rms(hum) * 0.02 * np.sqrt(np.mean(pad ** 2)) / max(1e-9, np.sqrt(np.mean(hum ** 2)))
    return x


ZAP_GAIN, CREAK_GAIN, SETTLE_GAIN = 4.5, 2.2, 1.3


def main():
    meta_p = M.REP / "v07m4_meta.js"
    meta = json.loads(meta_p.read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";"))
    with wave.open(str(B.OUT_DIR / "amb_cave.wav")) as w:
        cave = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768
    cave_ld = float(loudness(cave, True))
    for v in "EF":
        xi = write_wav(M.PEND / f"amb_vesper_{v}.wav", finalize(amb_vesper_ef(v), True, cave_ld))
        xf = xi.astype(float) / 32768
        d = np.abs(np.diff(xi.astype(float)))
        meta[f"amb_vesper_{v}"] = {
            "file": f"pendentes/amb_vesper_{v}.wav", "loop": True, "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(20 * np.log10(np.abs(xf).max())), 2),
            "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(xf ** 2)))), 1),
            "loudness_db": round(float(loudness(xf, True)), 1), "wave": waveform_peaks(xi), "bands": M.bands(xf),
            "clip": int(np.sum(np.abs(xi) >= 32767)), "first": int(xi[0]), "last": int(xi[-1]),
            "seam": float(abs(int(xi[0]) - int(xi[-1]))), "seam_ref": round(float(np.percentile(d, 99.9)), 1),
            "transient_db": M.transient_db(xf),
            "transient_hp_db": M.transient_db(B.filt(xf, 200, None, 2, circular=True)),
            "tonal_db": M.tonal_peak(xf)[0], "tonal_hz": M.tonal_peak(xf)[1]}
        seg = np.concatenate([cave[: ns(10)] * 0.3, xf[: ns(14)] * 0.3])
        write_wav(M.PEND / f"cmp_cave_vesper_{v}.wav", seg * 0.95)
        print(v, {k: val for k, val in meta[f"amb_vesper_{v}"].items() if k != "wave"})
    meta_p.write_text("// gerado por tools/audio/build_v07_m4.py + build_v07_m4_r3.py, não editar\nwindow.M4_META = "
                      + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
