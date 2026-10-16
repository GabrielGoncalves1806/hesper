import sys
from PIL import Image
# uso: v07_zoom.py saida.png fator arquivo1 arquivo2 ...
out, k = sys.argv[1], int(sys.argv[2])
ims = [Image.open(f).convert("RGBA") for f in sys.argv[3:]]
W = sum(i.width * k + 8 for i in ims) + 8
H = max(i.height * k for i in ims) + 16
bg = Image.new("RGBA", (W, H), (120, 100, 90, 255))
x = 8
for i in ims:
    bg.alpha_composite(i.resize((i.width * k, i.height * k), Image.NEAREST), (x, 8)); x += i.width * k + 8
bg.save(out)
