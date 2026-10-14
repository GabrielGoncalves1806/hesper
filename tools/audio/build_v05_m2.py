"""v0.5 Marco 2 · base respirável: gera os 6 sons PENDENTES (proposta, fora do jogo).

Uso:  python3 tools/audio/build_v05_m2.py

Saída: reports/audio/v05_m2_base/pendentes/*.wav + v05_meta.js (pro report).
NÃO escreve em assets/audio/. Quando o dono aprovar, o gerente promove (mover os wavs
e registrar as funções no SOUNDS do build_audio.py, ou copiar estes arquivos).

Reusa os blocos do build_audio.py (filt, reverb, Track, finalize...), só numpy.
Cada som tem seed própria (rng_for(nome)), então mexer num não muda os outros.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, Track, add_circ, bl_wave, bump, filt, finalize, fr, loudness,  # noqa: E402
                         midi, noise_burst, noise_sweep, ns, perc, periodic_ctrl, phase_of,
                         reverb, rng_for, tail_cut, tvec, waveform_peaks, write_wav, norm_rms)

OUT = B.ROOT / "reports" / "audio" / "v05_m2_base" / "pendentes"


def click(rng, gain=1.0, lo=500, hi=2600, dur=0.03):
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


def sfx_door_open(rng):
    """~0,40 s. Destrava (clack leve), sopro pneumático subindo de brilho (o atuador soltando
    ar) e a porta deslizando num trilho de banda larga; servo discreto subindo. Termina
    macio, sem batida (ela abre, não bate)."""
    tr = Track()
    tr.add(click(rng, 0.9), 0.0, 0.7)
    n = ns(0.3)
    tr.add(noise_sweep(rng, 0.3, 900, 2800, 2.5) * bump(n, 0.25), 0.015, 0.5)
    tr.add(slide(rng, 0.34, 110, 1000), 0.03, 0.5)
    tr.add(servo(0.3, 210, 330), 0.03, 0.10)
    return tail_cut(filt(reverb(tr.render(), rng, decay=0.3, mix=0.08, lp=4000), None, 5200, 2), 0.44, 0.06)


def sfx_door_close(rng):
    """~0,42 s. Irmã de trás pra frente: desliza (servo descendo), e no fim a trava encaixa
    (clack de banda larga um pouco mais grave) com um 'tss' curto de selo. Mais seco no fim
    que o open, pra dar pra distinguir os dois só de ouvir."""
    tr = Track()
    tr.add(slide(rng, 0.30, 110, 1000), 0.0, 0.5)
    n = ns(0.24)
    tr.add(noise_sweep(rng, 0.24, 2600, 900, 2.5) * bump(n, 0.4), 0.0, 0.35)
    tr.add(servo(0.28, 330, 200), 0.0, 0.10)
    tr.add(click(rng, 1.0, 380, 2200, 0.035), 0.30, 0.95)
    m = ns(0.09)
    tr.add(filt(rng.standard_normal(m), 1800, 6500, 1) * bump(m, 0.08) ** 2, 0.315, 0.16)
    return tail_cut(filt(reverb(tr.render(), rng, decay=0.3, mix=0.08, lp=4000), None, 5200, 2), 0.46, 0.06)


def sfx_base_sealed(rng):
    """~2,3 s. 'Pressurizou'. Selo pneumático (clack + 'tchss'), um sopro de ar que ENCHE e
    sobe (banda larga 300 Hz -> 4 kHz, crescendo) e um acorde de Lá maior sus2 -> maior (Lá3,
    Mi4, Lá4, Dó#5) que abre por baixo do sopro e assenta, com um sininho suave de seno em
    Lá5+Mi5 no fim ('ok, estável'). Sem seno grave com pitch (nada de tambor)."""
    tr = Track()
    tr.add(click(rng, 1.0, 400, 2400, 0.04), 0.0, 0.8)
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
    tr.add(click(rng, 0.9), 0.0, 0.5)
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
    tr.add(click(rng, 1.0, 380, 2200, 0.035), 0.48, 1.0)
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
    tr.add(click(rng, 0.7, 600, 3000, 0.02), 0, 0.4)
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
    tr.add(click(rng, 0.8, 350, 2000, 0.035), 1.12, 0.7)
    m = ns(0.25)
    tr.add(filt(rng.standard_normal(m), 400, 2500, 1) * bump(m, 0.1) ** 2, 1.1, 0.1)
    return tail_cut(reverb(tr.render(), rng, decay=0.5, mix=0.14, lp=3500), 1.6, 0.2)


# nome: (função, loop?, alvo de loudness dB)
SOUNDS_M2 = {
    "door_open": (sfx_door_open_B, False, -25.0, "v05m2:door_open_B"),
    "door_close": (sfx_door_close_B, False, -25.0, "v05m2:door_close_B"),
    "anterior_A/door_open_A": (sfx_door_open, False, -24.0, "v05m2:door_open"),
    "anterior_A/door_close_A": (sfx_door_close, False, -24.0, "v05m2:door_close"),
    "base_sealed": (sfx_base_sealed, False, -19.0),
    "dispenser_hum": (loop_dispenser_hum, True, -34.0),
    "leak_alert": (sfx_leak_alert, False, -21.0),
    "dispenser_dry": (sfx_dispenser_dry, False, -23.0),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, (fn, loop, target, *sd) in SOUNDS_M2.items():
        (OUT / name).parent.mkdir(parents=True, exist_ok=True)
        x = finalize(fn(rng_for(sd[0] if sd else "v05m2:" + name)), loop, target)
        xi = write_wav(OUT / f"{name}.wav", x)
        xf = xi.astype(float) / 32768
        meta[name] = {
            "file": f"pendentes/{name}.wav", "loop": loop, "duration": round(len(xi) / SR, 3),
            "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
            "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(xi),
        }
        if loop:
            adj = np.abs(np.diff(xi.astype(int)))
            jump = abs(int(xi[0]) - int(xi[-1]))
            meta[name]["seam_lsb"] = jump
            meta[name]["seam_pct"] = round(float(100 * np.mean(adj < jump)), 1)
        print(f"{name + '.wav':<30}{len(xi) / SR:>7.3f} s  pico {meta[name]['peak_db']:>6} dBFS  "
              f"loud {meta[name]['loudness_db']:>6}")
    # vizinhos oficiais, só pra comparar (lidos de assets/audio, nada é copiado nem escrito lá)
    import wave
    for nb in ("o2_low", "power_low", "machine_hum", "o2_refill", "pickup", "place", "build"):
        p = B.OUT_DIR / f"{nb}.wav"
        with wave.open(str(p), "rb") as w:
            d = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        xf = d.astype(float) / 32768
        loop = nb in ("o2_low", "machine_hum")
        meta["nb:" + nb] = {
            "file": f"../../../assets/audio/{nb}.wav", "loop": loop, "duration": round(len(d) / SR, 3),
            "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
            "loudness_db": round(float(loudness(xf, loop)), 1), "wave": waveform_peaks(d),
        }
    (OUT.parent / "v05_meta.js").write_text(
        "// gerado por tools/audio/build_v05_m2.py, não editar\nwindow.V05_META = "
        + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("ok:", OUT.relative_to(B.ROOT))


if __name__ == "__main__":
    main()
