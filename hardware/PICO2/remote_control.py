"""Relay FLIH drive frames from the Jetson's USB serial to the motor board over I2C.

The Pico 2 has no radio, so it cannot hold the authenticated WebSocket itself. The
Jetson runs backend/robot_websocket.py and talks to this board over USB; set
ROBOT_SERIAL_PORT=/dev/ttyACM0 and nothing on the Jetson changes.

The Jetson speaks the module manual's ASCII `$cmd:args#` frames either way. FLIH's
board is wired to this Pico's I2C pins (GP4 SDA, GP5 SCL, address 0x26) rather than
its UART, so this relay parses each frame and writes the matching register from
hardware/PICO2/IIC/IIC.py. Set TRANSPORT = "uart" if the board is ever moved to
GP0/GP1; the frame format is identical on both sides of that switch.

Unlike UART, an I2C write either gets an ACK or raises, so every frame gets a real
`command+OK` or an error back up the USB link instead of best-effort silence.

`$read_vol#` and `$upload:` have no I2C equivalent: the vendor register map has no
battery register, and encoder telemetry is polled there rather than pushed.

Save to the Pico as main.py so it starts on power-up. Doing so takes over the USB
REPL, because this loop reads every character the host sends. Thonny's Stop button
still interrupts it and hands the REPL back, since nothing here calls
micropython.kbd_intr(-1). Reach for BOOTSEL only to reflash MicroPython itself: it
drops the board into the UF2 bootloader, and reflashing erases main.py with it.
"""

from machine import Pin, SoftI2C, UART
import select
import struct
import sys
import time

TRANSPORT = "i2c"  # "i2c": GP4/GP5 to the board. "uart": GP0/GP1, the vendor tutorial.

MOTOR_ADDR = 0x26
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5

# Bit-banged, not the RP2350 I2C block. On FLIH's wiring the hardware peripheral
# NACKs every data byte while the address still ACKs - measured 0/5 register writes at
# 400k, 100k and 50k, against 5/5 over SoftI2C on the same pins in the same session.
# The hardware block is far less forgiving of slow rise times than bit-banging, so this
# points at marginal pull-ups or jumper capacitance. SoftI2C at 100k drives the board
# reliably; if the bus is ever cleaned up, machine.I2C is the faster path to switch back
# to. 100 kHz is well clear of the 350 ms frame budget either way.
I2C_FREQ = 100000

# Registers, from hardware/PICO2/IIC/IIC.py.
REG_MTYPE = 0x01
REG_DEADZONE = 0x02
REG_MLINE = 0x03
REG_MPHASE = 0x04
REG_WDIAMETER = 0x05
REG_SPEED = 0x06
REG_PWM = 0x07

# Stop the wheels if a drive frame has not arrived recently. The motor board holds its
# last speed forever, so an unplugged USB cable must not leave the cart driving.
COMMAND_TIMEOUT_MS = 500

# Push telemetry has no I2C analogue; accept the frame so the Jetson's profile push
# does not look like a failure, and do nothing with it.
IGNORED = ("upload",)

led = Pin("LED", Pin.OUT)

if TRANSPORT == "i2c":
    link = SoftI2C(sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
else:
    link = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))

poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

host_buffer = ""
last_command = time.ticks_ms()
driving = False
last_drive_reg = REG_SPEED


def reply(text):
    """Answer the Jetson. motor_board.drain() reads this raw, so keep it one line."""
    try:
        sys.stdout.write(text + "\n")
    except Exception:
        pass


def int16(value):
    """Two bytes big-endian, as the board's registers want them."""
    value = max(-32768, min(32767, int(value)))
    return [(value >> 8) & 0xFF, value & 0xFF]


def four_int16(args):
    parts = args.split(",")
    if len(parts) != 4:
        raise ValueError("expected four values")
    payload = []
    for part in parts:
        payload += int16(part)
    return payload


def translate(name, args):
    """Frame to (register, payload bytes). Raises ValueError on anything unusable."""
    if name == "spd":
        return REG_SPEED, four_int16(args)
    if name == "pwm":
        return REG_PWM, four_int16(args)
    if name == "mtype":
        return REG_MTYPE, [int(args) & 0xFF]
    if name == "deadzone":
        return REG_DEADZONE, int16(args)
    if name == "mline":
        return REG_MLINE, int16(args)
    if name == "mphase":
        return REG_MPHASE, int16(args)
    if name == "wdiameter":
        return REG_WDIAMETER, list(struct.pack("<f", float(args)))
    raise ValueError("unsupported on i2c")


def write_register(register, payload):
    link.writeto_mem(MOTOR_ADDR, register, bytes(payload))


def send_stop():
    """Zero whichever channel was last driving, so a stop matches the drive mode."""
    try:
        if TRANSPORT == "i2c":
            write_register(last_drive_reg, [0] * 8)
        else:
            link.write("$spd:0,0,0,0#".encode())
    except Exception:
        pass


def handle(frame):
    """One complete `$cmd:args#` frame from the Jetson."""
    global last_command, driving, last_drive_reg

    body = frame[1:-1]
    name, _, args = body.partition(":")
    name = name.lower()

    if TRANSPORT == "uart":
        link.write(frame.encode())
        if name in ("spd", "pwm"):
            last_command = time.ticks_ms()
            driving = any(int(value) for value in args.split(","))
            led.value(driving)
        return

    if name in IGNORED:
        return reply("command+OK")

    try:
        register, payload = translate(name, args)
    except ValueError as error:
        return reply("$err:{}:{}#".format(name, error))

    try:
        write_register(register, payload)
    except Exception as error:  # A NAK means nobody is listening at 0x26.
        return reply("$err:{}:{}#".format(name, error))

    if name in ("spd", "pwm"):
        last_drive_reg = register
        last_command = time.ticks_ms()
        driving = any(payload)
        led.value(driving)

    reply("command+OK")


def read_host():
    """Pull whatever the Jetson has sent without blocking, one frame at a time."""
    global host_buffer
    while poller.poll(0):
        host_buffer += sys.stdin.read(1)
        if not host_buffer.endswith("#"):
            if len(host_buffer) > 128:  # Never let a truncated frame wedge the buffer.
                host_buffer = ""
            continue
        start = host_buffer.find("$")
        frame = host_buffer[start:] if start >= 0 else ""
        host_buffer = ""
        if frame:
            handle(frame)


try:
    send_stop()
    while True:
        read_host()
        if driving and time.ticks_diff(time.ticks_ms(), last_command) > COMMAND_TIMEOUT_MS:
            send_stop()
            driving = False
            led.value(0)
        time.sleep_ms(5)
finally:
    send_stop()
    led.value(0)
