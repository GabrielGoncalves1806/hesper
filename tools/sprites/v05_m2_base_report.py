"""Report do v0.5 M2 · Base respirável (reports/design/v05_m2_base/index.html).
Chamado pelo tools/sprites/v05_m2_base.py depois de exportar os pendentes. Só LÊ assets/ (nunca escreve lá).

Os mocks são montados só com os sprites, na ordem do jogo (game/render.py):
  1. chão (terreno da região + base_floor nos tiles de chão);
  2. linha por linha, de cima pra baixo: primeiro as paredes/portas da linha (topo em y − 24, face em y + 8 se o de
     baixo não é parede), depois os objetos com o pé naquela linha, do mais alto pro mais baixo;
  3. raio-x: se o topo de uma parede da linha de baixo cobre o player, ele é redesenhado com alpha 95 por cima;
  4. por cima de tudo: o aviso de vazamento.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import v05_m2_base as G  # noqa: E402

ROOT = G.ROOT
OUT = G.REP
PEND = G.PEND
SPR = ROOT / "assets" / "sprites"
T = G.T
LIFT = G.LIFT


def load(p):
    return Image.open(p).convert("RGBA")


def crop(img, i, w):
    return img.crop((i * w, 0, i * w + w, img.height))


# ---- autotile A2 (a mesma regra do game/autotile.py) ----------------------------------------------------------------
OUTER, HEDGE, VEDGE, INNER, FULL = "outer", "hedge", "vedge", "inner", "full"
QUADS = ("TL", "TR", "BL", "BR")
CORNER = {"TL": (-1, -1), "TR": (1, -1), "BL": (-1, 1), "BR": (1, 1)}
SOURCE = {
    "TL": {OUTER: (0, 2), HEDGE: (2, 2), VEDGE: (0, 4), FULL: (2, 4), INNER: (2, 0)},
    "TR": {OUTER: (3, 2), HEDGE: (1, 2), VEDGE: (3, 4), FULL: (1, 4), INNER: (3, 0)},
    "BL": {OUTER: (0, 5), HEDGE: (2, 5), VEDGE: (0, 3), FULL: (2, 3), INNER: (2, 1)},
    "BR": {OUTER: (3, 5), HEDGE: (1, 5), VEDGE: (3, 3), FULL: (1, 3), INNER: (3, 1)},
}
ISOLATED = {"TL": (0, 0), "TR": (1, 0), "BL": (0, 1), "BR": (1, 1)}
OFFSET = {"TL": (0, 0), "TR": (16, 0), "BL": (0, 16), "BR": (16, 16)}


def piece(side, vertical, diagonal):
    if side and vertical:
        return FULL if diagonal else INNER
    if side:
        return HEDGE
    if vertical:
        return VEDGE
    return OUTER


def top_sources(conn, tx, ty):
    key = []
    for q in QUADS:
        dx, dy = CORNER[q]
        key.append(piece(conn(tx + dx, ty), conn(tx, ty + dy), conn(tx + dx, ty + dy)))
    if all(p == OUTER for p in key):
        return [(q, ISOLATED[q]) for q in QUADS]
    return [(q, SOURCE[q][p]) for q, p in zip(QUADS, key)]


class Sheet:
    def __init__(self):
        self.top = load(PEND / "base_wall_top.png")
        self.face = load(PEND / "base_wall_face.png")
        self.floor = [load(PEND / f"base_floor_{v}.png") for v in range(4)]
        oe = [f"{o}_{e}" for o, es in (("h", "ns"), ("v", "we")) for e in es]
        self.solo = {k: load(PEND / f"base_door_{k}.png") for k in oe}
        self.duo = {k: load(PEND / f"base_door2_{k}.png") for k in oe}
        self.door = {k: load(OUT / "anterior" / f"fina_base_door_{k}.png") for k in oe}
        self.door_old = {o: load(OUT / "anterior" / f"base_door_{o}.png") for o in ("h", "v")}
        self.leak = load(PEND / "leak_blink.png")
        self.disp_still = load(PEND / "machine_o2_dispenser.png")
        self.disp = load(PEND / "anim" / "anim_machine_o2_dispenser.png")
        self.disp_leak = load(PEND / "anim" / "anim_machine_o2_dispenser_leak.png")

    def wall_top(self, conn, tx, ty):
        im = Image.new("RGBA", (T, T))
        for q, (c, r) in top_sources(conn, tx, ty):
            im.alpha_composite(self.top.crop((c * 16, r * 16, c * 16 + 16, r * 16 + 16)), OFFSET[q])
        return im


FLOOR_PICK = (0, 0, 0, 0, 1, 1, 2, 3)        # metade lisa, 1/4 emendada, 1/8 grelha, 1/8 tampa


def floor_variant(tx, ty):
    return FLOOR_PICK[((tx * 73856093) ^ (ty * 19349663)) & 7]


def door_orient(conn, tx, ty):
    """'v' se encaixa numa parede vertical (N e S são parede/porta e L/O não); senão 'h'."""
    ns = conn(tx, ty - 1) and conn(tx, ty + 1)
    ew = conn(tx - 1, ty) or conn(tx + 1, ty)
    return "v" if ns and not ew else "h"


def ground(region, stage, w, h, seed):
    import regions_v9 as V9
    return V9.ground_patch(region, stage, w, h, seed)


def door_edge(at, tx, ty, orient, variant):
    """Borda da folha: A = a borda de DENTRO da base (o lado que dá pro chão da base), B = a de fora."""
    if orient == "h":
        inside = "n" if at(tx, ty - 1) == "." else "s"
        return inside if variant == "A" else {"n": "s", "s": "n"}[inside]
    inside = "w" if at(tx - 1, ty) == "." else "e"
    return inside if variant == "A" else {"w": "e", "e": "w"}[inside]


def compose(stage, plan, objs, ox, oy, size=(480, 270), region="plateau", seed=21, door_frame=0, leak=None,
            leak_on=True, xray=True, ground_img=None, variant="new"):
    """plan: lista de strings ('#' parede, 'D' porta, '.' chão, ' ' terreno). (ox, oy) = px do tile (0, 0).
    objs: [(sprite, foot_x, foot_y, is_player)] em px da tela."""
    S = Sheet()
    bg = ground_img.copy() if ground_img is not None else ground(region, stage, *size, seed)
    H = len(plan)
    W = max(len(r) for r in plan)

    def at(tx, ty):
        if 0 <= ty < H and 0 <= tx < len(plan[ty]):
            return plan[ty][tx]
        return " "

    new = variant in ("solo", "new")

    def conn(tx, ty):                     # v1.2: a porta não emenda no desenho da parede (a parede mostra a ponta)
        return at(tx, ty) == "#" if new else at(tx, ty) in "#D"

    def solid(tx, ty):
        return at(tx, ty) in "#DE"

    for ty in range(H):                                              # 1. chão
        for tx in range(W):
            if at(tx, ty) == ".":
                bg.alpha_composite(S.floor[floor_variant(tx, ty)], (ox + tx * T, oy + ty * T))
    player = None
    by_row = {}
    for o in objs:
        img, fx, fy, is_p = o
        row = (fy - oy - 1) // T
        by_row.setdefault(row, []).append(o)
        if is_p:
            player = o
    rows = sorted(set(range(-1, H + 1)) | set(by_row))
    for ty in rows:                                                  # 2. linha por linha
        for tx in range(W):
            ch = at(tx, ty)
            sx, sy = ox + tx * T, oy + ty * T
            if ch == "#":
                bg.alpha_composite(S.wall_top(conn, tx, ty), (sx, sy - LIFT))
                if not conn(tx, ty + 1):
                    idx = int(conn(tx - 1, ty)) + 2 * int(conn(tx + 1, ty))
                    bg.alpha_composite(crop(S.face, idx, T), (sx, sy + 8))
            elif ch == "D":
                o = door_orient(solid, tx, ty)
                if new:
                    sheet = S.solo[f"{o}_{door_edge(at, tx, ty, o, 'B')}"]
                elif variant == "old":
                    sheet = S.door_old[o]
                else:
                    sheet = S.door[f"{o}_{door_edge(at, tx, ty, o, variant)}"]
                bg.alpha_composite(crop(sheet, door_frame, T), (sx, sy - LIFT))
            elif ch == "E":                                          # porta dupla: metade 0 (esq./cima) ou 1
                if at(tx + 1, ty) == "E" or at(tx - 1, ty) == "E":
                    o, half = "h", (0 if at(tx + 1, ty) == "E" else 1)
                else:
                    o, half = "v", (0 if at(tx, ty + 1) == "E" else 1)
                sheet = S.duo[f"{o}_{door_edge(at, tx, ty, o, 'B')}"]
                bg.alpha_composite(crop(sheet, half * 4 + door_frame, T), (sx, sy - LIFT))
        for img, fx, fy, _ in sorted(by_row.get(ty, []), key=lambda o: o[2]):
            bg.alpha_composite(img, (fx - img.width // 2, fy - img.height))
    if xray and player is not None:                                  # 3. raio-x (igual ao player_occluded)
        img, fx, fy, _ = player
        wx, wy = fx - ox, fy - oy
        row_below = (wy - 1) // T + 1
        cols = {(wx - 10) // T, (wx + 9) // T}
        if any(at(c, row_below) == "#" or (at(c, row_below) in "DE" and door_frame < 2) for c in cols):
            ghost = img.copy()
            a = ghost.getchannel("A").point(lambda v: 95 if v else 0)
            ghost.putalpha(a)
            bg.alpha_composite(ghost, (fx - img.width // 2, fy - img.height))
    if leak is not None:                                             # 4. aviso de vazamento por cima de tudo
        lx, ly = leak
        bg.alpha_composite(crop(S.leak, 0 if leak_on else 1, T), (ox + lx * T, oy + ly * T - LIFT))
    return bg


# ---- cenas ----------------------------------------------------------------------------------------------------------
BASE = [
    "#######",
    "#.....#",
    "#.....D",
    "#.....#",
    "#.....#",
    "###D###",
]


SHOWCASE = [
    " #   ###  #.# ",
    "     #.#  ### ",
    " ##  ###  #.# ",
    "              ",
    " ### #####  # ",
    " #     #   ###",
    " #     #    # ",
]


def player_img(view="down", f=0):
    return load(SPR / f"player_idle_{view}.png").crop((f * 32, 0, f * 32 + 32, 32))


def base_scene(stage, f=0, door=0, region="plateau", seed=21, player=None, leak=None, leak_on=True, plan=None,
               disp="on", xray=True, variant="new"):
    S = Sheet()
    ox, oy = 112, 48
    plan = plan or BASE
    dimg = {"on": crop(S.disp, f % 4, G.DW), "leak": crop(S.disp_leak, f % 4, G.DW), "off": S.disp_still}[disp]
    objs = [
        (dimg, ox + 3 * T + 16, oy + 3 * T, False),                                  # dispersor no meio (3, 2)
        (load(SPR / "machine_workbench.png"), ox + 1 * T + 16, oy + 2 * T, False),   # bancada T2 (1, 1)
        (load(SPR / "chest.png"), ox + 5 * T + 16, oy + 2 * T, False),               # baú (5, 1)
        (load(SPR / "machine_o2.png"), ox + 5 * T + 16, oy + 5 * T, False),          # O₂ nv.1 (5, 4)
        (load(SPR / "lamp.png"), ox + 1 * T + 16, oy + 4 * T, False),                # luminária (1, 3)
        (load(SPR / "solar_panel.png"), ox + 9 * T + 16, oy + 3 * T, False),         # painel fora da base
    ]
    if player is not None:
        img, px, py = player
        objs.append((img, ox + px, oy + py, True))
    return compose(stage, plan, objs, ox, oy, region=region, seed=seed, door_frame=door, leak=leak,
                   leak_on=leak_on, xray=xray, variant=variant)


def build_mocks():
    out = {}
    for st in ("arid", "mist", "green"):
        out[f"cena_base_{st}.png"] = base_scene(st, f=0, player=(player_img("down"), 3 * T + 16, 5 * T + 26))
    # raio-x: player atrás da parede de baixo (dentro da base, encostado nela) e a mesma cena sem o raio-x
    pl = (player_img("down"), 2 * T + 14, 4 * T + 30)
    out["cena_raiox_arid.png"] = base_scene("arid", player=pl)
    out["cena_raiox_sem_arid.png"] = base_scene("arid", player=pl, xray=False)
    pl2 = (player_img("side"), 5 * T + 12, 0 * T - 2)                    # atrás da parede de cima (lado de fora)
    out["cena_raiox_fundo_green.png"] = base_scene("green", player=pl2)
    # portas abrindo (4 quadros), player chegando de baixo
    # v1.2: mock 1 = solo na parede de baixo + dupla na da direita; mock 2 = dupla embaixo + solo na direita
    P1 = ["#######", "#.....#", "#.....E", "#.....E", "#.....#", "###D###"]
    P2 = ["#######", "#.....#", "#.....#", "#.....D", "#.....#", "##EE###"]
    for name, plan in (("m1", P1), ("m2", P2)):
        for k in range(4):
            out[f"cena_porta_{name}_{k}.png"] = base_scene("arid", door=k, variant="new", plan=plan,
                                                           player=(player_img("up"), 5 * T + 2, 6 * T + 30))
        for st in ("mist", "green"):
            for k in (0, 3):
                out[f"cena_porta_{name}_{st}_{k}.png"] = base_scene(st, door=k, variant="new", plan=plan)
    for v in ("A", "B"):                                                # v1.1 fina (reprovada), pra comparar
        for k in (0, 3):
            out[f"anterior/cena_porta_fina_{v}_{k}.png"] = base_scene("arid", door=k, variant=v)
    for k in range(4):                                                  # v1.0 (reprovada), pra comparar
        out[f"anterior/cena_porta_{k}.png"] = base_scene("arid", door=k, variant="old",
                                                          player=(player_img("up"), 3 * T + 16, 6 * T + 28))
    # vazamento: tira um tile da parede da direita
    plan = [r for r in BASE]
    plan[4] = plan[4][:6] + " "
    out["cena_vazamento_on.png"] = base_scene("mist", plan=plan, leak=(6, 4), leak_on=True, disp="leak", f=0)
    out["cena_vazamento_off.png"] = base_scene("mist", plan=plan, leak=(6, 4), leak_on=False, disp="leak", f=1)
    for st in ("arid", "mist", "green"):
        out[f"cena_autotile_{st}.png"] = compose(st, SHOWCASE, [], 16, 36, seed=33)
    for k, im in out.items():
        im.save(OUT / k)
    return out


def all_combos():
    """As 47 combinações reais do autotile (chave = as 4 peças TL, TR, BL, BR), cada uma com um arranjo 3×3 que
    gera ela. Ordenadas pela quantidade de vizinhos."""
    seen = {}
    for bits in range(256):
        nb = [(bits >> i) & 1 for i in range(8)]
        cells = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
        m = {c: nb[i] for i, c in enumerate(cells)}
        m[(0, 0)] = 1

        def conn(x, y, m=m):
            return bool(m.get((x, y), 0))
        key = tuple(piece(conn(dx, 0), conn(0, dy), conn(dx, dy)) for dx, dy in CORNER.values())
        card = sum(m[c] for c in ((0, -1), (1, 0), (0, 1), (-1, 0)))
        # arranjo mínimo: só os diagonais que importam (os que têm os 2 cardinais vizinhos)
        mm = dict(m)
        for (dx, dy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            if not (m[(dx, 0)] and m[(0, dy)]):
                mm[(dx, dy)] = 0
        if key not in seen:
            seen[key] = (card, sum(mm.values()), mm)
    out = sorted(seen.items(), key=lambda kv: (kv[1][0], kv[1][1], str(kv[0])))
    return [(k, v[2]) for k, v in out]


def autotile_table():
    """Imagem com as 47 combinações: cada célula é o arranjo 3×3 desenhado com os sprites (vizinhos escurecidos), o
    tile do meio aceso. Embaixo, o código de 4 letras das peças (TL TR BL BR: o=externo, h=borda horiz., v=borda
    vert., i=canto interno, f=miolo)."""
    from PIL import ImageDraw
    S = Sheet()
    combos = all_combos()
    cw, chh, lab = 96 + 8, 96 + LIFT + 8, 12
    cols = 8
    rows_n = -(-len(combos) // cols)
    im = Image.new("RGBA", (cols * cw + 8, rows_n * (chh + lab) + 8), (31, 27, 36, 255))
    d = ImageDraw.Draw(im)
    letter = {OUTER: "o", HEDGE: "h", VEDGE: "v", INNER: "i", FULL: "f"}
    for n, (key, mm) in enumerate(combos):
        cx, cy = 8 + (n % cols) * cw, 8 + (n // cols) * (chh + lab)
        cell = Image.new("RGBA", (96, 96 + LIFT), (58, 50, 46, 255))
        plan = [[" "] * 3 for _ in range(3)]
        for (dx, dy), v in mm.items():
            if v:
                plan[dy + 1][dx + 1] = "#"
        plan = ["".join(r) for r in plan]

        def at(tx, ty):
            return plan[ty][tx] if 0 <= ty < 3 and 0 <= tx < 3 else " "

        def conn(tx, ty):
            return at(tx, ty) == "#"
        for ty in range(3):
            for tx in range(3):
                if at(tx, ty) == "#":
                    top = S.wall_top(conn, tx, ty)
                    face = None
                    if not conn(tx, ty + 1):
                        face = crop(S.face, int(conn(tx - 1, ty)) + 2 * int(conn(tx + 1, ty)), T)
                    if (tx, ty) != (1, 1):
                        top = Image.blend(Image.new("RGBA", top.size, (31, 27, 36, 255)), top, 0.45)
                        top.putalpha(255)
                        if face is not None:
                            f2 = Image.blend(Image.new("RGBA", face.size, (31, 27, 36, 255)), face, 0.45)
                            f2.putalpha(255)
                            face = f2
                    cell.alpha_composite(top, (tx * T, ty * T))
                    if face is not None:
                        cell.alpha_composite(face, (tx * T, ty * T + LIFT + 8))
        im.alpha_composite(cell, (cx, cy))
        hb = 32 + LIFT + 8 if mm.get((0, 1)) == 0 else 32 + 32
        d.rectangle([cx + 31, cy + 31, cx + 64, cy + hb], outline=(242, 196, 109, 255), width=1)
        d.text((cx, cy + 96 + LIFT + 1), f"{n:02d} " + "".join(letter[p] for p in key), fill=(239, 229, 218, 255))
    return im, len(combos)


def atlas_annotated(k=6):
    """O base_wall_top.png ampliado com a grade dos minitiles e o nome de cada bloco."""
    from PIL import ImageDraw
    a = load(PEND / "base_wall_top.png")
    big = a.resize((a.width * k, a.height * k), Image.NEAREST)
    im = Image.new("RGBA", big.size, (42, 47, 56, 255))
    im.alpha_composite(big)
    d = ImageDraw.Draw(im)
    for x in range(0, big.width + 1, 16 * k):
        d.line([(x, 0), (x, big.height)], fill=(89, 208, 230, 255), width=1)
    for y in range(0, big.height + 1, 16 * k):
        d.line([(0, y), (big.width, y)], fill=(89, 208, 230, 255), width=1)
    for x in (0, 32 * k):
        d.rectangle([x, 0, x + 32 * k - 1, 32 * k - 1], outline=(242, 196, 109, 255), width=2)
    d.rectangle([0, 32 * k, 64 * k - 1, 96 * k - 1], outline=(242, 196, 109, 255), width=2)
    return im


def height_compare():
    """Parede de rocha do jogo × parede da base, 1 bloco isolado cada, com o Explorador e o O₂ nv.1 pra escala."""
    S = Sheet()
    bg = ground("plateau", "arid", 224, 112, 5)
    y = 64
    bg.alpha_composite(load(SPR / "wall_dead_0.png"), (16, y - LIFT))
    bg.alpha_composite(load(SPR / "wall_face_dead.png"), (16, y + 8))
    objs = [(load(SPR / "player_down.png"), 80, y + 32), (load(SPR / "machine_o2.png"), 176, y + 32)]
    bg.alpha_composite(S.wall_top(lambda x, y_: (x, y_) == (0, 0), 0, 0), (112, y - LIFT))
    bg.alpha_composite(crop(S.face, 0, T), (112, y + 8))
    for img, fx, fy in objs:
        bg.alpha_composite(img, (fx - img.width // 2, fy - img.height))
    return bg


def size_of(p):
    with Image.open(p) as im:
        return im.size


def img(src, k, cls="chk", cap=""):
    w, h = size_of(OUT / src)
    c = f"<figcaption>{cap}</figcaption>" if cap else ""
    return f'<figure><div class="{cls}"><img src="{src}" width="{w * k}" height="{h * k}" alt=""></div>{c}</figure>'


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    build_mocks()
    tab, ncombo = autotile_table()
    tab.save(OUT / "autotile_47.png")
    atlas_annotated().save(OUT / "atlas_grade.png")
    height_compare().save(OUT / "altura_rocha_x_base.png")
    tw, th = size_of(OUT / "autotile_47.png")
    aw, ah = size_of(OUT / "atlas_grade.png")
    Z = 6
    DW, DH = G.DW, G.DH
    floors = "".join(img(f"pendentes/base_floor_{v}.png", Z, cap=f"<code>base_floor_{v}.png</code> · {c}") for v, c in
                     enumerate(["lisa (metade dos tiles)", "emendada (1/4)", "grelha de ventilação (1/8)",
                                "tampa de inspeção (1/8)"]))
    icons = "".join(f"""<figure><div class="row"><div class="chk"><img src="pendentes/{n}.png" width="128" height="128" alt=""></div><div class="lt"><img src="pendentes/{n}.png" width="128" height="128" alt=""></div><div class="one"><img src="pendentes/{n}.png" width="16" height="16" alt=""><img src="pendentes/{n}.png" width="32" height="32" alt=""></div></div><figcaption><code>{n}.png</code> · 16×16 · {c}</figcaption></figure>"""
                    for n, c in (("icon_base_floor", "chapa do chão"), ("icon_base_wall", "bloco de parede"),
                                 ("icon_base_door", "porta solo"), ("icon_base_door_double", "porta dupla"), ("icon_o2_dispenser", "Dispersor de O₂")))
    def _dsc(v):
        seq = [(0, 0), (18, 1), (26, 2), (34, 3), (74, 2), (82, 1), (90, 0)]
        return f"@keyframes dsc{v}{{" + "".join(f"{p}%{{background-image:url(cena_porta_{v}_{k}.png)}}" for p, k in seq) + "}"
    door_scene_css = _dsc("m1") + "\n" + _dsc("m2")
    door2_kf = ("0%{background-position:-768px 0}18%{background-position:-960px 0}26%{background-position:-1152px 0}"
                "34%{background-position:-1344px 0}74%{background-position:-1152px 0}82%{background-position:-960px 0}"
                "90%{background-position:-768px 0}")
    door_kf = ("0%{background-position:0 0}18%{background-position:-192px 0}26%{background-position:-384px 0}"
               "34%{background-position:-576px 0}74%{background-position:-384px 0}82%{background-position:-192px 0}"
               "90%{background-position:0 0}")
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hesper · v0.5 M2 · Base respirável · v1.2</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@400;600&family=Pixelify+Sans:wght@600&family=Silkscreen&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15100e;--panel:#1e1714;--line:#3a2c25;--fg:#efe5da;--muted:#a8968a;--rust:#e2733a;--cyan:#59d0e6;--gold:#f2c46d;--ok:#7fd67a;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "IBM Plex Sans",system-ui,sans-serif;padding:0 16px}}
.wrap{{max-width:1300px;margin:0 auto;padding:44px 0 80px}}
.eyebrow{{font:12px "Silkscreen",monospace;letter-spacing:.08em;color:var(--rust);text-transform:uppercase}}
h1{{font:600 44px/1.1 "Pixelify Sans",monospace;margin:8px 0 12px}}h2{{font:600 24px "Pixelify Sans",monospace;margin:44px 0 12px}}
h2::before{{content:"";display:inline-block;width:10px;height:10px;background:var(--rust);margin-right:10px;vertical-align:middle}}
h3{{font:600 16px "Pixelify Sans",monospace;margin:0 0 4px}}code{{font-family:"IBM Plex Mono",monospace;color:var(--gold);font-size:.92em}}
p,li,td{{color:var(--muted)}}li b,p b,td b{{color:var(--fg)}}
.v2{{background:#241b17;border:1px solid var(--line);border-left:3px solid var(--rust);padding:12px 18px;max-width:1100px}}
.v2>b{{font:13px "Silkscreen",monospace;color:var(--rust)}}
.chk{{display:inline-block;padding:10px;background-color:#2a2f38;background-image:linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%),linear-gradient(45deg,#333944 25%,transparent 25%,transparent 75%,#333944 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
.lt{{display:inline-block;padding:10px;background-color:#e8e2d6;background-image:linear-gradient(45deg,#d8d0c2 25%,transparent 25%,transparent 75%,#d8d0c2 75%),linear-gradient(45deg,#d8d0c2 25%,transparent 25%,transparent 75%,#d8d0c2 75%);background-size:16px 16px;background-position:0 0,8px 8px}}
img{{image-rendering:pixelated}}figure{{margin:0}}figcaption{{font:12px "Silkscreen",monospace;color:var(--muted);margin-top:6px;max-width:460px}}
.flex{{display:flex;gap:22px;align-items:flex-end;flex-wrap:wrap}}
.grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
@media(max-width:1000px){{.grid2,.grid3{{grid-template-columns:1fr}}}}
img.px{{width:100%;height:auto;border:1px solid var(--line);display:block}}
.box{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--cyan);padding:16px 20px}}
.ask{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);padding:16px 20px}}
.row{{display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
.one{{display:flex;gap:10px;align-items:center;background:#2a2f38;padding:10px}}
.sp{{background-repeat:no-repeat;image-rendering:pixelated;display:inline-block}}
.a-door{{width:192px;height:336px;background-size:768px 336px;animation:door 3s step-end infinite}}
.a-door2{{width:192px;height:336px;background-size:1536px 336px;animation:door2 3s step-end infinite}}
@keyframes door2{{{door2_kf}}}
@keyframes door{{{door_kf}}}
.a-disp{{width:{DW * Z}px;height:{DH * Z}px;background-image:url(pendentes/anim/anim_machine_o2_dispenser.png);background-size:{DW * 4 * Z}px {DH * Z}px;animation:disp .667s steps(4) infinite}}
.a-displ{{width:{DW * Z}px;height:{DH * Z}px;background-image:url(pendentes/anim/anim_machine_o2_dispenser_leak.png);background-size:{DW * 4 * Z}px {DH * Z}px;animation:disp .667s steps(4) infinite}}
@keyframes disp{{from{{background-position:0 0}}to{{background-position:-{DW * 4 * Z}px 0}}}}
.a-disp1{{width:{DW}px;height:{DH}px;background-image:url(pendentes/anim/anim_machine_o2_dispenser.png);background-size:{DW * 4}px {DH}px;animation:disp1 .667s steps(4) infinite}}
@keyframes disp1{{from{{background-position:0 0}}to{{background-position:-{DW * 4}px 0}}}}
.a-leak{{width:192px;height:336px;background-image:url(pendentes/leak_blink.png);background-size:384px 336px;animation:leak .8s steps(2) infinite}}
@keyframes leak{{from{{background-position:0 0}}to{{background-position:-384px 0}}}}
.a-leakscene{{width:100%;aspect-ratio:480/270;background-size:100% 100%;image-rendering:pixelated;animation:lks .8s step-end infinite;border:1px solid var(--line)}}
@keyframes lks{{0%{{background-image:url(cena_vazamento_on.png)}}50%{{background-image:url(cena_vazamento_off.png)}}}}
.a-doorscene{{width:100%;aspect-ratio:480/270;background-size:100% 100%;image-rendering:pixelated;animation-duration:3s;animation-timing-function:step-end;animation-iteration-count:infinite;border:1px solid var(--line)}}
{door_scene_css}
table{{border-collapse:collapse;margin:8px 0}}td,th{{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}}th{{font:12px "Silkscreen",monospace;color:var(--gold)}}
pre{{background:#120d0b;border:1px solid var(--line);padding:12px 16px;overflow:auto;font:13px/1.5 "IBM Plex Mono",monospace;color:#d8cfc4}}
</style></head><body><div class="wrap">
<div class="eyebrow">Hesper · Designer · v0.5 Marco 2 · proposta pro dono aprovar (nada disso está no jogo)</div>
<h1>Base respirável: chão, parede alta, porta e Dispersor de O₂</h1>

<div class="v2"><b>v1.2 · o que mudou (feedback do dono: o vão ficou apertado)</b><ul>
<li><b>A parede continua grossa</b> (padrão do jogo). O que mudou foi a porta: saíram os batentes de 5 px que comiam a
passagem. Agora a porta é só uma <b>moldura fina</b> (jambas de 2 px e a travessa) na borda de fora da parede, e a
folha <b>some dentro da parede</b> ao abrir. Aberta, o vão fica com 28 px livres na solo e 60 px na dupla.</li>
<li><b>Dois tipos</b>: a <b>porta solo</b> (1 tile, uma folha que corre pra esquerda) e a <b>porta dupla</b> (2 tiles lado a
lado, duas folhas que abrem do meio pros lados, com a emenda em degrau na junção dos tiles). Ambas na horizontal e na
vertical, 4 quadros, na linguagem airlock (grafite, X em relevo, travessa laranja e LED).</li>
<li><b>Posição: variante B</b> (folha rente à face de fora da parede), a recomendada. A A não foi refeita.</li>
<li>A parede ao lado da porta agora mostra a <b>ponta</b> dela (a porta não emenda no desenho da parede; continua
contando como parede pra vedação). É isso que emoldura o vão.</li>
<li>A porta fina A/B da v1.1 e a grossa da v1.0 estão no bloco "anterior", no fim da seção da porta.</li>
</ul></div>

<div class="v2" style="opacity:.75;margin-top:10px"><b>v1.1 · o que mudou (feedback do dono)</b><ul>
<li><b>Aprovado</b>: chão, parede alta com autotile, Dispersor (com a tira âmbar de vazamento, que <b>entra</b>), aviso de
vazamento e ícones. Decidido: a parede <b>não</b> emenda com a rocha, o chão é igual nos 3 estágios e a parede de baixo
cobrir a última fileira está ok.</li>
<li><b>Porta refeita, FINA</b>: airlock de 2 folhas de metal grafite (3 px de espessura) encostadas numa borda da parede,
com a emenda em degrau no meio, o X em relevo em cada folha e a moldura de metal claro (batentes finos e a travessa
com a faixa laranja e o LED). O resto do tile é soleira com o trilho, entre os batentes bege que emendam com a parede.
As folhas deslizam pros lados a partir do meio.</li>
<li><b>Duas variantes pra escolher</b>: <b>A</b> = folha na borda de <b>dentro</b> da base; <b>B</b> = folha na borda de
<b>fora</b>. Os sprites são os mesmos 4 (um por borda); a variante é só a regra de qual borda usar.</li>
<li>A porta grossa da v1.0 ficou em <code>anterior/</code> pra comparar, no fim da seção da porta.</li>
</ul></div>

<div class="v2" style="opacity:.75;margin-top:10px"><b>v1.0 · o que tem aqui</b><ul>
<li><b>Parede ALTA estilo Core Keeper</b>, na mesma geometria da parede de rocha do jogo: o bloco ocupa o tile e tem
<b>24 px de altura</b>. O topo (32×32) sobe 24 px por cima do tile de trás e a face (32×24) aparece embaixo quando o
vizinho de baixo não é parede. Total na tela: <b>56 px</b> (24 + 32). Usa o raio-x que já existe, sem mudar nada nele.</li>
<li><b>Autotile do topo no layout A2</b> (o mesmo do <code>water_auto</code>, que o <code>game/autotile.py</code> já
monta): 47 combinações com quinas externas, internas, T, cruz, pontas e peça isolada. A <b>face</b> tem 4 peças
(pontas abertas ou emendadas dos lados).</li>
<li><b>Chão construído</b>: chapa de aço azulada de valor médio, 4 variações. Não muda com o estágio (é construído).</li>
<li><b>Porta</b> nas 2 orientações, 4 quadros (fechada → aberta). <i>Refeita na v1.1.</i></li>
<li><b>Dispersor de O₂</b>, da família r3d (sapata B, bege, faixa laranja): soprando, parado e (opcional) vazamento.</li>
<li><b>Aviso de vazamento</b>: uma "parede-fantasma" vermelha piscando no tile que falta, por cima de tudo.</li>
<li>4 ícones novos. O da cápsula de água já estava aprovado e não foi mexido.</li>
</ul></div>

<h2>Base pronta nas 3 paletas</h2>
<div class="grid3">
<figure><img class="px" src="cena_base_arid.png" alt=""><figcaption><b>Árido / Morto</b></figcaption></figure>
<figure><img class="px" src="cena_base_mist.png" alt=""><figcaption><b>Névoa</b></figcaption></figure>
<figure><img class="px" src="cena_base_green.png" alt=""><figcaption><b>Verde</b></figcaption></figure>
</div>
<p>Recortes 480×270 (metade da tela), montados só com os sprites, na ordem do jogo. Base com 5×4 de chão por dentro,
porta na parede de baixo (horizontal) e na da direita (vertical), o Dispersor no meio soprando, a Bancada T2, o baú, a
luminária e o O₂ nv.1 em cima do chão, o painel solar fora. Repare no O₂ do canto de baixo: o topo da parede de baixo
cobre o pé dele, igual a parede de rocha faz hoje (é o "alto" do Core Keeper).</p>

<h2>Raio-x: o player atrás da parede</h2>
<div class="grid3">
<figure><img class="px" src="cena_raiox_arid.png" alt=""><figcaption><b>com o raio-x</b> · o player encostado na parede de baixo, por dentro: o topo cobre o corpo e ele é redesenhado com alpha 95 por cima (o <code>_draw_player_silhouette</code> de hoje)</figcaption></figure>
<figure><img class="px" src="cena_raiox_sem_arid.png" alt=""><figcaption>a mesma cena <b>sem</b> o raio-x, pra comparar</figcaption></figure>
<figure><img class="px" src="cena_raiox_fundo_green.png" alt=""><figcaption>atrás da parede de cima, pelo lado de fora (Verde)</figcaption></figure>
</div>

<h2>Vazamento: o tile furado pisca</h2>
<div class="grid2">
<figure><div class="a-leakscene"></div><figcaption>um tile da parede da direita faltando · <b>Névoa</b> · pisca a 2,5 Hz · o Dispersor com o LED âmbar (tira opcional de vazamento)</figcaption></figure>
<div class="flex">
<figure><div class="chk"><div class="sp a-leak"></div></div><figcaption><code>leak_blink.png</code> · 6× animado</figcaption></figure>
{img("pendentes/leak_blink.png", 4, cap="64×56 · quadro 0 aceso · quadro 1 apagado")}
</div>
</div>
<p>É uma parede-fantasma do tamanho do bloco (topo + face), com a cantoneira e a hachura vermelhas, o triângulo de
alerta e as setinhas de ar saindo. Desenhada <b>por cima de tudo</b>, então lê em cima de chão, de vazio e até
quando a parede de baixo cobre o tile.</p>

<h2>Porta solo e porta dupla</h2>
<div class="grid2">
<figure><div class="a-doorscene" style="animation-name:dscm1"></div><figcaption><b>mock 1</b> · <b>solo</b> na parede de baixo (horizontal) e <b>dupla</b> na da direita (vertical), abrindo e fechando (0 → 3 → 0)</figcaption></figure>
<figure><div class="a-doorscene" style="animation-name:dscm2"></div><figcaption><b>mock 2</b> · <b>dupla</b> na parede de baixo (horizontal) e <b>solo</b> na da direita (vertical)</figcaption></figure>
</div>
<div class="grid3" style="margin-top:14px">
<figure><img class="px" src="cena_porta_m1_0.png" alt=""><figcaption>mock 1 · fechada</figcaption></figure>
<figure><img class="px" src="cena_porta_m1_1.png" alt=""><figcaption>mock 1 · abrindo (quadro 1)</figcaption></figure>
<figure><img class="px" src="cena_porta_m1_3.png" alt=""><figcaption>mock 1 · aberta</figcaption></figure>
<figure><img class="px" src="cena_porta_m2_0.png" alt=""><figcaption>mock 2 · fechada</figcaption></figure>
<figure><img class="px" src="cena_porta_m2_1.png" alt=""><figcaption>mock 2 · abrindo (quadro 1)</figcaption></figure>
<figure><img class="px" src="cena_porta_m2_3.png" alt=""><figcaption>mock 2 · aberta</figcaption></figure>
<figure><img class="px" src="cena_porta_m1_mist_0.png" alt=""><figcaption>mock 1 · fechada · Névoa</figcaption></figure>
<figure><img class="px" src="cena_porta_m2_green_3.png" alt=""><figcaption>mock 2 · aberta · Verde</figcaption></figure>
<figure><img class="px" src="cena_porta_m2_mist_0.png" alt=""><figcaption>mock 2 · fechada · Névoa</figcaption></figure>
</div>
<h3 style="margin-top:22px">Solo · <code>base_door_{{h_n,h_s,v_w,v_e}}.png</code> · 128×56 (4 quadros de 32×56)</h3>
<div class="flex" style="margin-top:8px">
<figure><div class="chk"><div class="sp a-door" style="background-image:url(pendentes/base_door_h_s.png)"></div></div><figcaption><code>h_s</code> · horizontal, folha na borda sul · 6×</figcaption></figure>
<figure><div class="chk"><div class="sp a-door" style="background-image:url(pendentes/base_door_v_e.png)"></div></div><figcaption><code>v_e</code> · vertical, folha na borda leste · 6×</figcaption></figure>
{img("pendentes/base_door_h_s.png", 4, cap="h_s · 0 fechada · 1 · 2 · 3 aberta")}
{img("pendentes/base_door_h_n.png", 4, cap="h_n (porta na parede de cima)")}
{img("pendentes/base_door_v_e.png", 4, cap="v_e")}
{img("pendentes/base_door_v_w.png", 4, cap="v_w (porta na parede da esquerda)")}
</div>
<h3 style="margin-top:22px">Dupla · <code>base_door2_{{h_n,h_s,v_w,v_e}}.png</code> · 256×56 (metade 1: quadros 0–3; metade 2: quadros 4–7)</h3>
<div class="flex" style="margin-top:8px">
<figure><div class="chk" style="display:flex"><div class="sp a-door" style="background-image:url(pendentes/base_door2_h_s.png);background-size:1536px 336px"></div><div class="sp a-door2" style="background-image:url(pendentes/base_door2_h_s.png)"></div></div><figcaption><code>h_s</code> · as 2 metades lado a lado · 6×</figcaption></figure>
<figure><div class="chk"><div class="sp a-door" style="background-image:url(pendentes/base_door2_v_e.png);background-size:1536px 336px"></div><div class="sp a-door2" style="background-image:url(pendentes/base_door2_v_e.png);margin-top:-144px"></div></div><figcaption><code>v_e</code> · metade de cima e a de baixo (32 px abaixo) · 6×</figcaption></figure>
{img("pendentes/base_door2_h_s.png", 3, cap="h_s · metade 1 (q 0–3) · metade 2 (q 0–3)")}
{img("pendentes/base_door2_v_e.png", 3, cap="v_e · metade 1 (cima) · metade 2 (baixo)")}
</div>
<p><b>Como abrem:</b> a solo corre pra <b>esquerda</b> na horizontal. Na vertical, "esquerda" não existe pra câmera
(ela vê a parede de lado), então decidi uma regra só: <b>a folha da solo sempre corre pro lado de menor coordenada</b>,
oeste na horizontal e <b>norte na vertical</b>. Na tela, a folha da vertical sobe e entra na parede de trás (que é
desenhada antes), o que lê bem como "sumiu dentro da parede". A dupla abre do meio: na horizontal cada folha vai pro seu
lado (oeste e leste) e na vertical a de cima sobe e a de baixo desce (entra embaixo do topo da parede de baixo).</p>
<p><b>Limite da vertical</b> (igual antes): a câmera vê essa parede de lado, então da folha só aparece o topo, uma faixa
grafite de 4 px com as pontas laranja (e o degrau, na dupla). O X e a travessa só aparecem na horizontal.</p>
<details><summary style="color:var(--muted);cursor:pointer;font:600 18px 'Pixelify Sans',monospace;margin-top:20px">anterior · v1.1 porta fina A/B e v1.0 porta grossa (reprovadas)</summary>
<p>v1.1: airlock fina com batentes de 5 px dos dois lados (vão de 22 px, apertado). A = folha por dentro, B = por fora.</p>
<div class="grid2" style="margin-top:12px">
<figure><img class="px" src="anterior/cena_porta_fina_A_0.png" alt=""><figcaption>v1.1 · A · fechada</figcaption></figure>
<figure><img class="px" src="anterior/cena_porta_fina_B_0.png" alt=""><figcaption>v1.1 · B · fechada</figcaption></figure>
<figure><img class="px" src="anterior/cena_porta_fina_A_3.png" alt=""><figcaption>v1.1 · A · aberta</figcaption></figure>
<figure><img class="px" src="anterior/cena_porta_fina_B_3.png" alt=""><figcaption>v1.1 · B · aberta</figcaption></figure>
</div>
<div class="flex" style="margin-top:12px">
{img("anterior/fina_base_door_h_n.png", 3, cap="v1.1 · h_n")}
{img("anterior/fina_base_door_h_s.png", 3, cap="v1.1 · h_s")}
{img("anterior/fina_base_door_v_w.png", 3, cap="v1.1 · v_w")}
{img("anterior/fina_base_door_v_e.png", 3, cap="v1.1 · v_e")}
</div>
<p>v1.0: a porta grossa, que ocupava o bloco inteiro.</p>
<div class="grid2" style="margin-top:12px">
<figure><img class="px" src="anterior/cena_porta_0.png" alt=""><figcaption>v1.0 · fechada</figcaption></figure>
<figure><img class="px" src="anterior/cena_porta_3.png" alt=""><figcaption>v1.0 · aberta</figcaption></figure>
</div>
<div class="flex" style="margin-top:12px">
{img("anterior/base_door_h.png", 3, cap="v1.0 · horizontal")}
{img("anterior/base_door_v.png", 3, cap="v1.0 · vertical")}
</div>
</details>

<h2>Dispersor de O₂</h2>
<div class="flex">
{img("pendentes/machine_o2_dispenser.png", Z, cap="parado (sem água / sem energia) · <code>machine_o2_dispenser.png</code> · grade apagada, LED vermelho")}
<figure><div class="chk"><div class="sp a-disp"></div></div><figcaption>soprando (vedado) · 4 quadros a 6 fps · grade ciano pulsando, bolhas de ar saindo</figcaption></figure>
<figure><div class="chk"><div class="sp a-displ"></div></div><figcaption>opcional: vazamento · grade e LED âmbar, sopro fraco</figcaption></figure>
<figure><div class="chk" style="padding:18px"><img src="pendentes/machine_o2_dispenser.png" width="{DW}" height="{DH}" alt=""> <div class="sp a-disp1"></div> <img src="../../../assets/sprites/chest.png" width="32" height="40" alt=""> <img src="../../../assets/sprites/machine_o2.png" width="40" height="56" alt=""></div><figcaption>1×: parado, soprando, o baú e o gerador de O₂ nv.1</figcaption></figure>
</div>
<p>Corpo bege baixo com a <b>cápsula de água encaixada na janela da frente</b> (a mesma água azul do ícone da cápsula),
faixa laranja e a <b>grade difusora</b> acesa em ciano por onde o ar sai em volta toda, com o chapéu por cima. Pra não
confundir com o gerador de O₂ (tanque alto com ventoinha), ele é baixo e largo, do tamanho do baú.</p>

<h2>Chão</h2>
<div class="flex">{floors}</div>
<p>Aço azulado de valor médio, com chanfro (luz de cima-esquerda) e rebites. Contrasta pela cor com o vermelho do
Árido e o verde, e pelo valor e pela temperatura com o cinza-marrom escuro da Névoa. Máquina em cima lê bem (o bege
das máquinas é bem mais claro). Sorteio sugerido por hash do tile:
<code>(tx·73856093 ^ ty·19349663) &amp; 7</code> → <code>0,0,0,0,1,1,2,3</code>.</p>

<h2>Parede alta</h2>
<div class="flex">
{img("altura_rocha_x_base.png", 3, cap="a parede de rocha de hoje × a da base: mesma altura (topo 24 px acima, face 24 px), com o Explorador e o O₂ nv.1")}
</div>
<div class="flex" style="margin-top:18px">
<figure><img src="atlas_grade.png" width="{aw}" height="{ah}" alt=""><figcaption><code>base_wall_top.png</code> 64×96 · 6× · grade de minitiles 16×16 · layout A2</figcaption></figure>
<div>
{img("pendentes/base_wall_face.png", 4, cap="<code>base_wall_face.png</code> 128×24 · peças 0 · 1 · 2 · 3 (índice = W + 2·E)")}
<p style="max-width:560px">Topo: chapa ardósia escura (o "telhado" do muro, mais escuro que o chão pra ler como
altura), aba clara nas bordas de cima e da esquerda, escura nas de baixo e da direita, um sulco e o miolo
antiderrapante. A borda de baixo do topo é uma aba clara: é o encontro com a face. Face: trilho, painel bege da
família das máquinas, um respiro por tile, a faixa laranja <code>#e2733a</code> e o rodapé escuro com rebites, escurecendo pro pé.
Nada de junta vertical repetida.</p>
</div>
</div>

<h2>Tabela de autotile ({ncombo} combinações)</h2>
<div class="grid3">
<figure><img class="px" src="cena_autotile_arid.png" alt=""><figcaption>formatos variados: ponta, isolada, quina, T, cruz, anel 3×3 com 1 chão no meio</figcaption></figure>
<figure><img class="px" src="cena_autotile_mist.png" alt=""><figcaption>Névoa</figcaption></figure>
<figure><img class="px" src="cena_autotile_green.png" alt=""><figcaption>Verde</figcaption></figure>
</div>
<figure style="margin-top:14px"><img src="autotile_47.png" width="{tw}" height="{th}" style="max-width:100%;height:auto" alt=""><figcaption>as {ncombo} combinações de verdade, cada uma num arranjo 3×3 (vizinhos escurecidos). Código = peças TL TR BL BR: o externo, h borda horizontal, v borda vertical, i canto interno, f miolo</figcaption></figure>

<div class="box" style="margin-top:14px">
<h3>A regra de índice (a mesma do <code>game/autotile.py</code>)</h3>
<p><code>conn(x, y)</code> = o tile é <b>parede da base</b> (rocha não conta; desde a v1.2 a porta também não conta no desenho). Cada tile de parede é montado
com 4 quadrantes 16×16 (TL, TR, BL, BR). Cada quadrante olha 3 vizinhos: o do lado (esquerda ou direita), o vertical
(cima ou baixo) e a diagonal entre eles:</p>
<table><tr><th>lado</th><th>vertical</th><th>diagonal</th><th>peça</th></tr>
<tr><td>não</td><td>não</td><td>–</td><td>canto externo (<code>outer</code>)</td></tr>
<tr><td>sim</td><td>não</td><td>–</td><td>borda horizontal (<code>hedge</code>)</td></tr>
<tr><td>não</td><td>sim</td><td>–</td><td>borda vertical (<code>vedge</code>)</td></tr>
<tr><td>sim</td><td>sim</td><td>não</td><td>canto interno (<code>inner</code>)</td></tr>
<tr><td>sim</td><td>sim</td><td>sim</td><td>miolo (<code>full</code>)</td></tr></table>
<p>Os 4 quadrantes em <code>outer</code> = peça isolada (bloco 0,0–32,32). Minitile (coluna, linha) de cada peça no
atlas:</p>
<table><tr><th>quadrante</th><th>outer</th><th>hedge</th><th>vedge</th><th>inner</th><th>full</th><th>isolada</th></tr>
<tr><td>TL</td><td>(0,2)</td><td>(2,2)</td><td>(0,4)</td><td>(2,0)</td><td>(2,4)</td><td>(0,0)</td></tr>
<tr><td>TR</td><td>(3,2)</td><td>(1,2)</td><td>(3,4)</td><td>(3,0)</td><td>(1,4)</td><td>(1,0)</td></tr>
<tr><td>BL</td><td>(0,5)</td><td>(2,5)</td><td>(0,3)</td><td>(2,1)</td><td>(2,3)</td><td>(0,1)</td></tr>
<tr><td>BR</td><td>(3,5)</td><td>(1,5)</td><td>(3,3)</td><td>(3,1)</td><td>(1,3)</td><td>(1,1)</td></tr></table>
<p>Em código: <code>autotile.sources(autotile.tile_key(conn, tx, ty))</code> já devolve isso; é só trocar o atlas da
água pelo <code>base_wall_top.png</code>. <b>Face</b>: <code>idx = conn(x−1, y) + 2·conn(x+1, y)</code> → recorte
<code>(idx·32, 0, 32, 24)</code> do <code>base_wall_face.png</code> (0 = as duas pontas abertas, 1 = emenda à
esquerda, 2 = emenda à direita, 3 = emenda dos dois lados).</p>
</div>

<h2>Ícones</h2>
<div class="flex">{icons}</div>

<h2>Pro Dev integrar</h2>
<div class="box"><ul>
<li><b>Nada disso entra sem o ok do dono.</b> Os PNGs estão em <code>reports/design/v05_m2_base/pendentes/</code>, com os
nomes prontos pro <code>assets/sprites/</code>. Ids sugeridos: <code>base_floor</code>, <code>base_wall</code>,
<code>base_door</code> (solo), <code>base_door_double</code>, <code>o2_dispenser</code>.</li>
<li><b>Chão</b> <code>base_floor_{{0..3}}.png</code> 32×32 em (x, y), na passada do chão (embaixo de tudo). Variação pelo
hash acima.</li>
<li><b>Parede</b>, igual ao <code>_draw_wall</code>: topo montado dos 4 minitiles do <code>base_wall_top.png</code> em
<b>(x, y − 24)</b> (<code>C.WALL_LIFT</code>); se <code>not conn(x, y + 1)</code>, face 32×24 em <b>(x, y + 8)</b>
(<code>FACE_Y</code>). <b>Altura do bloco: 24 px; ocupa na tela de y − 24 a y + 32 (56 px).</b> Os sprites já trazem o
contorno: não precisa do <code>outline_h/v</code>. Colisão: o tile inteiro.</li>
<li><b>Ordem de desenho</b>: a parede da base entra na mesma vez das paredes da linha (antes dos objetos com o pé
naquela linha). Na superfície, onde a linha vira a tira de morro (<code>hill_rows</code>), o jeito simples é pôr cada
parede/porta da base no <code>collect_objects</code> com <code>ay = ty·32 + 1</code>: cai na linha certa e é o primeiro
da linha.</li>
<li><b>Raio-x</b>: no <code>player_occluded</code>, a linha de baixo também conta parede da base e <b>porta fechada ou
abrindo</b> (quadros 0–1). Porta nos quadros 2–3 não acende (a passagem está aberta).</li>
<li><b>Parede × porta no desenho</b>: no autotile e na face da parede, <code>conn</code> = só parede da base. A porta
<b>não</b> conta (a parede ao lado mostra a ponta, que emoldura o vão). Pra <b>vedação</b> e pro raio-x a porta conta como
parede.</li>
<li><b>Portas (v1.2)</b>: todo tile de porta desenha um quadro de 32×56 em <b>(x, y − 24)</b>, na vez das paredes da linha
(ou como objeto com <code>ay = ty·32 + 1</code>). O quadro traz moldura, folha e soleira; o tile da porta não desenha chão
à parte. Abre com o player a ≤ 1,5 tile do tile (ou de qualquer tile da dupla): 0 → 3 a ~12 fps, fica no 3, volta
3 → 0 quando ele sai. Raio-x: quadros 0–1 contam como parede.
<ul>
<li><b>Orientação</b>: <code>h</code> se a porta está numa parede horizontal (vizinhos a oeste/leste são parede ou porta);
<code>v</code> se norte e sul são parede ou porta e os lados não. Na dupla, é o eixo das 2 metades (lado a lado = h,
uma em cima da outra = v).</li>
<li><b>Borda (variante B)</b>: a borda de <b>fora</b> = o lado oposto ao chão da base (o flood fill do Dispersor sabe).
h: chão ao norte → <code>h_s</code>, chão ao sul → <code>h_n</code>. v: chão a oeste → <code>v_e</code>, chão a leste →
<code>v_w</code>. Porta solta (sem base): <code>h_s</code> / <code>v_e</code>.</li>
<li><b>Solo</b> <code>base_door_{{o}}_{{e}}.png</code> 128×56: quadro k em <code>(k·32, 0, 32, 56)</code>.</li>
<li><b>Dupla</b> <code>base_door2_{{o}}_{{e}}.png</code> 256×56: metade 1 (oeste na h, norte na v) no quadro k em
<code>(k·32, 0)</code>; metade 2 (leste/sul) em <code>((4 + k)·32, 0)</code>. As 2 metades sempre no mesmo quadro.</li>
</ul></li>
<li><b>Dupla no construtor</b>: é <b>um item só</b> que ocupa 2 tiles. O fantasma mostra 2×1 ou 1×2; o R gira (h ↔ v), e
também dá pra sugerir a orientação pela parede embaixo do cursor. A âncora é a metade 1 (o tile de oeste/norte); a outra
metade é o vizinho (+1 em x na h, +1 em y na v). Só coloca se os 2 tiles estão livres (ou são parede da base no lugar
da qual ela entra, se o Dev quiser substituir). É um objeto só no save (tile da metade 1 + orientação); <b>desmontar
qualquer metade tira as duas</b> e devolve 1 receita. Pro flood fill, os 2 tiles são porta.</li>
<li><b>Colisão</b> (x, y = canto do tile; dupla h: x = tile da metade 1, a porta vai até x + 64; dupla v: até y + 64):
<table><tr><th>porta</th><th>fechada (quadros 0–2)</th><th>aberta (quadro 3)</th><th>vão aberto</th></tr>
<tr><td>solo <code>h_s</code></td><td><code>(x, y+27, 32, 5)</code></td><td><code>(x, y+27, 2, 5)</code> e <code>(x+30, y+27, 2, 5)</code></td><td>28 px</td></tr>
<tr><td>solo <code>h_n</code></td><td><code>(x, y, 32, 5)</code></td><td><code>(x, y, 2, 5)</code> e <code>(x+30, y, 2, 5)</code></td><td>28 px</td></tr>
<tr><td>solo <code>v_e</code></td><td><code>(x+26, y, 6, 32)</code></td><td><code>(x+26, y, 6, 2)</code> e <code>(x+26, y+30, 6, 2)</code></td><td>28 px</td></tr>
<tr><td>solo <code>v_w</code></td><td><code>(x, y, 6, 32)</code></td><td><code>(x, y, 6, 2)</code> e <code>(x, y+30, 6, 2)</code></td><td>28 px</td></tr>
<tr><td>dupla <code>h_s</code></td><td><code>(x, y+27, 64, 5)</code></td><td><code>(x, y+27, 2, 5)</code> e <code>(x+62, y+27, 2, 5)</code></td><td>60 px</td></tr>
<tr><td>dupla <code>h_n</code></td><td><code>(x, y, 64, 5)</code></td><td><code>(x, y, 2, 5)</code> e <code>(x+62, y, 2, 5)</code></td><td>60 px</td></tr>
<tr><td>dupla <code>v_e</code></td><td><code>(x+26, y, 6, 64)</code></td><td><code>(x+26, y, 6, 2)</code> e <code>(x+26, y+62, 6, 2)</code></td><td>60 px</td></tr>
<tr><td>dupla <code>v_w</code></td><td><code>(x, y, 6, 64)</code></td><td><code>(x, y, 6, 2)</code> e <code>(x, y+62, 6, 2)</code></td><td>60 px</td></tr></table>
As jambas de 2 px abertas podem até ficar sem colisão (a parede do lado já segura). Fechada, só a faixa da moldura
bloqueia: o resto do tile é soleira andável (o player encosta na folha pelo lado de dentro).</li>
<li><b>Dispersor</b> <code>machine_o2_dispenser.png</code> 32×48, âncora padrão das máquinas (centro da borda de baixo do
tile), sapata B de 1 tile. Parado = sem água ou sem energia. <code>anim/anim_machine_o2_dispenser.png</code> 128×48, 4
quadros, ~6 fps, enquanto "Vedado ✓". Opcional: <code>anim/anim_machine_o2_dispenser_leak.png</code> (mesmo formato)
enquanto "Vazamento". Sem a tira, usa o parado.</li>
<li><b>Vazamento</b> <code>leak_blink.png</code> 64×56: 2 quadros de 32×56 em <b>(x, y − 24)</b> do tile furado (o primeiro
tile fora do chão alcançado pelo flood fill que não é parede nem porta), alternando a ~2,5 Hz (0,2 s cada), desenhado
<b>depois</b> dos objetos e do raio-x (junto da camada de destaques). Só enquanto o estado for "Vazamento".</li>
<li><b>Ícones</b> 16×16: <code>icon_base_floor</code>, <code>icon_base_wall</code>, <code>icon_base_door</code> (solo),
<code>icon_base_door_double</code>,
<code>icon_o2_dispenser</code>. Contorno <code>#1b1630</code>, alpha 0/255.</li>
<li>Regerar: <code>python3 tools/sprites/v05_m2_base.py</code> (determinístico; refaz este report).</li>
</ul></div>

<h2>Pro dono decidir</h2>
<div class="ask"><ul>
<li><b>Porta solo e dupla</b> na variante B: aprova? Se quiser a folha por dentro (A), é só inverter a regra da borda
(os mesmos sprites servem).</li>
</ul></div>
</div></body></html>
"""
    page = OUT / "index.html"
    page.write_text(html, encoding="utf-8")
    return page


if __name__ == "__main__":
    print(build())
