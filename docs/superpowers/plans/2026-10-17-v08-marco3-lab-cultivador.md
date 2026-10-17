# v0.8 M3 · Lab da Ilves e cultivador: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a primeira planta do jogo.
- O laboratório da Dra. Ilves nasce trancado por gelo, que derrete com o calor.
- Lá dentro, escanear o tanque de cultura quebrado libera o **Cultivador**, e a caixa traz a **alga** (cultura-controle).
- O Cultivador, dentro da base vedada e com água, faz a alga crescer em 4 etapas, gera **biomassa por segundo** e dá colheita.

**Architecture:**
- **Gelo do lab:** reaproveita os gelos-portão (`ice_blocks.blocks_at`, `thaw`, `Layer.refresh_gates`), com um "portão" a mais posicionado na porta do lab e com uma faixa de calor própria.
- **Máquina quebrada que dá diagrama:** reaproveita o scan segurando dos props (`GameState._update_scan`). O scan de certos alvos libera uma **receita de máquina** (`state.blueprints`) em vez de um prop de decoração.
- **Cultivador:** máquina com storage de slots fixos, no molde da Fundição e do Coletor (M2). Um `Machine.crop` + `growth` + `tank` guardam a planta.

**Tech Stack:** Python 3 + pygame-ce, pytest, `uv run`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-16-v08-plantas-design.md` (seções "Laboratório da Ilves" e "Cultivador"). Bíblia §17 (decisões da arte: cultivador B, UI A, gelo do lab = blocos do portão).
- **Arte já em `assets/sprites/`** (contrato §6):
  - `machine_cultivator{,_dry,_broken}.png`, `anim/anim_machine_cultivator.png`;
  - `cultivator_crop_{algae,plant_1,plant_2,plant_3}_{0..3}.png`;
  - `machine_microscope_broken.png`;
  - `icon_algae.png`, `icon_cultivator.png` e os outros ícones da v0.8.
  - **As quebradas não levam `RUIN_BROKEN_TINT`.**
- O mock aprovado da UI é `reports/design/v08_plantas/ui_cultivador_A.png`. Abra com Read antes da Task 6.
- **Números de partida** (todos em `config.py`, balanceados no M5):
  - `LAB_ICE_HEAT = (5_000, 8_000)` pK: o gelo do lab começa a derreter em 5.000 e some em 8.000;
  - `CULTIVATOR_TANK = 5.0` (cápsulas no tanque interno);
  - `CROPS`:

    | Cultura | `biomass` (/s) | `water_s` (s por cápsula) | `cycle` (s de muda a madura) |
    |---|---|---|---|
    | `algae` | 0.5 | 120.0 | 90.0 |
    | `plant_1` | 1.5 | 90.0 | 120.0 |
    | `plant_2` | 4.0 | 60.0 | 150.0 |
    | `plant_3` | 10.0 | 45.0 | 180.0 |

  - colheita: 1 ou 2 itens da própria cultura (50/50, rng do estado);
  - Cultivador: custo `{"iron_ingot": 4, "silicon": 6, "ice": 4}`, `unlock_ti 0` (trava pelo diagrama), `POWER_USE` 1, categoria "automation" depois do Coletor.
- **Só a alga é alcançável no M3.** As plantas 1–3 já ficam no `CROPS` (o M4 só cria o jeito de obter), mas nenhuma fonte delas entra agora.
- O microscópio quebrado **fica no lab, mas o scan dele ainda não dá nada**. O M4 liga o diagrama do microscópio, quando a máquina existir.
- **Save v16.**
- O Dev **não commita**, **não abre o jogo em janela**, **não roda `build_sprites.py`**, **não mexe em `assets/`**. O pytest inteiro roda em background com log, e nunca dois ao mesmo tempo.

---

### Task 1: Gelo na porta do lab

**Files:**
- Modify: `game/config.py` (`LAB_ICE_HEAT`, `LAB_ICE_RECIPE = "A"`)
- Modify: `game/ruins.py` (o lab só nas orientações em que a porta dupla `==` fica na borda **de baixo**; o lab nunca derruba parede)
- Modify: `game/layers.py` (`refresh_gates`: soma os blocos do gelo do lab), `game/systems.py` (`_apply_thaw`: progresso do lab, evento quando abre), `game/app.py` (aviso e som ao abrir; dica com o mouse em cima: "Gelo · a porta do laboratório abre com ~N pK (agora X)")
- Test: `tests/test_lab_v08.py` (novo)

**Interfaces:**
- Produces:
  - `ruins.lab_door_px(world) -> tuple[float, float] | None`: o pé do gelo, no meio da borda de baixo da porta dupla do lab, em px do mundo. `None` sem lab;
  - `thaw.lab_ice_progress(heat) -> float` (0..1, linear em `LAB_ICE_HEAT`);
  - `layer.lab_ice_open: bool`;
  - o evento `("lab_ice_open",)` uma vez.

- [ ] **Step 1: Testes que falham**

```python
"""v0.8 M3: o laboratório da Ilves trancado no gelo, o tanque quebrado que dá o Cultivador e a alga."""

import pytest

from game import config as C, ruins, thaw
from game.systems import GameState


def lab_of(state):
    return next((r for r in state.world.ruins if r.key == "lab"), None)


def test_lab_ice_progress():
    lo, hi = C.LAB_ICE_HEAT
    assert thaw.lab_ice_progress(lo - 1) == 0.0 and thaw.lab_ice_progress(hi) == 1.0
    assert thaw.lab_ice_progress((lo + hi) / 2) == pytest.approx(0.5)


def test_lab_door_faces_south_and_walls_never_fall():
    for seed in (1, 7, 42, 2024):
        state = GameState(seed=seed)          # use o construtor que os testes de ruína usam pra trocar a seed
        lab = lab_of(state)
        if lab is None:
            continue
        assert lab.orient in ruins.LAB_ORIENTS
        assert ruins.lab_door_px(state.world) is not None


def test_lab_is_closed_until_the_heat_opens_it():
    state = GameState(seed=7)
    if lab_of(state) is None:
        pytest.skip("seed sem lab")
    assert state.active.lab_ice_open is False
    assert any(b.rect is not None for b in state.active.gate_blocks)       # tem bloco na porta
    state.indices["heat"] = C.LAB_ICE_HEAT[1]
    state._apply_thaw()
    assert state.active.lab_ice_open is True
    assert ("lab_ice_open",) in state.events
```

Mais um teste:
- com o calor abaixo da faixa, o player **não passa** pela porta do lab;
- com o calor no fim da faixa, **passa**.

Faça como `tests/test_giant_gate.py` / `tests/test_thaw.py` testam o player andando pela fresta (procure "passable" ou o teste que anda o player). Se o `Ruin` não guardar `orient`, guarde, porque o teste precisa dele.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

`ruins.py`:
- descubra quais dos 8 `orient` deixam a porta dupla `==` do `lab.txt` na **última linha** da grade transformada. É o 0 e o espelhado (4), mas confira rodando `transform`;
- guarde isso em `LAB_ORIENTS` (tupla calculada uma vez a partir do `lab.txt`, não escrita à mão);
- no `_search`/`build` do lab, sorteie a orientação só entre essas;
- o lab usa nível de destruição só em `(0, 1)`, que é onde `RUIN_DAMAGE_WALL` é 0, pra nenhuma parede cair e abrir passagem;
- `lab_door_px(world)`: o meio da borda de baixo dos 2 tiles `==` do lab, em px.

`thaw.py`:
```python
def lab_ice_progress(heat: float) -> float:
    """v0.8 M3: degelo da porta do laboratório da Ilves (0 = inteiro .. 1 = sem gelo), linear em C.LAB_ICE_HEAT."""
    lo, hi = C.LAB_ICE_HEAT
    return min(1.0, max(0.0, (heat - lo) / (hi - lo)))
```

`layers.py`:
- a camada da superfície ganha `lab_ice_p = 0.0` e `lab_ice_open = False`;
- `refresh_gates` acrescenta `ice_blocks.blocks_at(lab_door_px, C.LAB_ICE_RECIPE, self.lab_ice_p, gate=<um índice que não colide com os portões; use um índice novo e confira o que o `gate` muda dentro do blocks_at>)`;
- `lab_ice_open = self.lab_ice_p >= ice_blocks.opens_at(C.LAB_ICE_RECIPE)`;
- sem lab ou sem geo, nada muda.

`systems.py`, `_apply_thaw`:
- calcula `lab_ice_progress(heat)`;
- se mudou, `refresh_gates()`;
- na primeira vez que `lab_ice_open` vira `True`, solta `("lab_ice_open",)`.

Como nos portões, **nada vai no save**: o load reconstrói pelo calor.

`app.py`:
- no `("lab_ice_open",)`, aviso de 4 s no topo, `"O gelo do laboratório cedeu"`, e o som `ice_collapse` (0,8), como no `gate_thaw` 3;
- a dica com o mouse em cima do gelo do lab segue a do gelo-portão.

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_lab_v08.py tests/test_ruins.py tests/test_thaw.py tests/test_giant_gate.py -q` → PASS.

---

### Task 2: Escanear o tanque quebrado libera o Cultivador

**Files:**
- Modify: `game/config.py`:
  - `BLUEPRINTS` ou um dict novo `SCAN_BLUEPRINT = {"prop_sample_tank": "cultivator"}`;
  - `RECIPE_BLUEPRINT["cultivator"] = "cultivator"` (ou o equivalente de hoje, que faz `recipe_status` devolver "blueprint" até liberar);
  - a arte dos dois props do lab.
- Modify: `game/systems.py` (`can_scan` e `_update_scan`)
- Modify: `game/render.py` (os dois props do lab desenham a máquina quebrada)
- Test: `tests/test_lab_v08.py`

**Decisão:** o tanque (`prop_sample_tank`) e o microscópio (`prop_microscope_digital`) **continuam props** na planta do lab, porque o scan, o alcance e o save do scan já funcionam pra prop. Mudam duas coisas:
- **arte:** o desenho dos dois no lab vira `machine_cultivator_broken.png` e `machine_microscope_broken.png`, ancorados no pé como as máquinas de 40×56;
- **scan:** escanear o tanque **não** põe o tanque em `scanned` (decoração). Põe `"cultivator"` em `state.blueprints` e solta `("scan_done", "cultivator")`, com o aviso "Projeto liberado: Cultivador".

O microscópio fica escaneável **só a partir do M4**: `can_scan` devolve `False` pra ele enquanto `SCAN_BLUEPRINT` não tiver a chave dele.

Se o `prop_sample_tank` também aparece em outras ruínas, a regra vale em qualquer uma: escanear dá o Cultivador, e o diagrama é um só.

- [ ] **Step 1: Testes que falham**

```python
def test_scanning_the_tank_unlocks_the_cultivator_recipe():
    state = GameState()
    assert state.recipe_status("cultivator") == "blueprint"
    tank = place_lab_prop(state, "prop_sample_tank")    # helper: põe o prop de ruína perto do player (molde: tests/test_props.py)
    hold_scan(state, tank)                                # segura o scan até C.SCAN_HOLD (molde: tests/test_props.py)
    assert "cultivator" in state.blueprints
    assert "prop_sample_tank" not in state.scanned        # não vira decoração
    assert state.recipe_status("cultivator") != "blueprint"


def test_microscope_is_not_scannable_yet():
    state = GameState()
    mic = place_lab_prop(state, "prop_microscope_digital")
    assert state.can_scan(mic) is False
```
Escreva `place_lab_prop` e `hold_scan` copiando o que `tests/test_props.py` usa pra pôr um prop de ruína e escanear.

- [ ] **Step 2: Rodar e ver falhar.** **Step 3: Implementar.**

**Step 4:** `uv run pytest tests/test_lab_v08.py tests/test_props.py tests/test_props_vesper_kit.py tests/test_ruins.py -q` → PASS.

---

### Task 3: A cultura-controle na caixa do lab

**Files:**
- Modify: `game/config.py`:
  - item `algae` ("Alga", "cultura-controle da Ilves", ícone `icon_algae`, não colocável, empilha como recurso de loot);
  - `RUIN_LOOT["lab"]` não muda;
  - `LOGISTIC_ITEMS` ganha `algae`, `plant_1`, `plant_2` e `plant_3`.
- Modify: `game/ruins.py` (`make_ruin_crates`: a caixa do lab sempre ganha 1 `algae` além do saque)
- Test: `tests/test_lab_v08.py`

Itens `plant_1..3` (só definição, com ícone e nome):

| Chave | Nome | Ícone |
|---|---|---|
| `plant_1` | "Folha-gota" | `icon_plant_1` |
| `plant_2` | "Espiral-de-geada" | `icon_plant_2` |
| `plant_3` | "Lírio-de-Ilves" | `icon_plant_3` |

- [ ] **Step 1: Teste**
```python
def test_lab_crate_always_has_the_algae():
    for seed in (1, 7, 42):
        state = GameState(seed=seed)
        lab = lab_of(state)
        if lab is None:
            continue
        crate = state.active.crates[lab.crate]            # ajuste pro nome real do dict de caixas da camada
        assert crate.storage.count("algae") >= 1
```
- [ ] **Step 2–4:** falhar, implementar, rodar com `tests/test_ruins.py tests/test_crate_storage.py`.

---

### Task 4: Cultivador · regras

**Files:**
- Modify: `game/config.py` (bloco "v0.8 M3 · Cultivador": `CULTIVATOR`, slots, `CULTIVATOR_TANK`, `CROPS`, `CROP_ITEMS`, a `MachineType`, `POWER_USE`, ordem/categoria)
- Modify: `game/systems.py` (`Machine.is_cultivator`, campos `crop`, `growth`, `tank`, `__post_init__`, `is_logistic`/`needs_chip`, `_update_cultivator`, `cultivator_put`/take, `GameState.in_breathing_base(tile, layer)`, roteamento do E nos mesmos pontos da Fundição/Coletor)
- Test: `tests/test_cultivator_v08.py` (novo)

**Interfaces:**
- Produces:
  - `C.CULTIVATOR = "cultivator"`;
  - slots: `C.CULT_WATER_SLOT = 0` (reserva de cápsulas cheias), `C.CULT_EMPTY_SLOT = 1` (vazias), `C.CULT_SEED_SLOT = 2` (a muda: 1 item de `CROP_ITEMS`), `C.CULT_HARVEST_SLOTS = (3, 4, 5, 6)`, `C.CULT_SLOTS = 7`;
  - `C.CROPS: dict[str, Crop]`, onde `Crop` é uma dataclass `(biomass: float, water_s: float, cycle: float)`;
  - `C.CROP_ITEMS = tuple(C.CROPS)`;
  - `Machine.crop -> str | None` (o item no slot da muda);
  - `Machine.growth: float` (0..1);
  - `Machine.tank: float` (0..`CULTIVATOR_TANK`, em cápsulas);
  - `Machine.crop_stage -> int` (0..3);
  - `GameState.cultivator_blocker(m, layer) -> str | None`, com `"no_seed"`, `"no_base"`, `"dry"`, `"full"` ou `None` = crescendo;
  - o evento `("harvest", m, item, n)`.

**Regras** (são elas que os testes cobrem):
1. **Muda:** a cultura é o item do slot da muda (1 unidade, só `CROP_ITEMS`). Tirar a muda zera `growth`. Pôr outra cultura troca a planta e também zera.
2. **Base:** só cresce com o tile do cultivador dentro de uma base com Dispersor soprando (`air_ok`) na mesma camada. Fora disso: `"no_base"`.
3. **Água:**
   - o `tank` desce `dt / crop.water_s` por segundo crescendo;
   - quando `tank <= CULTIVATOR_TANK - 1` e tem cápsula no slot 0, injeta: `tank += 1`, tira 1 cápsula e põe 1 vazia no slot 1 (cheio, a vazia some, a mesma regra do Dispersor);
   - com `tank <= 0` e sem cápsula: `"dry"`, ou seja, não cresce e não soma biomassa. A planta não morre.
4. **Crescer:**
   - `growth += dt / crop.cycle`;
   - `crop_stage = 3 if growth >= 1 else int(growth * 3)`, ou seja, 0 até 1/3, 1 até 2/3, 2 até 1 e 3 madura.
5. **Colheita:** quando `growth >= 1`, põe `n = 1 ou 2` (`rng.random() < 0.5`) do item da cultura nos slots de colheita (empilha, até onde couber).
   - Se coube, `growth = 1/3` (volta pra etapa "pequena", porque é perene) e solta `("harvest", m, item, n)`.
   - Se **não coube nada** (saída cheia): `"full"`, a planta fica madura parada, sem gastar água e sem somar biomassa.
   - Se coube parte, a parte que não coube some e a regra é a mesma do "coube".
6. **Biomassa:** enquanto `blocker is None`, `indices["biomass"] += crop.biomass × dt` (já com o `work_dt` do fator de energia).
7. **Energia:** o cultivador está em `working_machines` e gasta `POWER_USE`. Sem energia (fator 0), nada anda.

- [ ] **Step 1: Testes que falham** (`tests/test_cultivator_v08.py`)

```python
"""v0.8 M3: o Cultivador (água, 4 etapas, perene, biomassa por segundo, colheita)."""

import pytest

from game import config as C
from game.inventory import Stack


def test_algae_grows_through_4_stages_in_a_sealed_base(base_with_cultivator):
    state, cult = base_with_cultivator            # fixture: base vedada 5×5 com Dispersor com água e 1 Cultivador dentro
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 5)
    stages = set()
    for _ in range(int(C.CROPS["algae"].cycle / 0.5) - 2):
        tick(state, 0.5)                          # helper: chama o update das máquinas com dt (molde: test_water_v08.py)
        stages.add(cult.crop_stage)
    assert stages == {0, 1, 2}
    tick(state, 2.0)
    assert sum(cult.storage.count("algae") for _ in [0]) >= 2          # muda (1) + colheita (1 ou 2)
    assert cult.crop_stage == 1                   # perene: voltou pra "pequena"


def test_biomass_per_second(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 5)
    before = state.indices["biomass"]
    tick(state, 10.0)
    assert state.indices["biomass"] - before == pytest.approx(10.0 * C.CROPS["algae"].biomass, rel=0.02)


def test_outside_the_base_it_does_not_grow(game_on_surface):
    state = game_on_surface
    cult = build_now(state, C.CULTIVATOR, free_tile(state))
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 5)
    assert state.cultivator_blocker(cult, state.active) == "no_base"


def test_water_is_injected_and_leaves_an_empty(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 3)
    tick(state, 0.1)
    assert cult.tank == pytest.approx(C.CULTIVATOR_TANK, abs=0.01)      # tanque cheio de cara
    assert cult.storage.count(C.EMPTY_CAPSULE) >= 1


def test_dry_stops_growth_and_biomass(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.tank = 0.0
    before, g = state.indices["biomass"], cult.growth
    tick(state, 5.0)
    assert state.cultivator_blocker(cult, state.active) == "dry"
    assert state.indices["biomass"] == before and cult.growth == g


def test_full_harvest_holds_the_plant_mature(base_with_cultivator):
    state, cult = base_with_cultivator
    cult.storage.slots[C.CULT_SEED_SLOT] = Stack("algae", 1)
    cult.storage.slots[C.CULT_WATER_SLOT] = Stack("water_capsule", 5)
    for s in C.CULT_HARVEST_SLOTS:
        cult.storage.slots[s] = Stack("algae", C.STACK_LOOT)          # ajuste pro max_stack real da alga
    cult.growth = 0.999
    tick(state, 1.0)
    assert cult.crop_stage == 3 and state.cultivator_blocker(cult, state.active) == "full"
```

Escreva também:
- `test_removing_the_seed_resets_growth`;
- `test_only_crop_items_go_in_the_seed_slot` (pelo `cultivator_put`);
- `test_tank_drains_at_the_crop_rate`.

As fixtures `base_with_cultivator`, `game_on_surface`, `free_tile` e `tick` seguem as do `tests/test_water_v08.py` (M2). Reaproveite importando de lá ou movendo pro `tests/helpers.py`.

Uma correção no primeiro teste: a linha `sum(...)` é ruim. Escreva a asserção direito, com o total de `algae` nos slots de colheita `>= 1` e o slot da muda ainda com 1.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**, seguindo as regras acima. `_update_cultivator(m, layer, dt)` é chamado num laço próprio por camada, como o Coletor e o Dispersor no M2, com o `work_dt`. O `rng` da colheita é o do estado: veja o que `_update_*` já usa pra sorteio, ou o `random.Random` do `GameState`. O resultado tem que ser determinístico no teste.

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_cultivator_v08.py tests/test_water_v08.py tests/test_energy.py tests/test_fabricator.py -q` → PASS.

---

### Task 5: Cultivador · desenho no mundo

**Files:** `game/render.py` (e `game/art.py` só se precisar de fallback)

- Corpo:
  - `machine_cultivator` parado, ou a tira `anim/anim_machine_cultivator` **só crescendo** (`blocker is None` e com energia), no molde da Fundição/Coletor;
  - com `"dry"`, o `machine_cultivator_dry`.
- Miolo: com `m.crop`, desenhe `cultivator_crop_<crop>_<crop_stage>` **por cima do corpo, no mesmo (x, y) de âncora**, em qualquer estado (parado, animando ou seco).
- Luz da máquina verde-água em `MACHINE_LIGHT["cultivator"] = (140, 230, 170)`.
- Os props quebrados do lab (Task 2) usam as artes `_broken` sem tint.

Teste em `tests/test_cultivator_v08.py`: um teste de render headless que monta o cultivador com alga na etapa 2 e confere que o nome do miolo pedido é `cultivator_crop_algae_2`. Se o render tiver uma função que devolve a lista de surfaces/nomes a desenhar, teste por ela; senão, extraia uma função pura `cultivator_layers(m, blocker) -> list[str]` e teste essa.

---

### Task 6: Cultivador · painel (UI A)

**Files:** `game/app.py` (modo `"cultivator"`, como `"collector"`), `game/ui.py` (`_cultivator_panel`)

Siga o mock `reports/design/v08_plantas/ui_cultivador_A.png`:
- **Título:** "Cultivador", e à direita `"<CULTURA> · ETAPA n/4"`, ou "SEM MUDA".
- **Coluna esquerda:**
  - barra vertical **ÁGUA** (tanque, `tank / CULTIVATOR_TANK`, com o texto `"3/5"`);
  - barra vertical **CRESCE** (`growth`, com o texto `"55%"`).
- **Centro:** o cilindro ampliado ×2, ou seja, o corpo + o miolo da etapa atual, com o texto `"0,5 BIO/S"` embaixo (a biomassa/s da cultura; 0 se travado).
- **Direita:** **COLHEITA**, os 4 slots de colheita, e `"1-2 POR COLHEITA"`.
- **Embaixo:**
  - os slots **CHEIAS** (reserva) e **VAZIAS**;
  - o slot da **MUDA** (na posição que couber, perto do cilindro);
  - a linha de status (`"Crescendo"`, `"Sem muda"`, `"Fora da base vedada"`, `"Sem água"` ou `"Colheita cheia"`, curta como no Coletor);
  - a faixa **DRONES** (Envia/Recebe/Lote), igual às outras.
- Clique, clique direito e shift+clique seguem as outras máquinas: a muda só aceita `CROP_ITEMS`, a reserva só cápsula cheia, e a colheita e as vazias só saem.

**Drones** (`game/drones.py`):
- o cultivador **recebe** `water_capsule` no slot 0;
- **envia** `EMPTY_CAPSULE` e os itens de `CROP_ITEMS` da colheita (nunca a muda do slot 2).

Testes de lógica em `tests/test_cultivator_v08.py`:
- `can_send` e `can_receive` do cultivador;
- `cultivator_put` (a muda, a reserva e o que recusa);
- o take, que nunca tira a muda junto no "pegar tudo".

**Decisão:** o "PEGAR TUDO" pega colheita e vazias, **não** a muda. A muda sai só com clique nela.

---

### Task 7: Save v16

**Files:** `game/save.py`, `tests/test_save.py`
- O cultivador salva `growth`, `tank` e o storage com os slots fixos (cada slot só aceita o que pode).
- `SAVE_VERSION = 16`, `_v15_to_v16` sem mudança no dict (documente), `MIGRATIONS[15]`.
- O gelo do lab **não** vai no save (derivado do calor). O scan do tanque já vai pelo `blueprints`.
- Teste: round-trip de um cultivador com alga na etapa 2, tanque 3,4, 2 cápsulas, 1 vazia e 3 algas de colheita.

---

### Task 8: Prints e fechamento

**Files:** `tools/dev/shot_v08_m3.py` (novo, no molde do `shot_v08_m2.py`)

Prints em `reports/dev/`:
- `v08_m3_lab_fechado.png`: o lab com o gelo na porta, calor abaixo da faixa;
- `v08_m3_lab_aberto.png`: o lab por dentro, aberto, com o tanque e o microscópio quebrados e o player perto da caixa;
- `v08_m3_cultivador_etapas.png`: 4 cultivadores com alga, um em cada etapa, dentro da base;
- `v08_m3_painel.png`: o painel do cultivador aberto (alga, etapa 3/4, tanque 3/5, colheita com algas);
- `v08_m3_seco.png`: um cultivador seco.

Abra cada um com Read e descreva no report.

- **pytest inteiro** em background (`uv run pytest -q > /tmp/pytest_m3.log 2>&1; echo exit=$?`) → `exit=0`.
- **Smoke:** rode `grep -n "lab\|ruin\|prop_sample_tank\|prop_microscope" tools/dev/smoke.py tools/dev/shot_*.py` e ajuste o que depender do lab aberto ou do prop antigo.
- **Report** `reports/dev/v08_m3.md`: mudanças por arquivo, os prints, o fim do log do pytest, **"Diferente do plano"** e os riscos.

**Não commite.**
