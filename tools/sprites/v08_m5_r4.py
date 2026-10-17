#!/usr/bin/env python3
"""v0.8 M5 · rodada 4 · BOTAS (icon_boots, 4 candidatas) e MOCHILA nv.1 (icon_backpack, 3 candidatas), 16×16.
Nada vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v08_m5_r4.py

Por que à mão (grade de caracteres) e não no r3d: em 16 px o r3d decide a silhueta sozinho, e a silhueta é justamente
o que o dono reprovou ("parece um L"). Aqui cada pixel é escolhido, mas com as MESMAS paletas de 5 tons do r3d
(v08_m5_r2: branco do traje, laranja, fibra, resina, cinza, escuro), a mesma luz (de cima e da esquerda) e o contorno
#1b1630, pra ficar na família do tanque, do scanner e da Mochila T2 aprovados. A candidata C da mochila sai da própria
icon_backpack_t2.png aprovada, recolorida (troca de cor por região, nenhum pixel inventado).
Saída em reports/design/v08_m5_itens_r4/. Só LÊ assets/sprites/. Determinístico.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v08_m5_itens as I  # noqa: E402
import v08_m5_r2 as R2  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v08_m5_itens_r4"
CAND = REP / "candidatas"
PEND = REP / "pendentes"
ANTES = ROOT / "reports" / "design" / "before"
R3REP = ROOT / "reports" / "design" / "v08_m5_itens_r3"

# ---- legenda (tons tirados das paletas r3d do v08_m5_r2) ------------------------------------------------------------
LEG = {
    "K": "#1b1630",                                                            # contorno
    "1": "#f4f6f8", "2": "#e8ebef", "3": "#cfd4db", "4": "#a3aab6", "5": "#767d8b",   # branco do traje (P_WHITE)
    "m": "#c8cdd4", "w": "#b9bfc8", "n": "#abb2bb", "v": "#8c949e", "P": "#6b717a",   # cinza (P_GREYP)
    "D": "#5a5f6b", "X": "#3b3f46", "x": "#2a2d33",                            # escuro (P_DARK)
    "o": "#f4a06a", "O": "#e2733a", "q": "#a9482a", "Q": "#6e2a1c",            # laranja (P_ORANGE)
    "f": "#8fd65a", "F": "#4f9a3f", "g": "#2f6b3a",                            # fibra (P_FIBER)
    "r": "#a6ecff", "R": "#58a0e0", "b": "#2f68b0", "B": "#22407a",            # resina de geada (P_RESIN)
    "c": "#59d0e6", "C": "#2b9fb8",                                            # LED ciano (P_CYAN)
}


def draw(rows):
    assert len(rows) == 16, len(rows)
    a = np.zeros((16, 16, 4), np.uint8)
    for y, r in enumerate(rows):
        assert len(r) == 16, (y, r, len(r))
        for x, ch in enumerate(r):
            if ch != ".":
                h = LEG[ch].lstrip("#")
                a[y, x] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    return Image.fromarray(a)


# =====================================================================================================================
# BOTAS · uma bota só (o par em 16 px vira bloco). Receita: punho/tira de FIBRA (verde) + sola/fivela de RESINA (azul).
# =====================================================================================================================
BOOT_A = [   # 3/4 de lado, peito do pé em rampa
    "...KKKKKKKK.....",
    "..KfxxxxxxFK....",
    "..KffffffFgK....",
    "..K21122344K....",
    "..K21122344K....",
    "..KOoOOOOqqK....",
    "..K2112233ffK...",
    "..K2112233fF3K..",
    "..K211223rR3oOK.",
    "..K21122fF3oOOqK",
    ".K12112fF33OOOqK",
    ".K23332fF34qqqqK",
    "KrrrrrrrrrrRRRbK",
    "KRRRRRRRRRRbbbBK",
    "KbBKKbBKKbBKKbBK",
    ".KK..KK..KK..KK.",
]
BOOT_B = [   # no passo: sola inclinada, bico subindo
    ".KKKKKKKK.......",
    "KfxxxxxxFK......",
    "KffffffFgK......",
    "K21122344K......",
    "KOoOOOOqq4KKKK..",
    "K2112fF333ooOOK.",
    "K2112rR33oOOOOqK",
    "K211fF333oOOOqqK",
    "K211fF3333qqqrrK",
    "K21fF33334rrrRRK",
    "K2fF344rrrRRRBBK",
    "K334rrrRRRBBKKK.",
    "KrrrRRRBBKKK....",
    "KRRRBBKKK.......",
    "KBBKKK..........",
    ".KK.............",
]
BOOT_C = [   # chibi: bico redondão maior que o cano
    ".KKKKKKK........",
    "KfxxxxxFK.......",
    "KfffffFgK.......",
    "K2112344K.......",
    "KfFrRFggKKKKK...",
    "K2112344KooOOK..",
    "K211234ooOOOOqK.",
    "K21123ooOOOOOqqK",
    "K2112oOOOOOOOqqK",
    "K2112OOOOOOOqqqK",
    "K3223OOOOOOqqqQK",
    "K3334qOOOqqqqQQK",
    "KrrrrrrrrrrRRRbK",
    "KRRRRRRRRbbbbbBK",
    "KbBKKbBKKbBKKbBK",
    ".KK..KK..KK..KK.",
]
BOOT_D = [   # 3/4 de frente, bico vindo pra câmera (à esquerda)
    ".......KKKKKK...",
    "......KfxxxxFK..",
    "......KffffFgK..",
    "......K211234K..",
    "......K211234K..",
    "......KOoOOqqK..",
    "....KK2211234K..",
    "...K11fF22334K..",
    "..K1112rR2334K..",
    ".KoOo122fF3344K.",
    "KoOOOq233fF344K.",
    "KOOOqq33333444K.",
    "KrrrrrrrrrRRRbbK",
    ".KRRRRRRRbbbbBK.",
    "..KBBKBBKBBKBBK.",
    "...KK.KK.KK.KK..",
]
BOOTS = {"A": BOOT_A, "B": BOOT_B, "C": BOOT_C, "D": BOOT_D}
BOOT_CAP = {
    "A": "A · 3/4 de lado, peito do pé em rampa: cano cilíndrico (boca aberta, punho de fibra, faixa laranja), "
         "tira de fibra com fivela de resina, bico laranja redondo, sola de resina com 4 cravos",
    "B": "B · no passo: a sola de resina inclinada (calcanhar no chão, bico subindo), a tira de fibra na diagonal",
    "C": "C · chibi: bico laranja redondão, maior que o cano; a tira de fibra com fivela de resina sobe pro cano",
    "D": "D · 3/4 de frente: o bico vem pra câmera, à esquerda; a tira de fibra cruza o peito do pé",
}

# =====================================================================================================================
# MOCHILA nv.1 · família da Mochila T2 aprovada, sem dourado e sem fibra
# =====================================================================================================================
BAG_A = [    # o corpo da T2 + a leitura do 2D antigo (alça de mão, LED ciano, alças de ombro dos lados)
    "................",
    "......KKKK......",
    ".....KXDDXK.....",
    "..KKKXKKKKXKKK..",
    ".K111111111112K.",
    ".K11111cC11112K.",
    "KKoooooooooooqKK",
    "DKOOOOOXXOOOOqKD",
    "DX22222xX22233Xx",
    "DX322222222223Xx",
    "DX3mOOOOOOOOn3Xx",
    "DX3wwwwwwwwwn3Xx",
    "KX2wwwwwwwwwnPXK",
    ".KKvnnnnnnnnPKK.",
    "...KKKKKKKKKK...",
    "................",
]
BAG_B = [    # a silhueta do 2D antigo (alta, em domo) com o volume em faixas
    "......KKKK......",
    ".....KDDDXK.....",
    "....KXKKKKXK....",
    "....K111112K....",
    "...K11111123K...",
    "..K111cC11123K..",
    ".KD21111111233xK",
    ".KDoOOOOOOOOOqxK",
    ".KD21111111233xK",
    ".KD21111111233xK",
    ".KD3oOOOOOOOOqxK",
    ".KD3wwwwwwwwn3xK",
    ".KD3wwwwwwwwn4xK",
    ".KD4nnnnnnnnv4xK",
    "..KXvvvvvvvvvxK.",
    "...KKKKKKKKKKK..",
]


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def bag_C():
    """C · a T2 aprovada recolorida por região: rolo de cima branco, tiras e fivela escuras (no lugar do dourado), aba
    laranja, zíper laranja, bolsos dos lados cinza (no lugar da fibra). Mesmos pixels, outro nível."""
    a = np.array(Image.open(SPR / "icon_backpack_t2.png").convert("RGBA"))
    out = a.copy()
    gold = {"#ffe08f": "#5a5f6b", "#f2c46d": "#4a4f5a", "#b8893a": "#3b3f46", "#d9a64e": "#3b3f46"}
    orange = {"#8fd65a": "#f4a06a", "#7fc94f": "#e2733a", "#4f9a3f": "#a9482a", "#2f6b3a": "#6e2a1c",
              "#5fae45": "#e2733a"}
    grey = {"#8fd65a": "#cfd4db", "#7fc94f": "#b9bfc8", "#4f9a3f": "#8c949e", "#2f6b3a": "#6b717a",
            "#5fae45": "#cfd4db"}
    roll = {"#5fae45": "#e8ebef", "#8fd65a": "#f4f6f8", "#4f9a3f": "#a3aab6"}
    for y in range(16):
        for x in range(16):
            if not a[y, x, 3]:
                continue
            c = "#%02x%02x%02x" % tuple(a[y, x, :3])
            if y <= 3:
                m = {**roll, **gold}
            elif y >= 6 and (x <= 1 or x >= 14 or (x in (2, 13) and y >= 8)):
                m = grey
            elif y == 10 and 4 <= x <= 11 and c in gold:
                m = {c: "#e2733a" if c == "#ffe08f" else "#a9482a"}
            else:
                m = {**orange, **gold}
            if c in m:
                out[y, x, :3] = _hex(m[c])
    return Image.fromarray(out)


BAGS = {"A": lambda: draw(BAG_A), "B": lambda: draw(BAG_B), "C": bag_C}
BAG_CAP = {
    "A": "A · corpo da T2 + a leitura do 2D: alça de mão em arco, LED ciano, alças de ombro escuras dos lados, aba e "
         "zíper laranja, fivela escura",
    "B": "B · a silhueta do 2D antigo (alta, em domo) com volume: alça em arco, LED, 2 faixas laranja, alças de ombro",
    "C": "C · a própria T2 recolorida: rolo branco, tiras e fivela escuras, aba laranja, bolsos cinza",
}
REC_BOOT = "A"
REC_BAG = "A"


# =====================================================================================================================
# build + checagem
# =====================================================================================================================
def build():
    for d in (CAND, PEND, ANTES):  # ANTES = reports/design/before/ (as reprovadas, com prefixo v08m5_)
        d.mkdir(parents=True, exist_ok=True)
    for k, g in BOOTS.items():
        im = draw(g)
        im.save(CAND / f"icon_boots_{k}.png")
        if k == REC_BOOT:
            im.save(PEND / "icon_boots.png")
    for k, fn in BAGS.items():
        im = fn()
        im.save(CAND / f"icon_backpack_{k}.png")
        if k == REC_BAG:
            im.save(PEND / "icon_backpack.png")
    # as reprovadas, copiadas pra cá (o report não depende de arquivo que pode mudar)
    old = {"v08m5_boots_r1_2d.png": I.PEND / "icon_boots.png", "v08m5_boots_r2_3d.png": R2.PEND / "icon_boots.png",
           "v08m5_boots_r3_A.png": R3REP / "candidatas" / "icon_boots_A.png",
           "v08m5_boots_r3_B.png": R3REP / "candidatas" / "icon_boots_B.png",
           "v08m5_boots_r3_C.png": R3REP / "candidatas" / "icon_boots_C.png",
           "v08m5_backpack_r2_3d.png": R2.PEND / "icon_backpack.png"}
    for name, src in old.items():
        shutil.copyfile(src, ANTES / name)
    if not (ANTES / "v08m5_backpack_2d_antigo.png").exists():
        # o 2D antigo é o que está no assets/ hoje (commit f03bf358); guardado uma vez só
        shutil.copyfile(SPR / "icon_backpack.png", ANTES / "v08m5_backpack_2d_antigo.png")


def check():
    ok = True
    if {p.name for p in PEND.glob("*.png")} != {"icon_boots.png", "icon_backpack.png"}:
        print("pendentes/ fora do contrato:", sorted(p.name for p in PEND.glob("*.png")))
        ok = False
    for p in sorted(list(PEND.glob("*.png")) + list(CAND.glob("*.png"))):
        im = Image.open(p)
        al = set(np.unique(np.array(im.convert("RGBA"))[:, :, 3]).tolist())
        if im.size != (16, 16) or im.mode != "RGBA" or not al <= {0, 255}:
            print("problema:", p.name, im.size, im.mode, al)
            ok = False
    print("contrato ok (pendentes: icon_boots + icon_backpack, 16×16 RGBA, alpha 0/255)" if ok else "COM PROBLEMA")
    return ok


# =====================================================================================================================
# prévias
# =====================================================================================================================
def resolver(boot=REC_BOOT, bag=REC_BAG):
    def f(name):
        if name == "icon_boots":
            return Image.open(CAND / f"icon_boots_{boot}.png").convert("RGBA")
        if name == "icon_backpack":
            return Image.open(CAND / f"icon_backpack_{bag}.png").convert("RGBA")
        for d in (SPR, I.PEND, I.CAND, R2.PEND):
            p = d / f"{name}.png"
            if p.exists():
                return Image.open(p).convert("RGBA")
        raise FileNotFoundError(name)
    return f


def zoom_sheet(path, ims, k=4, pad=8):
    """Tira de ícones 1× e ×k lado a lado, no fundo do slot (pra ver a 16 px de verdade e ampliado)."""
    W = sum(16 + 4 + 16 * k + pad * 2 for _ in ims)
    out = Image.new("RGBA", (W, 16 * k + 2 * pad), _hex("#181c28") + (255,))
    x = pad
    for im in ims:
        out.alpha_composite(im, (x, pad + 16 * k - 16))
        out.alpha_composite(im.resize((16 * k, 16 * k), Image.NEAREST), (x + 20, pad))
        x += 20 + 16 * k + 2 * pad
    out.save(path)


def previews():
    import v08_m5_itens_report as RP
    import v08_plantas_report as PR
    bg = PR.scene_base("mist")
    orig = RP.icon
    eq1 = {"o2_tank": "o2_tank", "scanner": "scanner", "backpack": "backpack", "boots": "boots"}
    # slots na escala do jogo (Grande ×2): os aprovados + a candidata por último
    for k in BOOTS:
        RP.icon = resolver(boot=k)
        RP.slot_sheet(["icon_o2_tank", "icon_scanner", "icon_backpack", "icon_backpack_t2", "icon_o2_tank_t2",
                       "icon_boots"]).save(REP / f"slots_boots_{k}.png")
    for k in BAGS:
        RP.icon = resolver(bag=k)
        RP.slot_sheet(["icon_o2_tank", "icon_scanner", "icon_backpack", "icon_backpack_t2", "icon_o2_tank_t2",
                       "icon_boots"]).save(REP / f"slots_bag_{k}.png")
    # cartão TRAJE: as 4 botas com nv.1 e com nv.2
    for tag, eq in (("nv1", eq1), ("nv2", RP.EQ_T2)):
        m = PR.UIMock(bg)
        m.window(14, 36, 452, 162)
        for i, k in enumerate(BOOTS):
            RP.icon = resolver(boot=k)
            x = 24 + i * 110
            m.text(x + 48, 40, f"bota {k}", PR.GOLD_UI if k == REC_BOOT else PR.B_MUTED, "label", "center")
            RP.suit_card_col(m, x, 58, 96, 126, eq)
        m.finish(REP / f"traje_botas_{tag}.png")
    # cartão TRAJE: as 3 mochilas nv.1 + o nv.2 aprovado do lado
    m = PR.UIMock(bg)
    m.window(14, 36, 452, 162)
    for i, k in enumerate(BAGS):
        RP.icon = resolver(bag=k)
        x = 24 + i * 110
        m.text(x + 48, 40, f"mochila {k} · nv.1", PR.GOLD_UI if k == REC_BAG else PR.B_MUTED, "label", "center")
        RP.suit_card_col(m, x, 58, 96, 126, eq1)
    RP.icon = resolver()
    m.text(24 + 3 * 110 + 48, 40, "nv.2 (aprovado)", PR.B_MUTED, "label", "center")
    RP.suit_card_col(m, 24 + 3 * 110, 58, 96, 126, RP.EQ_T2)
    m.finish(REP / "traje_mochilas.png")
    # Tab A inteiro com as recomendadas (o Tab A aprovado mostra o traje nv.2; o nv.1 aparece no cartão acima)
    RP.icon = resolver()
    RP.tab_A(bg, REP / "tab_A_recomendadas.png")
    RP.icon = orig
    # tiras de zoom
    zoom_sheet(REP / "zoom_botas.png", [draw(g) for g in BOOTS.values()])
    zoom_sheet(REP / "zoom_mochilas.png", [fn() for fn in BAGS.values()] +
               [Image.open(SPR / "icon_backpack_t2.png").convert("RGBA")])


# =====================================================================================================================
# report
# =====================================================================================================================
CSS = R2.CSS + """
.big{image-rendering:pixelated}
.cmp{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-end}
@keyframes pulse{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}
.pick .chk img:last-child{animation:pulse 1.6s steps(2) infinite}
"""


def _u(p):
    p = Path(p)
    return p.relative_to(REP).as_posix() if str(p).startswith(str(REP)) else "../before/" + p.name


def fig(path, cap, k=4, pick=False):
    u = _u(path)
    return (f'<figure{" class=pick" if pick else ""}><div class="chk"><img class="px" src="{u}" width="16" height="16">'
            f'<img class="px" src="{u}" width="{16 * k}" height="{16 * k}"></div><figcaption>{cap}</figcaption></figure>')


def write_html(ok):
    o = []
    a = o.append
    a(f'<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>v0.8 M5 · rodada 4 · botas e mochila nv.1</title>'
      f'<style>{CSS}</style></head><body><div class="wrap">')
    a('<div class="eyebrow">Hesper · Designer · v0.8 M5 · rodada 4 · candidatas</div>')
    a('<h1>Rodada 4 · botas e mochila nv.1</h1>')
    a('<div class="note"><b>v1.3 · o que mudou:</b> só dois ícones de 16×16, <code>icon_boots</code> (4 candidatas) e '
      '<code>icon_backpack</code> nv.1 (3 candidatas). Desta vez <b>desenhados pixel a pixel</b>, não no r3d: em 16 px o r3d '
      'escolhia a silhueta sozinho, e a silhueta era o problema. As paletas são as mesmas de 5 tons dos equipáveis 3D aprovados '
      '(branco do traje, laranja <code>#e2733a</code>, fibra, resina, cinza, escuro), com a mesma luz (de cima e da esquerda) e o mesmo contorno <code>#1b1630</code>. '
      'A mochila C sai da própria <code>icon_backpack_t2.png</code> aprovada, só recolorida. Nada foi pro jogo. '
      f'Tamanhos: <b>{"todos 16×16, alpha 0/255, pendentes só com os 2 nomes do contrato" if ok else "COM PROBLEMA"}</b>. '
      'Anteriores: <a href="../v08_m5_itens_r3/index.html" style="color:#59d0e6">rodada 3</a> · '
      '<a href="../v08_m5_itens_r2/index.html" style="color:#59d0e6">rodada 2</a> · '
      '<a href="../v08_m5_itens/index.html" style="color:#59d0e6">rodada 1</a>.</div>')

    # ---- botas
    a('<h2>1 · Botas (4 candidatas)</h2>')
    a('<p>Pra fugir do "L", nenhuma tem mais o ângulo reto entre o cano e o pé. Em todas: o <b>cano é um cilindro</b> com a '
      'boca aberta em cima (o anel do punho de <b>fibra</b> verde em volta do escuro) e faixas de luz e sombra; o <b>bico é '
      'redondo e grande</b>; a <b>sola de resina</b> azul-gelo é grossa e tem <b>cravos</b> embaixo; e uma <b>tira de fibra com '
      'fivela de resina</b> passa no peito do pé. A receita (fibra + resina) fica visível nas duas cores.</p><div class="row">')
    for k in BOOTS:
        a(fig(CAND / f"icon_boots_{k}.png", BOOT_CAP[k], pick=k == REC_BOOT))
    a('</div><p>Lado a lado a 1× e ×4 no fundo do slot:</p><img class="px" src="zoom_botas.png">')
    a('<h3>As reprovadas, pra comparar</h3><div class="row">')
    a(fig(ANTES / "v08m5_boots_r1_2d.png", "rodada 1 · 2D, par"))
    a(fig(ANTES / "v08m5_boots_r2_3d.png", "rodada 2 · 3D, par (virou bloco)"))
    for k in "ABC":
        a(fig(ANTES / f"v08m5_boots_r3_{k}.png", f"rodada 3 · {k}" + (" (o 'L')" if k == "A" else "")))
    a('</div>')
    a('<h3>No slot, na escala do jogo (Grande ×2)</h3><p>Tanque, scanner, mochila nv.1 (A), Mochila T2, tanque nv.2 e a bota da candidata, por último.</p>')
    for k in BOOTS:
        a(f'<p style="margin:10px 0 2px"><b>{k}</b></p><img class="px" src="slots_boots_{k}.png">')
    a('<h3>No cartão TRAJE do Tab A: com nv.1 e com nv.2</h3>')
    a('<img class="full" src="traje_botas_nv1.png" width="960" height="540"><img class="full" src="traje_botas_nv2.png" width="960" height="540">')
    a('<div class="note rec"><b>Recomendo A.</b> A 16 px é a única que lê "bota" de primeira sem precisar de contexto: o cano '
      'cilíndrico com a boca aberta, a rampa do peito do pé descendo até o bico e a sola com os cravos. A rampa preenche o canto, '
      'então o "L" some. Os pontos fracos: a <b>tira verde</b> em diagonal some um pouco a 1× (vira um risco) e o desenho ainda '
      'é de lado. Se o dono achar a A "parada" demais, a <b>B</b> é a que mais foge do L: com a sola inclinada, a silhueta '
      'vira um paralelogramo. Só que a 1× ela lembra um tênis ou um patins. A <b>C</b> é a mais simpática e a mais "astronauta de desenho", mas o '
      'bico laranja vira uma bola maior que o resto e briga com o laranja do tanque no slot. A <b>D</b> (3/4 de frente) tem '
      'volume, mas a 16 px é a que demora mais pra ler: o bico vira uma mancha laranja à esquerda.</div>')

    # ---- mochila
    a('<h2>2 · Mochila nv.1 (3 candidatas)</h2>')
    a('<p>Todas são da família da Mochila T2 aprovada (corpo branco em domo, aba e bolso cinza embaixo), sem o dourado e sem a fibra, '
      'e com a leitura do 2D antigo: o <b>LED ciano</b>, as <b>alças de ombro</b> escuras e a alça de mão.</p><div class="row">')
    for k in BAGS:
        a(fig(CAND / f"icon_backpack_{k}.png", BAG_CAP[k], pick=k == REC_BAG))
    a('</div><p>1× e ×4 no fundo do slot (a última é a T2 aprovada):</p><img class="px" src="zoom_mochilas.png">')
    a('<h3>As anteriores, pra comparar</h3><div class="row">')
    a(fig(ANTES / "v08m5_backpack_2d_antigo.png", "2D antigo (o de hoje no jogo): LED e alças liam bem"))
    a(fig(ANTES / "v08m5_backpack_r2_3d.png", "rodada 2 · 3D (reprovado: aba laranja enorme, sem LED, sem alças)"))
    a('</div>')
    a('<h3>No slot, na escala do jogo (Grande ×2)</h3><p>Tanque, scanner, a mochila da candidata (3º), Mochila T2, tanque nv.2 e a bota A.</p>')
    for k in BAGS:
        a(f'<p style="margin:10px 0 2px"><b>{k}</b></p><img class="px" src="slots_bag_{k}.png">')
    a('<h3>No cartão TRAJE: as 3 nv.1 e o nv.2 aprovado do lado</h3>')
    a('<img class="full" src="traje_mochilas.png" width="960" height="540">')
    a('<div class="note rec"><b>Recomendo A.</b> É a T2 "com menos coisa": o mesmo corpo, a mesma aba e o mesmo bolso, então a '
      'família é óbvia, e no lugar do rolo de fibra entra a alça de mão. Também traz o LED ciano e as alças de ombro escuras do 2D antigo. '
      'O nv.2 vira "esta + fibra + dourado". O defeito: de lado, as alças escuras deixam a silhueta com cara de caixa térmica '
      '(a 1× lê bem, no ×4 aparece). A <b>B</b> é a mais fiel ao 2D antigo, e quem gostava dele vai reconhecer, mas fica '
      'mais alta e estreita que a T2 e a família pesa menos. A <b>C</b> é a T2 recolorida: a família é perfeita, mas não é '
      '"mais simples", e as duas tiras escuras em cima viram umas orelhas.</div>')

    a('<h2>Tab A inteiro com as recomendadas</h2><p>O Tab A aprovado mostra o traje nv.2. A bota A aparece no slot BOTAS; a mochila nv.1 aparece nos cartões acima.</p>')
    a('<img class="full" src="tab_A_recomendadas.png" width="960" height="540">')

    a('<h2>Pro Dev integrar (depois do ok do dono)</h2><ul>')
    a('<li>Só troca de PNG, nenhum código muda. <code>v08_m5_itens_r4/pendentes/icon_boots.png</code> e <code>pendentes/icon_backpack.png</code> '
      'vão pra <code>assets/sprites/</code> com o mesmo nome: 16×16 RGBA, ícone de item como os outros (sem âncora: desenhado no slot com 2 px de margem, ×2 no Grande).</li>')
    a('<li>Se o dono escolher outra: <code>candidatas/icon_boots_{A..D}.png</code> ou <code>candidatas/icon_backpack_{A..C}.png</code>, renomeado sem a letra.</li>')
    a('<li>O fantasma do slot vazio no TRAJE continua sendo o ícone nv.1 a alpha 45 (BOTAS e MOCHILA).</li>')
    a('<li>Gerar de novo: <code>python3 tools/sprites/v08_m5_r4.py</code>. É determinístico, só lê <code>assets/</code> e não mexe no <code>build_sprites.py</code>.</li>')
    a('</ul></div></body></html>')
    (REP / "index.html").write_text("\n".join(o), encoding="utf-8")


def md5s():
    return {p.relative_to(REP).as_posix(): hashlib.md5(p.read_bytes()).hexdigest()
            for p in sorted(list(CAND.glob("*.png")) + list(PEND.glob("*.png")))}


if __name__ == "__main__":
    build()
    ok = check()
    previews()
    write_html(ok)
    for k, v in md5s().items():
        print(v, k)
