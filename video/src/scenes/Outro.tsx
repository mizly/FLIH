import { useCurrentFrame } from "remotion";
import { Fly } from "../Fly";
import { BEAT, Paper, Pop, RED, Tag, Title } from "../design";
export const Outro = () => {
  const f = useCurrentFrame();
  return (
    <Paper label="LET’S ROLL.">
      <Pop style={{ position: "absolute", left: 170, top: 175 }}>
        <Title style={{ fontSize: 265, color: RED, letterSpacing: -12 }}>
          FLIH.
        </Title>
        <Title style={{ fontSize: 103, letterSpacing: -3 }}>
          tiny brain.
          <br />
          big campus.
        </Title>
        <Pop delay={18} style={{ marginTop: 32 }}>
          <Tag>Plan. Queue. Drive. Explore.</Tag>
        </Pop>
      </Pop>
      <Pop
        style={{
          position: "absolute",
          width: 770,
          top: 235,
          right: 110,
          rotate: `${Math.sin((f / BEAT) * Math.PI) * 2}deg`,
        }}
      >
        <Fly />
      </Pop>
    </Paper>
  );
};
