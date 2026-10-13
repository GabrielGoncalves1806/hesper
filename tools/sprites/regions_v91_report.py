"""Seção v9.1 do report das regiões (fumarolas ativas, PROPOSTA). Chamado pelo tools/sprites/regions_v91.py.

Escreve reports/design/regioes/v91/section.html e v91/note.html; o regions_v9_report.inject() põe os dois no index,
acima da v9.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import regions_core as R
import regions_vents as VT

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "reports" / "design" / "regioes"
OUT = REG / "v91"

CSS_V91 = """
.v91{border:1px solid var(--rust);padding:22px 22px 30px;margin-top:40px;background:rgba(226,115,58,.04)}
.v91 > h2::before{background:var(--rust)}
.smk{image-rendering:pixelated;background-repeat:no-repeat;border:1px solid var(--line)}
"""


def _size(p):
    with Image.open(p) as im:
        return im.size


def chk(src, k, cap):
    w, h = _size(REG / src)
    return f'<figure><img src="{src}" width="{w * k}" height="{h * k}" alt=""><figcaption>{cap}</figcaption></figure>'


def smoke_anim(kind, fw, fh, n, k=3, fps=8):
    """Folha de quadros animada em CSS (background-position em degraus)."""
    name = f"smk_{kind}"
    dur = n / fps
    return (f'<style>.{name}{{width:{fw * k}px;height:{fh * k}px;background-image:url(v91/smoke_{kind}.png);'
            f'background-size:{fw * n * k}px {fh * k}px;animation:{name} {dur:.2f}s steps({n}) infinite}}'
            f'@keyframes {name}{{from{{background-position:0 0}}to{{background-position:-{fw * n * k}px 0}}}}</style>'
            f'<div class="smk {name}"></div>')


def build(files, forms, strips):
    S = VT.SMOKE
    rows = []
    for kind in ("cone", "pair", "chimney"):
        info = forms[f"vent_{kind}"]
        size = files[f"form_vent_{kind}_dormant.png"]["size"]
        nt = len(info["tiles"])
        fw, fh, n = strips[kind]
        sw, sh = _size(OUT / "cat" / f"strip_vent_{kind}.png")
        rows.append(f"""<tr><td><b>{info['name']}</b><br><code>form_vent_{kind}_{{dormant,active}}.png</code><br>{size} ·
rampa HILL+VENT<br>âncora {tuple(info['foot'])} = centro de baixo da pegada<br>bloqueia {'1 tile' if nt == 1 else '2×1'}<br>
boca{'s' if len(info['mouths']) > 1 else ''} (fumaça): {', '.join(str(tuple(m)) for m in info['mouths'])}<br>
{S['rate'][kind]} puffs/s por boca</td>
<td><div class="chk" style="padding:8px">{chk(f"v91/cat/vent_{kind}_dormant.png", 3, "dormente")}
{chk(f"v91/cat/vent_{kind}_active.png", 3, "ativa")}</div></td>
<td><div class="chk" style="padding:8px">{chk(f"v91/cat/foot_vent_{kind}.png", 1, "pegada · âncora (ponto) · boca (quadrado)")}</div></td>
<td>{smoke_anim(kind, fw, fh, n)}<figcaption>ativa com a fumaça (3×, 8 qps, laço de 4 s)</figcaption></td></tr>
<tr><td colspan="4"><img class="strip" src="v91/cat/strip_vent_{kind}.png" width="{sw * 2}" height="{sh * 2}" alt="">
<figcaption>dormente e ativa nos 4 estágios (Tempestade · Árido · Névoa · Verde), 2×</figcaption></td></tr>""")
    vent_sw = "".join(f'<i style="background:{c}" title="{c}"></i>' for c in VT.VENT)
    stage_sw = "".join(f'<tr><td>{R.STAGE_NAME[st]}</td><td><div class="sws">'
                       + "".join(f'<i style="background:{R.hexc(c)}" title="{R.hexc(c)}"></i>'
                                 for c in VT.vent_ramp(st)[10:14]) + "</div></td></tr>" for st in R.STAGES)
    lw, lh = _size(OUT / "smoke_puff_life.png")
    gw, gh = _size(OUT / "vents_dormant_crop.png")
    import regions_v91 as V
    D = V.DENSITY
    sec = f"""<!-- v91:begin -->
<section class="v91" id="v91"><h2>v9.1 · Fumarolas ativas que acordam com o calor (PROPOSTA)</h2>
<p class="lede">Ideia do dono: conforme o índice de calor sobe no Marco 3 (o mesmo que derrete a cratera), as
fumarolas do basalto acordam e soltam fumaça. Do esboço (<code>reports/design/refs/fumarolas_esboco_dono.png</code>)
aproveitei só as 3 formas: cone baixo e largo com boca, par de cones e chaminé alta e fina com veios escorrendo, todas
com a boca aberta no topo. O desenho é original, feito no mesmo motor de volume do cone de escória e do basalto
colunar, com a rampa <code>HILL</code> do basalto. Nada disso está em <code>assets/</code>: os PNGs indexados ficam em
<code>reports/design/regioes/v91/pendentes/</code>, com o <code>regions_v91.json</code>. O decalque <code>fumarole</code> da v9
continua sendo o respiro apagado de chão.</p>

<h3 style="margin-top:22px">As 3 fumarolas · dormente × ativa</h3>
<p class="lede"><b>Dormente</b>: boca escura e fria, veios de óxido. <b>Ativa</b>: brilho de brasa leve no fundo da boca,
crosta de enxofre em manchas na borda e veios amarelados escorrendo. O resto do sprite é igual, então a troca não
pula.</p>
<table style="margin-top:10px"><tr><th>fumarola</th><th>sprite (3×)</th><th>pegada</th><th>fumaça</th></tr>
{''.join(rows)}</table>

<h3 style="margin-top:26px">Paleta · rampa nova <code>VENT</code> (índices 10..13)</h3>
<div class="grid2"><div class="box"><div class="sws">{vent_sw}</div><ul>
<li><b>10, 11 · enxofre</b> (escuro, claro): é mineral, então segue o estágio como o resto (a mesma conta do
<code>stage_color</code> do basalto). Na Tempestade fica empoeirado; na Névoa, apagado; no Verde, mais oliva.</li>
<li><b>12, 13 · brasa</b> (escura, clara): emite luz, então é <b>fixa</b> nos 4 estágios, como as cores de LED das
máquinas. É pequena (só o fundo da boca) pra ficar “leve”.</li>
<li>0..9 é a rampa <code>HILL</code> do basalto, igual às formações: o dormente nem usa a <code>VENT</code>.</li></ul></div>
<table><tr><th>estágio</th><th>10 · 11 · 12 · 13</th></tr>{stage_sw}</table></div>

<h3 style="margin-top:26px">Fumaça (partícula do jogo, não sprite)</h3>
<div class="grid2"><div><div class="chk" style="padding:10px">{chk("v91/smoke_puff_life.png", 3, "a vida de 1 puff em 8 passos (sem vento)")}</div></div>
<div class="box dev"><ul>
<li><b>Taxa</b>: {S['rate']['cone']} puffs/s por boca no cone, {S['rate']['pair']} em cada boca do par,
{S['rate']['chimney']} na chaminé. Nasce na <code>mouths</code> do JSON (px do sprite) ± 1 px.</li>
<li><b>Vida</b>: {S['life'][0]}–{S['life'][1]} s. <b>Subida</b>: {S['rise'][0]:.0f}–{S['rise'][1]:.0f} px/s na saída,
freando até ~35% no fim.</li>
<li><b>Tamanho</b>: raio {S['radius'][0]}–{S['radius'][1]} px ao nascer, abre até {S['radius'][2]:.0f}–{S['radius'][3]:.0f} px
(rápido no começo, devagar no fim). Disco levemente achatado (y × 1,1).</li>
<li><b>Vento</b>: o puff anda com {int(S['wind'] * 100)}% do vento da superfície (o mesmo da poeira), mais uma tremida lateral de
± {S['jitter']:.0f} px num seno lento. Na Tempestade a coluna deita.</li>
<li><b>Cor</b>: 3 tons chapados, sem gradiente: miolo <code>{S['color'][0]}</code> (de cima-esquerda, onde bate a
luz), corpo <code>{S['color'][1]}</code>, borda de baixo <code>{S['color'][2]}</code>. Na Tempestade e na Névoa os tons
puxam 40% pra <code>{S['stage_tint']['storm']}</code> e <code>{S['stage_tint']['mist']}</code>.</li>
<li><b>Alfa em degraus</b> (pixel art, nada de fade contínuo): {S['alpha'][0]} até 35% da vida, {S['alpha'][1]} até
70%, {S['alpha'][2]} no fim. O puff novo vai por cima do velho.</li>
<li>Desenhada depois dos objetos (por cima da fumarola e do player), antes da HUD. No máximo ~12 puffs vivos por
boca.</li></ul></div></div>

<h3 style="margin-top:26px">Na cena do basalto · dormente × ativa</h3>
<p class="lede">Mesma vista do basalto da v9 aprovada, com um campo de 3 fumarolas perto do cone de escória.</p>
<div class="grid2" style="margin-top:12px">
<figure><img src="v91/vents_dormant_crop.png" width="{gw * 2}" height="{gh * 2}" style="image-rendering:pixelated;max-width:100%;height:auto" alt="">
<figcaption><b>dormente</b> (2×)</figcaption></figure>
<figure><img src="v91/vents_active.gif" width="{gw * 2}" height="{gh * 2}" style="image-rendering:pixelated;max-width:100%;height:auto" alt="">
<figcaption><b>ativa</b> (GIF, 8 qps, 4 s em laço, vento do Árido) · <code>v91/vents_active.gif</code></figcaption></figure>
</div>
<div class="grid2" style="margin-top:12px">
<figure><img class="px" src="v91/scene_arid_dormant.png" alt=""><figcaption><b>Árido · dormente</b> · a cena inteira</figcaption></figure>
<figure><img class="px" src="v91/scene_arid_active.png" alt=""><figcaption><b>Árido · ativa</b></figcaption></figure>
<figure><img class="px" src="v91/scene_storm_active.png" alt=""><figcaption><b>Tempestade · ativa</b> · a coluna deita com o vento</figcaption></figure>
<figure><img class="px" src="v91/scene_mist_active.png" alt=""><figcaption><b>Névoa · ativa</b></figcaption></figure>
<figure><img class="px" src="v91/scene_green_dormant.png" alt=""><figcaption><b>Verde · dormente</b></figcaption></figure>
<figure><img class="px" src="v91/scene_green_active.png" alt=""><figcaption><b>Verde · ativa</b></figcaption></figure>
</div>
<figure class="one" style="margin-top:12px"><img class="px" src="v91/vents_active_panel.png" alt="">
<figcaption>painel de 4 quadros (0, 1, 2 e 3 s) da ativa</figcaption></figure>

<h3 style="margin-top:26px">Onde nascem, quantas e quando acordam</h3>
<div class="box"><ul>
<li><b>Quantas</b>: {D['per_world']}.</li>
<li><b>Onde</b>: {D['rule']}</li>
<li><b>Quando acordam</b>: {D['wake']}</li>
<li><b>Colisão e desenho</b>: igual às formações (tile <code>FORMATION</code> na pegada, âncora no centro de baixo da
pegada, ordem pelo pé, não minera, sombra no sprite). O sprite troca de <code>_dormant</code> pra <code>_active</code>
pelo estado; a paleta é <code>HILL</code> do basalto (0..9) + <code>VENT</code> do estágio (10..13), no estágio do tile do pé.</li>
<li><b>Mapa</b>: entram como “Formação” (pictograma de pico) só se o dono quiser; por padrão não marcam.</li></ul></div>

<h3 style="margin-top:26px">Se o dono aprovar · contrato (bíblia §6)</h3>
<div class="box"><ul>
<li>Linha nova: <code>form_vent_{{cone,pair,chimney}}_{{dormant,active}}.png</code> · 60×48, 72×64 e 40×78 · fumarolas do
basalto, bloqueiam 1, 2×1 e 1 tile · paleta 0..9 <code>HILL</code> do basalto + 10..13 <code>VENT</code> · <code>mouths</code> no JSON.</li>
<li>Rampa nova <code>VENT</code> no <code>regions_palettes.json</code> (por estágio, 4 cores) e o bloco <code>smoke</code> com os
números da partícula.</li></ul></div>
</section>
<!-- v91:end -->"""
    note = """<!-- v91note:begin -->
<div class="v2"><b>v9.1 · o que mudou (PROPOSTA, pendente)</b><ul>
<li><b>Fumarolas ativas</b> no basalto: cone baixo, par de cones e chaminé, cada uma dormente × ativa (brasa leve e
crosta de enxofre), a rampa nova <code>VENT</code>, a fumaça como partícula (com os números), a cena dormente × ativa
com GIF e a regra de onde nascem e de quando acordam com o calor. <a href="#v91">Seção v9.1</a>.</li>
<li>A v9 foi <b>aprovada</b> e promovida pra <code>assets/sprites/regions/</code> (os 70 PNGs, o basalto novo e os
dados no <code>regions_palettes.json</code>).</li></ul></div>
<!-- v91note:end -->"""
    (OUT / "section.html").write_text(sec, encoding="utf-8")
    (OUT / "note.html").write_text(note, encoding="utf-8")
    import regions_v9_report
    page = REG / "index.html"
    page.write_text(regions_v9_report.inject(page.read_text(encoding="utf-8")), encoding="utf-8")
    return page
