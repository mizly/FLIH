import BrainViewer from "./brain-viewer";
import { ExternalLink } from "lucide-react";
import type { TrainingSnapshot } from "@/lib/training-types";

export default function TrainingBrain({
  phase,
  live,
  activity,
  connectome,
}: {
  phase: string;
  live: boolean;
  activity?: TrainingSnapshot["neural_activity"];
  connectome?: TrainingSnapshot["connectome"];
}) {
  const activityNodes = activity?.neurons ?? [];
  const state = !activity
    ? "Activity unavailable"
    : phase === "collecting" && live
      ? `Measured · episode ${activity.episode} · step ${activity.step.toLocaleString()}`
      : "Last measured collection state";

  return (
    <section className="training-panel training-brain">
      <div className="training-panel-heading training-brain-heading">
        <div>
          <h2>FAFB brain anatomy</h2>
          <p>FlyWire atlas · interactive 3D</p>
        </div>
        <a
          href="https://codex.flywire.ai/?dataset=fafb"
          target="_blank"
          rel="noreferrer"
          aria-label="Explore the FAFB connectome in Codex (opens in a new tab)"
        >
          Explore <ExternalLink size={12} />
        </a>
      </div>

      <div className="training-brain-stage">
        <div className="training-brain-status">
          <span />
          {state}
        </div>
        <BrainViewer />
        <div className="training-brain-count">
          <strong>{(connectome?.neurons ?? 139255).toLocaleString()}</strong>
          <span>source neurons</span>
        </div>
      </div>

      <div
        className="training-brain-legend"
        aria-label="Anatomy and measured state legend"
      >
        <span>
          <i className="positive" /> Positive state
        </span>
        <span>
          <i className="negative" /> Negative state
        </span>
        <span>
          <i className="unmeasured" /> Atlas surface
        </span>
      </div>
      {activityNodes.length ? (
        <div className="training-brain-ranked">
          <span>Strongest measured states</span>
          {activityNodes.slice(0, 4).map((neuron) => (
            <div key={neuron.index}>
              <code title={`FAFB root ID ${neuron.root_id}`}>
                {neuron.root_id}
              </code>
              <span>{neuron.kind}</span>
              <strong
                className={neuron.activation >= 0 ? "positive" : "negative"}
              >
                {neuron.activation >= 0 ? "+" : ""}
                {neuron.activation.toFixed(4)}
              </strong>
            </div>
          ))}
        </div>
      ) : (
        <div className="training-brain-unavailable">
          Start a new trainer run to stream measured hidden states.
        </div>
      )}
      <p className="training-caption">
        FlyWire-space neuropil atlas. Dots show anatomical surfaces; measured
        neuron states appear in the readout because their coordinates are not
        available.{" "}
        <a href="/brain/source.json" target="_blank" rel="noreferrer">
          Atlas source
        </a>
      </p>
    </section>
  );
}
