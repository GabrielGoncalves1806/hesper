# v0.8 M6 · Objetivos e fechamento: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** fechar a v0.8 · Plantas.
- **11 objetivos novos** depois de "Construa uma máquina nv.2", e a **dica do coletor**.
- A seção **DRONES** do Cultivador, do Microscópio e da Centrífuga **cabe no Grande**.
- O **`balance_sim`** passa a conhecer as plantas: biomassa, trava por estágio, materiais e a janela de calor do gelo do lab.
- **Ritmo das plantas:** mais lentas por raridade e a alga rebalanceada. O número final é do dono, decidido com o report do sim.

**Architecture:**
- **Objetivos:** cada objetivo continua "texto + função que olha o `GameState`" (`game/objectives.py`). As condições novas que não têm estado hoje (achar o lab, pegar a cultura, primeira colheita etc.) viram **marcos que só crescem**, guardados num set `GameState.milestones`. Esse set entra no save como campo opcional, então **o save continua v17**.
- **Quem já passou não trava:** cada objetivo novo tem um *fallback* derivado do que o save antigo já tem (blueprints, `crafted`, estágio), no molde do `found_magmatite`.
- **DRONES no Grande:** as três máquinas usam a fileira compacta do baú (botões 16×16 com o rótulo no vão), em todos os tamanhos.
- **Plantas no sim:** a tabela das plantas roda a regra real do Cultivador (`GameState`, base vedada de verdade). A simulação principal ganha uma biomassa "virtual" (N cultivadores a partir do lab aberto), pras marcas de Algas, Musgo e Verde pararem de ser só "(Ti)".

**Tech Stack:** Python 3 + pygame-ce, pytest, `uv run`.

## Global Constraints

- **Leia antes:**
  - spec `docs/superpowers/specs/2026-10-16-v08-plantas-design.md`, seções "Objetivos" e "Testes";
  - bíblia §17, inteira, incluindo o "como ficou" do M1 ao M5;
  - item M6 do `docs/ROADMAP.md`.
- **Nomes que já existem (não redefina):**
  - `C.ALGAE_STAGE = 4`, `C.MOSS_STAGE = 5`, `C.GREEN_STAGE = 6`;
  - `C.CULTIVATOR`, `C.MICROSCOPE`, `C.CENTRIFUGE`, `C.SCAN_BLUEPRINT`: prop do tanque dá `cultivator`, `prop_microscope_digital` dá `microscope`;
  - `C.CROPS` (`Crop(biomass, water_s, cycle)`), `C.CROP_ITEMS`, `C.SAMPLE_ITEMS`;
  - `C.FIBER`, `C.HYDROGEL`, `C.FROST_RESIN`, `C.LILY_ESSENCE`, `C.FERTILIZER`;
  - `C.LAB_ICE_HEAT`, `thaw.lab_ice_progress`, `Layer.lab_ice_open`, `Layer.lab_ice_opens_at`;
  - `GameState.in_breathing_base(tile, layer)`, `GameState.crafted`, `GameState.blueprints`.
- **Save continua v17.** Só entra o campo opcional `"milestones"` (lista ordenada; sem o campo, carrega vazio). Ninguém mexe no `SAVE_VERSION`.
- **Sem arte nova e sem som novo.** A dica do coletor é texto.
- **Os números das plantas não mudam nas Tasks 1–3.** Quem muda o `CROPS` é a Task 4 (gerente), depois do ok do dono.
- **O Dev:**
  - não commita;
  - não abre o jogo em janela;
  - não roda `build_sprites.py`;
  - não mexe em `assets/`;
  - não roda o pytest inteiro, só os testes da task e os listados.
- **Teste de UI confere altura, não só largura:** nada passa da moldura da hotbar nem da linha de ajuda (lição do M4).

## Ondas

| Onda | Tasks | Por quê |
|---|---|---|
| 1 (paralelo) | 1 Objetivos · 2 DRONES no Grande · 3 Plantas no `balance_sim` | arquivos diferentes (`objectives`/`systems`/`save` · `ui` · `tools/dev`) |
| 2 (dono + gerente) | 4 Ritmo das plantas | o dono decide os números com o report da Task 3 |
| 3 | 6 A garrafa é recurso | entrou no meio do M6 (dono) |
| 4 | 5 Prints, report e merge de marco | depende de tudo |

Cada task tem o seu arquivo de teste: `tests/test_m6_objectives_v08.py`, `test_m6_drones_fit_v08.py` e `test_m6_balance_v08.py`.

---

### Task 1: Objetivos novos e a dica do coletor

**Files:**
- `game/objectives.py`;
- `game/systems.py`: `GameState.milestones` e os 6 ganchos abaixo;
- `game/save.py`: só o campo `milestones`;
- `game/config.py`: só `MILESTONES`;
- `tests/test_m6_objectives_v08.py`;
- e `tests/test_objectives.py`, se algum teste de ordem antigo precisar de ajuste.

**Interfaces:**
- Produces:
  - `C.MILESTONES = ("lab_found", "control_culture", "cultivator_in_base", "first_harvest", "first_sample", "first_plant")`;
  - `GameState.milestones: set[str]`, que só cresce;
  - `GameState.mark(name: str) -> None`, que faz `assert name in C.MILESTONES` e adiciona;
  - `objectives.COLLECTOR_HINT = "Pouco gelo? O coletor de água puxa a umidade do ar."`

**Ganchos em `game/systems.py`** (cada um chama `self.mark(...)`; todos são idempotentes):

| Marco | Onde | Quando |
|---|---|---|
| `lab_found` | `_update_explore`, junto do laço dos destroços (só na superfície) | o player a até `C.WRECK_VISIT_DIST` tiles da porta do lab (`ruins.lab_door_px(self.world)`, em px; divida por `C.TILE`). Mundo sem lab: nunca marca |
| `control_culture` | `crate_take` | saiu ≥ 1 `algae` (`got > 0`) de uma caixa (só a do lab tem alga). Na caixa de ruína, `crate.wreck` é um `RuinSpot`, então exija também `getattr(crate.wreck, "key", None) == "lab"` |
| `cultivator_in_base` | update do Cultivador (perto do `cultivator_blocker`) | algum Cultivador com `in_breathing_base((m.tx, m.ty), layer)` verdadeiro, com ou sem muda |
| `first_harvest` | `_cultivator_harvest` | colheu ≥ 1 (`n - left > 0`), de qualquer cultura |
| `first_sample` | update do Microscópio, onde sai `("sample_found", ...)` | saiu amostra |
| `first_plant` | update da Centrífuga, onde sai `("centrifuge_done", m, plant)` com `plant` | saiu planta (falha não conta) |

**Objetivos:** entram depois de "Construa uma máquina nv.2". O "Deixe o planeta verde" continua sendo o último. Cada condição é `marco or fallback`, e o fallback cobre quem já passou com save antigo:

| # | Texto | Feito quando |
|---|---|---|
| 1 | Ache o laboratório da Ilves | `lab_found` **ou** `"cultivator" in blueprints` |
| 2 | Derreta o gelo do laboratório | `state.surface.lab_ice_open` **ou** `"cultivator" in blueprints` |
| 3 | Escaneie o microscópio e o tanque do laboratório | `{"cultivator", "microscope"} <= blueprints` |
| 4 | Pegue a cultura-controle | `control_culture` **ou** `crafted(cultivator) ≥ 1` |
| 5 | Construa um cultivador dentro da base | `cultivator_in_base` **ou** `first_harvest` **ou** `stage ≥ ALGAE_STAGE` |
| 6 | Colha a primeira alga | `first_harvest` **ou** `crafted(fiber) ≥ 1` **ou** `crafted(fertilizer) ≥ 1` **ou** `stage ≥ ALGAE_STAGE` — **hint = `COLLECTOR_HINT`** |
| 7 | Chegue ao estágio Algas | `stage ≥ ALGAE_STAGE` |
| 8 | Consiga uma amostra no microscópio | `first_sample` **ou** o fallback do 9 |
| 9 | Consiga uma planta nova na centrífuga | `first_plant` **ou** `crafted` de gel, resina, essência ou adubo ≥ 1 |
| 10 | Chegue ao estágio Musgo | `stage ≥ MOSS_STAGE` |
| 11 | Deixe o planeta verde | (o que já existe) |

- Confira o nome real do campo `crafted` pros materiais: ele é indexado por `C.MACHINES`, que inclui os itens da Bancada. Se algum material não estiver lá, use outro sinal do save que só cresce e conte no report.
- Os textos têm que caber na caixa de objetivos nos 3 tamanhos. Se algum passar, encurte, mostre o texto novo no report e mantenha o sentido.
- O `hint` é o mecanismo que já existe (`take_hint`, uma vez por objetivo por sessão).

**Save:**
- grava `"milestones": sorted(state.milestones)`;
- no load, filtra por `C.MILESTONES`;
- sem o campo, carrega vazio;
- **não** sobe a versão.

**Testes** (no mínimo):
- [ ] a ordem nova: os 11 textos vêm logo depois de "Construa uma máquina nv.2", e o último é o "Deixe o planeta verde";
- [ ] cada gancho marca o marco certo, usando a regra real:
  - o player perto da porta do lab;
  - `crate_take` da caixa do lab;
  - Cultivador dentro da base com Dispersor (use o helper de base vedada que os testes do M3 já usam);
  - colheita, amostra e planta, com rng fixo;
  - falha da centrífuga **não** marca;
- [ ] **quem já passou não trava:** estado no Verde com `crafted` de fibra, gel e cultivador e os dois blueprints → `current_index` é `None`;
- [ ] estado no Algas sem o diagrama do microscópio → o atual é o 3 (escanear);
- [ ] a dica do coletor sai uma vez quando o 6 vira o atual;
- [ ] round-trip do save com 3 marcos; save sem `milestones` carrega vazio; marco desconhecido no save é ignorado;
- [ ] monotonia: tirar o Dispersor depois de marcar `cultivator_in_base` não "descumpre".

Rode também `tests/test_objectives.py`, `tests/test_save.py` e os testes do Cultivador, do Microscópio e da Centrífuga (`grep -l "cultivator\|microscope\|centrifuge" tests/`).

---

### Task 2: Seção DRONES do Cultivador, do Microscópio e da Centrífuga cabe no Grande

**Files:**
- `game/ui.py`: `draw_logistics`, `logistics_height` e, se precisar, as constantes `CULT_LOGI_Y`, `MIC_LOGI_Y` e `CENT_LOGI_Y`;
- `tests/test_m6_drones_fit_v08.py`;
- `tests/test_m5_chest_fit_v08.py`: o `test_machine_rows_stay_normal` muda; veja abaixo.

**Antes:**
- Meça. Faça um teste que desenha os três painéis no `SIZES = [(480, 270), (640, 360), (960, 540)]`, com a mochila nv.1 e com a T2 (molde: `tests/test_m5_chest_fit_v08.py`, fixture `suited`). Use `m.chip = "chip"` se a máquina pedir chip, e `sends`/`receives` com tudo o que ela aceita.
- Anote no report quanto cada um passa da moldura (`ui.hotbar_y - 11 - 1 - HELP_H`).

**Regra:**
1. Uma máquina "compacta" (`COMPACT_LOGI = {C.CULTIVATOR, C.MICROSCOPE, C.CENTRIFUGE}`) desenha Envia e Recebe na **fileira larga do baú**:
   - botões `LOGI_WIDE_BTN` (16×16), `LOGI_WIDE_COLS` por linha;
   - rótulo no vão da última linha quando `wide_label_inline(n)` (com ≤ 5 itens o vão sempre existe).
   - Isso vale **em todos os tamanhos**, pra a máquina não mudar de cara entre o Grande e o Pequeno.
2. O slot do chip (se tiver) continua à direita. A fileira compacta tem que caber em `GRID_W - (SLOT + 4)` quando a máquina pede chip.
3. `logistics_height` usa a mesma conta da fileira larga pra essas máquinas, senão o painel calcula a altura errada.
4. O Lote fica igual: os botões já têm 16 de altura.
5. Se, mesmo compacta, alguma passar da moldura no Grande:
   - suba o `*_LOGI_Y` dela o necessário, encostando no que vem antes sem sobrepor (teste de retângulos);
   - conte no report quantos px ganhou e de onde.
   - **Não** corte informação do painel.
6. As outras máquinas (Fundição, derretedor, dispersor, drill) **não mudam**. O `test_machine_rows_stay_normal` continua com a Fundição; acrescente um caso que garante 16×16 no Cultivador.

**Testes:**
- [ ] nos 3 tamanhos × nv.1/T2 × as 3 máquinas, a base dos botões (`logistics_buttons`) e a janela (`inv_window.bottom`) ficam `<= frame`;
- [ ] a contagem de botões é a de antes (nenhum toggle some);
- [ ] o clique ainda acerta: `logistics_at` (ou o hit-test que existir) no centro de cada botão devolve o item certo;
- [ ] a Fundição continua com botões de `LOGI_BTN`.

**Print headless:** os três painéis no Grande com a T2, em `reports/dev/v08_m6_drones_*.png`. Abra com Read e confira se o rótulo não encosta no chip.

---

### Task 3: Plantas no `balance_sim`

**Files:**
- `tools/dev/balance_sim.py`;
- `tools/dev/balance_proposal.json`: a proposta dos ciclos;
- `tests/test_m6_balance_v08.py`;
- `reports/dev/v08_m6_balance.md`, gerado pelo `--markdown` e comentado.

**Antes:**
- Leia o docstring do `balance_sim` (o que é real e o que é aproximado) e o `tests/test_balance_sim.py`.
- Ele roda devagar: nos testes, use 1 seed e o mínimo de estratégia.

**3a · Tabela das plantas (regra real):** função `crop_table(overrides=None) -> list[dict]` e flag `--crops`.
- Monte um `GameState` com uma base vedada pequena (5×5) e Dispersor soprando, do jeito que os testes do M3 montam. Ponha um Cultivador por cultura, com reserva de água sempre cheia.
- Rode o update real por 1 h de jogo (dt = 1 s) e meça, por cultura:
  - **colheitas/h** e **itens/h** (1–2 por colheita; use rng fixo e N grande);
  - **biomassa/s** média;
  - **cápsulas/h**;
  - o mesmo com **adubo** contínuo, com quantos adubos/h isso gasta.
- **Consumo** (das receitas reais do config, não digitado):
  - quantas algas/h uma Centrífuga rodando sem parar come;
  - quantos cultivadores de alga sustentam 1 Centrífuga;
  - o custo em plantas de cada item do M5 (Mochila T2, Tanque nv.2, Botas, Drone nv.2, Luminária bio, Adubo), abrindo fibra/gel/resina até a planta;
  - o tempo pra juntar o kit todo com 3 cultivadores de alga e 1 de cada planta.
- **Plantas por amostra:** o tempo esperado pra sair 1 Folha-gota, 1 Espiral e 1 Lírio de uma Centrífuga alimentada por 1 Microscópio. Use as odds reais (`MICROSCOPE_ODDS`, `CENTRIFUGE_RECIPES`) em conta fechada e confira com 1 rodada de rng.
- **Overrides:** o `balance_proposal.json` passa a aceitar `"CROPS": {"algae": {"cycle": 150}, ...}`. Como o `Crop` é NamedTuple, use `_replace`, e restaure depois, como os outros overrides fazem. A proposta de partida (ROADMAP): alga 150, Folha-gota 240, Espiral 360, Lírio 540.

**3b · Simulação principal:**
1. **Lab abre:** marca nova "Lab abre", no primeiro instante em que o calor passa do ponto de abertura da fresta. Use a regra real (`thaw.lab_ice_progress(heat) >= surface.lab_ice_opens_at` ou o `lab_ice_open` da camada, se o update do sim já roda o degelo).
2. **Biomassa virtual:**
   - Do "Lab abre" e do estágio Úmido em diante (o que vier por último), mais `craft_overhead`, o jogador tem `Strategy.cultivators` (padrão 3) cultivando alga.
   - A biomassa sobe `N × biomassa/s` da tabela 3a, com a disponibilidade de água medida lá (o sim não simula as cápsulas).
   - No estágio Algas, a cada `t_planta` esperado (da 3a), um cultivador troca pra próxima planta (Folha → Espiral → Lírio).
   - Documente no docstring como aproximação.
3. **Marcas:** Algas, Musgo e Verde passam a usar o `stage_for_ti(ti, biomass)` real. O `mark_label` tira o " (Ti)" e a tabela mostra qual dos dois foi o gargalo em cada estágio (coluna "gargalo": Ti/bio).
4. **Trava por estágio:** o sim já usa o `recipe_status` real. Confirme que a Centrífuga só entra depois do Algas e que nenhuma estratégia tenta fabricar coisa travada em laço. Teste isso.

**Testes:**
- [ ] `crop_table()` dá, pra alga, colheitas/h ≈ 3600 / (ciclo × (1 − `CULTIVATOR_HARVEST_AFTER`)) (±10%), e biomassa/s = `CROPS["algae"].biomass` enquanto tem água;
- [ ] o override de `CROPS` muda o ciclo e é restaurado depois;
- [ ] "Lab abre" aparece antes de Algas numa seed;
- [ ] com `cultivators=0`, Algas nunca chega (trava dupla); com 3, chega;
- [ ] a Centrífuga não é fabricada antes do Algas.

**Report** `reports/dev/v08_m6_balance.md`, atual × proposta:
- a tabela 3a;
- as marcas (com "Lab abre" e o gargalo);
- 3 a 5 linhas do que os números dizem: se a alga rende demais pro consumo, quantos cultivadores o jogador precisa, e se o Lírio a 540 s fica chato.
- Lembrete pro report: **sem F1**. O dono testa com ×10.
- **Não** proponha número final: isso é a Task 4, com o dono.

---

### Task 4: Ritmo das plantas (gerente, com o dono)

**Files:** `game/config.py` (`CROPS`, e os números da alga que o dono escolher: ciclo, colheita ou receitas da fibra/adubo), `docs/GAME_BIBLE.md` §17, `docs/ROADMAP.md`, e os testes que fixam o ciclo antigo (`grep -rn "90\.0\|CROPS\[" tests/`).

1. O gerente mostra ao dono o `reports/dev/v08_m6_balance.md`.
2. O dono escolhe os ciclos e o ajuste da alga. A bíblia é atualizada primeiro.
3. Muda o `config.py` e roda o `balance_sim --crops` de novo pra confirmar.
4. `uv run pytest` passando, lido no `tail -1` do log.

Ajuste de número fica só no pytest, sem smoke (regra do dono, 2026-10-16).

---

### Task 6: A garrafa é recurso (entrou no meio do M6, dono 2026-10-17)

**Por quê:** o derretedor cria cápsula do zero, e o Dispersor e o Cultivador transformam cada cheia gasta em 1 vazia, então as vazias só se acumulam. Decisão do dono (bíblia §17, "A garrafa é recurso"):
- a **cápsula vazia é fabricada**;
- o derretedor **só enche vazia**;
- sem kit e sem vazia de graça.

**Files:**
- `game/config.py`: receita e `CRAFT_YIELD` da vazia, `MELTER_EMPTY_SLOT`, `MELTER_SLOTS`, descrições;
- `game/systems.py`: `_update_melter`, storage do derretedor, bloqueio;
- `game/drones.py`: o derretedor recebe vazia;
- `game/app.py`: o slot aceita vazia; o rótulo de estado;
- `game/ui.py`: painel do derretedor;
- `game/save.py`;
- `game/objectives.py`: só a dica;
- `tools/dev/balance_sim.py`: só se ele usar as cápsulas do derretedor;
- `tests/test_m6_bottles_v08.py`.

**Interfaces:**
- Produces:
  - `C.MELTER_EMPTY_SLOT = 2` e `C.MELTER_SLOTS = 3`. O 0 (gelo) e o 1 (cheias) **não mudam de índice**;
  - `MACHINES[EMPTY_CAPSULE].recipe = {"silicon": 1}` e `CRAFT_YIELD[EMPTY_CAPSULE] = 2`, no fabricador, aba **Materiais** (onde estão os fios);
  - a descrição da vazia vira "o derretedor e o Coletor enchem".

**Regras:**
1. **Derretedor:** a cada `MELTER_CAPSULE_TIME` gasta `MELTER_ICE_PER_CAPSULE` de gelo **e 1 vazia** e põe 1 cheia.
   - Sem vazia, para e não gasta gelo. O progresso fica guardado, como no "sem gelo" de hoje.
   - A terraformação (o "+ água" do índice) **não muda**: continua independente das cápsulas.
2. **Slot VAZIAS (2):** só aceita `C.EMPTY_CAPSULE`, pelo clique, pelo shift+clique e pelos drones. O slot 0 continua só gelo.
3. **Estado do painel:** status curto **SEM VAZIA**, no molde do COLETANDO / PARADO / SEM VAZIA do Coletor, com o motivo na linha de baixo ("Fabrique cápsulas vazias"). O slot VAZIAS fica ao lado do gelo, com rótulo.
4. **Drones:**
   - o derretedor **recebe** gelo e vazia (vazia no slot 2);
   - o derretedor continua mandando só cheias;
   - os drones nunca tiram a vazia de lá.
   - Coletor e derretedor disputam as vazias pela regra que já existe. **Não** invente prioridade.
5. **Dica:** o objetivo "Minere gelo e construa um Derretedor" ganha o `hint` "O derretedor enche cápsulas vazias: fabrique algumas (silício) e ponha nele." (mecanismo `Objective.hint`). Confira se cabe no cartão.
6. **Save:**
   - o derretedor de save v17 tem 2 slots. Se o load já completa o storage de slots fixos (`save.py` ~324 e ~412), não precisa de versão nova; se não, `SAVE_VERSION = 18`, com `_v17_to_v18`. Conte no report qual dos dois;
   - **sem** vazia de presente na migração: o dono quer que o jogador fabrique. As vazias que já sobram no mundo dele viram úteis.
7. **Desmontar** o derretedor devolve as vazias junto do resto.
8. **`balance_sim`:** confira se ele depende das cápsulas do derretedor. Se depender, o jogador simulado fabrica as vazias quando precisa, e conte no report.

**Testes** (no mínimo):
- [ ] 1 ciclo gasta 1 vazia + o gelo e põe 1 cheia;
- [ ] sem vazia, para, não gasta gelo e guarda o progresso; o índice de água continua subindo;
- [ ] a receita dá 2 vazias por 1 silício e aparece na aba Materiais;
- [ ] **conservação:** derretedor + Dispersor + 1 estação com drone, N ciclos: cheias + vazias em todo lugar = constante;
- [ ] o slot 2 recusa outro item e o slot 0 recusa vazia;
- [ ] o drone leva vazia pro derretedor e nunca tira de lá;
- [ ] round-trip do save com vazias no derretedor; um derretedor de save v17 (2 slots) carrega;
- [ ] desmontar devolve as vazias;
- [ ] a altura do painel nos 3 tamanhos × nv.1/T2 (molde: `tests/test_m6_drones_fit_v08.py`).
  - Nada passa da moldura da hotbar nem da linha de ajuda.
  - O derretedor usa o `DISP_LOGI_Y` dele.

Rode também os testes do derretedor, do Dispersor, do Coletor, dos drones, dos objetivos, do save e do fabricador (`grep -l "melter\|dispenser\|collector\|drone\|craft" tests/`), mais o `tests/test_balance_sim.py` se mexer no sim.

**Saídas:**
- print headless do painel do derretedor no Grande, com vazias e com "SEM VAZIA", em `reports/dev/v08_m6_derretedor*.png`, aberto com Read;
- report `reports/dev/v08_m6_task6.md`.

---

### Task 5: Prints, report e merge de marco

**Files:** `tools/dev/shot_v08_m6.py` (molde: `shot_v08_m5.py`)

**Prints em `reports/dev/`:**
- `v08_m6_objetivos.png`: a caixa de objetivos com "Ache o laboratório da Ilves" atual e o próximo embaixo;
- `v08_m6_dica.png`: o aviso da dica do coletor no topo;
- `v08_m6_drones_grande.png`: o painel do Cultivador no Grande com a T2.

Abra cada um com Read.

**Report** `reports/dev/v08_m6.md`:
- mudanças por arquivo, juntando os reports das tasks;
- os prints;
- "Diferente do plano";
- riscos.

**Não commite.**

**Merge de marco (gerente):**
1. pytest + smoke + `real_video_check`, olhando os prints;
2. commit dos prints separado (`git add reports/dev ':!reports/dev/receitas.html'`);
3. "como ficou" do M6 na bíblia;
4. lista de teste pro dono em cima do save dele (`saves/world1.json`, só leitura);
5. o `[x]` só depois do teste dele.

---

## Fora do M6 (o dono pode querer rever no fechamento)
- o drone nv.2 "carregar mais" (cortado no M5);
- as cores das amostras em `ORE_COLORS` (escolhidas pelo Dev);
- as botas 2D provisórias;
- o modal de logística (Futuro). O remendo da Task 2 segura até lá.
