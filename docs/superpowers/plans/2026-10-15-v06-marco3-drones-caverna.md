# v0.6 Marco 3 · Drones na caverna · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** a estação de drones pode ser construída na caverna. Cada camada tem a sua rede: os drones de uma estação só atendem baús e máquinas com chip da mesma camada, e as duas redes trabalham ao mesmo tempo, com o player em qualquer camada.

**Arquitetura:** hoje o `_update_machines` faz **uma** chamada `drones.update_stations(estações da superfície, drone_logistics())`. O M3 troca isso por um laço nas camadas (`layers.ORDER`): uma chamada por camada, com as estações e a rede **daquela** camada. Como o `drones.update_stations` já cria o `Ledger(stations)` dentro dele a cada passo, uma chamada por camada já dá um `Ledger` por camada, sem mexer no `game/drones.py`. O `drone_logistics()` ganha o parâmetro da camada. O desenho (`Renderer.draw_flying_drones`, `draw_station`) e o som (`App.update_ambient_sounds`) já usam `state.stations`, que é a camada ativa: não mudam, só ganham teste.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-v06-logistica-design.md` (Marco 3). Bíblia §14 (ponto "Caverna").

## Restrições globais
- **Rede por camada**: estação na camada X só enxerga `layers[X].machines` com `in_network`. Drone nunca troca de camada.
- **As duas camadas rodam sempre**, independente de `state.layer`.
- **Energia continua global** (`self.power.factor` de todas as máquinas): o mesmo `work_dt` vai pras duas camadas.
- **Submersa**: a regra fica como está (`drone.state == LANDED and machine.submerged` em `drones.update_drone`). Não mexer no `game/drones.py`.
- Some o bloqueio da caverna em `can_place` e a dica **"Drones só funcionam na superfície · Esc cancela"** em `App.hint`. A dica de construir passa a ser **"Clique para construir · drones atendem esta camada · Esc cancela"**.
- **Save**: sem versão nova (`SAVE_VERSION` continua 11). As estações já vão em `layers[key]["machines"]`.
- Os drones voam em linha reta por cima das paredes da caverna, igual voam por cima dos morros na superfície. Sem pathfinding.
- UI/arquivos: não abrir janela, não commitar, não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/`, `settings.json`.
- Mudou o que entra na rede: **rode as 3 ferramentas** no fim (`uv run pytest`, `uv run python tools/dev/smoke.py`, `uv run python tools/dev/real_video_check.py`). Se o smoke estourar o orçamento de frame (16,7 ms) num ponto só, rode de novo antes de chamar de regressão.

## Decisões (o dono deveria ver)
- **Nada muda no `game/drones.py`.** Separar por camada é só chamar o `update_stations` uma vez por camada. O `Ledger` por camada sai de graça.
- **`drone_logistics(key=SURFACE)`**: o padrão é a superfície, então os testes do M2 (`tests/test_chip.py`) que chamam sem argumento continuam valendo.
- **Ordem das camadas**: `layers.ORDER` (superfície, depois caverna), só as que existem em `self.layers`. A caverna só existe depois da 1ª descida.
- **Sem cena nova no smoke** (regra do dono: só quando não dá pra validar sem tela). Fica um print avulso `tools/dev/shot_v06_m3.py` pro dono ver a estação na caverna com drones voando.

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/systems.py` | `drone_logistics(key)`; `_update_machines` com o laço por camada; `can_place` sem o bloqueio da caverna |
| `game/app.py` | `hint()`: tira a dica da superfície e troca "o mapa todo" por "esta camada" |
| `docs/GAME_BIBLE.md` | linhas 326 e 481 (estação "atende o mapa inteiro" e "não pode ser colocada na caverna") |
| `tools/dev/shot_v06_m3.py` (novo) | print avulso: caverna com estação, dois baús e drones voando |
| `tests/test_drones_cave.py` (novo) | os testes deste marco |
| `tests/test_layers.py` | `test_drones_only_serve_the_surface` vira o teste da rede por camada |

---

### Task 1: Rede por camada, estação na caverna e bíblia

**Files:**
- Modify: `game/systems.py:503-505` (`drone_logistics`), `game/systems.py:762-763` (`can_place`), `game/systems.py:1536-1538` (`_update_machines`)
- Modify: `game/app.py:1946-1953` (`hint`)
- Modify: `docs/GAME_BIBLE.md:326`, `docs/GAME_BIBLE.md:481`
- Modify: `tests/test_layers.py:83-88`
- Create: `tests/test_drones_cave.py`

**Interfaces:**
- Consumes: `game.layers.SURFACE`, `CAVE`, `ORDER`; `GameState.enter_layer(key)`; `drones.new_station(machine, count)`; `Machine.in_network`; `drones.update_stations(stations, logistics, dt, events) -> int`.
- Produces: `GameState.drone_logistics(self, key: str = SURFACE) -> list[Machine]`. A Task 2 usa.

- [x] **Step 1: Escrever os testes que falham**

Criar `tests/test_drones_cave.py`:

```python
"""v0.6 M3: drones na caverna. Cada camada tem a sua rede e as duas rodam com o player em qualquer camada."""
import os
import random

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game import drones, save  # noqa: E402
from game.layers import CAVE, SURFACE  # noqa: E402
from game.systems import GameState, Machine  # noqa: E402


@pytest.fixture
def game() -> GameState:
    g = GameState(rng=random.Random(3))
    g.debug_add_ti()
    return g


def add_station(game, tile=(60, 70)) -> Machine:
    """Estação com 1 drone na camada ATIVA."""
    m = Machine("drone_station", *tile)
    m.station = drones.new_station(m, 1)
    game.machines.append(m)
    return m


def chests(game, a=(80, 70), b=(40, 70)) -> tuple[Machine, Machine]:
    """Baú que envia 10 ferro e baú que recebe ferro, na camada ATIVA."""
    src = Machine("chest_large", *a, sends={"iron"})
    src.storage.add("iron", 10)
    dst = Machine("chest_large", *b, receives={"iron"})
    game.machines += [src, dst]
    return src, dst


def run(game, seconds: float, step: float = 1 / 30) -> None:
    for _ in range(round(seconds / step)):
        game._update_machines(step)


def test_station_can_be_placed_in_the_cave(game):
    game.enter_layer(CAVE)
    px, py = game.player.tile
    spots = [(px + dx, py + dy) for dx in range(-4, 5) for dy in range(-4, 5)]
    assert any(game.can_place("drone_station", t) for t in spots)


def test_drone_logistics_is_per_layer(game):
    surf_chest = Machine("chest", 70, 70)
    game.machines.append(surf_chest)
    game.enter_layer(CAVE)
    cave_chest = Machine("chest", 60, 60)
    game.machines.append(cave_chest)
    assert cave_chest in game.drone_logistics(CAVE) and surf_chest not in game.drone_logistics(CAVE)
    assert surf_chest in game.drone_logistics(SURFACE) and cave_chest not in game.drone_logistics(SURFACE)
    assert surf_chest in game.drone_logistics()            # padrão = superfície (testes do M2)


def test_cave_drones_work_with_the_player_on_the_surface(game):
    game.enter_layer(CAVE)
    add_station(game)
    src, dst = chests(game)
    game.enter_layer(SURFACE)
    run(game, 40)
    assert dst.storage.count("iron") == 10 and src.storage.count("iron") == 0


def test_surface_drones_work_with_the_player_in_the_cave(game):
    add_station(game)
    src, dst = chests(game)
    game.enter_layer(CAVE)
    run(game, 40)
    assert dst.storage.count("iron") == 10


def test_networks_never_mix(game):
    """Estação só na superfície; os baús da caverna ficam parados. E vice-versa."""
    add_station(game)
    game.enter_layer(CAVE)
    src, dst = chests(game)
    run(game, 40)
    assert dst.storage.count("iron") == 0 and src.storage.count("iron") == 10


def test_cave_station_never_takes_from_the_surface(game):
    surf_src, surf_dst = chests(game)
    game.enter_layer(CAVE)
    st = add_station(game)
    cave_dst = Machine("chest_large", 40, 70, receives={"iron"})
    game.machines.append(cave_dst)
    run(game, 40)
    assert surf_src.storage.count("iron") == 10 and cave_dst.storage.count("iron") == 0
    assert all(d.source is None for d in st.station.drones)


def test_power_deficit_slows_both_layers(game, monkeypatch):
    """Energia global: o mesmo work_dt (dt × fator) chega nas duas chamadas."""
    add_station(game)
    game.enter_layer(CAVE)
    add_station(game)
    seen = []
    monkeypatch.setattr(drones, "update_stations", lambda st, lg, dt, ev: seen.append(dt) or 0)
    game._update_machines(0.1)
    assert len(seen) == 2 and seen[0] == seen[1] == pytest.approx(0.1 * game.power.factor)


def test_stations_property_is_the_active_layer(game):
    """Desenho e som usam state.stations: só a camada do player."""
    surf = add_station(game)
    game.enter_layer(CAVE)
    cave = add_station(game, (50, 50))
    assert game.stations == [cave]
    game.enter_layer(SURFACE)
    assert game.stations == [surf]
```

Em `tests/test_layers.py`, trocar `test_drones_only_serve_the_surface` (linhas 83-88) por:

```python
def test_each_layer_has_its_own_drone_network():
    g = GameState(rng=random.Random(1))
    g.enter_layer(CAVE)
    cave_chest = Machine("chest", 60, 60)
    g.machines.append(cave_chest)
    g.enter_layer(SURFACE)
    assert cave_chest not in g.drone_logistics() and cave_chest in g.drone_logistics(CAVE)
    assert g.base_chests() == []
```

- [x] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_drones_cave.py tests/test_layers.py -q`
Expected: FAIL. O `drone_logistics(CAVE)` dá `TypeError` (não aceita argumento), o `can_place` na caverna dá `False` e os drones da caverna não andam.

- [x] **Step 3: Implementar**

`game/systems.py`, o `drone_logistics` (o `SURFACE` já é importado no arquivo; conferir com `grep -n "^from game.layers\|^from game import.*layers" game/systems.py` e usar o nome que o arquivo já usa):

```python
    def drone_logistics(self, key: str = SURFACE) -> list[Machine]:
        """O que os drones da camada `key` atendem: a camada inteira (v0.6 M3: cada camada tem a sua rede, o drone
        nunca troca de camada) e só quem está na rede (v0.6 M2: chip)."""
        return [m for m in self.layers[key].machines if m.in_network]
```

`can_place`: apagar as duas linhas

```python
        if kind == "drone_station" and not self.active.has_base:   # drones só atendem a superfície (v0.3)
            return False
```

`_update_machines`: trocar

```python
        stations = [m for m in self.surface.machines if m.is_station and m.build <= 0]
        if stations:                         # drones (game/drones.py): só na superfície; no déficit voam mais devagar
            self.drone_deliveries += drones.update_stations(stations, self.drone_logistics(), work_dt, self.events)
```

por

```python
        for key in layers.ORDER:             # drones (game/drones.py): uma rede por camada (v0.6 M3), as duas rodam
            if key not in self.layers:       # sempre; um Ledger por chamada; no déficit voam mais devagar
                continue
            stations = [m for m in self.layers[key].machines if m.is_station and m.build <= 0]
            if stations:
                self.drone_deliveries += drones.update_stations(stations, self.drone_logistics(key), work_dt,
                                                                self.events)
```

(conferir que o módulo `layers` está importado em `game/systems.py`; o `enter_layer` já usa `layers.MAKERS`.)

`game/app.py`, no `hint()`: apagar

```python
        if self.placing == "drone_station" and not state.active.has_base:
            return "Drones só funcionam na superfície · Esc cancela"
```

e trocar `"Clique para construir · drones atendem o mapa todo · Esc cancela"` por `"Clique para construir · drones atendem esta camada · Esc cancela"`. Procurar teste que espera o texto antigo: `grep -rn "mapa todo\|só funcionam na superfície" tests tools` e atualizar.

`docs/GAME_BIBLE.md`:
- Linha 326: "eles atendem o **mapa inteiro**, sem alcance." → "eles atendem a **camada inteira** em que a estação está, sem alcance (v0.6 M3: cada camada tem a sua rede)."
- Linha 481: "**estação de drones não pode ser colocada na caverna** (dica \"Drones só funcionam na superfície\")" → "**a estação de drones funciona nas duas camadas, cada uma com a sua rede** (v0.6 M3; antes era só na superfície)".

Comentário do `game/config.py:545` ("os drones atendem o mapa inteiro"): trocar por "a camada inteira".

- [x] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/test_drones_cave.py tests/test_layers.py tests/test_chip.py tests/test_drones.py -q`
Expected: PASS.

Se `test_station_can_be_placed_in_the_cave` falhar por falta de chão perto da chegada (e não pela regra), olhar `game.world.is_floor` em volta do `player.tile` e escolher um ponto de chão no teste. Não afrouxar a regra do `can_place`.

- [x] **Step 5: Suíte inteira**

Run: `uv run pytest -q`
Expected: tudo verde (1514+ passed).

---

### Task 2: Save das duas redes e print avulso

**Files:**
- Modify: `tests/test_drones_cave.py` (acrescentar)
- Create: `tools/dev/shot_v06_m3.py`

**Interfaces:**
- Consumes: `GameState.drone_logistics(key)` (Task 1); `save.state_to_dict(state) -> dict`, `save.state_from_dict(data) -> GameState`; `drones.CARRYING`.
- Produces: nada de código pra outras tarefas.

- [x] **Step 1: Teste do save**

Acrescentar em `tests/test_drones_cave.py`:

```python
def test_save_keeps_stations_and_flying_cargo_of_each_layer(game):
    surf = add_station(game)
    chests(game)
    game.enter_layer(CAVE)
    cave = add_station(game)
    src, dst = chests(game)
    run(game, 6)                                           # drone da caverna já pegou ferro e está voando
    flying = cave.station.drones[0]
    assert flying.in_air and flying.cargo > 0
    carried = flying.cargo
    loaded = save.state_from_dict(save.state_to_dict(game))
    l_cave = [m for m in loaded.layers[CAVE].machines if m.is_station]
    l_surf = [m for m in loaded.layers[SURFACE].machines if m.is_station]
    assert len(l_cave) == 1 and len(l_surf) == 1
    assert (l_cave[0].tx, l_cave[0].ty) == (cave.tx, cave.ty) and (l_surf[0].tx, l_surf[0].ty) == (surf.tx, surf.ty)
    assert l_cave[0].station.drones[0].cargo == carried    # volta pousado, com a carga (entrega no 1º frame)
    run(loaded, 40)
    l_dst = next(m for m in loaded.layers[CAVE].machines if m.is_chest and (m.tx, m.ty) == (dst.tx, dst.ty))
    assert l_dst.storage.count("iron") == 10               # nada some nem duplica no save no meio do voo
```

Run: `uv run pytest tests/test_drones_cave.py -q`
Expected: PASS sem mudar código (o save já grava cada camada). Se falhar, a causa está no `game/save.py` (`machine_to_dict`/`machine_from_dict` da estação): investigar antes de mexer e avisar o gerente no report. Se o `run(game, 6)` não deixar o drone no ar com carga, ajustar o tempo (olhar `drone.state`) e não a regra.

- [x] **Step 2: Print avulso `tools/dev/shot_v06_m3.py`**

Seguir o molde do `tools/dev/shot_v06_m2.py` (mesmo cabeçalho, driver dummy, `settings.SETTINGS_PATH` temporário, `App(scale=1, skip_title=True)`, `app.set_mode("play")`). Cena:

1. `state.enter_layer(CAVE)`; achar 3 tiles de chão perto do player com `state.can_place("drone_station", t)` e `state.can_place("chest_large", t)`.
2. Pôr a estação com 2 drones (`drones.new_station(m, 2)`), um baú `chest_large` enviando 20 `iron` a ~6 tiles de um lado e um recebendo `iron` a ~6 tiles do outro. Máquinas com `build = 0`.
3. Rodar `state._update_machines(DT)` + `app.render` (o que o `shot_v06_m2.py` usa pra desenhar o frame) por ~3 s de jogo, até ter drone no ar, e salvar `reports/dev/v06_m3/cave_drones.png`.
4. Segundo print com o fantasma da estação na mão (`app.placing = "drone_station"`) na caverna, mostrando a dica "drones atendem esta camada": `reports/dev/v06_m3/cave_place_hint.png`.

Run: `uv run python tools/dev/shot_v06_m3.py`
Expected: os 2 PNGs em `reports/dev/v06_m3/`. Abrir com o Read e conferir que tem drone voando na caverna escura e a dica nova.

- [x] **Step 3: As 3 ferramentas**

Run: `uv run pytest -q && uv run python tools/dev/smoke.py && uv run python tools/dev/real_video_check.py`
Expected: tudo verde. No report, dizer quantos testes passaram e se o smoke estourou frame em algum ponto (rodar de novo antes de chamar de regressão).

---

## Fechamento (gerente)
- Merge pelo fluxo do handoff, prints do smoke regerados no main, olhar `reports/dev/v06_m3/`.
- Bíblia §14: "Marco 3 · como ficou na implementação". ROADMAP e este plano marcados.
- Mostrar os prints ao dono e esperar o ok pra ele testar no jogo.
