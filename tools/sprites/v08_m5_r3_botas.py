#!/usr/bin/env python3
"""v0.8 M5 · rodada 3 · só as BOTAS (icon_boots, 16×16), 3 candidatas. Nada vai pro assets/ sem o ok do dono.

    python3 tools/sprites/v08_m5_r3_botas.py

Uma bota só (o par em 16 px vira bloco), na mesma cena/luz dos equipáveis 3D aprovados (r3d.py, v08_m5_r2.py):
  A · perfil, cano alto: bota de traje de lado, cano alto com punho de fibra e faixa laranja, sola de resina com cravos.
  B · perfil, sola de garras: cano mais baixo, sola grossa de resina com garras exageradas pra baixo (tração).
  C · 3/4, pé à frente: a bota virada pro jogador, biqueira grande na frente e a sola com cravos aparecendo.
Saída em reports/design/v08_m5_itens_r3/. Só LÊ assets/sprites/. Determinístico.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v08_m5_itens as I  # noqa: E402
import v08_m5_r2 as R2  # noqa: E402
from r3d import Pal  # noqa: E402

ROOT = HERE.parents[1]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v08_m5_itens_r3"
CAND = REP / "candidatas"
PEND = REP / "pendentes"

P_WHITE, P_ORANGE, P_FIBER, P_RESIN, P_GREYP, P_DARK = (R2.P_WHITE, R2.P_ORANGE, R2.P_FIBER, R2.P_RESIN, R2.P_GREYP,
                                                        R2.P_DARK)
P_CREAM = Pal(["#fdf8ec", "#efe6d4", "#d6c9b4", "#a99a8c", "#6f6070"])          # creme do traje (BEIGE das máquinas)
P_CLEAT = Pal(["#58a0e0", "#2f68b0", "#22407a", "#101c40", "#0b1430"])          # cravos: resina 1 tom abaixo


def shaft_paint(band_lo, band_hi, cuff):
    """Cano: faixa laranja entre band_lo..band_hi (z local), punho de fibra acima de cuff e a boca do cano (face de
    cima) escura, pra ler como bota aberta e não como bloco."""
    def f(L, N):
        top = (N[:, 2] > 0.8) if np.ndim(N) == 2 else np.zeros(len(L), bool)
        out = np.where((L[:, 2] > band_lo) & (L[:, 2] < band_hi), 1, np.where(L[:, 2] > cuff, 2, 0))
        return np.where(top, 3, out)
    return f


def boot_A():
    """Perfil, cano alto: cano creme alto e estreito com a boca escura, punho de fibra verde e faixa laranja, pé curto
    arredondado com a biqueira laranja, sola grossa de resina azul e 3 cravos aparecendo embaixo."""
    sc = R2.scene(-1.3)
    sc.gy -= 0.9
    sc.rbox((-2.4, 0, 7.1), (2.3, 1.2, 5.3), 1.0, P_CREAM, paint=shaft_paint(-0.4, 0.9, 3.6),
            extra=(P_ORANGE, P_FIBER, P_DARK))                                            # cano alto
    sc.rbox((1.2, 0, 2.6), (4.4, 1.2, 1.6), 1.1, P_CREAM)                                 # pé
    sc.rbox((4.6, 0, 2.5), (1.2, 1.15, 1.4), 0.7, P_ORANGE)                               # biqueira
    sc.box((-4.9, 6.0), (-1.3, 1.3), (0.2, 1.3), P_RESIN)                                 # sola
    for X in (-3.8, 0.6, 4.9):
        sc.box((X - 1.0, X + 1.0), (-1.2, 1.2), (-2.0, 0.3), P_CLEAT)                     # cravos
    return R2.img(sc.render())


def boot_B():
    """Perfil, sola de garras exagerada: cano médio creme com punho de fibra, faixa laranja, e uma sola enorme de
    resina com 3 garras em dente de serra pra baixo (a tração é a cara do item)."""
    sc = R2.scene(-1.8)
    sc.gy = 16 - 5.0                                                                      # sobe a cena: espaço das garras
    sc.rbox((-2.4, 0, 7.0), (2.5, 1.7, 4.2), 1.0, P_CREAM, paint=shaft_paint(0.4, 1.6, 2.8),
            extra=(P_ORANGE, P_FIBER, P_DARK))
    sc.rbox((0.8, 0, 3.4), (5.0, 1.7, 1.5), 1.2, P_CREAM)                                 # pé
    sc.rbox((4.8, 0, 3.3), (1.1, 1.65, 1.2), 0.7, P_ORANGE)                               # biqueira
    sc.rbox((0.4, 0, 1.2), (6.2, 1.9, 1.1), 0.6, P_RESIN)                                 # sola grossa
    for X in (-4.0, 0.4, 4.8):                                                           # garras em dente
        sc.box((X - 1.5, X + 1.5), (-1.7, 1.7), (-1.0, 0.2), P_CLEAT)
        sc.box((X - 0.9, X + 0.9), (-1.6, 1.6), (-2.2, -1.0), P_CLEAT)
        sc.box((X - 0.35, X + 0.35), (-1.5, 1.5), (-3.2, -2.2), P_CLEAT)
    return R2.img(sc.render())


def boot_C():
    """3/4 com o pé à frente: a bota girada ~40° (biqueira apontando pra frente e pra direita), o cano atrás, a
    biqueira laranja grande na frente e a sola de resina com cravos marcando a borda de baixo."""
    import math
    sc = R2.scene(-4.5)
    ang = math.radians(-40)
    ca, sa = math.cos(ang), math.sin(ang)

    def at(x, y):
        return (x * ca - y * sa, x * sa + y * ca)

    def part(x, y, z, half, pal, **kw):
        X, Y = at(x, y)
        sc.obox((X, Y, z), half, pal, rot_z=ang, **kw)
    part(-2.6, 0, 5.9, (2.3, 1.6, 3.7), P_CREAM,
         paint=lambda L, F: np.where(L[:, 2] > 3.6, 3, np.where((L[:, 2] > -0.3) & (L[:, 2] < 1.1), 1,
                                                                 np.where(L[:, 2] > 2.4, 2, 0))),
         extra=(P_ORANGE, P_FIBER, P_DARK))                                                       # cano
    part(0.8, 0, 2.4, (4.6, 1.8, 1.6), P_CREAM)                                           # pé
    part(4.4, 0, 2.3, (1.2, 1.75, 1.4), P_ORANGE)                                         # biqueira
    part(0.4, 0, 0.6, (5.6, 2.0, 0.6), P_RESIN)                                           # sola
    for x in (-3.8, -1.0, 1.8, 4.6):
        part(x, 0, -0.4, (0.7, 1.9, 0.5), P_CLEAT)                                        # cravos
    return R2.img(sc.render())


CANDS = {"A": boot_A, "B": boot_B, "C": boot_C}
RECOMMEND = "A"


def build():
    CAND.mkdir(parents=True, exist_ok=True)
    PEND.mkdir(parents=True, exist_ok=True)
    for k, fn in CANDS.items():
        im = fn()
        assert im.size == (16, 16), (k, im.size)
        assert set(np.unique(np.array(im)[:, :, 3]).tolist()) <= {0, 255}, k
        im.save(CAND / f"icon_boots_{k}.png")
        if k == RECOMMEND:
            im.save(PEND / "icon_boots.png")
    print("contrato ok (3 candidatas 16×16 + pendentes/icon_boots.png)")


# ---- prévias + report ----------------------------------------------------------------------------------------------
def _icon_for(boot):
    def f(name):
        if name == "icon_boots":
            return Image.open(CAND / f"icon_boots_{boot}.png").convert("RGBA")
        for d in (R2.PEND, I.PEND, I.CAND, SPR):
            p = d / f"{name}.png"
            if p.exists():
                return Image.open(p).convert("RGBA")
        raise FileNotFoundError(name)
    return f


def previews():
    import v08_m5_itens_report as RP
    import v08_plantas_report as PR
    bg = PR.scene_base("mist")
    RP.icon = _icon_for("A")
    RP.slot_sheet(["icon_o2_tank", "icon_backpack", "icon_scanner", "icon_o2_tank_t2", "icon_backpack_t2"]).save(
        REP / "slots_vizinhos.png")
    for k in CANDS:
        RP.icon = _icon_for(k)
        RP.slot_sheet(["icon_o2_tank", "icon_backpack", "icon_scanner", "icon_boots"]).save(REP / f"slots_{k}.png")
    m = PR.UIMock(bg)
    m.window(70, 40, 340, 156)
    eq1 = {"o2_tank": "o2_tank", "scanner": "scanner", "backpack": "backpack", "boots": "boots"}
    for i, k in enumerate(CANDS):
        RP.icon = _icon_for(k)
        x = 80 + i * 110
        m.text(x + 48, 44, k, PR.GOLD_UI if k == RECOMMEND else PR.B_MUTED, "label", "center")
        RP.suit_card_col(m, x, 62, 96, 126, eq1 if i != 2 else RP.EQ_T2)
    m.finish(REP / "traje_candidatas.png")
    RP.icon = _icon_for(RECOMMEND)
    RP.tab_A(bg, REP / "tab_A_botas_A.png")
    RP.icon = RP.__dict__.get("_orig_icon", RP.icon)


CSS = R2.CSS


def fig(path, cap, k=4, pick=False):
    w, h = Image.open(path).size
    p = Path(path)
    u = (p.relative_to(REP).as_posix() if str(p).startswith(str(REP)) else
         "../v08_m5_itens_r2/" + p.relative_to(R2.REP).as_posix() if str(p).startswith(str(R2.REP)) else
         "../v08_m5_itens/" + p.relative_to(I.REP).as_posix())
    return (f'<figure{" class=pick" if pick else ""}><div class="chk"><img class="px" src="{u}" width="{w}" height="{h}">'
            f'<img class="px" src="{u}" width="{w * k}" height="{h * k}"></div><figcaption>{cap}</figcaption></figure>')


def write_html():
    caps = {"A": "A · perfil, cano alto: cano estreito com a boca escura, punho de fibra, faixa laranja, pé curto com "
                 "biqueira laranja, sola de resina e 3 cravos",
            "B": "B · perfil, sola de garras: cano médio e uma sola grossa de resina com 3 garras em dente de serra",
            "C": "C · 3/4, pé à frente: a bota girada 40°, biqueira laranja apontando pra frente e a direita, cravos "
                 "embaixo"}
    o = []
    a = o.append
    a(f'<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8"><title>v0.8 M5 · rodada 3 · botas</title><style>{CSS}</style></head><body><div class="wrap">')
    a('<div class="eyebrow">Hesper · Designer · v0.8 M5 · rodada 3 · candidatas</div>')
    a('<h1>Rodada 3 · botas</h1>')
    a('<div class="note"><b>v1.2 · o que mudou:</b> só o <code>icon_boots</code> (16×16). O dono aprovou o resto da rodada 2 (slime A e os equipáveis 3D). '
      'Agora é <b>uma bota só</b>, porque em 16 px o par vira bloco. Mesma cena, mesma luz e contorno <code>#1b1630</code> dos equipáveis 3D aprovados, creme do traje com laranja, '
      'punho de <b>fibra</b> verde e sola de <b>resina</b> azul (a receita é fibra + resina), e cravos ou garras visíveis embaixo. '
      'São 3 candidatas bem diferentes. Nada foi pro jogo. Anteriores: <a href="../v08_m5_itens_r2/index.html" style="color:#59d0e6">rodada 2</a> · '
      '<a href="../v08_m5_itens/index.html" style="color:#59d0e6">rodada 1</a>.</div>')
    a('<h2>As 3 candidatas (×4, com o 1× do lado)</h2><div class="row">')
    for k in CANDS:
        a(fig(CAND / f"icon_boots_{k}.png", caps[k], pick=k == RECOMMEND))
    a('</div><p>Vizinhos 3D aprovados, pra comparar o peso:</p><div class="row">')
    for n in ("icon_o2_tank", "icon_backpack", "icon_scanner"):
        a(fig(R2.PEND / f"{n}.png", n))
    a('</div><p>As botas das rodadas que não serviram:</p><div class="row">')
    a(fig(I.PEND / "icon_boots.png", "rodada 1 (2D, par)"))
    a(fig(R2.PEND / "icon_boots.png", "rodada 2 (3D, par)"))
    a('</div>')
    a('<h2>No slot, na escala do jogo (Grande ×2)</h2><p>Tanque, mochila e scanner 3D e, por último, a bota de cada candidata.</p>')
    for k in CANDS:
        a(f'<p style="margin:10px 0 2px"><b>{k}</b></p><img class="px" src="slots_{k}.png">')
    a('<h2>No cartão TRAJE do Tab A</h2><p>A e B com os nv.1 3D; a C aparece com os nv.2, pra ver a bota ao lado do dourado também.</p>')
    a('<img class="full" src="traje_candidatas.png" width="960" height="540">')
    a('<h3>Tab A inteiro com a bota A</h3><img class="full" src="tab_A_botas_A.png" width="960" height="540">')
    a('<div class="note rec"><b>Recomendo A.</b> O cano alto e a sola com cravos dão a silhueta em "L" que lê "bota" de longe, e no slot ela tem o mesmo peso '
      'do tanque e da mochila. A <b>B</b> é a que mais diz "tração", mas a sola grande puxa o olho pra uma plataforma azul e o cano fica baixo. '
      'A <b>C</b> tem mais volume, mas a boca do cano vista de cima vira uma mancha cinza e a leitura demora.</div>')
    a('<h2>Pro Dev integrar (depois do ok do dono)</h2><ul>')
    a('<li>Só troca PNG: <code>v08_m5_itens_r3/pendentes/icon_boots.png</code> (A) vira <code>assets/sprites/icon_boots.png</code>, 16×16, ícone de item como os outros. '
      'Se o dono escolher B ou C: <code>candidatas/icon_boots_B.png</code> ou <code>_C.png</code>, renomeado.</li>')
    a('<li>O fantasma do slot BOTAS vazio é esse mesmo ícone, a alpha 45.</li>')
    a('<li>Gerar de novo: <code>python3 tools/sprites/v08_m5_r3_botas.py</code>. É determinístico e só lê <code>assets/</code>.</li>')
    a('</ul></div></body></html>')
    (REP / "index.html").write_text("\n".join(o), encoding="utf-8")


if __name__ == "__main__":
    build()
    previews()
    write_html()
