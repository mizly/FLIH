"use client";

import { useEffect, useRef, useState } from "react";
import type { TrainingPreview } from "@/lib/training-types";

type Vec = [number, number, number];
type Face = { points: Vec[]; color: string; line?: boolean };

// Small, software-projected 3D scene. No WebGL context or additional simulator
// camera competes with training. Geometry and backing resolution are bounded.
function draw(
  canvas: HTMLCanvasElement,
  sample: TrainingPreview,
  pose: TrainingPreview["pose"],
  angle: number,
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const width = canvas.width,
    height = canvas.height;
  const extent = Math.max(1, sample.arena);
  const scale = Math.min(width / 3.3, height / 2.1) / extent;
  const c = Math.cos(angle),
    s = Math.sin(angle);
  const project = ([x, y, z]: Vec) => [
    width / 2 + (c * x - s * y) * scale,
    height * 0.58 + ((s * x + c * y) * 0.53 - z * 0.85) * scale,
  ];
  const depth = ([x, y, z]: Vec) => (s * x + c * y) * 0.85 + z * 0.53;
  const paint = (points: Vec[], color: string, line = false) => {
    ctx.beginPath();
    points.forEach((point, i) => {
      const [x, y] = project(point);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    if (line) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    } else {
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    }
  };
  ctx.fillStyle = "#101d22";
  ctx.fillRect(0, 0, width, height);
  paint(
    [
      [-extent, -extent, 0],
      [extent, -extent, 0],
      [extent, extent, 0],
      [-extent, extent, 0],
    ],
    "#1a2c32",
  );
  for (let i = -10; i <= 10; i++) {
    const v = (i * extent) / 10;
    paint(
      [
        [-extent, v, 0],
        [extent, v, 0],
      ],
      "#263d43",
      true,
    );
    paint(
      [
        [v, -extent, 0],
        [v, extent, 0],
      ],
      "#263d43",
      true,
    );
  }
  paint(
    sample.trail.slice(-64).map(([x, y]) => [x, y, 0.02]),
    "#77cdbb",
    true,
  );
  const ring = (x: number, y: number, r: number, z: number): Vec[] =>
    Array.from({ length: 25 }, (_, i) => [
      x + r * Math.cos((i * Math.PI) / 12),
      y + r * Math.sin((i * Math.PI) / 12),
      z,
    ]);
  paint(
    ring(...sample.goal, Math.max(sample.goal_radius, 0.18), 0.03),
    "#9bdf8c",
    true,
  );
  paint(
    ring(...sample.goal, Math.max(sample.goal_radius, 0.18) * 1.35, 0.03),
    "#4f8064",
    true,
  );
  const faces: Face[] = [];
  for (const obstacle of sample.obstacles.slice(0, 20)) {
    const bottom = ring(obstacle.x, obstacle.y, obstacle.radius, 0);
    const top = ring(obstacle.x, obstacle.y, obstacle.radius, obstacle.height);
    for (let i = 0; i < 24; i++)
      faces.push({
        points: [bottom[i], bottom[i + 1], top[i + 1], top[i]],
        color: i % 3 ? "#395965" : "#426572",
      });
    faces.push({ points: top, color: "#5d8290" });
  }
  // The model controls a wheeled navigation body; the fly is a stylized avatar
  // of its measured position and heading, not measured insect joint kinematics.
  const flyScale = Math.max(0.7, extent / 6);
  const local = ([x, y, z]: Vec): Vec => [
    pose.x + flyScale * (x * Math.cos(pose.yaw) - y * Math.sin(pose.yaw)),
    pose.y + flyScale * (x * Math.sin(pose.yaw) + y * Math.cos(pose.yaw)),
    z * flyScale,
  ];
  const ellipsoid = (center: Vec, radius: Vec, color: string) => {
    const point = (lat: number, lon: number): Vec =>
      local([
        center[0] + radius[0] * Math.cos(lat) * Math.cos(lon),
        center[1] + radius[1] * Math.cos(lat) * Math.sin(lon),
        center[2] + radius[2] * Math.sin(lat),
      ]);
    for (let j = 0; j < 6; j++)
      for (let i = 0; i < 12; i++) {
        const a = -Math.PI / 2 + (j * Math.PI) / 6,
          b = a + Math.PI / 6;
        const u = (i * Math.PI) / 6,
          v = u + Math.PI / 6;
        faces.push({
          points: [point(a, u), point(a, v), point(b, v), point(b, u)],
          color,
        });
      }
  };
  paint(
    ring(pose.x, pose.y, 0.65 * flyScale, 0.02),
    sample.collision ? "#ef9b79" : "#73dcca",
    true,
  );
  for (const side of [-1, 1]) {
    for (let leg = 0; leg < 3; leg++) {
      const x = 0.22 - leg * 0.27;
      faces.push({
        points: [
          [x, side * 0.12, 0.48],
          [x - 0.14, side * 0.5, 0.26],
          [x + 0.08, side * 0.68, 0.04],
        ].map((p) => local(p as Vec)),
        color: "#b4c7c5",
        line: true,
      });
    }
  }
  ellipsoid([-0.3, 0, 0.55], [0.43, 0.23, 0.24], "#899c94");
  ellipsoid([0.05, 0, 0.63], [0.26, 0.26, 0.27], "#acb8a8");
  ellipsoid([0.36, 0, 0.68], [0.22, 0.22, 0.21], "#bcc3ad");
  for (const side of [-1, 1]) {
    ellipsoid([0.43, side * 0.15, 0.74], [0.12, 0.105, 0.135], "#c27b64");
    ellipsoid([-0.28, side * 0.29, 0.85], [0.51, 0.19, 0.035], "#abc9c9b0");
  }
  faces.sort(
    (a, b) =>
      a.points.reduce((v, p) => v + depth(p), 0) / a.points.length -
      b.points.reduce((v, p) => v + depth(p), 0) / b.points.length,
  );
  for (const face of faces) paint(face.points, face.color, face.line);
}

export default function TrainingScene({
  preview: incoming,
  live,
  phase,
}: {
  preview?: TrainingPreview;
  live: boolean;
  phase: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const previous = useRef<TrainingPreview | undefined>(undefined);
  const [paused, setPaused] = useState(false);
  const [frozen, setFrozen] = useState<TrainingPreview>();
  const preview = paused ? frozen : incoming;
  const [visible, setVisible] = useState(true);
  const [angle, setAngle] = useState(-0.6);
  const [supported, setSupported] = useState(true);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) =>
      setVisible(entry.isIntersecting),
    );
    if (holder.current) observer.observe(holder.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = canvas.current;
    if (!element || !preview || paused || !visible) return;
    if (!element.getContext("2d")) {
      setSupported(false);
      return;
    }
    const current = preview;
    const old = previous.current;
    const interpolate =
      live &&
      phase === "collecting" &&
      old?.episode === current.episode &&
      old.captured_at !== current.captured_at &&
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = performance.now();
    let timer: ReturnType<typeof setTimeout> | undefined;
    function frame() {
      if (document.hidden) return;
      const t = interpolate
        ? Math.min(1, (performance.now() - start) / 400)
        : 1;
      const from = old?.pose ?? current.pose;
      const turn = Math.atan2(
        Math.sin(current.pose.yaw - from.yaw),
        Math.cos(current.pose.yaw - from.yaw),
      );
      draw(
        element!,
        current,
        {
          x: from.x + (current.pose.x - from.x) * t,
          y: from.y + (current.pose.y - from.y) * t,
          yaw: from.yaw + turn * t,
        },
        angle,
      );
      if (t < 1) timer = setTimeout(frame, 50); // At most 20 FPS, then idle.
    }
    frame();
    const visibility = () => {
      clearTimeout(timer);
      frame();
    };
    document.addEventListener("visibilitychange", visibility);
    previous.current = current;
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [preview, paused, visible, angle, live, phase]);

  const age = preview
    ? Math.max(0, Math.floor(Date.now() / 1000 - preview.captured_at))
    : 0;
  const state = paused
    ? "Preview paused"
    : !live
      ? "Last recorded scene"
      : phase !== "collecting"
        ? "Optimizing · holding last scene"
        : age > 15
          ? "Waiting for a fresh sample"
          : "Live · sampled view";
  return (
    <section className="training-panel training-scene">
      <div className="training-panel-heading">
        <div>
          <h2>A fly’s-eye on training</h2>
          <p>3D navigation arena · environment 1</p>
        </div>
        <button
          type="button"
          className="training-scene-button"
          onClick={() => {
            setFrozen(incoming);
            setPaused((p) => !p);
          }}
          disabled={!preview}
        >
          {paused ? "Resume preview" : "Pause preview"}
        </button>
      </div>
      <div className="training-scene-viewport" ref={holder}>
        <canvas
          ref={canvas}
          width={960}
          height={460}
          role="img"
          aria-label="3D training arena showing the fly, obstacles, goal and sampled path"
          hidden={!preview || !supported}
        />
        {preview && supported ? (
          <>
            <div className="training-scene-badge">
              <span />
              {state}
            </div>
            <div className="training-scene-readout">
              STEP {preview.step.toLocaleString()}
              <br />
              {preview.simulation_seconds.toFixed(1)}s simulated · sample {age}s
              ago
            </div>
          </>
        ) : (
          <div className="training-scene-empty">
            <strong>
              {supported
                ? "Waiting for arena snapshots"
                : "Preview unavailable in this browser"}
            </strong>
            <span>
              {supported
                ? "New trainer runs share a sampled view during experience collection."
                : "Training metrics remain available below."}
            </span>
          </div>
        )}
      </div>
      <div className="training-scene-foot">
        <div>
          <span className="training-scene-key" /> Sampled path{" "}
          <span className="training-scene-key goal" /> Goal
        </div>
        <label>
          Orbit{" "}
          <input
            aria-label="Orbit camera"
            type="range"
            min={-3.14}
            max={3.14}
            step={0.01}
            value={angle}
            onChange={(e) => setAngle(Number(e.target.value))}
            disabled={paused || !preview}
          />
        </label>
      </div>
      <p className="training-caption">
        Actual position and heading, shown with a stylized fly. Snapshots skip
        intermediate steps; movement between samples is illustrative. Training
        runs independently.
      </p>
    </section>
  );
}
