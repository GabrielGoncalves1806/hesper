# v0.8 M4 Task 6: desenho no mundo

- `machine_anim_index`: Microscópio anima só `analyzing` (5 fps padrão); Centrífuga só `spinning` a `C.CENTRIFUGE_FPS` (10). Parado, sem energia ou submersa devolve `None` (sprite parado).
- Luz: `MACHINE_LIGHT` ganhou `microscope` (170,210,255) e `centrifuge` (190,255,160). As duas listas de luz (`cave_lights` e a de tela) só acendem com `microscope_blocker` / `centrifuge_blocker` livres.
- Ícone: `item_icon` agora carrega `icon_microscope.png` e `icon_centrifuge.png` (molde do Cultivador). `machine_preview` já usava o sprite da máquina, sem mudança.
- Teste novo: `tests/test_m4_render_v08.py` (5 testes). Rodados junto: water, cultivator, microscope, centrifuge, anim_rocks, cave_light, lighting. 194 passam.
- Só mexi em `game/render.py`. Sem commit, sem janela, sem smoke.
