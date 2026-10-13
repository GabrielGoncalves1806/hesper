# Hesper: bíblia do jogo

> Codinome provisório. Esse documento é a fonte da verdade pra equipe toda (Dev, Designer, Som).
> Mudou alguma decisão? Muda aqui primeiro.

## 1. Conceito

Jogo 2D top-down (visão 3/4, estilo Core Keeper) de **sobrevivência e terraformação** (estilo The Planet Crafter).
Tu cai num planeta morto, minera as paredes de uma cratera, fabrica máquinas que aumentam oxigênio, calor e água,
e vê o planeta **mudar visualmente** conforme o índice de terraformação (Ti) sobe.

**Pilares**
1. **Progresso visível:** o mapa muda de cara (morto → névoa → verde). Essa é a recompensa principal.
2. **Ir e voltar:** o O₂ te obriga a voltar pra base. Cavar mais fundo é sempre um risco calculado.
3. **Mistério:** alguém já tentou terraformar esse planeta e deu errado. Tu descobre isso aos poucos.

## 2. Lore

- O planeta já recebeu uma colônia: **Colônia Hesper**. A tentativa de terraformação deu errado e a colônia sumiu.
- Personagem citada: **Dra. Ilves**, cientista da colônia, desconfiava do gelo do planeta ("não é só água").
- O jogador é um terraformador enviado depois, numa cápsula (a base inicial).
- No MVP a lore aparece em **3 terminais** escondidos nas paredes:

| Log (exibido) | Texto |
|---|---|
| LOG 01 | "Dia 3. Pouso perfeito. A cratera é maior do que as sondas mostraram. Começamos a montar os geradores amanhã." |
| LOG 03 | "Dia 97. O índice subiu rápido demais esse mês. A Dra. Ilves pediu pra desacelerar. A diretoria disse que o cronograma não espera." |
| LOG 06 | "Dia 212. O derretedor 4 parou de novo. A Dra. Ilves jura que o gelo daqui não é só água, que tem alguma coisa dentro dele. Ninguém quis ouvir. Amanhã a gente desce pro nível 2 de qualquer jeito." |

O mistério do gelo **não se resolve no MVP**. É gancho pro futuro.

**Numeração = cronologia da história** (v0.3): o número que o jogador vê ("LOG 01".."LOG 07") é a posição do LOG na linha do tempo, não a ordem em que ele acha. Cada LOG tem um dia (`LOG_DAYS` no `config.py`, mesma ordem de `LOGS`) e `LOG_ORDER` ordena por ele. Os índices em `LOGS` nunca mudam (o save guarda índices). Com os 4 dos destroços (ver §9, Marco 3): dias 3, 41, 97, 140, 188, 212 e 230. Todo texto de LOG começa com "Dia N.". Os lidos ficam na **aba LOGs** do inventário (Tab) pra reler.

## 3. Direção visual

Referência obrigatória: `reports/mockups/mockups.html` (abre no navegador).

- **Tile 32×32 px**, visão top-down 3/4. Quando o tile de baixo é chão, a parede mostra uma faixa de topo de 8 px e uma **face frontal alta de 24 px**. A parede tem que parecer parede, não degrau.
- **Resolução interna 960×540** (30×17 tiles visíveis), escalada inteira pra janela. Pixel art sem suavização.
- Personagem: o **Explorador**, chibi **32×32** (v6.0, aprovado pelo dono), com capacete em domo (~metade da altura), **visor dourado** refletivo em faixa com reflexo duro, lanterna na lateral e antena; traje branco, ombreiras e joelheiras de metal cinza, acento laranja `#e2733a` (o das máquinas), cachecol cor de ferrugem, botas escuras com poeira e mochila com 2 tanques. Contorno `#1b1630`. Tem 3 direções (baixo, cima, lado) e as animações andando, parado (idle) e minerando. Gerado por `tools/sprites/explorer.py`.
- Luz: cosmética no MVP (brilho das máquinas e do capacete). Escuridão de verdade só no v0.3.

### Paletas por estágio (hex)

| Elemento | Morto (Tempestade e Árido, Ti < 10k) | Névoa (10k–100k) | Verde (≥ 100k) |
|---|---|---|---|
| Chão | `#7b402c` `#743b29` `#814430` | `#6e5a4f` `#685448` `#75604f` | `#4d7a39` `#477235` `#548140` |
| Rocha topo | `#4b3332` `#563a38` | `#4a4447` `#544d50` | `#4b4a45` `#55544e` |
| Rocha luz/sombra | `#6e4b47` / `#352323` | `#6c6467` / `#343033` | `#6d6c64` / `#353530` |
| Face da parede | `#2f1f1f` | `#2b272a` | `#2c2c28` |
| Água | **nenhuma** (sem atmosfera não há água líquida) | `#3f7690` | `#2c7ea6` |
| Extra | poeira laranja no ar | névoa + chuva fina | grama `#79b04f`, musgo `#5c9a43` |

**Minérios:** ferro `#e8a066` (sombra `#a5582c`), silício `#c3d1e2` (`#7d8ca3`), gelo `#a6ecff` (`#4fb3d6`).
**Cores de UI:** ciano O₂ `#59d0e6`, laranja de destaque `#e2733a`, dourado do Ti `#f2c46d`, verde OK `#7fd67a`, vermelho alerta `#ff6a55`.
**Fontes de UI:** Silkscreen (rótulos) e Pixelify Sans (textos), ambas Google Fonts, licença OFL.

## 4. Escopo do MVP (v0.1)

**Regra:** só entra o que é necessário pra fechar o loop uma vez:
`cavar → coletar → craftar → colocar máquina → índice sobe → mundo muda → libera receita nova`

### Mundo
- Mapa fixo de **128×128 tiles**, gerado por noise com seed fixa.
- Cratera aberta no centro (raio ~12 tiles) com a cápsula. Rocha em volta. Quanto mais longe do centro, mais minério.
- Câmera segue o player.
- 3 terminais de lore espalhados a distâncias crescentes da base.

### Player e controles
| Ação | Tecla |
|---|---|
| Andar | WASD |
| Minerar | segurar botão esquerdo do mouse (alcance 2 tiles) |
| Abrir/fechar fabricador | E (só na zona da base) |
| Colocar máquina | clique esquerdo com máquina selecionada · R gira (cosmético) · Esc cancela |
| Ler terminal | E perto do terminal |
| Interagir (E) | Abre o que está **debaixo do mouse** (baú, drill, estação ou terminal) se estiver no alcance do E; senão, o mais perto do player; sem nada no alcance, na base abre o fabricador. Vale igual pro **Shift+E** na drill. O alvo ganha um **contorno claro** e o texto do canto mostra o que o E vai abrir (com o mouse numa máquina que o E não vai abrir, o canto diz qual ele abre) |
| Zoom do mundo | + / - (ou = e o teclado numérico) · Ctrl+rodinha (Cmd no Mac) · níveis 0,75× · 1× · 1,5× · 2× (padrão 1×). Só o mundo aproxima: HUD e menus ficam do mesmo tamanho |
| Tela cheia | F11 ou Alt+Enter · também em Pausa > Opções. Usa a resolução do monitor mantendo 16:9 (tarja preta se sobrar) |
| Tamanho da interface | Pausa > Opções > **Interface: Grande / Média / Pequena** (padrão **Média**, salvo em `settings.json`). Muda só HUD, menus, inventários, fabricador, título, terminal, avisos e tooltips; o mundo continua no zoom escolhido. Grande = a UI de sempre (480×270 esticada pra tela); Média ≈ 75% disso; Pequena ≈ 50%. Em Média/Pequena a escala é inteira (letra pixel art limpa) e nunca menor que 1 px de imagem por px de tela: em 1920×1080 dá 4 / 3 / 2 px por px da UI; numa janela de 960×540 os três ficam iguais. Os painéis se ancoram nos cantos/centro. Textos presos no mundo (+15 FERRO, nome do baú) acompanham o mundo na posição e a interface no tamanho da letra |
| Debug (dev) | F1 acelera o tempo ×10 · F2 +10.000 Ti · F3 liga/desliga o modo rápido: player ×2 e broca ×5 (`DEBUG_SPEED`/`DEBUG_MINE`). F1 e F3 mostram "DEBUG · ..." no topo da tela |

### Mineração
| Tile | Tempo pra quebrar | Drop |
|---|---|---|
| Rocha comum | 0,6 s | nada |
| Ferro | 1,0 s | 1–2 ferro |
| Silício | 1,2 s | 1–2 silício |
| Gelo | 0,8 s | 1–2 gelo |

Inventário é só contador (`ferro: 12`), sem limite no MVP.

### Sobrevivência
- O₂ de 0 a 100. **Fora** da zona da base cai 1/s (~100 s de autonomia). **Dentro** da zona (raio 5 tiles da cápsula) recarrega 20/s.
- Abaixo de 25%: alarme, tela avermelha, seta apontando pra base.
- Em 0: desmaia (fade preto), acorda na cápsula com O₂ cheio. **Não perde nada.**

### Máquinas e índices
Ti = O₂ (ppq) + Calor (pK) + Água (ppm). Cada máquina colocada soma por segundo no índice dela.

| Máquina | Receita | Efeito | Libera em |
|---|---|---|---|
| Gerador de O₂ | 10 ferro, 4 silício | +3 ppq/s | Ti 0 |
| Derretedor de gelo | 6 ferro, 10 gelo | +2 ppm/s | Ti 0 |
| Aquecedor | 12 ferro, 8 silício | +4 pK/s | Ti 500 |
| Gerador de O₂ nv.2 | 30 ferro, 20 silício, 10 gelo | +25 ppq/s | Ti 10.000 |
| Derretedor nv.2 | 25 ferro, 30 gelo | +20 ppm/s | Ti 10.000 |
| Aquecedor nv.2 | 35 ferro, 25 silício | +30 pK/s | Ti 10.000 |

Meta: ~25 min de jogo até o fim do MVP. **Os números são chute e vão ser ajustados jogando.**

### Veios e drills automáticas
- **Veios**: depósitos de minério **no chão**, de **2×2 tiles**, de ferro, silício ou gelo, gerados com a seed do mapa.
  - Perto da base (até ~20 tiles) há 1 de cada tipo. Mais longe há mais veios.
  - Parte deles fica em bolsões escavados dentro da rocha, pra serem achados cavando.
  - Aparecem desde o estágio 1 e não somem nos estágios seguintes (a água não cobre veio).
  - **Não dá pra minerar veio na mão.**
  - Com o mouse em cima, a dica diz "Veio de <minério> · drill libera na Névoa" (ou "Coloque uma drill", depois de liberada).
- **Drill**: máquina craftada no fabricador, **liberada no estágio Névoa (Ti 10.000)**. Só pode ser colocada **exatamente em cima de um veio livre** (ocupa os 2×2).
  - Extrai o minério do veio **pra sempre**, ~1 unidade a cada 12 s, custo 12 ferro + 6 silício.
  - Guarda até **20** unidades num **inventário de 1 slot** (só o minério dela). Cheia, para.
  - **E** perto da drill abre o painel dela (estilo baú): inventário do player à esquerda e a drill à direita, com clique pra tirar (esquerdo a pilha, direito 1, Shift+clique tudo daquele item), botão **Pegar tudo** e a seção **DRONES** (ver §8, Marco 3). Não dá pra guardar nada na drill: ela só produz.
  - Atalho rápido: **Shift+E** perto da drill coleta tudo direto pro inventário, sem abrir o painel.
  - Com o mouse em cima, mostra o conteúdo ("12/20 ferro").
  - Pode ser desmontada com clique direito. Volta pro estoque, e o conteúdo vai pro inventário.
  - Não soma Ti.
  - Custo e ritmo finais quem define é o simulador de balanceamento (`tools/dev/balance_sim.py`).
- Logística: os drones da estação levam o minério das drills pros baús (§8, Marco 3).

### Estágios de terraformação
v0.4 Marco 1: são **4** estágios (`config.STAGES`, chaves `storm`, `arid`, `mist`, `green`). A Tempestade e o Árido usam a arte do Morto (`config.STAGE_ART`: sprites `*_dead_*` e `PALETTES["dead"]`).

| Estágio | Ti | O que muda |
|---|---|---|
| 1 · Tempestade | 0 | paleta vermelha + tempestade de poeira (visão curta, rajadas, O₂ mais rápido fora da base) · jogo novo começa aqui |
| 2 · Árido ("céu limpo") | 6.500 | a tempestade some em 20 s (`STORM_FADE_S`): a poeira afina e as rajadas param · mesma arte, sem água |
| 3 · Névoa | 10.000 | paleta fria, poças em tiles baixos, névoa, chuva fina, receitas nv.2 |
| 4 · Primeiro verde | 100.000 | grama, musgo, lagos, plantas · mensagem de fim do MVP |

- O Ti do Árido saiu do simulador: com o chute de 2.500 o casual chegava em ~5 min; com **6.500** chega em 8m15s–8m24s (meta: 8 a 12 min). O tempo total da partida não mudou (casual 38–44 min).
- `state.storm` (1,0 cheia, 0,0 sem) é a intensidade da tempestade. Começa em 1,0; passou do estágio Tempestade, desce linear até 0 em 20 s de jogo (também na caverna) e vai pro save. `storm_level(state)` dá 0 na caverna (a poeira não entra lá).
- Objetivo "Limpe o céu (Árido)" logo antes de "Chegue ao estágio Névoa".
- Ambiente: Tempestade toca `amb_storm` (se existir; senão `amb_dead`), Árido toca `amb_dead`.
- Save do v0.3 (v6 sem `progress.stage_scheme`): o número do estágio sobe 1 (Morto 1 → Árido 2, Névoa 2 → 3, Verde 3 → 4) e carrega com `storm = 0`. O formato continua v6 até o Marco 2.

A transição de estágio tem um aviso na tela ("ESTÁGIO 2 · CÉU LIMPO", "ESTÁGIO 3 · PRIMEIRAS CHUVAS").

### Fora do MVP, de propósito
Energia, comida, inimigos, combate, save/load, escuridão, superfície × subsolo, música.

## 5. Stack técnica

- Python 3.13 + **pygame-ce**, ambiente gerenciado com **uv** (`pyproject.toml` na raiz).
- Rodar: `uv run python -m game`
- 60 FPS, lógica com delta time.
- **Todo asset é opcional.** Se o PNG/WAV não existir, o jogo usa um retângulo colorido (cores da paleta acima) ou fica em silêncio. Nada pode quebrar por falta de asset.
- **Assets novos só entram no jogo depois que o dono do projeto aprovar** o report de design/som.

## 6. Contrato de assets

### Sprites: `assets/sprites/` (Designer)
PNG com transparência, **escala 1:1** (o jogo não redimensiona). Objetos são ancorados pelo **centro da base** no chão.

| Arquivo | Tamanho | Observação |
|---|---|---|
| `player_{down,up,side}.png` | 32×32 | parado, olhando pra baixo / cima / direita (o jogo espelha `side` pra esquerda) |
| `player_walk_{down,up,side}.png` | 128×32 | 4 quadros de 32×32 na horizontal |
| `player_idle_{down,up,side}.png` | 128×32 | parado: 4 quadros de 32×32 (respiração, cachecol, lanterna piscando), ~4 fps |
| `player_mine_{down,up,side}.png` | 128×32 | minerando: 4 quadros de 32×32 com a pose segurando a broca, 14 fps no mesmo índice de quadro da broca. Prioridade: minerando > andando > parado. Sem o PNG o jogo repete o `player_{view}` |
| `drill_side.png` | 96×16 | broca na mão, olhando pra direita (o jogo espelha). 4 quadros de 24×16 girando, só tocados enquanto minera |
| `drill_down.png` `drill_up.png` | 64×24 | 4 quadros de 16×24 · ponto de pega relativo ao quadro do player documentado no report |
| `floor_{stage}_{0..3}.png` | 32×32 | 4 variações · stage = `dead`, `mist`, `green` |
| `wall_{stage}_{0..2}.png` | 32×32 | topo da rocha, 3 variações |
| `wall_face_{stage}.png` | 32×24 | face frontal alta. Quando o tile abaixo é chão, o tile da parede mostra os 8 px de cima do `wall_{stage}_N` + essa face de 24 px |
| `water_{stage}.png` | 32×32 | |
| `water_auto_{mist,green}.png` | 64×96 | autotile da água no layout A2 (minitiles 16×16): (0,0)–(32,32) poça isolada, (32,0)–(64,32) cantos internos, (0,32)–(64,96) lago 2×2 com cantos externos, bordas e miolo. Fora da margem é transparente (o chão aparece). Sem ele, o jogo gera o atlas por código a partir do `water_{stage}` (`game/autotile.py`) |
| `ore_iron.png` `ore_silicon.png` `ore_ice.png` | 32×32 | overlay transparente por cima da parede |
| `icon_iron.png` `icon_silicon.png` `icon_ice.png` | 16×16 | ícones do inventário/HUD |
| `pod.png` | 64×72 | cápsula/base |
| `machine_o2.png` `machine_heater.png` `machine_melter.png` | até 40×56 | nível 1 |
| `machine_o2_t2.png` `machine_heater_t2.png` `machine_melter_t2.png` | até 40×64 | nível 2 |
| `terminal.png` | 32×32 | terminal de parede |
| `vein_iron.png` `vein_silicon.png` `vein_ice.png` | 64×64 | veio 2×2 no chão. Overlay transparente que funciona sobre o chão dos 3 estágios |
| `machine_drill.png` | 256×80 | drill automática: 4 quadros de 64×80 (broca girando), ocupa 2×2 tiles, ancorada no centro da base dos 2×2 |
| `icon_drill.png` | 16×16 | ícone (estoque de máquinas e fabricador) |
| `plant_bush.png` `plant_tree.png` `plant_flower.png` | até 32×40 | estágio verde |

### Sprites da superfície do v0.4 · regiões: `assets/sprites/regions/` (proposta da Designer, **aprovado pelo dono, v8.1**; pedra de topo do hoodoo v8.3)
Report: `reports/design/regioes/index.html`. Gerados por `tools/sprites/regions_mockups.py` (volumes em `regions_volume.py`, receita do chão em `regions_scene.py`).

**PNG indexado (modo P)**, com a paleta do Árido embutida. Índices: 0..7 = rampa da região, 8 = contorno `#1b1630`, 9 = sombra (preto, alfa 80), 255 = transparente. Os outros estágios trocam a paleta pela rampa do estágio em `regions/regions_palettes.json` (`ramps[tabela][região][estágio]`, tabelas `BASE`, `HILL`, `SAND`, `ICE` e `METAL`). O JSON também traz âncoras, tiles que bloqueiam, níveis d'água e a mistura de decalques.

| Arquivo | Tamanho | Observação |
|---|---|---|
| `ground_{plateau,salar,basalt,frost,bed}.png` | 512×512 | chão por região (`bed` = leito seco das depressões); emenda nos 4 lados; o tile (tx, ty) usa o recorte `((tx % 16)·32, (ty % 16)·32)`. Rampa `BASE` |
| `hill_top.png` / `hill_face.png` | 512×512 / 512×24 | topo e face dos morros mineráveis (rampa `HILL` da região). Silhueta por grade dual; a face é a silhueta extrudada 24 px pra baixo |
| `decal_*.png` | variados | decoração de chão (não colide, não minera). Rampa `BASE` da região onde cai |
| `decor_{shards,salt_crystals,ice_chunks}_{0..2}.png` | até 28×24 | soltos com altura, ordenados pelo pé, não colidem |
| `frost_ring.png` | 176×72 | geada no chão em volta do gelo-portão que sublima |
| `form_{monolith,arch,basalt_spires,salt_ridge,cone}.png` | até 208×150 | formações fixas (não mineram, marcos no mapa), ancoradas no centro da base e ordenadas pelo pé. Bloqueiam só os tiles do pé (lista no JSON): hoodoo 1, arco 2 (as pernas; o vão de 3 é andável), basalto colunar 3×2, crosta de sal 5×1, cone 3×2. hoodoo e arco usam a rampa `SAND` |
| `ice_gate_{0,1,2}.png` | 144×132 | gelo-portão em 3 etapas; bloqueia 4×2 → 3×2 → 2×1 → nada (aberto: sem sprite, fica o `frost_ring`) |
| `crater_impact_{0..4}.png` | 168×150 | **cratera de impacto, substitui `crater.png` e `crater_ramp.png` na superfície.** 0 = tampa de gelo cheia, 1..3 = o gelo baixando (marcas de geada nas paredes), 4 = vazia, com a rampa e o buraco expostos. Âncora (84, 70) = centro dos 3×3 (px `(cx·32 + 48, cy·32 + 48)`), desenhada pelo pé (borda de baixo dos 3×3). Continua bloqueando os mesmos 3×3; o E segue no tile do meio de baixo. Paleta: 0..9 planalto (`BASE`), 10..17 `ICE`, 18..20 `METAL` (degraus e postes da rampa) |
| `crater_ejecta.png` | 256×216 | manto de ejeção e pedrisco em volta da cratera, centrado no mesmo ponto; camada de decalques (não colide) |

A caverna continua com o `cave_ramp_up.png` e os sprites de hoje. Na superfície, `sand_*` e os `wall_*`/`wall_face_*` dos morros saem de uso quando o Marco 2 entrar.

### Áudio: `assets/audio/` (Som)
WAV, 44,1 kHz, 16-bit, mono. Loops precisam emendar sem estalo.

| Arquivo | Tipo | Quando toca |
|---|---|---|
| `mine_hit.wav` | sfx curto | a cada ~0,25 s enquanto minera |
| `mine_break.wav` | sfx | tile quebrou |
| `pickup.wav` | sfx | ganhou recurso |
| `craft.wav` | sfx | fabricou máquina |
| `place.wav` | sfx | colocou máquina |
| `ui_open.wav` `ui_close.wav` `ui_click.wav` | sfx | menus |
| `o2_low.wav` | loop | O₂ abaixo de 25% |
| `o2_refill.wav` | sfx | entrou na zona da base |
| `faint.wav` | sfx | desmaiou |
| `terminal_open.wav` | sfx | abriu terminal |
| `stage_up.wav` | sfx/jingle | mudou de estágio |
| `footstep_0.wav` `footstep_1.wav` | sfx | passos alternados |
| `machine_hum.wav` | loop | perto de máquinas |
| `drill_loop.wav` | loop | perto de uma drill trabalhando (volume pela distância). Some quando ela enche |
| `drill_collect.wav` | sfx | coletou o conteúdo de uma drill |
| `drill_full.wav` | sfx | discreto, quando o jogador chega perto de uma drill cheia |
| `amb_dead.wav` `amb_mist.wav` `amb_green.wav` | loop 20–40 s | ambiente de cada estágio (`amb_dead` no Árido, e na Tempestade quando não tem `amb_storm`) |

## 7. Organização da equipe

| Pasta | Dono |
|---|---|
| `docs/` | Gerente (orquestrador) |
| `game/`, `pyproject.toml`, `tests/` | Dev |
| `assets/sprites/`, `tools/sprites/`, `reports/design/` | Designer |
| `assets/audio/`, `tools/audio/`, `reports/audio/` | Som |
| `reports/mockups/` | referência, ninguém edita |

Ninguém mexe na pasta do outro. Dúvida ou conflito vai pro gerente.

## 8. Escopo do v0.2: "a base ganha vida"

Tema: **automação**. O jogador monta um sistema que trabalha por ele, e o resto do v0.2 existe pra sustentar isso.
Decisões do dono: inventário com slots (a mochila de upgrade fica pra depois), automação com **drones** (sem esteiras), **energia global sem fios**, e água e comida ficam no v0.3.
Os números abaixo são o ponto de partida; o balanceamento final sai do `tools/dev/balance_sim.py`.

### Marco 1 · Fundação
**Save/load**
- Um slot em `saves/slot1.json` (no `.gitignore`) *(v0.4: virou 3 mundos, ver "Mundos com nome e seed" na §11)*, em JSON **versionado** (`"version": N`), com migração simples quando o formato mudar.
- **Salva só o que muda**: o mundo é gerado pela seed, então o save guarda os tiles minerados e não o mapa inteiro. Também guarda: player (posição, direção, O₂), inventário e baús, máquinas e drills (com o conteúdo), índices e Ti, objetivos, terminais lidos, fontes da transição, energia e tempo de jogo.
- **Autosave** a cada 2 min e ao sair. No menu de pausa entra "Salvar e sair".
- **Tela de título** mínima: nome do jogo, "Continuar" (só se existir save), "Novo jogo" (pede confirmação se já existir save) e "Sair". *(v0.4: Continuar · Mundos · Sair, ver §11)*
- Cada sistema novo do v0.2 tem que entrar no save, com teste de ida e volta (salvar → carregar → estado igual).

**Inventário com slots**
- O player tem **16 slots**. Recursos empilham até **50** por slot; máquinas fabricadas viram **itens** e empilham até **5**.
- **Hotbar** de 8 slots no rodapé central. Teclas **1–8** ou a rodinha do mouse selecionam (com Ctrl segurado a rodinha mexe no zoom). Se o item selecionado for máquina, o jogo entra no modo de colocar (o drone é item, mas não se coloca no chão: vai na estação). Isso substitui o estoque de máquinas atual (teclas 1–7).
- **Tela de inventário (Tab)**: grade dos 16 slots e a hotbar. Clique pega e solta a pilha, e clique direito pega metade.
- **Inventário cheio**: o minério minerado **não é coletado**, e aparece o aviso "Inventário cheio" (o tile quebra mesmo assim).
- O **fabricador** usa o que está no inventário **e nos baús dentro da zona da base**. *(v0.3)* A aba **Fabricar** do Tab (fabricar em campo, §9) gasta **só do inventário**.
- Futuro (fora do v0.2): **mochila** que aumenta os slots.

**Baú**
- Craftável desde o início, custa **6 ferro**. Tem **24 slots** e ocupa 1 tile. **E** abre e mostra o baú ao lado do inventário.
- Desmontar o baú só funciona se ele estiver vazio (aparece um aviso se não estiver).
- **Nome**: cada baú tem um nome (padrão "Baú"). No painel do baú, clicar no nome (título) abre a edição: até **16 caracteres**, **Enter** confirma, **Esc** cancela, **Backspace** apaga, e clicar fora do campo também confirma. Nome vazio volta pra "Baú". Enquanto edita, nenhuma tecla do jogo (E, Tab, números, WASD, +/-) faz nada além de digitar.
- No mundo, o nome aparece flutuando em cima do baú só quando o mouse está em cima dele (decisão do dono: perto não mostra, pra não poluir a base). O tamanho da letra não muda com o zoom.

**Transferência entre painéis (estilo Planet Crafter)** · vale no baú, na drill (só tirar) e na estação de drones
- Com os dois painéis abertos (inventário + baú/estação): **clique esquerdo** num item manda a **pilha inteira** pro outro lado, **clique direito** manda **1 unidade**, e **Shift+clique** manda **todas as pilhas daquele item**. O que não couber fica onde está (com o aviso "Baú cheio" / "Inventário cheio").
- No **Tab** (inventário sozinho) nada muda: clique pega/solta a pilha e o direito pega metade, pra organizar a mochila e a hotbar.
- Botões no painel do baú: **Pegar tudo** (tudo do baú pro inventário, até onde couber) e **Guardar tudo** (manda **só os recursos**, ferro, silício e gelo, de todos os slots do inventário, inclusive a hotbar; máquinas e drones ficam com o player, porque são coisas que ele vai colocar).
- Passar o mouse num slot mostra o nome do item e a quantidade.

### Marco 2 · Energia (global, sem fios)
- A energia é um **pool global**: a produção total (kW) contra o consumo total. O HUD mostra um medidor "⚡ produção / consumo".
- **Cápsula**: gera **5 kW** fixos, pro começo do jogo funcionar.
- **Painel solar**: +4 kW, custa 8 ferro + 6 silício, libera com Ti 0. Ocupa 1 tile.
- **Consumo**: Gerador de O₂ 1 · Derretedor 1 · Aquecedor 2 · máquinas nv.2 3/3/4 · Drill 2 · Estação de drones 1 (kW). O baú não consome.
- **Déficit**: todos os consumidores rodam no ritmo `produção / consumo` (desaceleração proporcional), e o medidor fica vermelho. Não há corte total.
- No v0.2 não tem bateria nem ciclo dia/noite (ficam pra depois).

### Marco 3 · Automação com drones (logística estilo The Planet Crafter)
- **Estação de drones**: libera na Névoa (Ti 10.000), custa **12 ferro + 8 silício + 3 gelo** e ocupa 2×2. **Vem vazia**: tem **4 slots de drone** e consome **1 kW**. A estação é só a **casa** dos drones (onde pousam e de onde saem): eles atendem o **mapa inteiro**, sem alcance.
- **Drone** é um **item**: receita no fabricador, libera junto com a estação (Névoa), custa **6 ferro + 4 silício** e empilha até 5 no inventário (igual às máquinas). Não se coloca no chão: vai num slot da estação.
- **E na estação** abre um painel no estilo do baú: inventário à esquerda e a estação à direita, com os **4 slots de drone** (só aceitam o item drone, 1 por slot) e o estado ("ALCANCE: MAPA TODO" e "2 drones · 1 em voo · 1 kW").
  - Cada drone num slot é **1 drone ativo**. Colocar um drone (clique no drone do inventário) faz ele começar a operar; clique esquerdo manda quantos couberem, o direito manda 1.
  - **Drone em voo**: o slot dele fica **travado** (marcado "EM VOO") e não pode ser tirado até ele pousar. **Drone pousado** pode ser tirado: volta pro inventário como item (se estiver segurando carga, a carga vai junto; não cabendo tudo, ele fica).
  - **Buffer antigo**: a estação não recebe mais nada no buffer. O que um save antigo tinha lá aparece como "SOBRAS" e continua tirável (clique ou **Pegar tudo**) até esvaziar; vazio, o espaço mostra uma dica de como configurar os baús.
- **Desmontar a estação** devolve a estação, **todos os drones** (os em voo cancelam a viagem) e todo o minério (sobras + carga de cada drone) pro inventário. Ou cabe tudo, ou ela fica no lugar com o aviso de inventário cheio: nada some.

**Inventários logísticos (baú e drill)**: cada um tem uma configuração de drones, no painel dele (seção **DRONES**):
- **ENVIA** (oferta): os itens que os drones podem **tirar** daqui. Toggle por item: ferro, silício, gelo (no código é um conjunto de ids, pra crescer depois).
- **RECEBE** (demanda): os itens que os drones **trazem** pra cá.
- Um item **não pode** estar em Envia e Recebe no mesmo inventário: marcar um lado desmarca o outro.
- **LOTE**: quanto um drone tira **deste** inventário por viagem: **1 / 5 / 10 / 20** (padrão 10). Vale pro inventário que envia.
- **Padrões**: baú novo e **drill nova** vêm com Envia = nada e Recebe = nada (igual ao Planet Crafter). O jogador vai lá e configura. Enquanto nada estiver marcado, a seção mostra a dica "NADA CONFIGURADO".
- **Drill**: só tem **ENVIA** (com o minério dela) e **LOTE**. Não tem Recebe (no lugar aparece "NÃO RECEBE"): ela tem 1 slot só do minério dela, e receber outra coisa travaria a extração.
- No mundo, o rótulo flutuante do baú mostra o que ele recebe e envia junto do nome: **↓[ícones] ↑[ícones] Nome** (sem configuração, só o nome). Os textos que sobem ("+10 SILÍCIO", "+O2") não passam por trás do rótulo: quem ia cruzar ele fica logo acima (e acima dos outros que já desviaram, sem encavalar).
- A configuração vale só pros drones: o jogador guarda e tira qualquer coisa à mão.

**Tarefa do drone** (um drone livre, pousado na estação):
1. Procura um **par**: uma **origem** que Envia o item X com estoque livre > 0 e um **destino** (outro inventário) que Recebe X com espaço livre. "Livre" já desconta o que outros drones reservaram (estoque que vão buscar e espaço que vão ocupar), então dois drones nunca brigam pelas mesmas unidades.
2. **Quando a origem está pronta**: baú, com qualquer estoque; drill, quando tiver pelo menos o lote (ou estiver cheia). Assim o drone não fica indo buscar 1 unidade de cada vez (a não ser que o lote seja 1).
3. **Escolha**: a origem **mais cheia** (mais estoque livre) primeiro; empate: a viagem mais curta. Pra cada origem, o destino é o que deixa a viagem mais curta (origem → destino → estação).
4. Leva **min(lote da origem, estoque, espaço no destino)**, **um item por viagem**.
5. Ciclo: decola → voa em **linha reta por cima das paredes** até a origem → pega (0,8 s) → voa até o destino → solta (0,6 s) → volta pra estação e pousa.
6. **Destino encheu no meio do caminho** (ou foi desmontado): entrega o que couber e procura outro destino que Recebe X. Se não houver, volta pra estação **com a carga** e fica pousado segurando ela (aparece a pepita); quando surgir um destino, sai pra entregar. Nada some.
7. Origem desmontada ou esvaziada pelo jogador antes do drone chegar: ele volta vazio.
- **Velocidade**: **6 tiles/s** (era 4). Com o mapa todo, a viagem típica (drill a 40 tiles da base, entregando num baú da base) é ~80 tiles: 20 s a 4 tiles/s, ~13 s a 6. Até a borda do mapa (~60 tiles da base) a ida dura ~10 s em vez de 15. Uma drill enche um lote de 10 em 120 s, então 1 drone dá conta de várias drills.
- Sem energia suficiente, os drones voam mais devagar, na mesma proporção do déficit.
- **Visual**: drone pequeno voando com sombra no chão. A estação mostra os drones pousados (slots 1 e 2 nos pads; 3 e 4 estacionados na frente deles).
- **Drones na mesma rota não se empilham** (só no desenho; posição lógica e chegada não mudam): voando, cada drone vai no lugar dele numa formação em losango pelo slot (1 e 2 lado a lado, 3 atrás, 4 na frente), com altura e balanço um pouco diferentes; pegando/soltando, cada slot fica num ponto próprio em volta do alvo. A troca entre um e outro é suave, e na decolagem/pouso a formação entra/sai junto com a subida (ele sai e chega no pad certinho).
- Futuro: upgrade de estação (mais slots), mais itens nos toggles (máquinas, drones).
- Save **v4**: baús ganham `name`; a estação guarda os 4 slots de drone. Migração v3→v4: baús viram "Baú" e cada estação existente ganha **2 drones** nos slots 1 e 2.
- Save **v5**: baús e drills ganham `sends`, `receives` e `batch`; a drill guarda o inventário (`storage`) no lugar do contador. Migração v4→v5 (ninguém perde a base que já funcionava): baú com filtro "Tudo" → Recebe {ferro, silício, gelo}; filtro X → Recebe {X}; Envia nada. **Drills existentes** ganham o inventário com o estoque atual e **Envia = o minério delas** (drill nova continua vindo sem nada). Drone com carga continua com ela e entrega assim que achar um destino. O buffer da estação vira as "sobras" tiráveis.

### Marco 4 · Polimento
- **Fabricador com abas**: **Terraformação** (O₂, derretedor, aquecedor e os nv.2), **Energia** (painel solar), **Automação** (drill, estação, drone) e **Armazenamento** (baú). As categorias ficam em `C.MACHINE_CATEGORY`. **A/D**, **←/→** ou **Tab** trocam de aba (E fecha o menu), **W/S** escolhe dentro da aba, clique na aba ou na receita também. A lista mostra 5 receitas e rola (rodinha do mouse ou acompanhando a seleção), com barra de rolagem quando não cabe. *(Redesign B2: 6 receitas, ver o fim da §9.)* Aba sem nada liberado aparece apagada, mas abre e mostra as bloqueadas. *(v0.3)* Parte das receitas também sai **em campo**, pela aba Fabricar do Tab (kit de campo, ver §9).
- **Fabricar em lote**: **Shift+Enter** (ou Shift+clique em CRAFTAR) fabrica até **5** de uma vez e para quando falta recurso ou espaço; aparece "Nome x5".
- **Textos que sobem** não encavalam: o mesmo recurso no mesmo ponto em menos de 0,6 s soma ("+15 FERRO" + "+15 FERRO" = "+30 FERRO"); outros textos nascidos perto sobem uma linha cada.
- **Drone decola e pousa suave**: nos primeiros/últimos ~0,35 s de voo a sombra sai de debaixo dele (maior e mais escura) e vai se afastando e encolhendo.
- **Barrinha nas drills**: barra fina em cima de cada drill (quanto ela guardou de 20), na cor do minério; cheia fica verde.
- **Sem energia**: no déficit, toda máquina que consome mostra um raio vermelho piscando em cima.
- **Alcance da estação**: ~~círculo de 30 tiles e área de entrega lilás~~ saiu no Marco 3 da logística (os drones atendem o mapa inteiro). Colocando a estação, a dica diz "drones atendem o mapa todo".
- **Volume padrão** (quem nunca mexeu): geral 100%, efeitos 40%, ambiente 50%.
- Rodar o simulador de novo com inventário, energia e drones, e ajustar até bater a meta de tempo.
- Playtest do dono. Os assets novos só entram depois de aprovados.

### Assets novos do v0.2 (contrato)
| Sprite | Tamanho | Observação |
|---|---|---|
| `chest.png` | 32×40 | baú, ancorado no centro da base |
| `chest_open.png` | 32×40 | baú aberto |
| `solar_panel.png` | 32×40 | painel solar |
| `drone_station.png` | 64×72 | estação 2×2, com espaço pros drones pousados (documentar os pontos de pouso) |
| `drone.png` | 64×16 | 4 quadros de 16×16 com as hélices girando. O jogo desenha a sombra |
| `icon_chest.png` `icon_solar.png` `icon_drone_station.png` | 16×16 | ícones de item |
| `icon_drone.png` | 16×16 | ícone do item drone. Até ser aprovado, o jogo usa o 1º quadro do `drone.png` |
| `ui_slot.png` | 20×20 | moldura de slot do inventário/hotbar (opcional; se faltar, o jogo desenha) |

| Áudio | Tipo | Quando toca |
|---|---|---|
| `chest_open.wav` `chest_close.wav` | sfx | abrir e fechar o baú |
| `inv_move.wav` | sfx curto | mover uma pilha no inventário |
| `inv_full.wav` | sfx discreto | tentou coletar com o inventário cheio |
| `power_low.wav` | sfx | o déficit de energia começou (uma vez) |
| `solar_hum.wav` | loop baixíssimo | perto de painéis |
| `drone_loop.wav` | loop | drone voando (volume pela distância) |
| `drone_deliver.wav` | sfx | o drone entregou carga |
| `save.wav` | sfx discreto | salvou o jogo (autosave e manual) |

**Regra de aprovação:** os assets novos são entregues em `assets/sprites/_pending/` e `assets/audio/_pending/`. O gerente só move pra pasta oficial depois que o dono aprovar o report. Até lá, o jogo usa o fallback.

## 9. Escopo do v0.3: "superfície"

Design completo e aprovado: `docs/superpowers/specs/2026-10-12-v03-superficie-design.md`. Resumo das decisões:

- **Duas camadas**, em mapas separados:
  - **Superfície**: deserto aberto de 192×192, com a cápsula no centro, rochas pequenas de minério que reaparecem, morros, cordilheira na borda, **3 a 5 veios só** e destroços.
  - **Caverna**: 128×128, escura, com minério abundante e veios comuns. Gerada pelo `world.py` de hoje.
  - Troca de camada por uma **rampa na cratera**, com E e fade.
- **A base fica na superfície.** A terraformação aparece no deserto; a caverna não muda com o Ti.
- **O₂**: só na zona da base. Fora dela, 100 s; com o **tanque de O₂** (equipamento, num slot novo), ~220 s.
- **Luz na caverna**:
  - lanterna do capacete (~4 tiles);
  - **luminária**: 1 Fe + 1 Si, ~5 tiles, sem energia;
  - luz fraca das máquinas;
  - pontinho de brilho nos minérios.
- **Destroços** (6 a 8): nave de carga, módulo da colônia e sonda. Têm caixa de saque (só tirar, conteúdo fixo), terminal com LOG e **projetos**.
- **Projetos** liberam receitas na hora em que tu pega: tanque de O₂, **scanner de navegação** (minimapa com névoa de guerra, M abre o mapa), luminária melhor e, se der tempo, drill nv.2.
- **Drones só atendem a superfície** no v0.3. O **elevador de carga** na cratera entra no v0.4.
- **Energia continua global** (vale pras duas camadas).
- **Fabricar em campo (kit de campo)**: aba Fabricar do Tab, em qualquer lugar, só com o inventário: drill, luminárias e baú. O resto continua só no fabricador da base (ver o fim desta seção).
- **Save v6**: exige novo jogo, sem migração do v5.
- **Marcos**: 1 Superfície · 2 Caverna · 3 Destroços/projetos/tanque/scanner · 4 Polimento.
- **Fora do v0.3**:
  - v0.4: biomas de caverna, mochila, drill melhor, peças raras e elevador de carga;
  - depois: água e comida.

### Marco 1 · como ficou na implementação (números de partida, ajustáveis em `game/config.py`)
- **Base no centro** do deserto: cápsula nos tiles (95, 95)–(96, 95), zona de O₂ de 5 tiles. Areia limpa num raio de **8 tiles**.
- **Borda**: 2 ou 3 tiles de rocha indestrutível (o noise decide), desenhada com a parede escurecida.
- **Morros**: 24 a 32 por mapa, de 3 a 8 tiles, com 2 tiles de folga entre eles; 12% dos tiles de morro têm minério. Morro minerado vira areia. *(Marco 4)* Forma orgânica: elipse principal + 1 ou 2 lóbulos com borda tremida, suavizada por autômato celular, sem ponta de 1 tile, sem dente de 1 tile e sem tile encostando só pela quina; os morros têm gerador aleatório próprio (mexer na forma deles não move cratera, veios e destroços).
- **Cratera**: 3×3, centro a 15–20 tiles da base, com areia limpa em volta. É obstáculo plano (bloqueia, não minera); a dica diz "Cratera · fechada por enquanto". O canto fica em `world.crater` pra virar a rampa no Marco 2 (alvo do E no tile do meio de baixo).
- **Veios**: 3 a 5, um de cada minério garantido, todos a ≥ 35 tiles da base e ≥ 14 entre si, em areia aberta.
- **Rochas pequenas**: ~1,3% da areia (~430 no mapa), fora da área da base; 0,7 s pra quebrar, dão 2 a 4 (45% ferro, 30% silício, 25% gelo). Um cristalzinho na cor do minério em cima da pedra diz o que ela dá. Contam como "minerado" nos objetivos.
- **Rochas reaparecem** (`game/rock_respawn.py`): 1 a cada 15 s (4/min), até o teto de **520** rochas no mapa. Só fora da meia-tela do zoom 0,75, a ≥ 12 tiles da base e em areia livre: fora de veio, de lago futuro, da cratera/rampa (com folga), de destroço (com a folga dele) e de máquina (com 1 tile de folga), e com os 8 vizinhos sem nada sólido (rocha nova nunca fecha passagem). Mesmos pesos da geração. Continua reaparecendo com o player na caverna. A rocha nova entra no save como tile mudado; o relógio vai em `layers.surface.rocks`.
- **Recursos soltos saíram** (o dono achou as rochas melhores). Os ~70 soltos viraram +~70 rochas no começo (357 -> ~430). Save v6 com o campo antigo `pickups` carrega e ignora o campo (sem subir a versão).
- **Objetivo "Leia um terminal"**: só aparece quando existe uma camada com terminal (no Marco 1 os terminais estão na caverna, que ainda não abre).
- **Vento do deserto** (`desert_wind.wav`): volume 0,45 por cima do ambiente, canal próprio, sobe em 2,5 s e desce em 1,5 s; some na caverna e no desmaio.
- **Save v6** por camada. Save v1–v5: a tela de título mostra "Save de uma versão antiga · comece um novo jogo" com Continuar apagado; ao começar um jogo novo, o arquivo antigo é guardado como `saves/slot1.v5.json` (não é apagado).
- **Água**: poça em chão baixo (noise), sem colisão, a partir da Névoa. Desenhada com autotile A2 (cantos redondos, margem, brilho). A geração é suavizada: água ligada só pela quina some; gota de 1 tile só fica se nem nas diagonais tem água (olhando o estágio Verde, então a água da Névoa está sempre dentro da do Verde).
- **Transição de estágio**: a frente da mancha vai até ~152 tiles (o canto do deserto fica a ~136 da base).
- **Duração** (simulador, só superfície): 28–42 min nos números atuais, contra 23–30 min no v0.2. Quase todo o tempo a mais é andando; a caverna (Marco 2) é que traz minério em volume. *(Rochas reaparecendo no lugar dos soltos, média de 5 seeds na proposta: guloso 39,4 -> 38,2 min, variado 39,7 -> 36,4, casual 52,2 -> 48,3; caverna e destroços só mudam no ruído.)*

### Assets do Marco 1 · Superfície (contrato)
Entregues em `_pending/` até o dono aprovar. Os morros usam a arte de parede que já existe (`wall_*`, `wall_face_*`), e a cordilheira da borda também (o jogo escurece ela).

| Sprite | Tamanho | Observação |
|---|---|---|
| `sand_{stage}_{0..3}.png` | 32×32 | chão da superfície, 4 variações. `dead` = areia avermelhada (o planeta morto); `mist` = terra marrom úmida; `green` = grama de verdade (a terraformação transforma o deserto) |
| `rock_small.png` | 32×32 | rocha pequena no chão (1 tile, quebrável), contorno `#1b1630`, funciona nos 3 chãos |
| ~~`pickup_iron.png` `pickup_silicon.png` `pickup_ice.png`~~ | 16×16 | recurso solto no chão. **Fora do jogo** (os soltos saíram); os arquivos ficaram nos assets |
| `crater.png` | 96×96 | cratera 3×3 fechada (Marco 1), escura no centro, borda de rocha |
| `crater_ramp.png` | 96×96 | a mesma cratera com a rampa de descida aberta (usada no Marco 2) |

| Áudio | Tipo | Quando toca |
|---|---|---|
| `desert_wind.wav` | loop 20–40 s, baixíssimo | camada de vento seco por cima do `amb_{stage}` na superfície. Some na caverna |

Rochas usam `mine_hit`/`mine_break` e, ao dar o minério, o `pickup.wav` já aprovado.

### Assets do Marco 2 · Caverna (contrato)
**Sprites aprovados (Designer v5.0) e promovidos pra `assets/sprites/`.** A caverna usa a arte de chão e parede do estágio **névoa** já aprovada (`floor_mist_*`, `wall_mist_*`, `wall_face_mist`), sempre, sem mudar com o Ti (rocha fria). Sem água na caverna.

| Sprite | Tamanho | Observação |
|---|---|---|
| `lamp.png` | 16×32 | luminária de chão (poste baixo com luz quente no topo), ancorada no centro da base. O jogo desenha a luz por cima |
| `icon_lamp.png` | 16×16 | ícone de item da luminária |
| `cave_ramp_up.png` | 96×96 | rampa de subida na caverna, 3×3 como a cratera: buraco de luz vindo de cima, degraus de metal subindo, mesma linguagem da `crater_ramp` |

| Áudio | Tipo | Quando toca |
|---|---|---|
| `amb_cave.wav` | loop 20–40 s | ambiente da caverna: grave, gotejar esparso, eco. Substitui o `amb_{stage}` e o vento enquanto na caverna |
| `ramp_down.wav` `ramp_up.wav` | sfx ~1 s | descer e subir pela rampa (passos metálicos + mudança de espaço) |
| `lamp_place.wav` | sfx curto | colocou uma luminária (clique + acender) |

### Marco 2 · como ficou na implementação (números de partida, ajustáveis em `game/config.py`)
- **Rampa** (as duas camadas usam a mesma regra): um 3×3 de tiles `CRATER` em `world.crater` (sólido baixo, não minera). Na superfície é a cratera (agora com o `crater_ramp`); na caverna é a **rampa de subida**, no meio do salão (canto em (63, 61), `CAVE_RAMP`). O E mira o tile do meio de baixo (tx+1, ty+2) e o player chega/sai em (tx+1, ty+3).
- **E na rampa** segue a regra do jogo: o que está debaixo do mouse, se no alcance; senão o mais perto no alcance. Alcance de **64 px** dos pés até o meio da borda de baixo da rampa (quem acabou de chegar já está no alcance). Dicas: "[E] Descer pela rampa" / "[E] Subir pela rampa"; longe: "Cratera · chegue mais perto pra descer" / "Rampa · chegue mais perto pra subir".
- **Fade**: 1,3 s no total; troca de camada no preto aos 0,6 s; texto "Descendo..." / "Subindo...". Durante o fade o player fica parado e o O₂ continua. Desmaio cancela a viagem (acorda na cápsula).
- **Caverna**: 128×128, gerador do `world.py`. Minério: um tile vira minério se o noise passar de **0,64 − 0,11 × longe**: **~39% das paredes** (seeds 7/1/42: 40,0/40,9/36,9%), ~29% perto do salão e ~41% a 40–60 tiles. *(Pós-playtest: no Marco 2 era 0,62 − 0,15, ~48% das paredes, e o dono achou demais; no Marco 1, 0,66 − 0,11, ~35%.)* Perto da rampa continua sobrando pro começo: a até 20 tiles dela tem ≥ 49 tiles de cada minério nas 3 seeds (eram ≥ 55), fora o veio de cada perto. Simulador: caverna 32–33 min e destroços 30–32 min nos números atuais (antes 32–39 e 30–32, dentro do ruído); na proposta, caverna 41–44 min e destroços 36–40 (antes 37–40 e 35–36). 18 veios (1 de cada perto, 5 de cada longe), 3 terminais (19, 31 e 45 tiles da rampa). Visual fixo do estágio névoa, `terraforms = False` (sem água, sem plantas, sem clima).
- **O₂ na caverna**: sem zona; 100 s; a seta do O₂ crítico aponta pra rampa ("Suba pela rampa · N m", rótulo RAMPA).
- **Escuridão** (`game/lighting.py`, `Lighting(cell=4, banding=True)`, ambiente 0 = breu): lanterna do capacete (4 tiles, viés de 10 px pra onde o player olha); **luz do dia na boca da rampa** de subida ((tx·32+48, ty·32+30), 3,5 tiles, `#fff0d6`); luminária (5 tiles, quente, tremidinha leve); luz fraca de cada máquina (1,8 tile, na cor dela; baú não tem, drill cheia apaga); terminais com verde fraco (2 tiles); brilho nos minérios (~40% dos tiles, por cima do escuro). Rachaduras da mineração e fantasma de colocar ficam por cima do escuro; HUD e textos flutuantes também.
- **Luminária** (`lamp`): 1 Fe + 1 Si, Ti 0, sem energia, sem Ti, 1 tile (só o pé bloqueia, 12×12 px), colocável nas duas camadas. Fica na aba nova **"Luz"** do fabricador (junto vai a "luminária melhor" do Marco 3). Na superfície ela também ganha um brilho quente no sistema de luz de lá. *(Dono: revisar a aba.)*
- **Duas camadas**: drill na caverna funciona e o jogador busca à mão; **estação de drones não pode ser colocada na caverna** (dica "Drones só funcionam na superfície"); fabricador puxa só dos baús da base; energia e Ti globais.
- **Áudio** (dica do Som): `amb_cave` (0,7, nos mesmos canais A/B do ambiente) substitui o `amb_{estágio}` e o vento; descendo, o ambiente e o vento saem em 1,5 s e o `amb_cave` entra em 2,5 s, meio segundo depois (subindo, o inverso; o vento volta em 2,5 s). Mudar de estágio lá embaixo não troca o ambiente: o novo entra ao subir. `ramp_down`/`ramp_up` 0,8; `lamp_place` 0,8 no lugar do `place`. Sem o arquivo: silêncio (sem `amb_cave`, fica o ambiente do estágio, sem vento).
- **Objetivos**: depois de "Fabrique um baú" entram "Desça na caverna pela cratera [E]" e "Coloque uma luminária" (contador `lamps_placed`, só cresce). "Leia um terminal" não pula mais. *(Dono: revisar a posição.)*
- **Save v6** (sem subir versão): a camada atual e a caverna (se já foi gerada) já iam no save; entrou `progress.lamps_placed` (save do Marco 1 sem o campo carrega com 0). Salvou no meio do fade, antes da troca: o save já grava o destino (camada + ponto de chegada da rampa), como se a viagem tivesse acabado *(Marco 4; antes carregava antes da troca)*.
- **Desempenho** (smoke, headless): caverna escura com 36 luminárias no zoom 0,75 ≈ 5,3 ms por frame.
- **Duração** (simulador, estratégia nova "caverna" = o casual que só minera na caverna, drills nos veios de lá, sem drones): **31–37 min** nos números atuais (casual da superfície: 34–42), 37–38 min na proposta. A viagem custa ~20 "tiles" de cada lado (cratera + fade). Nenhum ajuste de número foi preciso.

### Assets do Marco 3 · Destroços (contrato)
**Sprites aprovados (Designer v5.0) e promovidos pra `assets/sprites/`.**

| Sprite | Tamanho | Observação |
|---|---|---|
| `wreck_cargo.png` | 128×112 | nave de carga caída, ocupa 4×3 tiles, meio enterrada na areia, ancorada no centro da base |
| `wreck_module.png` | 96×88 | módulo da colônia, 3×2 tiles, com um terminal visível |
| `wreck_probe.png` | 64×64 | sonda pequena, 2×2 tiles |
| `loot_crate.png` `loot_crate_empty.png` | 32×32 | caixa de saque (fechada/cheia e aberta/vazia) |
| `icon_blueprint.png` | 16×16 | item de projeto |
| `icon_o2_tank.png` | 16×16 | tanque de O₂ (equipamento) |
| `icon_scanner.png` | 16×16 | scanner de navegação |

| Áudio | Tipo | Quando toca |
|---|---|---|
| `crate_open.wav` | sfx | abriu uma caixa de saque |
| `blueprint_found.wav` | sfx/jingle curto | achou um projeto (som de conquista) |
| `equip.wav` | sfx curto | colocou equipamento no slot |
| `map_open.wav` | sfx curto | abriu o mapa (M) |

**Luminária forte (Designer v5.1, variante A).** Aprovada pelo dono e promovida pra `assets/sprites/`. O desenho de fallback do `art.py` (cúpula branca-fria) só entra se o PNG faltar.

| Sprite | Tamanho | Observação |
|---|---|---|
| `lamp_t2.png` | 16×32 | luminária forte, irmã nv.2 da `lamp`: mesma âncora (centro da base, base na linha 29), drop-in no `LAMP_SPRITE_SIZE`. Cabeça de gaiola maior com aba e aro dourados, vidro branco-quente (centro em (8, 7) do PNG), poste mais grosso, sapata em 2 degraus. O jogo desenha a luz por cima |
| `icon_lamp_t2.png` | 16×16 | ícone de item da luminária forte |

### Marco 3 · como ficou na implementação (números de partida, ajustáveis em `game/config.py`)
- **Destroços** (`game/wrecks.py`): 6 a 8 por seed, centros de `WRECK_DIST` = 30 a 84 tiles da base, distâncias sempre crescentes, ≥ 14 tiles entre eles, com 2 tiles de areia livre em volta (sem morro, veio, cratera, borda, zona da base e sem rocha pequena). A área vira tile `WRECK` (sólido baixo, não minera; o sprite é um objeto ordenado pelo pé) e a caixa vira `LOOT_CRATE`. Âncoras e caixas como no contrato da Designer (v5.0). Sprites aprovados pelo dono (Designer v5.0) e promovidos pra `assets/sprites/`; o desenho do `art.py` só entra se o PNG faltar.
- **Ordem por distância** *(dono: revisar)*: nave de carga (projeto do **tanque de O₂** + registro da VÉSPER-7, dia 188 = LOG 05), sonda, módulo da colônia (projeto do **scanner** + dia 140 = LOG 04), nave (projeto da **luminária forte**), sonda (S-3, dia 41 = LOG 02), [nave e sonda extras com 7 ou 8], módulo (dia 230 = LOG 07, o mais longe). Números exibidos pela cronologia (§2).
- **Caixa de saque**: 8 slots, E abre (alcance 48 px), só tirar (esquerdo pilha, direito 1, **Pegar tudo**). Saque pela seed e fixo: nave 14–20 ferro, 8–12 silício, 6–10 gelo; módulo 8–12 / 4–7 / 3–5; sonda 2–4 / 1–3 / 0–2. Vazia troca o sprite e a dica vira "Caixa vazia". Som `crate_open` 0,9 (vazia: ~0,6); fechar: `chest_close`.
- **Projetos** *(dono: revisar)*: o projeto sai **sozinho ao abrir a caixa** (não ocupa espaço), libera a receita na hora e mostra por 3,5 s, no vão do topo entre o O₂ e o Ti, o aviso com o ícone do projeto (`icon_blueprint`) e 2 linhas: "PROJETO · RECEITA LIBERADA" / "<Nome>" (formato curto pra caber com o ícone nos 3 tamanhos de interface); `blueprint_found` 0,4 s depois do `crate_open`, ambiente a 60% por 2 s. Receita sem projeto aparece no fabricador como **"??? · projeto não encontrado"** (prévia apagada, botão "SEM PROJETO").
- **LOGs dos destroços** (índices 3–6 em `LOGS`): **aprovados pelo dono** (`docs/lore/logs_v03_rascunho.md`), num bloco só no `config.py` (`LOGS` + `LOG_TITLES` + `LOG_DAYS`). O módulo tem terminal (E no tile do terminal, lido do tile de baixo); a **nave e a sonda** (sem terminal no sprite) mostram o registro de bordo na tela de terminal na 1ª vez que a caixa abre, e o painel da caixa ganha **Ler registro**. *(Dono: revisar.)*
- **Equipamento** (`game/equipment.py`) *(dono: revisar)*: aba nova do fabricador **"Traje"**; slots tipados **TANQUE** e **SCANNER** embaixo da hotbar, no Tab. Clique num equipamento do inventário equipa (troca com o do slot); clique no slot tira (som `inv_move`); soltar o item da mão no slot também equipa (som `equip` 0,7). Não vai pra hotbar nem pro chão.
- **Tanque de O₂**: 10 Fe + 6 Si + 4 gelo, depois do projeto. Equipado, O₂ máximo **220 s**; a barra é proporcional ao máximo e mostra os segundos + "TANQUE". O alarme e a tela vermelha continuam nos 25 s restantes. Tirar o tanque corta o O₂ pra 100.
- **Scanner de navegação** *(dono: revisar)*: equipamento, 4 Fe + 4 Si depois do projeto. Equipado: **minimapa** 64×64 tiles no canto direito (embaixo da energia) e **M** abre o mapa grande da camada (som `map_open` 0,6, no máximo 1 a cada 0,3 s; fecha com M/Esc/Tab, *(B2)* com o botão **FECHAR** ou clicando fora da janela; o E agora troca a camada, ver "Mapa aberto panorâmico" no Redesign B2). Sem scanner, M só avisa.
- **Explorado** (`game/explore.py`): desde o 1º frame, em cada camada, a cada 0,2 s. Superfície: retângulo de ±20×±12 tiles em volta do player (a tela no zoom 0,75). Caverna: só o que a luz revela (lanterna 4, luminária 5, forte 7, boca da rampa 3,5, terminal 2, máquina 1,8 tiles) e que está na tela. Marcadores: *(B2)* pictogramas do mockup aprovado (ver "Mapa aberto panorâmico" no Redesign B2); antes eram formas simples (retângulo, anel, losango, ponto, quadrado, seta). A textura do mapa (`game/minimap.py`) só pinta os tiles novos e os minerados.
- **Luminária forte** (`lamp_t2`): aba Luz, 2 Fe + 2 Si + 1 gelo, depois do projeto, raio 7 tiles.
- **Drill nv.2: fora** do v0.3 (precisaria de máquina nova com sprite, regra de drill por tipo, drones e save; não ficava simples).
- **Objetivos** *(dono: revisar)*: depois de "Coloque uma luminária" entram "Ache um destroço" (chegar a 6 tiles de um), "Ache o projeto do tanque de O2" e "Fabrique e equipe o tanque de O2".
- **Save v6** (sem subir versão): cada camada ganha `explored` (bitset zlib+base64, ~100–400 bytes) e `crates` (só as caixas que mudaram); o progresso ganha `blueprints`, `equipment`, `equipped_ever` e `wrecks_visited`. Save do Marco 1/2 carrega com caixas cheias, nada visto e nada equipado.
- **Bug do "céu estrelado" na caverna** (print do Marco 2): eram os brilhos de minério do silício (#c3d1e2) e do gelo (#a6ecff), quase brancos e espalhados por toda rocha, até no miolo das paredes. Agora o brilho só sai em minério com chão do lado (a parede que o jogador vê) e numa cor saturada, sem o "+branco" no miolo.
- **Desempenho** (smoke, headless, zoom 0,75): superfície com minimapa ≈ 4,9 ms por frame; caverna escura com 36 luminárias ≈ 5,2 ms.
- **Duração** (simulador, estratégia nova "destrocos" = casual da caverna que antes vai à nave mais perto, pega o saque (37 un.) e equipa o tanque aos ~35 s): **36–38 min** na proposta (caverna sem tanque: 37–38). Números atuais: 31–33 min.

### Marco 4 · polimento técnico (parte que não depende do dono)
- **Morros** orgânicos (ver Marco 1). Prints `reports/dev/morros_antes.png` × `morros_depois.png`. Mesma quantidade (24–32) e massa parecida (~550–750 tiles de rocha). Como os morros passaram a ter gerador próprio, a seed padrão tem cratera, veios e destroços em outros lugares (mesmas regras); o simulador ficou dentro do ruído de antes (atual: destroços 30–32 min, caverna 31–39).
- **Mapa e minimapa**: marcadores distintos e legenda com o mesmo desenho (ver Marco 3). A janela do mapa alarga pra legenda caber.
- **Controles da pausa**: largura pelo texto mais comprido; quando as linhas não cabem na altura (Grande, 480×270), 2 páginas equilibradas com `<` `1/2` `>` e A/D.
- **Save na rampa**: grava o destino (ver Marco 2).
- **Revisão de prints**: fabricador alarga pra 6 abas caberem (a "Traje" saía da moldura); aviso de projeto cabe no vão do topo (no Grande sem o ícone) em vez de cobrir o painel do Ti; Opções da pausa com a ajuda dentro da moldura, acima da hotbar; seta do O₂ crítico não desce na hotbar; "Jogo salvo" logo abaixo da coluna da direita (cobria o medidor de energia); textos flutuantes escolhem a faixa pelo lugar na tela (não encavalam mais com vizinhos nascidos noutra altura).

### Aba LOGs do inventário (decisão do dono)
- O **Tab** ganha abas no topo, no estilo do fabricador: **Inventário**, **Fabricar** (ver "Fabricar em campo" abaixo) e **LOGs N/7** (contador de achados; ponto laranja se tem LOG lido ainda não aberto pela aba). Clique na aba ou **A/D** trocam (dá a volta); o Tab sempre abre no Inventário. Ir pra Fabricar ou LOGs devolve a pilha da mão pro inventário (sem espaço: não troca e avisa).
- Lista com os 7 na **ordem da história** (`LOG_ORDER`, ver §2). Achado: "LOG 0N · Dia X · <título>", clicável (ou W/S + Enter), abre a mesma tela de leitura do terminal e, ao fechar, volta pra aba. Não achado: "LOG 0N · ???" apagado, sem dia nem título, não clicável. W/S pulam os não achados.
- **NOVO**: selo laranja nos lidos (terminal, módulo ou registro de bordo) que ainda não foram abertos pela aba. Save v6 ganha `progress.logs_seen`; save v6 de antes, sem o campo, carrega com todos os lidos contando como vistos (sem NOVO).
- A janela da aba LOGs tem a largura do texto mais comprido de todos os LOGs (não muda conforme acha) e o mesmo topo da aba Inventário; se não couber na altura, mostra menos linhas e rola (rodinha/W/S). Nos 3 tamanhos de interface couberam as 7.
- Controles: "TAB · Inventário, fabricar em campo e LOGs (A/D: aba)".

### Fabricar em campo · kit de campo (pedido do dono no playtest)
- O problema: "achei um veio de minério, tenho que voltar na base pra fazer a drill" / "tô na caverna e tenho que voltar pra fazer luminária".
- A aba **Fabricar** do Tab (ordem **Inventário | Fabricar | LOGs**) fabrica o **kit de campo** em qualquer lugar, nas duas camadas: **Drill automática**, **Luminária**, **Luminária forte** e **Baú** (`C.FIELD_RECIPES`).
- **Só no fabricador**: terraformação (O₂, derretedor, aquecedor e os nv.2), painel solar, estação de drones e drone, e os equipamentos (tanque de O₂ e scanner). É o motivo de ainda voltar pra base.
- Mesmo **custo** e mesmas **travas** do fabricador: a drill continua liberando no Ti 10.000 (cadeado "TI 10.000"), e a luminária forte sem o projeto aparece como **"??? · projeto não encontrado"** (botão "SEM PROJETO").
- Gasta **só do inventário**: não puxa dos baús da base, mesmo estando na base. O custo mostra o que tem no inventário (falta em vermelho; *(B2)* o botão diz o que falta, "FALTAM 2 SILÍCIO").
- O item vai pro inventário, como no fabricador: fabricou, o menu fecha e, se caiu na hotbar, já entra no modo de colocar. Inventário cheio: não fabrica e avisa "Inventário cheio" (mesmo som). Som `craft`. **Shift+Enter**/Shift+clique fabricam até 5.
- Mesmo visual das linhas do fabricador (prévia, nome, custo com ícones/cores e botão CRAFTAR), numa janela "FABRICAR EM CAMPO · SÓ DO INVENTÁRIO" com a mesma faixa de abas e o mesmo topo das outras abas do Tab. **W/S** escolhe, **Enter** fabrica, clique na linha escolhe e no botão fabrica. A janela do Tab alargou um pouco pra as 3 abas caberem (a grade fica centralizada).

### Redesign da UI · B2 (aprovado pelo dono)
Referência: `reports/design/ui_redesign/index.html` (seção "Versão final (B + mixes)") e os mockups `b2_*.png`; coordenadas e cores em `tools/sprites/ui_mockups.py` (px da UI no Grande). Implementado em `game/ui.py`.
- **Estilo B**: cartões escuros e planos com o pixel de cada canto cortado, sem moldura pesada; cor é informação (laranja = ação/seleção, verde = tem, vermelho = falta). Abas com ícone no fabricador (só a ativa mostra o nome) e controle segmentado no Tab (Inventário | Fabricar | LOGs). A ajuda embaixo das janelas vira pares **tecla em caixinha + texto**; a dica do canto mostra as teclas em caixinha (a 1ª laranja). Slot desenhado em código (o `ui_slot.png` deixa de ser usado).
- **HUD**: O₂ numa pílula (barra + segundos com o tanque, % sem ele); objetivo num cartão com a barra laranja à esquerda (texto comprido quebra, o cartão não alarga); painel **"ÍNDICE TI"** (+/s, Ti grande numa faixa escura, O₂/calor/água com valor e unidade alinhados à direita, próximo estágio com barra segmentada, % e "faltam X · ~Y"); energia numa pílula (no déficit ocupa a largura do painel, com o aviso); minimapa num cartão com "MAPA" e a tecla M por dentro; hotbar com o número em cima de cada slot e, jogando, o nome e a quantidade do item escolhido numa pílula em cima dela.
- **Inventário (Tab)**: mochila, hotbar e o cartão **TRAJE** (o Explorador no meio, quadro 0 do `player_idle_down` 2×, com uma linha até o tanque e outra até o scanner; mesmos slots e cliques). À direita, o **detalhe do item** debaixo do mouse (ou da mão, ou o da hotbar): ícone 2×, nome, categoria, pilha/máximo e **"USADO EM"** (as receitas que gastam o item, achadas pelos custos; as de projeto ainda não encontrado ficam de fora).
- **Fabricador e aba Fabricar**: lista à esquerda (✓ dá pra fabricar, "falta" em vermelho, cadeado trancado ou sem projeto) e detalhe à direita (prévia, nome, descrição, kW, quantas já tem, uma linha por material com o ícone, "tem/precisa", barrinha e ✓/✗). Seletor **×1 / ×5** (o lote vale pro menu; Shift continua fazendo até 5) e o botão **FABRICAR**, que diz o que falta ("FALTAM 2 SILÍCIO"), "LIBERA EM TI 10.000" ou "SEM PROJETO". A lista mostra **6 receitas** (`C.FAB_VISIBLE_ROWS`) e rola se tiver mais. Na aba Fabricar o detalhe fica um pouco mais compacto no Grande (a janela e a ajuda não podem chegar na hotbar).
- **Baú, drill, estação e caixa**: inventário à esquerda, o outro painel à direita e, no meio, **"GUARDAR RECURSOS >>"** e **"<< PEGAR TUDO"** (na drill, na caixa e nas sobras da estação, só o "<< PEGAR TUDO"). Seção **DRONES** com o resumo no título ("· envia ferro"); no Envia e no Recebe **o ícone do material é o botão**: aceso (fundo tingido, borda laranja no Envia e ciano no Recebe) ou apagado; Lote 1/5/10/20.
- **Opções**: sliders de som; **Tela cheia Não|Sim**, **Zoom** e **Interface** como controles segmentados (clique no segmento escolhe; A/D e Enter continuam valendo). A Interface vai na ordem **Grande | Média | Pequena**, a mesma do A/D. Botão **VOLTAR**.
- **Mapa (M)**: botão **FECHAR** (com hover), clique fora da janela fecha, clique dentro não; o mouse num marcador mostra o nome (base, cratera/rampa, destroço, veio, terminal, você). Nenhum clique com o mapa aberto chega no jogo, e a rodinha não troca a hotbar. O cursor e o tooltip vão por cima da textura do mapa (antes o cursor sumia embaixo dela).
- **Mapa aberto panorâmico** (aprovado pelo dono; `reports/design/ui_redesign/index.html`, seção "Mapa aberto (B2)", mockups `map_var_superficie.png` / `map_var_caverna.png`). Câmera e filtros em `game/map_view.py`, pictogramas em `game/map_markers.py` (porte do `marker()` do `tools/sprites/ui_mockups.py`), desenho no `draw_map` do `game/ui.py`.
  - **Janela**: 464×258 px da UI no Grande, área do mapa 444×196; no Média/Pequena e em janela grande a janela ocupa a tela toda (8 px de margem) e mostra mais tiles. Cabeçalho: "Mapa", **Superfície | Caverna**, **EXPLORADO N%** com barrinha e **FECHAR [M]**.
  - **Zoom**: só níveis inteiros **1× / 2× / 3× / 4×** (1 a 4 px da UI por tile), padrão **2×**, selo "ZOOM N×" no canto. A **rodinha** com o mapa aberto é o zoom do mapa (não mexe no zoom do mundo nem na hotbar, sem Ctrl), ancorada no tile debaixo do mouse. **+ / −** (e = e o numérico) ancoram no centro, igual aos botões **+ / −** da lateral.
  - **Arrastar** com o botão esquerdo, 1:1 com o mouse, só depois de **3 px da UI** de movimento (antes é clique; clique num marcador só mostra o tooltip). **WASD/setas** andam ~1 área por segundo (o player fica parado).
  - **Centralizar**: botão com a setinha ou **C**. O mapa **sempre abre centrado em você**, no último zoom usado.
  - **Limites**: a borda da camada encosta na borda da área e nunca passa; se no zoom atual a camada é menor que a área num eixo (superfície no 1×/2× do Grande na largura, caverna no 1×), aquele eixo fica centrado e travado. Fora da camada continua o fundo pontilhado.
  - **Camadas**: clique no seletor ou **Q/E** (o E não fecha mais o mapa). Mantém o zoom e centra em você ou, se você está na outra camada, na rampa dela (aí a distância do tooltip é contada "da rampa"). "Você" só aparece na sua camada. A **Caverna fica apagada e sem clique até a primeira descida**.
  - **Não visto**: fundo escuro da B com um ponto a cada 8 tiles e 1 tile de névoa mais clara na borda do explorado.
  - **Marcadores** (fixos, 2× no mapa e 1× no minimapa, não mudam de tamanho com o zoom): você (seta amarela com anel, apontando pra onde olha), base (**opção A, módulo de frente**, 13×11), cratera (anel branco, seta pra baixo) / rampa (anel verde, seta pra cima), destroço (losango laranja) / vazio (losango vazado, a caixa esvaziou), veio (quadradinho na cor do minério), terminal (tela verde), **máquinas** (as colocadas, menos luminária) e **baús** (novos). O minimapa usa os mesmos pictogramas, sem máquinas e baús (amontoam na base) e sem filtro.
  - **Só o que já foi visto**: todo marcador precisa de pelo menos um tile no explorado da camada (veio, destroço, terminal, cratera/rampa, máquina, baú); as exceções são **você** e a **base**. Na caverna, terminal e boca da rampa têm luz própria: se a luz deles esteve na tela, contam como vistos mesmo longe do player e aparecem numa ilhota de explorado no meio do não visto (não é spoiler: o jogador viu a luz). Luz fora da tela não conta.
  - **Grupos** *(polimento)*: máquinas coladas viram **um marcador só** com o número num selinho laranja (o mesmo pros baús, cada categoria agrupando só com ela, então os filtros continuam valendo). Junta quem está a menos de **10 / 5 / 3 / 2 tiles** (1× / 2× / 3× / 4×, a maior distância entre os eixos; em cadeia): no 1× e no 2× agrupa mais, no 4× só o que fica a 1 tile. O grupo fica no centro deles e o tooltip ganha uma linha: "Máquinas · 6" / "3 geradores de O₂, 2 aquecedores, 1 drill" (até 3 tipos, o resto vira "+N") / distância e direção. Baús: "Baús · 3" / "5/72 pilhas". Prioridade do tooltip igual à da categoria. `map_view.cluster`.
  - **Filtros**: fileira de chips embaixo, um por categoria que existe na camada aberta (Base, Cratera/Rampa, Destroço, Vazio, Veios, Terminal, Máquinas, Baús); ligado = fundo hover + borda clara, desligado = escuro e apagado. "Você" não é filtro. Marcador escondido não ganha tooltip. Valem igual nas duas camadas. Se não couber na largura, o chip aperta o espaçamento e, no último caso, fica só com o ícone.
  - **Tooltip**: cartão B2 abaixo do cursor, preso dentro da área: pictograma, nome e "estado · distância em tiles + direção em 8 pontos" (ex.: "caixa cheia · 39 tiles a noroeste"). Encostou em dois: você › base › destroço › terminal › rampa/cratera › veio › máquina › baú. O marcador com o mouse ganha cantoneiras laranja.
  - **Escala "16 tiles"** embaixo à esquerda e o **N** embaixo à direita.
  - **Persistência**: os filtros escondidos e o último zoom são **preferência do jogador**: vão no `settings.json` (`"map_hidden": ["machine"]`, `"map_zoom": 2`), valem pra qualquer save e **não entram no save do jogo**. A posição da câmera não é salva.
  - Nenhum clique, arrasto, rodinha ou tecla com o mapa aberto chega no jogo; Esc, M e Tab fecham.


## 10. Escopo do v0.4: "mundo vivo"
Spec: `docs/superpowers/specs/2026-10-13-v04-mundo-vivo-design.md`. Plano do Marco 1: `docs/superpowers/plans/2026-10-13-v04-marco1-tempestade.md`.

### Marco 1 · Tempestade: clima e jogabilidade (números de partida, ajustáveis em `game/config.py`, bloco `STORM_*`)
- **Intensidade**: tudo da tempestade é multiplicado por `state.storm` (1 = cheia no estágio Tempestade, desce até 0 em ~20 s ao chegar no Árido). Na **caverna** a intensidade efetiva é 0: lá embaixo não tem rajada, empurrão nem O₂ extra.
- **Clima** (`game/weather.py`, `state.weather`, determinístico pela seed do mundo, não vai no save):
  - **vento**: direção dominante sorteada pela seed; foge dela até **40°** pra cada lado, com um alvo novo a cada 6–14 s, virando no máximo **8°/s** (variação lenta);
  - **rajadas**: a 1ª entre **10 e 20 s** (pro jogador conhecer logo a mecânica), depois uma a cada **20–40 s** (de começo a começo), cada uma segurando o pico por **3–5 s**; a força (`gust`, 0 a 1) sobe e desce em **0,5 s**. Rajada nova só começa com a tempestade cheia: na transição pro Árido as rajadas param (a que estava rolando termina);
  - **visão** (`view_tiles`, lida pela camada de poeira): **7 tiles**, caindo até **4** no pico da rajada, e abrindo até o infinito conforme a tempestade some (raio ÷ intensidade).
- **Empurrão**: na rajada o player ganha `vento × PLAYER_SPEED × 35% × gust × storm` px/s (~42 px/s no pico), somado ao andar e com a mesma colisão (não atravessa parede nem máquina). Parado, ele **desliza** sem animar a caminhada nem virar; andando contra, **avança a ~65%** da velocidade. Sem empurrão desmaiado, durante o fade da rampa e com qualquer tela aberta (inventário, fabricador, mapa, baú...).
- **O₂**: fora da base gasta **×1,25** com a tempestade cheia, interpolando com a intensidade (`1 + 0,25 × storm`). Na zona da base, a recarga não muda; na caverna, o gasto é o normal.
- **Aviso no HUD**: enquanto a rajada está forte (`gust > 0,3`), uma pílula **"RAJADA"** no estilo B2 (barra laranja à esquerda, ícone de vento com 3 traços correndo) logo abaixo da coluna do O₂/objetivo. Some quando a rajada baixa.
- **Som**: `gust` (0,7 no `VOLUME`) no começo de cada rajada, com o volume proporcional à intensidade. Sem `gust.wav`, fica em silêncio.

## 11. v0.4 · Marco 2: Geografia nova
Plano: `docs/superpowers/plans/2026-10-13-v04-marco2-geografia.md`. Referência visual aprovada: `reports/design/regioes/index.html` (v8.0) e o mapa `mapa_regioes.png`. Cada trilha escreve a sua parte aqui.

### Geração e dados (trilha A · `game/geo.py`, `game/surface_gen.py`; números no bloco `GEO_*` do `game/config.py`)
- **Geografia** (`generate_geo(seed, w, h, base) -> Geo`, numpy, sem pygame): porte do `regions_core.gen_world` da Designer, variando pela seed. Não vai no save: sai igual da seed no load. A camada da superfície expõe `layer.geo` (na caverna é `None`).
  - **Relevo**: altura 0..1 por tile (fbm de 3 oitavas, ~0,52 a 0,72), menos a tigela do salar e 3 depressões pequenas do planalto (raio 6 a 8,5 tiles, a ~25–45 tiles da base, mexidas até 4 tiles pela seed).
  - **Regiões**: **planalto rachado** em volta da base (um raio de 16 tiles em volta dela é sempre planalto e seco), **salar** a leste (elipse de ~29–34 × 22–27 tiles a ~55–64 tiles da base, borda torcida, a maior bacia), **basalto** a oeste e sudoeste (x < ~44 com ruído, y > ~44, alargando pro sudoeste) e a **faixa gelada** na borda norte (y < ~24 com ruído). Nas seeds 1, 7 e 42: planalto ~58%, basalto ~22%, faixa gelada ~13%, salar ~6%.
  - **Bacias**: onde a altura fica abaixo de **L3**, o tile guarda o nível em que alaga no Marco 3 (`basin`: 0 = L1 0,19 · 1 = L2 0,29 · 2 = L3 0,385; -1 fora). No M2 elas só aparecem secas no chão (leito e marca d'água, trilha B).
  - **Borda orgânica**: `geo.region_px(px, py)` dá a região num pixel do mundo = a do tile em (x + dx, y + dy), com o deslocamento do `warp_field` da Designer preso em **±14 px**. A divisa vira curva e nunca passa de 14 px da divisa por tile.
- **Formações fixas** (`geo.formations`, pegada e âncora do `regions_palettes.json` da Designer): monolito (2–3) e arco (1–2) no planalto, crosta de sal (2–3) no salar, pináculos (2–3) e cone (1) no basalto. Cada uma inteira na sua região (com 3 tiles de folga), fora de bacia (a crosta de sal pode: vira ilhota no Verde), a 26+ tiles da base e a 16+ uma da outra. A pegada vira o tile **`FORMATION`** (sólido, não minera, não é parede; quem desenha é o objeto da formação). No arco só as pernas bloqueiam: o vão de 3 é andável. Cada formação tem **3 ou 4 afloramentos** (rochas pequenas) a 1–2 tiles da pegada, com o minério da região (planalto ferro/silício, salar silício, basalto ferro, gelada gelo), nunca no vão do arco.
- **Gelos-portão** (2 ou 3): bolsões na cordilheira do norte (interior de 8×7 tiles, anel de **rocha que não minera**, `BEDROCK`, pra não dar pra contornar cavando), fechados por um gelo-portão 4×2 (`ice_gate`, formação) no corredor de baixo, com um avental livre na frente. O interior só é alcançável quando o portão sumir (Marco 3). Cada bolsão já marca onde vão o destroço melhor e o contêiner lacrado do Marco 3 (`geo.pockets[i].wreck_spot`, `.container_spot`).
- **Morros por região**: 26 a 34 morros; a região do centro decide a chance de ficar (salar 0,05, planalto e gelada 1, basalto 2,2) e o minério sai da região de cada tile (basalto mais ferro, gelada mais gelo, chance de minério 12% no planalto e 16% no basalto e na gelada). Morro nenhum em bacia nem a menos de 4 tiles de uma formação. No mapa (M) e no minimapa a rocha pinta com a sombra da rampa do morro da região.
- **Nada nasce** em bacia, no halo de 2 tiles das formações nem no bolsão/avental de um portão (`world.keep_clear`): veios, destroços, rochas pequenas e a rocha que reaparece respeitam. A **cratera** fica inteira no planalto, seca, sem cortar morro (mesmo tamanho e mesma regra de rampa de antes).
- **Alcance**: todo destroço (a caixa) e todo veio são alcançáveis a pé da base sem cavar; os portões bloqueiam só o que está atrás deles (testado nas seeds 1, 7 e 42, e conferido em 120 seeds).
- **Mapa e minimapa**: o chão da superfície pinta pela região (cor média da rampa do Árido de cada uma). A formação vista vira o marcador **"Formação"** (pictograma de pico de pedra, tooltip com o nome e a região), sem chip de filtro e por baixo dos outros marcadores.
- **Save v7** (novo jogo obrigatório): o save v6 (v0.3 e v0.4 Marco 1) vira "save antigo" como os v1–v5: a tela de título avisa, só deixa começar um novo jogo e o arquivo vira `slot1.v6.json`.

### Chão assado (trilha B · `game/ground.py`; números no bloco `GROUND_*` do `game/config.py`)
- **O que é**: na superfície (com `layer.geo`), o chão deixa de ser tile repetido e vira o chão da proposta da Designer (`regions_scene.Scene.ground`): textura grande de 512 px por região, **borda entre regiões curva** (a região de cada pixel é a do `geo.region_px`, o mesmo `geo.warp` de ±14 px), 1 px de fenda na divisa, **leito seco** (silte com rachadura de lama) no planalto dentro de bacia e as **marcas d'água secas** L1, L2 (tracejadas) e L3 (contínua) como curvas de nível suaves do `geo.basin`; no salar, anel escuro. Por cima, **decalques** (manchas, rachaduras longas, placas, cascalho, sulcos de vento, escória, cristinhas, lâminas de gelo) sorteados pela seed numa grade de 96 px presa no mundo, sem nenhum no raio de 6 tiles da base nem em volta das formações. Na caverna (sem geo) o chão é o de sempre.
- **Estágios**: a cor sai da rampa da região no estágio (`regions_palettes.json`, tabela BASE, chaves storm/arid/mist/green): a Tempestade e o Árido agora têm chão diferente (a Tempestade é a rampa com poeira assentada). A água de hoje (poças da Névoa e do Verde) continua desenhada por cima até o Marco 3 trocar pelas bacias enchendo, e a sombra das paredes também.
- **Como desenha**: o chão é **assado** em blocos de 16×16 tiles (512×512 px) com numpy e guardado como código sem cor (classe·16 + índice da rampa); a cor é a paleta de uma Surface de 8 bits, então trocar de estágio não assa de novo. No quadro é 1 blit por bloco visível. Assar custa ~36 ms por bloco e é feito em faixas de 32 linhas, até 3 ms por quadro, primeiro o que está na tela e depois o que está a até 320 px dela; bloco que ainda não ficou pronto aparece com a cor chapada da região de cada tile. Se nenhum bloco da tela está pronto (começo do jogo, load) assa a tela inteira na hora (~0,4 s). Cache LRU de 40 blocos.
- **Transição de estágio**: o bloco onde passa a mancha da transição (game/transition.py) mistura os dois estágios por pixel: cada pixel usa o estágio do tile em (x + dx, y + dy), com o mesmo deslocamento das regiões, então a frente da mancha é uma curva orgânica (no lugar do pontilhado por tile). É refeito quando o degrau da janela muda; até ficar pronto, o bloco anterior continua na tela.
- **Decoração solta com altura** (não colide, não minera): lascas de basalto, cristais de sal e pedaços de gelo em ~3,5% dos tiles de basalto, salar e faixa gelada, ordenados pelo pé como os outros objetos. Some onde tem máquina, veio, destroço, rocha ou parede.

### Morros orgânicos (trilha C · `game/hills.py`; números no bloco `HILL_*` do `game/config.py`)
- **O que é**: na superfície, os morros mineráveis e a cordilheira da borda perdem o degrau de grade (porte do `regions_scene.hill_layers` da Designer). A colisão e a mineração continuam por tile; só o desenho muda. Grade dual: o campo "tem parede" é interpolado entre os centros dos tiles (bilinear com smoothstep), somado a um ruído de borda e cortado em 0,5. A escada vira diagonal, o canto convexo arredonda e o tile sozinho vira seixo. O topo continua 24 px acima do tile (`hill_top.png`) e a **face** é a silhueta extrudada 24 px pra baixo (`hill_face.png`, estratos e fissuras), com contorno e brilho na borda. Os minérios (`ore_*.png`) vão por cima do topo, recortados pela silhueta; a borda do mapa fica mais escura. Cor da rampa `HILL` da região (`layer.geo`) no estágio. Embaixo do morro vai chão, e a sombra quadrada da parede no chão sai. A caverna continua com as paredes de hoje (`C.ORGANIC_HILLS = False` volta a superfície pro jeito antigo).
- **Como desenha**: assado em blocos de 8×8 tiles (~3 ms cada), cortado em **uma tira por linha de tiles** (topo + face daquela linha), que entra no `build_draw_list` no lugar das paredes da linha (`("hills", ty)`). Assim o player logo acima do morro fica atrás do topo e logo abaixo fica na frente da face, como antes. Cada bloco guarda a assinatura das paredes em volta e, quando um tile é minerado, **só os blocos que enxergam aquele tile são re-assados** (1, ou 2 na beira). Na troca de estágio o bloco só é recolorido; na mancha da transição a cor vai por tile. O que está na tela é assado na hora e mais 1 bloco da volta por quadro; LRU de 96 blocos. A rachadura da mineração e o fantasma de colocar são os de sempre.
- **Formações** (C3, `hills.FormationSprites`): cada `geo.formations` é um objeto do `build_draw_list` com o sprite `form_<kind>.png` (o gelo-portão, `ice_gate_<variant>.png`) e a `anchor` caindo no `Formation.base_px`. O y da ordem é o do `base_px`, a mesma regra das máquinas: acima do pé o player fica atrás e ganha o raio-x quando a silhueta cobre o corpo. A pegada é `C.FORMATION`, e o vão do arco é andável. O PNG indexado é recolorido pela rampa da formação (`regions_palettes.json → formations[kind].ramp/region`: SAND no hoodoo e no arco, HILL no basalto e no cone, BASE no sal, ICE no gelo) no estágio do tile do pé. A sombra é a que já vem no sprite (índice 9, alfa 80).
- **Cratera de impacto** (C4, `hills.CraterSprites`): na superfície a cratera passa a ser o `crater_impact_<etapa>.png` (168×150, âncora do JSON no centro dos 3×3, ordenado pela borda de baixo dos 3×3) com o `crater_ejecta.png` no chão em volta (depois do chão, antes dos veios); saem o `crater.png`/`crater_ramp.png` da superfície. Colisão 3×3 e E no tile do meio de baixo, como antes. Paleta: 0..9 `BASE` do planalto, 10..17 `ICE`, 18..20 `METAL`, no estágio do tile do meio.
- **Tampa de gelo**: `layer.crater_ice` da superfície, de 0 (tampada) a 4 (`CRATER_ICE_STAGES`, vazia com a rampa exposta); cada etapa é um sprite. Enquanto não chega a 4 o E não desce (`GameState.ramp_blocked`) e a dica vira "Gelo · derrete com o calor" (perto e com o mouse em cima, longe). Subir da caverna nunca trava. Vai no save (`layers.surface.crater_ice`; save v7 sem o campo = tampada). No Marco 2 fica sempre tampada: o derretimento pelo calor é do Marco 3.
- **Objetivo** "Derreta o gelo da cratera" entra logo antes de "Desça na caverna pela cratera [E]" (completa com a tampa vazia ou já tendo descido). No Marco 2 ele não completa sozinho, então os objetivos seguintes ficam esperando o M3 (ou o F4).
- **F4 (debug)**: derrete a tampa na hora (etapa 4), no mesmo esquema do F1–F3 (`C.DEBUG_MELT_CRATER`), com o aviso "DEBUG · CRATERA ABERTA (F4)" no topo da tela e a linha nos Controles da pausa. O smoke e os testes que descem na caverna usam o F4 (ou setam o estado).

### Mundos com nome e seed (pedido do dono · `game/worlds.py`, tela em `game/title.py`)
- **3 espaços**: `saves/world1.json`, `world2.json`, `world3.json` (o formato do `game/save.py`) e o índice `saves/worlds.json` (`last` = último mundo jogado, `migrated_slot1`).
- **Bloco `world` no save**: `{"name", "seed", "created", "played_s"}`, **sem subir a versão** (continua v7). A seed que gera o mapa é a `seed` da raiz; `world.seed` repete ela e `played_s` repete o `progress.play_time`. Save sem o bloco carrega como "Mundo 1".
- **Migração**: na primeira vez, um `saves/slot1.json` **v7** vira o mundo 1 ("Mundo 1", seed 7) por **cópia**: o `slot1.json` fica intacto como backup e não volta a virar mundo se o mundo 1 for apagado. Um `slot1.json` v1–v6 não migra: o título mostra "Save de uma versão antiga · comece um novo mundo" com Continuar apagado e, quando um mundo é criado, ele vira `slot1.v<N>.json` (sem sobrescrever backup: se já existe, `-2`, `-3`...). Nenhum outro arquivo da pasta é tocado.
- **Título**: **Continuar** (o último mundo jogado; se ele sumiu, o de save mais recente; à direita, nome e tempo de jogo) · **Mundos** · **Sair**.
- **Mundos** (janela B2): os 3 espaços com número, nome, data do último save e "SEED N · ESTÁGIO · X MIN"; vazio = "+ Novo mundo". Enter/clique joga (vazio abre o Novo mundo). **Apagar**: o botão APAGAR (ou X/Delete) arma ("APAGAR DE VEZ? CLIQUE DE NOVO", botão vermelho) e o segundo clique/tecla (ou Enter) apaga; Esc, mexer a seleção ou clicar fora desarma. Save de versão antiga ou estragado num espaço: Enter abre o Novo mundo ali e apagar/criar guarda o arquivo como `worldN.v<N>.json` / `worldN.estragado.json`.
- **Novo mundo**: campo **Nome** (vazio = "Mundo N", até 20 letras, o `TextField` do nome do baú) e **Seed** opcional (até 20). Vazia = a seed **sorteada** ao abrir (1 a 999.999.999), que aparece no próprio campo e fica salva. Só dígitos = o número (acima de 2³¹ dá a volta). Qualquer outro texto = **sha256** do texto (4 bytes, 31 bits): o mesmo texto dá sempre a mesma seed, em qualquer máquina (o `hash()` do Python não serve). "SEED DO MUNDO: N" mostra o resultado antes de criar. Teclado: Tab/setas trocam o campo (W/S são letras aqui), Enter cria, Esc volta. Ao entrar, um aviso "Nome · seed N".
- **A seed vale pra tudo**: `state.seed` gera a superfície (`surface_gen` → `generate_geo`), a caverna, destroços e saque, o clima (`Weather`), a mancha da transição (`StageMap`) e os grãos da poeira (`DustParticles`); o Renderer troca os dois últimos quando a seed do estado muda (`Renderer.use_seed`). A `C.WORLD_SEED` (7) ficou só como padrão do smoke, dos testes e do fundo do título.
