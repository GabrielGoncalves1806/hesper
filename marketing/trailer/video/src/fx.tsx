import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { BODY_FONT, C, LABEL_FONT } from "./theme";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const easeOut = Easing.bezier(0.22, 1, 0.36, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);
/** Escala tipográfica: 1 no 1920×1080 e no 1080×1920. */
export const useUnit = () => {
  const { width, height } = useVideoConfig();
  return { u: Math.min(width, height) / 1080, vertical: height > width, width, height };
};
/** Quantiza em degraus (movimento "pixel art": anda de 4 em 4 px). */
export const snap = (v: number, step = 4) => Math.round(v / step) * step;

/** Grão de filme bem leve + vinheta. */
export const Grain: React.FC<{ amount?: number }> = ({ amount = 0.06 }) => {
  const frame = useCurrentFrame();
  return (
    <>
      <AbsoluteFill style={{ opacity: amount, mixBlendMode: "overlay", pointerEvents: "none" }}>
        <svg width="100%" height="100%">
          <filter id="grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={frame % 9} />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </AbsoluteFill>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,.55) 100%)" }} />
    </>
  );
};

/** Texto em que trechos entre *asteriscos* ganham a cor de destaque. */
export const Rich: React.FC<{ text: string; hi?: string; chars?: number }> = ({ text, hi = C.accent, chars }) => {
  let left = chars ?? Infinity;
  return (
    <>
      {text.split(/(\*[^*]+\*)/g).map((p, i) => {
        const strong = p.startsWith("*");
        let s = strong ? p.slice(1, -1) : p;
        const full = s;
        s = s.slice(0, Math.max(0, left));
        left -= full.length;
        return (
          <span key={i} style={{ color: strong ? hi : undefined }}>
            {s}
            <span style={{ opacity: 0 }}>{full.slice(s.length)}</span>
          </span>
        );
      })}
    </>
  );
};

/**
 * Legenda no estilo da UI do jogo (pílula B2: barra laranja à esquerda, rótulo em Silkscreen, texto em Pixelify).
 * `at`/`until` em frames absolutos da composição.
 */
export const Caption: React.FC<{ text: string; kicker?: string; at: number; until: number; center?: boolean }> = ({ text, kicker, at, until, center }) => {
  const frame = useCurrentFrame();
  const { u, vertical } = useUnit();
  if (frame < at || frame > until + 8) return null;
  const inP = interpolate(frame, [at, at + 8], [0, 1], { ...clamp, easing: easeOut });
  const outP = interpolate(frame, [until, until + 8], [0, 1], clamp);
  const plain = text.replace(/\*/g, "");
  const chars = Math.floor(interpolate(frame, [at + 2, at + 2 + plain.length * 0.9], [0, plain.length], clamp));
  const soon = kicker === "EM BREVE";
  const x = snap((1 - inP) * -60 * u);
  const pos: React.CSSProperties = center
    ? { left: 0, right: 0, top: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center" }
    : vertical
      ? { left: 70 * u, right: 70 * u, bottom: 420 * u }
      : { left: 110 * u, bottom: 120 * u };
  return (
    <div style={{ position: "absolute", ...pos, opacity: (1 - outP) * Math.min(1, inP * 1.4), transform: `translateX(${x}px)` }}>
      <div
        style={{
          display: "inline-flex",
          alignItems: "stretch",
          background: center ? "transparent" : C.panel,
          boxShadow: center ? "none" : `${8 * u}px ${8 * u}px 0 rgba(0,0,0,.45)`,
          imageRendering: "pixelated",
        }}
      >
        {!center && <div style={{ width: 10 * u, background: soon ? C.ice : C.accent }} />}
        <div style={{ padding: center ? 0 : `${20 * u}px ${34 * u}px ${22 * u}px ${28 * u}px`, textAlign: center ? "center" : "left" }}>
          {kicker && (
            <div style={{ fontFamily: LABEL_FONT, fontSize: 30 * u, letterSpacing: 4 * u, color: soon ? C.ice : C.accent, marginBottom: 8 * u }}>
              {kicker}
            </div>
          )}
          <div
            style={{
              fontFamily: BODY_FONT,
              fontSize: (center ? 78 : 60) * u,
              lineHeight: 1.1,
              color: C.text,
              textShadow: `${4 * u}px ${4 * u}px 0 rgba(0,0,0,.6)`,
              whiteSpace: vertical ? "normal" : "nowrap",
            }}
          >
            <Rich text={text} chars={chars} hi={soon ? C.ice : C.accent} />
          </div>
        </div>
      </div>
    </div>
  );
};

/** Selo "EM BREVE" no canto (o que ainda não está no jogo). */
export const SoonTag: React.FC<{ at: number; until: number }> = ({ at, until }) => {
  const frame = useCurrentFrame();
  const { u } = useUnit();
  if (frame < at || frame > until) return null;
  const blink = Math.floor((frame - at) / 15) % 2 === 0 ? 1 : 0.55;
  const o = interpolate(frame, [at, at + 6, until - 6, until], [0, 1, 1, 0], clamp);
  return (
    <div
      style={{
        position: "absolute",
        top: 70 * u,
        right: 80 * u,
        padding: `${12 * u}px ${22 * u}px`,
        border: `${4 * u}px solid ${C.ice}`,
        background: "rgba(10,18,28,.75)",
        fontFamily: LABEL_FONT,
        fontSize: 30 * u,
        letterSpacing: 4 * u,
        color: C.ice,
        opacity: o,
      }}
    >
      <span style={{ opacity: blink }}>■</span> EM BREVE
    </div>
  );
};

/** Flash curto (branco por padrão). */
export const Flash: React.FC<{ at: number; dur?: number; peak?: number; color?: string }> = ({ at, dur = 10, peak = 0.8, color = "#fff" }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [at - 1, at, at + dur], [0, peak, 0], clamp);
  if (o <= 0) return null;
  return <AbsoluteFill style={{ background: color, opacity: o }} />;
};
