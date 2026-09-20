"""YDLIDAR T-mini Plus capture, read straight off the serial port.

FLIH reads the scanner itself instead of going through ROS. The Yahboom workspace
under `hardware/Jetson NANO/lidar/` is the vendor's ROS 2 driver and is kept for
reference, but it is not what runs here and cannot be: it builds against
`ydlidar_sdk`, a separate C++ package its CMakeLists marks REQUIRED and which is not
installed, and this machine has no ROS 2 at all. The protocol turns out to be ten
bytes of header and three bytes a point, which is far less to carry than a ROS graph,
and it keeps the scan in the same process as the rest of the backend.

The frame this produces is field-for-field what a `sensor_msgs/LaserScan` carries, so
if ROS 2 does arrive later, `lidar_stream.py` can be pointed at a `/scan`
subscription and nothing downstream needs to change. See the note by
`ZERO_OFFSET_DEG` for the one place the two conventions have to be reconciled.

Getting at the data
-------------------

    from lidar import TminiPlus

    lidar = TminiPlus()             # finds its own port
    lidar.start()
    scan, serial = lidar.read()     # newest complete turn, (None, 0) before the first
    scan.ranges                     # metres, one per sample, 0.0 = no return
    scan.angles                     # radians, robot frame: 0 forward, positive left

`read()` never blocks and always hands back the most recent completed turn, the way
`csi_camera.CsiCamera.read()` hands back the newest frame. A consumer that falls
behind skips ahead in time rather than working through a queue of stale scans. The
serial number distinguishes a fresh turn from one already seen without comparing
arrays.

The angles come out in the convention `fly-gym` already expects, so a scan feeds the
simulator's own preprocessing untouched:

    from core.lidar import lidar_proximity_features   # fly-gym, needs only numpy
    from robot_config import LIDAR_CONFIG

    features = lidar_proximity_features(scan.ranges, scan.angles, LIDAR_CONFIG)

with no `clockwise=True`, because that conversion has already happened here. Those 12
numbers are what the trained policy actually sees; everything else in a scan is for
the operator. Invalid returns are 0.0 metres, which is exactly what that function
treats as "no reading", so dropped points need no special handling.

The wire protocol
-----------------

Little-endian throughout. One packet is one angular slice of a turn, up to 40 points
on this part:

    offset size field
    0      2    header   0xAA 0x55 on the wire (uint16 0x55AA)
    2      1    ct       bit 0 set on the first packet of a turn;
                         ct >> 1 is the spin rate in tenths of a hertz
    3      1    count    samples in this packet
    4      2    fsa      angle of the first sample: degrees = (fsa >> 1) / 64
    6      2    lsa      angle of the last sample:  degrees = (lsa >> 1) / 64
    8      2    checksum xor of every 16-bit word, see `checksum`
    10     3*n  samples  [intensity uint8][value uint16] each

    value & 0xFFFC   distance in quarter-millimetres, so metres = that / 4000
    value & 0x0003   0 normal, 2 glass-like return, 3 sunlight interference

Sample angles are linear between `fsa` and `lsa` with `lsa` wrapped past 360 when it
reads lower. Most YDLIDAR parts then apply a second-order correction for the offset
between the spinning mirror and the axis; **the T-mini series does not**, and the
SDK excludes it by model (`!isTminiLidar(model)` in `YDlidarDriver::parsePoints`).
Applying it anyway skews near returns by degrees, so it is absent here on purpose.

Everything above is taken from YDLidar-SDK master: `core/common/ydlidar_protocol.h`
for the layout, `YDlidarDriver.cpp::parsePoints` for the angles and the masks, and
`CYdLidar.cpp` for the quarter-millimetre scale, which is chosen there by lidar type
rather than by model. Do not "simplify" the /4000: the TOF parts use /1000 and it is
the one place a wrong constant still produces a plausible-looking plot.
"""

import math
import struct
import threading
import time

import serial
from serial.tools import list_ports

# The vendor's params/TminiPro.yaml, which is what the Yahboom launch file loads.
BAUDRATE = 230400
# The T-mini Plus reports 8-bit intensity. Kept as a flag because the SDK will fall
# back to no-intensity framing on repeated checksum failures, and a unit that has been
# reconfigured would otherwise just look broken.
INTENSITY = True

# The scanner is silent until told to scan. Commands are two bytes, 0xA5 then the
# code; the reply is a seven-byte header, 0xA5 0x5A, a packed size/subtype word, and
# a type byte, after which the packets above stream continuously. 0x81 is the type
# that means "measurement data follows"; anything else means the unit answered but is
# not scanning, which is worth telling apart from silence.
#
# This is the one part of the protocol that is not in the packet layout, and it is
# easy to miss: the vendor's ROS driver never issues it either, because the SDK does
# it inside `startScan`. Without it the port opens cleanly, reads zero bytes forever,
# and reports no error at all.
CMD_SYNC = 0xA5
CMD_STOP = 0x65
CMD_SCAN = 0x60
ANS_SYNC = b"\xa5\x5a"
ANS_TYPE_MEASUREMENT = 0x81
ANS_HEADER_BYTES = 7

HEADER = b"\xaa\x55"
HEADER_BYTES = 10
MAX_SAMPLES = 40  # TRI_PACKMAXNODES is 80, but only the G4 fills it.

FLAG_NORMAL = 0
FLAG_GLASS = 2
FLAG_SUNLIGHT = 3

# Where the scanner's own zero mark sits, measured counterclockwise from the robot's
# forward axis, in degrees.
#
# This is the whole of the mounting convention and the only number here that is about
# FLIH rather than about the sensor. **270 is measured, not derived**: it was read off
# the live plot against a known room, which came out a quarter turn clockwise of the
# truth until this went from 180 to 270.
#
# 180 is what the vendor's yaml would give - it sets `reversion: true` (add 180
# degrees) and `inverted: true` (flip to counterclockwise), which together make the
# ROS `/scan` angle `pi - raw`. FLIH's scanner is mounted a quarter turn round from
# the orientation that yaml assumes, so a scan from this driver and a scan from the
# vendor's ROS driver on this robot do *not* agree: theirs would be 90 degrees out.
# If this ever runs against the vendor stack, that is the reconciliation to make.
#
# Re-seat the scanner and this is the one number to change. To re-measure it: put
# something narrow a metre or so directly in front of the robot and confirm the blip
# lands at the top of the plot and in the `+0.0 deg` row of
# `hardware/Jetson NANO/lidar/test_lidar.py --bearings`. Add 90 for each quarter turn
# the map needs to rotate counterclockwise. Nothing else in the pipeline moves.
ZERO_OFFSET_DEG = 270.0

# A turn this far from a plausible one is a resync artefact rather than a scan: the
# T-mini spins at 6-10 Hz and samples at 4 kHz, so a turn holds roughly 400-670
# points. Publishing a 12-point "turn" would draw a near-empty plot that reads as
# "nothing around me", which is the one wrong answer that looks safe.
MIN_SCAN_POINTS = 60


class Scan:
    """One complete revolution.

    `angles` and `ranges` line up index for index. Unlike a `LaserScan` the angles
    are explicit rather than implied by an increment, because the T-mini's samples
    are not evenly spaced: each packet interpolates across its own slice, and the
    slices are not all the same width. Storing them explicitly is also what
    `lidar_proximity_features` wants.
    """

    __slots__ = ("stamp", "angles", "ranges", "intensities", "flags", "reported_hz", "measured_hz")

    def __init__(self, stamp, angles, ranges, intensities, flags, reported_hz, measured_hz):
        self.stamp = stamp
        self.angles = angles
        self.ranges = ranges
        self.intensities = intensities
        self.flags = flags
        self.reported_hz = reported_hz      # what the scanner says it is spinning at
        self.measured_hz = measured_hz      # what we actually timed between turns

    def __len__(self):
        return len(self.ranges)

    @property
    def returns(self):
        """How many samples came back with a distance; the rest saw nothing."""
        return sum(1 for r in self.ranges if r > 0)


def checksum(packet, intensity=INTENSITY):
    """The packet's own 16-bit xor, recomputed.

    Every 16-bit word of the header takes part, including the 0x55AA, but the
    checksum field itself does not. Each sample then contributes its intensity byte
    on its own and its 16-bit value, which is the only reason the intensity flag has
    to be right to validate a packet at all.
    """
    count = packet[3]
    stride = 3 if intensity else 2
    value = 0
    for offset in (0, 2, 4, 6):
        value ^= struct.unpack_from("<H", packet, offset)[0]
    for index in range(count):
        base = HEADER_BYTES + index * stride
        if intensity:
            value ^= packet[base]
            value ^= struct.unpack_from("<H", packet, base + 1)[0]
        else:
            value ^= struct.unpack_from("<H", packet, base)[0]
    return value


def decode(packet, intensity=INTENSITY):
    """One packet into its samples, or None when the checksum rejects it.

    Returns a dict rather than a class because nothing keeps a packet: the assembler
    reads it once and throws it away.
    """
    count = packet[3]
    if len(packet) != HEADER_BYTES + count * (3 if intensity else 2):
        return None
    if checksum(packet, intensity) != struct.unpack_from("<H", packet, 8)[0]:
        return None

    control = packet[2]
    first, last = struct.unpack_from("<HH", packet, 4)
    first = (first >> 1) / 64.0
    last = (last >> 1) / 64.0
    if last < first:
        last += 360.0
    step = (last - first) / (count - 1) if count > 1 else 0.0

    angles, ranges, intensities, flags = [], [], [], []
    stride = 3 if intensity else 2
    for index in range(count):
        base = HEADER_BYTES + index * stride
        if intensity:
            quality = packet[base]
            value = struct.unpack_from("<H", packet, base + 1)[0]
            flag = value & 0x0003
            value &= 0xFFFC
        else:
            quality = 0
            value = struct.unpack_from("<H", packet, base)[0]
            flag = FLAG_NORMAL
        angles.append((first + step * index) % 360.0)
        ranges.append(value / 4000.0)
        intensities.append(quality)
        flags.append(flag)

    return {
        # Bit 0 of ct, the only framing that says where a revolution begins. Without
        # it there is no way to cut the stream into turns: angles alone cannot do it,
        # because a packet may straddle the wrap.
        "start": bool(control & 0x01),
        "reported_hz": (control >> 1) / 10.0,
        "angles": angles,
        "ranges": ranges,
        "intensities": intensities,
        "flags": flags,
    }


class PacketReader:
    """Byte stream in, packets out, resynchronising on its own.

    Serial gives no framing, so every read has to find the header itself. Two things
    make that less simple than scanning for 0xAA 0x55: the pattern occurs in payload
    often enough to matter at 230400 baud, and a header can straddle two reads.
    """

    def __init__(self, intensity=INTENSITY):
        self.intensity = intensity
        self.checksum_errors = 0
        self._buffer = bytearray()

    def feed(self, chunk):
        """Append bytes and return every whole packet they completed."""
        buffer = self._buffer
        buffer.extend(chunk)
        packets = []
        stride = 3 if self.intensity else 2

        while True:
            start = buffer.find(HEADER)
            if start < 0:
                # Keep the last byte: a header split across two reads has to survive.
                del buffer[:max(0, len(buffer) - 1)]
                break
            if start:
                del buffer[:start]
            if len(buffer) < HEADER_BYTES:
                break
            size = HEADER_BYTES + buffer[3] * stride
            if len(buffer) < size:
                break

            packet = decode(bytes(buffer[:size]), self.intensity)
            if packet is None:
                # The checksum says those two bytes were payload that happened to
                # read 0xAA 0x55. Drop only them and search again from just past:
                # skipping the whole apparent packet would swallow the real header
                # sitting inside it.
                self.checksum_errors += 1
                del buffer[:2]
                continue

            del buffer[:size]
            packets.append(packet)

        return packets


def to_robot_frame(degrees_clockwise, zero_offset_deg=ZERO_OFFSET_DEG):
    """Device angle to robot angle: radians, counterclockwise, 0 forward, in [-pi, pi).

    The scanner counts clockwise from its own zero mark, which is the opposite of
    every convention downstream - ROS, `fly-gym` and the plot on the control page all
    count counterclockwise from the robot's nose - so the sign flips here, once, at
    the edge, and nothing after this has to think about it.
    """
    angle = math.radians(zero_offset_deg - degrees_clockwise)
    return (angle + math.pi) % (2 * math.pi) - math.pi


def find_port():
    """The scanner's serial port, or None.

    The T-mini Plus arrives as a CP210x bridge (10c4:ea60); the vendor's udev rules
    also allow a PL2303 and an STM32 CDC variant, and point /dev/ydlidar at whichever
    turned up. That symlink wins when it exists because it survives a re-enumeration.

    ttyACM is never considered even though one of those vendor rules matches it. On
    FLIH that port is the Pico 2 motor relay, and probing a running motor board with
    scanner start-up bytes is not a thing to do by accident. A T-mini that genuinely
    enumerates as ttyACM has to be named with --port.
    """
    known = {(0x10C4, 0xEA60), (0x067B, 0x2303)}
    for port in list_ports.comports():
        if port.device.startswith("/dev/ttyACM"):
            continue
        if (port.vid, port.pid) in known:
            return port.device
    for port in list_ports.comports():
        if port.device.startswith("/dev/ttyUSB"):
            return port.device
    return None


class TminiPlus:
    """One scanner, read in the background so the newest turn is always ready."""

    def __init__(self, port=None, baudrate=BAUDRATE, intensity=INTENSITY,
                 zero_offset_deg=ZERO_OFFSET_DEG, timeout=1.0):
        self.port = port or "/dev/ydlidar"
        self.baudrate = baudrate
        self.intensity = intensity
        self.zero_offset_deg = zero_offset_deg
        self.timeout = timeout
        self.error = None
        self._serial_port = None
        self._reader = PacketReader(intensity)
        self._scan = None
        self._serial = 0
        self._last_turn = None
        self._measured_hz = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    @property
    def running(self):
        return self._running

    def open(self):
        """Open the port and start the scan. False, with `error` set, when it cannot.

        The stop comes first on purpose. A unit left scanning by a process that died
        without cleaning up is still mid-stream, and the scan command's reply would
        arrive buried in packets with no way to find it. Stopping first makes the
        handshake the same whatever state the scanner was left in.
        """
        try:
            self._serial_port = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except (serial.SerialException, OSError) as problem:
            self.error = str(problem)
            return False

        try:
            self._command(CMD_STOP)
            time.sleep(0.3)
            # Whatever the scanner sent while nothing was listening describes a world
            # that has since moved. Start from the next byte.
            self._serial_port.reset_input_buffer()
            self._command(CMD_SCAN)
            answer = self._serial_port.read(ANS_HEADER_BYTES)
        except (serial.SerialException, OSError) as problem:
            self.error = str(problem)
            self._close_port()
            return False

        if len(answer) < ANS_HEADER_BYTES or not answer.startswith(ANS_SYNC):
            self.error = ("no valid reply to the scan command (read %d bytes: %s). "
                          "Wrong baud rate, wrong port, or the scanner is not powered."
                          % (len(answer), answer.hex(" ") or "nothing"))
            self._close_port()
            return False
        if answer[6] != ANS_TYPE_MEASUREMENT:
            self.error = ("the scanner answered with type 0x%02x, not measurement data"
                          % answer[6])
            self._close_port()
            return False
        return True

    def _command(self, code):
        self._serial_port.write(bytes([CMD_SYNC, code]))
        self._serial_port.flush()

    def _close_port(self):
        if self._serial_port is None:
            return
        try:
            self._serial_port.close()
        finally:
            self._serial_port = None

    def start(self):
        """Open if needed and begin reading. False when the port did not open."""
        if self._serial_port is None and not self.open():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        # Points accumulated since the last start-of-turn flag.
        pending = ([], [], [], [])
        reported_hz = 0.0
        # The first flag we see lands mid-revolution, so the points before it are a
        # partial turn. Dropped rather than published, or the first plot shows a
        # wedge of the room and a wedge of nothing.
        seen_start = False

        while self._running:
            try:
                waiting = self._serial_port.in_waiting or 1
                chunk = self._serial_port.read(waiting)
            except (serial.SerialException, OSError) as problem:
                self.error = str(problem)
                self._running = False
                break

            if not chunk:
                # Timeout with nothing on the wire: spinning down, unplugged, or
                # never started. Leave the last scan for read() to age out. The
                # sleep only matters if the port ever stops honouring its own
                # timeout, which would otherwise turn this into a busy loop.
                time.sleep(0.01)
                continue

            for packet in self._reader.feed(chunk):
                if packet["start"]:
                    if seen_start and len(pending[0]) >= MIN_SCAN_POINTS:
                        self._publish(pending, reported_hz)
                    pending = ([], [], [], [])
                    seen_start = True
                if packet["reported_hz"]:
                    reported_hz = packet["reported_hz"]
                for store, key in zip(pending, ("angles", "ranges", "intensities", "flags")):
                    store.extend(packet[key])

    def _publish(self, pending, reported_hz):
        degrees, ranges, intensities, flags = pending
        now = time.time()
        elapsed = None if self._last_turn is None else now - self._last_turn
        self._last_turn = now
        if elapsed and elapsed > 0:
            instant = 1.0 / elapsed
            self._measured_hz = (instant if not self._measured_hz
                                 else 0.8 * self._measured_hz + 0.2 * instant)

        scan = Scan(
            stamp=now,
            angles=[to_robot_frame(d, self.zero_offset_deg) for d in degrees],
            ranges=ranges,
            intensities=intensities,
            flags=flags,
            reported_hz=reported_hz,
            measured_hz=self._measured_hz,
        )
        with self._lock:
            self._scan = scan
            self._serial += 1

    def read(self):
        """The newest complete turn and its serial number; (None, 0) before the first.

        The Scan is immutable once published, so this hands back the object itself
        rather than a copy.
        """
        with self._lock:
            return self._scan, self._serial

    def release(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._serial_port is not None:
            # Leave the scanner idle rather than spinning into a closed port, so the
            # next open's handshake starts from a known state.
            try:
                self._command(CMD_STOP)
            except (serial.SerialException, OSError):
                pass
        self._close_port()
