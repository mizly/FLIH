import { timingSafeEqual } from "node:crypto";
import { createServer } from "node:http";
import next from "next";
import nextEnv from "@next/env";
import { WebSocket, WebSocketServer } from "ws";

const dev = process.argv.includes("--dev");
// Render and other managed hosts proxy traffic to the process over the
// container network, so the HTTP/WebSocket server must listen on all
// interfaces. Keep localhost as an explicit override for local development.
const hostname = process.env.HOSTNAME || "0.0.0.0";
const port = Number.parseInt(process.env.PORT || "3000", 10);
const projectDir = process.cwd();

nextEnv.loadEnvConfig(projectDir, dev);

const app = next({ dev, dir: "frontend", hostname, port });
const handle = app.getRequestHandler();
const server = createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("ok");
    return;
  }

  handle(request, response);
});
const controlServer = new WebSocketServer({ noServer: true });
const robotServer = new WebSocketServer({ noServer: true });
const cameraServer = new WebSocketServer({ noServer: true });
const viewerServer = new WebSocketServer({ noServer: true });
const lidarServer = new WebSocketServer({ noServer: true });
const scanServer = new WebSocketServer({ noServer: true });

let robot = null;
let activeController = null;
let sequence = 0;
let lastDriveAt = 0;
const controllers = new Set();

let camera = null;
const viewers = new Set();

// The LiDAR is the camera arrangement again with a different payload: the robot
// publishes to /ws/lidar and browsers watch /ws/scan. It gets its own pair rather
// than sharing the video sockets so the plot keeps working when the cameras are
// down, and so a scan is never mistaken for a JPEG by either end.
let lidar = null;
const scanViewers = new Set();

// A 640x360 q70 JPEG is about 22 KB; the cap is generous enough for a 1280x720
// frame and still small enough that a confused publisher cannot post a blob at us.
const MAX_FRAME_BYTES = 512 * 1024;
// Past this much unflushed video a viewer is not keeping up. Frames are dropped
// rather than queued, so a slow browser falls behind in time instead of in memory.
const VIEWER_BACKLOG_LIMIT = 1024 * 1024;
// A 667-point turn rounded the way backend/lidar_stream.py rounds it is about 10 KB.
// The cap leaves room for a faster scanner and still refuses a blob.
const MAX_SCAN_BYTES = 64 * 1024;
const SCAN_BACKLOG_LIMIT = 256 * 1024;
// Give the LiDAR process fresh camera context for OMNI without copying the full
// 15 fps stream onto its socket. Each pane is sampled independently.
const PERCEPTION_FRAME_INTERVAL_MS = Number.parseInt(process.env.ROBOT_PERCEPTION_FRAME_INTERVAL_MS || "100", 10);
const lastPerceptionFrameAt = new Map();

function sameSecret(provided) {
  const expected = process.env.ROBOT_API_KEY || "";
  return Boolean(expected) &&
    Buffer.byteLength(expected) === Buffer.byteLength(provided) &&
    timingSafeEqual(Buffer.from(expected), Buffer.from(provided));
}

function reject(socket, status, message) {
  socket.write(`HTTP/1.1 ${status}\r\nConnection: close\r\n\r\n${message}`);
  socket.destroy();
}

function send(socket, payload) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(payload));
}

function broadcastStatus() {
  for (const controller of controllers) {
    send(controller, {
      type: "status",
      robotConnected: robot?.readyState === WebSocket.OPEN,
      controllerAvailable: activeController === null || activeController === controller,
    });
  }
}

function broadcastCameraStatus() {
  const payload = { type: "camera-status", online: camera?.readyState === WebSocket.OPEN };
  for (const viewer of viewers) send(viewer, payload);
}

function broadcastLidarStatus() {
  const payload = { type: "lidar-status", online: lidar?.readyState === WebSocket.OPEN };
  for (const viewer of scanViewers) send(viewer, payload);
}

function stopRobot(reason) {
  sequence += 1;
  const command = { type: "drive", forward: 0, turn: 0, sequence, sentAt: Date.now(), reason };
  send(robot, command);
  send(lidar, command);
}

function releaseController(controller, reason) {
  if (activeController !== controller) return;
  stopRobot(reason);
  activeController = null;
  lastDriveAt = 0;
  broadcastStatus();
}

function validOrigin(request) {
  const origin = request.headers.origin;
  if (!origin) return false;
  try {
    return new URL(origin).host === request.headers.host;
  } catch {
    return false;
  }
}

server.on("upgrade", (request, socket, head) => {
  const pathname = new URL(request.url || "/", "http://localhost").pathname;

  if (pathname === "/ws/robot") {
    const provided = request.headers.authorization?.replace(/^Bearer /, "") || "";
    if (!sameSecret(provided)) return reject(socket, "401 Unauthorized", "Unauthorized");
    robotServer.handleUpgrade(request, socket, head, (websocket) => {
      robotServer.emit("connection", websocket, request);
    });
    return;
  }

  if (pathname === "/ws/camera") {
    const provided = request.headers.authorization?.replace(/^Bearer /, "") || "";
    if (!sameSecret(provided)) return reject(socket, "401 Unauthorized", "Unauthorized");
    cameraServer.handleUpgrade(request, socket, head, (websocket) => {
      cameraServer.emit("connection", websocket, request);
    });
    return;
  }

  if (pathname === "/ws/lidar") {
    const provided = request.headers.authorization?.replace(/^Bearer /, "") || "";
    if (!sameSecret(provided)) return reject(socket, "401 Unauthorized", "Unauthorized");
    lidarServer.handleUpgrade(request, socket, head, (websocket) => {
      lidarServer.emit("connection", websocket, request);
    });
    return;
  }

  if (pathname === "/ws/scan") {
    if (!validOrigin(request)) return reject(socket, "403 Forbidden", "Forbidden");
    scanServer.handleUpgrade(request, socket, head, (websocket) => {
      scanServer.emit("connection", websocket, request);
    });
    return;
  }

  if (pathname === "/ws/video") {
    if (!validOrigin(request)) return reject(socket, "403 Forbidden", "Forbidden");
    viewerServer.handleUpgrade(request, socket, head, (websocket) => {
      viewerServer.emit("connection", websocket, request);
    });
    return;
  }

  if (pathname === "/ws/control") {
    if (!validOrigin(request)) return reject(socket, "403 Forbidden", "Forbidden");
    controlServer.handleUpgrade(request, socket, head, (websocket) => {
      controlServer.emit("connection", websocket, request);
    });
  }
});

cameraServer.on("connection", (socket) => {
  if (camera && camera !== socket) camera.close(1012, "Replaced by a new camera connection");
  camera = socket;
  socket.isAlive = true;
  socket.on("pong", () => { socket.isAlive = true; });
  socket.on("message", (raw, isBinary) => {
    // [1 byte camera index][JPEG]. The server relays the bytes without decoding
    // them; only the length and the framing are its business.
    if (!isBinary || raw.length < 2 || raw.length > MAX_FRAME_BYTES) return;
    const pane = raw[0];
    const now = Date.now();
    if (lidar?.readyState === WebSocket.OPEN && lidar.bufferedAmount <= SCAN_BACKLOG_LIMIT &&
        now - (lastPerceptionFrameAt.get(pane) || 0) >= PERCEPTION_FRAME_INTERVAL_MS) {
      lidar.send(raw, { binary: true });
      lastPerceptionFrameAt.set(pane, now);
    }
    for (const viewer of viewers) {
      if (viewer.readyState !== WebSocket.OPEN) continue;
      if (viewer.bufferedAmount > VIEWER_BACKLOG_LIMIT) continue;
      viewer.send(raw, { binary: true });
    }
  });
  socket.on("close", () => {
    if (camera === socket) camera = null;
    broadcastCameraStatus();
  });
  socket.on("error", () => {});
  broadcastCameraStatus();
});

viewerServer.on("connection", (socket) => {
  viewers.add(socket);
  socket.isAlive = true;
  socket.on("pong", () => { socket.isAlive = true; });
  // Viewers only watch. Anything they send is a protocol error.
  socket.on("message", (raw) => { if (raw.length > 1024) socket.close(1009, "Message too large"); });
  socket.on("close", () => viewers.delete(socket));
  socket.on("error", () => {});
  send(socket, { type: "camera-status", online: camera?.readyState === WebSocket.OPEN });
});

lidarServer.on("connection", (socket) => {
  if (lidar && lidar !== socket) lidar.close(1012, "Replaced by a new LiDAR connection");
  lidar = socket;
  socket.isAlive = true;
  socket.on("pong", () => { socket.isAlive = true; });
  socket.on("message", (raw, isBinary) => {
    // One JSON scan per revolution. The server relays the text without parsing it;
    // only the length and the framing are its business, as with camera frames.
    if (isBinary || raw.length > MAX_SCAN_BYTES) return;
    for (const viewer of scanViewers) {
      if (viewer.readyState !== WebSocket.OPEN) continue;
      if (viewer.bufferedAmount > SCAN_BACKLOG_LIMIT) continue;
      viewer.send(raw, { binary: false });
    }
  });
  socket.on("close", () => {
    if (lidar === socket) lidar = null;
    broadcastLidarStatus();
  });
  socket.on("error", () => {});
  // Until an active controller sends the next frame, stopped is the only safe
  // direction assumption for a newly connected indicator.
  send(socket, { type: "drive", forward: 0, turn: 0, sequence, sentAt: Date.now() });
  broadcastLidarStatus();
});

scanServer.on("connection", (socket) => {
  scanViewers.add(socket);
  socket.isAlive = true;
  socket.on("pong", () => { socket.isAlive = true; });
  // Viewers only watch. Anything they send is a protocol error.
  socket.on("message", (raw) => { if (raw.length > 1024) socket.close(1009, "Message too large"); });
  socket.on("close", () => scanViewers.delete(socket));
  socket.on("error", () => {});
  send(socket, { type: "lidar-status", online: lidar?.readyState === WebSocket.OPEN });
});

robotServer.on("connection", (socket) => {
  if (robot && robot !== socket) {
    stopRobot("robot-replaced");
    robot.close(1012, "Replaced by a new robot connection");
  }
  robot = socket;
  socket.isAlive = true;
  socket.on("pong", () => { socket.isAlive = true; });
  socket.on("message", (raw) => {
    if (raw.length > 4096) return;
    try {
      const message = JSON.parse(raw.toString());
      if (message?.type !== "ack") return;
      for (const controller of controllers) send(controller, message);
    } catch {}
  });
  socket.on("close", () => {
    if (robot !== socket) return;
    robot = null;
    stopRobot("robot-disconnected");
    activeController = null;
    lastDriveAt = 0;
    broadcastStatus();
  });
  socket.on("error", () => {});
  send(socket, { type: "ready", protocol: 1 });
  broadcastStatus();
});

controlServer.on("connection", (socket) => {
  controllers.add(socket);
  socket.isAlive = true;
  socket.on("pong", () => { socket.isAlive = true; });
  broadcastStatus();

  socket.on("message", (raw) => {
    if (raw.length > 1024) return socket.close(1009, "Message too large");
    let message;
    try { message = JSON.parse(raw.toString()); } catch { return; }
    if (
      message?.type !== "drive" ||
      !Number.isFinite(message.forward) ||
      !Number.isFinite(message.turn) ||
      ![-1, 0, 1].includes(message.forward) ||
      ![-1, 0, 1].includes(message.turn)
    ) return;

    const isStop = message.forward === 0 && message.turn === 0;
    if (!isStop && activeController && activeController !== socket) {
      return send(socket, { type: "error", code: "controller-busy", message: "Another browser is driving FLIH." });
    }
    if (!isStop && robot?.readyState !== WebSocket.OPEN) {
      return send(socket, { type: "error", code: "robot-offline", message: "The robot is not connected." });
    }
    if (isStop) return releaseController(socket, "controls-released");

    activeController = socket;
    lastDriveAt = Date.now();
    sequence += 1;
    const command = {
      type: "drive",
      forward: message.forward,
      turn: message.turn,
      sequence,
      sentAt: lastDriveAt,
    };
    send(robot, command);
    send(lidar, command);
    broadcastStatus();
  });

  socket.on("close", () => {
    controllers.delete(socket);
    releaseController(socket, "controller-disconnected");
  });
  socket.on("error", () => {});
});

setInterval(() => {
  if (activeController && Date.now() - lastDriveAt > 350) {
    releaseController(activeController, "command-timeout");
  }
  for (const socket of [...controllers, ...viewers, ...scanViewers,
                        ...(robot ? [robot] : []), ...(camera ? [camera] : []),
                        ...(lidar ? [lidar] : [])]) {
    if (!socket.isAlive) {
      socket.terminate();
      continue;
    }
    socket.isAlive = false;
    socket.ping();
  }
}, 250);

await app.prepare();
server.listen(port, hostname, () => {
  console.log(`> FLIH ready on http://${hostname}:${port}`);
});
