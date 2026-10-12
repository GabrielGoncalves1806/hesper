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
| Interagir (E) | Abre o que está **debaixo do mouse** (baú, drill, estação ou terminal) se estiver no alcance do E; senão, o mais perto do player; sem nada no alcance, na base abre o fabricador. Vale igual pro **Shift+E** na drill. O alvo ganha um **contorno claro** e o texto do canto mostra o que o E vai abrir (com o mouse numa máquina que o E não vai abrir, o canto diz qual ele abre) |
| Zoom do mundo | + / - (ou = e o teclado numérico) · Ctrl+rodinha (Cmd no Mac) · níveis 0,75× · 1× · 1,5× · 2× (padrão 1×). Só o mundo aproxima: HUD e menus ficam do mesmo tamanho |
| Tela cheia | F11 ou Alt+Enter · também em Pausa > Opções. Usa a resolução do monitor mantendo 16:9 (tarja preta se sobrar) |
| Tamanho da interface | Pausa > Opções > **Interface: Grande / Média / Pequena** (padrão **Média**, salvo em `settings.json`). Muda só HUD, menus, inventários, fabricador, título, terminal, avisos e tooltips; o mundo continua no zoom escolhido. Grande = a UI de sempre (480×270 esticada pra tela); Média ≈ 75% disso; Pequena ≈ 50%. Em Média/Pequena a escala é inteira (letra pixel art limpa) e nunca menor que 1 px de imagem por px de tela: em 1920×1080 dá 4 / 3 / 2 px por px da UI; numa janela de 960×540 os três ficam iguais. Os painéis se ancoram nos cantos/centro. Textos presos no mundo (+15 FERRO, nome do baú) acompanham o mundo na posição e a interface no tamanho da letra |
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
  - Guarda até **20** unidades num **inventário de 1 slot** (só o minério dela). Cheia, para.
  - **E** perto da drill abre o painel dela (estilo baú): inventário do player à esquerda e a drill à direita, com clique pra tirar (esquerdo a pilha, direito 1, Shift+clique tudo daquele item), botão **Pegar tudo** e a seção **DRONES** (ver §8, Marco 3). Não dá pra guardar nada na drill: ela só produz.
  - Atalho rápido: **Shift+E** perto da drill coleta tudo direto pro inventário, sem abrir o painel.
  - Com o mouse em cima, mostra o conteúdo ("12/20 ferro").
  - Pode ser desmontada com clique direito. Volta pro estoque, e o conteúdo vai pro inventário.
  - Não soma Ti.
  - Custo e ritmo finais quem define é o simulador de balanceamento (`tools/dev/balance_sim.py`).
- Logística: os drones da estação levam o minério das drills pros baús (§8, Marco 3).

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

## 8. Escopo do v0.2: "a base ganha vida"

Tema: **automação**. O jogador monta um sistema que trabalha por ele, e o resto do v0.2 existe pra sustentar isso.
Decisões do dono: inventário com slots (a mochila de upgrade fica pra depois), automação com **drones** (sem esteiras), **energia global sem fios**, e água e comida ficam no v0.3.
Os números abaixo são o ponto de partida; o balanceamento final sai do `tools/dev/balance_sim.py`.

### Marco 1 · Fundação
**Save/load**
- Um slot em `saves/slot1.json` (no `.gitignore`), em JSON **versionado** (`"version": N`), com migração simples quando o formato mudar.
- **Salva só o que muda**: o mundo é gerado pela seed, então o save guarda os tiles minerados e não o mapa inteiro. Também guarda: player (posição, direção, O₂), inventário e baús, máquinas e drills (com o conteúdo), índices e Ti, objetivos, terminais lidos, fontes da transição, energia e tempo de jogo.
- **Autosave** a cada 2 min e ao sair. No menu de pausa entra "Salvar e sair".
- **Tela de título** mínima: nome do jogo, "Continuar" (só se existir save), "Novo jogo" (pede confirmação se já existir save) e "Sair".
- Cada sistema novo do v0.2 tem que entrar no save, com teste de ida e volta (salvar → carregar → estado igual).

**Inventário com slots**
- O player tem **16 slots**. Recursos empilham até **50** por slot; máquinas fabricadas viram **itens** e empilham até **5**.
- **Hotbar** de 8 slots no rodapé central. Teclas **1–8** ou a rodinha do mouse selecionam (com Ctrl segurado a rodinha mexe no zoom). Se o item selecionado for máquina, o jogo entra no modo de colocar (o drone é item, mas não se coloca no chão: vai na estação). Isso substitui o estoque de máquinas atual (teclas 1–7).
- **Tela de inventário (Tab)**: grade dos 16 slots e a hotbar. Clique pega e solta a pilha, e clique direito pega metade.
- **Inventário cheio**: o minério minerado **não é coletado**, e aparece o aviso "Inventário cheio" (o tile quebra mesmo assim).
- O **fabricador** usa o que está no inventário **e nos baús dentro da zona da base**.
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
- **Fabricador com abas**: **Terraformação** (O₂, derretedor, aquecedor e os nv.2), **Energia** (painel solar), **Automação** (drill, estação, drone) e **Armazenamento** (baú). As categorias ficam em `C.MACHINE_CATEGORY`. **A/D**, **←/→** ou **Tab** trocam de aba (E fecha o menu), **W/S** escolhe dentro da aba, clique na aba ou na receita também. A lista mostra 5 receitas e rola (rodinha do mouse ou acompanhando a seleção), com barra de rolagem quando não cabe. Aba sem nada liberado aparece apagada, mas abre e mostra as bloqueadas.
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
  - **Superfície**: deserto aberto de 192×192, com a cápsula no centro, recursos soltos que reaparecem, rochas pequenas, morros, cordilheira na borda, **3 a 5 veios só** e destroços.
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
- **Save v6**: exige novo jogo, sem migração do v5.
- **Marcos**: 1 Superfície · 2 Caverna · 3 Destroços/projetos/tanque/scanner · 4 Polimento.
- **Fora do v0.3**:
  - v0.4: biomas de caverna, mochila, drill melhor, peças raras e elevador de carga;
  - depois: água e comida.

### Assets do Marco 1 · Superfície (contrato)
Entregues em `_pending/` até o dono aprovar. Os morros usam a arte de parede que já existe (`wall_*`, `wall_face_*`), e a cordilheira da borda também (o jogo escurece ela).

| Sprite | Tamanho | Observação |
|---|---|---|
| `sand_{stage}_{0..3}.png` | 32×32 | chão do deserto, 4 variações (areia, cascalho, dunas, manchas de rocha). stage = `dead`, `mist`, `green` |
| `rock_small.png` | 32×32 | rocha pequena no chão (1 tile, quebrável), contorno `#1b1630`, funciona nos 3 chãos |
| `pickup_iron.png` `pickup_silicon.png` `pickup_ice.png` | 16×16 | recurso solto no chão, legível de longe, com sombrinha no chão |
| `crater.png` | 96×96 | cratera 3×3 fechada (Marco 1), escura no centro, borda de rocha |
| `crater_ramp.png` | 96×96 | a mesma cratera com a rampa de descida aberta (usada no Marco 2) |

| Áudio | Tipo | Quando toca |
|---|---|---|
| `desert_wind.wav` | loop 20–40 s, baixíssimo | camada de vento seco por cima do `amb_{stage}` na superfície. Some na caverna |

Recursos soltos usam o `pickup.wav` já aprovado; rochas usam `mine_hit`/`mine_break`.
