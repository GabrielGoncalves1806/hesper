"""Estação de drones e o ciclo de cada drone (bíblia §8, Marco 3).

Tudo aqui é Python puro (nada de pygame), testado em tests/test_drones.py.

A ideia, em uma frase: a estação tem 4 slots de drone (vem vazia; o drone é um item fabricado
e colocado num slot pelo painel da estação); cada drone pousado procura a drill mais cheia
(dentro de 30 tiles, com pelo menos 5 unidades e sem outro drone indo pra ela), voa em linha reta
até lá (por cima das paredes, então não precisa de caminho), pega TUDO, volta e entrega.

Ciclo de um drone (o `state` dele):

    pousado ──acha drill──> indo ──chegou──> coletando ──pegou──> voltando ──pousou──> entregando ──> pousado
    (landed)                (outbound)       (collecting)         (returning)          (delivering)

Entrega (pick_delivery_chest): entre os baús a até 6 tiles da estação, primeiro um com filtro igual
ao minério da carga, depois um "all", sempre o mais perto e só se tiver espaço; baú filtrado pra outro
minério nunca recebe. A carga é dividida entre quantos baús precisar e o resto vai pro buffer interno
da estação (50 unidades). Se nem o buffer tiver lugar, o drone fica pousado segurando
a carga (aparece a pepita nele) e tenta de novo a cada frame. Com o buffer cheio e sem baú com espaço,
nenhum drone decola.

Energia: quem chama passa o `dt` já multiplicado pelo fator da energia (game/energy.py), então com
pouca energia os drones só ficam mais lentos (voo e coleta), igual às outras máquinas.

Posições: (x, y) do drone é o CENTRO do desenho dele, em pixels do mundo. Voando, a sombra é
desenhada 18 px abaixo (C.DRONE_SHADOW_DROP); quem desenha é o render.py.
"""

import math
from dataclasses import dataclass, field

from game import config as C

LANDED, OUTBOUND, COLLECTING, RETURNING, DELIVERING = "landed", "outbound", "collecting", "returning", "delivering"
IN_AIR = (OUTBOUND, COLLECTING, RETURNING)   # estados em que o drone está voando (tem sombra)
MAX_STEP = 0.25   # segundos: um dt grande (simulador, F1) é quebrado em pedaços pra não "pular" a drill


@dataclass
class Drone:
    pad: int                       # 0 a 3: em qual slot da estação ele está (e onde pousa)
    x: float = 0.0
    y: float = 0.0
    state: str = LANDED
    target: object | None = None   # a drill (Machine) pra onde ele está indo
    resource: str | None = None    # minério que está carregando
    cargo: int = 0                 # quanto está carregando
    timer: float = 0.0             # tempo que falta pra coletar/entregar

    @property
    def in_air(self) -> bool:
        return self.state in IN_AIR

    @property
    def busy(self) -> bool:
        """Em viagem (voando, coletando ou entregando): o slot fica travado, não dá pra tirar."""
        return self.state != LANDED


@dataclass
class Station:
    """O que só a estação de drones tem: o buffer e os drones. Fica em `Machine.station`.

    `drones` tem só os drones que existem; cada um sabe o slot dele (`Drone.pad`, de 0 a 3).
    """
    buffer: dict[str, int] = field(default_factory=dict)   # {"iron": 12, "ice": 3}
    drones: list[Drone] = field(default_factory=list)
    warned: bool = False           # já avisou "Estação cheia" (rearma quando o buffer libera espaço)

    # ---- slots de drone
    def drone_in(self, slot: int) -> Drone | None:
        return next((d for d in self.drones if d.pad == slot), None)

    def free_slots(self) -> list[int]:
        return [i for i in range(C.STATION_DRONE_SLOTS) if self.drone_in(i) is None]

    def buffer_stacks(self) -> list[tuple[str, int]]:
        """O buffer como "slots" pra tela: [(minério, quantidade)] na ordem de C.RESOURCES.
        Cabe sempre numa pilha por minério (o buffer inteiro tem 50 = 1 pilha)."""
        return [(r, self.buffer[r]) for r in C.RESOURCES if self.buffer.get(r, 0) > 0]

    def take(self, resource: str, amount: int) -> int:
        """Tira até `amount` desse minério do buffer. Devolve quanto tirou."""
        moved = min(amount, self.buffer.get(resource, 0))
        if moved:
            self.buffer[resource] -= moved
            if self.buffer[resource] == 0:
                del self.buffer[resource]
        return moved

    @property
    def stored(self) -> int:
        return sum(self.buffer.values())

    @property
    def room(self) -> int:
        return max(0, C.STATION_BUFFER - self.stored)

    @property
    def full(self) -> bool:
        return self.room == 0

    def add(self, resource: str, amount: int) -> int:
        """Guarda no buffer o que couber. Devolve quanto NÃO coube."""
        moved = min(amount, self.room)
        if moved:
            self.buffer[resource] = self.buffer.get(resource, 0) + moved
        return amount - moved


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


def hover_position(drill) -> tuple[float, float]:
    """Onde o drone para no ar em cima da drill (a sombra cai nos tiles dela)."""
    ax, ay = drill.anchor
    return ax, ay - 56


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


def tile_distance(a, b) -> float:
    """Distância (tiles) entre os centros de duas máquinas."""
    (ax, ay), (bx, by) = a.anchor, b.anchor
    return math.hypot((ax - bx) / C.TILE, (ay - a.size * C.TILE / 2 - by + b.size * C.TILE / 2) / C.TILE)


def gap_tiles(station, chest) -> int:
    """Quantos tiles separam o baú da estação (0 = encostado). Conta a partir da borda dos 2×2."""
    dx = max(station.tx - chest.tx, 0, chest.tx - (station.tx + station.size - 1))
    dy = max(station.ty - chest.ty, 0, chest.ty - (station.ty + station.size - 1))
    return max(dx, dy)


@dataclass
class Spot:
    """Uma estação "de mentira" num tile (o fantasma de colocar): o mínimo que tile_distance e gap_tiles usam."""
    tx: int
    ty: int
    size: int = 2

    @property
    def anchor(self) -> tuple[float, float]:
        return (self.tx + self.size / 2) * C.TILE, (self.ty + self.size) * C.TILE


def range_center(station) -> tuple[float, float]:
    """Centro do círculo de alcance (pixels do mundo): o meio dos 2×2 da estação."""
    ax, ay = station.anchor
    return ax, ay - station.size * C.TILE / 2


def drills_in_range(station, drills) -> list:
    """Drills que os drones dessa estação alcançam (mesma conta do pick_drill)."""
    return [d for d in drills if tile_distance(station, d) <= C.DRONE_RANGE]


def delivery_rect(station) -> tuple[int, int, int, int]:
    """Área de entrega em tiles (x, y, largura, altura): até 6 tiles da borda da estação, num quadrado,
    igual à conta do gap_tiles (não é um círculo)."""
    r = C.DRONE_CHEST_RADIUS
    return station.tx - r, station.ty - r, station.size + 2 * r, station.size + 2 * r


def delivers_to(stations, tile: tuple[int, int]) -> bool:
    """Um baú nesse tile recebe entrega de alguma das estações?"""
    chest = Spot(tile[0], tile[1], 1)
    return any(gap_tiles(s, chest) <= C.DRONE_CHEST_RADIUS for s in stations)


# ---------------------------------------------------------------- escolhas
def new_station(machine, count: int = 0) -> Station:
    """Estação recém-colocada: buffer vazio e sem drone (a não ser que `count` peça alguns, nos
    primeiros slots: o save v3 e os testes usam isso)."""
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


def pick_drill(machine, drills, claimed: set[int]):
    """A drill mais cheia ao alcance, com ≥ DRONE_MIN_PICKUP e sem drone indo pra ela (empate: a mais perto)."""
    options = [d for d in drills
               if d.stored >= C.DRONE_MIN_PICKUP and id(d) not in claimed
               and tile_distance(machine, d) <= C.DRONE_RANGE]
    return max(options, key=lambda d: (d.stored, -tile_distance(machine, d)), default=None)


def pick_delivery_chest(station, chests, resource: str, radius: int = C.DRONE_CHEST_RADIUS):
    """Em qual baú o drone entrega `resource` agora (ou None = vai pro buffer da estação).

    Só conta baú a até `radius` tiles da estação e com espaço pra esse minério. Prioridade: filtro
    igual ao minério > filtro "all"; empate: o mais perto da estação. Baú filtrado pra outro minério
    nunca recebe. Carga maior que o espaço: quem chama entrega o que cabe e chama de novo (o baú
    cheio sai da lista sozinho)."""
    options = [c for c in chests
               if c.filter in (resource, "all") and gap_tiles(station, c) <= radius
               and c.storage.space_for(resource) > 0]
    return min(options, key=lambda c: (c.filter != resource, gap_tiles(station, c), tile_distance(station, c)),
               default=None)


def can_accept(machine, chests) -> bool:
    """Ainda tem onde guardar minério? (lugar no buffer, ou algum baú perto aceita algum minério)"""
    if machine.station.room > 0:
        return True
    return any(pick_delivery_chest(machine, chests, r) is not None for r in C.RESOURCES)


# ---------------------------------------------------------------- ciclo
def _exists(machine, machines) -> bool:
    """A máquina ainda está no mapa? (por identidade: `in` compararia campo a campo)"""
    return any(m is machine for m in machines)


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


def unload(machine, drone: Drone, chests, events: list) -> int:
    """Entrega a carga do drone: baús perto (pick_delivery_chest, quantos precisar), depois o buffer.
    O que não couber fica no drone. Devolve quanto entregou."""
    if drone.cargo <= 0:
        return 0
    resource, amount = drone.resource, drone.cargo
    to_chest, first_chest = 0, None
    while amount > 0:
        chest = pick_delivery_chest(machine, chests, resource)
        if chest is None:
            break
        left = chest.storage.add(resource, amount)
        to_chest, amount = to_chest + amount - left, left
        first_chest = first_chest or chest
    to_buffer = amount - machine.station.add(resource, amount)
    amount -= to_buffer
    drone.cargo = amount
    if amount == 0:
        drone.resource = None
    delivered = to_chest + to_buffer
    if delivered:
        where = first_chest.anchor if to_chest else machine.anchor
        events.append(("drone_deliver", resource, delivered, where))
    return delivered


def update_drone(machine, drone: Drone, drills, chests, claimed: set[int], dt: float, events: list) -> int:
    """Um passo do ciclo de um drone. Devolve quantas entregas ele fez (0 ou 1)."""
    delivered = 0
    if drone.state == LANDED:
        if drone.cargo:                                   # voltou (ou carregou o save) com carga: tenta de novo
            delivered = 1 if unload(machine, drone, chests, events) else 0
        if drone.cargo == 0 and can_accept(machine, chests):
            drill = pick_drill(machine, drills, claimed)
            if drill is not None:
                claimed.add(id(drill))
                drone.target, drone.state = drill, OUTBOUND
    elif drone.state == OUTBOUND:
        if not _exists(drone.target, drills):                    # a drill foi desmontada no caminho: volta vazio
            drone.target, drone.state = None, RETURNING
        elif _fly(drone, *hover_position(drone.target), dt):
            drone.state, drone.timer = COLLECTING, C.DRONE_PICKUP_TIME
    elif drone.state == COLLECTING:
        drone.timer -= dt
        if drone.timer <= 0:
            drill = drone.target
            if _exists(drill, drills) and drill.stored > 0:      # pega TUDO (se o player coletou antes, volta vazio)
                drone.resource, drone.cargo = drill.resource, drill.stored
                drill.stored = 0
            drone.target, drone.state = None, RETURNING
    elif drone.state == RETURNING:
        if _fly(drone, *pad_position(machine, drone.pad), dt):
            if drone.cargo:
                drone.state, drone.timer = DELIVERING, C.DRONE_DROP_TIME
            else:
                drone.state = LANDED
    elif drone.state == DELIVERING:
        drone.timer -= dt
        if drone.timer <= 0:
            drone.state = LANDED
            delivered = 1 if unload(machine, drone, chests, events) else 0
    return delivered


def update_stations(stations, drills, chests, dt: float, events: list) -> int:
    """Roda todos os drones de todas as estações por `dt` segundos (já com o fator da energia).
    Devolve quantas entregas aconteceram (pro objetivo "Receba uma entrega de drone")."""
    deliveries = 0
    while dt > 1e-9:
        step = min(dt, MAX_STEP)
        dt -= step
        # drills que já têm drone indo (vale pra todas as estações: nunca dois drones na mesma drill)
        claimed = {id(d.target) for m in stations for d in m.station.drones if d.target is not None}
        for machine in stations:
            for drone in machine.station.drones:
                deliveries += update_drone(machine, drone, drills, chests, claimed, step, events)
            station = machine.station
            if station.full and not station.warned:       # avisa uma vez quando o buffer enche
                station.warned = True
                events.append(("station_full", machine.anchor))
            elif not station.full:
                station.warned = False
    return deliveries


def recall_cargo(station: Station) -> dict[str, int]:
    """Todo o minério da estação: buffer + o que os drones estão carregando (pra desmontar sem perder nada).
    Os drones em si (itens) quem devolve é o GameState._dismantle_station."""
    total = dict(station.buffer)
    for d in station.drones:
        if d.cargo:
            total[d.resource] = total.get(d.resource, 0) + d.cargo
    return total
