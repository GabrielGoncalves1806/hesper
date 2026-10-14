"""Report do gelo gigante (v0.5, PROPOSTA). Chamado pelo tools/sprites/gelo_gigante.py.
Escreve reports/design/gelo_gigante/index.html (caminhos relativos, abre local)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import gelo_gigante as G
import regions_core as R

OUT = G.OUT

CSS = """
:root{--bg:#15100e;--panel:#1e1714;--panel2:#241b17;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;--alert:#ff6a55;
  --f-label:"Silkscreen",ui-monospace,monospace;--f-display:"Pixelify Sans",ui-monospace,monospace;--f-body:"IBM Plex Sans",system-ui,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,monospace;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.6 var(--f-body);padding-inline:16px}
.wrap{max-width:1500px;margin:0 auto;padding-block:48px 80px}
.eyebrow{font:12px var(--f-label);letter-spacing:.08em;color:var(--cyan);text-transform:uppercase}
h1{font:600 clamp(34px,6vw,54px)/1.05 var(--f-display);margin:10px 0 14px}
.lede{color:var(--muted);max-width:92ch;margin:0}
h2{font:600 24px/1.2 var(--f-display);margin:0 0 16px}
h2::before{content:"";display:inline-block;width:10px;height:10px;background:var(--cyan);margin-right:10px;vertical-align:middle}
h3{font:600 18px var(--f-display);margin:0 0 8px}
section{margin-top:56px}
code{font-family:var(--f-mono);font-size:.92em;color:var(--gold)}
img{image-rendering:pixelated}
.note{margin-top:22px;max-width:1040px;background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:14px 18px}
.note > b{font:13px var(--f-label);color:var(--cyan)}
.note ul{margin:8px 0 0;padding-left:18px;color:var(--muted)}.note li{margin-bottom:6px}.note li b{color:var(--fg)}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
@media (max-width:1100px){.grid2,.grid3{grid-template-columns:1fr}}
figure{margin:0}
figcaption{font:12px var(--f-label);color:var(--muted);margin-top:6px;letter-spacing:.04em}figcaption b{color:var(--fg)}
.box{background:var(--panel);border:1px solid var(--line);padding:18px 20px}
.box ul{margin:0;padding-left:18px;color:var(--muted)}.box li{margin-bottom:8px}.box li b{color:var(--fg)}
.box p{color:var(--muted);margin:6px 0}
.dev{border-left:3px solid var(--cyan)}
.chk{background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px;padding:10px;display:inline-block}
.scroll{overflow-x:auto;padding-bottom:6px}
.scene{width:100%;height:auto;display:block;border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{font:12px var(--f-label);color:var(--gold);background:var(--panel2)}td{color:var(--muted)}td b{color:var(--fg)}
.sws{display:flex;gap:3px}.sws i{width:22px;height:22px;border:1px solid rgba(255,255,255,.12);display:inline-block}
.tabs input{display:none}.tabs label{font:12px var(--f-label);padding:6px 12px;border:1px solid var(--line);cursor:pointer;display:inline-block;margin:0 4px 8px 0;color:var(--muted)}
.tabs input:checked + label{color:var(--fg);border-color:var(--cyan);background:rgba(89,208,230,.08)}
.tabs .pane{display:none}
#t-coil:checked ~ .p-coil,#t-s:checked ~ .p-s,#t-piece:checked ~ .p-piece{display:block}
.sprite{image-rendering:pixelated;background-repeat:no-repeat}
@keyframes play{from{background-position-x:0}to{background-position-x:calc(-8 * var(--fw))}}
"""


def size(name):
    with Image.open(OUT / name) as im:
        return im.size


def img(name, k=1, cls="", style=""):
    w, h = size(name)
    return f'<img src="{name}" width="{w * k}" height="{h * k}" class="{cls}" style="{style}" alt="">'


def anim(key, stage, k, idle_frames=10):
    """Tira de 8 quadros em CSS: segura o quadro 0 e toca 1 vez a 6 fps (como no jogo, só que com pausa curta)."""
    fw, fh = G.SW * k, G.SH * k
    total = idle_frames + G.NFRAMES
    dur = total / 6
    name = f"anim_{key}_{stage}.png"
    kf = f"a_{key}_{stage}_{k}"
    steps = []
    for i in range(total):
        f = max(0, i - idle_frames)
        steps.append(f"{100 * i / total:.3f}%{{background-position-x:{-f * fw}px}}")
    steps.append(f"100%{{background-position-x:0px}}")
    return (f'<style>@keyframes {kf}{{{"".join(steps)}}}</style>'
            f'<div class="sprite" style="width:{fw}px;height:{fh}px;background-image:url({name});'
            f'background-size:{fw * G.NFRAMES}px {fh}px;animation:{kf} {dur:.2f}s steps(1) infinite"></div>')


def build(data, tiles):
    V = G.VARIANTS
    desc = {
        "coil": "1,25 volta de espiral, dormindo enrolada. A cabeça fica por fora, embaixo à esquerda, e o rabo "
                "afina pro miolo. A metade de cima está mais funda e quase some.",
        "s": "Atravessa o bloco na diagonal. A cabeça, perto da face, mostra a boca; o rabo afunda à direita e vira "
             "só um vulto. É a que mais lê como 'bicho comprido'.",
        "piece": "Só um arco grosso (raio 15, o dobro das outras) saindo do fundo e voltando pro fundo. Não tem cabeça "
                 "nem rabo: o jogador nunca sabe o tamanho. Medo pelo tamanho.",
    }
    var_cards = []
    for k in V:
        var_cards.append(f"""<figure class="box"><h3>{V[k]['name']} <code>form_ice_giant_{k}.png</code></h3>
<div class="chk">{img(f'giant_{k}.png', 2)}</div>
<div style="display:flex;gap:16px;align-items:flex-end;margin-top:10px">
<div class="chk">{img(f'giant_{k}.png', 1)}</div><figcaption>tamanho real (1:1)</figcaption></div>
<p>{desc[k]}</p></figure>""")
    stage_rows = "\n".join(
        f'<figure style="margin-top:14px"><div class="scroll">{img(f"stages_{k}.png", 1)}</div>'
        f'<figcaption><b>{V[k]["name"]}</b> · Tempestade, Árido, Névoa, Verde (só troca a paleta)</figcaption></figure>'
        for k in V)
    tabs = ['<div class="tabs">']
    for i, k in enumerate(V):
        tabs.append(f'<input type="radio" name="sc" id="t-{k}" {"checked" if i == 0 else ""}><label for="t-{k}">{V[k]["name"]}</label>')
    for k in V:
        cells = "".join(f'<figure><img class="scene" src="scene_{k}_{s}.png" alt=""><figcaption><b>{R.STAGE_NAME[s]}</b></figcaption></figure>'
                        for s in R.STAGES)
        tabs.append(f'<div class="pane p-{k}"><div class="grid2">{cells}</div>'
                    f'<figure style="margin-top:14px"><div class="scroll">{img(f"crop_{k}_arid.png", 2)}</div>'
                    f'<figcaption>recorte 2× do Árido: o Explorador (32×32) do lado, pra dar escala</figcaption></figure></div>')
    tabs.append("</div>")
    anims = "".join(f'<figure class="box"><h3>{V[k]["name"]}</h3><div class="chk">{anim(k, "arid", 2)}</div>'
                    f'<figcaption>2× · segura o quadro 0 e toca a tira uma vez · GIF: <a href="anim_{k}.gif" style="color:var(--cyan)">anim_{k}.gif</a></figcaption></figure>'
                    for k in V)
    strips = "".join(f'<figure style="margin-top:10px"><div class="scroll"><div class="chk">{img(f"anim_{k}_arid.png", 1)}</div></div>'
                     f'<figcaption>tira <code>form_ice_giant_{k}_anim.png</code> · 8 quadros de 256×220</figcaption></figure>' for k in ("s",))
    deep_rows = "".join(
        f'<tr><td><b>{R.STAGE_NAME[s]}</b></td><td><div class="sws">'
        + "".join(f'<i style="background:{c}" title="{c}"></i>' for c in data["ramps"]["ICE_DEEP"][s])
        + f'</div></td><td><code>{" ".join(data["ramps"]["ICE_DEEP"][s])}</code></td></tr>' for s in R.STAGES)
    new_section = new_block(data)
    tl = ", ".join(f"({dx}, {dy})" for dx, dy in sorted(tiles))
    shards = "<br>".join(f"<code>{s['sprite']}</code> quadro {s['frame']} em ({s['x']}, {s['y']})" for s in data["shards"])
    chips = " · ".join(f"({c['x']}, {c['y']})" for c in data["chips"])
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Gelo gigante · v0.5.1 (proposta)</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Pixelify+Sans:wght@400;600&family=Silkscreen&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5.1 · proposta · a criatura em "C" (a 1ª rodada segue abaixo como histórico)</div>
<h1>O gelo gigante</h1>
<p class="lede">Num canto da faixa gelada, um monólito de gelo antigo, encalhado, bem maior que tudo em volta, cercado de
estilhaços. Lá dentro, escura e borrada pela espessura do gelo, a silhueta de uma coisa comprida e segmentada. O
jogador não descobre o que é. Só vê, teoriza e lembra da Dra. Ilves: <i>"o gelo daqui não é só água, tem alguma
coisa dentro dele"</i>, <i>"cresce quando ninguém olha"</i>, <i>"Não acorde o gelo"</i>.</p>

<div class="note" style="border-left-color:var(--gold)"><b style="color:var(--gold)">v0.5.1 · o que mudou</b><ul>
<li><b>O monólito, os estilhaços e a geada ficaram iguais</b>, como o dono pediu ("o gelo tá perfeito").</li>
<li><b>A criatura virou um bicho encolhido em "C"</b>, em posição fetal, "tipo o Mewtwo no tubo". São 4 amostras novas:
<b>Larva em C</b>, <b>Embrião</b>, <b>Casulo</b> e <b>Encolhido com cauda</b>. As 4 ocupam o miolo da face da frente
e seguem a mesma regra: escura e difusa pela espessura do gelo, mais nítida perto da face, sumindo no fundo, sem olho e
sem gore.</li>
<li><b>Aprovadas pelo dono: Larva em C e Casulo.</b> As tiras dos 4 estágios do Casulo estão logo abaixo.</li>
<li>O motor da silhueta agora aceita corpo feito de tubos e bolas, mais uma <b>membrana</b> (casca de elipsoide) que
aparece como véu na borda. Os índices e a rampa <code>ICE_DEEP</code> não mudaram.</li>
</ul></div>

<div class="note"><b>v0.5 · 1ª rodada</b><ul>
<li><b>Gelo gigante</b> (<code>form_ice_giant_*.png</code>, 256×220): volume 3D no mesmo motor das formações (poliedros
convexos como os blocos do portão), facetado, com estratos inclinados, bolhas presas, fissuras de ar e brilho especular.
Pegada proposta de <b>7×4 tiles</b>.</li>
<li><b>A silhueta</b>: um tubo segmentado <i>dentro</i> do volume. Cada pixel da superfície olha pra dentro pelo raio de
visão; quanto mais fundo o bicho, mais ele vira só um escurecido do gelo. Tem 3 variações pro dono escolher:
<b>Enrolada</b>, <b>Em S</b> e <b>Só um pedaço</b>.</li>
<li><b>Rampa nova <code>ICE_DEEP</code></b> (3 cores, índices 10..12), derivada da <code>ICE</code> de cada estágio
misturada com o contorno. Vale o mesmo esquema da <code>VENT</code> das fumarolas.</li>
<li><b>Estilhaços</b>: nenhum sprite novo. São os <code>ice_block_*</code> do portão em quadros menores, mais os
<code>decor_ice_chunks</code>, num arranjo fixo. A geada é uma <code>frost_field.png</code> nova (420×200), a
<code>frost_ring</code> esticada.</li>
<li><b>Animação</b> opcional e quase subliminar, numa tira de 8 quadros: uma faixa de brilho frio varre o gelo e a
silhueta "respira" (o raio cresce até 7%, cerca de 1 px na borda).</li>
<li>Nada foi pra <code>assets/</code>. Os pendentes estão em <code>reports/design/gelo_gigante/pendentes/</code>.</li>
</ul></div>

{new_section}

<section><h2>Histórico · 1ª rodada: o verme comprido</h2>
<p class="lede" style="margin-bottom:12px">As 3 silhuetas da 1ª rodada, guardadas pra comparar. O dono aprovou o monólito,
os estilhaços e a geada, e pediu a criatura encolhida em "C" (acima).</p>
<div class="grid3">{''.join(var_cards)}</div>
<div class="box" style="margin-top:16px"><ul>
<li><b>Sugere, não mostra.</b> Perto da face, o corpo aparece em 2 tons (corpo e miolo) e as juntas dos segmentos
ficam um tom mais claras. Mais fundo, vira véu e depois só um escurecido de 1 tom no gelo. A franja é um xadrez de
1 px (é o "difuso" sem alfa).</li>
<li><b>A boca</b> (Enrolada e Em S) é um disco escuro na ponta da cabeça com um anel um tom mais claro em volta.
Lê como abertura, não como olho, e não brilha.</li>
<li>O tampo do bloco tem geada: ali a silhueta aparece só pela metade, então o bicho nunca "vaza" pra cima.</li>
<li>Sem olho, sem dente nítido, sem gore. O medo vem da forma e do tamanho: cada segmento tem a largura do Explorador.</li>
</ul></div>
{stage_rows}
</section>

<section><h2>Histórico · o verme na faixa gelada, nos 4 estágios</h2>
<p class="lede" style="margin-bottom:12px">O mundo dos mockups da v9, com o gigante num canto da faixa gelada. Em volta ficam
os estilhaços (blocos do portão em quadros menores, caídos mais pra frente-direita, o lado que "rachou"), os caquinhos
soltos e a geada grande no chão. O Explorador está à esquerda pra dar escala.</p>
{''.join(tabs)}
</section>

<section><h2>Histórico · a animação na 1ª rodada</h2>
<div class="grid3">{anims}</div>
{strips}
<div class="box" style="margin-top:12px"><ul>
<li><b>Brilho frio</b>: uma faixa diagonal de 7 px sobe 1 tom nas faces iluminadas e passa em 5 dos 8 quadros.</li>
<li><b>Respiração</b>: o raio da silhueta vai até +7% e volta (0, 2, 5, 7, 7, 5, 2, 0%), o que dá 1 px na borda.
Quase ninguém nota de propósito: a ideia é o jogador achar que viu alguma coisa.</li>
<li><b>No jogo</b>: fica parado no quadro 0. A cada 9 a 14 s (sorteado), toca a tira uma vez a 6 fps e volta pro 0.</li>
</ul></div>
</section>

<section><h2>Pegada e âncora (proposta)</h2>
<div class="grid2">
<figure><div class="chk">{img('footprint.png', 1)}</div><figcaption>amarelo: a caixa 7×4 · vermelho: os tiles que
bloqueiam · ciano: o corte da base do volume (Z = 1..3) · ponto ciano: a âncora</figcaption></figure>
<div class="box dev"><h3>Pro Dev integrar (depois do ok do dono)</h3><ul>
<li><b>Sprite</b>: <code>form_ice_giant.png</code> (256×220, a variação escolhida) + <code>form_ice_giant_anim.png</code>
(2048×220, 8 quadros de 256×220). PNG indexado no esquema das formações: 0..7 rampa <code>ICE</code>
(<code>ramps.ICE.frost[estágio]</code>), 8 contorno, 9 sombra (alfa 80), <b>10..12 rampa nova
<code>ramps.ICE_DEEP[estágio]</code></b>, 255 transparente.</li>
<li><b>Âncora</b>: <code>foot = ({G.OX}, {G.OY})</code>, o centro da base no sprite, que cai no meio da borda de baixo
do tile da âncora. É o mesmo <code>place_sprite_foot</code> das formações (pé em <code>(tx·32+16, ty·32+30)</code>).
Ordenado pelo pé.</li>
<li><b>Pegada</b>: <code>size = (7, 4)</code> reservado (nada nasce dentro). Os tiles que bloqueiam viram
<code>FORMATION</code>, relativos ao tile da âncora (dy negativo = pra trás): {tl}. Não minera, não tem afloramento.
Merece um marcador no mapa, porque é marco.</li>
<li><b>Quantos e onde</b>: 1 por mundo, num canto da faixa gelada, longe dos gelos-portão. O <code>keep_clear</code>
é de 11×7 tiles em volta da pegada, que é onde moram os estilhaços e a geada.</li>
<li><b>Estilhaços</b> (objetos, ordenados pelo pé, colisão = a caixa daquele quadro no <code>regions_palettes.json</code>
(<code>blocks</code>); (x, y) = pé relativo à âncora do gigante):<br>{shards}</li>
<li><b>Caquinhos</b> (<code>decor_ice_chunks</code>, sem colisão): {chips}</li>
<li><b>Geada</b>: <code>frost_field.png</code> (420×200), rampa <code>BASE</code> da faixa gelada, na camada de
decalques, centrada em (âncora.x, âncora.y − 54).</li>
<li><b>Ordem de desenho</b>: chão → decalques (geada) → objetos ordenados pelo pé (estilhaços, gigante, Explorador)
→ partículas/clima → HUD.</li>
<li><b>Contrato</b>: isso tudo é <b>proposta</b>. A bíblia §6 ganharia a linha do <code>form_ice_giant*</code>, a
<code>frost_field.png</code> e a rampa <code>ICE_DEEP</code>. Os dados estão em <code>pendentes/gelo_gigante.json</code>.</li>
</ul></div></div>
<h3 style="margin-top:20px">Rampa nova ICE_DEEP (índices 10 véu, 11 corpo, 12 miolo/boca)</h3>
<table><tr><th>Estágio</th><th>Cores</th><th>Hex</th></tr>{deep_rows}</table>
<p class="lede" style="margin-top:8px">Fórmula: 10 = 75% <code>ICE[1]</code> + 25% <code>ICE[2]</code> · 11 = 85%
<code>ICE[0]</code> + 15% contorno · 12 = 40% <code>ICE[0]</code> + 60% contorno.</p>
</section>

<section><h2>Arquivos</h2><div class="box"><ul>
<li>Gerador: <code>tools/sprites/gelo_gigante.py</code> (+ <code>gelo_gigante_report.py</code>). Roda com
<code>python3 tools/sprites/gelo_gigante.py</code>, é determinístico e reaproveita <code>regions_volume</code> e
<code>regions_ice_blocks</code>.</li>
<li>Pendentes: <code>pendentes/form_ice_giant_{{coil,s,piece}}.png</code> (256×220),
<code>pendentes/form_ice_giant_{{coil,s,piece}}_anim.png</code> (2048×220), <code>pendentes/frost_field.png</code>
(420×200) e <code>pendentes/gelo_gigante.json</code>.</li>
</ul></div></section>
</div></body></html>
"""
    page = OUT / "index.html"
    page.write_text(html, encoding="utf-8")
    return page


def new_block(data):
    C = G.C_VARIANTS
    rec = G.SHOWCASE
    desc = {
        "larva": "Corpo gordo e segmentado curvado em C, a cabeça (sem rosto) quase encostando na cauda, e 3 pares de "
                 "patinhas dobradas pra dentro. É a mais 'bicho' das quatro.",
        "embryo": "Cabeça grande em cima e o corpo enrolado por baixo, com brotos de braço e perna e um cordão fino que "
                  "some no fundo do gelo. Silhueta de algo que ainda vai nascer.",
        "cocoon": "A larva em C, menor, dentro de uma membrana oval: a casca aparece como um anel de véu e o miolo fica "
                  "um tom mais escuro. É a crisálida no gelo, o 'Mewtwo no tubo'.",
        "fetal": "Variação minha: cabeça baixa com o crânio puxado pra trás, costas curvas, joelhos encolhidos, um braço "
                 "abraçando as pernas e uma cauda longa dando a volta por fora (mais funda, quase só véu).",
    }
    cards = []
    for k in C:
        badge = ' <span style="font:11px var(--f-label);color:var(--ok);border:1px solid var(--ok);padding:1px 6px">aprovada</span>' if k in G.APPROVED else ""
        cards.append(f"""<figure class="box"><h3>{C[k]['name']}{badge}</h3><p><code>form_ice_giant_{k}.png</code></p>
<div class="chk">{img(f'giant_{k}.png', 2)}</div>
<div style="display:flex;gap:16px;align-items:flex-end;margin-top:10px">
<div class="chk">{img(f'giant_{k}.png', 1)}</div><figcaption>tamanho real (1:1)</figcaption></div>
<p>{desc[k]}</p></figure>""")
    rec_scenes = "".join(f'<figure><img class="scene" src="scene_{rec}_{s}.png" alt=""><figcaption><b>{R.STAGE_NAME[s]}</b></figcaption></figure>'
                         for s in R.STAGES)
    other = "".join(f'<figure><div class="scroll">{img(f"stages_{k}.png", 1)}</div><figcaption><b>{C[k]["name"]}</b> · 4 estágios</figcaption></figure>'
                    for k in C if k != rec)
    return f"""<section><h2>v0.5.1 · a criatura em "C" (4 amostras)</h2>
<figure><div class="scroll">{img('c_side_by_side.png', 1, 'scene')}</div>
<figcaption>a mesma cena, no mesmo estágio (Árido), com o Explorador à esquerda. Só a criatura muda. Da esquerda pra
direita: <b>Larva em C</b>, <b>Embrião</b>, <b>Casulo</b>, <b>Encolhido com cauda</b></figcaption></figure>
<div class="grid2" style="margin-top:16px">{''.join(cards)}</div>
<div class="box" style="margin-top:16px"><ul>
<li><b>O dono aprovou as duas versões: a Larva em C e o Casulo.</b></li>
<li><b>O Casulo.</b> Ele resolve o "sugerir sem mostrar" sozinho: a membrana dá um contorno oval escuro e
limpo, que lê de longe como "tem algo guardado ali", e o bicho lá dentro fica ainda mais borrado. É o que mais lembra
"o Mewtwo no tubo" e conversa com a fala da Ilves ("cresce quando ninguém olha"), porque um casulo é algo que ainda vai
sair. A Larva em C é o mesmo bicho sem a membrana: maior e mais legível.</li>
<li>Em todas, a parte mais funda vira só um escurecido de 1 tom (o rabo do Encolhido, o cordão do Embrião, a
casca de trás do Casulo). A franja é o xadrez de 1 px, sem alfa.</li>
<li>A animação é a mesma da 1ª rodada (o brilho frio varrendo o gelo e a respiração de +7%). No Casulo a membrana
fica parada e só o bicho respira.</li>
</ul></div>
<h3 style="margin-top:22px">{C[rec]['name']} nos 4 estágios</h3>
<figure><div class="scroll">{img(f'stages_{rec}.png', 2)}</div><figcaption>sprite 2× sobre o chão da faixa gelada · Tempestade,
Árido, Névoa, Verde</figcaption></figure>
<figure style="margin-top:10px"><div class="scroll"><div class="chk">{img(f'anim_{rec}_arid.png', 1)}</div></div>
<figcaption>tira <code>form_ice_giant_{rec}_anim.png</code> · 8 quadros de 256×220</figcaption></figure>
<div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:12px">{''.join(f'<figure><div class="chk">{anim(rec, s, 1)}</div><figcaption>{R.STAGE_NAME[s]} · animação</figcaption></figure>' for s in R.STAGES)}</div>
<div class="grid2" style="margin-top:14px">{rec_scenes}</div>
<h3 style="margin-top:22px">As outras 3 nos 4 estágios</h3>
<div style="display:grid;gap:10px">{other}</div>
</section>"""
