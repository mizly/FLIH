import { NextRequest, NextResponse } from "next/server";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { transaction } from "@/lib/store";
import { places, type PlaceId } from "@/lib/campus";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
function session(req: NextRequest) {
  const existing = req.cookies.get("flih-session")?.value;
  return existing && /^[a-f0-9-]{36}$/.test(existing) ? existing : randomUUID();
}
function response(data: unknown, id: string, status = 200) {
  const res = NextResponse.json(data, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
  res.cookies.set("flih-session", id, {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24 * 7,
    path: "/",
  });
  return res;
}
export async function GET(req: NextRequest) {
  const id = session(req);
  if (req.nextUrl.searchParams.get("challenge") === "1") {
    const a = Math.floor(Math.random() * 5) + 2;
    const b = Math.floor(Math.random() * 4) + 1;
    const challengeId = randomUUID();
    await transaction((state) => {
      state.challenges[id] = {
        id: challengeId,
        answer: String(a + b),
        expires: Date.now() + 300000,
      };
    });
    return response(
      {
        id: challengeId,
        question: `I have ${a} existential crises before lunch and ${b} after. How many crises is that?`,
        hint: "A tiny brain. A surprisingly big emotional workload.",
      },
      id,
    );
  }
  const data = await transaction((state) => {
    const mine = state.queue.find((entry) => entry.session === id);
    if (mine) mine.lastSeenAt = Date.now();
    return {
      queue: state.queue.map(
        ({ session: _session, lastSeenAt: _lastSeenAt, ...entry }) => entry,
      ),
      mine: mine?.id ?? null,
      robot: state.robot
        ? {
            ...state.robot,
            status:
              Date.now() - state.robot.updatedAt > 30000
                ? "offline"
                : state.robot.status,
          }
        : {
            x: 420 + Math.sin(Date.now() / 20000) * 45,
            y: 257,
            battery: 86,
            status: "available",
            updatedAt: Date.now(),
            demo: true,
          },
    };
  });
  return response(data, id);
}
export async function POST(req: NextRequest) {
  const id = session(req);
  const origin = req.headers.get("origin");
  if (origin) {
    try {
      if (new URL(origin).host !== req.headers.get("host"))
        return response(
          { error: "Please make your request from the FLIH website." },
          id,
          403,
        );
    } catch {
      return response({ error: "Invalid origin." }, id, 403);
    }
  }
  let body;
  try {
    body = await req.json();
  } catch {
    return response({ error: "Invalid request." }, id, 400);
  }
  if (!body || typeof body !== "object")
    return response({ error: "Invalid request." }, id, 400);
  const result = await transaction((state) => {
    if (body.action === "cancel") {
      state.queue = state.queue.filter((entry) => entry.session !== id);
      return { ok: true };
    }
    if (body.action === "heartbeat") {
      const mine = state.queue.find((entry) => entry.session === id);
      if (mine) mine.lastSeenAt = Date.now();
      return { ok: true, active: Boolean(mine) };
    }
    const username =
      typeof body.username === "string" ? body.username.trim() : "";
    if (!/^[\p{L}\p{N}_ .-]{2,20}$/u.test(username))
      return {
        error:
          "Use 2–20 letters, numbers, spaces, dots, dashes, or underscores.",
      };
    if (
      !places.some((p) => p.id === body.pickup) ||
      !places.some((p) => p.id === body.destination) ||
      body.pickup === body.destination
    )
      return { error: "Choose two different campus stops." };
    if (state.queue.some((entry) => entry.session === id))
      return { error: "You already have a spot in the queue." };
    if (
      state.queue.some(
        (entry) => entry.username.toLowerCase() === username.toLowerCase(),
      )
    )
      return { error: "That name is in the queue already. Try another alias." };
    if (state.queue.length >= 30)
      return { error: "The queue is full. This little brain needs a minute." };
    const challenge = state.challenges[id];
    delete state.challenges[id];
    if (
      !challenge ||
      challenge.id !== body.challengeId ||
      challenge.expires < Date.now() ||
      challenge.answer !== String(body.answer).trim()
    )
      return {
        error: "Not quite! Try a fresh brain check.",
        refreshChallenge: true,
      };
    state.queue.push({
      id: randomUUID(),
      session: id,
      username,
      pickup: body.pickup as PlaceId,
      destination: body.destination as PlaceId,
      createdAt: Date.now(),
      lastSeenAt: Date.now(),
    });
    return { ok: true };
  });
  return response(result, id, "error" in result ? 400 : 200);
}
export async function PATCH(req: NextRequest) {
  const secret = process.env.ROBOT_API_KEY;
  const provided =
    req.headers.get("authorization")?.replace(/^Bearer /, "") ?? "";
  if (
    !secret ||
    Buffer.byteLength(secret) !== Buffer.byteLength(provided) ||
    !timingSafeEqual(Buffer.from(secret), Buffer.from(provided))
  )
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  let body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  if (
    !body ||
    !Number.isFinite(body.x) ||
    !Number.isFinite(body.y) ||
    body.x < 0 ||
    body.x > 800 ||
    body.y < 0 ||
    body.y > 540 ||
    !Number.isFinite(body.battery) ||
    body.battery < 0 ||
    body.battery > 100 ||
    !["available", "guiding", "offline"].includes(body.status)
  )
    return NextResponse.json(
      {
        error: "Provide map x (0–800), y (0–540), battery (0–100), and status.",
      },
      { status: 400 },
    );
  await transaction((state) => {
    state.robot = {
      x: body.x,
      y: body.y,
      battery: body.battery,
      status: body.status,
      updatedAt: Date.now(),
      demo: false,
    };
    if (typeof body.completedId === "string")
      state.queue = state.queue.filter(
        (entry) => entry.id !== body.completedId,
      );
  });
  return NextResponse.json({ ok: true });
}
