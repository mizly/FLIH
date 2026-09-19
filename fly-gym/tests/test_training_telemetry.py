import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training_telemetry import TrainingTelemetry


class TrainingTelemetryTests(unittest.TestCase):
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
                    data = json.loads(path.read_text())
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
