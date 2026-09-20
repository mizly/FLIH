import { Video } from "@remotion/media";
import { staticFile, useCurrentFrame } from "remotion";
import { C, Field, Label, move, Ring, Star, Type } from "../system";

export const Brain = () => {
  const f = useCurrentFrame();
  return (
    <Field color={C.ink} dark>
      <Label style={{ color: C.yellow }}>04 / FLY BRAIN ONLINE</Label>
      <div style={{ position: "absolute", left: 112, top: 230, zIndex: 2 }}>
        <Type style={{ fontSize: 148 }}>DRIVEN BY A</Type>
        <Type delay={8} style={{ fontSize: 216, color: C.yellow }}>
          REAL
        </Type>
        <Type delay={16} style={{ fontSize: 178 }}>
          FLY BRAIN.
        </Type>
      </div>
      <Ring x={1410} y={535} size={754} color={C.grey} />
      <div
        style={{
          position: "absolute",
          left: 960,
          top: 255,
          width: 850,
          height: 560,
          overflow: "hidden",
          border: `2px solid ${C.yellow}`,
          clipPath: `circle(${move(f, 0, 26, 0, 75)}% at 50% 50%)`,
          scale: move(f, 0, 35, 0.8, 1),
          rotate: `${move(f, 0, 32, 8, 0)}deg`,
        }}
      >
        <Video
          src={staticFile("fly_brain_beat_saber.mp4")}
          trimBefore={660}
          muted
          objectFit="cover"
          style={{ width: "100%", height: "100%" }}
        />
      </div>
      <Star
        color={C.red}
        style={{
          position: "absolute",
          left: 1640,
          top: 735,
          width: 130,
          height: 130,
          rotate: `${f * 1.5}deg`,
        }}
      />
      <Label style={{ top: 930, fontSize: 28, letterSpacing: 1 }}>
        YO WTH HOW IS IT HITTING THAT???
      </Label>
    </Field>
  );
};
