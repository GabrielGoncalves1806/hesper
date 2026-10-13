"""Seção v9.2 do report das regiões (PROPOSTA: gelo-portão em blocos). Chamado pelo tools/sprites/regions_v92.py,
que injeta a seção e a nota no reports/design/regioes/index.html, acima da v9.1 (idempotente)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import regions_ice_blocks as B

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "reports" / "design" / "regioes"
OUT = REG / "v92"

CSS = """
.v92{border:1px solid var(--cyan);padding:22px 22px 30px;margin-top:40px;background:rgba(89,208,230,.04)}
.v92 > h2::before{background:var(--cyan)}
.v92 .chk{background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px;padding:8px;display:inline-block}
.v92 img{image-rendering:pixelated}
.v92 .scroll{overflow-x:auto;padding-bottom:6px}
.v92 table{border-collapse:collapse;width:100%}.v92 td,.v92 th{border-top:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}
.v92 th{font:12px var(--f-label);color:var(--muted)}
.v92 .pill{display:inline-block;font:11px var(--f-label);padding:1px 6px;border:1px solid var(--line);margin:1px}
.v92 .pill.ok{border-color:var(--ok);color:var(--ok)}.v92 .pill.no{color:var(--muted)}
"""


def _size(p):
    with Image.open(p) as im:
        return im.size


def img(src, k, cap="", cls=""):
    w, h = _size(REG / src)
    c = f"<figcaption>{cap}</figcaption>" if cap else ""
    return f'<figure class="{cls}"><img src="{src}" width="{w * k}" height="{h * k}" alt="">{c}</figure>'


def build(data, opens):
    rows = []
    for key, b in data["blocks"].items():
        kind, v = key.rsplit("_", 1)
        fw, fh = b["frame"]
        cols = " · ".join(f"{int(s * 100)}%: {c}" for s, c in zip(b["scales"], b["collision"]))
        rows.append(f"""<tr><td><b>{b['name']}</b><br><code>{b['sprite']}</code><br>tira {fw * 8}×{fh} · 8 quadros de
{fw}×{fh}<br>âncora {tuple(b['anchor'])} (centro da base)<br><small>colisão [x, y, w, h] por escala:<br>{cols}</small></td>
<td><div class="scroll"><div class="chk">{img(f"v92/cat/ice_block_{key}.png", 2)}</div>
<div class="chk" style="margin-top:6px">{img(f"v92/cat/boxes_{key}.png", 2, "caixa de colisão (laranja) e âncora (ponto ciano) em cada escala")}</div></div></td></tr>""")
    stage_rows = "\n".join(
        f'<div class="scroll" style="margin-top:8px">{img(f"v92/cat/stages_{k}.png", 2, f"<b>{B.BLOCKS[k]["name"]}</b> nos 4 estágios (Tempestade, Árido, Névoa, Verde): inteiro e no quadro 4, v1 e v2")}</div>'
        for k in B.KINDS)
    rec_rows = []
    for rk, r in data["recipes"].items():
        pills = " ".join(f'<span class="pill {"ok" if ok else "no"}">p {p:.2f} · {"passa" if ok else "fechado"}</span>'
                         for p, ok in opens[rk])
        blist = "<br>".join(f"<code>{b['b']}</code> em ({b['x']}, {b['y']}) · derrete de {b['melt'][0]:.2f} a {b['melt'][1]:.2f}"
                            for b in r["blocks"])
        rec_rows.append(f"""<h3 style="margin-top:22px">Arranjo {rk} · {r['name']} · fresta abre em p ≈ {r['opens_at']:.2f}</h3>
<p style="color:var(--muted);margin:4px 0 8px">{blist}</p>
<div class="scroll">{img(f"v92/melt_{rk}.png", 2)}</div>
<div style="margin:6px 0">{pills}</div>
<div class="grid2" style="max-width:960px">{img(f"v92/melt_{rk}_boxes.gif", 2, "GIF com as caixas e o caminho do player (verde) quando passa")}
{img(f"v92/melt_{rk}_clean.gif", 2, "GIF limpo (como fica no jogo)")}</div>""")

    sec = f"""<!-- v92:begin -->
<section class="v92" id="v92"><h2>v9.2 · Gelo-portão em blocos que derretem (proposta)</h2>
<p class="lede">Pedido do dono no playtest do Marco 3 (M3.5): o gelo-portão deixa de ser um sprite que troca por
etapa e vira um <b>amontoado de 3 a 5 blocos de gelo</b> de 3 tipos. Cada bloco derrete no seu ritmo e <b>vai
encolhendo sem trocar de desenho</b>: o volume 3D é refeito em 8 escalas (100% → 23%) pelo mesmo motor das formações, e
não redimensionado em pixel. Nas escalas menores as quinas amolecem e o brilho molhado aumenta, mas é sempre o mesmo
bloco. A caixa de colisão encolhe junto e, quando abre uma fresta de 14 px (a caixa do player), ele passa.
Os PNGs ficam em <code>v92/pendentes/</code> com o <code>regions_v92.json</code>: nada entra em <code>assets/</code> sem o ok do dono.</p>

<h3 style="margin-top:22px">Os 6 blocos nas 8 escalas</h3>
<p style="color:var(--muted)">Lasca (coluna grossa de topo em bisel; a 2 é um par com um toco), Laje (larga e baixa; a 2 é
rachada em duas) e Pedra (poliédrica arredondada; a 2 é um cubo tombado de quinas gastas, que conversa com o gelo em
cubos dos minérios). Rampa <code>ICE</code>, PNG indexado igual às formações (1..6 gelo, 8 contorno, 9 sombra).
Ampliado 2×.</p>
<table><tr><th style="width:260px">bloco</th><th>tira (8 escalas) e caixas</th></tr>
{''.join(rows)}</table>
{stage_rows}

<h3 style="margin-top:28px">O amontoado derretendo · 3 arranjos pra seed variar</h3>
<p style="color:var(--muted)">O corredor de 4 tiles (128 px) entre as duas paredes de BEDROCK, com a faixa de 2 tiles
da pegada de hoje. <b>Laranja</b>: a caixa de colisão de cada bloco no quadro da hora. <b>Verde</b>: o caminho que a
busca acha pra caixa do player (14×8), do avental até o bolsão, e a caixa do player no ponto mais apertado. A tira
mostra p = 0 · 0,15 · 0,3 · 0,45 · 0,6 · 0,7 · 0,8 · 0,9 · 1. A geada (<code>frost_ring</code>) entra no chão quando
começa a derreter, como hoje. Ampliado 2×.</p>
{''.join(rec_rows)}

<h3 style="margin-top:28px">Na cena (arranjo A)</h3>
<div class="grid2">
{img("v92/crop_arid_inteiro.png", 2, "<b>Árido</b> · inteiro")}
{img("v92/crop_arid_derretendo.png", 2, "<b>Árido</b> · p = 0,62, a fresta acabou de abrir")}
{img("v92/crop_green_inteiro.png", 2, "<b>Verde</b> · inteiro")}
{img("v92/crop_green_derretendo.png", 2, "<b>Verde</b> · p = 0,62")}
</div>
<div class="grid2" style="margin-top:10px">
<figure><img class="px" src="v92/scene_arid_inteiro.png" alt=""><figcaption><b>Árido</b> · cena 960×540 inteira</figcaption></figure>
<figure><img class="px" src="v92/scene_green_derretendo.png" alt=""><figcaption><b>Verde</b> · cena 960×540 inteira, derretendo</figcaption></figure>
</div>
<p style="color:var(--muted)">A cena usa o corredor do mapa de exemplo das regiões (não é um corredor de 4 tiles exato): o
que vale pra medir a fresta é o diagrama de cima.</p>

<div class="box dev" style="margin-top:24px"><h3>Pro Dev integrar</h3><ul>
<li><b>Arquivos</b>: <code>ice_block_{{shard,slab,boulder}}_{{0,1}}.png</code> (6 tiras, 8 quadros cada, todos do mesmo
tamanho dentro da tira) + o bloco <code>ice_blocks</code> e <code>ice_gate_recipes</code> que entram no
<code>regions_palettes.json</code> na promoção (hoje em <code>v92/pendentes/regions_v92.json</code>, chaves
<code>blocks</code> e <code>recipes</code>). Saem <code>ice_gate_{{0,1,2}}.png</code> e a pegada por etapa.</li>
<li><b>Âncora</b>: <code>blocks[k].anchor</code> = px do quadro que cai no pé do bloco. O pé do bloco no mundo =
<code>base_px</code> do portão (centro da borda de baixo da caixa 4×2 de hoje) + <code>(x, y)</code> da receita. O quadro
k fica em <code>(k · frame.w, 0)</code> na tira. Mesma âncora nos 8 quadros: o bloco não anda quando encolhe.</li>
<li><b>Derretimento</b>: o progresso do portão é <code>p ∈ [0, 1]</code> (ex.: linear no calor entre o 1º e o último
marco do <code>THAW_GATE_HEAT[i]</code>). Cada bloco: <code>p &lt; começa</code> → quadro 0; entre <code>começa</code> e
<code>termina</code> → quadro <code>int((p − começa)/(termina − começa) · 8)</code>; <code>p ≥ termina</code> → some.
Só sobe (como o resto do degelo), então pode ser derivado do calor no load.</li>
<li><b>Colisão</b>: <code>blocks[k].collision[quadro]</code> = <code>[x, y, w, h]</code> em px relativos ao pé do bloco
(y negativo = pra trás), a base do volume com 1 px de folga. Igual ao <code>Machine.rect</code>: retângulo no chão. A
pegada em tiles <code>FORMATION</code> sai; o player bate nos retângulos. Medido aqui: fresta de 14 px abre em
p ≈ {data['recipes']['A']['opens_at']:.2f} (A), {data['recipes']['B']['opens_at']:.2f} (B) e {data['recipes']['C']['opens_at']:.2f} (C).</li>
<li><b>Ordem de desenho</b>: cada bloco é um objeto do <code>build_draw_list</code> com o y do pé dele (não um objeto
só pro portão), então o player passa na frente de um e atrás do outro. A sombra (índice 9) vem no sprite.</li>
<li><b>Cor</b>: <code>ramps.ICE.frost[estágio]</code>, a mesma do gelo-portão de hoje (0..7, 8 contorno, 9 sombra).</li>
<li><b>Escolha do arranjo</b>: pela seed do portão (A, B ou C). Os blocos encostam nas paredes do corredor
(x de −64 a +64); se o corredor do <code>geo</code> não for exatamente 4 tiles, dá pra espelhar a receita (x → −x) sem
espelhar o sprite.</li>
<li><b>Geada e poça</b>: o <code>frost_ring</code> continua no chão quando p &gt; 0. <b>Poça de degelo: não proponho</b>
na Tempestade nem no Árido (sem água líquida: o gelo sublima, por isso a geada). Na Névoa e no Verde dá pra entrar uma
mancha úmida no chão, mas os portões costumam abrir antes disso; fica de fora até o dono pedir.</li>
<li><b>Eventos</b>: o aviso "Um gelo-portão abriu" pode sair quando a fresta abre (o primeiro p em que a busca acha
caminho) e não no p = 1. O <code>ice_crack</code> do Som casa com um bloco sumindo.</li>
</ul></div>
</section>
<!-- v92:end -->"""
    note = """<!-- v92note:begin -->
<div class="v2"><b>v9.2 · o que mudou (proposta, espera o ok do dono)</b><ul>
<li><b>Gelo-portão em blocos</b>: 3 tipos de bloco (lasca, laje, pedra), 2 variações cada, exportados em 8 escalas
geradas pelo volume (o mesmo bloco encolhendo), com a caixa de colisão de cada escala.</li>
<li><b>3 arranjos</b> de 3 a 5 blocos fechando o corredor de 4 tiles, com quando cada bloco derrete e a busca de caminho
mostrando quando abre a fresta (≈ 60% do degelo). Cenas no Árido e no Verde. <a href="#v92">Seção v9.2</a>.</li>
</ul></div>
<!-- v92note:end -->"""
    (OUT / "section.html").write_text(sec, encoding="utf-8")
    (OUT / "note.html").write_text(note, encoding="utf-8")
    return sec, note, CSS
