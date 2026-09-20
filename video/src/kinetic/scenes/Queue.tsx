import { useCurrentFrame } from "remotion";
import { C, Field, Label, move, Ring, Type } from "../system";

export const Queue = () => {
  const f = useCurrentFrame();
  return (
    <Field>
      <Label>03 / JOIN THE QUEUE</Label>
      <Ring
        x={960}
        size={322 + move(f, 0, 26, 0, 380)}
        color={C.red}
        style={{ opacity: move(f, 0, 35, 1, 0.15) }}
      />
      <div
        style={{
          position: "absolute",
          left: 799,
          top: 379,
          width: 322,
          height: 322,
          borderRadius: "50%",
          background: C.red,
          scale: move(f, 0, 14, 1, 0.86),
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <svg width="170" height="170" viewBox="0 0 170 170">
          <path
            d="M30 85L68 123L142 46"
            fill="none"
            stroke={C.paper}
            strokeWidth="18"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset={1 - move(f, 6, 23)}
          />
        </svg>
      </div>
      <div style={{ position: "absolute", left: 110, top: 350 }}>
        <Type style={{ fontSize: 190 }}>ONE</Type>
        <Type delay={5} style={{ fontSize: 190 }}>
          TAP.
        </Type>
      </div>
      <div style={{ position: "absolute", left: 1250, top: 350 }}>
        <Type delay={10} style={{ fontSize: 190 }}>
          YOU’RE
        </Type>
        <Type delay={15} style={{ fontSize: 190, color: C.red }}>
          IN.
        </Type>
      </div>
      <Label
        style={{
          top: 865,
          left: 0,
          width: "100%",
          textAlign: "center",
          fontSize: 43,
          letterSpacing: -1,
          opacity: move(f, 18, 30),
        }}
      >
        No account needed.
      </Label>
    </Field>
  );
};
