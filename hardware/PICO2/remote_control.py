"""Relay FLIH drive frames from the Jetson's USB serial to the motor board's UART.

The Pico 2 has no radio, so it cannot hold the authenticated WebSocket itself. The
Jetson runs backend/robot_websocket.py and talks to this board over USB instead of
straight to the motor driver; set ROBOT_SERIAL_PORT=/dev/ttyACM0 and nothing else
changes. Frames pass through untouched, so the Jetson stays the single source of the
motor profile, and `$MSPD:` speed reports are echoed back up the USB link.

Save to the Pico as main.py so it starts on power-up. Doing so takes over the USB
REPL; hold BOOTSEL while plugging in to get it back.
"""

from machine import UART, Pin
import select
import sys
import time

# Stop the wheels if a $spd frame has not arrived recently. The motor board holds its
# last speed forever, so an unplugged USB cable must not leave the cart driving.
COMMAND_TIMEOUT_MS = 500
STOP_FRAME = "$spd:0,0,0,0#"

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
led = Pin("LED", Pin.OUT)

poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

host_buffer = ""
last_command = time.ticks_ms()
driving = False


def send_to_board(frame):
    uart.write(frame.encode())


def read_host():
    """Pull whatever the Jetson has sent without blocking, one frame at a time."""
    global host_buffer, last_command, driving
    while poller.poll(0):
        host_buffer += sys.stdin.read(1)
        if not host_buffer.endswith("#"):
            if len(host_buffer) > 128:  # Never let a truncated frame wedge the buffer.
                host_buffer = ""
            continue
        start = host_buffer.find("$")
        frame = host_buffer[start:] if start >= 0 else ""
        host_buffer = ""
        if not frame:
            continue
        send_to_board(frame)
        if frame.startswith("$spd:") or frame.startswith("$pwm:"):
            last_command = time.ticks_ms()
            driving = frame not in (STOP_FRAME, "$pwm:0,0,0,0#")
            led.value(driving)


def read_board():
    """Pass the board's replies straight up the USB link, unparsed.

    Config writes answer with a bare `command+OK` and no `#`, so anything that
    reassembles frames here would swallow them. The Jetson reads the raw stream.

    Bytes go out without decoding, and anything that still goes wrong is dropped:
    board chatter is optional, but this is the loop that also holds the stop
    watchdog, so nothing here may be allowed to break out of it.
    """
    pending = uart.any()
    if not pending:
        return
    data = uart.read(pending)
    if not data:
        return
    try:
        sys.stdout.buffer.write(data)
    except Exception:
        pass


try:
    send_to_board(STOP_FRAME)
    while True:
        read_host()
        read_board()
        if driving and time.ticks_diff(time.ticks_ms(), last_command) > COMMAND_TIMEOUT_MS:
            send_to_board(STOP_FRAME)
            driving = False
            led.value(0)
        time.sleep_ms(5)
finally:
    send_to_board(STOP_FRAME)
    led.value(0)
