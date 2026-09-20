# Backend and bot services

This directory contains the FLIH bot and hardware-facing backend code. The web
app's route handlers remain under `frontend/src/app/api` as required by Next.js.

See `TELEOP_SETUP.md` for bringing the robot up from scratch.

## OMNI surroundings classification

The `classification` module sends one or more camera images and an optional LiDAR scan to
Huawei OMNI, then returns a structured description of the robot's surroundings.

```powershell
python -m pip install -r backend/classification/requirements.txt
Copy-Item .env.example .env
# Add your private YIBU_API_KEY to .env, then run from the repository root:
python backend/classification/classify_surroundings.py
```

The bundled `images.jpg` is used by default. To fuse a LiDAR scan:

```powershell
python backend/classification/classify_surroundings.py `
  --image path/to/left.jpg --image path/to/right.jpg `
  --lidar backend/classification/lidar_example.json
```

In the live robot path, `server.mjs` samples both camera panes onto the LiDAR
socket. `lidar_stream.py` combines those views with compact front/left/right/back
LiDAR minima and the commanded direction, then calls OMNI in a background worker
at most once every five seconds while the robot is moving. Set
`ROBOT_OMNI_INTERVAL` to change that cadence or pass `--no-omni` to disable it.
The result appears in the next scan payload under `omni`. The direct LiDAR traffic
light remains local and does not wait for cloud latency or depend on network access.

The LiDAR JSON may be an array of distances (evenly distributed around 360
degrees), or an object with a `ranges` array and optional sensor metadata such
as `angle_min`, `angle_increment`, `unit`, and `max_range`.

API call metadata and token counts are appended to the git-ignored
`.data/yibu_api_calls.jsonl` ledger. Prompts, media, responses, and full API keys
are not logged.

## WebSocket drive bridge

`robot_websocket.py` connects the Jetson to the website and forwards live drive
commands to the four-motor board. `motor_board.py` holds the protocol, and
`motor_check.py` is a bench tool for verifying wiring before anything drives.

The board is wired for **I2C at `0x26`**, not the UART in the vendor's `USART.py`
sample. Frames reach it either through the Pico 2 relay over USB (`ROBOT_TRANSPORT=serial`,
the path FLIH has driven on) or from the Jetson's own I2C controller
(`ROBOT_TRANSPORT=i2c`, written but never run against hardware). Only the Pico path
has a hardware dead-man.

```sh
python -m pip install -r backend/requirements.txt
export ROBOT_WS_URL=wss://your-flih-host.example/ws/robot
export ROBOT_API_KEY='the-same-long-secret-as-the-server'
export ROBOT_SERIAL_PORT=/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_<serial>-if00
python backend/robot_websocket.py
```

> **Do not set `ROBOT_MOTOR_SIGNS` or `ROBOT_MOTOR_SIDES` by hand.** The confirmed
> values are the defaults in `motor_board.py`, pinned by
> `backend/tests/test_drive_mixing.py` and documented in `hardware/MOTOR_MAP.md`.
> Exporting them from a stale snippet is how forward and reverse got inverted twice:
> the signs and the sides travel together, and flipping both negates forward while
> leaving the turns *exactly* correct, so driving A and D cannot reveal it.


Use the `by-id` path rather than `/dev/ttyACM0`: the ACM index moves when the Pico
re-enumerates, and the bridge does not survive its port disappearing.

Use `ws://127.0.0.1:3000/ws/robot` locally. The protocol sends JSON drive states
with `forward` and `turn`, each `-1`, `0`, or `1`; positive `turn` swings right. The robot authenticates with an
`Authorization: Bearer` header; the server never sends `ROBOT_API_KEY` to browsers.
The bridge stops the motors when the socket closes, errors, receives invalid input,
or gets a stop command, and releases them on exit. It also runs its own watchdog: no
drive frame for `ROBOT_COMMAND_TIMEOUT` seconds and the motors are stopped, re-asserted
until a write succeeds. That is the layer that still fires when a socket stalls open
without ever closing, which nothing on the server side can detect.

Diagonals are mixed rather than clamped. Turning at full authority while driving
forward cancels the inside wheels to exactly zero, which reads as two motors stalling;
`ROBOT_TURN_RATIO` scales the turn so both sides keep driving and the robot arcs.

## Tests

```sh
python -m unittest discover -s backend/tests -p 'test_*.py' -v
```

`test_drive_mixing.py` pins the four teleop motions to the wheel commands confirmed on
the robot. It is hermetic against `ROBOT_*` in your shell on purpose, because a stale
export is one of the ways the drive map goes wrong.

`test_lidar.py` builds T-mini packets from the YDLidar-SDK definitions and checks the
parser reads back what went in. None of it touches a serial port, so it runs anywhere
- and it can only catch a transcription mistake, not a wrong source. See "Two numbers
to confirm against the hardware" below.

## Camera stream

`camera_stream.py` publishes both CSI cameras to the web app as JPEG frames over a
WebSocket, and `csi_camera.py` holds the capture itself. The control page draws them
above the drive controls.

```sh
export ROBOT_API_KEY='the-same-long-secret-as-the-server'
export ROBOT_CAMERA_WS_URL=ws://127.0.0.1:3000/ws/camera
python3 backend/camera_stream.py
```

`ROBOT_CAMERA_WS_URL` is optional: with only `ROBOT_WS_URL` set, the camera endpoint
is derived from it by swapping `/ws/robot` for `/ws/camera`.

**Run it as its own process, not inside the drive bridge.** Video is bulk traffic and
driving is latency-critical; a video frame queued ahead of a drive command on one TCP
connection delays that command by however long the frame takes to flush, and the drive
path has three dead-man timers that read a late frame as a fault. Separate processes
also mean a wedged camera cannot take the motors down with it.

| Flag | Default | Meaning |
| ---- | ------- | ------- |
| `--sensors` | `1 0` | CSI sensor ids, in the order the browser lays them out left to right |
| `--width` / `--height` | `640` / `360` | Size sent to the browser |
| `--fps` | `15` | Frames per second **per camera** |
| `--quality` | `70` | JPEG quality, 1-100 |
| `--capture-width` / `--capture-height` | `1640` / `1232` | Sensor mode requested from Argus |
| `--capture-fps` | `30` | Sensor mode framerate; the full-array mode tops out at 30 |
| `--no-rectify` | off | Publish the raw lens view instead of the sim's camera model |
| `--flip-method` | `0` | `nvvidconv` flip; `2` is 180 degrees |

The defaults cost about **5.2 Mbps for both cameras** (measured: 23 KB and 19 KB per
frame at 15 fps), which is comfortable on a LAN. Raising `--width` to 1280 roughly
triples that.

**`--sensors` defaults to `1 0`, and that is not a typo.** FLIH's harness has CSI port
0 on the right of the chassis and port 1 on the left, while the leading byte of each
frame is a *view position* - 0 is the left pane, 1 the right. Publishing the ports in
numeric order therefore shows each camera in the other one's pane. That is invisible
on a desk, where both cameras see much the same room, and only reads as wrong once
the robot turns toward something the operator recognises; `backend/tests/test_camera_panes.py`
pins it. Re-plug the ribbon cables and this is the default to change - not a flag in
whatever terminal happens to be running the publisher.

Frames go out as `[1 byte pane index][JPEG]`. The server relays them without
decoding, capping any single frame at 512 KB and dropping frames for any viewer with
more than 1 MB unflushed, so a slow browser falls behind in time rather than in
memory. Only the newest frame per camera is ever sent: if a sensor is slower than
`--fps`, the tick is skipped rather than resending a duplicate.

Both cameras need a device-tree overlay enabled before anything opens them. See
`TELEOP_SETUP.md`.

## Matching the simulator's camera

fly-gym renders each eye as an ideal pinhole: **42.61 deg vertical over a 16:9 frame**
(69.47 deg horizontal), square pixels, principal point dead centre, no distortion. A
policy trained there has never seen anything else, so `camera_geometry.py` reprojects
every published frame onto that exact model before it leaves the robot. Straight lines
come out straight, a given pixel names the same ray it would name in the sim, and the
frame is resampled through the same `INTER_AREA` steps fly-gym uses.

Three consequences worth knowing before touching any of it.

**The capture mode is 1640x1232 because of the sim, not the sensor.** The sim wants
42.61 deg vertically and every 16:9 IMX219 mode is a vertical crop of the array that
falls short of it - about 37.6 deg at 3264x1848, less again at 1280x720. Only the
full-array modes contain the sim's vertical field of view, so only they can be
rectified onto it. The cost is frame rate: 60 fps exists only at 1280x720, and this
mode tops out at 30. The link publishes at 15, so nothing downstream notices.

**The horizontal does not fit, and cannot be made to.** The stock IMX219-77 lens
reaches about 62.2 deg horizontally; the sim wants 69.47. Rectification crops angle,
it never adds it, so **the outer 6.5% of each side of the published frame is black -
3.6 deg per side with no sensor behind it.** That is the real sim-to-real gap in the
vision path and no amount of configuration closes it; it takes a wider lens. Until
then the policy sees black where the sim always had scene. `python3
backend/camera_geometry.py` prints the current numbers.

**It is nominal until calibrated.** With no calibration on disk the module falls back
to the IMX219 spec sheet, which models zero lens distortion - the one thing a real
lens is guaranteed to have. `calibrate_cameras.py` fixes that; see
`calibration/README.md`. The publisher says which mode it is in at startup.

Rectification costs about **12 ms per frame** at the published size (measured on the
Orin Nano this repo runs on, despite the `hardware/Jetson NANO/` folder name), so both
cameras at 15 fps are roughly a third of one core. `--no-rectify` publishes the raw
lens view instead, which is the wider picture and the better one for an operator who
just wants to see the room - but it is not the picture the sim describes.

`backend/tests/test_camera_geometry.py` pins all of it, including a check that the
constants copied out of fly-gym still match fly-gym.

## LiDAR scan

`lidar_stream.py` publishes the YDLIDAR T-mini Plus to the web app as one JSON scan
per revolution, and `lidar.py` holds the driver. The control page draws it top-down
below the camera panes.

```sh
export ROBOT_API_KEY='the-same-long-secret-as-the-server'
export ROBOT_LIDAR_WS_URL=ws://127.0.0.1:3000/ws/lidar
python3 backend/lidar_stream.py
```

`ROBOT_LIDAR_WS_URL` is optional, the same way `ROBOT_CAMERA_WS_URL` is: with only
`ROBOT_WS_URL` set, the endpoint is derived by swapping `/ws/robot` for `/ws/lidar`.
Its own process for the same reason the camera has one.

| Flag | Default | Meaning |
| ---- | ------- | ------- |
| `--port` | autodetect | Serial port; `/dev/ydlidar` first, then a CP210x-looking USB port |
| `--baudrate` | `230400` | From the vendor's `params/TminiPro.yaml` |
| `--no-intensity` | off | Unit reconfigured to 2-byte samples with no intensity |
| `--zero-offset-deg` | `270` | Where the scanner's zero mark sits, CCW from forward |
| `--max-range` | `12.0` | Outermost range ring the control page offers |
| `--max-hz` | `10` | Upper bound on publish rate |
| `--demo` | off | Synthesise a room instead of opening the port |
| `--led-driver` | none | Optional LED adapter as `module:factory`; see below |
| `--omni-interval` | `5` | Minimum seconds between live multimodal OMNI calls |
| `--no-omni` | off | Disable live OMNI fusion even when `YIBU_API_KEY` is set |
| `--fly-checkpoint` | iteration 10 | Checkpoint used for fly-policy advice |
| `--no-fly-policy` | off | Disable the experimental fly advisor |

### Omnidirectional safety LED

The nearest valid LiDAR return in the full 360-degree scan drives the signal,
regardless of the commanded direction or whether the robot is stopped. The signal
is **red at 20 cm or closer**, **yellow above 20 cm and below 50 cm**, and **green
at 50 cm or farther**. Motion before the first scan is red as a fail-safe. The
current result is also included in scan JSON as `safetySignal`, `safetyDirection`,
and `safetyClearance`, so it can be checked before hardware is attached and the
control page can show the nearest-object distance.

There is deliberately no GPIO dependency yet. `safety_signal.py` uses a no-hardware
output by default. Once the LED and pins are chosen, add a small adapter with
`set_signal(signal)` and optional `close()` methods, then start the stream with:

```sh
export ROBOT_LED_DRIVER=my_led_driver:create_output
python3 backend/lidar_stream.py
```

The adapter receives a `SafetySignal` whose `.value` is `"red"`, `"yellow"`, or
`"green"`; none of the LiDAR logic needs to change.

### Fly connectome advisor

The iteration-10 connectome policy is also part of the live perception stack. Its
checkpoint metadata matches the robot's two camera positions, T-mini LiDAR frame,
and 12-sector preprocessing. While an operator commands forward or reverse,
`lidar_stream.py` gives that direction to the policy as a temporary goal bearing
and feeds it both camera panes plus the current LiDAR turn. The newest suggestion is
published as `flyAdvice` with `motion`, `turn`, `velocity`, and `headingDeg`.

This is intentionally **advisory only**: it does not write the motors and cannot
override the deterministic LED thresholds. Model loading and inference run in a
daemon worker so they cannot stall LiDAR publication. The default checkpoint is
`fly-gym/checkpoints/connectome_rnn_dagger_iter_10.pt`; override it with
`ROBOT_FLY_CHECKPOINT` or disable it with `--no-fly-policy`. The Jetson environment
needs the PyTorch/OpenCV dependencies from `fly-gym/requirements.txt` for inference;
if they are absent or the checkpoint contract fails validation, the advisor reports
an error and disables itself while LiDAR and the LED continue normally.

A 667-point turn is about **8.9 KB**, so 6 Hz costs roughly 0.4 Mbps - under a tenth
of what the two cameras cost. Scans go out as JSON text and the server relays them
without parsing, capping a message at 64 KB and dropping scans for any viewer more
than 256 KB behind.

### It does not go through ROS

`hardware/Jetson NANO/lidar/yahboomcar_ws/` is the vendor's ROS 2 workspace and is
kept for reference, but it is not what runs, and on this machine it could not: there
is no ROS 2 installed (no `/opt/ros`, no `rclpy`, nothing from `ros-humble-*`), and
the driver's `CMakeLists.txt` marks `ydlidar_sdk` REQUIRED, which is a separate C++
package that is not installed either. `lidar.py` speaks the serial protocol directly
in about 200 lines and has no dependency the backend did not already have.

If ROS 2 does turn up later, the scan structure is field-for-field a
`sensor_msgs/LaserScan`, so the swap is a different source feeding the same
`publish()`. `fly-gym/core/lidar.py` already anticipates both: it takes
`clockwise=True` for raw T-mini packets and the default for converted ROS scans.

### The two numbers that needed real hardware

Everything in `lidar.py` about the protocol comes from YDLidar-SDK's own source, and
`tests/test_lidar.py` checks the parser against packets built from those definitions.
That catches a transcription mistake but not a mistake in the source, so two numbers
had to be confirmed against a scanner. Both now have been, on a T-mini Plus on
`/dev/ttyUSB0`:

1. **Scale — confirmed.** Ranges are `value / 4000` metres, because the T-mini is a
   triangulation part and `CYdLidar.cpp` picks quarter-millimetres for those; the TOF
   parts use `/1000`. Hand-decoding a packet gave a run of adjacent samples at
   ~2.37 m off a wall, with 0.527 degrees between them - which is 4000 samples/s at
   6 Hz, so the angular step corroborates the radial one.
2. **Heading — measured, and it was not the vendor's value.** `ZERO_OFFSET_DEG` is
   **270**, read off the live plot against a known room. The vendor yaml's
   `reversion` + `inverted` pair implies 180; FLIH's scanner is bolted a quarter turn
   round from that, and at 180 the map came out rotated 90 degrees clockwise. It
   looked like a perfectly ordinary room the whole time, which is exactly why this
   one cannot be settled from a datasheet.

Re-seat the scanner and `ZERO_OFFSET_DEG` is the one number to change - add 90 for
each quarter turn the map needs to rotate counterclockwise. The bench tool for it is
`hardware/Jetson NANO/lidar/test_lidar.py --bearings`: something narrow a metre in
front of the robot belongs in the `+0.0 deg` row.

Note that at 270 this driver and the vendor's ROS driver would disagree by 90 degrees
on this robot. The driver is right about FLIH; the yaml is right about the car it
shipped with.

## Checking the wiring first

Prop the chassis up so all four wheels are off the ground and run:

```sh
python backend/motor_check.py
```

It configures the board, reports pack voltage, then drives each motor on its own
followed by the four teleop motions, printing what each step should look like.

The harness map and how to re-derive it live in `hardware/MOTOR_MAP.md`. Read that
before changing either variable - the short version is that FLIH's chassis does not
follow the manual's numbering *and* the end labelled "front" is not the end it drives
toward, so the confirmed values are `ROBOT_MOTOR_SIGNS=1,-1,-1,1` with
`ROBOT_MOTOR_SIDES=L,R,L,R`, and they are already the defaults.

## Motor profile

The board stores its motor settings in flash, but the **factory reduction ratio is
30 while FLIH's L-type 520 motors are 40:1**, so closed-loop speed runs a quarter
low until the profile is pushed. Both scripts send it on startup. The defaults below
mirror `fly-gym/robot_config.py` and `wheel_positions.pdf`; change them only if the
hardware changes.

| Variable                   | Default | Meaning                                              |
| -------------------------- | ------- | ---------------------------------------------------- |
| `ROBOT_TRANSPORT`          | `serial` | `serial`: frames to the Pico relay. `i2c`: Jetson straight to the board |
| `ROBOT_SERIAL_PORT`        | `/dev/ttyACM0` | The Pico, on the `serial` transport. Prefer the `by-id` path |
| `ROBOT_I2C_BUS`            | `7`     | On the `i2c` transport. Orin 40-pin pins 3/5; bus 1 is pins 27/28 |
| `ROBOT_I2C_ADDRESS`        | `0x26`  | Board address on the `i2c` transport                 |
| `ROBOT_MOTOR_SIDES`        | `L,R,L,R` | Which side each of M1-M4 drives. **Confirmed; see `hardware/MOTOR_MAP.md`** |
| `ROBOT_DRIVE_SPEED`        | `500`   | Forward/reverse speed in mm/s (max 1000)             |
| `ROBOT_TURN_SPEED`         | drive speed | Spin-in-place speed in mm/s                      |
| `ROBOT_TURN_RATIO`         | `0.5`   | Turn authority while also driving; `1.0` stalls the inside wheels |
| `ROBOT_MIN_SPEED`          | `120`   | Floor for a non-zero wheel speed, so mixing cannot command a stall |
| `ROBOT_COMMAND_TIMEOUT`    | `1.0`   | Seconds of silence before the bridge stops the motors |
| `ROBOT_MOTOR_SIGNS`        | `1,-1,-1,1` | Per-motor polarity for M1–M4. **Confirmed; travels with `ROBOT_MOTOR_SIDES`** |
| `ROBOT_MOTOR_TYPE`         | `1`     | 1: 520, 2: 310, 3: TT with encoder, 4: TT without    |
| `ROBOT_REDUCTION_RATIO`    | `40`    | Gearbox ratio; **wrong by default on the board**     |
| `ROBOT_ENCODER_LINES`      | `11`    | Hall encoder lines per turn                          |
| `ROBOT_WHEEL_DIAMETER_MM`  | `67.5`  | Wheel diameter, scales the speed units               |
| `ROBOT_DEADZONE`           | `1600`  | PWM dead zone, 0–3600                                |
| `ROBOT_CONFIGURE_BOARD`    | `1`     | Set `0` to skip the profile push on startup          |

Motor type 4 has no encoder, so there is no closed loop to command: setting
`ROBOT_MOTOR_TYPE=4` switches both scripts to open-loop `$pwm` and raises the speed
ceiling to 3600. Raise the wheels for the first test either way.
