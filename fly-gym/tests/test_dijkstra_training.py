import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train_connectome_dijkstra import DijkstraPlanner, DijkstraTeacher, training_env_factory


class DijkstraTests(unittest.TestCase):
    def test_no_route_recovers_and_retries_without_ending_episode(self):
        teacher = DijkstraTeacher(2)
        teacher._get_base_xy_yaw = lambda env: (np.array([-1., 0.]), 0.)
        teacher._get_goal_xy = lambda env: np.array([1., 0.])
        teacher._get_obstacles_xy = lambda env: np.empty((0, 2))
        teacher._should_trigger_recovery = lambda env: False
        with patch.object(teacher.global_planner, 'plan', return_value=None) as plan:
            for _ in range(120):
                action = teacher.act(SimpleNamespace())
                self.assertIsNotNone(action)
                self.assertTrue(np.isfinite(action).all())
                self.assertTrue(teacher.force_teacher_action)
            self.assertIsNone(teacher._rec_phase)
            self.assertEqual(plan.call_count, 1)
            teacher.act(SimpleNamespace())
            self.assertEqual(plan.call_count, 2)

    def test_sustained_no_progress_triggers_recovery_not_short_stall(self):
        teacher = DijkstraTeacher(2)
        teacher._get_base_xy_yaw = lambda env: (np.array([-1., 0.]), 0.)
        teacher._get_goal_xy = lambda env: np.array([1., 0.])
        teacher._get_obstacles_xy = lambda env: np.empty((0, 2))
        teacher._should_trigger_recovery = lambda env: False
        env = SimpleNamespace()
        for _ in range(199):
            teacher.act(env)
            self.assertFalse(teacher.force_teacher_action)
        teacher.act(env)
        self.assertTrue(teacher.force_teacher_action)
        teacher.reset()
        self.assertFalse(teacher._recent_poses)

    def test_training_env_preserves_timeout(self):
        env = SimpleNamespace(max_steps=4000, stall_limit=50)
        wrapped = training_env_factory(lambda **kwargs: env)
        self.assertIs(wrapped(seed=42), env)
        self.assertEqual(env.max_steps, 4000)
        self.assertGreater(env.stall_limit, env.max_steps)

    def test_open_grid_shortest_route(self):
        planner = DijkstraPlanner(2, resolution=0.25, clearance=0.1)
        path = planner.plan([-1, -1], [1, 1], [])
        self.assertAlmostEqual(np.linalg.norm(np.diff(path, axis=0), axis=1).sum(), math.sqrt(8))

    def test_obstacle_detour_has_clear_segments(self):
        planner = DijkstraPlanner(2, resolution=0.2, clearance=0.2)
        obstacles = np.array([[0., 0.]])
        path = planner.plan([-1, 0], [1, 0], obstacles)
        self.assertIsNotNone(path)
        np.testing.assert_allclose(path[0], [-1, 0])
        np.testing.assert_allclose(path[-1], [1, 0])
        for a, b in zip(path[:-1], path[1:]):
            self.assertTrue(planner.segment_clear(a, b, obstacles, 0.4))

    def test_blocked_goal_and_disconnected_map(self):
        planner = DijkstraPlanner(2, resolution=0.2, clearance=0.2)
        self.assertIsNone(planner.plan([-1, 0], [0, 0], [[0, 0]]))
        wall = np.array([[0, y] for y in np.arange(-2, 2.1, 0.4)])
        self.assertIsNone(planner.plan([-1, 0], [1, 0], wall))

    def test_teacher_plans_once_and_turns_before_advancing(self):
        teacher = DijkstraTeacher(2)
        teacher._get_base_xy_yaw = lambda env: (np.array([-1., 0.]), math.pi)
        teacher._get_goal_xy = lambda env: np.array([1., 0.])
        teacher._get_obstacles_xy = lambda env: np.empty((0, 2))
        teacher._should_trigger_recovery = lambda env: False
        env = SimpleNamespace()
        with patch.object(teacher.global_planner, 'plan', wraps=teacher.global_planner.plan) as plan:
            for _ in range(3):
                action = teacher.act(env)
                self.assertEqual(action[0], 0)
                self.assertGreater(abs(action[1]), 1)
            self.assertEqual(plan.call_count, 1)
            teacher.reset()
            teacher.act(env)
            self.assertEqual(plan.call_count, 2)


if __name__ == '__main__':
    unittest.main()
