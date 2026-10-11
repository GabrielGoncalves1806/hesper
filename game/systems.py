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
from game.inventory import Inventory
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
    tx: int              # tile de cima à esquerda (máquina comum ocupa 1 tile; a drill, 2×2)
    ty: int
    rotation: int = 0    # 0..3, só cosmético
    # só a drill usa estes três:
    resource: str | None = None   # minério do veio embaixo dela
    stored: int = 0               # quanto já extraiu e está esperando coleta
    timer: float = 0.0            # segundos acumulados pra próxima unidade
    # só o baú usa este: os 24 slots dele (criado no place)
    storage: Inventory | None = None

    @property
    def type(self) -> C.MachineType:
        return C.MACHINES[self.kind]

    @property
    def size(self) -> int:
        return self.type.size

    @property
    def is_drill(self) -> bool:
        return self.kind == "drill"

    @property
    def is_chest(self) -> bool:
        return self.kind == "chest"

    @property
    def full(self) -> bool:
        return self.is_drill and self.stored >= C.DRILL_CAPACITY

    @property
    def tiles(self) -> list[tuple[int, int]]:
        return [(self.tx + dx, self.ty + dy) for dy in range(self.size) for dx in range(self.size)]

    @property
    def anchor(self) -> tuple[float, float]:
        """Centro da base (pixels do mundo): onde o sprite fica "em pé"."""
        return (self.tx + self.size / 2) * C.TILE, (self.ty + self.size) * C.TILE

    @property
    def rect(self) -> Rect:
        """Caixa de colisão (só a base, no chão)."""
        if self.size > 1:
            return (self.tx * C.TILE + 4, self.ty * C.TILE + 20, self.size * C.TILE - 8, self.size * C.TILE - 20)
        return (self.tx * C.TILE + 4, self.ty * C.TILE + 14, C.TILE - 8, C.TILE - 14)

    @property
    def sprite_rect(self) -> Rect:
        """Área que a máquina ocupa na tela (âncora: centro da base). Usada pelo mouse."""
        if self.is_drill:
            w, h = C.DRILL_SPRITE_SIZE
        elif self.is_chest:
            w, h = C.CHEST_SPRITE_SIZE
        else:
            w, h = C.MACHINE_SPRITE_SIZE[2 if self.kind.endswith("_t2") else 1]
        ax, ay = self.anchor
        return (ax - w / 2, ay - h, w, h)


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
    """Estimativa de tempo até o próximo estágio NO RITMO ATUAL, ou um aviso se nada produz Ti.

    É só "falta ÷ taxa de agora". Como a taxa cresce o jogo todo (mais máquinas), o tempo real
    costuma ser bem menor; por isso o texto avisa "(ritmo atual)" em vez de tentar prever.
    """
    if rate_per_second <= 1e-6:
        return "coloque máquinas"
    return f"{format_eta(remaining / rate_per_second)} (ritmo atual)"


def smooth_rate(previous: float, target: float, dt: float, tau: float = C.RATE_SMOOTHING) -> float:
    """Média móvel exponencial: anda em direção ao alvo sem pular (tau = 'memória' em segundos)."""
    return previous + (target - previous) * (1 - math.exp(-dt / tau))


class GameState:
    def __init__(self, seed: int = C.WORLD_SEED, rng: random.Random | None = None):
        self.world = World.generate(seed)
        self.rng = rng or random.Random()
        self.player = Player(*C.SPAWN_POS)
        # mochila com slots (game/inventory.py): recursos E máquinas fabricadas ainda não colocadas.
        # A hotbar são os slots 0 a 7 (a primeira linha).
        self.inventory = Inventory(C.INVENTORY_SLOTS)
        self.machines: list[Machine] = []                  # colocadas no mundo
        # Tiles onde já existiu máquina: fontes da mancha de transição (game/transition.py).
        # Só cresce: desmontar a máquina NÃO tira daqui, senão a terra em volta "desconverteria".
        self.transition_sources: set[tuple[int, int]] = set()
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
        self.drills_placed = 0                         # quantas vezes já colocou uma drill (só cresce)
        self.drill_collected = {r: 0 for r in C.RESOURCES}   # total já coletado de drills (só cresce)
        self.crafted = {k: 0 for k in C.MACHINES}            # quantas de cada já fabricou (só cresce)
        self.events: list[tuple] = []

    # ---- consultas ----------------------------------------------------------
    @property
    def ti(self) -> float:
        """Índice de terraformação = O₂ + Calor + Água."""
        return sum(self.indices.values())

    @property
    def ti_rate(self) -> float:
        return sum(m.type.rate for m in self.machines)

    @property
    def drills(self) -> list[Machine]:
        return [m for m in self.machines if m.is_drill]

    def dist_to_base(self) -> float:
        return math.hypot(self.player.x - C.BASE_CENTER[0], self.player.y - C.BASE_CENTER[1])

    def in_base_zone(self) -> bool:
        return self.dist_to_base() <= C.BASE_RADIUS

    def machine_at(self, tile: tuple[int, int]) -> Machine | None:
        """Máquina que ocupa esse tile (a drill ocupa 4)."""
        for m in self.machines:
            if tile in m.tiles:
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
            got = amount - self.inventory.add(resource, amount)   # cheio: o tile quebra, o minério se perde
            if got:
                self.mined_total[resource] += got
                self.events.append(("pickup", tile, resource, got))
            if got < amount:
                self.events.append(("inv_full",))

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
    @property
    def chests(self) -> list[Machine]:
        return [m for m in self.machines if m.is_chest]

    def base_chests(self) -> list[Machine]:
        """Baús dentro da zona de O₂ da base: o fabricador também puxa recurso deles."""
        return [c for c in self.chests
                if math.hypot(c.anchor[0] - C.BASE_CENTER[0], c.anchor[1] - C.BASE_CENTER[1]) <= C.BASE_RADIUS]

    def available(self, resource: str) -> int:
        """Quanto o fabricador enxerga desse recurso: inventário + baús da base."""
        return self.inventory.count(resource) + sum(c.storage.count(resource) for c in self.base_chests())

    def recipe_status(self, kind: str) -> str:
        """'locked' (Ti insuficiente), 'missing' (falta recurso) ou 'ok'."""
        machine = C.MACHINES[kind]
        if self.ti < machine.unlock_ti:
            return "locked"
        if any(self.available(r) < n for r, n in machine.cost.items()):
            return "missing"
        return "ok"

    def missing_resource(self, kind: str) -> str | None:
        for r, n in C.MACHINES[kind].cost.items():
            if self.available(r) < n:
                return r
        return None

    def craft(self, kind: str) -> bool:
        """Fabrica 1 máquina: gasta primeiro o que está no inventário, depois o dos baús da base.
        A máquina vira um item no inventário (falha com aviso se não couber)."""
        if not self.in_base_zone() or self.recipe_status(kind) != "ok":
            return False
        cost = C.MACHINES[kind].cost
        # "e se eu gastar o que vem do inventário, sobra lugar pra máquina?" (testa numa cópia)
        trial = self.inventory.copy()
        for r, n in cost.items():
            trial.remove(r, n)
        if not trial.has_space(kind):
            self.events.append(("inv_full",))
            return False
        for r, n in cost.items():
            left = n - self.inventory.remove(r, n)
            for chest in self.base_chests():
                if left <= 0:
                    break
                left -= chest.storage.remove(r, left)
        self.inventory.add(kind, 1)
        self.crafted[kind] += 1
        self.events.append(("craft", kind))
        return True

    def can_place(self, kind: str, tile: tuple[int, int]) -> bool:
        """Máquina comum: 1 tile de chão livre fora de veio. Drill: `tile` tem que ser o canto
        de cima à esquerda de um veio livre (o App "gruda" o fantasma no veio debaixo do mouse)."""
        tx, ty = tile
        if self.inventory.count(kind) <= 0:     # precisa ter a máquina (item) no inventário
            return False
        machine = Machine(kind, tx, ty)
        vein = self.world.vein_at(tx, ty)
        if kind == "drill":
            if vein is None or (vein.tx, vein.ty) != tile:
                return False
        elif vein is not None:            # veio fica livre pra drill
            return False
        for t in machine.tiles:
            if self.world.get(*t) != C.FLOOR or t in C.POD_TILES or self.machine_at(t):
                return False
        px, py = self.player.tile
        if (px, py) in machine.tiles:
            return False
        if min(max(abs(x - px), abs(y - py)) for x, y in machine.tiles) > C.PLACE_REACH:
            return False
        # não pode prender o player dentro da máquina
        return not overlaps(self.player.box, machine.rect)

    def place(self, kind: str, tile: tuple[int, int], rotation: int = 0, slot: int | None = None) -> bool:
        """Coloca a máquina e gasta 1 item dela. `slot` = de qual slot sai (o da hotbar selecionado);
        sem `slot`, sai de qualquer pilha dessa máquina."""
        if not self.can_place(kind, tile):
            return False
        stack = self.inventory.slots[slot] if slot is not None else None
        if slot is not None and (stack is None or stack.item != kind):
            return False
        machine = Machine(kind, tile[0], tile[1], rotation)
        if machine.is_drill:
            machine.resource = self.world.vein_at(*tile).resource
            self.drills_placed += 1
        if machine.is_chest:
            machine.storage = Inventory(C.CHEST_SLOTS)
        self.machines.append(machine)
        self.transition_sources.add(tuple(tile))
        if slot is not None:
            self.inventory.remove_from_slot(slot, 1)
        else:
            self.inventory.remove(kind, 1)
        self.events.append(("place", kind, tile))
        return True

    # ---- drill automática ---------------------------------------------------
    def drill_distance(self, drill: Machine) -> float:
        """Distância (px) dos pés do player até a base da drill."""
        ax, ay = drill.anchor
        return math.hypot(self.player.x - ax, self.player.y - (ay - C.TILE / 2))

    def nearby_drill(self) -> Machine | None:
        """Drill ao alcance do E (a mais perto)."""
        near = [d for d in self.drills if self.drill_distance(d) <= C.DRILL_REACH]
        return min(near, key=self.drill_distance, default=None)

    def terminal_distance(self, index: int) -> float:
        tx, ty = self.world.terminals[index]
        return math.hypot(self.player.x - (tx + 0.5) * C.TILE, self.player.y - (ty + 1) * C.TILE)

    def nearby_chest(self) -> Machine | None:
        """Baú ao alcance do E (o mais perto). A distância é medida igual à da drill: até a base."""
        near = [c for c in self.chests if self.drill_distance(c) <= C.CHEST_REACH]
        return min(near, key=self.drill_distance, default=None)

    def interaction(self) -> tuple[str, object] | None:
        """O que o E faz aqui: ("terminal", índice), ("drill", máquina) ou ("chest", máquina),
        o que estiver mais perto."""
        options = []
        terminal = self.nearby_terminal()
        if terminal is not None:
            options.append((self.terminal_distance(terminal), "terminal", terminal))
        drill = self.nearby_drill()
        if drill is not None:
            options.append((self.drill_distance(drill), "drill", drill))
        chest = self.nearby_chest()
        if chest is not None:
            options.append((self.drill_distance(chest), "chest", chest))
        if not options:
            return None
        _, kind, target = min(options, key=lambda o: o[0])
        return kind, target

    def collect(self, drill: Machine) -> int:
        """Leva o que a drill guardou pro inventário (o que não couber fica nela). Devolve quanto coletou."""
        if drill.stored <= 0:
            return 0
        left = self.inventory.add(drill.resource, drill.stored)
        amount = drill.stored - left
        drill.stored = left
        if left:
            self.events.append(("inv_full",))
        if amount <= 0:
            return 0
        self.drill_collected[drill.resource] += amount
        self.events.append(("drill_collect", drill.resource, amount, drill.anchor))
        return amount

    def _update_drill(self, drill: Machine, dt: float) -> None:
        if drill.full:
            return
        drill.timer += dt
        while drill.timer >= C.DRILL_INTERVAL and not drill.full:
            drill.timer -= C.DRILL_INTERVAL
            drill.stored += 1
            if drill.full:
                drill.timer = 0.0
                self.events.append(("drill_full", drill.anchor))

    def machine_at_point(self, px: float, py: float) -> Machine | None:
        """Máquina desenhada no pixel (px, py) do mundo. Se duas se sobrepõem, a da frente (mais embaixo) ganha."""
        hits = [m for m in self.machines if overlaps(m.sprite_rect, (px, py, 1, 1))]
        return max(hits, key=lambda m: m.ty, default=None)

    def can_dismantle(self, machine: Machine) -> bool:
        px, py = self.player.tile
        return machine in self.machines and max(abs(machine.tx - px), abs(machine.ty - py)) <= C.PLACE_REACH

    def dismantle(self, machine: Machine) -> bool:
        """Tira a máquina do mapa e devolve ela como item pro inventário.
        Não desmonta (e avisa) se: o baú tem coisa dentro, ou não cabe no inventário.
        Drill: o que ela guardou vai antes pro inventário; se não couber tudo, o resto fica nela
        e ela continua no lugar. A cápsula não é uma Machine, então nunca entra aqui."""
        if not self.can_dismantle(machine):
            return False
        if machine.is_chest and not machine.storage.is_empty():
            self.events.append(("chest_not_empty",))
            return False
        if machine.is_drill and machine.stored:      # o que a drill guardou vai pro inventário
            self.collect(machine)
            if machine.stored:                       # não coube tudo: a drill fica (o collect já avisou)
                return False
        if not self.inventory.has_space(machine.kind):
            self.events.append(("inv_full",))
            return False
        self.machines.remove(machine)
        self.inventory.add(machine.kind, 1)
        self.events.append(("dismantle", machine.kind, (machine.tx, machine.ty)))
        return True

    def _update_machines(self, dt: float) -> None:
        for m in self.machines:
            if m.is_drill:
                self._update_drill(m, dt)
            elif m.type.index is not None:           # o baú não soma índice nenhum
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
