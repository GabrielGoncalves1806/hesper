"""Reaparecimento das rochas pequenas de minério na superfície (bíblia §9, Marco 1).

As rochas pequenas (SMALL_IRON, SMALL_SILICON, SMALL_ICE) nascem com o deserto (surface_gen.py) e quebram com a
broca. Quebrada, vira areia. Este módulo faz rocha nova aparecer devagar, no lugar dos recursos soltos que
existiam antes (o dono preferiu as rochas):

- 1 rocha a cada `ROCK_RESPAWN` s, até o teto `ROCK_MAX` de rochas no mapa;
- só onde o jogador não está vendo (fora da meia-tela do zoom mais afastado) e a `ROCK_BASE_DIST`+ tiles da base;
- só em areia livre: fora de veio, de lago futuro, de máquina, de destroço, da cratera/rampa e com os 8 vizinhos
  sem nada sólido (assim uma rocha nova nunca fecha uma passagem nem encosta num morro ou numa máquina);
- o minério sai pelos mesmos pesos da geração (`SMALL_ROCK_WEIGHTS`).

A rocha nova é só um tile no mapa: o save já guarda os tiles da superfície diferentes do mapa da seed
(`save.tiles_to_list`), então ela volta no load sem nada especial. Aqui só fica o timer.
Python puro (sem pygame), testado em tests/test_rock_respawn.py.
"""

import random

from game import config as C
from game.wrecks import keep_free

KIND_OF = {"iron": C.SMALL_IRON, "silicon": C.SMALL_SILICON, "ice": C.SMALL_ICE}


def hidden_from(player_xy, tx: int, ty: int) -> bool:
    """O tile (tx, ty) está fora da tela do jogador (no zoom mais afastado, com folga)?"""
    px, py = player_xy
    hx, hy = C.ROCK_HIDDEN
    return abs(tx + 0.5 - px / C.TILE) > hx or abs(ty + 0.5 - py / C.TILE) > hy


def count(world) -> int:
    """Quantas rochas pequenas tem no mapa agora."""
    kinds = tuple(C.SMALL_ROCKS)
    return sum(row.count(k) for row in world.tiles for k in kinds)


def blocked_tiles(world, machines=()) -> set[tuple[int, int]]:
    """Tiles proibidos fora a regra da areia: em volta de destroços, veios, cratera e máquinas, e (v0.4 Marco 2)
    o halo das formações e os bolsões dos gelos-portão (`world.keep_clear`). Na pegada da formação (C.FORMATION)
    nunca nasce: não é areia."""
    out = keep_free(world.wrecks) | set(getattr(world, "keep_clear", ()))
    for v in world.veins:                          # o veio e a linha de baixo dele (onde o player para)
        out |= {(v.tx + dx, v.ty + dy) for dx in (0, 1) for dy in (0, 1, 2)}
    if world.crater is not None:                   # rampa + 1 de folga + a chegada (2 linhas abaixo)
        cx, cy = world.crater
        out |= {(cx + dx, cy + dy) for dx in range(-1, 4) for dy in range(-1, 5)}
    for m in machines:                             # a máquina e 1 tile de folga em volta
        for x, y in m.tiles:
            out |= {(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return out


def can_spawn(world, tx: int, ty: int, blocked=()) -> bool:
    """Areia livre, longe da base, fora de veio/lago futuro/`blocked` e sem nada sólido nos 8 vizinhos."""
    if world.get(tx, ty) != C.SAND or (tx, ty) in blocked:
        return False
    if world.dist_from_center(tx, ty) < C.ROCK_BASE_DIST or world.vein_at(tx, ty) is not None:
        return False
    if any(world.is_solid(tx + dx, ty + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
        return False
    return not world.future_water(tx, ty)          # lago futuro: a bacia (com geo) ou a água do Verde


def pick_kind(r: float) -> int:
    """Tile de rocha pelo sorteio `r` em [0, 1), com os pesos da geração."""
    total = sum(C.SMALL_ROCK_WEIGHTS.values())
    acc = 0.0
    for resource, weight in C.SMALL_ROCK_WEIGHTS.items():
        acc += weight / total
        if r < acc:
            return KIND_OF[resource]
    return KIND_OF[resource]


class RockRespawn:
    def __init__(self, timer: float = 0.0):
        self.timer = timer            # segundos acumulados pra próxima rocha

    def update(self, world, rng: random.Random, dt: float, player_xy, machines=()) -> list[tuple[int, int]]:
        """Soma o tempo e põe 1 rocha a cada ROCK_RESPAWN s (até o teto). Devolve os tiles que ganharam rocha."""
        self.timer += dt
        if self.timer < C.ROCK_RESPAWN:
            return []
        n = count(world)
        blocked = blocked_tiles(world, machines)
        born = []
        while self.timer >= C.ROCK_RESPAWN:
            if n >= C.ROCK_MAX:
                self.timer = 0.0          # no teto: o relógio só volta a contar depois que alguém quebrar uma
                break
            self.timer -= C.ROCK_RESPAWN
            for _ in range(200):
                tx, ty = rng.randrange(world.width), rng.randrange(world.height)
                if can_spawn(world, tx, ty, blocked) and hidden_from(player_xy, tx, ty):
                    world.set(tx, ty, pick_kind(rng.random()))
                    born.append((tx, ty))
                    n += 1
                    break
        return born

    # ---- save --------------------------------------------------------------------------
    def to_data(self) -> dict:
        return {"timer": self.timer}

    @classmethod
    def from_data(cls, data: dict) -> "RockRespawn":
        return cls(min(max(float(data.get("timer", 0.0)), 0.0), C.ROCK_RESPAWN))
