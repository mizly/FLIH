"""Adapter tests need numpy/OpenCV, but neither working torch nor attached hardware."""

from contextlib import nullcontext
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent / "fly-gym"))

import live_flynn_shadow as shadow


class LiveInputsTests(unittest.TestCase):
    def setUp(self):
        self.cameras = [Mock(running=True), Mock(running=True)]
        # Distinct BGR colours pin both RGB conversion and left/right ordering.
        self.cameras[0].read.return_value = (np.full((135, 240, 3), [10, 20, 30],
                                                        dtype=np.uint8), 1, 30)
        self.cameras[1].read.return_value = (np.full((135, 240, 3), [40, 50, 60],
                                                        dtype=np.uint8), 2, 30)
        self.rectifiers = [Mock(side_effect=lambda frame: frame) for _ in range(2)]
        self.scan = SimpleNamespace(stamp=100, returns=1,
                                    angles=np.array([0.0]), ranges=np.array([3.0]))
        self.scanner = Mock(running=True, error=None)
        self.scanner.read.return_value = (self.scan, 3)
        config = SimpleNamespace(min_range=0.05, max_range=12.0, fov_deg=360.0)
        self.inputs = shadow.LiveInputs(self.cameras, self.rectifiers, self.scanner,
                                        config, timeout=1.0)

    def read(self, now=10, wall_now=100):
        return self.inputs.read(now=now, wall_now=wall_now)

    def test_rgb_shape_forward_goal_and_lidar_convention(self):
        obs, ages = self.read()
        self.assertEqual(obs["cam_left"].shape, (128, 128, 3))
        self.assertEqual(obs["cam_left"].dtype, np.uint8)
        np.testing.assert_array_equal(obs["cam_left"][0, 0], [30, 20, 10])
        np.testing.assert_array_equal(obs["cam_right"][0, 0], [60, 50, 40])
        np.testing.assert_array_equal(obs["sensors"]["vec_to_goal"], [1, 0])
        np.testing.assert_array_equal(obs["sensors"]["wind_direction"], [1, 0])
        expected = np.zeros(12, dtype=np.float32)
        expected[6] = 0.75  # forward: 1 - 3m/12m, no extra driver-angle flip
        np.testing.assert_array_equal(obs["sensors"]["lidar_features"], expected)
        self.assertEqual(obs["sensors"]["collision"], 0)
        self.assertEqual(ages, [0, 0, 0])

    def test_holds_processed_samples_until_serial_changes(self):
        first, _ = self.read()
        second, ages = self.read(now=10.5, wall_now=100.5)
        self.assertIs(first["cam_left"], second["cam_left"])
        self.assertIs(first["sensors"]["lidar_features"], second["sensors"]["lidar_features"])
        self.assertEqual(ages, [0.5, 0.5, 0.5])
        for rectifier in self.rectifiers:
            rectifier.assert_called_once()

    def test_new_camera_sample_replaces_cache(self):
        first, _ = self.read()
        frame, _, fps = self.cameras[0].read.return_value
        self.cameras[0].read.return_value = (frame, 4, fps)
        second, ages = self.read(now=10.5, wall_now=100.5)
        self.assertIsNot(first["cam_left"], second["cam_left"])
        self.assertEqual(ages, [0, 0.5, 0.5])

    def test_waits_for_first_sample(self):
        self.cameras[1].read.return_value = (None, 0, 0)
        self.assertIsNone(self.read())

    def test_stale_camera_is_fatal_even_if_cached_frame_exists(self):
        self.read()
        with self.assertRaisesRegex(TimeoutError, "left camera"):
            self.read(now=11.1, wall_now=100.5)

    def test_stale_first_scan_is_rejected(self):
        with self.assertRaisesRegex(TimeoutError, "timestamp"):
            self.read(wall_now=102)

    def test_stalled_lidar_uses_monotonic_time_too(self):
        self.read()
        for camera in self.cameras:
            frame, serial, fps = camera.read.return_value
            camera.read.return_value = (frame, serial + 10, fps)
        with self.assertRaisesRegex(TimeoutError, "Stale LiDAR"):
            self.read(now=12, wall_now=100)  # wall-clock adjustment cannot hide a stall

    def test_dead_camera_is_rejected(self):
        self.cameras[0].running = False
        with self.assertRaisesRegex(RuntimeError, "Left camera stopped"):
            self.read()

    def test_dead_lidar_is_rejected(self):
        self.scanner.running = False
        with self.assertRaisesRegex(RuntimeError, "LiDAR stopped"):
            self.read()

    def test_no_returns_is_not_treated_as_clear(self):
        self.scan.returns = 0
        with self.assertRaisesRegex(RuntimeError, "no valid returns"):
            self.read()


class RunnerTests(unittest.TestCase):
    def test_smoke_loop_carries_hidden_state_without_opening_hardware(self):
        args = shadow.parse_args(["--smoke-test"])
        initial = object()
        torch = Mock(float32="float32")
        torch.zeros.return_value = initial
        torch.inference_mode.side_effect = nullcontext
        torch.isfinite.return_value.all.return_value.item.return_value = True
        action = Mock()
        action.__getitem__ = Mock(return_value=action)
        action.detach.return_value.cpu.return_value.tolist.return_value = [0.1, 0.2]
        states = [object() for _ in range(10)]
        agent = Mock(device="cpu", lidar_bins=12)
        agent.cell.N = 5
        agent.step.side_effect = [(state, action) for state in states]
        convert = Mock(side_effect=lambda observation, *_: observation)
        with patch.object(shadow, "load_model", return_value=(torch, agent, convert, None)), \
                patch.object(shadow, "open_inputs") as open_inputs, \
                patch.object(shadow.time, "sleep"), patch("sys.stdout", new_callable=io.StringIO):
            shadow.run(args)
        open_inputs.assert_not_called()
        self.assertEqual(agent.step.call_count, 10)
        for call, expected in zip(agent.step.call_args_list, [initial] + states[:-1]):
            self.assertIs(call.args[0], expected)
        agent.reset_vision_state.assert_not_called()  # initialization belongs to load_model

    def test_bad_timing_arguments_are_rejected(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            for value in ("0", "-1", "nan", "inf"):
                with self.assertRaises(SystemExit):
                    shadow.parse_args(["--hz", value])


if __name__ == "__main__":
    unittest.main()
