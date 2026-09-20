import { readFile } from "node:fs/promises";
import path from "node:path";
import type { TrainingSnapshot } from "./training-types";

type Positions = Record<string, [number, number, number]>;
let cached: Promise<Positions> | undefined;

async function positions(): Promise<Positions> {
  // Support both `next frontend` and the custom server's project root.
  for (const directory of ["public/brain", "frontend/public/brain"]) {
    try {
      return JSON.parse(
        await readFile(
          /* turbopackIgnore: true */ path.join(
            process.cwd(),
            directory,
            "neuron-positions.json",
          ),
          "utf8",
        ),
      );
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
  }
  throw new Error("Neuron position asset unavailable");
}

export async function locateNeuralActivity(
  activity: TrainingSnapshot["neural_activity"],
  dataset?: string,
) {
  if (!activity) return activity;
  // Root IDs are specific to the materialization; never reuse a different map.
  if (dataset !== "FAFB v783")
    return { ...activity, coordinate_status: "unsupported_dataset" as const };
  try {
    cached ??= positions().catch((error) => {
      cached = undefined;
      throw error;
    });
    const lookup = await cached;
    return {
      ...activity,
      coordinate_status: "available" as const,
      neurons: activity.neurons.map((neuron) => ({
        ...neuron,
        position: lookup[neuron.root_id],
      })),
    };
  } catch {
    // An optional anatomy asset must not take down training metrics.
    return { ...activity, coordinate_status: "unavailable" as const };
  }
}
