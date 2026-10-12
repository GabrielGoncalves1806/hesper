# v0.3 Marco 3 · Destroços, projetos, tanque de O₂ e scanner · Plano de implementação

> **Para agentes:** SUB-SKILL: superpowers:executing-plans (inline) ou superpowers:subagent-driven-development. Passos em checkbox (`- [ ]`).
> **Neste projeto agentes NÃO commitam**: no lugar de "commit", cada tarefa termina com `uv run pytest` verde; quem commita é o gerente.

**Objetivo:** o deserto ganha 6–8 destroços (nave de carga, módulo da colônia, sonda) com caixa de saque, LOGs 04–07 e projetos que liberam receitas (tanque de O₂, scanner de navegação, luminária forte); o inventário ganha slots de equipamento; o jogo registra o que foi visto em cada camada e o scanner mostra minimapa + mapa grande (M) com névoa de guerra.

**Arquitetura:** a geometria dos destroços é estática e sai da seed: `game/wrecks.py` sorteia posição/tipo/conteúdo e o `surface_gen` carimba no `World` (tiles `WRECK` = sólido baixo, caixa = `CRATE` = sólido baixo; `world.wrecks`). O estado que muda (conteúdo de cada caixa) fica na camada (`Layer.crates`, como os soltos). Projetos são itens (`bp_*`) que, ao sair da caixa, viram `state.blueprints` e somem. Equipamento (`game/equipment.py`) é um dict de slots tipados no `GameState`. Explorado (`game/explore.py`) é um bytearray por camada, atualizado a cada 0,2 s, com lista de tiles novos que o minimapa (render, incremental) consome.

**Stack:** Python 3.13, pygame-ce, uv, pytest.

## Restrições globais
- Destroços 6–8 na superfície, distâncias crescentes (~30 tiles até perto da borda), sem sobrepor morros/veios/cratera/base, pela seed. Área sólida. Caixa e terminal com chão livre ao lado.
- Sprites (pendentes, fallback por código até a promoção): `wreck_cargo` 128×112 (4×3, blit (tx·32, ty·32−16), caixa (tx+1, ty+3)); `wreck_module` 96×88 (3×2, blit (tx·32, ty·32−24), terminal (tx+2, ty+1), caixa (tx, ty+2)); `wreck_probe` 64×64 (2×2, blit (tx·32, ty·32), caixa (tx+2, ty+1)); `loot_crate`/`loot_crate_empty` 32×32 blit (tx·32, ty·32), ordenada por (ty+1)·32; `icon_blueprint`, `icon_o2_tank`, `icon_scanner` 16×16.
- Caixa: E abre painel tipo baú, só tirar (esquerdo pilha, direito 1, Pegar tudo). Conteúdo pela seed, fixo; vazia troca sprite e dica "vazia".
- Projetos: entram e somem, liberam receita, aviso "PROJETO: <NOME>"; `blueprint_found` ~0,4 s depois do `crate_open`, ambiente a ~60% por 2 s. Receita trancada: "??? · projeto não encontrado".
- Tanque: 10 Fe + 6 Si + 4 gelo; equipado → O₂ máx 220 s; barra proporcional; som `equip` (tirar: `inv_move`). Save.
- Explorado desde o início, por camada; scanner → minimapa + M (som `map_open`, máx 1 a cada 0,3 s). Névoa = preto. Marcadores: base, cratera/rampa, destroços vistos, veios vistos, player. Minimapa incremental.
- Save: v6 continua (campos novos com padrão); saves do Marco 1/2 carregam.
- UI: nada de UW/UH/HOTBAR fixos em código novo; mouse via `app.mouse_ui`. Não abrir janela, não commitar, não mexer em assets/, tools/sprites, tools/audio, reports/design, reports/audio, saves/, settings.json, biomas.

## Decisões (as [revisar] o dono deveria ver)
- **[revisar]** Sequência dos destroços por distância (n = 6..8): `cargo` (tanque + LOG 04), `probe`, `module` (scanner + LOG 05), `cargo` (luminária forte), `probe` (LOG 06), [`cargo`, `probe` extras se n ≥ 7/8], `module` (LOG 07, o mais longe).
- **[revisar]** LOG 04 e 06 (nave e sonda não têm terminal no sprite): abrir a caixa pela 1ª vez mostra o registro na tela de terminal ("REGISTRO DE BORDO"); [E] continua e abre a caixa. O painel da caixa tem "Ler registro" pra reler.
- **[revisar]** O projeto é pego sozinho ao abrir a caixa (o som do Som foi feito assim: crate_open → 0,45 s → blueprint_found). Recurso continua na caixa pra pegar à mão.
- **[revisar]** Scanner = equipamento (receita barata 4 Fe + 4 Si após o projeto). 2 slots tipados na tela do Tab: TANQUE e SCANNER. Clique esquerdo num item de equipamento (mão vazia) equipa; clique no slot equipado tira. Soltar o item da mão no slot também equipa.
- **[revisar]** Aba nova do fabricador "Traje" (tanque e scanner); "Luminária forte" (raio 7, 2 Fe + 2 Si + 1 gelo) na aba "Luz".
- **[revisar]** Objetivos depois de "Coloque uma luminária": "Ache um destroço", "Ache o projeto do tanque de O2", "Fabrique e equipe o tanque de O2".
- Drill nv.2: **fora** (precisaria de máquina nova com sprite, lógica de drill por tipo, drones e save; não é "simples").
- Alarme de O₂ e tela vermelha continuam por segundos restantes (25 s), com ou sem tanque.
- Explorado: superfície = retângulo de 20×12 tiles de meia-largura em volta do player (a tela no zoom 0,75); caverna = círculos das luzes (lanterna 4, luminária 5/7, rampa 3,5, terminal 2, máquina 1,8), a cada 0,2 s.
- Bug dos "pontinhos brancos" na caverna: são os glints de silício (#c3d1e2) e gelo (#a6ecff), quase brancos, espalhados por TODA rocha (inclusive no miolo da parede) = céu estrelado. Correção: glint só em minério com chão do lado (borda visível do túnel) e na cor de sombra do minério (mais saturada), sem o "+30" de branco.

---

## Estrutura de arquivos

| Arquivo | Muda o quê |
|---|---|
| `game/config.py` | tiles `WRECK`/`CRATE`, constantes de destroço, `LOGS` 04–07 + títulos, máquinas `o2_tank`, `scanner`, `lamp_t2`, `BLUEPRINTS`, aba "Traje", `O2_TANK_MAX`, explorado, volumes novos |
| `game/wrecks.py` (novo) | `WreckSpec`, `Wreck`, `place_wrecks(world, rng)`, `crate_loot(wreck, seed)`, `make_crates(world, seed)` |
| `game/equipment.py` (novo) | `Equipment` (slots tipados, equip/unequip, to/from data), `o2_max(eq)` |
| `game/explore.py` (novo) | `Explored` (bytearray, reveal_rect/circle, fresh, save comprimido), `reveal_for(state)` |
| `game/surface_gen.py` | chama `place_wrecks`, rochas pequenas longe dos destroços, `_copy` copia `wrecks` |
| `game/world.py` | `wrecks` no World, `wreck_at`, `crate_at` |
| `game/layers.py` | `Layer.crates`, `Layer.explored` |
| `game/systems.py` | blueprints, recipe_status "blueprint", crate (abrir/tirar), terminal de destroço, equipamento, o2_max, explorar, wrecks_visited |
| `game/objectives.py` | 3 objetivos |
| `game/save.py` | crates, explored, blueprints, equipment, wrecks_visited, logs 0..6 |
| `game/art.py` | fallbacks: destroços, caixa, ícones, luminária forte |
| `game/render.py` | destroços e caixas na ordenação, contorno, glint corrigido, `Minimap` incremental |
| `game/lighting.py` | `ore_glints` só em minério exposto, cor saturada |
| `game/ui.py` | painel da caixa, slots de equipamento, aviso PROJETO, fabricador "???", minimapa e mapa grande, terminal com título por LOG, barra de O₂ proporcional |
| `game/app.py` | E na caixa/terminal do destroço, modo "map" (M), equipar por clique, sons, dicas |
| `tools/dev/balance_sim.py` | estratégia com destroços |
| `tools/dev/smoke.py` | prints novos |
| testes | `tests/test_wrecks.py`, `tests/test_equipment.py`, `tests/test_explore.py`; ajustes em save/objectives/fabricator |

---

### Task 1: destroços no deserto (`wrecks.py` + surface_gen)
**Interfaces:** `WRECK_SPECS[kind] -> WreckSpec(size=(w,h), sprite=(w,h), lift, crate=(dx,dy), terminal=(dx,dy)|None)`; `Wreck(kind, tx, ty, rank, log: int|None, blueprint: str|None)` com `.tiles`, `.crate`, `.terminal`, `.center`; `place_wrecks(world, rng) -> list[Wreck]`; `crate_loot(wreck, seed) -> list[(item, n)]`.
- [ ] Teste (`tests/test_wrecks.py`): 6–8 destroços em várias seeds; distâncias crescentes, 1º entre 26 e 36, último ≥ 70; tiles do destroço `WRECK`, caixa `CRATE`; nenhum tile de veio/cratera/morro/borda/zona da base; caixa e terminal com vizinho de areia alcançável a pé da base (BFS); 1º é cargo com `bp_o2_tank` e log 3; existe module com `bp_scanner` e log 4; o último é module com log 6; conteúdo igual pra mesma seed.
- [ ] Rodar: falha (módulo não existe).
- [ ] Implementar `game/wrecks.py` e chamar em `surface_gen._build` depois dos veios; `_small_rocks` pula a folga dos destroços; `_copy` copia `wrecks`.
- [ ] `uv run pytest tests/test_wrecks.py tests/test_surface_gen.py` verde.

### Task 2: caixas e projetos no GameState
**Interfaces:** `Layer.crates: dict[(tx,ty)] -> Crate(wreck, storage: Inventory, opened: bool)`; `GameState.open_crate(crate) -> list[str]` (blueprints novos); `GameState.crate_take(crate, index|None, amount|None) -> int`; `GameState.blueprints: set[str]`; `recipe_status(kind)` → `"blueprint"`; evento `("blueprint", id)`, `("crate_open", empty: bool)`.
- [ ] Teste: abrir a caixa da nave mais perto libera `o2_tank` (some do conteúdo, não ocupa inventário); receita trancada antes; tirar pilha/1/tudo; caixa vazia; inventário cheio deixa na caixa.
- [ ] Implementar (systems + interação E: `("crate", crate)` e `("wreck_terminal", wreck)`; alcance 48 px).
- [ ] pytest verde.

### Task 3: equipamento e tanque
**Interfaces:** `Equipment.slots: dict[str, str|None]` (chaves `C.EQUIP_SLOTS`), `equip(item) -> str|None` (o que saiu), `unequip(slot) -> str|None`; `GameState.equip_from(index) -> bool`, `GameState.unequip(slot) -> bool`, `GameState.o2_max`.
- [ ] Teste: tanque no slot → o2_max 220; tirar com O₂ 180 corta pra 100; refill vai até 220; trocar; sem espaço não tira; scanner idem; `equipped_ever`.
- [ ] Implementar. pytest verde.

### Task 4: explorado
**Interfaces:** `Explored(w, h)`: `reveal_rect(cx, cy, hx, hy)`, `reveal_circle(cx, cy, r)`, `seen(x, y)`, `take_fresh() -> list[(x,y)]`, `to_data() -> str`, `from_data(w, h, s)`; `GameState._update_explore(dt)`.
- [ ] Teste: começa vazio; após update na superfície vê o retângulo; caverna vê só o círculo da lanterna + luminárias; ida e volta do save idêntica e curta (< 2 KB pra mapa novo).
- [ ] Implementar. pytest verde.

### Task 5: save
- [ ] Teste: ida e volta com caixa saqueada, blueprints, equipamento, explorado, wrecks_visited; save v6 sem os campos carrega com padrão (caixas cheias, nada equipado, nada visto).
- [ ] Implementar. pytest verde.

### Task 6: objetivos
- [ ] Teste: sequência "Ache um destroço" → "Ache o projeto do tanque de O2" → "Fabrique e equipe o tanque de O2" depois de "Coloque uma luminária".
- [ ] Implementar. pytest verde.

### Task 7: visual (art, render, ui, app) + glint
- [ ] Teste de lógica do glint (`ore_glints` ignora minério sem chão do lado); teste do fabricador (`??? · projeto não encontrado` via `recipe_status`); teste do minimapa (pinta só tiles frescos).
- [ ] Fallbacks em art; destroços/caixas no render; painel da caixa, slots de equipamento, aviso PROJETO, fabricador trancado, minimapa e mapa grande no ui; app: E, M, cliques, sons, dicas.
- [ ] pytest verde; smoke.

### Task 8: simulador, smoke, bíblia e README
- [ ] `balance_sim`: estratégia "destroços" (vai à nave mais perto, pega o tanque, fabrica e equipa; minera na caverna com 220 s).
- [ ] Smoke com os 9 prints; olhar todos.
- [ ] Bíblia §9 "Marco 3 · como ficou" e README.
