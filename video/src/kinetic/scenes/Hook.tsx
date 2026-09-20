import { useCurrentFrame } from "remotion";
import { C, Field, Label, move, Ring, Star } from "../system";

export const Hook = () => {
  const f = useCurrentFrame();
  const phase = f < 113 ? 0 : f < 207 ? 1 : 2;
  const t = f - [0, 113, 207][phase];
  const reveal = f >= 239;
  if (reveal)
    return (
      <Field color={C.ink} dark>
        <Label>YOUR CAMPUS CO-PILOT.</Label>
        <div
          style={{
            position: "absolute",
            left: 100,
            top: 184,
            fontFamily: "Anton",
            fontSize: 570,
            lineHeight: 1,
            letterSpacing: -5,
            color: "transparent",
            WebkitTextStroke: `3px ${C.yellow}`,
            scale: move(f, 239, 268, 0.65, 1),
            transformOrigin: "left center",
          }}
        >
          FLIH.
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 120,
            left: 112,
            height: 5,
            width: move(f, 239, 269, 0, 1696),
            background: C.yellow,
          }}
        />
      </Field>
    );
  return (
    <Field color={C.ink} dark>
      <Label>MEET YOUR CAMPUS CO-PILOT</Label>
      <Ring
        x={960}
        size={900 + t * 3}
        color={C.paper}
        style={{ opacity: 0.12 }}
      />
      <Ring
        x={960}
        size={560 + t * 3}
        color={C.paper}
        style={{ opacity: 0.12 }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          fontFamily: "Anton",
          lineHeight: 0.98,
          fontSize: phase === 2 ? 245 : 290,
          letterSpacing: -5,
          scale: move(t, 0, 12, 0.72, 1),
          rotate: `${move(t, 0, 13, -5, 0)}deg`,
        }}
      >
        <div style={{ color: C.paper }}>{["TINY", "BIG", "LET’S"][phase]}</div>
        <div
          style={{
            color: phase === 1 ? C.red : C.yellow,
            opacity: move(t, 10, 20),
          }}
        >
          {["BRAIN.", "CAMPUS.", "ROLL."][phase]}
        </div>
      </div>
      <Star
        color={phase === 1 ? C.yellow : C.red}
        style={{
          position: "absolute",
          left: 1460,
          top: 660,
          rotate: `${f * 0.8}deg`,
          scale: move(t, 0, 16, 0.2, 1),
        }}
      />
      <Label style={{ top: 945, fontSize: 25, letterSpacing: 2 }}>
        HTN 2026
      </Label>
    </Field>
  );
};
