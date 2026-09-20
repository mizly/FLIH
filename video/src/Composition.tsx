import {
  AbsoluteFill,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Audio } from "@remotion/media";
import { TransitionSeries } from "@remotion/transitions";
import { loadFont } from "@remotion/fonts";
import { Intro } from "./scenes/Intro";
import { Route } from "./scenes/Route";
import { Queue } from "./scenes/Queue";
import { Drive } from "./scenes/Drive";
import { Sense } from "./scenes/Sense";
import { Outro } from "./scenes/Outro";
import { BEAT, INK, RED } from "./design";
loadFont({
  family: "Kalam",
  url: staticFile("fonts/kalam-latin-700-normal.woff2"),
  weight: "700",
});
loadFont({
  family: "Patrick Hand",
  url: staticFile("fonts/patrick-hand-latin-400-normal.woff2"),
});
export const FlihVideo = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{ background: INK, fontFamily: "Patrick Hand", color: INK }}
    >
      <Audio
        src={staticFile("soundtrack.mp3")}
        volume={(frame) =>
          interpolate(frame, [0, 3, 438, 449], [0, 0.9, 0.9, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        }
      />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={75} name="Meet FLIH">
          <Intro />
        </TransitionSeries.Sequence>
        <TransitionSeries.Sequence durationInFrames={76} name="Plan a route">
          <Route />
        </TransitionSeries.Sequence>
        <TransitionSeries.Sequence durationInFrames={75} name="Join the queue">
          <Queue />
        </TransitionSeries.Sequence>
        <TransitionSeries.Sequence
          durationInFrames={76}
          name="Controlled by a real fly brain"
        >
          <Drive />
        </TransitionSeries.Sequence>
        <TransitionSeries.Sequence durationInFrames={75} name="FLIH CAM">
          <Sense />
        </TransitionSeries.Sequence>
        <TransitionSeries.Sequence
          durationInFrames={73}
          name="Tiny brain. Big campus."
        >
          <Outro />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <div
        style={{
          position: "absolute",
          bottom: 0,
          height: 8,
          width: `${(f / 449) * 100}%`,
          background: RED,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 38,
          right: 85,
          display: "flex",
          gap: 10,
        }}
      >
        {Array.from({ length: 8 }, (_, i) => (
          <div
            key={i}
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: Math.floor(f / BEAT) % 8 === i ? RED : "#b3aca0",
            }}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};
