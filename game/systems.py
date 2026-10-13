"""As regras do jogo: mineração, O₂, fabricador, máquinas, Ti e estágios.

Tudo aqui é Python puro (nada de pygame). O `App` (app.py) lê o teclado/mouse,
traduz isso num `Controls` e chama `GameState.update(dt, controls)` a cada frame.
O estado avisa o que aconteceu (pra tocar som, mostrar texto flutuante etc.)
através da lista `events`, que o App esvazia com `pop_events()`.
"""

import dataclasses
import math
import random
from dataclasses import dataclass, field

from game import config as C
from game import drones
from game import explore
from game import layers
from game.equipment import Equipment, is_equipment
from game.inventory import Inventory
from game.energy import PowerAlert, PowerReport, power_report
from game.layers import CAVE, SURFACE, Layer
from game.player import Player, Rect, overlaps
from game.world import World
from game.wrecks import Crate, Wreck


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
    # só a drill usa estes dois:
    resource: str | None = None   # minério do veio embaixo dela
    timer: float = 0.0            # segundos acumulados pra próxima unidade
    # baú e drill: o inventário (baú 24 slots; drill 1 slot só do minério dela, até DRILL_CAPACITY).
    # Criado sozinho no __post_init__ se ninguém passar.
    storage: Inventory | None = None
    name: str | None = None       # só o baú: o nome que o jogador deu
    # baú e drill: logística dos drones (game/drones.py). O player guarda/tira qualquer coisa à mão.
    sends: set[str] = field(default_factory=set)      # Envia: itens que os drones podem tirar daqui
    receives: set[str] = field(default_factory=set)   # Recebe: itens que os drones trazem pra cá
    batch: int = C.DRONE_BATCH_DEFAULT                # Lote: quanto um drone tira daqui por viagem
    # só a estação de drones usa este: drones + sobras do buffer antigo (game/drones.py, criado no place)
    station: drones.Station | None = None
    stored_init: dataclasses.InitVar[int] = 0         # atalho pros testes: Machine("drill", ..., stored_init=8)

    def __post_init__(self, stored_init: int = 0) -> None:
        if self.storage is None and self.is_drill:
            self.storage = Inventory(C.DRILL_SLOTS)
        elif self.storage is None and self.is_chest:
            self.storage = Inventory(C.CHEST_SLOTS)
        if stored_init:
            self.stored = stored_init

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
    def is_station(self) -> bool:
        return self.kind == "drone_station"

    @property
    def is_lamp(self) -> bool:
        return self.kind in C.LAMP_RADIUS          # luminária comum e a forte (Marco 3)

    @property
    def is_logistic(self) -> bool:
        """Baú e drill: têm inventário que os drones atendem (Envia/Recebe/Lote)."""
        return self.is_chest or self.is_drill

    @property
    def stored(self) -> int:
        """Drill: quanto do minério dela está guardado (o inventário de 1 slot)."""
        return self.storage.count(self.resource) if self.is_drill and self.storage is not None else 0

    @stored.setter
    def stored(self, amount: int) -> None:
        """Drill: troca o conteúdo por `amount` do minério dela (testes, save antigo)."""
        self.storage.clear()
        if amount > 0:
            self.storage.add(self.resource, amount)

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
        if self.is_lamp:                       # poste fino: só o pé bloqueia
            return (self.tx * C.TILE + 10, self.ty * C.TILE + 20, 12, 12)
        return (self.tx * C.TILE + 4, self.ty * C.TILE + 14, C.TILE - 8, C.TILE - 14)

    @property
    def sprite_rect(self) -> Rect:
        """Área que a máquina ocupa na tela (âncora: centro da base). Usada pelo mouse."""
        if self.is_drill:
            w, h = C.DRILL_SPRITE_SIZE
        elif self.is_chest:
            w, h = C.CHEST_SPRITE_SIZE
        elif self.is_station:
            w, h = C.DRONE_STATION_SPRITE_SIZE
        elif self.is_lamp:
            w, h = C.LAMP_SPRITE_SIZE
        else:
            w, h = C.MACHINE_SPRITE_SIZE[2 if self.kind.endswith("_t2") else 1]
        ax, ay = self.anchor
        return (ax - w / 2, ay - h, w, h)


@dataclass
class RampTrip:
    """Viagem pela rampa (fade): no RAMP_SWITCH_AT troca de camada, no RAMP_DURATION acaba."""
    to: str              # camada de destino
    time: float = 0.0
    switched: bool = False


@dataclass
class Mining:
    tile: tuple[int, int]
    elapsed: float = 0.0
    next_hit: float = 0.0

    def progress(self, kind: int) -> float:
        return min(1.0, self.elapsed / C.MINE_TIME[kind])


POD_RECT: Rect = (C.POD_TILES[0][0] * C.TILE + 4, C.POD_TILES[0][1] * C.TILE + 12, 2 * C.TILE - 8, C.TILE - 12)


def clean_chest_name(text: str) -> str:
    """Nome de baú válido: sem quebra de linha nem caractere de controle, sem espaço nas pontas,
    até C.CHEST_NAME_MAX caracteres. Vazio vira o nome padrão ("Baú")."""
    text = "".join(ch for ch in str(text) if ch.isprintable()).strip()[:C.CHEST_NAME_MAX].strip()
    return text or C.CHEST_DEFAULT_NAME


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
        # Camadas (game/layers.py): cada uma com o próprio mapa e máquinas. O jogo começa na
        # superfície; `world` e `machines` sempre apontam pra camada ATIVA.
        self.seed = seed
        self.layers: dict[str, Layer] = {SURFACE: layers.make_surface(seed)}
        self.layer = SURFACE
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
        self.logs_seen: set[int] = set()   # LOGs já abertos pela aba LOGs do inventário (os outros lidos = "NOVO")
        self.was_in_base = True
        self.smoothed_rate = 0.0       # taxa de Ti por segundo (real), suavizada pra estimativa do HUD
        # pros objetivos (objectives.py): total já minerado (craftar não desconta) e se já abriu o fabricador
        self.mined_total = {r: 0 for r in C.RESOURCES}
        self.fabricator_opened = False
        self.drills_placed = 0                         # quantas vezes já colocou uma drill (só cresce)
        self.drill_collected = {r: 0 for r in C.RESOURCES}   # total já coletado de drills (só cresce)
        self.crafted = {k: 0 for k in C.MACHINES}            # quantas de cada já fabricou (só cresce)
        self.drone_deliveries = 0                      # entregas feitas por drones (só cresce)
        self.drones_docked = 0                         # drones já colocados numa estação (só cresce)
        self.power_alert = PowerAlert()                # quando tocar o power_low (game/energy.py)
        self.ramp: RampTrip | None = None              # descendo/subindo pela rampa (o fade está rolando)
        self.lamps_placed = 0                          # luminárias já colocadas (só cresce, pros objetivos)
        # Marco 3: projetos achados (liberam receitas), equipamento do traje, destroços visitados e explorado
        self.blueprints: set[str] = set()
        self.equipment = Equipment()
        self.equipped_ever: set[str] = set()           # equipamento que já foi encaixado alguma vez (objetivos)
        self.wrecks_visited: set[int] = set()          # rank dos destroços que o player já chegou perto
        self.explore_timer = 0.0                       # o explorado atualiza a cada EXPLORE_INTERVAL
        self.events: list[tuple] = []

    # ---- camadas --------------------------------------------------------------
    @property
    def active(self) -> Layer:
        return self.layers[self.layer]

    @property
    def surface(self) -> Layer:
        return self.layers[SURFACE]

    @property
    def world(self) -> World:
        return self.active.world

    @world.setter
    def world(self, value: World) -> None:
        self.active.world = value

    @property
    def machines(self) -> list:
        """Máquinas da camada ativa (a lista de verdade: dá pra dar append)."""
        return self.active.machines

    @machines.setter
    def machines(self, value: list) -> None:
        self.active.machines = value

    @property
    def all_machines(self) -> list:
        """Máquinas de todas as camadas (energia, Ti e produção são globais)."""
        return [m for key in layers.ORDER if key in self.layers for m in self.layers[key].machines]

    def enter_layer(self, key: str, pos: tuple[float, float] | None = None) -> None:
        """Troca a camada ativa (cria a caverna na primeira vez). `pos` = onde o player aparece."""
        if key not in self.layers:
            self.layers[key] = layers.MAKERS[key](self.seed)
        self.layer = key
        self.mining = None
        if pos is not None:
            self.player.x, self.player.y = pos
        self.explore_timer = 0.0                       # chegou: marca o que vê já no próximo frame

    # ---- rampa (Marco 2): cratera da superfície <-> rampa de subida da caverna --------
    def ramp_distance(self) -> float:
        """Distância (px) dos pés até o meio da borda de baixo da rampa desta camada (inf sem rampa)."""
        if self.world.crater is None:
            return math.inf
        mx, my = layers.ramp_mouth(self.world)
        return math.hypot(self.player.x - mx, self.player.y - my)

    def start_ramp(self) -> bool:
        """E na rampa (no alcance): começa o fade. A troca de camada acontece no meio dele."""
        if self.ramp is not None or self.fainted or self.ramp_distance() > C.RAMP_REACH:
            return False
        self.ramp = RampTrip(layers.other_layer(self.layer))
        self.mining = None
        self.events.append(("ramp", self.ramp.to))
        return True

    def _update_ramp(self, dt: float) -> None:
        trip = self.ramp
        trip.time += dt
        if not trip.switched and trip.time >= C.RAMP_SWITCH_AT:
            trip.switched = True
            if trip.to not in self.layers:
                self.layers[trip.to] = layers.MAKERS[trip.to](self.seed)
            self.enter_layer(trip.to, layers.ramp_arrival(self.layers[trip.to].world))
            self.events.append(("layer", trip.to))
        if trip.time >= C.RAMP_DURATION:
            self.ramp = None

    def safe_point(self) -> tuple[float, float, str]:
        """Pra onde a seta do O₂ crítico aponta: a base (superfície) ou a rampa de subida (caverna)."""
        if self.active.has_base or self.world.crater is None:
            return C.BASE_CENTER[0], C.BASE_CENTER[1], "BASE"
        return (*layers.ramp_mouth(self.world), "RAMPA")

    # ---- consultas ----------------------------------------------------------
    @property
    def ti(self) -> float:
        """Índice de terraformação = O₂ + Calor + Água."""
        return sum(self.indices.values())

    @property
    def ti_rate(self) -> float:
        """Ti por segundo, já com o ritmo da energia (no déficit, todas rendem menos)."""
        return sum(m.type.rate for m in self.all_machines) * self.power.factor

    @property
    def power(self) -> PowerReport:
        """Energia agora: produção, consumo e o fator (ritmo) de todas as máquinas. Ver game/energy.py."""
        return power_report(m.kind for m in self.all_machines)

    @property
    def drills(self) -> list[Machine]:
        return [m for m in self.machines if m.is_drill]

    @property
    def stations(self) -> list[Machine]:
        return [m for m in self.machines if m.is_station]

    @property
    def logistics(self) -> list[Machine]:
        """Baús e drills da camada ativa."""
        return [m for m in self.machines if m.is_logistic]

    def drone_logistics(self) -> list[Machine]:
        """Baús e drills que os drones atendem: o mapa inteiro, mas só da superfície (v0.3)."""
        return [m for m in self.surface.machines if m.is_logistic]

    def dist_to_base(self) -> float:
        return math.hypot(self.player.x - C.BASE_CENTER[0], self.player.y - C.BASE_CENTER[1])

    def in_base_zone(self) -> bool:
        """Na zona de O₂ da cápsula (só existe na superfície)."""
        return self.active.has_base and self.dist_to_base() <= C.BASE_RADIUS

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
        if self.active.has_base:
            solids.append(POD_RECT)
        return solids

    # ---- loop principal -----------------------------------------------------
    def update(self, dt: float, controls: Controls) -> None:
        dt = min(dt, C.MAX_DT)
        self.play_time += dt
        sim_dt = dt * self.time_scale     # O₂ e máquinas andam mais rápido com F1

        if self.fainted:
            self.ramp = None                  # desmaiou no meio do fade: acorda na cápsula, sem viagem
            self._update_faint(dt)
        elif self.ramp is not None:           # descendo/subindo: parado, só o O₂ continua
            self._update_ramp(dt)
            self._update_o2(sim_dt)
        else:
            self.player.move(controls.move_x, controls.move_y, dt, self.solids_near)
            self._update_mining(dt, controls.mine_tile)
            self._update_o2(sim_dt)
        self._update_machines(sim_dt)
        self._update_rocks(sim_dt)
        self._update_explore(dt)
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
        self.world.set(*tile, self.world.floor_kind)       # no deserto vira areia
        self.mining = None
        self.events.append(("break", tile, kind))
        resource = C.TILE_RESOURCE.get(kind)                # minério de parede (1–2) ou rocha pequena (2–4)
        if resource:
            amount = self.rng.randint(*C.DROP_RANGE.get(kind, (C.DROP_MIN, C.DROP_MAX)))
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
            if not self.was_in_base and self.o2 < self.o2_max:
                self.events.append(("refill",))
            self.o2 = min(self.o2_max, self.o2 + C.O2_REFILL * dt)
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
            self.enter_layer(SURFACE, C.SPAWN_POS)          # desmaiou na caverna: acorda na cápsula, lá em cima
            self.o2 = self.o2_max
            self.was_in_base = True
            self.events.append(("wake",))
        if self.faint_time >= C.FAINT_DURATION:
            self.fainted = False

    # ---- fabricador e máquinas ----------------------------------------------
    @property
    def chests(self) -> list[Machine]:
        return [m for m in self.machines if m.is_chest]

    def base_chests(self) -> list[Machine]:
        """Baús dentro da zona de O₂ da base (superfície): o fabricador também puxa recurso deles."""
        return [c for c in self.surface.machines if c.is_chest
                and math.hypot(c.anchor[0] - C.BASE_CENTER[0], c.anchor[1] - C.BASE_CENTER[1]) <= C.BASE_RADIUS]

    def available(self, resource: str) -> int:
        """Quanto o fabricador enxerga desse recurso: inventário + baús da base."""
        return self.inventory.count(resource) + sum(c.storage.count(resource) for c in self.base_chests())

    def recipe_status(self, kind: str) -> str:
        """'blueprint' (projeto não encontrado), 'locked' (Ti insuficiente), 'missing' (falta recurso) ou 'ok'."""
        machine = C.MACHINES[kind]
        blueprint = C.RECIPE_BLUEPRINT.get(kind)
        if blueprint is not None and blueprint not in self.blueprints:
            return "blueprint"
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

    def craft_many(self, kind: str, limit: int = C.CRAFT_BATCH) -> int:
        """Fabrica até `limit` de uma vez (Shift no fabricador). Para no primeiro que falhar (faltou
        recurso ou não cabe no inventário). Devolve quantas fabricou; o evento "craft" sai uma vez só
        (um som), com a quantidade."""
        made = 0
        while made < limit and self.craft(kind):
            made += 1
        if made > 1:
            crafts = [e for e in self.events if e[0] == "craft" and e[1] == kind]
            for e in crafts[:-1]:
                self.events.remove(e)
            self.events[self.events.index(crafts[-1])] = ("craft", kind, made)
        return made

    def can_place(self, kind: str, tile: tuple[int, int]) -> bool:
        """Máquina comum: 1 tile de chão livre fora de veio. Drill: `tile` tem que ser o canto
        de cima à esquerda de um veio livre (o App "gruda" o fantasma no veio debaixo do mouse)."""
        tx, ty = tile
        if not C.MACHINES[kind].placeable:      # o drone é item, mas vai na estação, não no chão
            return False
        if kind == "drone_station" and not self.active.has_base:   # drones só atendem a superfície (v0.3)
            return False
        if self.inventory.count(kind) <= 0:     # precisa ter a máquina (item) no inventário
            return False
        machine = Machine(kind, tx, ty)
        vein = self.world.vein_at(tx, ty)
        if kind == "drill":
            if vein is None or (vein.tx, vein.ty) != tile:
                return False
        elif any(self.world.vein_at(*t) for t in machine.tiles):   # veio fica livre pra drill
            return False
        pod = C.POD_TILES if self.active.has_base else ()
        for t in machine.tiles:
            if not self.world.is_floor(*t) or t in pod or self.machine_at(t):
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
        if machine.is_drill:                                   # vem com Envia/Recebe vazios: o player configura
            machine.resource = self.world.vein_at(*tile).resource
            self.drills_placed += 1
        if machine.is_chest:
            machine.name = C.CHEST_DEFAULT_NAME
        if machine.is_station:
            machine.station = drones.new_station(machine)      # vem vazia: os drones vão pelo painel (E)
        if machine.is_lamp:
            self.lamps_placed += 1
        self.machines.append(machine)
        if self.active.has_base:                               # a caverna não muda com o Ti
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

    def nearby_station(self) -> Machine | None:
        """Estação de drones ao alcance do E (abre o painel dela: drones e buffer)."""
        near = [m for m in self.stations if self.drill_distance(m) <= C.STATION_REACH]
        return min(near, key=self.drill_distance, default=None)

    def interactable_at(self, px: float, py: float) -> tuple[str, object] | None:
        """O que dá pra abrir com E debaixo do pixel (px, py) do mundo: ("drill"/"chest"/"station",
        máquina) ou ("terminal", índice). Sem checar alcance (isso é com o `in_reach`)."""
        machine = self.machine_at_point(px, py)
        if machine is not None:
            for kind, flag in (("drill", machine.is_drill), ("chest", machine.is_chest),
                               ("station", machine.is_station)):
                if flag:
                    return kind, machine
            return None                                  # O2, aquecedor...: o E não abre nada
        tiles = {self.world.visual_tile_at(px, py), (int(px // C.TILE), int(py // C.TILE))}
        for tile in tiles:                               # destroço: a caixa ou o terminal do módulo
            crate = self.crates.get(tile)
            if crate is not None:
                return "crate", crate
            wreck = self.world.wreck_at(*tile)
            if wreck is not None and wreck.terminal == tile:
                return "wreck_log", wreck
        for i, tile in enumerate(self.world.terminals):
            if tuple(tile) in tiles:
                return "terminal", i
        if self.world.crater is not None and tiles & set(layers.ramp_tiles(self.world)):
            return "ramp", tuple(self.world.crater)
        return None

    def in_reach(self, kind: str, target) -> bool:
        """O alvo está no alcance do E? (mesmas distâncias do "mais perto")"""
        if kind == "terminal":
            return self.terminal_distance(target) <= C.TERMINAL_REACH
        if kind == "ramp":
            return self.ramp_distance() <= C.RAMP_REACH
        if kind == "crate":
            return self.crates.get(target.tile) is target and self.crate_distance(target) <= C.CRATE_REACH
        if kind == "wreck_log":
            return target in self.world.wrecks and self.wreck_terminal_distance(target) <= C.TERMINAL_REACH
        reach = {"drill": C.DRILL_REACH, "chest": C.CHEST_REACH, "station": C.STATION_REACH}[kind]
        return any(m is target for m in self.machines) and self.drill_distance(target) <= reach

    def interaction(self, hover: tuple[str, object] | None = None) -> tuple[str, object] | None:
        """O que o E faz aqui: ("terminal", índice), ("drill", máquina), ("chest", máquina) ou
        ("station", máquina). Se `hover` (o que está debaixo do mouse, de `interactable_at`) estiver no
        alcance, é ele; senão, o que estiver mais perto do player."""
        if hover is not None and self.in_reach(*hover):
            return hover
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
        station = self.nearby_station()
        if station is not None:
            options.append((self.drill_distance(station), "station", station))
        crate = self.nearby_crate()
        if crate is not None:
            options.append((self.crate_distance(crate), "crate", crate))
        wreck = self.nearby_wreck_terminal()
        if wreck is not None:
            options.append((self.wreck_terminal_distance(wreck), "wreck_log", wreck))
        if self.ramp_distance() <= C.RAMP_REACH:
            options.append((self.ramp_distance(), "ramp", tuple(self.world.crater)))
        if not options:
            return None
        _, kind, target = min(options, key=lambda o: o[0])
        return kind, target

    def collect(self, drill: Machine) -> int:
        """Leva tudo que a drill guardou pro inventário (Shift+E, "Pegar tudo", desmontar). O que não
        couber fica nela. Devolve quanto coletou."""
        return self.drill_take(drill)

    def drill_take(self, drill: Machine, index: int | None = None, amount: int | None = None) -> int:
        """Tira do inventário da drill pro do player: tudo (`index` None) ou o slot `index` (`amount`
        None = a pilha inteira, 1 = clique direito). Conta pro objetivo e avisa se não coube."""
        if drill.stored <= 0:
            return 0
        resource, before = drill.resource, drill.stored
        if index is None:
            drill.storage.transfer_all(self.inventory)
            want = before
        else:
            stack = drill.storage.slots[index]
            want = 0 if stack is None else stack.count if amount is None else min(amount, stack.count)
            drill.storage.transfer(index, self.inventory, amount)
        moved = before - drill.stored
        if moved < want:
            self.events.append(("inv_full",))
        if moved <= 0:
            return 0
        self.drill_collected[resource] += moved
        self.events.append(("drill_collect", resource, moved, drill.anchor))
        return moved

    def collect_station(self, machine: Machine) -> int:
        """Leva as sobras do buffer antigo da estação pro inventário (o que não couber fica nela). Devolve quanto coletou."""
        buffer = machine.station.buffer
        total = 0
        for resource in list(buffer):
            amount = buffer[resource] - self.inventory.add(resource, buffer[resource])
            buffer[resource] -= amount
            if buffer[resource] == 0:
                del buffer[resource]
            if amount:
                total += amount
                self.events.append(("station_collect", resource, amount, machine.anchor))
        if buffer:
            self.events.append(("inv_full",))
        return total

    # ---- baú: nome ----------------------------------------------------------------
    def rename_chest(self, chest: Machine, text: str) -> str:
        """Troca o nome do baú (limpo por clean_chest_name). Devolve o nome que ficou."""
        chest.name = clean_chest_name(text)
        return chest.name

    def chests_showing_name(self) -> list[Machine]:
        """Baús no alcance do E: o nome deles flutua em cima (o do mouse o App acrescenta)."""
        return [c for c in self.chests if self.drill_distance(c) <= C.CHEST_REACH]

    # ---- estação: painel (slots de drone e buffer) -----------------------------------
    def station_dock(self, machine: Machine, index: int, amount: int | None = None) -> int:
        """Põe drones do slot `index` do inventário na estação: `amount` (None = quantos couberem
        nos slots livres). Só aceita o item drone. Devolve quantos entraram."""
        stack = self.inventory.slots[index]
        if stack is None or stack.item != "drone":
            return 0
        want = stack.count if amount is None else min(amount, stack.count)
        placed = 0
        while placed < want and drones.dock(machine, machine.station) is not None:
            placed += 1
        self.inventory.remove_from_slot(index, placed)
        if placed:
            self.drones_docked += placed
            self.events.append(("drone_dock", placed))
        return placed

    def station_undock(self, machine: Machine, slot: int) -> bool:
        """Tira o drone pousado do slot e devolve como item (com a carga que ele segurava, se tiver).
        Drone em viagem: não sai (o slot está travado). Não cabe no inventário: fica, com o aviso."""
        drone = machine.station.drone_in(slot)
        if drone is None or drone.busy:
            return False
        trial = self.inventory.copy()
        if trial.add("drone", 1) or (drone.cargo and trial.add(drone.resource, drone.cargo)):
            self.events.append(("inv_full",))
            return False
        drones.undock(machine.station, slot)
        self.inventory.add("drone", 1)
        if drone.cargo:
            self.inventory.add(drone.resource, drone.cargo)
        self.events.append(("drone_undock",))
        return True

    def station_take(self, machine: Machine, resource: str, amount: int | None = None) -> int:
        """Tira minério das sobras do buffer antigo pro inventário (`amount` None = tudo daquele minério, até onde couber)."""
        have = machine.station.buffer.get(resource, 0)
        want = have if amount is None else min(amount, have)
        moved = want - self.inventory.add(resource, want)
        machine.station.take(resource, moved)
        if moved < want:
            self.events.append(("inv_full",))
        return moved

    def _update_drill(self, drill: Machine, dt: float) -> None:
        if drill.full:
            return
        drill.timer += dt
        while drill.timer >= C.DRILL_INTERVAL and not drill.full:
            drill.timer -= C.DRILL_INTERVAL
            drill.storage.add(drill.resource, 1)
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
        if machine.is_station:                       # buffer + carga dos drones: ou cabe tudo, ou nada muda
            return self._dismantle_station(machine)
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

    def _dismantle_station(self, machine: Machine) -> bool:
        """Estação: o buffer, a carga dos drones e os próprios drones (até os que estão voando: a viagem
        é cancelada) vão pro inventário junto com a estação. Se não couber tudo, ela fica no lugar
        (com o aviso de inventário cheio), sem perder nada."""
        contents = drones.recall_cargo(machine.station)
        n_drones = len(machine.station.drones)
        if n_drones:
            contents["drone"] = n_drones
        trial = self.inventory.copy()
        if any(trial.add(r, n) for r, n in contents.items()) or not trial.has_space(machine.kind):
            self.events.append(("inv_full",))
            return False
        for r, n in contents.items():
            self.inventory.add(r, n)
        machine.station.drones.clear()                 # quem estava voando some junto (sem carga perdida)
        self.machines.remove(machine)
        self.inventory.add(machine.kind, 1)
        self.events.append(("dismantle", machine.kind, (machine.tx, machine.ty)))
        return True

    def _update_machines(self, dt: float) -> None:
        power = self.power
        if self.power_alert.update(power.deficit, dt):
            self.events.append(("power_low",))
        work_dt = dt * power.factor          # sem energia suficiente, tudo anda mais devagar
        for m in self.all_machines:          # as duas camadas produzem (drill na caverna também)
            if m.is_drill:
                self._update_drill(m, work_dt)
            elif m.type.index is not None:   # painel solar, baú e estação não somam Ti
                self.indices[m.type.index] += m.type.rate * work_dt
        stations = [m for m in self.surface.machines if m.is_station]
        if stations:                         # drones (game/drones.py): só na superfície; no déficit voam mais devagar
            self.drone_deliveries += drones.update_stations(stations, self.drone_logistics(), work_dt, self.events)
        self._check_stage()

    def _check_stage(self) -> None:
        new_stage = stage_for_ti(self.ti)
        if new_stage > self.stage:          # estágio nunca volta
            self.stage = new_stage
            self.events.append(("stage_up", new_stage))

    # ---- rochas pequenas reaparecendo (game/rock_respawn.py) -----------------
    def _update_rocks(self, dt: float) -> list[tuple[int, int]]:
        """Rocha pequena nova na superfície (fora da vista do player, longe da base). Devolve os tiles novos."""
        surface = self.surface
        if surface.rocks is None:
            return []
        where = (self.player.x, self.player.y) if self.layer == SURFACE else C.SPAWN_POS
        born = surface.rocks.update(surface.world, self.rng, dt, where, surface.machines)
        for tile in born:
            self.events.append(("rock_spawn", tile))
        return born

    # ---- terminais ----------------------------------------------------------
    def nearby_terminal(self) -> int | None:
        for i, (tx, ty) in enumerate(self.world.terminals):
            bx, by = (tx + 0.5) * C.TILE, (ty + 1) * C.TILE    # base do terminal (onde a parede encosta no chão)
            if math.hypot(self.player.x - bx, self.player.y - by) <= C.TERMINAL_REACH:
                return i
        return None

    def read_terminal(self, index: int) -> str:
        """Terminal da caverna `index` (0 a 2) = índice 0 a 2 em LOGS (exibidos como LOG 01, 03 e 06)."""
        return self.read_log(index)

    def read_log(self, log: int) -> str:
        """Lê o LOG `log` (índice em config.LOGS): terminal da caverna, do módulo ou registro de bordo."""
        self.logs_read.add(log)
        self.events.append(("terminal", log))
        return C.LOGS[log]

    def log_entries(self) -> list[tuple[int, int, bool, bool]]:
        """Aba LOGs do inventário, na ordem cronológica: (índice em LOGS, número exibido, lido, novo).
        Novo = lido mas ainda não aberto pela aba."""
        return [(log, n, log in self.logs_read, log in self.logs_read and log not in self.logs_seen)
                for n, log in enumerate(C.LOG_ORDER, 1)]

    @property
    def new_logs(self) -> int:
        """Quantos LOGs lidos ainda não foram abertos pela aba (marca "NOVO")."""
        return len(self.logs_read - self.logs_seen)

    def reread_log(self, log: int) -> str | None:
        """Reabre pela aba LOGs um LOG já lido (tira o "NOVO"). Não lido: None (a aba não revela)."""
        if log not in self.logs_read:
            return None
        self.logs_seen.add(log)
        return self.read_log(log)

    # ---- destroços (v0.3 Marco 3 · game/wrecks.py) ---------------------------------
    @property
    def crates(self) -> dict:
        """Caixas de saque da camada ativa (tile -> Crate)."""
        return self.active.crates

    def crate_distance(self, crate: Crate) -> float:
        ax, ay = crate.anchor
        return math.hypot(self.player.x - ax, self.player.y - ay)

    def nearby_crate(self) -> Crate | None:
        near = [c for c in self.crates.values() if self.crate_distance(c) <= C.CRATE_REACH]
        return min(near, key=self.crate_distance, default=None)

    def wreck_terminal_distance(self, wreck: Wreck) -> float:
        """Dos pés até a base do terminal do módulo (o player lê do tile logo abaixo dele)."""
        tx, ty = wreck.terminal
        return math.hypot(self.player.x - (tx + 0.5) * C.TILE, self.player.y - (ty + 1) * C.TILE)

    def nearby_wreck_terminal(self) -> Wreck | None:
        near = [w for w in self.world.wrecks
                if w.terminal is not None and self.wreck_terminal_distance(w) <= C.TERMINAL_REACH]
        return min(near, key=self.wreck_terminal_distance, default=None)

    def learn(self, blueprint: str) -> bool:
        """Projeto encontrado: libera a receita na hora. False se já tinha."""
        if blueprint in self.blueprints:
            return False
        self.blueprints.add(blueprint)
        self.events.append(("blueprint", blueprint))
        return True

    def open_crate(self, crate: Crate) -> list[str]:
        """E na caixa: abre (som) e o projeto que estiver dentro sai sozinho (libera a receita e some).
        Devolve os projetos novos."""
        crate.opened = True
        self.events.append(("crate_open", crate.empty))
        found = []
        for i, stack in enumerate(crate.storage.slots):
            if stack is not None and stack.item in C.BLUEPRINT_ITEMS:
                crate.storage.slots[i] = None
                if self.learn(C.BLUEPRINT_ITEMS[stack.item]):
                    found.append(C.BLUEPRINT_ITEMS[stack.item])
        if found:                                    # o resto do saque encosta no começo (sem buraco no 1º slot)
            left = [st for st in crate.storage.slots if st is not None]
            crate.storage.slots = left + [None] * (len(crate.storage) - len(left))
        return found

    def crate_take(self, crate: Crate, index: int | None = None, amount: int | None = None) -> int:
        """Tira da caixa pro inventário: tudo (`index` None) ou o slot `index` (`amount` None = a pilha,
        1 = clique direito). Projeto não ocupa espaço: vira receita. Devolve quantas unidades saíram."""
        indexes = range(len(crate.storage)) if index is None else [index]
        moved = want = 0
        for i in indexes:
            stack = crate.storage.slots[i]
            if stack is None:
                continue
            if stack.item in C.BLUEPRINT_ITEMS:
                crate.storage.slots[i] = None
                self.learn(C.BLUEPRINT_ITEMS[stack.item])
                moved += 1
                want += 1
                continue
            n = stack.count if amount is None else min(amount, stack.count)
            item = stack.item
            got = crate.storage.transfer(i, self.inventory, n)
            want += n
            moved += got
            if got and item in C.RESOURCES:
                self.events.append(("loot", item, got, crate.anchor))
        if moved < want:
            self.events.append(("inv_full",))
        return moved

    def _update_explore(self, dt: float) -> None:
        """Explorado (game/explore.py) e destroços visitados, a cada EXPLORE_INTERVAL."""
        self.explore_timer -= dt
        if self.explore_timer > 0:
            return
        self.explore_timer = C.EXPLORE_INTERVAL
        explore.reveal_for(self)
        if self.active.has_base:
            ptx, pty = self.player.x / C.TILE, self.player.y / C.TILE
            for w in self.world.wrecks:
                if w.rank not in self.wrecks_visited:
                    cx, cy = w.center
                    if math.hypot(ptx - cx, pty - cy) <= C.WRECK_VISIT_DIST:
                        self.wrecks_visited.add(w.rank)

    # ---- equipamento (game/equipment.py) ----------------------------------------------
    @property
    def o2_max(self) -> float:
        """O₂ máximo: 100 s, ou 220 s com o tanque equipado."""
        return self.equipment.o2_max

    @property
    def has_scanner(self) -> bool:
        return self.equipment.has("scanner")

    def equip_from(self, index: int) -> bool:
        """Encaixa o equipamento do slot `index` do inventário no traje (troca com o que estava lá)."""
        stack = self.inventory.slots[index]
        if stack is None or not is_equipment(stack.item):
            return False
        item = stack.item
        self.inventory.remove_from_slot(index, 1)
        old = self.equipment.equip(item)
        if old is not None:
            self.inventory.add(old, 1)               # acabou de sair 1 do mesmo tipo: sempre cabe
        self.equipped_ever.add(item)
        self.events.append(("equip", item))
        self._clamp_o2()
        return True

    def equip_item(self, item: str) -> str | None:
        """Encaixa um item que não está no inventário (a "mão" da tela do Tab). Devolve o que saiu do slot."""
        old = self.equipment.equip(item)
        self.equipped_ever.add(item)
        self.events.append(("equip", item))
        self._clamp_o2()
        return old

    def unequip(self, kind: str) -> bool:
        """Tira o equipamento do slot e devolve pro inventário (sem espaço: fica, com o aviso)."""
        item = self.equipment.slots.get(kind)
        if item is None:
            return False
        if not self.inventory.has_space(item):
            self.events.append(("inv_full",))
            return False
        self.equipment.unequip(kind)
        self.inventory.add(item, 1)
        self.events.append(("unequip", item))
        self._clamp_o2()
        return True

    def _clamp_o2(self) -> None:
        self.o2 = min(self.o2, self.o2_max)

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
