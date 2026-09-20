import type { CSSProperties, ReactNode } from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";

export const C = {
  ink: "#191b19",
  paper: "#f4f0e5",
  red: "#fa503c",
  yellow: "#e9f477",
  grey: "#74776b",
};
export const BEAT = 3600 / 115;
export const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;
export const ease = Easing.bezier(0.76, 0, 0.24, 1);
export const out = Easing.bezier(0.16, 1, 0.3, 1);
export const move = (f: number, start: number, end: number, a = 0, b = 1) =>
  interpolate(f, [start, end], [a, b], { ...clamp, easing: ease });

export const Field = ({
  children,
  color = C.paper,
  dark = false,
}: {
  children: ReactNode;
  color?: string;
  dark?: boolean;
}) => (
  <AbsoluteFill
    style={{
      background: color,
      color: dark ? C.paper : C.ink,
      overflow: "hidden"
    }}
  >
    <AbsoluteFill
      style={{
        opacity: 0.055,
        backgroundImage: `linear-gradient(${dark ? C.paper : C.ink} 1px, transparent 1px),linear-gradient(90deg,${dark ? C.paper : C.ink} 1px, transparent 1px)`,
        backgroundSize: "120px 120px",
      }}
    />
    {children}
  </AbsoluteFill>
);

export const Label = ({
  children,
  style,
}: {
  children: ReactNode;
  style?: CSSProperties;
}) => (
  <div
    style={{
      position: "absolute",
      left: 112,
      top: 84,
      fontFamily: "Space Grotesk",
      fontSize: 28,
      fontWeight: 700,
      letterSpacing: 3,
      ...style,
    }}
  >
    {children}
  </div>
);

export const Type = ({
  children,
  style,
  delay = 0,
}: {
  children: ReactNode;
  style?: CSSProperties;
  delay?: number;
}) => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        fontFamily: "Anton",
        fontSize: 190,
        lineHeight: 1.02,
        letterSpacing: -3,
        ...style,
        translate: interpolate(
          f,
          [delay, delay + 16],
          ["0px 150px", "0px 0px"],
          { ...clamp, easing: out },
        ),
        opacity: interpolate(f, [delay, delay + 6], [0, 1], clamp),
      }}
    >
      {children}
    </div>
  );
};

export const Ring = ({
  x = 1370,
  y = 540,
  size = 580,
  color = C.red,
  thickness = 4,
  style,
}: {
  x?: number;
  y?: number;
  size?: number;
  color?: string;
  thickness?: number;
  style?: CSSProperties;
}) => (
  <div
    style={{
      position: "absolute",
      left: x - size / 2,
      top: y - size / 2,
      width: size,
      height: size,
      border: `${thickness}px solid ${color}`,
      borderRadius: "50%",
      ...style,
    }}
  />
);

export const Arrow = ({
  color = C.ink,
  style,
}: {
  color?: string;
  style?: CSSProperties;
}) => (
  <svg
    viewBox="0 0 200 200"
    style={{ width: 180, height: 180, ...style }}
    fill="none"
  >
    <path
      d="M30 100H170M100 30L170 100L100 170"
      stroke={color}
      strokeWidth="22"
      strokeLinecap="square"
    />
  </svg>
);

export const Star = ({
  color = C.red,
  style,
}: {
  color?: string;
  style?: CSSProperties;
}) => (
  <svg viewBox="0 0 200 200" style={{ width: 200, height: 200, ...style }}>
    <path
      d="M100 0L119 57L165 24L153 78L200 100L146 118L175 172L121 149L100 200L79 148L25 174L52 121L0 100L51 80L24 25L78 51Z"
      fill={color}
    />
  </svg>
);
