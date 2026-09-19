"""Serial control for FLIH's Yahboom 4-channel motor drive board.

Framing and the command set come from the module manual in `hardware/`: ASCII
`$cmd:args#` at 115200 8N1. Frames reach the board either straight over USB serial
or through the Pico 2 relay in `hardware/PICO2/remote_control.py`, which passes
them along untouched, so nothing here depends on which link is in use.

Wheel mapping, from section 1 of the manual:

    M1 front left    M2 rear left    M3 front right    M4 rear right
"""

import os
import time

import serial

SERIAL_PORT = os.environ.get("ROBOT_SERIAL_PORT", "/dev/ttyUSB0")


def number(name: str, default: float, low: float, high: float, whole: bool = True):
    try:
        value = (int if whole else float)(os.environ.get(name, "") or default)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a number") from error
    if not low <= value <= high:
        raise RuntimeError(f"{name} must be between {low} and {high}")
    return value


def motor_signs() -> tuple[int, int, int, int]:
    """Per-motor polarity for M1-M4, so a wheel wired backwards can be flipped."""
    raw = os.environ.get("ROBOT_MOTOR_SIGNS", "1,1,1,1")
    try:
        signs = tuple(int(value) for value in raw.split(","))
    except ValueError as error:
        raise RuntimeError("ROBOT_MOTOR_SIGNS must be four comma-separated 1 or -1 values") from error
    if len(signs) != 4 or any(value not in (-1, 1) for value in signs):
        raise RuntimeError("ROBOT_MOTOR_SIGNS must be four comma-separated 1 or -1 values")
    return signs


# FLIH's motor profile. The board saves these to flash, but its factory reduction
# ratio is 30 and the L-type 520 motors are 40:1, so closed-loop speed runs a
# quarter low until this is pushed. Values mirror fly-gym/robot_config.py and the
# 67.5 mm wheel in wheel_positions.pdf.
MOTOR_TYPE = number("ROBOT_MOTOR_TYPE", 1, 1, 4)
REDUCTION_RATIO = number("ROBOT_REDUCTION_RATIO", 40, 1, 65535)
ENCODER_LINES = number("ROBOT_ENCODER_LINES", 11, 1, 65535)
DEADZONE = number("ROBOT_DEADZONE", 1600, 0, 3600)
WHEEL_DIAMETER_MM = number("ROBOT_WHEEL_DIAMETER_MM", 67.5, 1, 1000, whole=False)

# Type 4 is the TT motor without an encoder, which has no closed loop to command;
# it has to run open-loop on $pwm instead of $spd.
OPEN_LOOP = MOTOR_TYPE == 4
DRIVE_COMMAND = "pwm" if OPEN_LOOP else "spd"
SPEED_LIMIT = 3600 if OPEN_LOOP else 1000  # Manual sections 8 and 9.

DRIVE_SPEED = number("ROBOT_DRIVE_SPEED", 1000 if OPEN_LOOP else 250, 0, SPEED_LIMIT)
# Spinning in place is the twitchiest thing to tune, so it gets its own ceiling.
TURN_SPEED = number("ROBOT_TURN_SPEED", DRIVE_SPEED, 0, SPEED_LIMIT)


class MotorBoard:
    def __init__(self, port: str = SERIAL_PORT):
        self.signs = motor_signs()
        self.port = serial.Serial(
            port,
            115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1,
        )
        time.sleep(0.2)  # The Pico's USB serial needs a moment after the port opens.

    def send(self, frame: str) -> None:
        self.port.write(frame.encode("ascii"))
        self.port.flush()

    def drain(self) -> str:
        """Take whatever the board has said back. Config writes answer `command+OK`."""
        pending = self.port.in_waiting
        return self.port.read(pending).decode("ascii", "replace").strip() if pending else ""

    def write_speeds(self, speeds) -> None:
        signed = [
            max(-SPEED_LIMIT, min(SPEED_LIMIT, int(speed) * sign))
            for speed, sign in zip(speeds, self.signs)
        ]
        self.send(f"${DRIVE_COMMAND}:{signed[0]},{signed[1]},{signed[2]},{signed[3]}#")

    def stop(self) -> None:
        """Hold still. On $spd the PID keeps braking, which is what a stop wants."""
        self.write_speeds((0, 0, 0, 0))

    def release(self) -> None:
        """Cut drive entirely so the wheels push freely. $spd:0 alone stays clamped."""
        self.send("$pwm:0,0,0,0#")

    def drive(self, forward: int, turn: int) -> None:
        left = max(-1, min(1, forward + turn))
        right = max(-1, min(1, forward - turn))
        speed = TURN_SPEED if forward == 0 else DRIVE_SPEED
        self.write_speeds((left * speed, left * speed, right * speed, right * speed))

    def configure(self) -> None:
        """Push the motor profile and silence telemetry nothing here reads.

        Each write answers `command+OK`. A silent reply is not on its own a failure:
        replies only survive the USB link when the Pico relay is in the path.
        """
        print(f"Configuring the motor board on {self.port.name} (driving with ${DRIVE_COMMAND})")
        for name, value in (
            ("mtype", MOTOR_TYPE),
            ("deadzone", DEADZONE),
            ("mline", ENCODER_LINES),
            ("mphase", REDUCTION_RATIO),
            ("wdiameter", f"{WHEEL_DIAMETER_MM:.2f}"),
            ("upload", "0,0,0"),
        ):
            self.send(f"${name}:{value}#")
            time.sleep(0.1)  # Some writes restart the chip; let it come back first.
            print(f"  ${name}:{value}# -> {self.drain() or 'no reply'}")

    def battery_volts(self) -> float | None:
        """Ask the board for pack voltage; it answers `$Battery:7.40V#`."""
        self.drain()
        self.send("$read_vol#")
        time.sleep(0.1)
        reply = self.drain()
        marker = reply.find("$Battery:")
        if marker < 0:
            return None
        try:
            return float(reply[marker + 9:].split("V")[0])
        except ValueError:
            return None

    def close(self) -> None:
        self.stop()
        self.release()
        self.port.close()
