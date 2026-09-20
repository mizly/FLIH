import { useCurrentFrame } from "remotion";
import { card, Paper, Pop, RED, Title, YELLOW } from "../design";
export const Queue = () => {
  const f = useCurrentFrame();
  return (
    <Paper label="02 / RESERVE">
      <Pop style={{ position: "absolute", top: 230, left: 115, width: 700 }}>
        <Title>
          Your turn.
          <br />
          <span style={{ color: RED }}>One tap.</span>
        </Title>
        <div style={{ fontSize: 49, marginTop: 40 }}>
          Join the guide queue.
          <br />
          No account needed.
        </div>
      </Pop>
      <div style={{ position: "absolute", left: 980, top: 190, width: 710 }}>
        {["01   Alex → E7", "02   Sam → E5", "03   You’re in!"].map((t, i) => (
          <Pop
            key={t}
            delay={i * 9}
            style={{
              ...card,
              background: i === 2 ? YELLOW : "#fdfbf7",
              padding: "27px 40px",
              marginBottom: 30,
              fontSize: 53,
              rotate: `${i % 2 ? 2 : -2}deg`,
            }}
          >
            {t}
            <span style={{ float: "right", color: RED }}>
              {i === 2 && f > 25 ? "✓" : "↗"}
            </span>
          </Pop>
        ))}
        <Pop
          delay={30}
          style={{ fontSize: 35, marginTop: 33, textAlign: "center" }}
        >
          Save your spot. Change your route.
        </Pop>
      </div>
    </Paper>
  );
};
