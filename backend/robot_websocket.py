"""Authenticated FLIH WebSocket-to-UART bridge for the Jetson.

Holds the authenticated socket to the web app's /ws/robot endpoint and turns each
drive frame into motor board commands. The serial protocol itself lives in
motor_board.py.
"""

import json
import os
import signal
import sys
import threading
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

# Stop if no drive frame arrives for this long. The browser repeats every 100 ms while
# a key is held, so anything above ~0.3 s cannot fire during normal driving; the gap
# between that and this timeout is the robot coasting on its last command, so keep it
# short. This is the Jetson's own dead-man, independent of the server's 350 ms
# controller drop and the relay's 500 ms watchdog - it is the one that still fires when
# the socket stalls open without closing, which no amount of server-side logic catches.
COMMAND_TIMEOUT = float(os.environ.get("ROBOT_COMMAND_TIMEOUT", "1.0"))

board = MotorBoard()
running = True
client = None

last_command = time.monotonic()
moving = False
state_lock = threading.Lock()


def note_command(is_moving: bool) -> None:
    global last_command, moving
    with state_lock:
        last_command = time.monotonic()
        moving = is_moving


def watchdog() -> None:
    """Stop the motors when the commands dry up.

    The board holds its last speed until something overwrites it, so silence has to be
    treated as a fault rather than as "carry on". Re-asserts the stop on every pass
    until a write succeeds, because a stop that raises is a robot still driving.
    """
    global moving
    while running:
        time.sleep(0.05)
        problems = board.poll_errors()
        if problems:
            print(problems, file=sys.stderr)
        with state_lock:
            idle = moving and (time.monotonic() - last_command) > COMMAND_TIMEOUT
        if not idle:
            continue
        try:
            board.stop()
        except OSError as error:
            print(f"Watchdog stop failed, retrying: {error}", file=sys.stderr)
            continue
        with state_lock:
            moving = False
        print(
            f"No drive command for {COMMAND_TIMEOUT:.1f}s - motors stopped",
            file=sys.stderr,
        )


def on_message(socket: websocket.WebSocketApp, raw: str) -> None:
    try:
        message = json.loads(raw)
        if message.get("type") != "drive":
            return
        forward = message.get("forward")
        turn = message.get("turn")
        if forward not in (-1, 0, 1) or turn not in (-1, 0, 1):
            board.stop()
            note_command(False)
            return
        board.drive(forward, turn)
        note_command(forward != 0 or turn != 0)
        socket.send(json.dumps({"type": "ack", "sequence": message.get("sequence")}))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        board.stop()
        note_command(False)
        print(f"Rejected drive command: {error}", file=sys.stderr)


def on_open(_socket: websocket.WebSocketApp) -> None:
    board.stop()
    note_command(False)
    print("Connected to the FLIH control server")


def on_close(_socket: websocket.WebSocketApp, code: int, reason: str) -> None:
    board.stop()
    note_command(False)
    print(f"Control connection closed ({code}): {reason}", file=sys.stderr)


def on_error(_socket: websocket.WebSocketApp, error: object) -> None:
    board.stop()
    note_command(False)
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

    threading.Thread(target=watchdog, daemon=True).start()

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
