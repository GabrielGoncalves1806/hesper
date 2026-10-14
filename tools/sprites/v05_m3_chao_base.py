#!/usr/bin/env python3
"""v0.5 M3 · Chão da base refeito: um chão só, sutil (pedido do dono, referência em
reports/design/v05_m3_chao_base/ref/referencia_chao.png).
PROPOSTA: nada daqui vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_m3_chao_base.py            (gera os pendentes e o report)
    python3 tools/sprites/v05_m3_chao_base.py --no-report

Ideia: uma chapa de metal por tile, cinza-azulado puxando pro verde (a referência), em 4 tons bem próximos.
A junta é fina e rebaixada (sombra embaixo/direita da chapa de cima, linha de junta, fio de luz na borda de cima/
esquerda da chapa seguinte) e cada cruzamento de juntas ganha um pino em losango (cada tile desenha 1/4 dele em cada
canto; 4 tiles montam o losango inteiro). Sem rebite, sem grelha, sem tampa: o que muda entre as 4 variações são só
3–4 pintinhas de 1 tom (desgaste), pra repetição não marcar padrão.

Contrato: os mesmos nomes e tamanhos do v0.5 M2 (bíblia §6):
    base_floor_{0..3}.png   32×32   em (tx·32, ty·32), passada do chão, embaixo de tudo; sorteio por hash do tile
    icon_base_floor.png     16×16   ícone do bloco no menu do construtor (a chapa nova)
Saída: reports/design/v05_m3_chao_base/pendentes/
Determinístico: sem aleatório (as pintinhas saem de uma tabela fixa).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import machines_r3d as M  # noqa: E402

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v05_m3_chao_base"
PEND = REP / "pendentes"
T = 32

# chão: aço cinza-azulado com um pé no verde (hue ~205°, saturação ~19%, valor ~47%). Degraus pequenos de propósito: a junta e o
# pino ficam a 1–2 tons da chapa (o azul faz a ponte com o ardósia-lilás do topo da parede), pro chão ficar de fundo e as máquinas (brancas, contorno escuro) lerem por cima.
FL2 = dict(
    seam="#505c65",     # linha da junta
    shade="#5a6770",    # borda de baixo/direita da chapa (o rebaixo da junta)
    base="#616e78",     # chapa
    wear="#65737c",     # desgaste (pintinha clara, quase invisível)
    pit="#5d6a73",      # desgaste (pintinha escura)
    light="#677580",    # fio de luz na borda de cima/esquerda da chapa
    stud="#72808a",     # pino em losango no cruzamento
    stud_d="#4c5861",   # pé do pino (a ponta de baixo do losango)
)

# pintinhas de desgaste por variação: (x, y, tom). Poucas e espalhadas, longe das bordas.
WEAR = {
    0: [(9, 12, "wear"), (21, 22, "pit"), (24, 8, "wear")],
    1: [(13, 7, "pit"), (7, 22, "wear"), (25, 18, "wear")],
    2: [(18, 11, "wear"), (10, 25, "pit"), (26, 26, "wear"), (5, 15, "pit")],
    3: [(22, 14, "pit"), (12, 18, "wear"), (6, 6, "wear")],
}


def rgb(c):
    return M.rgb(c)


def floor_tile(v=0, pal=FL2):
    """Chapa 32×32. Junta em cima/esquerda (linha 0 / coluna 0), rebaixo na borda de baixo/direita."""
    a = np.zeros((T, T, 4), np.uint8)

    def put(x, y, c):
        a[y, x] = rgb(pal[c])

    for y in range(T):
        for x in range(T):
            c = "base"
            if x == 0 or y == 0:
                c = "seam"
            elif y == T - 1 or x == T - 1:
                c = "shade"
            elif y == 1 or x == 1:
                c = "light"
            put(x, y, c)
    # pino em losango no cruzamento: cada canto do tile tem 1/4 dele (3 px); 4 tiles montam um losango 4×4
    for (cx, cy, sx, sy) in ((0, 0, 1, 1), (T - 1, 0, -1, 1), (0, T - 1, 1, -1), (T - 1, T - 1, -1, -1)):
        put(cx, cy, "stud")
        put(cx + sx, cy, "stud")
        put(cx, cy + sy, "stud_d" if sy > 0 else "stud")   # a ponta de baixo do losango (canto de cima do tile) é o pé escuro
    for (x, y, c) in WEAR[v]:
        put(x, y, c)
    return a


def icon_base_floor():
    """Ícone 16×16: 4 chapas novas com a junta em cruz e o pino em losango no meio, a espessura embaixo e o contorno."""
    rows = [
        "................",
        "................",
        "................",
        "..LLLLLsLLLLLL..",
        "..LBBBBsLBBBBd..",
        "..LBBBBsLBBBBd..",
        "..LBBBBSLBBBBd..",
        "..ssssSSSsssss..",
        "..LLLLLDLLLLLd..",
        "..LBBBBsLBBBBd..",
        "..LBBBBsLBBBBd..",
        "..dddddsdddddd..",
        "..kkkkkkkkkkkk..",
        "................",
        "................",
        "................",
    ]
    pal = {"S": FL2["stud"], "D": FL2["stud_d"], "L": FL2["light"], "B": FL2["base"], "d": FL2["shade"],
           "s": FL2["seam"], "k": "#3a474e"}
    cv = M.Canvas(16, 16)
    cv.draw_map([r.ljust(16, ".") for r in rows], pal)
    cv.outline()
    return cv


def _cv(arr):
    c = M.Canvas(arr.shape[1], arr.shape[0])
    c.a = arr.copy()
    return c


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {f"base_floor_{v}.png": _cv(floor_tile(v)) for v in range(4)}
    out["icon_base_floor.png"] = icon_base_floor()
    for name, cv in out.items():
        cv.save(PEND / name)
    return out


if __name__ == "__main__":
    o = build()
    for k, cv in o.items():
        print(f"{k}: {cv.w}×{cv.h}")
    if "--no-report" not in sys.argv:
        import v05_m3_chao_base_report as REP_
        print(REP_.build())
