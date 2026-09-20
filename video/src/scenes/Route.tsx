import { interpolate, useCurrentFrame } from "remotion";
import {
  BLUE,
  card,
  clamp,
  INK,
  Paper,
  Pop,
  RED,
  Title,
  YELLOW,
} from "../design";
export const Route = () => {
  const f = useCurrentFrame();
  const p = interpolate(f, [8, 54], [0, 1], clamp);
  return (
    <Paper label="01 / PLAN">
      <Pop style={{ position: "absolute", left: 115, top: 280, width: 780 }}>
        <Title>
          Pick a stop.
          <br />
          <span style={{ color: RED }}>Find a route.</span>
        </Title>
        <div style={{ fontSize: 48, marginTop: 35 }}>
          Indoor campus route planning.
        </div>
      </Pop>
      <Pop
        delay={3}
        style={{
          ...card,
          position: "absolute",
          left: 920,
          top: 180,
          width: 850,
          height: 690,
          rotate: "2deg",
          padding: 35,
        }}
      >
        <div style={{ fontSize: 39 }}>
          E5 / E7 · sixth floor{" "}
          <span style={{ float: "right", color: BLUE }}>DEMO</span>
        </div>
        <svg width="770" height="530" viewBox="0 0 770 530">
          {[0, 1, 2, 3].map((i) => (
            <g key={i}>
              <rect
                x={30 + i * 182}
                y="55"
                width="146"
                height="140"
                rx="8"
                fill="#eae5db"
                stroke={INK}
                strokeWidth="3"
              />
              <rect
                x={30 + i * 182}
                y="325"
                width="146"
                height="130"
                rx="8"
                fill="#eae5db"
                stroke={INK}
                strokeWidth="3"
              />
            </g>
          ))}
          <path
            d="M100 170 V260 H652 V350"
            fill="none"
            stroke="#ccc5b9"
            strokeWidth="26"
            strokeLinecap="round"
          />
          <path
            d="M100 170 V260 H652 V350"
            fill="none"
            stroke={RED}
            strokeWidth="14"
            strokeLinecap="round"
            pathLength="1"
            strokeDasharray="1"
            strokeDashoffset={1 - p}
          />
          <circle
            cx="100"
            cy="170"
            r="24"
            fill={YELLOW}
            stroke={INK}
            strokeWidth="4"
          />
          <text x="100" y="179" textAnchor="middle" fontSize="27">
            A
          </text>
          <circle cx="652" cy="350" r={24 + Math.sin(f * 0.3) * 3} fill={RED} />
          <text x="652" y="359" textAnchor="middle" fill="white" fontSize="27">
            B
          </text>
          <text x="275" y="500" fontSize="33" fill={INK}>
            Your next stop, mapped.
          </text>
        </svg>
      </Pop>
    </Paper>
  );
};
