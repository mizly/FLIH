"""Run: python -m unittest discover -s fly-gym/tests -p test_robot_geometry.py -v"""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mujoco
import numpy as np
import torch
from environment.mujoco_two_cam_env_random_obstacles import MuJoCoTwoCamEnv
from robot_config import LidarConfig, ROBOT_RADIUS, MOTOR_CONFIG, WHEEL_RADIUS, WHEEL_HALF_WIDTH


class RobotGeometryTests(unittest.TestCase):
    def make_env(self, **kwargs):
        env = MuJoCoTwoCamEnv(n_obstacles=0, width=64, height=64, **kwargs)
        self.addCleanup(env.close)
        env.place_robot(0, 0, 0, env.data.qpos.copy(), env.data.qvel.copy())
        mujoco.mj_forward(env.model, env.data)
        return env

    def test_geometry_both_scenes(self):
        for mode in ("checker", "realistic"):
            env = self.make_env(texture_mode=mode)
            for name, expected in {
                "left_wheel": [.124, .108, .03375], "right_wheel": [.124, -.108, .03375],
                "rear_left_wheel": [-.124, .108, .03375], "rear_right_wheel": [-.124, -.108, .03375],
            }.items():
                np.testing.assert_allclose(env.data.body(name).xpos, expected, atol=1e-8)
            np.testing.assert_allclose(env.data.site("lidar").xpos, [0, 0, .210])
            self.assertEqual(env.model.nu, 4)
            self.assertGreater(ROBOT_RADIUS, .19)

    def test_camera_pose_and_coverage(self):
        env = self.make_env()
        for name, side in (("left", 1), ("right", -1)):
            camera = env.data.camera(f"cam_{name}")
            np.testing.assert_allclose(camera.xpos, [.103, side * .035, .175])
            forward = -camera.xmat.reshape(3, 3)[:, 2]
            self.assertAlmostEqual(math.degrees(math.atan2(forward[1], forward[0])), side * 29.73, places=5)
            self.assertAlmostEqual(math.degrees(math.asin(forward[2])), -5, places=5)
        hfov = math.degrees(2 * math.atan(math.tan(math.radians(42.61 / 2)) * 16 / 9))
        self.assertAlmostEqual(hfov, 69.47, places=2)
        self.assertAlmostEqual(env.camera_width / env.camera_height, 16 / 9)
        self.assertEqual(env._get_obs()["cam_left"].shape, (64, 64, 3))

    def test_scan_distance_rotation_and_range_limit(self):
        env = self.make_env()
        self.assertAlmostEqual(float(env.lidar_scan()[np.argmin(np.abs(env.lidar_angles))]), 6.95, places=3)
        env.place_robot(1, 0, math.pi, env.data.qpos.copy(), env.data.qvel.copy())
        mujoco.mj_forward(env.model, env.data)
        self.assertAlmostEqual(float(env.lidar_scan()[np.argmin(np.abs(env.lidar_angles))]), 7.95, places=3)
        short = self.make_env(lidar_config=LidarConfig(max_range=2))
        np.testing.assert_allclose(short.lidar_scan(), 2)

    def test_scan_height_and_sample_hold(self):
        env = self.make_env()
        wall = env.model.geom("wall_e")
        wall.pos[:] = [1, 0, .3]
        mujoco.mj_forward(env.model, env.data)
        self.assertAlmostEqual(float(env.lidar_scan()[np.argmin(np.abs(env.lidar_angles))]), .95, places=3)
        wall.pos[0] = 2
        mujoco.mj_forward(env.model, env.data)
        self.assertAlmostEqual(float(env.lidar_scan()[np.argmin(np.abs(env.lidar_angles))]), .95, places=3)
        env.data.time += 1 / env.lidar_config.rate_hz + .001
        self.assertAlmostEqual(float(env.lidar_scan()[np.argmin(np.abs(env.lidar_angles))]), 1.95, places=3)
        wall.pos[2] = .05
        wall.size[2] = .05  # Below the horizontal scan plane.
        mujoco.mj_forward(env.model, env.data)
        env.data.time += 1 / env.lidar_config.rate_hz + .001
        self.assertAlmostEqual(float(env.lidar_scan()[np.argmin(np.abs(env.lidar_angles))]), 12, places=5)

    def test_drive_and_turn(self):
        env = self.make_env()
        for _ in range(100):
            env.step([.5, 0])
        self.assertGreater(env._base_xy()[0], .25)
        self.assertLess(abs(env._base_xy()[1]), .02)
        self.assertAlmostEqual(env.data.body("base").xpos[2], .1, places=3)
        for _ in range(100):
            env.step([0, 1])
        self.assertGreater(env._base_yaw(), .1)
        np.testing.assert_allclose(env.data.ctrl[:2], env.data.ctrl[2:])

    def test_wheel_dimensions_motor_limits_and_encoder(self):
        env = self.make_env()
        self.assertEqual(WHEEL_RADIUS, .03375)
        self.assertEqual(WHEEL_HALF_WIDTH, .01325)
        np.testing.assert_allclose(env.model.actuator_ctrlrange,
            np.tile([-MOTOR_CONFIG.max_wheel_speed_rad_s, MOTOR_CONFIG.max_wheel_speed_rad_s], (4, 1)))
        np.testing.assert_allclose(env.model.actuator_forcerange,
            np.tile([-MOTOR_CONFIG.rated_torque_nm, MOTOR_CONFIG.rated_torque_nm], (4, 1)))
        self.assertAlmostEqual(MOTOR_CONFIG.rated_torque_nm, .4314926)
        self.assertEqual(MOTOR_CONFIG.encoder_counts_per_wheel_revolution, 1760)
        env.data.qpos[env._wheel_qpos] = np.array([1, -1, .5, 0]) * 2 * np.pi
        mujoco.mj_forward(env.model, env.data)
        np.testing.assert_array_equal(env._sensor_vec()["wheel_encoder_counts"], [1760, -1760, 880, 0])
        env.place_robot(0, 0, 0, env.data.qpos.copy(), env.data.qvel.copy())
        mujoco.mj_forward(env.model, env.data)
        np.testing.assert_array_equal(env._sensor_vec()["wheel_encoder_counts"], 0)
        env.step([1, np.pi])
        self.assertTrue(np.all(np.abs(env.data.actuator_force) <= MOTOR_CONFIG.rated_torque_nm + 1e-8))

    def test_invalid_lidar_settings(self):
        for kwargs in ({"sample_rate_hz": 0}, {"max_range": 0}, {"rate_hz": 0}, {"fov_deg": 361}):
            with self.assertRaises(ValueError):
                LidarConfig(**kwargs)

    def test_tmini_scan_spec_and_hardware_angles(self):
        from core.lidar import lidar_proximity_features
        config = LidarConfig()
        self.assertEqual(config.num_rays, 667)
        self.assertEqual(LidarConfig(rate_hz=12).num_rays, 333)
        self.assertAlmostEqual(360 / config.num_rays, .54, places=2)
        # Raw clockwise device samples and CCW ROS samples yield identical inputs.
        raw_angles = np.deg2rad([30, 90, 200, 350])
        ranges = np.array([1, 2, 3, 4])
        raw = lidar_proximity_features(ranges, raw_angles, config, clockwise=True)
        ros = lidar_proximity_features(ranges, -raw_angles, config)
        np.testing.assert_allclose(raw, ros)
        self.assertAlmostEqual(raw[5], 1 - 1 / 12, places=6)
        np.testing.assert_allclose(lidar_proximity_features([np.nan, np.inf, 0], [0, 1, 2], config), 0)

    def test_scan_rate_does_not_drift_to_control_rate(self):
        env = self.make_env()
        timestamps = []
        for step in range(51):
            env.data.time = step * .02
            env.lidar_scan()
            if not timestamps or timestamps[-1] != env._lidar_time:
                timestamps.append(env._lidar_time)
        # Initial scan plus six updates in one second, despite 50 Hz control.
        self.assertEqual(len(timestamps), 7)

    def test_lidar_reaches_training_network(self):
        from agents.connectome_rnn_agent import ConnectomeAgent
        from models.connectome_rnn_model import LeakyConnectomeRNNCell
        from core.utils import obs_to_torch
        env = self.make_env()
        splits = {}
        start = 0
        for name in ("pr_L1_left", "pr_L2_left", "pr_L3_left", "pr_L1_right", "pr_L2_right", "pr_L3_right", "tactile_left", "tactile_right", "wind"):
            end = start + (14 if name == "wind" else 1)
            splits[name] = (start, end)
            start = end
        torch.manual_seed(7)
        cell = LeakyConnectomeRNNCell(
            W=(torch.eye(start) * .5).to_sparse_coo(), input_nodes=list(range(start)),
            output_nodes=list(range(start)), neuron_type_ids=torch.zeros(start, dtype=torch.long), num_cell_types=1,
        )
        agent = ConnectomeAgent(cell, [[.5, .5]] * start, splits, lidar_bins=12)
        obs = obs_to_torch(env._get_obs(), torch.device("cpu"), torch.float32)
        raw = agent.obs_to_x(obs)
        np.testing.assert_allclose(raw.detach().numpy()[0, -12:], obs["sensors"]["lidar_features"][0].numpy())
        # This is the same raw-feature sequence path used by DAgger replay.
        _, actions, _ = agent.forward_sequence(raw.unsqueeze(0).repeat(3, 1, 1))
        actions.square().sum().backward()
        self.assertGreater(agent.wind_mlp[0].weight.grad[:, 2:].abs().sum().item(), 0)
        self.assertTrue(torch.isfinite(actions).all())
        self.assertTrue((actions[..., 0].abs() <= 1).all())
        del obs["sensors"]["lidar_features"]
        with self.assertRaises(ValueError):
            agent.obs_to_x(obs)


if __name__ == "__main__":
    unittest.main()
