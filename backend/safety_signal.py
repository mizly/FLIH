"""Omnidirectional LiDAR clearance signals and an LED hardware boundary.

The scanner uses the robot frame: zero radians is forward and angles increase to
the left.  This module deliberately knows nothing about the T-mini serial protocol
or a particular GPIO library, which makes the safety calculation testable now and
lets an LED driver be added later without changing it.
"""

from dataclasses import dataclass
from enum import Enum
import importlib
import math
import threading


RED_DISTANCE_M = 0.20
GREEN_DISTANCE_M = 0.50


class SafetySignal(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


@dataclass(frozen=True)
class SafetyReading:
    signal: SafetySignal
    clearance_m: float | None
    direction: str


class NoHardwareLedOutput:
    """Placeholder used until LEDs are attached.

    `last_signal` also makes the result observable in tests.  A hardware adapter
    only needs the same `set_signal(signal)` and `close()` methods.
    """

    def __init__(self):
        self.last_signal = None

    def set_signal(self, signal):
        self.last_signal = signal

    def close(self):
        pass


def load_led_output(spec):
    """Create an LED output from ``module:factory`` or use the placeholder.

    The factory may be a class or a zero-argument function.  This keeps GPIO
    packages out of the backend until the actual LED and pins are chosen.
    """
    if not spec:
        return NoHardwareLedOutput()
    try:
        module_name, factory_name = spec.rsplit(":", 1)
    except ValueError as error:
        raise ValueError("LED driver must be in module:factory form") from error
    output = getattr(importlib.import_module(module_name), factory_name)()
    if not callable(getattr(output, "set_signal", None)):
        raise TypeError("LED driver must provide set_signal(signal)")
    return output


def signal_for_clearance(clearance_m):
    """Map metres to the requested traffic-light thresholds.

    Twenty centimetres is included in red.  Fifty centimetres is included in
    green, matching the explicit "50 cm+" requirement.
    """
    if clearance_m <= RED_DISTANCE_M:
        return SafetySignal.RED
    if clearance_m < GREEN_DISTANCE_M:
        return SafetySignal.YELLOW
    return SafetySignal.GREEN


def nearest_clearance(angles, ranges):
    """Return the nearest valid range anywhere around the robot.

    A zero range is the scanner's "no return" value and is ignored. ``None``
    means that the scan contained no usable obstacle return.
    """
    candidates = (
        distance
        for angle, distance in zip(angles, ranges)
        if math.isfinite(angle)
        and math.isfinite(distance)
        and distance > 0
    )
    return min(candidates, default=None)


class SafetyIndicator:
    """Drive an LED from the nearest return in the latest full scan."""

    def __init__(self, output=None, sector_degrees=None):
        self.output = output or NoHardwareLedOutput()
        # Kept as an ignored argument so older launch code can migrate without a
        # coordinated deploy. Clearance is always evaluated over the full scan.
        self.sector_degrees = sector_degrees
        self._forward = 0
        self._angles = None
        self._ranges = None
        self._lock = threading.Lock()
        self._reading = SafetyReading(SafetySignal.GREEN, None, "stopped")
        self.output.set_signal(self._reading.signal)

    @property
    def reading(self):
        with self._lock:
            return self._reading

    def set_motion(self, forward):
        if forward not in (-1, 0, 1):
            raise ValueError("forward must be -1, 0, or 1")
        with self._lock:
            self._forward = forward
            return self._evaluate_locked()

    def update_scan(self, scan):
        with self._lock:
            self._angles = tuple(scan.angles)
            self._ranges = tuple(scan.ranges)
            return self._evaluate_locked()

    def _evaluate_locked(self):
        direction = "forward" if self._forward > 0 else "reverse" if self._forward < 0 else "stopped"
        if self._angles is None:
            # Red is the fail-safe choice while moving without a scan.
            signal = SafetySignal.RED if self._forward != 0 else SafetySignal.GREEN
            reading = SafetyReading(signal, None, direction)
        else:
            clearance = nearest_clearance(self._angles, self._ranges)
            signal = SafetySignal.GREEN if clearance is None else signal_for_clearance(clearance)
            reading = SafetyReading(signal, clearance, direction)

        if reading.signal != self._reading.signal:
            self.output.set_signal(reading.signal)
        self._reading = reading
        return reading

    def close(self):
        close = getattr(self.output, "close", None)
        if callable(close):
            close()


# Keep the former public name working for robot-side integrations while they move
# to the clearer name. Its behaviour is now omnidirectional.
DirectionalSafetyIndicator = SafetyIndicator
