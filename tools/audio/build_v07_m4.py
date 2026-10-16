"""v0.7 M4 · Interior da VÉSPER-7: amb_vesper, door_stuck, spark (2 candidatos cada). Fora do jogo.

Uso:  python3 tools/audio/build_v07_m4.py

Saída (tudo em reports/audio/v07_m4_vesper/pendentes/, NADA em assets/audio/):
  amb_vesper_A/B.wav (loop 28 s, o mesmo formato do amb_cave), door_stuck_A/B.wav,
  spark_A/A1/A2 e spark_B/B1/B2.wav, mix_*.wav (simulações) e ../v07m4_meta.js.

Família do amb_cave: Lá grave, quinta vazia, reverb escuro, sem bicho. Aqui o espaço é
metal (reflexões mais curtas e secas que a caverna) e o drone é um zumbido de transformador
morto (Lá1 + harmônicos baixos, sem cantar). Sem seno grave com pitch nos sfx (nada de tambor),
sem ressonância estreita (nada de latinha).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, Track, add_circ, bump, filt, finalize, loudness, midi, noise_burst,  # noqa: E402
                         norm_rms, ns, pad_voice, periodic_ctrl, reverb, rng_for, tail_cut, tvec,
                         waveform_peaks, write_wav, cave_space, fr)

REP = B.ROOT / "reports" / "audio" / "v07_m4_vesper"
PEND = REP / "pendentes"
L = 28.0


def creak(rng, dur, f0, f1, harsh=1.0):
    """Gemido de casco: trem de pulsos (atrito pega-e-solta) cuja taxa desliza f0 -> f1,
    com tremida irregular na taxa e na amplitude, passado num filtro largo (sem pico estreito)."""
    n = ns(dur)
    t = tvec(n)
    k = t / dur
    jit = filt(rng.standard_normal(n), None, 25, 1)
    jit = jit / (np.abs(jit).max() + 1e-9)
    rate = (f0 + (f1 - f0) * (0.5 - 0.5 * np.cos(np.pi * k ** 0.8))) * (1 + 0.18 * jit * harsh)
    ph = np.cumsum(rate) / SR
    saw = (ph % 1.0) * 2 - 1
    pulse = saw - np.roll(saw, 1)                       # derivada: estalinhos do atrito
    pulse[0] = 0
    body = filt(pulse + 0.6 * saw, 160, 1800, 1)
    amp = 0.55 + 0.45 * np.clip(filt(rng.standard_normal(n), None, 18, 1) * 3 + 0.5, 0, 1)
    return body * amp * bump(n, 0.35) ** 0.8


def tick_hull(rng):
    """Casco esfriando: "tic" seco de banda larga, grave, sem tom."""
    tr = Track()
    tr.add(noise_burst(rng, 90, 700, 0.001, 0.025, 0.12, order=1), 0, 1.0)
    tr.add(noise_burst(rng, 800, 3200, 0.0004, 0.004, 0.03, order=1), 0.0, 0.3)
    return tr.render()


def metal_room(x, rng, circ=True):
    """Espaço de casco: reflexões bem próximas e cauda média/escura (menos caverna, mais cabine)."""
    return cave_space(x, rng, circular=circ, decay=2.4, mix=0.7, lp=2600)


def amb_vesper(rng, variant):
    n = ns(L)
    A = variant == "A"
    # zumbido morto: Lá1 + 2º e 3º harmônicos de transformador, tremida lenta (energia que falha)
    hum = sum(g * pad_voice(n, L, rng, midi(m), detune=(-0.07, 0.0, 0.07), harm=(1.0, 0.5, 0.25, 0.1),
                            swell=(1, 3)) for m, g in ((33, 1.0), (45, 0.35)))
    hum = norm_rms(filt(hum, 35, 520, 2, circular=True))
    flick = 0.8 + 0.2 * periodic_ctrl(n, L, rng, 3, 9, 0.6)
    # queda: o zumbido some um instante, 2x por volta (energia que não pega), suave pra não estalar
    gate = np.ones(n)
    for at, w in ((9.3, 0.5), (21.1, 0.35)):
        g = ns(w)
        add_circ(gate, -bump(g, 0.5) * 0.7, ns(at) % n)
    hum = hum * flick * gate
    # pad escuro de quinta vazia (mesma família do cave), baixinho
    pad = norm_rms(filt(sum(g * pad_voice(n, L, rng, midi(m), harm=(1.0, 0.1), swell=(1, 3))
                            for m, g in ((45, 1.0), (52, 0.7), (57, 0.25))), 40, 700, 2, circular=True))
    pad = reverb(pad, rng, decay=5.0, mix=0.5, lp=1500, circular=True)
    # rangidos do casco, em tempos irregulares
    creaks = np.zeros(n)
    plan = ([(3.2, 2.6, 62, 38), (11.5, 1.7, 47, 71), (17.8, 3.0, 85, 49), (24.0, 1.4, 55, 40)] if A
            else [(2.0, 1.2, 70, 52), (6.4, 2.4, 44, 33), (10.9, 1.5, 58, 82), (15.2, 2.9, 90, 52),
                  (20.0, 1.3, 40, 60), (24.8, 2.0, 66, 41)])
    for at, d, f0, f1 in plan:
        c = creak(rng, d, f0, f1) * rng.uniform(0.7, 1.0)
        add_circ(creaks, c, ns(at) % n)
    creaks = metal_room(creaks, rng)
    ticks = np.zeros(n)
    for at in ((5.1, 13.7, 19.4, 26.2) if A else (4.2, 8.8, 13.0, 18.6, 22.9)):
        add_circ(ticks, tick_hull(rng) * rng.uniform(0.5, 1.0), ns(at) % n)
    ticks = metal_room(ticks, rng)
    air = norm_rms(filt(rng.standard_normal(n), 120, 800, 1, circular=True)) * 0.006
    if A:
        x = norm_rms(hum) * 0.9 + norm_rms(pad) * 0.5 + norm_rms(creaks) * 0.38 + norm_rms(ticks) * 0.1 + air
    else:
        x = norm_rms(hum) * 0.6 + norm_rms(pad) * 0.6 + norm_rms(creaks) * 0.5 + norm_rms(ticks) * 0.12 + air
    return x


def door_stuck(rng, variant):
    tr = Track()
    # tranco do ferrolho: ruído grave de banda larga (nada de seno), corpo, estalo da trava
    tr.add(noise_burst(rng, 60, 380, 0.0008, 0.035, 0.14, order=2), 0, 2.2)
    tr.add(noise_burst(rng, 250, 2200, 0.0004, 0.012, 0.06, order=1), 0, 0.6)
    tr.add(noise_burst(rng, 1800, 7000, 0.0002, 0.0025, 0.02, order=1), 0.001, 0.22)
    for _ in range(int(rng.integers(4, 7))):                 # grãos de metal pesado chacoalhando
        hi = rng.uniform(1200, 4500)
        tr.add(noise_burst(rng, hi / 3, hi, 0.0002, rng.uniform(0.002, 0.006), 0.02, order=1),
               rng.uniform(0.01, 0.09), rng.uniform(0.1, 0.3))
    if variant == "A":
        # bate e volta um tiquinho (a trava não cede): ressalto seco 70 ms depois
        tr.add(noise_burst(rng, 120, 1500, 0.0005, 0.012, 0.06, order=1), 0.07, 0.35)
        tr.add(noise_burst(rng, 1500, 5000, 0.0002, 0.003, 0.02, order=1), 0.07, 0.15)
    else:
        # força e geme: bate, tenta empurrar (rangido curtíssimo e rouco) e bate de novo mais fraco
        tr.add(creak(rng, 0.22, 52, 70, 1.2), 0.11, 0.3)
        tr.add(noise_burst(rng, 90, 600, 0.0008, 0.018, 0.08, order=1), 0.33, 0.55)
        tr.add(noise_burst(rng, 500, 3000, 0.0003, 0.006, 0.03, order=1), 0.33, 0.35)
    x = tr.render()
    x = reverb(x, rng, decay=0.35, mix=0.14, lp=3000)
    return tail_cut(x, 0.4 if variant == "A" else 0.5, 0.08)


def spark(rng, variant, idx):
    tr = Track()
    if variant == "A":
        # crepitar: 3 a 6 estalinhos de banda larga em tempo irregular, o primeiro mais forte
        k = [4, 3, 5][idx]
        at = 0.0
        for i in range(k):
            hi = rng.uniform(5000, 9500)
            tr.add(noise_burst(rng, rng.uniform(1800, 3200), hi, 0.00008, rng.uniform(0.0004, 0.0012), 0.006, order=1),
                   at, (1.0 if i == 0 else rng.uniform(0.25, 0.6)))
            at += rng.uniform(0.008, 0.035) * (1 + 0.5 * i)
        dur = 0.14
    else:
        # zap: um estalo + chiadinho curto que cai de brilho (3 -> 1 kHz), meio "fsst"
        tr.add(noise_burst(rng, 2500, 9000, 0.00008, 0.0008, 0.006, order=1), 0, 1.0)
        m = ns([0.07, 0.09, 0.06][idx])
        z = rng.standard_normal(m)
        z = filt(z, [1500, 1300, 1800][idx], [5200, 4600, 6000][idx], 1) * np.exp(-tvec(m) / 0.02)
        tr.add(z, 0.003, 0.22)
        tr.add(noise_burst(rng, 3000, 8000, 0.0001, 0.0006, 0.005, order=1), 0.035 + 0.01 * idx, 0.4)
        dur = 0.15
    x = reverb(tr.render(), rng, decay=0.25, mix=0.12, lp=5000)
    return tail_cut(x, dur, 0.04)


def presence(n, spans):
    """Janelas de cosseno (0 -> 1 -> 0), periódicas, sem corte seco. spans = [(inicio s, largura s)]."""
    g = np.zeros(n)
    for at, w in spans:
        m = ns(w)
        add_circ(g, 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(m) / m), ns(at) % n)
    return np.minimum(g, 1.0)


def far_creak(rng, dur, f0, f1):
    """Rangido longínquo: gemido lento de atrito, ataque/saída de segundos, só graves (atrás de paredes)."""
    c = creak(rng, dur, f0, f1, 0.6)
    n = len(c)
    env = np.sin(np.pi * np.arange(n) / n) ** 2
    return filt(c, 70, 330, 2) * env


def amb_vesper2(rng, variant):
    """Rodada 2 (abandono e silêncio): drone Lá1 + quinta quase parados, ventilação morta (ar filtrado
    bem baixo respirando devagar), zumbido de transformador que entra e sai em fade de vários segundos
    e rangidos longínquos, lentos e abafados. D tem mais um rangido e 3 goteiras distantes e macias."""
    n = ns(L)
    C = variant == "C"
    drone = sum(g * pad_voice(n, L, rng, midi(m), detune=(-0.06, 0.0, 0.06), harm=(1.0, 0.3, 0.08), swell=(1, 2))
                for m, g in ((33, 1.0), (40, 0.55), (45, 0.7)))
    drone = norm_rms(filt(drone, 30, 420, 2, circular=True))
    drone = reverb(drone, rng, decay=4.5, mix=0.4, lp=1400, circular=True)
    hum = pad_voice(n, L, rng, midi(33), detune=(-0.05, 0.05), harm=(0.3, 1.0, 0.7, 0.3), swell=(1, 2))
    hum = norm_rms(filt(hum, 60, 600, 2, circular=True)) * presence(n, [(3.0, 10.0)] if C else [(1.0, 9.0), (15.0, 11.0)])
    air = norm_rms(filt(rng.standard_normal(n), 180, 1100, 1, circular=True))
    air *= 0.35 + 0.65 * periodic_ctrl(n, L, rng, 1, 3)
    far = np.zeros(n)
    plan = ([(8.0, 5.5, 40, 31)] if C else [(5.0, 5.0, 42, 33), (18.0, 6.0, 36, 48)])
    for at, d, f0, f1 in plan:
        add_circ(far, far_creak(rng, d, f0, f1), ns(at) % n)
    far = metal_room(far, rng)
    drip = np.zeros(n)
    if not C:
        for at in (10.5, 21.0, 25.4):
            f0 = rng.uniform(700, 1100)
            d = filt(B.plink(rng, f0, 0.12), 250, 1400, 1) * 0.7
            add_circ(drip, d, ns(at) % n)
        drip = cave_space(drip, rng, circular=True, decay=4.0, mix=1.2, lp=1600)
    x = norm_rms(drone) * 1.0 + norm_rms(hum) * 0.28 + air * 0.16 + norm_rms(far) * (0.14 if C else 0.17)
    if not C:
        x = x + norm_rms(drip) * 0.03
    return x


def transient_db(xf):
    """Maior pico de energia em janela de 50 ms acima do fundo (mediana das janelas), em dB."""
    w = ns(0.05)
    k = len(xf) // w
    r = np.sqrt((xf[: k * w].reshape(k, w) ** 2).mean(1)) + 1e-9
    return round(float(20 * np.log10(r.max() / np.median(r))), 1)


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
    k = max(3, int(100 / f[1]))
    for i in np.nonzero((f > 150) & (f < 12000))[0][::5]:
        r = 20 * np.log10(sm[i] / (np.median(X[max(0, i - k):i + k]) + 1e-12))
        if r > best[0]:
            best = (float(r), float(f[i]))
    return round(best[0], 1), round(best[1])


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    meta, xs = {}, {}
    cave = B.read_wav(B.OUT_DIR / "amb_cave.wav") if hasattr(B, "read_wav") else None
    import wave
    with wave.open(str(B.OUT_DIR / "amb_cave.wav")) as w:
        cave = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768
    cave_ld = float(loudness(cave, True))

    def put(key, x, loop, target):
        xi = write_wav(PEND / f"{key}.wav", finalize(x, loop, target))
        xf = xi.astype(float) / 32768
        m = {"file": f"pendentes/{key}.wav", "loop": loop, "duration": round(len(xi) / SR, 3),
             "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
             "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(xf ** 2)))), 1),
             "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(xi), "bands": bands(xf),
             "clip": int(np.sum(np.abs(xi) >= 32767)), "first": int(xi[0]), "last": int(xi[-1])}
        if loop:
            d = np.abs(np.diff(xi.astype(float)))
            m["seam"] = float(abs(int(xi[0]) - int(xi[-1])))
            m["seam_ref"] = round(float(np.percentile(d, 99.9)), 1)
        if loop:
            m["transient_db"] = transient_db(xf)
            m["transient_hp_db"] = transient_db(B.filt(xf, 200, None, 2, circular=True))
        m["tonal_db"], m["tonal_hz"] = tonal_peak(xf)
        meta[key] = m
        xs[key] = xf
        print(key, {k: v for k, v in m.items() if k != "wave"})

    for v, off in (("A", 1.0), ("B", 1.0)):
        put(f"amb_vesper_{v}", amb_vesper(rng_for(f"v07m4:amb_vesper_{v}"), v), True, cave_ld + off)
    for v in "CD":
        put(f"amb_vesper_{v}", amb_vesper2(rng_for(f"v07m4:amb_vesper_{v}"), v), True, cave_ld - 2.0)
    put("door_stuck_A", door_stuck(rng_for("v07m4:door_stuck_A"), "A"), False, -19.0)
    put("door_stuck_B", door_stuck(rng_for("v07m4:door_stuck_B"), "B"), False, -19.0)
    for v in "AB":
        for i, nm in enumerate((f"spark_{v}", f"spark_{v}1", f"spark_{v}2")):
            put(nm, spark(rng_for(f"v07m4:{nm}"), v, i), False, -27.0)

    # simulações: ambiente 0,3 + faíscas esparsas (0,25) + door_stuck (0,6) 2x
    T = 20.0
    for v in "AB":
        rng = np.random.default_rng(7)
        mix = np.zeros(ns(T))
        a = xs[f"amb_vesper_{v}"]
        mix += np.tile(a, 2)[: ns(T)] * 0.3
        for at in (2.0, 3.1, 7.6, 8.0, 13.5, 16.2):
            s = xs[f"spark_{v}{['', '1', '2'][int(rng.integers(0, 3))]}"] * 0.25
            mix[ns(at):ns(at) + len(s)] += s
        for at in (5.0, 11.0):
            d = xs[f"door_stuck_{v}"] * 0.6
            mix[ns(at):ns(at) + len(d)] += d
        write_wav(PEND / f"mix_{v}.wav", mix * 0.95)
    # comparação: 14 s de amb_cave seguido de 14 s do amb_vesper (como se fosse o crossfade)
    for v in "AB":
        seg = np.concatenate([cave[: ns(10)] * 0.3, xs[f"amb_vesper_{v}"][: ns(14)] * 0.3])
        write_wav(PEND / f"cmp_cave_vesper_{v}.wav", seg * 0.95)
    for v in "CD":
        seg = np.concatenate([cave[: ns(10)] * 0.3, xs[f"amb_vesper_{v}"][: ns(14)] * 0.3])
        write_wav(PEND / f"cmp_cave_vesper_{v}.wav", seg * 0.95)
    meta["_cave"] = {"loudness_db": round(cave_ld, 1), "transient_db": transient_db(cave), "transient_hp_db": transient_db(B.filt(cave, 200, None, 2, circular=True))}
    (REP / "v07m4_meta.js").write_text("// gerado por tools/audio/build_v07_m4.py, não editar\nwindow.M4_META = "
                                       + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
