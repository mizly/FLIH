"""Map the robot's cameras onto the simulator's camera model.

fly-gym renders each eye as an ideal pinhole: 42.61 deg vertical over a 16:9 frame
(69.47 deg horizontal), square pixels, principal point dead centre, no distortion
(`fly-gym/environment/robot_geometry.xml`, `fly-gym/robot_config.py`). A raw IMX219
frame is none of those, so a policy trained in the sim meets a different scene
geometry on the robot than it ever saw in training.

This module is the adapter. It rectifies a capture frame onto the sim's exact
pinhole -- so a normalised coordinate in the rectified frame names the same ray it
would name in the sim -- and then resamples it through the same two INTER_AREA steps
the sim uses, so the pixel grid matches as well as the geometry.

Two things it deliberately does not do.

**It does not change the sim.** The published FLYNN numbers are tied to the sim's
current frustum, so the sim is the fixed reference and the robot is what moves.

**It cannot invent horizontal field of view.** The stock IMX219-77 lens covers about
62.2 deg horizontally; the sim wants 69.47. Rectification crops angle, it never adds
it, so the outer few percent of each side of the rectified frame has no sensor behind
it and comes back black. `coverage_report()` prints exactly how much. Closing that
gap takes a wider lens, not a code change.

Run `python3 backend/camera_geometry.py` for the current numbers.
"""

import json
import math
import os

import cv2 as cv
import numpy as np

# --- The sim's camera, copied from fly-gym. The drift guard for these is
# --- backend/tests/test_camera_geometry.py, which reads them back out of fly-gym.
SIM_FOVY_DEG = 42.61
SIM_ASPECT_NUM = 16
SIM_ASPECT_DEN = 9
SIM_NET_INPUT = 128

# --- Capture. 1640x1232 is the 2x2-binned full sensor array: the only mode family
# --- whose vertical coverage (~48.8 deg) contains the sim's 42.61. Every 16:9 mode
# --- is a vertical crop of this one and falls short, so this is not a preference.
CAPTURE_WIDTH = 1640
CAPTURE_HEIGHT = 1232
CAPTURE_FPS = 30

# --- Working size for the rectified pinhole. 4x the sim's 240x135 intermediate, so
# --- the downscale to it is an exact integer factor.
RECT_WIDTH = 960
RECT_HEIGHT = 540

# --- Nominal IMX219-77 full-array field of view, used until a real calibration
# --- exists. Vendor spec, not a measurement: every number derived from it is
# --- provisional and `calibrated` is False wherever it is in play.
NOMINAL_HFOV_DEG = 62.2
NOMINAL_VFOV_DEG = 48.8

CALIBRATION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calibration")


def sim_tan_half():
    """(horizontal, vertical) tangents of the sim's half-angles."""
    tan_v = math.tan(math.radians(SIM_FOVY_DEG) / 2.0)
    return tan_v * SIM_ASPECT_NUM / SIM_ASPECT_DEN, tan_v


def sim_fov_deg():
    """(horizontal, vertical) field of view of the sim camera, in degrees."""
    tan_h, tan_v = sim_tan_half()
    return 2 * math.degrees(math.atan(tan_h)), 2 * math.degrees(math.atan(tan_v))


def sim_intermediate_size(net_input=SIM_NET_INPUT):
    """The size fly-gym renders at before squashing to the square network input.

    Mirrors MuJoCoTwoCamEnv.__init__ (environment/mujoco_two_cam_env_random_obstacles.py):
    round the network height up to a whole number of aspect units, then widen. The
    robot has to land on the same intermediate or the two resample chains diverge.
    """
    height = max(SIM_ASPECT_DEN, int(math.ceil(net_input / SIM_ASPECT_DEN)) * SIM_ASPECT_DEN)
    return height * SIM_ASPECT_NUM // SIM_ASPECT_DEN, height


def sim_pinhole(width=RECT_WIDTH, height=RECT_HEIGHT):
    """The sim's camera as an OpenCV intrinsic matrix at the given output size.

    Square pixels and a centred principal point are not choices: MuJoCo cannot
    express anything else, so the rectification target cannot either.
    """
    focal = (height / 2.0) / math.tan(math.radians(SIM_FOVY_DEG) / 2.0)
    return np.array([[focal, 0.0, (width - 1) / 2.0],
                     [0.0, focal, (height - 1) / 2.0],
                     [0.0, 0.0, 1.0]], dtype=np.float64)


def nominal_intrinsics(width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT):
    """Pinhole intrinsics implied by the IMX219-77 spec sheet, zero distortion.

    A placeholder with the right shape, so the pipeline runs before anyone has
    stood in front of a checkerboard. It models no distortion at all, which is the
    one thing a real lens is guaranteed to have.
    """
    fx = (width / 2.0) / math.tan(math.radians(NOMINAL_HFOV_DEG) / 2.0)
    fy = (height / 2.0) / math.tan(math.radians(NOMINAL_VFOV_DEG) / 2.0)
    focal = (fx + fy) / 2.0  # square pixels; the two agree to 0.04% at nominal
    return np.array([[focal, 0.0, (width - 1) / 2.0],
                     [0.0, focal, (height - 1) / 2.0],
                     [0.0, 0.0, 1.0]], dtype=np.float64), np.zeros(5, dtype=np.float64)


def calibration_path(sensor_id):
    return os.path.join(CALIBRATION_DIR, "camera_%d.json" % sensor_id)


def load_calibration(sensor_id):
    """A sensor's measured intrinsics, or None if it has never been calibrated."""
    path = calibration_path(sensor_id)
    if not os.path.isfile(path):
        return None
    with open(path) as handle:
        record = json.load(handle)
    for key in ("camera_matrix", "distortion", "capture_width", "capture_height"):
        if key not in record:
            raise ValueError("%s is missing %r" % (path, key))
    return record


def intrinsics_for(sensor_id, width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT):
    """(K, dist, calibrated) for one sensor at the given capture size.

    A calibration taken at another size is rescaled rather than refused: the modes
    that share the full array differ only by a resampling factor. A calibration from
    a *cropped* mode is not rescalable that way, which is why calibrate_cameras.py
    records the capture size it used and this warns rather than silently converting.
    """
    record = load_calibration(sensor_id)
    if record is None:
        K, dist = nominal_intrinsics(width, height)
        return K, dist, False

    K = np.array(record["camera_matrix"], dtype=np.float64)
    dist = np.array(record["distortion"], dtype=np.float64).ravel()
    source = (int(record["capture_width"]), int(record["capture_height"]))
    if source != (width, height):
        scale = width / float(source[0])
        if abs(height / float(source[1]) - scale) > 1e-3:
            raise ValueError(
                "calibration for sensor %d was taken at %dx%d, which is not a uniform "
                "rescale of %dx%d. Recalibrate at the capture mode you deploy."
                % (sensor_id, source[0], source[1], width, height))
        K = scale_intrinsics(K, scale)
    return K, dist, True


def scale_intrinsics(K, scale):
    """Rescale intrinsics for a resized image, honouring OpenCV's pixel centres.

    A pixel centre at integer x becomes (x + 0.5) * scale - 0.5, so the principal
    point does not simply multiply. Half a pixel is small, and it is also exactly
    the kind of thing that turns an exact mapping into an almost-exact one.
    """
    scaled = K.copy()
    scaled[0, 0] *= scale
    scaled[1, 1] *= scale
    scaled[0, 2] = (K[0, 2] + 0.5) * scale - 0.5
    scaled[1, 2] = (K[1, 2] + 0.5) * scale - 0.5
    return scaled


def lens_half_angles(K, dist, width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT):
    """(horizontal, vertical) half-angle tangents the lens actually reaches.

    Measured by undistorting the midpoint of each frame edge, which is where the
    usable rectangle is widest; the corners reach further but are the first thing
    a rectification to a centred rectangle throws away.
    """
    edges = np.array([[[0.0, (height - 1) / 2.0]],
                      [[width - 1.0, (height - 1) / 2.0]],
                      [[(width - 1) / 2.0, 0.0]],
                      [[(width - 1) / 2.0, height - 1.0]]], dtype=np.float64)
    normalised = cv.undistortPoints(edges, K, dist).reshape(-1, 2)
    tan_h = min(abs(normalised[0, 0]), abs(normalised[1, 0]))
    tan_v = min(abs(normalised[2, 1]), abs(normalised[3, 1]))
    return tan_h, tan_v


def coverage(K, dist, width=CAPTURE_WIDTH, height=CAPTURE_HEIGHT):
    """How much of the sim's frame this lens can actually fill.

    Returns fractions of the sim's half-width and half-height that have sensor
    behind them. >= 1.0 means fully covered; below that is the black margin.
    """
    want_h, want_v = sim_tan_half()
    have_h, have_v = lens_half_angles(K, dist, width, height)
    return have_h / want_h, have_v / want_v


class Rectifier:
    """Turns one camera's capture frames into the sim's pinhole.

    Built once per camera and then called per frame. The maps are fixed, so the
    per-frame cost is a single remap.
    """

    def __init__(self, sensor_id, capture_width=CAPTURE_WIDTH, capture_height=CAPTURE_HEIGHT,
                 width=RECT_WIDTH, height=RECT_HEIGHT):
        self.sensor_id = sensor_id
        self.capture_size = (capture_width, capture_height)
        self.size = (width, height)
        self.K, self.dist, self.calibrated = intrinsics_for(sensor_id, capture_width, capture_height)
        self.target = sim_pinhole(width, height)
        self.coverage = coverage(self.K, self.dist, capture_width, capture_height)

        # Remapping straight from the capture grid to a much coarser output samples
        # single source pixels and aliases. Pre-shrinking with INTER_AREA first puts
        # the source near the output's own scale, so the remap runs about 1:1 and the
        # downscale is the properly averaged one.
        shrink = min(1.0, self.target[0, 0] / self.K[0, 0])
        self.prescale_size = (max(1, int(round(capture_width * shrink))),
                              max(1, int(round(capture_height * shrink))))
        source = scale_intrinsics(self.K, self.prescale_size[0] / float(capture_width))

        self.map1, self.map2 = cv.initUndistortRectifyMap(
            source, self.dist, None, self.target, self.size, cv.CV_16SC2)

    def __call__(self, frame):
        """One capture frame -> one sim-geometry frame. Black where the lens cannot see."""
        if (frame.shape[1], frame.shape[0]) != self.capture_size:
            raise ValueError("expected a %dx%d frame, got %dx%d"
                             % (self.capture_size + (frame.shape[1], frame.shape[0])))
        if self.prescale_size != self.capture_size:
            frame = cv.resize(frame, self.prescale_size, interpolation=cv.INTER_AREA)
        return cv.remap(frame, self.map1, self.map2, cv.INTER_LINEAR,
                        borderMode=cv.BORDER_CONSTANT, borderValue=(0, 0, 0))


def to_network_input(rectified, net_input=SIM_NET_INPUT):
    """Resample a rectified frame exactly the way fly-gym resamples a render.

    The sim renders at the 16:9 intermediate and then squashes to a square with one
    INTER_AREA (`_render_camera`). The robot arrives at that intermediate by
    downscaling instead of rendering, then takes the identical final step.
    """
    intermediate = sim_intermediate_size(net_input)
    if (rectified.shape[1], rectified.shape[0]) != intermediate:
        rectified = cv.resize(rectified, intermediate, interpolation=cv.INTER_AREA)
    return cv.resize(rectified, (net_input, net_input), interpolation=cv.INTER_AREA)


def coverage_report(sensor_ids=(1, 0)):
    """Human-readable status for every camera. Printed by __main__ and the setup docs."""
    hfov, vfov = sim_fov_deg()
    lines = ["sim camera      %.2f deg H x %.2f deg V, %d:%d, %dx%d -> %dx%d"
             % (hfov, vfov, SIM_ASPECT_NUM, SIM_ASPECT_DEN,
                sim_intermediate_size()[0], sim_intermediate_size()[1],
                SIM_NET_INPUT, SIM_NET_INPUT),
             "capture         %dx%d @ %d fps (full array, 2x2 binned)"
             % (CAPTURE_WIDTH, CAPTURE_HEIGHT, CAPTURE_FPS),
             "rectified to    %dx%d" % (RECT_WIDTH, RECT_HEIGHT),
             ""]
    for sensor_id in sensor_ids:
        rectifier = Rectifier(sensor_id)
        cover_h, cover_v = rectifier.coverage
        have_h, have_v = lens_half_angles(rectifier.K, rectifier.dist)
        lines.append("sensor-id %d (%s)  %s" % (
            sensor_id, "left" if sensor_id == 1 else "right",
            "calibrated" if rectifier.calibrated else "NOMINAL - run calibrate_cameras.py"))
        lines.append("    lens reaches  %.2f deg H x %.2f deg V"
                     % (2 * math.degrees(math.atan(have_h)), 2 * math.degrees(math.atan(have_v))))
        for axis, cover in (("horizontal", cover_h), ("vertical", cover_v)):
            if cover >= 1.0:
                lines.append("    %-12s fully covered (%.1f%% of the sim frame in view)"
                             % (axis, 100.0))
            else:
                lines.append("    %-12s SHORT: %.1f%% covered, %.2f deg missing per side"
                             % (axis, 100.0 * cover,
                                (2 * math.degrees(math.atan(sim_tan_half()[0 if axis == "horizontal" else 1]))
                                 - 2 * math.degrees(math.atan(have_h if axis == "horizontal" else have_v))) / 2))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(coverage_report())
