# v0.4 · Mundo vivo (design)

Aprovado pelo dono no brainstorm de 2026-10-13. Substitui a lista antiga do v0.4 ("Fundo"), que foi pro v0.5.

## Objetivo

O planeta continua morto, mas para de parecer um mapa de tileset e vira um **lugar**. Ele reage ao jogador (a tempestade baixa, o gelo derrete, chove e os lagos enchem) e tem geografia pra explorar: regiões, relevo e formações que servem de marco.

"Vivo" aqui não é bicho. É o mundo ter personalidade e responder à terraformação.

## Decisões do dono

| Tema | Decisão |
|---|---|
| Escopo | Mundo vivo + o gancho das peças raras atrás do gelo. Mochila, broca nv.2, elevador de carga, biomas de caverna e peças raras de verdade vão pro v0.5 |
| Estágios | 4: **Tempestade → Árido → Névoa → Verde** |
| Tempestade | Visual + pressão leve: pouca visibilidade, rajadas que fecham mais a visão, **empurram o player** e fazem o minimapa chiar, e O₂ fora da base gastando um pouco mais rápido |
| Superfície | "Árido e vazio", não areia. **3 regiões**: planalto rachado (em volta da base), salar e basalto, mais uma faixa gelada |
| Orgânico | Nível 1 (decoração que disfarça a grade) + nível 2 (formações grandes de verdade). Terreno sem grade (curvas) fica de fora |
| Formações | **Misto**: formações grandes fixas, que não se mineram e servem de marco, com afloramentos de minério mineráveis em volta |
| Gelo | **Escalonado**: a **cratera nasce coberta de gelo** e derrete cedo (1º marco de calor). Mais 2 ou 3 gelos maiores abrem em marcos de calor maiores. O gelo encolhe em etapas visíveis |
| Atrás do gelo | Destroços melhores e um **contêiner lacrado** (gancho das peças raras do v0.5, ainda sem uso) |
| Água | Relevo com depressões. Na Névoa começa a **chover** e os lagos **enchem as depressões** com o índice de água. O **salar é a maior depressão** (leito de lago seco) e vira o grande lago. Sai o "lago aleatório em todo canto" de hoje |
| Máquina na água | A água sobe e a máquina fica **submersa e para de funcionar**, mas o player ainda pode recolher. Onde já tem água não dá pra construir |
| Save | Geração nova: **exige novo jogo** (save v7) |

Ganchos pro futuro (fora do v0.4):
- **basalto → vulcão**;
- **espécie nativa** que sobreviveu indo pras cavernas (as ossadas entram no subterrâneo, junto com a lore dela). No v0.4 **não tem ossada** na superfície.

## Marcos

### Marco 1 · Tempestade (os 4 estágios)

Roda no mapa de hoje: não depende da geografia nova.

- **Estágios** (`config.STAGES`), numerados de 1 a 4:

  | # | Chave | Ti de partida | Visual |
  |---|---|---|---|
  | 1 | `storm` | 0 | o chão de hoje (`dead`) + poeira |
  | 2 | `arid` | 2.500 | o chão de hoje (`dead`), céu limpo |
  | 3 | `mist` | 10.000 | Névoa (igual hoje) |
  | 4 | `green` | 100.000 | Verde (igual hoje), fim do jogo |

  O Ti do Árido é chute de partida: o simulador (`tools/dev/balance_sim.py`) ajusta pra o Árido chegar nos **primeiros ~8 a 12 minutos** do casual. Névoa e Verde mantêm os números de hoje, a não ser que o simulador mostre que a partida mudou de tamanho. Os sprites do Árido são os do `dead`, sem arte nova de chão; o código que hoje usa a chave `dead` passa a mapear `storm` e `arid` pra ela.

- **Visibilidade da tempestade**: uma camada de poeira por cima do mundo, reaproveitando o `Lighting` da caverna, mas com uma "luz" de visão em volta do player de **~7 tiles** sobre um fundo cor de poeira (não preto), mais as luzes da base, porque as máquinas abrem a vista em volta delas.
  - Partículas e faixas de poeira andando com o vento: direção dominante do vento + variação lenta.
  - A HUD fica sempre legível, por cima da poeira.

- **Rajadas**: a cada ~20 a 40 s (sorteio com seed), uma rajada de ~3 a 5 s:
  - a visão cai pra ~4 tiles;
  - o player é **empurrado** na direção do vento: velocidade somada, ~35% da de andar, que ele consegue vencer andando contra;
  - o minimapa **chia** (ruído por cima) e o mapa aberto também, se estiver aberto;
  - aviso no HUD e som de rajada.

- **O₂**: fora da base, na tempestade, o O₂ gasta **×1,25**. A zona da base não muda.

- **Saindo da tempestade**: a passagem pro Árido acontece **ao longo de ~20 s**. A poeira afina, as rajadas param e o céu limpa, com aviso de estágio ("ESTÁGIO 2 · CÉU LIMPO" ou similar) e jingle. Do Árido em diante não tem rajada nem penalidade.

- **Caverna**: a tempestade não entra na caverna. Lá embaixo vale o escuro de hoje, sem poeira.

- **Arte e som** (passam pelo dono antes de entrar):
  - Designer: textura e partículas de poeira e cor do fundo da tempestade, além do ícone e banner do estágio, se precisar;
  - Som: `amb_storm` (vento forte em loop), `gust` (rajada) e o jingle de saída, se quiser um próprio.

- **Objetivos**: o primeiro objetivo passa a ser sobreviver e montar a base no meio da tempestade. Em seguida vem "Limpe o céu (Árido)", ligado ao Ti do Árido.

- **Save**: o Marco 1 sozinho não muda a geração, mas os estágios mudam de número. Save v6 carregado: mapeia estágio 1→2, 2→3 e 3→4, porque quem já jogou passou da tempestade. O save v7 (novo jogo obrigatório) vem no Marco 2.

- **Testes**: estágios e limites, mapeamento de chave pra sprites, visibilidade (raio por estágio e na rajada), empurrão (soma de velocidade e dá pra vencer andando contra), O₂ ×1,25 só fora da base e só na tempestade, chiado do minimapa, nada disso na caverna, transição de ~20 s e carga do save v6. Prints no smoke e no `real_video_check.py`.

### Marco 2 · Geografia nova

- **Relevo**: mapa de altura (noise) no gerador da superfície. As depressões são marcadas (bacias) e o salar fica na maior.
- **3 regiões**: planalto rachado em volta da base, salar e basalto, mais a faixa gelada. Cada uma com seu chão, suas formações e sua decoração.
- **Formações fixas**: sprites grandes com colisão própria (monolito, arco, pináculo de basalto, crosta de sal elevada). Não se mineram e aparecem como marco no mapa. **Afloramentos de minério** em volta delas.
- **Morros mineráveis** com borda irregular, sem degrau de grade.
- **Camada de decoração** (não colide, não minera): manchas grandes que atravessam vários tiles, rachaduras longas, crosta, cascalho e sulcos de vento.
- **Arte**: paleta base por região, e os 4 estágios como variação de cor (sem desenhar 12 conjuntos à mão).
- **Save v7** (novo jogo obrigatório).

### Marco 3 · Gelo e água

- **Gelo da cratera**: a cratera nasce coberta. Ele derrete no 1º marco de calor, em etapas visíveis, e libera a descida.
- **Gelos-portão** (2 ou 3, na faixa gelada e em passagens): abrem em marcos de calor maiores. Atrás deles ficam destroços melhores e o **contêiner lacrado** (sem uso no v0.4, com dica de lore).
- **Chuva** na Névoa (efeito e som), e os **lagos enchem as depressões** conforme o índice de água sobe, das partes mais fundas pra fora. O salar vira o grande lago. A marca d'água seca no chão mostra onde vai alagar.
- **Máquina submersa**: para de funcionar e pode ser recolhida. Não dá pra construir na água.
- **Plantas** no Verde preferem a beira d'água.
- **Objetivos**: "Derreta o gelo da cratera" e os seguintes.

### Marco 4 · Polimento e playtest

Playtest do dono, ajustes, balanceamento no simulador (tempo de partida com a tempestade e os portões) e desempenho (relevo, decoração, poeira e chuva no orçamento de 16,7 ms).

## Riscos

- **Desempenho**: a poeira da tempestade e a chuva cobrem a tela toda. Tem que reaproveitar o `Lighting` (célula de 4 px) e medir no smoke.
- **Legibilidade na tempestade**: poeira demais frustra. A visão de 7 tiles e o empurrão de 35% são pontos de partida, a acertar no playtest.
- **Escopo do Marco 2**: é o maior. Se pesar, a decoração (nível 1) entra antes e as formações (nível 2) depois, dentro do mesmo marco.
