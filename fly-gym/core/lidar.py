"""Shared simulation/hardware scan preprocessing (no serial-driver dependency)."""
import numpy as np
from robot_config import LIDAR_FEATURE_BINS


def lidar_proximity_features(ranges, angles, config, *, clockwise=False, yaw_offset=0.0):
    """Pool an angular scan into fixed sectors; ranges in m, angles in radians.

    ROS LaserScan angles normally increase counterclockwise. Raw T-mini packets
    increase clockwise: set clockwise=True for those, not for already-converted
    ROS scans. yaw_offset is the mounted sensor's CCW yaw relative to the robot.
    Invalid/nonpositive returns are unknown and represented by max range.
    """
    ranges = np.asarray(ranges, dtype=np.float64)
    angles = np.asarray(angles, dtype=np.float64)
    if ranges.ndim != 1 or ranges.shape != angles.shape:
        raise ValueError("LiDAR ranges and angles must be matching one-dimensional arrays")
    angles = (-angles if clockwise else angles) + yaw_offset
    angles = (angles + np.pi) % (2 * np.pi) - np.pi
    half_fov = np.deg2rad(config.fov_deg) / 2
    valid = np.isfinite(angles) & np.isfinite(ranges) & (ranges > 0)
    valid &= (angles >= -half_fov) & (angles < half_fov)
    sector = np.floor((angles[valid] + half_fov) / (2 * half_fov) * LIDAR_FEATURE_BINS).astype(int)
    nearest = np.full(LIDAR_FEATURE_BINS, config.max_range)
    np.minimum.at(nearest, np.clip(sector, 0, LIDAR_FEATURE_BINS - 1),
                  np.clip(ranges[valid], config.min_range, config.max_range))
    return (1 - nearest / config.max_range).astype(np.float32)
