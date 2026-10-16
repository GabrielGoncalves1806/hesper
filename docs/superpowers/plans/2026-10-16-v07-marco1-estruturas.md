# v0.7 Lore · Marco 1 · Estruturas · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** 4 estruturas da Colônia Hesper (acampamento, laboratório da Ilves, estação de derretedores, posto de perfuração) geradas pela seed, uma de cada por mundo, montadas com os blocos da base e máquinas que já existem: casca intocável, máquinas quebradas que desmontam uma vez, caixa de saque, terminais com 12 LOGs novos e marcador no mapa.

**Arquitetura:**
- **`game/ruins.py`** (novo, Python puro): lê as plantas de texto (`game/ruin_plans/*.txt`), gira/espelha, sorteia destruição, escolhe o lugar e devolve objetos `Ruin`. Não importa pygame.
- **Duas metades**, pra o save funcionar sem migração:
  - **tiles** (o que muda o mapa: chão limpo/escavado, gelo ou rocha da destruição, o tile `LOOT_CRATE` da caixa) entram **na geração** (`surface_gen._build` e `cave_gen.generate_cave`, no fim). Ficam no mapa "virgem" (pristine), que é a base do `changed_tiles` do save;
  - **objetos** (blocos `BaseBlock` com `ruin=True`, máquinas `Machine` com `broken=True`, a `Crate` da caixa) são **recolocados da seed** toda vez que a camada nasce (`layers.make_surface/make_cave`) e depois do load (`save.layers_from_dict`). **Nunca vão no save.** No save vai só `ruin_salvaged` (máquinas quebradas já desmontadas).
- `world.ruins` (lista de `Ruin`), `world.ruin_tiles` (pegada de todas, pra travar construção e reaparecimento de rocha) e `world.ruin_terminals` (`{tile: índice em LOGS}`).

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-v07-lore-design.md` (seção "M1 · Estruturas"); bíblia §2 (canon) e §16. LOGs: `docs/lore/logs_v07_rascunho.md` (**aprovado pelo dono**; é a fonte dos textos, dias e títulos).

## Restrições globais
- **Números de partida** (balanceamento depois). Use exatamente estes, num bloco `# v0.7 M1 · Estruturas` no fim do `game/config.py`:
  - `RUIN_CAMP_DIST = (40, 60)` tiles do centro da cratera (`world.crater` + 1,5) até o centro do acampamento.
  - `RUIN_LAB_GIANT_MIN = 28` tiles do centro do lab até o tile do gelo gigante (`world.geo.giant.giant` → use o `tile` do pé; sem `geo.giant`, sem restrição).
  - `RUIN_MARGIN = 2` (folga de areia livre em volta, superfície). `RUIN_CAVE_MARGIN = 3` (na caverna, tudo até 3 tiles da pegada tem que ser sólido e da mesma região). `RUIN_SPACING = 20` (distância mínima do centro da ruína ao centro de qualquer destroço).
  - Destruição: `RUIN_DAMAGE_LEVELS = (0, 1, 2, 3)`; chance de cada `~` virar o efeito: `RUIN_DAMAGE_FLOOR = {0: 0.0, 1: 0.35, 2: 0.65, 3: 1.0}`; chance de cada parede "comum" cair: `RUIN_DAMAGE_WALL = {0: 0.0, 1: 0.0, 2: 0.08, 3: 0.16}`.
  - Desmontar máquina quebrada (`RUIN_SALVAGE`): `"o2": {"iron": 3}`, `"heater": {"iron": 3, "silicon": 1}`, `"melter": {"iron": 4}`, `"lamp": {"iron": 1, "silicon": 1}`.
  - Loot da caixa (`RUIN_LOOT`, recursos `{item: (mín, máx)}` + peças `{item: (chance, (mín, máx))}`, mesmo formato dos destroços):
    - `camp`: recursos `{"iron": (6, 10), "silicon": (4, 8)}`, peças `C.LOOT_COMMON`
    - `lab`: recursos `{"silicon": (6, 10), "ice": (5, 10)}`, peças `C.LOOT_RICH`
    - `melters`: recursos `{"iron_ingot": (3, 6), "ice": (10, 16)}`, peças `C.LOOT_RICH`
    - `drill_post`: recursos `{"copper_ingot": (3, 6), "magmatite": (2, 4)}`, peças `C.LOOT_RICH`
- **Uma de cada por mundo.** Se não couber em lugar nenhum (depois do afrouxamento da Task 2), aquela não nasce, e o jogo segue. Teste: nas seeds 1..20 nascem as 4.
- **Casca intocável:** bloco `ruin` não desmonta, não conta na vedação de base do player e **o player não constrói em tile de `world.ruin_tiles`** (nem máquina nem bloco). A broca não quebra (os blocos já não são tiles de mundo; o que é tile, como o gelo da destruição, quebra normal).
- **Máquina quebrada** (`broken=True`): não soma índice, Ti nem energia; não acende luz; não anima; o E não abre; não entra em rede de drone. Desmontar (direito, construtor na mão, como hoje) devolve `RUIN_SALVAGE[kind]` e ela some (vai pro `ruin_salvaged`).
- **Save continua v12.** Campos novos opcionais. Objeto de ruína nunca vai no save. Save antigo carrega: a ruína cuja pegada tem máquina ou bloco do player **não ganha os objetos** naquele mundo (`layer.ruins_off`).
- **LOGs:** 12 novos, índices **7 a 18** em `LOGS`, com `LOG_DAYS` e `LOG_TITLES` do rascunho. Os índices 0..6 não mudam.
- A fonte do jogo **não tem "→"**: em texto use ":" ou palavra.
- Não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` e `settings.json`. **Sem arte nem som novos** (terminal, blocos e máquinas usam os sprites que existem).
- **Sem cena nova no smoke** (regra do dono). Prints avulsos em `tools/dev/shot_v07_m1.py` (Task 6). **Antes do fim, varra o `tools/dev/smoke.py`** (grep `build(`, `place`, `teleport`, coordenadas fixas na superfície) atrás de cena que constrói num lugar onde agora pode nascer o acampamento (40–60 tiles da cratera) e ajuste a cena, se precisar.
- Não abrir janela e não commitar. No fim: `uv run pytest`. O gerente roda o smoke e o `real_video_check` no merge.

## Decisões (o dono deveria ver)
- **Terminal da ruína fica na parede** (como os da caverna): o dígito da planta é uma parede da casca com o sprite `terminal` desenhado na face dela, lido do tile de baixo. Depois de girar/espelhar, um terminal que ficou sem chão logo abaixo **muda pra a parede mais perto da mesma estrutura que tem chão embaixo** (determinístico). Assim valem as 8 orientações.
- **Lâmpada da ruína é quebrada** (apagada). Ruína é escura; quem ilumina é o player.
- **Não dá pra construir dentro da ruína** (pegada inteira). É o que garante que o save novo nunca entra em conflito com a ruína.
- **A caixa da ruína desmonta** vazia, igual à do destroço (devolve 3 ferro). Ela não é casca.
- **Marcador no mapa:** "Ruína" (pictograma do destroço com cor própria) quando algum tile da pegada foi visto; vira o nome da estrutura ("Laboratório da Ilves") depois que o player lê qualquer LOG dela.

---

## Estrutura de arquivos

| Arquivo | O quê |
|---|---|
| `game/ruin_plans/camp.txt`, `lab.txt`, `melters.txt`, `drill_post.txt` | **novo** · as 4 plantas (Task 1) |
| `game/ruins.py` | **novo** · `Plan`, `load_plan`, `transform`, `Ruin`, `damage`, `place_surface_ruins`, `place_cave_ruins`, `RuinSpot`, `ruin_loot`, `make_ruin_crates`, `apply_overlays` |
| `game/config.py` | bloco "v0.7 M1", LOGs 7..18 |
| `game/surface_gen.py` | chama `place_surface_ruins` no fim do `_build`; `_copy` copia `ruins`, `ruin_tiles`, `ruin_terminals` |
| `game/cave_gen.py` | chama `place_cave_ruins` no fim do `generate_cave` |
| `game/world.py` | atributos `ruins`, `ruin_tiles`, `ruin_terminals` no `World.__init__` |
| `game/layers.py` | `Layer.ruin_salvaged`, `Layer.ruins_off`; `make_surface`/`make_cave` criam as caixas e chamam `apply_overlays` |
| `game/base.py` | `BaseBlock.ruin`; vedação trata bloco `ruin` como vazamento |
| `game/systems.py` | `Machine.broken`; exclusões; desmontar; `can_place`; terminal da ruína no E |
| `game/rock_respawn.py` | `can_spawn` recusa `world.ruin_tiles` |
| `game/wrecks.py` | `loot_for` despacha `RuinSpot` |
| `game/save.py` | não salva objeto de ruína; `ruin_salvaged`; reaplica depois do load |
| `game/render.py`, `game/lighting.py` (se a luz morar lá), `game/app.py`, `game/map_view.py`, `game/map_markers.py` | desenho, E, marcador |
| `tests/test_ruins.py` | **novo** · tudo de regra |
| `tools/dev/shot_v07_m1.py` | **novo** · prints de cada estrutura |

---

### Task 1: Plantas e leitor

**Files:**
- Create: `game/ruin_plans/camp.txt`, `game/ruin_plans/lab.txt`, `game/ruin_plans/melters.txt`, `game/ruin_plans/drill_post.txt`
- Create: `game/ruins.py`
- Test: `tests/test_ruins.py`

**Interfaces:**
- Produces: `ruins.Plan` (dataclass: `key: str`, `name: str`, `layer: str` ("surface"/"cave"), `damage: str` ("sand"/"ice"/"rock"), `grid: list[str]`, `machines: dict[str, str]` (letra → kind), `logs: dict[str, int]` (dígito → índice em LOGS)); `ruins.load_plan(key) -> Plan`; `ruins.PLAN_KEYS = ("camp", "lab", "melters", "drill_post")`; `ruins.transform(grid, orient: int) -> list[str]` (orient 0..7: `orient % 4` giros de 90° no sentido horário, `orient >= 4` espelha na horizontal antes de girar).

Formato do arquivo: linhas `chave: valor` até uma linha `---`; depois a grade. Caracteres da grade:

```
#  parede            .  chão             D  porta (solo; orientação sai dos vizinhos)
=  porta dupla (sempre 2 "=" vizinhos, na horizontal ou na vertical)
~  chão que a destruição pode trocar     c  caixa de saque (tem chão embaixo)
1 2 3  terminal (é parede; o LOG sai da legenda)
o h m l  máquina quebrada (letra na legenda; tem chão embaixo)
(espaço)  fora da estrutura
```

- [ ] **Step 1: Escreva as 4 plantas** (copie exatamente; cada linha da grade tem a mesma largura).

`game/ruin_plans/camp.txt`:
```
name: Acampamento de pouso
layer: surface
damage: sand
o: o2
h: heater
l: lamp
1: 7
2: 8
3: 9
---
###1#####2#####
#.....#.......#
#.....#..c....#
#..~~.D.......#
#..~~.#..~~...#
#l....#3##D####
#.............#
#..o..~~...h..#
#.....~~......#
######==#######
```

`game/ruin_plans/lab.txt`:
```
name: Laboratório da Ilves
layer: surface
damage: ice
m: melter
h: heater
o: o2
l: lamp
1: 10
2: 11
3: 12
---
####1###2####
#...........#
#.~~..c..~~.#
#.~~.....~~.#
####D###3####
#.....#.....#
#..m..#..h..#
#.....D.....#
#l....#..o..#
#########==##
```

`game/ruin_plans/melters.txt`:
```
name: Estação de derretedores
layer: cave
damage: ice
m: melter
h: heater
l: lamp
1: 13
2: 14
3: 15
---
####1######2####
#..............#
#.m..m..m..m...#
#......~~......#
#..~~..~~...c..#
#......~~......#
#.h....#3#...l.#
#..............#
#######==#######
```

`game/ruin_plans/drill_post.txt`:
```
name: Posto de perfuração
layer: cave
damage: rock
h: heater
o: o2
l: lamp
1: 16
2: 17
3: 18
---
###1####2###
#..........#
#.h..~~..o.#
#....~~....#
####D###3###
#..........#
#.~~....c..#
#.~~.....l.#
#####==#####
```

- [ ] **Step 2: Testes que falham** (`tests/test_ruins.py`):

```python
from game import ruins


def test_all_plans_load_and_are_rectangular():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        assert plan.key == key and plan.name
        assert len({len(row) for row in plan.grid}) == 1


def test_plan_letters_are_declared():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        used = {ch for row in plan.grid for ch in row} - set("#.D=~c ")
        assert used <= set(plan.machines) | set(plan.logs)


def test_terminals_have_floor_below_in_the_drawing():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for y, row in enumerate(plan.grid):
            for x, ch in enumerate(row):
                if ch in plan.logs:
                    assert plan.grid[y + 1][x] not in "# 123"


def test_transform_has_8_distinct_orientations_and_keeps_counts():
    grid = ruins.load_plan("camp").grid
    seen = set()
    for orient in range(8):
        out = ruins.transform(grid, orient)
        seen.add(tuple(out))
        assert sorted("".join(out)) == sorted("".join(grid))
    assert len(seen) == 8
    assert ruins.transform(grid, 0) == grid


def test_rotate_90_clockwise():
    assert ruins.transform(["ab", "cd"], 1) == ["ca", "db"]
    assert ruins.transform(["ab", "cd"], 4) == ["ba", "dc"]


def test_logs_7_to_18_are_used_once():
    used = sorted(i for key in ruins.PLAN_KEYS for i in ruins.load_plan(key).logs.values())
    assert used == list(range(7, 19))
```

- [ ] **Step 3: Rode e veja falhar:** `uv run pytest tests/test_ruins.py -v` → FAIL (`No module named game.ruins`).

- [ ] **Step 4: Implemente o começo do `game/ruins.py`:**

```python
"""Estruturas da Colônia Hesper (v0.7 M1 · bíblia §16): plantas desenhadas à mão + variação pela seed.

As plantas moram em game/ruin_plans/*.txt (cabeçalho "chave: valor" até "---", depois a grade, 1 caractere por tile).
Duas metades: os TILES (chão limpo/escavado, destruição, a caixa) entram na geração e ficam no mapa virgem; os OBJETOS
(blocos `ruin`, máquinas `broken`, a Crate) são recolocados da seed quando a camada nasce e depois do load (nunca vão
no save). Python puro, testado em tests/test_ruins.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PLAN_DIR = Path(__file__).with_name("ruin_plans")
PLAN_KEYS = ("camp", "lab", "melters", "drill_post")
TERMINAL_CHARS = "123"


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    layer: str                      # "surface" ou "cave"
    damage: str                     # "sand", "ice" ou "rock": o que a destruição põe no lugar
    grid: list[str]
    machines: dict[str, str] = field(default_factory=dict)   # letra -> kind da máquina quebrada
    logs: dict[str, int] = field(default_factory=dict)       # dígito -> índice em C.LOGS


def load_plan(key: str) -> Plan:
    head, grid = (PLAN_DIR / f"{key}.txt").read_text(encoding="utf-8").split("\n---\n", 1)
    meta = dict(line.split(":", 1) for line in head.splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    rows = [row for row in grid.splitlines() if row]
    machines = {k: v for k, v in meta.items() if len(k) == 1 and k not in TERMINAL_CHARS}
    logs = {k: int(v) for k, v in meta.items() if k in TERMINAL_CHARS}
    return Plan(key, meta["name"], meta["layer"], meta["damage"], rows, machines, logs)


def transform(grid: list[str], orient: int) -> list[str]:
    """`orient` 0..7: espelha na horizontal se >= 4, depois gira 90° no sentido horário (orient % 4) vezes."""
    rows = [row[::-1] for row in grid] if orient >= 4 else list(grid)
    for _ in range(orient % 4):
        rows = ["".join(rows[len(rows) - 1 - y][x] for y in range(len(rows))) for x in range(len(rows[0]))]
    return rows
```

- [ ] **Step 5: Rode:** `uv run pytest tests/test_ruins.py -v` → PASS.

---

### Task 2: Montagem, destruição e lugar no mapa (a metade dos tiles)

**Files:**
- Modify: `game/ruins.py`, `game/config.py` (bloco "v0.7 M1"), `game/world.py`, `game/surface_gen.py`, `game/cave_gen.py`
- Test: `tests/test_ruins.py`

**Interfaces:**
- Consumes: `load_plan`, `transform` (Task 1).
- Produces:
  - `ruins.Ruin` (dataclass): `key`, `name`, `layer`, `tx`, `ty` (canto de cima à esquerda), `grid: list[str]` (já transformada **e** com a destruição aplicada, ver abaixo), `machines: dict[tuple[int,int], str]` (tile → kind), `terminals: dict[tuple[int,int], int]` (tile da parede → índice em LOGS), `crate: tuple[int,int]`, `level: int`; propriedades `tiles` (todos os tiles não-espaço da grade, em coordenada de mundo), `center: tuple[float, float]`.
  - `ruins.build(plan, orient, level, rng) -> Ruin | None` com `tx = ty = 0` (quem posiciona chama `ruin.moved(tx, ty)`, que devolve uma cópia deslocada).
  - `ruins.place_surface_ruins(world, seed) -> None` e `ruins.place_cave_ruins(world, seed) -> None`: escolhem o lugar, **carimbam os tiles** e preenchem `world.ruins`, `world.ruin_tiles` (frozenset) e `world.ruin_terminals`.
- Na grade final do `Ruin`, depois da destruição, os caracteres são: `#` parede, `.` chão, `D`/`=` porta, `c` caixa, letras de máquina, dígitos de terminal, **`x`** = tile que a destruição trocou (sem bloco; o tile de mundo já leva o efeito), `' '` fora.

Regras do `build`:
1. `grid = transform(plan.grid, orient)`.
2. **Terminal reassentado:** pra cada dígito, se o tile logo abaixo não é chão (`.`, `~`, `c` ou letra de máquina), troque o dígito por `#` e ponha o dígito na **parede `#` mais perto** (distância de Chebyshev, desempate por `(y, x)`) que tenha chão logo abaixo e não seja vizinha de porta. Faça na ordem `1, 2, 3`.
3. **Destruição** (`level` 0..3): cada `~` vira `x` com chance `RUIN_DAMAGE_FLOOR[level]` (senão vira `.`). Cada `#` "comum" (não é canto, não é vizinho de porta nem de terminal, tem exatamente 2 vizinhos `#`/porta/dígito em linha reta) vira `x` com chance `RUIN_DAMAGE_WALL[level]`. Use o `rng` nessa ordem: linhas de cima pra baixo, colunas da esquerda pra direita, `~` e `#` no mesmo passe.
4. **Caminho garantido:** com `x` contando como **bloqueado** quando `plan.damage != "sand"` (gelo e rocha são parede; areia é chão sem bloco), um BFS de 4 vizinhos a partir de cada tile de porta precisa alcançar: o tile abaixo de cada terminal e um vizinho da caixa. Se falhar, `build` devolve `None` (quem chama tenta `level - 1`; `level 0` sempre passa, testado).

Efeito no mapa do `x`: `sand` = `world.floor_kind` (na superfície, areia; sem bloco por cima); `ice` = `C.ICE`; `rock` = `C.ROCK`. Os outros tiles da pegada viram `world.floor_kind`, menos a caixa (`C.LOOT_CRATE`).

Lugar:
- **Superfície** (`place_surface_ruins`, no fim do `surface_gen._build`, depois de `_place_magmatite_rocks`): `camp` e `lab`, cada um com `rng = random.Random(seed * 6151 + i * 97 + 17)` (`i` = posição em `PLAN_KEYS`). Até 4000 tentativas: sorteia `orient` (0..7), `level` (0..3; se `build` der None, desce), posição. Serve se a pegada + `RUIN_MARGIN` é toda `C.SAND`, sem veio, fora de `world.keep_clear` e de bacia (`geo.basin_at >= 0`), longe do centro (`dist_from_center >= SURFACE_CLEAR_RADIUS + 2`), fora da cratera (≥ 8 tiles), a `RUIN_SPACING` de cada destroço (`world.wrecks`, centro a centro) e da outra ruína. `camp`: centro a `RUIN_CAMP_DIST` do centro da cratera. `lab`: todos os tiles da pegada com `geo.region_at == FROST` e centro a `RUIN_LAB_GIANT_MIN` do gelo gigante. Sem lugar em 4000: tenta mais 4000 aceitando `RUIN_MARGIN = 1` e (só o `camp`) `RUIN_CAMP_DIST` de (30, 75); ainda sem lugar, não nasce.
- **Caverna** (`place_cave_ruins`, no fim do `generate_cave`): `melters` na região `FROST`, `drill_post` na `BASALT` (`world.cave_region`). Serve se a pegada + `RUIN_CAVE_MARGIN` é toda sólida (`world.get` em `C.SOLID_TILES`, sem `BEDROCK`), da mesma região e longe de veio. A pegada é **escavada** (vira `C.FLOOR`) e a destruição carimbada; a rocha em volta fica. Mesmo afrouxamento (margem 2, depois 1).
- `World.__init__`: `self.ruins: list = []`, `self.ruin_tiles: frozenset = frozenset()`, `self.ruin_terminals: dict = {}`. `surface_gen._copy` copia os três (a lista e o dict com `list(...)`/`dict(...)`).

- [ ] **Step 1: Testes que falham:**

```python
import random

from game import config as C
from game import layers, ruins
from game.world import World


def test_build_level0_always_passes_every_orientation():
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            r = ruins.build(plan, orient, 0, random.Random(1))
            assert r is not None
            assert sorted(r.terminals.values()) == sorted(plan.logs.values())
            for (tx, ty) in r.terminals:
                assert r.grid[ty + 1][tx] in ".c" or r.grid[ty + 1][tx] in plan.machines


def test_same_seed_same_ruin():
    a, b = layers.make_surface(7).world, layers.make_surface(7).world
    assert [(r.key, r.tx, r.ty, r.grid) for r in a.ruins] == [(r.key, r.tx, r.ty, r.grid) for r in b.ruins]


def test_four_ruins_on_seeds_1_to_20():
    for seed in range(1, 21):
        surf = layers.make_surface(seed).world
        cave = World.generate(seed)
        assert {r.key for r in surf.ruins} == {"camp", "lab"}, seed
        assert {r.key for r in cave.ruins} == {"melters", "drill_post"}, seed


def test_camp_distance_and_lab_region():
    for seed in range(1, 11):
        w = layers.make_surface(seed).world
        camp = next(r for r in w.ruins if r.key == "camp")
        kx, ky = w.crater
        d = ((camp.center[0] - kx - 1.5) ** 2 + (camp.center[1] - ky - 1.5) ** 2) ** 0.5
        assert 30 <= d <= 75
        lab = next(r for r in w.ruins if r.key == "lab")
        assert all(w.geo.region_at(*t) == 3 for t in lab.tiles)       # FROST


def test_cave_ruins_are_inside_hard_rock_region():
    from game.geo import BASALT, FROST
    for seed in range(1, 6):
        w = World.generate(seed)
        for r in w.ruins:
            want = FROST if r.key == "melters" else BASALT
            assert all(int(w.cave_region[y, x]) == want for x, y in r.tiles)
            x0, y0 = r.tx - 1, r.ty - 1                                # a borda logo fora é rocha (dura ou destruição)
            assert w.get(x0, y0) in C.SOLID_TILES


def test_ruin_tiles_and_crate_tile():
    w = layers.make_surface(3).world
    for r in w.ruins:
        assert set(r.tiles) <= w.ruin_tiles
        assert w.get(*r.crate) == C.LOOT_CRATE
```

- [ ] **Step 2: Rode e veja falhar.**
- [ ] **Step 3: Implemente** `Ruin`, `build`, `place_surface_ruins`, `place_cave_ruins`, as chamadas em `surface_gen._build`/`cave_gen.generate_cave`, os atributos do `World` e a cópia no `_copy`. Ponha as constantes no `config.py`.
- [ ] **Step 4: Rode `uv run pytest tests/test_ruins.py -v`** → PASS. Depois `uv run pytest` inteiro: os testes que fixam o mapa de uma seed (destroço num tile exato, contagem de rochas) podem mudar; a ruína nasce **por último** e com rng próprio, então só deve mudar o que cai dentro da pegada. Se algum teste quebrar por isso, ajuste a expectativa do teste (não a ruína) e anote no relatório.

---

### Task 3: Os objetos (casca, máquinas quebradas, caixa, terminais)

**Files:**
- Modify: `game/ruins.py`, `game/base.py`, `game/systems.py`, `game/layers.py`, `game/wrecks.py`, `game/rock_respawn.py`, `game/config.py` (`RUIN_SALVAGE`, `RUIN_LOOT`)
- Test: `tests/test_ruins.py`

**Interfaces:**
- Consumes: `world.ruins`, `Ruin.grid/machines/terminals/crate` (Task 2).
- Produces:
  - `BaseBlock.ruin: bool = False` (field com `compare=False`).
  - `Machine.broken: bool = field(default=False, compare=False)`.
  - `Layer.ruin_salvaged: set = field(default_factory=set)` (tiles de máquina quebrada já desmontada) e `Layer.ruins_off: set = field(default_factory=set)` (keys de ruína sem objetos neste mundo).
  - `ruins.RuinSpot` (frozen dataclass, molde do `ContainerSpot`): `tx`, `ty`, `key`, `name` (ex.: "Caixa · Acampamento de pouso"), `log=None`, `terminal=None`, `blueprint=None`, `rich=False`; propriedade `crate`.
  - `ruins.ruin_loot(spot, seed) -> list[tuple[str, int]]` (rng `random.Random(seed * 3203 + spot.tx * 41 + spot.ty * 13 + 9)`, recursos de `RUIN_LOOT[key]` e depois `wrecks._roll_parts` com as peças).
  - `ruins.make_ruin_crates(world, seed) -> dict[tile, Crate]`.
  - `ruins.apply_overlays(layer) -> None`: pra cada `Ruin` de `layer.world.ruins`: se algum tile da pegada tem máquina **não quebrada** ou bloco **não ruin** da camada, põe `key` em `layer.ruins_off`, tira a caixa dela de `layer.crates` e segue. Senão adiciona os `BaseBlock(..., ruin=True)` (`#` e dígito = `BASE_WALL`; `.`, `c`, máquina = `BASE_FLOOR`; `D` = `BASE_DOOR`; o par `=` = um `BASE_DOOR2` com âncora a oeste/norte e `orient` H/V) e as `Machine(kind, tx, ty, broken=True)` que não estão em `layer.ruin_salvaged`. Idempotente: antes de adicionar, remove os objetos de ruína que já estão na camada.
  - `wrecks.loot_for` despacha `RuinSpot` pra `ruins.ruin_loot` (import dentro da função, pra não criar ciclo).

Regras (cada uma com teste):
- `layers.make_surface`: `crates={**make_crates(world, seed), **ruins.make_ruin_crates(world, seed)}` e `ruins.apply_overlays(layer)` antes do `return`. `make_cave`: `Layer(CAVE, world, crates=ruins.make_ruin_crates(world, seed))` + `apply_overlays`.
- **Casca:** `GameState.can_dismantle` devolve False pra `BaseBlock` com `ruin`. Na vedação (`BaseGrid.seal_from`), bloco `ruin` conta como **vazamento** (igual a tile sem bloco).
- **Não constrói na ruína:** `can_place` (máquina) e `_can_place_base` devolvem False se algum tile está em `self.world.ruin_tiles`.
- **Máquina quebrada:** `working_machines` exclui `broken` (isso já tira índice, Ti e energia, que usam `working_machines`; confira com grep `all_machines`/`state.machines` em `systems.py`, `drones.py`, `energy.py`, `render.py`, e exclua `broken` onde a máquina "funciona": luz das máquinas e das luminárias no render, animação, "+O2", status no mundo, logística dos drones). `interactable_at` devolve `None` pra máquina `broken`. `dismantle_returns` devolve `dict(C.RUIN_SALVAGE[kind])` pra `broken` (sem custo da receita). `dismantle` de `broken`: além de remover, `self.active.ruin_salvaged.add((m.tx, m.ty))`.
- **Caixa:** `dismantle_crate` usa `self.world.floor_kind` em vez de `C.SAND` (na caverna o chão é `FLOOR`).
- **Rocha que reaparece:** `rock_respawn.can_spawn` devolve False se `(tx, ty) in world.ruin_tiles` (vale pra magmatita também, que usa a mesma regra; confira).
- **Terminal no E:** `interactable_at`, antes dos terminais da caverna: `if tile in self.world.ruin_terminals and ruin não está em ruins_off: return "ruin_log", tile`. `in_reach("ruin_log", tile)`: distância dos pés até `((tx + 0.5) * T, (ty + 1) * T)` `<= C.TERMINAL_REACH`. `interaction()` (o "mais perto") entra com a mesma distância. Helper `GameState.ruin_of_tile(tile) -> Ruin | None`.

- [ ] **Step 1: Testes que falham:**

```python
from game import config as C
from game import layers, ruins, save
from game.base import BaseBlock
from game.systems import GameState, Machine


def _state_at_ruin(seed=3, key="camp"):
    s = save.new_state(seed)
    r = next(r for r in s.world.ruins if r.key == key)
    return s, r


def test_overlays_add_walls_and_broken_machines():
    s, r = _state_at_ruin()
    ruin_blocks = [b for b in s.base.blocks if b.ruin]
    assert ruin_blocks
    broken = [m for m in s.machines if m.broken]
    assert {(m.tx, m.ty) for m in broken} == set(r.machines)
    assert all(m not in s.working_machines for m in broken)


def test_apply_overlays_is_idempotent():
    s, _ = _state_at_ruin()
    n_blocks, n_machines = len(s.base.blocks), len(s.machines)
    ruins.apply_overlays(s.active)
    assert (len(s.base.blocks), len(s.machines)) == (n_blocks, n_machines)


def test_ruin_wall_cannot_be_dismantled_and_blocks_building():
    s, r = _state_at_ruin()
    wall = next(b for b in s.base.blocks if b.ruin and b.is_wall)
    s.player.x, s.player.y = (wall.tx + 0.5) * C.TILE, (wall.ty + 2) * C.TILE
    assert not s.can_dismantle(wall)
    floor = next(t for t, b in s.base.cells.items() if b.ruin and b.is_floor and t not in r.machines and t != r.crate)
    assert not s.can_place("lamp", floor)


def test_broken_machine_salvages_once():
    s, r = _state_at_ruin()
    m = next(m for m in s.machines if m.broken)
    s.player.x, s.player.y = (m.tx + 0.5) * C.TILE, (m.ty + 2) * C.TILE
    assert s.dismantle_returns(m) == C.RUIN_SALVAGE[m.kind]
    before = s.inventory.count("iron")
    assert s.dismantle(m)
    assert s.inventory.count("iron") == before + C.RUIN_SALVAGE[m.kind].get("iron", 0)
    assert (m.tx, m.ty) in s.active.ruin_salvaged
    ruins.apply_overlays(s.active)
    assert all((x.tx, x.ty) != (m.tx, m.ty) for x in s.machines)


def test_ruin_crate_has_loot_and_terminals_are_readable():
    s, r = _state_at_ruin()
    crate = s.crates[r.crate]
    assert not crate.empty
    tile, log = next(iter(r.terminals.items()))
    s.player.x, s.player.y = (tile[0] + 0.5) * C.TILE, (tile[1] + 1.4) * C.TILE
    assert s.in_reach("ruin_log", tile)


def test_rocks_never_respawn_inside_a_ruin():
    from game import rock_respawn
    w = layers.make_surface(3).world
    assert not any(rock_respawn.can_spawn(w, *t) for t in w.ruin_tiles)
```

(Ajuste nomes de helper do inventário — `count`, `base.cells` — ao que existe no código; o comportamento testado é o que vale.)

- [ ] **Step 2: Rode e veja falhar.**
- [ ] **Step 3: Implemente.**
- [ ] **Step 4: `uv run pytest`** → tudo verde.

---

### Task 4: Save

**Files:**
- Modify: `game/save.py`
- Test: `tests/test_ruins.py`

**Interfaces:**
- Consumes: `Layer.ruin_salvaged`, `Layer.ruins_off`, `ruins.apply_overlays`, `Machine.broken`, `BaseBlock.ruin`.
- Produces: campo opcional por camada `"ruin_salvaged": [[x, y], ...]` (só quando não vazio). Docstring do topo do `save.py` ganha a linha do campo. **`SAVE_VERSION` continua 12.**

Regras:
- `layers_to_dict`: `machines` sem as `broken`; `base` sem os blocos `ruin`.
- `layers_from_dict`: depois de carregar `machines` e `base` e **antes** do laço das `crates`, faça `layer.ruin_salvaged = {tuple(map(int, t)) for t in ldata.get("ruin_salvaged", [])}`, `layer.ruins_off = set()` e `ruins.apply_overlays(layer)`.
- `crates_to_list` já usa `loot_for` (que agora entende `RuinSpot`).

- [ ] **Step 1: Testes que falham:**

```python
import json

from game import save


def test_save_roundtrip_keeps_ruins_and_salvage(tmp_path):
    s = save.new_state(3)
    m = next(m for m in s.machines if m.broken)
    s.player.x, s.player.y = (m.tx + 0.5) * 32, (m.ty + 2) * 32
    assert s.dismantle(m)
    data = save.state_to_dict(s)
    surf = data["layers"]["surface"]
    assert all(not d.get("broken") for d in surf["machines"])
    assert surf["ruin_salvaged"] == [[m.tx, m.ty]]
    t = save.state_from_dict(json.loads(json.dumps(data)))
    assert (m.tx, m.ty) not in {(x.tx, x.ty) for x in t.machines if x.broken}
    assert len([b for b in t.base.blocks if b.ruin]) == len([b for b in s.base.blocks if b.ruin])


def test_old_save_with_player_machine_on_footprint_skips_that_ruin():
    s = save.new_state(3)
    r = next(r for r in s.world.ruins if r.key == "camp")
    data = save.state_to_dict(s)
    x, y = next(t for t in r.tiles if t != r.crate)
    data["layers"]["surface"]["machines"].append({"kind": "lamp", "tx": x, "ty": y})
    t = save.state_from_dict(data)
    assert "camp" in t.active.ruins_off
    assert not any(b.ruin and (b.tx, b.ty) in set(r.tiles) for b in t.base.blocks)
```

(O dict da máquina segue o formato do `machine_to_dict`; complete os campos obrigatórios que ele exigir.)

- [ ] **Step 2: Rode e veja falhar.** - [ ] **Step 3: Implemente.** - [ ] **Step 4: `uv run pytest`** → verde.

---

### Task 5: LOGs, desenho, E e mapa

**Files:**
- Modify: `game/config.py` (LOGs), `game/render.py`, `game/app.py`, `game/map_view.py`, `game/map_markers.py`
- Test: `tests/test_ruins.py`

**Interfaces:**
- Consumes: `world.ruin_terminals`, `GameState.ruin_of_tile`, `Layer.ruins_off`, `Machine.broken`.

Regras:
- **LOGs:** acrescente ao `LOGS`, num bloco `# LOGs das estruturas (v0.7 M1, aprovados pelo dono · docs/lore/logs_v07_rascunho.md)`, os 12 textos **exatos** do rascunho, na ordem dos índices 7..18. `LOG_DAYS += [1, 9, 22, 120, 152, 175, 198, 205, 219, 61, 209, 224]`. `LOG_TITLES += ["TERMINAL · ACAMPAMENTO"] * 3 + ["DIARIO · DRA. ILVES"] * 3 + ["TERMINAL · ESTACAO DE DERRETEDORES"] * 3 + ["TERMINAL · POSTO DE PERFURACAO"] * 3`. Teste: `len(LOGS) == len(LOG_DAYS) == len(LOG_TITLES) == 19`, todo texto começa com `f"Dia {LOG_DAYS[i]}."`, nenhum tem "→".
- **E:** `app.py`, onde trata `"wreck_log"` (abrir, texto do canto "[E] Ler terminal", contorno do alvo), trate `"ruin_log"` igual, chamando `self.show_log(self.state.world.ruin_terminals[tile])`.
- **Desenho do terminal:** depois de desenhar a parede da base no tile de um `ruin_terminals` (`Renderer.draw_base_wall`), desenhe por cima o quadro atual da tira `anim_terminal` (o mesmo que o terminal da caverna usa), alinhado à face da parede. Com o highlight `("ruin_log", tile)`, contorno claro no terminal (igual ao do módulo).
- **Máquina quebrada:** no desenho das máquinas, `broken` usa o quadro 0 (sem animação), escurecido (multiplica RGB por `C.RUIN_BROKEN_TINT = (120, 112, 108)`), sem luz, sem status flutuante, sem "+O2".
- **Mapa** (`map_view`): categoria nova `"ruin"` (`Entry("ruin", "ruin", *ruin.center, label)`), visível quando `seen_any(ruin.tiles)` e a ruína não está em `ruins_off`. Label `"Ruína"` até o player ler algum LOG dela (`state.logs_read & set(ruin.terminals.values())`), depois `ruin.name`. Entra em `FILTERS` (rótulo "Ruínas"), `PRIORITY` (2, como o destroço) e `DRAW_ORDER` (junto de `"wreck"`). Em `map_markers`: `"ruin"` desenha o pictograma do destroço (`WRECK`) com a cor `"#9fc2d8"` em `COLORS`.
- Terminal da ruína **não** entra no objetivo "Leia um terminal" além do que ele já conta (se o objetivo conta `logs_read`, já vale).

- [ ] **Step 1: Testes que falham** (`tests/test_ruins.py`):

```python
from game import config as C


def test_logs_7_to_18():
    assert len(C.LOGS) == len(C.LOG_DAYS) == len(C.LOG_TITLES) == 19
    for i, text in enumerate(C.LOGS):
        assert text.startswith(f"Dia {C.LOG_DAYS[i]}.")
        assert "→" not in text
    assert C.LOG_ORDER[0] == 7                                      # Dia 1 é o primeiro da história


def test_map_shows_ruin_after_seen():
    from game import map_view, save
    s = save.new_state(3)
    r = next(r for r in s.world.ruins if r.key == "lab")
    for t in r.tiles:
        s.active.explored.mark(*t)                                  # use o método real do Explored
    entries = map_view.entries(s, s.active)                         # use a função real que monta o mapa
    e = next(e for e in entries if e.kind == "ruin")
    assert e.label == "Ruína"
    s.logs_read.add(next(iter(r.terminals.values())))
    e = next(e for e in map_view.entries(s, s.active) if e.kind == "ruin")
    assert e.label == "Laboratório da Ilves"
```

(Ajuste `explored.mark` e `map_view.entries` aos nomes reais; o comportamento é o que vale.)

- [ ] **Step 2: Rode e veja falhar.** - [ ] **Step 3: Implemente.** - [ ] **Step 4: `uv run pytest`** → verde.

---

### Task 6: Prints, varredura do smoke e bíblia

**Files:**
- Create: `tools/dev/shot_v07_m1.py`
- Modify: `docs/GAME_BIBLE.md` (§16, subseção nova "Marco 1 · como ficou na implementação"), `tools/dev/smoke.py` (só se a varredura achar cena quebrada)

- [ ] **Step 1:** `tools/dev/shot_v07_m1.py`, no molde dos `tools/dev/shot_v06_*.py` (SDL dummy, sem janela): seed 3, pra cada uma das 4 ruínas, põe o player na frente da porta (na caverna, entra na camada e ilumina com F3/mapa revelado como os outros shots fazem) e salva `reports/dev/v07_m1/<key>.png`; mais um print do mapa aberto com os marcadores (`reports/dev/v07_m1/mapa.png`) e um da tela do LOG de uma ruína (`reports/dev/v07_m1/log.png`). Rode: `uv run python tools/dev/shot_v07_m1.py` e confira que os 6 PNGs saíram.
- [ ] **Step 2: Varredura do smoke:** `grep -n "build(\|can_place\|teleport\|player.x =\|enter_layer" tools/dev/smoke.py`. Pra cada cena que constrói ou anda numa coordenada fixa da superfície/caverna, confira se a seed dela agora tem ruína ali (`world.ruin_tiles`). Se tiver, mude a coordenada da cena. Anote no relatório o que mudou (ou "nada").
- [ ] **Step 3: Bíblia §16**, subseção "Marco 1 · como ficou na implementação (`game/ruins.py`, `game/ruin_plans/`, ...)": o formato da planta, as regras de lugar com os números, destruição, terminal reassentado, máquina quebrada, save (`ruin_salvaged`, `ruins_off`), o que mudou no smoke.
- [ ] **Step 4:** `uv run pytest` → verde. Relatório final pro gerente: tasks feitas, testes novos, testes antigos ajustados (e por quê), o que mudou no smoke, caminho dos prints.
