import React from "react";
import { AbsoluteFill, interpolate, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ASSETS, BODY_FONT, C, f, LABEL_FONT, MUSIC, TL } from "./theme";
import { clamp, easeInOut, easeOut, Rich, snap, useUnit } from "./fx";

const PIXEL: React.CSSProperties = { imageRendering: "pixelated" };

/** Vídeo de tela cheia sem suavizar. No vertical, recorta (cover) em volta de `focus` (0..1 na horizontal). */
const PixelVideo: React.FC<{ src: string; startFrom?: number; rate?: number; scale?: number; focus?: number; filter?: string; vfit?: number }> = ({
  src,
  startFrom = 0,
  rate = 1,
  scale = 1,
  focus = 0.5,
  filter,
  vfit,
}) => {
  const { width, height } = useVideoConfig();
  // cover; no vertical, `vfit` troca o cover por uma escala menor (mostra mais da largura, sobra preto em cima/embaixo)
  const k = (height > width && vfit ? vfit : Math.max(width / 1920, height / 1080)) * scale;
  const w = 1920 * k;
  const h = 1080 * k;
  const left = (width - w) * focus;
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000" }}>
      <OffthreadVideo
        src={staticFile(src)}
        startFrom={Math.round(startFrom * TL.fps)}
        playbackRate={rate}
        muted
        style={{ ...PIXEL, position: "absolute", width: w, height: h, left, top: (height - h) / 2, maxWidth: "none", filter }}
      />
    </AbsoluteFill>
  );
};

/** Placeholder de clipe que ainda não foi capturado (rode capture.py). */
const Missing: React.FC<{ label: string }> = ({ label }) => {
  const { u } = useUnit();
  return (
    <AbsoluteFill style={{ background: "repeating-linear-gradient(45deg,#1a1420 0 40px,#221a2a 40px 80px)", alignItems: "center", justifyContent: "center" }}>
      <div style={{ fontFamily: LABEL_FONT, color: C.accent, fontSize: 40 * u }}>CLIPE PENDENTE · {label}</div>
    </AbsoluteFill>
  );
};

type ShotT = { clip: string; at: number; dur: number; from?: number; rate?: number; zoom?: number[]; in?: number; out?: number; focus?: number; suck?: number[] };

/** Um take do gameplay: corte seco (ou fade do/pro preto), Ken Burns leve por cima. Frame relativo à Sequence. */
export const Shot: React.FC<{ s: ShotT }> = ({ s }) => {
  const frame = useCurrentFrame();
  const t = frame / TL.fps;
  const z = s.zoom ?? [1, 1];
  let scale = interpolate(t, [0, s.dur], [z[0], z[1]], clamp);
  let filter: string | undefined;
  let black = 0;
  if (s.in) black = Math.max(black, interpolate(t, [0, s.in], [1, 0], clamp));
  if (s.out) black = Math.max(black, interpolate(t, [s.dur - s.out, s.dur], [0, 1], clamp));
  if (s.suck) {
    // a sugada da trilha: a câmera mergulha no gelo e tudo apaga antes do silêncio
    const p = interpolate(t + s.at, [s.suck[0], s.suck[1]], [0, 1], { ...clamp, easing: (x) => x * x * x });
    scale *= 1 + p * 2.2;
    filter = `brightness(${1 - p * 0.85}) contrast(${1 + p})`;
    black = Math.max(black, interpolate(t + s.at, [s.suck[1] - 0.12, s.suck[1]], [0, 1], clamp));
  }
  const has = ASSETS.clips.includes(s.clip);
  return (
    <AbsoluteFill>
      {has ? <PixelVideo src={`clips/${s.clip}.mp4`} startFrom={s.from ?? 0} rate={s.rate ?? 1} scale={scale} focus={s.focus} filter={filter} /> : <Missing label={s.clip} />}
      {black > 0 && <AbsoluteFill style={{ background: "#000", opacity: black }} />}
    </AbsoluteFill>
  );
};

/** Cutscene da Dra. Ilves (Designer). Sem o arquivo, um placeholder com o mesmo enquadramento. */
export const Cutscene: React.FC<{ id?: string; slot: number; dur: number; label?: string; quote?: string; quoteAt?: number; at: number; from?: number; suck?: number[]; vfit?: number; vfocus?: number }> = ({
  id,
  slot,
  dur,
  label,
  quote,
  quoteAt,
  at,
  from = 0,
  suck,
  vfit,
  vfocus,
}) => {
  const frame = useCurrentFrame();
  const { u, vertical } = useUnit();
  const t = frame / TL.fps;
  const cs = ASSETS.cutscenes.find((c) => c.id === id) ?? ASSETS.cutscenes[slot];
  // a câmera da cena já vem no vídeo (render_cutscenes.py); aqui só um empurrão bem leve
  let scale = interpolate(t, [0, dur], [1.0, 1.02], { ...clamp, easing: easeInOut });
  let fade = interpolate(t, [0, 0.1, dur - 0.06, dur], [0, 1, 1, 0.0], clamp);
  let filter: string | undefined;
  if (suck) {
    const p = interpolate(t + at, [suck[0], suck[1]], [0, 1], { ...clamp, easing: (x) => x * x * x });
    scale *= 1 + p * 2.2;
    filter = `brightness(${1 - p * 0.85}) contrast(${1 + p})`;
    fade = Math.min(fade, interpolate(t + at, [suck[1] - 0.12, suck[1]], [1, 0], clamp));
  }
  const qt = quoteAt !== undefined ? t + at - quoteAt : -1;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <AbsoluteFill style={{ opacity: fade }}>
        {cs ? (
          <PixelVideo src={cs.src} startFrom={from} scale={scale} focus={vfocus ?? 0.55} filter={filter} vfit={vfit} />
        ) : (
          <AbsoluteFill style={{ background: "linear-gradient(180deg,#0d1424,#1b2440 60%,#0b0f1a)", alignItems: "center", justifyContent: "center" }}>
            <div style={{ fontFamily: LABEL_FONT, color: C.o2, fontSize: 36 * u, opacity: 0.7 }}>CUTSCENE {slot + 1} · DRA. ILVES (placeholder)</div>
          </AbsoluteFill>
        )}
        {/* faixas de cinema */}
        {!vertical && (
          <>
            <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: 90 * u, background: "#000" }} />
            <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 90 * u, background: "#000" }} />
          </>
        )}
      </AbsoluteFill>
      {label && (
        <div style={{ position: "absolute", left: 110 * u, ...(vertical ? { top: 260 * u } : { bottom: 30 * u }), fontFamily: LABEL_FONT, fontSize: 28 * u, letterSpacing: 4 * u, color: C.o2, opacity: interpolate(t, [0.3, 0.6], [0, 0.9], clamp) * fade }}>
          {label}
        </div>
      )}
      {quote && qt >= 0 && (
        <div
          style={{
            position: "absolute",
            left: 60 * u,
            right: 60 * u,
            bottom: (vertical ? 420 : 14) * u,
            textAlign: "center",
            fontFamily: BODY_FONT,
            fontSize: 56 * u,
            color: C.text,
            textShadow: `${4 * u}px ${4 * u}px 0 #000`,
            opacity: interpolate(qt, [0, 0.4], [0, 1], clamp) * fade,
          }}
        >
          <Rich text={quote} chars={Math.floor(qt * 30)} />
        </div>
      )}
    </AbsoluteFill>
  );
};

/** Cartela de LOG: o terminal do jogo (texto datilografado, cursor) e a frase de impacto embaixo. */
export const LogCard: React.FC<{ label: string; text: string; punch: string; dur: number; bg?: string; bgFrom?: number }> = ({ label, text, punch, dur, bg, bgFrom = 0 }) => {
  const frame = useCurrentFrame();
  const { u, vertical } = useUnit();
  const t = frame / TL.fps;
  const chars = Math.floor(interpolate(t, [0.25, 0.25 + text.length / 42], [0, text.length], clamp));
  const punchT = Math.min(dur - 2.2, 0.4 + text.length / 42 + 0.3);
  const pc = Math.floor(interpolate(t, [punchT, punchT + punch.length / 26], [0, punch.length], clamp));
  const cursor = Math.floor(frame / 8) % 2 === 0;
  const fadeOut = interpolate(t, [dur - 0.25, dur], [1, 0], clamp);
  const shake = t < 0.3 ? snap(Math.sin(frame * 3) * 6 * (1 - t / 0.3) * u, 2) : 0; // o estalo do gelo
  return (
    <AbsoluteFill style={{ background: "#05070b", opacity: fadeOut }}>
      {bg && ASSETS.cutscenes.some((c) => c.id === bg) && (
        <AbsoluteFill style={{ opacity: 0.32 }}>
          <PixelVideo src={`art/${bg}.mp4`} startFrom={bgFrom} scale={interpolate(t, [0, dur], [1, 1.03], clamp)} />
        </AbsoluteFill>
      )}
      {/* scanlines + brilho frio */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, rgba(89,208,230,.10), transparent 65%)" }} />
      <AbsoluteFill style={{ backgroundImage: "repeating-linear-gradient(0deg, rgba(255,255,255,.035) 0 2px, transparent 2px 6px)" }} />
      <div
        style={{
          position: "absolute",
          left: (vertical ? 70 : 260) * u,
          right: (vertical ? 70 : 260) * u,
          top: "50%",
          transform: `translate(${shake}px, -50%)`,
        }}
      >
        <div style={{ fontFamily: LABEL_FONT, fontSize: 32 * u, letterSpacing: 4 * u, color: C.accent, marginBottom: 26 * u }}>
          ▸ {label}
        </div>
        <div style={{ fontFamily: BODY_FONT, fontSize: 50 * u, lineHeight: 1.3, color: C.muted }}>
          {text.slice(0, chars)}
          <span style={{ opacity: 0 }}>{text.slice(chars)}</span>
          {chars < text.length && cursor && <span style={{ color: C.o2 }}>█</span>}
        </div>
        <div style={{ height: 50 * u }} />
        <div style={{ fontFamily: BODY_FONT, fontSize: 76 * u, lineHeight: 1.1, color: C.text, textShadow: `0 0 ${24 * u}px rgba(166,236,255,.35)` }}>
          {punch.slice(0, pc)}
          <span style={{ opacity: 0 }}>{punch.slice(pc)}</span>
          {pc > 0 && pc < punch.length && cursor && <span style={{ color: C.o2 }}>█</span>}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Pulsos do coração (beats_heart da trilha): vinheta fria que aperta a cada batida. Frames absolutos. */
export const Heartbeat: React.FC<{ from: number; to: number }> = ({ from, to }) => {
  const frame = useCurrentFrame();
  const t = frame / TL.fps;
  if (t < from || t > to) return null;
  const beats = MUSIC.beats_heart ?? [];
  let p = 0;
  for (const b of beats) p = Math.max(p, interpolate(t, [b - 0.02, b + 0.05, b + 0.6], [0, 1, 0], clamp));
  return <AbsoluteFill style={{ pointerEvents: "none", background: `radial-gradient(ellipse at center, transparent ${48 - p * 10}%, rgba(6,14,26,${0.55 + p * 0.3}) 100%)` }} />;
};

/** Logo final: HESPER em Silkscreen com letras espaçadas, sombra e o traço laranja (como na tela de título). */
export const Logo: React.FC = () => {
  const frame = useCurrentFrame();
  const { u, vertical } = useUnit();
  const t = frame / TL.fps;
  const letters = "HESPER".split("");
  const line = interpolate(t, [0.5, 1.1], [0, 1], { ...clamp, easing: easeOut });
  const tag = interpolate(t, [1.2, 1.8], [0, 1], clamp);
  const status = interpolate(t, [2.0, 2.6], [0, 1], clamp);
  const out = interpolate(t, [4.4, 5], [1, 0], clamp);
  const size = (vertical ? 190 : 230) * u;
  return (
    <AbsoluteFill style={{ background: "#000", alignItems: "center", justifyContent: "center", opacity: out }}>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 55%, rgba(226,115,58,.10), transparent 60%)" }} />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 18 * u }}>
          {letters.map((ch, i) => {
            const on = t > 0.04 + i * 0.05;
            return (
              <span
                key={i}
                style={{
                  fontFamily: LABEL_FONT,
                  fontSize: size,
                  lineHeight: 1,
                  color: C.text,
                  opacity: on ? 1 : 0,
                  textShadow: `${10 * u}px ${10 * u}px 0 rgba(0,0,0,.67)`,
                }}
              >
                {ch}
              </span>
            );
          })}
        </div>
        <div style={{ width: 320 * u * line, height: 8 * u, background: C.accent, marginTop: 14 * u }} />
        <div style={{ fontFamily: BODY_FONT, fontSize: 56 * u, color: C.muted, marginTop: 34 * u, opacity: tag }}>Planeta sem ar. Por enquanto.</div>
        <div style={{ fontFamily: LABEL_FONT, fontSize: 28 * u, letterSpacing: 6 * u, color: C.accent, marginTop: 60 * u, opacity: status * 0.9 }}>
          {TL.logo.status.toUpperCase()}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const sec = (s: number) => f(s);
