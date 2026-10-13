"""Seção v9 do report das regiões (proposta pendente do dono). Chamado pelo tools/sprites/regions_v9.py.

Escreve reports/design/regioes/v9/section.html e v9/note.html e INJETA os dois no reports/design/regioes/index.html
(entre marcadores, idempotente). O regions_report.build() também chama inject(), então rodar o regions_mockups.py de
novo não apaga a v9.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

import regions_core as R

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "reports" / "design" / "regioes"
OUT = REG / "v9"

CSS_V9 = """
.v9{border:1px solid var(--gold);padding:22px 22px 30px;margin-top:40px;background:rgba(242,196,109,.03)}
.v9 > h2::before{background:var(--gold)}
.cat{display:grid;grid-template-columns:240px 1fr;gap:14px;border-top:1px solid var(--line);padding:14px 0}
.cat h3{margin:0}.cat p{color:var(--muted);margin:4px 0 0;font-size:14px}
.cat .meta{font:12px var(--f-mono);color:var(--gold)}
.cat .chk{gap:16px;padding:10px}
.strip{image-rendering:pixelated;display:block;margin-top:8px;max-width:100%;height:auto}
.tog{position:relative;aspect-ratio:16/9;border:1px solid var(--line);overflow:hidden}
.tog img{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated}
.tog img.b,.tog span.b{animation:togB 4s infinite}
.tog span{position:absolute;left:8px;bottom:8px;font:12px var(--f-label);background:#0f1119;padding:3px 7px}
.tog span.a{animation:togA 4s infinite}
@keyframes togB{0%,49.9%{opacity:1}50%,100%{opacity:0}}
@keyframes togA{0%,49.9%{opacity:0}50%,100%{opacity:1}}
.rg{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:middle;border:1px solid #0006}
"""

REG_COL = {"plateau": "#8a573a", "salar": "#c6b8a4", "basalt": "#3a343e", "frost": "#90a6b9", "bed": "#96694d"}


def _size(p):
    with Image.open(p) as im:
        return im.size


def chk(src, w, h, k, cap=""):
    return f'<figure><img src="{src}" width="{w * k}" height="{h * k}" alt=""><figcaption>{cap}</figcaption></figure>'


def tog(before, after, lab_b="ANTES", lab_a="DEPOIS"):
    return (f'<div class="tog"><img src="{after}" alt=""><img class="b" src="{before}" alt="">'
            f'<span class="b">{lab_b}</span><span class="a">{lab_a}</span></div>')


def fig(src, cap):
    return f'<figure><img class="px" src="{src}" alt=""><figcaption>{cap}</figcaption></figure>'


def cat_row(prefix, name, reg, title, desc, files, k, extra=""):
    names = [f"{prefix}_{name}_{v}" for v in range(3)]
    sizes = [files[f"{n}.png"]["size"] for n in names]
    ramp = files[f"{names[0]}.png"]["ramp"]
    big = "".join(chk(f"v9/cat/{n}.png", *_size(OUT / "cat" / f"{n}.png"), k, f"{n} · {s}") for n, s in zip(names, sizes))
    real = "".join(f'<img src="v9/cat/{n}.png" alt="">' for n in names)
    strip = f"v9/cat/strip_{name}.png"
    sw, sh = _size(OUT / "cat" / f"strip_{name}.png")
    return f"""<div class="cat"><div><h3><i class="rg" style="background:{REG_COL[reg]}"></i>{title}</h3>
<div class="meta">{prefix}_{name}_{{0..2}}.png</div><div class="meta">{" · ".join(sizes)} · rampa {ramp}</div>
<p>{desc}</p>{extra}</div>
<div><div class="chk">{big}<figure><div style="display:flex;gap:8px;align-items:flex-end">{real}</div>
<figcaption>tamanho real</figcaption></figure></div>
<img class="strip" src="{strip}" width="{sw * 2}" height="{sh * 2}" alt="">
<figcaption>as 3 variações nos 4 estágios (Tempestade · Árido · Névoa · Verde), 2×, só trocando a paleta</figcaption>
</div></div>"""


def build_section(files, b):
    import regions_v9 as V
    E = __import__("regions_v9_elements")
    regions = ["plateau", "bed", "salar", "basalt", "frost"]
    # ---- catálogo
    cat_html = []
    for reg in regions:
        rows = []
        for name, (r, title, desc) in V.DECALS.items():
            if r == reg:
                rows.append(cat_row("decal", name, reg, title, desc, files, 2))
        for name, (r, title, desc) in V.DECORS.items():
            if r == reg:
                extra = '<p><span class="tag">VERDE+</span>ganha musgo no Verde</p>' if name in V.MOSSY else ""
                rows.append(cat_row("decor", name, reg, title, desc, files, 4, extra))
        cat_html.append(f'<h3 style="margin-top:26px">{V.REGION_PT[reg].capitalize()}</h3>' + "".join(rows))
    # ---- formações pequenas
    frows = []
    for k, (fn, reg, tb) in E.SMALL_FORMS.items():
        idx, info, _, _ = V.forms()[k]
        w, h = idx.shape[1], idx.shape[0]
        fw, fh = _size(OUT / "cat" / f"foot_{k}.png")
        sw, sh = _size(OUT / "cat" / f"strip_form_{k}.png")
        n_tiles = len(info["tiles"])
        frows.append(f"""<tr><td><b>{info['name']}</b><br>{V.REGION_PT[reg]}<br><code>form_{k}.png</code><br>{w}×{h} ·
rampa {tb}<br>âncora {info['foot']} · bloqueia {n_tiles} tile{'s' if n_tiles > 1 else ''}<br>{V.SMALL_N[k]}</td>
<td><div class="chk" style="padding:8px">{chk(f"v9/cat/form_{k}.png", w, h, 2, "2×")}</div></td>
<td><div class="chk" style="padding:8px">{chk(f"v9/cat/foot_{k}.png", fw, fh, 1, "pegada (vermelho) · âncora (ponto)")}</div></td>
<td><img class="strip" src="v9/cat/strip_form_{k}.png" width="{sw}" height="{sh}" alt=""></td></tr>""")
    # ---- musgo
    moss = "".join(chk(f"v9/cat/decor_{n}_{v}_green.png", *_size(OUT / "cat" / f"decor_{n}_{v}_green.png"), 4,
                       f"decor_{n}_{v} + moss") for n in V.MOSSY for v in range(3))
    # ---- cenas
    sc = []
    for view, lab in (("plateau", "Planalto (com a depressão de leito seco)"), ("salar", "Salar"),
                      ("basalt", "Basalto"), ("frost", "Faixa gelada")):
        for st, stl in (("arid", "Árido"), ("green", "Verde")):
            a = f"v9/scene_{view}_{st}_antes.png"
            d = f"v9/scene_{view}_{st}_depois.png"
            sc.append(f"""<h3 style="margin-top:22px">{lab} · {stl}</h3><div class="grid2">
{fig(a, "<b>antes</b> · v8.3 aprovada")}{fig(d, "<b>depois</b> · com os elementos da v9")}</div>""")
    # ---- densidade
    drows = []
    for reg in regions:
        mix = ", ".join(f"<code>{n}</code> {w}" for n, w in V.DECAL_MIX_V9[reg])
        dec = ", ".join(f"<code>{n}</code> {p * 100:.1f}%" for n, p in V.DECOR_P_V9[reg])
        tot = sum(p for _, p in V.DECOR_P_V9[reg]) * 100
        sm = {"plateau": "split_rock 4–6", "salar": "salt_pillar 3–4", "basalt": "lava_tube 2–4",
              "frost": "ice_needles 3–5", "bed": "nenhuma (alaga no M3)"}[reg]
        old = {"plateau": "nenhuma", "salar": "salt_crystals 3,5%", "basalt": "shards 3,5%", "frost": "ice_chunks 3,5%",
               "bed": "nenhuma"}[reg]
        drows.append(f"<tr><td><b>{V.REGION_PT[reg]}</b></td><td>{V.DECAL_P_V9[reg] * 100:.0f}% · {mix}</td>"
                     f"<td>{dec} · <b>total {tot:.1f}%</b></td><td>{old}</td><td>{sm}</td></tr>")
    nd = sum(1 for k in files if k.startswith("decal_"))
    no = sum(1 for k in files if k.startswith("decor_") and "_moss_" not in k)
    nm = sum(1 for k in files if "_moss_" in k)
    nf = sum(1 for k in files if k.startswith("form_"))
    zw, zh = _size(OUT / "basalt_zoom_antes.png")
    html = f"""<!-- v9:begin -->
<section class="v9" id="v9"><h2>v9 · Mais elementos nas regiões + basalto sem retângulo (aprovado)</h2>
<p class="lede"><b>Aprovado pelo dono e promovido</b>: os PNGs estão em <code>assets/sprites/regions/</code> e os dados no
<code>regions_palettes.json</code> (formações pequenas em <code>formations</code>, rampa <code>MOSS</code> em <code>ramps</code>,
densidade em <code>v9_density</code>). A cópia em <code>reports/design/regioes/v9/pendentes/</code> fica de registro (mesmo
formato: modo P, 0..7 rampa, 8 contorno, 9 sombra, 255 transparente). São <b>{nd} decalques</b>, <b>{no} soltos com altura</b>, <b>{nm} overlays de musgo
(Verde+)</b> e <b>{nf} formações pequenas</b>, mais a candidata do <code>ground_basalt.png</code>.
Tudo natural, nada de construção, nada biológico (sem ossada); o musgo é o mesmo da cobertura do Verde que já existe.</p>

<h3 style="margin-top:26px">1 · Basalto: a célula retangular</h3>
<p class="lede">A fratura do basalto é um Voronoi de 9×9 sítios. O sítio (1, 4) caiu alinhado na horizontal e na
vertical com os 4 vizinhos, e as 4 bissetrizes viraram um retângulo (x 64–133, y 215–290). Um detector de células
“quadradas” (quanto da borda fica a menos de 9° de horizontal/vertical) achou mais 3 parecidas, menos visíveis. Os
4 sítios foram empurrados 0,3 célula na diagonal (<code>BASALT_NUDGE</code> em <code>regions_core.py</code>), e
nada mais mudou: são <b>{b['changed']} px</b> de 262.144 (0,5%). A emenda continua: o Voronoi é periódico e o
empurrão vale pro sítio em qualquer volta (fração de pixel diferente na emenda {b['seam_new'][0]} contra
{b['seam_new'][1]} entre colunas vizinhas no miolo, igual à v8.3).</p>
<div class="grid2" style="margin-top:12px">
<figure><img src="v9/basalt_zoom_antes.png" width="{zw}" height="{zh}" style="image-rendering:pixelated;max-width:100%;height:auto" alt="">
<figcaption><b>antes</b> (3×) · a caixa vermelha é a célula</figcaption></figure>
<figure><img src="v9/basalt_zoom_depois.png" width="{zw}" height="{zh}" style="image-rendering:pixelated;max-width:100%;height:auto" alt="">
<figcaption><b>depois</b> (3×) · o retângulo virou 3 fraturas tortas</figcaption></figure>
<figure><img class="px" src="v9/basalt_tile3x3_antes.png" alt=""><figcaption><b>antes</b> · ladrilhado 3×3 (1536 px,
reduzido) · o retângulo se repete a cada 512 px</figcaption></figure>
<figure><img class="px" src="v9/basalt_tile3x3_depois.png" alt=""><figcaption><b>depois</b> · ladrilhado 3×3</figcaption></figure>
</div>
<div class="grid2" style="margin-top:12px"><div>{tog("v9/basalt_full_antes.png", "v9/basalt_full_depois.png")}
<figcaption>a textura inteira (512 px), alternando antes × depois a cada 2 s</figcaption></div>
<div class="box"><ul><li><b>Promovido</b>: <code>BASALT_FIX = True</code> no <code>regions_core.py</code>; o <code>assets/sprites/regions/ground_basalt.png</code>
é igual à candidata (<code>v9/ground_basalt.png</code>). Os 1.421 px que mudaram ficam todos nas 4 células empurradas
(mais 3 px de borda), conferido.</li>
<li>Com <code>BASALT_FIX = False</code> o script gera byte a byte a textura da v8.3 (é o “antes” do report).</li></ul></div></div>

<h3 style="margin-top:34px">2 · Catálogo dos elementos novos</h3>
<p class="lede">Cada região ganhou decalques de chão (não colidem) e pelo menos 2 tipos de solto com altura (não
colidem, ordenados pelo pé, até 32×28), com 3 variações cada. Os soltos são <b>volumes 3D</b> no mesmo renderizador
das formações (luz em faixas, sombra própria e no chão em alfa fixo, contorno <code>#1b1630</code>), menos as lajes e
as lascas de lama, que são desenho 2D. A tira de cada um mostra os 4 estágios só trocando a rampa.
<b>Ficaram de fora</b> (testei e não passaram): o <b>geodo</b> (em 20 px o miolo claro dentro da casca lia como
comida ou como rosto) e a <b>pedra equilibrada</b> (lia como cogumelo, e o hoodoo já ocupa essa ideia); no lugar
entraram as <b>lajes lascadas</b> e a <b>pedra rachada</b>.</p>
{''.join(cat_html)}

<h3 style="margin-top:30px">Verde+ · musgo nas pedras</h3>
<p class="lede">Só no Verde. A pedra média do planalto e o toco de coluna do basalto ganham um overlay
<code>decor_{{boulder,column_stub}}_moss_{{0..2}}.png</code> (mesmo tamanho da pedra, desenhado por cima, índices 0..3
na rampa fixa <code>MOSS</code>: {", ".join(f"<code>{c}</code>" for c in E.MOSS)}, a família do musgo da cobertura).
Nos outros estágios a pedra aparece limpa.</p>
<div class="chk">{moss}</div>

<h3 style="margin-top:30px">Formações pequenas (opcionais)</h3>
<p class="lede">Menores que as de hoje, mesmo esquema: volume 3D, ancoradas no centro da base, ordenadas pelo pé,
bloqueiam só os tiles do pé (tile <code>FORMATION</code>), não mineram. Não viram marcador “Formação” no mapa
(são miúdas); se o dono quiser, entram com o mesmo pictograma.</p>
<table style="margin-top:10px"><tr><th>formação</th><th>sprite (2×)</th><th>pegada</th><th>4 estágios</th></tr>
{''.join(frows)}</table>

<h3 style="margin-top:34px">3 · As regiões antes × depois</h3>
<p class="lede">Mesma vista, mesmo mundo de exemplo da v8 (sem HUD, pra ver o chão). O “depois” só acrescenta: os
decalques novos num 3º sorteio por célula de 96 px, os soltos novos por tile e 1 ou 2 formações pequenas por vista.
No Verde as bacias estão cheias (L3), então o leito seco some debaixo d'água, como vai ser no jogo.</p>
<div class="grid2" style="margin-top:12px"><div>{tog("v9/scene_plateau_arid_antes.png", "v9/scene_plateau_arid_depois.png")}
<figcaption>planalto no Árido, alternando a cada 2 s</figcaption></div>
<div>{tog("v9/scene_basalt_arid_antes.png", "v9/scene_basalt_arid_depois.png")}
<figcaption>basalto no Árido, alternando a cada 2 s</figcaption></div></div>
{''.join(sc)}
<h3 style="margin-top:22px">Os outros 2 estágios (planalto, depois)</h3><div class="grid2">
{fig("v9/scene_plateau_storm_depois.png", "<b>Tempestade</b>")}{fig("v9/scene_plateau_mist_depois.png", "<b>Névoa</b> · água no L2")}</div>

<h3 style="margin-top:34px">4 · Densidade sugerida</h3>
<table><tr><th>região</th><th>decalques v9 (3º sorteio na célula de 96 px: chance · pesos)</th>
<th>soltos v9 (chance por tile de chão livre)</th><th>soltos da v8 (continuam)</th><th>formações pequenas por mundo</th></tr>
{''.join(drows)}</table>
<div class="box" style="margin-top:10px"><p>Os números são de partida, ajustáveis no <code>game/config.py</code>
(na mesma linha do <code>GROUND_*</code>). Ficam todos em <code>v9/pendentes/regions_v9.json</code>
(<code>decal_p_v9</code>, <code>decal_mix_v9</code>, <code>decor_p_v9</code>, <code>small_formations</code>).</p></div>

<h3 style="margin-top:34px">Pro Dev integrar (v9)</h3>
<div class="box dev"><ul>
<li><b>Basalto</b>: trocar o <code>ground_basalt.png</code> pela candidata. Mesmo tamanho, mesma paleta, mesma regra de
recorte; nada muda no código.</li>
<li><b>Decalques</b> (<code>decal_*.png</code> novos, rampa <code>BASE</code> da região onde caem, leito seco = <code>bed</code>):
na mesma grade de 96 px presa no mundo, um <b>3º sorteio por célula</b>, com hash próprio, posição própria e só a
lista da v9 da região (<code>decal_mix_v9</code>) com a chance <code>decal_p_v9</code>. Espelhar na horizontal com 50%.
Mesmas exclusões de hoje (raio de 6 tiles da base, volta das formações). Entram na camada do chão, antes da água e
da cobertura (a água e a grama tapam).</li>
<li><b>Soltos</b> (<code>decor_*.png</code> novos): como os de hoje. Âncora no centro da base, pé em
<code>(tx·32 + 16 ± 7, ty·32 + 26..29)</code>, ordenados pelo pé, espelho horizontal com 50%, não colidem. 1 sorteio por
tile de chão livre (<code>decor_p_v9</code>, as chances somam); some onde tem máquina, veio, destroço, rocha,
parede, formação e no tile com o solto da v8; nada abaixo do nível d'água atual. Rampa pela tabela do arquivo
(<code>files[...].ramp</code> no JSON): seixos, pedra média, lajes, bombas, toco e pedra com geada = <code>HILL</code> da região
(seixo no leito seco usa o <code>HILL</code> do planalto); montinho de sal, crosta solta e lascas de lama =
<code>BASE</code>; penitentes = <code>ICE</code>.</li>
<li><b>Verde+</b>: no estágio Verde, desenhar <code>decor_X_moss_N.png</code> logo depois de <code>decor_X_N.png</code>, no mesmo
lugar e com o mesmo espelho. Paleta fixa <code>MOSS</code> (índices 0..3; 8 = contorno). Na mancha da transição, segue
o estágio do tile do pé.</li>
<li><b>Formações pequenas</b> (<code>form_split_rock</code>, <code>form_salt_pillar</code>, <code>form_lava_tube</code>,
<code>form_ice_needles</code>): igual às formações de hoje (<code>hills.FormationSprites</code>): âncora do JSON no
<code>base_px</code>, ordem pelo pé, pegada vira <code>FORMATION</code>, sombra já vem no sprite (índice 9). Rampa: pedra
rachada e tubo de lava = <code>HILL</code>; pilar de sal = <code>BASE</code> do salar; agulhas = <code>ICE</code>. Geração: inteira na
região, fora de bacia, 2 tiles de folga, a 10+ tiles uma da outra e das grandes, a 20+ da base; sem afloramento em
volta (são miúdas).</li>
<li><b>Ordem de desenho</b> não muda: chão → decalques (v8 + v9) → água/cobertura → por linha: morros, objetos pelo pé
(soltos, formações, player, máquinas) → efeitos do estágio.</li></ul></div>

<h3 style="margin-top:34px">Contrato · aprovado, já na bíblia §6</h3>
<div class="box"><ul>
<li><code>decal_*.png</code>: a tabela já cobre (“variados”, rampa BASE). Entram os nomes novos:
<code>decal_{{vein,oxide,saltpoly,efflor,fumarole,ropy,icepoly,rime,trail,ripples}}_{{0..2}}.png</code>.</li>
<li><code>decor_*</code>: a linha vira <code>decor_{{shards,salt_crystals,ice_chunks,pebbles,boulder,slabs,salt_mound,salt_slabs,
bombs,column_stub,penitentes,rimed_rock,mud_curls}}_{{0..2}}.png</code>, “até 32×28” (hoje diz 28×24; os novos
vão até 31×26), com a rampa de cada um no JSON.</li>
<li>Linha nova: <code>decor_{{boulder,column_stub}}_moss_{{0..2}}.png</code> · mesmo tamanho da pedra · overlay só no Verde,
rampa fixa <code>MOSS</code> (nova no <code>regions_palettes.json</code>, como a <code>METAL</code>).</li>
<li><code>form_*</code>: entram <code>form_{{split_rock,salt_pillar,lava_tube,ice_needles}}.png</code> (até 124×56), com a pegada:
pedra rachada 1, pilar de sal 1, tubo de lava 3×1, agulhas de gelo 3×1.</li>
<li><code>ground_basalt.png</code>: sem mudança de contrato (mesmo arquivo, mesmo tamanho).</li></ul></div>

<h3 style="margin-top:34px">O que aproveitei de referência</h3>
<div class="box"><p>Nenhuma imagem de fora: só a geologia de verdade de desertos e lugares frios, desenhada do zero
no estilo aprovado. Salar: polígonos de sal e eflorescência dos lagos salgados secos. Basalto: lava em corda
(pahoehoe), tubos de lava com claraboia e bombas vulcânicas. Faixa gelada: penitentes e solo poligonal de permafrost.
Leito seco: rastro de pedra arrastada no lodo e marca de onda fossilizada. Planalto: veio de quartzo exposto e
anéis de oxidação.</p></div>
</section>
<!-- v9:end -->"""
    note = """<!-- v9note:begin -->
<div class="v2"><b>v9.0 · o que mudou (aprovado e promovido)</b><ul>
<li><b>Basalto sem o retângulo</b>: a célula quase retangular do <code>ground_basalt.png</code> (e mais 3 parecidas)
quebrada empurrando só 4 sítios do Voronoi. Continua emendando e com a mesma cara. Antes × depois e ladrilhado 3×3
na <a href="#v9">seção v9</a>.</li>
<li><b>Mais elementos por região</b>: 10 decalques novos, 10 soltos com altura novos (3 variações cada), musgo
Verde+ em 2 deles e 4 formações pequenas, com cenas antes × depois no Árido e no Verde e a densidade sugerida.</li>
<li>A v8.3 continua aprovada e intacta logo abaixo.</li></ul></div>
<!-- v9note:end -->"""
    return html, note


def inject(html: str) -> str:
    """Põe a nota e a seção v9 no index (idempotente)."""
    sec = OUT / "section.html"
    note = OUT / "note.html"
    if not sec.exists():
        return html
    html = re.sub(r"<!-- v9:begin -->.*?<!-- v9:end -->\n*", "", html, flags=re.S)
    html = re.sub(r"<!-- v9note:begin -->.*?<!-- v9note:end -->\n?", "", html, flags=re.S)
    html = re.sub(r"/\* v9css \*/.*?/\* /v9css \*/\n?", "", html, flags=re.S)
    html = html.replace("</style>", "/* v9css */" + CSS_V9 + "/* /v9css */\n</style>", 1)
    html = re.sub(r"<!-- v91:begin -->.*?<!-- v91:end -->\n*", "", html, flags=re.S)
    html = re.sub(r"<!-- v91note:begin -->.*?<!-- v91note:end -->\n?", "", html, flags=re.S)
    sec91, note91 = OUT.parent / "v91" / "section.html", OUT.parent / "v91" / "note.html"
    has91 = sec91.exists() and note91.exists()
    css = CSS_V9
    if has91:
        import regions_v91_report
        css += regions_v91_report.CSS_V91
    html = html.replace("/* v9css */" + CSS_V9 + "/* /v9css */", "/* v9css */" + css + "/* /v9css */", 1)
    ver = "v9.1" if has91 else "v9.0"
    html = re.sub(r"<title>.*?</title>", f"<title>Hesper · Geografia nova · {ver}</title>", html, count=1)
    eb = ("v9.1 · v0.4 regiões · PROPOSTA: fumarolas ativas · v9 aprovada (a v8.3 continua abaixo)" if has91 else
          "v9.0 · v0.4 regiões · mais elementos por região + basalto, aprovado (a v8.3 continua abaixo)")
    html = re.sub(r'<div class="eyebrow">.*?</div>', f'<div class="eyebrow">Hesper · Designer · {eb}</div>', html, count=1)
    top_note = (note91.read_text() + "\n" if has91 else "") + note.read_text()
    top_sec = (sec91.read_text() + "\n\n" if has91 else "") + sec.read_text()
    html = html.replace('<div class="v2"><b>v8.3 · o que mudou</b>', top_note + '\n<div class="v2"><b>v8.3 · o que mudou</b>', 1)
    html = html.replace("<section><h2>Resumo · recomendação e custo</h2>", top_sec + "\n\n<section><h2>Resumo · recomendação e custo</h2>", 1)
    return html


def build(files, b):
    sec, note = build_section(files, b)
    (OUT / "section.html").write_text(sec, encoding="utf-8")
    (OUT / "note.html").write_text(note, encoding="utf-8")
    page = REG / "index.html"
    page.write_text(inject(page.read_text(encoding="utf-8")), encoding="utf-8")
    return page
