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

| Log | Texto |
|---|---|
| LOG 01 | "Dia 3. Pouso perfeito. A cratera é maior do que as sondas mostraram. Começamos a montar os geradores amanhã." |
| LOG 02 | "Dia 97. O índice subiu rápido demais esse mês. A Dra. Ilves pediu pra desacelerar. A diretoria disse que o cronograma não espera." |
| LOG 03 | "Dia 212. O derretedor 4 parou de novo. A Dra. Ilves jura que o gelo daqui não é só água, que tem alguma coisa dentro dele. Ninguém quis ouvir. Amanhã a gente desce pro nível 2 de qualquer jeito." |

O mistério do gelo **não se resolve no MVP**. É gancho pro futuro.

## 3. Direção visual

Referência obrigatória: `reports/mockups/mockups.html` (abre no navegador).

- **Tile 32×32 px**, visão top-down 3/4. Quando o tile de baixo é chão, a parede mostra uma faixa de topo de 8 px e uma **face frontal alta de 24 px**. A parede tem que parecer parede, não degrau.
- **Resolução interna 960×540** (30×17 tiles visíveis), escalada inteira pra janela. Pixel art sem suavização.
- Personagem: astronauta **chibi 32×32**, com capacete grande (~metade da altura), visor escuro azul-marinho com reflexo, traje branco com detalhes vermelhos e mochila. Tem 3 direções (baixo, cima, lado).
- Luz: cosmética no MVP (brilho das máquinas e do capacete). Escuridão de verdade só no v0.3.

### Paletas por estágio (hex)

| Elemento | Morto (Ti < 10k) | Névoa (10k–100k) | Verde (≥ 100k) |
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
| Debug (dev) | F1 acelera o tempo ×10 · F2 +10.000 Ti |

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
  - Guarda até **20** unidades. Cheia, para.
  - **O jogador precisa ir buscar:** com **E** perto da drill, coleta tudo pro inventário.
  - Com o mouse em cima, mostra o conteúdo ("12/20 ferro").
  - Pode ser desmontada com clique direito. Volta pro estoque, e o conteúdo vai pro inventário.
  - Não soma Ti.
  - Custo e ritmo finais quem define é o simulador de balanceamento (`tools/dev/balance_sim.py`).
- Futuro (fora do escopo): drones de logística levando o minério das drills pra base.

### Estágios de terraformação
| Estágio | Ti | O que muda |
|---|---|---|
| 1 · Morto | 0 | paleta vermelha, poeira |
| 2 · Névoa | 10.000 | paleta fria, poças em tiles baixos, névoa, chuva fina, receitas nv.2 |
| 3 · Primeiro verde | 100.000 | grama, musgo, lagos, plantas · mensagem de fim do MVP |

A transição de estágio tem um aviso na tela ("ESTÁGIO 2 · PRIMEIRAS CHUVAS").

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
| `drill_side.png` | 96×16 | broca na mão, olhando pra direita (o jogo espelha). 4 quadros de 24×16 girando, só tocados enquanto minera |
| `drill_down.png` `drill_up.png` | 64×24 | 4 quadros de 16×24 · ponto de pega relativo ao quadro do player documentado no report |
| `floor_{stage}_{0..3}.png` | 32×32 | 4 variações · stage = `dead`, `mist`, `green` |
| `wall_{stage}_{0..2}.png` | 32×32 | topo da rocha, 3 variações |
| `wall_face_{stage}.png` | 32×24 | face frontal alta. Quando o tile abaixo é chão, o tile da parede mostra os 8 px de cima do `wall_{stage}_N` + essa face de 24 px |
| `water_{stage}.png` | 32×32 | |
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
| `amb_dead.wav` `amb_mist.wav` `amb_green.wav` | loop 20–40 s | ambiente de cada estágio |

## 7. Organização da equipe

| Pasta | Dono |
|---|---|
| `docs/` | Gerente (orquestrador) |
| `game/`, `pyproject.toml`, `tests/` | Dev |
| `assets/sprites/`, `tools/sprites/`, `reports/design/` | Designer |
| `assets/audio/`, `tools/audio/`, `reports/audio/` | Som |
| `reports/mockups/` | referência, ninguém edita |

Ninguém mexe na pasta do outro. Dúvida ou conflito vai pro gerente.
