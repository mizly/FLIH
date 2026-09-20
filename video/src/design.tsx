import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
export const INK = "#2d2d2d",
  PAPER = "#fdfbf7",
  RED = "#ff4d4d",
  YELLOW = "#fff2a6",
  BLUE = "#2d5da1";
export const BEAT = (30 * 60) / 191;
export const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;
export const card: CSSProperties = {
  background: PAPER,
  border: `4px solid ${INK}`,
  borderRadius: "28px 13px 25px 17px",
  boxShadow: `12px 12px 0 ${INK}`,
};
export const Paper = ({
  children,
  dark = false,
  label = "",
}: {
  children: ReactNode;
  dark?: boolean;
  label?: string;
}) => (
  <AbsoluteFill
    style={{
      backgroundColor: dark ? INK : PAPER,
      backgroundImage: `radial-gradient(${dark ? "#484840" : "#ded8cc"} 1.4px,transparent 1.4px)`,
      backgroundSize: "28px 28px",
      color: dark ? PAPER : INK,
      padding: 85,
    }}
  >
    <div
      style={{
        position: "absolute",
        top: 46,
        left: 85,
        fontSize: 30,
        letterSpacing: 3,
      }}
    >
      FLIH / {label}
    </div>
    {children}
    <div
      style={{
        position: "absolute",
        bottom: 35,
        left: 85,
        fontSize: 26,
        opacity: 0.65,
      }}
    >
      TINY BRAIN, BIG CAMPUS
    </div>
  </AbsoluteFill>
);
export const Pop = ({
  children,
  delay = 0,
  style = {},
}: {
  children: ReactNode;
  delay?: number;
  style?: CSSProperties;
}) => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        ...style,
        opacity: interpolate(f, [delay, delay + 5], [0, 1], clamp),
        translate: interpolate(
          f,
          [delay, delay + 15],
          ["0px 90px", "0px 0px"],
          { ...clamp, easing: Easing.bezier(0.16, 1, 0.3, 1) },
        ),
        scale: interpolate(f, [delay, delay + 15], [0.92, 1], clamp),
      }}
    >
      {children}
    </div>
  );
};
export const Title = ({
  children,
  style = {},
}: {
  children: ReactNode;
  style?: CSSProperties;
}) => (
  <div
    style={{
      fontFamily: "Kalam",
      fontWeight: 700,
      fontSize: 142,
      lineHeight: 1.06,
      letterSpacing: 0,
      ...style,
    }}
  >
    {children}
  </div>
);
export const Tag = ({
  children,
  style = {},
}: {
  children: ReactNode;
  style?: CSSProperties;
}) => (
  <div
    style={{
      ...card,
      display: "inline-block",
      background: YELLOW,
      padding: "10px 30px",
      fontSize: 44,
      rotate: "-3deg",
      ...style,
    }}
  >
    {children}
  </div>
);
