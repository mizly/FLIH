import { Video } from "@remotion/media";
import { staticFile } from "remotion";
import { Paper, Pop, RED, Title, YELLOW } from "../design";

export const Drive = () => (
  <Paper dark label="03 / FLY BRAIN ONLINE">
    <Pop style={{ position: "absolute", left: 105, top: 255, width: 665 }}>
      <Title style={{ fontSize: 105, letterSpacing: -3 }}>
        controlled by
        <br />a{" "}
        <span style={{ color: RED }}>
          real
          <br />
          fly brain.
        </span>
      </Title>
      <div style={{ fontSize: 39, color: YELLOW, marginTop: 38 }}>
        Tiny brain. Big Beat Saber energy.
      </div>
    </Pop>
    <div
      style={{
        position: "absolute",
        left: 820,
        top: 173,
        width: 1010,
        height: 704,
        border: "4px solid #fff2a6",
        borderRadius: 22,
        overflow: "hidden",
        background: "#101715",
        boxShadow: "12px 12px 0 #ff4d4d",
      }}
    >
      <div
        style={{ height: 48, padding: "3px 22px", fontSize: 28, color: YELLOW }}
      >
        FLY POV + BRAIN ACTIVITY
      </div>
      <Video
        src={staticFile("fly_brain_beat_saber.mp4")}
        trimBefore={330}
        muted
        objectFit="contain"
        style={{ width: 1002, height: 648 }}
      />
    </div>
  </Paper>
);
