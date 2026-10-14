"""Galeria única com todos os sprites de assets/sprites/ (pra mandar pra outra IA como referência de estilo).

Gera reports/design/galeria/index.html, autossuficiente: cada PNG vai embutido em base64
uma vez só (classe CSS por sprite), então o 1× e o 4× usam o mesmo dado.

Uso: python3 tools/sprites/build_gallery.py
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SPR = ROOT / "assets" / "sprites"
OUT = ROOT / "reports" / "design" / "galeria" / "index.html"
WARN_MB = 15

# Regras de categoria pelo prefixo do nome (ordem importa: a 1ª que casar vence).
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Player / personagem", ("player", "drill_hand")),
    ("Ícones e itens", ("icon_", "pickup_")),
    ("Minérios e veios", ("ore_", "vein_")),
    ("Paredes e rochas", ("wall_", "rock_", "hill_")),
    ("Chão e tiles", ("floor_", "sand_", "water", "ground_", "decal_")),
    ("Máquinas e objetos", ("machine_", "drill", "drone", "chest", "container", "loot_crate",
                            "terminal", "pod", "solar", "lamp", "crater", "wreck_", "cave_")),
    ("UI", ("ui_",)),
]
OTHER = "Outros"

# Seções fixas, na ordem em que aparecem na página.
MAIN_ORDER = [r[0] for r in RULES] + [OTHER]


def categoria(nome: str) -> str:
    for cat, prefixos in RULES:
        if nome.startswith(prefixos):
            return cat
    return OTHER


def coletar() -> list[dict]:
    """Devolve uma lista de sprites: {secao, grupo, rel, path, w, h}."""
    itens: list[dict] = []
    for p in sorted(SPR.rglob("*.png")):
        rel = p.relative_to(SPR)
        partes = rel.parts
        if partes[0] == "_pending":
            secao = "Pendentes (NÃO está no jogo)"
            grupo = partes[1] if len(partes) > 2 else "raiz"
        elif partes[0] == "_future":
            secao = "Futuros (NÃO está no jogo)"
            grupo = "raiz"
        elif partes[0] == "anim":
            secao = "Animações (tiras)"
            grupo = "anim"
        elif partes[0] == "regions":
            secao = "Superfície · regiões (v0.4)"
            grupo = p.stem.split("_")[0]
        else:
            secao = categoria(p.name)
            grupo = "raiz"
        w, h = Image.open(p).size
        itens.append({"secao": secao, "grupo": grupo, "rel": rel.as_posix(),
                      "path": p, "w": w, "h": h})
    return itens


def ordem_secao(s: str) -> int:
    if s in MAIN_ORDER:
        return MAIN_ORDER.index(s)
    return len(MAIN_ORDER) + ["Animações (tiras)", "Superfície · regiões (v0.4)",
                              "Pendentes (NÃO está no jogo)", "Futuros (NÃO está no jogo)"].index(s)


CSS = """
:root{--bg:#121014;--panel:#1d1a20;--line:#34303a;--fg:#ece8f0;--muted:#9d95a8;--acc:#e2733a}
:root[data-bg="xadrez"]{--bg:#2a2a2a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,sans-serif;padding:0 16px 64px}
body.xadrez .card .stage{background-color:#3a3a3a;background-image:conic-gradient(#4a4a4a 25%,transparent 0 50%,#4a4a4a 0 75%,transparent 0);background-size:16px 16px}
.wrap{max-width:1280px;margin:0 auto}
header{padding:32px 0 16px;border-bottom:1px solid var(--line)}
h1{margin:0 0 8px;font-size:28px}
.lang{color:var(--muted);margin:0 0 10px;max-width:80ch}
.tog{margin-top:12px;background:var(--panel);color:var(--fg);border:1px solid var(--line);padding:6px 12px;cursor:pointer;font:inherit}
nav.idx{margin:20px 0;display:flex;flex-wrap:wrap;gap:8px}
nav.idx a{color:var(--fg);text-decoration:none;background:var(--panel);border:1px solid var(--line);padding:4px 10px;font-size:13px}
nav.idx a.off{border-style:dashed;color:var(--muted)}
nav.idx b{color:var(--acc);font-weight:600}
section{margin-top:36px}
section h2{font-size:20px;margin:0 0 4px;border-left:3px solid var(--acc);padding-left:10px}
section h2 small{color:var(--muted);font-weight:400;font-size:13px}
section .sub{color:var(--muted);margin:0 0 14px;font-size:13px}
h3{font-size:14px;color:var(--muted);margin:22px 0 10px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);padding:10px;min-width:0}
.card .nm{font:12px ui-monospace,monospace;word-break:break-all}
.card .sz{color:var(--muted);font-size:12px;margin-bottom:8px}
.stage{display:flex;align-items:center;justify-content:center;background:#0c0b0e;min-height:48px;padding:8px;overflow:auto;max-width:100%}
.stage+.stage{margin-top:8px}
.lbl{font-size:11px;color:var(--muted);margin:8px 0 4px;text-transform:uppercase;letter-spacing:.05em}
.spr{background-repeat:no-repeat;background-size:100% 100%;image-rendering:pixelated;image-rendering:-webkit-optimize-contrast;flex:none}
.wide{display:block;overflow-x:auto}
.warn{color:#f2c46d}
"""

JS = """
(function(){
  var b=document.getElementById('tog'), r=document.documentElement;
  function ap(){ var x=b.getAttribute('aria-pressed')==='true';
    document.body.classList.toggle('xadrez',x); r.setAttribute('data-bg',x?'xadrez':'escuro');
    b.textContent=x?'Fundo: xadrez (clique pra escuro)':'Fundo: escuro (clique pra xadrez)'; }
  b.addEventListener('click',function(){ b.setAttribute('aria-pressed',b.getAttribute('aria-pressed')==='true'?'false':'true'); ap(); });
  ap();
})();
"""


def card(i: int, it: dict) -> str:
    w, h = it["w"], it["h"]
    nome = html.escape(it["rel"])
    cls = f"s{i}"
    # 4× com rolagem horizontal se for maior que o card (tiras de animação e regiões).
    return (
        f'<div class="card">'
        f'<div class="nm">{nome}</div>'
        f'<div class="sz">{w} × {h} px</div>'
        f'<div class="lbl">1×</div>'
        f'<div class="stage"><div class="spr {cls}" role="img" aria-label="{nome}" '
        f'style="width:{w}px;height:{h}px"></div></div>'
        f'<div class="lbl">4×</div>'
        f'<div class="stage wide"><div class="spr {cls}" role="img" aria-label="{nome} 4x" '
        f'style="width:{w * 4}px;height:{h * 4}px"></div></div>'
        f'</div>'
    )


def build() -> None:
    itens = coletar()
    itens.sort(key=lambda it: (ordem_secao(it["secao"]), it["grupo"], it["rel"]))

    css_sprites = []
    for i, it in enumerate(itens):
        b64 = base64.b64encode(it["path"].read_bytes()).decode("ascii")
        css_sprites.append(f".s{i}{{background-image:url(data:image/png;base64,{b64})}}")

    # Índice e seções.
    secoes: dict[str, list[tuple[int, dict]]] = {}
    for i, it in enumerate(itens):
        secoes.setdefault(it["secao"], []).append((i, it))
    ordem = sorted(secoes, key=ordem_secao)

    idx_html = []
    for s in ordem:
        off = "off" if s.startswith(("Pendentes", "Futuros")) else ""
        ancora = "sec-" + str(ordem_secao(s))
        idx_html.append(f'<a class="{off}" href="#{ancora}">{html.escape(s)} <b>{len(secoes[s])}</b></a>')

    corpo = []
    for s in ordem:
        ancora = "sec-" + str(ordem_secao(s))
        lista = secoes[s]
        aviso = ""
        if s.startswith(("Pendentes", "Futuros")):
            aviso = '<p class="sub warn">Não está no jogo: rascunhos e candidatos, pra referência de estilo.</p>'
        partes = [f'<section id="{ancora}"><h2>{html.escape(s)} <small>{len(lista)} sprites</small></h2>{aviso}']
        grupo_atual = None
        for i, it in lista:
            if it["grupo"] != grupo_atual:
                if grupo_atual is not None:
                    partes.append("</div>")
                grupo_atual = it["grupo"]
                if len(secoes[s]) and len({x["grupo"] for _, x in lista}) > 1:
                    partes.append(f'<h3>{html.escape(grupo_atual)}</h3>')
                partes.append('<div class="grid">')
            partes.append(card(i, it))
        partes.append("</div></section>")
        corpo.append("".join(partes))

    total = len(itens)
    doc = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · Galeria de sprites</title>
<style>
{CSS}
{chr(10).join(css_sprites)}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Hesper · Galeria completa de sprites</h1>
  <p class="lang"><b>PT-BR.</b> Pixel art top-down 3/4 (estilo Core Keeper, com a pegada do The Planet Crafter). Tile de 32×32 px, sprites na escala 1:1 (o jogo não redimensiona). Contorno escuro (<code>#1b1630</code> nas regiões) com sombra chapada. As máquinas e o baú seguem a família r3d (freela r3d v1.2, sapata B).</p>
  <p class="lang"><b>EN.</b> Top-down 3/4 pixel art (Core Keeper style, with The Planet Crafter's feel). 32×32 px tiles, sprites at 1:1 scale (the game does not resize them). Dark outline (<code>#1b1630</code> in the regions) with flat shadow. Machines and the chest belong to the r3d family (freela r3d v1.2, sapata B).</p>
  <button id="tog" class="tog" type="button" aria-pressed="false">Fundo: escuro (clique pra xadrez)</button>
  <p class="lang">{total} sprites · {len(ordem)} seções · gerado por <code>tools/sprites/build_gallery.py</code></p>
  <nav class="idx">{"".join(idx_html)}</nav>
</header>
{"".join(corpo)}
</div>
<script>{JS}</script>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")

    mb = OUT.stat().st_size / 1e6
    print(f"{OUT.relative_to(ROOT)}: {mb:.2f} MB, {total} sprites")
    for s in ordem:
        print(f"  {len(secoes[s]):4d}  {s}")
    if mb > WARN_MB:
        print(f"AVISO: passou de {WARN_MB} MB ({mb:.1f} MB)")


if __name__ == "__main__":
    build()
