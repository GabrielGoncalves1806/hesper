"""Report da Bancada T2 e dos ícones dos itens do v0.5 (reports/design/v05_bancada_itens/index.html).
Chamado pelo tools/sprites/v05_bancada_itens.py depois de exportar os pendentes. Só lê assets/ (nunca escreve lá)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import v05_bancada_itens as G  # noqa: E402

ROOT = G.ROOT
OUT = G.REP
PEND = G.PEND
SPR = ROOT / "assets" / "sprites"
ATUAL = OUT / "atual"
CONCEPT_SRC = Path("/private/tmp/claude-501/-Users-gabrieloliveira-personal-projects-hesper/"
                   "a41d67f8-eba1-421d-81dc-da6cace40cf3/images/44.png")
CONCEPT = OUT / "ref_conceito_montadora.png"
INGOT_REF_SRC = CONCEPT_SRC.with_name("45.png")
INGOT_REF = OUT / "ref_lingote_aco.png"
V1 = OUT / "v1"

ICONS = [
    ("icon_iron_ingot", "Lingote de ferro", "barra em tronco de pirâmide na cor do ferro do jogo"),
    ("icon_water_capsule", "Cápsula de água", "cilindro de vidro com tampas de metal, água azul até 2/3"),
    ("icon_silicon_wafer", "Wafer de silício", "disco espelhado com grade de dies, chanfro reto e reflexo iridescente"),
    ("icon_circuit", "Circuito elétrico", "placa verde deitada, trilhas, CI, resistor e os dentes dourados"),
    ("icon_chip", "Chip de computador", "CPU quadrada escura, pernas douradas nos 4 lados, tampa prateada"),
    ("icon_wire", "Fios", "carretel com voltas de fio de cobre e a ponta solta"),
    ("icon_diagram", "Diagrama", "cartão de planta azul deitado, desenho técnico, clipe laranja"),
]


def load(p):
    return Image.open(p).convert("RGBA")


def put(objs, img, fx, fy):
    """Objeto pelo pé (centro da base), como o jogo."""
    objs.append((fy, img, fx - img.width // 2, fy - img.height))


def compose(bg, objs):
    for _, img, x, y in sorted(objs, key=lambda o: o[0]):
        bg.alpha_composite(img, (x, y))
    return bg


def ground(region, stage, w, h, seed):
    import regions_v9 as V9
    return V9.ground_patch(region, stage, w, h, seed)


def frame(i):
    fw, fh = G.W, G.H
    return load(PEND / "anim" / "anim_machine_workbench.png").crop((i * fw, 0, i * fw + fw, fh))


def base_scene(stage, f):
    """Recorte 480×270 da base: a cápsula (fabricador, T1) com a Bancada T2 do lado, máquinas e o Explorador.
    Tiles de 32 px: o pé de cada máquina é a borda de baixo do tile (y múltiplo de 32), x no centro do tile."""
    bg = ground("plateau", stage, 480, 270, 21)
    o = []
    put(o, load(SPR / "pod.png"), 144, 128)
    put(o, frame(f), 208, 128)
    put(o, load(SPR / "machine_o2.png"), 272, 128)
    put(o, load(SPR / "machine_heater_t2.png"), 304, 128)
    put(o, load(SPR / "machine_melter.png"), 336, 128)
    put(o, load(SPR / "solar_panel.png"), 400, 128)
    put(o, load(SPR / "chest.png"), 176, 192)
    put(o, load(SPR / "lamp.png"), 240, 192)
    put(o, load(SPR / "player_idle_down.png").crop((0, 0, 32, 32)), 208, 172)
    return compose(bg, o)


def outpost_scene(stage, region, f):
    """Posto avançado: a bancada sozinha longe da base, com um baú, uma luminária e o Explorador."""
    bg = ground(region, stage, 480, 270, 47)
    o = []
    put(o, frame(f), 240, 144)
    put(o, load(SPR / "chest.png"), 304, 144)
    put(o, load(SPR / "lamp_t2.png"), 176, 144)
    put(o, load(SPR / "player_idle_side.png").crop((0, 0, 32, 32)), 208, 186)
    put(o, load(SPR / "solar_panel.png"), 336, 208)
    return compose(bg, o)


def hotbar(bg_col, light=False):
    """Hotbar de mentira no estilo B (cartões escuros, canto cortado), com os ícones novos em 1:1 e o vizinho
    aprovado no fim. Devolve a imagem 1:1."""
    names = [n for n, _, _ in ICONS] + ["icon_workbench", "icon_iron", "icon_silicon", "icon_blueprint"]
    pad, sz = 4, 20
    W = pad + len(names) * (sz + 2) + pad
    im = Image.new("RGBA", (W, sz + 2 * pad), bg_col)
    card = "#1e1a24" if not light else "#2a2531"
    edge = "#3a3549" if not light else "#4a4458"
    for i, n in enumerate(names):
        x, y = pad + i * (sz + 2), pad
        slot = Image.new("RGBA", (sz, sz), card)
        for k in range(sz):
            slot.putpixel((k, 0), Image.new("RGBA", (1, 1), edge).getpixel((0, 0)))
        for c in ((0, 0), (sz - 1, 0), (0, sz - 1), (sz - 1, sz - 1)):
            slot.putpixel(c, (0, 0, 0, 0))
        im.alpha_composite(slot, (x, y))
        src = PEND / f"{n}.png" if (PEND / f"{n}.png").exists() else SPR / f"{n}.png"
        im.alpha_composite(load(src), (x + 2, y + 2))
    return im


def size(p):
    with Image.open(p) as im:
        return im.size


def img(src, k, cls="chk", cap=""):
    w, h = size(OUT / src)
    c = f"<figcaption>{cap}</figcaption>" if cap else ""
    return f'<figure><div class="{cls}"><img src="{src}" width="{w * k}" height="{h * k}" alt=""></div>{c}</figure>'


def build():
    ATUAL.mkdir(parents=True, exist_ok=True)
    for n in ("pod", "chest", "machine_o2_t2", "machine_heater_t2", "icon_blueprint", "icon_iron", "icon_silicon",
              "icon_ice"):
        shutil.copyfile(SPR / f"{n}.png", ATUAL / f"{n}.png")
    for src, dst in ((CONCEPT_SRC, CONCEPT), (INGOT_REF_SRC, INGOT_REF)):
        if src.exists():
            shutil.copyfile(src, dst)
    nf, fw, fh = G.NF, G.W, G.H
    for i in range(nf):
        frame(i).save(OUT / f"bancada_v2_q{i}.png")
    base_scene("arid", 0).save(OUT / "cena_base_arid.png")
    base_scene("arid", 4).save(OUT / "cena_base_arid_operando.png")
    base_scene("green", 4).save(OUT / "cena_base_green.png")
    outpost_scene("mist", "frost", 4).save(OUT / "cena_posto_mist.png")
    hotbar((21, 16, 14, 255)).save(OUT / "hotbar_escuro.png")
    hotbar((232, 226, 214, 255), light=True).save(OUT / "hotbar_claro.png")
    # v2 × v1 × baú × cápsula, pés alinhados na mesma linha
    items = [load(V1 / "machine_workbench.png"), load(PEND / "machine_workbench.png"), load(SPR / "chest.png"),
             load(SPR / "pod.png")]
    Wc = sum(i.width for i in items) + 8 * (len(items) - 1)
    Hc = max(i.height for i in items)
    cmpi = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
    x = 0
    for im in items:
        cmpi.alpha_composite(im, (x, Hc - im.height))
        x += im.width + 8
    cmpi.save(OUT / "comparacao_v2.png")
    ing = Image.new("RGBA", (16 * 2 + 6, 16), (0, 0, 0, 0))
    ing.alpha_composite(load(V1 / "icon_iron_ingot.png"), (0, 0))
    ing.alpha_composite(load(PEND / "icon_iron_ingot.png"), (22, 0))
    ing.save(OUT / "lingote_v1_v2.png")

    icon_cards = []
    for n, label, desc in ICONS:
        icon_cards.append(f"""<div class="card"><h3>{label}</h3><code>{n}.png</code> · 16×16<div class="row">
{img(f"pendentes/{n}.png", 8)}{img(f"pendentes/{n}.png", 8, "lt")}
<div class="one"><img src="pendentes/{n}.png" width="16" height="16" alt=""><img src="pendentes/{n}.png" width="32" height="32" alt=""></div>
</div><p>{desc}</p></div>""")
    icon_cards.append(f"""<div class="card"><h3>Bancada T2 (item)</h3><code>icon_workbench.png</code> · 16×16<div class="row">
{img("pendentes/icon_workbench.png", 8)}{img("pendentes/icon_workbench.png", 8, "lt")}
<div class="one"><img src="pendentes/icon_workbench.png" width="16" height="16" alt=""><img src="pendentes/icon_workbench.png" width="32" height="32" alt=""></div>
</div><p>redesenhado na v2 pra acompanhar a bancada nova (baixa, braço de perfil na quina)</p></div>""")
    frames = "".join(img(f"bancada_v2_q{i}.png", 5, cap=c) for i, c in enumerate([
        "0 · repouso (= o parado): braço dobrado pra cima, visor desligado",
        "1 · o antebraço começa a baixar",
        "2 · o punho chega em cima do visor, a grade acende",
        "3 · a garra abre, laser fino",
        "4 · laser cheio, visor todo aceso, faíscas",
        "5 · laser cheio (pulsa), faíscas trocam",
        "6 · laser apaga, o braço sobe",
        "7 · voltando pro repouso, visor apagando"]))
    hb_w, hb_h = size(OUT / "hotbar_escuro.png")
    cw, ch = size(OUT / "comparacao_v2.png")
    S = 6
    cyc = nf / G.FPS
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · v0.5 · Bancada T2 e itens novos · v2</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1300px;margin:0 auto;padding:44px 0 80px}}
.eyebrow{{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}}
h1{{font:600 44px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}}h2{{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}}
h3{{font:600 16px "Pixelify Sans",monospace;margin:0 0 4px}}code{{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}}
p,li{{color:var(--muted)}}li b,p b{{color:var(--fg)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--rust);padding:12px 18px;max-width:1040px}}
.v2>b{{font:13px "Silkscreen",monospace;color:var(--rust)}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
.lt{{display:inline-block;padding:10px;background-color:#e8e2d6;background-image:linear-gradient(45deg,#d8d0c2 25%,transparent 25%,transparent 75%,#d8d0c2 75%),linear-gradient(45deg,#d8d0c2 25%,transparent 25%,transparent 75%,#d8d0c2 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px;max-width:420px}}
.flex{{display:flex;gap:22px;align-items:flex-end;flex-wrap:wrap}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}@media(max-width:1000px){{.grid2{{grid-template-columns:1fr}}}}
img.px{{width:100%;height:auto;border:1px solid var(--line);display:block}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:16px}}
.card{{background:var(--panel);border:1px solid var(--line);padding:14px}}.card p{{margin:6px 0 0;font-size:14px}}
.row{{display:flex;gap:12px;align-items:center;margin-top:8px;flex-wrap:wrap}}
.one{{display:flex;gap:10px;align-items:center;background:#2a2f38;padding:10px}}
.sp{{background-repeat:no-repeat;image-rendering:pixelated;display:inline-block}}
.a-wb{{width:{fw * S}px;height:{fh * S}px;background-image:url(pendentes/anim/anim_machine_workbench.png);background-size:{fw * nf * S}px {fh * S}px;animation:wb {cyc}s steps({nf}) infinite}}
@keyframes wb{{from{{background-position:0 0}}to{{background-position:-{fw * nf * S}px 0}}}}
.a-wb1{{width:{fw}px;height:{fh}px;background-image:url(pendentes/anim/anim_machine_workbench.png);background-size:{fw * nf}px {fh}px;animation:wb1 {cyc}s steps({nf}) infinite}}
@keyframes wb1{{from{{background-position:0 0}}to{{background-position:-{fw * nf}px 0}}}}
.a-v1{{width:240px;height:384px;background-image:url(v1/anim_machine_workbench.png);background-size:960px 384px;animation:v1 .6667s steps(4) infinite}}
@keyframes v1{{from{{background-position:0 0}}to{{background-position:-960px 0}}}}
.cmp{{display:flex;gap:30px;align-items:flex-end;flex-wrap:wrap}}
details>summary{{color:var(--muted);cursor:pointer;font:600 18px "Pixelify Sans",monospace;margin-top:40px}}
</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5 · proposta pro dono aprovar (nada disso está no jogo)</div>
<h1>Bancada T2 e os ícones dos itens novos</h1>

<div class="v2"><b>v2 · o que mudou (feedback do dono sobre a v1)</b><ul>
<li><b>Bancada menor</b>: de 40×64 pra <b>32×40</b>, o mesmo quadro do baú. O corpo ocupa uns 28×24 px, quase a pegada
do baú (31×23), e ela continua lendo como máquina: sapata B, colunas bege com a faixa laranja e o friso dourado,
corpo de cobre, visor e boca com bandeja.</li>
<li><b>Braço robótico na quina</b> da frente-esquerda do tampo, <b>de perfil</b>: base giratória (escura com anel
laranja), braço, cotovelo, antebraço, punho e garra de 2 dedos. É bege com juntas escuras pra destacar do cobre. O
antebraço baixa e o laser sai da garra e desce pro visor.</li>
<li><b>Animação mais lenta: 8 quadros a 4 fps</b> (ciclo de 2 s). Escolhi mais quadros em vez de só baixar o fps:
com 4 quadros a 3 fps o braço "pula"; com 8 ele desce, trabalha (laser fino → cheio → pulsa) e volta suave.</li>
<li><b>Lingote de ferro refeito</b> pela referência do dono: barra de <b>aço cinza claro</b>, bloco retangular em 3/4
com o tampo grande e chanfrado, brilho no tampo, a frente média com um reflexo e o lado na sombra. Nada de cobre.</li>
<li><b>Decisões do dono registradas:</b> o <b>diagrama substitui o projeto</b> (<code>bp_&lt;id&gt;</code>) e o ícone
novo fica no lugar do <code>icon_blueprint</code>; o <code>icon_workbench</code> fica (redesenhado pra bancada
nova); os ids propostos estão ok: <code>workbench</code>, <code>iron_ingot</code>, <code>water_capsule</code>,
<code>silicon_wafer</code>, <code>circuit</code>, <code>chip</code>, <code>wire</code> e <code>diagram</code>.</li>
<li>Os outros ícones (cápsula, wafer, circuito, chip, fios e diagrama) foram <b>aprovados</b> e não mudaram.</li>
</ul></div>

<h2>v2 · Bancada ao lado da v1, do baú e da cápsula</h2>
<div class="flex">
{img("comparacao_v2.png", 5, cap="v1 (40×64) · <b>v2 (32×40)</b> · baú (32×40) · cápsula/fabricador (64×72), pés alinhados, 5×")}
{img("comparacao_v2.png", 1, cap="1×")}
</div>
<div class="flex" style="margin-top:18px">
{img("pendentes/machine_workbench.png", S, cap="v2 · repouso · <code>machine_workbench.png</code> · 6×")}
<figure><div class="chk"><div class="sp a-wb"></div></div><figcaption>v2 · operando · {nf} quadros a {G.FPS} fps · 6×</figcaption></figure>
<figure><div class="chk" style="padding:18px"><img src="pendentes/machine_workbench.png" width="{fw}" height="{fh}" alt=""> <div class="sp a-wb1"></div> <img src="atual/chest.png" width="32" height="40" alt=""></div><figcaption>1×: parado, operando e o baú</figcaption></figure>
<figure><div class="chk"><div class="sp a-v1"></div></div><figcaption>v1 (histórico) · 6×</figcaption></figure>
</div>

<h2>v2 · Os 8 quadros</h2>
<div class="flex">{frames}</div>

<h2>v2 · Lingote de ferro: referência × v1 × v2</h2>
<div class="cmp">
<figure><img src="ref_lingote_aco.png" width="220" height="220" style="image-rendering:auto" alt=""><figcaption>referência do dono (só estilo, não copiado)</figcaption></figure>
{img("v1/icon_iron_ingot.png", 10, cap="v1 · trapézio cor de cobre (o “pão de forma”)")}
{img("pendentes/icon_iron_ingot.png", 10, cap="<b>v2</b> · barra de aço cinza claro")}
{img("pendentes/icon_iron_ingot.png", 10, "lt", cap="v2 sobre fundo claro")}
<figure><div class="one" style="padding:16px"><img src="v1/icon_iron_ingot.png" width="16" height="16" alt=""><img src="pendentes/icon_iron_ingot.png" width="16" height="16" alt=""><img src="atual/icon_iron.png" width="16" height="16" alt=""><img src="pendentes/icon_chip.png" width="16" height="16" alt=""><img src="pendentes/icon_iron_ingot.png" width="32" height="32" alt=""></div><figcaption>1×: v1, v2, o minério de ferro e o chip; e a v2 a 2×</figcaption></figure>
</div>
<p><b>O que veio da referência:</b> o bloco retangular deitado em 3/4, o tampo grande e claro com a faixa de brilho,
a quina chanfrada clara entre o tampo e a frente, a frente cinza média com um pontinho de reflexo e a lateral
escura. <b>No nosso estilo:</b> 16×16, contorno <code>#1b1630</code>, só cores chapadas (6 cinzas frios, do
<code>#ffffff</code> ao <code>#555b6a</code>), sem alfa parcial. Diferencia-se do minério de ferro (pepitas cobre) e
do tampo prateado do chip pelo formato de barra.</p>

<h2>v2 · No chão do jogo</h2>
<div class="grid2">
<figure><img class="px" src="cena_base_arid.png" alt=""><figcaption><b>base</b> · Árido · bancada em repouso ao lado da cápsula</figcaption></figure>
<figure><img class="px" src="cena_base_arid_operando.png" alt=""><figcaption><b>base</b> · Árido · operando (quadro 4)</figcaption></figure>
<figure><img class="px" src="cena_base_green.png" alt=""><figcaption><b>base</b> · Verde · operando</figcaption></figure>
<figure><img class="px" src="cena_posto_mist.png" alt=""><figcaption><b>posto avançado</b> · Névoa, faixa gelada · com baú, luminária forte e painel</figcaption></figure>
</div>
<p>Recortes 480×270 (metade da tela) ampliados 2×, montados só com os sprites, ordenados pelo pé como o jogo desenha.</p>

<h2>Ícones dos itens</h2>
<div class="cards">{''.join(icon_cards)}</div>

<h2>Na hotbar, em tamanho real</h2>
<div class="flex">
<figure><img src="hotbar_escuro.png" width="{hb_w}" height="{hb_h}" alt=""><figcaption>1×</figcaption></figure>
</div>
<div class="flex" style="margin-top:14px">
<figure><img src="hotbar_escuro.png" width="{hb_w * 3}" height="{hb_h * 3}" alt=""><figcaption>3× sobre fundo escuro · no fim, os aprovados (minério de ferro, silício e o projeto que sai) pra comparar</figcaption></figure>
<figure><img src="hotbar_claro.png" width="{hb_w * 3}" height="{hb_h * 3}" alt=""><figcaption>3× sobre fundo claro</figcaption></figure>
</div>

<h2>Projeto (sai) × Diagrama (entra)</h2>
<div class="cmp">
{img("atual/icon_blueprint.png", 10, cap="sai · <code>icon_blueprint.png</code> (projeto, bp_&lt;id&gt;)")}
{img("pendentes/icon_diagram.png", 10, cap="entra · <code>icon_diagram.png</code> (diagrama)")}
</div>
<p>Decisão do dono: o diagrama <b>substitui</b> o projeto. Mesma família (azul de planta, grade, traço claro, laranja
de acento), agora um cartão deitado com clipe.</p>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Nada disso entra sem o ok do dono.</b> Ids aprovados: <code>workbench</code>, <code>iron_ingot</code>,
<code>water_capsule</code>, <code>silicon_wafer</code>, <code>circuit</code>, <code>chip</code>, <code>wire</code>,
<code>diagram</code>.</li>
<li><b>Bancada</b>: <code>machine_workbench.png</code> <b>32×40</b> (v2; a v1 era 40×64), âncora do baú: pé no centro
da borda de baixo do tile, 1 tile, cabe no tile (não passa pros lados). Sem sombra no sprite.</li>
<li><b>Animação</b>: <code>anim/anim_machine_workbench.png</code> <b>{fw * nf}×{fh}</b>, <b>{nf} quadros</b> de {fw}×{fh} na
horizontal, <b>{G.FPS} fps</b> sugerido (ciclo de {cyc:g} s). <b>Atenção:</b> o <code>anim_frames</code> de hoje usa
<code>ANIM_FRAMES = 4</code> fixo; essa tira precisa do nº de quadros tirado da largura (largura ÷ largura do parado) ou
de um caso só pra ela. Quadro 0 = o repouso (pixel a pixel igual ao parado). Sugestão: anima só enquanto fabrica e sem
fase por tile.</li>
<li>Pontos no quadro (32×40): ponta da garra trabalhando (quadros 3–5) em (17, 13); miolo do visor em (16, 22); boca de
(12, 26) a (20, 30).</li>
<li><b>Ícones</b> 16×16, contorno <code>#1b1630</code>, alpha 0/255: <code>icon_iron_ingot</code> (v2),
<code>icon_water_capsule</code>, <code>icon_silicon_wafer</code>, <code>icon_circuit</code>, <code>icon_chip</code>,
<code>icon_wire</code>, <code>icon_diagram</code> (no lugar do <code>icon_blueprint</code> nos itens
<code>bp_&lt;id&gt;</code> / aviso de projeto) e <code>icon_workbench</code> (v2).</li>
<li>Regerar: <code>python3 tools/sprites/v05_bancada_itens.py</code> (determinístico; refaz este report). A v1 fica
congelada em <code>v1/</code>.</li>
</ul></div>

<details><summary>v1 · histórico</summary>
<div class="v2" style="margin-top:12px"><b>v1.0 · o que tinha</b><ul>
<li>Bancada 40×64 (tamanho do nv.2), garra no meio do tampo, 4 quadros a 6 fps.</li>
<li>Lingote em trapézio cor de cobre. O resto dos ícones é o mesmo da v2.</li>
</ul></div>
<div class="flex" style="margin-top:14px">
<figure><img src="ref_conceito_montadora.png" width="512" height="383" style="image-rendering:auto" alt=""><figcaption>conceito do dono (Montadora)</figcaption></figure>
{img("v1/machine_workbench.png", 5, cap="v1 · repouso")}
{''.join(img(f"v1/bancada_q{i}.png", 4, cap=f"v1 · quadro {i}") for i in range(4))}
{img("v1/familia.png", 4, cap="v1 · cápsula × bancada × O₂ nv.2")}
{img("v1/icon_workbench.png", 8, cap="v1 · icon_workbench")}
</div>
<div class="grid2" style="margin-top:14px">
<figure><img class="px" src="v1/cena_base_arid_operando.png" alt=""><figcaption>v1 · base no Árido, operando</figcaption></figure>
<figure><img class="px" src="v1/cena_posto_mist.png" alt=""><figcaption>v1 · posto avançado</figcaption></figure>
</div>
<p><b>O que veio do conceito (vale pras duas versões):</b> corpo de cobre entre laterais creme, base escura larga, garra
robótica, visor na frente, boca com bandeja, laser azul da garra pro visor, visor piscando em ciano, faíscas. Traduzido
pro nosso pixel art: colunas bege com faixa laranja e friso dourado (família do fabricador e das nv.2), sapata B
padrão, cobre em 5 faixas de luz, laser em pixel chapado (núcleo branco, borda ciano), sem glow nem gradiente.</p>
</details>
</div></body></html>
"""
    page = OUT / "index.html"
    page.write_text(html, encoding="utf-8")
    return page


if __name__ == "__main__":
    print(build())
