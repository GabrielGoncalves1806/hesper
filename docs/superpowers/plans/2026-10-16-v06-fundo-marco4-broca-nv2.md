# v0.6 Fundo · Marco 4 · Broca nv.2 · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** entra a **broca de mão nv.2** (`hand_drill_t2`), feita na Bancada T2 a partir da nv.1 (que é consumida). Ela minera tudo ×1,5 e quebra rocha dura. Pra ela sair sem depender de loot, a **Fundição passa a fundir silício → wafer** e o **circuito** vira receita do fabricador (aba Materiais).

**Arquitetura:** a "broca na mão" deixa de ser um `bool` e passa a ter nível: o App manda `Controls.drill_tier` (1 ou 2) junto do `drill_in_hand`, e o `GameState` guarda isso em `self.drill_tier` a cada `update`. O `can_break_hard` e o `mine_speed` leem esse nível. Todo lugar que hoje pergunta `== C.HAND_DRILL` passa a perguntar `in C.HAND_DRILLS` (as duas brocas). O wafer é só uma entrada nova no `C.SMELTER_RECIPES`, que já guia slots, drones e save. O circuito segue o molde dos fios (`MACHINES[...] = _replace(...)`, aba `materials`).

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-v06-fundo-design.md`, seção "M4 · Broca nv.2". Bíblia §15 (bullets "Broca nv.2" e "Wafer e circuito fabricáveis", já atualizados pelo gerente).

## Restrições globais
- **Números de partida** (balanceamento depois, regra do dono):
  - receita da nv.2 na **Bancada T2**: `{"hand_drill": 1, "iron_ingot": 2, "wire": 4, "circuit": 1}`, liberada em Ti 0;
  - mineração com a nv.2: **×1,5** (`C.HAND_DRILL_T2_SPEED = 1.5`), mesmo alcance (`C.MINE_REACH`);
  - rocha dura com a nv.2: **~1,5 s** → `C.MINE_TIME[C.HARD_ROCK]` passa de 1,5 pra **2,25** (2,25 / 1,5 = 1,5 s);
  - Fundição: **1 silício → 1 wafer**, mesmo `SMELTER_TIME` e mesma magmatita;
  - circuito no fabricador, aba Materiais: **1 `silicon_wafer` + 2 `wire` → 1 `circuit`**, Ti 0.
- **Nome no jogo**: "Broca de mão nv.2", descrição "minera ×1,5 e quebra rocha dura". Categoria FERRAMENTA, não empilha (stack 1).
- **Bedrock continua inquebrável.** A nv.1 continua sem quebrar rocha dura. O F3 continua quebrando (e multiplica junto: F3 + nv.2 = `DEBUG_MINE × 1,5`).
- **Save continua v12.** O item novo é só uma string no inventário; não tem migração. O `ensure_hand_drill` não pode dar uma nv.1 a quem já tem a nv.2.
- Não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` e `settings.json`. O ícone `icon_hand_drill_t2.png` (e o novo `icon_hand_drill.png`) vêm do Designer; sem o PNG, a nv.2 usa o mesmo fallback da nv.1.
- **Sem cena nova no smoke** (regra do dono). Prints avulsos em `tools/dev/shot_v06_fundo_m4.py` (Task 3).
- Não abrir janela e não commitar. No fim: `uv run pytest`. O gerente roda smoke e `real_video_check` no merge.

## Decisões (o dono deveria ver)
- **A nv.2 nasce no slot da nv.1.** Se a nv.1 estava no slot 3 da hotbar, a nv.2 sai no slot 3 (o player não perde a broca de vista). Feito por `C.CRAFT_REPLACES = {"hand_drill_t2": "hand_drill"}`.
- **A broca no `cost`**: a nv.1 entra na receita como ingrediente normal. Como a T2 gasta só o inventário, a nv.1 guardada num baú não conta.
- **Rocha dura subiu pra 2,25 s de base** pra fechar em ~1,5 s com a nv.2. O minério de parede dentro do gelo e do basalto continua com o tempo do minério (ferro 1,0 s → ~0,67 s com a nv.2).
- **A nv.2 na mão do player usa o mesmo sprite da nv.1** (`drill_side/up/down`). Só os ícones são novos.
- **O slot de saída da Fundição vira "SAÍDA"** (era "LINGOTE"), já que o wafer não é lingote. O título mostra `"{n} ling."` → passa a `"{n} prontos"`.
- **O wafer entra no `LOGISTIC_ITEMS`**: baú com **9** toggles. O print confere se cabe; se não couber, o Dev para e avisa o gerente (não redesenha o painel: o modal de itens está no Futuro do ROADMAP).

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | bloco "v0.6 Fundo M4": `HAND_DRILL_T2`, `HAND_DRILLS`, `HAND_DRILL_T2_SPEED`, `MachineType` da nv.2, `T2_RECIPES`, `CRAFT_REPLACES`, `MINE_TIME[HARD_ROCK]`, `SMELTER_RECIPES["silicon"]`, `LOGISTIC_ITEMS` com o wafer, receita do circuito, descrições de wafer e circuito |
| `game/inventory.py` | `max_stack` usa `C.HAND_DRILLS` |
| `game/systems.py` | `Controls.drill_tier`, `GameState.drill_tier`, `can_break_hard`, `mine_speed`, `ensure_hand_drill`, `craft` com `CRAFT_REPLACES` |
| `game/app.py` | `hand_drill_selected` aceita as duas, `held_drill_tier`, `Controls(drill_tier=...)`, recusa da Fundição com silício |
| `game/ui.py` | `item_category` das duas brocas; rótulo "SAÍDA" e título da Fundição |
| `game/render.py` | ícone da nv.2 no `_m4_icon` e nos dois ramos que chamam ele |
| `tools/dev/shot_v06_fundo_m4.py` (novo) | prints: T2 com a receita da nv.2, fabricador Materiais com o circuito, Fundição com wafer, baú com 9 toggles, hover de rocha dura com a nv.1 e a nv.2 |
| `docs/GAME_BIBLE.md` | §15 "Marco 4 · como ficou" |
| `tests/test_drill_t2.py` (novo) | item, receita, slot, mineração, rocha dura, save, ensure |
| `tests/test_smelter.py` | wafer na Fundição e na logística |
| `tests/test_fabricator.py` | circuito na aba Materiais |

---

### Task 1: A nv.2 como item e receita da T2

**Files:**
- Modify: `game/config.py` (bloco novo "v0.6 Fundo M4" logo depois da linha `T2_RECIPES` (~1070); mais nada no bloco do M4 da v0.5)
- Modify: `game/inventory.py:23-29`
- Modify: `game/systems.py` (`craft`, ~735; `ensure_hand_drill`, ~1978)
- Modify: `game/ui.py:330` (`item_category`)
- Modify: `game/render.py:1838`, `:1863-1869`, `:1895` (ícone)
- Test: `tests/test_drill_t2.py` (novo)

**Interfaces:**
- Produz: `C.HAND_DRILL_T2 = "hand_drill_t2"`, `C.HAND_DRILLS = (C.HAND_DRILL, C.HAND_DRILL_T2)`, `C.HAND_DRILL_T2_SPEED = 1.5`, `C.CRAFT_REPLACES: dict[str, str]`, `C.T2_RECIPES` com `"hand_drill_t2"` no fim.

- [ ] **Step 1: Escrever os testes que falham** (`tests/test_drill_t2.py`)

```python
"""v0.6 Fundo M4: broca de mão nv.2 (item, receita na T2, nasce no slot da nv.1, mineração ×1,5, rocha dura)."""

import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import config as C  # noqa: E402
from game.inventory import Stack, max_stack  # noqa: E402
from game.systems import GameState  # noqa: E402
from tests.helpers import give  # noqa: E402

T2_COST = {"hand_drill": 1, "iron_ingot": 2, "wire": 4, "circuit": 1}


def game() -> GameState:
    return GameState(rng=random.Random(1))


def ready_to_craft(g: GameState) -> None:
    give(g, iron_ingot=2, wire=4, circuit=1)          # a nv.1 já vem no slot 0


def test_item_registered():
    m = C.MACHINES[C.HAND_DRILL_T2]
    assert C.HAND_DRILL_T2 == "hand_drill_t2"
    assert m.name == "Broca de mão nv.2" and not m.placeable
    assert m.cost == T2_COST and m.unlock_ti == 0
    assert C.HAND_DRILLS == ("hand_drill", "hand_drill_t2")
    assert C.T2_RECIPES[-1] == "hand_drill_t2"
    assert max_stack("hand_drill_t2") == 1
    assert C.HAND_DRILL_T2 not in C.MACHINE_ORDER


def test_crafting_consumes_t1_and_lands_in_its_slot():
    g = game()
    g.inventory.swap(0, 3)                             # a nv.1 no slot 3
    ready_to_craft(g)
    assert g.craft("hand_drill_t2", bench="t2")
    assert g.inventory.count("hand_drill") == 0
    assert g.inventory.slots[3] == Stack("hand_drill_t2", 1)
    assert g.inventory.count("iron_ingot") == 0 and g.inventory.count("wire") == 0
    assert g.inventory.count("circuit") == 0


def test_needs_t1_in_inventory():
    g = game()
    g.inventory.remove("hand_drill", 1)
    ready_to_craft(g)
    assert g.recipe_status("hand_drill_t2", inv_only=True) == "missing"
    assert g.missing_resource("hand_drill_t2", inv_only=True) == "hand_drill"
    assert not g.craft("hand_drill_t2", bench="t2")


def test_not_in_t1_fabricator():
    g = game()
    ready_to_craft(g)
    assert not g.craft("hand_drill_t2")               # bench "t1": a receita é só da T2


def test_ensure_hand_drill_respects_t2():
    g = game()
    ready_to_craft(g)
    g.craft("hand_drill_t2", bench="t2")
    assert not g.ensure_hand_drill()                   # tem a nv.2: não ganha outra nv.1
    assert g.inventory.count("hand_drill") == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_drill_t2.py -v`
Expected: FAIL com `AttributeError: ... has no attribute 'HAND_DRILL_T2'`

- [ ] **Step 3: Config** (logo depois da linha `T2_RECIPES: tuple[str, ...] = ...` em `game/config.py`)

```python
# ---------------------------------------------------------------------------
# v0.6 Fundo M4 · Broca nv.2 (números de partida; balanceamento depois)
# ---------------------------------------------------------------------------
# Feita na Bancada T2 com a nv.1, que é consumida (a nv.1 no `cost`; a T2 gasta só o inventário). Minera ×1,5 e quebra
# rocha dura (GameState.can_break_hard / mine_speed, pelo Controls.drill_tier). Mesmo alcance, mesmo sprite na mão.
HAND_DRILL_T2 = "hand_drill_t2"
HAND_DRILLS = (HAND_DRILL, HAND_DRILL_T2)
HAND_DRILL_T2_SPEED = 1.5
MACHINES[HAND_DRILL_T2] = MachineType(HAND_DRILL_T2, "Broca de mão nv.2", "minera ×1,5 e quebra rocha dura",
                                      {HAND_DRILL: 1, "iron_ingot": 2, "wire": 4, "circuit": 1}, None, 0, 0,
                                      "icon_hand_drill_t2", placeable=False)
T2_RECIPES = T2_RECIPES + (HAND_DRILL_T2,)
CRAFT_REPLACES = {HAND_DRILL_T2: HAND_DRILL}   # o item novo nasce no slot do que foi consumido (a broca na hotbar)
```

Confira a assinatura do `MachineType` (argumentos posicionais do `HAND_DRILL` em `config.py:826`) e a do `unlock_ti` antes de colar. Atualize o comentário da linha do `T2_RECIPES` ("a broca nv.2 entra no M4" → "a broca nv.2 entra no bloco do M4, mais abaixo").

- [ ] **Step 4: Inventário, ensure e craft**

`game/inventory.py`:
```python
    if item in C.HAND_DRILLS:
        return C.STACK_TOOL                           # v0.5 M4: a broca de mão não empilha (v0.6 Fundo M4: nem a nv.2)
```

`game/systems.py`, `ensure_hand_drill`: troque as duas contagens de `C.HAND_DRILL` por "qualquer broca":
```python
        has = lambda inv: any(inv.count(d) for d in C.HAND_DRILLS)   # noqa: E731 (v0.6 Fundo M4: a nv.2 também vale)
        if has(self.inventory) or any(
                m.storage is not None and has(m.storage)
                for layer in self.layers.values() for m in layer.machines):
            return False
```

`game/systems.py`, `craft`: guarde o slot do item consumido antes do `_spend` e ponha o novo nele.
```python
        replaced = C.CRAFT_REPLACES.get(kind)
        slot = next((i for i, s in enumerate(self.inventory.slots) if s is not None and s.item == replaced), None)
        self._spend(cost, inv_only=t2)
        if slot is not None and self.inventory.slots[slot] is None and made == 1:
            self.inventory.slots[slot] = Stack(kind, 1)   # v0.6 Fundo M4: a nv.2 nasce onde estava a nv.1
        else:
            self.inventory.add(kind, made)
```
(`Stack` vem de `game.inventory`; confira se já está importado em `systems.py`.)

- [ ] **Step 5: Ícone e categoria**

`game/ui.py` `item_category`: `if item in C.HAND_DRILLS: return "FERRAMENTA", C.C_TI`.

`game/render.py`: nos dois ramos (`item == C.HAND_DRILL or item in C.PART_ITEMS` e `kind == C.HAND_DRILL or kind in C.PART_ITEMS`) troque por `item in C.HAND_DRILLS or item in C.PART_ITEMS`. No `_m4_icon`:
```python
        if item in C.HAND_DRILLS:
            sheet = self.surface("drill_side", lambda: art.drill("side"))[0]
            fallback = lambda: art.hand_drill_icon(sheet)   # noqa: E731
            if item == C.HAND_DRILL_T2:                     # v0.6 Fundo M4: sem o PNG dela, o da nv.1 (ou o fallback)
                return self.surface("icon_hand_drill_t2",
                                    lambda: self.surface("icon_hand_drill", fallback)[0].copy())[0]
            return self.surface("icon_hand_drill", fallback)[0]
```
Atualize o comentário do ramo ("a broca ainda aguarda o dono").

- [ ] **Step 6: Rodar**

Run: `uv run pytest tests/test_drill_t2.py tests/test_m4_expedition.py tests/test_bench_t2.py tests/test_inventory.py -v`
Expected: PASS. Se algum teste antigo comparar `C.T2_RECIPES == ("backpack", "chip")`, atualize pra incluir `"hand_drill_t2"`.

- [ ] **Step 7: `uv run pytest` inteiro verde.**

---

### Task 2: Minerar com a nv.2 (×1,5 e rocha dura)

**Files:**
- Modify: `game/config.py:159` (`MINE_TIME[HARD_ROCK]`)
- Modify: `game/systems.py` (`Controls`, ~37; `GameState.__init__`; `update`, ~600; `can_break_hard`/`mine_speed`, ~2026)
- Modify: `game/app.py` (`hand_drill_selected`, ~566; `Controls(...)`, ~1609; hint, ~2125)
- Test: `tests/test_drill_t2.py`, `tests/test_hard_rock.py`

**Interfaces:**
- Consome: `C.HAND_DRILL_T2`, `C.HAND_DRILLS`, `C.HAND_DRILL_T2_SPEED` (Task 1).
- Produz: `Controls.drill_tier: int = 1`, `GameState.drill_tier: int` (1 ou 2, atualizado em `update`), `App.held_drill_tier() -> int` (0 sem broca, 1 ou 2).

- [ ] **Step 1: Testes que falham** (no fim de `tests/test_drill_t2.py`)

```python
from game.systems import Controls  # noqa: E402
from tests.test_hard_rock import HARD, cave_state  # noqa: E402

DT = 1 / 30


def run(g, seconds, controls):
    for _ in range(round(seconds / DT)):
        g.update(DT, controls)


def stand_next_to(g, tile):
    g.player.x = (tile[0] + 1.5) * C.TILE
    g.player.y = (tile[1] + 0.5) * C.TILE + 4


def test_hard_rock_base_time():
    assert C.MINE_TIME[C.HARD_ROCK] == 2.25            # ~1,5 s com a nv.2


def test_t1_cannot_break_hard_t2_can():
    g = cave_state()
    stand_next_to(g, HARD)
    run(g, 3.0, Controls(mine_tile=HARD, drill_in_hand=True, drill_tier=1))
    assert g.world.get(*HARD) == C.HARD_ROCK
    run(g, 1.6, Controls(mine_tile=HARD, drill_in_hand=True, drill_tier=2))
    assert g.world.get(*HARD) != C.HARD_ROCK


def test_t2_hard_rock_takes_about_1_5_s():
    g = cave_state()
    stand_next_to(g, HARD)
    run(g, 1.4, Controls(mine_tile=HARD, drill_in_hand=True, drill_tier=2))
    assert g.world.get(*HARD) == C.HARD_ROCK


def test_t2_mines_faster():
    g = game()
    px, py = g.player.tile
    g.world.set(px + 1, py, C.IRON)                    # ferro: 1,0 s na nv.1, ~0,67 s na nv.2
    run(g, 0.75, Controls(mine_tile=(px + 1, py), drill_in_hand=True, drill_tier=2))
    assert g.world.get(px + 1, py) != C.IRON


def test_speed_and_hard_flags():
    g = game()
    g.drill_tier = 1
    assert g.mine_speed == 1.0 and not g.can_break_hard
    g.drill_tier = 2
    assert g.mine_speed == C.HAND_DRILL_T2_SPEED and g.can_break_hard
    g.fast = True
    assert g.mine_speed == C.DEBUG_MINE * C.HAND_DRILL_T2_SPEED


def test_bedrock_still_unbreakable():
    g = cave_state()
    g.drill_tier = 2
    assert not g.world.is_minable(0, 0)                # borda do sintético é BEDROCK
```

Confira como o `test_hard_rock.py` posiciona o player perto do `HARD` (copie o jeito dele se o `stand_next_to` não bater com a colisão) e se `HARD` tem chão do lado.

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/test_drill_t2.py -v` (FAIL: `Controls` sem `drill_tier`).

- [ ] **Step 3: Implementar**

`game/config.py:159`: `HARD_ROCK: 2.25,   # v0.6 Fundo: só com a nv.2 (~1,5 s nela, ×1,5) ou o F3`

`game/systems.py`:
```python
    drill_tier: int = 1                        # v0.6 Fundo M4: 2 = broca nv.2 na mão (×1,5 e quebra rocha dura)
```
no `Controls`; `self.drill_tier = 1` no `GameState.__init__`; no `update`, antes do `_update_mining`: `self.drill_tier = controls.drill_tier`.

```python
    @property
    def can_break_hard(self) -> bool:
        """Quebra rocha dura? A broca nv.2 na mão (v0.6 Fundo M4) ou o F3."""
        return self.fast or self.drill_tier >= 2

    @property
    def mine_speed(self) -> float:
        """Multiplicador da broca: ×1,5 com a nv.2, ×DEBUG_MINE com o F3 (os dois juntos multiplicam)."""
        speed = C.HAND_DRILL_T2_SPEED if self.drill_tier >= 2 else 1.0
        return speed * (C.DEBUG_MINE if self.fast else 1.0)
```

`game/app.py`:
```python
    def held_drill_tier(self) -> int:
        """v0.6 Fundo M4: 0 sem broca na mão, 1 a nv.1, 2 a nv.2 (slot escolhido da hotbar)."""
        stack = self.state.inventory.slots[self.hotbar_selected]
        if stack is None or stack.item not in C.HAND_DRILLS:
            return 0
        return 2 if stack.item == C.HAND_DRILL_T2 else 1

    def hand_drill_selected(self) -> bool:
        """v0.5 M4: uma broca de mão (nv.1 ou nv.2) é o slot escolhido da hotbar? (só com ela o clique minera)"""
        return self.held_drill_tier() > 0
```
E no `Controls(...)` da linha ~1609: `drill_in_hand=self.hand_drill_selected(), drill_tier=max(1, self.held_drill_tier())`.

Na dica (linha ~2125): antes do `state.hard_blocked(tile)`, ponha `state.drill_tier = max(1, self.held_drill_tier())` pra dica valer no mesmo frame da troca de slot. O texto "Selecione a broca de mão pra minerar" fica igual.

- [ ] **Step 4: Rodar** — `uv run pytest tests/test_drill_t2.py tests/test_hard_rock.py tests/test_m4_expedition.py -v`. Teste antigo que dependa de `MINE_TIME[HARD_ROCK] == 1.5` ou de "F3 quebra rocha dura em X s" tem que ser atualizado pro 2,25.

- [ ] **Step 5: `uv run pytest` inteiro verde.**

---

### Task 3: Wafer na Fundição, circuito no fabricador e prints

**Files:**
- Modify: `game/config.py` (`SMELTER_RECIPES`, ~298; `LOGISTIC_ITEMS`, ~598; bloco dos fios, ~1007; descrições do wafer e do circuito no bloco do M4)
- Modify: `game/app.py:1002`, `:1120` (texto da recusa)
- Modify: `game/ui.py:1972-1978` (título e rótulo "SAÍDA"; o texto "Ponha minério e magmatita. Drones levam os lingotes." vira "Ponha minério e magmatita. Drones levam o que sair.")
- Create: `tools/dev/shot_v06_fundo_m4.py`
- Test: `tests/test_smelter.py`, `tests/test_fabricator.py`

**Interfaces:**
- Consome: Tasks 1 e 2 (os prints usam a nv.2).
- Produz: `C.SMELTER_RECIPES["silicon"] == "silicon_wafer"`, `"silicon_wafer" in C.LOGISTIC_ITEMS`, `C.MACHINES["circuit"].cost == {"silicon_wafer": 1, "wire": 2}`.

- [ ] **Step 1: Testes que falham**

Em `tests/test_smelter.py`:
```python
def test_silicon_makes_wafer(game):
    m = add_smelter(game, ore=("silicon", 2), fuel_items=1)
    run(game, C.SMELTER_TIME * 2 + 1)
    assert m.storage.slots[C.SMELTER_OUT_SLOT] == Stack("silicon_wafer", 2)
    assert m.storage.slots[C.SMELTER_ORE_SLOT] is None


def test_wafer_is_logistic_and_drones_route_silicon(game):
    m = add_smelter(game)
    assert "silicon_wafer" in C.LOGISTIC_ITEMS
    assert drones.can_send(m, "silicon_wafer") and drones.can_receive(m, "silicon")
    assert drones.receive_slot(m, "silicon") == C.SMELTER_ORE_SLOT


def test_save_keeps_silicon_and_wafer():
    inv = save.smelter_storage([["silicon", 3], None, ["silicon_wafer", 2]])
    assert inv.slots[C.SMELTER_ORE_SLOT] == Stack("silicon", 3)
    assert inv.slots[C.SMELTER_OUT_SLOT] == Stack("silicon_wafer", 2)
```
(Confira o formato de `save.smelter_storage` no `test_save_cleans_bad_slots` e copie.) Atualize `test_logistic_items_include_ingots` se ele comparar a tupla inteira.

Em `tests/test_fabricator.py`, no molde do teste dos fios:
```python
def test_circuit_recipe_in_materials():
    m = C.MACHINES["circuit"]
    assert m.cost == {"silicon_wafer": 1, "wire": 2} and m.unlock_ti == 0
    assert C.MACHINE_CATEGORY["circuit"] == "materials"
    assert "circuit" in craft_kinds("materials")
```
(Use o nome real da função que lista as receitas por aba no `game/fabricator.py`; o teste dos fios mostra qual é.) Mais um teste que fabrica no T1 dentro da base (copie o do fio): com 1 wafer e 2 fios, `craft("circuit")` dá 1 circuito e zera os dois.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

```python
SMELTER_RECIPES = {"iron": "iron_ingot", "copper": "copper_ingot",
                   "silicon": "silicon_wafer"}   # v0.6 Fundo M4: o silício vira wafer (mesmo tempo e magmatita)
```
`LOGISTIC_ITEMS`: some `"silicon_wafer"` no fim, com comentário `v0.6 Fundo M4: o wafer da Fundição`.

No bloco do M4 (depois dos fios existirem, ou seja, perto da linha ~1010; se o bloco do M4 estiver acima, ponha esta parte logo depois do bloco dos fios com o cabeçalho "v0.6 Fundo M4 · circuito"):
```python
MACHINES["circuit"] = _replace(MACHINES["circuit"], cost={"silicon_wafer": 1, "wire": 2}, desc="1 wafer + 2 fios")
MACHINE_ORDER.append("circuit")
MACHINE_CATEGORY["circuit"] = "materials"
MACHINES["silicon_wafer"] = _replace(MACHINES["silicon_wafer"], desc="sai da Fundição (silício)")
```

`game/app.py`: as duas mensagens viram `"A Fundição só aceita ferro, cobre, silício e magmatita"`.

`game/ui.py` `_smelter_panel`: título `f"{out.count if out else 0} prontos"`, rótulo `"SAÍDA"` no lugar de `"LINGOTE"`, texto de ajuda acima. Atualize a docstring.

- [ ] **Step 4: Prints** (`tools/dev/shot_v06_fundo_m4.py`, molde do `shot_v06_fundo_m3.py`: mesmo `save`, `App(scale=1, skip_title=True)`, seed 7, saída em `reports/dev/v06_fundo_m4/`)
  - `bench_t2_drill.png`: painel da Bancada T2 com a receita da nv.2 selecionada (com tudo no inventário) e a nv.1 no slot 0;
  - `bench_t2_missing.png`: a mesma receita sem a nv.1 (mostra o que falta; confere que o nome "Broca de mão" aparece sem quebrar);
  - `fabricator_materials.png`: fabricador T1, aba Materiais, com fios e circuito;
  - `smelter_wafer.png`: Fundição fundindo silício com 2 wafers na saída;
  - `chest_logistics.png`: painel do baú com os **9** toggles;
  - `hotbar_t2.png`: hotbar com a nv.2 no slot onde estava a nv.1 (depois do craft).

  Rode `uv run python tools/dev/shot_v06_fundo_m4.py` e **olhe cada PNG**. Se os 9 toggles do baú não couberem na largura do painel, pare e avise o gerente com o print (não redesenhe).

- [ ] **Step 5: `uv run pytest` inteiro verde.**

---

### Task 4: Bíblia "Marco 4 · como ficou"

**Files:**
- Modify: `docs/GAME_BIBLE.md` (§15, depois de "Marco 3 · como ficou")

- [ ] **Step 1:** Escreva `### Marco 4 · como ficou na implementação (...)` no estilo dos marcos de cima, com bullets: a nv.2 (item, receita, slot da nv.1, `Controls.drill_tier`, ×1,5, rocha dura 2,25 s de base = 1,5 s na nv.2, F3 multiplica junto, bedrock); `ensure_hand_drill`; o wafer na Fundição (slot "SAÍDA", recusa nova, logística com 9 toggles); o circuito na aba Materiais; save v12 sem migração; ícones (pendente do Designer até o merge; sem o PNG da nv.2, o da nv.1). No bullet "Painel" do Marco 3 e no da recusa, acrescente "*(M4: e silício)*" onde fala de "ferro, cobre e magmatita".

- [ ] **Step 2:** `uv run pytest` verde e relatório final pro gerente: arquivos mudados, testes novos, os 6 prints (caminho) e qualquer desvio do plano.
