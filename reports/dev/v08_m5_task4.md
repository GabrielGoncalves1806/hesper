# v0.8 M5 · Task 4 · Drone nv.2

## Mudanças
- `game/drones.py`: `Drone.tier = 1`; as propriedades `speed`, `pickup_time` e `drop_time` (o tier 2 usa `DRONE_T2_SPEED` e os tempos × `DRONE_T2_HANDLING`). `_fly`, `lift` e os timers de pegar/soltar usam o drone. `DRONE_TIERS`/`TIER_ITEMS`, `tier_of(item)` e `item_of(drone)`. `dock(..., tier=1)`.
- `game/systems.py`: `station_dock` aceita `drone` e `drone_t2`. `station_dock_slot(machine, slot, item="drone")`. `station_undock` devolve o item do tier. `dismantle_returns` conta cada tier no item dele. `drones_docked` conta os dois tiers.
- `game/app.py`: a baia e o arrastar pra estação aceitam qualquer drone (`drones.tier_of`), e o item segurado vai pro `station_dock_slot`.
- `game/save.py`: cada slot vira `[resource, cargo, tier]`. O formato de 2 elementos (ou um tier inválido) carrega como tier 1. **`SAVE_VERSION` não mudou.**
- `game/render.py` (só o drone): `drone_frame(t, offset, tier=1)` usa `drone_t2.png` no tier 2, com o `drone` de fallback. Usado no drone pousado e no voando. `drone_icon(tier)`, `item_icon("drone_t2")` → `icon_drone_t2.png` e `machine_preview("drone_t2")` (×3).
- `game/ui.py` (poucas linhas, com o import local como no resto da UI): no painel da estação, o ícone de cada baia segue o tier. A categoria "ITEM" vale também pro `drone_t2`.
- `tests/test_drones.py`: o teste do save espera o 3º elemento (tier).

## Testes
- Novo: `tests/test_m5_drone_v08.py` (14). Cobre o tier e os números, o percurso fixo (o nv.2 chega em menos de 0,75× o tempo do nv.1), a rampa do lift, pôr/tirar/pousar pela baia, desmontar com os dois tiers, o round-trip do save, o save antigo e o tier inválido, e o `drone_frame`/ícone do tier 2 com o fallback.
- Passando: `test_m5_drone_v08`, `test_drones`, `test_drones_cave`, `test_logistics`, `test_save`, `test_station_slots` e `test_panel_cursor` (148).
- Render headless (estação + drone nv.2 voando + ícone) sem erro. O painel da estação não foi desenhado em teste.

## Riscos
- O `render.py` também é mexido pela Task 2 (luminárias) e pela Task 1 (o dict do `machine_preview`). O meu `if kind == C.DRONE_T2` fica logo depois do `if kind == "drone"`, então pode dar conflito de texto perto dali.
