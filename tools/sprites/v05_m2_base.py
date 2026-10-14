#!/usr/bin/env python3
"""v0.5 Marco 2 · Base respirável: chão, parede alta (autotile), porta, Dispersor de O₂, aviso de vazamento e ícones.
PROPOSTA: nada daqui vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v05_m2_base.py

Geometria = a mesma da parede de rocha do jogo (game/render.py `_draw_wall`): o bloco ocupa o tile inteiro e tem 24 px
de altura. O topo (32×32) é desenhado em (x, y − 24) e a face (32×24) em (x, y + 8), só quando o tile de baixo não é
parede. Assim o raio-x (`player_occluded`) e a ordem de desenho por linha valem do jeito que já estão.

Projeção usada aqui (a do jogo, sem encurtar): um ponto do tile em planta (px, py) na altura z cai na tela em
(px, py − z). As portas são montadas num motorzinho de voxels com essa projeção (o z-buffer resolve quem cobre quem
quando as folhas abrem); o topo e a face da parede são pintados em 2D a partir da máscara em planta.

Saída: reports/design/v05_m2_base/pendentes/
    base_floor_{0..3}.png                 32×32   chão construído (4 variações, sorteio por hash do tile)
    base_wall_top.png                     64×96   topo da parede no layout A2 (o mesmo do water_auto e do game/autotile.py)
    base_wall_face.png                    128×24  face: 4 peças de 32×24, índice = W + 2·E (1 = o vizinho é parede/porta)
    base_door_h_{n,s}.png                 128×56  v1.1 porta FINA na parede horizontal (passa N–S), folha na borda n ou s:
                                                  4 quadros 32×56, 0 fechada → 3 aberta
    base_door_v_{w,e}.png                 128×56  idem na parede vertical (passa L–O), folha na borda w ou e
    (a porta grossa da v1.0 vai pra reports/design/v05_m2_base/anterior/, só pra comparar)
    machine_o2_dispenser.png              32×48   Dispersor de O₂ parado (sem água / sem energia)
    anim/anim_machine_o2_dispenser.png    128×48  soprando (vedado): 4 quadros
    anim/anim_machine_o2_dispenser_leak.png 128×48 soprando com vazamento (LED âmbar piscando, sopro fraco): 4 quadros (opcional)
    leak_blink.png                        64×56   aviso de vazamento: 2 quadros de 32×56 (aceso, apagado), em (x, y − 24)
    icon_base_floor.png icon_base_wall.png icon_base_door.png icon_o2_dispenser.png   16×16
Depois chama o v05_m2_base_report.py (mocks e index.html). Determinístico: sem aleatório.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import machines_r3d as M  # noqa: E402
from r3d import Pal  # noqa: E402

ROOT = HERE.parents[1]
REP = ROOT / "reports" / "design" / "v05_m2_base"
PEND = REP / "pendentes"

T = 32
LIFT = 24                       # = C.WALL_LIFT
FACE_H = 24
OUTLINE = M.OUTLINE
ORANGE, ORANGE_D, ORANGE_L = M.ORANGE, M.ORANGE_D, M.ORANGE_L
CYAN, CYAN_D, CYAN_L = M.CYAN, M.CYAN_D, M.CYAN_L
OK, ALERT = M.OK, M.ALERT
AMBER = "#ffc24a"


def rgb(c):
    return M.rgb(c)


# ---------------------------------------------------------------------------------------------------------------------
# Paletas (fixas, não mudam com o estágio: é coisa construída)
# ---------------------------------------------------------------------------------------------------------------------
# topo da parede: chapa ardósia fria (mais escura que o chão, pra ler como "telhado" do muro), aba clara na borda
TOP = dict(hl="#c9c4d6", lip="#b4afc6", cap="#8f8aa6", cap_d="#6f6a85", groove="#34304a", plate="#55506a",
           tread="#625d78", tread_d="#47425c", rivet="#8f8aa6", dark="#3a3549")
# face: painel bege (a família das máquinas), faixa laranja, rodapé escuro
FACE = dict(trim_l="#8f8aa6", trim="#55506a", hi="#fbf8f1", panel="#e6e1dc", low="#cfc8cc", low2="#b9b1ba",
            o_l=ORANGE_L, o=ORANGE, o_d=ORANGE_D, plinth="#58536b", plinth_d="#3a3549", rivet="#8f8aa6",
            vent="#8f88a0", vent_d="#5c5570")
# chão: chapa de aço azulada, valor médio (contrasta com o vermelho do Árido, o cinza-marrom da Névoa e o verde)
FL = dict(seam="#3b374d", hl="#b3afc8", light="#9b97b3", base="#837f9c", shade="#6c6886", dark="#555170",
          rivet="#c9c6da", rivet_d="#4a465f", grate="#2c2838", grate_l="#6c6886", stripe="#e2733a", stripe_d="#a9482a")
# porta: aço claro (destaca do bege da parede) com a faixa de advertência laranja/escura
DOOR = dict(hl="#ffffff", light="#e3e5ee", base="#c3c6d4", shade="#9a9db0", dark="#6f7286", seam="#2a2638",
            hz="#e2733a", hz_d="#3a3549", win="#1d2b3a", win_l="#2f4a66")


# ---------------------------------------------------------------------------------------------------------------------
# Topo da parede: pintado a partir da máscara em planta (True = parede). Cada pixel olha o pixel aberto mais perto
# (distância de Chebyshev) e a direção dele: borda N/O clara, L/S escura, contorno no limite e a aba clara no S
# (o encontro com a face). O miolo é chapa com padrão de piso antiderrapante alinhado a 16 px (emenda no A2).
# ---------------------------------------------------------------------------------------------------------------------
def _nearest_open(mask, R=7):
    H, W = mask.shape
    best = np.full((H, W), 99, int)
    bdx = np.zeros((H, W), int)
    bdy = np.zeros((H, W), int)
    pad = np.pad(~mask, R, constant_values=True)
    order = []
    for r in range(1, R + 1):
        ring = [(dx, dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if max(abs(dx), abs(dy)) == r]
        # prioridade em empate: N, O, NO, NE, SO, L, S, SE
        ring.sort(key=lambda d: (abs(d[0]) + abs(d[1]), 0 if d[1] < 0 else (1 if d[0] < 0 else 2), d[0], d[1]))
        order += [(r, dx, dy) for dx, dy in ring]
    for r, dx, dy in order:
        hit = pad[R + dy:R + dy + H, R + dx:R + dx + W] & (best == 99) & mask
        best[hit] = r - 1
        bdx[hit] = dx
        bdy[hit] = dy
    return best, bdx, bdy


def top_paint(mask, ox=0, oy=0, style="wall"):
    """RGBA (H, W, 4) do topo pra máscara em planta. ox, oy = deslocamento absoluto (o padrão casa a cada 16 px)."""
    H, W = mask.shape
    m, dx, dy = _nearest_open(mask)
    out = np.zeros((H, W, 4), np.uint8)
    for y in range(H):
        for x in range(W):
            if not mask[y, x]:
                continue
            d, ex, ey = m[y, x], dx[y, x], dy[y, x]
            south = ey > 0 and ex == 0
            light = ey < 0 or ex < 0
            ax, ay = (x + ox) % 16, (y + oy) % 16
            if d == 0:
                c = TOP["lip"] if south else OUTLINE
            elif d == 1:
                c = TOP["hl"] if light else (TOP["cap_d"] if south else TOP["dark"])
            elif d in (2, 3):
                c = TOP["cap"] if light else TOP["cap_d"]
            elif d == 4:
                c = TOP["groove"]
            else:
                c = TOP["plate"]
                # antiderrapante: tracinhos de 2 px alternando a direção, em grade de 4 px
                cx, cy = ax % 8, ay % 8
                if (cx, cy) in ((1, 1), (2, 1), (5, 5), (5, 6)):
                    c = TOP["tread"]
                elif (cx, cy) in ((1, 2), (2, 2), (6, 5), (6, 6)):
                    c = TOP["tread_d"]
            out[y, x] = rgb(c)
    return out


def top_tile_mask(conn):
    """Máscara 3×3 tiles (96×96) de um arranjo de vizinhos. conn = 3×3 de bool (o meio é o tile)."""
    mk = np.zeros((96, 96), bool)
    for j in range(3):
        for i in range(3):
            if conn[j][i]:
                mk[j * T:(j + 1) * T, i * T:(i + 1) * T] = True
    return mk


def wall_top_atlas():
    """Atlas A2 64×96 (minitiles 16×16), o MESMO layout do water_auto e do game/autotile.py:
    (0,0)-(32,32) peça isolada, (32,0)-(64,32) cantos internos, (0,32)-(64,96) bloco 2×2 (cantos externos, bordas,
    miolo)."""
    atlas = np.zeros((96, 64, 4), np.uint8)
    iso = top_paint(top_tile_mask([[0, 0, 0], [0, 1, 0], [0, 0, 0]]))
    atlas[0:32, 0:32] = iso[32:64, 32:64]
    plus = top_paint(top_tile_mask([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    atlas[0:32, 32:64] = plus[32:64, 32:64]
    mk = np.zeros((128, 128), bool)
    mk[32:96, 32:96] = True
    blk = top_paint(mk)
    atlas[32:96, 0:64] = blk[32:96, 32:96]
    return atlas


# ---------------------------------------------------------------------------------------------------------------------
# Face da parede (24 px de altura): trilho, painel bege, faixa laranja, rodapé escuro, contorno no pé.
# Sem juntas verticais: o detalhe é horizontal (respiro e rebites) e casa a cada 16 px.
# ---------------------------------------------------------------------------------------------------------------------
FACE_ROWS = (["trim_l", "trim", "hi"] + ["panel"] * 9 + ["low", "low2", "o_l", "o", "o", "o_d", "plinth", "plinth",
                                                          "plinth", "plinth_d", "plinth_d"] + ["OUT"])
assert len(FACE_ROWS) == FACE_H


def _lighter(c):
    return {"panel": "hi", "low": "panel", "low2": "low", "o": "o_l", "o_d": "o", "plinth": "trim_l",
            "plinth_d": "plinth", "trim": "trim_l"}.get(c, c)


def _darker(c):
    return {"hi": "panel", "panel": "low2", "low": "low2", "low2": "vent_d", "o_l": "o", "o": "o_d",
            "plinth": "plinth_d", "trim_l": "trim", "trim": "plinth_d"}.get(c, c)


def face_paint(w, left_open, right_open, ox=0, detail=True):
    out = np.zeros((FACE_H, w, 4), np.uint8)
    for y in range(FACE_H):
        for x in range(w):
            k = FACE_ROWS[y]
            ax = (x + ox) % 32
            if detail and k == "panel" and y in (6, 7) and 12 <= ax <= 19:         # respiro no meio do tile
                k = "vent_d" if y == 7 else "vent"
            if detail and k == "plinth" and y == 19 and ax in (4, 27):            # rebites no rodapé
                k = "rivet"
            c = OUTLINE if k == "OUT" else FACE[k]
            if left_open and x == 0 or right_open and x == w - 1:
                c = OUTLINE
            elif left_open and x == 1 and k != "OUT":
                c = FACE[_lighter(k)]
            elif right_open and x == w - 2 and k != "OUT":
                c = FACE[_darker(k)]
            out[y, x] = rgb(c)
    return out


def wall_face_strip():
    """4 peças 32×24 lado a lado: índice = W + 2·E (W/E = o vizinho daquele lado é parede ou porta)."""
    out = np.zeros((FACE_H, 4 * T, 4), np.uint8)
    for idx in range(4):
        w_conn, e_conn = idx & 1, idx >> 1
        out[:, idx * T:(idx + 1) * T] = face_paint(T, not w_conn, not e_conn)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Chão construído (32×32): chapa de aço com chanfro, rebites; variações com grelha e faixa de advertência
# ---------------------------------------------------------------------------------------------------------------------
def floor_tile(v):
    a = np.zeros((T, T, 4), np.uint8)

    def put(x, y, c):
        a[y, x] = rgb(c)

    for y in range(T):
        for x in range(T):
            c = FL["base"]
            if x == 0 or y == 0:
                c = FL["seam"]
            elif y == 1 or x == 1:
                c = FL["light"]
            elif y == T - 1 or x == T - 1:
                c = FL["dark"]
            elif y == T - 2 or x == T - 2:
                c = FL["shade"]
            put(x, y, c)
    put(1, 1, FL["hl"])
    rivets = [(4, 4), (27, 4), (4, 27), (27, 27)]
    if v == 1:                         # dividida em 2 chapas (emenda horizontal), rebites no meio
        for x in range(1, T):
            put(x, 15, FL["dark"])
            put(x, 16, FL["seam"])
            put(x, 17, FL["light"])
        rivets += [(4, 12), (27, 12), (4, 20), (27, 20)]
    elif v == 2:                       # grelha de ventilação no meio
        x0, y0, gw, gh = 9, 10, 14, 12
        for y in range(y0, y0 + gh):
            for x in range(x0, x0 + gw):
                edge = y in (y0, y0 + gh - 1) or x in (x0, x0 + gw - 1)
                put(x, y, FL["seam"] if edge else (FL["grate"] if (y - y0) % 3 else FL["grate_l"]))
        for x in range(x0 + 1, x0 + gw):
            put(x, y0 + gh, FL["light"])
        for y in range(y0 + 1, y0 + gh):
            put(x0 + gw, y, FL["light"])
    elif v == 3:                       # tampa de inspeção quadrada (rebaixada) com 4 parafusos
        x0, y0, w = 10, 10, 12
        for y in range(y0, y0 + w):
            for x in range(x0, x0 + w):
                c = FL["shade"]
                if y == y0 or x == x0:
                    c = FL["seam"]
                elif y == y0 + w - 1 or x == x0 + w - 1:
                    c = FL["light"]
                elif y == y0 + 1 or x == x0 + 1:
                    c = FL["dark"]
                put(x, y, c)
        for (x, y) in ((x0 + 3, y0 + 3), (x0 + w - 4, y0 + 3), (x0 + 3, y0 + w - 4), (x0 + w - 4, y0 + w - 4)):
            put(x, y, FL["rivet"])
        rivets = [(4, 4), (27, 4), (4, 27), (27, 27)]
    for (x, y) in rivets:
        put(x, y, FL["rivet"])
        put(x + 1, y + 1, FL["rivet_d"])
    return a


# ---------------------------------------------------------------------------------------------------------------------
# Motorzinho de voxels com a projeção do jogo: voxel (x, y, z) ocupa [x,x+1)×[y,y+1)×[z,z+1).
# Topo exposto → pixel (x, y − z − 1); frente exposta → pixel (x, y − z). Quanto maior y + z, mais perto.
# z = −1 é o chão do tile (o topo dele fica na altura 0, na linha y).
# ---------------------------------------------------------------------------------------------------------------------
class Vox:
    Z0 = -1

    def __init__(self, X=T, Y=T, Z=LIFT):
        self.X, self.Y, self.Z = X, Y, Z
        self.m = np.zeros((X, Y, Z - self.Z0), np.int16)

    def box(self, x0, x1, y0, y1, z0, z1, mat):
        x0, x1 = max(0, x0), min(self.X, x1)
        y0, y1 = max(0, y0), min(self.Y, y1)
        if x1 > x0 and y1 > y0:
            self.m[x0:x1, y0:y1, z0 - self.Z0:z1 - self.Z0] = mat

    def render(self, H=LIFT + T, oy=LIFT):
        """Devolve (mat, face, px, py, pz) por pixel da tela H×X (face 1 = topo, 2 = frente, 0 = vazio)."""
        X = self.X
        depth = np.full((H, X), -1e9)
        mat = np.zeros((H, X), int)
        face = np.zeros((H, X), int)
        P = np.zeros((H, X, 3), int)
        xs, ys, zs = np.nonzero(self.m)
        for x, y, zi in zip(xs, ys, zs):
            z = zi + self.Z0
            mt = self.m[x, y, zi]
            above = zi + 1 < self.m.shape[2] and self.m[x, y, zi + 1] != 0
            front = y + 1 < self.Y and self.m[x, y + 1, zi] != 0
            d = y + z
            if not above:
                r = y - z - 1 + oy
                if 0 <= r < H and d > depth[r, x]:
                    depth[r, x], mat[r, x], face[r, x], P[r, x] = d, mt, 1, (x, y, z)
            if not front:
                r = y - z + oy
                if 0 <= r < H and d > depth[r, x]:
                    depth[r, x], mat[r, x], face[r, x], P[r, x] = d, mt, 2, (x, y, z)
        return mat, face, P, depth


# materiais das portas
POST, HEADER, LEAF, SILL = 1, 2, 3, 4


def _door_top_colors(mask_mid, conn_w, conn_e, conn_n, conn_s):
    """Pinta o topo das partes fixas da porta (batentes, travessa) com o mesmo estilo da parede, com os vizinhos
    certos em volta (parede onde a porta encosta, aberto no resto). mask_mid = 32×32 em planta."""
    mk = np.zeros((96, 96), bool)
    mk[32:64, 32:64] = mask_mid
    if conn_w:
        mk[32:64, 0:32] = True
    if conn_e:
        mk[32:64, 64:96] = True
    if conn_n:
        mk[0:32, 32:64] = True
    if conn_s:
        mk[64:96, 32:64] = True
    return top_paint(mk)[32:64, 32:64]


def _leaf_top(mask, seam_axis, seam_at, ox=0, oy=0):
    """Topo das folhas da porta: aço claro, chanfro, faixa de advertência ao longo da emenda."""
    H, W = mask.shape
    m, dx, dy = _nearest_open(mask, R=4)
    out = np.zeros((H, W, 4), np.uint8)
    for y in range(H):
        for x in range(W):
            if not mask[y, x]:
                continue
            d, ex, ey = m[y, x], dx[y, x], dy[y, x]
            light = ey < 0 or ex < 0
            s = (x - seam_at) if seam_axis == "x" else (y - seam_at)
            along = y if seam_axis == "x" else x
            if d == 0:
                c = DOOR["seam"] if not (ey > 0 and ex == 0) else DOOR["light"]
            elif d == 1:
                c = DOOR["hl"] if light else DOOR["shade"]
            elif abs(s + 0.5) <= 3.5:                  # faixa de advertência dos dois lados da emenda
                c = DOOR["hz"] if ((along + (s if s >= 0 else -s)) // 2) % 2 == 0 else DOOR["hz_d"]
            else:
                c = DOOR["base"] if d > 2 else DOOR["light"]
            out[y, x] = rgb(c)
    return out


def _leaf_front(w, h, seam_x=None, ox=0, ends=(False, False), window=True):
    """Frente das folhas (aço claro): chanfro em cima, visor escuro, chevrons laranja perto da emenda, rodapé."""
    out = np.zeros((h, w, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            ax = x + ox
            c = DOOR["base"]
            if y == 0:
                c = DOOR["light"]
            elif y >= h - 4:
                c = DOOR["dark"] if y < h - 1 else OUTLINE
            elif y >= h - 7:
                c = DOOR["shade"]
            if window and 4 <= y <= 9 and seam_x is not None and 3 <= abs(ax + 0.5 - seam_x) <= 7.5:
                c = DOOR["win"] if y > 4 else DOOR["win_l"]
            if seam_x is not None and 11 <= y <= 16 and abs(ax + 0.5 - seam_x) <= 7.5:
                k = int(abs(ax + 0.5 - seam_x)) + y
                c = DOOR["hz"] if (k // 2) % 2 == 0 else DOOR["hz_d"]
            if seam_x is not None and abs(ax + 0.5 - seam_x) < 1 and y < h - 1:
                c = DOOR["seam"]
            if ends[0] and x == 0 or ends[1] and x == w - 1:
                c = OUTLINE
            out[y, x] = rgb(c)
    return out


def door_frame(orient, k, n=4):
    """Quadro k (0 fechada .. n−1 aberta) da porta, 32×56, desenhada em (x, y − 24)."""
    retract = [0, 4, 8, 11][k]
    V = Vox()
    V.box(0, T, 0, T, -1, 0, SILL)
    if orient == "h":                         # parede horizontal, passa N–S; folhas correm pros batentes L/O
        V.box(0, 5, 0, T, 0, LIFT, POST)
        V.box(27, T, 0, T, 0, LIFT, POST)
        V.box(5, 27, 0, 4, LIFT - 4, LIFT, HEADER)
        V.box(5, 16 - retract, 0, T, 0, LIFT, LEAF)
        V.box(16 + retract, 27, 0, T, 0, LIFT, LEAF)
    else:                                     # parede vertical, passa L–O; folhas correm pros batentes N/S
        V.box(0, T, 0, 5, 0, LIFT, POST)
        V.box(0, T, 27, T, 0, LIFT, POST)
        V.box(0, T, 5, 16 - retract, 0, LIFT, LEAF)
        V.box(0, T, 16 + retract, 27, 0, LIFT, LEAF)
    mat, face, P, depth = V.render()
    H = LIFT + T
    # topo: máscaras em planta das partes na altura cheia
    fixed = np.zeros((T, T), bool)
    leaf = np.zeros((T, T), bool)
    for x in range(T):
        for y in range(T):
            col = V.m[x, y, LIFT - 1 - V.Z0]
            if col in (POST, HEADER):
                fixed[y, x] = True
            elif col == LEAF:
                leaf[y, x] = True
    if orient == "h":
        top_fixed = _door_top_colors(fixed | leaf, True, True, False, False)
        top_leaf = _leaf_top(leaf, "x", 16)
    else:
        top_fixed = _door_top_colors(fixed | leaf, False, False, True, True)
        top_leaf = _leaf_top(leaf, "y", 16)
    sill = floor_tile(0)
    # trilho da porta na soleira
    if orient == "h":
        for x in range(2, 30):
            sill[14, x] = rgb(FL["grate"])
            sill[15, x] = rgb(FL["seam"])
            sill[16, x] = rgb(FL["light"])
    else:
        for y in range(2, 30):
            sill[y, 14] = rgb(FL["grate"])
            sill[y, 15] = rgb(FL["seam"])
            sill[y, 16] = rgb(FL["light"])
    out = np.zeros((H, T, 4), np.uint8)
    for r in range(H):
        for x in range(T):
            mt, fc = mat[r, x], face[r, x]
            if fc == 0:
                continue
            px, py, pz = P[r, x]
            if mt == SILL:
                c = sill[py, px]
            elif fc == 1:                                     # topo (só existe na altura cheia, aqui)
                c = top_leaf[py, px] if mt == LEAF else top_fixed[py, px]
            else:                                             # frente
                fz = LIFT - 1 - pz                            # linha da face (0 = em cima)
                if mt == POST:
                    if orient == "h":
                        left = px < 16
                        f = face_paint(5, False, True) if left else face_paint(5, True, False, ox=27)
                        c = f[fz, px if left else px - 27]
                    else:
                        c = face_paint(T, True, True)[fz, px]
                elif mt == HEADER:
                    c = rgb(FACE["trim"] if fz > 1 else FACE["trim_l"])
                    if fz == 3:
                        c = rgb(OUTLINE)
                else:                                         # folha
                    if orient == "h":
                        lw = 11 - retract
                        if px < 16:
                            f = _leaf_front(lw, FACE_H, seam_x=lw if retract == 0 else None, ox=0,
                                            ends=(False, retract > 0))
                            c = f[fz, px - 5]
                        else:
                            f = _leaf_front(lw, FACE_H, seam_x=0 if retract == 0 else None, ox=0,
                                            ends=(retract > 0, False))
                            c = f[fz, px - (16 + retract)]
                    else:
                        f = _leaf_front(T, FACE_H, seam_x=16, ends=(True, True), window=False)
                        c = f[fz, px]
            out[r, x] = c
    # contorno nos saltos de profundidade (ex.: borda da folha sobre a soleira) e na silhueta
    solid = out[:, :, 3] == 255
    add = np.zeros_like(solid)
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.full_like(depth, -1e9)
        ys = slice(max(ddy, 0), H + min(ddy, 0))
        yd = slice(max(-ddy, 0), H + min(-ddy, 0))
        xs = slice(max(ddx, 0), T + min(ddx, 0))
        xd = slice(max(-ddx, 0), T + min(-ddx, 0))
        nb[yd, xd] = depth[ys, xs]
        add |= solid & (nb - depth > 4)
    out[add] = rgb(OUTLINE)
    # LED do batente: verde aberta, vermelho fechada (no batente direito / no da frente)
    led = OK if k == n - 1 else (AMBER if k else ALERT)
    if orient == "h":
        out[LIFT + 8 + 4, 29] = rgb(led)
        out[LIFT + 8 + 4, 2] = rgb(led)
    else:
        out[LIFT + 27 - 24 + 6, 3] = rgb(led)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# v1.1 · PORTA FINA (pedido do dono): airlock de 2 folhas de metal grafite, finas (3 px), encostadas numa BORDA da
# parede, com a emenda em degrau no meio, o X em relevo em cada folha e a moldura de metal claro (2 batentes finos +
# travessa com a faixa laranja). O resto da espessura do tile é soleira com os batentes da parede (bege) dos lados.
# edge = a borda onde fica a folha: h → 'n' (fundo) ou 's' (frente); v → 'w' ou 'e'.
# ---------------------------------------------------------------------------------------------------------------------
GR = dict(hl="#9a9eb0", light="#6f7385", base="#4f5262", shade="#3d3f4d", dark="#2a2b36", ridge="#8a8ea0",
          groove="#30313d")
FR = dict(hl="#f1f3f8", light="#d9dde6", base="#b9bccb", shade="#8f92a6", dark="#6c6f84")
LEAF_L, LEAF_R, FRAME = 5, 6, 7
RETRACT_THIN = [0, 4, 7, 10]
SEAM_UP, SEAM_LO, Z_SPLIT, Z_LEAF = 17, 15, 10, 20       # emenda em degrau: x 17 em cima, x 15 embaixo


def _x_paint(u, v, w, h, mirror):
    """Folha grafite com o X em relevo: diagonal clara (crista) e a outra escura (sulco), chanfro na borda."""
    if mirror:
        u = w - 1 - u
    if v == 0 or u == 0:
        return GR["light"]
    if v == h - 1:
        return GR["dark"]
    if u == w - 1:
        return GR["shade"]
    d1 = u - v * (w - 1) / (h - 1)
    d2 = (w - 1 - u) - v * (w - 1) / (h - 1)
    if -0.5 <= d1 < 0.5:
        return GR["ridge"]
    if -0.5 <= d1 + 1 < 0.5:
        return GR["groove"]
    if -0.5 <= d2 < 0.5:
        return GR["groove"]
    if -0.5 <= d2 - 1 < 0.5:
        return GR["ridge"]
    return GR["base"]


def thin_door_frame(orient, edge, k):
    r = RETRACT_THIN[k]
    V = Vox()
    V.box(0, T, 0, T, -1, 0, SILL)
    if orient == "h":
        y0 = 0 if edge == "n" else T - 5                  # faixa da moldura (5 px); folha no miolo dela (3 px)
        V.box(0, 5, 0, T, 0, LIFT, POST)
        V.box(27, T, 0, T, 0, LIFT, POST)
        V.box(5, 7, y0, y0 + 5, 0, LIFT, FRAME)
        V.box(25, 27, y0, y0 + 5, 0, LIFT, FRAME)
        V.box(7, 25, y0, y0 + 5, Z_LEAF, LIFT, FRAME)
        ly = (y0 + 1, y0 + 4)
        V.box(7, SEAM_UP - r, *ly, Z_SPLIT, Z_LEAF, LEAF_L)
        V.box(7, SEAM_LO - r, *ly, 0, Z_SPLIT, LEAF_L)
        V.box(SEAM_UP + r, 25, *ly, Z_SPLIT, Z_LEAF, LEAF_R)
        V.box(SEAM_LO + r, 25, *ly, 0, Z_SPLIT, LEAF_R)
    else:
        x0 = 0 if edge == "w" else T - 6                  # na vertical a câmera vê só o topo: folha de 4 px, sem travessa
        V.box(0, T, 0, 5, 0, LIFT, POST)
        V.box(0, T, 27, T, 0, LIFT, POST)
        V.box(x0, x0 + 6, 5, 7, 0, LIFT, FRAME)
        V.box(x0, x0 + 6, 25, 27, 0, LIFT, FRAME)
        lx = (x0 + 1, x0 + 5)
        V.box(*lx, 7, SEAM_UP - r, 0, LIFT, LEAF_L)
        V.box(*lx, SEAM_UP + r, 25, 0, LIFT, LEAF_R)
    mat, face, P, depth = V.render()
    H = LIFT + T
    posts = np.zeros((T, T), bool)
    for x in range(T):
        for y in range(T):
            posts[y, x] = V.m[x, y, LIFT - 1 - V.Z0] == POST
    if orient == "h":
        top_post = _door_top_colors(posts, True, True, False, False)
    else:
        top_post = _door_top_colors(posts, False, False, True, True)
    sill = floor_tile(0)
    if orient == "h":                                     # trilho na linha da folha
        ty_ = y0 + 2
        for x in range(2, 30):
            sill[ty_, x] = rgb(FL["grate"])
            sill[ty_ + 1, x] = rgb(FL["light"])
    else:
        tx_ = x0 + 2
        for y in range(2, 30):
            sill[y, tx_] = rgb(FL["grate"])
            sill[y, tx_ + 1] = rgb(FL["light"])
    out = np.zeros((H, T, 4), np.uint8)
    for row in range(H):
        for x in range(T):
            mt, fc = mat[row, x], face[row, x]
            if fc == 0:
                continue
            px, py, pz = P[row, x]
            fz = LIFT - 1 - pz
            if mt == SILL:
                c = sill[py, px]
            elif mt == POST:
                if fc == 1:
                    c = top_post[py, px]
                elif orient == "h":
                    left = px < 16
                    f = face_paint(5, False, True) if left else face_paint(5, True, False, ox=27)
                    c = f[fz, px if left else px - 27]
                else:
                    c = face_paint(T, True, True)[fz, px]
            elif mt == FRAME:
                if fc == 1:
                    edge_px = (orient == "h" and py == y0) or (orient == "v" and px == x0)
                    c = rgb(FR["hl"] if edge_px else FR["light"])
                    if orient == "v" and py in (6, 25):
                        c = rgb(FR["shade"])
                else:
                    lintel = pz >= Z_LEAF
                    if lintel:
                        c = rgb([FR["hl"], FR["base"], ORANGE, FR["dark"]][min(fz, 3)])
                        if fz == 2 and px % 4 == 3:
                            c = rgb(FR["dark"])
                    else:
                        c = rgb({5: FR["hl"], 6: FR["light"], 25: FR["shade"], 26: FR["dark"]}.get(px, FR["shade"]))
                        if orient == "v":
                            c = rgb(FR["base"] if fz < 12 else FR["shade"])
            else:                                         # folhas
                if orient == "h":
                    if fc == 1:
                        c = rgb(GR["hl"] if py == ly[0] else GR["light"])
                    else:
                        upper = pz >= Z_SPLIT
                        v = (Z_LEAF - 1 - pz)                          # 0 em cima
                        hh = Z_LEAF
                        if mt == LEAF_L:
                            u = px - 7 + r
                            w = (SEAM_UP if upper else SEAM_LO) - 7
                            c = rgb(_x_paint(u, v, max(w, 10), hh, False))
                            if r == 0 and px == (SEAM_UP if upper else SEAM_LO) - 1:
                                c = rgb(OUTLINE)
                        else:
                            u = px - (SEAM_UP if upper else SEAM_LO) - r
                            w = 25 - (SEAM_UP if upper else SEAM_LO)
                            c = rgb(_x_paint(u + (10 - w if w < 10 else 0), v, max(w, 10), hh, False))
                        if r == 0 and pz == Z_SPLIT and SEAM_LO <= px < SEAM_UP:
                            c = rgb(OUTLINE)                           # o degrau da emenda
                else:
                    if fc == 1:                                        # topo da folha (o que se vê da vertical)
                        yy = py
                        c = rgb(GR["light"] if px == lx[0] else (GR["shade"] if px == lx[1] - 1 else GR["base"]))
                        if yy in (7, 8, 23, 24) and px in (lx[0] + 1, lx[0] + 2):
                            c = rgb(ORANGE)                            # pontas laranja (onde a folha encosta)
                        if r == 0 and yy == SEAM_UP - 1:
                            c = rgb(OUTLINE)
                        elif r == 0 and yy == SEAM_UP and px in (lx[0], lx[0] + 1):
                            c = rgb(OUTLINE)                           # o degrau da emenda visto de cima
                        elif r == 0 and yy == SEAM_UP - 2 and px in (lx[0] + 2, lx[0] + 3):
                            c = rgb(OUTLINE)
                    else:
                        c = rgb(GR["shade"])
            out[row, x] = c
    solid = out[:, :, 3] == 255
    add = np.zeros_like(solid)
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.full_like(depth, -1e9)
        ys = slice(max(ddy, 0), H + min(ddy, 0))
        yd = slice(max(-ddy, 0), H + min(-ddy, 0))
        xs = slice(max(ddx, 0), T + min(ddx, 0))
        xd = slice(max(-ddx, 0), T + min(-ddx, 0))
        nb[yd, xd] = depth[ys, xs]
        add |= solid & (nb - depth > 3)
    out[add] = rgb(OUTLINE)
    led = OK if k == 3 else (AMBER if k else ALERT)       # LED na travessa
    if orient == "h":
        zr = (y0 + 5) - LIFT + LIFT + 1                    # linha da frente da travessa (1 abaixo do topo)
        out[zr + 1, 16] = rgb(led)
    else:
        out[5, x0 + 3] = rgb(led)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# v1.2 · PORTA SOLO e PORTA DUPLA (feedback do dono: vão apertado). Sem batentes grossos: só a moldura fina (jambas de
# 2 px + travessa) na borda da parede; a folha some DENTRO da parede ao abrir e o vão fica quase o tile inteiro.
#   solo  (1 tile): 1 folha. Horizontal desliza pra ESQUERDA (oeste); vertical desliza pro NORTE (pra cima na tela,
#         entra na parede de trás). Regra única: a folha sempre corre pro lado de MENOR coordenada (−x / −y).
#   dupla (2 tiles): 2 folhas que se abrem do meio, cada uma pro seu lado; a emenda em degrau fica na junção dos tiles.
# Posição: edge = a borda onde fica a moldura/folha (h: 'n'/'s', v: 'w'/'e'). Padrão = variante B (borda de FORA).
# A cena inteira (1 ou 2 tiles) é montada no motor de voxels e cada pixel vai pro sprite do tile dono do voxel, então as
# duas metades da dupla se desenham cada uma na sua linha/coluna, como um tile comum (32×56 em (x, y − 24)).
# ---------------------------------------------------------------------------------------------------------------------
RETRACT_SOLO = [0, 10, 20, 28]
RETRACT_DUO = [0, 10, 20, 30]
JAMB = 2                     # jamba da moldura (ao longo da parede)
DEPTH_H, DEPTH_V = 5, 6      # espessura da moldura atravessando a parede (h, v)
STEP = 1                     # degrau da emenda: +1 px em cima, −1 px embaixo


def slide_door(orient, edge, n, k):
    """Devolve a lista de n sprites (32×56) do quadro k da porta (n = 1 solo, 2 dupla)."""
    L = n * T                                            # comprimento ao longo da parede
    r = (RETRACT_SOLO if n == 1 else RETRACT_DUO)[k]
    if orient == "h":
        V = Vox(X=L, Y=T)
        d0 = 0 if edge == "n" else T - DEPTH_H
        V.box(0, L, 0, T, -1, 0, SILL)
        V.box(0, JAMB, d0, d0 + DEPTH_H, 0, LIFT, FRAME)
        V.box(L - JAMB, L, d0, d0 + DEPTH_H, 0, LIFT, FRAME)
        V.box(JAMB, L - JAMB, d0, d0 + DEPTH_H, Z_LEAF, LIFT, FRAME)
        ly = (d0 + 1, d0 + 4)
    else:
        V = Vox(X=T, Y=L)
        d0 = 0 if edge == "w" else T - DEPTH_V
        V.box(0, T, 0, L, -1, 0, SILL)
        V.box(d0, d0 + DEPTH_V, 0, JAMB, 0, LIFT, FRAME)
        V.box(d0, d0 + DEPTH_V, L - JAMB, L, 0, LIFT, FRAME)
        ly = (d0 + 1, d0 + 5)
    a0, a1 = JAMB, L - JAMB                               # vão da moldura (ao longo da parede)
    zt = Z_LEAF if orient == "h" else LIFT
    leaves = []                                          # (mat, s0, s1, z0, z1) ao longo da parede
    if n == 1:
        leaves.append((LEAF_L, a0 - r, a1 - r, 0, zt))
    else:
        mid = L // 2
        for (z0, z1, st) in ((Z_SPLIT, zt, STEP), (0, Z_SPLIT, -STEP)) if orient == "h" else ((0, zt, 0),):
            leaves.append((LEAF_L, a0 - r, mid + st - r, z0, z1))
            leaves.append((LEAF_R, mid + st + r, a1 + r, z0, z1))
    for mt, s0, s1, z0, z1 in leaves:
        s0, s1 = max(s0, a0), min(s1, a1)
        if s1 <= s0:
            continue
        if orient == "h":
            V.box(s0, s1, *ly, z0, z1, mt)
        else:
            if n == 2:                                   # degrau visto de cima: metade da espessura +1, metade −1
                half = (ly[0] + ly[1]) // 2
                mid = L // 2
                for (x0, x1, st) in ((ly[0], half, STEP), (half, ly[1], -STEP)):
                    a = s0 if mt == LEAF_L else max(s0, mid + st + r)
                    b = min(s1, mid + st - r) if mt == LEAF_L else s1
                    if b > a:
                        V.box(x0, x1, a, b, z0, z1, mt)
            else:
                V.box(*ly, s0, s1, z0, z1, mt)
    H = LIFT + (T if orient == "h" else L)
    mat, face, P, depth = V.render(H=H)
    sill = np.concatenate([floor_tile(0)] * n, axis=1 if orient == "h" else 0)
    if orient == "h":
        for x in range(2, L - 2):
            sill[d0 + 2, x] = rgb(FL["grate"])
            sill[d0 + 3, x] = rgb(FL["light"])
    else:
        for y in range(2, L - 2):
            sill[y, d0 + 2] = rgb(FL["grate"])
            sill[y, d0 + 3] = rgb(FL["light"])
    W = L if orient == "h" else T
    out = np.zeros((H, W, 4), np.uint8)
    owner = np.full((H, W), -1)
    for row in range(H):
        for x in range(W):
            mt, fc = mat[row, x], face[row, x]
            if fc == 0:
                continue
            px, py, pz = P[row, x]
            owner[row, x] = (px if orient == "h" else py) // T
            fz = LIFT - 1 - pz
            along = px if orient == "h" else py
            if mt == SILL:
                c = sill[py, px]
            elif mt == FRAME:
                if fc == 1:
                    outer = (orient == "h" and py == d0) or (orient == "v" and px == d0)
                    c = rgb(FR["hl"] if outer else FR["light"])
                    if along in (0, L - 1):
                        c = rgb(FR["shade"])
                elif pz >= Z_LEAF and orient == "h":
                    c = rgb([FR["hl"], FR["base"], ORANGE, FR["dark"]][min(fz, 3)])
                    if fz == 2 and px % 4 == 3:
                        c = rgb(FR["dark"])
                elif orient == "h":
                    c = rgb({0: FR["hl"], 1: FR["light"], L - 2: FR["shade"], L - 1: FR["dark"]}.get(along, FR["base"]))
                else:                                             # frente da jamba na vertical (vista de frente)
                    c = rgb(FR["shade"] if fz < 18 else FR["dark"])
                    if px == d0:
                        c = rgb(FR["base"])
            else:
                if orient == "h":
                    if fc == 1:
                        c = rgb(GR["hl"] if py == ly[0] else GR["light"])
                    else:
                        v = Z_LEAF - 1 - pz
                        if n == 1:
                            c = rgb(_x_paint(px - a0 + r, v, a1 - a0, Z_LEAF, False))
                        elif mt == LEAF_L:
                            c = rgb(_x_paint(px - a0 + r, v, L // 2 - a0, Z_LEAF, False))
                        else:
                            c = rgb(_x_paint(px - L // 2 - r, v, a1 - L // 2, Z_LEAF, True))
                        if n == 2 and r == 0 and pz == Z_SPLIT and abs(px + 0.5 - L // 2) < STEP + 0.5:
                            c = rgb(OUTLINE)                       # o degrau da emenda
                        if n == 2 and r == 0 and mt == LEAF_L and V.m[px + 1, py, pz - V.Z0] == LEAF_R:
                            c = rgb(OUTLINE)
                else:
                    if fc == 1:
                        c = rgb(GR["light"] if px == ly[0] else (GR["shade"] if px == ly[1] - 1 else GR["base"]))
                        if py in (a0 - r, a0 + 1 - r) or (mt == LEAF_R and py in (a1 + r - 1, a1 + r - 2)) or                                 (n == 1 and py in (a1 - r - 1, a1 - r - 2)):
                            c = rgb(ORANGE) if ly[0] < px < ly[1] - 1 else c
                        if n == 2 and r == 0 and mt == LEAF_L and py + 1 < L and V.m[px, py + 1, pz - V.Z0] == LEAF_R:
                            c = rgb(OUTLINE)
                        # X em relevo achatado no topo da folha (2 diagonais curtinhas a cada 8 px)
                        rel = (py - a0 + r) if mt == LEAF_L else (py - a0 - r)
                        if ly[0] < px < ly[1] - 1 and rel % 8 in (3, 4) and (px - ly[0]) == (1 if rel % 8 == 3 else 2):
                            c = rgb(GR["ridge"])
                    else:
                        c = rgb(GR["shade"] if fz < 20 else GR["dark"])
            out[row, x] = c
    solid = out[:, :, 3] == 255
    add = np.zeros_like(solid)
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nb = np.full_like(depth, -1e9)
        ys = slice(max(ddy, 0), H + min(ddy, 0))
        yd = slice(max(-ddy, 0), H + min(-ddy, 0))
        xs = slice(max(ddx, 0), W + min(ddx, 0))
        xd = slice(max(-ddx, 0), W + min(-ddx, 0))
        nb[yd, xd] = depth[ys, xs]
        add |= solid & (nb - depth > 3)
    out[add] = rgb(OUTLINE)
    led = OK if k == 3 else (AMBER if k else ALERT)
    if orient == "h":
        out[LIFT + d0 + 5 - LIFT + 1, L // 2 - (0 if n == 2 else 0)] = rgb(led)   # na frente da travessa, no meio
        if n == 2:
            out[LIFT + d0 + 5 - LIFT + 1, L // 2 - 1] = rgb(led)
    else:
        out[LIFT - LIFT + 0 + 1 + LIFT - 24, d0 + 3] = rgb(led)                     # no topo da jamba de trás
    sprites = []
    for t in range(n):
        sp = np.zeros((LIFT + T, T, 4), np.uint8)
        if orient == "h":
            blk, own = out[:, t * T:(t + 1) * T], owner[:, t * T:(t + 1) * T]
        else:
            blk, own = out[t * T:t * T + LIFT + T], owner[t * T:t * T + LIFT + T]
        m = own == t
        sp[m] = blk[m]
        sprites.append(sp)
    return sprites


def slide_strip(orient, edge, n):
    """Tira: n = 1 → 128×56 (quadros 0..3); n = 2 → 256×56 (metade 1 nos quadros 0..3, depois a metade 2)."""
    frames = [slide_door(orient, edge, n, k) for k in range(4)]
    cols = [frames[k][t] for t in range(n) for k in range(4)]
    return np.concatenate(cols, axis=1)


# ---------------------------------------------------------------------------------------------------------------------
# Aviso de vazamento: parede-fantasma vermelha piscando no tile furado (32×56, em (x, y − 24), desenhada por cima)
# ---------------------------------------------------------------------------------------------------------------------
def leak_frame(on):
    H = LIFT + T
    a = np.zeros((H, T, 4), np.uint8)
    red, red_d, wht = (ALERT, "#a8323a", "#ffd0c8") if on else ("#a8323a", "#6e1e2a", None)

    def p(x, y, c):
        if 0 <= x < T and 0 <= y < H:
            a[y, x] = rgb(c)

    def rect_line(x0, y0, x1, y1, c, dash=None):
        for x in range(x0, x1 + 1):
            for y in (y0, y1):
                if dash is None or ((x + y) // dash) % 2 == 0:
                    p(x, y, c)
        for y in range(y0, y1 + 1):
            for x in (x0, x1):
                if dash is None or ((x + y) // dash) % 2 == 0:
                    p(x, y, c)

    # caixa do bloco: topo (0..31) e face (32..55), cantoneiras grossas
    for (x0, y0, x1, y1) in ((1, 1, 30, 31), (1, 32, 30, 54)):
        rect_line(x0 - 1, y0 - 1, x1 + 1, y1 + 1, OUTLINE)
        rect_line(x0, y0, x1, y1, red, dash=None if on else 3)
        rect_line(x0 + 1, y0 + 1, x1 - 1, y1 - 1, OUTLINE)
    for (cx, cy, sx, sy) in ((1, 1, 1, 1), (30, 1, -1, 1), (1, 54, 1, -1), (30, 54, -1, -1)):
        for t in range(5):
            p(cx + sx * t, cy + sy, red)
            p(cx + sx, cy + sy * t, red)
    # hachura na face
    for y in range(34, 53):
        for x in range(3, 29):
            if (x + y) % 6 in (0, 1) and on:
                p(x, y, red_d)
            elif (x + y) % 6 == 0:
                p(x, y, red_d)
    if on:                              # triângulo de alerta com "!" no meio do topo
        tri = ["......K......",
               ".....KRK.....",
               "....KRRRK....",
               "....KRWRK....",
               "...KRRWRRK...",
               "...KRRWRRK...",
               "..KRRRWRRRK..",
               "..KRRRRRRRK..",
               ".KRRRRWRRRRK.",
               ".KRRRRRRRRRK.",
               "KKKKKKKKKKKKK"]
        pal = {"K": OUTLINE, "R": red, "W": "#ffffff"}
        for j, row in enumerate(tri):
            for i, ch in enumerate(row):
                if ch != ".":
                    p(10 + i, 10 + j, pal[ch])
        # setinhas de ar saindo pros lados (o O₂ vazando)
        for (x, y) in ((3, 17), (4, 16), (4, 18), (5, 17), (6, 17)):
            p(x, y, CYAN_L)
        for (x, y) in ((28, 17), (27, 16), (27, 18), (26, 17), (25, 17)):
            p(x, y, CYAN_L)
    else:
        for (x, y) in ((15, 15), (16, 15), (15, 16), (16, 16), (15, 18), (16, 18)):
            p(x, y, red)
    return a


# ---------------------------------------------------------------------------------------------------------------------
# Dispersor de O₂ (r3d, família das máquinas): sapata B (meia-largura 12, como o painel solar), corpo bege baixo com a
# cápsula de água encaixada na frente, pescoço de metal e a cabeça difusora: anel de respiros, ventoinha no tampo e
# o anel ciano que acende quando sopra. Os sopros (anéis de ar) são pixel chapado por cima.
# ---------------------------------------------------------------------------------------------------------------------
DW, DH = 32, 48
P_RING_ON = [Pal([c] * 5, emit=True, emit_tone=0) for c in (CYAN_L, CYAN, CYAN_L, "#ffffff")]
P_RING_OFF = Pal(["#2f4a5c"] * 5, emit=True, emit_tone=0)
P_RING_LEAK = [Pal([c] * 5, emit=True, emit_tone=0) for c in (AMBER, "#b8823c", AMBER, "#b8823c")]
P_WATER_LO = Pal(["#6f9fb8", "#3f7690", "#2f5f78", "#24485c", "#1a3444"])


def _disp_body_paint(th, z, cap):
    out = np.zeros(len(th), int)
    if np.all(cap):
        return out
    out[(z > 13.6) & (z < 15.2)] = 1                                  # faixa laranja
    d = M.ang_dist(th, M.FRONT)
    out[(d < 0.66) & (z > 6.0) & (z < 13.4)] = 2                      # moldura da janela da cápsula
    out[(d < 0.48) & (z > 7.0) & (z < 12.4)] = 3                      # a cápsula (água)
    return out


def dispenser(f=0, state="on"):
    """state: 'on' (soprando, vedado), 'leak' (soprando fraco, LED âmbar), 'off' (parado).
    Corpo bege baixo com a cápsula de água na janela da frente; em cima, a cabeça difusora em 3 aletas (discos bege
    empilhados) com as frestas acesas em ciano quando sopra; domo com a pontinha laranja."""
    sc = M.scene(DW, DH, -M.SAP_D)
    M.sapata(sc, 12)
    water = M.P_WATER if state != "off" else P_WATER_LO
    sc.cyl(0, 0, 9.0, M.SAP_H, 16, M.P_BEIGE, paint=_disp_body_paint, extra=(M.P_ORANGE, M.P_METAL, water))
    sc.cyl(0, 0, 9.4, 15.6, 16.8, M.P_METAL)                                    # aro do tampo do corpo
    if state == "on":
        glow = P_RING_ON[f % 4]
    elif state == "leak":
        glow = P_RING_LEAK[f % 4]
    else:
        glow = P_RING_OFF
    # cabeça: a grade acesa (por onde o ar sai, em volta toda, com as nervuras escuras) e o chapéu por cima
    rib = lambda t, z, c: np.where(~c & (((t * 10 / (2 * math.pi)) % 1.0) < 0.3), 1, 0)   # noqa: E731
    sc.cyl(0, 0, 8.6, 16.8, 23.0, glow, paint=rib, extra=(M.P_DARK,))
    sc.cyl(0, 0, 9.6, 23.0, 24.2, M.P_METAL)                                    # aba do chapéu
    sc.cyl(0, 0, 9.2, 24.2, 26.6, M.P_BEIGE, r_top=4.2)                         # chapéu
    sc.cyl(0, 0, 1.6, 26.6, 28.2, M.P_ORANGE)                                   # pino
    # tubo da cápsula (tampinhas de metal em cima e embaixo da janela)
    sc.box((-2.4, 2.4), (-10.2, -8.6), (12.2, 13.6), M.P_METAL)
    sc.box((-2.4, 2.4), (-10.2, -8.6), (5.6, 7.0), M.P_METAL)
    led = {"on": OK, "leak": AMBER if f % 2 == 0 else "#7a5a1e", "off": ALERT}[state]
    sc.dot(6.4, -7.6, 10.5, led, always=True)
    cv = M.render(sc)
    if state != "off":
        _puffs(cv, f, weak=state == "leak")
    return cv


def _puffs(cv, f, weak=False):
    """Sopros: bolinhas de ar saindo das frestas da cabeça pros dois lados e subindo, crescendo e clareando
    (chapado, branco → ciano claro). 4 quadros em loop; cada lado com a fase trocada."""
    shapes = [[(0, 0), (1, 0), (0, 1), (1, 1)],
              [(0, -1), (1, -1), (-1, 0), (2, 0), (-1, 1), (2, 1), (0, 2), (1, 2)],
              [(0, -1), (1, -1), (-1, 0), (2, 0), (-1, 1), (2, 1), (0, 2), (1, 2)],
              [(0, -1), (2, 0), (-1, 1), (1, 2)]]
    cols = ["#ffffff", "#ffffff", CYAN_L, "#9fe0f5"]
    tracks = [(-1, 22, 0), (1, 21, 2), (-1, 20, 2), (1, 22, 0)] if not weak else [(-1, 22, 0), (1, 21, 2)]
    for side, y0, ph in tracks:
        k = (f + ph) % 4
        if weak and k >= 2:
            continue
        cx = DW // 2 - 1 + side * (11 + k)
        cy = y0 - k * 3
        for (px, py) in shapes[k]:
            x, y = cx + px * side, cy + py
            if 0 <= x < DW and 0 <= y < DH and cv.a[y, x, 3] == 0:
                cv.px(x, y, cols[k])


# ---------------------------------------------------------------------------------------------------------------------
# Ícones 16×16 (padrão dos icon_* aprovados: contorno #1b1630, cores chapadas, luz de cima-esquerda)
# ---------------------------------------------------------------------------------------------------------------------
def _icon(rows, pal):
    cv = M.Canvas(16, 16)
    cv.draw_map([r.ljust(16, ".") for r in rows], pal)
    cv.outline()
    return cv


def icon_base_floor():
    """Chapa do chão em 3/4: tampo com chanfro, emenda, 2 rebites e a espessura da placa embaixo."""
    rows = [
        "................",
        "................",
        "................",
        "..hLLLLLLLLLLL..",
        "..LBBBBBBBBBBd..",
        "..LBrBBBBBBrBd..",
        "..LBBBBBBBBBBd..",
        "..LBBBBBBBBBBd..",
        "..ddddddddddds..",
        "..LBBBBBBBBBBd..",
        "..LBrBBBBBBrBd..",
        "..LBBBBBBBBBBd..",
        "..sssssssssssk..",
        "..OOOOOOOOOOOk..",
        "................",
        "................",
    ]
    pal = {"h": FL["hl"], "L": FL["light"], "B": FL["base"], "d": FL["shade"], "s": FL["dark"], "r": FL["rivet"],
           "k": FL["seam"], "O": "#3b374d"}
    return _icon(rows, pal)


def icon_base_wall():
    """Bloco de parede: topo ardósia (aba clara em cima e à esquerda, antiderrapante no miolo), a aba clara do
    encontro com a face, face bege com o respiro, a faixa laranja e o rodapé escuro."""
    rows = [
        "................",
        "................",
        ".hhhhhhhhhhhhhh.",
        ".hcccccccccccca.",
        ".hcpppptpppppaa.",
        ".hcpptppppptpaa.",
        ".llllllllllllll.",
        ".mmmmmmmmmmmmmm.",
        ".WPPPPPPPPPPPPw.",
        ".WPPPvvvvvPPPPw.",
        ".WPPPPPPPPPPPPw.",
        ".oOOOOOOOOOOOOd.",
        ".kkrkkkkkkkkrkk.",
        ".KKKKKKKKKKKKKK.",
        "................",
        "................",
    ]
    pal = {"h": TOP["hl"], "c": TOP["cap"], "p": TOP["plate"], "t": TOP["tread"], "a": TOP["dark"],
           "l": TOP["lip"], "m": FACE["trim"], "W": FACE["hi"], "P": FACE["panel"], "w": FACE["low2"],
           "v": FACE["vent_d"], "o": ORANGE_L, "O": ORANGE, "d": ORANGE_D, "k": FACE["plinth"],
           "K": FACE["plinth_d"], "r": FACE["rivet"]}
    return _icon(rows, pal)


def _door_icon_pal():
    return {"F": FR["light"], "f": FR["shade"], "H": FR["hl"], "O": ORANGE, "d": FR["dark"], "r": ALERT, "g": GR["ridge"],
            "b": GR["base"], "s": GR["shade"], "l": GR["light"], "K": OUTLINE, "S": FL["base"], "L": FL["light"]}


def icon_base_door():
    """Porta solo (v1.2): moldura de metal claro com a travessa listrada de laranja e o LED, a folha grafite única com
    o X em relevo, e a soleira embaixo."""
    rows = [
        "................",
        "................",
        "..HHHHHHHHHHHH..",
        "..FOdOdOdrdOdF..",
        "..FddddddddddF..",
        "..Hlllllllllls..",
        "..Hlgbbbbbbgbs..",
        "..Hlbgbbbbgbbs..",
        "..Hlbbggggbbbs..",
        "..Hlbbggggbbbs..",
        "..Hlbgbbbbgbbs..",
        "..Hlgbbbbbbgbs..",
        "..Hssssssssssf..",
        "..LLLLLLLLLLLL..",
        "................",
        "................",
    ]
    return _icon(rows, _door_icon_pal())


def icon_base_door_double():
    """Porta dupla (v1.2): moldura larga, duas folhas grafite com o X, a emenda em degrau no meio e o LED na travessa."""
    rows = [
        "................",
        "................",
        ".HHHHHHHHHHHHH..",
        ".FOdOdOrrOdOdF..",
        ".FdddddddddddF..",
        ".HlllllKllllls..",
        ".HlgbbgKlgbbgs..",
        ".HlbggbKlbggbs..",
        ".HlbggKllbggbs..",
        ".HlbggKlbggbbs..",
        ".HlgbbKlgbbgbs..",
        ".HlbbbKlbbbbbs..",
        ".HssssKssssssf..",
        ".LLLLLLLLLLLLL..",
        "................",
        "................",
    ]
    return _icon(rows, _door_icon_pal())


def icon_o2_dispenser():
    """O Dispersor em miniatura: chapéu bege com o pino laranja, a grade acesa em ciano com as nervuras, o corpo bege
    com a janela da cápsula (água azul) e a sapata metálica com os pés laranja; duas bolhas de ar saindo."""
    rows = [
        "................",
        ".o...........o..",
        "o.o....p....o.o.",
        ".o...hWWWb...o..",
        "....hWWWWWWb....",
        "...mmmmmmmmmm...",
        "...CkCkCkCkCk...",
        "...CkCkCkCkCk...",
        "....OOOOOOOO....",
        "....WWmmmmWb....",
        "....WWwAAAWb....",
        "....WWAAAAWb....",
        "...MMMMMMMMMM...",
        "...DDDDDDDDDD...",
        "...oo......oo...",
        "................",
    ]
    pal = {"o": CYAN_L, "p": ORANGE, "h": "#ffffff", "W": "#efe6d4", "b": "#a99a8c", "m": "#7d7892",
           "C": CYAN, "k": "#2e2a3a", "O": ORANGE, "w": "#d8f6ff", "A": "#4aa8d8", "M": "#a7a3b8", "D": "#58536b"}
    cv = M.Canvas(16, 16)
    body = [r.replace("o", ".") if i < 4 else r for i, r in enumerate(rows)]
    cv.draw_map(body, pal)
    cv.outline()
    for y, r in enumerate(rows[:4]):                       # bolhas por fora do contorno
        for x, ch in enumerate(r):
            if ch == "o":
                cv.px(x, y, CYAN_L)
    for (x, y) in ((3, 14), (4, 14), (11, 14), (12, 14)):  # pés laranja da sapata
        cv.px(x, y, ORANGE)
    return cv


# ---------------------------------------------------------------------------------------------------------------------
def _cv(arr):
    c = M.Canvas(arr.shape[1], arr.shape[0])
    c.a = arr.copy()
    return c


def strip_arr(frames):
    return np.concatenate(frames, axis=1)


def build():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for v in range(4):
        out[f"base_floor_{v}.png"] = _cv(floor_tile(v))
    out["base_wall_top.png"] = _cv(wall_top_atlas())
    out["base_wall_face.png"] = _cv(wall_face_strip())
    for o, edges in (("h", "ns"), ("v", "we")):
        for e in edges:
            out[f"base_door_{o}_{e}.png"] = _cv(slide_strip(o, e, 1))
            out[f"base_door2_{o}_{e}.png"] = _cv(slide_strip(o, e, 2))
    out["machine_o2_dispenser.png"] = dispenser(0, "off")
    out["anim/anim_machine_o2_dispenser.png"] = M.strip([dispenser(f, "on") for f in range(4)])
    out["anim/anim_machine_o2_dispenser_leak.png"] = M.strip([dispenser(f, "leak") for f in range(4)])
    out["leak_blink.png"] = _cv(strip_arr([leak_frame(True), leak_frame(False)]))
    out["icon_base_floor.png"] = icon_base_floor()
    out["icon_base_wall.png"] = icon_base_wall()
    out["icon_base_door.png"] = icon_base_door()
    out["icon_base_door_double.png"] = icon_base_door_double()
    out["icon_o2_dispenser.png"] = icon_o2_dispenser()
    for name, cv in out.items():
        cv.save(PEND / name)
    ant = REP / "anterior"                               # v1.0 · porta grossa (reprovada), só pra comparar
    for o in ("h", "v"):
        _cv(strip_arr([door_frame(o, k) for k in range(4)])).save(ant / f"base_door_{o}.png")
    for o, edges in (("h", "ns"), ("v", "we")):                # v1.1 · porta fina A/B (reprovada: vão apertado)
        for e in edges:
            _cv(strip_arr([thin_door_frame(o, e, k) for k in range(4)])).save(ant / f"fina_base_door_{o}_{e}.png")
    for old in ("base_door_h.png", "base_door_v.png"):
        if (PEND / old).exists():
            (PEND / old).unlink()
    return out


if __name__ == "__main__":
    o = build()
    for k, cv in o.items():
        print(f"{k}: {cv.w}×{cv.h}")
    if "--no-report" not in sys.argv:
        import v05_m2_base_report as REP_
        print(REP_.build())
