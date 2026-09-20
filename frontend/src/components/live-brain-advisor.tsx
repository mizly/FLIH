"use client";

import { useEffect, useMemo, useState } from "react";
import BrainViewer from "./brain-viewer";
import type { FlyAdvice } from "./lidar-view";
import type { TrainingSnapshot } from "@/lib/training-types";

type Positions = Record<string, [number, number, number]>;

function decision(advice: FlyAdvice | null) {
  if (!advice) return "Waiting for live perception…";
  if (advice.status === "loading") return "Reading cameras and LiDAR…";
  if (advice.status === "error") return "My policy is unavailable.";
  if (advice.status === "idle") return "Start moving—I'll think ahead.";
  if (advice.motion === "stop") return "Stop here.";
  if (advice.motion === "reverse") {
    if (advice.turn === "left") return "Reverse to the left.";
    if (advice.turn === "right") return "Reverse to the right.";
    return "Move backward.";
  }
  if (advice.turn === "left") return "Move forward and turn left.";
  if (advice.turn === "right") return "Move forward and turn right.";
  return "Move straight ahead.";
}

export function LiveBrainAdvisor({ advice }: { advice: FlyAdvice | null }) {
  const [positions, setPositions] = useState<Positions | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    fetch("/brain/neuron-positions.json", { signal: abort.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Neuron positions unavailable");
        return response.json() as Promise<Positions>;
      })
      .then(setPositions)
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError"))
          setPositions({});
      });
    return () => abort.abort();
  }, []);

  const activity = useMemo<TrainingSnapshot["neural_activity"]>(() => {
    if (!advice?.activity) return undefined;
    const neurons = advice.activity.neurons.flatMap((neuron) => {
      const position = positions?.[neuron.rootId];
      return position
        ? [
            {
              index: neuron.index,
              root_id: neuron.rootId,
              kind: "interneuron" as const,
              activation: neuron.activation,
              magnitude: neuron.magnitude,
              position,
            },
          ]
        : [];
    });
    return {
      coordinate_status: positions === null ? "unavailable" : "available",
      captured_at: Date.now() / 1000,
      episode: "live",
      step: 0,
      semantics: advice.activity.semantics,
      neurons,
    };
  }, [advice, positions]);

  const mapped = activity?.neurons.length ?? 0;
  return (
    <div className="control-brain-stage">
      <BrainViewer activity={activity} autoRotate compact />
      <div
        className={`brain-speech is-${advice?.status ?? "waiting"}`}
        role="status"
        aria-live="polite"
      >
        <span>Next move</span>
        <strong>{decision(advice)}</strong>
      </div>
      <div
        className="control-brain-legend"
        aria-label="Live neural activity legend"
      >
        <span>
          <i className="positive" /> positive
        </span>
        <span>
          <i className="negative" /> negative
        </span>
        <strong>
          {mapped ? `${mapped} active neurons` : "awaiting activity"}
        </strong>
      </div>
    </div>
  );
}
