#!/usr/bin/env python3
"""Print the LiDAR to the terminal, on the Jetson itself.

The bench counterpart to `backend/lidar_stream.py`: same driver, but the scan goes
to stdout here instead of to the web app. Use it to check the scanner is alive, that
the ranges are sane, and - the one thing no amount of code can settle - that the
plot is pointing the way the robot is.

    python3 test_lidar.py                 # ASCII plot, 4 m across
    python3 test_lidar.py --view 2        # zoom in
    python3 test_lidar.py --bearings      # nearest return in each 30-degree sector
    python3 test_lidar.py --raw           # device angles, before the frame conversion

Two checks worth doing the first time a scanner is plugged in, in this order:

1.  **Scale.** Face a flat wall, measure the gap with a tape, and compare it with
    what `--bearings` prints ahead. A reading 4x or 1/4 of the truth means the
    quarter-millimetre scale in backend/lidar.py is wrong for this unit.

2.  **Heading.** Stand something narrow - a chair leg, a bottle - about a metre
    directly in front of the robot and watch where it lands. It should be at the top
    of the plot, and `--bearings` should put it in the `+0.0 deg` row. If it is not,
    adjust ZERO_OFFSET_DEG in backend/lidar.py: add 90 for each quarter turn the map
    needs to rotate counterclockwise, 180 if it is exactly backwards. It is currently
    270, measured on this robot; the vendor's yaml would imply 180. Do this whenever
    the scanner is re-seated, because a rotated scan looks completely plausible until
    the robot moves.

Press Ctrl-C to stop.
"""
import argparse
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "backend"))

import lidar as lidar_module  # noqa: E402  (needs the path above)
from lidar import TminiPlus  # noqa: E402  (needs the path above)

SECTORS = 12


def plot(scan, view, width=61, height=29):
    """A top-down scan as characters, robot at the centre facing up."""
    grid = [[" "] * width for _ in range(height)]
    # Cells are wider than they are tall in a terminal, so the horizontal axis gets
    # roughly twice the resolution to keep a round room looking round.
    for angle, metres in zip(scan.angles, scan.ranges):
        if not (0 < metres <= view):
            continue
        column = int(round(width / 2 - math.sin(angle) * metres / view * (width / 2 - 1)))
        row = int(round(height / 2 - math.cos(angle) * metres / view * (height / 2 - 1)))
        if 0 <= column < width and 0 <= row < height:
            grid[row][column] = "#" if grid[row][column] == " " else "@"
    grid[height // 2][width // 2] = "^"
    border = "+" + "-" * width + "+"
    return "\n".join([border] + ["|" + "".join(row) + "|" for row in grid] + [border])


def bearings(scan):
    """Nearest return per 30-degree sector, one of them centred straight ahead.

    Sectors are centred on their bearing rather than starting at it, so the nose
    gets a row of its own instead of falling on the boundary between two - which
    matters, because the nose is the bearing the heading check depends on.
    """
    span = 2 * math.pi / SECTORS
    nearest = [float("inf")] * SECTORS
    for angle, metres in zip(scan.angles, scan.ranges):
        if metres <= 0:
            continue
        sector = int(((angle + span / 2) % (2 * math.pi)) / span) % SECTORS
        nearest[sector] = min(nearest[sector], metres)

    rows = []
    for index, metres in enumerate(nearest):
        centre = math.degrees(span * index)
        rows.append((centre - 360 if centre >= 180 else centre, metres))
    rows.sort()

    return "\n".join(
        "%+7.1f deg   %s   %s" % (centre,
                                  "   --  " if math.isinf(metres) else "%6.2f m" % metres,
                                  "ahead" if centre == 0 else "")
        for centre, metres in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", default=None, help="serial port (default: autodetect)")
    parser.add_argument("--baudrate", type=int, default=lidar_module.BAUDRATE)
    parser.add_argument("--no-intensity", action="store_true")
    parser.add_argument("--zero-offset-deg", type=float, default=lidar_module.ZERO_OFFSET_DEG)
    parser.add_argument("--view", type=float, default=4.0, help="metres across the plot")
    parser.add_argument("--bearings", action="store_true", help="sector table instead of a plot")
    parser.add_argument("--raw", action="store_true",
                        help="device angles, clockwise from the scanner's own zero")
    args = parser.parse_args()

    port = args.port or lidar_module.find_port()
    if port is None:
        print("No scanner found. Check the cable, install the vendor udev rules from "
              "yahboomcar_ws/src/ydlidar_ros2_driver-humble/startup/initenv.sh, or pass --port.")
        return 1

    zero_offset = 0.0 if args.raw else args.zero_offset_deg
    scanner = TminiPlus(port, args.baudrate, not args.no_intensity, zero_offset)
    if not scanner.start():
        print("Could not open %s: %s" % (port, scanner.error))
        return 1
    print("Reading %s at %d baud%s" % (port, args.baudrate, "  [RAW device angles]" if args.raw else ""))

    seen = 0
    try:
        while scanner.running:
            scan, serial = scanner.read()
            if scan is None or serial == seen:
                time.sleep(0.02)
                continue
            seen = serial
            header = ("turn %d   %d points, %d returns   %.1f Hz measured, %.1f reported"
                      % (serial, len(scan), scan.returns, scan.measured_hz, scan.reported_hz))
            body = bearings(scan) if args.bearings else plot(scan, args.view)
            print("\033[H\033[J%s\n%s" % (header, body), flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        scanner.release()
        if scanner.error:
            print("Scanner stopped: %s" % scanner.error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
