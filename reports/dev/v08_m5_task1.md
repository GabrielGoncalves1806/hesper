# v0.8 M5 · Task 1: traje nv.2, botas e Mochila T2 (lógica e save)

## O que entrou
- `config`: `EQUIP_SLOTS` ganhou `"boots"` e `EQUIP_LABEL["boots"] = "BOTAS"`.
- `equipment.py`:
  - `is_equipment` usa o `EQUIP_SLOT_OF`, e entrou o `slot_of`;
  - `Equipment` ganhou `filled(slot)`, `has(item)` (o item exato), `equip` no slot do item, `o2_max` (400/220/100) e `backpack_rows` (0/1/2);
  - `from_data` aceita o nv.2 no slot do nv.1 e o slot das botas.
- `systems.py`:
  - `player_speed` × `BOOTS_SPEED` com as botas (o F3 multiplica junto). A tempestade continua com a constante crua;
  - `sync_backpack` usa 16 + 8 × `backpack_rows`;
  - `has_scanner` e `has_backpack` usam `filled`;
  - `can_equip(item, free_index, back_to_inventory)` novo: na troca T2 → nv.1, as linhas que somem têm que estar vazias (`backpack_not_empty`) e o item que sai tem que caber (`inv_full`). O `equip_from` e o `equip_item` usam ele.
- `save.py`:
  - `SAVE_VERSION = 17` e `_v16_to_v17`, que não muda nada (documentado), em `MIGRATIONS[16]`;
  - o inventário carrega com 16, 24 ou 32 slots;
  - o `equipped_ever` filtra pelo `EQUIP_SLOT_OF`.
- `render.py`: `suit_icon(item)` novo, usado pelo `machine_preview` e pelo `item_icon` dos 6 itens do traje:
  - usa o `icon_<item>.png`;
  - sem ele: o desenho antigo nos 3 de sempre, o ícone do nv.1 no tanque nv.2 e na T2, e o placeholder nas botas.
- Callers de `has` revisados:
  - **`ui`:** HUD do O₂ (`slots["o2_tank"]`, e o ícone é o do tanque equipado), detalhe do slot do traje e `item_category`;
  - **`app`:** clique com a mão no slot (aceita nv.1 ou nv.2 e confere `can_equip` antes de gastar a mão) e tooltip;
  - **`owns`** continua com `has(item)` exato.

## Diferente do plano
- **Não precisei de `xfail` no `test_tab_inventory_layout`.** O slot das botas entrou provisório no cartão do traje (canto de baixo à esquerda), sem colidir com nada em nenhum dos `SIZES`. Só atualizei a lista esperada do `equip_rects` pra `[..., "boots"]`. A Task 5 reescreve o teste.
- **UI provisória (feia, sem crash):**
  - no Tab, com o tanque equipado, o "400 s" encosta no slot das botas;
  - a mochila T2 mostra as 2 linhas em cima (`ui.backpack_extra`: a janela cresce 22 px na T2, no Tab e no painel lateral). Cabe em 480×270.
- **Fora da lista de arquivos da task:**
  - `game/app.py` (o clique com a mão perderia o item na troca recusada) e `game/ui.py` (callers de `has`);
  - o `render.item_icon` também usa o `suit_icon` (sem ele, o nv.2 virava a prévia encolhida).
- **`equip_item` recusado devolve `None` sem mexer em nada.** O app confere `can_equip` antes, então a mão não perde o item.
- **Testes antigos que fixavam o save v16 passaram pra 17 (ou `SAVE_VERSION`):**
  - `test_save.py` (o hook de migração de teste virou v17 → v18), `test_base.py`, `test_pockets.py`, `test_props.py` e `test_cultivator_v08.py`;
  - os dicts de slots em `test_equipment.py` e `test_save.py` ganharam `"boots": None`.
- Atenção no merge: o `test_cultivator_v08.py` também pode ser mexido pela Task 3.

## Testes
- `tests/test_m5_suit_v08.py` (23 testes): `Equipment`, tanque nv.2, botas + F3, T2 com 32 slots e troca recusada, save v17 round-trip, v16 → v17, scanner, `machine_preview` e ícone dos 6 itens, Tab e painel lateral sem crash em 3 tamanhos.
- Rodados e passando: `test_m5_suit_v08`, `test_backpack`, `test_equipment`, `test_save`, `test_remap_crafts`, `test_hud_text`, `test_ui_b2` e `test_cultivator_v08`.
- Também rodei os que citam save/equipamento: `test_base`, `test_bench_t2`, `test_fabricator`, `test_drones`, `test_logic`, `test_magmatite`, `test_melter`, `test_map_view`, `test_pockets`, `test_stages_v04`, `test_thaw`, `test_worlds`, `test_water_v08` e `test_props`. Passaram todos.
- **Não rodei o pytest inteiro.**
- Prints headless de conferência (fora do repo) na pasta do scratchpad.
