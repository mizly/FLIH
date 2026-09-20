# LiDAR

FLIH's scanner is a **YDLIDAR T-mini Plus**, 12 m, 4000 samples/s, 6-12 Hz, 360
degrees. `fly-gym/robot_config.py` models it as `LidarConfig` and the simulator scans
with it, so the numbers here and the numbers there are meant to be the same numbers.

## Where the data is

```python
from lidar import TminiPlus          # backend/lidar.py

lidar = TminiPlus()                  # finds its own port
lidar.start()
scan, serial = lidar.read()          # newest complete turn; (None, 0) before the first

scan.ranges                          # metres, one per sample, 0.0 = nothing came back
scan.angles                          # radians, robot frame: 0 forward, positive left
scan.returns                         # how many samples actually hit something
scan.measured_hz                     # timed between turns, not what the unit claims
```

`read()` never blocks and always hands back the most recent turn, the way
`csi_camera.CsiCamera.read()` hands back the newest frame. The serial number tells a
fresh turn from one already seen.

Angles come out in the convention `fly-gym` expects, so a scan feeds the simulator's
own preprocessing with nothing in between:

```python
from core.lidar import lidar_proximity_features   # fly-gym, needs only numpy
from robot_config import LIDAR_CONFIG

features = lidar_proximity_features(scan.ranges, scan.angles, LIDAR_CONFIG)
```

Those 12 numbers are what a trained policy actually sees. Everything else in a scan
is for the operator.

In the browser, the same data arrives as JSON on `/ws/scan`, one message per
revolution - see the type at the top of `frontend/src/components/lidar-view.tsx`.

| I want | Look at |
| ------ | ------- |
| the driver, and the wire protocol written out | `backend/lidar.py` |
| to publish to the control page | `backend/lidar_stream.py` |
| to see a scan on the Jetson's own terminal | `test_lidar.py`, next to this file |
| the plot on the control page | `frontend/src/components/lidar-view.tsx` |
| what the simulator assumes | `fly-gym/robot_config.py`, `fly-gym/core/lidar.py` |
| proof the parser matches the spec | `backend/tests/test_lidar.py` |

## First plug-in

```sh
sudo ./yahboomcar_ws/src/ydlidar_ros2_driver-humble/startup/initenv.sh   # udev rules, once
python3 "test_lidar.py"                                                  # ASCII plot
python3 "test_lidar.py" --bearings                                       # sector table
```

The udev rules give the scanner a stable `/dev/ydlidar` symlink and make it readable
without root. Without them autodetection still finds a CP210x bridge on `/dev/ttyUSB*`,
but the name moves around between reboots.

`/dev/ttyACM*` is **never** autodetected even though one of those vendor rules matches
it, because on FLIH that port is the Pico 2 motor relay. A scanner that genuinely
enumerates there has to be named with `--port`.

Then do the two checks in `test_lidar.py`'s docstring - scale against a tape measure,
heading against something placed in front of the robot. Both constants are documented
guesses until someone does. A scan that is mirrored or rotated draws a completely
plausible room, so nothing catches it except looking.

## Why yahboomcar_ws/ is not what runs

It is Yahboom's ROS 2 Humble workspace, kept as the reference for the hardware and
for the vendor's parameters. It is not on FLIH's path, for two reasons that are both
about this machine rather than about preference:

- **There is no ROS 2 here.** No `/opt/ros`, no `rclpy`, nothing from `ros-humble-*`.
- **The driver would not build anyway.** Its `CMakeLists.txt` marks `ydlidar_sdk`
  REQUIRED. That is a separate C++ SDK, not vendored here and not installed.

The bits that do matter have been read out of it and into `backend/lidar.py`:
`params/TminiPro.yaml` for the baud rate and the intensity framing, and the start-scan
handshake (`0xA5 0x60`, which the packet spec does not mention because the SDK hides
it inside `startScan` - without it the port opens and reads nothing, forever, with no
error).

Its `reversion: true` / `inverted: true` pair implies `ZERO_OFFSET_DEG = 180`, and
that one turned out to be **wrong for FLIH**: the scanner is bolted a quarter turn
round from the car that yaml shipped with, so the measured value is **270**. On this
robot the vendor's ROS driver would draw the map 90 degrees out.

One inconsistency worth knowing about: that yaml asks for `frequency: 10.0`, while
`fly-gym`'s `LidarConfig` defaults to `rate_hz=6.0`. Both are inside the unit's
6-12 Hz range and the driver reports whatever it is actually spinning at, but the
number of points in a turn scales with it - roughly 667 at 6 Hz, 400 at 10 - so a
scan captured for the simulator should be captured at the rate the simulator assumes.

`build/`, `install/` and `log/` are that workspace's April 2024 colcon output against
another machine's paths - 118 MB of it - and are gitignored. `src/` is the part worth
keeping.
