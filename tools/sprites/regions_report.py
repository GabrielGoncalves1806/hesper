"""Report da GEOGRAFIA NOVA (v8.0 · v0.4 Marco 2): reports/design/regioes/index.html.
Chamado no fim do tools/sprites/regions_mockups.py (não roda sozinho: precisa das imagens geradas)."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

import regions_core as R

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "design" / "regioes"
PEND = ROOT / "assets" / "sprites" / "_pending" / "regions"

CSS = """
:root{--bg:#15100e;--panel:#1e1714;--panel2:#241b17;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;--alert:#ff6a55;
  --f-label:"Silkscreen",ui-monospace,monospace;--f-display:"Pixelify Sans",ui-monospace,monospace;--f-body:"IBM Plex Sans",system-ui,sans-serif;--f-mono:"IBM Plex Mono",ui-monospace,monospace;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--fg);font:15px/1.6 var(--f-body);padding-inline:16px}
.wrap{max-width:1500px;margin:0 auto;padding-block:48px 80px}
.eyebrow{font:12px var(--f-label);letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
h1{font:600 clamp(34px,6vw,54px)/1.05 var(--f-display);margin:10px 0 14px}
.lede{color:var(--muted);max-width:90ch;margin:0}
h2{font:600 24px/1.2 var(--f-display);margin:0 0 16px}
h2::before{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}
h3{font:600 18px var(--f-display);margin:0 0 8px}
section{margin-top:60px}
code{font-family:var(--f-mono);font-size:.92em;color:var(--gold)}
img.px{image-rendering:pixelated;display:block;width:100%;height:auto;border:1px solid var(--line)}
.v2{margin-top:22px;max-width:1040px;background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--gold);padding:14px 18px}
.v2 > b{font:13px var(--f-label);color:var(--gold)}
.v2 ul{margin:8px 0 0;padding-left:18px;color:var(--muted)}.v2 li{margin-bottom:6px}.v2 li b{color:var(--fg)}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
@media (max-width:1100px){.grid2,.grid3,.grid4{grid-template-columns:1fr}}
figure{margin:0}
figcaption{font:12px var(--f-label);color:var(--muted);margin-top:6px;letter-spacing:.04em}figcaption b{color:var(--fg)}
.one{max-width:960px}
.box{background:var(--panel);border:1px solid var(--line);padding:18px 20px}
.box ul{margin:0;padding-left:18px;color:var(--muted)}.box li{margin-bottom:8px}.box li b{color:var(--fg)}
.box p{color:var(--muted);margin:6px 0}
.dev{border-left:3px solid var(--cyan)}.reco{border-left:3px solid var(--ok)}
.reg{background:var(--panel);border:1px solid var(--line);padding:16px 18px;border-top:4px solid var(--c)}
.reg p,.reg li{color:var(--muted)}.reg ul{padding-left:18px;margin:6px 0}.reg li b{color:var(--fg)}
.sws{display:flex;gap:3px;margin:8px 0}.sws i{width:24px;height:24px;border:1px solid rgba(255,255,255,.12)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{font:12px var(--f-label);color:var(--gold);background:var(--panel2)}td{color:var(--muted)}td b{color:var(--fg)}
.chk{display:flex;gap:22px;align-items:flex-end;flex-wrap:wrap;padding:14px;
  background-color:#2a211d;background-image:conic-gradient(#3a2e28 25%,transparent 0 50%,#3a2e28 0 75%,transparent 0);background-size:16px 16px;border:1px solid var(--line)}
.chk figure{margin:0}.chk img{image-rendering:pixelated;display:block}
.chk figcaption{font:11px var(--f-mono);color:var(--fg);text-shadow:0 1px 0 #000}
.tag{display:inline-block;font:11px var(--f-label);padding:2px 6px;border:1px solid var(--line);color:var(--gold);margin-right:6px}
/* ciclo de quadros (antes de tudo, no lugar): cada img aparece 1/N do tempo */
.cyc{position:relative;aspect-ratio:16/9;border:1px solid var(--line);overflow:hidden}
.cyc img{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated;opacity:0;animation:show4 var(--d,8s) infinite}
.cyc.sq{aspect-ratio:auto;width:var(--w);height:var(--h);border:0}
.cyc span{position:absolute;left:8px;bottom:8px;font:12px var(--f-label);background:#0f1119;padding:3px 7px;opacity:0;animation:show4 var(--d,8s) infinite}
@keyframes show4{0%,24.9%{opacity:1}25%,100%{opacity:0}}
.cyc.c5 img,.cyc.c5 span{animation-name:show5}
@keyframes show5{0%,19.9%{opacity:1}20%,100%{opacity:0}}
.d1{animation-delay:calc(var(--d,8s) * -0.75)!important}.d2{animation-delay:calc(var(--d,8s) * -0.5)!important}.d3{animation-delay:calc(var(--d,8s) * -0.25)!important}
"""


def swatches(region, stage="arid", table=None):
    r = R.ramp(region, stage, table)[:8]
    return '<div class="sws">' + "".join(f'<i style="background:{R.hexc(c)}" title="{R.hexc(c)}"></i>' for c in r) + "</div>"


def fig(src, cap, cls="px"):
    return f'<figure><img class="{cls}" src="{src}" alt=""><figcaption>{cap}</figcaption></figure>'


def chk_img(src, cap, w, h, k=2):
    return (f'<figure><img src="{src}" width="{w * k}" height="{h * k}" alt=""><figcaption>{cap}</figcaption>'
            f'</figure>')


def cycle(frames, labels, d="8s"):
    cls = ["", " d1", " d2", " d3"]
    imgs = "".join(f'<img class="{cls[i].strip()}" src="{f}" alt="">' for i, f in enumerate(frames))
    spans = "".join(f'<span class="{cls[i].strip()}">{lab}</span>' for i, lab in enumerate(labels))
    return f'<div class="cyc" style="--d:{d}">{imgs}{spans}</div>'


def cycle5(frames, labels, d="7.5s"):
    imgs = "".join(f'<img style="animation-delay:calc(var(--d) * {-i / 5:.2f} * -1 - var(--d))" src="{f}" alt="">'
                   for i, f in enumerate(frames))
    spans = "".join(f'<span style="animation-delay:calc(var(--d) * {-i / 5:.2f} * -1 - var(--d))">{lab}</span>'
                    for i, lab in enumerate(labels))
    return f'<div class="cyc c5" style="--d:{d}">{imgs}{spans}</div>'


def build():
    data = json.loads((PEND / "regions_palettes.json").read_text())
    forms = data["formations"]
    files = data["files"]
    n_pend = len(list(PEND.glob("*.png")))

    regions = [
        ("plateau", "#8a573a", "Planalto rachado", "em volta da base · o “normal” do planeta",
         "Terra e rocha seca ocre-ferrugem (sai do vermelho de hoje e puxa pro ocre da referência). "
         "Textura grande de 512 px com manchas suaves de baixo contraste, pedrisco e poucas fendas.",
         ["<b>Hoodoo</b> (fuste de arenito com pedra de topo, 1 tile de pé)", "<b>Arco natural</b> (5 tiles, vão de 3 "
          "por onde se passa)", "<b>Morros mineráveis</b> com borda orgânica (ferro e silício)",
          "<b>Depressões pequenas</b> com leito seco e marca d'água"],
         ["Manchas grandes escuras e claras (3 a 7 tiles)", "Rachaduras longas com galhos (4 a 7 tiles)",
          "Placas soltas levantadas", "Cascalho", "Sulcos de vento (leste, 8° descendo, igual ao vento da tempestade)"]),
        ("salar", "#c6b8a4", "Salar", "leito de lago seco · a maior depressão · vira o grande lago no Marco 3",
         "Crosta de sal creme, um tico rosada (não é branco de neve: fica na família do planeta e não briga com o "
         "traje branco). Polígonos de ~50 px com crista clara e sombra embaixo, rede fina por dentro.",
         ["<b>Crosta de sal elevada</b> (placas grossas empurradas, 5×1 tiles, baixa)",
          "Sem morros: é plano de propósito, pra ler como fundo de lago",
          "Anéis de marca d'água (L1, L2, L3) em anel escuro"],
         ["Cristinhas de sal", "Manchas de crosta úmida (mais escura)", "Rachaduras", "Cristais de sal soltos "
          "(com altura, não colidem)"]),
        ("basalt", "#3a343e", "Basalto", "escuro, rochas pontudas · no futuro vira vulcão",
         "Rocha escura fria com fraturas retas e angulosas, escória e manchas de óxido apagadas "
         "(nada de laranja vivo: o vulcão é só gancho, por enquanto está extinto).",
         ["<b>Basalto colunar</b> (prismas hexagonais em degraus, 3×2 tiles)",
          "<b>Cone de escória</b> (cratera no topo: o gancho do vulcão, 3×2 tiles)",
          "Morros escuros com mais ferro"],
         ["Escória (cascalho escuro)", "Manchas de óxido pintadas", "Rachaduras", "Lascas pontudas soltas (com altura, "
          "não colidem)"]),
        ("frost", "#90a6b9", "Faixa gelada", "borda norte · onde ficam os gelos-portão",
         "Geada por cima da rocha: azul-acinzentado com manchas claras e brilhos de gelo. Na Névoa a geada some "
         "e aparece rocha molhada; no Verde vira tundra com musgo.",
         ["<b>Gelos-portão</b> (bloco de gelo gigante com rocha presa dentro, 4×2 tiles) fechando corredores entre "
          "morros", "Morros gelados com muito gelo", "Atrás do portão: destroço melhor + contêiner lacrado (Marco 3)"],
         ["Lâminas de gelo liso com reflexo", "Sulcos de geada", "Pedaços de gelo soltos (com altura, não colidem)"]),
    ]

    reg_html = ""
    for key, col, name, sub, ground, big, loose in regions:
        table = None
        reg_html += f"""<div class="reg" style="--c:{col}"><h3>{name}</h3><p><i>{sub}</i></p>
<b style="font:11px var(--f-label);color:var(--gold)">PALETA BASE (ÁRIDO)</b>{swatches(key)}
<p><b>Chão:</b> {ground}</p>
<img class="px" src="sprites/ground_{key}_arid.png" alt="" style="max-width:512px">
<p><b>Formações grandes:</b></p><ul>{''.join(f'<li>{x}</li>' for x in big)}</ul>
<p><b>Decoração solta:</b></p><ul>{''.join(f'<li>{x}</li>' for x in loose)}</ul></div>"""

    stage_tbl = "<table><tr><th>região</th>" + "".join(f"<th>{R.STAGE_NAME[s]}</th>" for s in R.STAGES) + "</tr>"
    for key, nm in (("plateau", "planalto"), ("salar", "salar"), ("basalt", "basalto"), ("frost", "gelada"),
                    ("bed", "leito seco")):
        stage_tbl += f"<tr><td><b>{nm}</b></td>" + "".join(
            f'<td><img class="px" src="sprites/ground_{key}_{s}.png" alt="" style="border:0">{swatches(key, s)}</td>'
            for s in R.STAGES) + "</tr>"
    stage_tbl += "</table>"

    form_rows = ""
    form_info = [
        ("monolith", "Hoodoo (monolito)", "planalto", "fuste de arenito que afina e engorda, com a pedra de topo "
         "mais dura (cinza, escura e inclinada) segurando tudo; camadas seguem a rocha"),
        ("arch", "Arco natural", "planalto", "erosão tipo Delicate Arch: perna esquerda maciça, direita fina com "
         "cintura, vão torto, buracos, ressaltos de estrato; só as pernas bloqueiam"),
        ("basalt_spires", "Basalto colunar", "basalto", "prismas hexagonais em patamares (Calçada dos Gigantes), "
         "topos claros em degrau, alguns quebrados em diagonal, colunas caídas em gomos, juntas transversais"),
        ("cone", "Cone de escória", "basalto", "relevo baixo com cratera no topo e sulcos de erosão; o pé some no "
         "chão (sem contorno embaixo); óxido apagado"),
        ("salt_ridge", "Crosta de sal elevada", "salar", "placas de sal empurradas e quebradas, cada uma no seu "
         "eixo, encavaladas; baixa, não esconde ninguém"),
        ("ice_gate_0", "Gelo-portão", "faixa gelada", "bloco poliédrico de gelo glacial translúcido (a rocha presa "
         "aparece por dentro); encolhe em 3 etapas e amolece as quinas"),
    ]
    for key, name, reg, note in form_info:
        new = f"sprites/form_{key}.png" if not key.startswith("ice") else "sprites/ice_gate_0.png"
        old = f"../before/regioes_v80_form_{key}.png" if not key.startswith("ice") else \
            "../before/regioes_v80_ice_gate_0.png"
        foot = f"sprites/foot_{key}.png"
        nw, nh = Image.open(OUT / new).size
        ow, oh = Image.open(OUT / old).size
        fk = key if key in forms else key
        info = forms[fk]
        tiles = info["tiles"]
        form_rows += f"""<tr><td><b>{name}</b><br>{reg}<br><span style="font-size:13px">{note}</span></td>
<td><div class="chk" style="padding:8px"><figure><img src="{old}" width="{ow * 2}" height="{oh * 2}" alt="">
<figcaption>v8.0</figcaption></figure></div></td>
<td><div class="chk" style="padding:8px"><figure><img src="{new}" width="{nw * 2}" height="{nh * 2}" alt="">
<figcaption>v8.1</figcaption></figure></div></td>
<td><img class="px" src="{foot}" alt="" style="max-width:300px;border:0"><br><b>{nw}×{nh}</b> px · bloqueia
<b>{len(tiles)} tile{'s' if len(tiles) > 1 else ''}</b></td></tr>"""

    pend_rows = "".join(f"<tr><td><code>{k}</code></td><td>{v['size']}</td><td>{v['ramp']}</td><td>{v['region']}</td></tr>"
                        for k, v in files.items())

    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Geografia nova · v8.1</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Pixelify+Sans:wght@400;600&family=Silkscreen&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v8.1 · v0.4 Marco 2 (geografia nova) · formações e cratera refeitas</div>
<h1>Regiões, relevo e água</h1>
<p class="lede">Objetivo: tirar a cara de “mapa gerado com tileset” e deixar a superfície orgânica e explorável. O
planeta é <b>árido e vazio, não areia</b>: rocha, terra seca, sal, basalto e geada. Tudo aqui sai de script
(<code>tools/sprites/regions_mockups.py</code>), em pixels reais 960×540 com a HUD B2 por cima. Nada disso está
no jogo ainda: é pra tu aprovar antes do código.</p>

<div class="v2"><b>v8.1 · o que mudou</b><ul>
<li><b>Formações refeitas como rocha natural</b> (seção 4, com antes × depois): o arco virou arco de erosão
assimétrico e esburacado; o monolito virou <b>hoodoo</b> com pedra de topo; os pináculos viraram <b>basalto
colunar</b> hexagonal em degraus com colunas caídas; a crosta de sal, o cone e o gelo-portão também foram
refeitos sem geometria de construção.</li>
<li>Por baixo: cada formação agora é um <b>volume 3D renderizado em pixel art</b> (<code>regions_volume.py</code>),
não polígono 2D.</li>
<li><b>Cratera de impacto</b> nova: borda elevada irregular, blocos e manto de ejeção, bacia rebaixada, rampa
entalhada descendo até o buraco no fundo. O gelo é uma tampa que baixa em <b>5 etapas</b> como lago secando, com
marcas de geada nas paredes.</li>
<li>Pegadas de colisão revistas: o cone agora bloqueia 3×2 (o pé baixo é andável); a cratera continua 3×3.
O resto não mudou.</li>
<li>Regiões, paletas, estágios por cor, decalques, morros e água: <b>aprovados</b>, sem mudança.</li></ul></div>
<div class="v2" style="opacity:.75"><b>v8.0 · aprovado (menos as formações e a cratera)</b><ul>
<li><b>3 regiões + faixa gelada</b> com paleta base própria, chão de textura grande (sem repetir tile) e borda
entre regiões deformada (curva irregular, nunca linha de tile).</li>
<li><b>4 estágios por variação de cor</b>: 1 rampa de 8 cores por região, e a Tempestade, a Névoa e o Verde saem de
uma conta fixa em cima dela. São 5 conjuntos de chão (com o leito seco), e não 12 desenhados à mão.</li>
<li>6 formações fixas e a tampa da cratera (refeitas na v8.1).</li>
<li><b>Decoração que quebra a grade</b>: manchas, rachaduras longas, placas, cascalho, sulcos de vento, entulho no
pé dos morros, e coisas soltas com altura por região.</li>
<li><b>Morros com borda orgânica</b> (grade dual: a escada vira curva, a colisão continua a do tile).</li>
<li><b>Relevo e água</b>: bacias com leito seco e marca d'água (L1, L2, L3) que enchem na Névoa e no Verde; o salar
vira o grande lago.</li>
<li>Sem ossada nenhuma, como pedido.</li></ul></div>

<section><h2>Resumo · recomendação e custo</h2>
<table><tr><th>item</th><th>recomendação</th><th>arte (Designer)</th><th>Dev</th></tr>
<tr><td><b>1 · Regiões</b></td><td>As 3 + faixa gelada como estão; planalto no centro, salar a leste, basalto a
oeste/sudoeste, gelo no norte (mapa abaixo).</td><td>pronto · ajuste fino de cor depois do playtest (~0,5 dia)</td><td>médio:
mapa de região no gerador + chão por região</td></tr>
<tr><td><b>2 · Bordas orgânicas</b></td><td>Deslocamento de domínio de ±14 px (borda curva) + 1 px de fenda
na divisa.</td><td>pronto</td><td>médio (ver “Pro Dev”: fácil com numpy)</td></tr>
<tr><td><b>3 · Estágios por cor</b></td><td>Sim: PNG indexado + rampa por estágio. Grama, umidade e água vêm por
cima, como camadas.</td><td>pronto</td><td>baixo (troca de paleta no load)</td></tr>
<tr><td><b>4 · Formações</b></td><td>Entram as 6 (refeitas na v8.1); o gelo-portão em 3 etapas e a cratera em 5 são
o Marco 3.</td><td>pronto · polir 1 ou 2 depois de ver no jogo (~1 dia)</td><td>baixo: objeto com pegada de colisão
(igual ao destroço)</td></tr>
<tr><td><b>5 · Decoração</b></td><td>Entra primeiro (o maior ganho pelo menor custo, como a spec já previa).</td><td>pronto
(36 decalques + 9 soltos)</td><td>baixo</td></tr>
<tr><td><b>6 · Morros</b></td><td>Grade dual (marching squares) + face por extrusão.</td><td>pronto (topo e face
indexados)</td><td>médio</td></tr>
<tr><td><b>7 · Relevo e água</b></td><td>Altura por noise, bacias marcadas, 3 níveis. A marca d'água seca mostra
onde vai alagar.</td><td>pronto</td><td>médio/alto (é o Marco 3)</td></tr></table></section>

<section><h2>1 · As regiões</h2>
<div class="grid2" style="align-items:start">
<figure><img class="px" src="mapa_regioes.png" alt="" style="max-width:576px"><figcaption><b>mapa 192×192 da proposta</b>
(3 px por tile) · triângulo = formação · quadrado azul = gelo-portão · círculo = cratera com gelo · base no meio ·
linhas azuis = marcas d'água L1/L2/L3 · retângulos = as vistas dos mockups</figcaption></figure>
<div class="box reco"><h3>Como o mapa se organiza</h3><ul>
<li><b>Planalto rachado</b> em volta da base (raio ~45 tiles): o começo calmo, com morros e 3 depressões pequenas.</li>
<li><b>Salar</b> a leste: a <b>maior depressão</b> (elipse de ~62×50 tiles), sem morro nenhum.</li>
<li><b>Basalto</b> a oeste e sudoeste, um pouco mais alto, com mais morros e mais ferro.</li>
<li><b>Faixa gelada</b> na borda norte (~24 tiles), com os gelos-portão fechando corredores entre morros. O
contêiner lacrado fica atrás deles.</li>
<li>A <b>cratera</b> nasce coberta de gelo (tampa em 3 etapas).</li>
<li>O que o dono mandou de referência (<code>tempestade/referencia_dono.png</code>), aproveitado só como estilo:
chão aparecendo em <b>graus diferentes</b> (manchas grandes de tom, baixo contraste), <b>sulcos de vento</b>
longos e finos e nada de duna. Não copiei nenhum desenho.</li></ul></div></div>
<div class="grid2" style="margin-top:16px">{reg_html}</div></section>

<section><h2>2 · As regiões no Árido (960×540, HUD B2)</h2>
<div class="grid2">
{fig("arid_base.png", "<b>planalto · a base</b> · cratera com a tampa de gelo (canto direito)")}
{fig("arid_plateau.png", "<b>planalto</b> · arco, monolito, afloramentos e uma depressão com leito seco")}
{fig("arid_salar.png", "<b>salar</b> · crosta poligonal, crosta elevada, afloramentos de silício")}
{fig("arid_basalt.png", "<b>basalto</b> · pináculos, cone, lascas soltas, morros escuros com ferro")}
{fig("arid_frost.png", "<b>faixa gelada</b> · gelo-portão fechando o corredor entre 2 morros gelados")}
{fig("../before/regioes_hoje_arido.png", "<b>antes · o jogo hoje</b> no Árido (mesmo chão em todo canto)")}
</div>
<h3 style="margin-top:26px">Passagem de uma região pra outra</h3>
<p class="lede">A região de cada pixel é a do tile em (x + dx, y + dy), com dx e dy vindos de um ruído preso no
mundo (até ±14 px). A divisa vira curva irregular; 1 px de fenda escura marca o encontro.</p>
<div class="grid3" style="margin-top:10px">
{fig("arid_t_salar.png", "<b>planalto → salar</b>")}
{fig("arid_t_basalt.png", "<b>planalto → basalto</b>")}
{fig("arid_t_frost.png", "<b>planalto → faixa gelada</b>")}
</div></section>

<section><h2>3 · Os 4 estágios numa região (planalto)</h2>
<div class="grid2">
<div>{cycle(["stage_storm.png", "stage_arid.png", "stage_mist.png", "stage_green.png"],
            ["1 · TEMPESTADE", "2 · ÁRIDO", "3 · NÉVOA", "4 · VERDE"])}<figcaption>ciclo de 2 s por estágio · mesma
vista</figcaption></div>
<div class="box reco"><h3>“Paleta base + variação”</h3><ul>
<li>Cada região tem <b>1 rampa de 8 cores</b> (fenda, sombra, escuro, base, claro, brilho, 2 acentos). Os
sprites são <b>PNG indexado</b>: o índice é o desenho, a rampa é a cor.</li>
<li><b>Tempestade</b>: puxa 30% pro ocre da poeira e achata o contraste (a poeira assentou) + a camada de poeira
que já está no jogo.</li>
<li><b>Árido</b>: a rampa base.</li>
<li><b>Névoa</b>: 45% menos saturação, 16% mais escuro, véu cinza-azulado; na faixa gelada a geada vira rocha
molhada. Por cima: manchas de umidade, chuva e as bacias enchendo.</li>
<li><b>Verde</b>: terra com matéria orgânica (mistura de verde-oliva, mais forte no planalto e na faixa gelada,
fraca no salar). Por cima: <b>grama/musgo como camada com borda deformada</b> (musgo no basalto), que prefere a
beira d'água, e as plantas de hoje.</li>
<li>Resultado: <b>5 conjuntos de chão</b> (4 regiões + o leito seco) × 1 desenho cada.</li></ul></div></div>
<div class="grid4" style="margin-top:14px">
{fig("stage_storm.png", "<b>Tempestade</b>")}{fig("stage_arid.png", "<b>Árido</b>")}
{fig("stage_mist.png", "<b>Névoa</b> · água no L2, chuva")}{fig("stage_green.png", "<b>Verde</b> · água no L3, grama")}
</div>
<h3 style="margin-top:22px">As rampas (região × estágio)</h3>{stage_tbl}</section>

<section><h2>4 · Formações fixas (marcos, não mineráveis) · refeitas na v8.1</h2>
<p class="lede">Na v8.0 elas eram desenhadas como polígonos e faixas 2D, e por isso viravam “construção” (ponte,
torre, bambu). Agora cada uma é um <b>volume 3D</b> (densidade com ruído de erosão) renderizado na projeção do jogo
(o pixel (x, y) vê o ponto mais alto com x = X e y = Y − Z), com luz em 5 faixas chapadas, sombra própria e
projetada (alfa fixo), linha escura onde uma parte passa na frente da outra e contorno <code>#1b1630</code>.
Continua sendo pixel art chapado, só que a FORMA é de rocha. Sprite ancorado no centro da base, ordenado pelo pé;
bloqueia <b>só os tiles do pé</b> (vermelho na grade).</p>
<table style="margin-top:12px"><tr><th>formação</th><th>antes (2×)</th><th>depois (2×)</th><th>pegada (vermelho = bloqueia,
ponto = âncora)</th></tr>{form_rows}</table>

<h3 style="margin-top:30px">Cratera de impacto (refeita)</h3>
<div class="grid2">
<div><div class="chk" style="padding:10px;justify-content:space-around">
<figure><img src="../before/regioes_v80_crater_ice_0.png" width="192" height="192" alt=""><figcaption>antes · buraco
com tampa</figcaption></figure>
<figure><img src="sprites/crater_impact_0.png" width="336" height="300" alt=""><figcaption>depois · cratera de
impacto com a tampa de gelo</figcaption></figure></div></div>
<div class="box reco"><h3>Como ficou</h3><ul>
<li><b>Borda elevada irregular</b> (crista 9 px acima do chão, contorno torto), com <b>blocos ejetados</b> na borda e
fora dela, e um decalque de chão (<code>crater_ejecta.png</code>) com o manto de ejeção e pedrisco que rareia pra
fora.</li>
<li><b>Bacia rebaixada</b> (19 px abaixo do chão no fundo), parede de dentro mais escura, sombra própria do lado
oposto à luz.</li>
<li><b>Rampa integrada</b>: um entalhe na borda sul (de frente pra câmera) descendo em degraus de metal (a família
da <code>crater_ramp</code> de hoje, com os postes laranja na entrada) até o <b>buraco</b> no fundo da bacia, a boca
da caverna.</li>
<li><b>O gelo é uma tampa que enche a bacia</b> e baixa como lago secando: o nível cai, ficam <b>marcas de geada</b>
nas paredes nos níveis por onde passou, e no fim a cratera fica vazia com o buraco e a rampa expostos.</li></ul></div></div>
<div class="grid2" style="margin-top:14px">
<div>{cycle5(["crater_melt_0.png", "crater_melt_1.png", "crater_melt_2.png", "crater_melt_3.png", "crater_melt_4.png"],
             ["0 · TAMPA CHEIA", "1 · BAIXOU", "2 · METADE", "3 · SÓ NO FUNDO", "4 · VAZIA, RAMPA EXPOSTA"])}
<figcaption><b>as 5 etapas</b> (1,5 s cada) · <code>crater_impact_0..4.png</code></figcaption></div>
<div>{fig("arid_crater.png", "<b>a cratera no jogo</b> (Árido, HUD B2), etapa 0")}</div></div>
<div class="chk" style="margin-top:12px">
{''.join(chk_img(f"sprites/crater_impact_{k}.png", f"crater_impact_{k}", 168, 150) for k in range(5))}</div>

<h3 style="margin-top:26px">Gelo-portão derretendo</h3>
<div class="grid2">
<div>{cycle(["gate_melt_0.png", "gate_melt_1.png", "gate_melt_2.png", "gate_melt_3.png"],
            ["INTEIRO", "ETAPA 1", "ETAPA 2", "ABERTO"], "6s")}<figcaption><b>gelo-portão</b> · encolhe e deixa
<b>geada</b> no chão (sublima: no Árido não tem água líquida)</figcaption></div>
<div class="chk" style="align-items:flex-end">
{chk_img("sprites/ice_gate_0.png", "ice_gate_0 · 4×2", 144, 132)}{chk_img("sprites/ice_gate_1.png", "ice_gate_1 · 3×2", 144, 132)}
{chk_img("sprites/ice_gate_2.png", "ice_gate_2 · 2×1", 144, 132)}</div></div>

<h3 style="margin-top:22px">Soltos com altura (não colidem, não mineram)</h3>
<div class="chk">{chk_img("sprites/decor_shards.png", "lascas de basalto", 28, 24, 4)}
{chk_img("sprites/decor_salt_crystals.png", "cristais de sal", 22, 16, 4)}
{chk_img("sprites/decor_ice_chunks.png", "pedaços de gelo", 26, 18, 4)}</div></section>

<section><h2>5 · Decoração que quebra a grade · sem × com</h2>
<p class="lede">“Sem” é o jeito de hoje: tile 32×32 repetido (4 variações), região por tile, borda reta. “Com” é a
proposta inteira: textura grande, borda deformada, decalques e entulho no pé dos morros.</p>
<div class="grid2" style="margin-top:12px">
{fig("decor_off.png", "<b>sem</b> · o tile repete e a bacia vira escada")}
{fig("decor_on.png", "<b>com</b> · manchas, rachaduras longas, placas, cascalho, sulcos")}
{fig("decor_border_off.png", "<b>sem</b> · a divisa do salar é a grade")}
{fig("decor_border_on.png", "<b>com</b> · a divisa vira costa")}
</div>
<h3 style="margin-top:22px">Os decalques (Árido, 1×)</h3>
<div class="grid2">
{fig("sprites/decals_plateau.png", "<b>planalto</b> · mancha escura, mancha clara, rachadura, placas, cascalho, sulcos")}
{fig("sprites/decals_salar.png", "<b>salar</b> · cristinhas, mancha úmida, rachadura, mancha clara")}
{fig("sprites/decals_basalt.png", "<b>basalto</b> · escória, óxido, rachadura, mancha, placas")}
{fig("sprites/decals_frost.png", "<b>faixa gelada</b> · lâmina de gelo, geada, cascalho, mancha clara")}
</div>
<div class="box" style="margin-top:12px"><p>Sorteio numa grade de <b>96 px presa no mundo</b> (≈ 3×3 tiles), 2
sorteios por célula (um grande e um miúdo). Chance por região: planalto 40%, salar 35%, basalto 45%, gelada
40%, leito 25%. A mesma célula dá sempre o mesmo decalque (seed do mundo), então não pisca nem muda entre
vistas. Não sorteia no raio de 6 tiles da base nem em cima das formações.</p></div></section>

<section><h2>6 · Morros mineráveis com borda orgânica</h2>
<div class="grid2">
{fig("hills_before.png", "<b>antes</b> · o desenho de hoje (wall_dead + face por tile): degrau de grade")}
{fig("hills_after.png", "<b>depois</b> · mesmos tiles, mesma colisão: borda curva, face em camadas, entulho no pé")}
</div>
<div class="box reco" style="margin-top:12px"><h3>Como funciona (grade dual)</h3><ul>
<li>A silhueta do topo sai de um campo <b>interpolado entre os centros dos tiles</b> (bilinear com smoothstep) mais
um ruído, cortado em 0,5. A <b>borda reta cai exatamente na borda do tile</b> (a colisão bate), a escada diagonal
vira diagonal, o canto convexo arredonda e o côncavo ganha um filete.</li>
<li>A <b>face é a silhueta extrudada 24 px pra baixo</b> (o mesmo topo elevado de 24 px de hoje): sai certa em
curva, canto e reentrância, sem peça especial. A face continua rocha: estratos tremidos, fissuras curtas e
inclinadas, escurecendo pro pé, <b>sem junta vertical regular</b>.</li>
<li>Minerar 1 tile só refaz a silhueta em volta dele (3×3 tiles).</li>
<li>Os minérios de hoje (<code>ore_*.png</code>) continuam por cima do topo, recortados pela silhueta.</li></ul></div></section>

<section><h2>7 · Relevo e água</h2>
<figure class="one"><img class="px" src="corte_relevo.png" alt=""><figcaption><b>corte do relevo</b> · o salar é a
bacia mais funda; as depressões pequenas do planalto só enchem de verdade no L3</figcaption></figure>
<div class="grid2" style="margin-top:14px">
<div>{cycle(["water_arid.png", "water_mist_l1.png", "water_mist_l2.png", "water_green_l3.png"],
            ["ÁRIDO · SECO", "NÉVOA · L1", "NÉVOA · L2", "VERDE · L3"])}<figcaption><b>a mesma bacia</b> enchendo
das partes mais fundas pra fora</figcaption></div>
<div class="box reco"><h3>Como a depressão aparece no seco</h3><ul>
<li><b>Leito seco</b>: dentro do nível máximo (L3) o chão vira silte claro com rachadura de lama (placas de ~36 px
com a borda enrolando). Dá pra ver de longe que “aqui já foi lago”.</li>
<li><b>Marca d'água seca</b>: as curvas de nível <b>L1, L2 e L3</b> desenhadas no chão (linha mineral clara de 2 px
com 1 px de sombra; L3 contínua, L1 e L2 tracejadas; no salar, anel escuro). A água vai chegar exatamente nelas.</li>
<li><b>Na Névoa</b> chove e a água sobe de L1 pra L2 com o índice de água; as marcas de cima continuam visíveis, a
margem fica 3 px úmida (terra escurecida), e tem raso, fundo e espuma na beira.</li>
<li><b>No Verde</b> chega no L3; a grama e as plantas preferem a beira.</li>
<li>Como as marcas mostram o futuro, o jogador já sabe onde <b>não</b> construir (máquina submersa para).</li></ul></div></div>
<div class="grid2" style="margin-top:14px">
{fig("water_salar_mist.png", "<b>salar na Névoa</b> (L2) · o lago começa no meio")}
{fig("water_salar_green.png", "<b>salar no Verde</b> (L3) · o grande lago, a crosta elevada vira ilhota")}
</div></section>

<section><h2>Pro Dev integrar</h2>
<div class="box dev"><h3>Camadas e ordem de desenho (superfície)</h3><ol style="color:var(--muted)">
<li><b>Chão</b>: textura grande da classe do pixel (planalto, salar, basalto, gelada ou leito), recortada pela
posição no mundo: <code>ground_{{região}}.png</code> 512×512, o tile (tx, ty) usa o retângulo
<code>((tx % 16)·32, (ty % 16)·32, 32, 32)</code>. A classe do pixel = região do tile em <code>(x + dx, y +
dy)</code> (deslocamento ±14 px, ruído preso no mundo). Leito = planalto com altura &lt; L3. 1 px de fenda
(índice 1) na divisa.</li>
<li><b>Marcas d'água</b> L1..L3 acima do nível atual (curva de nível da altura por pixel = bilinear das alturas dos
tiles com o mesmo deslocamento).</li>
<li><b>Decalques</b> (sorteio por célula de 96 px) e <b>entulho</b> no pé dos morros (45% dos tiles de pé).</li>
<li><b>Água</b> (altura &lt; nível): espuma 1 px, raso, médio, fundo; margem úmida de 3 px.</li>
<li><b>Cobertura</b>: umidade (Névoa) ou grama/musgo (Verde), com a borda deformada.</li>
<li><b>Morros + objetos por linha</b> (igual ao <code>build_draw_list</code>): topo da grade dual na linha do tile,
face na linha do topo de onde pende; formações, rochas, soltos, máquinas e player pelo pé.</li>
<li>Clima (poeira/chuva) e HUD por cima, como hoje.</li></ol></div>

<div class="grid2" style="margin-top:14px">
<div class="box dev"><h3>O que é sprite e o que é procedural</h3><ul>
<li><b>Sprite (PNG indexado)</b>: as 5 texturas de chão, topo e face do morro, 36 decalques, 5 formações, gelo-portão
×3, cratera ×5 + ejeção, geada, 9 soltos. Total <b>{n_pend} PNG</b> em
<code>assets/sprites/_pending/regions/</code>.</li>
<li><b>Procedural</b>: mapa de região e de altura (noise), deslocamento da borda, silhueta dos morros (grade
dual) e extrusão da face, curvas de nível, água, cobertura de grama/umidade, sorteio dos decalques.</li>
<li><b>Recolorir</b>: PNG modo P com a rampa do Árido embutida. Índices: 0..7 rampa, 8 contorno
<code>#1b1630</code>, 9 sombra (preto, alfa {R.SHADOW_A}), 255 transparente. As rampas dos 4 estágios estão
em <code>regions_palettes.json</code> (tabelas BASE, HILL, SAND e ICE). No load: trocar a paleta da Surface de 8
bits (ou <code>PixelArray.replace</code>, se o pygame converter pra 32 bits; não testei qual dos dois o
<code>pygame.image.load</code> devolve com o tRNS parcial da sombra).</li>
<li>A receita completa por pixel está em <code>tools/sprites/regions_scene.py</code> (classe <code>Scene</code>),
e as formações e pegadas em <code>tools/sprites/regions_formations.py</code>.</li></ul></div>
<div class="box dev"><h3>Desempenho (recomendação)</h3><ul>
<li>Assar o chão em <b>pedaços de 16×16 tiles (512×512 px)</b>: textura + borda + marcas + decalques + água +
cobertura, cacheados e refeitos só quando muda o estágio, o nível da água ou um tile minerado. No quadro é
1 blit por pedaço visível (~6), mais barato que os ~550 blits por tile de hoje.</li>
<li><b>numpy liberado</b>: assar com numpy + <code>pygame.surfarray</code>, que é literalmente o
<code>regions_scene.py</code> portado.</li>
<li>As formações e a cratera <b>não</b> rodam no jogo: são sprites prontos (o volume 3D é só a ferramenta da
Designer).</li>
<li>Não medi no jogo; os tempos acima são estimativa.</li></ul></div></div>

<div class="box dev" style="margin-top:14px"><h3>Formações: âncora e colisão</h3>
<table><tr><th>sprite</th><th>tamanho</th><th>âncora (px no sprite)</th><th>tiles que bloqueiam (dx, dy) relativos ao
tile do pé</th></tr>
{''.join(f"<tr><td><code>{v['sprite']}</code></td><td>{files[v['sprite']]['size']}</td><td>{tuple(v.get('foot') or v['anchor'])}{' (centro dos 3×3)' if 'anchor' in v else ''}</td><td>{', '.join(str(tuple(t)) for t in v['tiles']) or 'nenhum'}</td></tr>" for k, v in forms.items())}
</table><p style="color:var(--muted)">A âncora cai no meio da borda de baixo do tile do pé (y = tile·32 + 30). <b>Cratera</b>:
a âncora é o <b>centro dos 3×3</b> (px (cx·32 + 48, cy·32 + 48)), desenhada pelo pé (borda de baixo dos 3×3), com o
<code>crater_ejecta.png</code> (256×216) centrado no mesmo ponto na camada de decalques; paleta com 21 índices
(0..9 planalto, 10..17 gelo, 18..20 metal da rampa); o E continua no tile do meio de baixo.
Arco: só as pernas bloqueiam; o vão é andável e a ordem por y basta (quem está atrás fica por trás do arco). O
gelo-portão troca de sprite e de pegada a cada etapa. Afloramentos: 4 rochas pequenas por formação (raio 2,5 a 5
tiles), com o minério da região (planalto ferro/silício, basalto ferro, salar silício, gelada gelo); as rochas
de hoje recoloridas pela rocha da região.</p></div>

<div class="box dev" style="margin-top:14px"><h3>Números de partida (ajustáveis)</h3><ul>
<li>Níveis d'água (altura 0..1): <b>L1 {R.LEVELS[0]}</b> (começo da Névoa), <b>L2 {R.LEVELS[1]}</b>, <b>L3
{R.LEVELS[2]}</b> (Verde cheio). Salar: elipse de 31×25 tiles a leste; depressões do planalto de 6 a 8,5 tiles.</li>
<li>Faixa gelada: y &lt; ~24 (com ruído). Basalto: x &lt; ~44 (com ruído) e y &gt; ~44.</li>
<li>Decalques: célula de {R.DECAL_CELL} px, chances acima, mistura por região no JSON. Soltos com altura: 3,5% dos tiles
livres da região.</li>
<li>Morros: ruído de 0,42 na grade dual (±4 px de tremido nas bordas retas). Nenhum morro no salar nem abaixo do L3.</li></ul></div>

<details style="margin-top:14px"><summary style="cursor:pointer;color:var(--gold)">Lista dos {n_pend} PNG pendentes</summary>
<table style="margin-top:8px"><tr><th>arquivo</th><th>tamanho</th><th>rampa</th><th>região</th></tr>{pend_rows}</table>
</details></section>

<section><h2>Desvios do contrato</h2><div class="box"><ul>
<li><b>Nenhum arquivo do contrato atual foi tocado.</b> Tudo novo está em <code>_pending/regions/</code>.</li>
<li>Se aprovado, o contrato do §6 ganha: <code>ground_*</code>, <code>hill_top</code>/<code>hill_face</code>,
<code>decal_*</code>, <code>form_*</code>, <code>ice_gate_*</code>, <code>crater_impact_0..4</code> +
<code>crater_ejecta</code>, <code>frost_ring</code>,
<code>decor_*</code> (PNG indexado, o que é novo no projeto). Saem de uso na superfície: <code>sand_*</code> e os
<code>wall_*</code>/<code>wall_face_*</code> dos morros (a caverna continua com os de hoje).</li>
<li><b>Desvio proposto (cratera)</b>: o contrato tem <code>crater.png</code> e <code>crater_ramp.png</code> em
96×96. A cratera de impacto precisa de mais espaço pra borda e a ejeção: <code>crater_impact_0..4.png</code> em
168×150, sempre bloqueando os mesmos 3×3. Se aprovado, ela substitui as duas, porque a rampa já vem no sprite e
aparece quando o gelo some.</li></ul></div></section>
</div></body></html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    return OUT / "index.html"
