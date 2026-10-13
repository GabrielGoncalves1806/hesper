"""Mundos: até 3 jogos salvos, cada um com nome e seed. Python puro (nada de pygame), testado em
tests/test_worlds.py.

Arquivos (tudo em `saves/`, que está no .gitignore):

    saves/world1.json   world2.json   world3.json    # um save por espaço (formato do game/save.py)
    saves/worlds.json                                # índice: {"last": 2, "migrated_slot1": true}

Cada save ganha o bloco `world` (ver game/save.py): {"name": "Mundo 1", "seed": 7, "created": "2026-10-13T14:02",
"played_s": 734.2}. A seed do mundo continua também no `seed` da raiz do save (é ela que gera o mapa); o
`world.seed` é a mesma, repetida pra lista de mundos.

Migração do save único: na primeira vez, um `saves/slot1.json` **v7** (o formato atual) é COPIADO pra
`world1.json`, com o nome "Mundo 1" e a seed que ele já usava (7). O `slot1.json` fica onde está, intacto (é o
backup), e o índice marca `migrated_slot1` pra ele não voltar a virar mundo se o mundo 1 for apagado.
Um `slot1.json` v1–v6 não migra: o título mostra o aviso de "save antigo" e, ao criar um mundo, ele vira
`slot1.v<N>.json` (`save.backup_old`, que nunca sobrescreve outro backup). Nenhum outro arquivo da pasta
(`slot1.antigo.json`, `slot1.v5.json`, `slot1.v6.json`...) é lido, mexido ou apagado.

A lista de mundos lê só o JSON (nome, seed, estágio, tempo de jogo) e a data do arquivo: não gera mapa,
então abrir a tela de Mundos é instantâneo. Quem carrega o jogo de verdade é o `save.probe`.

Seed digitada no "Novo mundo" (`parse_seed`):
    - vazio          -> sorteada (1 a 999.999.999) e mostrada na tela antes de criar;
    - só dígitos     -> esse número (acima de 2^31 dá a volta: `n % 2^31`);
    - qualquer texto -> hash ESTÁVEL do texto (sha256, 4 primeiros bytes, 31 bits). O `hash()` do Python
                        muda a cada execução e não serve.
"""

import hashlib
import json
import os
import random
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from game import config as C
from game import save

SLOTS = 3                     # quantos mundos cabem
NAME_MAX = C.WORLD_NAME_MAX      # caracteres do nome
SEED_MAX = 20                 # caracteres do campo de seed
SEED_MOD = 2 ** 31            # seeds ficam em 0..2^31-1 (cabem em qualquer gerador, numpy incluso)
RANDOM_SEED_MAX = 999_999_999

SAVES_DIR = C.ROOT_DIR / "saves"   # o smoke e os testes apontam pra outro lugar
LEGACY_NAME = "slot1.json"
INDEX_NAME = "worlds.json"


def saves_dir() -> Path:
    # resolvido na hora (não no import): o smoke troca SAVES_DIR
    return Path(SAVES_DIR)


def path(slot: int) -> Path:
    """Arquivo do mundo `slot` (1 a 3)."""
    if not 1 <= slot <= SLOTS:
        raise ValueError(f"espaço de mundo inválido: {slot}")
    return saves_dir() / f"world{slot}.json"


def default_name(slot: int) -> str:
    return f"Mundo {slot}"


def clean_name(name: str, slot: int) -> str:
    """Nome sem espaço sobrando e até NAME_MAX letras; vazio volta pro padrão ("Mundo N")."""
    name = " ".join(str(name or "").split())[:NAME_MAX].strip()
    return name or default_name(slot)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
def text_seed(text: str) -> int:
    """Seed de um texto: sempre a mesma pro mesmo texto, em qualquer máquina e execução."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % SEED_MOD


def random_seed(rng: random.Random | None = None) -> int:
    return (rng or random.SystemRandom()).randint(1, RANDOM_SEED_MAX)


def parse_seed(text: str) -> int | None:
    """Texto do campo -> seed. None = campo vazio (quem chama sorteia)."""
    text = (text or "").strip()
    if not text:
        return None
    if text.isascii() and text.isdigit():
        return int(text) % SEED_MOD
    return text_seed(text)


# ---------------------------------------------------------------------------
# Índice (último mundo jogado, migração feita)
# ---------------------------------------------------------------------------
def read_index() -> dict:
    try:
        data = json.loads((saves_dir() / INDEX_NAME).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(target: Path, data: dict) -> bool:
    """Escrita atômica (temporário na mesma pasta + os.replace), igual ao save."""
    tmp_name = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
        return True
    except OSError as err:
        print(f"[mundos] não consegui gravar {target}: {err}")
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        return False


def write_index(**changes) -> None:
    data = read_index()
    data.update(changes)
    _write_json(saves_dir() / INDEX_NAME, data)


def last_slot() -> int | None:
    """O último mundo jogado (só se o arquivo dele ainda existe)."""
    slot = read_index().get("last")
    if isinstance(slot, int) and not isinstance(slot, bool) and 1 <= slot <= SLOTS and path(slot).exists():
        return slot
    return None


def mark_played(slot: int) -> None:
    write_index(last=slot)


# ---------------------------------------------------------------------------
# Migração do slot1.json
# ---------------------------------------------------------------------------
def now_iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if ts is None else ts).isoformat(timespec="minutes")


def legacy_path() -> Path:
    return saves_dir() / LEGACY_NAME


def legacy_status() -> str:
    """Estado do saves/slot1.json: "none", "ok" (versão atual), "old" (v1–v6) ou "broken". Só lê o JSON."""
    legacy = legacy_path()
    if not legacy.exists():
        return "none"
    try:
        version = json.loads(legacy.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, AttributeError):
        return "broken"
    if _int(version) and 1 <= version < save.FIRST_VERSION:
        return "old"
    if _int(version) and save.FIRST_VERSION <= version <= save.SAVE_VERSION:
        return "ok"
    return "broken"


def migrate_legacy() -> bool:
    """saves/slot1.json da versão atual (v7) -> saves/world1.json, uma vez só. O slot1.json não é tocado
    (fica de backup). Save antigo (v1–v6) NÃO migra: segue o fluxo de "save antigo" (o título avisa e, quando
    um mundo novo é criado, ele vira slot1.v<N>.json pelo save.backup_old). Devolve True se migrou."""
    index = read_index()
    if index.get("migrated_slot1"):
        return False
    status = legacy_status()
    if status in ("none", "old", "broken"):
        return False
    if any(path(s).exists() for s in range(1, SLOTS + 1)):     # já tem mundo: não mexe, só marca
        write_index(migrated_slot1=True)
        return False
    legacy = legacy_path()
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        stamp = legacy.stat().st_mtime
    except (OSError, ValueError) as err:
        print(f"[mundos] não consegui ler {legacy.name}: {err}")
        return False
    progress = data.get("progress") if isinstance(data.get("progress"), dict) else {}
    data["world"] = {"name": default_name(1), "seed": data.get("seed", C.WORLD_SEED),
                     "created": now_iso(stamp), "played_s": progress.get("play_time", 0.0)}
    target = path(1)
    if not _write_json(target, data):
        return False
    os.utime(target, (stamp, stamp))        # a data do mundo é a do último save, não a da migração
    write_index(migrated_slot1=True, last=1)
    return True


def retire_old_legacy() -> Path | None:
    """Criou um mundo com um slot1.json antigo (v1–v6) na pasta: ele vira slot1.v<N>.json (nunca apagado,
    nunca por cima de outro backup), igual ao "Novo jogo" de antes dos mundos."""
    if legacy_status() != "old":
        return None
    return save.backup_old(legacy_path())


# ---------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------
@dataclass
class WorldInfo:
    slot: int
    status: str = "empty"         # "empty", "ok", "old" (versão que este jogo não carrega) ou "broken"
    name: str = ""
    seed: int | None = None
    stage: int = 1
    play_time: float = 0.0
    saved: float = 0.0            # data do arquivo (último save), timestamp
    created: str = ""

    @property
    def empty(self) -> bool:
        return self.status == "empty"

    @property
    def playable(self) -> bool:
        return self.status == "ok"

    @property
    def stage_name(self) -> str:
        stage = max(1, min(len(C.STAGES), self.stage))
        return C.STAGES[stage - 1].name

    @property
    def date_label(self) -> str:
        return datetime.fromtimestamp(self.saved).strftime("%d/%m/%y") if self.saved else ""


def _int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def info(slot: int) -> WorldInfo:
    """O resumo de um espaço, lido só do JSON (sem gerar o mundo)."""
    file = path(slot)
    out = WorldInfo(slot)
    if not file.exists():
        return out
    out.name = default_name(slot)
    try:
        out.saved = file.stat().st_mtime
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("não é um objeto")
        world = data.get("world") if isinstance(data.get("world"), dict) else {}
        out.name = clean_name(world.get("name", ""), slot)
        seed = data.get("seed", world.get("seed"))
        out.seed = seed if _int(seed) else None
        out.created = str(world.get("created", ""))
        version = data.get("version")
        if _int(version) and 1 <= version < save.FIRST_VERSION:
            out.status = "old"
            return out
        if not (_int(version) and save.FIRST_VERSION <= version <= save.SAVE_VERSION) or out.seed is None:
            out.status = "broken"
            return out
        progress = data["progress"]
        stage = int(progress["stage"])
        out.stage = max(1, min(len(C.STAGES), stage))
        out.play_time = float(progress.get("play_time", world.get("played_s", 0.0)))
        out.status = "ok"
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
        print(f"[mundos] {file.name}: {err}")
        out.status = "broken"
    return out


def continue_slot(infos: list[WorldInfo]) -> int | None:
    """O mundo do "Continuar": o último jogado; se ele sumiu, o de save mais recente."""
    last = last_slot()
    if last is not None:
        return last
    filled = [w for w in infos if not w.empty]
    return max(filled, key=lambda w: w.saved).slot if filled else None


def list_worlds() -> list[WorldInfo]:
    """Os 3 espaços, na ordem (migra o slot1.json antes, na primeira vez)."""
    migrate_legacy()
    return [info(slot) for slot in range(1, SLOTS + 1)]


def load(slot: int):
    """("ok", GameState) / ("old" | "broken" | "none", None), igual ao save.probe."""
    return save.probe(path(slot))


# ---------------------------------------------------------------------------
# Criar e apagar
# ---------------------------------------------------------------------------
def _backup(file: Path, tag: str) -> Path:
    """Guarda `file` como worldN.<tag>.json (sem sobrescrever outro backup)."""
    target = file.with_name(f"{file.stem}.{tag}{file.suffix}")
    n = 2
    while target.exists():
        target = file.with_name(f"{file.stem}.{tag}-{n}{file.suffix}")
        n += 1
    os.replace(file, target)
    return target


def free_slot(slot: int) -> Path | None:
    """Libera o espaço: save bom é apagado; save de versão antiga ou estragado vira backup
    (worldN.vX.json / worldN.estragado.json), porque o jogo não sabe ler mas o dono pode querer.
    Devolve o caminho do backup, se teve."""
    file = path(slot)
    current = info(slot)
    backup = None
    if current.status == "ok":
        file.unlink(missing_ok=True)
    elif current.status == "old":
        try:
            version = json.loads(file.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError, AttributeError):
            version = "antigo"
        backup = _backup(file, f"v{version}")
    elif current.status == "broken":
        backup = _backup(file, "estragado")
    if read_index().get("last") == slot:
        write_index(last=None)
    return backup


def delete(slot: int) -> Path | None:
    """Apaga o mundo (a tela pede confirmação antes)."""
    return free_slot(slot)


def create(slot: int, name: str, seed: int | None = None, rng: random.Random | None = None):
    """Mundo novo no espaço `slot`: libera o espaço, gera o estado da seed, grava e marca como o último.
    Devolve o GameState (com `world_name`, `world_created` e a seed sorteada se veio None)."""
    if seed is None:
        seed = random_seed(rng)
    free_slot(slot)
    retire_old_legacy()
    state = save.new_state(int(seed))
    state.world_name = clean_name(name, slot)
    state.world_created = now_iso()
    save.write_save(state, path(slot))
    mark_played(slot)
    return state
