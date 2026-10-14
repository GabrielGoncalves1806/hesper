"""Magmatita (v0.4 · bíblia §12 "Magmatita"): a pedra quente que as fumarolas do basalto expelem.

Só existe como rocha pequena (C.SMALL_MAGMATITE), num anel em volta de cada fumarola (`geo.vents`):

- no mapa da seed, cada fumarola (todas nascem dormentes) já tem MAGMATITE_DORMANT rochas em volta, o bastante pro
  1º Aquecedor (que custa magmatita). `place_initial` roda no fim do gerador da superfície, com rng próprio por
  fumarola, então nada do que já nascia antes muda;
- depois, `respawn` põe rocha nova em volta de cada fumarola até um teto: devagar e poucas na dormente
  (MAGMATITE_DORMANT_MAX a cada MAGMATITE_DORMANT_RESPAWN s), mais e mais rápido na acordada
  (MAGMATITE_AWAKE_MAX a cada MAGMATITE_AWAKE_RESPAWN s). Pode nascer na tela (é a fumarola expelindo), mas
  nunca embaixo do player.

O anel é de MAGMATITE_RING tiles (Chebyshev) da caixa da pegada: fora da pegada e do halo (keep_clear). A rocha
segue a regra do reaparecimento (`rock_respawn.can_spawn`): areia livre, fora de bacia, de veio, de destroço e de
máquina, e com os 8 vizinhos livres, então nunca fecha um caminho. Python puro, testado em tests/test_magmatite.py.
"""

import random

from game import config as C
from game.rock_respawn import blocked_tiles, can_spawn


def ring_tiles(vent) -> list[tuple[int, int]]:
    """Os tiles a MAGMATITE_RING tiles (Chebyshev, das duas pontas inclusive) da caixa da pegada da fumarola."""
    lo, hi = C.MAGMATITE_RING
    w, h = vent.size
    x0, y0, x1, y1 = vent.tx, vent.ty, vent.tx + w - 1, vent.ty + h - 1
    out = []
    for y in range(y0 - hi, y1 + hi + 1):
        for x in range(x0 - hi, x1 + hi + 1):
            d = max(x0 - x, x - x1, y0 - y, y - y1, 0)
            if lo <= d <= hi:
                out.append((x, y))
    return out


def rocks_around(world, vent) -> list[tuple[int, int]]:
    """As rochas de magmatita no anel da fumarola agora."""
    return [t for t in ring_tiles(vent) if world.get(*t) == C.SMALL_MAGMATITE]


def _vent_rng(seed: int, index: int) -> random.Random:
    return random.Random((seed * 1_000_003 + C.MAGMATITE_SEED) * 101 + index)


def place_initial(world) -> list[tuple[int, int]]:
    """Mapa da seed: MAGMATITE_DORMANT rochas em volta de cada fumarola (rng próprio por fumarola). Devolve os tiles."""
    geo = world.geo
    if geo is None:
        return []
    blocked = blocked_tiles(world)
    placed = []
    for i, vent in enumerate(geo.vents):
        rng = _vent_rng(world.seed, i)
        want = rng.randint(*C.MAGMATITE_DORMANT)
        cands = ring_tiles(vent)
        rng.shuffle(cands)
        got = 0
        for t in cands:
            if got >= want:
                break
            if can_spawn(world, *t, blocked):
                world.set(*t, C.SMALL_MAGMATITE)
                placed.append(t)
                got += 1
    return placed


def limits(awake: bool) -> tuple[int, float]:
    """(teto de rochas em volta, segundos por rocha nova) da fumarola dormente ou acordada."""
    if awake:
        return C.MAGMATITE_AWAKE_MAX, C.MAGMATITE_AWAKE_RESPAWN
    return C.MAGMATITE_DORMANT_MAX, C.MAGMATITE_DORMANT_RESPAWN


def respawn(world, awake: list, timers: list, rng: random.Random, dt: float, player_xy,
            machines=()) -> list[tuple[int, int]]:
    """Soma `dt` no relógio de cada fumarola e põe 1 rocha quando ele passa do tempo dela (até o teto em volta).
    `timers` (um por fumarola, do RockRespawn) é atualizado no lugar. Devolve os tiles que ganharam rocha."""
    geo = world.geo
    if geo is None or not geo.vents:
        return []
    while len(timers) < len(geo.vents):
        timers.append(0.0)
    px, py = int(player_xy[0] // C.TILE), int(player_xy[1] // C.TILE)
    born, blocked = [], None
    for i, vent in enumerate(geo.vents):
        cap, every = limits(i < len(awake) and bool(awake[i]))
        timers[i] += dt
        if timers[i] < every:
            continue
        have = len(rocks_around(world, vent))
        if have >= cap:
            timers[i] = 0.0                  # cheia: o relógio só volta a contar quando alguém quebrar uma
            continue
        timers[i] -= every
        if blocked is None:
            blocked = blocked_tiles(world, machines)
        cands = [t for t in ring_tiles(vent)
                 if max(abs(t[0] - px), abs(t[1] - py)) > 1 and can_spawn(world, *t, blocked)]
        if cands:
            t = cands[rng.randrange(len(cands))]
            world.set(*t, C.SMALL_MAGMATITE)
            born.append(t)
    return born
