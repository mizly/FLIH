#!/usr/bin/env python3
"""Measure what the robot's cameras actually see, so camera_geometry can undo it.

Everything in camera_geometry.py is provisional until this has run: without a
calibration it falls back to the IMX219-77 spec sheet, which models zero lens
distortion -- the one thing a real lens definitely has.

Hold a printed checkerboard in front of both cameras and work it around the frame,
including the corners, where distortion is largest and where a calibration that only
saw the middle of the image will be worst. Twenty-odd views per camera at a range of
distances and tilts is plenty; more near-identical views add nothing.

    python3 backend/calibrate_cameras.py                  # live, SPACE to grab
    python3 backend/calibrate_cameras.py --no-preview     # headless, grabs on a timer
    python3 backend/calibrate_cameras.py --from-dir shots # re-solve saved images

Writes backend/calibration/camera_<id>.json per camera, plus stereo.json for the
pair. Commit them: they describe these specific camera modules, and a swapped module
is a recalibration.

The capture mode matters. Sensor modes crop differently, so a calibration is only
valid for the mode it was taken at; this uses camera_geometry's deployment mode by
default and records the size it used.
"""

import argparse
import glob
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import cv2 as cv
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import camera_geometry as geom
from csi_camera import CsiCamera

FIND_FLAGS = cv.CALIB_CB_ADAPTIVE_THRESH | cv.CALIB_CB_NORMALIZE_IMAGE | cv.CALIB_CB_FAST_CHECK
REFINE = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sensors", type=int, nargs=2, default=[1, 0],
                        help="CSI sensor ids, left then right (default: 1 0)")
    parser.add_argument("--board", type=int, nargs=2, default=[9, 6],
                        metavar=("COLS", "ROWS"), help="inner corners (default: 9 6)")
    parser.add_argument("--square-mm", type=float, default=25.0,
                        help="checkerboard square size in mm (default: 25)")
    parser.add_argument("--views", type=int, default=24,
                        help="views to collect per camera (default: 24)")
    parser.add_argument("--capture-width", type=int, default=geom.CAPTURE_WIDTH)
    parser.add_argument("--capture-height", type=int, default=geom.CAPTURE_HEIGHT)
    parser.add_argument("--capture-fps", type=int, default=geom.CAPTURE_FPS)
    parser.add_argument("--no-preview", action="store_true",
                        help="no window; grab whenever the board is found, on a timer")
    parser.add_argument("--interval", type=float, default=1.5,
                        help="seconds between headless grabs (default: 1.5)")
    parser.add_argument("--save-dir", default=None,
                        help="also write the raw frames here, for re-solving later")
    parser.add_argument("--from-dir", default=None,
                        help="solve from <dir>/<sensor id>_*.png instead of the cameras")
    parser.add_argument("--out-dir", default=geom.CALIBRATION_DIR)
    return parser.parse_args(argv)


def object_points(board, square_mm):
    """One board's corners in board coordinates, in metres."""
    grid = np.zeros((board[0] * board[1], 3), dtype=np.float32)
    grid[:, :2] = np.mgrid[0:board[0], 0:board[1]].T.reshape(-1, 2)
    return grid * (square_mm / 1000.0)


def find_corners(gray, board):
    found, corners = cv.findChessboardCorners(gray, tuple(board), FIND_FLAGS)
    if not found:
        return None
    return cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), REFINE)


def collect_from_cameras(args):
    """Drive both cameras until enough views are in hand. Returns corners per sensor."""
    cameras = [CsiCamera(sensor_id, args.capture_width, args.capture_height,
                         args.capture_fps) for sensor_id in args.sensors]
    for camera, sensor_id in zip(cameras, args.sensors):
        if not camera.start():
            for opened in cameras:
                opened.release()
            raise SystemExit("sensor-id %d did not open. Check the device-tree overlay." % sensor_id)

    corners = {sensor_id: [] for sensor_id in args.sensors}
    pairs = []
    size = (args.capture_width, args.capture_height)
    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)

    print("Move the board around the frame, corners included. "
          + ("grabbing every %.1fs" % args.interval if args.no_preview
             else "SPACE to grab, q when done."))
    next_grab = time.monotonic() + args.interval
    try:
        while min(len(v) for v in corners.values()) < args.views:
            frames, found = [], []
            for camera in cameras:
                frame, _, _ = camera.read()
                frames.append(frame)
                if frame is None:
                    found.append(None)
                    continue
                found.append(find_corners(cv.cvtColor(frame, cv.COLOR_BGR2GRAY), args.board))

            grab = False
            if args.no_preview:
                grab = time.monotonic() >= next_grab
            else:
                preview = []
                for frame, corner in zip(frames, found):
                    if frame is None:
                        continue
                    shown = frame.copy()
                    if corner is not None:
                        cv.drawChessboardCorners(shown, tuple(args.board), corner, True)
                    preview.append(cv.resize(shown, (640, 480), interpolation=cv.INTER_AREA))
                if preview:
                    banner = "  ".join("id %d: %d/%d" % (s, len(corners[s]), args.views)
                                       for s in args.sensors)
                    canvas = np.hstack(preview)
                    cv.putText(canvas, banner, (16, 32), cv.FONT_HERSHEY_SIMPLEX, 0.8,
                               (0, 0, 255), 2)
                    cv.imshow("calibration", canvas)
                key = cv.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                grab = key == ord(" ")

            if not grab:
                continue
            next_grab = time.monotonic() + args.interval
            taken = []
            for sensor_id, frame, corner in zip(args.sensors, frames, found):
                if corner is None:
                    continue
                corners[sensor_id].append(corner)
                taken.append(sensor_id)
                if args.save_dir and frame is not None:
                    cv.imwrite(os.path.join(args.save_dir, "%d_%03d.png"
                                            % (sensor_id, len(corners[sensor_id]))), frame)
            # Only a view both cameras saw at the same instant constrains the pose
            # between them, so the stereo set is built separately from the two
            # intrinsic sets rather than assumed to be the same views.
            if len(taken) == len(args.sensors):
                pairs.append(tuple(corners[s][-1] for s in args.sensors))
            if taken:
                print("  grabbed: " + "  ".join("id %d: %d/%d" % (s, len(corners[s]), args.views)
                                                for s in args.sensors))
            else:
                print("  no board found in either camera")
    finally:
        for camera in cameras:
            camera.release()
        if not args.no_preview:
            cv.destroyAllWindows()
    return corners, pairs, size


def collect_from_dir(args):
    """Re-solve from saved frames, so a calibration can be redone without the robot."""
    corners = {sensor_id: [] for sensor_id in args.sensors}
    per_name = {sensor_id: [] for sensor_id in args.sensors}
    size = None
    for sensor_id in args.sensors:
        for path in sorted(glob.glob(os.path.join(args.from_dir, "%d_*.png" % sensor_id))):
            image = cv.imread(path)
            if image is None:
                continue
            size = (image.shape[1], image.shape[0])
            corner = find_corners(cv.cvtColor(image, cv.COLOR_BGR2GRAY), args.board)
            if corner is None:
                print("  no board in %s" % os.path.basename(path))
                continue
            corners[sensor_id].append(corner)
            per_name[sensor_id].append(os.path.basename(path).split("_", 1)[1])
    if size is None:
        raise SystemExit("no readable images in %s" % args.from_dir)
    shared = sorted(set(per_name[args.sensors[0]]) & set(per_name[args.sensors[1]]))
    pairs = [tuple(corners[s][per_name[s].index(name)] for s in args.sensors) for name in shared]
    return corners, pairs, size


def solve_one(corner_sets, board, square_mm, size):
    grid = object_points(board, square_mm)
    objects = [grid] * len(corner_sets)
    rms, K, dist, _, _ = cv.calibrateCamera(objects, corner_sets, size, None, None)
    return rms, K, dist


def main():
    args = parse_args()
    if len(args.sensors) != 2:
        raise SystemExit("this expects exactly two sensors")

    if args.from_dir:
        corners, pairs, size = collect_from_dir(args)
    else:
        corners, pairs, size = collect_from_cameras(args)

    if size != (geom.CAPTURE_WIDTH, geom.CAPTURE_HEIGHT):
        print("WARNING: calibrating at %dx%d but camera_geometry deploys %dx%d. "
              "Sensor modes crop differently; calibrate at the mode you run."
              % (size[0], size[1], geom.CAPTURE_WIDTH, geom.CAPTURE_HEIGHT), file=sys.stderr)

    os.makedirs(args.out_dir, exist_ok=True)
    solved = {}
    for sensor_id in args.sensors:
        views = corners[sensor_id]
        if len(views) < 8:
            print("sensor-id %d: only %d usable views, refusing to fit. "
                  "Below about 10 the distortion terms are noise." % (sensor_id, len(views)),
                  file=sys.stderr)
            continue
        rms, K, dist = solve_one(views, args.board, args.square_mm, size)
        solved[sensor_id] = (K, dist)
        record = {
            "sensor_id": sensor_id,
            "capture_width": size[0],
            "capture_height": size[1],
            "camera_matrix": K.tolist(),
            "distortion": dist.ravel().tolist(),
            "rms_reprojection_px": rms,
            "views": len(views),
            "board": "%dx%d inner corners @ %.1f mm" % (args.board[0], args.board[1], args.square_mm),
            "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path = os.path.join(args.out_dir, "camera_%d.json" % sensor_id)
        with open(path, "w") as handle:
            json.dump(record, handle, indent=2)
            handle.write("\n")
        hfov = 2 * math.degrees(math.atan((size[0] / 2.0) / K[0, 0]))
        vfov = 2 * math.degrees(math.atan((size[1] / 2.0) / K[1, 1]))
        print("sensor-id %d: rms %.3f px over %d views, %.2f deg H x %.2f deg V -> %s"
              % (sensor_id, rms, len(views), hfov, vfov, path))
        if rms > 1.0:
            print("  rms above 1 px. Usually a mis-measured square size or a board that "
                  "was not flat; the fit is not trustworthy.", file=sys.stderr)

    if len(solved) == 2 and len(pairs) >= 8:
        left, right = args.sensors
        grid = object_points(args.board, args.square_mm)
        rms, _, _, _, _, R, T, _, _ = cv.stereoCalibrate(
            [grid] * len(pairs), [p[0] for p in pairs], [p[1] for p in pairs],
            solved[left][0], solved[left][1], solved[right][0], solved[right][1], size,
            flags=cv.CALIB_FIX_INTRINSIC)
        yaw = math.degrees(math.atan2(-R[2, 0], R[2, 2]))
        record = {
            "left_sensor_id": left,
            "right_sensor_id": right,
            "rotation": R.tolist(),
            "translation_m": T.ravel().tolist(),
            "baseline_m": float(np.linalg.norm(T)),
            "relative_yaw_deg": yaw,
            "rms_reprojection_px": rms,
            "views": len(pairs),
            "calibrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path = os.path.join(args.out_dir, "stereo.json")
        with open(path, "w") as handle:
            json.dump(record, handle, indent=2)
            handle.write("\n")
        print("stereo: rms %.3f px over %d pairs, baseline %.1f mm, %.2f deg between the "
              "cameras -> %s" % (rms, len(pairs), 1000 * record["baseline_m"], yaw, path))
        print("  fly-gym's nominal pair is 70.0 mm apart and 59.46 deg opposed "
              "(2 x 29.73 outward). Those are drawing numbers, this is the robot.")
        print("  Note this is the pose of one camera relative to the other. Where the pair "
              "sits on the chassis -- mount height and pitch -- still has to be measured "
              "against the floor; stereo calibration cannot see the ground.")
    elif len(solved) == 2:
        print("stereo skipped: only %d views had the board in both cameras at once "
              "(need 8)." % len(pairs), file=sys.stderr)

    print()
    print(geom.coverage_report(args.sensors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
