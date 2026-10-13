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
- [ ] Marco 2: geografia nova (relevo, 3 regiões, formações fixas com afloramentos, decoração que quebra a grade)
- [ ] Marco 3: gelo (cratera congelada + gelos-portão) e água (chuva, lagos enchendo as depressões, máquina submersa)
- [ ] Marco 4: polimento + playtest do dono

## v0.5 · Fundo
Biomas de caverna, mochila, broca nv.2 (perfuratriz térmica, que também minera a rocha dura dos anéis dos bolsões), peças raras (o contêiner lacrado do v0.4), elevador de carga (drones atendem a caverna). Ganchos: basalto → vulcão, espécie nativa nas cavernas.

## v0.6 · Perigo e lore
Inimigos, combate, primeiro boss, ruínas da Colônia Hesper.

## v0.7 · Vida
Fauna e flora surgindo com o Ti, farm, música.

## Futuro
- Mapa: máquinas coladas viram uma "régua" de marcadores (agrupar por base ou desenhar menor quando estão juntas).
- Testar em Windows/Linux (CI com testes + smoke nos 3 sistemas, varrer imagens criadas sem formato explícito) e empacotar executável.
- Água e comida (barras de sobrevivência).
- Drones: upgrade da estação (mais drones, drones mais rápidos).
- Versão pra celular (navegador via pygbag + controles de toque), decidir se vira plataforma principal.
- Bateria e ciclo dia/noite.
- Baú de chão estilo caixa azul baixa e larga (referência: storage do Planet Crafter), talvez como segundo tipo de armazenamento.
