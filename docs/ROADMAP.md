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

**v0.5 fechado em 2026-10-14.** Ficou pra depois: ícone da broca de mão definitivo (hoje a Y provisória; as R1/R2 da referência do dono estão em `reports/design/v05_m4_broca_conteiner/`), update de melhoria de sprites, balanceamento do loot (números de partida em `C.LOOT_*`), uso das peças (v0.6).

## v0.6 · Logística e fundo
Dividido em dois blocos (brainstorm de 2026-10-15).

**Logística** (spec: `docs/superpowers/specs/2026-10-15-v06-logistica-design.md`)
- [ ] Marco 1 · Baús e painel: baú Simples (8) / Normal (16) / Grande (24, diagrama na Névoa); baú de loot guarda item e desmonta; painel de transferência com pilha no cursor; sem migração de save (baú antigo vira Normal).
- [ ] Marco 2 · Chip e máquinas na rede: chip no slot liga drill, derretedor e dispersor aos drones; derretedor recebe gelo, dispersor recebe cápsula; chip na T2; save v11.
- [ ] Marco 3 · Drones na caverna: estação na caverna, rede separada por camada.

**Fundo** (spec própria depois): caverna espelhando as regiões da superfície (caverna gelada, de fogo e magma), menos minério solto e veios de parede (6 a 8 blocos), cobre na caverna, fornalha (magmatita → lingote, cobre → fios), broca nv.2 quebrando a pedra que dá acesso aos biomas. Ganchos: basalto → vulcão, espécie nativa nas cavernas. Remapear os crafts.

## v0.7 · Perigo e lore
Inimigos, combate, primeiro boss, ruínas da Colônia Hesper.

## v0.8 · Vida
Fauna e flora surgindo com o Ti, farm, música.

## Futuro
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
