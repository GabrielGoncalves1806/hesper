"""Desenha o mundo na tela: tiles, objetos, luz e clima.

Ordem de cada frame (de trás pra frente, como camadas de papel):
  1. tiles visíveis (chão, água, paredes com face, minério, terminais)
  2. zona de O₂ (círculo tracejado)
  3. objetos ordenados pelo Y do pé (cápsula, máquinas, plantas, player):
     quem está mais embaixo na tela é desenhado por último e fica "na frente"
  4. efeitos de mineração e fantasma da máquina sendo colocada
  5. luz (escurece tudo e "abre buracos" de luz) e clima do estágio (poeira, névoa, chuva...)
A UI (HUD, menus) vem depois, no ui.py.
"""

import math
import random

import pygame

from game import art
from game import config as C
from game.assets import Sprites
from game.systems import GameState, Mining
from game.transition import BASE_SOURCE, StageMap
from game.world import hash01

T = C.TILE
WALL_LIFT = C.WALL_LIFT   # o topo da parede é desenhado 24 px acima do tile (altura, estilo Core Keeper)
FACE_Y = 8       # a face (32×24) começa 8 px abaixo do topo do tile e vai até a borda de baixo


def build_draw_list(world, objects, tx0: int, tx1: int, ty0: int, ty1: int) -> list[tuple]:
    """Ordem de desenho por profundidade (função pura, testável sem tela).

    Percorre as linhas de cima pra baixo. Em cada linha: primeiro as paredes da linha,
    depois os objetos cujo pé (`ay`) cai nessa linha, do mais alto pro mais baixo.
    Como o topo de uma parede invade 24 px a linha de cima, quem anda logo acima dela
    é desenhado antes e fica meio escondido atrás do topo.

    objects: lista de (ay, qualquer_coisa). Devolve ("wall", tx, ty) e ("obj", qualquer_coisa).
    """
    by_row: dict[int, list] = {}
    for ay, obj in objects:
        by_row.setdefault(int((ay - 1) // T), []).append((ay, obj))
    wall_rows = range(ty0, ty1 + 1)
    order = []
    for row in sorted(set(wall_rows) | set(by_row)):
        if row in wall_rows:
            order += [("wall", tx, row) for tx in range(tx0, tx1 + 1) if world.is_solid(tx, row)]
        order += [("obj", obj) for _, obj in sorted(by_row.get(row, []), key=lambda o: o[0])]
    return order


def stage_key(stage: int) -> str:
    return C.STAGES[stage - 1].key


class Renderer:
    def __init__(self, sprites: Sprites):
        self.sprites = sprites
        self._surfaces: dict[str, tuple[pygame.Surface, bool]] = {}
        self._fx: dict[tuple, pygame.Surface] = {}
        self.particles: list[list[float]] = []   # [x, y, vx, vy, vida, cor]
        self.stage_map = StageMap()              # estágio visual de cada tile (transição gradual)
        self._fade_cache: dict[str, tuple[int, pygame.Surface]] = {}   # clima esmaecido (ver _faded)
        # Relógio das animações das máquinas: o App soma dt × fator da energia (game/energy.py).
        # No déficit ele anda mais devagar, então a drill gira e as máquinas animam mais devagar.
        self.machine_t = 0.0

        # Superfícies de efeito pré-calculadas (fazer isso a cada frame seria lento).
        self.shadow_top = self._alpha_strips(T, [(10, 84), (6, 40)])   # sombra que a parede joga no chão
        self.shadow_left = pygame.Surface((4, T), pygame.SRCALPHA)
        self.shadow_left.fill((0, 0, 0, 40))
        self.water_top = pygame.Surface((T, 4), pygame.SRCALPHA)
        self.water_top.fill((0, 0, 0, 72))
        self.water_left = pygame.Surface((2, T), pygame.SRCALPHA)
        self.water_left.fill((0, 0, 0, 46))
        self.outline_h = pygame.Surface((T, 1), pygame.SRCALPHA)
        self.outline_h.fill((0, 0, 0, 90))
        self.outline_v = pygame.Surface((1, T), pygame.SRCALPHA)
        self.outline_v.fill((0, 0, 0, 70))
        self.bedrock_shade = pygame.Surface((T, T), pygame.SRCALPHA)
        self.bedrock_shade.fill((0, 0, 0, 110))
        self.player_shadow = pygame.Surface((16, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(self.player_shadow, (0, 0, 0, 97), (0, 0, 16, 5))
        self.darkness = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        self.layer = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)   # camada reaproveitável
        self.vignette = art.vignette(C.SCREEN_W, C.SCREEN_H, (0, 0, 0), 128)
        self.zone_surf = pygame.Surface((C.BASE_RADIUS * 2 + 4, C.BASE_RADIUS * 2 + 4), pygame.SRCALPHA)
        self.tints = {
            "dead": self._full((214, 104, 52, 18)),
            "green": self._full((255, 226, 160, 13)),
        }
        self.fog_gradient = self._vertical_gradient((220, 230, 235), 51, 13)
        self.fog_blob = art.radial(180, (230, 236, 240), 70)
        self.dust = [self._dot((240, 170, 120, 128)), self._dot((255, 210, 170, 178))]

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
    def _full(rgba):
        s = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        s.fill(rgba)
        return s

    @staticmethod
    def _dot(rgba):
        s = pygame.Surface((2, 2), pygame.SRCALPHA)
        s.fill(rgba)
        return s

    @staticmethod
    def _vertical_gradient(rgb, top_alpha, bottom_alpha):
        s = pygame.Surface((1, 64), pygame.SRCALPHA)
        for y in range(64):
            a = top_alpha + (bottom_alpha - top_alpha) * y / 63
            s.set_at((0, y), (*rgb, int(a)))
        return pygame.transform.smoothscale(s, (C.SCREEN_W, C.SCREEN_H))

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
            glow = pygame.Surface(src.get_size())
            glow.fill((0, 0, 0))
            glow.blit(src, (0, 0))
            self._fx[key] = glow
        return self._fx[key]

    # ---- câmera ---------------------------------------------------------------
    @staticmethod
    def camera(state: GameState) -> tuple[int, int]:
        """Canto superior esquerdo da tela, em pixels do mundo. Segue o player e não sai do mapa."""
        max_x = state.world.width * T - C.SCREEN_W
        max_y = state.world.height * T - C.SCREEN_H
        cx = min(max(0, state.player.x - C.SCREEN_W / 2), max_x)
        cy = min(max(0, state.player.y - 16 - C.SCREEN_H / 2), max_y)
        return int(cx), int(cy)

    # ---- frame completo -------------------------------------------------------
    def draw(self, canvas: pygame.Surface, state: GameState, cam: tuple[int, int], t: float,
             ghost: tuple[str, tuple[int, int], int, bool] | None = None) -> None:
        stage = stage_key(state.stage)
        self.stage_map.update(state.ti, [BASE_SOURCE, *state.transition_sources])
        self.draw_floors(canvas, state, cam, stage, t)
        self.draw_veins(canvas, state, cam)
        self.draw_zone(canvas, cam, t)
        self.draw_walls_and_objects(canvas, state, cam, stage, t)
        if state.mining:
            self.draw_mining(canvas, state, state.mining, cam)
        if ghost:
            self.draw_ghost(canvas, cam, *ghost, t)
        self.draw_particles(canvas, cam)
        self.draw_lighting(canvas, state, cam, stage, t)
        self.draw_atmosphere(canvas, stage, t)

    # ---- tiles ----------------------------------------------------------------
    def visible_tiles(self, cam) -> tuple[int, int, int, int]:
        cam_x, cam_y = cam
        return cam_x // T, (cam_x + C.SCREEN_W) // T, cam_y // T, (cam_y + C.SCREEN_H) // T

    def draw_floors(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        """Passada 1: todo o chão e a água visíveis (as paredes vêm depois, por cima)."""
        world = state.world
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        backstop = C.PALETTES[stage]["face_dark"]
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                sx, sy = tx * T - cam[0], ty * T - cam[1]
                if world.is_solid(tx, ty):
                    canvas.fill(backstop, (sx, sy, T, T))   # fundo escuro (só aparece na borda do mapa)
                else:
                    num = self.stage_map.stage_at(tx, ty)   # pode estar "à frente" no meio da transição
                    self._draw_floor(canvas, world, tx, ty, sx, sy, stage_key(num), num, t)

    def draw_veins(self, canvas, state: GameState, cam) -> None:
        """Veios 2×2: overlay do chão (vale pros 3 estágios), antes das paredes e dos objetos."""
        for v in state.world.veins:
            sx, sy = v.tx * T - cam[0], v.ty * T - cam[1]
            if -64 < sx < C.SCREEN_W and -64 < sy < C.SCREEN_H:
                surf, _ = self.surface(f"vein_{v.resource}", lambda r=v.resource: art.vein(r))
                canvas.blit(surf, (sx, sy))

    def draw_walls_and_objects(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        """Passada 2: linha por linha, paredes com topo elevado e objetos ordenados pelo pé."""
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        objects = self.collect_objects(canvas, state, cam, t)
        # +1 linha embaixo: o topo elevado de uma parede logo abaixo da tela ainda aparece
        for item in build_draw_list(state.world, objects, tx0, tx1, ty0, ty1 + 1):
            if item[0] == "wall":
                _, tx, ty = item
                tile_stage = stage_key(self.stage_map.stage_at(tx, ty))
                self._draw_wall(canvas, state.world, tx, ty, tx * T - cam[0], ty * T - cam[1], tile_stage)
            else:
                item[1]()
        self._draw_player_silhouette(canvas, state, cam)
        # Broca da frente (lado e baixo) por cima de tudo: ela encosta no tile que está sendo minerado,
        # e esse tile pode ser uma parede desenhada depois do player (minerando pra baixo).
        if state.mining:
            frame, (dx, dy), behind = self.drill_sprite(state, t)
            if not behind:
                p = state.player
                canvas.blit(frame, (round(p.x - cam[0]) + dx, round(p.y - cam[1]) + dy))

    def player_occluded(self, state: GameState) -> bool:
        """O topo elevado de alguma parede da linha de baixo está cobrindo o player?"""
        p = state.player
        row_below = int((p.y - 1) // T) + 1
        cols = {int((p.x - 10) // T), int((p.x + 9) // T)}
        return any(state.world.is_solid(tx, row_below) for tx in cols)

    def _draw_player_silhouette(self, canvas, state: GameState, cam) -> None:
        """Player escondido atrás de parede (ex.: túnel de 1 tile): redesenha ele translúcido por cima,
        tipo raio-x, pra nunca perder o personagem de vista. A ilusão de profundidade continua."""
        if not self.player_occluded(state):
            return
        surf, flip = self._player_frame(state)
        ghost = (pygame.transform.flip(surf, True, False) if flip else surf.copy())
        ghost.set_alpha(95)
        p = state.player
        canvas.blit(ghost, (round(p.x - cam[0]) - ghost.get_width() // 2, round(p.y - cam[1]) - ghost.get_height()))

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
        open_up = not world.is_solid(tx, ty - 1)
        open_left = not world.is_solid(tx - 1, ty)
        open_right = not world.is_solid(tx + 1, ty)
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
        if not world.is_solid(tx, ty + 1):
            canvas.blit(self.surface(f"wall_face_{stage}", lambda: art.wall_face(stage))[0], (sx, sy + FACE_Y))
            if kind == C.TERMINAL:   # o terminal fica pendurado na face
                canvas.blit(self.surface("terminal", art.terminal)[0], (sx, sy))

    def _draw_floor(self, canvas, world, tx, ty, sx, sy, stage, stage_num, t) -> None:
        P = C.PALETTES[stage]
        v = int(hash01(tx, ty, 3) * 4)
        canvas.blit(self.surface(f"floor_{stage}_{v}", lambda: art.floor(stage, v))[0], (sx, sy))
        if self.stage_map.step > 0:
            self._blend_edges(canvas, world, tx, ty, sx, sy, stage_num, False,
                              lambda st: (f"floor_{st}_{v}", lambda: art.floor(st, v)))
        # cada vizinho é água (ou não) no estágio visual DELE (na transição, pode ser outro)
        wet = lambda x, y: world.is_water(x, y, self.stage_map.stage_at(x, y))   # noqa: E731
        if wet(tx, ty):
            up, down = wet(tx, ty - 1), wet(tx, ty + 1)
            left, right = wet(tx - 1, ty), wet(tx + 1, ty)
            water, fallback = self.surface(f"water_{stage}", lambda: art.water(stage))
            if not fallback:
                canvas.blit(water, (sx, sy))   # sprite aprovado: tile quadrado, sem borda
            else:
                # Fallback: a água encolhe 3 px nos lados sem água vizinha (vira poça, não quadrado).
                l, r = (0 if left else 3), (0 if right else 3)
                u, d = (0 if up else 3), (0 if down else 3)
                canvas.blit(water, (sx + l, sy + u), (l, u, T - l - r, T - u - d))
            if fallback:
                # água funda: só no miolo dos lagos (os 8 vizinhos também são água)
                if up and down and left and right and all(
                        wet(tx + dx, ty + dy) for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1))):
                    canvas.fill(P["water_d"], (sx, sy, T, T))
                if not up:
                    canvas.blit(self.water_top, (sx + l, sy + u), (0, 0, T - l - r, 4))
                    canvas.fill(P["foam"], (sx + l, sy + u + 4, T - l - r, 1))
                if not left:
                    canvas.blit(self.water_left, (sx + l, sy + u), (0, 0, 2, T - u - d))
            # reflexos que andam devagar
            h = hash01(tx, ty, 5)
            o = int((t * 5.4 + h * 24) % 24)
            canvas.fill((170, 214, 230), (sx + 4 + o, sy + 10 + int(h * 12), 5, 1))
            canvas.fill((170, 214, 230), (sx + 4 + (o + 12) % 22, sy + 21 + int(h * 5), 4, 1))
        # sombra que a parede projeta no chão
        if world.is_solid(tx, ty - 1):
            canvas.blit(self.shadow_top, (sx, sy))
        if world.is_solid(tx - 1, ty):
            canvas.blit(self.shadow_left, (sx, sy))

    # Ordem de "pontilhado" (Bayer 4×4): espalha os pixels da mistura sem formar listras.
    BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
    BLEND_DEPTH = 16   # px: até onde a mistura entra no tile (meio tile)
    BLEND_CELL = 2     # px: tamanho de cada "ponto" do pontilhado

    def _blend_edges(self, canvas, world, tx, ty, x, y, stage_num, solid, sprite) -> None:
        """Fronteira da mancha de transição: se o vizinho (do mesmo tipo: chão com chão, parede com
        parede) está em outro estágio, a versão daquele estágio entra pontilhada pela borda deste tile
        (50% na borda, sumindo até o meio). Como os dois lados fazem isso, a troca de estágio vira uma
        faixa de mistura em vez de um degrau de cor. `sprite(stage)` devolve (nome, desenho de fallback)."""
        for direction, (dx, dy) in (("left", (-1, 0)), ("right", (1, 0)), ("up", (0, -1)), ("down", (0, 1))):
            other = self.stage_map.stage_at(tx + dx, ty + dy)
            if other != stage_num and world.is_solid(tx + dx, ty + dy) == solid:
                canvas.blit(self._fringe(*sprite(stage_key(other)), direction), (x, y))

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

        ax, ay = C.POD_ANCHOR
        items.append((ay, lambda: self._draw_pod(canvas, ax - cam_x, ay - cam_y, t)))

        for m in state.machines:
            mx, my = m.anchor                                  # centro da base (drill: centro dos 2×2)
            if -64 < mx - cam_x < C.SCREEN_W + 64 and -80 < my - cam_y < C.SCREEN_H + 80:
                if m.is_drill:
                    items.append((my, lambda m=m, mx=mx, my=my: self.draw_drill(canvas, m, mx - cam_x, my - cam_y, self.machine_t)))
                else:
                    items.append((my, lambda m=m, mx=mx, my=my: self.draw_machine(canvas, m.kind, mx - cam_x, my - cam_y, self.machine_t, m.rotation)))

        if self.stage_map.next_stage >= 3:   # plantas nascem junto com a mancha verde
            tx0, ty0 = cam_x // T, cam_y // T
            for ty in range(ty0, ty0 + C.SCREEN_H // T + 3):
                for tx in range(tx0, tx0 + C.SCREEN_W // T + 2):
                    kind = state.world.plant_at(tx, ty)
                    if kind and self.stage_map.stage_at(tx, ty) >= 3 and not state.machine_at((tx, ty)):
                        px, py = tx * T + T // 2, (ty + 1) * T
                        surf = self.surface(f"plant_{kind}", lambda k=kind: art.plant(k))[0]
                        items.append((py, lambda s=surf, px=px, py=py: canvas.blit(
                            s, (px - cam_x - s.get_width() // 2, py - cam_y - s.get_height()))))

        p = state.player
        items.append((p.y, lambda: self._draw_player(canvas, state, p.x - cam_x, p.y - cam_y, t)))
        return items

    def _blit_anchored(self, canvas, surf, ax, ay, flip=False):
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        canvas.blit(surf, (round(ax) - surf.get_width() // 2, round(ay) - surf.get_height()))

    def _draw_pod(self, canvas, ax, ay, t) -> None:
        surf, fallback = self.surface("pod", art.pod)
        self._blit_anchored(canvas, surf, ax, ay)
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

    def machine_preview(self, kind: str) -> pygame.Surface:
        """Imagem da máquina pro fabricador (resolução cheia, sem redimensionar com suavização)."""
        if kind == "drill":
            icon = self.sprites.get("icon_drill")
            if icon:
                return pygame.transform.scale_by(icon, 3)        # 16×16 → 48×48, pixel a pixel
            frame = self.drill_frame(0)
            return frame.subsurface((0, 16, 64, 64))              # sem a cabeça, pra caber na caixinha
        return self.surface(C.MACHINES[kind].sprite, lambda: art.machine(kind))[0]

    def draw_machine(self, canvas, kind, ax, ay, t, rotation=0, alpha=None) -> None:
        name = C.MACHINES[kind].sprite
        surf, fallback = self.surface(name, lambda: art.machine(kind))
        if alpha is not None:
            surf = surf.copy()
            surf.set_alpha(alpha)
        self._blit_anchored(canvas, surf, ax, ay, flip=rotation % 2 == 1)
        if fallback and alpha is None and rotation % 2 == 0:
            art.machine_anim(canvas, kind, round(ax), round(ay), t)

    def _player_frame(self, state: GameState) -> tuple[pygame.Surface, bool]:
        """Quadro atual do player (parado ou andando) e se precisa espelhar (olhando pra esquerda)."""
        p = state.player
        # "left" usa o sprite de lado espelhado; "right" usa ele direto
        view = "side" if p.direction in ("left", "right") else p.direction
        if p.moving and not state.fainted:
            sheet, _ = self.surface(f"player_walk_{view}", lambda: art.player_walk(view))
            frame = int(p.walk_time * 9) % 4          # ~9 quadros por segundo
            return sheet.subsurface((frame * 32, 0, 32, 32)), p.direction == "left"
        return self.surface(f"player_{view}", lambda: art.player(view))[0], p.direction == "left"

    def _draw_player(self, canvas, state: GameState, x, y, t) -> None:
        canvas.blit(self.player_shadow, (round(x) - 8, round(y) - 5))   # elipse 16×5 nos pés (linha 30)
        surf, flip = self._player_frame(state)
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
        return {"right": (p.x + 20, p.y - 11), "left": (p.x - 20, p.y - 11),
                "down": (p.x + 5, p.y + 8), "up": (p.x + 12, p.y - 28)}[p.direction]

    # ---- mineração e colocação ------------------------------------------------
    def draw_mining(self, canvas, state: GameState, mining: Mining, cam) -> None:
        tx, ty = mining.tile
        kind = state.world.get(tx, ty)
        if kind not in C.MINE_TIME:
            return
        prog = mining.progress(kind)
        px = tx * T - cam[0]
        py = ty * T - WALL_LIFT - cam[1]                          # topo elevado da parede
        h = WALL_LIFT + (T if not state.world.is_solid(tx, ty + 1) else FACE_Y)   # topo + face (se tiver)
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
        else:
            self.draw_machine(canvas, kind, px + T // 2, py + T, t, rotation, alpha=128)

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

    def draw_particles(self, canvas, cam) -> None:
        for x, y, _, _, _, color in self.particles:
            canvas.fill(color, (round(x - cam[0]), round(y - cam[1]), 2, 2))

    # ---- luz ------------------------------------------------------------------
    def draw_lighting(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        cam_x, cam_y = cam
        tick = t * 9
        lights = []   # (x, y, raio, cor, força do brilho, quanto "corta" o escuro)
        pod_x, pod_y = C.POD_ANCHOR[0] - 32 - cam_x, C.POD_ANCHOR[1] - 70 - cam_y
        lights.append((pod_x + 20, pod_y + 29, 170, (89, 208, 230), 0.2, 1.0))
        if tick % 10 < 5:
            lights.append((pod_x + 50, pod_y + 2, 44, (255, 90, 74), 0.5, 0.5))
        machine_light = {"o2": ((89, 208, 230), 80, -30, 0.2), "heater": ((255, 138, 61), 100, -20, 0.3),
                         "melter": ((159, 230, 255), 70, -36, 0.18)}
        # no déficit de energia o brilho das máquinas fica mais fraco (metade com fator 0)
        dim = 0.5 + 0.5 * state.power.factor
        for m in state.machines:
            if m.is_drill:   # luzinha quente na cabeça da drill, só enquanto ela trabalha
                if m.full:
                    continue
                ax, ay = m.anchor
                lights.append((ax - cam_x, ay - 66 - cam_y, 56, (255, 210, 140), round(0.14 * dim, 2), 1.0))
                continue
            if m.kind.removesuffix("_t2") not in machine_light:   # painel solar: sem luz própria
                continue
            rgb, r, dy, a = machine_light[m.kind.removesuffix("_t2")]
            a = round(a * dim, 2)
            if m.kind.endswith("_t2"):
                r = int(r * 1.25)
            lx, ly = m.tx * T + 16 - cam_x, m.ty * T + T + dy - cam_y
            if -r < lx < C.SCREEN_W + r and -r < ly < C.SCREEN_H + r:
                lights.append((lx, ly, r, rgb, a, 1.0))
        for tx, ty in state.world.terminals:
            lx, ly = tx * T + 16 - cam_x, ty * T + 16 - cam_y
            if -120 < lx < C.SCREEN_W + 120 and -120 < ly < C.SCREEN_H + 120:
                lights.append((lx, ly, 120, (111, 227, 160), 0.3, 1.0))
        p = state.player
        lights.append((p.x - cam_x, p.y - 18 - cam_y, 130, (255, 236, 210), 0.07, 1.0))

        self.darkness.fill(self.ambient_color(stage))
        for x, y, r, _, _, cut in lights:
            self.darkness.blit(self.light_cut(r, cut), (round(x - r), round(y - r)), special_flags=pygame.BLEND_RGBA_SUB)
        canvas.blit(self.darkness, (0, 0))
        for x, y, r, rgb, a, _ in lights:
            gr = int(r * 0.75)
            canvas.blit(self.light_glow(gr, rgb, a), (round(x - gr), round(y - gr)), special_flags=pygame.BLEND_RGB_ADD)

    def transition_fade(self) -> float:
        """Quanto (0 a 1) o clima e a luz do próximo estágio já entraram. 0 = sem transição."""
        m = self.stage_map
        return m.progress if m.next_stage > m.stage else 0.0

    def ambient_color(self, stage: str) -> tuple[int, int, int, int]:
        """Escuro ambiente do estágio, misturado com o do próximo durante a transição."""
        color = C.PALETTES[stage]["ambient"]
        fade = self.transition_fade()
        if fade <= 0:
            return color
        target = C.PALETTES[stage_key(self.stage_map.next_stage)]["ambient"]
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
        cached = self._fade_cache.get(name)
        if cached is None or cached[0] != level:
            faded = surf.copy()
            faded.fill((255, 255, 255, level * 8), special_flags=pygame.BLEND_RGBA_MULT)
            cached = self._fade_cache[name] = (level, faded)
        return cached[1]

    # ---- clima por estágio ----------------------------------------------------
    def draw_atmosphere(self, canvas, stage: str, t: float) -> None:
        """Clima do estágio. Na transição, o do estágio atual vai saindo e o do próximo entrando."""
        fade = self.transition_fade()
        self._draw_weather(canvas, stage, t, 1.0 - fade)
        if fade > 0:
            self._draw_weather(canvas, stage_key(self.stage_map.next_stage), t, fade)
        canvas.blit(self.vignette, (0, 0))

    def _draw_weather(self, canvas, stage: str, t: float, amount: float = 1.0) -> None:
        """Clima de um estágio com intensidade `amount` (0 a 1): menos partículas e véus mais fracos."""
        W, H = C.SCREEN_W, C.SCREEN_H
        if stage == "dead":           # poeira laranja no ar
            canvas.blit(self._faded("tint_dead", self.tints["dead"], amount), (0, 0))
            for i in range(round(70 * amount)):
                x = (hash01(i, 1, 7) * W + t * 27 * (0.5 + hash01(i, 2, 7))) % W
                y = hash01(i, 3, 7) * H + math.sin(t * 0.9 + i) * 6
                canvas.blit(self.dust[0 if i % 3 else 1], (int(x), int(y)))
        elif stage == "mist":         # névoa + chuva fina
            canvas.blit(self._faded("fog_gradient", self.fog_gradient, amount), (0, 0))
            fog_blob = self._faded("fog_blob", self.fog_blob, amount)
            for i in range(4):
                fx = ((hash01(i, 9, 7) * W + t * 11) % (W + 320)) - 160
                fy = hash01(i, 8, 7) * H
                canvas.blit(fog_blob, (int(fx - 180), int(fy - 180)))
            self.layer.fill((0, 0, 0, 0))
            for i in range(round(80 * amount)):
                x = (hash01(i, 5, 7) * W + t * 36) % W
                y = (hash01(i, 6, 7) * H + t * 108) % H
                pygame.draw.line(self.layer, (185, 215, 230, 128), (x, y), (x - 4, y + 10))
            canvas.blit(self.layer, (0, 0))
        else:                          # luz quente + borboletas
            canvas.blit(self._faded("tint_green", self.tints["green"], amount), (0, 0))
            for i in range(round(6 * amount)):
                x = round((hash01(i, 11, 7) * W + t * 22 + math.sin(t * 2.7 + i) * 16) % W)
                y = round(hash01(i, 12, 7) * H * 0.8 + 40 + math.sin(t * 4.5 + i * 2) * 12)
                col = "#f5d36b" if i % 2 else "#f2a3c8"
                canvas.fill(col, (x, y, 2, 3))
                if (t * 9) % 4 < 2:
                    canvas.fill(col, (x - 4, y - 2, 4, 3))
                    canvas.fill(col, (x + 2, y - 2, 4, 3))
                else:
                    canvas.fill(col, (x - 2, y - 4, 2, 4))
                    canvas.fill(col, (x + 2, y - 4, 2, 4))
