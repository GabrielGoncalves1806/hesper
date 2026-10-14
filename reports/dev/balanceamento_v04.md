# Balanceamento do v0.4 (Marco 4), com a magmatita

Rodada final. Feedback do dono no playtest: a **cratera** e os **gelos-portão** abriam rápido demais; o resto estava ok.
Medido com `tools/dev/balance_sim.py` (5 seeds, 5 estratégias, valores em minutos, média por estratégia). O jogador de
referência é o **casual**. "Antes" = o `main` na hora do pedido (com a magmatita); "depois" = o bloco
"v0.4 M4 balanceamento" no fim do `game/config.py`.

## 1. Diagnóstico (main antes do M4)

| estratégia | Ti 500 | magmat. | 1º aquec. | cratera | Árido | Névoa | portão 1 | portão 2 | portão 3 | L1 | L2 | L3 | Verde = total | déficit | desmaios |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guloso | 1,9 | 9,2 | 12,3 | 12,5 | 6,7 | 8,6 | 13,9 | 15,3 | 17,0 | 26,8* | — | — | 28,9 | 13,1 | 0 |
| variado | 2,0 | 3,1 | 3,4 | 4,4 | 7,7 | 9,6 | 10,2 | 13,9 | 18,2 | 9,7 | 25,0 | — | 31,6 | 12,8 | 0 |
| **casual** | 2,4 | 4,2 | 4,6 | **5,7** | 8,7 | 10,9 | **12,3** | 18,0 | 24,4 | 11,2 | 32,6 | — | 41,1 | 11,8 | 0 |
| caverna | 2,8 | 4,6 | 6,0 | 7,2 | 9,6 | 12,1 | 14,1 | 20,0 | 24,9 | 13,5 | 26,2 | — | 34,8 | 12,3 | 0 |
| destroços | 2,8 | 4,6 | 6,2 | 7,3 | 9,6 | 12,2 | 14,3 | 20,0 | 25,8 | 13,7 | 27,7 | — | 34,6 | 14,3 | 0 |

(* nem todas as seeds chegaram.) O que o dono sentiu aparece nos números: o casual abre a cratera **1,1 min depois do
1º aquecedor** (220 pK a 4 pK/s = 55 s) e o 1º gelo-portão aos 12 min, só 1,4 min depois da Névoa. O L3 nunca chega
(40.000 ppm; o jogo todo termina com ~25.000) e o L2 só aos 26-33 min. O "guloso" é um jogador caótico (a seed 5 só
fez o 1º aquecedor aos 20 min): serve de borda, não de referência.

## 2. Números trocados e o motivo

| config | antes | depois | motivo |
|---|---|---|---|
| `THAW_CRATER_HEAT` | (40, 90, 150, 220) | **(200, 450, 750, 1000)** | pedido do dono. 1.000 pK = ~4 min de 1 aquecedor (4 pK/s) ou ~2 min com 2. Casual: aquecedor 4m06s, cratera 7m54s (3m50s depois). As 4 etapas visuais ficam espaçadas (~50 s, 1m, 1m15, 1m) |
| `THAW_FUMAROLE_HEAT` | (40, 220) | **(200, 1000)**, atrelada à cratera | continua derivada: as fumarolas acordam uma a uma entre ~1 e ~4 min de aquecimento, dando feedback enquanto a tampa derrete. A magmatita acordada (1 a cada 20 s, até 6) está toda disponível bem antes do Aquecedor nv.2 (10 magmatita, Ti 10.000, ~10 min), e a dormente já cobre o 2º aquecedor (3 rochas por fumarola, 13-16 no mapa). Não precisou de faixa própria |
| `THAW_GATE_HEAT` | ((1500,2500,3500), (3500,5000,6500), (6000,8000,10000)) | **((2800,4300,5800), (5800,8000,10200), (14000,18000,22000))** | pedido do dono. O 1º abre no meio da partida (casual 15,6 min, 45%), o 2º aos 22 (64%) e o 3º aos 28 (80%, perto do Verde). O 3º passa a exigir Aquecedor nv.2 (~19.000 pK pra abrir), que é a "recompensa de fim de jogo" |
| `LAKE_WATER` | (3000, 15000, 40000) | **(2500, 7000, 15000)** | L1 junto com a Névoa (casual 10,2 min, na entrada), L2 no meio (16 min, era 33) e L3 antes do Verde (27 min; antes nunca chegava) |
| `SMALL_ROCK_CHANCE` | 0,013 | **0,019** | trazido da proposta anterior e reavaliado: a magmatita (ida às fumarolas) e a bacia sem rocha deixaram o casual em 41 min; com ~600 rochas ele volta a ~35 min (meta 25-40) |
| `ROCK_MAX` | 520 | **700** | com ~600 rochas na partida o teto de 520 desligaria o reaparecimento |
| `STAGES` Árido | 6.500 | **7.000** | as rochas a mais adiantam o Árido (casual 8m12s com 6.500); com 7.000 fica em 8m30s (meta 8-12 min) |

Não trazidos da proposta anterior: `RAIN_MIST_LEN/EVERY` e `RAIN_FIRST` (o dono aprovou a chuva no playtest; ela não
mexe no ritmo de recursos), portões `(2200,3700,5200)...` e `LAKE_WATER`/gelo (reavaliados com a magmatita, ver acima).
Mantidos: Névoa 10.000, Verde 100.000, receitas, taxas, O₂.

## 3. Antes × depois (médias de 5 seeds, minutos)

| marco | casual antes | casual depois | caverna antes | caverna depois | destroços antes | destroços depois |
|---|---|---|---|---|---|---|
| Ti 500 | 2,4 | 2,0 | 2,8 | 2,8 | 2,8 | 2,8 |
| 1º aquecedor | 4,6 | 4,1 | 6,0 | 6,3 | 6,2 | 6,4 |
| cratera | 5,7 | **7,9** | 7,2 | **10,6** | 7,3 | **10,7** |
| Árido | 8,7 | 8,5 | 9,6 | 10,1 | 9,6 | 10,0 |
| Névoa | 10,9 | 10,2 | 12,1 | 12,2 | 12,2 | 12,3 |
| portão 1 | 12,3 | **15,6** | 14,1 | 18,4 | 14,3 | 18,6 |
| portão 2 | 18,0 | **22,1** | 20,0 | 25,8 | 20,0 | 26,2 |
| portão 3 | 24,4 | **27,8** | 24,9 | 31,7 | 25,8 | 30,9 |
| L1 | 11,2 | 10,2 | 13,5 | 12,3 | 13,7 | 12,3 |
| L2 | 32,6 | **16,4** | 26,2 | 22,8 | 27,7 | 22,3 |
| L3 | — | **27,4** | — | 29,4 | — | 27,8 |
| Verde (total) | 41,1 | **34,6** | 34,8 | 36,4 | 34,6 | 34,5 |
| déficit de energia | 11,8 | 11,3 | 12,3 | 14,1 | 14,3 | 14,2 |
| desmaios (5 seeds) | 0 | 0 | 0 | 0 | 0 | 0 |

Variado (borda rápida): cratera 4,4 -> 6,6, portões 10,2/13,9/18,2 -> 12,3/17,8/23,5, total 31,6 -> 27,7.

## 4. Metas

- Árido entre 8 e 12 min no casual: 8,5 (8,3 a 8,6 nas seeds). Cumpre.
- Partida de 25 a 40 min: casual 34,6 (30,3 a 42,0; a seed 4 passa dos 40 por sorte nas rochas), caverna 36,4 (34,1 a
  39,6), destroços 34,5. Cumpre na média.
- Lagos visíveis no começo da Névoa: L1 no casual 0 s depois da Névoa (variado 0 s, caverna ~6 s). Cumpre.
- Sem desmaio e sem espera longa no meio do jogo (os testes do sim seguem passando).

## 5. Pontos pra olhar

- **Caverna e destroços** só descem depois da cratera: ela agora abre aos 10,6 min (era 7,2), ou seja, 3,4 min mais
  tarde. O total delas subiu pouco (34,8 -> 36,4) porque o sim já minera o resto na superfície nesse intervalo, mas na
  prática o jogador espera mais pela caverna. Se o dono achar demais, o 1º aquecedor + um 2º cedo corta pela metade.
- **Portão 3 pede Aquecedor nv.2.** Com só aquecedores nv.1 (~14.000 pK no fim da caverna/seed 4) ele não abre; todas as
  outras seeds o abriram. É de propósito (recompensa de fim), mas dá pra baixar o 3º trio pra (12000,16000,20000) se
  quiserem que ele abra sem nv.2.
- **F2 (+10.000 Ti)** gera ~3.333 de calor: abre a cratera mas não o portão 1 (precisa de ~4.600). Debug, só informa.
- O sim não modela esperar pela cratera nem escolher aquecer cedo: o tempo real depende de quando o jogador monta o
  aquecedor. A conta do dono (cratera 3 a 5 min depois do 1º aquecedor) vale pra 1 aquecedor.

## 6. Mudanças de código nesta rodada

- `game/config.py`: bloco "v0.4 M4 balanceamento" no fim (valores por cima dos antigos, que ficam nas linhas originais).
- `tools/dev/balance_sim.py`: colunas de magmatita, 1º aquecedor, portões 1-3 e lagos L1-L3; cache do mapa
  (`surface_gen._cache`) limpo ao aplicar overrides (corrige override de geração como `SMALL_ROCK_CHANCE`).
- Testes: `test_balance_sim.py` (tetos de referência: casual 52, caverna 40; teste novo do ritmo cratera/portões/lagos),
  `test_rock_respawn.py` (rochas iniciais 540-680), `test_pockets.py` (dica da cratera com ponto de milhar),
  `test_save.py` (o teste do portão fixa o calor em vez de depender do rich_state).
- `docs/GAME_BIBLE.md`: números da cratera, fumarolas, portões, lago e Árido.
