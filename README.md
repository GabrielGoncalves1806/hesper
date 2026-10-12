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
| Hotbar | 1 a 8 ou a rodinha do mouse escolhem o slot · se for máquina, já entra no modo de colocar |
| Inventário | Tab · clique pega/solta a pilha · clique direito pega metade |
| Baú | E perto dele · clique esquerdo manda a pilha inteira pro outro lado · clique direito manda 1 · Shift+clique manda todas as pilhas daquele item · botões **Pegar tudo** e **Guardar recursos** (só ferro, silício e gelo) · o fabricador usa o que está nos baús da base |
| Nome do baú | no painel do baú, clique no nome · digite (até 16 letras) · Enter confirma · Esc cancela · Backspace apaga · o nome flutua em cima do baú quando tu chega perto ou passa o mouse |
| Estação de drones | E perto dela · clique no drone do inventário põe na estação (esquerdo: quantos couberem nos 4 slots, direito: 1) · clique num drone pousado tira (em voo fica travado) · clique no buffer tira o minério (direito: 1) · **Pegar tudo** leva o buffer |
| Drone | item do fabricador (6 ferro + 4 silício, libera na Névoa) · não vai pro chão: vai num slot da estação |
| Coletar drill | E perto dela (leva o minério que ela extraiu pro inventário) |
| Desmontar máquina | clique direito em cima dela (volta pro inventário; baú só vazio; a estação devolve junto os drones e o minério) |
| Pausa | Esc (Continuar, Opções, Controles, Salvar e sair, Sair) · em Opções ficam volumes, tela cheia e zoom, salvos em `settings.json` |
| Zoom do mundo | + / - (ou = e o teclado numérico) · Ctrl+rodinha (Cmd no Mac) · 0,75× · 1× · 1,5× · 2× · HUD e menus não mudam de tamanho |
| Tela cheia | F11 ou Alt+Enter (resolução do monitor, 16:9 com tarja preta se precisar) |
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
| `game/render.py` | desenha o mundo: só os tiles visíveis, paredes altas, objetos por profundidade, luz e clima do estágio |
| `game/ui.py` | HUD, fabricador, terminal, banner, O₂ crítico, desmaio e tela de fim (desenhado em 480×270 e esticado 2×, igual ao mockup) |
| `game/art.py` | os desenhos "de retângulos" usados enquanto não tem sprite aprovado |
| `game/assets.py` | carrega sprites e fontes; se o PNG não existir, devolve nada e o jogo usa o desenho de fallback |
| `game/audio.py` | som: efeitos com variação de pitch, alarme de O₂ com histerese, zumbido pela distância, ambiente com crossfade entre estágios |

O fluxo de um frame: `App.handle_events()` → `App.update(dt)` (que chama `GameState.update`) → `App.draw()`
(que chama `Renderer.draw` e depois a `UI`). O `GameState` nunca toca som nem desenha: ele só anota o que aconteceu
numa lista de eventos (`"break"`, `"pickup"`, `"stage_up"`...) e o `App` decide o que fazer com isso.

### Paredes altas e profundidade

Cada parede tem altura: o topo da rocha é desenhado 24 px **acima** do tile dela e, se embaixo tem chão,
a face frontal aparece embaixo do topo. Por isso o desenho é feito em duas passadas:

1. todo o chão e a água;
2. linha por linha, de cima pra baixo: as paredes da linha e depois os objetos (player, máquinas, cápsula,
   plantas) cujo pé está nessa linha.

Assim, quem anda logo acima de uma parede fica meio escondido atrás do topo dela (estilo Core Keeper).
Quando isso acontece com o player, o jogo redesenha ele translúcido por cima, pra ele nunca sumir num túnel.
A ordem é calculada por `build_draw_list` (em `render.py`), uma função pura com testes.
A colisão continua sendo o tile: a altura é só visual. O mouse mira no que está à vista (`World.visual_tile_at`).

## Assets

Sprites e sons ficam em `assets/` e seguem o contrato da bíblia (§6). Eles só entram no jogo depois de aprovados,
pelas flags em `game/config.py`:

- `ENABLE_SPRITES = True`: os sprites aprovados (design v2.1) estão ligados.
- `ENABLE_AUDIO = True`: os sons aprovados (som v3) estão ligados. Os volumes de cada categoria ficam
  em `VOLUME` no `config.py`, comentados, pra ajustar depois de cada playtest.

Com uma flag ligada e algum arquivo faltando, o jogo continua funcionando com o desenho de fallback (ou em silêncio).
Pra ver o jogo só com o fallback de retângulos, é só desligar `ENABLE_SPRITES`.

As fontes Silkscreen e Pixelify Sans (licença OFL) estão em `game/fonts/`, junto com as licenças.
