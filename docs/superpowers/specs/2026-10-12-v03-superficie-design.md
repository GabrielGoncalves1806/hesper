# v0.3 · Superfície: design

Data: 2026-10-12 · Aprovado pelo dono em conversa (brainstorm com o gerente).
Resumo na `GAME_BIBLE.md` §9; plano em `ROADMAP.md`.

## Visão

Hoje o jogo é uma cratera cercada de rocha. No v0.3 o mundo ganha **duas camadas**:

```
SUPERFÍCIE (deserto aberto, claro)        ← exploração, lore, terraformação visível
  · cápsula/base, recursos soltos, rochas, poucos veios
  · destroços de naves e da colônia (saque, LOGs, projetos)
        │  cratera com rampa (E)
        ▼
CAVERNA (escura, raio de luz)             ← mineração em volume e risco
  · paredes com minério abundante, veios comuns, terminais
```

A superfície é onde tu explora e vê o planeta mudar; a caverna é onde tu minera de verdade.

## Decisões do dono

- Superfície e caverna são **mapas separados**; troca de camada por uma rampa na cratera (transição com fade).
- A **base fica na superfície**. O O₂ continua restrito à zona da base até existirem equipamentos (tanque agora; mochila e outros depois).
- **Drones não descem** no v0.3. No v0.4 entra o **elevador de carga**, colocado na cratera, que deixa os drones atenderem a caverna.
- **Energia continua global** (vale pras duas camadas).
- Recursos na superfície: **soltos no chão + rochas pequenas** pra quebrar; **veios de drill raros** na superfície (obriga a explorar).
- Destroços dão saque, LOGs e **projetos** (estilo chips de blueprint do Planet Crafter): algumas receitas só liberam achando o projeto.
- Caverna: lanterna do capacete + **luminárias** que o jogador coloca + **brilho fraco nos minérios**.
- Projeto extra pedido pelo dono: **scanner de navegação**, que libera minimapa com névoa de guerra.
- O v0.3 exige **novo jogo** (o save do v0.2 não migra).

## Fora do v0.3 (vai pro v0.4 ou depois)

Biomas de caverna, mochila, drill melhor, peças raras, elevador de carga (v0.4). Água e comida, inimigos e dia/noite ficam pra depois.

## Marco 1 · Superfície

**Mundo**
- Deserto de **192×192 tiles**, gerado pela seed.
- Chão de areia e cascalho com dunas e manchas de rocha desenhadas no chão.
- Alguns **morros de rocha** de 3 a 8 tiles: a única parede da superfície, obstáculo e ponto de referência. Parede de morro pode ser minerada como hoje.
- Borda do mapa: **cordilheira intransponível** (não minerável).
- **Cápsula no centro**; zona de O₂ em volta, como hoje (raio de 5 tiles).
- **Cratera** a 15–20 tiles da base. No Marco 1 ela é só visual (fechada); abre no Marco 2.

**Recursos**
- **Soltos no chão**: ferro, silício e gelo, em 1 a 3 unidades. Pega passando por cima ou com E/clique no alcance. **Reaparecem** devagar (alguns por minuto), só fora da vista do jogador e longe da base, com um teto de quantos ficam soltos no mapa.
- **Rochas pequenas** (1 tile): quebra com a broca, dão 2 a 4 unidades e não voltam.
- **Veios de drill**: só **3 a 5 no mapa**, longe da base.

**Terraformação**
Os mesmos 3 estágios de hoje, aplicados ao deserto:
- **Morto**: areia avermelhada, poeira.
- **Névoa**: paleta fria, poças nas partes baixas, chuva.
- **Verde**: grama e plantas se espalhando a partir da base, lagos nas partes baixas.

## Marco 2 · Caverna

**Entrada e troca de camada**
- A cratera ganha uma **rampa de descida**. Com o mouse em cima (no alcance), E desce, com fade pro preto e o texto "Descendo...".
- Na caverna há uma **rampa de subida** com o mesmo funcionamento.
- O jogador sempre chega ao lado da rampa.

**Mapa**
- **128×128**, usando o gerador de hoje (paredes, minério e os 3 terminais), com um salão aberto em volta da rampa.
- Minério **mais abundante** que hoje e mais rico conforme se afasta da rampa. Veios de drill comuns.
- A caverna **não muda com o Ti** (rocha fria sempre).

**O₂**
- Não há zona de O₂ na caverna.
- Sem tanque: os mesmos **100 s** de hoje fora da zona.
- Desmaiou na caverna: reaparece na cápsula, na superfície.

**Escuridão**
- Fora de luz, preto.
- **Lanterna do capacete**: raio de ~4 tiles.
- **Luminária**: item novo, 1 Fe + 1 Si, liberado desde o início. Raio de ~5 tiles, **sem consumo de energia**.
- Máquinas na caverna emitem luz fraca.
- **Minérios** têm um pontinho de brilho na cor deles, visível no escuro, mas não iluminam o redor.
- A escuridão só existe na caverna; a superfície continua clara.

**Duas camadas**
- Cada camada guarda as próprias máquinas, itens no chão e baús.
- Drill na caverna funciona; o jogador busca à mão. Os drones só atendem a superfície no v0.3.
- O fabricador puxa só dos baús da base (superfície).
- Energia global.

## Marco 3 · Destroços, projetos, tanque de O₂ e scanner

**Destroços**
- **6 a 8 no deserto**, a distâncias crescentes: os mais perto a ~30 tiles, os mais longe perto da borda.
- **Tipos**:
  - **Nave de carga**: grande, ~4×3, mais saque.
  - **Módulo da colônia**: médio, tem terminal.
  - **Sonda**: pequena, ~2×2, saque curto.
- São **obstáculo** (não se atravessa).
- Pontos de interação:
  - **Caixa de saque**: abre com E. Painel igual ao do baú, mas só deixa tirar. Contém recursos e às vezes um projeto.
  - **Terminal**: LOG, como os terminais de hoje.
- Conteúdo sorteado pela seed e **fixo** (não reabastece). Caixa vazia fica marcada como "vazia".

**Projetos**
- Item que, ao entrar no inventário, **libera a receita na hora** e some, com o aviso "PROJETO: <NOME>".
- Receita trancada por projeto aparece no fabricador como "??? · projeto não encontrado".
- Projetos do v0.3:
  - **Tanque de O₂**: na nave de carga mais próxima, o primeiro grande achado.
  - **Scanner de navegação**: num módulo da colônia a média distância, o segundo grande achado.
  - **Luminária melhor**: raio maior.
  - **Drill nv.2**: opcional, só se sobrar tempo.

**Tanque de O₂**
- Equipamento: ganha um **slot de equipamento** novo na tela do inventário (não fica na hotbar).
- Receita: 10 Fe + 6 Si + 4 gelo.
- O₂ máximo de 100 s → **~220 s**. A barra do HUD fica proporcional ao máximo.

**Scanner de navegação**
- O jogo **registra os tiles vistos desde o início**, em cada camada. Quando o scanner chega, o mapa já vem com o que foi explorado.
- **Minimapa** no canto do HUD; **M** abre o mapa grande.
- **Névoa de guerra**: o que não foi visto fica preto.
- No mapa aparecem marcados a base, a cratera, os destroços vistos e os veios vistos.
- **Um mapa por camada**. Na caverna, "visto" é o que a luz revelou.

**LOGs novos**
3 a 4 logs sobre a colônia, a Dra. Ilves e o nível 2, sem resolver o mistério do gelo. O gerente escreve a primeira versão e o dono aprova o texto.

## Marco 4 · Polimento

Balanceamento com o simulador e playtest do dono.

## Técnico

**Estrutura**
- O `GameState` passa a ter **camadas**. Cada camada tem mapa, máquinas, itens no chão, baús e explorado; inventário, energia, Ti, drones (só superfície) e objetivos ficam globais.
- Módulos novos, pequenos e testáveis isoladamente:

| Módulo | Faz |
|---|---|
| `layers.py` | camadas e troca entre elas |
| `surface_gen.py` | gerador do deserto |
| `pickups.py` | recursos soltos e reaparecimento |
| `wrecks.py` | destroços, saque e projetos |
| `lighting.py` | escuridão e fontes de luz |
| `explore.py` | tiles vistos e minimapa |
| `equipment.py` | slot de equipamento |

- O gerador atual (`world.py`) vira o gerador da caverna.

**Save**
- **v6**, sem migração do v5. Na tela de título, save antigo mostra "Save de uma versão antiga · comece um novo jogo".

**Desempenho**
- O smoke mede o tempo por frame com a caverna escura e 30 luminárias acesas, e com a superfície de 192×192.
- Limite: 16,7 ms por frame.

**Arte** (Designer · tudo passa pelo dono, entregue em `_pending/`)
- **Superfície**: chão de areia/cascalho nos 3 estágios, morros, cordilheira da borda, rocha pequena, recursos soltos e cratera (fechada e com rampa).
- **Destroços**: os 3 tipos, caixa de saque (cheia e vazia) e item de projeto.
- **Caverna**: rampa de subida e luminária.
- **Itens e interface**: tanque de O₂, ícone do scanner, moldura do minimapa e slot de equipamento.
- O contrato exato (nomes e tamanhos) entra na bíblia antes da Designer começar cada marco.

**Som** (Som · passa pelo dono)
- **Ambiente do deserto**: vento seco e espaçoso, sem bicho.
- **Ambiente da caverna**: grave, com gotejar e eco.
- **Efeitos**:
  - descer e subir a rampa;
  - pegar recurso solto;
  - abrir caixa de saque;
  - projeto encontrado (som de conquista);
  - colocar luminária.

**Testes**
- Cada módulo novo tem os próprios testes.
- O smoke ganha prints da superfície, da caverna escura com luminárias, dos destroços, do minimapa e da troca de camada.
- O simulador ganha a estratégia "explorar e descer". Referência de duração: 25–40 min (o dono disse que tempo de partida não é foco agora).

**Processo**
- Um marco por vez.
- Arte e som de cada marco são pedidos no começo do marco. O código usa placeholders até o dono aprovar.
- Devs em paralelo vão em worktree, e o gerente faz o merge.
