#!/usr/bin/env python3
"""v0.6 Fundo M4 · ícones 16×16 em par da broca de mão (nv.1 definitiva + nv.2). PROPOSTA: nada vai pra assets/ sem ok.

    python3 tools/sprites/v06_fundo_m4_broca.py

Gera em reports/design/v06_fundo_m4_broca/: icon_hand_drill_{A,B}.png (nv.1), icon_hand_drill_t2_{A,B}.png (nv.2),
cenas (hotbar, painel) e o index.html. Determinístico, sem aleatório.
Opção A = corpo da referência do dono (R2: cápsula creme, visor com LED, faixa laranja, broca cônica).
Opção B = pistola de perfil (a do drill_side.png, redesenhada limpa em 16 px).
"""
from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from r3d import Canvas  # noqa: E402
import v05_m4_broca_conteiner as m4  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v06_fundo_m4_broca"
OLD = ROOT / "reports" / "design" / "v05_m4_broca_conteiner" / "pendentes"

KEY = dict(m4.KEY2)
KEY.update({"e": "#f2c46d", "E": "#b98a3a", "f": "#fbe3a3", "H": "#7a5a2a"})   # ouro das máquinas nv.2


def grid(txt, ox=1, oy=1):
    cv = Canvas(16, 16)
    rows = txt.strip("\n").split("\n")
    for y, row in enumerate(rows):
        assert len(row) <= 14, (len(row), row)
        for x, ch in enumerate(row):
            if ch != ".":
                cv.px(x + ox, y + oy, KEY[ch])
    cv.outline()
    return cv


A1 = m4.hand_ref(6, [2, 2, 1, 1, 1, 0])
A2 = """
.feeee........
feeeeeMKk.....
mSSSmMKkwz....
mSLSmMKkwzxy..
mfffeEKkwzxvl.
meeeeEKkwzxy..
mmmmmMKkwz....
NNNNNN..wz....
NeeeeN........
.EEEE.........
"""
# o miolo do A2 acima não alinha com a broca (cone); reescrito abaixo com a broca centrada na linha 4
A2 = """
.feeee........
feeeeeMKkwz...
mSSSmMKkwzxy..
mSLSmMKkwzxvl.
mfffeEKkwzxvly
meeeeEKkwzxvl.
mmmmmMKkwzxy..
NNNNNNKkwz....
NeeeeN........
.EEEE.........
"""
B1 = """
.aaaaa........
abbbbbc.......
ablyybcKkwxz..
apoooocKkwzxvx
abbbbbcKkwxz..
dccccccKk.....
.ccKkc........
.ccKkc........
.qqqqq........
"""
B2 = """
.feeeee.......
mbbbbbM.......
mblyybMKkwx...
feeeeeEKkwzxy.
eeeeeeEKkwzxyl
mbbbbbMKkwzxy.
nnnnnnNKkwx...
.nnKkN........
.nnKkN........
.nnKkN........
.EeeeE........
"""
# nv.2 em 3 linhas de ouro: tampa, faixa e base. O Kk (mandril) só nas linhas da broca.


def build():
    out = {}
    out["icon_hand_drill_A"] = grid(A1, 1, 3)
    out["icon_hand_drill_t2_A"] = grid(A2, 1, 2)
    out["icon_hand_drill_B"] = grid(B1, 1, 3)
    out["icon_hand_drill_t2_B"] = grid(B2, 1, 2)
    return out


# ------------------------------------------------------------------ cenas
BG = (31, 24, 21, 255)


def load(p):
    return Image.open(p).convert("RGBA")


def up(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def slot(icon, sel=False):
    s = Image.new("RGBA", (40, 40), (46, 36, 32, 255))
    b = (242, 196, 109, 255) if sel else (74, 58, 50, 255)
    for i in range(40):
        for j in (0, 1, 38, 39):
            s.putpixel((i, j), b); s.putpixel((j, i), b)
    s.alpha_composite(up(icon, 2), (4, 4))
    return s


def hotbar(d1, d2, extra=("icon_wire", "icon_circuit", "icon_iron_ingot")):
    icons = [load(SPR / f"{n}.png") for n in extra[:1]] + [d1, d2] + [load(SPR / f"{n}.png") for n in extra[1:]]
    im = Image.new("RGBA", (len(icons) * 44 + 4, 48), BG)
    for i, ic in enumerate(icons):
        im.alpha_composite(slot(ic, sel=(i == 1)), (4 + i * 44, 4))
    return im


def pair_sheet(d1, d2):
    im = Image.new("RGBA", (16 * 2 + 16 * 4 * 2 + 16 * 6 * 2 + 70, 100), BG)
    x = 6
    for d in (d1, d2):
        for k in (1, 2, 3):
            pass
    for k in (1, 2, 3):
        pass
    return im


def sheet(d1, d2):
    W = 16 + 32 + 48
    im = Image.new("RGBA", (2 * (W + 24) + 8, 64), BG)
    for i, d in enumerate((d1, d2)):
        x = 8 + i * (W + 24)
        im.alpha_composite(d, (x, 8)); im.alpha_composite(up(d, 2), (x + 24, 8)); im.alpha_composite(up(d, 3), (x + 64, 8))
    return im


def write_html():
    def row(src, cap):
        cells = "".join(f'<figure><div class="chk"><img src="{src}" width="{16*k}" height="{16*k}" alt=""></div>'
                        f'<figcaption>{k}x</figcaption></figure>' for k in (1, 2, 3, 8))
        return f'<div class="row">{cells}<figcaption style="max-width:260px">{cap}</figcaption></div>'
    body = ""
    info = {"A": ("Opção A · cápsula da referência do dono",
                  "nv.1: corpo creme com visor e LED verde, faixa laranja, broca cônica prateada (o R2 da rodada 4, afinado). "
                  "nv.2: a mesma cápsula e a mesma posição de visor e broca, mas em <b>aço cinza com tampa, faixa e base douradas</b> "
                  "(o dourado das máquinas nv.2), LED ciano, broca mais grossa (7 linhas contra 5) com <b>ponta de diamante ciano</b>."),
            "B": ("Opção B · pistola de perfil",
                  "nv.1: a pistola do <code>drill_side.png</code> redesenhada limpa em 16 px (carcaça cinza, visor ciano, faixa laranja, cabo com base laranja, broca fina). "
                  "nv.2: carcaça mais alta, <b>tampa e faixa douradas</b>, cabo mais grosso com base dourada, broca grossa com <b>ponta ciano</b>.")}
    for o in "AB":
        t, d = info[o]
        body += f'<h2>{t}</h2><p>{d}</p>'
        body += '<h3>nv.1</h3>' + row(f"icon_hand_drill_{o}.png", "icon_hand_drill_" + o)
        body += '<h3>nv.2</h3>' + row(f"icon_hand_drill_t2_{o}.png", "icon_hand_drill_t2_" + o)
        body += f'<h3>Hotbar (a nv.1 selecionada) e painel de receita 3x</h3><div class="row"><figure><img class="px" src="hotbar_{o}.png" width="672" height="144" alt=""><figcaption>fios, nv.1, nv.2, circuito, lingote</figcaption></figure></div>'
        body += (f'<div class="row"><figure><div class="chk"><img src="icon_hand_drill_{o}.png" width="48" height="48" alt=""></div></figure>'
                 f'<span style="font-size:30px;color:#a8968a">&rarr;</span><figure><div class="chk"><img src="icon_hand_drill_t2_{o}.png" width="48" height="48" alt=""></div></figure>'
                 f'<figcaption>receita 3x: nv.1 vira nv.2</figcaption></div>')
    body += ('<h2>Comparação com a atual (Y, provisória)</h2><div class="row"><figure><div class="chk"><img src="atual_Y.png" width="128" height="128" alt=""></div><figcaption>atual Y</figcaption></figure>'
             '<figure><img class="px" src="hotbar_Y.png" width="672" height="144" alt=""><figcaption>hotbar: Y + nv.2 da opção A</figcaption></figure></div>'
             '<p>A Y é o quadro 0 do drill_side reduzido por nearest, com a broca e o contorno falhados e sem espaço pra diferenciar uma nv.2.</p>')
    body += ('<h2>Pro Dev integrar</h2><ul><li>Quando o dono escolher A ou B: copiar <code>icon_hand_drill_{O}.png</code> para '
             '<code>assets/sprites/icon_hand_drill.png</code> e <code>icon_hand_drill_t2_{O}.png</code> para <code>assets/sprites/icon_hand_drill_t2.png</code> (16x16, alpha 0/255, contorno #1b1630).</li>'
             '<li>Sem mudança de âncora nem de escala: o jogo desenha em 2x no slot e 3x no painel de receita, como os outros <code>icon_*</code>.</li>'
             '<li>Gerado por <code>tools/sprites/v06_fundo_m4_broca.py</code> (determinístico). Nada foi instalado em <code>assets/sprites/</code> ainda.</li></ul>')
    css = open(OLD.parent / "index.html").read().split("<style>")[1].split("</style>")[0].split(".a-c")[0]
    html = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Hesper · v0.6 Fundo M4 · Broca de mão nv.1 e nv.2</title><style>{css}'
            'h3{font:600 15px monospace;color:#f2c46d;margin:18px 0 6px}</style></head><body><div class="wrap">'
            '<h1>v0.6 Fundo M4 · Broca de mão nv.1 e nv.2</h1>'
            '<div class="v2"><b>v1.0 · o que mudou</b><ul><li>2 opções de par (A e B) de ícones 16x16: a nv.1 definitiva e a nova '
            '<b>Broca de mão nv.2</b> (minera x1,5 e quebra rocha dura de gelo e basalto). A nv.2 se distingue da nv.1 pela cor de destaque (dourado em vez de laranja), '
            'corpo mais parrudo e ponta de diamante ciano.</li><li>Estilo: das referências do dono (R1/R2) só a proporção e a leitura de cápsula; todo o desenho é original.</li></ul></div>'
            f'{body}</div></body></html>')
    (REP / "index.html").write_text(html)


def main():
    REP.mkdir(parents=True, exist_ok=True)
    cvs = build()
    ims = {}
    for n, cv in cvs.items():
        im = cv.image(); im.save(REP / f"{n}.png"); ims[n] = im
    atual = load(SPR / "icon_hand_drill.png")
    atual.save(REP / "atual_Y.png")
    for o in "AB":
        n1, n2 = ims[f"icon_hand_drill_{o}"], ims[f"icon_hand_drill_t2_{o}"]
        up(hotbar(n1, n2), 3).save(REP / f"hotbar_{o}.png")
    up(hotbar(atual, ims["icon_hand_drill_t2_A"]), 3).save(REP / "hotbar_Y.png")
    write_html()
    print("ok")


if __name__ == "__main__":
    main()
