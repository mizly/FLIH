# Teleop bring-up

How to get WASD driving working on the real robot, end to end. Read
`backend/README.md` for the env vars and the register map itself.

> **Status:** driving has been confirmed on real hardware over the Pico path: the
> browser's keys reached the motor board and turned the wheels. Two things are
> written but **not** confirmed against hardware, and both are called out where they
> appear below: the corrected left/right side map, and the Jetson-direct I2C
> transport.

## What runs where

| File | Runs on | Role |
| ---- | ------- | ---- |
| `backend/motor_board.py` | Jetson (CPython) | The protocol: transports, profile push, drive mixing, stop/release |
| `backend/robot_websocket.py` | Jetson | Holds the authenticated socket to `/ws/robot`, turns drive frames into motor commands |
| `backend/motor_check.py` | Jetson | Bench tool: drives each motor on its own to verify wiring |
| `hardware/PICO2/remote_control.py` | Pico 2 (MicroPython) | Translates `$cmd:args#` frames into I2C register writes on the board |
| `backend/csi_camera.py` | Jetson | CSI capture behind `nvarguscamerasrc`, newest frame only |
| `backend/camera_stream.py` | Jetson | Publishes both cameras to `/ws/camera` as JPEG over a WebSocket |
| `hardware/Jetson NANO/test_camera_csi_dual.py` | Jetson | Bench tool: both camera feeds in a local window, no network |
| `backend/lidar.py` | Jetson | T-mini Plus capture, straight off the serial port, newest turn only |
| `backend/lidar_stream.py` | Jetson | Publishes one JSON scan per revolution to `/ws/lidar` |
| `hardware/Jetson NANO/lidar/test_lidar.py` | Jetson | Bench tool: the scan as an ASCII plot in the terminal, no network |

**The Jetson is the brain.** The Pico cannot hold the WebSocket, because it has no
radio.

## The board speaks I2C, not UART

This is the single most important correction to make if you are coming from the
vendor tutorial. FLIH's motor board is wired for **I2C at address `0x26`**, not the
UART the tutorial's `USART.py` demonstrates. The symptom of getting this wrong is
distinctive and silent: every config write returns `no reply` and no motor moves,
with no error anywhere.

Confirm which one you are on before debugging anything else. From the Pico's REPL:

```python
from machine import I2C, Pin
I2C(0, sda=Pin(4), scl=Pin(5), freq=100000).scan()   # -> [0x26] when wired for I2C
```

`hardware/PICO2/IIC/IIC.py` is the vendor's I2C sample and the source of the register
map. `hardware/PICO2/USART/USART.py` is the UART sample and does **not** apply here.

## Choosing a transport

| | Path | `ROBOT_TRANSPORT` | Watchdog | State |
| --- | ---- | ----------------- | -------- | ----- |
| A | Jetson to USB to **Pico** to board | `serial` (default) | **500 ms, on the Pico** | Driven wheels |
| B | Jetson 40-pin I2C straight to board | `i2c` | none | Untested |

**Path A is the recommended one**, and the only one that has driven the robot. The
Pico is wired to the board with three wires - **GP4 to SDA, GP5 to SCL, GND to GND** -
and relays frames from USB onto that bus.

It is also the only path with a hardware dead-man, which matters because the bridge
has no watchdog of its own: on a silent network stall the server's stop command never
arrives, and `websocket-client`'s `ping_timeout=5` means up to five seconds before the
bridge notices. The Pico caps that at 500 ms.

Those timeouts are a chain, each the backstop for the layer above it:

| Interval | Where | What it does |
| -------- | ----- | ------------ |
| 100 ms | browser (`robot-control.tsx`) | Resends the drive frame while keys are held |
| 350 ms | server (`server.mjs`) | Drops the controller and sends an explicit stop |
| 500 ms | Pico (`remote_control.py`) | Writes zero speed on its own |

The browser's 100 ms repeat is load-bearing: it is what keeps the two dead-mans fed
while driving. Confirmed on hardware - a sustained 2 s drive sent 13 frames and got
14 acks with no watchdog cut-in.

**Path B drops the Pico** and wires the board's SDA/SCL/GND to the Jetson's 40-pin
header - pin 3, pin 5, pin 6, which is `/dev/i2c-7` on an Orin (**not** bus 1, which
is what the vendor's Jetson sample hardcodes; bus 1 is pins 27/28). The code is
written and its register encoding is unit-tested byte-for-byte, but no byte has ever
reached the board this way.

One trap cost us an evening on this path: **those header pins are plain GPIO until
I2C is enabled for them.** `i2cdetect` finds an empty bus and reports nothing wrong,
so it reads exactly like bad wiring. Enable the pin mux with `sudo /opt/nvidia/jetson-io/jetson-io.py`
and reboot before concluding anything is miswired.

It also gives up the 500 ms dead-man, so a bridge crash mid-drive leaves the wheels
turning until power is cut. Do not reach for this during a demo.

## Steps

### 0. Jetson permissions

Serial devices are `root:dialout crw-rw----`, so the user opening the port has to be
in that group. **On FLIH's Jetson this is already done**; check before changing
anything:

```sh
id | grep dialout
```

If that comes back empty, add the group and log out and back in:

```sh
sudo usermod -aG dialout "$USER"
```

### 1. Flash the Pico

In Thonny, open `hardware/PICO2/remote_control.py` and save it **to the Pico as
`main.py`** so it runs on power-up.

Do not try to test it from Thonny first: it reads from stdin, which is the same USB
channel Thonny talks over, so it will look hung. Flashing it blind is safe, because
it never calls `micropython.kbd_intr(-1)` and so Thonny's Stop button can always
interrupt it and return the REPL.

To confirm it is running rather than sitting at the REPL, send a bare newline down
the port. The REPL echoes a `>>>` prompt; the relay swallows it silently.

### 2. Move the Pico to the Jetson

Plug it into the Jetson by USB and confirm it enumerates:

```sh
ls -l /dev/serial/by-id/
```

**Use the `by-id` path, not `/dev/ttyACM0`.** The ACM index moves whenever the device
re-enumerates, and a bridge pinned to a stale index dies with
`SerialException: [Errno 5] Input/output error`. The stable name is keyed to the
Pico's own serial number:

```
/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_<serial>-if00
```

**Close Thonny before the next step.** It keeps the port open for as long as it is
connected, and the port takes one owner at a time, so `motor_check.py` will fail to
open it. `fuser -v <port>` names whatever is holding it.

> **Use a known-good data USB cable.** A marginal cable enumerates and then drops the
> device under sustained traffic, which presents as the bridge dying mid-session with
> an I/O error and the Pico vanishing from `lsusb` entirely. This has bitten FLIH
> once already and cost an hour.

### 3. Bench test, wheels off the ground

```sh
cd ~/FLIH
export ROBOT_SERIAL_PORT=/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_<serial>-if00
python3 backend/motor_check.py
```

> **Do not export `ROBOT_MOTOR_SIGNS` or `ROBOT_MOTOR_SIDES`.** The confirmed values
> are the defaults in `motor_board.py` and are pinned by
> `backend/tests/test_drive_mixing.py`; `hardware/MOTOR_MAP.md` is the source of truth.
> Pasting them from an old snippet is how forward and reverse got inverted twice.


The configuration output should show `command+OK` for every write. Over I2C a write
either gets an ACK or raises, so this is a real signal: `no reply` for all six means
the relay is not reaching the board at all, and `error:` names the failure.

The first four steps drive M1 to M4 one at a time and check `ROBOT_MOTOR_SIGNS`. The
last four drive through `drive()` itself and check `ROBOT_MOTOR_SIDES`.

**Keep a hand on the battery disconnect for the first run.** `$spd` is closed loop,
so a motor whose encoder is unplugged or miswired reports no movement, the board's PID
integrates the error, and that wheel ramps to full PWM instead of the 250 mm/s asked
for. Wheels up is what makes this safe to discover.

### 3b. Enable the cameras

**The CSI ports are dead until a device-tree overlay is applied**, and the symptom
gives nothing away: `nvarguscamerasrc` reports `No cameras available`, there is no
`/dev/video*` at all, and the camera I2C buses do not exist either, so probing them
looks exactly like a cable problem.

Check first - this is only needed once per flash:

```sh
grep -i overlay /boot/extlinux/extlinux.conf
```

Nothing there means nothing is enabled. FLIH runs two IMX219 modules on an Orin Nano
dev kit, which is header 2, option 1:

```sh
sudo /opt/nvidia/jetson-io/config-by-hardware.py -l
sudo /opt/nvidia/jetson-io/config-by-hardware.py -n 2="Camera IMX219 Dual"
sudo reboot
```

It rewrites `extlinux.conf` and does **not** reboot on its own. Afterwards both
sensors should be present:

```sh
ls /dev/video*                                   # video0 and video1
cat /sys/class/video4linux/video*/name           # imx219 9-0010, imx219 10-0010
```

Check the ribbon cables while the power is off: contacts face **away** from the
latch on the carrier board, blue backing toward it. A reversed cable produces the
same `No cameras available`, which is an entire reboot cycle to discover.

Then confirm the picture locally, before involving the network:

```sh
python3 "hardware/Jetson NANO/test_camera_csi_dual.py"
```

Both IMX219s offer 3280x2464@21 down to 1280x720@60; **60 fps exists only at 720p**.

### 4. Start the web stack

There is no `.env` in a fresh checkout. Write one only if it is missing, so that
rerunning this step never rotates a key the bridge is already using:

```sh
[ -e ~/FLIH/.env ] || printf 'ROBOT_API_KEY=%s\n' "$(openssl rand -hex 32)" > ~/FLIH/.env
```

Terminal 1. `HOSTNAME=0.0.0.0` is required to reach the page from another machine,
because `server.mjs` binds to `127.0.0.1` by default:

```sh
cd ~/FLIH && HOSTNAME=0.0.0.0 npm run dev
```

Terminal 2:

```sh
cd ~/FLIH
export $(grep ROBOT_API_KEY .env)
export ROBOT_WS_URL=ws://127.0.0.1:3000/ws/robot
export ROBOT_SERIAL_PORT=/dev/serial/by-id/usb-MicroPython_Board_in_FS_mode_<serial>-if00
python3 backend/robot_websocket.py
```

Wait for `Connected to the FLIH control server`.

Terminal 3, for the camera feeds. This is deliberately its own process: video is bulk
traffic, driving is latency-critical, and a camera that wedges must not be able to
take the motors with it.

```sh
cd ~/FLIH
export $(grep ROBOT_API_KEY .env)
export ROBOT_CAMERA_WS_URL=ws://127.0.0.1:3000/ws/camera
python3 backend/camera_stream.py
```

Wait for `Camera link up`. It names which port went to which pane:

```
Publishing 2 camera(s) to ... (left pane <- sensor-id 1, right pane <- sensor-id 0)
```

That crossover is correct - CSI port 1 is the left-facing camera. Defaults are
640x360 at 15 fps per camera, about 5.2 Mbps for the pair; `backend/README.md` lists
the flags.

Terminal 4, for the LiDAR. Its own process for the same reason, and optional: nothing
about driving depends on it.

```sh
cd ~/FLIH
export $(grep ROBOT_API_KEY .env)
export ROBOT_LIDAR_WS_URL=ws://127.0.0.1:3000/ws/lidar
python3 backend/lidar_stream.py
```

Wait for `LiDAR link up`. It names the port and the mounting angle it is assuming:

```
Scanner on /dev/ttyUSB0 at 230400 baud, zero mark 270 deg CCW of forward
```

That 270 is measured against FLIH's own mount, not taken from the vendor's yaml,
which implies 180 and puts the map a quarter turn out. **If the scanner is ever
re-seated, re-measure it**: run `hardware/Jetson NANO/lidar/test_lidar.py --bearings`
with something narrow a metre in front of the robot and confirm it lands in the
`+0.0 deg` row. A rotated scan draws a completely plausible room, so nothing catches
it except looking. `--demo` publishes a synthetic one if you want to see the page
working with no scanner wired.

### 5. Drive it

Open `http://<jetson-ip>:3000/control`. The status line should read "Robot connected
- controls are live." Keep the wheels up for the first drive.

The camera panes sit above the controls and are independent of the drive link: they
read "Live from the robot" once frames arrive, and a pane that goes 1.5 s without one
blanks itself rather than leave a stale image an operator could mistake for live
video. The LiDAR plot below them behaves the same way and for the same reason - a
stale scan shows a clear path through obstacles that are still there.

**Check W first, not A and D.** With the wheels still up, press W and confirm every
wheel turns the way the robot is meant to travel. Forward is the only one of the four
motions that can tell a correct drive map from an inverted one; the turns look right
either way. See "Wheel numbering" below.

Only one browser can drive at a time. Releasing the keys, leaving the tab,
disconnecting, or 350 ms without a command all stop the robot.

## Opening the page from another machine

`npm run dev` blocks cross-origin requests to Next's dev assets, trusting only
localhost and the hostname the server was started with - which is `0.0.0.0`, never
the address a browser actually uses. Without the fix the page loads but **never
hydrates**, so the control socket is never opened and the UI sits forever on
"connecting" with nothing in the browser console to explain it. The server log is
where it shows up:

```
⚠ Blocked cross-origin request to Next.js dev resource /_next/hmr from "..."
```

`frontend/next.config.mjs` lists the LAN and Tailscale ranges under
`allowedDevOrigins`, with an `ALLOWED_DEV_ORIGINS=a,b` env override for anything else.
Matching is on hostname alone - no scheme, no port - and `*` matches exactly one
label, which for an IPv4 address is one octet.

**For a demo, run `npm run build && npm run start` instead.** Production mode has no
dev-origin restriction at all, so this whole class of problem disappears, and it is
meaningfully faster on a Jetson.

## Wheel numbering

**`hardware/MOTOR_MAP.md` is the source of truth.** It holds the confirmed harness
table, what each variable does, and how to re-derive both from scratch. The values
there are the defaults in `motor_board.py`, so a correct bring-up sets neither
variable.

```sh
ROBOT_MOTOR_SIGNS=1,-1,-1,1
ROBOT_MOTOR_SIDES=L,R,L,R
```

Two distinct ways to get this wrong, and only one of them is findable by turning:

| Wrong | What you see |
| ----- | ------------ |
| Sides only | Driving straight is perfect, turns are broken |
| Signs **and** sides together | Forward and reverse inverted, **turns exactly correct** |

The second is the one that keeps coming back. Rotation about the centre is identical
whichever end you call the front, so A and D look right no matter which way round the
map is - the only check that catches it is whether **W drives the way the robot
faces**. Confirm that before trusting a bring-up, and do it with the wheels up.

## Known gaps

- **`$read_vol#` battery reads are gone.** The vendor register map has no battery
  register, so pack voltage is unavailable on any I2C path. `battery_volts()` returns
  `None` unless a real UART board is on the other end.
- **`$upload` telemetry is gone**, for the same reason: I2C is polled, not pushed.
  Encoder counts can be read back via registers `0x10`-`0x27` if ever needed.
- **The bridge has no watchdog of its own.** Path A's Pico covers it; path B does not.
- **The bridge does not survive its serial port disappearing.** A re-enumerated or
  unplugged Pico kills it with `[Errno 5]` and it does not retry. The `by-id` path
  removes the common cause; a supervisor would remove the rest.
- **Video is MJPEG, not WebRTC.** Every frame is a whole JPEG, so bandwidth scales
  with resolution far faster than an inter-frame codec would and there is no
  congestion control beyond dropping frames. It is simple, it reuses the existing
  auth, and it is fine on a LAN; it is not what you would send over the open
  internet.
- **The camera stream is unauthenticated on the browser side.** `/ws/video` checks
  the origin, exactly like `/ws/control`, which means anyone who can reach the page
  can watch. That matches the drive channel's model, but driving has a one-controller
  lock and watching does not.
- **Robot telemetry is not wired up.** `PATCH /api/flih` wants floor coordinates,
  which needs localization, so the map still shows the simulated demo position.
