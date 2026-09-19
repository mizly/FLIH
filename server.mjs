import { timingSafeEqual } from "node:crypto";
import { createServer } from "node:http";
import next from "next";
import nextEnv from "@next/env";
import { WebSocket, WebSocketServer } from "ws";

const dev = process.argv.includes("--dev");
const hostname = process.env.HOSTNAME || "127.0.0.1";
const port = Number.parseInt(process.env.PORT || "3000", 10);
const projectDir = process.cwd();

nextEnv.loadEnvConfig(projectDir, dev);

const app = next({ dev, dir: "frontend", hostname, port });
const handle = app.getRequestHandler();
const server = createServer((request, response) => handle(request, response));
const controlServer = new WebSocketServer({ noServer: true });
const robotServer = new WebSocketServer({ noServer: true });

let robot = null;
let activeController = null;
let sequence = 0;
let lastDriveAt = 0;
const controllers = new Set();

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

function stopRobot(reason) {
  sequence += 1;
  send(robot, { type: "drive", forward: 0, turn: 0, sequence, sentAt: Date.now(), reason });
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

  if (pathname === "/ws/control") {
    if (!validOrigin(request)) return reject(socket, "403 Forbidden", "Forbidden");
    controlServer.handleUpgrade(request, socket, head, (websocket) => {
      controlServer.emit("connection", websocket, request);
    });
  }
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
    if (robot === socket) robot = null;
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
    send(robot, {
      type: "drive",
      forward: message.forward,
      turn: message.turn,
      sequence,
      sentAt: lastDriveAt,
    });
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
  for (const socket of [...controllers, ...(robot ? [robot] : [])]) {
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
