import React from "react";
import { Composition } from "remotion";
import { HesperTrailer } from "./HesperTrailer";
import { TL } from "./theme";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="HesperTrailer" component={HesperTrailer} durationInFrames={TL.duration * TL.fps} fps={TL.fps} width={1920} height={1080} />
    <Composition id="HesperTrailerVertical" component={HesperTrailer} durationInFrames={TL.duration * TL.fps} fps={TL.fps} width={1080} height={1920} />
  </>
);
