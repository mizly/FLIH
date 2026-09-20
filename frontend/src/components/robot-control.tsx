"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Bot, House, Radio, RotateCcw } from "lucide-react";
import { Fly } from "./fly";

type Connection = "connecting" | "connected" | "disconnected";
type Direction = "w" | "a" | "s" | "d";

const directionKeys = new Set<Direction>(["w", "a", "s", "d"]);

export function RobotControl() {
  const socketRef = useRef<WebSocket | null>(null);
  const pressedRef = useRef(new Set<Direction>());
  const [pressed, setPressed] = useState<Set<Direction>>(new Set());
  const [connection, setConnection] = useState<Connection>("connecting");
  const [robotConnected, setRobotConnected] = useState(false);
  const [controllerAvailable, setControllerAvailable] = useState(true);
  const [message, setMessage] = useState("Connecting to control server…");
  const enabled = connection === "connected" && robotConnected && controllerAvailable;

  const sendDrive = useCallback(() => {
    const socket = socketRef.current;
    if (socket?.readyState !== WebSocket.OPEN) return;
    const keys = pressedRef.current;
    socket.send(JSON.stringify({
      type: "drive",
      forward: Number(keys.has("w")) - Number(keys.has("s")),
      turn: Number(keys.has("d")) - Number(keys.has("a")),
    }));
  }, []);

  const releaseAll = useCallback(() => {
    if (pressedRef.current.size === 0) return;
    pressedRef.current = new Set();
    setPressed(new Set());
    sendDrive();
  }, [sendDrive]);

  const setKey = useCallback((key: Direction, down: boolean) => {
    const next = new Set(pressedRef.current);
    if (down) next.add(key); else next.delete(key);
    pressedRef.current = next;
    setPressed(next);
    sendDrive();
  }, [sendDrive]);

  useEffect(() => {
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;

    const connect = () => {
      setConnection("connecting");
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/control`);
      socketRef.current = socket;
      socket.addEventListener("open", () => {
        setConnection("connected");
        setMessage("Control link ready. Waiting for robot status…");
      });
      socket.addEventListener("message", (event) => {
        try {
          const data = JSON.parse(String(event.data));
          if (data.type === "status") {
            setRobotConnected(Boolean(data.robotConnected));
            setControllerAvailable(Boolean(data.controllerAvailable));
            setMessage(data.robotConnected ? "Robot connected — controls are live." : "Waiting for the robot to connect.");
          } else if (data.type === "error") {
            setMessage(data.message || "The command was rejected.");
          }
        } catch {}
      });
      socket.addEventListener("close", () => {
        if (socketRef.current === socket) socketRef.current = null;
        setConnection("disconnected");
        setRobotConnected(false);
        setMessage("Control link lost. Reconnecting…");
        if (!disposed) retryTimer = setTimeout(connect, 1500);
      });
    };

    connect();
    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      releaseAll();
      socketRef.current?.close(1000, "Page closed");
      socketRef.current = null;
    };
  }, [releaseAll]);

  useEffect(() => {
    const keyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase() as Direction;
      if (!directionKeys.has(key) || event.repeat || !enabled) return;
      event.preventDefault();
      setKey(key, true);
    };
    const keyUp = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase() as Direction;
      if (!directionKeys.has(key)) return;
      event.preventDefault();
      setKey(key, false);
    };
    window.addEventListener("keydown", keyDown);
    window.addEventListener("keyup", keyUp);
    window.addEventListener("blur", releaseAll);
    document.addEventListener("visibilitychange", releaseAll);
    return () => {
      window.removeEventListener("keydown", keyDown);
      window.removeEventListener("keyup", keyUp);
      window.removeEventListener("blur", releaseAll);
      document.removeEventListener("visibilitychange", releaseAll);
    };
  }, [enabled, releaseAll, setKey]);

  useEffect(() => {
    if (!enabled) releaseAll();
  }, [enabled, releaseAll]);

  // Load-bearing repeat: the server drops the controller after 350 ms without a
  // command and the Pico relay stops the motors after 500 ms, so holding a key has
  // to keep sending. See backend/TELEOP_SETUP.md before changing this interval.
  useEffect(() => {
    if (pressed.size === 0) return;
    const timer = setInterval(sendDrive, 100);
    return () => clearInterval(timer);
  }, [pressed, sendDrive]);

  const keyProps = (key: Direction) => ({
    onPointerDown: (event: React.PointerEvent<HTMLButtonElement>) => {
      event.currentTarget.setPointerCapture(event.pointerId);
      setKey(key, true);
    },
    onPointerUp: () => setKey(key, false),
    onPointerCancel: () => setKey(key, false),
    className: pressed.has(key) ? "drive-key is-pressed" : "drive-key",
    disabled: !enabled,
  });

  return (
    <main className="control-shell">
      <header className="control-header">
        <Link className="brand" href="/" aria-label="Back to FLIH home"><Fly small /><span>FLIH<span className="brand-dot">.</span></span></Link>
        <Link className="control-home" href="/"><House size={18} /> Route map</Link>
      </header>

      <section className="control-card" aria-labelledby="control-title">
        <div className="control-icon"><Bot size={34} /></div>
        <span className="wizard-eyebrow">Manual drive</span>
        <h1 id="control-title">Take the wheel.</h1>
        <p className="control-copy">Use WASD or hold the controls below. Releasing the keys stops FLIH immediately.</p>

        <div className={`control-connection ${robotConnected ? "is-online" : ""}`} role="status" aria-live="polite">
          <Radio size={17} />
          <span>{message}</span>
        </div>

        <div className="drive-grid" aria-label="Robot directional controls">
          <button {...keyProps("w")} aria-label="Drive forward"><kbd>W</kbd><ArrowUp size={22} /></button>
          <button {...keyProps("a")} aria-label="Turn left"><kbd>A</kbd><ArrowLeft size={22} /></button>
          <button type="button" className="drive-stop" onClick={releaseAll} aria-label="Stop robot"><RotateCcw size={20} /><span>STOP</span></button>
          <button {...keyProps("d")} aria-label="Turn right"><kbd>D</kbd><ArrowRight size={22} /></button>
          <button {...keyProps("s")} aria-label="Drive backward"><kbd>S</kbd><ArrowDown size={22} /></button>
        </div>

        {!controllerAvailable && <p className="control-warning">Another browser currently has control.</p>}
        <p className="control-safety">Keep the robot in sight. The server applies a 350 ms dead-man timeout if commands stop arriving.</p>
      </section>
    </main>
  );
}
