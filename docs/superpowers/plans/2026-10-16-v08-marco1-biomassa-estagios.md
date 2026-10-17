# v0.8 M1 · Biomassa e estágios: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ligar o 4º índice (Biomassa) e passar de 4 pra 6 estágios (TEMPESTADE → ÁRIDO → ÚMIDO → ALGAS → MUSGO → VERDE). Os 3 últimos pedem Ti **e** biomassa mínima. Entram também o lago esverdeado das Algas, o musgo do Musgo e o atalho F7.

**Architecture:**
- Cada `Stage` ganha `biomass` (mínimo), `look` (qual arte dos 4 estágios antigos ele usa: `storm`/`arid`/`mist`/`green`) e `water` (a paleta da água).
- Toda busca de arte por chave passa a ler o `look`. Algas e Musgo usam a arte `mist`, e o resto do render, das rampas e dos sons continua igual. A comparação por número (`>= C.GREEN_STAGE`) continua valendo, porque o Verde vira 6.
- A trava dupla mora em `stage_for_ti(ti, biomass)` e `stage_progress(ti, biomass)`. A transição (mancha) recebe a biomassa também.

**Tech Stack:** Python 3 + pygame-ce, pytest. Rodar com `uv run`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-16-v08-plantas-design.md`. Bíblia §17.
- Números de partida (exatos):
  - Algas: 25.000 Ti + biomassa 500;
  - Musgo: 50.000 Ti + biomassa 3.000;
  - Verde: 100.000 Ti + biomassa 15.000;
  - Árido continua 7.000 (o override da linha ~1043 do `config.py`) e Úmido continua 10.000.
- A chave interna `mist` **não muda**. Só o nome curto vira `ÚMIDO`. O título continua "ESTÁGIO 3 · PRIMEIRAS CHUVAS".
- Novos números: `ALGAE_STAGE = 4`, `MOSS_STAGE = 5`, `GREEN_STAGE = 6`. `STORM_STAGE`, `ARID_STAGE` e `MIST_STAGE` continuam 1, 2 e 3.
- Save sobe pra **v14** (`STAGE_SCHEME = 3`). Na migração, o save v13 ganha `biomass: 0` e o estágio fica em `min(estágio, 3)`.
- O F6 fica **livre** (reservado pro overlay de colisão do Futuro). A biomassa de debug é **F7**, que soma `DEBUG_BIOMASS_BONUS = 500`.
- Unidade da biomassa: `kg`. Cor: `C_BIOMASS = "#8fd46a"`. Rótulo: `"BIOMASSA"`.
- A paleta `algae` (água das Algas e do Musgo) é placeholder por código: `water #3f8a72`, `water_d #2f6e5a`. Ela **passa pelo dono** pelo print do Task 5 antes do merge.
- O Dev **não commita**. O gerente commita.
- O pytest inteiro leva ~7–8 min: rode em background com log (`uv run pytest -q > /tmp/pytest_m1.log 2>&1; echo exit=$?`), nunca dois ao mesmo tempo.
- Não rode `tools/sprites/build_sprites.py`. Ele sobrescreve os destroços do v0.7.
- Não abra o jogo em janela real.

---

### Task 1: Estágios e tabelas no config

**Files:**
- Modify: `game/config.py`:
  - `Stage` e `STAGES` (~322–347);
  - `WATER_THRESHOLD` (~352);
  - `INDEX_LABEL` e `INDEX_UNIT` (~194–195);
  - `PALETTES` (~506);
  - `C_*`, `INDEX_COLOR` e `STAGE_COLOR` (~549–560);
  - `DEBUG_TI_BONUS` (~61).
- Modify: `game/hills.py:50`, `game/render.py:131-138`, `game/ground.py:77-78`
- Create: `tests/test_stages_v08.py`
- Modify: `tests/test_stages_v04.py` (as expectativas de 4 estágios)

**Interfaces:**
- Produces:
  - `C.Stage(number, key, ti, title, subtitle, name, biomass=0, look="", water="")`, com `look` e `water` caindo na `key` quando vazios (`__post_init__`);
  - `C.ALGAE_STAGE`, `C.MOSS_STAGE` e `C.GREEN_STAGE == 6`;
  - `C.DEBUG_BIOMASS_BONUS`;
  - `C.PALETTES["algae"]`;
  - `render.stage_key(n)` e `ground.stage_key(n)` devolvendo o **look**;
  - `render.water_key(n)` devolvendo `C.STAGE_ART`-equivalente da água (`"dead"`, `"mist"`, `"algae"` ou `"green"`).

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_stages_v08.py`:
```python
"""v0.8 M1: 6 estágios (Tempestade, Árido, Úmido, Algas, Musgo, Verde), a trava dupla Ti + biomassa e o 4º índice."""

from game import config as C
from game.render import art_key, stage_key, water_key


def test_six_stages_in_order():
    assert [s.key for s in C.STAGES] == ["storm", "arid", "mist", "algae", "moss", "green"]
    assert [s.number for s in C.STAGES] == [1, 2, 3, 4, 5, 6]
    assert [s.name for s in C.STAGES] == ["TEMPESTADE", "ÁRIDO", "ÚMIDO", "ALGAS", "MUSGO", "VERDE"]
    assert [s.ti for s in C.STAGES] == [0, 7_000, 10_000, 25_000, 50_000, 100_000]
    assert [s.biomass for s in C.STAGES] == [0, 0, 0, 500, 3_000, 15_000]


def test_stage_constants():
    assert (C.STORM_STAGE, C.ARID_STAGE, C.MIST_STAGE) == (1, 2, 3)
    assert (C.ALGAE_STAGE, C.MOSS_STAGE, C.GREEN_STAGE) == (4, 5, 6)


def test_algae_and_moss_look_like_the_mist_but_have_their_own_water():
    assert stage_key(C.ALGAE_STAGE) == stage_key(C.MOSS_STAGE) == "mist"
    assert art_key(C.ALGAE_STAGE) == art_key(C.MOSS_STAGE) == "mist"
    assert water_key(C.ALGAE_STAGE) == water_key(C.MOSS_STAGE) == "algae"
    assert water_key(C.MIST_STAGE) == "mist" and water_key(C.GREEN_STAGE) == "green"
    assert water_key(C.STORM_STAGE) == "dead"


def test_every_stage_has_color_threshold_and_palettes():
    for s in C.STAGES:
        assert s.number in C.STAGE_COLOR and s.number in C.WATER_THRESHOLD
        assert art_key(s.number) in C.PALETTES and water_key(s.number) in C.PALETTES
    assert C.WATER_THRESHOLD[C.ALGAE_STAGE] == C.WATER_THRESHOLD[C.MIST_STAGE]
    assert C.WATER_THRESHOLD[C.MOSS_STAGE] == C.WATER_THRESHOLD[C.MIST_STAGE]


def test_algae_palette_only_changes_the_water():
    mist, algae = C.PALETTES["mist"], C.PALETTES["algae"]
    assert algae["water"] == "#3f8a72" and algae["water_d"] == "#2f6e5a"
    assert {k: v for k, v in algae.items() if k not in ("water", "water_d")} == \
        {k: v for k, v in mist.items() if k not in ("water", "water_d")}


def test_biomass_index_labels():
    assert C.INDEX_LABEL["biomass"] == "BIOMASSA" and C.INDEX_UNIT["biomass"] == "kg"
    assert C.INDEX_COLOR["biomass"] == C.C_BIOMASS == "#8fd46a"


def test_hills_ramp_keys_follow_the_look():
    from game import hills
    assert hills.STAGE_KEYS == ("storm", "arid", "mist", "mist", "mist", "green")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_stages_v08.py -q`
Expected: FAIL (`ImportError: cannot import name 'water_key'`, e o resto falha nas contagens).

- [ ] **Step 3: Implementar no `game/config.py`**

Troque a dataclass `Stage` e a lista `STAGES` (~322–347) por:
```python
@dataclass(frozen=True)
class Stage:
    number: int
    key: str            # "storm", "arid", "mist", "algae", "moss", "green"
    ti: int             # Ti mínimo
    title: str
    subtitle: str
    name: str           # nome curto, usado no HUD ("PRÓXIMO: ALGAS")
    biomass: int = 0    # v0.8 M1: biomassa mínima (além do Ti) pra entrar no estágio
    look: str = ""      # v0.8 M1: qual dos 4 visuais antigos ele usa (rampas, sprites, som); vazio = a própria key
    water: str = ""     # v0.8 M1: paleta da água (PALETTES); vazio = a arte do look (STAGE_ART)

    def __post_init__(self):
        if not self.look:
            object.__setattr__(self, "look", self.key)
        if not self.water:
            object.__setattr__(self, "water", STAGE_ART[self.look])


STAGE_ART = {"storm": "dead", "arid": "dead", "mist": "mist", "green": "green"}   # look -> arte (sprites e paleta)

# v0.4 Marco 1: 4 estágios. v0.8 M1: 6, e os 3 últimos pedem biomassa também (bíblia §17). Algas e Musgo
# usam o visual da Névoa (look "mist"), com a água esverdeada da paleta "algae".
STAGES = [
    Stage(1, "storm", 0, "ESTÁGIO 1 · TEMPESTADE", "Sobreviva e monte a base", "TEMPESTADE"),
    Stage(2, "arid", 6_500, "ESTÁGIO 2 · CÉU LIMPO", "A poeira baixou", "ÁRIDO"),
    Stage(3, "mist", 10_000, "ESTÁGIO 3 · PRIMEIRAS CHUVAS", "Máquinas nv.2 liberadas", "ÚMIDO"),
    Stage(4, "algae", 25_000, "ESTÁGIO 4 · PRIMEIRAS ALGAS", "Os lagos ganham cor", "ALGAS",
          biomass=500, look="mist", water="algae"),
    Stage(5, "moss", 50_000, "ESTÁGIO 5 · MUSGO", "O verde agarra nas pedras", "MUSGO",
          biomass=3_000, look="mist", water="algae"),
    Stage(6, "green", 100_000, "ESTÁGIO 6 · PRIMEIRO VERDE", "Ti 100.000 · fim do MVP", "VERDE", biomass=15_000),
]
STORM_STAGE = 1      # estágio da tempestade de poeira (passou dele, a tempestade some)
ARID_STAGE = 2
MIST_STAGE = 3       # Úmido: a água e as máquinas nv.2 começam aqui (a chave continua "mist")
ALGAE_STAGE = 4      # v0.8 M1
MOSS_STAGE = 5       # v0.8 M1: o musgo das pedras aparece daqui pra frente
GREEN_STAGE = 6      # plantas e fim do jogo
```
- Apague a linha antiga `STAGE_ART = {...}` (~347), que agora fica antes de `STAGES`.
- Os comentários antigos sobre o Ti do Árido (6.500 / balance_sim) ficam onde estavam.
- O override da linha ~1043 (`ti=7_000` no `arid`) continua igual. O `_replace` preserva `biomass`/`look`/`water`.

`WATER_THRESHOLD` (~352):
```python
WATER_THRESHOLD = {1: 0.0, 2: 0.0, 3: 0.24, 4: 0.24, 5: 0.24, 6: 0.33}   # Tempestade e Árido sem água (§3); Algas e Musgo = Úmido
```

`INDEX_UNIT` e `INDEX_LABEL` (~194–195):
```python
INDEX_UNIT = {"o2": "ppq", "heat": "pK", "water": "ppm", "biomass": "kg"}
INDEX_LABEL = {"o2": "O₂", "heat": "CALOR", "water": "AGUA", "biomass": "BIOMASSA"}
```

Em `PALETTES`, logo depois do dict (fechou o `}` do `"green"`), acrescente:
```python
PALETTES["algae"] = {**PALETTES["mist"], "water": "#3f8a72", "water_d": "#2f6e5a"}   # v0.8 M1: lago das Algas (placeholder; dono aprova pelo print)
```

Junto das cores (~556):
```python
C_BIOMASS = "#8fd46a"
```

`INDEX_COLOR` e `STAGE_COLOR` (~559–560):
```python
INDEX_COLOR = {"o2": C_O2, "heat": C_HEAT, "water": C_WATER, "biomass": C_BIOMASS}
STAGE_COLOR = {1: C_ACCENT, 2: "#e8b37a", 3: "#9fd2e6", 4: "#7fcfb0", 5: "#8fd46a", 6: "#a6e07a"}
```

Ao lado de `DEBUG_TI_BONUS` (~61):
```python
DEBUG_BIOMASS_BONUS = 500       # F7: soma isso na biomassa (v0.8 M1; o F6 fica pro overlay de colisão)
```

Atenção: `INDEX_COLOR` é definido depois de `C_BIOMASS`. Se a ordem do arquivo não deixar, defina o `C_BIOMASS` antes do `INDEX_COLOR`.

- [ ] **Step 4: Ler o look nas chaves de arte**

`game/render.py:131-138`:
```python
def stage_key(stage: int) -> str:
    """Visual do estágio `stage` (1 a 6): "storm", "arid", "mist" ou "green". Algas e Musgo usam o da Névoa (look)."""
    return C.STAGES[stage - 1].look


def art_key(stage: int) -> str:
    """Arte (sprites e paleta) do estágio `stage`: "dead", "mist" ou "green". Tempestade e Árido usam a do Morto."""
    return C.STAGE_ART[stage_key(stage)]


def water_key(stage: int) -> str:
    """Paleta da água do estágio `stage` (v0.8 M1): a da arte, menos Algas e Musgo ("algae", esverdeada)."""
    return C.STAGES[stage - 1].water
```

`game/ground.py:77-78`:
```python
def stage_key(stage: int) -> str:
    return C.STAGES[stage - 1].look         # v0.8 M1: Algas e Musgo usam as rampas da Névoa
```

`game/hills.py:50`:
```python
STAGE_KEYS = tuple(s.look for s in C.STAGES)                 # estágio 1..6 -> rampa (v0.8 M1: Algas e Musgo = "mist")
```
Confira se o `hills.py` já importa `config as C`. Se não, acrescente `from game import config as C` nos imports.

- [ ] **Step 5: Atualizar `tests/test_stages_v04.py`**

- `test_four_stages_in_order`: troque pelo nome `test_first_stages_in_order` e confira só os 3 primeiros (`[s.key for s in C.STAGES][:3] == ["storm", "arid", "mist"]`, `C.STAGES[2].ti == 10_000`). Os 6 já estão no `test_stages_v08.py`.
- `test_no_water_before_the_mist`: continua valendo (`MIST < GREEN` em limiar).
- Qualquer outro teste que fixava `len(C.STAGES) == 4`, `"NÉVOA"` ou `GREEN_STAGE == 4` passa a usar a constante ou o nome novo (`"ÚMIDO"`). **Não afrouxe** o que o teste verifica, só atualize o valor esperado pro da spec.

- [ ] **Step 6: Rodar**

Run: `uv run pytest tests/test_stages_v08.py tests/test_stages_v04.py tests/test_hills.py tests/test_ground.py -q`
Expected: PASS.

---

### Task 2: Trava dupla, índice no estado, transição e F7

**Files:**
- Modify: `game/systems.py`:
  - `stage_for_ti` e `stage_progress` (~309–329);
  - `GameState.__init__` (~380);
  - `_check_stage` (~2033);
  - `debug_add_ti` (~2329).
- Modify: `game/transition.py`: `window_progress`, `window_step`, `tile_stage` e `StageMap.update`.
- Modify: `game/render.py:368` (chamada do `stage_map.update`).
- Modify: `game/app.py:428-437` (tecla F7) e `game/ui.py:2455` (lista de atalhos).
- Test: `tests/test_stages_v08.py` (acrescentar), `tests/test_progress.py`, `tests/test_transition.py`.

**Interfaces:**
- Consumes: `C.Stage.biomass`, `C.DEBUG_BIOMASS_BONUS` (Task 1).
- Produces:
  - `stage_for_ti(ti: float, biomass: float = 0.0) -> int`;
  - `stage_progress(ti: float, biomass: float = 0.0) -> tuple[Stage | None, float, float, float]`, ou seja (próximo, fração, Ti que falta, biomassa que falta);
  - `GameState.indices["biomass"]`;
  - `GameState.debug_add_biomass(amount=C.DEBUG_BIOMASS_BONUS)`;
  - `transition.window_progress(ti, biomass=0.0)`, `window_step(ti, biomass=0.0)`, `tile_stage(x, y, ti, sources, seed=..., biomass=0.0)`;
  - `StageMap.update(ti, sources, biomass=0.0)`.

- [ ] **Step 1: Escrever os testes que falham** (acrescentar em `tests/test_stages_v08.py`)

```python
import pytest

from game.systems import GameState, stage_for_ti, stage_progress
from game.transition import StageMap


def test_stage_needs_ti_and_biomass():
    assert stage_for_ti(25_000) == C.MIST_STAGE                     # Ti sem biomassa: para no Úmido
    assert stage_for_ti(25_000, 499) == C.MIST_STAGE
    assert stage_for_ti(25_000, 500) == C.ALGAE_STAGE
    assert stage_for_ti(24_999, 10_000) == C.MIST_STAGE             # biomassa sem Ti também não sobe
    assert stage_for_ti(100_000, 15_000) == C.GREEN_STAGE
    assert stage_for_ti(100_000, 3_000) == C.MOSS_STAGE             # não pula: para no primeiro que falta


def test_progress_reports_the_bottleneck():
    nxt, frac, ti_left, bio_left = stage_progress(25_000, 250)      # Ti cheio, biomassa na metade
    assert nxt.key == "algae" and frac == pytest.approx(0.5)
    assert ti_left == 0 and bio_left == 250
    nxt, frac, ti_left, bio_left = stage_progress(17_500, 500)      # biomassa cheia, Ti na metade (10k -> 25k)
    assert nxt.key == "algae" and frac == pytest.approx(0.5) and ti_left == 7_500 and bio_left == 0


def test_progress_without_biomass_requirement_is_the_old_one():
    nxt, frac, ti_left, bio_left = stage_progress(C.STAGES[1].ti / 2)
    assert nxt.key == "arid" and frac == pytest.approx(0.5) and bio_left == 0


def test_progress_at_the_end():
    assert stage_progress(100_000, 15_000) == (None, 1.0, 0.0, 0.0)


def test_state_has_biomass_and_it_counts_in_ti():
    s = GameState()
    assert s.indices["biomass"] == 0.0
    s.indices["biomass"] = 123.0
    assert s.ti == pytest.approx(123.0)


def test_check_stage_uses_biomass():
    s = GameState()
    s.indices["o2"] = 30_000.0
    s._check_stage()
    assert s.stage == C.MIST_STAGE
    s.debug_add_biomass()                                           # +500
    assert s.indices["biomass"] == C.DEBUG_BIOMASS_BONUS
    assert s.stage == C.ALGAE_STAGE


def test_stage_map_waits_for_biomass():
    m = StageMap()
    m.update(24_999, [(0, 0)])                                      # Ti quase no limiar, sem biomassa
    assert m.stage == C.MIST_STAGE
    m.update(25_000, [(0, 0)], biomass=500)
    assert m.stage == C.ALGAE_STAGE
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_stages_v08.py -q`
Expected: FAIL (`stage_progress` devolve 3 valores; não existe `debug_add_biomass`).

- [ ] **Step 3: Implementar em `game/systems.py`**

```python
def stage_for_ti(ti: float, biomass: float = 0.0) -> int:
    """Estágio pelo Ti e pela biomassa (v0.8 M1): o maior em sequência cujos dois mínimos já bateram."""
    stage = 1
    for s in C.STAGES:
        if ti < s.ti or biomass < s.biomass:
            break
        stage = s.number
    return stage


# ---- quanto falta pro próximo estágio (funções puras, testadas em tests/test_progress.py) ----
def stage_progress(ti: float, biomass: float = 0.0) -> tuple[C.Stage | None, float, float, float]:
    """(próximo estágio, progresso de 0 a 1 DENTRO do estágio atual, Ti que falta, biomassa que falta).

    O progresso é relativo ao estágio atual e vale o do gargalo (o menor entre Ti e biomassa). Próximo estágio sem
    biomassa a mais conta só o Ti. No último estágio devolve (None, 1.0, 0, 0).
    """
    current = C.STAGES[stage_for_ti(ti, biomass) - 1]
    if current.number == len(C.STAGES):
        return None, 1.0, 0.0, 0.0
    nxt = C.STAGES[current.number]
    fraction = (ti - current.ti) / (nxt.ti - current.ti)
    if nxt.biomass > current.biomass:
        fraction = min(fraction, (biomass - current.biomass) / (nxt.biomass - current.biomass))
    return nxt, max(0.0, min(1.0, fraction)), max(0.0, nxt.ti - ti), max(0.0, nxt.biomass - biomass)
```

`GameState.__init__` (~380):
```python
        self.indices = {"o2": 0.0, "heat": 0.0, "water": 0.0, "biomass": 0.0}   # v0.8 M1: biomassa (4º índice)
```

`_check_stage` (~2033):
```python
    def _check_stage(self) -> None:
        new_stage = stage_for_ti(self.ti, self.indices["biomass"])
```
(o resto igual).

Logo depois de `debug_add_ti` (~2335):
```python
    def debug_add_biomass(self, amount: float = C.DEBUG_BIOMASS_BONUS) -> None:
        """F7 (v0.8 M1): biomassa de graça, pra testar os estágios novos antes do cultivador existir."""
        self.indices["biomass"] += amount
        self._check_stage()
```

- [ ] **Step 4: Transição em `game/transition.py`**

```python
def window_progress(ti: float, biomass: float = 0.0) -> tuple[int, float]:
    """(estágio atual, quanto da janela de transição já andou, de 0 a 1). v0.8 M1: com a biomassa, a janela anda pelo
    gargalo (o mesmo progresso do HUD)."""
    stage = stage_for_ti(ti, biomass)
    nxt, fraction, _, _ = stage_progress(ti, biomass)
    if nxt is None:
        return stage, 0.0
    start = 1.0 - C.TRANSITION_WINDOW
    return stage, max(0.0, (fraction - start) / C.TRANSITION_WINDOW)


def window_step(ti: float, biomass: float = 0.0) -> tuple[int, int]:
    stage, progress = window_progress(ti, biomass)
    return stage, min(C.TRANSITION_STEPS - 1, int(progress * C.TRANSITION_STEPS))
```
- Mantenha as docstrings antigas e só acrescente a frase da biomassa.
- `tile_stage(x, y, ti, sources, seed=C.WORLD_SEED, biomass: float = 0.0)` chama `window_step(ti, biomass)`.
- `StageMap.update(self, ti, sources, biomass: float = 0.0)` chama `window_progress(ti, biomass)`.

`game/render.py:368`:
```python
            self.stage_map.update(state.ti, [BASE_SOURCE, *state.transition_sources], state.indices["biomass"])
```

- [ ] **Step 5: F7 e a lista de atalhos**

`game/app.py`, no `on_key`, depois do `elif key == pygame.K_F5:` (mantendo o bloco do F5):
```python
        elif key == pygame.K_F7:                          # debug (v0.8 M1): +biomassa (F6 fica pro overlay de colisão)
            state.debug_add_biomass()
```

`game/ui.py:2455`:
```python
        ("F1 · F2 · F3 · F4", "Debug: x10 · +10.000 Ti · rápido · gelo da cratera"),
        ("F5", "Contador de FPS e ms do quadro"),
        ("F7", "Debug: +500 de biomassa"),
```

No `CLAUDE.md` da raiz, na linha "Atalhos de debug no jogo", acrescente ` · F7 +500 de biomassa (v0.8)`.

- [ ] **Step 6: Atualizar `tests/test_progress.py` e `tests/test_transition.py`**

- Quem desempacota `stage_progress(...)` em 3 passa a desempacotar em 4 (`nxt, frac, left, _ =`). Quem compara com `(None, 1.0, 0.0)` passa a comparar com `(None, 1.0, 0.0, 0.0)`.
- Em `test_progress.py`, `"NÉVOA"` vira `"ÚMIDO"`.
- Os exemplos com Ti entre 10k e 100k, que antes iam pro Verde, passam a ir pras Algas (10k → 25k). Exemplo do dono: `stage_progress(12_914)` → próximo `"ALGAS"`, fração `(12_914 - 10_000) / 15_000`.
- `stage_progress(100_000)` sem biomassa **não** é mais o fim: é `ALGAS` com biomassa 500 faltando.
- `game/ui.py:857` (o painel) ainda desempacota 3. Ele é reescrito no Task 4. Até lá, troque só pra `nxt, fraction, remaining, _ = stage_progress(state.ti, state.indices["biomass"])`, pra não quebrar.

- [ ] **Step 7: Rodar**

Run: `uv run pytest tests/test_stages_v08.py tests/test_progress.py tests/test_transition.py tests/test_stages_v04.py -q`
Expected: PASS.

---

### Task 3: Save v14 e a lista de mundos

**Files:**
- Modify: `game/save.py`:
  - `SAVE_VERSION` (~104) e `STAGE_SCHEME` (~108);
  - `MIGRATIONS` (~575) mais a função nova.
- Modify: `game/worlds.py:274-275`
- Test: `tests/test_save.py` (acrescentar), `tests/test_worlds.py` (acrescentar)

**Interfaces:**
- Consumes: `GameState.indices["biomass"]` (Task 2).
- Produces: `save._v13_to_v14(data) -> dict`, `SAVE_VERSION == 14`, `STAGE_SCHEME == 3`.

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_save.py`:
```python
def test_v13_save_gets_biomass_and_loses_the_old_green():
    from game import config as C
    data = {"version": 13, "progress": {"indices": {"o2": 60_000.0, "heat": 30_000.0, "water": 20_000.0},
                                        "stage": 4, "stage_scheme": 2}}
    out = save._v13_to_v14(data)
    assert out["progress"]["indices"]["biomass"] == 0.0
    assert out["progress"]["stage"] == C.MIST_STAGE            # o Verde antigo (4) volta pro Úmido: falta biomassa
    assert out["progress"]["stage_scheme"] == 3


def test_v13_early_stage_is_kept():
    data = {"version": 13, "progress": {"indices": {"o2": 1.0, "heat": 0.0, "water": 0.0}, "stage": 2,
                                        "stage_scheme": 2}}
    assert save._v13_to_v14(data)["progress"]["stage"] == 2


def test_biomass_round_trips(tmp_path):
    from game.systems import GameState
    s = GameState()
    s.indices["biomass"] = 321.0
    # use aqui o mesmo par salvar/carregar que os outros testes de round-trip deste arquivo usam
    # (procure "def test_" com tmp_path e copie o padrão: salvar em tmp_path e carregar num GameState novo)
```
O último teste fica **completo** usando o helper de round-trip que já existe em `tests/test_save.py`. Abra o arquivo, ache o padrão (salvar com `tmp_path`, carregar) e escreva o teste com ele. A asserção final é `assert loaded.indices["biomass"] == 321.0`.

Em `tests/test_worlds.py`, siga o padrão de um teste que já escreve um JSON de save num slot e lê com `worlds.info`:
- grave um save `version: 13` com `progress.stage = 4`;
- confira `worlds.info(slot).stage == C.MIST_STAGE` e `.stage_name == "ÚMIDO"`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_save.py tests/test_worlds.py -q`
Expected: FAIL (`AttributeError: _v13_to_v14`).

- [ ] **Step 3: Implementar**

`game/save.py`:
- `SAVE_VERSION = 14`, com o comentário começando por `# v14 (v0.8 M1): biomassa (4º índice) e 6 estágios · v13 ...`, mantendo o resto do histórico.
- `STAGE_SCHEME = 3`, e no comentário de cima acrescente "3 = v0.8 (Tempestade, Árido, Úmido, Algas, Musgo, Verde)".

```python
def _v13_to_v14(data: dict) -> dict:
    """v0.8 M1: o 4º índice (biomassa) nasce zerado e os estágios viram 6. O Verde antigo (4) pedia só Ti; agora
    Algas, Musgo e Verde pedem biomassa também, então quem estava no 4 volta pro Úmido (3). Do 1 ao 3 nada muda."""
    progress = data.get("progress", {})
    progress.setdefault("indices", {})["biomass"] = 0.0
    progress["stage"] = min(int(progress.get("stage", 1)), C.MIST_STAGE)
    progress["stage_scheme"] = 3
    return data


MIGRATIONS: dict = {10: _v10_to_v11, 11: _v11_to_v12, 12: _v12_to_v13, 13: _v13_to_v14}
```
Confira se o `save.py` importa `config as C`. Ele usa `C.MELTER_KINDS`, então importa.

`game/worlds.py`, onde lê o estágio (~274):
```python
        progress = data["progress"]
        stage = int(progress["stage"])
        if version < 14:                                   # v0.8 M1: o Verde antigo (4) volta pro Úmido (save._v13_to_v14)
            stage = min(stage, C.MIST_STAGE)
        out.stage = max(1, min(len(C.STAGES), stage))
```

- [ ] **Step 4: Rodar**

Run: `uv run pytest tests/test_save.py tests/test_worlds.py tests/test_stages_v04.py -q`
Expected: PASS. Se algum teste do `test_stages_v04.py` sobre o save do v0.3/v6 quebrar por causa da versão, ajuste o valor esperado pra 14 sem tirar a verificação.

---

### Task 4: HUD (4 índices e o próximo estágio com biomassa) e objetivos

**Files:**
- Modify: `game/ui.py:850-895` (`draw_ti_panel`)
- Modify: `game/objectives.py:101`
- Test: `tests/test_stages_v08.py` (acrescentar), `tests/test_objectives.py`

**Interfaces:**
- Consumes: `stage_progress(ti, biomass)` de 4 valores, `C.INDEX_*["biomass"]`.
- Produces: `ui.next_stage_line(nxt, remaining_ti, remaining_bio, eta) -> str`, uma função pura no módulo `game/ui.py`.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_next_stage_line_shows_the_bottleneck():
    from game.ui import next_stage_line
    algae = C.STAGES[C.ALGAE_STAGE - 1]
    assert next_stage_line(algae, 7_500, 0, "~2 min") == "faltam 7.5k · ~2 min"
    assert next_stage_line(algae, 0, 380, "~2 min") == "falta biomassa 380"
    assert next_stage_line(algae, 7_500, 380, "~2 min") == "faltam 7.5k · biomassa 380"


def test_mist_objective_says_umido():
    from game.objectives import OBJECTIVES
    texts = [o.text for o in OBJECTIVES]
    assert "Chegue ao estágio Úmido" in texts and "Chegue ao estágio Névoa" not in texts
```
O formato do número (`7.5k`) é o do `fmt` que já existe no `ui.py`. Antes de fixar o texto esperado, confira no código o que `fmt(7_500)` devolve e use isso no teste.

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_stages_v08.py -q -k "next_stage_line or umido"`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Em `game/ui.py`, função de módulo perto do `eta_label`/`fmt`:
```python
def next_stage_line(nxt, remaining_ti: float, remaining_bio: float, eta: str) -> str:
    """Linha de baixo do "próximo estágio" (v0.8 M1): o que falta, Ti e/ou biomassa. Só biomassa não tem estimativa."""
    if remaining_bio > 0 and remaining_ti <= 0:
        return f"falta biomassa {fmt(remaining_bio)}"
    if remaining_bio > 0:
        return f"faltam {fmt(remaining_ti)} · biomassa {fmt(remaining_bio)}"
    return f"faltam {fmt(remaining_ti)} · {eta}"
```

`draw_ti_panel`:
- `nxt, fraction, remaining, remaining_bio = stage_progress(state.ti, state.indices["biomass"])`;
- `line2 = next_stage_line(nxt, remaining, remaining_bio, eta)`;
- o loop de índices vira `for i, key in enumerate(("o2", "heat", "water", "biomass")):`;
- **todo y do bloco "próximo estágio" desce 9 px**: `y + 62` → `y + 71`, `y + 61` → `y + 70`, `y + 66` → `y + 75`, `y + 70` → `y + 79` e `y + 82` → `y + 91`;
- as alturas `h = 74 / 100 / 88` viram `83 / 109 / 97`;
- quando quebra a linha (`wrap_eta`), a primeira linha é `line2` até o `·` e a segunda é o resto. Mantenha a lógica que já existe, aplicada sobre `line2` em vez de `f"faltam {fmt(remaining)}"` e `eta`.

Se o `INDEX_NAME` não tiver acento pra biomassa, ele não precisa de entrada (o rótulo já é `BIOMASSA`).

`game/objectives.py:101`:
```python
    Objective("Chegue ao estágio Úmido", lambda s: s.stage >= C.MIST_STAGE),
```

- [ ] **Step 4: Rodar**

Run: `uv run pytest tests/test_stages_v08.py tests/test_objectives.py tests/test_ui_b2.py tests/test_hud_text.py tests/test_ui_size.py -q`
Expected: PASS. Teste de layout que fixava a altura do painel do Ti é atualizado pros valores novos (+9).

---

### Task 5: Visual das Algas (água) e do Musgo (musgo nas pedras) + print pro dono

**Files:**
- Modify: `game/render.py`:
  - `_lake_stage` (~1203–1219);
  - os dois `_draw_water(...)` (~1171 e ~1182);
  - o musgo do topo da parede (~1132).
- Modify: `game/ground.py:657-660` (`decor_layers`)
- Create: `tools/dev/shot_v08_m1.py`
- Test: `tests/test_stages_v08.py` (acrescentar)

**Interfaces:**
- Consumes: `render.water_key`, `C.MOSS_STAGE`, `C.PALETTES["algae"]`.
- Produces: prints em `reports/dev/v08_m1_*.png`.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_moss_overlay_starts_in_the_moss_stage():
    from game.ground import decor_layers
    moss_on = {"pebble_a"}
    assert decor_layers("pebble_a", C.ALGAE_STAGE, moss_on) == ["pebble_a"]
    assert decor_layers("pebble_a", C.MOSS_STAGE, moss_on) == ["pebble_a", "pebble_a_moss"]
    assert decor_layers("pebble_a", C.GREEN_STAGE, moss_on) == ["pebble_a", "pebble_a_moss"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/test_stages_v08.py -q -k moss`
Expected: FAIL (no Musgo ainda devolve só a pedra).

- [ ] **Step 3: Implementar**

`game/ground.py`, `decor_layers`:
```python
def decor_layers(name: str, stage: int, moss_on) -> list[str]:
    """O que desenhar no lugar do solto, em ordem: a pedra e, do Musgo em diante (v0.8 M1; era só no Verde), o
    overlay de musgo de mesmo N."""
    if stage >= C.MOSS_STAGE and name in moss_on:
        return [name, f"{name}_moss"]
    return [name]
```

`game/render.py`, musgo no topo da parede (~1132). A condição `stage == "green"` vira:
```python
            if self.stage_map.stage_at(tx, ty) >= C.MOSS_STAGE and hash01(tx, ty, 70) < 0.5:   # v0.8 M1: do Musgo em diante
```
Na caverna o `stage_map` é o `cave_map`, fixo no estágio 1, então ela continua sem musgo, como hoje.

Água das Algas: em `_lake_stage`, troque os dois `art_key(...)` por `water_key(...)`, tanto no `return ("all", m.stage), art_key(m.stage)` quanto no `grid = ...art_key(m.stage_at(...))`. Nos dois `_draw_water`:
- ~1171: `self._draw_water(canvas, world, tx, ty, sx, sy, water_key(stage_num), t)`;
- ~1182: `self._draw_water(canvas, world, tx, ty, sx, sy, water_key(self.stage_map.stage_at(tx, ty)), t)`.

O `water_atlas("algae")` não acha `water_auto_algae.png` e cai no gerado por código a partir do `art.water("algae")`, que usa `C.PALETTES["algae"]["water"]`. O `lake.full_tile` usa `C.PALETTES[stage]`, e o `"algae"` existe. Confirme que nada mais quebra procurando `water_atlas(` e `full_tile(` e vendo se alguém passa uma chave que não existe em `PALETTES`.

- [ ] **Step 4: Print pro dono**

Crie `tools/dev/shot_v08_m1.py` seguindo o padrão do `tools/dev/shot_v07_m3.py`: headless, `SDL_VIDEODRIVER=dummy`, seed 7, mesmo jeito de montar o `App` e salvar o canvas. Gere 4 prints de um lago com pedras soltas por perto, usando o `region_spot`/lago que o smoke usa em `verde_cobertura_lago`:
- `reports/dev/v08_m1_umido.png`: Ti 10.000, biomassa 0;
- `reports/dev/v08_m1_algas.png`: Ti 25.000, biomassa 500 (a água esverdeada);
- `reports/dev/v08_m1_musgo.png`: Ti 50.000, biomassa 3.000 (o musgo nas pedras);
- `reports/dev/v08_m1_hud.png`: o painel do Ti nas Algas com biomassa faltando ("falta biomassa ...").

Run: `uv run python tools/dev/shot_v08_m1.py > /tmp/shot_v08_m1.log 2>&1; echo exit=$?`
Expected: `exit=0` e os 4 arquivos em `reports/dev/`. **Olhe os 4 prints** (Read na imagem) e descreva no report o que aparece.

- [ ] **Step 5: Rodar**

Run: `uv run pytest tests/test_stages_v08.py tests/test_ground.py tests/test_ground_cover.py tests/test_v9_elements.py tests/test_lakes.py tests/test_lake_shore.py tests/test_water.py -q`
Expected: PASS.

---

### Task 6: Ferramentas (balance_sim e smoke) e o pytest inteiro

**Files:**
- Modify: `tools/dev/balance_sim.py` (~173, ~338–339, ~612, ~1157, ~1317)
- Modify: `tools/dev/smoke.py`: todo lugar que monta o estágio por Ti (`s.indices.update(o2=float(C.STAGES[stage - 1].ti), ...)` e o `set_stage`/`ti_in_window` por volta de ~907).
- Test: `tests/test_balance_sim.py`

**Interfaces:**
- Consumes: tudo de cima.

- [ ] **Step 1: Smoke monta biomassa junto**

No `tools/dev/smoke.py`, crie um helper perto do `ti_in_window` (~907):
```python
def reach_stage(s, stage: int, ti: float | None = None) -> None:
    """v0.8 M1: põe o Ti (no o2) e a biomassa mínima do estágio. `ti` troca o Ti (ex.: meio da janela)."""
    st = C.STAGES[stage - 1]
    s.indices.update(o2=float(st.ti if ti is None else ti), heat=0.0, water=0.0, biomass=float(st.biomass))
```
- Troque cada `s.indices.update(o2=float(C.STAGES[stage - 1].ti), heat=0.0, water=0.0)` (e as variantes com `C.ARID_STAGE`) por `reach_stage(s, stage)` ou `reach_stage(s, C.ARID_STAGE)`.
- Onde o Ti é calculado (`ti_in_window(...)`, `- value`), use `reach_stage(s, stage, ti=...)` e confira se a biomassa do estágio **alvo** também precisa entrar. Na janela antes do Verde, a biomassa precisa estar no meio também, senão a mancha não anda.
- As cenas de "verde" (`GREEN_STAGE`) passam a montar a biomassa de 15.000.
- As cenas por nome (`"nevoa"`) podem manter o nome do arquivo de print.
- Rode `grep -n "STAGES\[\|_STAGE" tools/dev/smoke.py tools/dev/shot_*.py` e revise cada ocorrência. Os `shot_*.py` antigos que montam o Verde também precisam da biomassa.

- [ ] **Step 2: balance_sim continua medindo o Ti**

O sim não produz biomassa (o cultivador é do M3). No M1 ele continua medindo **as marcas de Ti**:
- confira que o fim da simulação (`final_ti = C.STAGES[-1].ti`) depende do Ti e não de `gs.stage`. Se depender de `gs.stage`, troque pra Ti;
- `marks` (~339 e ~1157) passam a mostrar os 5 estágios depois da Tempestade pelo Ti. Os rótulos de Algas, Musgo e Verde ganham `" (Ti)"`, pra deixar claro que a biomassa ainda não entra;
- ~612 (`sum(1 for s in C.STAGES if s.ti <= ...)`) e ~1317 continuam iguais, mas confira o que eles contam com 6 estágios e ajuste se for pra continuar contando "até o Úmido";
- no `test_balance_sim.py`, ajuste só o que fixava 4 estágios.

Run: `uv run pytest tests/test_balance_sim.py -q && uv run python tools/dev/balance_sim.py > /tmp/balance_m1.log 2>&1; echo exit=$?`
Expected: PASS e `exit=0`.

- [ ] **Step 3: Varredura**

Run: `grep -rn "NÉVOA\|Névoa\|== 4\b\|GREEN_STAGE\|len(C.STAGES)" game/ tests/ tools/dev/ | grep -v "\.pyc"`
Revise cada linha:
- texto visível ao player que diz "Névoa" como **nome de estágio** vira "Úmido". Comentário de código pode ficar;
- número 4 que era "o Verde" vira a constante.

- [ ] **Step 4: pytest inteiro (background)**

Run: `uv run pytest -q > /tmp/pytest_m1.log 2>&1; echo exit=$?` (em background) e depois `tail -5 /tmp/pytest_m1.log`.
Expected: `exit=0`. Antes do M1 eram 1980 passed e 2 skipped, e o número sobe com os testes novos.

- [ ] **Step 5: Report**

Escreva `reports/dev/v08_m1.md` com:
- o que mudou por arquivo;
- os 4 prints e o que se vê neles;
- a saída do pytest;
- uma seção **"Diferente do plano"**, com tudo que precisou ser feito de outro jeito e por quê.

**Não commite.**
