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
| Debug (dev) | F1 acelera o tempo ×10 · F2 +10.000 Ti · F3 liga/desliga o modo rápido: player ×2 e broca ×5 (`DEBUG_SPEED`/`DEBUG_MINE`) e, a partir do v0.5 M3, mapa e minimapa inteiros sem explorar (ainda pedem o scanner; só exibe, não grava como explorado). F1 e F3 mostram "DEBUG · ..." no topo da tela |

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
| Aquecedor | 12 ferro, 8 silício, 3 magmatita (§12) | +4 pK/s | Ti 500 |
| Gerador de O₂ nv.2 | 30 ferro, 20 silício, 10 gelo | +25 ppq/s | Ti 10.000 |
| Derretedor nv.2 | 25 ferro, 30 gelo | +20 ppm/s | Ti 10.000 |
| Aquecedor nv.2 | 35 ferro, 25 silício, 10 magmatita | +30 pK/s | Ti 10.000 |

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
| 2 · Árido ("céu limpo") | 7.000 | a tempestade some em 20 s (`STORM_FADE_S`): a poeira afina e as rajadas param · mesma arte, sem água |
| 3 · Névoa | 10.000 | paleta fria, poças em tiles baixos, névoa, chuva fina, receitas nv.2 |
| 4 · Primeiro verde | 100.000 | grama, musgo, lagos, plantas · mensagem de fim do MVP |

- O Ti do Árido saiu do simulador: com o chute de 2.500 o casual chegava em ~5 min; com **6.500** chegava em 8m15s–8m24s (meta: 8 a 12 min). M4: com as rochas a mais (`SMALL_ROCK_CHANCE` 0,019) subiu pra **7.000** (casual ~8m30s); casual fecha em ~35 min (relatório `reports/dev/balanceamento_v04.md`).
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
| `ore_iron.png` `ore_silicon.png` `ore_ice.png` | 32×32 | overlay transparente por cima da parede. **Freela, aprovado pelo dono** (minério bruto chunky: pepitas cor de cobre, lascas grossas de silício, cubos de gelo) |
| `icon_iron.png` `icon_silicon.png` `icon_ice.png` | 16×16 | ícones do inventário/HUD. **Freela, aprovado pelo dono** |
| `pickup_iron.png` `pickup_silicon.png` `pickup_ice.png` | 16×16 | **Freela, aprovado pelo dono** (arquivos copiados junto com o minério; continuam fora do jogo, como antes) |
| `rock_small_{iron,silicon,ice}_{0,1}.png` | 32×32 | rocha com veio (minério bruto), 2 variações por minério. **Freela, aprovado pelo dono.** A variação sai por hash do tile (`(tx·73856093 ^ ty·19349663) & 1`), sem o cristalzinho do `art.ore_fleck()`; sem o PNG cai no jeito antigo (rock_small + fleck). **Ligadas** na superfície e na caverna |
| `{ore,icon,pickup,vein}_magmatite.png`, `rock_small_magmatite_{0,1}.png` | os mesmos tamanhos das outras famílias | **Magmatita** (bíblia §12): basalto escuro com lava só nas fissuras, no visual das pedras do aquecedor. O veio 64×64 tem a lava irradiando de uma poça central. **Aprovado pelo dono.** Tiras de 4 quadros com a lava pulsando em `anim/{ore,vein}_magmatite_anim.png` e `anim/rock_small_magmatite_{0,1}_anim.png` (opcionais, pensadas pra caverna) |
| `rock_small_snowcap_{0,1}.png` | 32×32 | **v0.5 M3.3, aprovado pelo dono.** Neve por cima da rocha pequena na faixa gelada: o jogo desenha logo depois da rocha, no mesmo `(x, y)`, quando o tile da rocha é da região `frost` **na superfície** (na caverna não). Vale pra `rock_small_{iron,silicon,ice}_{0,1}` (a variação é a mesma da rocha: `rock_variant(tx, ty)`; o desenho antigo, sem PNG da rocha, usa a 0). Carregado uma vez no cache do `Sprites` |
| `pod.png` | 64×72 | cápsula/base. **Freela r3d v1.2, sapata B, aprovado pelo dono** |
| `machine_o2.png` `machine_heater.png` `machine_melter.png` | até 40×56 | nível 1. **Freela r3d v1.2, sapata B, aprovado pelo dono** |
| `machine_o2_t2.png` `machine_heater_t2.png` `machine_melter_t2.png` | até 40×64 | nível 2. **Freela r3d v1.2, sapata B, aprovado pelo dono** |
| `terminal.png` | 32×32 | terminal de parede. **Freela r3d v1.2, sapata B, aprovado pelo dono** |
| `vein_iron.png` `vein_silicon.png` `vein_ice.png` | 64×64 | veio 2×2 no chão. Overlay transparente que funciona sobre o chão dos 3 estágios. **Freela, aprovado pelo dono: veio orgânico** (placas achatadas e angulosas encravadas no chão, com pepitas por cima; é o `vein_linha_*` do freela, copiado sem o sufixo) |
| `machine_drill.png` | 256×80 | drill automática: 4 quadros de 64×80 (broca girando), ocupa 2×2 tiles, ancorada no centro da base dos 2×2. **Freela r3d v1.2, sapata B, aprovado pelo dono.** `DRILL_FILL_RECT` novo = `(12, 54, 7, 10)` (o Dev aplica; o atual `(48, 47, 7, 12)` sai) |
| `anim/anim_{machine_o2,machine_heater,machine_melter}{,_t2}.png` | 160×56 / 160×64 | tiras de animação das máquinas (4 quadros de 40 px, na horizontal). **Ligadas**: a máquina trabalhando anima a ~5 fps com fase por tile (hash); parada no quadro 0 se submersa ou sem energia nenhuma; no déficit anda mais devagar (× `power.factor`). Fantasma de colocar e ícones ficam no parado; sem a tira, usa o parado |
| `anim/anim_solar_panel.png` `anim/anim_terminal.png` | 128×40 / 128×32 | tiras de animação (4 quadros). **Ligadas**: o painel solar anima sempre que está em pé (não há noite no jogo); o terminal anima sempre |
| `anim/anim_pod.png` `anim/anim_drone_station.png` | 256×72 | tiras de animação (4 quadros de 64 px). **Ligadas**: a cápsula anima sempre; a estação anima só com drone dentro (e energia) |
| `icon_drill.png` | 16×16 | ícone (estoque de máquinas e fabricador) · **refeito no v0.5 M4 (candidata B, aprovada pelo dono)**: a máquina do `machine_drill` inteira (base com tela e LED verde, mastro, braço, cabeça e feixe no chão) |
| `icon_water_capsule.png` | 16×16 | **v0.5 M2, aprovado pelo dono.** Ícone da cápsula de água (item que sai do derretedor e o Dispersor gasta). Entrou com o Dev D do M2 e só agora está registrado aqui |
| `base_floor_{0..3}.png` | 32×32 | **v0.5 M2, aprovado pelo dono.** Chão da base: chapa de aço azulada, 4 variações, igual nos 3 estágios. Sorteio por hash do tile: `FLOOR_PICK[(tx·73856093 ^ ty·19349663) & 7]` = `(0,0,0,0,1,1,2,3)`. Passada do chão, embaixo de tudo; aceita máquina em cima |
| `base_wall_top.png` | 64×96 | **v0.5 M2, aprovado.** Topo da parede da base no autotile A2 (o mesmo layout do `water_auto`, 47 combinações: `game/autotile.py`). Sobe 24 px (`WALL_LIFT`) por cima do tile; conecta só com parede da base (a porta e a rocha não contam) |
| `base_wall_face.png` | 128×24 | **v0.5 M2, aprovado.** Face da parede, 4 peças de 32×24 (índice = `conn(x−1) + 2·conn(x+1)`), desenhada em `(x, y+8)` quando não há parede da base embaixo |
| `base_door_{h_n,h_s,v_e,v_w}.png` | 128×56 | **v0.5 M2, aprovado (v1.2, variante B).** Porta solo, 4 quadros de 32×56 (0 fechada … 3 aberta) em `(x, y−24)`. O sufixo é a borda de fora da base (oposta ao chão): `h_s` = chão ao norte, `h_n` = chão ao sul, `v_e` = chão a oeste, `v_w` = chão a leste. Colisão: tabela da v1.2 em `BaseGrid.door_rects` |
| `base_door2_{h_n,h_s,v_e,v_w}.png` | 256×56 | **v0.5 M2, aprovado.** Porta dupla (1 item, 2 tiles): metade 1 (oeste/norte) nos quadros 0–3, metade 2 (leste/sul) nos 4–7 |
| `icon_base_{floor,wall,door,door_double}.png` `icon_o2_dispenser.png` | 16×16 | **v0.5 M2, aprovados.** Ícones do menu do construtor |
| `machine_o2_dispenser.png` | 32×48 | **v0.5 M2, aprovado.** Dispersor de O₂ parado (sem água ou sem energia), âncora padrão das máquinas. `anim/anim_machine_o2_dispenser.png` (128×48, 4 quadros, ~6 fps) enquanto "Vedado ✓" e `anim/anim_machine_o2_dispenser_leak.png` (mesmo formato, tira âmbar) no vazamento |
| `icon_{iron_ingot,silicon_wafer,circuit,chip,wire}.png` | 16×16 | **v0.5 M4, aprovados pelo dono no M1.** Ícones das peças de loot (Lingote de ferro, Wafer de silício, Circuito, Chip, Fios). Sem o PNG, quadradinho colorido por código |
| `icon_tab_base.png` | 16×16 | **v0.5 M4, aprovado (cápsula A).** Ícone da aba "Base" do construtor (`FAB_TAB_ICON["base"] = "tab_base"`). Sem ele, o baú |
| `icon_hand_drill.png` | 16×16 | **v0.5 M4, provisório aprovado pelo dono (opção Y: o 1º quadro do `drill_side` reduzido; as R1/R2 da referência dele ficam no report pra voltar depois).** Ícone da broca de mão. Sem ele, o 1º quadro da `drill_side.png` reduzido (`art.hand_drill_icon`) |
| `container_open.png` | 40×44 | **v0.5 M4, aprovado (B).** Contêiner aberto, mesma âncora do `container_sealed.png`. Sem ele, o lacrado escurecido com a tampa aberta (`art.opened_container`) |
| `leak_blink.png` | 64×56 | **v0.5 M2, aprovado.** "Parede-fantasma" vermelha, 2 quadros de 32×56 (aceso, apagado) a ~2,5 Hz em `(x, y−24)` do tile furado, por cima dos objetos e do raio-x |
| `plant_bush.png` `plant_tree.png` `plant_flower.png` | até 32×40 | estágio verde |

### Sprites da superfície do v0.4 · regiões: `assets/sprites/regions/` (proposta da Designer, **aprovado pelo dono, v8.1**; **gelo em blocos aprovado pelo dono, v9.2**; pedra de topo do hoodoo v8.3; **elementos novos e basalto aprovados pelo dono, v9**; **fumarolas aprovadas pelo dono, v9.1**)
Report: `reports/design/regioes/index.html`. Gerados por `tools/sprites/regions_mockups.py` (volumes em `regions_volume.py`, receita do chão em `regions_scene.py`; os elementos da v9 em `regions_v9_elements.py`, prévias e cenas da v9 em `regions_v9.py`).

**PNG indexado (modo P)**, com a paleta do Árido embutida. Índices: 0..7 = rampa da região, 8 = contorno `#1b1630`, 9 = sombra (preto, alfa 80), 255 = transparente. Os outros estágios trocam a paleta pela rampa do estágio em `regions/regions_palettes.json` (`ramps[tabela][região][estágio]`, tabelas `BASE`, `HILL`, `SAND`, `ICE` e `METAL`; v9: `MOSS`, rampa fixa de 4 cores do musgo do Verde+, que não muda com o estágio; v9.1: `VENT`, `ramps.VENT.basalt[estágio]` com 4 cores pros índices 10..13 das fumarolas: 10 e 11 enxofre, que seguem o estágio, 12 e 13 brasa, iguais nos 4 estágios porque emitem luz). O JSON também traz âncoras, tiles que bloqueiam, níveis d'água, a mistura de decalques e, na chave `v9_density`, a densidade dos elementos da v9. **v9.1 (aprovado pelo dono)**: o bloco `smoke` traz os números da fumaça das fumarolas, que é **partícula, não sprite** (`rate` puffs/s por boca: cone 2,5, par 2,0 cada boca, chaminé 3,5; `life` 2,6–3,4 s; `rise` 16–22 px/s freando até ~35%; `radius` 1,5–2,5 px abrindo até 7–10 px; `wind` 0,45 do vento da superfície; `jitter` ±3 px; `color` 3 tons chapados; `alpha` em degraus 150/110/70 por terço da vida; `stage_tint` na Tempestade e na Névoa), desenhada depois dos objetos e antes da HUD. A chave `vent_density` traz quantas por mundo (`count`), onde nascem (`rule`) e quando acordam (`wake`: cada fumarola sorteia um limiar de calor entre o da etapa 1 e o da etapa 4 da tampa da cratera).

| Arquivo | Tamanho | Observação |
|---|---|---|
| `ground_{plateau,salar,basalt,frost,bed}.png` | 512×512 | chão por região (`bed` = leito seco das depressões); emenda nos 4 lados; o tile (tx, ty) usa o recorte `((tx % 16)·32, (ty % 16)·32)`. Rampa `BASE`. v9: o basalto perdeu a célula de fratura retangular (mesmo arquivo e tamanho) |
| `hill_top.png` / `hill_face.png` | 512×512 / 512×24 | topo e face dos morros mineráveis (rampa `HILL` da região). Silhueta por grade dual; a face é a silhueta extrudada 24 px pra baixo |
| `decal_*.png` | variados | decoração de chão (v0.5 M3.3, faixa gelada: `decal_{snowbank,sastrugi,glaze}_{0..2}`, `decal_snowdrift_{0..2}`, `decal_sparkle_{0..3}`; entram por glob, sem código) (não colide, não minera). Rampa `BASE` da região onde cai. v9 (3 variações cada, `_{0..2}`): planalto `vein` e `oxide`, salar `saltpoly` e `efflor`, basalto `fumarole` (respiro apagado) e `ropy`, faixa gelada `icepoly` e `rime` (v0.5 M3.3: o mix da faixa passou a `snowbank`, `sastrugi`, `glaze` e `patch_light` no 1º sorteio, com `decal_p` 0,5, e `snowdrift` e `sparkle` na lista da v9, `decal_p` 0,45; os decalques `icesheet`, `wind` e `gravel` dela saíram do sorteio, os arquivos ficam), leito seco (`bed`) `trail` e `ripples`. Entram num 3º sorteio da célula de 96 px, só com a lista da v9 da região (`v9_density.decal_p` e `decal_mix`) |
| `decor_{shards,salt_crystals,ice_chunks,pebbles,boulder,slabs,salt_mound,salt_slabs,bombs,column_stub,penitentes,rimed_rock,snow_slabs,mud_curls}_{0..2}.png` | até 32×28 | soltos com altura, ancorados no centro da base, ordenados pelo pé, não colidem. Rampa de cada um em `files[...].ramp` (`HILL`, `BASE` ou `ICE` da região do arquivo; seixo no leito seco usa o `HILL` do planalto). v9: planalto seixos, pedra média e lajes; leito seco lascas de lama e seixos; salar montinho de sal e crosta solta; basalto bombas vulcânicas e toco de coluna; faixa gelada penitentes, pedra com geada e, no v0.5 M3.3, `snow_slabs` (lajes de neve; chances 0,010 · 0,010 · 0,006). Chance por tile em `v9_density.decor_p` |
| `decor_{boulder,column_stub}_moss_{0..2}.png` | o tamanho da pedra de mesmo nome e N | **v9 · Verde+**: overlay de musgo desenhado logo depois da pedra de mesmo nome e N (mesmo lugar, mesmo espelho), **só no estágio Verde**. Índices 0..3 = rampa fixa `MOSS`, 8 = contorno |
| `frost_ring.png` | 176×72 | geada no chão em volta do gelo-portão que sublima |
| `form_{monolith,arch,basalt_spires,salt_ridge,cone}.png` | até 208×150 | formações fixas (não mineram, marcos no mapa), ancoradas no centro da base e ordenadas pelo pé. Bloqueiam só os tiles do pé (lista no JSON): hoodoo 1, arco 2 (as pernas; o vão de 3 é andável), basalto colunar 3×2, crosta de sal 5×1, cone 3×2. hoodoo e arco usam a rampa `SAND` |
| `form_{split_rock,salt_pillar,lava_tube,ice_needles}.png` | até 124×72 | **v9 · formações pequenas** (`small: true` no JSON), mesmo esquema das formações (âncora no centro da base, ordem pelo pé, pegada vira `FORMATION`, não mineram, sem afloramento e sem marcador no mapa). Pedra rachada 72×64, 1 tile, `HILL` do planalto; pilar de sal 68×60, 1 tile, `BASE` do salar; tubo de lava colapsado 124×56, 3×1, `HILL` do basalto; agulhas de gelo 84×72, 3×1, `ICE`. Por mundo (`count`): 4–6, 3–4, 2–4 e 3–5 |
| `form_vent_{cone,pair,chimney}_{dormant,active}.png` | 60×48, 72×64, 40×78 | **v9.1 · fumarolas do basalto, aprovado pelo dono** (`formations.vent_*` no JSON, `small: true`): cone baixo bloqueia 1 tile, par de cones 2×1, chaminé 1 tile; âncora no centro de baixo da pegada, ordem pelo pé, pegada vira `FORMATION`, não mineram. `_dormant` (boca escura e fria) abaixo do limiar de calor, `_active` (brasa leve na boca, crosta de enxofre) acima. Paleta 0..9 = `HILL` do basalto, 10..13 = `VENT`. `mouths` = px do sprite de onde sai a fumaça (bloco `smoke`). Por mundo: cone 2–3, par 1–2, chaminé 1–2, no basalto, fora de bacia, a 26+ tiles da base, 8+ uma da outra e 6+ das formações grandes, 60% num raio de 10–30 tiles do cone de escória |
| `form_ice_giant_{larva,cocoon}.png` / `form_ice_giant_{larva,cocoon}_anim.png` / `frost_field.png` | 256×220 / tira 2048×220 (8 quadros de 256×220) / 420×200 | **v0.5 M3.6.2 · gelo gigante da criatura, aprovado pelo dono (Larva em C e Casulo; as outras variações da Designer não entram).** Formação no JSON (`formations.ice_giant`: `foot` [120, 216], pegada de 17 tiles em 7×3, região `frost`, rampa composta **`ICE+ICE_DEEP`**). Índices: 0..7 = `ICE`, 8 contorno, 9 sombra (alfa 80), **10..12 = rampa nova `ICE_DEEP`** (`ramps.ICE_DEEP.frost[estágio]`, 3 cores por estágio: a silhueta presa), 255 transparente. `_anim`: parado no quadro 0, a cada 9–14 s (sorteio) toca os 8 quadros a 6 fps e volta (a "respirada"). `frost_field.png` (indexado, rampa `BASE.frost`): geada grande no chão, centro em (âncora.x, âncora.y − 54). `formations.ice_giant.shards`: 12 estilhaços (blocos `ice_block_*`, quadro = tamanho, pé relativo à âncora), sem colisão. Os `chips` (`decor_ice_chunks`) do contrato não entraram |
| `ice_gate_{0,1,2}.png` | 144×132 | gelo-portão em 3 etapas (M3.2). **Fora do desenho desde o M3.5** (os blocos `ice_block_*` entraram); o arquivo fica, e a caixa 4×2 do `ice_gate_0` no JSON continua sendo o corredor do portão |
| `ice_block_{shard,slab,boulder}_{0,1}.png` | tiras de 8 quadros: lasca 800×117 / 896×131, laje 776×71 / 872×68, pedra 760×84 / 696×90 (quadro = 100×117, 112×131, 97×71, 109×68, 95×84, 87×90) | **v9.2 · gelo em blocos, aprovado pelo dono, promovido**. Rampa `ICE` (`ramps.ICE.frost[estágio]`), 8 quadros = 8 escalas (do inteiro ao último caquinho), âncora e caixa de colisão por quadro no `regions_palettes.json` (chaves `blocks` e `recipes`: receitas A, B e C do portão, derretimento por fração `melt`). Aprovado pelo dono, v9.2; **integrado no M3.5** (§12, "Gelos-portão"): substitui o `ice_gate_*` no desenho |
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
| `ice_crack.wav` `ice_crack_1.wav` | sfx ~1,9 s | **aprovado pelo dono, v11** (gravação). v0.4 M3.1: a tampa de gelo da cratera baixou uma etapa (etapas 1–3, `crater_thaw`). Sorteia entre os dois sem repetir o último. Volume sugerido **0,7**, sem atenuação por distância (aviso global); pitch ±4% opcional |
| `ice_collapse.wav` | sfx ~2,4 s | **aprovado pelo dono, v11** (gravação). A cratera abriu (`crater_thaw` etapa 4) e um gelo-portão abriu (`gate_thaw` etapa 3). Volume sugerido **0,8**; na caverna, 0,5 ou nada |
| `amb_rain.wav` `amb_rain_light.wav` `amb_rain_heavy.wav` | loop 24 s | **aprovado pelo dono, v11** (gravação). v0.4 M3.3: chuva na superfície, no canal 10, com o volume = **0,55** × intensidade da pancada (`rain.rain_level`, 0..1, já com a subida e a descida de 2 s). Uma variação por pancada (média = a principal; fraca ou média no Verde; a forte quando quiser aguaceiro), sorteada pela seed. Para quando a intensidade chega a 0. Na caverna, 0. Sem variar o pitch |
| `vent_hiss.wav` | loop 20 s | **aprovado pelo dono, v11** (gravação). Perto de uma fumarola **acordada** (`layer.vents_awake`): um canal só, pela mais próxima, volume **0,6** × `fade_by_distance(d, 2, 7)` em tiles. Dormente não toca. Só na superfície. Sem variar o pitch |
| `build.wav` | sfx 1,54 s | **aprovado pelo dono, v12.** Máquina colocada com o construtor (scanner varrendo): feixe subindo de tom e clack de trava a ~1,35 s (o Dev ajusta a animação ao clack). Volume **0,55**, pitch 0,97–1,03 |
| `dismantle_charge.wav` | sfx 1,98 s | **aprovado pelo dono, v12.** Enquanto segura o botão direito (2 s), sobe de tom e trêmolo. Canal único; ao soltar, `channel.fadeout(60)` (nunca `stop()` seco). Volume **0,45**, sem variar o pitch |
| `dismantle_done.wav` | sfx 0,55 s | **aprovado pelo dono, v12.** Desmonte concluído e materiais devolvidos; **substitui o `place_low`** no desmonte de máquina. Volume **0,6**, pitch 0,97–1,03 |
| `diagram_read.wav` | sfx 1,24 s | **aprovado pelo dono, v12.** Ler um diagrama na bancada e liberar a receita ("aprendi algo"; mais calmo que o `blueprint_found`). Volume **0,6**, sem variar o pitch |
| `door_open.wav` `door_close.wav` | sfx ~0,75 s | **aprovado pelo dono, v13.1** (porta B, sibilo pneumático). v0.5 M2: a porta começa a abrir / fecha de vez (não toca se já estava no estado). Volume **0,45**, pitch 0,95–1,05, atenuado pela distância (cheio até 3 tiles, some em 12) |
| `base_sealed.wav` | sfx ~2,3 s | **aprovado, v13.1.** A base passou de furada (ou recém-construída) pra vedada. Nunca no carregamento do save; cooldown de 3 s (`SEAL_SOUND_COOLDOWN`). Volume **0,6** |
| `dispenser_hum.wav` | loop 8 s | **aprovado, v13.1.** Canal próprio (13), enquanto o player está dentro de uma base vedada com o Dispersor soprando; entra e sai com fade de 0,8 s (0,3 s quando a água acaba) e **substitui o `machine_hum`** lá dentro. Volume **0,35** |
| `leak_alert.wav` | sfx ~0,9 s | **aprovado, v13.1.** A cada 4 s (`LEAK_ALERT_EVERY`) enquanto a base que já esteve vedada vaza, com o player a até 12 tiles do Dispersor ou do tile furado. Sem variar o pitch. Volume **0,55** |
| `dispenser_dry.wav` | sfx ~1,6 s | **aprovado, v13.1.** Uma vez, quando acaba a última cápsula do Dispersor. Volume **0,5** |
| `container_open.wav` | sfx ~0,31 s | **aprovado pelo dono, v14.3** (gravação CC0 limpa, rubberduck `lock_03`, sem camadas nem reverb: "a mais seca"). v0.5 M4: o E rompeu o lacre do contêiner lacrado e o saque top sai. Uma vez só por contêiner, junto da troca pro sprite de aberto; o `pickup` dos itens entra ~0,8 a 1 s depois. Sem variação de pitch. Volume **0,9** |

Os 7 sons da v11 vêm de gravações livres (CC0, domínio público do NPS e um IR de reverb em **CC BY 4.0**): o crédito obrigatório pra tela de créditos está em `assets/audio/CREDITS.md`. O build deles precisa do pedalboard: `uv run python tools/audio/build_audio.py`.

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
| `chest.png` | 32×40 | baú, ancorado no centro da base · **r3d v1.1, aprovado pelo dono** |
| `chest_open.png` | 32×40 | baú aberto · **r3d v1.1, aprovado pelo dono** |
| `container_sealed.png` | 40×44 | **contêiner lacrado** (v0.4 M3, gancho das peças raras), 1 tile, mesma família do baú (caixa de aço com cintas e selo) · **r3d v1.1, aprovado pelo dono**. Substitui o placeholder `art.sealed_container` quando o Dev integrar |
| `container_open.png` | 40×44 | **contêiner lacrado aberto** (v0.5 M4), mesma caixa, pivô e pé do `container_sealed.png`; tampa meio aberta (forçada), miolo escuro e vazio, cintas cortadas e selo partido. Troca a textura do `C.CONTAINER` depois que o player abre com E · **r3d v1.1, aprovado pelo dono (candidata B)** |
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
| `rock_small.png` | 32×32 | rocha pequena no chão (1 tile, quebrável), contorno `#1b1630`, funciona nos 3 chãos. **Freela, aprovado pelo dono** (rocha sem veio) |
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
| `loot_crate.png` `loot_crate_empty.png` | 32×32 | caixa de saque (fechada/cheia e aberta/vazia) · **r3d v1.1, aprovado pelo dono** |
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
- **Nevasca na faixa gelada (v0.5 M3.7)**: com o player num tile `frost`, a camada da tempestade vira neve (só aparência; vento, rajada, visão e som iguais). Detalhes na nota M3.7 da §13.

## 11. v0.4 · Marco 2: Geografia nova
Plano: `docs/superpowers/plans/2026-10-13-v04-marco2-geografia.md`. Referência visual aprovada: `reports/design/regioes/index.html` (v8.0) e o mapa `mapa_regioes.png`. Cada trilha escreve a sua parte aqui.

### Geração e dados (trilha A · `game/geo.py`, `game/surface_gen.py`; números no bloco `GEO_*` do `game/config.py`)
- **Geografia** (`generate_geo(seed, w, h, base) -> Geo`, numpy, sem pygame): porte do `regions_core.gen_world` da Designer, variando pela seed. Não vai no save: sai igual da seed no load. A camada da superfície expõe `layer.geo` (na caverna é `None`).
  - **Relevo**: altura 0..1 por tile (fbm de 3 oitavas, ~0,52 a 0,72), menos a tigela do salar e 3 depressões pequenas do planalto (raio 6 a 8,5 tiles, a ~25–45 tiles da base, mexidas até 4 tiles pela seed).
  - **Regiões**: **planalto rachado** em volta da base (um raio de 16 tiles em volta dela é sempre planalto e seco), **salar** a leste (elipse de ~29–34 × 22–27 tiles a ~55–64 tiles da base, borda torcida, a maior bacia), **basalto** a oeste e sudoeste (x < ~44 com ruído, y > ~44, alargando pro sudoeste) e a **faixa gelada** na borda norte (no mapa de 192 do v0.4, y < ~24 com ruído; **no 256 do v0.5 M3.6.1 a borda cai a ~50–60 tiles**, `GEO_FROST_Y = (38, 45)` × `sy`). Nas seeds 1, 7 e 42 do v0.4 (192): planalto ~58%, basalto ~22%, faixa gelada ~13%, salar ~6%; no 256 do M3.6.1 a faixa passa a ~22% do mapa (basalto ~21%, salar ~6,5%).
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
- **Cobertura do estágio** (porte do `Scene.cover_layer` da Designer; bug do playtest: o Verde continuava marrom): a **Névoa** ganha manchas de umidade que escurecem o chão (×0,80/0,84/0,90, e a borda de cima ×0,9 a mais) e o **Verde** ganha grama em manchas (fbm de célula de 5 tiles com o domínio deformado por um 2º warp, o da Designer deslocado de +3000/+1700). O limiar da grama depende da classe do chão (planalto 0,47 · salar 0,70 · basalto 0,58 · gelada 0,62 (era 0,48 até o v0.5 M3.3: no Verde a faixa tem que parecer neve derretendo, não gramado) · leito 0,40, em `GROUND_GRASS_THR`) e **cai 0,12 perto da bacia** (mais grama na beira); **no basalto vira musgo** (outra paleta). Borda escura de 1 px, tufinhos de 1×2 px saindo da borda e fios de grama clara (5%). Nada de grama na bacia inteira (onde o lago vai ficar; o lago desenha por cima de qualquer jeito) e **sem exclusão em volta da base**, igual ao design. No design a grama cobre os decalques e as marcas d'água secas. Medido na seed 7: ~58% do planalto vira grama (design: 40–60%), ~28% do basalto, ~52% da faixa gelada, ~0% do salar e do leito. Seed muda as manchas (a seed do mundo entra no ruído).
  - **Como entra no bake**: o chão continua sem cor e sem estágio. Junto do código, cada bloco assa um **mapa de cobertura** de 1 byte por pixel (bits 0..3 = grama 1..5, +6 no musgo; bit 4 = umidade da Névoa; bit 5 = borda dela), igual em todos os estágios, então **nada é reassado na troca de estágio**. Quem decide o que aparece é o `_colorize`, pelo estágio de **cada pixel**: no Verde a grama usa códigos próprios da paleta (82..92, a mesma Surface de 8 bits de sempre, custo ~0); na Névoa a umidade escurece a cor que já está no pixel (RGB, uma vez por bloco). No bloco da mancha da transição cada pixel traz a cobertura do estágio dele (a mancha que avança traz a grama junto, com a mesma borda orgânica do chão). Árido e Tempestade não mostram nada.
  - **"Perto da água"** é a **bacia** (`geo.basin >= 0`, o nível máximo L3, a água do Verde), não o `world.water_level`: o lago sobe várias vezes e nada precisa ser reassado. O mesmo vale pra "não cresce na água": a bacia inteira já fica sem grama, e a Névoa evita só as bacias que alagam até o L2. A dilatação é a da Designer (4 deslocamentos de 2, 5, 9, 14 px nas 4 direções), calculada a cada 2 px e só nos blocos que têm bacia por perto.
  - **Custo**: assar um bloco foi de ~38 pra ~60 ms (o ruído das manchas sai a cada 4 px e é interpolado; mesma faixa de 32 linhas, dentro do orçamento de 3 ms por quadro). Mais 256 KB por bloco na cache (cobertura). Testes em `tests/test_ground_cover.py`; prints do smoke `reports/dev/{verde_cobertura_planalto,verde_cobertura_basalto,verde_cobertura_lago,nevoa_cobertura}.png`.
- **Decoração solta com altura** (não colide, não minera): lascas de basalto, cristais de sal e pedaços de gelo em ~3,5% dos tiles de basalto, salar e faixa gelada, ordenados pelo pé como os outros objetos. Some onde tem máquina, veio, destroço, rocha ou parede.

### Morros orgânicos (trilha C · `game/hills.py`; números no bloco `HILL_*` do `game/config.py`)
- **O que é**: na superfície, os morros mineráveis e a cordilheira da borda perdem o degrau de grade (porte do `regions_scene.hill_layers` da Designer). A colisão e a mineração continuam por tile; só o desenho muda. Grade dual: o campo "tem parede" é interpolado entre os centros dos tiles (bilinear com smoothstep), somado a um ruído de borda e cortado em 0,5. A escada vira diagonal, o canto convexo arredonda e o tile sozinho vira seixo. O topo continua 24 px acima do tile (`hill_top.png`) e a **face** é a silhueta extrudada 24 px pra baixo (`hill_face.png`, estratos e fissuras), com contorno e brilho na borda. Os minérios (`ore_*.png`) vão por cima do topo, recortados pela silhueta; a borda do mapa fica mais escura. Cor da rampa `HILL` da região (`layer.geo`) no estágio. Embaixo do morro vai chão, e a sombra quadrada da parede no chão sai. A caverna usa a mesma geometria pelo `game/cave_rocks.py` (v0.5 M3.4, abaixo); `C.ORGANIC_HILLS = False` volta a superfície pro jeito antigo.
- **Como desenha**: assado em blocos de 8×8 tiles (~3 ms cada), cortado em **uma tira por linha de tiles** (topo + face daquela linha), que entra no `build_draw_list` no lugar das paredes da linha (`("hills", ty)`). Assim o player logo acima do morro fica atrás do topo e logo abaixo fica na frente da face, como antes. Cada bloco guarda a assinatura das paredes em volta e, quando um tile é minerado, **só os blocos que enxergam aquele tile são re-assados** (1, ou 2 na beira). Na troca de estágio o bloco só é recolorido; na mancha da transição a cor vai por tile. O que está na tela é assado na hora e mais 1 bloco da volta por quadro; LRU de 96 blocos. A rachadura da mineração e o fantasma de colocar são os de sempre.
- **Formações** (C3, `hills.FormationSprites`): cada `geo.formations` é um objeto do `build_draw_list` com o sprite `form_<kind>.png` (o gelo-portão, `ice_gate_<variant>.png`) e a `anchor` caindo no `Formation.base_px`. O y da ordem é o do `base_px`, a mesma regra das máquinas: acima do pé o player fica atrás e ganha o raio-x quando a silhueta cobre o corpo. A pegada é `C.FORMATION`, e o vão do arco é andável. O PNG indexado é recolorido pela rampa da formação (`regions_palettes.json → formations[kind].ramp/region`: SAND no hoodoo e no arco, HILL no basalto e no cone, BASE no sal, ICE no gelo) no estágio do tile do pé. A sombra é a que já vem no sprite (índice 9, alfa 80).
- **Cratera de impacto** (C4, `hills.CraterSprites`): na superfície a cratera passa a ser o `crater_impact_<etapa>.png` (168×150, âncora do JSON no centro dos 3×3, ordenado pela borda de baixo dos 3×3) com o `crater_ejecta.png` no chão em volta (depois do chão, antes dos veios); saem o `crater.png`/`crater_ramp.png` da superfície. Colisão 3×3 e E no tile do meio de baixo, como antes. Paleta: 0..9 `BASE` do planalto, 10..17 `ICE`, 18..20 `METAL`, no estágio do tile do meio.
- **Tampa de gelo**: `layer.crater_ice` da superfície, de 0 (tampada) a 4 (`CRATER_ICE_STAGES`, vazia com a rampa exposta); cada etapa é um sprite. Enquanto não chega a 4 o E não desce (`GameState.ramp_blocked`) e a dica vira "Gelo · derrete com o calor" (perto e com o mouse em cima, longe). Subir da caverna nunca trava. Vai no save (`layers.surface.crater_ice`; save v7 sem o campo = tampada). No Marco 2 ficava sempre tampada; no Marco 3 derrete com o calor (§12).
- **Objetivo** "Derreta o gelo da cratera" entra logo antes de "Desça na caverna pela cratera [E]" (completa com a tampa vazia ou já tendo descido). No Marco 2 ele não completa sozinho, então os objetivos seguintes ficam esperando o M3 (ou o F4). **Decisão do dono pro Marco 3:** como o calor só sai do aquecedor, o trio "Minere gelo e fabrique um Derretedor" → "Chegue a Ti 500" → "Fabrique um Aquecedor" sobe pra logo depois de "Fabrique um baú". A ordem fica: baú → Derretedor → Ti 500 → Aquecedor → Derreta o gelo da cratera → Desça na caverna → luminária → destroço → tanque de O₂ → painel solar → …
- **F4 (debug)**: derrete a tampa na hora (etapa 4), no mesmo esquema do F1–F3 (`C.DEBUG_MELT_CRATER`), com o aviso "DEBUG · CRATERA ABERTA (F4)" no topo da tela e a linha nos Controles da pausa. O smoke e os testes que descem na caverna usam o F4 (ou setam o estado).

### Elementos v9 (M3.0 · `game/ground.py`, `game/geo.py`, `game/render.py`; números no `regions_palettes.json → v9_density` e no bloco `GEO_SMALL_FORMATIONS` / `SMALL_FORMATION_*` do `game/config.py`)
- **Decalques v9**: um **3º sorteio** por célula de 96 px (`ground.v9_decals_for_block`), com hash e posição próprios (os da Designer + a seed), só a lista da v9 da classe do tile (leito seco = `bed`) e a chance de `v9_density.decal_p`/`decal_mix`; espelho com 50%. Mesmas exclusões dos outros (6 tiles da base, volta das formações). São colados **depois** dos da v8, no chão assado: continua determinístico e sem cor (troca de estágio só troca a paleta).
- **Soltos v9** (`ground.decor_items_v9`): 1 sorteio por tile com as chances somadas de `v9_density.decor_p` da classe, pé em (tx·32 + 16 ± 7, ty·32 + 26..29), espelho com 50%, ordenados pelo pé como os da v8. Nunca no tile de um solto da v8, nem perto da base ou de formação; no quadro, somem onde tem máquina, veio, destroço, rocha, parede ou formação (`ground.decor_tile_free`, o mesmo filtro dos da v8) e em cima de poça. Rampa pelo `files[...].ramp` do JSON.
- **Musgo (Verde+)**: no estágio Verde do tile do pé, a pedra média e o toco de coluna desenham `decor_<nome>_moss_<N>` logo depois da pedra (mesmo lugar, mesmo espelho), com a rampa fixa `MOSS`. Nos outros estágios a pedra fica limpa.
- **Formações pequenas** (`geo.formations`, `Formation.small`): pedra rachada (4–6, planalto), pilar de sal (3–4, salar), tubo de lava (2–4, basalto) e agulhas de gelo (3–5, faixa gelada). Saem com um gerador próprio depois das grandes e dos bolsões (esses não mudam). Pegada + 2 tiles de folga inteiras na região e fora de bacia (nenhuma no leito seco; o **pilar de sal pode** ficar em bacia, como a crosta de sal, porque o salar é quase todo bacia), a 20+ tiles da base, a 10+ de qualquer outra formação e fora dos bolsões. A pegada vira `C.FORMATION`, o desenho é o do `FormationSprites`, e morro nenhum encosta (3 tiles de folga). Não têm afloramento nem marcador "Formação" no mapa (são miúdas).
- **Save**: continua v7. Tudo sai da seed (o mapa virgem de cada seed ganhou as pegadas novas).

### Mundos com nome e seed (pedido do dono · `game/worlds.py`, tela em `game/title.py`)
- **3 espaços**: `saves/world1.json`, `world2.json`, `world3.json` (o formato do `game/save.py`) e o índice `saves/worlds.json` (`last` = último mundo jogado, `migrated_slot1`).
- **Bloco `world` no save**: `{"name", "seed", "created", "played_s"}`, **sem subir a versão** (continua v7). A seed que gera o mapa é a `seed` da raiz; `world.seed` repete ela e `played_s` repete o `progress.play_time`. Save sem o bloco carrega como "Mundo 1".
- **Migração**: na primeira vez, um `saves/slot1.json` **v7** vira o mundo 1 ("Mundo 1", seed 7) por **cópia**: o `slot1.json` fica intacto como backup e não volta a virar mundo se o mundo 1 for apagado. Um `slot1.json` v1–v6 não migra: o título mostra "Save de uma versão antiga · comece um novo mundo" com Continuar apagado e, quando um mundo é criado, ele vira `slot1.v<N>.json` (sem sobrescrever backup: se já existe, `-2`, `-3`...). Nenhum outro arquivo da pasta é tocado.
- **Título**: **Continuar** (o último mundo jogado; se ele sumiu, o de save mais recente; à direita, nome e tempo de jogo) · **Mundos** · **Sair**.
- **Mundos** (janela B2): os 3 espaços com número, nome, data do último save e "SEED N · ESTÁGIO · X MIN"; vazio = "+ Novo mundo". Enter/clique joga (vazio abre o Novo mundo). **Apagar**: o botão APAGAR (ou X/Delete) arma ("APAGAR DE VEZ? CLIQUE DE NOVO", botão vermelho) e o segundo clique/tecla (ou Enter) apaga; Esc, mexer a seleção ou clicar fora desarma. Save de versão antiga ou estragado num espaço: Enter abre o Novo mundo ali e apagar/criar guarda o arquivo como `worldN.v<N>.json` / `worldN.estragado.json`.
- **Novo mundo**: campo **Nome** (vazio = "Mundo N", até 20 letras, o `TextField` do nome do baú) e **Seed** opcional (até 20). Vazia = a seed **sorteada** ao abrir (1 a 999.999.999), que aparece no próprio campo e fica salva. Só dígitos = o número (acima de 2³¹ dá a volta). Qualquer outro texto = **sha256** do texto (4 bytes, 31 bits): o mesmo texto dá sempre a mesma seed, em qualquer máquina (o `hash()` do Python não serve). "SEED DO MUNDO: N" mostra o resultado antes de criar. Teclado: Tab/setas trocam o campo (W/S são letras aqui), Enter cria, Esc volta. Ao entrar, um aviso "Nome · seed N".
- **A seed vale pra tudo**: `state.seed` gera a superfície (`surface_gen` → `generate_geo`), a caverna, destroços e saque, o clima (`Weather`), a mancha da transição (`StageMap`) e os grãos da poeira (`DustParticles`); o Renderer troca os dois últimos quando a seed do estado muda (`Renderer.use_seed`). A `C.WORLD_SEED` (7) ficou só como padrão do smoke, dos testes e do fundo do título.

## 12. v0.4 · Marco 3: Gelo e água
Plano: `docs/superpowers/plans/2026-10-13-v04-marco3-gelo-agua.md`. O que o calor e a água mudam no mapa sai de **funções puras dos índices** (`game/thaw.py`), que já vão no save e nunca descem: o `GameState._apply_thaw()` sobe as etapas no fim do `_update_machines` (e no F2) e o load só reaplica, sem aviso nem som. Save continua v7. Cada etapa escreve a sua parte aqui.

### Decisões do dono no playtest do Marco 3
- **Sem sal no lago**: sal dissolveria na água, então **por enquanto nenhuma formação de sal nasce** (`GEO_FORMATIONS["salt_ridge"] = (0, 0)`, `GEO_SMALL_FORMATIONS["salt_pillar"] = (0, 0)`, e nenhuma pequena em bacia). A arte (`form_salt_ridge`, `form_salt_pillar`) continua em `assets/` pra quando o salar ganhar outro papel.
- **Sem tubo de lava colapsado** (dono: ficou feio): `GEO_SMALL_FORMATIONS["lava_tube"] = (0, 0)`; a arte fica guardada e o basalto ganha outra formação depois.
- **Sem o respiro de fumarola no chão** (decalque `fumarole` da v9, dono: "a gente já tem a fumarola pra isso"): saiu do sorteio do basalto (`v9_density.decal_mix.basalt` só com `ropy`); o PNG fica em `assets/`.
- **Rocha pequena colide só na base do desenho** (`C.SMALL_ROCK_RECT`, 26×14 px dentro do tile), não no tile inteiro: com o tile todo sólido o player travava no ar, longe da pedra.
- **Contador de desempenho** (F5, ligado por padrão no desenvolvimento): canto de baixo à esquerda, FPS e os ms de trabalho do quadro (média e pior de 0,5 s), verde até 10 ms, amarelo até 14, vermelho acima (`game/perf_meter.py`).
- **Cenário pausado** (o dono marcou no catálogo `reports/design/catalogo_cenario`): `C.SCENERY_PAUSED` tira o desenho sem mudar o sorteio. Hoje: soltos v8 (lascas de basalto, cristais de sal, pedaços de gelo), soltos v9 (seixos, lajes, lama enrolada, montinho de sal, placas de sal) e o decalque cascalho (v8). Pra voltar, é tirar o nome da lista.
- **Sem minério nem decoração no lago**: rocha pequena e afloramento não nascem em bacia, e a decoração solta (v8 e v9) some quando a água cobre o tile.

### Magmatita (decisão do dono · `game/magmatite.py`; números no bloco `MAGMATITE_*` do `game/config.py`)
- **O que é**: mineral novo (`"magmatite"`, "Magmatita"), uma pedra quente de basalto com fissuras de lava. É o que faz as **primeiras máquinas de calor**: entra como **ingrediente na receita do Aquecedor** (nv.1 e nv.2). Depois de colocado, o aquecedor roda sozinho como hoje (não é combustível).
- **Recurso**: entra em `C.RESOURCES` (nome, rótulo `MAGMATITA`, cor laranja-lava **#ff7a2e** / sombra #a8361a nos floaters e chips), no inventário/hotbar/fabricador (`icon_magmatite`), na logística dos drones (Envia/Recebe) e empilha até 50. **Sem veio e sem minério de parede**: os veios (superfície e caverna) e a drill usam `C.VEIN_RESOURCES` (ferro, silício, gelo), então o sorteio dos veios não mudou.
- **Rocha pequena**: tile novo `C.SMALL_MAGMATITE` (16), sprite `rock_small_magmatite_{0,1}` pela mesma variação por hash das outras, quebra em 0,9 s e dá 2–4. No mapa e no minimapa pinta na cor neutra das outras rochas pequenas. As tiras animadas (`anim/`) ficam pra caverna.
- **Onde nasce**: **só perto das fumarolas** (`geo.vents`), num anel de **3 a 5 tiles** (Chebyshev) da caixa da pegada, logo depois do halo de 2 (nunca na pegada nem no `keep_clear`). Segue a regra do reaparecimento das rochas (`rock_respawn.can_spawn`): areia livre, fora de bacia, veio, destroço, cratera e máquina, e com os **8 vizinhos livres** (nunca fecha caminho). Rng próprio (`MAGMATITE_SEED`, por fumarola) e por último no gerador: as rochas, veios e destroços de antes saem iguais.
- **Quanto nasce**: no mapa da seed, **2 a 3 rochas** em volta de cada fumarola (todas nascem dormentes): 2 rochas já dão ≥ 4, o bastante pro 1º Aquecedor (o calor que acorda a fumarola vem dele). Nas seeds 1, 7 e 42: 6 fumarolas e 13–16 rochas no mapa (2 a 5 em volta de cada, contando os anéis que se cruzam).
- **Reaparece**: cada fumarola tem um relógio (`RockRespawn.vent_timers`, vai no save em `rocks.vents`; save sem ele começa do zero). **Dormente**: 1 rocha a cada **120 s** até **3** em volta. **Acordada** (`layer.vents_awake`): 1 a cada **20 s** até **6**. Pode nascer na tela (é a fumarola expelindo), mas nunca no tile do player nem do lado. Rng próprio (`GameState.magma_rng`), fora do teto `ROCK_MAX` das outras rochas.
- **Receita**: Aquecedor **ferro 12 · silício 8 · magmatita 3**; Aquecedor nv.2 **ferro 35 · silício 25 · magmatita 10**.
- **Objetivo novo**, logo antes de "Fabrique um Aquecedor": **"Encontre magmatita no basalto (oeste)"** (completa ao minerar a 1ª magmatita; quem já fabricou um Aquecedor pula). A dica *"Os sensores detectaram calor a oeste. Talvez exista algo por lá pra gerar calor."* aparece quando ele vira o atual, como um cartão da largura do objetivo logo abaixo da coluna da esquerda (barra no laranja do calor, 9 s, uma vez por sessão). O basalto fica a oeste/sudoeste da base (as fumarolas ficam a ~50–90 tiles).
- **Save**: **continua v7**. Inventário/`mined_total` sem a chave = 0; o mapa da seed ganhou as rochas, e uma máquina de save antigo em cima de uma delas fica com areia embaixo.
- **balance_sim**: o simulador vê a magmatita como as outras rochas (superfície). As estratégias da caverna fazem uma ida a pé até a rocha mais perto (`Sim.magma_trip`). Com os números atuais: casual 38–43 min (antes 33–37), cratera do casual ~5m15–5m40 (antes ~5m), caverna/destroços 33–36 min. Só informa (o balanceamento é no Marco 4).
- **Depois (gancho)**: uma **drill nv.2 colocada na fumarola** pra extrair magmatita direto.
- **Arte**: o aquecedor redesenhado (Marco 4) mostra as pedras de magmatita incandescentes numa câmara com janela.
- Prints: `reports/dev/magmatita_{dormente,acordada,objetivo,fabricador}.png`.

### Derretimento da cratera e fumarolas (M3.1 · `game/thaw.py`, `game/smoke.py`; números no bloco `THAW_CRATER_*` / `THAW_FUMAROLE_*`)
- **Cratera**: `thaw.crater_stage(calor)` dá a etapa da tampa (0..4) pelos marcos **200, 450, 750 e 1.000 pK** de calor (`THAW_CRATER_HEAT`, ~4 min de um aquecedor de 4 pK/s; era 40..220, ~1 min, até o M4 por pedido do dono). O `_thaw_crater` sobe `layer.crater_ice` até ela e solta um `("crater_thaw", etapa)` por etapa. **Nunca desce**: o F4 (debug) e um save com etapa maior que o calor continuam valendo. Na etapa 4 o `ramp_blocked` libera e o objetivo "Derreta o gelo da cratera" completa sozinho. O F2 (+3.333 de calor) também abre.
- **Aviso**: no `crater_thaw`, uma pílula no estilo da "RAJADA", só que neutra (barra e cristal de gelo em azul-gelo, texto claro), logo abaixo da coluna do O₂/objetivo (e abaixo da RAJADA se ela estiver na tela), por 3,5 s: **"O gelo da cratera está cedendo"** nas etapas 1–3 e **"A cratera abriu · desça [E]"** na 4. Som `ice_crack` (0,8; sem o arquivo, silêncio).
- **Ordem dos objetivos** (decisão do dono): baú → **Minere gelo e fabrique um Derretedor → Chegue a Ti 500 → Encontre magmatita no basalto (oeste) → Fabrique um Aquecedor** → Derreta o gelo da cratera → Desça na caverna → luminária → destroço → projeto do tanque → tanque de O₂ → painel solar → …
- **Fumarolas** (arte v9.1 aprovada, `form_vent_{cone,pair,chimney}_{dormant,active}.png`): formações pequenas do basalto em `geo.formations` (no fim da lista) e em `geo.vents`. São sorteadas pelo `geo.add_vents` com rng próprio (seed + `THAW_FUMAROLE_SEED`), **depois dos morros** e só no chão livre, então os morros e o resto do mapa saem iguais aos de antes delas. Regra do `vent_density` do JSON: cone 2–3, par 1–2, chaminé 1–2; a pegada + 2 tiles de folga inteiras no basalto, fora de bacia e de morro; a 26+ tiles da base, 8+ uma da outra e 6+ de qualquer formação; 60% tentam primeiro o anel de 10–30 tiles do cone de escória (campo de fumarolas). A pegada vira `FORMATION` (cone e chaminé 1 tile, par 2×1), não minera, sem afloramento e sem marcador no mapa; o halo de 2 tiles entra no `keep_clear` (nada nasce ali). O mundo continua alcançável a pé.
- **Acordar**: `thaw.fumarole_active(calor, i)` liga a fumarola `i` quando o calor passa do limiar dela (`thaw.fumarole_threshold(i)`), espalhado entre o calor da etapa 1 e o da etapa 4 da cratera (`THAW_FUMAROLE_HEAT` = 200..1.000 pK, atrelado à cratera: elas acordam uma a uma entre ~1 e ~4 min de aquecimento) pela sequência de ouro do índice: elas acordam aos poucos enquanto a tampa derrete. Monótona: nunca volta a dormir. O estado fica em `layer.vents_awake` (derivado, não vai no save; na camada porque a geo é dividida entre estados da mesma seed) e o `_thaw_fumaroles` solta `("fumarole_wake", i)`. O App só mostra o aviso **"Uma fumarola acordou com o calor"** (mesma pílula) se ela estiver na tela, e não troca o "A cratera abriu" por ele. Sem som por enquanto.
- **Acordada**: o sprite troca pro `_active` na hora (paleta 0..9 = `HILL` do basalto, 10..13 = `VENT`; a brasa 12–13 é igual nos 4 estágios, o enxofre 10–11 segue o estágio; `hills.ramp("HILL+VENT", ...)`), e liga a **fumaça em partícula** (`game/smoke.py`, padrão do `dust.py`) com os números do bloco `smoke` do JSON: cada boca (`mouths`) solta 2,5 puffs/s (cone), 2,0 (cada boca do par) ou 3,5 (chaminé); vida 2,6–3,4 s; sobe 16–22 px/s freando até ~35%; raio de 1,5–2,5 px abrindo até 7–10 px; tremida de ±3 px; alfa em degraus 150/110/70 por terço da vida (alfa de puffs cruzados é o maior, não a soma); 3 tons chapados puxados 40% pro `stage_tint` na Tempestade e na Névoa. Entorta com o vento do `state.weather`: direção do clima × `THAW_FUMAROLE_WIND` do estágio (34/9/5/7 px/s, até 2× na rajada da tempestade) × 0,45, com o componente norte/sul a 1/4 (`THAW_FUMAROLE_WIND_Y`). Ao acordar, a taxa começa em 1/3 e chega na cheia em 1 s. Só na superfície e só na tela: boca fora da tela (com folga) não solta, e puff que sai da área some (teto de 220). Desenhada depois dos objetos e antes da luz, do clima e da HUD. Custo medido no smoke: ~0 ms.
- **Fumaça mais visível** (M3.5, pedido do dono: no basalto escuro ela sumia; só precisa dar pra ver que a fumarola ficou ativa): `C.SMOKE_OVERRIDE` por cima do bloco `smoke` do JSON (o asset não muda): tons mais claros **#f6f3ee / #d9d3cb / #aaa49d** (antes #e9e4dc / #c4bdb4 / #958e88), alfa **185/135/85** (antes 150/110/70) e vida **3,2–4,2 s** (antes 2,6–3,4: a coluna sobe um pouco mais). Na boca acordada, um **brilho quente bem leve** (`THAW_FUMAROLE_GLOW` laranja, raio 7 px, achatado, somado na tela com intensidade até 56 pulsando devagar entre 60% e 100%, embaixo dos puffs; ao acordar acende junto com a taxa). Print `reports/dev/m35_fumaca.png` (dormente × ativa). Custo: ~0 ms.
- **balance_sim**: a coluna "cratera" registra quando o calor abre a tampa. Na proposta: casual ~6m20s (seeds 1–3), guloso 3m39s–4m31s, variado ~5 min, caverna/destroços 7m30s–8m30s. Só informa (o balanceamento é no Marco 4).

### Gelos-portão (M3.2 e M3.5 · `game/thaw.py`, `game/ice_blocks.py`, `game/geo.py`, `game/layers.py`, `game/systems.py`; números no bloco `THAW_GATE_*` / `WRECK_RICH_*` do `game/config.py`)
- **Em blocos** (M3.5, arte v9.2 aprovada): cada gelo-portão é um **amontoado de blocos de gelo** (3 tipos × 2 variações: lasca, laje e pedra, `ice_block_<tipo>_<n>.png`), arrumados por uma das 3 receitas da Designer (`regions_palettes.json → recipes`): **A** "Muralha" (5 blocos), **B** "Lasca no meio" (4) e **C** "Duas lajes" (3). A receita de cada portão sai da seed do mundo e do índice (`ice_blocks.recipe_for`, `THAW_GATE_RECIPE_SALT`), igual em todo load. O pé de cada bloco fica no `base_px` do portão (centro da borda de baixo da caixa 4×2) mais o `(x, y)` da receita, e a `anchor` do bloco cai nesse pé (o bloco não anda quando encolhe).
- **Derretimento**: `thaw.gate_progress(heat, i)` dá o progresso **p** (0 = inteiro .. 1 = sem gelo), linear no calor entre o 1º e o último marco de `THAW_GATE_HEAT[i]` (pK): portão 0 de **2.800 a 5.800**, portão 1 de **5.800 a 10.200** e o 3º (só quando o mundo tem 3 bolsões) de **14.000 a 22.000** (M4; eram 1.500–3.500 / 3.500–6.500 / 6.000–10.000, abriam rápido demais) (o marco do meio fica só de referência). Os bolsões são numerados da esquerda pra direita e o 0 derrete primeiro. Cada bloco tem a janela `melt = (começa, termina)` da receita: antes de `começa` fica inteiro (quadro 0), entre os dois passa pelos 8 quadros da tira (100% → 23%, quadro `int((p − começa)/(termina − começa)·8)`, o quadro k em `(k·largura, 0)`) e em `termina` some. A colisão encolhe junto: `blocks[tipo].collision[quadro]` é um retângulo no chão relativo ao pé (o caquinho final da lasca 1 não colide).
- **Estado**: tudo **derivado** do calor, nada vai no save (continua v7; o load reconstrói pelo `_apply_thaw`). Na camada da superfície: `gate_melt` (p, só sobe), `gate_recipes`, `gate_blocks` (os `ice_blocks.IceBlock` que ainda existem: tipo, quadro, pé e retângulo) e `gate_ice`, a **etapa derivada**: 0 inteiro, 1 derretendo (fechado) e **3 fresta aberta** (`thaw.gate_stage(p, opens_at)`; a etapa 2 do M3.2 não existe mais). `Layer.refresh_gates` refaz tudo quando o p muda.
- **Colisão por retângulo**: a caixa 4×2 do portão **não é mais `FORMATION`**: é areia, e quem bloqueia são os retângulos dos blocos, que o `GameState.solids_near` devolve junto com as paredes e as máquinas (o mesmo `overlaps` do movimento e do vento). O anel de `BEDROCK` continua inteiro (não dá pra contornar cavando). O `can_place` recusa máquina com algum tile cruzando um bloco (sem gelo, o chão fica livre); minerar não pega nada ali (a caixa é areia e o anel não minera). O mesmo vale pro `keep_clear`: a caixa e o halo continuam fora do que nasce. A "sombra em tiles" do portão fechado é o `world.closed_gate_tiles` (a caixa 4×2 enquanto a fresta não abriu): o `reachable_from` trata como parede e o mapa do scanner pinta como pegada de formação.
- **Fresta**: abre quando os retângulos deixam a **caixa do player (14×8)** passar do avental pro bolsão, medido pela mesma busca pixel a pixel da Designer (`ice_blocks.passable`, flood fill em numpy no corredor de 4 tiles). O `ice_blocks.opens_at(receita)` acha o p exato (só testa os p em que algum bloco troca de quadro): **A 0,5975 · B 0,57 · C 0,575** (a Designer mediu 0,60 / 0,57 / 0,58 com passo de 0,01). No jogo (números do M4), o portão 0 abre a fresta com ~4.600 pK (A), ~4.500 (B) ou ~4.500 (C), e o resto do gelo continua derretendo até p = 1. Teste: o player anda de verdade pela fresta (o `Player.move` com o `solids_near` do jogo) nas 3 receitas.
- **Desenho**: cada bloco é um objeto próprio do `build_draw_list` (entra no `visible_formations` com o pé dele), então o player passa na frente de um e atrás do outro, e o raio-x acende quando um bloco da frente cobre o corpo, como nas formações. Recolorido pela rampa `ICE` da faixa gelada no estágio do tile do pé do portão (`hills.IceBlockSprites`, cache por tipo, quadro e estágio; a sombra vem no sprite; sem a arte, um bloco chapado azul-gelo). O `ice_gate_0..2.png` saiu do desenho (os arquivos ficam em `assets/`; a caixa 4×2 do `ice_gate_0` continua sendo a do corredor). Com **p > 0**, o `frost_ring.png` (rampa `BASE` da faixa gelada) vai no chão, na camada de decalques, centrado no pé do portão e 60 px acima dele.
- **Evento**: `("gate_thaw", i, 1)` quando o gelo começa a derreter e `("gate_thaw", i, 3)` **quando a fresta abre** (os dois em ordem se o calor pular direto). No 3 aparece o aviso neutro **"Um gelo-portão abriu ao norte"** (4 s, no topo), toca o `ice_collapse` (0,8) e o mapa do scanner tira a caixa fechada. Prints: `reports/dev/m35_gelo_blocos_{0,50,fresta,aberto}.png`.
- **Dica** (pedido do dono): com o mouse em cima do gelo (a caixa do portão e uns 5 tiles pra cima), o canto mostra **"Gelo-portão · a passagem abre com ~N pK (agora X)"**, onde N é o calor em que a fresta abre na receita daquele portão. Na cratera tampada: **"Gelo · derrete com o calor · abre com 1.000 pK (agora X)"**.
- **Mapa**: o marcador do portão continua; o tooltip diz **"fecha a passagem · gelo"**, **"derretendo · N%"** (o p) ou **"aberto · passagem livre"** (com a fresta).
- **Destroço rico**: no `wreck_spot` de cada bolsão vai uma **nave de carga** (`WRECK_RICH_KIND`) com o saque `WRECK_RICH_LOOT`: ferro 30–40, silício 20–28, gelo 14–20 (sempre mais do que a melhor nave de fora). Se algum projeto de `BLUEPRINTS` não caiu nos destroços de fora, cada destroço rico traz um dos que faltam, na ordem. Ele é gerado com a superfície (seed), fica em `world.wrecks` **depois** dos de fora (`rich=True`, rank a partir de n), e a caixa salva igual às outras.
- **Contêiner lacrado** (gancho das peças raras do v0.5): tile novo `C.CONTAINER` (15, sólido baixo, não minera, não é parede) no `container_spot` de cada bolsão (`world.containers`). *(v0.5 M4: agora abre, ver "Marco 4" na seção 13; a dica de lore saiu.)* Longe, com o mouse em cima: "Contêiner lacrado · chegue mais perto". Desenho: o `container_sealed.png` da Designer (r3d v1.1, 40×44, aprovado), com o pé no centro de baixo do tile, como as máquinas de 40 px (M3.5). O placeholder por código (`art.sealed_container`, 32×40) fica só de fallback sem a arte. Quando é visto, vira o marcador **"Contêiner"** no mapa e no minimapa (pictograma próprio, sem chip de filtro). O tooltip do gelo-portão no mapa passa a dizer "fecha a passagem", "derretendo" ou "aberto".

### Chuva e lagos (M3.3 · `game/thaw.py`, `game/world.py`, `game/rain.py`; números no bloco `LAKE_*` / `RAIN_*` do `game/config.py`)
- **Nível d'água** (`thaw.lake_level(water)`): o índice de água (ppm) vira uma altura na escala do `geo.height`. Abaixo de **2.500** é seco; em **2.500 / 7.000 / 15.000** (M4; eram 3.000 / 15.000 / 40.000) é exatamente **L1 / L2 / L3** (0,19 · 0,29 · 0,385) e entre eles interpola linear; acima de 15.000 fica em L3. Monótona. Só vale **da Névoa em diante** (antes disso o lago não sobe, mesmo com água no índice).
- **`layer.water_level`** (mora no `World`, derivado, não vai no save): o `_thaw_lake` só sobe o nível (nunca desce) e em degraus de **0,004** de altura (o render e o mapa refazem a água poucas vezes por minuto), mas cada marca é batida exata e solta o evento **`("lake_rise", k)`** uma vez (k = 0, 1, 2 pra L1, L2, L3).
- **Água = bacia abaixo do nível**: com geo, `is_water` é `geo.height < water_level` num tile de chão (ou de rocha pequena, que fica com o pé na água). O estágio não entra e não tem nada aleatório: a água enche **das partes mais fundas pra fora** (o fundo do salar, ~0,03, antes do fundo das depressões do planalto, ~0,11) e nunca sai de uma bacia (o nível para em L3). O `lowness` e a suavização antiga saem da superfície (continuam só no `World` sem geo, dos testes; a caverna nunca terraforma). Ficam secos: veio, destroço, a **crosta de sal** (`salt_ridge`, `FORMATION`, que vira **ilhota**) e a **base** (o raio de 16 tiles está sempre acima de L3).
- **Lago futuro** (`world.future_water`): com geo é o chão de bacia. A rocha que reaparece e as plantas não nascem nele.
- **Desenho**: por cima do chão assado (o leito seco e as marcas d'água da trilha B ficam por baixo). No mapa (M) e no minimapa a água continua por tile, pintada de azul (`minimap.WATER_COLOR`) e, quando o nível sobe, só as bacias já vistas são repintadas.
- **Margem orgânica** (M3.5 · `game/lake.py`; números no bloco `LAKE_BLOCK_TILES` / `LAKE_BAKE_MS` / `LAKE_CACHE_BLOCKS`): a silhueta da água segue o `geo.height` contínuo em vez da escadinha do autotile. É a mesma grade dual dos morros e das marcas d'água secas (`ground.smooth_sample`): o campo por tile é o `height` nos tiles que podem alagar (chão e rocha pequena, sem veio) e alto no resto (morro, veio, formação, cratera, destroço: a água contorna em curva, como ilhota), interpolado entre os **centros** dos tiles com smoothstep, e o pixel é água onde o campo fica abaixo do `water_level`. **Regra desenho × jogo**: no centro de cada tile o campo vale exatamente o `height` do tile, então **o pixel do centro é água ⇔ `is_water` do tile** (teste em todas as bacias, nos 3 níveis); entre os centros a margem corre suave. A colisão, o `can_place` e a máquina submersa continuam por tile: é só desenho.
  - **Visual**: o miolo é o tile de água cheia do atlas A2 do estágio (a mesma textura de antes, presa na grade do mundo) com os 2 reflexos de cada tile andando como antes, presos no trecho de água funda da linha. Na margem, as cores do próprio atlas: pra dentro, 2 px de sombra azul-escura (margem de cima e dos lados) ou de **espuma** (margem de baixo, onde a terra está logo embaixo); pra fora, 2 px de barranco marrom e 1 px de barranco claro, acompanhando a curva.
  - **Como desenha**: assada em blocos de **8×8 tiles** (256 px) como código sem cor (numpy, ~2 ms por bloco) e colorida por estágio numa Surface opaca com colorkey (1 blit por bloco; na transição a cor vai pelo estágio de cada tile). Refeita só quando o `water_level` muda, quando os tiles da janela do bloco mudam (assinatura, como os morros) ou, só a cor, na troca de estágio. Até **2 ms por quadro** (no mínimo 1 bloco), primeiro o que está na tela e de folga 1 bloco da volta; enquanto o bloco novo não fica pronto, o anterior (nível velho) continua na tela, e bloco nunca assado cai no autotile por tile. Sem nenhum bloco pronto na tela (teleporte, load), assa a tela toda na hora. LRU de 64 blocos. Bloco sem bacia na janela não custa nada.
  - **Custo** (smoke, zoom 0,75, andando na margem do salar em L2): por tile 6,5 ms → orgânico 5,4 ms (−1,1 ms: 1 blit por bloco no lugar de ~1 blit e 9 consultas por tile). Média do smoke inteiro: 5,5 → 5,6 ms (o passeio novo de comparação entra na média).
- **Plantas na beira d'água** (Verde, com geo): **30%** de chance num tile de chão a até **3 tiles** (num quadrado) de uma bacia, **5%** longe dela, nenhuma dentro da bacia. Na seed 7: 27% na beira, 5% longe.
- **Chuva** (`game/rain.py`, `state.rain`, determinística pela seed, não vai no save): pancadas no estilo das rajadas. A 1ª vem **15–40 s** depois de entrar na Névoa; na **Névoa**, **30–60 s** de chuva a cada **60–120 s** (de começo a começo); no **Verde**, **15–30 s** a cada 60–120 s. Intensidade 0..1 com **2 s** de subida e de descida. Pancada nova só da Névoa em diante; o evento `("rain", True)` sai no começo de cada uma. **Só na superfície** (`rain.rain_level(state)` dá 0 na caverna; o relógio continua lá em cima).
- **Chuva na tela** (`RainDrops`, depois do clima do estágio e antes da poeira e da HUD): até **300 traços** com a chuva cheia (proporcional à intensidade), caindo a 620 px/s e tortos pro lado do vento (`state.weather.wind`, a componente x × 0,45), presos à câmera (espaço de dobra com módulo da visão, o padrão dos grãos do `dust.py`), traço de 10–18 px com a cauda sumindo, mais um véu frio leve (multiplicação, até −34). Custo medido no smoke: +0,2 ms no zoom 1× e +0,3 ms no 0,75×. A chuvinha fina de sempre da Névoa (`_draw_weather`) continua por baixo.
- **Som**: `amb_rain` em loop com o volume = intensidade. Ver §6.
- **Fora daqui (M3.4)**: máquina submersa e "não constrói na água". O player continua andando na água rasa.

### Máquina submersa (M3.4 · `game/systems.py`, `game/render.py`, `game/app.py`, `game/drones.py`)
- **Não constrói na água**: o `can_place` recusa se qualquer tile da máquina é água (`world.is_water` com o estágio do jogo; com geo o estágio não entra, igual ao render). O fantasma de colocar fica vermelho em cima do lago.
- **Alaga depois**: dá pra construir no leito seco de uma bacia. Quando o lago sobe, o `_thaw_submerged` (chamado no `_apply_thaw` depois do `_thaw_lake`) marca `m.submerged = True` em toda máquina da superfície com algum tile na água e solta **`("submerged", kind, (tx, ty))`** uma vez por máquina (o lago nunca desce, então ela nunca "seca"). `submerged` é **derivado**: não vai no save (continua v7) e o load refaz pelo nível, sem aviso. A base nunca alaga (raio 16 sempre acima de L3) e a caverna não tem água. Veio fica seco (ilhota), então na prática a drill não alaga; a regra vale pra ela mesmo assim.
- **Parada**: a submersa sai do `working_machines`: não soma índice nem Ti/s, não gera nem consome energia (o painel solar para também), a drill não cava e a estação não manda drone (os pousados ficam no pad; os que estavam voando terminam a viagem e voltam). Também não solta "+O2", não acende e não pisca o raio de sem-energia.
- **Recolher**: desmontar funciona normal (clique direito, volta pro inventário). O E continua abrindo baú/drill/estação submersos, pra tirar o que estava dentro.
- **Desenho**: só a metade de cima da silhueta (o corte é na metade da caixa opaca do sprite, que fica no mesmo lugar), as 3 últimas linhas no tom `water_d` da paleta do estágio e a **linha d'água** em `foam` por cima do corte, 2 px mais larga que a máquina de cada lado, com 1 px de `water_d` embaixo. Sprite parado (drill no quadro 0, sem a animação de ligada) e sem luz. Embaixo do corte aparece o tile de água do chão. Fica no cache por tipo, lado e estágio.
- **Aviso** (a pílula neutra do degelo): **"Gerador de O₂ submerso · recolha [Clique direito]"** (concorda com o nome: "Luminária submersa", "Estação de drones submersa"; `C.MACHINE_FEMININE`). Se outra alagar enquanto o aviso está na tela, vira **"3 máquinas submersas · recolha [Clique direito]"**. Sem som.
- **Dica do mouse**: "Submersa · [Clique direito] recolher" (longe: "Submersa · chegue mais perto pra recolher"); no alvo do E, "Submersa · [E] Abrir baú…".
- O player continua andando na água rasa (rever no playtest do Marco 4).

## 13. Escopo do v0.5: "base e expedição"
Design completo em `docs/superpowers/specs/2026-10-14-v05-base-e-expedicao-design.md` (aprovado pelo dono em 2026-10-14). Em resumo:
- **Construtor** é o único jeito de colocar máquina (luz de scanner construindo). **Desmontar** = segurar o botão direito 2 s, devolve os materiais da receita; o clique rápido não faz nada.
- **Fabricador da nave = bancada T1** (só itens básicos). Ela fabrica o diagrama da **Bancada T2**, construída onde quiser, com as receitas avançadas.
- **Diagrama** substitui o projeto: item lido na bancada.
- **Mochila**: equipamento, +1 linha de slots.
- **Base respirável**: chão, parede e porta; base fechada (≥ 9 tiles de chão, ≥ 1 porta) com **Dispersor de O₂** dentro, gastando **cápsula de água** (sai do derretedor).
- Itens novos (lingote de ferro, cápsula de água, wafer, circuito, chip, fios, diagrama); fora a cápsula, só loot no v0.5.
- Mapa **256×256** (save v10, novo jogo obrigatório), faixa gelada como região de verdade (chão de neve azul, minério de gelo facetado, veio de gelo só no gelo), blocos orgânicos dentro da cratera (motor dos morros), fumarola garantida perto da cápsula, criatura no gelo gigante (Larva em C ou Casulo, sorteado pela seed), broca de mão nv.1/nv.2.

### Marco 2 · Base respirável (`game/base.py`, `game/systems.py`; números provisórios no bloco `BASE_*` / `DISPENSER_*` do `game/config.py`)
- **Blocos do construtor** (aba "Base" do menu, receitas baratas em `BASE_COST`): `base_floor` (chão, 1 ferro), `base_wall`, `base_door` (solo) e `base_door2` (dupla: **1 item que ocupa 2 tiles**, o R gira h ↔ v, a âncora é a metade de oeste/norte; desmontar qualquer metade tira as duas e devolve 1 receita). Moram no `Layer.base` (`BaseGrid`), não na lista de máquinas; 1 bloco por tile. Constroem na hora (sem scanner), e desmontar segue o fluxo do M1 (segurar o botão direito 2 s, devolve a receita; a máquina em cima do chão tem prioridade no mouse).
- **Parede** alta (24 px, mesma geometria da rocha), autotile A2 que conecta só com parede da base (a porta não conta no desenho, a rocha nunca), face quando não tem parede da base embaixo, entra na ordem de profundidade com `ay = ty·32 + 1`. Parede e porta fechada/abrindo (quadros 0–1) contam no raio-x. O chão aceita máquina em cima; parede e porta não aceitam máquina e não podem prender o player.
- **Portas** abrem sozinhas com o player a até 1,5 tile de qualquer tile delas (4 quadros a ~12 fps, fica aberta enquanto ele estiver perto). Orientação e borda de fora (variante B) saem dos vizinhos: a folha vai na face oposta ao chão da base. Colisão pela tabela da v1.2 (`BaseGrid.door_rects`).
- **Vedação** (flood fill a partir do tile do Dispersor, só por chão da base, vizinhança de 4): cada vizinho é chão (entra), parede ou porta (muro) ou vazamento (guarda o primeiro e para). Vale com **≥ 9 tiles de chão, ≥ 1 porta e ≤ 200 tiles** (`BASE_MIN_FLOOR`, `BASE_MIN_DOORS`, `BASE_MAX_FLOOR`). A porta, aberta ou fechada, conta como muro. Resultado em cache por Dispersor (`Machine.seal`) e recalculado só quando um bloco muda dentro dos tiles que o flood fill examinou (`BaseGrid.changed_near`) ou quando o Dispersor entra ou sai; nunca por frame, e nunca salvo (o load recalcula, sem som).
- **Dispersor de O₂** (`o2_dispenser`): 1 slot de cápsula de água, **1 kW** na rede, gasta 1 cápsula a cada `DISPENSER_CAPSULE_TIME` (provisório: 3 min) só com a base vedada e ligado; a cápsula sai do slot quando começa a queimar (`Machine.burn`, vai no save). Estados (painel e em cima da máquina): "Vedado ✓" (sprite soprando), "Vazamento" (tira âmbar; o tile furado pisca com o `leak_blink`), "Sem água" e "Sem energia" (parado), mais "Base pequena", "Sem porta", "Base grande" e "Sem chão" quando a base não vale por outro motivo. Prioridade: sem energia > geometria > sem água > vedado. Dentro da base vedada e com o Dispersor soprando, o O₂ recarrega igual à zona da cápsula (`GameState.in_sealed_base`).
- **Sons**: porta (`door_open`/`door_close`), `base_sealed` na transição pra vedada (nunca no load, cooldown de 3 s), `dispenser_hum` em loop dentro da base vedada (no lugar do `machine_hum`), `leak_alert` a cada 4 s enquanto vaza (só base que já esteve vedada, player a até 12 tiles) e `dispenser_dry` uma vez quando a água acaba.
- **Derretedor com inventário** (Dev D do M2): 2 slots, **entra gelo** (slot 0) e **sai cápsula de água** (slot 1); gasta `MELTER_ICE_PER_CAPSULE` (2) de gelo a cada `MELTER_CAPSULE_TIME` (20 s no nv.1 e **10 s no T2, 2× mais rápido**) e não gasta gelo com a saída cheia. Continua terraformando como sempre. **Os drones só tiram** (Envia a cápsula; o derretedor não recebe nada deles) e levam pros baús. A cápsula é um item que empilha como máquina e só sai do derretedor (sem receita).
- **Save v9**: os blocos de cada camada em `"base"` (a dupla como 1 objeto, com âncora e orientação) e o Dispersor com o inventário (`storage`), `burn` e `sealed_once`. Migração v8 → v9 sem conversão (sem base).

### Marco 3 · como ficou na implementação
**M3.1 · Mapa 256 + F3 revela o mapa** (`SURFACE_W/H` no `game/config.py`; nenhum `192` cravado: trocar a constante basta pra crescer de novo)
- **Proporcional ao tamanho do mapa**: as regiões do `game/geo.py` (salar, basalto, faixa gelada, bacias) escalam por `SURFACE/GEO_REF_SIZE` (`GEO_REF_SIZE = 192`, o tamanho pro qual os números `GEO_*` foram ajustados); `TRANSITION_FRONT_FAR` (a mancha da transição chega nas bordas); contagem dos **morros** (`HILLS` × `SURFACE_AREA_SCALE`, ~46–60); **teto de rochas** `ROCK_MAX` (700 × a área, 1244: as rochas pequenas já são por tile, ~1.100 no mapa; sem isso o reaparecimento desligava).
- **Absoluto, de propósito** (o mapa cresce na borda, não no miolo): cratera a 15–20 da base, formações (26+), veios a 35+ e **no máximo 88** da base (`SURFACE_VEIN_MAX_DIST`, o alcance do mapa antigo: sem esse teto o casual do simulador de balanceamento foi de ~50 pra ~55 min), destroços a 30–84 (`WRECK_DIST`, e a mesma contagem de 6–8). Consequência: a borda nova (além de ~90 tiles da base) é só deserto, morros, rochas pequenas e as regiões; os destroços e veios não chegam lá. Contagem de formações e destroços fica pro balanceamento.
- **Save v10**: a mesma seed gera outro mundo, então o v7–v9 viram "save antigo" (aviso + backup `.v<N>.json`, sem migrar). `MIGRATIONS` ficou vazio.
- **F3**: `state.fast` também faz o mapa (M) e o minimapa mostrarem a camada inteira. `game/explore.py` (`view_of`/`REVEALED_ALL`) responde "tudo visto" pros marcadores (veio, destroço, cratera, formação...) e o `game/minimap.py` pinta uma textura separada da camada toda (guardada e acompanhando a mineração). O `Explored` nunca é tocado: desligar o F3 volta a névoa igual, e o save não muda. Continua exigindo o scanner. O "DEBUG · RAPIDO..." do topo ganhou "· MAPA REVELADO".


**M3.3 · Faixa gelada** (arte aprovada pelo dono, proposta A do minério; `game/render.py`, `game/surface_gen.py`, `game/config.py`)
- **Arte integrada** (`assets/sprites/` e `regions/`): chão `ground_frost`, rampas `BASE.frost`/`HILL.frost` novas, decalques `snowbank`/`sastrugi`/`glaze` (1º sorteio) e `snowdrift`/`sparkle` (v9), soltos `rimed_rock` refeito e `snow_slabs` novo, minério/veio/ícone/pickup do gelo facetado e `rock_small_snowcap_{0,1}`. O `regions_palettes.json` do pendente entrou inteiro (o do jogo não tinha nenhuma mudança fora dele). Decalques e soltos entram por glob; o `snow_slabs` usa a âncora padrão (centro de baixo).
- **Neve na rocha pequena**: o `draw_small_rock` desenha o `rock_small_snowcap_{v}` logo depois da rocha, no mesmo `(x, y)`, quando o tile é da região `frost` e o mundo tem geo (superfície; a caverna não tem).
- **Grama**: `GROUND_GRASS_THR` da classe gelada 0,48 → 0,62.
- **Veio de gelo só na faixa gelada**: os 4 tiles do veio de **gelo** da superfície ficam na região `frost`; ferro e silício continuam em qualquer areia aberta (teto de 88). A faixa começa a ~95 tiles da base (no mapa 256 ela é a tira do norte), então o gelo ganhou o próprio teto, `SURFACE_ICE_VEIN_MAX_DIST = 120` (a metade do mapa − 8), e o gerador sorteia entre os cantos válidos da faixa em vez de tentar às cegas. Toda seed testada (1–200) tem pelo menos 1 veio de gelo (com teto de 110, as seeds 9 e 98 ficavam sem). O `VEINS_NEAR_BASE`/`VEINS_FAR_*` é da caverna (`world.py`) e não mudou.
- **Fora do escopo, por decisão do dono**: aumentar a faixa gelada (fica pra outra versão). **Balanceamento** do gelo mais longe fica pra rodada de balanceamento.

**M3.4 · Cratera orgânica** (`game/cave_rocks.py`, `game/render.py`; `C.ORGANIC_CAVE = False` volta a rocha quadrada)
- Os blocos de rocha da **caverna** ganham as bordas curvas dos morros. **Só o desenho muda**: geração, tiles, colisão e minérios da caverna são os mesmos. O `hills.py` **não mudou**: o `cave_rocks.py` importa dele a geometria pura (`bake_block`, `window_bounds`, `tile_window`, `edge_noise`, `colorize_block`) e tem o que é da caverna (cor, cache, rebake). Outro planeta no futuro vira mais um módulo desses.
- **Cor**: uma rampa só (sem regiões nem estágios), montada com as cores que a rocha da caverna já tinha (`PALETTES` do estágio névoa, as dos `wall_mist_*.png`/`wall_face_mist.png`); o único tom novo é a média de `rock_dot` e `rock`. Sem arte nova.
- **Cache**: blocos de 8×8 tiles em tiras por linha, no `build_draw_list` no lugar das paredes da linha (raio-x e ordem iguais). Minerar re-assa só os blocos que enxergam o tile (1, ou 2 na beira). O terminal continua desenhado na face, depois da tira da linha dele.
- **Luz**: nada a mudar: a escuridão e o brilho dos minérios são passes por cima do quadro, depois das paredes. Com morro orgânico a sombra quadrada da parede no chão sai, como na superfície.

**M3.6.1 · Faixa gelada maior** (pedido do dono: mais ou menos o dobro; `game/config.py`, `game/geo.py` sem mudança de código)
- `GEO_FROST_Y` de `(22, 26)` pra **`(38, 45)`** (unidade do mapa de referência 192, continua × `sy = h / GEO_REF_SIZE`): no mapa 256 a borda da faixa cai a **y ≈ 50–60 tiles** (era ~29–35), com o mesmo ruído de borda (±8 tiles). Medido em 200 seeds na fatia do meio: borda em y 47–61 (média 55; antes 26–38, média 31,5). Faixa de ~13% pra ~22% do mapa.
- **Prioridade das regiões intacta**: o gelo continua ganhando do basalto e do salar (só perde o canto noroeste do basalto, ~25 linhas); o raio de planalto de 16 tiles em volta da base segue planalto e seco, e a cratera segue a 15–20 tiles. Bolsões e gelos-portão (2 ou 3, nas linhas 0–~16) continuam nascendo em toda seed. As formações do norte (agulhas de gelo etc.) simplesmente caem na faixa nova; as grandes de outras regiões que caíam onde agora é gelo são sorteadas de novo (o gerador já exige a pegada inteira na região certa).
- **Veio de gelo** (`SURFACE_ICE_VEIN_MAX_DIST = 120`, não mudou): 1+ por seed em 200 seeds; distância à base: antes mín 91,5 · média 108,7 · máx 120,0; depois mín 65,8 · média 98,0 · máx 119,7.
- **Balanceamento fica pra depois**: nenhum limite de teste mexeu (pytest passou sem tocar no `test_balance_sim`). Só mudaram o teto de y da faixa em `test_geo.py` (era `< 40`, agora `< 72`) e o piso da umidade em `test_ground_cover.py` (0,15 → 0,10: o 1º bloco de planalto é outro agora). Print `reports/dev/faixa_gelada_antes_depois.png`.

**M3.6.2 · Bolsão grande da criatura + gelo gigante** (`game/geo.py · _giant_pocket`, `game/ice_giant.py`, `game/surface_gen.py`, `game/hills.py`, `game/render.py`; números no bloco `GIANT_*` do `game/config.py`; arte da Designer em `formations.ice_giant` do `regions_palettes.json`)
- **Bolsão**: 1 por mundo, **lugar sorteado pela seed dentro da faixa gelada** (gerador próprio, `[seed, 2026, 62]`, depois das formações grandes e antes das pequenas: o resto da geografia não muda). **Forma orgânica (pedido do dono, "menos quadradão")**, não retângulo: o interior é um morro (`_hill_shape` + `_tidy` da receita dos morros orgânicos, esticado pra caixa 17×13) com o retângulo do gelo + 3 tiles de corredor forçado dentro; o anel de `BEDROCK` é o interior dilatado 2 tiles em todas as direções (quina inclusa), então tem **espessura ≥ 2 em qualquer ponto, é contínuo (sem fresta nem pela diagonal)** e acompanha a curva. Tamanho de fora ≈ 21×16 (área parecida com a do retângulo de 19×15 de antes, que era 285 tiles). Cai em qualquer lugar da faixa, do meio a um canto e colado na cordilheira (200 seeds: x de 3 a 234, y de 1 a 41; 20 delas a ≤ 4 tiles de uma borda). Regras do sorteio: tudo (interior, anel, entrada e avental) na região `frost` e fora de bacia, a `GIANT_GAP = 3` tiles dos bolsões de hoje e das formações, a 40+ da base; se o sorteio livre falhar (1500 tentativas) varre a faixa toda, então existe em toda seed. Os bolsões dos gelos-portão (2–3) continuam iguais (número, ordem de derretimento, conteúdo). Veios, morros, destroços e rochas respeitam o bolsão inteiro (`keep_clear`).
- **Entrada**: 8 tiles de largura × 2 de altura (a espessura do anel) no **fundo** (virada pra fora da cordilheira, que é ao norte), com o deslocamento sorteado em ±1 do centro. Como o fundo é curvo, o chão do interior é esticado pra baixo nas 8 colunas do vão (fundo reto): assim o vão do anel é sempre um **retângulo reto** e o portão de blocos da 6.3 encaixa. **Aberta por enquanto** (areia, o player entra e sai). Fica em `geo.giant.entry` (os tiles), `geo.giant.entry_rect` (x, y, largura, altura em tiles) e `geo.giant.side` (`"s"`): a 6.3 fecha o vão com o portão grande a partir daí. Na frente, um avental livre de 4 linhas (`GIANT_APRON`).
- **Gelo gigante** (formação `ice_giant`, última de `geo.formations`, então os índices das outras não mudam): no meio da caixa do interior, **pelo menos 3 tiles de corredor livre em volta em todo ponto da pegada** (testado). Pegada de 7×3 tiles (17 tiles, `FORMATION`: colide, não minera); desenhado pelo pé como as outras formações (raio-x igual), recolorido por estágio (`ICE+ICE_DEEP`). Respira (`ice_giant.Breath`, quadro 0 parado, 9–14 s entre respiradas, tira a 6 fps, por seed), com 12 estilhaços sem colisão em volta e a geada grande (`frost_field`) no chão. **Teaser: sem interação.**
- **Criatura**: sorteio pela seed entre **Larva em C** e **Casulo** (`C.GIANT_VARIANTS`, `GIANT_SALT`; 200 seeds: 110 larvas, 90 casulos). O estado fica em **`geo.giant.creature`** (`IceCreature`: `variant`, `tile`, `trapped = True`), o gancho do futuro (um dia ela derrete e foge pra caverna). Não vai no save: sai sempre da seed.
- **Scanner**: por enquanto o gelo gigante aparece no mapa como qualquer formação (a 6.4 esconde o interior).
- **Correção da "florzinha rosa" na neve**: não era planta nem decor (as plantas já saíam da faixa gelada). Era uma **borboleta do clima do Verde** (`Renderer._draw_weather`, efeito de tela rosa/amarelo sem noção de região). Agora a borboleta é pulada quando o pixel do mundo dela cai na região `frost` (`geo.region_px`).
- Testes em `tests/test_giant_pocket.py` (30 seeds na geografia: forma, espessura, vão reto, corredor; 4 no mundo com `reachable_from`, inclusive o interior inalcançável com o vão fechado; e a borboleta fora da neve). Print avulso (fora do smoke): `uv run python tools/dev/shot_bolsao.py` → `reports/dev/bolsao_criatura.png`.

**M3.6.3 · Portão grande** (`game/ice_blocks.py`, `game/thaw.py`, `game/layers.py`, `game/systems.py`, `game/app.py`, `game/map_view.py`; receita `G` em `recipes` do `regions_palettes.json`; marcos em `C.THAW_GIANT_HEAT`)
- **Fecha a entrada** do bolsão da criatura (`geo.giant.entry_rect`, vão de 8×2 tiles) com um gelo-portão do mesmo sistema dos outros (blocos por retângulo, `refresh_gates`, `solids_near`). Pé do portão = meio da borda de baixo da entrada (`ice_blocks.gate_base_px`). É o **último** da lista de portões (índice `len(geo.pockets)`; `ice_blocks.gate_count/is_giant_gate/gate_tiles`), com `gate_ice/gate_melt/gate_recipes` de um item a mais. Tudo derivado do calor, nada no save.
- **Receita `G`** (não entra no sorteio da seed: `RECIPE_KEYS` continua `A, B, C`): **11 blocos** (os 3 tipos, lasca/laje/pedra, nas 2 variações), 2 fileiras largas, `corridor_tiles = 8`. `opens_at` medido = **0,565** (a busca da fresta aceita `corridor` por receita: `passable/path_through/occupancy(corridor=…)`; a dos outros segue em 4 tiles). Fechada em p = 0 e a fresta abre antes de p = 1. Sem arte nova.
- **Calor (provisório, balancear depois)**: `THAW_GIANT_HEAT = (22.000, 25.000, 28.000)` pK: começa onde o 3º portão termina (22.000), então só abre depois de **todos** os outros (`thaw.gate_progress(heat, i, giant=True)`). A fresta abre com ~25.400 pK. O calor que o jogo alcança no `balance_sim` (casual/guloso/variado, seeds 1 e 2) vai de ~28.000 a ~52.000 pK (casual 28.000–31.500), e a fresta abre aos ~94% da partida do casual: perto do fim, nunca "nunca". Os 3 portões de hoje não mudaram (ordem, janelas, receitas). O `balance_sim` ganhou a coluna **grande**.
- **Evento**: `("giant_gate_thaw", etapa)` (1 = começou, 3 = fresta aberta), em vez do `gate_thaw` com índice. O App, na abertura, repinta o mapa do scanner e toca o som de gelo quebrando (a 6.4 pendurou nele a mensagem especial e o fim da névoa).
- **Dica e mapa**: com o mouse no gelo, **"Grande gelo · a passagem abre com ~N pK (agora X)"** (ou "· a passagem já abriu"); marcador "Grande gelo" no mapa (fechado / "derretendo · N%" / "aberto · passagem livre"). A geada de chão dos portões não vale pro grande.
- Testes: `tests/test_giant_gate.py` (receita, fechado bloqueia o interior, ordem depois dos outros, o player passa pela fresta, evento, dica e marcador). Print avulso: `uv run python tools/dev/shot_portao_grande.py` → `reports/dev/portao_grande.png`.

**M3.6.4 · Névoa no bolsão e mensagem ao abrir** (`game/pocket_fog.py`, `game/render.py`, `game/layers.py`, `game/minimap.py`, `game/map_view.py`, `game/map_markers.py`, `game/app.py`; números no bloco `GIANT_FOG_*` / `GIANT_OPEN_NOTICE` do `game/config.py`)
- **Névoa**: enquanto a fresta do portão grande não abriu, uma névoa fria e densa (branco-azulada, ruído fbm rolando devagar em duas camadas, borda suave seguindo o interior orgânico) cobre o interior do bolsão e a pegada do gelo gigante: de fora não se vê o gelo gigante nem a criatura. Desenhada depois dos objetos e estilhaços, antes da luz (a noite escurece a névoa junto) e da HUD (`Renderer.draw_pocket_fog`). Ao abrir, **dissipa em 3,5 s** (`C.GIANT_FOG_FADE_S`, em manchas, não só alfa).
- **Tudo derivado do calor, nada no save**: `pocket_fog.closed(layer)` = portão grande ainda sem a fresta. O load com o portão já aberto nasce sem névoa e sem mensagem (o load descarta os eventos).
- **Mapa do scanner e minimapa**: fechado, o interior e o gelo gigante viram uma mancha de névoa (`World.hidden_tiles`, refeito no `refresh_gates`; `minimap.FOG_COLOR`) com um **"?"** (marcador `unknown`, "Desconhecido"); o marcador "Grande gelo" do portão continua. Aberto, o App repinta o interior e o mapa mostra tudo. **F3** (mapa revelado) mostra tudo mesmo fechado, sem o "?".
- **Mensagem** (provisória, `C.GIANT_OPEN_NOTICE`): "O grande gelo do norte cedeu. O que ele guardava não é rocha." Sai uma vez, na etapa 3 do `giant_gate_thaw`, na mesma pílula do aviso da cratera (`show_thaw_notice`, 3,5 s). Nada de interação com a criatura (gancho do futuro).
- Testes: `tests/test_pocket_fog.py`. Print avulso (fora do smoke): `uv run python tools/dev/shot_bolsao_nevoa.py` → `reports/dev/bolsao_nevoa.png`.

### M3.7 · Nevasca na faixa gelada (`game/dust.py`, `game/weather.py`, `game/ui.py`; números no topo do `dust.py` e `C.STORM_SNOW_FADE_S`)
- **Gatilho**: o tile do player é `frost` (`geo.region_at`) na superfície. `state.weather.snow` (0 poeira .. 1 neve) sobe/desce linear em **1,5 s** (`STORM_SNOW_FADE_S`) e só a aparência usa; vento, rajada, raio de visão, empurrão, O₂ e som do vento não mudam. Na caverna não tem tempestade, então não tem nevasca (`dust.snow_of` = 0).
- **Skin**: fundo da nuvem `#a9bec0` (média de `#99b6b7`/`#b9c6bf`, rampa `ICE.frost.storm`), nuvem clareia `+(30,32,36)` e escurece `-(38,34,28)` (chega perto de `#d3cec2` e `#7ca0a8` da mesma rampa), faixas `#e6f0f4` com alfa ×0,7 (mais ralas), grãos `#ddeaee/#f7fcfe/#7ca0a8`. Cores interpolam com o fator.
- **Flocos**: cada grão tem um limiar sorteado; passou do fator, vira floco (+1 px, 55% da velocidade, zigue-zague de 24 px/s com harmônico). A troca é grão a grão, sem pulo. Contagens e faixas iguais.
- **Custo**: o ruído fbm continua gerado uma vez; as texturas tingidas (add/sub/detail e faixas) ficam em cache por degrau de neve (12), construídas na 1ª vez que o degrau aparece. Frame da tempestade (`draw_storm`, 960×540 sem janela): ~0,53 ms na poeira, ~0,66 ms na neve cheia.
- **Chiado**: `ui.static_noise(..., snow)` esfria o chiado do mapa/minimapa (branco-azulado), mesmo fator, 4 degraus de cor em cache.
- Testes em `tests/test_dust.py`. Print avulso: `uv run python tools/dev/shot_nevasca.py` → `reports/dev/nevasca.png`.

### Marco 4 · Expedição e loot (decisões do dono, 2026-10-14)
- **Broca de mão** (`hand_drill`) vira item de hotbar e **substitui** a mineração embutida: o player nasce com ela (nv.1, minera igual a antes: mesmos `MINE_TIME`, alcance e drops). **Só minera com ela selecionada**; com outro slot na mão, o clique não minera. Arte da mão continua a de sempre (`drill_*.png`); ícone novo pela Designer.
- **Sem broca nv.2 neste update** e o `BEDROCK` continua sem minerar. A nv.2 vem depois, pra furar rochas mais duras que ainda não existem.
- **Itens novos no loot** (lingote de ferro, wafer de silício, circuito, chip, fios; ícones aprovados no M1): **não fazem nada ainda**, só ocupam inventário. Destroços comuns dão os mais simples, o destroço rico dos bolsões dá os melhores, e o contêiner lacrado dá o saque top.
- **Contêiner lacrado abre** com E, de graça (sem chip, por enquanto), uma vez só, e entrega o saque top. Sprite de aberto e som de abrir pela Designer e pelo Som.

### Marco 4 · como ficou na implementação (`game/config.py` bloco "v0.5 Marco 4", `game/wrecks.py`, `game/systems.py`, `game/app.py`, `game/render.py`)
- **Broca de mão** (`hand_drill`, "Broca de mão"): item como a cápsula de água (`MachineType` com `placeable=False`, fora do `MACHINE_ORDER`: sem receita, sem categoria, nenhum menu de fabricar mostra). Stack 1 (`STACK_TOOL`). O novo jogo **nasce com 1** no slot 0 da hotbar. **Só minera com ela selecionada na hotbar**: `Controls.drill_in_hand` (o app calcula por `hand_drill_selected()`); sem ela o clique não minera, não tem som de mineração (`mine_hit` nasce no estado) e a dica do mouse diz "Selecione a broca de mão pra minerar". Com ela é igual a antes (tempos, alcance, drops, sons, arte `drill_*.png`). Nada do jogo a destrói: não existe descarte, ela não é logística (drones não levam) e dá pra guardar em baú e pegar de volta. A nv.2 (T2, fura `BEDROCK`) continua pra depois.
- **Save**: continua **v10** (sem bump). Save v10 do M3 sem broca ganha uma ao carregar (`GameState.ensure_hand_drill`, chamado no `state_from_dict`): só dá se não houver nenhuma no inventário nem em baú (nunca duplica). Inventário lotado: não dá nesse load (tenta de novo no próximo). Os novos itens e o contêiner aberto usam os mesmos campos de antes (`inventory.slots` e `crates`), então não precisa migração.
- **Peças de loot** (`iron_ingot` Lingote de ferro, `silicon_wafer` Wafer de silício, `circuit` Circuito, `chip` Chip, `wire` Fios): `MachineType` `placeable=False` como a cápsula, empilham até **20** (`STACK_LOOT`), vão pra baú e save, nome/ícone/categoria "PEÇA" no inventário, **nenhum uso nem receita**. Ícones aprovados do M1 em `assets/sprites/icon_<item>.png`.
- **Loot** (números de partida, `C.LOOT_COMMON/RICH/CONTAINER`, formato `item: (chance, (mín, máx))`; o dono balanceia depois). Sorteado pela seed, **depois** dos recursos (os recursos e diagramas das caixas não mudaram):
  - destroço comum (de fora): fios 60% (1–3), lingote 40% (1–2), wafer 15% (1);
  - destroço rico (bolsão, `WRECK_RICH_LOOT`): wafer 70% (1–3), circuito 60% (1–2), chip 15% (1);
  - contêiner lacrado (`CONTAINER_LOOT`/`CONTAINER_RESOURCES`): sempre chip 2–3, circuito 3–5, wafer 2–4, lingote 3–5, fios 4–8, mais ferro 20–30, silício 14–20, gelo 10–14 (8 pilhas, a caixa tem 8 slots).
- **Contêiner lacrado abre**: o E abre de graça (sem chip) e usa **a mesma tela e fluxo da caixa de saque** (`Crate` com um `wrecks.ContainerSpot` no lugar do destroço; `Layer.containers`, tile → `Crate`, criada junto com a camada). O saque é fixo, uma vez só (pegou, acabou; o que sobrou na caixa fica lá). `crate.opened` vira o estado "aberto", **salvo no save na mesma lista `crates`** (só entra se abriu ou foi mexido). Alvo do E: "[E] Abrir contêiner"; aberto e vazio, "Contêiner aberto" (o E ainda abre a tela vazia, como a caixa). Mapa: o marcador continua, com o estado "aberto". A **lore antiga saiu** (`CONTAINER_LORE` removido): a tela com o saque já conta a história, e o texto nunca foi aprovado. Painel: "Contêiner · caixa".
- **Arte e som**: `container_open.png` (B, **aprovado**) e `container_open.wav` (D3s, **aprovado**, volume 0,9) já estão no jogo; `icon_hand_drill.png` (opção Y, provisória) e `icon_tab_base.png` (cápsula A) aprovados. O evento `container_open` toca `container_open` se existir em `assets/audio/` (`Audio.has`), senão o `crate_open`.
- Testes: `tests/test_m4_expedition.py`. Print avulso: `uv run python tools/dev/shot_m4_loot.py` → `reports/dev/m4_*.png`.

## 14. v0.6 · Logística (decisões do dono, 2026-10-15)
Spec: `docs/superpowers/specs/2026-10-15-v06-logistica-design.md`. O v0.6 virou dois blocos, Logística e Fundo; o elevador de carga foi pro Futuro.
- **Chip**: máquina só entra na rede dos drones com um chip no slot dela (drill envia o minério; derretedor recebe gelo e envia cápsula; dispersor de O₂ recebe cápsula). **Baú não precisa de chip.** Receita do chip na Bancada T2 (2 wafer + 1 ferro, partida); continua saindo de loot. Save antigo: drill e derretedor com Envia ligado ganham o chip.
- **Baús**: Simples (8 slots, sprite `loot_crate`), Normal (16, `chest`) e Grande (24, `container_sealed`/`container_open`). Travas: Simples desde o começo, **Normal em Ti 50.000**, Grande pelo diagrama (fabricado no T1, receita em **Ti 90.000**). Sem migração (dono): o baú do save antigo carrega como Normal (16) e perde os slots 17–24.
- **Baú de loot** dos destroços, depois de aberto, funciona como Baú Simples (guarda item, entra na rede) e desmonta vazio. O contêiner lacrado aberto guarda item mas não desmonta.
- **Painel de transferência** (baú, drill, máquinas, estação) no estilo do inventário: o clique pega a pilha no cursor e solta no slot escolhido; **Shift+clique manda só a pilha clicada** direto pro outro lado (dono, teste do M1: não manda mais todas as pilhas do item).
- **Caverna**: a estação de drones funciona lá; cada camada tem a sua rede e os drones nunca trocam de camada.
- **Desmontar** (pedido do dono no teste do M1): só com o **construtor selecionado na hotbar**, segurando o botão direito **1 s** (era 2 s, `C.DISMANTLE_HOLD`). Sem o construtor na mão, a dica diz "construtor na mão pra desmontar".
- Receita que pede diagrama fabricado (Bancada T2, Baú grande) diz "Fabrique o diagrama no fabricador T1 e leia na bancada"; só os diagramas de destroço (`WRECK_DIAGRAMS`) dizem pra achar num destroço.

