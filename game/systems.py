"""As regras do jogo: mineração, O₂, fabricador, máquinas, Ti e estágios.

Tudo aqui é Python puro (nada de pygame). O `App` (app.py) lê o teclado/mouse,
traduz isso num `Controls` e chama `GameState.update(dt, controls)` a cada frame.
O estado avisa o que aconteceu (pra tocar som, mostrar texto flutuante etc.)
através da lista `events`, que o App esvazia com `pop_events()`.
"""

import math
import random
from dataclasses import dataclass

from game import config as C
from game.player import Player, Rect, overlaps
from game.world import World


@dataclass
class Controls:
    """O que o jogador quer fazer neste frame (já traduzido do teclado/mouse)."""
    move_x: float = 0.0
    move_y: float = 0.0
    mine_tile: tuple[int, int] | None = None   # tile mirado enquanto segura o clique


@dataclass
class Machine:
    kind: str            # chave em config.MACHINES
    tx: int
    ty: int
    rotation: int = 0    # 0..3, só cosmético

    @property
    def type(self) -> C.MachineType:
        return C.MACHINES[self.kind]

    @property
    def rect(self) -> Rect:
        return (self.tx * C.TILE + 4, self.ty * C.TILE + 14, C.TILE - 8, C.TILE - 14)


@dataclass
class Mining:
    tile: tuple[int, int]
    elapsed: float = 0.0
    next_hit: float = 0.0

    def progress(self, kind: int) -> float:
        return min(1.0, self.elapsed / C.MINE_TIME[kind])


POD_RECT: Rect = (C.POD_TILES[0][0] * C.TILE + 4, C.POD_TILES[0][1] * C.TILE + 12, 2 * C.TILE - 8, C.TILE - 12)


def stage_for_ti(ti: float) -> int:
    stage = 1
    for s in C.STAGES:
        if ti >= s.ti:
            stage = s.number
    return stage


# ---- quanto falta pro próximo estágio (funções puras, testadas em tests/test_progress.py) ----
def stage_progress(ti: float) -> tuple[C.Stage | None, float, float]:
    """(próximo estágio, progresso de 0 a 1 DENTRO do estágio atual, Ti que falta).

    O progresso é relativo ao estágio atual: no estágio 2 (10k → 100k) com Ti 12.914 dá ~3%.
    No último estágio devolve (None, 1.0, 0).
    """
    current = C.STAGES[stage_for_ti(ti) - 1]
    if current.number == len(C.STAGES):
        return None, 1.0, 0.0
    nxt = C.STAGES[current.number]
    fraction = (ti - current.ti) / (nxt.ti - current.ti)
    return nxt, max(0.0, min(1.0, fraction)), max(0.0, nxt.ti - ti)


def format_eta(seconds: float) -> str:
    """Tempo amigável: '~45 s', '~12 min', '~1 h 20 min', '~2 h'."""
    if seconds < 59.5:
        return f"~{max(1, round(seconds))} s"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"~{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"~{hours} h" if minutes == 0 else f"~{hours} h {minutes} min"


def eta_label(remaining: float, rate_per_second: float) -> str:
    """Estimativa de tempo até o próximo estágio, ou um aviso se nada estiver produzindo Ti."""
    if rate_per_second <= 1e-6:
        return "coloque máquinas"
    return format_eta(remaining / rate_per_second)


def smooth_rate(previous: float, target: float, dt: float, tau: float = C.RATE_SMOOTHING) -> float:
    """Média móvel exponencial: anda em direção ao alvo sem pular (tau = 'memória' em segundos)."""
    return previous + (target - previous) * (1 - math.exp(-dt / tau))


class GameState:
    def __init__(self, seed: int = C.WORLD_SEED, rng: random.Random | None = None):
        self.world = World.generate(seed)
        self.rng = rng or random.Random()
        self.player = Player(*C.SPAWN_POS)
        self.inventory = {r: 0 for r in C.RESOURCES}
        self.machines_owned = {k: 0 for k in C.MACHINES}   # fabricadas, ainda não colocadas
        self.machines: list[Machine] = []                  # colocadas no mundo
        self.indices = {"o2": 0.0, "heat": 0.0, "water": 0.0}
        self.o2 = C.O2_MAX
        self.stage = 1
        self.mining: Mining | None = None
        self.fainted = False
        self.faint_time = 0.0          # segundos desde o desmaio
        self.time_scale = 1            # F1 muda pra 10
        self.play_time = 0.0
        self.logs_read: set[int] = set()
        self.was_in_base = True
        self.smoothed_rate = 0.0       # taxa de Ti por segundo (real), suavizada pra estimativa do HUD
        # pros objetivos (objectives.py): total já minerado (craftar não desconta) e se já abriu o fabricador
        self.mined_total = {r: 0 for r in C.RESOURCES}
        self.fabricator_opened = False
        self.events: list[tuple] = []

    # ---- consultas ----------------------------------------------------------
    @property
    def ti(self) -> float:
        """Índice de terraformação = O₂ + Calor + Água."""
        return sum(self.indices.values())

    @property
    def ti_rate(self) -> float:
        return sum(m.type.rate for m in self.machines)

    def dist_to_base(self) -> float:
        return math.hypot(self.player.x - C.BASE_CENTER[0], self.player.y - C.BASE_CENTER[1])

    def in_base_zone(self) -> bool:
        return self.dist_to_base() <= C.BASE_RADIUS

    def machine_at(self, tile: tuple[int, int]) -> Machine | None:
        for m in self.machines:
            if (m.tx, m.ty) == tile:
                return m
        return None

    def solids_near(self, box: Rect) -> list[Rect]:
        """Retângulos sólidos que podem encostar na caixa: paredes, máquinas e a cápsula."""
        solids = []
        x0, y0 = int(box[0] // C.TILE) - 1, int(box[1] // C.TILE) - 1
        x1, y1 = int((box[0] + box[2]) // C.TILE) + 1, int((box[1] + box[3]) // C.TILE) + 1
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if self.world.is_solid(tx, ty):
                    solids.append((tx * C.TILE, ty * C.TILE, C.TILE, C.TILE))
        solids += [m.rect for m in self.machines]
        solids.append(POD_RECT)
        return solids

    # ---- loop principal -----------------------------------------------------
    def update(self, dt: float, controls: Controls) -> None:
        dt = min(dt, C.MAX_DT)
        self.play_time += dt
        sim_dt = dt * self.time_scale     # O₂ e máquinas andam mais rápido com F1

        if self.fainted:
            self._update_faint(dt)
        else:
            self.player.move(controls.move_x, controls.move_y, dt, self.solids_near)
            self._update_mining(dt, controls.mine_tile)
            self._update_o2(sim_dt)
        self._update_machines(sim_dt)
        # taxa efetiva em segundos reais (com F1 ligado, as máquinas rendem 10×)
        self.smoothed_rate = smooth_rate(self.smoothed_rate, self.ti_rate * self.time_scale, dt)

    # ---- mineração ----------------------------------------------------------
    def can_mine(self, tile: tuple[int, int]) -> bool:
        if not self.world.is_minable(*tile):
            return False
        px, py = self.player.tile
        return max(abs(tile[0] - px), abs(tile[1] - py)) <= C.MINE_REACH

    def _update_mining(self, dt: float, tile: tuple[int, int] | None) -> None:
        if tile is None or not self.can_mine(tile):
            self.mining = None
            return
        if self.mining is None or self.mining.tile != tile:
            self.mining = Mining(tile)          # mirou outro tile: começa do zero
        # vira o player pro tile que está minerando
        self.player.face((tile[0] + 0.5) * C.TILE - self.player.x, (tile[1] + 0.5) * C.TILE - (self.player.y - 12))
        m = self.mining
        m.elapsed += dt
        if m.elapsed >= m.next_hit:
            self.events.append(("mine_hit", tile))
            m.next_hit += C.MINE_HIT_INTERVAL
        kind = self.world.get(*tile)
        if m.elapsed >= C.MINE_TIME[kind]:
            self._break_tile(tile, kind)

    def _break_tile(self, tile: tuple[int, int], kind: int) -> None:
        self.world.set(*tile, C.FLOOR)
        self.mining = None
        self.events.append(("break", tile, kind))
        resource = C.ORE_TILES.get(kind)
        if resource:
            amount = self.rng.randint(C.DROP_MIN, C.DROP_MAX)
            self.inventory[resource] += amount
            self.mined_total[resource] += amount
            self.events.append(("pickup", tile, resource, amount))

    # ---- oxigênio -----------------------------------------------------------
    def _update_o2(self, dt: float) -> None:
        inside = self.in_base_zone()
        if inside:
            if not self.was_in_base and self.o2 < C.O2_MAX:
                self.events.append(("refill",))
            self.o2 = min(C.O2_MAX, self.o2 + C.O2_REFILL * dt)
        else:
            self.o2 = max(0.0, self.o2 - C.O2_DRAIN * dt)
            if self.o2 <= 0:
                self._faint()
        self.was_in_base = inside

    def _faint(self) -> None:
        self.fainted = True
        self.faint_time = 0.0
        self.mining = None
        self.events.append(("faint",))

    def _update_faint(self, dt: float) -> None:
        before = self.faint_time
        self.faint_time += dt
        # No meio do fade preto: acorda na cápsula, com O₂ cheio e o inventário intacto.
        if before < C.FAINT_RESPAWN_AT <= self.faint_time:
            self.player.x, self.player.y = C.SPAWN_POS
            self.o2 = C.O2_MAX
            self.was_in_base = True
            self.events.append(("wake",))
        if self.faint_time >= C.FAINT_DURATION:
            self.fainted = False

    # ---- fabricador e máquinas ----------------------------------------------
    def recipe_status(self, kind: str) -> str:
        """'locked' (Ti insuficiente), 'missing' (falta recurso) ou 'ok'."""
        machine = C.MACHINES[kind]
        if self.ti < machine.unlock_ti:
            return "locked"
        if any(self.inventory[r] < n for r, n in machine.cost.items()):
            return "missing"
        return "ok"

    def missing_resource(self, kind: str) -> str | None:
        for r, n in C.MACHINES[kind].cost.items():
            if self.inventory[r] < n:
                return r
        return None

    def craft(self, kind: str) -> bool:
        if not self.in_base_zone() or self.recipe_status(kind) != "ok":
            return False
        for r, n in C.MACHINES[kind].cost.items():
            self.inventory[r] -= n
        self.machines_owned[kind] += 1
        self.events.append(("craft", kind))
        return True

    def can_place(self, kind: str, tile: tuple[int, int]) -> bool:
        tx, ty = tile
        if self.machines_owned.get(kind, 0) <= 0:
            return False
        if self.world.get(tx, ty) != C.FLOOR or tile in C.POD_TILES or self.machine_at(tile):
            return False
        px, py = self.player.tile
        if tile == (px, py) or max(abs(tx - px), abs(ty - py)) > C.PLACE_REACH:
            return False
        # não pode prender o player dentro da máquina
        return not overlaps(self.player.box, Machine(kind, tx, ty).rect)

    def place(self, kind: str, tile: tuple[int, int], rotation: int = 0) -> bool:
        if not self.can_place(kind, tile):
            return False
        self.machines.append(Machine(kind, tile[0], tile[1], rotation))
        self.machines_owned[kind] -= 1
        self.events.append(("place", kind, tile))
        return True

    def _update_machines(self, dt: float) -> None:
        for m in self.machines:
            self.indices[m.type.index] += m.type.rate * dt
        self._check_stage()

    def _check_stage(self) -> None:
        new_stage = stage_for_ti(self.ti)
        if new_stage > self.stage:          # estágio nunca volta
            self.stage = new_stage
            self.events.append(("stage_up", new_stage))

    # ---- terminais ----------------------------------------------------------
    def nearby_terminal(self) -> int | None:
        for i, (tx, ty) in enumerate(self.world.terminals):
            bx, by = (tx + 0.5) * C.TILE, (ty + 1) * C.TILE    # base do terminal (onde a parede encosta no chão)
            if math.hypot(self.player.x - bx, self.player.y - by) <= C.TERMINAL_REACH:
                return i
        return None

    def read_terminal(self, index: int) -> str:
        self.logs_read.add(index)
        self.events.append(("terminal", index))
        return C.LOGS[index]

    # ---- debug --------------------------------------------------------------
    def debug_add_ti(self, amount: float = C.DEBUG_TI_BONUS) -> None:
        # Divide em partes inteiras (3334 + 3333 + 3333) pra soma fechar exata.
        share = int(amount) // 3
        self.indices["o2"] += int(amount) - 2 * share
        self.indices["heat"] += share
        self.indices["water"] += share
        self._check_stage()

    def toggle_time_scale(self) -> None:
        self.time_scale = C.DEBUG_TIME_SCALE if self.time_scale == 1 else 1

    def pop_events(self) -> list[tuple]:
        events, self.events = self.events, []
        return events
