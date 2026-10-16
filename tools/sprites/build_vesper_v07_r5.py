#!/usr/bin/env python3
"""Hesper v0.7 M4 · rodada 5: props com mais volume (r3d). Cilindros de pé com tampo elíptico, racks girados mostrando
frente + lateral, cama de parede que sai da parede (prop `desk`), mesa/armário/estação/cadeira com cantos arredondados e
uniformes com forma. Sufixo _r5; a rodada 4 não é sobrescrita. Rode depois do build_vesper_v07_r4.py.

Saída: reports/design/v07_m4/pendentes/<id>_r5.png, icon_<id>_r5.png ; reports/design/v07_m4/sala_r5_{cabine,alojamento}_{clara,escura}.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chests_r3d as CH  # noqa: E402
import build_vesper_v07 as V  # noqa: E402
import build_vesper_v07_r2 as R2  # noqa: E402
import build_vesper_v07_r3 as R3  # noqa: E402
import build_vesper_v07_r4 as R4  # noqa: E402
from r3d import Pal, Scene  # noqa: E402

PEND, REP, T, OUT = V.PEND, V.REP, V.T, V.OUT
SL, SLD, CR, OR, TANK, SCR = R4.SL, R4.SLD, R4.CR, R4.OR, R4.TANK, R4.SCR
LEDR, LEDO, GO, CAB_R, CAB_B = R4.LEDR, R4.LEDO, R4.GO, R4.CAB_R, R4.CAB_B
SPEC = Pal(["#ffffff"] * 5, emit=True, emit_tone=0)
TANK2 = Pal(["#f6f4fa", "#d4d0e0", "#a49fbd", "#756f92", "#4e4a68"])
MATT = Pal(["#ffffff", "#eceaf2", "#d6d2e2", "#b0abc4", "#7d7894"])


class K(R4.K):
    def rbox(self, c, h, r, pal, **kw):
        if "pivot" in kw and kw["pivot"] is not None:
            kw["pivot"] = self._t(kw["pivot"])
        self.sc.rbox(self._t(c), self._t(h), r * self.k, pal, **kw)


class G:
    """Grupo girado em z: peças em coordenadas locais (x, y, z) do gabinete, giradas por `ang` em volta de (ox, oy)."""

    def __init__(self, s, ang, ox=0.0, oy=0.0):
        self.s, self.a, self.ox, self.oy = s, ang, ox, oy
        self.c, self.sn = math.cos(ang), math.sin(ang)

    def w(self, p):
        return (self.ox + p[0] * self.c - p[1] * self.sn, self.oy + p[0] * self.sn + p[1] * self.c, p[2])

    def box(self, c, h, pal, rot=0.0, **kw):
        self.s.obox(self.w(c), h, pal, rot_z=self.a + rot, **kw)

    def tube(self, pts, r, pal):
        self.s.tube([self.w(p) for p in pts], r, pal)


def render(model, size, k, detail, front_y):
    sc = CH.scene(size[0], size[1], front_y * k)
    model(K(sc, k), detail)
    cv = sc.render()
    CH.check(cv, "x", size)
    return cv


# ---- cilindros de O₂: 3 de pé, com tampo elíptico, brilho vertical, válvula ---------------------------------------
def tank(s, cx, cy, h, r, d):
    def paint(th, z, cap):
        idx = np.zeros(len(th), int)
        idx[(np.abs(th - 3.75) < 0.2)] = 1
        idx[(z > h * 0.42) & (z < h * 0.42 + 2.4) & ~cap] = 2
        return idx
    s.cyl(cx, cy, r, 0, h, TANK2, paint=paint if d else None, extra=(SPEC, OR))
    s.sphere((cx, cy, h), r, TANK2)
    s.cyl(cx, cy, 1.8, h + r * 0.8, h + r + 1.6, SLD)
    s.box((cx - 0.9, cx + 0.9), (cy - 0.9, cy + 0.9), (h + r + 1.6, h + r + 2.8), SL)
    s.box((cx - 2.8, cx + 2.8), (cy - 0.5, cy + 0.5), (h + r + 2.8, h + r + 3.7), OR)      # volante da válvula


def m_cyl5(s, d):
    s.cyl(0, 0, 14, 0, 1.2, SLD)                                                          # base de chapa
    for (cx, cy, h) in ((-7.4, 2.6, 19), (7.4, 2.6, 19), (0, -3.6, 17)):
        tank(s, cx, cy, h, 4.7, d)
    s.box((-12, 12), (6.4, 7.4), (5, 8), SLD)                                               # barra de fixação


# ---- racks: gabinete girado (frente + lateral) com gavetas em volume ----------------------------------------------
def rack_common(s, g, d, ledon=2):
    hx, hy, hz = 8, 6, 15

    def side(L, face):
        idx = np.zeros(len(L), int)
        if face in (0, 1):
            z = L[:, 2]
            fr = (z / 3.0) - np.floor(z / 3.0)
            idx[(fr < 0.35) & (np.abs(L[:, 1]) < 4.2) & (z > 3) & (z < 27)] = 1
        return idx
    g.box((0, 0, hz), (hx, hy, hz), SL, paint=side if d else None, extra=(SCR,))
    g.box((0, 0, 2 * hz + 0.7), (hx + 0.7, hy + 0.7, 0.7), SLD)
    g.box((0, 0, 0.8), (hx + 0.7, hy + 0.7, 0.8), SLD)
    return hx, hy, hz


def m_rack5(s, d):
    g = G(s, 0.5)
    hx, hy, hz = rack_common(s, g, d)
    for i in range(6):
        z = 3.6 + i * 4.6
        g.box((0, -hy - 0.5, z), (6.6, 0.9, 1.9), SLD if i % 2 else SL)
        g.box((2.2, -hy - 1.5, z), (2.4, 0.35, 0.5), SL)
        g.box((-4.6, -hy - 1.5, z), (0.8, 0.4, 0.8), LEDO if i == 2 else LEDR)
        g.box((-1.4, -hy - 1.4, z + 0.3), (1.2, 0.3, 0.3), SCR)
    for x in (-7.3, 7.3):
        g.box((x, -hy - 0.2, hz), (0.7, 0.5, hz - 1), SL)


def m_rack_open5(s, d):
    g = G(s, 0.5)
    hx, hy, hz = 8, 6, 15
    g.box((0, hy - 0.7, hz), (hx, 0.7, hz), SLD)
    g.box((-hx + 0.7, 0, hz), (0.7, hy, hz), SL)
    g.box((hx - 0.7, 0, hz), (0.7, hy, hz), SL)
    g.box((0, 0, 2 * hz - 0.7), (hx, hy, 0.7), SL)
    g.box((0, 0, 0.7), (hx, hy, 0.7), SLD)
    g.box((0, 0, 2 * hz + 0.7), (hx + 0.7, hy + 0.7, 0.7), SLD)
    g.box((0, 1.5, hz), (hx - 1.4, hy - 2, hz - 1.6), SCR)
    for i, pull in enumerate((0, 3.5, 0.8, 5.5, 1.5)):
        z = 4.2 + i * 5.4
        g.box((0, -hy + 4.4 - pull - 1.2, z), (6.4, 3.6, 1.9), SLD if i % 2 else SL)
        g.box((-4.4, -hy + 0.8 - pull - 1.2, z), (0.8, 0.4, 0.8), LEDO if i == 3 else LEDR)
    # porta aberta em ângulo (articulada na quina da frente à esquerda)
    hinge = (-hx, -hy - 0.4)
    beta = -1.9
    half = 7.0
    cen = (hinge[0] + half * math.cos(beta) * 0.5 * 2 * 0.5, hinge[1] + half * math.sin(beta) * 0.5 * 2 * 0.5)
    cen = (hinge[0] + (half / 2) * math.cos(beta), hinge[1] + (half / 2) * math.sin(beta))
    g.box((cen[0], cen[1], hz), (half / 2, 0.7, hz - 0.4), SL, rot=beta)
    g.box((cen[0], cen[1] - 0.3, hz), (half / 2 - 1, 0.3, hz - 3), SLD, rot=beta)
    g.tube([(-3, -hy + 2, 20), (-4, -hy - 3.5, 14), (-2, -hy - 6, 5), (2, -hy - 8, 0.9)], 0.9, CAB_R)
    g.tube([(2, -hy + 2, 9), (4, -hy - 3, 5), (6, -hy - 6, 0.9)], 0.9, CAB_B)
    g.tube([(5, -hy + 2, 26), (7.5, -hy - 1.5, 21), (8.4, -hy - 2.5, 13)], 0.8, GO)


# ---- cama de parede: sai da parede (prop desk, encostado ao norte) ------------------------------------------------
def m_bunk5(s, d):
    # parede ao norte (y+): placa de fixação com a cama de cima dobrada pra cima, encostada nela
    s.box((-14, 14), (6.4, 8), (1, 33), SLD)
    s.box((-14, 14), (6.2, 6.6), (31.4, 33), SL)
    s.rbox((0, 4.6, 24.5), (11.6, 1.4, 6.6), 1.0, SL)                                        # estrado dobrado
    s.rbox((0, 3.0, 24.5), (10.6, 0.9, 5.8), 0.8, OR)                                        # o lado do colchão, laranja
    s.box((-13.5, 13.5), (6.0, 6.5), (12.4, 13.6), OR) if False else None
    # a cama de baixo, aberta pra frente: estrado + colchão grosso + travesseiro + cobertor
    s.rbox((0, -1.4, 8.4), (13, 8, 1.4), 1.0, SL)
    s.rbox((0, -1.2, 11.4), (12, 7.4, 2.0), 1.6, MATT)
    s.rbox((2.5, -0.6, 13.2), (9, 6.4, 1.1), 1.0, OR)
    s.rbox((-8, 3.4, 13.4), (3.8, 2.6, 1.2), 1.0, CR)
    # braços/correntes: da parede até as quinas da frente da cama (e pés dobráveis)
    for sx in (-12.2, 12.2):
        s.tube([(sx, 6.0, 20), (sx, -2, 14.5), (sx, -8, 9.4)], 0.6, GO)
        s.tube([(sx, 6.0, 9), (sx, -7.5, 8.6)], 0.8, SLD)
        s.box((sx - 0.7, sx + 0.7), (-8.4, -6.8), (0, 8.4), SLD)                             # pé articulado


# ---- mesa de comando, armário, estação, cadeira (com cantos arredondados) -------------------------------------------
def m_table5(s, d):
    s.cyl(0, 0, 12, 0, 1.6, SLD)
    s.cyl(0, 0, 8.5, 1.6, 9.5, SL, paint=(lambda th, z, c: np.where((z > 4) & (z < 5.6) & ~c, 1, 0)) if d else None, extra=(OR,))
    s.rbox((0, 0, 11.4), (26, 8.4, 2.2), 1.8, SL,
           paint=(lambda L, N: np.where((N[:, 2] > 0.85) & (np.abs(L[:, 0]) < 22.5) & (np.abs(L[:, 1]) < 4.6), 1, 0)) if d else None,
           extra=(SCR,))
    s.rbox((0, -6.4, 14.4), (14, 2.2, 1.0), 0.8, SLD, rot_x=0.0)
    for i, x in enumerate((-11, -7, -3, 1, 5, 9)):
        s.dot(x, -8.8, 15.0, "#ffb04a" if i == 3 else "#7a2a36")
    s.cyl(0, 0, 4.4, 13.4, 14.4, SLD)
    s.cyl(0, 0, 2.6, 14.4, 14.9, SCR)
    s.cyl(0, 0, 8.6, 13.7, 13.9, SCR) if False else None
    for (x, y, z) in ((-3, 0, 19), (1, 1, 22), (3, -1, 17), (-1, 2, 25), (5, 0, 21), (-6, 1, 15)):
        s.dot(x, y, z, "#4f86a8")


def m_locker5(s, d):
    s.rbox((0, 0, 14), (8, 5, 14), 1.2, SL)
    s.box((-6.2, 6.2), (-5.2, -4.8), (1.8, 26.2), SCR)
    s.rbox((0, -5.2, 10.5), (4.6, 1.5, 6.5), 1.4, CR)
    s.sphere((0, -5.2, 21), 3.6, CR)
    s.box((-2.4, 2.4), (-5.3, -4.3), (18.6, 20.6), SCR)
    s.box((-4.8, 4.8), (-6.0, -4.3), (9.5, 10.8), OR)
    s.box((-3.8, -0.6), (-5.8, -4.4), (1.8, 4.5), CR)
    s.box((0.6, 3.8), (-5.8, -4.4), (1.8, 4.5), CR)
    s.obox((-6.9, -8.8, 14), (4, 0.6, 13.2), SL, rot_z=-1.3)


def m_ws5(s, d):
    s.rbox((0, 0, 5), (12, 6, 5), 1.2, SL, paint=(lambda L, N: np.where((N[:, 1] < -0.85) & (L[:, 2] > 0.5) & (L[:, 2] < 2.8), 1, 0)) if d else None, extra=(OR,))
    s.cyl(0, 2, 2, 10, 13, SLD)
    s.rbox((0, 2, 18.5), (8.2, 1.6, 5.4), 1.0, SL, rot_x=0.12, pivot=(0, 2, 13))
    s.box((-6.6, 6.6), (0.3, 0.8), (14, 22.6), SCR) if False else None
    s.rbox((0, 0.35, 18.8), (6.9, 0.5, 4.4), 0.4, SCR, rot_x=0.12, pivot=(0, 2, 13))
    for i in range(4):
        s.box((-5, 3 - i * 0.0), (-0.1, 0.1), (17 + i * 1.8, 17.5 + i * 1.8), DIM) if False else None
    s.rbox((0, -4, 10.8), (6.2, 2.6, 0.7), 0.5, SLD)
    for x in (-4, -1, 2, 5):
        s.dot(x, -4.6, 11.8, "#8f94b4")
    s.cyl(9.5, -2.5, 1.5, 10, 13.2, OR)


def m_chair5(s, d):
    s.cyl(0, 0, 5.6, 0, 1.2, SLD)
    s.cyl(0, 0, 1.4, 1.2, 6, SLD)
    s.rbox((0, 0, 7.6), (6.8, 6, 1.7), 1.5, OR)
    s.rbox((0, 4.6, 15.5), (5.9, 1.8, 7.5), 1.5, SL)
    s.rbox((0, 4.2, 22.6), (4.4, 1.9, 2.4), 1.4, OR)
    for sx in (-8, 8):
        s.rbox((sx, -0.5, 10.5), (1.0, 4.6, 1.0), 0.8, SLD)
        s.box((sx - 0.5, sx + 0.5), (-0.5, 0.5), (6, 10), SLD)


MODELS = {"prop_o2_cylinders": (m_cyl5, (32, 40), -9.8, 0.5),
          "prop_server_rack": (m_rack5, (32, 40), -9, 0.38),
          "prop_server_rack_open": (m_rack_open5, (32, 40), -13, 0.34),
          "prop_wall_bunk": (m_bunk5, (32, 40), -9, 0.4),
          "prop_command_table": (m_table5, (64, 40), -8.5, 0.27),
          "prop_suit_locker": (m_locker5, (32, 40), -8, 0.42),
          "prop_workstation": (m_ws5, (32, 40), -7, 0.5),
          "prop_pilot_chair": (m_chair5, (32, 40), -7, 0.5)}


# ---- uniformes: macacão aberto, manga, gola, bota e capacete do lado -------------------------------------------------
def uniforms5():
    f = V.Img(32, 32)
    cr, crd, orn, ornd, bot = "#eceaf2", "#b9b4c9", "#e2733a", "#a9482a", "#3a3d56"
    f.poly([(5, 15), (18, 14), (21, 23), (17, 25)], crd)                                   # perna direita
    f.poly([(5, 15), (12, 15), (11, 26), (6, 26)], cr)                                     # perna esquerda
    f.rect(6, 26, 11, 28, bot); f.rect(6, 26, 8, 26, "#6a6f90")                            # botas
    f.poly([(17, 24), (21, 23), (23, 26), (18, 27)], bot)
    f.poly([(6, 6), (16, 5), (18, 15), (5, 16)], cr)                                       # tronco
    f.poly([(12, 5), (16, 5), (18, 15), (13, 15)], crd)
    f.poly([(9, 6), (13, 6), (11, 12)], orn)                                               # camiseta laranja no V
    f.line(11, 12, 11, 15, "#8f8aa6")                                                      # zíper aberto
    f.poly([(7, 4), (14, 3), (15, 6), (8, 7)], crd)                                        # gola
    f.line(8, 4, 14, 3, "#ffffff")
    f.poly([(6, 6), (2, 9), (1, 15), (4, 16), (5, 11)], cr)                                # manga dobrada
    f.poly([(1, 13), (4, 14), (4, 16), (1, 15)], orn)                                      # punho laranja
    f.poly([(16, 5), (22, 6), (27, 11), (25, 14), (20, 10), (17, 9)], crd)                 # manga esticada
    f.poly([(23, 10), (27, 11), (26, 13), (24, 13)], orn)
    f.px(8, 11, "#ffd23a"); f.px(9, 11, "#ffd23a")                                         # remendo de nome
    V_ = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    V_.alpha_composite(f.im)
    f.im = V_
    R4.outline_img(f)
    # capacete ao lado (esfera r3d pequena)
    sc = Scene(12, 12, ground=10)
    sc.sphere((0, 0, 4.2), 4.4, CR)
    sc.box((-3, 3), (-5, -3.2), (3.2, 5.6), SCR)
    h = sc.render().image().convert("RGBA")
    f.im.alpha_composite(h, (19, 19))
    return f.im


def render_all():
    img, icons = {}, {}
    for pid, (model, size, fy, ik) in MODELS.items():
        cv = render(model, size, 1.0, True, fy)
        im = R4.finish(cv, size, shw=(size[0] - 4))
        im.save(PEND / f"{pid}_r5.png")
        ic = render(model, (16, 16), ik, False, fy)
        ic.image().save(PEND / f"icon_{pid}_r5.png")
        img[pid] = im
    u = uniforms5()
    u.save(PEND / "prop_uniforms_r5.png")
    img["prop_uniforms"] = u
    ic = V.Img(16, 16)
    ic.im.alpha_composite(u.resize((16, 16), Image.NEAREST)) if False else None
    small = V.Img(16, 16)
    small.poly([(3, 3), (8, 2), (9, 8), (3, 9)], "#eceaf2")
    small.poly([(3, 9), (9, 8), (10, 13), (6, 14)], "#b9b4c9")
    small.poly([(3, 3), (1, 6), (2, 9), (3, 8)], "#eceaf2")
    small.poly([(8, 2), (13, 5), (12, 8), (9, 6)], "#b9b4c9")
    small.rect(4, 4, 6, 5, "#e2733a")
    small.rect(11, 10, 14, 13, "#eceaf2"); small.rect(12, 11, 14, 12, "#2c3a52")
    R4.outline_img(small)
    small.im.save(PEND / "icon_prop_uniforms_r5.png")
    img["prop_container_stack"] = Image.open(PEND / "prop_container_stack.png").convert("RGBA")
    return img


def rooms(img):
    sp = dict(top=Image.open(PEND / "hull_wall_top.png").convert("RGBA"), face=Image.open(PEND / "hull_wall_face.png").convert("RGBA"),
              floor=[Image.open(PEND / f"hull_floor_{i}.png").convert("RGBA") for i in range(4)])
    light = Image.open(PEND / "vesper_emergency_light_A.png").convert("RGBA")
    cable = Image.open(PEND / "wall_cable_panel.png").convert("RGBA")
    old = R4.scene_room
    # a montagem usa nomes "sala_r4_*": gerar com o mesmo código e renomear
    old(sp, 8, {(3, 0): cable, (7, 0): light},
        [(img["prop_command_table"], 3, 3), (img["prop_server_rack"], 1, 1), (img["prop_server_rack"], 2, 1),
         (img["prop_server_rack_open"], 3, 1), (img["prop_workstation"], 6, 1), (img["prop_pilot_chair"], 6, 2),
         (img["prop_pilot_chair"], 4, 4)], [], (4 * T + 16, 3 * T + 40),
        [(1 * T + 16, 2 * T + 30, 14, (.6, .35, .05)), (2 * T + 16, 2 * T + 30, 14, (.6, .35, .05))], "r5tmp_cabine")
    old(sp, 8, {(5, 0): light},
        [(img["prop_wall_bunk"], 2, 1), (img["prop_wall_bunk"], 3, 1), (img["prop_wall_bunk"], 6, 1),
         (img["prop_suit_locker"], 7, 5), (img["prop_o2_cylinders"], 7, 3), (img["prop_container_stack"], 1, 5)],
        [(img["prop_uniforms"], 3, 4), (img["prop_uniforms"], 5, 5)], (4 * T + 16, 3 * T + 40),
        [(5 * T + 16, 24 + 22, 30, (.7, .08, .08))], "r5tmp_alojamento")
    for n in ("cabine", "alojamento"):
        for t in ("clara", "escura"):
            (REP / f"sala_r4_r5tmp_{n}_{t}.png").replace(REP / f"sala_r5_{n}_{t}.png")


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    img = render_all()
    for pid in list(MODELS) + ["prop_uniforms"]:
        size = Image.open(PEND / f"{pid}_r5.png").size
        assert Image.open(PEND / f"icon_{pid}_r5.png").size == (16, 16)
    rooms(img)
    print("ok")


if __name__ == "__main__":
    main()
