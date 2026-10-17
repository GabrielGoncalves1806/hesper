# v0.8 M6 · Plantas no `balance_sim` (atual × proposta)

Gerado por:

```
uv run python tools/dev/balance_sim.py --crops --markdown     # tabela das plantas (10 h de jogo por cultura)
uv run python tools/dev/balance_sim.py --markdown             # marcas, seeds 1–3, todas as estratégias
```

- **Atual** = `game/config.py` (alga 90 s, Folha-gota 120 s, Espiral 150 s, Lírio 180 s).
- **Proposta** = `tools/dev/balance_proposal.json`: os ciclos de partida do ROADMAP (alga 150, Folha 240, Espiral 360, Lírio 540) por cima da proposta antiga das máquinas.
- **Sem F1.** Tudo aqui é tempo de jogo em ×1. O dono testa com ×10, então divida por 10 o que ele sente no teste.
- **Isto não é proposta de número final.** Os números são decididos na Task 4, com o dono.

## O que os números dizem

1. **A alga rende demais pro consumo, no atual.** Um cultivador dá **88 algas/h**, não as ~72/h (6 a cada 5 min) da conta do ROADMAP: depois da colheita a planta volta pra 1/3, então colhe a cada 60 s, com 1,5 alga por colheita. Uma Centrífuga alimentada por 1 Microscópio come 90 algas/h, o que dá **~1 cultivador de alga**. Sem parar, come 120/h (1,36 cultivador). Três cultivadores fazem ~264/h, e o kit inteiro do M5 só pede 29 algas. Com a alga a 150 s, cai pra 54/h: 1,66 cultivador por Centrífuga alimentada, e 3 cultivadores ainda sobram (162 contra 90).
2. **Quem trava os estágios novos é a biomassa, e o ciclo não muda a biomassa.** Algas, Musgo e Verde têm "bio" como gargalo em quase todas as rodadas (só o guloso da proposta pega Algas pelo Ti). O Verde chega sempre **~31 min depois do Algas**, tanto no atual quanto na proposta: o `biomass/s` não muda com o ciclo. O relógio é dominado pelo **Lírio**, que sai em média **22m43s** depois da Centrífuga (1,5% por gelo) e sozinho faz 10 dos 15,5 de bio/s. O jogador fecha o Ti entre 27 e 45 min e depois espera de **7 a 30 min** só a biomassa ("esperando biomassa"). Pra mexer no fim do jogo, os botões são a bio/s, a biomassa mínima dos estágios, as odds das amostras ou o número de cultivadores. O ciclo não serve pra isso.
3. **Lírio a 540 s:** cai de 45 pra **15 Lírios/h** (31/h com adubo). Na v0.8 o Lírio só vira essência, que não tem uso, e a bio/s dele continua 10. Então a 540 s só fica chato pra quem quer a essência: o ritmo dos estágios não muda. Quem sente mais a proposta é a **Espiral** (22/h): o kit do M5 (12 Espirais, por causa da resina) passa de **13 min pra 32 min** com 3 de alga + 1 de cada planta.
4. **Adubo contínuo é caro:** 30 adubos/h por cultivador = 15 algas + **30 Folhas-gota**/h. Na proposta, um cultivador de Folha faz 34/h, então manter um cultivador adubado come quase um cultivador de Folha inteiro.
5. **O gelo do lab é a porta da biomassa:** ele abre sempre depois do Úmido, entre 17 e 25 min no atual (12 a 25 min na proposta, que esquenta antes). É ele que decide quando a biomassa começa.

Leitura das colunas novas da tabela das marcas:
- **lab abre**: quando a fresta do gelo do lab abriu.
- **bio desde**: lab aberto e Úmido, mais o tempo de fabricar.
- **gargalo**: o que chegou por último em cada estágio, Ti ou bio.
- **Ti 100k**: quando o Ti sozinho bateu o do Verde.
- **Folha/Espiral/Lírio**: quando cada cultivador trocou a alga pela planta.

A biomassa da simulação principal é **virtual** (3 cultivadores; ver o docstring do sim).

### Plantas: números atuais (game/config.py)

#### Cultivador, regra real (10 h de jogo, dt = 1 s, água sempre cheia, base vedada 5×5)

| cultura | ciclo | colheitas/h | itens/h | bio/s | água | cápsulas/h | adubo: colheitas/h | adubo: itens/h | adubos/h |
|---|---|---|---|---|---|---|---|---|---|
| Alga | 90 s | 60 | 88 | 0.50 | 100% | 30 | 120 | 178 | 30 |
| Folha-gota | 120 s | 45 | 68 | 1.50 | 100% | 40 | 90 | 133 | 30 |
| Espiral-de-geada | 150 s | 36 | 54 | 4.00 | 100% | 60 | 72 | 107 | 30 |
| Lírio-de-Ilves | 180 s | 30 | 45 | 10.00 | 100% | 80 | 60 | 88 | 30 |

#### Consumo (receitas reais do config)

- Centrífuga sem parar: 120 algas/h = 1.36 cultivadores de alga (88 algas/h cada).
- Alimentada por 1 Microscópio (1 amostra a cada 40 s em média): 90 algas/h = 1.02 cultivadores de alga.
- Adubo contínuo num cultivador: ~30 adubos/h = 15 Alga + 30 Folha-gota por hora.

| item | custo em plantas |
|---|---|
| Mochila T2 | 12 Alga |
| Tanque de O₂ nv.2 | 6 Alga, 4 Folha-gota |
| Botas de tração | 6 Alga, 4 Espiral-de-geada |
| Drone nv.2 | 4 Alga, 4 Espiral-de-geada |
| Luminária bio | 4 Espiral-de-geada |
| Adubo | 0.5 Alga, 1 Folha-gota |

- Kit do M5 (1 de cada item, 1 receita de adubo): 29 Alga, 6 Folha-gota, 12 Espiral-de-geada. Com 3 de Alga, 1 de Folha-gota, 1 de Espiral-de-geada, 1 de Lírio-de-Ilves: 13m16s (gargalo: Espiral-de-geada; começa com a muda de cada planta na mão).

#### Plantas por amostra (1 Microscópio → 1 Centrífuga; odds reais, conta fechada × 2000 rodadas de rng)

| 1ª planta | chance por gelo | conta | rng |
|---|---|---|---|
| Folha-gota | 18.0% | 2m21s | 2m20s |
| Espiral-de-geada | 6.8% | 5m26s | 5m20s |
| Lírio-de-Ilves | 1.5% | 22m43s | 22m31s |
| as três | — | 23m41s | 23m29s |

### Plantas: proposta (balance_proposal.json)

#### Cultivador, regra real (10 h de jogo, dt = 1 s, água sempre cheia, base vedada 5×5)

| cultura | ciclo | colheitas/h | itens/h | bio/s | água | cápsulas/h | adubo: colheitas/h | adubo: itens/h | adubos/h |
|---|---|---|---|---|---|---|---|---|---|
| Alga | 150 s | 36 | 54 | 0.50 | 100% | 30 | 72 | 107 | 30 |
| Folha-gota | 240 s | 22 | 34 | 1.50 | 100% | 40 | 45 | 68 | 30 |
| Espiral-de-geada | 360 s | 15 | 22 | 4.00 | 100% | 60 | 30 | 45 | 30 |
| Lírio-de-Ilves | 540 s | 10 | 15 | 10.00 | 100% | 80 | 20 | 31 | 30 |

#### Consumo (receitas reais do config)

- Centrífuga sem parar: 120 algas/h = 2.21 cultivadores de alga (54 algas/h cada).
- Alimentada por 1 Microscópio (1 amostra a cada 40 s em média): 90 algas/h = 1.66 cultivadores de alga.
- Adubo contínuo num cultivador: ~30 adubos/h = 15 Alga + 30 Folha-gota por hora.

| item | custo em plantas |
|---|---|
| Mochila T2 | 12 Alga |
| Tanque de O₂ nv.2 | 6 Alga, 4 Folha-gota |
| Botas de tração | 6 Alga, 4 Espiral-de-geada |
| Drone nv.2 | 4 Alga, 4 Espiral-de-geada |
| Luminária bio | 4 Espiral-de-geada |
| Adubo | 0.5 Alga, 1 Folha-gota |

- Kit do M5 (1 de cada item, 1 receita de adubo): 29 Alga, 6 Folha-gota, 12 Espiral-de-geada. Com 3 de Alga, 1 de Folha-gota, 1 de Espiral-de-geada, 1 de Lírio-de-Ilves: 32m17s (gargalo: Espiral-de-geada; começa com a muda de cada planta na mão).

#### Plantas por amostra (1 Microscópio → 1 Centrífuga; odds reais, conta fechada × 2000 rodadas de rng)

| 1ª planta | chance por gelo | conta | rng |
|---|---|---|---|
| Folha-gota | 18.0% | 2m21s | 2m20s |
| Espiral-de-geada | 6.8% | 5m26s | 5m20s |
| Lírio-de-Ilves | 1.5% | 22m43s | 22m31s |
| as três | — | 23m41s | 23m29s |

### Números atuais (game/config.py)

| estratégia | seed | Ti 500 | Árido | Úmido | Algas | Musgo | Verde | lab abre | bio desde | gargalo (Algas/Musgo/Verde) | Ti 100k | Folha/Espiral/Lírio | total | espera total | maior espera | desm. | drill un. | drone un. | déficit | tanque | saque | magmat. | aquec. | cratera | portão 1 | portão 2 | portão 3 | grande | L1 | L2 | L3 | máquinas (o2/melter/heater/o2_t2/melter_t2/heater_t2/drill/smelter/water_capsule/water_capsule_empty/solar/chest_small/chest/chest_large/drone_station/drone/lamp/lamp_t2/o2_tank/scanner/backpack/hand_drill/iron_ingot/silicon_wafer/circuit/chip/wire/copper_ingot/constructor/workbench/diagram_workbench/diagram_chest_large/hand_drill_t2/base_floor/base_wall/base_door/base_door2/o2_dispenser/water_collector/algae/plant_1/plant_2/plant_3/cultivator/sample_basic/sample_mutant/sample_rare/microscope/centrifuge/prop_table/prop_chair/prop_crate/prop_sign/prop_barrel/prop_bunk/prop_locker/prop_sample_shelf/prop_dead_plant/prop_lab_bench/prop_microscope/prop_console/prop_wall_desk_a/prop_wall_desk_b/wall_monitor_on/wall_monitor_off/wall_bp_plan/wall_bp_ship/wall_bp_ice/wall_notice/prop_container_stack/prop_command_table/prop_o2_cylinders/prop_server_rack/prop_server_rack_open/prop_workstation/prop_pilot_chair/wall_cable_panel/prop_wall_bunk/prop_suit_locker/prop_suit_niche/prop_briefing_table/prop_mess_table/prop_repair_bench/prop_nav_table/prop_side_table/fiber/hydrogel/frost_resin/lily_essence/backpack_t2/o2_tank_t2/boots/fertilizer/drone_t2/lamp_bio) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guloso | 1 | 1m48s | 6m37s | 8m08s | 25m33s | 36m04s | 56m27s | 19m57s | 20m00s | bio/bio/bio | 27m13s | 27m54s/30m59s/48m16s | 56m27s | 28m35s | 28m35s | 0 | 58 | 600 | 45m22s | — | 0 | 7m27s | 16m27s | 17m07s | 19m09s | 20m14s | 22m36s | 23m46s | 28m49s | 32m17s | 38m27s | 11/1/0/0/1/5/3/0/0/0/9/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| guloso | 2 | 1m48s | 6m30s | 8m01s | 24m32s | 35m02s | 55m26s | 18m56s | 18m59s | bio/bio/bio | 26m52s | 26m53s/29m58s/47m15s | 55m26s | 28m48s | 28m48s | 0 | 81 | 530 | 44m17s | — | 0 | 8m01s | 15m37s | 16m17s | 18m08s | 19m12s | 21m49s | 23m11s | — | — | — | 13/0/0/0/0/5/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| guloso | 3 | 1m42s | 6m37s | 8m08s | 27m45s | 38m15s | 58m39s | 22m07s | 22m11s | bio/bio/bio | 33m52s | 30m06s/33m11s/50m28s | 58m39s | 26m43s | 26m27s | 0 | 153 | 550 | 19m06s | — | 0 | 7m11s | 17m35s | 18m18s | 20m30s | 22m44s | 28m46s | 32m52s | 26m17s | 30m05s | 35m52s | 12/2/0/0/1/1/3/0/0/0/6/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| variado | 1 | 2m00s | 7m53s | 9m34s | 22m25s | 32m57s | 53m20s | 16m48s | 16m52s | bio/bio/bio | 32m17s | 24m48s/27m53s/45m10s | 53m20s | 21m23s | 21m23s | 0 | 137 | 401 | 32m13s | — | 0 | 3m04s | 3m26s | 7m02s | 12m50s | 18m08s | 29m07s | 31m56s | 9m34s | 15m43s | 25m47s | 4/6/4/2/2/1/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| variado | 2 | 2m01s | 7m51s | 9m31s | 22m23s | 32m57s | 53m20s | 16m46s | 16m50s | bio/bio/bio | 37m48s | 24m48s/27m53s/45m10s | 53m20s | 17m30s | 17m30s | 0 | 157 | 410 | 30m07s | — | 0 | 3m03s | 3m25s | 6m58s | 12m49s | 18m05s | 33m09s | 43m00s | 9m31s | 15m40s | 29m35s | 4/8/3/1/1/0/3/0/0/0/6/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| variado | 3 | 1m51s | 7m55s | 9m37s | 22m28s | 33m02s | 53m26s | 16m51s | 16m55s | bio/bio/bio | 34m28s | 24m53s/27m59s/45m16s | 53m26s | 19m33s | 19m33s | 0 | 141 | 432 | 14m44s | — | 0 | 3m05s | 3m27s | 7m09s | 12m53s | 18m15s | 31m12s | 37m08s | 9m39s | 15m42s | 26m00s | 4/7/5/1/2/0/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| casual | 1 | 2m21s | 8m59s | 10m49s | 27m56s | 38m28s | 58m51s | 22m17s | 22m23s | bio/bio/bio | 37m09s | 30m19s/33m24s/50m41s | 58m51s | 22m12s | 22m12s | 0 | 123 | 510 | 10m58s | — | 0 | 4m05s | 4m35s | 8m32s | 16m04s | 24m18s | 31m08s | 34m17s | 10m49s | 16m59s | 29m45s | 5/5/2/2/2/1/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| casual | 2 | 2m20s | 9m00s | 10m45s | 27m43s | 38m14s | 58m37s | 22m04s | 22m10s | bio/bio/bio | 35m05s | 30m04s/33m10s/50m27s | 58m37s | 23m56s | 23m56s | 0 | 97 | 510 | 35m22s | — | 0 | 4m08s | 4m40s | 8m23s | 15m54s | 24m02s | 29m02s | 31m57s | 10m45s | 16m59s | 29m27s | 5/5/2/2/1/2/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| casual | 3 | 2m13s | 8m52s | 10m40s | 27m57s | 38m30s | 58m54s | 22m17s | 22m23s | bio/bio/bio | 36m33s | 30m21s/33m26s/50m44s | 58m54s | 23m51s | 23m51s | 0 | 145 | 480 | 14m42s | — | 0 | 4m01s | 4m30s | 8m36s | 16m11s | 24m19s | 42m07s | 51m37s | 10m40s | 16m45s | 30m15s | 6/5/3/2/1/0/3/0/0/0/7/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| caverna | 1 | 2m42s | 10m24s | 12m42s | 30m58s | 41m29s | 1h01m | 25m18s | 25m24s | bio/bio/bio | 33m52s | 33m20s/36m25s/53m42s | 1h01m | 27m50s | 27m50s | 0 | 151 | 0 | 13m07s | — | 0 | 4m58s | 7m06s | 11m32s | 19m18s | 25m50s | 30m41s | 33m48s | 12m47s | 21m54s | 27m10s | 4/3/2/3/1/1/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| caverna | 2 | 2m34s | 10m05s | 12m18s | 30m36s | 41m10s | 1h01m | 24m56s | 25m02s | bio/bio/bio | 35m46s | 33m01s/36m07s/53m24s | 1h01m | 30m02s | 30m02s | 0 | 117 | 0 | 37m49s | — | 0 | 5m28s | 6m52s | 10m59s | 18m50s | 25m37s | 30m14s | 33m06s | 12m43s | 20m46s | 25m54s | 5/3/3/1/1/1/3/0/0/0/6/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| caverna | 3 | 2m34s | 9m29s | 11m38s | 29m28s | 39m59s | 1h00m | 23m48s | 23m54s | bio/bio/bio | 34m16s | 31m50s/34m55s/52m12s | 1h00m | 25m09s | 25m09s | 0 | 157 | 0 | 16m32s | — | 0 | 4m22s | 5m41s | 9m56s | 17m29s | 26m01s | 31m04s | 34m18s | 11m52s | 22m26s | 28m09s | 6/4/2/2/1/1/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| destrocos | 1 | 2m55s | 10m30s | 12m43s | 30m37s | 41m08s | 1h01m | 24m58s | 25m04s | bio/bio/bio | 36m08s | 32m59s/36m04s/53m21s | 1h01m | 25m44s | 25m44s | 0 | 140 | 0 | 36m51s | 0m29s | 36 | 5m01s | 6m25s | 10m51s | 18m48s | 26m09s | 30m43s | 33m52s | 12m47s | 20m05s | 25m10s | 4/4/4/1/2/1/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| destrocos | 2 | 2m52s | 10m07s | 12m24s | 30m35s | 41m05s | 1h01m | 24m55s | 25m01s | bio/bio/bio | 35m00s | 32m56s/36m01s/53m18s | 1h01m | 26m01s | 26m01s | 0 | 144 | 0 | 14m48s | 0m29s | 36 | 4m31s | 6m47s | 11m05s | 18m47s | 27m05s | 31m52s | 34m45s | 12m24s | 21m55s | 27m10s | 6/3/4/1/1/1/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| destrocos | 3 | 2m51s | 9m47s | 11m55s | 29m32s | 40m03s | 1h00m | 23m53s | 23m59s | bio/bio/bio | 34m52s | 31m53s/34m59s/52m16s | 1h00m | 26m05s | 26m05s | 0 | 157 | 0 | 10m22s | 0m29s | 36 | 4m14s | 5m39s | 10m02s | 17m53s | 24m56s | 29m32s | 32m21s | 12m03s | 19m29s | 24m34s | 8/3/3/1/1/1/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |

### Proposta (balance_proposal.json)

| estratégia | seed | Ti 500 | Árido | Úmido | Algas | Musgo | Verde | lab abre | bio desde | gargalo (Algas/Musgo/Verde) | Ti 100k | Folha/Espiral/Lírio | total | espera total | maior espera | desm. | drill un. | drone un. | déficit | tanque | saque | magmat. | aquec. | cratera | portão 1 | portão 2 | portão 3 | grande | L1 | L2 | L3 | máquinas (o2/melter/heater/o2_t2/melter_t2/heater_t2/drill/smelter/water_capsule/water_capsule_empty/solar/chest_small/chest/chest_large/drone_station/drone/lamp/lamp_t2/o2_tank/scanner/backpack/hand_drill/iron_ingot/silicon_wafer/circuit/chip/wire/copper_ingot/constructor/workbench/diagram_workbench/diagram_chest_large/hand_drill_t2/base_floor/base_wall/base_door/base_door2/o2_dispenser/water_collector/algae/plant_1/plant_2/plant_3/cultivator/sample_basic/sample_mutant/sample_rare/microscope/centrifuge/prop_table/prop_chair/prop_crate/prop_sign/prop_barrel/prop_bunk/prop_locker/prop_sample_shelf/prop_dead_plant/prop_lab_bench/prop_microscope/prop_console/prop_wall_desk_a/prop_wall_desk_b/wall_monitor_on/wall_monitor_off/wall_bp_plan/wall_bp_ship/wall_bp_ice/wall_notice/prop_container_stack/prop_command_table/prop_o2_cylinders/prop_server_rack/prop_server_rack_open/prop_workstation/prop_pilot_chair/wall_cable_panel/prop_wall_bunk/prop_suit_locker/prop_suit_niche/prop_briefing_table/prop_mess_table/prop_repair_bench/prop_nav_table/prop_side_table/fiber/hydrogel/frost_resin/lily_essence/backpack_t2/o2_tank_t2/boots/fertilizer/drone_t2/lamp_bio) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| guloso | 1 | 2m19s | 8m50s | 10m46s | 20m32s | 31m04s | 51m13s | 12m26s | 12m29s | Ti/Ti/bio | 45m29s | 22m55s/26m00s/43m17s | 51m13s | 11m50s | 6m53s | 0 | 160 | 352 | 37m52s | — | 0 | 9m22s | 2m30s | 5m35s | 9m42s | 13m22s | 23m46s | 30m21s | 26m00s | 30m59s | 37m54s | 4/7/7/0/1/0/3/0/0/0/7/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| guloso | 2 | 2m22s | 8m55s | 10m51s | 18m58s | 29m17s | 49m49s | 12m31s | 12m34s | Ti/bio/bio | 29m40s | 21m21s/24m26s/41m43s | 49m49s | 20m38s | 20m18s | 0 | 53 | 440 | 41m35s | — | 0 | 16m02s | 2m40s | 5m45s | 9m46s | 13m27s | 19m36s | 21m23s | 32m26s | 37m36s | 46m51s | 4/0/6/0/1/6/3/0/0/0/10/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| guloso | 3 | 2m19s | 8m44s | 10m34s | 19m03s | 29m12s | 49m49s | 11m55s | 11m58s | Ti/bio/bio | 40m53s | 21m25s/24m31s/41m48s | 49m49s | 10m49s | 10m40s | 0 | 182 | 340 | 24m41s | — | 0 | — | 2m49s | 5m39s | 9m30s | 12m45s | 21m00s | 25m34s | 34m58s | 39m05s | 45m34s | 4/3/7/0/1/1/3/0/0/0/7/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| variado | 1 | 2m30s | 8m57s | 10m51s | 26m09s | 36m40s | 57m03s | 20m32s | 20m36s | bio/bio/bio | 32m30s | 28m30s/31m35s/48m52s | 57m03s | 24m48s | 24m48s | 0 | 87 | 490 | 44m57s | — | 0 | 23m16s | 3m21s | 7m34s | 14m49s | 21m57s | 27m21s | 29m28s | 10m51s | 19m13s | 25m14s | 7/5/3/2/2/2/3/0/0/0/9/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| variado | 2 | 2m26s | 9m02s | 10m52s | 26m02s | 36m36s | 57m00s | 20m25s | 20m29s | bio/bio/bio | 35m13s | 28m28s/31m33s/48m50s | 57m00s | 23m19s | 23m19s | 0 | 139 | 440 | 39m27s | — | 0 | — | 3m23s | 7m37s | 14m43s | 22m09s | 28m13s | 30m57s | 10m53s | 15m09s | 26m36s | 5/9/3/1/1/2/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| variado | 3 | 2m24s | 9m05s | 10m58s | 26m13s | 36m44s | 57m07s | 20m36s | 20m40s | bio/bio/bio | 33m24s | 28m35s/31m40s/48m57s | 57m07s | 23m00s | 23m00s | 0 | 92 | 510 | 41m07s | — | 0 | 20m46s | 3m34s | 7m47s | 14m51s | 21m45s | 27m10s | 29m25s | 11m01s | 15m13s | 25m52s | 6/7/3/2/2/2/3/0/0/0/10/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| casual | 1 | 2m46s | 10m10s | 12m16s | 27m39s | 38m10s | 58m33s | 22m00s | 22m06s | bio/bio/bio | 40m11s | 30m01s/33m06s/50m23s | 58m33s | 20m16s | 20m16s | 0 | 133 | 470 | 13m44s | — | 0 | — | 4m26s | 9m04s | 16m42s | 23m49s | 35m29s | 39m07s | 12m18s | 17m10s | 30m09s | 4/7/3/2/1/1/3/0/0/0/8/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| casual | 2 | 2m47s | 10m15s | 12m24s | 27m50s | 38m22s | 58m46s | 22m11s | 22m17s | bio/bio/bio | 45m02s | 30m13s/33m18s/50m35s | 58m46s | 16m00s | 14m00s | 0 | 179 | 412 | 17m55s | — | 0 | — | 4m20s | 9m13s | 16m53s | 24m04s | 43m50s | 56m31s | 12m27s | 17m20s | 31m00s | 4/10/3/1/1/0/3/0/0/0/7/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| casual | 3 | 2m46s | 10m13s | 12m19s | 27m39s | 38m11s | 58m34s | 22m00s | 22m06s | bio/bio/bio | 45m04s | 30m02s/33m07s/50m24s | 58m34s | 21m33s | 15m33s | 0 | 146 | 431 | 29m46s | — | 0 | — | 4m31s | 9m09s | 16m41s | 23m45s | 43m32s | 57m22s | 12m19s | 17m13s | 30m51s | 5/8/3/1/1/0/3/0/0/0/6/1/0/0/1/2/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| caverna | 1 | 3m27s | 11m40s | 13m53s | 30m20s | 40m54s | 1h01m | 24m41s | 24m47s | bio/bio/bio | 39m46s | 32m46s/35m51s/53m08s | 1h01m | 20m51s | 20m51s | 0 | 205 | 0 | 14m56s | — | 0 | — | 5m40s | 10m51s | 20m55s | 25m16s | 31m28s | 35m12s | 13m54s | 22m25s | 33m37s | 6/5/3/1/1/2/3/0/0/0/8/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| caverna | 2 | 3m22s | 11m50s | 14m02s | 30m15s | 40m47s | 1h01m | 24m36s | 24m42s | bio/bio/bio | 39m28s | 32m37s/35m43s/53m00s | 1h01m | 24m07s | 24m07s | 0 | 140 | 0 | 37m36s | — | 0 | — | 5m59s | 11m14s | 21m18s | 25m15s | 31m28s | 34m50s | 14m02s | 22m27s | 33m58s | 5/5/2/1/1/2/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| caverna | 3 | 3m23s | 11m42s | 13m56s | 29m55s | 40m28s | 1h00m | 24m16s | 24m22s | bio/bio/bio | 40m18s | 32m20s/35m25s/52m42s | 1h00m | 21m23s | 21m23s | 0 | 173 | 0 | 38m39s | — | 0 | — | 6m07s | 11m00s | 21m03s | 24m50s | 31m09s | 34m52s | 13m56s | 22m32s | 33m35s | 6/6/4/1/1/1/3/0/0/0/7/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| destrocos | 1 | 3m32s | 12m02s | 14m15s | 29m53s | 40m24s | 1h00m | 24m13s | 24m19s | bio/bio/bio | 37m54s | 32m14s/35m19s/52m37s | 1h00m | 23m00s | 23m00s | 0 | 175 | 0 | 36m30s | 0m29s | 36 | — | 6m58s | 11m34s | 21m39s | 24m48s | 30m51s | 33m23s | 14m16s | 22m42s | 32m19s | 5/5/3/2/1/2/3/0/0/0/8/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| destrocos | 2 | 3m29s | 11m51s | 14m00s | 29m59s | 40m30s | 1h00m | 24m20s | 24m26s | bio/bio/bio | 38m10s | 32m21s/35m26s/52m43s | 1h00m | 22m41s | 22m41s | 0 | 182 | 0 | 38m50s | 0m29s | 36 | — | 6m32s | 11m23s | 18m57s | 26m11s | 33m32s | 37m08s | 14m00s | 22m12s | 30m21s | 6/4/4/2/2/1/3/0/0/0/8/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
| destrocos | 3 | 3m47s | 11m58s | 14m11s | 29m58s | 40m29s | 1h00m | 24m19s | 24m25s | bio/bio/bio | 38m28s | 32m20s/35m25s/52m42s | 1h00m | 22m56s | 22m56s | 0 | 183 | 0 | 37m23s | 0m29s | 36 | — | 5m57s | 11m12s | 21m14s | 24m55s | 30m54s | 34m06s | 14m11s | 22m39s | 33m36s | 5/4/3/2/1/2/3/0/0/0/8/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0/0 |
