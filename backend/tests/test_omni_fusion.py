import math
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from omni_fusion import OmniFusion, summarize_scan  # noqa: E402


class FakeScan:
    def __init__(self):
        self.angles = [0.0, math.pi / 2, math.pi, -math.pi / 2, math.nan]
        self.ranges = [0.2, 0.4, 0.6, 0.8, 0.01]

    @property
    def returns(self):
        return 5


class SummaryTests(unittest.TestCase):
    def test_scan_is_summarized_in_robot_directions(self):
        summary = summarize_scan(FakeScan())
        self.assertEqual(summary["nearest_by_direction"], {
            "front": 0.2, "left": 0.4, "back": 0.6, "right": 0.8,
        })


class FusionTests(unittest.TestCase):
    def test_cloud_call_requires_both_views_but_not_motion(self):
        calls = []

        def classify(*args):
            calls.append(args)
            return {"summary": "clear"}

        with mock.patch.dict(os.environ, {"YIBU_API_KEY": "test-key"}):
            fusion = OmniFusion(interval_s=1, classifier=classify)
            fusion.offer_camera(0, b"left")
            fusion.observe_scan(FakeScan(), "forward")
            self.assertEqual(calls, [])
            fusion.offer_camera(1, b"right")
            fusion.observe_scan(FakeScan(), "stopped")
            fusion._worker.join(timeout=1)
            self.assertEqual(len(calls), 1)
            self.assertEqual([view[0] for view in calls[0][0]], ["left", "right"])
            self.assertEqual(calls[0][3], "stopped")
            self.assertEqual(calls[0][4], mock.ANY)
            fusion.close()

    def test_no_key_disables_calls(self):
        with mock.patch.dict(os.environ, {"YIBU_API_KEY": ""}):
            fusion = OmniFusion(classifier=lambda *args: self.fail("called"))
            self.assertFalse(fusion.enabled)
            fusion.close()


if __name__ == "__main__":
    unittest.main()
