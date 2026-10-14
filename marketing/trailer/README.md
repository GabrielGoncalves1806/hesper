# Trailer do Hesper (1:30)

Mesmo esquema do `MyFinances-V2/marketing/moni-reel`: vídeo em **Remotion** (React) em `video/`, com o roteiro inteiro
em `video/src/timeline.json`.

| Pasta | O que é | Quem |
|---|---|---|
| `capture.py` | roda o jogo **sem janela** (SDL dummy, seed 7, 30 fps fixos) e grava as cenas de gameplay sem HUD, com câmera própria | video maker |
| `render_cutscenes.py` | monta as cutscenes da Dra. Ilves a partir das camadas do `art/cenas.json` (parallax, tiras, digitação do terminal), ×4 nearest | video maker |
| `art/` | camadas + `cenas.json` das cutscenes | Designer |
| `audio/` | `trailer_music.wav` + `trailer_music.json` (marcadores) e `sfx/` | Som |
| `video/` | projeto Remotion (`src/HesperTrailer.tsx`, `scenes.tsx`, `fx.tsx`, `theme.ts`, `timeline.json`) | video maker |
| `stills/` | PNGs dos momentos principais | gerado |

## Re-renderizar

```bash
# 1) gameplay (só quando o jogo mudar): ~3 min, grava frames/<cena>/*.png e video/public/clips/<cena>.mp4
uv run python marketing/trailer/capture.py              # todas
uv run python marketing/trailer/capture.py giant crater # só algumas

# 2) vídeo (o sync roda sozinho: copia trilha/sfx/fontes e remonta as cutscenes que mudaram)
cd marketing/trailer/video
npm install                 # 1ª vez
npm run render              # out/hesper_trailer.mp4           (1920×1080, 30 fps, H.264 + áudio)
npm run render:vertical     # out/hesper_trailer_vertical.mp4  (1080×1920)
npm run stills              # ../stills/*.png
npm run studio              # preview interativo
```

## Trocar placeholders / assets

- **Trilha**: substitua `audio/trailer_music.wav` (e o `.json` dos marcadores) e re-renderize. Sem o wav, entra 90 s de
  silêncio. Os cortes estão no `timeline.json` (em segundos), alinhados com os hits: 9,6 · 12 · 40 · 55 · 59/65/71 · 85.
- **Cutscenes**: mexeu no `art/cenas.json` ou numa camada? `npm run render` refaz só as cenas que mudaram. Sem
  `cenas.json` com camadas, o sync usa `art/<id>.mp4` ou `art/preview/<id>.gif`; sem nada, entra um placeholder.
  A câmera de cada cena (pan/zoom/âncora) fica na tabela `CAMERA` do `render_cutscenes.py`.
- **Gelo gigante (EM BREVE)**: a variação é a constante `GIANT_VARIANT` no topo do `capture.py` (hoje `"cocoon"`).
  Pra trocar pra larva: mude pra `"larva"` e rode `capture.py giant`. A cutscene 6 usa a variação que a Designer
  gerou (`HESPER_CRIATURA=larva python3 tools/sprites/trailer_ilves.py`).
- **Textos**: legendas, LOGs e logo no `timeline.json`.

## O que é o quê no vídeo

- 0–12 pouso na tempestade (a cápsula bate no chão em 9,6 s, no baque da trilha)
- 12–40 gameplay no compasso de 2 s: tempestade, mineração, magmatita/fumarolas, base, drones, gelo-portão, caverna,
  e "EM BREVE" das drills aranha/tripé + eólico (sprites da Designer em `reports/design/maquinas_r3d/`)
- 40–55 cratera derretendo, chuva enchendo o lago, a mancha do Verde
- 55–75 cutscenes da Dra. Ilves (LOGs 04, 06 e 07 nos estalos de 59/65/71)
- 75–85 EM BREVE: caverna funda com magmatita, gelo gigante no jogo e as cutscenes 6/6b, sugada até 84,85
- 85–90 logo HESPER (Silkscreen + traço laranja), "Planeta sem ar. Por enquanto.", "em desenvolvimento"

SFX: só os do jogo/Som sem exigência de crédito (sem `ice_crack*`/`ice_collapse`, que levam o IR CC BY 4.0).
