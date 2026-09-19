"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowLeft,
  ArrowUpRight,
  BrainCircuit,
  Check,
  Circle,
  Clock3,
  Database,
  Radio,
  Terminal,
} from "lucide-react";
import type { TrainingResponse } from "@/lib/training-types";

const number = (value: number) => value.toLocaleString();
const decimal = (value: number | null | undefined, digits = 4) =>
  value == null ? "—" : value.toFixed(digits);
function duration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m ${Math.floor(seconds % 60)}s`;
}

function MetricChart({
  title,
  subtitle,
  points,
  color,
  unit,
}: {
  title: string;
  subtitle: string;
  points: { x: number; y: number }[];
  color: string;
  unit: string;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const active =
    points[Math.min(selected ?? points.length - 1, points.length - 1)];
  const min = Math.min(0, ...points.map((p) => p.y));
  const max = Math.max(...points.map((p) => p.y), min + 0.001);
  const x = (i: number) => 48 + (i / Math.max(points.length - 1, 1)) * 620;
  const y = (value: number) => 200 - ((value - min) / (max - min)) * 155;
  return (
    <section className="training-panel training-chart">
      <div className="training-panel-heading">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <strong style={{ color }}>{decimal(active?.y, 3)}</strong>
      </div>
      {points.length ? (
        <>
          <svg
            viewBox="0 0 700 240"
            role="img"
            aria-label={`${title}: ${points.length} recorded values`}
            onMouseMove={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              setSelected(
                Math.max(
                  0,
                  Math.min(
                    points.length - 1,
                    Math.round(
                      ((((event.clientX - rect.left) / rect.width) * 700 - 48) /
                        620) *
                        (points.length - 1),
                    ),
                  ),
                ),
              );
            }}
            onMouseLeave={() => setSelected(null)}
          >
            {[0, 1, 2, 3].map((i) => (
              <g key={i}>
                <line
                  x1="48"
                  x2="668"
                  y1={45 + (i * 155) / 3}
                  y2={45 + (i * 155) / 3}
                  stroke="#e5e6e2"
                  strokeDasharray="3 5"
                />
                <text x="40" y={49 + (i * 155) / 3} textAnchor="end">
                  {(max - (i * (max - min)) / 3).toFixed(2)}
                </text>
              </g>
            ))}
            <polyline
              points={points.map((p, i) => `${x(i)},${y(p.y)}`).join(" ")}
              fill="none"
              stroke={color}
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
            {active && (
              <circle
                cx={x(
                  Math.min(selected ?? points.length - 1, points.length - 1),
                )}
                cy={y(active.y)}
                r="4"
                fill={color}
                stroke="white"
                strokeWidth="2"
              />
            )}
            <text x="48" y="227">
              {points[0].x}
            </text>
            <text x="668" y="227" textAnchor="end">
              {points[points.length - 1].x}
            </text>
          </svg>
          <div className="training-chart-foot">
            <span>
              {unit} {active?.x} · {decimal(active?.y, 5)}
            </span>
            <span>Hover to inspect</span>
          </div>
        </>
      ) : (
        <div className="training-chart-empty">
          <Activity size={25} />
          <p>
            Waiting for{" "}
            {unit === "Step"
              ? "the first optimization step"
              : "the first completed episode"}
          </p>
        </div>
      )}
    </section>
  );
}

export default function TrainingDashboard() {
  const [data, setData] = useState<TrainingResponse | null>(null);
  const [error, setError] = useState(false);
  const [clock, setClock] = useState(0);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    const poll = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch("/api/training", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Metrics unavailable");
        const next: TrainingResponse = await response.json();
        if (alive) {
          setData(next);
          setError(false);
          setClock(Date.now());
        }
      } catch {
        if (alive) setError(true);
      } finally {
        clearTimeout(timeout);
        if (alive) timer = setTimeout(poll, 2000);
      }
    };
    void poll();
    const tick = setInterval(() => setClock(Date.now()), 1000);
    return () => {
      alive = false;
      controller?.abort();
      clearTimeout(timer);
      clearInterval(tick);
    };
  }, []);
  const run = data?.run;
  const stale =
    data?.stale ||
    (run?.status === "running" && clock / 1000 - run.updated_at > 15);
  const live = run?.status === "running" && !stale && !error;
  const status = error
    ? "Connection lost"
    : stale
      ? "Updates paused"
      : run?.status === "running"
        ? "Live training"
        : run?.status === "completed"
          ? "Run completed"
          : run?.status === "failed"
            ? "Run failed"
            : run?.status === "interrupted"
              ? "Run interrupted"
              : data
                ? "Waiting for a run"
                : "Connecting";
  const losses =
    run?.loss_history
      .filter((p) => p.loss != null && Number.isFinite(p.loss))
      .map((p) => ({ x: p.step, y: p.loss! })) ?? [];
  const episodes = run?.episodes ?? [];
  const progress = !run
    ? 0
    : run.phase === "optimizing"
      ? run.train_step / Math.max(run.config.train_steps, 1)
      : run.episodes_in_iteration /
        Math.max(run.config.episodes_per_iteration, 1);
  const bufferTotal = Object.values(run?.buffer_counts ?? {}).reduce(
    (a, b) => a + b,
    0,
  );
  return (
    <main className="training-shell">
      <div className="training-container">
        <nav className="training-nav">
          <Link href="/" className="training-brand">
            <BrainCircuit size={24} /> FLIH<span>/</span>
            <span>Training lab</span>
          </Link>
          <Link href="/">
            <ArrowLeft size={15} /> Back to campus
          </Link>
        </nav>
        <header className="training-header">
          <div>
            <div className="training-eyebrow">CONNECTOME INTELLIGENCE</div>
            <h1>A tiny brain, learning.</h1>
            <p>Follow the model from its first steps to better navigation.</p>
          </div>
          <div
            className={`training-status ${live ? "is-live" : ""}`}
            role="status"
          >
            <span />
            {status}
          </div>
        </header>
        {error && (
          <div className="training-notice" role="alert">
            Couldn’t reach training metrics. Reconnecting automatically; any
            values below are the last received snapshot.
          </div>
        )}
        {stale && !error && (
          <div className="training-notice">
            The trainer hasn’t sent an update in over 15 seconds. Check whether
            the training process is still running.
          </div>
        )}
        {!run ? (
          <section className="training-welcome training-panel">
            <div className="training-icon">
              <Terminal size={28} />
            </div>
            <h2>
              {error ? "Metrics unavailable" : "Ready when your model is."}
            </h2>
            <p>
              Start the trainer on this machine. Results will appear here
              automatically.
            </p>
            <pre>cd fly-gym{"\n"}python train_connectome_rnn_dagger.py</pre>
            <small>
              This page monitors training. It doesn’t start or stop a run.
            </small>
          </section>
        ) : (
          <>
            <section className="training-run training-panel">
              <div>
                <div className="training-eyebrow">
                  CURRENT RUN <span>{run.run_id}</span>
                </div>
                <h2>{run.config.model}</h2>
                <p>
                  {run.config.environments} parallel environments <span>·</span>{" "}
                  Cameras + LiDAR <span>·</span> <Clock3 size={13} />
                  {duration(
                    live ? clock / 1000 - run.started_at : run.elapsed_seconds,
                  )}
                </p>
              </div>
              <div className="training-progress">
                <div>
                  <strong>
                    Iteration {run.iteration}{" "}
                    <span>/ {run.config.iterations}</span>
                  </strong>
                  <span>
                    {run.phase === "initializing"
                      ? "Initializing model"
                      : run.phase === "collecting"
                        ? "Collecting experience"
                        : "Optimizing weights"}
                  </span>
                </div>
                <progress
                  max={1}
                  value={Math.min(progress, 1)}
                  aria-label="Current phase progress"
                />
                <small>
                  {run.phase === "optimizing"
                    ? `${run.train_step} / ${run.config.train_steps} optimization steps`
                    : `${run.episodes_in_iteration} / ${run.config.episodes_per_iteration} episodes`}{" "}
                  · teacher mix {decimal((run.beta ?? 1) * 100, 0)}%
                </small>
              </div>
            </section>
            {run.error && (
              <div className="training-notice" role="alert">
                Training stopped: {run.error}
              </div>
            )}
            <div className="training-metrics">
              {[
                [
                  "Latest loss",
                  decimal(losses[losses.length - 1]?.y),
                  "Imitation learning objective",
                ],
                [
                  "Goal success",
                  run.episodes_total
                    ? `${((100 * run.successes) / run.episodes_total).toFixed(1)}%`
                    : "—",
                  `${number(run.successes)} of ${number(run.episodes_total)} episodes`,
                ],
                [
                  "Collision episodes",
                  run.episodes_total
                    ? `${((100 * run.collision_episodes) / run.episodes_total).toFixed(1)}%`
                    : "—",
                  "Episodes with at least one contact",
                ],
                [
                  "Environment steps",
                  number(run.environment_steps),
                  `${number(run.episodes_total)} episodes completed`,
                ],
              ].map(([label, value, note]) => (
                <section className="training-panel training-metric" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{note}</small>
                </section>
              ))}
            </div>
            <div className="training-charts">
              <MetricChart
                title="Learning curve"
                subtitle="Loss per optimization step · lower is better"
                points={losses}
                color="#28675e"
                unit="Step"
              />
              <MetricChart
                title="Episode return"
                subtitle="Total reward · most recent 200 episodes"
                points={episodes.map((e) => ({ x: e.episode, y: e.reward }))}
                color="#537eac"
                unit="Episode"
              />
            </div>
            <p className="training-caption">
              Episode results reflect the teacher/student mixture during
              collection, not a separate policy evaluation. Loss chart retains
              the latest 2,000 steps.
            </p>
            <div className="training-bottom">
              <section className="training-panel">
                <div className="training-panel-heading">
                  <div>
                    <h2>Recent episodes</h2>
                    <p>The last 10 completed trajectories</p>
                  </div>
                  <ArrowUpRight size={19} />
                </div>
                <div className="training-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Episode</th>
                        <th>Outcome</th>
                        <th>Return</th>
                        <th>Steps</th>
                        <th>Contact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {episodes
                        .slice(-10)
                        .reverse()
                        .map((e) => (
                          <tr key={e.episode}>
                            <td>#{e.episode}</td>
                            <td>
                              <span
                                className={
                                  e.success
                                    ? "training-success"
                                    : "training-muted"
                                }
                              >
                                {e.success ? (
                                  <Check size={13} />
                                ) : (
                                  <Circle size={11} />
                                )}{" "}
                                {e.success ? "Goal reached" : "Not reached"}
                              </span>
                            </td>
                            <td>{e.reward.toFixed(2)}</td>
                            <td>{number(e.steps)}</td>
                            <td>{e.collision ? "Yes" : "No"}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                  {!episodes.length && (
                    <p className="training-table-empty">
                      Episodes will appear as they finish.
                    </p>
                  )}
                </div>
              </section>
              <div className="training-sidebar">
                <section className="training-panel">
                  <div className="training-panel-heading">
                    <h2>
                      <Database size={16} /> Replay buffer
                    </h2>
                    <span>{number(bufferTotal)} chunks</span>
                  </div>
                  {Object.entries(run.buffer_counts).map(([key, count], i) => (
                    <div className="training-buffer" key={key}>
                      <div>
                        <span>{key.replaceAll("_", " ")}</span>
                        <span>{number(count)}</span>
                      </div>
                      <div className="training-buffer-track">
                        <i
                          style={{
                            width: `${bufferTotal ? (100 * count) / bufferTotal : 0}%`,
                            background: [
                              "#28675e",
                              "#537eac",
                              "#cf7754",
                              "#c9a44f",
                              "#8a82a5",
                            ][i % 5],
                          }}
                        />
                      </div>
                    </div>
                  ))}
                  {!bufferTotal && (
                    <p className="training-muted">
                      Collecting the first experience chunks.
                    </p>
                  )}
                </section>
                <section className="training-panel">
                  <div className="training-panel-heading">
                    <h2>
                      <Radio size={16} /> Run settings
                    </h2>
                  </div>
                  <dl className="training-settings">
                    <dt>Learning rate</dt>
                    <dd>{run.config.learning_rate}</dd>
                    <dt>Batch size</dt>
                    <dd>{run.config.batch_size}</dd>
                    <dt>Cameras</dt>
                    <dd>{run.config.camera_size.join(" × ")}</dd>
                    <dt>LiDAR</dt>
                    <dd>
                      {run.config.lidar_rays} rays · {run.config.lidar_rate_hz}{" "}
                      Hz
                    </dd>
                  </dl>
                </section>
              </div>
            </div>
            <section className="training-panel training-checkpoints">
              <div className="training-panel-heading">
                <div>
                  <h2>Saved checkpoints</h2>
                  <p>Weights saved by the training process</p>
                </div>
                <span>{run.checkpoints.length} saved</span>
              </div>
              {run.checkpoints.length ? (
                run.checkpoints
                  .slice(-5)
                  .reverse()
                  .map((c, i) => (
                    <div className="training-checkpoint" key={`${c.name}-${i}`}>
                      <Check size={16} />
                      <code>{c.name}</code>
                      <span>Iteration {c.iteration}</span>
                      <time>
                        {new Date(c.saved_at * 1000).toLocaleTimeString()}
                      </time>
                    </div>
                  ))
              ) : (
                <p className="training-muted">
                  The first checkpoint is saved after an iteration finishes.
                </p>
              )}
            </section>
          </>
        )}
        <footer className="training-footer">
          <span>
            <Activity size={14} /> FLIH Training Observatory
          </span>
          <span>
            {run
              ? `Last update ${new Date(run.updated_at * 1000).toLocaleTimeString()} · `
              : ""}
            Refreshes every 2 seconds
          </span>
        </footer>
      </div>
    </main>
  );
}
