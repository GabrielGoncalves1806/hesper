# v0.8 M5 · Materiais e itens: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** as plantas viram material, e os materiais viram itens.
- Na Bancada T2: alga → **fibra**, Folha-gota → **gel hídrico**, Espiral → **resina de geada**, Lírio → **essência** (sem uso na v0.8).
- Com eles: **Mochila T2**, **Tanque de O₂ nv.2**, **Botas de tração**, **Luminária bio**, **Adubo** e **Drone nv.2**.
- O Tab vira o **layout A** (3 colunas, traje com 4 slots).

**Architecture:**
- **Fundação:** os itens, as receitas e os números já estão no `game/config.py`, no bloco "v0.8 M5 · Materiais e itens", feito pelo gerente. Os PNGs aprovados já estão em `assets/sprites/`. Cada task liga o comportamento de um item.
- **Traje:** um slot por tipo, mas agora o slot aceita o nv.1 **ou** o nv.2 (`C.EQUIP_SLOT_OF`). O nv.2 não consome o nv.1: equipar troca, e o nv.1 volta pro inventário.

**Tech Stack:** Python 3 + pygame-ce, pytest, `uv run`.

## Global Constraints

- Bíblia §17, bloco "Plantas viram material" e as decisões de arte. Mapa do código: veja os trechos citados em cada task.
- **Já no config (não redefina):**
  - **Materiais:** `FIBER`, `HYDROGEL`, `FROST_RESIN`, `LILY_ESSENCE`, `MATERIAL_ITEMS` (em `PART_ITEMS`, empilham 20).
  - **Traje:** `BACKPACK_T2`, `O2_TANK_T2`, `BOOTS`, `BACKPACK_T2_SLOTS = 16`, `O2_TANK_T2_MAX = 400`, `BOOTS_SPEED = 1.3`, `EQUIP_SLOT_OF`.
  - **Adubo:** `FERTILIZER` (rende 2 por receita), `FERTILIZER_TIME = 120`, `FERTILIZER_BOOST = 2.0`, `FERTILIZER_MAX = 600`.
  - **Drone:** `DRONE_T2`, `DRONE_T2_SPEED = 9.0`, `DRONE_T2_HANDLING = 0.5`.
  - **Luminária:** `LAMP_BIO` (raio 6, sem energia), `LAMP_BIO_COLOR = (150, 245, 215)`.
  - **Receitas:** todas na Bancada T2 (`T2_RECIPES`), menos a luminária bio, que é do construtor. Os itens de traje estão em `ONCE_ITEMS`.
- **Arte em `assets/sprites/`:**
  - `icon_{fiber,hydrogel,frost_resin,lily_essence,fertilizer,backpack_t2,o2_tank_t2,drone_t2,lamp_bio}.png`;
  - `lamp_bio.png` (16×32, mesma âncora do `lamp.png`);
  - `drone_t2.png` (64×16, 4 quadros, igual ao `drone.png`);
  - `icon_{o2_tank,backpack,scanner}.png` 3D (trocaram os antigos).
  - **`icon_boots.png` ainda não existe**: o dono escolhe na rodada 3. Até lá, o ícone cai no placeholder, e o código tem que funcionar sem ele.
- **Mock do Tab A:** `reports/design/v08_m5_itens/tab_A.png` (cópia em `reports/design/ideias/v08_m5/tab_A_aprovado.png`) e `lado_a_lado_A.png` (painéis laterais), mais a seção "Pro Dev integrar" de `reports/design/v08_m5_itens/index.html`.
- **Save sobe pra v17** (Task 1): o inventário pode ter 32 slots e o traje ganha `boots`. As Tasks 3 e 4 só acrescentam campos novos com default; quem mexe no `SAVE_VERSION` é só a Task 1.
- Sem som novo.
- O Dev **não commita**, **não abre o jogo em janela**, **não roda `build_sprites.py`**, **não mexe em `assets/`**. Não roda o pytest inteiro: só os testes da task e os listados.

## Ondas

| Onda | Tasks | Por quê |
|---|---|---|
| 1 (paralelo) | 1 Traje · 2 Luminária bio · 3 Adubo · 4 Drone nv.2 | arquivos quase todos diferentes |
| 2 | 5 Tab A e painéis laterais | depende da API do traje (Task 1) |
| 3 | 6 Prints e report | depende de tudo |

Cada task tem o seu arquivo de teste: `tests/test_m5_suit_v08.py`, `test_m5_lamp_v08.py`, `test_m5_fertilizer_v08.py`, `test_m5_drone_v08.py`, `test_m5_tab_v08.py`.

---

### Task 1: Traje · nv.2, botas e Mochila T2 (lógica e save)

**Files:** `game/equipment.py`, `game/systems.py` (`o2_max`, `player_speed`, `sync_backpack`, `equip_from`/`equip_item`/`unequip`, `has_backpack`), `game/save.py`, `game/config.py` (só `EQUIP_SLOTS`/`EQUIP_LABEL`), `game/render.py` (só o dict de `machine_preview` dos equipáveis, ~2157), `tests/test_m5_suit_v08.py`

**Interfaces:**
- Produces:
  - `C.EQUIP_SLOTS = ("o2_tank", "scanner", "backpack", "boots")`, `C.EQUIP_LABEL["boots"] = "BOTAS"`;
  - `equipment.is_equipment(item)` = `item in C.EQUIP_SLOT_OF`; `equipment.slot_of(item) -> str`;
  - `Equipment.slots: dict[slot, item | None]`; `Equipment.filled(slot) -> bool`; `Equipment.has(item) -> bool` (aquele item exato equipado); `Equipment.equip(item) -> antigo | None` (no slot `slot_of(item)`); `Equipment.unequip(slot)`;
  - `Equipment.o2_max`: 400 com `o2_tank_t2`, 220 com `o2_tank`, senão `O2_MAX`;
  - `Equipment.backpack_rows -> int`: 0, 1 (nv.1) ou 2 (T2);
  - `GameState.player_speed` × `BOOTS_SPEED` com as botas.

**Regras:**
1. O slot aceita o nv.1 ou o nv.2. Equipar o outro troca, e o antigo volta pro inventário (no slot de onde veio o novo, como hoje).
2. **Mochila:** `sync_backpack` usa `INVENTORY_SLOTS + 8 × backpack_rows` (16, 24 ou 32). Trocar a T2 pela nv.1, ou tirar a mochila, só pode com as linhas que somem vazias (`tail_empty`), senão o evento `backpack_not_empty`, como hoje.
3. **Callers de `has`:** confira cada um (`grep -n "equipment.has\|\.has(\"" game/`). Onde a pergunta é "o slot tem algo" (mochila, scanner, minimapa), use `filled(slot)`. O scanner continua só nv.1.
4. **Botas:** só no `player_speed`. O empurrão da tempestade (`weather.py`) continua com a constante crua.
5. **Ícone/prévia:** o dict de `render.machine_preview` (~2157) quebra com o slot novo. Faça os 6 itens do traje usarem `icon_<item>.png` (com fallback pro art antigo nos 3 de sempre).
6. **Save v17:**
   - `inventory_from_dict` aceita 16, 24 ou 32 slots (hoje é `24 if > 16 else 16`);
   - `Equipment.from_data` aceita o nv.2 no slot do nv.1 e o slot `boots`;
   - `equipped_ever` filtra pelo `EQUIP_SLOT_OF`;
   - `SAVE_VERSION = 17`, `_v16_to_v17` sem mudar o dict (documente), `MIGRATIONS[16]`.

**Testes** (no mínimo):
- equipar o tanque nv.2 dá `o2_max` 400 e o nv.1 volta pro inventário;
- botas: `player_speed` = 120 × 1,3 (e com o F3 multiplica também);
- Mochila T2: inventário 32; trocar pra nv.1 com a última linha cheia é recusado;
- round-trip do save com T2, tanque nv.2 e botas, e 32 slots com item no último;
- save v16 carrega e migra;
- o scanner continua mostrando o minimapa;
- `machine_preview` dos 6 itens do traje não quebra.

Rode também `tests/test_backpack.py`, `tests/test_equipment.py`, `tests/test_save.py`, `tests/test_remap_crafts.py`, `tests/test_hud_text.py` e `tests/test_ui_b2.py`. **O layout do Tab é da Task 5.** Aqui, se o teste de layout do `test_backpack.py` quebrar só por causa do 4º slot ou dos 32 slots, marque com `xfail(reason="layout do Tab A: Task 5")` e conte no report.

---

### Task 2: Luminária bio

**Files:** `game/lighting.py` (`lamp()` aceita cor), `game/render.py` (`cave_lights`, o halo de superfície `machine_light`, `lamp_surface`, `item_icon`, `machine_preview`), `tests/test_m5_lamp_v08.py`

- `lighting.lamp(tx, ty, radius_tiles=5, color=LAMP_COLOR)`. A luminária bio usa `C.LAMP_BIO_COLOR`.
- `render.lamp_surface("lamp_bio")` → o sprite `lamp_bio.png` (fallback: o `art.lamp` tingido, ou o `lamp`).
- Halo de superfície: `"lamp_bio": (C.LAMP_BIO_COLOR, ...)` no mesmo molde do `"lamp"`. Confira se o `lamp_t2` tem halo; se não tiver, não mexa nele.
- O ícone `icon_lamp_bio.png` aparece no construtor e na hotbar.
- Testes: a luz da caverna da bio tem a cor e o raio certos; `lamp_surface` devolve o PNG; constrói sem gastar energia (`power_report` não muda).

---

### Task 3: Adubo

**Files:** `game/systems.py` (`Machine.boost: float`, `cultivator_put`, `_update_cultivator`), `game/save.py` (só o campo `boost` do cultivador), `game/app.py` (recusa/aviso ao pôr o adubo), `game/ui.py` (`_cultivator_panel`: indicador do adubo), `tests/test_m5_fertilizer_v08.py`

**Regras:**
1. `cultivator_put` com `fertilizer`: consome **1** e soma `FERTILIZER_TIME` em `m.boost`, até `FERTILIZER_MAX` (cheio: recusa e não gasta). Não ocupa slot. Shift+clique e clique direito põem 1 por vez.
2. `_update_cultivator`: enquanto `m.boost > 0`, o `growth` avança `FERTILIZER_BOOST` vezes mais rápido. A água e a biomassa por segundo **não** mudam. Ajuste o `need` (o tempo até madura fica `(1 - growth) × cycle / boost`).
3. O `boost` desce com o tempo real de crescimento (só enquanto `blocker is None`). Parado, seco ou fora da base, não gasta.
4. Save: o cultivador salva `boost` (limitado a `[0, FERTILIZER_MAX]`); save sem o campo carrega 0.
5. Painel: um selo pequeno "ADUBO 1:40" (min:s) perto da barra CRESCE quando `boost > 0`. Siga o estilo do painel (cores e fonte) e não empurre nada pra fora.
6. Drones não mexem com adubo.

**Testes:** com adubo, a alga fica madura na metade do ciclo; a biomassa num tempo fixo é a mesma com e sem adubo; o adubo não gasta parado; o teto de 600 s; round-trip do `boost`; pôr no cultivador consome 1.

---

### Task 4: Drone nv.2

**Files:** `game/drones.py` (`Drone.tier`, velocidade e tempos), `game/systems.py` (pôr/tirar drone da estação), `game/app.py` (o slot da estação aceita `drone_t2`), `game/save.py` (o tier de cada drone), `game/render.py` (`drone_frame` com o sprite do tier; ícone), `tests/test_m5_drone_v08.py`

**Regras:**
1. `Drone.tier: int = 1`. Pôr um `drone_t2` na estação cria um drone de tier 2; tirar devolve o item certo (`drone` ou `drone_t2`). Desmontar a estação devolve os itens certos.
2. Tier 2: velocidade `DRONE_T2_SPEED` e `DRONE_PICKUP_TIME`/`DRONE_DROP_TIME` × `DRONE_T2_HANDLING`.
3. Save: cada slot da estação vira `[resource, cargo, tier]`; o formato antigo (2 elementos) carrega como tier 1.
4. Render: `drone_frame(t, offset, tier=1)` usa `drone_t2.png` no tier 2 (fallback: o `drone`). Pousado e voando. O `item_icon("drone_t2")` usa `icon_drone_t2.png`.
5. A contagem de drones (`drones_docked`, o painel da estação) conta os dois tiers.

**Testes:** o tier 2 chega antes num percurso fixo; pôr/tirar/desmontar devolve o item certo; round-trip do save com 1 de cada; save antigo carrega tier 1; `drone_frame` do tier 2 vem do `drone_t2`.

---

### Task 5: Tab A e painéis laterais

**Files:** `game/ui.py` (`_tab_inventory`, `_suit_card`, `_backpack_slot`, `_side_panels`, constantes), `game/app.py` (só se o clique precisar), `tests/test_backpack.py` (o teste de layout), `tests/test_m5_tab_v08.py`

**Antes:** abra com Read `reports/design/v08_m5_itens/tab_A.png`, `lado_a_lado_A.png`, `tab_A_sem_reorganizar.png` e a seção "Pro Dev integrar" do `reports/design/v08_m5_itens/index.html`.

- **Tab, 3 colunas** (mock A):
  - **esquerda:** as grades (MOCHILA T2 com 2 linhas, ou MOCHILA com 1, INVENTÁRIO e HOTBAR);
  - **meio:** o cartão TRAJE em coluna, com o explorador e os 4 slots (TANQUE, SCANNER, MOCHILA, BOTAS), cada um com rótulo, e o "180 s" do tanque;
  - **direita:** o detalhe do item com "USADO EM".
  - A janela fica **mais larga e mais baixa** que a de hoje e cabe em todas as escalas (`SIZES` do teste).
- **Rótulo da grade da mochila:** "MOCHILA T2" com a T2, e "MOCHILA" com a nv.1.
- **Painéis laterais** (baú e máquinas): a janela "Inventário" cresce 1 ou 2 linhas (`BACKPACK_ROW_H` × `backpack_rows`). O mock diz 148 de altura com a T2. Nada pode sair da tela nem passar por cima da hotbar.
- **Slot vazio:** o fantasma (ícone nv.1 com alpha 45) em cada slot. O das BOTAS usa o placeholder até o PNG chegar.
- **Clique:** o 4º slot funciona como os outros (`equip_rects`); o slot aceita nv.1 ou nv.2 (`EQUIP_SLOT_OF`).
- **Teste de layout** (`tests/test_backpack.py::test_tab_inventory_layout`): atualize pras 3 colunas e pros 4 slots (`equip_rects` == tanque, scanner, mochila, botas), com nv.1 e com T2, em todos os `SIZES`. Tire os `xfail` que a Task 1 tiver posto.
- Print headless do Tab (nv.1 e T2) e de um painel lateral com a T2, em `reports/dev/v08_m5_tab_*.png`. Abra com Read e compare com o mock.

---

### Task 6: Prints e report

**Files:** `tools/dev/shot_v08_m5.py` (molde: `shot_v08_m4.py`)

Prints em `reports/dev/`:
- `v08_m5_bancada.png`: a Bancada T2 na aba Bancada com os materiais;
- `v08_m5_tab.png`: o Tab com a Mochila T2, o tanque nv.2 e as botas equipados;
- `v08_m5_luminarias.png`: a caverna escura com uma luminária comum, uma forte e uma bio lado a lado;
- `v08_m5_adubo.png`: o painel do Cultivador com o selo do adubo;
- `v08_m5_drones.png`: uma estação com 1 drone nv.1 e 1 nv.2 voando.

Abra cada um com Read. Report `reports/dev/v08_m5.md`: mudanças por arquivo (juntando os reports das tasks), os prints, "Diferente do plano" e os riscos. **Não commite.**
