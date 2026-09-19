import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training_telemetry import TrainingTelemetry


class TrainingTelemetryTests(unittest.TestCase):
    def preview_env(self):
        return SimpleNamespace(_base_xy=lambda: [1., 2.], _base_yaw=lambda: .5,
            _goal_xy=[3., 4.], arena=7., goal_radius=.3, obstacle_ids=[0],
            data=SimpleNamespace(time=1., geom_xpos=[[2., 3., .8]]),
            model=SimpleNamespace(geom_size=[[.4, .8, 0.]]))

    def test_preview_throttles_bounds_and_separates_episodes(self):
        run = TrainingTelemetry({"train_steps": 1})
        run.preview_enabled = True
        env = self.preview_env()
        with patch("training_telemetry.time.monotonic", return_value=1):
            run.preview(env, 0, 1)
            env._base_xy = lambda: [5., 6.]
            run.preview(env, 0, 2)
        self.assertEqual(run.data["preview"]["pose"]["x"], 1.)
        for i in range(100):
            with patch("training_telemetry.time.monotonic", return_value=i + 2):
                run.preview(env, 0, i + 3)
        self.assertEqual(len(run.data["preview"]["trail"]), 64)
        with patch("training_telemetry.time.monotonic", return_value=200):
            run.preview(env, 1, 1)
        self.assertEqual(len(run.data["preview"]["trail"]), 1)
        self.assertEqual(run.data["preview"]["obstacles"][0]["height"], 1.6)
        # Copies must not retain references to the running simulation.
        env._goal_xy[0] = 100
        self.assertEqual(run.data["preview"]["goal"][0], 3.)

    def test_preview_never_waits_for_heartbeat_and_can_be_disabled(self):
        run = TrainingTelemetry({"train_steps": 1})
        run.preview_enabled = True
        # Another thread's lock cannot be reentered by the sampler.
        with run.lock:
            worker = threading.Thread(target=run.preview, args=(self.preview_env(), 0, 1), daemon=True)
            worker.start()
            worker.join(timeout=.5)
            self.assertFalse(worker.is_alive())
        self.assertNotIn("preview", run.data)
        with patch.dict("os.environ", {"FLY_GYM_PREVIEW": "0"}):
            disabled = TrainingTelemetry({"train_steps": 1})
        disabled.preview(None, 0, 1)
        self.assertNotIn("preview", disabled.data)

    def test_bad_preview_does_not_break_metrics(self):
        run = TrainingTelemetry({"train_steps": 1})
        run.preview_enabled = True
        env = self.preview_env()
        env._base_yaw = lambda: float("nan")
        run.preview(env, 0, 1)
        self.assertNotIn("preview", run.data)
        json.dumps(run.data, allow_nan=False)

    def test_running_snapshot_and_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            with TrainingTelemetry({"train_steps": 5}, path, interval=.01) as run:
                run.update(iteration=1, phase="optimizing")
                run.loss(.4, 1)
                run.advance(30)
                run.episode(reward=2, steps=30, success=True, collision=False, distance=.2)
                run.checkpoint("somewhere/model.pt")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    try:
                        data = json.loads(path.read_text())
                    except PermissionError:
                        # Windows can briefly deny a read during atomic replace.
                        time.sleep(.01)
                        continue
                    if data["environment_steps"] == 30:
                        break
                    time.sleep(.01)
                self.assertEqual(data["status"], "running")
                self.assertEqual(data["successes"], 1)
            data = json.loads(path.read_text())
            self.assertEqual(data["status"], "completed")
            self.assertEqual(data["loss_history"][0]["loss"], .4)
            self.assertEqual(data["checkpoints"][0]["name"], "model.pt")

    def test_errors_and_interruptions_are_not_success(self):
        for error, status in [(RuntimeError("test failure"), "failed"), (KeyboardInterrupt(), "interrupted")]:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "latest.json"
                with self.assertRaises(type(error)):
                    with TrainingTelemetry({"train_steps": 1}, path):
                        raise error
                self.assertEqual(json.loads(path.read_text())["status"], status)

    def test_history_is_bounded_and_nan_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            with TrainingTelemetry({"train_steps": 3000}, path) as run:
                run.update(iteration=1)
                for step in range(2100):
                    run.loss(.5, step)
                run.loss(float("nan"), 2101)
            data = json.loads(path.read_text())
            self.assertEqual(len(data["loss_history"]), 2000)
            self.assertIsNone(data["loss_history"][-1]["loss"])


if __name__ == "__main__":
    unittest.main()
