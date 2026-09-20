import { useCurrentFrame } from "remotion";
import { Fly } from "../../Fly";
import { C, Field, Label, move, Ring } from "../system";

export const Brand = () => {
  const f = useCurrentFrame();
  return (
    <Field color={C.yellow}>
      <Label>01 / A DIFFERENT KIND OF DRIVE</Label>
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 184,
          fontFamily: "Anton",
          fontSize: 570,
          lineHeight: 1,
          letterSpacing: 0,
          scale: 1 + Math.sin(f / 5) * 0.035 * (1 - move(f, 0, 22)),
          transformOrigin: "left center",
        }}
      >
        FLIH<span style={{ color: C.red }}>.</span>
      </div>
      <Ring x={1430} y={555} size={640} color={C.ink} thickness={3} />
      <div
        style={{
          position: "absolute",
          left: 1070,
          top: 275,
          width: 720,
          rotate: `${move(f, 0, 25, -22, -7)}deg`,
          translate: `${move(f, 0, 22, 850, 0)}px ${Math.sin(f / 9) * 8}px`,
        }}
      >
        <Fly />
      </div>
      <Label style={{ top: 910, fontSize: 44, letterSpacing: -1 }}>
        Your campus. A new co-pilot.
      </Label>
    </Field>
  );
};
