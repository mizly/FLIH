"""Authenticated FLIH WebSocket-to-UART bridge for the Jetson."""

import json
import os
import signal
import sys
import time

import serial
import websocket


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


WS_URL = required("ROBOT_WS_URL")
API_KEY = required("ROBOT_API_KEY")
SERIAL_PORT = os.environ.get("ROBOT_SERIAL_PORT", "/dev/ttyUSB0")
DRIVE_SPEED = max(0, min(1000, int(os.environ.get("ROBOT_DRIVE_SPEED", "250"))))

try:
    MOTOR_SIGNS = tuple(int(value) for value in os.environ.get("ROBOT_MOTOR_SIGNS", "1,1,1,1").split(","))
except ValueError as error:
    raise RuntimeError("ROBOT_MOTOR_SIGNS must contain four comma-separated 1 or -1 values") from error
if len(MOTOR_SIGNS) != 4 or any(value not in (-1, 1) for value in MOTOR_SIGNS):
    raise RuntimeError("ROBOT_MOTOR_SIGNS must contain four comma-separated 1 or -1 values")

motor = serial.Serial(SERIAL_PORT, 115200, timeout=1)
running = True


def write_speeds(speeds: tuple[int, int, int, int]) -> None:
    signed = [speed * sign for speed, sign in zip(speeds, MOTOR_SIGNS)]
    motor.write(f"$spd:{signed[0]},{signed[1]},{signed[2]},{signed[3]}#".encode("ascii"))
    motor.flush()


def stop() -> None:
    write_speeds((0, 0, 0, 0))


def apply_drive(forward: int, turn: int) -> None:
    left = max(-1, min(1, forward + turn))
    right = max(-1, min(1, forward - turn))
    write_speeds((left * DRIVE_SPEED, left * DRIVE_SPEED, right * DRIVE_SPEED, right * DRIVE_SPEED))


def on_message(socket: websocket.WebSocketApp, raw: str) -> None:
    try:
        message = json.loads(raw)
        if message.get("type") != "drive":
            return
        forward = message.get("forward")
        turn = message.get("turn")
        if forward not in (-1, 0, 1) or turn not in (-1, 0, 1):
            stop()
            return
        apply_drive(forward, turn)
        socket.send(json.dumps({"type": "ack", "sequence": message.get("sequence")}))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        stop()
        print(f"Rejected drive command: {error}", file=sys.stderr)


def on_open(_socket: websocket.WebSocketApp) -> None:
    stop()
    print("Connected to the FLIH control server")


def on_close(_socket: websocket.WebSocketApp, code: int, reason: str) -> None:
    stop()
    print(f"Control connection closed ({code}): {reason}", file=sys.stderr)


def on_error(_socket: websocket.WebSocketApp, error: object) -> None:
    stop()
    print(f"Control connection error: {error}", file=sys.stderr)


def shutdown(_signal: int, _frame: object) -> None:
    global running
    running = False
    stop()


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

try:
    while running:
        client = websocket.WebSocketApp(
            WS_URL,
            header=[f"Authorization: Bearer {API_KEY}"],
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )
        client.run_forever(ping_interval=15, ping_timeout=5)
        if running:
            time.sleep(2)
finally:
    stop()
    motor.close()
