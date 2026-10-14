"""Report do minério bruto do freela (reports/design/minerio_raw/index.html).

Roda com o Python do projeto (usa game.hills e game.art só pra LER, igual ao jogo desenha os morros):
  uv run --with pillow python tools/sprites/ores_raw_report.py   (o venv do jogo não tem PIL)
Antes (assets/sprites/ de hoje, copiado pra antes/) x depois (pendentes/, saída do ores_raw.py).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import ores_raw as OR  # noqa: E402

OUT = ROOT / "reports" / "design" / "minerio_raw"
PEND = OUT / "pendentes"
ANTES = OUT / "antes"
SPR = ROOT / "assets" / "sprites"
KINDS = OR.KINDS
NAMES = list(OR.contract())


def load(p):
    return Image.open(p).convert("RGBA")


def prepare():
    if not (PEND / "rock_small_magmatite_0.png").exists():   # não reescreve os pendentes que já existem
        OR.build()
    ANTES.mkdir(exist_ok=True)
    for n in NAMES:
        shutil.copy(SPR / n, ANTES / n)
    # o cristalzinho de hoje é desenhado por código (game/art.py): rasteriza pra comparar
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    from game import art
    for k in KINDS:
        s = art.ore_fleck(k)
        Image.frombytes("RGBA", s.get_size(), pygame.image.tostring(s, "RGBA")).save(ANTES / f"fleck_{k}.png")


# ---------------------------------------------------------------------------------------------------------------
# Cenas: chão da região + um morro (grade dual do jogo) com minério no topo + veios + rochas
# ---------------------------------------------------------------------------------------------------------------
REG = ("plateau", "salar", "basalt", "frost")
RNAME = {"plateau": "Planalto", "salar": "Salar", "basalt": "Basalto", "frost": "Faixa gelada"}
W, H = 512, 320


def hill_layer(region_i, src):
    from game import config as C, hills
    ore_rgba = {k: np.array(load(src / f"ore_{k}.png")) for k in KINDS}
    luts = {2: hills.hill_lut("arid")}
    i0, i1, j0, j1 = hills.window_bounds(0, 0)
    kinds = np.full((j1 - j0, i1 - i0), C.SAND, np.uint8)
    ores = {(2, 3): C.IRON, (3, 3): C.IRON, (5, 3): C.SILICON, (3, 5): C.ICE, (4, 5): C.ICE, (6, 5): C.SILICON,
            (4, 4): C.IRON, (2, 5): C.SILICON}
    for j in range(3, 7):
        for i in range(2, 8):
            kinds[j - j0, i - i0] = C.ROCK
    for (i, j), k in ores.items():
        kinds[j - j0 + 0, i - i0] = k
    regions = np.full(kinds.shape, region_i, np.uint8)
    blk = hills.bake_block(kinds, regions, 0, 0, hills.load_indexed("hill_top.png"),
                           hills.load_indexed("hill_face.png"), hills.edge_noise())
    return blk, Image.fromarray(hills.colorize_block(blk, luts, 2, ore_rgba), "RGBA")


def scene(region_i, which):
    from game import hills
    src = ANTES if which == "antes" else PEND
    import regions_v9 as V9
    bg = V9.ground_patch(REG[region_i], "arid", W, H, 5).convert("RGBA")
    blk, hl = hill_layer(region_i, src)
    # o bloco começa em y0 = -32; leva ele pra y = 0 da cena + 8
    bg.alpha_composite(hl, (blk["x0"] + 8, blk["y0"] + 40))
    objs = []
    for n, k in enumerate(KINDS):
        v = load(src / f"vein_{k}.png")
        objs.append((70 + 6, v, 288 + n * 72 - 8, 12 + (n % 2) * 6))
    rock = load(src / "rock_small.png")
    for n, k in enumerate(KINDS):
        fl = load(src / f"fleck_{k}.png")
        x, y = 296 + n * 72, 112
        objs.append((y + 32, rock, x, y))
        objs.append((y + 33, fl, x, y))
    # rochas a mais (fileira de baixo, outra posição) + pickups 16x16 soltos
    for n, k in enumerate(KINDS):
        x, y = 296 + n * 72 + 24, 168
        objs.append((y + 32, rock, x - 24, y))
        objs.append((y + 33, load(src / f"fleck_{k}.png"), x - 24, y))
    for n, k in enumerate(KINDS):
        objs.append((250, load(src / f"pickup_{k}.png"), 300 + n * 40, 232))
        objs.append((250, load(src / f"icon_{k}.png"), 300 + n * 40, 262))
    for _, im, x, y in sorted(objs, key=lambda o: o[0]):
        bg.alpha_composite(im, (x, y))
    return bg


STAGES = ("storm", "arid", "mist", "green")


def veined_grid():
    """4 regiões (linhas) x 4 estágios (colunas): as 6 rochas com veio (2 variações x 3 minérios) no chão."""
    import regions_v9 as V9
    cw, ch = 200, 44
    out = Image.new("RGBA", (cw * 4, ch * 4))
    for r, reg in enumerate(REG):
        for c, st in enumerate(STAGES):
            cell = V9.ground_patch(reg, st, cw, ch, 3 + r * 4 + c).convert("RGBA")
            for n, (k, v) in enumerate([(k, v) for k in KINDS for v in (0, 1)]):
                im = load(PEND / f"rock_small_{k}_{v}.png")
                cell.alpha_composite(im, (n * 32 + 4, 6))
            out.alpha_composite(cell, (c * cw, r * ch))
    out.save(OUT / "cena_rochas_veio.png")


def vein_compare():
    """veio 2x2 em 3 versões (atual, freela com pintas, veio em linha) sobre planalto e faixa gelada."""
    import regions_v9 as V9
    cw = 3 * 70
    img = Image.new("RGBA", (cw * 2, 3 * 68 + 4))
    for g, reg in enumerate(("plateau", "frost")):
        bg = V9.ground_patch(reg, "arid", cw, 3 * 68 + 4, 9 + g).convert("RGBA")
        for row, k in enumerate(KINDS):
            for col, src in enumerate((ANTES / f"vein_{k}.png", PEND / f"vein_{k}.png", PEND / f"vein_linha_{k}.png")):
                bg.alpha_composite(load(src), (col * 70 + 3, row * 68 + 2))
        img.alpha_composite(bg, (g * cw, 0))
    img.save(OUT / "cena_veios_linha.png")


def magma_scene():
    """Basalto nos 4 estágios (colunas): fumarola dormente com poucas pedras (cima) e acordada com mais (baixo)."""
    import regions_v9 as V9
    from game import hills
    cw, ch = 256, 190
    out = Image.new("RGBA", (cw * 4, ch * 2))
    spots_d = [(-52, 18, 0), (46, 22, 1), (4, 46, 0)]
    spots_a = [(-60, 14, 0), (-34, 40, 1), (44, 16, 1), (62, 42, 0), (6, 52, 1), (-30, 24, 0), (30, 54, 0)]
    for r, (state, spots) in enumerate((("dormant", spots_d), ("active", spots_a))):
        for c, st in enumerate(STAGES):
            cell = V9.ground_patch("basalt", st, cw, ch, 40 + c).convert("RGBA")
            idx = hills.load_indexed(f"form_vent_cone_{state}.png")
            rgba = hills.colorize(idx, hills.ramp("HILL+VENT", "basalt", st))
            fx, fy = cw // 2, 112                        # pé da fumarola (âncora 30,38 do sprite 60x48)
            objs = [(fy, Image.fromarray(rgba, "RGBA"), fx - 30, fy - 38)]
            for dx, dy, v in spots:
                im = load(PEND / f"rock_small_magmatite_{v}.png")
                objs.append((fy + dy + 16, im, fx + dx - 16, fy + dy - 16))
            for _, im, x, y in sorted(objs, key=lambda o: o[0]):
                cell.alpha_composite(im, (x, y))
            out.alpha_composite(cell, (c * cw, r * ch))
    out.save(OUT / "cena_magmatita.png")


def anim_html():
    """Animação da lava em CSS (steps(4)) no basalto dos 4 estágios: tamanho real e ampliada 3x."""
    import regions_v9 as V9
    CW, CH = 192, 80
    css = ("<style>.lv{position:relative;overflow:hidden;image-rendering:pixelated}"
           ".lv i{position:absolute;display:block;image-rendering:pixelated;background-repeat:no-repeat;"
           "animation:lvstep 1.2s steps(4) infinite}"
           "@keyframes lvstep{to{background-position-x:var(--end)}}"
           ".lvz{display:inline-block;margin:4px}.lvz>.lv{transform-origin:0 0;transform:scale(3)}"
           ".lvr{display:inline-block;margin:2px}</style>")

    def sprite(name, w, x, y):
        return (f'<i style="left:{x}px;top:{y}px;width:{w}px;height:{32 if w != 64 else 64}px;'
                f'background-image:url(pendentes/{name});--end:-{w * 4}px"></i>')

    cells = []
    for c, st in enumerate(STAGES):
        bg = V9.ground_patch("basalt", st, CW, CH, 60 + c).convert("RGBA")
        rock = Image.new("RGBA", (32, 32), (0x3a, 0x33, 0x44, 255))
        bg.alpha_composite(rock, (76, 8))                 # a parede atrás do ore_magmatite (overlay)
        bg.save(OUT / f"basalto_{st}.png")
        inner = (sprite("vein_magmatite_anim.png", 64, 4, 8) + sprite("ore_magmatite_anim.png", 32, 76, 8)
                 + sprite("rock_small_magmatite_0_anim.png", 32, 116, 8) + sprite("rock_small_magmatite_1_anim.png", 32, 154, 8)
                 + sprite("rock_small_magmatite_0_anim.png", 32, 40, 46) + sprite("rock_small_magmatite_1_anim.png", 32, 100, 46))
        cells.append(f'<div class="lv" style="width:{CW}px;height:{CH}px;background:url(basalto_{st}.png)">{inner}</div>')
    names = ("tempestade", "árido", "névoa", "verde")
    real = "".join(f'<div class="lvr"><small>{n}</small><br>{c}</div>' for n, c in zip(names, cells))
    zoom = "".join(f'<div class="lvz" style="width:{CW * 3}px;height:{CH * 3}px"><small>{n}</small>{c}</div>'
                   for n, c in zip(names, cells))
    return css + f"<h3>Tamanho real</h3>{real}<h3>Ampliado 3×</h3>{zoom}"


GLX, GLY, GCW, GCH = 84, 18, 264, 44
GRID_ORDER = [(k, v) for k in KINDS + ("magmatite",) for v in (0, 1)]


def grid_magma():
    """Grade 4 regiões (linhas) x 4 estágios (colunas), com ferro, silício, gelo e magmatita (2 variações cada),
    rótulos nas linhas e colunas. Só lê os pendentes; escreve a imagem nova."""
    import regions_v9 as V9
    from PIL import ImageDraw
    out = Image.new("RGBA", (GLX + GCW * 4, GLY + GCH * 4), (27, 22, 48, 255))
    dr = ImageDraw.Draw(out)
    snames = ("1 tempestade", "2 arido", "3 nevoa", "4 verde")      # fonte do PIL sem acento
    for c, n in enumerate(snames):
        dr.text((GLX + c * GCW + 6, 4), n, fill=(242, 196, 109, 255))
    for r, reg in enumerate(REG):
        dr.text((4, GLY + r * GCH + 16), RNAME[reg], fill=(89, 208, 230, 255))
        for c, st in enumerate(STAGES):
            cell = V9.ground_patch(reg, st, GCW, GCH, 3 + r * 4 + c).convert("RGBA")
            for n, (k, v) in enumerate(GRID_ORDER):
                name = f"rock_small_{k}_{v}.png"
                cell.alpha_composite(load(PEND / name), (n * 32 + 4, 6))
            out.alpha_composite(cell, (GLX + c * GCW, GLY + r * GCH))
    out.save(OUT / "cena_rochas_veio_magmatita.png")


def grid_html():
    css = ("<style>.gl{position:relative;display:inline-block}.gl i{position:absolute;display:block;width:32px;height:32px;"
           "image-rendering:pixelated;background-repeat:no-repeat;animation:lvstep 1.2s steps(4) infinite}"
           "@keyframes lvstep{to{background-position-x:-128px}}</style>")
    els = ""
    for r in range(4):
        for c in range(4):
            for v in (0, 1):
                n = 6 + v
                x, y = GLX + c * GCW + n * 32 + 4, GLY + r * GCH + 6
                els += f'<i style="left:{x}px;top:{y}px;background-image:url(pendentes/rock_small_magmatite_{v}_anim.png)"></i>'
    return (css + '<h3>Todas as rochas com veio, por região e estágio (estática)</h3>'
            '<p>Cada célula, da esquerda pra direita: ferro, silício, gelo e magmatita, 2 variações de cada.</p>'
            '<img src="cena_rochas_veio_magmatita.png" style="image-rendering:pixelated">'
            '<h3>A mesma grade com a lava pulsando (CSS)</h3>'
            f'<div class="gl"><img src="cena_rochas_veio_magmatita.png" style="image-rendering:pixelated;display:block">{els}</div>')


def scenes():
    grid_magma()
    magma_scene()
    veined_grid()
    vein_compare()
    for i, r in enumerate(REG):
        for which in ("antes", "depois"):
            scene(i, which).save(OUT / f"cena_{r}_{which}.png")


# ---------------------------------------------------------------------------------------------------------------
def check_contract():
    """Existe, no tamanho exato, e sem extras fora do contrato nos pendentes (fleck_* é extra declarado)."""
    rows = []
    for n in NAMES:
        a, d = load(ANTES / n).size, load(PEND / n).size
        rows.append((n, a, d, a == d))
    extra = sorted(set(p.name for p in PEND.glob("*.png")) - set(NAMES))
    return rows, extra


def checker(z):
    return f"background-color:#fff;background-image:linear-gradient(45deg,#cfcfd8 25%,transparent 25%,transparent 75%,#cfcfd8 75%),linear-gradient(45deg,#cfcfd8 25%,transparent 25%,transparent 75%,#cfcfd8 75%);background-size:{z*2}px {z*2}px;background-position:0 0,{z}px {z}px"


def img(path, w, h, z):
    return (f'<img src="{path}" width="{w*z}" height="{h*z}" style="image-rendering:pixelated;{checker(max(4, z*2))}">')


SEC = '''
<h2>2b. Rochas com veio (pedido do dono)</h2>
<div class="note">O dono achou feio o "blob colado em cima da pedra". Agora o minério está <b>dentro</b>: linhas da cor do minério atravessando a rocha, rachadura preenchida (fenda escura de 1 px, miolo na cor do minério, brilho e sombra ao longo da linha). Estilo aproveitado da referência dele: pedra escura com veios claros em diagonal cruzando de ponta a ponta. Original, desenhado por código.</div>
<div class="pair"><figure><figcaption>ref do dono: como está hoje</figcaption><img src="../refs/rocha_minerio_atual_feia_dono.png" class="px" style="width:240px"></figure>
<figure><figcaption>ref do dono: a ideia</figcaption><img src="../refs/rocha_minerio_veio_linha_ref_dono.png" class="px" style="width:240px"></figure></div>
<h3>Antes × depois, 2 variações por minério</h3>
<table><tr><th>antes (rock_small + fleck por código)</th><th colspan="2">depois: variação 0 e 1</th></tr>
{rv}</table>
<h3>Nas 4 regiões (linhas) e nos 4 estágios (colunas: tempestade, árido, névoa, verde)</h3>
<img src="cena_rochas_veio.png" class="px" style="width:768px">
<p>Ferro (laranja) e gelo (ciano) leem em tudo. O silício (cinza azulado claro) é o de menor contraste, sobretudo no salar claro e na faixa gelada: a fenda escura em volta segura a leitura.</p>
<h3>Veio 2×2 (<code>vein_*</code>): veja a seção "Veio orgânico" abaixo</h3>

<h2>2c. Veio orgânico (pedido do dono)</h2>
<div class="note"><b>v2 do veio em linha.</b> O dono achou a v1 geométrica ("cookies": elipses repetidas). Agora as lajes são <b>polígonos angulosos irregulares</b> (7 de tamanhos e ângulos diferentes, nada de elipse) e as rachaduras são um passeio aleatório que segue a pedra: espessura varia de 1 a 3 px, ramifica, e a ponta se perde em pontilhado. Mesma linguagem das rochas com veio (fenda escura de 1 px, miolo, brilho em cima/esquerda, sombra embaixo). 64×64, nome alternativo <code>vein_linha_{{iron,silicon,ice}}.png</code>. Se o dono aprovar, vira o <code>vein_*</code> oficial.</div>
<p>Colunas: atual do jogo · freela (pintas) · orgânico. Sobre planalto (esq.) e faixa gelada (dir.), estágio árido.</p>
<img src="cena_veios_linha.png" class="px" style="width:840px">
<p>Ampliado 4× (ferro, silício, gelo, magmatita):</p>
<div>{vz}</div>

<h2>2d. Magmatita (a família completa)</h2>
<div class="note">Pedra quente de basalto, <b>igual à do aquecedor</b> (<code>machines_r3d.py</code>, <code>magma_rock</code>): basalto escuro (<code>#6a5f72 · #4e4558 · #3a3244 · #2a2333</code>) com veios de lava incandescente (laranja <code>#ff9a3d</code>, vermelho <code>#e0602a</code>, toques de amarelo <code>#ffd27a</code>). <b>O brilho fica só dentro das fissuras</b>: nenhum halo fora da pedra, e o contorno é o normal da família (<code>#1b1630</code>). Mantive a rede de rachaduras finas espalhadas pela pedra, que combina com o visual do aquecedor. Mesmos tamanhos do contrato. Nasce só perto das fumarolas (bíblia §12, "Magmatita"; sem veio por enquanto, o <code>vein_magmatite</code> fica pronto pro gancho da drill nv.2 na fumarola).</div>
<h3>Veio da magmatita: "mais lava" (ajuste do dono)</h3>
<div class="pair"><figure><figcaption>referência do dono (estilo)</figcaption><img src="../refs/veio_magmatita_lava_ref_dono.png" style="width:384px;height:384px;image-rendering:pixelated"></figure>
<figure><figcaption>esboço do dono (radial)</figcaption><img src="../refs/veio_magmatita_radial_esboco_dono.png" style="width:384px;image-rendering:pixelated"></figure>
<figure><figcaption>vein_magmatite 64×64 (6×)</figcaption>{img_v}</figure>
<figure><figcaption>animada (6×, CSS)</figcaption><div style="width:384px;height:384px;image-rendering:pixelated;background:url(pendentes/vein_magmatite_anim.png) 0 0/1536px 384px no-repeat;animation:vl 1.2s steps(4) infinite"></div></figure></div>
<style>@keyframes vl{{to{{background-position-x:-1536px}}}}</style>
<p><b>v4 · lava radial.</b> A fenda diagonal reta ("raio de Zeus") saiu; as placas de basalto continuam as mesmas (o dono gostou da distribuição). Agora a lava <b>nasce numa poça incandescente no centro</b> (núcleo amarelo-branco <code>#fff4cc</code>) e <b>8 rachaduras tortas irradiam pras bordas</b>, buscando as juntas entre as placas, ramificando e <b>afinando até 1 px</b> perto das bordas; a mais grossa é a perto do centro. O brilho que vaza tinge as quinas das placas vizinhas (só dentro da silhueta, mais forte perto do centro, sem halo fora) e as <b>brasas</b> ficam. Do estilo da referência de lava aproveitei basalto quase preto com desnível, o gradiente amarelo-branco, laranja, vermelho e a luz vindo só da lava (desenho original). 64×64, mesma âncora, contorno <code>#1b1630</code>. <b>Animação</b> (4 quadros, 256×64): o núcleo da poça pulsa e o calor corre do centro pras pontas das rachaduras; as brasas piscam. As rochas e o minério de morro seguem como estavam.</p>
{grid}
<table><tr><th>arquivo</th><th>1:1</th><th>ampliado</th></tr>{mz}</table>
<h3>No basalto, perto da fumarola, nos 4 estágios (tempestade, árido, névoa, verde)</h3>
<p>Cima: fumarola <b>dormente</b> com poucas pedras. Baixo: <b>acordada</b>, com mais. A fumarola é o <code>form_vent_cone_*</code> recolorido pela rampa do basalto, ancorado pelo pé (30, 38). As pedras são o <code>rock_small_magmatite_{{0,1}}</code>, ordenadas pelo pé.</p>
<img src="cena_magmatita.png" class="px" style="width:1024px">
<h3>Mais espalhada (ajuste do dono)</h3>
<p>As fissuras agora cruzam a pedra inteira: ficam os veios grossos principais e entra uma rede de rachaduras finas incandescentes (largura 1 px) pela laje, pela rocha e pelo minério de morro, em vez de um ponto só.</p>
<h3>Animação de lava (<code>*_anim.png</code>, 4 quadros)</h3>
<p>Tiras de 4 quadros do mesmo tamanho do estático: <code>vein_magmatite_anim.png</code> 256×64, <code>ore_magmatite_anim.png</code> 128×32, <code>rock_small_magmatite_{{0,1}}_anim.png</code> 128×32. O núcleo amarelo acende e apaga numa onda que desce pelas fissuras (o calor "escorre"), e só a lava dentro das fissuras respira (sem halo). Laço perfeito, ~0,3 s por quadro (1,2 s o ciclo). Os estáticos continuam valendo; a animação é opcional (talvez pra caverna). Sem alpha parcial.</p>
{anim}
<p>Leitura: a lava laranja salta no basalto escuro de qualquer estágio, e a rocha de basalto (mais escura que as de ferro/silício/gelo) não se confunde com elas.</p>
'''


def html(rows, extra):
    def sheet(n, size, zoom):
        w, h = size
        return (f'<tr><td class="n">{n}<br><small>{w}×{h}</small></td>'
                f'<td>{img(f"antes/{n}", w, h, 1)}</td><td>{img(f"pendentes/{n}", w, h, 1)}</td>'
                f'<td>{img(f"antes/{n}", w, h, zoom)}</td><td>{img(f"pendentes/{n}", w, h, zoom)}</td></tr>')
    trs = "".join(sheet(n, a, 8 if a[0] <= 16 else 4 if a[0] <= 32 else 3) for n, a, d, ok in rows)
    trs += "".join(sheet(f"fleck_{k}.png", (32, 32), 4) for k in KINDS)
    sc = ""
    for r in REG:
        sc += (f'<h3>{RNAME[r]}</h3><div class="pair"><figure><figcaption>antes</figcaption>'
               f'<img src="cena_{r}_antes.png" class="px"></figure><figure><figcaption>depois</figcaption>'
               f'<img src="cena_{r}_depois.png" class="px"></figure></div>')
    rv = ""
    for k in KINDS:
        rv += (f'<tr><td>{img(f"antes/rock_small.png", 32, 32, 4)}{img(f"antes/fleck_{k}.png", 32, 32, 4)}</td>'
               f'<td>{img(f"pendentes/rock_small_{k}_0.png", 32, 32, 4)}</td><td>{img(f"pendentes/rock_small_{k}_1.png", 32, 32, 4)}</td></tr>')
    vz = "".join(img(f"pendentes/{('vein_magmatite.png' if k == 'magmatite' else f'vein_linha_{k}.png')}", 64, 64, 4) for k in KINDS + ("magmatite",))
    mz = "".join(f'<tr><td class="n">{n}</td><td>{img(f"pendentes/{n}", sz, sz, 1)}</td><td>{img(f"pendentes/{n}", sz, sz, 8 if sz == 16 else 4)}</td></tr>'
                 for n, sz in (("ore_magmatite.png", 32), ("icon_magmatite.png", 16), ("pickup_magmatite.png", 16),
                               ("rock_small_magmatite_0.png", 32), ("rock_small_magmatite_1.png", 32), ("vein_magmatite.png", 64)))
    rv_sec = SEC.format(rv=rv, vz=vz, mz=mz, img_v=img('pendentes/vein_magmatite.png', 64, 64, 6), anim=anim_html(), grid=grid_html())
    return f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Hesper · minério bruto (proposta)</title>
<style>
body{{background:#1b1630;color:#eee8f5;font:15px/1.5 system-ui,sans-serif;max-width:1180px;margin:0 auto;padding:24px}}
h1,h2,h3{{color:#f2c46d}} table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #3a3150;padding:8px;vertical-align:middle;text-align:center}}
td.n{{text-align:left;font-family:monospace}} .px{{image-rendering:pixelated;width:1024px;max-width:100%}} .pair{{display:flex;gap:12px;flex-wrap:wrap}}
figure{{margin:0}} figcaption{{color:#59d0e6;font-weight:600}} .note{{background:#2a2142;border-left:4px solid #e2733a;padding:10px 16px}}
code{{background:#2a2142;padding:1px 5px;border-radius:3px}} .bad{{color:#ff6a55}} .ok{{color:#7fd67a}}
</style>
<h1>Minério bruto do freela · proposta v1</h1>
<div class="note"><b>v1 · o que mudou.</b> Porte do minério aprovado da sessão experimental ("o freela"): <code>ore_*</code>, <code>vein_*</code>,
<code>icon_*</code>, <code>pickup_*</code> (ferro, silício, gelo) e <code>rock_small</code>, com os mesmos nomes e tamanhos de <code>assets/sprites/</code>.
Gerado por <code>tools/sprites/ores_raw.py</code> (autocontido); <code>--check</code> confirma <b>pixel a pixel</b> contra os PNGs do freela.
Lingotes e wafers ficaram fora. Nada foi copiado pra <code>assets/</code>: está em <code>pendentes/</code> esperando a aprovação do dono.</div>

<h2>1. Antes × depois, arquivo por arquivo</h2>
<p>Colunas: tamanho real (antes, depois) e ampliado (antes, depois), sobre xadrez. Os <code>fleck_*</code> são um <b>extra proposto</b> (ver desvios).</p>
<table><tr><th>arquivo</th><th>antes 1:1</th><th>depois 1:1</th><th>antes ampliado</th><th>depois ampliado</th></tr>{trs}</table>

<h2>2. Cenas por região (estágio árido)</h2>
<p>Cada cena: chão da região, um morro orgânico com ferro, silício e gelo no topo (grade dual do jogo, <code>game/hills.py</code>), os 3 veios, rochas pequenas com o cristal de cada minério,
e embaixo os <code>pickup_*</code> (em cima) e <code>icon_*</code> (embaixo) em 1:1. Ampliado 2×.</p>
<p class="note"><b>Leitura, a olho:</b> o veio e a rocha leem bem nas 4 regiões. Já as pintas do <code>ore_*</code> no topo do morro são bem menores e mais finas que as pepitas de hoje: sobre o basalto e a faixa gelada o silício (cinza claro, 1 a 2 px) e o gelo ficam discretos de longe. Fica pro dono julgar se é o que ele quer na parede; o gelo e o ferro ainda saltam, o silício é o mais fraco.</p>
{sc}

{rv_sec}
<h2>3. Tabela de desvios</h2>
<table>
<tr><th>Item</th><th>Contrato</th><th>Freela</th><th>Situação</th></tr>
<tr><td>12 arquivos ore/vein/pickup/icon</td><td>32², 64², 16², 16²</td><td>idem</td><td class="ok">igual (nome e tamanho)</td></tr>
<tr><td><code>rock_small.png</code></td><td>32×32, rocha de 1 tile</td><td>32×32</td><td class="ok">igual. Muda o visual: rocha 3/4 com face e pedrinha, sem sombra de chão</td></tr>
<tr><td>Cristal do minério na rocha pequena</td><td>não é PNG: <code>art.ore_fleck()</code> desenha por código (2 cristais retos)</td><td>não tem equivalente</td><td class="bad">DESVIO. Com a rocha nova o cristal antigo (retângulos) destoa. Proposta extra: <code>fleck_{{iron,silicon,ice}}.png</code> 32×32 (overlay no tile da rocha, mesma linguagem das pepitas). Precisa de 3 linhas no <code>draw_small_rock</code></td></tr>
<tr><td>Rochas pequenas "por região"</td><td>bíblia §11 não tem PNG por região: é o mesmo <code>rock_small</code> + fleck em todas</td><td>só uma rocha</td><td class="ok">sem desvio. A rocha é neutra (mauve) e lê bem nas 4 regiões</td></tr>
<tr><td><code>pickup_*</code></td><td>"fora do jogo" (§11), arquivos só ficaram nos assets</td><td>tem, 16×16</td><td class="ok">gerado por paridade; não é usado</td></tr>
<tr><td>Sombra de chão</td><td>alpha 0/255 (sem sombra no ore/vein)</td><td>idem</td><td class="ok">sem sombra. O <code>rock_small</code> antigo tinha uma sombra preta (alpha 92) na elipse; o novo não tem</td></tr>
<tr><td>Fonte do código</td><td>-</td><td>ore/vein/icon/pickup saem do <code>items.py</code> do freela, não do <code>make_ore/make_vein/make_icon</code> do <code>objects.py</code> (essas são o desenho antigo e <b>não</b> batem com os PNGs)</td><td>informativo: o porte segue o que gerou os PNGs</td></tr>
<tr><td><code>rock_small_{{iron,silicon,ice}}_{{0,1}}.png</code> (6 novos)</td><td>1 só <code>rock_small</code> + fleck por código; sem variação</td><td>-</td><td class="bad">DESVIO de contrato (pedido do dono): 32×32, mesma âncora, 2 variações por minério. O Dev escolhe a variação por hash do tile, ex.: <code>(tx*73856093 ^ ty*19349663) % 2</code>, estável entre sessões, e a rocha do minério certo (o <code>rock_small</code> neutro e os <code>fleck_*</code> saem de uso se aprovar). A magmatita, quando entrar, segue a mesma regra (<code>MIN</code> com 5 tons, é só acrescentar)</td></tr>
<tr><td><code>vein_linha_*.png</code> (3 novos)</td><td><code>vein_*</code> 64×64</td><td>-</td><td>veio orgânico v2, mesmo tamanho; se aprovado, substitui o <code>vein_*</code></td></tr>
<tr><td>Magmatita: <code>ore_</code>, <code>vein_</code>, <code>icon_</code>, <code>pickup_magmatite.png</code> e <code>rock_small_magmatite_{{0,1}}.png</code> (7 novos)</td><td>não existe no contrato hoje (a bíblia §12 pede a arte "proposta pela Designer")</td><td>-</td><td class="bad">NOVOS (+ 4 tiras <code>*_anim.png</code> de 4 quadros, opcionais), mesmos tamanhos dos outros minérios (32², 64², 16², 16², 32²). Precisam de entrada no contrato da §6 quando o dono aprovar. O Dev escolhe a variação por hash do tile, como as outras rochas. <code>pickup_magmatite</code> só por paridade (soltos saíram)</td></tr>
</table>
<p>Tamanhos conferidos: {sum(1 for r in rows if r[3])}/{len(rows)} iguais ao contrato atual; extras nos pendentes: {", ".join(extra) or "nenhum"}.</p>

<h2>4. Pro Dev integrar</h2>
<ul>
<li>Trocar os 13 PNGs de <code>pendentes/</code> em <code>assets/sprites/</code> (mesmos nomes, mesmos tamanhos; nenhum código muda pra eles).</li>
<li><code>ore_*</code>: overlay no topo elevado da parede em (x, y−24), como hoje; nos morros orgânicos o <code>colorize_block</code> recorta pela silhueta (testado na cena).</li>
<li><code>vein_*</code>: 64×64 no canto do 2×2, como hoje. Overlay sem sombra, lê sobre os 4 chãos.</li>
<li><code>rock_small</code>: tile 32×32 no canto, ordenado pelo pé (y+32). Se aprovar o extra, desenhar <code>fleck_{{res}}.png</code> no mesmo (x, y), logo depois, no lugar de <code>art.ore_fleck</code>.</li>
<li><code>icon_*</code> 16×16: inventário/HUD, sem mudança de código. Conferir o tamanho de leitura no HUD 1:1.</li>
<li>Rochas com veio (se aprovadas): <code>rock_small_{{res}}_{{0,1}}.png</code> no lugar de <code>rock_small</code> + fleck, variação por hash do tile, mesmo (x, y) e ordem pelo pé.</li>
<li>Reprodutível: <code>python3 tools/sprites/ores_raw.py</code> e <code>--check</code>.</li>
</ul>
</html>'''


def main():
    prepare()
    scenes()
    rows, extra = check_contract()
    (OUT / "index.html").write_text(html(rows, extra), encoding="utf-8")
    print("ok", OUT / "index.html")


if __name__ == "__main__":
    main()
