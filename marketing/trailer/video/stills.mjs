// Stills dos momentos principais pro dono ver rápido: node stills.mjs [segundos...]
// Saída: ../stills/<nn>_<segundo>s.png (1920×1080)
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";

const DEFAULT = [9.8, 19.5, 24.6, 28.5, 42.5, 52, 58.6, 60.2, 64.6, 70.8, 74.6, 81.5, 87.5];
const secs = process.argv.length > 2 ? process.argv.slice(2).map(Number) : DEFAULT;
const out = path.resolve("../stills");
fs.mkdirSync(out, { recursive: true });
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const composition = await selectComposition({ serveUrl, id: "HesperTrailer" });
let i = 0;
for (const s of secs) {
  const name = `${String(++i).padStart(2, "0")}_${String(s).replace(".", "_")}s.png`;
  await renderStill({ serveUrl, composition, frame: Math.round(s * 30), output: path.join(out, name) });
  console.log("still", name);
}
