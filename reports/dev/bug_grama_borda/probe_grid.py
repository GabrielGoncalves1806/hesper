from common import *  # noqa
bot = setup()
w = bot.state.world
sym = {5: "#", 7: ".", 8: "o", 9: "~", 10: "x", 14: "F", 12: "W", 13: "C", 15: "K", 1: "r", 2: "i", 3: "s", 4: "I", 6: "T", 0: " "}
print("tiles x 140..200 (cada char = 1 tile), y 244..255; # = BEDROCK, . = SAND")
for y in range(244, 256):
    print(f"{y:3d} " + "".join(sym.get(w.get(x, y), "?") for x in range(140, 200)))
print("coluna(s) com BEDROCK no fundo, x=0..255 (espessura do fundo):")
th = []
for x in range(256):
    t = 0
    for y in range(255, 200, -1):
        if w.get(x, y) == 5: t += 1
        else: break
    th.append(t)
from collections import Counter
print(Counter(th))
