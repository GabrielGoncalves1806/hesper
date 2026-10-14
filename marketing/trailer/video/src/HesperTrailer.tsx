import React from "react";
import { AbsoluteFill, Audio, interpolate, Sequence, staticFile } from "remotion";
import { Caption, Flash, Grain, SoonTag } from "./fx";
import { Cutscene, Heartbeat, LogCard, Logo, Shot } from "./scenes";
import { ASSETS, f, TL } from "./theme";

// trilha a 1.0; nos SFX fortes ("duck") desce pra 0,65 por ~1 s
const ducks = TL.sfx.filter((s) => s.duck).map((s) => s.at);
const musicVolume = (frame: number) => {
  const t = frame / TL.fps;
  let v = 1;
  for (const d of ducks) v = Math.min(v, interpolate(t, [d - 0.08, d, d + 0.8, d + 1.1], [1, 0.65, 0.65, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  return v;
};

/**
 * Trailer do Hesper (90 s). Todo o roteiro mora no timeline.json (shots, cutscenes, legendas, LOGs, logo), cortado
 * nos marcadores da trilha do Som. Mesmo componente pro 16:9 e pro vertical 9:16 (layout pelo useVideoConfig).
 */
export const HesperTrailer: React.FC = () => (
  <AbsoluteFill style={{ background: "#000" }}>
    {TL.shots.map((s, i) => (
      <Sequence key={`s${i}`} from={f(s.at)} durationInFrames={f(s.dur)} premountFor={f(1)}>
        <Shot s={s} />
      </Sequence>
    ))}
    {TL.cutscenes.map((c, i) => (
      <Sequence key={`c${i}`} from={f(c.at)} durationInFrames={f(c.dur)} premountFor={f(1)}>
        <Cutscene id={c.id} slot={c.slot} dur={c.dur} label={c.label} quote={c.quote} quoteAt={c.quoteAt} at={c.at} from={c.from} suck={c.suck} vfit={c.vfit} vfocus={c.vfocus} />
      </Sequence>
    ))}
    {TL.logs.map((l, i) => (
      <Sequence key={`l${i}`} from={f(l.at)} durationInFrames={f(l.until - l.at)}>
        <LogCard label={l.label} text={l.text} punch={l.punch} dur={l.until - l.at} bg={l.bg} bgFrom={l.bgFrom} />
      </Sequence>
    ))}

    <Heartbeat from={75} to={84.85} />
    <Grain />

    {TL.shots.filter((s) => s.soon).map((s, i) => (
      <SoonTag key={`t${i}`} at={f(s.at)} until={f(s.soonUntil ?? s.at + s.dur)} />
    ))}
    {TL.captions.map((c, i) => (
      <Caption key={`k${i}`} text={c.text} kicker={c.kicker} at={f(c.at)} until={f(c.until)} center={c.center} />
    ))}

    {/* golpes de luz nos marcadores: o baque do pouso, o pulso, a abertura */}
    <Flash at={f(9.6)} dur={8} peak={0.35} color="#ffd9b0" />
    <Flash at={f(40)} dur={14} peak={0.5} />
    <Flash at={f(55)} dur={6} peak={0.25} color="#a6ecff" />

    <Sequence from={f(TL.logo.at)} durationInFrames={f(TL.duration - TL.logo.at)}>
      <Logo />
    </Sequence>
    <Flash at={f(TL.logo.at)} dur={10} peak={0.6} />

    <Audio src={staticFile("audio/trailer_music.wav")} volume={musicVolume} />
    {TL.sfx
      .filter((s) => (ASSETS.sfx ?? []).includes(s.file))
      .map((s, i) => (
        <Sequence key={`x${i}`} from={f(s.at)} durationInFrames={s.dur ? f(s.dur) : undefined}>
          <Audio src={staticFile(`sfx/${s.file}`)} volume={s.vol} loop={!!s.dur} />
        </Sequence>
      ))}
  </AbsoluteFill>
);
