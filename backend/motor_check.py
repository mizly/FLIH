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

from motor_board import DRIVE_COMMAND, DRIVE_SPEED, MotorBoard, TURN_SPEED

HOLD = 1.5  # Seconds of motion per step.
SETTLE = 1.0  # Seconds stopped between steps, to tell the steps apart.

WHEELS = ("M1 front left", "M2 rear left", "M3 front right", "M4 rear right")


def step(board: MotorBoard, label: str, speeds, expected: str) -> None:
    print(f"\n{label}\n  expect: {expected}")
    board.write_speeds(speeds)
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
        print("\nWheels off the ground. Ctrl-C stops everything.")
        time.sleep(2)

        for index, wheel in enumerate(WHEELS):
            speeds = [0, 0, 0, 0]
            speeds[index] = DRIVE_SPEED
            step(board, f"[{index + 1}/4] {wheel}", speeds,
                 f"only the {wheel[3:]} wheel turns, forward")

        left, right = DRIVE_SPEED, DRIVE_SPEED
        step(board, "Forward", (left, left, right, right), "all four turn forward")
        step(board, "Reverse", (-left, -left, -right, -right), "all four turn backward")
        step(board, "Spin left", (-TURN_SPEED, -TURN_SPEED, TURN_SPEED, TURN_SPEED),
             "left side backward, right side forward")
        step(board, "Spin right", (TURN_SPEED, TURN_SPEED, -TURN_SPEED, -TURN_SPEED),
             "left side forward, right side backward")

        print("\nDone. Every step matching means ROBOT_MOTOR_SIGNS is correct.")
        return 0
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130
    finally:
        board.close()


if __name__ == "__main__":
    raise SystemExit(main())
