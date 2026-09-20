import { useCurrentFrame } from "remotion";
import { C, Field, Label, move, Type } from "../system";

export const Route = () => {
  const f = useCurrentFrame();
  const end = move(f, 60, 91);
  return (
    <Field>
      <Label>02 / PICK YOUR NEXT STOP</Label>
      <div
        style={{ position: "absolute", left: 112, top: 250, opacity: 1 - end }}
      >
        <Type>GO FROM</Type>
        <Type delay={9} style={{ color: C.red, fontSize: 250 }}>
          A TO B.
        </Type>
        <div style={{ fontSize: 43, marginTop: 40 }}>
          Indoor routes. Sorted.
        </div>
      </div>
      <svg
        width="1920"
        height="1080"
        style={{ position: "absolute", opacity: 1 - end }}
      >
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <rect
              x={990 + i * 265}
              y="235"
              width="215"
              height="190"
              fill="#e5e2d7"
            />
            <rect
              x={990 + i * 265}
              y="680"
              width="215"
              height="160"
              fill="#e5e2d7"
            />
          </g>
        ))}
        <path
          d="M1070 405V550H1645V450"
          fill="none"
          stroke="#d3d2c8"
          strokeWidth="32"
        />
        <path
          d="M1070 405V550H1645V450"
          fill="none"
          stroke={C.red}
          strokeWidth="20"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - move(f, 8, 54)}
        />
        <circle cx="1070" cy="405" r="30" fill={C.ink} />
        <text x="1070" y="416" textAnchor="middle" fill={C.paper} fontSize="30">
          A
        </text>
      </svg>
      <div
        style={{
          position: "absolute",
          left: 1645 + (960 - 1645) * end - (52 + 270 * end) / 2,
          top: 450 + 90 * end - (52 + 270 * end) / 2,
          width: 52 + 270 * end,
          height: 52 + 270 * end,
          borderRadius: "50%",
          background: C.red,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: C.paper,
          fontSize: 32 + 80 * end,
          fontFamily: "Anton",
          scale: f < 60 ? 1 + Math.sin(f / 6) * 0.06 : 1,
        }}
      >
        <span style={{ opacity: 1 - end }}>B</span>
      </div>
      <Label style={{ top: 940, fontSize: 23, opacity: 1 - end }}>
        SCHEMATIC CAMPUS ROUTE
      </Label>
    </Field>
  );
};
