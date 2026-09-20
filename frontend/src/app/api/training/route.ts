import { readFile, access } from "node:fs/promises";
import path from "node:path";
import type { TrainingSnapshot } from "@/lib/training-types";
import { locateNeuralActivity } from "@/lib/neuron-positions";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "no-store, max-age=0" };

async function snapshotPath() {
  if (process.env.FLY_GYM_TRAINING_FILE)
    return path.resolve(process.env.FLY_GYM_TRAINING_FILE);
  // Next runs from frontend; also support launching from the repository root.
  for (const root of [process.cwd(), path.dirname(process.cwd())]) {
    try {
      await access(
        path.join(root, "fly-gym", "train_connectome_rnn_dagger.py"),
      );
      return path.join(root, "fly-gym", "training", "latest.json");
    } catch {
      /* Try the next repository location. */
    }
  }
  throw new Error("Training directory unavailable");
}

export async function GET() {
  try {
    // Runtime telemetry is shared with Python, not an asset to bundle at build time.
    const run = JSON.parse(
      await readFile(/* turbopackIgnore: true */ await snapshotPath(), "utf8"),
    ) as TrainingSnapshot;
    if (
      run.schema_version !== 1 ||
      !Number.isFinite(run.updated_at) ||
      !run.config ||
      !Array.isArray(run.loss_history) ||
      !Array.isArray(run.episodes)
    ) {
      throw new Error("Unsupported training snapshot");
    }
    return Response.json(
      {
        run: {
          ...run,
          neural_activity: await locateNeuralActivity(
            run.neural_activity,
            run.connectome?.dataset,
          ),
        },
        stale:
          run.status === "running" && Date.now() / 1000 - run.updated_at > 15,
      },
      { headers },
    );
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return Response.json({ run: null, stale: false }, { headers });
    }
    return Response.json(
      { error: "Training metrics are temporarily unavailable." },
      { status: 503, headers },
    );
  }
}
