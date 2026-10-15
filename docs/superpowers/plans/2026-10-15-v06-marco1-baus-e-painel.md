# v0.6 Marco 1 · Baús e painel · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** três tamanhos de baú (Simples 8, Normal 16, Grande 24 com diagrama), a caixa de saque dos destroços passa a guardar item e desmontar, o contêiner guarda item, e todos os painéis de transferência ganham a pilha no cursor (igual à tela de inventário). Save v11.

**Arquitetura:** os três baús são o mesmo `Machine` de hoje com `kind` diferente: `Machine.is_chest` passa de `kind == "chest"` pra `kind in C.CHEST_KINDS`, e o tamanho do inventário sai de `C.CHEST_SIZES[kind]`. O Baú Grande usa o mecanismo de diagrama que já existe (`BLUEPRINTS`/`RECIPE_BLUEPRINT`/`DIAGRAM_BENCH`). A caixa de saque e o contêiner continuam sendo `wrecks.Crate` (não viram `Machine`); ganham "guardar" no painel e a caixa ganha um caminho de desmonte próprio. O painel com cursor reaproveita `app.held` e os métodos por slot do `Inventory` (`put`, `take_half`).

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-v06-logistica-design.md` (Marco 1). Bíblia §14.

## Restrições globais
- Baús (números de partida, `game/config.py`):

| id | Nome | Slots | Custo | Libera | Sprite fechado / aberto | Tamanho do PNG |
|---|---|---|---|---|---|---|
| `chest_small` | Baú simples | 8 | 3 ferro | Ti 0 | `loot_crate` / `loot_crate_empty` | 32×32 |
| `chest` | Baú | 16 | 6 ferro | Ti 50.000 | `chest` / `chest_open` | 32×40 |
| `chest_large` | Baú grande | 24 | 10 ferro + 2 silício | diagrama lido | `container_sealed` / `container_open` | 40×44 (pé no centro de baixo do tile, como as máquinas de 40 px) |

- Todos ocupam 1 tile. Ícones: `icon_chest_small`, `icon_chest`, `icon_chest_large` (os dois novos vêm da Designer; até aprovar, fallback = o sprite fechado reduzido pra 16×16).
- `diagram_chest_large`: item não colocável, fabricado no **T1**, `unlock_ti = 90_000`, custo 10 ferro + 4 silício + 2 `iron_ingot`, categoria "tools", ícone `icon_diagram`. Lido na bancada (`DIAGRAM_BENCH = "t1"`) libera `chest_large` no construtor.
- Baú de qualquer tamanho: nome, Envia/Recebe/Lote, Pegar tudo/Guardar tudo, desmonta só vazio, entra na rede dos drones, conta como baú da base pro fabricador.
- **Caixa de saque (`loot_crate` dos destroços)**: aberta, aceita guardar item (8 slots). **Fica fora da rede dos drones** (decisão do gerente, ver abaixo). Segurar o botão direito 2 s com ela vazia desmonta: devolve `C.CRATE_DISMANTLE_RETURN = {"iron": 3}`, o tile vira chão (`SAND`) e a caixa some de vez (inclusive depois de carregar o save). Com item: aviso igual ao do baú ("Esvazie a caixa antes").
- **Contêiner**: aberto, aceita guardar item; **não desmonta** (o clique direito segurado não faz nada nele).
- **Painel com cursor** (modos de `PANEL_MODES`: baú, caixa/contêiner, drill, derretedor, dispersor, estação):
  - clique esquerdo num slot (de qualquer lado): `held = inv.put(i, held)` (pega, solta, junta ou troca);
  - clique direito: mão vazia pega metade (`take_half`); com pilha na mão solta 1;
  - **Shift+clique esquerdo** mantém o comportamento de hoje (manda direto pro outro lado: `quick_move`, `drill_take` tudo, etc.);
  - slot que não aceita o item recusa: a pilha fica no cursor, toca o som de erro de hoje e mostra o aviso de hoje ("A drill só produz", "Só gelo", "Só cápsula", "Só drone");
  - drill: só tira (soltar na drill recusa); derretedor: slot de entrada só `ice`, slot de saída só tira; dispersor: só `water_capsule`; estação: slots de drone só `drone` (1 por slot), slot travado "EM VOO" recusa; sobras da estação só tiram;
  - efeitos colaterais de hoje continuam quando o item sai/entra pelo cursor: `drill_collected` + evento `drill_collect`, evento `loot` da caixa, `drones_docked`;
  - fechar o painel (ou trocar de modo) com pilha na mão: `stash_held` devolve pro inventário; não cabendo, pro inventário aberto do painel (baú, caixa, contêiner); não cabendo, fica na mão como hoje. Nada some.
- Save **v11** (`SAVE_VERSION = 11`, `FIRST_VERSION` continua 10): `MIGRATIONS[10]` troca `kind == "chest"` por `"chest_large"` em todas as máquinas de todas as camadas (nome, itens, Envia/Recebe/Lote mantidos). Caixas: o conteúdo guardado já vai no `crates` de hoje; caixa desmontada vai como marcador.
- UI: nada de UW/UH/HOTBAR fixos em código novo; mouse via `app.mouse_ui`; superfície nova sempre com formato explícito (teste AST existente). Não abrir janela, não commitar, não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/`, `settings.json`.

## Decisões (o dono deveria ver)
- **Caixa de saque fora da rede dos drones** (aprovado pelo dono). A spec dizia que ela entraria como baú; o código dos drones só conhece `Machine` (precisa de `sends`/`receives`/`batch`/`anchor`/`size`, `_exists`), e a caixa fica nos destroços, longe da base. Ela guarda e desmonta; drone nela fica pra depois se fizer falta.
- Objetivo "Construa um baú" passa a valer pra qualquer um dos três.
- `Machine.is_chest` cobre os três; nenhum outro lugar compara `kind == "chest"`.

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | `CHEST_KINDS`, `CHEST_SIZES`, `CHEST_SLOTS` vira o do Grande (24, só pra compatibilidade), `MACHINES` dos três baús + `diagram_chest_large`, `MACHINE_ORDER`, `MACHINE_CATEGORY`, `BLUEPRINTS`/`RECIPE_BLUEPRINT`/`DIAGRAM_BENCH`, `CHEST_DIAGRAM_COST`, `CRATE_DISMANTLE_RETURN`, sprites/tamanhos por baú |
| `game/systems.py` | `is_chest`, tamanho do storage, `sprite_rect` por tipo, `crate_put`, desmonte da caixa (`dismantle_crate`, caminho no `_update_dismantle`), `stash` |
| `game/inventory.py` | nada novo esperado (usar `put`/`take_half`/`quick_move`) |
| `game/app.py` | `on_panel_click` com cursor, Shift mantém o atalho, `stash_held` com caixa, alvo de desmonte na caixa, dicas com `len(machine.storage)` |
| `game/ui.py` | `_chest_panel` com altura e posição da logística pelo número de linhas, `_crate_panel` sem "Só dá pra tirar", textos de ajuda dos painéis |
| `game/render.py` | `chest_surface(kind, opened)`, ícones/fantasma/prévia por tipo |
| `game/art.py` | fallback dos ícones novos |
| `game/objectives.py` | "Construa um baú" aceita qualquer `CHEST_KINDS` |
| `game/wrecks.py` / `game/layers.py` | caixa removida não volta da seed |
| `game/save.py` | v11, `MIGRATIONS[10]`, storage por tipo, marcador de caixa desmontada |
| `game/map_view.py` | destroço sem caixa (desmontada) não quebra o marcador |
| testes | `tests/test_chest_sizes.py`, `tests/test_panel_cursor.py`, `tests/test_crate_storage.py` (novos); ajustes nos que fixam 24 |
| `tools/dev/shot_v06_m1.py` | print avulso pro dono |

---

### Task 1: três baús e o diagrama do Grande
**Interfaces:** `C.CHEST_KINDS = ("chest_small", "chest", "chest_large")`; `C.CHEST_SIZES = {"chest_small": 8, "chest": 16, "chest_large": 24}`; `C.CHEST_SPRITES = {kind: (fechado, aberto)}`; `Machine.is_chest -> kind in C.CHEST_KINDS`; `Machine.storage` com `C.CHEST_SIZES[kind]` slots; `Renderer.chest_surface(kind: str, opened: bool)`; `MACHINES["diagram_chest_large"]` (unlock_ti 10_000).
- [x] Teste (`tests/test_chest_sizes.py`): cada tipo nasce com 8/16/24 slots; os três são `is_chest`, `is_logistic` e aparecem em `state.chests`/`base_chests`; construir `chest_small` e `chest` no começo dá `ok`; `chest_large` dá `"blueprint"` antes de ler o diagrama e `ok` depois (com material); `diagram_chest_large` no T1 dá `"locked"` com Ti < 10.000 e `ok` com Ti ≥ 10.000 e material; desmontar cada um vazio devolve o custo dele; com item não desmonta; objetivo "Construa um baú" fecha com qualquer um dos três.
- [x] Rodar: falha.
- [x] Implementar config, `is_chest`, storage, `sprite_rect` (tamanho do PNG por tipo), render (mundo, aberto quando `open_chest`, fantasma, prévia do construtor, ícone, contorno), fallback de ícone em `art.py`, objetivo. Trocar os `C.CHEST_SLOTS` fixos por `len(machine.storage)` (app.py ~1846, testes que procuram a grade por `len == 24`).
- [x] Painel do baú (`ui._chest_panel` / `_side_panels`): `side_h` e o `y` do `draw_logistics` derivados das linhas (`ceil(len(box) / 8)`), em vez do `y + 100` fixo. Conferir `test_backpack.py::test_chest_panel_layout_shows_extra_row` e `test_hud_text.py`.
- [x] `uv run pytest` verde.

### Task 2: caixa de saque guarda e desmonta; contêiner guarda
**Interfaces:** `GameState.crate_put(crate, index: int, amount: int | None) -> int`; `GameState.dismantle_crate(crate) -> bool`; evento `("crate_not_empty",)`; `Layer.removed_crates: set[tuple[int, int]]`; `C.CRATE_DISMANTLE_RETURN = {"iron": 3}`.
- [x] Teste (`tests/test_crate_storage.py`): caixa aberta aceita item do inventário e devolve; contêiner idem; caixa fechada (não aberta) não aceita; desmontar caixa vazia devolve 3 ferro, tile vira `SAND`, some de `layer.crates`; com item não desmonta e emite `crate_not_empty`; inventário sem espaço pro ferro: não desmonta (regra do tudo-ou-nada de hoje); contêiner não desmonta; ida e volta do save: caixa com item guardado volta com o item, caixa desmontada não volta da seed; `map_view` não quebra com destroço sem caixa.
- [x] Rodar: falha.
- [x] Implementar: `crate_put`; alvo de desmonte em `app.controls()` quando o mouse está numa caixa (`hovered_crate`, só `Layer.crates`, não `containers`); `_update_dismantle` aceita a caixa (mesma barra de 2 s e trava por tentativa); `dismantle_crate`; `Layer.removed_crates` no save (lista `removed_crates` por camada) e no load pula essas caixas e mantém o tile em `SAND` (já vai pelo `changed_tiles`); `_crate_panel` sem "Só dá pra tirar" (caixa vazia: "VAZIA · dá pra guardar coisas"); aviso `crate_not_empty`.
- [x] `uv run pytest` verde.

### Task 3: painel com a pilha no cursor
**Interfaces:** `App.on_panel_click(button)` usa `self.held`; `App.panel_put(side_inv, index, button) -> bool` (helper único que aplica a regra do slot e os efeitos colaterais); `App.stash_held()` cobre caixa e contêiner.
- [x] Teste (`tests/test_panel_cursor.py`, app headless como nos testes que já usam `app.held`): no baú, clique esquerdo pega a pilha e outro clique solta no slot escolhido (no baú e no inventário); junta mesmo item; troca item diferente; clique direito pega metade e, com mão cheia, solta 1; Shift+clique manda direto (comportamento antigo); drill recusa soltar e tirar pelo cursor conta em `drill_collected`; derretedor aceita só gelo na entrada; dispersor só cápsula; estação aceita só drone, 1 por slot, recusa slot em voo; caixa tirar pelo cursor emite `loot`; fechar o painel com pilha na mão devolve pro inventário e, cheio, pro baú; nada some em nenhum caminho.
- [x] Rodar: falha.
- [x] Implementar o cursor em `on_panel_click` (manter nome/logística/botões antes, como hoje), helper `panel_put`, `stash_held` com caixa/contêiner, textos de ajuda dos painéis (`_side_panels`): "Clique: pegar/soltar · Direito: metade/1 · Shift+clique: mandar direto".
- [x] `uv run pytest` verde.

### Task 4: save v11 · CANCELADA pelo dono (2026-10-15: "pode jogar fora meus itens"; baú antigo carrega como Normal de 16 e perde os slots 17–24)
- [ ] Teste: save v10 com baú (24 slots, nome, itens, Envia/Recebe/Lote) carrega como `chest_large` com tudo igual; save v11 ida e volta com os três tipos; `test_save.py::test_migration_hook_runs` ajustado (hoje ele finge o v11 com `MIGRATIONS[10]`: passar pra 12/`MIGRATIONS[11]` e restaurar o dicionário no fim); save v9 continua recusado.
- [ ] Implementar `SAVE_VERSION = 11`, `MIGRATIONS[10]`, `machine_from_dict` com `C.CHEST_SIZES[kind]`, docstring do formato.
- [x] `uv run pytest` verde.

### Task 5: print avulso, smoke, bíblia
- [ ] ~~`tools/dev/shot_v06_m1.py`~~ (pulado: o dono testou tudo no jogo) (headless, save/settings em pasta temporária, saída em `reports/dev/v06_m1/`): os três baús lado a lado na base, painel de cada um aberto, pilha no cursor no painel do baú, caixa de saque com item guardado, construtor mostrando o Baú Grande trancado e liberado.
- [x] `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py` passando; olhar os prints do baú.
- [x] Bíblia §14: "Marco 1 · como ficou na implementação" (números, ids, save v11, decisão da caixa fora da rede).
- [x] `uv run pytest` verde.
