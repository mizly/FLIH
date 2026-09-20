"""Publishes the robot's LiDAR to the web app as JSON scans over a WebSocket.

Holds an authenticated socket to the web app's /ws/lidar endpoint and pushes one
message per completed revolution. The server fans those out to whoever has the
control page open, the same way `camera_stream.py` feeds the camera panes.

This is a **separate process and a separate socket** from `robot_websocket.py`, for
the reason set out at the top of `camera_stream.py`: sensor traffic is bulk and
driving is latency-critical, and a scan queued ahead of a drive command on one TCP
connection delays that command by however long the scan takes to flush. A scanner
that wedges cannot take the motors down with it either.

    export ROBOT_API_KEY=... ROBOT_LIDAR_WS_URL=ws://127.0.0.1:3000/ws/lidar
    python3 backend/lidar_stream.py

The message is one JSON object per turn:

    {"type": "scan", "stamp": 1758300000.12, "points": 667, "returns": 640,
     "hz": 6.2, "reportedHz": 6.0, "maxRange": 12.0, "demo": false,
     "angles": [...], "ranges": [...]}

`angles` are radians in the robot frame, 0 forward and positive to the left;
`ranges` are metres, 0.0 where nothing came back. They line up index for index.
`lidar.py` is where that convention is set and explained. Intensity is not sent:
nothing reads it yet, and it would be a third of the message.
"""

import argparse
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import websocket

import lidar as lidar_module
from fly_advisor import DEFAULT_CHECKPOINT, FlyPolicyAdvisor
from lidar import TminiPlus
from omni_fusion import OmniFusion
from safety_signal import SafetyIndicator, load_led_output

# A turn is ~667 points and the scanner tops out near 10 Hz, so publishing every
# revolution costs well under a tenth of what the video link does. No point rounding
# the data harder than the sensor resolves it: a quarter-millimetre is 6 decimals of
# a metre, and a tenth of a degree is 4 of a radian.
RANGE_DECIMALS = 3
ANGLE_DECIMALS = 4

running = True
client = None


def log(message):
    print(message, file=sys.stderr, flush=True)


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("%s must be set" % name)
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=None,
                        help="serial port; default is /dev/ydlidar, then autodetect")
    parser.add_argument("--baudrate", type=int, default=lidar_module.BAUDRATE)
    parser.add_argument("--no-intensity", action="store_true",
                        help="unit reconfigured to 2-byte samples without intensity")
    parser.add_argument("--zero-offset-deg", type=float, default=lidar_module.ZERO_OFFSET_DEG,
                        help="where the scanner's zero mark sits, CCW from forward "
                             "(default: %g)" % lidar_module.ZERO_OFFSET_DEG)
    parser.add_argument("--max-range", type=float, default=12.0,
                        help="range ring the control page draws to (default: 12.0)")
    parser.add_argument("--max-hz", type=float, default=10.0,
                        help="upper bound on publish rate (default: 10)")
    parser.add_argument("--demo", action="store_true",
                        help="synthesise a scan instead of opening the port, to "
                             "exercise the web path with no scanner attached")
    parser.add_argument("--led-driver", default=os.environ.get("ROBOT_LED_DRIVER", ""),
                        help="optional LED output as module:factory; no hardware by default")
    parser.add_argument("--safety-sector-deg", type=float, help=argparse.SUPPRESS)
    parser.add_argument("--omni-interval", type=float,
                        default=float(os.environ.get("ROBOT_OMNI_INTERVAL", "5")),
                        help="minimum seconds between OMNI fusion calls (default: 5)")
    parser.add_argument("--no-omni", action="store_true",
                        help="disable camera/LiDAR OMNI fusion even when a key is configured")
    parser.add_argument("--fly-checkpoint", type=Path,
                        default=Path(os.environ.get("ROBOT_FLY_CHECKPOINT", DEFAULT_CHECKPOINT)),
                        help="connectome checkpoint used for advisory steering")
    parser.add_argument("--no-fly-policy", action="store_true",
                        help="disable the experimental connectome policy advisor")
    return parser.parse_args(argv)


def payload(scan, args, demo=False, safety=None, omni=None, fly_advice=None):
    safety_fields = {}
    if safety is not None:
        safety_fields = {
            "safetySignal": safety.signal.value,
            "safetyDirection": safety.direction,
            "safetyClearance": (None if safety.clearance_m is None
                                else round(safety.clearance_m, RANGE_DECIMALS)),
        }
    return json.dumps({
        "type": "scan",
        "stamp": round(scan.stamp, 3),
        "points": len(scan),
        "returns": scan.returns,
        "hz": round(scan.measured_hz, 2),
        "reportedHz": round(scan.reported_hz, 1),
        "maxRange": args.max_range,
        "demo": demo,
        "angles": [round(a, ANGLE_DECIMALS) for a in scan.angles],
        "ranges": [round(r, RANGE_DECIMALS) for r in scan.ranges],
        **safety_fields,
        **({"omni": omni} if omni is not None else {}),
        **({"flyAdvice": fly_advice} if fly_advice is not None else {}),
    }, separators=(",", ":"))


def demo_scan(turn):
    """A plausible room, so the socket and the plot can be checked without hardware.

    Deliberately not a circle: four walls at different distances and a post off to
    one side, drifting slowly, so a plot that is stuck, mirrored or rotated is
    obvious at a glance rather than merely plausible. Every message it produces
    carries "demo": true and the page says so on screen.
    """
    import math

    points = 667
    angles, ranges = [], []
    spin = turn * 0.05
    for index in range(points):
        angle = -math.pi + 2 * math.pi * index / points
        world = angle + spin
        # Rectangular room, 4 m by 2.6 m, robot off centre.
        reach = min(abs(2.0 / math.cos(world)) if math.cos(world) else 99,
                    abs(1.3 / math.sin(world)) if math.sin(world) else 99)
        if -0.5 < angle < -0.3:
            reach = min(reach, 0.9)  # a post, front right
        angles.append(angle)
        ranges.append(0.0 if index % 53 == 0 else round(reach, 3))
    return lidar_module.Scan(time.time(), angles, ranges, [0] * points, [0] * points, 6.0, 6.0)


def publish(socket, lidar, args, indicator, fusion, fly_advisor):
    """Send one message per new revolution until the socket or the scanner dies."""
    interval = 1.0 / max(args.max_hz, 1.0)
    sent = 0
    turn = 0
    next_tick = time.monotonic()

    while running and socket.sock is not None:
        next_tick += interval
        if args.demo:
            turn += 1
            scan, serial = demo_scan(turn), turn
        else:
            scan, serial = lidar.read()

        # Nothing new since the last tick means the scanner is slower than the
        # publish rate; resending a turn would only burn bandwidth.
        if scan is not None and serial != sent:
            sent = serial
            safety = indicator.update_scan(scan)
            omni = fusion.observe_scan(scan, safety.direction)
            fly_advice = fly_advisor.observe_scan(scan, safety.direction)
            try:
                socket.send(payload(scan, args, demo=args.demo, safety=safety, omni=omni,
                                    fly_advice=fly_advice))
            except (websocket.WebSocketException, OSError) as error:
                log("LiDAR link send failed: %s" % error)
                return

        if not args.demo and not lidar.running:
            log("Scanner stopped delivering packets: %s" % (lidar.error or "no packets"))
            return

        slack = next_tick - time.monotonic()
        if slack > 0:
            time.sleep(slack)
        else:
            next_tick = time.monotonic()


def shutdown(_signal, _frame):
    global running
    running = False
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def main():
    global client
    args = parse_args()
    url = os.environ.get("ROBOT_LIDAR_WS_URL", "").strip()
    if not url:
        # Every endpoint lives on the same server, so derive this one rather than
        # make the operator set three nearly identical URLs.
        url = required("ROBOT_WS_URL").rsplit("/ws/robot", 1)[0] + "/ws/lidar"
    api_key = required("ROBOT_API_KEY")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    lidar = None
    indicator = SafetyIndicator(load_led_output(args.led_driver))
    fusion = OmniFusion(args.omni_interval, enabled=not args.no_omni)
    log("OMNI camera/LiDAR fusion %s" % ("enabled" if fusion.enabled else "disabled"))
    fly_advisor = FlyPolicyAdvisor(args.fly_checkpoint, enabled=not args.no_fly_policy)
    log("Fly connectome advisor %s" % ("enabled" if fly_advisor.enabled else "disabled"))
    if args.demo:
        log("DEMO MODE: publishing a synthetic room. Nothing here is measured.")
    else:
        port = args.port or lidar_module.find_port()
        if port is None:
            log("No scanner found. /dev/ydlidar is absent and no USB serial port "
                "looks like a CP210x bridge. Check the cable, run the vendor's "
                "hardware/Jetson NANO/lidar/yahboomcar_ws/src/ydlidar_ros2_driver-humble/"
                "startup/initenv.sh once to install the udev rules, or pass --port. "
                "Use --demo to exercise the web path with no scanner attached.")
            return 1
        lidar = TminiPlus(port, args.baudrate, not args.no_intensity,
                          args.zero_offset_deg)
        if not lidar.start():
            log("Could not open %s: %s" % (port, lidar.error))
            return 1
        log("Scanner on %s at %d baud, zero mark %g deg CCW of forward"
            % (port, args.baudrate, args.zero_offset_deg))

    try:
        while running:
            try:
                client = websocket.create_connection(
                    url,
                    header=["Authorization: Bearer %s" % api_key],
                    timeout=10,
                    enable_multithread=True,
                )
            except (websocket.WebSocketException, OSError) as error:
                log("LiDAR link connect failed, retrying: %s" % error)
                if running:
                    time.sleep(2)
                continue

            log("LiDAR link up")
            # The server pings every 250 ms and terminates sockets that do not
            # pong, so something has to be reading while we send.
            reader = threading.Thread(target=drain,
                                      args=(client, indicator, fusion, fly_advisor), daemon=True)
            reader.start()
            try:
                publish(client, lidar, args, indicator, fusion, fly_advisor)
            finally:
                try:
                    client.close()
                except Exception:
                    pass
                reader.join(timeout=2.0)
                log("LiDAR link down")

            if lidar is not None and not lidar.running:
                break
            if running:
                time.sleep(2)
    finally:
        if lidar is not None:
            lidar.release()
        indicator.close()
        fusion.close()
        fly_advisor.close()
    return 0


def drain(socket, indicator, fusion, fly_advisor):
    """Read drive direction updates while also answering server pings."""
    while running and socket.sock is not None:
        try:
            raw = socket.recv()
            if isinstance(raw, (bytes, bytearray)):
                if len(raw) > 1:
                    fusion.offer_camera(raw[0], raw[1:])
                    fly_advisor.offer_camera(raw[0], raw[1:])
                continue
            message = json.loads(raw)
            if message.get("type") == "drive" and message.get("forward") in (-1, 0, 1):
                reading = indicator.set_motion(message["forward"])
                clearance = ("unknown" if reading.clearance_m is None
                             else "%.2f m" % reading.clearance_m)
                log("Safety LED: %s (%s, %s)" %
                    (reading.signal.value, reading.direction, clearance))
        except (websocket.WebSocketException, OSError, ValueError, TypeError, json.JSONDecodeError):
            return


if __name__ == "__main__":
    raise SystemExit(main())
