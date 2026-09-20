import { useCurrentFrame } from "remotion";
import { Fly } from "../../Fly";
import { Arrow, C, Field, Label, move, Ring } from "../system";

export const Finale = () => {
  const frame = useCurrentFrame();
  const recap = frame < 94;
  const word = frame < 31 ? 0 : frame < 63 ? 1 : 2;
  const t = frame - [0, 31, 63][word];
  const f = frame - 37;
  return (
    <Field
      color={recap ? [C.ink, C.paper, C.yellow][word] : C.paper}
      dark={recap && word === 0}
    >
      {recap ? (
        <>
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              fontFamily: "Anton",
              fontSize: 370,
              letterSpacing: 0,
              translate: `${move(t, 0, 10, 250, 0)}px 0px`,
              scale: move(t, 0, 10, 0.9, 1),
            }}
          >
            {["PLAN.", "QUEUE.", "DRIVE."][word]}
          </div>
          <Arrow
            color={word === 0 ? C.red : C.ink}
            style={{
              position: "absolute",
              left: 1620,
              top: 445,
              translate: `${move(t, 0, 15, -60, 0)}px 0px`,
            }}
          />
        </>
      ) : (
        <>
          <Label>YOUR CAMPUS CO-PILOT.</Label>
          <Ring
            x={1420}
            y={510}
            size={680}
            color={C.red}
            thickness={3}
            style={{ scale: move(f, 57, 82, 0.5, 1) }}
          />
          <div
            style={{
              position: "absolute",
              left: 105,
              top: 170,
              fontFamily: "Anton",
              fontSize: 520,
              lineHeight: 1,
              letterSpacing: -5,
              color: C.red,
              scale: move(f, 57, 77, 1.25, 1),
              transformOrigin: "left center",
              opacity: move(f, 57, 65),
            }}
          >
            FLIH.
          </div>
          <div
            style={{
              position: "absolute",
              left: 1080,
              top: 260,
              width: 700,
              rotate: `${move(f, 57, 95, -12, 0)}deg`,
              translate: `${move(f, 57, 85, 500, 0)}px 0px`,
            }}
          >
            <Fly />
          </div>
          <div
            style={{
              position: "absolute",
              left: 112,
              top: 760,
              fontSize: 64,
              letterSpacing: -2,
              opacity: move(f, 65, 80),
            }}
          >
            Tiny brain. Big campus.
          </div>
          <div
            style={{
              position: "absolute",
              left: 112,
              top: 885,
              display: "flex",
              alignItems: "center",
              gap: 28,
              opacity: move(f, 80, 93),
            }}
          >
            <div style={{ width: 470, height: 5, background: C.ink }} />
            <span style={{ fontSize: 32 }}>PLAN. QUEUE. DRIVE.</span>
            <Arrow style={{ width: 58, height: 58 }} />
          </div>
        </>
      )}
    </Field>
  );
};
