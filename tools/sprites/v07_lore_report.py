#!/usr/bin/env python3
"""v0.7 Lore · prévias e report (reports/design/v07_lore/index.html). Roda depois dos 3 scripts de arte:

    python3 tools/sprites/v07_destrocos.py && python3 tools/sprites/v07_props.py && python3 tools/sprites/v07_constructor.py
    python3 tools/sprites/v07_lore_report.py

Só LÊ assets/sprites/ e pendentes/. Determinístico.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v07_props as PR  # noqa: E402
from v07_lib import hsh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v07_lore"
PEND = REP / "pendentes"
T = 32


def A(name):
    return Image.open(SPR / name).convert("RGBA")


def P(name):
    return Image.open(PEND / name).convert("RGBA")


def sand(stage, x, y):
    return A(f"sand_{stage}_{int(hsh(x, y, 5) * 4)}.png")


# ---------------------------------------------------------------------------------------------------------------------
# Destroços: ficha de cada um (pegada, lift, marcas pro Dev)
# ---------------------------------------------------------------------------------------------------------------------
W = {
    "cargo_A": dict(f="wreck_cargo_A.png", tiles=(4, 3), lift=16, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "cargo_B": dict(f="wreck_cargo_B.png", tiles=(4, 3), lift=16, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "module_A": dict(f="wreck_module_A.png", tiles=(5, 4), lift=24, crate=(3, 4), term=(38, 124, 20, 17)),
    "module_B": dict(f="wreck_module_B.png", tiles=(4, 3), lift=24, crate=(3, 3), term=(38, 92, 20, 17)),
    "probe": dict(f="wreck_probe.png", tiles=(2, 2), lift=0, crate=(2, 1)),
    "liner": dict(f="wreck_liner.png", tiles=(5, 3), lift=24, crate=(2, 3)),
    "robot": dict(f="wreck_robot.png", tiles=(2, 2), lift=0, crate=(2, 1)),
    "r2_cargo_A": dict(f="r2_wreck_cargo_A.png", tiles=(4, 3), lift=16, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "r2_cargo_B": dict(f="r2_wreck_cargo_B.png", tiles=(4, 3), lift=16, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "r2_glass": dict(f="r2_wreck_module_glass.png", tiles=(7, 5), lift=32, crate=(4, 5), term=(104, 166, 20, 17), door=(1, 4), approach=(1, 5)),
    "r3_cargo_A": dict(f="r3_wreck_cargo_A.png", tiles=(5, 3), lift=16, crate=(1, 3), mouth=(4, 2), approach=(4, 3)),
    "r3_cargo_B": dict(f="r3_wreck_cargo_B.png", tiles=(5, 3), lift=16, crate=(1, 3), mouth=(4, 2), approach=(4, 3)),
    "r3_glass": dict(f="r3_wreck_module_glass.png", tiles=(7, 5), lift=32, crate=(4, 5), term=(104, 166, 20, 17), door=(1, 4), approach=(1, 5)),
    "r5_cargo_A": dict(f="r5_wreck_cargo_A.png", tiles=(5, 3), lift=32, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "r5_cargo_B": dict(f="r5_wreck_cargo_B.png", tiles=(5, 3), lift=32, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "r5_glass": dict(f="r5_wreck_module_glass.png", tiles=(8, 4), lift=40, crate=(5, 4), term=(138, 117, 20, 17), door=(1, 3), approach=(1, 4)),
    "r2_probe": dict(f="r2_wreck_probe.png", tiles=(2, 2), lift=0, crate=(2, 1)),
    "r2_robot": dict(f="r2_wreck_robot.png", tiles=(3, 2), lift=0, crate=(3, 1)),
}


def annotate(key, k=3):
    w = W[key]
    im = P(w["f"])
    tw, th = w["tiles"]
    pad = 2 * T if "crate" in w else 0
    base = Image.new("RGBA", (im.width, im.height + T), (120, 100, 90, 255))
    for ty in range(base.height // T + 1):
        for tx in range(base.width // T + 1):
            pass
    base.alpha_composite(im, (0, 0))
    big = base.resize((base.width * k, base.height * k), Image.NEAREST)
    ov = Image.new("RGBA", big.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    lift = w["lift"]
    for ty in range(th + 1):
        d.line([(0, (lift + ty * T) * k), (tw * T * k, (lift + ty * T) * k)], fill=(255, 255, 255, 110), width=1)
    for tx in range(tw + 1):
        d.line([(tx * T * k, lift * k), (tx * T * k, (lift + th * T) * k)], fill=(255, 255, 255, 110), width=1)
    def tile(t, col, label, fill=70):
        x0, y0 = t[0] * T * k, (lift + t[1] * T) * k
        d.rectangle([x0, y0, x0 + T * k - 1, y0 + T * k - 1], outline=col, width=3, fill=col[:3] + (fill,))
        d.text((x0 + 6, y0 + 4), label, fill=(255, 255, 255, 255))
    if "mouth" in w:
        tile(w["mouth"], (89, 208, 230, 255), "BOCA (E)")
        tile(w["approach"], (127, 214, 122, 255), "chega aqui", 40)
    if "door" in w:
        tile(w["door"], (89, 208, 230, 255), "PORTA futura")
        tile(w["approach"], (127, 214, 122, 255), "chega aqui", 40)
    if "crate" in w:
        tile(w["crate"], (242, 196, 109, 255), "caixa", 40)
    if "term" in w:
        x, y, rw, rh = w["term"]
        d.rectangle([x * k, y * k, (x + rw) * k, (y + rh) * k], outline=(127, 214, 122, 255), width=3)
    d.text((6, 4), f"{im.width}x{im.height}  pegada {tw}x{th}  lift {lift}", fill=(255, 255, 255, 255))
    big.alpha_composite(ov)
    big.save(REP / f"anot_{key}.png")


# ---------------------------------------------------------------------------------------------------------------------
# Cena 960×540: 5 destroços novos na areia dos 3 estágios
# ---------------------------------------------------------------------------------------------------------------------
def scene(stage):
    img = Image.new("RGBA", (960, 544), (0, 0, 0, 255))
    for y in range(17):
        for x in range(30):
            img.alpha_composite(sand(stage, x + 3, y + 5), (x * T, y * T))
    objs = []   # (pé y, âncora x, imagem, (blit x, y))

    def wreck(key, tx, ty, crate_open=None):
        w = W[key]
        im = P(w["f"])
        tw, th = w["tiles"]
        objs.append(((ty + th) * T, (tx + tw / 2) * T, im, (tx * T, ty * T - w["lift"])))
        if "crate" in w:
            cx, cy = w["crate"]
            c = A("loot_crate_empty.png" if crate_open else "loot_crate.png")
            objs.append(((ty + cy + 1) * T, (tx + cx) * T + 16, c, ((tx + cx) * T, (ty + cy) * T)))
    wreck("liner", 1, 1, True)
    wreck("cargo_A", 11, 1, False)
    wreck("module_A", 19, 1, False)
    wreck("probe", 5, 10)
    wreck("robot", 12, 10)
    for (x, y) in ((8, 6), (17, 9), (26, 8), (3, 14), (22, 13), (28, 14), (9, 14)):
        objs.append(((y + 1) * T, x * T + 16, A("rock_small.png"), (x * T, y * T)))
    if stage == "green":
        for (x, y, k) in ((9, 8, "plant_bush.png"), (16, 7, "plant_flower.png"), (27, 11, "plant_tree.png"), (2, 8, "plant_bush.png"),
                          (18, 14, "plant_flower.png"), (24, 5, "plant_bush.png")):
            im = A(k)
            objs.append((y * T + 30, x * T + 16, im, (x * T + 16 - im.width // 2, y * T + 30 - im.height)))
    pl = A("player_up.png")                                  # entrando pelo porão da VÉSPER-7
    objs.append((5 * T + 30, 14 * T + 16, pl, (14 * T, 5 * T - 2)))
    pl2 = A("player_side.png")
    objs.append((6 * T + 28, 20 * T + 16, pl2, (20 * T, 6 * T - 4)))   # lendo o terminal do módulo
    for (fy, fx, im, pos) in sorted(objs, key=lambda o: o[0]):
        img.alpha_composite(im, pos)
    out = img.crop((0, 0, 960, 540))
    out.save(REP / f"preview_wrecks_v07_{stage}.png")


# ---------------------------------------------------------------------------------------------------------------------
# Escala 1× (hoje × novo, com o Explorador)
# ---------------------------------------------------------------------------------------------------------------------
def escala():
    items = [("hoje", ["wreck_cargo.png", "wreck_module.png", "wreck_probe.png"], SPR),
             ("novo", ["wreck_cargo_A.png", "wreck_module_A.png", "wreck_probe.png", "wreck_robot.png", "wreck_liner.png"], PEND)]
    Wd = 3 * 20 + 128 + 160 + 64 + 64 + 160 + 6 * 24
    Wd = 1100
    out = Image.new("RGBA", (Wd, 2 * 190), (140, 112, 96, 255))
    ex = A("player_down.png")
    for r, (lab, names, base) in enumerate(items):
        x = 16
        y0 = r * 190
        for n in names:
            im = Image.open(base / n).convert("RGBA")
            out.alpha_composite(im, (x, y0 + 176 - im.height))
            x += im.width + 8
            out.alpha_composite(ex, (x, y0 + 176 - 32))
            x += 32 + 14
    out = out.crop((0, 0, 1000, 380))
    out.save(REP / "escala_1x.png")
    return out.size


# ---------------------------------------------------------------------------------------------------------------------
# Sala montada (base_wall + base_floor + props)
# ---------------------------------------------------------------------------------------------------------------------
M = 16
OUTER, HEDGE, VEDGE, INNER, FULL = "outer", "hedge", "vedge", "inner", "full"
SOURCE = {
    "TL": {OUTER: (0, 2), HEDGE: (2, 2), VEDGE: (0, 4), FULL: (2, 4), INNER: (2, 0)},
    "TR": {OUTER: (3, 2), HEDGE: (1, 2), VEDGE: (3, 4), FULL: (1, 4), INNER: (3, 0)},
    "BL": {OUTER: (0, 5), HEDGE: (2, 5), VEDGE: (0, 3), FULL: (2, 3), INNER: (2, 1)},
    "BR": {OUTER: (3, 5), HEDGE: (1, 5), VEDGE: (3, 3), FULL: (1, 3), INNER: (3, 1)},
}
CORNER = {"TL": (-1, -1), "TR": (1, -1), "BL": (-1, 1), "BR": (1, 1)}
ISO = {"TL": (0, 0), "TR": (1, 0), "BL": (0, 1), "BR": (1, 1)}
OFF = {"TL": (0, 0), "TR": (M, 0), "BL": (0, M), "BR": (M, M)}


def wall_piece(wall, tx, ty):
    key = []
    for q, (dx, dy) in CORNER.items():
        s, v, dg = wall(tx + dx, ty), wall(tx, ty + dy), wall(tx + dx, ty + dy)
        key.append(FULL if (s and v and dg) else INNER if (s and v) else HEDGE if s else VEDGE if v else OUTER)
    atlas = A("base_wall_top.png")
    t = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    for q, p in zip(CORNER, key):
        c, r = ISO[q] if all(k == OUTER for k in key) else SOURCE[q][p]
        t.alpha_composite(atlas.crop((c * M, r * M, c * M + M, r * M + M)), OFF[q])
    return t


def room(layout, props, w, h, k=2, name="mock_sala.png", extras=(), wallprops=()):
    """layout: lista de strings ('#' parede, '.' chão, ' ' vazio). props: (id, tx, ty)."""
    lift = 24
    W_, H_ = w * T, h * T + lift + 8
    img = Image.new("RGBA", (W_, H_), (24, 20, 28, 255))
    wall = lambda x, y: 0 <= y < h and 0 <= x < w and layout[y][x] == "#"
    floor = lambda x, y: 0 <= y < h and 0 <= x < w and layout[y][x] == "."
    objs = []
    for ty in range(h):
        for tx in range(w):
            if floor(tx, ty):
                img.alpha_composite(A(f"base_floor_{int(hsh(tx, ty, 2) * 4)}.png"), (tx * T, ty * T + lift))
    face = A("base_wall_face.png")
    for ty in range(h):
        for tx in range(w):
            if wall(tx, ty):
                def draw(tx=tx, ty=ty):
                    img.alpha_composite(wall_piece(wall, tx, ty), (tx * T, ty * T))
                    if not wall(tx, ty + 1):
                        idx = int(wall(tx - 1, ty)) + 2 * int(wall(tx + 1, ty))
                        img.alpha_composite(face.crop((idx * T, 0, idx * T + T, 24)), (tx * T, ty * T + 8 + lift))
                        for wn, wx, wy in wallprops:
                            if (wx, wy) == (tx, ty):
                                img.alpha_composite(P(f"wall_{wn}.png"), (tx * T, ty * T + 8 + lift))
                objs.append((ty * T + 1, draw))
    for pid, tx, ty in props:
        spr = P(f"prop_{pid}.png")
        if pid == "ice_stain":
            img.alpha_composite(spr, (tx * T, ty * T + lift))
            continue
        objs.append(((ty + 1) * T, lambda spr=spr, tx=tx, ty=ty: img.alpha_composite(spr, (tx * T, ty * T - 8 + lift))))
    for nm, tx, ty in extras:
        spr = A(nm)
        objs.append(((ty + 1) * T - 2, lambda spr=spr, tx=tx, ty=ty: img.alpha_composite(spr, (tx * T, ty * T - 2 + lift))))
    for _, fn in sorted(objs, key=lambda o: o[0]):
        fn()
    img = img.resize((img.width * k, img.height * k), Image.NEAREST)
    img.save(REP / name)
    return img.size


def mocks():
    lay = [
        "##################",
        "#........#.......#",
        "#........#.......#",
        "#........#.......#",
        "#................#",
        "#........#.......#",
        "#........#.......#",
        "##################",
    ]
    lab = [("lab_bench", 1, 1), ("wall_desk_a", 2, 1), ("microscope", 3, 1), ("wall_desk_b", 4, 1), ("sample_shelf", 5, 1), ("sample_shelf", 6, 1),
           ("console", 7, 1), ("ice_stain", 4, 3), ("table", 2, 4), ("chair", 3, 4), ("chair_fallen", 4, 5),
           ("sample_tank", 8, 3), ("rubble", 6, 5), ("crate", 7, 5), ("dead_plant", 1, 5), ("sign", 5, 3)]
    bunks = [("wall_desk_b", 12, 1), ("wall_desk_a", 15, 1), ("bunk", 10, 1), ("bunk", 11, 1), ("locker", 13, 1), ("locker", 14, 1), ("console", 16, 1),
             ("table", 13, 4), ("chair", 12, 4), ("chair", 14, 4), ("crate", 16, 5), ("barrel", 10, 5), ("dead_plant", 16, 3), ("sign", 12, 5)]
    wp = [("monitor_on", 2, 0), ("bp_plan", 4, 0), ("notice", 7, 0), ("bp_ice", 6, 0),
          ("monitor_off", 12, 0), ("bp_ship", 15, 0), ("notice", 10, 7)]
    return room(lay, lab + bunks, 18, 8, 2, "mock_sala.png", extras=[("player_down.png", 3, 3)], wallprops=[w for w in wp if w[2] == 0])


# ---------------------------------------------------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------------------------------------------------
def chk(src, w, h, cap="", extra=""):
    return (f'<figure><div class="chk"><img src="{src}" width="{w}" height="{h}" {extra}></div>'
            f'<figcaption>{cap}</figcaption></figure>')


def png_size(p):
    return Image.open(p).size


def main():
    REP.mkdir(parents=True, exist_ok=True)
    for key in W:
        annotate(key)
    for st in ("dead", "mist", "green"):
        scene(st)
    es = escala()
    rs = mocks()

    def wfig(src, k, cap, base=PEND):
        wd, ht = png_size((base or SPR) / Path(src).name)
        return chk(src, wd * k, ht * k, cap)

    wr = []
    # ---- seção 1: destroços
    sec = []
    sec.append('<h2>1 · Os 5 destroços</h2><p>Referência do dono à esquerda; estilo do jogo à direita. Aproveitei da referência só a <b>silhueta, a cor e o tipo de dano</b> (casco ardósia com laranja, domo partido, rampa de carga caída, painel solar, esteiras); todo pixel é desenhado por script (<code>v07_destrocos.py</code>), com contorno <code>#1b1630</code>, luz de cima-esquerda e o mesmo creme/laranja das máquinas. Sem anti-aliasing, alpha só 0/255 e a sombra de chão em um nível (92).</p>')
    sec.append('<div class="row"><figure><img class="soft" src="../v07_destrocos/referencia.png" width="560"><figcaption>referência do dono (não é pixel a pixel)</figcaption></figure></div>')
    sec.append('<h3>1.1 · Escala: hoje × novo, com o Explorador 32×32 ao lado de cada um</h3>')
    sec.append(f'<img src="escala_1x.png" width="{es[0] * 2}" height="{es[1] * 2}"><p>Em cima o que existe hoje (nave de carga, módulo, sonda). Embaixo o novo, na ordem: transportador de carga, base espacial 5×4, sonda, robô, nave de passageiros. 2×.</p>')
    # cargo
    sec.append('<h3>1.2 · #3 Transportador de carga (vira a <code>wreck_cargo</code>, a VÉSPER-7)</h3>')
    sec.append('<div class="row">' + wfig("../../../assets/sprites/wreck_cargo.png", 3, "hoje · 128×112", None) +
               wfig("pendentes/wreck_cargo_A.png", 3, "<b>A</b> ardósia (a da referência) · 128×112") +
               wfig("pendentes/wreck_cargo_B.png", 3, "<b>B</b> creme (família do creme dos de hoje) · 128×112") + '</div>')
    sec.append('<p>Mesmo desenho nas duas, só muda a paleta. O casco é uma caixa em 3/4: costado à frente, telhado em cima e a <b>tampa traseira virada pra direita, aberta e rasgada</b>, com as costelas do porão, duas caixas lá dentro, o chão do porão virando uma <b>rampa de tábuas caída</b> até a areia (com a faixa de perigo na soleira) e mais duas caixas tombadas pra fora. "03" no costado (hoje é "07"; no jogo o nome continua VÉSPER-7, o número do casco é arte; se o dono quiser igual ao texto, é só trocar os dígitos). O braço da cauda dobrado e a antena com luz vermelha sobem pros 16 px de cima. <b>Recomendo A</b>: é a da referência e destaca bem do chão vermelho; a B lê "mais uma nave de hoje".</p>')
    sec.append('<img src="anot_cargo_A.png" width="384" height="396"><p>Tile da <b>boca</b> do porão (E): <code>(3, 2)</code> relativo ao canto da pegada (azul), onde cai a rampa. O player chega por <code>(3, 3)</code> (verde, fora da pegada, mesma lógica da caixa de hoje). A caixa de saque fica em <code>(1, 3)</code> como hoje.</p>')
    # module
    sec.append('<h3>1.3 · #2 Base espacial (vira o <code>wreck_module</code>)</h3>')
    sec.append('<div class="row">' + wfig("../../../assets/sprites/wreck_module.png", 2, "hoje · 96×88 · 3×2", None) +
               wfig("pendentes/wreck_module_A.png", 2, "<b>A</b> 160×152 · pegada 5×4") +
               wfig("pendentes/wreck_module_B.png", 2, "<b>B</b> 128×120 · pegada 4×3") + '</div>')
    sec.append('<p>Anel de base com topo e parede (faixa laranja que dá a volta), <b>domo partido</b> com as costelas à mostra, <b>torre</b> à direita com cintas laranja, duas antenas, um vão caído no anel (frente-direita) com placas e entulho. <b>Terminal</b> na parede da frente: tela verde acesa (como o do módulo de hoje), dentro de um tile só. <b>A</b> é a base cheia, mais "lugar"; <b>B</b> é a compacta, ocupa menos do mapa e menos colisão. Recomendo <b>A</b> (o dono pediu "maior", e os tiles de colisão são só 20, dá pra nascer no mesmo critério de areia livre com folga de 2).</p>')
    sec.append('<div class="row"><figure><img src="anot_module_A.png" width="480" height="456"><figcaption>A · terminal em <code>(38,124)</code> 20×17, tile <code>(1,3)</code></figcaption></figure><figure><img src="anot_module_B.png" width="384" height="360"><figcaption>B · terminal em <code>(38,92)</code> 20×17, tile <code>(1,2)</code></figcaption></figure></div>')
    # probe
    sec.append('<h3>1.4 · #4 Sonda (troca a <code>wreck_probe</code>)</h3>')
    sec.append('<div class="row">' + wfig("../../../assets/sprites/wreck_probe.png", 4, "hoje · 64×64", None) +
               wfig("pendentes/wreck_probe.png", 4, "nova · 64×64 · 2×2") + '</div>')
    sec.append('<p>Corpo esférico creme com cinta laranja, lente, parabólica torta no topo, 2 painéis solares (um caído, um erguido), bocal quebrado e a caixinha de instrumentos. O LED vermelho continua em <code>(23,37)</code> (2×1 px), então o pisca do <code>draw_wreck</code> de hoje funciona sem mudar nada.</p>')
    # liner
    sec.append('<h3>1.5 · #1 Nave de passageiros (tipo NOVO: a que trouxe a colônia)</h3>')
    sec.append('<div class="row">' + wfig("pendentes/wreck_liner.png", 3, "nova · 160×120 · pegada 5×3") + '<figure><img src="anot_liner.png" width="480" height="372"><figcaption>pegada 5×3, lift 24; caixa em <code>(2,3)</code></figcaption></figure></div>')
    sec.append('<p>Fuselagem comprida creme com painéis lavanda (as chapas azuladas da referência), cabine azul no nariz enterrado na areia, fileira de janelinhas, faixa laranja, <b>rombo no meio do casco</b> com costelas e duas poltronas à mostra, asa caída, deriva alta e nacela do motor. Proponho <b>5×3 tiles</b>: é o maior depois do módulo e o mais comprido; a caixa em <code>(2,3)</code> (logo embaixo do rombo). Sem boca de entrada: o interior só existe na nave de carga.</p>')
    # robot
    sec.append('<h3>1.6 · #5 Robô de reconhecimento (tipo NOVO)</h3>')
    sec.append('<div class="row">' + wfig("pendentes/wreck_robot.png", 4, "novo · 64×64 · 2×2") + '<figure><img src="anot_robot.png" width="192" height="288"><figcaption>pegada 2×2; caixa em <code>(2,1)</code></figcaption></figure></div>')
    sec.append('<p>Chassi creme com a faixa laranja, cabeça de câmera num mastro (lente laranja), antena com luz vermelha, braço dobrado, esteira da frente grande, esteira de trás escura e uma esteira solta caída ao lado, mais uma caixa de componentes. <b>2×2</b>, igual à sonda, e dá "circuito e eletrônico" no loot.</p>')
    sec.append('<h3>1.7 · Prévias 960×540 (mesma ordem de desenho do jogo, sem recolorir)</h3><div class="pvs">' +
               "".join(f'<figure><img src="preview_wrecks_v07_{s}.png" width="960" height="540"><figcaption><b>{l}</b> · liner (caixa aberta), transportador (player entrando pela rampa), base espacial (player lendo o terminal), sonda e robô</figcaption></figure>'
                       for s, l in (("dead", "Morto"), ("mist", "Névoa"), ("green", "Verde"))) + '</div>')
    sec.append('<p><b>Estágio:</b> igual aos destroços de hoje, o sprite é <b>um só pros 3 estágios</b> (não é recolorido): o chão muda embaixo e os montinhos de areia/terra do sprite usam um marrom-cinza neutro que funciona nos três. Conferido nas 3 prévias.</p>')

    # ---- seção 2: props
    sec.append('<h2>2 · Kit de props (16 sprites 32×40 + ícones 16×16) · <span style="color:#7fd67a">APROVADOS pelo dono</span></h2>')
    sec.append('<p>Mesma âncora do baú (<code>chest.png</code> 32×40: centro da base do tile, <code>blit = (tx·32, ty·32 − 8)</code>, pé na linha 36 do PNG). A <b>mancha de gelo</b> é decal de chão (32×32, <code>blit = (tx·32, ty·32)</code>, desenhado antes dos objetos, sem colisão). Cores: creme das máquinas, cinza-lavanda da base, laranja <code>#e2733a</code>, caixote na cor do ferro. Os ícones saem do próprio sprite (sem contorno, reduzidos, contorno refeito), então sempre batem com ele.</p>')
    rows = []
    for pid, name, _, col, free, where in PR.PROPS:
        sp = PEND / f"prop_{pid}.png"
        wd, ht = png_size(sp)
        rows.append(f'<tr><td><div class="chk"><img src="pendentes/prop_{pid}.png" width="{wd * 3}" height="{ht * 3}"></div></td>'
                    f'<td><div class="chk"><img src="pendentes/icon_prop_{pid}.png" width="64" height="64"></div></td>'
                    f'<td><code>prop_{pid}</code><br><b>{name}</b></td><td>{"colide" if col else "<b>não colide</b>"}</td>'
                    f'<td>{"<b>liberado de cara</b>" if free else "scanner"}</td><td>{where}</td></tr>')
    sec.append('<table class="tb"><thead><tr><th>Sprite 3×</th><th>Ícone 4×</th><th>Id</th><th>Colisão (proposta)</th><th>Como libera</th><th>Onde aparece</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>')
    sec.append('<p><b>Liberados de cara (proposta):</b> mesa, cadeira, caixote e placa (os 4 mais "de qualquer base"). Cadeira e placa não colidem (dá pra andar por cima, não trava o corredor); o resto colide. Mancha de gelo e planta seca não colidem. Detalhe de lore opcional: no <code>sample_tank</code> tem um vulto fino escuro dentro do gelo (1 traço), sem dizer o que é; se não quiser a pista, é só pedir que eu tiro.</p>')
    sec.append(f'<h3>2.1 · Mock de sala montada (2×)</h3><img src="mock_sala.png" width="{rs[0]}" height="{rs[1]}"><p>À esquerda um <b>laboratório em ruína</b> (bancadas, microscópio, estantes de amostra, tanque, mancha de gelo, cadeira caída, entulho); à direita um <b>alojamento</b> / base do player (beliches, armários, mesa com cadeiras, console, barril). Feito com o <code>base_wall</code> (autotile) e o <code>base_floor</code> de hoje; o Explorador na porta é pra escala. Props encostados na parede ficam certos (a face da parede de 24 px passa por trás do pé).</p>')

    # ---- seção 3: construtor
    sec.append('<h2>3 · Construtor com módulo de scanner</h2>')
    sec.append('<p>O construtor só tem <b>um sprite no jogo: o ícone 16×16</b> (<code>icon_constructor.png</code>, usado na hotbar, no inventário e no fabricador; o <code>render.py</code> amplia 3× pro painel). Não existe sprite do construtor na mão do player. Duas candidatas, mesma paleta da atual:</p>')
    sec.append('<div class="row">' + chk("../../../assets/sprites/icon_constructor.png", 128, 128, "hoje") +
               chk("pendentes/icon_constructor_A.png", 128, 128, "<b>A</b> módulo em cima do corpo (tela verde de scan)") +
               chk("pendentes/icon_constructor_B.png", 128, 128, "<b>B</b> módulo embaixo do cano (tambor com lente verde)") + '</div>')
    sec.append('<p><b>A</b> lê "pistola com visor de scanner", mais legível em 16 px. <b>B</b> mantém a silhueta de hoje e põe o módulo onde a mão não cobre, mas o tambor vira um bloco cinza. Recomendo <b>A</b>. O verde da tela é o "OK" da UI, lê como "escaneando".</p>')

    # ---- seção 4: Pro Dev integrar
    sec.append('<h2>4 · Pro Dev integrar (contrato proposto, só vale depois do ok do dono)</h2>')
    sec.append('<div class="note">Nada foi pra <code>assets/sprites/</code>. Depois do ok, o gerente copia os escolhidos de <code>pendentes/</code> com o nome final da coluna "arquivo". Tudo escala 1:1, alpha 0/255 (mais a sombra de chão em 92 nos destroços e props).</div>')
    sec.append("""<table class="tb"><thead><tr><th>Arquivo final</th><th>Tamanho</th><th>Pegada (tiles)</th><th>lift</th><th>Âncora e blit</th><th>Marcas</th></tr></thead><tbody>
<tr><td><code>wreck_cargo.png</code> (troca)</td><td>128×112</td><td>4×3</td><td>16</td><td>igual a hoje: <code>ax=(tx+2)·32</code>, <code>ay=(ty+3)·32</code>, blit <code>(tx·32, ty·32−16)</code>; colisão os 12 tiles</td><td><b>Boca do porão = tile (3,2)</b> (alvo do E); chega por (3,3); caixa (1,3)</td></tr>
<tr><td><code>wreck_module.png</code> (troca, cresce)</td><td>A: 160×152 · B: 128×120</td><td>A: 5×4 · B: 4×3</td><td>24</td><td><code>ax=tx·32+W/2</code>, <code>ay=(ty+h)·32</code>, blit <code>(tx·32, ty·32−24)</code>; colisão todos os tiles da pegada</td><td><code>MODULE_TERMINAL_RECT</code> A <b>(38,124,20,17)</b> (tile (1,3), lê de (1,4)); B <b>(38,92,20,17)</b> (tile (1,2), lê de (1,3)); caixa A (3,4), B (3,3)</td></tr>
<tr><td><code>wreck_probe.png</code> (troca)</td><td>64×64</td><td>2×2</td><td>0</td><td>igual a hoje: blit <code>(tx·32, ty·32)</code></td><td>caixa (2,1); LED 2×1 em (23,37)</td></tr>
<tr><td><code>wreck_liner.png</code> (NOVO)</td><td>160×120</td><td>5×3</td><td>24</td><td><code>ax=(tx+2.5)·32</code>, <code>ay=(ty+3)·32</code>, blit <code>(tx·32, ty·32−24)</code>; colisão os 15 tiles</td><td>caixa (2,3); sem terminal (registro de bordo na caixa, como a nave de hoje)</td></tr>
<tr><td><code>wreck_robot.png</code> (NOVO)</td><td>64×64</td><td>2×2</td><td>0</td><td>blit <code>(tx·32, ty·32)</code>; colisão os 4 tiles</td><td>caixa (2,1)</td></tr>
<tr><td><code>prop_&lt;id&gt;.png</code> ×15</td><td>32×40</td><td>1×1</td><td>8</td><td>como o baú: <code>ax=tx·32+16</code>, <code>ay=(ty+1)·32</code>, blit <code>(tx·32, ty·32−8)</code>, ordenado por <code>ay</code>; caixa de colisão sugerida igual à das máquinas de 1 tile (<code>tx·32+4, ty·32+14, 24, 18</code>)</td><td>colide: ver tabela da seção 2 (cadeira, cadeira caída, placa e planta seca não)</td></tr>
<tr><td><code>prop_ice_stain.png</code> (decal)</td><td>32×32</td><td>1×1</td><td>0</td><td>blit <code>(tx·32, ty·32)</code>, desenhado <b>antes</b> de tudo que é objeto (junto do chão); sem colisão</td><td>pode ser a única decoração do tile</td></tr>
<tr><td><code>icon_prop_&lt;id&gt;.png</code> ×16</td><td>16×16</td><td>-</td><td>-</td><td>ícone do construtor (aba Decoração), mesmo padrão dos <code>icon_base_*</code></td><td>-</td></tr>
<tr><td><code>icon_constructor.png</code> (troca)</td><td>16×16</td><td>-</td><td>-</td><td>o <code>render.py</code> já carrega por esse nome (hotbar, inventário, fabricador; 3× no painel). Nenhum outro sprite do construtor existe</td><td>-</td></tr></tbody></table>""")
    sec.append("""<ul><li><b>Ordem de desenho:</b> igual aos destroços de hoje, ordenado pelo pé (<code>ay</code>); os 24/16 px de lift sobem pro tile de cima e cobrem o player que passar atrás.</li>
<li><b>Mouse/clique nos destroços:</b> usar o tamanho do sprite novo (<code>SPECS[...].sprite_size</code>), não o antigo.</li>
<li><b>Estágios:</b> os destroços e props são um PNG só pros 3 estágios (coisa construída, como a base). O decal de gelo e o tanque têm tons de gelo próprios.</li>
<li><b>Luz da caverna:</b> nenhum prop emite luz. A tela verde do terminal do módulo é pintada no sprite (como o <code>terminal.png</code>).</li></ul>""")
    # ---- decisões
    dec = ('<h2>Decisões que o dono precisa tomar</h2><ol class="dec">'
           '<li><b>Transportador:</b> A (ardósia, a da referência) ou B (creme)? Recomendo A. Número do casco "03" (da referência) ou "07" (VÉSPER-7 de hoje)?</li>'
           '<li><b>Base espacial:</b> A (5×4, 160×152) ou B (4×3, 128×120)? Recomendo A.</li>'
           '<li><b>Nave de passageiros:</b> pegada 5×3 serve? (é a maior depois do módulo A.) E o robô e a sonda em 2×2.</li>'
           '<li><b>Props:</b> os 4 liberados de cara (mesa, cadeira, caixote, placa) e a colisão proposta; manter o vulto no tanque de amostra?</li>'
           '<li><b>Construtor:</b> A (visor no corpo) ou B (tambor embaixo)? Recomendo A.</li></ol>')
    return [r5_html()] + [r4_html()] + [r3_html()] + [r2_html()] + [dec.replace('Decisões que o dono precisa tomar','Decisões da rodada 1 (construtor A/B pendente; o resto superado)')] + sec


def scene2(stage):
    img = Image.new("RGBA", (960, 544), (0, 0, 0, 255))
    for y in range(17):
        for x in range(30):
            img.alpha_composite(sand(stage, x + 3, y + 5), (x * T, y * T))
    objs = []

    def wreck(key, tx, ty, crate_open=None):
        w = W[key]
        im = P(w["f"])
        tw, th = w["tiles"]
        objs.append(((ty + th) * T, 0, im, (tx * T, ty * T - w["lift"])))
        cx, cy = w["crate"]
        c = A("loot_crate_empty.png" if crate_open else "loot_crate.png")
        objs.append(((ty + cy + 1) * T, 0, c, ((tx + cx) * T, (ty + cy) * T)))
    wreck("r2_glass", 1, 2, False)
    wreck("r2_cargo_A", 10, 11, True)
    wreck("r2_robot", 22, 2, False)
    wreck("r2_probe", 18, 11, False)
    wreck("liner", 14, 6, True) if False else None
    for (x, y) in ((9, 8), (17, 9), (27, 8), (3, 14), (24, 14), (29, 12)):
        objs.append(((y + 1) * T, 0, A("rock_small.png"), (x * T, y * T)))
    if stage == "green":
        for (x, y, k) in ((9, 5, "plant_bush.png"), (17, 6, "plant_flower.png"), (28, 9, "plant_tree.png"), (2, 12, "plant_bush.png")):
            im = A(k)
            objs.append((y * T + 30, 0, im, (x * T + 16 - im.width // 2, y * T + 30 - im.height)))
    objs.append((15 * T + 30, 0, A("player_up.png"), (11 * T + 16 - 16, 15 * T - 2)))     # na frente do porão... chegando
    objs.append((9 * T + 28, 0, A("player_up.png"), (3 * T, 9 * T - 4)))                 # na frente da porta da base
    for (_, _, im, pos) in sorted(objs, key=lambda o: o[0]):
        img.alpha_composite(im, pos)
    img.crop((0, 0, 960, 540)).save(REP / f"preview_r2_{stage}.png")


def r2_html():
    for k in ("r2_cargo_A", "r2_glass", "r2_probe", "r2_robot"):
        annotate(k)
    for st in ("dead", "mist", "green"):
        scene2(st)
    out = []
    o = out.append
    o('<h1 style="color:#f2c46d">Rodada 2</h1><div class="note"><b>v1.1 · o que mudou</b>: o dono <b>aprovou os props</b> (seção 2 abaixo, marcados) e pediu mais capricho nos destroços. '
      'Refeitos: <b>transportador</b> (silhueta de nave com curvas, cockpit, o nome VÉSPER-7 no casco, porão aberto), <b>sonda</b> (satélite caído, sem "caule + cabeça"), '
      '<b>base espacial</b> (maior, 7×5, com vidro e janelões, domo partido, eclusa com a futura porta) e <b>robô</b> (rover de esteiras com cabeça em pescoço, 3×2). '
      'Novo: <b>6 props de parede</b> (monitores e diagramas). A nave de passageiros ficou como estava. O construtor segue com A/B em aberto.</div>')
    o('<h2>R2.1 · Antes × depois</h2>')
    pairs = [("Transportador", "pendentes/wreck_cargo_A.png", "pendentes/r2_wreck_cargo_A.png", "pendentes/r2_wreck_cargo_B.png", 3),
             ("Sonda", "pendentes/wreck_probe.png", "pendentes/r2_wreck_probe.png", None, 4),
             ("Robô", "pendentes/wreck_robot.png", "pendentes/r2_wreck_robot.png", None, 4)]
    for nm, a, b, c, k in pairs:
        row = chk(a, Image.open(REP / a).width * k, Image.open(REP / a).height * k, "antes (rodada 1)") + chk(b, Image.open(REP / b).width * k, Image.open(REP / b).height * k, "<b>depois</b>" + (" · A ardósia" if c else ""))
        if c:
            row += chk(c, Image.open(REP / c).width * k, Image.open(REP / c).height * k, "<b>depois</b> · B creme")
        o(f'<h3>{nm}</h3><div class="row">{row}</div>')
    o('<h3>Base espacial</h3><div class="row">' + chk("pendentes/wreck_module_A.png", 320, 304, "antes (rodada 1, 5×4)") + chk("pendentes/r2_wreck_module_glass.png", 448, 384, "<b>depois</b> · 7×5 · 224×192 (2×)") + '</div>')
    o('<h3>Escala (1×, com o Explorador)</h3>')
    es = Image.new("RGBA", (760, 210), (140, 112, 96, 255))
    x = 10
    for n in ("r2_wreck_cargo_A.png", "r2_wreck_robot.png", "r2_wreck_probe.png"):
        im = P(n); es.alpha_composite(im, (x, 200 - im.height)); x += im.width + 4
        es.alpha_composite(A("player_down.png"), (x, 200 - 32)); x += 40
    im = P("r2_wreck_module_glass.png"); es.alpha_composite(im, (x, 205 - im.height)); x += im.width + 4
    es.alpha_composite(A("player_down.png"), (x, 200 - 32))
    es = es.crop((0, 0, 900, 210)) if es.width >= 900 else es
    es.save(REP / "escala_r2.png")
    o(f'<img src="escala_r2.png" width="{es.width * 2}" height="{es.height * 2}">')
    o('<h2>R2.2 · Os redesenhos</h2>')
    o('<h3>Transportador · VÉSPER-7</h3><p>Casco de cápsula com volume (cilindro sombreado em faixas, nariz arredondado), <b>cockpit de vidro</b> com estrutura e reflexo, barbatana dorsal curva com ponta laranja, faixa laranja que acompanha a curva, antena, costuras de placa. <b>Nome pintado: "VESPER-7"</b> numa fonte própria 3×5 px (8 letras = 31 px de largura, legível em 1×); o <b>É</b> leva um pixel de acento. A popa termina num <b>arco aberto</b> (a boca do porão) com costelas, caixas, lábio de chapa torta, rampa de tábuas e 2 caixas caídas. Duas paletas: <b>A ardósia</b> (letras claras) e <b>B creme</b> (letras escuras). Recomendo A.</p>')
    o('<div class="row"><img src="anot_r2_cargo_A.png" width="384" height="396"><figure><div class="chk"><img src="pendentes/r2_wreck_cargo_A.png" width="256" height="224"></div><figcaption>1× ampliado 2×: o nome lê bem</figcaption></figure></div>')
    o('<p>Boca do porão = tile <code>(3,2)</code> (onde a rampa encosta), chega por <code>(3,3)</code>; caixa em <code>(1,3)</code>. Mesmo contrato da rodada 1.</p>')
    o('<h3>Sonda · satélite caído</h3><p>Barramento de instrumentos em caixa com <b>manta térmica dourada</b>, luneta no topo, bocal de empuxo, <b>prato parabólico arrancado e caído no chão</b> (borda torta, mordida, alimentador dobrado), uma asa solar quebrada em pé e outra caída, pernas de pouso entortadas, <b>cratera/sulco de impacto</b> embaixo. Sem haste com cabeça. <b>Mudança de contrato:</b> o LED vermelho do pisca agora fica em <code>(40,26)</code> (2×1 px; apagado <code>#3b3f46</code>).</p>')
    o('<img src="anot_r2_probe.png" width="192" height="288">')
    o('<h3>Robô de reconhecimento · 3×2</h3><p>Rover como o #5 da referência: esteira da frente com rodas e sapatas, esteira de trás escura, <b>chassi creme com faixa laranja e painel arrancado</b> mostrando a placa verde, <b>pescoço com cabeça de câmera</b> (lente laranja), antena com LED, braço dobrado com a garra no chão, <b>esteira solta</b> caída à direita e caixote tombado. Pedi <b>3×2</b> (96×64, lift 0) pra a silhueta caber sem espremer; a caixa de saque fica em <code>(3,1)</code>.</p>')
    o('<div class="row"><img src="anot_r2_robot.png" width="288" height="192"><figure><div class="chk"><img src="pendentes/r2_wreck_robot.png" width="192" height="128"></div><figcaption>1× ampliado 2×</figcaption></figure></div>')
    o('<h3>Base espacial de vidro · 7×5</h3><p>Inspirada no habitat da sua referência (módulos brancos, domo de vidro com estrutura, janelões, eclusa com porta e rampa, painel solar ao lado), tudo original: <b>tambor central</b> com faixa laranja e um <b>anel de janelões</b> em volta, <b>domo de vidro com meridianos e paralelos</b>, <b>eclusa à esquerda</b> com janelinha, porta escura e rampa de aço, módulo-tanque à direita e <b>2 painéis solares</b> (um com canto arrancado). Ruína: <b>domo estilhaçado</b> (buraco irregular com vigas enferrujadas), rachaduras brancas, um janelão arrancado, estilhaços e placas no chão.</p>')
    o('<p><b>Como fiz o vidro em pixel art</b> (sem alpha intermediário, como a água e o gelo do jogo): <b>degraus de cian</b> de cima pra baixo (<code>#a8e4f2 → #6cbcd4 → #3f8fae → #26627c</code>), <b>reflexos duros em diagonal</b> em branco gelo <code>#e6fbff</code> (faixas de 2 px que repetem a cada 23 px) e manchas de <b>interior escuro</b> (<code>#1f3a46</code>) com uns pontinhos quentes (luz) e verdes (planta) vistos através do vidro. O vidro partido mostra o interior mais escuro e as quinas ganham 1 px de branco e 1 de sombra.</p>')
    o('<div class="row"><img src="anot_r2_glass.png" width="672" height="576"></div>')
    o('<p><b>Pegada 7×5</b> (224×192, lift 32): <b>terminal</b> embutido na base do tambor, rect <code>(104,166,20,17)</code> = tile <code>(3,4)</code>, lido de <code>(3,5)</code>; <b>futura porta</b> = a porta da eclusa, tile <code>(1,4)</code> (ramp em volta; o jogador chega por <code>(1,5)</code>); <b>caixa</b> em <code>(4,5)</code>, na frente do tambor. Colisão sugerida: todos os 35 tiles menos a quina de cima à esquerda e as de cima à direita fora das antenas (livre pra Dev decidir; o sprite tem cantos transparentes em cima). Pra camadas por dentro no futuro: a eclusa é a entrada e o domo/janelões já mostram o interior.</p>')
    o('<h2>R2.3 · Prévias 960×540 (mesma ordem de desenho do jogo)</h2><div class="pvs">' +
      "".join(f'<figure><img src="preview_r2_{s}.png" width="960" height="540"><figcaption><b>{l}</b> · base de vidro (player na porta), robô, sonda e transportador (caixa já aberta, player chegando pela rampa)</figcaption></figure>'
              for s, l in (("dead", "Morto"), ("mist", "Névoa"), ("green", "Verde"))) + '</div>')
    # props de parede
    import v07_r2_wallprops as WP
    o('<h2>R2.4 · Props de parede (novos)</h2><p>32×40 não: estes são <b>32×24</b>, do tamanho da face da <code>base_wall</code>, desenhados <b>por cima da face</b> em <code>blit (tx·32, ty·32 + 8)</code> do tile de parede, depois dela, sem colisão. Vivem nas linhas 2–18 da face (passam por cima da faixa laranja) e só valem em parede que mostra face (tile de baixo é chão). Ícones 16×16 gerados do sprite.</p>')
    rows = "".join(f'<tr><td><div class="chk"><img src="pendentes/wall_{pid}.png" width="192" height="144"></div></td><td><div class="chk"><img src="pendentes/icon_wall_{pid}.png" width="64" height="64"></div></td><td><code>wall_{pid}</code><br><b>{nm}</b></td></tr>' for pid, nm, _ in WP.WALL)
    o('<table class="tb"><thead><tr><th>Sprite 6×</th><th>Ícone 4×</th><th>Id</th></tr></thead><tbody>' + rows + '</tbody></table>')
    o(f'<p>Mock da sala atualizado (os props de parede estão na fileira de cima), 2×:</p><img src="mock_sala.png" width="1152" height="576">')
    o('<div class="note"><b>Pro Dev (rodada 2)</b>: arquivos novos em <code>pendentes/</code>: <code>r2_wreck_cargo_{A,B}.png</code> (128×112, 4×3, lift 16, boca (3,2)), <code>r2_wreck_module_glass.png</code> (224×192, 7×5, lift 32, terminal (104,166,20,17), porta (1,4), caixa (4,5)), <code>r2_wreck_probe.png</code> (64×64, 2×2, LED 2×1 em (40,26), caixa (2,1)), <code>r2_wreck_robot.png</code> (96×64, <b>3×2</b>, lift 0, caixa (3,1)), <code>wall_*.png</code> (32×24) e <code>icon_wall_*.png</code> (16×16). Nomes finais sugeridos: <code>wreck_cargo</code>, <code>wreck_module</code>, <code>wreck_probe</code>, <code>wreck_robot</code>, <code>prop_wall_&lt;id&gt;</code>. A nave de passageiros (<code>wreck_liner</code>) e os 16 props continuam como na rodada 1.</div>')
    o('<h2>R2.5 · Decisões do dono</h2><ol class="dec"><li>Transportador: A (ardósia) ou B (creme)? A fonte do nome ficou legível ("VESPER-7" em 31 px)?</li><li>Base de vidro 7×5 serve (ou quer maior ainda)? Vidro e janelões estão no tom?</li><li>Robô em 3×2 (em vez de 2×2) ok?</li><li>Props de parede: quais entram e quais liberados de cara?</li><li>Construtor A ou B (segue pendente).</li></ol>')
    o('<hr style="border-color:#3a2c25;margin:48px 0"><h1 style="color:#a8968a">Rodada 1 (histórico)</h1><p><b>Props aprovados pelo dono</b>: todos os 16 da seção 2 abaixo. Transportador, base, sonda e robô desta rodada foram <b>substituídos pela rodada 2</b>; a nave de passageiros segue valendo.</p>')
    return "".join(out)


def scene3(stage):
    img = Image.new("RGBA", (960, 544), (0, 0, 0, 255))
    for y in range(17):
        for x in range(30):
            img.alpha_composite(sand(stage, x + 3, y + 5), (x * T, y * T))
    objs = []

    def wreck(key, tx, ty, crate_open=None):
        w = W[key]
        im = P(w["f"])
        tw, th = w["tiles"]
        objs.append(((ty + th) * T, 0, im, (tx * T, ty * T - w["lift"])))
        cx, cy = w["crate"]
        c = A("loot_crate_empty.png" if crate_open else "loot_crate.png")
        objs.append(((ty + cy + 1) * T, 0, c, ((tx + cx) * T, (ty + cy) * T)))
    wreck("r3_glass", 1, 2, False)
    wreck("r3_cargo_A", 14, 9, True)
    wreck("r2_robot", 22, 2, False)
    wreck("r2_probe", 6, 13, False)
    for (x, y) in ((11, 7), (19, 14), (27, 8), (4, 11), (26, 14)):
        objs.append(((y + 1) * T, 0, A("rock_small.png"), (x * T, y * T)))
    if stage == "green":
        for (x, y, k) in ((9, 5, "plant_bush.png"), (17, 6, "plant_flower.png"), (28, 10, "plant_tree.png"), (2, 12, "plant_bush.png")):
            im = A(k)
            objs.append((y * T + 30, 0, im, (x * T + 16 - im.width // 2, y * T + 30 - im.height)))
    objs.append((13 * T + 30, 0, A("player_up.png"), (18 * T, 13 * T - 2)))
    objs.append((9 * T + 28, 0, A("player_up.png"), (3 * T, 9 * T - 4)))
    for (_, _, im, pos) in sorted(objs, key=lambda o: o[0]):
        img.alpha_composite(im, pos)
    img.crop((0, 0, 960, 540)).save(REP / f"preview_r3_{stage}.png")


def r3_html():
    for k in ("r3_cargo_A", "r3_cargo_B", "r3_glass"):
        annotate(k)
    for st in ("dead", "mist", "green"):
        scene3(st)
    out = []
    o = out.append
    o('<h1 style="color:#f2c46d">Rodada 3</h1><div class="note"><b>v1.2 · o que mudou</b>: <b>props continuam aprovados</b>. Novo: <b>mesas de parede</b> (2 variações) que encaixam sob os monitores e diagramas. '
      '<b>Base espacial</b> refeita em 3/4 de verdade (topo, frente e lateral com volume e sombra). <b>VÉSPER-7</b> refeita como nave angular facetada (chapas em camadas com bordas escuras), '
      '<b>2 formas</b> (A cargueiro largo e achatado em creme, B comprido com cabine elevada e motores laterais em vermelho). Sonda e robô da rodada 2 ficaram; construtor A/B segue pendente.</div>')
    o('<h2>R3.1 · Mesas de parede</h2><p>Sprite 32×40 igual aos props (blit <code>(tx·32, ty·32 − 8)</code>), pra ficar <b>no tile logo abaixo da parede de cima</b>. O PNG cobre os 8 px de baixo da face da parede, e o <b>tampo começa na linha 1 do PNG</b> (= linha 17 da face de 24 px): o pé do monitor (linhas 16–18 da face) fica atrás da borda do tampo, então o monitor "senta" na mesa, sem fresta. Colidem (tile inteiro), 1 tile.</p>')
    o('<div class="row">' + chk("pendentes/prop_wall_desk_a.png", 192, 240, "<b>A</b> bancada simples · <code>prop_wall_desk_a</code>") + chk("pendentes/prop_wall_desk_b.png", 192, 240, "<b>B</b> escrivaninha com gaveta · <code>prop_wall_desk_b</code>") +
      chk("pendentes/icon_prop_wall_desk_a.png", 64, 64, "ícone A") + chk("pendentes/icon_prop_wall_desk_b.png", 64, 64, "ícone B") + '</div>')
    o('<p>Encaixe no mock (monitor ligado + mesa A; diagrama + mesa B; à direita monitor apagado + mesa B e diagrama + mesa A), 2×:</p><img src="mock_sala.png" width="1152" height="576">')
    o('<h2>R3.2 · Base espacial em 3/4</h2><p>Mesmo desenho (domo de vidro, janelões, eclusa com porta e rampa, 2 painéis solares, domo estilhaçado), agora com <b>volume</b>: eclusa e módulo-tanque são <b>caixas com teto visível, frente e lateral direita escura</b> (escotilha, vigia e saídas de ar no teto); o tambor tem <b>topo elíptico mais alto</b> (ângulo de máquina do jogo), o domo deixa ver o <b>piso interior de cima</b> com as costelas de trás pelo vidro, as faces da direita escurecem e a <b>sombra cai pra direita</b>; painéis solares com espessura. Mesma pegada e marcas da rodada 2 (7×5, terminal <code>(104,166,20,17)</code>, porta (1,4), caixa (4,5)).</p>')
    o('<div class="row">' + chk("pendentes/r2_wreck_module_glass.png", 448, 384, "antes (rodada 2)") + chk("pendentes/r3_wreck_module_glass.png", 448, 384, "<b>depois</b> (rodada 3)") + '</div>')
    o('<h2>R3.3 · VÉSPER-7 angular, 2 formas (160×112, pegada 5×3)</h2><p>Casco facetado hard-surface: <b>chapas poligonais sobrepostas em camadas</b>, cada uma com borda escura de 1 px e realce na aresta de cima, frisos laranja, aberturas de ventilação, cockpit de vidro em faceta, motores e antena; nada de cápsula. <b>Pegada cresce de 4×3 pra 5×3</b> (160 de largura) pra caber asa/motores sem espremer. Nome <b>VESPER-7</b> pintado (fonte 3×5, com acento no E). Porão traseiro aberto com rampa e caixas; <b>boca = tile (4,2)</b> (a rampa), chega por <code>(4,3)</code>; caixa de saque em <code>(1,3)</code>.</p>')
    o('<div class="row">' + chk("pendentes/wreck_cargo_A.png", 256, 224, "rodada 1 (caixa)") + chk("pendentes/r2_wreck_cargo_A.png", 256, 224, "rodada 2 (cápsula, \"Banzai Bill\")") + '</div>')
    o('<div class="row">' + chk("pendentes/r3_wreck_cargo_A.png", 480, 336, "<b>A</b> cargueiro largo e achatado, asas curtas e dois motores traseiros (creme com bordas azul-marinho)") +
      chk("pendentes/r3_wreck_cargo_B.png", 480, 336, "<b>B</b> comprido, cabine elevada com vidros inclinados, nacelas de motor laterais e deriva (vermelho facetado)") + '</div>')
    o('<div class="row"><img src="anot_r3_cargo_A.png" width="480" height="396"><img src="anot_r3_cargo_B.png" width="480" height="396"></div>')
    o('<p>Recomendo <b>A</b> pelo creme (família dos destroços e máquinas) e a leitura de "cargueiro"; <b>B</b> é mais "nave de ação" e destaca mais no chão claro do estágio verde.</p>')
    o('<h2>R3.4 · Prévias 960×540 (mesma ordem de desenho)</h2><div class="pvs">' +
      "".join(f'<figure><img src="preview_r3_{s}.png" width="960" height="540"><figcaption><b>{l}</b> · base de vidro 3/4, robô, sonda e VÉSPER-7 A (caixa aberta, player chegando pela rampa)</figcaption></figure>'
              for s, l in (("dead", "Morto"), ("mist", "Névoa"), ("green", "Verde"))) + '</div>')
    o('<div class="note"><b>Pro Dev (rodada 3)</b>: <code>r3_wreck_cargo_{A,B}.png</code> 160×112, <b>5×3</b>, lift 16, boca (4,2), chega (4,3), caixa (1,3); <code>r3_wreck_module_glass.png</code> 224×192, 7×5, lift 32 (marcas iguais às da rodada 2); <code>prop_wall_desk_{a,b}.png</code> 32×40 (colide, colada na parede norte: só colocar com o tile de cima sendo parede) e <code>icon_prop_wall_desk_{a,b}.png</code> 16×16. Os props de parede <code>wall_*</code> (32×24) são desenhados na face da parede de cima, depois dela.</div>')
    o('<h2>R3.5 · Decisões do dono</h2><ol class="dec"><li>VÉSPER-7: forma A ou B? E a pegada 5×3 (em vez de 4×3)?</li><li>Base de vidro em 3/4 agora lê como as máquinas do jogo?</li><li>Mesas de parede: A, B ou as duas? Entram nos "liberados de cara"?</li><li>Construtor A ou B (pendente).</li></ol>')
    o('<hr style="border-color:#3a2c25;margin:48px 0"><h1 style="color:#a8968a">Rodada 2 (histórico)</h1>')
    return "".join(out)


def r4_html():
    out = []
    o = out.append
    ch = '<span style="color:#7fd67a">APROVADO</span>'
    o('<h1 style="color:#f2c46d">Rodada 4</h1><div class="note"><b>v1.3 · o que mudou</b>: correção de rota. O "Plants vs Zombies" era o <b>ícone do construtor</b>, não a sonda. '
      'Por isso: <b>sonda da rodada 1 = APROVADA</b> (a <code>r2_wreck_probe</code> está descartada); <b>ícone do construtor refeito</b> como scanner de mão (2 candidatas). '
      '<b>VÉSPER-7 continua pendente</b> (nada mexido nela nesta rodada).</div>')
    o('<h2>R4.1 · Status</h2><table class="tb"><thead><tr><th>Item</th><th>Status</th></tr></thead><tbody>'
      f'<tr><td>Sonda (rodada 1, <code>pendentes/wreck_probe.png</code>, 64×64, 2×2, LED em (23,37))</td><td>{ch}</td></tr>'
      f'<tr><td>Props (16) e mesas de parede A/B, props de parede (6)</td><td>{ch}</td></tr>'
      f'<tr><td>Base espacial de vidro 3/4 (7×5)</td><td>{ch} por ora</td></tr>'
      f'<tr><td>Robô (3×2) e nave de passageiros (5×3)</td><td>{ch} por ora</td></tr>'
      '<tr><td>VÉSPER-7 (rodada 3, A/B)</td><td><b style="color:#f2c46d">pendente</b> ("ainda não tá como eu quero")</td></tr>'
      '<tr><td>Construtor (ícone)</td><td><b style="color:#f2c46d">2 candidatas novas abaixo</b></td></tr></tbody></table>')
    o('<div class="row">' + chk("pendentes/wreck_probe.png", 256, 256, f"sonda aprovada (rodada 1) {ch}") + chk("pendentes/r2_wreck_probe.png", 256, 256, "r2_wreck_probe · descartada") + '</div>')
    o('<h2>R4.2 · Construtor como scanner de mão</h2><p>Referência (scanner de mão estilo Subnautica) usada só como estilo: aparelho retangular chunky de quinas chanfradas, <b>tela grande escura com grade e um traço de HUD</b> ocupando a frente, detalhes laranja de painel, empunhadura embaixo. Nada de cano nem haste. O jogo usa <b>um só PNG 16×16</b> (<code>icon_constructor</code>) e o painel só amplia esse mesmo arquivo 3× (<code>render.py</code>), então não há outro asset: abaixo, o 1× ampliado e o 3× do painel.</p>')
    ic = lambda n: Image.open(PEND / n).convert("RGBA")
    row = chk("../../../assets/sprites/icon_constructor.png", 128, 128, "hoje (a que parece planta)")
    for t, cap in (("A", "<b>A</b> de frente, tela dominando, casca creme com faixa laranja e empunhadura laranja (paleta das máquinas)"),
                   ("B", "<b>B</b> em 3/4 com a lateral de painel laranja e casca verde-escura (como a referência)")):
        row += chk(f"pendentes/r4_icon_constructor_{t}.png", 128, 128, cap)
    o('<div class="row">' + row + '</div>')
    o('<div class="row">' + chk("../../../assets/sprites/icon_constructor.png", 48, 48, "hoje · 3× (painel)") + chk("pendentes/r4_icon_constructor_A.png", 48, 48, "A · 3×") + chk("pendentes/r4_icon_constructor_B.png", 48, 48, "B · 3×") + '</div>')
    o('<p><b>A</b> lê como "aparelho com tela" mesmo em 1× e combina com o branco/laranja das máquinas e da hotbar. <b>B</b> é mais fiel à referência, mas o verde destoa do resto da hotbar. Recomendo <b>A</b>. Nome final: <code>icon_constructor.png</code> (troca).</p>')
    o('<div class="note"><b>Pro Dev</b>: só trocar <code>icon_constructor.png</code> (16×16); nada de código muda. Sonda: voltar ao <code>wreck_probe</code> da rodada 1 (mesmo contrato de hoje, LED em (23,37)).</div>')
    o('<h2>R4.3 · Decisão do dono</h2><ol class="dec"><li>Construtor: A ou B?</li><li>VÉSPER-7: o que falta pra ficar como quer? (pendente da rodada 3)</li></ol>')
    o('<hr style="border-color:#3a2c25;margin:48px 0"><h1 style="color:#a8968a">Rodada 3 (histórico)</h1>')
    return "".join(out)


def scene5(stage):
    img = Image.new("RGBA", (960, 544), (0, 0, 0, 255))
    for y in range(17):
        for x in range(30):
            img.alpha_composite(sand(stage, x + 3, y + 5), (x * T, y * T))
    objs = []

    def wreck(key, tx, ty, crate_open=None):
        w = W[key]
        im = P(w["f"])
        tw, th = w["tiles"]
        objs.append(((ty + th) * T, 0, im, (tx * T, ty * T - w["lift"])))
        cx, cy = w["crate"]
        c = A("loot_crate_empty.png" if crate_open else "loot_crate.png")
        objs.append(((ty + cy + 1) * T, 0, c, ((tx + cx) * T, (ty + cy) * T)))
    wreck("r5_glass", 1, 3, False)
    wreck("r5_cargo_A", 16, 4, True)
    wreck("r5_cargo_B", 16, 12, False)
    wreck("probe", 4, 13, False)
    for (x, y) in ((11, 9), (13, 14), (27, 9), (28, 14), (2, 10)):
        objs.append(((y + 1) * T, 0, A("rock_small.png"), (x * T, y * T)))
    if stage == "green":
        for (x, y, k) in ((11, 3, "plant_bush.png"), (24, 8, "plant_flower.png"), (28, 4, "plant_tree.png"), (12, 12, "plant_bush.png")):
            im = A(k)
            objs.append((y * T + 30, 0, im, (x * T + 16 - im.width // 2, y * T + 30 - im.height)))
    ex = lambda n, x, y: objs.append((y + 30, 0, A(n), (x, y - 2)))
    ex("player_down.png", 2 * T, 9 * T + 8)
    ex("player_up.png", 19 * T, 8 * T + 4)
    ex("player_side.png", 12 * T, 13 * T + 4)
    for (_, _, im, pos) in sorted(objs, key=lambda o: o[0]):
        img.alpha_composite(im, pos)
    img.crop((0, 0, 960, 540)).save(REP / f"preview_r5_{stage}.png")


def r5_html():
    for k in ("r5_cargo_A", "r5_cargo_B", "r5_glass"):
        annotate(k)
    for st in ("dead", "mist", "green"):
        scene5(st)
    out = []
    o = out.append
    o('<h1 style="color:#f2c46d">Rodada 5</h1><div class="note"><b>v1.4 · o que mudou</b>: <b>construtor</b> com a forma da B (tablet) em creme + laranja; '
      '<b>VÉSPER-7</b> e <b>base espacial</b> agora em <b>isométrico/diagonal (2:1)</b>, com o sprite maior que a pegada (a colisão fica uma aproximação embaixo do casco). '
      'Nada mais mexido (props, mesas, sonda r1, robô e nave de passageiros seguem aprovados).</div>')
    o('<h2>R5.1 · Construtor em creme + laranja</h2><p>Forma da B (tablet em 3/4: lateral, tela grande escura com grade e traço de HUD, empunhadura embaixo). Duas opções de onde fica o laranja:</p>')
    row = chk("pendentes/r4_icon_constructor_B.png", 128, 128, "rodada 4 B (verde)") + chk("pendentes/r5_icon_constructor_A.png", 128, 128, "<b>A</b> laranja na lateral e na empunhadura") + chk("pendentes/r5_icon_constructor_B.png", 128, 128, "<b>B</b> moldura laranja em volta da tela")
    o('<div class="row">' + row + '</div><div class="row">' + chk("../../../assets/sprites/icon_constructor.png", 48, 48, "hoje 3×") + chk("pendentes/r5_icon_constructor_A.png", 48, 48, "A 3×") + chk("pendentes/r5_icon_constructor_B.png", 48, 48, "B 3×") + '</div>')
    o('<p>Recomendo <b>A</b> (a tela fica limpa e o laranja repete o das máquinas na lateral). Nome final: <code>icon_constructor.png</code>.</p>')
    o('<h2>R5.2 · VÉSPER-7 em isométrico (2 formas)</h2><p>Referência principal: o cargueiro iso do dono (blocão hard-surface, chapas em camadas, painéis laranja na lateral, porta traseira aberta com rampa e luz azul dentro, trem de pouso, motores com luz azul) e a nave diagonal pro cockpit e as turbinas. Tudo original, por script (<code>v07_r5_cargo.py</code>, projeção 2:1). Casco ardósia (A) ou creme (B), contorno <code>#1b1630</code>, luzes ciano. Destroço: uma perna quebrada, motor traseiro apagado, pés e chapas soltos na areia, caixas caídas. <b>Nome VESPER-7</b> pintado no costado esquerdo (fonte 3×5 cisalhada pela inclinação do iso).</p>')
    o('<div class="row">' + chk("pendentes/r5_wreck_cargo_A.png", 480, 384, "<b>A</b> cargueiro blocão (referência principal) · 160×128") + chk("pendentes/r5_wreck_cargo_B.png", 480, 384, "<b>B</b> cabine de vidro, asa+turbina e 2 contêineres no convés · 160×128") + '</div>')
    o('<div class="row">' + chk("pendentes/r3_wreck_cargo_A.png", 320, 224, "rodada 3 (3/4 frontal, pendente), pra comparar") + '</div>')
    o('<h3>Contrato proposto</h3><div class="row"><img src="anot_r5_cargo_A.png" width="480" height="384"></div>')
    o('<p><b>Sprite 160×128</b> (lift 32). <b>Pegada de colisão 5×3</b> (160×96), aproximação do casco: o sprite sai dela por cima (antena) e a rampa/caixas saem pra baixo-direita. <b>Boca do porão</b> = tile <code>(3,2)</code> (onde a rampa encosta, alvo do E), chega por <code>(3,3)</code>; caixa de saque em <code>(1,3)</code>. Blit <code>(tx·32, ty·32 − 32)</code>, ordenado pelo pé da pegada.</p>')
    o('<h2>R5.3 · Base espacial em isométrico</h2><p>Mesmo design de vidro aprovado, em diagonal 2:1: tambor circular com janelões e domo de vidro estilhaçado (piso interior visível), eclusa como caixa iso com porta escura, luz azul e rampa descendo pra esquerda, módulo-tanque à direita e 2 painéis solares (um com canto arrancado). Sprite <b>256×168</b>; pegada aproximada <b>8×4</b> (lift 40).</p>')
    o('<div class="row">' + chk("pendentes/r3_wreck_module_glass.png", 448, 384, "3/4 frontal (rodada 3) · 224×192") + chk("pendentes/r5_wreck_module_glass.png", 512, 336, "<b>isométrica</b> (rodada 5) · 256×168") + '</div>')
    o('<img src="anot_r5_glass.png" width="768" height="528"><p><b>Terminal</b> em pedestal na frente do tambor: rect <code>(138,117,20,17)</code> = tile <code>(4,2)</code>, lido de <code>(4,3)</code>. <b>Futura porta</b> = porta da eclusa, rampa terminando no tile <code>(1,3)</code>, chega por <code>(1,4)</code>. <b>Caixa</b> em <code>(5,4)</code>.</p>')
    o('<h2>R5.4 · Prévias 960×540 com o Explorador pra escala</h2><div class="pvs">' +
      "".join(f'<figure><img src="preview_r5_{s}.png" width="960" height="540"><figcaption><b>{l}</b> · base iso à esquerda, VÉSPER-7 A (em cima, caixa aberta) e B (embaixo), sonda aprovada e o Explorador em 3 lugares</figcaption></figure>'
              for s, l in (("dead", "Morto"), ("mist", "Névoa"), ("green", "Verde"))) + '</div>')
    o('<div class="note"><b>Pro Dev (rodada 5)</b>: <code>r5_wreck_cargo_{A,B}.png</code> 160×128, pegada 5×3, lift 32, boca (3,2), chega (3,3), caixa (1,3); <code>r5_wreck_module_glass.png</code> 256×168, pegada 8×4, lift 40, terminal (138,117,20,17), porta (1,3), caixa (5,4); <code>r5_icon_constructor_{A,B}.png</code> 16×16. Sprites maiores que a pegada: ordenar pelo pé da pegada.</div>')
    o('<h2>R5.5 · Decisões do dono</h2><ol class="dec"><li>Construtor: A ou B (laranja)?</li><li>VÉSPER-7: A ou B? Lê como nave agora? O que falta?</li><li>Base isométrica ou a 3/4 frontal (rodada 3)?</li><li>Pegadas: VÉSPER 5×3 e base 8×4 com sprite saindo do retângulo ok?</li></ol>')
    o('<hr style="border-color:#3a2c25;margin:48px 0"><h1 style="color:#a8968a">Rodada 4 (histórico)</h1>')
    return "".join(out)


def page(sec):
    css = """<style>
:root{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;margin:0;padding:32px;max-width:1180px}
h1{margin:6px 0}h2{margin-top:44px;color:var(--gold);border-bottom:1px solid var(--line)}h3{color:var(--cyan)}.eb{color:var(--rust);font:12px monospace;text-transform:uppercase}
img{image-rendering:pixelated}img.soft{image-rendering:auto}.chk{display:inline-block;background:conic-gradient(#3a3a46 25%,#2b2b35 0 50%,#3a3a46 0 75%,#2b2b35 0) 0 0/16px 16px;padding:8px}
.row{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-end}figure{margin:0}figcaption{color:var(--muted);font-size:12px;margin-top:4px}
.note{background:var(--panel);border:1px solid var(--line);padding:10px 16px;border-left:4px solid var(--rust);margin:14px 0}
code{color:var(--cyan)}table{border-collapse:collapse}td,th{border:1px solid var(--line);padding:4px 10px;text-align:left;vertical-align:top}
.dec li{margin:6px 0}.pvs figure{margin:12px 0}
</style>"""
    return css


def write_html(sections):
    head = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Hesper · v0.7 Lore · arte</title>' + page(None) + '</head><body>'
            '<div class="eb">Hesper · Designer · v0.7 Lore</div><h1>Destroços, props e construtor</h1>'
            '<div class="note"><b>v1.0 · o que é</b>: 5 destroços novos a partir da sua referência (2 candidatas pro transportador e pra base espacial), '
            'kit de 16 props 1×1 (sprite + ícone) com mock de sala montada, e o construtor com módulo de scanner (2 candidatas). '
            '<b>Pra aprovar</b>: tudo em <code>pendentes/</code>, nada foi pra <code>assets/sprites/</code>. Estilo: contorno <code>#1b1630</code>, creme/laranja das máquinas, '
            'luz de cima-esquerda, sem anti-aliasing. Gerado por <code>tools/sprites/v07_*.py</code>.</div>')
    (REP / "index.html").write_text(head + "".join(sections) + '</body></html>', encoding="utf-8")


if __name__ == "__main__":
    write_html(main())
    h = hashlib.md5()
    for p in sorted(PEND.glob("*.png")):
        h.update(p.read_bytes())
    print("md5 pendentes:", h.hexdigest())
