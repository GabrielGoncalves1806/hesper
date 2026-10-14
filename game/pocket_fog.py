"""Névoa fria do bolsão da criatura (v0.5 Marco 3 · M3.6.4).

Enquanto a fresta do portão grande não abriu, uma névoa branco-azulada e densa cobre o interior do bolsão: de fora não se
vê o gelo gigante nem a criatura. Tudo é DERIVADO do degelo (o portão grande aberto = sem névoa), nada vai no save: no
load com o portão já aberto não há névoa nem mensagem.

Este módulo tem a regra (`closed`, `hidden_tiles`, usadas pelo mapa do scanner) e o desenho (`PocketFog`, usado pelo
Renderer). O desenho é numa grade baixa (1 célula = CELL px do mundo) com numpy: ruído fbm ladrilhável (o mesmo do
poeira, game/dust.py · fbm_noise) rolando devagar em duas camadas, máscara do interior com a borda suave, e um
smoothscale pro tamanho da tela. Só desenha se o bolsão aparece na tela.
"""

from __future__ import annotations

import numpy as np
import pygame

from game import config as C
from game import ice_blocks, thaw

CELL = 8                     # px do mundo por célula da grade da névoa
NOISE_N = 128                # lado do ladrilho de ruído (células)
SPEED = ((1.1, 0.45), (-0.6, 0.8))       # células/s de cada camada de ruído (devagar, em sentidos diferentes)
FOG_RGB = np.array((196, 218, 236), dtype=np.float32)    # branco-azulado frio
FOG_DARK = np.array((142, 172, 200), dtype=np.float32)   # o miolo das dobras da névoa
EDGE_CELLS = 5               # largura (células) do degradê da borda


def closed(layer) -> bool:
    """O interior do bolsão ainda está escondido? (há bolsão grande e a fresta do portão grande não abriu)"""
    geo = layer.world.geo
    if geo is None or getattr(geo, "giant", None) is None or not layer.gate_ice:
        return False
    return layer.gate_ice[ice_blocks.gate_count(geo) - 1] < thaw.GATE_OPEN


def hidden_tiles(geo) -> frozenset[tuple[int, int]]:
    """Os tiles que o mapa não mostra com o portão fechado: o chão de dentro do anel e a pegada do gelo gigante."""
    g = geo.giant
    return frozenset(g.interior) | frozenset(g.giant.tiles)


class PocketFog:
    """Estado e desenho da névoa. `alpha` vai de 1 (fechado) a 0 (dissipada); ao abrir, cai em C.GIANT_FOG_FADE_S s."""

    def __init__(self) -> None:
        self.key = None                      # id do layer pra que o estado vale (jogo novo/carregado reinicia)
        self.alpha = 0.0
        self._t = None
        self._noise = None
        self._geo_id = None
        self._mask = None                    # (gh, gw) float32 0..1
        self._origin = (0, 0)                # canto do retângulo da grade, em px do mundo
        self._buf = None                     # superfície SRCALPHA gw × gh

    # ---- estado ----
    def update(self, layer, t: float) -> float:
        """Avança o fade pelo relógio `t` (s) e devolve o alfa. Primeira vez que vê este layer: já nasce no estado
        certo (aberto = 0 sem fade, o que cobre o load com o portão aberto)."""
        key = id(layer)
        gap = 0.0 if self._t is None else max(0.0, t - self._t)
        dt = min(C.MAX_DT, gap)
        self._t = t
        shut = closed(layer)
        if key != self.key:
            self.key, self.alpha = key, 1.0 if shut else 0.0
        elif shut:
            self.alpha = 1.0
        elif gap > 1.0:                      # ficou um tempo sem desenhar (estava na caverna): já está dissipada
            self.alpha = 0.0
        else:
            self.alpha = max(0.0, self.alpha - dt / C.GIANT_FOG_FADE_S)
        return self.alpha

    # ---- desenho ----
    def _prepare(self, geo) -> None:
        if self._geo_id == id(geo):
            return
        self._geo_id = id(geo)
        if self._noise is None:
            from game import dust                      # aqui dentro: o dust importa o systems, que importa o layers (ciclo)
            self._noise = np.array(dust.fbm_noise(NOISE_N, seed=4041, periods=(64, 32, 16, 8)), dtype=np.float32)
        g = geo.giant
        x0, y0, w, h = g.outer
        pad = 2                                           # folga em tiles em volta (o gelo gigante sobe além do interior)
        gx0, gy0 = (x0 - pad) * C.TILE, (y0 - pad) * C.TILE
        k = C.TILE // CELL
        gw, gh = (w + 2 * pad) * k, (h + 2 * pad) * k
        mask = np.zeros((gh, gw), dtype=np.float32)
        for tx, ty in g.interior:
            cx, cy = (tx - x0 + pad) * k, (ty - y0 + pad) * k
            mask[cy:cy + k, cx:cx + k] = 1.0
        # a pegada do gelo gigante também (ela pode passar do interior), e um tile de sprite acima dela
        for tx, ty in g.giant.tiles:
            cx, cy = (tx - x0 + pad) * k, (ty - y0 + pad) * k
            mask[max(0, cy - k):cy + k, cx:cx + k] = 1.0
        mask = _blur(mask, EDGE_CELLS)
        self._mask, self._origin = mask, (gx0, gy0)
        self._buf = pygame.Surface((gw, gh), pygame.SRCALPHA)

    def draw(self, canvas: pygame.Surface, geo, cam, t: float, alpha: float) -> None:
        if alpha <= 0 or getattr(geo, "giant", None) is None:
            return
        self._prepare(geo)
        mask, (ox, oy) = self._mask, self._origin
        gh, gw = mask.shape
        vw, vh = canvas.get_size()
        sx, sy = ox - cam[0], oy - cam[1]
        if sx >= vw or sy >= vh or sx + gw * CELL <= 0 or sy + gh * CELL <= 0:
            return                                        # o bolsão não aparece na tela: custo zero
        n = self._noise
        ys, xs = np.arange(gh)[:, None], np.arange(gw)[None, :]
        n1 = _sample(n, ys, xs, t * SPEED[0][1], t * SPEED[0][0])
        n2 = _sample(n, ys * 2, xs * 2, t * SPEED[1][1], t * SPEED[1][0] + 37)
        field = (n1 + n2) * 0.5                           # ~0,2..0,8
        dens = 1.14 + 0.9 * (field - 0.5) - (1.0 - alpha) * 1.3     # dissipa em manchas (os vãos abrem primeiro)
        a = np.clip(dens, 0.0, 1.0) * mask * 0.97
        shade = np.clip((field - 0.35) / 0.35, 0.0, 1.0)[..., None]
        rgb = FOG_DARK + (FOG_RGB - FOG_DARK) * shade     # dobras mais escuras, o resto claro
        buf = self._buf
        pygame.surfarray.pixels3d(buf)[:] = rgb.astype(np.uint8).transpose(1, 0, 2)
        pygame.surfarray.pixels_alpha(buf)[:] = (a * 255).astype(np.uint8).T
        canvas.blit(pygame.transform.smoothscale(buf, (gw * CELL, gh * CELL)), (round(sx), round(sy)))


def _sample(n: np.ndarray, ys, xs, oy: float, ox: float) -> np.ndarray:
    """Ruído ladrilhável `n` amostrado em (ys + oy, xs + ox) com interpolação bilinear (o rolar fica suave, sem saltos
    de célula)."""
    size = n.shape[0]
    fy, fx = oy % size, ox % size
    iy, ix = int(fy), int(fx)
    ty, tx = np.float32(fy - iy), np.float32(fx - ix)
    r0, r1 = (ys + iy) % size, (ys + iy + 1) % size
    c0, c1 = (xs + ix) % size, (xs + ix + 1) % size
    top = n[r0, c0] * (1 - tx) + n[r0, c1] * tx
    bot = n[r1, c0] * (1 - tx) + n[r1, c1] * tx
    return top * (1 - ty) + bot * ty


def _blur(mask: np.ndarray, r: int) -> np.ndarray:
    """Borda suave: média em caixa de raio `r` (duas passadas separáveis) via soma cumulativa."""
    out = mask
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(out, pad), axis=axis, dtype=np.float32)
        n = out.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out
