#!/usr/bin/env python3
"""v0.7 M4 · destroços maiores · RODADA 2: robô R-2 e ARCA-2 em ISOMÉTRICO (2 candidatas de cada).

    python3 tools/sprites/build_wrecks_v07_m4_r2.py
    ->  reports/design/v07_m4_destrocos/pendentes/wreck_{robot,liner}_r2_{A,B}.png

Mesma projeção 2:1 da VÉSPER e da base: P(u,v,z) = (x0 + u − v, y0 + (u+v)/2 − z). Aqui o desenho é um mini
renderizador com z-buffer: cada peça (caixa, cilindro, chapa, tubo) vira pontos 3D com normal; a luz (de cima e do
lado esquerdo) escolhe o tom numa rampa curta de cores chapadas (2–5 faixas), o z-buffer resolve quem tapa quem
(inclusive o casco aberto da ARCA, onde se vê a parede de dentro, as costelas e as poltronas), e no fim entram a
linha escura onde uma peça passa na frente da outra e o contorno #1b1630. Sem anti-aliasing, alpha 0/255 (+ sombra 92).
Determinístico (hash fixo).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v07_lib import Cv, OUT, SHADOW, hsh, sand_pile, scatter  # noqa: E402
from v07_r2_destrocos import FONT  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PEND = ROOT / "reports" / "design" / "v07_m4_destrocos" / "pendentes"

FONT2 = dict(FONT, A=["010", "101", "111", "101", "101"], C=["111", "100", "100", "100", "111"],
             **{"2": ["111", "001", "111", "100", "111"]})


def rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def ramp(*hs):
    return np.array([rgb(h) for h in hs], dtype=np.int32)


CREAM = ramp("#fbf7ec", "#efe7d4", "#e3d9c3", "#cfc4ab", "#b3a78d", "#8e7f73")
LAVR = ramp("#d9dbe8", "#b9bccf", "#8f93ad", "#6b6f8c", "#4f5270")
ORR = ramp("#f29a62", "#e2733a", "#c85a2a", "#a8471f")
TEALR = ramp("#8fe0ee", "#59d0e6", "#2b9fb8", "#1f7690")
METR = ramp("#c8cdd4", "#9aa2ab", "#6b717a", "#4a4f57", "#3b3f46")
RUBR = ramp("#5a6069", "#4a4f57", "#3b3f46", "#2a2d33", "#1f2126")
GLR = ramp("#c8f6ff", "#59d0e6", "#2b9fb8", "#1d4a66", "#16203a")
SOLR = ramp("#9cc0ff", "#5b86d0", "#3d63a8", "#27468a", "#1f3a6e")
INTR = ramp("#5a4a5a", "#4a3a4a", "#3a3040", "#2c2634", "#221d2a")
RUSTR = ramp("#c8794a", "#b0663f", "#8a4e34", "#5e3526")
SANDR = ramp("#b3a393", "#a39385", "#8e7f73", "#796b61")
WOODR = ramp("#d9a066", "#c98a56", "#9a5a3a", "#6c4030")
BAGS = [ramp("#7f89ad", "#626b8e", "#4b5273", "#363b58"), ramp("#e2733a", "#c85a2a", "#a8471f", "#7a3418"),
        ramp("#7fd67a", "#4aa860", "#2f7a44", "#1f5a30"), ramp("#f2c46d", "#d9a24a", "#a87830", "#7a5420"),
        ramp("#b9bccf", "#8f93ad", "#6b6f8c", "#4f5270"), ramp("#c98a56", "#9a5a3a", "#6c4030", "#4a2a20")]

LD = np.array([-0.3, 0.45, 0.85])
LD = LD / np.linalg.norm(LD)
CAM = np.array([1.0, 1.0, 1.0]) / math.sqrt(3)


def toneidx(l, n):
    t = np.clip((l + 0.3) / 1.2, 0, 1)
    return np.clip(np.round((1 - t) * (n - 1)).astype(int), 0, n - 1)


def rot(axis, ang):
    c, s = math.cos(ang), math.sin(ang)
    if axis == "u":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "v":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def inpoly(x, y, poly):
    inside = np.zeros(x.shape, bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        cond = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        inside ^= cond
        j = i
    return inside


class ZR:
    """Pontos 3D com cor -> imagem com z-buffer. Transformação atual (M, t) aplicada em tudo que entra."""

    def __init__(self, W, H, x0, y0, g=1.0, clip=False):
        self.W, self.H, self.x0, self.y0, self.g = W, H, x0, y0, g
        self.clip = clip                      # r3: descarta o que ficou abaixo do chão (z < 0), ex. o nariz enterrado
        self.parts = []
        self.M, self.t = np.eye(3), np.zeros(3)
        self.stack = []
        self.oid = 0

    # transformações (pivô em coordenadas do mundo atual)
    def push(self, M=None, pivot=(0, 0, 0), move=(0, 0, 0)):
        self.stack.append((self.M, self.t))
        p = np.array(pivot, float)
        M = np.eye(3) if M is None else M
        # novo = Matual·(M·(x − p) + p + move) + tatual
        self.t = self.M @ (p - M @ p + np.array(move, float)) + self.t
        self.M = self.M @ M

    def pop(self):
        self.M, self.t = self.stack.pop()

    def light(self, N):
        return (N @ self.M.T) @ LD

    def faces_cam(self, N):
        return (N @ self.M.T) @ CAM

    def emit(self, P, C, oid=None):
        if len(P) == 0:
            return
        P = (P @ self.M.T + self.t) * self.g
        if self.clip:
            k = P[:, 2] >= -0.3
            P, C = P[k], np.asarray(C)[k]
            if len(P) == 0:
                return
        x = np.floor(self.x0 + P[:, 0] - P[:, 1] + .5).astype(int)
        y = np.floor(self.y0 + (P[:, 0] + P[:, 1]) / 2 - P[:, 2] + .5).astype(int)
        d = P.sum(1)
        self.oid += 1
        self.parts.append((x, y, d, np.asarray(C, np.int32), np.full(len(x), self.oid if oid is None else oid)))

    def render(self):
        x = np.concatenate([p[0] for p in self.parts]); y = np.concatenate([p[1] for p in self.parts])
        d = np.concatenate([p[2] for p in self.parts]); C = np.concatenate([p[3] for p in self.parts])
        I = np.concatenate([p[4] for p in self.parts])
        ok = (x >= 0) & (x < self.W) & (y >= 0) & (y < self.H)
        x, y, d, C, I = x[ok], y[ok], d[ok], C[ok], I[ok]
        pid = y * self.W + x
        order = np.lexsort((d, pid))
        ps = pid[order]
        last = np.r_[ps[1:] != ps[:-1], True]
        sel = order[last]
        img = np.zeros((self.H, self.W, 4), np.uint8)
        dep = np.full((self.H, self.W), -1e9)
        ids = np.full((self.H, self.W), -1)
        img[y[sel], x[sel], :3] = C[sel]
        img[y[sel], x[sel], 3] = 255
        dep[y[sel], x[sel]] = d[sel]
        ids[y[sel], x[sel]] = I[sel]
        return img, dep, ids


def edge_lines(img, dep, ids, ink, thr=5.0):
    """Linha escura de 1 px no pixel de trás onde uma peça da frente encosta (o 'borda de chapa' do estilo)."""
    H, W = dep.shape
    op = img[:, :, 3] == 255
    mark = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        q = np.full((H, W), -1e9)
        qi = np.full((H, W), -1)
        ys, yd = slice(max(0, dy), H + min(0, dy)), slice(max(0, -dy), H + min(0, -dy))
        xs, xd = slice(max(0, dx), W + min(0, dx)), slice(max(0, -dx), W + min(0, -dx))
        q[yd, xd] = dep[ys, xs]
        qi[yd, xd] = ids[ys, xs]
        mark |= op & (q > dep + thr) & (qi != ids)
    out = img.copy()
    out[mark, :3] = rgb(ink)
    return out


# ---- primitivas -----------------------------------------------------------------------------------------------------
STEP = .42


def grid(La, Lb, step=STEP):
    s = np.arange(0, La + 1e-6, step)
    t = np.arange(0, Lb + 1e-6, step)
    S, Tt = np.meshgrid(s, t)
    return S.ravel(), Tt.ravel()


def quad(zr, o, a, b, fn, two_sided=True, oid=None):
    """Retângulo o + s·â + t·b̂, s∈[0,|a|], t∈[0,|b|]. fn(s, t, l) -> (cores Nx3, keep)."""
    o, a, b = (np.array(v, float) for v in (o, a, b))
    La, Lb = np.linalg.norm(a), np.linalg.norm(b)
    s, t = grid(La, Lb)
    N = np.cross(a, b); N /= np.linalg.norm(N)
    if two_sided and zr.faces_cam(N[None])[0] < 0:
        N = -N
    l = np.full(len(s), zr.light(N[None])[0])
    C, keep = fn(s, t, l)
    P = o + np.outer(s / La, a) + np.outer(t / Lb, b)
    zr.emit(P[keep], C[keep], oid)


def plain(R, hi=True, wear=0.0, seed=0, shift=0):
    """Textura padrão de face: tom pela luz, realce na borda de cima (t alto) e sujeira."""
    def fn(s, t, l):
        idx = toneidx(l, len(R)) + shift
        if hi:
            top = t >= t.max() - .9
            idx = np.where(top, idx - 1, idx)
        if wear:
            h = np.array([hsh(int(a), int(b), seed) for a, b in zip(s * 1.0, t * 1.0)])
            idx = np.where(h > 1 - wear, idx + 1, idx)
        idx = np.clip(idx, 0, len(R) - 1)
        return R[idx], np.ones(len(s), bool)
    return fn


def box(zr, u0, u1, v0, v1, z0, z1, R, fns=None, wear=.06, seed=0, sides="all"):
    """Caixa. fns = {"top": fn, "v": fn, "u": fn, ...} pra texturas próprias; o resto usa `plain`."""
    fns = fns or {}
    du, dv, dz = u1 - u0, v1 - v0, z1 - z0
    F = {"top": ((u0, v0, z1), (du, 0, 0), (0, dv, 0)), "v": ((u0, v1, z0), (du, 0, 0), (0, 0, dz)),
         "u": ((u1, v0, z0), (0, dv, 0), (0, 0, dz)), "v0": ((u0, v0, z0), (du, 0, 0), (0, 0, dz)),
         "u0": ((u0, v0, z0), (0, dv, 0), (0, 0, dz)), "bot": ((u0, v0, z0), (du, 0, 0), (0, dv, 0))}
    for k in (F if sides == "all" else sides):
        o, a, b = F[k]
        quad(zr, o, a, b, fns.get(k) or plain(R, hi=k != "top", wear=wear, seed=seed + len(k)))


def cyl(zr, c, axis, L, rfun, fn, th=(0, 2 * math.pi), inner=False, step=STEP, oid=None):
    """Cilindro ao longo de `axis` ('u','v','z') a partir do centro c, comprimento L, raio rfun(s) (s ao longo do eixo).
    fn(s, th, l, N) -> (cores, keep). inner=True: só a parede de DENTRO do lado de trás (aparece pelos buracos)."""
    c = np.array(c, float)
    ax = {"u": np.array([1., 0, 0]), "v": np.array([0, 1., 0]), "z": np.array([0, 0, 1.])}[axis]
    e1 = {"u": np.array([0, 1., 0]), "v": np.array([1., 0, 0]), "z": np.array([1., 0, 0])}[axis]
    e2 = {"u": np.array([0, 0, 1.]), "v": np.array([0, 0, 1.]), "z": np.array([0, 1., 0])}[axis]
    S, TH = [], []
    for s in np.arange(0, L + 1e-6, step):
        r = rfun(s)
        if r <= 0:
            continue
        n = max(8, int((th[1] - th[0]) * r / step) + 1)
        a = np.linspace(th[0], th[1], n)
        S.append(np.full(n, s)); TH.append(a)
    s, a = np.concatenate(S), np.concatenate(TH)
    r = np.array([rfun(v) for v in s])
    dr = np.array([(rfun(min(L, v + .5)) - rfun(max(0, v - .5))) for v in s])
    radial = np.outer(np.cos(a), e1) + np.outer(np.sin(a), e2)
    N = radial - np.outer(dr, ax)
    N /= np.linalg.norm(N, axis=1)[:, None]
    P = c + np.outer(s, ax) + radial * r[:, None]
    if inner:
        N = -N
        vis = zr.faces_cam(N) > 0
        P = c + np.outer(s, ax) + radial * (r - 1.2)[:, None]
    else:
        vis = np.ones(len(s), bool)
    C, keep = fn(s, a, zr.light(N), N)
    keep &= vis
    zr.emit(P[keep], C[keep], oid)


def disc(zr, c, axis, r, fn, ring=None, oid=None):
    """Tampa redonda virada pro +axis. fn(rho, th, l) -> (cores, keep)."""
    c = np.array(c, float)
    ax = {"u": np.array([1., 0, 0]), "v": np.array([0, 1., 0]), "z": np.array([0, 0, 1.])}[axis]
    e1 = {"u": np.array([0, 1., 0]), "v": np.array([1., 0, 0]), "z": np.array([1., 0, 0])}[axis]
    e2 = {"u": np.array([0, 0, 1.]), "v": np.array([0, 0, 1.]), "z": np.array([0, 1., 0])}[axis]
    x, y = grid(2 * r, 2 * r)
    x, y = x - r, y - r
    keep = x * x + y * y <= r * r
    x, y = x[keep], y[keep]
    rho, th = np.hypot(x, y), np.arctan2(y, x)
    C, k2 = fn(rho, th, np.full(len(x), zr.light(ax[None])[0]))
    P = c + np.outer(x, e1) + np.outer(y, e2)
    zr.emit(P[k2], C[k2], oid)


def plate_poly(zr, o, a, b, poly, fn, thick=0.0, dark=None, oid=None):
    """Chapa plana: polígono em coordenadas (s,t) do plano o + s·â + t·b̂ (â, b̂ unitários). thick: lâmina de baixo."""
    o, a, b = (np.array(v, float) for v in (o, a, b))
    a /= np.linalg.norm(a); b /= np.linalg.norm(b)
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    s, t = grid(max(xs) - min(xs), max(ys) - min(ys))
    s, t = s + min(xs), t + min(ys)
    k = inpoly(s, t, poly)
    s, t = s[k], t[k]
    N = np.cross(a, b); N /= np.linalg.norm(N)
    if zr.faces_cam(N[None])[0] < 0:
        N = -N
    l = np.full(len(s), zr.light(N[None])[0])
    C, keep = fn(s, t, l)
    P = o + np.outer(s, a) + np.outer(t, b)
    if thick:
        zr.emit(P[keep] - N * thick, np.tile(np.array(rgb(dark)), (keep.sum(), 1)), oid)
    zr.emit(P[keep], C[keep], oid)


def tube(zr, pts, r, R, oid=None):
    """Cabo/haste: esferinhas ao longo de uma polilinha 3D (cor pela luz)."""
    P, C = [], []
    for (a, b) in zip(pts, pts[1:]):
        a, b = np.array(a, float), np.array(b, float)
        L = np.linalg.norm(b - a)
        for s in np.arange(0, L + 1e-6, .35):
            c = a + (b - a) * s / L
            for th in np.linspace(0, 2 * math.pi, 10, endpoint=False):
                for ph in (-0.9, 0, 0.9):
                    n = np.array([math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph), math.sin(ph)])
                    P.append(c + n * r); C.append(n)
    P, N = np.array(P), np.array(C)
    idx = toneidx(zr.light(N), len(R))
    zr.emit(P, R[idx], oid)


def mound(zr, uc, vc, ru, rv, h, seed=0):
    """Montinho de areia (domo achatado) no chão."""
    s, t = grid(2 * ru, 2 * rv)
    du, dv = (s - ru) / ru, (t - rv) / rv
    k = du * du + dv * dv <= 1
    du, dv = du[k], dv[k]
    z = h * (1 - du * du - dv * dv)
    N = np.stack([2 * h * du / ru, 2 * h * dv / rv, np.ones(len(du))], 1)
    N /= np.linalg.norm(N, axis=1)[:, None]
    idx = toneidx(zr.light(N), len(SANDR))
    sp = np.array([hsh(int(a * 7), int(b * 7), seed) for a, b in zip(du, dv)]) > .8
    idx = np.clip(np.where(sp, idx - 1, idx), 0, len(SANDR) - 1)
    P = np.stack([uc + du * ru, vc + dv * rv, z], 1)
    zr.emit(P, SANDR[idx])


def finish(W, H, zr, ink, ground=None):
    """Sombra + chão (ground(cv)) + render com z-buffer + linhas internas + contorno."""
    cv = Cv(W, H)
    if ground:
        ground(cv)
    img, dep, ids = zr.render()
    img = edge_lines(img, dep, ids, ink)
    base = np.array(cv.im)
    op = img[:, :, 3] == 255
    base[op] = img[op]
    cv.im = Image.fromarray(base)
    from PIL import ImageDraw
    cv.d = ImageDraw.Draw(cv.im)
    cv.outline()
    cv.check()
    return cv


# =====================================================================================================================
# ROBÔ R-2 (estilo "robozinho simpático"): corpo-caixa, esteiras dos 2 lados, cabeça binocular num pescoço, braços
# dobrados, painel solar no lombo. Ele olha pra +v (a face clara). 96×72 · pegada 3×2 · lift 8 · caixa (3,1).
# =====================================================================================================================
ROBOT_R2 = dict(size=(3, 2), sprite=(96, 72), lift=8, crate=(3, 1))
INK_R = "#2a2440"


def track(zr, u0, u1, v0, v1, h, near):
    """Esteira ao longo de v (frente = +v): faces laterais em 'estádio' com rodas, piso com sapatas."""
    r = h / 2
    poly = []
    for a in np.linspace(-math.pi / 2, math.pi / 2, 9):
        poly.append((v1 - r + r * math.cos(a), r + r * math.sin(a)))
    for a in np.linspace(math.pi / 2, 3 * math.pi / 2, 9):
        poly.append((v0 + r + r * math.cos(a), r + r * math.sin(a)))
    hubs = [(v0 + r, r), ((v0 + v1) / 2, r * .9), (v1 - r, r)]

    def side(s, t, l):
        idx = toneidx(l, len(RUBR))
        rim = np.zeros(len(s), bool)
        hub = np.zeros(len(s), bool); cen = np.zeros(len(s), bool)
        for (hv, hz) in hubs:
            d = np.hypot(s - hv, t - hz)
            hub |= d < r * .62; cen |= d < r * .25
        out = RUBR[np.clip(idx, 0, 4)].copy()
        out[hub] = METR[1]; out[cen] = METR[3]
        hl = hub & (t > np.array([hz for _, hz in hubs]).mean() + r * .3)
        out[hl] = METR[0]
        return out, np.ones(len(s), bool)
    for u in ((u1,) if near else (u0, u1)):
        plate_poly(zr, (u, 0, 0), (0, 1, 0), (0, 0, 1), poly, side)
    # sapatas: superfície em volta (cilindro "achatado" aproximado por caixa + 2 meios cilindros)
    def tread(s, th, l, N):
        idx = toneidx(l, len(RUBR))
        bar = (np.floor(th * r / 1.6) % 2 == 0)
        return RUBR[np.clip(np.where(bar, idx + 1, idx), 0, 4)], np.ones(len(s), bool)
    for (vc, ths) in ((v1 - r, (-math.pi / 2, math.pi / 2)), (v0 + r, (math.pi / 2, 3 * math.pi / 2))):
        # cilindro ao longo de u, seção no plano (v,z): reaproveita cyl com eixo u
        cyl(zr, (u0, vc, r), "u", u1 - u0, lambda s: r, tread, th=ths)

    def topf(s, t, l):
        idx = toneidx(l, len(RUBR))
        bar = (np.floor(t / 1.6) % 2 == 0)
        return RUBR[np.clip(np.where(bar, idx + 1, idx), 0, 4)], np.ones(len(s), bool)
    quad(zr, (u0, v0 + r, h), (u1 - u0, 0, 0), (0, v1 - v0 - 2 * r, 0), topf)


def robot_r2(variant="A"):
    W, H = ROBOT_R2["sprite"]
    zr = ZR(W, H, 45, 39, g=1.16)
    B = variant == "B"

    def ground(cv):
        cv.shadow_ell(47, 60, 31, 7)
        sand_pile(cv, 43, 62, 27, 5, 6 if not B else 9)
        scatter(cv, [(4, 64), (14, 66), (74, 65), (84, 62), (62, 66), (8, 57)], 12)
    if B:   # tombado pro lado direito (+u), a esteira da direita afundada na areia
        zr.push(rot("v", math.radians(13)), pivot=(21, 10, -1.5))
    # esteiras
    track(zr, -5, -1, 0, 22, 10, near=False)
    track(zr, 17, 21, 0, 22, 10, near=True)
    # corpo-caixa (frente = +v): creme, faixa laranja, grade de "boca" e escotilha
    def front(s, t, l):        # face +v: s = u (0..16), t = z (0..13)
        idx = toneidx(l, len(CREAM))
        out = CREAM[idx].copy()
        band = (t > 7.5) & (t < 9.5)
        out[band] = ORR[1]; out[band & (t > 9)] = ORR[0]
        gr = (s > 3) & (s < 13) & (t > 1.5) & (t < 6.5)
        out[gr] = np.where((np.floor(t[gr]) % 2 == 0)[:, None], METR[3], METR[2])
        hi = t >= 12.2
        out[hi] = CREAM[0]
        dust = np.array([hsh(int(a * 2), int(b * 2), 31) for a, b in zip(s, t)]) > .9
        out[dust & ~gr & ~band] = CREAM[4]
        return out, np.ones(len(s), bool)

    def side(s, t, l):         # face +u: s = v (0..16), t = z
        idx = toneidx(l, len(CREAM))
        out = CREAM[idx].copy()
        band = (t > 7.5) & (t < 9.5)
        out[band] = ORR[2]
        # "R-2" na lateral
        for i, ch in enumerate("R-2"):
            for j, row in enumerate(FONT2[ch]):
                for k, b in enumerate(row):
                    if b == "1":
                        m = (s >= 2 + (i * 4 + k)) & (s < 3 + (i * 4 + k)) & (t <= 6 - j) & (t > 5 - j)
                        out[m] = rgb("#4a4260")
        hi = t >= 12.2
        out[hi] = CREAM[2]
        return out, np.ones(len(s), bool)

    def topc(s, t, l):
        idx = toneidx(l, len(CREAM))
        out = CREAM[idx].copy()
        dust = np.array([hsh(int(a * 2), int(b * 2), 41) for a, b in zip(s, t)]) > .7
        out[dust] = rgb("#d9c7ae")
        return out, np.ones(len(s), bool)
    box(zr, 0, 16, 2, 18, 8, 21, CREAM, fns={"v": front, "u": side, "top": topc})
    # parafusos nos cantos da frente
    for (u, z) in ((1, 9), (15, 9), (1, 20), (15, 20)):
        box(zr, u - .5, u + .5, 18, 18.6, z - .5, z + .5, METR, sides=("v",))
    # painel solar no lombo (levantado atrás)
    zr.push(rot("u", math.radians(-14)), pivot=(8, 4, 21.5))
    def sol(s, t, l):
        out = np.tile(SOLR[2], (len(s), 1))
        cell = (np.floor(s / 3.5) + np.floor(t / 3.2)) % 2 == 0
        out[cell] = SOLR[1]
        gridl = (s % 3.5 < .45) | (t % 3.2 < .45)
        out[gridl] = SOLR[4]
        gl = np.array([hsh(int(a * 3), int(b * 3), 5) for a, b in zip(s, t)]) > .93
        out[gl] = SOLR[0]
        if B:
            crack = np.abs((s - 2) - (t - 1) * 1.6) < .5
            out[crack & (s < 9)] = rgb("#c8f6ff")
        return out, np.ones(len(s), bool)
    box(zr, 1, 15, 3, 13, 21.5, 22.5, METR, fns={"top": sol})
    zr.pop()
    # pescoço
    tube(zr, [(8, 9, 21), (8, 9, 25.5)], 1.2, METR)
    # cabeça binocular (cai pra frente na B)
    if B:
        zr.push(rot("u", math.radians(24)), pivot=(8, 9, 25))
    box(zr, 2.5, 13.5, 7, 11.5, 25, 30, CREAM, fns={"top": topc})
    box(zr, 5.8, 10.2, 11.5, 12.5, 26.5, 28.5, METR)                     # ponte entre as lentes
    for (cu, cracked, dead) in ((4.3, variant == "A", False), (11.7, B, B)):
        def ring(s, th, l, N):
            return METR[toneidx(l, len(METR))], np.ones(len(s), bool)
        cyl(zr, (cu, 11, 27.6), "v", 3.2, lambda s: 3.1, ring)
        def lens(rho, th, l, cracked=cracked, dead=dead):
            out = np.tile(GLR[4 if dead else 3], (len(rho), 1))
            out[rho < 2.2] = GLR[3 if dead else 2]
            out[rho > 2.6] = METR[3]
            glint = (rho < 1.4) & (th > 1.2) & (th < 2.6)
            if not dead:
                out[glint] = GLR[0]
            if cracked:
                c1 = (np.abs(np.sin(th - .6)) < .22) | (np.abs(np.sin(th + 1.0)) < .18)
                out[c1 & (rho > .5) & (rho < 2.6)] = rgb("#e6fbff")
            return out, np.ones(len(rho), bool)
        disc(zr, (cu, 14.2, 27.6), "v", 3.1, lens)
    zr.pop() if B else None
    # braços pequenos dobrados na frente (A: os dois juntos; B: o da esquerda caído)
    for (u, hang) in ((-0.5, B), (16.5, False)):
        tube(zr, [(u, 8, 15), (u, 13, 14), (u, 18, 11 if not hang else 6)], .9, METR)
        box(zr, u - 1.2, u + 1.2, 18, 21, (10 if not hang else 4.5), (12 if not hang else 6.5), METR)
        box(zr, u - 1.2, u - .4, 21, 22.5, (10 if not hang else 4.5), (11 if not hang else 5.5), METR)
        box(zr, u + .4, u + 1.2, 21, 22.5, (10 if not hang else 4.5), (11 if not hang else 5.5), METR)
    # antena com LED
    tube(zr, [(14, 4, 21), (15, 3, 33)], .45, METR)
    box(zr, 14.2, 16.2, 2, 4, 33, 35, ramp("#ff8a7a", "#ff5a4a", "#c83a2a", "#8a2a20"))
    if B:
        zr.pop()
        mound(zr, 23, 11, 5, 13, 3.2, 3)                                   # areia cobrindo a esteira afundada
    # caixote de amostras caído e roda solta
    zr.push(rot("z", math.radians(18)), pivot=(31, 7, 0))
    box(zr, 28, 34, 4, 10, 0, 5, ramp("#9fa8c8", "#7f89ad", "#626b8e", "#4b5273", "#363b58"))
    zr.pop()
    for (u, v, c) in ((24, 13, "#7fd67a"), (27, 17, "#59d0e6"), (-12, 8, "#f2c46d")):
        box(zr, u, u + 4, v, v + 1.6, 0, 1.6, ramp("#e6e9ef", "#d9dde6", "#a9b0be", "#8c93a3"))
        box(zr, u + 1, u + 3, v + 1.6, v + 1.8, .3, 1.3, ramp(c, c, c), sides=("v",))
    if not B:
        tube(zr, [(-12, 14, 0.6), (-9, 20, 0.6)], .6, RUBR)                # pedaço de sapata
    else:
        def wheel(rho, th, l):
            out = np.tile(RUBR[3], (len(rho), 1)); out[rho < 2.4] = METR[1]; out[rho < 1] = METR[3]
            return out, np.ones(len(rho), bool)
        disc(zr, (-13, 16, .8), "z", 4, wheel)
    cv = finish(W, H, zr, INK_R, ground)
    cv.meta = dict(ROBOT_R2)
    return cv


# =====================================================================================================================
# ARCA-2 (nave de colonos) em iso: cilindro creme de nariz redondo, faixa, fileira de vigias, cabine; uma parte do
# casco DESMONTADA DE PROPÓSITO (chapas tiradas, costelas à mostra, cabos puxados pra fora, chapas empilhadas no
# chão), bagagem e caixas dos colonos espalhadas. 288×208 · pegada 9×4 · lift 80 · caixa (3,4).
# =====================================================================================================================
LINER_R2 = dict(size=(9, 4), sprite=(288, 208), lift=80, crate=(3, 4))
INK_L = "#3a3550"


def liner_r2(variant="A"):
    W, H = LINER_R2["sprite"]
    B = variant == "B"
    zr = ZR(W, H, 48, 94)
    L, R = 176, 24
    zc = R - 3
    STRIPE = TEALR if B else ORR
    # trecho desmontado (u0, u1, th0, th1): A no meio, B a metade de trás quase toda
    cut = (66, 102, 0.22, 2.5) if not B else (88, 140, 0.18, 2.6)
    cell_u, cell_t = 9, 0.42
    keep_cells = {(1, 3), (3, 0)} if not B else {(0, 4), (4, 1), (2, 4)}

    def rfun(s):
        if s < 30:
            return R * math.sqrt(max(0, 1 - ((30 - s) / 30) ** 2)) * .92 + R * .08 * (s / 30)
        if s > 150:
            return R - (s - 150) * .34
        return R

    def removed(s, th):
        u0, u1, t0, t1 = cut
        inr = (s >= u0) & (s < u1) & (th >= t0) & (th < t1)
        cu = np.floor((s - u0) / cell_u).astype(int)
        ct = np.floor((th - t0) / cell_t).astype(int)
        kept = np.zeros(len(s), bool)
        for (a, b) in keep_cells:
            kept |= (cu == a) & (ct == b)
        return inr & ~kept

    def skin(s, th, l, N):
        th = np.where(th > math.pi, th - 2 * math.pi, th)          # −π..π, 0 = lado de quem olha (+v)
        r = np.array([rfun(v) for v in s])
        idx = toneidx(l, len(CREAM))
        out = CREAM[idx].copy()
        # painéis lavanda (chapas trocadas)
        pc = np.array([hsh(int(a // 16), int((b + 4) // .5), 13) for a, b in zip(s, th)]) > (.82 if not B else .7)
        out[pc] = LAVR[np.clip(idx[pc] - 1, 0, 4)]
        # emendas
        seam = ((s % 16) < .5) | (np.abs(((th + 4) % .5) - .25) > .24 * (1 - .9 / np.maximum(r, 1)) + .0)
        seam = ((s % 16) < .5) | ((((th + 4) / .5) % 1) * r * .5 < .45)
        out[seam & (s > 28) & (s < 160)] = CREAM[np.clip(idx[seam & (s > 28) & (s < 160)] + 1, 0, 5)]
        # faixa
        band = (th > -0.27) & (th < -0.12) & (s > 22) & (s < 168)
        out[band] = STRIPE[np.clip(idx[band] - 2, 0, 3)]
        out[band & (th > -0.15)] = STRIPE[0]
        # vigias
        win = (th > 0.10) & (th < 0.25) & (s > 34) & (s < 148) & (((s - 34) % 7) < 3.6)
        dark = np.array([hsh(int((a - 34) // 7), 5, 21 if not B else 22) for a in s]) > .72
        out[win] = GLR[3]
        out[win & (((s - 34) % 7) < 1.3) & (th > 0.19)] = GLR[1]
        out[win & dark] = GLR[4]
        # cabine (nariz): para-brisa com montantes
        cab = (th > 0.45) & (th < 1.22) & (s > 7) & (s < 24)
        gi = toneidx(l, 5)
        out[cab] = GLR[np.clip(gi[cab] + 1, 1, 4)]
        mull = cab & ((np.abs(s - 13) < .5) | (np.abs(s - 18.5) < .5))
        out[mull] = CREAM[4]
        streak = cab & (np.abs((s - 9) - (th - .5) * 14) < .7)
        out[streak] = GLR[0]
        # sujeira e escorrido
        dirt = np.array([hsh(int(a), int(b * R), 7) for a, b in zip(s, th)]) > .94
        out[dirt] = CREAM[np.clip(idx[dirt] + 2, 0, 5)]
        keep = ~removed(s, th + np.where(th < 0, 0, 0))
        # furos de parafuso na borda das chapas que ficaram (a desmontagem foi caprichada)
        return out, keep
    cyl(zr, (0, 0, zc), "u", L, rfun, skin)

    # parede de dentro (aparece pelo trecho aberto)
    def inner(s, th, l, N):
        th2 = np.where(th > math.pi, th - 2 * math.pi, th)
        out = INTR[np.clip(toneidx(-l, len(INTR)), 0, 4)].copy()
        quilt = ((s % 4) < .5) | ((((th2 + 4) / .3) % 1) < .12)
        out[quilt] = INTR[4]
        return out, (s > cut[0] - 2) & (s < cut[1] + 2)
    cyl(zr, (0, 0, zc), "u", L, rfun, inner, inner=True)
    # costelas e longarinas no trecho aberto (um pouquinho pra dentro do casco)
    u0, u1 = cut[0], cut[1]
    for ur in np.arange(u0, u1 + .1, cell_u):
        def rib(s, th, l, N):
            idx = toneidx(l, len(METR))
            out = METR[idx].copy()
            rs = np.array([hsh(int(a * 3), int(b * 9), 3) for a, b in zip(s, th)]) > .8
            out[rs] = RUSTR[1]
            return out, np.ones(len(s), bool)
        cyl(zr, (ur - .7, 0, zc), "u", 1.4, lambda s: R - .9, rib)
    for tl in np.arange(cut[2], cut[3], cell_t):
        P, C = [], []
        for s in np.arange(u0, u1, .4):
            for dt in np.linspace(-.6 / R, .6 / R, 3):
                th = tl + dt
                n = np.array([0, math.cos(th), math.sin(th)])
                P.append((s, (R - .9) * n[1], zc + (R - .9) * n[2])); C.append(n)
        N = np.array(C)
        zr.emit(np.array(P), METR[np.clip(toneidx(zr.light(N), 5) + 1, 0, 4)])
    # piso e poltronas lá dentro (algumas tiradas: foram pra tenda)
    fz = zc - R * .45
    hw = R * .88
    def floor(s, t, l):
        out = np.tile(rgb("#5a4a52"), (len(s), 1))
        out[(s % 3) < .5] = rgb("#4a3a44")
        return out, np.ones(len(s), bool)
    quad(zr, (u0, -hw, fz), (u1 - u0, 0, 0), (0, 2 * hw, 0), floor)
    seat = ramp("#8f93ad", "#6b6f8c", "#4f5270", "#3a3c55")
    for i, us in enumerate(np.arange(u0 + 3, u1 - 3, 6)):
        for j, (va, vb) in enumerate(((-16, -4), (4, 16))):
            if hsh(i, j, 77 if not B else 78) > (.55 if not B else .35):
                continue
            box(zr, us, us + 3, va, vb, fz, fz + 4, seat)
            box(zr, us - 1, us, va, vb, fz, fz + 9, seat)
    # cabos puxados pra fora do rasgo, descendo até o chão (um vai até a pilha de chapas)
    cab_cols = [ramp("#ff8a7a", "#e2533a", "#a8331f", "#7a2414"), ramp("#f2d27a", "#f2c46d", "#c8963a", "#8a6420"),
                ramp("#6b717a", "#4a4f57", "#2a2d33", "#1f2126")]
    um = (u0 + u1) / 2
    for i, (du, end) in enumerate(((-6, (um - 14, 44, 0)), (2, (um + 4, 50, 0)), (8, (um + 16, 38, 0)))):
        start = (um + du, 6, zc + 12)
        mid = (um + du + 2, 26, zc + 6)
        low = ((mid[0] + end[0]) / 2, (mid[1] + end[1]) / 2 + 2, 2)
        tube(zr, [start, mid, low, end], .55, cab_cols[i])
    # tampa da cauda + motores
    def tail(rho, th, l):
        out = np.tile(CREAM[4], (len(rho), 1)); out[rho > rfun(L) - 1.2] = CREAM[5]
        return out, np.ones(len(rho), bool)
    disc(zr, (L, 0, zc), "u", rfun(L), tail)
    for (ve, ze) in ((-17, zc + 5), (17, zc + 5)):
        def nac(s, th, l, N):
            idx = toneidx(l, len(METR))
            out = METR[idx].copy()
            out[(s > 4) & (s < 6)] = STRIPE[1]
            return out, np.ones(len(s), bool)
        cyl(zr, (150, ve, ze), "u", 30, lambda s: 7.5 if s > 4 else 4 + s * .87, nac)
        def noz(rho, th, l):
            out = np.tile(rgb("#17131e"), (len(rho), 1)); out[rho > 5.6] = METR[3]; out[(rho > 2) & (rho < 3)] = rgb("#2c2634")
            return out, np.ones(len(rho), bool)
        disc(zr, (180, ve, ze), "u", 7.5, noz)
    # deriva (cauda vertical)
    def finf(s, t, l):
        idx = toneidx(l, len(LAVR))
        out = LAVR[idx].copy()
        out[(t > 18) & (t < 22)] = STRIPE[1]
        out[(s > 26) & (t > 30)] = rgb("#ff5a4a")
        return out, np.ones(len(s), bool)
    fin = [(0, 0), (30, 0), (36, 34), (26, 34)] if not B else [(0, 0), (30, 0), (34, 22), (22, 26), (24, 18)]
    plate_poly(zr, (142, 1.2, zc + R - 2), (1, 0, 0), (0, 0, 1), fin, finf, thick=2.4, dark="#6b6f8c")
    # asas: a de longe e a de perto (na B a de perto foi DESMONTADA: sobrou o toco com as nervuras)
    def wingf(s, t, l):
        idx = toneidx(l, len(LAVR))
        out = LAVR[idx].copy()
        out[(np.abs(t) > 34) & (np.abs(t) < 38)] = STRIPE[1]
        out[(s % 9) < .45] = LAVR[3]
        return out, np.ones(len(s), bool)
    plate_poly(zr, (0, 0, zc - 6), (1, 0, 0), (0, 1, 0), [(64, -18), (104, -18), (100, -58), (84, -62)], wingf, thick=2, dark="#4f5270")
    if not B:
        plate_poly(zr, (0, 0, zc - 8), (1, 0, 0), (0, 1, 0), [(62, 18), (104, 18), (100, 60), (82, 64)], wingf, thick=2, dark="#4f5270")
    else:
        plate_poly(zr, (0, 0, zc - 8), (1, 0, 0), (0, 1, 0), [(62, 18), (104, 18), (102, 30), (66, 30)], wingf, thick=2, dark="#4f5270")
        for us in np.arange(66, 103, 6):                                       # nervuras da asa à mostra
            tube(zr, [(us, 30, zc - 8), (us + 3, 52, zc - 9)], .55, METR)
        tube(zr, [(64, 50, zc - 9), (104, 50, zc - 9)], .55, METR)
    # trem de pouso (esquis curtos)
    for us in (34, 128):
        box(zr, us, us + 10, 14, 18, 0, 3, METR)
        tube(zr, [(us + 5, 16, 3), (us + 5, 12, zc - 14)], .9, METR)
    # antena com LED
    tube(zr, [(44, -4, zc + R - 1), (45, -4, zc + R + 16)], .5, METR)
    box(zr, 44, 46.5, -5, -2.5, zc + R + 16, zc + R + 18.5, ramp("#ff8a7a", "#ff5a4a", "#c83a2a", "#8a2a20"))
    # chapas tiradas, empilhadas certinho no chão (a diretoria ia levar)
    stack = (108, 30) if not B else (um - 30, 46)
    for i in range(5 if not B else 7):
        o = hsh(i, 1, 4) * 1.2
        box(zr, stack[0] + o, stack[0] + 14 + o, stack[1] + o * .5, stack[1] + 9 + o * .5, i * 1.1, i * 1.1 + 1,
            LAVR if i % 3 == 1 else CREAM)
    if B:   # pedaços da asa desmontada encostados
        for i in range(3):
            box(zr, 112 + i * 4, 126 + i * 4, 52 + i * 2, 54 + i * 2, 0, 9 - i, LAVR)
    # bagagem e caixas dos colonos
    rng_spots = [(84, 40), (96, 46), (106, 36), (118, 44), (70, 48), (130, 40), (58, 40), (140, 34), (48, 50), (112, 52)]
    for i, (u, v) in enumerate(rng_spots[: 8 if not B else 10]):
        k = int(hsh(u, v, 9) * len(BAGS))
        w_, d_, h_ = 5 + int(hsh(u, v, 1) * 3), 3 + int(hsh(u, v, 2) * 2), 3 + int(hsh(u, v, 3) * 3)
        zr.push(rot("z", math.radians(-30 + 60 * hsh(u, v, 5))), pivot=(u, v, 0))
        box(zr, u, u + w_, v, v + d_, 0, h_, BAGS[k])
        box(zr, u + w_ / 2 - 1, u + w_ / 2 + 1, v + d_ / 2 - .4, v + d_ / 2 + .4, h_, h_ + 1, METR, sides=("top", "v", "u"))
        zr.pop()
    for (u, v, s_) in ((60, 30, 7), (150, 30, 6), (38, 40, 6)):                # caixotes de madeira
        box(zr, u, u + s_, v, v + s_, 0, s_ - 1, WOODR)
        box(zr, u, u + s_, v + s_ / 2 - .4, v + s_ / 2 + .4, s_ - 1, s_ - .6, ramp("#f2c46d", "#d9a24a", "#a87830"), sides=("top", "v", "u"))
    # areia: o nariz enterrado e montes no pé do casco
    mound(zr, 6, 8, 12, 20, 6, 1)
    mound(zr, 120, 20, 30, 7, 3, 2)

    def ground(cv):
        P = lambda u, v: (zr.x0 + u - v, zr.y0 + (u + v) / 2)
        cv.poly([P(2, -R + 2), P(L + 8, -R + 2), P(L + 8, R + 4), P(2, R + 4)], SHADOW)   # sombra no chão, ao longo do casco
        cv.poly([P(60, 16), P(108, 16), P(104, 66), P(80, 70)], SHADOW) if not B else None   # sombra da asa
        sand_pile(cv, *P(20, 26), 22, 5, 3); sand_pile(cv, *P(150, 28), 22, 4, 4)
        scatter(cv, [(10, 196), (40, 202), (100, 204), (150, 200), (200, 204), (260, 196), (276, 186)], 11)
    cv = finish(W, H, zr, INK_L, ground)
    # nome pintado no costado (fonte 3×5 cisalhada pelo iso, como o VESPER-7), só onde o casco aparece
    th = 0.40
    vv, zz = R * math.cos(th) + .5, zc + R * math.sin(th)
    img = np.array(cv.im)
    for i, ch in enumerate("ARCA-2"):
        for j, row in enumerate(FONT2[ch]):
            for k, b in enumerate(row):
                if b != "1":
                    continue
                u = 104 + (i * 4 + k) * 2
                for du in (0, 1):
                    for dz in (0, 1):
                        x = int(math.floor(zr.x0 + u + du - vv + .5)); y = int(math.floor(zr.y0 + (u + du + vv) / 2 - (zz - j * 2 - dz) + .5))
                        if img[y, x, 3] == 255:
                            img[y, x, :3] = rgb("#4a4260")
    cv.im = Image.fromarray(img)
    cv.meta = dict(LINER_R2)
    return cv


def main():
    PEND.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in (("robot", robot_r2), ("liner", liner_r2)):
        for v in "AB":
            c = fn(v)
            assert c.im.size == tuple(c.meta["sprite"])
            c.im.save(PEND / f"wreck_{name}_r2_{v}.png")
            out[f"{name}_r2_{v}"] = c.meta
            print(name, v, c.meta)
    return out


if __name__ == "__main__":
    main()
