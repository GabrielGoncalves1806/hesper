"""Save/load: guarda o jogo em saves/slot1.json e traz de volta.

Python puro (nada de pygame), testado em tests/test_save.py.

Ideia central: **salvar só o que muda**. O mapa sai sempre igual da seed (world.py), então o save
não guarda as 128×128 casas: guarda a seed e só os tiles que ficaram diferentes do mapa gerado
(os que o jogador minerou). Pra carregar, gera o mapa da seed de novo e aplica as diferenças.

Formato do arquivo (JSON):

    {
      "version": 1,              # sobe quando o formato mudar (ver MIGRATIONS)
      "seed": 7,
      "world":     {...},        # tiles que mudaram
      "player":    {...},        # posição, direção, O₂, desmaio
      "inventory": {...},        # recursos + máquinas fabricadas ainda não colocadas
      "machines":  [...],        # máquinas colocadas (e o conteúdo das drills)
      "progress":  {...}         # índices, estágio, objetivos, terminais lidos, tempo de jogo...
    }

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
from game.systems import GameState, Machine
from game.world import World

SAVE_VERSION = 1
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


def inventory_to_dict(state: GameState) -> dict:
    """Inventário de hoje: recursos soltos + estoque de máquinas fabricadas.
    Isolado aqui de propósito: quando o inventário virar slots, só esta dupla de funções muda."""
    return {"resources": dict(state.inventory), "machines_owned": dict(state.machines_owned)}


def inventory_from_dict(state: GameState, data: dict) -> None:
    # só copia as chaves que o jogo conhece (recurso/máquina removida do config não quebra o load)
    for r in state.inventory:
        state.inventory[r] = int(data["resources"].get(r, 0))
    for k in state.machines_owned:
        state.machines_owned[k] = int(data["machines_owned"].get(k, 0))


def machine_to_dict(m: Machine) -> dict:
    data = {"kind": m.kind, "tx": m.tx, "ty": m.ty, "rotation": m.rotation}
    if m.is_drill:
        data.update(resource=m.resource, stored=m.stored, timer=m.timer)
    return data


def machine_from_dict(data: dict) -> Machine:
    kind = data["kind"]
    if kind not in C.MACHINES:
        raise ValueError(f"máquina desconhecida: {kind!r}")
    return Machine(kind, int(data["tx"]), int(data["ty"]), int(data["rotation"]) % 4,
                   resource=data.get("resource"), stored=int(data.get("stored", 0)),
                   timer=float(data.get("timer", 0.0)))


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
# um save da versão N pra N+1 (ela recebe o dict e devolve o dict atualizado). Exemplo:
#     def _v1_to_v2(data):
#         data["chests"] = []          # saves antigos não tinham baú
#         return data
#     MIGRATIONS = {1: _v1_to_v2}
MIGRATIONS: dict = {}


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
