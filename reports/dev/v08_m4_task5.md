# v0.8 M4 Task 5: Drones

- `game/drones.py`: `can_send`, `can_receive`, `receive_slot` e `stock` conhecem Microscópio (recebe `ice` no `MIC_ICE_SLOT`, manda as 3 amostras) e Centrífuga (recebe `algae` e as 3 amostras, manda `plant_1..3`).
- `stock` só oferece a saída (nunca gelo, alga nem amostra de entrada).
- Amostra de tipo diferente na centrífuga: não precisou código novo, o `Ledger.room` ja usa `slot_room` (0 se o slot tem outro item), igual ao minério da Fundição.
- Testes: `tests/test_m4_drones_v08.py` (5, incluindo entrega de ponta a ponta baú → microscópio → baú).
- Pytest do arquivo + drones/logistics/water/cultivator/microscope/centrifuge: 203 passando. Não commitado.
