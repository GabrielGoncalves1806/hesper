# v0.8 M6 · Task 3: Plantas no `balance_sim`

## O que mudou

- **`tools/dev/balance_sim.py`**
  - **Overrides:** o `patched_config` aceita `"CROPS": {"algae": {"cycle": 150}}`. Usa `Crop._replace` e restaura na saída.
  - **3a · Tabela das plantas.** `crop_table(overrides=None, hours=1.0)`, um `GameState` com base vedada 5×5 de verdade (chão, parede, porta, Dispersor), como o `demo_base` dos testes. Um Cultivador por cultura, sem e com adubo contínuo, rodando o `_update_machines` real com dt = 1 s. Por cultura mede:
    - colheitas/h e itens/h;
    - biomassa/s;
    - água (fração do tempo crescendo);
    - cápsulas/h;
    - adubos/h, no caso com adubo.
  - **Funções novas da 3a:**
    - `plant_cost(item)` abre fibra, gel, resina e adubo até a planta, pelas receitas e pelo `CRAFT_YIELD`;
    - `plant_times()` dá o tempo da 1ª Folha, Espiral e Lírio e o das três (conta fechada com `MICROSCOPE_ODDS` × `CENTRIFUGE_RECIPES`);
    - `plant_times_rng()` confere a conta com o `microscope_roll` real e o teste da centrífuga;
    - `crop_report()` junta tudo: consumo da Centrífuga, cultivadores por Centrífuga, custo dos 6 itens do M5 e tempo do kit;
    - `crop_text()` imprime.
  - **Flags novas:** `--crops` e `--crop-hours` (padrão 10 h pro `--crops`, N grande pros itens/h).
  - **3b · Simulação principal:**
    - `Strategy.cultivators` (padrão 3).
    - **Lab abre:** `Layer.lab_ice_open`, ou `thaw.lab_ice_progress(heat) >= lab_ice_opens_at`, interpolado pelo ritmo do calor.
    - **Biomassa virtual:** começa em max(lab, Úmido) + `craft_overhead`, a N × bio/s da tabela. Quando a receita da Centrífuga sai de `locked` (o `recipe_status` real), um cultivador troca a alga por cada planta no tempo esperado da 1ª dela.
    - **`_produce`:** anda em pedaços de até 5 s, cortando nos instantes em que a bio/s muda.
    - **Marcas:** as dos estágios saem do `stage_for_ti(ti, biomassa)` real, no instante interpolado. O fim é o Verde de verdade (Ti E biomassa).
    - **Espera:** com o Ti fechado e a biomassa faltando, a espera é "esperando biomassa", em pedaços de até 60 s.
    - **`Result` ganhou:** `lab_at`, `bio_at`, `centrifuge_at`, `switch_at`, `bottleneck`, `ti_done`, `locked_tries`, `biomass`.
    - **`mark_label`:** sem o " (Ti)".
    - **Tabela:** colunas novas "lab abre", "bio desde", "gargalo (Algas/Musgo/Verde)", "Ti 100k" e "Folha/Espiral/Lírio".
    - **Docstring:** seção "v0.8 M6 · Plantas", com o que é real e o que é aproximado.
- **`tools/dev/balance_proposal.json`:** entrou `CROPS` com a proposta de partida (150/240/360/540).
- **`tests/test_m6_balance_v08.py`** (novo, 8 testes):
  - a linha da alga ≈ 3600 / (ciclo × 2/3) ±10%, e bio/s = `CROPS.biomass`;
  - o adubo dobra as colheitas e não muda a bio/s;
  - o override de `CROPS` muda o ciclo e é restaurado;
  - o custo em plantas vem das receitas;
  - a conta fechada das amostras bate com o rng (±10%);
  - o "Lab abre" vem antes do Algas (casual, seed 1);
  - as marcas e o gargalo existem e estão em ordem;
  - com `cultivators=0` o Algas nunca chega (com 3, chega: é o fixture);
  - a Centrífuga só destrava depois do Algas, e `locked_tries == 0`.
- **`tests/test_balance_sim.py`:** ajustado ao Verde de verdade (ver "Diferente do plano").
- **`reports/dev/v08_m6_balance.md`:** saída do `--crops --markdown` e do `--markdown`, mais o comentário.

Nada em `game/`, `assets/` ou nos números do `config.py`.

## Testes

```
uv run pytest tests/test_m6_balance_v08.py tests/test_balance_sim.py -q
19 passed in 48.51s
```

## Números principais (10 h por cultura)

| cultura | ciclo atual → proposta | itens/h | bio/s |
|---|---|---|---|
| Alga | 90 → 150 s | 88 → 54 | 0,5 |
| Folha-gota | 120 → 240 s | 68 → 34 | 1,5 |
| Espiral | 150 → 360 s | 54 → 22 | 4 |
| Lírio | 180 → 540 s | 45 → 15 | 10 |

- **Centrífuga:** 120 algas/h sem parar, 90/h alimentada por 1 Microscópio. Dá 1,36 / 1,02 cultivadores de alga no atual e 2,21 / 1,66 na proposta.
- **Kit do M5** (29 algas, 6 Folhas, 12 Espirais): 13 min no atual, 32 min na proposta, com 3 de alga + 1 de cada planta.
- **1ª planta por amostra:** Folha 2m21s, Espiral 5m26s, Lírio 22m43s, as três 23m41s. O rng dá 22m31s pro Lírio.
- **Verde:** sempre ~31 min depois do Algas, com a biomassa de gargalo. O ciclo não muda a bio/s.

## Aproximações

- **Tabela:**
  - a água e o Dispersor são enchidos e a colheita é esvaziada a cada segundo;
  - a medição começa no regime (planta recém-colhida);
  - energia sobrando: o fator é 1.
- **Biomassa virtual:**
  - não constrói cultivador, base vedada, microscópio nem centrífuga (o sim não faz lingote, circuito nem fio);
  - não gasta energia nem cápsulas, e não usa os itens colhidos;
  - cada planta entra no tempo esperado da 1ª dela, contado da Centrífuga, independente das outras;
  - só os N primeiros cultivadores trocam.
- **Plantas por amostra:** a conta supõe que a Centrífuga dá conta do Microscópio (1 amostra a cada 40 s, contra um ciclo de 30 s) e que não há fila de tipos de amostra.
- **"Lab abre":** se a seed não tiver lab, vale o `lab_ice_opens_at` padrão (1.0, ou seja 8.000 pK).

## Diferente do plano

- **`tests/test_balance_sim.py` mudou.** O plano listava só o teste novo, mas o 3b muda o fim e os rótulos, então o arquivo antigo teve que mudar:
  - os rótulos perderam o " (Ti)";
  - os tetos de tempo (54 min, caverna 25–40, portão 3 ≥ 0,7×) agora valem pro `ti_done` (o ritmo do Ti, que é o que eles mediam), não pro `total`, que virou o Verde com biomassa (~50–61 min);
  - a espera "esperando biomassa" fica fora do teto das esperas desde que seja a que fecha a partida.
- **A Centrífuga não é fabricada de verdade.** O teste "não é fabricada antes do Algas" virou: `centrifuge_at` (receita destravada pelo `recipe_status` real) ≥ Algas, mais um contador `locked_tries` em todo `build`/`craft` do sim, que tem que ficar em 0.
- **A troca de planta é independente por planta**, contada da Centrífuga, e não em cadeia ("a cada t_planta"). O Microscópio sorteia as três em paralelo.
- **`--crops` usa 10 h por cultura** (o plano dizia 1 h; foi pra ter N grande nos itens/h). O `crop_table()` e os testes usam 1 h.

## Riscos

- **O `total` das tabelas mudou de sentido:** agora é o Verde com biomassa. Quem comparar com o `reports/dev/balance.md` antigo precisa olhar a coluna "Ti 100k".
- **O teto de espera ficou mais frouxo:** se a maior espera for a de biomassa, uma espera longa no meio do jogo pode ficar escondida atrás dela (o teste só olha a maior).
- **A coluna de máquinas da tabela ficou enorme:** ela lista todo o `C.MACHINES`, que cresceu muito. Isso já vinha de antes; não mexi.
- **O sim ficou um pouco mais lento** por causa dos pedaços de 5 s (casual, seed 1: 3,9 s → 4,1 s de CPU). A suíte completa não foi cronometrada.
- **Ruff:** os avisos novos são cosméticos (concatenação de string no `crop_text`). O projeto não roda ruff.
