"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Radar, CircleOff } from "lucide-react";

type Link = "connecting" | "connected" | "disconnected";

// One message per revolution, exactly as backend/lidar_stream.py builds it.
// `angles` are radians in the robot frame - 0 forward, positive to the left - and
// `ranges` are metres with 0.0 meaning nothing came back. They line up index for
// index. backend/lidar.py is where that convention is set.
type Scan = {
  type: "scan";
  stamp: number;
  points: number;
  returns: number;
  hz: number;
  reportedHz: number;
  maxRange: number;
  demo: boolean;
  safetySignal?: "red" | "yellow" | "green";
  safetyDirection?: "forward" | "reverse" | "stopped";
  safetyClearance?: number | null;
  angles: number[];
  ranges: number[];
};

// A plot that has gone this long without a turn is blanked rather than left holding
// the last one. A stale scan is the one wrong answer that looks safe: it draws a
// clear path through obstacles that are still there.
const STALE_MS = 1500;
const ZOOMS = [2, 4, 8, 12];
const SIZE = 520;

type LidarViewProps = {
  onSafetySignalChange?: (signal: "red" | "yellow" | "green" | null) => void;
};

export function LidarView({ onSafetySignalChange }: LidarViewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const scanRef = useRef<Scan | null>(null);
  const lastScanRef = useRef(0);
  const [link, setLink] = useState<Link>("connecting");
  const [publisherOnline, setPublisherOnline] = useState(false);
  const [live, setLive] = useState(false);
  const [zoom, setZoom] = useState(4);
  const [summary, setSummary] = useState<Scan | null>(null);

  const draw = useCallback((scan: Scan | null, range: number) => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    const centre = SIZE / 2;
    // Leave a margin so the outermost ring and its label are not clipped.
    const scale = (centre - 26) / range;

    context.clearRect(0, 0, SIZE, SIZE);
    context.fillStyle = "#14161a";
    context.fillRect(0, 0, SIZE, SIZE);

    // Range rings, one per metre while they stay legible.
    const step = range <= 4 ? 1 : range <= 8 ? 2 : 3;
    context.font = "11px ui-monospace, monospace";
    context.textAlign = "center";
    for (let metres = step; metres <= range; metres += step) {
      context.beginPath();
      context.arc(centre, centre, metres * scale, 0, Math.PI * 2);
      context.strokeStyle = "rgba(255,255,255,.1)";
      context.lineWidth = 1;
      context.stroke();
      context.fillStyle = "rgba(255,255,255,.34)";
      context.fillText(`${metres} m`, centre, centre - metres * scale - 5);
    }

    // Cross hairs: vertical is the robot's forward axis, horizontal is its sides.
    context.beginPath();
    context.moveTo(centre, 10); context.lineTo(centre, SIZE - 10);
    context.moveTo(10, centre); context.lineTo(SIZE - 10, centre);
    context.strokeStyle = "rgba(255,255,255,.08)";
    context.stroke();

    if (scan) {
      // Robot frame is x forward, y left. The plot puts forward up and left left,
      // so a point at (range, angle) lands at (-sin, -cos) from the centre.
      context.fillStyle = scan.demo ? "#e0a33c" : "#7fd6a0";
      for (let index = 0; index < scan.ranges.length; index += 1) {
        const metres = scan.ranges[index];
        // 0.0 is "no return", not "a hit at zero range": it must not be drawn at
        // the robot's own position, where it would read as an imminent collision.
        if (!(metres > 0) || metres > range) continue;
        const angle = scan.angles[index];
        const x = centre - Math.sin(angle) * metres * scale;
        const y = centre - Math.cos(angle) * metres * scale;
        context.fillRect(x - 1.1, y - 1.1, 2.2, 2.2);
      }
    }

    // The robot itself, nose up.
    context.beginPath();
    context.moveTo(centre, centre - 9);
    context.lineTo(centre - 6, centre + 6);
    context.lineTo(centre + 6, centre + 6);
    context.closePath();
    context.fillStyle = live ? "#f4f2ec" : "#5b5f66";
    context.fill();
  }, [live]);

  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      setLink("connecting");
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/scan`);

      socket.addEventListener("open", () => setLink("connected"));
      socket.addEventListener("message", (event) => {
        let data: Scan | { type: string; online?: boolean };
        try { data = JSON.parse(String(event.data)); } catch { return; }
        if (data.type === "lidar-status") {
          setPublisherOnline(Boolean((data as { online?: boolean }).online));
          return;
        }
        if (data.type !== "scan") return;
        const scan = data as Scan;
        if (!Array.isArray(scan.ranges) || !Array.isArray(scan.angles)) return;
        scanRef.current = scan;
        lastScanRef.current = performance.now();
        onSafetySignalChange?.(scan.safetySignal ?? null);
        setSummary(scan);
      });
      socket.addEventListener("close", () => {
        setLink("disconnected");
        setPublisherOnline(false);
        onSafetySignalChange?.(null);
        if (!disposed) retryTimer = setTimeout(connect, 1500);
      });
      socket.addEventListener("error", () => socket?.close());
    };

    connect();
    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close(1000, "Page closed");
    };
  }, []);

  // Redraw whenever a turn or the zoom changes. Six to ten scans a second is well
  // inside what a canvas of this size does comfortably, so there is no frame loop.
  useEffect(() => { draw(scanRef.current, zoom); }, [draw, summary, zoom]);

  useEffect(() => {
    const timer = setInterval(() => {
      const fresh = lastScanRef.current > 0 && performance.now() - lastScanRef.current < STALE_MS;
      setLive(fresh);
      if (!fresh && scanRef.current !== null) {
        scanRef.current = null;
        onSafetySignalChange?.(null);
        setSummary(null);
      }
    }, 500);
    return () => clearInterval(timer);
  }, [onSafetySignalChange]);

  const status = live
    ? summary?.demo
      ? "Demo scan — synthetic, nothing here is measured."
      : `Scanning. ${summary?.returns ?? 0} of ${summary?.points ?? 0} returns at ${summary?.hz?.toFixed(1) ?? "0.0"} Hz.`
    : link !== "connected"
      ? "Connecting to the scan link…"
      : publisherOnline
        ? "LiDAR link up, waiting for a turn…"
        : "No LiDAR stream. Start backend/lidar_stream.py on the robot.";

  return (
    <section className="lidar-panel" aria-label="Robot LiDAR scan">
      <div className={`camera-status ${live && !summary?.demo ? "is-live" : ""}`} role="status" aria-live="polite">
        {live ? <Radar size={16} /> : <CircleOff size={16} />}
        <span>{status}</span>
      </div>

      <figure className={`lidar-plot ${live ? "is-live" : ""} ${summary?.demo ? "is-demo" : ""}`}>
        <canvas ref={canvasRef} width={SIZE} height={SIZE} aria-label="Top-down LiDAR scan, robot facing up" />
        {!live && <span className="camera-placeholder">No scan</span>}
        <figcaption>
          <span>Top-down · forward is up</span>
          <span className="lidar-zooms">
            {ZOOMS.map((metres) => (
              <button
                key={metres}
                type="button"
                className={metres === zoom ? "lidar-zoom is-active" : "lidar-zoom"}
                onClick={() => setZoom(metres)}
                aria-pressed={metres === zoom}
              >
                {metres} m
              </button>
            ))}
          </span>
        </figcaption>
      </figure>
    </section>
  );
}
