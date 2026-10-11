"""Simulador de jogador pra medir o ritmo do jogo (sem pygame, sem janela).

    uv run python tools/dev/balance_sim.py                    # atual × proposta (balance_proposal.json)
    uv run python tools/dev/balance_sim.py --current          # só os números do config.py
    uv run python tools/dev/balance_sim.py --overrides x.json # outro arquivo de overrides
    uv run python tools/dev/balance_sim.py --markdown         # tabelas em Markdown (pro reports/dev/balance.md)
    uv run python tools/dev/balance_sim.py --no-energy        # roda também sem energia (como era antes do Marco 2)

O que é real e o que é aproximado
---------------------------------
Real (vem do jogo): o mapa (`World.generate`, mesma seed), o inventário, os drops (`GameState._break_tile`,
com o `rng` do estado), `can_mine` (alcance), `craft`/`can_place`/`place`, a produção das máquinas
(`GameState._update_machines`), os estágios (`stage_for_ti`), o desmaio (`_faint` + `_update_faint` frame a frame) e
todos os números do `game/config.py` (velocidade, tempos de mineração, O₂, receitas, taxas, limiares).

Aproximado (o simulador decide no lugar do jogador):
- Deslocamento: Dijkstra no grid de tiles, 8 vizinhos (diagonal só se os dois vizinhos retos estiverem livres,
  igual a caixa de colisão faria), custo = distância × TILE / PLAYER_SPEED. Entrar numa rocha custa o tempo de
  minerar ela. Isso é o caminho ótimo de um jogador que conhece o mapa; o jogador "casual" anda 30% mais devagar
  que o planejado (desvio, mira, colisão), o que é o fator de realismo.
  Não usamos o `Player.move` frame a frame porque seria ~50× mais lento e o resultado é o mesmo em linha reta.
- Máquinas colocadas não bloqueiam o caminho no grid (são caixas de 24×18 px num tile de 32: dá pra passar do lado).
- Craftar e colocar custa um tempo fixo por máquina (`craft_overhead`), cobrindo menu + andar até o lugar.
- Drills (depois da Névoa): o jogador fabrica até `Strategy.drills` drills e põe cada uma num veio livre alcançável
  a pé (ferro primeiro). Ir e voltar custa a distância andando real (com O₂). A extração é a regra real do jogo
  (`_update_drill`). Na base, antes de sair pra minerar um recurso, ele vai coletar uma drill desse recurso se a
  viagem custar menos do que minerar aquelas unidades no ritmo dele. "Sem drills" = mesma simulação com a receita
  da drill trancada (`--no-drills` / `without_drills`).
- Energia (Marco 2): a produção das máquinas e das drills já sai no ritmo da energia, porque o simulador usa o
  `_update_machines` e o `ti_rate` reais. O jogador fabrica um painel solar (na base, como outra máquina qualquer)
  sempre que o fator cai abaixo de `PANEL_BELOW`. "Sem energia" = consumo zerado (`--no-energy` / `without_energy`).

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
      {"STAGES": {"mist": 8000, "green": 60000}}                    Ti de cada estágio
    `cost` substitui a receita inteira. O código do jogo lê `C.<nome>` na hora do uso, então trocar o atributo
    do módulo basta.
    """
    overrides = overrides or {}
    saved = {}
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


STRATEGIES = {
    # conhece o mapa, caminho ótimo, sempre a máquina com melhor Ti/s por segundo de coleta
    "guloso": Strategy("guloso"),
    # joga direito mas monta de tudo: alterna os tipos da maior tier liberada
    "variado": Strategy("variado", pick="balanced", craft_overhead=4.0, mine_overhead=0.1),
    # humano normal: anda 30% mais que o planejado (pode até desmaiar), volta com folga, demora pra mirar
    "casual": Strategy("casual", pick="balanced", walk_factor=1.3, o2_margin=12.0, craft_overhead=6.0,
                       mine_overhead=0.3),
}


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
    tiles_mined: int = 0
    units: int = 0                                   # recursos coletados
    time_by: dict = field(default_factory=dict)      # andar / minerar / base / espera
    deficit_time: float = 0.0                        # segundos com falta de energia (máquinas mais lentas)


# ---------------------------------------------------------------------------
# O jogador simulado
# ---------------------------------------------------------------------------
class Sim:
    def __init__(self, strategy: Strategy, seed: int = 1, max_time: float = 6 * 3600):
        self.s = strategy
        self.gs = GameState(rng=random.Random(seed))
        self.world = self.gs.world
        self.W, self.H = self.world.width, self.world.height
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
        self.cur = self._i(*self.gs.player.tile)
        self.blocked = {self._i(*t) for t in C.POD_TILES}
        self.zone = [self._in_zone(i) for i in range(self.W * self.H)]
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
        px, py = self._pos(i)
        return math.hypot(px - C.BASE_CENTER[0], py - C.BASE_CENTER[1]) <= C.BASE_RADIUS

    def _tile(self, i):
        x, y = self._xy(i)
        return self.world.tiles[y][x]

    def _walkable(self, i):
        return self._tile(i) == C.FLOOR and i not in self.blocked

    def _passable(self, i):
        """Dá pra chegar nele andando ou minerando."""
        return i not in self.blocked and (self._tile(i) == C.FLOOR or self._tile(i) in C.MINE_TIME)

    def _set_player(self, i):
        self.gs.player.x, self.gs.player.y = self._pos(i)
        self.cur = i

    def _neighbors(self, i, walk_only):
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
        self.near = {r: [0] * (self.W * self.H) for r in C.RESOURCES}
        for y in range(self.H):
            for x in range(self.W):
                res = C.ORE_TILES.get(self.world.tiles[y][x])
                if res:
                    self._bump_near(res, x, y, +1, R)

    def _bump_near(self, res, x, y, d, R=None):
        R = C.MINE_REACH if R is None else R
        arr = self.near[res]
        for yy in range(max(0, y - R), min(self.H, y + R + 1)):
            base = yy * self.W
            for xx in range(max(0, x - R), min(self.W, x + R + 1)):
                arr[base + xx] += d

    def _ores_in_reach(self, i):
        x, y = self._xy(i)
        R = C.MINE_REACH
        out = []
        for yy in range(y - R, y + R + 1):
            for xx in range(x - R, x + R + 1):
                k = self.world.get(xx, yy)
                if k in C.ORE_TILES:
                    out.append((self._i(xx, yy), k))
        return out

    # ---- distância andando até a zona de O₂ (em tiles), atualizada a cada tile quebrado ----
    def _init_field(self):
        self.field = [INF] * (self.W * self.H)
        heap = []
        for i in range(self.W * self.H):
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
                self.gs.o2 = min(C.O2_MAX, self.gs.o2 + C.O2_REFILL * step)
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
        self.cur = self._i(*self.gs.player.tile)
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
        units = sum(max(0, n - self.gs.inventory[r]) for r, n in cost.items())
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
        return self._trip_time(vein) + self.s.o2_margin <= C.O2_MAX / C.O2_DRAIN

    def free_vein(self):
        """Veio livre alcançável a pé com um tanque de O₂, preferindo tipo ainda sem drill (ferro primeiro)."""
        taken = {(d.tx, d.ty) for d in self.gs.drills}
        have = {d.resource for d in self.gs.drills}
        options = [v for v in self.world.veins if (v.tx, v.ty) not in taken
                   and self._vein_walk(v) < INF and self._trip_fits_o2(v)]
        order = {r: i for i, r in enumerate(C.RESOURCES)}
        return min(options, key=lambda v: (v.resource in have, order[v.resource], self._vein_walk(v)), default=None)

    def want_drill(self) -> bool:
        if "drill" not in C.MACHINES or self.gs.recipe_status("drill") == "locked":
            return False
        built = len(self.gs.drills) + self.gs.machines_owned["drill"]
        return built < self.s.drills and self.free_vein() is not None

    def _visit_vein(self, vein, action):
        """Sai da base, vai até o veio (O₂ caindo), faz `action` lá e volta pra base (go_base)."""
        self._set_player(self._i(*self._xy_spawn()))
        walk = self._vein_walk(vein) * self.tw * self.s.walk_factor
        self._advance(walk, outside=True, what="andar")
        below = (vein.tx, vein.ty + 2)                 # parado logo abaixo do veio (sempre chão)
        self.gs.player.x, self.gs.player.y = self._pos(self._i(*below))
        self.cur = self._i(*below)
        action()
        self._advance(self.s.craft_overhead / 2, outside=True, what="base")
        self.go_base()

    def craft_and_place_drill(self):
        self._set_player(self._i(*self._xy_spawn()))
        vein = self.free_vein()
        if vein is None or not self.gs.craft("drill"):
            return False
        self._visit_vein(vein, lambda: self._place_drill(vein))
        return True

    def _place_drill(self, vein):
        ok = self.gs.place("drill", (vein.tx, vein.ty))
        assert ok, f"não conseguiu colocar a drill no veio {vein}"

    def collect_trip(self, missing) -> bool:
        """Na base: vale ir buscar o que uma drill guardou em vez de minerar isso?"""
        best = None
        for d in self.gs.drills:
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

    # ---- ações ----
    def go_base(self):
        """Volta pela trilha mais curta até a zona e espera o O₂ encher."""
        d = self.field[self.cur]
        if d > 0:
            self._advance(d * self.tw * self.s.walk_factor, outside=True, what="andar")
        self._set_player(self._i(*self._xy_spawn()))
        self._advance((C.O2_MAX - self.gs.o2) / C.O2_REFILL)

    def _xy_spawn(self):
        return int(C.SPAWN_POS[0] // C.TILE), int((C.SPAWN_POS[1] - 1) // C.TILE)

    def craft_and_place(self, kind) -> bool:
        self._set_player(self._i(*self._xy_spawn()))
        if not self.gs.craft(kind):
            return False
        site = self._next_site()
        sx, sy = self._xy(site)
        self.gs.player.x, self.gs.player.y = self._pos(self._i(sx + 1, sy))
        ok = self.gs.place(kind, (sx, sy))
        assert ok, f"não conseguiu colocar {kind} em {(sx, sy)}"
        self._set_player(self._i(*self._xy_spawn()))
        self._advance(self.s.craft_overhead)
        if C.MACHINES[kind].index is not None:   # painel solar não conta como "a próxima máquina de Ti"
            self.plan = None
            if self.s.pick == "balanced":
                self.rr += 1
        return True

    def _next_site(self):
        """Tiles pares (x e y) de chão, do mais perto pro mais longe da base: sobra corredor entre as máquinas."""
        if not self.sites:
            used = {(m.tx, m.ty) for m in self.gs.machines}
            cx, cy = C.CRATER_CENTER
            cand = [(math.hypot(x - cx, y - cy), self._i(x, y))
                    for y in range(2, self.H - 2, 2) for x in range(2, self.W - 2, 2)
                    if self.world.tiles[y][x] == C.FLOOR and (x, y) not in used and (x, y) not in C.POD_TILES
                    and (x, y) != self._xy_spawn() and math.hypot(x - cx, y - cy) >= 2
                    and self.world.tiles[y][x + 1] == C.FLOOR]
            cand.sort()
            self.sites = [i for _, i in cand[:40]][::-1]   # pop() pega o mais perto
        return self.sites.pop()

    def _mine(self, i):
        """Minera o tile i parado (tempo real da dureza) e quebra com a regra do jogo."""
        x, y = self._xy(i)
        kind = self.world.tiles[y][x]
        assert self.gs.can_mine((x, y)), "fora do alcance"
        self._advance(C.MINE_TIME[kind] + self.s.mine_overhead, outside=not self.zone[self.cur], what="minerar")
        res = C.ORE_TILES.get(kind)
        before = dict(self.gs.inventory)
        self.gs._break_tile((x, y), kind)
        self.res.tiles_mined += 1
        if res:
            self._bump_near(res, x, y, -1)
        self._opened(i)
        return sum(self.gs.inventory.values()) - sum(before.values())

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
                cost = step * tw + (C.MINE_TIME[k] if k != C.FLOOR else 0.0)
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
        ores = sorted(self._ores_in_reach(self.cur), key=lambda o: C.ORE_TILES[o[1]] not in wanted)
        for i, kind in ores:
            if self.gs.o2 / C.O2_DRAIN - C.MINE_TIME[kind] - self._ret_cost(self.cur) < self.s.o2_margin:
                break
            got += self._mine(i)
        return got

    def walk_path(self, path):
        for i in path:
            if self._tile(i) != C.FLOOR:
                self._mine(i)
            x0, y0 = self._xy(self.cur)
            x1, y1 = self._xy(i)
            step = SQRT2 if (x0 != x1 and y0 != y1) else 1.0
            self._advance(step * self.tw * self.s.walk_factor, outside=not self.zone[i], what="andar")
            self._set_player(i)

    def affordable(self, kind):
        return all(self.gs.inventory[r] >= n for r, n in C.MACHINES[kind].cost.items())

    # ---- laço principal ----
    def run(self) -> Result:
        trip_t0, trip_units = self.t, 0
        while not self.res.finished and self.t < self.max_time:
            try:
                if self.want_panel():
                    kind = "solar"
                elif self.want_drill():
                    kind = "drill"
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
                    else:
                        self.craft_and_place(kind)
                    continue
                self._not_idle()
                missing = [r for r, n in C.MACHINES[kind].cost.items() if self.gs.inventory[r] < n]
                if self.zone[self.cur] and self.collect_trip(missing):
                    continue
                got = self.mine_here(missing)
                if got:
                    trip_units += got
                    continue
                path = self.search(missing)
                if path is None:
                    if self.zone[self.cur] and self.gs.o2 >= C.O2_MAX - 1e-6:
                        self.res.idle_reason = "sem minério alcançável"
                        self._advance(30.0, idle=True)
                        continue
                    self.go_base()
                    self._update_pace(trip_t0, trip_units)
                    trip_t0, trip_units = self.t, 0
                    continue
                if self.zone[self.cur]:
                    self.res.trips += 1
                before = sum(self.gs.inventory.values())
                self.walk_path(path)
                trip_units += sum(self.gs.inventory.values()) - before
            except Fainted:
                self._update_pace(trip_t0, trip_units)
                trip_t0, trip_units = self.t, 0
        self.res.total = self.t
        self.res.units = sum(self.gs.inventory.values()) + sum(
            sum(C.MACHINES[m.kind].cost.values()) for m in self.gs.machines)
        self.res.machines = {k: sum(1 for m in self.gs.machines if m.kind == k) for k in C.MACHINES}
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
            "déficit", "máquinas (" + "/".join(kinds) + ")"]
    rows = []
    for r in results:
        rows.append([r.strategy, str(r.seed), *[fmt(r.milestones.get(m)) for m in marks],
                     fmt(r.total) + ("" if r.finished else " (não acabou)"),
                     fmt(r.idle_total), fmt(r.idle_longest), str(r.faints), str(r.drill_units),
                     fmt(r.deficit_time), "/".join(str(r.machines[k]) for k in kinds)])
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
    args = ap.parse_args(argv)
    if args.no_energy:
        print(table("Números atuais SEM energia (antes do Marco 2)", run_suite(without_energy(None), args.seeds),
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


def without_drills(overrides):
    """Mesmos overrides, mas com a receita da drill trancada (o jogo como era antes dos veios)."""
    ov = copy.deepcopy(overrides or {})
    ov.setdefault("MACHINES", {}).setdefault("drill", {})["unlock_ti"] = 10**12
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
        t2 = [k for k, m in C.MACHINES.items() if m.unlock_ti >= C.STAGES[1].ti and m.index is not None]
    machines = ov.setdefault("MACHINES", {})
    for k in t2:
        machines.setdefault(k, {})["unlock_ti"] = 10**12
    return ov


if __name__ == "__main__":
    main()
