# v0.8 M5 · Task 2 · Luminária bio

- `game/lighting.py`: `lamp(tx, ty, radius_tiles=5, color=LAMP_COLOR)`.
- `game/render.py`:
  - `cave_lights` passa `LAMP_BIO_COLOR` pra `lamp_bio` (raio vem do `LAMP_RADIUS`, 6).
  - `lamp_surface("lamp_bio")` usa `lamp_bio.png` (fallback: `lamp` tingido de verde-água via `_tinted_lamp`).
  - Halo de superfície: chave `lamp_bio` no `machine_light` (cor bio, mesmo raio/força do `lamp`). `lamp_t2` já herdava o halo do `lamp` (x1,25), não mexi.
  - `item_icon("lamp_bio")` usa `icon_lamp_bio.png`.
  - Pontos 1816, 1923, 2155, 2189 são genéricos (`is_lamp` / `in LAMP_RADIUS`) e já servem; `dust.py` e `explore.py` também.
- Energia: `lamp_bio` não está em `POWER_USE`, consumo 0 (testado).
- Testes: `tests/test_m5_lamp_v08.py` (7) + `test_cave_light`, `test_lighting`, `test_cave` verdes.
- Não rodei o pytest inteiro nem o smoke. Sem commit.
