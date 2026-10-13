"""v9.1 · fumarolas ATIVAS (PROPOSTA, pendente do dono): cones e chaminés de basalto com boca aberta no topo, em 2
estados: dormente (boca escura e fria) e ativa (brilho quente leve no fundo da boca e crosta de enxofre na borda).

Esboço do dono: reports/design/refs/fumarolas_esboco_dono.png (só a ideia das formas: cone baixo e largo com boca,
par de cones com fumaça, chaminé alta e fina com veios escorrendo). Desenho original, no motor de volume das
formações (regions_volume.Volume), na família do cone de escória e do basalto colunar.

Índices: 0..7 rampa HILL do basalto · 8 contorno · 9 sombra · 255 transparente
         10..13 rampa VENT: 10 enxofre escuro, 11 enxofre claro (mudam com o estágio, como mineral),
                            12 brasa, 13 brasa clara (emissivas: fixas nos 4 estágios)
A fumaça NÃO é sprite: é partícula no jogo (ver SMOKE e o report).
"""

from __future__ import annotations

import math

import numpy as np

import regions_core as R
from regions_core import fbm, hash2
from regions_volume import L, Volume, bands, fbm3

VENT = ["#86773a", "#c9b65e", "#b8431e", "#ff9a3c"]    # enxofre escuro, enxofre claro, brasa, brasa clara


def vent_ramp(stage):
    """Rampa de 14 cores: HILL do basalto (0..9) + VENT (10..13). O enxofre segue o estágio, a brasa não."""
    base = R.ramp("basalt", stage, R.HILL)
    sul = [R.stage_color(R.rgb(c), "basalt", stage) for c in VENT[:2]]
    glow = [R.rgb(c) for c in VENT[2:]]
    return np.concatenate([base, np.array(sul + glow, np.uint8)])


# cada boca: (cx, cy, R base, H altura, r topo, r boca, fundo da boca)
SHAPES = {
    "cone": dict(vents=[(0, 0, 22, 15, 8.0, 6.2, 9)], w=60, h=48, ox=30, oy=38, zmax=22,
                 tiles=[(0, 0)], name="Fumarola · cone baixo"),
    "pair": dict(vents=[(-10, -2, 15, 30, 5.5, 4.3, 9), (12, 3, 12, 17, 5.0, 3.9, 7)], w=72, h=64, ox=36, oy=52,
                 zmax=34, tiles=[(0, 0), (1, 0)], name="Fumarola · par de cones"),
    "chimney": dict(vents=[(0, 0, 11, 50, 5.2, 4.0, 10)], w=40, h=78, ox=20, oy=68, zmax=54,
                    tiles=[(0, 0)], name="Fumarola · chaminé"),
}


def _r(X, Y, cx, cy, seed):
    ang = np.arctan2(Y - cy, X - cx)
    return np.sqrt((X - cx) ** 2 + ((Y - cy) * 1.25) ** 2) * (1 + 0.06 * np.sin(3 * ang + seed) + 0.04 * np.sin(7 * ang))


def _profile(r, Rb, H, rt, rm, dm, X, Y, seed):
    """Altura de um cone/chaminé: flanco côncavo do pé até o lábio, lábio, boca afundando até o fundo."""
    k = np.clip((Rb - r) / max(Rb - rt, 1), 0, 1)
    tall = H / Rb                                                   # chaminé: flanco quase reto
    flank = H * (k ** (1.6 if tall < 1.5 else 0.9))
    lip = np.where(r < rt + 0.4, H + 0.6, flank)
    mouth = (H - dm) + dm * np.clip(r / rm, 0, 1) ** 2
    h = np.where(r < rm, mouth, lip)
    gully = np.abs(np.sin(np.arctan2(Y, X) * 7 + 2.0 * fbm(X, Y, 14, seed, 2))) ** 6
    h = h - (1.8 if tall < 1.5 else 1.0) * gully * (r > rt + 1) * (r < Rb - 2)
    return h + 1.2 * fbm(X, Y, 5, seed + 1, 2) * (r > rm)


def vent_h(kind):
    spec = SHAPES[kind]

    def h(X, Y):
        out = np.full(X.shape, -50.0)
        for i, (cx, cy, Rb, H, rt, rm, dm) in enumerate(spec["vents"]):
            r = _r(X, Y, cx, cy, i + 3)
            v = _profile(r, Rb, H, rt, rm, dm, X - cx, Y - cy, 300 + 7 * i)
            out = np.maximum(out, np.where(r < Rb + 0.5, v, -50))
        base = 3.0 - np.sqrt((X / 2.2) ** 2 + (Y / 1.6) ** 2) * 0.35 + 1.2 * fbm(X, Y, 6, 309, 2)  # saia de escória
        out = np.maximum(out, np.where(base > 1.2, base, -50))
        return np.where(out > 0.5, out, -50)
    return h


def vent_shade(kind, active):
    spec = SHAPES[kind]

    def shade(hx, hy, hz, nrm, lit):
        b = bands(nrm @ L, lit)
        b = np.minimum(b, 4)
        sp = hash2(np.round(hx).astype(int), np.round(hy * 2 + hz).astype(int), 311)
        b = np.where((sp < 0.06) & (b > 1), b - 1, b)
        rust = fbm3(hx, hy, hz, 4, 312, 2) > 0.33
        b = np.where(rust & (b >= 2) & (hz > 2), 7, b)
        for i, (cx, cy, Rb, H, rt, rm, dm) in enumerate(spec["vents"]):
            r = _r(hx, hy, cx, cy, i + 3)
            mouth = (r < rm) & (hz < H - 0.3)
            ang = np.arctan2(hy - cy, hx - cx)
            # veios escorrendo do lábio pelo flanco (no dormente: óxido; na ativa: enxofre)
            streak = (np.abs(np.sin(ang * 5 + i * 1.7 + 1.5 * fbm(hx, hy, 9, 320 + i, 1))) > 0.93) \
                & (hz > H * (0.35 + 0.25 * hash2(np.round(ang * 5).astype(int), i, 321))) & (r > rt) & (r < Rb)
            rim = (r >= rm) & (r < rt + 0.8) & (hz > H - 2)
            if not active:
                b = np.where(streak & (b >= 2), 6, b)
                b = np.where(rim & lit, 5, b)
                b = np.where(mouth, np.where(hz > H - dm * 0.45, 1, 0), b)
            else:
                patch = fbm(hx, hy, 3, 330 + i, 2) > 0.45
                crust = (rim & patch) | ((r < rt + 3.0) & (hz > H - 4) & patch & (sp > 0.55))
                b = np.where(streak & (sp > 0.35), 10, b)
                b = np.where(crust, np.where(lit & (sp > 0.4), 11, 10), b)
                b = np.where(rim & ~patch & lit, 5, b)
                deep = hz < H - dm * 0.3
                b = np.where(mouth, np.where(deep, np.where((r < rm * 0.6) & (hz < H - dm * 0.5), 13, 12),
                                             np.where(hz > H - dm * 0.15, 1, 0)), b)
        return b.astype(np.uint8)
    return shade


def vent(kind, active):
    spec = SHAPES[kind]
    v = Volume(spec["w"], spec["h"], spec["ox"], spec["oy"], -2, spec["zmax"],
               lambda X, Y, Z: vent_h(kind)(X, Y) - Z, vent_shade(kind, active), soft_edge=True)
    idx = v.render()
    # boca: ponto de onde sai a fumaça (px do sprite), no meio da boca na altura do lábio
    mouths = [(int(round(spec["ox"] + cx)), int(round(spec["oy"] + cy - H + 1))) for (cx, cy, Rb, H, rt, rm, dm)
              in spec["vents"]]
    # âncora = centro de baixo da pegada (a regra do jogo, geo.Formation.base_px). Pegada 1×1: o pé do volume;
    # par 2×1: a âncora fica no meio dos 2 tiles, que é o (ox, oy) do volume.
    return idx, dict(foot=(spec["ox"], spec["oy"]), tiles=spec["tiles"], size=(len(spec["tiles"]), 1),
                     name=spec["name"], mouths=mouths)


# ---------------------------------------------------------------------------------------------------------------
# FUMAÇA (referência pra partícula do jogo; aqui só pra prévia do report)
# ---------------------------------------------------------------------------------------------------------------
SMOKE = dict(
    rate={"cone": 2.5, "pair": 2.0, "chimney": 3.5},     # puffs por segundo, por boca
    life=(2.6, 3.4),                                     # s
    rise=(16.0, 22.0),                                   # px/s na saída, freia até 35% no fim da vida
    radius=(1.5, 2.5, 7.0, 10.0),                         # raio inicial (min, máx) e final (min, máx), px
    jitter=3.0,                                          # px: tremida lateral (seno lento)
    wind=0.45,                                           # fração do vento da superfície que arrasta o puff
    color=["#e9e4dc", "#c4bdb4", "#958e88"],             # miolo, corpo, borda de baixo (sombra do puff)
    alpha=[150, 110, 70],                                # alfa em degraus (pixel art): <35% vida, <70%, resto
    stage_tint={"storm": "#c9a37e", "arid": None, "mist": "#aab3bb", "green": None},
)


def _hex(c):
    return R.rgb(c)


def smoke_frame(w, h, t, origin, seed=0, kind="cone", wind=(6.0, 0.0), stage="arid", n_max=12, loop=4.0):
    """RGBA (numpy h×w×4) com os puffs no instante t (s), saindo de `origin`. Determinístico e em laço de `loop` s
    (o sorteio de cada puff repete a cada laço, pra prévia emendar)."""
    S = SMOKE
    out = np.zeros((h, w, 4), np.uint8)
    ys, xs = np.mgrid[0:h, 0:w]
    rate = S["rate"][kind]
    period = 1.0 / rate
    cols = [np.array(_hex(c)) for c in S["color"]]
    tint = S["stage_tint"].get(stage)
    if tint:
        cols = [np.round(c * 0.6 + np.array(_hex(tint)) * 0.4).astype(int) for c in cols]
    n_loop = max(1, int(round(rate * loop)))
    t = t % loop + loop * 4                                   # longe do zero: puffs "antigos" já existem
    k0 = int(math.floor(t / period))
    puffs = []
    for k in range(k0 - n_max, k0 + 1):
        born = k * period
        life = S["life"][0] + (S["life"][1] - S["life"][0]) * float(hash2(k % n_loop, 1, seed))
        age = t - born
        if age < 0 or age > life:
            continue
        f = age / life
        v0 = S["rise"][0] + (S["rise"][1] - S["rise"][0]) * float(hash2(k % n_loop, 2, seed))
        rise = v0 * age * (1 - 0.325 * f)
        r0 = S["radius"][0] + (S["radius"][1] - S["radius"][0]) * float(hash2(k % n_loop, 3, seed))
        r1 = S["radius"][2] + (S["radius"][3] - S["radius"][2]) * float(hash2(k % n_loop, 4, seed))
        rad = r0 + (r1 - r0) * (1 - (1 - f) ** 2)
        px = origin[0] + S["wind"] * wind[0] * age + S["jitter"] * math.sin(age * 2.1 + (k % n_loop))
        py = origin[1] - rise + S["wind"] * wind[1] * age
        a = S["alpha"][0] if f < 0.35 else (S["alpha"][1] if f < 0.7 else S["alpha"][2])
        puffs.append((px, py, rad, a))
    for px, py, rad, a in puffs:                          # mais velhos primeiro (ficam atrás)
        d = np.hypot(xs - px, (ys - py) * 1.1)
        body = d <= rad
        if not body.any():
            continue
        core = np.hypot(xs - (px - rad * 0.3), ys - (py - rad * 0.3)) <= rad * 0.55
        low = body & (ys > py + rad * 0.35)
        col = np.where(core[..., None], cols[0], np.where(low[..., None], cols[2], cols[1]))
        m = body
        out[m, :3] = col[m]
        out[m, 3] = np.maximum(out[m, 3], a)
    return out
