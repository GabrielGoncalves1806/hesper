# v0.7 Lore · Marco 4 · Interior da VÉSPER-7 · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** a VÉSPER-7 vira única no mundo e ganha um interior: uma camada nova `vesper` (48×48), com entrada pelo porão (E na boca, fade "Entrando..."/"Saindo..."), salas desenhadas à mão e escolhidas pela seed (porão, corredor, alojamento, câmara fria, cabine), 3 LOGs, 2 caixas de loot, o contêiner arrombado (cenário), o painel de energia sem bateria e a porta emperrada no norte (faísca + névoa, gancho do futuro).

**Arquitetura:**
- **`game/vesper.py`** (novo, Python puro): esqueleto fixo de 5 *slots* (caixas em tiles, com as passagens fixas). Cada slot tem 2 plantas em `game/vesper_plans/*.txt`, no formato das plantas de ruína (`ruins.load_plan`). A seed escolhe a variante de cada slot. O resultado é **um único `ruins.Ruin`** de 48×48 (key `"vesper"`), e por isso a casca (paredes `ruin`), o chão, os props de ruína, as máquinas quebradas e os terminais de parede saem do `ruins.apply_overlays`, que já existe e já vai no save do jeito certo. O que é só da nave fica em `world.fixtures` (tile → tipo): a saída, o contêiner arrombado, o painel, a porta emperrada e as luzes de emergência.
- **Camada**: `layers.VESPER = "vesper"` e `layers.make_vesper` em `MAKERS`. O mundo nasce com tudo `BEDROCK` e chão `FLOOR` na pegada da nave. `has_base` é False, então o render já trata a camada como a caverna: escuro, lanterna do capacete e luz da região padrão (`cave_region = None`).
- **Viagem**: o `RampTrip` ganha `arrival` (onde o player aparece) e `text` ("Entrando..."/"Saindo..."). A rampa da caverna continua igual (os dois ficam `None` e caem no comportamento de hoje). A entrada é o alvo de E novo `"hatch_in"` (boca do porão da VÉSPER na superfície), e a saída é `"hatch_out"` (a escotilha no chão do porão, lá dentro).
- **Casca com cara de nave**: o render escolhe o prefixo dos sprites da base pela camada (`hull_*` na `vesper`, `base_*` no resto). Sem o PNG, cai no `base_*` e depois no placeholder de hoje.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** bíblia §16, "Marco 4 · Interior da VÉSPER-7" (decisões do dono, 2026-10-16). Spec do v0.7: `docs/superpowers/specs/2026-10-16-v07-lore-design.md`, seção "M4". LOGs: `docs/lore/logs_v07_rascunho.md`, seção "v0.7 M4" (**só entra depois de aprovada pelo dono**).

## Restrições globais
- **Camada**: key `"vesper"`, mundo 48×48, nome no jogo **"VÉSPER-7"**. A planta **não gira** e não tem destruição (nível 0).
- **Esqueleto** (tiles; a origem da nave no mundo é `ORIGIN = (5, 6)`; caixa = `(x, y, w, h)` relativa à origem; passagem = tile local da planta que **tem de ser chão `.`**):

  | slot | sala | caixa | passagens (local) | obrigatório na planta |
  |---|---|---|---|---|
  | `bridge` | Cabine | (11, 0, 18, 10) | (9, 9) | `J` em (9, 0) na parede norte; `P` numa parede com chão embaixo; terminal `1` (LOG 21) |
  | `hall` | Corredor | (17, 9, 7, 16) | (3, 0), (0, 7), (6, 7), (3, 15) | — |
  | `bunks` | Alojamento | (4, 11, 14, 11) | (13, 5) | terminal `1` (LOG 22); ≥ 2 `prop_bunk` |
  | `cold` | Câmara fria | (23, 11, 14, 11) | (0, 5) | `K` (contêiner arrombado); terminal `1` (LOG 23) |
  | `hold` | Porão | (10, 24, 21, 12) | (10, 0) | `E` (escotilha de saída) no chão; exatamente 2 `c` |

  As caixas vizinhas dividem uma linha/coluna de parede. Quando duas plantas caem no mesmo tile, **o que não é `#` ganha** (é assim que a passagem de uma sala abre a parede da outra). A pegada total cabe em 37×36, e o mundo 48×48 sobra borda de `BEDROCK` em volta.
- **Legenda das plantas** (cabeçalho igual ao das ruínas: `name`, `layer: vesper`, `damage: rock`, letras):
  - `#` parede (casca), `.` chão, `c` caixa, `1` terminal (o índice do LOG vem na legenda, `1: 21`), espaço = fora;
  - letra com valor de prop (`b: prop_bunk`) = prop de ruína, escaneável (como no M2);
  - `l: lamp` = luminária **quebrada** (máquina `broken`, apagada, desmontável como nas ruínas);
  - **fixtures** (só da nave, `vesper.FIXTURES`): `E: hatch` (escotilha de saída, no chão, **andável**), `K: container_broken` (contêiner arrombado, no chão, **sólido**), `P: power_panel` (na parede, face pro sul), `J: jammed_door` (na parede norte, face pro sul), `L: emergency_light` (na parede, face pro sul, acende).
- **Textos** (exatos):
  - porta: `"Porta emperrada · energizar a nave pode resolver"`;
  - painel: `"Painel de energia · sem bateria"`;
  - contêiner: `"Vazio. A tampa foi forçada por dentro."`;
  - alvo do E na boca do porão: `"[E] Entrar na VÉSPER-7"`; na escotilha: `"[E] Sair da nave"`;
  - fade: `"Entrando..."` (pra `vesper`) e `"Saindo..."` (da `vesper` pra superfície);
  - construir lá dentro: `"Não dá pra construir aqui · Esc cancela"`;
  - aba do mapa: `"VÉSPER-7"`.
- **Loot** das 2 caixas do porão: recursos `C.WRECK_RICH_LOOT` + peças `C.LOOT_RICH` (rng por tile). Nome da caixa: `"Caixa · VÉSPER-7"`.
- **LOGs**: índices **21, 22, 23**, dias **188, 190, 193**. Títulos: `"CABINE · VÉSPER-7"`, `"ALOJAMENTO · VÉSPER-7"`, `"CAMARA FRIA · VÉSPER-7"`. O texto vem **igual** de `docs/lore/logs_v07_rascunho.md`, seção "v0.7 M4", depois que o dono aprovar.
- **Uma VÉSPER por mundo**: `kinds_for(n)` vira `["cargo", "probe", "module", "liner", "probe", "probe", "robot", *["robot", "module"][:n - 8], "module"]`. O rank 4 (agora `probe`) continua com o diagrama `lamp_t2` (o `extras_for` não muda). `WRECK_RICH_KIND = "module"`; se em alguma seed de 0 a 199 o `module` 8×4 não couber no `wreck_spot`, usa `"robot"` e avisa no report. O `SPECS["cargo"].name` vira `"VÉSPER-7"`.
- **Save**: continua **v13**. A camada `vesper` entra no `layers` do save como as outras. Nenhum campo novo. Save antigo: sem cuidado especial (decisão do dono).
- **Não mexer** em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` nem `settings.json`. A arte e o som entram na Task 5, depois da aprovação do dono.

## Decisões (o dono deveria ver)
1. **A nave é um `Ruin` só**, não 5. Assim o `apply_overlays`, os terminais, os props e o scan funcionam sem código novo, e o save já sabe lidar.
2. **A saída é uma escotilha no chão do porão**, não um buraco na parede sul. A face da parede só aparece pro sul (pra fora da nave), e o player lá dentro não ia ver a porta.
3. **Passagens entre salas são abertas** (sem porta). As portas da base iam ficar com cara de colônia dentro da nave. Se o dono quiser porta de nave, entra depois com sprite próprio.
4. **A luz**: `L` (luz de emergência) acende fraca e avermelhada (~2,5 tiles). As luminárias `l` são as quebradas de ruína (apagadas). O resto é o escuro da caverna.
5. **Dá pra desmontar** a caixa vazia e a luminária quebrada lá dentro, como nas ruínas. Construir não dá.

## Mapa de arquivos
| Arquivo | Task | O quê |
|---|---|---|
| `game/wrecks.py`, `game/config.py` (bloco `WRECK_*`), `tests/test_wrecks.py` | 1 | uma VÉSPER por mundo |
| `game/vesper.py` (novo), `game/vesper_plans/*.txt` (novo, 10 plantas), `game/layers.py`, `game/save.py` (`pristine_tiles`), `game/config.py` (bloco `VESPER_*` e LOGs 21–23), `tests/test_vesper.py` (novo) | 2 | geração da camada |
| `game/systems.py`, `game/save.py` (viagem salva no meio), `game/audio.py`, `game/app.py` (E, dica, som da viagem), `tests/test_vesper_trip.py` (novo) | 3 | entrar, sair, regras |
| `game/render.py`, `game/ui.py`, `game/map_view.py`, `game/app.py` (partículas), `tools/dev/smoke.py`, `tools/dev/shot_v07_m4.py` (novo) | 4 | desenho, mapa, partículas |
| `assets/` (cópia da arte e do som aprovados) | 5 | integração |

---

### Task 1: uma VÉSPER por mundo

**Files:**
- Modify: `game/wrecks.py` (`kinds_for`, `SPECS["cargo"]`)
- Modify: `game/config.py` (`WRECK_RICH_KIND`)
- Test: `tests/test_wrecks.py`

**Interfaces:**
- Produces: `wrecks.vesper_wreck(world) -> Wreck | None` (o único `cargo` não rico do mundo).

- [ ] **Step 1: testes que falham** (em `tests/test_wrecks.py`)

```python
@pytest.mark.parametrize("n", [8, 9, 10])
def test_one_cargo_per_world(n):
    kinds = wrecks.kinds_for(n)
    assert kinds.count("cargo") == 1 and kinds[0] == "cargo"
    assert kinds[4] == "probe"                     # o rank 4 leva o diagrama da luminária forte
    assert wrecks.extras_for(4, n) == (None, "lamp_t2")


def test_vesper_is_unique_and_named():
    from game.layers import make_surface
    for seed in range(0, 200, 7):
        world = make_surface(seed).world
        cargos = [w for w in world.wrecks if w.kind == "cargo"]
        assert len(cargos) == 1 and not cargos[0].rich
        assert wrecks.vesper_wreck(world) is cargos[0]
        assert cargos[0].name == "VÉSPER-7"


def test_rich_wreck_is_not_cargo():
    from game.layers import make_surface
    for seed in range(200):
        world = make_surface(seed).world
        rich = [w for w in world.wrecks if w.rich]
        assert all(w.kind == C.WRECK_RICH_KIND != "cargo" for w in rich)
```

- [ ] **Step 2:** `uv run pytest tests/test_wrecks.py -q` → FAIL (`vesper_wreck` não existe; 2 ou 3 `cargo`).
- [ ] **Step 3: implementação**

```python
def kinds_for(n: int) -> list[str]:
    """Tipo de cada destroço, do mais perto pro mais longe (n de 8 a 10). v0.7 M4: uma VÉSPER-7 (cargo) por mundo,
    no rank 0; o rank 4 virou sonda (leva o diagrama da luminária forte) e o extra do n=10 virou base."""
    extras = ["robot", "module"][:max(0, n - 8)]
    return ["cargo", "probe", "module", "liner", "probe", "probe", "robot", *extras, "module"]


def vesper_wreck(world) -> "Wreck | None":
    """A VÉSPER-7 do mundo (o único cargo de fora dos bolsões; v0.7 M4), ou None."""
    return next((w for w in getattr(world, "wrecks", []) if w.kind == "cargo" and not w.rich), None)
```

  Em `SPECS`, o nome do `cargo` passa de `"Nave de carga"` pra `"VÉSPER-7"`. Em `config.py`, `WRECK_RICH_KIND = "module"`.
- [ ] **Step 4:** `uv run pytest tests/test_wrecks.py -q`. Se o `test_rich_wreck_is_not_cargo` acusar destroço rico faltando (o `module` 8×4 não cabe no `wreck_spot`), troque pra `"robot"` e anote no report. Depois disso, rode `uv run pytest` inteiro: algum teste antigo que contava `cargo` ou usava o nome "Nave de carga" pode precisar de ajuste. Ajuste o teste (a regra mudou por decisão do dono) e liste no report.

---

### Task 2: a camada `vesper` (geração, sem jogabilidade)

**Files:**
- Create: `game/vesper.py`, `game/vesper_plans/{bridge,hall,bunks,cold,hold}_{a,b}.txt`, `tests/test_vesper.py`
- Modify: `game/layers.py` (`VESPER`, `make_vesper`, `MAKERS`), `game/world.py` (`fixtures` no `__init__`), `game/save.py` (`pristine_tiles` por camada), `game/config.py` (LOGs 21–23, `VESPER_*`)

**Interfaces:**
- Produces:
  - `vesper.VESPER = "vesper"`, `vesper.SIZE = (48, 48)`, `vesper.ORIGIN = (5, 6)`
  - `vesper.FIXTURES = ("hatch", "container_broken", "power_panel", "jammed_door", "emergency_light")`
  - `vesper.SLOTS: tuple[Slot, ...]`, com `Slot(key, box, passages)`
  - `vesper.compose(seed) -> ruins.Ruin` (a nave inteira, já na posição do mundo, key `"vesper"`) e `vesper.fixtures_of(seed) -> dict[tuple[int, int], str]`
  - `vesper.generate_world(seed) -> World` (tiles + `world.ruins = [ship]`, `ruin_tiles`, `ruin_terminals`, `fixtures`)
  - `vesper.make_crates(world, seed) -> dict[tile, Crate]`
  - `vesper.hatch_tile(world) -> tuple[int, int]` (o `E`), `vesper.arrival(world) -> tuple[float, float]` (pés, 1 tile ao norte da escotilha)
  - `layers.VESPER`, `layers.make_vesper(seed) -> Layer`
  - `World.fixtures: dict[tuple[int, int], str]` (vazio fora da `vesper`)

- [ ] **Step 1: as plantas.** Escreva 2 variantes por slot (`_a` e `_b`), com a caixa exata da tabela de Restrições (largura e altura da grade = `w` × `h`). A borda da grade é `#`, menos as passagens (que são `.`). As variantes mudam o miolo: onde ficam os props, as caixas, os terminais e as luzes. Exemplo do `bunks_a.txt` (14×11; passagem em (13, 5)):

```
name: Alojamento
layer: vesper
damage: rock
b: prop_bunk
k: prop_locker
t: prop_table
h: prop_chair_fallen
L: emergency_light
1: 22
---
######1###L###
#bb........kk#
#............#
#bb...t......#
#.....h......#
#.............
#bb..........#
#............#
#bb.......k..#
#............#
##############
```

  Regras que os testes cobram: o `J` do `bridge` em (9, 0), um `P` e um `1` no `bridge`, o `K` e um `1` no `cold`, um `E` e exatamente 2 `c` no `hold`, um `1` no `bunks`. Terminal, `P`, `J` e `L` ficam em `#` com chão (`.`) logo embaixo. Use os props do kit (`C.PROPS`): `prop_bunk`, `prop_locker`, `prop_table`, `prop_chair`, `prop_chair_fallen`, `prop_crate`, `prop_barrel`, `prop_console`, `prop_rubble`, `prop_ice_stain` (a câmara fria merece umas), `wall_monitor_off`, `wall_bp_ship`. A legenda dos LOGs: `bridge` `1: 21`, `bunks` `1: 22`, `cold` `1: 23`.

- [ ] **Step 2: testes que falham** (`tests/test_vesper.py`)

```python
"""Interior da VÉSPER-7 (v0.7 M4): geração da camada pela seed."""

import pytest

from game import config as C
from game import layers, ruins, vesper

SEEDS = range(0, 60, 3)


def test_plans_respect_slots():
    for slot in vesper.SLOTS:
        for key in vesper.VARIANTS[slot.key]:
            plan = vesper.load(key)
            _, _, w, h = slot.box
            assert len(plan.grid) == h and all(len(r) == w for r in plan.grid), key
            for x, y in slot.passages:
                assert plan.grid[y][x] == ".", (key, x, y)


@pytest.mark.parametrize("seed", SEEDS)
def test_same_seed_same_ship(seed):
    a, b = vesper.compose(seed), vesper.compose(seed)
    assert a.grid == b.grid and a.props == b.props and vesper.fixtures_of(seed) == vesper.fixtures_of(seed)


def test_seeds_vary():
    assert len({tuple(vesper.compose(s).grid) for s in range(40)}) > 1


@pytest.mark.parametrize("seed", SEEDS)
def test_required_pieces(seed):
    fx = vesper.fixtures_of(seed)
    kinds = sorted(fx.values())
    assert kinds.count("hatch") == 1 and kinds.count("container_broken") == 1
    assert kinds.count("power_panel") == 1 and kinds.count("jammed_door") == 1
    ox, oy = vesper.ORIGIN
    assert fx[(ox + 11 + 9, oy + 0)] == "jammed_door"           # porta emperrada no norte, sempre no mesmo lugar
    ship = vesper.compose(seed)
    assert sorted(ship.terminals.values()) == [21, 22, 23]


@pytest.mark.parametrize("seed", SEEDS)
def test_everything_reachable_from_hatch(seed):
    layer = layers.make_vesper(seed)
    world = layer.world
    start = vesper.hatch_tile(world)
    seen = vesper.walkable_from(world, layer, start)
    def touches(t):
        x, y = t
        return any(n in seen for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for tile in layer.crates:
        assert touches(tile)
    for tile in world.ruin_terminals:                            # o tile de baixo do terminal
        assert (tile[0], tile[1] + 1) in seen
    for tile, kind in world.fixtures.items():
        if kind in ("power_panel", "jammed_door"):
            assert (tile[0], tile[1] + 1) in seen
        elif kind == "container_broken":
            assert touches(tile)


@pytest.mark.parametrize("seed", SEEDS)
def test_layer_shape(seed):
    layer = layers.make_vesper(seed)
    world = layer.world
    assert (world.width, world.height) == vesper.SIZE
    assert len(layer.crates) == 2 and not layer.has_base and world.crater is None
    assert world.get(0, 0) == C.BEDROCK
    hx, hy = vesper.hatch_tile(world)
    assert world.is_floor(hx, hy) and world.is_floor(hx, hy - 1)
    kx, ky = next(t for t, k in world.fixtures.items() if k == "container_broken")
    assert world.is_solid(kx, ky)
    assert all(p.ruin for p in layer.props.values())


def test_makers_and_logs():
    assert layers.MAKERS[layers.VESPER] is layers.make_vesper
    assert len(C.LOGS) == len(C.LOG_TITLES) == len(C.LOG_DAYS) == 24
    assert C.LOG_DAYS[21:] == [188, 190, 193]
    assert C.LOG_TITLES[21:] == ["CABINE · VÉSPER-7", "ALOJAMENTO · VÉSPER-7", "CAMARA FRIA · VÉSPER-7"]


def test_pristine_tiles_of_vesper():
    from game import save
    world = layers.make_vesper(5).world
    assert save.pristine_tiles(5, layers.VESPER) == world.tiles
```

  (`walkable_from` e `cells_blocking` são os nomes que esses testes esperam. Se a `BaseGrid` já tiver algo que diga "este tile barra o passo", use e ajuste o teste, mas sem perder a checagem.)

- [ ] **Step 3:** `uv run pytest tests/test_vesper.py -q` → FAIL (`game.vesper` não existe).

- [ ] **Step 4: `game/vesper.py`**

```python
"""Interior da VÉSPER-7 (v0.7 M4 · bíblia §16): a camada `vesper`, 48×48, montada pela seed.

Esqueleto fixo de 5 salas (SLOTS); cada uma tem 2 plantas em game/vesper_plans/ (formato das ruínas: ruins.load_plan) e
a seed escolhe qual entra. A nave inteira vira UM ruins.Ruin, então casca, chão, props, máquinas quebradas e terminais
de parede saem do ruins.apply_overlays (nunca vão no save). O que é só da nave fica em world.fixtures: a escotilha de
saída, o contêiner arrombado, o painel de energia, a porta emperrada e as luzes de emergência. Python puro, testado em
tests/test_vesper.py.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from game import config as C
from game import ruins

VESPER = "vesper"
SIZE = (48, 48)
ORIGIN = (5, 6)
PLAN_DIR = Path(__file__).with_name("vesper_plans")
FIXTURES = ("hatch", "container_broken", "power_panel", "jammed_door", "emergency_light")
WALL_FIXTURES = frozenset({"power_panel", "jammed_door", "emergency_light"})   # na parede, face pro sul


@dataclass(frozen=True)
class Slot:
    key: str
    box: tuple[int, int, int, int]            # (x, y, w, h) relativo ao ORIGIN
    passages: tuple[tuple[int, int], ...]     # tiles locais que têm de ser chão (abrem a parede da sala vizinha)


SLOTS = (
    Slot("bridge", (11, 0, 18, 10), ((9, 9),)),
    Slot("hall", (17, 9, 7, 16), ((3, 0), (0, 7), (6, 7), (3, 15))),
    Slot("bunks", (4, 11, 14, 11), ((13, 5),)),
    Slot("cold", (23, 11, 14, 11), ((0, 5),)),
    Slot("hold", (10, 24, 21, 12), ((10, 0),)),
)
VARIANTS = {s.key: (f"{s.key}_a", f"{s.key}_b") for s in SLOTS}


@cache
def load(key: str) -> ruins.Plan:
    """A planta `key` (as letras de fixture saem do `machines` do ruins.Plan pro `fixtures`, ver _split)."""
    return ruins.load_plan(key, PLAN_DIR)


def _split(plan: ruins.Plan) -> tuple[dict[str, str], dict[str, str]]:
    """(máquinas quebradas, fixtures) da legenda: o load_plan põe toda letra que não é prop em `machines`."""
    machines = {k: v for k, v in plan.machines.items() if v not in FIXTURES}
    fixtures = {k: v for k, v in plan.machines.items() if v in FIXTURES}
    return machines, fixtures


def _pick(seed: int) -> list[tuple[Slot, ruins.Plan]]:
    rng = random.Random(seed * 7919 + 4243)
    return [(slot, load(rng.choice(VARIANTS[slot.key]))) for slot in SLOTS]


def _cells(seed: int) -> dict[tuple[int, int], tuple[str, ruins.Plan]]:
    """Tile do mundo -> (caractere, planta). Duas plantas no mesmo tile: o que não é `#` ganha."""
    ox, oy = ORIGIN
    out: dict[tuple[int, int], tuple[str, ruins.Plan]] = {}
    for slot, plan in _pick(seed):
        sx, sy, _, _ = slot.box
        for y, row in enumerate(plan.grid):
            for x, ch in enumerate(row):
                if ch == " ":
                    continue
                t = (ox + sx + x, oy + sy + y)
                if t not in out or out[t][0] == "#":
                    out[t] = (ch, plan)
    return out


@cache
def _built(seed: int) -> tuple[ruins.Ruin, tuple]:
    w, h = SIZE
    rows = [[" "] * w for _ in range(h)]
    machines, terminals, props, fixtures, crates = {}, {}, {}, {}, []
    for (x, y), (ch, plan) in _cells(seed).items():
        broken, fx = _split(plan)
        base = ch
        if ch in fx:
            kind = fx[ch]
            fixtures[(x, y)] = kind
            base = "#" if kind in WALL_FIXTURES else "."
        elif ch in plan.props:
            kind = plan.props[ch]
            props[(x, y)] = kind
            base = "#" if C.PROPS[kind].place == "face" else "."
        elif ch in broken:
            machines[(x, y)] = broken[ch]
            base = "."
        elif ch in plan.logs:
            terminals[(x, y)] = plan.logs[ch]
        elif ch == "c":
            crates.append((x, y))
        rows[y][x] = base
    grid = ["".join(r) for r in rows]
    crates.sort(key=lambda t: (t[1], t[0]))
    ship = ruins.Ruin(VESPER, "VÉSPER-7", VESPER, "rock", 0, 0, grid, machines, terminals, crates[0], 0, props)
    return ship, (tuple(sorted(fixtures.items())), tuple(crates))


def compose(seed: int) -> ruins.Ruin:
    return _built(seed)[0]


def fixtures_of(seed: int) -> dict[tuple[int, int], str]:
    return dict(_built(seed)[1][0])


def crate_tiles(seed: int) -> list[tuple[int, int]]:
    return list(_built(seed)[1][1])


def generate_world(seed: int):
    """O mapa da camada: BEDROCK em tudo, FLOOR na pegada da nave, LOOT_CRATE nas caixas, WRECK (sólido baixo) no
    contêiner arrombado. world.ruins = [a nave] (o apply_overlays põe casca, chão, props e máquinas quebradas)."""
    from game.world import World
    w, h = SIZE
    world = World(seed, w, h)
    world.tiles = [[C.BEDROCK] * w for _ in range(h)]
    world.floor_kind = C.FLOOR
    world.terraforms = False
    ship = compose(seed)
    for x, y in ship.tiles:
        world.set(x, y, C.FLOOR)
    for t in crate_tiles(seed):
        world.set(*t, C.LOOT_CRATE)
    world.fixtures = fixtures_of(seed)
    for t, kind in world.fixtures.items():
        if kind == "container_broken":
            world.set(*t, C.WRECK)
    world.ruins = [ship]
    world.ruin_tiles = frozenset(ship.tiles)
    world.ruin_terminals = dict(ship.terminals)
    hx, hy = hatch_tile(world)
    world.center = (hx, hy - 1)
    return world


def make_crates(world, seed: int) -> dict:
    """As 2 caixas do porão: recursos do destroço rico (C.WRECK_RICH_LOOT) + peças boas (C.LOOT_RICH)."""
    from game.inventory import Inventory
    from game.wrecks import Crate, _roll_parts
    out = {}
    for tx, ty in crate_tiles(world.seed):
        rng = random.Random(seed * 3209 + tx * 43 + ty * 17 + 11)
        storage = Inventory(C.CRATE_SLOTS)
        for item, (lo, hi) in C.WRECK_RICH_LOOT.items():
            storage.add(item, rng.randint(lo, hi))
        for item, n in _roll_parts(rng, C.LOOT_RICH):
            storage.add(item, n)
        out[(tx, ty)] = Crate(ruins.RuinSpot(tx, ty, VESPER, "Caixa · VÉSPER-7"), storage)
    return out


def hatch_tile(world) -> tuple[int, int]:
    return next(t for t, k in world.fixtures.items() if k == "hatch")


def arrival(world) -> tuple[float, float]:
    """Onde o player aparece ao entrar (pés): no tile logo ao norte da escotilha."""
    hx, hy = hatch_tile(world)
    return (hx + 0.5) * C.TILE, (hy - 1) * C.TILE + 24


def walkable_from(world, layer, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Tiles que o player alcança a pé a partir de `start` (chão do mundo, sem parede da casca, sem prop sólido)."""
    blocked = {t for t, p in layer.props.items() if p.solid} | set(layer.base.cells_blocking())
    blocked |= {t for m in layer.machines for t in m.tiles}
    seen, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n not in seen and world.in_bounds(*n) and not world.is_solid(*n) and n not in blocked:
                seen.add(n)
                queue.append(n)
    return seen
```

  Ajustes de apoio:
  - `ruins.load_plan(key, plan_dir=PLAN_DIR)`: ganha o parâmetro opcional `plan_dir` (o default é o de hoje).
  - `BaseGrid.cells_blocking()`: os tiles de parede e porta fechada (se já existir algo equivalente, use).
  - `World.__init__`: `self.fixtures: dict = {}` (com comentário "v0.7 M4: só na camada vesper (game/vesper.py)").
  - Em `game/layers.py`:

```python
from game import vesper
VESPER = vesper.VESPER
ORDER = (SURFACE, CAVE, VESPER)


def make_vesper(seed: int) -> Layer:
    world = vesper.generate_world(seed)
    layer = Layer(VESPER, world, crates=vesper.make_crates(world, seed))
    ruins.apply_overlays(layer)
    return layer


MAKERS = {SURFACE: make_surface, CAVE: make_cave, VESPER: make_vesper}
```

  - Em `game/save.py`, o `pristine_tiles` gera pela camada: `World.generate(seed)` pra `CAVE` e `vesper.generate_world(seed)` pra `VESPER`.
  - Em `game/config.py`: `LOGS += [...]` (21, 22, 23, com o texto igual ao do rascunho aprovado), `LOG_TITLES += [...]`, `LOG_DAYS += [188, 190, 193]`.

- [ ] **Step 5:** `uv run pytest tests/test_vesper.py -q` → PASS. Se o `apply_overlays` reclamar da nave (ex.: porta `D` que a nave não tem, `_connected`), lembre que a nave **não passa pelo `ruins.build`**: só pelo `apply_overlays`. Ajuste o que for preciso nele de forma que as ruínas de hoje não mudem (`uv run pytest tests/test_ruins.py`).
- [ ] **Step 6:** `uv run pytest` inteiro.

---

### Task 3: entrar, sair e as regras lá dentro

**Files:**
- Modify: `game/systems.py`, `game/save.py`, `game/audio.py`, `game/app.py`
- Test: `tests/test_vesper_trip.py` (novo)

**Interfaces:**
- Consumes: `wrecks.vesper_wreck`, `vesper.hatch_tile`, `vesper.arrival`, `layers.VESPER`, `World.fixtures`.
- Produces:
  - `RampTrip(to, arrival=None, text=None)` (os dois `None` = rampa da caverna, como hoje)
  - `GameState.hatch_in_target() -> tuple[int, int] | None` (o tile (3,2) da VÉSPER, na superfície), `hatch_in_distance()`, `start_hatch() -> bool` (entra ou sai, pela camada atual)
  - `GameState.surface_exit() -> tuple[float, float]` (pés no tile (3,3) da VÉSPER)
  - `GameState.fixture_text(kind) -> str` e o alvo de E `("fixture", tile)` pra `power_panel`, `jammed_door` e `container_broken`
  - alvos novos no `interactable_at`/`interaction`/`in_reach`: `"hatch_in"` (superfície) e `"hatch_out"` (vesper)
  - `Layer.buildable` (False na `vesper`)

- [ ] **Step 1: testes que falham** (`tests/test_vesper_trip.py`)

```python
"""v0.7 M4: entrar e sair da VÉSPER-7, e as regras lá dentro."""

from game import config as C
from game import layers, save, vesper, wrecks
from game.systems import GameState

DT = 1 / 60


def run(state, seconds):
    for _ in range(int(seconds / DT) + 1):
        state.update(DT)


def at_hatch_in(state):
    w = wrecks.vesper_wreck(state.surface.world)
    state.player.x, state.player.y = (w.tx + 3.5) * C.TILE, (w.ty + 3) * C.TILE + 20
    return w


def test_enter_and_exit():
    state = GameState(3)
    w = at_hatch_in(state)
    assert state.interaction() == ("hatch_in", (w.tx + 3, w.ty + 2))
    assert state.start_hatch()
    run(state, C.RAMP_DURATION)
    assert state.layer == layers.VESPER and state.ramp is None
    assert (state.player.x, state.player.y) == vesper.arrival(state.world)
    assert state.interaction()[0] == "hatch_out"
    assert state.start_hatch()
    run(state, C.RAMP_DURATION)
    assert state.layer == layers.SURFACE
    assert (state.player.x, state.player.y) == state.surface_exit()


def test_trip_texts():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    assert state.ramp.text == "Entrando..."
    run(state, C.RAMP_DURATION)
    state.start_hatch()
    assert state.ramp.text == "Saindo..."


def test_no_build_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    tx, ty = state.player.tile
    assert not state.active.buildable
    assert not state.can_place("prop_table", (tx + 1, ty))


def test_fixture_texts():
    state = GameState(3)
    assert state.fixture_text("jammed_door") == "Porta emperrada · energizar a nave pode resolver"
    assert state.fixture_text("power_panel") == "Painel de energia · sem bateria"
    assert state.fixture_text("container_broken") == "Vazio. A tampa foi forçada por dentro."


def test_o2_drops_and_no_storm_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    state.storm = 1.0
    before = state.o2
    run(state, 2.0)
    assert state.o2 < before
    from game.systems import storm_level
    assert storm_level(state) == 0.0
    assert state.safe_point()[2] == "SAÍDA"


def test_save_inside_loads_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    crate = next(iter(state.active.crates.values()))
    crate.opened = True
    data = save.state_to_dict(state)
    back = save.state_from_dict(data)
    assert back.layer == layers.VESPER
    assert back.active.crates[crate.tile].opened


def test_save_mid_trip_lands_inside():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    data = save.state_to_dict(state)
    back = save.state_from_dict(data)
    assert back.layer == layers.VESPER
    assert (back.player.x, back.player.y) == vesper.arrival(back.world)


def test_faint_inside_wakes_at_base():
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    state.o2 = 0
    run(state, C.FAINT_DURATION + 0.5)
    assert state.layer == layers.SURFACE
```

- [ ] **Step 2:** `uv run pytest tests/test_vesper_trip.py -q` → FAIL.
- [ ] **Step 3: `RampTrip` e a viagem** (`game/systems.py`)

```python
@dataclass
class RampTrip:
    """Viagem pela rampa ou pela escotilha da VÉSPER (fade): no RAMP_SWITCH_AT troca de camada, no RAMP_DURATION acaba.
    `arrival` (pés) e `text` são da escotilha (v0.7 M4); None = rampa (chega no ramp_arrival, "Descendo..."/"Subindo...")."""
    to: str
    time: float = 0.0
    switched: bool = False
    arrival: tuple[float, float] | None = None
    text: str | None = None
```

  No `_update_ramp`: `self.enter_layer(trip.to, trip.arrival or layers.ramp_arrival(self.layers[trip.to].world))`.

  Métodos novos:

```python
    # ---- escotilha da VÉSPER-7 (v0.7 M4 · game/vesper.py) --------------------
    def hatch_in_target(self) -> tuple[int, int] | None:
        """O tile da boca do porão da VÉSPER (3,2 da pegada), na superfície; None fora dela."""
        if self.layer != SURFACE:
            return None
        w = wrecks.vesper_wreck(self.world)
        return None if w is None else (w.tx + 3, w.ty + 2)

    def hatch_in_distance(self) -> float:
        """Dos pés até a borda de baixo da boca (quem está no (3,3) já está no alcance)."""
        t = self.hatch_in_target()
        if t is None:
            return math.inf
        return math.hypot(self.player.x - (t[0] + 0.5) * C.TILE, self.player.y - (t[1] + 1) * C.TILE)

    def hatch_out_distance(self) -> float:
        if self.layer != layers.VESPER:
            return math.inf
        hx, hy = vesper.hatch_tile(self.world)
        return math.hypot(self.player.x - (hx + 0.5) * C.TILE, self.player.y - (hy + 0.5) * C.TILE)

    def surface_exit(self) -> tuple[float, float]:
        w = wrecks.vesper_wreck(self.surface.world)
        return (w.tx + 3.5) * C.TILE, (w.ty + 3) * C.TILE + 24

    def start_hatch(self) -> bool:
        """E na boca do porão (entra) ou na escotilha do porão (sai): começa o fade, como a rampa."""
        if self.ramp is not None or self.fainted:
            return False
        if self.hatch_in_distance() <= C.RAMP_REACH:
            if layers.VESPER not in self.layers:
                self.layers[layers.VESPER] = layers.MAKERS[layers.VESPER](self.seed)
            trip = RampTrip(layers.VESPER, arrival=vesper.arrival(self.layers[layers.VESPER].world), text="Entrando...")
        elif self.hatch_out_distance() <= C.RAMP_REACH:
            trip = RampTrip(SURFACE, arrival=self.surface_exit(), text="Saindo...")
        else:
            return False
        self.ramp = trip
        self.mining = None
        self.events.append(("ramp", trip.to))
        return True

    def fixture_text(self, kind: str) -> str:
        return C.VESPER_FIXTURE_TEXT[kind]
```

  Em `config.py`:

```python
# v0.7 M4 · interior da VÉSPER-7 (game/vesper.py)
VESPER_FIXTURE_TEXT = {
    "jammed_door": "Porta emperrada · energizar a nave pode resolver",
    "power_panel": "Painel de energia · sem bateria",
    "container_broken": "Vazio. A tampa foi forçada por dentro.",
}
VESPER_FIXTURE_REACH = 48        # px dos pés até a base do fixture (igual ao terminal)
```

- [ ] **Step 4: alvos do E.**
  - `interactable_at`: na superfície, o tile da boca (`hatch_in_target`) e o retângulo do sprite da VÉSPER na altura da boca dão `("hatch_in", tile)`. Na `vesper`, o tile da escotilha dá `("hatch_out", tile)`, e o tile de um fixture de texto (painel, porta, contêiner) dá `("fixture", tile)`. **A ordem importa**: a caixa do porão e os terminais vêm antes.
  - `in_reach`: `hatch_in` → `hatch_in_distance() <= C.RAMP_REACH`; `hatch_out` → `hatch_out_distance() <= C.RAMP_REACH`; `fixture` → distância dos pés até a base do tile (`(tx+0.5)·T, (ty+1)·T`) `<= C.VESPER_FIXTURE_REACH`.
  - `interaction` (o mais perto): entram os três, com essas mesmas distâncias.
  - `app.py`, no E do modo play: `hatch_in`/`hatch_out` → `state.start_hatch()`; `fixture` → `self.show_toast(state.fixture_text(kind))` (use o toast que já existe, `self.toast`/`toast_time`, por ~3 s) e toca `door_stuck` na porta, `power_low` no painel (só se `self.audio.has(...)`). A dica do alvo: `"[E] Entrar na VÉSPER-7"`, `"[E] Sair da nave"`, e o próprio texto do fixture com o mouse em cima.
- [ ] **Step 5: regras lá dentro.**
  - `Layer.buildable` (property): `self.key != VESPER`. No `can_place`, logo no começo: `if not self.active.buildable: return False`. No `app.hint()`, com `placing` na `vesper`: `"Não dá pra construir aqui · Esc cancela"`.
  - `storm_level`: `0.0 if not state.active.has_base else state.storm` (vale pra caverna e nave). A neve (`update_snow`): troque o `self.layer != CAVE` por `self.active.has_base`.
  - `safe_point`: na `vesper`, `(*centro da escotilha, "SAÍDA")`.
  - `state_to_dict` com a viagem no meio: use `trip.arrival or layers.ramp_arrival(...)`.
  - `audio.ambient_for`: `layer == "vesper"` toca `"vesper"` se existir `amb_vesper` (passe `has_vesper` igual ao `has_cave`), senão o `"cave"`. No `app.py`, o som da viagem (`ramp_down` quando `event[1] in ("cave", "vesper")`, senão `ramp_up`) e o `ambient_layer()` seguem iguais.
  - Confira os outros `"cave"`/`CAVE` da lista do `grep` (`app.py` 1835, 1843, 1876–1906; `objectives.py:38`) e decida um por um: o que é "debaixo do chão/dentro" passa a usar `not has_base`; o que é da caverna mesmo (bioma, objetivo de descer) fica. Liste no report.
- [ ] **Step 6:** `uv run pytest tests/test_vesper_trip.py -q` → PASS; depois `uv run pytest` inteiro.

---

### Task 4: desenho, mapa e partículas

**Files:**
- Modify: `game/render.py`, `game/ui.py`, `game/map_view.py`, `game/app.py`, `tools/dev/smoke.py`
- Create: `tools/dev/shot_v07_m4.py`
- Test: `tests/test_vesper_trip.py` (os puros: luzes e mapa)

**Interfaces:**
- Consumes: tudo das Tasks 2 e 3.
- Produces: `render.cave_lights` com as luzes `emergency_light`; `MapView.layers` com a `vesper`; sprites esperados (contrato da Designer, abaixo).

- [ ] **Step 1: testes puros que falham**

```python
def test_emergency_lights_and_map_tab():
    from game import render
    from game.map_view import MapView
    state = GameState(3)
    at_hatch_in(state)
    state.start_hatch()
    run(state, C.RAMP_DURATION)
    lights = render.cave_lights(state)
    n = sum(1 for k in state.world.fixtures.values() if k == "emergency_light")
    assert sum(1 for l in lights if l.color == render.EMERGENCY_LIGHT) == n
    assert MapView.layers(state) == ["surface", "vesper"]
```

- [ ] **Step 2: render.**
  - **Casca**: `draw_base_floors` e `draw_base_wall` pegam o prefixo `"hull"` quando `state.layer == layers.VESPER` (`hull_floor_{v}`, `hull_wall_top`, `hull_wall_face`), e caem no `base_*` se o PNG não existir. O `autotile` (`base_wall_tiles`) precisa de cache separado por prefixo.
  - **Fixtures**: uma passada nova `draw_fixtures` dentro do `collect_*` (ordem de profundidade pelo pé, igual aos props). Sprites: `vesper_hatch` (32×32, no chão, com o chão), `vesper_container_broken` (40×44, âncora do `container_sealed`), `vesper_power_panel`, `vesper_jammed_door` e `vesper_emergency_light` (32×24, na face da parede: `(tx·32, ty·32 + 8)`, como o prop de face). Sem PNG, um retângulo de placeholder com cor própria por tipo. O alvo do E ganha o contorno claro (`outline_of`), como o terminal.
  - **Luz**: `EMERGENCY_LIGHT = (255, 96, 72)`. Em `cave_lights`, cada `emergency_light` soma `LightSource((tx + 0.5)·T, (ty + 1)·T, 2.5·T, EMERGENCY_LIGHT, 0.7)`.
  - **Partículas da porta emperrada** (em `app.py`/`render.py`, no sistema de `self.particles` que já existe): só com o player a ≤ 8 tiles. **Faísca**: a cada 0,6–1,8 s (rng do render), 3–6 partículas amarelas e brancas (`(255, 236, 140)`, `(255, 255, 255)`) saindo do leitor (lado direito da porta: px (24, 12) do sprite de face), vida 0,25 s, com gravidade. Toca `spark` se existir, com volume pela distância. **Névoa**: contínua, 2–3 por segundo, azul-clara translúcida (`(190, 225, 255)`, alfa 60–90), nascendo na soleira (y = `(ty + 1)·T`), andando pros lados e pra baixo devagar (vy 4–8 px/s), vida 1,5–2,5 s, e **morrendo antes de 1 tile da soleira**.
  - **Fade**: `UI.draw_ramp_fade` usa `trip.text` quando tiver; senão o de hoje.
- [ ] **Step 3: mapa.**
  - `MapView.layers`: `[k for k in ("surface", "cave", "vesper") if k in state.layers]`.
  - `UI._map_header`: o rótulo `("vesper", "VÉSPER-7")` entra **só se** `"vesper" in state.layers` (a caverna continua aparecendo apagada antes da descida, como hoje).
  - Abrir o mapa na `vesper` centra no player. Visto de outra camada, centra no meio da nave (`world.center`).
  - O minimapa funciona dentro (o `cave_region` `None` já é tratado). Confira com o shot.
- [ ] **Step 4: smoke e shot.**
  - Cena nova no `tools/dev/smoke.py`: entra na VÉSPER (teleporta pro (3,3), E), print do porão, anda até a cabine (teleporte), print da porta emperrada com partículas, abre o mapa na aba VÉSPER-7, sai. Exit 0.
  - `tools/dev/shot_v07_m4.py` (molde do `shot_v07_m3.py`): prints de cada sala nas 2 variantes (seeds escolhidas pra cobrir `_a` e `_b`), do contêiner com a dica, do painel com a dica e do fade "Entrando...". Saída em `reports/dev/v07_m4/`.
- [ ] **Step 5:** `uv run pytest` inteiro; smoke com `> /tmp/smoke.log 2>&1; echo exit=$?`; `uv run python tools/dev/real_video_check.py`. Olhe os prints.

---

### Task 5: integrar a arte, o som e os LOGs aprovados (depois do ok do dono)

- [ ] Copiar de `reports/design/v07_m4/pendentes/` pra `assets/sprites/` os PNGs aprovados, com o nome do contrato abaixo. Copiar de `reports/audio/` pra `assets/audio/` o `amb_vesper.wav`, o `door_stuck.wav` e o `spark.wav` aprovados (volumes na bíblia §6).
- [ ] Bíblia §6 (contrato de assets): as linhas novas.
- [ ] Shot de novo (`tools/dev/shot_v07_m4.py`) e olhar: a casca encaixa (autotile), a face do painel e da porta caem no lugar, o contêiner fica com o pé no tile.
- [ ] `uv run pytest`.

## Contrato da arte (Designer) e do som (Som)

| Sprite | Tamanho | O quê |
|---|---|---|
| `hull_wall_top` | atlas A2 igual ao `base_wall_top` | topo da parede da nave (metal ardósia da VÉSPER, rebites, sem tijolo da colônia) |
| `hull_wall_face` | 128×24 (4 peças, índice W + 2·E, igual ao `base_wall_face`) | face da parede da nave |
| `hull_floor_0..3` | 32×32 | chão de chapa (grade, manchas, uma com risco de gelo) |
| `vesper_hatch` | 32×32 | escotilha/rampa do porão no chão, com a luz do dia vazando pela fresta |
| `vesper_container_broken` | 40×44 (âncora do `container_sealed`) | contêiner de gelo **arrombado por dentro**: tampa estourada pra fora, metal dobrado de dentro pra fora, gelo derretido escorrido |
| `vesper_power_panel` | 32×24 (face) | painel com tela apagada e o **encaixe vazio com a silhueta da bateria** |
| `vesper_jammed_door` | 32×24 (face) + a porta é a própria parede | porta de nave fechada, torta, com o **leitor de crachá** do lado (silhueta do crachá do desenho do dono: cordão, foto, amarelo) |
| `vesper_emergency_light` | 32×24 (face) | luz de emergência vermelha na parede |

| Som | Tipo | O quê |
|---|---|---|
| `amb_vesper` | ambiente em loop | casco metálico rangendo e um zumbido elétrico morto, bem baixo |
| `door_stuck` | sfx curto | "tunk" seco de trava que não cede |
| `spark` | sfx bem curto | estalinho elétrico, com variação de pitch |

## Self-review do plano
- Cobertura da bíblia §16 M4: uma VÉSPER (T1); camada, salas, esqueleto sem giro, fixtures, caixas, LOGs (T2); entrada e saída, fade, sem construir, O₂, mapa, save (T3/T4); faísca + névoa, luzes (T4); arte e som (T5 + contrato). O "marcador com nome" sai do `SPECS["cargo"].name` (T1).
- Fora do M4 (gancho): abrir a porta emperrada, bateria e crachá da Ilves.

## Mudanças depois do plano (gerente, 2026-10-16, conversas com o dono)
Valem por cima do que está acima.

- **Task 1 (feita)**: `WRECK_RICH_KIND = "robot"` (o `module` 8×4 não cabe no `wreck_spot`).
- **Task 2 (feita)**: o Dev B já pôs `VESPER_FIXTURE_TEXT` e `VESPER_FIXTURE_REACH` no `config.py`; a Task 3 só usa.
- **Contêiner da câmara fria**: não tem sprite novo. O fixture `container_broken` desenha o **`container_open.png`** (já aprovado, v0.5 M4), na mesma âncora do `container_sealed` (pé no tile). O texto continua "Vazio. A tampa foi forçada por dentro.".
- **Escotilha de saída**: o sprite passa a se chamar **`vesper_hatch_exit`** (32×32, no chão, andável, sem luz: buraco escuro, grade arrancada deitada no canto, parafusos soltos). Ainda não aprovado; use placeholder.
- **Luz de emergência**: sprite bem menor (luzinha). No `cave_lights` o raio cai de 2,5 pra **1,5 tile**, com intensidade 0,6.
- **Som aprovado**: `amb_vesper` = candidato **F**; `door_stuck` = **A**; `spark` = **A** (+ `spark_1`, `spark_2`). Origem: `reports/audio/v07_m4_vesper/pendentes/` (`amb_vesper_F.wav`, `door_stuck_A.wav`, `spark_A.wav`, `spark_A1.wav`, `spark_A2.wav`). Créditos do "zzt" (OpenGameArt, BMacZero, CC0) no report do Som, seção "Rodada 3": vão pro `assets/audio/CREDITS.md` na integração. Dicas do Som: `door_stuck` com cooldown de ~0,4 s e pitch 0,96–1,04; `spark` sorteia entre as 3 sem repetir a última, pitch 0,93–1,07, ganho pela distância zerando em ~5–6 tiles.
- **Arte aprovada**: `hull_wall_top`, `hull_wall_face` (**128×24**, 4 peças, índice W + 2·E), `hull_floor_0..3`, `vesper_power_panel`, `vesper_jammed_door`. Em `reports/design/v07_m4/pendentes/`.

### Task 4 ganha: prop maior que 1 tile
A Designer fez props novos (rodada 4, `reports/design/v07_m4/index.html`, **ainda esperando o dono**). Dois deles são **2×1** (`prop_container_stack` 64×40, `prop_command_table` 64×40). Hoje todo prop é 1 tile (M2). A Task 4 ensina o sistema de props a ter tamanho:
- `PropType` ganha `size: tuple[int, int] = (1, 1)` (com default, a `_PROP_TABLE` de hoje não muda de forma) e `Prop.tiles` (a âncora é o tile de cima à esquerda; o `layer.props` guarda **todos** os tiles apontando pro mesmo `Prop`).
- Colisão, `can_place`/`_can_place_prop` (todos os tiles livres), scan (o contorno é o sprite inteiro), desmontar (tira todos os tiles), save (salva só a âncora, `[kind, x, y]`, e o load remonta) e o desenho (o sprite sai uma vez, pela âncora, na ordem de profundidade do pé).
- Na planta (ruínas e nave), a letra do prop 2×1 vai **só na âncora** e o tile da direita é `.`. O `ruins._extract_props`/`ok_in_plan` e o `vesper._built` conferem que os 2 tiles são chão.
- Testes: um prop fake 2×1 em `C.PROPS` via monkeypatch (põe, colide nos 2 tiles, não põe com 1 tile ocupado, desmonta inteiro, salva e carrega).
- **Os 11 props novos NÃO entram no `config.py` nem nas plantas na Task 4** (esperam o ok do dono). Entram na Task 5.
- **Escotilha aprovada (as duas)**: `vesper_hatch_exit_A` e `_B` (rodada 4). O dono mandou guardar as duas, então elas viram **variantes**: a planta `hold_a` usa a A e a `hold_b` usa a B. Na integração entram como `vesper_hatch_exit_a.png` e `vesper_hatch_exit_b.png`, e o render escolhe pela variante do porão sorteada (`vesper` expõe qual).
- **Luz de emergência aprovada (as duas)**: `vesper_emergency_light_A` (luzinha 6 px) e `_B` (8 px, com grade), da rodada 2. As duas entram como variantes, `vesper_emergency_light_a.png` e `_b.png`, e o render sorteia por hash do tile (determinístico, igual ao `floor_variant`).
- **Traje EVA aprovado (os dois)**: `prop_suit_locker_r6_A` (armário de portas abertas, visor azul-marinho) e `_r6_B` (nicho com LEDs, viseira dourada), rodada 6. Entram como **dois props** escaneáveis: `prop_suit_locker` (A) e `prop_suit_niche` (B, nome "Nicho de traje"), os dois floor 1×1, colidem.
- **Macacão aprovado (os dois)**: `prop_uniforms_r6_A` e `_B` (rodada 6). Entram como variantes do decal `prop_uniforms` (`prop_uniforms_a.png`/`_b.png`), sorteadas por hash do tile.
- **Kit aprovado (rodadas 4/5)**: `prop_container_stack` (r4, 2×1), `prop_command_table` (r5, 2×1), `prop_o2_cylinders`, `prop_server_rack`, `prop_server_rack_open`, `prop_workstation`, `prop_pilot_chair` (r5), `wall_cable_panel` (r4). Em revisão (rodada 7): `prop_wall_bunk` (travesseiro e lençol), mesas novas (com uma redonda 2×2 com painéis) e o `prop_microscope` refeito.
- **Destroços maiores** (pedido do dono): outra Designer refaz os 5 em escala maior (`reports/design/v07_m4_destrocos/`). Depois da aprovação vira uma **Task 6** do Dev: pegadas e marcas novas no `SPECS`, a boca do porão nova da VÉSPER (`hatch_in_target`/`surface_exit`), a regra de lugar e os testes de geração (seeds 0–199 sem destroço perdido).
- **Destroços maiores, aprovados (rodada 2 de `reports/design/v07_m4_destrocos/`)**: base espacial `wreck_module_r2` (14×5), sonda `wreck_probe_r2` (3×2), ARCA-2 **A e B** (`wreck_liner_r2_{A,B}`, 9×4) e robô **A e B** (`wreck_robot_r2_{A,B}`, 3×2) — os dois de cada viram **variantes sorteadas pela seed** do destroço (determinístico, vai junto do `Wreck`; não precisa de save). Contrato completo no "Pro Dev" da rodada 2. A **VÉSPER** vai numa v2 (rodada 3: maior, porão na traseira, frente e pés menos quadrados); a Task 6 espera ela.
