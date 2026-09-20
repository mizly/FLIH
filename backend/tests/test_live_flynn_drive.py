from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live_flynn_drive as drive
import live_flynn_shadow as shadow


class DriveTests(unittest.TestCase):
    def targets(self, speed, heading, cap=150):
        return drive.wheel_targets(speed, heading, .216, .4, .5, cap, ("L", "R", "L", "R"))

    def test_forward_and_reverse(self):
        self.assertEqual(self.targets(.1, 0), (40, 40, 40, 40))
        self.assertEqual(self.targets(-.1, 0), (-40, -40, -40, -40))

    def test_positive_heading_turns_left(self):
        self.assertEqual(self.targets(0, 1), (-54, 54, -54, 54))

    def test_cap_preserves_ratio(self):
        self.assertEqual(self.targets(1, 1, 100), (76, 100, 76, 100))

    def test_does_not_boost_small_model_actions(self):
        self.assertEqual(self.targets(.01, 0), (4, 4, 4, 4))
        self.assertEqual(self.targets(0, 0), (0, 0, 0, 0))

    def test_rejects_nan(self):
        with self.assertRaises(ValueError):
            self.targets(float("nan"), 0)

    def test_synthetic_inputs_cannot_drive_motors(self):
        with self.assertRaisesRegex(ValueError, "synthetic"):
            shadow.run(shadow.parse_args(["--smoke-test"]), action_sink=Mock())

    def sink(self):
        sink = drive.PicoSink.__new__(drive.PicoSink)
        sink.lock = threading.RLock()
        sink.board = Mock(signs=(1, -1, -1, 1))
        sink.fault = None
        sink.last_command = None
        sink.last_log = 0
        sink.count = 0
        sink.config = (.216, .4, .5, 150, ("L", "R", "L", "R"))
        sink._ack = Mock()
        return sink

    def test_stale_warmup_cannot_move(self):
        sink = self.sink()
        with patch("builtins.print"):
            sink(.1, 0, [.6, .6, .6])
        sink.board.write_speeds.assert_not_called()

    def test_stale_action_after_arming_is_fatal(self):
        sink = self.sink()
        sink.last_command = 1
        with self.assertRaises(TimeoutError):
            sink(.1, 0, [0, 0, .4])
        sink.board.write_speeds.assert_not_called()

    def test_fresh_model_action_reaches_board_and_requires_ack(self):
        sink = self.sink()
        with patch("builtins.print"):
            sink(.1, -.2, [.01, .01, .1])
        sink.board.write_speeds.assert_called_once_with((51, 29, 51, 29))
        sink._ack.assert_called_once()
        self.assertEqual(sink.count, 1)

    def test_failed_ack_is_not_counted(self):
        sink = self.sink()
        sink._ack.side_effect = TimeoutError("missing ACK")
        with self.assertRaises(TimeoutError):
            sink(.1, 0, [0, 0, 0])
        self.assertEqual(sink.count, 0)

    def test_fault_cannot_rearm(self):
        sink = self.sink()
        sink.fault = "watchdog stopped"
        with self.assertRaisesRegex(RuntimeError, "watchdog"):
            sink(.1, 0, [0, 0, 0])
        sink.board.write_speeds.assert_not_called()

    def test_stop_attempts_pwm_even_if_speed_ack_fails(self):
        sink = self.sink()
        sink._ack.side_effect = [TimeoutError("missing ACK"), None]
        with self.assertRaises(RuntimeError):
            sink._stop()
        self.assertEqual([call.args for call in sink.board.command.call_args_list],
                         [("spd", "0,0,0,0"), ("pwm", "0,0,0,0")])


if __name__ == "__main__":
    unittest.main()
