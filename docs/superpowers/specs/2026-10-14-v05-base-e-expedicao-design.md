# v0.5 · Base e expedição (design)

Aprovado pelo dono no brainstorm de 2026-10-14. Substitui a lista antiga do v0.5 ("Fundo"): a mochila ficou; biomas de caverna, elevador de carga e os ganchos (vulcão, espécie nativa) foram pro v0.6.

## Objetivo

Hoje o ciclo é minerar, fabricar, colocar e esperar o número, e explorar dá recurso rápido demais. O v0.5 traz **tensão e descoberta** pela **expedição com preparo**: o jogador leva material, monta um **posto avançado respirável** longe da cápsula e explora a partir dali até uma descoberta (o contêiner lacrado, a criatura no gelo).

## Decisões do dono

| Tema | Decisão |
|---|---|
| Colocar máquina | **Construtor** (item da hotbar) é o **único** jeito. A máquina se constrói no lugar com uma luz de scanner varrendo os pixels; não existe mais máquina como item no inventário |
| Construtor | Primeira receita do fabricador T1, barata (vira o 1º objetivo) |
| Desmontar | **Segurar o botão direito 2 s** na máquina: barrinha enchendo, o scanner desfaz os pixels e os materiais da receita voltam pro inventário. O clique rápido não faz mais nada |
| Bancadas | O **fabricador da nave vira a bancada T1** (só o básico). A T1 fabrica o **diagrama da Bancada T2**, que libera a T2 no construtor. A T2 se constrói em qualquer lugar e tem as receitas avançadas |
| Diagrama | **Substitui o projeto** (`bp_<id>`). É item: se leva até a bancada e se lê lá; a receita fica liberada pra sempre |
| Mochila | Equipamento do traje, **+1 linha** de slots. Mochila T2 fica pra depois |
| Base | Blocos **chão, parede, porta**. Base fechada com **Dispersor de O₂** dentro vira lugar respirável |
| Dispersor de O₂ | **Obrigatório** pra base respirar. Gasta **cápsula de água** devagar |
| Cápsula de água | Sai do **Derretedor**, que ganha inventário (entra gelo, sai cápsula). Drones só **tiram** as cápsulas prontas (opção A); abastecer máquina fica pro v0.6 |
| Itens novos | Lingote de ferro, cápsula de água, wafer de silício, circuito, chip, fios, diagrama. Fora a cápsula, no v0.5 são **só loot** (destroços, gelos-portão, contêiner lacrado) |
| Mapa | 192 → **~256 tiles**, faixa gelada como região de verdade, fumarola (magmatita) a uma distância razoável da cápsula |
| Cratera | Blocos mineráveis orgânicos, como os da superfície |
| Criatura no gelo | Teaser sem interação num canto da faixa gelada. **Mesma criatura**, sprite muda por mapa: **Larva em C** ou **Casulo** (as duas aprovadas, `reports/design/gelo_gigante/`) |
| Broca de mão | Item da hotbar com nível: **nv.1** (a mineração de hoje) e **nv.2** (fura o anel de `BEDROCK` dos bolsões) |

Pro v0.6 ("logística e fundo"): **chip num slot** de baú/máquina deixa ela visível pros drones e libera o menu "Drone" nela; drones abastecendo máquinas; elevador de carga; biomas de caverna; ganchos do vulcão e da espécie nativa. Futuro: fornalha (magmatita como combustível → lingote), cobre → fios.

## Marcos

### Marco 1 · Construtor e bancadas

**Construtor**
- Item da hotbar, 1ª receita do fabricador T1 (barata, só ferro). Objetivo novo no começo: "Fabrique o construtor".
- Com ele selecionado, **E abre o menu de construção**, com as abas de categoria de hoje (`FAB_TABS`). Escolhida a máquina, entra no modo de colocar que já existe (fantasma verde/vermelho).
- **Clique esquerdo constrói**: gasta os materiais **só do inventário** (como o fabricar em campo de hoje) e respeita as travas de hoje (Ti e diagrama).
- **Animação de construir**: a luz de scanner varre a máquina de baixo pra cima em ~1,5 s; nesse tempo ela ainda não funciona.
- Todas as máquinas de hoje passam a vir do construtor: O₂, derretedor, aquecedor (e as nv.2), painel solar, drill, estação de drones, baú, luminária, luminária forte e a Bancada T2. O drone continua item (vai na estação).
- A aba "Fabricar" do Tab (fabricar em campo, `FIELD_RECIPES`) sai: as receitas dela eram todas máquinas e agora estão no construtor.

**Desmontar**
- Segurar o **botão direito 2 s** em cima da máquina: barrinha enchendo, o scanner varre ao contrário (de cima pra baixo) e os materiais da receita voltam pro inventário. Soltar antes cancela.
- Não cabendo tudo no inventário, a máquina fica no lugar com o aviso de inventário cheio: nada some (mesma regra da estação de drones hoje). A estação continua devolvendo os drones e o minério dela.
- O clique direito rápido numa máquina não faz nada. O aviso de máquina submersa muda de "recolha [Clique direito]" pra "segure [Clique direito]".

**Fabricador T1 (a cápsula)**: só itens. Construtor, drone, tanque de O₂, scanner e o **diagrama da Bancada T2**.

**Bancada T2 (máquina)**: sprite da Designer (`reports/design/v05_bancada_itens/`, v2, aprovado pelo dono): 32×40, o tamanho do baú, braço robótico de perfil na quina, animação de 8 quadros a 4 fps só enquanto fabrica. Abre o mesmo painel de fabricar do T1, com as receitas dela: no M1, a **mochila**; a broca nv.2 entra no M4.

**Diagrama**: os projetos de hoje (tanque de O₂, scanner, luminária forte) viram diagramas. Na bancada, um slot "Ler diagrama"; lido, o item some e a receita libera. Cada diagrama é lido na bancada que faz aquela receita (os de máquina, em qualquer bancada). Ícone `icon_diagram` no lugar do `icon_blueprint`.

**Mochila**: equipamento novo no traje (`EQUIP_SLOTS`), +1 linha de 8 slots no inventário. Tirar a mochila com a linha extra ocupada: só deixa se a linha estiver vazia.

**Save**: v8. Save v7 carregado: máquinas que estavam como item (inventário e baús) viram os recursos da receita; projetos viram diagramas.

**Assets** (aprovados pelo dono em `reports/design/v05_bancada_itens/`): `machine_workbench.png` + `anim/anim_machine_workbench.png` (8 quadros; o `anim_frames` passa a ler o número de quadros da largura da tira) e os ícones `icon_workbench`, `icon_diagram`, `icon_iron_ingot`, `icon_water_capsule`, `icon_silicon_wafer`, `icon_circuit`, `icon_chip`, `icon_wire`. Pendentes: ícone do construtor, ícone da mochila e a luz de scanner (Designer); som de construir e de desmontar (Som).

### Marco 2 · Base respirável

- **Blocos** chão, parede e porta (construtor, baratos, 1 tile cada). Parede bloqueia; porta abre sozinha com o player perto e **não quebra a vedação**; chão é piso e aceita máquina em cima.
- **Validação** (flood fill a partir do tile do Dispersor, pelo chão, vizinhança de 4): a base é válida quando todo o chão alcançado está cercado de parede ou porta, tem **≥ 9 tiles de chão** (o 3×3 mínimo, em qualquer formato), **≥ 1 porta** e **≤ ~200 tiles** de chão. Recalcula quando um bloco é colocado ou desmontado perto.
- **Dispersor de O₂** (construtor): 1 slot de cápsulas de água, gasta 1 cápsula a cada X minutos (número no balanceamento). Estado no painel e em cima dele: "Vedado ✓", "Vazamento" (o tile furado pisca) ou "Sem água". Tudo ok: dentro da base o O₂ recarrega igual à zona da cápsula.
- **Derretedor**: continua terraformando como hoje e ganha inventário (entra gelo, sai cápsula de água). Os drones tiram as cápsulas e levam pros baús (mesma rota da drill).
- **Energia**: o Dispersor consome **1 kW** (decisão do dono), como as outras máquinas.

### Marco 3 · Mundo

- Mapa ~256×256, faixa gelada como região de verdade, cratera com blocos orgânicos, garantia de fumarola a uma distância máxima da cápsula.
- Gelo gigante com a criatura (contrato em `reports/design/gelo_gigante/pendentes/`): pegada 7×4, rampa `ICE_DEEP`, geada; sprite Larva em C ou Casulo sorteado pela seed (ou pelo tipo de mundo, a decidir no plano).
- Novo jogo obrigatório (save novo).

### Marco 4 · Expedição e loot

- Broca de mão como item: nv.1 (T1) e nv.2 (T2: ferro + silício + 1 circuito), que fura o `BEDROCK`. Sem broca na mão não se minera.
- Contêiner lacrado abre com as peças raras (chip, circuito).
- Itens novos espalhados nos loots dos destroços e dos gelos-portão.
- Playtest e polimento.

## Riscos

- **O construtor mexe no fluxo central** (fabricar → colocar): fabricador, hotbar, inventário, drones e save tocam nisso. Por isso é o M1, e os outros marcos já nascem no fluxo novo.
- **Construtor gastando só do inventário** pode irritar na base principal (tirar do baú antes de construir). A acertar no playtest; uma saída é puxar dos baús perto de uma bancada.
- **Flood fill** tem que ser barato: limite de tiles e recálculo só quando um bloco muda.
