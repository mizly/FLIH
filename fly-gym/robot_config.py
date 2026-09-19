"""Robot configuration in metres/radians; geometry source is robot_geometry.xml."""
from dataclasses import asdict, dataclass
from pathlib import Path
import math
import xml.etree.ElementTree as ET

ROBOT_XML = Path(__file__).parent / "environment" / "robot_geometry.xml"
_root = ET.parse(ROBOT_XML).getroot()
_base = _root.find("worldbody/body")
BASE_HEIGHT = float(_base.get("pos").split()[2])
WHEEL_RADIUS, WHEEL_HALF_WIDTH = map(float, _base.find("body/geom").get("size").split())
_front_left = tuple(map(float, _base.find("body[@name='left_wheel']").get("pos").split()))
_front_right = tuple(map(float, _base.find("body[@name='right_wheel']").get("pos").split()))
_rear_left = tuple(map(float, _base.find("body[@name='rear_left_wheel']").get("pos").split()))
WHEEL_TRACK = abs(_front_left[1] - _front_right[1])
WHEELBASE = abs(_front_left[0] - _rear_left[0])
# Circumscribed footprint includes the wheel radius and half tire width.
ROBOT_RADIUS = math.hypot(WHEELBASE / 2 + WHEEL_RADIUS, WHEEL_TRACK / 2 + WHEEL_HALF_WIDTH)
CAMERA_ASPECT = 16 / 9
LIDAR_FEATURE_BINS = 12
MAX_LINEAR_SPEED = 0.4  # Navigation command ceiling, not the motor's unloaded top speed.
HEADING_GAIN = 0.5  # Heading error (rad) -> commanded yaw rate (rad/s).


@dataclass(frozen=True)
class MotorConfig:
    """Yahboom L-type 520 output-shaft specs at 12 V, variant 51500753846588.

    Source: https://cdn.shopify.com/s/files/1/0066/9686/1780/files/520_encoder_geared_motor_2.jpg
    Published values are not a measured torque-speed curve or PID calibration.
    """
    voltage: float = 12.0
    reduction_ratio: int = 40
    output_rpm: float = 300.0
    speed_tolerance_fraction: float = 0.05
    rated_torque_nm: float = 4.4 * 0.0980665
    stall_torque_nm: float = 10 * 0.0980665
    rated_current_a: float = 0.5
    stall_current_a: float = 4.0
    rated_power_w: float = 6.0
    mass_kg: float = 0.161
    encoder_lines: int = 11
    quadrature_edges: int = 4

    @property
    def max_wheel_speed_rad_s(self):
        return self.output_rpm * 2 * math.pi / 60

    @property
    def encoder_counts_per_wheel_revolution(self):
        return self.encoder_lines * self.reduction_ratio * self.quadrature_edges


MOTOR_CONFIG = MotorConfig()
KINEMATIC_SPEED_AT_NOMINAL_RPM = WHEEL_RADIUS * MOTOR_CONFIG.max_wheel_speed_rad_s


@dataclass(frozen=True)
class LidarConfig:
    """YDLIDAR T-mini Plus 12M (Yahboom variant 52514639020348).

    Manufacturer: https://www.ydlidar.com/products/view/27.html
    4000 samples/s, 6 Hz default (adjustable 6-12 Hz), 0.05-12 m.
    Fixed-size simulation scans approximate samples/s divided by scan rate.

    Angles increase counterclockwise from forward; no duplicate endpoint.
    Missing/out-of-range returns use max_range, too-close hits use min_range.
    """
    sample_rate_hz: int = 4000
    min_range: float = 0.05
    max_range: float = 12.0
    fov_deg: float = 360.0
    rate_hz: float = 6.0

    @property
    def num_rays(self):
        return round(self.sample_rate_hz / self.rate_hz * self.fov_deg / 360)

    def __post_init__(self):
        if not isinstance(self.sample_rate_hz, int) or self.sample_rate_hz <= 0:
            raise ValueError("LiDAR sample rate must be a positive integer")
        if not all(math.isfinite(x) for x in (self.min_range, self.max_range, self.fov_deg, self.rate_hz)):
            raise ValueError("LiDAR settings must be finite")
        if not (0 < self.min_range < self.max_range <= 12 and 0 < self.fov_deg <= 360 and 6 <= self.rate_hz <= 12):
            raise ValueError("Invalid LiDAR ranges, field of view or scan rate")
        if self.num_rays < LIDAR_FEATURE_BINS:
            raise ValueError("LiDAR needs at least 12 rays")


LIDAR_CONFIG = LidarConfig()


def training_robot_metadata():
    return {
        "geometry_xml": ROBOT_XML.read_text(),
        "layout_source": "wheel_positions.png (updated layout)",
        "frame": "x forward, y left, z up; metres",
        "lidar": asdict(LIDAR_CONFIG),
        "lidar_model": "YDLIDAR T-mini Plus 12M; Yahboom variant 52514639020348",
        "lidar_num_rays": LIDAR_CONFIG.num_rays,
        "lidar_feature_bins": LIDAR_FEATURE_BINS,
        "lidar_feature_convention": "CCW angles from forward; sectors from -pi to pi; 1 - nearest/max_range",
        "max_linear_speed_m_s": MAX_LINEAR_SPEED,
        "heading_gain": HEADING_GAIN,
        "camera_native_aspect": CAMERA_ASPECT,
        "camera_centers_m": {
            "left": [0.103, 0.035, 0.175],
            "right": [0.103, -0.035, 0.175],
        },
        "camera_horizontal_fov_deg": 69.47,
        "camera_vertical_fov_deg": 42.61,
        "camera_yaw_outward_deg": 29.73,
        "camera_pitch_down_deg": 5.0,
        "lidar_center_m": [0.0, 0.0, 0.210],
        "top_deck_height_m": 0.130,
        "wheel_diameter_m": 2 * WHEEL_RADIUS,
        "wheel_tread_width_m": 2 * WHEEL_HALF_WIDTH,
        "wheel_overall_width_with_hub_m": 0.0306,
        "motor_model": "Yahboom L-type 520, variant 51500753846588",
        "motor": asdict(MOTOR_CONFIG),
        "encoder_counts_per_wheel_revolution": MOTOR_CONFIG.encoder_counts_per_wheel_revolution,
        "kinematic_speed_at_nominal_rpm_m_s": KINEMATIC_SPEED_AT_NOMINAL_RPM,
        "provisional": ["chassis envelope/mass distribution", "wheel mass", "servo gain, damping and reflected inertia", "tire friction and loaded rolling radius", "supply voltage under load"],
    }
