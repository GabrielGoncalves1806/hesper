# v0.4 Marco 2 · Geografia nova · Plano de implementação

> **Pra agentes:** cada Dev roda num worktree isolado e executa só a sua trilha. O gerente faz os merges. Os passos usam checkbox (`- [ ]`).

**Objetivo:** a superfície deixa de parecer tileset e passa a ter relevo, 3 regiões (planalto rachado, salar, basalto) mais a faixa gelada, chão "assado" orgânico com decalques, morros com borda orgânica e formações fixas que servem de marco. É novo jogo obrigatório (save v7).

**Referência visual aprovada pelo dono:** `reports/design/regioes/index.html` (v8.0). O código de referência da Designer é `tools/sprites/regions_core.py`, `regions_scene.py` e `regions_formations.py` (numpy + PIL). **Portar a lógica de lá**, não reinventar.

**Arte aprovada:** está em `assets/sprites/regions/` (chão, morros, decalques, decoração solta e `regions_palettes.json`). As **formações e a cratera estão em revisão** com a Designer (v8.1); até lá use os PNG de `assets/sprites/_pending/regions/` (`form_*`, `ice_gate_*`, `crater_ice_*`) só como placeholder, carregados com fallback.

**Stack:** Python 3.13, pygame-ce, **numpy** (liberado pelo dono; a trilha A adiciona com `uv add numpy`), pytest.

## Restrições globais
- Não commitar e não abrir janela visível.
- Têm que passar: `uv run pytest`, `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py`.
- Formato de surface explícito (`game/surfaces.py`, `tests/test_surface_format.py`).
- Desempenho: o smoke fica no orçamento de 16,7 ms. A meta é a superfície custar no máximo +2 ms de média em relação a hoje (meça).
- Determinístico pela seed.
- A caverna **não muda**: continua com o gerador e os tiles de hoje.
- Números novos vão no `game/config.py`. A bíblia ganha a seção "§11 v0.4 · Marco 2" (cada trilha escreve a sua parte).
- **Água e gelo derretendo são do Marco 3.** No M2:
  - as bacias existem nos dados e aparecem secas no chão (leito de silte e marca d'água);
  - a cratera e os gelos-portão existem e bloqueiam, mas ainda não derretem.

## Interfaces combinadas

```python
# game/geo.py  (trilha A) — dados puros, numpy, sem pygame
PLATEAU, SALAR, BASALT, FROST = 0, 1, 2, 3
@dataclass
class Formation:
    kind: str                 # "monolith" | "arch" | "basalt_spires" | "cone" | "salt_ridge" | "ice_gate"
    tx: int; ty: int          # canto de cima-esquerda da pegada (tiles)
    footprint: list[tuple[int, int]]   # tiles que bloqueiam, relativos a (tx, ty)
    anchor: tuple[int, int]   # px do sprite que cai no centro de baixo da pegada (do regions_palettes.json)
    variant: int = 0
@dataclass
class Geo:
    seed: int
    region: np.ndarray        # (H, W) uint8, região de cada tile (já com a borda deformada)
    height: np.ndarray        # (H, W) float32, 0..1
    basin: np.ndarray         # (H, W) int8: -1 fora de bacia; 0..2 = nível de marca d'água L1..L3 em que o tile alaga
    formations: list[Formation]
    region_px: callable       # region_px(px, py) -> região num pixel do mundo, com o warp de ±14 px (pra borda orgânica no chão)
def generate_geo(seed: int, w: int, h: int, base: tuple[int, int]) -> Geo

# Layer da superfície (trilha A): layer.geo: Geo | None   (None na caverna)
# Tile novo (trilha A): C.FORMATION — sólido, não minera, não aparece como parede (quem desenha é a formação)
```

- A trilha **B** consome `geo.region`, `geo.region_px`, `geo.basin` e `geo.seed`.
- A trilha **C** consome `geo.formations`, os tiles de morro (`world.is_wall` na superfície) e `C.FORMATION`.
- B e C, até a A ser mergeada, usam um `Geo` falso montado nos testes ou no smoke (ex. `fake_geo(w, h)` dentro do próprio teste). Nenhuma delas cria `game/geo.py`.

---

## Trilha A · Geração e dados (Dev A)
**Arquivos:**
- `pyproject.toml` (numpy)
- `game/geo.py` (novo)
- `game/surface_gen.py`
- `game/config.py`
- `game/world.py` (tile `FORMATION`)
- `game/layers.py`
- `game/save.py` (v7)
- `game/minimap.py`
- `game/wrecks.py` (só pra respeitar regiões e formações)
- `tools/dev/balance_sim.py`
- testes

- [ ] **A1.** `uv add numpy`. Crie `game/geo.py`, portando de `tools/sprites/regions_core.gen_world`/`organic`/`fbm`/`blob`/`smooth`:
  - relevo;
  - regiões: planalto em volta da base (a base fica sempre no planalto), salar a leste (a maior bacia), basalto a oeste/sudoeste e faixa gelada na borda norte. Proporções e posições como no mapa do report (`reports/design/regioes/mapa_regioes.png`), com variação pela seed;
  - bacias com 3 níveis;
  - `region_px` com warp.

  Testes:
  - determinismo;
  - a base no planalto;
  - as 4 regiões presentes nas seeds 1, 7 e 42;
  - o salar como a maior bacia;
  - o warp mudando a região perto da borda, mas nunca a mais de 14 px dela.
- [ ] **A2.** `surface_gen` v7, usando o `Geo`:
  - morros mineráveis por região (o salar quase sem morro; o basalto com mais);
  - formações colocadas em lugar válido. A pegada vira `C.FORMATION`, e cada uma tem 3 a 4 **afloramentos** (rochas pequenas de minério, `SMALL_*`) a 1–2 tiles em volta;
  - os gelos-portão fechando de 2 a 3 corredores na faixa gelada, com algo atrás: os destroços mais longe e o contêiner lacrado ficam pro M3, mas deixe as posições marcadas em `geo`;
  - a cratera dentro do planalto, ainda com o tamanho e a regra de rampa de hoje (a trilha C cuida do visual);
  - veios, destroços e rochas que reaparecem respeitando formações e regiões (`rock_respawn` não nasce em `FORMATION`).

  Testes:
  - nada nasce em cima de formação;
  - toda formação tem afloramento;
  - todo destroço e veio é alcançável a pé da base, sem contar portões: BFS no grid. Os portões bloqueiam só o que está atrás deles.
- [ ] **A3.** Save **v7**:
  - o `geo` não vai no save (é regerado pela seed);
  - save v6 → recusa com a mensagem de "novo jogo obrigatório", igual ao v0.3 (`save.probe`/título).

  Testes de save e load mais a recusa do v6.
- [ ] **A4.** Minimapa e mapa (`minimap.TILE_COLORS`):
  - o chão da superfície pinta pela região (cor média da rampa do Árido de cada uma, em `regions_palettes.json`);
  - a formação aparece como marcador fixo de paisagem: categoria nova "Formação" em `map_view`, sem filtro, só pictograma simples.
- [ ] **A5.** No `balance_sim.py`, confira que a partida não quebrou: as distâncias dos destroços e o minério perto da base. Só reporte; o balanceamento é depois.
- [ ] **A6.** Validação e bíblia §11 (geração).

## Trilha B · Chão assado (Dev B)
**Arquivos:**
- `game/ground.py` (novo)
- `game/render.py`: só o desenho do chão da superfície, em `draw_floors`/`_draw_floor`, pela camada nova
- `game/assets.py`, se precisar
- testes

- [ ] **B1.** `game/ground.py`, portando de `tools/sprites/regions_scene.py` (classe `Scene`, `tex`, `rmp`, `warp_field`, `decals`, `scatter`):
  - o chão da superfície é **assado em blocos de 16×16 tiles (512×512 px)** com numpy + `pygame.surfarray`;
  - textura da região pelo `region_px` (borda orgânica);
  - rampa de cor do estágio (`regions_palettes.json` → `ramps`, com chave `art`: storm/arid/mist/green, conforme o `stage_key`);
  - leito de silte e marca d'água nas bacias (`geo.basin`);
  - decalques espalhados pela seed (`decal_cell`, `decal_p`, `decal_mix`).
- [ ] **B2.** Cache dos blocos:
  - por (bloco, estágio de arte);
  - só assa o que está perto da tela;
  - no máximo 1 bloco por frame, com prioridade pro que está visível; o que ainda não foi assado usa uma cor chapada da região;
  - LRU limitado em memória.

  Na troca de estágio, re-assa aos poucos. O fade de transição de hoje tem que continuar funcionando: misturar os dois estágios no bloco, ou usar o mecanismo atual de transição; escolha e documente.
- [ ] **B3.** Decoração solta com altura (`decor_*`): entra no `build_draw_list` como objeto ordenado pelo pé, sem colisão.
- [ ] **B4.** Desempenho:
  - mede o custo de assar um bloco;
  - o frame no pior caso (andando rápido com F3);
  - a média do smoke contra a de hoje.
- [ ] **B5.** Validação:
  - pytest, smoke e checador (com uma tela de superfície nova);
  - prints das 4 regiões no Árido e de uma borda entre regiões, comparados com os mockups do report.

## Trilha C · Morros orgânicos, formações e cratera (Dev C)
**Arquivos:**
- `game/hills.py` (novo)
- `game/render.py`: só o desenho de parede/morro da superfície e os objetos de formação
- `game/autotile.py`, se reaproveitar
- testes

- [ ] **C1.** Morros orgânicos na superfície, portando a grade dual do `regions_scene` (`hill_top_tex`, `face_index`, silhueta extrudada 24 px):
  - a mesma colisão por tile de hoje;
  - a borda reta continua na borda do tile, e a escada vira curva;
  - o topo e a face são assados em blocos, junto com a cache da B ou numa própria, e **re-assados só no bloco tocado quando um tile é minerado**;
  - a rachadura de mineração e o "fantasma" continuam funcionando;
  - a caverna continua com as paredes de hoje.
- [ ] **C2.** Formações como objetos no `build_draw_list`:
  - sprite pela âncora;
  - a pegada bloqueia (já é `C.FORMATION` pela trilha A);
  - o player passa por trás quando está acima do pé (mesma regra de ordem das máquinas);
  - o vão do arco é andável;
  - o sprite vem de `assets/sprites/regions/form_<kind>.png`, com fallback em `_pending/regions/` (placeholder até a v8.1).
- [ ] **C3.** Cratera:
  - o visual de cratera de impacto (borda irregular e bacia), com a rampa no fundo;
  - a **tampa de gelo** (estado `crater_ice` 0..N no layer, sempre fechado no M2; o derretimento é do M3) bloqueando a descida;
  - a dica "Gelo · derrete com o calor" no lugar de "[E] Descer".

  O objetivo "Desça na caverna" passa a vir depois do "Derreta o gelo da cratera" (este ainda não completável no M2: deixe o objetivo, e o M3 liga o derretimento).

  **Atenção:** isso trava a caverna no M2. Pro smoke e pros testes, use um atalho de debug (ex. F4 = derrete a cratera na hora, só com debug ligado) e documente.
- [ ] **C4.** Gelo-portão como formação `ice_gate` (sprite do estágio 0), bloqueando.
- [ ] **C5.** Validação:
  - pytest, smoke e checador;
  - prints de morro antes × depois, das 6 formações no mundo, da cratera tampada e do player atrás do arco e na frente dele.

## Arte (Designer, em andamento)
A v8.1 redesenha as formações (arco natural, hoodoo, colunas de basalto, crosta de sal, cone, gelo-portão) e a cratera de impacto com a tampa de gelo baixando "como um lago secando". Quando o dono aprovar, os arquivos vão de `_pending/regions/` pra `assets/sprites/regions/` e a trilha C troca o fallback.

## Ordem de merge (gerente)
1. **A**: dados, tile `FORMATION`, save v7.
2. **B**: chão assado; tira o `fake_geo`.
3. **C**: morros, formações e cratera; tira o `fake_geo`.

Depois de cada merge, rodar pytest, smoke e checador. Com os três dentro, olhar os prints contra o report e chamar o dono pra jogar **um novo jogo**.
