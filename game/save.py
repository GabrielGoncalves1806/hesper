"""Save/load: guarda o jogo em saves/slot1.json e traz de volta.

Python puro (nada de pygame), testado em tests/test_save.py.

Ideia central: **salvar só o que muda**. O mapa sai sempre igual da seed (world.py), então o save
não guarda as 128×128 casas: guarda a seed e só os tiles que ficaram diferentes do mapa gerado
(os que o jogador minerou). Pra carregar, gera o mapa da seed de novo e aplica as diferenças.

Formato do arquivo (JSON):

    {
      "version": 3,              # sobe quando o formato mudar (ver MIGRATIONS)
      "seed": 7,
      "world":     {...},        # tiles que mudaram
      "player":    {...},        # posição, direção, O₂, desmaio
      "inventory": {"slots": [...]},   # os 16 slots: [item, quantidade] ou null (v2)
      "machines":  [...],        # máquinas colocadas (conteúdo das drills, slots dos baús e, na
                                 # estação de drones, "buffer" + "drone_cargo": v3)
      "progress":  {...}         # índices, estágio, objetivos, terminais lidos, tempo de jogo...
    }

Estação de drones (v3): fica dentro da própria máquina, como os slots do baú:
    {"kind": "drone_station", "tx": .., "ty": .., "rotation": 0,
     "buffer": {"iron": 12}, "drone_cargo": [["ice", 8], null]}
Os drones NÃO guardam posição: ao carregar, nascem pousados nos pads. A carga que cada um levava
vem em "drone_cargo" e ele entrega (baú perto ou buffer) logo no primeiro frame, então nada some.
O contador de entregas (objetivo) fica em progress["drone_deliveries"].

Baú: {"kind": "chest", ..., "storage": [...], "filter": "iron"}. "filter" é o minério que os drones
entregam nele ("all", "iron", "silicon" ou "ice"); save sem o campo carrega como "all".

Como um sistema novo entra no save (baú, energia, drones...):
    1. escreva `coisa_to_dict(state)` e `coisa_from_dict(state, data)` aqui embaixo;
    2. acrescente ("coisa", coisa_to_dict, coisa_from_dict) em SECTIONS;
    3. se um save antigo não tiver essa chave, crie uma migração (ver MIGRATIONS) que preenche o padrão;
    4. acrescente o campo no teste de ida e volta (tests/test_save.py).

Segurança contra crash: a escrita é atômica (grava num arquivo temporário e renomeia por cima).
A leitura é tolerante: arquivo estragado, versão desconhecida ou campo faltando viram "sem save"
com um aviso no terminal, nunca um crash.
"""

import json
import os
import tempfile
from pathlib import Path

from game import config as C
from game import drones
from game.inventory import Inventory
from game.systems import GameState, Machine
from game.world import World

SAVE_VERSION = 3   # v3: estação de drones · v2: inventário com slots, baús e `crafted` (v1 = contador)
SAVE_PATH = C.ROOT_DIR / "saves" / "slot1.json"   # o smoke e os testes apontam pra outro lugar


def _path(path: Path | str | None) -> Path:
    # resolvido na hora (não no default do parâmetro): assim dá pra trocar SAVE_PATH no smoke
    return Path(path or SAVE_PATH)


# ---------------------------------------------------------------------------
# Mapa "virgem" de cada seed (pra saber o que mudou sem gerar o mundo a cada save)
# ---------------------------------------------------------------------------
_pristine: dict[int, list[list[int]]] = {}   # seed -> cópia dos tiles recém-gerados


def remember_pristine(world: World) -> None:
    """Guarda uma cópia dos tiles do mundo ANTES do jogador mexer (chamar logo depois de gerar)."""
    _pristine.setdefault(world.seed, [row[:] for row in world.tiles])


def pristine_tiles(seed: int) -> list[list[int]]:
    if seed not in _pristine:
        remember_pristine(World.generate(seed))   # ~0,15 s, só na primeira vez de cada seed
    return _pristine[seed]


def new_state(seed: int = C.WORLD_SEED) -> GameState:
    """GameState novinho, já com o mapa virgem guardado (o primeiro autosave não engasga)."""
    state = GameState(seed)
    remember_pristine(state.world)
    return state


# ---------------------------------------------------------------------------
# Cada sistema: to_dict (estado -> dados) e from_dict (dados -> estado)
# ---------------------------------------------------------------------------
def world_to_dict(state: GameState) -> dict:
    """Só os tiles diferentes do mapa gerado pela seed, como [x, y, tipo]."""
    world, original = state.world, pristine_tiles(state.world.seed)
    changed = [[x, y, world.tiles[y][x]]
               for y in range(world.height) for x in range(world.width)
               if world.tiles[y][x] != original[y][x]]
    return {"changed_tiles": changed}


def world_from_dict(state: GameState, data: dict) -> None:
    for x, y, kind in data["changed_tiles"]:
        state.world.set(int(x), int(y), int(kind))


def player_to_dict(state: GameState) -> dict:
    p = state.player
    return {"x": p.x, "y": p.y, "direction": p.direction,
            "o2": state.o2, "fainted": state.fainted, "faint_time": state.faint_time,
            "was_in_base": state.was_in_base}


def player_from_dict(state: GameState, data: dict) -> None:
    p = state.player
    p.x, p.y = float(data["x"]), float(data["y"])
    p.direction = data["direction"] if data["direction"] in ("down", "up", "left", "right") else "down"
    state.o2 = float(data["o2"])
    state.fainted = bool(data["fainted"])
    state.faint_time = float(data["faint_time"])
    state.was_in_base = bool(data["was_in_base"])


def _known_item(item) -> bool:
    return item in C.RESOURCES or item in C.MACHINES


def slots_from_data(data: list, size: int) -> Inventory:
    """Lista de slots do save -> Inventory do tamanho certo. Item que o jogo não conhece mais
    (removido do config) vira slot vazio, em vez de quebrar o load."""
    clean = [[d[0], int(d[1])] if d and _known_item(d[0]) and int(d[1]) > 0 else None for d in data[:size]]
    return Inventory.from_data(clean + [None] * (size - len(clean)))


def inventory_to_dict(state: GameState) -> dict:
    """Os 16 slots do player (a hotbar são os 8 primeiros)."""
    return {"slots": state.inventory.to_data()}


def inventory_from_dict(state: GameState, data: dict) -> None:
    state.inventory = slots_from_data(data["slots"], C.INVENTORY_SLOTS)


def machine_to_dict(m: Machine) -> dict:
    data = {"kind": m.kind, "tx": m.tx, "ty": m.ty, "rotation": m.rotation}
    if m.is_drill:
        data.update(resource=m.resource, stored=m.stored, timer=m.timer)
    if m.is_chest:
        data["storage"] = m.storage.to_data()
        data["filter"] = m.filter
    if m.is_station:
        data["buffer"] = dict(m.station.buffer)
        data["drone_cargo"] = [[d.resource, d.cargo] if d.cargo else None for d in m.station.drones]
    return data


def machine_from_dict(data: dict) -> Machine:
    kind = data["kind"]
    if kind not in C.MACHINES:
        raise ValueError(f"máquina desconhecida: {kind!r}")
    machine = Machine(kind, int(data["tx"]), int(data["ty"]), int(data["rotation"]) % 4,
                      resource=data.get("resource"), stored=int(data.get("stored", 0)),
                      timer=float(data.get("timer", 0.0)))
    if machine.is_chest:
        machine.storage = slots_from_data(data.get("storage", []), C.CHEST_SLOTS)
        chest_filter = data.get("filter", "all")          # saves antigos não têm o campo: "all"
        machine.filter = chest_filter if chest_filter in C.CHEST_FILTERS else "all"
    if machine.is_station:
        # drones recriados pousados; quem estava carregando volta com a carga e entrega no 1º frame
        machine.station = drones.new_station(machine)
        machine.station.buffer = {r: int(n) for r, n in data.get("buffer", {}).items()
                                  if r in C.RESOURCES and int(n) > 0}
        for drone, cargo in zip(machine.station.drones, data.get("drone_cargo", [])):
            if cargo and cargo[0] in C.RESOURCES and int(cargo[1]) > 0:
                drone.resource, drone.cargo = cargo[0], int(cargo[1])
    return machine


def machines_to_dict(state: GameState) -> list:
    return [machine_to_dict(m) for m in state.machines]


def machines_from_dict(state: GameState, data: list) -> None:
    state.machines = [machine_from_dict(d) for d in data]


def progress_to_dict(state: GameState) -> dict:
    """Terraformação, objetivos e tudo que "só cresce"."""
    return {
        "indices": dict(state.indices),
        "stage": state.stage,
        "smoothed_rate": state.smoothed_rate,           # pra estimativa do HUD não zerar ao carregar
        "play_time": state.play_time,
        "mined_total": dict(state.mined_total),
        "fabricator_opened": state.fabricator_opened,
        "drills_placed": state.drills_placed,
        "drill_collected": dict(state.drill_collected),
        "crafted": dict(state.crafted),
        "drone_deliveries": state.drone_deliveries,
        "logs_read": sorted(state.logs_read),
        "transition_sources": sorted([list(t) for t in state.transition_sources]),
    }


def progress_from_dict(state: GameState, data: dict) -> None:
    for key in state.indices:
        state.indices[key] = float(data["indices"][key])
    state.stage = int(data["stage"])
    state.smoothed_rate = float(data["smoothed_rate"])
    state.play_time = float(data["play_time"])
    for r in state.mined_total:
        state.mined_total[r] = int(data["mined_total"].get(r, 0))
    state.fabricator_opened = bool(data["fabricator_opened"])
    state.drills_placed = int(data["drills_placed"])
    for r in state.drill_collected:
        state.drill_collected[r] = int(data["drill_collected"].get(r, 0))
    for k in state.crafted:
        state.crafted[k] = int(data["crafted"].get(k, 0))
    state.drone_deliveries = int(data["drone_deliveries"])
    state.logs_read = {int(i) for i in data["logs_read"] if 0 <= int(i) < len(C.LOGS)}
    state.transition_sources = {(int(x), int(y)) for x, y in data["transition_sources"]}


# A ORDEM importa no load: o mundo vem antes de quem depende dele.
# Sistema novo? Uma linha aqui (veja o passo a passo no topo do arquivo).
SECTIONS = [
    ("world", world_to_dict, world_from_dict),
    ("player", player_to_dict, player_from_dict),
    ("inventory", inventory_to_dict, inventory_from_dict),
    ("machines", machines_to_dict, machines_from_dict),
    ("progress", progress_to_dict, progress_from_dict),
]


def state_to_dict(state: GameState) -> dict:
    data = {"version": SAVE_VERSION, "seed": state.world.seed}
    for name, to_dict, _ in SECTIONS:
        data[name] = to_dict(state)
    return data


def state_from_dict(data: dict) -> GameState:
    """Gera o mundo da seed e aplica cada seção por cima. Dado estranho levanta erro (quem chama trata)."""
    state = new_state(int(data["seed"]))
    for name, _, from_dict in SECTIONS:
        from_dict(state, data[name])
    return state


# ---------------------------------------------------------------------------
# Versões e migração
# ---------------------------------------------------------------------------
# Quando o formato mudar: suba SAVE_VERSION e registre aqui a função que converte
# um save da versão N pra N+1 (ela recebe o dict e devolve o dict atualizado).
def _v1_to_v2(data: dict) -> dict:
    """v1 -> v2: o inventário era um contador ({"resources": {...}, "machines_owned": {...}}).
    Agora são slots: empilha tudo do jeito que o jogo empilharia (recursos primeiro, depois as
    máquinas, na ordem do fabricador). O que não couber nos 16 slots é perdido (save v1 com
    centenas de itens; o v0.1 não tinha limite). `crafted` não existia: estima com o que o
    jogador tinha (guardado + colocado), que é o que os objetivos contavam no v1."""
    old = data["inventory"]
    inv = Inventory(C.INVENTORY_SLOTS)
    for r in C.RESOURCES:
        inv.add(r, int(old.get("resources", {}).get(r, 0)))
    owned = old.get("machines_owned", {})
    for k in C.MACHINE_ORDER:
        inv.add(k, int(owned.get(k, 0)))
    data["inventory"] = {"slots": inv.to_data()}
    placed = [m["kind"] for m in data["machines"]]
    data["progress"]["crafted"] = {k: int(owned.get(k, 0)) + placed.count(k) for k in C.MACHINES}
    return data


def _v2_to_v3(data: dict) -> dict:
    """v2 -> v3: chegou a estação de drones. Um save v2 não tem estação nenhuma, então só falta
    o contador de entregas (zero). As máquinas e o resto continuam iguais."""
    data["progress"]["drone_deliveries"] = 0
    return data


MIGRATIONS: dict = {1: _v1_to_v2, 2: _v2_to_v3}


class SaveError(Exception):
    """Save que não dá pra usar (estragado, de versão desconhecida...)."""


def migrate(data: dict) -> dict:
    """Leva um save de qualquer versão conhecida até a SAVE_VERSION atual."""
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= SAVE_VERSION:
        raise SaveError(f"versão de save desconhecida: {version!r} (este jogo entende até a {SAVE_VERSION})")
    while version < SAVE_VERSION:
        if version not in MIGRATIONS:
            raise SaveError(f"não sei migrar save da versão {version}")
        data = MIGRATIONS[version](data)
        version += 1
        data["version"] = version
    return data


# ---------------------------------------------------------------------------
# Disco
# ---------------------------------------------------------------------------
def write_save(state: GameState, path: Path | str | None = None) -> bool:
    """Salva de forma atômica. Devolve True se deu certo (erro de disco só avisa, não derruba o jogo).

    Atômica = grava tudo num arquivo temporário na MESMA pasta e só no fim troca pelo save de verdade
    (os.replace). Se o jogo morrer no meio, o save antigo continua inteiro.
    """
    path = _path(path)
    tmp_name = None
    try:
        text = json.dumps(state_to_dict(state), ensure_ascii=False, separators=(",", ":"))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())        # garante que chegou no disco antes de trocar
        os.replace(tmp_name, path)      # a troca é atômica: ou é o save velho, ou o novo inteiro
        return True
    except OSError as err:
        print(f"[save] não consegui salvar em {path}: {err}")
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        return False


def load_game(path: Path | str | None = None) -> GameState | None:
    """Carrega o save. Sem arquivo, arquivo estragado ou versão desconhecida: avisa e devolve None."""
    path = _path(path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SaveError("o arquivo não é um objeto JSON")
        return state_from_dict(migrate(data))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, SaveError) as err:
        # ValueError cobre JSON quebrado; KeyError/TypeError cobrem campo faltando ou do tipo errado
        print(f"[save] ignorando {path.name}: {err}")
        return None


def has_save(path: Path | str | None = None) -> bool:
    """Existe um save que dá pra carregar?"""
    return load_game(path) is not None
