# v0.8 · Plantas (design)

Decisões do dono no brainstorm de 2026-10-16. Referências visuais em `reports/design/ideias/v08_plantas/`.

## Por quê

Hoje são 4 estágios: Tempestade 0, Árido 7k, Névoa 10k e Verde 100k. Depois da Névoa (máquinas nv.2) não aparece nada novo: de 10k a 100k o player só espera o Ti subir. Os objetivos também acabam em "construa uma máquina nv.2" → "deixe o planeta verde".

A v0.8 enche esse meio com **plantas**: um 4º índice (Biomassa), 2 estágios novos que pedem esse índice, 4 máquinas novas e a cadeia da água ganhando garrafa vazia e coletor.

**Fica de fora, de propósito:**
- o Verde funcional (respirar lá fora);
- fauna e tudo da Vida (vira v0.9);
- farm ao ar livre;
- receitas que usam as plantas fora do próprio ciclo;
- variar a amostra pelo tipo de gelo;
- cursor novo e colisão dos destroços (continuam no Futuro).

## Linha de estágios

**TEMPESTADE → ÁRIDO → ÚMIDO → ALGAS → MUSGO → VERDE**

| # | Chave | Nome (HUD) | Pede | O que muda |
|---|---|---|---|---|
| 1 | `storm` | TEMPESTADE | 0 | igual hoje |
| 2 | `arid` | ÁRIDO | 7.000 Ti | igual hoje |
| 3 | `mist` | **ÚMIDO** (era NÉVOA) | 10.000 Ti | igual hoje, mais: o coletor de água funciona daqui pra frente |
| 4 | `algae` (novo) | ALGAS | 25.000 Ti **e** biomassa 500 | os lagos esverdeiam; libera a centrífuga |
| 5 | `moss` (novo) | MUSGO | 50.000 Ti **e** biomassa 3.000 | o musgo nasce nas pedras (reaproveita a rampa `MOSS`) |
| 6 | `green` | VERDE | 100.000 Ti **e** biomassa 15.000 | igual hoje (fim do MVP; ainda não dá pra respirar lá fora) |

- Os números são de partida. O `tools/dev/balance_sim.py` acerta eles no M5.
- A chave `mist` continua. Muda só o texto: o nome curto vira **ÚMIDO** e o título continua "ESTÁGIO 3 · PRIMEIRAS CHUVAS".
- O estágio passa a exigir **as duas coisas**: o Ti total (O₂ + Calor + Água + Biomassa) e a biomassa mínima. Senão o player chega no Verde só com aquecedor.
- O HUD de "PRÓXIMO" mostra o que falta das duas, por exemplo "PRÓXIMO: ALGAS · Ti 18k/25k · biomassa 120/500".
- Save antigo: o estágio 4 (`green`) vira 6. O estágio é recalculado pelo Ti e pela biomassa no load, e quem tinha Verde sem biomassa volta pro estágio que os números mandam.

## Biomassa (4º índice)

- `state.indices` ganha a chave `biomass`, e o `ti` continua sendo a soma de todos.
- A biomassa sobe **por segundo**, como os outros índices: cada cultivador com planta crescendo e com água soma a taxa da cultura dele. Seco, sem planta ou fora da base vedada, ele não soma.
- A colheita **não** soma biomassa. Ela dá itens (ver Cultivador). Assim a taxa no HUD fica suave, igual às outras.
- Atalho de debug: **F7 +biomassa** (sempre ligado, no esquema do F2). O F6 fica reservado pro overlay de colisão do Futuro.

## Água: Dispersor proporcional, cápsula vazia e coletor

**Dispersor proporcional ao tamanho da base:**
```
duração da cápsula = DISPENSER_CAPSULE_TIME (180 s) × DISPENSER_REF_FLOOR (25) / len(seal.floor)
```
- Limitada entre 30 s e 360 s. Uma base 5×5 continua com os 3 min de hoje.
- O painel do Dispersor mostra "1 cápsula = N s nesta base".
- Mais de um Dispersor na mesma base continua como hoje: cada um queima a sua cápsula. A demanda **não** é dividida (decisão do dono).

**Cápsula vazia** (`water_capsule_empty`):
- Sai do Dispersor e do Cultivador cada vez que uma cápsula cheia acaba de ser usada.
- Cada uma das duas máquinas ganha um slot de saída pra vazias.
- Os drones levam as vazias pra baú ou pro coletor, do mesmo jeito que já levam cápsula cheia.
- O derretedor continua fabricando cápsula nova sem precisar de vazia (decisão do dono, opção A). A vazia só serve pro coletor.

**Coletor de água** (máquina nova, `water_collector`):
- Entra uma cápsula vazia e, com o tempo, sai uma cheia. Ele puxa a umidade do ar.
- Só funciona **na superfície e do estágio Úmido em diante**. Na caverna ou antes do Úmido, o painel diz por quê.
- Enche **mais rápido durante a chuva** (`rain_level`).
- Libera no fabricador por Ti, em 10.000.
- Gasta energia como as outras máquinas. Não soma índice.
- Motivo: tem mundo com um veio de gelo só, e a água vira gargalo justo quando as plantas pedem mais.

## Laboratório da Ilves trancado no gelo

O lab já existe (`game/ruin_plans/lab.txt`, ruína de superfície do v0.7 M1, na faixa gelada).

**O gelo:**
- O lab nasce com a porta dupla tampada por gelo.
- O gelo derrete com o **calor**, reaproveitando os gelos-portão: blocos, `thaw.gate_progress`, a dica "abre com ~N pK", o aviso e o som `ice_collapse`.
- A faixa de calor é escolhida pra abrir **entre o Úmido e as Algas**. O número sai do `balance_sim`.
- Antes de abrir, os LOGs e a caixa do lab ficam inalcançáveis.

**O que tem dentro, trocando os props atuais:**
- `prop_microscope_digital` vira a máquina **Microscópio quebrada**. Escanear dá o diagrama dele, e o diagrama vai pra lista de **máquinas**, não de decoração.
- `prop_sample_tank` vira o **Cultivador quebrado**. Escanear dá o diagrama dele, que também vai pra máquinas.
- A caixa do lab traz a **cultura-controle** (`algae`, 1 unidade), sempre, além do loot normal.
- Na lore, a cultura-controle é uma alga da Terra, que a colônia trouxe. A Ilves comparava ela com o gelo, e o player continua o experimento dela.

## Cultivador (`cultivator`)

**Regras:**
- Funciona **só dentro da base vedada** (o mesmo `seal.inside` do Dispersor).
- Recebe uma muda: `algae` ou uma das plantas.
- Com água, a planta cresce em **4 etapas** (muda → pequena → média → madura).
- Madura, ela produz a colheita e volta pra etapa 2: é perene, a muda não some.
- Biomassa por segundo enquanto cresce com água (ver Biomassa).

**Água:**
- Tem um **tanque interno de 5 cápsulas** e um **slot de reserva de 5 cápsulas**.
- Quando o tanque baixa de uma cápsula, ele puxa uma da reserva sozinho, e cada cápsula puxada vira uma vazia no slot de saída.
- Os drones abastecem a reserva.
- Cada cultura gasta água no seu ritmo. Seco, para de crescer e não soma biomassa, mas a planta não morre.

**Colheita:**
- Sai 1–2 itens da própria cultura (`algae`, `plant_1`, `plant_2`, `plant_3`) nos slots de saída (4 slots).
- O item serve de muda pra outro cultivador e de ingrediente da centrífuga.
- Saída cheia: a planta para na etapa madura até alguém esvaziar.

**UI** (rascunho do dono, `cultivador_ui_rascunho.png`):
- **Esquerda:** o tanque com o nível de água, o slot de reserva embaixo e a barra vertical de crescimento ao lado.
- **Meio:** o cilindro de vidro com a planta na etapa atual, sobre o substrato.
- **Direita:** os 4 slots de colheita.
- O inventário fica embaixo, no padrão dos outros painéis.

**Sprite no mundo:**
- O cilindro mostra a etapa atual de cada cultura (4 culturas × 4 etapas), mais o vazio.
- Referências do dono: `cultivador_ref_a.png` e `cultivador_ref_b.png`. Base cheia lê melhor em 40×56 do que pernas, e a Designer decide com o dono.

**Culturas** (números de partida):

| Cultura | Biomassa/s | Água (s por cápsula) | Ciclo até madura |
|---|---|---|---|
| Alga | 0,5 | 120 | 90 s |
| Planta 1 | 1,5 | 90 | 120 s |
| Planta 2 | 4 | 60 | 150 s |
| Planta 3 | 10 | 45 | 180 s |

Os nomes das 3 plantas saem na rodada de arte do M4. Até lá, as chaves são `plant_1..3`.

## Microscópio (`microscope`)

- Diagrama no lab.
- Entra **gelo** (o recurso `ice`), 1 por análise. Cada análise leva um tempo e gasta energia.
- Cada análise sorteia:

| Resultado | Chance |
|---|---|
| amostra simples (`sample_basic`) | 30% |
| amostra com mutação (`sample_mutant`) | 15% |
| amostra rara (`sample_rare`) | 5% |
| nada | 50% |

- O sorteio sai do rng do estado (determinístico no teste). Toca um "bip" quando sai amostra.

## Centrífuga (`centrifuge`)

- Libera no fabricador **no estágio Algas**. É uma trava por estágio, coisa nova: hoje só existe trava por Ti.
- Entra 1 `algae` + 1 amostra. Cada ciclo leva um tempo, gasta energia e tem chance de dar a planta:

| Amostra | Planta | Chance |
|---|---|---|
| simples | `plant_1` | 60% |
| mutação | `plant_2` | 45% |
| rara | `plant_3` | 30% |

- Falhou: consome os dois e não dá nada.

## Objetivos

Entram depois de "Construa uma máquina nv.2", trocando o "Deixe o planeta verde" pela sequência:

1. Ache o laboratório da Ilves
2. Derreta o gelo do laboratório
3. Escaneie o microscópio e o tanque do laboratório
4. Pegue a cultura-controle
5. Construa um cultivador dentro da base
6. Colha a primeira alga
7. Chegue ao estágio Algas
8. Consiga uma amostra no microscópio
9. Consiga uma planta nova na centrífuga
10. Chegue ao estágio Musgo
11. Deixe o planeta verde

O coletor entra como dica ("Pouco gelo? O coletor de água puxa a umidade do ar"), não como objetivo obrigatório.

## Save

- Formato **v14**:
  - `indices.biomass`;
  - estado do cultivador (cultura, etapa, progresso, tanque);
  - o progresso do microscópio e da centrífuga;
  - o novo item `water_capsule_empty`.
- Save v13 carrega com biomassa 0, estágio recalculado e o lab trancado se o calor ainda não chegou na faixa dele.
- O gelo do lab é derivado do calor, como os gelos-portão. Não vai no save.

## Marcos

| Marco | O quê | Depende de |
|---|---|---|
| **M1 · Biomassa e estágios** | índice Biomassa, 6 estágios com trava dupla, ÚMIDO, HUD do "próximo", visual de Algas (lago verde) e Musgo, F7 | — |
| **M2 · Água** | Dispersor proporcional, cápsula vazia, coletor de água, drones carregando vazias | — |
| **M3 · Lab e cultivador** | gelo do lab, máquinas quebradas que dão diagrama, cultura-controle, cultivador (regras, UI, sprite, colheita, biomassa) | M1, M2 |
| **M4 · Microscópio e centrífuga** | as duas máquinas, as amostras, as 3 plantas, a trava por estágio, os nomes das plantas | M3 |
| **M5 · Objetivos e fechamento** | objetivos novos, `balance_sim` com os estágios e a biomassa, smoke e shots | M4 |

**Arte (Designer, passa pelo dono):**
- cultivador: vazio + 4 culturas × 4 etapas, e a versão quebrada;
- microscópio e centrífuga, inteiros e quebrados;
- coletor de água;
- ícones: alga, plantas 1–3, 3 amostras, cápsula vazia;
- lago verde das Algas e o visual do Musgo;
- o gelo na porta do lab.

**Som (passa pelo dono):**
- borbulhar do cultivador (loop baixo, perto);
- giro da centrífuga;
- bip de amostra encontrada;
- gotejar do coletor.

## Testes

- Estágio com trava dupla: Ti alto e biomassa baixa não sobe, e vice-versa.
- Migração do save v13 com estágio 4 recalculado.
- Duração da cápsula por tamanho de base, com os limites de 30 e 360 s.
- Cápsula vazia saindo do Dispersor e do Cultivador. Os drones entregando vazia no coletor.
- Coletor parado antes do Úmido e na caverna, e mais rápido com chuva.
- Gelo do lab abrindo pela faixa de calor. Escanear a máquina quebrada dando o diagrama.
- Cultivador:
  - não cresce fora da base vedada nem seco;
  - perene, volta pra etapa 2;
  - para com a saída cheia;
  - soma a biomassa certa.
- Sorteios do microscópio e da centrífuga com rng fixo (as proporções batem em N grande).
- Objetivos na ordem nova, sem travar quem já passou.
