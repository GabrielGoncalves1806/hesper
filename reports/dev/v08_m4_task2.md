# v0.8 M4 · Task 2 · As 3 amostras

## Mudanças por arquivo
- `game/render.py`: `item_icon` agora usa `icon_sample_*.png` (mesma linha das culturas).
- `game/inventory.py`: `max_stack` empilha amostra como loot (20); antes caía em STACK_MACHINE (5).
- `game/config.py`: `ORE_COLORS` ganha as 3 amostras (a pepita do drone em `render.py:1984` e os floaters davam KeyError).
- `tests/test_samples_v08.py` (novo, 8 testes): logística; `chest_label_icons` cobre todo `LOGISTIC_ITEMS` (16x16); rótulo do baú desenha com tudo ligado; ícone == PNG aprovado byte a byte (falhou antes do render.py); seção DRONES com 16 itens cabe na `GRID_W`; título DRONES não estoura (cai nos nomes curtos / contagem); cor de pepita; empilhamento.

## Testes
`pytest tests/test_samples_v08.py test_water_v08 test_cultivator_v08 test_drones test_logistics test_ui_b2 test_chest_name` -> 195 passed.

## Diferente do plano
- Teste da seção DRONES: o `test_chest_toggles_wrap_with_the_crops` já conta 16; deixei ele e fiz um teste próprio no arquivo novo.
- Achei 2 lugares além do render: `max_stack` e `ORE_COLORS` (acima). Cores escolhidas por mim, sem aprovação do dono (ajustar se quiser).
- Não usei `SHORT_NAME` pras amostras: o título já cai pra contagem ("envia 3") quando não cabe.
