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
from game.world import hash01

T = C.TILE
WALL_TOP = 8   # quantos px do topo da rocha aparecem acima da face (face = 24 px, §6)


def stage_key(stage: int) -> str:
    return C.STAGES[stage - 1].key


class Renderer:
    def __init__(self, sprites: Sprites):
        self.sprites = sprites
        self._surfaces: dict[str, tuple[pygame.Surface, bool]] = {}
        self._fx: dict[tuple, pygame.Surface] = {}
        self.particles: list[list[float]] = []   # [x, y, vx, vy, vida, cor]

        # Superfícies de efeito pré-calculadas (fazer isso a cada frame seria lento).
        self.shadow_top = self._alpha_strips(T, [(10, 84), (6, 40)])   # sombra que a parede joga no chão
        self.shadow_left = pygame.Surface((4, T), pygame.SRCALPHA)
        self.shadow_left.fill((0, 0, 0, 40))
        self.water_top = pygame.Surface((T, 4), pygame.SRCALPHA)
        self.water_top.fill((0, 0, 0, 72))
        self.water_left = pygame.Surface((2, T), pygame.SRCALPHA)
        self.water_left.fill((0, 0, 0, 46))
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
        self.draw_tiles(canvas, state, cam, stage, t)
        self.draw_zone(canvas, cam, t)
        if state.mining:
            self.draw_mining(canvas, state, state.mining, cam)
        self.draw_objects(canvas, state, cam, stage, t)
        if ghost:
            self.draw_ghost(canvas, cam, *ghost, t)
        self.draw_particles(canvas, cam)
        self.draw_lighting(canvas, state, cam, stage, t)
        self.draw_atmosphere(canvas, stage, t)

    # ---- tiles ----------------------------------------------------------------
    def draw_tiles(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        world = state.world
        cam_x, cam_y = cam
        tx0, ty0 = cam_x // T, cam_y // T
        tx1, ty1 = (cam_x + C.SCREEN_W) // T, (cam_y + C.SCREEN_H) // T
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                sx, sy = tx * T - cam_x, ty * T - cam_y
                if world.is_solid(tx, ty):
                    self._draw_wall(canvas, world, tx, ty, sx, sy, stage)
                else:
                    self._draw_floor(canvas, world, tx, ty, sx, sy, stage, state.stage, t)

    def _draw_wall(self, canvas, world, tx, ty, sx, sy, stage) -> None:
        P = C.PALETTES[stage]
        kind = world.get(tx, ty)
        v = int(hash01(tx, ty, 3) * 3)
        surf, fallback = self.surface(f"wall_{stage}_{v}", lambda: art.wall(stage, v))
        canvas.blit(surf, (sx, sy))
        has_face = not world.is_solid(tx, ty + 1)
        top = WALL_TOP if has_face else T   # com chão embaixo, só 8 px de topo aparecem
        if fallback:   # bordas iluminadas onde a parede encontra o chão (os PNGs não precisam)
            if not world.is_solid(tx, ty - 1):
                canvas.fill(P["edge"], (sx, sy, T, 2))
            if not world.is_solid(tx - 1, ty):
                canvas.fill(P["edge"], (sx, sy, 1, top))
            if not world.is_solid(tx + 1, ty):
                canvas.fill(P["rock_dot"], (sx + T - 1, sy, 1, top))
        if fallback and stage == "green" and hash01(tx, ty, 70) < 0.5:
            canvas.blit(self.surface(None, lambda: art.moss(v), f"moss#{v}")[0], (sx, sy))
        if has_face:
            canvas.blit(self.surface(f"wall_face_{stage}", lambda: art.wall_face(stage))[0], (sx, sy + WALL_TOP))
        # minério e terminal vêm depois da face: ficam visíveis "cravados" na parede
        resource = C.ORE_TILES.get(kind)
        if resource:
            ov = int(hash01(tx, ty, 80) * 3)
            canvas.blit(self.surface(f"ore_{resource}", lambda: art.ore(resource, ov), f"ore_{resource}#{ov}")[0], (sx, sy))
        if kind == C.BEDROCK:
            canvas.blit(self.bedrock_shade, (sx, sy))
        elif kind == C.TERMINAL:
            canvas.blit(self.surface("terminal", art.terminal)[0], (sx, sy))

    def _draw_floor(self, canvas, world, tx, ty, sx, sy, stage, stage_num, t) -> None:
        P = C.PALETTES[stage]
        v = int(hash01(tx, ty, 3) * 4)
        canvas.blit(self.surface(f"floor_{stage}_{v}", lambda: art.floor(stage, v))[0], (sx, sy))
        if world.is_water(tx, ty, stage_num):
            up, down = world.is_water(tx, ty - 1, stage_num), world.is_water(tx, ty + 1, stage_num)
            left, right = world.is_water(tx - 1, ty, stage_num), world.is_water(tx + 1, ty, stage_num)
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
                        world.is_water(tx + dx, ty + dy, stage_num) for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1))):
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
    def draw_objects(self, canvas, state: GameState, cam, stage: str, t: float) -> None:
        cam_x, cam_y = cam
        items: list[tuple[float, callable]] = []

        ax, ay = C.POD_ANCHOR
        items.append((ay, lambda: self._draw_pod(canvas, ax - cam_x, ay - cam_y, t)))

        for m in state.machines:
            mx, my = m.tx * T + T // 2, (m.ty + 1) * T      # âncora: centro do tile, borda de baixo
            if -64 < mx - cam_x < C.SCREEN_W + 64 and -80 < my - cam_y < C.SCREEN_H + 80:
                items.append((my, lambda m=m, mx=mx, my=my: self.draw_machine(canvas, m.kind, mx - cam_x, my - cam_y, t, m.rotation)))

        if state.stage >= 3:
            tx0, ty0 = cam_x // T, cam_y // T
            for ty in range(ty0, ty0 + C.SCREEN_H // T + 3):
                for tx in range(tx0, tx0 + C.SCREEN_W // T + 2):
                    kind = state.world.plant_at(tx, ty)
                    if kind and not state.machine_at((tx, ty)):
                        px, py = tx * T + T // 2, (ty + 1) * T
                        surf = self.surface(f"plant_{kind}", lambda k=kind: art.plant(k))[0]
                        items.append((py, lambda s=surf, px=px, py=py: canvas.blit(
                            s, (px - cam_x - s.get_width() // 2, py - cam_y - s.get_height()))))

        p = state.player
        items.append((p.y, lambda: self._draw_player(canvas, state, p.x - cam_x, p.y - cam_y, t)))

        for _, draw in sorted(items, key=lambda it: it[0]):
            draw()

    def _blit_anchored(self, canvas, surf, ax, ay, flip=False):
        if flip:
            surf = pygame.transform.flip(surf, True, False)
        canvas.blit(surf, (round(ax) - surf.get_width() // 2, round(ay) - surf.get_height()))

    def _draw_pod(self, canvas, ax, ay, t) -> None:
        surf, fallback = self.surface("pod", art.pod)
        self._blit_anchored(canvas, surf, ax, ay)
        if fallback and (t * 9) % 10 < 5:   # luz da antena piscando
            canvas.fill("#ff5a4a", (round(ax) - 32 + 49, round(ay) - 72 + 1, 3, 3))

    def draw_machine(self, canvas, kind, ax, ay, t, rotation=0, alpha=None) -> None:
        name = C.MACHINES[kind].sprite
        surf, fallback = self.surface(name, lambda: art.machine(kind))
        if alpha is not None:
            surf = surf.copy()
            surf.set_alpha(alpha)
        self._blit_anchored(canvas, surf, ax, ay, flip=rotation % 2 == 1)
        if fallback and alpha is None and rotation % 2 == 0:
            art.machine_anim(canvas, kind, round(ax), round(ay), t)

    def _draw_player(self, canvas, state: GameState, x, y, t) -> None:
        p = state.player
        canvas.blit(self.player_shadow, (round(x) - 8, round(y) - 5))   # elipse 16×5 nos pés (linha 30)
        # "left" usa o sprite de lado espelhado; "right" usa ele direto
        view = "side" if p.direction in ("left", "right") else p.direction
        if p.moving and not state.fainted:
            sheet, _ = self.surface(f"player_walk_{view}", lambda: art.player_walk(view))
            frame = int(p.walk_time * 9) % 4          # ~9 quadros por segundo
            surf = sheet.subsurface((frame * 32, 0, 32, 32))
        else:
            surf, _ = self.surface(f"player_{view}", lambda: art.player(view))
        self._blit_anchored(canvas, surf, x, y, flip=p.direction == "left")
        if state.mining and view == "side":   # furadeira na mão (só aparece de lado)
            d = 1 if p.direction == "right" else -1
            bx = round(x) + (4 if d > 0 else -17)
            by = round(y) + 3
            canvas.fill("#1a1418", (bx, by - 17, 13, 7))
            canvas.fill("#6b717a", (bx + 1, by - 16, 11, 5))
            canvas.fill("#8a929c", (bx + 1, by - 16, 11, 1))
            tip = bx + 12 if d > 0 else bx - 4
            canvas.fill(C.C_ACCENT, (tip, by - 15, 4, 3))
            canvas.fill(C.C_TI, (tip + (4 if d > 0 else -2), by - 14, 2, 1))

    # ---- mineração e colocação ------------------------------------------------
    def draw_mining(self, canvas, state: GameState, mining: Mining, cam) -> None:
        tx, ty = mining.tile
        kind = state.world.get(tx, ty)
        if kind not in C.MINE_TIME:
            return
        prog = mining.progress(kind)
        px, py = tx * T - cam[0], ty * T - cam[1]
        # rachaduras aparecendo conforme o progresso
        cracks = [(4, 3), (5, 4), (6, 5), (7, 6), (8, 7), (9, 8), (9, 9), (8, 10), (8, 11), (7, 12), (7, 13), (6, 14),
                  (10, 8), (11, 8), (12, 7), (13, 7), (14, 7), (15, 8), (16, 9), (17, 10), (18, 10), (19, 11),
                  (20, 12), (21, 12), (22, 13), (16, 6), (17, 5), (18, 4)]
        for cx, cy in cracks[: int(len(cracks) * prog)]:
            canvas.fill((15, 8, 6), (px + cx, py + cy, 1, 1))
        # cantoneiras brancas em volta do tile
        for x, y, w, h in [(-2, -2, 8, 2), (-2, -2, 2, 8), (T - 6, -2, 8, 2), (T, -2, 2, 8),
                           (-2, T, 8, 2), (-2, T - 6, 2, 8), (T - 6, T, 8, 2), (T, T - 6, 2, 8)]:
            canvas.fill((255, 255, 255), (px + x, py + y, w, h))
        # barrinha de progresso
        canvas.fill((0, 0, 0), (px - 4, py - 16, 40, 8))
        canvas.fill(C.C_TI, (px - 2, py - 14, round(36 * prog), 4))
        canvas.fill("#fff3c4", (px - 2, py - 14, round(36 * prog), 1))

    def draw_ghost(self, canvas, cam, kind, tile, rotation, valid, t) -> None:
        px, py = tile[0] * T - cam[0], tile[1] * T - cam[1]
        color = (127, 214, 122) if valid else (255, 106, 85)
        tint = pygame.Surface((T, T), pygame.SRCALPHA)
        tint.fill((*color, 51))
        canvas.blit(tint, (px, py))
        # contorno tracejado andando
        step = int(t * 8) % 8
        for i in range(0, T - 2, 8):
            for x, y, w, h in [(px + 1 + (i + step) % (T - 2), py + 1, 4, 2), (px + 1 + (i + step) % (T - 2), py + T - 3, 4, 2),
                               (px + 1, py + 1 + (i + step) % (T - 2), 2, 4), (px + T - 3, py + 1 + (i + step) % (T - 2), 2, 4)]:
                canvas.fill(color, (x, y, w, h))
        self.draw_machine(canvas, kind, px + T // 2, py + T, t, rotation, alpha=128)

    # ---- partículas (lasquinhas da mineração) ---------------------------------
    def spawn_chips(self, tile: tuple[int, int], color: str, n: int = 10) -> None:
        cx, cy = (tile[0] + 0.5) * T, (tile[1] + 0.5) * T
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
        for m in state.machines:
            rgb, r, dy, a = machine_light[m.kind.removesuffix("_t2")]
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

        self.darkness.fill(C.PALETTES[stage]["ambient"])
        for x, y, r, _, _, cut in lights:
            self.darkness.blit(self.light_cut(r, cut), (round(x - r), round(y - r)), special_flags=pygame.BLEND_RGBA_SUB)
        canvas.blit(self.darkness, (0, 0))
        for x, y, r, rgb, a, _ in lights:
            gr = int(r * 0.75)
            canvas.blit(self.light_glow(gr, rgb, a), (round(x - gr), round(y - gr)), special_flags=pygame.BLEND_RGB_ADD)

    # ---- clima por estágio ----------------------------------------------------
    def draw_atmosphere(self, canvas, stage: str, t: float) -> None:
        W, H = C.SCREEN_W, C.SCREEN_H
        if stage == "dead":           # poeira laranja no ar
            canvas.blit(self.tints["dead"], (0, 0))
            for i in range(70):
                x = (hash01(i, 1, 7) * W + t * 27 * (0.5 + hash01(i, 2, 7))) % W
                y = hash01(i, 3, 7) * H + math.sin(t * 0.9 + i) * 6
                canvas.blit(self.dust[0 if i % 3 else 1], (int(x), int(y)))
        elif stage == "mist":         # névoa + chuva fina
            canvas.blit(self.fog_gradient, (0, 0))
            for i in range(4):
                fx = ((hash01(i, 9, 7) * W + t * 11) % (W + 320)) - 160
                fy = hash01(i, 8, 7) * H
                canvas.blit(self.fog_blob, (int(fx - 180), int(fy - 180)))
            self.layer.fill((0, 0, 0, 0))
            for i in range(80):
                x = (hash01(i, 5, 7) * W + t * 36) % W
                y = (hash01(i, 6, 7) * H + t * 108) % H
                pygame.draw.line(self.layer, (185, 215, 230, 128), (x, y), (x - 4, y + 10))
            canvas.blit(self.layer, (0, 0))
        else:                          # luz quente + borboletas
            canvas.blit(self.tints["green"], (0, 0))
            for i in range(6):
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
        canvas.blit(self.vignette, (0, 0))
