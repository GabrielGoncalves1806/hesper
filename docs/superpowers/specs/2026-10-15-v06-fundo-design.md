# v0.6 · Bloco Fundo: design

Aprovado pelo dono no brainstorm de 2026-10-15. É o segundo bloco do v0.6 (o primeiro, Logística, está em `2026-10-15-v06-logistica-design.md`). Números são de partida; o balanceamento é uma passada só, depois (regra do dono).

## Objetivo

Dar um "fundo" de verdade ao jogo: a caverna cresce pro tamanho da superfície e ganha regiões, dois biomas ficam trancados atrás de uma rocha que só a broca nv.2 quebra, e entra a primeira cadeia de processamento (cobre → fundição → lingote → fios → broca nv.2).

## Decisões do dono

| Tema | Decisão |
|---|---|
| Tamanho | Caverna **256×256**, igual à superfície. Já deixa espaço pras ruínas de um update próximo |
| Posição | A rampa da caverna fica **na mesma coordenada da cratera** da superfície |
| Regiões | **Não espelha 100%** a superfície: só a direção. **Gelo ao norte, basalto à esquerda (oeste), salar à direita (leste)**, centro em volta da rampa. Fronteira torta (noise), gerada pela própria caverna |
| Salar | **Maior** que o da superfície ("espalhado nos lençóis freáticos"). **Sem línguas**, só um bloco maior. Visual mais **arenoso**, com cara de infiltração (gancho futuro: tirar areia dele) |
| O que o bioma muda | Visual, minério e **trava**. Sem dano/efeito de ambiente (isso é v0.7) |
| Trava | Toda a rocha do **gelo** e do **basalto** é **rocha dura**: a broca nv.1 não quebra. **Centro e salar são livres** (o cobre do salar destrava a cadeia) |
| Entradas | Sem muralha e sem entrada garantida: a fronteira é só uma linha torta; caverna natural que por sorte cruza a fronteira deixa o player "pôr a pontinha do pé" no bioma, e tá tudo bem |
| Magmatita | **Não nasce na parede** (o sprite `ore_magmatite` fica guardado). Sai das **fumarolas** (como hoje), de **veios** e de **rochinhas no chão do basalto** da caverna |
| Fundição | **Magmatita é o combustível** ("o carvão de Hesper"). Ferro → lingote de ferro; cobre → **lingote de cobre** (item novo) |
| Fios | Lingote de cobre → fios no **fabricador** (receita de partida). Os crafts são remapeados no M5 |
| Broca nv.2 | Quebra a rocha dura **e minera ×1,5** mais rápido. O craft **consome a nv.1**. Bedrock continua inquebrável |
| Save | **v12**. A superfície carrega igual; a caverna antiga é **descartada inteira** (tiles, máquinas, baús, o que tiver lá). Sem baú de compensação |
| Debug | **F3** (modo rápido) passa a quebrar rocha dura, pra testar os biomas antes da nv.2 |
| Arte | Cobre (laranja com verdete) e ferro numa paleta bege nova: em aprovação (`reports/design/v06_fundo_cobre_ferro/`) |

## Regiões e minério (partida)

| Região | Área (aprox.) | Trava | Parede | Veios 2×2 (drill) | Chão |
|---|---|---|---|---|---|
| Centro | o resto (~15%) | livre | rocha normal: ferro, silício, um pouco de gelo | ferro, silício | — |
| Salar (leste) | ~30% | livre | rocha normal: **cobre**, silício | cobre, silício | — |
| Gelo (norte) | ~30% | rocha dura | rocha dura: gelo em volume, um pouco de ferro | gelo | — |
| Basalto (oeste) | ~25% | rocha dura | rocha dura: ferro | magmatita | rochinhas de magmatita |

- **Veios de parede**: aglomerados de **6 a 8 tiles** de minério colados (o minério da região). Substituem boa parte do minério solto, que fica **bem mais raro** que hoje (~39% das paredes).
- O gelo pega a faixa de cima inteira; o salar pega o leste de cima a baixo, abaixo do gelo; o basalto, o oeste abaixo do gelo; o centro fica em volta da rampa (raio de partida ~30 tiles livre de bioma).
- Terminais, cavernas naturais e veios se espalham pelo mapa maior. Os 3 terminais de hoje ficam na área livre (centro/salar).

## Marcos

### M1 · Caverna nova (geração)
- `World` da caverna em 256×256; rampa na coordenada da cratera da superfície.
- Mapa de região da caverna (centro, salar, gelo, basalto) com fronteira torta, determinístico pela seed.
- Tile novo **rocha dura** (`HARD_ROCK`, parede alta, minerável só pela nv.2). Minério dentro do bioma trancado também é "duro" (o tile de minério carrega a dureza da região: a nv.1 não minera parede nenhuma dentro do gelo/basalto).
- Dica ao tentar minerar com a nv.1: **"Rocha dura demais · precisa da broca nv.2"**.
- Veios de parede (6–8 tiles), menos minério solto, **cobre** (`copper`: recurso novo, tile de parede, rochinha, veio 2×2, ícone, pickup) no salar; veios 2×2 por região; rochinhas de magmatita no chão do basalto.
- F3 quebra rocha dura.
- **Save v12**: carregar um save v11 descarta `layers.cave` (e, se o player estava na caverna, ele volta pra chegada da cratera na superfície). Mundo que nunca desceu carrega igual.
- Visual provisório: o chão de cada região levemente tingido, até a arte do M2.
- Desempenho: medir caverna escura no zoom 0,75 (hoje ~5,2 ms/frame) e a geração (tempo de primeira descida).

### M2 · Cara dos biomas (arte e som)
- Chão e parede por região (centro: a névoa de hoje; salar: arenoso com manchas de infiltração; gelo; basalto/fogo), rocha dura com leitura clara de "não dá", tom da luz por região. Ambiente sonoro por bioma, se o dono quiser.
- Designer e Som entregam report; nada entra sem aprovação.

### M3 · Fundição
- Máquina no molde do derretedor: 3 slots (**minério**, **combustível** só magmatita, **saída**). Ferro → `iron_ingot`; cobre → `copper_ingot` (item novo).
- Partida: 1 lingote a cada 15 s (nv.1, × fator da energia); 1 magmatita queima por 4 fundições. Custo partida: 15 ferro + 6 silício + 4 magmatita.
- Entra na rede com chip: **Recebe** minério (ferro/cobre) e magmatita, **Envia** lingote.
- Fios: receita no fabricador, 1 `copper_ingot` → 3 `wire`.
- Sprite e som novos (aprovação do dono).

### M4 · Broca nv.2
- Item `hand_drill_t2`, craft na Bancada T2 (partida: broca nv.1 + 2 lingote de ferro + 4 fios + 1 circuito; a nv.1 é consumida).
- Minera tudo ×1,5 mais rápido e quebra rocha dura (rocha dura com nv.2: ~1,5 s, partida). Mesmo alcance.
- Ícone novo (aprovação do dono).

### M5 · Remapear crafts
- Chip, baú grande, diagramas e o que hoje pede lingote/fio/wafer passam a usar a cadeia nova (fundição/fabricador). Brainstorm curto com o dono antes.

## Fora deste bloco (ganchos)
- Vulcão no basalto; espécie nativa nas cavernas; areia do salar; ruínas na caverna (próximo update).
- **Trefiladora** (lingote → fio como máquina, linha de produção fundição → trefiladora pelos drones): Futuro.
- Minério exclusivo dentro dos biomas trancados: por ora não.
