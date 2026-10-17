# v0.8 M6 · Task 6: a garrafa é recurso

Decisão do dono (bíblia §17, "A garrafa é recurso"):
- a cápsula vazia agora é **fabricada**;
- o derretedor **só enche vazia**;
- ninguém ganha vazia de graça.

## O que mudou, por arquivo

- **`game/config.py`**
  - `MELTER_EMPTY_SLOT = 2` e `MELTER_SLOTS = 3`. O 0 (gelo) e o 1 (cheias) não mudaram de índice.
  - Bloco novo "v0.8 M6 · A garrafa é recurso", no fim do bloco do adubo:
    - `MACHINES[EMPTY_CAPSULE].cost = {"silicon": 1}`, com a descrição "o derretedor e o Coletor enchem";
    - `CRAFT_YIELD[EMPTY_CAPSULE] = 2`;
    - categoria `materials`, logo depois do circuito no `MACHINE_ORDER`.
  - No fabricador T1, a aba Materiais mostra **Fios, Cápsula vazia**. Não é receita da T2.
  - O comentário do derretedor foi atualizado.
- **`game/systems.py`**
  - Propriedade nova `Machine.melter_blocker`, que dá `"out_full"`, `"no_empty"`, `"no_ice"` ou `None`.
  - `_update_melter` só anda com `melter_blocker is None`. A cada ciclo gasta o gelo **e 1 vazia** (`remove_from_slot(MELTER_EMPTY_SLOT, 1)`) e põe 1 cheia.
  - Travado, ele não gasta nada e o `timer` fica guardado.
  - A terraformação continua em `_update_machines`, sem depender disso.
  - `melter_put` agora encaminha: o gelo vai pro slot 0, a vazia pro slot 2, o resto é recusado.
- **`game/drones.py`**
  - `can_receive(melter)` aceita gelo e vazia, e `receive_slot` manda a vazia pro slot 2.
  - `can_send` continua só com as cheias.
  - `stock(melter, item)` dá 0 pra tudo que não é cheia, então os drones nunca tiram gelo nem vazia de lá.
  - Coletor e derretedor disputam as vazias pela regra que já existia. Não tem prioridade nova.
- **`game/app.py`**
  - `panel_refusal` do derretedor:
    - slot 0 só aceita gelo;
    - slot 2 só aceita vazia;
    - slot 1 só dá pra tirar.
  - Shift+clique manda o gelo e a vazia cada um pro seu slot.
  - `melter_status` mostra **SEM VAZIA**, SEM GELO, SAÍDA CHEIA ou "1 A CADA N S".
  - A dica do mouse ficou "Derretedor: N gelo · N vazia(s) · N cheia(s)".
- **`game/ui.py`**: o painel do derretedor ganhou 3 slots com rótulo, no molde do Coletor e da Fundição.
  - A ordem é GELO, VAZIAS, ">" e CHEIAS (`MELT_SLOT_X = (0, 36, 74)`).
  - A barra e o estado ficam à direita (`MELT_BAR_X`, 72 px de largura).
  - O estado fica vermelho em SEM VAZIA e SAÍDA CHEIA.
  - Linha de ajuda:
    - normal: "Gelo + 1 vazia = 1 cheia. Drones levam as cheias.";
    - sem vazia: "Fabrique cápsulas vazias (silício) e ponha aqui.".
  - A seção DRONES continua em `DISP_LOGI_Y` (92) e a altura do painel não mudou. O Recebe ganhou um 2º botão, mas a altura da fileira é a mesma.
- **`game/save.py`**: o `melter_storage` lê o slot 2, que só aceita vazia (outra coisa vira vazio). As docstrings foram atualizadas.
- **`game/objectives.py`**: `MELTER_HINT` = "O derretedor enche cápsulas vazias: fabrique algumas (silício) e ponha nele.", posto em "Minere gelo e construa um Derretedor".
- **`tools/dev/smoke.py`** (`check_melter`), ajustado à regra nova:
  - o Recebe tem gelo e vazia;
  - o aviso novo de recusa;
  - sem vazia não sai cápsula, e o smoke tira o print `derretedor_sem_vazia.png`;
  - depois o jogador solta 5 vazias no slot VAZIAS e o resto do fluxo continua igual.
- **`tools/dev/shot_v08_m6_derretedor.py`** (novo): os prints headless.
- **Testes antigos** ajustados à regra nova:
  - `test_melter.py`: `add_melter(..., empties=)`, e os 2 testes que enchiam sem vazia;
  - `test_chip.py`: o Recebe do derretedor;
  - `test_fabricator.py` e `test_constructor.py`: a vazia na aba Materiais.

## Save: continua v17

O load já monta o storage de slots fixos do zero: `Inventory(C.MELTER_SLOTS)` e depois lê cada slot por índice. Um derretedor de save v17 tem 2 slots e carrega com o slot 2 livre.
- Não tem `SAVE_VERSION` nova nem migração.
- **Ninguém ganha vazia de presente.** As vazias que já sobram no mundo do jogador passam a ser úteis.

## balance_sim

Ele **não depende** das cápsulas do derretedor. A tabela das plantas põe as cápsulas direto no Dispersor e no Cultivador, e o derretedor só aparece como custo do nv.2. Por isso não mexi nele e não rodei o `test_balance_sim.py`.

## Testes

- `tests/test_m6_bottles_v08.py`: 35 testes, cobrindo:
  - ciclo, parada sem vazia (guarda o progresso, a água sobe) e a ordem do bloqueio;
  - receita 1 silício → 2, na aba Materiais;
  - conservação: derretedor + Dispersor 7×7 + estação com 1 drone, por 400 s. O total de garrafas fica constante em cada checagem, e o derretedor encheu ≥ 4 com só 3 vazias no começo, ou seja, a vazia voltou;
  - slots, clique e shift+clique;
  - drone leva vazia pro derretedor e nunca tira de lá;
  - save round-trip e derretedor v17 de 2 slots;
  - desmontar devolve as vazias;
  - a dica, e se ela cabe no cartão (≤ linhas da dica do scan);
  - altura do painel: nv.1/nv.2 × 3 tamanhos × mochila nv.1/T2. Nem os botões, nem a janela, nem a linha de ajuda passam da moldura da hotbar;
  - DRONES em `DISP_LOGI_Y` e os rótulos/estado cabem.
  - Resultado: `35 passed in 1.89s`.
- Os listados (`grep -l "melter\|dispenser\|collector\|drone\|craft" tests/`, 53 arquivos fora o `test_balance_sim`) deram `1411 passed in 313.63s (0:05:13)`.

## Prints (Grande 480×270, mochila T2, DRONES toda ligada; abertos com Read)

- `reports/dev/v08_m6_derretedor_vazias.png`: 18 gelo, 3 vazias e 2 cheias, a barra em 60%, "1 A CADA 20 S".
- `reports/dev/v08_m6_derretedor_sem_vazia.png`: o slot VAZIAS vazio, **SEM VAZIA** em vermelho, e embaixo "Fabrique cápsulas vazias (silício) e ponha aqui.".

## Textos novos

- Rótulos dos slots: GELO / VAZIAS / CHEIAS (era GELO / CÁPSULA).
- Estado: SEM VAZIA.
- Ajuda do painel:
  - "Gelo + 1 vazia = 1 cheia. Drones levam as cheias.";
  - "Fabrique cápsulas vazias (silício) e ponha aqui.".
- Avisos:
  - "O derretedor só aceita gelo e cápsula vazia";
  - "A vazia vai no slot VAZIAS";
  - "O gelo vai no slot GELO";
  - "A saída do derretedor só dá pra tirar";
  - "Slot de vazias cheio".
- Dica do objetivo: "O derretedor enche cápsulas vazias: fabrique algumas (silício) e ponha nele."
- Descrição da vazia: "o derretedor e o Coletor enchem".
- Dica do mouse: "Derretedor: N gelo · N vazia(s) · N cheia(s)".

## Diferente do plano

- O rótulo da saída virou **CHEIAS** (era CÁPSULA), pra casar com o Coletor.
- A linha de ajuda normal também mudou, pra explicar a regra.
- `stock()` do derretedor ganhou uma trava extra: só as cheias contam. É redundante com o `can_send`, mas garante que os drones nunca tiram de lá.
- O smoke foi ajustado, mas **não rodei** o smoke completo, porque ele só roda no merge de marco. Ele mexe no `check_melter` e gera um print novo, `derretedor_sem_vazia.png`.

## Riscos

- O estado "1 A CADA 10 S · RITMO X%" no déficit de energia é cortado com ".." na barra de 72 px. Já era cortado antes, com 104 px.
- Os rótulos VAZIAS e CHEIAS ficam a 3 px um do outro no Grande. Dá pra ler (ver o print), mas é apertado.
- No save de quem já joga, o derretedor para até o jogador fabricar ou trazer vazias. A dica só aparece pra quem ainda está no objetivo do derretedor, então quem já passou dele só vê o SEM VAZIA no painel.
- A bíblia já tem a decisão. Falta só o "como ficou" do M6, que fica com o gerente no fechamento.
