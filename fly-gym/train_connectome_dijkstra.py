r"""Experimental global-path DAgger teacher for the existing fly policy.

Run from fly-gym: .\.venv\Scripts\python.exe train_connectome_dijkstra.py
Plans a shortest 8-connected grid route once per episode, then follows it.
Replans after recovery or substantial deviation caused by the student.
Uses privileged simulation geometry for labels; the student retains its usual
camera/LiDAR inputs. Outputs and auto-resume are isolated under dijkstra/.
"""
import heapq
import math
from collections import deque
from pathlib import Path

import numpy as np

from agents.teacher_analytic_agent import PlannerAnalyticTeacher
from robot_config import ROBOT_RADIUS


class DijkstraPlanner:
    def __init__(self, arena, resolution=0.15, clearance=ROBOT_RADIUS + 0.1):
        self.arena = float(arena)
        self.resolution = float(resolution)
        self.clearance = float(clearance)
        if self.resolution <= 0 or not 0 <= self.clearance < self.arena:
            raise ValueError("Invalid grid resolution or arena clearance")

    def segment_clear(self, a, b, obstacles, obstacle_radius):
        a, b = np.asarray(a), np.asarray(b)
        limit = self.arena - self.clearance
        if np.any(np.abs(a) > limit) or np.any(np.abs(b) > limit):
            return False
        obstacles = np.asarray(obstacles).reshape(-1, 2)
        delta = b - a
        t = np.clip(((obstacles - a) @ delta) / max(float(delta @ delta), 1e-12), 0, 1)
        distances = np.linalg.norm(obstacles - (a + t[:, None] * delta), axis=1)
        return bool(np.all(distances > obstacle_radius + self.clearance))

    def plan(self, start, goal, obstacles, obstacle_radius=0.4):
        start, goal = np.asarray(start, dtype=float), np.asarray(goal, dtype=float)
        obstacles = np.asarray(obstacles, dtype=float).reshape(-1, 2)
        if not self.segment_clear(start, start, obstacles, obstacle_radius):
            return None
        if not self.segment_clear(goal, goal, obstacles, obstacle_radius):
            return None
        axis = np.arange(-self.arena, self.arena + 1e-9, self.resolution)
        xx, yy = np.meshgrid(axis, axis)
        points = np.stack((xx, yy), axis=-1)
        # Half-cell padding conservatively protects edges between free cells.
        pad = self.resolution / math.sqrt(2)
        free = np.all(np.abs(points) <= self.arena - self.clearance, axis=-1)
        for obstacle in obstacles:
            free &= np.linalg.norm(points - obstacle, axis=-1) > obstacle_radius + self.clearance + pad
        cells = np.argwhere(free)
        if not len(cells):
            return None

        def attach(position):
            coords = points[free]
            for index in np.argsort(np.sum((coords - position) ** 2, axis=1)):
                if self.segment_clear(position, coords[index], obstacles, obstacle_radius):
                    return tuple(cells[index])
            return None

        source, target = attach(start), attach(goal)
        if source is None or target is None:
            return None
        queue, distances, parents = [(0.0, source)], {source: 0.0}, {}
        while queue:
            cost, cell = heapq.heappop(queue)
            if cost > distances[cell]:
                continue
            if cell == target:
                route = [cell]
                while route[-1] != source:
                    route.append(parents[route[-1]])
                return np.vstack([start, [points[c] for c in reversed(route)], goal])
            r, c = cell
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (-1, 1), (1, -1), (1, 1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < len(axis) and 0 <= nc < len(axis) and free[nr, nc]):
                    continue
                if dr and dc and not (free[r, nc] and free[nr, c]):
                    continue
                neighbor = (nr, nc)
                proposed = cost + self.resolution * math.hypot(dr, dc)
                if proposed < distances.get(neighbor, math.inf):
                    distances[neighbor] = proposed
                    parents[neighbor] = cell
                    heapq.heappush(queue, (proposed, neighbor))
        return None


class DijkstraTeacher(PlannerAnalyticTeacher):
    def __init__(self, arena_half_extent, resolution=0.15):
        super().__init__(arena_half_extent=arena_half_extent, recovery_turn_steps=80)
        self.global_planner = DijkstraPlanner(arena_half_extent, resolution)
        self.waypoint = 0
        self._recent_poses = deque(maxlen=200)
        self.force_teacher_action = False

    def reset(self):
        super().reset()
        self.waypoint = 0
        self._recent_poses.clear()
        self.force_teacher_action = False

    def _recover(self, xy, yaw, obstacles):
        # Planning can fail before physical contact, so contact_angle may not exist.
        if self._rec_phase is None:
            self.contact_angle = getattr(self, "contact_angle", 0.0) or 0.0
            self._start_recovery(xy, yaw, obstacles)
        self.force_teacher_action = True
        self._recent_poses.clear()
        action, finished = self._step_recovery()
        if finished:
            self._path = None
        return action

    def act(self, env):
        xy, yaw = self._get_base_xy_yaw(env)
        goal = self._get_goal_xy(env)
        obstacles = self._get_obstacles_xy(env)
        self.force_teacher_action = False
        self._recent_poses.append((xy.copy(), yaw))
        # Slow translation or intentional rotation is not a stall. Require a
        # sustained lack of both positional and heading progress before recovery.
        stuck = False
        if len(self._recent_poses) == self._recent_poses.maxlen:
            positions = np.array([p[0] for p in self._recent_poses])
            headings = np.unwrap([p[1] for p in self._recent_poses])
            stuck = (np.max(np.linalg.norm(positions - positions[0], axis=1)) < 0.03
                     and np.ptp(headings) < 0.15)
        if self._rec_phase is None and self._should_trigger_recovery(env):
            self._start_recovery(xy, yaw, obstacles)
        if self._rec_phase is not None or stuck:
            return self._recover(xy, yaw, obstacles)

        if self._path is not None:
            # Distance to the remaining polyline, rather than just its vertices.
            remaining = self._path[max(0, self.waypoint - 1):]
            a, b = remaining[:-1], remaining[1:]
            delta = b - a
            t = np.clip(np.sum((xy - a) * delta, axis=1) /
                        np.maximum(np.sum(delta * delta, axis=1), 1e-12), 0, 1)
            deviation = np.min(np.linalg.norm(xy - (a + t[:, None] * delta), axis=1))
            if deviation > 0.6:
                self._path = None
        if self._path is None:
            self._path = self.global_planner.plan(xy, goal, obstacles, self.obstacle_disc_r)
            self.waypoint = 1
            if self._path is None:
                # Keep the episode alive: collect recovery examples and retry
                # planning after the maneuver. The environment timeout still applies.
                return self._recover(xy, yaw, obstacles)

        while self.waypoint < len(self._path) - 1:
            following = self._path[self.waypoint + 1]
            if (np.linalg.norm(following - xy) > 0.4 or
                    not self.global_planner.segment_clear(xy, following, obstacles, self.obstacle_disc_r)):
                break
            self.waypoint += 1
        target = self._path[self.waypoint]
        if not self.global_planner.segment_clear(xy, target, obstacles, self.obstacle_disc_r):
            self._path = None
            return np.zeros(2, dtype=np.float32)  # Replan on the next call.
        delta = target - xy
        error = (math.atan2(delta[1], delta[0]) - yaw + math.pi) % (2 * math.pi) - math.pi
        # Rotate in place for large errors; slow on bends to avoid cutting corners.
        speed = 0.7 * max(0.0, math.cos(error)) ** 2
        if abs(error) > 0.7:
            speed = 0.0
        env.path_to_draw = self._path
        env.target_to_draw = target
        return np.array([speed, error], dtype=np.float32)


def training_env_factory(base_factory):
    def make_env(*args, **kwargs):
        env = base_factory(*args, **kwargs)
        # Preserve goal/time-limit termination, but let slow students collect
        # full training sequences. DijkstraTeacher handles sustained no progress.
        env.stall_limit = env.max_steps + 1
        return env
    return make_env


def main():
    import train_connectome_rnn_dagger as trainer

    # Configure only this process; the original trainer file is unchanged.
    trainer._make_teacher = lambda: DijkstraTeacher(trainer.ARENA_HALF_EXTENT)
    trainer._make_env = training_env_factory(trainer._make_env)
    trainer.BETA_DECAY = 0.1  # 100%, 90%, 80%, ... teacher contribution.
    trainer.CHECKPOINT_DIR = str(Path(trainer.CHECKPOINT_DIR) / "dijkstra")
    trainer.LOSS_DIR = str(Path(trainer.LOSS_DIR) / "dijkstra")
    trainer.FINAL_CHECKPOINT_PATH = str(Path(trainer.CHECKPOINT_DIR) / "connectome_rnn_dagger_princeton.pt")
    trainer.LOSS_CSV_PATH = str(Path(trainer.LOSS_DIR) / "connectome_rnn_dagger_loss.csv")
    trainer.RESUME_CHECKPOINT_PATH = "latest"
    print("[Dijkstra] Preplanned routes; isolated checkpoints/losses in dijkstra/.")
    print("[Dijkstra] First run starts fresh; later runs resume latest Dijkstra weights.")
    trainer.main()


if __name__ == "__main__":
    main()
