import { WebSocket } from "ws";

const base = "ws://127.0.0.1:3100";
const wait = (socket, predicate) => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("timeout")), 3000);
  socket.on("message", (raw) => {
    const data = JSON.parse(raw);
    if (predicate(data)) {
      clearTimeout(timer);
      resolve(data);
    }
  });
});

const unauthorized = new WebSocket(`${base}/ws/robot`);
const rejected = await new Promise((resolve) =>
  unauthorized.on("unexpected-response", (_request, response) => resolve(response.statusCode)),
);
if (rejected !== 401) throw new Error("Unauthorized robot was not rejected");

const control = new WebSocket(`${base}/ws/control`, {
  headers: { Origin: "http://127.0.0.1:3100" },
});
await new Promise((resolve) => control.on("open", resolve));
const robot = new WebSocket(`${base}/ws/robot`, {
  headers: { Authorization: "Bearer integration-test-secret" },
});
await new Promise((resolve) => robot.on("open", resolve));
await wait(control, (data) => data.type === "status" && data.robotConnected);

control.send(JSON.stringify({ type: "drive", forward: 1, turn: -1 }));
const drive = await wait(robot, (data) => data.type === "drive" && data.forward === 1);
control.send(JSON.stringify({ type: "drive", forward: 0, turn: 0 }));
const stop = await wait(robot, (data) => data.type === "drive" && data.forward === 0);

console.log(JSON.stringify({ rejected, drive, stop }));
control.close();
robot.close();
