#!/usr/bin/env python3
"""v0.7 M4 · report dos destroços maiores (comparação atual × novo × player, anotações, cenas 960×540, HTML).

    python3 tools/sprites/build_wrecks_v07_m4.py          # primeiro: gera os PNGs em pendentes/
    python3 tools/sprites/build_wrecks_v07_m4_report.py   # depois: report em reports/design/v07_m4_destrocos/

Os "atuais" vêm de assets/sprites/wreck_*.png (cópia guardada em reports/design/before/v07_m3_wreck_*.png).
Cenas montadas só com sprites, na ordem do jogo: chão → objetos ordenados pelo pé (destroço pelo pé da pegada,
caixa pela borda de baixo do tile, player pelos pés, com a sombrinha 16×5 embaixo).
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_wrecks_v07_m4 as WR  # noqa: E402
from v07_lib import hsh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPR = ROOT / "assets" / "sprites"
REP = WR.REP
PEND = WR.PEND
BEFORE = ROOT / "reports" / "design" / "before"
T = 32
KINDS = ("cargo", "module", "probe", "robot", "liner")
NAMES = {"cargo": "VÉSPER-7", "module": "Base espacial", "probe": "Sonda", "robot": "Robô de reconhecimento R-2", "liner": "Nave de passageiros ARCA-2"}
OLD = {   # contrato do M3 (bíblia §16)
    "cargo": dict(size=(5, 3), sprite=(160, 128), lift=32, crate=(1, 3), mouth=(3, 2), approach=(3, 3)),
    "module": dict(size=(8, 4), sprite=(256, 168), lift=40, crate=(5, 4), terminal=(4, 2), reads_from=(4, 4),
                   terminal_rect=(138, 117, 20, 17), door=(1, 3)),
    "probe": dict(size=(2, 2), sprite=(64, 64), lift=0, crate=(2, 1), led=(23, 37, 2, 1)),
    "robot": dict(size=(3, 2), sprite=(96, 64), lift=0, crate=(3, 1)),
    "liner": dict(size=(5, 3), sprite=(160, 120), lift=24, crate=(2, 3)),
}
NEW = {"cargo": WR.CARGO, "module": None, "probe": WR.PROBE, "robot": WR.ROBOT, "liner": WR.LINER}


def A(name):
    return Image.open(SPR / name).convert("RGBA")


def newspr(kind):
    return Image.open(PEND / f"wreck_{kind}.png").convert("RGBA")


def sand(stage, x, y):
    return A(f"sand_{stage}_{int(hsh(x, y, 5) * 4)}.png")


def ground(w, h, stage="dead", sx=3, sy=5):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    for y in range((h + T - 1) // T):
        for x in range((w + T - 1) // T):
            img.alpha_composite(sand(stage, x + sx, y + sy), (x * T, y * T))
    return img


def player_shadow():
    s = Image.new("RGBA", (16, 5), (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse([0, 0, 15, 4], fill=(0, 0, 0, 92))
    return s


class Scene:
    """Lista de objetos (pé, imagem, pos) desenhada em ordem do pé, como o Renderer."""

    def __init__(self, img):
        self.img, self.objs = img, []

    def wreck(self, kind, tx, ty, meta, img=None, crate_open=False):
        im = img or newspr(kind)
        w, h = meta["size"]
        self.objs.append(((ty + h) * T, im, (tx * T, ty * T - meta["lift"])))
        cx, cy = meta["crate"]
        self.crate(tx + cx, ty + cy, crate_open)

    def crate(self, tx, ty, empty=False):
        self.objs.append(((ty + 1) * T, A("loot_crate_empty.png" if empty else "loot_crate.png"), (tx * T, ty * T)))

    def player(self, fx, fy, facing="up", frame=None):
        if frame is None:
            im = A(f"player_{facing}.png")
        else:
            strip = A(f"player_walk_{facing}.png")
            im = strip.crop((frame * 32, 0, frame * 32 + 32, 32))
        self.objs.append((fy, None, (fx - 8, fy - 5)))
        self.objs.append((fy + .1, im, (fx - 16, fy - 32)))

    def thing(self, name, tx, ty, foot=None):
        im = A(name)
        self.objs.append((foot or (ty + 1) * T, im, (tx * T + 16 - im.width // 2, (ty + 1) * T - im.height)))

    def draw(self):
        sh = player_shadow()
        for foot, im, pos in sorted(self.objs, key=lambda o: o[0]):
            self.img.alpha_composite(sh if im is None else im, (int(pos[0]), int(pos[1])))
        return self.img


# ---------------------------------------------------------------------------------------------------------------------
def save_before():
    BEFORE.mkdir(parents=True, exist_ok=True)
    for k in KINDS:
        dst = BEFORE / f"v07_m3_wreck_{k}.png"
        if not dst.exists():
            shutil.copyfile(SPR / f"wreck_{k}.png", dst)


def compare(kind, meta):
    """Faixa de areia: atual + player na caixa | novo + player na caixa (1:1)."""
    old, new = A(f"wreck_{kind}.png"), newspr(kind)
    om, nm = OLD[kind], meta
    pad = 2
    w = (om["size"][0] + 3 + nm["size"][0] + 3) * T
    hh = max(om["size"][1] + om["lift"] / T, nm["size"][1] + nm["lift"] / T) + 2.5
    rows = int(hh + .99)
    img = ground(w, rows * T, "dead", 7, 2)
    sc = Scene(img)
    base_row = rows - 3                             # pé dos dois destroços na mesma linha
    otx, oty = 1, base_row - om["size"][1] + 1
    ntx, nty = om["size"][0] + 4, base_row - nm["size"][1] + 1
    sc.wreck(kind, otx, oty, om, img=old)
    sc.wreck(kind, ntx, nty, nm)
    for (tx, ty, m) in ((otx, oty, om), (ntx, nty, nm)):
        ax, ay = m.get("approach", m.get("reads_from", (m["crate"][0], m["crate"][1] + 1)))
        if "approach" not in m and "reads_from" not in m:
            ax, ay = m["crate"][0] - 1, m["crate"][1] + 1
        sc.player((tx + ax) * T + 16, (ty + ay) * T + 20, "up")
    out = sc.draw()
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for (tx, label) in ((otx, "HOJE (M3)"), (ntx, "NOVO (M4)")):
        d.rectangle([tx * T, 4, tx * T + 64, 16], fill=(21, 16, 14, 255))
        d.text((tx * T + 4, 5), label, fill=(242, 196, 109, 255), font=f)
    out.save(REP / f"cmp_{kind}.png")
    return out.size


def lineup():
    """Os 5 novos lado a lado com um player em cada (1:1) e, em cima, os atuais na mesma régua."""
    gap = 2
    cols_new = sum(WR_META[k]["size"][0] + gap for k in KINDS) + 1
    cols_old = sum(OLD[k]["size"][0] + gap for k in KINDS) + 1
    w = max(cols_new, cols_old) * T
    rows = 7 + 11
    img = ground(w, rows * T, "dead", 11, 1)
    sc = Scene(img)
    x = 1
    for k in KINDS:                                   # linha de cima: hoje
        m = OLD[k]
        ty = 5 - m["size"][1]
        sc.wreck(k, x, ty, m, img=A(f"wreck_{k}.png"))
        sc.player((x + m["size"][0]) * T + 20, (ty + m["size"][1]) * T - 2, "down")
        x += m["size"][0] + gap
    x = 1
    for k in KINDS:                                   # linha de baixo: novo
        m = WR_META[k]
        ty = 16 - m["size"][1]
        sc.wreck(k, x, ty, m)
        sc.player((x + m["size"][0]) * T + 20, (ty + m["size"][1]) * T - 2, "down")
        x += m["size"][0] + gap
    out = sc.draw()
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for (y, label) in ((6, "HOJE (M3)"), (T * 7 + 4, "NOVO (M4)")):
        d.rectangle([6, y, 72, y + 12], fill=(21, 16, 14, 255)); d.text((10, y + 1), label, fill=(242, 196, 109, 255), font=f)
    out.save(REP / "escala.png")
    return out.size


COL = dict(grid=(255, 80, 220, 255), mouth=(242, 196, 109, 255), approach=(89, 208, 230, 255), crate=(226, 115, 58, 255),
           term=(127, 214, 122, 255), rect=(255, 255, 255, 255), door=(242, 196, 109, 255))


def annotate(kind, meta, z):
    im = newspr(kind)
    W, H = im.size
    w, h = meta["size"]
    extra = 2 * T
    bg = Image.new("RGBA", (W + T, H + extra), (196, 160, 122, 255))
    bg.alpha_composite(im, (0, 0))
    big = bg.resize((bg.width * z, bg.height * z), Image.NEAREST)
    d = ImageDraw.Draw(big)
    f = ImageFont.load_default()
    L = meta["lift"]

    def tile(t, col, label, width=3):
        x, y = t
        x0, y0 = x * T * z, (L + y * T) * z
        d.rectangle([x0, y0, x0 + T * z - 1, y0 + T * z - 1], outline=col, width=width)
        d.rectangle([x0 + 3, y0 + 3, x0 + 3 + 6 * len(label) + 4, y0 + 15], fill=(21, 16, 14, 255))
        d.text((x0 + 5, y0 + 4), label, fill=col, font=f)
    for x in range(w + 1):
        d.line([(x * T * z, L * z), (x * T * z, (L + h * T) * z)], fill=COL["grid"], width=1)
    for y in range(h + 1):
        d.line([(0, (L + y * T) * z), (w * T * z, (L + y * T) * z)], fill=COL["grid"], width=1)
    d.line([(0, L * z), (W * z, L * z)], fill=COL["grid"], width=2)
    tile(meta["crate"], COL["crate"], f"caixa {meta['crate']}")
    if "mouth" in meta:
        tile(meta["mouth"], COL["mouth"], f"boca {meta['mouth']}")
        tile(meta["approach"], COL["approach"], f"chega {meta['approach']}")
    if "terminal" in meta:
        tile(meta["terminal"], COL["term"], f"terminal {meta['terminal']}")
        tile(meta["reads_from"], COL["approach"], f"lido de {meta['reads_from']}")
        rx, ry, rw, rh = meta["terminal_rect"]
        d.rectangle([(rx - 1) * z, (ry - 1) * z, (rx + rw + 1) * z - 1, (ry + rh + 1) * z - 1], outline=COL["rect"], width=2)
    if "door" in meta:
        tile(meta["door"], COL["door"], f"porta {meta['door']} (arte)", 2)
    if "led" in meta:
        lx, ly, lw, lh = meta["led"]
        d.rectangle([(lx - 1) * z, (ly - 1) * z, (lx + lw + 1) * z - 1, (ly + lh + 1) * z - 1], outline=COL["rect"], width=2)
    d.text((4, 4), f"sprite {W}x{H} · pegada {w}x{h} · lift {L}", fill=(21, 16, 14, 255), font=f)
    big.save(REP / f"anot_{kind}.png")
    return big.size


def scene_vesper(stage):
    img = ground(960, 544, stage, 3, 5)
    sc = Scene(img)
    m = WR_META["cargo"]
    tx, ty = 3, 5
    sc.wreck("cargo", tx, ty, m)
    mx, my = m["approach"]
    sc.player((tx + mx) * T + 16, (ty + my) * T + 14, "up", frame=1)       # chegando na boca do porão
    sc.wreck("probe", 21, 3, WR_META["probe"])
    sc.wreck("robot", 19, 11, WR_META["robot"], crate_open=True)
    sc.player(24 * T + 4, 14 * T + 12, "down")
    for (x, y) in ((16, 9), (1, 13), (27, 9), (15, 15), (2, 3)):
        sc.thing("rock_small.png", x, y)
    if stage == "green":
        for (x, y, k) in ((17, 3, "plant_bush.png"), (28, 6, "plant_flower.png"), (1, 1, "plant_tree.png"), (14, 13, "plant_bush.png")):
            sc.thing(k, x, y, foot=y * T + 30)
    sc.draw().crop((0, 0, 960, 540)).save(REP / f"preview_vesper_{stage}.png")


def scene_base(stage):
    img = ground(960, 544, stage, 9, 2)
    sc = Scene(img)
    m = WR_META["module"]
    tx, ty = 1, 6
    sc.wreck("module", tx, ty, m)
    rx, ry = m["reads_from"]
    sc.player((tx + rx) * T + 16, (ty + ry) * T + 12, "up")                # lendo o terminal
    sc.wreck("liner", 19, 9, WR_META["liner"])
    sc.player(25 * T + 10, 14 * T + 20, "side")
    for (x, y) in ((17, 4), (28, 3), (16, 15), (2, 15)):
        sc.thing("rock_small.png", x, y)
    if stage == "green":
        for (x, y, k) in ((16, 2, "plant_tree.png"), (27, 6, "plant_bush.png"), (17, 14, "plant_flower.png")):
            sc.thing(k, x, y, foot=y * T + 30)
    sc.draw().crop((0, 0, 960, 540)).save(REP / f"preview_base_{stage}.png")


def hatch_zoom():
    """Recorte da boca do porão com o chão embaixo (fundo do card animado do player chegando)."""
    m = WR_META["cargo"]
    img = ground(10 * T, 10 * T, "dead", 3, 5)
    sc = Scene(img)
    sc.wreck("cargo", 0, 2, m)
    x0, y0, cw, ch = HZ
    out = sc.draw().crop((x0 * T, y0 * T, (x0 + cw) * T, (y0 + ch) * T))
    out.save(REP / "hatch_bg.png")
    return out.size


# ---------------------------------------------------------------------------------------------------------------------
def fmt(t):
    return "—" if t is None else f"({t[0]},{t[1]})"


def html(sizes, fit, r2html=""):
    css = (ROOT / "reports" / "design" / "index.html").read_text(encoding="utf-8")
    style = css[css.index("<style>"):css.index("</style>") + 8].replace("url(../../assets", "url(../../../assets")
    o = []
    a = o.append
    a('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
      '<title>Hesper · v0.7 M4 · Destroços maiores</title>' + style +
      '<style>.big img{image-rendering:pixelated}.scroll{overflow:auto;max-width:100%%;border:1px solid var(--line)}'
      '.tb td code{white-space:nowrap}.hz{position:relative;width:%dpx;height:%dpx;background:url(hatch_bg.png) 0 0/%dpx %dpx;image-rendering:pixelated;border:1px solid var(--line)}'
      '.hz .pl{position:absolute;left:%dpx;width:96px;height:96px;background:url(../../../assets/sprites/player_walk_up.png) 0 0/384px 96px;image-rendering:pixelated;'
      'animation:walk .5s steps(4) infinite,come 3.2s steps(32) infinite}'
      '@keyframes walk{from{background-position:0 0}to{background-position:-384px 0}}'
      '@keyframes come{0%%{top:%dpx}75%%{top:%dpx}100%%{top:%dpx}}'
      '.led{position:absolute;background:#3b3f46;animation:led 1.667s steps(1) infinite}@keyframes led{0%%{opacity:1}50%%{opacity:0}}'
      '.pr{position:relative;display:inline-block}</style></head><body><div class="wrap">' % hatch_css())
    a('<header><div class="eyebrow">Hesper · Designer · v0.7 M4 · destroços maiores · v1.3 (rodada 4)</div><h1>Destroços maiores</h1>')
    a('<div class="v2"><b>v1.0 · o que mudou</b><ul>'
      '<li>Os <b>5 destroços</b> foram redesenhados <b>maiores</b>, com o mesmo design aprovado no M3. Não é bitmap ampliado: cada desenho roda de novo numa resolução maior (contorno e linhas continuam com 1 px) e ganha detalhe novo.</li>'
      '<li><b>VÉSPER-7</b> com 2× o tamanho (5×3 → <b>10×5</b>). O <b>porão</b> agora tem fundo de verdade: piso claro, parede com costelas e fita de LED, uma <b>porta acesa</b> lá dentro que leva pro corredor (o convite pro interior), carga presa à esquerda, moldura com faixa de perigo e lâmpada âmbar. A <b>rampa ficou mais comprida</b> e o pé dela encosta na borda de baixo da pegada. Na frente ficou a chapa do casco arrancada e os caixotes que caíram.</li>'
      '<li><b>Base espacial</b> com 1,75× (8×4 → <b>14×5</b>). O <b>terminal foi pra frente</b>, na borda de baixo da pegada, maior (32×26) e com cabo até o tambor. A porta da eclusa ficou entreaberta, com luz de emergência. No chão: painel solar arrancado, chapas e cacos do domo.</li>'
      '<li><b>Sonda</b> 1,5× (2×2 → <b>3×2</b>), <b>robô R-2</b> 1,67× (3×2 → <b>5×2</b>, com "R-2" no capô, painel solar no lombo, tubos de amostra) e <b>ARCA-2</b> 1,8× (5×3 → <b>9×4</b>, com o nome no casco, mais janelas, para-brisa trincado e a <b>bagagem dos colonos</b> espalhada).</li>'
      '<li>Nada foi pra <code>assets/</code>: tudo está em <code>pendentes/</code>. Os atuais estão guardados em <code>../before/v07_m3_wreck_*.png</code>.</li></ul></div>')
    a('<div class="status"><span class="chip ok">5/5 no tamanho do contrato proposto</span><span class="chip ok">alpha só 0/255 (+ sombra 92)</span>'
      f'<span class="chip ok">{fit}</span><span class="chip">script: tools/sprites/build_wrecks_v07_m4.py</span></div></header>')
    a(r2html)
    a('<hr style="border-color:#3a2c25;margin:56px 0 0"><h1 style="color:#a8968a;margin-top:28px">Rodada 1 (histórico)</h1>')

    a('<section><h2>Escala: hoje × novo, com o player</h2><p class="lede">Tudo 1:1, na mesma régua, com um Explorador do lado de cada destroço. Em cima estão os de hoje (M3) e embaixo os novos. A imagem é larga: role pro lado.</p>'
      f'<div class="scroll"><img src="escala.png" width="{sizes["escala"][0]}" height="{sizes["escala"][1]}" style="image-rendering:pixelated;display:block"></div></section>')

    a('<section><h2>Cada destroço · hoje × novo (2×)</h2><div class="pvs">')
    for k in KINDS:
        w_, h_ = sizes["cmp_" + k]
        a(f'<figure class="pv"><div class="scroll"><img src="cmp_{k}.png" width="{w_ * 2}" height="{h_ * 2}" style="image-rendering:pixelated;max-width:none;width:{w_ * 2}px"></div>'
          f'<figcaption><b>{NAMES[k]}</b><span>{CAPS[k]}</span></figcaption></figure>')
    a('</div></section>')

    a('<section><h2>Chegando na boca do porão</h2><p class="lede">O Explorador anda até o pé da rampa: é o tile de onde o E entra. Animação em CSS, 3×.</p>'
      '<div class="cards"><div class="hz"><div class="pl"></div></div>'
      '<figure class="spr"><div class="chk pr"><img src="pendentes/wreck_probe.png" width="288" height="288">'
      f'<i class="led" style="left:{8 + WR.PROBE["led"][0] * 3}px;top:{8 + WR.PROBE["led"][1] * 3}px;width:{WR.PROBE["led"][2] * 3}px;height:{WR.PROBE["led"][3] * 3}px"></i></div>'
      '<figcaption><span>sonda 3× · LED piscando (o render apaga o retângulo do LED)</span></figcaption></figure></div></section>')

    a('<section><h2>Prévias 960×540</h2><div class="pvs">')
    for st, lab in (("dead", "Morto"), ("mist", "Névoa"), ("green", "Verde")):
        a(f'<figure class="pv"><img src="preview_vesper_{st}.png" width="960" height="540"><figcaption><b>{lab} · VÉSPER-7</b><span>o player subindo pro porão, sonda e robô (caixa aberta) atrás</span></figcaption></figure>')
    for st, lab in (("dead", "Morto"), ("mist", "Névoa"), ("green", "Verde")):
        a(f'<figure class="pv"><img src="preview_base_{st}.png" width="960" height="540"><figcaption><b>{lab} · Base e ARCA-2</b><span>o player lendo o terminal da base, ARCA-2 à direita</span></figcaption></figure>')
    a('</div></section>')

    a('<section><h2>Sprites novos (1:1 e ampliados)</h2><div class="cards">')
    for k in KINDS:
        m = WR_META[k]
        W, H = m["sprite"]
        zz = 2 if W > 200 else 3
        a(f'<figure class="spr"><div class="chk"><img src="pendentes/wreck_{k}.png" width="{W}" height="{H}"><img src="pendentes/wreck_{k}.png" width="{W * zz}" height="{H * zz}"></div>'
          f'<figcaption>wreck_{k}.png<span>{W}×{H} · 1× e {zz}×</span></figcaption></figure>')
    a('</div></section>')

    a('<section><h2>Pro Dev integrar</h2><div class="box dev">')
    a('<p>Cada anotação mostra a grade da <b>pegada</b> (magenta, começa em y = lift), a <b>caixa</b> (laranja), a <b>boca/terminal</b> (dourado/verde), o tile <b>de onde se chega/lê</b> (ciano) e o <b>contorno do E</b> e o LED (branco, em px do sprite).</p>')
    a('<table class="tb"><tr><th>kind</th><th>pegada</th><th>sprite</th><th>tamanho</th><th>lift</th><th>caixa</th><th>terminal</th><th>lido de</th><th>boca / porta</th><th>chega por</th><th>contorno / LED (px)</th></tr>')
    for k in KINDS:
        m = WR_META[k]
        mouth = fmt(m.get("mouth")) + " boca" if "mouth" in m else (fmt(m.get("door")) + " porta, só arte" if "door" in m else "—")
        appr = fmt(m.get("approach") or m.get("door_approach"))
        rect = m.get("terminal_rect") or m.get("led")
        rect = "—" if rect is None else ("contorno " if "terminal_rect" in m else "LED ") + f"({', '.join(map(str, rect))})"
        a(f'<tr><td><code>{k}</code><br>{NAMES[k]}</td><td><b>{m["size"][0]}×{m["size"][1]}</b><br><span style="color:var(--muted)">era {OLD[k]["size"][0]}×{OLD[k]["size"][1]}</span></td>'
          f'<td><code>wreck_{k}</code></td><td>{m["sprite"][0]}×{m["sprite"][1]}</td><td>{m["lift"]}</td><td>{fmt(m["crate"])}</td>'
          f'<td>{fmt(m.get("terminal"))}</td><td>{fmt(m.get("reads_from"))}</td><td>{mouth}</td><td>{appr}</td><td><code>{rect}</code></td></tr>')
    a('</table>')
    a('<ul>'
      '<li><b>Blit e ordem: não muda nada.</b> O sprite vai em <code>(tx·32, ty·32 − lift)</code> e é ordenado pelo pé da pegada (<code>anchor</code>). Todos seguem <code>sprite = (pegada_w·32, pegada_h·32 + lift)</code> (o teste de contrato já confere isso). A caixa continua sendo o <code>loot_crate</code> 32×32 por cima, no tile dela.</li>'
      '<li><b>Toda marca de interação fica fora da pegada ou na fileira de baixo dela.</b> Caixas: todas fora (embaixo ou do lado). Boca do porão e terminal: na <b>última fileira</b> da pegada, e o tile de chegar/ler fica <b>logo abaixo</b>, fora dela. Nenhuma marca caiu dentro da parte sólida (o furo do "(4,3)" do M3 não se repete).</li>'
      '<li><b>VÉSPER-7</b>: <code>hatch_in_target</code> passa de <code>(tx+3, ty+2)</code> pra <code>(tx+8, ty+4)</code>, e <code>surface_exit</code> pra <code>((tx+8.5)·T, (ty+5)·T + 24)</code>. Sugestão: virar campo do <code>WreckSpec</code> (ex. <code>hatch=(8, 4)</code>) em vez de número no <code>systems.py</code>. O pé da rampa desenhado cai em x 240–310 / y 190–215 do sprite, dentro do tile (8,4).</li>'
      '<li><b>Base espacial</b>: terminal <code>(8,4)</code> lido de <code>(8,5)</code>, que é logo abaixo, então dá até pra deixar <code>reads_from=None</code>. <code>terminal_rect=(251, 224, 32, 26)</code>. A porta da eclusa <code>(2,4)</code> continua só arte.</li>'
      '<li><b>Sonda</b>: o LED piscante mudou de lugar. No <code>draw_wreck</code>, troque <code>fill(..., (x+23, y+37, 2, 1))</code> por <code>(x+34, y+55, 3, 2)</code>.</li>'
      '<li><b>Robô no bolsão</b> (<code>WRECK_RICH_KIND = "robot"</code>): 5×2 no <code>wreck_spot</code> (x0+1, top+1) ocupa x0+1..x0+5. A caixa (2,2) cai em (x0+3, top+3), e o contêiner (x0+6, top+1) fica livre e com o tile de baixo dele livre. Tudo dentro do interior 8×7. Por isso a caixa do robô foi pra baixo: do lado direito, ela cairia embaixo do contêiner.</li>'
      '<li><b>Fallback</b> (<code>art.wreck</code>) e <code>tests/test_wrecks.py</code> (<code>test_specs_match_sprite_contract</code>) leem os números novos da tabela.</li>'
      '<li><b>Promover</b>: copiar <code>pendentes/wreck_*.png</code> → <code>assets/sprites/</code> (mesmos nomes). O <code>build_sprites.py</code> ainda gera os antigos e não foi rodado.</li></ul>')
    for k in KINDS:
        w_, h_ = sizes["anot_" + k]
        a(f'<h3 style="margin-top:22px">{NAMES[k]}</h3><div class="scroll"><img src="anot_{k}.png" width="{w_}" height="{h_}" style="image-rendering:pixelated;display:block;max-width:none"></div>')
    a('</div></section>')

    a('<section><h2>Geração do mundo: cabe?</h2><div class="box"><p>Testei com o gerador de verdade (<code>generate_surface</code>), trocando só a pegada e a caixa do <code>SPECS</code> pelas novas, sem mexer em <code>WRECK_DIST</code>, <code>WRECK_SPACING</code> nem <code>WRECK_MARGIN</code>:</p>'
      f'<ul><li><b>Proposta</b> (10×5, 14×5, 3×2, 5×2, 9×4): {fit}.</li>'
      '<li><b>Teste de estresse</b> (VÉSPER 12×6, base 14×7, ARCA 11×5, robô 5×3, sonda 3×3), 60 seeds: nenhum destroço perdido, 2 ruínas em todos.</li>'
      '<li><b>Teto sugerido</b>: até <b>12×6</b> nas naves e <b>14×7</b> na base ainda cabe com folga. Acima disso eu não testei. Com a pegada maior, o sorteio às vezes aceita um lugar um pouco mais longe do alvo de distância (o <code>jitter</code> cresce com as tentativas), mas a ordem perto → longe continua garantida.</li></ul></div></section>')

    a('<section><h2>Decisões pro dono</h2><div class="box"><ol>'
      '<li>A escala nova tá boa? VÉSPER 2×, base 1,75×, ARCA 1,8×, robô 1,67×, sonda 1,5×.</li>'
      '<li>O porão da VÉSPER chama pra entrar? (porta acesa no fundo, rampa comprida, luz no piso)</li>'
      '<li>Terminal da base na frente, longe do tambor: ok?</li></ol></div></section>')
    a('</div></body></html>')
    (REP / "index.html").write_text("".join(o), encoding="utf-8")


HZ = (4, 1, 6, 9)   # recorte do card da boca: x0, y0, largura, altura (tiles)

CAPS = {
    "cargo": "5×3 → 10×5 · 160×128 → 320×224 · porão fundo com porta acesa, rampa até a borda da pegada · o player no tile de chegar",
    "module": "8×4 → 14×5 · 256×168 → 448×294 · terminal na frente, eclusa entreaberta · o player no tile de ler",
    "probe": "2×2 → 3×2 · 64×64 → 96×96 · o player do lado da caixa",
    "robot": "3×2 → 5×2 · 96×64 → 160×104 · caixa embaixo (cabe no bolsão)",
    "liner": "5×3 → 9×4 · 160×120 → 288×208 · bagagem e poltronas espalhadas",
}


def hatch_css():
    """Posição do player animado no card da boca (recorte 5..10 × 2..9 tiles da mini-cena, destroço em ty = 2, 3×)."""
    mx, my = WR_META["cargo"]["approach"]
    x0, y0, cw, ch = HZ
    fx, fy = mx * T + 16 - x0 * T, (2 + my) * T + 14 - y0 * T          # pés no recorte (destroço em ty = 2)
    left, top = (fx - 16) * 3, (fy - 32) * 3
    return (cw * T * 3, ch * T * 3, cw * T * 3, ch * T * 3, left, ch * T * 3 - 96, top, top)


def check_contract():
    bad = []
    for k in KINDS:
        m = WR_META[k]
        p = PEND / f"wreck_{k}.png"
        im = Image.open(p)
        if im.size != tuple(m["sprite"]) or im.size != (m["size"][0] * T, m["size"][1] * T + m["lift"]):
            bad.append((k, im.size))
        w, h = m["size"]
        marks = [m["crate"]] + [m[x] for x in ("approach", "reads_from", "door_approach") if x in m]
        for (x, y) in marks:                         # fora da pegada
            if 0 <= x < w and 0 <= y < h:
                bad.append((k, "marca dentro da pegada", (x, y)))
        for x in ("mouth", "terminal", "door"):
            if x in m and m[x][1] != h - 1:
                bad.append((k, f"{x} fora da fileira de baixo", m[x]))
    r2 = {"wreck_cargo_r2.png": (320, 224), "wreck_module_r2.png": (448, 294), "wreck_probe_r2.png": (96, 96),
          "wreck_cargo_r3_A.png": (384, 240), "wreck_cargo_r3_B.png": (384, 240),
          "wreck_cargo_r4_A.png": (448, 272), "wreck_cargo_r4_B.png": (448, 272),
          "wreck_robot_r2_A.png": (96, 72), "wreck_robot_r2_B.png": (96, 72), "wreck_liner_r2_A.png": (288, 208), "wreck_liner_r2_B.png": (288, 208)}
    for nm, sz in r2.items():
        if (PEND / nm).exists():
            im = Image.open(PEND / nm)
            import numpy as np
            al = np.array(im)[:, :, 3] > 0
            if im.size != sz or al[0].any() or al[-1].any() or al[:, 0].any() or al[:, -1].any():
                bad.append((nm, "tamanho ou peça na borda"))
    extras = sorted(set(p.name for p in PEND.glob("*.png")) - {f"wreck_{k}.png" for k in KINDS} - set(r2))
    return bad, extras


def main(fit="seeds 0–199: nenhum destroço perdido"):
    global WR_META
    REP.mkdir(parents=True, exist_ok=True)
    WR_META = {}
    for k, fn in (("cargo", WR.cargo), ("module", WR.module), ("probe", WR.probe), ("robot", WR.robot), ("liner", WR.liner)):
        WR_META[k] = fn().meta
    bad, extras = check_contract()
    assert not bad and not extras, (bad, extras)
    save_before()
    sizes = {"escala": lineup()}
    for k in KINDS:
        sizes["cmp_" + k] = compare(k, WR_META[k])
        sizes["anot_" + k] = annotate(k, WR_META[k], 2 if k == "module" else 3)
    for st in ("dead", "mist", "green"):
        scene_vesper(st); scene_base(st)
    hatch_zoom()
    html(sizes, fit, r4_section() + '<hr style="border-color:#3a2c25;margin:56px 0 0">' + r3_section() + '<hr style="border-color:#3a2c25;margin:56px 0 0">' + r2_section())
    h = hashlib.md5()
    for p in sorted(PEND.glob("*.png")):
        h.update(p.read_bytes())
    print("contrato ok · md5 pendentes:", h.hexdigest())


# =====================================================================================================================
# Rodada 2: robô e ARCA-2 em iso (A/B) + correções da base (anexo encavalado), da VÉSPER e da sonda (peça na borda)
# =====================================================================================================================
import build_wrecks_v07_m4_r2 as R2  # noqa: E402
FIT_R2 = "seeds 0–199 com robô 3×2 e ARCA 9×4: nenhum destroço perdido, 2 ruínas em todos"


def r2img(name):
    return Image.open(PEND / f"{name}.png").convert("RGBA")


def r2_compare(kind, names, labels, metas):
    """Faixa de areia com as versões lado a lado, cada uma com o player na caixa, mesmo pé."""
    rows = max(m["size"][1] + m["lift"] / T for m in metas) + 3
    rows = int(rows + .99)
    cols = sum(m["size"][0] + 3 for m in metas) + 1
    img = ground(cols * T, rows * T, "dead", 5, 3)
    sc = Scene(img)
    x = 1
    pos = []
    for nm, m in zip(names, metas):
        ty = rows - 2 - m["size"][1]
        sc.wreck(kind, x, ty, m, img=r2img(nm) if nm else A(f"wreck_{kind}.png"))
        cx, cy = m["crate"]
        sc.player((x + cx) * T + 16, (ty + cy + 1) * T + 20, "up")
        pos.append(x)
        x += m["size"][0] + 3
    out = sc.draw()
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for x, lab in zip(pos, labels):
        d.rectangle([x * T, 4, x * T + 6 * len(lab) + 8, 16], fill=(21, 16, 14, 255))
        d.text((x * T + 4, 5), lab, fill=(242, 196, 109, 255), font=f)
    fn = f"r2_cmp_{kind}.png"
    out.save(REP / fn)
    return fn, out.size


def r2_fix_pair(kind, crop, z):
    """Antes × depois de uma correção (recorte ampliado)."""
    a, b = A(f"wreck_{kind}.png") if False else Image.open(PEND / f"wreck_{kind}.png").convert("RGBA"), r2img(f"wreck_{kind}_r2")
    x0, y0, x1, y1 = crop
    w, h = x1 - x0, y1 - y0
    out = Image.new("RGBA", (w * 2 + 8, h), (196, 160, 122, 255))
    out.alpha_composite(a.crop(crop), (0, 0)); out.alpha_composite(b.crop(crop), (w + 8, 0))
    d = ImageDraw.Draw(out)
    d.rectangle([w, 0, w + 7, h], fill=(21, 16, 14, 255))
    out = out.resize((out.width * z, out.height * z), Image.NEAREST)
    fn = f"r2_fix_{kind}.png"
    out.save(REP / fn)
    return fn, out.size


def r2_scene(stage):
    img = ground(960, 544, stage, 13, 4)
    sc = Scene(img)
    lm = R2.LINER_R2
    sc.wreck("liner", 1, 3, lm, img=r2img("wreck_liner_r2_A"))
    sc.wreck("liner", 12, 3, lm, img=r2img("wreck_liner_r2_B"), crate_open=True)
    rm = R2.ROBOT_R2
    sc.wreck("robot", 23, 4, rm, img=r2img("wreck_robot_r2_A"))
    sc.wreck("robot", 23, 10, rm, img=r2img("wreck_robot_r2_B"))
    sc.player(4 * T + 16, 8 * T + 20, "up")
    sc.player(16 * T + 6, 8 * T + 22, "side")
    sc.player(26 * T + 18, 6 * T + 4, "down")
    sc.player(27 * T + 4, 12 * T + 18, "up")
    for (x, y) in ((22, 1), (10, 13), (20, 14), (2, 14), (29, 8)):
        sc.thing("rock_small.png", x, y)
    if stage == "green":
        for (x, y, k) in ((11, 1, "plant_tree.png"), (21, 9, "plant_bush.png"), (6, 14, "plant_flower.png")):
            sc.thing(k, x, y, foot=y * T + 30)
    out = sc.draw().crop((0, 0, 960, 540))
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for (x, y, lab) in ((1 * T, 4, "ARCA-2 A"), (12 * T, 4, "ARCA-2 B"), (23 * T, 2 * T + 8, "R-2 A"), (23 * T, 8 * T + 8, "R-2 B")):
        d.rectangle([x, y, x + 6 * len(lab) + 8, y + 12], fill=(21, 16, 14, 255)); d.text((x + 4, y + 1), lab, fill=(242, 196, 109, 255), font=f)
    fn = f"r2_preview_{stage}.png"
    out.save(REP / fn)
    return fn


def r2_annot(kind, name, meta, z):
    im = r2img(name)
    W, H = im.size
    w, h = meta["size"]
    L = meta["lift"]
    bg = Image.new("RGBA", (W + T, H + 2 * T), (196, 160, 122, 255))
    bg.alpha_composite(im, (0, 0))
    big = bg.resize((bg.width * z, bg.height * z), Image.NEAREST)
    d = ImageDraw.Draw(big)
    f = ImageFont.load_default()
    for x in range(w + 1):
        d.line([(x * T * z, L * z), (x * T * z, (L + h * T) * z)], fill=COL["grid"], width=1)
    for y in range(h + 1):
        d.line([(0, (L + y * T) * z), (w * T * z, (L + y * T) * z)], fill=COL["grid"], width=1)
    cx, cy = meta["crate"]
    d.rectangle([cx * T * z, (L + cy * T) * z, (cx + 1) * T * z - 1, (L + cy * T + T) * z - 1], outline=COL["crate"], width=3)
    d.text((cx * T * z + 4, (L + cy * T) * z + 4), f"caixa {meta['crate']}", fill=COL["crate"], font=f)
    fn = f"r2_anot_{name}.png"
    big.save(REP / fn)
    return fn, big.size


def r2_section():
    R2.main()
    WR.main()
    rm, lm = R2.ROBOT_R2, R2.LINER_R2
    rob = r2_compare("robot", [None, "wreck_robot", "wreck_robot_r2_A", "wreck_robot_r2_B"], ["M3 (jogo)", "rodada 1", "R2 A", "R2 B"],
                     [OLD["robot"], WR.ROBOT, rm, rm])
    lin = r2_compare("liner", ["wreck_liner", "wreck_liner_r2_A", "wreck_liner_r2_B"], ["rodada 1", "R2 A", "R2 B"], [WR.LINER, lm, lm])
    fixes = [r2_fix_pair("module", (150, 20, 448, 294), 2), r2_fix_pair("cargo", (0, 120, 320, 224), 3), r2_fix_pair("probe", (0, 20, 96, 96), 4)]
    scenes = [r2_scene(st) for st in ("dead", "mist", "green")]
    anns = [r2_annot("robot", f"wreck_robot_r2_{v}", rm, 4) for v in "AB"] + [r2_annot("liner", f"wreck_liner_r2_{v}", lm, 2) for v in "AB"]
    o = []
    a = o.append
    a('<h1 style="color:#a8968a;margin-top:40px">Rodada 2 (aprovada pelo dono: ARCA-2 A e B, robô A e B sorteados pela seed; correções ok)</h1>')
    a('<div class="v2"><b>v1.1 · o que mudou</b><ul>'
      '<li><b>Robô R-2</b> refeito em <b>isométrico</b> e <b>menor</b>, no jeito de robozinho simpático: corpo-caixa creme com faixa laranja e grade na frente, '
      'esteiras dos dois lados (rodas na lateral e sapatas), cabeça <b>binocular</b> num pescoço, bracinhos dobrados, painel solar no lombo e antena com LED. '
      'Fica com <b>~1,5× a altura do player</b> e cabe em <b>3×2</b> (sprite 96×72, lift 8). '
      '<b>A</b>: parado, empoeirado, a lente esquerda rachada. <b>B</b>: tombado pro lado direito com a esteira afundada na areia, cabeça caída pra frente, uma lente rachada e a outra apagada, um braço pendurado, painel trincado e uma roda solta.</li>'
      '<li><b>ARCA-2</b> refeita em <b>isométrico</b>, no mesmo padrão da VÉSPER: casco cilíndrico creme de nariz redondo, cabine com montantes, faixa, fileira de vigias (algumas apagadas), nome pintado, deriva, dois motores e trem de pouso. '
      'Uma parte do casco foi <b>desmontada de propósito</b> (LOG do dia 2): as chapas foram tiradas em quadros certinhos, com costelas e longarinas à mostra, a parede de dentro e poltronas faltando lá dentro, cabos puxados até o chão e as chapas tiradas <b>empilhadas</b> do lado. Bagagem e caixotes dos colonos estão espalhados. '
      '<b>A</b>: faixa laranja, o trecho do meio aberto, as duas asas. <b>B</b>: faixa ciano, a metade de trás quase toda aberta e a asa de perto também desmontada (sobrou o toco com as nervuras e os pedaços encostados). Continua <b>9×4</b>.</li>'
      '<li><b>Base espacial</b> (<code>wreck_module_r2.png</code>): o anexo da direita (caixa creme com escada) estava encavalado no anel do domo, porque era desenhado <b>antes</b> do tambor estando na frente dele. Agora ele fica 8 mais pra frente e é desenhado <b>depois</b>. Os painéis solares foram pra trás-direita do tambor (sem cortar o domo), o painel caído saiu do pé do anexo e a ponta da antena saiu da borda de cima. As marcas não mudaram.</li>'
      '<li><b>VÉSPER-7</b> (<code>wreck_cargo_r2.png</code>): o caixote azul caído do lado da rampa saía pela borda de baixo do canvas e o caixote da esquerda encostava na borda esquerda. Os dois vieram pra dentro (o caixotinho do lado da rampa foi pro pé do casco). As marcas não mudaram.</li>'
      '<li><b>Sonda</b> (<code>wreck_probe_r2.png</code>): conferindo todas as bordas, os dois painéis solares encostavam na esquerda e na direita (a ponta do da direita era cortada). Agora estão um tiquinho pra dentro.</li>'
      '<li>Conferi as 4 bordas de todos: as versões r2 não encostam em nenhuma.</li></ul></div>')
    a(f'<div class="status"><span class="chip ok">{FIT_R2}</span><span class="chip">script: tools/sprites/build_wrecks_v07_m4_r2.py</span></div>')
    a('<section><h2>R2 · Prévias 960×540</h2><div class="pvs">' + "".join(
        f'<figure class="pv"><img src="{fn}" width="960" height="540"><figcaption><b>{lab}</b><span>ARCA-2 A e B em cima, robô A e B à direita, Explorador em 4 lugares (1:1)</span></figcaption></figure>'
        for fn, lab in zip(scenes, ("Morto", "Névoa", "Verde"))) + '</div></section>')
    for (fn, sz), title, cap in ((rob, "R2 · Robô R-2: M3 × rodada 1 × A × B (2×)", "Cada um com o player na caixa. O novo é menor que a rodada 1 e um pouco maior que o player."),
                                 (lin, "R2 · ARCA-2: rodada 1 × A × B (2×)", "Cada um com o player na caixa (3,4).")):
        a(f'<section><h2>{title}</h2><p class="lede">{cap}</p><div class="scroll"><img src="{fn}" width="{sz[0] * 2}" height="{sz[1] * 2}" style="image-rendering:pixelated;display:block;max-width:none;width:{sz[0] * 2}px"></div></section>')
    a('<section><h2>R2 · Candidatas ampliadas</h2><div class="cards">')
    for v in "AB":
        a(f'<figure class="spr"><div class="chk"><img src="pendentes/wreck_robot_r2_{v}.png" width="96" height="72"><img src="pendentes/wreck_robot_r2_{v}.png" width="384" height="288"></div><figcaption>wreck_robot_r2_{v}.png<span>96×72 · 1× e 4×</span></figcaption></figure>')
    for v in "AB":
        a(f'<figure class="spr"><div class="chk"><img src="pendentes/wreck_liner_r2_{v}.png" width="576" height="416"></div><figcaption>wreck_liner_r2_{v}.png<span>288×208 · 2×</span></figcaption></figure>')
    a('</div></section>')
    a('<section><h2>R2 · Correções: antes × depois</h2><div class="pvs">')
    for (fn, sz), lab in zip(fixes, ("Base espacial: o anexo separado do anel do domo e desenhado na ordem certa, painéis atrás (2×)",
                                     "VÉSPER-7: os caixotes que saíam pela borda de baixo e pela esquerda (3×)",
                                     "Sonda: os painéis que encostavam nas bordas (4×)")):
        a(f'<figure class="pv"><div class="scroll"><img src="{fn}" width="{sz[0]}" height="{sz[1]}" style="image-rendering:pixelated;display:block;max-width:none"></div><figcaption><b>antes | depois</b><span>{lab}</span></figcaption></figure>')
    a('</div></section>')
    a('<section><h2>R2 · Pro Dev</h2><div class="box dev"><table class="tb"><tr><th>kind</th><th>arquivo</th><th>pegada</th><th>sprite</th><th>lift</th><th>caixa</th><th>outras marcas</th></tr>'
      '<tr><td><code>robot</code></td><td><code>wreck_robot_r2_{A,B}</code> → <code>wreck_robot</code></td><td><b>3×2</b></td><td>96×72</td><td>8</td><td>(3,1)</td><td>—</td></tr>'
      '<tr><td><code>liner</code></td><td><code>wreck_liner_r2_{A,B}</code> → <code>wreck_liner</code></td><td>9×4</td><td>288×208</td><td>80</td><td>(3,4)</td><td>—</td></tr>'
      '<tr><td><code>module</code></td><td><code>wreck_module_r2</code> → <code>wreck_module</code></td><td>14×5</td><td>448×294</td><td>134</td><td>(10,5)</td><td>terminal (8,4), lido de (8,5), contorno (251,224,32,26), porta (2,4) só arte</td></tr>'
      '<tr><td><code>cargo</code></td><td><code>wreck_cargo_r2</code> → <code>wreck_cargo</code></td><td>10×5</td><td>320×224</td><td>64</td><td>(2,5)</td><td>boca (8,4), chega por (8,5)</td></tr>'
      '<tr><td><code>probe</code></td><td><code>wreck_probe_r2</code> → <code>wreck_probe</code></td><td>3×2</td><td>96×96</td><td>32</td><td>(3,1)</td><td>LED (34,55,3,2)</td></tr></table>'
      '<ul><li>Só o <b>robô</b> muda de contrato em relação à rodada 1: de 5×2 / 160×104 / lift 40 / caixa (2,2) pra <b>3×2 / 96×72 / lift 8 / caixa (3,1)</b> (a pegada volta à do M3; o sprite passa 8 px pra cima por causa da antena).</li>'
      '<li><b>Robô no bolsão</b> (<code>WRECK_RICH_KIND = "robot"</code>): 3×2 no <code>wreck_spot</code> (x0+1, top+1) ocupa x0+1..x0+3. A caixa (3,1) cai em (x0+4, top+2), e o contêiner (x0+6, top+1) e o tile de baixo dele ficam livres. Tudo dentro do interior 8×7.</li>'
      '<li>Base, VÉSPER e sonda: mesmo contrato da rodada 1, só troca o PNG.</li>'
      '<li>Promover: copiar a candidata escolhida pra <code>assets/sprites/wreck_&lt;kind&gt;.png</code>.</li></ul>')
    for fn, sz in anns:
        a(f'<div class="scroll" style="margin-top:12px"><img src="{fn}" width="{sz[0]}" height="{sz[1]}" style="image-rendering:pixelated;display:block;max-width:none"></div>')
    a('</div></section>')
    a('<section><h2>R2 · Decisões pro dono</h2><div class="box"><ol><li>Robô: A (parado) ou B (tombado)? O tamanho (~1,5× o player) tá bom?</li>'
      '<li>ARCA-2: A (faixa laranja, meio aberto) ou B (faixa ciano, metade de trás aberta e asa desmontada)?</li>'
      '<li>As correções da base, da VÉSPER e da sonda resolveram?</li></ol></div></section>')
    return "".join(o)

# =====================================================================================================================
# Rodada 3: VÉSPER-7 v2 (maior, nariz com volume, pernas articuladas, porão na traseira), A/B
# =====================================================================================================================
import build_wrecks_v07_m4_r3 as R3  # noqa: E402
FIT_R3 = "seeds 0–199 com a VÉSPER 12×6: nenhum destroço perdido, 2 ruínas em todos"


def r3_compare():
    cur = dict(WR.CARGO)
    metas = [cur, R3.CARGO_R3, R3.CARGO_R3]
    names = ["wreck_cargo_r2", "wreck_cargo_r3_A", "wreck_cargo_r3_B"]
    labels = ["hoje (r2 aprovada)", "R3 A", "R3 B"]
    rows = int(max(m["size"][1] + m["lift"] / T for m in metas) + 3.99)
    cols = sum(m["size"][0] + 2 for m in metas) + 1
    img = ground(cols * T, rows * T, "dead", 4, 2)
    sc = Scene(img)
    x = 1
    pos = []
    for nm, m in zip(names, metas):
        ty = rows - 2 - m["size"][1]
        sc.wreck("cargo", x, ty, m, img=r2img(nm))
        ax, ay = m["approach"]
        sc.player((x + ax) * T + 16, (ty + ay) * T + 14, "up", frame=1)
        pos.append(x)
        x += m["size"][0] + 2
    out = sc.draw()
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for x, lab in zip(pos, labels):
        d.rectangle([x * T, 4, x * T + 6 * len(lab) + 8, 16], fill=(21, 16, 14, 255)); d.text((x * T + 4, 5), lab, fill=(242, 196, 109, 255), font=f)
    out.save(REP / "r3_cmp.png")
    return "r3_cmp.png", out.size


def r3_scene(stage):
    img = ground(960, 544, stage, 2, 6)
    sc = Scene(img)
    m = R3.CARGO_R3
    for (tx, ty, v) in ((0, 2, "A"), (16, 9, "B")):
        sc.wreck("cargo", tx, ty, m, img=r2img(f"wreck_cargo_r3_{v}"), crate_open=(v == "B"))
        ax, ay = m["approach"]
        sc.player((tx + ax) * T + 16, (ty + ay) * T + 12, "up", frame=2)
    sc.player(13 * T, 13 * T, "side")
    for (x, y) in ((14, 3), (28, 2), (3, 15), (24, 8)):
        sc.thing("rock_small.png", x, y)
    if stage == "green":
        for (x, y, k) in ((14, 6, "plant_bush.png"), (26, 4, "plant_tree.png"), (6, 13, "plant_flower.png")):
            sc.thing(k, x, y, foot=y * T + 30)
    out = sc.draw().crop((0, 0, 960, 540))
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for (x, y, lab) in ((6, 6, "VESPER-7 A"), (16 * T + 6, 9 * T - 36, "VESPER-7 B")):
        d.rectangle([x, y, x + 6 * len(lab) + 8, y + 12], fill=(21, 16, 14, 255)); d.text((x + 4, y + 1), lab, fill=(242, 196, 109, 255), font=f)
    fn = f"r3_preview_{stage}.png"
    out.save(REP / fn)
    return fn


def r3_annot(v):
    m = R3.CARGO_R3
    im = r2img(f"wreck_cargo_r3_{v}")
    W, H = im.size
    w, h = m["size"]
    Lf = m["lift"]
    z = 2
    bg = Image.new("RGBA", (W + T, H + 2 * T), (196, 160, 122, 255))
    bg.alpha_composite(im, (0, 0))
    big = bg.resize((bg.width * z, bg.height * z), Image.NEAREST)
    d = ImageDraw.Draw(big)
    f = ImageFont.load_default()
    for x in range(w + 1):
        d.line([(x * T * z, Lf * z), (x * T * z, (Lf + h * T) * z)], fill=COL["grid"], width=1)
    for y in range(h + 1):
        d.line([(0, (Lf + y * T) * z), (w * T * z, (Lf + y * T) * z)], fill=COL["grid"], width=1)
    for (t, col, lab) in ((m["crate"], COL["crate"], "caixa"), (m["mouth"], COL["mouth"], "boca"), (m["approach"], COL["approach"], "chega")):
        x0, y0 = t[0] * T * z, (Lf + t[1] * T) * z
        d.rectangle([x0, y0, x0 + T * z - 1, y0 + T * z - 1], outline=col, width=3)
        d.rectangle([x0 + 3, y0 + 3, x0 + 70, y0 + 15], fill=(21, 16, 14, 255)); d.text((x0 + 5, y0 + 4), f"{lab} {t}", fill=col, font=f)
    fn = f"r3_anot_{v}.png"
    big.save(REP / fn)
    return fn, big.size


def r3_section():
    R3.main()
    cmpf = r3_compare()
    scenes = [r3_scene(st) for st in ("dead", "mist", "green")]
    anns = [r3_annot(v) for v in "AB"]
    m = R3.CARGO_R3
    o = []
    a = o.append
    a('<h1 style="color:#a8968a;margin-top:40px">Rodada 3 · VÉSPER-7 v2 (aprovada pelo dono: A e B sorteadas pela seed, "um pouco maiores" → rodada 4)</h1>')
    a('<div class="v2"><b>v1.2 · o que mudou</b><ul>'
      '<li><b>Maior</b>: de 10×5 (320×224) pra <b>12×6 (384×240)</b>, com a mesma alma: a cargueira de ardósia em isométrico, "VESPER-7" pintado (gasto), a faixa e o painel laranja desbotados e o porão aberto com a porta acesa.</li>'
      '<li><b>Porão na traseira</b>: a boca é a popa inteira (virada pra baixo-direita), com moldura de faixa de perigo e lâmpada âmbar. A <b>rampa de carga</b> é comprida e desce da traseira até a areia, com trilhos dourados, LEDs ciano e luz no piso. Dentro: piso claro, parede com fita de LED, costelas no teto, carga presa de um lado e o caminho livre até a <b>porta acesa</b> no fundo.</li>'
      '<li><b>Menos caixa</b>: o casco virou uma seção chanfrada (A) ou arredondada (B), com <b>nariz de verdade</b> e para-brisa (A em cunha com ponte de comando; B redondo com cabine-bolha de vidro), mais <b>dois motores em pilones</b> dos dois lados da rampa (um aceso, um apagado), radiadores abertos do lado de lá, espinha e módulos no convés, prato, antenas com LED, escotilha, módulo lateral com escada, vigias e amassados do impacto.</li>'
      '<li><b>Pés</b>: 4 pernas articuladas (caixa da dobradiça, braço com tirante, joelho, cilindro do amortecedor com anel laranja, haste cromada e sapata redonda). A <b>da frente de perto quebrou</b> (o toco ficou pendurado e o pedaço de baixo com a sapata virada está na areia). A de trás de lá está <b>afundada</b>. O casco ficou <b>embicado 5°</b>, com o nariz enterrado num monte de areia.</li>'
      '<li><b>A × B</b>: A tem casco chanfrado, ponte de comando e 2 radiadores. B tem casco arredondado, cabine-bolha, 2 contêineres de carga no convés e 1 radiador.</li></ul></div>')
    a(f'<div class="status"><span class="chip ok">{FIT_R3}</span><span class="chip ok">sem peça na borda do canvas</span><span class="chip">script: tools/sprites/build_wrecks_v07_m4_r3.py</span></div>')
    a('<section><h2>R3 · Prévias 960×540: chegando na rampa</h2><div class="pvs">' + "".join(
        f'<figure class="pv"><img src="{fn}" width="960" height="540"><figcaption><b>{lab}</b><span>VÉSPER A (em cima) e B (embaixo), com o Explorador no pé de cada rampa (1:1)</span></figcaption></figure>'
        for fn, lab in zip(scenes, ("Morto", "Névoa", "Verde"))) + '</div></section>')
    fn, sz = cmpf
    a(f'<section><h2>R3 · Hoje × A × B, com o player na rampa (2×)</h2><div class="scroll"><img src="{fn}" width="{sz[0] * 2}" height="{sz[1] * 2}" style="image-rendering:pixelated;display:block;max-width:none;width:{sz[0] * 2}px"></div></section>')
    a('<section><h2>R3 · Candidatas ampliadas (2×)</h2><div class="cards">' + "".join(
        f'<figure class="spr"><div class="chk"><img src="pendentes/wreck_cargo_r3_{v}.png" width="768" height="480"></div><figcaption>wreck_cargo_r3_{v}.png<span>384×240 · 2×</span></figcaption></figure>' for v in "AB") + '</div></section>')
    a('<section><h2>R3 · Pro Dev</h2><div class="box dev"><table class="tb"><tr><th>kind</th><th>arquivo</th><th>pegada</th><th>sprite</th><th>lift</th><th>caixa</th><th>boca</th><th>chega por</th></tr>'
      f'<tr><td><code>cargo</code></td><td><code>wreck_cargo_r3_{{A,B}}</code> → <code>wreck_cargo</code></td><td><b>12×6</b> (era 10×5)</td><td>384×240</td><td>48</td><td>{fmt(m["crate"])}</td><td>{fmt(m["mouth"])}</td><td>{fmt(m["approach"])}</td></tr></table>'
      '<ul><li>A boca fica na <b>fileira de baixo</b> da pegada: o pé da rampa desenhado cai no tile (10,5). O tile de chegar, (10,6), fica logo abaixo, fora da pegada. A traseira com a rampa vira pra baixo-direita, então a boca não fica na lateral.</li>'
      '<li><code>hatch_in_target</code> → <code>(tx+10, ty+5)</code>; <code>surface_exit</code> → <code>((tx+10.5)·T, (ty+6)·T + 24)</code>. Continua valendo a sugestão de virar campo do <code>WreckSpec</code> (<code>hatch=(10, 5)</code>).</li>'
      '<li>Caixa (6,6): embaixo do meio do casco, fora da pegada e alcançável.</li>'
      '<li><code>sprite = (12·32, 6·32 + 48)</code>, blit <code>(tx·32, ty·32 − 48)</code>, ordenado pelo pé da pegada, como sempre.</li>'
      '<li><b>Variantes</b>: se as duas entrarem (como a ARCA e o robô), o sorteio pela seed só troca o PNG. A pegada e as marcas são as mesmas nas duas.</li></ul>')
    for fn, sz in anns:
        a(f'<div class="scroll" style="margin-top:12px"><img src="{fn}" width="{sz[0]}" height="{sz[1]}" style="image-rendering:pixelated;display:block;max-width:none"></div>')
    a('</div></section>')
    a('<section><h2>R3 · Decisões pro dono</h2><div class="box"><ol><li>A (chanfrada, ponte de comando) ou B (arredondada, cabine-bolha)? Ou as duas sorteadas?</li>'
      '<li>O tamanho 12×6 tá bom, ou quer ainda maior?</li><li>A rampa na traseira chama pra entrar?</li></ol></div></section>')
    return "".join(o)

# =====================================================================================================================
# Rodada 4: as duas VÉSPER v2 17% maiores (14×7), mesmo desenho
# =====================================================================================================================
FIT_R4 = "seeds 0–199 com a VÉSPER 14×7: nenhum destroço perdido, 2 ruínas em todos"


def r4_compare():
    m3, m4 = R3.CARGO_R3, R3.CARGO_R4
    items = [("wreck_cargo_r3_A", m3, "R3 A"), ("wreck_cargo_r4_A", m4, "R4 A"), ("wreck_cargo_r3_B", m3, "R3 B"), ("wreck_cargo_r4_B", m4, "R4 B")]
    rows = int(m4["size"][1] + m4["lift"] / T + 3.99)
    cols = sum(m["size"][0] + 2 for _, m, _ in items) + 1
    img = ground(cols * T, rows * T, "dead", 6, 1)
    sc = Scene(img)
    x, pos = 1, []
    for nm, m, lab in items:
        ty = rows - 2 - m["size"][1]
        sc.wreck("cargo", x, ty, m, img=r2img(nm))
        ax, ay = m["approach"]
        sc.player((x + ax) * T + 16, (ty + ay) * T + 14, "up", frame=1)
        pos.append((x, lab))
        x += m["size"][0] + 2
    out = sc.draw()
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for x, lab in pos:
        d.rectangle([x * T, 4, x * T + 6 * len(lab) + 8, 16], fill=(21, 16, 14, 255)); d.text((x * T + 4, 5), lab, fill=(242, 196, 109, 255), font=f)
    out.save(REP / "r4_cmp.png")
    return "r4_cmp.png", out.size


def r4_scene(stage):
    img = ground(960, 544, stage, 7, 3)
    sc = Scene(img)
    m = R3.CARGO_R4
    for (tx, ty, v) in ((0, 2, "A"), (15, 9, "B")):
        sc.wreck("cargo", tx, ty, m, img=r2img(f"wreck_cargo_r4_{v}"), crate_open=(v == "B"))
        ax, ay = m["approach"]
        sc.player((tx + ax) * T + 16, (ty + ay) * T + 12, "up", frame=2)
    sc.player(12 * T, 14 * T, "side")
    for (x, y) in ((16, 3), (28, 4), (3, 15), (26, 2)):
        sc.thing("rock_small.png", x, y)
    if stage == "green":
        for (x, y, k) in ((17, 6, "plant_bush.png"), (24, 5, "plant_tree.png"), (6, 14, "plant_flower.png")):
            sc.thing(k, x, y, foot=y * T + 30)
    out = sc.draw().crop((0, 0, 960, 540))
    d = ImageDraw.Draw(out)
    f = ImageFont.load_default()
    for (x, y, lab) in ((6, 6, "VESPER-7 A"), (15 * T + 6, 9 * T - 52, "VESPER-7 B")):
        d.rectangle([x, y, x + 6 * len(lab) + 8, y + 12], fill=(21, 16, 14, 255)); d.text((x + 4, y + 1), lab, fill=(242, 196, 109, 255), font=f)
    fn = f"r4_preview_{stage}.png"
    out.save(REP / fn)
    return fn


def r4_annot(v):
    m = R3.CARGO_R4
    im = r2img(f"wreck_cargo_r4_{v}")
    W, H = im.size
    w, h = m["size"]
    Lf, z = m["lift"], 2
    bg = Image.new("RGBA", (W + T, H + 2 * T), (196, 160, 122, 255))
    bg.alpha_composite(im, (0, 0))
    big = bg.resize((bg.width * z, bg.height * z), Image.NEAREST)
    d = ImageDraw.Draw(big)
    f = ImageFont.load_default()
    for x in range(w + 1):
        d.line([(x * T * z, Lf * z), (x * T * z, (Lf + h * T) * z)], fill=COL["grid"], width=1)
    for y in range(h + 1):
        d.line([(0, (Lf + y * T) * z), (w * T * z, (Lf + y * T) * z)], fill=COL["grid"], width=1)
    for (t, col, lab) in ((m["crate"], COL["crate"], "caixa"), (m["mouth"], COL["mouth"], "boca"), (m["approach"], COL["approach"], "chega")):
        x0, y0 = t[0] * T * z, (Lf + t[1] * T) * z
        d.rectangle([x0, y0, x0 + T * z - 1, y0 + T * z - 1], outline=col, width=3)
        d.rectangle([x0 + 3, y0 + 3, x0 + 70, y0 + 15], fill=(21, 16, 14, 255)); d.text((x0 + 5, y0 + 4), f"{lab} {t}", fill=col, font=f)
    fn = f"r4_anot_{v}.png"
    big.save(REP / fn)
    return fn, big.size


def r4_section():
    R3.main()
    cmpf = r4_compare()
    scenes = [r4_scene(st) for st in ("dead", "mist", "green")]
    anns = [r4_annot(v) for v in "AB"]
    m = R3.CARGO_R4
    o = []
    a = o.append
    a('<h1 style="color:#f2c46d;margin-top:40px">Rodada 4 · VÉSPER-7 v2 um pouco maior</h1>')
    a('<div class="v2"><b>v1.3 · o que mudou</b><ul>'
      '<li>As duas VÉSPER v2 aprovadas (A e B) foram <b>rerenderizadas 17% maiores</b>, sem mudar o desenho. O renderizador escala a geometria e desenha de novo na resolução nova, então as linhas e o contorno continuam com 1 px (não é bitmap ampliado).</li>'
      '<li><b>12×6 (384×240) → 14×7 (448×272)</b>, lift 48. As marcas acompanharam: <b>boca (12,6)</b> no pé da rampa, na fileira de baixo; <b>chega por (12,7)</b> e <b>caixa (7,7)</b>, as duas fora da pegada.</li>'
      f'<li>Geração: {FIT_R4}. Não precisou voltar pra 13×6.</li></ul></div>')
    a(f'<div class="status"><span class="chip ok">{FIT_R4}</span><span class="chip ok">sem peça na borda do canvas</span><span class="chip">script: tools/sprites/build_wrecks_v07_m4_r3.py (view "r4")</span></div>')
    a('<section><h2>R4 · Prévias 960×540: chegando na rampa</h2><div class="pvs">' + "".join(
        f'<figure class="pv"><img src="{fn}" width="960" height="540"><figcaption><b>{lab}</b><span>VÉSPER A (em cima) e B (embaixo) 14×7, com o Explorador no pé de cada rampa (1:1)</span></figcaption></figure>'
        for fn, lab in zip(scenes, ("Morto", "Névoa", "Verde"))) + '</div></section>')
    fn, sz = cmpf
    a(f'<section><h2>R4 · R3 × R4, com o player na rampa (2×)</h2><div class="scroll"><img src="{fn}" width="{sz[0] * 2}" height="{sz[1] * 2}" style="image-rendering:pixelated;display:block;max-width:none;width:{sz[0] * 2}px"></div></section>')
    a('<section><h2>R4 · Sprites (2×)</h2><div class="cards">' + "".join(
        f'<figure class="spr"><div class="chk"><img src="pendentes/wreck_cargo_r4_{v}.png" width="896" height="544"></div><figcaption>wreck_cargo_r4_{v}.png<span>448×272 · 2×</span></figcaption></figure>' for v in "AB") + '</div></section>')
    a('<section><h2>R4 · Pro Dev</h2><div class="box dev"><table class="tb"><tr><th>kind</th><th>arquivos (variantes pela seed)</th><th>pegada</th><th>sprite</th><th>lift</th><th>caixa</th><th>boca</th><th>chega por</th></tr>'
      f'<tr><td><code>cargo</code></td><td><code>wreck_cargo_r4_A</code>, <code>wreck_cargo_r4_B</code></td><td><b>14×7</b></td><td>448×272</td><td>48</td><td>{fmt(m["crate"])}</td><td>{fmt(m["mouth"])}</td><td>{fmt(m["approach"])}</td></tr></table>'
      '<ul><li><code>hatch_in_target</code> → <code>(tx+12, ty+6)</code>; <code>surface_exit</code> → <code>((tx+12.5)·T, (ty+7)·T + 24)</code> (sugestão: campo <code>hatch=(12, 6)</code> no <code>WreckSpec</code>).</li>'
      '<li><code>sprite = (14·32, 7·32 + 48)</code>, blit <code>(tx·32, ty·32 − 48)</code>, ordenado pelo pé da pegada.</li>'
      '<li>As duas variantes têm a mesma pegada e as mesmas marcas: o sorteio pela seed só troca o PNG (por exemplo <code>wreck_cargo_a</code> / <code>wreck_cargo_b</code> em <code>assets/sprites/</code>, nomes a combinar com o gerente).</li></ul>')
    for fn, sz in anns:
        a(f'<div class="scroll" style="margin-top:12px"><img src="{fn}" width="{sz[0]}" height="{sz[1]}" style="image-rendering:pixelated;display:block;max-width:none"></div>')
    a('</div></section>')
    return "".join(o)


WR_META = {}

if __name__ == "__main__":
    main(*(sys.argv[1:2]))
