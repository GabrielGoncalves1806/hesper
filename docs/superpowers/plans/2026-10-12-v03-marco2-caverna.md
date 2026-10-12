# v0.3 Marco 2 · Caverna · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: no lugar de "commit", cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** abrir a caverna: a cratera da superfície vira rampa (E desce com fade), a caverna 128×128 ganha rampa de subida, minério mais abundante, visual fixo de névoa, escuridão com `game/lighting.py` (lanterna, luminária nova, luz de máquina, brilho de minério), áudio de caverna, objetivos novos, save, simulador e smoke.

**Arquitetura:** a rampa usa a mesma ideia nas duas camadas: `world.crater` é o canto de um 3×3 de tiles `CRATER` (sólido baixo, não minera). Na superfície é a cratera (já existe); na caverna o gerador põe o 3×3 no meio do salão (rampa de subida). As regras de troca ficam em `layers.py` (alvo do E, ponto de chegada) e no `GameState` (viagem com fade, como o desmaio: `state.ramp`). O render escolhe o modo pela camada: superfície = luz/clima de hoje; caverna = estágio visual fixo "mist", sem água/plantas, `Lighting(banding=True)` + glints.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

## Restrições globais (do pedido e da bíblia)
- Rampa: mouse em cima + no alcance + E (ou a mais perto no alcance, como terminal/baú) → fade preto com "Descendo..." / "Subindo...". Alvo do E = tile (tx+1, ty+2) do 3×3; chega/sai em (tx+1, ty+3).
- Caverna 128×128 (gerador do `world.py`), 3 terminais, salão aberto em volta da rampa, minério **mais abundante** que hoje e mais rico longe da rampa, veios comuns. Visual fixo névoa (`floor_mist_*`, `wall_mist_*`, `wall_face_mist`), sem água, sem plantas, sem clima.
- O₂: sem zona na caverna; 100 s fora; desmaio na caverna acorda na cápsula.
- Escuridão só na caverna, `Lighting(cell=4, banding=True)`. Lanterna (facing do player), luminária `lamp` (1 Fe + 1 Si, Ti 0, raio ~5, sem energia, qualquer camada), máquinas com luz fraca, `ore_glints`. HUD/floaters por cima. Na caverna NÃO chamar `draw_lighting`/`draw_atmosphere`.
- Drill na caverna funciona (coleta à mão); drones só na superfície; fabricador só puxa dos baús da base; energia global.
- Áudio: `amb_cave` no lugar de `amb_{stage}` + vento na caverna (crossfade); `ramp_down`/`ramp_up`; `lamp_place`. Sem arquivo: silêncio (amb_cave ausente = mantém o `amb_{stage}`).
- Sprites pendentes (`lamp`, `icon_lamp`, `cave_ramp_up`) com fallback em `art.py`; `crater_ramp` já é oficial.
- Save v6 compatível (campo novo com default); NÃO mexer em `saves/` nem `settings.json`.
- UI: nada de UW/UH/HOTBAR_X/Y fixos; mouse da UI via `app.mouse_ui`. Não mexer em biomas.
- Perf: caverna escura com 30 luminárias, zoom 0,75, média < 16,7 ms.
- Não abrir janela real; não commitar; não mexer em assets/, tools/sprites, tools/audio, reports/design, reports/audio.

## Decisões (marcadas pro dono revisar)
- **[revisar]** Luminária numa aba nova **"Luz"** do fabricador (cabe com o padding das abas 12→10 px). O Marco 3 traz a "luminária melhor", que vai pra mesma aba.
- **[revisar]** Objetivos novos logo depois de "Fabrique um baú": "Desça na caverna pela cratera [E]" e "Coloque uma luminária". "Leia um terminal" deixa de ser pulado (a caverna sempre existe agora).
- E na rampa segue o padrão do jogo: o do mouse (no alcance) ou, sem mouse em nada, o mais perto no alcance (64 px do pé até a borda de baixo da rampa).
- Estação de drones não pode ser colocada na caverna (aviso na dica).
- Sem `amb_cave.wav`, a caverna mantém o ambiente do estágio (sem vento).
- Lanterna, rampa de subida (luz fria de cima, ~3,5 tiles) e terminais (verde, ~2 tiles) iluminam a caverna; baú não tem luz.

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | `CAVE_RAMP` (canto), `RAMP_REACH`, `RAMP_SWITCH_AT`, `RAMP_DURATION`, `CAVE_ORE_THRESHOLD`, máquina `lamp`, aba "Luz", volumes `ramp_down/ramp_up/lamp_place` |
| `game/world.py` | `terraforms` (sem água/plantas na caverna), rampa 3×3 no salão, minério mais abundante |
| `game/layers.py` | `ramp_target(world)`, `ramp_arrival(world)`, `ramp_tiles(world)`, `other_layer(key)` |
| `game/systems.py` | `RampTrip`, `start_ramp`, update da viagem, interação "ramp", lamp (contador, rect), drone_station proibida na caverna, `safe_point()` |
| `game/player.py` | `facing` (alias de `direction`) |
| `game/objectives.py` | 2 objetivos novos; terminal sem atalho |
| `game/save.py` | `lamps_placed` (default 0) |
| `game/art.py` | `lamp()`, `lamp_icon()`, `cave_ramp_up()` |
| `game/render.py` | modo caverna (estágio fixo, Lighting, glints, `cave_lights`), rampa aberta, luminária, contorno da rampa |
| `game/ui.py` | aba "Luz" (padding), `draw_ramp_fade`, seta do O₂ pra rampa, controles |
| `game/audio.py` | `has()`, `crossfade_to()`, `_crossfade` não reinicia o mesmo loop |
| `game/app.py` | E na rampa, dicas, sons, ambiente da caverna, limpa floaters na troca, fade |
| `tools/dev/balance_sim.py` | estratégia "caverna" (minera na caverna, drills nos veios da caverna) |
| `tools/dev/smoke.py` | prints da caverna e perf com 30 luminárias |
| testes | novo `tests/test_cave.py`; ajustes em test_logic, test_objectives, test_fabricator, test_save, test_balance_sim |

---

### Task 1: caverna gerada com rampa, sem terraformação e com mais minério

**Files:** Modify `game/config.py`, `game/world.py`, `game/layers.py`; Test `tests/test_cave.py`, `tests/test_logic.py`

**Interfaces (produz):**
- `C.CAVE_RAMP = (CAVE_CENTER[0] - 1, CAVE_CENTER[1] - 3)` (canto do 3×3: tiles (63..65, 61..63); chegada (64, 64))
- `C.CAVE_ORE_THRESHOLD = (0.60, 0.15)` → limiar = `0.60 - 0.15 * far` (hoje 0.66 − 0.11·far)
- `World.terraforms: bool` (True no default; `World.generate` põe False). `is_water` → False e `plant_at` → None quando False.
- `World.generate` põe `world.crater = C.CAVE_RAMP` e os 9 tiles = `C.CRATER`.
- `layers.ramp_tiles(world) -> list[(x, y)]`, `layers.ramp_target(world) -> (tx+1, ty+2)`, `layers.ramp_arrival(world) -> (px, py)` = `((tx+1.5)*T, (ty+3)*T + 24)`, `layers.other_layer(key)`.

- [ ] **Step 1: testes que falham** (`tests/test_cave.py`)
```python
from game import config as C
from game import layers
from game.world import World

W = World.generate(C.WORLD_SEED)

def test_cave_has_ramp_up_in_the_open_hall():
    tx, ty = W.crater
    assert (tx, ty) == C.CAVE_RAMP
    assert all(W.get(x, y) == C.CRATER for x, y in layers.ramp_tiles(W))
    assert layers.ramp_target(W) == (tx + 1, ty + 2)
    ax, ay = layers.ramp_arrival(W)
    arrival = (int(ax // C.TILE), int((ay - 1) // C.TILE))
    assert arrival == (tx + 1, ty + 3) and W.is_floor(*arrival)
    hall = [(x, y) for y in range(128) for x in range(128) if W.dist_from_center(x, y) < C.CAVE_SAFE_RADIUS]
    assert all(W.is_floor(x, y) for x, y in hall if (x, y) not in layers.ramp_tiles(W))

def test_cave_never_terraforms():
    tiles = [(x, y) for y in range(128) for x in range(128)]
    assert not W.terraforms
    assert not any(W.is_water(x, y, 3) for x, y in tiles) and not any(W.plant_at(x, y) for x, y in tiles)

def test_cave_ore_is_more_abundant_and_richer_far():
    def ratio(lo, hi):
        cells = [W.tiles[y][x] for y in range(128) for x in range(128)
                 if lo <= W.dist_from_center(x, y) < hi and not W.is_floor(x, y)]
        return sum(t in C.ORE_TILES for t in cells) / len(cells)
    assert ratio(40, 60) > ratio(13, 22) > 0.15
    assert ratio(13, 60) > 0.30            # hoje ~0,22: mais abundante
    assert len(W.veins) >= 15             # veios comuns

def test_other_layer():
    assert layers.other_layer(layers.SURFACE) == layers.CAVE and layers.other_layer(layers.CAVE) == layers.SURFACE
```
- [ ] **Step 2:** `uv run pytest tests/test_cave.py` → FAIL (`CAVE_RAMP`/`ramp_tiles` não existem).
- [ ] **Step 3:** implementar: config; em `World.generate`, depois de `_pick_tile`, `world.crater = C.CAVE_RAMP` e `set` dos 9 tiles; `_place_veins` bloqueia ramp_tiles + 2 de folga; `_pick_tile` usa `CAVE_ORE_THRESHOLD`; `terraforms` em `_low_wet` e `plant_at`. Medir a razão atual antes (`ratio(13,60)`), e calibrar o limiar.
- [ ] **Step 4:** ajustar `tests/test_logic.py`: `test_crater_center_is_free` ignora os tiles da rampa; `test_no_water_in_stage1_but_water_later` vira "caverna sem água" (a água da superfície já é testada em `test_water.py`). `uv run pytest` → PASS.

### Task 2: viagem pela rampa no GameState

**Files:** Modify `game/config.py`, `game/systems.py`, `game/player.py`; Test `tests/test_cave.py`

**Interfaces:**
- `C.RAMP_REACH = 64`, `C.RAMP_SWITCH_AT = 0.6`, `C.RAMP_DURATION = 1.3` (s)
- `@dataclass RampTrip: to: str; time: float = 0.0`
- `GameState.ramp: RampTrip | None`; `GameState.ramp_distance() -> float` (pé até `((tx+1.5)*T, (ty+3)*T)`); `GameState.start_ramp() -> bool` (evento `("ramp", to)`); no `update`, com `ramp` ativo o player não anda/minera; em `RAMP_SWITCH_AT` faz `enter_layer(to, ramp_arrival(mundo destino))` + evento `("layer", to)`; em `RAMP_DURATION` vira None. Desmaio cancela a viagem.
- `interactable_at` devolve `("ramp", corner)` em cima de um tile do 3×3; `in_reach("ramp", _)` = `ramp_distance() <= RAMP_REACH`; `interaction()` inclui a rampa entre as opções.
- `GameState.safe_point() -> (x, y, label)`: superfície → `(*BASE_CENTER, "BASE")`; caverna → centro de baixo da rampa, `"RAMPA"`.
- `Player.facing` (property = `direction`).
- `enter_layer` gera a caverna na hora (já existe).

- [ ] **Step 1: testes**
```python
import random
from game.layers import CAVE, SURFACE
from game.systems import Controls, GameState

DT = 1 / 60
def run(g, s, c=None):
    for _ in range(round(s / DT)):
        g.update(DT, c or Controls())

def at_crater(g):
    tx, ty = g.world.crater
    g.player.x, g.player.y = layers.ramp_arrival(g.world)
    return tx, ty

def test_ramp_is_interactable_and_in_reach():
    g = GameState(rng=random.Random(1))
    tx, ty = at_crater(g)
    hover = g.interactable_at((tx + 1.5) * C.TILE, (ty + 2.5) * C.TILE)
    assert hover == ("ramp", (tx, ty)) and g.in_reach(*hover)
    assert g.interaction() == ("ramp", (tx, ty))
    g.player.x += 6 * C.TILE
    assert not g.in_reach(*hover)

def test_going_down_and_up():
    g = GameState(rng=random.Random(1))
    at_crater(g)
    assert g.start_ramp() and ("ramp", CAVE) in g.events
    run(g, C.RAMP_SWITCH_AT / 2, Controls(move_x=1))
    assert g.layer == SURFACE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)   # parado no fade
    run(g, C.RAMP_SWITCH_AT / 2 + 0.05)
    assert g.layer == CAVE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)
    run(g, C.RAMP_DURATION)
    assert g.ramp is None
    assert g.start_ramp()
    run(g, C.RAMP_DURATION + 0.05)
    assert g.layer == SURFACE and (g.player.x, g.player.y) == layers.ramp_arrival(g.world)

def test_cannot_ramp_from_far_or_twice():
    g = GameState(rng=random.Random(1))
    assert not g.start_ramp()
    at_crater(g)
    assert g.start_ramp() and not g.start_ramp()

def test_safe_point_points_to_the_ramp_in_the_cave():
    g = GameState(rng=random.Random(1))
    assert g.safe_point() == (*C.BASE_CENTER, "BASE")
    g.enter_layer(CAVE)
    tx, ty = g.world.crater
    assert g.safe_point() == ((tx + 1.5) * C.TILE, (ty + 3) * C.TILE, "RAMPA")

def test_player_facing_follows_direction():
    g = GameState(rng=random.Random(1))
    run(g, 0.1, Controls(move_x=-1))
    assert g.player.facing == "left"
```
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `uv run pytest` → PASS.

### Task 3: luminária (item, regras, objetivos, save) e drone na caverna

**Files:** Modify `game/config.py`, `game/systems.py`, `game/objectives.py`, `game/save.py`; Test `tests/test_cave.py`, `tests/test_objectives.py`, `tests/test_fabricator.py`, `tests/test_save.py`

**Interfaces:**
- `C.MACHINES["lamp"] = MachineType("lamp", "Luminária", "luz na caverna", {"iron": 1, "silicon": 1}, None, 0, 0, "lamp")`, `C.LAMP_SPRITE_SIZE = (16, 32)`, aba `("light", "Luz")`, `MACHINE_CATEGORY["lamp"] = "light"`.
- `Machine.is_lamp`; `rect` da luminária = `(tx*T+10, ty*T+20, 12, 12)`; `sprite_rect` 16×32.
- `GameState.lamps_placed` (só cresce, salvo em `progress` com `.get(..., 0)`); `GameState.visited_cave` = `CAVE in layers`.
- `can_place("drone_station", ...)` False na caverna.
- Objetivos: depois de "Fabrique um baú" → `"Desça na caverna pela cratera [E]"` (`CAVE in s.layers`), `"Coloque uma luminária"` (`s.lamps_placed >= 1`); "Leia um terminal" = `len(s.logs_read) >= 1`.

- [ ] **Step 1: testes**
```python
def test_lamp_recipe_is_cheap_unlocked_and_unpowered():
    g = GameState(rng=random.Random(1))
    lamp = C.MACHINES["lamp"]
    assert lamp.cost == {"iron": 1, "silicon": 1} and lamp.unlock_ti == 0 and lamp.index is None
    assert C.MACHINE_CATEGORY["lamp"] == "light" and ("light", "Luz") in C.FAB_TABS
    from game import energy
    assert energy.machine_use("lamp") == 0

def test_lamp_goes_on_both_layers_and_counts():
    g = GameState(rng=random.Random(1))
    give(g, lamp=2)
    px, py = g.player.tile
    assert g.place("lamp", (px + 2, py)) and g.lamps_placed == 1
    g.enter_layer(CAVE, layers.ramp_arrival(layers.MAKERS[CAVE](g.seed).world))
    px, py = g.player.tile
    assert g.place("lamp", (px + 2, py)) and g.lamps_placed == 2

def test_no_drone_station_in_the_cave():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE, ...)  # chegada da rampa
    give(g, drone_station=1)
    px, py = g.player.tile
    assert not g.can_place("drone_station", (px + 2, py - 3))
```
Objetivos: atualizar a sequência de `test_objectives` (inserir os dois novos e o "Leia um terminal" volta); trocar `test_terminal_objective_only_when_a_terminal_exists` por um teste de que o objetivo só sai lendo. Save: `lamps_placed` na ida e volta e save sem o campo carrega com 0. Fabricador: `set(MACHINE_CATEGORY) == set(MACHINE_ORDER)` já cobre a aba.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `uv run pytest` → PASS.

### Task 4: render da caverna (estágio fixo, escuridão, luminária, rampas)

**Files:** Modify `game/art.py`, `game/render.py`, `game/ui.py`; Test `tests/test_cave.py`

**Interfaces:**
- `art.lamp() -> Surface 16×32`, `art.lamp_icon() -> 16×16`, `art.cave_ramp_up() -> 96×96`.
- `render.cave_lights(state) -> list[LightSource]`: lanterna `helmet_lamp(p.x, p.y - 18, p.facing)`, luz da rampa de subida (fria, 3,5 tiles), `lamp(tx, ty)` por luminária, `machine_light` por máquina (menos baú e luminária; drill cheia não), luz verde fraca dos terminais.
- `Renderer.surface_map` (o StageMap de hoje) e `Renderer.cave_map` (StageMap fixo no estágio 2); `self.stage_map` aponta pro da camada no `draw`.
- `Renderer.lighting = Lighting(cell=4, banding=True)`.
- Caverna no `draw`: chão/paredes → partículas → `lighting.apply` → glints → fantasma de colocação → status das máquinas. Superfície: igual a hoje.
- `crater_surface(layer)`: superfície `crater_ramp` (fallback `art.crater(open_ramp=True)`); caverna `cave_ramp_up` (fallback `art.cave_ramp_up`). Contorno quando `highlight == ("ramp", corner)`.
- Luminária no `draw_machine`/`machine_preview`/`item_icon` (`icon_lamp` com fallback); na superfície ganha um brilho no `draw_lighting`.
- UI: abas com padding 10; `draw_o2_critical` usa `state.safe_point()` ("Volte para a base"/"Suba pela rampa"); `draw_ramp_fade(state)` (preto + "Descendo..."/"Subindo..."); linha "E · na cratera: descer/subir" nos controles.

- [ ] **Step 1: testes**
```python
def test_cave_lights_has_helmet_lamps_and_machines():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE, layers.ramp_arrival(...))
    g.machines += [Machine("lamp", 60, 70), Machine("lamp", 62, 70), Machine("o2", 58, 70), Machine("chest", 57, 70)]
    lights = cave_lights(g)
    assert lights[0].radius == 4 * C.TILE                      # lanterna primeiro
    assert sum(L.radius == 5 * C.TILE for L in lights) == 2      # 2 luminárias
    assert len(lights) == 1 + 1 + 2 + 1 + 3                    # + rampa + o2 + 3 terminais (baú não)

def test_cave_fallback_sprites_have_contract_sizes():
    assert art.lamp().get_size() == (16, 32) and art.lamp_icon().get_size() == (16, 16)
    assert art.cave_ramp_up().get_size() == (96, 96)
```
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `uv run pytest` → PASS.

### Task 5: App (E na rampa, dicas, fade, áudio da caverna)

**Files:** Modify `game/audio.py`, `game/app.py`; Test `tests/test_audio_rules.py`

**Interfaces:**
- `audio.ambient_for(layer, stage_key, has_cave) -> str` (pura): caverna com `amb_cave` → "cave", senão `stage_key`.
- `Audio.has(name) -> bool`; `Audio.crossfade_to(key, ms=1500)`; `_crossfade` com a mesma chave só restaura o nível.
- App: E com alvo "ramp" → `state.start_ramp()`; evento `("ramp", to)` → `ramp_down`/`ramp_up`; `("layer", _)` → limpa floaters/partículas, larga a máquina na mão; `("place", "lamp", _)` → `lamp_place` (ou `place` sem o arquivo); ambiente segue `ambient_for` (crossfade de 1,5 s); stage_up manda a chave desejada; dicas: "[E] Descer pela rampa", "[E] Subir pela rampa", "Cratera · chegue mais perto pra descer", "Rampa · chegue mais perto pra subir", "Drones só funcionam na superfície"; `draw` chama `ui.draw_ramp_fade` por cima do HUD.

- [ ] **Step 1: teste**
```python
def test_ambient_for_layer():
    assert audio.ambient_for("cave", "mist", True) == "cave"
    assert audio.ambient_for("cave", "mist", False) == "mist"
    assert audio.ambient_for("surface", "green", True) == "green"
```
- [ ] **Step 2–4:** FAIL → implementar → `uv run pytest` PASS.

### Task 6: smoke da caverna, simulador, docs

**Files:** Modify `tools/dev/smoke.py`, `tools/dev/balance_sim.py`, `tests/test_balance_sim.py`, `docs/GAME_BIBLE.md`, `README.md`

- Smoke `check_cave(bot)`: mouse na cratera (`caverna_rampa_superficie.png`, dica "[E] Descer pela rampa"), E e print no meio do fade (`caverna_transicao.png`), chegada (`caverna_chegada.png`), 6 luminárias + minério à vista (`caverna_escura.png`), minerando (`caverna_mineracao.png`), mapa 128×128 reduzido (`caverna_mapa.png`), perf com 30 luminárias no zoom 0,75 (assert < 16,7 ms), sobe pela rampa e confere a superfície. Atualizar o assert antigo da cratera ("Cratera · fechada por enquanto").
- Simulador: `Strategy.cave: bool`; estratégia `"caverna"` (= "casual" minerando na caverna, drills nos veios da caverna, sem drones). O Sim ganha um "mundo de mineração" (caverna) separado do "mundo da base" (superfície): índice virtual `BASE` (= W·H) é a base; campo de distância semeado na chegada da rampa com `K = (caminho cratera→zona na superfície) + tempo da rampa / tw`. Reportar números; meta 25–40 min.
- Teste: `test_estrategia_caverna_termina` (termina, minera na caverna, total dentro de 20–50 min).
- Bíblia §9 "Marco 2 · como ficou"; README (controles: E na cratera/rampa, luminária).
- [ ] `uv run pytest` verde, `uv run python tools/dev/smoke.py` OK, prints olhados com Read.
