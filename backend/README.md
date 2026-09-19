# Backend and bot services

This directory is reserved for the FLIH bot and hardware-facing backend code.

The web app currently exposes its HTTP API through `frontend/src/app/api/flih/route.ts`, because Next.js route handlers must live inside the frontend app's `app` directory. The robot service can be added here and send telemetry to that API using `ROBOT_API_KEY`.

## WebSocket drive bridge

`robot_websocket.py` connects the Jetson to the website and forwards live drive commands to the four-motor UART board:

```sh
python -m pip install -r backend/requirements.txt
export ROBOT_WS_URL=wss://your-flih-host.example/ws/robot
export ROBOT_API_KEY='the-same-long-secret-as-the-server'
export ROBOT_SERIAL_PORT=/dev/ttyUSB0
export ROBOT_DRIVE_SPEED=250
export ROBOT_MOTOR_SIGNS=1,1,1,1
python backend/robot_websocket.py
```

Use `ws://127.0.0.1:3000/ws/robot` locally. `ROBOT_MOTOR_SIGNS` controls motor 1 through 4 polarity. Raise the wheels for the first test and change individual values to `-1` if a motor is reversed.

The protocol sends JSON drive states with `forward` and `turn`, each `-1`, `0`, or `1`. The robot authenticates with an `Authorization: Bearer` header; the server never sends `ROBOT_API_KEY` to browsers. The bridge stops all motors when the socket closes, errors, receives invalid input, or gets a stop command.
