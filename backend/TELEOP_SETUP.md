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
export ROBOT_MOTOR_SIGNS=-1,1,1,-1
python3 backend/motor_check.py
```

The configuration output should show `command+OK` for every write. Over I2C a write
either gets an ACK or raises, so this is a real signal: `no reply` for all six means
the relay is not reaching the board at all, and `error:` names the failure.

The first four steps drive M1 to M4 one at a time and check `ROBOT_MOTOR_SIGNS`. The
last four drive through `drive()` itself and check `ROBOT_MOTOR_SIDES`.

**Keep a hand on the battery disconnect for the first run.** `$spd` is closed loop,
so a motor whose encoder is unplugged or miswired reports no movement, the board's PID
integrates the error, and that wheel ramps to full PWM instead of the 250 mm/s asked
for. Wheels up is what makes this safe to discover.

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
export ROBOT_MOTOR_SIGNS=-1,1,1,-1
python3 backend/robot_websocket.py
```

Wait for `Connected to the FLIH control server`.

### 5. Drive it

Open `http://<jetson-ip>:3000/control`. The status line should read "Robot connected
- controls are live." Keep the wheels up for the first drive.

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

The module manual numbers the outputs M1 front left, M2 rear left, M3 front right,
M4 rear right. **FLIH's harness does not match:**

| Output | Wheel |
| ------ | ----- |
| M1 | rear right |
| M2 | rear left |
| M3 | front right |
| M4 | front left |

So the right side is M1 and M3, the left side is M2 and M4, which is what
`ROBOT_MOTOR_SIDES=R,L,R,L` encodes. A wrong side map is **invisible when driving
straight** - every motor gets the same value - and shows up only as a broken turn.
That is exactly how it was found.

`ROBOT_MOTOR_SIGNS=-1,1,1,-1` flips M1 and M4, which are mounted mirrored.

> **Unverified:** the side map was corrected after observing the bad turn, but the
> fix has not yet been driven. Step 3's last four steps are the check - confirm A
> rotates the cart left and D rotates it right before trusting it.

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
- **Robot telemetry is not wired up.** `PATCH /api/flih` wants floor coordinates,
  which needs localization, so the map still shows the simulated demo position.
