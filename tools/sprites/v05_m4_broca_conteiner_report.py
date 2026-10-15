"""Report do v0.5 M4 · broca de mão e contêiner aberto (reports/design/v05_m4_broca_conteiner/index.html).
Só LÊ assets/. Cenas montadas só com os sprites."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v05_m4_broca_conteiner as G  # noqa: E402

SPR, REP, PEND = G.SPR, G.REP, G.PEND


def load(p):
    return Image.open(p).convert("RGBA")


def hotbar(cand):
    """Hotbar de 7 slots (ui_slot 20×20): a broca de mão no 1, selecionada, e os ícones de item que já existem."""
    slot = load(SPR / "ui_slot.png")
    icons = [load(PEND / f"icon_hand_drill_{cand}.png")] + [load(SPR / f"icon_{n}.png") for n in
             ("scanner", "chest", "lamp", "drill", "o2_tank", "iron")]
    out = Image.new("RGBA", (len(icons) * 22 + 2, 24), (22, 17, 14, 255))
    for i, ic in enumerate(icons):
        x = 2 + i * 22
        out.alpha_composite(slot, (x, 2))
        out.alpha_composite(ic, (x + 2, 4))
        if i == 0:                                            # seleção (o jogo desenha um contorno claro)
            for xx in range(x - 1, x + 21):
                for yy in (1, 22):
                    out.putpixel((xx, yy), (242, 196, 109, 255))
            for yy in range(1, 23):
                for xx in (x - 1, x + 20):
                    out.putpixel((xx, yy), (242, 196, 109, 255))
    return out


def ground(w, h):
    tiles = [load(SPR / f"sand_dead_{i}.png") for i in range(4)]
    cv = Image.new("RGBA", (w, h))
    for ty in range(h // 32 + 1):
        for tx in range(w // 32 + 1):
            cv.alpha_composite(tiles[(tx * 3 + ty * 5) % 4], (tx * 32, ty * 32))
    return cv


def scene():
    """Chão do Morto com o contêiner fechado e os abertos A/B lado a lado, pé no centro de baixo do tile.
    O jogador (drill_side não, só o explorer parado) fica ao lado pra dar escala."""
    W, H = 288, 96
    cv = ground(W, H)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    items = [load(SPR / "container_sealed.png"), load(PEND / "container_open_A.png"), load(PEND / "container_open_B.png")]
    for i, im in enumerate(items):
        cx = 48 + i * 96
        y_foot = 80
        cv.alpha_composite(im, (cx - im.width // 2, y_foot - im.height))
    return cv


def ref_big(src, cap):
    load(SPR / src).crop((0, 0, 64, 80)).save(REP / "ref_machine_drill_f0.png")
    return (f'<figure><div class="chk"><img src="ref_machine_drill_f0.png" width="256" height="320" alt=""></div><figcaption>{cap}</figcaption></figure>')


def ref_big2(src, cap):
    return (f'<figure><div class="chk"><img src="ref_drill_side_f0.png" width="240" height="160" alt=""></div><figcaption>{cap}</figcaption></figure>')


ASSETS_DRILL = SPR / "icon_drill.png"


def tabs():
    """Fileira de abas do construtor (FAB_TAB_ICON de game/ui.py:89) com a aba Base no fim, em 3 versões."""
    names = ["workbench", "constructor", None, "solar", "drill", "chest", "lamp", "o2_tank"]
    out = {}
    for tag, drill_src, base_src in (("hoje", SPR / "icon_drill.png", None),
                                     ("A", ASSETS_DRILL, PEND / "icon_tab_base_1.png"),
                                     ("B", ASSETS_DRILL, PEND / "icon_tab_base_2.png")):
        icons = []
        for n in names:
            if n is None:
                icons.append(load(SPR / "icon_o2_dispenser.png"))
            elif n == "drill":
                icons.append(load(drill_src))
            else:
                icons.append(load(SPR / f"icon_{n}.png"))
        icons.append(load(base_src) if base_src else load(SPR / "icon_chest.png"))
        img = Image.new("RGBA", (len(icons) * 20 + 4, 24), (22, 17, 14, 255))
        for i, ic in enumerate(icons):
            x = 4 + i * 20
            for xx in range(x - 2, x + 16 + 2):
                for yy in range(2, 22):
                    img.putpixel((xx, yy), (38, 43, 59, 255) if i != len(icons) - 1 else (74, 56, 47, 255))
            img.alpha_composite(ic, (x, 4))
        img.save(REP / f"abas_{tag}.png")
        out[tag] = img.size
    return out


def build():
    REP.mkdir(parents=True, exist_ok=True)
    sc = scene()
    sc.save(REP / "cena_conteiner.png")
    for c in "ABC":
        hotbar(c).save(REP / f"hotbar_{c}.png")
    for c in "XY":
        hotbar(c).save(REP / f"hotbar3_{c}.png")
    # a broca da mão (quadro 0 do drill_side) pra comparação
    ds = load(SPR / "drill_side.png").crop((0, 0, 24, 16))
    ds.save(REP / "ref_drill_side_f0.png")

    def im(src, k, cap):
        w, h = Image.open(REP / src).size
        return (f'<figure><div class="chk"><img src="{src}" width="{w * k}" height="{h * k}" alt=""></div>'
                f'<figcaption>{cap}</figcaption></figure>')

    def ref(src, k, cap):
        w, h = load(SPR / src).size
        return (f'<figure><div class="chk"><img src="../../../assets/sprites/{src}" width="{w * k}" height="{h * k}" alt=""></div>'
                f'<figcaption>{cap}</figcaption></figure>')

    # ---- rodada 2
    def gr(name, k, cap):
        return im(f"pendentes/{name}.png", k, cap)
    old_drill = ref("icon_drill.png", 14, "icon_drill de hoje (o dono reprovou)")
    mach = ref_big("machine_drill.png", "machine_drill.png, quadro 0 (a máquina no chão)")
    r2_hand = (ref_big2("drill_side.png", "drill_side.png, quadro 0 (a que o player segura)") +
               gr("icon_hand_drill_1", 14, "1 · reto · recomendado") + gr("icon_hand_drill_2", 14, "2 · diagonal (girado 28°)"))
    r2_drill = old_drill + "".join(gr(f"icon_drill_{c}", 14, t) for c, t in (
        ("A", "A · a máquina inteira: base com tela, mastro, braço, cabeça e feixe no chão · recomendada"),
        ("B", "B · como A, com LED verde e mais uma faixa no mastro"),
        ("C", "C · só a cabeça e o feixe furando a placa do chão (mais simples)")))
    r2_base = "".join(gr(f"icon_tab_base_{c}", 14, t) for c, t in (
        ("A", "A · fachada: parede com faixa laranja, porta com luz e chão · recomendada"),
        ("B", "B · módulo da base em corte, com a porta e o chão")))
    r2_wall = "".join(ref(n, 14, n) for n in ("icon_base_wall.png", "icon_base_door.png", "icon_base_floor.png"))
    tabsz = tabs()
    tabfig = "".join(f'<figure><img class="px" src="abas_{t}.png" width="{tabsz[t][0] * 4}" height="{tabsz[t][1] * 4}" alt=""><figcaption>{c}</figcaption></figure>'
                     for t, c in (("hoje", "hoje: drill antiga e a aba Base caindo no ícone do baú (fallback)"),
                                  ("A", "porta entreaberta 1 (luz âmbar vazando)"), ("B", "porta entreaberta 2 (luz verde e poça de luz no chão)")))
    hot2 = "".join(f'<figure><img class="px" src="hotbar3_{c}.png" width="{(7 * 22 + 2) * 4}" height="{24 * 4}" alt=""><figcaption>hotbar com a opção {c}</figcaption></figure>' for c in "XY")
    r3_hand = (ref_big2("drill_side.png", "drill_side.png, quadro 0 original (10×)") +
               gr("icon_hand_drill_X", 14, "X · corpo idêntico, broca encurtada · recomendada") +
               gr("icon_hand_drill_Y", 14, "Y · quadro todo reduzido (nearest)"))
    r3_base = "".join(gr(f"icon_tab_base_{c}", 14, t) for c, t in (("1", "1 · luz âmbar vazando pela fresta"), ("2", "2 · luz verde e poça de luz no chão")))
    r3_drill = ref("icon_drill.png", 14, "icon_drill APROVADO (B, já em assets/)")
    icons = "".join(im(f"pendentes/icon_hand_drill_{c}.png", 14, f"{c}" + (" · recomendada" if c == "A" else ""))
                    for c in "ABC")
    conts = (ref("container_sealed.png", 8, "fechado (aprovado, hoje)") +
             im("pendentes/container_open_A.png", 8, "A · tampa toda aberta") +
             im("pendentes/container_open_B.png", 8, "B · tampa meio aberta (forçada) · APROVADA"))
    hot = "".join(f'<figure><img class="px" src="hotbar_{c}.png" width="{(7 * 22 + 2) * 4}" height="{24 * 4}" alt="">'
                  f'<figcaption>hotbar com a candidata {c}</figcaption></figure>' for c in "ABC")
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · v0.5 M4 · Broca de mão e contêiner aberto</title>
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1100px;margin:0 auto;padding:40px 0 80px}}
h1{{font:600 36px/1.1 monospace;margin:8px 0 12px}}h2{{font:600 22px monospace;margin:40px 0 12px;color:var(--cyan)}}
code{{color:var(--gold)}}p,li{{color:var(--muted)}}b{{color:var(--fg)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--cyan);padding:12px 18px}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px monospace;color:var(--muted);margin-top:6px}}
.row{{display:flex;gap:28px;align-items:flex-end;flex-wrap:wrap}}
.px{{border:1px solid var(--line)}}
.a-c{{width:320px;height:352px;background-size:100% 100%;animation:op 2.4s steps(1) infinite}}
@keyframes op{{0%{{background-image:url(../../../assets/sprites/container_sealed.png)}}50%{{background-image:url(pendentes/container_open_A.png)}}}}
</style></head><body><div class="wrap">
<h1>v0.5 M4 · Ícones novos e contêiner aberto</h1>
<div class="v2" style="border-left-color:#7fd67a"><b>Rodada 3 · v3.0 · o que mudou</b><ul>
<li><b><code>icon_drill</code> B aprovado</b>: copiado pra <code>assets/sprites/icon_drill.png</code> (substitui o antigo) e registrado no contrato §6.</li>
<li><b>Broca de mão: o sprite exato.</b> O quadro 0 do <code>drill_side.png</code> tem 19×10 px com contorno, então não cabe inteiro em 16 de largura.
<b>X</b>: as 16 primeiras colunas do corpo pixel a pixel (carcaça, faixa, LED, cabo, mandril) e a ponta da broca encurtada em 3 colunas.
<b>Y</b>: o quadro todo por nearest em 16×8 (perde a espiral e o contorno fica falhado, mas é "o desenho inteiro").
<b>Z</b> (canvas maior que 16×16): <b>não dá sem mexer em código</b>. O <code>item_icon</code> (<code>game/render.py</code>) escala o PNG ×2 e o slot
(<code>draw_slot</code>, <code>game/ui.py</code>) cola o resultado fixo em <code>(x*2+4, y*2+4)</code> sem centralizar; um ícone maior que 16×16 sai
do slot (40 px nativos, 32 de ícone + 4 de margem de cada lado). Recomendo <b>X</b>.</li>
<li><b>Aba Base com a porta entreaberta</b>: 2 opções, partindo da fachada A.</li></ul></div>

<h2>Rodada 3 · Broca de mão (sprite exato)</h2>
<div class="row">{r3_hand}</div>
<div class="row">{hot2}</div>
<p>A <b>X</b> mantém a carcaça, o LED, a faixa laranja e o cabo com a base laranja idênticos ao quadro 0; só a broca fica mais curta
(a espiral vira 2 listras). A Y mantém a broca comprida, mas amassa tudo na vertical e perde o cabo e o LED legíveis.</p>

<h2>Rodada 3 · Aba "Base" com a porta entreaberta</h2>
<div class="row">{r3_base}{r3_drill}</div>
<div class="row" style="flex-direction:column;align-items:flex-start">{tabfig}</div>
<p>Fileira de abas com o <code>icon_drill</code> novo e a aba Base em cada opção. Sugestão de nome: <code>icon_tab_base.png</code>.
<b>Recomendo a 1</b> (fresta amarela quente: lê "luz de dentro" mais rápido que o verde).</p>

<div class="v2" style="border-left-color:#f2c46d"><b>Rodada 2 · v2.0 · o que mudou (retorno do dono)</b><ul>
<li><b>Contêiner aberto: a B foi aprovada</b> e já está em <code>assets/sprites/container_open.png</code> (40×44), com a linha no contrato da bíblia §6.</li>
<li><b>Ícone da broca de mão refeito</b> a partir do quadro 0 do <code>drill_side.png</code>: carcaça cinza, faixa laranja, LED ciano, cabo escuro com base laranja, broca prateada. 2 opções (reto e diagonal).</li>
<li><b><code>icon_drill</code> (a drill automática) refeito</b> pra ler como a máquina do <code>machine_drill.png</code>: base com tela, mastro, braço, cabeça e feixe ciano entrando no chão com a brasa. 3 opções.</li>
<li><b>Ícone novo da aba Base</b> do construtor (<code>icon_tab_base</code>), com as cores dos blocos da base. 2 opções.</li>
<li>Os candidatos desta rodada ficam em <code>pendentes/</code> até o ok do dono.</li></ul></div>

<h2>Rodada 2 · Broca de mão (item 2)</h2>
<div class="row">{r2_hand}</div>
<p>Mantém a silhueta da broca da mão (carcaça, mandril escuro, broca cônica de aço, cabo com base laranja), reduzida pra 16×16
com contorno <code>#1b1630</code>. O <b>1</b> é o reto, o mais fiel ao quadro 0; o <b>2</b> é o mesmo girado 28° (cabe na diagonal,
mas o cabo vira escada e perde limpeza). <b>Recomendo o 1.</b></p>
<div class="row">{hot2}</div>

<h2>Rodada 2 · Drill automática (item 3) · B APROVADA</h2>
<div class="row">{mach}{r2_drill}</div>
<p>A fonte é a máquina do chão: pedestal bege com a tela escura, mastro com faixa laranja, braço, cabeça bege com o LED e o feixe
ciano furando o chão (brasa laranja e faíscas). No <b>A</b> sobra espaço vazio entre o mastro e a cabeça pra silhueta não virar
caixa. O <b>C</b> é o mais legível em 16 px, mas já não mostra a máquina inteira. <b>Recomendo A.</b></p>

<h2>Rodada 2 · Aba "Base" do construtor (item 4)</h2>
<div class="row">{r2_base}{r2_wall}</div>
<p>Os 3 últimos são os ícones de item da base (parede, porta, chão), pra comparar: o da aba é bem diferente deles (um é o
conjunto montado, os outros são peças soltas). <b>Recomendo A</b> (parede + porta + chão numa fachada só, lê "construir base").</p>
<div class="row" style="flex-direction:column;align-items:flex-start">{tabfig}</div>
<p>Fileira de abas do fabricador na ordem de <code>FAB_TAB_ICON</code> (<code>game/ui.py</code>) com a aba Base no fim (a última, marrom).
Nome sugerido: <code>icon_tab_base.png</code> (a candidata escolhida renomeada).</p>

<h2>Rodada 1 · Contêiner aberto (B aprovado) e broca de mão (substituída pela rodada 2)</h2>
<div class="v2"><b>v1.0 · o que mudou (proposta, espera o ok do dono)</b><ul>
<li><b>Ícone da broca de mão nv.1</b> (<code>icon_hand_drill</code>, 16×16): a mesma pistola do <code>drill_side.png</code> que o
player segura (carcaça cinza-metal, faixa laranja, LED ciano, cabo escuro, mandril e broca cônica de aço), de perfil, bocal pra
direita, contorno <code>#1b1630</code>. Não confunde com o <code>icon_drill</code> (a drill automática é uma máquina branca com
pé e broca pra baixo).</li>
<li><b>Contêiner aberto</b> (<code>container_open</code>, 40×44): o mesmo modelo r3d v1.1 do <code>container_sealed</code>
(mesma caixa, pivô e pé), com a tampa girada pra trás na dobradiça, o miolo escuro e vazio, o trinco levantado, as duas
cintas de aço cortadas (só o coto) e o selo dourado partido.</li>
<li><b>B aprovada</b> e promovida a <code>container_open.png</code>. O resto da rodada 1 (broca A/B/C) foi substituído pela rodada 2.</li></ul></div>

<h2>Ícone da broca de mão · 3 candidatas</h2>
<div class="row">{icons}
{ref("icon_drill.png", 14, "icon_drill (a drill AUTOMÁTICA, pra comparar)")}
<figure><div class="chk"><img src="ref_drill_side_f0.png" width="240" height="160" alt=""></div><figcaption>drill_side.png, quadro 0 (a que o player segura)</figcaption></figure></div>
<p><b>A</b> é a fiel à da mão (carcaça mais comprida, cabo fino, bit cônico). <b>B</b> é mais robusta, com a bateria laranja
grande no cabo: lê melhor como "equipamento", mas se afasta um pouco da broca da mão. <b>C</b> é compacta, com o bit mais
longo e a espiral mais marcada. <b>Recomendo A</b>: é a que mais lembra a broca na mão do player e continua legível em 16 px.</p>

<h2>Na hotbar, com os outros ícones</h2>
<div class="row">{hot}</div>
<p>Slots do <code>ui_slot.png</code> (20×20), ícones 16×16 com 2 px de margem, ampliado 4×. O slot 1 está selecionado.</p>

<h2>Contêiner aberto · 2 candidatas</h2>
<div class="row">{conts}</div>
<p><b>A</b>: tampa toda em pé. <b>B</b> (aprovada): tampa meio aberta, com cara de "forçada".</p>

<h2>No chão do jogo</h2>
<div class="row"><figure><img class="px" src="cena_conteiner.png" width="864" height="288" alt=""><figcaption>chão do estágio Morto · fechado, A, B · pé no centro de baixo do tile (mesmo pivô do fechado), 3×</figcaption></figure>
<figure><div class="chk"><div class="a-c"></div></div><figcaption>fechado → aberto A (o que o E faz)</figcaption></figure></div>

<h2>Pro Dev integrar</h2>
<ul>
<li><code>icon_hand_drill.png</code>: 16×16, mesmo uso dos outros <code>icon_*</code> (hotbar e inventário). Item <code>hand_drill</code>.</li>
<li><code>container_open.png</code>: 40×44, <b>mesma âncora do <code>container_sealed.png</code></b> (pé no centro de baixo do
tile, a mesma conta de offset); só troca a textura do tile <code>C.CONTAINER</code> quando o contêiner já foi aberto.
A silhueta ocupa a mesma caixa; a tampa em pé sobe até a linha 1 do quadro (a do fechado sobe até a linha ~8).</li>
<li>Alpha só 0/255, sem sombra no PNG.</li></ul>
<h2>Gerado por</h2><p><code>python3 tools/sprites/v05_m4_broca_conteiner.py</code> (determinístico).</p>
</div></body></html>"""
    (REP / "index.html").write_text(html)
    return REP / "index.html"
