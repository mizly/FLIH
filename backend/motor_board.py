"""Motor control for FLIH's Yahboom 4-channel motor drive board.

The board speaks two protocols and FLIH can reach it either way, chosen by
ROBOT_TRANSPORT:

    serial  (default) ASCII `$cmd:args#` frames down a serial port to the Pico 2
            relay in hardware/PICO2/remote_control.py, which re-emits them as I2C
            writes. This is the path FLIH has actually driven on.
    i2c     the Jetson's own I2C controller wired straight to the 40-pin header,
            board at 0x26, no Pico. Written and unit-tested, never yet run against
            the hardware.

Both end at the same registers; only the path differs. The i2c transport is fewer
parts but has **no hardware dead-man**: the Pico relay stops the motors by itself
500 ms after the last command, and nothing on the direct path does. The server's
350 ms stop still covers a browser going away, but if this process is killed
mid-drive the board holds its last commanded speed until power is cut.

On an Orin, the 40-pin I2C at pins 3 (SDA) and 5 (SCL) is bus 7, not bus 1 as the
vendor's Jetson sample hardcodes; bus 1 is pins 27/28. `i2cdetect -y -r 7` should
show 26.

The manual numbers the outputs M1 front left, M2 rear left, M3 front right, M4 rear
right. **FLIH is not wired that way**, and the end its chassis has labelled "front"
is not the end it drives toward. The confirmed map is in hardware/MOTOR_MAP.md and
the defaults below are those values; that file is the single source of truth, and
this docstring is a summary of it, not a second copy to be edited on its own.

Two ways to get it wrong, with very different symptoms:

    Wrong sides         Driving straight looks perfect - every wheel gets the same
                        value - and only the turns are broken.
    Signs and sides
    both flipped        Forward and reverse are inverted and the turns stay
                        *exactly* correct. Rotation about the centre is the same
                        whichever end you call the front, so nothing you can do
                        with A and D will reveal it. This has shipped twice.

Because the second one is invisible to every check except "does W drive the way the
robot faces", the confirmed values are the defaults here rather than something the
operator exports by hand. tests/test_drive_mixing.py pins them.
"""

import math
import os
import struct
import threading
import time

TRANSPORT = (os.environ.get("ROBOT_TRANSPORT", "") or "serial").strip().lower()
SERIAL_PORT = os.environ.get("ROBOT_SERIAL_PORT", "/dev/ttyACM0")

# Registers, from the vendor sample in hardware/PICO2/IIC/IIC.py.
REGISTERS = {
    "mtype": 0x01,
    "deadzone": 0x02,
    "mline": 0x03,
    "mphase": 0x04,
    "wdiameter": 0x05,
    "spd": 0x06,
    "pwm": 0x07,
}
# Telemetry is pushed over serial and polled over I2C, so there is no register for it.
NO_REGISTER = ("upload", "read_vol")


def number(name: str, default: float, low: float, high: float, whole: bool = True):
    try:
        value = (int if whole else float)(os.environ.get(name, "") or default)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a number") from error
    if not low <= value <= high:
        raise RuntimeError(f"{name} must be between {low} and {high}")
    return value


def motor_sides() -> tuple[str, ...]:
    """Which side of the chassis each of M1-M4 drives, in motor order.

    Defaults to FLIH's confirmed harness rather than the manual's numbering; see
    hardware/MOTOR_MAP.md. Override only if the motors are re-plugged, and re-run
    backend/motor_check.py if you do.
    """
    raw = os.environ.get("ROBOT_MOTOR_SIDES", "L,R,L,R")
    sides = tuple(value.strip().upper()[:1] for value in raw.split(","))
    if len(sides) != 4 or any(side not in ("L", "R") for side in sides):
        raise RuntimeError("ROBOT_MOTOR_SIDES must be four comma-separated L or R values")
    return sides


def motor_signs() -> tuple[int, ...]:
    """Per-motor polarity for M1-M4, so a wheel wired backwards can be flipped.

    Defaults to the confirmed values in hardware/MOTOR_MAP.md. These travel with
    ROBOT_MOTOR_SIDES: flipping every sign *and* every side negates forward while
    leaving the turns untouched, which is the failure this default exists to stop.
    """
    raw = os.environ.get("ROBOT_MOTOR_SIGNS", "1,-1,-1,1")
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
MOTOR_SIDES = motor_sides()
MOTOR_TYPE = number("ROBOT_MOTOR_TYPE", 1, 1, 4)
REDUCTION_RATIO = number("ROBOT_REDUCTION_RATIO", 40, 1, 65535)
ENCODER_LINES = number("ROBOT_ENCODER_LINES", 11, 1, 65535)
DEADZONE = number("ROBOT_DEADZONE", 1600, 0, 3600)
WHEEL_DIAMETER_MM = number("ROBOT_WHEEL_DIAMETER_MM", 67.5, 1, 1000, whole=False)

I2C_BUS = number("ROBOT_I2C_BUS", 7, 0, 32)
I2C_ADDRESS = number("ROBOT_I2C_ADDRESS", 0x26, 0x03, 0x77)

# Type 4 is the TT motor without an encoder, which has no closed loop to command;
# it has to run open-loop on $pwm instead of $spd.
OPEN_LOOP = MOTOR_TYPE == 4
DRIVE_COMMAND = "pwm" if OPEN_LOOP else "spd"
SPEED_LIMIT = 3600 if OPEN_LOOP else 1000  # Manual sections 8 and 9.

DRIVE_SPEED = number("ROBOT_DRIVE_SPEED", 1800 if OPEN_LOOP else 500, 0, SPEED_LIMIT)
# Spinning in place is the twitchiest thing to tune, so it gets its own ceiling.
TURN_SPEED = number("ROBOT_TURN_SPEED", DRIVE_SPEED, 0, SPEED_LIMIT)

# How much of a full turn to apply while also driving forward, as a fraction. At 1.0 a
# forward+turn command cancels one side to exactly zero - the inside wheels stop dead
# and the robot lurches instead of arcing. Below 1.0 both sides keep turning and the
# robot curves. Pure spins (forward == 0) always get full authority regardless.
TURN_RATIO = max(0.0, min(1.0, float(os.environ.get("ROBOT_TURN_RATIO", "0.5"))))

# Floor for a non-zero commanded speed. Mixing can ask for a speed too small to break
# static friction, which reads as a stalled wheel and, on $spd, as the PID grinding
# against a load it cannot move. 0 disables the floor.
MIN_SPEED = number("ROBOT_MIN_SPEED", 0 if OPEN_LOOP else 120, 0, SPEED_LIMIT)


def int16(value) -> list:
    """Two bytes big-endian. Negative values land as two's complement."""
    value = max(-32768, min(32767, int(value)))
    return [(value >> 8) & 0xFF, value & 0xFF]


def payload_for(name: str, args: str) -> list:
    """Encode one command's arguments the way its register expects them."""
    if name in ("spd", "pwm"):
        parts = args.split(",")
        if len(parts) != 4:
            raise ValueError("expected four speeds")
        return [byte for part in parts for byte in int16(part)]
    if name == "mtype":
        return [int(args) & 0xFF]
    if name == "wdiameter":
        return list(struct.pack("<f", float(args)))
    return int16(args)


class I2CLink:
    """The Jetson's own I2C controller, talking to the board directly."""

    def __init__(self) -> None:
        from smbus2 import SMBus

        self.name = f"/dev/i2c-{I2C_BUS} at 0x{I2C_ADDRESS:02x}"
        self.bus = SMBus(I2C_BUS)
        try:  # Fail loudly at startup rather than on the first drive command.
            self.bus.write_quick(I2C_ADDRESS)
        except OSError as error:
            raise RuntimeError(
                f"no motor board at 0x{I2C_ADDRESS:02x} on /dev/i2c-{I2C_BUS} ({error}). "
                f"Check wiring and run: i2cdetect -y -r {I2C_BUS}"
            ) from error

    def command(self, name: str, args: str = "") -> str:
        if name in NO_REGISTER:
            return "skipped (no i2c register)"
        try:
            self.bus.write_i2c_block_data(I2C_ADDRESS, REGISTERS[name], payload_for(name, args))
        except (OSError, KeyError, ValueError) as error:
            return f"error: {error}"
        return "command+OK"

    def close(self) -> None:
        self.bus.close()


class SerialLink:
    """ASCII `$cmd:args#` frames to the Pico 2 relay, which re-emits them as I2C."""

    def __init__(self) -> None:
        import serial

        self.name = SERIAL_PORT
        self.port = serial.Serial(
            SERIAL_PORT,
            115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1,
        )
        time.sleep(0.2)  # The Pico's USB serial needs a moment after the port opens.

    def drain(self) -> str:
        pending = self.port.in_waiting
        return self.port.read(pending).decode("ascii", "replace").strip() if pending else ""

    def command(self, name: str, args: str = "") -> str:
        self.port.write((f"${name}:{args}#" if args else f"${name}#").encode("ascii"))
        self.port.flush()
        return ""  # Replies are drained by the caller, which controls the timing.

    def close(self) -> None:
        self.port.close()


class MotorBoard:
    def __init__(self) -> None:
        self.signs = motor_signs()
        self.link = I2CLink() if TRANSPORT == "i2c" else SerialLink()
        # robot_websocket.py stops the motors from a watchdog thread while the socket
        # thread may be mid-drive. Two interleaved writes on one link produce a frame
        # the board reads as neither command, so serialise them.
        self.lock = threading.Lock()

    def command(self, name: str, args: str = "") -> str:
        with self.lock:
            return self.link.command(name, args)

    def write_speeds(self, speeds) -> None:
        signed = [
            max(-SPEED_LIMIT, min(SPEED_LIMIT, int(speed) * sign))
            for speed, sign in zip(speeds, self.signs)
        ]
        self.command(DRIVE_COMMAND, ",".join(str(value) for value in signed))

    def stop(self) -> None:
        """Hold still. On $spd the PID keeps braking, which is what a stop wants."""
        self.write_speeds((0, 0, 0, 0))

    def poll_errors(self) -> str:
        """Any `$err:` the relay has sent back since the last poll, or "".

        Drive frames are written without waiting for a reply, so without this the
        relay's errors - including a watchdog stop that never reached the board - are
        read by nobody. Only meaningful on the serial transport; I2CLink reports
        failures inline from command().
        """
        if not isinstance(self.link, SerialLink):
            return ""
        with self.lock:
            pending = self.link.drain()
        return "\n".join(
            line for line in pending.splitlines() if line.startswith("$err:")
        )

    def release(self) -> None:
        """Cut drive entirely so the wheels push freely. $spd:0 alone stays clamped."""
        self.command("pwm", "0,0,0,0")

    @staticmethod
    def with_floor(speed: float) -> int:
        """Round away from zero to MIN_SPEED, so a slow wheel turns instead of stalling."""
        value = int(round(speed))
        if value == 0 or MIN_SPEED == 0:
            return value
        return int(math.copysign(max(abs(value), MIN_SPEED), value))

    def drive(self, forward: int, turn: int) -> None:
        """Mix forward/turn onto the two sides. Positive turn swings right.

        Clamping each side to +-1 the way this used to zeroes the inside wheels on any
        forward+turn combination. Scale the turn instead and normalise, which keeps the
        ratio between the sides and leaves both of them driving.
        """
        authority = 1.0 if forward == 0 else TURN_RATIO
        left = forward + turn * authority
        right = forward - turn * authority
        peak = max(1.0, abs(left), abs(right))
        left /= peak
        right /= peak
        speed = TURN_SPEED if forward == 0 else DRIVE_SPEED
        self.write_speeds(
            tuple(
                self.with_floor((left if side == "L" else right) * speed)
                for side in MOTOR_SIDES
            )
        )

    def configure(self) -> None:
        """Push the motor profile and silence telemetry nothing here reads."""
        print(f"Configuring the motor board on {self.link.name} (driving with {DRIVE_COMMAND})")
        if isinstance(self.link, SerialLink):
            time.sleep(0.1)   # Let an earlier frame's reply land before clearing it,
            self.link.drain()  # so each line below reports only its own frame's answer.
        for name, value in (
            ("mtype", MOTOR_TYPE),
            ("deadzone", DEADZONE),
            ("mline", ENCODER_LINES),
            ("mphase", REDUCTION_RATIO),
            ("wdiameter", f"{WHEEL_DIAMETER_MM:.2f}"),
            ("upload", "0,0,0"),
        ):
            result = self.command(name, str(value))
            time.sleep(0.1)  # Some writes restart the chip; let it come back first.
            if isinstance(self.link, SerialLink):
                result = self.link.drain()
            print(f"  {name}:{value} -> {result or 'no reply'}")

    def battery_volts(self) -> float | None:
        """Pack voltage, over serial only: the I2C register map has no battery entry."""
        if not isinstance(self.link, SerialLink):
            return None
        self.link.drain()
        self.command("read_vol")
        time.sleep(0.1)
        reply = self.link.drain()
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
        self.link.close()
