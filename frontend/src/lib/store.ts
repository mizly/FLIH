import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import type { QueueEntry, Robot } from "./campus";
type State = {
  queue: (QueueEntry & { session: string })[];
  robot: Robot | null;
  challenges: Record<string, { id: string; answer: string; expires: number }>;
};
export const RESERVATION_TIMEOUT_MS = 90 * 1000;
const globals = globalThis as typeof globalThis & {
  flihLock?: Promise<unknown>;
};
const directory = path.join(process.cwd(), ".data");
const filename = path.join(directory, "flih.json");
export function transaction<T>(
  fn: (state: State) => T | Promise<T>,
): Promise<T> {
  const task = (globals.flihLock ?? Promise.resolve()).then(async () => {
    await mkdir(directory, { recursive: true });
    let state: State;
    try {
      state = JSON.parse(await readFile(filename, "utf8"));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      state = { queue: [], robot: null, challenges: {} };
    }
    const now = Date.now();
    state.queue = state.queue.filter(
      (entry) =>
        now - (entry.lastSeenAt ?? entry.createdAt) < RESERVATION_TIMEOUT_MS,
    );
    for (const [key, value] of Object.entries(state.challenges))
      if (value.expires < now) delete state.challenges[key];
    const result = await fn(state);
    const temporary = `${filename}.${randomUUID()}.tmp`;
    await writeFile(temporary, JSON.stringify(state), "utf8");
    await rename(temporary, filename);
    return result;
  });
  globals.flihLock = task.catch(() => {});
  return task;
}
