"""Estação de drones e a logística deles (bíblia §8, Marco 3), no estilo do The Planet Crafter.

Tudo aqui é Python puro (nada de pygame), testado em tests/test_drones.py e tests/test_logistics.py.

A ideia, em uma frase: cada inventário logístico (baú e drill) diz o que ENVIA (os drones podem tirar
dali), o que RECEBE (os drones trazem pra lá) e o LOTE (quanto um drone tira dali por viagem). Um drone
livre, pousado na estação, procura um par origem → destino pra algum item, no MAPA INTEIRO (não tem
alcance), voa em linha reta por cima das paredes, pega, entrega e volta pra estação.

Ciclo de um drone (o `state` dele):

    pousado ──acha par──> indo ──chegou──> pegando ──pegou──> levando ──chegou──> soltando ──> voltando ──> pousado
    (landed)              (outbound)       (collecting)       (carrying)          (dropping)    (returning)

Escolha do par (pick_task): origem com estoque livre do item (já descontando o que outros drones vão
buscar) e destino com espaço livre (já descontando o que outros drones vão trazer). Drill só é origem
quando tem pelo menos o lote (ou está cheia); baú, com qualquer estoque. Ganha a origem mais cheia;
empate (e escolha do destino): a viagem mais curta estação → origem → destino → estação.
Leva min(lote da origem, estoque livre, espaço livre no destino), um item por viagem.

Destino encheu (ou sumiu) no meio do caminho: entrega o que couber e procura outro destino que receba
o item; sem nenhum, volta pra estação com a carga e fica pousado segurando ela, até surgir um destino.
Nada some.

O buffer da estação é legado (save ≤ v4): não recebe mais nada, só dá pra tirar as sobras.

Energia: quem chama passa o `dt` já multiplicado pelo fator da energia (game/energy.py), então com
pouca energia os drones só ficam mais lentos (voo e coleta), igual às outras máquinas.

Posições: (x, y) do drone é o CENTRO do desenho dele, em pixels do mundo. Voando, a sombra é
desenhada 18 px abaixo (C.DRONE_SHADOW_DROP); quem desenha é o render.py.
"""

import math
from dataclasses import dataclass, field

from game import config as C
from game.inventory import Inventory

LANDED, OUTBOUND, COLLECTING, CARRYING, DROPPING, RETURNING = (
    "landed", "outbound", "collecting", "carrying", "dropping", "returning")
IN_AIR = (OUTBOUND, COLLECTING, CARRYING, DROPPING, RETURNING)   # estados em que o drone está voando
MAX_STEP = 0.25   # segundos: um dt grande (simulador, F1) é quebrado em pedaços pra não "pular" o alvo


@dataclass
class Drone:
    pad: int                       # 0 a 3: em qual slot da estação ele está (e onde pousa)
    x: float = 0.0
    y: float = 0.0
    state: str = LANDED
    source: object | None = None   # origem (Machine) de onde vai tirar
    dest: object | None = None     # destino (Machine) pra onde leva
    resource: str | None = None    # item da viagem (o que vai buscar ou está carregando)
    planned: int = 0               # quanto vai pegar na origem (fica reservado até pegar)
    cargo: int = 0                 # quanto está carregando
    timer: float = 0.0             # tempo que falta pra pegar/soltar (pousado: até procurar tarefa de novo)

    @property
    def in_air(self) -> bool:
        return self.state in IN_AIR

    @property
    def busy(self) -> bool:
        """Em viagem: o slot fica travado, não dá pra tirar."""
        return self.state != LANDED


@dataclass
class Station:
    """O que só a estação de drones tem: os drones e o buffer legado. Fica em `Machine.station`.

    `drones` tem só os drones que existem; cada um sabe o slot dele (`Drone.pad`, de 0 a 3).
    """
    buffer: dict[str, int] = field(default_factory=dict)   # sobras de save antigo: {"iron": 12}, só tirar
    drones: list[Drone] = field(default_factory=list)

    # ---- slots de drone
    def drone_in(self, slot: int) -> Drone | None:
        return next((d for d in self.drones if d.pad == slot), None)

    def free_slots(self) -> list[int]:
        return [i for i in range(C.STATION_DRONE_SLOTS) if self.drone_in(i) is None]

    def buffer_stacks(self) -> list[tuple[str, int]]:
        """As sobras como "slots" pra tela: [(minério, quantidade)] na ordem de C.RESOURCES."""
        return [(r, self.buffer[r]) for r in C.RESOURCES if self.buffer.get(r, 0) > 0]

    def take(self, resource: str, amount: int) -> int:
        """Tira até `amount` desse minério das sobras. Devolve quanto tirou."""
        moved = min(amount, self.buffer.get(resource, 0))
        if moved:
            self.buffer[resource] -= moved
            if self.buffer[resource] == 0:
                del self.buffer[resource]
        return moved

    @property
    def stored(self) -> int:
        return sum(self.buffer.values())


# ---------------------------------------------------------------- geometria
def pad_position(machine, pad: int) -> tuple[float, float]:
    """Centro do drone pousado no pad `pad` (pixels do mundo).

    O PNG da estação (64×72) é desenhado com o canto em (ax − 32, ay − 72), onde (ax, ay) é o centro
    da base 2×2. O drone pousado (16×16) vai em (canto + pad − (8, 10)): o centro dele fica em
    (canto + pad − (0, 2)).
    """
    ax, ay = machine.anchor
    w, h = C.DRONE_STATION_SPRITE_SIZE
    px, py = C.DRONE_PADS[pad]
    return ax - w / 2 + px, ay - h + py - 2


def hover_position(machine) -> tuple[float, float]:
    """Onde o drone para no ar em cima de um inventário (drill 2×2 ou baú 1×1): a sombra cai nele."""
    ax, ay = machine.anchor
    return ax, ay - (56 if machine.size > 1 else 44)


LIFT_TIME = 0.35   # segundos (na velocidade cheia) que o drone leva pra subir ou descer


def lift(machine, drone: Drone) -> float:
    """Altura do drone de 0 (pousado) a 1 (voando), pra sombra e o balanço (o render.py desenha).

    Sai da distância até o pad dele: nos primeiros LIFT_TIME × velocidade px depois de decolar ele vai
    subindo, e nos últimos antes de pousar vai descendo. Por ser pela distância (e não por um relógio),
    o pouso termina exatamente quando ele encosta no pad, e com pouca energia (voo mais lento) a subida
    fica mais lenta junto. Pousado ou entregando: 0."""
    if not drone.in_air:
        return 0.0
    px, py = pad_position(machine, drone.pad)
    ramp = C.DRONE_SPEED * C.TILE * LIFT_TIME
    return min(1.0, math.hypot(drone.x - px, drone.y - py) / ramp)


# ---------------------------------------------------------------- só visual: drones na mesma rota
# Vários drones indo pro mesmo lugar voariam no mesmo ponto e pareceriam um só. Cada um ganha uma
# "faixa" estável pelo slot dele: um deslocamento de lado (perpendicular ao voo), uma altura e, parado
# em cima de um inventário, um ponto diferente em volta do alvo. Só o desenho muda: (x, y) do drone, a
# chegada e o resto da lógica continuam iguais. Quem suaviza a troca de um pro outro é o render.py.
# Formação em losango, por slot: (de lado, pra frente) em px, relativo à direção do voo. Os dois primeiros
# lado a lado (16 px = um drone), o 3º atrás e o 4º na frente, no meio.
FORMATION = ((-8.0, 0.0), (8.0, 0.0), (0.0, -13.0), (0.0, 13.0))
ALTITUDES = (0, 3, 6, 2)          # px a mais de altura (o drone sobe, a sombra fica no chão), por slot
# Pegando/soltando: cada slot num ponto em volta do alvo (visão de cima: elipse mais larga que alta).
SPOT_RX, SPOT_RY = 13.0, 8.0
SPOT_ANGLES = (math.pi, 0.0, -math.pi / 2, math.pi / 2)   # esquerda, direita, atrás (em cima), na frente
EASE_RATE = 6.0                   # por segundo: quão rápido o desenho troca de faixa/ponto


def _station_jitter(machine) -> float:
    """-1, 0 ou 1, fixo por estação: drones do mesmo slot em estações diferentes não ficam colados."""
    return float((machine.tx * 7 + machine.ty * 13) % 3 - 1)


def flight_target(machine, drone: Drone) -> tuple[float, float] | None:
    """Pra onde o drone está voando agora (None: parado no ar pegando/soltando, ou pousado)."""
    if drone.state == OUTBOUND and drone.source is not None:
        return hover_position(drone.source)
    if drone.state == CARRYING and drone.dest is not None:
        return hover_position(drone.dest)
    if drone.state == RETURNING:
        return pad_position(machine, drone.pad)
    return None


def visual_offset(machine, drone: Drone) -> tuple[float, float]:
    """Deslocamento (px do mundo) que o desenho do drone QUER ter: o lugar dele na formação (de lado e
    pra frente/trás, pelo slot) enquanto voa, ou o ponto dele em volta do alvo enquanto pega/solta.
    Pousado: (0, 0). Não mexe no drone."""
    if not drone.in_air:
        return 0.0, 0.0
    jitter = _station_jitter(machine)
    slot = drone.pad % len(FORMATION)
    target = flight_target(machine, drone)
    if target is not None:
        dx, dy = target[0] - drone.x, target[1] - drone.y
        dist = math.hypot(dx, dy)
        if dist > 1e-6:
            ux, uy = dx / dist, dy / dist                 # pra frente
            side, ahead = FORMATION[slot]
            side += jitter * 2
            return -uy * side + ux * ahead, ux * side + uy * ahead
    angle = SPOT_ANGLES[slot] + jitter * 0.3
    return math.cos(angle) * SPOT_RX, math.sin(angle) * SPOT_RY


def altitude(drone: Drone) -> int:
    """Altura extra (px) do desenho do drone, pelo slot."""
    return ALTITUDES[drone.pad % len(ALTITUDES)]


def ease(current: tuple[float, float], goal: tuple[float, float], dt: float,
         rate: float = EASE_RATE) -> tuple[float, float]:
    """Anda de `current` pra `goal` suavemente (exponencial): nada de pulo quando o drone troca de rota."""
    k = 1.0 - math.exp(-rate * max(0.0, dt))
    return current[0] + (goal[0] - current[0]) * k, current[1] + (goal[1] - current[1]) * k


def tile_distance(a, b) -> float:
    """Distância (tiles) entre os centros de duas máquinas."""
    (ax, ay), (bx, by) = center(a), center(b)
    return math.hypot(ax - bx, ay - by) / C.TILE


def center(machine) -> tuple[float, float]:
    """Centro dos tiles da máquina (pixels do mundo)."""
    ax, ay = machine.anchor
    return ax, ay - machine.size * C.TILE / 2


# ---------------------------------------------------------------- configuração (Envia / Recebe / Lote)
def is_logistic(machine) -> bool:
    """Baú, drill e derretedor têm inventário que os drones atendem."""
    return machine.is_logistic


def can_send(machine, item: str) -> bool:
    """A drill só tem o minério dela pra enviar, o derretedor só a cápsula (o gelo da entrada é dele); o baú,
    qualquer item logístico."""
    if item not in C.LOGISTIC_ITEMS:
        return False
    if machine.is_melter:
        return item == "water_capsule"
    return not machine.is_drill or item == machine.resource


def can_receive(machine, item: str) -> bool:
    """Drill e derretedor não recebem (só produzem: abastecer o derretedor de gelo é do v0.6)."""
    return item in C.LOGISTIC_ITEMS and not machine.is_producer


def toggle_send(machine, item: str) -> bool:
    """Liga/desliga Envia desse item. Ligar tira o item do Recebe. False se não pode."""
    if not can_send(machine, item):
        return False
    if item in machine.sends:
        machine.sends.discard(item)
    else:
        machine.sends.add(item)
        machine.receives.discard(item)
    return True


def toggle_receive(machine, item: str) -> bool:
    """Liga/desliga Recebe desse item. Ligar tira o item do Envia. False se não pode."""
    if not can_receive(machine, item):
        return False
    if item in machine.receives:
        machine.receives.discard(item)
    else:
        machine.receives.add(item)
        machine.sends.discard(item)
    return True


def set_batch(machine, amount: int) -> bool:
    if amount not in C.DRONE_BATCH_OPTIONS:
        return False
    machine.batch = amount
    return True


def configured(machine) -> bool:
    return bool(machine.sends or machine.receives)


# ---------------------------------------------------------------- reservas
class Ledger:
    """O que os drones em viagem já "prometeram": estoque que vão tirar de cada origem e itens que vão
    pôr em cada destino. Recalculado a cada passo (não vai no save) e atualizado quando um drone pega tarefa."""

    def __init__(self, stations=()):
        self.taking: dict[tuple[int, str], int] = {}
        self.incoming: dict[int, list[tuple[str, int]]] = {}
        for m in stations:
            for d in m.station.drones:
                if d.state in (OUTBOUND, COLLECTING) and d.source is not None:
                    self.take(d.source, d.resource, d.planned)
                    if d.dest is not None:
                        self.bring(d.dest, d.resource, d.planned)
                elif d.state in (CARRYING, DROPPING) and d.dest is not None:
                    self.bring(d.dest, d.resource, d.cargo)

    def take(self, source, item: str, amount: int) -> None:
        key = (id(source), item)
        self.taking[key] = self.taking.get(key, 0) + amount

    def bring(self, dest, item: str, amount: int) -> None:
        self.incoming.setdefault(id(dest), []).append((item, amount))

    def available(self, source, item: str) -> int:
        """Estoque que ninguém reservou ainda."""
        return max(0, source.storage.count(item) - self.taking.get((id(source), item), 0))

    def room(self, dest, item: str) -> int:
        """Espaço livre pro item, como se o que já está vindo pra cá tivesse chegado."""
        if not can_receive(dest, item):
            return 0
        promised = self.incoming.get(id(dest))
        if not promised:
            return dest.storage.space_for(item)
        trial = dest.storage.copy()
        for it, n in promised:
            trial.add(it, n)
        return trial.space_for(item)


# ---------------------------------------------------------------- escolhas
@dataclass
class Task:
    source: object
    dest: object
    item: str
    amount: int


def ready_stock(source, item: str, ledger: Ledger) -> int:
    """Quanto dá pra tirar da origem agora (0 = ainda não vale a viagem).
    Drill: só com o lote completo (ou cheia), pra não buscar de 1 em 1. Baú: qualquer estoque."""
    avail = ledger.available(source, item)
    if source.is_drill and avail < source.batch and not source.full:
        return 0
    return avail


def pick_task(station, logistics, ledger: Ledger) -> Task | None:
    """O melhor par origem → destino pra um drone dessa estação (ou None).
    Origem mais cheia primeiro; empate, e escolha do destino: a viagem mais curta."""
    best, best_key = None, None
    for src in logistics:
        for item in sorted(src.sends):
            avail = ready_stock(src, item, ledger)
            if avail <= 0:
                continue
            for dst in logistics:
                if dst is src or item not in dst.receives:
                    continue
                room = ledger.room(dst, item)
                if room <= 0:
                    continue
                trip = tile_distance(station, src) + tile_distance(src, dst) + tile_distance(dst, station)
                key = (-avail, trip)
                if best_key is None or key < best_key:
                    best_key = key
                    best = Task(src, dst, item, min(src.batch, avail, room))
    return best


def pick_dest(item: str, near, logistics, ledger: Ledger, exclude=None):
    """Destino pra carga que já está no drone: o mais perto de `near` (x, y em pixels) que Recebe o item e
    tem espaço. None se não tem nenhum."""
    options = [m for m in logistics
               if m is not exclude and item in m.receives and ledger.room(m, item) > 0]
    return min(options, key=lambda m: math.hypot(center(m)[0] - near[0], center(m)[1] - near[1]), default=None)


# ---------------------------------------------------------------- estação
def new_station(machine, count: int = 0) -> Station:
    """Estação recém-colocada: sem drone (a não ser que `count` peça alguns, nos primeiros slots:
    a migração e os testes usam isso)."""
    station = Station()
    for _ in range(count):
        dock(machine, station)
    return station


def dock(machine, station: Station, slot: int | None = None) -> Drone | None:
    """Põe um drone novo (pousado) num slot livre (ou no `slot` pedido). None se não tem lugar."""
    free = station.free_slots()
    if slot is None:
        slot = free[0] if free else None
    if slot is None or slot not in free:
        return None
    x, y = pad_position(machine, slot)
    drone = Drone(slot, x, y)
    station.drones.append(drone)
    station.drones.sort(key=lambda d: d.pad)
    return drone


def undock(station: Station, slot: int) -> Drone | None:
    """Tira o drone do slot, só se ele estiver pousado (em viagem o slot fica travado). None se não deu."""
    drone = station.drone_in(slot)
    if drone is None or drone.busy:
        return None
    station.drones.remove(drone)
    return drone


# ---------------------------------------------------------------- ciclo
def _exists(machine, machines) -> bool:
    """A máquina ainda está no mapa? (por identidade: `in` compararia campo a campo)"""
    return machine is not None and any(m is machine for m in machines)


def _fly(drone: Drone, tx: float, ty: float, dt: float) -> bool:
    """Anda em linha reta até (tx, ty). Devolve True quando chega."""
    step = C.DRONE_SPEED * C.TILE * dt
    dx, dy = tx - drone.x, ty - drone.y
    dist = math.hypot(dx, dy)
    if dist <= step:
        drone.x, drone.y = tx, ty
        return True
    drone.x += dx / dist * step
    drone.y += dy / dist * step
    return False


def _carry_on(drone: Drone, logistics, ledger: Ledger, exclude=None) -> None:
    """Com carga na mão: vai pra um destino que receba o item, ou volta pra estação segurando ela."""
    dest = pick_dest(drone.resource, (drone.x, drone.y), logistics, ledger, exclude)
    if dest is not None:
        ledger.bring(dest, drone.resource, drone.cargo)
        drone.dest, drone.state = dest, CARRYING
    else:
        drone.dest, drone.state = None, RETURNING


def _finish_trip(drone: Drone) -> None:
    drone.source = drone.dest = None
    drone.planned = 0
    if drone.cargo == 0:
        drone.resource = None


def update_drone(machine, drone: Drone, logistics, ledger: Ledger, dt: float, events: list) -> int:
    """Um passo do ciclo de um drone. Devolve quantas entregas ele fez (0 ou 1)."""
    if drone.state == LANDED and getattr(machine, "submerged", False):
        return 0                                         # v0.4 M3.4: estação debaixo d'água não manda drone
    if drone.state == LANDED:
        drone.timer -= dt
        if drone.timer > 0:
            return 0
        drone.timer = C.DRONE_IDLE_RETRY
        if drone.cargo:                                  # pousou (ou carregou o save) com carga: entrega antes
            dest = pick_dest(drone.resource, (drone.x, drone.y), logistics, ledger)
            if dest is not None:
                ledger.bring(dest, drone.resource, drone.cargo)
                drone.dest, drone.state = dest, CARRYING
            return 0
        task = pick_task(machine, logistics, ledger)
        if task is not None:
            ledger.take(task.source, task.item, task.amount)
            ledger.bring(task.dest, task.item, task.amount)
            drone.source, drone.dest, drone.resource, drone.planned = task.source, task.dest, task.item, task.amount
            drone.state = OUTBOUND
    elif drone.state == OUTBOUND:
        if not _exists(drone.source, logistics):         # a origem foi desmontada no caminho: volta vazio
            _finish_trip(drone)
            drone.state = RETURNING
        elif _fly(drone, *hover_position(drone.source), dt):
            drone.state, drone.timer = COLLECTING, C.DRONE_PICKUP_TIME
    elif drone.state == COLLECTING:
        drone.timer -= dt
        if drone.timer <= 0:
            src, item = drone.source, drone.resource
            got = src.storage.remove(item, drone.planned) if _exists(src, logistics) else 0
            drone.source, drone.planned = None, 0
            if got:
                drone.cargo = got
                if _exists(drone.dest, logistics) and item in drone.dest.receives:
                    drone.state = CARRYING
                else:                                    # o destino sumiu (ou mudou a config) enquanto pegava
                    _carry_on(drone, logistics, ledger)
            else:                                        # o player esvaziou antes: volta vazio
                _finish_trip(drone)
                drone.state = RETURNING
    elif drone.state == CARRYING:
        if not _exists(drone.dest, logistics) or drone.resource not in drone.dest.receives:
            _carry_on(drone, logistics, ledger, exclude=drone.dest)
        elif _fly(drone, *hover_position(drone.dest), dt):
            drone.state, drone.timer = DROPPING, C.DRONE_DROP_TIME
    elif drone.state == DROPPING:
        drone.timer -= dt
        if drone.timer <= 0:
            dest, item = drone.dest, drone.resource
            delivered = 0
            if _exists(dest, logistics) and item in dest.receives:
                delivered = drone.cargo - dest.storage.add(item, drone.cargo)
                drone.cargo -= delivered
            if delivered:
                events.append(("drone_deliver", item, delivered, dest.anchor))
            if drone.cargo:                              # encheu no meio do caminho: procura outro destino
                _carry_on(drone, logistics, ledger, exclude=dest)
            else:
                _finish_trip(drone)
                drone.state = RETURNING
            return 1 if delivered else 0
    elif drone.state == RETURNING:
        if _fly(drone, *pad_position(machine, drone.pad), dt):
            _finish_trip(drone)
            drone.state, drone.timer = LANDED, 0.0
    return 0


def update_stations(stations, logistics, dt: float, events: list) -> int:
    """Roda todos os drones de todas as estações por `dt` segundos (já com o fator da energia).
    `logistics` = baús e drills do mapa. Devolve quantas entregas aconteceram (objetivo "Receba uma entrega")."""
    deliveries = 0
    logistics = list(logistics)
    while dt > 1e-9:
        step = min(dt, MAX_STEP)
        dt -= step
        ledger = Ledger(stations)                        # reservas de todas as estações juntas
        for machine in stations:
            for drone in machine.station.drones:
                deliveries += update_drone(machine, drone, logistics, ledger, step, events)
    return deliveries


def recall_cargo(station: Station) -> dict[str, int]:
    """Todo o minério da estação: sobras + o que os drones estão carregando (pra desmontar sem perder nada).
    Os drones em si (itens) quem devolve é o GameState._dismantle_station."""
    total = dict(station.buffer)
    for d in station.drones:
        if d.cargo:
            total[d.resource] = total.get(d.resource, 0) + d.cargo
    return total


def new_drill_storage() -> Inventory:
    return Inventory(C.DRILL_SLOTS)
