# v0.8 M4 Task 8: Save

- `game/save.py`: `microscope_storage` / `centrifuge_storage` (slots fixos, helper `_fixed_slots_storage`); `machine_to_dict` salva `timer` das duas; `machine_from_dict` usa os storages e limita o timer. A Centrífuga aceita qualquer `SAMPLE_ITEMS` no slot da amostra.
- `SAVE_VERSION` continua 16 (comentário atualizado).
- `tests/test_m4_save_v08.py`: round-trip das duas, slots sujos/timer limitado, round-trip de estado completo (diagrama `microscope`, amostras no inventário e num baú).
- pytest (arquivo novo + test_save, water, cultivator, microscope, centrifuge): 208 passed. Sem commit.
