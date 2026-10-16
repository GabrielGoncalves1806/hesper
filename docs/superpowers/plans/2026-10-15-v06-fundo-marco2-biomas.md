# v0.6 Fundo · Marco 2 · Cara dos biomas · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** a caverna ganha a arte aprovada do M2. O chão é assado como o da superfície, com divisa curva por pixel e decalques por região. A rocha usa uma rampa de cor por região, e a cor troca pela mesma curva do chão, sem escadinha por tile. A luz ambiente e a lanterna do capacete mudam suavemente com a região do player. A tinta provisória do M1 sai.

**Arquitetura:** reaproveitar o motor do chão da superfície (`game/ground.py`) sem duplicar. Um módulo novo, `game/cave_ground.py`, traz:
- `CaveArt`, a arte da caverna no lugar da `RegionArt`: 4 classes, sem leito, sem estágio, sem cobertura;
- `CaveGeo`, o mínimo que o `bake_strip` pede de um geo;
- `CaveGround`, uma subclasse de `ground.Ground` que troca só o que depende de estágio ou de superfície.

A rocha (`game/cave_rocks.py`) passa a ler as 4 rampas de um JSON e calcula a região **por pixel** com o mesmo `geo.warp_px` do chão. A luz por região é um módulo novo, `game/cave_light.py`, puro e testável, e o `Renderer` só consulta.

**Stack:** Python 3.13, pygame-ce, numpy, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-v06-fundo-design.md` (M2). Bíblia §15. Arte aprovada: `reports/design/v06_fundo_m2_biomas/index.html` (leia as seções **0, 5, 6 e 7**; a 7 é o contrato pro Dev).

## Restrições globais
- **Arte já aprovada pelo dono.** A promoção pra `assets/sprites/cave_ground/` faz parte da Task 1 (cópia simples, sem redesenhar nada). Não editar PNG nem JSON da arte, só copiar e renomear como está na Task 1.
- **A luz fica como no `luz.json`**, e o basalto continua avermelhado (`ambient [34, 10, 5]`). O dono decidiu: "mantém o vermelho pro ar de quente".
- Não mexer em `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `assets/audio`, `saves/` e `settings.json`. Em `assets/` só entra a pasta nova `assets/sprites/cave_ground/`.
- **Save continua v12.** Nada do M2 vai pro save: região, chão e luz saem da seed.
- **Sem cena nova no smoke** (regra do dono). O print avulso fica em `tools/dev/shot_v06_fundo_m2.py`.
- Desempenho: o smoke tem que continuar no orçamento. Hoje a média é ~6 ms e o p95 ~11 ms. Assar um bloco do chão leva ~100 ms e vai por faixas (`C.GROUND_BAKE_MS`). Se o smoke estourar o "caverna escura no zoom 0,75" num ponto só, rode de novo antes de chamar de regressão.
- Sem arte (pasta ausente): a caverna volta pro chão por tile `floor_mist_*` **sem tinta** e pra rocha com a rampa única de hoje, sem crash.
- Não abrir janela e não commitar. No fim: `uv run pytest`, `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py`.

## Decisões (o dono deveria ver)
- **A divisa da rocha** segue a curva do chão. Cada pixel do topo pega a região do chão em `(x + dx, y + LIFT + dy)`, e a face pega a região do tile dono, na mesma curva. Assim a cor muda no meio do tile, junto com o chão.
- **A luz** é uma média das regiões numa janela de 5×5 tiles em volta do player (`C.CAVE_LIGHT_SAMPLE_R = 2`), suavizada no tempo com τ = 0,5 s (`C.CAVE_LIGHT_TAU`). A cor do capacete é arredondada de 8 em 8, pra o cache de texturas de luz não crescer sem limite.
- **Decalques do chão:** nenhum num raio de 6 tiles em volta da chegada (`C.CAVE_DECAL_CLEAR = 6`). A caverna não tem decoração solta com altura, porque ninguém pediu.
- **Minimapa:** o chão de cada região usa a cor base (índice 3) da paleta assada. A rocha fica como está.
- **Som do M2:** é um report separado do agente Som e **não está neste plano**. Se o dono aprovar, vira uma task extra (escolher `amb_cave_<região>` pela região do player com histerese).

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `assets/sprites/cave_ground/` (novo) | 4 `ground_cave_*.png`, 46 `decal_*.png`, `cave_ground_palettes.json`, `cave_rock_ramps.json` (= `ramps.json`), `cave_light.json` (= `luz.json`) |
| `game/config.py` | `CAVE_GROUND_DIR`, `CAVE_DECAL_CLEAR`, `CAVE_LIGHT_SAMPLE_R`, `CAVE_LIGHT_TAU`; **sai** o `CAVE_REGION_TINT` |
| `game/ground.py` | `bake_strip` pula a cobertura quando `art.cover` é False (1 linha) |
| `game/cave_ground.py` (novo) | `CaveArt`, `CaveGeo`, `arrival_skip`, `CaveGround` |
| `game/cave_rocks.py` | `load_ramps`, `cave_luts` com as 4 rampas, `pixel_regions`, `CaveRocks.strips` usa a região por pixel |
| `game/cave_light.py` (novo) | `load`, `region_weights`, `blend`, `CaveLight` |
| `game/lighting.py` | `helmet_lamp(..., color, intensity)` |
| `game/render.py` | `cave_ground` + `cave_geo`, `draw_floors` com o chão assado na caverna, sem `region_tint`, `cave_lights(state, helmet, intensity)`, `draw_cave_darkness` com ambiente, `sync` também na caverna |
| `game/minimap.py` | `CAVE_REGION_COLORS` sai da paleta assada (com fallback) |
| `tools/dev/shot_v06_fundo_m2.py` (novo) | print avulso: 5 fronteiras, claro e escuro, mais o tempo do assado |
| `docs/GAME_BIBLE.md` | §15 "Marco 2 · como ficou" |
| `tests/test_cave_ground.py` (novo) | arte, assado, divisa, decalques, fallback, render |
| `tests/test_cave_rocks.py` | rampas por região e região por pixel |
| `tests/test_cave_light.py` (novo) | pesos, mistura, suavização, quantização |
| `tests/test_hard_rock.py` | sai o teste da tinta (`test_cave_luts_region_zero_is_the_old_ramp_and_others_are_tinted`) e entra o equivalente das rampas; as cores do minimapa continuam pelo nome `CAVE_REGION_COLORS` |

---

### Task 1: Promover a arte e o chão assado da caverna

**Files:**
- Create: `assets/sprites/cave_ground/*`, `game/cave_ground.py`, `tests/test_cave_ground.py`
- Modify: `game/config.py` (perto do `REGIONS_DIR`, linha ~829), `game/ground.py:280-331` (`bake_strip`), `game/render.py:220-226, 241, 504-534, 987-989`, `game/minimap.py:31-32, 76`, `tools/dev/smoke.py:2712-2719`

**Interfaces:**
- Produz:
  - `C.CAVE_GROUND_DIR: Path`, `C.CAVE_DECAL_CLEAR = 6`;
  - `cave_ground.CaveArt(folder=None)` com `.ok`, `.meta`, `.ramps`, `.decal_p`, `.decal_mix`, `.v9 = {}`, `.cover = False`, `.tex_stack (4, 512, 512)`, `.decals`, `.lut() -> np.ndarray (128, 3)`;
  - `cave_ground.CaveGeo(world)` com `.seed`, `.region`, `.basin`, `.formations`, `.center` e `.warp(px, py)`;
  - `cave_ground.arrival_skip(center, r) -> set[tuple[int, int]]`;
  - `cave_ground.CaveGround(enabled=True)`, com o mesmo `draw(canvas, geo, cam, view, stage_map)` do `Ground` (o `stage_map` é ignorado);
  - `Renderer.cave_ground` e `Renderer.cave_geo(world) -> CaveGeo | None`.

- [ ] **Step 1: Copiar a arte pra `assets/`**

```bash
mkdir -p assets/sprites/cave_ground
cp reports/design/v06_fundo_m2_biomas/assado/ground_cave_*.png assets/sprites/cave_ground/
cp reports/design/v06_fundo_m2_biomas/assado/decal_*.png assets/sprites/cave_ground/
cp reports/design/v06_fundo_m2_biomas/assado/cave_ground_palettes.json assets/sprites/cave_ground/
cp reports/design/v06_fundo_m2_biomas/ramps.json assets/sprites/cave_ground/cave_rock_ramps.json
cp reports/design/v06_fundo_m2_biomas/luz.json assets/sprites/cave_ground/cave_light.json
ls assets/sprites/cave_ground | wc -l     # esperado: 53 (4 + 46 + 3)
```

Confira no `cave_ground_palettes.json` que `ramps["BASE"][<classe>]["cave"]` é uma lista de 8 hex pra cada uma das 4 classes. A seção 0.1 do report mostra os valores. Se a estrutura for outra, ajuste o `CaveArt.lut` e **não** o JSON.

- [ ] **Step 2: Config**

Em `game/config.py`, logo depois de `REGIONS_DIR = SPRITES_DIR / "regions"`:

```python
CAVE_GROUND_DIR = SPRITES_DIR / "cave_ground"   # v0.6 Fundo M2: chão assado, rampas da rocha e luz da caverna
CAVE_DECAL_CLEAR = 6                             # tiles: sem decalque em volta da chegada da rampa
```

- [ ] **Step 3: Escrever os testes que falham** (`tests/test_cave_ground.py`)

```python
"""v0.6 Fundo M2: chão assado da caverna (game/cave_ground.py)."""
import numpy as np
import pytest

from game import cave_gen
from game import cave_ground as CG
from game import config as C
from game import ground as G
from game.geo import BASALT, FROST, PLATEAU, SALAR


@pytest.fixture(scope="module")
def art():
    a = CG.CaveArt()
    assert a.ok, "assets/sprites/cave_ground/ incompleto"
    return a


@pytest.fixture(scope="module")
def world():
    return cave_gen.generate_cave(7)


def test_art_loads_four_textures_and_decals(art):
    assert art.tex_stack.shape == (4, G.BP, G.BP)
    assert {"scoria", "icesheet", "wet", "soil"} <= set(art.decals)
    assert art.cover is False and art.v9 == {}


def test_lut_has_eight_colours_per_class_plus_outline(art):
    lut = art.lut()
    assert lut.shape == (G.NEW, 3)
    for c in range(4):
        assert tuple(lut[c * 16 + 8]) == G.OUTLINE
    assert tuple(lut[BASALT * 16 + 7]) == (0xFF, 0x8A, 0x45)       # brasa do basalto (seção 0.1 do report)


def test_missing_folder_is_not_ok(tmp_path):
    assert CG.CaveArt(tmp_path).ok is False


def test_bake_is_deterministic_and_has_no_bed(world, art):
    geo = CG.CaveGeo(world)
    bx, by = world.center[0] // G.BT, world.center[1] // G.BT
    a = _bake(geo, art, bx, by)
    b = _bake(geo, art, bx, by)
    assert np.array_equal(a, b)
    assert not np.any((a // 16) == G.BED)                            # sem leito na caverna
    assert set(np.unique(a // 16)) <= {PLATEAU, SALAR, BASALT, FROST}


def test_border_is_curved_not_on_tile_lines(world, art):
    """Num bloco que tem duas regiões, a troca de classe não fica só nas linhas de 32 px."""
    geo = CG.CaveGeo(world)
    reg = world.cave_region
    for by in range(reg.shape[0] // G.BT):
        for bx in range(reg.shape[1] // G.BT):
            sub = reg[by * G.BT:(by + 1) * G.BT, bx * G.BT:(bx + 1) * G.BT]
            if len(np.unique(sub)) > 1:
                cls = _bake(geo, art, bx, by) // 16
                change = np.nonzero(cls[:, 1:] != cls[:, :-1])[1] + 1
                assert np.any(change % G.T != 0)
                return
    pytest.fail("nenhum bloco com fronteira na seed 7")


def test_no_decals_near_arrival(world, art):
    geo = CG.CaveGeo(world)
    skip = CG.arrival_skip(world.center, C.CAVE_DECAL_CLEAR)
    ctx = G.BakeContext(geo)
    ctx.skip = skip
    bx, by = world.center[0] // G.BT, world.center[1] // G.BT
    for x, y, _, idx in G.decals_for_block(geo, art, bx, by, ctx.tcls, skip):
        cx, cy = (x + idx.shape[1] // 2) // G.T, (y + idx.shape[0] // 2) // G.T
        assert (cx, cy) not in skip


def test_cave_ground_draws_and_bakes(world, monkeypatch):
    import pygame
    pygame.init()
    gr = CG.CaveGround()
    gr.sync = True
    canvas = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
    cam = (world.center[0] * G.T - 480, world.center[1] * G.T - 270)
    gr.draw(canvas, CG.CaveGeo(world), cam, (C.SCREEN_W, C.SCREEN_H), None)
    assert gr.bake_ms, "assou pelo menos 1 bloco"
    assert canvas.get_at((480, 270))[:3] != (0, 0, 0)


def _bake(geo, art, bx, by):
    ctx = G.BakeContext(geo)
    ctx.skip = set()
    gen = G.bake_block_codes(geo, art, bx, by, ctx)
    out = None
    while out is None:
        out = next(gen)
    return out[0]
```

Run: `uv run pytest tests/test_cave_ground.py -v`
Esperado: FAIL com `ModuleNotFoundError: game.cave_ground`.

- [ ] **Step 4: `bake_strip` sem cobertura quando a arte não tem**

Em `game/ground.py`, `bake_strip` (linha ~329), troque a linha da `cover`:

```python
    if getattr(art, "cover", True):
        cover = cover_strip(geo, depth if depth is not None else depth_field(geo.basin), xs, ys, cls, d)[crop]
    else:                                          # caverna (v0.6 Fundo M2): sem grama nem umidade
        cover = np.zeros(code.shape, np.uint8)
```

- [ ] **Step 5: `game/cave_ground.py`**

```python
"""Chão assado da caverna (v0.6 Fundo M2 · bíblia §15).

O motor é o da superfície (game/ground.py: `bake_block_codes`, `decals_for_block`, o cache e o desenho do
`Ground`), só com a arte da caverna no lugar da `RegionArt` (assets/sprites/cave_ground/, aprovada pelo dono no
report reports/design/v06_fundo_m2_biomas/). Diferenças:
- 4 classes (geo.REGION_NAMES: centro, salar, basalto, gelo), sem leito: o `basin` é -1 em tudo;
- 1 paleta só (a caverna não tem estágio): o colorir é 1 LUT, sem a variante "m" da transição;
- sem cobertura (grama, umidade) e sem decoração solta; sem decalque num raio de C.CAVE_DECAL_CLEAR da chegada.
A região de cada pixel é a do `world.cave_region` em (x + dx, y + dy), com o `geo.warp_px` da seed da caverna.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pygame

from game import config as C
from game import geo as geo_mod
from game import ground as G
from game.surfaces import opaque

NAMES = geo_mod.REGION_NAMES
STAGE = "cave"                     # a única chave de estágio do cave_ground_palettes.json


class CaveArt:
    """O que a `RegionArt` tem, só que da caverna. `ok` = tudo carregou."""

    def __init__(self, folder=None):
        folder = folder or C.CAVE_GROUND_DIR
        self.ok = False
        path = folder / "cave_ground_palettes.json"
        if not path.exists():
            return
        self.meta = json.loads(path.read_text(encoding="utf-8"))
        self.ramps = self.meta["ramps"]
        self.decal_p = self.meta["decal_p"]
        self.decal_mix = {k: [(n, w) for n, w in v] for k, v in self.meta["decal_mix"].items()}
        self.v9 = {}                               # sem 3º sorteio
        self.cover = False                         # sem grama/umidade (ground.bake_strip)
        textures = []
        for name in NAMES:
            tex = G.load_indexed(folder / f"ground_cave_{name}.png")
            if tex is None or tex.shape != (G.BP, G.BP):
                return
            textures.append(tex)
        self.tex_stack = np.stack(textures)        # (4, 512, 512)
        self.decals: dict[str, list[np.ndarray]] = {}
        for p in sorted(folder.glob("decal_*.png")):
            name, _ = p.stem.removeprefix("decal_").rsplit("_", 1)
            idx = G.load_indexed(p)
            if idx is not None:
                self.decals.setdefault(name, []).append(idx)
        self.ok = True

    def lut(self) -> np.ndarray:
        """128×3: código (classe·16 + índice) -> cor. 8 = contorno, 9 = preto, como a `RegionArt.lut`."""
        out = np.zeros((G.NEW, 3), np.uint8)
        for c, name in enumerate(NAMES):
            cols = [G._hex(h) for h in self.ramps["BASE"][name][STAGE]] + [G.OUTLINE, (0, 0, 0)]
            out[c * 16:c * 16 + len(cols)] = cols
        return out


class CaveGeo:
    """O mínimo que o `ground.bake_strip` pede de um geo, montado do mundo da caverna."""

    def __init__(self, world):
        self.seed = world.seed
        self.region = world.cave_region
        self.basin = np.full(self.region.shape, -1, np.int16)
        self.formations = []
        self.center = world.center

    def warp(self, px, py):
        return geo_mod.warp_px(self.seed, px, py)


def arrival_skip(center, r: int) -> set[tuple[int, int]]:
    """Tiles sem decalque: um disco de raio `r` em volta da chegada."""
    cx, cy = center
    return {(tx, ty) for ty in range(cy - r, cy + r + 1) for tx in range(cx - r, cx + r + 1)
            if math.hypot(tx - cx, ty - cy) < r}


class CaveGround(G.Ground):
    """O `Ground` da superfície com a arte da caverna: troca só o que dependia de estágio ou da superfície."""

    @property
    def art(self) -> CaveArt | None:
        if self._art is None and self.wanted:
            self._art = CaveArt()
        return self._art if self._art is not None and self._art.ok else None

    def bind(self, geo) -> None:
        if geo is self._geo:
            return
        self._geo = geo
        self.ctx = G.BakeContext(geo)
        self.ctx.skip = arrival_skip(geo.center, C.CAVE_DECAL_CLEAR)
        self._index.clear()
        self._color.clear()
        self._jobs.clear()
        self._grid_memo.clear()
        self._decor, self._decor9 = {}, {}
        self.bake_ms.clear()

    def _pal(self) -> np.ndarray:
        if STAGE not in self._lut:
            self._lut[STAGE] = self.art.lut()
        return self._lut[STAGE]

    def variant(self, key, stage_map) -> tuple:
        return ("u", STAGE)

    def _colorize(self, key, want) -> pygame.Surface:
        code = self._index[key][0]
        pal = np.concatenate([self._pal(), self._pal()])          # 256 entradas, como a superfície
        surf8 = pygame.Surface((G.BP, G.BP), 0, 8)
        surf8.set_palette([tuple(int(v) for v in c) for c in pal])
        pygame.surfarray.blit_array(surf8, code.T)
        out = opaque((G.BP, G.BP))
        out.blit(surf8, (0, 0))
        self._color[key] = (want, out)
        return out

    def _flat(self, key, want) -> pygame.Surface:
        bx, by = key
        sub = self.ctx.tcls[by * G.BT:(by + 1) * G.BT, bx * G.BT:(bx + 1) * G.BT]
        small = opaque((sub.shape[1], sub.shape[0]))
        pygame.surfarray.blit_array(small, self._pal()[sub.astype(int) * 16 + 3].transpose(1, 0, 2))
        out = opaque((G.BP, G.BP))
        pygame.transform.scale(small, (sub.shape[1] * G.T, sub.shape[0] * G.T), out)
        self._color[key] = (("flat", STAGE), out)
        return out
```

`G.load_indexed` aceita `Path`, porque o `RegionArt` já chama assim. Confira se `world.seed` e `world.center` existem no `World` da caverna. Em `game/world.py:72` existe o `self.seed`, e o `center` vem do `cave_gen.generate_cave`.

- [ ] **Step 6: Rodar os testes do módulo**

Run: `uv run pytest tests/test_cave_ground.py -v`
Esperado: PASS (o `test_cave_ground_draws_and_bakes` assa ~6 blocos, então leva ~1 s).

- [ ] **Step 7: Plugar no `Renderer`**

Em `game/render.py`:

1. Na linha ~241, logo depois de `self.ground = ground.Ground(...)`:

```python
        self.cave_ground = cave_ground.CaveGround(getattr(sprites, "enabled", True))  # v0.6 Fundo M2: chão assado da caverna
        self._cave_geo: cave_ground.CaveGeo | None = None
        self._cave_geo_world = None
```

   E `from game import cave_ground` junto dos imports de `game`.

2. Apague o bloco `self.region_tint = {} ... self.region_tint[region] = s` (linhas ~220-225) e, no `_draw_floor`, as 3 linhas `tint = self.region_tint.get(...)`, `if tint is not None:` e `canvas.blit(tint, ...)`.

3. Método novo, perto do `surface_geo`:

```python
    def cave_geo(self, world):
        """O geo do chão assado da caverna (v0.6 Fundo M2), ou None (superfície ou sem a arte)."""
        if world.cave_region is None or not self.cave_ground.enabled:
            return None
        if self._cave_geo_world is not world:
            self._cave_geo, self._cave_geo_world = cave_ground.CaveGeo(world), world
        return self._cave_geo
```

4. No `draw_floors`, logo depois do `geo = self.surface_geo(state)` e **antes** do `if geo is not None:` da superfície:

```python
        cgeo = self.cave_geo(world) if self.organic_hills(state) else None
        if cgeo is not None:   # caverna (v0.6 Fundo M2): chão assado; sem água e sem sombra quadrada (a rocha é orgânica)
            self.cave_ground.draw(canvas, cgeo, cam, (self.view_w, self.view_h), None)
            return
```

5. A `sync` dos prints: no `tools/dev/smoke.py` (linhas ~2712 e ~2719), em todo lugar que faz `r.ground.sync = True/False`, faça o mesmo em `r.cave_ground.sync`. Procure outros com `grep -rn "ground.sync" game tools/dev`.

- [ ] **Step 8: Minimapa com a cor da paleta assada**

Em `game/minimap.py`, troque a constante da linha 32 por:

```python
# v0.6 Fundo M2: chão da caverna no mapa, por região = a cor base (índice 3) da paleta assada (cave_ground_palettes.json)
_CAVE_REGION_FALLBACK = {0: (92, 84, 80), 1: (130, 112, 88), 2: (96, 66, 60), 3: (98, 118, 134)}


def _cave_region_colors() -> dict[int, tuple[int, int, int]]:
    try:
        meta = json.loads((C.CAVE_GROUND_DIR / "cave_ground_palettes.json").read_text(encoding="utf-8"))
        base = meta["ramps"]["BASE"]
        return {i: _hex(base[name]["cave"][3]) for i, name in enumerate(REGION_NAMES)}
    except (OSError, KeyError, ValueError, IndexError):
        return dict(_CAVE_REGION_FALLBACK)


CAVE_REGION_COLORS = _cave_region_colors()
```

Use o conversor de hex que o `minimap.py` já tem pro `_region_colors` (se não houver, `tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))`). Os testes que comparam com `minimap.CAVE_REGION_COLORS[...]` continuam passando, porque usam o nome. Se o basalto ficar escuro demais no mapa a ponto de sumir contra a rocha, **não** invente cor: anote no relatório final.

- [ ] **Step 9: Rodar tudo**

Run: `uv run pytest`
Esperado: PASS. Se algum teste de render da caverna dependia da tinta, troque a asserção pela regra nova (com a arte, o chão vem do `cave_ground`; sem ela, o `floor_mist` sem tinta).

---

### Task 2: Rocha com rampa por região e divisa por pixel

**Files:**
- Modify: `game/cave_rocks.py:29-56, 87-107`, `game/config.py:265-269` (sai o `CAVE_REGION_TINT`), `tests/test_hard_rock.py:162-...`
- Test: `tests/test_cave_rocks.py`

**Interfaces:**
- Consome: `C.CAVE_GROUND_DIR` e `assets/sprites/cave_ground/cave_rock_ramps.json` (Task 1).
- Produz:
  - `cave_rocks.load_ramps(path=None) -> dict[int, np.ndarray] | None`, com 4 rampas `(10, 3) uint8`;
  - `cave_rocks.cave_luts(ramps=...) -> dict[int, np.ndarray]` (LUT 80×3);
  - `cave_rocks.pixel_regions(blk, region, seed) -> np.ndarray`.

- [ ] **Step 1: Testes que falham** (no fim de `tests/test_cave_rocks.py`)

```python
from game import cave_rocks, hills
from game import config as C
from game.geo import BASALT, FROST, PLATEAU, SALAR


def test_ramps_load_and_centre_is_todays_ramp():
    ramps = cave_rocks.load_ramps()
    assert ramps is not None and set(ramps) == {PLATEAU, SALAR, BASALT, FROST}
    assert np.array_equal(ramps[PLATEAU][:9], cave_rocks.cave_ramp()[:9])   # report §1: o centro não muda
    assert tuple(ramps[BASALT][8]) == (194, 72, 31)                          # contorno de brasa


def test_luts_use_one_ramp_per_region():
    ramps = cave_rocks.load_ramps()
    lut = cave_rocks.cave_luts(ramps)[1]
    assert lut.shape == (80, 3)
    for r in range(4):
        assert np.array_equal(lut[r * 10:r * 10 + 10], ramps[r])
    assert np.array_equal(lut[40:], (lut[:40] * hills.BEDROCK_SHADE).astype(np.uint8))


def test_luts_without_file_fall_back_to_single_ramp(tmp_path):
    lut = cave_rocks.cave_luts(cave_rocks.load_ramps(tmp_path / "nada.json"))[1]
    for r in range(4):
        assert np.array_equal(lut[r * 10:r * 10 + 10], cave_rocks.cave_ramp())


def test_wall_region_border_is_curved():
    """Muro inteiro num bloco, região 0 à esquerda da coluna 4 e 1 à direita: a troca de cor não é uma reta."""
    kinds = np.full((12, 10), C.ROCK, np.uint8)
    region = np.zeros((64, 64), np.uint8)
    region[:, 4:] = SALAR
    i0, i1, j0, j1 = hills.window_bounds(0, 1)
    blk = hills.bake_block(kinds, cave_rocks.region_window(region, i0, i1, j0, j1), 0, 1,
                           hills.load_indexed("hill_top.png"), hills.load_indexed("hill_face.png"),
                           hills.edge_noise())
    reg = cave_rocks.pixel_regions(blk, region, seed=7)
    top = blk["top"]
    firsts = {int(np.argmax(reg[y] == SALAR)) for y in range(reg.shape[0]) if top[y].all() and (reg[y] == SALAR).any()}
    assert len(firsts) > 1, "a divisa da rocha virou reta (escadinha por tile)"
```

Antes de escrever, confira os nomes: o tile de rocha comum em `C` (`C.ROCK` ou outro em `C.WALL_TILES`) e se `hill_top.png` e `hill_face.png` carregam no ambiente de teste. Os testes que já existem em `tests/test_cave_rocks.py` mostram o jeito certo de montar um `bake_block`, então copie de lá.

Run: `uv run pytest tests/test_cave_rocks.py -v`
Esperado: FAIL (`load_ramps` não existe).

- [ ] **Step 2: Rampas e LUT**

Em `game/cave_rocks.py`, troque o `cave_luts` por:

```python
def load_ramps(path=None) -> dict[int, np.ndarray] | None:
    """As 4 rampas da rocha (v0.6 Fundo M2, cave_rock_ramps.json: região -> 10×[r,g,b], ordem do `cave_ramp`)."""
    path = path or C.CAVE_GROUND_DIR / "cave_rock_ramps.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {i: np.array(data[name], np.uint8).reshape(10, 3) for i, name in enumerate(hills.REGIONS)}
    except (OSError, KeyError, ValueError):
        return None


_DEFAULT = object()


def cave_luts(ramps=_DEFAULT) -> dict[int, np.ndarray]:
    """LUT (80×3) no formato do `hills.colorize_block`: a rampa de cada região (sem o arquivo: a de hoje nas 4) e,
    +40, a versão escurecida (topo da borda do mapa)."""
    if ramps is _DEFAULT:
        ramps = load_ramps()
    base = cave_ramp()
    lut = np.concatenate([ramps[r] if ramps else base for r in range(len(hills.REGIONS))])
    lut = np.concatenate([lut, (lut * hills.BEDROCK_SHADE).astype(np.uint8)])
    return {n: lut for n in STAGES}
```

Coloque `import json` no topo. Atualize a docstring do módulo: o item "COR" vira "uma rampa por região (cave_rock_ramps.json, arte do M2), com a região por pixel na curva do chão (`pixel_regions`)".

- [ ] **Step 3: Região por pixel**

Ainda em `game/cave_rocks.py`:

```python
from game import geo as geo_mod

T = C.TILE


def pixel_regions(blk: dict, region: np.ndarray, seed: int) -> np.ndarray:
    """Região de cada pixel do bloco na MESMA curva do chão assado (game/cave_ground.py): o topo pega a região do
    chão em (x + dx, y + LIFT + dy); a face pega a do tile dono (o y é preso no fim da linha dele). Fora da
    silhueta fica o `reg` por tile de antes (não é desenhado)."""
    idx = blk["idx"]
    h, w = idx.shape
    ys, xs = np.mgrid[blk["y0"]:blk["y0"] + h, blk["x0"]:blk["x0"] + w]
    gy = ys + hills.LIFT
    solid = idx != hills.TRANSPARENT
    face = solid & ~blk["top"]
    gy = np.where(face, np.minimum(gy, (blk["row"] + 1) * T - 1), gy)
    dx, dy = geo_mod.warp_px(seed, xs, gy)
    H, W = region.shape
    tj = np.clip(np.floor((gy + dy) / T).astype(np.int64), 0, H - 1)
    ti = np.clip(np.floor((xs + dx) / T).astype(np.int64), 0, W - 1)
    return np.where(solid, region[tj, ti], blk["reg"]).astype(blk["reg"].dtype)
```

No `CaveRocks.strips`, logo depois do `geo = hills.bake_block(...)`:

```python
            if world.cave_region is not None:
                geo["reg"] = pixel_regions(geo, world.cave_region, world.seed)
```

Confira se o `geo_mod.warp_px` aceita arrays 2D inteiros. O `ground.warp_half` chama com o `mgrid`, então sim. Se o assado de um bloco de rocha subir mais de ~5 ms (meça com `time.perf_counter` num teste rápido), calcule o warp a cada 2 px como o `ground.warp_half`.

- [ ] **Step 4: Tirar a tinta provisória**

- `game/config.py`: apague o comentário "Visual PROVISÓRIO por região" e o `CAVE_REGION_TINT` (linhas ~265-269).
- `tests/test_hard_rock.py`: apague o `test_cave_luts_region_zero_is_the_old_ramp_and_others_are_tinted`, porque os testes novos da Step 1 cobrem o mesmo.
- `grep -rn "CAVE_REGION_TINT\|region_tint" game tests tools/dev` tem que voltar vazio.

- [ ] **Step 5: Rodar tudo**

Run: `uv run pytest`
Esperado: PASS.

---

### Task 3: Luz por região, print avulso, desempenho e bíblia

**Files:**
- Create: `game/cave_light.py`, `tests/test_cave_light.py`, `tools/dev/shot_v06_fundo_m2.py`
- Modify: `game/config.py`, `game/lighting.py:110-114`, `game/render.py:145-150, 487-491`, `docs/GAME_BIBLE.md` (§15)

**Interfaces:**
- Consome: `assets/sprites/cave_ground/cave_light.json` (Task 1).
- Produz:
  - `C.CAVE_LIGHT_SAMPLE_R = 2` e `C.CAVE_LIGHT_TAU = 0.5`;
  - `cave_light.load(path=None) -> list[dict]` (4 entradas, ordem `REGION_NAMES`);
  - `cave_light.region_weights(region, tx, ty, r) -> np.ndarray (4,)`;
  - `cave_light.blend(table, weights) -> np.ndarray (7,)`;
  - `cave_light.CaveLight`, com `.update(world, tx, ty, t)`, `.ambient`, `.helmet` e `.helmet_intensity`;
  - `lighting.helmet_lamp(px, py, facing, color=WARM_WHITE, intensity=1.0)`;
  - `render.cave_lights(state, helmet=WARM_WHITE, helmet_intensity=1.0)`.

- [ ] **Step 1: Config**

No `game/config.py`, perto do `CAVE_DECAL_CLEAR`:

```python
CAVE_LIGHT_SAMPLE_R = 2      # tiles: a luz da caverna é a média das regiões num quadrado de 5×5 em volta do player
CAVE_LIGHT_TAU = 0.5         # s: suavização da luz ao cruzar a fronteira (não estala)
```

- [ ] **Step 2: Testes que falham** (`tests/test_cave_light.py`)

```python
"""v0.6 Fundo M2: luz por região da caverna (game/cave_light.py)."""
import numpy as np

from game import cave_light as L
from game.geo import BASALT, PLATEAU, SALAR
from game.lighting import WARM_WHITE


class W:
    def __init__(self, region):
        self.cave_region = region


def test_table_matches_approved_values():
    t = L.load()
    assert t[PLATEAU]["ambient"] == (3, 4, 6) and t[PLATEAU]["helmet"] == WARM_WHITE
    assert t[BASALT]["ambient"] == (34, 10, 5) and t[BASALT]["helmet_intensity"] == 0.95   # o vermelho fica (dono)


def test_missing_file_falls_back_to_pitch_black(tmp_path):
    t = L.load(tmp_path / "nada.json")
    assert all(e["ambient"] == (0, 0, 0) and e["helmet"] == WARM_WHITE for e in t)


def test_weights_on_the_border_are_mixed():
    reg = np.zeros((20, 20), np.uint8)
    reg[:, 10:] = SALAR
    w = L.region_weights(reg, 10, 5, 2)
    assert np.isclose(w.sum(), 1) and w[PLATEAU] == 0.4 and w[SALAR] == 0.6
    assert L.region_weights(reg, 2, 5, 2)[PLATEAU] == 1


def test_light_snaps_on_enter_and_eases_after():
    reg = np.zeros((20, 20), np.uint8)
    reg[:, 10:] = BASALT
    world = W(reg)
    cl = L.CaveLight()
    cl.update(world, 2, 5, t=0.0)
    assert cl.ambient == (3, 4, 6)                         # entrou: na hora
    cl.update(world, 17, 5, t=0.1)
    mid = cl.ambient
    assert 3 < mid[0] < 34                                 # cruzou: a meio caminho
    for i in range(2, 40):
        cl.update(world, 17, 5, t=i * 0.1)
    assert cl.ambient == (34, 10, 5)


def test_helmet_colour_is_quantized():
    reg = np.zeros((20, 20), np.uint8)
    reg[:, 10:] = BASALT
    cl = L.CaveLight()
    cl.update(W(reg), 10, 5, t=0.0)
    assert all(c % 8 == 0 or c == 255 for c in cl.helmet)


def test_no_region_map_is_centre():
    cl = L.CaveLight()
    cl.update(W(None), 0, 0, t=0.0)
    assert cl.ambient == (3, 4, 6)
```

Run: `uv run pytest tests/test_cave_light.py -v`
Esperado: FAIL com `ModuleNotFoundError: game.cave_light`.

- [ ] **Step 3: `game/cave_light.py`**

```python
"""Luz por região da caverna (v0.6 Fundo M2 · bíblia §15).

Cada região tem um ambiente (o que se enxerga fora dos focos, o `ambient` do Lighting.apply), a cor e a
intensidade da lanterna do capacete (cave_light.json, aprovado pelo dono no report do M2). O que vale no quadro é
a média das regiões num quadrado em volta do player (C.CAVE_LIGHT_SAMPLE_R), suavizada no tempo
(C.CAVE_LIGHT_TAU): na fronteira a luz mistura e ao cruzar não estala. Entrar na caverna (ou trocar de mundo)
pega o valor na hora. A cor do capacete é arredondada de 8 em 8 (o Lighting guarda uma textura por cor).
"""

from __future__ import annotations

import json
import math

import numpy as np

from game import config as C
from game import geo as geo_mod
from game.lighting import WARM_WHITE

NAMES = geo_mod.REGION_NAMES
DEFAULT = {"ambient": (0, 0, 0), "helmet": WARM_WHITE, "helmet_intensity": 1.0}
QUANT = 8


def load(path=None) -> list[dict]:
    path = path or C.CAVE_GROUND_DIR / "cave_light.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [{"ambient": tuple(int(v) for v in data[n]["ambient"]),
                 "helmet": tuple(int(v) for v in data[n]["helmet"]),
                 "helmet_intensity": float(data[n]["helmet_intensity"])} for n in NAMES]
    except (OSError, KeyError, ValueError, TypeError):
        return [dict(DEFAULT) for _ in NAMES]


def region_weights(region: np.ndarray, tx: int, ty: int, r: int = C.CAVE_LIGHT_SAMPLE_R) -> np.ndarray:
    """Fração de cada região no quadrado (2r+1)² em volta do tile (cortado na borda do mapa)."""
    h, w = region.shape
    win = region[max(0, ty - r):min(h, ty + r + 1), max(0, tx - r):min(w, tx + r + 1)]
    counts = np.bincount(win.ravel(), minlength=len(NAMES))[:len(NAMES)].astype(np.float64)
    total = counts.sum()
    return counts / total if total else np.eye(len(NAMES))[0]


def blend(table: list[dict], weights: np.ndarray) -> np.ndarray:
    """(7,): ambiente RGB, capacete RGB, intensidade do capacete."""
    vecs = np.array([[*e["ambient"], *e["helmet"], e["helmet_intensity"]] for e in table], np.float64)
    return weights @ vecs


class CaveLight:
    def __init__(self, table: list[dict] | None = None):
        self.table = table if table is not None else load()
        self.value: np.ndarray | None = None
        self._t: float | None = None
        self._world = None

    def update(self, world, tx: int, ty: int, t: float) -> None:
        region = world.cave_region
        weights = np.eye(len(NAMES))[0] if region is None else region_weights(region, tx, ty)
        target = blend(self.table, weights)
        if self.value is None or world is not self._world or self._t is None:
            self.value = target
        else:
            dt = min(max(t - self._t, 0.0), 0.25)
            self.value = self.value + (target - self.value) * (1 - math.exp(-dt / C.CAVE_LIGHT_TAU))
        self._t, self._world = t, world

    @property
    def ambient(self) -> tuple[int, int, int]:
        return tuple(int(round(v)) for v in self.value[:3])

    @property
    def helmet(self) -> tuple[int, int, int]:
        return tuple(min(255, int(round(v / QUANT)) * QUANT) for v in self.value[3:6])

    @property
    def helmet_intensity(self) -> float:
        return float(self.value[6])
```

Observação: o `test_light_snaps_on_enter_and_eases_after` espera chegar exatamente em `(34, 10, 5)` depois de ~4 s. Com τ = 0,5 s, `exp(-8)` dá menos de 0,1 de erro, e o `round` fecha. Se a conta não fechar, troque o loop do teste por 60 passos em vez de mexer na fórmula. O `(255 // 8) * 8` daria 248, por isso o `min(255, round(...) * 8)` arredonda 255 pra 256 e depois corta em 255. O teste aceita `c == 255`.

- [ ] **Step 4: Rodar**

Run: `uv run pytest tests/test_cave_light.py -v`
Esperado: PASS.

- [ ] **Step 5: Ligar no render**

1. `game/lighting.py`, `helmet_lamp`:

```python
def helmet_lamp(px: float, py: float, facing: str | tuple[float, float] | None = None,
                color: tuple[int, int, int] = WARM_WHITE, intensity: float = 1.0) -> LightSource:
    """Lanterna do capacete: ~4 tiles, centro levemente deslocado pra onde o player olha. Na caverna a cor e a
    intensidade vêm da região (game/cave_light.py)."""
    dx, dy = FACING_DIR.get(facing, (0, 0)) if isinstance(facing, str) or facing is None else facing
    bias = 10
    return LightSource(px + dx * bias, py + dy * bias, 4 * T, color, intensity)
```

2. `game/render.py`, `cave_lights(state, helmet=WARM_WHITE, helmet_intensity=1.0)`: a primeira linha vira `out = [helmet_lamp(p.x, p.y - 18, p.facing, helmet, helmet_intensity)]`. Importe o `WARM_WHITE` de `game.lighting` se ainda não estiver.

3. `Renderer.__init__`: `self.cave_light = cave_light.CaveLight()` (e `from game import cave_light`).

4. `draw_cave_darkness`:

```python
    def draw_cave_darkness(self, canvas, state: GameState, cam, t: float) -> None:
        """Escuridão da caverna (game/lighting.py), com a luz da região do player (game/cave_light.py), e, por
        cima, o brilho dos minérios no escuro."""
        cl = self.cave_light
        cl.update(state.world, *state.player.tile, t)
        self.lighting.apply(canvas, cam, cave_lights(state, cl.helmet, cl.helmet_intensity), ambient=cl.ambient, t=t)
        tx0, tx1, ty0, ty1 = self.visible_tiles(cam)
        self.lighting.draw_glints(canvas, cam, ore_glints(state.world, tx0, tx1, ty0, ty1 + 1), t=t)
```

Confira se `state.player.tile` é `(tx, ty)`, porque o smoke usa `s.player.tile` assim. Confira também se tem outra chamada de `cave_lights` ou `helmet_lamp` (`grep -rn "cave_lights\|helmet_lamp" game tests tools/dev`). As que não passarem cor continuam com o padrão.

5. `uv run pytest`. Se algum teste afirma que a caverna fora da luz é **preto 0**, o ambiente do centro agora é `(3, 4, 6)`. Ajuste a asserção pra "quase preto" (≤ 8 por canal) e anote no relatório.

- [ ] **Step 6: Print avulso `tools/dev/shot_v06_fundo_m2.py`**

No molde do `tools/dev/shot_v06_fundo_m1.py` (copie a montagem do jogo headless de lá): seed **7**, entra na caverna, liga `renderer.cave_ground.sync = True` e, pra cada ponto, teleporta o player e tira dois prints, claro e escuro (o normal do jogo). Saída: `reports/dev/v06_fundo_m2/`. Os pontos são os mesmos da seção 0.5 do report da Designer:

```python
SPOTS = {"centro_salar": (155, 132), "basalto_centro": (77, 132), "gelo_centro": (128, 71),
         "juncao_no": (82, 88), "juncao_ne": (188, 82)}
```

No print "claro", desligue só a escuridão: chame o pipeline sem o `draw_cave_darkness`, ou use o que o `shot_v06_fundo_m1.py` já faz pra ver a cor. No fim, imprima a média e o máximo de `renderer.cave_ground.bake_ms` e quantos blocos de rocha foram assados (`renderer.cave_rock_blocks().bakes`).

Run: `uv run python tools/dev/shot_v06_fundo_m2.py`
Esperado: 10 PNGs. Olhe todos e compare com as cenas da seção 0.5 do report (`reports/design/v06_fundo_m2_biomas/assado/cenas/`). O chão e a rocha devem bater, a divisa da rocha tem que sair curva e o basalto tem que aparecer avermelhado no escuro.

- [ ] **Step 7: Smoke e vídeo real**

Run: `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py`
Esperado: OK, com média e p95 perto de hoje (~6 ms / ~11 ms). Se a caverna estourar, o mais provável é assar chão e rocha no mesmo quadro. Reduza o `GROUND_BAKE_MS` só da caverna (um atributo do `CaveGround`) antes de mexer em outra coisa e relate os números.

Depois: `git checkout -- reports/dev` (o smoke reescreve os prints; o gerente refaz no main). **Não** apague a pasta `reports/dev/v06_fundo_m2/` do print avulso.

- [ ] **Step 8: Bíblia**

Na §15 do `docs/GAME_BIBLE.md`, depois do "Marco 1 · como ficou", escreva o "Marco 2 · como ficou" com:
- o chão assado da caverna (motor da superfície, `assets/sprites/cave_ground/`, 4 classes, sem leito nem estágio, sem decalque em 6 tiles da chegada);
- a rocha com uma rampa por região e a divisa na curva do chão;
- a luz por região (valores do `cave_light.json`, média 5×5, τ 0,5 s; o basalto avermelhado de propósito, "ar quente");
- o minimapa;
- o que não entrou (soltos com altura no chão da caverna, som por bioma).

Uma linha por item, no tom do M1.

- [ ] **Step 9: Rodar tudo**

Run: `uv run pytest`
Esperado: PASS. No relatório final: os números do smoke, os do print avulso (tempo do assado) e o que ficou diferente do report da Designer.

---

## Fechamento (gerente)
1. Revisar o diff e os 10 PNGs do `shot_v06_fundo_m2.py` contra o report da Designer.
2. Fazer o merge (`--no-ff`) e rodar `uv run pytest`, o smoke e o `real_video_check` no main.
3. Commit como Gabriel Oliveira. Os prints vão num commit separado, sem o `reports/dev/receitas.html`. Depois, push.
4. Marcar o ROADMAP e avisar o dono pra testar: entrar na caverna, F3 pra furar a rocha dura e andar até cada fronteira.
5. Som por bioma: se o dono aprovar o report do Som, vira uma task curta separada (promover os `amb_cave_*`, escolher pela região do player com histerese e mexer no `audio.ambient_for`).
