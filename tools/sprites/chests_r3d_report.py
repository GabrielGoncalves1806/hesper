"""Report do baú r3d (reports/design/bau_r3d/index.html): antes × depois, animação em CSS, cenas e pro Dev.
Chamado pelo tools/sprites/chests_r3d.py depois de exportar os pendentes."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import chests_r3d as C  # noqa: E402
import regions_core as R  # noqa: E402

OUT = C.OUT
SPR = C.SPR
T = 32


def load(p):
    return Image.open(p).convert("RGBA")


def ground(region, stage, w, h, seed):
    import regions_v9 as V9
    return V9.ground_patch(region, stage, w, h, seed)


def put(objs, img, fx, fy, corner=False):
    """Objeto pelo pé (centro da base) ou pelo canto (caixa de saque: blit no canto do tile)."""
    if corner:
        objs.append((fy + img.height, img, fx, fy))
    else:
        objs.append((fy, img, fx - img.width // 2, fy - img.height))


def compose(bg, objs):
    for _, img, x, y in sorted(objs, key=lambda o: o[0]):
        bg.alpha_composite(img, (x, y))
    return bg


def base_scene(stage, new=True):
    """Recorte 480×270 da base: módulo, máquinas, Explorador e dois baús (um aberto)."""
    bg = ground("plateau", stage, 480, 270, 21)
    src = C.PEND if new else C.BEFORE
    chest = load(src / "chest.png")
    chest_o = load(src / "chest_open.png")
    o = []
    put(o, load(SPR / "pod.png"), 120, 120)
    put(o, load(SPR / "machine_o2.png"), 200, 112)
    put(o, load(SPR / "machine_heater.png"), 244, 112)
    put(o, load(SPR / "machine_melter_t2.png"), 288, 112)
    put(o, load(SPR / "solar_panel.png"), 352, 112)
    put(o, load(SPR / "lamp.png"), 168, 176)
    put(o, load(SPR / "drone_station.png"), 400, 208)
    for i, x in enumerate((208, 240, 272, 304)):
        put(o, chest_o if i == 1 else chest, x, 192)
    put(o, load(SPR / "player_idle_down.png").crop((0, 0, 32, 32)), 240, 236)
    return compose(bg, o)


def pocket_scene(stage):
    """Recorte 480×270 do bolsão: o contêiner lacrado, o destroço rico com a caixa de saque (cheia e vazia) e o
    gelo-portão (v9.2) já quase derretido no corredor."""
    import regions_ice_blocks as B
    bg = ground("frost", stage, 480, 270, 33)
    o = []
    put(o, load(C.PEND / "container_sealed.png"), 240, 140)
    put(o, load(C.PEND / "loot_crate.png"), 128, 160, corner=True)
    put(o, load(C.PEND / "loot_crate_empty.png"), 352, 160, corner=True)
    ramp = R.ramp("frost", stage, {"frost": R.ICE})
    for kind, v, k, x, y in (("slab", 1, 5, 200, 262), ("boulder", 0, 6, 270, 258), ("shard", 0, 4, 320, 264)):
        w, h, ox, oy, _ = B.frame_box(kind, v)
        img = R.colorize(B.render(kind, v, B.SCALES[k]), ramp)
        o.append((y, img, x - ox, y - oy))
    put(o, load(SPR / "player_idle_side.png").crop((0, 0, 32, 32)), 196, 168)
    return compose(bg, o)


def scenes():
    base_scene("arid").save(OUT / "cena_base_arid.png")
    base_scene("arid", new=False).save(OUT / "cena_base_arid_antes.png")
    base_scene("green").save(OUT / "cena_base_green.png")
    pocket_scene("arid").save(OUT / "cena_bolsao_arid.png")
    pocket_scene("green").save(OUT / "cena_bolsao_green.png")


def palette_strip():
    sw = 22
    rows = [("BLUE (corpo)", C.BLUE), ("BLUE_D (painel)", C.BLUE_D),
            ("acento", [C.ORANGE_L, C.ORANGE, C.ORANGE_D, C.OUTLINE]),
            ("lacre", [C.GOLD_L, C.GOLD, C.GOLD_D, C.ALERT])]
    im = Image.new("RGBA", (sw * 5, sw * len(rows)), (0, 0, 0, 0))
    for j, (_, cols) in enumerate(rows):
        for i, c in enumerate(cols):
            im.paste(Image.new("RGBA", (sw - 2, sw - 2), R.rgb(c) + (255,)), (i * sw, j * sw))
    im.save(OUT / "paleta_azul.png")
    return rows


def size(p):
    with Image.open(p) as im:
        return im.size


def fig(src, k, cap):
    w, h = size(OUT / src)
    return f'<figure><div class="chk"><img src="{src}" width="{w * k}" height="{h * k}" alt=""></div><figcaption>{cap}</figcaption></figure>'


PAIRS = [
    ("chest", "Baú fechado", "32×40"),
    ("chest_open", "Baú aberto", "32×40"),
    ("icon_chest", "Ícone do baú", "16×16"),
    ("loot_crate", "Caixa de saque cheia", "32×32"),
    ("loot_crate_empty", "Caixa de saque vazia", "32×32"),
]


def build():
    scenes()
    rows = palette_strip()
    pairs = []
    for name, label, sz in PAIRS:
        k = 6 if sz != "16×16" else 8
        pairs.append(f"""<div class="pair"><h3>{label} · <code>{name}.png</code> · {sz}</h3><div class="ab">
{fig(f"before/{name}.png", k, "antes (hoje no jogo)")}{fig(f"pendentes/{name}.png", k, "depois (r3d azul)")}</div></div>""")
    pairs.append(f"""<div class="pair"><h3>Contêiner lacrado · <code>container_sealed.png</code> · 40×44 (proposta)</h3><div class="ab">
{fig("before/container_sealed_placeholder.png", 6, "antes: o placeholder do código (art.sealed_container, 32×40)")}
{fig("pendentes/container_sealed.png", 6, "depois (r3d azul, maior, trava + selo)")}</div></div>""")
    pal = "".join(f'<li><b>{n}</b>: {" ".join(f"<code>{c}</code>" for c in cols)}</li>' for n, cols in rows)
    fam = "".join(f'<img src="pendentes/{n}.png" width="{size(C.PEND / f"{n}.png")[0] * 5}" height="{size(C.PEND / f"{n}.png")[1] * 5}" alt="">'
                  for n in ("loot_crate", "chest", "container_sealed"))
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Baú r3d azul · v1.0</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;--blue:#4a86d0;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1300px;margin:0 auto;padding:44px 0 80px}}
.eyebrow{{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--blue);text-transform:uppercase}}
h1{{font:600 44px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}}h2{{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--blue);margin-right:10px;vertical-align:middle}}
h3{{font:600 16px "Pixelify Sans",monospace;margin:0 0 8px}}code{{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}}
p,li{{color:var(--muted)}}li b,p b{{color:var(--fg)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--blue);padding:12px 18px;max-width:1000px}}
.v2>b{{font:13px "Silkscreen",monospace;color:var(--blue)}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px}}
.pairs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:18px}}
.pair{{background:var(--panel);border:1px solid var(--line);padding:14px}}.ab{{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}@media(max-width:1000px){{.grid2{{grid-template-columns:1fr}}}}
img.px{{width:100%;height:auto;border:1px solid var(--line);display:block}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}}
.anim{{display:flex;gap:28px;flex-wrap:wrap;align-items:flex-end}}
.sp{{background-repeat:no-repeat;background-size:100% 100%;image-rendering:pixelated}}
.a-chest{{width:192px;height:240px;animation:chestA 2.4s steps(1) infinite}}
@keyframes chestA{{0%{{background-image:url(pendentes/chest.png)}}50%{{background-image:url(pendentes/chest_open.png)}}}}
.a-crate{{width:192px;height:192px;animation:crateA 2.4s steps(1) infinite}}
@keyframes crateA{{0%{{background-image:url(pendentes/loot_crate.png)}}50%{{background-image:url(pendentes/loot_crate_empty.png)}}}}
.a-led{{width:240px;height:264px;animation:ledA 1.2s steps(1) infinite;background-image:url(pendentes/container_sealed.png)}}
@keyframes ledA{{0%{{filter:none}}50%{{filter:brightness(.92)}}}}
</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v1.0 · proposta: família de caixas no r3d, padrão azul</div>
<h1>Baú, caixa de saque e contêiner lacrado · r3d azul</h1>
<div class="v2"><b>v1.0 · o que mudou (proposta, espera o ok do dono)</b><ul>
<li><b>Um modelo só</b> pra toda caixa do jogo, no motor r3d das máquinas experimentais: base de metal, corpo azul com
o painel rebaixado na frente, um friso laranja de acento, tampa com a emenda escura e o trinco de aço com LED. É a
forma do <code>chest()</code> do experimento, recolorida pro padrão azul, sem detalhe industrial a mais (sem rebite e
sem faixa de advertência), como o dono pediu.</li>
<li><b>Baú</b> (<code>chest</code>, <code>chest_open</code>, <code>icon_chest</code>) substitui o armário de hoje.
<b>Caixa de saque</b> (<code>loot_crate</code>, <code>loot_crate_empty</code>) é o mesmo modelo menor. <b>Contêiner
lacrado</b> (<code>container_sealed</code>, novo) é o mesmo modelo maior, com duas travas, a placa do selo da colônia
em dourado e o LED vermelho.</li>
<li>Cheia × vazia/aberta muda <b>só a tampa e o conteúdo</b>, nunca a cor. LED: verde no baú, âmbar na caixa de saque
cheia (como hoje), vermelho no lacrado.</li>
<li>O motor <code>r3d.py</code> foi portado pro <code>tools/sprites/</code>, autocontido; ele reproduz pixel a pixel o
baú do experimento.</li>
</ul></div>

<h2>A família</h2>
<div class="chk" style="display:flex;gap:30px;align-items:flex-end;padding:18px">{fam}</div>
<p>Caixa de saque (32×32) · baú (32×40) · contêiner lacrado (40×44). Ampliado 5×.</p>

<h2>Antes × depois</h2>
<div class="pairs">{''.join(pairs)}</div>

<h2>Animações</h2>
<div class="anim">
<figure><div class="chk"><div class="sp a-chest"></div></div><figcaption>baú: fecha / abre (E)</figcaption></figure>
<figure><div class="chk"><div class="sp a-crate"></div></div><figcaption>caixa de saque: cheia / vazia</figcaption></figure>
<figure><div class="chk"><img src="pendentes/container_sealed.png" width="240" height="264" alt=""></div><figcaption>contêiner lacrado: não abre</figcaption></figure>
</div>

<h2>Na base, com as máquinas e o Explorador</h2>
<div class="grid2">
<figure><img class="px" src="cena_base_arid_antes.png" alt=""><figcaption><b>antes</b> · Árido, o baú de hoje (armário)</figcaption></figure>
<figure><img class="px" src="cena_base_arid.png" alt=""><figcaption><b>depois</b> · Árido, 4 baús (o 2º aberto)</figcaption></figure>
<figure><img class="px" src="cena_base_green.png" alt=""><figcaption><b>depois</b> · Verde</figcaption></figure>
<figure><img class="px" src="cena_bolsao_arid.png" alt=""><figcaption><b>bolsão</b> · Árido: contêiner lacrado, caixa de saque cheia (esq.) e vazia (dir.), o gelo-portão da v9.2 derretendo embaixo</figcaption></figure>
<figure><img class="px" src="cena_bolsao_green.png" alt=""><figcaption><b>bolsão</b> · Verde</figcaption></figure>
</div>
<p>Recortes 480×270 (metade da tela do jogo) ampliados 2×, montados só com os sprites e ordenados pelo pé, como o jogo
desenha. O chão é o da v9 (planalto e faixa gelada).</p>

<h2>Nota sobre a paleta azul</h2>
<div class="grid2"><div class="chk"><img src="paleta_azul.png" width="{size(OUT / 'paleta_azul.png')[0] * 3}" height="{size(OUT / 'paleta_azul.png')[1] * 3}" alt=""></div>
<ul>{pal}
<li>O r3d acende o <b>tampo</b> com o tom 0, a <b>frente</b> com o 1 e a <b>lateral</b> com o 3. Por isso a rampa foi
deslocada: o azul "de verdade" (<code>#4a86d0</code>) é a frente, o tampo fica azul claro (<code>#8ec4f4</code>) e não
estoura pro branco.</li>
<li>É um azul de contêiner, mais fundo e menos verde que o ciano do O₂ (<code>#59d0e6</code>) e o gelo, pra não
confundir com a UI nem com o minério. Destaca bem no ocre do Árido e no verde do Verde; na faixa gelada lê como objeto
feito pelo homem, no meio do gelo, pelo contorno e pela base de metal.</li>
<li>Referência de estilo do The Planet Crafter: só a ideia do contêiner de armazenamento simples, de cor chapada, com
tampa e um trinco. Nada foi copiado: a forma é a do <code>chest()</code> do nosso experimento.</li>
</ul></div>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Baú</b>: <code>chest.png</code> e <code>chest_open.png</code> continuam <b>32×40</b>, ancorados no centro da base
(o <code>_blit_anchored</code> de hoje, pé na borda de baixo do tile). Nada muda no código além de trocar o PNG.
<code>icon_chest.png</code> continua 16×16.</li>
<li><b>Caixa de saque</b>: <code>loot_crate.png</code> / <code>loot_crate_empty.png</code> continuam <b>32×32</b>, blit no
canto do tile (<code>draw_crate</code>), a base da caixa na última linha do sprite.</li>
<li><b>Contêiner lacrado</b>: <code>container_sealed.png</code> <b>40×44</b> (o placeholder é 32×40). O render já mede o
sprite (<code>tx·32 + 16 − w/2</code>, <code>(ty + 1)·32 − h</code>), então ele passa 4 px de cada lado do tile, como as
máquinas de 40 px. Continua bloqueando 1 tile.</li>
<li><b>Sem sombra no sprite</b> (como as máquinas r3d do experimento): se quiser, o jogo põe a sombra de chão de sempre.</li>
<li><b>Contorno do alvo do E</b>: o <code>outline_of</code> funciona igual (silhueta opaca).</li>
<li>Regerar: <code>python3 tools/sprites/chests_r3d.py</code> (determinístico; os PNGs saem em
<code>reports/design/bau_r3d/pendentes/</code>). Na promoção, copia pro <code>assets/sprites/</code>.</li>
</ul></div>
</div></body></html>
"""
    page = OUT / "index.html"
    page.write_text(html, encoding="utf-8")
    return page
