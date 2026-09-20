import { interpolate, useCurrentFrame } from "remotion";
import { clamp, INK, Paper, RED, Title, YELLOW } from "../design";

// A deterministic, illustrated stereo-camera simulation; no live telemetry.
const rangeAt = (f: number) =>
  interpolate(
    f,
    [0, 18, 21, 28, 37, 40, 47, 56, 57, 74],
    [2.8, 0.12, 0.08, 1.5, 0.1, 0.06, 0.9, 0.02, 0, 0],
    clamp,
  );
const impactAt = (f: number) =>
  Math.max(
    ...[19, 38, 57].map((hit) => Math.max(0, 1 - Math.abs(f - hit) / 7)),
  );

const Camera = ({ frame, side }: { frame: number; side: "L" | "R" }) => {
  const range = rangeAt(frame),
    impact = impactAt(frame),
    crash = frame >= 57;
  const approach = interpolate(range, [0, 2.8], [1.95, 0.28], clamp);
  const steering = interpolate(
    frame,
    [0, 19, 27, 38, 46, 57],
    [0, 0, 90, 90, -70, -70],
    clamp,
  );
  const parallax = side === "L" ? -22 : 22;
  return (
    <div
      style={{
        position: "relative",
        width: 655,
        height: 430,
        overflow: "hidden",
        border: `4px solid ${impact > 0.1 ? RED : "#b6cfc4"}`,
        borderRadius: 16,
        background: "#11201e",
        translate: `${Math.sin(frame * 2.8) * impact * 15}px ${Math.cos(frame * 3) * impact * 10}px`,
      }}
    >
      <svg width="655" height="430" viewBox="0 0 655 430">
        <defs>
          <linearGradient id={`wall-${side}`} x2="0" y2="1">
            <stop stopColor="#6d8f83" />
            <stop offset="1" stopColor="#273e37" />
          </linearGradient>
        </defs>
        <rect width="655" height="430" fill={`url(#wall-${side})`} />
        <path
          d="M0 0 L240 155 H415 L655 0 M0 430 L240 250 H415 L655 430"
          fill="#c9ccaa"
        />
        <path d="M0 0 L240 155 V250 L0 430 Z" fill="#789b85" />
        <rect x="240" y="155" width="175" height="95" fill="#324c41" />
        {[0, 1, 2, 3, 4, 5].map((i) => {
          const y = 265 + ((i * 38 + frame * 6) % 180);
          return (
            <path key={i} d={`M0 ${y} H655`} stroke="#7c8873" strokeWidth="2" />
          );
        })}
        {[0, 130, 260, 390, 520, 655].map((x) => (
          <path
            key={x}
            d={`M327 250 L${x} 430`}
            stroke="#7c8873"
            strokeWidth="2"
          />
        ))}
        <g
          transform={`translate(${327 + parallax + steering} 265) scale(${approach})`}
        >
          <path
            d="M-100 -140 H80 L113 -113 V60 H-100Z"
            fill="#daac69"
            stroke={INK}
            strokeWidth="4"
          />
          <path
            d="M80 -140 V30 L113 60 V-113 M-100 30 H80 L113 60 M-10 -140 V30"
            fill="none"
            stroke="#866035"
            strokeWidth="5"
          />
          <path
            d="M-42 -80 L-20 -100 L2 -80 M-20 -100 V-45"
            fill="none"
            stroke={INK}
            strokeWidth="6"
          />
        </g>
        <path d="M305 215 H350 M327 193 V237" stroke={YELLOW} strokeWidth="2" />
        <path
          d="M80 405 Q327 355 575 405 V430 H80Z"
          fill="#26312e"
          stroke="#93a397"
          strokeWidth="4"
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          boxShadow: `inset 0 0 ${45 + impact * 110}px ${10 + impact * 35}px rgba(255,35,35,${impact * 0.95})`,
          background: crash ? "rgba(255,55,25,.25)" : "transparent",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 15,
          left: 18,
          fontSize: 27,
          color: YELLOW,
        }}
      >
        ● CAM {side} / {crash ? "SIGNAL LOST" : "LIVE"}
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 16,
          left: 20,
          color: "#fff",
          fontSize: 29,
        }}
      >
        RANGE {range.toFixed(2)} m
      </div>
      {impact > 0.3 && !crash && (
        <div
          style={{
            position: "absolute",
            top: 120,
            left: 210,
            color: YELLOW,
            fontFamily: "Kalam",
            fontSize: 72,
            rotate: "-9deg",
          }}
        >
          BONK!
        </div>
      )}
    </div>
  );
};

export const Sense = () => {
  const f = useCurrentFrame(),
    range = rangeAt(f),
    impact = impactAt(f),
    crash = f >= 57;
  const boom = interpolate(f, [57, 61, 74], [0.35, 1.08, 1], clamp);
  return (
    <Paper dark label="04 / YOU ARE THE FLY">
      <div
        style={{
          position: "absolute",
          left: 105,
          top: 100,
          display: "flex",
          alignItems: "center",
          gap: 50,
        }}
      >
        <Title style={{ fontSize: 100, color: YELLOW }}>FLIH CAM</Title>
        <div style={{ fontSize: 36 }}>
          Your keys. Fly’s-eye view. Questionable parking.
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 270,
          display: "flex",
          gap: 24,
        }}
      >
        <Camera frame={f} side="L" />
        <Camera frame={f} side="R" />
      </div>
      <div
        style={{
          position: "absolute",
          left: 1470,
          top: 270,
          width: 345,
          height: 430,
          border: `3px solid ${range < 0.5 ? RED : "#789b85"}`,
          borderRadius: 16,
          background: "#14251f",
          padding: 16,
          color: YELLOW,
        }}
      >
        <div style={{ fontSize: 28 }}>LiDAR / 360°</div>
        <svg width="305" height="265" viewBox="0 0 305 265">
          {[40, 80, 120].map((r) => (
            <circle
              key={r}
              cx="152"
              cy="132"
              r={r}
              fill="none"
              stroke="#577569"
            />
          ))}
          <path d="M152 10 V254 M30 132 H274" stroke="#577569" />
          <g transform={`rotate(${f * 8} 152 132)`}>
            <path
              d="M152 132 L152 12 A120 120 0 0 1 237 47 Z"
              fill="#addb7a"
              opacity=".22"
            />
            <path d="M152 132 V12" stroke={YELLOW} strokeWidth="2" />
          </g>
          {Array.from({ length: 40 }, (_, i) => {
            const a = (i / 40) * Math.PI * 2;
            const r =
              i > 22 && i < 36 ? 25 + range * 29 : 100 + Math.sin(i * 7) * 14;
            return (
              <circle
                key={i}
                cx={152 + Math.cos(a) * r}
                cy={132 + Math.sin(a) * r}
                r="3.5"
                fill={range < 0.5 ? RED : YELLOW}
              />
            );
          })}
          <path d="M152 119 L143 141 H161Z" fill={YELLOW} />
        </svg>
        <div style={{ fontSize: 42, color: range < 0.5 ? RED : YELLOW }}>
          {range.toFixed(2)} m
        </div>
        <div style={{ fontSize: 27 }}>
          {crash
            ? "IMPACT / OOPS."
            : range < 0.5
              ? "COLLISION WARNING"
              : "SCANNING AHEAD"}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          top: 752,
          left: 110,
          display: "flex",
          gap: 18,
          alignItems: "center",
        }}
      >
        {["W", "A", "S", "D"].map((k) => (
          <div
            key={k}
            style={{
              width: 78,
              height: 78,
              border: "3px solid #fff2a6",
              borderRadius: 10,
              fontSize: 49,
              textAlign: "center",
              background:
                !crash &&
                (k === "W" ||
                  (f > 21 && f < 33 && k === "D") ||
                  (f > 40 && k === "A"))
                  ? RED
                  : "transparent",
            }}
          >
            {k}
          </div>
        ))}
        <span style={{ fontSize: 34, marginLeft: 25 }}>
          {crash ? "...we meant to do that." : "W: forward · A / D: steer"}
        </span>
      </div>
      <div
        style={{
          position: "absolute",
          right: 115,
          top: 747,
          width: 470,
          height: 133,
        }}
      >
        <svg width="470" height="133" viewBox="0 0 470 133">
          <rect
            x="12"
            y="30"
            width="440"
            height="90"
            rx="25"
            fill="#4d5d52"
            stroke={YELLOW}
            strokeWidth="3"
          />
          {[95, 365].map((x) => (
            <g key={x}>
              <circle
                cx={x}
                cy="76"
                r="29"
                fill="#14251f"
                stroke={YELLOW}
                strokeWidth="4"
              />
              <circle cx={x} cy="76" r="12" fill="#77aaac" />
            </g>
          ))}
          <ellipse cx="230" cy="40" rx="47" ry="18" fill={RED} />
          <rect x="183" y="20" width="94" height="22" fill={RED} />
          <ellipse cx="230" cy="20" rx="47" ry="17" fill={YELLOW} />
          <text x="95" y="129" fill={YELLOW} textAnchor="middle" fontSize="19">
            CAM L
          </text>
          <text x="230" y="99" fill={YELLOW} textAnchor="middle" fontSize="22">
            LiDAR
          </text>
          <text x="365" y="129" fill={YELLOW} textAnchor="middle" fontSize="19">
            CAM R
          </text>
        </svg>
      </div>
      <div
        style={{
          position: "absolute",
          left: 112,
          top: 883,
          fontSize: 25,
          color: "#a3aca1",
        }}
      >
        SIMULATED POV · COMIC CRASH SEQUENCE
      </div>
      {crash && (
        <div
          style={{
            position: "absolute",
            left: 435,
            top: 230,
            width: 980,
            height: 560,
            scale: boom,
            rotate: `${Math.sin(f) * 2}deg`,
          }}
        >
          <svg width="980" height="560" viewBox="0 0 980 560">
            <path
              d="M490 5 L555 135 L715 30 L700 170 L955 125 L810 260 L975 370 L740 385 L790 540 L580 445 L470 555 L395 433 L170 535 L210 385 L15 350 L175 255 L35 110 L290 160 L275 15 L420 143Z"
              fill={RED}
              stroke={INK}
              strokeWidth="12"
            />
            <path
              d="M490 70 L550 190 L680 115 L650 245 L860 255 L700 330 L700 450 L545 390 L470 490 L400 365 L225 425 L275 310 L100 245 L350 230 L335 105 L425 215Z"
              fill={YELLOW}
            />
            <text
              x="490"
              y="340"
              textAnchor="middle"
              fontFamily="Kalam"
              fontWeight="700"
              fontSize="158"
              fill={INK}
            >
              BOOM!
            </text>
          </svg>
          <div
            style={{
              position: "absolute",
              bottom: 48,
              left: 320,
              fontSize: 38,
              color: INK,
            }}
          >
            tiny brain. big bonk.
          </div>
        </div>
      )}
      {impact > 0.2 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            boxShadow: `inset 0 0 140px 45px rgba(255,30,30,${impact * 0.65})`,
          }}
        />
      )}
    </Paper>
  );
};
