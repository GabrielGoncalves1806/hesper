# Roadmap

## v0.1 · MVP ✓ (tag v0.1)
Detalhes em `GAME_BIBLE.md` §4.

- [x] Janela 960×540 escalada, game loop com delta time
- [x] Mapa 128×128 gerado + câmera seguindo o player
- [x] Player andando com colisão
- [x] Mineração com mouse (dureza por tile, drops)
- [x] Inventário (contador) + HUD
- [x] O₂: zona da base, alarme, desmaio e respawn
- [x] Fabricador (menu de receitas, desbloqueio por Ti)
- [x] Colocar máquinas + índices subindo + Ti
- [x] 3 estágios visuais (troca de paleta, água, plantas)
- [x] 3 terminais de lore
- [x] Tela de fim do MVP
- [x] Guia visual + sprites (Designer) · aprovado pelo dono
- [x] Guia de som + efeitos (Som) · aprovado pelo dono
- [x] Integrar sprites e sons aprovados
- [x] Polimento: pausa/volumes, objetivos, desmontar, transição gradual, simulador de balanceamento
- [x] Veios de minério 2×2 no chão + drill automática (libera na Névoa, coleta manual)

## v0.2 · A base ganha vida (automação) ✓ (tag v0.2)
Detalhes em `GAME_BIBLE.md` §8.

- [x] Marco 1: save/load versionado + tela de título
- [x] Marco 1: inventário com 16 slots + hotbar + tela de inventário
- [x] Marco 1: baú (24 slots, o fabricador puxa dos baús na base)
- [x] Marco 2: energia global (cápsula 5 kW, painel solar, consumo, déficit proporcional)
- [x] Marco 3: estação de drones + drones levando minério das drills pros baús
- [x] Assets do v0.2 (sprites e sons) · aprovados pelo dono
- [x] Marco 3+: logística estilo Planet Crafter (drone como item, estação com 4 slots, alcance no mapa todo, Envia/Recebe/Lote em baú e drill, drill com inventário)
- [x] Baú com nome, transferência por clique, Pegar tudo / Guardar recursos
- [x] Tela cheia, janela redimensionável, zoom do mundo, tamanho da interface (Grande/Média/Pequena)
- [x] Fabricador com abas, scroll e fabricar em lote
- [x] Marco 4: balanceamento (painel solar 4 kW) + polimento + playtest do dono

## v0.3 · Superfície ✓ (tag v0.3)
Detalhes em `GAME_BIBLE.md` §9 e no design `docs/superpowers/specs/2026-10-12-v03-superficie-design.md`. Novo jogo obrigatório.

- [x] Marco 1: superfície (deserto 192×192, cápsula no centro, rochas de minério que reaparecem, morros, veios raros, terraformação no deserto)
- [x] Marco 2: caverna (rampa na cratera, mapa separado e escuro, lanterna, luminárias, brilho nos minérios)
- [x] Marco 3: destroços, projetos, tanque de O₂ (slot de equipamento) e scanner com minimapa
- [x] Assets do v0.3 (sprites v5.0/v5.1 e sons v8.1) · aprovados pelo dono
- [x] Marco 4: polimento + playtest do dono (morros orgânicos, aba LOGs em ordem cronológica, fabricar em campo, F3, menos minério na caverna, player sem tremer na diagonal, O₂ com subscrito, tooltip e floaters sem cobrir o HUD)

## v0.4 · Mundo vivo
Design em `docs/superpowers/specs/2026-10-13-v04-mundo-vivo-design.md`. Novo jogo obrigatório (save v7, no Marco 2).

- [x] Marco 1: Tempestade (4 estágios: Tempestade → Árido → Névoa → Verde; poeira, rajadas com empurrão, O₂ ×1,25)
- [x] Marco 2: geografia nova (relevo, 3 regiões, formações fixas com afloramentos, decoração que quebra a grade) + mundos com nome e seed (3 espaços)
- [x] Marco 3: elementos v9 das regiões, cratera derretendo pelo calor, fumarolas acordando (com fumaça), gelos-portão em blocos (fresta, destroço rico, contêiner lacrado), chuva e lagos nas bacias (margem orgânica), máquina submersa, grama do Verde, sons v11 (gelo, chuva, fumarola), caixas azuis r3d
- [x] Magmatita: pedra quente em volta das fumarolas (pouca na dormente, mais na acordada), receita do Aquecedor, objetivo "calor a oeste"
- [x] Marco 4: máquinas do freela (sapata B, aquecedor de magmatita, drill T1 a laser, animações), minério do freela com rochas de veio e veio orgânico, cenário pausado pelo dono, contador de FPS (F5), Hesper.app, balanceamento final (cratera 1.000 pK, portões no meio/fim, lagos L1–L3, partida casual ~35 min)

**v0.4 fechado em 2026-10-14.** Ficou pra depois (ver "Futuro"): rodada de sons e tela de créditos (o IR da reverb do gelo é CC BY 4.0), eólico no jogo (sprite pronto), drills T2/T3 (aranha e tripé guardados em `reports/design/maquinas_r3d/futuro/`), drill nv.2 na fumarola, formação nova pro basalto, papel do salar sem sal, lingotes/wafers redesenhados, marca de queimado no veio minerado.

## v0.5 · Base e expedição
Design em `docs/superpowers/specs/2026-10-14-v05-base-e-expedicao-design.md`. Novo jogo obrigatório (no Marco 3).

- [x] Marco 1: construtor (único jeito de colocar máquina, luz de scanner), desmontar segurando 2 s, fabricador T1 → Bancada T2, diagrama no lugar do projeto, mochila (+1 linha)
- [x] Marco 2: base respirável (chão, parede alta, porta solo e dupla, flood fill, Dispersor de O₂ gastando cápsula de água, derretedor com inventário, save v9)
  - Pendências: blocos não reagem quando o lago sobe por cima, hum não baixa com a porta aberta (porta redesenhada no M3; chuva dentro da base: o dono decidiu deixar)
- [x] Marco 3: mundo (mapa 256 + F3 revela o mapa, faixa gelada maior com neve e veio de gelo, caverna orgânica, bolsão da criatura com gelo gigante, portão grande "Grande gelo" com névoa e mensagem, nevasca na faixa, porta e chão novos da base; fumarola garantida adiada)
- [x] Marco 4: expedição e loot (broca de mão como item, nasce com ela, só minera com ela selecionada; lingote, wafer, circuito, chip e fios nos loots, sem uso ainda; contêiner lacrado abre com E e dá o saque top, sprite aberto B e trava CC0 D3s; ícones novos da drill automática e da aba Base) + playtest do dono
  - Decisões: sem broca nv.2 e sem furar BEDROCK neste update (a nv.2 vem pra rochas mais duras); contêiner abre de graça por enquanto (sem chip)

**v0.5 fechado em 2026-10-14.** Ficou pra depois: simulador: a estratégia "variado" ficou bimodal no v0.6 M1 (seeds 1 e 5 fecham em ~50 min sem máquina nv.2; o teste dela não exige mais a nv.2); ícone da broca de mão definitivo (hoje a Y provisória; as R1/R2 da referência do dono estão em `reports/design/v05_m4_broca_conteiner/`), update de melhoria de sprites, balanceamento do loot (números de partida em `C.LOOT_*`), uso das peças (v0.6).

## v0.6 · Logística e fundo
**v0.6 fechado em 2026-10-16.** Ficou pra depois: simulador aprender a cadeia nova (Fundição, Bancada, cobre da caverna) na passada de balanceamento; tooltip de descrições e wiki (Futuro).

Dividido em dois blocos (brainstorm de 2026-10-15).

**Logística** (spec: `docs/superpowers/specs/2026-10-15-v06-logistica-design.md`)
- [x] Marco 1 · Baús e painel (fechado em 2026-10-15, testado pelo dono; travas: Normal em Ti 50.000, diagrama do Grande em Ti 90.000; desmontar só com o construtor na mão, 1 s; Shift+clique manda só a pilha clicada; caixa de saque fora da rede): baú Simples (8) / Normal (16) / Grande (24, diagrama na Névoa); baú de loot guarda item e desmonta; painel de transferência com pilha no cursor; sem migração de save (baú antigo vira Normal).
- [x] Marco 2 · Chip e máquinas na rede (fechado em 2026-10-15, testado pelo dono; Lote só em quem envia; estado do dispersor no mundo só no hover, "!" quando parado; sons `chip_connect`/`chip_disconnect`): chip no slot liga drill, derretedor e dispersor aos drones; derretedor recebe gelo, dispersor recebe cápsula; chip na T2 (2 wafer + 1 ferro); save v11.
- [x] Marco 3 · Drones na caverna (fechado em 2026-10-15; os drones voam por cima das paredes, sem pathfinding): estação na caverna, rede separada por camada, as duas rodando com o player em qualquer camada; sem save novo.

**Fundo** (spec: `docs/superpowers/specs/2026-10-15-v06-fundo-design.md`)
- [x] Marco 1 · Caverna nova (fechado em 2026-10-15; dono testou e pediu fronteiras tortas, biomas mais longe do centro, basalto cinza e gelo mais azul): 256×256, rampa sob a cratera, regiões (gelo N, basalto O, salar L maior, centro), rocha dura nos biomas trancados, veios de parede (6–8), menos minério solto, cobre no salar, magmatita em veio e rochinha no basalto, F3 quebra rocha dura, save v12 (caverna antiga descartada).
- [x] Marco 2 · Cara dos biomas (fechado em 2026-10-16; dono testou e pediu a luz dos biomas um tiquinho mais escura e a do centro mais clara): chão assado da caverna por região com divisa curva, rocha com rampa por região na mesma curva, luz ambiente e capacete por região (basalto avermelhado), minimapa, ambiente sonoro por bioma (salar, basalto, gelo) com troca depois de 1,5 s. Tinta provisória do M1 saiu.
- [x] Marco 3 · Fundição (fechado em 2026-10-16; dono testou junto com o M2; sprite r3d opção A e som aprovados): magmatita de combustível (1 pedra = 4 lingotes), 1 minério → 1 lingote a cada 15 s, lingote de ferro e de cobre, fios no fabricador (aba Materiais, 1 lingote de cobre → 3), na rede com chip (lingotes entram na logística, baú com 8 toggles).
- [x] Marco 4 · Broca nv.2 (fechado em 2026-10-16, testado e aprovado pelo dono; ícones par A): quebra rocha dura (2,25 s de base, ~1,5 s com ela), minera ×1,5, consome a nv.1 e nasce no slot dela; Fundição funde silício → wafer, circuito no fabricador (1 wafer + 2 fios); baú com 9 toggles.
- [x] Marco 5 · Remapear crafts (fechado em 2026-10-16, testado e aprovado pelo dono): Fundição 3:1 (ferro e cobre, sem wafer), wafer na Bancada T2 (10 silício), receitas da tabela da bíblia §15 (Ti 0 cru, Ti 10.000 em diante refinado; Dispersor, tanque e scanner caros), Bancada vê tudo do T1 com a aba "Bancada" das exclusivas, item de uma vez só com "feito" (sem save novo), wafer fora da logística (8 toggles), objetivos-guia antes da drill; no teste do dono: diagrama da Bancada em Ti 10.000, fabricar não fecha o painel, meia linha (com ícone) na lista que rola. Simulador congelado nas receitas do M4 (passada de balanceamento).
Ganchos: vulcão no basalto, espécie nativa, areia do salar, ruínas na caverna.

## v0.7 · Lore
Spec: `docs/superpowers/specs/2026-10-16-v07-lore-design.md` (brainstorm de 2026-10-16). Inimigos, combate e boss saíram (versão futura); o planeta reagindo foi pra v0.8.
- [x] Marco 1 · Estruturas (fechado em 2026-10-16, testado e aprovado pelo dono; falta só ele conferir "mesma seed, mesmas ruínas", que o pytest já cobre): plantas à mão + variação pela seed, acampamento de pouso, laboratório da Ilves, estação de derretedores, posto de perfuração; casca intocável, máquinas quebradas, LOGs novos.
- [x] Arte (Designer, aprovada pelo dono "por hora" em 2026-10-16, 5 rodadas, `reports/design/v07_lore/`; dá pra polir depois): 5 destroços da referência do dono, kit médio de props, construtor com scanner.
- [x] Marco 2 · Props e scanner (fechado em 2026-10-16, testado pelo dono; som do scan loop B + done A; prop de chão colado em parede ao sul fica): aba Decoração (mesa, cadeira, caixote e placa de cara), scan no esquerdo segurado em prop de ruína, props nas 4 plantas, props de parede, ícone novo do construtor; save continua v12.
- [ ] Marco 3 · Destroços novos: 3 sprites trocados, nave de passageiros e robô de reconhecimento.
- [ ] Marco 4 · Interior da VÉSPER-7: camada pequena pelo porão, salas encaixadas pela seed, câmara fria.

## v0.8 · Vida
Fauna e flora surgindo com o Ti, farm, música. **O planeta reage** ao Ti e ao derretimento (saiu da v0.7). Genes do gelo (canon na bíblia §2).

## Depois · Perigo
Inimigos (larvas pelo mapa), combate, a criatura como boss (saíram da v0.7).

## Futuro
- **Base de pesquisa + dungeon** (dono, 2026-10-16, "olhar com calma depois"; referência em `reports/design/ideias/base_pesquisa_dungeon.png`): base externa grande (domo central, módulos ligados por tubos, pista com nave, painéis, estufa de vidro) e por dentro uma instalação estilo dungeon, vista de cima, com salas encaixadas (laboratório, servidores, depósito, enfermaria, controle, corredor, reator) e elementos marcados (porta, terminal, baú, ponto de interesse, armadilha, parede destruída, bloqueio, loot). Conversa com o interior da VÉSPER (M4) e com as ruínas do M1.
- **Baú grande colado em outro** (dono, teste do v0.6 M1, print em `reports/design/v06_m1_baus/feedback/bau_grande_colado.png`): o sprite do contêiner tem 40 px num tile de 32, então dois Grandes lado a lado se sobrepõem 8 px. Opções: arte de 32 px de largura, Grande ocupando 2 tiles, ou proibir colar. Já tinha sido levantado pela Designer.
- **Modal de itens no painel de logística** (dono, 2026-10-16, abrindo o v0.6 Fundo M4): a fileira de toggles Envia/Recebe do baú já está em 9 itens (recursos, cápsula, lingotes, wafer) e não escala. Trocar por um modal/lista de itens (com ícone, busca ou abas) em vez de crescer a fileira a cada item novo.
- **Tooltip com descrição dos itens** (dono, 2026-10-16, brainstorm do v0.6 Fundo M5): mouse em cima do item (inventário/fabricador) mostra nome + 1 frase curta (≤ ~90 caracteres). Rascunho dos 42 textos e mock do tooltip em `reports/dev/descricoes.html` (o dono achou ok; revisar os textos contra o código antes, alguns foram chutados: ferro, painel solar, porta, gelo). "Futuro próximo".
- **Wiki estilo fandom** (dono, 2026-10-16): página de cada item com ícone, descrição, receita (de onde sai, pra onde vai), árvore da cadeia, travas de Ti e custo em bruto. Ideia do gerente: **gerada do `config.py`** por um script em `tools/dev/` (nunca escrita à mão, pra não desatualizar), substituindo o `reports/dev/receitas.html` e reaproveitando as descrições do tooltip. Depois do M5, junto com o tooltip.
- **Enxugar o smoke** (dono, 2026-10-16): passada no `tools/dev/smoke.py` (52 cenas, ~4,5 min, ~340 prints) pra deixar só as cenas que realmente valem (as que pegam o que o pytest não pega: tela, layout, vídeo).
- **Prioridade dos drones** (dono, 2026-10-15, fechando o v0.6 M2): um esquema de prioridade pra quem os drones atendem primeiro (ex.: dispersor sem água antes de encher baú). Hoje o `drones.pick_task` escolhe pelo maior estoque e pela menor viagem. Conversar o desenho antes.
- **Trefiladora** (dono, brainstorm do Fundo): lingote de cobre → fio como máquina, linha de produção fundição → trefiladora pelos drones. No Fundo o fio sai do fabricador.
- **Elevador de carga** (saiu do v0.6): ligar a rede de drones da caverna com a da superfície.
- **Update de melhoria de sprites** (pedido do dono no playtest do v0.5 M4): uma rodada só de arte, revisando os sprites que ficaram "ok mas não ótimos" (começa pela broca de mão).
- Ideia do dono (2026-10-13): **variação de tom por mundo**, a seed puxando um leve deslocamento de cor em cada região (um basalto mais avermelhado num mundo, mais acinzentado em outro). Hoje a cor é só região × estágio.
- Mapa: máquinas coladas viram uma "régua" de marcadores (agrupar por base ou desenhar menor quando estão juntas).
- Testar em Windows/Linux (CI com testes + smoke nos 3 sistemas, varrer imagens criadas sem formato explícito) e empacotar executável.
- Água e comida (barras de sobrevivência).
- Drones: upgrade da estação (mais drones, drones mais rápidos).
- Versão pra celular (navegador via pygbag + controles de toque), decidir se vira plataforma principal.
- Bateria e ciclo dia/noite.
- Baú de chão estilo caixa azul baixa e larga (referência: storage do Planet Crafter), talvez como segundo tipo de armazenamento.
