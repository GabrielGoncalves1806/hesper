"""Save/load: guarda um jogo num arquivo JSON e traz de volta (os arquivos de cada mundo: game/worlds.py).

Python puro (nada de pygame), testado em tests/test_save.py.

Ideia central: **salvar só o que muda**. O mapa de cada camada sai sempre igual da seed (o deserto do
surface_gen.py, a caverna do world.py), então o save não guarda as casas da superfície: guarda a seed e só os
tiles que ficaram diferentes do mapa gerado (paredes mineradas, rochas pequenas quebradas ou reaparecidas). Pra carregar,
gera o mapa da seed de novo e aplica as diferenças.

Formato do arquivo (JSON, v10 · v0.5 M3.1, mapa 256; igual ao v9 do M2, mas a mesma seed gera outro mundo, então o
v9 e os anteriores não carregam):

    {
      "version": 10,
      "seed": 7,
      "layer": "surface",          # camada em que o player está
      "layers": {                  # uma entrada por camada que já existe ("surface", e "cave" no Marco 2)
        "surface": {
          "changed_tiles": [[x, y, tipo], ...],
          "machines": [...],        # máquinas da camada (baús, drills e estações com o conteúdo)
          "rocks": {"timer": 3.5},   # relógio do reaparecimento das rochas pequenas (só superfície)
          "crates": [[x, y, slots, aberta], ...],   # Marco 3: só as caixas de destroço que mudaram
          "explored": "eJzt...",    # Marco 3: tiles vistos (bitset, zlib, base64)
          "crater_ice": 0,          # v0.4 M2: tampa de gelo da cratera, 0 (tampada) a 4 (vazia); só superfície
          "base": [...]             # v9: blocos da base (chão, parede, portas), ver abaixo; ausente = sem base
        }
      },
      "player":    {...},          # posição, direção, O₂, desmaio
      "inventory": {"slots": [...]},
      "progress":  {...},          # índices, estágio, objetivos, terminais lidos, tempo de jogo...
      "world": {"name": "Mundo 1", "seed": 7, "created": "2026-10-13T14:02", "played_s": 734.2}
    }

`world` (mundos com nome e seed, game/worlds.py): entrou SEM subir a versão (o v7 é do Marco 2 do v0.4). É
opcional no load: save sem ele carrega como "Mundo 1" criado "agora". A seed que gera o mapa continua sendo
a `seed` da raiz; `world.seed` é a mesma, repetida, e `world.played_s` repete o `progress.play_time`.

Baú: {"kind": "chest", ..., "storage": [...], "name": "Minério",
      "sends": ["ice"], "receives": ["iron", "silicon"], "batch": 10}
Drill: {"kind": "drill", ..., "resource": "iron", "timer": 3.2, "storage": [["iron", 12]],
        "sends": ["iron"], "receives": [], "batch": 10}
Bloco da base (v9): {"kind": "base_wall", "tx": 70, "ty": 80}. A porta dupla é UM objeto: {"kind": "base_door2",
        "tx": 70, "ty": 80, "orient": "h"|"v"} com a âncora na metade de oeste/norte. Nada de estado de porta (nasce
        fechada) nem da vedação (recalculada no load, sem som).
Dispersor de O₂ (v9): {"kind": "o2_dispenser", ..., "storage": [["water_capsule", 2]], "burn": 80.5, "sealed_once": true}.
        `burn` = segundos que faltam da cápsula que está sendo gasta (já saiu do slot).
Derretedor (v0.5 M2, ainda v8): {"kind": "melter", ..., "timer": 4.0, "storage": [["ice", 12], ["water_capsule", 2]],
        "sends": ["water_capsule"], "receives": [], "batch": 10}. Slot 0 = gelo, slot 1 = cápsulas. Sem "storage"
        (derretedor de antes) carrega vazio: não precisou subir a versão.
Estação: {"kind": "drone_station", ..., "buffer": {"iron": 12}, "drones": [["ice", 8], [None, 0], None, None]}
"drones" são os 4 slots: null = vazio; [minério, carga] = tem drone. Os drones nascem pousados nos pads.

**Saves antigos NÃO migram**: v1 a v5 (v0.1/v0.2: o v0.3 exigiu novo jogo) e v6 (v0.3 e v0.4 Marco 1: o
mundo da seed mudou inteiro no Marco 2, com relevo, regiões e formações, então os tiles mudados de um save v6 não
batem com o mapa novo). O `probe` devolve "old" e a tela de título mostra "Save de uma versão antiga · comece um
novo jogo"; o arquivo não é apagado: quando um jogo novo é salvo por cima, ele vira `slot1.v6.json` (`backup_old`).
A geografia (`game/geo.py · Geo`) não vai no save: sai da seed de novo no load.

Como um sistema novo entra no save:
    1. escreva `coisa_to_dict(state)` e `coisa_from_dict(state, data)` aqui embaixo;
    2. acrescente ("coisa", coisa_to_dict, coisa_from_dict) em SECTIONS (ou no dict da camada);
    3. se um save v7 não tiver essa chave, crie uma migração v7 -> v8 (ver MIGRATIONS);
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
from game import layers
from game.base import BaseBlock, BaseGrid
from game.base import H as ORIENT_H, V as ORIENT_V
from game.equipment import Equipment
from game.explore import Explored
from game.inventory import Inventory, Stack, max_stack
from game.rock_respawn import RockRespawn
from game.surface_gen import pristine_tiles as surface_pristine
from game.systems import GameState, Machine, clean_chest_name
from game.world import World
from game.wrecks import loot_for

SAVE_VERSION = 10  # v10 (v0.5 M3.1): superfície 256×256 (a mesma seed gera outro mundo) · v9: blocos da base e Dispersor
FIRST_VERSION = 10  # saves com versão menor que essa são de outra época do jogo: "save antigo" (v1–v9, não migram)
# Numeração dos estágios dentro do "progress": 2 = v0.4 (Tempestade, Árido, Névoa, Verde). O 1 (os 3 estágios do
# v0.3) só existia no save v6, que não carrega mais.
STAGE_SCHEME = 2
# Save único de antes dos mundos (v0.4): o jogo agora usa saves/world1..3.json (game/worlds.py), que migra
# este arquivo pro mundo 1 sem apagar. Continua sendo o padrão do write_save/probe sem caminho (testes).
SAVE_PATH = C.ROOT_DIR / "saves" / "slot1.json"   # o smoke e os testes apontam pra outro lugar


def _path(path: Path | str | None) -> Path:
    # resolvido na hora (não no default do parâmetro): assim dá pra trocar SAVE_PATH no smoke
    return Path(path or SAVE_PATH)


# ---------------------------------------------------------------------------
# Mapa "virgem" de cada camada e seed (pra saber o que mudou sem gerar o mundo a cada save)
# ---------------------------------------------------------------------------
_pristine: dict[tuple[str, int], list[list[int]]] = {}   # (camada, seed) -> cópia dos tiles recém-gerados


def remember_pristine(world: World, key: str = layers.CAVE) -> None:
    """Guarda uma cópia dos tiles da caverna ANTES do jogador mexer (o deserto já tem cache próprio)."""
    if key != layers.SURFACE:
        _pristine.setdefault((key, world.seed), [row[:] for row in world.tiles])


def pristine_tiles(seed: int, key: str = layers.SURFACE) -> list[list[int]]:
    if key == layers.SURFACE:
        return surface_pristine(seed)
    if (key, seed) not in _pristine:
        remember_pristine(World.generate(seed), key)   # ~0,15 s, só na primeira vez de cada seed
    return _pristine[(key, seed)]


def new_state(seed: int = C.WORLD_SEED) -> GameState:
    """GameState novinho, já com o mapa virgem guardado (o primeiro autosave não engasga)."""
    return GameState(seed)


# ---------------------------------------------------------------------------
# Cada sistema: to_dict (estado -> dados) e from_dict (dados -> estado)
# ---------------------------------------------------------------------------
def derived_tiles(layer) -> set[tuple[int, int]]:
    """Tiles que saem dos índices (v0.4 Marco 3) e não entram no `changed_tiles`: a caixa dos gelos-portão. Desde o
    M3.5 eles ficam areia (o gelo bate por retângulo, refeito pelo _apply_thaw do load), então isto é só garantia:
    nada mexe neles (não minera e não vira outra coisa)."""
    geo = layer.geo
    return {t for p in geo.pockets for t in p.gate.tiles} if geo is not None else set()


def tiles_to_list(state: GameState, key: str) -> list:
    """Só os tiles da camada diferentes do mapa gerado pela seed, como [x, y, tipo] (sem os derivados)."""
    layer = state.layers[key]
    world, original = layer.world, pristine_tiles(state.seed, key)
    skip = derived_tiles(layer)
    return [[x, y, world.tiles[y][x]]
            for y in range(world.height) for x in range(world.width)
            if world.tiles[y][x] != original[y][x] and (x, y) not in skip]


def crates_to_list(state: GameState, layer) -> list:
    """Só as caixas que mudaram (abertas ou saqueadas): [x, y, slots, aberta]."""
    out = []
    for (x, y), crate in [*layer.crates.items(), *layer.containers.items()]:   # destroços e contêineres (v0.5 M4)
        fresh = Inventory(C.CRATE_SLOTS)
        for item, n in loot_for(crate.wreck, state.seed):
            fresh.add(item, n)
        if crate.opened or crate.storage.to_data() != fresh.to_data():
            out.append([x, y, crate.storage.to_data(), crate.opened])
    return out


def block_to_dict(b: BaseBlock) -> dict:
    data = {"kind": b.kind, "tx": b.tx, "ty": b.ty}
    if b.is_double:
        data["orient"] = b.orient
    return data


def base_from_list(data: list) -> BaseGrid:
    """Grade da base do save. Bloco de tipo desconhecido ou em cima de outro é ignorado (nunca quebra o load)."""
    grid = BaseGrid()
    for d in data:
        kind = d.get("kind")
        if kind not in C.BASE_KINDS:
            continue
        orient = ORIENT_V if d.get("orient") == ORIENT_V else ORIENT_H
        block = BaseBlock(kind, int(d["tx"]), int(d["ty"]), orient if kind == C.BASE_DOOR2 else ORIENT_H)
        if all(t not in grid.cells for t in block.tiles):
            grid.add(block)
    return grid


def layers_to_dict(state: GameState) -> dict:
    out = {}
    for key, layer in state.layers.items():
        data = {"changed_tiles": tiles_to_list(state, key),
                "machines": [machine_to_dict(m) for m in layer.machines],
                "explored": layer.explored.to_data()}
        if layer.rocks is not None:
            data["rocks"] = layer.rocks.to_data()
        if layer.crates or layer.containers:
            data["crates"] = crates_to_list(state, layer)
        if layer.has_base:                                       # v0.4 M2: a tampa de gelo da cratera (0..4)
            data["crater_ice"] = layer.crater_ice
        if layer.base.blocks:                                    # v9: blocos da base (a dupla é 1 objeto)
            data["base"] = [block_to_dict(b) for b in layer.base.blocks]
        out[key] = data
    return out


def layers_from_dict(state: GameState, data: dict) -> None:
    for key, ldata in data.items():
        if key not in layers.MAKERS:
            raise ValueError(f"camada desconhecida: {key!r}")
        if key not in state.layers:
            state.layers[key] = layers.MAKERS[key](state.seed)
        layer = state.layers[key]
        for x, y, kind in ldata["changed_tiles"]:
            layer.world.set(int(x), int(y), int(kind))
        layer.machines = [machine_from_dict(d) for d in ldata["machines"]]
        layer.base = base_from_list(ldata.get("base", []))       # v9 (o v8 migrado não tem: sem base)
        for m in layer.machines:            # save v7 de antes da magmatita: a rocha nova da seed não fica embaixo
            for t in m.tiles:               # de uma máquina que já estava lá (vira areia; o próximo save guarda)
                if layer.world.get(*t) == C.SMALL_MAGMATITE:
                    layer.world.set(*t, C.SAND)
        if layer.rocks is not None and "rocks" in ldata:     # save v6 antigo: "rocks" falta e "pickups"
            layer.rocks = RockRespawn.from_data(ldata["rocks"])  # (os soltos, que saíram do jogo) é ignorado
        for x, y, slots, opened in ldata.get("crates", []):      # Marco 3 (save do Marco 1/2 não tem)
            crate = layer.crates.get((int(x), int(y))) or layer.containers.get((int(x), int(y)))
            if crate is not None:
                crate.storage = slots_from_data(slots, C.CRATE_SLOTS)
                crate.opened = bool(opened)
        world = layer.world
        layer.explored = Explored.from_data(world.width, world.height, ldata.get("explored"))
        layer.crater_ice = max(0, min(C.CRATER_ICE_STAGES, int(ldata.get("crater_ice", 0))))


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
    return item in C.RESOURCES or item in C.MACHINES or item in C.DIAGRAM_ITEMS


def slots_from_data(data: list, size: int) -> Inventory:
    """Lista de slots do save -> Inventory do tamanho certo. Item que o jogo não conhece mais
    (removido do config) vira slot vazio, em vez de quebrar o load."""
    clean = []
    for d in data[:size]:
        item = C.LEGACY_DIAGRAM_ITEMS.get(d[0], d[0]) if d else None     # projeto antigo (bp_*) vira diagrama
        clean.append([item, int(d[1])] if item is not None and _known_item(item) and int(d[1]) > 0 else None)
    return Inventory.from_data(clean + [None] * (size - len(clean)))


def inventory_to_dict(state: GameState) -> dict:
    """Os slots do player: 16 (a hotbar são os 8 primeiros) ou 24 com a mochila equipada."""
    return {"slots": state.inventory.to_data()}


def inventory_from_dict(state: GameState, data: dict) -> None:
    # 16 slots, ou 24 se o save tem a linha da mochila (quem decide de vez é o sync_backpack, depois do equipamento)
    size = C.INVENTORY_SLOTS + C.BACKPACK_SLOTS if len(data["slots"]) > C.INVENTORY_SLOTS else C.INVENTORY_SLOTS
    state.inventory = slots_from_data(data["slots"], size)


def melter_storage(data: list) -> Inventory:
    """Inventário do derretedor do save: slot 0 só gelo, slot 1 só cápsula (outra coisa vira vazio)."""
    inv = Inventory(C.MELTER_SLOTS)
    for slot, item in ((C.MELTER_ICE_SLOT, "ice"), (C.MELTER_CAPSULE_SLOT, "water_capsule")):
        d = data[slot] if slot < len(data) else None
        if d and d[0] == item and int(d[1]) > 0:
            inv.slots[slot] = Stack(item, min(int(d[1]), max_stack(item)))
    return inv


def dispenser_storage(data: list) -> Inventory:
    """Inventário do Dispersor do save: 1 slot, só cápsula de água (outra coisa vira vazio)."""
    inv = Inventory(C.DISPENSER_SLOTS)
    d = data[C.DISPENSER_CAPSULE_SLOT] if len(data) > C.DISPENSER_CAPSULE_SLOT else None
    if d and d[0] == "water_capsule" and int(d[1]) > 0:
        inv.slots[C.DISPENSER_CAPSULE_SLOT] = Stack("water_capsule", min(int(d[1]), max_stack("water_capsule")))
    return inv


def machine_to_dict(m: Machine) -> dict:
    data = {"kind": m.kind, "tx": m.tx, "ty": m.ty, "rotation": m.rotation}
    if m.is_drill:
        data.update(resource=m.resource, timer=m.timer)
    if m.is_melter:
        data["timer"] = m.timer          # v0.5 M2: progresso da cápsula (o inventário vai com o resto do logístico)
    if m.is_dispenser:                   # v9
        data.update(storage=m.storage.to_data(), burn=m.burn, sealed_once=m.sealed_once)
    if m.is_chest:
        data["name"] = m.name or C.CHEST_DEFAULT_NAME
    if m.is_logistic:
        data["storage"] = m.storage.to_data()
        data["sends"] = [i for i in C.LOGISTIC_ITEMS if i in m.sends]
        data["receives"] = [i for i in C.LOGISTIC_ITEMS if i in m.receives]
        data["batch"] = m.batch
    if m.is_station:
        data["buffer"] = dict(m.station.buffer)
        slots = [m.station.drone_in(i) for i in range(C.STATION_DRONE_SLOTS)]
        data["drones"] = [None if d is None else [d.resource if d.cargo else None, d.cargo] for d in slots]
    return data


def machine_from_dict(data: dict) -> Machine:
    kind = data["kind"]
    if kind not in C.MACHINES:
        raise ValueError(f"máquina desconhecida: {kind!r}")
    machine = Machine(kind, int(data["tx"]), int(data["ty"]), int(data["rotation"]) % 4,
                      resource=data.get("resource"), timer=float(data.get("timer", 0.0)))
    if not machine.type.placeable:
        raise ValueError(f"{kind!r} não é máquina de chão")
    if machine.is_chest:
        machine.storage = slots_from_data(data.get("storage", []), C.CHEST_SIZES[machine.kind])
        machine.name = clean_chest_name(data.get("name", C.CHEST_DEFAULT_NAME))
    if machine.is_drill:
        if machine.resource not in C.RESOURCES:
            raise ValueError(f"drill sem minério: {machine.resource!r}")
        # a drill só guarda o minério dela, até a capacidade
        amount = sum(int(d[1]) for d in data.get("storage", []) if d and d[0] == machine.resource)
        machine.stored = min(amount, C.DRILL_CAPACITY)
    if machine.is_melter:
        # v0.5 M2: [0] gelo, [1] cápsulas. Save de antes do Marco 2 não tem "storage": carrega vazio (sem migração)
        machine.storage = melter_storage(data.get("storage", []))
        machine.timer = min(max(machine.timer, 0.0), C.MELTER_CAPSULE_TIME[kind])
    if machine.is_dispenser:
        machine.storage = dispenser_storage(data.get("storage", []))
        machine.burn = min(max(float(data.get("burn", 0.0)), 0.0), C.DISPENSER_CAPSULE_TIME)
        machine.sealed_once = bool(data.get("sealed_once", False))
    if machine.is_logistic:
        # o que não pode (item desconhecido, a drill recebendo, o mesmo item dos dois lados) é ignorado
        machine.sends = {i for i in data.get("sends", []) if drones.can_send(machine, i)}
        machine.receives = {i for i in data.get("receives", [])
                            if drones.can_receive(machine, i) and i not in machine.sends}
        batch = data.get("batch", C.DRONE_BATCH_DEFAULT)
        machine.batch = batch if batch in C.DRONE_BATCH_OPTIONS else C.DRONE_BATCH_DEFAULT
    if machine.is_station:
        # drones recriados pousados no slot deles; quem estava carregando volta com a carga e entrega no 1º frame
        machine.station = drones.new_station(machine)
        machine.station.buffer = {r: int(n) for r, n in data.get("buffer", {}).items()
                                  if r in C.RESOURCES and int(n) > 0}
        for slot, cargo in enumerate(data.get("drones", [])[:C.STATION_DRONE_SLOTS]):
            if cargo is None:
                continue
            drone = drones.dock(machine, machine.station, slot)
            if cargo[0] in C.RESOURCES and int(cargo[1]) > 0:
                drone.resource, drone.cargo = cargo[0], int(cargo[1])
    return machine


def progress_to_dict(state: GameState) -> dict:
    """Terraformação, objetivos e tudo que "só cresce"."""
    return {
        "indices": dict(state.indices),
        "stage": state.stage,
        "stage_scheme": STAGE_SCHEME,                   # numeração dos estágios (2 = v0.4)
        "storm": state.storm,                           # tempestade no meio da passagem pro Árido continua de onde parou
        "smoothed_rate": state.smoothed_rate,           # pra estimativa do HUD não zerar ao carregar
        "play_time": state.play_time,
        "mined_total": dict(state.mined_total),
        "fabricator_opened": state.fabricator_opened,
        "drills_placed": state.drills_placed,
        "drill_collected": dict(state.drill_collected),
        "crafted": dict(state.crafted),
        "drone_deliveries": state.drone_deliveries,
        "drones_docked": state.drones_docked,
        "lamps_placed": state.lamps_placed,
        "logs_read": sorted(state.logs_read),
        "logs_seen": sorted(state.logs_seen),           # aba LOGs: já abertos por lá (sem "NOVO")
        # Marco 3
        "blueprints": sorted(state.blueprints),
        "equipment": state.equipment.to_data(),
        "equipped_ever": sorted(state.equipped_ever),
        "wrecks_visited": sorted(state.wrecks_visited),
        "transition_sources": sorted([list(t) for t in state.transition_sources]),
    }


def progress_from_dict(state: GameState, data: dict) -> None:
    for key in state.indices:
        state.indices[key] = float(data["indices"][key])
    state.stage = int(data["stage"])
    state.storm = max(0.0, min(1.0, float(data.get("storm", 0.0))))
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
    state.drones_docked = int(data["drones_docked"])
    state.lamps_placed = int(data.get("lamps_placed", 0))     # Marco 2: save v6 do Marco 1 não tem
    state.logs_read = {int(i) for i in data["logs_read"] if 0 <= int(i) < len(C.LOGS)}
    # aba LOGs: save v6 de antes dela não tem o campo, e aí todo LOG lido conta como visto (sem "NOVO")
    seen = data.get("logs_seen")
    state.logs_seen = set(state.logs_read) if seen is None else {int(i) for i in seen if int(i) in state.logs_read}
    state.transition_sources = {(int(x), int(y)) for x, y in data["transition_sources"]}
    # Marco 3 (save do Marco 1/2 não tem: começa sem diagrama lido, sem equipamento, nenhum destroço visitado)
    state.blueprints = {b for b in data.get("blueprints", []) if b in C.BLUEPRINTS}
    state.equipment = Equipment.from_data(data.get("equipment"))
    state.equipped_ever = {e for e in data.get("equipped_ever", []) if e in C.EQUIP_SLOTS}
    state.sync_backpack()          # v0.5 B3: 24 slots com a mochila, 16 sem (save v8 sem mochila continua com 16)
    state.wrecks_visited = {int(r) for r in data.get("wrecks_visited", [])}


# A ORDEM importa no load: o mundo vem antes de quem depende dele.
# Sistema novo? Uma linha aqui (veja o passo a passo no topo do arquivo).
SECTIONS = [
    ("layers", layers_to_dict, layers_from_dict),
    ("player", player_to_dict, player_from_dict),
    ("inventory", inventory_to_dict, inventory_from_dict),
    ("progress", progress_to_dict, progress_from_dict),
]


def world_to_dict(state: GameState) -> dict:
    """Nome e seed do mundo (a lista de mundos lê isso sem carregar o resto)."""
    return {"name": state.world_name, "seed": state.seed, "created": state.world_created,
            "played_s": round(state.play_time, 1)}


def world_from_dict(state: GameState, data) -> None:
    if not isinstance(data, dict):                 # save de antes dos mundos
        return
    name = " ".join(str(data.get("name", "")).split())
    if name:
        state.world_name = name[:C.WORLD_NAME_MAX]
    state.world_created = str(data.get("created", state.world_created))


def state_to_dict(state: GameState) -> dict:
    trip = state.ramp
    if trip is not None and not trip.switched and trip.to not in state.layers:
        state.layers[trip.to] = layers.MAKERS[trip.to](state.seed)   # 1ª descida: o destino entra no save
    data = {"version": SAVE_VERSION, "seed": state.seed, "layer": state.layer}
    for name, to_dict, _ in SECTIONS:
        data[name] = to_dict(state)
    data["world"] = world_to_dict(state)
    if trip is not None and not trip.switched:
        # salvou no meio do fade, antes da troca: grava o destino (camada + chegada da rampa), como se a
        # viagem já tivesse acabado. Depois da troca o estado já está no destino e sai igual.
        data["layer"] = trip.to
        data["player"]["x"], data["player"]["y"] = layers.ramp_arrival(state.layers[trip.to].world)
    return data


def state_from_dict(data: dict) -> GameState:
    """Gera o mundo da seed e aplica cada seção por cima. Dado estranho levanta erro (quem chama trata)."""
    state = new_state(int(data["seed"]))
    for name, _, from_dict in SECTIONS:
        from_dict(state, data[name])
    world_from_dict(state, data.get("world"))
    layer = data.get("layer", layers.SURFACE)
    if layer not in state.layers:
        raise ValueError(f"camada ativa sem dados: {layer!r}")
    state.layer = layer
    state.ensure_hand_drill()     # v0.5 M4: save v10 do M3 não tem a broca de mão (mesma versão, checagem no load)
    state._apply_thaw()           # v0.4 M3: o que o calor muda no mapa sai dos índices (não vai no save)
    state.events.clear()          # ...e o load não solta aviso nem som
    return state


# ---------------------------------------------------------------------------
# Versões e migração
# ---------------------------------------------------------------------------
# Quando o formato mudar: suba SAVE_VERSION e registre aqui a função que converte
# um save da versão N pra N+1 (ela recebe o dict e devolve o dict atualizado).
# As migrações v1 -> v5 (v0.1/v0.2) saíram no v0.3: o mundo mudou inteiro (deserto + camadas) e o dono
# decidiu que o v0.3 começa do zero. Ver o histórico do git (game/save.py até o commit ec889a6).
MIGRATIONS: dict = {}   # vazio: o v10 recomeçou do zero (v7–v9 viraram "save antigo")


class SaveError(Exception):
    """Save que não dá pra usar (estragado, de versão desconhecida...)."""


class OldSaveError(SaveError):
    """Save de uma versão antiga do jogo (v1–v9, antes do mapa 256 do v0.5 M3.1): não migra, pede novo jogo."""

    def __init__(self, version: int):
        super().__init__(f"save da versão {version} (esta versão do jogo exige novo jogo)")
        self.version = version


def migrate(data: dict) -> dict:
    """Leva um save de qualquer versão conhecida até a SAVE_VERSION atual."""
    version = data.get("version")
    if isinstance(version, int) and not isinstance(version, bool) and 1 <= version < FIRST_VERSION:
        raise OldSaveError(version)
    if not isinstance(version, int) or isinstance(version, bool) or not FIRST_VERSION <= version <= SAVE_VERSION:
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


def probe(path: Path | str | None = None) -> tuple[str, GameState | None]:
    """Olha o save: ("none", None) sem arquivo, ("old", None) de versão antiga (v1–v9), ("broken", None)
    estragado ou de versão desconhecida, ("ok", estado) carregado. Nunca apaga nada."""
    path = _path(path)
    if not path.exists():
        return "none", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise SaveError("o arquivo não é um objeto JSON")
        return "ok", state_from_dict(migrate(data))
    except OldSaveError as err:
        print(f"[save] {path.name}: {err}")
        return "old", None
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, SaveError) as err:
        # ValueError cobre JSON quebrado; KeyError/TypeError cobrem campo faltando ou do tipo errado
        print(f"[save] ignorando {path.name}: {err}")
        return "broken", None


def load_game(path: Path | str | None = None) -> GameState | None:
    """Carrega o save. Sem arquivo, estragado, antigo ou de versão desconhecida: avisa e devolve None."""
    return probe(path)[1]


def has_save(path: Path | str | None = None) -> bool:
    """Existe um save que dá pra carregar?"""
    return load_game(path) is not None


def backup_old(path: Path | str | None = None) -> Path | None:
    """Save antigo (v1–v9) vira slot1.v<N>.json, pra um jogo novo poder salvar sem apagar ele.
    Devolve o caminho novo (None se não tinha save antigo)."""
    path = _path(path)
    try:
        version = json.loads(path.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    if not (isinstance(version, int) and 1 <= version < FIRST_VERSION):
        return None
    target = path.with_name(f"{path.stem}.v{version}{path.suffix}")
    n = 2
    while target.exists():                       # nunca sobrescreve um backup que já existia
        target = path.with_name(f"{path.stem}.v{version}-{n}{path.suffix}")
        n += 1
    os.replace(path, target)
    return target
