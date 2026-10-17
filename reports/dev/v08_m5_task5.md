# v0.8 M5 · Task 5: Tab A e painéis laterais

## O que entrou (`game/ui.py`)
- **Constantes do Tab A:** `TAB_SUIT_W = 96`, `TAB_DETAIL_W = 142` e `TAB_COL_GAP = 8`.
  - `TAB_INV_W = 446`, calculado como `10 + 174 + 8 + 96 + 8 + 142 + 8`.
  - `TAB_INV_H = 174`, calculado como `40 + 4×32 − 2 + 8`. Antes era 178, ou 210 com a mochila.
  - `TAB_BARE_H = 104`: a janela fora do Tab, sem traje.
  - `SUIT_ROW_Y = (44, 85)` e `SUIT_CELL_W = 46`.
- **`backpack_extra(slots)`** agora devolve `BACKPACK_ROW_H × linhas`: 0, 32 ou 64. É o que o plano e o mock pedem (148 no painel lateral com a T2). Antes era 0, 32 ou 54.
- **`backpack_label(slots)`** novo: "MOCHILA T2" com 32 slots e "MOCHILA" com 24. Vale no Tab e no painel lateral.
- **`_tab_inventory`** agora tem 3 colunas:
  - **esquerda:** as grades (mochila em cima, depois INVENTÁRIO e HOTBAR);
  - **meio:** o cartão do TRAJE (96 de largura);
  - **direita:** o detalhe.
  - A altura é **a mesma com ou sem mochila** (174), porque quem manda é o cartão do TRAJE.
  - Sem `equipment` (fora do Tab), a coluna do TRAJE some.
- **`_suit_card(equipment, rect, …)`** foi reescrito:
  - o Explorador fica em cima e os 4 slots de `C.EQUIP_SLOTS` em 2×2, cada um centrado numa célula de 46, com o rótulo centrado em `sy+21`;
  - o estado só aparece no tanque (`round(o2_max)` mais " s": 220 s no nv.1, 400 s no nv.2) e nos slots vazios ("vazio"). O "equipado" saiu;
  - as linhas ligam o tanque e o scanner ao corpo.
- **`_backpack_slot` virou `_equip_slot(equipment, kind, …)`:**
  - com item, mostra o item e a borda ciana;
  - vazio, mostra o fantasma `item_icon(kind)` com alpha 45 (as botas usam o placeholder até o PNG chegar);
  - entra no `equip_rects`. O clique (`app.on_equip_click`) não precisou mudar.
- **Painel lateral:** a janela "Inventário" fica com `84 + backpack_extra` de altura, ou seja 148 com a T2, e usa o rótulo novo.
- **Barra das abas:** agora fica centrada na tela.
  - Antes, a janela do Inventário (largura par) e a de LOGs (375, ímpar) arredondavam o centro pra lados diferentes, e a barra pulava 1 px ao trocar de aba.
  - A barra continua no mesmo y nas duas abas, porque o `inv_tabs_top` sai da janela mais alta, a de LOGs.
- **Atributos novos do `UI`:**
  - `inv_window`, `suit_rect` e `detail_rect`;
  - `suit_text_rects`: a caixa da tinta de cada rótulo e estado do TRAJE, medida pelo novo helper `_ink`. Os testes usam essas caixas pra conferir que o "400 s" não encosta em nada.

## Testes
- **`tests/test_m5_tab_v08.py` (83 testes, escritos antes do código, TDD):**
  - `backpack_extra` e as constantes;
  - as 3 colunas e a janela de 446×174 nos 3 tamanhos, com traje vazio, nv.1 e T2;
  - o 2×2 do TRAJE na ordem tanque, scanner, mochila, botas;
  - os textos do TRAJE com pelo menos 1 px de folga de todos os slots e de todos os outros textos;
  - "220 s" e "400 s" no tanque e "vazio" só nos slots vazios;
  - o rótulo "MOCHILA" ou "MOCHILA T2", no Tab e no painel lateral;
  - as linhas da T2 em cima;
  - o fantasma com alpha 45;
  - a barra das abas igual no Inventário e no LOGs;
  - o hover no slot das botas mostrando as botas no detalhe;
  - os painéis laterais com 32 slots: 12 máquinas × 3 tamanhos, `inv_window.h == 148`, sem sobreposição e acima da moldura da hotbar;
  - o clique no 4º slot pelo `App`: botas na mão equipam, e a mão vazia tira.
- **`tests/test_backpack.py::test_tab_inventory_layout`:**
  - roda com `suit` ∈ {none, nv1, t2} × `SIZES`;
  - confere o `equip_rects` com os 4 slots, as 3 colunas e as linhas da mochila em cima (32 ou 64);
  - não havia `xfail` pra tirar (a Task 1 não pôs nenhum).
- **Rodados e passando (409):** `test_backpack`, `test_m5_tab_v08`, `test_equipment`, `test_m5_suit_v08`, `test_ui_b2`, `test_ui_size`, `test_hud_text`, `test_logs_tab`, `test_constructor`, `test_m4_panels_v08` e `test_cultivator_v08`.
- **Rodei também todos os testes que citam `draw_inventory`, `equip_rects` ou `inv_tab`:** 424 passaram. **Não rodei o pytest inteiro.**

## Prints (headless; script descartável no scratchpad, a Task 6 faz o `shot_v08_m5.py`)
- `reports/dev/v08_m5_tab_nv1.png`: mochila nv.1 e tanque nv.1.
- `reports/dev/v08_m5_tab_t2.png`: Mochila T2, tanque nv.2 e botas, com as 32 casas cheias.
- `reports/dev/v08_m5_lateral_t2.png`: baú grande aberto, com a T2.

### Diferenças em relação ao mock
1. **A janela do Tab fica no topo (y = 6 no Grande), não no meio como no mock.** É a regra que já existia: o `inv_tabs_top` usa a janela mais alta, e a de LOGs tem 208 de altura com os 24 LOGs. É isso que faz as abas não pularem ao trocar. A janela de 174 fica pendurada embaixo da barra.
2. **2ª linha de slots do TRAJE em `+85`, não em `+84`.** Com `+84`, o "vazio" das botas ficava a 0–1 px da borda do cartão. Com `+85`, sobra 1 px entre texto e slot e entre texto e borda, e o teste garante essa folga.
3. **O tanque mostra o número de verdade:** 220 s no nv.1 e 400 s no nv.2. O "180 s" do mock era só ilustrativo.
4. **O detalhe da fibra mostra "PEÇA", não "RECURSO".** O nome quebra em 2 linhas, e o "USADO EM" mostra 2 receitas e "+ 2 receitas" (o mock mostrava 3 linhas). É o `_item_detail`/`item_category` de sempre, que não mexi.
5. **Botas:** com as botas equipadas aparece o placeholder rosa, e vazias aparece o fantasma escuro do placeholder. Vai trocar quando o PNG da rodada 4 entrar. O layout não depende do conteúdo do ícone.
6. **O print da T2 não tem o scanner equipado** (o pedido era T2, tanque nv.2 e botas), então o scanner aparece com o fantasma e "vazio".

### Problema que já existia, não é desta task (vale olhar)
- **No Grande (480×270), o painel do baú com a seção DRONES (as 16 fileiras de toggle do M4) passa da moldura da hotbar e cobre a linha de ajuda.** Dá pra ver no `v08_m5_lateral_t2.png`.
  - Medi: os botões de logística vão até y = 220 no baú e 242 no baú grande, e a moldura fica em 214.
  - Acontece **igual com 16, 24 ou 32 slots**, porque o painel do baú é mais alto que a janela do inventário. Não foi a T2 que causou.
  - O `test_chest_panel_layout_shows_extra_row` não pega isso porque só confere `slot_rects`.
  - A janela do inventário (148) cabe em todos os tamanhos.

## Arquivos
- `game/ui.py`
- `tests/test_backpack.py`
- `tests/test_m5_tab_v08.py` (novo)
- `reports/dev/v08_m5_tab_nv1.png`, `v08_m5_tab_t2.png` e `v08_m5_lateral_t2.png`
- Não commitei, não abri o jogo em janela e não mexi em `assets/`.
