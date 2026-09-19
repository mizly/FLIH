"""Authenticated FLIH WebSocket-to-UART bridge for the Jetson.

Holds the authenticated socket to the web app's /ws/robot endpoint and turns each
drive frame into motor board commands. The serial protocol itself lives in
motor_board.py.
"""

import json
import os
import signal
import sys
import time

import websocket

from motor_board import MotorBoard


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


WS_URL = required("ROBOT_WS_URL")
API_KEY = required("ROBOT_API_KEY")
CONFIGURE_BOARD = os.environ.get("ROBOT_CONFIGURE_BOARD", "1") != "0"

board = MotorBoard()
running = True
client = None


def on_message(socket: websocket.WebSocketApp, raw: str) -> None:
    try:
        message = json.loads(raw)
        if message.get("type") != "drive":
            return
        forward = message.get("forward")
        turn = message.get("turn")
        if forward not in (-1, 0, 1) or turn not in (-1, 0, 1):
            board.stop()
            return
        board.drive(forward, turn)
        socket.send(json.dumps({"type": "ack", "sequence": message.get("sequence")}))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        board.stop()
        print(f"Rejected drive command: {error}", file=sys.stderr)


def on_open(_socket: websocket.WebSocketApp) -> None:
    board.stop()
    print("Connected to the FLIH control server")


def on_close(_socket: websocket.WebSocketApp, code: int, reason: str) -> None:
    board.stop()
    print(f"Control connection closed ({code}): {reason}", file=sys.stderr)


def on_error(_socket: websocket.WebSocketApp, error: object) -> None:
    board.stop()
    print(f"Control connection error: {error}", file=sys.stderr)


def shutdown(_signal: int, _frame: object) -> None:
    global running
    running = False
    board.stop()
    if client:  # run_forever blocks until the socket itself is closed.
        client.close()


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

try:
    board.release()
    if CONFIGURE_BOARD:
        board.configure()
    board.stop()

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
    board.close()
