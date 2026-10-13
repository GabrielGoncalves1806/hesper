"""Renderizador da cena 960×540 da proposta de regiões. É a RECEITA pro Dev (ver o report, seção "Pro Dev"):

    1. CHÃO        textura grande da região (512×512, emenda) recortada pela posição no mundo, no estágio
    2. BORDAS      a região de cada pixel é a do tile em (x + dx, y + dy): deslocamento de domínio de até ±14 px
                   (ruído preso no mundo). A borda entre regiões vira curva irregular, nunca linha de tile
    3. LEITO       onde a altura (bilinear dos tiles + o mesmo deslocamento) fica abaixo do nível máximo da água:
                   silte com rachadura de lama. Marcas d'água secas = curvas de nível L1, L2, L3
    4. DECORAÇÃO   decalques indexados (manchas, rachaduras longas, placas, cascalho, sulcos) numa grade de
                   sorteio de 96 px presa no mundo
    5. ÁGUA        (Névoa/Verde) altura < nível: margem clara, raso, fundo
    6. COBERTURA   (Névoa) umidade, (Verde) grama/musgo, com a mesma borda deformada
    7. MORROS      silhueta do topo recortada (cantos redondos + borda tremida) e a FACE = a silhueta extrudada
                   24 px pra baixo; tudo intercalado por linha com os objetos (igual ao build_draw_list)
"""

from __future__ import annotations

import numpy as np
from PIL import Image

import regions_core as R
from regions_core import T, hash2, vnoise, fbm, grid

SPR = R.__file__ and __import__("pathlib").Path(R.__file__).resolve().parents[2] / "assets" / "sprites"
VW, VH = 960, 540
WARP = 14            # px de deslocamento máximo da borda das regiões
LIFT = 24            # topo elevado da parede
FACE = 24


def load(name):
    return Image.open(SPR / f"{name}.png").convert("RGBA")


# ---- caches ---------------------------------------------------------------------------------------------------
_TEX: dict = {}
_RAMP: dict = {}


def tex(region):
    if region not in _TEX:
        _TEX[region] = R.TEXTURES[region]()
    return _TEX[region]


def rmp(region, stage, table=None):
    key = (region, stage, id(table))
    if key not in _RAMP:
        _RAMP[key] = R.ramp(region, stage, table)
    return _RAMP[key]


# ---- campos por pixel -------------------------------------------------------------------------------------------
def warp_field(wx, wy):
    dx = WARP * (2 * fbm(wx, wy, 44, 901, 2) - 1) + 3 * (2 * vnoise(wx, wy, 7, 903) - 1)
    dy = WARP * (2 * fbm(wx, wy, 44, 905, 2) - 1) + 3 * (2 * vnoise(wx, wy, 7, 907) - 1)
    return dx, dy


def bilinear(a, u, v):
    hgt, wid = a.shape
    u = np.clip(u, 0, wid - 1.001)
    v = np.clip(v, 0, hgt - 1.001)
    i, j = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - i, v - j
    return (a[j, i] * (1 - fu) * (1 - fv) + a[j, i + 1] * fu * (1 - fv) + a[j + 1, i] * (1 - fu) * fv
            + a[j + 1, i + 1] * fu * fv)


def _sm(t):
    return t * t * (3 - 2 * t)


def shift(a, dy=0, dx=0, fill=False):
    out = np.full_like(a, fill)
    hh, ww = a.shape[:2]
    ys0, ys1 = max(0, dy), min(hh, hh + dy)
    xs0, xs1 = max(0, dx), min(ww, ww + dx)
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


# ---- morros: texturas -------------------------------------------------------------------------------------------
_HT: dict = {}


def hill_top_tex(seed=61):
    if "top" in _HT:
        return _HT["top"]
    xs, ys = grid(R.TEX, R.TEX)
    p = R.TEX
    n = R.organic(xs, ys, p, 10, seed)
    idx = np.full((p, p), 4, np.uint8)
    idx[n < np.quantile(n, 0.40)] = 3
    idx[n < np.quantile(n, 0.06)] = 2
    idx[n > np.quantile(n, 0.93)] = 5
    _, edge, cid = R.voronoi(xs, ys, p / 12, seed + 2, 12)           # fraturas esparsas de ~42 px
    crack = (edge < 1.0) & (hash2(cid, 1, seed) < 0.35)
    idx[crack] = 1
    idx[np.roll(crack, 1, axis=0) & ~crack] = 5
    idx[np.roll(crack, -1, axis=0) & ~crack] = 2
    sp = hash2(xs, ys, seed + 5)
    idx[(sp < 0.015) & (idx >= 3)] = 2
    idx[(sp > 0.99) & (idx <= 4)] = 5
    idx = R._pebbles(idx, seed + 7, 0.05, top=5, body=4, low=2, step=7)
    _HT["top"] = idx
    return idx


def face_index(wx, d, seed=71):
    """Índice da face de rocha no px de mundo x, a d px abaixo do topo (0..23). Blocos irregulares, estratos
    horizontais tremidos, fissuras curtas e inclinadas (nunca junta vertical regular), escurecendo pro pé."""
    idx = np.full(d.shape, 2, np.uint8)
    idx[d >= 10] = 1
    idx[(d >= 17) & (hash2(wx, d, seed + 9) < 0.5)] = 0
    idx[d >= 21] = 0
    idx[d <= 4] = 3
    idx[d <= 1] = 4
    # estratos: linha escura (sombra da saliência) com brilho em cima
    for base, sd in ((7, 1), (15, 2)):
        wob = np.floor(2.6 * vnoise(wx, 0 * wx, 23, seed + sd)).astype(int) - 1
        line = d == base + wob
        idx[line] = 0
        lit = d == base + wob - 1
        idx[lit] = np.minimum(idx[lit] + 1, 4)
    # blocos: em cada faixa, fissuras a cada 9..26 px, com inclinação
    band = np.where(d < 8, 0, np.where(d < 16, 1, 2))
    cellw = 17
    cx = (wx + band * 7) // cellw
    off = (hash2(cx, band, seed + 3) * 12).astype(int)
    slant = (hash2(cx, band, seed + 4) * 3).astype(int) - 1
    fiss = ((wx + band * 7) % cellw == (off + slant * (d % 8) // 3) % cellw) & (hash2(cx, band, seed + 5) < 0.55)
    fiss &= (d > 2) & (d < 22)
    idx[fiss] = 0
    # textura
    sp = hash2(wx, d, seed + 6)
    idx[(sp < 0.06) & (idx >= 1) & (d > 2)] -= 1
    idx[(sp > 0.95) & (idx <= 2) & (d > 2) & (d < 18)] += 1
    return idx


# =================================================================================================================
class Scene:
    """Uma vista 960×540 do mundo. `world` vem de R.gen_world() + as alterações feitas à mão pelos mockups."""

    def __init__(self, world, x0, y0, stage="arid", decor=True, hills="new", water=None, cover=True, tiles=False):
        self.tiles = tiles            # True = jeito de hoje: tile 32×32 repetido, região por tile, sem deformar
        self.w = world
        self.x0, self.y0 = x0, y0
        self.stage = stage
        self.decor = decor
        self.hills = hills
        self.water = water            # nível d'água (altura) ou None
        self.cover = cover
        self.objects = []             # (pé_y_mundo, img, x_mundo, y_mundo)
        self.roofs = []               # desenhados por cima de tudo (vão do arco)
        self.ground_decals = []       # (img, x_mundo, y_mundo) por cima do chão
        self.under_decals = []        # já recoloridos, desenhados antes dos decalques (sombras de formação)

    # ---------------------------------------------------------------------------------------------------------
    def fields(self):
        wx, wy = grid(VW, VH, self.x0, self.y0)
        dx, dy = warp_field(wx, wy)
        if self.tiles:
            dx, dy = 0 * dx + T / 2, 0 * dy + T / 2
        ux, uy = (wx + dx) / T, (wy + dy) / T
        ti = np.clip(np.floor(ux).astype(int), 0, R.W - 1)
        tj = np.clip(np.floor(uy).astype(int), 0, R.H - 1)
        reg = self.w["region"][tj, ti].astype(np.int16)
        hpx = bilinear(self.w["h"], ux - 0.5, uy - 0.5)
        if self.tiles:
            hpx = self.w["h"][tj, ti]
        return wx, wy, reg, hpx

    def ground(self):
        wx, wy, reg, hpx = self.fields()
        self.wx, self.wy, self.reg, self.hpx = wx, wy, reg, hpx
        st = self.stage
        L3 = R.LEVELS[2]
        cls = reg.copy()
        bed = (hpx < L3) & (reg == R.REG["plateau"])
        cls[bed] = 4
        self.cls = cls
        names = R.REG_NAMES + ["bed"]
        img = np.zeros((VH, VW, 3), np.uint8)
        idx_all = np.zeros((VH, VW), np.uint8)
        for c, name in enumerate(names):
            m = cls == c
            if not m.any():
                continue
            t = tex(name)
            if self.tiles:                      # 4 recortes 32×32 da textura, sorteados por tile
                v = (hash2(wx[m] // T, wy[m] // T, 3) * 4).astype(int)
                idx = t[(v // 2) * T + wy[m] % T, (v % 2) * T + wx[m] % T]
            else:
                idx = t[wy[m] % R.TEX, wx[m] % R.TEX]
            idx_all[m] = idx
            img[m] = rmp(name, st)[idx]
        # borda entre classes: o lado "de baixo" (mais escuro) ganha 1 px de fenda e o outro 1 px de brilho
        diff_d = (cls != shift(cls, -1, 0, -1)) & (shift(cls, -1, 0, -1) >= 0)
        diff_r = (cls != shift(cls, 0, -1, -1)) & (shift(cls, 0, -1, -1) >= 0)
        edge = diff_d | diff_r
        for c, name in enumerate(names):
            m = edge & (cls == c)
            img[m] = rmp(name, st)[1]
        # marcas d'água secas (curvas de nível) acima da água atual: linha mineral clara de 2 px (no salar, anel
        # escuro), com 1 px de sombra embaixo. L3 contínua (a borda do leito), L1 e L2 tracejadas
        lv = self.water if self.water is not None else -1
        pale = np.array(R.rgb("#dcd0bb"), np.uint8)
        pale2 = np.array(R.rgb("#c4b59c"), np.uint8)
        for k, L in enumerate(R.LEVELS):
            if L <= lv + 1e-6:
                continue
            below = hpx < L
            ring = below & ~(shift(below, 1, 0, True) & shift(below, -1, 0, True) & shift(below, 0, 1, True)
                             & shift(below, 0, -1, True))
            ring |= shift(ring, 0, 1) & below
            if k < 2:
                ring &= hash2(wx // 5, wy // 5, 77 + k) < 0.7
            sal = cls == 1
            img[ring & ~sal] = pale if k == 2 else pale2
            img[ring & sal] = rmp("salar", st)[1]
            under = shift(ring, 1, 0) & ~ring & below
            img[under & ~sal] = rmp("bed", st)[2]
            img[under & sal] = rmp("salar", st)[0]
        self.img = img
        self.idx = idx_all

    # ---------------------------------------------------------------------------------------------------------
    def water_layer(self):
        if self.water is None:
            return
        st = self.stage
        wet = self.hpx < self.water
        if not wet.any():
            return
        pal = {"mist": ("#2c5a72", "#3f7690", "#5d93aa", "#a9cbd6"),
               "green": ("#1d5f86", "#2c7ea6", "#4c9cc0", "#bfe4ee")}[st]
        deep, mid, shallow, foam = (np.array(R.rgb(c), np.uint8) for c in pal)
        depth = self.water - self.hpx
        img = self.img
        # margem molhada (terra escurecida) até 3 px fora da água
        near = np.zeros_like(wet)
        for k in (1, 2, 3):
            near |= shift(wet, k, 0) | shift(wet, -k, 0) | shift(wet, 0, k) | shift(wet, 0, -k)
        damp = near & ~wet
        img[damp] = (img[damp] * 0.78).astype(np.uint8)
        img[wet] = mid
        img[wet & (depth > 0.05)] = deep
        img[wet & (depth < 0.018)] = shallow
        shore = wet & ~(shift(wet, 1, 0, True) & shift(wet, -1, 0, True) & shift(wet, 0, 1, True)
                        & shift(wet, 0, -1, True))
        img[shore] = foam
        # brilhos parados (no jogo andam devagar)
        g = (hash2(self.wx // 9, self.wy // 3, 55) < 0.05) & ((self.wx % 9) < 5) & ((self.wy % 3) == 0)
        img[wet & g & (depth > 0.02)] = shallow
        self.wet = wet

    def cover_layer(self):
        """Cobertura do estágio por cima do chão: umidade na Névoa, grama/musgo no Verde (borda deformada)."""
        st = self.stage
        if not self.cover or st not in ("mist", "green"):
            return
        wx, wy = self.wx, self.wy
        dx, dy = warp_field(wx + 3000, wy + 1700)
        n = fbm((wx + dx) / T, (wy + dy) / T, 5.0, 313, 3)
        wet = getattr(self, "wet", np.zeros_like(n, bool))
        cls = self.cls
        img = self.img
        if st == "mist":
            m = (n > 0.56) & ~wet
            img[m] = (img[m].astype(int) * np.array([0.80, 0.84, 0.90])).astype(np.uint8)
            edge = m & ~shift(m, 1, 0, True)
            img[edge] = (img[edge] * 0.9).astype(np.uint8)
            return
        thr = {0: 0.47, 1: 0.70, 2: 0.58, 3: 0.48, 4: 0.40}
        tvec = np.vectorize(thr.get)(cls)
        near_water = np.zeros_like(wet)
        for k in (2, 5, 9, 14):
            near_water |= shift(wet, k, 0) | shift(wet, -k, 0) | shift(wet, 0, k) | shift(wet, 0, -k)
        tvec = np.where(near_water, tvec - 0.12, tvec)
        g = (n > tvec) & ~wet
        moss = cls == 2
        grass = np.array([R.rgb(c) for c in ("#2f5a2a", "#3f6e30", "#4d7a39", "#5f9442", "#79b04f", "#9ccc62")],
                         np.uint8)
        mossc = np.array([R.rgb(c) for c in ("#22331f", "#2c4127", "#38502e", "#466338", "#5c7d45", "#75985a")],
                         np.uint8)
        tn = R.organic(wx % 256, wy % 256, 256, 16, 333)
        lvl = np.clip((tn * 5).astype(int), 1, 4)
        blade = (hash2(wx, wy // 2, 335) < 0.05)
        lvl = np.where(blade, 5, lvl)
        col = np.where(moss[..., None], mossc[lvl], grass[lvl])
        img[g] = col[g]
        edge = g & ~(shift(g, 1, 0, True) & shift(g, -1, 0, True) & shift(g, 0, 1, True) & shift(g, 0, -1, True))
        dark = np.where(moss[..., None], mossc[1], grass[1])
        img[edge] = dark[edge]
        # tufos que saem da borda pra cima (folhinhas de 1×2 px)
        tuft = shift(edge, 1, 0) & ~g & (hash2(wx, wy, 337) < 0.35)
        img[tuft] = np.where(moss[..., None], mossc[3], grass[3])[tuft]

    # ---------------------------------------------------------------------------------------------------------
    def to_image(self):
        return Image.fromarray(self.img).convert("RGBA")

    # ---- morros ----------------------------------------------------------------------------------------------
    def hill_layers(self):
        """Devolve [(linha_do_tile, RGBA 960×540)] dos morros (topo + face), pra intercalar com objetos."""
        if self.hills == "old":
            return self.hill_layers_old()
        wall = self.w["wall"]
        x0, y0 = self.x0, self.y0
        wx, wy = grid(VW, VH + FACE + LIFT + T, x0, y0 - T)        # um pouco acima, pra pegar topos
        ty = np.floor((wy + LIFT) / T).astype(int)                  # o topo do tile ty fica em [ty·32−24, ty·32+8)
        tx = np.floor(wx / T).astype(int)
        lx = wx - tx * T
        ly = wy + LIFT - ty * T
        Wl = lambda a, b: wall[np.clip(b, 0, R.H - 1), np.clip(a, 0, R.W - 1)]  # noqa: E731
        # GRADE DUAL: o campo é interpolado (bilinear com smoothstep) entre os CENTROS dos tiles e cortado em 0,5.
        # Borda reta cai exatamente na borda do tile; escada diagonal vira diagonal; tile sozinho vira seixo.
        u = wx / T - 0.5
        v = (wy + LIFT) / T - 0.5
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        fu, fv = _sm(u - i), _sm(v - j)
        f = (Wl(i, j) * (1 - fu) * (1 - fv) + Wl(i + 1, j) * fu * (1 - fv) + Wl(i, j + 1) * (1 - fu) * fv
             + Wl(i + 1, j + 1) * fu * fv)
        f = f + 0.42 * (fbm(wx, wy, 15, 517, 3) - 0.5) + 0.10 * (vnoise(wx, wy, 4, 519) - 0.5)
        M = f > 0.5
        # a face é a silhueta extrudada pra baixo
        F = np.zeros_like(M)
        depth = np.full(M.shape, 99, int)
        for k in range(1, FACE + 1):
            s = shift(M, k, 0)
            new = s & ~M & (depth == 99)
            depth[new] = k - 1
            F |= new
        # linha dona de cada pixel (pra ordem de desenho): topo -> ty; face -> a linha do topo de onde ela pende
        rowM = ty
        rowF = np.full(M.shape, -1)
        for k in range(1, FACE + 1):
            m = F & (depth == k - 1)
            rowF[m] = shift(ty, k, 0, 0)[m]
        # cores
        reg = self.w["region"][np.clip(ty, 0, R.H - 1), np.clip(tx, 0, R.W - 1)]
        regF = np.zeros_like(reg)
        for k in range(1, FACE + 1):
            m = F & (depth == k - 1)
            regF[m] = shift(reg, k, 0, 0)[m]
        top = hill_top_tex()[(wy + LIFT) % R.TEX, wx % R.TEX].copy()
        # brilho na borda de cima (luz vem de cima) e contorno
        up_open = M & ~shift(M, 1, 0)
        top[up_open] = 8
        top[M & ~up_open & shift(up_open, 1, 0)] = 5
        left_open = M & ~shift(M, 0, 1)
        right_open = M & ~shift(M, 0, -1)
        top[left_open | right_open] = 8
        top[M & shift(left_open, 0, 1) & ~left_open] = 4
        fidx = face_index(wx, np.clip(depth, 0, FACE - 1))
        fl = F & ~shift(F, 0, 1) & ~shift(M, 0, 1)
        fr = F & ~shift(F, 0, -1) & ~shift(M, 0, -1)
        fidx[fl | fr] = 8
        fidx[F & (depth == FACE - 1)] = 8
        rgbimg = np.zeros(M.shape + (4,), np.uint8)
        names = R.REG_NAMES
        for c, name in enumerate(names):
            table = R.HILL if name in R.HILL else None
            ramp_ = rmp(name, self.stage, R.HILL)
            m = M & (reg == c)
            rgbimg[m, :3] = ramp_[top[m]]
            m = F & (regF == c)
            rgbimg[m, :3] = ramp_[fidx[m]]
        rgbimg[M | F, 3] = 255
        # minério por cima do topo (o sprite de hoje, recortado pela silhueta)
        ore = self.w.get("ore")
        oreimg = Image.new("RGBA", (VW, VH + FACE + LIFT + T))
        if ore is not None:
            for (otx, oty), res in ore.items():
                sx, sy = otx * T - x0, oty * T - LIFT - (y0 - T)
                if -T < sx < VW and -T < sy < VH + 80:
                    v = int(hash2(otx, oty, 80) * 3)
                    oreimg.alpha_composite(ore_sprite(res, v), (sx, sy))
        ore_a = np.array(oreimg)
        om = (ore_a[..., 3] > 0) & M
        rgbimg[om] = ore_a[om]
        # parte de cima extra (32 px) é cortada: a vista começa em y0
        rgbimg = rgbimg[T:T + VH]
        rows_M = np.where(M, rowM, -1)[T:T + VH]
        rows_F = rowF[T:T + VH]
        rows = np.where(rows_M >= 0, rows_M, rows_F)
        self.hill_mask = (M | F)[T:T + VH]
        self.hill_face = F[T:T + VH]
        self.hill_depth = depth[T:T + VH]
        out = []
        for r in sorted(set(np.unique(rows)) - {-1}):
            a = rgbimg.copy()
            a[rows != r, 3] = 0
            out.append((r, Image.fromarray(a)))
        return out

    def hill_layers_old(self):
        """Morros como o jogo desenha hoje (wall_dead_N + wall_face_dead + contorno/sombra)."""
        wall = self.w["wall"]
        st = "dead" if self.stage in ("storm", "arid") else self.stage
        x0, y0 = self.x0, self.y0
        tx0, ty0 = x0 // T - 1, y0 // T - 1
        layers = {}
        tops = [load(f"wall_{st}_{v}") for v in range(3)]
        face = load(f"wall_face_{st}")
        oh = Image.new("RGBA", (T, 1), (0, 0, 0, 90))
        ov = Image.new("RGBA", (1, T), (0, 0, 0, 70))
        ore = self.w.get("ore") or {}
        for ty in range(ty0, ty0 + VH // T + 3):
            for tx in range(tx0, tx0 + VW // T + 3):
                if not (0 <= tx < R.W and 0 <= ty < R.H) or not wall[ty, tx]:
                    continue
                L = layers.setdefault(ty, Image.new("RGBA", (VW, VH)))
                sx, sy = tx * T - x0, ty * T - y0
                v = int(hash2(tx, ty, 3) * 3)
                L.alpha_composite(tops[v], (sx, sy - LIFT)) if sy - LIFT > -T else None
                if sy - LIFT <= -T:
                    pass
                W_ = lambda a, b: 0 <= a < R.W and 0 <= b < R.H and wall[b, a]  # noqa: E731
                if not W_(tx, ty - 1):
                    L.alpha_composite(oh, (sx, max(0, sy - LIFT)))
                if not W_(tx - 1, ty):
                    L.alpha_composite(ov, (sx, sy - LIFT)) if sy - LIFT >= 0 else None
                if not W_(tx + 1, ty):
                    L.alpha_composite(ov, (sx + T - 1, sy - LIFT)) if sy - LIFT >= 0 else None
                if (tx, ty) in ore:
                    ovv = int(hash2(tx, ty, 80) * 3)
                    L.alpha_composite(ore_sprite(ore[(tx, ty)], ovv), (sx, sy - LIFT)) if sy - LIFT >= 0 else None
                if not W_(tx, ty + 1):
                    L.alpha_composite(face, (sx, sy + 8)) if sy + 8 >= 0 else None
        self.hill_mask = None
        return sorted(layers.items())

    def old_floor_shadows(self, img):
        """Sombra que a parede joga no chão (jogo de hoje)."""
        wall = self.w["wall"]
        st = Image.new("RGBA", (T, 16))
        a = np.zeros((16, T, 4), np.uint8)
        a[:10, :, 3] = 84
        a[10:, :, 3] = 40
        st = Image.fromarray(a)
        sl = Image.new("RGBA", (4, T), (0, 0, 0, 40))
        for ty in range(self.y0 // T - 1, (self.y0 + VH) // T + 2):
            for tx in range(self.x0 // T - 1, (self.x0 + VW) // T + 2):
                if not (0 < tx < R.W and 0 < ty < R.H) or wall[ty, tx]:
                    continue
                sx, sy = tx * T - self.x0, ty * T - self.y0
                if wall[ty - 1, tx]:
                    img.alpha_composite(st, (sx, sy)) if sy >= 0 else None
                if wall[ty, tx - 1]:
                    img.alpha_composite(sl, (sx, sy)) if sy >= 0 and sx >= 0 else None

    # ---------------------------------------------------------------------------------------------------------
    def compose(self, overlay=None):
        self.ground()
        # decoração entra NO CHÃO, antes da água e da cobertura (a água cobre a rachadura, a grama cobre a mancha)
        img = self.to_image()
        for im, x, y in self.under_decals:
            _paste(img, im, x - self.x0, y - self.y0)
        if self.decor:
            for im, x, y in self.ground_decals:
                _paste(img, im, x - self.x0, y - self.y0)
        self.img = np.array(img)[..., :3].copy()
        self.water_layer()
        self.cover_layer()
        img = self.to_image()
        if self.hills == "old":
            self.old_floor_shadows(img)
        hl = dict(self.hill_layers())
        objs = sorted(self.objects, key=lambda o: o[0])
        rows = sorted(set(hl) | {int(o[0] // T) for o in objs})
        for r in rows:
            if r in hl:
                img.alpha_composite(hl[r])
            for o in objs:
                if int(o[0] // T) == r:
                    _paste(img, o[1], o[2] - self.x0, o[3] - self.y0)
        for im, x, y in self.roofs:
            _paste(img, im, x - self.x0, y - self.y0)
        if overlay is not None:
            overlay(img, self)
        return img

    def hill_foot_shadow(self, img):
        """Sombra no chão logo embaixo do pé da face (1 faixa de 4 px, alfa fixo)."""
        self.hill_layers_cache = None


_DEC: dict = {}


def decals():
    if not _DEC:
        _DEC.update(R.decal_set())
    return _DEC


def scatter(world, x0, y0, stage, w=VW, h=VH, skip=None):
    """Decalques de uma área: 1 sorteio por célula de 96 px presa no mundo (a mesma em qualquer vista).
    `skip(tx, ty)` -> True pula a célula (base limpa, formação, etc.)."""
    out = []
    C = R.DECAL_CELL
    d = decals()
    for cy in range((y0 - 200) // C, (y0 + h + 200) // C + 1):
        for cx in range((x0 - 260) // C, (x0 + w + 260) // C + 1):
            for layer in (0, 1):                      # 2 sorteios por célula: um grande, um pequeno
                if hash2(cx, cy, 700 + layer) > 0.5 + 0.35 * layer:
                    pass
                px = cx * C + int(hash2(cx, cy, 702 + layer) * C)
                py = cy * C + int(hash2(cx, cy, 704 + layer) * C)
                tx, ty = px // T, py // T
                if not (0 <= tx < R.W and 0 <= ty < R.H):
                    continue
                if skip and skip(tx, ty):
                    continue
                reg = R.REG_NAMES[world["region"][ty, tx]]
                if reg == "plateau" and world["h"][ty, tx] < R.LEVELS[2]:
                    reg = "bed"
                if hash2(cx, cy, 706 + layer) > R.DECAL_P[reg] * (1.0 if layer == 0 else 0.6):
                    continue
                mix_ = R.DECAL_MIX[reg]
                if layer == 1:          # o 2º sorteio é sempre coisa miúda
                    mix_ = [m for m in mix_ if m[0] in ("gravel", "scoria", "plates", "ridges", "crack")] or mix_
                tot = sum(wt for _, wt in mix_)
                r = hash2(cx, cy, 708 + layer) * tot
                for name, wt in mix_:
                    r -= wt
                    if r <= 0:
                        break
                variants = [k for k in d if k.rsplit("_", 1)[0] == name]
                key = variants[int(hash2(cx, cy, 710 + layer) * len(variants))]
                idx = d[key]
                if hash2(cx, cy, 712 + layer) < 0.5 and not name.startswith("wind"):
                    idx = idx[:, ::-1]
                img = R.colorize(idx, rmp(reg, stage))
                out.append((img, px - img.width // 2, py - img.height // 2))
    return out


def _inside(im, x, y):
    return x < VW and y < VH and x + im.width > 0 and y + im.height > 0


def _paste(img, im, x, y):
    x, y = int(x), int(y)
    if not _inside(im, x, y):
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    crop = im.crop((cx0, cy0, min(im.width, VW - x), min(im.height, VH - y)))
    img.alpha_composite(crop, (x + cx0, y + cy0))


_ORE: dict = {}


def ore_sprite(res, v):
    key = (res, v)
    if key not in _ORE:
        _ORE[key] = load(f"ore_{res}")
    return _ORE[key]
