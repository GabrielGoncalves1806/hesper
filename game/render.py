"""Desenha o mundo na tela: tiles, objetos, luz e clima.

Ordem de cada frame (de trás pra frente, como camadas de papel):
  1. tiles visíveis (chão ou areia do deserto, água, paredes com face, minério, terminais)
     Na superfície com geo (v0.4 M2) o chão é assado em blocos de 512 px (game/ground.py) e só a água e a
     sombra das paredes vão por tile.
  2. zona de O₂ (círculo tracejado, só na superfície)
  3. objetos ordenados pelo Y do pé (cratera, rochas pequenas, cápsula, máquinas,
     plantas, player):
     quem está mais embaixo na tela é desenhado por último e fica "na frente"
  4. efeitos de mineração, fantasma da máquina sendo colocada e drones voando (por cima de tudo)
  5. luz (escurece tudo e "abre buracos" de luz) e clima do estágio (poeira, névoa, chuva...).
     Na CAVERNA (Marco 2) é outro sistema: escuridão total do game/lighting.py (lanterna, luminárias,
     luz fraca das máquinas, rampa e terminais) + brilho dos minérios; sem clima. O chão e as paredes da
     caverna usam sempre a arte do estágio névoa, sem água nem plantas (a caverna não terraforma).
     5b. TEMPESTADE (v0.4): nuvens de poeira andando com o vento, visão mais limpa (sem borda de círculo)
     em volta do player e das máquinas, faixas e grãos de vento (game/dust.py). Só com storm_level > 0.
  6. indicadores: barrinha das drills, raio de "sem energia", alcance da estação de drones
A UI (HUD, menus) vem depois, no ui.py.
"""

import math
import random

import numpy as np
import pygame

from game import art
from game import autotile
from game import cave_ground
from game import cave_light
from game import cave_rocks
from game.base import floor_variant, hull_floor_variant
from game import config as C
from game import drones
from game import dust
from game import energy
from game import ground
from game import hills
from game import ice_blocks
from game import ice_giant
from game.pocket_fog import PocketFog
from game import lake
from game import layers
from game import vesper, vesper_fx
from game import smoke
from game.assets import Sprites
from game.ground import decor_layers, decor_tile_free
from game.lighting import WARM_WHITE, LightSource, Lighting, helmet_lamp, lamp as lamp_light, ore_glints
from game.minimap import Minimap
from game.rain import RainDrops, rain_level
from game.surfaces import opaque
from game.base import BaseBlock
from game.props import Prop
from game.geo import FROST
from game.systems import GameState, Mining
from game.wrecks import Crate
from game.transition import BASE_SOURCE, StageMap
from game.world import hash01

ANIM_FRAMES = 4
MACHINE_ANIM_FPS = 5      # máquinas e ambiente animam a ~5 fps (a drill tem o dela, DRILL_FPS)


def tile_phase(tx: int, ty: int) -> int:
    """Fase 0–3 da animação de um tile (hash do tile): as máquinas não piscam em sincronia."""
    return ((tx * 73856093) ^ (ty * 19349663)) >> 4 & (ANIM_FRAMES - 1)


def anim_frame_index(t: float, phase: int = 0, working: bool = True, fps: float = MACHINE_ANIM_FPS) -> int:
    """Quadro (0–3) da tira de animação no tempo `t` com a fase do tile. Parada = quadro 0."""
    if not working:
        return 0
    return (int(t * fps) + phase) % ANIM_FRAMES


def bench_frame_index(work: float) -> int:
    """Quadro (0–7) da Bancada T2 com `work` s de animação por tocar: o ciclo anda do 0 ao 7 e termina parada (0)."""
    if work <= 0:
        return 0
    return min(int((C.BENCH_WORK_TIME - work) * C.BENCH_FPS), 7)


def rock_variant(tx: int, ty: int) -> int:
    """Variação (0 ou 1) da rocha pequena com veio, por hash do tile (sempre a mesma pro mesmo tile)."""
    return ((tx * 73856093) ^ (ty * 19349663)) & 1

T = C.TILE
WALL_LIFT = C.WALL_LIFT   # o topo da parede é desenhado 24 px acima do tile (altura, estilo Core Keeper)
LANDED_SHADOW_DROP = 6   # px abaixo do centro do drone: a sombra encostada nele (ainda no chão)
FACE_Y = 8       # a face (32×24) começa 8 px abaixo do topo do tile e vai até a borda de baixo
DECOR_FOOT = 26  # px: o pé da decoração solta (lasca, cristal, gelo) dentro do tile, como no mockup da Designer


def snap(v: float) -> int:
    """Pixel inteiro do mundo onde o player é desenhado. A câmera usa o MESMO pixel: assim o sprite fica
    parado na tela enquanto anda (antes a câmera truncava e o sprite arredondava; na diagonal, 1,41 px por
    quadro, a parte quebrada cruzava 0,5 quase todo quadro e o sprite pulava 1 px pra lá e pra cá)."""
    return math.floor(v + 0.5)


def build_draw_list(world, objects, tx0: int, tx1: int, ty0: int, ty1: int,
                    hill_rows=None) -> list[tuple]:
    """Ordem de desenho por profundidade (função pura, testável sem tela).

    Percorre as linhas de cima pra baixo. Em cada linha: primeiro as paredes da linha,
    depois os objetos cujo pé (`ay`) cai nessa linha, do mais alto pro mais baixo.
    Como o topo de uma parede invade 24 px a linha de cima, quem anda logo acima dela
    é desenhado antes e fica meio escondido atrás do topo.

    objects: lista de (ay, qualquer_coisa). Devolve ("wall", tx, ty) e ("obj", qualquer_coisa).
    hill_rows (morros orgânicos da superfície, v0.4): linhas que têm morro assado. No lugar das paredes da
    linha entra um ("hills", ty) só, a tira inteira daquela linha (game/hills.py), no mesmo lugar da ordem.
    """
    by_row: dict[int, list] = {}
    for ay, obj in objects:
        by_row.setdefault(int((ay - 1) // T), []).append((ay, obj))
    wall_rows = range(ty0, ty1 + 1)
    rows = set(wall_rows) | set(by_row) | (set(hill_rows) if hill_rows is not None else set())
    order = []
    for row in sorted(rows):
        if hill_rows is not None:
            if row in hill_rows:
                order.append(("hills", row))
        elif row in wall_rows:
            order += [("wall", tx, row) for tx in range(tx0, tx1 + 1) if world.is_wall(tx, row)]
        order += [("obj", obj) for _, obj in sorted(by_row.get(row, []), key=lambda o: o[0])]
    return order


def stage_key(stage: int) -> str:
    """Chave do estágio `stage` (1 a 4): "storm", "arid", "mist" ou "green"."""
    return C.STAGES[stage - 1].key


def art_key(stage: int) -> str:
    """Arte (sprites e paleta) do estágio `stage`: "dead", "mist" ou "green". Tempestade e Árido usam a do Morto."""
    return C.STAGE_ART[stage_key(stage)]


CAVE_STAGE = C.MIST_STAGE          # a caverna é desenhada sempre com a arte do estágio névoa (rocha fria)
RAMP_LIGHT = (255, 240, 214)       # luz do dia caindo pela boca da rampa de subida (cor da Designer, v5.0)
TERMINAL_LIGHT = (111, 227, 160)
MACHINE_LIGHT = {"o2": (89, 208, 230), "heater": (255, 138, 61), "melter": (159, 230, 255),
                 "smelter": (255, 138, 61), "solar": (255, 216, 74), "drill": (255, 210, 140), "drone_station": (150, 210, 230)}
EMERGENCY_LIGHT = (255, 96, 72)     # v0.7 M4: luz de emergência da VÉSPER-7 (vermelha, fraca)
EMERGENCY_RADIUS = 1.5              # tiles (decisão do dono: era 2,5 no plano)
EMERGENCY_INTENSITY = 0.6
DRONE_LIGHT = MACHINE_LIGHT["drone_station"]   # v0.6 M3: luzinha do drone voando na caverna (pedido do dono)


def cave_lights(state: GameState, helmet=WARM_WHITE, helmet_intensity: float = 1.0) -> list[LightSource]:
    """Fontes de luz da caverna (a lanterna sempre primeiro). Função pura, testada em tests/test_cave.py.
    Lanterna do capacete (~4 tiles, pra onde o player olha), luz do dia caindo pela boca da rampa (~3,5),
    luminárias (~5), luz fraca de cada máquina (~1,8; baú não tem e drill cheia está parada) e o verde
    dos terminais (~2)."""
    p = state.player
    out = [helmet_lamp(p.x, p.y - 18, p.facing, helmet, helmet_intensity)]
    world = state.world
    if world.crater is not None:                 # luz fixa na boca da rampa: (tx·32+48, ty·32+30), 3,5 tiles
        rx, ry = world.crater
        out.append(LightSource(rx * T + 48, ry * T + 30, 3.5 * T, RAMP_LIGHT))
    for m in state.machines:
        if m.broken:                              # v0.7 M1: máquina quebrada de ruína não acende
            continue
        if m.is_lamp:
            out.append(lamp_light(m.tx, m.ty, C.LAMP_RADIUS.get(m.kind, 5)))
        elif m.is_chest or (m.is_drill and m.full) or (m.is_smelter and m.smelter_blocker is not None):
            continue                              # (Fundição apagada parece desligada: só acende enquanto funde)
        else:
            ax, ay = m.anchor
            color = MACHINE_LIGHT.get(m.kind.removesuffix("_t2"), MACHINE_LIGHT["drone_station"])
            out.append(LightSource(ax, ay - T / 2 - (T / 2 if m.size > 1 else 0), 1.8 * T, color, 0.55))
    for m in state.stations:                     # v0.6 M3: drone voando leva uma luzinha (pousado, a estação já ilumina)
        for d in m.station.drones:
            if d.in_air:
                out.append(LightSource(d.x, d.y, 1.4 * T, DRONE_LIGHT, 0.6))
    for tx, ty in world.terminals:
        out.append(LightSource((tx + 0.5) * T, (ty + 1) * T, 2 * T, TERMINAL_LIGHT, 0.6))
    for (tx, ty), kind in world.fixtures.items():   # v0.7 M4: luzes de emergência da VÉSPER-7
        if kind == "emergency_light":
            out.append(LightSource((tx + 0.5) * T, (ty + 1) * T, EMERGENCY_RADIUS * T, EMERGENCY_LIGHT, EMERGENCY_INTENSITY))
    return out


class Renderer:
    def __init__(self, sprites: Sprites):
        self.sprites = sprites
        self._surfaces: dict[str, tuple[pygame.Surface, bool]] = {}
        self._fx: dict[tuple, pygame.Surface] = {}
        self.particles: list[list[float]] = []   # [x, y, vx, vy, vida, cor]
        self.door_fx = vesper_fx.DoorFx()        # v0.7 M4: faísca e névoa da porta emperrada da VÉSPER-7
        self.surface_map = StageMap()            # estágio visual de cada tile da superfície (transição gradual)
        self.cave_map = StageMap()               # caverna: estágio fixo (névoa), nunca transiciona
        self.cave_map.stage = CAVE_STAGE
        self.stage_map = self.surface_map        # o da camada que está sendo desenhada (troca no draw)
        self.lighting = Lighting(cell=4, banding=True)   # escuridão da caverna (degraus: decisão do dono)
        self.storm_dust = dust.DustLayer()              # poeira da tempestade (v0.4): nuvens + visão
        # grãos da tempestade: sorteados pela seed do mundo (trocou de mundo, troca junto: use_seed)
        self.storm_particles = dust.DustParticles(seed=C.WORLD_SEED)
        self.rain_drops = RainDrops(seed=C.WORLD_SEED)  # traços da chuva (v0.4 M3.3, game/rain.py)
        self.seed = C.WORLD_SEED                 # seed do mundo que está sendo desenhado
        self._fade_cache: dict[str, tuple[int, pygame.Surface]] = {}   # clima esmaecido (ver _faded)
        # Relógio das animações das máquinas: o App soma dt × fator da energia (game/energy.py).
        # No déficit ele anda mais devagar, então a drill gira e as máquinas animam mais devagar.
        self.machine_t = 0.0
        self.clock = 0.0
        self.powered = True
        # v0.5 M1: luz de scanner. O último desmonte desenhado (pro holograma piscar depois que a máquina sai) e os
        # holograma piscando agora: [(dados do scan, âncora no mundo, t do começo)].
        self._unbuilding = None
        self.blinks: list[tuple[dict, tuple[float, float], float]] = []

        # Superfícies de efeito pré-calculadas (fazer isso a cada frame seria lento).
        self.shadow_top = self._alpha_strips(T, [(10, 84), (6, 40)])   # sombra que a parede joga no chão
        self.shadow_left = pygame.Surface((4, T), pygame.SRCALPHA)
        self.shadow_left.fill((0, 0, 0, 40))
        self.water_tiles = autotile.WaterTiles()   # tiles de água já montados (≤ 47 por estágio)
        self.base_wall_tiles = autotile.WaterTiles()   # topos da parede da base já montados (≤ 47, v0.5 M2)
        self.power_factor = 1.0                    # ritmo da energia neste frame (o Dispersor lê o estado dele)
        # água por tile: com geo (lago nas bacias, M3.3) vale até o nível d'água mudar; sem geo, só um frame
        self._wet_memo: dict[tuple[int, int], bool] = {}
        self._wet_key = None                       # (id do mundo, water_level) do memo; None = zera a cada frame
        self.lake = lake.LakeBlocks()              # v0.4 M3.5: lago com margem orgânica, assado em blocos
        self.organic_lake = True                   # False = a água por tile de antes (autotile; o smoke compara)
        self._lake_stage_tags: dict[tuple[int, int], tuple] = {}
        self.outline_h = pygame.Surface((T, 1), pygame.SRCALPHA)
        self.outline_h.fill((0, 0, 0, 90))
        self.outline_v = pygame.Surface((1, T), pygame.SRCALPHA)
        self.outline_v.fill((0, 0, 0, 70))
        self.bedrock_shade = pygame.Surface((T, T), pygame.SRCALPHA)
        self.bedrock_shade.fill((0, 0, 0, 110))
        self.player_shadow = pygame.Surface((16, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(self.player_shadow, (0, 0, 0, 97), (0, 0, 16, 5))
        # Tamanho da "visão" (px do mundo que cabem na tela). Sem zoom é 960×540; com zoom muda
        # (o App desenha numa superfície de SCREEN/zoom e estica). Vem do tamanho do canvas em draw().
        self.view_w, self.view_h = C.SCREEN_W, C.SCREEN_H
        self._view_fx: dict[tuple, pygame.Surface] = {}   # escuridão, vinheta, véus... um por tamanho de visão
        self.zone_surf = pygame.Surface((C.BASE_RADIUS * 2 + 4, C.BASE_RADIUS * 2 + 4), pygame.SRCALPHA)
        self.fog_blob = art.radial(180, (230, 236, 240), 70)
        self.dust = [self._dot((240, 170, 120, 128)), self._dot((255, 210, 170, 178))]
        self.open_chest = None                   # baú aberto agora (o App avisa): desenha com a tampa aberta
        self.highlight = None                    # alvo do E (o App avisa): Machine ou ("terminal", índice)
        self._drone_offsets: dict[int, tuple[float, float]] = {}   # deslocamento visual suavizado por drone
        self._drone_t: float | None = None
        self._item_icons: dict[str, pygame.Surface] = {}
        self.minimap = Minimap()                 # textura do mapa (1 px por tile), incremental (game/minimap.py)
        self.ground = ground.Ground(getattr(sprites, "enabled", True))  # chão assado da superfície com geo (v0.4 M2, game/ground.py)
        self.cave_ground = cave_ground.CaveGround(getattr(sprites, "enabled", True))  # v0.6 Fundo M2: chão assado da caverna
        self.cave_light = cave_light.CaveLight()           # v0.6 Fundo M2: luz ambiente e do capacete por região
        self._cave_geo: cave_ground.CaveGeo | None = None
        self._cave_geo_world = None
        # v0.4 Marco 2 (trilha C, game/hills.py): morros orgânicos assados em blocos
        self._hills: hills.HillBlocks | None = None
        self._cave_rocks: cave_rocks.CaveRocks | None = None   # rocha da caverna com borda orgânica (v0.5 M3.4)
        self._hill_stage_tags: dict[tuple[int, int], tuple] = {}
        self.formation_sprites = hills.FormationSprites()   # formações fixas (v0.4 M2 · C3)
        self.crater_sprites = hills.CraterSprites()          # cratera de impacto e a tampa de gelo (C4)
        self.frost_ring = hills.FrostRing()                   # geada do gelo-portão derretendo (v0.4 M3.2)
        self.ice_block_sprites = hills.IceBlockSprites()      # blocos do gelo-portão (v0.4 M3.5)
        self.frost_field = hills.FrostRing("frost_field.png")  # geada grande do gelo gigante (v0.5 M3.6.2)
        self.giant_breath = ice_giant.Breath(C.WORLD_SEED)   # a respirada do gelo gigante (refeita a cada seed)
        self.giant_shards: list = []                          # estilhaços dele (IceBlock sem colisão), cache por seed
        self.pocket_fog = PocketFog()                         # névoa do bolsão da criatura (M3.6.4)
        self.anim_t = 0.0                                     # relógio do último draw (a animação da respirada)
        # v0.4 M3.1: fumaça das fumarolas acordadas (game/smoke.py), partícula; relógio próprio pelo `t` do draw
        self.vent_smoke = smoke.VentSmoke(seed=C.WORLD_SEED)
        self._smoke_t: float | None = None
        self._vents_seen: list | None = None           # vents_awake do quadro anterior (pra pegar quem acordou)

    # ---- utilitários ----------------------------------------------------------
    @staticmethod
    def _alpha_strips(width, strips):
        h = sum(s[0] for s in strips)
        surf = pygame.Surface((width, h), pygame.SRCALPHA)
        y = 0
        for sh, a in strips:
            surf.fill((0, 0, 0, a), (0, y, width, sh))
            y += sh
        return surf

    @staticmethod
    def _full(size, rgba):
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill(rgba)
        return s

    @staticmethod
    def _dot(rgba):
        s = pygame.Surface((2, 2), pygame.SRCALPHA)
        s.fill(rgba)
        return s

    @staticmethod
    def _vertical_gradient(size, rgb, top_alpha, bottom_alpha):
        s = pygame.Surface((1, 64), pygame.SRCALPHA)
        for y in range(64):
            a = top_alpha + (bottom_alpha - top_alpha) * y / 63
            s.set_at((0, y), (*rgb, int(a)))
        return pygame.transform.smoothscale(s, size)

    VIEW_FX = {   # superfícies do tamanho da visão, criadas na primeira vez que cada tamanho aparece
        "darkness": lambda size: pygame.Surface(size, pygame.SRCALPHA),
        "layer": lambda size: pygame.Surface(size, pygame.SRCALPHA),          # camada reaproveitável
        "vignette": lambda size: art.vignette(*size, (0, 0, 0), 128),
        "tint_dead": lambda size: Renderer._full(size, (214, 104, 52, 18)),
        "tint_green": lambda size: Renderer._full(size, (255, 226, 160, 13)),
        "fog_gradient": lambda size: Renderer._vertical_gradient(size, (220, 230, 235), 51, 13),
    }

    def view_fx(self, name: str) -> pygame.Surface:
        size = (self.view_w, self.view_h)
        key = (name, size)
        if key not in self._view_fx:
            self._view_fx[key] = self.VIEW_FX[name](size)
        return self._view_fx[key]

    def surface(self, name: str | None, painter, variant_key: str | None = None) -> tuple[pygame.Surface, bool]:
        """Sprite do contrato (se ligado e existir) ou o desenho de fallback. Devolve (surface, é_fallback)."""
        key = variant_key or name
        if key not in self._surfaces:
            sprite = self.sprites.get(name) if name else None
            self._surfaces[key] = (sprite, False) if sprite else (painter(), True)
        return self._surfaces[key]

    def light_cut(self, radius: int, strength: float) -> pygame.Surface:
        key = ("cut", radius, round(strength, 2))
        if key not in self._fx:
            self._fx[key] = art.radial(radius, (0, 0, 0), int(255 * strength))
        return self._fx[key]

    def light_glow(self, radius: int, rgb: tuple[int, int, int], strength: float) -> pygame.Surface:
        """Brilho colorido 'pré-multiplicado' (fundo preto) pra somar na tela com BLEND_RGB_ADD."""
        key = ("glow", radius, rgb, round(strength, 2))
        if key not in self._fx:
            src = art.radial(radius, rgb, int(255 * strength))
            glow = opaque(src.get_size())   # o radial tem alfa; no formato padrão (ARGB no macOS) o blit zerava o alfa
            glow.fill((0, 0, 0))
            glow.blit(src, (0, 0))
            self._fx[key] = glow
        return self._fx[key]

    # ---- câmera ---------------------------------------------------------------
    @staticmethod
    def camera(state: GameState, view: tuple[int, int] = (C.SCREEN_W, C.SCREEN_H)) -> tuple[int, int]:
        """Canto superior esquerdo da visão, em pixels do mundo. Segue o player e não sai do mapa.
        `view` = quanto do mundo cabe na tela (muda com o zoom: game/viewport.py)."""
        vw, vh = view
        max_x = state.world.width * T - vw
        max_y = state.world.height * T - vh
        cx = min(max(0, snap(state.player.x) - vw // 2), max_x)
        cy = min(max(0, snap(state.player.y) - 16 - vh // 2), max_y)
        return int(cx), int(cy)

    # ---- frame completo -------------------------------------------------------
    def draw(self, canvas: pygame.Surface, state: GameState, cam: tuple[int, int], t: float,
             ghost: tuple[str, tuple[int, int], int, bool] | None = None, overlay: dict | None = None) -> None:
        self.view_w, self.view_h = canvas.get_size()     # tamanho da visão (com zoom, não é 960×540)
        self.use_seed(state.seed)
        self.anim_t = t
        cave = not state.active.has_base
        if cave:                                         # rocha fria: sempre névoa, sem transição
            self.stage_map = self.cave_map
            stage = art_key(CAVE_STAGE)
        else:
            self.stage_map = self.surface_map
            stage = art_key(state.stage)
            self.stage_map.update(state.ti, [BASE_SOURCE, *state.transition_sources])
        self.draw_floors(canvas, state, cam, stage, t)
        self.draw_crater_ejecta(canvas, state, cam)
        self.draw_gate_frost(canvas, state, cam)
        self.draw_giant_frost(canvas, state, cam)
        self.draw_veins(canvas, state, cam)
        self.draw_base_floors(canvas, state, cam)
        self.draw_prop_decals(canvas, state, cam)           # v0.7 M2: a mancha de gelo, com o chão
        if state.active.has_base:
            self.draw_zone(canvas, cam, t)
        self.draw_walls_and_objects(canvas, state, cam, stage, t)
        self.draw_leaks(canvas, state, cam, t)               # v0.5 M2: o tile furado pisca, por cima dos objetos e do raio-x
        if not cave:
            if state.mining:
                self.draw_mining(canvas, state, state.mining, cam)
            if ghost:
                self.draw_ghost(canvas, cam, *ghost, t)
        self.draw_flying_drones(canvas, state, cam, t)
        self.draw_particles(canvas, cam)
        if not cave:
            self.draw_vent_smoke(canvas, state, cam, t)
            self.draw_pocket_fog(canvas, state, cam, t)
        if cave:
            self.draw_cave_darkness(canvas, state, cam, t)
            if state.layer == layers.VESPER:
                self.door_fx.draw(canvas, cam)                   # faísca e névoa por cima do escuro (brilham)
            # rachaduras e fantasma por cima do escuro: o jogador precisa ver onde está mexendo
            if state.mining:
                self.draw_mining(canvas, state, state.mining, cam)
            if ghost:
                self.draw_ghost(canvas, cam, *ghost, t)
        else:
            self.draw_lighting(canvas, state, cam, stage, t)
            self.draw_atmosphere(canvas, stage, t, cam, getattr(state.active, "geo", None))
            self.draw_rain(canvas, state, t)
            self.draw_storm(canvas, state, cam, t)
        # 6. indicadores por cima da luz (no escuro da caverna eles têm que aparecer): barrinha das
        #    drills e raio de "sem energia". Ficam no mundo, então crescem com o zoom.
        self.draw_machine_status(canvas, state, cam, t)

    def use_seed(self, seed: int) -> None:
        """A transição e os grãos da poeira saem da seed do mundo (state.seed), não da C.WORLD_SEED."""
        if seed == self.seed:
            return
        self.seed = seed
        self.surface_map = StageMap(seed)
        self.storm_particles = dust.DustParticles(seed=seed)
        self.rain_drops = RainDrops(seed=seed)
        self.vent_smoke = smoke.VentSmoke(seed=seed)
        self._vents_seen = None
        self.giant_breath = ice_giant.Breath(seed)
        self.giant_shards = []
        self.pocket_fog = PocketFog()

    def draw_storm(self, canvas, state: GameState, cam, t: float) -> None:
        """Tempestade de poeira (game/dust.py): poeira com a visão recortada + grãos e faixas de vento.
        Por cima do mundo e do clima, por baixo dos indicadores e da HUD. Sem tempestade: nada (custo zero)."""
        storm = dust.storm_of(state)
        if storm <= 0:
            return
        wind, gust, view_tiles = dust.weather_of(state)
        snow = dust.snow_of(state)                      # nevasca na faixa gelada (v0.5 M3.7)
        self.storm_dust.tick(t, wind, storm, gust)
        self.storm_particles.tick(t, wind, storm, gust, snow)
        lights = dust.vision_lights(state, cam, view_tiles * T)
        (px, py, view_px), extra = lights[0], lights[1:]
        self.storm_dust.apply(canvas, cam, storm, gust, view_px, extra, (px, py), self.storm_particles, wind, snow)

    def draw_pocket_fog(self, canvas, state: GameState, cam, t: float) -> None:
        """Névoa fria do bolsão da criatura (v0.5 M3.6.4, game/pocket_fog.py): por cima das formações e dos estilhaços,
        antes da luz (a noite escurece a névoa junto) e da HUD. Sem bolsão grande, ou depois de dissipada: nada."""
        geo = state.active.geo
        if geo is None or getattr(geo, "giant", None) is None:
            return
        alpha = self.pocket_fog.update(state.active, t)
        self.pocket_fog.draw(canvas, geo, cam, t, alpha)

    def draw_rain(self, canvas, state: GameState, t: float) -> None:
        """Chuva (v0.4 M3.3, game/rain.py): véu frio + traços no ângulo do vento, por cima do clima do estágio e
        por baixo dos indicadores e da HUD. Só na superfície; sem chuva, nada (custo zero)."""
        self.rain_drops.draw(canvas, rain_level(state), state.weather.wind, t)

    # ---- fumarolas (v0.4 M3.1) ------------------------------------------------------------------------------
    @staticmethod
    def formation_variant(state: GameState, f) -> int | None:
        """Sprite de cada formação pelo estado (None = o `variant` da própria formação). Fumarola: 1 = acordada."""
        if not f.kind.startswith("vent_"):
            return None
        geo = state.active.geo
        awake = state.active.vents_awake
        for i, v in enumerate(geo.vents):
            if v is f:
                return 1 if i < len(awake) and awake[i] else 0
        return 0

    def vent_sources(self, state: GameState) -> list[smoke.Source]:
        """As fumarolas acordadas da camada, com as bocas (mouths do JSON, px do sprite) em px do mundo."""
        geo = getattr(state.active, "geo", None)
        if geo is None:
            return []
        out = []
        forms = hills.palettes().get("formations", {})
        for i, (f, on) in enumerate(zip(geo.vents, state.active.vents_awake)):
            if not on:
                continue
            surf, x, y = self.formation_sprites.placement(f, self.stage_map.stage_at(*hills.foot_tile(f)), 1)
            mouths = forms.get(f.kind, {}).get("mouths") or [(surf.get_width() // 2, 4)]
            out.append(smoke.Source(i, f.kind.removeprefix("vent_"), [(x + mx, y + my) for mx, my in mouths]))
        return out

    def draw_vent_smoke(self, canvas, state: GameState, cam, t: float) -> None:
        """Fumaça das fumarolas acordadas: depois dos objetos, antes da luz/clima e da HUD. Só na superfície."""
        dt = 0.0 if self._smoke_t is None else max(0.0, min(C.MAX_DT, t - self._smoke_t))
        self._smoke_t = t
        awake = list(getattr(state.active, "vents_awake", []))
        seen = self._vents_seen
        if seen is not None and len(seen) == len(awake):
            for i, (was, now) in enumerate(zip(seen, awake)):
                if now and not was:
                    self.vent_smoke.wake(i)
        self._vents_seen = awake
        if not any(awake) and not self.vent_smoke.puffs:
            return
        storm = dust.storm_of(state)
        wind, gust, _ = dust.weather_of(state)
        speed = C.THAW_FUMAROLE_WIND.get(stage_key(state.stage), 0.0) * (1 + gust * storm)
        view = pygame.Rect(cam[0], cam[1], self.view_w, self.view_h)
        push = (wind[0] * speed, wind[1] * speed * C.THAW_FUMAROLE_WIND_Y)
        sources = self.vent_sources(state)
        self.vent_smoke.update(dt, sources, push, view)
        self.vent_smoke.draw_glow(canvas, cam, sources, t)
        self.vent_smoke.draw(canvas, cam, stage_key(state.stage))

    def draw_cave_darkness(self, canvas, state: GameState, cam, t: float) -> None:
        """Escuridão da caverna (game/lighting.py), com a luz da região do player (game/cave_light.py), e, por
        cima, o brilho dos minérios no escuro."""
        cl = self.cave_light
        cl.update(state.world, *state.player.tile, t)
        self.lighting.apply(canvas, cam, cave_lights(state, cl.helmet, cl.helmet_intensity), ambient=cl.ambient, t=t)
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        self.lighting.draw_glints(canvas, cam, ore_glints(state.world, tx0, tx1, ty0, ty1 + 1), t=t)

    # ---- tiles ----------------------------------------------------------------
    def visible_tiles(self, cam) -> tuple[int, int, int, int]:
        cam_x, cam_y = cam
        return cam_x // T, (cam_x + self.view_w) // T, cam_y // T, (cam_y + self.view_h) // T

    def surface_geo(self, state: GameState):
        """O geo da camada (v0.4 M2: regiões e bacias) quando dá pra usar o chão assado; senão None (caverna,
        mundo sem geo ou sem a arte das regiões): aí o chão é o de hoje, por tile."""
        geo = getattr(state.active, "geo", None)
        return geo if geo is not None and self.ground.enabled else None

    def cave_geo(self, world):
        """O geo do chão assado da caverna (v0.6 Fundo M2), ou None (superfície ou sem a arte)."""
        if world.cave_region is None or not self.cave_ground.enabled:
            return None
        if self._cave_geo_world is not world:
            self._cave_geo, self._cave_geo_world = cave_ground.CaveGeo(world), world
        return self._cave_geo

    def draw_floors(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        """Passada 1: todo o chão e a água visíveis (as paredes vêm depois, por cima)."""
        world = state.world
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        geo = self.surface_geo(state)
        cgeo = self.cave_geo(world) if self.organic_hills(state) else None
        if cgeo is not None:   # caverna (v0.6 Fundo M2): chão assado; sem água e sem sombra quadrada (a rocha é orgânica)
            self.cave_ground.draw(canvas, cgeo, cam, (self.view_w, self.view_h), None)
            return
        if geo is not None:   # chão assado em blocos de 512 px (game/ground.py); por tile só água e sombra
            self.ground.draw(canvas, geo, cam, (self.view_w, self.view_h), self.stage_map)
            self.sync_water(world)
            shadows = not self.organic_hills(state)   # morro orgânico: a face curva já faz a borda (sem sombra quadrada)
            per_tile = self.draw_lake(canvas, world, cam, t)
            if per_tile is not None and not per_tile and not shadows:
                return                                # sem água por tile e sem sombra: nada mais por tile
            for ty in range(ty0, ty1 + 1):
                for tx in range(tx0, tx1 + 1):
                    if not world.is_wall(tx, ty):
                        water = per_tile is None or (tx // lake.BT, ty // lake.BT) in per_tile
                        self._floor_overlays(canvas, world, tx, ty, tx * T - cam[0], ty * T - cam[1], t, shadows,
                                             water)
            return
        backstop = C.PALETTES[stage]["face_dark"]
        self.sync_water(world)   # cada vizinho é consultado por até 9 tiles (sem geo: guarda só neste frame)
        # Morro orgânico (v0.4): a silhueta arredonda nos cantos e não cobre o tile inteiro, então embaixo da
        # parede vai chão (e sem a sombra retangular da parede: quem faz a borda agora é a face curva)
        organic = self.organic_hills(state)
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                sx, sy = tx * T - cam[0], ty * T - cam[1]
                if world.is_wall(tx, ty) and not organic:
                    canvas.fill(backstop, (sx, sy, T, T))   # fundo escuro (só aparece na borda do mapa)
                else:
                    num = self.stage_map.stage_at(tx, ty)   # pode estar "à frente" no meio da transição
                    self._draw_floor(canvas, world, tx, ty, sx, sy, art_key(num), num, t, not organic)

    def draw_veins(self, canvas, state: GameState, cam) -> None:
        """Veios 2×2: overlay do chão (vale pra todos os estágios), antes das paredes e dos objetos."""
        for v in state.world.veins:
            sx, sy = v.tx * T - cam[0], v.ty * T - cam[1]
            if -64 < sx < self.view_w and -64 < sy < self.view_h:
                surf, _ = self.surface(f"vein_{v.resource}", lambda r=v.resource: art.vein(r))
                canvas.blit(surf, (sx, sy))

    def draw_walls_and_objects(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        """Passada 2: linha por linha, paredes com topo elevado e objetos ordenados pelo pé."""
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        self.clock = t                                  # relógio do ambiente (terminal, pod, painel solar)
        self.power_factor = state.power.factor
        self.powered = self.power_factor > 0            # sem energia nenhuma: máquinas no quadro 0
        objects = self.collect_objects(canvas, state, cam, t)
        organic = self.organic_hills(state)
        cave = not state.active.has_base
        strips = (self.cave_strips(state, cam) if cave else self.hill_strips(state, cam)) if organic else None
        terminals = {}                                  # caverna orgânica: o terminal é desenhado depois da tira da linha
        if strips is not None and cave:
            for term in state.world.terminals:
                terminals.setdefault(term[1], []).append(term)
        hill_rows = None if strips is None else {r for rows in strips.values() for r in rows}
        # +1 linha embaixo: o topo elevado de uma parede logo abaixo da tela ainda aparece
        for item in build_draw_list(state.world, objects, tx0, tx1, ty0, ty1 + 1, hill_rows):
            if item[0] == "wall":
                _, tx, ty = item
                tile_stage = art_key(self.stage_map.stage_at(tx, ty))
                self._draw_wall(canvas, state.world, tx, ty, tx * T - cam[0], ty * T - cam[1], tile_stage)
            elif item[0] == "hills":
                row = item[1]
                for rows in strips.values():
                    strip = rows.get(row)
                    if strip is not None:
                        surf, x, y = strip
                        canvas.blit(surf, (x - cam[0], y - cam[1]))
                for tx, ty in terminals.get(row, ()):
                    self._draw_terminal(canvas, tx, ty, tx * T - cam[0], ty * T - cam[1])
            else:
                item[1]()
        self._draw_player_silhouette(canvas, state, cam, t)
        # Broca da frente (lado e baixo) por cima de tudo: ela encosta no tile que está sendo minerado,
        # e esse tile pode ser uma parede desenhada depois do player (minerando pra baixo).
        if state.mining:
            frame, (dx, dy), behind = self.drill_sprite(state, t)
            if not behind:
                p = state.player
                canvas.blit(frame, (snap(p.x) - cam[0] + dx, snap(p.y) - cam[1] + dy))

    # ---- base respirável (v0.5 M2 · game/base.py · arte: reports/design/v05_m2_base) ---------------------
    @staticmethod
    def _placeholder(size: int, key: str = "") -> pygame.Surface:
        """Quadradinho colorido quando o PNG não existe (sprites desligados nos testes)."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((90 + hash(key) % 100, 110, 140, 255))
        return surf

    def base_view(self, cam) -> tuple[int, int, int, int]:
        """Tiles visíveis com folga (o topo da parede sobe 24 px; a face desce até a linha de baixo)."""
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        return tx0 - 1, tx1 + 1, ty0 - 1, ty1 + 2

    def hull_name(self, state, name: str) -> str:
        """Nome do sprite da casca: na VÉSPER-7 o `hull_*` no lugar do `base_*` (se o PNG existir; senão o da base)."""
        if state.layer == layers.VESPER and name.startswith("base_"):
            hull = "hull_" + name[len("base_"):]
            if self.sprites.get(hull) is not None:
                return hull
        return name

    def draw_hatch(self, canvas, state: GameState, cam) -> None:
        """A escotilha de saída (v0.7 M4), no chão do porão: vesper_hatch_exit_a/_b pela variante do porão (andável, abaixo
        de tudo). Sem o PNG, um quadrado escuro com borda."""
        hx, hy = vesper.hatch_tile(state.world)
        name = f"vesper_hatch_exit_{vesper.hold_variant(state.world.seed)}"
        surf = self.surface(name, lambda: self._fixture_placeholder("hatch", (T, T)))[0]
        canvas.blit(surf, (hx * T - cam[0], hy * T - cam[1]))

    FIXTURE_COLORS = {"hatch": (20, 18, 24), "container_broken": (150, 170, 190), "power_panel": (70, 90, 120),
                      "jammed_door": (120, 100, 70), "emergency_light": (200, 60, 50)}

    def _fixture_placeholder(self, kind: str, size) -> pygame.Surface:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((*self.FIXTURE_COLORS.get(kind, (200, 0, 200)), 255))
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 1)
        return surf

    def fixture_face(self, kind: str, tile) -> pygame.Surface:
        """Face opaca (32×24) do painel, da porta ou da luz de emergência (a luz tem 2 variantes por hash do tile)."""
        name = f"vesper_{kind}"
        if kind == "emergency_light":
            name += "_a" if hash01(tile[0], tile[1], 11) < 0.5 else "_b"
        return self.surface(name, lambda: self._fixture_placeholder(kind, C.PROP_FACE_SIZE))[0]

    def draw_container_broken(self, canvas, tile, x: int, y: int) -> None:
        """Contêiner arrombado da câmara fria: o container_open.png (aprovado, v0.5 M4), pé no tile (âncora do lacrado)."""
        surf = self.container_surface(True)
        canvas.blit(surf, (x, y))
        if self.highlight == ("fixture", tile):
            canvas.blit(self.outline_of(("fixture", "container_broken"), surf), (x - 1, y - 1))

    def draw_base_floors(self, canvas, state: GameState, cam) -> None:
        """Passada do chão: as 4 variações do base_floor por hash do tile (igual nos 3 estágios), embaixo de tudo."""
        grid = state.base
        if not grid.blocks:
            return
        hull = state.layer == layers.VESPER
        tx0, tx1, ty0, ty1 = self.base_view(cam)
        for b in grid.blocks:
            if not b.is_floor or not (tx0 <= b.tx <= tx1 and ty0 <= b.ty <= ty1):
                continue
            if hull:                                          # v0.7 M4: chão de chapa da nave (0 em ~75%)
                name = self.hull_name(state, f"base_floor_{hull_floor_variant(b.tx, b.ty)}")
            else:
                name = f"base_floor_{floor_variant(b.tx, b.ty)}"
            surf, _ = self.surface(name, lambda b=b: self._placeholder(T, "floor"))
            canvas.blit(surf, (b.tx * T - cam[0], b.ty * T - cam[1]))
        if hull:
            self.draw_hatch(canvas, state, cam)

    def collect_base_objects(self, items: list, canvas, state: GameState, cam) -> None:
        """Parede e porta da base entram na ordem de profundidade com ay = ty·32 + 1: caem na linha certa e saem
        primeiro dela (antes dos objetos com o pé naquela linha), também onde a linha vira tira de morro."""
        grid = state.base
        if not grid.blocks:
            return
        tx0, tx1, ty0, ty1 = self.base_view(cam)
        for b in grid.blocks:
            if b.is_floor:
                continue
            for tile in b.tiles:
                if not (tx0 <= tile[0] <= tx1 and ty0 <= tile[1] <= ty1):
                    continue
                ay = tile[1] * T + 1
                if b.is_wall:
                    items.append((ay, lambda t=tile: self.draw_base_wall(canvas, state, t, cam)))
                else:
                    items.append((ay, lambda b=b, t=tile: self.draw_base_door(canvas, state, b, t, cam)))

    def draw_base_wall(self, canvas, state: GameState, tile, cam) -> None:
        """Parede alta da base: topo no autotile A2 de 47 combinações (conecta só com parede da base: a porta e a
        rocha não contam) em (x, y−24); a face 32×24 em (x, y+8) quando não tem parede da base embaixo."""
        tx, ty = tile
        grid = state.base
        x, y = tx * T - cam[0], ty * T - cam[1]
        top_name = self.hull_name(state, "base_wall_top")      # v0.7 M4: casca da VÉSPER-7 (hull_*), com fallback pro base_*
        atlas = self.sprites.get(top_name)
        if atlas is None:                                       # sem sprites (testes): caixa lisa
            canvas.fill((58, 62, 78), (x, y - C.BASE_WALL_LIFT, T, T))
            if not grid.is_wall((tx, ty + 1)):
                canvas.fill((176, 160, 130), (x, y + C.BASE_FACE_Y, T, T - C.BASE_FACE_Y))
                self._draw_face_prop(canvas, state, tile, x, y)
            self._draw_ruin_terminal(canvas, state, tile, x, y)
            return
        key = autotile.tile_key(lambda a, b: grid.is_wall((a, b)), tx, ty)
        canvas.blit(self.base_wall_tiles.get(top_name.removesuffix("_top"), atlas, key), (x, y - C.BASE_WALL_LIFT))
        if not grid.is_wall((tx, ty + 1)):
            face = self.sprites.get(self.hull_name(state, "base_wall_face"))
            if face is not None:
                idx = int(grid.is_wall((tx - 1, ty))) + 2 * int(grid.is_wall((tx + 1, ty)))
                canvas.blit(face, (x, y + C.BASE_FACE_Y), (idx * T, 0, T, C.BASE_WALL_LIFT))
            self._draw_fixture_face(canvas, state, tile, x, y)
            self._draw_face_prop(canvas, state, tile, x, y)
        self._draw_ruin_terminal(canvas, state, tile, x, y)

    # ---- props (v0.7 M2 · game/props.py · arte: reports/design/v07_lore) -------------------------------
    def prop_surface(self, kind: str, tile=None) -> pygame.Surface:
        """prop_*.png / wall_*.png (chão e mesa 32×40, decal 32×32, face 32×24; prop grande: largura e altura em tiles) ou
        um quadradinho se o PNG não existe. Kind com variantes (C.PROP_VARIANT_KINDS): _a/_b por hash do `tile`."""
        ptype = C.PROPS[kind]
        name = kind
        if kind in C.PROP_VARIANT_KINDS:
            name += "_a" if tile is None or hash01(tile[0], tile[1], 17) < 0.5 else "_b"

        def painter():
            w, h = ptype.size
            if ptype.place == "face":
                size = C.PROP_FACE_SIZE
            elif ptype.place == "decal":
                size = (T, T)
            else:
                size = (C.PROP_SPRITE_SIZE[0] * w, C.PROP_SPRITE_SIZE[1] + T * (h - 1))
            surf = pygame.Surface(size, pygame.SRCALPHA)
            surf.fill((140 + hash(kind) % 80, 120, 100, 255))
            return surf
        return self.surface(name, painter)[0]

    def _blit_prop(self, canvas, prop: Prop, x: int, y: int) -> None:
        """Blit do prop em (x, y) (o topo do sprite, já com o deslocamento do tipo) e o contorno se é o alvo do scan."""
        surf = self.prop_surface(prop.kind, prop.tile)
        canvas.blit(surf, (x, y))
        if self.highlight is prop:
            canvas.blit(self.outline_of(("prop", prop.kind, id(surf)), surf), (x - 1, y - 1))

    def _draw_fixture_face(self, canvas, state: GameState, tile, x: int, y: int) -> None:
        """Painel de energia, porta emperrada ou luz de emergência da VÉSPER-7 (v0.7 M4): face opaca 32×24 que troca a peça
        normal da face, em (tx·32, ty·32 + 8). O alvo do E (painel e porta) ganha o contorno claro."""
        kind = state.world.fixtures.get(tuple(tile)) if state.layer == layers.VESPER else None
        if kind not in vesper.WALL_FIXTURES:
            return
        surf = self.fixture_face(kind, tile)
        canvas.blit(surf, (x, y + C.BASE_FACE_Y))
        if self.highlight == ("fixture", tuple(tile)):
            canvas.blit(self.outline_of(("fixture", kind), surf), (x - 1, y + C.BASE_FACE_Y - 1))

    def _draw_face_prop(self, canvas, state: GameState, tile, x: int, y: int) -> None:
        """Prop de face (32×24) na face da parede, logo depois dela: (tx·32, ty·32 + 8)."""
        prop = state.active.props.get(tuple(tile)) if state.active.props else None
        if prop is not None and prop.place == "face":
            self._blit_prop(canvas, prop, x, y + C.BASE_FACE_Y)

    def draw_prop_decals(self, canvas, state: GameState, cam) -> None:
        """Decal (a mancha de gelo): 32×32 no tile, junto do chão, antes dos objetos."""
        props = state.active.props
        if not props:
            return
        tx0, tx1, ty0, ty1 = self.base_view(cam)
        for tile, prop in props.items():
            if tile == prop.tile and prop.place == "decal" and tx0 <= prop.tx <= tx1 and ty0 <= prop.ty <= ty1:
                self._blit_prop(canvas, prop, prop.tx * T - cam[0], prop.ty * T - cam[1])

    def collect_props(self, items: list, canvas, state: GameState, cam) -> None:
        """Props de chão e mesas de parede na ordem de profundidade, com o pé na borda de baixo do tile (como o baú):
        sprite 32×40 em (tx·32, ty·32 − 8)."""
        props = state.active.props
        if not props:
            return
        tx0, tx1, ty0, ty1 = self.base_view(cam)
        for tile, prop in props.items():                 # v0.7 M4: prop grande aparece em vários tiles; desenha pela âncora
            w, h = prop.type.size
            if (tile == prop.tile and prop.place in ("floor", "desk")
                    and tx0 - w <= prop.tx <= tx1 and ty0 - h <= prop.ty <= ty1):
                items.append(((prop.ty + h) * T, lambda p=prop: self._blit_prop(
                    canvas, p, p.tx * T - cam[0], p.ty * T - cam[1] - C.PROP_LIFT)))

    def draw_prop_ghost(self, canvas, cam, kind, tile, valid, t) -> None:
        """Fantasma do prop: quadrado verde/vermelho no tile e o sprite translúcido (face: na face da parede)."""
        color = (127, 214, 122) if valid else (255, 106, 85)
        px, py = tile[0] * T - cam[0], tile[1] * T - cam[1]
        fw, fh = C.PROPS[kind].size                        # v0.7 M4: a pegada inteira (2×1, 2×2)
        pw, ph = fw * T, fh * T
        tint = pygame.Surface((pw, ph), pygame.SRCALPHA)
        tint.fill((*color, 51))
        canvas.blit(tint, (px, py))
        step = int(t * 8) % 8
        for i in range(0, pw - 2, 8):                      # formigas nas bordas de cima e de baixo
            k = (i + step) % (pw - 2)
            canvas.fill(color, (px + 1 + k, py + 1, 4, 2))
            canvas.fill(color, (px + 1 + k, py + ph - 3, 4, 2))
        for i in range(0, ph - 2, 8):                      # e nas laterais
            k = (i + step) % (ph - 2)
            canvas.fill(color, (px + 1, py + 1 + k, 2, 4))
            canvas.fill(color, (px + pw - 3, py + 1 + k, 2, 4))
        sprite = self.prop_surface(kind).copy()
        sprite.set_alpha(140)
        face = C.PROPS[kind].place == "face"
        canvas.blit(sprite, (px, py + C.BASE_FACE_Y) if face else (px, py - C.PROP_LIFT))
        if face:                                           # a face fica no tile da parede: contorno da área da face
            pygame.draw.rect(canvas, color, (px, py + C.BASE_FACE_Y, T, C.PROP_FACE_SIZE[1]), 1)

    def _draw_ruin_terminal(self, canvas, state: GameState, tile, x: int, y: int) -> None:
        """v0.7 M1: o terminal de uma ruína é uma parede da casca com o sprite do terminal (o mesmo da caverna) na face,
        quando tem chão embaixo (a planta garante). O alvo do E ganha o contorno claro."""
        if tile in state.world.ruin_terminals and not state.base.is_wall((tile[0], tile[1] + 1)):
            self._draw_terminal(canvas, tile[0], tile[1], x, y, "ruin_log")

    def draw_base_door(self, canvas, state: GameState, door: BaseBlock, tile, cam) -> None:
        """Quadro de 32×56 da porta em (x, y−24): moldura, folha e soleira (o tile não desenha chão à parte). O
        sprite é o da orientação e da borda de fora (variante B, ver BaseGrid.layout). Dupla: cada tile pega a sua
        metade (a 1ª nos quadros 0–3 da tira, a 2ª nos 4–7)."""
        orient, edge = state.base.layout(door)
        x, y = tile[0] * T - cam[0], tile[1] * T - cam[1]
        name = f"{'base_door2' if door.is_double else 'base_door'}_{orient}_{edge}"
        sheet = self.sprites.get(name)
        if sheet is None:
            canvas.fill((120, 110, 100), (x, y - C.BASE_WALL_LIFT + 8, T, T + C.BASE_WALL_LIFT - 8))
            return
        half = door.tiles.index(tuple(tile)) if door.is_double else 0
        canvas.blit(sheet, (x, y - C.BASE_WALL_LIFT),
                    ((half * C.DOOR_FRAMES + door.frame_index) * T, 0, T, T + C.BASE_WALL_LIFT))

    def draw_base_ghost(self, canvas, cam, kind, tile, rotation, valid, t) -> None:
        """Fantasma do construtor pros blocos: quadrado verde/vermelho em cada tile (a dupla mostra 2×1 ou 1×2) e o
        sprite translúcido por cima."""
        color = (127, 214, 122) if valid else (255, 106, 85)
        tiles = GameState.base_tiles(kind, tile, rotation)
        for tx, ty in tiles:
            px, py = tx * T - cam[0], ty * T - cam[1]
            tint = pygame.Surface((T, T), pygame.SRCALPHA)
            tint.fill((*color, 51))
            canvas.blit(tint, (px, py))
            step = int(t * 8) % 8
            for i in range(0, T - 2, 8):
                k = (i + step) % (T - 2)
                for rx, ry, w, h in [(px + 1 + k, py + 1, 4, 2), (px + 1 + k, py + T - 3, 4, 2),
                                     (px + 1, py + 1 + k, 2, 4), (px + T - 3, py + 1 + k, 2, 4)]:
                    canvas.fill(color, (rx, ry, w, h))
        px, py = tile[0] * T - cam[0], tile[1] * T - cam[1]
        if kind == C.BASE_FLOOR:
            sprite = self.sprites.get("base_floor_0")
            area = None
            dest = (px, py)
        elif kind == C.BASE_WALL:
            sprite = self.sprites.get("base_wall_top")
            area = (0, 0, T, T)                                  # a peça isolada do atlas (bloco 0,0–32,32)
            dest = (px, py - C.BASE_WALL_LIFT)
        else:
            horizontal = kind == C.BASE_DOOR2 and rotation % 2 == 0 or kind == C.BASE_DOOR
            sprite = self.sprites.get(f"{'base_door2' if kind == C.BASE_DOOR2 else 'base_door'}_"
                                      f"{'h_s' if horizontal else 'v_e'}")
            area = (0, 0, T, T + C.BASE_WALL_LIFT)
            dest = (px, py - C.BASE_WALL_LIFT)
            if kind == C.BASE_DOOR2 and sprite is not None:     # as 2 metades fechadas (quadro 0 e quadro 4)
                for half, (dx, dy) in enumerate(((0, 0), (T, 0) if rotation % 2 == 0 else (0, T))):
                    piece = sprite.subsurface((half * C.DOOR_FRAMES * T, 0, T, T + C.BASE_WALL_LIFT)).copy()
                    piece.set_alpha(140)
                    canvas.blit(piece, (dest[0] + dx, dest[1] + dy))
                return
        if sprite is not None:
            piece = sprite.subsurface(area).copy() if area else sprite.copy()
            piece.set_alpha(140)
            canvas.blit(piece, dest)

    def dispenser_frame(self, state: GameState, m, t: float) -> pygame.Surface:
        """Sprite do Dispersor agora: soprando (tira de 4 quadros a 6 fps) quando vedado, a tira âmbar no vazamento,
        o parado sem água ou sem energia (ou sem a tira)."""
        still = self.surface(C.MACHINES[m.kind].sprite, lambda: art.machine(m.kind))[0]
        status = state.dispenser_state(m, self.power_factor)
        phase = tile_phase(m.tx, m.ty)
        idx = (int(t * C.DISPENSER_FPS) + phase) % ANIM_FRAMES
        if status == "sealed":
            return self.anim_surface(C.MACHINES[m.kind].sprite, still, idx)
        if status in ("leak", "small", "nodoor", "big", "nofloor"):
            return self.anim_surface(C.MACHINES[m.kind].sprite + "_leak", still, idx)
        return still

    def draw_dispenser(self, canvas, state: GameState, m, ax, ay, t: float) -> None:
        self._blit_anchored(canvas, self.dispenser_frame(state, m, t), ax, ay)

    def draw_leaks(self, canvas, state: GameState, cam, t: float) -> None:
        """leak_blink.png (2 quadros de 32×56, aceso/apagado a ~2,5 Hz) em (x, y−24) do tile furado de cada Dispersor
        em "Vazamento". Depois dos objetos e do raio-x, por cima de tudo (chão, vazio, parede de baixo)."""
        sheet = None
        for m in state.machines:
            if not m.is_dispenser or m.submerged or m.build > 0:
                continue
            if state.dispenser_state(m, self.power_factor) not in ("leak", "nofloor") or m.seal is None:
                continue
            leak = m.seal.leak
            if leak is None:
                continue
            x, y = leak[0] * T - cam[0], leak[1] * T - cam[1]
            if not (-T < x < self.view_w and -T < y - 24 < self.view_h):
                continue
            if sheet is None:
                sheet = self.sprites.get("leak_blink")
            frame = int(t * C.LEAK_BLINK_HZ * 2) % 2
            if sheet is not None:
                canvas.blit(sheet, (x, y - C.BASE_WALL_LIFT), (frame * T, 0, T, T + C.BASE_WALL_LIFT))
            elif frame == 0:
                canvas.fill((235, 70, 60), (x + 2, y + 2, T - 4, T - 4), special_flags=0)

    # ---- morros orgânicos da superfície (v0.4 Marco 2 · game/hills.py) ----------
    def organic_hills(self, state: GameState) -> bool:
        """Morro com borda orgânica? Com sprites e com a arte dos morros presente: na superfície (hills.py) e, desde
        o v0.5 M3.4, na rocha da caverna (cave_rocks.py)."""
        if not self.sprites.enabled:
            return False
        if not state.active.has_base:
            return C.ORGANIC_CAVE and self.cave_rock_blocks().ok
        return C.ORGANIC_HILLS and self.hill_blocks().ok

    def _ore_rgba(self) -> dict:
        ore = {}
        for resource in C.ORE_TILES.values():
            surf = self.surface(f"ore_{resource}", lambda r=resource: art.ore(r, 0), f"ore_{resource}#0")[0]
            rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2)
            alpha = pygame.surfarray.array_alpha(surf).T
            ore[resource] = np.dstack([rgb, alpha]).astype(np.uint8)
        return ore

    def cave_rock_blocks(self) -> cave_rocks.CaveRocks:
        if self._cave_rocks is None:
            self._cave_rocks = cave_rocks.CaveRocks(self._ore_rgba())
        return self._cave_rocks

    def cave_strips(self, state: GameState, cam) -> dict:
        """{(bx, by): {linha: (surf, x, y)}} da rocha da caverna que aparece na tela (e 1 bloco de folga por frame)."""
        cb = self.cave_rock_blocks()
        world = state.world
        bp = C.HILL_BLOCK * T
        cam_x, cam_y = cam
        bx0, bx1 = cam_x // bp, (cam_x + self.view_w) // bp
        by0 = (cam_y // T - 1) // C.HILL_BLOCK
        by1 = ((cam_y + self.view_h) // T + 2) // C.HILL_BLOCK
        nb_x = -(-world.width // C.HILL_BLOCK)
        nb_y = -(-world.height // C.HILL_BLOCK)
        out = {}
        for by in range(max(0, by0), min(nb_y, by1 + 1)):
            for bx in range(max(0, bx0), min(nb_x, bx1 + 1)):
                out[(bx, by)] = cb.strips(world, bx, by)
        budget = C.HILL_PREFETCH
        for by in range(max(0, by0 - 1), min(nb_y, by1 + 2)):
            for bx in range(max(0, bx0 - 1), min(nb_x, bx1 + 2)):
                if budget <= 0:
                    return out
                if (bx, by) not in out and not cb.cached(world, bx, by):
                    cb.strips(world, bx, by)
                    budget -= 1
        return out

    def hill_blocks(self) -> hills.HillBlocks:
        if self._hills is None:
            self._hills = hills.HillBlocks(self._ore_rgba())
        return self._hills

    def _hill_stage(self, bx: int, by: int) -> tuple:
        """(etiqueta, estágios) do bloco: o estágio do mapa inteiro, ou por tile no meio de uma transição."""
        m = self.stage_map
        if m.step == 0:
            return ("all", m.stage), m.stage
        key = (m.stage, m.step, m._sources)
        memo = self._hill_stage_tags.get((bx, by))
        if memo is not None and memo[0] == key:
            return memo[1], memo[2]
        i0, i1, j0, j1 = hills.window_bounds(bx, by)
        grid = np.array([[m.stage_at(i, j) for i in range(i0, i1)] for j in range(j0, j1)], np.uint8)
        tag = ("tiles", grid.tobytes())
        if (grid == grid.flat[0]).all():           # o bloco inteiro num estágio só: dá pra dividir a cor
            tag, grid = ("all", int(grid.flat[0])), int(grid.flat[0])
        self._hill_stage_tags[(bx, by)] = (key, tag, grid)
        return tag, grid

    def hill_strips(self, state: GameState, cam) -> dict:
        """{(bx, by): {linha: (surf, x, y)}} dos blocos que aparecem na tela (assando o que faltar) e, de
        folga, assa até C.HILL_PREFETCH bloco(s) da volta por frame (o que vai aparecer andando)."""
        hb = self.hill_blocks()
        world = state.world
        geo = getattr(state.active, "geo", None)   # trilha A: layer.geo; sem ele, tudo planalto

        def regions(i0, i1, j0, j1):
            out = np.zeros((j1 - j0, i1 - i0), np.uint8)
            if geo is not None:
                a, b, c, d = max(0, i0), min(world.width, i1), max(0, j0), min(world.height, j1)
                out[c - j0:d - j0, a - i0:b - i0] = geo.region[c:d, a:b]
            return out

        bp = C.HILL_BLOCK * T
        cam_x, cam_y = cam
        bx0, bx1 = cam_x // bp, (cam_x + self.view_w) // bp
        # linhas visíveis: do topo (24 px acima) da 1ª até a face da última que ainda aparece
        by0 = (cam_y // T - 1) // C.HILL_BLOCK
        by1 = ((cam_y + self.view_h) // T + 2) // C.HILL_BLOCK
        nb_x = -(-world.width // C.HILL_BLOCK)
        nb_y = -(-world.height // C.HILL_BLOCK)
        out = {}
        for by in range(max(0, by0), min(nb_y, by1 + 1)):
            for bx in range(max(0, bx0), min(nb_x, bx1 + 1)):
                out[(bx, by)] = hb.strips(world, regions, self._hill_stage(bx, by), bx, by)
        budget = C.HILL_PREFETCH
        ring = C.HILL_PREFETCH and 1
        for by in range(max(0, by0 - ring), min(nb_y, by1 + ring + 1)):
            for bx in range(max(0, bx0 - ring), min(nb_x, bx1 + ring + 1)):
                if budget <= 0:
                    return out
                if (bx, by) not in out and not hb.cached(world, bx, by):
                    hb.strips(world, regions, self._hill_stage(bx, by), bx, by)
                    budget -= 1
        return out

    def visible_formations(self, state: GameState, cam, margin: int = 0) -> list[tuple]:
        """[(formação, sprite, x, y)] das formações da camada que aparecem na tela (x, y = canto do sprite no mundo).
        v0.4 M3.5: cada bloco de gelo dos portões entra aqui como uma formação própria (ice_blocks.IceBlock, com o
        `base_px` no pé dele): ordena pelo pé no desenho e acende o raio-x igual às formações."""
        geo = getattr(state.active, "geo", None)
        if geo is None:
            return []
        out = []
        cam_x, cam_y = cam

        def visible(surf, x, y) -> bool:
            w, h = surf.get_size()
            return x + w > cam_x - margin and x < cam_x + self.view_w + margin \
                and y + h > cam_y - margin and y < cam_y + self.view_h + margin

        for f in layers.current_formations(state.active):      # todas menos o gelo-portão (vai em blocos)
            frame = self.giant_breath.frame(self.anim_t) if f.kind == "ice_giant" else 0
            surf, x, y = self.formation_sprites.placement(f, self.stage_map.stage_at(*hills.foot_tile(f)),
                                                          self.formation_variant(state, f), frame)
            if visible(surf, x, y):
                out.append((f, surf, x, y))
        giant = getattr(geo, "giant", None)
        if giant is not None:                                    # v0.5 M3.6.2: estilhaços em volta do gelo gigante
            if not self.giant_shards:
                self.giant_shards = ice_giant.shards(giant.giant)
            stage = self.stage_map.stage_at(*hills.foot_tile(giant.giant))
            for b in self.giant_shards:
                surf, x, y = self.ice_block_sprites.placement(b, stage)
                if visible(surf, x, y):
                    out.append((b, surf, x, y))
        for b in state.active.gate_blocks:
            if ice_blocks.is_giant_gate(geo, b.gate):                    # M3.6.3: o portão grande: o tile do meio da entrada
                stage = self.stage_map.stage_at(*geo.giant.entry[len(geo.giant.entry) // 2])
            else:
                stage = self.stage_map.stage_at(*hills.foot_tile(geo.pockets[b.gate].gate))
            surf, x, y = self.ice_block_sprites.placement(b, stage)
            if visible(surf, x, y):
                out.append((b, surf, x, y))
        return out

    def player_occluded(self, state: GameState) -> bool:
        """O topo elevado de alguma parede da linha de baixo (ou uma formação na frente) está cobrindo o player?"""
        p = state.player
        row_below = int((p.y - 1) // T) + 1
        cols = {int((p.x - 10) // T), int((p.x + 9) // T)}
        grid = state.base                                # v0.5 M2: parede da base e porta fechada/abrindo (quadros 0–1)
        if grid.blocks and any((b := grid.get((tx, row_below))) is not None and b.xray for tx in cols):
            return True
        return any(state.world.is_wall(tx, row_below) for tx in cols) or self.formation_occludes(state)

    def formation_occludes(self, state: GameState) -> bool:
        """Uma formação desenhada depois do player (pé dela mais embaixo) cobre o corpo dele? Pela silhueta do
        sprite (sem a sombra), pra o raio-x não acender só por estar perto."""
        p = state.player
        px, py = snap(p.x), snap(p.y)
        body = pygame.Rect(px - 8, py - 28, 16, 26)
        for f, surf, x, y in self.visible_formations(state, (px - 200, py - 200)):
            if f.base_px[1] <= p.y or not body.colliderect((x, y, *surf.get_size())):
                continue
            box = pygame.mask.Mask(body.size, fill=True)
            if self.formation_sprites.mask(surf).overlap(box, (body.x - x, body.y - y)):
                return True
        return False

    def _draw_player_silhouette(self, canvas, state: GameState, cam, t: float = 0.0) -> None:
        """Player escondido atrás de parede (ex.: túnel de 1 tile): redesenha ele translúcido por cima,
        tipo raio-x, pra nunca perder o personagem de vista. A ilusão de profundidade continua."""
        if not self.player_occluded(state):
            return
        surf, flip = self._player_frame(state, t)
        ghost = (pygame.transform.flip(surf, True, False) if flip else surf.copy())
        ghost.set_alpha(95)
        p = state.player
        canvas.blit(ghost, (snap(p.x) - cam[0] - ghost.get_width() // 2, snap(p.y) - cam[1] - ghost.get_height()))

    def _draw_wall(self, canvas, world, tx, ty, sx, sy, stage) -> None:
        """Parede alta: topo 32×32 em (x, y-24) e, se embaixo tem chão, face 32×24 em (x, y+8)."""
        P = C.PALETTES[stage]
        kind = world.get(tx, ty)
        v = int(hash01(tx, ty, 3) * 3)
        top_y = sy - WALL_LIFT
        surf, fallback = self.surface(f"wall_{stage}_{v}", lambda: art.wall(stage, v))
        canvas.blit(surf, (sx, top_y))
        if self.stage_map.step > 0:
            self._blend_edges(canvas, world, tx, ty, sx, top_y, self.stage_map.stage_at(tx, ty), True,
                              lambda st: (f"wall_{st}_{v}", lambda: art.wall(st, v)))
        open_up = not world.is_wall(tx, ty - 1)
        open_left = not world.is_wall(tx - 1, ty)
        open_right = not world.is_wall(tx + 1, ty)
        if fallback:   # bordas iluminadas onde o topo encontra o vazio (os PNGs não precisam)
            if open_up:
                canvas.fill(P["edge"], (sx, top_y, T, 2))
            if open_left:
                canvas.fill(P["edge"], (sx, top_y, 1, T))
            if open_right:
                canvas.fill(P["rock_dot"], (sx + T - 1, top_y, 1, T))
            if stage == "green" and hash01(tx, ty, 70) < 0.5:
                canvas.blit(self.surface(None, lambda: art.moss(v), f"moss#{v}")[0], (sx, top_y))
        else:          # contorno escuro fininho: separa o topo elevado do chão atrás dele
            if open_up:
                canvas.blit(self.outline_h, (sx, top_y))
            if open_left:
                canvas.blit(self.outline_v, (sx, top_y))
            if open_right:
                canvas.blit(self.outline_v, (sx + T - 1, top_y))
        resource = C.ORE_TILES.get(kind)
        if resource:   # o minério acompanha o topo elevado
            ov = int(hash01(tx, ty, 80) * 3)
            canvas.blit(self.surface(f"ore_{resource}", lambda: art.ore(resource, ov), f"ore_{resource}#{ov}")[0], (sx, top_y))
        if kind == C.BEDROCK:
            canvas.blit(self.bedrock_shade, (sx, top_y))
        if not world.is_wall(tx, ty + 1):
            canvas.blit(self.surface(f"wall_face_{stage}", lambda: art.wall_face(stage))[0], (sx, sy + FACE_Y))
            if kind == C.TERMINAL:   # o terminal fica pendurado na face
                self._draw_terminal(canvas, tx, ty, sx, sy)

    def _draw_terminal(self, canvas, tx, ty, sx, sy, target: str = "terminal") -> None:
        term = self.surface("terminal", art.terminal)[0]
        canvas.blit(self.anim_surface("terminal", term, anim_frame_index(self.clock, tile_phase(tx, ty))), (sx, sy))
        if self.highlight is not None and self.highlight == (target, (tx, ty)):
            canvas.blit(self.outline_of("terminal", term), (sx - 1, sy - 1))

    def _draw_floor(self, canvas, world, tx, ty, sx, sy, stage, stage_num, t, wall_shadows=True) -> None:
        # deserto: areia com a variação da Designer (dunas em faixas); FLOOR (caverna) com o sorteio de sempre
        if world.sand_variants is not None and world.get(tx, ty) != C.FLOOR and 0 <= ty < world.height \
                and 0 <= tx < world.width:
            v = world.sand_variants[ty][tx]
            sprite = lambda st: (f"sand_{st}_{v}", lambda: art.sand(st, v))       # noqa: E731
        else:
            v = int(hash01(tx, ty, 3) * 4)
            sprite = lambda st: (f"floor_{st}_{v}", lambda: art.floor(st, v))     # noqa: E731
        canvas.blit(self.surface(*sprite(stage))[0], (sx, sy))
        if self.stage_map.step > 0:
            self._blend_edges(canvas, world, tx, ty, sx, sy, stage_num, False, sprite)
        if self._wet(world, tx, ty):
            self._draw_water(canvas, world, tx, ty, sx, sy, stage, t)
        # sombra que a parede projeta no chão
        if wall_shadows and world.is_wall(tx, ty - 1):
            canvas.blit(self.shadow_top, (sx, sy))
        if wall_shadows and world.is_wall(tx - 1, ty):
            canvas.blit(self.shadow_left, (sx, sy))

    def _floor_overlays(self, canvas, world, tx, ty, sx, sy, t, wall_shadows=True, water=True) -> None:
        """Por cima do chão assado: a água por tile (só onde o lago orgânico ainda não foi assado) e a sombra das
        paredes."""
        if water and self._wet(world, tx, ty):
            self._draw_water(canvas, world, tx, ty, sx, sy, art_key(self.stage_map.stage_at(tx, ty)), t)
        if wall_shadows and world.is_wall(tx, ty - 1):
            canvas.blit(self.shadow_top, (sx, sy))
        if wall_shadows and world.is_wall(tx - 1, ty):
            canvas.blit(self.shadow_left, (sx, sy))

    # ---- lago orgânico (v0.4 M3.5, game/lake.py) -------------------------------
    def draw_lake(self, canvas, world, cam, t: float) -> set | None:
        """A água das bacias com a margem seguindo o geo.height contínuo (blocos assados). Devolve os blocos que
        ainda não têm assado (lá a água vai por tile, no autotile de antes) ou None se o lago orgânico não vale
        (sem água: o conjunto vazio)."""
        if world.geo is None or not world.terraforms or not self.organic_lake:
            return None
        if world.water_level <= 0:
            return set()
        self.lake.sync = self.ground.sync
        entries, missing = self.lake.prepare(world, cam, (self.view_w, self.view_h))
        self.lake.draw(canvas, entries, cam, self._lake_stage, lambda st: (self.water_atlas(st)[0], self.water_tiles),
                       t)
        return missing

    def _lake_stage(self, bx: int, by: int) -> tuple:
        """(etiqueta, estágios) do bloco do lago: a arte do estágio do mapa inteiro, ou por tile na transição."""
        m = self.stage_map
        if m.step == 0:
            return ("all", m.stage), art_key(m.stage)
        key = (m.stage, m.step, m._sources)
        memo = self._lake_stage_tags.get((bx, by))
        if memo is not None and memo[0] == key:
            return memo[1], memo[2]
        n = lake.BT
        grid = np.array([[art_key(m.stage_at(bx * n + i, by * n + j)) for i in range(n)] for j in range(n)])
        if (grid == grid.flat[0]).all():
            tag, stages = ("all", str(grid.flat[0])), str(grid.flat[0])
        else:
            tag, stages = ("tiles", "|".join(grid.ravel().tolist())), grid
        self._lake_stage_tags[(bx, by)] = (key, tag, stages)
        return tag, stages

    # ---- água (autotile A2, ver game/autotile.py) ------------------------------
    def sync_water(self, world) -> None:
        """Zera o memo da água quando ela pode ter mudado. Com geo (lago nas bacias, M3.3), a água só depende do
        `water_level` (o estágio não entra, e nas bacias nada é minerado nem nasce): o memo vale entre frames e é
        zerado quando o nível ou o mundo mudam (umas poucas vezes por minuto). Sem geo, zera todo frame."""
        key = (id(world), world.water_level) if world.geo is not None else None
        if key is None or key != self._wet_key:
            self._wet_memo.clear()
        self._wet_key = key

    def _wet(self, world, x: int, y: int) -> bool:
        """Água no tile, no estágio visual DELE (na transição, o vizinho pode estar em outro estágio)."""
        key = (x, y)
        wet = self._wet_memo.get(key)
        if wet is None:
            wet = self._wet_memo[key] = world.is_water(x, y, self.stage_map.stage_at(x, y))
        return wet

    def water_atlas(self, stage: str) -> tuple[pygame.Surface, bool]:
        """Atlas A2 64×96 do estágio: o sprite water_auto_{stage}.png da Designer ou o gerado por código
        a partir do water_{stage}. Devolve (atlas, é_fallback)."""
        key = ("water_atlas", stage)
        if key not in self._fx:
            sprite = self.sprites.get(f"water_auto_{stage}")
            if sprite is not None:
                self._fx[key] = (sprite, False)
            else:
                texture = self.surface(f"water_{stage}", lambda: art.water(stage))[0]
                self._fx[key] = (autotile.build_atlas(texture, stage), True)
        return self._fx[key]

    def _draw_water(self, canvas, world, tx, ty, sx, sy, stage: str, t: float) -> None:
        key = autotile.tile_key(lambda x, y: self._wet(world, x, y), tx, ty)
        atlas = self.water_atlas(stage)[0]
        canvas.blit(self.water_tiles.get(stage, atlas, key), (sx, sy))
        # reflexos que andam devagar, sem passar pra areia: encolhem do lado onde a margem está
        tl, tr, bl, br = key
        left = 6 if autotile.OUTER in (tl, bl) or autotile.VEDGE in (tl, bl) else 0
        right = 26 if autotile.OUTER in (tr, br) or autotile.VEDGE in (tr, br) else T
        top = 8 if autotile.OUTER in (tl, tr) or autotile.HEDGE in (tl, tr) else 0
        bottom = 24 if autotile.OUTER in (bl, br) or autotile.HEDGE in (bl, br) else T
        area = pygame.Rect(sx + left, sy + top, right - left, bottom - top)
        h = hash01(tx, ty, 5)
        o = int((t * 5.4 + h * 24) % 24)
        for rect in ((sx + 4 + o, sy + 10 + int(h * 12), 5, 1), (sx + 4 + (o + 12) % 22, sy + 21 + int(h * 5), 4, 1)):
            clipped = area.clip(rect)
            if clipped.w:
                canvas.fill((170, 214, 230), clipped)

    # Ordem de "pontilhado" (Bayer 4×4): espalha os pixels da mistura sem formar listras.
    BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
    BLEND_DEPTH = 16   # px: até onde a mistura entra no tile (meio tile)
    BLEND_CELL = 2     # px: tamanho de cada "ponto" do pontilhado

    def _blend_edges(self, canvas, world, tx, ty, x, y, stage_num, solid, sprite) -> None:
        """Fronteira da mancha de transição: se o vizinho (do mesmo tipo: chão com chão, parede com
        parede) está em outro estágio, a versão daquele estágio entra pontilhada pela borda deste tile
        (50% na borda, sumindo até o meio). Como os dois lados fazem isso, a troca de estágio vira uma
        faixa de mistura em vez de um degrau de cor. `sprite(arte)` devolve (nome, desenho de fallback).
        Estágios com a mesma arte (Tempestade e Árido) não têm fronteira."""
        art = art_key(stage_num)
        for direction, (dx, dy) in (("left", (-1, 0)), ("right", (1, 0)), ("up", (0, -1)), ("down", (0, 1))):
            other = self.stage_map.stage_at(tx + dx, ty + dy)
            if other != stage_num and art_key(other) != art and world.is_wall(tx + dx, ty + dy) == solid:
                canvas.blit(self._fringe(*sprite(art_key(other)), direction), (x, y))

    def _fringe(self, name: str, painter, direction: str) -> pygame.Surface:
        """O tile `name` recortado num pontilhado que encosta na borda `direction`."""
        key = ("fringe", name, direction)
        if key not in self._fx:
            tile = self.surface(name, painter)[0]
            fringe = pygame.Surface((T, T), pygame.SRCALPHA)
            cell = self.BLEND_CELL
            for y in range(0, T, cell):
                for x in range(0, T, cell):
                    depth = {"left": x, "right": T - cell - x, "up": y, "down": T - cell - y}[direction]
                    density = 0.5 * (1 - depth / self.BLEND_DEPTH)
                    if self.BAYER[(y // cell) % 4][(x // cell) % 4] / 16 < density:
                        fringe.blit(tile, (x, y), (x, y, cell, cell))
            self._fx[key] = fringe
        return self._fx[key]

    # ---- zona de O₂ -----------------------------------------------------------
    def draw_zone(self, canvas, cam, t) -> None:
        r = C.BASE_RADIUS
        z = self.zone_surf
        z.fill((0, 0, 0, 0))
        c = r + 2
        pygame.draw.circle(z, (89, 208, 230, 15), (c, c), r)
        dashes = 56
        offset = (t * 0.6) % 1
        for i in range(dashes):
            a0 = (i + offset) / dashes * math.tau
            a1 = (i + offset + 0.5) / dashes * math.tau
            p0 = (c + math.cos(a0) * r, c + math.sin(a0) * r)
            p1 = (c + math.cos(a1) * r, c + math.sin(a1) * r)
            pygame.draw.line(z, (89, 208, 230, 140), p0, p1, 2)
        canvas.blit(z, (C.BASE_CENTER[0] - c - cam[0], C.BASE_CENTER[1] - c - cam[1]))

    # ---- objetos (ordenados por Y) --------------------------------------------
    def collect_objects(self, canvas, state: GameState, cam, t: float) -> list[tuple[float, callable]]:
        """Tudo que fica em pé no chão, como (ay, função que desenha). Quem ordena é o build_draw_list."""
        cam_x, cam_y = cam
        items: list[tuple[float, callable]] = []

        world = state.world
        if state.active.has_base:
            ax, ay = C.POD_ANCHOR
            items.append((ay, lambda: self._draw_pod(canvas, ax - cam_x, ay - cam_y, t)))
        # cratera (3×3): objeto com o pé na borda de baixo (a borda de trás cobre os pés de quem está acima)
        if world.crater is not None:
            ctx, cty = world.crater
            cx, cy = ctx * T - cam_x, cty * T - cam_y
            impact = self.crater_impact(state)            # v0.4 M2: cratera de impacto com a tampa de gelo
            if impact is not None:
                surf, key, x, y = impact
                cx, cy = x - cam_x, y - cam_y
            else:
                surf, key = self.crater_surface(state.active.has_base)
            w, h = surf.get_size()
            if -w < cx < self.view_w and -h < cy < self.view_h:
                lit = self.highlight == ("ramp", (ctx, cty))
                items.append(((cty + 3) * T, lambda cx=cx, cy=cy, surf=surf, key=key, lit=lit: self._draw_ramp(
                    canvas, surf, key, cx, cy, lit)))
        # formações fixas (v0.4 Marco 2): sprite grande com a âncora no base_px (centro de baixo da pegada),
        # ordenado pelo pé igual às máquinas. A pegada é C.FORMATION; a sombra já vem no sprite. Os blocos de gelo
        # dos portões (M3.5) vêm junto, um objeto por bloco com o pé dele.
        for f, surf, x, y in self.visible_formations(state, cam):
            items.append((f.base_px[1], lambda s=surf, x=x - cam_x, y=y - cam_y: canvas.blit(s, (x, y))))
        # destroços (Marco 3): o sprite inteiro é um objeto com o pé na borda de baixo da área; caixas à parte
        for wreck in world.wrecks:
            bx, by = wreck.blit_pos
            sw, sh = wreck.spec.sprite_size
            x, y = bx - cam_x, by - cam_y
            if -sw < x < self.view_w and -sh < y < self.view_h:
                items.append((wreck.anchor[1], lambda w=wreck, x=x, y=y: self.draw_wreck(canvas, w, x, y)))
        for crate in state.crates.values():
            tx, ty = crate.tile
            x, y = tx * T - cam_x, ty * T - cam_y
            if -T < x < self.view_w and -T < y < self.view_h:
                items.append(((ty + 1) * T, lambda c=crate, x=x, y=y: self.draw_crate(canvas, c, x, y)))
        for (tx, ty), box in state.containers.items():          # contêiner lacrado/aberto (v0.5 M4): pé na borda de baixo
            surf = self.container_surface(box.opened)
            w, h = surf.get_size()
            x, y = (tx * T + T // 2 - w // 2) - cam_x, (ty + 1) * T - h - cam_y
            if -w < x < self.view_w and -h < y < self.view_h:
                items.append(((ty + 1) * T, lambda t=(tx, ty), o=box.opened, x=x, y=y:
                              self.draw_container(canvas, t, x, y, o)))
        if state.layer == layers.VESPER:                       # v0.7 M4: o contêiner arrombado da câmara fria
            cw, ch = self.container_surface(True).get_size()
            for (tx, ty), kind in state.world.fixtures.items():
                if kind == "container_broken":
                    x, y = (tx * T + T // 2 - cw // 2) - cam_x, (ty + 1) * T - ch - cam_y
                    if -cw < x < self.view_w and -ch < y < self.view_h:
                        items.append(((ty + 1) * T, lambda t=(tx, ty), x=x, y=y: self.draw_container_broken(canvas, t, x, y)))
        self.blinks = [b for b in self.blinks if (t - b[2]) * C.SCAN_FPS < C.SCAN_BLINK_STEPS]
        for info, (bx, by), t0 in self.blinks:                 # v0.5 M1: o holograma piscando depois do desmonte
            step = int((t - t0) * C.SCAN_FPS)
            if step == 1:                                      # apagado, ACESO, apagado (C.SCAN_BLINK_STEPS)
                items.append((by, lambda i=info, x=bx - cam_x, y=by - cam_y: self._blit_anchored(
                    canvas, i["ghost"], x, y)))
        self.collect_base_objects(items, canvas, state, cam)
        self.collect_props(items, canvas, state, cam)
        for m in state.machines:
            mx, my = m.anchor                                  # centro da base (drill: centro dos 2×2)
            if -64 < mx - cam_x < self.view_w + 64 and -80 < my - cam_y < self.view_h + 80:
                scan = self.machine_scan(m, state)             # v0.5 M1: se construindo ou desmontando
                if scan is not None:
                    items.append((my, lambda m=m, mx=mx, my=my, sc=scan: self.draw_scan(
                        canvas, self.scan_info(m), sc[0], sc[1], mx - cam_x, my - cam_y)))
                    continue
                if m.submerged:                                # v0.4 M3.4: só da metade pra cima, parada
                    items.append((my, lambda m=m, mx=mx, my=my: self._blit_anchored(
                        canvas, self.submerged_surface(m), mx - cam_x, my - cam_y)))
                elif m.broken:                                 # v0.7 M1: ruína, parada no quadro 0 e escurecida
                    items.append((my, lambda m=m, mx=mx, my=my: self._blit_anchored(
                        canvas, self.broken_surface(m.kind), mx - cam_x, my - cam_y)))
                elif m.is_drill:
                    items.append((my, lambda m=m, mx=mx, my=my: self.draw_drill(canvas, m, mx - cam_x, my - cam_y, self.machine_t)))
                elif m.is_chest:
                    items.append((my, lambda m=m, mx=mx, my=my: self._blit_anchored(
                        canvas, self.chest_surface(m.kind, m is self.open_chest), mx - cam_x, my - cam_y)))
                elif m.is_station:
                    items.append((my, lambda m=m: self.draw_station(canvas, m, cam, t)))
                elif m.is_dispenser:
                    items.append((my, lambda m=m, mx=mx, my=my: self.draw_dispenser(
                        canvas, state, m, mx - cam_x, my - cam_y, t)))
                else:
                    items.append((my, lambda m=m, mx=mx, my=my: self.draw_machine(
                        canvas, m.kind, mx - cam_x, my - cam_y, self.machine_t, m.rotation,
                        frame=self.machine_anim_index(m, self.powered, t))))
                if m is self.highlight:   # alvo do E: contorno logo depois dele (quem está na frente cobre)
                    items.append((my, lambda m=m, mx=mx, my=my: self._blit_anchored(
                        canvas, self.highlight_outline(m), mx - cam_x, my - cam_y + 1)))

        grid = state.base
        occupied = (lambda t: state.machine_at(t) or grid.get(t)) if grid.blocks else state.machine_at   # máquina ou bloco da base
        tx0, ty0 = cam_x // T, cam_y // T
        for ty in range(max(0, ty0), min(world.height, ty0 + self.view_h // T + 2)):   # rochas pequenas (pé na borda de baixo)
            row = world.tiles[ty]
            for tx in range(max(0, tx0), min(world.width, tx0 + self.view_w // T + 2)):
                resource = C.SMALL_ROCKS.get(row[tx])
                if resource:
                    snow = world.geo is not None and world.geo.region_at(tx, ty) == FROST   # v0.5 M3.3: neve na rocha (só superfície)
                    items.append(((ty + 1) * T, lambda tx=tx, ty=ty, r=resource, sn=snow: self.draw_small_rock(
                        canvas, tx * T - cam_x, ty * T - cam_y, r, tx, ty, sn)))
        if self.stage_map.next_stage >= C.GREEN_STAGE:   # plantas nascem junto com a mancha verde
            for ty in range(ty0, ty0 + self.view_h // T + 3):
                for tx in range(tx0, tx0 + self.view_w // T + 2):
                    kind = state.world.plant_at(tx, ty)
                    if kind and self.stage_map.stage_at(tx, ty) >= C.GREEN_STAGE and not occupied((tx, ty)):
                        px, py = tx * T + T // 2, (ty + 1) * T
                        surf = self.surface(f"plant_{kind}", lambda k=kind: art.plant(k))[0]
                        items.append((py, lambda s=surf, px=px, py=py: canvas.blit(
                            s, (px - cam_x - s.get_width() // 2, py - cam_y - s.get_height()))))

        geo = self.surface_geo(state)
        if geo is not None:                      # decoração solta com altura (v0.4 M2): não colide, ordena pelo pé
            ground = self.ground
            moss_on = ground.moss_on
            tx1 = tx0 + self.view_w // T + 1
            for ty in range(max(0, ty0 - 1), min(world.height, ty0 + self.view_h // T + 2)):
                for tx, name, v in ground.decor_row(ty):
                    if not (tx0 - 1 <= tx <= tx1) or not decor_tile_free(world, tx, ty, occupied):
                        continue
                    surf = ground.decor_surface(name, v, stage_key(self.stage_map.stage_at(tx, ty)))
                    if surf is not None:
                        px, py = tx * T + T // 2, ty * T + DECOR_FOOT
                        items.append((py, lambda s=surf, px=px, py=py: canvas.blit(
                            s, (px - cam_x - s.get_width() // 2, py - cam_y - s.get_height()))))
                # v9 (M3.0): pé com folga, espelho, e o musgo logo depois da pedra só no Verde (estágio do tile do pé)
                for d in ground.decor_row_v9(ty):
                    if not (tx0 - 1 <= d.tx <= tx1) or not decor_tile_free(world, d.tx, ty, occupied):
                        continue
                    stage = self.stage_map.stage_at(d.tx, ty)
                    if stage >= C.MIST_STAGE and world.is_water(d.tx, ty, stage):
                        continue                         # nada debaixo d'água (a poça de hoje; o lago do M3.3)
                    key = stage_key(stage)
                    surfs = [sf for sf in (ground.decor_surface(n, d.v, key, d.flip)
                                           for n in decor_layers(d.name, stage, moss_on)) if sf is not None]
                    if surfs:
                        items.append((d.foot_y, lambda ss=surfs, px=d.foot_x, py=d.foot_y: [canvas.blit(
                            sf, (px - cam_x - sf.get_width() // 2, py - cam_y - sf.get_height())) for sf in ss]))

        p = state.player
        items.append((p.y, lambda: self._draw_player(canvas, state, snap(p.x) - cam_x, snap(p.y) - cam_y, t)))
        return items

    def crater_impact(self, state: GameState) -> tuple[pygame.Surface, tuple, int, int] | None:
        """(sprite, chave, x, y no mundo) da cratera de impacto da superfície na etapa do gelo (layer.crater_ice):
        a âncora do sprite cai no centro dos 3×3. None na caverna ou sem a arte (aí vale o crater_ramp)."""
        world = state.world
        if not state.active.has_base or world.crater is None or not self.sprites.enabled:
            return None
        ctx, cty = world.crater
        level = state.active.crater_ice
        stage = self.stage_map.stage_at(ctx + 1, cty + 1)
        surf = self.crater_sprites.crater(level, stage)
        if surf is None:
            return None
        ax, ay = hills.crater_anchor(level)
        return surf, ("impact", level, stage), ctx * T + 48 - ax, cty * T + 48 - ay

    def draw_crater_ejecta(self, canvas, state: GameState, cam) -> None:
        """Manto de ejeção em volta da cratera de impacto: decalque no chão (não colide), centrado nos 3×3."""
        if self.crater_impact(state) is None:
            return
        ctx, cty = state.world.crater
        surf = self.crater_sprites.ejecta(self.stage_map.stage_at(ctx + 1, cty + 1))
        if surf is None:
            return
        x = ctx * T + 48 - surf.get_width() // 2 - cam[0]
        y = cty * T + 48 - surf.get_height() // 2 - cam[1]
        if -surf.get_width() < x < self.view_w and -surf.get_height() < y < self.view_h:
            canvas.blit(surf, (x, y))

    def gate_frost(self, state: GameState, cam) -> list[tuple[pygame.Surface, int, int]]:
        """[(geada, x, y no mundo)] dos gelos-portão derretendo ou abertos (p > 0) que aparecem na tela (v0.4 M3.2).
        Fica no pé do portão (o base_px da caixa 4×2), na camada de decalques: o portão sem gelo é só ela."""
        layer = state.active
        geo = getattr(layer, "geo", None)
        if geo is None or not self.sprites.enabled:
            return []
        out = []
        cam_x, cam_y = cam
        for i, p in enumerate(geo.pockets):
            if i >= len(layer.gate_melt) or layer.gate_melt[i] <= 0:
                continue
            surf = self.frost_ring.surface(self.stage_map.stage_at(*hills.foot_tile(p.gate)))
            if surf is None:
                continue
            x, y = hills.frost_ring_pos(p.gate, surf)
            w, h = surf.get_size()
            if x + w > cam_x and x < cam_x + self.view_w and y + h > cam_y and y < cam_y + self.view_h:
                out.append((surf, x, y))
        return out

    def draw_gate_frost(self, canvas, state: GameState, cam) -> None:
        for surf, x, y in self.gate_frost(state, cam):
            canvas.blit(surf, (x - cam[0], y - cam[1]))

    def draw_giant_frost(self, canvas, state: GameState, cam) -> None:
        """Geada grande no chão em volta do gelo gigante (v0.5 M3.6.2), na camada de decalques."""
        geo = getattr(state.active, "geo", None)
        giant = getattr(geo, "giant", None)
        if giant is None or not self.sprites.enabled:
            return
        surf = self.frost_field.surface(self.stage_map.stage_at(*hills.foot_tile(giant.giant)))
        if surf is None:
            return
        x, y = hills.frost_field_pos(giant.giant, surf)
        w, h = surf.get_size()
        if x + w > cam[0] and x < cam[0] + self.view_w and y + h > cam[1] and y < cam[1] + self.view_h:
            canvas.blit(surf, (x - cam[0], y - cam[1]))

    def container_surface(self, opened: bool = False) -> pygame.Surface:
        """Contêiner lacrado: container_sealed.png (r3d v1.1, 40×44, aprovado; o pé cai no centro de baixo do tile, como
        as máquinas de 40 px) ou, sem a arte, o placeholder por código. Aberto (v0.5 M4): container_open.png (mesma
        âncora) ou, enquanto a arte não vem, o lacrado escurecido com a tampa aberta (art.opened_container)."""
        sealed = self.surface("container_sealed", art.sealed_container)[0]
        if not opened:
            return sealed
        return self.surface("container_open", lambda: art.opened_container(sealed))[0]

    def draw_container(self, canvas, tile, x: int, y: int, opened: bool = False) -> None:
        surf = self.container_surface(opened)
        canvas.blit(surf, (x, y))
        if self.highlight == ("container", tile):          # alvo do E: contorno igual ao da caixa de saque
            canvas.blit(self.outline_of(("container", opened), surf), (x - 1, y - 1))

    def crater_surface(self, surface_layer: bool = True) -> tuple[pygame.Surface, str]:
        """A rampa da camada (96×96) e a chave dela: na superfície a cratera com a rampa de descida aberta
        (crater_ramp), na caverna a rampa de subida (cave_ramp_up, com fallback art.cave_ramp_up)."""
        if surface_layer:
            return self.surface("crater_ramp", lambda: art.crater(open_ramp=True))[0], "crater_ramp"
        return self.surface("cave_ramp_up", art.cave_ramp_up)[0], "cave_ramp_up"

    def _draw_ramp(self, canvas, surf, key, x, y, lit: bool) -> None:
        canvas.blit(surf, (x, y))
        if lit:                                   # alvo do E: contorno igual ao das máquinas
            canvas.blit(self.outline_of(("ramp", key), surf), (x - 1, y - 1))

    def wreck_surface(self, kind: str, variant: str = "") -> pygame.Surface:
        """wreck_<kind>_<variante>.png, senão wreck_<kind>.png, senão o desenho de fallback (art.wreck)."""
        from game.wrecks import SPECS
        base = SPECS[kind].sprite
        name = f"{base}_{variant}" if variant and self.sprites.get(f"{base}_{variant}") is not None else base
        return self.surface(name, lambda: art.wreck(kind))[0]

    def crate_surface(self, empty: bool) -> pygame.Surface:
        name = "loot_crate_empty" if empty else "loot_crate"
        return self.surface(name, lambda: art.loot_crate(empty))[0]

    def draw_wreck(self, canvas, wreck, x: int, y: int) -> None:
        canvas.blit(self.wreck_surface(wreck.kind, wreck.variant), (x, y))
        if wreck.spec.led_rect and (self.machine_t * 1.2) % 2 < 1:   # LED da sonda piscando (apagado: #3b3f46)
            lx, ly, lw, lh = wreck.spec.led_rect
            canvas.fill((59, 63, 70), (x + lx, y + ly, lw, lh))
        if self.highlight == ("wreck_log", wreck) and wreck.spec.terminal_rect:   # alvo do E: contorno só no terminal
            rx, ry, rw, rh = wreck.spec.terminal_rect
            pygame.draw.rect(canvas, self.HIGHLIGHT_RGBA[:3], (x + rx - 1, y + ry - 1, rw + 2, rh + 2), 1)

    def draw_crate(self, canvas, crate, x: int, y: int) -> None:
        surf = self.crate_surface(crate.empty)
        canvas.blit(surf, (x, y))
        if self.highlight is crate:
            canvas.blit(self.outline_of(("crate", crate.empty), surf), (x - 1, y - 1))

    def small_rock_surface(self, resource: str, tx: int, ty: int) -> tuple[pygame.Surface, bool]:
        """Rocha pequena do minério (rock_small_<minério>_{0,1}.png, variação por hash do tile) e se é o
        jeito antigo (rock_small neutro + cristalzinho por cima), que vale quando o PNG não existe."""
        name = f"rock_small_{resource}_{rock_variant(tx, ty)}"
        sprite = self.sprites.get(name)
        if sprite is not None:
            return self.surface(name, art.rock_small)[0], False
        key = f"rock_small_old#{resource}"
        if key not in self._surfaces:
            base = self.surface("rock_small", art.rock_small)[0].copy()
            base.blit(self.surface(None, lambda: art.ore_fleck(resource), f"fleck#{resource}")[0], (0, 0))
            self._surfaces[key] = (base, True)
        return self._surfaces[key]

    def draw_small_rock(self, canvas, x: int, y: int, resource: str, tx: int = 0, ty: int = 0,
                        snow: bool = False) -> None:
        """Rocha pequena em (tx·32, ty·32): a do minério com veio (2 variações por tile). `snow` (tile da região
        gelada, só na superfície): a neve (rock_small_snowcap_{v}.png) por cima, no mesmo (x, y). Sem o PNG, nada."""
        surf, old = self.small_rock_surface(resource, tx, ty)
        canvas.blit(surf, (x, y))
        if snow:
            cap = self.sprites.get(f"rock_small_snowcap_{0 if old else rock_variant(tx, ty)}")   # rock_small comum = 0
            if cap is not None:
                canvas.blit(cap, (x, y))

    HIGHLIGHT_RGBA = (255, 236, 176, 150)   # contorno do alvo do E: creme claro, meio transparente

    def outline_of(self, key, surf: pygame.Surface) -> pygame.Surface:
        """Contorno de 1 px em volta da silhueta de `surf` (2 px maior em cada eixo), no cache por `key`."""
        cache_key = ("outline", key)
        if cache_key not in self._fx:
            mask = pygame.mask.from_surface(surf, 40)
            w, h = surf.get_size()
            grown = pygame.mask.Mask((w + 2, h + 2))
            for off in ((0, 1), (2, 1), (1, 0), (1, 2)):
                grown.draw(mask, off)
            grown.erase(mask, (1, 1))
            self._fx[cache_key] = grown.to_surface(setcolor=self.HIGHLIGHT_RGBA, unsetcolor=(0, 0, 0, 0))
        return self._fx[cache_key]

    def highlight_outline(self, machine) -> pygame.Surface:
        """Contorno do sprite da máquina (drill no quadro 0: a silhueta não muda girando)."""
        if machine.submerged:
            return self.outline_of(("submerged",) + self._submerged_key(machine), self.submerged_surface(machine))
        if machine.is_drill:
            return self.outline_of("drill", self.drill_frame(0))
        if machine.is_chest:
            opened = machine is self.open_chest
            return self.outline_of(("chest", machine.kind, opened), self.chest_surface(machine.kind, opened))
        if machine.is_bench:
            return self.outline_of("bench", self.machine_still(machine)[0])
        if machine.is_station:
            return self.outline_of("station", self.station_surface())
        sprite, flip = self.machine_still(machine)   # derretedor e o resto: a silhueta do próprio sprite
        if flip:
            sprite = pygame.transform.flip(sprite, True, False)
        return self.outline_of((machine.kind, flip), sprite)

    # ---- luz de scanner: construir e desmontar (v0.5 M1) -----------------------------------
    # Referência da Designer: tools/sprites/v05_m1_construtor.py · scan_frame (o mesmo algoritmo, em pygame).
    @staticmethod
    def build_scan(build_left: float) -> tuple[float, int] | None:
        """(p, passo) da construção com `build_left` s faltando. p = 1 no(s) passo(s) do flash (no fim do
        BUILD_TIME). None = pronta."""
        if build_left <= 0:
            return None
        total = max(1, round(C.BUILD_TIME * C.SCAN_FPS))
        scan_steps = max(1, total - C.SCAN_FLASH_STEPS)
        step = int((C.BUILD_TIME - build_left) * C.SCAN_FPS)
        if step >= scan_steps:
            return 1.0, -1                                    # -1 = flash
        return step / scan_steps, step

    @staticmethod
    def unbuild_scan(held: float) -> tuple[float, int]:
        """(p, passo) do desmonte com `held` s segurando: a faixa desce, p = 1 − passo/N."""
        n = max(1, round(C.DISMANTLE_HOLD * C.SCAN_FPS))
        step = min(n, int(held * C.SCAN_FPS))
        return 1 - step / n, step

    def machine_scan(self, m, state: GameState) -> tuple[float, int] | None:
        if m.build > 0:
            return self.build_scan(m.build)
        if m is state.dismantling:
            self._unbuilding = m
            return self.unbuild_scan(state.dismantle_t)
        return None

    def start_blink(self, tile: tuple[int, int], t: float) -> None:
        """A máquina desmontada saiu: o holograma dela pisca (apagado, aceso, apagado) e some."""
        m = self._unbuilding
        if m is not None and (m.tx, m.ty) == tuple(tile):
            self.blinks.append((self.scan_info(m), m.anchor, t))
        self._unbuilding = None

    def scan_info(self, machine) -> dict:
        """Tudo que o scan precisa do sprite parado da máquina, no cache por tipo e espelho: o sprite, a caixa da
        silhueta, o holograma (contorno em SCAN_GHOST), a silhueta pintada de cada cor da faixa, a máquina inteira
        no flash e as pontas da silhueta por linha (pro plano do emissor)."""
        sprite, flip = self.machine_still(machine)
        key = ("scan", machine.kind, flip, id(sprite))
        if key in self._fx:
            return self._fx[key]
        if flip:
            sprite = pygame.transform.flip(sprite, True, False)
        w, h = sprite.get_size()
        sil = pygame.mask.from_surface(sprite, 1)
        box = sil.get_bounding_rects()
        x0 = min((r.left for r in box), default=0)
        y0 = min((r.top for r in box), default=0)
        x1 = max((r.right for r in box), default=w) - 1
        y1 = max((r.bottom for r in box), default=h) - 1
        outline = pygame.mask.from_threshold(sprite, pygame.Color(C.SCAN_OUTLINE), (1, 1, 1, 255))
        ghost = outline.to_surface(setcolor=pygame.Color(C.SCAN_GHOST), unsetcolor=(0, 0, 0, 0))
        paint = {c: sil.to_surface(setcolor=pygame.Color(c), unsetcolor=(0, 0, 0, 0))
                 for c in (C.SCAN_CORE, C.SCAN_EDGE, C.SCAN_PULSE)}
        flash = sprite.copy()
        flash.fill(C.SCAN_FRESH_ADD, special_flags=pygame.BLEND_RGB_ADD)
        spans = {}
        for y in range(h):
            xs = [x for x in range(w) if sil.get_at((x, y))]
            if xs:
                spans[y] = (xs[0], xs[-1])
        info = {"sprite": sprite, "box": (x0, y0, x1, y1), "ghost": ghost, "paint": paint, "flash": flash,
                "spans": spans, "outline": outline}
        self._fx[key] = info
        return info

    @staticmethod
    def _scan_hash(*k: int) -> int:
        h = 2166136261
        for v in k:
            h = ((h ^ (v & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
        return h

    def draw_scan(self, canvas, info: dict, p: float, step: int, ax: float, ay: float) -> None:
        """Um quadro da luz de scanner na âncora (ax, ay) da tela. Abaixo da faixa, a máquina (as 2 primeiras linhas
        mais claras); acima, o holograma; a faixa só sobre a silhueta, pulsando 3 ↔ 5 px, com o plano do emissor
        pra fora e as faíscas acima. `step` -1 = o flash do fim da construção."""
        sprite = info["sprite"]
        w, h = sprite.get_size()
        X, Y = round(ax) - w // 2, round(ay) - h
        if step < 0:
            canvas.blit(info["flash"], (X, Y))
            return
        x0, y0, x1, y1 = info["box"]
        ys = int(round(y1 + 1 - p * (y1 - y0 + 2)))
        if ys + 1 < h:                                          # a parte construída
            top = max(0, ys + 1)
            canvas.blit(sprite, (X, Y + top), (0, top, w, h - top))
            fresh_h = min(C.SCAN_FRESH_ROWS, h - top)
            if fresh_h > 0:
                fresh = sprite.subsurface((0, top, w, fresh_h)).copy()
                fresh.fill(C.SCAN_FRESH_ADD, special_flags=pygame.BLEND_RGB_ADD)
                canvas.blit(fresh, (X, Y + top))
        if ys > 0:                                              # o holograma acima da faixa
            canvas.blit(info["ghost"], (X, Y), (0, 0, w, min(h, ys)))
        half = 2 if step % 2 else 1
        for k in range(-half, half + 1):                        # a faixa, só sobre a silhueta
            y = ys + k
            if 0 <= y < h:
                color = C.SCAN_CORE if k == 0 else C.SCAN_EDGE if abs(k) == 1 else C.SCAN_PULSE
                canvas.blit(info["paint"][color], (X, Y + y), (0, y, w, 1))
        span = info["spans"].get(ys)
        if span is not None:                                    # o plano do emissor pra fora da silhueta
            a, b = span
            out = C.SCAN_PLANE_OUT
            canvas.fill(C.SCAN_PLANE, (X + a - out, Y + ys, out, 1))
            canvas.fill(C.SCAN_PLANE, (X + b + 1, Y + ys, out, 1))
            canvas.fill(C.SCAN_NODE, (X + a - out - 1, Y + ys, 1, 1))
            canvas.fill(C.SCAN_NODE, (X + b + out + 1, Y + ys, 1, 1))
        if 0 < p < 1:                                           # faíscas: só em pixel vazio da máquina
            lo, hi = C.SCAN_SPARK_UP
            outline = info["outline"]                           # acima da faixa só o holograma (o contorno) ocupa
            for i in range(C.SCAN_SPARKS):
                hh = self._scan_hash(step, i, 77)
                x = x0 + hh % (x1 - x0 + 1)
                y = ys - lo - (hh >> 8) % (hi - lo + 1)
                if 0 <= x < w and -6 <= y < h and (y < 0 or not outline.get_at((x, y))):
                    canvas.fill(C.SCAN_CORE if (step + i) % 2 == 0 else C.SCAN_EDGE, (X + x, Y + y, 1, 1))

    # ---- máquina submersa (v0.4 M3.4) ---------------------------------------------
    SUBMERGED_TINT = 3      # px: quantas linhas acima da linha d'água ganham o tom da água

    def machine_still(self, machine) -> tuple[pygame.Surface, bool]:
        """Sprite parado da máquina (sem animação, drill no quadro 0) e se vai espelhado (rotação ímpar)."""
        kind = machine.kind
        if machine.is_drill:
            return self.drill_frame(0), False
        if machine.is_chest:
            return self.chest_surface(machine.kind), False
        if machine.is_station:
            return self.station_surface(), False
        if machine.is_lamp:
            return self.lamp_surface(kind), False
        return self.surface(C.MACHINES[kind].sprite, lambda: art.machine(kind))[0], machine.rotation % 2 == 1

    def _submerged_key(self, machine) -> tuple:
        return machine.kind, machine.rotation % 2, art_key(self.stage_map.stage_at(machine.tx, machine.ty))

    def submerged_surface(self, machine) -> pygame.Surface:
        """A máquina debaixo d'água: só a metade de cima da silhueta, as últimas linhas no tom da água e a linha
        d'água (a espuma da paleta do estágio) por cima do corte, um pouco mais larga que a máquina. Mesmo tamanho
        do sprite (âncora igual): embaixo do corte aparece o tile de água do chão. No cache por tipo e estágio."""
        key = ("submerged",) + self._submerged_key(machine)
        if key not in self._fx:
            sprite, flip = self.machine_still(machine)
            if flip:
                sprite = pygame.transform.flip(sprite, True, False)
            w, h = sprite.get_size()
            box = sprite.get_bounding_rect(40)
            cut = box.top + box.height // 2                   # da metade da silhueta pra cima
            out = pygame.Surface((w, h), pygame.SRCALPHA)
            out.blit(sprite, (0, 0), (0, 0, w, cut))
            pal = C.PALETTES[key[3]]
            tint = self.SUBMERGED_TINT
            band = pygame.mask.from_surface(out.subsurface((0, cut - tint, w, tint)), 40)
            out.blit(band.to_surface(setcolor=(*pygame.Color(pal["water_d"])[:3], 120), unsetcolor=(0, 0, 0, 0)),
                     (0, cut - tint))
            row = pygame.mask.from_surface(out.subsurface((0, cut - 1, w, 1)), 40).get_bounding_rects()
            x0 = min((r.left for r in row), default=box.left)
            x1 = max((r.right for r in row), default=box.right)
            x0, x1 = max(0, x0 - 2), min(w, x1 + 2)          # a espuma passa um pouco da silhueta
            out.fill(pal["foam"], (x0, cut - 1, x1 - x0, 1))
            out.fill(pal["water_d"], (x0 + 1, cut, x1 - x0 - 2, 1))
            self._fx[key] = out
        return self._fx[key]

    # ---- animação das máquinas e do ambiente (tiras anim/anim_<sprite>.png, 4 quadros lado a lado) -------------
    def anim_frames(self, name: str, still: pygame.Surface) -> list[pygame.Surface] | None:
        """Os quadros da tira `anim/anim_<name>.png`, recortados uma vez (cache). O quadro tem o tamanho do
        sprite parado `still` e o nº de quadros é a largura da tira ÷ a largura do parado (4 nas máquinas, 8 na
        bancada). None se a tira não existe ou não bate com o parado (aí vale o parado)."""
        key = ("anim", name, still.get_size())
        if key not in self._fx:
            strip = self.sprites.get(f"anim/anim_{name}")
            w, h = still.get_size()
            n = strip.get_width() // w if strip is not None else 0
            ok = n >= 1 and strip.get_size() == (w * n, h)
            self._fx[key] = [strip.subsurface((i * w, 0, w, h)) for i in range(n)] if ok else None
        return self._fx[key]

    def anim_surface(self, name: str, still: pygame.Surface, index: int | None) -> pygame.Surface:
        """Quadro `index` da tira, ou o parado (`index` None ou sem tira)."""
        frames = None if index is None else self.anim_frames(name, still)
        return still if frames is None else frames[index % len(frames)]

    def machine_anim_index(self, m, powered: bool, clock: float) -> int | None:
        """Quadro da animação da máquina `m`. Submersa ou sem energia nenhuma: quadro 0. O painel solar anima
        sempre que está em pé (gera, não gasta; sem noite no jogo). A estação só com drone dentro. O resto anda no
        `machine_t`, que já corre no ritmo do power.factor (déficit = mais devagar). A Fundição parada devolve None
        (o sprite apagado: o quadro 0 da tira dela já é acesa)."""
        if m.is_smelter:                # v0.6 Fundo M3: só anima fundindo
            working = powered and not m.submerged and m.smelter_blocker is None
            return anim_frame_index(self.machine_t, tile_phase(m.tx, m.ty)) if working else None
        if m.submerged:
            return 0
        if m.is_bench:                  # v0.5 M1 B2: só anima fabricando, 1 ciclo (0 -> 7 a BENCH_FPS), sem fase por tile
            return bench_frame_index(m.work)
        phase = tile_phase(m.tx, m.ty)
        if m.kind == "solar":
            return anim_frame_index(clock, phase)
        working = powered
        if m.is_station:
            working = powered and bool(m.station is not None and m.station.drones)
        return anim_frame_index(self.machine_t, phase, working)

    def broken_surface(self, kind: str) -> pygame.Surface:
        """Máquina quebrada de ruína (v0.7 M1): o quadro 0 do sprite que já existe, escurecido por C.RUIN_BROKEN_TINT."""
        cache = self.__dict__.setdefault("_broken_surfaces", {})
        surf = cache.get(kind)
        if surf is None:
            if kind in C.LAMP_RADIUS:
                base = self.lamp_surface(kind)
            else:
                name = C.MACHINES[kind].sprite
                base, fallback = self.surface(name, lambda: art.machine(kind))
                if not fallback:
                    base = self.anim_surface(name, base, 0)
            surf = base.copy()
            surf.fill(C.RUIN_BROKEN_TINT, special_flags=pygame.BLEND_RGB_MULT)
            cache[kind] = surf
        return surf

    def _blit_anchored(self, canvas, surf, ax, ay, flip=False):
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        canvas.blit(surf, (round(ax) - surf.get_width() // 2, round(ay) - surf.get_height()))

    def _draw_pod(self, canvas, ax, ay, t) -> None:
        surf, fallback = self.surface("pod", art.pod)
        self._blit_anchored(canvas, self.anim_surface("pod", surf, anim_frame_index(t, 0)), ax, ay)
        if fallback and (t * 9) % 10 < 5:   # luz da antena piscando
            canvas.fill("#ff5a4a", (round(ax) - 32 + 49, round(ay) - 72 + 1, 3, 3))

    DRILL_FPS = 8

    def drill_frame(self, frame: int) -> pygame.Surface:
        """Quadro `frame` (0–3) do machine_drill: recorte (64·f, 0, 64, 80) da folha."""
        sheet, _ = self.surface("machine_drill", art.drill_machine)
        w, h = C.DRILL_SPRITE_SIZE
        return sheet.subsurface((frame * w, 0, w, h))

    def draw_drill(self, canvas, drill, ax, ay, t, alpha=None) -> None:
        """Drill: gira enquanto trabalha (parada no quadro 0 quando cheia) + indicador de enchimento."""
        w, h = C.DRILL_SPRITE_SIZE
        working = drill is not None and not drill.full and alpha is None
        frame = self.drill_frame(int(t * self.DRILL_FPS) % 4 if working else 0)
        if alpha is not None:
            frame = frame.copy()
            frame.set_alpha(alpha)
        x, y = round(ax) - w // 2, round(ay) - h
        canvas.blit(frame, (x, y))
        if drill is not None and drill.stored:
            # retângulo do indicador dentro do quadro (spec da Designer): enche de baixo pra cima
            fx, fy, fw, fh = art.DRILL_FILL_RECT
            level = round(fh * drill.stored / C.DRILL_CAPACITY)
            canvas.fill(C.ORE_COLORS[drill.resource][0], (x + fx, y + fy + fh - level, fw, level))

    def chest_surface(self, kind: str = "chest", opened: bool = False) -> pygame.Surface:
        """Baú de qualquer tamanho, fechado ou aberto (v0.6 M1): o Simples usa a arte da caixa de saque, o Normal a
        do baú e o Grande a do contêiner. Sem o PNG, o desenho de fallback de cada um."""
        if kind == "chest_small":
            return self.crate_surface(opened)
        if kind == "chest_large":
            return self.container_surface(opened)
        name = ("chest_open" if opened else "chest") if C.CHEST_SPRITE_APPROVED else None
        return self.surface(name, lambda: art.chest(opened), f"chest#{opened}")[0]

    # ---- estação de drones (game/drones.py) -------------------------------------
    def station_surface(self) -> pygame.Surface:
        """drone_station.png (64×72) se aprovado e existir; senão o desenho de fallback."""
        name = "drone_station" if C.DRONE_SPRITES_APPROVED else None
        return self.surface(name, art.drone_station, "drone_station#fallback" if name is None else None)[0]

    def drone_frame(self, t: float, offset: int = 0) -> pygame.Surface:
        """Quadro do drone (16×16) com as hélices girando a ~15 fps. `offset` desencontra os drones."""
        name = "drone" if C.DRONE_SPRITES_APPROVED else None
        sheet = self.surface(name, art.drone_sheet, "drone#fallback" if name is None else None)[0]
        size = C.DRONE_SPRITE
        frame = (int(t * C.DRONE_FPS) + offset) % (sheet.get_width() // size)
        return sheet.subsurface((frame * size, 0, size, size))

    def _draw_nugget(self, canvas, drone, x: int, y: int) -> None:
        """Pepita da cor do minério embaixo do drone carregado. (x, y) = centro do drone na tela."""
        color, shade = C.ORE_COLORS[drone.resource]
        canvas.fill(shade, (x - 2, y + 5, 5, 4))
        canvas.fill(color, (x - 2, y + 5, 4, 3))

    def draw_station(self, canvas, machine, cam, t: float) -> None:
        """Estação + os drones pousados nos pads (os que estão voando são desenhados depois, por cima)."""
        ax, ay = machine.anchor
        still = self.station_surface()
        frame = self.machine_anim_index(machine, self.powered, t)
        self._blit_anchored(canvas, self.anim_surface("drone_station", still, frame), ax - cam[0], ay - cam[1])
        if machine.station is None:
            return
        for i, drone in enumerate(machine.station.drones):
            if drone.in_air:
                continue
            x, y = round(drone.x - cam[0]), round(drone.y - cam[1])
            canvas.blit(self.drone_frame(0), (x - 8, y - 8))      # pousado: hélices paradas
            if drone.cargo:
                self._draw_nugget(canvas, drone, x, y)

    def drone_shadow_at(self, lift: float) -> pygame.Surface:
        """Sombra do drone pra altura `lift` (0 pousado, 1 voando): de 14×6 (preto 43%) até 12×5 (36%).
        Em 8 degraus, guardados no cache."""
        step = round(max(0.0, min(1.0, lift)) * 8)
        key = ("drone_shadow", step)
        if key not in self._fx:
            k = step / 8
            w, h = round(14 - 2 * k), round(6 - k)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (0, 0, 0, round(110 - 18 * k)), (0, 0, w, h))
            self._fx[key] = surf
        return self._fx[key]

    def draw_flying_drones(self, canvas, state: GameState, cam, t: float) -> None:
        """Drones no ar: sombra no chão (elipse 12×5, preto 36%) e o drone balançando de leve em cima.
        Cada um vai na faixa dele (drones.visual_offset): de lado na rota, um pouco mais alto ou mais
        baixo, e num ponto próprio em volta do alvo. Só o desenho: a posição lógica é a mesma."""
        dt = 0.0 if self._drone_t is None else max(0.0, min(0.1, t - self._drone_t))
        self._drone_t = t
        offsets = {}
        for machine in state.stations:
            for drone in machine.station.drones:
                if not drone.in_air:
                    continue
                key = id(drone)
                goal = drones.visual_offset(machine, drone)
                ox, oy = offsets[key] = drones.ease(self._drone_offsets.get(key, goal), goal, dt)
                # decolando/pousando (lift < 1): a sombra vem de debaixo dele, maior e mais escura,
                # e vai se afastando e encolhendo conforme sobe (o inverso no pouso). A faixa entra junto
                # com a subida, então ele sai e chega no pad certinho.
                lift = drones.lift(machine, drone)
                x = round(drone.x + ox * lift - cam[0])
                y = round(drone.y + oy * lift - cam[1])
                if not (-32 < x < self.view_w + 32 and -32 < y < self.view_h + 48):
                    continue
                shadow = self.drone_shadow_at(lift)
                drop = round(LANDED_SHADOW_DROP + (C.DRONE_SHADOW_DROP - LANDED_SHADOW_DROP) * lift)
                canvas.blit(shadow, (x - shadow.get_width() // 2, y + drop - shadow.get_height() // 2))
                bob = round(math.sin(t * 5 + drone.pad * 1.7) * 1.5 * lift - drones.altitude(drone) * lift)
                canvas.blit(self.drone_frame(t, drone.pad), (x - 8, y - 8 + bob))
                if drone.cargo:
                    self._draw_nugget(canvas, drone, x, y + bob)
        self._drone_offsets = offsets

    def item_icon(self, item: str) -> pygame.Surface:
        """Ícone 32×32 (resolução cheia) de um item do inventário: recurso, drill, baú ou máquina."""
        if item not in self._item_icons:
            if item in C.RESOURCES:
                small = self.surface(f"icon_{item}", lambda: art.icon(item))[0]
            elif item == "drill":
                small = self.surface("icon_drill", art.drill_icon)[0]
            elif item == "chest":
                name = "icon_chest" if C.CHEST_SPRITE_APPROVED else None
                small = self.surface(name, art.chest_icon, "icon_chest#fallback" if name is None else None)[0]
            elif item in ("chest_small", "chest_large"):
                # icon_chest_small / icon_chest_large vêm da Designer; até lá, o sprite fechado reduzido pra 16×16
                small = self.surface(C.CHEST_ICONS[item], lambda: art.reduced_icon(self.chest_surface(item)),
                                     f"{C.CHEST_ICONS[item]}#fallback")[0]
            elif item == "drone_station":
                name = "icon_drone_station" if C.DRONE_SPRITES_APPROVED else None
                small = self.surface(name, art.drone_station_icon,
                                     "icon_drone_station#fallback" if name is None else None)[0]
            elif item == "drone":
                small = self.drone_icon()
            elif item == "lamp":
                small = self.surface("icon_lamp", art.lamp_icon)[0]
            elif item == "lamp_t2":
                small = self.surface("icon_lamp_t2", art.lamp_strong_icon)[0]
            elif item == "chip_slot_empty":     # v0.6 M2: a silhueta do slot de chip vazio (UI), não é item
                small = self.surface("chip_slot_empty", art.chip_slot_empty)[0]
            elif item == "o2_tank":
                small = self.surface("icon_o2_tank", art.o2_tank_icon)[0]
            elif item == "scanner":
                small = self.surface("icon_scanner", art.scanner_icon)[0]
            elif item == "workbench":           # v0.5 M1 B2: icon_workbench.png (aprovado)
                small = self.surface("icon_workbench", lambda: art.machine("workbench"))[0]
            elif item == "backpack":
                small = self.surface("icon_backpack", art.backpack_icon)[0]
            elif item == "water_capsule":        # v0.5 M2: icon_water_capsule.png (aprovado)
                small = self.surface("icon_water_capsule", art.water_capsule_icon)[0]
            elif item in C.HAND_DRILLS or item in C.PART_ITEMS:   # v0.5 M4: icon_<item>.png (v0.6 Fundo M4: as duas brocas)
                small = self._m4_icon(item)
            elif item in C.PLAYER_PROPS:         # v0.7 M2: icon_<prop>.png (16×16)
                small = self.surface(f"icon_{item}", lambda: self._placeholder(16, item))[0]
            elif item in C.BASE_KINDS or item == C.DISPENSER:   # v0.5 M2: icon_base_*.png e icon_o2_dispenser.png
                name = C.BASE_ICON.get(item, "icon_o2_dispenser")
                small = self.surface(name, lambda: self._placeholder(16, item))[0]
            elif item == "tab_base":             # v0.5 M4: ícone da aba Base do construtor (cápsula A, aprovado); sem ele, o baú
                small = self.surface("icon_tab_base", art.chest_icon)[0]
            elif item == "constructor":          # v0.5 M1: com o icon_constructor.png no assets, ele (sem mudar código)
                small = self.surface("icon_constructor", art.constructor_icon)[0]
            elif item in C.DIAGRAM_ITEMS:       # v0.5 M1: icon_diagram.png (aprovado); sem ele, o chip de projeto de antes
                small = self.surface("icon_diagram", art.blueprint_icon)[0]
            elif item == "solar" and self.sprites.get("icon_solar"):
                small = self.sprites.get("icon_solar")
            else:   # máquina sem ícone próprio: o sprite dela encolhido pra caber (sem suavizar)
                big = self.machine_preview(item)
                w, h = big.get_size()
                k = 30 / max(w, h)
                small = pygame.transform.scale(big, (max(1, round(w * k)), max(1, round(h * k))))
                icon = pygame.Surface((32, 32), pygame.SRCALPHA)
                icon.blit(small, (16 - small.get_width() // 2, 31 - small.get_height()))
                self._item_icons[item] = icon
                return icon
            self._item_icons[item] = pygame.transform.scale_by(small, 2)   # 16×16 → 32×32, pixel a pixel
        return self._item_icons[item]

    def _m4_icon(self, item: str) -> pygame.Surface:
        """Ícone 16×16 da broca de mão ou de uma peça de loot: o PNG de assets/sprites ou, sem ele, o fallback (a broca
        usa o 1º quadro da drill_side reduzido; as peças, um quadradinho colorido)."""
        if item in C.HAND_DRILLS:
            sheet = self.surface("drill_side", lambda: art.drill("side"))[0]
            fallback = lambda: art.hand_drill_icon(sheet)   # noqa: E731
            if item == C.HAND_DRILL_T2:                     # v0.6 Fundo M4: sem o PNG dela, o da nv.1 (ou o fallback)
                return self.surface("icon_hand_drill_t2",
                                    lambda: self.surface("icon_hand_drill", fallback)[0].copy())[0]
            return self.surface("icon_hand_drill", fallback)[0]
        return self.surface(f"icon_{item}", lambda: self._placeholder(16, item))[0]

    def drone_icon(self) -> pygame.Surface:
        """Ícone 16×16 do item drone: assets/sprites/icon_drone.png assim que for aprovado (é só ele
        existir na pasta oficial); até lá, o 1º quadro do drone.png (ou do drone de fallback)."""
        return self.surface("icon_drone", lambda: self.drone_frame(0).copy())[0]

    def machine_preview(self, kind: str) -> pygame.Surface:
        """Imagem da máquina pro fabricador (resolução cheia, sem redimensionar com suavização)."""
        if kind == "drone":
            return pygame.transform.scale_by(self.drone_icon(), 3)   # 16×16 → 48×48, pixel a pixel
        if kind in C.CHEST_KINDS:
            return self.chest_surface(kind)
        if kind in C.DIAGRAM_ITEMS:      # o item do diagrama (receita no fabricador): o ícone ×3, pixel a pixel
            return pygame.transform.scale_by(self.surface("icon_diagram", art.blueprint_icon)[0], 3)
        if kind == "drone_station":
            return self.station_surface()
        if kind in C.LAMP_RADIUS:
            return pygame.transform.scale_by(self.lamp_surface(kind), 2)   # 16×32 → 32×64, pixel a pixel
        if kind in C.EQUIP_SLOTS:
            painter = {"o2_tank": art.o2_tank_icon, "scanner": art.scanner_icon, "backpack": art.backpack_icon}[kind]
            return pygame.transform.scale_by(self.surface(f"icon_{kind}", painter)[0], 3)   # 16×16 → 48×48
        if kind == "constructor":
            return pygame.transform.scale_by(self.surface("icon_constructor", art.constructor_icon)[0], 3)
        if kind == "water_capsule":
            return pygame.transform.scale_by(self.surface("icon_water_capsule", art.water_capsule_icon)[0], 3)
        if kind in C.HAND_DRILLS or kind in C.PART_ITEMS:
            return pygame.transform.scale_by(self._m4_icon(kind), 3)
        if kind in C.PLAYER_PROPS:       # v0.7 M2: o ícone do prop ×3
            return pygame.transform.scale_by(self.surface(f"icon_{kind}", lambda: self._placeholder(16, kind))[0], 3)
        if kind in C.BASE_KINDS:
            return pygame.transform.scale_by(self.surface(C.BASE_ICON[kind], lambda: self._placeholder(16, kind))[0], 3)
        if kind == "drill":
            icon = self.sprites.get("icon_drill")
            if icon:
                return pygame.transform.scale_by(icon, 3)        # 16×16 → 48×48, pixel a pixel
            frame = self.drill_frame(0)
            return frame.subsurface((0, 16, 64, 64))              # sem a cabeça, pra caber na caixinha
        return self.surface(C.MACHINES[kind].sprite, lambda: art.machine(kind))[0]

    def lamp_surface(self, kind: str = "lamp") -> pygame.Surface:
        if kind == "lamp_t2":                    # luminária forte (Marco 3): sem sprite ainda, fallback próprio
            return self.surface("lamp_t2", art.lamp_strong)[0]
        return self.surface("lamp", art.lamp)[0]

    def draw_machine(self, canvas, kind, ax, ay, t, rotation=0, alpha=None, frame: int | None = None) -> None:
        """`frame` = quadro da tira de animação; None = o parado (fantasma de colocar, ícones)."""
        if kind in C.LAMP_RADIUS:                # luminária: sem animação nem rotação (a luz vem do lighting)
            surf = self.lamp_surface(kind)
            if alpha is not None:
                surf = surf.copy()
                surf.set_alpha(alpha)
            self._blit_anchored(canvas, surf, ax, ay)
            return
        if kind in C.CHEST_KINDS:                # baú: sem animação nem rotação (é o fantasma de colocar)
            surf = self.chest_surface(kind).copy()
            if alpha is not None:
                surf.set_alpha(alpha)
            self._blit_anchored(canvas, surf, ax, ay)
            return
        if kind == "drone_station":              # estação: idem (fantasma de colocar)
            surf = self.station_surface().copy()
            if alpha is not None:
                surf.set_alpha(alpha)
            self._blit_anchored(canvas, surf, ax, ay)
            return
        name = C.MACHINES[kind].sprite
        surf, fallback = self.surface(name, lambda: art.machine(kind))
        if not fallback and alpha is None:
            surf = self.anim_surface(name, surf, frame)
        if alpha is not None:
            surf = surf.copy()
            surf.set_alpha(alpha)
        self._blit_anchored(canvas, surf, ax, ay, flip=rotation % 2 == 1)
        if fallback and alpha is None and rotation % 2 == 0:
            art.machine_anim(canvas, kind, round(ax), round(ay), t)

    PLAYER_WALK_FPS = 9     # caminhada: avança pelo walk_time (só corre enquanto anda)
    PLAYER_IDLE_FPS = 4     # parado respirando: bem lento
    PLAYER_MINE_FPS = 14    # minerando: = DRILL_FPS, mesmo índice de quadro da broca (o tranco de 1 px casa)

    @staticmethod
    def player_anim(state: GameState) -> str:
        """Qual animação o player toca agora: 'mine' > 'walk' > 'idle' ('still' = desmaiado, sprite parado)."""
        if state.fainted:
            return "still"
        if state.mining:
            return "mine"
        if state.player.moving:
            return "walk"
        return "idle"

    @staticmethod
    def anim_frame(time: float, fps: float, frames: int = 4) -> int:
        """Índice do quadro de um loop de `frames` quadros tocando a `fps`."""
        return int(time * fps) % frames

    def _player_loop(self, name: str, view: str) -> pygame.Surface:
        """Tira 128×32 do contrato; sem o PNG, repete o sprite parado (do contrato ou do art.py) 4 vezes.
        Assim o jogo fica igual ao de antes enquanto a arte nova não chega."""
        def still_sheet() -> pygame.Surface:
            still = self.surface(f"player_{view}", lambda: art.player(view))[0]
            sheet = pygame.Surface((128, 32), pygame.SRCALPHA)
            for i in range(4):
                sheet.blit(still, (i * 32, 0))
            return sheet
        return self.surface(name, still_sheet)[0]

    def _player_frame(self, state: GameState, t: float = 0.0) -> tuple[pygame.Surface, bool]:
        """Quadro atual do player e se precisa espelhar (olhando pra esquerda).
        Prioridade: minerando > andando > parado. `t` = relógio do render (idle e mine)."""
        p = state.player
        # "left" usa o sprite de lado espelhado; "right" usa ele direto
        view = "side" if p.direction in ("left", "right") else p.direction
        flip = p.direction == "left"
        anim = self.player_anim(state)
        if anim == "walk":
            sheet, _ = self.surface(f"player_walk_{view}", lambda: art.player_walk(view))
            frame = self.anim_frame(p.walk_time, self.PLAYER_WALK_FPS)
        elif anim == "mine":
            sheet = self._player_loop(f"player_mine_{view}", view)
            frame = self.anim_frame(t, self.PLAYER_MINE_FPS)
        elif anim == "idle":
            sheet = self._player_loop(f"player_idle_{view}", view)
            frame = self.anim_frame(t, self.PLAYER_IDLE_FPS)
        else:
            return self.surface(f"player_{view}", lambda: art.player(view))[0], flip
        return sheet.subsurface((frame * 32, 0, 32, 32)), flip

    def _draw_player(self, canvas, state: GameState, x, y, t) -> None:
        canvas.blit(self.player_shadow, (round(x) - 8, round(y) - 5))   # elipse 16×5 nos pés (linha 30)
        surf, flip = self._player_frame(state, t)
        drill = self.drill_sprite(state, t) if state.mining else None
        if drill and drill[2]:          # olhando pra cima: a broca fica atrás do corpo
            canvas.blit(drill[0], (round(x) + drill[1][0], round(y) + drill[1][1]))
        self._blit_anchored(canvas, surf, x, y, flip=flip)
        # a broca da frente (lado/baixo) é desenhada depois das paredes: ver draw_walls_and_objects

    # Onde a broca encaixa, a partir do canto superior esquerdo do quadro 32×32 do player
    # (px = x - 16, py = y - 32). "behind" = desenhada antes do player. Valores do report da Designer.
    DRILL_GRIP = {
        "right": ((12, 13), False),
        "left": ((-4, 13), False),
        "down": ((13, 16), False),
        "up": ((20, 4), True),
    }
    DRILL_FPS = 14

    def drill_sprite(self, state: GameState, t: float):
        """(quadro, deslocamento a partir dos pés, fica atrás?) da broca girando. Loop próprio a 14 fps."""
        direction = state.player.direction
        view = "side" if direction in ("left", "right") else direction
        sheet, _ = self.surface(f"drill_{view}", lambda: art.drill(view))
        fw = sheet.get_width() // 4
        frame = sheet.subsurface((int(t * self.DRILL_FPS) % 4 * fw, 0, fw, sheet.get_height()))
        if direction == "left":
            frame = pygame.transform.flip(frame, True, False)
        (gx, gy), behind = self.DRILL_GRIP[direction]
        return frame, (gx - 16, gy - 32), behind

    def drill_tip(self, state: GameState) -> tuple[float, float]:
        """Ponta da broca em pixels do mundo (de onde saem as faíscas)."""
        p = state.player
        return {"right": (p.x + 15, p.y - 14), "left": (p.x - 16, p.y - 14),     # broca A (v6.0, furadeira de bolso)
                "down": (p.x + 1, p.y - 3), "up": (p.x + 8, p.y - 24)}[p.direction]

    # ---- mineração e colocação ------------------------------------------------
    def draw_mining(self, canvas, state: GameState, mining: Mining, cam) -> None:
        tx, ty = mining.tile
        kind = state.world.get(tx, ty)
        if kind not in C.MINE_TIME:
            return
        prog = mining.progress(kind)
        px = tx * T - cam[0]
        if kind in C.FLAT_SOLIDS:                                 # rocha pequena: sem topo elevado
            py, h = ty * T - cam[1], T
        else:
            py = ty * T - WALL_LIFT - cam[1]                      # topo elevado da parede
            h = WALL_LIFT + (T if not state.world.is_wall(tx, ty + 1) else FACE_Y)   # topo + face (se tiver)
        # rachaduras aparecendo no topo conforme o progresso
        cracks = [(4, 3), (5, 4), (6, 5), (7, 6), (8, 7), (9, 8), (9, 9), (8, 10), (8, 11), (7, 12), (7, 13), (6, 14),
                  (10, 8), (11, 8), (12, 7), (13, 7), (14, 7), (15, 8), (16, 9), (17, 10), (18, 10), (19, 11),
                  (20, 12), (21, 12), (22, 13), (16, 6), (17, 5), (18, 4)]
        for cx, cy in cracks[: int(len(cracks) * prog)]:
            canvas.fill((15, 8, 6), (px + cx, py + cy + 6, 1, 1))
        # cantoneiras brancas em volta da parede inteira
        for x, y, w, hh in [(-2, -2, 8, 2), (-2, -2, 2, 8), (T - 6, -2, 8, 2), (T, -2, 2, 8),
                            (-2, h, 8, 2), (-2, h - 6, 2, 8), (T - 6, h, 8, 2), (T, h - 6, 2, 8)]:
            canvas.fill((255, 255, 255), (px + x, py + y, w, hh))
        # barrinha de progresso
        canvas.fill((0, 0, 0), (px - 4, py - 16, 40, 8))
        canvas.fill(C.C_TI, (px - 2, py - 14, round(36 * prog), 4))
        canvas.fill("#fff3c4", (px - 2, py - 14, round(36 * prog), 1))

    def draw_ghost(self, canvas, cam, kind, tile, rotation, valid, t) -> None:
        if kind in C.PLAYER_PROPS:
            self.draw_prop_ghost(canvas, cam, kind, tile, valid, t)
            return
        if kind in C.BASE_KINDS:
            self.draw_base_ghost(canvas, cam, kind, tile, rotation, valid, t)
            return
        px, py = tile[0] * T - cam[0], tile[1] * T - cam[1]
        size = C.MACHINES[kind].size * T                  # drill ocupa 2×2
        color = (127, 214, 122) if valid else (255, 106, 85)
        tint = pygame.Surface((size, size), pygame.SRCALPHA)
        tint.fill((*color, 51))
        canvas.blit(tint, (px, py))
        # contorno tracejado andando
        step = int(t * 8) % 8
        for i in range(0, size - 2, 8):
            k = (i + step) % (size - 2)
            for x, y, w, h in [(px + 1 + k, py + 1, 4, 2), (px + 1 + k, py + size - 3, 4, 2),
                               (px + 1, py + 1 + k, 2, 4), (px + size - 3, py + 1 + k, 2, 4)]:
                canvas.fill(color, (x, y, w, h))
        if kind == "drill":
            self.draw_drill(canvas, None, px + size // 2, py + size, t, alpha=128)
        else:   # âncora no centro da base (vale pra 1×1 e pra estação 2×2)
            self.draw_machine(canvas, kind, px + size // 2, py + size, t, rotation, alpha=128)

    # ---- indicadores no mundo (por cima da luz) ---------------------------------
    # Desenhados no mundo (e não na UI): crescem junto com a máquina no zoom. No menor zoom (0,75×)
    # a barra ainda tem 18×4 px na tela, legível; e no 2× não vira um tijolão porque é fininha.
    DRILL_BAR_W, DRILL_BAR_H = 24, 5          # com a borda escura de 1 px
    DRILL_BAR_FULL = "#7fd67a"                 # cheia: verde (hora de coletar)
    NO_POWER = "#ff4a3a"
    BOLT = ("  ###", " ### ", " ##  ", "#####", "  ## ", " ##  ", " #   ", "#    ")   # 5×8, igual ao do HUD

    def draw_machine_status(self, canvas, state: GameState, cam, t: float) -> None:
        """Barrinha de enchimento em cima de cada drill e raio vermelho piscando em quem está sem energia."""
        factor = state.power.factor
        blink = (t * 2.5) % 1 < 0.6
        block = state.dismantling
        if isinstance(block, BaseBlock):                      # v0.5 M2: desmontando um bloco da base
            xs = [tx for tx, _ in block.tiles]
            bw, bh = C.DISMANTLE_BAR
            x = round((sum(xs) / len(xs) + 0.5) * T - cam[0])
            y = round(block.ty * T - cam[1]) - (0 if block.is_floor else C.BASE_WALL_LIFT) - bh - 2
            self.draw_drill_bar(canvas, x, y, state.dismantle_progress, C.C_O2, False, w=bw, h=bh)
        bw, bh = C.DISMANTLE_BAR
        for prop, fill, color in ((block, state.dismantle_progress, C.C_O2), (state.scanning, state.scan_progress, C.C_TI)):
            if isinstance(prop, Prop):                        # v0.7 M2: desmontando um prop / escaneando um de ruína
                top = prop.ty * T - cam[1] + (C.BASE_FACE_Y if prop.place == "face" else -C.PROP_LIFT if prop.place != "decal" else 0)
                self.draw_drill_bar(canvas, round((prop.tx + prop.type.size[0] / 2) * T - cam[0]), round(top) - bh - 2, fill, color, False, w=bw, h=bh)
        if isinstance(block, Crate):                          # v0.6 M1: desmontando a caixa de saque
            bw, bh = C.DISMANTLE_BAR
            ax, ay = block.anchor
            self.draw_drill_bar(canvas, round(ax - cam[0]), round(ay - cam[1]) - C.LOOT_CRATE_SIZE[1] - bh - 2,
                                state.dismantle_progress, C.C_O2, False, w=bw, h=bh)
        for m in state.machines:
            ax, ay = m.anchor
            x, y = round(ax - cam[0]), round(ay - cam[1])
            if not (-64 < x < self.view_w + 64 and -100 < y < self.view_h + 100):
                continue
            top = y - round(m.sprite_rect[3])
            if m is state.dismantling:            # v0.5 M1: a barrinha do desmonte enchendo
                bw, bh = C.DISMANTLE_BAR
                self.draw_drill_bar(canvas, x, top - bh - 2, state.dismantle_progress, C.C_O2, False, w=bw, h=bh)
                continue
            if m.submerged or m.build > 0 or m.broken:   # parada (ou se construindo, ou quebrada): sem barra e sem raio
                continue
            if m.is_drill:
                top -= 2
                self.draw_drill_bar(canvas, x, top - self.DRILL_BAR_H, m.stored / C.DRILL_CAPACITY,
                                    C.ORE_COLORS[m.resource][0] if m.resource else C.C_TEXT, m.full)
                top -= self.DRILL_BAR_H + 1
            if blink and energy.starved(m.kind, factor):
                self.draw_bolt(canvas, x - 3, top - 10, self.NO_POWER)

    def draw_drill_bar(self, canvas, cx: int, y: int, fill: float, color, full: bool, w: int | None = None,
                       h: int | None = None) -> None:
        w, h = w or self.DRILL_BAR_W, h or self.DRILL_BAR_H
        x = cx - w // 2
        canvas.fill((20, 14, 12), (x, y, w, h))
        canvas.fill((52, 40, 34), (x + 1, y + 1, w - 2, h - 2))
        inner = round((w - 2) * max(0.0, min(1.0, fill)))
        if inner:
            canvas.fill(self.DRILL_BAR_FULL if full else color, (x + 1, y + 1, inner, h - 2))
            canvas.fill((255, 255, 255) if full else (255, 246, 230), (x + 1, y + 1, inner, 1))

    def draw_bolt(self, canvas, x: int, y: int, color) -> None:
        for dy, row in enumerate(self.BOLT):
            for dx, cell in enumerate(row):
                if cell == "#":
                    canvas.fill((0, 0, 0), (x + dx + 1, y + dy + 1, 1, 1))
        for dy, row in enumerate(self.BOLT):
            for dx, cell in enumerate(row):
                if cell == "#":
                    canvas.fill(color, (x + dx, y + dy, 1, 1))

    # ---- partículas (lasquinhas da mineração) ---------------------------------
    def spawn_chips(self, tile: tuple[int, int] | None, color: str, n: int = 10, at=None) -> None:
        """Lasquinhas voando. Saem do centro do tile ou de um ponto `at` (ex.: a ponta da broca)."""
        cx, cy = at if at else ((tile[0] + 0.5) * T, (tile[1] + 0.5) * T - WALL_LIFT / 2)
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(30, 90)
            self.particles.append([cx, cy, math.cos(a) * sp, math.sin(a) * sp - 40, random.uniform(0.3, 0.6), color])

    def update_particles(self, dt: float) -> None:
        for p in self.particles:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 220 * dt   # gravidade
            p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]

    def update_door_fx(self, state: GameState, dt: float) -> tuple[float, float] | None:
        """Anda a faísca e a névoa da porta emperrada (só dentro da VÉSPER-7, a até 8 tiles). Devolve onde estalou uma
        faísca neste passo (o app toca o `spark` com o ganho pela distância) ou None."""
        door = None
        if state.layer == layers.VESPER:
            door = next((t for t, k in state.world.fixtures.items() if k == "jammed_door"), None)
        elif self.door_fx.sparks or self.door_fx.fog:
            self.door_fx.clear()
        return self.door_fx.update(dt, door, (state.player.x, state.player.y))

    def draw_particles(self, canvas, cam) -> None:
        for x, y, _, _, _, color in self.particles:
            canvas.fill(color, (round(x - cam[0]), round(y - cam[1]), 2, 2))

    # ---- luz ------------------------------------------------------------------
    def draw_lighting(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        cam_x, cam_y = cam
        tick = t * 9
        lights = []   # (x, y, raio, cor, força do brilho, quanto "corta" o escuro)
        if state.active.has_base:   # luz da janela e do beacon da cápsula (pontos relativos ao canto do PNG)
            pod_x, pod_y = C.POD_ANCHOR[0] - 32 - cam_x, C.POD_ANCHOR[1] - 72 - cam_y
            spots = C.POD_LIGHTS["v4" if C.POD_SPRITE_REDESIGN else "v3"]
            wx, wy = spots["window"]
            lights.append((pod_x + wx, pod_y + wy, 170, (89, 208, 230), 0.2, 1.0))
            if tick % 10 < 5:
                bx, by = spots["beacon"]
                lights.append((pod_x + bx, pod_y + by, 44, (255, 90, 74), 0.5, 0.5))
        machine_light = {"o2": ((89, 208, 230), 80, -30, 0.2), "heater": ((255, 138, 61), 100, -20, 0.3),
                         "melter": ((159, 230, 255), 70, -36, 0.18), "smelter": ((255, 138, 61), 90, -22, 0.26),
                         "lamp": ((255, 222, 184), 96, -26, 0.22)}
        # no déficit de energia o brilho das máquinas fica mais fraco (metade com fator 0)
        dim = 0.5 + 0.5 * state.power.factor
        for m in state.machines:
            if m.submerged or m.build > 0 or m.broken:  # v0.4 M3.4: debaixo d'água não acende (v0.5: nem se construindo; v0.7: nem quebrada)
                continue
            if m.is_drill:   # luzinha quente na cabeça da drill, só enquanto ela trabalha
                if m.full:
                    continue
                ax, ay = m.anchor
                lights.append((ax - cam_x, ay - 66 - cam_y, 56, (255, 210, 140), round(0.14 * dim, 2), 1.0))
                continue
            if m.is_smelter and m.smelter_blocker is not None:    # v0.6 M3: só acende enquanto funde
                continue
            if m.kind.removesuffix("_t2") not in machine_light:   # painel solar e baú: sem luz própria
                continue
            rgb, r, dy, a = machine_light[m.kind.removesuffix("_t2")]
            a = round(a * dim, 2)
            if m.kind.endswith("_t2"):
                r = int(r * 1.25)
            lx, ly = m.tx * T + 16 - cam_x, m.ty * T + T + dy - cam_y
            if -r < lx < self.view_w + r and -r < ly < self.view_h + r:
                lights.append((lx, ly, r, rgb, a, 1.0))
        for tx, ty in state.world.terminals:
            lx, ly = tx * T + 16 - cam_x, ty * T + 16 - cam_y
            if -120 < lx < self.view_w + 120 and -120 < ly < self.view_h + 120:
                lights.append((lx, ly, 120, (111, 227, 160), 0.3, 1.0))
        p = state.player
        lights.append((p.x - cam_x, p.y - 18 - cam_y, 130, (255, 236, 210), 0.07, 1.0))

        darkness = self.view_fx("darkness")
        darkness.fill(self.ambient_color(stage))
        for x, y, r, _, _, cut in lights:
            darkness.blit(self.light_cut(r, cut), (round(x - r), round(y - r)), special_flags=pygame.BLEND_RGBA_SUB)
        canvas.blit(darkness, (0, 0))
        for x, y, r, rgb, a, _ in lights:
            gr = int(r * 0.75)
            canvas.blit(self.light_glow(gr, rgb, a), (round(x - gr), round(y - gr)), special_flags=pygame.BLEND_RGB_ADD)

    def transition_fade(self) -> float:
        """Quanto (0 a 1) o clima e a luz do próximo estágio já entraram. 0 = sem transição (ou o próximo
        estágio tem a mesma arte, como Tempestade → Árido: aí quem cuida da passagem é o `state.storm`)."""
        m = self.stage_map
        return m.progress if m.next_stage > m.stage and art_key(m.next_stage) != art_key(m.stage) else 0.0

    def ambient_color(self, stage: str) -> tuple[int, int, int, int]:
        """Escuro ambiente do estágio, misturado com o do próximo durante a transição."""
        color = C.PALETTES[stage]["ambient"]
        fade = self.transition_fade()
        if fade <= 0:
            return color
        target = C.PALETTES[art_key(self.stage_map.next_stage)]["ambient"]
        return tuple(round(a + (b - a) * fade) for a, b in zip(color, target))

    def _faded(self, name: str, surf: pygame.Surface, amount: float) -> pygame.Surface:
        """Cópia de `surf` com o alfa multiplicado por `amount` (0 a 1).

        Por que não `set_alpha`? Em superfície com alfa por pixel ele cai num caminho lento
        (~1 ms por tela cheia). Aqui o alfa é "assado" na cópia uma vez e reaproveitado até o
        nível mudar (32 níveis: na transição real isso muda a cada vários segundos).
        """
        level = round(amount * 32)
        if level >= 32:
            return surf
        name = f"{name}@{surf.get_width()}x{surf.get_height()}"   # cada tamanho de visão tem o seu
        cached = self._fade_cache.get(name)
        if cached is None or cached[0] != level:
            faded = surf.copy()
            faded.fill((255, 255, 255, level * 8), special_flags=pygame.BLEND_RGBA_MULT)
            cached = self._fade_cache[name] = (level, faded)
        return cached[1]

    # ---- clima por estágio ----------------------------------------------------
    def draw_atmosphere(self, canvas, stage: str, t: float, cam=(0, 0), geo=None) -> None:
        """Clima do estágio. Na transição, o do estágio atual vai saindo e o do próximo entrando. `cam` e `geo` servem
        pras borboletas do Verde não voarem sobre a neve da faixa gelada (dono, v0.5 M3.6.2)."""
        fade = self.transition_fade()
        self._draw_weather(canvas, stage, t, 1.0 - fade, cam, geo)
        if fade > 0:
            self._draw_weather(canvas, art_key(self.stage_map.next_stage), t, fade, cam, geo)
        canvas.blit(self.view_fx("vignette"), (0, 0))

    def _draw_weather(self, canvas, stage: str, t: float, amount: float = 1.0, cam=(0, 0), geo=None) -> None:
        """Clima de um estágio com intensidade `amount` (0 a 1): menos partículas e véus mais fracos."""
        W, H = self.view_w, self.view_h
        if stage == "dead":           # poeira laranja no ar
            canvas.blit(self._faded("tint_dead", self.view_fx("tint_dead"), amount), (0, 0))
            for i in range(round(70 * amount)):
                x = (hash01(i, 1, 7) * W + t * 27 * (0.5 + hash01(i, 2, 7))) % W
                y = hash01(i, 3, 7) * H + math.sin(t * 0.9 + i) * 6
                canvas.blit(self.dust[0 if i % 3 else 1], (int(x), int(y)))
        elif stage == "mist":         # névoa + chuva fina
            canvas.blit(self._faded("fog_gradient", self.view_fx("fog_gradient"), amount), (0, 0))
            fog_blob = self._faded("fog_blob", self.fog_blob, amount)
            for i in range(4):
                fx = ((hash01(i, 9, 7) * W + t * 11) % (W + 320)) - 160
                fy = hash01(i, 8, 7) * H
                canvas.blit(fog_blob, (int(fx - 180), int(fy - 180)))
            layer = self.view_fx("layer")
            layer.fill((0, 0, 0, 0))
            for i in range(round(80 * amount)):
                x = (hash01(i, 5, 7) * W + t * 36) % W
                y = (hash01(i, 6, 7) * H + t * 108) % H
                pygame.draw.line(layer, (185, 215, 230, 128), (x, y), (x - 4, y + 10))
            canvas.blit(layer, (0, 0))
        else:                          # luz quente + borboletas
            canvas.blit(self._faded("tint_green", self.view_fx("tint_green"), amount), (0, 0))
            for i in range(round(6 * amount)):
                x = round((hash01(i, 11, 7) * W + t * 22 + math.sin(t * 2.7 + i) * 16) % W)
                y = round(hash01(i, 12, 7) * H * 0.8 + 40 + math.sin(t * 4.5 + i * 2) * 12)
                if geo is not None and geo.region_px(cam[0] + x, cam[1] + y) == FROST:
                    continue                     # na neve não tem borboleta (era a "florzinha rosa" da faixa gelada)
                col = "#f5d36b" if i % 2 else "#f2a3c8"
                canvas.fill(col, (x, y, 2, 3))
                if (t * 9) % 4 < 2:
                    canvas.fill(col, (x - 4, y - 2, 4, 3))
                    canvas.fill(col, (x + 2, y - 2, 4, 3))
                else:
                    canvas.fill(col, (x - 2, y - 4, 2, 4))
                    canvas.fill(col, (x + 2, y - 4, 2, 4))
