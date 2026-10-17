# v0.8 M6 Task 1: Objetivos novos e a dica do coletor

## O que mudou por arquivo
- `game/config.py`: `MILESTONES` (6 marcos), logo antes de `WRECK_VISIT_DIST`.
- `game/systems.py`:
  - `GameState.milestones: set[str]` e `mark(name)` (assert em `C.MILESTONES`, idempotente).
  - 6 ganchos:
    - `lab_found`: em `_update_explore`, só na superfície, a `WRECK_VISIT_DIST` tiles da porta (`ruins.lab_door_px`). Sem lab, não marca.
    - `control_culture`: em `crate_take`, `algae` com `got > 0` e `getattr(crate.wreck, "key", None) == "lab"`.
    - `cultivator_in_base`: início de `_update_cultivator`, com `in_breathing_base`, com ou sem muda.
    - `first_harvest`: em `_cultivator_harvest`, se `n - left > 0`.
    - `first_sample`: junto do evento `sample_found`.
    - `first_plant`: junto do `centrifuge_done` com planta. A falha não marca.
- `game/save.py`: grava `"milestones": sorted(...)`. No load filtra por `C.MILESTONES`, e sem o campo vem vazio. `SAVE_VERSION` continua 17.
- `game/objectives.py`: `COLLECTOR_HINT`, os helpers `_mats`, `_plant_fallback` e `_lab_ice_open`, e os 10 objetivos novos antes do "Deixe o planeta verde". Com o Verde são 11 depois de "Construa uma máquina nv.2". Condições `marco or fallback` como na tabela do plano. O 6 ("Colha a primeira alga") leva `hint=COLLECTOR_HINT`.
- `tests/test_m6_objectives_v08.py` (novo, 15 testes): ordem, wrap nos 3 tamanhos, cada gancho (a falha da centrífuga não marca, amostra vazia não marca, alga de caixa que não é a do lab não marca, Cultivador fora da base não marca), save velho no Verde que não trava, Algas sem o diagrama do microscópio cai em "Escaneie", dica uma vez só, round-trip do save e monotonia (tirar o Dispersor não descumpre).
- `tests/test_objectives.py`: `test_normal_sequence_walks_every_objective` ganhou os 10 passos novos, e `test_everything_done_list_disappears` ganhou os blueprints e o `crafted` (fibra, hidrogel, cultivador) pra quem já passou.

## Testes rodados
- `uv run pytest tests/test_m6_objectives_v08.py`: `15 passed in 1.84s`
- `uv run pytest tests/test_objectives.py tests/test_m6_objectives_v08.py tests/test_save.py tests/test_cultivator_v08.py tests/test_microscope_v08.py tests/test_centrifuge_v08.py tests/test_lab_v08.py tests/test_m4_save_v08.py`: `224 passed in 14.59s`
- Não rodei o pytest inteiro nem o smoke, como mandado.

## Textos encurtados
- "Escaneie o microscópio e o tanque do laboratório" passou a ser **"Escaneie o microscópio e o tanque"**. Com o texto original o cartão de 132 px quebrava em 4 linhas no 480×270. Agora todos os novos ficam em no máximo 3 linhas nos 3 tamanhos (o teste confere isso e a largura). "do laboratório" está implícito, porque o objetivo anterior já é o lab.

## Diferente do plano
- O texto encurtado acima.
- O gancho `cultivator_in_base` chama `in_breathing_base` direto em vez de olhar o `cultivator_blocker`, porque o blocker devolve `"no_seed"` antes de checar a base e não distinguiria "sem muda, dentro da base" de "sem muda, fora".
- O `crafted` usa os nomes reais (`C.FIBER`, `C.HYDROGEL`, `C.FROST_RESIN`, `C.LILY_ESSENCE`, `C.FERTILIZER`, `C.CULTIVATOR`), e todos estão em `C.MACHINES`. Não precisei de sinal alternativo.

## Riscos
- Os objetivos 1 a 4 não têm fallback de estágio (seguem a tabela). Um estado no Verde/Algas **sem** os blueprints e **sem** cultivador fabricado (só dá com debug F7 ou save montado à mão) fica preso em "Ache o laboratório" ou "Pegue a cultura-controle". Se o dono quiser, é só somar `stage >= ALGAE_STAGE` nesses.
- Quem estava entre o fim do "nv.2" e o Algas num save antigo, sem os marcos, cai nos fallbacks (blueprints e `crafted`). O "Derreta o gelo do laboratório" depende de `surface.lab_ice_open`, que já vai no save.
- `lab_found` só marca com o player na superfície e dentro do `explore_timer` (a cada `EXPLORE_INTERVAL`), igual aos destroços.
