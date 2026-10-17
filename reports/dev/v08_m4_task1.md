# v0.8 M4 · Task 1: trava de receita por estágio

## Mudanças
- `game/systems.py`: `recipe_status` devolve "locked" também com `stage < unlock_stage`; docstring atualizada.
- `game/ui.py`: novo `unlock_text(kind)` ("LIBERA NO ESTÁGIO ALGAS" / "LIBERA EM TI 500"); o botão do fabricador usa ele.
- `game/app.py` (`build_missing`): "Libera no estágio Algas" ou "Libera em Ti N".
- `tools/dev/smoke.py` (`build_at`): sobe o estágio junto com o Ti e restaura no `finally`. Não há outro lugar do smoke que libere por Ti.
- `tests/test_stage_lock_v08.py` (novo): 3 testes (trava por estágio, sem trava nas máquinas padrão ignorando `getattr(C, "CENTRIFUGE", None)`, `unlock_text`).
- `balance_sim.py` não mudou (fica pro M5).

## Testes
`uv run pytest tests/test_stage_lock_v08.py tests/test_fabricator.py tests/test_ui_b2.py tests/test_ui_size.py -q` -> 97 passed. (Vermelho antes: 2 failed.)

## Diferente do plano
- Teste em `test_stage_lock_v08.py`, sem skipif (instrução do gerente).
- O App não chama `ui.unlock_text`; monta a frase própria com `STAGES[n-1].name.capitalize()`.
