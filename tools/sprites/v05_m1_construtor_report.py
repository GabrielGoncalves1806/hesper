"""Report do construtor, da mochila e da luz de scanner (reports/design/v05_m1_construtor/index.html).
Chamado pelo tools/sprites/v05_m1_construtor.py depois de exportar os pendentes. Só lê assets/ (nunca escreve lá)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import v05_m1_construtor as G  # noqa: E402

ROOT = G.ROOT
OUT = G.REP
PEND = G.PEND
SIM = G.SIM
SPR = ROOT / "assets" / "sprites"
BANC = ROOT / "reports" / "design" / "v05_bancada_itens" / "pendentes"
ATUAL = OUT / "atual"
NEIGHBORS = ["icon_o2_tank", "icon_scanner", "icon_drill", "icon_drone", "icon_chest", "icon_lamp", "icon_iron"]
HOLD = 12            # passos parado entre construir e desmontar no loop do report (1 s)
GAP = 6              # passos vazios no fim do loop


def load(p):
    return Image.open(p).convert("RGBA")


def ground(region, stage, w, h, seed):
    import regions_v9 as V9
    return V9.ground_patch(region, stage, w, h, seed).convert("RGBA")


def put(objs, img, fx, fy):
    objs.append((fy, img, fx - img.width // 2, fy - img.height))


def compose(bg, objs):
    for _, img, x, y in sorted(objs, key=lambda o: o[0]):
        bg.alpha_composite(img, (x, y))
    return bg


def size(p):
    with Image.open(p) as im:
        return im.size


def img(src, k, cls="chk", cap=""):
    w, h = size(OUT / src)
    c = f"<figcaption>{cap}</figcaption>" if cap else ""
    return f'<figure><div class="{cls}"><img src="{src}" width="{w * k}" height="{h * k}" alt=""></div>{c}</figure>'


def hotbar(bg_col, light=False):
    """Hotbar de mentira no estilo B (cartões escuros, canto cortado): os 2 novos primeiro, depois os vizinhos."""
    names = ["icon_constructor", "icon_backpack"] + NEIGHBORS + ["icon_workbench", "icon_diagram"]
    pad, sz = 4, 20
    W = pad + len(names) * (sz + 2) + pad
    im = Image.new("RGBA", (W, sz + 2 * pad), bg_col)
    card = (0x1e, 0x1a, 0x24, 255) if not light else (0x2a, 0x25, 0x31, 255)
    edge = (0x3a, 0x35, 0x49, 255) if not light else (0x4a, 0x44, 0x58, 255)
    sel = (0xe2, 0x73, 0x3a, 255)
    for i, n in enumerate(names):
        x, y = pad + i * (sz + 2), pad
        slot = Image.new("RGBA", (sz, sz), card)
        for k in range(sz):
            slot.putpixel((k, 0), sel if i == 0 else edge)
        for c in ((0, 0), (sz - 1, 0), (0, sz - 1), (sz - 1, sz - 1)):
            slot.putpixel(c, (0, 0, 0, 0))
        im.alpha_composite(slot, (x, y))
        src = PEND / f"{n}.png"
        if not src.exists():
            src = ATUAL / f"{n}.png"
        im.alpha_composite(load(src), (x + 2, y + 2))
    return im


def equip_row():
    """Os 3 slots de equipamento do traje lado a lado: tanque, scanner e a mochila (nova)."""
    names = ["icon_o2_tank", "icon_scanner", "icon_backpack"]
    sz, pad = 22, 4
    im = Image.new("RGBA", (pad + len(names) * (sz + 3) + pad, sz + 2 * pad), (21, 16, 14, 255))
    for i, n in enumerate(names):
        x = pad + i * (sz + 3)
        im.alpha_composite(Image.new("RGBA", (sz, sz), (0x1e, 0x1a, 0x24, 255)), (x, pad))
        for k in range(sz):
            im.putpixel((x + k, pad), (0x59, 0xd0, 0xe6, 255) if n == "icon_backpack" else (0x3a, 0x35, 0x49, 255))
        src = PEND / f"{n}.png" if (PEND / f"{n}.png").exists() else ATUAL / f"{n}.png"
        im.alpha_composite(load(src), (x + 3, pad + 3))
    return im


def icons_on_ground():
    bg = ground("plateau", "arid", 160, 40, 5)
    names = ["icon_constructor", "icon_backpack", "icon_o2_tank", "icon_scanner"]
    for i, (region, stage) in enumerate((("plateau", "arid"), ("frost", "mist"), ("plateau", "green"))):
        bg.paste(ground(region, stage, 160 // 3 + 1, 40, 9 + i), (i * (160 // 3), 0))
    x = 6
    for st in range(3):
        for n in names[:2]:
            bg.alpha_composite(load(PEND / f"{n}.png"), (x, 12))
            x += 22
        x += 9
    return bg


# ---------------------------------------------------------------------------------------------------------------------
def seqs(spr):
    still = G.still_frame(spr)
    b = G.build_seq(spr)
    u = G.unbuild_seq(spr)
    return b, still, u


def loop_frames(spr):
    b, still, u = seqs(spr)
    empty = np.zeros_like(still)
    return b + [still] * HOLD + u + [empty] * GAP


def on_ground(frames, region, stage, seed, below=6):
    h, w = frames[0].shape[:2]
    bg = ground(region, stage, w, h + below, seed)
    out = []
    for f in frames:
        im = bg.copy()
        im.alpha_composite(Image.fromarray(f), (0, 0))
        out.append(im)
    return out


def strip_img(ims, gap=0, bg=(0, 0, 0, 0)):
    w, h = ims[0].size
    s = Image.new("RGBA", (len(ims) * (w + gap) - gap, h), bg)
    for i, im in enumerate(ims):
        s.alpha_composite(im, (i * (w + gap), 0))
    return s


BUILD_KEYS = [0, 3, 6, 9, 12, 15, 18]           # + flash + parado
UNBUILD_KEYS = [0, 4, 8, 12, 16, 20, 24]        # + apagado + holograma + some


def keyframes(spr, region, stage, seed):
    b, still, u = seqs(spr)
    bsel = [b[i] for i in BUILD_KEYS] + [b[G.BUILD_STEPS + 1], still]
    usel = [u[i] for i in UNBUILD_KEYS] + [u[G.UNBUILD_STEPS + 2]]
    return (strip_img(on_ground(bsel, region, stage, seed), 2, (21, 16, 14, 255)),
            strip_img(on_ground(usel, region, stage, seed), 2, (21, 16, 14, 255)))


def scene(region, stage, seed):
    """480×270: base com máquinas em estados diferentes da luz de scanner, o Explorador apontando o construtor."""
    bg = ground(region, stage, 480, 270, seed)
    o = []
    spr = {k: G.load(p) for k, p, _ in G.MACHINES}
    def obj(arr):
        return Image.fromarray(arr)

    put(o, obj(G.still_frame(G.load(SPR / "machine_melter.png"))), 112, 128)
    put(o, obj(G.scan_frame(spr["machine_o2"], 9 / G.BUILD_STEPS, 9)), 176, 128)
    put(o, obj(G.scan_frame(spr["machine_heater_t2"], 4 / G.BUILD_STEPS, 4)), 240, 128)
    put(o, obj(G.flash_frame(spr["chest"])), 304, 128)
    put(o, obj(G.scan_frame(spr["machine_workbench"], 1 - 14 / G.UNBUILD_STEPS, 14)), 368, 128)
    put(o, obj(G.still_frame(G.load(SPR / "solar_panel.png"))), 176, 224)
    put(o, obj(G.still_frame(G.load(SPR / "lamp.png"))), 112, 224)
    put(o, load(SPR / "player_idle_up.png").crop((0, 0, 32, 32)), 240, 186)
    return compose(bg, o)


def build():
    ATUAL.mkdir(parents=True, exist_ok=True)
    SIM.mkdir(parents=True, exist_ok=True)
    for n in NEIGHBORS:
        shutil.copyfile(SPR / f"{n}.png", ATUAL / f"{n}.png")
    for n in ("icon_workbench", "icon_diagram"):
        shutil.copyfile(BANC / f"{n}.png", ATUAL / f"{n}.png")
    hotbar((21, 16, 14, 255)).save(OUT / "hotbar_escuro.png")
    hotbar((232, 226, 214, 255), light=True).save(OUT / "hotbar_claro.png")
    equip_row().save(OUT / "equip_traje.png")
    icons_on_ground().save(OUT / "icones_no_chao.png")

    stages = {"machine_o2": ("plateau", "arid", 3), "chest": ("frost", "mist", 4),
              "machine_workbench": ("plateau", "green", 5), "machine_heater_t2": ("plateau", "arid", 6)}
    anims = []
    nloop = None
    for key, path, label in G.MACHINES:
        spr = G.load(path)
        region, stage, seed = stages[key]
        kb, ku = keyframes(spr, region, stage, seed)
        kb.save(SIM / f"quadros_construir_{key}.png")
        ku.save(SIM / f"quadros_desmontar_{key}.png")
        lf = on_ground(loop_frames(spr), region, stage, seed)
        nloop = len(lf)
        strip_img(lf).save(SIM / f"loop_{key}.png")
        fw, fh = lf[0].size
        anims.append((key, label, stage, fw, fh))
    for st, (reg, stage, seed) in {"arid": ("plateau", "arid", 21), "mist": ("frost", "mist", 22),
                                   "green": ("plateau", "green", 23)}.items():
        scene(reg, stage, seed).save(OUT / f"cena_scanner_{st}.png")
    # paleta da luz (amostras)
    sw = Image.new("RGBA", (7 * 12, 12), (0, 0, 0, 0))
    for i, c in enumerate((G.SCAN_CORE, G.SCAN_EDGE, G.SCAN_PULSE, G.SCAN_PLANE, G.SCAN_NODE, G.GHOST)):
        sw.paste(Image.new("RGBA", (10, 10), c), (i * 12 + 1, 1))
    sw.save(SIM / "paleta.png")
    return write_html(anims, nloop)


def write_html(anims, nloop):
    fps = G.FPS
    dur = nloop / fps
    S = 4
    css, blocks = [], []
    for key, label, stage, fw, fh in anims:
        css.append(f".a-{key}{{width:{fw * S}px;height:{fh * S}px;background-image:url(sim/loop_{key}.png);"
                   f"background-size:{fw * nloop * S}px {fh * S}px;animation:k{key} {dur:.4f}s steps({nloop}) infinite}}"
                   f"@keyframes k{key}{{from{{background-position:0 0}}to{{background-position:-{fw * nloop * S}px 0}}}}"
                   f".b-{key}{{width:{fw}px;height:{fh}px;background-image:url(sim/loop_{key}.png);"
                   f"background-size:{fw * nloop}px {fh}px;animation:j{key} {dur:.4f}s steps({nloop}) infinite}}"
                   f"@keyframes j{key}{{from{{background-position:0 0}}to{{background-position:-{fw * nloop}px 0}}}}")
        blocks.append(f"""<figure><div class="sp a-{key}"></div><div class="sp b-{key}" style="margin-top:8px"></div>
<figcaption>{label} · chão {stage} · 4× e 1×</figcaption></figure>""")
    keys = []
    for key, label, stage, fw, fh in anims:
        bw, bh = size(SIM / f"quadros_construir_{key}.png")
        uw, uh = size(SIM / f"quadros_desmontar_{key}.png")
        keys.append(f"""<h3 style="margin-top:22px">{label}</h3>
<figure><img src="sim/quadros_construir_{key}.png" width="{bw * 3}" height="{bh * 3}" alt="">
<figcaption>construir · passos {", ".join(map(str, BUILD_KEYS))} · flash · parado</figcaption></figure>
<figure style="margin-top:8px"><img src="sim/quadros_desmontar_{key}.png" width="{uw * 3}" height="{uh * 3}" alt="">
<figcaption>desmontar · passos {", ".join(map(str, UNBUILD_KEYS))} · holograma piscando (o vazio fica de fora)</figcaption></figure>""")
    hb_w, hb_h = size(OUT / "hotbar_escuro.png")
    eq_w, eq_h = size(OUT / "equip_traje.png")
    gw, gh = size(OUT / "icones_no_chao.png")
    cards = []
    for n, label, desc in (
        ("icon_constructor", "Construtor", "pistola de construção de perfil: corpo branco com a faixa laranja, visorzinho "
         "em cima, cabo laranja com gatilho e, na frente, a <b>cabeça emissora</b>: anel cinza com a lente ciano grande "
         "(brilho branco em cima, ciano escuro embaixo). Lê como projetor de luz: sem ponta, sem cone, sem rosca, pra "
         "não brigar com a broca de mão que vem depois."),
        ("icon_backpack", "Mochila", "vista de costas, em domo: alça de mão, aba branca com o LED ciano e a borda "
         "laranja com a fivela, tira escura descendo, bolso da frente com o zíper laranja e as alças de ombro escuras "
         "nos dois lados. Mesmo branco frio, cinzas, laranja e ciano do tanque de O₂ e do scanner.")):
        cards.append(f"""<div class="card"><h3>{label}</h3><code>{n}.png</code> · 16×16<div class="row">
{img(f"pendentes/{n}.png", 8)}{img(f"pendentes/{n}.png", 8, "lt")}
<div class="one"><img src="pendentes/{n}.png" width="16" height="16" alt=""><img src="pendentes/{n}.png" width="32" height="32" alt=""></div>
</div><p>{desc}</p></div>""")
    neigh = "".join(f'<img src="atual/{n}.png" width="64" height="64" alt="">' for n in NEIGHBORS[:3])
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · v0.5 M1 · construtor, mochila e luz de scanner · v1.0</title>
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
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px;max-width:520px}}
.flex{{display:flex;gap:22px;align-items:flex-end;flex-wrap:wrap}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}@media(max-width:1100px){{.grid3{{grid-template-columns:1fr}}}}
img.px{{width:100%;height:auto;border:1px solid var(--line);display:block}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(460px,1fr));gap:16px}}
.card{{background:var(--panel);border:1px solid var(--line);padding:14px}}.card p{{margin:6px 0 0;font-size:14px}}
.row{{display:flex;gap:12px;align-items:center;margin-top:8px;flex-wrap:wrap}}
.one{{display:flex;gap:10px;align-items:center;background:#2a2f38;padding:10px}}
.sp{{background-repeat:no-repeat;image-rendering:pixelated;display:block}}
table{{border-collapse:collapse;font-size:14px}}td,th{{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}}
th{{font:12px "Silkscreen",monospace;color:var(--rust)}}td{{color:var(--muted)}}td b{{color:var(--fg)}}
.sw{{display:inline-block;width:14px;height:14px;border:1px solid #000;vertical-align:middle;margin-right:6px}}
pre{{background:#100c0b;border:1px solid var(--line);padding:14px;overflow:auto;font:13px/1.5 "IBM Plex Mono",monospace;color:#d8cfc6}}
{''.join(css)}
</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5 Marco 1 · proposta pro dono aprovar (nada disso está no jogo)</div>
<h1>Construtor, mochila e a luz de scanner</h1>

<div class="v2"><b>v1.0 · o que tem aqui</b><ul>
<li><b>Ícone do construtor</b> (<code>icon_constructor</code>, 16×16): a ferramenta de mão que constrói as máquinas.
Pistola com <b>cabeça emissora e lente ciano</b>, nada de ponta de broca.</li>
<li><b>Ícone da mochila</b> (<code>icon_backpack</code>, 16×16): equipamento do traje, +1 linha de slots. Mesma
família do tanque de O₂ e do scanner.</li>
<li><b>Luz de scanner</b> pra construir (1,5 s, de baixo pra cima) e desmontar (2 s, de cima pra baixo). É um efeito
<b>procedural</b> que o Dev faz no código. Aqui estão as regras, os números e a simulação em 4 máquinas reais sobre o
chão do jogo.</li>
</ul></div>

<h2>Ícones novos</h2>
<div class="cards">{''.join(cards)}</div>
<div class="flex" style="margin-top:16px">
<figure><div class="one" style="padding:14px"><img src="pendentes/icon_constructor.png" width="64" height="64" alt="">{neigh}</div>
<figcaption>construtor ao lado do tanque, do scanner e da drill (4×)</figcaption></figure>
<figure><img src="icones_no_chao.png" width="{gw * 3}" height="{gh * 3}" alt=""><figcaption>sobre o chão do Árido, da Névoa e do Verde (3×)</figcaption></figure>
</div>

<h2>Na hotbar e no traje, em tamanho real</h2>
<div class="flex">
<figure><img src="hotbar_escuro.png" width="{hb_w}" height="{hb_h}" alt=""><figcaption>1×</figcaption></figure>
<figure><img src="equip_traje.png" width="{eq_w}" height="{eq_h}" alt=""><figcaption>1× · traje</figcaption></figure>
</div>
<div class="flex" style="margin-top:14px">
<figure><img src="hotbar_escuro.png" width="{hb_w * 3}" height="{hb_h * 3}" alt=""><figcaption>3× · fundo escuro · construtor (selecionado), mochila, e os vizinhos: tanque, scanner, drill, drone, baú, luminária, ferro, bancada e diagrama</figcaption></figure>
<figure><img src="hotbar_claro.png" width="{hb_w * 3}" height="{hb_h * 3}" alt=""><figcaption>3× · fundo claro</figcaption></figure>
<figure><img src="equip_traje.png" width="{eq_w * 3}" height="{eq_h * 3}" alt=""><figcaption>3× · os 3 slots do traje: tanque, scanner, mochila</figcaption></figure>
</div>

<h2>Luz de scanner · animada</h2>
<p>Loop do report: constrói (1,5 s), flash, fica parada 1 s, desmonta (2 s), holograma pisca e some. Tudo a
<b>{fps} passos por segundo</b>, sobre o chão do jogo.</p>
<div class="flex">{''.join(blocks)}</div>

<h2>Luz de scanner · na base</h2>
<div class="grid3">
<figure><img class="px" src="cena_scanner_arid.png" alt=""><figcaption>Árido</figcaption></figure>
<figure><img class="px" src="cena_scanner_mist.png" alt=""><figcaption>Névoa (faixa gelada)</figcaption></figure>
<figure><img class="px" src="cena_scanner_green.png" alt=""><figcaption>Verde</figcaption></figure>
</div>
<p>Da esquerda pra direita: derretedor parado, O₂ na metade da construção, aquecedor nv.2 começando, baú no quadro do
flash, bancada no meio do desmonte. Recortes 480×270 montados só com os sprites e ordenados pelo pé.</p>

<h2>Luz de scanner · quadros-chave</h2>
<p>3×, sobre o chão. Os passos são os de {fps} por segundo.</p>
{''.join(keys)}

<h2>Os números (pro config)</h2>
<table>
<tr><th>o quê</th><th>valor</th><th>como</th></tr>
<tr><td><b>Núcleo</b></td><td><span class="sw" style="background:{G.SCAN_CORE}"></span><code>{G.SCAN_CORE}</code></td><td>1 px, a linha da faixa, só sobre a silhueta do sprite</td></tr>
<tr><td><b>Borda</b></td><td><span class="sw" style="background:{G.SCAN_EDGE}"></span><code>{G.SCAN_EDGE}</code></td><td>1 px em cima e 1 px embaixo do núcleo, só sobre a silhueta</td></tr>
<tr><td><b>Pulso</b></td><td><span class="sw" style="background:{G.SCAN_PULSE}"></span><code>{G.SCAN_PULSE}</code></td><td>+1 px de cada lado nos passos ímpares: a faixa pulsa <b>3 px ↔ 5 px</b>, como o feixe da drill</td></tr>
<tr><td><b>Plano</b></td><td><span class="sw" style="background:{G.SCAN_PLANE}"></span><code>{G.SCAN_PLANE}</code> + ponta <code>{G.SCAN_NODE}</code></td><td>na linha do núcleo, <b>{G.PLANE_OUT} px</b> pra fora da silhueta de cada lado (medido na própria linha) e 1 px branco na ponta</td></tr>
<tr><td><b>Holograma</b></td><td><span class="sw" style="background:{G.GHOST}"></span><code>{G.GHOST}</code></td><td>o que ainda não foi construído: só os pixels de contorno <code>#1b1630</code> do sprite, trocados por essa cor</td></tr>
<tr><td><b>Linhas recém-reveladas</b></td><td><code>BLEND_RGB_ADD {G.FRESH_ADD}</code></td><td>as <b>{G.FRESH_ROWS}</b> linhas logo abaixo da faixa: sprite normal com essa soma (fica "quente" de ciano)</td></tr>
<tr><td><b>Faíscas</b></td><td><code>{G.SPARK_COLS[0]}</code> / <code>{G.SPARK_COLS[1]}</code></td><td><b>{G.SPARKS}</b> por passo, 1 px, vivem 1 passo; x sorteado no bbox, y de {G.SPARK_UP[0]} a {G.SPARK_UP[1]} px acima do núcleo; só em pixel vazio; cores alternando</td></tr>
<tr><td><b>Passo</b></td><td><b>{fps}/s</b> ({1000 / fps:.0f} ms)</td><td>a faixa anda em passos inteiros de pixel e as faíscas/pulso trocam a cada passo (pixel art, nada de sub-pixel)</td></tr>
<tr><td><b>Construir</b></td><td>{G.BUILD_S} s = <b>{G.BUILD_STEPS} passos</b></td><td>p = passo / {G.BUILD_STEPS}, sobe; depois <b>{G.FLASH_STEPS} passo de flash</b> (o sprite inteiro com a soma) e a máquina passa a funcionar</td></tr>
<tr><td><b>Desmontar</b></td><td>{G.UNBUILD_S} s = <b>{G.UNBUILD_STEPS} passos</b></td><td>p = 1 − passo / {G.UNBUILD_STEPS}, desce, segue o botão segurado; no fim o holograma pisca (<b>{G.BLINK_STEPS} passos</b>: apagado, aceso) e some. Soltou antes: volta direto pro sprite normal</td></tr>
</table>
<p style="margin-top:10px"><img src="sim/paleta.png" width="{7 * 12 * 4}" height="48" alt=""> núcleo, borda, pulso, plano, ponta, holograma. Todos na família do laser da drill (<code>LASER_CYAN</code> = branco, <code>#c8f6ff</code>, <code>#59d0e6</code>, <code>#2b8fb3</code>).</p>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Nada disso entra sem o ok do dono.</b> Ícones: <code>icon_constructor.png</code> e <code>icon_backpack.png</code>,
16×16, contorno <code>#1b1630</code>, alpha 0/255, mesmo uso dos outros <code>icon_*</code> (hotbar, inventário,
fabricador; a mochila também no slot de equipamento, ao lado de <code>icon_o2_tank</code> e <code>icon_scanner</code>).</li>
<li><b>A luz não tem asset</b>: é desenhada por cima do sprite parado da máquina, com a mesma âncora (pé no centro da
borda de baixo do tile). Funciona com qualquer sprite, inclusive os altos (nv.2) e a drill 2×2.</li>
<li><b>Uma função pros dois sentidos.</b> Construir e desmontar desenham igual: <b>abaixo da faixa é máquina, acima é
holograma</b>. Só muda de onde vem o p.</li>
<li>Pré-calcule por sprite (uma vez): o bbox da silhueta (y_topo, y_pé), a máscara da silhueta e a superfície do
holograma (contorno <code>#1b1630</code> → <code>{G.GHOST}</code>, resto transparente).</li>
<li>A <b>sombra de chão</b> da máquina (se houver) aparece já no começo da construção e some no fim do desmonte.</li>
<li>Durante a construção a máquina <b>não funciona</b> (sem anim de operando, sem LED). A animação de operando só
começa depois do flash.</li>
<li>A referência exata está em <code>tools/sprites/v05_m1_construtor.py</code> (<code>scan_frame</code>,
<code>build_seq</code>, <code>unbuild_seq</code>), em numpy. Em pygame fica assim:</li>
</ul>
<pre>SCAN_FPS = {fps}
SCAN_BUILD_S, SCAN_UNBUILD_S = {G.BUILD_S}, {G.UNBUILD_S}
SCAN_CORE, SCAN_EDGE, SCAN_PULSE = "{G.SCAN_CORE}", "{G.SCAN_EDGE}", "{G.SCAN_PULSE}"
SCAN_PLANE, SCAN_NODE, SCAN_GHOST = "{G.SCAN_PLANE}", "{G.SCAN_NODE}", "{G.GHOST}"
SCAN_FRESH_ADD, SCAN_FRESH_ROWS = {G.FRESH_ADD}, {G.FRESH_ROWS}
SCAN_PLANE_OUT, SCAN_SPARKS, SCAN_SPARK_UP = {G.PLANE_OUT}, {G.SPARKS}, {G.SPARK_UP}
SCAN_FLASH_STEPS, SCAN_BLINK_STEPS = {G.FLASH_STEPS}, {G.BLINK_STEPS}

# step = int(t * SCAN_FPS)
# construir:  p = min(step / round(SCAN_BUILD_S * SCAN_FPS), 1)
# desmontar:  p = 1 - min(step / round(SCAN_UNBUILD_S * SCAN_FPS), 1)
def draw_scan(dst, spr, ghost, x, y, p, step):          # (x, y) = canto do sprite, como o blit normal
    y0, y1 = bbox_top, bbox_bottom                       # pré-calculados
    ys = round(y1 + 1 - p * (y1 - y0 + 2))               # linha do núcleo (relativa ao sprite)
    h = spr.get_height()
    # 1) máquina: linhas abaixo da faixa
    if ys + 1 &lt; h:
        dst.blit(spr, (x, y + ys + 1), (0, ys + 1, spr.get_width(), h))
        fresh = spr.subsurface((0, ys + 1, w, min(SCAN_FRESH_ROWS, h - ys - 1))).copy()
        fresh.fill(SCAN_FRESH_ADD, special_flags=pygame.BLEND_RGB_ADD)
        dst.blit(fresh, (x, y + ys + 1))
    # 2) holograma: linhas acima da faixa
    if ys &gt; 0:
        dst.blit(ghost, (x, y), (0, 0, w, ys))
    # 3) faixa: 3 px (5 px nos passos ímpares), só onde a máscara tem pixel
    half = 2 if step % 2 else 1
    for k in range(-half, half + 1):
        row = ys + k
        cor = SCAN_CORE if k == 0 else SCAN_EDGE if abs(k) == 1 else SCAN_PULSE
        for (a, b) in runs_da_mascara(row):             # trechos [a, b] com pixel na linha
            dst.fill(cor, (x + a, y + row, b - a + 1, 1))
    # 4) plano: na linha ys, de a-2 até b+2 (a/b = 1º e último pixel da linha), ponta branca em a-3 e b+3
    # 5) faíscas: SCAN_SPARKS por passo, x = sorteio(step) no bbox, y = ys - randint(*SCAN_SPARK_UP), só fora da máscara</pre>
<ul>
<li>As faíscas usam um sorteio <b>só do passo</b> (hash do <code>step</code>), sem estado; no gerador é um FNV-1a, mas
qualquer <code>random.Random(step)</code> serve.</li>
<li>Regerar: <code>python3 tools/sprites/v05_m1_construtor.py</code> (determinístico; refaz este report).</li>
</ul></div>
</div></body></html>
"""
    page = OUT / "index.html"
    page.write_text(html, encoding="utf-8")
    return page


if __name__ == "__main__":
    print(build())
