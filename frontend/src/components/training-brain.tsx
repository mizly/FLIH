import { ExternalLink } from "lucide-react";
import type { TrainingSnapshot } from "@/lib/training-types";

type BrainNode = {
  x: number;
  y: number;
};

const clusters = [
  { cx: 76, cy: 128, rx: 61, ry: 68, count: 34 },
  { cx: 156, cy: 105, rx: 72, ry: 86, count: 46 },
  { cx: 264, cy: 105, rx: 72, ry: 86, count: 46 },
  { cx: 344, cy: 128, rx: 61, ry: 68, count: 34 },
];

const nodes: BrainNode[] = clusters.flatMap((cluster, clusterIndex) =>
  Array.from({ length: cluster.count }, (_, index) => {
    const radius = Math.sqrt((index + 0.7) / cluster.count);
    const angle = index * 2.399963 + clusterIndex * 0.61;
    const x = cluster.cx + Math.cos(angle) * cluster.rx * radius;
    const y = cluster.cy + Math.sin(angle) * cluster.ry * radius;
    return { x, y };
  }),
);

const edges = nodes.flatMap((_, index) => {
  const connections = [index + 5, index + 11];
  if (index % 4 === 0) connections.push(nodes.length - 1 - index);
  return connections
    .filter((target) => target > index && target < nodes.length)
    .map((target) => [index, target] as const);
});

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
  const maxMagnitude = activityNodes[0]?.magnitude || 1;
  const state = !activity
    ? "Activity unavailable"
    : phase === "collecting" && live
      ? `Measured · episode ${activity.episode} · step ${activity.step.toLocaleString()}`
      : "Last measured collection state";

  return (
    <section className="training-panel training-brain">
      <div className="training-panel-heading training-brain-heading">
        <div>
          <h2>FAFB neural graph</h2>
          <p>Fixed anatomy · live training state</p>
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
        <svg
          viewBox="0 0 420 235"
          role="img"
          aria-label="Representative graph of the bilateral FAFB fly-brain connectome"
        >
          <defs>
            <radialGradient id="brain-glow">
              <stop offset="0" stopColor="#315c62" stopOpacity=".44" />
              <stop offset="1" stopColor="#13272d" stopOpacity=".05" />
            </radialGradient>
            <filter
              id="node-glow"
              x="-300%"
              y="-300%"
              width="700%"
              height="700%"
            >
              <feGaussianBlur stdDeviation="2.2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <g className="training-brain-lobes" aria-hidden="true">
            <ellipse cx="76" cy="128" rx="66" ry="72" />
            <ellipse cx="156" cy="105" rx="78" ry="91" />
            <ellipse cx="264" cy="105" rx="78" ry="91" />
            <ellipse cx="344" cy="128" rx="66" ry="72" />
            <path d="M174 172 C185 203 193 220 210 224 C227 220 235 203 246 172" />
          </g>

          <g className="training-brain-edges" aria-hidden="true">
            {edges.map(([from, to], index) => (
              <line
                key={`${from}-${to}`}
                x1={nodes[from].x}
                y1={nodes[from].y}
                x2={nodes[to].x}
                y2={nodes[to].y}
                className={
                  activityNodes.length && index % 17 === 0
                    ? "is-signal"
                    : undefined
                }
              />
            ))}
          </g>

          <g className="training-brain-nodes" aria-hidden="true">
            {nodes.map((node, index) => {
              const measured = activityNodes[index];
              const strength = measured ? measured.magnitude / maxMagnitude : 0;
              return (
                <circle
                  key={index}
                  cx={node.x}
                  cy={node.y}
                  r={measured ? 1.25 + strength * 2.5 : 0.75}
                  className={
                    measured
                      ? `${measured.kind} has-activity ${measured.activation >= 0 ? "positive" : "negative"}`
                      : "unmeasured"
                  }
                  opacity={measured ? 0.35 + strength * 0.65 : 0.18}
                >
                  {measured && (
                    <title>
                      FAFB {measured.root_id} · {measured.kind} · hidden state{" "}
                      {measured.activation.toFixed(5)}
                    </title>
                  )}
                </circle>
              );
            })}
          </g>
        </svg>
        <div className="training-brain-count">
          <strong>{(connectome?.neurons ?? 139255).toLocaleString()}</strong>
          <span>source neurons</span>
        </div>
      </div>

      <div className="training-brain-legend" aria-label="Neural graph legend">
        <span>
          <i className="positive" /> Positive state
        </span>
        <span>
          <i className="negative" /> Negative state
        </span>
        <span>
          <i className="unmeasured" /> Not in top sample
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
        Each bright node is a real FAFB neuron among the 96 strongest absolute
        hidden states from environment 1. Position is schematic; hover for the
        full root ID. This rate-based RNN does not emit biological spikes.
      </p>
    </section>
  );
}
