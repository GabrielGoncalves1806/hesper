# v0.8 M4 · Task 7: Painéis do Microscópio e da Centrífuga

Layout: mock A (`reports/design/v08_m4_paineis/ui_*_A.png`). Prints headless em `reports/dev/`:
- `v08_m4_painel_microscopio.png`
- `v08_m4_painel_centrifuga.png`
- `v08_m4_painel_centrifuga_sem_amostra.png` (sem amostra: o cartão some e as 3 chances ficam apagadas)

## O que entrou
- **`game/ui.py`**:
  - `_microscope_panel` e `_centrifuge_panel`, com os helpers `_lab_bar`, `_lab_machine` e `_lab_output`;
  - `MIC_LOGI_Y = 156` e `CENT_LOGI_Y = 152`, mais `SAMPLE_COLOR` (as cores do mock) e `SAMPLE_SHORT`;
  - a altura do painel usa `max(LOGI_H, logistics_height)`.
- **`game/app.py`**:
  - os modos `"microscope"` e `"centrifuge"` em `INVENTORY_MODES` e `PANEL_MODES`, com `open_microscope` e `open_centrifuge`;
  - E abre o painel, e ele fecha no `set_mode` e no `start_game`;
  - recusas, clique e shift+clique (com o chip);
  - `take_microscope` / `take_centrifuge`: `take_outputs` pega só as saídas, e a entrada fica;
  - status e info, a seção DRONES (clique e dica);
  - o rótulo do E: "[E] Microscópio" / "[E] Centrífuga";
  - a dica do mouse em cima da máquina;
  - os avisos flutuantes de `sample_found` e `centrifuge_done`. O som só toca se `sample_found.wav` / `centrifuge_done.wav` existir. Não tem canal de loop.
- **`App.panel_machine_art(m)`** monta a máquina ampliada a partir de `Renderer.surface` e `anim_surface`, que já são públicos, mais `anim_frame_index`. Assim o `render.py` ficou intocado e não briga com a Task 6. A tira anda só analisando ou girando e com energia, a 5 fps no Microscópio e a `CENTRIFUGE_FPS` na Centrífuga.
- **`tests/test_m4_panels_v08.py`** (16 testes): os modos; o E abre e fecha; os rótulos; o status de cada trava; as recusas; clique e shift+clique; o "pegar tudo" não tira a entrada; o desenho pelo App (`draw()`) com e sem amostra; a seção DRONES cabe na altura; os floaters; a dica do mouse.
- **O teste da altura não depende da Task 5.** Ele faz um monkeypatch de `drones.can_send` / `can_receive` com as regras da tabela da Task 5. O script dos prints faz o mesmo.

## Diferente do mock (e por quê)
- **A barra vertical** foi pra `gx+44`, e o mock a punha em `gx+40`. Na fonte do jogo, o "AMOSTRA" (42 px) encostava na barra. O rótulo ANÁLISE/CICLO fica centrado nela.
- **Os textos de baixo** mudaram porque a Pixelify do jogo é mais larga que a do mock (a grade tem 174 px):
  - Microscópio: "Metade do gelo não dá nada." no lugar de "Metade das análises não dá nada.", que tem 194 px e cortava. No déficit de energia, vira "Metade: nada · ritmo X%";
  - cartão da Centrífuga: "Amostra mutação". O `SAMPLE_NAME` "Amostra com mutação" cortava;
  - Centrífuga sem amostra: "Alga + amostra = planta nova". A fonte não tem o "→" do plano, que saía como um quadrado.
- **A altura do painel** fica em 248 / 244, e o mock dizia 240 / 238. O `LOGI_Y` é o do mock (156 / 152), mas a seção DRONES tem 82 + 10 de margem. Cabe nos 270, igual ao Cultivador (244).
- **Plano × mock nas linhas de info:** o plano pedia "1 gelo a cada 20 s · metade não dá nada" e "Amostra simples · 60% de dar Folha-gota". Segui o mock aprovado:
  - o tempo vai embaixo do slot de gelo ("20 S") e ao lado do status ("30 s por ciclo");
  - a chance está no cartão;
  - a linha de baixo da Centrífuga com amostra diz "Falhou: gasta alga e amostra.".
- **Sem a Task 5 no branch,** as duas máquinas usam a regra padrão do drone, a do baú: 16 itens, fileira larga. O painel fica mais alto até o merge, mas funciona. Com a Task 5, fica como nos prints.

## Verificação
`uv run pytest tests/test_m4_panels_v08.py tests/test_ui_b2.py tests/test_ui_size.py tests/test_water_v08.py tests/test_cultivator_v08.py tests/test_microscope_v08.py tests/test_centrifuge_v08.py -q` → 243 passed.
Não rodei o pytest inteiro nem o smoke, e não commitei.
