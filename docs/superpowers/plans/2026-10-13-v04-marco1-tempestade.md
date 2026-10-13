# v0.4 Marco 1 · Tempestade · Plano de implementação

> **Pra agentes:** cada Dev roda num worktree isolado e executa só a sua trilha. Quem faz os merges é o gerente. Os passos usam checkbox (`- [ ]`).

**Objetivo:** o jogo passa a ter 4 estágios (Tempestade → Árido → Névoa → Verde) e começa numa tempestade de poeira: visão curta, rajadas que empurram e chiam o minimapa, O₂ gastando mais rápido. Tudo isso some ao passar pro Árido.

**Arquitetura:**
- A trilha **A** renumera os estágios e cria a intensidade da tempestade, `state.storm` (de 1.0 a 0.0), com a transição de 20 s.
- A trilha **B** cria o modelo de clima (`game/weather.py`: vento e rajadas) e os efeitos de jogo (empurrão, O₂, aviso, som).
- A trilha **C** desenha a tempestade (poeira, visão, partículas, chiado do minimapa/mapa), lendo o que A e B expõem.

As três trilhas combinam as interfaces abaixo e não mexem nos arquivos das outras, a não ser nos pontos indicados.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

## Restrições globais (da spec `docs/superpowers/specs/2026-10-13-v04-mundo-vivo-design.md`)

- **Estágios:**

  | # | Chave | Ti |
  |---|---|---|
  | 1 | `storm` | 0 |
  | 2 | `arid` | 2.500 (o simulador ajusta pra cair em 8–12 min no casual) |
  | 3 | `mist` | 10.000 |
  | 4 | `green` | 100.000 |

- **Arte:** `storm` e `arid` usam a arte do `dead`.
- **Visão:** ~7 tiles na tempestade, ~4 durante a rajada. As máquinas da base também abrem a vista.
- **Rajadas:** a cada 20–40 s (sorteio com seed), cada uma durando 3–5 s. O empurrão é de 35% da `PLAYER_SPEED` na direção do vento, e dá pra vencer andando contra.
- **O₂:** ×1,25 fora da base, só na tempestade.
- **Transição Tempestade → Árido:** ~20 s. A poeira afina, as rajadas param, aparece o aviso de estágio e toca o jingle.
- **Caverna:** a tempestade não entra lá.
- **Save:** save v6 carregado mapeia o estágio 1→2, 2→3 e 3→4 (começa no Árido).
- **Regras da casa:**
  - não commitar (o gerente commita);
  - não abrir janela visível;
  - `uv run pytest`, `uv run python tools/dev/smoke.py` e `uv run python tools/dev/real_video_check.py` têm que passar;
  - os números ficam em `game/config.py`;
  - a bíblia (`docs/GAME_BIBLE.md`) é atualizada pela trilha A (estágios) e pela B (tempestade).

## Interfaces combinadas (valem pras 3 trilhas)

```python
# game/config.py  (trilha A cria os estágios; trilha B cria o bloco STORM_*)
STAGES: list[Stage]          # 4 itens, chaves "storm", "arid", "mist", "green"
STORM_STAGE = 1              # trilha A
STORM_FADE_S = 20.0          # trilha A
# trilha B:
STORM_VIEW_TILES = 7.0
STORM_GUST_VIEW_TILES = 4.0
STORM_GUST_EVERY = (20.0, 40.0)
STORM_GUST_LEN = (3.0, 5.0)
STORM_PUSH = 0.35            # fração da PLAYER_SPEED
STORM_O2_MULT = 1.25

# game/render.py (trilha A)
def stage_key(stage: int) -> str          # "storm" | "arid" | "mist" | "green" (já existe, passa a ter 4)
def art_key(stage: int) -> str            # NOVO: "dead" | "mist" | "green" (storm/arid -> "dead")

# GameState (trilha A)
state.storm: float   # 1.0 = tempestade cheia, 0.0 = sem tempestade. Sobe/desce em STORM_FADE_S.
                     # Fica em 0.0 a partir do Árido e na caverna (vale o state.layer == "cave" -> efetivo 0).
def storm_level(state) -> float           # em game/systems.py: 0.0 na caverna, senão state.storm

# game/weather.py (trilha B)
class Weather:
    def __init__(self, seed: int): ...
    def update(self, dt: float, storm: float) -> None: ...   # storm = storm_level(state)
    wind: tuple[float, float]       # vetor unitário da direção do vento (varia devagar)
    gust: float                     # 0.0..1.0, intensidade da rajada agora (sobe e desce suave)
    view_tiles: float               # raio de visão atual em tiles (inf quando storm == 0)
state.weather: Weather              # a trilha B cria no GameState.__init__
```

Enquanto as outras trilhas não foram mergeadas, cada uma lê o que é da outra com fallback:
- `getattr(state, "storm", 0.0)`;
- `getattr(state, "weather", None)`.

Ninguém declara o campo que pertence a outra trilha. O gerente tira os fallbacks no merge.

---

## Trilha A · Estágios (Dev A)

**Arquivos:**
- `game/config.py`: STAGES, STORM_STAGE, STORM_FADE_S, e as tabelas indexadas por número de estágio, como WATER_THRESHOLD, STAGE_COLOR e PALETTES. Tudo que hoje usa 1..3 passa a usar 1..4, e storm/arid usam os valores do dead.
- `game/render.py`: `art_key` e todo lugar que escolhe sprite ou paleta pelo estágio. Confira também o `CAVE_STAGE`.
- `game/systems.py`: `state.storm`, a transição e `storm_level`.
- `game/save.py`: migração do estágio no v6.
- `game/objectives.py`: "Limpe o céu" ligado ao Árido.
- `game/app.py`: banner de estágio. O Árido tem título e subtítulo próprios, ex.: "ESTÁGIO 2 · CÉU LIMPO" / "A poeira baixou".
- `game/audio.py`: `ambient_for`, que hoje cai em `amb_{stage_key}`. Pra storm, toca `amb_storm` se existir, senão `amb_dead`; pra arid, `amb_dead`.
- `tools/dev/balance_sim.py`: ajustar o Ti do Árido.
- `docs/GAME_BIBLE.md`: tabela de estágios do §4.
- `tests/test_stages_v04.py`

**Tarefas:**
- [ ] **A1.** Teste primeiro e depois a implementação:

  ```python
  def test_four_stages_in_order():
      assert [s.key for s in C.STAGES] == ["storm", "arid", "mist", "green"]
      assert [s.ti for s in C.STAGES][:1] == [0] and C.STAGES[2].ti == 10_000 and C.STAGES[3].ti == 100_000

  def test_art_key_maps_storm_and_arid_to_dead():
      assert [art_key(i) for i in (1, 2, 3, 4)] == ["dead", "dead", "mist", "green"]
  ```

  Depois, varra todo uso de `stage_key(`, `C.STAGES[`, `PALETTES[`, `WATER_THRESHOLD`, `STAGE_COLOR` e `== 3` / `>= 2` ligados a estágio (`grep -n "stage" game/*.py`) e corrija. **Névoa agora é 3 e Verde é 4.** O fim do jogo continua no Verde.
- [ ] **A2.** `state.storm` com a transição:
  - começa em 1.0 no novo jogo;
  - quando `state.stage` passa de STORM_STAGE, desce linear até 0 em STORM_FADE_S;
  - salvar e carregar no meio da transição mantém o valor;
  - `storm_level(state)` dá 0 na caverna.

  ```python
  def test_storm_fades_over_20s_after_arid():
      s = GameState(); assert s.storm == 1.0
      s.ti = C.STAGES[1].ti; s.update_stage()      # use a função real que sobe estágio
      step(s, 10.0); assert 0.4 < s.storm < 0.6
      step(s, 11.0); assert s.storm == 0.0

  def test_storm_level_is_zero_in_cave():
      s = GameState(); s.layer = "cave"; assert storm_level(s) == 0.0
  ```

- [ ] **A3.** Save:
  - o v7 grava `storm`;
  - **o save v6 sobe o estágio em +1 e carrega com `storm = 0`**.

  Ainda não sobe a versão do formato pra exigir novo jogo; isso é do Marco 2. Use a migração existente (`save.migrate`) com um campo de versão de estágio, ex. `progress.stage_scheme = 2`. Teste: um dict de save v6 com estágio 2 carrega com estágio 3 e storm 0.
- [ ] **A4.** Banner do Árido, objetivo "Limpe o céu" e áudio. Teste do `ambient_for` com storm, arid, mist e green.
- [ ] **A5.** No `balance_sim.py`, ajuste o Ti do Árido pra cair entre 8 e 12 min no casual e reporte os tempos totais antes e depois. Se o tempo total da partida mudar mais de 3 min, avise sem ajustar mais nada.
- [ ] **A6.** Validação:
  - pytest, smoke e real_video_check;
  - prints do banner do Árido e do jogo novo no estágio 1.

## Trilha B · Clima e jogabilidade (Dev B)

**Arquivos:**
- `game/weather.py` (novo)
- `game/config.py`: o bloco STORM_*
- `game/systems.py`:
  - criar `state.weather`;
  - chamar `weather.update(dt, storm)`;
  - somar o empurrão no movimento do player;
  - O₂ ×1,25.
- `game/ui.py`: aviso de rajada no HUD, um pequeno "RAJADA" com ícone de vento perto do O₂, no estilo B2.
- `game/audio.py`: tocar `gust` no começo de cada rajada, com volume proporcional ao storm. Sem o arquivo, fica em silêncio.
- `docs/GAME_BIBLE.md`: seção da tempestade.
- `tests/test_weather.py`

**Tarefas:**
- [ ] **B1.** `Weather` determinístico pela seed:
  - o vento muda devagar (≤ 15°/s);
  - as rajadas seguem STORM_GUST_EVERY/LEN;
  - `gust` sobe e desce em ~0,5 s;
  - `view_tiles` interpola de STORM_VIEW_TILES até STORM_GUST_VIEW_TILES conforme o gust e vai pra infinito conforme o storm cai (com storm 0 é `math.inf`);
  - com storm 0, nenhuma rajada começa.

  ```python
  def test_gusts_happen_on_schedule_and_only_in_storm():
      w = Weather(1); times = []
      for i in range(int(120 / 0.05)):
          prev = w.gust; w.update(0.05, 1.0)
          if prev == 0 and w.gust > 0: times.append(i * 0.05)
      assert 3 <= len(times) <= 6
      w2 = Weather(1)
      for _ in range(2400): w2.update(0.05, 0.0)
      assert w2.gust == 0 and w2.view_tiles == math.inf

  def test_view_shrinks_in_gust():
      w = Weather(1); w.gust = 1.0; w._recompute(storm=1.0)
      assert w.view_tiles == pytest.approx(C.STORM_GUST_VIEW_TILES)
  ```

  O `_recompute` é o ponto interno que calcula o `view_tiles`. Use o nome que fizer sentido, mas teste por ele.
- [ ] **B2.** Empurrão:
  - durante a rajada, o player ganha `wind * C.PLAYER_SPEED * C.STORM_PUSH * gust * storm` px/s, somado ao movimento e com a mesma colisão do `Player.move`;
  - parado, ele desliza;
  - andando contra, avança mais devagar;
  - desmaiado, em transição de rampa ou com tela aberta (inventário, fabricador etc.), não tem empurrão.

  Testes:
  - deslocamento parado durante a rajada > 0;
  - andando contra, ainda anda pra frente;
  - nunca atravessa parede.
- [ ] **B3.** O₂: `C.O2_DRAIN * (C.STORM_O2_MULT if storm_level(state) > 0 and fora da zona else 1)`. Com storm parcial, interpola: `1 + (MULT - 1) * storm`. Testes: dentro da zona não muda, e na caverna não muda.
- [ ] **B4.** Aviso de rajada no HUD e o som `gust`. Teste do aviso: aparece com gust > 0.3 e some depois.
- [ ] **B5.** Validação: pytest, smoke (uma cena de rajada com o player empurrado) e real_video_check.

## Trilha C · Visual da tempestade (Dev C)

**Arquivos:**
- `game/dust.py` (novo): camada de poeira.
- `game/render.py`: só a chamada da camada de poeira e das partículas, na ordem de desenho certa. **Não mexa** em `stage_key`/`art_key`/paletas, que são da trilha A.
- `game/ui.py`: chiado no minimapa e no mapa aberto (função `static_noise(surf, amount, t)`). **Não mexa** no HUD de rajada, que é da trilha B.
- `tests/test_dust.py`

**Tarefas:**
- [ ] **C1.** Camada de poeira, reaproveitando o `game/lighting.Lighting` (célula de 4 px):
  - o fundo é a cor da poeira, não o preto. Chute `#8a5a3c`, que a Designer vai trocar;
  - a opacidade é `storm * 0.92`, e cresce um pouco com o gust;
  - a "luz" de visão fica no player com raio `weather.view_tiles` (sem weather: `C.STORM_VIEW_TILES`, quando existir, senão 7);
  - as máquinas da base abrem 2,5 tiles cada;
  - o ponto de visão tem o mesmo viés pra onde o player olha que a lanterna da caverna tem;
  - a HUD fica por cima;
  - com storm 0 não desenha nada, e o custo tem que ser zero.

  ```python
  def test_no_dust_when_storm_is_zero():
      layer = DustLayer(); surf = layer.render(view_size=(480, 270), storm=0.0, gust=0.0, view_px=224, lights=[], player=(240, 135))
      assert surf is None

  def test_center_is_clear_and_edges_are_dusty():
      layer = DustLayer(); surf = layer.render((480, 270), 1.0, 0.0, 224, [], (240, 135))
      assert surf.get_at((240, 135)).a < 40 and surf.get_at((5, 5)).a > 200
  ```

  Use **formato explícito** de surface (regra nova: `tests/test_surface_format.py` e `game/surfaces.py`). Superfície com alfa é `pygame.SRCALPHA`.
- [ ] **C2.** Partículas e faixas de vento:
  - grãos e faixas longas andando na direção do `weather.wind` (sem weather: vento fixo pra leste);
  - velocidade e densidade proporcionais a storm e gust;
  - por cima do mundo e por baixo da HUD;
  - quantidade limitada (≤ 250 grãos);
  - determinístico por seed no smoke.

  Teste: o número de partículas é 0 com storm 0 e ≤ 250 com storm 1 e gust 1.
- [ ] **C3.** Chiado: o minimapa e o mapa aberto ganham ruído (pixels claros e escuros aleatórios, mais 1 ou 2 linhas de interferência) proporcional a `gust * storm`. Teste: com amount 0 a surface não muda; com amount 1, mais de 5% dos pixels mudam.
- [ ] **C4.** Desempenho: o smoke numa cena de tempestade com rajada tem que ficar no orçamento de 16,7 ms (meta: menos de +2 ms de média em relação a hoje). Reporte o número.
- [ ] **C5.** Validação:
  - pytest, smoke e real_video_check;
  - prints da tempestade normal, da rajada, da tempestade perto da base (máquinas abrindo a vista) e do minimapa chiando.

## Arte e som (pra aprovação do dono)

- **Designer:**
  - cor de fundo da poeira e paleta das partículas (2–3 tons);
  - textura opcional de faixa de vento;
  - mockup 960×540 da tempestade normal, da rajada e do Árido limpo, pra comparar;
  - se precisar, o ícone de vento do aviso RAJADA.

  Tudo vai em `assets/sprites/_pending/` com report.
- **Som:**
  - `amb_storm` (vento forte em loop, emenda limpa);
  - `gust` (rajada, 3–5 s, cresce e cai);
  - opcional: jingle de "céu limpo".

  Tudo vai em `assets/audio/_pending/` com report.

## Ordem de merge (gerente)

1. **A**, que define estágios e `state.storm`.
2. **B**, que tira os fallbacks de `storm`.
3. **C**, que tira os fallbacks de `weather`.

Depois de cada merge: pytest, smoke e real_video_check. Com os três dentro, o gerente olha os prints e chama o dono pra testar. Os assets aprovados são promovidos depois.
