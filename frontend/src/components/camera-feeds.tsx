"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, Video, VideoOff } from "lucide-react";
import type { OmniReading } from "@/lib/perception";

type Link = "connecting" | "connected" | "disconnected";
type Feed = { live: boolean; fps: number };

const CAMERA_LABELS = ["Left camera", "Right camera"];
// A pane that has gone this long without a frame is blanked rather than left
// holding the last image, which an operator would otherwise read as live video.
const STALE_MS = 1500;

function emptyFeeds(): Feed[] {
  return CAMERA_LABELS.map(() => ({ live: false, fps: 0 }));
}

export function CameraFeeds({ perception }: { perception: OmniReading | null }) {
  const canvasRefs = useRef<(HTMLCanvasElement | null)[]>([]);
  const decodingRef = useRef<boolean[]>([]);
  const lastFrameRef = useRef<number[]>([]);
  const fpsRef = useRef<number[]>([]);
  const [link, setLink] = useState<Link>("connecting");
  const [publisherOnline, setPublisherOnline] = useState(false);
  const [feeds, setFeeds] = useState<Feed[]>(emptyFeeds);

  const blank = useCallback((index: number) => {
    const canvas = canvasRefs.current[index];
    if (!canvas) return;
    canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    lastFrameRef.current[index] = 0;
    fpsRef.current[index] = 0;
  }, []);

  const draw = useCallback(async (index: number, jpeg: ArrayBuffer) => {
    const canvas = canvasRefs.current[index];
    // Dropping a frame while the previous one is still decoding is the browser's
    // own backpressure: it keeps decode work from piling up behind the socket and
    // keeps frames from landing out of order.
    if (!canvas || decodingRef.current[index]) return;
    decodingRef.current[index] = true;
    try {
      const bitmap = await createImageBitmap(new Blob([jpeg], { type: "image/jpeg" }));
      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
      }
      canvas.getContext("2d")?.drawImage(bitmap, 0, 0);
      bitmap.close();

      const now = performance.now();
      const previous = lastFrameRef.current[index];
      lastFrameRef.current[index] = now;
      if (previous) {
        const instant = 1000 / (now - previous);
        const smoothed = fpsRef.current[index];
        fpsRef.current[index] = smoothed ? smoothed * 0.8 + instant * 0.2 : instant;
      }
    } catch {
      // A truncated or corrupt frame is not worth tearing the feed down for.
    } finally {
      decodingRef.current[index] = false;
    }
  }, []);

  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      setLink("connecting");
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/video`);
      socket.binaryType = "arraybuffer";

      socket.addEventListener("open", () => setLink("connected"));
      socket.addEventListener("message", (event) => {
        if (typeof event.data === "string") {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "camera-status") setPublisherOnline(Boolean(data.online));
          } catch {}
          return;
        }
        // [1 byte pane index][JPEG], matching backend/camera_stream.py. The byte is
        // a view position - 0 left, 1 right - and the publisher decides which CSI
        // port feeds each one, so nothing here should reorder the panes.
        const buffer = event.data as ArrayBuffer;
        if (buffer.byteLength < 2) return;
        const index = new Uint8Array(buffer, 0, 1)[0];
        if (index >= CAMERA_LABELS.length) return;
        void draw(index, buffer.slice(1));
      });
      socket.addEventListener("close", () => {
        setLink("disconnected");
        setPublisherOnline(false);
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
  }, [draw]);

  useEffect(() => {
    const timer = setInterval(() => {
      const now = performance.now();
      setFeeds((current) => {
        let changed = false;
        const next = current.map((feed, index) => {
          const last = lastFrameRef.current[index] || 0;
          const live = last > 0 && now - last < STALE_MS;
          if (!live && last > 0) blank(index);
          const fps = live ? Math.round(fpsRef.current[index] || 0) : 0;
          if (live !== feed.live || fps !== feed.fps) changed = true;
          return { live, fps };
        });
        return changed ? next : current;
      });
    }, 500);
    return () => clearInterval(timer);
  }, [blank]);

  const anyLive = feeds.some((feed) => feed.live);
  const status = anyLive
    ? "Live from the robot."
    : link !== "connected"
      ? "Connecting to the video link…"
      : publisherOnline
        ? "Camera link up, waiting for frames…"
        : "No camera stream. Start backend/camera_stream.py on the robot.";

  const perceptionStatus = perception?.error
    ? "AI check unavailable"
    : perception?.obstacle_ahead === true
      ? perception.obstacle_summary || "Obstacle ahead"
      : perception?.obstacle_ahead === false
        ? perception.obstacle_summary || "Path looks clear ahead"
        : anyLive
          ? "AI check pending"
          : "No visual check";
  const perceptionState = perception?.error
    ? "error"
    : perception?.obstacle_ahead === true
      ? "danger"
      : perception?.obstacle_ahead === false
        ? "clear"
        : "pending";
  const PerceptionIcon = perceptionState === "danger"
    ? AlertTriangle
    : perceptionState === "clear"
      ? CheckCircle2
      : CircleHelp;

  return (
    <section className="camera-panel" aria-label="Robot camera feeds">
      <div className={`camera-status ${anyLive ? "is-live" : ""}`} role="status" aria-live="polite">
        {anyLive ? <Video size={16} /> : <VideoOff size={16} />}
        <span>{status}</span>
      </div>
      <div
        className={`camera-perception-status is-${perceptionState}`}
        role="status"
        aria-live="polite"
        title={perception?.reasoning || perception?.error || undefined}
      >
        <PerceptionIcon size={19} />
        <span><strong>Dashboard:</strong> {perceptionStatus}</span>
        {perception?.updated_at && (
          <small>{Math.max(0, Math.round(Date.now() / 1000 - perception.updated_at))}s ago</small>
        )}
      </div>

      <div className="camera-grid">
        {CAMERA_LABELS.map((label, index) => (
          <figure key={label} className={`camera-feed ${feeds[index].live ? "is-live" : ""}`}>
            <canvas
              ref={(element) => { canvasRefs.current[index] = element; }}
              width={640}
              height={360}
              aria-label={`${label} video feed`}
            />
            {!feeds[index].live && <span className="camera-placeholder">No signal</span>}
            <figcaption>
              <span>{label}</span>
              {feeds[index].live && <span className="camera-fps">{feeds[index].fps} fps</span>}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
