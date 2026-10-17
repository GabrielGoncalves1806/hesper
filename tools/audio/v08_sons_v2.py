"""v0.8 · Sons v2: refaz collector_loop e cultivator_loop sem "sapo". Fora do jogo.

Uso:  python3 tools/audio/v08_sons_v2.py
Saída (só reports/audio/v08_sons_v2/, NADA em assets/audio/): collector_v2_A/B/C.wav, cultivator_v2_A/B/C.wav,
cópias dos antigos (old_*.wav), mixes "3 juntos", v08sons2_meta.js e index.html.

Por que o v1 coaxava: bolhas eram blips de seno com pitch subindo (chirp) em grade quase regular.
Agora: NENHUM oscilador nas bolhas/gotas. Tudo é ruído filtrado em banda larga (Q baixo), sem varredura de pitch,
com instantes de Poisson (intervalos exponenciais, em rajadas no caso do aquário). Tons só nos zumbidos de
bomba/motor (50-120 Hz, ciclos inteiros no loop) e bem baixos.
Cultivador L = 6,1 s, coletor L = 5,0 s (mesmos de antes).
"""
from __future__ import annotations

import json
import shutil
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, add_circ, filt, finalize, loudness, norm_rms, ns, periodic_ctrl,  # noqa: E402
                         reverb, rng_for, tvec, waveform_peaks, write_wav, fr)

REP = B.ROOT / "reports" / "audio" / "v08_sons_v2"
M2 = B.ROOT / "reports" / "audio" / "v08_m2"
M3 = B.ROOT / "reports" / "audio" / "v08_m3"
LC, LK = 5.0, 6.1


def poisson(rng, rate, L, min_gap=0.0):
    if rate <= 0:
        return []
    ts, t = [], rng.exponential(1 / rate)
    while t < L:
        ts.append(t)
        t += max(min_gap, rng.exponential(1 / rate))
    return ts


def lowdrift(n, L, rng, lo=0.6, kmax=4):
    return lo + (1 - lo) * periodic_ctrl(n, L, rng, 1, kmax)


# ---------------- cultivador ----------------
def bubble_n(rng, fc, tau):
    """Bolha de ruído: bandpass LARGO (sem ressonância), ataque ~2 ms, decaimento rápido, sem pitch."""
    n = ns(tau * 7 + 0.01)
    t = tvec(n)
    env = (1 - np.exp(-t / 0.0022)) * np.exp(-t / tau)
    return filt(rng.standard_normal(n), fc / 1.8, fc * 1.8, 1) * env


def glub(rng, fc, dur):
    """'glub' abafado: ruído grave (lowpass), contorno suave que fecha. Sem oscilador."""
    n = ns(dur)
    t = tvec(n)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2 * np.exp(-t / (dur * 0.7))
    return filt(rng.standard_normal(n), fc * 0.35, fc * 1.4, 2) * env


def build_cult(rng, rate, burst, glub_rate, hum_gain, air_gain, glass_gain, bub_gain=1.0):
    L = LK
    n = ns(L)
    t = tvec(n)
    dry = np.zeros(n)
    starts = []
    if burst:   # rajadas: instantes Poisson de "disparo", cada um solta 2-7 bolhas com intervalos exponenciais curtos
        for s in poisson(rng, rate, L, 0.25):
            at = s
            for _ in range(int(rng.integers(2, 8))):
                starts.append(at)
                at += rng.exponential(0.05) + 0.012
    else:
        starts = poisson(rng, rate, L)
    for at in starts:
        fc = np.exp(rng.uniform(np.log(450), np.log(2400)))
        add_circ(dry, bubble_n(rng, fc, rng.uniform(0.007, 0.022)), ns(at) % n, rng.lognormal(-0.5, 0.5))
    bub = norm_rms(reverb(filt(dry, 150, 3800, 1, circular=True), rng, decay=0.3, mix=0.3, lp=3500, circular=True))
    g = np.zeros(n)
    for at in poisson(rng, glub_rate, L, 0.8):
        add_circ(g, glub(rng, rng.uniform(130, 210), rng.uniform(0.08, 0.14)), ns(at) % n, rng.uniform(0.6, 1.0))
    g = norm_rms(g) if glub_rate > 0 else np.zeros(n)
    # bomba: ruído grave 45-130 Hz (sem tom fixo) + um fio de 55 Hz bem fraco; respira devagar
    breath = lowdrift(n, L, rng, 0.65, 3)
    hum = norm_rms(filt(rng.standard_normal(n), 45, 130, 2, circular=True)) * breath
    hum += 0.25 * norm_rms(np.sin(2 * np.pi * fr(55, L) * t + rng.uniform(0, 6.28)))
    air = norm_rms(filt(rng.standard_normal(n), 1800, 5200, 1, circular=True)) * lowdrift(n, L, rng, 0.3, 5)
    gl = np.zeros(n)   # vidro: pontinhos agudos de ruído, raros, banda larga
    for at in poisson(rng, 0.9, L, 0.4):
        m = ns(0.03)
        tt = tvec(m)
        add_circ(gl, filt(rng.standard_normal(m), 4500, 9500, 1) * np.exp(-tt / 0.006), ns(at) % n, rng.uniform(0.3, 1))
    gl = norm_rms(gl) if glass_gain > 0 else np.zeros(n)
    x = bub * bub_gain + g * 0.9 * (glub_rate > 0) + hum * hum_gain + air * air_gain + gl * glass_gain
    return filt(x, 40, 9000, 2, circular=True), starts


# ---------------- coletor ----------------
def drop_n(rng, fc):
    """Gota: clique curtíssimo + toc de ruído banda média com Q moderado (~2) e decaimento curto. Cada gota
    tem fc contínuo diferente: sem escala, sem melodia."""
    n = ns(0.12)
    t = tvec(n)
    tick = filt(rng.standard_normal(n), 2500, 7500, 1) * np.exp(-t / 0.0012) * 0.5
    body = filt(rng.standard_normal(n), fc * 0.7, fc * 1.4, 2) * (1 - np.exp(-t / 0.001)) * np.exp(-t / rng.uniform(0.014, 0.03))
    return tick + body * 1.4


def build_coll(rng, rate, double_p, motor_gain, trickle_gain, hum_gain):
    L = LC
    n = ns(L)
    t = tvec(n)
    dry = np.zeros(n)
    for at in poisson(rng, rate, L, 0.12):
        fc = np.exp(rng.uniform(np.log(900), np.log(3300)))
        a = rng.lognormal(-0.3, 0.45)
        add_circ(dry, drop_n(rng, fc), ns(at) % n, a)
        if rng.random() < double_p:   # segunda gota menor logo depois (pinga em cascata)
            add_circ(dry, drop_n(rng, fc * rng.uniform(0.7, 1.3)), ns(at + rng.uniform(0.07, 0.22)) % n, a * 0.35)
    drops = norm_rms(reverb(dry, rng, decay=0.5, mix=0.5, lp=4500, circular=True))
    breath = lowdrift(n, L, rng, 0.7, 3)
    motor = norm_rms(filt(rng.standard_normal(n), 60, 260, 2, circular=True)) * breath
    hum = norm_rms(np.sin(2 * np.pi * fr(55, L) * t + rng.uniform(0, 6.28)) + 0.4 * np.sin(2 * np.pi * fr(110, L) * t + rng.uniform(0, 6.28)))
    hum *= 1 + 0.08 * np.sin(2 * np.pi * fr(0.8, L) * t)
    # escorrer: ruído 1,6-5 kHz com amplitude modulada por ruído lento e irregular (gorgolejo sem pitch)
    mod = np.abs(filt(rng.standard_normal(n), 3, 30, 1, circular=True))
    mod = mod / mod.max()
    trick = norm_rms(filt(rng.standard_normal(n), 1600, 5000, 1, circular=True)) * (0.25 + mod ** 1.5) * lowdrift(n, L, rng, 0.5, 4)
    x = drops + motor * motor_gain + hum * hum_gain + trick * trickle_gain
    return filt(x, 45, 8000, 2, circular=True)


CULT = {
    "A": ("Aerador contínuo", "Muitas bolhinhas minúsculas e espaçadas ao acaso (Poisson, ~7 por segundo), um fio de ar e a bomba lá no fundo. Sem glub. É o mais \"chuvisco de bolhas\", bem neutro e fácil de somar 3.",
          dict(rate=7.5, burst=False, glub_rate=0.0, hum_gain=0.30, air_gain=0.10, glass_gain=0.0)),
    "B": ("Biorreator", "Bolhas raras (~2 por segundo), a bomba mais presente (ronco grave) e uns glubs graves e abafados de vez em quando. Parece mais máquina de laboratório que aquário.",
          dict(rate=2.2, burst=False, glub_rate=0.45, hum_gain=0.75, air_gain=0.06, glass_gain=0.0)),
    "C": ("Aquário (recomendada)", "Rajadas curtas de 2-7 bolhinhas em instantes aleatórios, com respiros entre elas, glub ocasional bem baixo, ronco de bomba leve e pontinhos de vidro quase inaudíveis. Mais orgânico, menos \"panela\".",
          dict(rate=0.7, burst=True, glub_rate=0.3, hum_gain=0.45, air_gain=0.07, glass_gain=0.05)),
}
COLL = {
    "A": ("Reservatório", "Pingos mais frequentes e bem espalhados caindo numa poça fechada, com um motor muito baixo. É a que mais soa a \"goteira\".",
          dict(rate=2.2, double_p=0.25, motor_gain=0.25, trickle_gain=0.10, hum_gain=0.10)),
    "B": ("Bomba + escorrer", "Quase sem gotas: o motor grave macio e um escorrer de água constante. Funciona como camada de fundo; a que menos chama atenção.",
          dict(rate=0.6, double_p=0.1, motor_gain=0.85, trickle_gain=0.45, hum_gain=0.30)),
    "C": ("Mistura (recomendada)", "Equilíbrio: gotas irregulares com pausas, motor macio por baixo e um fio de água escorrendo. Dá a ideia de máquina trabalhando na chuva sem competir com ela.",
          dict(rate=1.3, double_p=0.3, motor_gain=0.5, trickle_gain=0.22, hum_gain=0.18)),
}


# ---------------- análise ----------------
def bands(x):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    p = np.abs(np.fft.rfft(x)) ** 2
    ed = [(20, 150), (150, 600), (600, 2500), (2500, 6000), (6000, 16000)]
    return [round(float(100 * p[(f >= a) & (f < b)].sum() / p.sum()), 1) for a, b in ed]


def tonal_peak(x, lo=150, hi=12000):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / SR)
    sm = np.convolve(X, np.ones(7) / 7, "same")
    best = (0.0, 0.0)
    k = int(100 / f[1])
    for i in np.nonzero((f > lo) & (f < hi))[0][::5]:
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


def env_regularity(x, L):
    """Pico da autocorrelação do envelope (10-60 ms de suavização) para atrasos de 120 ms a L/2, circular.
    Perto de 1 = ritmo regular perceptível; ruído irregular fica baixo."""
    w = int(0.02 * SR)
    e = np.sqrt(np.convolve(x ** 2, np.ones(w) / w, "same"))[::SR // 200]   # 200 Hz
    e = e - e.mean()
    ac = np.fft.irfft(np.abs(np.fft.rfft(e)) ** 2, len(e))
    ac /= ac[0]
    lo, hi = int(0.12 * 200), int(len(e) / 2)
    return round(float(ac[lo:hi].max()), 2)


def main():
    REP.mkdir(parents=True, exist_ok=True)
    meta = {}

    def info(key, file, xi, loop, label=""):
        xf = xi.astype(float) / 32768
        m = {"file": file, "loop": loop, "duration": round(len(xi) / SR, 3),
             "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
             "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(xf ** 2)))), 1),
             "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(xi), "bands": bands(xf), "label": label}
        if loop:
            d = np.abs(np.diff(xi.astype(float)))
            m["seam"] = float(abs(int(xi[0]) - int(xi[-1])))
            m["seam_ref"] = round(float(np.percentile(d, 99.9)), 1)
            m["tonal_db"], m["tonal_hz"] = tonal_peak(xf)
            m["tonal_mid_db"], m["tonal_mid_hz"] = tonal_peak(xf, 300, 1500)
            m["regularity"] = env_regularity(xf, len(xf) / SR)
        meta[key] = m
        print(key, {k: v for k, v in m.items() if k != "wave"})

    cult, coll = {}, {}
    for k, (lab, _, kw) in CULT.items():
        x, _ = build_cult(rng_for(f"v08s2:cult:{k}"), **kw)
        cult[k] = write_wav(REP / f"cultivator_v2_{k}.wav", finalize(x, True, -34.0))
        info(f"cultivator_v2_{k}", f"cultivator_v2_{k}.wav", cult[k], True, lab)
    for k, (lab, _, kw) in COLL.items():
        x = build_coll(rng_for(f"v08s2:coll:{k}"), **kw)
        coll[k] = write_wav(REP / f"collector_v2_{k}.wav", finalize(x, True, -31.0))
        info(f"collector_v2_{k}", f"collector_v2_{k}.wav", coll[k], True, lab)
    # antigos (cópia só pra comparar)
    shutil.copy(M3 / "cultivator_loop_C.wav", REP / "old_cultivator_C.wav")
    shutil.copy(M2 / "collector_loop_C.wav", REP / "old_collector_C.wav")
    old_c, old_k = read(REP / "old_cultivator_C.wav"), read(REP / "old_collector_C.wav")
    info("old_cultivator_C", "old_cultivator_C.wav", (old_c * 32767).astype(np.int16), True, "v1 (sapos)")
    info("old_collector_C", "old_collector_C.wav", (old_k * 32767).astype(np.int16), True, "v1 (sapos)")

    T = 20.0
    mist = tile(read(B.OUT_DIR / "amb_mist.wav"), T)
    OFFS = ((0.0, 1.0), (2.3, 0.8), (4.1, 0.6))

    def three(c):
        return sum(tile(c, T, off) * g for off, g in OFFS)

    for k in CULT:
        c = cult[k].astype(float) / 32768
        info(f"mix3_cult_{k}", f"mix3_cult_{k}.wav", write_wav(REP / f"mix3_cult_{k}.wav", (mist * 0.7 + three(c) * 0.4) * 0.95), False, "3 juntos")
    c = old_c
    info("mix3_cult_old", "mix3_cult_old.wav", write_wav(REP / "mix3_cult_old.wav", (mist * 0.7 + three(c) * 0.4) * 0.95), False, "3 juntos v1")
    # bônus: 3 canais com sementes diferentes (variante C), pra ver quanto ganha em relação a só defasar
    ch = []
    for i in range(3):
        x, _ = build_cult(rng_for(f"v08s2:cult:C:ch{i}"), **CULT["C"][2])
        ch.append(finalize(x, True, -34.0))
    mixseed = sum(tile(ch[i], T, OFFS[i][0]) * OFFS[i][1] for i in range(3))
    info("mix3_cult_C_seeds", "mix3_cult_C_seeds.wav", write_wav(REP / "mix3_cult_C_seeds.wav", (mist * 0.7 + mixseed * 0.4) * 0.95), False, "3 sementes")
    rain_proxy = tile(read(B.OUT_DIR / "amb_mist.wav"), T)
    for k in COLL:
        c = coll[k].astype(float) / 32768
        info(f"mix_coll_{k}", f"mix_coll_{k}.wav", write_wav(REP / f"mix_coll_{k}.wav", (rain_proxy * 0.7 + tile(c, T) * 0.4) * 0.95), False, "com amb_mist")
    info("mix_coll_old", "mix_coll_old.wav", write_wav(REP / "mix_coll_old.wav", (rain_proxy * 0.7 + tile(old_k, T) * 0.4) * 0.95), False, "v1")
    (REP / "v08sons2_meta.js").write_text("// gerado por tools/audio/v08_sons_v2.py, não editar\nwindow.META = "
                                          + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")
    descr = {"cult": {k: (v[0], v[1]) for k, v in CULT.items()}, "coll": {k: (v[0], v[1]) for k, v in COLL.items()}}
    (REP / "v08sons2_desc.js").write_text("window.DESC = " + json.dumps(descr, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
