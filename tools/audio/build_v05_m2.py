"""v0.5 Marco 2 · base respirável: gera os 6 sons PENDENTES (proposta, fora do jogo).

Uso:  python3 tools/audio/build_v05_m2.py

Saída: reports/audio/v05_m2_base/pendentes/*.wav + v05_meta.js (pro report).
NÃO escreve em assets/audio/. PROMOVIDO (v13.1): as funções agora vivem no build_audio.py (SOUNDS) e este script só
as importa pra refazer o report; a porta A (anterior) continua só aqui.

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
# Promovidos (v13.1, aprovados): vivem no build_audio.py. Aqui ficam só a porta A (anterior) e o gerador do report.
from build_audio import (click_m2 as click, slide, servo, sfx_base_sealed, sfx_door_open_B,  # noqa: E402
                         sfx_door_close_B, loop_dispenser_hum, sfx_leak_alert, sfx_dispenser_dry)

OUT = B.ROOT / "reports" / "audio" / "v05_m2_base" / "pendentes"


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
