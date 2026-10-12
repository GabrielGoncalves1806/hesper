"""Recursos soltos no chão da superfície: ferro, silício e gelo em 1 a 3 unidades (bíblia §9, Marco 1).

- Num jogo novo já tem `PICKUP_START` espalhados (sorteio pela seed: mesmo deserto, mesmos soltos).
- O jogador pega passando por cima (raio pequeno nos pés) ou com E/clique no alcance (systems.py).
- Reaparecem devagar (1 a cada `PICKUP_RESPAWN` s), só onde o jogador não está vendo (fora da
  meia-tela do zoom mais afastado) e longe da base, até o teto `PICKUP_MAX`.

Posição: (x, y) é o centro do solto no chão, em pixels do mundo (o meio de um tile).
Python puro (sem pygame), testado em tests/test_pickups.py.
"""

import random
from dataclasses import dataclass

from game import config as C


@dataclass
class Pickup:
    resource: str
    amount: int
    x: float
    y: float

    @property
    def tile(self) -> tuple[int, int]:
        return int(self.x // C.TILE), int(self.y // C.TILE)


def hidden_from(player_xy, tx: int, ty: int) -> bool:
    """O tile (tx, ty) está fora da tela do jogador (no zoom mais afastado, com folga)?"""
    px, py = player_xy
    hx, hy = C.PICKUP_HIDDEN
    return abs(tx + 0.5 - px / C.TILE) > hx or abs(ty + 0.5 - py / C.TILE) > hy


def can_spawn(world, tx: int, ty: int, min_base: float, taken=()) -> bool:
    """Areia livre (sem veio, sem outro solto, fora de onde vai virar lago) e longe o bastante da base."""
    return (world.is_floor(tx, ty) and world.vein_at(tx, ty) is None and (tx, ty) not in taken
            and world.dist_from_center(tx, ty) >= min_base and not world.is_water(tx, ty, 3))


def pick_resource(r: float) -> str:
    acc = 0.0
    for resource, weight in C.PICKUP_WEIGHTS.items():
        acc += weight
        if r < acc:
            return resource
    return resource


def _new(rng: random.Random, tx: int, ty: int) -> Pickup:
    return Pickup(pick_resource(rng.random()), rng.randint(*C.PICKUP_AMOUNT), (tx + 0.5) * C.TILE, (ty + 0.5) * C.TILE)


class Pickups:
    def __init__(self, items: list[Pickup] | None = None, timer: float = 0.0):
        self.items: list[Pickup] = items if items is not None else []
        self.timer = timer            # segundos acumulados pro próximo reaparecimento

    @classmethod
    def generate(cls, world, seed: int) -> "Pickups":
        """Os soltos de um jogo novo, sorteados pela seed."""
        rng = random.Random(seed * 104729 + 7)
        out = cls()
        taken = set()
        while len(out.items) < C.PICKUP_START:
            tx, ty = rng.randrange(world.width), rng.randrange(world.height)
            if can_spawn(world, tx, ty, C.PICKUP_START_BASE_DIST, taken):
                out.items.append(_new(rng, tx, ty))
                taken.add((tx, ty))
        return out

    def update(self, world, rng: random.Random, dt: float, player_xy) -> list[Pickup]:
        """Reaparecimento: soma o tempo e cria 1 solto a cada PICKUP_RESPAWN s (até o teto).
        Devolve os que nasceram agora."""
        if len(self.items) >= C.PICKUP_MAX:
            self.timer = 0.0
            return []
        self.timer += dt
        born = []
        taken = {p.tile for p in self.items}
        while self.timer >= C.PICKUP_RESPAWN and len(self.items) < C.PICKUP_MAX:
            self.timer -= C.PICKUP_RESPAWN
            for _ in range(200):
                tx, ty = rng.randrange(world.width), rng.randrange(world.height)
                if can_spawn(world, tx, ty, C.PICKUP_BASE_DIST, taken) and hidden_from(player_xy, tx, ty):
                    p = _new(rng, tx, ty)
                    self.items.append(p)
                    born.append(p)
                    taken.add((tx, ty))
                    break
        return born

    # ---- consultas ---------------------------------------------------------------------
    def touching(self, x: float, y: float, radius: float = C.PICKUP_AUTO_RADIUS) -> list[Pickup]:
        """Soltos a até `radius` px do ponto (os pés do player)."""
        r2 = radius * radius
        return [p for p in self.items if (p.x - x) ** 2 + (p.y - y) ** 2 <= r2]

    def at_point(self, x: float, y: float) -> Pickup | None:
        """Solto debaixo do mouse (o mais perto, dentro do raio de acerto)."""
        near = self.touching(x, y, C.PICKUP_HIT)
        return min(near, key=lambda p: (p.x - x) ** 2 + (p.y - y) ** 2, default=None)

    def remove(self, p: Pickup) -> None:
        self.items = [q for q in self.items if q is not p]

    # ---- save --------------------------------------------------------------------------
    def to_data(self) -> dict:
        return {"items": [[p.resource, p.amount, p.x, p.y] for p in self.items], "timer": self.timer}

    @classmethod
    def from_data(cls, data: dict) -> "Pickups":
        items = []
        for d in data.get("items", []):
            if d[0] in C.RESOURCES and int(d[1]) > 0:
                items.append(Pickup(d[0], min(int(d[1]), C.PICKUP_AMOUNT[1]), float(d[2]), float(d[3])))
        return cls(items, float(data.get("timer", 0.0)))
