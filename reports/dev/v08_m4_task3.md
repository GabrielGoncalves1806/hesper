# v0.8 M4 · Task 3: Microscópio, regras e diagrama

Worktree `agent-aae3553e5900400b0`, branch `worktree-agent-aae3553e5900400b0`, base `853e2af2`. Sem commit.

## Mudanças por arquivo

- **`game/config.py`**
  - `BLUEPRINTS`, `RECIPE_BLUEPRINT` e `DIAGRAM_BENCH` ganham `"microscope"` nos literais, como o Cultivador. Assim o `DIAGRAM_ITEMS`/`LEGACY_DIAGRAM_ITEMS`, que derivam do `BLUEPRINTS` logo abaixo, já incluem o `diagram_microscope`.
  - Bloco novo "v0.8 M4 · Microscópio" logo depois do bloco das amostras:
    - `MICROSCOPE`, `MIC_ICE_SLOT`, `MIC_OUT_SLOTS`, `MIC_SLOTS`, `MICROSCOPE_TIME = 20.0`, `MICROSCOPE_ODDS`, `MICROSCOPE_REACH`;
    - o `MachineType`: custo 4 lingotes de ferro + 6 silício + 1 circuito, `unlock_ti 0`, sprite `machine_microscope`;
    - `POWER_USE` 1, ordem logo depois do Cultivador, categoria "automation";
    - `SCAN_BLUEPRINT["prop_microscope_digital"] = MICROSCOPE`.
- **`game/systems.py`**
  - `Machine`: campo `analyzing` (não vai no save), `is_microscope`, storage de 4 slots no `__post_init__`, entra em `is_logistic` e `needs_chip`.
  - `GameState`:
    - `nearby_microscope`, `microscope_put` (só gelo), `microscope_blocker`, `microscope_roll`, `_update_microscope`;
    - roteamento: `interactable_at`, `in_reach`, `interaction`, `dismantle_returns` (devolve o gelo e as amostras);
    - `_update_machines`: o microscópio entra no laço principal `working_machines`. Roda em qualquer camada e já recebe o `work_dt` com o fator de energia.
  - Todos os pontos do `is_collector` em `systems.py` foram seguidos.
- **`tests/test_microscope_v08.py`** (novo, 26 testes): registro, diagrama do lab, texto do aviso, build só com o diagrama, 1 gelo por análise, chances em 20k sorteios, limites do sorteio, amostra no slot fixo, "nada" também gasta gelo, `out_full`, progresso guardado, `no_ice`, caverna, déficit de energia, consumo, `microscope_put`, E/alcance, logística com chip, desmonte.
- **`tests/test_lab_v08.py`**: o `test_microscope_is_not_scannable_yet` (regra do M3) virou `test_scanning_the_tank_does_not_give_the_microscope`. O `SCAN_BLUEPRINT ==` agora tem as duas chaves.
- **`tests/test_fabricator.py`**: as duas listas da aba Automação ganham o `"microscope"` depois do `"cultivator"`.

## Testes

```
uv run pytest tests/test_microscope_v08.py tests/test_lab_v08.py tests/test_props.py tests/test_energy.py \
  tests/test_fabricator.py tests/test_cultivator_v08.py tests/test_water_v08.py -q
220 passed in 8.21s
```

Rodei também os testes genéricos que passam por todas as receitas e diagramas: `test_constructor`, `test_ui_size`, `test_hud_text`, `test_remap_crafts`, `test_ui_b2` e `test_drones`. Deu 243 passed. O pytest inteiro não rodou (fica pro merge).

## O App com o `("microscope", m)` (sem painel ainda)

Não quebra, mas tem duas esquisitices até a Task 7:
- **Rótulo do E:** o `_e_label` cai no `return` final da drill e mostra "[E] Abrir drill". Não dá crash, porque o `stored` devolve 0 pra quem não é drill.
- **Apertar E:**
  - nenhum `elif` pega o alvo, e o código cai no `elif state.in_base_zone()`;
  - **dentro da zona da base, o E abre o fabricador**, e fora dela não faz nada.

Deixei o `app.py` intocado pra não brigar com a Task 7. Se o gerente quiser blindar antes, bastam um `elif target and target[0] == "microscope": pass` no handler do E e um `"[E] Microscópio"` no `_e_label`.

O aviso do scan sai do `C.BLUEPRINTS[event[1]]` (`app.py:1881`), então mostra "Projeto liberado: Microscópio". Tem teste.

## Diferente do plano

- O teste está em `tests/test_microscope_v08.py`, e não em `tests/test_lab_tools_v08.py` (seção "Execução em paralelo").
- `make_microscope` usa `Machine(...)` + `state.machines.append`, no molde do `make_collector`, porque o `build_now` precisa do diagrama e de um chão livre. O build pelo construtor tem um teste próprio, com `free_spot` e `stand_at`.
- Nomes reais dos helpers:
  - `lab_prop` e `new_game` vêm do `tests/test_lab_v08.py`;
  - `tick` vem do `tests/test_cultivator_v08.py`;
  - a fixture `game` vem do `tests/test_base.py`;
  - em vez de `C.STACK_LOOT`, o teste usa `max_stack(...)`.
- O diagrama entrou nos literais do `BLUEPRINTS`/`RECIPE_BLUEPRINT`/`DIAGRAM_BENCH` (linhas ~781–792), não no bloco novo, porque o `DIAGRAM_ITEMS` é derivado logo ali.
- Dois testes antigos foram ajustados (`test_lab_v08`, `test_fabricator`). Eles afirmavam a regra do M3, de que o microscópio não escaneia, e a ordem antiga da aba.
- **Drones (Task 5):** o microscópio já é `is_logistic`, mas o `drones.can_send`/`can_receive` ainda não o conhece. Com chip, ele seria tratado como um baú (recebe qualquer item logístico, em qualquer slot). Hoje isso não acontece no jogo, porque sem painel ninguém liga o chip nem configura o Envia/Recebe. A Task 5 precisa fechar isso.
- O save continua na v16. Nada no `save.py` (é a Task 8).
