import {
  AbsoluteFill,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Audio } from "@remotion/media";
import { loadFont } from "@remotion/fonts";
import { TransitionSeries } from "@remotion/transitions";
import { C, clamp, move } from "./system";
import { Hook } from "./scenes/Hook";
import { Brand } from "./scenes/Brand";
import { Route } from "./scenes/Route";
import { Queue } from "./scenes/Queue";
import { Brain } from "./scenes/Brain";
import { Camera } from "./scenes/Camera";
import { Bonk } from "./scenes/Bonk";
import { Finale } from "./scenes/Finale";

loadFont({
  family: "Anton",
  url: staticFile("fonts/anton-400.ttf"),
  weight: "400",
});
loadFont({
  family: "Space Grotesk",
  url: staticFile("fonts/space-grotesk-700.ttf"),
  weight: "700",
});

// FEVER starts at 3.5s. The first reveal is at source 8s / composition frame 270.
// Subsequent cuts are 270 + round(beat * 3600 / 115), avoiding tempo drift.
// Route -> Queue is a true match cut: the same 322px coral circle at (960, 540).
const Bridges = () => {
  const f = useCurrentFrame();
  return (
    <>
      {[333, 771].map((cut, i) => {
        const t = f - cut;
        if (t < -12 || t > 12) return null;
        return (
          <div
            key={cut}
            style={{
              position: "absolute",
              inset: -250,
              background: i === 0 ? C.paper : C.ink,
              rotate: "-12deg",
              translate: `${move(t, -12, 12, -2600, 2600)}px 0px`,
            }}
          />
        );
      })}
      {[489, 614].map((cut, i) => {
        const t = f - cut;
        if (t < -16 || t > 18) return null;
        const radius =
          t < 0 ? move(t, -16, 0, 0, 1250) : move(t, 0, 18, 1250, 0);
        return (
          <div
            key={cut}
            style={{
              position: "absolute",
              left: 960 - radius,
              top: 540 - radius,
              width: radius * 2,
              height: radius * 2,
              borderRadius: "50%",
              background: i === 0 ? C.red : C.yellow,
            }}
          />
        );
      })}
    </>
  );
};

export const KineticVideo = () => (
  <AbsoluteFill
    style={{
      background: C.ink,
      color: C.ink,
      fontFamily: "Space Grotesk",
      fontWeight: 700
    }}
  >
    <Audio
      src={staticFile("fever.mp3")}
      trimBefore={210}
      volume={(f) =>
        interpolate(f, [0, 42, 979, 1020], [0, 0.9, 0.9, 0], clamp)
      }
    />
    <TransitionSeries>
      <TransitionSeries.Sequence
        durationInFrames={270}
        name="Tiny / Big / Roll"
      >
        <Hook />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence
        durationInFrames={63}
        name="Meet FLIH / music 8s impact"
      >
        <Brand />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence
        durationInFrames={94}
        name="A to B / circle match"
      >
        <Route />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence
        durationInFrames={62}
        name="One tap / circle match"
      >
        <Queue />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence durationInFrames={125} name="Real fly brain">
        <Brain />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence
        durationInFrames={94}
        name="Fly’s eye / illustrated POV"
      >
        <Camera />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence durationInFrames={63} name="Big bonk">
        <Bonk />
      </TransitionSeries.Sequence>
      <TransitionSeries.Sequence
        durationInFrames={250}
        name="Plan / Queue / Drive / FLIH"
      >
        <Finale />
      </TransitionSeries.Sequence>
    </TransitionSeries>
    <Bridges />
  </AbsoluteFill>
);
