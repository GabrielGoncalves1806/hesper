# Créditos de áudio do trailer

## trailer_music.wav

Síntese própria (`build_trailer_audio.py`, usando os utilitários de `tools/audio/build_audio.py`)
mais gravações **CC0 1.0** (domínio público, crédito não obrigatório), já registradas em
`assets/audio/CREDITS.md` e guardadas em `tools/audio/vendor/`:

| Gravação | Autor | Fonte | Onde entra |
|---|---|---|---|
| "Ice breaking/shattering" (`LedasLuzta*.ogg`) | IgnasD | https://opengameart.org/content/ice-breakingshattering | gelo da virada (55-75 s), sugadas reversas, impacto do logo |
| "75 CC0 breaking / falling / hit sfx" (`bfh1_rock_falling_03`) | rubberduck | https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx | pedrinhas do pouso (9,6 s) |
| "AMB Rain Loop 2" (trecho 404-432 s) | Kresiek The Furry | https://opengameart.org/content/amb-rain-loop-2 | chuva baixa (41-55 s) |

O reverb da trilha é sintético. O IR da capela de Aachen (CC BY 4.0) **não** entra na trilha.

## sfx/

- `trailer_*.wav`: síntese própria (o `trailer_reverse_ice` e o `trailer_logo_hit` levam gelo do IgnasD, CC0).
- Os demais são cópias byte a byte de `assets/audio/` e seguem `assets/audio/CREDITS.md`. Atenção a dois casos:
  - `ice_crack.wav`, `ice_crack_1.wav`, `ice_collapse.wav`: reverb por convolução com IR em **CC BY 4.0**.
    Se o vídeo usar algum deles, coloque na descrição:

    > Reverb (resposta ao impulso): "St. Nicholas Chapel, Aachen Cathedral, room impulse responses" por
    > Martin Zerwas e Selin Kayku (https://doi.org/10.5281/zenodo.20428705), licenciado sob CC BY 4.0
    > (https://creativecommons.org/licenses/by/4.0/). Modificado: canal omnidirecional, cauda encurtada e filtrada.

  - `vent_hiss.wav`: "Fumarole (large)", Yellowstone Sound Library, National Park Service (NPS/Jennifer Jerrett).
    No claim to original U.S. Government works.
