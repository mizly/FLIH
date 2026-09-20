#!/usr/bin/env python3
"""WHEELS-UP end-to-end test: live CSI/LiDAR -> full FLYNN -> Pico -> motor board.

python3 backend/live_flynn_drive.py --enable-motors --duration 10

No synthetic inputs or scripted driving. Wheel targets are mm/s, capped without
boosting small model outputs. Requires the existing Pico relay with its 500 ms
dead-man. Host watchdog also stops on a 350 ms command gap. Keep a cutoff nearby;
ACKs confirm relay/board communication, not measured wheel motion or safe driving.
"""

import argparse
import math
from pathlib import Path
import signal
import sys
import threading
import time

import live_flynn_shadow as shadow


def wheel_targets(speed, heading, track, max_speed, heading_gain, cap, sides):
    """Same differential-drive conversion as the sim; positive heading turns left."""
    if not all(math.isfinite(v) for v in (speed, heading, track, max_speed, heading_gain, cap)):
        raise ValueError("Non-finite action or wheel configuration")
    if track <= 0 or max_speed <= 0 or heading_gain <= 0 or cap <= 0:
        raise ValueError("Wheel configuration must be positive")
    v = max(-1, min(1, speed)) * max_speed
    omega = max(-math.pi, min(math.pi, heading)) * heading_gain
    left, right = 1000 * (v - omega * track / 2), 1000 * (v + omega * track / 2)
    scale = min(1.0, cap / max(abs(left), abs(right), 1e-9))
    return tuple(round((left if side == "L" else right) * scale) for side in sides)


class PicoSink:
    TIMEOUT = 0.35

    def __init__(self, port, cap):
        import motor_board as mb
        from serial.tools import list_ports
        sys.path.insert(0, str(shadow.FLY_GYM))
        from robot_config import WHEEL_TRACK, MAX_LINEAR_SPEED, HEADING_GAIN
        if mb.TRANSPORT != "serial" or mb.DRIVE_COMMAND != "spd":
            raise RuntimeError("This test requires the Pico serial transport and closed-loop spd")
        if mb.MOTOR_SIDES != ("L", "R", "L", "R") or mb.motor_signs() != (1, -1, -1, 1):
            raise RuntimeError("Motor map overrides differ from hardware/MOTOR_MAP.md")
        candidates = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x2E8A, 0x0005)]
        if port:
            candidates = [p for p in candidates if Path(p.device).resolve() == Path(port).resolve()]
        if len(candidates) != 1:
            raise RuntimeError("Expected exactly one Pico USB relay; check --motor-port")
        mb.SERIAL_PORT = port or candidates[0].device
        self.board = mb.MotorBoard()
        self.board.link.port.write_timeout = 0.1
        self.board.link.port.timeout = 0.05
        self.config = (WHEEL_TRACK, MAX_LINEAR_SPEED, HEADING_GAIN, cap, mb.MOTOR_SIDES)
        self.lock = threading.RLock()
        self.finished = threading.Event()
        self.last_command = None
        self.fault = None
        self.count = 0
        self.last_log = 0.0
        self.closed = False
        self.thread = None
        try:
            self.board.link.drain()
            self._stop()
            self.thread = threading.Thread(target=self._watchdog, daemon=True)
            self.thread.start()
            print(f"Pico ready on {mb.SERIAL_PORT}; STOP acknowledged; cap={cap:g} mm/s.", flush=True)
        except BaseException:
            self.close()
            raise

    def _ack(self):
        deadline = time.monotonic() + 0.2
        reply = ""
        while time.monotonic() < deadline:
            reply += self.board.link.drain()
            if "$err:" in reply:
                raise RuntimeError(f"Pico error: {reply}")
            if "command+OK" in reply:
                return
            time.sleep(0.002)
        raise TimeoutError(f"No Pico acknowledgement: {reply!r}")

    def _stop(self):
        # Attempt BOTH zero speed and zero PWM, even if one command fails.
        failures = []
        for command in ("spd", "pwm"):
            try:
                self.board.command(command, "0,0,0,0")
                self._ack()
            except Exception as exc:
                failures.append(str(exc))
        if failures:
            raise RuntimeError("STOP not fully acknowledged; use cutoff: " + "; ".join(failures))

    def _watchdog(self):
        while not self.finished.wait(0.02):
            with self.lock:
                if self.last_command is not None and time.monotonic() - self.last_command > self.TIMEOUT:
                    self.fault = "Motor watchdog: no fresh model command within 350 ms"
                    try:
                        self._stop()
                        print(self.fault + "; STOP acknowledged", flush=True)
                    except Exception as exc:
                        self.fault += f"; {exc}"
                        print(self.fault, file=sys.stderr, flush=True)
                    return

    def __call__(self, speed, heading, ages):
        with self.lock:
            if self.fault:
                raise RuntimeError(self.fault)
            if max(ages) > self.TIMEOUT:
                if self.last_command is None:
                    print("Skipping stale warm-up action; motors remain stopped.", flush=True)
                    return
                raise TimeoutError("Sensor-to-action age exceeds 350 ms")
            targets = wheel_targets(speed, heading, *self.config)
            self.board.write_speeds(targets)  # existing confirmed per-motor polarities
            self._ack()
            self.last_command = time.monotonic()
            self.count += 1
            if self.count == 1 or self.last_command - self.last_log >= 1:
                signed = tuple(value * sign for value, sign in zip(targets, self.board.signs))
                print(f"MOTOR ACK #{self.count}: model=({speed:+.4f},{heading:+.4f}) "
                      f"wheel_mm_s={targets} wire_spd={signed}", flush=True)
                self.last_log = self.last_command

    def close(self):
        if self.closed:
            return
        self.finished.set()
        with self.lock:
            self.closed = True
            try:
                self._stop()
                print(f"STOP/release acknowledged. Model motor commands acknowledged: {self.count}", flush=True)
            finally:
                self.board.link.close()
        if self.thread is not None:
            self.thread.join(timeout=0.5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-motors", action="store_true", required=True)
    parser.add_argument("--duration", type=shadow.positive_float, default=10)
    parser.add_argument("--max-wheel-mm-s", type=shadow.positive_float, default=150)
    parser.add_argument("--motor-port")
    parser.add_argument("--lidar-port")
    parser.add_argument("--checkpoint", type=Path, default=shadow.DEFAULT_CHECKPOINT)
    args = parser.parse_args(argv)
    if args.duration > 60 or args.max_wheel_mm_s > 200:
        parser.error("Test limits: duration <=60 seconds and wheel cap <=200 mm/s")
    live = shadow.parse_args(["--device", "cuda", "--duration", str(args.duration),
                              "--checkpoint", str(args.checkpoint), "--sensor-timeout", "0.35"])
    live.lidar_port = args.lidar_port
    sink = None

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, stop)
    try:
        sink = PicoSink(args.motor_port, args.max_wheel_mm_s)
        shadow.run(live, action_sink=sink)
        if not sink.count:
            raise RuntimeError("No live model commands reached the motors")
        print("PASS: live cameras/LiDAR -> full checkpoint -> Pico motor commands.")
        return 0
    except KeyboardInterrupt:
        print("Interrupted; stopping motors.")
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        try:
            if sink is not None:
                sink.close()
        finally:
            signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    sys.exit(main())
