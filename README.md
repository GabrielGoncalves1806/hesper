# Hesper (MVP v0.1)

Jogo 2D top-down de sobrevivência e terraformação. Tu cai numa cratera de um planeta morto,
minera as paredes, fabrica máquinas que aumentam O₂, calor e água, e vê o planeta mudar de cara.
A fonte da verdade do design é `docs/GAME_BIBLE.md`.

## Instalar e rodar

Precisa do [uv](https://docs.astral.sh/uv/) instalado (ele baixa o Python 3.13 e o pygame-ce sozinho).

```bash
uv sync                      # instala as dependências
uv run python -m game        # roda o jogo
uv run python -m game --scale 2   # força o zoom da janela (padrão: o maior que cabe na tela)
```

## Controles

| Ação | Tecla |
|---|---|
| Andar | WASD (ou setas) |
| Minerar | segurar o botão esquerdo do mouse em cima da parede (alcance 2 tiles) |
| Fabricador | E (só dentro do círculo azul da base) · W/S escolhe · clique ou Enter fabrica |
| Colocar máquina | depois de fabricar, clique no chão · R gira · Esc ou botão direito cancela |
| Escolher máquina já fabricada | 1 a 6 (aparece no HUD, em cima do inventário) |
| Ler terminal | E perto dele |
| Debug | F1 acelera o tempo ×10 (O₂ e máquinas) · F2 soma +10.000 Ti |

## Testes

```bash
uv run pytest                     # testes da lógica (não abrem janela)
uv run python tools/dev/smoke.py  # roda o jogo sem janela, simula input e salva prints em reports/dev/
```

## Como o código está organizado

Um jogo é basicamente um laço que roda 60 vezes por segundo: **lê o input → atualiza as regras → desenha a tela**.
Cada volta recebe o `dt` (quanto tempo passou desde a anterior) e tudo que se move ou conta tempo multiplica por ele,
assim o jogo anda na mesma velocidade num PC rápido ou lento. O código separa esse laço em peças pequenas:

| Módulo | O que faz |
|---|---|
| `game/config.py` | todos os números e tabelas da bíblia: paletas, receitas, tempos de mineração, O₂, estágios, textos dos logs |
| `game/world.py` | o mapa 128×128: gera com noise (seed fixa = sempre o mesmo mapa), cratera, minério, terminais, poças e plantas |
| `game/player.py` | o astronauta: posição, direção (baixo/cima/esquerda/direita) e movimento com colisão |
| `game/systems.py` | as regras (`GameState`): mineração, O₂, desmaio, fabricador, máquinas, Ti e estágios. **Python puro, sem pygame**, por isso dá pra testar fácil |
| `game/app.py` | o game loop: transforma teclado/mouse num `Controls`, chama `GameState.update(dt, controls)`, reage aos eventos (som, textos flutuantes, banner) e manda desenhar |
| `game/render.py` | desenha o mundo: só os tiles visíveis, objetos ordenados pelo Y do pé (quem está mais embaixo fica na frente), luz e clima do estágio |
| `game/ui.py` | HUD, fabricador, terminal, banner, O₂ crítico, desmaio e tela de fim (desenhado em 480×270 e esticado 2×, igual ao mockup) |
| `game/art.py` | os desenhos "de retângulos" usados enquanto não tem sprite aprovado |
| `game/assets.py` | carrega sprites e fontes; se o PNG não existir, devolve nada e o jogo usa o desenho de fallback |
| `game/audio.py` | som: efeitos com variação de pitch, alarme de O₂ com histerese, zumbido pela distância, ambiente com crossfade entre estágios |

O fluxo de um frame: `App.handle_events()` → `App.update(dt)` (que chama `GameState.update`) → `App.draw()`
(que chama `Renderer.draw` e depois a `UI`). O `GameState` nunca toca som nem desenha: ele só anota o que aconteceu
numa lista de eventos (`"break"`, `"pickup"`, `"stage_up"`...) e o `App` decide o que fazer com isso.

## Assets

Sprites e sons ficam em `assets/` e seguem o contrato da bíblia (§6). Eles só entram no jogo depois de aprovados,
pelas flags em `game/config.py`:

- `ENABLE_SPRITES = True`: os sprites do design v2 foram aprovados e estão ligados.
- `ENABLE_AUDIO = False`: o código de som está pronto, mas os sons ainda estão em revisão.

Com uma flag ligada e algum arquivo faltando, o jogo continua funcionando com o desenho de fallback (ou em silêncio).
Pra ver o jogo só com o fallback de retângulos, é só desligar `ENABLE_SPRITES`.

As fontes Silkscreen e Pixelify Sans (licença OFL) estão em `game/fonts/`, junto com as licenças.
