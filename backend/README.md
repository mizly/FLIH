# Backend and bot services

This directory is reserved for the FLIH bot and hardware-facing backend code.

The web app currently exposes its HTTP API through `frontend/src/app/api/flih/route.ts`, because Next.js route handlers must live inside the frontend app's `app` directory. The robot service can be added here and send telemetry to that API using `ROBOT_API_KEY`.

See `TELEOP_SETUP.md` for bringing the robot up from scratch.

## WebSocket drive bridge

`robot_websocket.py` connects the Jetson to the website and forwards live drive
commands to the four-motor board. `motor_board.py` holds the serial protocol, and
`motor_check.py` is a bench tool for verifying wiring before anything drives.

```sh
python -m pip install -r backend/requirements.txt
export ROBOT_WS_URL=wss://your-flih-host.example/ws/robot
export ROBOT_API_KEY='the-same-long-secret-as-the-server'
export ROBOT_SERIAL_PORT=/dev/ttyUSB0
python backend/robot_websocket.py
```

Use `ws://127.0.0.1:3000/ws/robot` locally. The protocol sends JSON drive states
with `forward` and `turn`, each `-1`, `0`, or `1`. The robot authenticates with an
`Authorization: Bearer` header; the server never sends `ROBOT_API_KEY` to browsers.
The bridge stops the motors when the socket closes, errors, receives invalid input,
or gets a stop command, and releases them on exit.

## Checking the wiring first

Prop the chassis up so all four wheels are off the ground and run:

```sh
python backend/motor_check.py
```

It configures the board, reports pack voltage, then drives each motor on its own
followed by the four teleop motions, printing what each step should look like. Any
wheel that turns the wrong way gets its slot in `ROBOT_MOTOR_SIGNS` flipped to `-1`.
Motors are numbered as the module manual numbers them:

| Motor | Wheel       |
| ----- | ----------- |
| M1    | front left  |
| M2    | rear left   |
| M3    | front right |
| M4    | rear right  |

## Motor profile

The board stores its motor settings in flash, but the **factory reduction ratio is
30 while FLIH's L-type 520 motors are 40:1**, so closed-loop speed runs a quarter
low until the profile is pushed. Both scripts send it on startup. The defaults below
mirror `fly-gym/robot_config.py` and `wheel_positions.pdf`; change them only if the
hardware changes.

| Variable                   | Default | Meaning                                              |
| -------------------------- | ------- | ---------------------------------------------------- |
| `ROBOT_SERIAL_PORT`        | `/dev/ttyUSB0` | Board directly, or `/dev/ttyACM0` via the Pico |
| `ROBOT_DRIVE_SPEED`        | `250`   | Forward/reverse speed in mm/s (max 1000)             |
| `ROBOT_TURN_SPEED`         | drive speed | Spin-in-place speed in mm/s                      |
| `ROBOT_MOTOR_SIGNS`        | `1,1,1,1` | Per-motor polarity for M1–M4                       |
| `ROBOT_MOTOR_TYPE`         | `1`     | 1: 520, 2: 310, 3: TT with encoder, 4: TT without    |
| `ROBOT_REDUCTION_RATIO`    | `40`    | Gearbox ratio; **wrong by default on the board**     |
| `ROBOT_ENCODER_LINES`      | `11`    | Hall encoder lines per turn                          |
| `ROBOT_WHEEL_DIAMETER_MM`  | `67.5`  | Wheel diameter, scales the speed units               |
| `ROBOT_DEADZONE`           | `1600`  | PWM dead zone, 0–3600                                |
| `ROBOT_CONFIGURE_BOARD`    | `1`     | Set `0` to skip the profile push on startup          |

Motor type 4 has no encoder, so there is no closed loop to command: setting
`ROBOT_MOTOR_TYPE=4` switches both scripts to open-loop `$pwm` and raises the speed
ceiling to 3600. Raise the wheels for the first test either way.
