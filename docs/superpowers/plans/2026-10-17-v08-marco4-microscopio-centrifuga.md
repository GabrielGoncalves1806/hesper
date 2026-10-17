# v0.8 M4 · Microscópio e centrífuga: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** as 3 plantas de Hesper ficam alcançáveis.
- Escanear o microscópio quebrado do lab libera o **Microscópio**: gelo → amostra (simples 30%, mutação 15%, rara 5%, nada 50%).
- No estágio **Algas**, o fabricador libera a **Centrífuga**: 1 alga + 1 amostra → Folha-gota, Espiral-de-geada ou Lírio-de-Ilves, por chance (60/45/30%).
- As plantas já crescem no Cultivador do M3 (`CROPS`, `plant_1..3`).

**Architecture:**
- **As duas máquinas** são de slots fixos, no molde da Fundição e do Coletor: `timer` + `storage`, `_update_*` com `work_dt`, `*_blocker`, `*_put`, painel e save próprios. O sorteio usa o `self.rng` do `GameState`, como a colheita do Cultivador.
- **Diagrama do microscópio:** reaproveita o scan do tanque do M3. Basta pôr a chave em `C.SCAN_BLUEPRINT` (o `can_scan` e o `_update_scan` já tratam).
- **Trava por estágio:** `MachineType` ganha `unlock_stage: int = 0`, e `recipe_status` devolve `"locked"` com `state.stage < unlock_stage`. O texto do "locked" passa a dizer o estágio.

**Tech Stack:** Python 3 + pygame-ce, pytest, `uv run`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-16-v08-plantas-design.md` (seções "Microscópio" e "Centrífuga"). Bíblia §17.
- **Arte já em `assets/sprites/`, aprovada** (bíblia, tabela de sprites da v0.8):
  - `machine_microscope.png`, `machine_microscope_broken.png`, `anim/anim_machine_microscope.png` (40×56, tira 160×56, 4 quadros, ~5 fps);
  - `machine_centrifuge.png`, `anim/anim_machine_centrifuge.png` (40×56, tira 160×56, 4 quadros, **10 fps**);
  - `icon_microscope.png`, `icon_centrifuge.png`, `icon_sample_{basic,mutant,rare}.png` e `icon_plant_{1,2,3}.png` (16×16).
  - Não existe centrífuga quebrada: ela não mora no lab.
- **Sem som novo.** O dono recusou duas rodadas de som da v0.8. Os eventos (`sample_found`, `centrifuge_done`) existem, mas o App só toca um som se o arquivo existir em `assets/audio/`, no molde do `collector_loop`. Nenhum `.wav` entra neste marco.
- **Números de partida** (todos em `config.py`, balanceados no M5):
  - `MICROSCOPE_TIME = 20.0` s por análise, 1 gelo por análise;
  - `MICROSCOPE_ODDS = (("sample_basic", 0.30), ("sample_mutant", 0.15), ("sample_rare", 0.05))`, e o resto (50%) é nada;
  - `CENTRIFUGE_TIME = 30.0` s por ciclo, 1 alga + 1 amostra por ciclo;
  - `CENTRIFUGE_RECIPES = {"sample_basic": ("plant_1", 0.60), "sample_mutant": ("plant_2", 0.45), "sample_rare": ("plant_3", 0.30)}`;
  - Microscópio: custo `{"iron_ingot": 4, "silicon": 6, "circuit": 1}`, `unlock_ti 0` (trava pelo diagrama), `POWER_USE` 1;
  - Centrífuga: custo `{"iron_ingot": 6, "copper_ingot": 2, "wire": 4}`, `unlock_ti 0`, `unlock_stage = C.ALGAE_STAGE`, `POWER_USE` 1;
  - as duas na categoria "automation", depois do Cultivador (Microscópio, depois Centrífuga).
- **Lição do crash do baú (`03e1cbe0`):** todo item novo em `LOGISTIC_ITEMS` precisa de ícone no rótulo do baú (`App.chest_label_icons`) e de espaço na fileira de toggles. As 3 amostras entram na logística, então a Task 2 testa as duas coisas.
- **Save continua v16.** As duas máquinas são novas (save antigo não tem nenhuma) e o diagrama do microscópio vai no `blueprints` que já existe. Nada a migrar. Se o Dev achar um motivo pra subir a versão, para e reporta em "Diferente do plano".
- O Dev **não commita**, **não abre o jogo em janela**, **não roda `build_sprites.py`**, **não mexe em `assets/`**. O pytest inteiro roda em background com log, e nunca dois ao mesmo tempo.
- Helpers de teste: use os de `tests/test_water_v08.py` (`tick`, `at_stage`, `make_collector`, fixtures `game` e `fresh`) e os de `tests/test_cultivator_v08.py`. Se precisar compartilhar, mova pro `tests/helpers.py` (não duplique).

## Execução em paralelo (dono, 2026-10-17)

As Tasks 1–4 rodam **ao mesmo tempo**, um Dev por task, cada um no seu worktree, saindo do mesmo commit. O gerente já pôs a **fundação** no `main`:
- `MachineType.unlock_stage: int = 0` (o campo; a lógica no `recipe_status` é da Task 1);
- `C.SAMPLE_ITEMS`, `C.SAMPLE_NAME`, `C.SAMPLE_DESC`, as 3 amostras em `C.MACHINES`, `RESOURCE_NAME`/`RESOURCE_LABEL` e `LOGISTIC_ITEMS` com as amostras (o config da Task 2). O teste do baú (`test_chest_toggles_wrap_with_the_crops`) já conta 16.

Pra o merge não virar briga, **cada task tem o seu arquivo de teste** (em vez de todas no `tests/test_lab_tools_v08.py`):

| Task | Teste |
|---|---|
| 1 | `tests/test_stage_lock_v08.py` |
| 2 | `tests/test_samples_v08.py` |
| 3 | `tests/test_microscope_v08.py` |
| 4 | `tests/test_centrifuge_v08.py` |

- A Task 3 e a Task 4 mexem nos mesmos pontos de roteamento (`interactable_at`, `in_reach`, `interaction`, `dismantle_returns`, `is_logistic`/`needs_chip`, `__post_init__`). Cada uma põe **só a sua máquina**, e o gerente junta no merge.
- A Task 4 **não** depende da lógica da Task 1. Ela só usa o campo `unlock_stage`, que já existe. O teste "a Centrífuga trava até as Algas" fica na Task 4, e passa depois do merge da Task 1. Até lá, marque com `pytest.mark.xfail(reason="precisa da Task 1", strict=False)`.
- O `test_default_machines_have_no_stage_lock` da Task 1 ignora `C.CENTRIFUGE` com `getattr(C, "CENTRIFUGE", None)`, então não precisa de `skipif`.
- Ninguém roda o pytest inteiro em paralelo com outro Dev: cada um roda **só os testes da sua task e os listados no Step 4**. O pytest inteiro roda no merge.

---

### Task 1: Trava de receita por estágio

**Files:**
- Modify: `game/config.py` (`MachineType.unlock_stage: int = 0`)
- Modify: `game/systems.py` (`recipe_status`)
- Modify: `game/ui.py:1433` e `game/app.py:2374` (texto do "locked")
- Modify: `tools/dev/smoke.py:173` (o helper que libera a receita sobe o estágio também)
- Test: `tests/test_lab_tools_v08.py` (novo)

**Interfaces:**
- Produces:
  - `C.MachineType.unlock_stage: int` (0 = sem trava; senão o número do estágio, 1..6);
  - `ui.unlock_text(kind: str) -> str`: `"LIBERA NO ESTÁGIO ALGAS"` se `unlock_stage > 0`, senão `f"LIBERA EM TI {fmt(unlock_ti)}"`. O App usa a mesma função e passa pra minúsculas no formato de frase: `"Libera no estágio Algas"` / `"Libera em Ti 10.000"` (veja o texto atual de `app.py:2374` e mantenha o estilo).

O nome do estágio vem de `C.STAGES[n - 1].name` (o nome curto: "ALGAS").

- [ ] **Step 1: Testes que falham**

```python
"""v0.8 M4: o Microscópio, as amostras, a Centrífuga e a trava de receita por estágio."""

import dataclasses

import pytest

from game import config as C
from game.systems import GameState


def test_stage_lock_blocks_until_the_stage(monkeypatch):
    monkeypatch.setitem(C.MACHINES, "o2", dataclasses.replace(C.MACHINES["o2"], unlock_stage=C.ALGAE_STAGE))
    state = GameState()
    state.inventory.add("iron", 50)
    state.inventory.add("silicon", 50)
    state.stage = C.MIST_STAGE
    assert state.recipe_status("o2") == "locked"
    state.stage = C.ALGAE_STAGE
    assert state.recipe_status("o2") != "locked"


def test_default_machines_have_no_stage_lock():
    assert all(m.unlock_stage == 0 for k, m in C.MACHINES.items() if k != C.CENTRIFUGE)
```

O segundo teste só passa depois da Task 4 (que cria `C.CENTRIFUGE`). Até lá, marque com `pytest.mark.skipif(not hasattr(C, "CENTRIFUGE"), ...)`, e tire o skip na Task 4.

Mais um teste: `ui.unlock_text` com uma máquina de `unlock_stage = ALGAE_STAGE` dá `"LIBERA NO ESTÁGIO ALGAS"` e com o `heater` (Ti 500) dá `"LIBERA EM TI 500"`.

- [ ] **Step 2: Rodar e ver falhar.** `uv run pytest tests/test_lab_tools_v08.py -q`

- [ ] **Step 3: Implementar**

`config.py`, no `MachineType` (depois de `placeable`):
```python
    unlock_stage: int = 0    # v0.8 M4: estágio necessário pra liberar a receita (0 = sem trava; a Centrífuga = Algas)
```

`systems.py`, `recipe_status`, logo depois do teste do Ti:
```python
        if self.ti < machine.unlock_ti or self.stage < machine.unlock_stage:
            return "locked"
```
Atualize a docstring: `'locked'` (Ti ou estágio insuficiente).

`ui.py` e `app.py`: troque os dois textos fixos pelo `unlock_text`.

`tools/dev/smoke.py:173`: além do Ti, faça `state.stage = max(state.stage, C.MACHINES[kind].unlock_stage)`. Confira se o smoke tem outro lugar que libera receita pelo Ti (`grep -n unlock_ti tools/dev/*.py`). O `balance_sim.py` **não** muda agora (fica pro M5); anote isso no report.

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_lab_tools_v08.py tests/test_fabricator.py -q` → PASS.

---

### Task 2: As 3 amostras (itens, logística, ícones)

**Files:**
- Modify: `game/config.py` (bloco novo "v0.8 M4", depois do bloco do Cultivador)
- Modify: `game/render.py` (o `item_icon` com os ícones novos, perto da linha do `C.CROP_ITEMS`, ~2086)
- Test: `tests/test_lab_tools_v08.py`

**Interfaces:**
- Produces:
  - `C.SAMPLE_ITEMS = ("sample_basic", "sample_mutant", "sample_rare")`;
  - `C.SAMPLE_NAME = {"sample_basic": "Amostra simples", "sample_mutant": "Amostra com mutação", "sample_rare": "Amostra rara"}`;
  - cada amostra em `C.MACHINES` como item não colocável (`placeable=False`, sprite `icon_<chave>`), no molde das culturas;
  - `RESOURCE_NAME` (`"amostra simples"`, `"amostra com mutação"`, `"amostra rara"`) e `RESOURCE_LABEL` (`"AMOSTRA"`, `"MUTAÇÃO"`, `"RARA"`);
  - `C.LOGISTIC_ITEMS` ganha as 3 no fim.

Descrições (`desc`): `"gelo de Hesper ao microscópio"`, `"o gelo guardava uma mutação"`, `"raríssima: o que a Ilves procurava"`.

- [ ] **Step 1: Testes que falham**

```python
def test_samples_are_logistic_items():
    for item in C.SAMPLE_ITEMS:
        assert item in C.MACHINES and not C.MACHINES[item].placeable
        assert item in C.LOGISTIC_ITEMS
        assert C.RESOURCE_NAME[item] and C.RESOURCE_LABEL[item]


def test_chest_label_has_an_icon_for_every_logistic_item(fresh):
    icons = fresh.chest_label_icons()          # o crash do 03e1cbe0: faltava ícone e dava KeyError
    assert set(C.LOGISTIC_ITEMS) <= set(icons)


def test_sample_icons_are_the_approved_pngs(fresh):
    for item in C.SAMPLE_ITEMS:
        surf = fresh.renderer.item_icon(item)  # use o nome real da função de ícone de item do render
        assert surf.get_size() == (16, 16)
```

Mais um teste de UI: a seção DRONES do **baú** com todos os itens de logística (16 agora) cabe no painel. Use `ui.logistics_height(chest)` e confira que é `wide_row_height(16)` por fileira (2 linhas de 8). Procure em `tests/` o teste do M3 que conferiu a fileira do baú com as culturas e estenda ele em vez de criar outro.

O `fresh` é a fixture do App headless de `tests/test_water_v08.py`. Pra saber se o ícone é o PNG e não o placeholder, siga o que `test_collector_item_icons_and_previews` faz.

- [ ] **Step 2: Rodar e ver falhar.** **Step 3: Implementar.**

`render.py`: junte as amostras na mesma linha das culturas:
```python
            elif item == C.CULTIVATOR or item in C.CROP_ITEMS or item in C.SAMPLE_ITEMS:   # v0.8 M3/M4: icon_<item>.png
```
O `chest_label_icons` já cai no `_m4_icon`, que acha o `icon_<item>.png`. Não precisa mexer nele, mas o teste garante.

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_lab_tools_v08.py tests/test_water_v08.py tests/test_cultivator_v08.py tests/test_drones.py -q` → PASS. (Se `tests/test_drones.py` não existir, rode os testes que têm "logist" ou "drone" no nome.)

---

### Task 3: Microscópio · regras e diagrama

**Files:**
- Modify: `game/config.py` (bloco "v0.8 M4": `MICROSCOPE`, slots, tempo, chances, `MachineType`, `POWER_USE`, ordem/categoria; `BLUEPRINTS`, `RECIPE_BLUEPRINT`, `DIAGRAM_BENCH` e `SCAN_BLUEPRINT` ganham o microscópio)
- Modify: `game/systems.py` (`Machine.is_microscope`, `__post_init__`, `is_logistic`/`needs_chip`, `microscope_blocker`, `_update_microscope`, `microscope_put`, `nearby_microscope`, `interactable_at`, `in_reach`, `interaction`, `dismantle_returns`, o laço do `_update_machines`)
- Test: `tests/test_lab_tools_v08.py`

**Interfaces:**
- Produces:
  - `C.MICROSCOPE = "microscope"`;
  - slots: `C.MIC_ICE_SLOT = 0`; `C.MIC_OUT_SLOTS = {"sample_basic": 1, "sample_mutant": 2, "sample_rare": 3}` (um slot fixo por tipo); `C.MIC_SLOTS = 4`;
  - `C.MICROSCOPE_TIME`, `C.MICROSCOPE_ODDS` (ver Global Constraints), `C.MICROSCOPE_REACH = C.MELTER_REACH`;
  - `Machine.is_microscope -> bool`;
  - `Machine.analyzing: bool` (recalculado a cada tick, não vai no save; o render anima só assim, como o `collecting` do Coletor);
  - `GameState.microscope_blocker(m) -> str | None`: `"no_ice"`, `"out_full"` ou `None` = analisando;
  - `GameState.microscope_roll() -> str | None`: sorteia com `self.rng`, devolve a chave da amostra ou `None`;
  - `GameState.microscope_put(m, index, amount=None) -> int` (só `ice` entra);
  - o evento `("sample_found", m, item)` quando sai amostra, e `("microscope_done", m, None)` quando a análise não dá nada.

**Regras:**
1. **Entrada:** só gelo, no slot 0.
2. **Análise:** com gelo e sem trava, `timer += dt`. Em `MICROSCOPE_TIME`, tira 1 gelo, zera o `timer` e sorteia.
3. **Sorteio:** `r = rng.random()`; percorre `MICROSCOPE_ODDS` acumulando as chances. `r < 0.30` → simples, `< 0.45` → mutação, `< 0.50` → rara, senão nada.
4. **Saída:** a amostra vai no slot fixo do tipo dela.
5. **Trava "out_full":** se **qualquer** um dos 3 slots de saída estiver cheio, para antes de começar (não dá pra saber o que vai sair). Guarda o progresso, não gasta gelo.
6. **Energia:** está em `working_machines` e gasta `POWER_USE`. Sem energia (fator 0), nada anda. O `dt` já vem com o fator.
7. **Onde:** funciona em qualquer camada (superfície ou caverna) e em qualquer estágio. Não precisa de base.
8. **Diagrama:** `C.SCAN_BLUEPRINT["prop_microscope_digital"] = C.MICROSCOPE`. Escanear o microscópio quebrado do lab põe `"microscope"` em `state.blueprints` e solta `("scan_done", "microscope")`. O aviso no App sai do mesmo jeito que o do Cultivador ("Projeto liberado: Microscópio"); confira que o texto vem do `BLUEPRINTS`.

- [ ] **Step 1: Testes que falham**

```python
import random

from game.inventory import Stack


def make_microscope(state, tile=(70, 70), ice=5):
    m = build_now(state, C.MICROSCOPE, tile)          # tests/helpers.py
    if ice:
        m.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", ice)
    return m


def test_microscope_is_a_diagram_from_the_lab():
    state = GameState()
    assert state.recipe_status(C.MICROSCOPE) == "blueprint"
    mic = place_lab_prop(state, "prop_microscope_digital")   # hold_scan e o helper de pôr o prop: tests/test_lab_v08.py (M3)
    assert state.can_scan(mic) is True
    hold_scan(state, mic)
    assert C.MICROSCOPE in state.blueprints
    assert ("scan_done", C.MICROSCOPE) in state.events
    assert state.can_scan(mic) is False                       # já tem o diagrama


def test_one_analysis_eats_one_ice(game):
    mic = make_microscope(game, ice=3)
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert mic.storage.count("ice") == 2


def test_odds_match_in_a_big_sample():
    state = GameState(rng=random.Random(1234))
    n = 20_000
    got = [state.microscope_roll() for _ in range(n)]
    assert got.count("sample_basic") / n == pytest.approx(0.30, abs=0.015)
    assert got.count("sample_mutant") / n == pytest.approx(0.15, abs=0.015)
    assert got.count("sample_rare") / n == pytest.approx(0.05, abs=0.01)
    assert got.count(None) / n == pytest.approx(0.50, abs=0.015)


def test_sample_goes_to_its_own_slot(game, monkeypatch):
    mic = make_microscope(game)
    monkeypatch.setattr(game, "microscope_roll", lambda: "sample_mutant")
    tick(game, C.MICROSCOPE_TIME + 0.1)
    assert mic.storage.slots[C.MIC_OUT_SLOTS["sample_mutant"]] == Stack("sample_mutant", 1)
    assert any(e[0] == "sample_found" and e[2] == "sample_mutant" for e in game.events)


def test_full_output_stops_before_eating_ice(game):
    mic = make_microscope(game, ice=3)
    mic.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", C.STACK_LOOT)
    tick(game, C.MICROSCOPE_TIME * 2)
    assert game.microscope_blocker(mic) == "out_full"
    assert mic.storage.count("ice") == 3


def test_no_ice_no_analysis(game):
    mic = make_microscope(game, ice=0)
    assert game.microscope_blocker(mic) == "no_ice"
    tick(game, 5.0)
    assert mic.timer == 0.0


def test_microscope_put_only_takes_ice(game):
    mic = make_microscope(game, ice=0)
    game.inventory.slots[0] = Stack("iron", 5)
    assert game.microscope_put(mic, 0) == 0
    game.inventory.slots[0] = Stack("ice", 5)
    assert game.microscope_put(mic, 0) == 5
```

Mais testes, no mesmo arquivo:
- `test_microscope_works_in_the_cave`: construído na camada da caverna, analisa igual;
- `test_power_deficit_slows_the_microscope` (molde: `test_power_deficit_slows_the_collector`);
- `test_interaction_opens_microscope` (molde: `test_interaction_opens_collector`);
- `test_microscope_dismantle_returns_contents` (gelo e amostras voltam, como no Coletor).

Ajuste `build_now`, `place_lab_prop`, `hold_scan`, `tick` e `game` pros nomes reais dos helpers do M2/M3. O `STACK_LOOT` pode não ser o `max` da amostra: use `max_stack("sample_rare")`.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

`systems.py`, no molde do `_collect` do Coletor:
```python
    def microscope_blocker(self, m: Machine) -> str | None:
        """Por que o Microscópio não analisa agora: "no_ice" (sem gelo), "out_full" (um dos 3 slots de amostra cheio:
        não dá pra saber o que vai sair); None = analisando."""
        if m.storage.count("ice") <= 0:
            return "no_ice"
        if any(m.storage.slots[s] is not None and m.storage.slots[s].room <= 0 for s in C.MIC_OUT_SLOTS.values()):
            return "out_full"
        return None

    def microscope_roll(self) -> str | None:
        """Uma análise: a amostra que saiu (C.MICROSCOPE_ODDS, com o rng do estado) ou None (o gelo não tinha nada)."""
        r, acc = self.rng.random(), 0.0
        for item, chance in C.MICROSCOPE_ODDS:
            acc += chance
            if r < acc:
                return item
        return None

    def _update_microscope(self, m: Machine, dt: float) -> None:
        """Microscópio (v0.8 M4): a cada MICROSCOPE_TIME s gasta 1 gelo e sorteia uma amostra no slot do tipo dela.
        Travado (sem gelo, saída cheia): para, guarda o progresso e não gasta nada."""
        while dt > 0 and self.microscope_blocker(m) is None:
            left = C.MICROSCOPE_TIME - m.timer
            if dt < left:
                m.timer += dt
                break
            dt -= left
            m.timer = 0.0
            m.storage.remove("ice", 1)
            item = self.microscope_roll()
            if item is None:
                self.events.append(("microscope_done", m, None))
                continue
            slot = C.MIC_OUT_SLOTS[item]
            out = m.storage.slots[slot]
            if out is None:
                m.storage.slots[slot] = Stack(item, 1)
            else:
                out.count += 1
            self.events.append(("sample_found", m, item))
        m.analyzing = self.microscope_blocker(m) is None
```

No `_update_machines`, o microscópio entra no laço principal (`for m in self.working_machines`), junto da Fundição (`if m.is_microscope: self._update_microscope(m, work_dt)`), porque não depende da camada.

Roteamento do E, alcance e desmonte: siga **todos** os pontos em que o `is_collector` aparece em `systems.py` (`grep -n is_collector game/systems.py`) e ponha o microscópio do lado.

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_lab_tools_v08.py tests/test_lab_v08.py tests/test_props.py tests/test_energy.py -q` → PASS.

---

### Task 4: Centrífuga · regras

**Files:**
- Modify: `game/config.py` (bloco "v0.8 M4": `CENTRIFUGE`, slots, tempo, receitas, `MachineType` com `unlock_stage=ALGAE_STAGE`, `POWER_USE`, ordem/categoria)
- Modify: `game/systems.py` (`Machine.is_centrifuge`, `__post_init__`, `is_logistic`/`needs_chip`, `centrifuge_blocker`, `_update_centrifuge`, `centrifuge_put`, `nearby_centrifuge`, `interactable_at`, `in_reach`, `interaction`, `dismantle_returns`, o laço do `_update_machines`)
- Test: `tests/test_lab_tools_v08.py`

**Interfaces:**
- Produces:
  - `C.CENTRIFUGE = "centrifuge"`;
  - slots: `C.CENT_ALGAE_SLOT = 0`, `C.CENT_SAMPLE_SLOT = 1` (uma amostra de qualquer tipo; um tipo por vez, como o minério da Fundição); `C.CENT_OUT_SLOTS = {"plant_1": 2, "plant_2": 3, "plant_3": 4}`; `C.CENT_SLOTS = 5`;
  - `C.CENTRIFUGE_TIME`, `C.CENTRIFUGE_RECIPES` (ver Global Constraints), `C.CENTRIFUGE_REACH = C.MELTER_REACH`, `C.CENTRIFUGE_FPS = 10`;
  - `Machine.is_centrifuge -> bool`;
  - `Machine.spinning: bool` (recalculado a cada tick, não vai no save);
  - `GameState.centrifuge_blocker(m) -> str | None`: `"no_algae"`, `"no_sample"`, `"out_full"` ou `None` = girando;
  - `GameState.centrifuge_put(m, index, amount=None) -> int` (a alga no slot 0, a amostra no slot 1; amostra de outro tipo com o slot ocupado não entra);
  - os eventos `("centrifuge_done", m, plant)` quando dá planta e `("centrifuge_done", m, None)` quando falha.

**Regras:**
1. **Entrada:** 1 alga (slot 0) e 1 amostra (slot 1) por ciclo. A amostra no slot define a receita.
2. **Ciclo:** com as duas e sem trava, `timer += dt`. Em `CENTRIFUGE_TIME`, consome 1 alga + 1 amostra, zera o `timer` e sorteia `rng.random() < chance`.
3. **Deu:** 1 planta da receita no slot fixo dela.
4. **Falhou:** consome os dois e não dá nada (spec).
5. **Trava "out_full":** o slot da planta **da receita atual** está cheio. Para antes de girar, guarda o progresso, não gasta nada.
6. **Energia:** igual ao microscópio.
7. **Onde:** qualquer camada. A trava de estágio é só na **receita** (fabricar). Uma centrífuga já construída funciona sempre, porque o estágio nunca volta.

- [ ] **Step 1: Testes que falham**

```python
def make_centrifuge(state, tile=(74, 70), algae=5, sample=("sample_basic", 5)):
    m = build_now(state, C.CENTRIFUGE, tile)
    if algae:
        m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", algae)
    if sample:
        m.storage.slots[C.CENT_SAMPLE_SLOT] = Stack(*sample)
    return m


def test_centrifuge_unlocks_at_the_algae_stage():
    state = GameState()
    state.inventory.add("iron_ingot", 20)
    state.inventory.add("copper_ingot", 20)
    state.inventory.add("wire", 20)
    state.stage = C.MIST_STAGE
    assert state.recipe_status(C.CENTRIFUGE) == "locked"
    state.stage = C.ALGAE_STAGE
    assert state.recipe_status(C.CENTRIFUGE) in ("ok", "missing")   # o construtor conta só o inventário: confira qual vale


def test_one_cycle_eats_one_algae_and_one_sample(game):
    m = make_centrifuge(game, algae=3, sample=("sample_basic", 3))
    tick(game, C.CENTRIFUGE_TIME + 0.1)
    assert m.storage.count("algae") == 2 and m.storage.count("sample_basic") == 2


@pytest.mark.parametrize("sample,plant,chance", [("sample_basic", "plant_1", 0.60),
                                                 ("sample_mutant", "plant_2", 0.45),
                                                 ("sample_rare", "plant_3", 0.30)])
def test_centrifuge_odds(sample, plant, chance):
    state = GameState(rng=random.Random(99))
    m = make_centrifuge(state, algae=0, sample=None)
    hits = 0
    n = 4_000
    for _ in range(n):
        m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 1)
        m.storage.slots[C.CENT_SAMPLE_SLOT] = Stack(sample, 1)
        m.storage.slots[C.CENT_OUT_SLOTS[plant]] = None
        m.timer = C.CENTRIFUGE_TIME - 1e-6
        state._update_centrifuge(m, 0.01)
        hits += m.storage.count(plant)
    assert hits / n == pytest.approx(chance, abs=0.03)


def test_failure_eats_both_and_gives_nothing(game, monkeypatch):
    m = make_centrifuge(game, algae=1, sample=("sample_rare", 1))
    monkeypatch.setattr(game.rng, "random", lambda: 0.99)
    tick(game, C.CENTRIFUGE_TIME + 0.1)
    assert m.storage.count("algae") == 0 and m.storage.count("sample_rare") == 0
    assert m.storage.count("plant_3") == 0
    assert ("centrifuge_done", m, None) in game.events


def test_full_plant_slot_stops_the_centrifuge(game):
    m = make_centrifuge(game, algae=3, sample=("sample_basic", 3))
    m.storage.slots[C.CENT_OUT_SLOTS["plant_1"]] = Stack("plant_1", max_stack("plant_1"))
    tick(game, C.CENTRIFUGE_TIME * 2)
    assert game.centrifuge_blocker(m) == "out_full"
    assert m.storage.count("algae") == 3


def test_centrifuge_put(game):
    m = make_centrifuge(game, algae=0, sample=("sample_basic", 1))
    game.inventory.slots[0] = Stack("algae", 4)
    assert game.centrifuge_put(m, 0) == 4
    game.inventory.slots[1] = Stack("sample_rare", 2)
    assert game.centrifuge_put(m, 1) == 0          # o slot da amostra já tem a simples
    game.inventory.slots[2] = Stack("ice", 2)
    assert game.centrifuge_put(m, 2) == 0
```

Mais testes, no mesmo arquivo:
- `test_centrifuge_blockers`: sem alga, `"no_algae"`; sem amostra, `"no_sample"`;
- `test_power_deficit_slows_the_centrifuge`;
- `test_interaction_opens_centrifuge`;
- `test_centrifuge_dismantle_returns_contents`.

Tire o `skipif` do `test_default_machines_have_no_stage_lock` (Task 1).

**Atenção no `test_centrifuge_odds`:** o `tick` do jogo também mexe no rng (rochas, colheita). O teste chama `_update_centrifuge` direto pra contar só o sorteio dela.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**, no molde do microscópio (Task 3) e da Fundição (`smelter_blocker` com o "out_busy"/"out_full"). A centrífuga entra no mesmo laço principal do `_update_machines`. Siga todos os pontos do `is_collector` em `systems.py`.

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_lab_tools_v08.py tests/test_cultivator_v08.py tests/test_energy.py tests/test_fabricator.py -q` → PASS.

---

### Task 5: Drones

**Files:** `game/drones.py`, test `tests/test_lab_tools_v08.py`

Regras:

| Máquina | Recebe (slot) | Envia |
|---|---|---|
| Microscópio | `ice` (`MIC_ICE_SLOT`) | as 3 amostras |
| Centrífuga | `algae` (`CENT_ALGAE_SLOT`), as 3 amostras (`CENT_SAMPLE_SLOT`) | `plant_1..3` |

- Na centrífuga, o drone só entrega amostra **do mesmo tipo** da que está no slot (ou com o slot vazio). Siga como a Fundição trata o minério no slot (`receive_slot` + o que o drone confere antes de entregar; procure "out_busy" ou a regra do minério em `drones.py`).
- `stock(machine, item)`: o microscópio só oferece as amostras (nunca o gelo); a centrífuga só oferece as plantas (nunca a alga nem a amostra da entrada).

Testes (molde: `test_collector_logistics`):
```python
def test_microscope_logistics():
    m = Machine(C.MICROSCOPE, 0, 0, 0)
    assert drones.can_receive(m, "ice") and not drones.can_receive(m, "iron")
    assert all(drones.can_send(m, s) for s in C.SAMPLE_ITEMS) and not drones.can_send(m, "ice")
    assert drones.receive_slot(m, "ice") == C.MIC_ICE_SLOT


def test_centrifuge_logistics():
    m = Machine(C.CENTRIFUGE, 0, 0, 0)
    assert drones.can_receive(m, "algae") and all(drones.can_receive(m, s) for s in C.SAMPLE_ITEMS)
    assert not drones.can_receive(m, "plant_1")
    assert all(drones.can_send(m, p) for p in ("plant_1", "plant_2", "plant_3"))
    assert not drones.can_send(m, "algae") and not drones.can_send(m, "sample_basic")
    assert drones.receive_slot(m, "algae") == C.CENT_ALGAE_SLOT
    assert drones.receive_slot(m, "sample_mutant") == C.CENT_SAMPLE_SLOT
```

Mais um: com `sample_basic` no slot da centrífuga, o drone não entrega `sample_rare` lá. Escreva no molde do teste da Fundição que já cobre o minério diferente (procure em `tests/`).

Conferir: `ui.logi_row_cap` com chip. O microscópio manda 3 e a centrífuga 3, então cabem numa fileira normal. A centrífuga recebe 4 (alga + 3 amostras). O teste confere que `logistics_height` dos dois não passa da altura do painel (Task 7).

**Step final:** `uv run pytest tests/test_lab_tools_v08.py tests/test_water_v08.py tests/test_cultivator_v08.py -q` + os testes de drones → PASS.

---

### Task 6: Desenho no mundo

**Files:** `game/render.py`

- **Microscópio:** `machine_microscope` parado, ou a tira `anim/anim_machine_microscope` **só analisando** (`m.analyzing` e com energia), a ~5 fps (o `MACHINE_ANIM_FPS` padrão). Molde: o `is_collector` em `machine_anim_index`.
- **Centrífuga:** `machine_centrifuge` parada, ou a tira `anim/anim_machine_centrifuge` **só girando** (`m.spinning`), a **10 fps**: passe `fps=C.CENTRIFUGE_FPS` pro `anim_frame_index`.
- **Luz:**
  - `MACHINE_LIGHT["microscope"] = (170, 210, 255)` (azul frio de tela), só analisando;
  - `MACHINE_LIGHT["centrifuge"] = (190, 255, 160)` (verde-claro), só girando;
  - siga o molde do Coletor nas duas listas de luz (`render.py:186` e `:2482`).
- O microscópio quebrado do lab já desenha com a arte `_broken` (M3). Não mexe.

Teste em `tests/test_lab_tools_v08.py`: `machine_anim_index` devolve `None` com a centrífuga parada e um índice com ela girando; com `machine_t` = 0,1 s a 10 fps o quadro anda 1, e a 5 fps não anda. Use o molde do teste do Coletor (`test_collector_light_only_while_collecting` e o do índice de animação).

---

### Task 7: Painéis

**Files:** `game/app.py` (modos `"microscope"` e `"centrifuge"`, como `"collector"`), `game/ui.py` (`_microscope_panel` e `_centrifuge_panel`)

**Mock aprovado: candidata A** (dono, 2026-10-17): `reports/design/v08_m4_paineis/ui_microscopio_A.png` e `ui_centrifuga_A.png`. Abra os dois com Read antes de começar, e leia a seção "Pro Dev integrar" de `reports/design/v08_m4_paineis/index.html` (posições, cores, `LOGI_Y`). É o mesmo esquema do Cultivador: a máquina ampliada no meio, a barra vertical do trabalho ao lado e as saídas empilhadas à direita. O texto abaixo é o conteúdo; o layout é o do mock.

Do mock, entram também:
- Microscópio: a faixa "CHANCE POR GELO" com NADA 50% em cinza e as 3 cores das amostras;
- Centrífuga: o cartão da amostra atual ("Amostra simples · dá Folha-gota · 60%"), com só a planta daquela amostra acesa na saída; sem amostra no slot, o cartão some e as 3 chances ficam apagadas.

**Microscópio:**
- Título "Microscópio".
- Esquerda: o slot **GELO**.
- Meio: a barra de progresso da análise (`timer / MICROSCOPE_TIME`).
- Direita: os 3 slots fixos, com a legenda embaixo de cada um: **SIMPLES 30%**, **MUTAÇÃO 15%**, **RARA 5%** (o número sai do `MICROSCOPE_ODDS`, não escrito à mão).
- Status: `"Analisando"`, `"Sem gelo"` ou `"Saída cheia"`.
- Info (a linha de baixo, como o `collector_info`): `"1 gelo a cada 20 s · metade não dá nada"`.

**Centrífuga:**
- Título "Centrífuga".
- Esquerda: os slots **ALGA** e **AMOSTRA**.
- Meio: a barra do ciclo (`timer / CENTRIFUGE_TIME`).
- Direita: os 3 slots de planta, com o nome curto embaixo (FOLHA, ESPIRAL, LÍRIO, do `RESOURCE_LABEL`).
- Status: `"Girando"`, `"Sem alga"`, `"Sem amostra"` ou `"Saída cheia"`.
- Info: com amostra no slot, `"Amostra simples · 60% de dar Folha-gota"`; sem amostra, `"Alga + amostra → planta nova"`.

**Os dois:**
- Faixa **DRONES** (Envia/Recebe/Lote) e o slot do chip, iguais às outras máquinas.
- Clique, clique direito e shift+clique seguem as outras máquinas. As entradas só aceitam o que a regra deixa (`microscope_put` / `centrifuge_put`), e as saídas só saem. O texto de recusa segue o do Coletor (`app.py:1035`): `"O Microscópio só aceita gelo"`, `"A Centrífuga só aceita alga e amostra"`, `"A saída só dá pra tirar"`.
- "PEGAR TUDO" pega só as saídas (amostras / plantas), nunca a entrada. Molde: `cultivator_take_all`.
- O E abre (Task 3/4 já roteiam). `INVENTORY_MODES` e `PANEL_MODES` ganham os dois modos, e a lista de `app.py:1719` também. Siga cada ponto do `"collector"` em `app.py` (`grep -n collector game/app.py`).

**Eventos no App:**
- `("sample_found", m, item)`: aviso flutuante em cima da máquina, `"+1 amostra rara"` (o nome curto do item), se for desta camada. Molde: o `"harvest"` (`app.py:1865`).
- `("centrifuge_done", m, plant)` com planta: aviso flutuante `"+1 Lírio-de-Ilves"`. Com `None`: aviso cinza curto `"falhou"`.
- Som: só se o arquivo existir (`sample_found.wav`, `centrifuge_loop.wav`). Hoje não existe nenhum, então fica mudo. **Não** crie canal novo de loop agora.

Testes de lógica em `tests/test_lab_tools_v08.py` (molde: `test_collector_panel_in_the_app`):
- abrir o painel de cada uma pelo App headless (`fresh`) e desenhar um frame sem erro;
- o texto de status de cada trava;
- o "pegar tudo" não tira a entrada;
- `logistics_height` dos dois cabe na altura do painel.

---

### Task 8: Save

**Files:** `game/save.py`, `tests/test_save.py` (ou `tests/test_lab_tools_v08.py`, onde ficar mais perto do molde do Coletor)

- `machine_to_dict`: o microscópio e a centrífuga salvam o `timer` (o storage vai com o resto do logístico).
- `machine_from_dict`:
  - `microscope_storage(data)`: [0] só gelo; [1..3] só a amostra do slot (`MIC_OUT_SLOTS`). Outra coisa vira vazio;
  - `centrifuge_storage(data)`: [0] só alga; [1] só amostra; [2..4] só a planta do slot. Outra coisa vira vazio;
  - `timer` limitado a `[0, MICROSCOPE_TIME]` / `[0, CENTRIFUGE_TIME]`.
- `SAVE_VERSION` **continua 16** (ver Global Constraints). Atualize o comentário da linha do `SAVE_VERSION` dizendo que o v0.8 M4 entrou sem versão nova.
- Testes:
  - round-trip de um microscópio (3 gelos, 2 simples, 1 rara, timer 7,5) e de uma centrífuga (2 algas, 1 mutação, 1 Espiral-de-geada, timer 12);
  - um save com lixo nos slots (ferro na entrada do microscópio, gelo na saída da centrífuga) carrega com o slot vazio;
  - o diagrama `"microscope"` em `blueprints` volta no load (confira como o load valida o `blueprints` contra `C.BLUEPRINTS`).

---

### Task 9: Prints e fechamento

**Files:** `tools/dev/shot_v08_m4.py` (novo, no molde do `shot_v08_m3.py`)

Prints em `reports/dev/`:
- `v08_m4_lab_scan.png`: o player escaneando o microscópio quebrado do lab (barra do scan na metade);
- `v08_m4_maquinas.png`: o Microscópio e a Centrífuga construídos lado a lado, os dois funcionando, perto de um Cultivador com Folha-gota;
- `v08_m4_painel_microscopio.png`: o painel aberto (gelo, barra no meio, 1 simples e 1 rara na saída);
- `v08_m4_painel_centrifuga.png`: o painel aberto (algas, amostra com mutação, uma Espiral-de-geada na saída);
- `v08_m4_fabricador.png`: a lista do construtor com a Centrífuga travada, mostrando "Libera no estágio Algas";
- `v08_m4_cultivadores.png`: 3 Cultivadores dentro da base, com Folha-gota, Espiral-de-geada e Lírio-de-Ilves maduras;
- `v08_m4_bau_drones.png`: o painel de um baú com a seção DRONES aberta (as 16 fileiras de toggle, conferindo a quebra).

Abra cada um com Read e descreva no report.

- **pytest inteiro** em background (`uv run pytest -q > /tmp/pytest_m4.log 2>&1; echo exit=$?`) → `exit=0`.
- **Smoke:** rode `grep -n "unlock_ti\|prop_microscope\|centrifuge\|microscope" tools/dev/smoke.py tools/dev/shot_*.py` e ajuste o que depender do microscópio não ser escaneável.
- **Report** `reports/dev/v08_m4.md`: mudanças por arquivo, os prints, o fim do log do pytest, **"Diferente do plano"** e os riscos (incluindo o `balance_sim` que ainda não conhece a trava por estágio).

**Não commite.**
