# v0.3 Marco 1 · Superfície · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Status (2026-10-12): executado inline pelo Dev, tarefas 1–8 concluídas (395 testes verdes, smoke ok).**
> **Neste projeto agentes NÃO commitam**: no lugar de "commit", cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** trocar a cratera 128×128 por um deserto aberto de 192×192 (a superfície), com o `GameState` organizado em camadas (superfície ativa; caverna já suportada pela estrutura), recursos soltos que reaparecem, rochas pequenas, morros, cordilheira, cratera fechada, poucos veios e save v6.

**Arquitetura:** o mapa continua sendo um `World` (mesma interface: `get/set/is_solid/vein_at/is_water/plant_at...`). A superfície é um `World` montado por `surface_gen.generate_surface(seed)`; a caverna futura é o `World.generate(seed)` de hoje. `layers.Layer` agrupa mundo + máquinas + recursos soltos de uma camada; o `GameState` guarda um dict de camadas e expõe `world`/`machines` da camada ativa (com setter, pra não quebrar quem já usa). Inventário, energia, Ti, objetivos e drones (só superfície) ficam globais.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

## Restrições globais (do pedido e da bíblia)
- Deserto **192×192** por seed; base (cápsula) no **centro**; zona de O₂ de **5 tiles**.
- Morros de **3–8 tiles** (parede mineável, arte de parede atual); **borda 2–3 tiles** intransponível e não minerável.
- **Cratera 3×3** a **15–20 tiles** da base, só visual/obstáculo no Marco 1 (ponto de extensão pra rampa).
- **3 a 5 veios**, a **≥ 35 tiles** da base, sem sobreposição.
- Rochas pequenas: 1 tile, quebram com a broca, **2–4 unidades**, não voltam.
- Soltos: ferro/silício/gelo, **1–3 unidades**, pega passando por cima ou E/clique no alcance, som `pickup`; reaparecem devagar (**4/min**), só **fora da tela** e a **≥ 12 tiles** da base, teto **120**; inventário cheio não pega e mostra o aviso existente.
- Areia nos 3 estágios (`sand_{stage}_{0..3}`); água e plantas como hoje (partes baixas por noise).
- Áudio `desert_wind` por cima do `amb_{stage}` na superfície, carregado de `assets/audio/` (sem arquivo = silêncio).
- **Save v6**, sem migração: save < v6 → título mostra "Save de uma versão antiga · comece um novo jogo" e desabilita Continuar; o arquivo antigo não é apagado (vira `slot1.v5.json` quando um jogo novo é salvo por cima).
- Sprites novos (`sand_*`, `rock_small`, `pickup_*`, `crater`, `crater_ramp`) com fallback em `game/art.py`, carregados sozinhos quando existirem em `assets/sprites/`.
- UI: nada de UW/UH/HOTBAR_X/Y fixos; mouse da UI via `app.mouse_ui`.
- Perf: frame médio no zoom 0,75 ≤ 16,7 ms.
- Não abrir janela real; não mexer em `saves/` nem `settings.json`; não commitar.

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | tamanhos (`SURFACE_W/H`, `CAVE_*`), base no centro (`BASE_TILE`, `POD_*`, `SPAWN_POS`, `BASE_CENTER`), tiles novos (`SAND`, `SMALL_IRON/SILICON/ICE`, `CRATER`), conjuntos (`WALL_TILES`, `FLAT_SOLIDS`, `FLOOR_TILES`, `TILE_RESOURCE`, `DROP_RANGE`), números do gerador e dos soltos, `DESERT_WIND_VOLUME`, `TRANSITION_FRONT_FAR` |
| `game/world.py` | `World.center`, `floor_kind`, `crater`; `is_wall`, `is_floor`; caverna usa `CAVE_CENTER` |
| `game/surface_gen.py` (novo) | `generate_surface(seed) -> World` (cache do mapa virgem + cópia) |
| `game/pickups.py` (novo) | `Pickup`, `Pickups` (geração inicial, reaparecimento, consulta por ponto, dados do save) |
| `game/layers.py` (novo) | `SURFACE`, `CAVE`, `Layer`, `make_surface(seed)`, `make_cave(seed)` |
| `game/systems.py` | `GameState` com camadas; quebra de rocha pequena; pegar solto (auto/E/clique); O₂ só na superfície; drones só na superfície; energia global |
| `game/objectives.py` | "Leia um terminal" vale como cumprido se não existe terminal em nenhuma camada; soltos e rochas contam como minerado |
| `game/transition.py` | `BASE_SOURCE` derivado da cápsula |
| `game/save.py` | v6 por camada, `probe()` com status `none/ok/old/broken`, `backup_old()` |
| `game/title.py` | Continuar desabilitado + aviso de save antigo |
| `game/art.py` | `sand`, `rock_small`, `pickup`, `crater` (fallbacks) |
| `game/render.py` | areia, rochas pequenas e cratera no chão, soltos como objetos, `is_wall` no lugar de `is_solid` onde é "parede alta", pod/zona só na superfície |
| `game/app.py` | E/clique pega solto, dicas, `set_wind`, título com save antigo, versão "v0.3" |
| `game/audio.py` | canal do vento (`set_wind`) |
| `tools/dev/balance_sim.py` | superfície: chão = `is_floor`, minério = `TILE_RESOURCE`, soltos como fonte, reaparecimento real |
| `tools/dev/smoke.py` | adaptado à superfície + prints novos + medição de perf no 0,75× |
| testes | novos: `test_surface_gen.py`, `test_pickups.py`, `test_layers.py`; adaptados: logic, drill, save, transition, objectives, polish_final, drones, logistics, station_slots |

---

### Task 1: config + World genérico (centro, chão, paredes altas × sólidos baixos)

**Files:** Modify `game/config.py`, `game/world.py`; Test `tests/test_layers.py` (parte do mundo), `tests/test_logic.py`, `tests/test_drill.py`

**Interfaces (produz):**
- `C.SURFACE_W = C.SURFACE_H = 192`, `C.CAVE_W = C.CAVE_H = 128` (`WORLD_W/H` = caverna), `C.CAVE_CENTER = (64, 64)`, `C.CAVE_HALL_RADIUS = 12`, `C.CAVE_SAFE_RADIUS = 8`
- `C.BASE_TILE = (96, 96)`; `C.POD_TILES = [(95, 95), (96, 95)]`; `C.POD_ANCHOR = (96*T, 96*T)`; `C.BASE_CENTER = (96*T, 96*T - 16)`; `C.SPAWN_POS = (96*T, 97*T + 8)`
- tiles: `SAND = 7`, `SMALL_IRON = 8`, `SMALL_SILICON = 9`, `SMALL_ICE = 10`, `CRATER = 11`
- `C.WALL_TILES` (paredes altas), `C.SMALL_ROCKS = {SMALL_IRON: "iron", ...}`, `C.FLAT_SOLIDS = set(SMALL_ROCKS) | {CRATER}`, `C.SOLID_TILES = WALL_TILES | FLAT_SOLIDS`, `C.FLOOR_TILES = {FLOOR, SAND}`, `C.TILE_RESOURCE = {**ORE_TILES, **SMALL_ROCKS}`, `C.DROP_RANGE = {k: (2, 4) for k in SMALL_ROCKS}` (o resto usa `DROP_MIN/MAX`), `C.MINE_TIME[small] = 0.7`
- `World.center: tuple[float, float]`, `World.floor_kind: int`, `World.crater: tuple[int, int] | None`, `World.is_wall(tx, ty)`, `World.is_floor(tx, ty)`; `is_water`/`plant_at` usam `is_floor` e `center`; `visual_tile_at` usa `is_wall`.

- [ ] **Step 1: testes que falham** (`tests/test_layers.py`)
```python
def test_flat_solids_are_solid_but_not_walls():
    w = World(seed=1, width=8, height=8)
    w.set(2, 2, C.SMALL_IRON); w.set(3, 3, C.CRATER); w.set(4, 4, C.ROCK); w.set(5, 5, C.SAND)
    assert w.is_solid(2, 2) and not w.is_wall(2, 2) and w.is_minable(2, 2)
    assert w.is_solid(3, 3) and not w.is_wall(3, 3) and not w.is_minable(3, 3)
    assert w.is_wall(4, 4) and w.is_floor(5, 5) and not w.is_solid(5, 5)

def test_visual_tile_ignores_flat_solids():
    w = World(seed=1, width=8, height=8)
    w.set(2, 3, C.SMALL_IRON)
    assert w.visual_tile_at(2 * C.TILE + 5, 2 * C.TILE + 20) == (2, 2)   # rocha pequena não tem topo elevado
```
- [ ] **Step 2:** `uv run pytest tests/test_layers.py` → FAIL (`C.SMALL_IRON` não existe).
- [ ] **Step 3:** implementar no config (constantes acima) e no world (`is_wall = get in WALL_TILES`, `is_floor = get in FLOOR_TILES`, `center`, `floor_kind`, `crater`; geração da caverna usa `CAVE_CENTER`/`CAVE_*_RADIUS` e bloqueia os 2 tiles acima do centro, onde a rampa vai ficar no Marco 2).
- [ ] **Step 4:** testes da caverna (`test_logic` mundo, `test_drill` geração) trocam `CRATER_CENTER`/`CRATER_SAFE_RADIUS` por `CAVE_CENTER`/`CAVE_SAFE_RADIUS` e `World.generate()` continua sendo a caverna. `uv run pytest tests/test_layers.py tests/test_drill.py -k "vein or world"` → PASS.

### Task 2: gerador do deserto (`surface_gen.py`)

**Files:** Create `game/surface_gen.py`, art fallbacks ficam na Task 6; Test `tests/test_surface_gen.py`

**Interfaces:**
- Consome: `World`, `value_noise`, `hash01`, `Vein`, constantes da Task 1.
- Produz: `generate_surface(seed: int = C.WORLD_SEED) -> World` (cópia nova a cada chamada; a geração pesada fica em cache por seed), `pristine_tiles(seed) -> list[list[int]]`.
- Config: `SURFACE_BORDER = (2, 3)`, `HILLS = (22, 30)`, `HILL_SIZE = (3, 8)`, `HILL_ORE_CHANCE = 0.12`, `SURFACE_CLEAR_RADIUS = 8`, `SURFACE_CRATER_DIST = (15, 20)`, `SURFACE_VEINS = (3, 5)`, `SURFACE_VEIN_MIN_DIST = 35`, `SMALL_ROCK_CHANCE`, `SMALL_ROCK_MIN_DIST = 6`.

- [ ] **Step 1: testes que falham**
```python
W = generate_surface(C.WORLD_SEED)

def test_size_seed_and_copy():
    assert (W.width, W.height) == (192, 192) and W.floor_kind == C.SAND
    assert generate_surface(C.WORLD_SEED).tiles == W.tiles
    assert generate_surface(C.WORLD_SEED + 1).tiles != W.tiles
    other = generate_surface(C.WORLD_SEED); other.set(50, 50, C.ROCK)
    assert generate_surface(C.WORLD_SEED).get(50, 50) == W.get(50, 50)   # cópia, não o cache

def test_border_is_bedrock_2_to_3_thick():
    for i in range(192):
        for x, y in ((i, 0), (i, 1), (0, i), (1, i), (i, 191), (i, 190), (191, i), (190, i)):
            assert W.get(x, y) == C.BEDROCK
    assert not W.is_minable(0, 50)
    # do lado de dentro de 3 tiles nunca é borda
    assert all(W.get(x, y) != C.BEDROCK for y in range(3, 189) for x in range(3, 189))

def test_base_area_is_clear_sand():
    for y in range(192):
        for x in range(192):
            if W.dist_from_center(x, y) < C.SURFACE_CLEAR_RADIUS:
                assert W.get(x, y) == C.SAND

def test_crater_3x3_between_15_and_20_tiles():
    tx, ty = W.crater
    assert all(W.get(tx + dx, ty + dy) == C.CRATER for dx in range(3) for dy in range(3))
    assert 15 <= W.dist_from_center(tx + 1, ty + 1) <= 20
    assert not W.is_minable(tx, ty)

def test_three_to_five_veins_far_and_apart():
    lo, hi = C.SURFACE_VEINS
    assert lo <= len(W.veins) <= hi
    assert {v.resource for v in W.veins} == set(C.RESOURCES)
    seen = set()
    for v in W.veins:
        assert W.dist_from_center(*v.tiles[0]) >= C.SURFACE_VEIN_MIN_DIST
        assert not set(v.tiles) & seen
        assert all(W.get(x, y) == C.SAND for x, y in v.tiles)
        assert all(W.get(x, v.ty + 2) == C.SAND for x in (v.tx, v.tx + 1))
        seen |= set(v.tiles)

def test_hills_small_rocks_and_reachability():
    rocks = [(x, y) for y in range(192) for x in range(192) if W.get(x, y) in C.SMALL_ROCKS]
    walls = [(x, y) for y in range(3, 189) for x in range(3, 189) if W.is_wall(x, y)]
    assert len(rocks) > 150 and walls                       # tem rocha pequena e morro
    assert all(W.dist_from_center(*t) >= C.SMALL_ROCK_MIN_DIST for t in rocks)
    reach = W.reachable_from(C.BASE_TILE)                   # rocha pequena conta como bloqueio aqui
    for v in W.veins:
        assert any(t in reach for t in v.tiles)
    tx, ty = W.crater
    assert any((tx + dx, ty + 3) in reach for dx in range(3))

def test_water_and_plants_still_appear():
    tiles = [(x, y) for y in range(192) for x in range(192)]
    assert not any(W.is_water(x, y, 1) for x, y in tiles)
    assert any(W.is_water(x, y, 2) for x, y in tiles)
    assert any(W.plant_at(x, y) for x, y in tiles)
```
- [ ] **Step 2:** FAIL (módulo não existe).
- [ ] **Step 3:** implementar na ordem: areia + `lowness` → borda (espessura 2 ou 3 por noise) → morros (blob de raio `size/2` + noise, rocha com chance de minério) → limpa o raio da base → cratera (ângulo/distância sorteados, área 5×5 limpa, 3×3 `CRATER`) → veios (ângulo/distância sorteados ≥ 35, 2×2 + linha de baixo + 1 de folga em areia, espaçamento 12, um de cada recurso primeiro) → rochas pequenas por `hash01` (fora do raio mínimo, fora de veio/cratera/linha de baixo do veio). Tudo com `random.Random(seed * 7919 + 101)`.
- [ ] **Step 4:** `uv run pytest tests/test_surface_gen.py` → PASS.

### Task 3: recursos soltos (`pickups.py`)

**Files:** Create `game/pickups.py`; Test `tests/test_pickups.py`

**Interfaces:**
- Config: `PICKUP_AMOUNT = (1, 3)`, `PICKUP_START = 70`, `PICKUP_MAX = 120`, `PICKUP_RESPAWN = 15.0` (s por solto = 4/min), `PICKUP_BASE_DIST = 12` (tiles, reaparecimento), `PICKUP_START_BASE_DIST = 6`, `PICKUP_HIDDEN = (21, 13)` (meia-tela em tiles no zoom 0,75 + folga), `PICKUP_AUTO_RADIUS = 12` (px), `PICKUP_REACH = 56` (px, E/clique), `PICKUP_HIT = 10` (px, mouse), `PICKUP_WEIGHTS = {"iron": 0.45, "silicon": 0.3, "ice": 0.25}`, `VOLUME["pickup_loose"]` não precisa (usa `pickup`).
- Produz:
```python
@dataclass
class Pickup:
    resource: str; amount: int; x: float; y: float        # (x, y) = centro do chão, px do mundo
    @property
    def tile(self) -> tuple[int, int]

class Pickups:
    items: list[Pickup]; timer: float
    @classmethod
    def generate(cls, world, seed: int) -> "Pickups"
    def update(self, world, rng, dt: float, player_xy) -> list[Pickup]      # reaparecimento, devolve os novos
    def touching(self, x: float, y: float, radius: float = C.PICKUP_AUTO_RADIUS) -> list[Pickup]
    def at_point(self, x: float, y: float) -> Pickup | None
    def remove(self, p: Pickup) -> None
    def to_data(self) -> dict ; @classmethod from_data(cls, data) -> "Pickups"
def hidden_from(player_xy, tx, ty) -> bool
def can_spawn(world, tx, ty, min_base: float) -> bool
```
- [ ] **Step 1: testes que falham**
```python
def test_generate_is_deterministic_and_on_free_sand():
    w = generate_surface(); a = Pickups.generate(w, 7); b = Pickups.generate(w, 7)
    assert [(p.resource, p.amount, p.x, p.y) for p in a.items] == [(p.resource, p.amount, p.x, p.y) for p in b.items]
    assert len(a.items) == C.PICKUP_START
    for p in a.items:
        assert C.PICKUP_AMOUNT[0] <= p.amount <= C.PICKUP_AMOUNT[1] and p.resource in C.RESOURCES
        assert w.is_floor(*p.tile) and w.vein_at(*p.tile) is None
    assert len({p.tile for p in a.items}) == len(a.items)

def test_respawn_rate_cap_offscreen_and_far_from_base():
    w = generate_surface(); pk = Pickups([], 0.0); rng = random.Random(1); player = C.SPAWN_POS
    new = pk.update(w, rng, 60.0, player)
    assert len(new) == round(60 / C.PICKUP_RESPAWN)
    for p in new:
        assert hidden_from(player, *p.tile) and w.dist_from_center(*p.tile) >= C.PICKUP_BASE_DIST
    pk.update(w, rng, 10_000.0, player)
    assert len(pk.items) == C.PICKUP_MAX

def test_touching_and_at_point():
    pk = Pickups([Pickup("iron", 2, 100.0, 100.0)], 0.0)
    assert pk.touching(105, 104) and not pk.touching(130, 100)
    assert pk.at_point(100, 96) is pk.items[0] and pk.at_point(140, 140) is None

def test_data_roundtrip():
    pk = Pickups([Pickup("ice", 3, 10.5, 20.0)], 4.25)
    back = Pickups.from_data(pk.to_data())
    assert back.items == pk.items and back.timer == 4.25
```
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** PASS.

### Task 4: camadas no `GameState` (+ rochas pequenas e soltos no jogo)

**Files:** Create `game/layers.py`; Modify `game/systems.py`, `game/objectives.py`, `game/transition.py`; Test `tests/test_layers.py`, `tests/test_pickups.py`

**Interfaces:**
- `layers.SURFACE = "surface"`, `layers.CAVE = "cave"`
```python
@dataclass
class Layer:
    key: str; world: World; machines: list = field(default_factory=list); pickups: Pickups | None = None
def make_surface(seed: int) -> Layer
def make_cave(seed: int) -> Layer
```
- `GameState.layers: dict[str, Layer]`, `GameState.layer: str`, propriedades `active`, `surface`, `world` (com setter), `machines` (com setter), `pickups`, `all_machines`; `enter_layer(key, pos=None)` (cria a caverna se precisar; ponto de extensão do Marco 2); `in_base_zone()` só na superfície; acordar do desmaio volta pra superfície.
- `power`/`ti_rate`/`_update_machines` olham `all_machines`; drones usam só `surface.machines`; `base_chests()` só baús da superfície.
- `_break_tile` vira `floor_kind`, drop por `TILE_RESOURCE` e `DROP_RANGE`.
- `take_pickup(p) -> int` (pega o que couber, conta em `mined_total`, evento `("pickup", tile, resource, n)`; nada coube → `("inv_full",)`), auto-pickup no `update` (aviso de cheio uma vez por toque), reaparecimento real no `update` (`_update_pickups(dt)`).
- `interactable_at` devolve `("pickup", p)`; `in_reach("pickup", p)` pelo `PICKUP_REACH`; `interaction()` inclui o solto mais perto.
- Objetivo "Leia um terminal": `len(logs_read) >= 1 or not any(l.world.terminals for l in layers.values())`.
- `transition.BASE_SOURCE = (C.BASE_TILE[0], C.POD_TILES[0][1])`; `TRANSITION_FRONT_FAR = 150` (o mapa é maior).

- [ ] **Step 1: testes que falham**
```python
def test_game_starts_on_the_surface_with_layers():
    g = GameState(rng=random.Random(1))
    assert g.layer == SURFACE and set(g.layers) == {SURFACE}
    assert g.world is g.layers[SURFACE].world and g.world.width == 192
    assert g.in_base_zone() and g.pickups is g.layers[SURFACE].pickups

def test_cave_layer_has_its_own_world_and_machines_but_global_energy():
    g = GameState(rng=random.Random(1))
    g.machines.append(Machine("solar", 90, 90))
    g.enter_layer(CAVE)
    assert g.world.width == 128 and g.machines == [] and not g.in_base_zone()
    g.machines.append(Machine("o2", 60, 60))
    assert g.power.produced == C.POD_POWER + 4 and g.ti_rate == 3      # energia e Ti somam as duas camadas
    g._update_machines(1.0)
    assert g.indices["o2"] == pytest.approx(3)
    g.enter_layer(SURFACE)
    assert [m.kind for m in g.machines] == ["solar"]

def test_faint_in_cave_wakes_up_on_surface():
    g = GameState(rng=random.Random(1)); g.enter_layer(CAVE); g._faint()
    for _ in range(int(C.FAINT_RESPAWN_AT * 60) + 2): g.update(1 / 60, Controls())
    assert g.layer == SURFACE and (g.player.x, g.player.y) == C.SPAWN_POS

def test_small_rock_drops_2_to_4_and_becomes_sand():
    for seed in range(15):
        g = GameState(rng=random.Random(seed)); px, py = g.player.tile
        g.world.set(px + 1, py, C.SMALL_SILICON)
        for _ in range(60): g.update(1 / 60, Controls(mine_tile=(px + 1, py)))
        assert g.world.get(px + 1, py) == C.SAND and 2 <= g.inventory.count("silicon") <= 4

def test_walk_over_pickup_collects_it(...)
def test_full_inventory_keeps_pickup_and_warns_once(...)
def test_e_and_click_take_pickup_in_reach(...)
```
- [ ] **Step 2:** FAIL → **Step 3:** implementar → **Step 4:** adaptar testes que dependiam do mapa antigo (posições fixas viram relativas a `C.BASE_TILE`; terminais vão pra camada caverna com `game.enter_layer(CAVE)`), `uv run pytest` → PASS.

### Task 5: save v6 + título com save antigo

**Files:** Modify `game/save.py`, `game/title.py`, `game/app.py`; Test `tests/test_save.py` (e remove os testes de migração v1→v5 de `test_save.py`, `test_drones.py`, `test_station_slots.py`, `test_logistics.py`, substituídos por "save antigo é reconhecido como antigo")

**Interfaces:**
- `SAVE_VERSION = 6`; formato `{"version", "seed", "layer", "layers": {key: {"changed_tiles", "machines", "pickups"}}, "player", "inventory", "progress"}`.
- `save.probe(path=None) -> tuple[str, GameState | None]` com `"none" | "ok" | "old" | "broken"`; `load_game` = `probe(...)[1]`; `class OldSaveError(SaveError)`; `save.backup_old(path=None) -> Path | None` (renomeia pra `slot1.v{N}.json`).
- `TitleScreen.open(saved, old: bool = False)`; com `old`, a linha "Continuar" aparece apagada, não seleciona, e o aviso "Save de uma versão antiga · comece um novo jogo" aparece embaixo do menu.

- [ ] **Step 1: testes**
```python
@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_old_versions_are_reported_as_old_and_kept(tmp_path, version):
    path = tmp_path / "slot1.json"; path.write_text(json.dumps({"version": version, "seed": 7}), encoding="utf-8")
    status, state = save.probe(path)
    assert status == "old" and state is None and path.exists()
    backup = save.backup_old(path)
    assert backup.name == f"slot1.v{version}.json" and backup.exists() and not path.exists()

def test_layers_pickups_and_broken_rocks_roundtrip(tmp_path): ...
def test_title_old_save_disables_continue(): (TitleScreen com ui falso)
```
- [ ] **Step 2–4:** FAIL → implementar → PASS.

### Task 6: render, arte de fallback, app e áudio

**Files:** Modify `game/art.py`, `game/render.py`, `game/app.py`, `game/audio.py`, `game/ui.py` (se precisar); Test `tests/test_depth.py` (build_draw_list ignora sólido baixo), `tests/test_audio_rules.py` (vento só na superfície)

**Interfaces:**
- `art.sand(stage, variant)`, `art.rock_small(resource)`, `art.pickup(resource)`, `art.crater(open_ramp: bool = False)`.
- `Renderer.draw_floors` desenha areia (`sand_{stage}_{v}`), rocha pequena (`rock_small` + pontinho do minério) e a cratera (`crater`, 96×96, no tile de cima à esquerda) no chão; `build_draw_list` usa `is_wall`; soltos entram em `collect_objects` (contorno quando é o alvo do E); pod, zona e luz da cápsula só se `state.layer == SURFACE`.
- `Audio.set_wind(on: bool)` (canal 9, `C.DESERT_WIND_VOLUME`), `App.update_ambient_sounds` liga na superfície.
- `App`: E/clique no solto, dicas ("[E] Pegar 2 ferro", "Cratera · fechada por enquanto"), título com save antigo + `backup_old` ao começar jogo novo, legenda "Hesper · v0.3".

- [ ] **Step 1:** teste de profundidade:
```python
def test_flat_solids_are_not_walls_in_draw_list():
    w = World(seed=1, width=10, height=10); w.set(3, 3, C.SMALL_ICE); w.set(4, 3, C.ROCK)
    order = build_draw_list(w, [], 0, 9, 0, 9)
    assert ("wall", 4, 3) in order and ("wall", 3, 3) not in order
```
- [ ] **Step 2–4:** FAIL → implementar → PASS; `uv run pytest`.

### Task 7: balance sim na superfície

**Files:** Modify `tools/dev/balance_sim.py`; Test `tests/test_balance_sim.py`

- chão = `world.is_floor`, minério = `C.TILE_RESOURCE` (rochas pequenas e minério dos morros), soltos viram fonte (`pickup` a 1 tile, 0,3 s pra pegar via `take_pickup`), o `_produce` roda `pickups.update` (regra real) e atualiza os contadores de soltos.
- `_next_site` e `_station_spots` com `is_floor` e `C.BASE_TILE`.
- [ ] Rodar `uv run python tools/dev/balance_sim.py --current`, anotar os números em `reports/dev/balance.md` (seção v0.3 Marco 1). Se não terminar, propor ajuste mínimo temporário e reportar.

### Task 8: smoke, prints, perf, bíblia e README

- [ ] Adaptar `tools/dev/smoke.py` (posições relativas à base, terminal na caverna criada por `enter_layer(CAVE)`).
- [ ] Prints novos: `superficie_base.png`, `superficie_deserto.png`, `superficie_cratera.png`, `superficie_veio.png`, `superficie_mapa.png` (mapa inteiro reduzido), `titulo_save_antigo.png`.
- [ ] Perf: frame médio no deserto no zoom 0,75 ≤ 16,7 ms (imprimir).
- [ ] Olhar todos os prints com Read e corrigir o feio.
- [ ] Bíblia §9 (números de implementação) e README (controles e módulos novos).
- [ ] `uv run pytest` verde.

---

## Auto-revisão
- Cobertura: camadas (T4), gerador (T2), soltos (T3/T4), terraformação na areia (T6: `sand_{stage}` + StageMap), vento (T6), save v6 + título (T5), placeholders (T6), sim (T7), smoke/perf/docs (T8). Drones só na superfície (T4). Fabricador puxa dos baús da base (T4, `base_chests` da superfície).
- Nomes consistentes: `generate_surface`, `Pickups.update/touching/at_point`, `Layer`, `enter_layer`, `probe`, `backup_old`, `set_wind`.
