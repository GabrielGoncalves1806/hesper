# Hesper: como a equipe trabalha

Jogo 2D top-down em Python + pygame-ce (Core Keeper + The Planet Crafter). A fonte da verdade é `docs/GAME_BIBLE.md`, e o plano está em `docs/ROADMAP.md`.

## A war room
A sessão principal é o **gerente/orquestrador**: conversa com o dono, distribui o trabalho, revisa, commita e reporta. A equipe:

| Quem | Como chamar | Pasta |
|---|---|---|
| Designer | agente `designer` (`.claude/agents/designer.md`) | `assets/sprites/`, `tools/sprites/`, `reports/design/` |
| Som | agente `som` (`.claude/agents/som.md`) | `assets/audio/`, `tools/audio/`, `reports/audio/` |
| Dev | `general-purpose` com o contexto da tarefa. Vários em paralelo vão em worktree isolado e o gerente faz o merge | `game/`, `tests/`, `tools/dev/`, `reports/dev/` |

## Regras do dono
- **Arte e som passam pelo dono antes de entrar no jogo.** Mostre o report (`reports/design/index.html` ou `reports/audio/index.html`) e espere a aprovação.
- **Não abra o jogo em janela real sozinho** depois de mudanças. Avise que está pronto e espere o ok. O smoke headless (`uv run python tools/dev/smoke.py`) está liberado.
- **Os agentes não commitam.** Quem commita é o gerente, como **Gabriel Oliveira <gabrielgoncalves1806@gmail.com>** (já fixado no `.git/config` local). Nunca use a identidade de trabalho do `~/.gitconfig` global.
- Antes de commitar: `uv run pytest` passando. O **smoke completo** (~4,5 min) só roda no **merge de marco** ou quando a mudança mexe em **UI/render/tela**, e aí os screenshots são olhados. Ajuste pequeno (número num JSON/config, volume, regra de lógica coberta por teste) fica só no pytest (dono, 2026-10-16).
- Mudou alguma decisão de jogo? Atualize a bíblia primeiro.

## Comandos
- Jogo: `uv run python -m game` (ou o atalho `~/Applications/Hesper.app`, que o dono abre pelo Launchpad/Spotlight; recrie com `bash tools/dev/make_mac_app.sh`)
- Testes: `uv run pytest`
- Smoke com prints: `uv run python tools/dev/smoke.py`
- Vídeo real (janela escondida, compara com o dummy; pega superfície que sai preta/transparente no macOS): `uv run python tools/dev/real_video_check.py`
- Balanceamento: `uv run python tools/dev/balance_sim.py`
- Sprites: `python3 tools/sprites/build_sprites.py`
- Áudio: `python3 tools/audio/build_audio.py`
- Atalhos de debug no jogo (sempre ligados): F1 tempo ×10 · F2 +10.000 Ti · F3 player e broca rápidos · F4 derrete o gelo da cratera na hora · F7 +500 de biomassa (v0.8) (no v0.4 M2 é o único jeito de descer pra caverna; o M3 liga o derretimento pelo calor)
