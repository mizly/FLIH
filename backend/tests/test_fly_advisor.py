import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fly_advisor import (  # noqa: E402
    DEFAULT_CHECKPOINT,
    FlyPolicyAdvisor,
    action_to_advice,
    lidar_features,
)


class FeatureTests(unittest.TestCase):
    def test_checkpoint_and_hardware_metadata_exist(self):
        self.assertTrue(DEFAULT_CHECKPOINT.is_file())
        self.assertTrue(Path(str(DEFAULT_CHECKPOINT) + ".robot.json").is_file())

    def test_lidar_features_use_twelve_nearest_range_sectors(self):
        features = lidar_features([0.0, 6.0, 3.0], [0.0, 0.0, -math.pi])
        self.assertEqual(len(features), 12)
        self.assertAlmostEqual(max(features), 0.75)
        self.assertIn(0.5, features)


class AdviceTests(unittest.TestCase):
    def test_action_is_presented_as_human_readable_advice(self):
        advice = action_to_advice(0.8, math.radians(25))
        self.assertEqual(advice["motion"], "forward")
        self.assertEqual(advice["turn"], "left")
        self.assertEqual(advice["headingDeg"], 25.0)

    def test_small_velocity_recommends_stop(self):
        self.assertEqual(action_to_advice(0.05, 0)["motion"], "stop")

    def test_stopped_advisor_is_explicitly_idle(self):
        advisor = FlyPolicyAdvisor(enabled=True)
        self.assertEqual(advisor.observe_scan(None, "stopped")["status"], "idle")


if __name__ == "__main__":
    unittest.main()
