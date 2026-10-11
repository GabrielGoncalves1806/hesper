# Balanceamento: medição e proposta (Dev 4)

Gerado com `uv run python tools/dev/balance_sim.py --ablate-t2 --markdown`. É um simulador sem pygame que usa `GameState`,
`World` e `config` reais. A proposta está em `tools/dev/balance_proposal.json`; **o `game/config.py` não foi alterado.**

Estratégias:
- **guloso**: conhece o mapa, anda pelo caminho ótimo e sempre faz a máquina com o melhor Ti/s por segundo de coleta.
- **variado**: joga direito e alterna os tipos da maior tier liberada.
- **casual**: anda 30% a mais que o planejado, gasta +0,3 s por tile pra mirar e volta pra base com mais folga de O₂.

As seeds mudam só os drops (1–2). "Espera" é o tempo parado sem nada útil pra fazer: esperando uma receita liberar,
ou quando a próxima máquina não ficaria pronta antes do fim.

## Resumo (faixa das seeds 1–3)

| | Ti 500 | Névoa | Verde (total) | maior espera |
|---|---|---|---|---|
| **atual** guloso | 1m49–1m53 | 7m48–8m01 | 17m49–18m36 | 0m33 |
| **atual** variado | 1m53–1m54 | 7m51–8m04 | 19m18–19m28 | 0m00 |
| **atual** casual | 2m09–2m11 | 8m59–9m05 | 22m06–22m26 | 0m37 |
| **proposta** guloso | 2m34–2m38 | 9m55–10m15 | 22m59–23m33 | 0m00 |
| **proposta** variado | 2m29–2m34 | 9m59–10m09 | 23m55–24m29 | 0m20 |
| **proposta** casual | 2m51–2m57 | 11m08–11m31 | 27m28–27m54 | 0m12 |
| proposta **sem nv.2** (variado) | igual | igual | 32m09–32m24 | 0m18 |

Com os números atuais o jogo já é mais rápido que a meta: a Névoa chega aos ~8 min e o fim aos ~18–22 min.
Na proposta, as nv.2 cortam uns 8 min da fase Névoa→Verde (de ~22 pra ~14 min) e rendem 2,5–3× a nv.1 por recurso.

## Mudanças propostas

Mexi só em `MACHINES`. Os limiares (500 / 10.000 / 100.000), a mineração, o O₂ e a velocidade continuam iguais.

| máquina | receita atual → proposta | taxa atual → proposta | Ti/s por recurso |
|---|---|---|---|
| o2 | 10 Fe + 4 Si → 14 Fe + 6 Si | 3 → 2 | 0,21 → 0,10 |
| melter | 6 Fe + 10 gelo → 8 Fe + 12 gelo | 2 → 2 | 0,13 → 0,10 |
| heater | 12 Fe + 8 Si → 16 Fe + 12 Si | 4 → 3 | 0,20 → 0,11 |
| o2_t2 | 30 Fe + 20 Si + 10 gelo → 40 Fe + 25 Si + 15 gelo | 25 → 20 | 0,42 → 0,25 |
| melter_t2 | 25 Fe + 30 gelo → 30 Fe + 40 gelo | 20 → 16 | 0,36 → 0,23 |
| heater_t2 | 35 Fe + 25 Si → 45 Fe + 30 Si | 30 → 24 | 0,50 → 0,32 |

Por que assim:
- O tempo até um limiar cresce mais ou menos com √(custo/taxa): a taxa sobe linear com o tempo de coleta e o Ti
  sobe com o quadrado. Pra esticar uns 25–30% foi preciso quase dobrar custo/taxa da nv.1.
- O Derretedor nv.1 ficou com o mesmo Ti por recurso que o Gerador de O₂. Antes ele era o pior, e o guloso nunca fazia.
- Segurei as nv.2 em no máximo 80 recursos. Assim a reta final (a espera porque a próxima máquina não fica pronta
  a tempo) não passa de ~2 min.

## O "faltam ~2 h 48 min" do playtest

Esse número não é o ritmo real. O HUD divide o Ti que falta pela taxa **atual**, só que a taxa cresce o jogo todo.
O mais provável é que o dono tenha usado o F2 (+10.000 Ti) com umas 3 máquinas nv.1: ~9 Ti/s dá 90.000 / 9 ≈ 2 h 47 min.
Jogando normal, o simulador chega na Névoa com ~40 Ti/s. Nessa hora o HUD mostra ~21 min (atual) / ~44 min (proposta)
até o Verde, mas o tempo real é ~11 / ~14 min. Sugestão (fora do meu escopo): estimar com a taxa projetada, ou trocar o
"~X min" por porcentagem até a taxa estabilizar.

## Limitações

- O movimento é por grid (Dijkstra com 8 vizinhos, custo = TILE / PLAYER_SPEED por tile), e não `Player.move` frame a
  frame. As máquinas colocadas não bloqueiam o caminho. O "casual" compensa com +30% de andar.
- O jogador simulado conhece o mapa inteiro e minera através de paredes dentro do alcance 2 (a regra real deixa).
  Um humano jogando pela primeira vez explora e mira pior. Os tempos do "casual" são o melhor palpite e não foram
  calibrados com playtest. Se o próximo playtest der bem mais lento que o "casual", o ajuste é no custo/taxa, não no simulador.
- Craftar + colocar custa um tempo fixo de 3–6 s por máquina. Ler terminal e explorar não entram na conta.
- O guloso usa um "segundos por recurso" único, sem saber que o silício é mais raro perto da base.

## Tabelas completas

### Números atuais (game/config.py)

| estratégia | seed | Ti 500 | Névoa | Verde | total | espera total | maior espera | desm. | máquinas (o2/melter/heater/o2_t2/melter_t2/heater_t2) |
|---|---|---|---|---|---|---|---|---|---|
| guloso | 1 | 1m49s | 8m01s | 18m36s | 18m36s | 0m19s | 0m14s | 0 | 12/0/1/0/0/7 |
| guloso | 2 | 1m51s | 7m57s | 17m52s | 17m52s | 0m33s | 0m33s | 0 | 11/0/0/0/0/8 |
| guloso | 3 | 1m53s | 7m48s | 17m49s | 17m49s | 0m12s | 0m12s | 0 | 12/0/0/0/1/7 |
| variado | 1 | 1m53s | 8m01s | 19m18s | 19m18s | 0m00s | 0m00s | 0 | 5/6/5/3/2/2 |
| variado | 2 | 1m54s | 8m04s | 19m28s | 19m28s | 0m00s | 0m00s | 0 | 5/6/4/3/3/2 |
| variado | 3 | 1m54s | 7m51s | 19m27s | 19m27s | 0m00s | 0m00s | 0 | 7/6/5/2/3/2 |
| casual | 1 | 2m09s | 9m02s | 22m26s | 22m26s | 0m00s | 0m00s | 0 | 6/6/4/2/2/2 |
| casual | 2 | 2m10s | 9m05s | 22m25s | 22m25s | 0m03s | 0m03s | 0 | 5/6/3/2/2/3 |
| casual | 3 | 2m11s | 8m59s | 22m06s | 22m06s | 0m37s | 0m37s | 0 | 5/6/4/2/2/2 |

### Proposta (balance_proposal.json)

| estratégia | seed | Ti 500 | Névoa | Verde | total | espera total | maior espera | desm. | máquinas (o2/melter/heater/o2_t2/melter_t2/heater_t2) |
|---|---|---|---|---|---|---|---|---|---|
| guloso | 1 | 2m34s | 9m55s | 23m00s | 23m00s | 0m00s | 0m00s | 0 | 4/0/8/1/0/6 |
| guloso | 2 | 2m35s | 10m15s | 22m59s | 22m59s | 0m00s | 0m00s | 0 | 4/0/8/0/1/6 |
| guloso | 3 | 2m38s | 10m02s | 23m33s | 23m33s | 0m00s | 0m00s | 0 | 4/0/8/0/2/6 |
| variado | 1 | 2m31s | 9m59s | 24m29s | 24m29s | 0m20s | 0m20s | 0 | 5/7/4/3/2/2 |
| variado | 2 | 2m29s | 10m09s | 23m55s | 23m55s | 0m05s | 0m05s | 0 | 6/7/4/3/2/2 |
| variado | 3 | 2m34s | 10m02s | 24m01s | 24m01s | 0m01s | 0m01s | 0 | 5/7/5/3/2/2 |
| casual | 1 | 2m54s | 11m08s | 27m42s | 27m42s | 0m06s | 0m06s | 0 | 6/6/4/2/2/2 |
| casual | 2 | 2m51s | 11m31s | 27m28s | 27m28s | 0m12s | 0m12s | 0 | 5/5/3/2/2/3 |
| casual | 3 | 2m57s | 11m19s | 27m54s | 27m54s | 0m09s | 0m09s | 0 | 5/6/4/2/2/2 |

### Proposta SEM nv.2 (as nv.2 valem a pena?)

| estratégia | seed | Ti 500 | Névoa | Verde | total | espera total | maior espera | desm. | máquinas (o2/melter/heater/o2_t2/melter_t2/heater_t2) |
|---|---|---|---|---|---|---|---|---|---|
| guloso | 1 | 2m34s | 9m55s | 31m25s | 31m25s | 0m00s | 0m00s | 0 | 4/0/32/0/0/0 |
| guloso | 2 | 2m35s | 10m15s | 31m35s | 31m35s | 0m00s | 0m00s | 0 | 4/1/31/0/0/0 |
| guloso | 3 | 2m38s | 10m01s | 31m40s | 31m40s | 0m23s | 0m23s | 0 | 4/1/31/0/0/0 |
| variado | 1 | 2m31s | 9m59s | 32m09s | 32m09s | 0m00s | 0m00s | 0 | 15/15/13/0/0/0 |
| variado | 2 | 2m29s | 10m09s | 32m19s | 32m19s | 0m06s | 0m06s | 0 | 16/14/13/0/0/0 |
| variado | 3 | 2m34s | 10m02s | 32m24s | 32m24s | 0m18s | 0m18s | 0 | 15/16/13/0/0/0 |
| casual | 1 | 2m54s | 11m08s | 36m25s | 36m25s | 0m44s | 0m44s | 0 | 13/14/11/0/0/0 |
| casual | 2 | 2m51s | 11m31s | 36m32s | 36m32s | 0m30s | 0m30s | 0 | 13/14/12/0/0/0 |
| casual | 3 | 2m57s | 11m19s | 36m24s | 36m24s | 0m13s | 0m13s | 0 | 13/15/11/0/0/0 |
