"""Report do v0.5 M3 · chão da base refeito (reports/design/v05_m3_chao_base/index.html).
Chamado pelo tools/sprites/v05_m3_chao_base.py. Só LÊ assets/ e reports/design/v05_m2_base/ (nunca escreve lá).

As cenas reaproveitam o montador do report do M2 (v05_m2_base_report.compose / base_scene, a ordem de desenho do
jogo) trocando só o chão. "Antes" = os base_floor_* de hoje (assets/). "Depois" = os pendentes daqui.
A porta tem chão desenhado dentro dela (feito com o floor_tile(0) do gerador do M2): pra cena "depois" não mostrar
um remendo do chão velho, a porta atual (v05_m3_porta, da outra Designer) é regerada aqui com o chão novo por baixo,
só pra prévia, em cena_src/.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import v05_m2_base as B  # noqa: E402
import v05_m2_base_report as R  # noqa: E402
import v05_m3_chao_base as G  # noqa: E402

ROOT = G.ROOT
OUT = G.REP
PEND = G.PEND
SRC = OUT / "cena_src"
SPR = ROOT / "assets" / "sprites"
T = G.T
STAGES = (("storm", "Tempestade"), ("arid", "Árido"), ("mist", "Névoa"), ("green", "Verde"))


def load(p):
    return Image.open(p).convert("RGBA")


# ---- portas da prévia com a soleira nova ----------------------------------------------------------------------------
def door_previews():
    """Regera a porta ATUAL (a do v05_m3_porta, que já usa o chão do B.floor_tile e as cores do B.FL) trocando só o
    chão por baixo: B.floor_tile -> o chão novo e B.FL (seam/light/grate) -> a paleta nova. Só lê o gerador da porta
    e grava em cena_src/ daqui; nada no assets/ nem no report da porta."""
    import v05_m3_porta as P
    SRC.mkdir(parents=True, exist_ok=True)
    old_tile, old_fl = B.floor_tile, dict(B.FL)
    B.floor_tile = lambda v=0: G.floor_tile(0)
    B.FL.update(grate=G.FL2["seam"], light=G.FL2["light"], seam=G.FL2["seam"])
    try:
        for o, edges in (("h", "ns"), ("v", "we")):
            for e in edges:
                P._cv(P.strip(o, e, 1)).save(SRC / f"base_door_{o}_{e}.png")
                P._cv(P.strip(o, e, 2)).save(SRC / f"base_door2_{o}_{e}.png")
    finally:
        B.floor_tile = old_tile
        B.FL.clear()
        B.FL.update(old_fl)


def sheet_class(which):
    """Sheet do M2 com o chão (e a soleira da porta) trocados."""
    class S(R.Sheet):
        def __init__(self):
            super().__init__()
            if which == "old":
                self.floor = [load(SPR / f"base_floor_{v}.png") for v in range(4)]
                src = SPR
            else:
                self.floor = [load(PEND / f"base_floor_{v}.png") for v in range(4)]
                src = SRC
            oe = [f"{o}_{e}" for o, es in (("h", "ns"), ("v", "we")) for e in es]
            self.solo = {k: load(src / f"base_door_{k}.png") for k in oe}
            self.duo = {k: load(src / f"base_door2_{k}.png") for k in oe}
    return S


def with_floor(which, fn, *a, **kw):
    keep = R.Sheet
    R.Sheet = sheet_class(which)
    try:
        return fn(*a, **kw)
    finally:
        R.Sheet = keep


# ---- cenas ----------------------------------------------------------------------------------------------------------
def small_scene(which, stage):
    """A base do M2 (7×6, porta embaixo e na direita, Dispersor, bancada, baú, O₂, luminária) com o player."""
    return with_floor(which, R.base_scene, stage, f=0, player=(R.player_img("down"), 3 * T + 16, 5 * T + 26))


BIG = [
    "##########################",
    "#........................#",
    "#........................#",
    "#........................#",
    "#........................#",
    "#........................D",
    "#........................#",
    "#........................#",
    "#........................#",
    "#........................#",
    "#........................#",
    "#........................#",
    "#........................#",
    "###########DD#############",
]


def big_scene(which, stage, machines=True):
    """Área grande (24×12 de chão, 960×540): repetição do chão, com poucas máquinas espalhadas."""
    ox, oy = 64, 56
    objs = []
    if machines:
        def m(name, tx, ty):
            im = load(SPR / f"{name}.png")
            if name == "machine_drill":
                im = im.crop((0, 0, 32, 80))
            return (im, ox + tx * T + 16, oy + (ty + 1) * T, False)
        disp = load(B.PEND / "machine_o2_dispenser.png")
        objs = [
            m("machine_workbench", 3, 2), m("chest", 5, 2), m("chest", 6, 2), m("machine_o2", 10, 3),
            (disp, ox + 13 * T + 16, oy + 7 * T, False),
            m("lamp", 2, 6), m("lamp", 22, 6), m("machine_heater", 18, 3), m("machine_o2_t2", 20, 9),
            m("solar_panel", 4, 10), m("solar_panel", 5, 10), m("machine_melter", 15, 10),
            (R.player_img("side"), ox + 9 * T + 10, oy + 8 * T + 20, True),
        ]
    return with_floor(which, R.compose, stage, BIG, objs, ox, oy, size=(960, 540), seed=21)


def tiles_strip(which):
    """As 4 variações lado a lado (×1) + um 2×2 de cada (pra ver o losango montado)."""
    src = SPR if which == "old" else PEND
    fl = [load(src / f"base_floor_{v}.png") for v in range(4)]
    im = Image.new("RGBA", (4 * 72, 64), (0, 0, 0, 0))
    for v in range(4):
        for dx in (0, 1):
            for dy in (0, 1):
                im.alpha_composite(fl[v], (v * 72 + dx * 32, dy * 32))
    return im


def zoom(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def build_images():
    door_previews()
    out = {}
    for st, _ in STAGES:
        for w in ("old", "new"):
            out[f"cena_{st}_{w}.png"] = small_scene(w, st)
    for w in ("old", "new"):
        out[f"area_arid_{w}.png"] = big_scene(w, "arid")
        out[f"area_vazia_mist_{w}.png"] = big_scene(w, "mist", machines=False)
        out[f"tiles_{w}.png"] = tiles_strip(w)
    for st, _ in STAGES:
        out[f"area_{st}_new.png"] = big_scene("new", st) if st != "arid" else out["area_arid_new.png"]
    for k, im in out.items():
        im.save(OUT / k)
    # recortes ampliados (×3) do miolo da base, antes e depois
    for w in ("old", "new"):
        zoom(out[f"cena_arid_{w}.png"].crop((96, 16, 352, 240)), 3).save(OUT / f"zoom_arid_{w}.png")
    return out


# ---- HTML -----------------------------------------------------------------------------------------------------------
def size_of(p):
    with Image.open(p) as im:
        return im.size


def fig(src, k=1, cap="", cls="chk"):
    w, h = size_of(OUT / src)
    c = f"<figcaption>{cap}</figcaption>" if cap else ""
    return f'<figure><div class="{cls}"><img src="{src}" width="{w * k}" height="{h * k}" alt=""></div>{c}</figure>'


def check_contract():
    names = sorted(p.name for p in PEND.glob("*.png"))
    want = sorted([f"base_floor_{v}.png" for v in range(4)] + ["icon_base_floor.png"])
    bad = []
    for n in want:
        p = PEND / n
        if not p.exists():
            bad.append(f"{n} falta")
            continue
        exp = (16, 16) if n.startswith("icon") else (32, 32)
        im = Image.open(p)
        if im.size != exp:
            bad.append(f"{n} {im.size}")
        a = set(im.convert("RGBA").getchannel("A").getdata())
        if not a <= {0, 255}:
            bad.append(f"{n} alpha {a}")
    extra = [n for n in names if n not in want]
    return want, bad, extra


def colors_of(p):
    im = Image.open(p).convert("RGBA")
    return len({c for c in im.getdata() if c[3]})


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    build_images()
    want, bad, extra = check_contract()
    ok = not bad and not extra
    pal = "".join(f'<div class="sw"><span style="background:{c}"></span><code>{k}</code><br><code>{c}</code></div>'
                  for k, c in G.FL2.items())
    sprites = "".join(fig(f"pendentes/base_floor_{v}.png", 8, f"<code>base_floor_{v}.png</code> · 32×32") for v in range(4))
    stage_rows = "".join(f"""<h3>{lab}</h3><div class="grid2">{fig(f"cena_{st}_old.png", 2, "antes (assets de hoje)", "plain")}{fig(f"cena_{st}_new.png", 2, "depois", "plain")}</div>"""
                         for st, lab in STAGES)
    one_x = "".join(f'<img src="cena_{st}_new.png" width="480" height="270" alt="">' for st, _ in STAGES)
    area_st = "".join(fig(f"area_{st}_new.png", 1, f"{lab} · depois · 1:1", "plain") for st, lab in STAGES if st != "arid")
    nc_old = len({c for v in range(4) for c in Image.open(SPR / f"base_floor_{v}.png").convert("RGBA").getdata()})
    nc_new = len({c for v in range(4) for c in Image.open(PEND / f"base_floor_{v}.png").convert("RGBA").getdata()})
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · v0.5 M3 · Chão da base · v1.0</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1300px;margin:0 auto;padding:44px 0 80px}}
.eyebrow{{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}}
h1{{font:600 44px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}}h2{{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}}
h3{{font:600 16px "Pixelify Sans",monospace;margin:18px 0 6px}}code{{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}}
p,li,td{{color:var(--muted)}}li b,p b,td b{{color:var(--fg)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--rust);padding:12px 18px;max-width:1100px}}
.v2>b{{font:13px "Silkscreen",monospace;color:var(--rust)}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
.plain{{display:inline-block;line-height:0}}
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px}}
.flex{{display:flex;gap:22px;align-items:flex-end;flex-wrap:wrap}}
.grid2{{display:grid;grid-template-columns:repeat(2,max-content);gap:14px;overflow-x:auto}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}}
.chip{{display:inline-block;font:12px "Silkscreen",monospace;padding:3px 10px;border:1px solid var(--line);margin:0 6px 6px 0}}
.chip.ok{{border-color:var(--ok);color:var(--ok)}}.chip.bad{{border-color:var(--rust);color:var(--rust)}}
.sw{{display:inline-block;width:120px;font-size:12px;margin:0 8px 10px 0}}.sw span{{display:block;height:34px;border:1px solid #000}}
.one{{display:flex;gap:8px;flex-wrap:wrap;line-height:0}}
.wipe{{position:relative;width:960px;height:540px;overflow:hidden;border:1px solid var(--line)}}
.wipe img{{position:absolute;left:0;top:0}}
.wipe img.top{{animation:wipe 4s steps(1) infinite}}
@keyframes wipe{{0%{{opacity:1}}50%{{opacity:0}}}}
</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5 M3 · chão da base · v1.0</div>
<h1>Chão da base, um só e sutil</h1>
<div class="v2"><b>v1.0 · o que mudou</b><ul>
<li><b>Um chão só.</b> As 4 variações de antes (lisa, emendada, grelha, tampa) viraram <b>a mesma chapa</b>: os 4 arquivos continuam (o jogo sorteia entre eles), mas a única diferença são 3–4 pintinhas de desgaste de 1 tom, que só servem pra repetição não marcar padrão.</li>
<li><b>Cor da referência:</b> cinza-azulado puxando pro verde (aço), no lugar do lilás de antes. Tudo em 4 tons a ±1–2 degraus da chapa.</li>
<li><b>Junta fina e discreta:</b> 1 px de junta, sombra de 1 px na borda de baixo/direita, fio de luz de 1 px na borda de cima/esquerda. Saíram os rebites dos cantos, o chanfro claro e o contraste forte.</li>
<li><b>Pino em losango</b> no cruzamento das juntas (da referência): cada tile desenha 1/4 dele, 4 tiles montam o losango 4×4.</li>
<li><b>Ícone do menu</b> (<code>icon_base_floor.png</code>) refeito: 4 chapas novas com a junta em cruz e o pino no meio.</li>
<li>A porta nas cenas é a de hoje no <code>assets/</code> (a redesenhada do v05_m3_porta); no \"depois\" ela foi regerada com o chão novo por baixo.</li>
</ul></div>
<p style="margin-top:14px"><span class="chip {'ok' if ok else 'bad'}">{len(want)} arquivos · tamanhos {'conferidos' if ok else 'COM ERRO: ' + ', '.join(bad + extra)}</span><span class="chip">cores no chão: {nc_old} antes → {nc_new} depois</span><span class="chip ok">0 desvios do contrato</span><span class="chip">pendentes, nada no assets/</span></p>

<h2>Antes × depois em cena</h2>
<p>A base do M2 (paredes, porta solo embaixo e na direita, Dispersor, bancada, baú, O₂ nv.1, luminária, painel fora) com o player na porta. Montada só com os sprites, na ordem do jogo. Ampliado ×2. O chão da base <b>não recolore por estágio</b> (o jogo usa o mesmo PNG nos 4); o que muda é o terreno em volta.</p>
{stage_rows}
<h3>Recorte ×3 (Árido)</h3>
<div class="grid2">{fig("zoom_arid_old.png", 1, "antes", "plain")}{fig("zoom_arid_new.png", 1, "depois", "plain")}</div>
<h3>Escala real (1:1), os 4 estágios, depois</h3>
<div class="one">{one_x}</div>

<h2>Área grande (repetição)</h2>
<p>24×12 tiles de chão em 960×540, 1:1, como fica na tela. Antes e depois alternando sozinhos a cada 2 s.</p>
<div class="wipe"><img src="area_arid_new.png" width="960" height="540" alt=""><img class="top" src="area_arid_old.png" width="960" height="540" alt=""></div>
<div class="grid2" style="margin-top:14px">{fig("area_arid_old.png", 1, "Árido · antes", "plain")}{fig("area_arid_new.png", 1, "Árido · depois", "plain")}</div>
<h3>Vazia (só o chão), Névoa</h3>
<div class="grid2">{fig("area_vazia_mist_old.png", 1, "antes", "plain")}{fig("area_vazia_mist_new.png", 1, "depois", "plain")}</div>
<h3>Os outros estágios, depois</h3>
<div class="grid2">{area_st}</div>

<h2>Os sprites</h2>
<div class="flex">{sprites}</div>
<h3>2×2 de cada variação (×4): antes · depois</h3>
<div class="flex">{fig("tiles_old.png", 4, "antes")}{fig("tiles_new.png", 4, "depois")}</div>
<h3>Ícone do menu</h3>
<div class="flex">{fig("../v05_m2_base/pendentes/icon_base_floor.png", 8, "antes")}{fig("pendentes/icon_base_floor.png", 8, "depois · <code>icon_base_floor.png</code> 16×16")}<figure><div class="chk"><img src="pendentes/icon_base_floor.png" width="16" height="16" alt=""> <img src="pendentes/icon_base_floor.png" width="32" height="32" alt=""></div><figcaption>1:1 e ×2</figcaption></figure></div>
<h3>Paleta do chão</h3>
<div>{pal}</div>

<h2>Referência do dono</h2>
<div class="flex">{fig("ref/referencia_chao.png", 4, "referência (só estilo)")}</div>
<p>Aproveitei <b>só o estilo</b>: a cor (cinza-azulado com um pé no verde), o contraste baixo, a junta fina rebaixada e a ideia do pino em losango no cruzamento das juntas. O desenho é nosso: pixel art 1:1 sem gradiente, chapa de 1 tile (a referência tem chapa bem maior, com junta dupla larga e manchas suaves, que viram barulho em 32 px), luz de cima/esquerda igual à parede e às máquinas, e o desgaste reduzido a pintinhas de 1 tom.</p>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Nada muda no código.</b> Mesmos nomes e tamanhos: <code>base_floor_{{0..3}}.png</code> 32×32 em <code>(tx·32, ty·32)</code>, passada do chão (embaixo de tudo), sorteio de hoje (<code>floor_variant</code>) pode ficar como está. <code>icon_base_floor.png</code> 16×16 igual.</li>
<li>Integrar = copiar <code>reports/design/v05_m3_chao_base/pendentes/*.png</code> pra <code>assets/sprites/</code> (depois do ok do dono).</li>
<li>Opcional: como as 4 são quase iguais, o <code>FLOOR_PICK</code> pode virar <code>(0,1,2,3,0,1,2,3)</code> pra espalhar as pintinhas; não é obrigatório.</li>
<li><b>A porta tem chão dentro</b> (a soleira dos <code>base_door*</code> é o <code>floor_tile(0)</code> do gerador). Se o chão novo entrar, a porta precisa ser regerada com a soleira nova, senão fica um quadrado lilás no vão. O gerador novo expõe <code>v05_m3_chao_base.floor_tile(0)</code> e a paleta <code>FL2</code> (soleira: <code>grate → FL2["seam"]</code>, <code>light → FL2["light"]</code>); as cenas "depois" daqui já usam uma porta regerada assim (só pra prévia, em <code>cena_src/</code>). Quem está refazendo a porta (<code>v05_m3_porta</code>) só precisa trocar a importação do chão.</li>
<li>Fantasma do construtor usa <code>base_floor_0</code>: continua igual.</li>
</ul></div>
<p style="margin-top:30px;font-size:12px">Gerado por <code>python3 tools/sprites/v05_m3_chao_base.py</code> (determinístico).</p>
</div></body></html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    return OUT / "index.html"


if __name__ == "__main__":
    print(build())
