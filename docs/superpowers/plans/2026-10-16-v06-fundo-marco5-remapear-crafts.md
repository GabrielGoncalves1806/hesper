# v0.6 Fundo · Marco 5 · Remapear crafts · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** a cadeia nova (Fundição e Bancada T2) vira obrigatória do Ti 10.000 pra frente. A Fundição passa a 3:1 e não faz mais wafer. O wafer passa a sair da Bancada T2. As receitas são remapeadas pela tabela da bíblia. A Bancada mostra tudo do T1 mais as dela, e o equipamento único fica "feito" depois de fabricado.

**Arquitetura:** é quase tudo dado em `game/config.py`, que já guia slots, drones, save e UI. Também tem quatro mudanças de regra:
- **3:1 na Fundição**: `C.SMELTER_ORE_PER_INGOT`, que o `smelter_blocker` e o `_update_smelter` passam a usar.
- **A T2 aceita receita do T1**: no `GameState.craft` e no `fabricator.t2_kinds`.
- **Estado novo `"made"` no `recipe_status`**: irmão do `"known"`, que já existe pro diagrama lido.
- **A T2 lê todos os diagramas**: no `bench_reads`.

O "já fabricou" usa o `GameState.crafted`, que **já vai no save**. Por isso o save continua v12, sem migração.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** bíblia §15, seção "Marco 5 · Remapear crafts (decisões do dono, 2026-10-16)". Ela é a fonte da tabela de receitas. Spec do Fundo, seção "M5".

## Restrições globais
- **Números de partida** (balanceamento depois). Use exatamente estes:
  - Fundição: `SMELTER_ORE_PER_INGOT = 3`; `SMELTER_RECIPES = {"iron": "iron_ingot", "copper": "copper_ingot"}` (sem silício). A magmatita continua queimando 1 carga por lingote (`SMELTER_BURNS_PER_FUEL = 4`), e o `SMELTER_TIME` (15 s) continua por lingote.
  - Receitas (o `cost` de cada `MachineType`):
    - `silicon_wafer` `{"silicon": 10}`
    - `circuit` `{"wire": 3, "silicon": 5}`
    - `chip` `{"silicon_wafer": 5, "wire": 5, "circuit": 1}`
    - `drone` `{"circuit": 2, "wire": 5, "iron_ingot": 2}`
    - `o2_tank` `{"iron_ingot": 5, "circuit": 1}`
    - `scanner` `{"circuit": 4, "iron_ingot": 5, "silicon": 2}`
    - `backpack` `{"iron_ingot": 5}`
    - `constructor` `{"iron": 5, "silicon": 5}`
    - `o2_dispenser` `{"circuit": 3, "chip": 2, "iron_ingot": 15, "wire": 5, "water_capsule": 2}`
    - `drill` `{"iron_ingot": 5, "circuit": 1}`
    - `drone_station` `{"iron_ingot": 10, "circuit": 1, "chip": 1, "wire": 2}`
    - `o2_t2` `{"iron_ingot": 8, "circuit": 2, "ice": 10}`
    - `melter_t2` `{"iron_ingot": 6, "wire": 4, "ice": 20}`
    - `heater_t2` `{"iron_ingot": 8, "copper_ingot": 3, "magmatite": 10}`
    - `chest` `{"iron_ingot": 3}`
    - `chest_large` `{"iron_ingot": 6}`
    - `diagram_chest_large` `{"iron_ingot": 4, "circuit": 1}`
    - Iguais: `wire` (`{"copper_ingot": 1}`, rende 3), `hand_drill_t2`, `smelter`, `workbench`, `diagram_workbench`, e tudo de Ti 0 (`o2`, `melter`, `heater`, `solar`, `lamp`, `lamp_t2`, `chest_small`, chão/parede/portas).
  - Os `unlock_ti` não mudam.
- **Só na Bancada T2** (`C.T2_RECIPES`): `silicon_wafer`, `circuit`, `chip`, `drone`, `o2_tank`, `backpack`, `scanner`, `hand_drill_t2`. O T1 não mostra nenhuma delas.
- **Item de uma vez só** (`C.ONCE_ITEMS`): `constructor`, `backpack`, `o2_tank`, `scanner`, `hand_drill_t2`. Depois de fabricado (`crafted[kind] >= 1`) ou se o player tem um (inventário ou equipamento), `recipe_status` dá `"made"`. A lista mostra **"feito"** (igual ao "lido") e o botão mostra **"JÁ FEITO"** (igual ao "JÁ LIDO"). Não fabrica.
- **Logística:** `silicon_wafer` sai do `LOGISTIC_ITEMS`, e o baú volta pra **8 toggles**.
- **Save continua v12.** O `crafted` já é salvo. Uma Fundição de save antigo com silício na entrada ou wafer na saída **não perde o item** no load: ele fica lá parado ("SEM MINÉRIO"), e o player tira com o cursor.
- **Simulador** (`tools/dev/balance_sim.py`): ele não sabe fazer a cadeia (não constrói Fundição nem Bancada, e as estratégias de superfície nem descem atrás de cobre). Neste marco ele **roda com as receitas do M4 congeladas** (`LEGACY_RECIPES`, aplicadas por baixo dos overrides). Ensinar a cadeia pra ele é tarefa da passada de balanceamento (ROADMAP Futuro).
- Não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` e `settings.json`. **Sem arte nem som novos.**
- **Sem cena nova no smoke** (regra do dono). Os prints avulsos ficam em `tools/dev/shot_v06_fundo_m5.py` (Task 5).
- Não abrir janela e não commitar. No fim: `uv run pytest`. O gerente roda o smoke e o `real_video_check` no merge.

## Decisões (o dono deveria ver)
- **Sem save novo:** o "feito" sai do `crafted` (que já é salvo) mais "tem no inventário ou no equipamento" (cobre o construtor do começo). O equipamento esquecido num baú de save antigo também conta, porque foi fabricado e o `crafted` lembra.
- **A Bancada lê todos os diagramas.** Os diagramas do tanque e do scanner (de destroço) passam a ser lidos **só na Bancada T2** (`DIAGRAM_BENCH` → `"t2"`), porque a receita deles mora lá. O T1 continua lendo os dele (luminária forte, Bancada, baú grande).
- **Abas da T2:** "Bancada" (as 8 exclusivas) **primeiro**, depois as do T1 (Ferramentas, Automação, Materiais, Traje) com as receitas do T1.
- **Objetivos (Task 4):** os objetivos são em sequência. Hoje "Fabrique e equipe o tanque de O₂" vem cedo (antes do painel solar), e o tanque agora pede circuito, o que **travaria a fila de objetivos** até o meio do jogo. O "Construa uma drill num veio" logo depois da Névoa também ficaria sem caminho. Proposta: o tanque desce pra depois da drill, e entram 3 objetivos-guia antes da drill (Bancada T2, Fundição, circuito).

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | `SMELTER_ORE_PER_INGOT`, `SMELTER_RECIPES` sem silício, `SMELTER_LEGACY`, `LOGISTIC_ITEMS` sem wafer, todos os `cost` da tabela, `T2_RECIPES`, `T2_TABS`, `ONCE_ITEMS`, `DIAGRAM_BENCH` |
| `game/systems.py` | `smelter_blocker` e `_update_smelter` 3:1; `craft` aceita T1 na T2; `recipe_status` → `"made"`; `owns`; `bench_reads` (T2 lê tudo) |
| `game/save.py` | o filtro da Fundição aceita `SMELTER_LEGACY` |
| `game/fabricator.py` | `t2_kinds` por aba (Bancada + abas do T1) |
| `game/app.py` | recusa e estado da Fundição; aviso "JÁ FEITO" no craft |
| `game/ui.py` | "feito" na lista e "JÁ FEITO" no botão |
| `game/objectives.py` | ordem nova e 3 objetivos-guia (Task 4) |
| `tools/dev/balance_sim.py` | `LEGACY_RECIPES` congeladas |
| `tools/dev/shot_v06_fundo_m5.py` (novo) | prints |
| `docs/GAME_BIBLE.md` | §15 "Marco 5 · como ficou" |
| `tests/test_remap_crafts.py` (novo) | receitas, T2 ⊇ T1, "made", diagramas |
| `tests/test_smelter.py` | 3:1, sem silício, legacy |
| Testes que fixam custo antigo | `test_chip`, `test_fabricator`, `test_drones`, `test_backpack`, `test_chest_sizes`, `test_energy`, `test_inventory`, `test_cave`, `test_base`, `test_drill_t2`: atualizar pro custo novo, ou dar os itens novos com `helpers.give` |

---

### Task 1: Fundição 3:1, sem wafer, wafer fora da logística

**Files:**
- Modify: `game/config.py` (bloco "v0.6 Fundo M3", ~linhas 294–305, e a linha `LOGISTIC_ITEMS`, ~601)
- Modify: `game/systems.py:134-148` (`smelter_blocker`), `game/systems.py:1431-1453` (`_update_smelter`)
- Modify: `game/save.py:297-299`
- Modify: `game/app.py:1125-1126` (recusa), `game/app.py:1314-1322` (`smelter_status`)
- Test: `tests/test_smelter.py`

**Interfaces:**
- Produces: `C.SMELTER_ORE_PER_INGOT: int = 3`, `C.SMELTER_LEGACY: dict[int, set[str]]` (slot → itens antigos aceitos no load).

- [ ] **Step 1: Testes que falham** (em `tests/test_smelter.py`; troque os testes do wafer do M4, ~linhas 225–250, por estes):

```python
def test_three_ore_make_one_ingot(game):
    m = add_smelter(game, ore=("iron", 6), fuel_items=1)
    run(game, C.SMELTER_TIME + 0.1)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("iron_ingot", 1)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("iron", 3)


def test_less_than_three_ore_does_not_smelt(game):
    m = add_smelter(game, ore=("copper", 2), fuel_items=1)
    assert m.smelter_blocker == "no_ore"
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] is None
    assert m.storage.count("magmatite") == 1                 # parada não acende combustível


def test_silicon_no_longer_smelts(game):
    assert "silicon" not in C.SMELTER_RECIPES
    assert "silicon_wafer" not in C.LOGISTIC_ITEMS
    m = add_smelter(game)
    assert not drones.can_receive(m, "silicon") and not drones.can_send(m, "silicon_wafer")


def test_old_save_keeps_silicon_and_wafer_in_smelter(game):
    data = {"kind": "smelter", "tx": 64, "ty": 70, "timer": 0.0, "fuel": 0,
            "storage": [["silicon", 3], None, ["silicon_wafer", 2]]}
    m = save.machine_from_dict(data)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("silicon", 3)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("silicon_wafer", 2)
    assert m.smelter_blocker == "no_ore"
```

Veja como o teste antigo do save (~linha 244) monta a máquina e chama o load (nome da função de `save.py` e campos), e **copie o mesmo jeito**. Se não for `machine_from_dict`, use o nome real.

- [ ] **Step 2:** `uv run pytest tests/test_smelter.py -q` → os 4 falham.

- [ ] **Step 3: Config.** No bloco do M3:

```python
SMELTER_ORE_PER_INGOT = 3                      # v0.6 Fundo M5: 3 minérios → 1 lingote (o tempo e a magmatita são por lingote)
SMELTER_RECIPES = {"iron": "iron_ingot", "copper": "copper_ingot"}   # M5: o silício saiu (o wafer é da Bancada T2)
SMELTER_LEGACY = {SMELTER_ORE_SLOT: {"silicon"}, SMELTER_OUT_SLOT: {"silicon_wafer"}}   # save do M4: não some no load
```

E `LOGISTIC_ITEMS = RESOURCES + ("water_capsule", "iron_ingot", "copper_ingot")` (atualize o comentário: "M5: o wafer saiu").

- [ ] **Step 4: Regra.** No `smelter_blocker`, logo depois do `if ingot is None: return "no_ore"`:

```python
        if self.storage.slots[C.SMELTER_ORE_SLOT].count < C.SMELTER_ORE_PER_INGOT:
            return "no_ore"
```

No `_update_smelter`, troque `smelter.storage.remove(smelter.storage.slots[C.SMELTER_ORE_SLOT].item, 1)` por `..., C.SMELTER_ORE_PER_INGOT)` e ajuste a docstring ("3 minérios da entrada viram 1 lingote").

- [ ] **Step 5: Save.** Em `game/save.py:298-299`, una os legados:

```python
    allowed = {C.SMELTER_ORE_SLOT: set(C.SMELTER_RECIPES) | C.SMELTER_LEGACY[C.SMELTER_ORE_SLOT],
               C.SMELTER_FUEL_SLOT: {C.SMELTER_FUEL},
               C.SMELTER_OUT_SLOT: set(C.SMELTER_RECIPES.values()) | C.SMELTER_LEGACY[C.SMELTER_OUT_SLOT]}
```

- [ ] **Step 6: App.**
  - Recusa: `"A Fundição só aceita ferro, cobre e magmatita"`.
  - `smelter_status`: troque `f"1 A CADA {C.SMELTER_TIME:g} S"` por `f"{C.SMELTER_ORE_PER_INGOT} → 1 A CADA {C.SMELTER_TIME:g} S"`.
  - Procure em `game/ui.py`, `game/app.py` e `game/render.py` outros textos que dizem "1 minério" ou "silício" sobre a Fundição: `grep -n "silício" game/app.py game/ui.py | grep -i fundi`.

- [ ] **Step 7:** `uv run pytest tests/test_smelter.py tests/test_drones.py -q` → verde. Se um teste antigo da Fundição assumir 1:1, ajuste o número de minérios (×3) mantendo o que ele testa.

---

### Task 2: Receitas novas, a T2 lê tudo, simulador congelado

**Files:**
- Modify: `game/config.py` (os `cost` da tabela, `T2_RECIPES`, `DIAGRAM_BENCH`)
- Modify: `game/systems.py:1861-1864` (`bench_reads`)
- Modify: `tools/dev/balance_sim.py` (`LEGACY_RECIPES` + `simulate`)
- Create: `tests/test_remap_crafts.py`
- Modify: os testes que fixam custo antigo (lista na tabela de arquivos)

**Interfaces:**
- Produces: `C.T2_RECIPES` com as 8 exclusivas; `GameState.bench_reads(diagram, "t2")` sempre `True` pra diagrama conhecido.

- [ ] **Step 1: Testes que falham** em `tests/test_remap_crafts.py`:

```python
"""v0.6 Fundo M5: receitas remapeadas pra cadeia nova (bíblia §15 "Marco 5")."""

import random

import pytest

from game import config as C
from game.systems import GameState

NEW_COSTS = {
    "silicon_wafer": {"silicon": 10},
    "circuit": {"wire": 3, "silicon": 5},
    "chip": {"silicon_wafer": 5, "wire": 5, "circuit": 1},
    "drone": {"circuit": 2, "wire": 5, "iron_ingot": 2},
    "o2_tank": {"iron_ingot": 5, "circuit": 1},
    "scanner": {"circuit": 4, "iron_ingot": 5, "silicon": 2},
    "backpack": {"iron_ingot": 5},
    "constructor": {"iron": 5, "silicon": 5},
    "o2_dispenser": {"circuit": 3, "chip": 2, "iron_ingot": 15, "wire": 5, "water_capsule": 2},
    "drill": {"iron_ingot": 5, "circuit": 1},
    "drone_station": {"iron_ingot": 10, "circuit": 1, "chip": 1, "wire": 2},
    "o2_t2": {"iron_ingot": 8, "circuit": 2, "ice": 10},
    "melter_t2": {"iron_ingot": 6, "wire": 4, "ice": 20},
    "heater_t2": {"iron_ingot": 8, "copper_ingot": 3, "magmatite": 10},
    "chest": {"iron_ingot": 3},
    "chest_large": {"iron_ingot": 6},
    "diagram_chest_large": {"iron_ingot": 4, "circuit": 1},
}
T2_ONLY = {"silicon_wafer", "circuit", "chip", "drone", "o2_tank", "backpack", "scanner", "hand_drill_t2"}
RAW_AT_TI0 = ("o2", "melter", "heater", "solar", "lamp", "lamp_t2", "chest_small", "smelter", "workbench",
              "diagram_workbench", "base_floor", "base_wall", "base_door", "base_door2")


@pytest.mark.parametrize("kind", sorted(NEW_COSTS))
def test_new_cost(kind):
    assert C.MACHINES[kind].cost == NEW_COSTS[kind]


def test_t2_exclusives():
    assert set(C.T2_RECIPES) == T2_ONLY


@pytest.mark.parametrize("kind", RAW_AT_TI0)
def test_ti0_stays_raw(kind):
    assert set(C.MACHINES[kind].cost) <= set(C.RESOURCES)


def test_wire_unchanged():
    assert C.MACHINES["wire"].cost == {"copper_ingot": 1} and C.CRAFT_YIELD["wire"] == 3


@pytest.mark.parametrize("diagram", sorted(C.BLUEPRINTS))
def test_bench_t2_reads_every_diagram(diagram):
    assert GameState.bench_reads(diagram, "t2")


def test_tank_and_scanner_diagrams_read_only_on_t2():
    assert not GameState.bench_reads("o2_tank", "t1") and not GameState.bench_reads("scanner", "t1")
    assert GameState.bench_reads("lamp_t2", "t1") and GameState.bench_reads("chest_large", "t1")
```

(`bench_reads` é `@staticmethod`: mantenha o decorador.)

- [ ] **Step 2:** `uv run pytest tests/test_remap_crafts.py -q` → falham.

- [ ] **Step 3: Config.** Troque cada `cost` **no lugar onde ele é definido hoje**, sem criar outro bloco que sobrescreva:
  - `DRILL_COST`, `DRONE_STATION_COST`, `DRONE_COST`, `CHEST_COST["chest"]`, `CHEST_COST["chest_large"]`, `CHEST_DIAGRAM_COST`;
  - os `MachineType` de `o2_t2`, `melter_t2`, `heater_t2`, `o2_tank`, `scanner`, `backpack`, `constructor`, `o2_dispenser`;
  - `CHIP_COST`;
  - o `circuit` (bloco do M4);
  - o `silicon_wafer`: hoje ele é `MachineType` de loot com `cost={}`. Faça `MACHINES["silicon_wafer"] = _replace(MACHINES["silicon_wafer"], cost={"silicon": 10})` no bloco novo "v0.6 Fundo M5", no fim do arquivo.

  Atualize os comentários que citam o número antigo. Depois:

```python
T2_RECIPES = ("silicon_wafer", "circuit", "chip", "drone", "o2_tank", "backpack", "scanner", HAND_DRILL_T2)  # M5
DIAGRAM_BENCH = {**DIAGRAM_BENCH, "o2_tank": "t2", "scanner": "t2"}   # M5: a receita deles mora na Bancada T2
```

  Ponha isso no bloco "v0.6 Fundo M5", no fim do `config.py`, **depois** do `T2_RECIPES = T2_RECIPES + (HAND_DRILL_T2,)` do M4. Confira se o `MACHINE_ORDER` e o `MACHINE_CATEGORY` do wafer, do drone e do circuito não quebram nada (a categoria não importa pra T2, que tem aba própria).

- [ ] **Step 4: `bench_reads`.**

```python
    def bench_reads(diagram: str, bench: str) -> bool:
        """A `bench` lê esse diagrama? A Bancada T2 lê todos (é o fabricador melhorado, v0.6 Fundo M5); o T1 lê os de
        máquina (placeable) e os de C.DIAGRAM_BENCH == "t1"."""
        if diagram not in C.BLUEPRINTS:
            return False
        if bench == "t2":
            return True
        machine = C.MACHINES.get(C.RECIPE_BLUEPRINT.get(diagram, ""))
        return bool(machine and machine.placeable) or C.DIAGRAM_BENCH.get(diagram) == bench
```

- [ ] **Step 5: Simulador congelado.** Em `tools/dev/balance_sim.py`, perto do `patched_config`:

```python
# v0.6 Fundo M5: o simulador ainda não sabe fazer a cadeia (Fundição, Bancada T2, cobre da caverna). Até a passada de
# balanceamento (ROADMAP Futuro), ele roda com as receitas do M4. Os overrides de uma proposta vêm por cima.
LEGACY_RECIPES = {
    "MACHINES": {
        "drill": {"cost": {"iron": 12, "silicon": 6}},
        "drone_station": {"cost": {"iron": 12, "silicon": 8, "ice": 3}},
        "drone": {"cost": {"iron": 6, "silicon": 4}},
        "o2_tank": {"cost": {"iron": 10, "silicon": 6, "ice": 4}},
        "scanner": {"cost": {"iron": 4, "silicon": 4}},
        "backpack": {"cost": {"iron": 12, "silicon": 6}},
        "constructor": {"cost": {"iron": 5}},
        "o2_dispenser": {"cost": {"iron": 14, "silicon": 8}},
        "o2_t2": {"cost": {"iron": 30, "silicon": 20, "ice": 10}},
        "melter_t2": {"cost": {"iron": 25, "ice": 30}},
        "heater_t2": {"cost": {"iron": 35, "silicon": 25, "magmatite": 10}},
        "chest": {"cost": {"iron": 6}},
        "chest_large": {"cost": {"iron": 10, "silicon": 2}},
    },
    "T2_RECIPES": ("backpack", "chip", "hand_drill_t2"),
    "DIAGRAM_BENCH": {"o2_tank": "t1", "scanner": "t1", "lamp_t2": "t1", "workbench": "t1", "chest_large": "t1"},
}


def with_legacy(overrides: dict | None) -> dict:
    """As receitas do M4 por baixo; os overrides da proposta por cima (MACHINES mesclado por máquina)."""
    merged = copy.deepcopy(LEGACY_RECIPES)
    for key, value in (overrides or {}).items():
        if key == "MACHINES":
            for kind, fields in value.items():
                merged["MACHINES"].setdefault(kind, {}).update(fields)
        else:
            merged[key] = value
    return merged
```

  No `simulate`: `with patched_config(with_legacy(overrides)):`. Procure outros `patched_config(` no arquivo e nos testes (`grep -n "patched_config(" tools/dev/balance_sim.py tests/test_balance_sim.py`). Onde roda o jogo simulado, use o `with_legacy`. O `test_overrides_nao_vazam_pro_config` continua valendo, porque o `patched_config` restaura tudo.

  O `constructor` continua no T1 com os números antigos, o que é ok. O `o2_dispenser` antigo também. No `LEGACY_RECIPES`, confira se cada chave do `MACHINES` existe no `C.MACHINES`.

- [ ] **Step 6: Testes antigos.** `uv run pytest -q -x`. Pra cada teste que quebrar por custo antigo: se ele testa o **custo**, troque pro novo; se ele testa **outra coisa** (drone voando, baú guardando, energia), dê os itens novos com `helpers.give(game, iron_ingot=..., circuit=...)`. **Não enfraqueça o que o teste verifica.** O `test_chip` (`cost == {"silicon_wafer": 2, "iron": 1}`) e o `test_fabricator` do circuito (aba Materiais, `craft("circuit")` no T1) mudam de sentido: o circuito agora é da T2. Reescreva-os pra Bancada (`craft("circuit", bench="t2", at=...)`, no molde do `tests/test_drill_t2.py`).

- [ ] **Step 7:** `uv run pytest -q` → verde (incluindo `tests/test_balance_sim.py`).

---

### Task 3: A Bancada vê tudo do T1 (abas) e o item de uma vez só ("feito")

**Files:**
- Modify: `game/config.py` (`T2_TABS`, `ONCE_ITEMS` no bloco do M5)
- Modify: `game/fabricator.py:144-151` (`t2_kinds`)
- Modify: `game/systems.py:707-721` (`recipe_status`), `game/systems.py:738-748` (`craft`), novo `owns`
- Modify: `game/ui.py:1250-1251` e `game/ui.py:1385-1386`; `game/app.py:~675` (o aviso do `"known"`)
- Test: `tests/test_remap_crafts.py`

**Interfaces:**
- Consumes: `C.T2_RECIPES` (Task 2).
- Produces: `C.ONCE_ITEMS: tuple[str, ...]`, `C.T2_TABS` com `("t2", "Bancada")` primeiro, `fabricator.t2_kinds(tab_id) -> list[str]`, `GameState.owns(kind) -> bool`, `recipe_status` pode devolver `"made"`.

- [ ] **Step 1: Testes que falham** (acrescente em `tests/test_remap_crafts.py`):

```python
from game import fabricator
from game.inventory import Stack
from tests.helpers import give


def test_t2_tabs_bench_first_then_t1():
    assert C.T2_TABS[0] == ("t2", "Bancada")
    assert C.T2_TABS[1:] == C.CRAFT_TABS
    assert set(fabricator.t2_kinds("t2")) == T2_ONLY
    for tab_id, _ in C.CRAFT_TABS:
        assert fabricator.t2_kinds(tab_id) == fabricator.craft_kinds(tab_id)


def test_t1_hides_t2_recipes():
    t1 = {k for tab_id, _ in C.CRAFT_TABS for k in fabricator.craft_kinds(tab_id)}
    assert not (t1 & T2_ONLY)
    assert "wire" in t1 and "constructor" in t1


def test_bench_crafts_t1_recipe_from_inventory():
    g = GameState(rng=random.Random(1))
    give(g, copper_ingot=1)
    assert g.craft("wire", bench="t2")
    assert g.inventory.count("wire") == 3


def test_t1_still_refuses_t2_recipe():
    g = GameState(rng=random.Random(1))
    give(g, iron_ingot=5)
    assert not g.craft("backpack")                       # T1
    assert g.craft("backpack", bench="t2")


def test_once_item_becomes_made_after_craft():
    g = GameState(rng=random.Random(1))
    give(g, iron_ingot=10)
    assert g.craft("backpack", bench="t2")
    assert g.recipe_status("backpack", inv_only=True) == "made"
    assert not g.craft("backpack", bench="t2")
    assert g.inventory.count("iron_ingot") == 5


def test_once_item_made_when_owned_or_equipped():
    g = GameState(rng=random.Random(1))
    g.inventory.add("constructor", 1)                    # o construtor do começo, sem crafted
    assert g.recipe_status("constructor") == "made"
    g.equipment.equip("o2_tank")
    assert g.recipe_status("o2_tank", inv_only=True) in ("made", "blueprint")


def test_once_items_list():
    assert set(C.ONCE_ITEMS) == {"constructor", "backpack", "o2_tank", "scanner", "hand_drill_t2"}


def test_made_survives_save_roundtrip():
    from game import save
    g = GameState(rng=random.Random(1))
    give(g, iron_ingot=5)
    g.craft("backpack", bench="t2")
    g.inventory.remove("backpack", 1)                    # "esqueceu num baú": só o crafted lembra
    g2 = save.state_from_dict(save.state_to_dict(g))
    assert g2.recipe_status("backpack", inv_only=True) == "made"
```

Confira o nome real do `equipment.equip` (veja `tests/test_backpack.py` e `tests/test_save*.py`) e ajuste.

O diagrama do tanque é "blueprint" enquanto não foi lido, e o `blueprint` vem antes no `recipe_status`. Isso é esperado: o diagrama não lido manda. Pro tanque, o teste aceita os dois. Teste o `"made"` limpo com a mochila.

- [ ] **Step 2:** `uv run pytest tests/test_remap_crafts.py -q` → os novos falham.

- [ ] **Step 3: Config** (bloco do M5):

```python
T2_TABS = (("t2", "Bancada"),) + CRAFT_TABS      # M5: a Bancada vê tudo do T1, com as exclusivas dela primeiro
ONCE_ITEMS = ("constructor", "backpack", "o2_tank", "scanner", HAND_DRILL_T2)   # fabricou, fica "feito" (não se perde item)
```

- [ ] **Step 4: `fabricator.t2_kinds`:**

```python
def t2_kinds(tab_id: str) -> list[str]:
    """Receitas da Bancada T2 numa aba (v0.6 Fundo M5): "t2" = as exclusivas dela (C.T2_RECIPES); as outras abas
    são as mesmas do fabricador T1."""
    return list(C.T2_RECIPES) if tab_id == "t2" else craft_kinds(tab_id)
```

- [ ] **Step 5: `GameState`.** Perto do `recipe_status`:

```python
    def owns(self, kind: str) -> bool:
        """Tem um desses no inventário ou no traje (v0.6 Fundo M5: item de uma vez só)."""
        return self.inventory.count(kind) > 0 or self.equipment.has(kind)
```

  No `recipe_status`, logo depois do `if kind in C.DIAGRAM_ITEMS ...: return "known"`:

```python
        if kind in C.ONCE_ITEMS and (self.crafted[kind] > 0 or self.owns(kind)):
            return "made"                       # v0.6 Fundo M5: item de uma vez só, já fabricado
```

  Atualize a docstring com `'made'`. No `craft`, troque a guarda `(kind in C.T2_RECIPES) != t2` por `(kind in C.T2_RECIPES and not t2)`: a T2 fabrica tudo, e o T1 não fabrica as dela. Atualize a docstring ("`bench` "t2": as receitas dela e as do T1").

  **O `hand_drill_t2` consome a nv.1.** O `crafted["hand_drill_t2"]` marca depois da primeira. Confira que o `tests/test_drill_t2.py` continua verde.

- [ ] **Step 6: UI.** Em `game/ui.py:1250`:

```python
            elif status in ("known", "made"):          # diagrama lido / item de uma vez só já fabricado
                status_w = self.tx("lido" if status == "known" else "feito", right, ry + 2, B_DIM, self.body, "right")
```

  E em `game/ui.py:1385`:

```python
        elif status in ("known", "made"):
            label, kind_b = ("JÁ LIDO" if status == "known" else "JÁ FEITO"), "off"
```

  Confira se a linha da receita fica apagada (`locked`) no "made" como no "known": `grep -n "locked =" game/ui.py`. Se o `locked` listar os estados, inclua o `"made"`.

  No `game/app.py:~675` (`elif result == "known":`), veja o que o craft devolve e qual aviso aparece. Se o caminho do clique em FABRICAR passar por ali com o "made", mostre `"Você já fabricou esse"`. O botão "off" provavelmente já impede o clique, então só mude se precisar.

- [ ] **Step 7:** `uv run pytest -q` → verde. O `test_every_recipe_detail_draws` (T1 e T2) tem que passar com as abas novas.

---

### Task 4: Objetivos que não travam (aprovado pelo dono, 2026-10-16)

**Files:**
- Modify: `game/objectives.py:70-115`
- Test: `tests/test_objectives.py` (ou onde os objetivos são testados: `grep -ln "OBJECTIVES" tests/`)

**Interfaces:**
- Consumes: `crafted`, `blueprints`, `machines` do `GameState`.

- [ ] **Step 1: Teste que falha:**

```python
def test_m5_chain_guides_before_drill():
    texts = [o.text for o in objectives.OBJECTIVES]
    i_mist = texts.index("Chegue ao estágio Névoa")
    i_drill = texts.index("Construa uma drill num veio")
    guide = ["Construa a Bancada T2", "Construa uma Fundição", "Fabrique um circuito na Bancada T2"]
    assert texts[i_mist + 1:i_drill] == guide
    assert texts.index("Fabrique e equipe o tanque de O₂") > texts.index("Receba uma entrega de drone")
```

- [ ] **Step 2: Mudança** em `OBJECTIVES`:
  - tire "Fabrique e equipe o tanque de O₂" de onde está e ponha logo depois de "Receba uma entrega de drone". O "Ache e leia o diagrama do tanque de O₂" continua no lugar, porque ler é cedo;
  - logo depois de "Chegue ao estágio Névoa", insira:

```python
    # v0.6 Fundo M5: a drill pede circuito (cobre do salar → Fundição → fios → Bancada T2). Os três guiam a cadeia.
    Objective("Construa a Bancada T2", lambda s: crafted(s, "workbench") >= 1),
    Objective("Construa uma Fundição", lambda s: crafted(s, C.SMELTER) >= 1),
    Objective("Fabrique um circuito na Bancada T2", lambda s: crafted(s, "circuit") >= 1),
```

  Confira se construir conta no `crafted` (`systems.py:859` diz que sim). O "ler o diagrama do tanque" agora só funciona na T2, mas o objetivo de ler continua cedo. Isso é aceitável: o player acha o diagrama e lê depois. Se o teste de objetivos exigir ler cedo, o objetivo de ler desce junto, pra antes do "Fabrique e equipe".

- [ ] **Step 3:** `uv run pytest -q` → verde.

---

### Task 5: Prints e bíblia

**Files:**
- Create: `tools/dev/shot_v06_fundo_m5.py` (no molde do `tools/dev/shot_v06_fundo_m4.py`)
- Modify: `docs/GAME_BIBLE.md` (fim da §15)

- [ ] **Step 1: Prints** em `reports/dev/v06_fundo_m5/`:
  - `bench_tab_bancada.png`: Bancada T2 aberta na aba "Bancada", com o wafer selecionado;
  - `bench_tab_materiais.png`: Bancada na aba Materiais (fios do T1);
  - `bench_made.png`: Bancada com a mochila já fabricada ("feito" na lista, "JÁ FEITO" no botão);
  - `fab_t1_tools.png`: T1 na aba Ferramentas (construtor "feito", diagrama do baú grande com o custo novo);
  - `smelter_3to1.png`: Fundição com 6 ferro e o estado "3 → 1 A CADA 15 S";
  - `chest_logistics.png`: baú com os 8 toggles;
  - `build_dispenser.png`: construtor com o Dispersor selecionado (receita longa: confira se as 5 linhas de custo cabem no painel de detalhe).

  Rode `uv run python tools/dev/shot_v06_fundo_m5.py` e **olhe cada PNG**. Se algum texto cortar ou o custo do Dispersor não couber, **pare e avise o gerente** (não redesenhe o painel).

- [ ] **Step 2: Bíblia.** No fim da §15, crie "### Marco 5 · como ficou na implementação (`game/config.py` bloco "v0.6 Fundo M5", `game/systems.py`, `game/fabricator.py`, `game/ui.py`, `game/objectives.py`, `tools/dev/balance_sim.py`)", com bullets curtos pra:
  - a Fundição 3:1 e o legado do save;
  - o `T2_RECIPES` e o `T2_TABS`;
  - o `bench_reads`;
  - o `ONCE_ITEMS` e o `"made"`, sem save novo;
  - o wafer fora da logística;
  - os objetivos;
  - o simulador congelado;
  - os testes e os prints.

  No bullet "Item de uma vez só" da seção de decisões do M5, troque "Save novo grava a lista; save antigo é marcado no load procurando esses itens..." por "Sem save novo: usa o `crafted` (já salvo) + inventário/equipamento".

- [ ] **Step 3:** `uv run pytest -q` → verde. Relatório final pro gerente: arquivos mexidos, testes antigos alterados (e por quê), prints gerados, e qualquer coisa que travou ou ficou estranha.
