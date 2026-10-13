# Créditos de áudio

Todos os sons em `assets/audio/` são gerados por síntese procedural em
`tools/audio/build_audio.py` (obra própria do projeto), **exceto** os listados abaixo.

## Kenney · Impact Sounds (1.0)

- Autor: Kenney (www.kenney.nl)
- Fonte: https://kenney.nl/assets/impact-sounds
  (zip baixado em `tools/audio/vendor/kenney_impact/kenney_impact-sounds.zip`)
- Licença: **Creative Commons Zero (CC0 1.0)**, domínio público.
  http://creativecommons.org/publicdomain/zero/1.0/
  Conferida no `License.txt` do pack e na página do asset. Crédito não é obrigatório,
  mas fica registrado aqui.

| Arquivo no projeto | Origem no pack | Tratamento |
|---|---|---|
| `candidates/mine_hit_B1.wav` | `Audio/impactMining_001.ogg` | mono, 44,1 kHz, corte em 0,28 s, passa-alta 40 Hz, normalizado |
| `candidates/mine_hit_B2.wav` | `Audio/impactMining_004.ogg` | mono, 44,1 kHz, corte em 0,25 s, passa-alta 180 Hz, normalizado |
| `candidates/mine_hit_B3.wav` | `Audio/impactMining_002.ogg` | mono, 44,1 kHz, corte em 0,25 s, passa-alta 100 Hz, normalizado |
| `candidates/mine_break_B1.wav` | `Audio/impactMining_003.ogg` | mono, 44,1 kHz, corte em 0,55 s, passa-alta 40 Hz, misturado com o `mine_break` v3 sintético |
| `candidates/ramp_down_B1.wav` | `Audio/footstep_concrete_000.ogg` a `_003.ogg` | mono, 44,1 kHz, passa-alta 60 Hz, 4 passos em sequência com passa-baixa progressivo, reverb sintético e ar grave sintético (v8.1) |
| `candidates/ramp_up_B1.wav` | `Audio/footstep_concrete_000.ogg` a `_003.ogg` | idem, na ordem inversa da progressão (v8.1) |

Se uma candidata B virar o som oficial, esta tabela continua valendo pro arquivo final.

## v11 · Gelo e água a partir de gravações (aprovado pelo dono, oficial em `assets/audio/`)

`ice_crack`, `ice_crack_1`, `ice_collapse`, `amb_rain`, `amb_rain_light`, `amb_rain_heavy` e
`vent_hiss` saem de gravações livres tratadas por `tools/audio/build_audio.py` (o peso grave
do gelo é síntese própria). Todos foram baixados sem login. Os originais (ou os recortes sem
perda) ficam em `tools/audio/vendor/<fonte>/` com um `SOURCE.txt` (URL, sha256 e o que foi
feito). Tudo foi só lido como áudio, nada foi executado.

### Texto pronto pra tela de créditos (obrigatório se o jogo for publicado)

O IR da capela de Aachen é **CC BY 4.0**: dar crédito é condição da licença. O aviso do NPS é
o que o próprio NPS pede numa publicação comercial. Os CC0 não exigem nada, mas é educado citar.

> **Reverb (resposta ao impulso):** "St. Nicholas Chapel, Aachen Cathedral, room impulse
> responses" por Martin Zerwas e Selin Kayku (https://doi.org/10.5281/zenodo.20428705),
> licenciado sob CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). **Modificado**:
> canal omnidirecional, cauda encurtada e filtrada.
>
> **Fumarola:** gravação "Fumarole (large)", Yellowstone Sound Library, National Park Service
> (NPS/Jennifer Jerrett). No claim to original U.S. Government works.
>
> **Chuva e gelo (CC0):** Kresiek The Furry, IgnasD e rubberduck (OpenGameArt.org).

### OpenGameArt · "AMB Rain Loop 2"

- Autor: Kresiek The Furry
- Fonte: https://opengameart.org/content/amb-rain-loop-2 (`amb_rain2.flac`, GoPro Hero 12 em áudio bruto, 12 min)
- Licença: **CC0 1.0**, domínio público. Conferida na página.

| Arquivo | Origem | Tratamento |
|---|---|---|
| `amb_rain.wav` | trecho 404–432 s | mono, 44,1 kHz, de-click leve só acima de 2 kHz (gota no máximo +5 dB sobre o véu), passa-alta 250 Hz, passa-baixa 6 kHz, loop de 24 s com crossfade de potência constante de 3 s |
| `amb_rain_light.wav` | trecho 520–548 s | idem, passa-alta 280 Hz e passa-baixa 3,2 kHz (mais longe e mais fina) |
| `amb_rain_heavy.wav` | trechos 282–310 s + 318–346 s somados | idem, as duas camadas juntas (o dobro de gotas), passa-alta 220 Hz e passa-baixa 7 kHz |

### OpenGameArt · "Ice breaking/shattering"

- Autor: IgnasD
- Fonte: https://opengameart.org/content/ice-breakingshattering (`IceShatters_0.zip`)
- Licença: **CC0 1.0**. Conferida na página.

### OpenGameArt · "75 CC0 breaking / falling / hit sfx"

- Autor: rubberduck
- Fonte: https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (`sfx_breaking_and_falling.zip`)
- Licença: **CC0 1.0**. Conferida na página.

| Arquivo | Origem | Tratamento |
|---|---|---|
| `ice_crack.wav` | IgnasD `LedasLuzta4` (−4 semitons) + rubberduck `bfh1_breaking_02` (−2 st) | mono, 44,1 kHz, peso grave de ruído sintético (sem seno), microestalos recortados de `LedasLuzta`/`2`/`4` (−2 a −6 st), compressão leve, passa-baixa 5,2 kHz, reverb por convolução com o IR de Aachen (abaixo), corte em 1,9 s |
| `ice_crack_1.wav` | IgnasD `LedasLuzta33` (−3 st) e `LedasLuzta2` (−4,5 st, 0,22 s depois) + rubberduck `bfh1_breaking_03` (−3 st) | idem |
| `ice_collapse.wav` | IgnasD `LedasLuzta5` (−5 st) e `LedasLuzta33` (−6 st) + rubberduck `bfh1_rock_breaking_01` (−3 st); pedaços caindo: rubberduck `bfh1_rock_falling_03/04/06/07/08` (−3 a −7 st) e grãos do IgnasD (−1 a −5 st) | idem, mais ronco e "whump" de ruído sintético, passa-baixa 4,8 kHz, reverb mais molhado, corte em 2,4 s |

### U.S. National Park Service · Yellowstone Sound Library

- Autor: NPS/Jennifer Jerrett ("Fumarole (large)", Norris Geyser Basin, 2014)
- Fonte: https://www.nps.gov/yell/learn/photosmultimedia/sounds-fumaroles.htm (`yell-NorrisPorcelainBasinFumerole.mp3`)
- Licença: **domínio público** (obra do governo dos EUA, 17 U.S.C. §105), conforme o aviso
  oficial do NPS (https://www.nps.gov/aboutus/disclaimer.htm). Não é CC0, mas tem o mesmo efeito
  prático. O NPS pede, numa publicação comercial, um aviso como "No claim to original U.S.
  Government works", e agradece o crédito "National Park Service".

| Arquivo | Origem | Tratamento |
|---|---|---|
| `vent_hiss.wav` | do 4 s em diante (antes é o fade de entrada do arquivo) | mono, 44,1 kHz, passa-alta 60 Hz, passa-baixa 3 kHz, loop de 20 s com crossfade de 3 s |

### Zenodo · resposta ao impulso da capela de São Nicolau (catedral de Aachen)

- Autores: Martin Zerwas e Selin Kayku
- Fonte: https://zenodo.org/records/23312556 (DOI 10.5281/zenodo.20428705), arquivo `S3-Do_R12.wav` do `impulse_responses.zip`
- Licença: **Creative Commons Attribution 4.0 (CC BY 4.0)**. https://creativecommons.org/licenses/by/4.0/
  É o único item que **exige crédito**: a tela de créditos precisa citar os autores, o link
  da licença e dizer que o IR foi modificado (texto pronto lá em cima). Não achei IR medido
  em CC0 que baixe sem login.
- Uso: só como reverb por convolução (`pedalboard.Convolution`) do `ice_crack`, `ice_crack_1` e
  `ice_collapse`. Mudanças: canal W, começa na primeira chegada, cauda de ~4,2 s encurtada pra
  ~2,3 s, passa-alta 120 Hz e passa-baixa 4,5 kHz.
