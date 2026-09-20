"""Non-blocking Huawei OMNI fusion for live camera and LiDAR observations."""

import math
import os
import threading
import time

from classification.classify_surroundings import classify_views, load_env, REPO_ROOT


SECTOR_CENTRES = {
    "front": 0.0,
    "left": math.pi / 2,
    "back": math.pi,
    "right": -math.pi / 2,
}


def _angle_distance(left, right):
    return abs((left - right + math.pi) % (2 * math.pi) - math.pi)


def summarize_scan(scan):
    """Compress a full turn into directional minima for an efficient API prompt."""
    summary = {name: None for name in SECTOR_CENTRES}
    for name, centre in SECTOR_CENTRES.items():
        values = [
            distance for angle, distance in zip(scan.angles, scan.ranges)
            if math.isfinite(angle) and math.isfinite(distance) and distance > 0
            and _angle_distance(angle, centre) <= math.pi / 4
        ]
        if values:
            summary[name] = round(min(values), 3)
    return {"unit": "m", "nearest_by_direction": summary, "returns": scan.returns}


class OmniFusion:
    """Keep the sensor loop fast while at most one cloud call runs in a worker."""

    def __init__(self, interval_s=5.0, enabled=True, classifier=classify_views):
        load_env(REPO_ROOT / ".env")
        self.enabled = enabled and bool(os.environ.get("YIBU_API_KEY", "").strip())
        self.interval_s = max(float(interval_s), 1.0)
        self.classifier = classifier
        self._frames = {}
        self._last_started = 0.0
        self._worker = None
        self._result = None
        self._lock = threading.Lock()

    def offer_camera(self, pane, jpeg):
        if pane not in (0, 1) or not jpeg:
            return
        with self._lock:
            self._frames[pane] = bytes(jpeg)

    def observe_scan(self, scan, direction):
        """Return the newest result and start a due analysis without blocking."""
        if not self.enabled:
            return None
        now = time.monotonic()
        with self._lock:
            ready = len(self._frames) == 2 and direction != "stopped"
            due = now - self._last_started >= self.interval_s
            busy = self._worker is not None and self._worker.is_alive()
            if ready and due and not busy:
                views = [
                    (("left", "right")[pane], self._frames[pane], "image/jpeg")
                    for pane in (0, 1)
                ]
                lidar = summarize_scan(scan)
                self._last_started = now
                self._worker = threading.Thread(
                    target=self._classify,
                    args=(views, lidar, direction),
                    name="omni-fusion",
                    daemon=True,
                )
                self._worker.start()
            return self._result

    def _classify(self, views, lidar, direction):
        try:
            result = self.classifier(
                views, lidar, "live_robot_perception", direction
            )
        except Exception as error:
            result = {"error": "%s: %s" % (type(error).__name__, error)}
        with self._lock:
            self._result = result

    def close(self):
        # The worker is a daemon so a slow network request cannot hold shutdown.
        pass
