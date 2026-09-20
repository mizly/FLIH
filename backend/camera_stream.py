"""Publishes the robot's CSI cameras to the web app as MJPEG over a WebSocket.

Holds an authenticated socket to the web app's /ws/camera endpoint and pushes a
JPEG per camera per tick. The server fans those frames out to whoever has the
control page open.

Frames are rectified onto the simulator's camera model on the way out, so the
operator sees the same geometry a sim-trained policy would be fed rather than the
raw lens: same field of view, same straight lines, black down the sides where the
lens does not reach as far as the sim does. `camera_geometry.py` explains the
mapping; `--no-rectify` sends the raw frame instead.

This is deliberately a **separate process and a separate socket** from
`robot_websocket.py`. Video is bulk traffic and driving is latency-critical: a
video frame queued ahead of a drive command on one TCP connection delays that
command by however long the frame takes to flush, and the drive path has three
dead-man timers that treat a late frame as a fault. Keeping them apart also means
a camera that wedges cannot take the motors down with it.

    export ROBOT_API_KEY=... ROBOT_CAMERA_WS_URL=ws://127.0.0.1:3000/ws/camera
    python3 backend/camera_stream.py
"""

import argparse
import os
import signal
import sys
import threading
import time

import cv2 as cv
import websocket

import camera_geometry as geom
from csi_camera import CsiCamera

# Frames carry a one-byte index so the browser knows which pane to draw into.
# Anything richer wants a header the server would have to parse, and the server's job
# here is to relay bytes it never looks inside.
#
# That byte is a **view position, not a CSI port**: 0 is the left pane, 1 is the
# right. FLIH's harness has sensor-id 0 on the right of the chassis and sensor-id 1
# on the left, so publishing the ports in numeric order puts each camera in the wrong
# pane - which is not obvious on a desk, where both cameras see much the same room.
#
# Like the motor map in hardware/MOTOR_MAP.md, this is a fact about the wiring rather
# than a preference, so it lives here as the default instead of in a --sensors flag
# someone has to remember. Re-plug the ribbon cables and this is what changes.
HEADER_BYTES = 1
SENSORS_LEFT_TO_RIGHT = [1, 0]

running = True
client = None


def log(message):
    print(message, file=sys.stderr, flush=True)


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("%s must be set" % name)
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensors", type=int, nargs="+", default=SENSORS_LEFT_TO_RIGHT,
                        help="CSI sensor ids, in the order the browser lays them out "
                             "left to right (default: %s)"
                             % " ".join(str(s) for s in SENSORS_LEFT_TO_RIGHT))
    parser.add_argument("--width", type=int, default=640,
                        help="width sent to the browser (default: 640)")
    parser.add_argument("--height", type=int, default=360,
                        help="height sent to the browser (default: 360)")
    parser.add_argument("--fps", type=int, default=15,
                        help="frames per second per camera (default: 15)")
    parser.add_argument("--quality", type=int, default=70,
                        help="JPEG quality 1-100 (default: 70)")
    parser.add_argument("--capture-width", type=int, default=geom.CAPTURE_WIDTH)
    parser.add_argument("--capture-height", type=int, default=geom.CAPTURE_HEIGHT)
    parser.add_argument("--capture-fps", type=int, default=geom.CAPTURE_FPS,
                        help="sensor mode framerate; the full-array mode tops out at 30")
    parser.add_argument("--no-rectify", action="store_true",
                        help="publish the raw lens view instead of the sim's camera model")
    parser.add_argument("--flip-method", type=int, default=0,
                        help="nvvidconv flip-method, 0=none 2=180deg")
    return parser.parse_args(argv)


def encode(frame, rectifier, width, height, quality):
    # The rectifier is built at the publish size, so it resamples and reprojects in
    # one remap and there is nothing left to resize afterwards.
    if rectifier is not None:
        frame = rectifier(frame)
    elif frame.shape[1] != width or frame.shape[0] != height:
        frame = cv.resize(frame, (width, height), interpolation=cv.INTER_AREA)
    ok, buffer = cv.imencode(".jpg", frame, [cv.IMWRITE_JPEG_QUALITY, quality])
    return buffer.tobytes() if ok else None


def publish(socket, cameras, rectifiers, args):
    """Send one JPEG per camera per tick until the socket or the cameras die."""
    interval = 1.0 / max(args.fps, 1)
    sent_serial = {camera.sensor_id: 0 for camera in cameras}
    next_tick = time.monotonic()

    while running and socket.sock is not None:
        next_tick += interval
        for index, camera in enumerate(cameras):
            frame, serial, _ = camera.read()
            # Nothing new since the last tick means the sensor is slower than the
            # publish rate; resending the same frame would only burn bandwidth.
            if frame is None or serial == sent_serial[camera.sensor_id]:
                continue
            sent_serial[camera.sensor_id] = serial
            payload = encode(frame, rectifiers[index], args.width, args.height, args.quality)
            if payload is None:
                continue
            try:
                socket.send(bytes([index]) + payload, websocket.ABNF.OPCODE_BINARY)
            except (websocket.WebSocketException, OSError) as error:
                log("Camera link send failed: %s" % error)
                return

        if not any(camera.running for camera in cameras):
            log("Every camera stopped delivering frames")
            return

        slack = next_tick - time.monotonic()
        if slack > 0:
            time.sleep(slack)
        else:
            # Encoding fell behind the tick rate. Re-base rather than accumulate
            # debt, so a transient stall does not turn into a burst.
            next_tick = time.monotonic()


def shutdown(_signal, _frame):
    global running
    running = False
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def main():
    global client
    args = parse_args()
    url = os.environ.get("ROBOT_CAMERA_WS_URL", "").strip()
    if not url:
        # The camera endpoint lives on the same server as the drive endpoint, so
        # derive it rather than make the operator set two nearly identical URLs.
        url = required("ROBOT_WS_URL").rsplit("/ws/robot", 1)[0] + "/ws/camera"
    api_key = required("ROBOT_API_KEY")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    cameras = []
    for sensor_id in args.sensors:
        camera = CsiCamera(sensor_id, args.capture_width, args.capture_height,
                           args.capture_fps, args.flip_method)
        if camera.start():
            log("sensor-id %d: streaming" % sensor_id)
        else:
            log("sensor-id %d: failed to open" % sensor_id)
        cameras.append(camera)

    if not any(camera.running for camera in cameras):
        log("No CSI cameras opened. Check that a camera device-tree overlay is "
            "enabled: gst-launch-1.0 nvarguscamerasrc sensor-id=0 num-buffers=1 ! fakesink")
        for camera in cameras:
            camera.release()
        return 1

    panes = ", ".join(
        "%s pane <- sensor-id %d" % (("left", "right")[index] if index < 2 else "pane %d" % index,
                                     camera.sensor_id)
        for index, camera in enumerate(cameras)
    )
    log("Publishing %d camera(s) to %s at %dx%d %d fps q%d (%s)"
        % (len(cameras), url, args.width, args.height, args.fps, args.quality, panes))

    rectifiers = [None] * len(cameras)
    if not args.no_rectify:
        # The published frame has to carry the sim's aspect or the rectification is
        # describing a camera nobody is using. Refuse rather than quietly reproject
        # onto a frustum the sim never renders.
        if args.width * geom.SIM_ASPECT_DEN != args.height * geom.SIM_ASPECT_NUM:
            log("--width/--height must be %d:%d to match the sim (got %dx%d). "
                "Use --no-rectify to publish the raw lens view at another shape."
                % (geom.SIM_ASPECT_NUM, geom.SIM_ASPECT_DEN, args.width, args.height))
            for camera in cameras:
                camera.release()
            return 2
        for index, camera in enumerate(cameras):
            rectifiers[index] = geom.Rectifier(
                camera.sensor_id, args.capture_width, args.capture_height,
                args.width, args.height)
        log(geom.coverage_report([camera.sensor_id for camera in cameras]))
        if not all(r.calibrated for r in rectifiers):
            log("Running on the IMX219 spec sheet, which models no lens distortion. "
                "Run backend/calibrate_cameras.py before trusting the geometry.")

    try:
        while running:
            try:
                client = websocket.create_connection(
                    url,
                    header=["Authorization: Bearer %s" % api_key],
                    timeout=10,
                    enable_multithread=True,
                )
            except (websocket.WebSocketException, OSError) as error:
                log("Camera link connect failed, retrying: %s" % error)
                if running:
                    time.sleep(2)
                continue

            log("Camera link up")
            # The server pings every 250 ms and terminates sockets that do not
            # pong, so something has to be reading while we send.
            reader = threading.Thread(target=drain, args=(client,), daemon=True)
            reader.start()
            try:
                publish(client, cameras, rectifiers, args)
            finally:
                try:
                    client.close()
                except Exception:
                    pass
                reader.join(timeout=2.0)
                log("Camera link down")

            if not any(camera.running for camera in cameras):
                break
            if running:
                time.sleep(2)
    finally:
        for camera in cameras:
            camera.release()
    return 0


def drain(socket):
    """Read and discard server traffic so the library answers pings."""
    while running and socket.sock is not None:
        try:
            socket.recv()
        except (websocket.WebSocketException, OSError):
            return


if __name__ == "__main__":
    raise SystemExit(main())
