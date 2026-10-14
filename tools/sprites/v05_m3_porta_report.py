"""Report do v0.5 M3 · Porta da base redesenhada (reports/design/v05_m3_porta/index.html).
Chamado pelo tools/sprites/v05_m3_porta.py. Só LÊ assets/ (o "antes" é o que está no jogo hoje; nunca escreve lá).

Cenas montadas só com os sprites, na ordem do jogo (game/render.py):
  1. chão (terreno do planalto no estágio + base_floor nos tiles de chão; o tile da porta não desenha chão);
  2. linha por linha, de cima pra baixo: paredes/portas da linha (topo e porta em y − 24, face em y + 8 se o de baixo
     não é parede), depois os objetos com o pé naquela linha;
  3. raio-x (player atrás de parede ou de porta nos quadros 0–1: redesenhado com alpha 95).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import v05_m2_base_report as R2  # noqa: E402
import v05_m3_porta as G  # noqa: E402

ROOT = G.ROOT
OUT = G.REP
PEND = G.PEND
BEFORE = OUT / "before"
CENAS = OUT / "cenas"
SPR = ROOT / "assets" / "sprites"
T = G.T
LIFT = G.LIFT
STAGES = (("storm", "Tempestade"), ("arid", "Árido"), ("mist", "Névoa"), ("green", "Verde"))
OE = [f"{o}_{e}" for o, es in (("h", "ns"), ("v", "we")) for e in es]
NAMES = [f"base_door{d}_{k}" for d in ("", "2") for k in OE]


def load(p):
    return Image.open(p).convert("RGBA")


def crop(img, i, w=T):
    return img.crop((i * w, 0, i * w + w, img.height))


class Sheet:
    def __init__(self, src):
        self.top = load(SPR / "base_wall_top.png")
        self.face = load(SPR / "base_wall_face.png")
        self.floor = [load(SPR / f"base_floor_{v}.png") for v in range(4)]
        self.solo = {k: load(src / f"base_door_{k}.png") for k in OE}
        self.duo = {k: load(src / f"base_door2_{k}.png") for k in OE}

    def wall_top(self, conn, tx, ty):
        im = Image.new("RGBA", (T, T))
        for q, (c, r) in R2.top_sources(conn, tx, ty):
            im.alpha_composite(self.top.crop((c * 16, r * 16, c * 16 + 16, r * 16 + 16)), R2.OFFSET[q])
        return im


_SHEETS = {}


def sheet(which):
    if which not in _SHEETS:
        _SHEETS[which] = Sheet(BEFORE if which == "antes" else PEND)
    return _SHEETS[which]


def compose(which, stage, plan, objs, ox, oy, size=(480, 270), seed=21, k=0):
    S = sheet(which)
    bg = R2.ground("plateau", stage, *size, seed)
    Hp = len(plan)
    W = max(len(r) for r in plan)

    def at(tx, ty):
        if 0 <= ty < Hp and 0 <= tx < len(plan[ty]):
            return plan[ty][tx]
        return " "

    def conn(tx, ty):
        return at(tx, ty) == "#"

    def solid(tx, ty):
        return at(tx, ty) in "#DE"

    for ty in range(Hp):
        for tx in range(W):
            if at(tx, ty) == ".":
                bg.alpha_composite(S.floor[R2.floor_variant(tx, ty)], (ox + tx * T, oy + ty * T))
    player = None
    by_row = {}
    for o in objs:
        img, fx, fy, is_p = o
        by_row.setdefault((fy - oy - 1) // T, []).append(o)
        if is_p:
            player = o
    for ty in sorted(set(range(-1, Hp + 1)) | set(by_row)):
        for tx in range(W):
            ch = at(tx, ty)
            sx, sy = ox + tx * T, oy + ty * T
            if ch == "#":
                bg.alpha_composite(S.wall_top(conn, tx, ty), (sx, sy - LIFT))
                if not conn(tx, ty + 1):
                    idx = int(conn(tx - 1, ty)) + 2 * int(conn(tx + 1, ty))
                    bg.alpha_composite(crop(S.face, idx), (sx, sy + 8))
            elif ch == "D":
                o = R2.door_orient(solid, tx, ty)
                sh = S.solo[f"{o}_{R2.door_edge(at, tx, ty, o, 'B')}"]
                bg.alpha_composite(crop(sh, k), (sx, sy - LIFT))
            elif ch == "E":
                if at(tx + 1, ty) == "E" or at(tx - 1, ty) == "E":
                    o, half = "h", (0 if at(tx + 1, ty) == "E" else 1)
                else:
                    o, half = "v", (0 if at(tx, ty + 1) == "E" else 1)
                sh = S.duo[f"{o}_{R2.door_edge(at, tx, ty, o, 'B')}"]
                bg.alpha_composite(crop(sh, half * 4 + k), (sx, sy - LIFT))
        for img, fx, fy, _ in sorted(by_row.get(ty, []), key=lambda o: o[2]):
            bg.alpha_composite(img, (fx - img.width // 2, fy - img.height))
    if player is not None:
        img, fx, fy, _ = player
        wx, wy = fx - ox, fy - oy
        row_below = (wy - 1) // T + 1
        cols = {(wx - 10) // T, (wx + 9) // T}
        if any(at(c, row_below) == "#" or (at(c, row_below) in "DE" and k < 2) for c in cols):
            ghost = img.copy()
            ghost.putalpha(ghost.getchannel("A").point(lambda v: 95 if v else 0))
            bg.alpha_composite(ghost, (fx - img.width // 2, fy - img.height))
    return bg


# a base do print do dono: dupla na parede de baixo, solo na da direita
DONO = ["#######", "#.....#", "#.....D", "#.....#", "#.....#", "##EE###"]
# as 8 combinações: T1 = solo em cima (h_n), dupla à esquerda (v_w), solo à direita (v_e), dupla embaixo (h_s)
T1 = ["###D###", "#.....#", "E.....D", "E.....#", "#.....#", "##EE###"]
# T2 = dupla em cima (h_n), solo à esquerda (v_w), dupla à direita (v_e), solo embaixo (h_s)
T2 = ["##EE###", "#.....#", "D.....E", "#.....E", "#.....#", "###D###"]


def player_img(view="down", f=0):
    return load(SPR / f"player_idle_{view}.png").crop((f * 32, 0, f * 32 + 32, 32))


def scene(which, stage, plan, k=0, player=None, seed=21):
    ox, oy = 112, 48
    disp = load(SPR / "anim" / "anim_machine_o2_dispenser.png")
    objs = [
        (crop(disp, 0, 32), ox + 3 * T + 16, oy + 3 * T, False),
        (load(SPR / "machine_workbench.png"), ox + 1 * T + 16, oy + 2 * T, False),
        (load(SPR / "chest.png"), ox + 5 * T + 16, oy + 2 * T, False),
        (load(SPR / "machine_o2.png"), ox + 5 * T + 16, oy + 5 * T, False),
        (load(SPR / "lamp.png"), ox + 1 * T + 16, oy + 4 * T, False),
        (load(SPR / "solar_panel.png"), ox + 9 * T + 16, oy + 3 * T, False),
    ]
    if player is not None:
        img, px, py = player
        objs.append((img, ox + px, oy + py, True))
    return compose(which, stage, plan, objs, ox, oy, seed=seed, k=k)


def build_scenes():
    CENAS.mkdir(parents=True, exist_ok=True)
    out = {}
    pl_out = (player_img("up"), 3 * T + 4, 6 * T + 26)        # do lado de fora, chegando na dupla de baixo
    pl_in = (player_img("down"), 3 * T + 16, 4 * T + 20)       # dentro, atrás da porta de baixo
    for w in ("antes", "depois"):
        for k in range(4):
            out[f"dono_{w}_{k}"] = scene(w, "arid", DONO, k, pl_out)
            out[f"t1_{w}_{k}"] = scene(w, "arid", T1, k)
            out[f"t2_{w}_{k}"] = scene(w, "arid", T2, k)
        for k in (0, 3):
            out[f"dentro_{w}_{k}"] = scene(w, "arid", DONO, k, pl_in)
        for st, _ in STAGES:
            for k in (0, 3):
                out[f"est_{st}_{w}_{k}"] = scene(w, st, T1, k, seed=21)
    for name, im in out.items():
        im.save(CENAS / f"{name}.png")
    return out


def sheet_previews():
    """Tiras dos 8 arquivos (antes e depois) com os quadros separados por 4 px, sobre transparente."""
    for w, src in (("antes", BEFORE), ("depois", PEND)):
        for n in NAMES:
            im = load(src / f"{n}.png")
            nf = im.width // T
            c = Image.new("RGBA", (nf * (T + 4) - 4, im.height))
            for f in range(nf):
                c.alpha_composite(crop(im, f), (f * (T + 4), 0))
            c.save(CENAS / f"tira_{w}_{n}.png")
        # a dupla montada (as 2 metades no lugar), 4 quadros lado a lado
        for o in ("h", "v"):
            for e in ("ns" if o == "h" else "we"):
                im = load(src / f"base_door2_{o}_{e}.png")
                fw, fh = (2 * T, 56) if o == "h" else (T, T + 56)
                c = Image.new("RGBA", (4 * (fw + 6) - 6, fh))
                for k in range(4):
                    x0 = k * (fw + 6)
                    a, b = crop(im, k), crop(im, 4 + k)
                    if o == "h":
                        c.alpha_composite(a, (x0, 0))
                        c.alpha_composite(b, (x0 + T, 0))
                    else:
                        c.alpha_composite(a, (x0, 0))
                        c.alpha_composite(b, (x0, T))
                c.save(CENAS / f"dupla_{w}_{o}_{e}.png")


def check_sizes():
    rows = []
    ok = True
    for n in NAMES + ["icon_base_door", "icon_base_door_double"]:
        a = load(SPR / f"{n}.png").size
        b = load(PEND / f"{n}.png").size
        alpha = set(load(PEND / f"{n}.png").getchannel("A").getdata())
        good = a == b and alpha <= {0, 255}
        ok &= good
        rows.append((n, a, b, sorted(alpha), good))
    extras = sorted(p.name for p in PEND.glob("*.png") if p.stem not in NAMES + ["icon_base_door",
                                                                                   "icon_base_door_double"])
    return rows, extras, ok


CSS = """
:root{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}
.wrap{max-width:1300px;margin:0 auto;padding:44px 0 80px}
.eyebrow{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}
h1{font:600 40px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}h2{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}
h2::before{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}
h3{font:600 16px "Pixelify Sans",monospace;margin:0 0 4px}code{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}
p,li,td{color:var(--muted)}li b,p b,td b{color:var(--fg)}
.v2{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--rust);padding:12px 18px;max-width:1100px}
.v2>b{font:13px "Silkscreen",monospace;color:var(--rust)}
.chk{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}
img{image-rendering:pixelated}figure{margin:0}figcaption{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
@media(max-width:1000px){.grid2,.grid4{grid-template-columns:1fr}}
img.px{width:100%;height:auto;border:1px solid var(--line);display:block}
.box{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}
.row{display:flex;gap:18px;align-items:flex-end;flex-wrap:wrap}
.anim{width:100%;aspect-ratio:480/270;background-size:100% 100%;image-rendering:pixelated;animation-duration:3s;animation-timing-function:step-end;animation-iteration-count:infinite;border:1px solid var(--line)}
.sp{background-repeat:no-repeat;image-rendering:pixelated;display:inline-block;animation-duration:3s;animation-timing-function:step-end;animation-iteration-count:infinite}
table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{font:12px "Silkscreen",monospace;color:var(--gold)}
.tag{font:11px "Silkscreen",monospace;padding:2px 6px;border:1px solid var(--line);margin-right:6px}
.ok{color:var(--ok)}.bad{color:#ff6a55}
"""

# 0 → 3 → 0: fechada, abre a ~12 fps, fica aberta, fecha
CYCLE = [(0, 0), (18, 1), (22, 2), (26, 3), (74, 2), (78, 1), (82, 0)]


def kf_scene(name, prefix):
    steps = "".join(f"{p}%{{background-image:url(cenas/{prefix}_{k}.png)}}" for p, k in CYCLE)
    return f"@keyframes {name}{{{steps}}}"


def kf_sprite(name, fw, offset=0):
    steps = "".join(f"{p}%{{background-position:-{(offset + k) * fw}px 0}}" for p, k in CYCLE)
    return f"@keyframes {name}{{{steps}}}"


def build():
    BEFORE.mkdir(parents=True, exist_ok=True)
    for n in NAMES + ["icon_base_door", "icon_base_door_double"]:
        dst = BEFORE / f"{n}.png"
        if not dst.exists():
            shutil.copy(SPR / f"{n}.png", dst)
    build_scenes()
    sheet_previews()
    rows, extras, ok = check_sizes()

    kfs = []
    for pre in ("dono", "t1", "t2"):
        for w in ("antes", "depois"):
            kfs.append(kf_scene(f"a_{pre}_{w}", f"{pre}_{w}"))
    Z = 6
    for n in NAMES:
        kfs.append(kf_sprite(f"s_{n}", T * Z))
        if n.startswith("base_door2"):
            kfs.append(kf_sprite(f"s_{n}_b", T * Z, 4))

    def anim_scene(pre, w, cap):
        return (f'<figure><div class="anim" style="animation-name:a_{pre}_{w}"></div>'
                f'<figcaption>{cap}</figcaption></figure>')

    def pair(pre, title):
        return (f'<div class="grid2">{anim_scene(pre, "antes", "antes · v1.2 (no jogo hoje)")}'
                f'{anim_scene(pre, "depois", "depois · v2.0 (proposta)")}</div>'
                f'<p>{title}</p>')

    def sprite_anim(n, half=None, z=Z, src="pendentes"):
        nm = f"s_{n}" + ("_b" if half == 1 else "")
        im = load(PEND / f"{n}.png")
        return (f'<div class="sp" style="width:{T * z}px;height:{56 * z}px;background-image:url({src}/{n}.png);'
                f'background-size:{im.width * z}px {56 * z}px;animation-name:{nm}"></div>')

    h = []
    h.append(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Hesper · v0.5 M3 · Porta da base · v2.0</title>
<style>{CSS}{''.join(kfs)}</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5 M3 · proposta pro dono aprovar (nada disso está no jogo)</div>
<h1>Porta da base · v2.0 · sobe até o teto da parede</h1>

<div class="v2"><b>v2.0 · o que mudou</b><ul>
<li><b>Pedido do dono</b> (print da base): a porta dupla da parede de baixo ficava baixa, com a folha só na faixa da
face (24 px) e o chão aparecendo por cima dela. Agora a porta da parede de baixo é uma <b>fachada alta de 56 px</b>:
a tampa fica na mesma linha do topo das paredes vizinhas (y − 24) e o pé na mesma linha do pé da face (y + 32).</li>
<li><b>Visual novo</b>, na linguagem da referência (só o estilo, o desenho é nosso): <b>batente de metal escuro com
rebites</b>, <b>caixa do mecanismo em cima</b> com a <b>luzinha</b> (vermelha fechada, âmbar abrindo, <b>verde
aberta</b>), <b>folha bege com contorno laranja</b>, <b>faixas de alerta</b> pretas e laranja em cima e embaixo,
<b>janelinha ciano</b> com reflexo e a faixa laranja no meio, maçaneta perto da borda que corre e a <b>soleira com
grade</b>.</li>
<li><b>Mesmo contrato</b>: os 8 arquivos com os mesmos nomes, <b>mesmo tamanho (32×56 por quadro), mesma âncora
(x, y − 24)</b>, 4 quadros, variante B (folha na borda de fora), solo corre pra oeste/norte, dupla abre do meio com a
emenda em degrau. Colisão não muda.</li>
<li>Ícones do construtor (<code>icon_base_door</code>, <code>icon_base_door_double</code>) refeitos na linguagem nova
(opcional: se preferir, ficam os de hoje).</li>
</ul></div>

<h2>O print do dono · antes × depois</h2>
<div class="grid2"><figure><img class="px" src="ref/porta_no_jogo_dono.png" alt="">
<figcaption>o print do dono (a porta dupla marcada)</figcaption></figure>
<figure><img class="px" src="ref/referencia_porta.png" alt="" style="max-width:360px">
<figcaption>a referência de estilo</figcaption></figure></div>
<p>A mesma base, montada só com os sprites na ordem do jogo · Árido · player chegando de fora. Fecha → abre (~12 fps)
→ fica aberta → fecha. Recorte 480×270 mostrado a 2×.</p>
{pair("dono", "Do lado de fora a porta agora tem a altura da parede inteira (topo + face). Aberta, o vão é transparente acima da linha do tile, então aparece o chão de dentro da base, como numa porta de verdade.")}
<div class="grid2">
<figure><img class="px" src="cenas/dono_antes_0.png" alt=""><figcaption>antes · fechada · 1× (escala real)</figcaption></figure>
<figure><img class="px" src="cenas/dono_depois_0.png" alt=""><figcaption>depois · fechada</figcaption></figure>
<figure><img src="cenas/dono_antes_0.png" alt="" width="480" height="270"><figcaption>antes · 1×</figcaption></figure>
<figure><img src="cenas/dono_depois_0.png" alt="" width="480" height="270"><figcaption>depois · 1×</figcaption></figure>
</div>
<h3 style="margin-top:18px">Player dentro da base, atrás da porta de baixo</h3>
<div class="grid4">
<figure><img class="px" src="cenas/dentro_antes_0.png" alt=""><figcaption>antes · fechada (raio-x)</figcaption></figure>
<figure><img class="px" src="cenas/dentro_depois_0.png" alt=""><figcaption>depois · fechada (raio-x)</figcaption></figure>
<figure><img class="px" src="cenas/dentro_antes_3.png" alt=""><figcaption>antes · aberta</figcaption></figure>
<figure><img class="px" src="cenas/dentro_depois_3.png" alt=""><figcaption>depois · aberta: o player aparece pelo vão</figcaption></figure>
</div>

<h2>As 8 combinações em cena</h2>
<p><b>T1</b>: solo em cima (<code>h_n</code>), dupla à esquerda (<code>v_w</code>), solo à direita
(<code>v_e</code>), dupla embaixo (<code>h_s</code>).</p>
{pair("t1", "")}
<p><b>T2</b>: dupla em cima (<code>h_n</code>), solo à esquerda (<code>v_w</code>), dupla à direita
(<code>v_e</code>), solo embaixo (<code>h_s</code>).</p>
{pair("t2", "")}
<div class="box"><b>Como cada lado fica</b><ul>
<li><b>Parede de baixo (<code>h_s</code>)</b>: fachada alta (o pedido). Tampa 0–4, caixa do mecanismo 5–12, viga 13,
vão 14–50, soleira com grade 51–55 (linhas do sprite de 56). As listras de baixo caem na mesma altura da faixa laranja
da face da parede vizinha.</li>
<li><b>Parede de cima (<code>h_n</code>)</b>: a folha fica na borda de fora (norte), lá no fundo do tile, então a
fachada vai do topo da parede (linha 0, alinhada com o topo das vizinhas) até o pé da folha (linha 27): tampa,
caixa, viga e uma folha mais baixa (é a mesma porta vista de longe). Na frente, a grade da soleira no chão.</li>
<li><b>Paredes laterais (<code>v_e</code>/<code>v_w</code>)</b>: a câmera vê de lado, então aparece o topo:
os batentes sobem até o topo da parede, a caixa do mecanismo com a luz fica em cima do batente pra onde a folha corre
(nos dois, na dupla), a folha bege com contorno laranja fica 2 px abaixo e a ponta que corre tem a faixa de alerta.
A frente do batente de baixo mostra o metal com rebites, e a grade da soleira fica no chão, do lado de dentro.</li>
</ul></div>

<h2>Nos 4 estágios (T1, fechada e aberta)</h2>
""")
    for st, lab in STAGES:
        h.append(f'<h3 style="margin-top:14px">{lab}</h3><div class="grid4">')
        for w in ("antes", "depois"):
            for k in (0, 3):
                h.append(f'<figure><img class="px" src="cenas/est_{st}_{w}_{k}.png" alt="">'
                         f'<figcaption>{w} · {"fechada" if k == 0 else "aberta"}</figcaption></figure>')
        h.append("</div>")
    h.append("""<p>A porta é coisa construída, então não muda de cor com o estágio (como o chão e a parede da base). O bege
com contorno laranja e o batente escuro leem bem no vermelho, no cinza da névoa e no verde.</p>
<h2>Os sprites · 6× animados</h2>
<p>Fecha (0) → abre (1, 2) → aberta (3) → fecha, como no jogo. A dupla mostra as duas metades lado a lado (h) ou
uma em cima da outra (v), cada uma é um sprite de 32×56 no tile dela.</p>""")
    for d, label in (("", "Solo"), ("2", "Dupla")):
        h.append(f'<h3 style="margin-top:18px">{label}</h3><div class="row">')
        for k in OE:
            n = f"base_door{d}_{k}"
            if d == "":
                h.append(f'<figure><div class="chk">{sprite_anim(n)}</div><figcaption>{k}</figcaption></figure>')
            elif k.startswith("h"):
                h.append(f'<figure><div class="chk" style="display:flex">{sprite_anim(n, 0)}{sprite_anim(n, 1)}'
                         f'</div><figcaption>{k} · metade 1 + metade 2</figcaption></figure>')
            else:
                h.append(f'<figure><div class="chk" style="display:flex;flex-direction:column;'
                         f'height:{(56 + 32) * Z + 20}px">{sprite_anim(n, 0)}'
                         f'<div style="margin-top:-{24 * Z}px">{sprite_anim(n, 1)}</div></div>'
                         f'<figcaption>{k} · metade 1 (cima) + 2</figcaption></figure>')
        h.append("</div>")
    h.append("<h2>Tiras · antes × depois (quadros 0 → 3)</h2>")
    for n in NAMES:
        im = load(PEND / f"{n}.png")
        nf = im.width // T
        wpx = (nf * (T + 4) - 4) * 4
        h.append(f'<h3 style="margin-top:14px"><code>{n}.png</code> · {im.width}×{im.height}</h3><div class="row">'
                 f'<figure><div class="chk"><img src="cenas/tira_antes_{n}.png" width="{wpx}" alt=""></div>'
                 f'<figcaption>antes · 4×</figcaption></figure>'
                 f'<figure><div class="chk"><img src="cenas/tira_depois_{n}.png" width="{wpx}" alt=""></div>'
                 f'<figcaption>depois · 4×</figcaption></figure>'
                 f'<figure><div class="chk"><img src="pendentes/{n}.png" alt=""></div>'
                 f'<figcaption>1×</figcaption></figure></div>')
    h.append("<h2>A dupla montada · 4 quadros · 4×</h2><div class='row'>")
    for o, es in (("h", "ns"), ("v", "we")):
        for e in es:
            im = load(CENAS / f"dupla_depois_{o}_{e}.png")
            h.append(f'<figure><div class="chk"><img src="cenas/dupla_depois_{o}_{e}.png" width="{im.width * 4}" '
                     f'alt=""></div><figcaption>{o}_{e}</figcaption></figure>')
    h.append("</div>")
    h.append("""<h2>Ícones do construtor · antes × depois</h2><div class="row">
<figure><div class="chk"><img src="before/icon_base_door.png" width="128" alt=""></div><figcaption>solo · antes · 8×</figcaption></figure>
<figure><div class="chk"><img src="pendentes/icon_base_door.png" width="128" alt=""></div><figcaption>solo · depois · 8×</figcaption></figure>
<figure><div class="chk"><img src="before/icon_base_door_double.png" width="128" alt=""></div><figcaption>dupla · antes · 8×</figcaption></figure>
<figure><div class="chk"><img src="pendentes/icon_base_door_double.png" width="128" alt=""></div><figcaption>dupla · depois · 8×</figcaption></figure>
<figure><div class="chk"><img src="pendentes/icon_base_door.png" alt=""> <img src="pendentes/icon_base_door_double.png" alt=""></div><figcaption>1×</figcaption></figure>
</div>

<h2>O que veio da referência</h2>
<p>Só o estilo, nada copiado: a ideia do <b>batente grosso escuro com rebites</b> (aqui 4 px, porque a colisão
aberta só deixa 2 px de jamba e o vão tem que continuar largo), a <b>caixa do mecanismo em cima</b> com blocos bege,
pistão laranja e a luz no meio, a <b>folha bege com contorno laranja</b>, as <b>listras de alerta</b> em cima e
embaixo, a <b>janelinha ciano</b> com reflexo em diagonal, a <b>maçaneta</b> perto da borda e a <b>grade na
soleira</b>. Tudo no contorno <code>#1b1630</code>, laranja <code>#e2733a</code> das máquinas, bege e metal das
paletas que a base já usa. A ferrugem/sujeira da referência ficou de fora: a base é nova e limpa como as máquinas.</p>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Nada muda no código.</b> Copiar os 8 PNGs de <code>reports/design/v05_m3_porta/pendentes/</code> pra
<code>assets/sprites/</code> (e os 2 ícones, se o dono aprovar os novos). Mesmos nomes, <b>mesmo tamanho</b>
(solo 128×56, dupla 256×56, ícones 16×16), <b>mesma âncora</b> (quadro de 32×56 em <code>(x, y − 24)</code>),
mesma tira (dupla: metade 1 nos quadros 0–3, metade 2 nos 4–7), mesma ordem de desenho (<code>ay = ty·32 + 1</code>,
com as paredes da linha) e a mesma regra de borda (variante B, <code>BaseGrid.layout</code>).</li>
<li><b>Colisão</b>: igual (tabela da v1.2 em <code>BaseGrid.door_rects</code>). O desenho respeita: fechada, a
folha cobre a faixa da colisão; aberta, só os batentes ficam (4 px no desenho, 2 px na colisão: o player pode encostar
1–2 px no batente, como já acontecia com a parede).</li>
<li><b>Raio-x</b>: a regra de hoje vale (quadros 0–1 contam). Diferença visual: a porta de baixo (<code>h_s</code>)
agora cobre o tile de cima até y − 24 como o topo da parede já cobre; com a porta aberta (quadros 2–3) o vão é
transparente, então o player aparece por ele; só a caixa do mecanismo (linhas 0–13) cobre a cabeça dele por um
instante enquanto ele passa. Se o dono quiser, dá pra contar o <code>h_s</code> no raio-x também nos quadros 2–3, mas
não acho necessário.</li>
<li><b>Chão</b>: como hoje, o tile da porta não desenha <code>base_floor</code>: o sprite traz o chão do tile
(linhas 24–55). Na <code>h_s</code> aberta, as linhas 14–23 do vão são transparentes (aparece o chão de verdade do
tile de cima).</li>
<li><b>Fantasma do construtor</b>: continua pegando o quadro 0 de <code>h_s</code>/<code>v_e</code>; agora ele é mais
alto (a fachada inteira), sem mudar nada no código.</li>
<li><b>Luz</b>: está pintada no sprite (vermelha no 0, âmbar no 1–2, verde no 3); nada a fazer.</li>
</ul></div>

<h2>Checagem de tamanhos</h2><table><tr><th>arquivo</th><th>no jogo hoje</th><th>pendente</th><th>alpha</th><th></th></tr>""")
    for n, a, b, al, good in rows:
        h.append(f"<tr><td><code>{n}.png</code></td><td>{a[0]}×{a[1]}</td><td>{b[0]}×{b[1]}</td><td>{al}</td>"
                 f"<td class='{'ok' if good else 'bad'}'>{'ok' if good else 'ERRO'}</td></tr>")
    h.append(f"</table><p>Extras em <code>pendentes/</code>: {', '.join(extras) if extras else 'nenhum'}.</p>")
    h.append("""<p style="margin-top:30px">Gerado por <code>python3 tools/sprites/v05_m3_porta.py</code> (chama o
<code>v05_m3_porta_report.py</code>). Determinístico. Sprites de hoje copiados em <code>before/</code>.</p>
</div></body></html>""")
    (OUT / "index.html").write_text("".join(h), encoding="utf-8")
    return f"report: {OUT / 'index.html'} · tamanhos {'ok' if ok else 'ERRO'} · extras: {extras or 'nenhum'}"


if __name__ == "__main__":
    print(build())
