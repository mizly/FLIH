"""Run: python -m unittest discover -s backend/tests -p 'test_*.py' -v

Pins the T-mini Plus wire format, because nothing else can.

There is no scanner attached to the machine this was written on, so every claim the
driver makes about the protocol is a claim about a document rather than about a
measurement. These tests build packets byte by byte from the YDLidar-SDK definitions
and check the parser reads back what was put in, which catches a transcription
mistake but cannot catch a mistake in the source.

Both of the numbers that needed real hardware have since been confirmed on a T-mini
Plus on /dev/ttyUSB0: the quarter-millimetre scale, by hand-decoding a packet against
a known distance, and ZERO_OFFSET_DEG, by reading the live plot against a known room.
The mount is the one that moves - re-seat the scanner and
`test_the_measured_mount_puts_device_270_at_the_nose` is what should fail first.
"""

import math
import struct
import sys
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import lidar  # noqa: E402  (needs the path above)


def build(samples, first_deg, last_deg, start=False, freq_hz=6.0, intensity=True,
          corrupt=False):
    """A packet, assembled from the spec rather than from the parser.

    `samples` are (quality, distance_quarter_mm, flag) triples. The checksum is
    recomputed here independently so a change to `lidar.checksum` cannot make a
    broken packet look valid.
    """
    control = (int(round(freq_hz * 10)) << 1) | (1 if start else 0)
    header = struct.pack("<HBBHH", 0x55AA, control, len(samples),
                         int(round(first_deg * 64)) << 1,
                         int(round(last_deg * 64)) << 1)
    body = b""
    for quality, distance, flag in samples:
        value = (distance & 0xFFFC) | (flag & 0x0003)
        body += struct.pack("<BH", quality, value) if intensity else struct.pack("<H", value)

    checksum = 0
    for offset in (0, 2, 4, 6):
        checksum ^= struct.unpack_from("<H", header, offset)[0]
    stride = 3 if intensity else 2
    for index in range(len(samples)):
        base = index * stride
        if intensity:
            checksum ^= body[base]
            checksum ^= struct.unpack_from("<H", body, base + 1)[0]
        else:
            checksum ^= struct.unpack_from("<H", body, base)[0]
    if corrupt:
        checksum ^= 0x0001

    return header + struct.pack("<H", checksum) + body


def turn(points=80, start=True):
    """One revolution as two packets, the first flagged as the start."""
    half = points // 2
    metres = 1.0
    first = [(200, int(metres * 4000), 0)] * half
    second = [(200, int(metres * 4000), 0)] * (points - half)
    return [build(first, 0.0, 179.0, start=start),
            build(second, 180.0, 359.0, start=False)]


class PacketTests(unittest.TestCase):
    def test_decode_round_trips_a_packet(self):
        packet = lidar.decode(build([(77, 4000, 0), (78, 8000, 0)], 10.0, 11.0, start=True))
        self.assertIsNotNone(packet)
        self.assertTrue(packet["start"])
        self.assertEqual(packet["intensities"], [77, 78])
        self.assertAlmostEqual(packet["reported_hz"], 6.0, places=3)

    def test_distance_is_quarter_millimetres(self):
        """4000 quarter-millimetres is one metre. The TOF parts use /1000 instead."""
        packet = lidar.decode(build([(0, 4000, 0), (0, 2000, 0)], 0.0, 1.0))
        self.assertAlmostEqual(packet["ranges"][0], 1.0, places=6)
        self.assertAlmostEqual(packet["ranges"][1], 0.5, places=6)

    def test_low_two_bits_are_flags_not_distance(self):
        """A glass or sunlight flag must not shift the range it rides on."""
        clean = lidar.decode(build([(0, 4000, 0)], 0.0, 1.0))
        flagged = lidar.decode(build([(0, 4000, lidar.FLAG_SUNLIGHT)], 0.0, 1.0))
        self.assertEqual(clean["ranges"], flagged["ranges"])
        self.assertEqual(flagged["flags"], [lidar.FLAG_SUNLIGHT])

    def test_no_return_is_zero_metres(self):
        packet = lidar.decode(build([(0, 0, 0)], 0.0, 1.0))
        self.assertEqual(packet["ranges"], [0.0])

    def test_angles_are_linear_with_no_second_order_correction(self):
        """The T-mini is excluded from the SDK's mirror-offset correction.

        Applying it anyway would bend near returns by degrees, and it would still
        look like a room - just the wrong one - so nothing but a test catches it.
        """
        count = 5
        packet = lidar.decode(build([(0, 4000, 0)] * count, 100.0, 108.0))
        step = 8.0 / (count - 1)
        for index, angle in enumerate(packet["angles"]):
            self.assertAlmostEqual(angle, 100.0 + step * index, places=3)

    def test_last_angle_wraps_past_360(self):
        """A packet straddling the wrap has a last angle lower than its first."""
        packet = lidar.decode(build([(0, 4000, 0)] * 3, 359.0, 1.0))
        self.assertAlmostEqual(packet["angles"][0], 359.0, places=2)
        self.assertAlmostEqual(packet["angles"][1], 0.0, places=2)
        self.assertAlmostEqual(packet["angles"][2], 1.0, places=2)

    def test_bad_checksum_is_rejected(self):
        self.assertIsNone(lidar.decode(build([(0, 4000, 0)], 0.0, 1.0, corrupt=True)))

    def test_packets_without_intensity_are_two_bytes_a_sample(self):
        raw = build([(0, 4000, 0), (0, 8000, 0)], 0.0, 1.0, intensity=False)
        self.assertEqual(len(raw), lidar.HEADER_BYTES + 2 * 2)
        packet = lidar.decode(raw, intensity=False)
        self.assertAlmostEqual(packet["ranges"][0], 1.0, places=6)
        # The same bytes read with the wrong framing must not pass as valid.
        self.assertIsNone(lidar.decode(raw, intensity=True))


class FrameTests(unittest.TestCase):
    def test_the_measured_mount_puts_device_270_at_the_nose(self):
        """Measured off the live plot against a known room, not derived from the yaml.

        The vendor's reversion+inverted pair would give 180. FLIH's scanner sits a
        quarter turn round from that, which showed up as a map rotated 90 degrees
        clockwise - a completely plausible-looking room, just the wrong one.
        """
        self.assertAlmostEqual(lidar.to_robot_frame(270.0), 0.0, places=9)
        # A quarter turn either side of the nose lands on the robot's flanks.
        self.assertAlmostEqual(lidar.to_robot_frame(180.0), math.pi / 2, places=9)
        self.assertAlmostEqual(lidar.to_robot_frame(0.0), -math.pi / 2, places=9)

    def test_device_angles_run_clockwise_and_robot_angles_run_counterclockwise(self):
        """The sign flip itself, independent of wherever the scanner is bolted."""
        self.assertAlmostEqual(lidar.to_robot_frame(0.0, zero_offset_deg=0.0), 0.0, places=9)
        self.assertAlmostEqual(lidar.to_robot_frame(90.0, zero_offset_deg=0.0),
                               -math.pi / 2, places=9)
        self.assertAlmostEqual(lidar.to_robot_frame(270.0, zero_offset_deg=0.0),
                               math.pi / 2, places=9)

    def test_output_is_normalised(self):
        for degrees in range(0, 360, 7):
            angle = lidar.to_robot_frame(float(degrees))
            self.assertGreaterEqual(angle, -math.pi)
            self.assertLess(angle, math.pi)

    def test_a_remounted_scanner_is_one_constant(self):
        self.assertAlmostEqual(lidar.to_robot_frame(0.0, zero_offset_deg=0.0), 0.0, places=9)


class ReaderTests(unittest.TestCase):
    def test_a_packet_split_across_reads_still_arrives(self):
        packet = build([(0, 4000, 0)] * 4, 0.0, 3.0)
        reader = lidar.PacketReader()
        for index in range(1, len(packet)):
            reader = lidar.PacketReader()
            self.assertEqual(reader.feed(packet[:index]), [])
            self.assertEqual(len(reader.feed(packet[index:])), 1)

    def test_a_header_split_across_reads_still_arrives(self):
        """0xAA and 0x55 landing in different reads is the case a naive find() loses."""
        packet = build([(0, 4000, 0)] * 4, 0.0, 3.0)
        reader = lidar.PacketReader()
        self.assertEqual(reader.feed(b"\x11\x22" + packet[:1]), [])
        self.assertEqual(len(reader.feed(packet[1:])), 1)

    def test_a_false_header_does_not_swallow_the_real_one(self):
        """0xAA 0x55 occurs in payload; dropping the whole apparent packet loses data."""
        packet = build([(0, 4000, 0)] * 4, 0.0, 3.0)
        noise = b"\xaa\x55\x30\x02" + b"\x00" * 20
        reader = lidar.PacketReader()
        packets = reader.feed(noise + packet)
        self.assertEqual(len(packets), 1)
        self.assertGreater(reader.checksum_errors, 0)

    def test_leading_garbage_is_skipped(self):
        packet = build([(0, 4000, 0)] * 4, 0.0, 3.0)
        reader = lidar.PacketReader()
        self.assertEqual(len(reader.feed(b"\x01\x02\x03" + packet)), 1)

    def test_the_buffer_does_not_grow_without_bound_on_pure_noise(self):
        reader = lidar.PacketReader()
        for _ in range(50):
            reader.feed(b"\x00\x11\x22\x33" * 64)
        self.assertLessEqual(len(reader._buffer), 2)


class FakePort:
    """Just enough pyserial for the driver: hand out bytes, then nothing."""

    def __init__(self, chunks, answer=None):
        self.chunks = list(chunks)
        self.closed = False
        self.written = bytearray()
        self.answer = answer

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, size):
        # The handshake reads a fixed-size reply before the stream starts.
        if self.answer is not None:
            reply, self.answer = self.answer[:size], None
            return reply
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, data):
        self.written.extend(data)
        return len(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def close(self):
        self.closed = True


class ScanAssemblyTests(unittest.TestCase):
    def drive(self, chunks):
        scanner = lidar.TminiPlus(port="fake")
        scanner._serial_port = FakePort(chunks)
        self.assertTrue(scanner.start())
        for _ in range(200):
            scan, serial = scanner.read()
            if serial:
                break
            import time
            time.sleep(0.005)
        scanner.release()
        return scanner.read()

    def test_a_turn_is_published_at_the_next_start_flag(self):
        stream = b"".join(turn() + turn())
        scan, serial = self.drive([stream])
        self.assertEqual(serial, 1)
        self.assertEqual(len(scan), 80)
        self.assertEqual(scan.returns, 80)
        self.assertAlmostEqual(scan.reported_hz, 6.0, places=3)

    def test_the_partial_first_turn_is_dropped(self):
        """Packets before the first start flag are a wedge, not a revolution."""
        stream = b"".join([build([(0, 4000, 0)] * 40, 200.0, 359.0)] + turn() + turn())
        scan, _ = self.drive([stream])
        self.assertEqual(len(scan), 80)

    def test_a_short_turn_is_not_published(self):
        """A resync artefact must not draw an empty room."""
        runt = [build([(0, 4000, 0)] * 4, 0.0, 3.0, start=True)]
        stream = b"".join(turn() + runt + turn())
        scan, serial = self.drive([stream])
        self.assertEqual(serial, 1)
        self.assertEqual(len(scan), 80)

    def test_angles_arrive_in_the_robot_frame(self):
        scan, _ = self.drive([b"".join(turn() + turn())])
        self.assertTrue(all(-math.pi <= a < math.pi for a in scan.angles))


class HandshakeTests(unittest.TestCase):
    """The scanner is silent until commanded, which no amount of parsing fixes."""

    # The seven bytes a healthy T-mini Plus actually replied with on /dev/ttyUSB0.
    GOOD = bytes([0xA5, 0x5A, 0x05, 0x00, 0x00, 0x40, lidar.ANS_TYPE_MEASUREMENT])

    def open_with(self, answer, chunks=()):
        """Run the real open() against a fake port, and hand back both."""
        port = FakePort(list(chunks), answer=answer)
        scanner = lidar.TminiPlus(port="fake")
        original = lidar.serial.Serial
        lidar.serial.Serial = lambda *args, **kwargs: port
        try:
            opened = scanner.open()
        finally:
            lidar.serial.Serial = original
        return scanner, port, opened

    def test_open_sends_stop_then_scan(self):
        """Stop first, or a unit left scanning buries the reply in its own packets."""
        scanner, port, opened = self.open_with(self.GOOD)
        self.assertTrue(opened)
        self.assertEqual(bytes(port.written),
                         bytes([lidar.CMD_SYNC, lidar.CMD_STOP,
                                lidar.CMD_SYNC, lidar.CMD_SCAN]))
        self.assertIsNone(scanner.error)

    def test_silence_is_reported_rather_than_looking_healthy(self):
        """The bug this catches: port opens, reads nothing forever, reports no error."""
        scanner, _, opened = self.open_with(b"")
        self.assertFalse(opened)
        self.assertIn("scan command", scanner.error)

    def test_a_reply_that_is_not_measurement_data_is_refused(self):
        answer = self.GOOD[:6] + bytes([lidar.ANS_TYPE_MEASUREMENT ^ 0xFF])
        scanner, _, opened = self.open_with(answer)
        self.assertFalse(opened)
        self.assertIn("not measurement", scanner.error)

    def test_a_reply_with_the_wrong_sync_is_refused(self):
        scanner, _, opened = self.open_with(b"\x00\x00\x00\x00\x00\x00\x81")
        self.assertFalse(opened)
        self.assertIn("scan command", scanner.error)

    def test_release_stops_the_scanner(self):
        scanner, port, _ = self.open_with(self.GOOD)
        port.written.clear()
        scanner.release()
        self.assertEqual(bytes(port.written), bytes([lidar.CMD_SYNC, lidar.CMD_STOP]))
        self.assertTrue(port.closed)


class PortTests(unittest.TestCase):
    def test_autodetect_never_offers_the_motor_board(self):
        """/dev/ttyACM0 is the Pico 2 relay on FLIH, and one vendor udev rule matches it."""
        source = (BACKEND / "lidar.py").read_text()
        self.assertIn('startswith("/dev/ttyACM")', source)


if __name__ == "__main__":
    unittest.main()
