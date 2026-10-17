# v0.8 M6 · Task 2: seção DRONES do Cultivador, do Microscópio e da Centrífuga no Grande

**Status:** cabe nos 3 tamanhos × nv.1/T2, com os botões, a janela do lado e a linha de ajuda acima da moldura da
hotbar.

1. **Primeira passada (plano):** fileira compacta + `*_LOGI_Y` encostado. Não bastou no Grande; sobravam 16–20 px.
2. **Segunda passada (decisão do dono, opções 1 + 2):**
   - folga de baixo 10 → 4 nas 3 do lab;
   - no Cultivador, o estado vai à direita do MUDA, em até 2 linhas;
   - no Microscópio e na Centrífuga, o estado e a explicação dividem uma linha.

Os 6 `xfail` saíram e todos os casos passam de verdade.

## Medição final (moldura = `hotbar_y - 11 - 1 - HELP_H` = 214 no Grande)

Valores em px abaixo (−) ou além (+) da moldura. A nv.1 e a T2 dão o mesmo número.

| Máquina | Tamanho | Botões | Janela do lado | Inventário |
|---|---|---|---|---|
| Cultivador | 480×270 | −4 | 0 (encosta) | −59 (T2) / −91 (nv.1) |
| Cultivador | 640×360 | −33 | −29 | −88 / −120 |
| Cultivador | 960×540 | −123 | −119 | −178 / −210 |
| Microscópio | 480×270 | −4 | 0 | −59 / −91 |
| Microscópio | 640×360 | −33 | −29 | −88 / −120 |
| Microscópio | 960×540 | −123 | −119 | −178 / −210 |
| Centrífuga | 480×270 | −4 | 0 | −59 / −91 |
| Centrífuga | 640×360 | −33 | −29 | −88 / −120 |
| Centrífuga | 960×540 | −123 | −119 | −178 / −210 |

As três janelas do lado do lab têm agora a mesma altura: 135 + 68 + 4 = 207. O `window_room` do Grande é 210; a
janela começa em y=7, então a base fica em 214, exatamente na moldura.

### De onde saiu cada px no Grande (janela do lado; antes → depois)

| | Cultivador | Microscópio | Centrífuga |
|---|---|---|---|
| Antes de tudo | +59 | +38 | +34 |
| Fileira compacta (seção 107/82 → 68) | −39 | −14 | −14 |
| `*_LOGI_Y` encostado (1ª passada) | 0 | −8 (156 → 148) | −3 (152 → 149) |
| Uma linha de texto a menos (2ª passada) | −17 (152 → 135) | −13 (148 → 135) | −14 (149 → 135) |
| Folga de baixo 10 → 4 | −6 | −6 | −6 |
| Resultado | −3 | −3 | −3 |

Com 3 px de folga, a janela desce de y=4 pra y=7 (`window_top` cola a base na moldura): por isso a tabela de cima mostra 0.

## Medição da 1ª passada (só o plano, antes da decisão do dono)
 (moldura = `hotbar_y - 11 - 1 - HELP_H` = 214 no Grande)

Chip ligado; Envia e Recebe com tudo o que a máquina aceita. Valores em px acima (−) ou abaixo (+) da moldura.
"Janela" é a janela do lado (`side_window`). É ela que manda: a linha de ajuda vai em `y + h + 7`. A janela
"Inventário" (`inv_window`) fica com folga em todos os casos (−62 com a T2 no Grande).

| Máquina | Tamanho | Botões antes | Botões depois | Janela antes | Janela depois |
|---|---|---|---|---|---|
| Cultivador | 480×270 | **+49** | **+10** | **+59** | **+20** |
| Cultivador | 640×360 | −10 | −27 | 0 | −17 |
| Cultivador | 960×540 | −98 | −117 | −88 | −107 |
| Microscópio | 480×270 | **+28** | **+6** | **+38** | **+16** |
| Microscópio | 640×360 | −18 | −29 | −8 | −19 |
| Microscópio | 960×540 | −108 | −119 | −98 | −109 |
| Centrífuga | 480×270 | **+24** | **+7** | **+34** | **+17** |
| Centrífuga | 640×360 | −20 | −29 | −10 | −19 |
| Centrífuga | 960×540 | −110 | −119 | −100 | −109 |

A mochila nv.1 e a T2 dão o mesmo número (a janela do lado é mais alta que a do Inventário nas duas).

A altura da seção DRONES caiu de 107 pra 68 no Cultivador e de 82 pra 68 no Microscópio e na Centrífuga. Antes, o
Envia do Cultivador (5 itens) quebrava em 2 linhas de 25.

### Quanto cada `*_LOGI_Y` subiu (regra 5)

O texto do corpo (Pixelify 11) ocupa 14 px; a tinta vai da linha 0 à 13, por causa dos acentos e do "g".

- **Cultivador:** 152 → 152 (0 px). O estado em y+138 termina em y+152; já estava encostado.
- **Microscópio:** 156 → 148 (**8 px**). A explicação em y+134 termina em y+148.
- **Centrífuga:** 152 → 149 (**3 px**). A explicação em y+135 termina em y+149.

### O que falta no Grande

A janela do lado precisa encolher **20 px** (Cultivador), **16** (Microscópio) ou **17** (Centrífuga). A seção
DRONES compacta já está no mínimo: cabeçalho 14 + Envia 18 + Recebe 18 + Lote 18 = 68. Juntar duas fileiras numa
linha não cabe ao lado do chip (150 px): Cultivador 5+1, Centrífuga 3+4; o Microscópio 3+1 dá 153.

## O que mudou

- **`game/ui.py`**
  - **1ª passada:**
    - `COMPACT_LOGI` e as funções `logi_wide`, `logi_wide_room` e `wide_cols`;
    - `wide_label_inline` e `wide_row_height` com `room` opcional;
    - `draw_logistics` e `logistics_height` com a mesma conta;
    - Microscópio e Centrífuga sem o `max(LOGI_H, …)`;
    - o `self.side_window`, pro teste.
  - **2ª passada:**
    - `CULT_LOGI_Y`, `MIC_LOGI_Y` e `CENT_LOGI_Y` = 135. `LAB_PAD = 4` é a folga de baixo nas 3 do lab; as outras
      máquinas continuam com 10.
    - **Cultivador:**
      - o passo CHEIAS → VAZIAS → MUDA caiu de 40 pra 36 (`CULT_ROW_STEP`). Os rótulos têm 32/33 px, então sobram
        3 px entre eles;
      - o estado foi pra direita do MUDA (`CULT_STATUS_X` = 100, `CULT_STATUS_W` = 74), quebrando por palavra em até
        2 linhas. Com 1 linha, fica centrado no slot.
    - **Microscópio e Centrífuga:** novo `_status_line`, com o estado na cor e a explicação apagada 8 px depois, na
      mesma linha (y+121).
    - **Centrífuga:** o "30 s por ciclo" virou "30 S" embaixo do slot da AMOSTRA, no mesmo molde do "20 S" do
      Microscópio. Antes ele sumia quando o estado era comprido; agora aparece sempre.
- **`game/app.py`**: textos encurtados. Veja "Diferente do plano".
- **`tests/test_m6_drones_fit_v08.py`**
  - Sem `xfail`.
  - 3 máquinas × 3 tamanhos × nv.1/T2: os botões, a `inv_window` e a `side_window` ≤ moldura, e a linha de ajuda
    (`side_window.bottom + HELP_H`) acima da moldura da hotbar.
  - Toggles: a contagem e a ordem são as de antes; 16×16; o Lote continua 22×16; o clique acerta.
  - A fileira e o rótulo param antes do chip.
  - A linha DRONES não sobrepõe o texto de cima.
  - `logistics_height` é igual ao que é desenhado.
  - **Novos:**
    - os 5 estados do Cultivador cabem em ≤ 2 linhas de 74 px sem cortar palavra, e os rótulos CHEIAS, VAZIAS e MUDA
      não encostam;
    - todos os pares (estado, explicação) reais do Microscópio e da Centrífuga cabem em `GRID_W` numa linha.
- **`tests/test_m5_chest_fit_v08.py`**: a Fundição continua 22×22, e entrou um caso que confere o Cultivador em 16×16.
- **`tests/test_m4_panels_v08.py`**: o texto esperado de `centrifuge_info()` sem amostra virou "Alga + amostra".
- **`tools/dev/shot_v08_m6_drones.py`**: os prints. Aceita uma pasta de saída como argumento.

## Testes

`uv run pytest -q tests/test_m6_drones_fit_v08.py tests/test_m5_chest_fit_v08.py tests/test_m4_panels_v08.py tests/test_ui_size.py tests/test_chest_sizes.py tests/test_backpack.py tests/test_ui_b2.py tests/test_cultivator_v08.py tests/test_chip.py tests/test_samples_v08.py`

```
293 passed in 5.02s
```

## Prints (Grande 480×270, T2, chip, tudo ligado), conferidos com Read

- `reports/dev/v08_m6_drones_cultivador.png`: "Fora da base / vedada" em 2 linhas à direita do MUDA. A ajuda está
  acima da hotbar.
- `reports/dev/v08_m6_drones_microscopio.png`: "Analisando  Metade: nada" numa linha.
- `reports/dev/v08_m6_drones_centrifuga.png`: "Girando  Falha: perde as 2" numa linha e o "30 S" embaixo da AMOSTRA.

Nos três:
- os rótulos "Envia"/"Recebe" ficam longe do chip;
- a linha DRONES não encosta no texto de cima;
- a janela do lado e a ajuda ficam acima da moldura da hotbar.

## Diferente do plano

- **O plano sozinho não fechava o Grande.** Entraram as opções 1 + 2 do dono.
- **O teste confere também a `side_window` e a linha de ajuda**, não só os botões e a `inv_window`.
- **A fileira compacta respeita o chip por conta geral** (`wide_cols(room)`: 8 colunas com chip).
- **Textos encurtados**, porque não cabiam numa linha ao lado do estado:

  | Onde | Antes | Depois |
  |---|---|---|
  | Microscópio | "Metade do gelo não dá nada." (161 px) | "Metade: nada" (78 px). A faixa de cima já diz "NADA 50%". |
  | Microscópio, no déficit | "Metade: nada · ritmo N%" | "Ritmo N%" (o "nada" já está na faixa) |
  | Centrífuga, sem amostra | "Alga + amostra = planta nova" | "Alga + amostra" |
  | Centrífuga, com amostra | "Falhou: gasta alga e amostra." | "Falha: perde as 2" |

  O pior par real é "Sem amostra" + "Alga + amostra" = 173 px, de 174.
- **O "30 s por ciclo" da Centrífuga virou "30 S"** e mudou de lugar (embaixo da AMOSTRA). Não sumiu.
- **Os 3 slots do Cultivador ficaram 4 px mais juntos** (passo 40 → 36).

## Riscos

- **Margem zero no Grande:** a janela do lado encosta na moldura. Qualquer px a mais nesses painéis faz o teste
  falhar, o que é o comportamento desejado.
- **"Sem amostra" + "Alga + amostra" sobra 1 px.** Se o texto mudar, o teste de pares pega.
- **"Fora da base" tem exatamente os 74 px da área.** Se um estado novo tiver uma palavra com mais de 74 px, ele não
  quebra; o teste do Cultivador pega, desde que o estado entre na lista `CULT_STATUS`. A lista copia
  `App.cultivator_label` à mão.
- **A cara das 3 máquinas mudou** (toggles 16×16, o estado de lugar, textos mais curtos). É UI: o dono vê os prints.
- **`tools/sprites/v08_m4_paineis.py`** (o gerador do mock antigo) ainda usa `LOGI_H` = 82. Não afeta o jogo.
