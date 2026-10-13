"""Mini motor 3D pra pixel art (r3d): peças geométricas → amostragem densa → z-buffer → luz em faixas → contorno.

Portado do gerador experimental (~/Desktop/hesper_sprites_experimento/gerador/r3d.py) pra cá, AUTOCONTIDO: o
pedacinho do common.py que ele usa (rgb, OUTLINE e o Canvas com contorno) vem junto aqui embaixo. Nada depende
do Desktop. Determinístico (sem aleatório), alpha só 0 ou 255, sem anti-aliasing.

Mundo: X pra direita, Y pra trás (longe da câmera), Z pra cima, em pixels. A câmera olha de frente e de cima
(elevação ELEV), então o tampo aparece encurtado e a frente quase inteira, igual ao 3/4 do resto do jogo.
A luz vem de cima-esquerda-frente. O tom sai de n·L quantizado em 5 faixas da paleta (sem dithering, sem
anti-aliasing). Entre peças com salto de profundidade entra uma linha de contorno, como num desenho à mão.

Uso:
    sc = Scene(40, 56)
    sc.box((-12, 12), (-10, 10), (0, 6), METAL_P)
    sc.cyl(0, 0, 11, 6, 40, BEIGE_P, bands=[(20, 22, ORANGE_P)])
    cv = sc.render()          # Canvas: cv.a é o array RGBA, cv.image() devolve a PIL.Image
"""
import math

import numpy as np
from PIL import Image

OUTLINE = "#1b1630"


def rgb(c):
    if isinstance(c, tuple):
        return c if len(c) == 4 else (*c, 255)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


class Canvas:
    """O mínimo do Canvas do gerador experimental: RGBA em numpy, pixel solto e contorno externo de 1 px."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x] = rgb(c)

    def outline(self, c=OUTLINE):
        sol = self.a[:, :, 3] == 255
        add = np.zeros_like(sol)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            sh = np.zeros_like(sol)
            ys = slice(max(dy, 0), self.h + min(dy, 0))
            yd = slice(max(-dy, 0), self.h + min(-dy, 0))
            xs = slice(max(dx, 0), self.w + min(dx, 0))
            xd = slice(max(-dx, 0), self.w + min(-dx, 0))
            sh[yd, xd] = sol[ys, xs]
            add |= sh
        add &= ~sol
        self.a[add] = rgb(c)

    def image(self):
        a = self.a.copy()
        a[a[:, :, 3] == 0] = 0
        return Image.fromarray(a)

ELEV = math.radians(35)
SA, CA = math.sin(ELEV), math.cos(ELEV)
LIGHT = np.array([-0.45, -0.30, 0.84])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
STEP = 0.3                       # passo da amostragem (px): menor que 1/2 px pra não deixar buraco


class Pal:
    """5 tons (brilho, claro, base, sombra, fundo). emit=True ignora a luz (brilha sozinho) e usa `emit_tone`."""

    def __init__(self, tones, emit=False, emit_tone=1):
        self.rgb = np.array([rgb(t)[:3] for t in tones], np.uint8)
        self.emit, self.emit_tone = emit, emit_tone


def tone_of(shade):
    return np.select([shade > 0.7, shade > 0.25, shade > -0.1, shade > -0.6], [0, 1, 2, 3], 4)


class Scene:
    def __init__(self, w, h, ground=None):
        self.w, self.h = w, h
        self.cx = w / 2
        self.gy = h - 2 if ground is None else ground     # linha da tela onde fica (Y=0, Z=0)
        self.parts = []                                    # (sx, sy, depth, rgb, id)
        self.nid = 0
        self.decals = []

    # ---- projeção
    def proj(self, X, Y, Z):
        sx = X + self.cx
        sy = self.gy - (Y * SA + Z * CA)
        depth = Y * CA - Z * SA
        return sx, sy, depth

    def _emit(self, P, N, pal_idx, pals, cull=True):
        """P, N: (n, 3). pal_idx: (n,) índice em pals. Faz a luz, o culling e guarda as amostras."""
        view = np.array([0, -CA, SA])                      # direção pra câmera
        vis = (N @ view) > -0.05 if cull else np.ones(len(P), bool)
        P, N, pal_idx = P[vis], N[vis], pal_idx[vis]
        if not len(P):
            return
        shade = N @ LIGHT
        tone = tone_of(shade)
        col = np.zeros((len(P), 3), np.uint8)
        for i, pal in enumerate(pals):
            m = pal_idx == i
            if not m.any():
                continue
            t = np.full(m.sum(), pal.emit_tone) if pal.emit else tone[m]
            col[m] = pal.rgb[t]
        sx, sy, d = self.proj(P[:, 0], P[:, 1], P[:, 2])
        self.parts.append((sx, sy, d, col, np.full(len(P), self.nid)))
        self.nid += 1

    # ---- peças
    def obox(self, center, half, pal, rot_z=0.0, rot_x=0.0, paint=None, extra=()):
        """Caixa orientada. half = meias-medidas (hx, hy, hz). rot_z gira em volta do eixo vertical,
        rot_x inclina pra frente/trás. paint(local_xyz, face) -> índice em [pal, *extra] (vetorizado)."""
        cz, sz = math.cos(rot_z), math.sin(rot_z)
        cx, sx = math.cos(rot_x), math.sin(rot_x)
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        R = Rz @ Rx
        hx, hy, hz = half
        P_all, N_all, I_all = [], [], []
        for axis in range(3):
            for sgn in (-1, 1):
                n = np.zeros(3)
                n[axis] = sgn
                o = [a for a in range(3) if a != axis]
                ua = np.arange(-half[o[0]], half[o[0]] + 1e-6, STEP)
                va = np.arange(-half[o[1]], half[o[1]] + 1e-6, STEP)
                U, V = np.meshgrid(ua, va)
                L = np.zeros((U.size, 3))
                L[:, axis] = sgn * half[axis]
                L[:, o[0]] = U.ravel()
                L[:, o[1]] = V.ravel()
                face = axis * 2 + (sgn > 0)
                idx = paint(L, face) if paint else np.zeros(len(L), int)
                P_all.append(L @ R.T + np.array(center))
                N_all.append(np.tile(R @ n, (len(L), 1)))
                I_all.append(np.broadcast_to(np.asarray(idx, int), (len(L),)))
        self._emit(np.vstack(P_all), np.vstack(N_all), np.concatenate(I_all), [pal, *extra])

    def box(self, xr, yr, zr, pal, **kw):
        c = ((xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2)
        h = ((xr[1] - xr[0]) / 2, (yr[1] - yr[0]) / 2, (zr[1] - zr[0]) / 2)
        self.obox(c, h, pal, **kw)

    def cyl(self, cx, cy, r, z0, z1, pal, r_top=None, cap=True, paint=None, extra=(), spin=0.0):
        """Cilindro (ou tronco de cone se r_top != r) vertical. paint(theta, z, is_cap) -> índice.
        `spin` soma ao ângulo passado pro paint (gira a pintura: estria de broca, faixa de ventoinha...)."""
        r_top = r if r_top is None else r_top
        th = np.arange(0, 2 * math.pi, STEP / max(r, r_top, 1))
        zs = np.arange(z0, z1 + 1e-6, STEP)
        T, Zg = np.meshgrid(th, zs)
        T, Zg = T.ravel(), Zg.ravel()
        k = (Zg - z0) / max(z1 - z0, 1e-6)
        R = r + (r_top - r) * k
        P = np.stack([cx + R * np.cos(T), cy + R * np.sin(T), Zg], 1)
        slope = (r - r_top) / max(z1 - z0, 1e-6)
        N = np.stack([np.cos(T), np.sin(T), np.full_like(T, slope)], 1)
        N /= np.linalg.norm(N, axis=1, keepdims=True)
        idx = paint((T + spin) % (2 * math.pi), Zg, np.zeros(len(T), bool)) if paint else np.zeros(len(T), int)
        Ps, Ns, Is = [P], [N], [np.broadcast_to(np.asarray(idx, int), (len(P),))]
        if cap and r_top > 0:
            rr = np.arange(0, r_top + 1e-6, STEP)
            th2 = np.arange(0, 2 * math.pi, STEP / max(r_top, 1))
            RR, TT = np.meshgrid(rr, th2)
            RR, TT = RR.ravel(), TT.ravel()
            Pc = np.stack([cx + RR * np.cos(TT), cy + RR * np.sin(TT), np.full_like(RR, z1)], 1)
            Ps.append(Pc)
            Ns.append(np.tile([0, 0, 1.0], (len(Pc), 1)))
            Is.append(np.broadcast_to(np.asarray(paint((TT + spin) % (2 * math.pi), RR, np.ones(len(TT), bool)), int), (len(Pc),))
                      if paint else np.zeros(len(Pc), int))
        self._emit(np.vstack(Ps), np.vstack(Ns), np.concatenate(Is), [pal, *extra])

    def hcyl(self, x0, x1, cy, cz, r, pal):
        """Cilindro deitado no eixo X (cano)."""
        xs = np.arange(x0, x1 + 1e-6, STEP)
        th = np.arange(0, 2 * math.pi, STEP / max(r, 1))
        Xg, T = np.meshgrid(xs, th)
        Xg, T = Xg.ravel(), T.ravel()
        P = np.stack([Xg, cy + r * np.cos(T), cz + r * np.sin(T)], 1)
        N = np.stack([np.zeros_like(T), np.cos(T), np.sin(T)], 1)
        self._emit(P, N, np.zeros(len(P), int), [pal])

    def sphere(self, c, r, pal, paint=None, extra=()):
        """Esfera. paint(normais (n, 3)) -> índice em [pal, *extra] (faixas, painéis...)."""
        th = np.arange(0, 2 * math.pi, STEP / r)
        ph = np.arange(0, math.pi, STEP / r)
        T, F = np.meshgrid(th, ph)
        N = np.stack([np.sin(F) * np.cos(T), np.sin(F) * np.sin(T), np.cos(F)], -1).reshape(-1, 3)
        idx = np.broadcast_to(np.asarray(paint(N), int), (len(N),)) if paint else np.zeros(len(N), int)
        self._emit(np.array(c) + r * N, N, idx, [pal, *extra])

    def disc(self, cx, cy, z, r, pal, r_in=0.0, paint=None, extra=()):
        rr = np.arange(r_in, r + 1e-6, STEP)
        th = np.arange(0, 2 * math.pi, STEP / max(r, 1))
        RR, TT = np.meshgrid(rr, th)
        RR, TT = RR.ravel(), TT.ravel()
        P = np.stack([cx + RR * np.cos(TT), cy + RR * np.sin(TT), np.full_like(RR, z)], 1)
        idx = paint(TT, RR) if paint else np.zeros(len(P), int)
        self._emit(P, np.tile([0, 0, 1.0], (len(P), 1)), np.broadcast_to(np.asarray(idx, int), (len(P),)), [pal, *extra],
                   cull=False)

    def rbox(self, center, half, r, pal, paint=None, extra=(), rot_x=0.0, pivot=None):
        """Caixa de quinas e arestas ARREDONDADAS (raio r): 6 faces planas + 12 arestas (quarto de cilindro) + 8
        cantos (oitavo de esfera). paint(local_xyz, normal_local) -> índice em [pal, *extra] (vetorizado).
        rot_x gira em volta do eixo X passando por `pivot` (tampa abrindo). Acrescentado na v1.1 do baú."""
        hx, hy, hz = half
        r = min(r, hx, hy, hz)
        h = np.array([hx - r, hy - r, hz - r])
        Ps, Ns = [], []
        for a in range(3):                                         # faces
            o = [b for b in range(3) if b != a]
            ua = np.arange(-h[o[0]], h[o[0]] + 1e-6, STEP)
            va = np.arange(-h[o[1]], h[o[1]] + 1e-6, STEP)
            U, Vv = np.meshgrid(ua, va)
            for sg in (-1, 1):
                L = np.zeros((U.size, 3))
                L[:, a] = sg * (h[a] + r)
                L[:, o[0]] = U.ravel()
                L[:, o[1]] = Vv.ravel()
                n = np.zeros((U.size, 3))
                n[:, a] = sg
                Ps.append(L)
                Ns.append(n)
        th = np.arange(0, math.pi / 2 + 1e-6, STEP / max(r, 0.5))
        for c in range(3):                                         # arestas (paralelas ao eixo c)
            a, b = [k for k in range(3) if k != c]
            ts = np.arange(-h[c], h[c] + 1e-6, STEP)
            TT, TH = np.meshgrid(ts, th)
            TT, TH = TT.ravel(), TH.ravel()
            for sa in (-1, 1):
                for sb in (-1, 1):
                    n = np.zeros((TT.size, 3))
                    n[:, a] = sa * np.cos(TH)
                    n[:, b] = sb * np.sin(TH)
                    L = n * r
                    L[:, a] += sa * h[a]
                    L[:, b] += sb * h[b]
                    L[:, c] = TT
                    Ps.append(L)
                    Ns.append(n)
        ph = np.arange(0, math.pi / 2 + 1e-6, STEP / max(r, 0.5))
        A, F = np.meshgrid(th, ph)
        oct_n = np.stack([np.sin(F) * np.cos(A), np.sin(F) * np.sin(A), np.cos(F)], -1).reshape(-1, 3)
        for sx in (-1, 1):                                         # cantos
            for sy in (-1, 1):
                for sz in (-1, 1):
                    n = oct_n * np.array([sx, sy, sz])
                    Ps.append(n * r + h * np.array([sx, sy, sz]))
                    Ns.append(n)
        L = np.vstack(Ps)
        N = np.vstack(Ns)
        idx = np.broadcast_to(np.asarray(paint(L, N), int), (len(L),)) if paint else np.zeros(len(L), int)
        P = L + np.array(center, float)
        if rot_x:
            c, s_ = math.cos(rot_x), math.sin(rot_x)
            R = np.array([[1, 0, 0], [0, c, -s_], [0, s_, c]])
            pv = np.array(pivot if pivot is not None else center, float)
            P = (P - pv) @ R.T + pv
            N = N @ R.T
        self._emit(P, N, idx, [pal, *extra])

    def dot(self, X, Y, Z, color, always=False):
        """Pixel solto num ponto 3D (LED, bolha, faísca). Só aparece se não estiver escondido."""
        self.decals.append((X, Y, Z, color, always))

    # ---- render
    def render(self, outline=True, inner=True):
        W, H = self.w, self.h
        zbuf = np.full((H, W), np.inf)
        cbuf = np.zeros((H, W, 3), np.uint8)
        ibuf = np.full((H, W), -1)
        for sx, sy, d, col, ids in self.parts:
            xi, yi = np.floor(sx).astype(int), np.floor(sy).astype(int)
            ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
            xi, yi, d, col, ids = xi[ok], yi[ok], d[ok], col[ok], ids[ok]
            order = np.argsort(-d, kind="stable")              # longe primeiro, o perto sobrescreve
            xi, yi, d, col, ids = xi[order], yi[order], d[order], col[order], ids[order]
            near = d < zbuf[yi, xi]
            xi, yi, d, col, ids = xi[near], yi[near], d[near], col[near], ids[near]
            zbuf[yi, xi] = d
            cbuf[yi, xi] = col
            ibuf[yi, xi] = ids
            # numpy: em índices repetidos fica o último escrito = o mais perto (ordem acima)
            # mas o z-buffer de cima pode ter ficado com o valor de um mais longe; reconcilia:
            zmin = np.full((H, W), np.inf)
            np.minimum.at(zmin, (yi, xi), d)
            zbuf = np.minimum(zbuf, zmin)
        cv = Canvas(W, H)
        solid = ibuf >= 0
        cv.a[solid, :3] = cbuf[solid]
        cv.a[solid, 3] = 255
        if inner:                                               # contorno interno entre peças (salto de fundo)
            with np.errstate(invalid="ignore"):
                edge = np.zeros_like(solid)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb_id = np.full_like(ibuf, -1)
                    nb_z = np.full_like(zbuf, np.inf)
                    ys = slice(max(dy, 0), H + min(dy, 0))
                    yd = slice(max(-dy, 0), H + min(-dy, 0))
                    xs = slice(max(dx, 0), W + min(dx, 0))
                    xd = slice(max(-dx, 0), W + min(-dx, 0))
                    nb_id[yd, xd] = ibuf[ys, xs]
                    nb_z[yd, xd] = zbuf[ys, xs]
                    edge |= solid & (nb_id >= 0) & (nb_id != ibuf) & (zbuf - nb_z > 2.2)
                cv.a[edge, :3] = rgb(OUTLINE)[:3]
        if outline:
            cv.outline()
        for (X, Y, Z, color, always) in self.decals:
            sx, sy, d = self.proj(X, Y, Z)
            xi, yi = int(math.floor(sx)), int(math.floor(sy))
            if 0 <= xi < W and 0 <= yi < H and (always or d <= zbuf[yi, xi] + 1.0):
                cv.px(xi, yi, color)
        return cv
