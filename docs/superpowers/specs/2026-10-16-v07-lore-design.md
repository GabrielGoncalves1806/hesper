# v0.7 · Lore: design

Aprovado pelo dono no brainstorm de 2026-10-16. Números são de partida; o balanceamento é uma passada só, depois (regra do dono).

## Objetivo

Fazer a lore virar **lugar**: estruturas da Colônia Hesper geradas pela seed (superfície e caverna), montadas com os blocos e máquinas que o jogo já tem, decoradas com um kit de props que o player também pode usar na base, destroços com cara nova e um interior de verdade na nave de carga. Ninguém encosta no player: a v0.7 é só pista.

## Fora da v0.7 (decisão do dono)

- **Inimigos, combate e boss**: versão futura ("ainda tem muita coisa até eles chegarem pra mexer com o player").
- **O planeta reagindo** ao Ti e ao derretimento (gelo voltando, leitura térmica estranha, terminal ligando sozinho): **v0.8**.

## A verdade da história (canon; o player descobre aos poucos)

| Tema | Decisão |
|---|---|
| O que tem no gelo | Uma **espécie nativa** do planeta. A criatura do **Grande gelo** (bolsão da faixa gelada, Larva ou Casulo, v0.5 M3.6) é ela: uma "minhoca" |
| O erro da colônia | **Acordar o gelo rápido demais.** O gelo guarda a vida do planeta; a diretoria apressou o cronograma, a coisa reagiu, a colônia desligou os derretedores e sumiu |
| O player | Está repetindo o que a colônia fez (derrete a cratera, acorda as fumarolas). A dúvida "tô salvando o planeta ou repetindo o erro?" é o motor |
| Futuro (não é v0.7) | Larvas pelo mapa; **genes do gelo** pra gerar vida (mobs pacíficos e agressivos, espécies que vieram do gelo derretido); a criatura vira inimigo e boss |

## Decisões do dono

| Tema | Decisão |
|---|---|
| Estruturas | "Dungeons" com lore, **montadas com os blocos e máquinas que já existem**, geradas pela seed |
| Como monta | **Planta desenhada à mão + variação pela seed** (gira, espelha, destruição, loot, LOG). Salas soltas encaixadas só no interior da nave |
| Catálogo | 4 estruturas, **uma de cada por mundo** (tabela abaixo) |
| O que dá pra fazer | **Casca intocável** (parede e chão não quebram nem desmontam; entra pela porta). Caixas e terminais funcionam. **Máquinas quebradas** desmontam **uma vez** e devolvem umas peças |
| Interior | **Só a nave de carga** (VÉSPER-7, o transportador): a porta é o porão aberto |
| Destroços | Arte nova a partir da referência do dono: **5 tipos** (3 trocam de cara, 2 novos) |
| Props | **Kit médio** (14–16), servindo ruína, interior e **base do player** |
| Liberar prop | **Scanner do construtor**: segura o **esquerdo** num prop de ruína desconhecido → libera a receita. Só decoração escaneia. 3–4 props liberados de cara |
| Construtor | Sprite novo com cara de módulo de scanner |

## Catálogo das estruturas

| # | Estrutura | Onde | Regra de lugar | O que conta |
|---|---|---|---|---|
| 1 | **Acampamento de pouso** | superfície | **40–60 tiles da cratera**, fora da vista inicial | os primeiros dias, tudo otimista |
| 2 | **Laboratório da Ilves** | superfície, faixa gelada | **distância mínima do bolsão da criatura** (número no config) | as amostras, o "espécime" (sem dizer onde) |
| 3 | **Estação de derretedores** | caverna, bioma do gelo | dentro da rocha dura (precisa da broca nv.2) | o derretedor 4, o gelo que não é só água |
| 4 | **Posto de perfuração** | caverna, basalto | dentro da rocha dura | o calor que sobe sozinho, a descida pro "nível 2", o primeiro rastro da criatura |

O salar da caverna fica de fora de propósito (guardado pra depois). Os destroços de hoje continuam existindo do lado das estruturas.

## Marcos

| Marco | Quem | O quê |
|---|---|---|
| **M1 · Estruturas** | Dev | plantas, gerador pela seed, as 4 estruturas com o que já existe, casca `ruin`, máquinas `broken`, LOGs novos, save, marcador no mapa |
| **Arte** | Designer, em paralelo ao M1 | 5 destroços, kit de props, construtor novo (tudo passa pelo dono) |
| **M2 · Props e scanner** | Dev | props no mundo, aba Decoração, scan no esquerdo, props nas plantas |
| **M3 · Destroços novos** | Dev | 3 sprites trocados, nave de passageiros e robô de reconhecimento |
| **M4 · Interior da VÉSPER-7** | Dev | camada nova pequena, porão como porta, salas encaixadas pela seed, câmara fria |

O M1 usa **só o que já existe**; os props entram nas plantas no M2.

## M1 · Estruturas

**Planta**: um arquivo de texto por estrutura em `game/ruin_plans/` (`camp.txt`, `lab.txt`, `melters.txt`, `drill_post.txt`; é dado de jogo, não arte, então fica fora de `assets/`). Uma legenda no topo diz o que cada letra é; o resto é a grade, um caractere por tile:

```
#  parede da base        .  chão da base       D  porta      =  porta dupla
m  máquina quebrada (qual: legenda, ex. "m = melter")
c  caixa de saque        T  terminal (qual LOG: legenda, ex. "T = 8")
L  luminária             ~  chão que pode ficar destruído
(espaço) fora da estrutura (o terreno fica como está)
```

**Variação pela seed** (rng próprio por estrutura, a mesma seed dá a mesma ruína):
- **orientação**: 8 (4 giros × espelho);
- **destruição** nível 0–3 por estrutura: nos `~` e em paredes vizinhas, sorteia **parede caída** (vira rocha/entulho), **gelo invadindo** (lab e derretedores), **areia cobrindo** (acampamento) ou nada. A destruição **nunca fecha a porta** nem isola o terminal ou a caixa (testado);
- **loot** da caixa: tabela por estrutura, mesmo formato das dos destroços;
- **posição**, dentro da regra do catálogo.

**Lugar**:
- superfície: em areia livre, com as mesmas exclusões dos destroços (veio, bacia, cratera, formações, bolsões, longe da base) e longe dos destroços;
- caverna: carimbada **dentro da rocha dura** do bioma. O gerador abre o espaço da planta e deixa a rocha em volta. Sem túnel pronto: o player cava com a nv.2.

**Blocos e máquinas**:
- casca = `BaseBlock` com a marca **`ruin`**: a broca não quebra, desmontar ignora, não conta na vedação da base do player, colide igual;
- máquina quebrada = máquina com a marca **`broken`**: não liga, não soma índice, Ti nem energia, não entra na rede; sprite apagado e torto. Desmontar com o **direito** (construtor na mão, 1 s, como hoje) devolve uma tabelinha de peças e a máquina some;
- caixa e terminal funcionam igual aos dos destroços.

**LOGs novos**: 2 ou 3 por estrutura, de 8 a 12 no total, encaixados na linha do tempo (`LOG_DAYS`; o "LOG 01..N" segue o dia; os índices em `LOGS` nunca mudam). Rascunho em `docs/lore/logs_v07_rascunho.md`, **aprovado pelo dono antes de entrar**.

**Save**: a estrutura sai da seed. No save vai só o que mudou (caixa aberta/esvaziada, máquina desmontada), no padrão do `removed_crates`. **Save antigo carrega**: as estruturas aparecem onde couberem sem atropelar o que o player construiu; onde não couber, aquela não nasce naquele mundo. Se isso complicar demais o código, o Dev avisa e a saída é "estrutura só em mundo novo".

**Mapa**: marcador "Ruína" quando o player chega perto; com o nome da estrutura depois de ler o terminal dela.

## Arte (Designer, em paralelo ao M1)

Tudo passa pelo dono no report antes de entrar no jogo.
- **5 destroços** a partir da referência do dono (`reports/design/v07_destrocos/referencia.png`): **#1 nave de passageiros** (nova; a que trouxe a colônia), **#2 base espacial** (vira o módulo; é bem maior que os 3×2 tiles de hoje), **#3 transportador de carga** (vira a nave de carga, VÉSPER-7; o **porão aberto** bem visível, é a porta do M4), **#4 sonda** (troca), **#5 robô de reconhecimento** (novo). No estilo do jogo: gerado por script, paleta da região, contorno `#1b1630`.
- **Kit médio de props** (14–16, 1 tile, sprite + ícone 16×16), servindo lab, acampamento, estação, posto, interior da nave e base do player. Ideias: bancada de laboratório, microscópio, estante com amostras, beliche, mesa, cadeira (e caída), caixote, entulho, mancha de gelo no chão, parede rachada, armário, tela/console apagado, tanque, placa.
- **Construtor** novo, com módulo de scanner.

## M2 · Props e scanner (detalhe na hora dele)

> Decisões fechadas com o dono em 2026-10-16 (liberados, cenário, props de parede, custo, colisão): bíblia §16, "Marco 2 · Props e scanner". Plano: `docs/superpowers/plans/2026-10-16-v07-marco2-props-scanner.md`.

- Prop é coisa colocável de 1 tile; colidir ou não é por prop. Na ruína pode estar "tombado".
- Aba **Decoração** no construtor, custo baratinho; 3–4 liberados de cara (mesa, cadeira, caixote).
- **Scan**: construtor na mão, mouse num prop de **ruína** que o player não conhece → contorno + "Escanear (segure)". Segura o **esquerdo** ~1,5 s (barrinha, som novo do Som) → "Projeto liberado: <nome>" e o prop entra na aba. Prop conhecido não ganha contorno. Com o fantasma de colocar na mão, o esquerdo é colocar (sem scan). **Direito segurado** continua sendo desmontar; prop de ruína não desmonta, prop do player desmonta.
- O que já foi escaneado vai no save.
- As plantas do M1 ganham letras de prop na legenda.

## M3 · Destroços novos (detalhe na hora dele)

- Os 3 sprites trocam; o módulo cresce (pegada do #2).
- Entram a **nave de passageiros** e o **robô de reconhecimento** (dá circuito e eletrônico), cada um com loot, LOG e pegada próprios, no mesmo sistema de tabela dos destroços.

> Decisões fechadas com o dono em 2026-10-16 (loot, LOGs, quantidade e lugar, save antigo): bíblia §16, "Marco 3 · Destroços novos". LOGs em `docs/lore/logs_v07_rascunho.md` (índices 19 e 20).

## M4 · Interior da VÉSPER-7 (detalhe na hora dele)

> Decisões fechadas com o dono em 2026-10-16 (uma VÉSPER por mundo, camada `vesper` sem giro, salas, porta emperrada com gancho de bateria + crachá, LOGs 21–23, sem construir dentro, aba no mapa, sons): bíblia §16, "Marco 4 · Interior da VÉSPER-7". Onde diverge do que está abaixo, vale a bíblia.

- **Camada nova pequena** (~48×48), uma por transportador, gerada com seed + destroço.
- Porta = o porão: E na boca, mesmo fade da rampa ("Entrando..." / "Saindo...").
- **Salas desenhadas à mão, encaixadas pela seed**: cabine, corredor, alojamento, porão e a **câmara fria**, com o contêiner de gelo **arrombado por dentro**.
- Escuro, luminária, caixas, props e LOG. O O₂ continua descendo (o "ir e voltar").

## Testes

- pytest em toda regra: planta carrega, 8 orientações, mesma seed = mesma ruína, destruição nunca fecha porta/caixa/terminal, casca não quebra nem desmonta, máquina quebrada desmonta uma vez, regra de lugar de cada estrutura (distância da cratera, do bolsão, dentro do bioma), save salva e carrega (e save antigo carrega).
- Depois: scan só em prop de ruína desconhecido, interior gerado pela seed, entrada e saída da camada.
- Smoke com print de cada estrutura no merge de cada marco.
