"""v0.5 Marco 4 · contêiner lacrado abrindo: 3 candidatas (A1, B1, C1), fora do jogo.

Uso:  python3 tools/audio/build_v05_m4.py

Saída: assets/audio/candidates/container_open_{A1,B1,C1}.wav (+ reports/audio/v05_m4_conteiner/v05_meta.js).
NÃO escreve assets/audio/container_open.wav (o dono escolhe antes). Só numpy; blocos do build_audio.py.

Família do chest_open/crate_open: trava de ruído de banda larga, rangido de dobradiça por pulsos
irregulares, tampa que assenta com ruído grave. Sem seno grave com pitch (nada de tambor), sem filtro
estreito (nada de latinha). O que é novo: selo que parte (estalo duplo com "rasgo"), despressurização
longa, tampa muito mais pesada e uma recompensa mínima (um brilho de Lá bem baixo, estilo base_sealed).
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_audio as B  # noqa: E402
from build_audio import (SR, Track, bump, filt, finalize, hinge_creak, loudness, midi, noise_burst,  # noqa: E402
                         noise_sweep, ns, phase_of, reverb, rng_for, shhh, soft_sat, tail_cut, tvec,
                         waveform_peaks, write_wav)

CAND = B.OUT_DIR / "candidates"
REP = B.ROOT / "reports" / "audio" / "v05_m4_conteiner"


def seal_break(rng, tr: Track, at: float, heavy: float = 1.0):
    """Selo partindo: estalo seco agudo + 'rasgo' de banda larga + peso grave curto."""
    tr.add(noise_burst(rng, 2500, 8000, 0.0002, 0.0008, 0.008, order=1), at, 0.45)
    tr.add(noise_burst(rng, 600, 4000, 0.0003, 0.005, 0.04, order=1), at, 0.85)
    tr.add(noise_burst(rng, 120, 700, 0.0008, 0.012, 0.07, order=2), at + 0.001, 0.55 * heavy)
    # rasgo: grãos irregulares (lacre de resina cedendo)
    t = at + 0.012
    for _ in range(9):
        t += rng.exponential(0.007)
        tr.add(noise_burst(rng, 800, 6000, 0.0002, 0.002, 0.012, order=1), t, rng.uniform(0.15, 0.4))


def glint(tr: Track, at: float, notes, gain: float, decay: float = 0.4):
    """Brilho de recompensa: senos agudos de Lá (sem grave), bem baixo na mistura."""
    for i, (mn, g) in enumerate(notes):
        q = ns(1.2)
        tt = tvec(q)
        x = (np.sin(phase_of(midi(mn), q)) + 0.12 * np.sin(phase_of(midi(mn) * 2, q))) * np.exp(-tt / decay)
        tr.add(x * np.minimum(1, tt / 0.006), at + 0.07 * i, gain * g)


def lid_thud(rng, tr: Track, at: float, w: float = 1.0):
    """Tampa pesada assentando: ruído largo e escuro, sem seno, + batida de metal larga e quique."""
    tr.add(noise_burst(rng, 300, 3500, 0.0004, 0.009, 0.06, order=1), at, 0.8 * w)
    tr.add(noise_burst(rng, None, 260, 0.002, 0.03, 0.16, order=2), at, 0.9 * w)
    tr.add(noise_burst(rng, 60, 450, 0.002, 0.045, 0.2, order=1), at + 0.004, 0.55 * w)
    tr.add(noise_burst(rng, 2500, 7000, 0.0002, 0.0008, 0.006, order=1), at, 0.2 * w)
    tr.add(noise_burst(rng, 400, 3000, 0.0003, 0.005, 0.04, order=1), at + 0.05, 0.28 * w)   # quique


def hiss(rng, tr: Track, at: float, dur: float, gain: float):
    """Despressurização: ar escapando, ataca forte e vai morrendo; brilho desce com o tempo."""
    tr.add(shhh(rng, dur, False, 0.025, dur * 0.33), at, gain)
    n = ns(dur)
    tr.add(filt(rng.standard_normal(n), 250, 1400, 1) * bump(n, 0.08) ** 1.5, at, gain * 0.22)


def cand_A1(rng):
    """~1,5 s. Estalo do selo, chiado que cai, rangido de dobradiça subindo e baque de tampa
    pesada, com um brilho de Lá (Lá5+Mi6) bem discreto depois. Equilibrada."""
    tr = Track()
    seal_break(rng, tr, 0.0)
    hiss(rng, tr, 0.03, 0.85, 0.5)
    tr.add(hinge_creak(rng, 0.5, 130, 260), 0.22, 0.5)
    n = ns(0.5)
    tr.add(filt(rng.standard_normal(n), 300, 2500, 1) * bump(n, 0.4), 0.22, 0.05)
    lid_thud(rng, tr, 0.74)
    glint(tr, 0.86, ((81, 1.0), (88, 0.6)), 0.05)
    return tail_cut(filt(reverb(soft_sat(tr.render(), 1.6), rng, decay=0.9, mix=0.2, lp=3800), None, 7000, 1), 1.55, 0.35)


def cand_B1(rng):
    """~1,6 s. Mais seca e mais mecânica, sem tom nenhum: duas travas partindo (ferrolho
    duplo), chiado mais curto e grave, rangido lento e tampa pesadíssima com quique. Sem brilho."""
    tr = Track()
    seal_break(rng, tr, 0.0, 1.2)
    seal_break(rng, tr, 0.11, 0.9)
    hiss(rng, tr, 0.05, 0.7, 0.4)
    tr.add(hinge_creak(rng, 0.65, 110, 230, 0.15), 0.25, 0.55)
    n = ns(0.65)
    tr.add(filt(rng.standard_normal(n), 250, 2000, 1) * bump(n, 0.45), 0.25, 0.06)
    lid_thud(rng, tr, 0.93, 1.25)
    tr.add(noise_burst(rng, 300, 2500, 0.0003, 0.006, 0.04, order=1), 1.06, 0.2)          # encosta
    return tail_cut(filt(reverb(soft_sat(tr.render(), 1.6), rng, decay=1.1, mix=0.22, lp=3500), None, 6500, 1), 1.75, 0.4)


def cand_C1(rng):
    """~1,8 s. Mais 'especial': selo, chiado longo e ar entrando, tampa subindo devagar com
    rangido longo, baque, e uma nuvem quente de Lá sus2 (Lá3, Mi4, Si4) que abre devagar,
    como o base_sealed mas bem mais discreta. É a mais premiadora das três."""
    tr = Track()
    seal_break(rng, tr, 0.0)
    hiss(rng, tr, 0.03, 1.0, 0.5)
    tr.add(hinge_creak(rng, 0.6, 120, 240), 0.2, 0.5)
    n = ns(0.6)
    tr.add(filt(rng.standard_normal(n), 300, 2500, 1) * bump(n, 0.4), 0.2, 0.05)
    lid_thud(rng, tr, 0.82)
    for mn, d, g in ((57, 0.88, 0.07), (64, 0.95, 0.06), (71, 1.02, 0.045)):
        q = ns(1.2)
        tt = tvec(q)
        x = np.sin(phase_of(midi(mn), q)) + 0.2 * np.sin(phase_of(midi(mn) * 2, q))
        env = np.minimum(1, tt / 0.3) * np.exp(-np.maximum(0, tt - 0.25) / 0.45)
        tr.add(x * env, d, g)
    glint(tr, 1.05, ((81, 1.0), (88, 0.6)), 0.04, 0.3)
    return tail_cut(filt(reverb(soft_sat(tr.render(), 1.5), rng, decay=1.3, mix=0.25, lp=3800), None, 7000, 1), 1.85, 0.45)



# ---------------------------------------------------------------------------
# v14.1: gravações reais CC0 (as sintéticas A1/B1/C1 foram reprovadas: "prato de bateria abafado").
# Base = click natural de trava gravado; por baixo só ruído ESCURO (sem brilho agudo, sem tom).
# ---------------------------------------------------------------------------
VENDOR = Path(__file__).resolve().parent / "vendor"


def rec(rel: str, trim: float | None = None, hp: float | None = 60, lp: float | None = None, fade: float = 0.03):
    """Decodifica um arquivo gravado do vendor (ffmpeg -> mono 44,1 kHz), recorta, filtra."""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VENDOR / rel), "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, "<i2").astype(float) / 32768
    if trim:
        x = x[: ns(trim)].copy()
    if hp or lp:
        x = filt(x, hp, lp, 2)
    f = min(ns(fade), len(x))
    x[-f:] *= np.linspace(1, 0, f) ** 2
    return x


def dark_hiss(rng, dur: float, lo=350, hi=3000):
    """Despressurização escura: ruído de banda larga até 3 kHz (sem agudo, sem 'tss' de prato)."""
    n = ns(dur)
    x = filt(rng.standard_normal(n), lo, hi, 1) + 0.5 * filt(rng.standard_normal(n), 150, 900, 1)
    return x * bump(n, 0.12) ** 1.4


def cand_D1(rng):
    """~1,3 s. lock_open_01 (rubberduck, CC0): trava se soltando em vários cliques e o
    'clunk' final. Embaixo: ar escuro saindo e a tampa pesada (ruído grave de síntese, sem tom)."""
    tr = Track()
    tr.add(rec("oga_metal_wood/Audio/lock_open_01.ogg", 0.74, hp=70, lp=6500), 0, 1.0)
    tr.add(dark_hiss(rng, 0.8), 0.46, 0.09)
    tr.add(rec("oga_metal_wood/Audio/door_open_01.ogg", 0.43, hp=100, lp=2800), 0.58, 0.22)
    lid_thud(rng, tr, 0.72, 0.45)
    return tail_cut(reverb(tr.render(), rng, decay=0.35, mix=0.06, lp=3000), 1.45, 0.25)


def cand_D2(rng):
    """~1,1 s. Fecho de case: duas travas gravadas (lock_02 e depois lock_01, rubberduck RPG
    SFX, CC0) soltando em sequência, ar escuro e a tampa subindo com rangido grave e baque."""
    tr = Track()
    tr.add(rec("oga_rpg80/Audio/lock_02.ogg", 0.40, hp=70, lp=6500), 0.0, 1.0)
    tr.add(rec("oga_rpg80/Audio/lock_01.ogg", 0.41, hp=70, lp=6500), 0.17, 0.8)
    tr.add(dark_hiss(rng, 0.8), 0.14, 0.1)
    tr.add(hinge_creak(rng, 0.38, 110, 210), 0.36, 0.28)
    lid_thud(rng, tr, 0.72, 0.5)
    return tail_cut(reverb(tr.render(), rng, decay=0.35, mix=0.06, lp=3000), 1.2, 0.2)


def cand_D3(rng):
    """~0,8 s. A mais seca: só o click natural (lock_03: dois cliques e o encaixe, rubberduck
    RPG SFX, CC0), um sopro escuro curtinho e o peso da tampa. Sem rangido."""
    tr = Track()
    tr.add(rec("oga_rpg80/Audio/lock_03.ogg", 0.34, hp=70, lp=6500), 0.0, 1.0)
    tr.add(dark_hiss(rng, 0.45), 0.2, 0.07)
    lid_thud(rng, tr, 0.34, 0.5)
    return tail_cut(reverb(tr.render(), rng, decay=0.3, mix=0.05, lp=3000), 0.85, 0.15)


def cand_D1s(rng):
    """~0,74 s. D1 sem nada por baixo: só o lock_open_01 gravado (cliques e o clunk final),
    sem ar, sem rangido (o door_open_01 é ruído e soaria como chiado), sem reverb."""
    return rec("oga_metal_wood/Audio/lock_open_01.ogg", 0.74, hp=70, lp=6500, fade=0.05)


def cand_D3s(rng):
    """~0,34 s. D3 sem nada por baixo: só o lock_03 gravado, limpo, sem reverb."""
    return rec("oga_rpg80/Audio/lock_03.ogg", 0.34, hp=70, lp=6500, fade=0.04)


CANDS_OLD = {"container_open_A1": (cand_A1, -18.0), "container_open_B1": (cand_B1, -18.0),
         "container_open_C1": (cand_C1, -18.0)}
CANDS = dict(CANDS_OLD)
CANDS.update({"container_open_D1": (cand_D1, -19.0), "container_open_D2": (cand_D2, -19.0),
              "container_open_D3": (cand_D3, -19.0),
              "container_open_D1s": (cand_D1s, -19.0), "container_open_D3s": (cand_D3s, -19.0)})


def band_report(x):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    p = np.abs(np.fft.rfft(x)) ** 2
    edges = [(20, 150), (150, 600), (600, 2500), (2500, 6000), (6000, 16000)]
    tot = p.sum()
    return [round(float(100 * p[(f >= a) & (f < b)].sum() / tot), 1) for a, b in edges]


def main():
    CAND.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    meta = {}

    def info(file, xi, key):
        xf = xi.astype(float) / 32768
        meta[key] = {"file": file, "loop": False, "duration": round(len(xi) / SR, 3),
                     "peak_db": round(float(20 * np.log10(np.max(np.abs(xf)) + 1e-12)), 2),
                     "loudness_db": round(float(loudness(xf, False)), 1), "wave": waveform_peaks(xi),
                     "bands": band_report(xf)}
        m = meta[key]
        print(f"{key:<24}{m['duration']:>6.2f} s  pico {m['peak_db']:>6}  loud {m['loudness_db']:>6}  bandas% {m['bands']}")

    for name, (fn, target) in CANDS.items():
        xi = write_wav(CAND / f"{name}.wav", finalize(fn(rng_for("v05m4:" + name)), False, target))
        info(f"../../../assets/audio/candidates/{name}.wav", xi, name)
    for nb in ("chest_open", "crate_open", "base_sealed", "pickup"):
        with wave.open(str(B.OUT_DIR / f"{nb}.wav"), "rb") as w:
            d = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        info(f"../../../assets/audio/{nb}.wav", d, "nb:" + nb)
    (REP / "v05_meta.js").write_text("// gerado por tools/audio/build_v05_m4.py, não editar\nwindow.V05_META = "
                                     + json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")


if __name__ == "__main__":
    main()
