"""Captura o gameplay do trailer: roda o jogo SEM JANELA (driver dummy do SDL, como o tools/dev/smoke.py),
roteirizado, e salva cada cena como sequência de PNG + um clipe MP4 pro Remotion.

    uv run python marketing/trailer/capture.py            # todas as cenas
    uv run python marketing/trailer/capture.py storm gate # só essas

Saída:
    marketing/trailer/frames/<cena>/00000.png ...          (960×540, brutos; gitignored)
    marketing/trailer/video/public/clips/<cena>.mp4        (1920×1080, 30 fps, escala nearest-neighbor)

Câmera: o script desenha só o MUNDO (renderer.draw), sem HUD, com câmera própria (centro em px do mundo e zoom
fracionário, pan suave com subpixel). Tudo determinístico: seed 7, dt fixo de 1/30 s, sem rajada nem chuva
sorteadas (as cenas ligam o clima na mão), random do Python com seed fixa.
"""

import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from game import config as C  # noqa: E402
from game import save, settings, worlds  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="hesper_trailer_"))
settings.SETTINGS_PATH = TMP / "settings.json"     # nunca mexe no settings.json nem nos saves de verdade
save.SAVE_PATH = TMP / "saves" / "slot1.json"
worlds.SAVES_DIR = save.SAVE_PATH.parent

# clima só na mão (igual ao smoke): uma rajada/pancada sorteada no meio de uma cena estraga o take
C.STORM_GUST_FIRST = C.STORM_GUST_EVERY = (1e9, 1e9)
C.RAIN_FIRST = C.RAIN_MIST_EVERY = C.RAIN_GREEN_EVERY = (1e9, 1e9)

from game.app import App  # noqa: E402
from game.systems import Controls, Machine  # noqa: E402

# Gelo gigante (EM BREVE): a variação pendente que entra no trailer. O dono ainda escolhe entre "cocoon" (casulo)
# e "larva": troque só aqui e rode `capture.py giant` de novo.
GIANT_VARIANT = "cocoon"
GIANT_DIR = ROOT / "reports" / "design" / "gelo_gigante" / "pendentes"

FPS = 30
DT = 1 / FPS
OUT_W, OUT_H = 960, 540            # frames brutos; o MP4 sai 2× (1920×1080) com nearest-neighbor
FRAMES = HERE / "frames"
CLIPS = HERE / "video" / "public" / "clips"
T = C.TILE


def ease(x: float) -> float:
    """ease-in-out (cosseno), 0..1."""
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def lerp(a, b, x):
    return a + (b - a) * x


class Director:
    """Liga o App sem janela e grava takes com câmera própria."""

    def __init__(self):
        random.seed(1806)
        self.app = App(scale=1, skip_title=True)
        self.app.mode = "play"
        self.state = self.app.state
        self.r = self.app.renderer
        self.ctrl = Controls()
        self.app.controls = lambda: self.ctrl          # o roteiro manda no player (sem teclado nem mouse)
        self.view = None
        self.out = pygame.Surface((OUT_W, OUT_H))
        self.overlay = None                              # função(surface, i, n) desenhada por cima (efeitos extras)
        self.world_fx = None                             # função(view, cam_x, cam_y): desenha no mundo (px do mundo)
        self.r.draw_zone = lambda *a, **k: None          # sem o círculo tracejado da zona da base (é HUD de jogo)
        self.r.draw_machine_status = lambda *a, **k: None   # sem barrinha de drill nem anel de "sem energia"

    # ---- simulação ----
    def tick(self, n: int = 1) -> None:
        for _ in range(n):
            self.app.handle_events()
            self.app.update(DT)
            self.state.o2 = C.O2_MAX                     # ninguém desmaia no trailer

    def warm(self, seconds: float) -> None:
        self.tick(max(1, round(seconds * FPS)))

    def teleport(self, tile, dy: float = 0) -> None:
        p = self.state.player
        p.x, p.y = (tile[0] + 0.5) * T, (tile[1] + 1) * T - 2 + dy

    # ---- câmera ----
    def render(self, cx: float, cy: float, zoom: float) -> pygame.Surface:
        """Desenha o mundo com o centro da câmera em (cx, cy) px do mundo e `zoom` px de tela por px do mundo."""
        vw, vh = OUT_W / zoom, OUT_H / zoom
        x0, y0 = cx - vw / 2, cy - vh / 2
        ix, iy = math.floor(x0), math.floor(y0)
        rw, rh = math.ceil(vw) + 2, math.ceil(vh) + 2
        if self.view is None or self.view.get_size() != (rw, rh):
            self.view = pygame.Surface((rw, rh), 0, self.app.canvas)
        self.r.draw(self.view, self.state, (ix, iy), self.app.t, None)
        if self.world_fx:
            self.world_fx(self.view, ix, iy)
        sw, sh = round(rw * zoom), round(rh * zoom)
        big = self.view if (sw, sh) == (rw, rh) else pygame.transform.scale(self.view, (sw, sh))
        self.out.fill((0, 0, 0))
        self.out.blit(big, (-round((x0 - ix) * zoom), -round((y0 - iy) * zoom)))
        return self.out

    def take(self, name: str, seconds: float, cam, step=None) -> None:
        """Grava `seconds` de take. `cam(u) -> (cx, cy, zoom)` com u de 0 a 1; `step(i, u)` mexe no estado antes
        de cada quadro (andar, minerar, subir calor...)."""
        n = round(seconds * FPS)
        folder = FRAMES / name
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        for i in range(n):
            u = i / max(1, n - 1)
            if step:
                step(i, u)
            self.tick()
            surf = self.render(*cam(u))
            if self.overlay:
                self.overlay(surf, i, n)
            pygame.image.save(surf, str(folder / f"{i:05d}.png"))
        self.overlay = self.world_fx = None
        self.ctrl = Controls()
        encode(name)
        print(f"  {name}: {n} quadros ({seconds:g} s)")


def encode(name: str) -> None:
    CLIPS.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FRAMES / name / "%05d.png"),
                    "-vf", "scale=1920:1080:flags=neighbor", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(CLIPS / f"{name}.mp4")], check=True)


# =====================================================================================================================
# utilidades das cenas
# =====================================================================================================================
def set_weather(state, gust: float, angle: float = 20.0) -> None:
    """Vento preso numa direção e rajada na força pedida (0..1), sem fim (igual ao smoke.set_weather)."""
    w = state.weather
    w.dominant = w.angle = w.target = angle
    w.retarget_in = 1e9
    w._update_wind_vector()
    w.gust, w.gust_left = gust, (1e9 if gust > 0 else 0.0)
    w._recompute(storm=state.storm)


def arid(d: Director) -> None:
    s = d.state
    s.stage, s.storm = C.ARID_STAGE, 0.0
    s.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti), heat=0.0, water=0.0)
    set_weather(s, 0.0)


def place(d: Director, kind: str, tile, **kw) -> Machine:
    m = Machine(kind, tile[0], tile[1], **kw)
    if m.is_station:
        from game import drones
        m.station = drones.new_station(m, kw.pop("drones", 2) if "drones" in kw else 2)
    d.state.machines.append(m)
    if d.state.active.has_base:
        d.state.transition_sources.add(tuple(tile))
    return m


def dust_ring(view, cx, cy, age: float, color=(196, 128, 86)) -> None:
    """Anel de poeira em pixel art (círculos sem suavizar com alfa), expandindo com `age` (0..1)."""
    if not 0 <= age <= 1:
        return
    rnd = random.Random(7)
    layer = pygame.Surface(view.get_size(), pygame.SRCALPHA)
    for k in range(46):
        a = rnd.uniform(0, math.tau)
        sp = rnd.uniform(0.55, 1.0)
        rad = 14 + 74 * sp * (1 - (1 - age) ** 2.2)
        x = cx + math.cos(a) * rad
        y = cy + math.sin(a) * rad * 0.45
        size = max(1, round(lerp(rnd.uniform(4, 9), 2, age)))
        alpha = int(170 * (1 - age))
        pygame.draw.circle(layer, (*color, alpha), (round(x), round(y)), size)
    view.blit(layer, (0, 0))


def pop_fx(view, x, y, age: float) -> None:
    """Brilho rápido quando uma máquina aparece (anel claro que abre e some)."""
    if not 0 <= age <= 1:
        return
    layer = pygame.Surface(view.get_size(), pygame.SRCALPHA)
    r = round(6 + 22 * ease(age))
    pygame.draw.circle(layer, (255, 236, 200, int(200 * (1 - age))), (round(x), round(y)), r, 2)
    pygame.draw.ellipse(layer, (255, 220, 170, int(90 * (1 - age))), (round(x - r), round(y - r * 0.35), 2 * r, round(r * 0.7)))
    view.blit(layer, (0, 0))


# =====================================================================================================================
# cenas
# =====================================================================================================================
def scene_landing(d: Director) -> None:
    """0–12 s do trailer: a câmera passeia pela tempestade, a cápsula cai e bate no chão EXATAMENTE em 9,6 s (o baque
    da trilha), levanta poeira e o Explorador sai."""
    s, r = d.state, d.r
    s.stage, s.storm = C.STORM_STAGE, 1.0
    set_weather(s, 0.25, 25.0)
    ax, ay = C.POD_ANCHOR
    state = {"drop": -3000.0, "hide": True, "impact": None, "i": 0}
    pod = r._draw_pod
    player = r._draw_player
    r._draw_pod = lambda canvas, x, y, t: pod(canvas, x, y + state["drop"], t)
    r._draw_player = lambda canvas, st, x, y, t: None if state["hide"] else player(canvas, st, x, y, t)
    d.teleport((C.BASE_TILE[0], C.BASE_TILE[1]))
    d.warm(1.0)
    seconds, t_fall, t_land = 12.0, 8.0, 9.6
    n = round(seconds * FPS)

    def step(i, u):
        state["i"] = i
        t = i / FPS
        if t < t_fall:
            state["drop"] = -3000.0
        else:
            x = min(1.0, (t - t_fall) / (t_land - t_fall))
            state["drop"] = -620 * (1 - x * x)
        if t >= t_land and state["impact"] is None:
            state["impact"] = i
        if t > 10.3:
            if state["hide"]:
                state["hide"] = False
                s.player.x, s.player.y = ax + 2, ay + 22
            d.ctrl = Controls(0.0, 0.6 if t < 10.9 else 0.0)
        set_weather(s, 0.25 + 0.55 * ease((t - 10.8) / 1.0), 25.0)

    def shadow(view, cx, cy):
        if -620 <= state["drop"] < 0:
            x = 1 - state["drop"] / -620
            w = round(lerp(10, 58, x))
            sh = pygame.Surface((w, max(2, w // 4)), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (20, 8, 4, int(lerp(30, 120, x))), sh.get_rect())
            view.blit(sh, (ax - cx - w // 2, ay - cy - 4))
        if state["impact"] is not None:
            dust_ring(view, ax - cx, ay - cy - 4, (state["i"] - state["impact"]) / (1.4 * FPS))

    d.world_fx = shadow

    def cam(u):
        t = u * seconds
        shake = 0.0
        if state["impact"] is not None:
            k = (state["i"] - state["impact"]) / FPS
            shake = 6 * math.exp(-k * 7) * math.sin(k * 70)
        travel = ease(t / t_fall)                        # passeio pela poeira até o ponto do pouso
        follow = max(state["drop"], -620) * 0.8 if state["drop"] > -3000 else -496
        settle = 30 * ease((t - t_land) / 1.5)            # depois do pouso a câmera desce um pouco (o player sai)
        x = lerp(ax - 420, ax, travel)
        y = lerp(ay - 700, ay - 40 + follow, travel)
        if t >= t_fall:
            y = ay - 40 + follow + settle
        return x + shake * 0.6, y + shake, lerp(1.5, 2.0, ease(t / t_land)) + 0.5 * ease((t - t_land) / 2.4)
    d.take("landing", seconds, cam, step)


def scene_storm_walk(d: Director) -> None:
    """O Explorador anda contra a rajada; a visão fecha pra 4 tiles."""
    s = d.state
    s.stage, s.storm = C.STORM_STAGE, 1.0
    spot = (C.BASE_TILE[0] + 10, C.BASE_TILE[1] + 3)
    d.teleport(spot)
    set_weather(s, 0.0, 200.0)
    d.warm(1.0)

    def step(i, u):
        set_weather(s, ease((u - 0.25) / 0.25), 200.0)        # vento soprando pra esquerda; ele anda pra direita
        d.ctrl = Controls(1.0, -0.15)

    p = s.player
    d.take("storm_walk", 5.0, lambda u: (p.x, p.y - 20, lerp(2.6, 3.0, u)), step)


def scene_mine(d: Director) -> None:
    """Minerando rochas com veio (ferro), lasquinhas voando."""
    arid(d)
    s = d.state
    rock = (98, 105)
    d.teleport((rock[0], rock[1] + 1))
    s.player.direction = "up"
    d.warm(0.4)
    targets = [rock]
    nxt = [(96, 104), (100, 104)]
    from game import config as CC
    w = s.world
    for t, k in zip(nxt, (CC.SMALL_SILICON, CC.SMALL_ICE)):
        if w.is_floor(*t):
            w.set(*t, k)
            targets.append(t)

    def step(i, u):
        tgt = next((t for t in targets if w.get(*t) in C.SMALL_ROCKS), None)
        d.ctrl = Controls(0, 0, tgt)

    p = s.player
    d.take("mine", 3.5, lambda u: (rock[0] * T + 16, rock[1] * T + 4, lerp(2.6, 3.0, ease(u))), step)


def scene_magma(d: Director) -> None:
    """Basalto: as fumarolas dormentes acordam com o calor (fumaça e brasa) e a magmatita pulsa."""
    arid(d)
    s = d.state
    vents = s.surface.geo.vents
    a, b = vents[0].base_px, vents[1].base_px
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 30
    d.teleport((int(cx // T) - 1, int(cy // T) + 3))
    s.player.direction = "up"
    d.warm(0.5)

    def step(i, u):
        if u > 0.22 and s.indices["heat"] == 0:
            s.indices["heat"] = float(C.THAW_FUMAROLE_HEAT[1])
        d.ctrl = Controls(0.4 if 0.45 < u < 0.8 else 0.0, 0.0)

    d.take("magma", 6.0, lambda u: (cx + lerp(-30, 30, u), cy + 30, lerp(2.0, 2.3, u)), step)


def scene_base(d: Director) -> None:
    """A base crescendo: as máquinas vão aparecendo em volta da cápsula, todas animadas."""
    arid(d)
    s = d.state
    bx, by = C.BASE_TILE
    plan = [("solar", (bx - 6, by + 4)), ("solar", (bx - 4, by + 4)), ("o2", (bx - 3, by + 1)),
            ("heater", (bx + 3, by + 1)), ("melter", (bx + 5, by + 3)), ("solar", (bx - 2, by + 4)),
            ("o2_t2", (bx - 5, by + 1)), ("chest", (bx + 1, by + 3)), ("heater_t2", (bx + 7, by + 1)),
            ("lamp_t2", (bx - 1, by - 2)), ("melter_t2", (bx + 7, by + 4)), ("drone_station", (bx + 2, by + 5))]
    d.teleport((bx + 1, by + 1))
    s.player.direction = "down"
    d.warm(0.4)
    n = round(7.0 * FPS)
    times = [round(n * (0.06 + 0.055 * k)) for k in range(len(plan))]
    born = {}

    def step(i, u):
        for k, (kind, tile) in enumerate(plan):
            if i == times[k]:
                m = place(d, kind, tile)
                born[id(m)] = (i, m)
        d.ctrl = Controls(-0.6 if 0.55 < u < 0.8 else 0.0, 0.0)

    def fx(view, cx, cy):
        for i0, m in born.values():
            ax, ay = m.anchor
            pop_fx(view, ax - cx, ay - cy - 10, (cur["i"] - i0) / (0.4 * FPS))

    cur = {"i": 0}
    d.world_fx = fx

    def step2(i, u):
        cur["i"] = i
        step(i, u)

    d.take("base", n / FPS, lambda u: (bx * T + 24, by * T + 70, lerp(2.4, 1.6, ease(u))), step2)


def scene_drones(d: Director) -> None:
    """Drill no veio + estação + baú: os drones levam o minério voando."""
    from game import drones
    arid(d)
    s = d.state
    w = s.world
    vein = min(w.veins, key=lambda v: math.hypot(v.tx - 96, v.ty - 96))
    vx, vy = vein.tx, vein.ty
    drill = place(d, "drill", (vx, vy), resource=vein.resource)
    drill.sends = {vein.resource}
    drill.batch = 4
    drill.stored = 20

    def free(t, size=1):
        return all(w.is_floor(t[0] + i, t[1] + j) and not w.vein_at(t[0] + i, t[1] + j)
                   for i in range(size) for j in range(size))
    cands = sorted(((x, y) for y in range(vy - 6, vy + 10) for x in range(vx - 12, vx + 14)
                    if free((x, y), 2) and math.hypot(x - vx, y - vy) > 6), key=lambda t: abs(t[0] - (vx + 8)) + abs(t[1] - (vy + 3)))
    st_tile = cands[0]
    station = place(d, "drone_station", st_tile)
    station.station = drones.new_station(station, 3)
    chest_tile = next(t for t in sorted(((x, y) for y in range(vy - 6, vy + 10) for x in range(vx - 14, vx + 16) if free((x, y))),
                                        key=lambda t: abs(t[0] - (vx + 12)) + abs(t[1] - (vy + 5)))
                      if abs(t[0] - st_tile[0]) > 2 or abs(t[1] - st_tile[1]) > 2)
    chest = place(d, "chest", chest_tile)
    for r_ in C.RESOURCES:
        drones.toggle_receive(chest, r_)
    for k, t in enumerate([(st_tile[0] - 2, st_tile[1] + 3), (st_tile[0], st_tile[1] + 3), (st_tile[0] + 2, st_tile[1] + 3)]):
        if free(t):
            place(d, "solar", t)
    print(f"    veio {vein.resource} {vx},{vy} · estação {st_tile} · baú {chest_tile}")
    d.teleport((vx + 3, vy + 3))
    d.warm(1.0)
    mx, my = ((vx + 1) * T + (st_tile[0] + 1) * T) / 2, ((vy + 1) * T + (st_tile[1] + 1) * T) / 2 - 20

    def step(i, u):
        drill.stored = max(drill.stored, 12)

    ex = ((st_tile[0] + 1) * T + (chest_tile[0] + 0.5) * T) / 2
    d.take("drones", 6.0, lambda u: (lerp(mx - 20, (mx + ex) / 2, ease(u)), my + 20, lerp(1.9, 1.75, u)), step)


def scene_crater(d: Director) -> None:
    """O calor derrete a tampa de gelo da cratera (etapas 0 → 4) e a rampa aparece."""
    arid(d)
    s = d.state
    tx, ty = s.world.crater
    cx, cy = tx * T + 48, ty * T + 40
    d.teleport((tx + 4, ty + 2))
    s.player.direction = "left"
    d.warm(0.5)

    def step(i, u):
        s.indices["heat"] = lerp(0.0, float(C.THAW_CRATER_HEAT[-1]) + 1, ease(min(1.0, u / 0.85)))

    d.take("crater", 5.0, lambda u: (cx, cy, lerp(2.6, 3.1, ease(u))), step)


def scene_cave(d: Director) -> None:
    """Caverna escura: só a lanterna do capacete, minério brilhando e umas luminárias."""
    from game import layers
    s = d.state
    s.enter_layer("cave")
    cave = s.world
    # chão com mais minério em volta (igual ao smoke.cave_spot)
    def score(x, y):
        return sum(cave.get(xx, yy) in C.ORE_TILES for yy in range(y - 6, y + 7) for xx in range(x - 10, x + 11))
    spots = [(x, y) for y in range(8, cave.height - 8, 2) for x in range(8, cave.width - 8, 2)
             if all(cave.is_floor(x + i, y) for i in range(-6, 1)) and cave.is_floor(x, y - 1)
             and 12 <= cave.dist_from_center(x, y) <= 30]
    spot = max(spots, key=lambda t: score(*t))
    d.teleport((spot[0] - 6, spot[1]))
    s.player.direction = "right"
    d.warm(0.5)
    p = s.player
    start = (p.x, p.y)

    def step(i, u):
        d.ctrl = Controls(0.55 if u < 0.85 else 0.0, 0.0)

    d.take("cave", 6.0, lambda u: (start[0] + 60 + lerp(0, 150, u), start[1] - 24, 2.6), step)


def scene_gate(d: Director) -> None:
    """O gelo-portão em blocos derrete com o calor, a fresta abre e o Explorador passa."""
    from game import ice_blocks
    arid(d)
    s = d.state
    p0 = s.surface.geo.pockets[0]
    gate = p0.gate
    bx, by = gate.base_px
    lo, hi = C.THAW_GATE_HEAT[0][0], C.THAW_GATE_HEAT[0][-1]

    def heat(v):
        s.indices.update(o2=float(C.STAGES[C.ARID_STAGE - 1].ti) - v, heat=float(v))

    heat(lo)
    d.teleport((gate.tx + 2, gate.ty + 3))
    s.player.direction = "up"
    d.warm(0.5)

    def step(i, u):
        heat(lerp(lo, hi, min(1.0, u / 0.85) ** 1.3))
        d.ctrl = Controls(0.0, -0.8 if u > 0.6 else 0.0)

    d.take("gate", 7.0, lambda u: (bx, by - 10 - lerp(0, 50, ease((u - 0.5) / 0.5)), lerp(2.2, 2.4, u)), step)


def lake_spot(world):
    import numpy as np
    from game.geo import PLATEAU
    g = world.geo
    mask = (g.region == PLATEAU) & (g.basin >= 0)
    y, x = np.unravel_index(np.argmin(np.where(mask, g.height, 9.0)), g.height.shape)
    return int(x), int(y)


def scene_rain(d: Director) -> None:
    """Névoa: a chuva cai e o lago enche na depressão, com a margem orgânica."""
    s = d.state
    s.stage, s.storm = C.MIST_STAGE, 0.0
    s.indices.update(o2=float(C.STAGES[C.MIST_STAGE - 1].ti), heat=0.0, water=0.0)
    set_weather(s, 0.0, 70.0)
    w = s.surface.world
    tx, ty = lake_spot(w)
    s.rain.left, s.rain.intensity = 1e9, 1.0
    w.water_level = C.GEO_LEVELS[0] - 0.02
    d.teleport((tx + 2, ty + 9))
    s.player.direction = "up"
    d.warm(1.0)

    def step(i, u):
        w.water_level = lerp(C.GEO_LEVELS[0] - 0.02, C.GEO_LEVELS[1] + 0.01, ease(u))

    d.take("rain", 7.0, lambda u: (tx * T + 16, ty * T + 60, lerp(1.6, 1.4, u)), step)


def scene_green(d: Director) -> None:
    """A mancha do Verde avança a partir da base e das máquinas: grama, musgo, plantas."""
    s = d.state
    s.stage, s.storm = C.MIST_STAGE, 0.0
    set_weather(s, 0.0)
    bx, by = C.BASE_TILE
    for kind, tile in [("o2_t2", (bx - 3, by + 1)), ("heater_t2", (bx + 3, by + 1)), ("melter_t2", (bx + 5, by + 3)),
                       ("solar", (bx - 6, by + 4)), ("solar", (bx - 4, by + 4)), ("solar", (bx - 2, by + 4)),
                       ("o2_t2", (bx - 9, by + 7)), ("melter_t2", (bx + 11, by - 3)), ("heater_t2", (bx - 12, by - 4)),
                       ("o2_t2", (bx + 9, by + 9))]:
        if s.world.is_floor(*tile):
            place(d, kind, tile)
    start, end = C.STAGES[C.MIST_STAGE - 1].ti, C.STAGES[C.MIST_STAGE].ti
    bar0 = 1 - C.TRANSITION_WINDOW

    def ti_at(f):
        return start + (end - start) * (bar0 + C.TRANSITION_WINDOW * f)

    s.indices.update(o2=ti_at(0.0), heat=0.0, water=0.0)
    d.teleport((bx, by + 2))
    d.warm(0.5)

    def step(i, u):
        s.indices.update(o2=ti_at(ease(u) * 1.02), heat=0.0, water=0.0)
        if s.stage > C.MIST_STAGE:
            pass

    d.take("green", 7.0, lambda u: (bx * T + 16, by * T + 40, lerp(1.25, 1.05, u)), step)


def scene_green_lake(d: Director) -> None:
    """Verde: o lago cheio com plantas na beira e a grama."""
    s = d.state
    s.stage, s.storm = C.GREEN_STAGE, 0.0
    s.indices.update(o2=float(C.STAGES[C.GREEN_STAGE - 1].ti), heat=0.0, water=0.0)
    set_weather(s, 0.0)
    w = s.surface.world
    w.water_level = C.GEO_LEVELS[2]
    tx, ty = lake_spot(w)
    d.teleport((tx - 6, ty + 8))
    s.player.direction = "right"
    d.warm(0.5)

    def step(i, u):
        d.ctrl = Controls(0.5 if 0.2 < u < 0.7 else 0.0, -0.2 if 0.2 < u < 0.7 else 0.0)

    d.take("green_lake", 6.0, lambda u: (tx * T + lerp(-60, 60, u), ty * T + 70, 1.6), step)


def scene_soon_machines(d: Director) -> None:
    """EM BREVE: as drills aranha e tripé nos veios e o gerador eólico girando (sprites da Designer, fora do jogo)."""
    arid(d)
    s = d.state
    base = ROOT / "reports" / "design" / "maquinas_r3d"
    spider = pygame.image.load(str(base / "futuro" / "drill_spider.png")).convert_alpha()
    tripod = pygame.image.load(str(base / "futuro" / "drill_tripod.png")).convert_alpha()
    wind = pygame.image.load(str(base / "pendentes" / "eolico" / "anim_wind_turbine.png")).convert_alpha()
    sp = [spider.subsurface((64 * k, 0, 64, 80)) for k in range(spider.get_width() // 64)]
    tp = [tripod.subsurface((64 * k, 0, 64, 80)) for k in range(tripod.get_width() // 64)]
    wd = [wind.subsurface((32 * k, 0, 32, 64)) for k in range(wind.get_width() // 32)]
    bx, by = C.BASE_TILE
    ox, oy = (bx + 14) * T, (by - 6) * T                  # chão aberto a leste da base
    items = [("t", ox - 80, oy + 46), ("s", ox + 70, oy + 30),
             ("w", ox - 150, oy - 40), ("w", ox - 105, oy - 22), ("w", ox - 30, oy - 52), ("w", ox + 10, oy - 30),
             ("w", ox + 140, oy - 46), ("w", ox + 180, oy - 20)]
    d.teleport((bx + 14, by - 3))
    s.player.direction = "up"
    d.warm(0.4)
    clock = {"i": 0}

    def fx(view, cx, cy):
        i = clock["i"]
        for kind, x, y in sorted(items, key=lambda it: it[2]):
            if kind == "w":
                f = wd[(i // 2 + x) % len(wd)]
            elif kind == "s":
                f = sp[(i // 4) % len(sp)]
            else:
                f = tp[(i // 4) % len(tp)]
            view.blit(f, (round(x - cx - f.get_width() / 2), round(y - cy - f.get_height())))

    d.world_fx = fx

    def step(i, u):
        clock["i"] = i

    d.take("soon_machines", 5.0, lambda u: (ox + lerp(-30, 30, u), oy - 10, 2.6), step)


def scene_deep_cave(d: Director) -> None:
    """EM BREVE: caverna mais funda e escura, com magmatita pulsando nas paredes."""
    s = d.state
    s.enter_layer("cave")
    cave = s.world
    spots = [(x, y) for y in range(8, cave.height - 8, 2) for x in range(8, cave.width - 8, 2)
             if all(cave.is_floor(x + i, y) for i in range(-4, 3)) and cave.dist_from_center(x, y) >= 34]
    spot = spots[len(spots) // 2]
    # magmatita: rochas pequenas no chão em volta (tile que já existe no jogo, sprite animado)
    rnd = random.Random(11)
    for y in range(spot[1] - 7, spot[1] + 8):
        for x in range(spot[0] - 12, spot[0] + 13):
            if cave.is_floor(x, y) and math.hypot(x - spot[0], y - spot[1]) > 2.5 and rnd.random() < 0.10:
                cave.set(x, y, C.SMALL_MAGMATITE)
    d.teleport(spot)
    s.player.direction = "right"
    d.warm(0.5)
    p = s.player
    start = (p.x, p.y)

    def step(i, u):
        d.ctrl = Controls(0.4 if u < 0.8 else 0.0, 0.0)

    d.take("deep_cave", 5.0, lambda u: (start[0] + lerp(0, 90, u), start[1] - 20, 2.4), step)


def scene_giant(d: Director) -> None:
    """EM BREVE: o gelo gigante na faixa gelada, com a criatura presa que "respira" (sprite pendente da Designer)."""
    arid(d)
    s, r = d.state, d.r
    sheet = pygame.image.load(str(GIANT_DIR / f"form_ice_giant_{GIANT_VARIANT}_anim.png")).convert_alpha()
    fw, fh = 256, 220
    frames = [sheet.subsurface((fw * k, 0, fw, fh)) for k in range(sheet.get_width() // fw)]
    frost = pygame.image.load(str(GIANT_DIR / "frost_field.png")).convert_alpha()
    foot = (66 * T + 16, 17 * T + 20)                    # chão aberto da faixa gelada (seed 7)
    fx_, fy_ = 120, 216                                  # pé do sprite (gelo_gigante.json)
    player = r._draw_player
    r._draw_player = lambda *a, **k: None                # o player vai por cima do gelo, desenhado no fx
    d.teleport((66 - 4, 21))
    s.player.direction = "up"
    d.warm(0.5)
    clock = {"i": 0}
    # parado no quadro 0; a tira toca a 6 fps (8 quadros = 1,33 s) em 2 respirações no take
    plays = [round(1.4 * FPS), round(4.9 * FPS)]

    def frame_at(i):
        for p0 in plays:
            k = (i - p0) * 6 // FPS
            if 0 <= k < len(frames):
                return frames[k]
        return frames[0]

    def fx(view, cx, cy):
        view.blit(frost, (foot[0] - cx - frost.get_width() // 2, foot[1] - 54 - cy - frost.get_height() // 2))
        view.blit(frame_at(clock["i"]), (foot[0] - fx_ - cx, foot[1] - fy_ - cy))
        p = s.player
        player(view, s, round(p.x) - cx, round(p.y) - cy, d.app.t)

    d.world_fx = fx

    def step(i, u):
        clock["i"] = i
        d.ctrl = Controls(0.0, -0.35 if u < 0.35 else 0.0)

    d.take("giant", 8.0, lambda u: (foot[0], foot[1] - 90, lerp(1.7, 2.3, ease(u))), step)


SCENES = {
    "landing": scene_landing,
    "storm_walk": scene_storm_walk,
    "mine": scene_mine,
    "magma": scene_magma,
    "base": scene_base,
    "drones": scene_drones,
    "crater": scene_crater,
    "cave": scene_cave,
    "gate": scene_gate,
    "rain": scene_rain,
    "green": scene_green,
    "green_lake": scene_green_lake,
    "soon_machines": scene_soon_machines,
    "deep_cave": scene_deep_cave,
    "giant": scene_giant,
}

def main(names: list[str]) -> None:
    todo = names or [n for n in SCENES if n != "test"]
    for name in todo:
        print(f"cena {name}")
        SCENES[name](Director())                        # cada cena num jogo novo: nada vaza de uma pra outra
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1:])
