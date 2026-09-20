import { useCurrentFrame } from "remotion";
import { C, Field, Label, move, Type } from "../system";

export const Camera = () => {
  const f = useCurrentFrame();
  const impact = Math.max(0, 1 - Math.abs(f - 72) / 10);
  const approach = move(f, 0, 78, 0.35, 2.5);
  return (
    <Field color={C.ink} dark>
      <div
        style={{
          position: "absolute",
          inset: 0,
          translate: `${Math.sin(f * 2) * impact * 10}px ${Math.cos(f * 3) * impact * 6}px`,
          rotate: `${Math.sin(f * 2.5) * impact * 0.45}deg`,
        }}
      >
      <div
        style={{
          position: "absolute",
          inset: 0,
          scale: move(f, 0, 24, 1.18, 1),
        }}
      >
        <svg width="1920" height="1080" viewBox="0 0 1920 1080">
          <rect width="1920" height="1080" fill="#303b30" />
          <path d="M0 0L780 390H1140L1920 0Z" fill="#a8b393" />
          <path d="M0 1080L780 640H1140L1920 1080Z" fill="#66765b" />
          <path d="M0 0L780 390V640L0 1080Z" fill="#4b614d" />
          <path d="M1920 0L1140 390V640L1920 1080Z" fill="#74836b" />
          <rect x="780" y="390" width="360" height="250" fill="#1e2d26" />
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
            const p = ((i / 8 + f / 230) % 1) ** 2;
            return (
              <path
                key={i}
                d={`M${780 * (1 - p)} ${640 + 440 * p}H${1140 + 780 * p}`}
                stroke="#b6c5a0"
                opacity=".45"
                strokeWidth="2"
              />
            );
          })}
          {[0, 320, 640, 960, 1280, 1600, 1920].map((x) => (
            <path
              key={x}
              d={`M960 640L${x} 1080`}
              stroke="#b6c5a0"
              opacity=".45"
              strokeWidth="2"
            />
          ))}
          <g
            transform={`translate(${960 + Math.sin(f / 20) * 28} 620) scale(${approach})`}
          >
            <rect
              x="-160"
              y="-190"
              width="320"
              height="230"
              fill="#b69e64"
              stroke={C.ink}
              strokeWidth="5"
            />
            <path
              d="M0 -190V40M-160 -155H160M-100 -40V-115L-125 -90M-100 -115L-75 -90"
              fill="none"
              stroke="#6e603c"
              strokeWidth="8"
            />
          </g>
          <path
            d="M900 540H935M985 540H1020M960 480V515M960 565V600"
            stroke={C.yellow}
            strokeWidth="4"
          />
        </svg>
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg,rgba(25,27,25,.75),transparent 40%,transparent 70%,rgba(25,27,25,.85))",
          boxShadow: `inset 0 0 ${impact * 170}px ${impact * 80}px ${C.red}`,
        }}
      />
      <Label style={{ color: C.yellow }}>05 / FLIH CAM</Label>
      <div style={{ position: "absolute", left: 112, top: 168 }}>
        <Type style={{ fontSize: 135 }}>VIEW FLIH CAM IN REAL TIME.</Type>
      </div>
      <div
        style={{
          position: "absolute",
          left: 112,
          top: 850,
          display: "flex",
          gap: 12,
        }}
      >
        {["W", "A", "S", "D"].map((k, i) => (
          <div
            key={k}
            style={{
              width: 82,
              height: 82,
              border: `2px solid ${C.yellow}`,
              background:
                i === 0 || (i === 3 && f > 35 && f < 65) ? C.yellow : C.ink,
              color:
                i === 0 || (i === 3 && f > 35 && f < 65) ? C.ink : C.yellow,
              display: "grid",
              placeItems: "center",
              fontSize: 42,
            }}
          >
            {k}
          </div>
        ))}
      </div>
      <Label
        style={{
          top: 867,
          left: 1450,
          color: f > 65 ? C.red : C.yellow,
          fontSize: 45,
        }}
      >
        {f > 65 ? "OOPS." : `${(2.8 - move(f, 0, 78, 0, 2.72)).toFixed(2)} m`}
      </Label>
      <Label style={{ top: 980, fontSize: 21, letterSpacing: 2 }}>
        ILLUSTRATED POV / SIMULATION
      </Label>
      </div>
    </Field>
  );
};
