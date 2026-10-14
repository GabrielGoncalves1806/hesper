#!/usr/bin/env python3
"""v0.5 M3 · Porta da base redesenhada (pedido do dono: a porta sobe até o "teto" da parede, estilo airlock).
PROPOSTA: nada daqui vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_m3_porta.py          (gera os pendentes e chama o v05_m3_porta_report.py)

Mesmo contrato do M2 (nomes, tamanhos, âncora, quadros, colisão):
    base_door_{h_n,h_s,v_e,v_w}.png    128×56  solo: 4 quadros de 32×56 (0 fechada … 3 aberta), em (x, y − 24)
    base_door2_{h_n,h_s,v_e,v_w}.png   256×56  dupla: metade 1 (oeste/norte) nos quadros 0–3, metade 2 nos 4–7
    icon_base_door.png icon_base_door_double.png   16×16  (refeitos pra casar com a porta nova)
O sufixo continua sendo a borda de FORA da base (variante B): h_s = chão ao norte, h_n = chão ao sul, v_e = chão a
oeste, v_w = chão a leste.

Linguagem (adaptada da referência do dono, desenho original): batente de metal escuro com rebites, caixa do mecanismo
em cima (lintel) com a luzinha (vermelha fechada, âmbar abrindo, verde aberta), folha bege com contorno laranja, faixas
de alerta pretas e laranja em cima e embaixo, janelinha ciano, soleira com grade.

Geometria:
  h_s (porta na parede de BAIXO, a que a câmera vê de frente): fachada alta de 56 px, do topo da parede (y − 24, a
      mesma linha do topo das paredes vizinhas) até o pé da face (y + 32). Tampa 0–4, caixa 5–12, viga 13, vão 14–50
      (folha 15–50), soleira com grade 51–55. Aberta: o vão é transparente acima de y (aparece o chão de verdade do
      tile de cima) e mostra o chão do próprio tile de y pra baixo (o tile da porta não desenha chão à parte).
  h_n (porta na parede de CIMA, vista por dentro): a folha fica na borda de fora (norte), lá no fundo do tile. A
      fachada vai do topo da parede (linha 0) até o pé da folha (linha 27): tampa 0–3, caixa 4–8, viga 9, vão 10–27.
      Na frente, a grade da soleira no chão (28–31) e o chão do tile.
  v_e / v_w (parede vertical, vista de lado): montada no motorzinho de voxels do M2 (mesma projeção do jogo). Os
      batentes sobem até o topo da parede; a folha (4 px) fica 2 px abaixo; a caixa do mecanismo com a luz fica em
      cima do batente pra onde a folha corre; a frente do batente de baixo aparece com os rebites; a grade fica no chão
      do lado de dentro.
Determinístico: sem aleatório.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import machines_r3d as M  # noqa: E402
import v05_m2_base as B  # noqa: E402

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v05_m3_porta"
PEND = REP / "pendentes"

T = 32
LIFT = 24
H = LIFT + T                      # 56
OUTLINE = M.OUTLINE
ORANGE, ORANGE_D, ORANGE_L = M.ORANGE, M.ORANGE_D, M.ORANGE_L
CYAN, CYAN_D, CYAN_L = M.CYAN, M.CYAN_D, M.CYAN_L
MT = M.METAL                      # a7a3b8 7d7892 58536b 3a3549 26222f
BG = M.BEIGE                      # fdf8ec efe6d4 d6c9b4 a99a8c 6f6070
FL = B.FL
GLASS = "#1d4a66"
JW = 4                            # batente na fachada (contorno + 3)
RETRACT = {1: [0, 8, 16, 24], 2: [0, 10, 20, 30]}
LED = {0: ("#ff6a55", "#ffc3b8", "#a8323a"),     # fechada: vermelha
       1: ("#ffc24a", "#fff0b8", "#b8823c"),     # abrindo: âmbar
       2: ("#ffc24a", "#fff0b8", "#b8823c"),
       3: ("#7fd67a", "#dcf8d8", "#3f8a4a")}     # aberta: verde

# linhas da fachada horizontal por borda
LAY = {
    "s": dict(cap=(0, 5), box=(5, 13), beam=13, under=14, leaf=(15, 51), sill=(51, 56), bottom=55),
    "n": dict(cap=(0, 4), box=(4, 9), beam=9, under=10, leaf=(11, 28), sill=None, bottom=27),
}


def rgb(c):
    return M.rgb(c)


# ---------------------------------------------------------------------------------------------------------------------
# Folha bege (vista de frente): faixa de alerta, contorno laranja, janelinha ciano, faixa laranja no meio, maçaneta.
# u, v = coordenadas na folha (w × h); lead = lado da borda que corre/encontra ("l" ou "r"); gx = x da folha fechada
# (as listras casam entre as duas folhas da dupla quando fechada).
# ---------------------------------------------------------------------------------------------------------------------
def leaf_color(u, v, w, h, lead, gx):
    hz = 3 if h >= 30 else 2
    pv0, pv1 = hz + 1, h - 2 - hz                      # painel: [pv0, pv1)
    bv = pv0 + int((pv1 - pv0) * 0.6)                  # faixa laranja do meio
    lu = w - 1 if lead == "r" else 0                   # coluna da borda que encontra
    if v == h - 1:
        return MT[4]
    if v < hz or pv1 < v < h - 1:                      # faixas de alerta (listras diagonais de 2 px)
        k = (gx + u + (v if v < hz else v - pv1)) // 2
        c = MT[4] if k % 2 == 0 else ORANGE
        if u == lu:
            c = MT[4]
        return c
    if v == hz or v == pv1:
        return ORANGE_D if u == lu else ORANGE
    # painel
    if u == lu:
        return ORANGE_D
    if u == w - 1 - lu:
        return ORANGE
    if v in (bv, bv + 1):
        return ORANGE if v == bv else ORANGE_D
    ww = 12 if w >= 26 else (10 if w >= 20 else 8)
    wh = max(4, int((bv - pv0) * 0.55))
    wu0 = (w - ww) // 2
    wv0 = pv0 + (2 if h >= 30 else 1)
    if wu0 <= u < wu0 + ww and wv0 <= v < wv0 + wh:   # janelinha ciano com moldura escura e reflexo
        gu, gv = u - wu0, v - wv0
        if gu in (0, ww - 1) or gv in (0, wh - 1):
            return MT[3] if (gu == ww - 1 or gv == wh - 1) else MT[4]
        if gu - gv in (1, 2) or gu - gv == 5:
            return CYAN_L
        return CYAN if gu + gv < (ww + wh) // 2 else CYAN_D
    hu = w - 4 if lead == "r" else 3                   # maçaneta: rasgo escuro perto da borda que encontra
    if h >= 30 and u in (hu, hu + (1 if lead == "r" else -1)) and bv - 6 <= v <= bv - 2:
        return MT[3] if u == hu else MT[2]
    rivets = {(2, pv0 + 1), (w - 3, pv0 + 1), (2, pv1 - 2), (w - 3, pv1 - 2)} if h >= 30 else set()
    if (u, v) in rivets:
        return BG[3]
    if u == 1 or v == pv0 or v == bv + 2:
        return BG[0]
    if u == w - 2 or v == pv1 - 1 or v == bv - 1:
        return BG[2]
    return BG[1]


# ---------------------------------------------------------------------------------------------------------------------
# Porta horizontal: pintura 2D da fachada (h_s alta na frente, h_n no fundo do tile)
# ---------------------------------------------------------------------------------------------------------------------
def _box_blocks(L):
    if L == T:
        return [(2, 9, False), (11, 21, True), (23, 30, False)]
    return [(2, 14, False), (26, 38, True), (50, 62, False)]


def door_h(edge, n, k):
    L = n * T
    lay = LAY[edge]
    out = np.zeros((H, L, 4), np.uint8)

    def put(x, y, c):
        if 0 <= x < L and 0 <= y < H:
            out[y, x] = rgb(c)

    # 1. chão do tile (rows 24..55), por baixo de tudo; no h_n, a grade da soleira no chão em frente à folha
    floor = np.concatenate([B.floor_tile(0)] * n, axis=1)
    out[LIFT:H] = floor
    if edge == "n":
        for x in range(2, L - 2):
            put(x, 28, MT[4])
            for y in (29, 30):
                put(x, y, MT[2] if x % 3 == 0 else MT[4])
            put(x, 31, FL["light"])
    # 2. vão: transparente acima de y (o tile de cima aparece), chão do tile de y pra baixo
    a0, a1 = JW, L - JW
    l0, l1 = lay["leaf"]
    for y in range(lay["under"], l1):
        for x in range(a0, a1):
            if y < LIFT:
                out[y, x] = 0
    for x in range(a0, a1):
        put(x, lay["under"], MT[4])                     # sombra embaixo da viga
    # 3. folha(s)
    r = RETRACT[n][k]
    lh = l1 - l0
    if n == 1:
        leaves = [(a0 - r, a1 - a0, "r", 0)]
    else:
        mid = L // 2
        leaves = [(a0 - r, mid - a0, "r", 0), (mid + r, a1 - mid, "l", mid - a0)]
    seam_top = l0 + (lh * 6) // 10                      # emenda em degrau da dupla: +1 em cima, −1 embaixo
    for li, (x0, w, lead, gx) in enumerate(leaves):
        for v in range(lh):
            y = l0 + v
            step = 0
            if n == 2:
                step = 1 if y < seam_top else -1
            ww = w + (step if li == 0 else -step)
            xs = x0 if li == 0 else x0 + step
            for u in range(ww):
                x = xs + u
                if not (a0 <= x < a1):
                    continue
                uu = min(u, w - 1) if li == 0 else max(0, u - (ww - w))
                c = leaf_color(uu, v, w, lh, lead, gx)
                if n == 2 and r == 0 and li == 0 and u == ww - 1 and v < lh - 1:
                    c = OUTLINE                                  # a emenda das duas folhas fechadas
                put(x, y, c)
            if n == 2 and r == 0 and li == 0 and y == seam_top and v < lh - 1:
                for x in (xs + ww - 2, xs + ww - 1, xs + ww):
                    put(x, y, OUTLINE)                           # o degrau
    # 4. batentes (rebites a cada 8 px)
    j0 = lay["beam"]
    for y in range(j0, lay["bottom"] + 1):
        for i, c in enumerate([OUTLINE, MT[1], MT[2], MT[3]]):
            put(i, y, c)
        for i, c in enumerate([MT[1], MT[2], MT[3], OUTLINE]):
            put(L - JW + i, y, c)
        if (y - j0) % 8 == 4 and y < lay["bottom"] - 1:
            put(2, y, MT[0])
            put(2, y + 1, MT[4])
            put(L - 3, y, MT[0])
            put(L - 3, y + 1, MT[4])
    # 5. soleira com grade (h_s)
    if lay["sill"]:
        s0, s1 = lay["sill"]
        for x in range(a0, a1):
            put(x, s0, MT[1])
            for y in range(s0 + 1, s1 - 2):
                put(x, y, MT[2] if (x - a0) % 3 == 2 else MT[4])
            put(x, s1 - 2, MT[3])
        for x in range(L):
            put(x, s1 - 1, OUTLINE)
        for x in (a0, a1 - 1):
            for y in range(s0 + 1, s1 - 2):
                put(x, y, MT[3])
    else:
        for x in range(L):
            put(x, lay["bottom"], OUTLINE if x < a0 or x >= a1 else MT[4])
    # 6. viga (embaixo da caixa) com rebites
    for x in range(L):
        put(x, j0, MT[2] if 0 < x < L - 1 else OUTLINE)
        if x % 8 == 4:
            put(x, j0, MT[0])
    # 7. caixa do mecanismo
    b0, b1 = lay["box"]
    for y in range(b0, b1):
        for x in range(L):
            put(x, y, MT[3])
        put(0, y, OUTLINE)
        put(L - 1, y, OUTLINE)
    for x in range(1, L - 1):
        put(x, b0, MT[4])                               # sombra embaixo da tampa
    led = LED[k]
    for (x0, x1, center) in _box_blocks(L):
        for y in range(b0 + 1, b1):
            for x in range(x0, x1):
                c = BG[1]
                if y == b0 + 1 or x == x0:
                    c = BG[0]
                if x == x1 - 1:
                    c = BG[2]
                if y == b1 - 1:
                    c = BG[3]
                put(x, y, c)
        if not center:                                  # parafusos
            put(x0 + 1, b1 - 2, BG[3])
            put(x1 - 2, b1 - 2, BG[3])
        else:
            cx = (x0 + x1) // 2
            ly0 = b0 + 2 if b1 - b0 >= 7 else b0 + 1
            lh_ = 2
            for y in range(ly0 - 1, ly0 + lh_ + 1):
                for x in range(cx - 2, cx + 2):
                    put(x, y, MT[4])
            put(cx - 1, ly0, led[1])
            put(cx, ly0, led[0])
            put(cx - 1, ly0 + 1, led[0])
            put(cx, ly0 + 1, led[2])
            if b1 - b0 >= 7:                            # risquinhos de ventilação dos lados da luz
                for x in (cx - 4, cx + 3):
                    for y in range(b0 + 2, b1 - 2):
                        put(x, y, BG[3] if y % 2 == 0 else BG[1])
    # engrenagens/pistões nos vãos entre os blocos
    blocks = _box_blocks(L)
    for (xa, _, _), (_, xb, _) in zip(blocks[1:], blocks[:-1]):
        gx0, gx1 = xb, xa
        gy = (b0 + 1 + b1) // 2
        for x in range(gx0, gx1):
            put(x, gy, ORANGE_D)
            put(x, gy - 1, MT[2])
        if gx1 - gx0 >= 6:                               # engrenagem na dupla
            cx = (gx0 + gx1) // 2
            for dx, dy in ((-1, -2), (0, -2), (-2, -1), (1, -1), (-2, 0), (1, 0), (-1, 1), (0, 1)):
                put(cx + dx, gy + dy, MT[1])
            put(cx - 1, gy - 1, MT[0])
            put(cx, gy, MT[4])
            put(cx - 1, gy, ORANGE)
            put(cx, gy - 1, ORANGE)
    # 8. tampa (vista de cima, alinhada com o topo das paredes vizinhas)
    c0, c1 = lay["cap"]
    caps = [OUTLINE, MT[0], MT[1], MT[1], MT[2]] if c1 - c0 == 5 else [OUTLINE, MT[0], MT[1], MT[2]]
    for i, y in enumerate(range(c0, c1)):
        for x in range(L):
            c = caps[i]
            if x in (0, L - 1):
                c = OUTLINE
            elif x == 1 and i > 0:
                c = MT[0]
            elif x == L - 2 and i > 0:
                c = MT[2]
            put(x, y, c)
    for x in range(6, L - 6, 10 if n == 1 else 12):  # risco de chapa na tampa
        put(x, c0 + 2, MT[2])
    # sprites por tile
    return [out[:, t * T:(t + 1) * T].copy() for t in range(n)]


# ---------------------------------------------------------------------------------------------------------------------
# Porta vertical: voxels (mesma projeção do jogo), cor pela peça
# ---------------------------------------------------------------------------------------------------------------------
POSTV, MECH, LEAFA, LEAFB, SILLV = 11, 12, 13, 14, 15
DEPTH_V = 6
POST_LEN = 4
Z_LEAF_V = 22
STEP_V = 1


def door_v(edge, n, k):
    L = n * T
    V = B.Vox(X=T, Y=L)
    d0 = 0 if edge == "w" else T - DEPTH_V
    V.box(0, T, 0, L, -1, 0, SILLV)
    a0, a1 = POST_LEN, L - POST_LEN
    V.box(d0, d0 + DEPTH_V, 0, a0, 0, LIFT, MECH)
    V.box(d0, d0 + DEPTH_V, a1, L, 0, LIFT, MECH if n == 2 else POSTV)
    r = RETRACT[n][k]
    lx0, lx1 = d0, d0 + DEPTH_V
    if n == 1:
        s0, s1 = max(a0, a0 - r), a1 - r
        if s1 > s0:
            V.box(lx0, lx1, s0, s1, 0, Z_LEAF_V, LEAFA)
    else:
        mid = L // 2
        half = (lx0 + lx1) // 2
        for (x0, x1, st) in ((lx0, half, STEP_V), (half, lx1, -STEP_V)):
            e0 = mid + st - r
            if e0 > a0:
                V.box(x0, x1, a0, e0, 0, Z_LEAF_V, LEAFA)
            e1 = mid + st + r
            if e1 < a1:
                V.box(x0, x1, e1, a1, 0, Z_LEAF_V, LEAFB)
    HH = LIFT + L
    mat, face, P, depth = V.render(H=HH)
    floor = np.concatenate([B.floor_tile(0)] * n, axis=0)
    gr = range(d0 - 5, d0 - 1) if edge == "e" else range(d0 + DEPTH_V + 1, d0 + DEPTH_V + 5)
    for y in range(2, L - 2):                            # grade da soleira no chão, do lado de dentro
        for i, x in enumerate(gr):
            if edge == "e":
                c = [MT[3], None, None, FL["light"]][i]
            else:
                c = [MT[3], None, None, FL["light"]][i]
            if c is None:
                c = MT[2] if y % 3 == 0 else MT[4]
            floor[y, x] = rgb(c)
        for x in (d0 + 1, d0 + DEPTH_V - 2):             # trilho embaixo da folha (2 riscos)
            floor[y, x] = rgb(FL["seam"])
    led = LED[k]
    out = np.zeros((HH, T, 4), np.uint8)
    for row in range(HH):
        for x in range(T):
            mt, fc = mat[row, x], face[row, x]
            if fc == 0:
                continue
            px, py, pz = P[row, x]
            if mt == SILLV:
                c = floor[py, px]
            elif mt in (POSTV, MECH):
                if fc == 1:                              # topo do batente
                    if mt == MECH:
                        north = py < a0
                        c = BG[1]
                        if px == d0 or (py == (0 if north else L - POST_LEN)):
                            c = BG[0]
                        if px == d0 + DEPTH_V - 1:
                            c = BG[2]
                        cx = d0 + DEPTH_V // 2
                        ly = 1 if north else L - 3
                        if px in (cx - 1, cx) and py in (ly, ly + 1):
                            c = [[led[1], led[0]], [led[0], led[2]]][py - ly][px - cx + 1]
                    else:
                        c = MT[1] if px == d0 else MT[2]
                        if px == d0 + DEPTH_V // 2 and py == L - 2:
                            c = MT[0]
                    c = rgb(c)
                else:                                    # frente do batente (só a de baixo aparece): metal e rebites
                    fz = LIFT - 1 - pz
                    c = MT[2]
                    if px == d0 + 1:
                        c = MT[1]
                    if px == d0 + DEPTH_V - 2:
                        c = MT[3]
                    if fz <= 6 and mt == MECH:            # a caixa do mecanismo em cima do batente
                        c = BG[1] if fz > 0 else BG[0]
                        if fz == 6:
                            c = BG[3]
                        if px == d0 + DEPTH_V // 2 and fz == 3:
                            c = led[0]
                    elif fz % 8 == 4 and px == d0 + DEPTH_V // 2:
                        c = MT[0]
                    c = rgb(c)
            else:                                        # folha
                if fc == 1:
                    lead_n = mt == LEAFB                  # a ponta que corre: sul na A, norte na B
                    if n == 1:
                        tip = py >= a1 - r - 4
                    elif mt == LEAFA:
                        tip = py >= L // 2 - r - 4
                    else:
                        tip = py < L // 2 + r + 4
                    xi = px - lx0
                    c = [MT[4], ORANGE, BG[0], BG[1], ORANGE_D, MT[4]][min(xi, 5)]
                    if tip:
                        c = MT[4] if ((px + py) // 2) % 2 == 0 else ORANGE
                    elif (py % 8) == 3 and xi in (2, 3):
                        c = BG[2]
                    _ = lead_n
                    c = rgb(c)
                else:
                    fz = Z_LEAF_V - 1 - pz
                    c = BG[1]
                    if fz < 2 or fz >= Z_LEAF_V - 3:
                        c = MT[4] if ((px + fz) // 2) % 2 == 0 else ORANGE
                    elif px in (lx0, lx1 - 1):
                        c = MT[4]
                    elif px == lx0 + 1:
                        c = ORANGE
                    elif px == lx1 - 2:
                        c = ORANGE_D
                    c = rgb(c)
            out[row, x] = c
    # contorno: pixel sólido (que não é chão) com vizinho vazio ou bem mais longe
    solid = out[:, :, 3] == 255
    add = np.zeros_like(solid)
    notfloor = solid & (mat != SILLV)
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.full_like(depth, -1e9)
        ys = slice(max(ddy, 0), HH + min(ddy, 0))
        yd = slice(max(-ddy, 0), HH + min(-ddy, 0))
        xs = slice(max(ddx, 0), T + min(ddx, 0))
        xd = slice(max(-ddx, 0), T + min(-ddx, 0))
        nb[yd, xd] = depth[ys, xs]
        add |= notfloor & (depth - nb > 3)
    out[add] = rgb(OUTLINE)
    sprites = []
    for t in range(n):
        sp = np.zeros((H, T, 4), np.uint8)
        blk = out[t * T:t * T + H]
        own = (P[t * T:t * T + H, :, 1] // T == t) & (face[t * T:t * T + H] > 0)
        sp[own] = blk[own]
        sprites.append(sp)
    return sprites


def door(orient, edge, n, k):
    return door_h(edge, n, k) if orient == "h" else door_v(edge, n, k)


def strip(orient, edge, n):
    frames = [door(orient, edge, n, k) for k in range(4)]
    return np.concatenate([frames[k][t] for t in range(n) for k in range(4)], axis=1)


# ---------------------------------------------------------------------------------------------------------------------
# Ícones 16×16 (refeitos na linguagem nova)
# ---------------------------------------------------------------------------------------------------------------------
def _icon_pal():
    return {"K": OUTLINE, "m": MT[1], "M": MT[2], "d": MT[3], "D": MT[4], "B": BG[1], "b": BG[2], "W": BG[0],
            "O": ORANGE, "o": ORANGE_D, "c": CYAN, "C": CYAN_D, "l": CYAN_L, "r": "#ff6a55", "g": MT[0]}


def icon_door():
    rows = [
        "................",
        ".KKKKKKKKKKKKKK.",
        ".KmmmmmmmmmmmmK.",
        ".KDBBdBrBdBBBDK.",
        ".KMMMMMMMMMMMMK.",
        ".KmDOODOODOODdK.",
        ".KmOWBBBBBBBodK.",
        ".KmOBKKKKKBBodK.",
        ".KmOBKlcCKBBodK.",
        ".KmOBKcCCKBBodK.",
        ".KmOOOOOOOOOodK.",
        ".KmOWBBBBBBdodK.",
        ".KmDOODOODOODdK.",
        ".KddddddddddddK.",
        ".KKKKKKKKKKKKKK.",
        "................",
    ]
    return B._icon(rows, _icon_pal())


def icon_door_double():
    rows = [
        "................",
        "KKKKKKKKKKKKKKKK",
        "KmmmmmmmmmmmmmmK",
        "KDBBdBBrrBBdBBDK",
        "KMMMMMMMMMMMMMMK",
        "KmDOODOKODOODOdK",
        "KmOWBBoKOWBBBodK",
        "KmOKKBoKOBKKBodK",
        "KmOlCBoKOBlCBodK",
        "KmOOOOoKOOOOOodK",
        "KmOWBBKoOWBBBodK",
        "KmOBBBKoOBBBBodK",
        "KmDOODKODOODOOdK",
        "KddddddddddddddK",
        "KKKKKKKKKKKKKKKK",
        "................",
    ]
    return B._icon(rows, _icon_pal())


def _cv(arr):
    return B._cv(arr)


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for o, edges in (("h", "ns"), ("v", "we")):
        for e in edges:
            out[f"base_door_{o}_{e}.png"] = _cv(strip(o, e, 1))
            out[f"base_door2_{o}_{e}.png"] = _cv(strip(o, e, 2))
    out["icon_base_door.png"] = icon_door()
    out["icon_base_door_double.png"] = icon_door_double()
    for name, cv in out.items():
        cv.save(PEND / name)
    return out


if __name__ == "__main__":
    o = build()
    for k, cv in o.items():
        print(f"{k}: {cv.w}×{cv.h}")
    if "--no-report" not in sys.argv:
        import v05_m3_porta_report as R
        print(R.build())
