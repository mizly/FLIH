"""CSI camera capture for the Jetson's two ports.

Wraps `nvarguscamerasrc` behind OpenCV so the rest of the backend never has to
think about GStreamer. Each camera is read on its own thread and only the newest
frame is kept: a consumer that falls behind should skip ahead in time rather than
work through a queue of stale video.

`hardware/Jetson NANO/test_camera_csi_dual.py` is the bench viewer for this, and
`camera_stream.py` is what feeds the web app.
"""

import threading
import time

import cv2 as cv

# Both IMX219s report the same five modes. 1640x1232 is the 2x2-binned full sensor
# array, and it is the default because of what the simulator expects rather than
# because of anything about the sensor: fly-gym renders 42.61 degrees vertically, and
# every 16:9 mode on this part is a vertical crop of the array that falls short of
# that (~37.6 degrees at 3264x1848, less again at 1280x720). Only the full-array
# modes contain the sim's vertical field of view, so only they can be rectified onto
# it. See camera_geometry.py.
#
# The cost is frame rate: 1280x720 is the only mode that reaches 60 fps, and this is
# 30. The video link publishes at 15, so nothing downstream notices today.
#
# Argus picks the mode from the caps, so asking for a size it does not have makes it
# scale rather than fail -- which is worth knowing, because a silently scaled frame
# has the field of view of whatever mode Argus actually chose, not of the size asked
# for, and a calibration taken through one is wrong for the other.
DEFAULT_WIDTH = 1640
DEFAULT_HEIGHT = 1232
DEFAULT_FPS = 30


def gst_pipeline(sensor_id, width, height, fps, flip_method=0):
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=%d, height=%d, format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=%d, height=%d, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! "
        "appsink drop=1 max-buffers=2 sync=false"
        % (sensor_id, width, height, fps, flip_method, width, height)
    )


class CsiCamera:
    """One CSI port, read in the background so the newest frame is always ready."""

    def __init__(self, sensor_id, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                 fps=DEFAULT_FPS, flip_method=0):
        self.sensor_id = sensor_id
        self.width = width
        self.height = height
        self.capture = cv.VideoCapture(
            gst_pipeline(sensor_id, width, height, fps, flip_method), cv.CAP_GSTREAMER
        )
        self._frame = None
        self._serial = 0
        self._fps = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def is_opened(self):
        return self.capture.isOpened()

    def start(self):
        """Begin capturing. False when the port did not open."""
        if not self.is_opened():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    @property
    def running(self):
        return self._running

    def _loop(self):
        last = time.monotonic()
        while self._running:
            ok, frame = self.capture.read()
            if not ok:
                # Argus dropped the stream. Stop rather than spin on a dead pipe,
                # and leave the last frame in place for read() to age out.
                self._running = False
                break
            now = time.monotonic()
            gap = now - last
            last = now
            with self._lock:
                self._frame = frame
                self._serial += 1
                if gap > 0:
                    instant = 1.0 / gap
                    self._fps = instant if not self._fps else 0.9 * self._fps + 0.1 * instant

    def read(self):
        """The newest frame, its serial number, and the measured capture rate.

        The serial lets a caller tell a fresh frame from one it has already seen
        without comparing pixel buffers.
        """
        with self._lock:
            if self._frame is None:
                return None, self._serial, self._fps
            return self._frame.copy(), self._serial, self._fps

    def release(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.capture.release()


def open_cameras(sensor_ids, width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                 fps=DEFAULT_FPS, flip_method=0, log=None):
    """Open and start every listed port, reporting each one's outcome."""
    cameras = []
    for sensor_id in sensor_ids:
        camera = CsiCamera(sensor_id, width, height, fps, flip_method)
        started = camera.start()
        if log:
            log("sensor-id %d: %s" % (sensor_id, "streaming" if started else "failed to open"))
        cameras.append(camera)
    return cameras
