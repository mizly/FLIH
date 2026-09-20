import { useCurrentFrame } from "remotion";
import { C, Field, Label, move, Star } from "../system";

export const Bonk = () => {
  const f = useCurrentFrame();
  return (
    <Field color={C.red}>
      <Star
        color={C.yellow}
        style={{
          position: "absolute",
          width: 1000,
          height: 1000,
          left: 460,
          top: 40,
          rotate: `${move(f, 0, 65, -18, 12)}deg`,
          scale: move(f, 0, 13, 0.2, 1.25),
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeItems: "center",
          fontFamily: "Anton",
          fontSize: 340,
          letterSpacing: -8,
          rotate: `${move(f, 0, 17, -13, -5)}deg`,
          scale: move(f, 0, 14, 1.6, 1),
        }}
      >
        ouch.
      </div>
      <Label
        style={{
          top: 916,
          left: 0,
          textAlign: "center",
          width: "100%",
          fontSize: 42,
          letterSpacing: -1,
        }}
      >
        …we meant to do that.
      </Label>
    </Field>
  );
};
