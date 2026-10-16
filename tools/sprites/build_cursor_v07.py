#!/usr/bin/env python3
"""Cursores do mouse v0.7 (opcoes A/B/C, 2 estados cada). Saida SO em reports/design/v07_cursor/pendentes/.
A UI do jogo desenha em 480x270 logico e escala (k=4 no Grande, 3 Media, 2 Pequena): 1 px aqui = k px na tela."""
import json, os, random
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "reports", "design", "v07_cursor")
PEND = os.path.join(OUT, "pendentes")
SPR = os.path.join(ROOT, "assets", "sprites")
os.makedirs(PEND, exist_ok=True)

PAL = {"k": (27, 22, 48, 255), "w": (255, 255, 255, 255), "g": (176, 184, 204, 255),
       "o": (226, 115, 58, 255), "d": (150, 66, 30, 255), "y": (255, 190, 120, 255),
       "f": (242, 196, 109, 255)}

def from_ascii(rows, w=None, h=None):
    w = w or max(len(r) for r in rows); h = h or len(rows)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in PAL: im.putpixel((x, y), PAL[c])
    return im

ARROW = ["k..........", "kk.........", "kwk........", "kwwk.......", "kwwwk......", "kwwwwk.....",
         "kwwwwwk....", "kwwwwwwk...", "kwwwwwwwk..", "kwwwwwkkkk.", "kwwkwwk....", "kwk.kwwk...",
         "kk..kwwk...", "k....kwwk..", ".....kwwk..", "......kk..."]

def recolor(rows, mp):
    return ["".join(mp.get(c, c) for c in r) for r in rows]

def shade_right(rows, light, dark):
    """w -> light; o ultimo pixel de preenchimento de cada linha (antes do k) -> dark."""
    out = []
    for r in rows:
        r = list(r)
        for i in range(1, len(r)):
            if r[i] == "k" and r[i - 1] in "wo" and (i + 1 >= len(r) or r[i + 1] != "w"):
                r[i - 1] = dark
        out.append("".join(r))
    return out

# ---- A: seta branca classica + luva de astronauta
A_N = shade_right(ARROW, "w", "g")
A_I = ["...kkk........", "..kwwgk.......", "..kwwgk.......", "..kwwgk.......", "..kwwgkkkk....",
       "..kwwgkwgkkk..", "kkkwwgkwgkwgkk", "kwwkwwwwwwwwgk", "kwwwwwwwwwwwgk", ".kwwwwwwwwwwgk",
       ".kwwwwwwwwwgk.", "..kwwwwwwwwgk.", "..kyoooooodk..", "..kooooooodk..", "..kkkkkkkkkk.."]
A_I = [r.ljust(14, ".") for r in A_I]

# ---- B: seta laranja (acento das maquinas) + selo de engrenagem/faisca quando interativo
B_N = shade_right(recolor(ARROW, {"w": "o"}), "o", "d")
B_N = [r.replace("o", "o") for r in B_N]
# brilho claro na borda esquerda do preenchimento
B_N = ["".join("y" if (c == "o" and i > 0 and r[i - 1] == "k" and n in (3, 4, 5, 6, 7)) else c for i, c in enumerate(r))
       for n, r in enumerate(B_N)]
B_I_arrow = shade_right(ARROW, "w", "g")
BADGE = [".kkk.", "kfffk", "kfwfk", "kfffk", ".kkk."]
def build_B_I():
    im = from_ascii(B_I_arrow, 17, 16)
    b = Image.new("RGBA", (5, 5), (0, 0, 0, 0))
    plus = ["..k..", ".kfk.", "kfwfk", ".kfk.", "..k.."]
    b = from_ascii(plus)
    im.alpha_composite(b, (11, 8))
    return im

# ---- C: reticulo (hotspot no centro)
def build_C(interactive):
    S = 17; c = 8
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = set()
    if not interactive:
        for d in (3, 4, 5):
            mask |= {(c + d, c), (c - d, c), (c, c + d), (c, c - d)}
        col = PAL["w"]; mask.add((c, c))
    else:
        L = 5
        for sx in (-1, 1):
            for sy in (-1, 1):
                for i in range(3):
                    mask.add((c + sx * L, c + sy * (L - i))); mask.add((c + sx * (L - i), c + sy * L))
        mask.add((c, c)); mask.add((c + 1, c)); mask.add((c - 1, c)); mask.add((c, c + 1)); mask.add((c, c - 1))
        col = PAL["o"]
    out = set()
    for (x, y) in mask:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (x + dx, y + dy)
                if p not in mask and 0 <= p[0] < S and 0 <= p[1] < S: out.add(p)
    for p in out: base.putpixel(p, PAL["k"])
    for p in mask: base.putpixel(p, col)
    if interactive: base.putpixel((c, c), PAL["w"])
    return base

SETS = {
    "A": {"nome": "Seta e luva", "normal": from_ascii(A_N), "interativo": from_ascii(A_I),
          "hot_n": (0, 0), "hot_i": (4, 0),
          "desc": "Seta branca clássica; ao passar em algo usável vira a luva do astronauta apontando (punho laranja)."},
    "B": {"nome": "Seta laranja", "normal": from_ascii(B_N, 17, 16), "interativo": build_B_I(),
          "hot_n": (0, 0), "hot_i": (0, 0),
          "desc": "Seta laranja (acento das máquinas); ao passar em algo usável fica branca e ganha um selo dourado de faísca."},
    "C": {"nome": "Retículo", "normal": build_C(False), "interativo": build_C(True),
          "hot_n": (8, 8), "hot_i": (8, 8),
          "desc": "Mira de astronauta, hotspot no centro; ao passar em algo usável as pontas viram colchetes laranja fechando."},
}

def save_x(im, path, k): im.resize((im.width * k, im.height * k), Image.NEAREST).save(path)

for key, s in SETS.items():
    for st in ("normal", "interativo"):
        s[st].save(os.path.join(PEND, f"cursor_{key}_{st}.png"))
        save_x(s[st], os.path.join(PEND, f"cursor_{key}_{st}_x8.png"), 8)

# ---- fundos (logico 1:1)
def tile_bg(name, w, h):
    t = Image.open(os.path.join(SPR, name)).convert("RGBA")
    im = Image.new("RGBA", (w, h))
    for y in range(0, h, 32):
        for x in range(0, w, 32): im.paste(t, (x, y))
    return im

def bgs():
    W, H = 150, 70
    d = {}
    d["areia (névoa)"] = tile_bg("sand_mist_0.png", W, H)
    d["chão morto (poeira)"] = tile_bg("floor_dead_0.png", W, H)
    r = random.Random(7); cave = Image.new("RGBA", (W, H), (24, 20, 34, 255))
    for _ in range(260):
        x, y = r.randrange(W), r.randrange(H); v = r.choice([(32, 28, 44), (18, 15, 27), (40, 35, 52)])
        cave.putpixel((x, y), v + (255,))
    d["caverna escura"] = cave
    pan = Image.new("RGBA", (W, H), (15, 17, 25, 255))
    for gx in range(6):
        for gy in range(3):
            x0, y0 = 8 + gx * 22, 8 + gy * 20
            for x in range(x0, x0 + 18):
                for y in range(y0, y0 + 16):
                    edge = x in (x0, x0 + 17) or y in (y0, y0 + 15)
                    pan.putpixel((x, y), (58, 62, 82, 255) if edge else (30, 33, 46, 255))
    d["painel de inventário"] = pan
    return d

BG = bgs()
def scene(bg):
    im = bg.copy()
    for i, (key, s) in enumerate(SETS.items()):
        for j, st in enumerate(("normal", "interativo")):
            im.alpha_composite(s[st], (14 + j * 62, 8 + i * 20))
    return im
names = {}
for n, bg in BG.items():
    fn = "cena_" + "".join(c if c.isalnum() else "_" for c in n.split(" (")[0]) + ".png"
    scene(bg).save(os.path.join(PEND, fn)); names[n] = fn

# ---- tela real: 1920x1080 grande k=4 (recorte 480x270 logico em 1 cena)
full = tile_bg("sand_mist_0.png", 480, 270)
pan = Image.new("RGBA", (150, 100), (15, 17, 25, 246)); full.alpha_composite(pan, (300, 20))
for i, (key, s) in enumerate(SETS.items()):
    full.alpha_composite(s["normal"], (60 + i * 40, 60)); full.alpha_composite(s["interativo"], (60 + i * 40, 110))
    full.alpha_composite(s["normal"], (330 + i * 40, 60))
save_x(full, os.path.join(PEND, "tela_grande_k4_crop.png"), 3)

json.dump({k: {"tamanho": list(v["normal"].size), "hotspot_normal": v["hot_n"], "hotspot_interativo": v["hot_i"],
               "tamanho_interativo": list(v["interativo"].size)} for k, v in SETS.items()},
          open(os.path.join(PEND, "cursor_meta.json"), "w"), indent=1)

# ---- report
def sec_set(key, s):
    ni, ii = s["normal"], s["interativo"]
    def fig(st, im, hot):
        return (f'<figure><div class="chk hs" style="--hx:{hot[0]*10}px;--hy:{hot[1]*10}px"><img src="pendentes/cursor_{key}_{st}_x8.png" style="width:{im.width*10}px"><i></i></div>'
                f'<figcaption>{st} · {im.width}×{im.height} · hotspot ({hot[0]},{hot[1]})</figcaption></figure>')
    return (f'<div class="pair"><h3>Opção {key} · {s["nome"]}</h3><p>{s["desc"]}</p><div class="ab">'
            + fig("normal", ni, s["hot_n"]) + fig("interativo", ii, s["hot_i"]) + '</div></div>')

scenes = "".join(f'<figure><img class="sc" src="pendentes/{fn}" style="width:600px"><figcaption>{n} · linhas: A, B, C · colunas: normal, interativo</figcaption></figure>' for n, fn in names.items())
rows = "".join(f'<tr><td>{k}</td><td>cursor_{k}_normal.png</td><td>{v["normal"].width}×{v["normal"].height}</td><td>({v["hot_n"][0]}, {v["hot_n"][1]})</td>'
               f'<td>cursor_{k}_interativo.png</td><td>{v["interativo"].width}×{v["interativo"].height}</td><td>({v["hot_i"][0]}, {v["hot_i"][1]})</td></tr>' for k, v in SETS.items())
html = f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Cursor do mouse · v0.7</title>
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--gold:#f2c46d;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1200px;margin:0 auto;padding:44px 0 80px}}h1{{font-size:40px;margin:8px 0}}h2{{font-size:24px;margin:44px 0 12px;border-left:10px solid var(--rust);padding-left:10px}}
h3{{margin:0 0 6px}}code{{color:var(--gold)}}p,li{{color:var(--muted)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--rust);padding:12px 18px;max-width:1000px}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px;position:relative}}
.hs i{{position:absolute;left:calc(10px + var(--hx));top:calc(10px + var(--hy));width:10px;height:10px;outline:2px solid #ff2fd0;outline-offset:-1px}}
img{{image-rendering:pixelated;display:block}}figure{{margin:0}}figcaption{{font-size:12px;color:var(--muted);margin-top:6px}}
.pairs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:18px}}.pair{{background:var(--panel);border:1px solid var(--line);padding:14px}}
.ab{{display:flex;gap:24px;align-items:flex-end;flex-wrap:wrap}}.scenes{{display:flex;gap:18px;flex-wrap:wrap}}
table{{border-collapse:collapse}}td,th{{border:1px solid var(--line);padding:4px 10px;text-align:left;color:var(--muted)}}
</style></head><body><div class="wrap">
<p style="color:var(--rust);margin:0">REPORT DE DESIGN · v0.7</p><h1>Cursor do mouse</h1>
<div class="v2"><b>v0.7 · cursor novo, 3 opções.</b> Hoje o cursor é um polígono branco/preto desenhado em código. Aqui vão 3 conjuntos (normal + interativo) em pixel art, contorno <code>#1b1630</code>, acento <code>#e2733a</code>. Nada entrou em <code>assets/sprites/</code>: aguardando escolha do dono. O quadradinho magenta nas ampliações marca o <b>hotspot</b>.</div>
<h2>As 3 opções (ampliadas 10×)</h2><div class="pairs">{"".join(sec_set(k, s) for k, s in SETS.items())}</div>
<h2>Prévia 1:1 nos fundos do jogo (resolução lógica da UI, ampliada 4× pelo navegador)</h2>
<p>Cada imagem está no tamanho lógico (150×70 px); aqui exibida a 4×, o mesmo que o jogo faz no tamanho de UI Grande.</p><div class="scenes">{scenes}</div>
<h2>Na tela real (UI Grande, k=4; recorte 480×270 lógico)</h2>
<p>Esquerda: fundo de areia com os 3 conjuntos (normal em cima, interativo embaixo). Direita: sobre um painel escuro.</p>
<img src="pendentes/tela_grande_k4_crop.png" style="width:1440px;max-width:100%">
<h2>Pro Dev integrar</h2><ul>
<li><b>Escala:</b> a UI desenha em 480×270 lógicos e é escalada por k inteiro (Grande 4, Média 3, Pequena 2; mínimo 2). Cursor com ~11×16 px lógicos vira 44×64 px no Grande e 22×32 no Pequeno. Se achar grande demais no Grande, dá pra desenhar o sprite direto na janela (k=1) em vez da camada da UI, mas isso é decisão de código.</li>
<li><b>Onde trocar:</b> <code>UI.draw_cursor(x, y)</code> em <code>game/ui.py</code> (~linha 2995), chamado em <code>game/app.py</code> (~2365) e <code>game/title.py</code> (~294) com <code>mouse_ui</code>. Trocar o polígono por <code>surf.blit(sprite, (x - hot_x, y - hot_y))</code> e escolher normal/interativo conforme o mouse esteja sobre algo usável (caixa, terminal, baú, máquina, destroço; o Dev já sabe isso pro realce/prompt). Esconder o cursor do sistema (<code>pygame.mouse.set_visible(False)</code>) se ainda não estiver.</li>
<li><b>Hotspot:</b> o pixel de clique é o (hx, hy) abaixo, relativo ao canto superior esquerdo do PNG. Alpha só 0/255.</li>
<li><b>Arquivos (após aprovação, copiar de <code>pendentes/</code> para <code>assets/sprites/ui/</code> ou similar; o contrato §6 precisa ganhar o nome):</b></li></ul>
<table><tr><th>Opção</th><th>Normal</th><th>Tam.</th><th>Hotspot</th><th>Interativo</th><th>Tam.</th><th>Hotspot</th></tr>{rows}</table>
<p>Gerado por <code>python3 tools/sprites/build_cursor_v07.py</code> (determinístico). Metadados em <code>pendentes/cursor_meta.json</code>.</p>
</div></body></html>'''
open(os.path.join(OUT, "index.html"), "w").write(html)
print("ok")
