"""Non-blocking, atomic snapshots consumed by the /training web dashboard."""
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid
import warnings


class TrainingTelemetry:
    def __init__(self, config, path=None, interval=2.0):
        self.path = Path(path or os.environ.get("FLY_GYM_TRAINING_FILE") or
                         Path(__file__).parent / "training" / "latest.json")
        self.interval = interval
        self.lock = threading.RLock()
        self.stopped = threading.Event()
        self.started = time.time()
        self.preview_enabled = os.environ.get("FLY_GYM_PREVIEW", "1") != "0"
        self._preview_due = 0.0
        self.data = dict(schema_version=1, run_id=uuid.uuid4().hex[:12],
                         started_at=self.started, updated_at=self.started,
                         status="running", phase="initializing", config=config,
                         iteration=0, episodes_in_iteration=0, train_step=0,
                         environment_steps=0, episodes_total=0, successes=0,
                         collision_episodes=0, loss_history=[], episodes=[],
                         iterations=[], checkpoints=[], buffer_counts={}, error=None)

    def preview(self, env, episode, step, collision=False):
        """Copy only CPU geometry from env 0, at most twice per wall-clock second.

        No render, inference, tensor transfer, file IO, or waiting for a reader.
        A busy heartbeat drops this sample. Browser speed never gates training.
        """
        if not self.preview_enabled:
            return
        now = time.monotonic()
        if now < self._preview_due:
            return
        self._preview_due = now + 0.5
        if not self.lock.acquire(blocking=False):
            return
        try:
            previous = self.data.get("preview")
            key = f"{self.data['iteration']}:{episode}"
            xy = [float(v) for v in env._base_xy()]
            pose = dict(x=xy[0], y=xy[1], yaw=float(env._base_yaw()))
            trail = previous["trail"] if previous and previous["episode"] == key else []
            sample = dict(
                episode=key, environment=0, captured_at=time.time(), step=int(step),
                simulation_seconds=float(env.data.time), arena=float(env.arena),
                goal=[float(v) for v in env._goal_xy], goal_radius=float(env.goal_radius),
                obstacles=[dict(x=float(env.data.geom_xpos[gid][0]),
                                y=float(env.data.geom_xpos[gid][1]),
                                radius=float(env.model.geom_size[gid][0]),
                                height=float(env.model.geom_size[gid][1]) * 2)
                           for gid in env.obstacle_ids[:20]],
                pose=pose, collision=bool(collision), trail=(trail + [xy])[-64:])
            # Invalid optional geometry must not poison the metrics JSON.
            json.dumps(sample, allow_nan=False)
            self.data["preview"] = sample
        except Exception:
            # Optional observation must never terminate training. Disable on failure.
            self.preview_enabled = False
        finally:
            self.lock.release()

    def update(self, **values):
        with self.lock:
            self.data.update(values)

    def advance(self, steps):
        with self.lock:
            self.data["environment_steps"] += steps

    def loss(self, value, step):
        with self.lock:
            value = float(value)
            value = value if math.isfinite(value) else None
            self.data["train_step"] = step
            self.data["loss_history"].append(dict(
                step=(self.data["iteration"] - 1) * self.data["config"]["train_steps"] + step,
                iteration=self.data["iteration"], loss=value))
            self.data["loss_history"] = self.data["loss_history"][-2000:]

    def episode(self, *, reward, steps, success, collision, distance, termination_reason=None):
        with self.lock:
            self.data["episodes_total"] += 1
            self.data["successes"] += int(success)
            self.data["collision_episodes"] += int(collision)
            self.data["episodes"].append(dict(
                episode=self.data["episodes_total"], iteration=self.data["iteration"],
                reward=float(reward), steps=int(steps), success=bool(success),
                collision=bool(collision), distance=float(distance),
                termination_reason=termination_reason))
            self.data["episodes"] = self.data["episodes"][-200:]

    def iteration_result(self, loss, batches):
        with self.lock:
            self.data["iterations"].append(dict(iteration=self.data["iteration"],
                mean_loss=float(loss) if math.isfinite(loss) else None, batches=batches))

    def checkpoint(self, path):
        with self.lock:
            self.data["checkpoints"].append(dict(name=Path(path).name,
                iteration=self.data["iteration"], saved_at=time.time()))
            self.data["checkpoints"] = self.data["checkpoints"][-100:]

    def flush(self):
        # File IO runs in the heartbeat thread, never the GPU training loop.
        try:
            with self.lock:
                self.data["updated_at"] = time.time()
                self.data["elapsed_seconds"] = self.data["updated_at"] - self.started
                payload = json.dumps(self.data, allow_nan=False)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(f".{self.data['run_id']}.tmp")
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, self.path)
        except (OSError, ValueError) as exc:
            # A dashboard failure must not discard an expensive training run.
            warnings.warn(f"Training dashboard snapshot failed: {exc}")

    def _heartbeat(self):
        while not self.stopped.wait(self.interval):
            self.flush()

    def __enter__(self):
        self.flush()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, kind, error, traceback):
        self.stopped.set()
        self.thread.join()
        self.update(status="completed" if kind is None else
                    "interrupted" if issubclass(kind, KeyboardInterrupt) else "failed",
                    error=str(error) if error else None)
        self.flush()
