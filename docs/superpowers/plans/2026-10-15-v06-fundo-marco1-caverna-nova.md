# v0.6 Fundo · Marco 1 · Caverna nova · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** a caverna passa a ter 256×256, com a rampa embaixo da cratera, quatro regiões (centro, salar a leste, gelo ao norte, basalto a oeste), rocha dura nos biomas trancados, veios de parede de 6 a 8 tiles, bem menos minério solto, cobre no salar e magmatita em veio e rochinha no basalto. O F3 quebra rocha dura. Save v12 descarta a caverna antiga.

**Arquitetura:** a geração da caverna sai do `game/world.py` e vai pra um módulo novo, `game/cave_gen.py` (no molde do `game/surface_gen.py`). `World.generate(seed)` continua existindo e só delega pra `cave_gen.generate_cave(seed)`, então os ~17 testes que chamam `World.generate` seguem funcionando. A rampa lê a cratera da superfície pelo cache do `surface_gen` (função nova `crater_of(seed)`). O mapa de regiões é um `np.ndarray` em `world.cave_region` (só na caverna; na superfície fica `None`, e o `world.geo` da caverna continua `None`, porque muito código de superfície testa `geo is not None`). As regiões usam os mesmos números do `game/geo.py` (`PLATEAU` = centro, `SALAR`, `BASALT`, `FROST`). A dureza é uma regra do `World` (`is_hard`), e quem decide se o player pode quebrar é o `GameState` (`can_break_hard`, que no M1 é só o F3; o M4 soma a broca nv.2).

**Stack:** Python 3.13, pygame-ce, numpy, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-v06-fundo-design.md` (M1). Bíblia §15.

## Restrições globais
- Caverna **256×256** (`C.CAVE_W = C.CAVE_H = 256`). O tamanho padrão de um `World` vazio (`C.WORLD_W/WORLD_H`, usado por testes) **continua 128**: desacoplar do `CAVE_W`.
- Rampa da caverna no **mesmo canto** da cratera da superfície (`world.crater` igual). `world.center = (crater_x + 1, crater_y + 3)` (a chegada, como era `CAVE_CENTER` em relação a `CAVE_RAMP`).
- Regiões pela direção: **gelo ao norte** (faixa de cima inteira), **basalto a oeste**, **salar a leste** (maior), **centro** em volta da rampa. Fronteira torta (fbm). Raio livre em volta da rampa: sempre centro.
- **Rocha dura** (`C.HARD_ROCK`) em toda parede de rocha do gelo e do basalto. Minério de parede dentro dessas regiões também é duro (`World.is_hard`). A nv.1 não quebra; dica **"Rocha dura demais · precisa da broca nv.2"**. Bedrock continua inquebrável.
- **A magmatita não nasce na parede.** Na caverna: veios 2×2 e rochinhas (`C.SMALL_MAGMATITE`) no chão do basalto. As rochinhas da caverna **não reaparecem** (o `game/magmatite.py` é só das fumarolas da superfície; não mexer).
- **Cobre** (`"copper"`): recurso novo em `C.RESOURCES`, tile de parede `C.COPPER`, veio 2×2. **Sem rochinha de cobre** neste marco.
- `C.VEIN_RESOURCES` **não muda** (é o sorteio dos veios da **superfície**). A caverna usa a tabela própria `C.CAVE_VEINS`.
- **Save v12**: v11 carrega sem a caverna (`layers.cave` some inteiro); se o player estava na caverna, volta pra chegada da cratera na superfície.
- **F3** (`state.fast`) quebra rocha dura.
- Visual **provisório**: chão e rocha da caverna levemente tingidos por região. A arte de verdade é o M2. **Não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/`, `settings.json`.** O cobre usa os desenhos de fallback do `game/art.py` (que saem de `C.ORE_COLORS`) até a arte da Designer ser promovida.
- Não abrir janela, não commitar. No fim: `uv run pytest`, `uv run python tools/dev/smoke.py`, `uv run python tools/dev/real_video_check.py`. Se o smoke estourar o orçamento num ponto só (o "caverna escura no zoom 0,75" às vezes estoura), rode de novo antes de chamar de regressão.

## Decisões (o dono deveria ver)
- **Números de partida** (todos no bloco "v0.6 Fundo M1" do `game/config.py`): as fronteiras são medidas **a partir do meio do mapa** (128, 128), não da rampa, porque a cratera cai a 15–20 tiles da base em qualquer direção e isso desequilibraria as áreas por seed. Gelo começa a **48 tiles ao norte** do meio, basalto a **40 a oeste**, salar a **26 a leste**, ondulação de ±10 tiles. Em volta da chegada da rampa, raio livre de **28** (sempre centro). Dá ~31% gelo, ~24% basalto, ~27% salar, ~18% centro.
- **Minério de parede por região**: centro ferro 50% / silício 35% / gelo 15%; salar cobre 60% / silício 40%; gelo gelo 80% / ferro 20%; basalto ferro 100%.
- **Minério solto** cai de ~39% das paredes pra **4 a 7%**; o resto vem em **veios de parede** (aglomerados de 6 a 8 tiles, um minério por aglomerado).
- **Começo garantido**: perto da rampa (12 a 28 tiles, na borda de um túnel/salão do centro) nascem 3 veios de parede de ferro, 3 de silício e 2 de gelo, mais 1 veio 2×2 de ferro e 1 de silício alcançáveis a pé (como hoje).
- **Veios 2×2 por região**: centro ferro e silício; salar cobre e silício; gelo só gelo; basalto só magmatita. 6 por região longe da rampa.
- **Terminais** mudam de lugar pra ficar na área livre: `(19, 35)`, `(31, 100)` e `(45, 350)` (distância, ângulo; 100° = sul, 350° ≈ leste, dentro do salar).
- **Rocha dura não tem desenho próprio**: no M1 ela é "a rocha tingida da região" (todo gelo e basalto é duro, então a cor da região já diz "não dá"). Minerar rocha dura com o F3 leva 1,5 s (antes do multiplicador do F3).
- **Sem cena nova no smoke** (regra do dono). Fica um print avulso `tools/dev/shot_v06_fundo_m1.py`: o mapa inteiro da caverna (regiões, minério, veios) e dois recortes de tela (a borda do gelo e um veio de cobre no salar).

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | `CAVE_W/H = 256`; `WORLD_W/H = 128` fixo; tiles `COPPER`, `HARD_ROCK`; `"copper"` em `RESOURCES`/`RESOURCE_LABEL`/`RESOURCE_NAME`/`ORE_COLORS`; `MINE_TIME[COPPER]`, `MINE_TIME[HARD_ROCK]`; bloco "v0.6 Fundo M1" com os números; `TERMINAL_SPOTS` novos; saem `CAVE_CENTER`, `CAVE_RAMP`, `CAVE_ORE_THRESHOLD`, `VEINS_NEAR_BASE`, `VEINS_FAR_*` |
| `game/cave_gen.py` (novo) | `region_map`, `generate_cave` e tudo da geração |
| `game/surface_gen.py` | `crater_of(seed)` |
| `game/world.py` | `World.generate` delega; saem `_pick_tile`, `_place_terminals`, `_place_veins`; entram `cave_region` e `is_hard` |
| `game/systems.py` | `can_break_hard`, `can_mine` com a dureza, `hard_blocked(tile)` |
| `game/app.py` | dica da rocha dura em `hint()` |
| `game/cave_rocks.py` | rocha orgânica tingida por região (`cave_luts`, `regions` do `world.cave_region`) |
| `game/render.py` | chão da caverna tingido por região em `_draw_floor` |
| `game/minimap.py`, `game/map_markers.py` | cores de `COPPER`, `HARD_ROCK`, chão/rocha da caverna por região, veio de cobre e de magmatita |
| `game/save.py` | `SAVE_VERSION = 12`, `_v11_to_v12`, volta pra superfície no load |
| `tools/dev/shot_v06_fundo_m1.py` (novo) | print avulso |
| `docs/GAME_BIBLE.md` | linha 477 (caverna 128×128) aponta pra §15; "Marco 1 · como ficou" na §15 |
| `tests/test_cave_gen.py` (novo) | os testes da geração |
| `tests/test_hard_rock.py` (novo) | dureza, F3, dica, cores |
| `tests/test_save.py` | migração v11 → v12 |
| `tests/test_cave.py`, `tests/test_drill.py`, `tests/test_layers.py`, `tests/test_explore.py`, `tests/test_logic.py`, `tests/test_map_view.py` | trocam `C.CAVE_CENTER`/`C.CAVE_RAMP`/`range(128)` pelo `world.center`/`world.crater`/`world.width` e as regras novas |

---

### Task 1: Gerador da caverna nova (regiões, rocha dura, cobre, veios)

**Files:**
- Create: `game/cave_gen.py`, `tests/test_cave_gen.py`
- Modify: `game/config.py:79-91` (tamanhos e constantes da caverna), `game/config.py:94-112` (tiles), `game/config.py:115` (`TERMINAL_SPOTS`), `game/config.py:163-176` (`MINE_TIME`, `RESOURCES`, rótulos), `game/config.py:239-241` (veios da caverna), `game/config.py:422-428` (`ORE_COLORS`)
- Modify: `game/surface_gen.py:42` (nova `crater_of` ao lado de `pristine_tiles`)
- Modify: `game/world.py:73-228` (`__init__`, `generate`, sai a geração antiga), `game/world.py:295` (`is_hard` logo depois de `is_minable`)
- Modify: `tests/test_cave.py`, `tests/test_drill.py`, `tests/test_layers.py:128`, `tests/test_explore.py:48`, `tests/test_logic.py:61-65`

**Interfaces:**
- Consumes: `game.geo.fbm(xs, ys, cell, seed, octaves)`, `game.geo.PLATEAU/SALAR/BASALT/FROST`, `game.world.World`, `Vein`, `value_noise`, `hash01`, `World.reachable_from`, `World._add_vein`.
- Produces (as Tasks 2 e 3 usam):
  - `C.COPPER: int`, `C.HARD_ROCK: int`, `C.CAVE_HARD_REGIONS: frozenset[int]`, `C.CAVE_W/CAVE_H = 256`.
  - `surface_gen.crater_of(seed: int) -> tuple[int, int]`.
  - `cave_gen.region_map(seed: int, center: tuple[int, int], w: int, h: int) -> np.ndarray` (uint8, (h, w)).
  - `cave_gen.generate_cave(seed: int) -> World` (com `world.cave_region` preenchido).
  - `World.cave_region: np.ndarray | None` (None fora da caverna), `World.region_at_cave(tx, ty) -> int | None`, `World.is_hard(tx, ty) -> bool`.

- [ ] **Step 1: Constantes no `game/config.py`**

Trocar o bloco das linhas 79–91 por:

```python
CAVE_W = CAVE_H = 256           # caverna (game/cave_gen.py). v0.6 Fundo M1: era 128; agora igual à superfície
WORLD_W = WORLD_H = 128         # tamanho padrão de um World VAZIO (testes). Não é mais o tamanho da caverna
CAVE_HALL_RADIUS = 12           # raio médio do salão aberto em volta da rampa (a borda é irregular por causa do noise)
CAVE_SAFE_RADIUS = 8            # dentro desse raio é sempre chão, não importa o noise
```

(`CAVE_CENTER`, `CAVE_RAMP` e `CAVE_ORE_THRESHOLD` saem: a rampa agora vem da cratera e o minério solto tem número novo.)

Tiles (depois de `SMALL_MAGMATITE = 16`):

```python
COPPER = 17                     # v0.6 Fundo M1: minério de cobre NA PAREDE (só na caverna, região do salar)
HARD_ROCK = 18                  # v0.6 Fundo M1: rocha dura (parede alta). Toda a rocha do gelo e do basalto da caverna;
                                # só a broca nv.2 quebra (no M1, o F3). Ver World.is_hard
ORE_TILES = {IRON: "iron", SILICON: "silicon", ICE: "ice", COPPER: "copper"}   # minério NA PAREDE (overlay no topo)
SMALL_ROCKS = {SMALL_IRON: "iron", SMALL_SILICON: "silicon", SMALL_ICE: "ice", SMALL_MAGMATITE: "magmatite"}
WALL_TILES = {ROCK, IRON, SILICON, ICE, COPPER, HARD_ROCK, BEDROCK, TERMINAL}   # paredes ALTAS (topo elevado + face)
```

Terminais:

```python
# Terminais de lore da caverna: (distância em tiles do centro, ângulo em graus; 0° = leste, 90° = sul). Distâncias
# crescentes. v0.6 Fundo M1: todos na área livre (centro/salar), longe do gelo (norte) e do basalto (oeste).
TERMINAL_SPOTS = [(19, 35), (31, 100), (45, 350)]
```

Mineração e recursos:

```python
MINE_TIME = {ROCK: 0.6, IRON: 1.0, SILICON: 1.2, ICE: 0.8, COPPER: 1.1,
             HARD_ROCK: 1.5,                                        # v0.6 Fundo: só com a nv.2 (no M1, o F3)
             SMALL_IRON: 0.7, SMALL_SILICON: 0.7, SMALL_ICE: 0.7,   # rocha pequena: rapidinha
             SMALL_MAGMATITE: 0.9}                                  # magmatita: basalto, um pouco mais dura

RESOURCES = ("iron", "silicon", "ice", "magmatite", "copper")
```

`RESOURCE_LABEL["copper"] = "COBRE"`, `RESOURCE_NAME["copper"] = "cobre"` (seguir o formato das outras entradas). Em `ORE_COLORS`:

```python
    "copper": ("#e0703f", "#aa4a2a"),      # v0.6 Fundo: laranja do cobre (paleta da Designer, reports/design/v06_fundo_cobre_ferro)
```

Trocar `VEINS_NEAR_BASE`, `VEINS_FAR_PER_TYPE` e `VEINS_FAR_RANGE` (linhas 239–241) pelo bloco:

```python
# v0.6 Fundo M1 · caverna nova (game/cave_gen.py · bíblia §15). Números de partida.
# Regiões (os números do game/geo.py: PLATEAU = centro). Distâncias em tiles a partir do MEIO DO MAPA (a cratera varia
# ±20 tiles por seed; medir da rampa desequilibraria as áreas). O raio livre é em volta da chegada da rampa.
CAVE_FROST_EDGE = 48            # o gelo começa a 48 tiles ao norte do meio (pega a faixa de cima inteira)
CAVE_BASALT_EDGE = 40           # o basalto, a 40 tiles a oeste
CAVE_SALAR_EDGE = 26            # o salar, a 26 tiles a leste (maior que os outros, decisão do dono)
CAVE_REGION_WARP = 10           # quanto a fronteira ondula (± tiles, fbm)
CAVE_FREE_RADIUS = 28           # em volta da chegada é sempre centro
CAVE_HARD_REGIONS = frozenset({2, 3})   # BASALT, FROST (game/geo.py): rocha dura
# Minério de parede por região: {região: ((recurso, peso), ...)}. A magmatita nunca nasce na parede.
CAVE_WALL_ORE = {0: (("iron", 0.50), ("silicon", 0.35), ("ice", 0.15)),
                 1: (("copper", 0.60), ("silicon", 0.40)),
                 2: (("iron", 1.0),),
                 3: (("ice", 0.80), ("iron", 0.20))}
CAVE_LOOSE_ORE_THRESHOLD = 0.80   # minério solto: o noise passa disto (alvo: 4–7% das paredes; calibrar nas seeds 7/1/42)
CAVE_WALL_VEIN_SIZE = (6, 8)      # veio de parede: 6 a 8 tiles do mesmo minério colados
CAVE_WALL_VEIN_TRIES = 900        # sorteios de semente de veio de parede no mapa todo (só pega em rocha)
CAVE_WALL_VEIN_SPACING = 7        # distância mínima entre as sementes de dois veios de parede
CAVE_NEAR_WALL_VEINS = {"iron": 3, "silicon": 3, "ice": 2}   # começo garantido: veios de parede perto da rampa
CAVE_NEAR_RANGE = (12, 28)        # ...a essa distância da chegada, na borda de um túnel/salão (visíveis)
# Veios 2×2 (drill) por região
CAVE_VEINS = {0: ("iron", "silicon"), 1: ("copper", "silicon"), 2: ("magmatite",), 3: ("ice",)}
CAVE_VEINS_NEAR = ("iron", "silicon")   # 1 de cada, a 8–20 tiles da chegada, alcançável a pé
CAVE_VEINS_NEAR_RANGE = (8, 20)
CAVE_VEINS_PER_REGION = 6         # longe: 6 por região, alternando os recursos da região
CAVE_VEINS_MIN_DIST = 24          # nenhum veio "de longe" a menos disso da chegada
CAVE_MAGMATITE_ROCK_CHANCE = 0.03 # rochinha de magmatita num chão do basalto (não reaparece)
```

- [ ] **Step 2: Escrever os testes que falham (`tests/test_cave_gen.py`)**

```python
"""v0.6 Fundo M1: a caverna nova (game/cave_gen.py · bíblia §15)."""

import math
from collections import Counter

import numpy as np
import pytest

from game import cave_gen, surface_gen
from game import config as C
from game.geo import BASALT, FROST, PLATEAU, SALAR
from game.world import World

SEEDS = (7, 1, 42)


@pytest.fixture(scope="module")
def caves():
    return {s: cave_gen.generate_cave(s) for s in SEEDS}


def walls(w):
    return [(x, y) for y in range(w.height) for x in range(w.width) if w.get(x, y) in C.WALL_TILES
            and w.get(x, y) not in (C.BEDROCK, C.TERMINAL)]


def test_cave_is_256_and_the_ramp_is_under_the_crater(caves):
    for s, w in caves.items():
        assert (w.width, w.height) == (256, 256)
        assert w.crater == surface_gen.crater_of(s)
        assert w.center == (w.crater[0] + 1, w.crater[1] + 3)
        assert all(w.get(w.crater[0] + dx, w.crater[1] + dy) == C.CRATER for dx in range(3) for dy in range(3))


def test_world_generate_delegates_to_cave_gen():
    assert World.generate(7).tiles == cave_gen.generate_cave(7).tiles


def test_regions_follow_the_directions(caves):
    for w in caves.values():
        r, (cx, cy) = w.cave_region, w.center
        assert r[cy, cx] == PLATEAU
        assert r[5, 128] == FROST                  # norte
        assert r[200, 5] == BASALT                 # oeste (abaixo do gelo)
        assert r[200, 250] == SALAR                # leste
        free = [(x, y) for y in range(256) for x in range(256) if math.hypot(x + .5 - cx, y + .5 - cy) < C.CAVE_FREE_RADIUS]
        assert all(r[y, x] == PLATEAU for x, y in free)


def test_region_shares_are_about_the_plan(caves):
    for w in caves.values():
        share = Counter(w.cave_region.ravel().tolist())
        n = 256 * 256
        assert 0.24 <= share[FROST] / n <= 0.38
        assert 0.18 <= share[BASALT] / n <= 0.30
        assert 0.22 <= share[SALAR] / n <= 0.34   # o salar é o maior depois do gelo
        assert share[SALAR] > share[BASALT]


def test_region_map_is_deterministic():
    a = cave_gen.region_map(7, (112, 132), 256, 256)
    assert np.array_equal(a, cave_gen.region_map(7, (112, 132), 256, 256))
    assert not np.array_equal(a, cave_gen.region_map(8, (112, 132), 256, 256))


def test_hard_regions_have_only_hard_rock(caves):
    for w in caves.values():
        for x, y in walls(w):
            reg = int(w.cave_region[y, x])
            kind = w.get(x, y)
            if kind == C.ROCK:
                assert reg not in C.CAVE_HARD_REGIONS
            if kind == C.HARD_ROCK:
                assert reg in C.CAVE_HARD_REGIONS
            if reg in C.CAVE_HARD_REGIONS:
                assert w.is_hard(x, y)


def test_free_regions_are_not_hard(caves):
    for w in caves.values():
        for x, y in walls(w):
            if int(w.cave_region[y, x]) not in C.CAVE_HARD_REGIONS:
                assert not w.is_hard(x, y)


def test_is_hard_is_false_on_the_surface_and_on_floor():
    surf = surface_gen.generate_surface(7)
    assert surf.cave_region is None
    assert not any(surf.is_hard(x, 50) for x in range(256))


def test_magmatite_never_in_the_wall_and_copper_only_in_the_salar(caves):
    for w in caves.values():
        for x, y in walls(w):
            kind = w.get(x, y)
            assert C.ORE_TILES.get(kind) != "magmatite"
            if kind == C.COPPER:
                assert int(w.cave_region[y, x]) == SALAR
            if kind in C.ORE_TILES:
                allowed = {r for r, _ in C.CAVE_WALL_ORE[int(w.cave_region[y, x])]}
                assert C.ORE_TILES[kind] in allowed


def test_ore_share_is_low_and_mostly_wall_veins(caves):
    for w in caves.values():
        ws = walls(w)
        ore = {t for t in ws if w.get(*t) in C.ORE_TILES}
        assert 0.06 <= len(ore) / len(ws) <= 0.20        # antes ~39%
        # aglomerados de 6+ tiles do mesmo minério (4-vizinhos)
        seen, big = set(), 0
        for t in ore:
            if t in seen:
                continue
            kind, stack, comp = w.get(*t), [t], 0
            seen.add(t)
            while stack:
                x, y = stack.pop()
                comp += 1
                for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if n in ore and n not in seen and w.get(*n) == kind:
                        seen.add(n)
                        stack.append(n)
            big += comp >= C.CAVE_WALL_VEIN_SIZE[0]
        assert big >= 120


def test_every_region_has_wall_veins(caves):
    for w in caves.values():
        per_region = Counter(int(w.cave_region[y, x]) for x, y in walls(w) if w.get(x, y) in C.ORE_TILES)
        for reg in (PLATEAU, SALAR, BASALT, FROST):
            assert per_region[reg] >= 30


def test_start_has_enough_ore_near_the_ramp(caves):
    for w in caves.values():
        near = Counter(C.ORE_TILES[w.get(x, y)] for x, y in walls(w)
                       if w.get(x, y) in C.ORE_TILES and w.dist_from_center(x, y) <= 30)
        assert near["iron"] >= 18 and near["silicon"] >= 18 and near["ice"] >= 12


def test_floor_veins_per_region(caves):
    for w in caves.values():
        reach = w.reachable_from(w.center)
        near = [v for v in w.veins if w.dist_from_center(*v.center) <= C.CAVE_VEINS_NEAR_RANGE[1] + 1]
        for res in C.CAVE_VEINS_NEAR:
            assert any(v.resource == res and all(t in reach for t in v.tiles) for v in near)
        for v in w.veins:
            reg = int(w.cave_region[v.ty, v.tx])
            assert v.resource in C.CAVE_VEINS[reg]
        got = Counter(v.resource for v in w.veins)
        assert got["copper"] >= 3 and got["magmatite"] >= 4 and got["ice"] >= 4


def test_magmatite_rocks_only_on_basalt_floor(caves):
    for w in caves.values():
        rocks = [(x, y) for y in range(256) for x in range(256) if w.get(x, y) == C.SMALL_MAGMATITE]
        assert len(rocks) >= 20
        assert all(int(w.cave_region[y, x]) == BASALT for x, y in rocks)
        assert not any(w.get(x, y) in (C.SMALL_IRON, C.SMALL_SILICON, C.SMALL_ICE)
                       for y in range(256) for x in range(256))


def test_terminals_are_in_the_free_area(caves):
    for w in caves.values():
        assert len(w.terminals) == 3
        for tx, ty in w.terminals:
            assert int(w.cave_region[ty, tx]) not in C.CAVE_HARD_REGIONS
            assert all(w.get(tx + dx, ty + dy) == C.FLOOR for dx in (-1, 0, 1) for dy in (1, 2))


def test_cave_never_terraforms_and_has_no_geo(caves):
    for w in caves.values():
        assert w.terraforms is False and w.geo is None
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `uv run pytest tests/test_cave_gen.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'game.cave_gen'`.

- [ ] **Step 4: `crater_of` no `game/surface_gen.py` (logo depois de `pristine_tiles`)**

```python
def crater_of(seed: int) -> tuple[int, int]:
    """Canto de cima à esquerda da cratera da seed (só leitura). A rampa da caverna nasce no mesmo canto
    (v0.6 Fundo M1)."""
    if seed not in _cache:
        _cache[seed] = _build(seed)
    return _cache[seed].crater
```

- [ ] **Step 5: `World` (`game/world.py`)**

No `__init__`, junto dos outros campos de camada:

```python
        # v0.6 Fundo M1 (só na caverna): região de cada tile, (H, W) uint8 com os números do game/geo.py
        # (PLATEAU = centro, SALAR, BASALT, FROST). None na superfície (lá a região é do self.geo).
        self.cave_region: np.ndarray | None = None
```

E o `center` padrão deixa de usar `C.CAVE_CENTER` (que sai):

```python
        self.center: tuple[int, int] = (width // 2, height // 2)  # "centro" da camada (base ou chegada da rampa), em tiles
```

`generate` vira:

```python
    @classmethod
    def generate(cls, seed: int = C.WORLD_SEED) -> "World":
        """A CAVERNA da seed (game/cave_gen.py). Fica aqui pelo nome antigo, que os testes e o layers usam."""
        from game.cave_gen import generate_cave          # cave_gen importa World: o import fica aqui dentro
        return generate_cave(seed)
```

Apagar `_pick_tile`, `_place_terminals` e `_place_veins` (vão pro `cave_gen`, reescritos). `_add_vein` e `reachable_from` ficam. Depois de `is_minable`:

```python
    def region_at_cave(self, tx: int, ty: int) -> int | None:
        """Região da caverna no tile (None fora da caverna ou fora do mapa)."""
        if self.cave_region is None or not self.in_bounds(tx, ty):
            return None
        return int(self.cave_region[ty, tx])

    def is_hard(self, tx: int, ty: int) -> bool:
        """Parede que só a broca nv.2 quebra (v0.6 Fundo): a rocha dura e o minério de parede dentro do gelo e do
        basalto da caverna."""
        kind = self.get(tx, ty)
        if kind == C.HARD_ROCK:
            return True
        return kind in C.ORE_TILES and self.region_at_cave(tx, ty) in C.CAVE_HARD_REGIONS
```

Atualizar a docstring do módulo (a caverna agora é gerada no `game/cave_gen.py`, 256×256).

- [ ] **Step 6: `game/cave_gen.py`**

```python
"""Gerador da CAVERNA (v0.6 Fundo M1 · bíblia §15). Antes morava no World.generate (128×128).

256×256, igual à superfície. A rampa de subida fica no mesmo canto da cratera da superfície (surface_gen.crater_of).
Regiões pela direção, sem copiar a geometria de cima (decisão do dono): gelo ao norte, basalto a oeste, salar a leste
(maior), centro em volta da chegada. Gelo e basalto têm rocha dura (só a broca nv.2 quebra; ver World.is_hard).

Ordem: regiões → tiles (borda, salão, cavernas naturais, minério solto raro, rocha/rocha dura) → rampa → terminais →
veios de parede (aglomerados de 6–8) → começo garantido perto da rampa → veios 2×2 por região → rochinhas de
magmatita no chão do basalto. Tudo determinístico pela seed.
"""

from __future__ import annotations

import math
import random

import numpy as np

from game import config as C
from game import surface_gen
from game.geo import BASALT, FROST, PLATEAU, SALAR, fbm
from game.world import Vein, World, hash01, value_noise


def region_map(seed: int, center: tuple[int, int], w: int, h: int) -> np.ndarray:
    """Região de cada tile, (h, w) uint8. As fronteiras saem do meio do mapa; `center` (a chegada da rampa) só marca o
    raio livre. O gelo pega a faixa de cima inteira (por cima do basalto e do salar)."""
    mx, my = w // 2, h // 2
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    s = (seed & 0xFFFF) * 16 + 500

    def warp(k: int) -> np.ndarray:
        return C.CAVE_REGION_WARP * 2 * (fbm(xs, ys, 18, s + k, 3) - 0.5)

    region = np.full((h, w), PLATEAU, np.uint8)
    region[xs - mx > C.CAVE_SALAR_EDGE + warp(1)] = SALAR
    region[mx - xs > C.CAVE_BASALT_EDGE + warp(2)] = BASALT
    region[my - ys > C.CAVE_FROST_EDGE + warp(3)] = FROST
    cx, cy = center
    region[np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) < C.CAVE_FREE_RADIUS] = PLATEAU
    return region


def pick_ore(region: int, u: float) -> int:
    """Tile de minério da região pra um sorteio u em [0, 1) (pesos de C.CAVE_WALL_ORE)."""
    table = C.CAVE_WALL_ORE[region]
    total = sum(p for _, p in table)
    acc = 0.0
    for resource, p in table:
        acc += p / total
        if u < acc:
            return _ORE_TILE[resource]
    return _ORE_TILE[table[-1][0]]


_ORE_TILE = {name: kind for kind, name in C.ORE_TILES.items()}


def _rock(region: int) -> int:
    return C.HARD_ROCK if region in C.CAVE_HARD_REGIONS else C.ROCK


def _pick_tile(world: World, x: int, y: int, dist: float, region: int) -> int:
    seed = world.seed
    if x == 0 or y == 0 or x == world.width - 1 or y == world.height - 1:
        return C.BEDROCK                                    # borda: ninguém cava pra fora do mundo
    edge = C.CAVE_HALL_RADIUS + (value_noise(x * 0.18, y * 0.18, seed) - 0.5) * 7
    if dist < C.CAVE_SAFE_RADIUS or dist < edge:
        return C.FLOOR                                      # salão em volta da rampa
    if dist > 20 and value_noise(x * 0.13 + 70, y * 0.13 + 30, seed + 3) > 0.74:
        return C.FLOOR                                      # cavernas naturais (às vezes cruzam a fronteira: tudo bem)
    if value_noise(x * 0.5 + 40, y * 0.5 + 9, seed + 7) > C.CAVE_LOOSE_ORE_THRESHOLD:
        return pick_ore(region, hash01(x, y, seed + 13))    # minério solto, raro
    return _rock(region)


def generate_cave(seed: int) -> World:
    world = World(seed, C.CAVE_W, C.CAVE_H)
    rx, ry = surface_gen.crater_of(seed)
    world.crater = (rx, ry)
    world.center = (rx + 1, ry + 3)
    world.terraforms = False                                # rocha fria: não muda com o Ti (bíblia §9)
    world.cave_region = region_map(seed, world.center, world.width, world.height)
    cx, cy = world.center
    regions = world.cave_region.tolist()
    for y in range(world.height):
        for x in range(world.width):
            dist = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
            world.tiles[y][x] = _pick_tile(world, x, y, dist, regions[y][x])
            world.lowness[y][x] = value_noise(x * 0.22 + 200, y * 0.22 + 50, seed + 21)
    for dy in range(3):
        for dx in range(3):
            world.set(rx + dx, ry + dy, C.CRATER)
    _place_terminals(world)
    rng = random.Random(seed * 7919 + 29)
    _place_wall_veins(world, rng)
    _place_near_wall_veins(world, rng)
    _place_veins(world, rng)
    _place_magmatite_rocks(world)
    return world


def _place_terminals(world: World) -> None:
    """Enterra cada terminal numa parede, com uma salinha de chão embaixo dele (área livre: rocha normal)."""
    cx, cy = world.center
    for dist, angle in C.TERMINAL_SPOTS:
        tx = int(round(cx + dist * math.cos(math.radians(angle))))
        ty = int(round(cy + dist * math.sin(math.radians(angle))))
        for dy in (-1, 0):
            for dx in (-1, 0, 1):
                world.set(tx + dx, ty + dy, C.ROCK)
        world.set(tx, ty, C.TERMINAL)
        for dy in (1, 2):
            for dx in (-1, 0, 1):
                world.set(tx + dx, ty + dy, C.FLOOR)
        world.terminals.append((tx, ty))


def _blocked(world: World) -> set[tuple[int, int]]:
    """Rampa + chegada e terminais + salinha, com folga: nada de veio por cima."""
    rx, ry = world.crater
    out = {(rx + dx, ry + dy) for dx in range(-2, 5) for dy in range(-2, 6)}
    for tx, ty in world.terminals:
        out |= {(tx + dx, ty + dy) for dx in range(-2, 3) for dy in range(-2, 4)}
    return out


def _grow(world: World, rng: random.Random, start: tuple[int, int], size: int, ore: int,
          blocked: set[tuple[int, int]]) -> int:
    """Aglomerado de `size` tiles de `ore` crescendo a partir de `start`, só por rocha (normal ou dura). Devolve
    quantos tiles virou."""
    cells, frontier = [start], [start]
    taken = {start}
    while frontier and len(cells) < size:
        x, y = frontier.pop(rng.randrange(len(frontier)))
        for n in rng.sample([(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)], 4):
            if len(cells) >= size:
                break
            if n in taken or n in blocked or world.get(*n) not in (C.ROCK, C.HARD_ROCK):
                continue
            taken.add(n)
            cells.append(n)
            frontier.append(n)
        if len(cells) < size:
            frontier.append((x, y)) if any(world.get(*m) in (C.ROCK, C.HARD_ROCK) and m not in taken
                                           for m in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))) else None
    for t in cells:
        world.set(*t, ore)
    return len(cells)


def _place_wall_veins(world: World, rng: random.Random) -> None:
    """Veios de parede pelo mapa todo: 6–8 tiles do mesmo minério (o da região da semente)."""
    blocked = _blocked(world)
    seeds: list[tuple[int, int]] = []
    lo, hi = C.CAVE_WALL_VEIN_SIZE
    for _ in range(C.CAVE_WALL_VEIN_TRIES):
        x, y = rng.randrange(2, world.width - 2), rng.randrange(2, world.height - 2)
        if world.get(x, y) not in (C.ROCK, C.HARD_ROCK) or (x, y) in blocked:
            continue
        if any(abs(x - sx) + abs(y - sy) < C.CAVE_WALL_VEIN_SPACING for sx, sy in seeds):
            continue
        seeds.append((x, y))
        ore = pick_ore(int(world.cave_region[y, x]), rng.random())
        _grow(world, rng, (x, y), rng.randint(lo, hi), ore, blocked)


def _place_near_wall_veins(world: World, rng: random.Random) -> None:
    """Começo garantido: veios de parede de ferro, silício e gelo na borda de um túnel/salão perto da rampa."""
    blocked = _blocked(world)
    lo, hi = C.CAVE_NEAR_RANGE
    lo_s, hi_s = C.CAVE_WALL_VEIN_SIZE
    edge = [(x, y) for y in range(1, world.height - 1) for x in range(1, world.width - 1)
            if world.get(x, y) == C.ROCK and lo <= world.dist_from_center(x, y) <= hi and (x, y) not in blocked
            and any(world.get(*n) == C.FLOOR for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))]
    rng.shuffle(edge)
    for resource, count in C.CAVE_NEAR_WALL_VEINS.items():
        ore = _ORE_TILE[resource]
        for _ in range(count):
            while edge and world.get(*edge[-1]) != C.ROCK:
                edge.pop()
            if not edge:
                return
            _grow(world, rng, edge.pop(), rng.randint(lo_s, hi_s), ore, blocked)


def _place_veins(world: World, rng: random.Random) -> None:
    """Veios 2×2 (drill): 1 de ferro e 1 de silício perto (chão aberto, alcançável a pé) e CAVE_VEINS_PER_REGION por
    região longe, com os recursos da região (C.CAVE_VEINS). Longe e sem chão: cava um bolsão 4×4 em volta."""
    blocked = _blocked(world)

    def block_ok(tx, ty, spacing):
        if not (3 <= tx <= world.width - 5 and 3 <= ty <= world.height - 5):
            return False
        if any((tx + dx, ty + dy) in blocked for dx in range(-1, 3) for dy in range(-1, 3)):
            return False
        return all(math.hypot(tx - v.tx, ty - v.ty) >= spacing for v in world.veins)

    def open_floor(tx, ty):
        return all(world.get(tx + dx, ty + dy) == C.FLOOR for dx in (0, 1) for dy in (0, 1, 2))

    def region_of(tx, ty):
        return int(world.cave_region[ty, tx])

    reach = world.reachable_from(world.center)
    lo, hi = C.CAVE_VEINS_NEAR_RANGE
    for resource in C.CAVE_VEINS_NEAR:
        candidates = [(tx, ty) for ty in range(world.height - 1) for tx in range(world.width - 1)
                      if lo <= world.dist_from_center(tx + 1, ty + 1) <= hi and block_ok(tx, ty, 8)
                      and open_floor(tx, ty) and all(t in reach for t in Vein(resource, tx, ty).tiles)]
        if candidates:
            world._add_vein(Vein(resource, *rng.choice(candidates)))

    for region, resources in C.CAVE_VEINS.items():
        placed = 0
        for _ in range(3000):
            if placed >= C.CAVE_VEINS_PER_REGION:
                break
            tx, ty = rng.randrange(3, world.width - 5), rng.randrange(3, world.height - 5)
            if region_of(tx, ty) != region or region_of(tx + 1, ty + 1) != region:
                continue
            if world.dist_from_center(tx + 1, ty + 1) < C.CAVE_VEINS_MIN_DIST or not block_ok(tx, ty, 10):
                continue
            if any(world.get(tx + dx, ty + dy) == C.TERMINAL for dx in range(-1, 3) for dy in range(-1, 3)):
                continue
            if not open_floor(tx, ty):
                for dy in range(-1, 3):
                    for dx in range(-1, 3):
                        world.set(tx + dx, ty + dy, C.FLOOR)
            world._add_vein(Vein(resources[placed % len(resources)], tx, ty))
            placed += 1


def _place_magmatite_rocks(world: World) -> None:
    """Rochinhas de magmatita no chão do basalto (não reaparecem: o magmatite.py é das fumarolas da superfície)."""
    for y in range(1, world.height - 2):
        for x in range(1, world.width - 1):
            if world.get(x, y) != C.FLOOR or world.get(x, y + 1) != C.FLOOR:
                continue
            if int(world.cave_region[y, x]) != BASALT or world.vein_at(x, y) is not None:
                continue
            if any(world.vein_at(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                continue
            if hash01(x, y, world.seed + 77) < C.CAVE_MAGMATITE_ROCK_CHANCE:
                world.set(x, y, C.SMALL_MAGMATITE)
```

> O `_grow` acima tem uma linha de "religar a fronteira" escrita como expressão. Se ficar confuso, reescreva como `if` normal: o comportamento esperado é "o tile continua na fronteira enquanto tiver vizinho de rocha livre". O que vale é o teste.

- [ ] **Step 7: Rodar os testes novos**

Run: `uv run pytest tests/test_cave_gen.py -q`
Expected: PASS. Se `test_ore_share_is_low_and_mostly_wall_veins` ou `test_region_shares_are_about_the_plan` falharem só no número, **calibre** `CAVE_LOOSE_ORE_THRESHOLD`, `CAVE_WALL_VEIN_TRIES` e as `CAVE_*_EDGE` (não os limites do teste) e anote os valores finais pro gerente. Meça o tempo de `generate_cave(7)` (esperado < 1,5 s) e anote.

- [ ] **Step 8: Ajustar os testes antigos que dependiam da caverna 128**

- `tests/test_cave.py`: `C.CAVE_RAMP` → `W.crater` e `C.CAVE_RAMP == surface_gen.crater_of(seed)`; `range(128)` → `range(W.width)`/`range(W.height)`. `test_cave_ore_is_more_abundant_and_richer_far` e `test_cave_ore_share_is_about_38_to_40_percent_and_the_ramp_has_enough` **saem** (a regra mudou; a cobertura nova está em `test_cave_gen.py`). O resto (rampa, descer/subir, luminária, estação, luz, fade) tem que passar sem mudar a intenção.
- `tests/test_drill.py:21-42`: `C.CAVE_CENTER` → `world.center`; a conta de veios "de longe" passa a ser `C.CAVE_VEINS_PER_REGION` por região (`len(C.CAVE_VEINS)` regiões) em vez de `C.VEINS_FAR_PER_TYPE` por tipo.
- `tests/test_layers.py:128`: `g.world.center == C.CAVE_CENTER` → `g.world.center == (g.world.crater[0] + 1, g.world.crater[1] + 3)`.
- `tests/test_explore.py:48` e `tests/test_logic.py:61-65`: `C.CAVE_RAMP` → `world.crater`.

Run: `uv run pytest -q`
Expected: tudo verde, exceto o que a Task 2 vai cobrir (`test_map_view.py:602` pode falhar se o chão da caverna mudou de cor; **deixe pra Task 2** só se for esse).

---

### Task 2: Dureza no jogo, F3, dica, cores e visual provisório por região

**Files:**
- Create: `tests/test_hard_rock.py`
- Modify: `game/systems.py:582-586` (`can_mine`), `game/systems.py:1932-1934` (perto de `mine_speed`: `can_break_hard`, `hard_blocked`)
- Modify: `game/app.py:2044-2053` (`hint`)
- Modify: `game/cave_rocks.py:42-47` (`cave_luts`), `game/cave_rocks.py:82` (`regions`)
- Modify: `game/render.py:971-989` (`_draw_floor`), `game/render.py:~218` (superfícies de tinta no `__init__`)
- Modify: `game/minimap.py:17-27, 54-69`, `game/map_markers.py:18`
- Modify: `tests/test_map_view.py:602`

**Interfaces:**
- Consumes (Task 1): `World.is_hard(tx, ty)`, `World.cave_region`, `World.region_at_cave(tx, ty)`, `C.COPPER`, `C.HARD_ROCK`, `C.CAVE_HARD_REGIONS`, `"copper"` em `C.ORE_COLORS`.
- Produces: `GameState.can_break_hard -> bool` (property; o M4 soma a broca nv.2 aqui), `GameState.hard_blocked(tile) -> bool`, `C.CAVE_REGION_TINT: dict[int, tuple[int, int, int, int]]`, `minimap.CAVE_REGION_COLORS: dict[int, tuple]`.

- [ ] **Step 1: Testes que falham (`tests/test_hard_rock.py`)**

```python
"""v0.6 Fundo M1: rocha dura (a nv.1 não quebra, o F3 quebra), dica e cores."""

from game import config as C
from game import layers, minimap
from game.geo import FROST, PLATEAU, SALAR
from game.systems import GameState


def cave_state(seed=7) -> GameState:
    g = GameState(seed=seed)
    g.enter_layer(layers.CAVE, layers.ramp_arrival(layers.make_cave(seed).world))
    return g


def put_player_next_to(g, tile):
    tx, ty = tile
    g.world.set(tx, ty + 1, C.FLOOR)
    g.player.x, g.player.y = (tx + 0.5) * C.TILE, (ty + 1) * C.TILE + 24


def first(g, pred):
    w = g.world
    return next((x, y) for y in range(2, w.height - 2) for x in range(2, w.width - 2) if pred(x, y))


def test_nv1_cannot_mine_hard_rock_and_f3_can():
    g = cave_state()
    tile = first(g, lambda x, y: g.world.get(x, y) == C.HARD_ROCK)
    put_player_next_to(g, tile)
    assert g.hard_blocked(tile) and not g.can_mine(tile)
    g.fast = True
    assert g.can_break_hard and not g.hard_blocked(tile) and g.can_mine(tile)


def test_ore_inside_hard_region_is_hard_too():
    g = cave_state()
    tile = first(g, lambda x, y: g.world.get(x, y) == C.ICE and g.world.region_at_cave(x, y) == FROST)
    put_player_next_to(g, tile)
    assert g.world.is_hard(*tile) and not g.can_mine(tile)


def test_copper_in_the_salar_mines_normally_and_drops_copper():
    g = cave_state()
    tile = first(g, lambda x, y: g.world.get(x, y) == C.COPPER)
    assert g.world.region_at_cave(*tile) == SALAR
    put_player_next_to(g, tile)
    assert g.can_mine(tile)
    for _ in range(200):
        g._update_mining(0.05, tile)
        if g.world.get(*tile) != C.COPPER:
            break
    assert g.inventory.count("copper") >= 1


def test_hard_rock_hint(app_factory):
    app = app_factory(cave_state())
    tile = first(app.state, lambda x, y: app.state.world.get(x, y) == C.HARD_ROCK)
    put_player_next_to(app.state, tile)
    app.mouse_tile = lambda: tile
    app.hand_drill_selected = lambda: True
    assert app.hint() == "Rocha dura demais · precisa da broca nv.2"


def test_surface_has_no_hard_rule():
    g = GameState(seed=7)
    tile = first(g, lambda x, y: g.world.get(x, y) == C.ROCK)
    assert not g.hard_blocked(tile)


def test_minimap_colors_the_cave_by_region_and_knows_copper():
    g = cave_state()
    w = g.world
    cx, cy = w.center
    assert minimap.tile_color(w, cx, cy) == minimap.CAVE_REGION_COLORS[PLATEAU]
    copper = first(g, lambda x, y: w.get(x, y) == C.COPPER)
    assert minimap.tile_color(w, *copper) == minimap.TILE_COLORS[C.COPPER]
    assert C.HARD_ROCK in minimap.TILE_COLORS
    assert {"copper", "magmatite"} <= set(minimap.VEIN_COLORS)
```

> `app_factory`: não existe `conftest.py`. Copie a fixture `app` (escopo de módulo) do `tests/test_base_app.py:49-55` pro arquivo novo e troque `app_factory(cave_state())` por `app.state = cave_state()`. `App.mouse_tile` (`game/app.py:339`) e `App.hand_drill_selected` (`game/app.py:559`) são métodos: trocar por `lambda` na instância funciona (restaure no fim do teste com `del app.mouse_tile, app.hand_drill_selected`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_hard_rock.py -q`
Expected: FAIL com `AttributeError: 'GameState' object has no attribute 'hard_blocked'`.

- [ ] **Step 3: Regra no `GameState` (`game/systems.py`)**

Perto de `mine_speed`:

```python
    @property
    def can_break_hard(self) -> bool:
        """Quebra rocha dura? (v0.6 Fundo: só a broca nv.2, que entra no M4; no M1, o F3 pra testar os biomas)"""
        return self.fast

    def hard_blocked(self, tile: tuple[int, int]) -> bool:
        """Tile duro que o player ainda não consegue quebrar."""
        return self.world.is_hard(*tile) and not self.can_break_hard
```

`can_mine`:

```python
    def can_mine(self, tile: tuple[int, int]) -> bool:
        if not self.world.is_minable(*tile) or self.hard_blocked(tile):
            return False
        px, py = self.player.tile
        return max(abs(tile[0] - px), abs(tile[1] - py)) <= C.MINE_REACH
```

(O `_update_mining` já chama `can_mine` e zera a mineração quando não pode. O `_break_tile` não muda: `HARD_ROCK` não dá recurso, o cobre dá `"copper"` pelo `C.TILE_RESOURCE`.)

- [ ] **Step 4: Dica no `App.hint` (`game/app.py`)**

Dentro de `if state.world.is_minable(*tile):`, logo depois do teste da broca na mão:

```python
            if state.hard_blocked(tile):                     # v0.6 Fundo: gelo e basalto da caverna
                return "Rocha dura demais · precisa da broca nv.2"
```

- [ ] **Step 5: Tinta por região (`game/config.py`, bloco "v0.6 Fundo M1")**

```python
# Visual PROVISÓRIO por região (até a arte do M2): tinta RGBA por cima do chão e cor da rocha orgânica.
CAVE_REGION_TINT = {0: (0, 0, 0, 0),            # centro: a névoa de sempre
                    1: (214, 176, 120, 46),     # salar: areia
                    2: (150, 52, 30, 52),       # basalto: brasa
                    3: (140, 200, 235, 52)}     # gelo
```

- [ ] **Step 6: Rocha orgânica tingida (`game/cave_rocks.py`)**

`cave_luts` passa a misturar a tinta de cada região na rampa (a região 0 fica igual):

```python
def cave_luts() -> dict[int, np.ndarray]:
    """LUT (80×3) no formato do `hills.colorize_block`: a rampa da caverna em cada região (v0.6 Fundo M1: tingida
    pela C.CAVE_REGION_TINT, provisório até a arte do M2) e, +40, a versão escurecida (topo da borda do mapa)."""
    base = cave_ramp().astype(np.float32)
    rows = []
    for region in range(len(hills.REGIONS)):
        r, g, b, a = C.CAVE_REGION_TINT.get(region, (0, 0, 0, 0))
        k = a / 255
        rows.append((base * (1 - k) + np.array([r, g, b], np.float32) * k).astype(np.uint8))
    lut = np.concatenate(rows)
    lut = np.concatenate([lut, (lut * hills.BEDROCK_SHADE).astype(np.uint8)])
    return {n: lut for n in STAGES}
```

Função nova no módulo (o `hills.tile_window` não serve: ele preenche fora do mapa com `BEDROCK` = 5, que não é região):

```python
def region_window(region: np.ndarray, i0: int, i1: int, j0: int, j1: int) -> np.ndarray:
    """Regiões da janela [j0, j1) × [i0, i1); fora do mapa repete a borda."""
    h, w = region.shape
    ys = np.clip(np.arange(j0, j1), 0, h - 1)
    xs = np.clip(np.arange(i0, i1), 0, w - 1)
    return region[np.ix_(ys, xs)]
```

Em `strips`, trocar `regions = np.zeros(kinds.shape, np.uint8)` por:

```python
            regions = (region_window(world.cave_region, i0, i1, j0, j1)
                       if world.cave_region is not None else np.zeros(kinds.shape, np.uint8))
```

(`hills.REGIONS` já está na ordem do `game/geo.py`: PLATEAU, SALAR, BASALT, FROST = 0..3; o código da LUT é `região · 10`.)

- [ ] **Step 7: Chão tingido (`game/render.py`)**

No `__init__`, perto do `bedrock_shade`:

```python
        self.region_tint = {}                               # v0.6 Fundo M1: tinta provisória do chão da caverna
        for region, rgba in C.CAVE_REGION_TINT.items():
            if rgba[3]:
                s = pygame.Surface((T, T), pygame.SRCALPHA)
                s.fill(rgba)
                self.region_tint[region] = s
```

No `_draw_floor`, logo depois do `canvas.blit(self.surface(*sprite(stage))[0], (sx, sy))`:

```python
        tint = self.region_tint.get(world.region_at_cave(tx, ty))
        if tint is not None:
            canvas.blit(tint, (sx, sy))
```

(`region_at_cave` devolve `None` na superfície, então lá não muda nada.)

- [ ] **Step 8: Mapa e minimapa (`game/minimap.py`, `game/map_markers.py`)**

`game/minimap.py`:

```python
TILE_COLORS = {
    ...                                   # as entradas de hoje
    C.COPPER: (206, 112, 66),             # v0.6 Fundo: cobre na parede
    C.HARD_ROCK: (44, 38, 44),            # v0.6 Fundo: rocha dura (fora da caverna não existe)
}
VEIN_COLORS = {"iron": (232, 160, 102), "silicon": (195, 209, 226), "ice": (166, 236, 255),
               "copper": (224, 112, 63), "magmatite": (255, 122, 46)}
# v0.6 Fundo M1: chão da caverna no mapa, por região (provisório como a tinta do render)
CAVE_REGION_COLORS = {0: (92, 84, 80), 1: (130, 112, 88), 2: (96, 66, 60), 3: (98, 118, 134)}
```

Em `tile_color`, antes do `return TILE_COLORS.get(...)` final:

```python
    region = world.region_at_cave(x, y) if hasattr(world, "region_at_cave") else None
    if region is not None and kind == C.FLOOR:
        return CAVE_REGION_COLORS[region]
```

`game/map_markers.py:18`:

```python
VEIN_COLORS = {"iron": "#e8a066", "silicon": "#c3d1e2", "ice": "#a6ecff", "copper": "#e0703f", "magmatite": "#ff7a2e"}
```

`tests/test_map_view.py:602`: o chão do centro da caverna agora pinta `minimap.CAVE_REGION_COLORS[PLATEAU]` (que é a mesma cor do `FLOOR` de antes; ajuste só se o teste usar outro ponto).

- [ ] **Step 9: Rodar**

Run: `uv run pytest -q`
Expected: tudo verde.

---

### Task 3: Save v12, print avulso, desempenho e bíblia

**Files:**
- Modify: `game/save.py:1-60` (docstring), `game/save.py:90` (`SAVE_VERSION`), `game/save.py:469-485` (`state_from_dict`), `game/save.py:~500` (`_v11_to_v12`, `MIGRATIONS`)
- Modify: `tests/test_save.py`
- Create: `tools/dev/shot_v06_fundo_m1.py`
- Modify: `docs/GAME_BIBLE.md:477` e §15

**Interfaces:**
- Consumes: `layers.ramp_arrival(world)`, `state.layers[SURFACE].world`, Tasks 1 e 2.
- Produces: `SAVE_VERSION = 12`, `save._v11_to_v12(data) -> dict`.

- [ ] **Step 1: Testes que falham (`tests/test_save.py`)**

```python
def test_v11_save_drops_the_old_cave_and_keeps_the_surface():
    g = GameState(seed=7)
    g.inventory.add("iron", 9)
    g.enter_layer(layers.CAVE, layers.ramp_arrival(layers.make_cave(7).world))
    data = save.state_to_dict(g)
    data["version"] = 11
    data["layers"]["cave"]["changed_tiles"] = [[3, 3, C.FLOOR]]
    data["layers"]["cave"]["machines"] = [{"kind": "chest", "tx": 5, "ty": 5}]
    data["layer"] = "cave"
    loaded = save.state_from_dict(save.migrate(data))
    assert "cave" not in loaded.layers
    assert loaded.layer == layers.SURFACE
    assert (loaded.player.x, loaded.player.y) == layers.ramp_arrival(loaded.layers[layers.SURFACE].world)
    assert loaded.inventory.count("iron") >= 9


def test_v11_save_on_the_surface_keeps_the_player_where_it_was():
    g = GameState(seed=7)
    g.player.x, g.player.y = 4000.0, 4100.0
    data = save.state_to_dict(g)
    data["version"] = 11
    loaded = save.state_from_dict(save.migrate(data))
    assert (loaded.player.x, loaded.player.y) == (4000.0, 4100.0)


def test_v12_round_trip_keeps_the_new_cave():
    g = GameState(seed=7)
    g.enter_layer(layers.CAVE, layers.ramp_arrival(layers.make_cave(7).world))
    tile = next((x, y) for y in range(256) for x in range(256) if g.world.get(x, y) == C.COPPER)
    g.world.set(*tile, C.FLOOR)
    loaded = save.state_from_dict(save.migrate(save.state_to_dict(g)))
    assert loaded.layers[layers.CAVE].world.get(*tile) == C.FLOOR
    assert save.SAVE_VERSION == 12
```

(Use os imports que o `tests/test_save.py` já tem; acrescente `from game import layers` e `from game import config as C` se faltar.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_save.py -q -k "v11 or v12"`
Expected: FAIL (`"cave" in loaded.layers` / `SAVE_VERSION == 11`).

- [ ] **Step 3: Migração e load (`game/save.py`)**

```python
SAVE_VERSION = 12  # v12 (v0.6 Fundo M1): caverna nova 256×256 (a do v11 é descartada) · v11 (v0.6 M2): "chip" nas máquinas que precisam · v10 (v0.5 M3.1): superfície 256×256 (a mesma seed gera outro mundo) · v9: blocos da base e Dispersor
```

```python
def _v11_to_v12(data: dict) -> dict:
    """v0.6 Fundo M1: a caverna mudou inteira (256×256, regiões). Decisão do dono: a do save antigo some (tiles,
    máquinas, baús, estações, o que tiver), sem compensação. Quem estava lá embaixo volta pra cratera da superfície
    (o state_from_dict põe o player na chegada dela)."""
    data.get("layers", {}).pop("cave", None)
    if data.get("layer") == "cave":
        data["layer"] = "surface"
        data["_back_to_crater"] = True
    return data


MIGRATIONS: dict = {10: _v10_to_v11, 11: _v11_to_v12}
```

Em `state_from_dict`, logo depois de `state.layer = layer`:

```python
    if data.get("_back_to_crater"):               # v11 -> v12: estava na caverna antiga
        state.player.x, state.player.y = layers.ramp_arrival(state.surface.world)
```

> `GameState.surface` é uma property (`game/systems.py:384`). Atualize a docstring do módulo (formato v12, a linha do "Saves antigos").

- [ ] **Step 4: Rodar**

Run: `uv run pytest -q`
Expected: tudo verde.

- [ ] **Step 5: Print avulso `tools/dev/shot_v06_fundo_m1.py`**

No molde do `tools/dev/shot_v06_m3.py` (mesmo jeito de subir o pygame headless, montar o `App` e salvar PNG). Saídas em `reports/dev/v06_fundo_m1/`:
1. `mapa_caverna_seed7.png`: a caverna inteira 256×256 pelo `minimap.tile_color(world, x, y, reveal=True)`, 3 px por tile, com a rampa marcada.
2. `borda_gelo.png`: tela do jogo (zoom 1) com o player no centro, na borda do gelo (um tile de chão a ≤ 3 tiles de um `HARD_ROCK` da região `FROST`), com F3 desligado.
3. `cobre_salar.png`: tela com o player perto de um veio de parede de cobre no salar.
4. As mesmas 1–3 pra seed 42 (`*_seed42.png`).

Run: `uv run python tools/dev/shot_v06_fundo_m1.py`
Expected: os 6 PNGs criados. Olhe os PNGs e descreva no relatório o que aparece (regiões nas direções certas, cobre laranja, rocha tingida).

- [ ] **Step 6: Desempenho e as 3 ferramentas**

Run: `uv run pytest -q && uv run python tools/dev/smoke.py && uv run python tools/dev/real_video_check.py`
Expected: verde. Anote no relatório: ms/frame da "caverna escura no zoom 0,75" (antes ~5,2 ms) e o tempo de `cave_gen.generate_cave(7)`.

- [ ] **Step 7: Bíblia**

- `docs/GAME_BIBLE.md:477` (ponto "Caverna: 128×128..."): no fim, acrescentar " *(v0.6 Fundo M1: substituído; ver §15.)*".
- No fim da §15, a seção **"### Marco 1 · como ficou na implementação (`game/cave_gen.py`, `game/world.py`, `game/systems.py`, `game/save.py`; números no bloco "v0.6 Fundo M1" do `game/config.py`)"** com: tamanho e rampa, as bordas das regiões e a % medida de cada uma nas seeds 7/1/42, o % de minério nas paredes medido, veios (de parede e 2×2) por região, terminais, rocha dura e a dica, F3, save v12, o visual provisório, tempo de geração e ms/frame.

---

## Fechamento (gerente)
1. Revisar o diff e os PNGs do `shot_v06_fundo_m1.py`.
2. `uv run pytest`, smoke e `real_video_check` no main depois do merge.
3. Commit (como Gabriel Oliveira) e prints em commit separado (sem o `reports/dev/receitas.html`).
4. Marcar o ROADMAP e avisar o dono pra testar (F3 pra entrar nos biomas). Lembrar: carregar o save atual descarta a caverna.
5. A arte do cobre e do ferro novo (report da Designer) entra quando o dono aprovar, em passo separado (promover os PNGs e trocar a cor do brilho do ferro em `C.ORE_COLORS`).
