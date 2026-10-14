#!/usr/bin/env python3
"""v0.5 · Marco 1 · construtor, mochila e a luz de scanner. PROPOSTA: nada daqui vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_m1_construtor.py

Saída: reports/design/v05_m1_construtor/pendentes/
    icon_constructor.png   16×16  o construtor (ferramenta de mão com emissor/lente ciano)
    icon_backpack.png      16×16  a mochila (equipamento do traje, família do tanque de O₂ e do scanner)
E a simulação da luz de scanner (efeito procedural que o Dev faz no código) em reports/design/v05_m1_construtor/sim/.
`scan_frame()` abaixo é a referência do efeito: o Dev reproduz o mesmo algoritmo em pygame (está no report).
Depois chama o v05_m1_construtor_report.py (prévias e index.html).
Determinístico: o único aleatório (faíscas) usa um hash fixo do passo, sem estado.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import machines_r3d as M  # noqa: E402

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v05_m1_construtor"
PEND = REP / "pendentes"
SIM = REP / "sim"

OUTLINE = M.OUTLINE

# ---------------------------------------------------------------------------------------------------------------------
# Ícones 16×16 (desenhados à mão, mapa de caracteres + contorno #1b1630, igual aos icon_* do jogo)
# ---------------------------------------------------------------------------------------------------------------------
# paleta dos ícones de equipamento aprovados (icon_o2_tank / icon_scanner): branco frio, cinzas, laranja, ciano
EQ = {
    "W": "#ffffff", "w": "#f4f6f8", "l": "#e1e5ea", "m": "#c8cdd4", "s": "#abb2bb", "d": "#8c949e", "g": "#6b717a",
    "k": "#3b3f46", "K": "#2a2d33", "o": "#e2733a", "h": "#f29a62", "r": "#a8471f",
    "c": "#59d0e6", "C": "#2b9fb8", "L": "#c8f6ff", "n": "#1f5a66", "G": "#7fd67a",
}


def _icon(rows):
    rows = [r.ljust(16, ".") for r in rows]
    assert len(rows) == 16
    cv = M.Canvas(16, 16)
    cv.draw_map(rows, EQ)
    cv.outline()
    return cv


def icon_constructor():
    """Construtor: pistola de construção de perfil, apontando pra direita. Corpo branco com a faixa laranja, um
    visorzinho escuro em cima (o "scanner"), cabo laranja inclinado com o gatilho, e na frente a CABEÇA EMISSORA:
    um anel cinza-escuro alto com a lente ciano grande (brilho branco em cima, ciano escuro embaixo) e um leque de
    luz curto saindo dela. Lê como "projetor de luz", não como broca: nada de ponta, cone ou rosca."""
    return _icon([
        "................",
        "................",
        "...........ggg..",
        "...kKKk...gmLWg.",
        ".llwwwwwwkgLccg.",
        ".wWwwwwwwkgcccg.",
        ".hooooooohgccCg.",
        ".wllllllmkgcCCg.",
        ".lmmmmmmmkgmCng.",
        "..ssskssss.ggg..",
        "...ohr.k........",
        "...ohr.k........",
        "..ohr...........",
        "..ohr...........",
        "..rrr...........",
        "................",
    ])


def icon_backpack():
    """Mochila: vista de costas, gordinha e arredondada. Alça de mão escura em cima, aba branca com a faixa laranja
    e a fivela, LED ciano na aba (o mesmo ciano do tanque de O₂), corpo branco sombreado pra direita, bolso da frente
    cinza com o zíper laranja, e as alças de ombro escuras aparecendo dos dois lados."""
    return _icon([
        "................",
        "......kkkk......",
        ".....kk..kk.....",
        ".....lwwwwl.....",
        "....wWwwwwwlm...",
        "...wwwwcCwwwlm..",
        "..kwwwwwwwwwlmk.",
        "..koowwwwwwwork.",
        "..kmmooohhoorsk.",
        "..kwwmmmkkmmlmk.",
        "..kwwdmmmmmmdmk.",
        "..kwlohoooooosk.",
        "..kwlmmmmmmmssk.",
        "..kwldssssssdmk.",
        "...ldddddddddm..",
        "................",
    ])


# ---------------------------------------------------------------------------------------------------------------------
# Luz de scanner (construir e desmontar). Referência do efeito que o Dev implementa no jogo.
# ---------------------------------------------------------------------------------------------------------------------
# Cores na família do laser da drill (machines_r3d.LASER_CYAN = branco, ciano claro, ciano, ciano escuro)
SCAN_CORE = "#ffffff"        # linha central da faixa (1 px), só sobre a silhueta
SCAN_EDGE = "#c8f6ff"        # 1 px de cada lado do núcleo, sobre a silhueta
SCAN_PULSE = "#59d0e6"       # +1 px de cada lado nos passos ímpares (pulsa 3 px ↔ 5 px, igual ao feixe da drill)
SCAN_PLANE = "#59d0e6"       # o núcleo continua 2 px pra fora da silhueta dos dois lados ("plano" do scanner)
SCAN_NODE = "#ffffff"        # 1 px na ponta do plano (o emissor)
GHOST = "#2b8fb3"            # holograma: o contorno #1b1630 da parte ainda não construída, em ciano escuro
FRESH_ADD = (24, 56, 64)     # linhas recém-reveladas: soma RGB (pygame BLEND_RGB_ADD) nas 2 linhas logo abaixo da faixa
FRESH_ROWS = 2
PLANE_OUT = 2                # px do plano pra fora do bbox da silhueta
SPARKS = 2                   # faíscas por passo, 1 px, vivem 1 passo
SPARK_COLS = ("#ffffff", "#c8f6ff")
SPARK_UP = (2, 5)            # sobem de 2 a 5 px acima do núcleo
FPS = 12                     # passos por segundo (posição da faixa quantizada por passo)
BUILD_S, UNBUILD_S = 1.5, 2.0
BUILD_STEPS = round(BUILD_S * FPS)     # 18
UNBUILD_STEPS = round(UNBUILD_S * FPS)  # 24
FLASH_STEPS = 1              # ao terminar de construir: 1 passo com a máquina inteira no FRESH_ADD
BLINK_STEPS = 2              # ao terminar de desmontar: holograma apagado 1 passo, aceso 1 passo, e some


def _hex(c):
    return np.array(M.rgb(c), np.uint8)


def _hash(*k):
    h = 2166136261
    for v in k:
        h = ((h ^ (v & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h


def bbox(spr):
    a = spr[:, :, 3] > 0
    ys, xs = np.nonzero(a)
    return xs.min(), ys.min(), xs.max(), ys.max()


def band_row(spr, p):
    """Linha do núcleo para o progresso p ∈ [0, 1] de CONSTRUÇÃO (0 = nada, 1 = tudo).
    Construir: p = t / 1,5 s (sobe). Desmontar: p = 1 − t / 2 s (desce). Mesma fórmula nos dois."""
    _, y0, _, y1 = bbox(spr)
    return int(round(y1 + 1 - p * (y1 - y0 + 2)))


def scan_frame(spr, p, step, pad=6):
    """Um quadro do efeito. `spr` = RGBA (h, w, 4) do sprite parado. Devolve RGBA com `pad` px de folga em cima e
    dos lados (pras faíscas e o plano); o pé fica no mesmo lugar (sem folga embaixo).

    Regras (iguais construindo e desmontando; só muda o sentido de p):
      · linhas abaixo da faixa (y > ys): o sprite normal; as FRESH_ROWS primeiras com FRESH_ADD somado;
      · linhas acima (y < ys): só o holograma, o contorno #1b1630 do sprite pintado de GHOST;
      · faixa: núcleo em ys, borda em ys±1, pulso em ys±2 nos passos ímpares, tudo só sobre a silhueta;
        o núcleo passa PLANE_OUT px pra fora da silhueta (SCAN_PLANE) com SCAN_NODE na ponta;
      · SPARKS faíscas de 1 px acima do núcleo, só em pixel vazio.
    """
    h, w = spr.shape[:2]
    x0, _, x1, _ = bbox(spr)
    ys = band_row(spr, p)
    out = np.zeros((h + pad, w + 2 * pad, 4), np.uint8)
    sil = spr[:, :, 3] > 0
    is_ol = sil & np.all(spr[:, :, :3] == _hex(OUTLINE)[:3], axis=2)
    rows = np.arange(h)[:, None]
    # parte construída
    built = sil & (rows > ys)
    reg = out[pad:, pad:pad + w]
    reg[built] = spr[built]
    fresh = built & (rows <= ys + FRESH_ROWS)
    add = np.array(FRESH_ADD, np.int16)
    reg[fresh, :3] = np.clip(spr[fresh, :3].astype(np.int16) + add, 0, 255).astype(np.uint8)
    # holograma
    ghost = is_ol & (rows < ys)
    reg[ghost] = _hex(GHOST)
    # faixa
    if True:  # a faixa
        half = 2 if step % 2 else 1
        for k in range(-half, half + 1):
            y = ys + k
            if not 0 <= y < h:
                continue
            c = SCAN_CORE if k == 0 else SCAN_EDGE if abs(k) == 1 else SCAN_PULSE
            m = sil[y]
            reg[y, m] = _hex(c)
        if 0 <= ys < h and sil[ys].any():
            xs = np.nonzero(sil[ys])[0]
            a, b = xs.min(), xs.max()
            y = ys + pad
            for x in list(range(a - PLANE_OUT, a)) + list(range(b + 1, b + 1 + PLANE_OUT)):
                out[y, x + pad] = _hex(SCAN_PLANE)
            out[y, a - PLANE_OUT - 1 + pad] = _hex(SCAN_NODE)
            out[y, b + PLANE_OUT + 1 + pad] = _hex(SCAN_NODE)
        # faíscas
        if 0 <= ys < h + 1 and 0 < p < 1:
            for i in range(SPARKS):
                hh = _hash(step, i, 77)
                x = x0 + hh % (x1 - x0 + 1)
                y = ys - SPARK_UP[0] - (hh >> 8) % (SPARK_UP[1] - SPARK_UP[0] + 1)
                if 0 <= y + pad < out.shape[0] and out[y + pad, x + pad, 3] == 0:
                    out[y + pad, x + pad] = _hex(SPARK_COLS[(step + i) % 2])
    return out


def flash_frame(spr, pad=6):
    h, w = spr.shape[:2]
    out = np.zeros((h + pad, w + 2 * pad, 4), np.uint8)
    reg = out[pad:, pad:pad + w]
    sil = spr[:, :, 3] > 0
    reg[sil] = spr[sil]
    reg[sil, :3] = np.clip(spr[sil, :3].astype(np.int16) + np.array(FRESH_ADD, np.int16), 0, 255).astype(np.uint8)
    return out


def still_frame(spr, pad=6):
    h, w = spr.shape[:2]
    out = np.zeros((h + pad, w + 2 * pad, 4), np.uint8)
    out[pad:, pad:pad + w] = spr
    return out


def build_seq(spr):
    """Construir: passo 0..BUILD_STEPS (p = passo/BUILD_STEPS), +FLASH_STEPS de flash, e o parado."""
    fr = [scan_frame(spr, s / BUILD_STEPS, s) for s in range(BUILD_STEPS + 1)]
    fr += [flash_frame(spr)] * FLASH_STEPS
    return fr


def unbuild_seq(spr):
    """Desmontar: passo 0..UNBUILD_STEPS (p = 1 − passo/UNBUILD_STEPS); no fim o holograma pisca (apagado, aceso) e
    some. Se o player soltar antes, volta direto pro parado (sem animação de volta)."""
    fr = [scan_frame(spr, 1 - s / UNBUILD_STEPS, s) for s in range(UNBUILD_STEPS + 1)]
    empty = np.zeros_like(fr[0])
    return fr + [empty, ghost_frame(spr), empty]


def ghost_frame(spr, pad=6):
    """Só o holograma (o contorno em GHOST), sem faixa. É o que o desmonte deixa no último passo."""
    h, w = spr.shape[:2]
    out = np.zeros((h + pad, w + 2 * pad, 4), np.uint8)
    sil = spr[:, :, 3] > 0
    is_ol = sil & np.all(spr[:, :, :3] == _hex(OUTLINE)[:3], axis=2)
    out[pad:, pad:pad + w][is_ol] = _hex(GHOST)
    return out


MACHINES = [
    ("machine_o2", ROOT / "assets" / "sprites" / "machine_o2.png", "Gerador de O₂"),
    ("chest", ROOT / "assets" / "sprites" / "chest.png", "Baú"),
    ("machine_workbench", ROOT / "reports" / "design" / "v05_bancada_itens" / "pendentes" / "machine_workbench.png",
     "Bancada T2 (pendente)"),
    ("machine_heater_t2", ROOT / "assets" / "sprites" / "machine_heater_t2.png", "Aquecedor nv.2"),
]


def load(p):
    return np.array(Image.open(p).convert("RGBA"))


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {"icon_constructor.png": icon_constructor(), "icon_backpack.png": icon_backpack()}
    for name, cv in out.items():
        cv.save(PEND / name)
    return out


if __name__ == "__main__":
    o = build()
    for k, cv in o.items():
        print(f"{k}: {cv.w}×{cv.h}")
    import v05_m1_construtor_report as REP_
    print(REP_.build())
