"""Bench check for FLIH's motor board: confirm wiring and polarity before teleop.

Run this with the chassis propped up and all four wheels off the ground. It drives
one motor at a time, then the four teleop motions, announcing what each step should
look like. Any wheel that turns the wrong way gets its slot in ROBOT_MOTOR_SIGNS
flipped to -1; rerun until every step matches.

    python backend/motor_check.py
    ROBOT_MOTOR_SIGNS=1,1,-1,-1 python backend/motor_check.py
"""

import sys
import time

from motor_board import DRIVE_COMMAND, DRIVE_SPEED, MOTOR_SIDES, MotorBoard, TURN_SPEED

HOLD = 1.5  # Seconds of motion per step.
SETTLE = 1.0  # Seconds stopped between steps, to tell the steps apart.

WHEELS = ("M1 rear right", "M2 rear left", "M3 front right", "M4 front left")


def step(board: MotorBoard, label: str, speeds, expected: str) -> None:
    print(f"\n{label}\n  expect: {expected}")
    board.write_speeds(speeds)
    time.sleep(HOLD)
    board.stop()
    time.sleep(SETTLE)


def drive_step(board: MotorBoard, label: str, forward: int, turn: int, expected: str) -> None:
    """Same as step(), but through drive() so the side map is exercised too."""
    print(f"\n{label}\n  expect: {expected}")
    board.drive(forward, turn)
    time.sleep(HOLD)
    board.stop()
    time.sleep(SETTLE)


def main() -> int:
    board = MotorBoard()
    try:
        board.release()
        board.configure()

        volts = board.battery_volts()
        print(f"\nBattery: {f'{volts:.2f} V' if volts else 'no reply'}")
        print(f"Driving with ${DRIVE_COMMAND} at {DRIVE_SPEED} (turn {TURN_SPEED})")
        print(f"Motor signs: {','.join(str(sign) for sign in board.signs)}")
        print(f"Motor sides: {','.join(MOTOR_SIDES)} (M1-M4)")
        print("\nWheels off the ground. Ctrl-C stops everything.")
        time.sleep(2)

        for index, wheel in enumerate(WHEELS):
            speeds = [0, 0, 0, 0]
            speeds[index] = DRIVE_SPEED
            step(board, f"[{index + 1}/4] {wheel}", speeds,
                 f"only the {wheel[3:]} wheel turns, forward")

        drive_step(board, "Forward (W)", 1, 0, "all four turn forward")
        drive_step(board, "Reverse (S)", -1, 0, "all four turn backward")
        drive_step(board, "Turn left (A)", 0, -1,
                   "left side backward, right side forward; the cart rotates left")
        drive_step(board, "Turn right (D)", 0, 1,
                   "left side forward, right side backward; the cart rotates right")

        print("\nDone. The first four steps check ROBOT_MOTOR_SIGNS, the last four"
              "\ncheck ROBOT_MOTOR_SIDES.")
        return 0
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    finally:
        board.close()


if __name__ == "__main__":
    raise SystemExit(main())
