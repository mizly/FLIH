#!/usr/bin/env python
# encoding: utf-8
"""Display both CSI cameras side by side.

Same nvarguscamerasrc pipeline as test_camera_csi.py, but one per sensor and
each read on its own thread so a stalled camera can't block the other.

    python3 test_camera_csi_dual.py
    python3 test_camera_csi_dual.py --width 1920 --height 1080 --fps 30

Press q or ESC to quit.
"""
import argparse
import threading
import time

import cv2 as cv


def gst_pipeline(sensor_id, width, height, fps, flip_method):
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
    """Grabs frames in the background so the newest one is always ready."""

    def __init__(self, sensor_id, width, height, fps, flip_method):
        self.sensor_id = sensor_id
        self.capture = cv.VideoCapture(
            gst_pipeline(sensor_id, width, height, fps, flip_method), cv.CAP_GSTREAMER
        )
        self.frame = None
        self.fps = 0.0
        self.lock = threading.Lock()
        self.running = False
        self.thread = None

    def is_opened(self):
        return self.capture.isOpened()

    def start(self):
        if not self.is_opened():
            return False
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return True

    def _loop(self):
        last = time.time()
        while self.running:
            ret, frame = self.capture.read()
            if not ret:
                # Argus dropped out; stop feeding stale frames.
                self.running = False
                break
            now = time.time()
            dt = now - last
            last = now
            with self.lock:
                self.frame = frame
                if dt > 0:
                    self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt) if self.fps else 1.0 / dt

    def read(self):
        with self.lock:
            if self.frame is None:
                return None, self.fps
            return self.frame.copy(), self.fps

    def release(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.capture.release()


def placeholder(width, height, text):
    import numpy as np

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    cv.putText(canvas, text, (20, height // 2), cv.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    return canvas


def label(frame, text):
    cv.putText(frame, text, (20, 30), cv.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sensors", type=int, nargs=2, default=[0, 1],
                        help="sensor-id of each CSI port (default: 0 1)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--flip-method", type=int, default=0,
                        help="nvvidconv flip-method, 0=none 2=180deg")
    parser.add_argument("--display-width", type=int, default=1600,
                        help="width of the combined window (0 = native)")
    args = parser.parse_args()

    cameras = []
    for sensor_id in args.sensors:
        cam = CsiCamera(sensor_id, args.width, args.height, args.fps, args.flip_method)
        if not cam.start():
            print("sensor-id %d: failed to open" % sensor_id)
        else:
            print("sensor-id %d: open" % sensor_id)
        cameras.append(cam)

    if not any(cam.is_opened() for cam in cameras):
        print("No CSI cameras opened. Check `gst-launch-1.0 nvarguscamerasrc sensor-id=0 "
              "num-buffers=1 ! fakesink` and that a camera device-tree overlay is enabled.")
        return 1

    window = "CSI dual"
    cv.namedWindow(window, cv.WINDOW_AUTOSIZE)

    try:
        while True:
            panes = []
            for cam in cameras:
                frame, fps = cam.read()
                if frame is None:
                    frame = placeholder(args.width, args.height, "sensor %d: no signal" % cam.sensor_id)
                    panes.append(frame)
                else:
                    panes.append(label(frame, "sensor %d  FPS: %d" % (cam.sensor_id, int(fps))))

            combined = cv.hconcat(panes)
            if args.display_width and combined.shape[1] > args.display_width:
                scale = args.display_width / float(combined.shape[1])
                combined = cv.resize(combined, None, fx=scale, fy=scale, interpolation=cv.INTER_AREA)

            cv.imshow(window, combined)
            key = cv.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if cv.getWindowProperty(window, cv.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        for cam in cameras:
            cam.release()
        cv.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
