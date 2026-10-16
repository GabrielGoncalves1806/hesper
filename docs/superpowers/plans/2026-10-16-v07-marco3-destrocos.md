# v0.7 Lore · Marco 3 · Destroços novos · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** trocar os sprites da nave de carga (VÉSPER-7), do módulo (base de vidro, 3×2 → 8×4) e da sonda; criar dois tipos novos, a **nave de passageiros ARCA-2** (`liner`) e o **robô de reconhecimento** (`robot`), com loot, LOG e pegada próprios; mudar de 6–8 pra 8–10 destroços por mundo; save v13, com o save antigo carregando sem destroço em cima de construção do player.

**Arquitetura:**
- Tudo continua na tabela `SPECS` de `game/wrecks.py`. O `WreckSpec` ganha 3 campos com default, então os tipos de hoje não mudam de forma:
  - `parts`: a tabela de peças de bônus. `None` usa `C.LOOT_COMMON`.
  - `reads_from`: o tile de onde se lê o terminal. `None` usa o tile logo abaixo do terminal.
  - `terminal_rect`: o contorno do alvo do E, em px dentro do sprite.
- `MODULE_TERMINAL_RECT` sai do código e vira `SPECS["module"].terminal_rect`.
- Os destroços continuam saindo do `rng` compartilhado da superfície. Por isso a mesma seed põe os destroços em outro lugar: decisão do dono, "opção A".
- Save antigo: `wrecks.settle(layer)` roda em todo load, logo depois de `ruins.apply_overlays`:
  - destroço com máquina, bloco ou prop do player na pegada ou na caixa **sai do mundo**: tira de `world.wrecks`, os tiles viram chão e a caixa some;
  - os outros têm os tiles **recarimbados**: a pegada vira `WRECK` e a caixa vira `LOOT_CRATE`. Isso conserta buraco deixado por `changed_tiles` de save v12, cuja posição velha agora cai num destroço novo.
  - É derivado, como o `ruins_off` do M1: não precisa de campo novo no save.
- A migração v12→v13 só sobe a versão.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-v07-lore-design.md` (seção "M3"); bíblia §16, "Marco 3 · Destroços novos" (decisões do dono). LOGs: `docs/lore/logs_v07_rascunho.md`, seção "v0.7 M3". Contrato da arte: `reports/design/v07_lore/index.html`, blocos "Pro Dev" (rodada 5: VÉSPER e base; rodada 2: robô; rodada 1: sonda e nave de passageiros).

## Restrições globais
- **Contrato dos 5 destroços** (tile relativo ao canto de cima à esquerda da pegada; a largura do sprite = largura da pegada × 32; o sprite só passa da pegada pra cima, pelo `lift`):

  | kind | nome | pegada | sprite | tamanho | lift | caixa | terminal | lido de | contorno do terminal (px no sprite) |
  |---|---|---|---|---|---|---|---|---|---|
  | `cargo` | Nave de carga | (5, 3) | `wreck_cargo` | (160, 128) | 32 | (1, 3) | - | - | - |
  | `module` | Base espacial | (8, 4) | `wreck_module` | (256, 168) | 40 | (5, 4) | (4, 2) | **(4, 4)** | (138, 117, 20, 17) |
  | `probe` | Sonda | (2, 2) | `wreck_probe` | (64, 64) | 0 | (2, 1) | - | - | - |
  | `robot` | Robô de reconhecimento | (3, 2) | `wreck_robot` | (96, 64) | 0 | (3, 1) | - | - | - |
  | `liner` | Nave de passageiros | (5, 3) | `wreck_liner` | (160, 120) | 24 | (2, 3) | - | - | - |

  - **"Lido de (4,4)"**: a Designer marcou (4,3), mas esse tile fica dentro da pegada 8×4, que é sólida, e o player não chega nele. Por isso a leitura passa pro tile logo abaixo da pegada. Ver "Decisões".
  - A boca do porão da VÉSPER (3,2) e a porta da base (1,3) são **só arte** no M3.
  - O LED da sonda continua em (23, 37).
- **Loot** (bruto na caixa; números de partida, o balanceamento vem depois):
  - cargo, module e probe: as tabelas de hoje;
  - `robot`: `{"iron": (4, 6), "silicon": (2, 4)}`, com `parts = {"circuit": (1.0, (1, 2)), "chip": (0.40, (1, 1))}`;
  - `liner`: `{"iron": (10, 14), "silicon": (4, 6), "ice": (4, 8)}`, com `parts = {"wire": (0.80, (2, 4)), "iron_ingot": (0.40, (1, 2)), "silicon_wafer": (0.35, (1, 1))}`.
  - O destroço rico (`rich=True`) continua com `WRECK_RICH_LOOT` e `LOOT_RICH`.
- **LOGs** (índices novos 19 e 20, nunca mudam). Texto copiado **igual** de `docs/lore/logs_v07_rascunho.md`, seção "v0.7 M3":
  - 19: dia **2**, título `"DIARIO DE BORDO · ARCA-2"`;
  - 20: dia **167**, título `"ROBO R-2 · RELATORIO AUTOMATICO"`.
- **Sequência por distância** (`kinds_for(n)`, n de 8 a 10):

  ```
  ["cargo", "probe", "module", "liner", "cargo", "probe", "robot", *["robot", "cargo"][:n - 8], "module"]
  ```

  Os extras (`extras_for`) por rank:

  | rank | LOG | diagrama |
  |---|---|---|
  | 0 | 3 | o2_tank |
  | 2 | 4 | scanner |
  | 3 | 19 | - |
  | 4 | - | lamp_t2 |
  | 5 | 5 | - |
  | 6 | 20 | - |
  | n−1 | 6 | - |

  Sai exatamente **1 liner por mundo** e **1 ou 2 robôs**, sempre no rank 6 ou depois. `WRECK_COUNT = (8, 10)`. `WRECK_DIST` e `WRECK_SPACING` ficam como estão, a não ser que a Task 2 mostre destroço faltando (ver lá).
- **Assets**: a arte foi aprovada pelo dono. A Task 1 copia de `reports/design/v07_lore/pendentes/` pra `assets/sprites/`:
  - `r5_wreck_cargo_A.png` → `wreck_cargo.png`;
  - `r5_wreck_module_glass.png` → `wreck_module.png`;
  - `wreck_probe.png` → `wreck_probe.png`;
  - `r2_wreck_robot.png` → `wreck_robot.png`;
  - `wreck_liner.png` → `wreck_liner.png`.

  Fora isso, não mexer em `assets/`, `tools/sprites`, `tools/audio`, `reports/design`, `reports/audio`, `saves/` nem `settings.json`.
- **Save v13**. Nenhum campo novo.

## Decisões (o dono deveria ver)
1. **Terminal da base de vidro lido de (4,4)**, não de (4,3). O (4,3) fica dentro da pegada sólida. Se no print o player parecer longe demais do terminal, a alternativa é tirar o (4,3) da pegada (um "nicho"), mas aí o player fica desenhado atrás da frente do sprite.
2. **Nome no jogo**: `module` passa de "Módulo da colônia" pra **"Base espacial"** (o sprite agora é a base de vidro). O título dos LOGs 4 e 6 ("TERMINAL · MODULO DA COLONIA") **não muda**, porque é o texto do terminal, que é da colônia.
3. **O mouse no sprite**: a dica "<nome> · destroço" passa a valer em todo o retângulo do sprite (inclusive a parte de cima, do `lift`), não só na pegada. O clique do E continua por tile (caixa e terminal).
4. **`tools/sprites/build_sprites.py` ainda gera os `wreck_*.png` velhos.** Se alguém rodar o script, a arte nova é sobrescrita. Fica pra Designer tirar (ou trocar), fora deste marco. O Dev **não** roda o `build_sprites`.

## Estrutura de arquivos
- `game/wrecks.py`:
  - `WreckSpec` ganha `parts`, `reads_from` e `terminal_rect`;
  - `SPECS` fica com 5 tipos;
  - mudam `kinds_for`, `extras_for` e `crate_loot` (que passa a usar `spec.parts`);
  - entram `Wreck.reads_from` e `Wreck.sprite_rect`, e a função nova `settle(layer)`.
- `game/config.py`: `WRECK_COUNT` e os LOGs 19 e 20 (`LOGS`, `LOG_DAYS`, `LOG_TITLES`).
- `game/art.py`: fallback de `robot` e `liner` no `wreck(kind)`.
- `game/render.py`: o `draw_wreck` passa a usar `spec.terminal_rect`.
- `game/systems.py`: o `wreck_terminal_distance` passa a usar `reads_from`.
- `game/world.py`: `wreck_at_px(px, py)`.
- `game/app.py`: a dica do corpo do destroço passa a usar `wreck_at_px`.
- `game/save.py`: `SAVE_VERSION = 13`, `_v12_to_v13` e a chamada de `wrecks.settle` no `layers_from_dict`.
- `tools/dev/balance_sim.py`: só se o teto quebrar (ver Task 2).
- `tools/dev/shot_v07_m3.py` (novo): prints de cada destroço.
- Testes: `tests/test_wrecks.py`, `tests/test_ruins.py` (contagem de LOGs), `tests/test_logs_tab.py` (se ele fixa o número), `tests/test_save.py` e `tests/test_pockets.py` (se o destroço rico não couber).

---

### Task 1: Specs, assets, loot e LOGs

**Files:**
- Modify: `game/wrecks.py` (`WreckSpec`, `SPECS`, `MODULE_TERMINAL_RECT`, `crate_loot`, a docstring do topo)
- Modify: `game/config.py` (os LOGs 19 e 20)
- Modify: `game/art.py:796-890` (fallback)
- Modify: `game/render.py:1471-1487` (`wreck_surface`, `draw_wreck`)
- Assets: copiar os 5 PNGs (ver "Restrições globais")
- Test: `tests/test_wrecks.py`, `tests/test_ruins.py:212-217`, `tests/test_logs_tab.py`

**Interfaces:**
- Produz:
  - `WreckSpec(name, size, sprite, sprite_size, lift, crate, terminal, loot, parts=None, reads_from=None, terminal_rect=None)`;
  - `Wreck.reads_from -> tuple[int, int] | None` (tile absoluto);
  - `Wreck.sprite_rect -> tuple[int, int, int, int]` (px do mundo: x, y, w, h);
  - `SPECS` com `cargo`, `module`, `probe`, `robot` e `liner`.

- [ ] **Step 1: Escrever os testes que falham.** Em `tests/test_wrecks.py`, trocar `test_specs_match_sprite_contract` por:

```python
def test_specs_match_sprite_contract():
    s = wrecks.SPECS
    assert set(s) == {"cargo", "module", "probe", "robot", "liner"}
    contract = {   # kind: (pegada, sprite_size, lift, caixa)
        "cargo": ((5, 3), (160, 128), 32, (1, 3)),
        "module": ((8, 4), (256, 168), 40, (5, 4)),
        "probe": ((2, 2), (64, 64), 0, (2, 1)),
        "robot": ((3, 2), (96, 64), 0, (3, 1)),
        "liner": ((5, 3), (160, 120), 24, (2, 3)),
    }
    for kind, (size, sprite_size, lift, crate) in contract.items():
        spec = s[kind]
        assert (spec.size, spec.sprite_size, spec.lift, spec.crate) == (size, sprite_size, lift, crate), kind
        assert spec.sprite == f"wreck_{kind}"
        assert spec.sprite_size == (size[0] * 32, size[1] * 32 + lift), kind   # só passa da pegada pra cima
        assert (spec.terminal is None) == (kind != "module")
    assert s["module"].terminal == (4, 2) and s["module"].reads_from == (4, 4)
    assert s["module"].terminal_rect == (138, 117, 20, 17)
    w = wrecks.Wreck("cargo", 10, 20, 0)
    assert w.blit_pos == (320, 640 - 32) and w.anchor == ((10 + 2.5) * 32, (20 + 3) * 32)
    assert w.sprite_rect == (320, 640 - 32, 160, 128)
    m = wrecks.Wreck("module", 10, 20, 0)
    assert m.terminal == (14, 22) and m.reads_from == (14, 24)


def test_reads_from_defaults_to_tile_below_terminal():
    spec = wrecks.WreckSpec("x", (2, 2), "x", (64, 64), 0, (2, 1), (1, 0), {})
    assert spec.reads_from is None
    # sem reads_from: terminal relativo (1, 0) no canto (5, 7) -> lê de (6, 8)
    assert wrecks._read_tile(5, 7, spec) == (6, 8)
    assert wrecks._read_tile(5, 7, wrecks.SPECS["probe"]) is None


@pytest.mark.parametrize("seed", [1, 7, 42, 99, 1234])
def test_robot_always_gives_circuit(seed):
    robot = wrecks.Wreck("robot", 50, 50, 6)
    items = dict(wrecks.crate_loot(robot, seed))
    assert 1 <= items["circuit"] <= 2
    assert set(items) <= {"iron", "silicon", "circuit", "chip"}
    assert "ice" not in items


def test_robot_chip_chance_is_about_40_percent():
    hits = sum("chip" in dict(wrecks.crate_loot(wrecks.Wreck("robot", 50, 50, 6), s)) for s in range(400))
    assert 120 <= hits <= 200


def test_liner_resources_are_between_cargo_and_probe():
    liner = dict(wrecks.crate_loot(wrecks.Wreck("liner", 50, 50, 3), 7))
    assert 10 <= liner["iron"] <= 14 and 4 <= liner["silicon"] <= 6 and 4 <= liner["ice"] <= 8
```

  Em `tests/test_ruins.py:212-217`, a contagem passa a ser 21 e entra a conferência dos novos:

```python
    assert len(C.LOGS) == len(C.LOG_DAYS) == len(C.LOG_TITLES) == 21
    ...
    assert C.LOG_DAYS[7:19] == [1, 9, 22, 120, 152, 175, 198, 205, 219, 61, 209, 224]
    assert C.LOG_DAYS[19:] == [2, 167]
    assert C.LOG_TITLES[19:] == ["DIARIO DE BORDO · ARCA-2", "ROBO R-2 · RELATORIO AUTOMATICO"]
```

  Em `tests/test_logs_tab.py`, se `N_LOGS` estiver fixo, ele passa pra 21.

- [ ] **Step 2: Rodar e ver falhar.**
  - Rodar: `uv run pytest tests/test_wrecks.py tests/test_ruins.py tests/test_logs_tab.py -q`
  - Esperado: FAIL (`robot` não existe em `SPECS`, contagem 19 ≠ 21).

- [ ] **Step 3: Implementar.**

  Copiar os 5 PNGs:

```bash
P=reports/design/v07_lore/pendentes; A=assets/sprites
cp $P/r5_wreck_cargo_A.png $A/wreck_cargo.png
cp $P/r5_wreck_module_glass.png $A/wreck_module.png
cp $P/wreck_probe.png $A/wreck_probe.png
cp $P/r2_wreck_robot.png $A/wreck_robot.png
cp $P/wreck_liner.png $A/wreck_liner.png
```

  Em `game/wrecks.py`:

```python
@dataclass(frozen=True)
class WreckSpec:
    name: str
    size: tuple[int, int]               # tiles (largura, altura) da área sólida
    sprite: str
    sprite_size: tuple[int, int]        # largura = pegada × 32; passa da pegada só pra cima (lift)
    lift: int                           # px que o sprite sobe acima da área (antena, teto)
    crate: tuple[int, int]              # tile da caixa, relativo ao canto do destroço
    terminal: tuple[int, int] | None    # tile do terminal (dentro da área), relativo ao canto
    loot: dict                          # recurso -> (mín, máx) na caixa
    parts: dict | None = None           # v0.7 M3: peças de bônus {item: (chance, (mín, máx))}; None = C.LOOT_COMMON
    reads_from: tuple[int, int] | None = None     # v0.7 M3: tile de onde se lê o terminal; None = logo abaixo dele
    terminal_rect: tuple[int, int, int, int] | None = None   # v0.7 M3: contorno do alvo do E, px dentro do sprite


SPECS = {   # v0.7 M3: arte nova (bíblia §16, "Marco 3 · Destroços novos")
    "cargo": WreckSpec("Nave de carga", (5, 3), "wreck_cargo", (160, 128), 32, (1, 3), None,
                       {"iron": (14, 20), "silicon": (8, 12), "ice": (6, 10)}),
    "module": WreckSpec("Base espacial", (8, 4), "wreck_module", (256, 168), 40, (5, 4), (4, 2),
                        {"iron": (8, 12), "silicon": (4, 7), "ice": (3, 5)},
                        reads_from=(4, 4), terminal_rect=(138, 117, 20, 17)),
    "probe": WreckSpec("Sonda", (2, 2), "wreck_probe", (64, 64), 0, (2, 1), None,
                       {"iron": (2, 4), "silicon": (1, 3), "ice": (0, 2)}),
    "robot": WreckSpec("Robô de reconhecimento", (3, 2), "wreck_robot", (96, 64), 0, (3, 1), None,
                       {"iron": (4, 6), "silicon": (2, 4)},
                       parts={"circuit": (1.0, (1, 2)), "chip": (0.40, (1, 1))}),
    "liner": WreckSpec("Nave de passageiros", (5, 3), "wreck_liner", (160, 120), 24, (2, 3), None,
                       {"iron": (10, 14), "silicon": (4, 6), "ice": (4, 8)},
                       parts={"wire": (0.80, (2, 4)), "iron_ingot": (0.40, (1, 2)), "silicon_wafer": (0.35, (1, 1))}),
}


def _read_tile(tx: int, ty: int, spec: WreckSpec) -> tuple[int, int] | None:
    """Tile absoluto de onde o player lê o terminal (o `reads_from` ou o tile logo abaixo do terminal)."""
    if spec.terminal is None:
        return None
    dx, dy = spec.reads_from or (spec.terminal[0], spec.terminal[1] + 1)
    return tx + dx, ty + dy
```

  Apagar `MODULE_TERMINAL_RECT`. Em `Wreck`, junto das outras properties:

```python
    @property
    def reads_from(self) -> tuple[int, int] | None:
        return _read_tile(self.tx, self.ty, self.spec)

    @property
    def sprite_rect(self) -> tuple[int, int, int, int]:
        """Retângulo do sprite no mundo (px): o mouse em cima dele é "em cima do destroço"."""
        x, y = self.blit_pos
        return x, y, *self.spec.sprite_size
```

  Em `crate_loot`, trocar a última linha das peças por:

```python
    parts = C.LOOT_RICH if wreck.rich else (wreck.spec.parts or C.LOOT_COMMON)
    items += _roll_parts(rng, parts)
```

  Atualizar a docstring do topo do módulo: 5 tipos, 8 a 10 destroços, a ordem nova.

  Em `game/config.py`, depois do bloco dos LOGs das estruturas (com o comentário `# v0.7 M3 · destroços novos (aprovados pelo dono · docs/lore/logs_v07_rascunho.md). Índices 19 e 20, nunca mudam.`):

```python
LOGS += [
    # 19 · nave de passageiros ARCA-2 (texto igual ao do rascunho)
    "Dia 2. ARCA-2, diário de bordo. Ordem da diretoria: desmontar o casco pra virar gerador e tenda. "
    "Ninguém volta, então não vai precisar de nave. O comandante assinou sem ler.",
    # 20 · robô de reconhecimento R-2
    "Dia 167. Unidade de reconhecimento R-2, relatório automático. Varredura do gelo norte: 14 pontos de calor "
    "se movendo sob a superfície, 3 metros por dia, todos na direção da colônia. Classificação: erro de sensor. "
    "Pedido de recalibração: negado.",
]
```

  Também em `game/config.py`:
  - `LOG_TITLES += ["DIARIO DE BORDO · ARCA-2", "ROBO R-2 · RELATORIO AUTOMATICO"]`, logo depois do `LOG_TITLES +=` das estruturas;
  - `LOG_DAYS += [2, 167]`, logo depois do `LOG_DAYS +=` das estruturas.

  Os `LOGS +=` precisam vir **antes** da linha do `LOG_ORDER`. Atualizar os comentários que dizem "LOG 01..19" pra "LOG 01..21".

  Em `game/art.py`, o `wreck(kind)` ganha `robot` e `liner`. Fallback simples, no tamanho do contrato: um retângulo cinza `#5a5f6a` com contorno `#1b1630` na área da pegada, deixando o `lift` transparente em cima. Ele só aparece se o PNG faltar.

```python
def wreck(kind: str) -> pygame.Surface:
    ...
    return {"cargo": _wreck_cargo, "module": _wreck_module, "probe": _wreck_probe,
            "robot": lambda: _wreck_box("robot"), "liner": lambda: _wreck_box("liner")}[kind]()


def _wreck_box(kind: str) -> pygame.Surface:
    """Fallback genérico (v0.7 M3): bloco na área da pegada, no tamanho do contrato."""
    from game.wrecks import SPECS
    spec = SPECS[kind]
    surf = pygame.Surface(spec.sprite_size, pygame.SRCALPHA)
    rect = pygame.Rect(0, spec.lift, spec.size[0] * 32, spec.size[1] * 32)
    surf.fill(pygame.Color("#5a5f6a"), rect)
    pygame.draw.rect(surf, pygame.Color("#1b1630"), rect, 1)
    return surf
```

  Conferir se os fallbacks velhos de `cargo`, `module` e `probe` desenham no tamanho velho. Se algum teste compara o tamanho do fallback com o `sprite_size`, trocar esses três também pelo `_wreck_box`. Fallback não precisa ser bonito.

  Em `game/render.py`, o `draw_wreck` passa a usar o retângulo do spec:

```python
        if self.highlight == ("wreck_log", wreck) and wreck.spec.terminal_rect:   # alvo do E: contorno só no terminal
            rx, ry, rw, rh = wreck.spec.terminal_rect
            pygame.draw.rect(canvas, self.HIGHLIGHT_RGBA[:3], (x + rx - 1, y + ry - 1, rw + 2, rh + 2), 1)
```

  A docstring do `wreck_surface` passa a listar os 5 tipos.

- [ ] **Step 4: Rodar os testes e ver passar.**
  - Rodar: `uv run pytest tests/test_wrecks.py tests/test_ruins.py tests/test_logs_tab.py -q`
  - Esperado: PASS nos testes novos.
  - `test_loot_is_fixed_by_seed_and_scales_with_size` e os testes de geração podem falhar aqui, porque a pegada mudou e a sequência ainda é a velha. Isso se resolve na Task 2. Anotar quais falharam.
- [ ] **Step 5: `uv run pytest -q`.** O que falhar e não for de geração/sequência de destroço, conserta aqui. Avisar o gerente da lista do que ficou pra Task 2.

---

### Task 2: Geração: 8 a 10, sequência nova e destroço rico

**Files:**
- Modify: `game/config.py` (`WRECK_COUNT`)
- Modify: `game/wrecks.py` (`kinds_for`, `extras_for`)
- Modify (se preciso): `game/geo.py:381` (`wreck_spot` do bolsão)
- Test: `tests/test_wrecks.py`, `tests/test_pockets.py`

**Interfaces:**
- Consome: `SPECS` da Task 1.
- Produz: `kinds_for(n: int) -> list[str]` e `extras_for(rank: int, n: int) -> tuple[int | None, str | None]` (assinaturas de hoje).

- [ ] **Step 1: Testes que falham.** Em `tests/test_wrecks.py`, trocar `test_kinds_logs_and_blueprints` por:

```python
@pytest.mark.parametrize("n", [8, 9, 10])
def test_kinds_for_sequence(n):
    kinds = wrecks.kinds_for(n)
    assert len(kinds) == n
    assert kinds[:7] == ["cargo", "probe", "module", "liner", "cargo", "probe", "robot"]
    assert kinds[-1] == "module"
    assert kinds.count("liner") == 1
    assert 1 <= kinds.count("robot") <= 2
    assert all(rank >= 6 for rank, k in enumerate(kinds) if k == "robot")   # robô da metade pra longe


@pytest.mark.parametrize("seed", SEEDS)
def test_kinds_logs_and_blueprints(seed):
    world = generate_surface(seed)
    ws = outside(world)
    assert len(ws) == len(wrecks.kinds_for(len(ws)))          # nenhum tipo pulado: a sequência é a do n
    assert [w.kind for w in ws] == wrecks.kinds_for(len(ws))
    assert ws[0].kind == "cargo" and ws[0].blueprint == "o2_tank" and ws[0].log == 3
    scanner = [w for w in ws if w.blueprint == "scanner"]
    assert len(scanner) == 1 and scanner[0].kind == "module" and scanner[0].log == 4
    assert ws[-1].kind == "module" and ws[-1].log == 6
    assert [w.log for w in ws if w.kind == "liner"] == [19]
    assert [w for w in ws if w.log == 20][0].kind == "robot"
    probe_log = [w for w in ws if w.log == 5]
    assert len(probe_log) == 1 and probe_log[0].kind == "probe"
    assert any(w.blueprint == "lamp_t2" for w in ws)
    for w in ws:
        assert (w.terminal is not None) == (w.kind == "module")
```

  Em `test_tiles_and_free_access`, a conferência do terminal passa a ser:

```python
        if w.terminal is not None:
            assert w.reads_from in reach
```

  Em `test_loot_is_fixed_by_seed_and_scales_with_size`, a ordem dos totais continua valendo pros 3 de hoje (`cargo > module > probe`). Acrescentar:

```python
    assert max(total["robot"]) < min(total["cargo"])
```

- [ ] **Step 2: Rodar e ver falhar.**
  - Rodar: `uv run pytest tests/test_wrecks.py -q`
  - Esperado: FAIL em `kinds_for`.

- [ ] **Step 3: Implementar.**
  - Em `config.py`: `WRECK_COUNT = (8, 10)` e o comentário "8 a 10 no deserto (v0.7 M3)".
  - Em `wrecks.py`:

```python
def kinds_for(n: int) -> list[str]:
    """Tipo de cada destroço, do mais perto pro mais longe (n de 8 a 10, v0.7 M3). Uma ARCA-2 (liner) por mundo;
    robô só do rank 6 pra frente (o circuito grátis chega quando o player já está perto de fabricar o dele)."""
    extras = ["robot", "cargo"][:max(0, n - 8)]
    return ["cargo", "probe", "module", "liner", "cargo", "probe", "robot", *extras, "module"]


def extras_for(rank: int, n: int) -> tuple[int | None, str | None]:
    """(LOG, diagrama) do destroço de posição `rank` (de n)."""
    if rank == 0:
        return 3, "o2_tank"            # VÉSPER-7 · o primeiro grande achado
    if rank == 2:
        return 4, "scanner"            # dia 140 · o segundo
    if rank == 3:
        return 19, None                # v0.7 M3: ARCA-2, dia 2
    if rank == 4:
        return None, "lamp_t2"
    if rank == 5:
        return 5, None                 # sonda S-3, dia 41
    if rank == 6:
        return 20, None                # v0.7 M3: robô R-2, dia 167
    if rank == n - 1:
        return 6, None                 # dia 230 · o mais longe de todos
    return None, None
```

- [ ] **Step 4: Rodar a geração em várias seeds.** Rodar `uv run pytest tests/test_wrecks.py tests/test_pockets.py tests/test_ruins.py -q`. Se `test_kinds_logs_and_blueprints` falhar porque algum destroço não coube:
  - **(a)** Medir quantas seeds de 0 a 199 perdem destroço:

    ```bash
    uv run python -c "
    from game.surface_gen import generate_surface
    from game import wrecks
    bad=[s for s in range(200) if [w.kind for w in generate_surface(s).wrecks if not w.rich]!=wrecks.kinds_for(len([w for w in generate_surface(s).wrecks if not w.rich]))]
    print(len(bad), bad[:20])"
    ```

  - **(b)** Se perder, subir `WRECK_DIST` pra `(30, 96)` e medir de novo. Se continuar perdendo, **parar e avisar o gerente** com os números. Não mexer no `WRECK_SPACING` sem o ok do dono.
- [ ] **Step 5: Destroço rico do bolsão.** O rico é `cargo`, que agora tem 5×3, e o `wreck_spot` é `(x0 + 1, top + 1)` num interior de 8×7 com o contêiner em `(x0 + pw - 2, top + 1)`. Conferir em `tests/test_pockets.py` que a pegada + caixa do rico não pisa no contêiner nem no anel, e que a caixa e o contêiner continuam alcançáveis de dentro. Se não couber, ajustar o `wreck_spot` em `game/geo.py:381` (ex.: `(x0, top + 1)`) e rodar `tests/test_pockets.py` e `tests/test_giant_pocket.py`.
- [ ] **Step 6: `uv run pytest -q` e balanceamento.**
  - Se o teto da `balance_sim` quebrar (`tests/` que chamam a sim), **não subir o teto sozinho**. Rodar `uv run python tools/dev/balance_sim.py`, anotar os números da seed 1 e avisar o gerente. Subir teto precisa do ok do dono, como no M2.
  - O bot vai à nave de carga do rank 0 (`balance_sim.py:863`), que continua `cargo`.

---

### Task 3: Terminal, mouse e prints

**Files:**
- Modify: `game/systems.py:2009-2012` (`wreck_terminal_distance`)
- Modify: `game/world.py:146-150` (`wreck_at_px`, novo)
- Modify: `game/app.py:2127-2129` (a dica do corpo do destroço)
- Create: `tools/dev/shot_v07_m3.py`
- Test: `tests/test_wrecks.py`

**Interfaces:**
- Consome: `Wreck.reads_from` e `Wreck.sprite_rect` (Task 1).
- Produz: `World.wreck_at_px(px: float, py: float) -> Wreck | None`.

- [ ] **Step 1: Testes que falham.**

```python
def test_module_terminal_reads_from_below_footprint():
    g = GameState(seed=7)
    module = next(w for w in g.world.wrecks if w.kind == "module")
    rx, ry = module.reads_from
    assert g.world.is_floor(rx, ry)
    g.player.x, g.player.y = (rx + 0.5) * C.TILE, ry * C.TILE + 6       # pés logo abaixo da pegada
    assert g.wreck_terminal_distance(module) <= C.TERMINAL_REACH
    assert g.nearby_wreck_terminal() is module


def test_wreck_at_px_covers_the_sprite_above_the_footprint():
    world = generate_surface(7)
    module = next(w for w in world.wrecks if w.kind == "module")
    x, y, w, h = module.sprite_rect
    assert world.wreck_at_px(x + w / 2, y + 4) is module           # no teto do sprite (fora da pegada)
    assert world.wreck_at_px(x - 40, y - 40) is not module
```

- [ ] **Step 2: Rodar e ver falhar.**
  - Rodar: `uv run pytest tests/test_wrecks.py -q -k "reads_from_below or wreck_at_px"`
  - Esperado: FAIL.
- [ ] **Step 3: Implementar.**

  Em `systems.py`:

```python
    def wreck_terminal_distance(self, wreck: Wreck) -> float:
        """Dos pés até a borda de cima do tile de onde se lê o terminal (`reads_from`; v0.7 M3: a base de vidro lê
        de fora da pegada)."""
        rx, ry = wreck.reads_from
        return math.hypot(self.player.x - (rx + 0.5) * C.TILE, self.player.y - ry * C.TILE)
```

  Pro módulo velho isso dá a mesma conta de antes: `reads_from` = terminal + (0, 1), e `ry · T` = `(ty + 1) · T`.

  Em `world.py`, logo depois de `wreck_at`:

```python
    def wreck_at_px(self, px: float, py: float):
        """Destroço cujo SPRITE (v0.7 M3: passa da pegada pra cima) tem esse ponto; o da frente (pé mais baixo) ganha."""
        hits = [w for w in self.wrecks
                if w.sprite_rect[0] <= px < w.sprite_rect[0] + w.sprite_rect[2]
                and w.sprite_rect[1] <= py < w.sprite_rect[1] + w.sprite_rect[3]]
        return max(hits, key=lambda w: w.anchor[1], default=None)
```

  Em `app.py:2127`, trocar `state.world.wreck_at(*self.mouse_tile())` por `state.world.wreck_at_px(*self.mouse_world())`.

  `tools/dev/shot_v07_m3.py`: seguir o molde de `tools/dev/shot_v07_m2.py`. Um print por tipo (`cargo`, `module`, `probe`, `robot`, `liner`), com o player ao lado da caixa, e mais um print do módulo com o player em `reads_from` e o terminal com contorno. Tudo em `reports/dev/v07_m3/`. Rodar com a janela headless, como o M2 faz.
- [ ] **Step 4: Rodar.**
  - Rodar: `uv run pytest tests/test_wrecks.py -q`, depois `uv run python tools/dev/shot_v07_m3.py`.
  - Olhar os prints:
    - o sprite assenta na pegada;
    - o player passa **na frente** quando está embaixo e **atrás** quando está em cima;
    - o contorno do terminal cai no terminal desenhado;
    - a caixa fica no lugar desenhado.
  - Se o contorno ou a caixa estiverem fora do desenho, **avisar o gerente com o print**. Não mexer na arte.
- [ ] **Step 5: `uv run pytest -q`.**

---

### Task 4: Save v13 e save antigo

**Files:**
- Modify: `game/wrecks.py` (`settle`, nova)
- Modify: `game/save.py` (`SAVE_VERSION`, `_v12_to_v13`, `MIGRATIONS`, chamada no `layers_from_dict`, comentário do formato)
- Test: `tests/test_save.py`

**Interfaces:**
- Consome: `layer.world.wrecks`, `layer.machines`, `layer.base.cells`, `layer.props` e `layer.crates`.
- Produz: `wrecks.settle(layer) -> None`.

- [ ] **Step 1: Testes que falham** (em `tests/test_save.py`):

```python
def test_v12_save_with_build_on_new_wreck_keeps_build_and_drops_wreck():
    state = save.new_state(7)
    liner = next(w for w in state.world.wrecks if w.kind == "liner")
    data = save.state_to_dict(state)
    data["version"] = 12
    tx, ty = liner.tiles[0]                               # no save v12, ali era areia e o player construiu
    data["layers"]["surface"]["base"].append({"kind": C.BASE_WALL, "tx": tx, "ty": ty})
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.surface.base.cells.get((tx, ty)) is not None
    assert all((w.kind, w.tx, w.ty) != ("liner", liner.tx, liner.ty) for w in loaded.world.wrecks)
    assert loaded.world.wreck_at(tx, ty) is None
    assert liner.crate not in loaded.surface.crates
    assert loaded.world.get(*liner.crate) != C.LOOT_CRATE
    assert all(loaded.world.get(*t) != C.WRECK for t in liner.tiles)
    again = save.state_from_dict(save.migrate(save.state_to_dict(loaded)))   # continua fora no save v13
    assert all((w.kind, w.tx, w.ty) != ("liner", liner.tx, liner.ty) for w in again.world.wrecks)


def test_v12_stale_changed_tile_does_not_punch_hole_in_wreck():
    state = save.new_state(7)
    module = next(w for w in state.world.wrecks if w.kind == "module")
    data = save.state_to_dict(state)
    data["version"] = 12
    hole = module.tiles[0]
    data["layers"]["surface"]["changed_tiles"].append([*hole, C.SAND])   # rocha minerada no mundo velho
    loaded = save.state_from_dict(save.migrate(data))
    assert loaded.world.get(*hole) == C.WRECK
    assert loaded.world.get(*module.crate) == C.LOOT_CRATE


def test_v12_old_crate_position_is_ignored():
    state = save.new_state(7)
    data = save.state_to_dict(state)
    data["version"] = 12
    data["layers"]["surface"]["crates"] = [[3, 3, [], True]]      # caixa que não existe mais
    loaded = save.state_from_dict(save.migrate(data))
    assert all(not c.opened for c in loaded.surface.crates.values())


def test_save_version_is_13():
    assert save.SAVE_VERSION == 13
    assert save.migrate({"version": 12, "layers": {}})["version"] == 13
```

  Ajustar os testes de `test_save.py` que fixam `SAVE_VERSION == 12`.

- [ ] **Step 2: Rodar e ver falhar.**
  - Rodar: `uv run pytest tests/test_save.py -q`
  - Esperado: FAIL.
- [ ] **Step 3: Implementar.**

  Em `wrecks.py`, depois de `keep_free`:

```python
def settle(layer) -> None:
    """v0.7 M3 (save antigo, opção A do dono): roda em todo load. Destroço com máquina, bloco ou prop do player na
    pegada ou na caixa sai deste mundo (tiles viram chão, a caixa some, sai de `world.wrecks`). Os outros têm a
    pegada e a caixa recarimbadas: um `changed_tiles` de save v12, cuja posição velha agora cai num destroço novo,
    não abre buraco. Antes do laço das caixas e do `removed_crates` (a caixa desmontada continua sumindo)."""
    world = layer.world
    if not getattr(world, "wrecks", None):
        return
    taken = {t for m in layer.machines for t in m.tiles} | set(layer.base.cells)
    taken |= {t for t, p in layer.props.items() if not p.ruin}
    live = []
    for wreck in world.wrecks:
        area = [*wreck.tiles, wreck.crate]
        if any(t in taken for t in area):
            for t in area:
                if world.get(*t) in (C.WRECK, C.LOOT_CRATE):
                    world.set(*t, world.floor_kind)
            layer.crates.pop(wreck.crate, None)
            continue
        for t in wreck.tiles:
            world.set(*t, C.WRECK)
        world.set(*wreck.crate, C.LOOT_CRATE)
        live.append(wreck)
    world.wrecks = live
    world._wreck_index = None
```

  > Nota: a casca das ruínas está em `layer.base.cells`, mas nunca encosta num destroço (`RUIN_SPACING`). O `world` é uma cópia (`generate_surface` devolve `_copy`), então trocar `world.wrecks` não suja o cache. **Confirmar** que `_copy` não compartilha o objeto `World`.

  Em `save.py`, `layers_from_dict`, logo depois de `ruins.apply_overlays(layer)`:

```python
        wrecks.settle(layer)            # v0.7 M3: destroço em cima de construção (save v12) não nasce; os outros recarimbados
```

  Com `from game import wrecks` no topo. O `from game.wrecks import loot_for` continua. Depois:

```python
SAVE_VERSION = 13  # v13 (v0.7 M3): destroços novos (a mesma seed põe os destroços em outro lugar; wrecks.settle) · v12 ...


def _v12_to_v13(data: dict) -> dict:
    """v0.7 M3: os destroços mudaram (8–10, 5 tipos, pegadas maiores) e saem da seed em outro lugar. Nada no dict
    muda: o `wrecks.settle` do load tira o destroço que bateria em construção do player e ignora as caixas velhas."""
    return data


MIGRATIONS: dict = {10: _v10_to_v11, 11: _v11_to_v12, 12: _v12_to_v13}
```

  Atualizar o comentário do formato no topo do `save.py`: "v13: destroços do v0.7 M3".

- [ ] **Step 4: Rodar.** `uv run pytest tests/test_save.py tests/test_wrecks.py tests/test_ruins.py -q` → PASS.
- [ ] **Step 5: `uv run pytest -q` inteiro.** Avisar o gerente com o número final (passed/skipped) e o que mudou fora do plano.

---

## Testes do dono (depois do merge; o gerente monta o checklist)
- Mundo novo:
  - acha os 5 tipos;
  - a VÉSPER perto da base;
  - a ARCA-2 no meio do caminho, com o LOG do dia 2;
  - o robô longe, com circuito na caixa;
  - a base de vidro com o terminal lido de baixo.
- Mouse no teto dos sprites grandes mostra o nome.
- Save antigo carrega: os destroços em lugar novo, nada em cima do que tu construiu.
- Aba LOGs com 21 e a numeração nova.
