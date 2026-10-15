# v0.6 · Logística (design)

Aprovado pelo dono no brainstorm de 2026-10-15. O v0.6 ("Logística e fundo") foi dividido em dois blocos: **Logística** (esta spec) e **Fundo** (spec própria depois, ideias anotadas no fim). O elevador de carga saiu do v0.6 e foi pro Futuro.

## Objetivo

Deixar a base rodar sozinha: os drones passam a **abastecer** máquinas (não só tirar delas), o chip vira a peça que liga uma máquina na rede, os baús ganham tamanhos e a caverna ganha a rede de drones dela. Tudo testável no mundo que já existe.

## Decisões do dono

| Tema | Decisão |
|---|---|
| Chip | **Máquina** só entra na rede dos drones com um chip no slot dela. **Baú não precisa** de chip (entra sempre) |
| Máquinas na rede | Drill (Envia o minério dela), Derretedor (Recebe gelo, Envia cápsula), Dispersor de O₂ (Recebe cápsula). Fornalha entra no Fundo |
| Receita do chip | Bancada T2: 2 wafer + 1 ferro (partida). Wafer ainda é só loot; os crafts todos serão remapeados depois |
| Baús | Três tamanhos: **Simples** 1 linha (8), **Normal** 2 linhas (16), **Grande** 3 linhas (24) |
| Save antigo | Sem migração (dono): o baú existente carrega como **Normal** (16) e o que estava nos slots 17–24 some. Save continua v10 |
| Baú Grande | Precisa do **diagrama**, fabricável no T1, receita do diagrama **libera na Névoa** (Ti 10.000) e é mais cara |
| Baú de loot | O bauzinho dos destroços vira um Baú Simples de verdade: guarda item e pode ser desmontado |
| Painel de transferência | O clique pega a pilha no cursor e solta no slot escolhido, igual ao inventário (hoje o clique joga direto pro outro lado) |
| Caverna | A estação de drones funciona na caverna. **Cada camada tem a sua rede**; drone nunca troca de camada |
| Elevador de carga | Fica pro Futuro |

## Marcos

### Marco 1 · Baús e painel

**Três baús** (construtor, aba Armazenamento). Números de partida:

| Baú | id | Slots | Custo | Libera | Sprite |
|---|---|---|---|---|---|
| Simples | `chest_small` | 8 (1×8) | 3 ferro | desde o começo | `loot_crate` (fechado) / `loot_crate_empty` (aberto) |
| Normal | `chest` | 16 (2×8) | 6 ferro | desde o começo | `chest` / `chest_open` de hoje |
| Grande | `chest_large` | 24 (3×8) | 10 ferro + 2 silício | diagrama lido | `container_sealed` (fechado) / `container_open` (aberto) |

- **Diagrama do Baú Grande** (`diagram_chest_large`): fabricado no T1, receita liberada em **Ti 10.000** (Névoa), custo 10 ferro + 4 silício + 2 lingote de ferro. Lido na bancada, libera o Baú Grande no construtor pra sempre (mecanismo de diagrama que já existe, `DIAGRAM_BENCH`).
- Os três são baús pra tudo: nome, Envia/Recebe/Lote, "Pegar tudo"/"Guardar tudo", desmontar só vazio (regra de hoje). O painel ajusta a altura ao número de linhas.
- **Baú de loot dos destroços** (`loot_crate`): depois de aberto, funciona como um Baú Simples no lugar (8 slots, guarda item; **fica fora da rede dos drones**, decisão do dono no plano do M1). Segurar o botão direito desmonta e devolve **os materiais do Baú Simples** (3 ferro), com a mesma regra dos baús: só desmonta vazio. O **contêiner lacrado** (aberto) também guarda item (24 slots), mas **não desmonta** (não vira Baú Grande de graça). Futuro: desmontar com uma trava (decisão do dono).
- **Painel de transferência no estilo do inventário** (baú, baú de loot, contêiner, drill, derretedor, dispersor, estação):
  - **clique esquerdo** num slot pega a pilha inteira no cursor; clique num slot (do baú ou do inventário) solta ali, junta se for o mesmo item, troca se for outro;
  - **clique direito** pega metade (com pilha no cursor, solta 1);
  - **Shift+clique** continua mandando direto pro outro lado (o atalho rápido de hoje);
  - slots que não aceitam o item (ex.: a drill só envia, o slot de cápsula só aceita cápsula) recusam a soltura e a pilha fica no cursor;
  - fechar o painel com pilha no cursor devolve ela pro inventário (não cabendo, volta pra origem; nada some).
  - Reaproveita o `held` e os métodos por slot do `Inventory` (`take`, `take_half`, `put`, `swap`) que a tela de inventário já usa.
- **Save** continua v10 (sem migração, decisão do dono): o tipo do baú já vai no `kind`; o baú antigo carrega como Normal e perde os slots 17–24. Baús de loot passam a guardar o conteúdo depois de abertos (o estado já vai na lista `crates`).

### Marco 2 · Chip e máquinas na rede

- **Slot de chip** no painel da drill, do derretedor e do dispersor: aceita só o item `chip`, 1 por máquina.
  - Sem chip: no lugar da seção DRONES, o texto "Coloque um chip pra ligar aos drones".
  - Com chip: a seção DRONES (Envia/Recebe/Lote) aparece. Ao entrar o chip, o **Recebe** da máquina vem ligado por padrão (derretedor: gelo; dispersor: cápsula); o Envia continua no toggle.
  - Tirou o chip: a máquina sai da rede na hora. Drone indo buscar nela volta vazio; drone indo entregar nela procura outro destino (regras de hoje pra origem/destino que somem).
  - Desmontar a máquina devolve o chip junto com os materiais.
- **O que cada máquina aceita**:

| Máquina | Envia | Recebe |
|---|---|---|
| Drill | o minério dela | nada |
| Derretedor | `water_capsule` | `ice` (vai pro slot de entrada) |
| Dispersor de O₂ | nada | `water_capsule` |

  O "espaço livre" de uma máquina que recebe é o espaço do slot daquele item (o derretedor recebe gelo até encher a entrada; o dispersor, cápsula até encher o slot).
- **Chip na Bancada T2**: 2 `silicon_wafer` + 1 ferro (partida). O chip continua saindo de loot.
- **Save v11**: a máquina guarda `chip: bool`. Migração: drill e derretedor que já tinham algum Envia ligado ganham o chip de graça (a base de ninguém para). O dispersor do save antigo vem sem chip.

### Marco 3 · Drones na caverna

- A estação pode ser colocada na caverna; sai a dica "Drones só funcionam na superfície".
- **Rede por camada**: os drones de uma estação só enxergam baús e máquinas com chip **da mesma camada**. O `Ledger` e a busca de tarefa passam a ser por camada.
- Os drones das duas camadas **trabalham com o player em qualquer camada** (as máquinas da superfície já rodam com o player na caverna; os drones seguem a mesma regra).
- Energia continua global; o déficit deixa os drones lentos nas duas camadas.
- Desenho dos drones e o som `drone_loop` só na camada em que o player está.
- Save: as estações da caverna já vão na camada dela (conferir que as `Station` e os drones em voo de cada camada salvam e carregam).

## Arte e som (passam pelo dono antes de entrar)

- **Designer**: ícones `icon_chest_small`, `icon_chest_large` (e conferir o `icon_chest`), ícone do `diagram_chest_large` se o genérico não servir, silhueta do slot de chip vazio no painel, conferir se o `loot_crate`/`loot_crate_empty` e o `container_*` ficam bem como baú construído (fantasma do construtor, scanner).
- **Som**: nada obrigatório. Encaixar o chip pode usar um click que já existe; se o dono quiser um bip de "conectado", um CC0 seco.

## Testes

- pytest: tamanhos dos três baús; desmontar baú de loot (vazio sim, com item não); contêiner não desmonta; painel com pilha no cursor (pegar, soltar, juntar, trocar, recusar, fechar devolvendo); migração v10 → v11 (drill/derretedor com Envia ganham chip); chip liga/desliga a máquina na rede; derretedor recebendo gelo e dispersor recebendo cápsula pelos drones; rede separada por camada.
- Print avulso por marco (`tools/dev/shot_*.py`) pro dono olhar; smoke existente antes de cada merge.

## Execução

Um marco por sessão. 1 Dev (sonnet, worktree) por marco; a Designer em paralelo no M1.

## Bloco Fundo (próxima spec, ideias do dono)

- **Caverna espelhando a superfície**: a geração do subsolo segue as regiões de cima (basalto, gelo, salar...), e o bioma vem junto: caverna gelada debaixo do gelo, caverna de fogo e magma debaixo do basalto.
- **Menos minério solto na parede**; os veios de chão ficam, e entram **veios de parede**: 6 a 8 blocos de minério juntos.
- **Cobre** na caverna.
- **Fornalha** no esquema do derretedor: põe o item, espera derreter (magmatita → lingote, cobre → fios). Puxa linha de produção no futuro. Entra na rede com chip.
- **Broca nv.2**: não quebra a bedrock dos bolsões; quebra uma pedra nova (da cratera/entradas) que dá acesso aos biomas (basalto, gelo).
- Ganchos: basalto → vulcão, espécie nativa nas cavernas.
- Remapear todos os crafts (chip, baú grande, lingote) quando a fornalha e o cobre existirem.
