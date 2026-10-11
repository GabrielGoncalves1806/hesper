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

Se uma candidata B virar o som oficial, esta tabela continua valendo pro arquivo final.
