# v0.7 Lore · Marco 2 · Props e scanner · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** props de 1 tile no mundo (21 do player + 3 de cenário), aba **Decoração** no construtor, scan com o esquerdo segurado num prop de ruína desconhecido, props nas 4 plantas, ícone novo do construtor.

**Arquitetura:**
- **`game/props.py`** (novo, Python puro): `Prop` (dataclass) e `face_visible` (a regra da face, usada pela ruína e pelo estado). Segue o molde de `Crate` e `BaseBlock`: objeto próprio, **não é `Machine`** (prop não entra em energia, índice, drone, luz nem na lista `machines`).
- `Layer.props: dict[tuple[int, int], Prop]`, uma por camada, chaveado pelo tile. O prop de face mora no tile da **parede**; o de chão e a mesa de parede, no tile de chão. Nunca dois no mesmo tile.
- Os props do player vão pro **menu do construtor como `MachineType`** (igual a `BASE_KINDS`: a receita e o ícone saem de `C.MACHINES[kind]`), aba nova `("decor", "Decoração")`. Construir um prop **cria um `Prop`**, não uma `Machine` (igual ao `_build_base`).
- **Prop de ruína** sai da seed (como a casca: `ruin=True`, recolocado no `apply_overlays`, nunca vai no save).
- **O que já foi escaneado**: `GameState.scanned: set[str]`. Conhecido = `C.PROP_STARTER | scanned`.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-v07-lore-design.md` (seção "M2"); bíblia §16, "Marco 2 · Props e scanner" (decisões do dono). Contrato da arte: `reports/design/v07_lore/index.html`, blocos "Pro Dev" (props: seção 4 da rodada 1; props de parede: rodada 2; mesas de parede: rodada 3).

## Restrições globais
- **Números de partida** (balanceamento depois), num bloco `# v0.7 M2 · Props e scanner` no fim do `game/config.py`:
  - `PROP_COST_SIMPLE = {"iron": 2}`; `PROP_COST_TECH = {"iron": 2, "silicon": 1}`.
  - `SCAN_HOLD = 1.5` (s segurando o esquerdo); `SCAN_REACH = PLACE_REACH`.
  - `RUIN_CHAIR_FALL = 0.5` (com destruição ≥ 1, chance de cada cadeira de ruína virar `prop_chair_fallen`).
- **Liberados de cara** (`PROP_STARTER`): `prop_table`, `prop_chair`, `prop_crate`, `prop_sign`.
- **Cenário de ruína** (`PROP_SCENERY`, não escaneia, não ganha contorno, não entra na aba nem no `MACHINES`): `prop_chair_fallen`, `prop_rubble`, `prop_ice_stain`.
- **Tabela dos props** (id = nome do PNG; nome em pt; custo; colide; onde vai):

  | id | nome | custo | colide | lugar |
  |---|---|---|---|---|
  | `prop_table` | Mesa | simples | sim | chão |
  | `prop_chair` | Cadeira | simples | não | chão |
  | `prop_crate` | Caixote | simples | sim | chão |
  | `prop_sign` | Placa de aviso | simples | não | chão |
  | `prop_barrel` | Barril | simples | sim | chão |
  | `prop_bunk` | Beliche | simples | sim | chão |
  | `prop_locker` | Armário | simples | sim | chão |
  | `prop_sample_shelf` | Estante de amostras | simples | sim | chão |
  | `prop_dead_plant` | Vaso com planta seca | simples | não | chão |
  | `prop_lab_bench` | Bancada de laboratório | tech | sim | chão |
  | `prop_microscope` | Microscópio | tech | sim | chão |
  | `prop_console` | Console | tech | sim | chão |
  | `prop_sample_tank` | Tanque de amostra | tech | sim | chão |
  | `prop_wall_desk_a` | Bancada de parede | simples | sim | mesa (tile de cima é parede) |
  | `prop_wall_desk_b` | Escrivaninha de parede | simples | sim | mesa |
  | `wall_monitor_on` | Monitor | tech | não | face |
  | `wall_monitor_off` | Monitor apagado | tech | não | face |
  | `wall_bp_plan` | Diagrama da base | simples | não | face |
  | `wall_bp_ship` | Diagrama da nave | simples | não | face |
  | `wall_bp_ice` | Diagrama do cristal | simples | não | face |
  | `wall_notice` | Quadro de avisos | simples | não | face |
  | `prop_chair_fallen` | Cadeira caída | - | não | chão (cenário) |
  | `prop_rubble` | Entulho | - | sim | chão (cenário) |
  | `prop_ice_stain` | Mancha de gelo | - | não | decal (cenário) |
- **Desenho** (contrato da Designer, 1:1, sem mudar arte):
  - chão e mesa: PNG 32×40, blit `(tx·32, ty·32 − 8)`, ordenado pelo pé `ay = (ty+1)·32` junto dos outros objetos (como o baú). Colisão de quem colide: `(tx·32+4, ty·32+14, 24, 18)`; **as 2 mesas de parede colidem no tile inteiro**.
  - decal (`prop_ice_stain`): 32×32, blit `(tx·32, ty·32)`, desenhado com o chão, antes dos objetos.
  - face (`wall_*`): 32×24, blit `(tx·32, ty·32 + 8)` no tile da parede, logo depois da face da parede.
  - nenhum prop emite luz.
- **Assets**: a arte foi aprovada pelo dono. A Task 1 copia de `reports/design/v07_lore/pendentes/` pra `assets/sprites/`, mesmo nome: os 16 `prop_*.png`, os 2 `prop_wall_desk_{a,b}.png`, os 6 `wall_*.png` e os `icon_` de cada um; e `r5_icon_constructor_A.png` vira `assets/sprites/icon_constructor.png` (troca). Fora isso, não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` e `settings.json`.
- **Som**: o código toca `scan_loop` (enquanto segura, num canal, para no cancel/fim) e `scan_done`. Os arquivos chegam depois pelo agente `som` (com aprovação do dono). Sem arquivo, `audio.play` não toca nada: está certo assim. Volumes em `VOLUME`: `scan_loop` 0.4 e `scan_done` 0.6.
- **Save continua v12**, com campos opcionais: `"scanned": [kinds]` no topo e `"props": [[kind, x, y], ...]` por camada (só os do player). Prop de ruína nunca vai no save. Save sem esses campos carrega com `scanned` vazio e sem props.
- A fonte do jogo **não tem "→"**: em texto use ":" ou palavra.
- **Sem cena nova no smoke** (regra do dono). Prints avulsos em `tools/dev/shot_v07_m2.py` (Task 5). **Antes do fim, varra o `tools/dev/smoke.py`** atrás de suposições que o M2 muda: lista e índice das abas do construtor (`FAB_TABS`), clique esquerdo com o construtor na mão, contagem de objetos perto das ruínas.
- Não abrir janela e não commitar. No fim: `uv run pytest`. O gerente roda o smoke e o `real_video_check` no merge.

## Decisões (o dono deveria ver)
- **Colisão segue a tabela da Designer**: o microscópio colide (fica numa bancadinha própria no sprite).
- **Prop de chão da planta que, depois do giro, cai colado numa parede ao sul some** (a face da parede cobriria 24 px dele). Do mesmo jeito somem a mesa de parede sem parede em cima e o prop de face cuja parede ficou sem chão embaixo. É determinístico (mesma seed, mesma ruína). Pro player não tem a regra da parede ao sul (é só visual; ele decide).
- **Desmontar uma parede da base com prop de face devolve os dois** (tudo ou nada no inventário).
- **Prop do player não vai em veio** (o veio fica livre pra drill, como a máquina), nem na água, no gelo do portão, na cápsula ou na pegada de ruína.
- **Máquina e bloco da base não entram em tile com prop.** Tirar o chão da base debaixo de um prop deixa o prop (ele fica no chão do mundo).
- A cadeira de ruína **tomba** (vira `prop_chair_fallen`) com chance `RUIN_CHAIR_FALL` se a destruição for ≥ 1.

---

## Estrutura de arquivos

| Arquivo | O quê |
|---|---|
| `game/props.py` | **novo** · `Prop`, `face_visible` |
| `game/config.py` | bloco "v0.7 M2": `PROPS`, `PROP_STARTER`, `PROP_SCENERY`, custos, `SCAN_*`, `RUIN_CHAIR_FALL`, `MachineType` dos props, aba `decor`, `VOLUME` |
| `game/ruin_plans/*.txt` | letras de prop nas 4 plantas |
| `game/ruins.py` | lê as letras de prop; `Ruin.props`; extrai e valida depois do giro; parede com prop de face não cai; tomba cadeira; `apply_overlays` põe os props de ruína |
| `game/layers.py` | `Layer.props` |
| `game/systems.py` | `scanned`, `known_props`, `prop_at`, `can_place`/`build`/`dismantle` de prop, colisão, `_update_scan`, `Controls.scan` |
| `game/fabricator.py` | `build_kinds` filtra a aba `decor` pelos conhecidos |
| `game/save.py` | `scanned` e `props` |
| `game/app.py` | menu com filtro, esquerdo segurado vira scan, eventos (aviso, som) |
| `game/render.py` | desenho dos props (chão, decal, face), fantasma, contorno, barrinha |
| `game/ui.py` | dica "Escanear (segure)" (se a dica de hover mora lá) |
| `assets/sprites/` | PNGs promovidos (Task 1) |
| `tests/test_props.py` | **novo** · regras |
| `tools/dev/shot_v07_m2.py` | **novo** · prints |

---

### Task 1: Config, `Prop` e assets

**Files:**
- Create: `game/props.py`, `tests/test_props.py`
- Modify: `game/config.py` (fim do arquivo), `game/layers.py` (`Layer`)
- Copy: PNGs (ver Restrições globais, "Assets")

**Interfaces:**
- Produces:
  - `C.PROPS: dict[str, PropType]`. `PropType` é um `NamedTuple(kind: str, name: str, cost: dict, solid: bool, place: str, scannable: bool)`, com `place` em `"floor" | "desk" | "face" | "decal"`. Tem as 24 linhas da tabela; `scannable` é falso pros 4 de `PROP_STARTER` e os 3 de `PROP_SCENERY`.
  - `C.PROP_STARTER: tuple[str, ...]`, `C.PROP_SCENERY: tuple[str, ...]`, `C.PLAYER_PROPS: tuple[str, ...]` (os 21 que não são cenário, na ordem da tabela).
  - `C.MACHINES[k]` pra cada `k` de `PLAYER_PROPS`: `MachineType(k, name, desc, cost, None, 0, 0, "icon_" + k)`, com `MACHINE_ORDER.append(k)` e `MACHINE_CATEGORY[k] = "decor"`. O `desc` é `"decoração"`, ou `"decoração · na parede"` pros de face e de mesa.
  - `C.FAB_TABS = C.FAB_TABS + (("decor", "Decoração"),)`, sempre a última aba (o índice das outras não muda).
  - `props.Prop` (dataclass): `kind: str`, `tx: int`, `ty: int`, `ruin: bool = False`. Propriedades: `tile`, `type` (`C.PROPS[kind]`), `place`, `solid`, e `rect` (a caixa de colisão em px, ou `None` se não colide; a mesa colide no tile inteiro).
  - `props.face_visible(is_wallish, tx, ty) -> bool`: a parede em `(tx, ty)` mostra face, ou seja, o tile de baixo não é parede. `is_wallish` é `callable(tx, ty) -> bool`.
  - `Layer.props: dict` (`field(default_factory=dict)`).

- [ ] **Step 1: teste que falha**

```python
# tests/test_props.py
from game import config as C
from game.props import Prop, face_visible


def test_tabela_de_props():
    assert len(C.PROPS) == 24
    assert set(C.PROP_STARTER) == {"prop_table", "prop_chair", "prop_crate", "prop_sign"}
    assert set(C.PROP_SCENERY) == {"prop_chair_fallen", "prop_rubble", "prop_ice_stain"}
    assert len(C.PLAYER_PROPS) == 21
    for k in C.PROP_STARTER + C.PROP_SCENERY:
        assert not C.PROPS[k].scannable
    assert C.PROPS["prop_dead_plant"].scannable
    assert C.PROPS["wall_bp_ice"].scannable and C.PROPS["wall_bp_ice"].place == "face"
    assert C.PROPS["prop_wall_desk_a"].place == "desk"
    assert C.PROPS["prop_ice_stain"].place == "decal"


def test_custos():
    tech = {"prop_lab_bench", "prop_microscope", "prop_console", "prop_sample_tank",
            "wall_monitor_on", "wall_monitor_off"}
    for k in C.PLAYER_PROPS:
        want = {"iron": 2, "silicon": 1} if k in tech else {"iron": 2}
        assert C.MACHINES[k].cost == want, k
        assert C.MACHINE_CATEGORY[k] == "decor"
    for k in C.PROP_SCENERY:
        assert k not in C.MACHINES


def test_aba_decoracao_e_a_ultima():
    assert C.FAB_TABS[-1] == ("decor", "Decoração")


def test_colisao():
    assert Prop("prop_table", 3, 4).rect == (3 * 32 + 4, 4 * 32 + 14, 24, 18)
    assert Prop("prop_wall_desk_b", 3, 4).rect == (96, 128, 32, 32)
    for k in ("prop_chair", "prop_sign", "prop_dead_plant", "prop_chair_fallen", "prop_ice_stain", "wall_notice"):
        assert Prop(k, 0, 0).rect is None, k
    assert Prop("prop_microscope", 0, 0).rect is not None


def test_face_visivel():
    walls = {(5, 5), (5, 6)}
    is_wall = lambda x, y: (x, y) in walls
    assert not face_visible(is_wall, 5, 5)   # parede embaixo: sem face
    assert face_visible(is_wall, 5, 6)


def test_assets_promovidos():
    from pathlib import Path
    sprites = Path("assets/sprites")
    for k in C.PROPS:
        assert (sprites / f"{k}.png").exists(), k
        if k in C.PLAYER_PROPS:
            assert (sprites / f"icon_{k}.png").exists(), k
```

- [ ] **Step 2:** `uv run pytest tests/test_props.py -v`. Esperado: FAIL (`game.props` não existe).
- [ ] **Step 3:** copiar os PNGs (`cp reports/design/v07_lore/pendentes/{prop_,icon_prop_,wall_,icon_wall_}*.png assets/sprites/` e `cp reports/design/v07_lore/pendentes/r5_icon_constructor_A.png assets/sprites/icon_constructor.png`). Escrever o bloco do config e o `game/props.py`. Antes, conferir com `python3 -c "import pygame;print(pygame.image.load(...).get_size())"` que os tamanhos batem: 32×40 pro chão e a mesa, 32×32 pro decal, 32×24 pra face, 16×16 pros ícones.
- [ ] **Step 4:** `uv run pytest tests/test_props.py -v`: PASS. Depois `uv run pytest`, tudo verde. Se algum teste antigo contar abas ou receitas do construtor, ajuste o número e explique no relatório.

---

### Task 2: Props nas plantas das ruínas

**Files:**
- Modify: `game/ruins.py`, `game/ruin_plans/{camp,lab,melters,drill_post}.txt`, `game/layers.py` (se o `apply_overlays` precisar), `tests/test_ruins.py`

**Interfaces:**
- Consumes: `C.PROPS`, `props.Prop`, `props.face_visible`, `Layer.props`.
- Produces:
  - Na legenda da planta, uma letra cujo valor é um id de `C.PROPS` é prop: `Plan.props: dict[str, str]` (letra → kind). As outras letras continuam em `Plan.machines`. Na grade, a letra de prop de **face** fica no lugar de uma parede (conta como `#`); as outras ficam no lugar de um chão (contam como `.`).
  - `Ruin.props: dict[tuple[int, int], str]` (tile → kind), deslocado no `moved` como `machines`.
  - `ruins.ok_in_plan(grid, x, y, kind) -> bool` (em `ruins.py`, é regra de planta): chão e decal valem se o tile de baixo não é casca; mesa vale se o tile de cima é casca e o de baixo não; face vale se o tile de baixo é chão.
  - `apply_overlays` põe em `layer.props` um `Prop(kind, *t, ruin=True)` por prop de ruína (tira os `ruin` antes, pra ser idempotente). Ruína em `ruins_off` não ganha props.

**Ordem dentro do `build()`:**
1. `transform`;
2. `_reseat_terminals` (o `_is_floor` e o `WALLISH` passam a reconhecer as letras de prop);
3. **extrai os props**: troca cada letra pelo caractere base (`#` ou `.`), guarda `{(x, y): kind}` e descarta quem falha no `ok_in_plan`;
4. `_damage`, que não derruba parede com prop de face (o tile entra num conjunto `protected`);
5. tomba as cadeiras: com `level >= 1`, percorre os props em ordem `(y, x)` e cada `prop_chair` vira `prop_chair_fallen` se `rng.random() < C.RUIN_CHAIR_FALL`;
6. `_connected`: prop que colide bloqueia a passagem, o que não colide não bloqueia.

Os sorteios do passo 5 vêm **depois** dos da destruição, então o sorteio das ruínas do M1 não muda.

**Plantas:** cada planta ganha 5 a 10 props que contam a história dela, sem pôr prop na fileira colada na parede sul (orientação 0) e com a mesa de parede logo abaixo de uma parede. Sugestão (o Dev ajusta pra caber):
- **acampamento**: beliche, armário, mesa, cadeira, barril, caixote, placa, planta seca, quadro de avisos;
- **laboratório**: bancada, microscópio, estante de amostras, tanque de amostra, mancha de gelo, console, cadeira, diagrama do cristal, monitor apagado;
- **derretedores**: bancada, armário, barril, mancha de gelo, entulho, diagrama da base, mesa de parede com monitor;
- **posto de perfuração**: console, armário, barril, caixote, entulho, diagrama da nave, mesa de parede, monitor.

**Entre as 4 plantas, todo prop escaneável aparece pelo menos uma vez.** Senão, ele nunca seria liberado.

- [ ] **Step 1: testes que falham** (em `tests/test_ruins.py`):

```python
from game import config as C, ruins


def test_planta_le_props():
    plans = [ruins.load_plan(k) for k in ruins.PLAN_KEYS]
    for p in plans:
        assert p.props, p.key
        assert all(k in C.PROPS for k in p.props.values())
        assert not set(p.props) & set(p.machines)
    seen = {k for p in plans for k in p.props.values()}
    scannable = {k for k, t in C.PROPS.items() if t.scannable}
    assert scannable <= seen


def test_props_validos_em_toda_orientacao():
    import random
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        for orient in range(8):
            for level in C.RUIN_DAMAGE_LEVELS:
                ruin = ruins.build(plan, orient, level, random.Random(orient * 10 + level))
                if ruin is None:
                    continue
                for (x, y), kind in ruin.props.items():
                    assert ruins.ok_in_plan(ruin.grid, x, y, kind), (key, orient, (x, y), kind)
                    if C.PROPS[kind].place == "face":
                        assert ruin.grid[y][x] in "#", (key, orient)     # a parede com quadro não caiu
                    else:
                        assert ruin.grid[y][x] == ".", (key, orient)


def test_cadeira_so_tomba_com_destruicao():
    import random
    for key in ruins.PLAN_KEYS:
        plan = ruins.load_plan(key)
        ruin = ruins.build(plan, 0, 0, random.Random(1))
        assert "prop_chair_fallen" not in ruin.props.values()


def test_mesma_seed_mesmos_props():
    from game.layers import make_surface   # use o mesmo helper de mundo que os testes do M1 já usam
    a = {t: p.kind for t, p in make_surface(7).props.items()}
    b = {t: p.kind for t, p in make_surface(7).props.items()}
    assert a == b and a
    assert all(p.ruin for p in make_surface(7).props.values())
```

(Se `make_surface` tiver outra assinatura, use o helper de `tests/test_ruins.py` que o M1 já usa pra montar a camada da seed.)

- [ ] **Step 2:** `uv run pytest tests/test_ruins.py -v`. Esperado: FAIL.
- [ ] **Step 3:** implementar na ordem acima e desenhar as letras nas plantas.
- [ ] **Step 4:** `uv run pytest tests/test_ruins.py -v`: PASS. Também passam os testes do M1: "mesma seed, mesmas ruínas", caminho garantido e terminal reassentado. `uv run pytest` verde.

---

### Task 3: Estado: conhecer, colocar, colidir, desmontar e salvar

**Files:**
- Modify: `game/systems.py`, `game/fabricator.py`, `game/save.py`, `tests/test_props.py`

**Interfaces:**
- Consumes: Tasks 1 e 2.
- Produces:
  - `GameState.scanned: set[str]` (começa vazio) e `GameState.known_props() -> set[str]` (`set(C.PROP_STARTER) | self.scanned`).
  - `GameState.props` (property: `self.active.props`) e `GameState.prop_at(tile) -> Prop | None`.
  - `recipe_status(kind)`: prop do player desconhecido devolve `"blueprint"`. Então `can_build` dá `False` sem mudar mais nada.
  - `can_place(kind, tile)` pra prop despacha pra `_can_place_prop(kind, tile)`:
    - **chão/mesa**: `world.is_floor` (ou chão da base), sem máquina, sem prop, sem barreira da base (`base.is_barrier`), fora de `world.ruin_tiles`, de veio, da água, do gelo do portão e da cápsula; dentro de `PLACE_REACH`; o player não está no tile; se colide, não prende o player (`overlaps(player.box, rect)`);
    - a **mesa** também exige que o tile de cima seja uma `base_wall` do player;
    - **face**: o tile é uma `base_wall` do player (não `ruin`, não porta), `face_visible`, sem prop nele; dentro de `PLACE_REACH`.
  - `build(kind, tile)` pra prop: gasta a receita, cria `Prop(kind, *tile)` em `layer.props` e emite `("build", kind, tile)`. Não cria `Machine`.
  - `can_place` de máquina e de bloco da base recusa tile com prop.
  - `solids_near` soma o `rect` de cada prop sólido do recorte.
  - `can_dismantle(prop)`: `not prop.ruin`, o prop está em `layer.props` e dentro de `PLACE_REACH`. `dismantle(prop)` devolve `C.MACHINES[kind].cost` (tudo ou nada) e tira o prop. `_dismantle_block` de uma parede com prop de face devolve as duas receitas juntas (tudo ou nada) e tira os dois.
  - `GameState.prop_at_point(px, py) -> Prop | None`: o prop debaixo do ponto do mundo. Pro de chão e mesa, a caixa visual é 32×40 a partir de `(tx·32, ty·32 − 8)`; pro de face, a face `(tx·32, ty·32 + 8, 32, 24)`; o decal ocupa o tile.
  - `fabricator.build_kinds(tab_id, known=None)`: na aba `decor`, só os de `known` (na ordem de `PLAYER_PROPS`). O App monta o menu com `kinds_of=lambda t: build_kinds(t, self.state.known_props())`, e o menu tem que continuar certo depois de carregar outro save.
  - **Save**: `"scanned": sorted(state.scanned)` e `"props": [[kind, x, y], ...]` por camada (só `not p.ruin`). No load, ignora kind fora de `C.PLAYER_PROPS` / `C.PROPS`. Os props de ruína voltam pelo `apply_overlays`, que já roda depois do load.

- [ ] **Step 1: testes que falham** (em `tests/test_props.py`). Use o helper de estado que os testes do construtor já usam (`tests/helpers.py` / `tests/test_constructor.py`: um `GameState` com construtor no inventário e o player num chão livre):

```python
def test_desconhecido_nao_constroi(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 10)
    tile = (s.player.tile[0] + 2, s.player.tile[1])
    assert s.recipe_status("prop_bunk", inv_only=True) == "blueprint"
    assert not s.build("prop_bunk", tile)
    s.scanned.add("prop_bunk")
    assert s.build("prop_bunk", tile)
    assert s.prop_at(tile).kind == "prop_bunk" and not s.prop_at(tile).ruin
    assert s.inventory.count("iron") == 8


def test_prop_bloqueia_maquina_e_colide(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 50); s.inventory.add("silicon", 50)
    tile = (s.player.tile[0] + 2, s.player.tile[1])
    assert s.build("prop_table", tile)
    assert not s.can_place("o2", tile)
    box = (tile[0] * 32, tile[1] * 32, 32, 32)
    assert any(r == s.prop_at(tile).rect for r in s.solids_near(box))


def test_cadeira_nao_colide(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 10)
    tile = (s.player.tile[0] + 2, s.player.tile[1])
    assert s.build("prop_chair", tile)
    box = (tile[0] * 32, tile[1] * 32, 32, 32)
    assert all(r != (tile[0] * 32 + 4, tile[1] * 32 + 14, 24, 18) for r in s.solids_near(box))


def test_desmonta_prop_do_player_devolve_custo(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 2)
    tile = (s.player.tile[0] + 2, s.player.tile[1])
    s.build("prop_crate", tile)
    assert s.inventory.count("iron") == 0
    assert s.dismantle(s.prop_at(tile))
    assert s.prop_at(tile) is None and s.inventory.count("iron") == 2


def test_prop_de_ruina_nao_desmonta():
    from game.props import Prop
    s = make_state_seed7()          # helper que monta o GameState da seed 7 (o de test_ruins.py)
    prop = next(iter(s.active.props.values()))
    assert prop.ruin and not s.can_dismantle(prop)


def test_face_so_em_parede_do_player_com_face(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 50); s.inventory.add("silicon", 50)
    px, py = s.player.tile
    wall, below = (px + 2, py - 1), (px + 2, py)
    assert not s.can_place("wall_notice", wall)            # sem parede
    s.build("base_wall", wall)
    s.scanned.add("wall_notice")
    assert s.can_place("wall_notice", wall)
    s.build("base_wall", below)                            # parede embaixo: a de cima perde a face
    assert not s.can_place("wall_notice", wall)


def test_mesa_de_parede_precisa_de_parede_em_cima(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 50)
    s.scanned.add("prop_wall_desk_a")
    px, py = s.player.tile
    tile = (px + 2, py)
    assert not s.can_place("prop_wall_desk_a", tile)
    s.build("base_wall", (px + 2, py - 1))
    assert s.can_place("prop_wall_desk_a", tile)


def test_desmontar_parede_leva_o_quadro(state_with_constructor):
    s = state_with_constructor
    s.inventory.add("iron", 4)
    px, py = s.player.tile
    wall = (px + 2, py - 1)
    s.build("base_wall", wall)
    s.scanned.add("wall_notice")
    s.build("wall_notice", wall)
    assert s.inventory.count("iron") == 0
    assert s.dismantle(s.block_at(wall))         # use o acesso a bloco que o código já tem
    assert s.prop_at(wall) is None and s.inventory.count("iron") == 4


def test_menu_decoracao_so_conhecidos():
    from game.fabricator import build_kinds
    assert build_kinds("decor", {"prop_table", "prop_chair", "prop_crate", "prop_sign"}) == \
        ["prop_table", "prop_chair", "prop_crate", "prop_sign"]
    assert "prop_bunk" in build_kinds("decor", {"prop_bunk"})


def test_save_props_e_scanned(state_with_constructor, tmp_path):
    from game import save
    s = state_with_constructor
    s.inventory.add("iron", 10)
    tile = (s.player.tile[0] + 2, s.player.tile[1])
    s.build("prop_table", tile)
    s.scanned.add("prop_bunk")
    data = save.to_dict(s)                       # use as funções de ida e volta que o test_save.py usa
    t = save.from_dict(data)
    assert t.scanned == {"prop_bunk"}
    assert t.prop_at(tile).kind == "prop_table"
    assert all(not p.ruin for p in t.active.props.values() if p.tile == tile)
    assert data["version"] == 12


def test_save_antigo_sem_campos(state_with_constructor):
    from game import save
    data = save.to_dict(state_with_constructor)
    data.pop("scanned", None)
    for layer in data.get("layers", {}).values():
        layer.pop("props", None)
    t = save.from_dict(data)
    assert t.scanned == set()
```

Os nomes `state_with_constructor`, `make_state_seed7`, `save.to_dict`, `save.from_dict` e `s.block_at` são de referência. **Use os fixtures e as funções que existem** (procure em `tests/helpers.py`, `tests/test_constructor.py`, `tests/test_base.py`, `tests/test_save.py`, `tests/test_ruins.py`) e mantenha o que cada teste verifica.

- [ ] **Step 2:** `uv run pytest tests/test_props.py -v`. Esperado: FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** `uv run pytest tests/test_props.py -v` PASS e `uv run pytest` verde.

---

### Task 4: Scan

**Files:**
- Modify: `game/systems.py`, `tests/test_props.py`

**Interfaces:**
- Consumes: Task 3.
- Produces:
  - `Controls.scan: Prop | None = None` (o prop debaixo do mouse com o esquerdo segurado; quem preenche é o App).
  - `GameState.can_scan(prop) -> bool`: `prop.ruin`, `C.PROPS[prop.kind].scannable`, `prop.kind not in self.known_props()`, o prop em `layer.props` e Chebyshev do player ao tile `<= C.SCAN_REACH`.
  - `GameState.scanning: Prop | None`, `GameState.scan_t: float`.
  - `GameState._update_scan(target, dt)`, no mesmo molde do `_update_dismantle`:
    - alvo válido novo emite `("scan_charge",)` e começa a contar;
    - o mesmo alvo soma `dt`;
    - com `scan_t >= C.SCAN_HOLD`, faz `scanned.add(kind)`, emite `("scan_done", kind)` e zera;
    - alvo `None`, outro alvo ou alvo inválido no meio da carga emite `("scan_cancel",)` e zera;
    - roda no `update` junto do `_update_dismantle` (e também no desmaio e na rampa, com `None`).

- [ ] **Step 1: testes que falham:**

```python
def test_scan_libera_depois_de_segurar():
    s = make_state_seed7()
    prop = next(p for p in s.active.props.values() if C.PROPS[p.kind].scannable)
    s.player.x, s.player.y = prop.tx * 32 + 16, (prop.ty + 2) * 32 + 16    # perto (ajuste ao campo de posição do Player)
    assert s.can_scan(prop)
    s._update_scan(prop, 1.0)
    assert ("scan_charge",) in s.pop_events()
    assert prop.kind not in s.scanned
    s._update_scan(prop, 0.6)
    assert ("scan_done", prop.kind) in s.pop_events()
    assert prop.kind in s.scanned and not s.can_scan(prop)


def test_soltar_cancela():
    s = make_state_seed7()
    prop = next(p for p in s.active.props.values() if C.PROPS[p.kind].scannable)
    s.player.x, s.player.y = prop.tx * 32 + 16, (prop.ty + 2) * 32 + 16
    s._update_scan(prop, 1.0)
    s._update_scan(None, 0.1)
    assert ("scan_cancel",) in s.pop_events()
    s._update_scan(prop, 1.0)
    assert prop.kind not in s.scanned       # recomeçou do zero


def test_cenario_conhecido_e_do_player_nao_escaneiam(state_with_constructor):
    from game.props import Prop
    s = make_state_seed7()
    for kind in C.PROP_SCENERY + C.PROP_STARTER:
        assert not s.can_scan(Prop(kind, 0, 0, ruin=True))
    player_prop = Prop("prop_bunk", 0, 0, ruin=False)
    assert not s.can_scan(player_prop)


def test_longe_nao_escaneia():
    s = make_state_seed7()
    prop = next(p for p in s.active.props.values() if C.PROPS[p.kind].scannable)
    s.player.x, s.player.y = (prop.tx + 20) * 32, prop.ty * 32
    assert not s.can_scan(prop)
```

- [ ] **Step 2:** `uv run pytest tests/test_props.py -v`. Esperado: FAIL.
- [ ] **Step 3:** implementar.
- [ ] **Step 4:** PASS e `uv run pytest` verde.

---

### Task 5: App, desenho e prints

**Files:**
- Modify: `game/app.py`, `game/render.py`, `game/ui.py` (se a dica de hover mora lá), `game/fabricator.py` (se precisar)
- Create: `tools/dev/shot_v07_m2.py`
- Test: `tests/test_props.py` (o que der pra testar sem janela)

**O que fazer:**

**Menu**
- O `build_menu` usa o filtro de conhecidos (Task 3).
- Na aba Decoração, o ícone de cada receita é o `icon_<kind>`.
- Escolher um prop entra no modo de colocar, igual a uma máquina.

**Fantasma**
- O sprite do prop em `place_target()`, verde ou vermelho pelo `can_build`.
- O de face aparece na face da parede debaixo do mouse.
- O `R` não gira prop.

**Clique**
- No modo de colocar, o esquerdo constrói, como hoje.
- Sem fantasma, com o construtor na mão: o esquerdo segurado preenche `Controls.scan = state.prop_at_point(*mouse_world())`. O `mine` continua só com a broca.
- O direito segurado: `dismantle` também considera `state.prop_at_point(...)`. A prioridade é prop > máquina > bloco > caixa, pra o quadro na parede sair antes da parede.

**Eventos**
- `scan_charge` toca `scan_loop` num canal guardado.
- `scan_cancel` para esse canal.
- `scan_done` para o canal, toca `scan_done` e mostra `show_notice(f"Projeto liberado: {nome}")`.
- `build` e `dismantle` de prop usam os sons que já existem pra máquina.

**Desenho**
- Os props de chão e as mesas entram na mesma lista ordenada pelo pé que o baú usa.
- O decal vai junto do chão.
- O de face vai logo depois da face da parede dele. Use o caminho do `_draw_ruin_terminal`, que já desenha na face.
- Com o construtor na mão e sem fantasma, o prop debaixo do mouse que `can_scan` ganha contorno (`outline_of`, o mesmo do hover de máquina) e a dica "Escanear (segure)".
- Enquanto carrega, aparece a barrinha no estilo da do desmonte (`state.scan_t / C.SCAN_HOLD`).
- Prop conhecido ou de cenário não ganha contorno nem dica.

**Prints**
- `tools/dev/shot_v07_m2.py` (molde: `tools/dev/shot_v07_m1.py`) salva em `reports/dev/v07_m2/`:
  1. cada uma das 4 ruínas com os props;
  2. uma base do player com uns 8 props (de chão, mesa e face);
  3. o contorno com a dica num prop de ruína;
  4. a barrinha no meio do scan;
  5. a aba Decoração com só os 4 de cara, e com mais 3 depois do scan;
  6. o fantasma verde e o vermelho de um prop de face.

**Varredura do smoke**
- Grep em `tools/dev/smoke.py` por `FAB_TABS`, `build_menu`, `set_tab`, aba por índice, `MOUSEBUTTONDOWN`/botão 1 com o construtor e cenas perto das ruínas.
- Ajuste o que quebraria e diga o que mudou no relatório.

- [ ] **Step 1:** teste sem janela de que o menu muda depois do scan (o `build_menu` pede a aba `decor` e recebe mais um kind depois de `state.scanned.add(...)`), no molde dos testes de app que já existem (`tests/test_base_app.py`).
- [ ] **Step 2:** implementar.
- [ ] **Step 3:** `uv run pytest` verde e `uv run python tools/dev/shot_v07_m2.py`; **olhar os prints** e conferir os 6 itens acima.
- [ ] **Step 4:** relatório final ao gerente com:
  - o que ficou fora do plano;
  - os ajustes do smoke;
  - os caminhos dos prints;
  - qualquer decisão tomada sozinho (ela entra na bíblia §16, "Marco 2 · como ficou").
