# v0.8 M5 Task 3: Adubo

- `Machine.boost` (s de adubo, 0..FERTILIZER_MAX). `cultivator_put` com `fertilizer` gasta 1, soma `FERTILIZER_TIME`, recusa no teto (600 s) sem gastar; não ocupa slot.
- `_update_cultivator`: com boost, `growth` avança ×`FERTILIZER_BOOST`; `need` = `(1-growth)*cycle/rate`; água e biomassa seguem o tempo real. O boost desce só no tempo de crescimento (parado/seco/fora da base não gasta; o passo é cortado quando o boost acaba).
- Save: `boost` no cultivador, clamp `[0, FERTILIZER_MAX]`, default 0. `SAVE_VERSION` intocado.
- App: shift+clique/direito põem 1 por vez; aviso "Adubo no máximo (10 min)" e o aviso de itens aceitos atualizado.
- UI: selo "ADUBO m:ss" (verde) sob o "BIO/S", no meio do painel. Print: `reports/dev/v08_m5_adubo_painel.png` (script `tools/dev/shot_v08_m5_adubo.py`).
- Testes: `tests/test_m5_fertilizer_v08.py` (7) + cultivator/save/m4_panels: 143 passando (antes do ajuste final do selo, reroda ok).
