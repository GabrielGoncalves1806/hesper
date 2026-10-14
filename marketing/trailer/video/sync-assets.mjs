// Junta tudo que o vídeo usa em public/ e escreve src/assets.json (o que é real e o que é placeholder).
// Roda sozinho antes de cada render (npm run render). Trocar placeholder por arquivo de verdade = só re-renderizar.
//
//   ../audio/trailer_music.wav + .json  (Som)      -> public/audio/trailer_music.wav, src/music.json
//   ../art/cenas.json + cutscenes       (Designer) -> public/art/<id>.mp4 (1920×1080, nearest-neighbor, em loop)
//   ../frames -> public/clips/*.mp4     (capture.py já grava os clipes direto em public/clips)
//   game/fonts                          -> public/fonts
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const TRAILER = path.resolve(HERE, "..");
const ROOT = path.resolve(TRAILER, "../..");
const PUB = path.join(HERE, "public");
const SRC = path.join(HERE, "src");
const ff = (...args) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...args], { stdio: "inherit" });
const newer = (a, b) => !fs.existsSync(b) || fs.statSync(a).mtimeMs > fs.statSync(b).mtimeMs;
for (const d of ["audio", "art", "fonts", "clips"]) fs.mkdirSync(path.join(PUB, d), { recursive: true });

// ---- fontes do jogo ----
for (const f of ["Silkscreen-Regular.ttf", "PixelifySans.ttf"]) {
  fs.copyFileSync(path.join(ROOT, "game/fonts", f), path.join(PUB, "fonts", f));
}

// ---- trilha (Som) ----
const DEFAULT_MUSIC = {
  placeholder: true, duration: 90, bpm: 120,
  hits: [9.6, 12, 40, 55, 59, 65, 71, 85].map((t) => ({ t, kind: "hit" })),
  beats_heart: [75.7, 77.0, 78.27, 79.512, 80.725, 81.91, 83.069],
};
const wav = path.join(TRAILER, "audio/trailer_music.wav");
const wavOut = path.join(PUB, "audio/trailer_music.wav");
let musicReal = false;
if (fs.existsSync(wav)) {
  if (newer(wav, wavOut)) fs.copyFileSync(wav, wavOut);
  musicReal = true;
} else if (!fs.existsSync(wavOut)) {
  ff("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "90", wavOut); // placeholder: 90 s de silêncio
}
const mj = path.join(TRAILER, "audio/trailer_music.json");
const music = fs.existsSync(mj) ? JSON.parse(fs.readFileSync(mj, "utf8")) : DEFAULT_MUSIC;
fs.writeFileSync(path.join(SRC, "music.json"), JSON.stringify(music, null, 1));

// ---- SFX do jogo (Som): audio/sfx -> public/sfx ----
const SFX = path.join(TRAILER, "audio/sfx");
fs.mkdirSync(path.join(PUB, "sfx"), { recursive: true });
const sfx = fs.existsSync(SFX) ? fs.readdirSync(SFX).filter((f) => f.endsWith(".wav")) : [];
for (const f of sfx) if (newer(path.join(SFX, f), path.join(PUB, "sfx", f))) fs.copyFileSync(path.join(SFX, f), path.join(PUB, "sfx", f));

// ---- cutscenes da Dra. Ilves (Designer) ----
// Aceita: art/cenas.json com uma lista (na raiz ou em "cenas"/"scenes") de {id, video|mp4|gif|preview|png|file}.
// Sem o json: cada art/<id>.mp4 e cada art/preview/<id>.gif, em ordem alfabética.
const ART = path.join(TRAILER, "art");
const found = [];
const pickFile = (entry) => {
  for (const k of ["video", "mp4", "gif", "preview", "anim", "png", "still", "file", "image"]) {
    const v = entry[k];
    if (typeof v === "string") {
      for (const base of [ART, path.join(ART, "preview"), path.join(ART, entry.id ?? "")]) {
        const p = path.join(base, v);
        if (fs.existsSync(p)) return p;
      }
    }
  }
  for (const ext of [".mp4", ".gif", ".png"]) {
    for (const base of [ART, path.join(ART, "preview")]) {
      const p = path.join(base, (entry.id ?? "") + ext);
      if (fs.existsSync(p)) return p;
    }
  }
  return null;
};
const cj = path.join(ART, "cenas.json");
const layered = []; // cenas em camadas (formato da Designer): montadas pelo render_cutscenes.py
if (fs.existsSync(cj)) {
  const raw = JSON.parse(fs.readFileSync(cj, "utf8"));
  for (const sc of raw.scenes ?? []) if (Array.isArray(sc.layers) && sc.layers.length) layered.push(sc);
}
if (layered.length) {
  // refaz só se o cenas.json, as camadas ou o script forem mais novos que o MP4 de alguma cena
  const script = path.join(TRAILER, "render_cutscenes.py");
  const stale = layered.filter((sc) => {
    const out = path.join(PUB, "art", `${sc.id}.mp4`);
    return [cj, script, ...sc.layers.map((l) => path.join(ART, l.file))].some((src) => fs.existsSync(src) && newer(src, out));
  });
  // camada com "replaces" = variante da cena (ex.: cena1b_reacao), montada junto pelo render_cutscenes.py
  const ids = (sc) => [sc.id, ...sc.layers.filter((l) => l.replaces).map((l) => `${sc.id}_${l.name.split("_").pop()}`)];
  const missing = layered.filter((sc) => ids(sc).some((id) => !fs.existsSync(path.join(PUB, "art", `${id}.mp4`))));
  const todo = [...new Set([...stale, ...missing])].flatMap(ids);
  if (todo.length) execFileSync("python3", [script, ...todo], { stdio: "inherit" });
  for (const sc of layered) for (const id of ids(sc)) found.push({ id, file: null, title: sc.title ?? null });
} else if (fs.existsSync(cj)) {
  const raw = JSON.parse(fs.readFileSync(cj, "utf8"));
  const list = Array.isArray(raw) ? raw : raw.cenas ?? raw.scenes ?? Object.entries(raw).map(([id, v]) => ({ id, ...(typeof v === "object" ? v : { file: v }) }));
  for (const e of list) {
    const file = pickFile(e);
    if (file) found.push({ id: String(e.id ?? path.parse(file).name), file, title: e.title ?? e.titulo ?? null });
  }
}
if (!found.length && fs.existsSync(ART)) {
  const vids = fs.readdirSync(ART).filter((f) => f.endsWith(".mp4")).sort();
  for (const f of vids) found.push({ id: path.parse(f).name, file: path.join(ART, f) });
  const prev = path.join(ART, "preview");
  if (!vids.length && fs.existsSync(prev)) {
    for (const f of fs.readdirSync(prev).filter((f) => f.endsWith(".gif")).sort()) found.push({ id: path.parse(f).name, file: path.join(prev, f) });
  }
}
const cutscenes = [];
for (const c of found) {
  const out = path.join(PUB, "art", `${c.id}.mp4`);
  if (c.file && newer(c.file, out)) {
    const still = c.file.endsWith(".png");
    ff(
      ...(still ? ["-loop", "1", "-t", "10"] : ["-stream_loop", "-1", "-t", "10"]),
      "-i", c.file,
      "-vf", "scale=1920:1080:flags=neighbor:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
      "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", out,
    );
  }
  cutscenes.push({ id: c.id, src: `art/${c.id}.mp4`, title: c.title ?? null });
}

// ---- clipes do gameplay (capture.py) ----
const clips = fs.readdirSync(path.join(PUB, "clips")).filter((f) => f.endsWith(".mp4")).map((f) => path.parse(f).name);

const assets = { musicReal, musicPlaceholder: !!music.placeholder, cutscenes, clips, sfx };
fs.writeFileSync(path.join(SRC, "assets.json"), JSON.stringify(assets, null, 1));
console.log(`assets: trilha ${musicReal ? "real" : "PLACEHOLDER"} · ${cutscenes.length} cutscene(s) ${cutscenes.map((c) => c.id).join(", ") || "(placeholder)"} · ${clips.length} clipes`);
