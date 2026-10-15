"""Simulador de jogador pra medir o ritmo do jogo (sem pygame, sem janela).

    uv run python tools/dev/balance_sim.py                    # atual × proposta (balance_proposal.json)
    uv run python tools/dev/balance_sim.py --current          # só os números do config.py
    uv run python tools/dev/balance_sim.py --overrides x.json # outro arquivo de overrides
    uv run python tools/dev/balance_sim.py --markdown         # tabelas em Markdown (pro reports/dev/balance.md)
    uv run python tools/dev/balance_sim.py --no-energy        # roda também sem energia (como era antes do Marco 2)

O que é real e o que é aproximado
---------------------------------
v0.3 Marco 1: o mundo é a SUPERFÍCIE (deserto do `surface_gen`, a camada ativa do GameState), ainda
sem caverna. Minério = minério dos morros + rochas pequenas (`C.TILE_RESOURCE`), que reaparecem pela regra real
(`game/rock_respawn.py`, rodando junto da produção). O volume de minério da superfície é baixo de propósito
(a mineração em volume vem com a caverna no Marco 2).

v0.3 Marco 2: a estratégia "caverna" minera só na CAVERNA (`Strategy.cave`). A base continua na superfície; o
mapa de mineração vira a caverna e a base é um índice virtual ligado à chegada da rampa por uma aresta de
`ramp_k` tiles (caminho real na superfície da zona de O₂ até a cratera + o fade da rampa). O O₂ cai no trecho todo.
As drills vão nos veios da caverna e ele busca à mão (drones só atendem a superfície: sem estação).

Real (vem do jogo): o mapa (`GameState(seed).world`, a superfície), o inventário, os drops (`GameState._break_tile`,
com o `rng` do estado), `can_mine` (alcance), `craft`/`can_place`/`build` (v0.5: o construtor), a produção das máquinas
(`GameState._update_machines`), os estágios (`stage_for_ti`), o desmaio (`_faint` + `_update_faint` frame a frame) e
todos os números do `game/config.py` (velocidade, tempos de mineração, O₂, receitas, taxas, limiares).

Aproximado (o simulador decide no lugar do jogador):
- Deslocamento: Dijkstra no grid de tiles, 8 vizinhos (diagonal só se os dois vizinhos retos estiverem livres,
  igual a caixa de colisão faria), custo = distância × TILE / PLAYER_SPEED. Entrar numa rocha custa o tempo de
  minerar ela. Isso é o caminho ótimo de um jogador que conhece o mapa; o jogador "casual" anda 30% mais devagar
  que o planejado (desvio, mira, colisão), o que é o fator de realismo.
  Não usamos o `Player.move` frame a frame porque seria ~50× mais lento e o resultado é o mesmo em linha reta.
- Rochas pequenas que reaparecem: regra real (`GameState._update_rocks`, com a posição do jogador simulado);
  cada rocha nova entra nos contadores de "minério ao alcance". O campo de distância até a base não é refeito
  quando uma rocha nasce (ela sempre tem os 8 vizinhos livres, então o desvio custa ~1 tile).
- Máquinas colocadas não bloqueiam o caminho no grid (são caixas de 24×18 px num tile de 32: dá pra passar do lado).
- Craftar e colocar custa um tempo fixo por máquina (`craft_overhead`), cobrindo menu + andar até o lugar.
- Drills (depois da Névoa): o jogador fabrica até `Strategy.drills` drills e põe cada uma num veio livre alcançável
  a pé (ferro primeiro). Ir e voltar custa a distância andando real (com O₂). A extração é a regra real do jogo
  (`_update_drill`). Na base, antes de sair pra minerar um recurso, ele vai coletar uma drill desse recurso se a
  viagem custar menos do que minerar aquelas unidades no ritmo dele. "Sem drills" = mesma simulação com a receita
  da drill trancada (`--no-drills` / `without_drills`).
- Drones (Marco 3, logística estilo Planet Crafter): cada drill colocada é configurada com **Envia = o minério
  dela** (a drill nova vem sem nada; o jogador configura no painel). Depois das drills, o jogador fabrica um baú
  na base (se ainda não tiver um) configurado com **Recebe = ferro, silício e gelo**, e 1 estação de drones perto
  dele (até 3 tiles; o alcance é o mapa todo, a estação perto da base só encurta a volta dos drones). A estação
  vem vazia: ele junta material pra estação E `Strategy.drones` drones (item, 2 por padrão) de uma vez, fabrica
  tudo e põe os drones nos slots pelo `GameState.station_dock` real. Os drones são a regra real
  (`game/drones.py`, rodando dentro do `_update_machines`): levam o lote (10) das drills pro baú. Toda vez que o
  jogador está na base, ele esvazia o baú da base pro inventário ("drone un."), em vez de ir até a drill.
  "Sem drones" = mesma simulação com a receita da estação trancada (`--no-drones` / `without_drones`).
- Energia (Marco 2): a produção das máquinas e das drills já sai no ritmo da energia, porque o simulador usa o
  `_update_machines` e o `ti_rate` reais. O jogador fabrica um painel solar (na base, como outra máquina qualquer)
  sempre que o fator cai abaixo de `PANEL_BELOW`. "Sem energia" = consumo zerado (`--no-energy` / `without_energy`).

v0.3 Marco 3: a estratégia "destrocos" é a "caverna" que, logo no começo, vai a pé até a nave de carga mais
perto (caminho real na superfície, ida e volta, com O₂), abre a caixa (regra real: `open_crate` + `crate_take`,
o diagrama do tanque vem no saque), volta, lê o diagrama, fabrica o tanque de O₂ e equipa (`equip_from`). Daí em diante o O₂ máximo
é o do tanque (`GameState.o2_max`, 220 s), o que deixa cada descida na caverna render mais.

Tempo morto: o jogador só fica parado quando não existe nada útil: (a) a próxima máquina não ficaria pronta antes
de o Ti bater o fim, (b) ele já tem os recursos e está esperando a receita liberar, ou (c) não há minério alcançável
com o O₂ de um tanque cheio.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import dataclasses
import heapq
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game import config as C  # noqa: E402
from game import drones  # noqa: E402
from game import layers  # noqa: E402
from game import surface_gen  # noqa: E402
from game import thaw  # noqa: E402
from game.layers import CAVE, SURFACE  # noqa: E402
from game.systems import GameState  # noqa: E402

PROPOSAL_PATH = Path(__file__).with_name("balance_proposal.json")
SQRT2 = math.sqrt(2)
INF = float("inf")
NEIGHBORS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2)]
TILE_NAMES = {"ROCK": C.ROCK, "IRON": C.IRON, "SILICON": C.SILICON, "ICE": C.ICE}
PANEL_BELOW = 0.9      # o jogador simulado fabrica um painel solar quando o fator da energia cai abaixo disso


# ---------------------------------------------------------------------------
# Overrides do config (só em memória, sempre restaurados)
# ---------------------------------------------------------------------------
def load_overrides(path: Path = PROPOSAL_PATH) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("overrides", data)


@contextlib.contextmanager
def patched_config(overrides: dict | None):
    """Aplica overrides no módulo `game.config` e desfaz tudo na saída.

    Formato (todas as chaves são opcionais):
      {"PLAYER_SPEED": 140, "O2_DRAIN": 1.0, ...}                  escalares do config
      {"MINE_TIME": {"IRON": 0.8}}                                  por nome de tile
      {"MACHINES": {"o2": {"rate": 5, "cost": {"iron": 8}}}}        campos do MachineType
      {"STAGES": {"arid": 6500, "mist": 8000, "green": 60000}}      Ti de cada estágio
    `cost` substitui a receita inteira. O código do jogo lê `C.<nome>` na hora do uso, então trocar o atributo
    do módulo basta.
    """
    overrides = overrides or {}
    saved = {}
    surface_gen._cache.clear()      # v0.4 M4: o mapa é cacheado por seed; override de geração (SMALL_ROCK_CHANCE...) tem que refazer
    try:
        for key, value in overrides.items():
            if not hasattr(C, key):
                raise KeyError(f"config não tem {key!r}")
            saved[key] = getattr(C, key)
            if key == "MINE_TIME":
                new = dict(C.MINE_TIME)
                new.update({TILE_NAMES[k]: v for k, v in value.items()})
                C.MINE_TIME = new
            elif key == "MACHINES":
                new = dict(C.MACHINES)
                for kind, fields in value.items():
                    new[kind] = dataclasses.replace(new[kind], **fields)
                C.MACHINES = new
            elif key == "STAGES":
                C.STAGES = [dataclasses.replace(s, ti=value.get(s.key, s.ti)) for s in C.STAGES]
            else:
                setattr(C, key, copy.deepcopy(value))
        yield
    finally:
        for key, value in saved.items():
            setattr(C, key, value)
        surface_gen._cache.clear()


# ---------------------------------------------------------------------------
# Estratégias
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Strategy:
    name: str
    pick: str = "greedy"          # "greedy": melhor Ti/s por segundo de coleta · "balanced": alterna os tipos
    walk_factor: float = 1.0      # quanto o andar real demora a mais que o planejado
    o2_margin: float = 6.0        # O₂ de sobra que o jogador quer ao chegar na base
    craft_overhead: float = 3.0   # segundos por máquina: menu + andar até o lugar + colocar
    mine_overhead: float = 0.0    # segundos por tile além da dureza: mirar o próximo, reposicionar o mouse
    drills: int = 3               # quantas drills ele monta depois da Névoa (uma por veio)
    stations: int = 1             # quantas estações de drones ele monta depois das drills
    drones: int = 2               # quantos drones (item) ele fabrica e põe na estação
    cave: bool = False            # Marco 2: minera na CAVERNA (desce pela rampa), drills nos veios de lá
    wrecks: bool = False          # Marco 3: começa indo à nave de carga mais perto (saque + tanque de O₂)


STRATEGIES = {
    # conhece o mapa, caminho ótimo, sempre a máquina com melhor Ti/s por segundo de coleta
    "guloso": Strategy("guloso"),
    # joga direito mas monta de tudo: alterna os tipos da maior tier liberada
    "variado": Strategy("variado", pick="balanced", craft_overhead=4.0, mine_overhead=0.1),
    # humano normal: anda 30% mais que o planejado (pode até desmaiar), volta com folga, demora pra mirar
    "casual": Strategy("casual", pick="balanced", walk_factor=1.3, o2_margin=12.0, craft_overhead=6.0,
                       mine_overhead=0.3),
    # v0.3 Marco 2: o mesmo humano casual, mas que desce pela cratera e minera na caverna (minério em volume,
    # sem as rochas da superfície). As drills vão nos veios da caverna e ele busca à mão (os drones só atendem a superfície).
    "caverna": Strategy("caverna", pick="balanced", walk_factor=1.3, o2_margin=12.0, craft_overhead=6.0,
                        mine_overhead=0.3, stations=0, cave=True),
    # v0.3 Marco 3: o casual da caverna que antes vai à nave de carga mais perto, pega o saque e o diagrama do
    # tanque, fabrica e equipa (O₂ de 100 -> 220 s pra minerar lá embaixo)
    "destrocos": Strategy("destrocos", pick="balanced", walk_factor=1.3, o2_margin=12.0, craft_overhead=6.0,
                          mine_overhead=0.3, stations=0, cave=True, wrecks=True),
}


def surface_walk_to_zone(world, target) -> float:
    """Tiles andando (8 vizinhos, sem cortar quina) do tile `target` até a zona de O₂ da base, na superfície."""
    W, H = world.width, world.height
    def zone(x, y):
        return math.hypot((x + 0.5) * C.TILE - C.BASE_CENTER[0], y * C.TILE + 24 - C.BASE_CENTER[1]) <= C.BASE_RADIUS
    def free(x, y):
        return world.is_floor(x, y) and (x, y) not in C.POD_TILES
    dist = {target: 0.0}
    heap = [(0.0, target)]
    while heap:
        d, (x, y) = heapq.heappop(heap)
        if d > dist[(x, y)]:
            continue
        if zone(x, y):
            return d
        for dx, dy, step in NEIGHBORS:
            nx, ny = x + dx, y + dy
            if not (0 < nx < W - 1 and 0 < ny < H - 1) or not free(nx, ny):
                continue
            if dx and dy and not (free(x + dx, y) and free(x, y + dy)):
                continue
            if d + step < dist.get((nx, ny), INF):
                dist[(nx, ny)] = d + step
                heapq.heappush(heap, (d + step, (nx, ny)))
    return INF


def surface_zone_field(world) -> dict:
    """Tiles andando (8 vizinhos, sem cortar quina) da zona de O₂ da base até cada tile de chão da superfície."""
    W, H = world.width, world.height
    def free(x, y):
        return world.is_floor(x, y) and (x, y) not in C.POD_TILES
    dist, heap = {}, []
    for y in range(H):
        for x in range(W):
            if free(x, y) and math.hypot((x + 0.5) * C.TILE - C.BASE_CENTER[0],
                                         y * C.TILE + 24 - C.BASE_CENTER[1]) <= C.BASE_RADIUS:
                dist[(x, y)] = 0.0
                heap.append((0.0, (x, y)))
    heapq.heapify(heap)
    while heap:
        d, (x, y) = heapq.heappop(heap)
        if d > dist[(x, y)]:
            continue
        for dx, dy, step in NEIGHBORS:
            nx, ny = x + dx, y + dy
            if not (0 < nx < W - 1 and 0 < ny < H - 1) or not free(nx, ny):
                continue
            if dx and dy and not (free(x + dx, y) and free(x, y + dy)):
                continue
            if d + step < dist.get((nx, ny), INF):
                dist[(nx, ny)] = d + step
                heapq.heappush(heap, (d + step, (nx, ny)))
    return dist


class Fainted(Exception):
    pass


@dataclass
class Result:
    strategy: str
    seed: int
    milestones: dict = field(default_factory=dict)   # nome -> segundos
    total: float = 0.0
    finished: bool = False
    machines: dict = field(default_factory=dict)
    idle_total: float = 0.0
    idle_longest: float = 0.0
    idle_longest_at: float = 0.0
    idle_reason: str = ""                            # motivo da espera atual
    idle_longest_reason: str = ""
    idle_by: dict = field(default_factory=dict)      # motivo -> segundos
    faints: int = 0
    trips: int = 0
    drill_units: int = 0                             # minério que veio de drills (coletado)
    drone_units: int = 0                             # minério que os drones trouxeram (pego no baú/estação)
    tiles_mined: int = 0
    units: int = 0                                   # recursos coletados
    time_by: dict = field(default_factory=dict)      # andar / minerar / base / espera
    deficit_time: float = 0.0                        # segundos com falta de energia (máquinas mais lentas)
    ramp_tiles: float = 0.0                          # estratégia caverna: "tiles" da base até a chegada na caverna
    tank_at: float | None = None                     # Marco 3: quando equipou o tanque de O₂
    loot_units: int = 0                              # Marco 3: recursos tirados da caixa do destroço
    crater_at: float | None = None                   # v0.4 M3.1: quando o calor abriu a cratera (só informa)
    magma_trips: int = 0                             # v0.4: idas da caverna até as fumarolas buscar magmatita
    gate_at: dict = field(default_factory=dict)      # v0.4 M4: portão i -> quando a fresta abriu (só lê os eventos)
    giant_at: float | None = None                    # v0.5 M3.6.3: quando a fresta do portão grande abriu
    final_indices: dict = field(default_factory=dict)   # v0.4 M4: o2/heat/water no fim (só leitura)
    lake_at: dict = field(default_factory=dict)      # v0.4 M4: lago k (0..2 = L1..L3) -> quando a água bateu a marca
    magma_at: float | None = None                    # v0.4 M4: quando minerou a 1ª magmatita (o que o inventário já viu)
    heater_at: float | None = None                   # v0.4 M4: quando o 1º aquecedor entrou no mapa


# ---------------------------------------------------------------------------
# O jogador simulado
# ---------------------------------------------------------------------------
class Sim:
    def __init__(self, strategy: Strategy, seed: int = 1, max_time: float = 6 * 3600):
        self.s = strategy
        self.gs = GameState(rng=random.Random(seed))
        # Mapa onde ele minera: a superfície (padrão) ou a caverna (Strategy.cave). A base (fabricar, colocar
        # máquinas, encher O₂) é sempre na superfície (`base_world`). Na caverna, a base vira um índice virtual
        # BASE (= W·H) ligado à chegada da rampa por uma "aresta" de `ramp_k` tiles: o caminho na superfície da
        # zona de O₂ até a cratera + o tempo do fade da rampa. O O₂ cai nesse trecho todo (não há zona lá).
        self.cave = strategy.cave
        self.base_world = self.gs.surface.world
        self.mine_layer = CAVE if self.cave else SURFACE
        if self.cave:
            self.gs.layers[CAVE] = layers.make_cave(self.gs.seed)
        self.world = self.gs.layers[self.mine_layer].world
        self.W, self.H = self.world.width, self.world.height
        self.N = self.W * self.H
        self.BASE = self.N
        self.t = 0.0
        self.max_time = max_time
        self.tw = C.TILE / C.PLAYER_SPEED                 # segundos por tile andado
        self.final_ti = C.STAGES[-1].ti
        self.marks = [("Ti 500", 500.0)] + [(s.name.capitalize(), float(s.ti)) for s in C.STAGES[1:]]
        self.res = Result(strategy.name, seed)
        self.sec_per_unit = 1.5                           # estimativa do jogador (EMA), atualizada a cada viagem
        self.plan: str | None = None
        self.plan_unlocked: tuple = ()
        self.rr = 0                                       # índice do round-robin (estratégia "variado")
        self.idle_run = 0.0
        if self.cave:
            self.home = self.BASE
            self.blocked = set()
            self.arrival = self._i(*layers.ramp_target(self.world)) + self.W     # tile logo abaixo da rampa
            crater = layers.ramp_target(self.base_world)
            self.ramp_k = (surface_walk_to_zone(self.base_world, (crater[0], crater[1] + 1))
                           + C.RAMP_DURATION / self.tw)
            self.res.ramp_tiles = self.ramp_k
        else:
            self.home = self._i(*self._xy_spawn())
            self.blocked = {self._i(*t) for t in C.POD_TILES}
        self.cur = self.home
        self.zone = [self._in_zone(i) for i in range(self.N)] + [self.cave]  # [BASE] = a base (virtual, só caverna)
        self._init_near_ore()
        self._init_field()
        self.sites: list[int] | None = None

    # ---- utilidades de grid ----
    def _i(self, x, y):
        return y * self.W + x

    def _xy(self, i):
        return i % self.W, i // self.W

    def _pos(self, i):
        x, y = self._xy(i)
        return (x + 0.5) * C.TILE, y * C.TILE + 24          # pés no meio do tile (player.tile == (x, y))

    def _in_zone(self, i):
        if self.cave:
            return False                                      # não tem zona de O₂ na caverna
        px, py = self._pos(i)
        return math.hypot(px - C.BASE_CENTER[0], py - C.BASE_CENTER[1]) <= C.BASE_RADIUS

    def _tile(self, i):
        x, y = self._xy(i)
        return self.world.tiles[y][x]

    def _walkable(self, i):
        if i == self.BASE:
            return self.cave
        return self._tile(i) in C.FLOOR_TILES and i not in self.blocked

    def _passable(self, i):
        """Dá pra chegar nele andando ou minerando (rocha dura não: o simulador não tem a broca nv.2)."""
        if i in self.blocked:
            return False
        k = self._tile(i)
        return k in C.FLOOR_TILES or (k in C.MINE_TIME and not (i != self.BASE and self.world.is_hard(*self._xy(i))))

    def _set_player(self, i):
        if self.cave and i == self.BASE:                     # na base, lá em cima
            self.gs.enter_layer(SURFACE, C.SPAWN_POS)
            self.cur = i
            return
        if self.gs.layer != self.mine_layer:
            self.gs.enter_layer(self.mine_layer)
        self.gs.player.x, self.gs.player.y = self._pos(i)
        self.cur = i

    @staticmethod
    def _tile_pos(x, y):
        """Pés no meio do tile (x, y) de qualquer camada."""
        return (x + 0.5) * C.TILE, y * C.TILE + 24

    def _base_free(self, t):
        return self.base_world.is_floor(*t) and t not in C.POD_TILES

    def _drills(self):
        """Drills do mapa onde ele minera (na estratégia caverna, as da caverna)."""
        return [m for m in self.gs.layers[self.mine_layer].machines if m.is_drill]

    def _neighbors(self, i, walk_only):
        if self.cave and i == self.BASE:                       # base -> rampa -> chegada na caverna
            yield self.arrival, self.ramp_k
            return
        x, y = self._xy(i)
        for dx, dy, step in NEIGHBORS:
            nx, ny = x + dx, y + dy
            if not (0 < nx < self.W - 1 and 0 < ny < self.H - 1):
                continue
            j = ny * self.W + nx
            if dx and dy:   # diagonal: só entre chãos, sem cortar quina
                if not (self._walkable(j) and self._walkable(self._i(x + dx, y)) and self._walkable(self._i(x, y + dy))):
                    continue
            elif not (self._walkable(j) if walk_only else self._passable(j)):
                continue
            yield j, step

    # ---- minério ao alcance (contadores 5×5) ----
    def _init_near_ore(self):
        R = C.MINE_REACH
        self.near = {r: [0] * (self.N + 1) for r in C.RESOURCES}
        for y in range(self.H):
            for x in range(self.W):
                res = C.TILE_RESOURCE.get(self.world.tiles[y][x])
                if res and not self.world.is_hard(x, y):          # v0.6 Fundo: minério duro não conta (sem nv.2)
                    self._bump_near(res, x, y, +1, R)

    def _bump_near(self, res, x, y, d, R=None):
        R = C.MINE_REACH if R is None else R
        arr = self.near[res]
        for yy in range(max(0, y - R), min(self.H, y + R + 1)):
            base = yy * self.W
            for xx in range(max(0, x - R), min(self.W, x + R + 1)):
                arr[base + xx] += d

    def _ores_in_reach(self, i):
        if i == self.BASE:
            return []
        x, y = self._xy(i)
        R = C.MINE_REACH
        out = []
        for yy in range(y - R, y + R + 1):
            for xx in range(x - R, x + R + 1):
                k = self.world.get(xx, yy)
                if k in C.TILE_RESOURCE and not self.world.is_hard(xx, yy):
                    out.append((self._i(xx, yy), k))
        return out

    # ---- distância andando até a zona de O₂ (em tiles), atualizada a cada tile quebrado ----
    def _init_field(self):
        self.field = [INF] * (self.N + 1)
        heap = []
        for i in range(self.N + 1):
            if self.zone[i] and self._walkable(i):
                self.field[i] = 0.0
                heap.append((0.0, i))
        heapq.heapify(heap)
        self._relax(heap)

    def _relax(self, heap):
        f = self.field
        while heap:
            d, u = heapq.heappop(heap)
            if d > f[u]:
                continue
            for v, step in self._neighbors(u, walk_only=True):
                nd = d + step
                if nd < f[v]:
                    f[v] = nd
                    heapq.heappush(heap, (nd, v))

    def _opened(self, i):
        """Tile i virou chão: puxa a distância dos vizinhos e propaga."""
        best = 0.0 if self.zone[i] else min((self.field[j] + s for j, s in self._neighbors(i, True)), default=INF)
        if best < self.field[i]:
            self.field[i] = best
        heap = [(self.field[i], i)]
        for j, s in self._neighbors(i, True):     # vizinhos podem ganhar atalho pelo tile novo
            heap.append((self.field[j], j))
        heapq.heapify(heap)
        self._relax(heap)

    # ---- tempo ----
    def _advance(self, dt, outside=False, idle=False, what="base"):
        """Passa dt segundos: máquinas produzem (regra real), O₂ cai fora da zona, marca os limiares."""
        what = "espera" if idle else what
        t0 = self.t
        try:
            self._advance_inner(dt, outside, idle)
        finally:
            self.res.time_by[what] = self.res.time_by.get(what, 0.0) + self.t - t0

    def _advance_inner(self, dt, outside, idle):
        while dt > 1e-9:
            step = dt
            faint = False
            if outside:
                left = self.gs.o2 / C.O2_DRAIN
                if left <= step:
                    step, faint = left, True
            t0 = self.t
            self._produce(step)
            step = self.t - t0             # pode ter sido cortado no fim do jogo
            if outside:
                self.gs.o2 = max(0.0, self.gs.o2 - C.O2_DRAIN * step)
            elif self.zone[self.cur]:
                self.gs.o2 = min(self.gs.o2_max, self.gs.o2 + C.O2_REFILL * step)
            if idle:
                self.idle_run += step
                self.res.idle_total += step
                reason = self.res.idle_reason
                self.res.idle_by[reason] = self.res.idle_by.get(reason, 0.0) + step
                if self.idle_run > self.res.idle_longest:
                    self.res.idle_longest = self.idle_run
                    self.res.idle_longest_at = self.t - self.idle_run
                    self.res.idle_longest_reason = reason
            if self.res.finished:
                return
            dt -= step
            if faint:
                self._faint()

    def _produce(self, dt):
        ti0, rate = self.gs.ti, self.gs.ti_rate
        for name, thr in self.marks:
            if name not in self.res.milestones and ti0 < thr <= ti0 + rate * dt:
                self.res.milestones[name] = self.t + (thr - ti0) / rate
        if rate > 0 and ti0 + rate * dt >= self.final_ti:
            dt = (self.final_ti - ti0) / rate
            self.res.finished = True
        if self.gs.power.deficit:
            self.res.deficit_time += dt
        self.gs._update_machines(dt)           # regra real: soma rate*dt×fator em cada índice e checa estágio
        if self.res.crater_at is None and not self.gs.crater_frozen:   # v0.4 M3.1: o calor (thaw) abriu a cratera
            heat_rate = sum(m.type.rate for m in self.gs.all_machines if m.type.index == "heat") * self.gs.power.factor
            over = self.gs.indices["heat"] - C.THAW_CRATER_HEAT[-1]
            self.res.crater_at = self.t + dt - (over / heat_rate if heat_rate > 0 else 0.0)
        if self.res.magma_at is None and self.gs.mined_total.get("magmatite", 0) > 0:
            self.res.magma_at = self.t
        if self.res.heater_at is None and any(m.type.index == "heat" for m in self.gs.all_machines):
            self.res.heater_at = self.t
        for ev in self.gs.events:              # v0.4 M4: só lê o estado (portão aberto, lago subindo), não muda o jogo
            if ev[0] == "gate_thaw" and ev[2] == thaw.GATE_OPEN:
                self.res.gate_at.setdefault(ev[1], self.t + dt)
            elif ev[0] == "giant_gate_thaw" and ev[1] == thaw.GATE_OPEN and self.res.giant_at is None:
                self.res.giant_at = self.t + dt
            elif ev[0] == "lake_rise":
                self.res.lake_at.setdefault(ev[1], self.t + dt)
        self.gs.events.clear()                 # os eventos (degelo etc.) são do App: aqui só iam acumular
        for x, y in self.gs._update_rocks(dt):  # regra real: rocha nova fora da vista e longe da base
            if not self.cave:                  # a estratégia "caverna" não minera na superfície
                self._bump_near(C.SMALL_ROCKS[self.world.tiles[y][x]], x, y, +1)
        self.gs.play_time += dt
        self.t += dt

    def _faint(self):
        """Regra real: GameState._faint + update frame a frame até devolver o controle (acorda na cápsula)."""
        self.res.faints += 1
        self.gs._faint()
        dt = 1 / 60
        while self.gs.fainted and not self.res.finished:
            # o update real também roda as máquinas; aqui a produção passa pelo _produce pra marcar os limiares
            self.gs._update_faint(dt)
            self._produce(dt)
        self.cur = self.home                    # acorda na cápsula (superfície)
        raise Fainted

    def _not_idle(self):
        self.idle_run = 0.0

    # ---- decisões ----
    @staticmethod
    def ti_kinds():
        """Máquinas que somam Ti (a drill não entra na conta de 'qual máquina rende mais Ti')."""
        return [k for k, m in C.MACHINES.items() if m.index is not None]

    def _gather_time(self, kind):
        cost = C.MACHINES[kind].cost
        units = sum(max(0, n - self.gs.inventory.count(r)) for r, n in cost.items())
        return units * self.sec_per_unit + self.s.craft_overhead

    def _unlock_eta(self, kind):
        need = C.MACHINES[kind].unlock_ti - self.gs.ti
        if need <= 0:
            return 0.0
        return INF if self.gs.ti_rate <= 0 else need / self.gs.ti_rate

    def _full_time(self, kind):
        """Custo 'de tabela' da máquina em segundos de coleta (ignora o que já tem no bolso)."""
        return sum(C.MACHINES[kind].cost.values()) * self.sec_per_unit + self.s.craft_overhead

    @staticmethod
    def _tier(kind):
        """Tier = estágio em que a receita libera (Aquecedor libera no Ti 500 mas ainda é nv.1)."""
        return sum(1 for s in C.STAGES if s.ti <= C.MACHINES[kind].unlock_ti)

    def choose(self):
        """Próxima máquina a juntar. None = nada útil (o fim chega antes de ela ficar pronta).

        O jogador se compromete com o alvo até fabricar (senão o guloso fica trocando de ideia toda hora),
        e só repensa quando uma receita nova libera.
        """
        unlocked_now = tuple(k for k in self.ti_kinds() if self._unlock_eta(k) == 0)
        if self.plan is None or unlocked_now != self.plan_unlocked:
            self.plan_unlocked = unlocked_now
            if self.s.pick == "balanced":
                # jogador "normal": usa a maior tier liberada e alterna entre os tipos dela
                top = max(self._tier(k) for k in unlocked_now)
                pool = [k for k in unlocked_now if self._tier(k) == top]
                self.plan = pool[self.rr % len(pool)]
            else:
                # guloso: melhor Ti/s por segundo de coleta, aceitando receita que libera antes de juntar tudo
                cands = [k for k in self.ti_kinds() if self._unlock_eta(k) <= self._gather_time(k)]
                self.plan = max(cands, key=lambda k: C.MACHINES[k].rate / self._full_time(k))
        rate = self.gs.ti_rate
        if rate <= 0:
            return self.plan
        left = (self.final_ti - self.gs.ti) / rate
        ready = {k: max(self._gather_time(k), self._unlock_eta(k)) for k in self.ti_kinds()}
        if ready[self.plan] < left:
            return self.plan
        # Reta final: o plano não fica pronto a tempo. Vale uma máquina mais barata que ainda renda algo?
        useful = [k for k in self.ti_kinds() if ready[k] < left]
        if not useful:
            return None
        self.plan = max(useful, key=lambda k: C.MACHINES[k].rate * (left - ready[k]))
        return self.plan

    # ---- energia ----
    def want_panel(self) -> bool:
        """Falta energia (fator < PANEL_BELOW) e o painel está liberado: a próxima máquina é um painel."""
        if "solar" not in C.MACHINES or self.gs.recipe_status("solar") == "locked":
            return False
        return self.gs.power.factor < PANEL_BELOW

    # ---- drills ----
    def _vein_walk(self, vein):
        """Tiles andando da zona de O₂ até o lado do veio (INF se ainda não dá pra chegar a pé)."""
        return min(self.field[self._i(x, y)] for x, y in vein.tiles)

    def _trip_time(self, vein):
        return 2 * self._vein_walk(vein) * self.tw * self.s.walk_factor + self.s.craft_overhead

    def _trip_fits_o2(self, vein):
        return self._trip_time(vein) + self.s.o2_margin <= self.gs.o2_max / C.O2_DRAIN

    def free_vein(self):
        """Veio livre alcançável a pé com um tanque de O₂, preferindo tipo ainda sem drill (ferro primeiro)."""
        taken = {(d.tx, d.ty) for d in self._drills()}
        have = {d.resource for d in self._drills()}
        options = [v for v in self.world.veins if (v.tx, v.ty) not in taken
                   and self._vein_walk(v) < INF and self._trip_fits_o2(v)]
        order = {r: i for i, r in enumerate(C.RESOURCES)}
        return min(options, key=lambda v: (v.resource in have, order[v.resource], self._vein_walk(v)), default=None)

    def want_drill(self) -> bool:
        if "drill" not in C.MACHINES or self.gs.recipe_status("drill") == "locked":
            return False
        built = len(self._drills()) + self.gs.inventory.count("drill")
        return built < self.s.drills and self.free_vein() is not None

    def _visit_vein(self, vein, action):
        """Sai da base, vai até o veio (O₂ caindo), faz `action` lá e volta pra base (go_base)."""
        self._set_player(self.home)
        walk = self._vein_walk(vein) * self.tw * self.s.walk_factor
        self._advance(walk, outside=True, what="andar")
        below = (vein.tx, vein.ty + 2)                 # parado logo abaixo do veio (sempre chão)
        self._set_player(self._i(*below))
        action()
        self._advance(self.s.craft_overhead / 2, outside=True, what="base")
        self.go_base()

    def craft_and_place_drill(self):
        self._set_player(self.home)
        vein = self.free_vein()
        if vein is None or not self._ready("drill"):
            return False
        self._visit_vein(vein, lambda: self._place_drill(vein))
        return True

    def _place_drill(self, vein):
        ok = self._build("drill", (vein.tx, vein.ty))
        assert ok, f"não conseguiu colocar a drill no veio {vein}"
        drill = self.gs.machine_at((vein.tx, vein.ty))
        drill.chip = True                                # v0.6 M2: o simulador não é jogador, ganha o chip de graça
        drones.toggle_send(drill, drill.resource)        # o jogador marca Envia = o minério dela no painel

    def collect_trip(self, missing) -> bool:
        """Na base: vale ir buscar o que uma drill guardou em vez de minerar isso?"""
        best = None
        for d in self._drills():
            if d.resource not in missing or d.stored <= 0:
                continue
            vein = self.world.vein_at(d.tx, d.ty)
            if not self._trip_fits_o2(vein):
                continue
            gain = d.stored * self.sec_per_unit - self._trip_time(vein)   # segundos economizados
            if gain > 0 and (best is None or gain > best[0]):
                best = (gain, d, vein)
        if best is None:
            return False
        _, drill, vein = best
        self._visit_vein(vein, lambda: self._collect(drill))
        return True

    def _collect(self, drill):
        self.res.drill_units += self.gs.collect(drill)

    # ---- drones ----
    def want_station(self) -> bool:
        """Depois das drills: 1 estação (perto de um baú na base), se a receita já liberou."""
        if "drone_station" not in C.MACHINES or self.gs.recipe_status("drone_station") == "locked":
            return False
        if len(self._drills()) < self.s.drills and self.free_vein() is not None:
            return False                                  # primeiro as drills
        built = len(self.gs.stations) + self.gs.inventory.count("drone_station")
        return built < self.s.stations

    def want_drone(self) -> bool:
        """Estação montada e com menos drones do que a estratégia quer: o próximo craft é um drone."""
        if "drone" not in C.MACHINES or not self.gs.stations or self.gs.recipe_status("drone") == "locked":
            return False
        docked = sum(len(m.station.drones) for m in self.gs.stations)
        return docked < self.s.drones and any(m.station.free_slots() for m in self.gs.stations)

    def cost(self, kind) -> dict:
        """Receita que o jogador junta antes de ir fabricar. A estação vem junto com os drones dela. Máquina sem o
        construtor no inventário (v0.5 M1): soma a receita dele (o 1º build fabrica ele antes)."""
        cost = dict(C.MACHINES[kind].cost)
        if C.MACHINES[kind].placeable and "constructor" in C.MACHINES and not self.gs.has_constructor:
            for r, n in C.MACHINES["constructor"].cost.items():
                cost[r] = cost.get(r, 0) + n
        if kind == "drone_station" and "drone" in C.MACHINES:
            for r, n in C.MACHINES["drone"].cost.items():
                cost[r] = cost.get(r, 0) + n * self.s.drones
        return cost

    def _ready(self, kind) -> bool:
        """v0.5 M1: máquina vem do construtor. Na base, fabrica o construtor se ainda não tem e diz se dá pra
        construir `kind` com o que está no inventário (o construtor gasta só dele)."""
        if not self.gs.has_constructor and not self.gs.craft("constructor"):
            return False
        return self.gs.build_status(kind) == "ok"

    def _build(self, kind, tile) -> bool:
        """Constrói pela regra real (state.build). A animação de construir (C.BUILD_TIME) não entra: o sim anda
        o relógio pelo _advance, então a máquina já sai pronta."""
        if not self.gs.build(kind, tile):
            return False
        self.gs.machines[-1].build = 0.0
        return True

    def craft_and_dock_drone(self) -> bool:
        """Fabrica 1 drone e põe no primeiro slot livre da estação (regra real: station_dock)."""
        self._set_player(self.home)
        if not self.gs.craft("drone"):
            return False
        station = next(m for m in self.gs.stations if m.station.free_slots())
        index = next(i for i, st in enumerate(self.gs.inventory.slots) if st and st.item == "drone")
        assert self.gs.station_dock(station, index, 1) == 1
        self._advance(self.s.craft_overhead)
        return True

    def _place_near(self, kind, tiles) -> bool:
        """Tenta colocar `kind` no primeiro tile de `tiles` que der, com o player parado do lado."""
        for tx, ty in tiles:
            for stand in ((tx, ty + 2), (tx + 1, ty + 2), (tx - 1, ty), (tx + 2, ty), (tx, ty - 1), (tx, ty + 1)):
                if not self._base_free(stand):
                    continue
                self.gs.player.x, self.gs.player.y = self._tile_pos(*stand)
                if self._build(kind, (tx, ty)):
                    self._set_player(self.home)
                    self._advance(self.s.craft_overhead)
                    return True
        return False

    def _station_spots(self, chest_tile):
        """Cantos 2×2 de chão livre (fora de veio e da cápsula) perto do baú (até ~4 tiles)."""
        cx, cy = chest_tile
        spots = []
        for ty in range(cy - 4, cy + 4):
            for tx in range(cx - 4, cx + 4):
                tiles = [(tx + dx, ty + dy) for dx in (0, 1) for dy in (0, 1)]
                if ((cx, cy) not in tiles
                        and all(self.base_world.is_floor(*t) and not self.gs.machine_at(t)
                                and t not in C.POD_TILES and not self.base_world.vein_at(*t) for t in tiles)):
                    spots.append((tx, ty))
        return spots

    def craft_and_place_chest(self) -> bool:
        """Baú dentro da zona de O₂ (o fabricador enxerga ele), num lugar com espaço pra estação do lado."""
        self._set_player(self.home)
        if not self._ready("chest_small"):
            return False
        bx, by = C.BASE_CENTER
        cand = sorted((math.hypot((x + 0.5) * C.TILE - bx, (y + 1) * C.TILE - by), (x, y))
                      for y in range(by // C.TILE - 6, by // C.TILE + 7) for x in range(bx // C.TILE - 6, bx // C.TILE + 7))
        tiles = [t for d, t in cand if d <= C.BASE_RADIUS - 8 and self._station_spots(t)]
        if not self._place_near("chest_small", tiles):
            raise AssertionError("não achou lugar pro baú na base")
        chest = self.gs.machines[-1]                       # o baú que acabou de colocar
        for r in C.RESOURCES:                             # o jogador marca Recebe tudo no painel do baú
            drones.toggle_receive(chest, r)
        return True

    def craft_and_place_station(self) -> bool:
        """Fabrica a estação e coloca num 2×2 livre a até 3 tiles do baú da base."""
        self._set_player(self.home)
        chests = self.gs.base_chests()
        if not chests or not self._ready("drone_station"):
            return False
        if not self._place_near("drone_station", self._station_spots((chests[0].tx, chests[0].ty))):
            raise AssertionError("não achou lugar pra estação perto do baú da base")
        while self.want_drone() and self.affordable("drone"):     # os drones que ele já juntou
            self.craft_and_dock_drone()
        return True

    def empty_base_storage(self):
        """Na base: tira do baú da base e do buffer das estações tudo que é minério (os drones trouxeram)."""
        got = 0
        for chest in self.gs.base_chests():
            for r in C.RESOURCES:
                n = chest.storage.count(r)
                if n:
                    moved = n - self.gs.inventory.add(r, n)
                    chest.storage.remove(r, moved)
                    got += moved
        for m in self.gs.stations:
            got += self.gs.collect_station(m)
        self.res.drone_units += got

    # ---- ações ----
    def go_base(self):
        """Volta pela trilha mais curta até a zona e espera o O₂ encher."""
        d = self.field[self.cur]
        if d > 0:
            self._advance(d * self.tw * self.s.walk_factor, outside=True, what="andar")
        self._set_player(self.home)
        self._advance((self.gs.o2_max - self.gs.o2) / C.O2_REFILL)

    # ---- destroços (Marco 3) ----
    def loot_trip(self):
        """Vai a pé até a caixa da nave de carga mais perto, saqueia (o diagrama do tanque vem no saque), volta,
        lê o diagrama no fabricador, fabrica o tanque de O₂ e equipa. Caminho real na superfície (ida e volta), com O₂ caindo."""
        w = self.base_world
        wreck = w.wrecks[0]
        cx, cy = wreck.crate
        stand = next(t for t in ((cx, cy + 1), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1)) if w.is_floor(*t))
        walk = surface_walk_to_zone(w, stand) * self.tw * self.s.walk_factor
        self._set_player(self.home)
        self._advance(walk, outside=True, what="andar")
        self.gs.enter_layer(SURFACE, self._tile_pos(*stand))
        crate = self.gs.surface.crates[wreck.crate]
        self.gs.open_crate(crate)
        self.res.loot_units += self.gs.crate_take(crate)
        self._advance(self.s.craft_overhead, outside=True, what="base")
        self._advance(walk, outside=True, what="andar")
        self._set_player(self.home)
        self._advance((self.gs.o2_max - self.gs.o2) / C.O2_REFILL)
        self.gs.read_diagram("diagram_o2_tank", "t1")
        if self.gs.craft("o2_tank"):
            index = next(i for i, st in enumerate(self.gs.inventory.slots) if st and st.item == "o2_tank")
            self.gs.equip_from(index)
            self._advance(self.s.craft_overhead)
            self.res.tank_at = self.t

    # ---- magmatita (v0.4) ----
    def magma_trip(self, need) -> bool:
        """Estratégias da caverna: a magmatita só nasce na SUPERFÍCIE, em volta das fumarolas. Sai da base a pé
        (caminho real, O₂ caindo) até a rocha de magmatita mais perto que cabe no O₂, minera as que alcança dali
        (regra real: `_break_tile`) e volta. False = nenhuma rocha alcançável agora (espera o reaparecimento)."""
        w = self.base_world
        field = surface_zone_field(w)
        best = None
        for y in range(w.height):
            for x in range(w.width):
                if w.tiles[y][x] != C.SMALL_MAGMATITE:
                    continue
                for sx, sy in ((x, y + 1), (x - 1, y), (x + 1, y), (x, y - 1)):
                    d = field.get((sx, sy))
                    if d is not None and (best is None or d < best[0]):
                        best = (d, (sx, sy))
        if best is None:
            return False
        walk = best[0] * self.tw * self.s.walk_factor
        if 2 * walk + self.s.o2_margin + 4 * C.MINE_TIME[C.SMALL_MAGMATITE] > self.gs.o2_max / C.O2_DRAIN:
            return False
        stand = best[1]
        self._set_player(self.home)
        self._advance(walk, outside=True, what="andar")
        self.gs.enter_layer(SURFACE, self._tile_pos(*stand))
        R = C.MINE_REACH
        got = 0
        for yy in range(stand[1] - R, stand[1] + R + 1):
            for xx in range(stand[0] - R, stand[0] + R + 1):
                if got >= need or w.get(xx, yy) != C.SMALL_MAGMATITE:
                    continue
                self._advance(C.MINE_TIME[C.SMALL_MAGMATITE] + self.s.mine_overhead, outside=True, what="minerar")
                before = self.gs.inventory.count("magmatite")
                self.gs._break_tile((xx, yy), C.SMALL_MAGMATITE)
                got += self.gs.inventory.count("magmatite") - before
                self.res.tiles_mined += 1
        self.res.magma_trips += 1
        self._advance(walk, outside=True, what="andar")
        self._set_player(self.home)
        self._advance((self.gs.o2_max - self.gs.o2) / C.O2_REFILL)
        return True

    def _xy_spawn(self):
        return int(C.SPAWN_POS[0] // C.TILE), int((C.SPAWN_POS[1] - 1) // C.TILE)

    def craft_and_place(self, kind) -> bool:
        self._set_player(self.home)
        if not self._ready(kind):
            return False
        sx, sy = self._next_site()
        self.gs.player.x, self.gs.player.y = self._tile_pos(sx + 1, sy)
        ok = self._build(kind, (sx, sy))
        assert ok, f"não conseguiu colocar {kind} em {(sx, sy)}"
        self._set_player(self.home)
        self._advance(self.s.craft_overhead)
        if C.MACHINES[kind].index is not None:   # painel solar não conta como "a próxima máquina de Ti"
            self.plan = None
            if self.s.pick == "balanced":
                self.rr += 1
        return True

    def _next_site(self):
        """Tiles pares (x e y) de chão, do mais perto pro mais longe da base: sobra corredor entre as máquinas."""
        if not self.sites:
            bw = self.base_world                             # as máquinas de Ti ficam na base (superfície)
            used = {(m.tx, m.ty) for m in self.gs.surface.machines}
            cx, cy = C.BASE_TILE
            cand = [(math.hypot(x - cx, y - cy), (x, y))
                    for y in range(2, bw.height - 2, 2) for x in range(2, bw.width - 2, 2)
                    if bw.is_floor(x, y) and (x, y) not in used and (x, y) not in C.POD_TILES
                    and (x, y) != self._xy_spawn() and math.hypot(x - cx, y - cy) >= 2
                    and bw.is_floor(x + 1, y)]
            cand.sort()
            self.sites = [t for _, t in cand[:40]][::-1]   # pop() pega o mais perto
        site = self.sites.pop()
        while self.gs.machine_at(site):                     # a estação (2×2) pode ter ocupado o lugar
            site = self.sites.pop()
        return site

    def _mine(self, i):
        """Minera o tile i parado (tempo real da dureza) e quebra com a regra do jogo."""
        x, y = self._xy(i)
        kind = self.world.tiles[y][x]
        assert self.gs.can_mine((x, y)), "fora do alcance"
        self._advance(C.MINE_TIME[kind] + self.s.mine_overhead, outside=not self.zone[self.cur], what="minerar")
        res = C.TILE_RESOURCE.get(kind)
        before = self._units()
        self.gs._break_tile((x, y), kind)
        self.res.tiles_mined += 1
        if res:
            self._bump_near(res, x, y, -1)
        self._opened(i)
        return self._units() - before

    def search(self, wanted):
        """Dijkstra (tempo) do tile atual até um tile de onde dá pra minerar um minério `wanted` e voltar com O₂."""
        start = self.cur
        o2 = self.gs.o2 / C.O2_DRAIN - self.s.o2_margin     # segundos de O₂ utilizáveis
        tw = self.tw
        g = {start: 0.0}
        used = {start: 0.0}     # O₂ gasto (só fora da zona)
        walk = {start: 0.0}     # tiles andados (pra estimar a volta)
        prev = {}
        heap = [(0.0, start)]
        base_ret = self.field[start]
        while heap:
            d, u = heapq.heappop(heap)
            if d > g[u]:
                continue
            if u != start and any(self.near[r][u] for r in wanted):
                ret = min(self.field[u], walk[u] + base_ret) * tw
                if used[u] + max(C.MINE_TIME.values()) + ret <= o2:
                    path = [u]
                    while path[-1] != start:
                        path.append(prev[path[-1]])
                    return path[::-1][1:]
            for v, step in self._neighbors(u, walk_only=False):
                k = self._tile(v)
                cost = step * tw + (C.MINE_TIME[k] if k not in C.FLOOR_TILES else 0.0)
                nd = d + cost
                nu = used[u] + (0.0 if self.zone[v] else cost)
                if nu > o2:
                    continue
                if nd < g.get(v, INF):
                    g[v], used[v], walk[v], prev[v] = nd, nu, walk[u] + step, u
                    heapq.heappush(heap, (nd, v))
        return None

    def _ret_cost(self, i):
        return self.field[i] * self.tw * self.s.walk_factor

    def mine_here(self, wanted):
        """Minera o que der ao alcance (primeiro o que falta), sem passar do O₂ pra voltar."""
        got = 0
        ores = sorted(self._ores_in_reach(self.cur), key=lambda o: C.TILE_RESOURCE[o[1]] not in wanted)
        for i, kind in ores:
            if self.gs.o2 / C.O2_DRAIN - C.MINE_TIME[kind] - self._ret_cost(self.cur) < self.s.o2_margin:
                break
            got += self._mine(i)
        return got

    def walk_path(self, path):
        for i in path:
            if self._tile(i) not in C.FLOOR_TILES:
                self._mine(i)
            if self.cur == self.BASE and self.cave:          # base -> cratera -> rampa -> chegada
                step = self.ramp_k
            else:
                x0, y0 = self._xy(self.cur)
                x1, y1 = self._xy(i)
                step = SQRT2 if (x0 != x1 and y0 != y1) else 1.0
            self._advance(step * self.tw * self.s.walk_factor, outside=not self.zone[i], what="andar")
            self._set_player(i)

    def _units(self):
        """Recursos no inventário (o inventário tem slots; as máquinas-item não contam aqui)."""
        return sum(self.gs.inventory.count(r) for r in C.RESOURCES)

    def affordable(self, kind):
        return all(self.gs.inventory.count(r) >= n for r, n in self.cost(kind).items())

    # ---- laço principal ----
    def run(self) -> Result:
        if self.s.wrecks:
            self.loot_trip()
        trip_t0, trip_units = self.t, 0
        while not self.res.finished and self.t < self.max_time:
            try:
                if self.zone[self.cur] and self.gs.stations:
                    self.empty_base_storage()
                if self.want_panel():
                    kind = "solar"
                elif self.want_drill():
                    kind = "drill"
                elif self.want_station():
                    kind = "drone_station" if self.gs.base_chests() else "chest_small"
                elif self.want_drone():
                    kind = "drone"
                else:
                    kind = self.choose()
                if kind is None:
                    if not self.zone[self.cur]:
                        self.go_base()
                    self.res.idle_reason = "fim chega antes da próxima máquina"
                    # a taxa não muda enquanto ele espera, então dá pra pular direto pro fim
                    left = (self.final_ti - self.gs.ti) / self.gs.ti_rate
                    self._advance(min(left + 1e-6, self.max_time - self.t), idle=True)
                    continue
                if self.affordable(kind):
                    if not self.zone[self.cur]:
                        self.go_base()
                        self._update_pace(trip_t0, trip_units)
                        trip_t0, trip_units = self.t, 0
                    if self.gs.recipe_status(kind) == "locked":
                        self.res.idle_reason = "esperando a receita liberar"
                        self._advance(min(self._unlock_eta(kind) + 1e-6, 30.0), idle=True)
                        continue
                    self._not_idle()
                    if kind == "drill":
                        self.craft_and_place_drill()
                    elif kind == "drone_station":
                        self.craft_and_place_station()
                    elif kind == "drone":
                        self.craft_and_dock_drone()
                    elif kind == "chest_small":
                        self.craft_and_place_chest()
                    else:
                        self.craft_and_place(kind)
                    continue
                self._not_idle()
                missing = [r for r, n in self.cost(kind).items() if self.gs.inventory.count(r) < n]
                if self.cave and "magmatite" in missing:     # magmatita só na superfície (em volta das fumarolas)
                    if not self.zone[self.cur]:
                        self.go_base()
                    need = self.cost(kind)["magmatite"] - self.gs.inventory.count("magmatite")
                    if self.magma_trip(need):
                        continue
                if self.zone[self.cur] and self.collect_trip(missing):
                    continue
                got = self.mine_here(missing)
                if got:
                    trip_units += got
                    continue
                path = self.search(missing)
                if path is None:
                    if self.zone[self.cur] and self.gs.o2 >= self.gs.o2_max - 1e-6:
                        self.res.idle_reason = "sem minério alcançável"
                        self._advance(30.0, idle=True)
                        continue
                    self.go_base()
                    self._update_pace(trip_t0, trip_units)
                    trip_t0, trip_units = self.t, 0
                    continue
                if self.zone[self.cur]:
                    self.res.trips += 1
                before = self._units()
                self.walk_path(path)
                trip_units += self._units() - before
            except Fainted:
                self._update_pace(trip_t0, trip_units)
                trip_t0, trip_units = self.t, 0
        self.res.total = self.t
        self.res.final_indices = {k: round(v) for k, v in self.gs.indices.items()}
        self.res.units = self._units() + sum(
            sum(C.MACHINES[m.kind].cost.values()) for m in self.gs.all_machines)
        self.res.machines = {k: sum(1 for m in self.gs.all_machines if m.kind == k) for k in C.MACHINES}
        self.res.machines["drone"] = sum(len(m.station.drones) for m in self.gs.stations)   # drones nas estações
        return self.res

    def _update_pace(self, t0, units):
        if units > 0:
            self.sec_per_unit = 0.5 * self.sec_per_unit + 0.5 * (self.t - t0) / units


# ---------------------------------------------------------------------------
# Rodar e imprimir
# ---------------------------------------------------------------------------
def simulate(strategy="guloso", seed=1, overrides=None, max_time=6 * 3600) -> Result:
    strat = STRATEGIES[strategy] if isinstance(strategy, str) else strategy
    with patched_config(overrides):
        return Sim(strat, seed, max_time).run()


def fmt(sec):
    if sec is None:
        return "—"
    m, s = divmod(int(round(sec)), 60)
    if m >= 60:
        return f"{m // 60}h{m % 60:02d}m"
    return f"{m}m{s:02d}s"


def table(title, results, markdown=False):
    marks = ["Ti 500"] + [s.name.capitalize() for s in C.STAGES[1:]]
    kinds = list(C.MACHINES)
    head = ["estratégia", "seed", *marks, "total", "espera total", "maior espera", "desm.", "drill un.",
            "drone un.", "déficit", "tanque", "saque", "magmat.", "aquec.", "cratera", "portão 1", "portão 2", "portão 3", "grande", "L1", "L2", "L3",
            "máquinas (" + "/".join(kinds) + ")"]
    rows = []
    for r in results:
        rows.append([r.strategy, str(r.seed), *[fmt(r.milestones.get(m)) for m in marks],
                     fmt(r.total) + ("" if r.finished else " (não acabou)"),
                     fmt(r.idle_total), fmt(r.idle_longest), str(r.faints), str(r.drill_units),
                     str(r.drone_units), fmt(r.deficit_time), fmt(r.tank_at), str(r.loot_units),
                     fmt(r.magma_at), fmt(r.heater_at), fmt(r.crater_at), *[fmt(r.gate_at.get(i)) for i in range(3)], fmt(r.giant_at),
                     *[fmt(r.lake_at.get(k)) for k in range(3)], "/".join(str(r.machines[k]) for k in kinds)])
    out = [f"\n{'### ' if markdown else '== '}{title}\n"]
    if markdown:
        out.append("| " + " | ".join(head) + " |")
        out.append("|" + "---|" * len(head))
        out += ["| " + " | ".join(row) + " |" for row in rows]
    else:
        widths = [max(len(h), *(len(row[c]) for row in rows)) for c, h in enumerate(head)]
        out.append("  ".join(h.ljust(w) for h, w in zip(head, widths)))
        out += ["  ".join(v.ljust(w) for v, w in zip(row, widths)) for row in rows]
    return "\n".join(out)


def run_suite(overrides=None, seeds=(1, 2, 3), strategies=tuple(STRATEGIES)):
    return [simulate(s, seed, overrides) for s in strategies for seed in seeds]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--current", action="store_true", help="só os números atuais do config.py")
    ap.add_argument("--overrides", type=Path, default=PROPOSAL_PATH, help="JSON com overrides (padrão: proposta)")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--ablate-t2", action="store_true", help="roda também a proposta sem as máquinas nv.2")
    ap.add_argument("--no-drills", action="store_true", help="roda também cada cenário sem drills, pra comparar")
    ap.add_argument("--no-energy", action="store_true", help="roda também sem energia (consumo zero), pra comparar")
    ap.add_argument("--no-drones", action="store_true", help="roda também sem a estação de drones, pra comparar")
    ap.add_argument("--geo", action="store_true", help="só o relatório da geografia (destroços, veios, minério perto)")
    args = ap.parse_args(argv)
    if args.geo:
        print(geo_report(args.seeds, args.markdown))
        return
    if args.no_energy:
        print(table("Números atuais SEM energia (antes do Marco 2)", run_suite(without_energy(None), args.seeds),
                    args.markdown))
    if args.no_drones:
        print(table("Números atuais SEM drones (antes do Marco 3)", run_suite(without_drones(None), args.seeds),
                    args.markdown))
    print(table("Números atuais (game/config.py)", run_suite(None, args.seeds), args.markdown))
    if args.no_drills:
        print(table("Números atuais SEM drills", run_suite(without_drills(None), args.seeds), args.markdown))
    if not args.current:
        ov = load_overrides(args.overrides)
        print(table(f"Proposta ({args.overrides.name})", run_suite(ov, args.seeds), args.markdown))
        if args.no_drills:
            print(table("Proposta SEM drills", run_suite(without_drills(ov), args.seeds), args.markdown))
        if args.ablate_t2:
            print(table("Proposta SEM nv.2 (as nv.2 valem a pena?)", run_suite(without_t2(ov), args.seeds),
                        args.markdown))


# ---------------------------------------------------------------------------
# Geografia (v0.4 Marco 2): a partida não quebrou? Distância a pé dos destroços e veios, minério perto da base
# ---------------------------------------------------------------------------
GEO_RADII = (15, 25, 40)          # raios (tiles) do "minério perto da base"


def _walk_field(world, start) -> dict:
    """Distância a pé (tiles, 4 vizinhos, sem cavar) de `start` até cada tile livre."""
    from collections import deque
    dist = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in dist and world.in_bounds(*n) and not world.is_solid(*n):
                dist[n] = dist[(x, y)] + 1
                queue.append(n)
    return dist


def _reach(dist, tiles) -> float:
    """Menor distância a pé até ficar do lado de algum dos `tiles` (ou em cima, se for chão)."""
    best = INF
    for x, y in tiles:
        for n in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            best = min(best, dist.get(n, INF))
    return best


def geo_stats(seed: int) -> dict:
    from game.surface_gen import generate_surface
    world = generate_surface(seed)
    dist = _walk_field(world, C.BASE_TILE)
    bx, by = C.BASE_TILE
    wrecks = [(round(math.hypot(w.center[0] - bx, w.center[1] - by)), _reach(dist, [w.crate])) for w in world.wrecks
              if not w.rich]                                   # o rico (M3.2) fica atrás do gelo-portão
    veins = [(v.resource, round(math.hypot(v.tx + 1 - bx, v.ty + 1 - by)), _reach(dist, v.tiles)) for v in world.veins]
    ore = {}
    for r in GEO_RADII:
        small = wall = 0
        for y in range(by - r, by + r + 1):
            for x in range(bx - r, bx + r + 1):
                if math.hypot(x - bx, y - by) > r:
                    continue
                k = world.get(x, y)
                small += k in C.SMALL_ROCKS
                wall += k in C.ORE_TILES
        ore[r] = (small, wall)
    geo = getattr(world, "geo", None)
    regions = None
    if geo is not None:
        import numpy as np
        regions = np.bincount(geo.region.ravel(), minlength=4) / geo.region.size
    return dict(seed=seed, wrecks=wrecks, veins=veins, ore=ore, regions=regions,
                formations=len(geo.formations) if geo is not None else 0)


def geo_report(seeds, markdown=False) -> str:
    lines = ["Geografia da superfície (distância reta / a pé, em tiles; minério = rochas pequenas + minério de morro)"]
    for seed in seeds:
        st = geo_stats(seed)
        lines.append(f"seed {seed}:")
        lines.append("  destroços: " + ", ".join(f"{d}/{w if w < INF else '∞'}" for d, w in st["wrecks"]))
        lines.append("  veios:     " + ", ".join(f"{r} {d}/{w if w < INF else '∞'}" for r, d, w in st["veins"]))
        lines.append("  minério:   " + ", ".join(f"r{r}: {s} rochas + {w} no morro" for r, (s, w) in st["ore"].items()))
        if st["regions"] is not None:
            names = ("planalto", "salar", "basalto", "gelada")
            lines.append("  regiões:   " + ", ".join(f"{n} {p:.0%}" for n, p in zip(names, st["regions"]))
                         + f" · {st['formations']} formações")
    return "\n".join(lines)


def without_drills(overrides):
    """Mesmos overrides, mas com a receita da drill trancada (o jogo como era antes dos veios)."""
    ov = copy.deepcopy(overrides or {})
    ov.setdefault("MACHINES", {}).setdefault("drill", {})["unlock_ti"] = 10**12
    return ov


def without_drones(overrides):
    """Mesmos overrides, mas com a receita da estação de drones trancada (o jogo como era antes do Marco 3)."""
    ov = copy.deepcopy(overrides or {})
    ov.setdefault("MACHINES", {}).setdefault("drone_station", {})["unlock_ti"] = 10**12
    return ov


def without_energy(overrides):
    """Mesmos overrides, mas nenhuma máquina consome energia (o jogo como era antes do Marco 2)."""
    ov = copy.deepcopy(overrides or {})
    ov["POWER_USE"] = {}
    return ov


def without_t2(overrides):
    """Mesmos overrides, mas com as receitas da última tier trancadas (nunca liberam)."""
    ov = copy.deepcopy(overrides or {})
    with patched_config(ov):
        t2 = [k for k, m in C.MACHINES.items() if m.unlock_ti >= C.STAGES[C.MIST_STAGE - 1].ti and m.index is not None]
    machines = ov.setdefault("MACHINES", {})
    for k in t2:
        machines.setdefault(k, {})["unlock_ti"] = 10**12
    return ov


if __name__ == "__main__":
    main()
