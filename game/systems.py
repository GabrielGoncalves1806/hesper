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
from game.base import BaseBlock, BaseGrid, Seal
from game.base import H as ORIENT_H, V as ORIENT_V
from game import explore
from game import layers
from game import magmatite
from game import thaw
from game.equipment import Equipment, is_equipment
from game.inventory import Inventory, Stack, max_stack
from game.energy import PowerAlert, PowerReport, power_report
from game.layers import CAVE, SURFACE, Layer
from game.player import Player, Rect, overlaps
from game.rain import Rain
from game.thaw import lake_level
from game.weather import Weather
from game.world import World
from game.wrecks import Crate, Wreck


@dataclass
class Controls:
    """O que o jogador quer fazer neste frame (já traduzido do teclado/mouse)."""
    move_x: float = 0.0
    move_y: float = 0.0
    mine_tile: tuple[int, int] | None = None   # tile mirado enquanto segura o clique
    in_menu: bool = False                      # tela aberta (inventário, fabricador, mapa...): sem empurrão do vento
    dismantle: "Machine | None" = None         # v0.5 M1: máquina debaixo do mouse com o botão direito segurado


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
    # v0.4 M3.4: o lago subiu por cima dela (GameState._thaw_submerged). Derivado: não vai no save, o load refaz.
    # Parada: não soma índice, não gera nem gasta energia, a drill não cava e a estação não manda drone.
    submerged: bool = field(default=False, compare=False)
    # v0.5 M1: segundos que faltam pra terminar de se construir (o scanner varrendo). Enquanto > 0 ela não funciona
    # (não soma Ti, não gera nem gasta energia). Não vai no save: carregou, já está pronta.
    build: float = field(default=0.0, compare=False)
    # v0.5 M1 B2: só a Bancada T2. Segundos que faltam da animação de "fabricando" (C.BENCH_WORK_TIME ao fabricar).
    work: float = field(default=0.0, compare=False)
    # v0.5 M2: só o Dispersor de O₂ (storage = 1 slot de cápsula). `burn` = segundos que faltam da cápsula que está
    # sendo gasta (vai no save). O resto é derivado ou de som: `seal`/`seal_version` (cache da vedação), `sealed_prev`
    # (None = ainda não olhou: o load nunca soa), `sealed_once` (já esteve vedada: só aí o furo é "vazamento" com alerta),
    # `leak_t` (relógio do leak_alert).
    burn: float = field(default=0.0, compare=False)
    seal: Seal | None = field(default=None, compare=False, repr=False)
    seal_version: int = field(default=-1, compare=False, repr=False)
    sealed_prev: bool | None = field(default=None, compare=False, repr=False)
    sealed_once: bool = field(default=False, compare=False)
    leak_t: float = field(default=0.0, compare=False, repr=False)

    def __post_init__(self, stored_init: int = 0) -> None:
        if self.storage is None and self.is_drill:
            self.storage = Inventory(C.DRILL_SLOTS)
        elif self.storage is None and self.is_chest:
            self.storage = Inventory(C.CHEST_SLOTS)
        elif self.storage is None and self.is_melter:
            self.storage = Inventory(C.MELTER_SLOTS)
        elif self.storage is None and self.is_dispenser:
            self.storage = Inventory(C.DISPENSER_SLOTS)
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
    def is_melter(self) -> bool:
        """Derretedor (nv.1 ou nv.2): terraforma e, de brinde, faz cápsula de água do gelo do inventário dele."""
        return self.kind in C.MELTER_KINDS

    @property
    def is_dispenser(self) -> bool:
        """Dispersor de O₂ (v0.5 M2): 1 slot de cápsula de água, vedação da base e O₂ lá dentro."""
        return self.kind == C.DISPENSER

    @property
    def is_chest(self) -> bool:
        return self.kind == "chest"

    @property
    def is_bench(self) -> bool:
        return self.kind == "workbench"

    @property
    def is_station(self) -> bool:
        return self.kind == "drone_station"

    @property
    def is_lamp(self) -> bool:
        return self.kind in C.LAMP_RADIUS          # luminária comum e a forte (Marco 3)

    @property
    def is_logistic(self) -> bool:
        """Baú, drill e derretedor: têm inventário que os drones atendem (Envia/Recebe/Lote)."""
        return self.is_chest or self.is_drill or self.is_melter

    @property
    def is_producer(self) -> bool:
        """Drill e derretedor só produzem pros drones tirarem: não recebem nada deles."""
        return self.is_drill or self.is_melter

    @property
    def capsules(self) -> int:
        """Derretedor: cápsulas de água na saída. Dispersor: as que estão no slot (fora a que está queimando)."""
        return self.storage.count("water_capsule") if self.is_melter or self.is_dispenser else 0

    @property
    def ice(self) -> int:
        """Derretedor: gelo na entrada."""
        return self.storage.count("ice") if self.is_melter else 0

    @property
    def capsules_full(self) -> bool:
        """Derretedor com a saída cheia (não faz mais cápsula até alguém tirar)."""
        return self.is_melter and self.capsule_room <= 0

    @property
    def capsule_room(self) -> int:
        """Derretedor: quantas cápsulas ainda cabem na saída (o slot [1] guarda só cápsula)."""
        if not self.is_melter:
            return 0
        stack = self.storage.slots[C.MELTER_CAPSULE_SLOT]
        return stack.room if stack else max_stack("water_capsule")

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
        elif self.is_bench:
            w, h = C.BENCH_SPRITE_SIZE
        elif self.is_dispenser:
            w, h = C.DISPENSER_SPRITE_SIZE
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


def storm_level(state) -> float:
    """Intensidade da tempestade que vale onde o player está: 0 na caverna (a poeira não entra lá),
    senão o `state.storm` (1 = tempestade cheia, 0 = céu limpo)."""
    return 0.0 if state.layer == CAVE else state.storm


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
        self.seed = seed               # seed do MUNDO: tudo que é gerado (mapa, clima, transição) sai dela
        self.world_name = "Mundo 1"    # nome do mundo (game/worlds.py); vai no bloco "world" do save
        self.world_created = ""        # quando o mundo foi criado (ISO, até o minuto)
        self.layers: dict[str, Layer] = {SURFACE: layers.make_surface(seed)}
        self.layer = SURFACE
        self.rng = rng or random.Random()
        self.magma_rng = random.Random(seed * 7919 + C.MAGMATITE_SEED)   # reaparecimento da magmatita (game/magmatite.py)
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
        # Tempestade de poeira (v0.4): 1.0 cheia, 0.0 sem. Passou do estágio Tempestade, desce até 0 em
        # STORM_FADE_S (a poeira afina e as rajadas param). Quem lê usa `storm_level(state)` (0 na caverna).
        self.storm = 1.0
        self.mining: Mining | None = None
        self.fainted = False
        self.faint_time = 0.0          # segundos desde o desmaio
        self.time_scale = 1            # F1 muda pra 10
        self.fast = False              # F3: player DEBUG_SPEED× mais rápido e broca DEBUG_MINE× mais rápida
        self.debug_crater = False      # F4: a cratera foi aberta pelo atalho de debug (aviso no topo da tela)
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
        # Marco 3: receitas liberadas por diagrama lido, equipamento do traje, destroços visitados e explorado
        self.blueprints: set[str] = set()
        self.equipment = Equipment()
        self.equipped_ever: set[str] = set()           # equipamento que já foi encaixado alguma vez (objetivos)
        self.wrecks_visited: set[int] = set()          # rank dos destroços que o player já chegou perto
        self.explore_timer = 0.0                       # o explorado atualiza a cada EXPLORE_INTERVAL
        self.weather = Weather(seed)                   # tempestade (v0.4): vento, rajadas e raio de visão
        self.rain = Rain(seed)                         # chuva (v0.4 M3.3): pancadas na Névoa e no Verde
        # v0.5 M1: desmontar segurando o botão direito (`_update_dismantle`)
        self.dismantling: Machine | None = None        # máquina com a barrinha enchendo
        self.dismantle_t = 0.0                         # s segurando nela
        self._dismantle_lock: Machine | None = None    # já tentou: só carrega de novo depois de soltar
        self.events: list[tuple] = []
        self._seal_sound_t = -99.0                     # play_time do último base_sealed (cooldown C.SEAL_SOUND_COOLDOWN)

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
    def base(self) -> BaseGrid:
        """Os blocos da base (chão, parede, porta) da camada ativa."""
        return self.active.base

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

    @property
    def crater_frozen(self) -> bool:
        """A cratera da superfície ainda está tampada de gelo? (v0.4: nasce coberta, derrete no M3)"""
        return SURFACE in self.layers and self.surface.crater_ice < C.CRATER_ICE_STAGES

    def ramp_blocked(self) -> bool:
        """Na superfície, com o gelo na cratera, não dá pra descer (subir da caverna sempre dá)."""
        return self.active.has_base and self.crater_frozen

    def start_ramp(self) -> bool:
        """E na rampa (no alcance): começa o fade. A troca de camada acontece no meio dele."""
        if self.ramp is not None or self.fainted or self.ramp_distance() > C.RAMP_REACH or self.ramp_blocked():
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
    def working_machines(self) -> list:
        """As máquinas das duas camadas que estão funcionando (a submersa parou: v0.4 M3.4; a que ainda está se
        construindo também não conta: v0.5 M1)."""
        return [m for m in self.all_machines if not m.submerged and m.build <= 0]

    @property
    def ti_rate(self) -> float:
        """Ti por segundo, já com o ritmo da energia (no déficit, todas rendem menos)."""
        return sum(m.type.rate for m in self.working_machines) * self.power.factor

    @property
    def power(self) -> PowerReport:
        """Energia agora: produção, consumo e o fator (ritmo) das máquinas que funcionam. Ver game/energy.py."""
        return power_report(m.kind for m in self.working_machines)

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
                if self.world.get(tx, ty) in C.SMALL_ROCKS:   # rocha pequena: só a base do desenho colide
                    rx, ry, rw, rh = C.SMALL_ROCK_RECT
                    solids.append((tx * C.TILE + rx, ty * C.TILE + ry, rw, rh))
                elif self.world.is_solid(tx, ty):
                    solids.append((tx * C.TILE, ty * C.TILE, C.TILE, C.TILE))
        solids += [m.rect for m in self.machines]
        if self.active.base.blocks:                       # v0.5 M2: parede e porta da base
            solids += self.active.base.solids_in(x0, y0, x1, y1)
        solids += self.active.gate_solids                 # v0.4 M3.5: os blocos de gelo dos portões (retângulos)
        if self.active.has_base:
            solids.append(POD_RECT)
        return solids

    # ---- loop principal -----------------------------------------------------
    def update(self, dt: float, controls: Controls) -> None:
        dt = min(dt, C.MAX_DT)
        self.play_time += dt
        sim_dt = dt * self.time_scale     # O₂ e máquinas andam mais rápido com F1
        storm = storm_level(self)
        if self.weather.update(dt, storm):
            self.events.append(("gust", storm))
        if self.rain.update(dt, self.stage):           # pancada de chuva começou (só a partir da Névoa)
            self.events.append(("rain", True))

        if self.fainted or self.ramp is not None:   # desmaiado ou na rampa: solta o desmonte que estava segurando
            self._update_dismantle(None, dt)
        if self.fainted:
            self.ramp = None                  # desmaiou no meio do fade: acorda na cápsula, sem viagem
            self._update_faint(dt)
        elif self.ramp is not None:           # descendo/subindo: parado, só o O₂ continua
            self._update_ramp(dt)
            self._update_o2(sim_dt)
        else:
            self._update_dismantle(controls.dismantle, dt)
            self.player.move(controls.move_x, controls.move_y, dt, self.solids_near, self.player_speed)
            if not controls.in_menu:          # rajada: o vento empurra (parado, desliza; contra, anda mais devagar)
                self.player.drift(*self.weather.push(storm), dt, self.solids_near)
            self._update_mining(dt, controls.mine_tile)
            self._update_o2(sim_dt)
        self._update_building(dt)
        self._update_doors(dt)
        self._update_base_events(dt)
        self._update_machines(sim_dt)
        self._update_storm(dt)
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
        m.elapsed += dt * self.mine_speed       # F3: a broca anda DEBUG_MINE× mais rápido
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
        inside = self.in_base_zone() or self.in_sealed_base()
        if inside:
            if not self.was_in_base and self.o2 < self.o2_max:
                self.events.append(("refill",))
            self.o2 = min(self.o2_max, self.o2 + C.O2_REFILL * dt)
        else:
            self.o2 = max(0.0, self.o2 - C.O2_DRAIN * self.o2_drain_mult * dt)
            if self.o2 <= 0:
                self._faint()
        self.was_in_base = inside

    @property
    def o2_drain_mult(self) -> float:
        """Fora da base, a tempestade gasta mais O₂: ×STORM_O2_MULT cheia, interpolando com a intensidade."""
        return 1 + (C.STORM_O2_MULT - 1) * storm_level(self)

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

    def craft_sources(self, inv_only: bool = False) -> list[Machine]:
        """Baús que entram na conta de uma receita: os da base no fabricador; nenhum no construtor (só o inventário)."""
        return [] if inv_only else self.base_chests()

    def available(self, resource: str, inv_only: bool = False) -> int:
        """Quanto dá pra gastar desse recurso: inventário + baús da base (fabricador) ou só o inventário (construtor)."""
        return self.inventory.count(resource) + sum(c.storage.count(resource) for c in self.craft_sources(inv_only))

    def recipe_status(self, kind: str, inv_only: bool = False) -> str:
        """'blueprint' (diagrama não lido), 'known' (a receita é um diagrama que já foi lido), 'locked' (Ti
        insuficiente), 'missing' (falta recurso) ou 'ok'.
        `inv_only`: conta só o inventário (o construtor, v0.5 M1)."""
        machine = C.MACHINES[kind]
        blueprint = C.RECIPE_BLUEPRINT.get(kind)
        if blueprint is not None and blueprint not in self.blueprints:
            return "blueprint"
        if kind in C.DIAGRAM_ITEMS and C.DIAGRAM_ITEMS[kind] in self.blueprints:
            return "known"                      # o diagrama dessa receita já foi lido: não se fabrica de novo
        if self.ti < machine.unlock_ti:
            return "locked"
        if any(self.available(r, inv_only) < n for r, n in machine.cost.items()):
            return "missing"
        return "ok"

    def missing_resource(self, kind: str, inv_only: bool = False) -> str | None:
        for r, n in C.MACHINES[kind].cost.items():
            if self.available(r, inv_only) < n:
                return r
        return None

    def _spend(self, cost: dict, inv_only: bool = False) -> None:
        """Gasta a receita: primeiro o inventário, depois os baús da base (se valer). Quem chama já conferiu."""
        for r, n in cost.items():
            left = n - self.inventory.remove(r, n)
            for chest in self.craft_sources(inv_only):
                if left <= 0:
                    break
                left -= chest.storage.remove(r, left)

    def craft(self, kind: str, bench: str = "t1", at: Machine | None = None) -> bool:
        """Fabrica 1 item no fabricador da base (v0.5 M1: só itens; máquina vem do construtor). Gasta primeiro o
        inventário, depois os baús da base. O item vai pro inventário (falha com aviso se não couber).
        `bench` "t2" = a Bancada T2 (`at`, a máquina): só receitas C.T2_RECIPES, em qualquer lugar, gastando SÓ o
        inventário, e ela anima por C.BENCH_WORK_TIME."""
        t2 = bench == "t2"
        if C.MACHINES[kind].placeable or (kind in C.T2_RECIPES) != t2:
            return False
        if not t2 and not self.in_base_zone():
            return False
        if self.recipe_status(kind, inv_only=t2) != "ok":
            return False
        cost = C.MACHINES[kind].cost
        # "e se eu gastar o que vem do inventário, sobra lugar pro item?" (testa numa cópia)
        trial = self.inventory.copy()
        for r, n in cost.items():
            trial.remove(r, n)
        if not trial.has_space(kind):
            self.events.append(("inv_full",))
            return False
        self._spend(cost, inv_only=t2)
        self.inventory.add(kind, 1)
        self.crafted[kind] += 1
        self.events.append(("craft", kind))
        if at is not None:
            at.work = C.BENCH_WORK_TIME
        return True

    def craft_many(self, kind: str, limit: int = C.CRAFT_BATCH, bench: str = "t1", at: Machine | None = None) -> int:
        """Fabrica até `limit` de uma vez (Shift no fabricador). Para no primeiro que falhar (faltou
        recurso ou não cabe no inventário). Devolve quantas fabricou; o evento "craft" sai uma vez só
        (um som), com a quantidade."""
        made = 0
        while made < limit and self.craft(kind, bench, at):
            made += 1
        if made > 1:
            crafts = [e for e in self.events if e[0] == "craft" and e[1] == kind]
            for e in crafts[:-1]:
                self.events.remove(e)
            self.events[self.events.index(crafts[-1])] = ("craft", kind, made)
        return made

    # ---- construtor (v0.5 M1) -------------------------------------------------
    @property
    def has_constructor(self) -> bool:
        return self.inventory.count("constructor") > 0

    def can_place(self, kind: str, tile: tuple[int, int], rotation: int = 0) -> bool:
        """O LUGAR serve? Máquina comum: 1 tile de chão livre fora de veio. Drill: `tile` tem que ser o canto
        de cima à esquerda de um veio livre (o App "gruda" o fantasma no veio debaixo do mouse).
        Não olha material nem construtor (isso é o `can_build`)."""
        tx, ty = tile
        if not C.MACHINES[kind].placeable:      # item (drone, construtor, equipamento) não vai pro chão
            return False
        if kind in C.BASE_KINDS:                # v0.5 M2: bloco da base (chão, parede, porta)
            return self._can_place_base(kind, tile, rotation)
        if kind == "drone_station" and not self.active.has_base:   # drones só atendem a superfície (v0.3)
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
            if not self.world.is_floor(*t) or t in pod or self.machine_at(t) or self.base.is_barrier(t):
                return False
            if self.world.is_water(*t, self.stage):     # v0.4 M3.4: não constrói na água (com geo, o estágio não entra)
                return False
        ice = self.active.gate_solids                   # v0.4 M3.5: nem em cima de um bloco de gelo do portão
        if any(overlaps((x * C.TILE, y * C.TILE, C.TILE, C.TILE), r) for x, y in machine.tiles for r in ice):
            return False
        px, py = self.player.tile
        if (px, py) in machine.tiles:
            return False
        if min(max(abs(x - px), abs(y - py)) for x, y in machine.tiles) > C.PLACE_REACH:
            return False
        # não pode prender o player dentro da máquina
        return not overlaps(self.player.box, machine.rect)

    def build_status(self, kind: str) -> str:
        """Dá pra construir essa máquina agora (fora o lugar)? 'no_constructor', o recipe_status contando só o
        inventário ('blueprint', 'locked', 'missing') ou 'ok'."""
        if not self.has_constructor:
            return "no_constructor"
        return self.recipe_status(kind, inv_only=True)

    def can_build(self, kind: str, tile: tuple[int, int], rotation: int = 0) -> bool:
        """Construtor no inventário, receita liberada, material no inventário e o lugar serve."""
        return self.build_status(kind) == "ok" and self.can_place(kind, tile, rotation)

    def build(self, kind: str, tile: tuple[int, int], rotation: int = 0) -> bool:
        """Constrói a máquina no lugar (v0.5 M1, o único jeito de pôr máquina no chão): gasta a receita SÓ do
        inventário e ela nasce "se construindo" por C.BUILD_TIME s (parada, o scanner varre de baixo pra cima)."""
        if not self.can_build(kind, tile, rotation):
            return False
        self._spend(C.MACHINES[kind].cost, inv_only=True)
        if kind in C.BASE_KINDS:
            return self._build_base(kind, tile, rotation)
        machine = Machine(kind, tile[0], tile[1], rotation)
        machine.build = C.BUILD_TIME
        if machine.is_drill:                                   # vem com Envia/Recebe vazios: o player configura
            machine.resource = self.world.vein_at(*tile).resource
            self.drills_placed += 1
        if machine.is_chest:
            machine.name = C.CHEST_DEFAULT_NAME
        if machine.is_station:
            machine.station = drones.new_station(machine)      # vem vazia: os drones vão pelo painel (E)
        if machine.is_lamp:
            self.lamps_placed += 1
        if machine.is_dispenser:
            machine.sealed_prev = False                        # recém-construído: vedar a base depois soa o base_sealed
        self.machines.append(machine)
        if self.active.has_base:                               # a caverna não muda com o Ti
            self.transition_sources.add(tuple(tile))
        self.crafted[kind] += 1                                # "já fez uma dessas" (objetivos): construir conta
        self.events.append(("build", kind, tile))
        return True

    def _update_building(self, dt: float) -> None:
        """O relógio das máquinas se construindo (tempo real, o F1 não acelera a animação)."""
        for m in self.all_machines:
            if m.build > 0:
                m.build = max(0.0, m.build - dt)
            if m.work > 0:
                m.work = max(0.0, m.work - dt)

    # ---- drill automática ---------------------------------------------------
    # ---- base respirável (v0.5 M2 · game/base.py) -----------------------------------------------------
    @staticmethod
    def base_tiles(kind: str, tile: tuple[int, int], rotation: int = 0) -> list[tuple[int, int]]:
        """Tiles que o bloco ocupa se for posto em `tile`. A porta dupla: rotação par = 2 lado a lado (h), ímpar = um
        em cima do outro (v); `tile` é a metade de oeste/norte."""
        tx, ty = tile
        if kind == C.BASE_DOOR2:
            return [(tx, ty), (tx + 1, ty)] if rotation % 2 == 0 else [(tx, ty), (tx, ty + 1)]
        return [(tx, ty)]

    def _can_place_base(self, kind: str, tile: tuple[int, int], rotation: int = 0) -> bool:
        """Chão: tile livre de bloco (aceita máquina em cima). Parede e portas: também sem máquina e sem prender o
        player. Todos: chão do mundo, fora da água, da cápsula, de veio e do gelo-portão, ao alcance."""
        tiles = self.base_tiles(kind, tile, rotation)
        pod = C.POD_TILES if self.active.has_base else ()
        ice = self.active.gate_solids
        for t in tiles:
            if not self.world.is_floor(*t) or t in pod or self.base.get(t) or self.world.vein_at(*t):
                return False
            if self.world.is_water(*t, self.stage):
                return False
            if kind != C.BASE_FLOOR and self.machine_at(t):
                return False
            if any(overlaps((t[0] * C.TILE, t[1] * C.TILE, C.TILE, C.TILE), r) for r in ice):
                return False
            if kind != C.BASE_FLOOR and overlaps(self.player.box, (t[0] * C.TILE, t[1] * C.TILE, C.TILE, C.TILE)):
                return False
        px, py = self.player.tile
        return min(max(abs(x - px), abs(y - py)) for x, y in tiles) <= C.PLACE_REACH

    def _build_base(self, kind: str, tile: tuple[int, int], rotation: int) -> bool:
        orient = ORIENT_H if rotation % 2 == 0 else ORIENT_V
        self.base.add(BaseBlock(kind, tile[0], tile[1], orient if kind == C.BASE_DOOR2 else ORIENT_H))
        self.crafted[kind] += 1
        self.events.append(("build", kind, tile))
        return True

    def block_at_point(self, px: float, py: float) -> BaseBlock | None:
        """Bloco da base desenhado no pixel (px, py): o do tile, ou o da parede/porta de baixo cujo topo (24 px
        acima do tile dela) cobre esse pixel. O chão só vale se não tem parede/porta cobrindo."""
        grid = self.base
        if not grid.blocks:
            return None
        tx, ty = int(px // C.TILE), int(py // C.TILE)
        below = grid.get((tx, ty + 1))
        if below is not None and not below.is_floor and py % C.TILE >= C.TILE - C.BASE_WALL_LIFT + C.BASE_FACE_Y:
            return below
        return grid.get((tx, ty))

    def _update_doors(self, dt: float) -> None:
        """As portas abrem sozinhas com o player a até DOOR_OPEN_RANGE de qualquer tile delas (0 -> 3 a DOOR_FPS) e
        fecham quando ele sai. Eventos: ("door", "open"|"close", centro em px) quando começa a abrir da fechada e
        quando fecha de vez."""
        doors = self.base.door_list
        if not doors:
            return
        p = self.player
        cx, cy = p.x, p.y - 12
        step = C.DOOR_FPS * dt
        top = C.DOOR_FRAMES - 1
        for d in doors:
            near = any(math.hypot(cx - (x + 0.5) * C.TILE, cy - (y + 0.5) * C.TILE) <= C.DOOR_OPEN_RANGE
                       for x, y in d.tiles) and not self.fainted
            if near:
                if not d.opening:
                    d.opening = True
                    if d.frame <= 0:
                        self.events.append(("door", "open", self._door_center(d)))
                d.frame = min(top, d.frame + step)
            else:
                d.opening = False
                if d.frame > 0:
                    d.frame = max(0.0, d.frame - step)
                    if d.frame <= 0:
                        self.events.append(("door", "close", self._door_center(d)))

    @staticmethod
    def _door_center(door: BaseBlock) -> tuple[float, float]:
        xs = [(x + 0.5) * C.TILE for x, _ in door.tiles]
        ys = [(y + 0.5) * C.TILE for _, y in door.tiles]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def _layer_of(self, machine: Machine) -> Layer:
        if any(m is machine for m in self.active.machines):
            return self.active
        return next((layer for layer in self.layers.values() if any(m is machine for m in layer.machines)), self.active)

    def seal_of(self, machine: Machine, layer: Layer | None = None) -> Seal:
        """A vedação da base do Dispersor (cache: só recalcula quando um bloco mudou perto, ver BaseGrid.changed_near)."""
        grid = (layer or self._layer_of(machine)).base
        if machine.seal is None or (machine.seal_version != grid.version
                                    and grid.changed_near(machine.seal_version, machine.seal.watch)):
            machine.seal = grid.seal_from((machine.tx, machine.ty))
        machine.seal_version = grid.version
        return machine.seal

    def dispenser_state(self, machine: Machine, factor: float | None = None) -> str:
        """Estado do Dispersor: "nopower" > geometria ("leak", "small", "nodoor", "big", "nofloor") > "dry" > "sealed"."""
        factor = self.power.factor if factor is None else factor
        if factor <= 0:
            return "nopower"
        seal = self.seal_of(machine)
        if not seal.ok:
            return seal.reason
        if machine.burn <= 0 and machine.capsules <= 0:
            return "dry"
        return "sealed"

    def air_ok(self, machine: Machine, factor: float | None = None) -> bool:
        """O Dispersor está soprando (ligado, base vedada, com água)?"""
        return (machine.is_dispenser and not machine.submerged and machine.build <= 0
                and self.dispenser_state(machine, factor) == "sealed")

    def in_sealed_base(self) -> bool:
        """O player está dentro de uma base vedada com o Dispersor soprando? (aí o O₂ recarrega como na cápsula)"""
        return self.breathing_dispenser() is not None

    def breathing_dispenser(self) -> Machine | None:
        dispensers = [m for m in self.machines if m.is_dispenser]
        if not dispensers:
            return None
        factor = self.power.factor
        tile = self.player.tile
        for m in dispensers:
            if self.air_ok(m, factor) and tile in self.seal_of(m, self.active).inside:
                return m
        return None

    def _update_base_events(self, dt: float) -> None:
        """Tempo real: a transição pra "vedada" (base_sealed, com cooldown; o load nunca soa) e o leak_alert a cada
        LEAK_ALERT_EVERY s enquanto vaza com o player por perto (só vazamento de base que já esteve vedada)."""
        for key, layer in self.layers.items():
            for m in layer.machines:
                if not m.is_dispenser or m.submerged or m.build > 0:
                    continue
                seal = self.seal_of(m, layer)
                if m.sealed_prev is None:
                    m.sealed_prev = seal.ok
                elif seal.ok != m.sealed_prev:
                    m.sealed_prev = seal.ok
                    if seal.ok and self.play_time - self._seal_sound_t >= C.SEAL_SOUND_COOLDOWN:
                        self._seal_sound_t = self.play_time
                        self.events.append(("base_sealed", m.anchor))
                if seal.ok:
                    m.sealed_once = True
                if key == self.layer and not seal.ok and m.sealed_once and seal.reason in ("leak", "nofloor"):
                    if self.leak_distance(m) <= C.LEAK_ALERT_RANGE * C.TILE:
                        m.leak_t -= dt
                        if m.leak_t <= 0:
                            m.leak_t = C.LEAK_ALERT_EVERY
                            self.events.append(("leak_alert", m.anchor))
                else:
                    m.leak_t = 0.0

    def leak_distance(self, m: Machine) -> float:
        """px do player até o Dispersor ou o tile furado (o que estiver mais perto)."""
        p = self.player
        points = [m.anchor]
        leak = m.seal.leak if m.seal is not None else None
        if leak is not None:
            points.append(((leak[0] + 0.5) * C.TILE, (leak[1] + 0.5) * C.TILE))
        return min(math.hypot(p.x - x, p.y - y) for x, y in points)

    def _burn_capsules(self, machine: Machine, layer: Layer, dt: float) -> None:
        """Gasta a água do Dispersor: com a base vedada e ligado, 1 cápsula dura C.DISPENSER_CAPSULE_TIME s. A cápsula
        sai do slot quando começa a queimar; acabou a última, solta ("dispenser_dry", posição) uma vez."""
        if not self.seal_of(machine, layer).ok:
            return
        while dt > 1e-9:
            if machine.burn <= 0:
                if machine.capsules <= 0:
                    return
                machine.storage.remove("water_capsule", 1)
                machine.burn = C.DISPENSER_CAPSULE_TIME
            used = min(dt, machine.burn)
            machine.burn -= used
            dt -= used
            if machine.burn <= 1e-9:
                machine.burn = 0.0
                if machine.capsules <= 0:
                    self.events.append(("dispenser_dry", machine.anchor))
                    return

    def drill_distance(self, drill: Machine) -> float:
        """Distância (px) dos pés do player até a base da drill."""
        ax, ay = drill.anchor
        return math.hypot(self.player.x - ax, self.player.y - (ay - C.TILE / 2))

    def vent_distance(self) -> float | None:
        """Distância (tiles) dos pés do player até a fumarola ACORDADA mais perto da superfície; None se nenhuma
        acordou. O pé da fumarola é o mesmo tile do hills.foot_tile (não importo o hills aqui: puxa o numpy)."""
        geo = self.surface.geo
        if geo is None:
            return None
        best = None
        for f, awake in zip(geo.vents, self.surface.vents_awake):
            if not awake:
                continue
            fx, fy = f.tx + f.size[0] // 2, f.ty + f.size[1] - 1
            d = math.hypot(self.player.x - (fx + 0.5) * C.TILE, self.player.y - (fy + 1) * C.TILE) / C.TILE
            best = d if best is None else min(best, d)
        return best

    def nearby_melter(self) -> Machine | None:
        """Derretedor ao alcance do E (o mais perto)."""
        near = [m for m in self.machines if m.is_melter and m.build <= 0 and self.drill_distance(m) <= C.MELTER_REACH]
        return min(near, key=self.drill_distance, default=None)

    def nearby_dispenser(self) -> Machine | None:
        """Dispersor de O₂ ao alcance do E (o mais perto)."""
        near = [m for m in self.machines if m.is_dispenser and m.build <= 0
                and self.drill_distance(m) <= C.DISPENSER_REACH]
        return min(near, key=self.drill_distance, default=None)

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

    def nearby_bench(self) -> Machine | None:
        """Bancada T2 ao alcance do E (a mais perto; ainda se construindo não abre)."""
        near = [m for m in self.machines if m.is_bench and m.build <= 0 and self.drill_distance(m) <= C.BENCH_REACH]
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
                               ("station", machine.is_station), ("bench", machine.is_bench),
                               ("melter", machine.is_melter and machine.build <= 0),
                               ("dispenser", machine.is_dispenser and machine.build <= 0)):
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
        for tile in tiles:                               # v0.4 M3.2: contêiner lacrado (só mostra a dica)
            if self.world.get(*tile) == C.CONTAINER:
                return "container", tile
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
        if kind == "container":
            return tuple(target) in self.world.containers and self.container_distance(target) <= C.CONTAINER_REACH
        reach = {"drill": C.DRILL_REACH, "chest": C.CHEST_REACH, "station": C.STATION_REACH,
                 "bench": C.BENCH_REACH, "melter": C.MELTER_REACH, "dispenser": C.DISPENSER_REACH}[kind]
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
        bench = self.nearby_bench()
        if bench is not None:
            options.append((self.drill_distance(bench), "bench", bench))
        melter = self.nearby_melter()
        if melter is not None:
            options.append((self.drill_distance(melter), "melter", melter))
        dispenser = self.nearby_dispenser()
        if dispenser is not None:
            options.append((self.drill_distance(dispenser), "dispenser", dispenser))
        crate = self.nearby_crate()
        if crate is not None:
            options.append((self.crate_distance(crate), "crate", crate))
        wreck = self.nearby_wreck_terminal()
        if wreck is not None:
            options.append((self.wreck_terminal_distance(wreck), "wreck_log", wreck))
        box = self.nearby_container()
        if box is not None:
            options.append((self.container_distance(box), "container", box))
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

    def melter_put(self, melter: Machine, index: int, amount: int | None = None) -> int:
        """Põe gelo do slot `index` do inventário do player na entrada do derretedor (`amount` None = a pilha
        inteira, 1 = clique direito). Só entra gelo, e só até a pilha encher. Devolve quanto entrou."""
        stack = self.inventory.slots[index]
        if stack is None or stack.item != "ice":
            return 0
        slot = C.MELTER_ICE_SLOT
        have = melter.storage.slots[slot]
        room = stack.max - (have.count if have else 0)
        moved = min(room, stack.count if amount is None else min(amount, stack.count))
        if moved <= 0:
            return 0
        if have is None:
            melter.storage.slots[slot] = Stack("ice", moved)
        else:
            have.count += moved
        self.inventory.remove_from_slot(index, moved)
        return moved

    def dispenser_put(self, dispenser: Machine, index: int, amount: int | None = None) -> int:
        """Põe cápsulas de água do slot `index` do inventário do player no slot do Dispersor (`amount` None = a pilha
        inteira, 1 = clique direito). Só entra cápsula, e só até a pilha encher. Devolve quanto entrou."""
        stack = self.inventory.slots[index]
        if stack is None or stack.item != "water_capsule":
            return 0
        slot = C.DISPENSER_CAPSULE_SLOT
        have = dispenser.storage.slots[slot]
        room = stack.max - (have.count if have else 0)
        moved = min(room, stack.count if amount is None else min(amount, stack.count))
        if moved <= 0:
            return 0
        if have is None:
            dispenser.storage.slots[slot] = Stack("water_capsule", moved)
        else:
            have.count += moved
        self.inventory.remove_from_slot(index, moved)
        return moved

    def melter_take(self, melter: Machine, index: int | None = None, amount: int | None = None) -> int:
        """Tira do inventário do derretedor pro do player: tudo (`index` None) ou o slot `index` (`amount` None
        = a pilha inteira). O que não couber fica lá (e avisa de inventário cheio). Devolve quanto saiu."""
        before = sum(melter.storage.counts().values())
        if index is None:
            melter.storage.transfer_all(self.inventory)
            want = before
        else:
            stack = melter.storage.slots[index]
            want = 0 if stack is None else stack.count if amount is None else min(amount, stack.count)
            melter.storage.transfer(index, self.inventory, amount)
        moved = before - sum(melter.storage.counts().values())
        if moved < want:
            self.events.append(("inv_full",))
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

    def _update_melter(self, melter: Machine, dt: float) -> None:
        """Cápsulas de água (v0.5 M2): a cada MELTER_CAPSULE_TIME s gasta MELTER_ICE_PER_CAPSULE de gelo da entrada
        e põe 1 cápsula na saída. Sem gelo ou com a saída cheia, para (o progresso fica guardado) e não gasta gelo.
        A terraformação não passa por aqui: segue em _update_machines como sempre."""
        need_time = C.MELTER_CAPSULE_TIME[melter.kind]
        while dt > 0 and melter.ice >= C.MELTER_ICE_PER_CAPSULE and melter.capsule_room > 0:
            left = need_time - melter.timer
            if dt < left:
                melter.timer += dt
                return
            dt -= left
            melter.timer = 0.0
            melter.storage.remove("ice", C.MELTER_ICE_PER_CAPSULE)
            stack = melter.storage.slots[C.MELTER_CAPSULE_SLOT]
            if stack is None:
                melter.storage.slots[C.MELTER_CAPSULE_SLOT] = Stack("water_capsule", 1)
            else:
                stack.count += 1

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

    def can_dismantle(self, machine) -> bool:
        px, py = self.player.tile
        if isinstance(machine, BaseBlock):              # v0.5 M2: bloco da base (a dupla: qualquer metade serve)
            return machine in self.base.blocks and min(
                max(abs(x - px), abs(y - py)) for x, y in machine.tiles) <= C.PLACE_REACH
        return machine in self.machines and max(abs(machine.tx - px), abs(machine.ty - py)) <= C.PLACE_REACH

    def dismantle_returns(self, machine: Machine) -> dict[str, int]:
        """O que volta pro inventário desmontando: os materiais da receita (v0.5 M1: a máquina não é item), mais o
        que a drill guardou e, na estação, as sobras do buffer, a carga e os próprios drones."""
        out = dict(machine.type.cost)
        if machine.is_drill and machine.stored:
            out[machine.resource] = out.get(machine.resource, 0) + machine.stored
        if machine.is_melter or machine.is_dispenser:          # v0.5 M2: o gelo e as cápsulas que ficaram dentro
            for item, n in machine.storage.counts().items():
                out[item] = out.get(item, 0) + n
        if machine.is_station:
            for r, n in drones.recall_cargo(machine.station).items():
                out[r] = out.get(r, 0) + n
            if machine.station.drones:
                out["drone"] = len(machine.station.drones)
        return out

    def dismantle(self, machine: Machine) -> bool:
        """Desmonta na hora (quem chama é o segurar do botão direito, `_update_dismantle`): tira a máquina do mapa
        e devolve `dismantle_returns` pro inventário. Ou cabe tudo, ou nada muda (aviso de inventário cheio).
        O baú só desmonta vazio. A cápsula não é uma Machine, então nunca entra aqui."""
        if not self.can_dismantle(machine):
            return False
        if isinstance(machine, BaseBlock):
            return self._dismantle_block(machine)
        if machine.is_chest and not machine.storage.is_empty():
            self.events.append(("chest_not_empty",))
            return False
        returns = self.dismantle_returns(machine)
        trial = self.inventory.copy()
        if any(trial.add(item, n) for item, n in returns.items()):
            self.events.append(("inv_full",))
            return False
        if machine.is_drill and machine.stored:
            self.drill_collected[machine.resource] += machine.stored
        if machine.is_station:
            machine.station.drones.clear()                 # quem estava voando some junto (sem carga perdida)
        for item, n in returns.items():
            self.inventory.add(item, n)
        self.machines.remove(machine)
        self.events.append(("dismantle", machine.kind, (machine.tx, machine.ty)))
        return True

    def _dismantle_block(self, block: BaseBlock) -> bool:
        """Tira o bloco da base e devolve 1 receita (a dupla: qualquer metade tira as duas e devolve 1)."""
        returns = dict(block.type.cost)
        trial = self.inventory.copy()
        if any(trial.add(item, n) for item, n in returns.items()):
            self.events.append(("inv_full",))
            return False
        for item, n in returns.items():
            self.inventory.add(item, n)
        self.base.remove(block)
        self.events.append(("dismantle", block.kind, (block.tx, block.ty)))
        return True

    def _update_dismantle(self, target: Machine | None, dt: float) -> None:
        """Desmontar segurando (v0.5 M1): o botão direito segurado em cima de uma máquina no alcance enche
        `dismantle_t` até C.DISMANTLE_HOLD e aí desmonta. Soltar, tirar o mouse ou sair do alcance cancela. Eventos:
        ("dismantle_charge",) quando começa a encher e ("dismantle_cancel",) quando para sem completar. Depois de
        uma tentativa (completa ou não: inventário cheio, baú com coisa) a mesma máquina só carrega de novo soltando."""
        if target is None:
            self._dismantle_lock = None
        if target is not None and (target is self._dismantle_lock or not self.can_dismantle(target)):
            target = None
        if target is not self.dismantling:
            if self.dismantling is not None:
                self.events.append(("dismantle_cancel",))
            self.dismantling, self.dismantle_t = None, 0.0
            if target is None:
                return
            if target.is_chest and not target.storage.is_empty():   # nem começa: já avisa
                self.events.append(("chest_not_empty",))
                self._dismantle_lock = target
                return
            self.dismantling = target
            self.events.append(("dismantle_charge",))
        if self.dismantling is None:
            return
        self.dismantle_t += dt
        if self.dismantle_t >= C.DISMANTLE_HOLD:
            machine = self.dismantling
            self.dismantling, self.dismantle_t = None, 0.0
            self._dismantle_lock = machine
            if not self.dismantle(machine):                  # não coube: a máquina fica e o charge para
                self.events.append(("dismantle_cancel",))

    @property
    def dismantle_progress(self) -> float:
        """0..1 do desmonte segurado agora (0 sem nenhum)."""
        return min(1.0, self.dismantle_t / C.DISMANTLE_HOLD) if self.dismantling is not None else 0.0

    def _update_machines(self, dt: float) -> None:
        power = self.power
        if self.power_alert.update(power.deficit, dt):
            self.events.append(("power_low",))
        work_dt = dt * power.factor          # sem energia suficiente, tudo anda mais devagar
        for m in self.working_machines:      # as duas camadas produzem (drill na caverna também); submersa não
            if m.is_drill:
                self._update_drill(m, work_dt)
            elif m.type.index is not None:   # painel solar, baú e estação não somam Ti
                self.indices[m.type.index] += m.type.rate * work_dt
            if m.is_melter:
                self._update_melter(m, work_dt)
        if power.factor > 0:                 # v0.5 M2: o Dispersor gasta a cápsula (só vedado e ligado)
            for layer in self.layers.values():
                for m in layer.machines:
                    if m.is_dispenser and not m.submerged and m.build <= 0:
                        self._burn_capsules(m, layer, work_dt)
        stations = [m for m in self.surface.machines if m.is_station and m.build <= 0]
        if stations:                         # drones (game/drones.py): só na superfície; no déficit voam mais devagar
            self.drone_deliveries += drones.update_stations(stations, self.drone_logistics(), work_dt, self.events)
        self._check_stage()
        self._apply_thaw()                   # v0.4 M3: o calor muda o mapa (depois de somar os índices)

    # ---- derretimento (v0.4 Marco 3 · game/thaw.py) ---------------------------------
    def _apply_thaw(self) -> None:
        """Despachante do derretimento: tudo o que o índice muda no mapa sobe aqui (nunca desce) e solta os eventos.
        Chamado no fim do _update_machines e depois do load (game/save.py, que descarta os eventos do load)."""
        self._thaw_crater()
        self._thaw_fumaroles()
        self._thaw_gates()
        self._thaw_lake()
        self._thaw_submerged()               # depois do lago: quem ficou debaixo d'água para

    def _thaw_gates(self) -> None:
        """M3.5: o progresso p de cada gelo-portão sobe com o calor (thaw.gate_progress, nunca desce), os blocos de
        gelo encolhem junto com a colisão (Layer.refresh_gates) e sai um ("gate_thaw", i, etapa) quando o gelo
        começa a derreter (1) e quando a fresta abre pra caixa do player (3 = thaw.GATE_OPEN: aviso e som)."""
        surface = self.layers.get(SURFACE)
        geo = surface.geo if surface is not None else None
        if geo is None:
            return
        heat = self.indices["heat"]
        old_stage = list(surface.gate_ice)
        changed = False
        for i in range(len(geo.pockets)):
            p = max(surface.gate_melt[i], thaw.gate_progress(heat, i))
            if p != surface.gate_melt[i]:
                surface.gate_melt[i] = p
                changed = True
        if not changed:
            return
        surface.refresh_gates()
        for i, (was, now) in enumerate(zip(old_stage, surface.gate_ice)):
            for stage in (thaw.GATE_MELTING, thaw.GATE_OPEN):
                if was < stage <= now:
                    self.events.append(("gate_thaw", i, stage))

    def _thaw_lake(self) -> None:
        """M3.3: a água das bacias sobe com o índice de água (thaw.lake_level), só a partir da Névoa. O nível anda
        em degraus de C.LAKE_STEP (o render e o mapa refazem a água poucas vezes por minuto), mas cada marca
        L1/L2/L3 é batida exata e solta ("lake_rise", k) uma vez."""
        surface = self.surface
        if surface.geo is None or self.stage < C.MIST_STAGE:
            return
        old = surface.water_level
        target = lake_level(self.indices["water"])
        if target <= old:
            return
        crossed = [k for k, level in enumerate(C.GEO_LEVELS) if old < level <= target]
        if not crossed and target - old < C.LAKE_STEP:
            return
        surface.water_level = target
        for k in crossed:
            self.events.append(("lake_rise", k))

    def _thaw_submerged(self) -> None:
        """M3.4: a máquina da superfície com algum tile na água (o lago só sobe) fica `submerged` e solta
        ("submerged", kind, (tx, ty)) uma vez. Não dá pra construir na água, então só alaga quem já estava na bacia
        seca. A caverna nunca terraforma; a base (raio 16) fica sempre acima de L3."""
        surface = self.layers.get(SURFACE)
        if surface is None or surface.world.water_level <= 0:
            return
        world = surface.world
        for m in surface.machines:
            if not m.submerged and any(world.is_water(x, y, self.stage) for x, y in m.tiles):
                m.submerged = True
                self.events.append(("submerged", m.kind, (m.tx, m.ty)))

    def _thaw_crater(self) -> None:
        """M3.1: a tampa de gelo baixa com o calor (o F4 e um save com etapa maior ficam: nunca fecha de novo).
        Um ("crater_thaw", etapa) por etapa que desceu."""
        if SURFACE not in self.layers:
            return
        layer = self.surface
        target = thaw.crater_stage(self.indices["heat"])
        while layer.crater_ice < target:
            layer.crater_ice += 1
            self.events.append(("crater_thaw", layer.crater_ice))

    def _thaw_fumaroles(self) -> None:
        """M3.1: cada fumarola do basalto acorda no limiar dela (thaw.fumarole_active) e solta ("fumarole_wake", i).
        Quem decide se o aviso aparece (só com ela na tela) é o App."""
        if SURFACE not in self.layers:
            return
        awake = self.surface.vents_awake
        heat = self.indices["heat"]
        for i, on in enumerate(awake):
            if not on and thaw.fumarole_active(heat, i):
                awake[i] = True
                self.events.append(("fumarole_wake", i))

    def _check_stage(self) -> None:
        new_stage = stage_for_ti(self.ti)
        if new_stage > self.stage:          # estágio nunca volta
            self.stage = new_stage
            self.events.append(("stage_up", new_stage))

    def _update_storm(self, dt: float) -> None:
        """A tempestade some linear em STORM_FADE_S segundos (de jogo) depois que o estágio passa dela.
        Só desce: o jogo novo já nasce com storm 1.0 e o estágio nunca volta."""
        if self.stage <= C.STORM_STAGE or self.storm <= 0.0:
            return
        self.storm = max(0.0, self.storm - dt / C.STORM_FADE_S)
        if self.storm < 1e-6:                   # sem resto de float: quem lê pode testar storm == 0
            self.storm = 0.0

    # ---- rochas pequenas reaparecendo (game/rock_respawn.py) -----------------
    def _update_rocks(self, dt: float) -> list[tuple[int, int]]:
        """Rocha pequena nova na superfície (fora da vista do player, longe da base). Devolve os tiles novos."""
        surface = self.surface
        if surface.rocks is None:
            return []
        where = (self.player.x, self.player.y) if self.layer == SURFACE else C.SPAWN_POS
        born = surface.rocks.update(surface.world, self.rng, dt, where, surface.machines)
        # magmatita em volta das fumarolas (game/magmatite.py), com rng próprio: não mexe no sorteio das outras
        born += magmatite.respawn(surface.world, surface.vents_awake, surface.rocks.vent_timers, self.magma_rng, dt,
                                  where, surface.machines)
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

    def container_distance(self, tile: tuple[int, int]) -> float:
        """Dos pés até a base do contêiner lacrado (v0.4 M3.2)."""
        tx, ty = tile
        return math.hypot(self.player.x - (tx + 0.5) * C.TILE, self.player.y - (ty + 1) * C.TILE)

    def nearby_container(self) -> tuple[int, int] | None:
        near = [t for t in self.world.containers if self.container_distance(t) <= C.CONTAINER_REACH]
        return min(near, key=self.container_distance, default=None)

    def open_crate(self, crate: Crate) -> list[str]:
        """E na caixa: abre (som). Diagrama que estiver dentro NÃO é lido sozinho: fica na caixa como item, o player
        pega e lê na bancada. Dá o aviso "diagrama encontrado" (evento) e devolve os diagramas que a caixa tem."""
        crate.opened = True
        self.events.append(("crate_open", crate.empty))
        found = [C.DIAGRAM_ITEMS[st.item] for st in crate.storage.slots if st is not None and st.item in C.DIAGRAM_ITEMS]
        for diagram in found:
            self.events.append(("diagram_found", diagram))
        return found

    # ---- diagramas (v0.5 M1): item no inventário, lido na bancada ----------------------
    def diagrams_held(self) -> list[tuple[str, int]]:
        """Diagramas no inventário (mochila + hotbar): [(id da receita, quantos)], na ordem do config."""
        return [(d, n) for item, d in C.DIAGRAM_ITEMS.items() if (n := self.inventory.count(item)) > 0]

    @staticmethod
    def bench_reads(diagram: str, bench: str) -> bool:
        """A `bench` ("t1"/"t2") lê esse diagrama? Os de máquina (placeable) leem em qualquer bancada."""
        machine = C.MACHINES.get(C.RECIPE_BLUEPRINT.get(diagram, ""))
        return bool(machine and machine.placeable) or C.DIAGRAM_BENCH.get(diagram) == bench

    def read_diagram(self, item: str, bench: str) -> str:
        """Ler o diagrama `item` ("diagram_<id>") na `bench`. 'ok' (gastou 1 e liberou a receita pra sempre),
        'wrong_bench', 'known' (a receita já estava liberada: não gasta) ou 'none' (não tem / item inválido)."""
        diagram = C.DIAGRAM_ITEMS.get(item)
        if diagram is None or self.inventory.count(item) <= 0:
            return "none"
        if not self.bench_reads(diagram, bench):
            return "wrong_bench"
        if diagram in self.blueprints:
            return "known"
        self.inventory.remove(item, 1)
        self.blueprints.add(diagram)
        self.events.append(("diagram_read", diagram))
        return "ok"

    def crate_take(self, crate: Crate, index: int | None = None, amount: int | None = None) -> int:
        """Tira da caixa pro inventário: tudo (`index` None) ou o slot `index` (`amount` None = a pilha,
        1 = clique direito). Diagrama é item como os outros (ocupa slot). Devolve quantas unidades saíram."""
        indexes = range(len(crate.storage)) if index is None else [index]
        moved = want = 0
        for i in indexes:
            stack = crate.storage.slots[i]
            if stack is None:
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
        self.sync_backpack()
        return True

    def equip_item(self, item: str) -> str | None:
        """Encaixa um item que não está no inventário (a "mão" da tela do Tab). Devolve o que saiu do slot."""
        old = self.equipment.equip(item)
        self.equipped_ever.add(item)
        self.events.append(("equip", item))
        self._clamp_o2()
        self.sync_backpack()
        return old

    def unequip(self, kind: str) -> bool:
        """Tira o equipamento do slot e devolve pro inventário (sem espaço: fica, com o aviso)."""
        item = self.equipment.slots.get(kind)
        if item is None:
            return False
        if kind == "backpack":                       # só sai com a linha extra vazia (senão os itens sumiriam)
            if not self.inventory.tail_empty(C.INVENTORY_SLOTS):
                self.events.append(("backpack_not_empty",))
                return False
            base = self.inventory.copy()
            base.resize(C.INVENTORY_SLOTS)
            if not base.has_space(item):             # sem a mochila, os 16 slots têm que ter lugar pra ela
                self.events.append(("inv_full",))
                return False
        elif not self.inventory.has_space(item):
            self.events.append(("inv_full",))
            return False
        self.equipment.unequip(kind)
        self.sync_backpack()
        self.inventory.add(item, 1)
        self.events.append(("unequip", item))
        self._clamp_o2()
        return True

    @property
    def has_backpack(self) -> bool:
        return self.equipment.has("backpack")

    def sync_backpack(self) -> None:
        """Deixa o inventário com 16 slots (sem mochila) ou 24 (com ela). Encolher só corta slots vazios; se a
        linha extra tem item (save estragado), a mochila continua valendo e o inventário não encolhe."""
        want = C.INVENTORY_SLOTS + (C.BACKPACK_SLOTS if self.has_backpack else 0)
        if want > len(self.inventory) or self.inventory.tail_empty(want):
            self.inventory.resize(want)

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
        self._apply_thaw()                    # o calor do F2 já derrete (igual ao tick das máquinas)

    def debug_melt_crater(self) -> None:
        """F4 (debug): derrete a tampa de gelo da cratera na hora (no M2 é o único jeito de descer)."""
        self.surface.crater_ice = C.CRATER_ICE_STAGES
        self.debug_crater = True

    def toggle_time_scale(self) -> None:
        self.time_scale = C.DEBUG_TIME_SCALE if self.time_scale == 1 else 1

    def toggle_fast(self) -> None:
        """F3: liga/desliga o player rápido + broca rápida (pra testar sem andar e minerar tanto)."""
        self.fast = not self.fast

    @property
    def player_speed(self) -> float:
        """px/s do player (com o F3 ligado, DEBUG_SPEED× mais rápido)."""
        return C.PLAYER_SPEED * (C.DEBUG_SPEED if self.fast else 1)

    @property
    def mine_speed(self) -> float:
        """Multiplicador da broca (com o F3 ligado, DEBUG_MINE×): vale pra parede, minério e rocha pequena."""
        return C.DEBUG_MINE if self.fast else 1.0

    def pop_events(self) -> list[tuple]:
        events, self.events = self.events, []
        return events
