import { continueRender, delayRender, staticFile } from "remotion";
import tl from "./timeline.json";
import music from "./music.json";
import assets from "./assets.json";

// Fontes do jogo (game/fonts): Silkscreen pros rótulos, Pixelify Sans pros textos (bíblia §3)
export const LABEL_FONT = "Silkscreen";
export const BODY_FONT = "PixelifySans";
if (typeof document !== "undefined") {
  const handle = delayRender("fontes do jogo");
  Promise.all([
    new FontFace(LABEL_FONT, `url(${staticFile("fonts/Silkscreen-Regular.ttf")})`).load(),
    new FontFace(BODY_FONT, `url(${staticFile("fonts/PixelifySans.ttf")})`).load(),
  ])
    .then((faces) => {
      faces.forEach((f) => document.fonts.add(f));
      continueRender(handle);
    })
    .catch(() => continueRender(handle));
}

// Cores da UI do jogo (bíblia §3 + config.py)
export const C = {
  text: "#efe5da",
  muted: "#d9cfc4",
  accent: "#e2733a", // laranja das máquinas / traço do logo
  o2: "#59d0e6",
  gold: "#f2c46d",
  green: "#a6e07a",
  ice: "#a6ecff",
  red: "#ff6a55",
  ink: "#1b1630", // contorno
  panel: "rgba(16,12,22,.82)",
};

export const TL = tl;
export const MUSIC = music as { hits?: { t: number }[]; beats_heart?: number[]; placeholder?: boolean };
export const ASSETS = assets as { musicReal: boolean; cutscenes: { id: string; src: string; title: string | null }[]; clips: string[]; sfx?: string[] };
export const FPS = tl.fps;
export const f = (s: number) => Math.round(s * FPS);
