#!/usr/bin/env python3
"""Report das máquinas r3d (reports/design/maquinas_r3d/index.html): antes × depois, animações em CSS, eólico, cena da
base, desvios de contrato e "pro Dev integrar".

    python3 tools/sprites/machines_r3d_report.py

Roda o gerador (machines_r3d.py), copia os "antes" (o jogo de hoje) pra before/ e monta as cenas e a página.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import machines_r3d as M  # noqa: E402

ROOT = M.ROOT
SPR = ROOT / "assets" / "sprites"
BASE = M.OUT.parent                 # reports/design/maquinas_r3d
PEND = M.OUT
BEFORE = BASE / "before"
VIEW = BASE / "view"

# nome, rótulo, quadros (1 = parado), fps do jogo hoje (None = o jogo não anima)
ITEMS = [
    ("machine_o2", "Gerador de O₂ nv.1", 1), ("machine_o2_t2", "Gerador de O₂ nv.2", 1),
    ("machine_heater", "Aquecedor nv.1", 1), ("machine_heater_t2", "Aquecedor nv.2", 1),
    ("machine_melter", "Derretedor nv.1", 1), ("machine_melter_t2", "Derretedor nv.2", 1),
    ("machine_drill", "Drill automática (2×2)", 4), ("solar_panel", "Painel solar", 1),
    ("lamp", "Luminária", 1), ("lamp_t2", "Luminária forte", 1),
    ("drone_station", "Estação de drones (2×2)", 1), ("drone", "Drone", 4),
    ("pod", "Cápsula / base", 1), ("terminal", "Terminal de parede", 1),
]
# animações que só o freela tem: arquivo, rótulo, quadros, tamanho do quadro, fps sugerido
NEW_ANIMS = [
    ("anim_machine_o2", "Gerador de O₂ nv.1", 4, (40, 56)), ("anim_machine_o2_t2", "Gerador de O₂ nv.2", 4, (40, 64)),
    ("anim_machine_heater", "Aquecedor nv.1", 4, (40, 56)), ("anim_machine_heater_t2", "Aquecedor nv.2", 4, (40, 64)),
    ("anim_machine_melter", "Derretedor nv.1", 4, (40, 56)), ("anim_machine_melter_t2", "Derretedor nv.2", 4, (40, 64)),
    ("anim_solar_panel", "Painel solar", 4, (32, 40)), ("anim_terminal", "Terminal", 4, (32, 32)),
    ("anim_drone_station", "Estação de drones", 4, (64, 72)), ("anim_pod", "Cápsula", 4, (64, 72)),
]
NEW_FPS = 5
DRILL_FPS, DRONE_FPS = 8, 15
OUTLINE = (0x1b, 0x16, 0x30)


def load(p):
    return Image.open(p).convert("RGBA")


def size(p):
    with Image.open(p) as im:
        return im.size


def bbox(im):
    a = np.array(im.convert("RGBA"))[:, :, 3] > 0
    ys, xs = np.nonzero(a)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def first_frame(im, n):
    return im.crop((0, 0, im.width // n, im.height))


# ---- cenas --------------------------------------------------------------------------------------------------------
def ground(region, stage, w, h, seed):
    import regions_v9 as V9
    return V9.ground_patch(region, stage, w, h, seed)


def put(objs, img, fx, fy):
    objs.append((fy, img, fx - img.width // 2, fy - img.height))


def compose(bg, objs):
    for _, img, x, y in sorted(objs, key=lambda o: o[0]):
        bg.alpha_composite(img, (x, y))
    return bg


def sheet_frame(path, n, f):
    im = load(path)
    w = im.width // n
    return im.crop((f * w, 0, f * w + w, im.height))


def base_scene(stage, new=True, frame=0):
    """Recorte 480×270 da base: cápsula, as máquinas (nv.1 e nv.2), drill, estação com os 4 drones nos pads,
    luminárias, baús azuis e o Explorador."""
    bg = ground("plateau", stage, 480, 270, 21)
    src = PEND if new else BEFORE
    o = []

    def S(n, fr=0, nf=1):
        return sheet_frame(src / f"{n}.png", nf, fr) if nf > 1 else load(src / f"{n}.png")
    put(o, S("pod"), 84, 118)
    put(o, S("machine_o2"), 150, 112)
    put(o, S("machine_heater"), 196, 112)
    put(o, S("machine_melter"), 242, 112)
    put(o, S("machine_o2_t2"), 150, 176)
    put(o, S("machine_heater_t2"), 196, 176)
    put(o, S("machine_melter_t2"), 242, 176)
    put(o, S("solar_panel"), 296, 112)
    put(o, S("solar_panel"), 330, 112)
    put(o, S("lamp"), 112, 176)
    put(o, S("lamp_t2"), 270, 176)
    put(o, S("machine_drill", frame, 4), 336, 226)
    # estação 2×2 com os 4 drones nos slots (DRONE_PADS, relativos ao canto do PNG; o drone é blitado em (x-8, y-8))
    st = S("drone_station")
    sx, sy = 420 - st.width // 2, 140 - st.height
    put(o, st, 420, 140)
    for i, (px, py) in enumerate(((18, 44), (46, 44), (25, 55), (53, 55))):
        d = S("drone", 0, 4)
        o.append((140 + (1 if i > 1 else 0) * 3 + 1, d, sx + px - 8, sy + py - 8))
    chest = load(SPR / "chest.png")
    chest_o = load(SPR / "chest_open.png")
    for i, x in enumerate((60, 96, 132)):
        put(o, chest_o if i == 1 else chest, x, 236)
    put(o, load(SPR / "player_idle_down.png").crop((0, 0, 32, 32)), 190, 246)
    return compose(bg, o)


def scenes():
    base_scene("arid", new=False).save(BASE / "cena_base_arid_antes.png")
    base_scene("arid").save(BASE / "cena_base_arid.png")
    base_scene("green").save(BASE / "cena_base_green.png")
    base_scene("green", new=False).save(BASE / "cena_base_green_antes.png")


# ---- HTML ---------------------------------------------------------------------------------------------------------
KEYFRAMES: set[int] = set()


def anim_div(rel, n, fw, fh, k, fps, extra=""):
    """Tira horizontal de n quadros fw×fh animada em CSS (steps), ampliada k vezes."""
    end = n * fw * k
    KEYFRAMES.add(end)
    return (f'<div class="sp" style="width:{fw * k}px;height:{fh * k}px;background-image:url(\'{rel}\');'
            f'background-size:{end}px {fh * k}px;animation:play{end} {n / fps:.3f}s steps({n}) infinite;{extra}"></div>')


def fig(rel, k, cap, w=None, h=None):
    if w is None:
        w, h = size(BASE / rel)
    return (f'<figure><div class="chk"><img src="{rel}" width="{w * k}" height="{h * k}" alt=""></div>'
            f'<figcaption>{cap}</figcaption></figure>')


def real_row(names, folder):
    out = []
    for n in names:
        w, h = size(folder / f"{n}.png")
        out.append(f'<img src="{folder.name}/{n}.png" width="{w}" height="{h}" alt="">')
    return " ".join(out)


def build():
    specs = M.build()
    ok, bad = M.check(specs)
    BEFORE.mkdir(parents=True, exist_ok=True)
    for n, _, _ in ITEMS:
        shutil.copy(SPR / f"{n}.png", BEFORE / f"{n}.png")
    scenes()

    # --- antes × depois
    pairs = []
    dev_rows = []
    for n, label, frames in ITEMS:
        a, b = load(BEFORE / f"{n}.png"), load(PEND / f"{n}.png")
        fa, fb = first_frame(a, frames), first_frame(b, frames)
        k = 8 if fa.width <= 20 else (6 if fa.width <= 40 else 4)
        wa, ha = a.size
        wb, hb = b.size
        extra = ' · tira de 4 quadros (1º quadro ampliado)' if frames > 1 else ''
        VIEW.mkdir(exist_ok=True)
        fa.save(VIEW / f"{n}_antes.png")
        fb.save(VIEW / f"{n}_depois.png")
        pairs.append(f"""<div class="pair"><h3>{label} · <code>{n}.png</code> · {wb}×{hb}{extra}</h3><div class="ab">
<figure><div class="chk"><img src="view/{n}_antes.png" width="{fa.width * k}" height="{fa.height * k}" alt=""></div><figcaption>hoje no jogo</figcaption></figure>
<figure><div class="chk"><img src="view/{n}_depois.png" width="{fb.width * k}" height="{fb.height * k}" alt=""></div><figcaption>freela (agora)</figcaption></figure>
<figure><div class="chk"><img src="view/{n}_antes.png" width="{fa.width}" height="{fa.height}" alt=""> <img src="view/{n}_depois.png" width="{fb.width}" height="{fb.height}" alt=""></div><figcaption>tamanho real (1×): hoje · freela</figcaption></figure>
</div></div>""")
        ba, bb_ = bbox(fa), bbox(fb)
        same = (a.size == b.size)
        dev_rows.append((n, label, a.size, b.size, same, ba, bb_, fa.size))

    # --- animações que o jogo já usa
    anim_now = f"""<div class="anim">
<figure><div class="chk">{anim_div("before/machine_drill.png", 4, 64, 80, 3, DRILL_FPS)}</div><figcaption>drill · hoje · {DRILL_FPS} fps</figcaption></figure>
<figure><div class="chk">{anim_div("pendentes/machine_drill.png", 4, 64, 80, 3, DRILL_FPS)}</div><figcaption>drill · freela · {DRILL_FPS} fps</figcaption></figure>
<figure><div class="chk">{anim_div("before/drone.png", 4, 16, 16, 10, DRONE_FPS)}</div><figcaption>drone · hoje · {DRONE_FPS} fps</figcaption></figure>
<figure><div class="chk">{anim_div("pendentes/drone.png", 4, 16, 16, 10, DRONE_FPS)}</div><figcaption>drone · freela · {DRONE_FPS} fps</figcaption></figure>
</div>"""
    new_figs = []
    for n, label, nf, (fw, fh) in NEW_ANIMS:
        k = 5 if fw <= 40 else 3
        new_figs.append(f'<figure><div class="chk">{anim_div(f"pendentes/anim/{n}.png", nf, fw, fh, k, NEW_FPS)}</div>'
                        f'<figcaption>{label}<br><code>anim/{n}.png</code> · {nf * fw}×{fh} · NOVO</figcaption></figure>')
    anim_new = '<div class="anim">' + "".join(new_figs) + "</div>"

    # --- eólico
    wf = f"""<div class="anim">
<figure><div class="chk"><img src="pendentes/eolico/wind_turbine.png" width="192" height="384" alt=""></div><figcaption><code>wind_turbine.png</code> · 32×64 (1 tile)</figcaption></figure>
<figure><div class="chk">{anim_div("pendentes/eolico/anim_wind_turbine.png", 8, 32, 64, 6, 8)}</div><figcaption>girando · 8 quadros · 8 fps</figcaption></figure>
<figure><div class="chk"><img src="pendentes/eolico/icon_wind.png" width="128" height="128" alt=""></div><figcaption><code>icon_wind.png</code> · 16×16</figcaption></figure>
<figure><div class="chk" style="padding:18px"><img src="pendentes/eolico/wind_turbine.png" width="32" height="64" alt=""> <img src="pendentes/eolico/icon_wind.png" width="16" height="16" alt=""></div><figcaption>tamanho real (1×)</figcaption></figure>
</div>"""

    # --- tabelas
    def bb_txt(b):
        return f"x {b[0]}–{b[2]} · y {b[1]}–{b[3]}"
    size_rows = "".join(
        f"<tr><td><code>{n}.png</code></td><td>{a[0]}×{a[1]}</td><td>{b[0]}×{b[1]}</td>"
        f"<td class=\"{'ok' if same else 'bad'}\">{'igual' if same else 'DIFERENTE'}</td>"
        f"<td>{bb_txt(ba)}</td><td>{bb_txt(bb_)}</td><td>{'' if ba[3] == bb_[3] else '<b>pé ' + str(bb_[3] - ba[3]) + ' px</b>'}</td></tr>"
        for (n, label, a, b, same, ba, bb_, fs) in dev_rows)
    px_rows = "".join(f'<li class="okl"><code>{n}</code></li>' for n in ok) + "".join(
        f'<li class="bad"><code>{n}</code> ({d} px diferentes)</li>' for n, d in bad)

    ks = "".join(f"@keyframes play{e}{{from{{background-position-x:0}}to{{background-position-x:-{e}px}}}}\n" for e in sorted(KEYFRAMES))

    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Máquinas r3d (o freela) · v1.0</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;--bad:#ff6a55;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1300px;margin:0 auto;padding:44px 0 80px}}
.eyebrow{{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}}
h1{{font:600 44px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}}h2{{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}}
h3{{font:600 16px "Pixelify Sans",monospace;margin:0 0 8px}}code{{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}}
p,li{{color:var(--muted)}}li b,p b{{color:var(--fg)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--rust);padding:12px 18px;max-width:1050px}}
.v2>b{{font:13px "Silkscreen",monospace;color:var(--rust)}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
.chk img,.sp{{image-rendering:pixelated}}img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px}}
.pairs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
.pair{{background:var(--panel);border:1px solid var(--line);padding:14px}}.ab{{display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}@media(max-width:1000px){{.grid2{{grid-template-columns:1fr}}}}
img.px{{width:100%;height:auto;border:1px solid var(--line);display:block}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}}
.new{{border-left-color:var(--ok)}}
.anim{{display:flex;gap:28px;flex-wrap:wrap;align-items:flex-end}}
.sp{{background-repeat:no-repeat}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid var(--line);padding:5px 8px;text-align:left;color:var(--muted)}}th{{background:#241b17;color:var(--fg)}}
td.ok,li.okl{{color:var(--ok)}}td.bad,li.bad{{color:var(--bad)}}
ul.cols{{columns:3;list-style:none;padding:0;font-size:13px}}
{ks}</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v1.0 · M4 do v0.4 · máquinas do "freela" trazidas iguais (espera o ok do dono)</div>
<h1>Máquinas r3d · o freela no jogo</h1>
<div class="v2"><b>v1.0 · o que mudou</b><ul>
<li><b>Não é redesenho.</b> O dono aprovou as máquinas da sessão experimental como estão. O código foi <b>portado</b> pra
<code>tools/sprites/machines_r3d.py</code> (autocontido, depende só do <code>r3d.py</code> do repo) e gera
<b>{len(ok)} de {len(ok) + len(bad)} PNGs idênticos pixel a pixel</b> aos do freela.</li>
<li>14 sprites do contrato (mesmo nome, tamanho e âncora de hoje): O₂, aquecedor e derretedor nv.1 e nv.2, drill, painel
solar, luminária e luminária forte, estação de drones, drone, cápsula e terminal.</li>
<li>10 tiras de animação que só o freela tem (<b>novo, o Dev liga depois</b>) e o <b>gerador eólico</b> pronto, ainda
<b>fora do jogo</b>. A fornalha não entra.</li>
<li>Baú, caixa de saque e contêiner ficam como estão (o r3d azul já foi aprovado e promovido).</li>
<li>Estilo aproveitado do freela (nada de referência externa nova): corpo bege/branco, faixas laranja, LED, base de metal,
nv.2 mais robustas com dourado, contorno <code>#1b1630</code>, volume calculado pelo motor r3d.</li>
</ul></div>

<h2>Antes (o jogo de hoje) × depois (o freela)</h2>
<div class="pairs">{''.join(pairs)}</div>

<h2>Animações que o jogo já usa</h2>
<p>Drill (4 quadros de 64×80, recorte do <code>drill_frame</code>) e drone (4 quadros de 16×16). Mesmo formato do contrato.</p>
{anim_now}

<h2>Animações novas: o Dev liga depois</h2>
<p>Hoje o jogo só anima a drill e o drone. As máquinas do freela têm 4 quadros de LED, ventoinha, grelha, água etc. Cada
tira tem 4 quadros lado a lado do tamanho do sprite parado; o quadro 0 é o PNG parado do contrato. Mostradas a
{NEW_FPS} fps (sugestão; o jogo decide).</p>
{anim_new}

<h2>Gerador eólico · pronto, ainda fora do jogo</h2>
<div class="box new"><b>Não entra no jogo agora</b>: o dono põe depois. Os arquivos estão em
<code>pendentes/eolico/</code>, separados de propósito pra ninguém copiar junto com o contrato. Eixo vertical, 3 pás
helicoidais, 32×64 (1 tile), âncora no centro da base. 8 quadros = 120° de giro (as 3 pás são iguais, então fecha sem
emenda). Ícone 16×16 incluído.</div><br>
{wf}

<h2>Na base, com as máquinas novas, o baú azul e o Explorador</h2>
<div class="grid2">
<figure><img class="px" src="cena_base_arid_antes.png" alt=""><figcaption><b>antes</b> · Árido, as máquinas de hoje</figcaption></figure>
<figure><img class="px" src="cena_base_arid.png" alt=""><figcaption><b>depois</b> · Árido, o freela</figcaption></figure>
<figure><img class="px" src="cena_base_green_antes.png" alt=""><figcaption><b>antes</b> · Verde</figcaption></figure>
<figure><img class="px" src="cena_base_green.png" alt=""><figcaption><b>depois</b> · Verde</figcaption></figure>
</div>
<p>Recortes 480×270 (metade da tela do jogo) ampliados 2×, só com sprites, ordenados pelo pé como o jogo desenha. Cada
fileira é o nv.1 (em cima) e o nv.2 (embaixo). A estação leva os 4 drones nos <code>DRONE_PADS</code> de hoje
((18,44) (46,44) (25,55) (53,55)).</p>

<h2>Desvios de contrato</h2>
<div class="box"><b>Tamanho: nenhum desvio.</b> Os 14 sprites do freela têm exatamente o mesmo tamanho dos que estão em
<code>assets/sprites/</code> e o que a bíblia §6 / §8 / §9 pede. Âncoras também iguais (centro da base do PNG), então é
troca de arquivo, sem mexer em <code>config.py</code>.</div>
<p>O que muda é <b>onde a arte ocupa dentro do PNG</b> (caixa dos pixels opacos). Isso não quebra nada (o jogo ancora
pelo PNG inteiro), mas o Dev deve olhar no smoke: onde o pé sobe/desce o objeto parece flutuar ou afundar uns px.</p>
<table><tr><th>arquivo</th><th>hoje</th><th>freela</th><th>tamanho</th><th>pixels opacos hoje (1º quadro)</th><th>pixels opacos freela</th><th>pé</th></tr>
{size_rows}</table>
<ul>
<li><b>Pé (última linha opaca)</b>: onde a coluna "pé" aparece, a base do freela fica mais acima/abaixo que a de hoje.
Se incomodar, o ajuste é de arte (eu desloco no gerador), não de código.</li>
<li><b>Estação</b>: o freela é mais baixa no topo (a torre sobe até y=11; a de hoje vai até y=0), com os mesmos 2 pads
H em (18,44) e (46,44). Os slots 3 e 4 ((25,55) e (53,55)) caem na frente do deck; confira na cena acima.</li>
<li><b>Drill</b>: o indicador de enchimento continua em <code>(48, 47, 7, 12)</code> (<code>DRILL_FILL_RECT</code>),
desenhado no próprio PNG como hoje.</li>
<li><b>Luminárias</b>: a luz é desenhada pelo jogo no tile, não depende do sprite. O vidro aceso do freela fica uns 2 px
mais baixo no PNG que o de hoje (centro do vidro ~ (7,16)).</li>
<li><b>Terminal</b>: fica do jeito 2D de sempre (o freela não o refez em 3D), mas é outro desenho: placa bege com tela
verde.</li>
<li><b>Baús</b> e <b>caixas</b>: o freela tem os dele (<code>chest.png</code>), mas o jogo já usa o r3d azul aprovado:
<b>não trazido de propósito</b>.</li>
<li><b>Broca de mão</b> (<code>drill_*.png</code> da raiz do freela): não é máquina e já foi tratada na sua própria
rodada (<code>reports/design/drill_hand_*</code>). Fora deste lote.</li>
</ul>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Drop-in:</b> os 14 PNGs de <code>pendentes/</code> têm o mesmo nome e tamanho dos de <code>assets/sprites/</code>.
Na promoção, copia só <code>pendentes/*.png</code> (não as pastas <code>anim/</code> e <code>eolico/</code>).</li>
<li><b>Âncora:</b> centro da base do PNG (como hoje). 1 tile: nv.1 40×56, nv.2 40×64 (passam 4 px de cada lado do tile),
solar 32×40, luminária 16×32, terminal 32×32 na parede. 2×2: drill 64×80 (4 quadros) e estação 64×72, cápsula 64×72.</li>
<li><b>Quadros:</b> <code>machine_drill.png</code> 256×80 = 4×(64×80), recorte <code>(64·f, 0, 64, 80)</code>;
<code>drone.png</code> 64×16 = 4×(16×16). Os dois já são animados pelo jogo ({DRILL_FPS} e {DRONE_FPS} fps). O quadro 0
dos outros é o PNG parado.</li>
<li><b>Animações novas</b> (<code>pendentes/anim/</code>): tiras de 4 quadros lado a lado, tamanho do quadro = tamanho do
sprite parado. Pra ligar é o mesmo recorte do <code>drill_frame</code>. Rodar só com a máquina ligada/com energia é
decisão do jogo.</li>
<li><b>Drones:</b> os 4 slots pousam nos <code>DRONE_PADS</code> de hoje, sem mudar.</li>
<li><b>Ordem de desenho:</b> igual a hoje (ordenado pelo pé; sem sombra no sprite, como o r3d azul: se quiser a sombra de
chão, o jogo põe).</li>
<li><b>Contorno do alvo do E</b> e <b>máquina submersa</b> usam a silhueta opaca: funcionam sem mudança.</li>
<li><b>Eólico:</b> <code>pendentes/eolico/</code> (32×64, 8 quadros de 32×64 em 256×64, ícone 16×16). Fora do jogo até o dono pedir.</li>
<li><b>Regerar:</b> <code>python3 tools/sprites/machines_r3d.py</code> (determinístico);
<code>--check</code> compara pixel a pixel com o freela do Desktop; este report sai de
<code>python3 tools/sprites/machines_r3d_report.py</code>.</li>
</ul></div>

<h2>Conferência pixel a pixel com o freela</h2>
<p><b>{len(ok)} de {len(ok) + len(bad)}</b> bateram (RGBA idêntico). {'Nenhum diferente.' if not bad else 'Diferentes marcados em vermelho.'}</p>
<ul class="cols">{px_rows}</ul>
</div></body></html>
"""
    (BASE / "index.html").write_text(html, encoding="utf-8")
    return BASE / "index.html"


if __name__ == "__main__":
    print(build())
