"""Run: python -m unittest discover -s backend/tests -p 'test_*.py' -v

Pins which CSI port feeds which browser pane.

Worth a test for the same reason the drive map is: it is a fact about the wiring that
is invisible from the bench. Both cameras point into the same room, so a swapped pair
looks entirely plausible on a desk and only reads as wrong once the robot is moving
and the operator turns toward something they can see.
"""

import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import camera_stream  # noqa: E402  (needs the path above)

# Confirmed on the robot: CSI port 1 is the left-facing camera, port 0 the right.
LEFT_SENSOR = 1
RIGHT_SENSOR = 0


class PaneMappingTests(unittest.TestCase):
    def test_publish_order_is_left_then_right(self):
        """Frame byte 0 is the left pane, so the left camera must be published first."""
        self.assertEqual(camera_stream.SENSORS_LEFT_TO_RIGHT, [LEFT_SENSOR, RIGHT_SENSOR])

    def test_default_sensors_match_the_pane_order(self):
        """Running with no flags must put each camera in its own pane."""
        self.assertEqual(
            camera_stream.parse_args([]).sensors,
            camera_stream.SENSORS_LEFT_TO_RIGHT,
        )

    def test_ports_are_not_published_in_numeric_order(self):
        """Numeric port order is the bug: it swaps the two views."""
        self.assertNotEqual(camera_stream.SENSORS_LEFT_TO_RIGHT, [0, 1])

    def test_frontend_labels_panes_by_view_not_by_port(self):
        """The UI must not name CSI ports, or the panes invite being 'fixed' back."""
        labels = (BACKEND.parent / "frontend" / "src" / "components" / "camera-feeds.tsx").read_text()
        self.assertIn('const CAMERA_LABELS = ["Left camera", "Right camera"];', labels)


if __name__ == "__main__":
    unittest.main()
