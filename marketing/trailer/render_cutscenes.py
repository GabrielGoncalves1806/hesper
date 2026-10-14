"""Monta as cutscenes da Dra. Ilves a partir das camadas da Designer (art/cenas.json) e grava um MP4 por cena em
video/public/art/<id>.mp4 (1920×1080, 30 fps, nearest-neighbor, sem suavizar).

    python3 marketing/trailer/render_cutscenes.py            # todas
    python3 marketing/trailer/render_cutscenes.py cena5 cena6

Lê do cenas.json: canvas 512×288, janela visível (16, 9, 480, 270), camadas em ordem com x/y, tiras de quadros
(frames/fps/loop), parallax e "move". A câmera de cada cena (pan, zoom e âncora) segue o texto "motion" da Designer e
fica na tabela CAMERA abaixo. Tudo em px inteiros do canvas, como pede o formato (pixel art não borra).
Precisa só de Pillow + ffmpeg. O sync-assets.mjs chama este script quando o cenas.json tem camadas.
"""

import json
import math
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ART = HERE / "art"
OUT = HERE / "video" / "public" / "art"
FPS = 30
W, H = 1920, 1080


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def ease_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


# Câmera por cena (do "motion" de cada uma): pan(t) em px do canvas (multiplicado pelo parallax de cada camada) e
# zoom(t) com a âncora em px do canvas. t vai de 0 a 1 na duração da cena.
CAMERA = {
    # v1.2: no plano geral ela ficou pequena -> zoom até ×2 inteiro (e segura) ancorado nela
    "cena1": {"pan": lambda t: round(12 * (1 - ease_out(t / 0.8))), "zoom": lambda t: 1 + ease(t / 0.8), "anchor": (248, 229)},
    "cena1_susto": {"zoom": lambda t: 2.0, "anchor": (248, 229)},                            # já no ×2: ela levanta a cabeça
    "cena1b": {},                                                                            # meia resolução (×8), parada
    "cena1b_reacao": {},
    "cena2": {"pan": lambda t: round(-20 * t)},                                              # o campo deriva ~12 px (×0,6)
    "cena3": {"zoom": lambda t: 1 + ease(t / 0.45), "anchor": (302, 223)},                    # até ×2 na Ilves e segura
    "cena3b": {"zoom": lambda t: 1 + 0.5 * ease(t / 0.66), "anchor": (161, 89)},              # 1,0 -> 1,5 no painel, segura 1 s
    "cena4": {"pan": lambda t: round(-14 * ease(t))},                                        # pan lento pra direita
    "cena5": {"zoom": lambda t: 1 + 0.28 * ease(t), "anchor": (150, 122)},                    # até a tela
    "cena6": {"zoom": lambda t: 1 + 0.15 * ease(t), "anchor": (272, 152)},                    # na criatura
    "cena6b": {"zoom": lambda t: 1 + 0.10 * ease(t), "anchor": (256, 144)},
}
# cena5: quando cada linha do terminal começa a ser digitada (s) e quantas letras por segundo; a última entra depois
# de uma pausa (a deixa "Não acorde o gelo." cai no fim do take do trailer)
TYPE_START = {"linha_00": 0.4, "linha_02": 1.6, "linha_03": 2.3, "linha_04": 3.9, "linha_05": 5.4,
              "linha_07": 6.4, "linha_08": 7.3, "linha_10": 8.6}
TYPE_CPS = 24


def load(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def strip_frame(layer: dict, img: Image.Image, t: float, dur: float, scene: str) -> Image.Image:
    n, fps = layer.get("frames", 1) or 1, layer.get("fps", 0) or 0
    w, h = layer["w"], layer["h"]
    if n <= 1:
        return img.crop((0, 0, w, h))
    k = int(t * fps)
    name = layer["name"]
    if scene == "cena2" and name == "forma_escura":          # q. 0..7 em loop; no fim PARA (q. 8..9)
        k = 8 + min(1, int((t - (dur - 0.7)) * 3)) if t > dur - 0.7 else k % 8
    elif scene == "cena6b" and name == "criatura":           # quase não mexe; no último quadro se contrai (q. 7)
        k = 7 if t > dur - 0.5 else k % 7
    elif layer.get("loop", True):
        k %= n
    else:
        k = min(n - 1, k)
    return img.crop((k * w, 0, k * w + w, h))


def move_offset(layer: dict, t: float) -> tuple[int, int]:
    """"anda pra esquerda ~8 px/s" / "anda pra direita ~6 px/s" → deslocamento em px inteiros."""
    m = layer.get("move") or ""
    speed = re.search(r"~?(\d+(?:[.,]\d+)?)\s*px/s", m)
    if not speed:
        return 0, 0
    v = float(speed.group(1).replace(",", "."))
    sign = -1 if "esquerda" in m else 1
    return round(sign * v * t), 0


def compose(scene: dict, t: float, dur: float, cache: dict) -> Image.Image:
    cw, ch = scene.get("canvas", [512, 288])
    vx, vy, vw, vh = scene.get("visible", [16, 9, 480, 270])
    cam = CAMERA.get(scene["id"], {})
    u = t / dur
    pan = cam["pan"](u) if "pan" in cam else 0
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 255))
    for layer in scene["layers"]:
        img = cache.setdefault(layer["file"], load(ART / layer["file"]))
        frame = strip_frame(layer, img, t, dur, scene["id"])
        if "mirror" in (layer.get("move") or "") or "espelhar" in (layer.get("move") or ""):
            frame = frame.transpose(Image.FLIP_LEFT_RIGHT)
        mx, my = move_offset(layer, t)
        x = layer["x"] + mx + round(pan * layer.get("parallax", 1.0))
        y = layer["y"] + my
        typ = layer.get("type")
        if typ:                                               # terminal: a linha aparece letra por letra
            start = TYPE_START.get(layer["name"], 0.0)
            chars = int((t - start) * TYPE_CPS)
            if chars <= 0:
                continue
            xs = typ["char_x"]
            cut = xs[min(chars, len(xs)) - 1] + 1
            frame = frame.crop((0, 0, min(frame.width, cut), frame.height))
        if layer["name"] == "cursor":                          # cursor no fim da linha sendo digitada
            cur = None
            for ln in scene["layers"]:
                tp = ln.get("type")
                if tp and t >= TYPE_START.get(ln["name"], 0):
                    chars = min(len(tp["char_x"]), int((t - TYPE_START[ln["name"]]) * TYPE_CPS))
                    cur = (ln["x"] + tp["char_x"][max(0, chars - 1)] + 2, ln["y"] + 1)
            if cur is None:
                continue
            x, y = cur
        canvas.alpha_composite(frame, (x, y)) if x >= 0 and y >= 0 else canvas.paste(frame, (x, y), frame)
    # janela visível + zoom ancorado (recorte em px inteiros, escala nearest pro 1920×1080)
    z = cam["zoom"](u) if "zoom" in cam else 1.0
    ax, ay = cam.get("anchor", (vx + vw / 2, vy + vh / 2))
    w, h = vw / z, vh / z
    left = vx + (ax - vx) * (1 - 1 / z)
    top = vy + (ay - vy) * (1 - 1 / z)
    left = round(max(vx, min(vx + vw - w, left)))
    top = round(max(vy, min(vy + vh - h, top)))
    view = canvas.crop((left, top, left + round(w), top + round(h)))
    return view.convert("RGB").resize((W, H), Image.NEAREST)


def render(scene: dict) -> None:
    dur = float(re.sub(r"[^\d.,]", "", str(scene.get("duration", "6"))).replace(",", ".") or 6)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{scene['id']}.mp4"
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16", "-preset", "medium",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    cache: dict = {}
    n = round(dur * FPS)
    for i in range(n):
        proc.stdin.write(compose(scene, i / FPS, dur, cache).tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"  {scene['id']}: {n} quadros ({dur:g} s) -> {out.relative_to(HERE)}")


def variant_id(scene_id: str, alt: dict) -> str:
    """Camada alternativa ("replaces"): vira a cena <id>_<sufixo do nome> (ilves_reacao -> cena1b_reacao)."""
    return f"{scene_id}_{alt['name'].split('_')[-1]}"


def expand(scene: dict) -> list[dict]:
    """A cena base (sem as camadas alternativas) e uma variante por camada com "replaces": a alternativa entra no
    lugar da camada que ela substitui (na ordem draw_at_order). A câmera da variante é a mesma da base."""
    alts = [l for l in scene["layers"] if l.get("replaces")]
    base = dict(scene, layers=[l for l in scene["layers"] if not l.get("replaces")])
    out = [base]
    for alt in alts:
        layers = [alt if l["name"] == alt["replaces"] else l for l in base["layers"]]
        vid = variant_id(scene["id"], alt)
        CAMERA.setdefault(vid, CAMERA.get(scene["id"], {}))
        out.append(dict(scene, id=vid, layers=layers))
    return out


def main(names: list[str]) -> None:
    data = json.loads((ART / "cenas.json").read_text())
    scenes = {}
    for sc in data["scenes"]:
        for v in expand(sc):
            scenes[v["id"]] = v
    order = []
    for sid in data.get("order") or [sc["id"] for sc in data["scenes"]]:
        order += [k for k in scenes if k == sid or k.startswith(sid + "_")]
    for sid in names or order:
        if sid in scenes and scenes[sid].get("layers"):
            render(scenes[sid])


if __name__ == "__main__":
    main(sys.argv[1:])
