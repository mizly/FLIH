import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from safety_signal import (  # noqa: E402
    SafetyIndicator,
    SafetySignal,
    nearest_clearance,
    signal_for_clearance,
)


class FakeScan:
    def __init__(self, points):
        self.angles = [point[0] for point in points]
        self.ranges = [point[1] for point in points]


class RecordingOutput:
    def __init__(self):
        self.signals = []
        self.closed = False

    def set_signal(self, signal):
        self.signals.append(signal)

    def close(self):
        self.closed = True


class ThresholdTests(unittest.TestCase):
    def test_twenty_centimetres_is_red(self):
        self.assertEqual(signal_for_clearance(0.20), SafetySignal.RED)

    def test_between_twenty_and_fifty_is_yellow(self):
        self.assertEqual(signal_for_clearance(0.201), SafetySignal.YELLOW)
        self.assertEqual(signal_for_clearance(0.499), SafetySignal.YELLOW)

    def test_fifty_centimetres_and_above_is_green(self):
        self.assertEqual(signal_for_clearance(0.50), SafetySignal.GREEN)
        self.assertEqual(signal_for_clearance(2.0), SafetySignal.GREEN)


class ClearanceTests(unittest.TestCase):
    def test_nearest_return_in_any_direction_wins(self):
        clearance = nearest_clearance(
            [0.0, math.pi / 2, math.pi], [0.7, 0.3, 0.1]
        )
        self.assertEqual(clearance, 0.1)

    def test_zero_and_non_finite_returns_are_ignored(self):
        clearance = nearest_clearance(
            [0.0, 0.1, 0.2, 0.3], [0.0, math.inf, math.nan, 0.6]
        )
        self.assertEqual(clearance, 0.6)

    def test_no_valid_returns_has_no_clearance(self):
        self.assertIsNone(nearest_clearance([0.0, math.nan], [0.0, 0.1]))


class IndicatorTests(unittest.TestCase):
    def setUp(self):
        self.output = RecordingOutput()
        self.indicator = SafetyIndicator(self.output)

    def test_direction_change_does_not_change_the_clearance(self):
        self.indicator.update_scan(FakeScan([(0.0, 0.1), (math.pi, 0.8)]))
        self.assertEqual(self.indicator.set_motion(1).signal, SafetySignal.RED)
        reading = self.indicator.set_motion(-1)
        self.assertEqual(reading.signal, SafetySignal.RED)
        self.assertEqual(reading.clearance_m, 0.1)

    def test_scan_updates_the_signal_while_moving(self):
        self.indicator.set_motion(1)
        self.assertEqual(self.indicator.reading.signal, SafetySignal.RED)
        self.assertEqual(
            self.indicator.update_scan(FakeScan([(0.0, 0.3)])).signal,
            SafetySignal.YELLOW,
        )

    def test_stopped_keeps_the_scan_signal(self):
        self.indicator.update_scan(FakeScan([(0.0, 0.05)]))
        self.indicator.set_motion(1)
        reading = self.indicator.set_motion(0)
        self.assertEqual(reading.signal, SafetySignal.RED)
        self.assertEqual(reading.clearance_m, 0.05)

    def test_output_is_only_written_when_the_colour_changes(self):
        self.indicator.update_scan(FakeScan([(0.0, 0.8)]))
        self.indicator.set_motion(1)
        self.indicator.update_scan(FakeScan([(0.0, 0.7)]))
        self.assertEqual(self.output.signals, [SafetySignal.GREEN])

    def test_close_releases_the_output(self):
        self.indicator.close()
        self.assertTrue(self.output.closed)


if __name__ == "__main__":
    unittest.main()
