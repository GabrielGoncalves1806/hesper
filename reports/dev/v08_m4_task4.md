# v0.8 M4 · Task 4 · Centrífuga · regras

Worktree `agent-aaec4c8673a2028e8`, base `853e2af2`. Sem commit.

## Mudanças por arquivo

- **`game/config.py`**: bloco novo "v0.8 M4 · Centrífuga", logo depois do bloco das amostras. Tem:
  - `CENTRIFUGE = "centrifuge"`;
  - os slots `CENT_ALGAE_SLOT = 0`, `CENT_SAMPLE_SLOT = 1`, `CENT_OUT_SLOTS = {plant_1: 2, plant_2: 3, plant_3: 4}` e `CENT_SLOTS = 5`;
  - `CENTRIFUGE_TIME = 30.0`, `CENTRIFUGE_RECIPES`, `CENTRIFUGE_REACH = MELTER_REACH` e `CENTRIFUGE_FPS = 10`;
  - o `MachineType`: "Centrífuga", "alga + amostra → planta", custo `{iron_ingot 6, copper_ingot 2, wire 4}`, `unlock_ti 0`, `unlock_stage=ALGAE_STAGE`;
  - `POWER_USE` 1, `MACHINE_ORDER` logo depois do Cultivador, categoria "automation";
  - `MACHINE_FEMININE.add(CENTRIFUGE)` (pro "submersa").
- **`game/systems.py`**:
  - `Machine.spinning` (não vai no save), `is_centrifuge` e o storage de 5 slots no `__post_init__`;
  - entra no `is_logistic` e no `needs_chip`;
  - `nearby_centrifuge`, e o kind `"centrifuge"` no `interactable_at`, no `in_reach` e no `interaction`;
  - `centrifuge_put`, no molde do `smelter_put`: a alga vai pro slot 0, a amostra pro 1, um tipo por vez; o resto não entra;
  - `centrifuge_blocker` (`no_algae` / `no_sample` / `out_full` / `None`) e `_update_centrifuge`. O sorteio usa `self.rng.random() < chance`. Os eventos são `("centrifuge_done", m, plant)` e `("centrifuge_done", m, None)`;
  - o conteúdo volta no `dismantle_returns`;
  - no `_update_machines`, a centrífuga entra no laço principal (`working_machines`), do lado da Fundição, e roda em qualquer camada.
- **`tests/test_centrifuge_v08.py`** (novo): 17 testes e 1 xfail.
  - Cobrem: registro, construção, ciclo, chances (3 parametrizados), sucesso no slot da planta, falha, `out_full` só da receita atual, travas, caverna, déficit de energia, `centrifuge_put` (inclusive com outra amostra no slot), E/alcance e desmonte.
  - O xfail é `test_centrifuge_unlocks_at_the_algae_stage` (`reason="precisa da Task 1"`). Hoje ele falha com `'ok' == 'locked'`, como esperado.
- **`tests/test_fabricator.py`**: a Centrífuga entra nas duas listas da aba Automação (`tab_kinds` e `build_kinds`), depois de `"cultivator"`. **Conflito certo com a Task 3 no merge** (o Microscópio entra antes da Centrífuga).

## Testes

```
uv run pytest tests/test_centrifuge_v08.py tests/test_cultivator_v08.py tests/test_energy.py tests/test_fabricator.py tests/test_water_v08.py -q
149 passed, 1 xfailed in 4.37s
```

## O App com um tipo que ele não conhece

Conferi num teste temporário com o App headless, já apagado: E na centrífuga, 3 ticks e um `draw()`.
- **Não quebra.**
- O hint cai no fallback da drill: `"[E] Abrir drill"`. O texto está errado, mas não dá erro.
- O E cai no `elif state.in_base_zone()`: na zona da base, abre o fabricador; fora dela, não faz nada.
- O frame desenha (sprite genérico).
- Hint e painel são da Task 7.

## Diferente do plano

- O teste está em `tests/test_centrifuge_v08.py`, não em `tests/test_lab_tools_v08.py`. Segui a seção "Execução em paralelo".
- `make_centrifuge` põe a `Machine` direto em `state.machines` (molde do `make_collector`), sem `build_now`. Motivo: depois da Task 1, o `build_now` vai travar a centrífuga, porque o helper só levanta o Ti e não o estágio. O `test_centrifuge_can_be_built` sobe o estágio antes do `build_now`. **No merge, vale o `build_now` subir o estágio também**, como faz com o Ti.
- O xfail confere `== "ok"` em vez de `in ("ok", "missing")`, porque o inventário do teste cobre o custo.
- Não tirei o `skipif` do `test_default_machines_have_no_stage_lock`: ele não existe neste worktree (é da Task 1, e lá usa `getattr`).
- O `MACHINE_FEMININE` ganhou a centrífuga. O plano não pedia; é só pro texto "submersa".

## Riscos e o que fica pras outras tasks

- **Save (Task 8):** o round-trip **perde o conteúdo**: `machine_from_dict` devolve os 5 slots vazios e `timer 0`. Ainda não tem `centrifuge_storage` nem `timer` no save.
- **Drones (Task 5):** a centrífuga já é `is_logistic`/`needs_chip`, mas o `drones.py` ainda não conhece ela. Sem chip, ela fica fora da rede.
- Só rodei os 5 arquivos pedidos, não o pytest inteiro. Pelo grep, `test_hud_text` e `test_ui_b2` iteram `C.MACHINES`/`MACHINE_ORDER` e devem passar (o nome e a descrição não têm "O2", e o custo só usa itens que já existem). Não rodei.
