# v0.6 Fundo · Marco 3 · Fundição · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** entra a **Fundição** (key `smelter`), a primeira máquina de processamento. Ela recebe minério (ferro ou cobre) e queima magmatita como combustível pra produzir lingote (`iron_ingot` ou `copper_ingot`, este último um item novo). Os **fios** passam a sair do fabricador a partir do lingote de cobre. A Fundição entra na rede dos drones com chip.

**Arquitetura:** a Fundição é uma cópia do molde do **derretedor** (`is_melter`, `_update_melter`, `melter_put`, `_melter_panel`, modo `"melter"` no App). A diferença é que ela tem 3 slots, um combustível que dura 4 fundições e uma saída que depende do minério. Cada ponto em que o derretedor encosta ganha o ramo equivalente da Fundição, sem tentar generalizar as duas máquinas numa abstração (YAGNI: são duas e se comportam diferente). A arte e o som chegam depois, com o Designer e o Som. Até lá fica o fallback do `game/art.py` e o silêncio.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-v06-fundo-design.md`, seção "M3 · Fundição". Bíblia §15 (bullet "Fundição").

## Restrições globais
- **Nome no jogo: "Fundição"** (feminino), key interna `smelter`. A palavra "fornalha" não aparece em lugar nenhum.
- **Partida** (balanceamento depois, regra do dono):
  - custo: 15 ferro + 6 silício + 4 magmatita;
  - libera em **Ti 10.000**, na aba **Automação** do construtor;
  - consome **2 kW**;
  - **15 s por lingote**, vezes o fator da energia;
  - **1 magmatita a cada 4 fundições**;
  - **1 minério vira 1 lingote**.
- **Fios**: no fabricador T1, 1 `copper_ingot` vira **3** `wire`. Libera em Ti 0, porque a trava real é ter cobre.
- **Save continua v12.** Os campos novos (`fuel` e o inventário de 3 slots) só aparecem em máquina nova, e save sem Fundição carrega igual. Não tem migração.
- Não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` e `settings.json`. A arte e o som são do Designer e do Som. Sem PNG, o jogo desenha o fallback; sem WAV, fica em silêncio.
- **Sem cena nova no smoke** (regra do dono). O print avulso do painel fica em `tools/dev/shot_v06_fundo_m3.py` (Task 3).
- Não abrir janela e não commitar. No fim: `uv run pytest`, `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py`. O smoke reescreve `reports/dev/`; só os prints do `shot_v06_fundo_m3` interessam, então rode `git checkout -- reports/dev` e depois rode o shot de novo.

## Decisões (o dono deveria ver)
- **1 minério → 1 lingote.** A spec não dizia; é número de partida.
- **A magmatita é gasta no começo da fundição.** Quando a carga acaba (`fuel == 0`) e começa um lingote novo, a Fundição tira 1 magmatita do slot e a carga vira 4. Cada lingote pronto gasta 1 da carga. Sem minério ou com a saída travada, ela não gasta nada. A carga que sobrou vai no save e **se perde ao desmontar** (é fogo, não é item).
- **Saída travada:** com `iron_ingot` na saída e cobre na entrada, a fundição para e o status mostra "SAÍDA OCUPADA". Ela não mistura nem troca sozinha. O progresso fica guardado.
- **A luz** é laranja como a do aquecedor e só acende **enquanto funde**, porque fundição apagada parece desligada.
- **Os lingotes entram na logística** (`LOGISTIC_ITEMS` ganha `iron_ingot` e `copper_ingot`). Com isso, o baú também pode Enviar e Receber lingote, e o painel do baú passa de 6 pra 8 toggles por linha. O print da Task 3 confere se cabe.
- **Fios** ficam numa aba nova do fabricador, **"Materiais"**. O lingote de cobre não tem receita (só sai da Fundição) e, como o `iron_ingot`, empilha até 20.

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | bloco "v0.6 Fundo M3": `MachineType("smelter")`, `SMELTER_*`, `copper_ingot`, `PART_ITEMS`, `POWER_USE`, `MACHINE_CATEGORY`, `MACHINE_FEMININE`, `LOGISTIC_ITEMS` com os lingotes, `CRAFT_TABS` com "Materiais", receita e `CRAFT_YIELD` dos fios |
| `game/inventory.py` | `max_stack` usa `C.PART_ITEMS` |
| `game/systems.py` | `Machine`: `fuel`, `is_smelter`, `smelter_output`, inventário de 3 slots, `is_logistic`/`needs_chip`; `GameState`: `_update_smelter`, `smelter_put`, `nearby_smelter`, `in_reach`/`interaction`/`interactable_at`, `dismantle_returns`, `craft` com `CRAFT_YIELD` |
| `game/drones.py` | `can_send`, `can_receive`, `receive_slot` da Fundição |
| `game/save.py` | `smelter_storage`, `timer` e `fuel` em `machine_to_dict`/`machine_from_dict` |
| `game/app.py` | modo `"smelter"`, `open_smelter`, E abre, `panel_refusal`, `smelter_status`, texto do hover e do prompt, "pegar tudo" |
| `game/ui.py` | `_smelter_panel` e o ramo em `_side_panels` |
| `game/art.py` | `_smelter` (fallback 40×58) em `_MACHINE_PAINTERS` e a chama em `machine_anim` |
| `game/render.py` | luz da Fundição (superfície e caverna) só enquanto funde; ícone do `copper_ingot` pelo `_m4_icon` |
| `tools/dev/shot_v06_fundo_m3.py` (novo) | prints do painel da Fundição (3 estados) e do painel do baú com 8 toggles |
| `docs/GAME_BIBLE.md` | §15 "Marco 3 · como ficou" |
| `tests/test_smelter.py` (novo) | máquina, produção, combustível, energia, logística, save, desmonte, painel |
| `tests/test_fabricator.py` | aba Materiais e o rendimento dos fios |

---

### Task 1: A Fundição como máquina (config, modelo e produção)

**Files:**
- Modify: `game/config.py` (bloco novo, logo depois do bloco do derretedor, por volta da linha 282; o `MACHINE_ORDER` e as categorias vão depois que eles existirem, no fim do bloco das abas, por volta da linha 615)
- Modify: `game/inventory.py:23-29`
- Modify: `game/systems.py` (`Machine`, linhas ~70-200; `_update_machines`, ~1518; `_update_smelter` novo, ao lado do `_update_melter`, ~1355)
- Test: `tests/test_smelter.py` (novo)

**Interfaces:**
- Produz: `C.SMELTER = "smelter"`, `C.SMELTER_ORE_SLOT, C.SMELTER_FUEL_SLOT, C.SMELTER_OUT_SLOT = 0, 1, 2`, `C.SMELTER_SLOTS = 3`, `C.SMELTER_TIME = 15.0`, `C.SMELTER_BURNS_PER_FUEL = 4`, `C.SMELTER_FUEL = "magmatite"`, `C.SMELTER_RECIPES = {"iron": "iron_ingot", "copper": "copper_ingot"}`, `C.SMELTER_REACH = 56`, `C.PART_ITEMS`
- Produz: `Machine.fuel: int`, `Machine.is_smelter`, `Machine.smelter_output -> str | None` (o lingote do minério da entrada), `Machine.smelter_blocker -> str | None` (`"no_ore"`, `"no_fuel"`, `"out_busy"`, `"out_full"` ou `None` = funde), `GameState._update_smelter(m, dt)`

- [ ] **Step 1: Escrever os testes que falham**

```python
"""v0.6 Fundo M3: Fundição (minério + magmatita → lingote)."""

import random

import pytest

from game import config as C
from game.inventory import Stack, max_stack
from game.systems import GameState, Machine


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add_smelter(game, tile=(64, 70), ore=None, fuel_items=0, out=None, fuel=0, sends=("iron_ingot", "copper_ingot"),
                receives=(), chip=True) -> Machine:
    """Fundição na rede (com chip, por padrão). `ore`/`out` = (item, n); `fuel_items` = magmatita no slot."""
    m = Machine("smelter", *tile, sends=set(sends), receives=set(receives), chip=chip)
    if ore:
        m.storage.slots[C.SMELTER_ORE_SLOT] = Stack(*ore)
    if fuel_items:
        m.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", fuel_items)
    if out:
        m.storage.slots[C.SMELTER_OUT_SLOT] = Stack(*out)
    m.fuel = fuel
    game.machines.append(m)
    return m


def run(game, seconds, step=1 / 30):
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def test_registered_as_machine():
    t = C.MACHINES["smelter"]
    assert t.name == "Fundição" and t.placeable and t.index is None
    assert t.cost == {"iron": 15, "silicon": 6, "magmatite": 4} and t.unlock_ti == 10_000
    assert C.MACHINE_CATEGORY["smelter"] == "automation" and C.POWER_USE["smelter"] == 2
    assert "smelter" in C.MACHINE_ORDER and "smelter" in C.MACHINE_FEMININE


def test_copper_ingot_is_an_item_that_stacks_like_parts():
    item = C.MACHINES["copper_ingot"]
    assert item.name == "Lingote de cobre" and not item.placeable and item.sprite == "icon_copper_ingot"
    assert max_stack("copper_ingot") == max_stack("iron_ingot") == C.STACK_LOOT
    assert "copper_ingot" not in C.LOOT_COMMON and "copper_ingot" not in C.LOOT_CONTAINER   # não cai de loot


def test_three_slots_and_needs_chip():
    m = Machine("smelter", 5, 5)
    assert len(m.storage) == C.SMELTER_SLOTS and m.is_smelter and m.is_logistic and m.needs_chip
    assert not m.in_network and m.fuel == 0


def test_smelts_iron_and_burns_one_magmatite_per_four(game):
    m = add_smelter(game, ore=("iron", 10), fuel_items=2)
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("iron_ingot", 1)
    assert m.storage.count("magmatite") == 1 and m.fuel == C.SMELTER_BURNS_PER_FUEL - 1
    run(game, C.SMELTER_TIME * 4)
    assert m.storage.count("iron_ingot") == 5 and m.storage.count("iron") == 5
    assert m.storage.count("magmatite") == 0 and m.fuel == 3     # a 2ª magmatita acendeu no 5º lingote


def test_copper_makes_copper_ingot(game):
    m = add_smelter(game, ore=("copper", 3), fuel_items=1)
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("copper_ingot", 1)


def test_stops_without_fuel_and_keeps_progress(game):
    m = add_smelter(game, ore=("iron", 5), fuel=1)
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.count("iron_ingot") == 1 and m.fuel == 0
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("iron_ingot") == 1 and m.storage.count("iron") == 4   # parou: sem magmatita
    assert m.smelter_blocker == "no_fuel"


def test_does_not_burn_without_ore(game):
    m = add_smelter(game, fuel_items=3)
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("magmatite") == 3 and m.fuel == 0 and m.smelter_blocker == "no_ore"


def test_output_busy_with_other_ingot_stops(game):
    m = add_smelter(game, ore=("copper", 5), fuel_items=2, out=("iron_ingot", 3))
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("copper") == 5 and m.storage.count("magmatite") == 2
    assert m.smelter_blocker == "out_busy"


def test_output_full_stops(game):
    m = add_smelter(game, ore=("iron", 5), fuel_items=2, out=("iron_ingot", max_stack("iron_ingot")))
    run(game, C.SMELTER_TIME * 2)
    assert m.storage.count("iron") == 5 and m.smelter_blocker == "out_full"


def test_power_deficit_slows_it(game):
    m = add_smelter(game, ore=("iron", 5), fuel_items=1)
    game.power.factor = 0.5                       # ver como o test_melter força o déficit, se o factor for derivado
    run(game, C.SMELTER_TIME + 0.5)
    assert m.storage.count("iron_ingot") == 0
```

Antes de rodar, veja como `tests/test_melter.py` e `tests/test_energy*.py` forçam o déficit de energia. Se `power.factor` for calculado (property) e não um campo, troque a linha do `test_power_deficit_slows_it` pela forma que esses testes usam (por exemplo, encher a camada de máquinas que consomem). Não invente um setter só pro teste.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_smelter.py -v`
Esperado: FAIL com `KeyError: 'smelter'`.

- [ ] **Step 3: Config**

Em `game/config.py`, logo depois de `MELTER_REACH`:

```python
# ---------------------------------------------------------------------------
# v0.6 Fundo M3 · Fundição (bíblia §15, spec 2026-10-15-v06-fundo-design.md). Números de partida.
# Molde do derretedor: 3 slots, [0] minério (ferro/cobre), [1] combustível (só magmatita), [2] lingote. Uma magmatita
# acende uma carga de SMELTER_BURNS_PER_FUEL fundições (`Machine.fuel`), gasta no começo de um lingote. 1 minério = 1
# lingote a cada SMELTER_TIME s (× fator da energia). Saída com o outro lingote ou cheia: para, sem gastar nada.
# ---------------------------------------------------------------------------
SMELTER = "smelter"
SMELTER_ORE_SLOT, SMELTER_FUEL_SLOT, SMELTER_OUT_SLOT = 0, 1, 2
SMELTER_SLOTS = 3
SMELTER_TIME = 15.0
SMELTER_BURNS_PER_FUEL = 4
SMELTER_FUEL = "magmatite"
SMELTER_RECIPES = {"iron": "iron_ingot", "copper": "copper_ingot"}
SMELTER_REACH = MELTER_REACH
MACHINES[SMELTER] = MachineType(SMELTER, "Fundição", "minério → lingote", {"iron": 15, "silicon": 6, "magmatite": 4},
                                None, 0, 10_000, "machine_smelter")
```

Depois do `MACHINE_ORDER = list(MACHINES)` ela já entra na lista. Mova-a pra depois da `drone` (onde a `drone` é inserida, por volta da linha 590):

```python
MACHINE_ORDER.remove(SMELTER)
MACHINE_ORDER.insert(MACHINE_ORDER.index("drone") + 1, SMELTER)   # v0.6 Fundo M3: na Automação, depois dos drones
```

No `POWER_USE` (adicione depois do dict): `POWER_USE[SMELTER] = 2`. No `MACHINE_CATEGORY` (depois do dict): `MACHINE_CATEGORY[SMELTER] = "automation"`. No `MACHINE_FEMININE`, adicione `"smelter"`.

O lingote de cobre fica logo depois do `for _key, _name, _desc in ...` dos itens de loot:

```python
# v0.6 Fundo M3: lingote de cobre (só sai da Fundição; não cai de loot). Peças (loot + lingotes) empilham até STACK_LOOT.
MACHINES["copper_ingot"] = MachineType("copper_ingot", "Lingote de cobre", "sai da Fundição", {}, None, 0, 0,
                                       "icon_copper_ingot", placeable=False)
PART_ITEMS = LOOT_ITEMS + ("copper_ingot",)
```

Em `game/inventory.py`, no `max_stack`, troque `C.LOOT_ITEMS` por `C.PART_ITEMS` (e o comentário: "peças de loot e lingotes").

- [ ] **Step 4: Modelo e produção**

Em `game/systems.py`, no `Machine`:

```python
    # v0.6 Fundo M3: só a Fundição. Fundições que ainda restam da magmatita que está queimando (vai no save).
    fuel: int = field(default=0, compare=False)
```

No `__post_init__`, junto dos outros:

```python
        elif self.storage is None and self.is_smelter:
            self.storage = Inventory(C.SMELTER_SLOTS)
```

Propriedades novas (perto do `is_melter`):

```python
    @property
    def is_smelter(self) -> bool:
        """Fundição (v0.6 Fundo M3): minério + magmatita → lingote."""
        return self.kind == C.SMELTER

    @property
    def smelter_output(self) -> str | None:
        """Fundição: o lingote que o minério da entrada vira (None = entrada vazia)."""
        ore = self.storage.slots[C.SMELTER_ORE_SLOT] if self.is_smelter else None
        return C.SMELTER_RECIPES.get(ore.item) if ore else None

    @property
    def smelter_blocker(self) -> str | None:
        """Por que a Fundição não funde agora: "no_ore", "out_busy" (o outro lingote na saída), "out_full",
        "no_fuel"; None = fundindo."""
        ingot = self.smelter_output
        if ingot is None:
            return "no_ore"
        out = self.storage.slots[C.SMELTER_OUT_SLOT]
        if out is not None and out.item != ingot:
            return "out_busy"
        if out is not None and out.room <= 0:
            return "out_full"
        if self.fuel <= 0 and self.storage.count(C.SMELTER_FUEL) <= 0:
            return "no_fuel"
        return None
```

Em `is_logistic` e `needs_chip`, some `or self.is_smelter` (e atualize as docstrings: "drill, derretedor, Fundição e dispersor").

No `GameState`, ao lado do `_update_melter`:

```python
    def _update_smelter(self, smelter: Machine, dt: float) -> None:
        """Fundição (v0.6 Fundo M3): a cada SMELTER_TIME s, 1 minério da entrada vira 1 lingote na saída. A magmatita
        queima no começo de um lingote, quando a carga (`fuel`) acabou, e vale SMELTER_BURNS_PER_FUEL lingotes.
        Travada (sem minério, sem combustível, saída ocupada/cheia): para, guarda o progresso e não gasta nada."""
        while dt > 0 and smelter.smelter_blocker is None:
            if smelter.fuel <= 0:                       # acende a próxima magmatita
                smelter.storage.remove(C.SMELTER_FUEL, 1)
                smelter.fuel = C.SMELTER_BURNS_PER_FUEL
            left = C.SMELTER_TIME - smelter.timer
            if dt < left:
                smelter.timer += dt
                return
            dt -= left
            smelter.timer = 0.0
            ingot = smelter.smelter_output
            smelter.storage.remove(smelter.storage.slots[C.SMELTER_ORE_SLOT].item, 1)
            smelter.fuel -= 1
            out = smelter.storage.slots[C.SMELTER_OUT_SLOT]
            if out is None:
                smelter.storage.slots[C.SMELTER_OUT_SLOT] = Stack(ingot, 1)
            else:
                out.count += 1
```

Atenção: `Inventory.remove(item, n)` tira de qualquer slot. Cobre e magmatita só ficam nos slots deles (as regras de entrada das Tasks 2 e 3 garantem isso), então tudo bem. Confira o nome do método que tira do inventário no `game/inventory.py` antes de usar.

Em `_update_machines`, depois do `if m.is_melter: ...`:

```python
            if m.is_smelter:
                self._update_smelter(m, work_dt)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `uv run pytest tests/test_smelter.py -v` e depois `uv run pytest`
Esperado: tudo verde. Se algum teste antigo contar as máquinas da aba Automação ou o tamanho do `MACHINE_ORDER`, ajuste a contagem e anote no relatório.

---

### Task 2: Rede dos drones, save e desmonte

**Files:**
- Modify: `game/config.py` (`LOGISTIC_ITEMS`)
- Modify: `game/drones.py:220-250`
- Modify: `game/save.py:281-350`
- Modify: `game/systems.py` (`dismantle_returns`, ~1398)
- Test: `tests/test_smelter.py`

**Interfaces:**
- Consome: Task 1 (`is_smelter`, `fuel`, `SMELTER_*`)
- Produz: `drones.can_send/can_receive/receive_slot` com a Fundição; `save.smelter_storage(data) -> Inventory`

- [ ] **Step 1: Testes que falham** (adicionar ao `tests/test_smelter.py`)

```python
from game import drones, save


def test_logistic_items_include_ingots():
    assert "iron_ingot" in C.LOGISTIC_ITEMS and "copper_ingot" in C.LOGISTIC_ITEMS


def test_drones_rules():
    m = Machine("smelter", 5, 5)
    assert drones.can_receive(m, "iron") and drones.can_receive(m, "copper") and drones.can_receive(m, "magmatite")
    assert not drones.can_receive(m, "silicon") and not drones.can_receive(m, "iron_ingot")
    assert drones.can_send(m, "iron_ingot") and drones.can_send(m, "copper_ingot")
    assert not drones.can_send(m, "iron") and not drones.can_send(m, "magmatite")
    assert drones.receive_slot(m, "iron") == drones.receive_slot(m, "copper") == C.SMELTER_ORE_SLOT
    assert drones.receive_slot(m, "magmatite") == C.SMELTER_FUEL_SLOT


def test_deliver_ore_respects_other_ore_in_slot():
    m = Machine("smelter", 5, 5)
    m.storage.slots[C.SMELTER_ORE_SLOT] = Stack("iron", 4)
    assert drones.deliver(m, "copper", 5) == 5          # não mistura: o slot é do ferro
    assert drones.deliver(m, "iron", 5) == 0 and m.storage.count("iron") == 9
    assert drones.deliver(m, "magmatite", 3) == 0 and m.storage.slots[C.SMELTER_FUEL_SLOT] == Stack("magmatite", 3)


def test_save_roundtrip():
    m = Machine("smelter", 7, 8, sends={"copper_ingot"}, receives={"copper", "magmatite"}, chip=True)
    m.storage.slots[C.SMELTER_ORE_SLOT] = Stack("copper", 6)
    m.storage.slots[C.SMELTER_FUEL_SLOT] = Stack("magmatite", 2)
    m.storage.slots[C.SMELTER_OUT_SLOT] = Stack("copper_ingot", 3)
    m.fuel, m.timer = 2, 7.5
    back = save.machine_from_dict(save.machine_to_dict(m))
    assert back.storage.slots == m.storage.slots and back.fuel == 2 and back.timer == 7.5
    assert back.sends == {"copper_ingot"} and back.receives == {"copper", "magmatite"} and back.chip


def test_save_cleans_bad_slots():
    data = {"kind": "smelter", "tx": 1, "ty": 1, "rotation": 0, "timer": 99, "fuel": 99,
            "storage": [["silicon", 5], ["iron", 3], ["iron_ingot", 2]]}
    m = save.machine_from_dict(data)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] is None and m.storage.slots[C.SMELTER_FUEL_SLOT] is None
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("iron_ingot", 2)
    assert m.timer == C.SMELTER_TIME and m.fuel == C.SMELTER_BURNS_PER_FUEL


def test_dismantle_returns_contents_but_not_burning_fuel(game):
    m = add_smelter(game, ore=("iron", 3), fuel_items=2, out=("iron_ingot", 4), fuel=3)
    out = game.dismantle_returns(m)
    assert out["iron"] == 15 + 3 and out["magmatite"] == 4 + 2 and out["iron_ingot"] == 4 and out["chip"] == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_smelter.py -v`

- [ ] **Step 3: Implementar**

`game/config.py`:

```python
LOGISTIC_ITEMS = RESOURCES + ("water_capsule", "iron_ingot", "copper_ingot")   # v0.6 Fundo M3: os lingotes da Fundição
```

`game/drones.py`:
- `can_send`: `if machine.is_smelter: return item in C.SMELTER_RECIPES.values()`
- `can_receive`: `if machine.is_smelter: return item in C.SMELTER_RECIPES or item == C.SMELTER_FUEL`
- `receive_slot`: minério da receita → `C.SMELTER_ORE_SLOT`; `C.SMELTER_FUEL` → `C.SMELTER_FUEL_SLOT`.

O `slot_room` já devolve 0 quando o slot tem outro item, então o "não mistura" sai de graça. Atualize as docstrings.

`game/save.py`:

```python
def smelter_storage(data: list) -> Inventory:
    """Inventário da Fundição do save: [0] minério da receita, [1] magmatita, [2] lingote (outra coisa vira vazio)."""
    inv = Inventory(C.SMELTER_SLOTS)
    allowed = {C.SMELTER_ORE_SLOT: set(C.SMELTER_RECIPES), C.SMELTER_FUEL_SLOT: {C.SMELTER_FUEL},
               C.SMELTER_OUT_SLOT: set(C.SMELTER_RECIPES.values())}
    for slot, items in allowed.items():
        d = data[slot] if slot < len(data) else None
        if d and d[0] in items and int(d[1]) > 0:
            inv.slots[slot] = Stack(d[0], min(int(d[1]), max_stack(d[0])))
    return inv
```

- `machine_to_dict`: `if m.is_smelter: data.update(timer=m.timer, fuel=m.fuel)`. O `storage` já vai pelo ramo `is_logistic`.
- `machine_from_dict`, depois do bloco do derretedor:

```python
    if machine.is_smelter:
        machine.storage = smelter_storage(data.get("storage", []))
        machine.timer = min(max(machine.timer, 0.0), C.SMELTER_TIME)
        machine.fuel = min(max(int(data.get("fuel", 0)), 0), C.SMELTER_BURNS_PER_FUEL)
```

Confira se o ramo `is_logistic` do `machine_from_dict` **não sobrescreve** o `storage` depois (no derretedor não sobrescreve; garanta que a ordem fique igual). Atualize o docstring de formato no topo do `save.py` (linha ~50) com um exemplo da Fundição.

`game/systems.py`, `dismantle_returns`: troque `if machine.is_melter or machine.is_dispenser:` por `if machine.is_melter or machine.is_dispenser or machine.is_smelter:`. A carga `fuel` não volta.

- [ ] **Step 4: Rodar tudo**

Run: `uv run pytest`
Esperado: verde. Se um teste antigo de logística, save ou painel de baú contar o `LOGISTIC_ITEMS` (6 itens), ajuste pra 8 e anote no relatório.

---

### Task 3: Interface (E abre, painel, avisos, arte de fallback, luz) e o print avulso

**Files:**
- Modify: `game/systems.py` (`nearby_smelter`, `in_reach`, `interaction`, `interactable_at`, `smelter_put`)
- Modify: `game/app.py` (modos, `open_smelter`, E, `panel_refusal`, `smelter_status`, hover, prompt, "pegar tudo", som de abrir)
- Modify: `game/ui.py` (`_smelter_panel`, `_side_panels`)
- Modify: `game/art.py` (`_smelter`, `_MACHINE_PAINTERS`, `machine_anim`)
- Modify: `game/render.py` (luz da Fundição; `copper_ingot` no ramo do `_m4_icon`)
- Create: `tools/dev/shot_v06_fundo_m3.py`
- Test: `tests/test_smelter.py`, `tests/test_panel_cursor.py`

**Interfaces:**
- Consome: Tasks 1 e 2
- Produz: `GameState.nearby_smelter() -> Machine | None`, `GameState.smelter_put(smelter, index, amount=None) -> int`, `App.open_smelter`, modo `"smelter"`, `App.smelter_status() -> str`

**Como fazer:** pra cada ocorrência de `melter` em `game/app.py`, `game/ui.py`, `game/systems.py` (`nearby_melter`, `in_reach`, `interaction`, `interactable_at`, `melter_put`) e `game/render.py` (luzes), crie o ramo equivalente `smelter` logo abaixo. Faça a lista com `grep -n "melter" game/app.py game/ui.py game/systems.py game/render.py` e trate cada linha. As diferenças:

- `smelter_put(smelter, index, amount)`: o item da pilha decide o slot. Minério da receita vai pro `SMELTER_ORE_SLOT`, só se o slot estiver vazio ou com o mesmo minério. Magmatita vai pro `SMELTER_FUEL_SLOT`. Qualquer outra coisa devolve 0.
- `panel_refusal`, quando o inventário é o da Fundição aberta:
  - slot 0 aceita ferro ou cobre;
  - slot 1 aceita magmatita;
  - slot 2 não aceita nada (só tira);
  - o texto é `"A Fundição só aceita ferro, cobre e magmatita"`;
  - pro minério diferente do que já está no slot 0, o texto é `"Tire o minério que está na Fundição antes"`.
- `smelter_status()`: `"SEM MINÉRIO"`, `"SEM MAGMATITA"`, `"SAÍDA OCUPADA"`, `"SAÍDA CHEIA"` (pelo `smelter_blocker`). Fundindo, `f"1 A CADA {C.SMELTER_TIME:g} S"`, mais `" · RITMO {p}%"` no déficit, igual ao `melter_status`.
- Hover: `f"Fundição: {minério} {nome} · {magmatita} magmatita · {lingotes} lingote(s)"`, com `" · [E] abrir"` como no derretedor. Prompt do E: `"[E] Abrir Fundição"`.
- `_smelter_panel` (no lugar do `_melter_panel`):
  - título `"Fundição"`, contador à direita `f"{lingotes} ling."`, cor de destaque laranja `"#ff8a3d"`;
  - três slots em linha: `MINÉRIO` (0), `MAGMATITA` (1), `>`, `LINGOTE` (2);
  - barra do lingote atual (`timer / SMELTER_TIME` enquanto `smelter_blocker is None`) e, embaixo, 4 pontinhos da carga (`fuel` acesos de 4);
  - texto de ajuda: `"Clique no minério e na magmatita pra pôr. Drones levam os lingotes."`;
  - botão `"<<\nPEGAR\nTUDO"` com a ação `"take_smelter"`;
  - `draw_logistics` igual ao do derretedor.
  - Se 3 slots e a barra não couberem na largura `GRID_W`, ponha a barra e o status numa linha embaixo dos slots e ajuste a altura no `_side_panels`. O print decide.
- `"take_smelter"` faz o mesmo que o `"take_melter"`: tira o que couber de todos os slots.
- `art._smelter(s, ox, oy)`: um bloco de pedra/metal escuro 32×~34, com boca de forno na frente (retângulo `#1a1418`) e uma chaminé curta. Registre em `_MACHINE_PAINTERS`. O `machine_anim` desenha a brasa piscando na boca (como o `heater`). É só o fallback até o Designer entregar o `machine_smelter.png`.
- Luz: `MACHINE_LIGHT["smelter"] = (255, 138, 61)` (caverna) e `"smelter": ((255, 138, 61), 90, -22, 0.26)` no `machine_light` da superfície. As duas **só enquanto `m.smelter_blocker is None`**. Siga o `continue` da drill como modelo.
- Ícone: em `render.item_icon`, troque `item in C.LOOT_ITEMS` por `item in C.PART_ITEMS`. O `_m4_icon` já cai no `icon_{item}` ou no quadradinho de placeholder.
- Som: `ui_open` ao abrir, como os outros painéis (inclua `"smelter"` na tupla da linha ~1534 do App). O loop da Fundição **não** entra neste plano.

- [ ] **Step 1: Testes que falham** (`tests/test_smelter.py`)

```python
def test_smelter_put_routes_by_item(game):
    m = add_smelter(game)
    game.inventory.slots[0] = Stack("copper", 10)
    game.inventory.slots[1] = Stack("magmatite", 4)
    game.inventory.slots[2] = Stack("iron", 5)
    assert game.smelter_put(m, 0) == 10 and m.storage.slots[C.SMELTER_ORE_SLOT] == Stack("copper", 10)
    assert game.smelter_put(m, 1, 1) == 1 and m.storage.slots[C.SMELTER_FUEL_SLOT] == Stack("magmatite", 1)
    assert game.smelter_put(m, 2) == 0                    # ferro com cobre na entrada: não mistura


def test_interaction_opens_smelter(game):
    m = add_smelter(game, tile=(int(game.player.x // C.TILE), int(game.player.y // C.TILE) - 2))
    assert game.nearby_smelter() is m
    assert game.interactable_at(m.anchor[0], m.anchor[1] - 8) == ("smelter", m)
```

E em `tests/test_panel_cursor.py`, um teste no modelo do derretedor (linhas ~140-160): abrir a Fundição, mostrar que o ferro entra no slot 0, a magmatita no 1, que a saída recusa e que o cobre com ferro no slot recusa.

Se a posição do `test_interaction_opens_smelter` não bater com o `drill_distance`, use o mesmo jeito de posicionar que o `test_melter.py`/`test_panel_cursor.py` usa pro derretedor.

- [ ] **Step 2: Rodar e ver falhar.** Run: `uv run pytest tests/test_smelter.py tests/test_panel_cursor.py -v`

- [ ] **Step 3: Implementar** seguindo a lista acima.

- [ ] **Step 4: Print avulso** `tools/dev/shot_v06_fundo_m3.py`, no modelo do `tools/dev/shot_v06_fundo_m2.py` (janela escondida/dummy, mesmo jeito de montar `App`). Ele salva em `reports/dev/v06_fundo_m3/`:
  - `smelter_working.png`: painel aberto com ferro, magmatita, 2 lingotes e a barra no meio;
  - `smelter_no_fuel.png`: status "SEM MAGMATITA";
  - `smelter_out_busy.png`: lingote de ferro na saída e cobre na entrada;
  - `chest_logistics.png`: painel do baú com os 8 toggles da seção DRONES (confere se os lingotes cabem na linha);
  - `smelter_world.png`: a Fundição de fallback no chão da superfície, acesa, ao lado de um derretedor (escala de referência).

Olhe os 5 prints. Se algo sair do painel ou cortar texto, corrija antes de seguir.

- [ ] **Step 5: Rodar tudo.** Run: `uv run pytest` (verde).

---

### Task 4: Fios no fabricador (aba Materiais, 1 lingote de cobre → 3 fios)

**Files:**
- Modify: `game/config.py` (`CRAFT_TABS`, receita do `wire`, `CRAFT_YIELD`)
- Modify: `game/systems.py:704-760` (`craft` e `craft_many` respeitam o rendimento)
- Modify: `game/ui.py` (o detalhe da receita mostra "×3" quando o rendimento > 1; procure onde o painel de detalhe desenha o nome/custo)
- Test: `tests/test_fabricator.py`

**Interfaces:**
- Produz: `C.CRAFT_YIELD: dict[str, int]` (item → quantos saem por fabricação; ausente = 1)

- [ ] **Step 1: Testes que falham**

```python
def test_wire_recipe_in_materials_tab():
    assert ("materials", "Materiais") in C.CRAFT_TABS
    assert C.MACHINES["wire"].cost == {"copper_ingot": 1} and C.CRAFT_YIELD["wire"] == 3
    assert "wire" in fabricator.craft_kinds("materials")


def test_crafting_wire_gives_three(game_in_base):
    g = game_in_base
    g.inventory.add("copper_ingot", 2)
    assert g.craft("wire")
    assert g.inventory.count("wire") == 3 and g.inventory.count("copper_ingot") == 1
```

Use a fixture de "player na base" que o `tests/test_fabricator.py` já tem (o `craft` exige `in_base_zone`). Se ela tiver outro nome, adapte.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**
  - `CRAFT_TABS = (("tools", "Ferramentas"), ("automation", "Automação"), ("materials", "Materiais"), ("suit", "Traje"))`. Confira que o `FAB_TABS` do construtor não ganha a aba nova: ele é derivado de outro tuple, mas confirme.
  - Depois do bloco do lingote de cobre: `MACHINES["wire"] = _replace(MACHINES["wire"], cost={"copper_ingot": 1}, desc="1 lingote de cobre → 3")`, `MACHINE_ORDER.append("wire")`, `MACHINE_CATEGORY["wire"] = "materials"`, `CRAFT_YIELD = {"wire": 3}`. O `MACHINE_ORDER` e o `MACHINE_CATEGORY` precisam já existir nesse ponto; se não existirem, mova as linhas pra depois do bloco das abas.
  - `craft`: troque `trial.has_space(kind)` / `self.inventory.add(kind, 1)` pelo rendimento `n = C.CRAFT_YIELD.get(kind, 1)`. O teste de espaço precisa caber `n`: use `trial.add(kind, n) == 0` numa cópia, ou o equivalente que o `Inventory` oferecer. `self.crafted[kind] += 1` continua contando fabricações.
  - UI: no detalhe da receita, `"Fios ×3"` quando `CRAFT_YIELD > 1`.
  - Os fios continuam caindo de loot (não mexer em `LOOT_*`).

- [ ] **Step 4: Rodar tudo.** Run: `uv run pytest` (verde). Se algum teste antigo contar as abas do fabricador (3), ajuste pra 4.

---

### Task 5: Bíblia e validação final

- [ ] **Step 1:** em `docs/GAME_BIBLE.md` §15, depois do "Marco 2 · como ficou", crie **"### Marco 3 · como ficou na implementação"**. Mesmo estilo das outras seções: arquivos, números (`SMELTER_*`), slots, regra do combustível, saída travada, logística, save, fios e a aba Materiais, luz só fundindo, fallback de arte e som pendentes.
- [ ] **Step 2:** `uv run pytest`, `uv run python tools/dev/smoke.py`, `uv run python tools/dev/real_video_check.py`. Depois `git checkout -- reports/dev` e `uv run python tools/dev/shot_v06_fundo_m3.py` (os prints novos ficam).
- [ ] **Step 3:** relatório pro gerente:
  - o que mudou;
  - números do pytest e do smoke (média e p95);
  - os testes antigos que foram ajustados, e por quê;
  - caminho dos prints;
  - qualquer decisão tomada fora do plano.
