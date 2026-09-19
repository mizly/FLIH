# Teleop bring-up

How to get WASD driving working on the real robot, end to end. Read
`backend/README.md` for the env vars and the serial protocol itself.

> **Status:** the Jetson-side code in `backend/` has been tested against the web
> stack with a pty standing in for the motor board, which proves the frame format
> and the WebSocket path only. **No part of it has driven real motors yet.** Step 3
> below is the first time it touches hardware.

## What runs where

| File | Runs on | Role |
| ---- | ------- | ---- |
| `backend/motor_board.py` | Jetson (CPython + pyserial) | The serial protocol: profile push, drive mixing, stop/release |
| `backend/robot_websocket.py` | Jetson | Holds the authenticated socket to `/ws/robot`, turns drive frames into motor commands |
| `backend/motor_check.py` | Jetson | Bench tool: drives each motor on its own to verify wiring |
| `hardware/PICO2/remote_control.py` | Pico 2 (MicroPython) | Dumb relay: USB stdin to the board's UART, and board replies back |

**The Jetson is the brain.** The Pico cannot hold the WebSocket, because it has no
radio. `motor_board.py` only writes `$cmd:args#` ASCII to a serial port and does not
care what is on the other end, so the transport is chosen entirely by
`ROBOT_SERIAL_PORT`.

## Choosing a transport

| | Path | Needs | Watchdog |
| --- | ---- | ----- | -------- |
| A | Jetson to USB-TTL adapter to board | A USB-TTL adapter | none |
| B | Jetson to USB to **Pico** to board | Just a USB cable | **500 ms, on the Pico** |
| C | Jetson 40-pin UART (`/dev/ttyTHS1`) to board | Rewiring, 3.3 V level check | none |

**Path B is the recommended one.** The Pico's UART0 pin assignment in
`remote_control.py` is identical to the vendor tutorial in
`hardware/PICO2/USART/USART.py`:

```python
uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
```

so any Pico-to-board wiring already proven with the tutorial works unchanged. It is
also the only path with a hardware dead-man, which matters because the bridge has no
watchdog of its own: on a silent network stall the server's stop command never
arrives, and `websocket-client`'s `ping_timeout=5` means up to five seconds before
the bridge notices. The Pico caps that at 500 ms.

Path C is available if you later want to drop the Pico: `/dev/ttyTHS1` exists on the
40-pin header and `nvgetty` is not running, so nothing is holding that UART.

## Steps

### 0. Jetson permissions

Serial devices are `root:dialout crw-rw----`, and the `jetson` user is not in that
group, so opening the port fails with permission denied until:

```sh
sudo usermod -aG dialout jetson
```

Log out and back in, then confirm with `id | grep dialout`.

### 1. Flash the Pico

In Thonny, open `hardware/PICO2/remote_control.py` and save it **to the Pico as
`main.py`** so it runs on power-up.

Do not try to test it from Thonny first: it reads from stdin, which is the same USB
channel Thonny talks over, so it will look hung. Flashing it blind is safe, because
it never calls `micropython.kbd_intr(-1)` and so Thonny's Stop button can always
interrupt it and return the REPL.

### 2. Move the Pico to the Jetson

Plug it into the Jetson by USB and confirm it enumerates:

```sh
ls -l /dev/ttyACM*
```

### 3. Bench test, wheels off the ground

```sh
cd ~/FLIH
ROBOT_SERIAL_PORT=/dev/ttyACM0 python3 backend/motor_check.py
```

This drives M1 to M4 one at a time, then forward, reverse and both spins, printing
what each step should look like. Flip any backwards wheel's slot in
`ROBOT_MOTOR_SIGNS` to `-1` and rerun until every step matches.

Watch the configuration output as well. With the Pico in the path the board's
`command+OK` replies should come back instead of `no reply`, which is the first live
confirmation that the relay works in both directions.

### 4. Start the web stack

There is no `.env` in a fresh checkout:

```sh
printf 'ROBOT_API_KEY=%s\n' "$(openssl rand -hex 32)" > ~/FLIH/.env
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
export ROBOT_SERIAL_PORT=/dev/ttyACM0
python3 backend/robot_websocket.py
```

### 5. Drive it

Open `http://<jetson-ip>:3000/control`. The status line should read "Robot connected
— controls are live." Keep the wheels up for the first drive.

Only one browser can drive at a time. Releasing the keys, leaving the tab,
disconnecting, or 350 ms without a command all stop the robot.

## Known gaps

- **The relay's board replies depend on `sys.stdout.buffer`.** `read_board` writes
  raw bytes and drops anything that raises, so a MicroPython build without a binary
  stdout degrades to silence rather than failing. If step 3 still prints `no reply`
  for every config write with the Pico in the path, suspect that before the wiring.
- **The bridge has no watchdog of its own**, as described under transports above.
  Path B covers it; paths A and C do not.
- **`$read_vol#` battery parsing is unexercised.** The command comes from section 12
  of the module manual rather than the vendor tutorial code, so its reply format has
  never been seen here.
- **The vendor tutorial sleeps 10 ms after every serial write**; `motor_board.py`
  uses `flush()` instead. If frames get dropped on real hardware, suspect this first.
- **Robot telemetry is not wired up.** `PATCH /api/flih` wants floor coordinates,
  which needs localization, so the map still shows the simulated demo position.
