"""Mockups da TEMPESTADE (v0.4 Marco 1): o jogo de verdade (mundo + HUD B2) com a camada de poeira por cima,
pra cada proposta de cor do tools/sprites/storm_art.py.

    python3 tools/sprites/storm_art.py            # paletas, nuvem, faixas, ícone (assets/sprites/_pending/storm/)
    uv run python tools/sprites/storm_capture.py  # mockups 960×540 (reports/design/tempestade/)

Só LÊ o jogo (não mexe em game/). Sem janela (SDL dummy), save/settings temporários. Determinístico: os grãos e as
faixas saem de um hash fixo, sem random.

A classe DustMock abaixo É a receita proposta pro Dev C (game/dust.py): só pygame, sem numpy, tudo em blits.
    1. máscara pequena (1 px = 1 célula de 4 px, grade presa no mundo como no Lighting), começa toda opaca;
    2. cada fonte de visão (player, cápsula, máquinas) carimba um "buraco" com BLEND_RGBA_MIN (vale o mais claro);
    3. a máscara é esticada 4× sem suavizar;
    4. a nuvem (dust_cloud_*.png, 256×256, emenda) é ladrilhada presa no mundo + deriva do vento e recebe a
       máscara com BLEND_RGBA_MULT; set_alpha(storm × opacidade) e blit no mundo;
    5. faixas (linhas de 1 px, alfa fixo da camada) e grãos (pixels opacos) por cima; a HUD vem depois.
"""

import json
import math
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import save, settings, viewport  # noqa: E402
from game import ui as game_ui  # noqa: E402
from game.app import App  # noqa: E402
from game.objectives import ObjectiveLine  # noqa: E402
from game.systems import Machine  # noqa: E402

settings.SETTINGS_PATH = Path(tempfile.gettempdir()) / "hesper_storm_settings.json"
save.SAVE_PATH = Path(tempfile.gettempdir()) / "hesper_storm_save" / "slot1.json"
PEND = ROOT / "assets" / "sprites" / "_pending" / "storm"
OUT = ROOT / "reports" / "design" / "tempestade"
DT = 1 / 60
T = C.TILE

# ---- números propostos (vão pro report e pro config.py do Dev) ------------------------------------------
CELL = 4                    # célula da máscara (a mesma do Lighting)
OPACITY = 0.90              # opacidade máxima da poeira com storm 1 (rajada: +0.06)
OPACITY_GUST = 0.06
VIEW_TILES = 7.0            # raio de visão do player
VIEW_TILES_GUST = 4.0       # na rajada
POD_TILES = 3.5             # a cápsula abre 3,5 tiles
MACHINE_TILES = 2.5         # cada máquina (menos o baú) abre 2,5 tiles
FACING_BIAS = 10            # px pra onde o player olha (igual à lanterna da caverna)
WIND_DEG = 8               # vento dominante: leste, 8° descendo (no jogo: weather.wind, com variação lenta)
GRAINS, GRAINS_GUST = 200, 250
STREAKS, STREAKS_GUST = 14, 30
STREAK_ALPHA, STREAK_ALPHA_GUST = 140, 180
CLOUD_DRIFT = 40            # px/s que a nuvem anda com o vento (rajada: ×2,5)


# perfil do buraco de visão: (até a distância relativa d, quanto de poeira). Miolo limpo até 55% do raio (7 tiles ->
# ~3,9 limpos) e 3 anéis em degrau até a borda. Fora do raio: poeira cheia.
HOLE_RINGS = ((0.55, 0.0), (0.70, 0.30), (0.85, 0.60), (1.00, 0.85))


def hole_alpha(d: float) -> float:
    for edge, a in HOLE_RINGS:
        if d < edge:
            return a
    return 1.0


def h01(i: int, k: int) -> float:
    n = (i * 374761393 + k * 668265263 + 0x9E3779B9) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n ^= n >> 16
    return (n & 0xFFFFFF) / 0x1000000


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class DustMock:
    """A camada de poeira proposta. render(canvas, cam, storm, gust, sources, t)."""

    def __init__(self, pal: dict, cloud: pygame.Surface):
        self.pal = pal
        self.cloud = cloud.convert()
        self._holes: dict[int, pygame.Surface] = {}

    def hole(self, r: int) -> pygame.Surface:
        """Buraco de visão de raio r células: branco, alfa = 255 × poeira do anel (HOLE_RINGS)."""
        if r not in self._holes:
            s = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
            s.fill((255, 255, 255, 255))
            for j in range(2 * r):
                for i in range(2 * r):
                    a = hole_alpha(math.hypot(i + 0.5 - r, j + 0.5 - r) / r)
                    if a < 1.0:
                        s.set_at((i, j), (255, 255, 255, round(255 * a)))
            self._holes[r] = s
        return self._holes[r]

    def render(self, canvas, cam, storm, gust, sources, t, particles=True):
        if storm <= 0:
            return
        w, h = canvas.get_size()
        ox, oy = -int(cam[0] % CELL), -int(cam[1] % CELL)
        sw, sh = (w - ox + CELL - 1) // CELL, (h - oy + CELL - 1) // CELL
        mask = pygame.Surface((sw, sh), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 255))
        for x, y, radius in sources:                       # (x, y, raio) em px do mundo
            sx, sy = x - cam[0], y - cam[1]
            r = max(1, round(radius / CELL))
            gx, gy = int((sx - ox) // CELL), int((sy - oy) // CELL)
            mask.blit(self.hole(r), (gx - r, gy - r), special_flags=pygame.BLEND_RGBA_MIN)
        big = pygame.transform.scale(mask, (sw * CELL, sh * CELL))
        dust = pygame.Surface(big.get_size(), pygame.SRCALPHA)
        drift = CLOUD_DRIFT * (1 + 1.5 * gust) * t
        wx, wy = math.cos(math.radians(WIND_DEG)), math.sin(math.radians(WIND_DEG))
        cx = int(cam[0] + ox - drift * wx) % 256        # nuvem presa no mundo + deriva (px inteiro)
        cy = int(cam[1] + oy - drift * wy) % 256
        for ty in range(-cy, dust.get_height(), 256):
            for tx in range(-cx, dust.get_width(), 256):
                dust.blit(self.cloud, (tx, ty))
        dust.blit(big, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        dust.set_alpha(round(255 * storm * min(1.0, OPACITY + OPACITY_GUST * gust)))
        canvas.blit(dust, (ox, oy))
        if particles:
            self.particles(canvas, cam, storm, gust, t)

    def particles(self, canvas, cam, storm, gust, t):
        w, h = canvas.get_size()
        a = math.radians(WIND_DEG)
        wx, wy = math.cos(a), math.sin(a)
        # faixas: linhas de 1 px na direção do vento, desenhadas opacas numa camada com colorkey e coladas
        # com UM alfa fixo (pixel art: um nível só)
        layer = pygame.Surface((w, h))
        layer.fill((255, 0, 255))
        layer.set_colorkey((255, 0, 255))
        sc = rgb(self.pal["streak"])
        n = round((STREAKS + (STREAKS_GUST - STREAKS) * gust) * storm)
        speed = 380 * (1 + 0.8 * gust)
        for i in range(n):
            ln = (40 + 80 * h01(i, 1)) * (1 + 0.6 * gust)
            span = w + 2 * ln
            x = (h01(i, 2) * span + speed * (0.8 + 0.4 * h01(i, 3)) * t) % span - ln
            y = (h01(i, 4) * (h + 80) + speed * wy / wx * 0.6 * t) % (h + 80) - 40
            gap = h01(i, 5)
            ex, ey = x + wx * ln, y + wy * ln
            if gap < 0.5:                                   # metade das faixas é quebrada: "—— ——————"
                f = 0.2 + 0.25 * h01(i, 6)
                pygame.draw.line(layer, sc, (x, y), (x + wx * ln * f, y + wy * ln * f))
                f2 = f + 0.08
                pygame.draw.line(layer, sc, (x + wx * ln * f2, y + wy * ln * f2), (ex, ey))
            else:
                pygame.draw.line(layer, sc, (x, y), (ex, ey))
        layer.set_alpha(round(STREAK_ALPHA + (STREAK_ALPHA_GUST - STREAK_ALPHA) * gust))
        canvas.blit(layer, (0, 0))
        # grãos: pixels opacos, 3 tons (claro 60%, brilho 15%, escuro 25%); 1×1, 2×1, e 3×1 na rajada
        light, bright, dark = (rgb(c) for c in self.pal["grains"])
        n = round((GRAINS + (GRAINS_GUST - GRAINS) * gust) * storm)
        gspeed = 260 * (1 + 0.7 * gust)
        for i in range(n):
            k = h01(i, 11)
            col = light if k < 0.6 else bright if k < 0.75 else dark
            v = gspeed * (0.6 + 0.8 * h01(i, 12))
            x = (h01(i, 13) * (w + 8) + v * wx * t) % (w + 8) - 4
            y = (h01(i, 14) * (h + 8) + v * wy * t + 3 * math.sin(t * 2 + i)) % (h + 8) - 4
            ln = 1 if h01(i, 15) < 0.7 else 2
            if gust > 0.5 and h01(i, 16) < 0.5:
                ln += 1
            canvas.fill(col, (int(x), int(y), ln, 1))


def anim_layers(pal, gust):
    """Pro report (animação em CSS): grãos e faixas em camadas transparentes 960×540 que emendam nas bordas,
    com o mesmo desenho do DustMock.particles. As faixas já saem com o alfa fixo da camada."""
    w, h = C.SCREEN_W, C.SCREEN_H
    a = math.radians(WIND_DEG)
    wx, wy = math.cos(a), math.sin(a)
    streaks = pygame.Surface((w, h), pygame.SRCALPHA)
    sc = (*rgb(pal["streak"]), round(STREAK_ALPHA + (STREAK_ALPHA_GUST - STREAK_ALPHA) * gust))
    n = round(STREAKS + (STREAKS_GUST - STREAKS) * gust)
    for i in range(n):
        ln = (40 + 80 * h01(i, 1)) * (1 + 0.6 * gust)
        x, y = h01(i, 2) * w, h01(i, 4) * h
        segs = [(0.0, 1.0)] if h01(i, 5) >= 0.5 else [(0.0, 0.2 + 0.25 * h01(i, 6)), (0.28 + 0.25 * h01(i, 6), 1.0)]
        for ddx in (0, -w):
            for ddy in (0, -h):
                for f0, f1 in segs:
                    pygame.draw.line(streaks, sc, (x + ddx + wx * ln * f0, y + ddy + wy * ln * f0),
                                     (x + ddx + wx * ln * f1, y + ddy + wy * ln * f1))
    grains = pygame.Surface((w, h), pygame.SRCALPHA)
    light, bright, dark = (rgb(c) for c in pal["grains"])
    for i in range(round(GRAINS + (GRAINS_GUST - GRAINS) * gust)):
        k = h01(i, 11)
        col = light if k < 0.6 else bright if k < 0.75 else dark
        ln = 1 if h01(i, 15) < 0.7 else 2
        if gust > 0.5 and h01(i, 16) < 0.5:
            ln += 1
        grains.fill(col, (int(h01(i, 13) * w), int(h01(i, 14) * h), ln, 1))
    return grains, streaks


# ---- cena -----------------------------------------------------------------------------------------------
def frames(app, seconds):
    for _ in range(max(1, round(seconds / DT))):
        app.step(DT)


def put(state, kind, tile):
    m = Machine(kind, tile[0], tile[1], 0)
    if m.is_chest:
        m.name = C.CHEST_DEFAULT_NAME
    state.machines.append(m)
    state.transition_sources.add(tuple(tile))


def sources_for(state, view_tiles, base=True):
    p = state.player
    dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[p.facing]
    out = [(p.x + dx * FACING_BIAS, p.y - 18 + dy * FACING_BIAS, view_tiles * T)]
    if base:
        out.append((C.POD_ANCHOR[0], C.POD_ANCHOR[1] - 24, POD_TILES * T))
        for m in state.machines:
            if m.is_chest:
                continue
            out.append((m.tx * T + T / 2, m.ty * T + T / 2 - 8, MACHINE_TILES * T))
    return out


def rajada_chip(ui):
    """Aviso RAJADA (mockup do que a trilha B desenha): pílula do estilo B2 à direita do O₂, ícone de vento 8×8."""
    glyph = json.loads((PEND / "storm_palettes.json").read_text())["wind_glyph"]
    x, y = 6 + 132 + 4, 6
    w = 8 + 8 + 4 + ui.font.size("RAJADA")[0] + 6
    ui.hud_panel(x, y, w, 17)
    ui.fill(C.C_ACCENT, (x, y + 2, 1, 13))
    c = pygame.Color(C.C_ACCENT)
    for dy, row in enumerate(glyph):
        for dx, ch in enumerate(row):
            if ch == "#":
                ui.surf.fill(c, (x + 6 + dx, y + 5 + dy, 1, 1))
    ui.tx("RAJADA", x + 18, y + 1, C.C_ACCENT)


def static_noise(surf, amount, seed):
    """Chiado de mentira no minimapa (o de verdade é a C3 do Dev): pixels claros/escuros + 2 linhas."""
    w, h = surf.get_size()
    n = int(w * h * 0.10 * amount)
    for i in range(n):
        x, y = int(h01(i + seed, 21) * w), int(h01(i + seed, 22) * h)
        v = 225 if h01(i + seed, 23) < 0.5 else 18
        surf.fill((v, v, v), (x - x % 2, y - y % 2, 2, 2))
    for j in range(2):
        y = int(h01(seed, 30 + j) * h) // 2 * 2
        surf.fill((200, 200, 200), (0, y, w, 2))
    return surf


def main():
    (OUT / "anim").mkdir(parents=True, exist_ok=True)
    data = json.loads((PEND / "storm_palettes.json").read_text())
    pals = data["palettes"]
    save.SAVE_PATH.unlink(missing_ok=True)
    app = App(scale=1)
    frames(app, 0.3)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="", scancode=0))
    frames(app, DT)
    pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN, mod=0, unicode="", scancode=0))
    frames(app, 0.5)
    s = app.state
    s.equipment.equip("scanner")
    for kind, tile in [("o2", (93, 98)), ("melter", (99, 98)), ("chest", (97, 100)),
                       ("heater", (100, 96)), ("solar", (94, 101))]:
        put(s, kind, tile)
    s.indices.update(o2=620.0, heat=180.0, water=140.0)

    # HUD do Marco 1 (mockup): próximo estágio é o ÁRIDO (Ti 2.500) e o objetivo novo
    arid = SimpleNamespace(name="ÁRIDO")
    game_ui.stage_progress = lambda ti: (arid, min(1.0, ti / 2500), max(0.0, 2500 - ti))
    app.objectives.lines = lambda state: [ObjectiveLine("Sobreviva e monte a base", "current"),
                                          ObjectiveLine("Limpe o céu (Árido)", "next")]

    scene = {"dust": None, "storm": 0.0, "gust": 0.0, "sources": [], "t": 0.0, "chip": False}
    orig_present = app.present

    def present():
        if scene["dust"] is not None:
            if scene.get("anim"):                          # base da animação do report: sem grãos/faixas
                base = app.canvas.copy()
                scene["dust"].render(base, app.cam, scene["storm"], scene["gust"], scene["sources"], scene["t"],
                                     particles=False)
                pygame.image.save(base, str(OUT / scene["anim"]))
            scene["dust"].render(app.canvas, app.cam, scene["storm"], scene["gust"], scene["sources"], scene["t"])
        orig_present()
    app.present = present

    orig_hud = app.ui.draw_hud

    def draw_hud(*a, **k):
        orig_hud(*a, **k)
        if scene["chip"]:
            rajada_chip(app.ui)
    app.ui.draw_hud = draw_hud

    orig_mm = app.ui.draw_minimap

    def draw_minimap(state, tex, t, item_icon=None):
        if scene["gust"] > 0:
            tex = static_noise(tex.copy(), scene["gust"], 7)
        orig_mm(state, tex, t, item_icon)
    app.ui.draw_minimap = draw_minimap

    def place(px, py, facing):
        s.player.x, s.player.y = (px + 0.5) * T, (py + 1) * T - 2
        s.player.direction = facing
        s.player.moving = True
        frames(app, 0.4)
        s.player.x, s.player.y = (px + 0.5) * T, (py + 1) * T - 2
        s.player.direction = facing

    app.ui.draw_cursor = lambda *a, **k: None               # sem o cursor do mouse no meio da cena
    app.ui.draw_floaters = lambda *a, **k: None             # nem os "+ÁGUA" das máquinas (variam entre as fotos)

    def shot(name):
        app.banner_time = 999.0                               # sem o banner de estágio
        app.draw()
        pygame.image.save(app.frame, str(OUT / name))
        print("  ", name)

    # cenas: "longe" = a oeste da base, com a cratera (marco do mapa) dentro da visão e a base no limite da tela
    cr = s.world.crater or (C.POD_TILES[0][0] - 16, C.POD_TILES[0][1] + 1)
    far_spot = (cr[0] - 3, cr[1] + 2)
    base_spot = (104, 96)

    # Árido limpo (uma vez só): o chão dead de hoje, sem poeira
    place(*far_spot, "right")
    scene.update(dust=None, chip=False, gust=0.0)
    game_ui.stage_progress = lambda ti: (SimpleNamespace(name="NÉVOA"), min(1.0, (ti + 2600) / 10000),
                                         max(0.0, 10000 - ti - 2600))
    app.objectives.lines = lambda state: [ObjectiveLine("Fabrique um Aquecedor", "current")]
    shot("arido.png")
    game_ui.stage_progress = lambda ti: (arid, min(1.0, ti / 2500), max(0.0, 2500 - ti))
    app.objectives.lines = lambda state: [ObjectiveLine("Sobreviva e monte a base", "current"),
                                          ObjectiveLine("Limpe o céu (Árido)", "next")]

    for key, pal in pals.items():
        dust = DustMock(pal, pygame.image.load(str(PEND / f"dust_cloud_{key}.png")))
        place(*far_spot, "right")
        scene.update(dust=dust, storm=1.0, gust=0.0, chip=False, t=3.0, sources=sources_for(s, VIEW_TILES),
                     anim=f"anim/{key}_tempestade_base.png")
        shot(f"{key}_tempestade.png")
        scene["anim"] = None
        place(*far_spot, "left")                            # andando contra o vento
        scene.update(gust=1.0, chip=True, t=3.0, sources=sources_for(s, VIEW_TILES_GUST),
                     anim=f"anim/{key}_rajada_base.png")
        shot(f"{key}_rajada.png")
        scene["anim"] = None
        for g, tag in ((0.0, "normal"), (1.0, "rajada")):
            grains, streaks = anim_layers(pal, g)
            pygame.image.save(grains, str(OUT / "anim" / f"{key}_graos_{tag}.png"))
            pygame.image.save(streaks, str(OUT / "anim" / f"{key}_faixas_{tag}.png"))
        if key == "a":                                      # o aviso RAJADA de perto (HUD em cima à esquerda)
            pygame.image.save(app.frame.subsurface((0, 0, 420, 56)), str(OUT / "hud_rajada_crop.png"))
        place(*base_spot, "left")
        scene.update(gust=0.0, chip=False, t=5.0, sources=sources_for(s, VIEW_TILES))
        shot(f"{key}_base.png")
        # transição pro Árido: storm 0,5 (metade dos 20 s)
        place(*far_spot, "right")
        scene.update(storm=0.5, gust=0.0, t=7.0, sources=sources_for(s, VIEW_TILES))
        shot(f"{key}_transicao.png")
    print("ok")


if __name__ == "__main__":
    main()
