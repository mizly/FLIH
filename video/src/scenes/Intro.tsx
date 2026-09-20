import { useCurrentFrame } from "remotion";
import { Fly } from "../Fly";
import { BEAT, Paper, Pop, RED, Tag, Title } from "../design";
export const Intro = () => {
  const f = useCurrentFrame();
  return (
    <Paper label="MEET YOUR CAMPUS CO-PILOT">
      <Pop style={{ position: "absolute", left: 140, top: 230 }}>
        <div style={{ fontSize: 64 }}>small robot.</div>
        <Title style={{ fontSize: 235, color: RED, letterSpacing: -12 }}>
          BIG FLIH.
        </Title>
        <Tag>Meet your campus co-pilot.</Tag>
      </Pop>
      <Pop
        delay={5}
        style={{
          position: "absolute",
          width: 740,
          right: 85,
          top: 190,
          rotate: `${Math.sin((f / BEAT) * Math.PI) * 3}deg`,
        }}
      >
        <Fly />
      </Pop>
      <svg
        style={{ position: "absolute", left: 700, top: 720 }}
        width="390"
        height="130"
        viewBox="0 0 390 130"
      >
        <path
          d="M10 95 Q190 130 345 20 l-5 45 M345 20 l-55 5"
          stroke={RED}
          strokeWidth="8"
          fill="none"
          strokeLinecap="round"
        />
      </svg>
    </Paper>
  );
};
