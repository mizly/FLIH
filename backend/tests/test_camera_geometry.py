"""Run: python -m unittest discover -s backend/tests -p 'test_*.py' -v

Pins the mapping from the robot's cameras onto the simulator's camera model.

The end-to-end test builds a synthetic capture frame with OpenCV's *forward*
distortion model (cv.projectPoints), rectifies it, and checks each feature lands
where fly-gym's pinhole says it should. That matters because the rectifier is built
from cv.initUndistortRectifyMap, which is the inverse of the same model: checking it
against itself would pass no matter which intrinsics went in.

The rest of the file guards the constants copied out of fly-gym. They are copied
rather than imported because fly-gym is a standalone paper-release repo and is not
importable from here without mujoco and torch, so the test reads its source instead.
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import cv2 as cv
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import camera_geometry as geom  # noqa: E402  (needs the path above)

FLY_GYM = BACKEND.parent / "fly-gym"

# A plausible IMX219-77 with real barrel distortion, so rectification has something
# to undo. Focal length is the nominal full-array value.
FOCAL = 1358.7
DISTORTION = [-0.283, 0.081, 0.0004, -0.0007, -0.0102]


def fake_calibration(directory, sensor_id):
    K = [[FOCAL, 0.0, (geom.CAPTURE_WIDTH - 1) / 2.0],
         [0.0, FOCAL, (geom.CAPTURE_HEIGHT - 1) / 2.0],
         [0.0, 0.0, 1.0]]
    record = {
        "sensor_id": sensor_id,
        "capture_width": geom.CAPTURE_WIDTH,
        "capture_height": geom.CAPTURE_HEIGHT,
        "camera_matrix": K,
        "distortion": DISTORTION,
        "rms_reprojection_px": 0.21,
        "views": 24,
    }
    with open(os.path.join(directory, "camera_%d.json" % sensor_id), "w") as handle:
        json.dump(record, handle)
    return np.array(K), np.array(DISTORTION)


class CalibratedRectificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.original = geom.CALIBRATION_DIR
        geom.CALIBRATION_DIR = self.directory
        self.addCleanup(setattr, geom, "CALIBRATION_DIR", self.original)
        self.K, self.dist = fake_calibration(self.directory, 1)

    def test_rectified_features_land_where_the_sim_puts_them(self):
        """A ray at a known angle must hit the same pixel on the robot as in the sim."""
        rectifier = geom.Rectifier(1)
        target = rectifier.target
        focal, cx, cy = target[0, 0], target[0, 2], target[1, 2]

        # Rays spread over the part of the sim frame the lens actually covers, kept
        # off the very edge so the drawn disc is whole in both images.
        cover_h, cover_v = rectifier.coverage
        tan_h, tan_v = geom.sim_tan_half()
        rays, expected = [], []
        for fx in (-0.8, -0.4, 0.0, 0.4, 0.8):
            for fy in (-0.8, -0.4, 0.0, 0.4, 0.8):
                x = fx * tan_h * min(1.0, cover_h) * 0.9
                y = fy * tan_v * min(1.0, cover_v) * 0.9
                rays.append([x, y, 1.0])
                expected.append((cx + focal * x, cy + focal * y))

        # Forward model: where each ray lands on the real, distorted sensor.
        projected, _ = cv.projectPoints(
            np.array(rays, dtype=np.float64), np.zeros(3), np.zeros(3), self.K, self.dist)
        capture = np.zeros((geom.CAPTURE_HEIGHT, geom.CAPTURE_WIDTH, 3), dtype=np.uint8)
        for point in projected.reshape(-1, 2):
            cv.circle(capture, (int(round(point[0])), int(round(point[1]))), 7, (255, 255, 255), -1)

        rectified = rectifier(capture)
        gray = cv.cvtColor(rectified, cv.COLOR_BGR2GRAY)
        count, _, stats, centroids = cv.connectedComponentsWithStats((gray > 96).astype(np.uint8))
        found = [tuple(centroids[i]) for i in range(1, count) if stats[i, cv.CC_STAT_AREA] > 12]
        self.assertEqual(len(found), len(rays), "every feature should survive rectification")

        for want in expected:
            nearest = min(found, key=lambda got: math.hypot(got[0] - want[0], got[1] - want[1]))
            offset = math.hypot(nearest[0] - want[0], nearest[1] - want[1])
            self.assertLess(offset, 1.5, "feature for ray at %.1f,%.1f landed %.2f px away"
                                         % (want[0], want[1], offset))

    def test_uncorrected_capture_would_be_wrong(self):
        """The test above is only meaningful if the distortion actually displaces things."""
        tan_h, _ = geom.sim_tan_half()
        edge = np.array([[0.9 * tan_h * 0.62, 0.0, 1.0]], dtype=np.float64)
        distorted, _ = cv.projectPoints(edge, np.zeros(3), np.zeros(3), self.K, self.dist)
        undistorted, _ = cv.projectPoints(edge, np.zeros(3), np.zeros(3), self.K, np.zeros(5))
        shift = abs(distorted.ravel()[0] - undistorted.ravel()[0])
        self.assertGreater(shift, 20.0, "this lens model barely distorts; the test proves little")

    def test_calibration_is_used_and_rescaled(self):
        K, dist, calibrated = geom.intrinsics_for(1)
        self.assertTrue(calibrated)
        np.testing.assert_allclose(K, self.K)
        np.testing.assert_allclose(dist, self.dist)

        half, _, _ = geom.intrinsics_for(1, geom.CAPTURE_WIDTH // 2, geom.CAPTURE_HEIGHT // 2)
        self.assertAlmostEqual(half[0, 0], FOCAL / 2, places=6)
        # Pixel centres, not corners: cx maps through (cx + 0.5) * s - 0.5.
        self.assertAlmostEqual(half[0, 2], (self.K[0, 2] + 0.5) / 2 - 0.5, places=6)

    def test_a_cropped_mode_calibration_is_refused(self):
        """1280x720 is a different crop of the sensor, not a resize of this one."""
        with self.assertRaises(ValueError):
            geom.intrinsics_for(1, 1280, 720)

    def test_missing_calibration_falls_back_and_says_so(self):
        _, dist, calibrated = geom.intrinsics_for(0)
        self.assertFalse(calibrated)
        np.testing.assert_allclose(dist, np.zeros(5))


class SimAgreementTests(unittest.TestCase):
    def test_sim_field_of_view(self):
        hfov, vfov = geom.sim_fov_deg()
        self.assertAlmostEqual(hfov, 69.47, places=2)
        self.assertAlmostEqual(vfov, 42.61, places=2)

    def test_intermediate_size_matches_the_sim(self):
        self.assertEqual(geom.sim_intermediate_size(128), (240, 135))
        self.assertEqual(geom.sim_intermediate_size(64), (128, 72))

    def test_network_input_takes_the_sim_final_step(self):
        """From the sim's intermediate onward, both paths must run identical code."""
        rng = np.random.default_rng(0)
        intermediate = rng.integers(0, 256, (135, 240, 3), dtype=np.uint8)
        np.testing.assert_array_equal(
            geom.to_network_input(intermediate, 128),
            cv.resize(intermediate, (128, 128), interpolation=cv.INTER_AREA))

    def test_capture_mode_contains_the_sim_vertical_fov(self):
        """The reason the capture mode is 4:3. Any 16:9 mode is a vertical crop."""
        _, cover_v = geom.coverage(*geom.nominal_intrinsics()[:2])
        self.assertGreaterEqual(cover_v, 1.0)

    def test_horizontal_shortfall_is_reported_not_hidden(self):
        """The stock lens cannot reach the sim's 69.47 deg. That must stay visible."""
        cover_h, _ = geom.coverage(*geom.nominal_intrinsics()[:2])
        self.assertLess(cover_h, 1.0)
        self.assertIn("SHORT", geom.coverage_report([1]))


@unittest.skipUnless(FLY_GYM.is_dir(), "fly-gym not checked out")
class SimConstantsStillMatchFlyGymTests(unittest.TestCase):
    """fly-gym is the reference the robot is rectified onto, so it must not drift.

    If one of these fails, fly-gym's camera changed and every trained checkpoint
    changed with it. Update the constants in camera_geometry.py to match, and expect
    to recalibrate nothing but to retrain everything.
    """

    def test_fovy(self):
        xml = (FLY_GYM / "environment" / "robot_geometry.xml").read_text()
        self.assertEqual(xml.count('fovy="%s"' % geom.SIM_FOVY_DEG), 2)

    def test_aspect(self):
        config = (FLY_GYM / "robot_config.py").read_text()
        self.assertIn("CAMERA_ASPECT = %d / %d" % (geom.SIM_ASPECT_NUM, geom.SIM_ASPECT_DEN),
                      config)

    def test_render_then_squash_chain(self):
        env = (FLY_GYM / "environment" / "mujoco_two_cam_env_random_obstacles.py").read_text()
        self.assertIn("self.camera_height = max(%d, int(math.ceil(self.H / %d)) * %d)"
                      % (geom.SIM_ASPECT_DEN, geom.SIM_ASPECT_DEN, geom.SIM_ASPECT_DEN), env)
        self.assertIn("self.camera_width = self.camera_height * %d // %d"
                      % (geom.SIM_ASPECT_NUM, geom.SIM_ASPECT_DEN), env)
        self.assertIn("interpolation=cv2.INTER_AREA", env)


if __name__ == "__main__":
    unittest.main()
