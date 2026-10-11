"""Valida os WAVs do contrato de áudio (GAME_BIBLE §6).

Uso:  python3 tools/audio/check_audio.py

Checa: arquivo existe, 44,1 kHz / 16-bit / mono, pico <= -1 dBFS, sem clipping,
e nos loops mede o salto entre a última e a primeira amostra comparado com os
saltos normais entre amostras vizinhas do próprio arquivo. Também imprime uma
análise grosseira (RMS, centroide espectral, energia por banda) pra conferir
sem ouvir.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AUDIO = ROOT / "assets" / "audio"

CONTRACT = {
    "mine_hit": False, "mine_break": False, "pickup": False, "craft": False, "place": False,
    "ui_open": False, "ui_close": False, "ui_click": False, "o2_low": True, "o2_refill": False,
    "faint": False, "terminal_open": False, "stage_up": False, "footstep_0": False,
    "footstep_1": False, "machine_hum": True, "amb_dead": True, "amb_mist": True, "amb_green": True,
}
BANDS = [(20, 150), (150, 600), (600, 2500), (2500, 8000), (8000, 22050)]


def load(path: Path):
    with wave.open(str(path), "rb") as w:
        params = (w.getframerate(), w.getsampwidth() * 8, w.getnchannels())
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return params, data


def main() -> int:
    fails = []
    print(f"{'arquivo':<18}{'fmt':>14}{'dur':>7}{'pico':>8}{'rms':>8}{'centr':>7}  "
          f"{'bandas dB (<150|150-600|0.6-2.5k|2.5-8k|>8k)':<46}{'emenda'}")
    for name, loop in CONTRACT.items():
        path = AUDIO / f"{name}.wav"
        if not path.exists():
            fails.append(f"{name}: não existe")
            print(f"{name:<18} FALTANDO")
            continue
        (sr, bits, ch), d = load(path)
        if (sr, bits, ch) != (44100, 16, 1):
            fails.append(f"{name}: formato {sr}/{bits}/{ch}")
        x = d.astype(float) / 32768
        peak = 20 * np.log10(np.max(np.abs(x)) + 1e-12)
        if peak > -1.0:
            fails.append(f"{name}: pico {peak:.2f} dBFS")
        if np.any(np.abs(d.astype(int)) >= 32767):
            fails.append(f"{name}: clipping")
        rms = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)
        spec = np.abs(np.fft.rfft(x)) ** 2
        f = np.fft.rfftfreq(len(x), 1 / 44100)
        centroid = float(np.sum(f * spec) / np.sum(spec))
        tot = spec.sum()
        bands = " ".join(f"{10 * np.log10(spec[(f >= lo) & (f < hi)].sum() / tot + 1e-12):6.1f}"
                         for lo, hi in BANDS)
        seam = ""
        if loop:
            # 1) salto entre a última e a primeira amostra, comparado com todos os saltos
            #    entre amostras vizinhas do arquivo (percentil = quão "anormal" ele é)
            adj = np.abs(np.diff(x))
            jump = abs(x[0] - x[-1])
            jump_rank = 100 * np.mean(adj < jump)
            # 2) teste de clique: gira o arquivo pra emenda cair no meio, passa-alta >5 kHz e
            #    compara a energia (janela de 3 ms) na emenda com a de todas as outras posições
            r = np.roll(x, len(x) // 2)
            F = np.fft.rfftfreq(len(r), 1 / 44100)
            hp = np.fft.irfft(np.fft.rfft(r) * (F > 5000), len(r))
            e = np.convolve(hp ** 2, np.ones(132) / 132, "same")
            click_rank = 100 * np.mean(e < e[len(x) // 2])
            ok = jump_rank <= 99.0 and click_rank <= 99.0
            seam = (f"salto {jump * 32768:.0f} lsb (percentil {jump_rank:.1f}), "
                    f"agudos na emenda percentil {click_rank:.1f} -> {'OK' if ok else 'FALHOU'}")
            if not ok:
                fails.append(f"{name}: emenda suspeita ({seam})")
        print(f"{name:<18}{f'{sr}/{bits}b/{ch}ch':>14}{len(x) / sr:>7.2f}{peak:>8.2f}{rms:>8.1f}"
              f"{centroid:>7.0f}  {bands:<46}{seam}")
    print()
    if fails:
        print("FALHAS:")
        for m in fails:
            print("  -", m)
        return 1
    print(f"tudo ok: {len(CONTRACT)} arquivos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
