# v0.4 Marco 3 · Gelo e água · Plano de implementação

> **Pra agentes:** **um Dev por vez** (pedido do dono, pra economizar crédito). Cada etapa (M3.1 … M3.4) roda num worktree isolado e **para no fim**: o gerente revisa, faz o merge, mostra os prints pro dono e só solta a próxima com o "segue" dele. Os passos usam checkbox (`- [ ]`).

**Objetivo:** o calor e a água passam a mudar o mapa. A tampa de gelo da cratera derrete no começo do jogo e libera a caverna. Os gelos-portão abrem mais tarde e revelam um destroço melhor e o contêiner lacrado. Na Névoa chove e as bacias enchem das partes mais fundas pra fora. A máquina que fica debaixo d'água para de funcionar.

**Spec:** `docs/superpowers/specs/2026-10-13-v04-mundo-vivo-design.md` (§ Marco 3). **Bíblia:** §11 (geo, bacias, bolsões, cratera, F4). **Arte:** `assets/sprites/regions/` (`crater_impact_0..4`, `ice_gate_0..2`, `frost_ring`, `regions_palettes.json` com as pegadas `ice_gate_0..2` e os níveis `levels`).

**Stack:** Python 3.13, pygame-ce, numpy, pytest.

## Restrições globais
- Não commitar e não abrir janela visível.
- Têm que passar: `uv run pytest`, `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py`.
- Formato de surface explícito (`game/surfaces.py`, `tests/test_surface_format.py`).
- Desempenho: o smoke fica no orçamento de 16,7 ms. A chuva cobre a tela toda, então meça (meta: até +1 ms de média).
- Determinístico pela seed e pelos índices.
- A caverna **não muda** (`world.terraforms = False`: sem água, sem chuva).
- **Números são de partida** e ficam no `game/config.py`, num bloco `THAW_*` / `LAKE_*` / `RAIN_*`. O balanceamento é feito numa rodada só, no Marco 4: não pare pra discutir número com o dono.
- **Save continua v7.** Tudo o que este marco muda no mapa sai de uma **função pura dos índices** (que já vão no save e nunca descem). No load, é só reaplicar. O único campo salvo continua sendo o `crater_ice`, por causa do F4.
- Cada etapa escreve a sua parte na bíblia, numa seção "§12 v0.4 · Marco 3", no mesmo estilo da §11.
- Arte ou som novo **não entra sem o ok do dono.** Enquanto não chega, use fallback: desenho por código ou silêncio, carregado com `sprites.get(...)` / sem o wav.

## Ordem dos objetivos (decidida pelo dono)
O objetivo "Derreta o gelo da cratera" hoje vem **antes** de "Fabrique um Aquecedor", mas calor só sai do aquecedor (que libera em Ti 500). **Fechado:** mover o bloco **"Minere gelo e fabrique um Derretedor" → "Chegue a Ti 500" → "Fabrique um Aquecedor"** pra logo depois de "Fabrique um baú", e só então vir "Derreta o gelo da cratera" → "Desça na caverna". O destroço e o tanque de O₂ continuam depois da caverna.

## Interfaces combinadas

```python
# game/thaw.py (novo, M3.1; cresce no M3.2 e no M3.3). Funções puras, sem pygame, testáveis sozinhas.
def crater_stage(heat: float) -> int            # 0..C.CRATER_ICE_STAGES, pelos marcos C.THAW_CRATER_HEAT (4 valores crescentes)
def gate_stage(heat: float, i: int) -> int      # M3.2: 0..3 (3 = aberto) pro portão i, pelos marcos C.THAW_GATE_HEAT[i] (3 valores)
def lake_level(water: float) -> float           # M3.3: altura (escala do geo.height) até onde a água sobe; -1.0 = seco
                                                #   0 abaixo de C.LAKE_WATER[0]; interpola C.GEO_LEVELS L1→L2→L3 entre C.LAKE_WATER[0..2]

# GameState (game/systems.py)
state._apply_thaw() -> None                     # chamado no _update_machines (depois de somar os índices) e no load.
                                                #   Sobe crater_ice/gate stages/lake (nunca desce) e solta os eventos abaixo.
# eventos novos em state.events:
("crater_thaw", etapa)      # M3.1: a tampa baixou uma etapa (4 = aberta)
("gate_thaw", i, etapa)     # M3.2
("lake_rise", nivel)        # M3.3: passou de L1/L2/L3 (0..2)
("submerged", kind, (tx, ty))   # M3.4

# Layer da superfície (game/layers.py)
layer.gate_ice: list[int]   # M3.2: etapa de cada portão (índice = geo.pockets[i]), derivada, NÃO vai no save
layer.water_level: float    # M3.3: lake_level(water) atual, derivado, NÃO vai no save

# World (game/world.py, M3.3): com world.geo, is_water(tx, ty, stage) passa a ser
#   geo.height[ty, tx] < world.water_level e tile de chão (o `stage` é ignorado nesse caminho).
#   Sem geo (testes antigos), continua o caminho do lowness.
```

---

## M3.0 · Elementos novos das regiões, v9 (Dev, 1 etapa curta)
Arte **aprovada pelo dono** (v9, `reports/design/regioes/index.html#v9`), já promovida pra `assets/sprites/regions/` pela Designer. A seção "Pro Dev integrar (v9)" do report tem a receita.
**Arquivos:** `game/ground.py` (decalques), `game/hills.py` / `game/render.py` (soltos e musgo), `game/geo.py` (formações pequenas), `game/config.py`, testes, smoke, bíblia §11.

- [ ] **1. Testes primeiro:** determinismo pela seed. Formação pequena só na sua região, fora de bacia, longe da base e com a pegada virando `FORMATION`. Solto novo nunca no tile de um solto da v8, de máquina, veio, destroço ou rocha. Musgo só no Verde.
- [ ] **2. Decalques v9:** um 3º sorteio por célula de 96 px (hash próprio), com a chance e os pesos por região do JSON. Fica na camada do chão assado, então entra na assinatura do bloco.
- [ ] **3. Soltos v9:** mesmo caminho dos soltos de hoje (pé, ordem pelo pé, espelho), com a chance por tile do JSON. O overlay de musgo é desenhado logo depois da pedra, só no estágio Verde.
- [ ] **4. Formações pequenas** (`split_rock`, `salt_pillar`, `lava_tube`, `ice_needles`) no `geo.formations`, pelo caminho do `FormationSprites`. Nenhuma no leito seco.
- [ ] **5.** Meça o custo no smoke (a meta é ≤ +0,5 ms), mais pytest, smoke e real_video, prints das 4 regiões no Árido e no Verde, e a bíblia §11. **Pare aqui.**

## M3.1 · A cratera derrete com o calor (Dev, 1 etapa)
**Arquivos:** `game/thaw.py` (novo), `game/config.py`, `game/systems.py`, `game/objectives.py`, `game/app.py` (aviso e som), `game/save.py` (só reaplicar no load), `tests/test_thaw.py` (novo), `tools/dev/smoke.py`, `tools/dev/balance_sim.py`, bíblia §12.

- [ ] **1. Teste primeiro** (`tests/test_thaw.py`):
  ```python
  def test_crater_stage_steps_with_heat():
      marks = C.THAW_CRATER_HEAT
      assert thaw.crater_stage(0) == 0
      assert thaw.crater_stage(marks[0]) == 1
      assert thaw.crater_stage(marks[-1]) == C.CRATER_ICE_STAGES
      assert thaw.crater_stage(marks[-1] * 10) == C.CRATER_ICE_STAGES

  def test_state_melts_crater_and_emits_events(new_state):
      new_state.indices["heat"] = C.THAW_CRATER_HEAT[1]
      new_state._apply_thaw()
      assert new_state.surface.crater_ice == 2
      assert ("crater_thaw", 2) in new_state.events

  def test_thaw_never_goes_back_and_respects_f4(new_state):
      new_state.debug_melt_crater()
      new_state._apply_thaw()           # calor 0 não fecha de novo
      assert new_state.surface.crater_ice == C.CRATER_ICE_STAGES
  ```
  Rode e confirme que falha (`ModuleNotFoundError: game.thaw`).
- [ ] **2.** `C.THAW_CRATER_HEAT = (40, 90, 150, 220)` (pK, ~1 min de um aquecedor). Crie `thaw.crater_stage` com `bisect`. Em `GameState`, `_apply_thaw()` faz `surface.crater_ice = max(surface.crater_ice, crater_stage(heat))` e solta um `("crater_thaw", etapa)` por etapa que subiu. Chame no fim do `_update_machines` e depois do load (`save.load` → `state._apply_thaw()` sem eventos, ou limpe os eventos depois).
- [ ] **3.** Na etapa 4, o `ramp_blocked` já libera sozinho e o `crater_open` completa (conferir com teste). O F4 continua como está.
- [ ] **4.** No `app.py`: no `crater_thaw`, um aviso no estilo do "RAJADA", só que neutro: "O gelo da cratera está cedendo" nas etapas 1–3 e "A cratera abriu · desça [E]" na 4. Som `ice_crack` (vazio enquanto o Som não entregar; sem wav = silêncio).
- [ ] **5.** Nova ordem dos objetivos (ver "Ordem dos objetivos" acima e a bíblia §11). Ajuste os testes de objetivo que dependem da ordem.
- [ ] **5b. Fumarolas acordam com o calor** (ideia do dono; arte da Designer na v9.1, **só depois da aprovação**). As chaminés do basalto nascem com o mundo (formação pequena, dormente). `thaw.fumarole_active(heat, i) -> bool` acorda cada uma num marco de calor próprio (`C.THAW_FUMAROLE_HEAT`, espalhado entre o 1º marco da cratera e o último portão), e o evento `("fumarole_wake", i)` só sai se ela estiver na tela. Ativa: sprite ativo e **fumaça em partícula** (`game/smoke.py`, no padrão do `dust.py`), entortando com `state.weather` e com os números da Designer. Teste: a função é monótona e o load reconstrói o estado. Se a arte não estiver aprovada quando chegar aqui, este passo vira M3.1b.
- [ ] **6.** `balance_sim.py`: o casual tem que conseguir abrir a cratera. Registre em quanto tempo isso acontece, só pra informar (não é pra tunar).
- [ ] **7.** Smoke: um print da cratera em cada etapa (0, 2, 4) sem F4, setando `indices["heat"]`. `pytest`, smoke e real_video. Escreva a §12 "Derretimento da cratera". **Pare aqui.**

## M3.2 · Gelos-portão, destroço melhor e contêiner lacrado (Dev, 1 etapa)
**Arquivos:** `game/thaw.py`, `game/config.py`, `game/systems.py`, `game/layers.py`, `game/world.py` (trocar tile `FORMATION` → chão), `game/hills.py` (sprite pela etapa e `frost_ring` no aberto), `game/wrecks.py` (destroço "rico"), `game/surface_gen.py` (colocar destroço e contêiner nos `*_spot`), objeto novo do contêiner (no `wrecks.py` ou num `game/container.py` pequeno), `game/app.py`, `game/minimap.py`, `tests/test_thaw.py`, `tests/test_pockets.py` (novo), smoke, bíblia §12.

- [ ] **1. Testes primeiro:**
  - `gate_stage(heat, i)` sobe 0→1→2→3 nos marcos `C.THAW_GATE_HEAT[i]` (um trio por portão, o portão 0 abrindo primeiro);
  - com a etapa `s` (0..2), os tiles `FORMATION` do portão são exatamente a pegada de `ice_gate_s` do `regions_palettes.json` (âncora no mesmo `base_px`). Com 3, não sobra nenhum, os tiles viram chão e o interior fica alcançável a pé da base (reaproveite o BFS do teste de alcance do M2);
  - o anel `BEDROCK` continua inteiro (não dá pra contornar);
  - load com calor alto reconstrói portões abertos sem precisar de campo no save.
- [ ] **2.** `C.THAW_GATE_HEAT = ((1500, 2500, 3500), (3500, 5000, 6500), (6000, 8000, 10000))` (o terceiro só vale quando existem 3 bolsões). `layer.gate_ice` com uma entrada por bolsão. O `_apply_thaw` sobe as etapas, troca a pegada no `world` (`C.FORMATION` ↔ `C.SAND` ou o tile de chão da superfície) e solta `("gate_thaw", i, s)`.
- [ ] **3.** `hills.FormationSprites`: o portão usa `ice_gate_<etapa>` e, no aberto, nenhum sprite, só o `frost_ring.png` no chão (camada de decalque). A troca de pegada invalida os blocos de morro/chão que a enxergam (mesmo esquema da mineração).
- [ ] **4.** **Destroço melhor**: no `wreck_spot` de cada bolsão vai um destroço com a tabela de saque "rica" (tabela nova no `config.py`, ao lado da de hoje do `wrecks.py`: mais material e, se ainda faltar algum, um projeto de `C.BLUEPRINTS` que não caiu). Ele é gerado com a superfície (seed), mas fica atrás do portão.
- [ ] **5.** **Contêiner lacrado**: objeto sólido de 1 tile no `container_spot`, que não abre. O E mostra uma dica de lore curta ("Contêiner lacrado · selo da Colônia Hesper · o lacre não cede com a ferramenta que você tem"). O texto final passa pelo dono. Placeholder desenhado por código até o sprite da Designer ser aprovado. Vira marcador "Contêiner" no mapa quando visto.
- [ ] **6.** Aviso no `gate_thaw` 3: "Um gelo-portão abriu ao norte", com som `ice_crack` mais grave (ou o mesmo).
- [ ] **7.** Smoke: prints de um portão nas etapas 0, 2 e aberto, mais o interior com o destroço e o contêiner. `pytest`, smoke e real_video. Escreva a §12 "Gelos-portão". **Pare aqui.**

## M3.3 · Chuva e lagos nas bacias (Dev, 1 etapa; a maior)
**Arquivos:** `game/thaw.py`, `game/config.py`, `game/world.py` (`is_water` pelo geo, `plant_at`), `game/systems.py`, `game/layers.py`, `game/render.py` (memo da água invalidado quando o nível muda), `game/rain.py` (novo: chuva), `game/weather.py` (pancadas na Névoa), `game/audio.py`/`app.py` (som da chuva), `game/rock_respawn.py`, `game/minimap.py`/`map_view.py` (água no mapa), `tests/test_lakes.py` (novo), `tests/test_rain.py` (novo), smoke, bíblia §12.

- [ ] **1. Testes primeiro** (`tests/test_lakes.py`):
  - `lake_level(0) < 0` (seco). Em `C.LAKE_WATER[k]`, `lake_level == C.GEO_LEVELS[k]`, e é monótona;
  - com nível em L1, só tiles com `geo.basin == 0` alagam, e o salar alaga antes do planalto (é o mais fundo);
  - a água sempre começa pelos tiles mais baixos: todo tile molhado tem `height` menor que todo tile seco da mesma bacia;
  - **nada aleatório**: com geo, nenhum tile fora de bacia vira água, em nenhum estágio (sai o `lowness` na superfície);
  - a crosta de sal (`salt_ridge`) continua `FORMATION` e vira ilhota (água em volta, ela não);
  - a base (raio 16) nunca alaga.
- [ ] **2.** `C.LAKE_WATER = (3000, 15000, 40000)` (ppm; antes disso, seco. A água só sobe a partir da Névoa, porque antes o índice não chega lá). `lake_level` interpola entre um pouco abaixo do fundo e L1, e depois L1→L2→L3. `layer.water_level` é derivado no `_apply_thaw`, que solta `("lake_rise", k)` ao cruzar cada nível.
- [ ] **3.** `World.is_water`: com `self.geo`, a água é `geo.height[ty, tx] < self.water_level` e tile de chão. A suavização antiga (gota sozinha) **não** se aplica, porque o relevo já é suave. O resto do jogo (render autotile, rochas que reaparecem, plantas) continua usando `is_water`. Onde hoje se usa `is_water(..., C.GREEN_STAGE)` como "lago futuro", com geo isso vira `geo.basin_at(tx, ty) >= 0`.
- [ ] **4.** Render: o `_wet_memo` é limpo quando o `water_level` muda (no máximo umas poucas vezes por minuto). A água continua sendo o autotile A2 de hoje, por cima do chão assado. Se a Designer entregar a água por estágio aprovada, troca o atlas.
- [ ] **5.** **Plantas na beira d'água** (Verde): `plant_at` usa a chance `C.PLANT_CHANCE_SHORE` (ex. 0,30) a até 3 tiles da água/bacia e `C.PLANT_CHANCE` reduzida (ex. 0,05) longe dela.
- [ ] **6.** **Chuva** (`game/rain.py`): pancadas determinísticas pela seed (como as rajadas do `weather.py`): na Névoa, 30–60 s de chuva a cada 60–120 s. No Verde, mais curtas. Intensidade 0..1 com subida e descida de 2 s. Efeito na tela: traços diagonais (ângulo do vento do `weather`) em grade presa à câmera, com no máximo ~300 traços, reaproveitando o padrão de partícula do `dust.py`. Só na superfície. O som `amb_rain` entra em loop com volume = intensidade (silêncio até o Som entregar).
- [ ] **7.** Smoke: prints das bacias em L1, L2 e L3 (salar e uma depressão do planalto), da chuva na Névoa e das plantas na margem no Verde. Meça o custo da chuva. `pytest`, smoke e real_video. Escreva a §12 "Chuva e lagos". **Pare aqui.**

## M3.4 · Máquina submersa e água como obstáculo de construção (Dev, 1 etapa)
**Arquivos:** `game/systems.py` (`can_place`, `_update_machines`, `_apply_thaw`), `game/render.py` (máquina submersa), `game/app.py` (aviso), `game/ui.py` (tooltip "Submersa"), `tests/test_submerged.py` (novo), smoke, bíblia §12.

- [ ] **1. Testes primeiro:**
  - `can_place` devolve False em tile com `world.is_water(...)`;
  - máquina num tile que alagou: `m.submerged` é True, não soma índice nem gasta/gera energia (o painel solar também para), e a drill para de produzir;
  - `dismantle` funciona normal numa máquina submersa (volta pro inventário);
  - o evento `("submerged", kind, tile)` sai uma vez só por máquina;
  - drone que levaria carga pra uma estação submersa não leva (a estação parou).
- [ ] **2.** `Machine.submerged` é derivado (não vai no save): ao subir o nível, `_apply_thaw` marca as máquinas da superfície que caíram na água.
- [ ] **3.** Render: a máquina submersa é desenhada só da metade pra cima, com a linha d'água por cima, e sem a luz ou animação de "ligada". Aviso "Gerador de O₂ submerso · recolha [clique direito]" (use o verbo de desmontar que o jogo já usa).
- [ ] **4.** O player continua andando na água rasa (como hoje). Isso fica pra rever no playtest do Marco 4.
- [ ] **5.** Smoke: print de uma máquina submersa e o fantasma vermelho de colocar na água. `pytest`, smoke e real_video. Escreva a §12 "Máquina submersa". **Pare aqui.**

## Assets do Marco 3 (Designer/Som, pra aprovar com o dono)
| Quem | Asset | Entra em |
|---|---|---|
| Som | `ice_crack.wav` (2 variações: estalo e desabamento) | M3.1, M3.2 |
| Designer | sprite do contêiner lacrado (1 tile, recolorível, sem cara de "tesouro") | M3.2 |
| Som | `amb_rain.wav` (loop, 2 intensidades) | M3.3 |
| Designer | atlas de água por região/estágio (`water_auto_<stage>`) se o A2 de hoje destoar do chão assado; brilho de margem | M3.3 |
| Designer | gota/respingo da chuva no chão (opcional) | M3.3 |

## Depois do Marco 3
Marco 4: polimento, playtest do dono, re-skin das máquinas com o motor 3D experimental (`r3d.py`, ver roadmap) e a rodada de balanceamento de tudo do v0.4 (`balance_sim`: tempo até abrir a cratera, os portões e o L3).
