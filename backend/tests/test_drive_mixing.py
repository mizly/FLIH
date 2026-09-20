"""Run: python -m unittest discover -s backend/tests -p 'test_*.py' -v

Pins the four teleop motions to the wheel commands that were confirmed on the real
robot, so a change to the sign or side map cannot silently reverse the controls.

The case this exists for: **flipping every sign and every side at once negates
forward and reverse while leaving the turns bit-for-bit identical.** Rotation about
the centre is the same whichever end of the chassis you call the front, so no amount
of driving A and D will show it, and it has reached the robot twice that way. The
expectations below are physical facts about FLIH's harness, taken from
hardware/MOTOR_MAP.md - if one fails, fix the configuration, not the expectation.
"""

import contextlib
import importlib
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import motor_board  # noqa: E402  (needs the path above)

# Confirmed on hardware: all four wheels drove the way the chassis faces on W,
# reversed on S, and the cart rotated left on A and right on D.
CONFIRMED_SIDES = ("L", "R", "L", "R")
CONFIRMED_SIGNS = (1, -1, -1, 1)

# The signed speeds those motions produce, as M1, M2, M3, M4 multiples of the
# commanded speed. Forward is the one that matters: it is the only one of the four
# that distinguishes the confirmed map from its inverted twin.
FORWARD = (1, -1, -1, 1)
REVERSE = (-1, 1, 1, -1)
SPIN_LEFT = (-1, -1, 1, 1)
SPIN_RIGHT = (1, 1, -1, -1)

# The configuration that shipped the bug, kept so the test can prove *why* it hid.
INVERTED_SIDES = ("R", "L", "R", "L")
INVERTED_SIGNS = (-1, 1, 1, -1)


class FakeLink:
    """Stands in for the serial or I2C link so the mixing can be tested off-robot."""

    name = "fake"

    def __init__(self):
        self.frames = []

    def command(self, name, args=""):
        self.frames.append((name, args))
        return "command+OK"

    def close(self):
        pass


@contextlib.contextmanager
def board_configured(**overrides):
    """A MotorBoard on a fake link, with the module reloaded under a clean ROBOT_* env.

    Hermetic on purpose: a stale ROBOT_MOTOR_SIGNS exported in the developer's shell
    is one of the ways this bug travels, so the test must not be able to inherit it.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("ROBOT_")}
    env.update(overrides)
    with mock.patch.dict(os.environ, env, clear=True):
        module = importlib.reload(motor_board)
        board = object.__new__(module.MotorBoard)
        board.signs = module.motor_signs()
        board.lock = threading.Lock()
        board.link = FakeLink()
        yield module, board
    importlib.reload(motor_board)  # Leave the module as the next test expects it.


def speeds(board):
    """The last commanded speeds, as four ints."""
    _, args = board.link.frames[-1]
    return tuple(int(part) for part in args.split(","))


class DefaultsTests(unittest.TestCase):
    def test_defaults_are_the_confirmed_map(self):
        """Forgetting the env vars must give the confirmed robot, not the inverted one."""
        with board_configured() as (module, _):
            self.assertEqual(module.motor_sides(), CONFIRMED_SIDES)
            self.assertEqual(module.motor_signs(), CONFIRMED_SIGNS)

    def test_motor_map_documents_the_defaults(self):
        """hardware/MOTOR_MAP.md is the source of truth; the code must agree with it."""
        text = (Path(__file__).resolve().parents[2] / "hardware" / "MOTOR_MAP.md").read_text()
        self.assertIn("ROBOT_MOTOR_SIGNS=%s" % ",".join(str(s) for s in CONFIRMED_SIGNS), text)
        self.assertIn("ROBOT_MOTOR_SIDES=%s" % ",".join(CONFIRMED_SIDES), text)


class DriveDirectionTests(unittest.TestCase):
    def assert_motion(self, forward, turn, expected):
        with board_configured() as (module, board):
            board.drive(forward, turn)
            speed = module.TURN_SPEED if forward == 0 else module.DRIVE_SPEED
            self.assertEqual(speeds(board), tuple(value * speed for value in expected))

    def test_w_drives_forward(self):
        self.assert_motion(1, 0, FORWARD)

    def test_s_drives_backward(self):
        self.assert_motion(-1, 0, REVERSE)

    def test_a_rotates_left(self):
        self.assert_motion(0, -1, SPIN_LEFT)

    def test_d_rotates_right(self):
        self.assert_motion(0, 1, SPIN_RIGHT)

    def test_forward_and_reverse_are_opposites(self):
        self.assertEqual(REVERSE, tuple(-value for value in FORWARD))

    def test_stop_is_all_zero(self):
        with board_configured() as (_, board):
            board.stop()
            self.assertEqual(speeds(board), (0, 0, 0, 0))


class InvertedMapTests(unittest.TestCase):
    """Why the bug is invisible: the inverted map differs from the confirmed one in
    forward and reverse *only*. Any check built on turning will pass on both."""

    def commands(self, forward, turn, **overrides):
        with board_configured(**overrides) as (_, board):
            board.drive(forward, turn)
            return speeds(board)

    def inverted(self):
        return {
            "ROBOT_MOTOR_SIDES": ",".join(INVERTED_SIDES),
            "ROBOT_MOTOR_SIGNS": ",".join(str(s) for s in INVERTED_SIGNS),
        }

    def test_turns_are_identical_under_the_inverted_map(self):
        for turn in (-1, 1):
            self.assertEqual(
                self.commands(0, turn),
                self.commands(0, turn, **self.inverted()),
                "turning cannot distinguish the two maps - do not test the map with A/D",
            )

    def test_forward_is_negated_under_the_inverted_map(self):
        confirmed = self.commands(1, 0)
        inverted = self.commands(1, 0, **self.inverted())
        self.assertEqual(inverted, tuple(-value for value in confirmed))

    def test_the_inverted_map_is_not_what_ships(self):
        with board_configured() as (module, _):
            self.assertNotEqual(module.motor_sides(), INVERTED_SIDES)
            self.assertNotEqual(module.motor_signs(), INVERTED_SIGNS)


if __name__ == "__main__":
    unittest.main()
