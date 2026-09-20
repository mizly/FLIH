#!/usr/bin/env python
# encoding: utf-8
"""Display both CSI cameras side by side, locally on the Jetson's own screen.

The bench counterpart to `backend/camera_stream.py`: same capture path, but the
frames go to a window here instead of to the web app. Use it to check focus,
framing and exposure without involving the network.

    python3 test_camera_csi_dual.py
    python3 test_camera_csi_dual.py --rectify
    python3 test_camera_csi_dual.py --width 1920 --height 1080 --fps 30

`--rectify` shows the frames the way the video link publishes them: reprojected onto
the simulator's camera model, black down the sides where the lens does not reach as
far as the sim does. Use the raw view to set focus and exposure, and the rectified
one to check aim and framing, since that is the view a sim-trained policy would get.

Press q or ESC to quit.
"""
import argparse
import os
import sys

import cv2 as cv
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "backend"))

import camera_geometry as geom  # noqa: E402  (needs the path above)
from csi_camera import CsiCamera  # noqa: E402  (needs the path above)


def placeholder(width, height, text):
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
    parser.add_argument("--width", type=int, default=geom.CAPTURE_WIDTH)
    parser.add_argument("--height", type=int, default=geom.CAPTURE_HEIGHT)
    parser.add_argument("--fps", type=int, default=geom.CAPTURE_FPS)
    parser.add_argument("--rectify", action="store_true",
                        help="show the sim's camera model instead of the raw lens")
    parser.add_argument("--flip-method", type=int, default=0,
                        help="nvvidconv flip-method, 0=none 2=180deg")
    parser.add_argument("--display-width", type=int, default=1600,
                        help="width of the combined window (0 = native)")
    args = parser.parse_args()

    cameras = []
    for sensor_id in args.sensors:
        camera = CsiCamera(sensor_id, args.width, args.height, args.fps, args.flip_method)
        print("sensor-id %d: %s" % (sensor_id, "open" if camera.start() else "failed to open"))
        cameras.append(camera)

    if not any(camera.running for camera in cameras):
        print("No CSI cameras opened. Check `gst-launch-1.0 nvarguscamerasrc sensor-id=0 "
              "num-buffers=1 ! fakesink` and that a camera device-tree overlay is enabled.")
        return 1

    rectifiers = {}
    if args.rectify:
        for camera in cameras:
            rectifiers[camera.sensor_id] = geom.Rectifier(
                camera.sensor_id, args.width, args.height,
                geom.RECT_WIDTH, geom.RECT_HEIGHT)
        print(geom.coverage_report([camera.sensor_id for camera in cameras]))

    pane_width, pane_height = ((geom.RECT_WIDTH, geom.RECT_HEIGHT) if args.rectify
                               else (args.width, args.height))

    window = "CSI dual"
    cv.namedWindow(window, cv.WINDOW_AUTOSIZE)

    try:
        while True:
            panes = []
            for camera in cameras:
                frame, _, fps = camera.read()
                if frame is None:
                    # Must match the live panes or hconcat refuses: rectified frames
                    # are not the capture size.
                    panes.append(placeholder(pane_width, pane_height,
                                             "sensor %d: no signal" % camera.sensor_id))
                else:
                    rectifier = rectifiers.get(camera.sensor_id)
                    if rectifier is not None:
                        frame = rectifier(frame)
                    panes.append(label(frame, "sensor %d  FPS: %d%s"
                                       % (camera.sensor_id, int(fps),
                                          "  sim view" if rectifier is not None else "")))

            combined = cv.hconcat(panes)
            if args.display_width and combined.shape[1] > args.display_width:
                scale = args.display_width / float(combined.shape[1])
                combined = cv.resize(combined, None, fx=scale, fy=scale, interpolation=cv.INTER_AREA)

            cv.imshow(window, combined)
            if (cv.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
            if cv.getWindowProperty(window, cv.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        for camera in cameras:
            camera.release()
        cv.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
