#!/usr/bin/env python3
"""v0.6 M1 · baús em 3 tamanhos: ícones pequeno/grande (A/B/C), silhueta de chip vazio (A/B) e conferência
dos 3 sprites de mundo como baú construído. PROPOSTA: nada vai pra assets/sprites sem o ok do dono.

    python3 tools/sprites/v06_m1_baus.py

Saída: reports/design/v06_m1_baus/ (pendentes/ + prévias + index.html). Só LÊ assets/sprites/. Determinístico.
Ícones: 16×16, mesma família do icon_chest (azul #0a74de/#2f93f4/#055ec8, cinza #d9dde6/#a9b0be, contorno #1b1630).
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SPR = ROOT / "assets" / "sprites"
REP = ROOT / "reports" / "design" / "v06_m1_baus"
PEND = REP / "pendentes"

K = {"a": "#1b1630", "b": "#2f93f4", "c": "#0a74de", "d": "#d4ecff", "e": "#055ec8", "f": "#d9dde6",
     "g": "#a9b0be", "h": "#0444a8", "i": "#8c93a3", "y": "#f2c46d", "Y": "#b8823c"}


def grid(txt, ox=0, oy=0):
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(txt.strip("\n").split("\n")):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x + ox, y + oy), tuple(int(K[ch][i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    return im


# ---- baú simples (8): 12×10, cresce menos que o normal (12 de largura), lido como o loot_crate de longe
SMALL_A = """
..aaaaaaaa..
.abdbbdbbba.
abbbbbbbbbca
affffffgffga
accccgicccha
acccccccccha
acccccccccha
.aaaaaaaaaa.
"""
SMALL_B = """
..aaaaaaaa..
.abdbbdbbba.
abbbbbbbbbca
affffffffffa
acccyyccccha
acccyYccccha
acccccccccha
acccccccccha
.aaaaaaaaaa.
"""
SMALL_C = """
..aaaaaaaa..
.abdbbdbbba.
abbbbbbbbbca
affffgiffgfa
agccccccccag
agccccccccag
acccccccccha
.aaaaaaaaaa.
"""

# ---- baú grande (24): 16×15, cheio como o container_sealed (tampa em 4 gomos, 2 cintas, fecho dourado)
LARGE_A = """
.aaaaaaaaaaaaaa.
abbdbbdbbdbbbbca
abbbbbbbbbbbbbca
abbbbbbbbbbbbbca
affffffgfffffgfa
agiccgccccgiccha
agiccgcyycgiccha
agiccgcyYcgiccha
agiccgccccgiccha
acccccccccccccha
acccccccccccccha
.aaaaaaaaaaaaaa.
"""
LARGE_B = """
..aaaaaaaaaaaa..
.abdbbdbbdbbbca.
abbbbbbbbbbbbbca
abdbbbbbbbbbbbca
affffffffffffffa
agcccccgcccgccch
agcccccgyyygccch
agcccccgyYygccch
agcccccgcccgccch
accccccccccccceh
.aaaaaaaaaaaaaa.
.aa..........aa.
"""
LARGE_C = """
.aaaaaaaaaaaaaa.
abbdbbdbbdbbbbca
abbbbbbbbbbbbbca
affffffffffffffa
afiggggggggggigf
agccccccccccccch
agcgcccyycccgcch
agcgcccyYcccgcch
agccccccccccccch
accccccccccccceh
.aaaaaaaaaaaaaa.
..aa........aa..
"""

# ---- silhueta de slot de chip vazio: cinza translúcido (alpha fixo 96), sem contorno escuro; lembra o icon_chip
CHIP_A_TXT = """
....x.x..x.x....
...xxxxxxxxxx...
...x.......xx...
.xxxxxxxxxxxxxx.
xxx..........xxx
.xx..xxxxxx..xx.
xxx..x....x..xxx
.xx..x....x..xx.
.xx..x....x..xx.
xxx..x....x..xxx
.xx..xxxxxx..xx.
xxx..........xxx
.xxxxxxxxxxxxxx.
...xx.xx.xx.xx..
...xxxxxxxxxx...
....x.x..x.x....
"""


def chip_a():
    """Contorno tracejado do chip inteiro (corpo + pinos), miolo vazio: lê 'encaixe'."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    src = Image.open(SPR / "icon_chip.png").convert("RGBA")
    for y in range(16):
        for x in range(16):
            if src.getpixel((x, y))[3]:
                edge = any(not (0 <= x + dx < 16 and 0 <= y + dy < 16) or src.getpixel((x + dx, y + dy))[3] == 0
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if edge:
                    im.putpixel((x, y), (150, 150, 158, 96))
    return im


def chip_b():
    """Silhueta cheia (a máscara do icon_chip) em cinza apagado, com o miolo mais fundo: lê 'espaço do item'."""
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    src = Image.open(SPR / "icon_chip.png").convert("RGBA")
    for y in range(16):
        for x in range(16):
            if src.getpixel((x, y))[3]:
                core = 5 <= x <= 10 and 5 <= y <= 10
                im.putpixel((x, y), (130, 130, 140, 70) if core else (150, 150, 158, 96))
    return im


ITEMS = {
    "icon_chest_small_A": lambda: grid(SMALL_A, 2, 4), "icon_chest_small_B": lambda: grid(SMALL_B, 2, 4),
    "icon_chest_small_C": lambda: grid(SMALL_C, 2, 4),
    "icon_chest_large_A": lambda: grid(LARGE_A, 0, 2), "icon_chest_large_B": lambda: grid(LARGE_B, 0, 1),
    "icon_chest_large_C": lambda: grid(LARGE_C, 0, 1),
    "chip_slot_empty_A": chip_a, "chip_slot_empty_B": chip_b,
}


def load(n):
    return Image.open(SPR / f"{n}.png").convert("RGBA")


def up(im, s):
    return im.resize((im.width * s, im.height * s), Image.NEAREST)


def hotbar(icon):
    slot = load("ui_slot")
    names = ["scanner", "chest", "lamp"]
    icons = [icon] + [load(f"icon_{n}") for n in names]
    out = Image.new("RGBA", (len(icons) * 22 + 2, 24), (22, 17, 14, 255))
    for i, ic in enumerate(icons):
        out.alpha_composite(slot, (2 + i * 22, 2))
        out.alpha_composite(ic, (4 + i * 22, 4))
    return out


def base_scene(ghost=None):
    """Chão da base (base_floor), uma máquina de referência e os 3 baús com o pé no centro de baixo do tile."""
    W, H = 320, 160
    cv = Image.new("RGBA", (W, H))
    for ty in range(H // 32):
        for tx in range(W // 32):
            cv.alpha_composite(load(f"base_floor_{(tx * 3 + ty * 5) % 4}"), (tx * 32, ty * 32))
    # fileira de parede de base atrás (se existir os sprites), senão só o chão
    items = [("machine_heater", None), ("loot_crate", None), ("chest", None), ("container_sealed", None)]
    xs = [48, 112, 176, 256]
    foot = 112
    for (n, _), cx in zip(items, xs):
        try:
            im = load(n)
        except FileNotFoundError:
            continue
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for dx in range(-im.width // 2 + 3, im.width // 2 - 2):
            for dy in (-2, -1, 0, 1):
                if 0 <= cx + dx < W:
                    sh.putpixel((cx + dx, foot + dy), (0, 0, 0, 70))
        cv.alpha_composite(sh)
        cv.alpha_composite(im, (cx - im.width // 2, foot - im.height))
    return cv


def tint(im, rgb, a=110):
    """Fantasma do construtor: sprite inteiro com cor chapada translúcida (verde = pode, vermelho = não pode)."""
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for y in range(im.height):
        for x in range(im.width):
            p = im.getpixel((x, y))
            if p[3]:
                m = (p[0] + p[1] + p[2]) / 3 / 255
                out.putpixel((x, y), tuple(int(c * (0.55 + 0.6 * m)) for c in rgb) + (a,))
    return out


def ghost_scene():
    W, H = 320, 128
    cv = Image.new("RGBA", (W, H))
    for ty in range(H // 32):
        for tx in range(W // 32):
            cv.alpha_composite(load(f"base_floor_{(tx * 3 + ty * 5) % 4}"), (tx * 32, ty * 32))
    names = ["loot_crate", "chest", "container_sealed"]
    for row, rgb in ((0, (90, 230, 100)), (1, (240, 70, 70))):
        for i, n in enumerate(names):
            im = load(n)
            cx = 48 + i * 96 + (0 if row == 0 else 0)
            cv.alpha_composite(tint(im, rgb), (cx - im.width // 2, 56 + row * 64 - im.height))
    return cv


def export():
    PEND.mkdir(parents=True, exist_ok=True)
    md5 = {}
    for n, fn in ITEMS.items():
        im = fn()
        assert im.size == (16, 16), n
        im.save(PEND / f"{n}.png")
        md5[n] = hashlib.md5((PEND / f"{n}.png").read_bytes()).hexdigest()
    base_scene().save(REP / "cena_base_3_baus.png")
    ghost_scene().save(REP / "cena_fantasma.png")
    for n in ("icon_chest_small_A", "icon_chest_small_B", "icon_chest_small_C", "icon_chest_large_A",
              "icon_chest_large_B", "icon_chest_large_C"):
        hotbar(Image.open(PEND / f"{n}.png").convert("RGBA")).save(REP / f"hotbar_{n[11:]}.png")
    # chip: slot de UI com a silhueta e com o chip de verdade
    slot = load("ui_slot")
    sheet = Image.new("RGBA", (22 * 3 + 2, 24), (22, 17, 14, 255))
    for i, ic in enumerate([Image.open(PEND / "chip_slot_empty_A.png"), Image.open(PEND / "chip_slot_empty_B.png"), load("icon_chip")]):
        sheet.alpha_composite(slot, (2 + i * 22, 2)); sheet.alpha_composite(ic.convert("RGBA"), (4 + i * 22, 4))
    sheet.save(REP / "slot_chip.png")
    return md5


if __name__ == "__main__":
    for k, v in export().items():
        print(k, v)
